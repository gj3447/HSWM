"""Generate the independent Python oracle for the bounded TS T16 core.

This maintenance program deliberately runs the existing Python trainer and
operator without importing or executing TypeScript.  The checked-in fixture is
float-free canonical JSON: every non-integral value is committed as exact
little-endian float64 bytes.  Ordinary tests validate the fixture and never
refit the models.

Scientific status: engineering parity fixture only; no efficacy verdict.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import struct
import sys
from typing import Any, Mapping, Sequence

# Fix native reduction concurrency before NumPy is imported.  This generator is
# a maintenance command, not part of the pure TS evaluator or ordinary tests.
for _thread_variable in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_thread_variable] = "1"

import numpy as np

from hswm.experiments.swm0w_s2s_family import generate_task
from hswm.experiments.swm0w_s2s_operator import (
    ROLE_CYCLES,
    S2SArm,
    S2SOperator,
    apply_physical_role_cycle,
    canonical_json,
    canonical_sha256,
    compile_model_world,
    forward,
    inverse_map_role_cycle_outputs,
    remove_q,
    restore_q,
)
from hswm.experiments.swm0w_s2s_protocol import archive_learned_model
from hswm.experiments.swm0w_s2s_training import (
    S2STrainingConfig,
    fit_task_operator,
)
from hswm.experiments.swm0w_s2s_worlds import ModelWorldV1


FIXTURE_SCHEMA_VERSION = "hswm-swm0-role-aware-t16-python-parity-fixture/v1"
ARCHIVE_SCHEMA_VERSION = "hswm-swm0-role-aware-t16-parameter-archive/v1"
TENSOR_SCHEMA_VERSION = "hswm-swm0-role-aware-t16-parameter-tensor/v1"
INPUT_SCHEMA_VERSION = "hswm-swm0-role-aware-t16-input/v1"
ARCHIVE_CLASSIFICATION = "ENGINEERING_CORE_PARAMETER_ARCHIVE_NON_AUTHORIZING"
CLAIM_BOUNDARY = (
    "NUMERIC_PARAMETER_PROJECTION_ONLY_NO_TRAINING_OR_EFFICACY_AUTHORIZATION"
)
PYTHON_ARCHITECTURE_RECEIPT_SHA256 = (
    "65e6e27379793a7f483e8c34292ba060b60b89824822167e7483e03f7415ad29"
)
PARAMETER_HASH_DOMAIN = b"hswm-swm0w-s2s-parameters/v1\x00"
INPUT_HASH_DOMAIN = b"hswm-swm0-role-aware-t16-input/v1\x00"
OUTPUT_HASH_DOMAIN = b"hswm-swm0-role-aware-t16-recipient-output/v1\x00"

WORLD_VALUES = (
    (0, 0, 0, 0, 0, 0),
    (0, 1, 2, 3, 4, 0),
    (4, 3, 2, 1, 0, 4),
    (1, 1, 3, 0, 2, 4),
    (2, 4, 0, 0, 3, 1),
    (4, 4, 4, 4, 4, 4),
)
INCIDENCE_ENUMERATION = (4, 1, 5, 0, 3, 2)
MODEL_SPECS = (
    {
        "label": "A",
        "seed_material": "hswm-swm0-role-aware-core-parity/a",
        "draw_index": 0,
        "initializer_seed": 0,
        "learning_rate": 1.0e-4,
        "expected_parameters_sha256": (
            "02169d99cf2f376105851245dd99f30b627eba7d89a7e3f87e556284ede71c4b"
        ),
    },
    {
        "label": "B",
        "seed_material": "hswm-swm0-role-aware-core-parity/b",
        "draw_index": 7,
        "initializer_seed": 17,
        "learning_rate": 0.003,
        "expected_parameters_sha256": (
            "94548fc587c16d29764292857daa4960b5a75d6dec42ce09b2d5bcabe20aead1"
        ),
    },
)


class FixtureGenerationError(RuntimeError):
    """Raised when the independent fixture contract drifts."""


def _canonical_bytes(value: Any) -> bytes:
    return canonical_json(value).encode("ascii") + b"\n"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _segment(data: bytes) -> bytes:
    return len(data).to_bytes(8, "big") + data


def _float64_bytes(value: np.ndarray) -> bytes:
    array = np.asarray(value, dtype="<f8", order="C")
    if not np.isfinite(array).all():
        raise FixtureGenerationError("fixture arrays must remain finite")
    return array.tobytes(order="C")


def _numeric_record(value: np.ndarray) -> dict[str, Any]:
    raw = _float64_bytes(value)
    return {
        "byte_length": len(raw),
        "bytes_base64": base64.b64encode(raw).decode("ascii"),
        "bytes_sha256": _sha256(raw),
        "dtype": "float64-le",
        "shape": list(value.shape),
    }


def _canonical_document_record(value: Mapping[str, Any]) -> dict[str, Any]:
    raw = _canonical_bytes(value)
    return {
        "byte_length": len(raw),
        "canonical_bytes_base64": base64.b64encode(raw).decode("ascii"),
        "raw_bytes_sha256": _sha256(raw),
        "receipt_sha256": value["receipt_sha256"],
    }


def _role_member_index(role: int, member: int) -> int:
    return 2 * role + member


def _input_document(
    world_index: int,
    compiled: np.ndarray,
    swap_mask: tuple[bool, bool, bool] = (False, False, False),
) -> dict[str, Any]:
    canonical_entries: list[dict[str, Any]] = []
    for role in range(3):
        for destination_member in range(2):
            source_member = (
                1 - destination_member
                if swap_mask[role]
                else destination_member
            )
            physical_index = _role_member_index(role, source_member)
            canonical_entries.append(
                {
                    "activation": [
                        int(value)
                        if float(value).is_integer()
                        else float(value)
                        for value in compiled[role, source_member]
                    ],
                    "incidence_id": f"w{world_index}.r{role}.m{source_member}.inc",
                    "member_slot": destination_member,
                    "node_id": f"w{world_index}.r{role}.m{source_member}.node",
                    "role": f"r{role}",
                }
            )
    return {
        "schema_version": INPUT_SCHEMA_VERSION,
        "hyperedge_id": f"fixture.world.{world_index}",
        "incidences": [canonical_entries[index] for index in INCIDENCE_ENUMERATION],
    }


def _compiled_from_input(document: Mapping[str, Any]) -> np.ndarray:
    result = np.empty((3, 2, 4), dtype=np.float64)
    for incidence in document["incidences"]:
        role = int(incidence["role"][1:])
        member = int(incidence["member_slot"])
        result[role, member] = np.asarray(incidence["activation"], dtype=np.float64)
    return result


def _ordered_addresses(document: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    by_slot = {
        (int(row["role"][1:]), int(row["member_slot"])): row
        for row in document["incidences"]
    }
    return tuple(by_slot[(role, member)] for role in range(3) for member in range(2))


def _input_sha256(document: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(INPUT_HASH_DOMAIN)
    digest.update(_segment(document["hyperedge_id"].encode("ascii")))
    for address in _ordered_addresses(document):
        metadata = {
            "incidence_id": address["incidence_id"],
            "member_slot": address["member_slot"],
            "node_id": address["node_id"],
            "role": address["role"],
        }
        digest.update(_segment(canonical_json(metadata).encode("ascii")))
        activation = np.asarray(address["activation"], dtype="<f8")
        digest.update(_segment(activation.tobytes(order="C")))
    return digest.hexdigest()


def _recipient_output_sha256(
    document: Mapping[str, Any], output: np.ndarray
) -> str:
    digest = hashlib.sha256(OUTPUT_HASH_DOMAIN)
    digest.update(_segment(document["hyperedge_id"].encode("ascii")))
    for index, address in enumerate(_ordered_addresses(document)):
        metadata = {
            "incidence_id": address["incidence_id"],
            "member_slot": address["member_slot"],
            "node_id": address["node_id"],
            "role": address["role"],
        }
        digest.update(_segment(canonical_json(metadata).encode("ascii")))
        role, member = divmod(index, 2)
        digest.update(_segment(_float64_bytes(output[role, member])))
    return digest.hexdigest()


def _parameter_sha256(parameters: Mapping[str, np.ndarray]) -> str:
    digest = hashlib.sha256(PARAMETER_HASH_DOMAIN)
    for name in sorted(parameters):
        array = np.asarray(parameters[name], dtype="<f8", order="C")
        descriptor = canonical_json(
            {"dtype": "float64-le", "name": name, "shape": list(array.shape)}
        ).encode("ascii")
        digest.update(_segment(descriptor))
        digest.update(_segment(array.tobytes(order="C")))
    return digest.hexdigest()


def _numeric_core_state_sha256(parameters_sha256: str, intervention: str | None) -> str:
    return canonical_sha256(
        {
            "architecture_receipt_sha256": PYTHON_ARCHITECTURE_RECEIPT_SHA256,
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


def _operator_binding_sha256(
    projection: Mapping[str, Any], numeric_core_state_sha256: str, intervention: str
) -> str:
    source = projection["source"]
    return canonical_sha256(
        {
            "archive_receipt_sha256": projection["receipt_sha256"],
            "arm": "T16",
            "classification": ARCHIVE_CLASSIFICATION,
            "claim_boundary": CLAIM_BOUNDARY,
            "intervention": intervention,
            "numeric_core_learned": False,
            "numeric_core_state_sha256": numeric_core_state_sha256,
            "parameter_count": 870,
            "parameters_sha256": projection["parameters_sha256"],
            "roles": ["r0", "r1", "r2"],
            "schema_version": "hswm-swm0-role-aware-t16-operator-binding/v1",
            "source_archive_receipt_sha256": source[
                "source_archive_receipt_sha256"
            ],
            "source_learned_state_sha256": source["learned_state_sha256"],
            "source_projection_fitted_claim": True,
            "source_projection_learned_claim": True,
            "structural_task_sha256": source["structural_task_sha256"],
        }
    )


def _scalar_forward(parameters: Mapping[str, np.ndarray], x: np.ndarray) -> np.ndarray:
    """Frozen Python equation and explicit order mirrored byte-exactly by TS."""

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

    def source_value(
        recipient_role: int,
        recipient_member: int,
        source_role: int,
        hidden: int,
    ) -> float:
        if source_role == recipient_role:
            return float(encoded[recipient_role, 1 - recipient_member, hidden])
        return float(role_sums[source_role, hidden])

    result = np.empty((3, 2, 2), dtype=np.float64)
    for role in range(3):
        for member in range(2):
            for channel in range(2):
                unary = 0.0
                for hidden in range(16):
                    unary += float(u[role, member, hidden]) * float(
                        parameters["unary_w"][role, channel, hidden]
                    )
                pair = 0.0
                for source_role in range(3):
                    for hidden in range(16):
                        pair_feature = float(u[role, member, hidden]) * source_value(
                            role, member, source_role, hidden
                        )
                        pair += pair_feature * float(
                            parameters["pair_w"][role, source_role, channel, hidden]
                        )
                q_value = 0.0
                for hidden in range(16):
                    product = 1.0
                    for source_role in range(3):
                        product *= source_value(
                            role, member, source_role, hidden
                        )
                    q_feature = float(u[role, member, hidden]) * product
                    q_value += q_feature * float(
                        parameters["q_w"][role, channel, hidden]
                    )
                prediction = unary
                prediction += pair
                prediction += q_value
                prediction += float(parameters["out_b"][role, channel])
                result[role, member, channel] = prediction
    if not np.isfinite(result).all():
        raise FixtureGenerationError("scalar oracle produced non-finite output")
    return result


def _ordered_int_bits(value: float) -> int:
    bits = struct.unpack(">q", struct.pack(">d", float(value)))[0]
    return 0x8000_0000_0000_0000 - bits if bits < 0 else bits


def _comparison_record(scalar: np.ndarray, numpy_value: np.ndarray) -> dict[str, Any]:
    absolute = np.abs(scalar - numpy_value)
    relative = absolute / np.maximum(np.abs(numpy_value), np.finfo(np.float64).tiny)
    max_ulp = max(
        abs(_ordered_int_bits(float(left)) - _ordered_int_bits(float(right)))
        for left, right in zip(scalar.reshape(-1), numpy_value.reshape(-1), strict=True)
    )
    return {
        "max_absolute_error_hex": float(absolute.max()).hex(),
        "max_relative_error_hex": float(relative.max()).hex(),
        "max_ulp_distance": int(max_ulp),
    }


def _output_pair(
    parameters: Mapping[str, np.ndarray],
    compiled: np.ndarray,
    document: Mapping[str, Any],
) -> dict[str, Any]:
    scalar = _scalar_forward(parameters, compiled)
    numpy_value = forward(S2SOperator(S2SArm.T16, parameters), compiled)
    return {
        "scalar": _numeric_record(scalar),
        "numpy": _numeric_record(numpy_value),
        "comparison": _comparison_record(scalar, numpy_value),
        "scalar_recipient_output_sha256": _recipient_output_sha256(document, scalar),
    }


def _projection(archive: Any, model: Any) -> dict[str, Any]:
    tensors = []
    for tensor in archive.tensors:
        raw = _float64_bytes(model.parameters[tensor.name])
        if _sha256(raw) != tensor.bytes_sha256:
            raise FixtureGenerationError("Python archive tensor bytes drifted")
        tensors.append(
            {
                "schema_version": TENSOR_SCHEMA_VERSION,
                "dtype": "float64-le",
                "name": tensor.name,
                "shape": list(tensor.shape),
                "byte_length": len(raw),
                "bytes_base64": base64.b64encode(raw).decode("ascii"),
                "bytes_sha256": tensor.bytes_sha256,
            }
        )
    unsigned = {
        "schema_version": ARCHIVE_SCHEMA_VERSION,
        "classification": ARCHIVE_CLASSIFICATION,
        "claim_boundary": CLAIM_BOUNDARY,
        "arm": "T16",
        "roles": ["r0", "r1", "r2"],
        "parameter_count": 870,
        "parameters_sha256": model.parameters_sha256,
        "source": {
            "kind": "PYTHON_LEARNED_MODEL_ARCHIVE_PROJECTION",
            "source_archive_schema_version": "hswm-swm0w-s2s-learned-archive/v1",
            "source_archive_receipt_sha256": archive.receipt_sha256,
            "learned_state_sha256": model.state_sha256,
            "structural_task_sha256": model.task_binding_sha256,
            "fitted": True,
            "learned": True,
            "assurance": (
                "SOURCE_ARCHIVE_RECEIPT_PIN_ONLY_NOT_REVALIDATED_BY_TYPESCRIPT"
            ),
        },
        "tensors": tensors,
    }
    return {**unsigned, "receipt_sha256": canonical_sha256(unsigned)}


def _broadcast(value: np.ndarray) -> np.ndarray:
    result = np.empty_like(value)
    for role in range(3):
        for channel in range(2):
            pooled = 0.5 * float(value[role, 0, channel]) + 0.5 * float(
                value[role, 1, channel]
            )
            result[role, 0, channel] = pooled
            result[role, 1, channel] = pooled
    return result


def _build_model_fixture(spec: Mapping[str, Any]) -> dict[str, Any]:
    external_seed = hashlib.sha256(spec["seed_material"].encode("ascii")).digest()
    task = generate_task(external_seed=external_seed, draw_index=spec["draw_index"])
    train = tuple(task.iter_cases("train"))
    dev = tuple(task.iter_cases("dev"))
    config = S2STrainingConfig(
        seed=spec["initializer_seed"],
        max_updates=1,
        learning_rate=spec["learning_rate"],
    )
    model = fit_task_operator(task, train, dev, arm=S2SArm.T16, config=config)
    if not model.learned or model.optimization.best_update != 1:
        raise FixtureGenerationError(f"model {spec['label']} did not learn at update one")
    if model.parameters_sha256 != spec["expected_parameters_sha256"]:
        raise FixtureGenerationError(
            f"model {spec['label']} parameter commitment drifted: "
            f"{model.parameters_sha256}"
        )
    if _parameter_sha256(model.parameters) != model.parameters_sha256:
        raise FixtureGenerationError("independent parameter hash disagrees")

    archive = archive_learned_model(model)
    projection = _projection(archive, model)
    base_operator = model.as_unlabeled_operator()
    if base_operator.state_sha256 != _numeric_core_state_sha256(
        model.parameters_sha256, None
    ):
        raise FixtureGenerationError("numeric core state hash disagrees with Python")

    worlds = []
    for world_index, raw_values in enumerate(WORLD_VALUES):
        world = ModelWorldV1(raw_values)
        compiled = compile_model_world(world)
        document = _input_document(world_index, compiled)
        if not np.array_equal(_compiled_from_input(document), compiled):
            raise FixtureGenerationError("input document compiler drifted")
        worlds.append(
            {
                "raw_values": list(raw_values),
                "input": document,
                "input_sha256": _input_sha256(document),
                "compiled_input": _numeric_record(compiled),
                "output": _output_pair(model.parameters, compiled, document),
            }
        )

    control_world_index = 1
    control_world = ModelWorldV1(WORLD_VALUES[control_world_index])
    base_compiled = compile_model_world(control_world)
    base_document = _input_document(control_world_index, base_compiled)
    base_scalar = _scalar_forward(model.parameters, base_compiled)

    member_swaps = []
    for mask_value in range(8):
        mask = tuple(bool(mask_value & (1 << role)) for role in range(3))
        swapped_document = _input_document(
            control_world_index, base_compiled, mask
        )
        swapped_compiled = _compiled_from_input(swapped_document)
        member_swaps.append(
            {
                "mask": [int(value) for value in mask],
                "input": swapped_document,
                "input_sha256": _input_sha256(swapped_document),
                "output": _output_pair(
                    model.parameters, swapped_compiled, swapped_document
                ),
            }
        )

    role_cycles = []
    for cycle in ROLE_CYCLES:
        moved = apply_physical_role_cycle(base_compiled, cycle)
        scalar = inverse_map_role_cycle_outputs(
            _scalar_forward(model.parameters, moved), cycle
        )
        numpy_value = inverse_map_role_cycle_outputs(
            forward(base_operator, moved), cycle
        )
        role_cycles.append(
            {
                "cycle": list(cycle),
                "scalar": _numeric_record(scalar),
                "numpy": _numeric_record(numpy_value),
                "comparison": _comparison_record(scalar, numpy_value),
                "scalar_recipient_output_sha256": _recipient_output_sha256(
                    base_document, scalar
                ),
            }
        )

    ablated, python_q_receipt = remove_q(base_operator)
    restored = restore_q(ablated, python_q_receipt)
    if (
        restored.parameters_sha256 != base_operator.parameters_sha256
        or restored.state_sha256 != base_operator.state_sha256
        or any(
            restored.parameters[name].tobytes(order="C")
            != base_operator.parameters[name].tobytes(order="C")
            for name in restored.parameters
        )
    ):
        raise FixtureGenerationError("Python Q restoration was not exact")
    q_output = _output_pair(ablated.parameters, base_compiled, base_document)
    if q_output["scalar"]["bytes_sha256"] == _numeric_record(base_scalar)[
        "bytes_sha256"
    ]:
        raise FixtureGenerationError("Q removal did not change the control world")
    broadcast = _broadcast(base_scalar)

    base_core_state = base_operator.state_sha256
    base_binding = _operator_binding_sha256(projection, base_core_state, "NONE")
    ablated_projection = {**projection, "parameters_sha256": ablated.parameters_sha256}
    ablated_core_state = ablated.state_sha256
    ablated_binding = _operator_binding_sha256(
        ablated_projection, ablated_core_state, "Q_REMOVED"
    )
    return {
        "label": spec["label"],
        "generation": {
            "seed_material": spec["seed_material"],
            "external_seed_commitment_sha256": hashlib.sha256(
                external_seed
            ).hexdigest(),
            "draw_index": spec["draw_index"],
            "initializer_seed": spec["initializer_seed"],
            "learning_rate_hex": float(spec["learning_rate"]).hex(),
            "max_updates": 1,
            "best_update": model.optimization.best_update,
        },
        "python_learned_archive": _canonical_document_record(archive.canonical()),
        "projection": projection,
        "expected_numeric_core_state_sha256": base_core_state,
        "expected_operator_binding_sha256": base_binding,
        "worlds": worlds,
        "controls": {
            "world_index": control_world_index,
            "member_swaps": member_swaps,
            "role_cycles": role_cycles,
            "q_removed": {
                "parameters_sha256": ablated.parameters_sha256,
                "numeric_core_state_sha256": ablated_core_state,
                "operator_binding_sha256": ablated_binding,
                "removed_q_bytes_sha256": python_q_receipt.removed_bytes_sha256,
                "positive_zero_q_bytes_sha256": _sha256(bytes(768)),
                "python_receipt": python_q_receipt.canonical(),
                "output": q_output,
            },
            "q_restored": {
                "parameters_sha256": restored.parameters_sha256,
                "numeric_core_state_sha256": restored.state_sha256,
                "scalar": _numeric_record(
                    _scalar_forward(restored.parameters, base_compiled)
                ),
                "numpy": _numeric_record(forward(restored, base_compiled)),
            },
            "broadcast": {
                "source_scalar_bytes_sha256": _numeric_record(base_scalar)[
                    "bytes_sha256"
                ],
                "scalar": _numeric_record(broadcast),
                "scalar_recipient_output_sha256": _recipient_output_sha256(
                    base_document, broadcast
                ),
            },
        },
    }


def build_fixture() -> dict[str, Any]:
    models = [_build_model_fixture(spec) for spec in MODEL_SPECS]
    unsigned = {
        "schema_version": FIXTURE_SCHEMA_VERSION,
        "classification": "TEST_ORACLE_ENGINEERING_PARITY_ONLY_NON_AUTHORIZING",
        "claim_boundary": (
            "NO_NEW_TRAINING_CLAIM_NO_EFFICACY_VERDICT_NO_PROTOCOL_PASS"
        ),
        "arithmetic_contract": {
            "scalar_oracle": "PYTHON_EXPLICIT_ASCENDING_D_H_SOURCE_LOOPS",
            "scalar_typescript_expected": "EXACT_FLOAT64_BYTES",
            "numpy_einsum_absolute_tolerance_hex": float(5e-14).hex(),
            "numpy_einsum_relative_tolerance_hex": float(5e-14).hex(),
            "member_equivariance_absolute_tolerance_hex": float(2e-14).hex(),
            "member_equivariance_relative_tolerance_hex": float(2e-14).hex(),
            "parameter_and_restore_tolerance": "EXACT_BYTES_ONLY",
        },
        "runtime_record": {
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "numpy_version": np.__version__,
            "byteorder": sys.byteorder,
            "threads_per_native_pool": 1,
        },
        "world_values": [list(values) for values in WORLD_VALUES],
        "models": models,
    }
    return {**unsigned, "receipt_sha256": canonical_sha256(unsigned)}


def _default_output() -> Path:
    return Path(__file__).resolve().parents[2] / "tests" / "fixtures" / (
        "swm0_role_aware_core_python_v1.canonical.json"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=_default_output())
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args(argv)
    fixture = build_fixture()
    encoded = _canonical_bytes(fixture)
    if len(encoded) > 196_608:
        raise FixtureGenerationError(
            f"fixture exceeds 192 KiB hard cap: {len(encoded)} bytes"
        )
    if arguments.check:
        if not arguments.output.is_file() or arguments.output.read_bytes() != encoded:
            raise FixtureGenerationError("checked-in fixture differs from regeneration")
        print(
            json.dumps(
                {
                    "byte_length": len(encoded),
                    "raw_sha256": _sha256(encoded),
                    "receipt_sha256": fixture["receipt_sha256"],
                    "status": "MATCH",
                },
                sort_keys=True,
            )
        )
        return 0
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(encoded)
    print(
        json.dumps(
            {
                "byte_length": len(encoded),
                "output": str(arguments.output),
                "raw_sha256": _sha256(encoded),
                "receipt_sha256": fixture["receipt_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
