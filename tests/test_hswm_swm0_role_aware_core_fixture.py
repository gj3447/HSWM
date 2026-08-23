from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import struct
from typing import Any, Mapping

import numpy as np

from hswm.experiments.swm0w_s2s_operator import (
    S2SArm,
    S2SOperator,
    apply_physical_role_cycle,
    canonical_json,
    canonical_sha256,
    inverse_map_role_cycle_outputs,
    remove_q,
    restore_q,
    within_role_broadcast,
)
from hswm.experiments.swm0w_s2s_protocol import (
    LearnedModelArchive,
    parse_learned_model_archive,
)


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "swm0_role_aware_core_python_v1.canonical.json"
)
PARAMETER_HASH_DOMAIN = b"hswm-swm0w-s2s-parameters/v1\x00"
INPUT_HASH_DOMAIN = b"hswm-swm0-role-aware-t16-input/v1\x00"
OUTPUT_HASH_DOMAIN = b"hswm-swm0-role-aware-t16-recipient-output/v1\x00"
ARCHITECTURE_RECEIPT_SHA256 = (
    "65e6e27379793a7f483e8c34292ba060b60b89824822167e7483e03f7415ad29"
)


def _fixture() -> dict[str, Any]:
    raw = FIXTURE_PATH.read_bytes()
    assert len(raw) <= 196_608
    document = json.loads(raw)
    assert raw == (canonical_json(document) + "\n").encode("ascii")
    receipt = document.pop("receipt_sha256")
    assert receipt == canonical_sha256(document)
    document["receipt_sha256"] = receipt
    return document


def _segment(value: bytes) -> bytes:
    return len(value).to_bytes(8, "big") + value


def _numeric_array(record: Mapping[str, Any]) -> np.ndarray:
    raw = base64.b64decode(record["bytes_base64"], validate=True)
    assert base64.b64encode(raw).decode("ascii") == record["bytes_base64"]
    assert len(raw) == record["byte_length"]
    assert hashlib.sha256(raw).hexdigest() == record["bytes_sha256"]
    assert record["dtype"] == "float64-le"
    shape = tuple(record["shape"])
    values = np.frombuffer(raw, dtype="<f8").reshape(shape)
    assert np.isfinite(values).all()
    return values


def _ordered_int_bits(value: float) -> int:
    bits = struct.unpack(">q", struct.pack(">d", float(value)))[0]
    return 0x8000_0000_0000_0000 - bits if bits < 0 else bits


def _comparison_record(
    scalar: np.ndarray, numpy_value: np.ndarray
) -> dict[str, Any]:
    absolute = np.abs(scalar - numpy_value)
    relative = absolute / np.maximum(
        np.abs(numpy_value), np.finfo(np.float64).tiny
    )
    max_ulp = max(
        abs(_ordered_int_bits(float(left)) - _ordered_int_bits(float(right)))
        for left, right in zip(
            scalar.reshape(-1), numpy_value.reshape(-1), strict=True
        )
    )
    return {
        "max_absolute_error_hex": float(absolute.max()).hex(),
        "max_relative_error_hex": float(relative.max()).hex(),
        "max_ulp_distance": int(max_ulp),
    }


def _archive_document(record: Mapping[str, Any]) -> dict[str, Any]:
    raw = base64.b64decode(record["canonical_bytes_base64"], validate=True)
    assert base64.b64encode(raw).decode("ascii") == record[
        "canonical_bytes_base64"
    ]
    assert len(raw) == record["byte_length"]
    assert hashlib.sha256(raw).hexdigest() == record["raw_bytes_sha256"]
    archive = json.loads(raw)
    assert raw == (canonical_json(archive) + "\n").encode("ascii")
    assert archive["receipt_sha256"] == record["receipt_sha256"]
    return archive


def _parameters_from_python_archive(
    archive: LearnedModelArchive, projection: Mapping[str, Any]
) -> dict[str, np.ndarray]:
    assert archive.arm is S2SArm.T16
    assert archive.fitted is True
    assert archive.learned is True
    assert archive.parameter_count == 870
    assert projection["source"]["source_archive_receipt_sha256"] == (
        archive.receipt_sha256
    )
    assert projection["source"]["learned_state_sha256"] == (
        archive.learned_state_sha256
    )
    assert projection["source"]["structural_task_sha256"] == (
        archive.optimization.structural_task_sha256
    )

    parameters: dict[str, np.ndarray] = {}
    assert len(archive.tensors) == len(projection["tensors"]) == 6
    for python_tensor, projected_tensor in zip(
        archive.tensors, projection["tensors"], strict=True
    ):
        assert python_tensor.name == projected_tensor["name"]
        assert list(python_tensor.shape) == projected_tensor["shape"]
        assert python_tensor.bytes_sha256 == projected_tensor["bytes_sha256"]
        values = np.asarray(python_tensor.array(), dtype="<f8", order="C")
        raw = values.tobytes(order="C")
        assert len(raw) == projected_tensor["byte_length"]
        assert hashlib.sha256(raw).hexdigest() == python_tensor.bytes_sha256
        assert base64.b64encode(raw).decode("ascii") == projected_tensor[
            "bytes_base64"
        ]
        parameters[python_tensor.name] = values
    return parameters


def _parameter_sha256(parameters: Mapping[str, np.ndarray]) -> str:
    digest = hashlib.sha256(PARAMETER_HASH_DOMAIN)
    for name in sorted(parameters):
        values = np.asarray(parameters[name], dtype="<f8", order="C")
        descriptor = canonical_json(
            {"dtype": "float64-le", "name": name, "shape": list(values.shape)}
        ).encode("ascii")
        digest.update(_segment(descriptor))
        digest.update(_segment(values.tobytes(order="C")))
    return digest.hexdigest()


def _ordered_addresses(document: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    by_slot = {
        (int(row["role"][1:]), int(row["member_slot"])): row
        for row in document["incidences"]
    }
    assert len(by_slot) == 6
    return tuple(by_slot[(role, member)] for role in range(3) for member in range(2))


def _compiled_input(document: Mapping[str, Any]) -> np.ndarray:
    values = np.empty((3, 2, 4), dtype=np.float64)
    node_ids: set[str] = set()
    incidence_ids: set[str] = set()
    for row in _ordered_addresses(document):
        role = int(row["role"][1:])
        member = int(row["member_slot"])
        assert row["node_id"] not in node_ids
        assert row["incidence_id"] not in incidence_ids
        node_ids.add(row["node_id"])
        incidence_ids.add(row["incidence_id"])
        values[role, member] = np.asarray(row["activation"], dtype=np.float64)
    return values


def _input_sha256(document: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(INPUT_HASH_DOMAIN)
    digest.update(_segment(document["hyperedge_id"].encode("ascii")))
    for row in _ordered_addresses(document):
        metadata = {
            "incidence_id": row["incidence_id"],
            "member_slot": row["member_slot"],
            "node_id": row["node_id"],
            "role": row["role"],
        }
        digest.update(_segment(canonical_json(metadata).encode("ascii")))
        digest.update(
            _segment(np.asarray(row["activation"], dtype="<f8").tobytes(order="C"))
        )
    return digest.hexdigest()


def _output_sha256(document: Mapping[str, Any], output: np.ndarray) -> str:
    digest = hashlib.sha256(OUTPUT_HASH_DOMAIN)
    digest.update(_segment(document["hyperedge_id"].encode("ascii")))
    for index, row in enumerate(_ordered_addresses(document)):
        metadata = {
            "incidence_id": row["incidence_id"],
            "member_slot": row["member_slot"],
            "node_id": row["node_id"],
            "role": row["role"],
        }
        digest.update(_segment(canonical_json(metadata).encode("ascii")))
        role, member = divmod(index, 2)
        digest.update(
            _segment(np.asarray(output[role, member], dtype="<f8").tobytes(order="C"))
        )
    return digest.hexdigest()


def _numeric_core_state(parameters_sha256: str, intervention: str | None) -> str:
    return canonical_sha256(
        {
            "architecture_receipt_sha256": ARCHITECTURE_RECEIPT_SHA256,
            "arm": "T16",
            "evaluator_family_sha256": None,
            "initialization_seed": None,
            "intervention": intervention,
            "learned": False,
            "origin": "EXTERNAL_UNTRAINED",
            "parameters_sha256": parameters_sha256,
            "schema_version": "hswm-swm0w-s2s-operator/v1",
            "scientific_status": "ENGINEERING_CORE_ONLY_UNJUDGED",
        }
    )


def _scalar_forward(parameters: Mapping[str, np.ndarray], x: np.ndarray) -> np.ndarray:
    u = np.empty((3, 2, 16), dtype=np.float64)
    encoded = np.empty((3, 2, 16), dtype=np.float64)
    role_sums = np.empty((3, 16), dtype=np.float64)
    for role in range(3):
        for member in range(2):
            for hidden in range(16):
                u_sum = 0.0
                encoded_sum = 0.0
                for channel in range(4):
                    activation = float(x[role, member, channel])
                    u_sum += activation * float(parameters["phi_w"][role, channel, hidden])
                    encoded_sum += activation * float(
                        parameters["psi_w"][role, channel, hidden]
                    )
                u[role, member, hidden] = u_sum
                encoded[role, member, hidden] = encoded_sum
        for hidden in range(16):
            total = 0.0
            total += float(encoded[role, 0, hidden])
            total += float(encoded[role, 1, hidden])
            role_sums[role, hidden] = total

    def source_value(role: int, member: int, source: int, hidden: int) -> float:
        if source == role:
            return float(encoded[role, 1 - member, hidden])
        return float(role_sums[source, hidden])

    output = np.empty((3, 2, 2), dtype=np.float64)
    for role in range(3):
        for member in range(2):
            for channel in range(2):
                unary = 0.0
                for hidden in range(16):
                    unary += float(u[role, member, hidden]) * float(
                        parameters["unary_w"][role, channel, hidden]
                    )
                pair = 0.0
                for source in range(3):
                    for hidden in range(16):
                        pair_feature = float(u[role, member, hidden]) * source_value(
                            role, member, source, hidden
                        )
                        pair += pair_feature * float(
                            parameters["pair_w"][role, source, channel, hidden]
                        )
                q_value = 0.0
                for hidden in range(16):
                    product = 1.0
                    for source in range(3):
                        product *= source_value(role, member, source, hidden)
                    q_feature = float(u[role, member, hidden]) * product
                    q_value += q_feature * float(
                        parameters["q_w"][role, channel, hidden]
                    )
                prediction = unary
                prediction += pair
                prediction += q_value
                prediction += float(parameters["out_b"][role, channel])
                output[role, member, channel] = prediction
    return output


def _assert_output_pair(
    parameters: Mapping[str, np.ndarray],
    operator: S2SOperator,
    document: Mapping[str, Any],
    pair: Mapping[str, Any],
) -> np.ndarray:
    compiled = _compiled_input(document)
    scalar = _scalar_forward(parameters, compiled)
    expected_scalar = _numeric_array(pair["scalar"])
    np.testing.assert_array_equal(scalar, expected_scalar)
    assert pair["scalar_recipient_output_sha256"] == _output_sha256(
        document, scalar
    )
    numpy_value = operator.forward(compiled)
    expected_numpy = _numeric_array(pair["numpy"])
    np.testing.assert_allclose(numpy_value, expected_numpy, atol=5e-14, rtol=5e-14)
    np.testing.assert_allclose(scalar, numpy_value, atol=5e-14, rtol=5e-14)
    assert pair["comparison"] == _comparison_record(scalar, numpy_value)
    return scalar


def test_fixture_is_canonical_and_binds_two_python_learned_projections() -> None:
    fixture = _fixture()
    assert fixture["schema_version"] == (
        "hswm-swm0-role-aware-t16-python-parity-fixture/v1"
    )
    assert fixture["classification"] == (
        "TEST_ORACLE_ENGINEERING_PARITY_ONLY_NON_AUTHORIZING"
    )
    assert len(fixture["models"]) == 2

    for model_fixture in fixture["models"]:
        archive = parse_learned_model_archive(
            _archive_document(model_fixture["python_learned_archive"])
        )
        projection = model_fixture["projection"]
        projection_unsigned = {
            key: value for key, value in projection.items() if key != "receipt_sha256"
        }
        assert projection["receipt_sha256"] == canonical_sha256(projection_unsigned)
        parameters = _parameters_from_python_archive(archive, projection)
        assert sum(value.size for value in parameters.values()) == 870
        assert sum(value.nbytes for value in parameters.values()) == 6_960
        assert _parameter_sha256(parameters) == projection["parameters_sha256"]
        operator = S2SOperator(S2SArm.T16, parameters)
        assert operator.parameters_sha256 == projection["parameters_sha256"]
        assert operator.state_sha256 == model_fixture[
            "expected_numeric_core_state_sha256"
        ]
        assert operator.state_sha256 == _numeric_core_state(
            operator.parameters_sha256, None
        )

        assert len(model_fixture["worlds"]) == 6
        for world_fixture in model_fixture["worlds"]:
            document = world_fixture["input"]
            compiled = _compiled_input(document)
            np.testing.assert_array_equal(
                compiled, _numeric_array(world_fixture["compiled_input"])
            )
            assert world_fixture["input_sha256"] == _input_sha256(document)
            _assert_output_pair(
                parameters, operator, document, world_fixture["output"]
            )


def test_fixture_controls_replay_without_refitting() -> None:
    fixture = _fixture()
    for model_fixture in fixture["models"]:
        projection = model_fixture["projection"]
        parameters = _parameters_from_python_archive(
            parse_learned_model_archive(
                _archive_document(model_fixture["python_learned_archive"])
            ),
            projection,
        )
        operator = S2SOperator(S2SArm.T16, parameters)
        controls = model_fixture["controls"]
        base_world = model_fixture["worlds"][controls["world_index"]]
        base_document = base_world["input"]
        base_scalar = _assert_output_pair(
            parameters, operator, base_document, base_world["output"]
        )

        assert len(controls["member_swaps"]) == 8
        for swap in controls["member_swaps"]:
            _assert_output_pair(parameters, operator, swap["input"], swap["output"])

        assert len(controls["role_cycles"]) == 2
        for cycle_fixture in controls["role_cycles"]:
            cycle = tuple(cycle_fixture["cycle"])
            moved = apply_physical_role_cycle(_compiled_input(base_document), cycle)
            scalar = inverse_map_role_cycle_outputs(
                _scalar_forward(parameters, moved), cycle
            )
            np.testing.assert_array_equal(
                scalar, _numeric_array(cycle_fixture["scalar"])
            )
            numpy_value = inverse_map_role_cycle_outputs(
                operator.forward(moved), cycle
            )
            np.testing.assert_allclose(
                numpy_value,
                _numeric_array(cycle_fixture["numpy"]),
                atol=5e-14,
                rtol=5e-14,
            )
            assert cycle_fixture["scalar_recipient_output_sha256"] == _output_sha256(
                base_document, scalar
            )
            assert not np.array_equal(scalar, base_scalar)

        ablated, receipt = remove_q(operator)
        q_fixture = controls["q_removed"]
        assert ablated.parameters_sha256 == q_fixture["parameters_sha256"]
        assert ablated.state_sha256 == q_fixture["numeric_core_state_sha256"]
        assert receipt.removed_bytes_sha256 == q_fixture["removed_q_bytes_sha256"]
        assert hashlib.sha256(ablated.parameters["q_w"].tobytes(order="C")).hexdigest() == (
            q_fixture["positive_zero_q_bytes_sha256"]
        )
        q_scalar = _assert_output_pair(
            ablated.parameters, ablated, base_document, q_fixture["output"]
        )
        assert not np.array_equal(q_scalar, base_scalar)

        restored = restore_q(ablated, receipt)
        assert restored.parameters_sha256 == controls["q_restored"][
            "parameters_sha256"
        ]
        assert restored.state_sha256 == controls["q_restored"][
            "numeric_core_state_sha256"
        ]
        np.testing.assert_array_equal(
            restored.forward(_compiled_input(base_document)),
            _numeric_array(controls["q_restored"]["numpy"]),
        )
        np.testing.assert_array_equal(
            _scalar_forward(restored.parameters, _compiled_input(base_document)),
            _numeric_array(controls["q_restored"]["scalar"]),
        )

        broadcast = within_role_broadcast(base_scalar)
        np.testing.assert_array_equal(
            broadcast, _numeric_array(controls["broadcast"]["scalar"])
        )
        assert controls["broadcast"][
            "scalar_recipient_output_sha256"
        ] == _output_sha256(base_document, broadcast)
