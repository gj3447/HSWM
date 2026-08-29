from hashlib import sha256
from pathlib import Path

import pytest

from _research.dnrd5.canonical_json import canonical_bytes, parse_canonical
from _research.dgx_mi.protocol import (
    ARMS, BLOCKS, EXPECTED_REQUEST_SHA256, MiRefusal, build_mi_request, make_mi_start_marker,
    USAGE_NORMALIZATION, validate_arm_identities, validate_mi_plan,
)
from _research.dgx_mi.preregistration import load_qcase024_material
from _research.dgx_q1.live_protocol import LiveQ1CaseMaterial, build_live_q1_request


ROOT = Path(__file__).parents[1]
MATERIAL_ROOT = ROOT / "_research/dgx_q1/preregistrations/hswm-dnrd5-dgx-live-q1-v3-2026-08-29/materials/QCASE-024"


@pytest.fixture
def mi_plan_raw() -> bytes:
    # Keep protocol tests dependent only on the public preregistration factory.
    from tests.test_dgx_mi_preregistration import _inputs
    from _research.dgx_mi.preregistration import build_mi_preregistration
    return build_mi_preregistration(_inputs())["plan.json"]


def test_qcase024_mi_request_is_the_q1_material_with_only_diagnostic_logprobs() -> None:
    material = load_qcase024_material(MATERIAL_ROOT)
    request = parse_canonical(build_mi_request("qwen-mi", material))
    assert request["logprobs"] is True
    assert request["top_logprobs"] == 20
    assert request["temperature"] == 0
    assert request["top_p"] == 1
    assert request["max_tokens"] == 256
    assert request["messages"][1]["content"].find("QCASE-024") >= 0
    baseline = parse_canonical(build_live_q1_request("qwen-mi", "FRESH_PROBE", LiveQ1CaseMaterial(
        "QCASE-024", material["instruction.txt"], material["model_input.json"],
        material["response_schema.json"], material["rng.bin"], 256)))
    expected = {**baseline, "logprobs": True, "top_logprobs": 20}
    assert request == expected


def test_pinned_served_model_request_has_the_declared_exact_hash() -> None:
    material = load_qcase024_material(MATERIAL_ROOT)
    raw = build_mi_request("qwen3.6-35b-a3b", material)
    assert sha256(raw).hexdigest() == EXPECTED_REQUEST_SHA256


def test_qcase024_mi_request_refuses_wrong_case_material(tmp_path: Path) -> None:
    material = load_qcase024_material(MATERIAL_ROOT)
    changed = dict(material)
    changed["model_input.json"] = canonical_bytes({"behaviorProjection": {}, "freshProbe": {"case": "QCASE-023"}})
    with pytest.raises(MiRefusal): build_mi_request("qwen-mi", changed)


def test_arm_identity_controls_require_async_pair_and_only_runtime_difference() -> None:
    from tests.test_dgx_mi_preregistration import _arm_identities
    identities = _arm_identities()
    validate_arm_identities(identities)
    identities["ASYNC_DISABLED"] = {**identities["ASYNC_DISABLED"], "tls_identity_sha256": canonical_bytes({"changed": True})}
    with pytest.raises(MiRefusal): validate_arm_identities(identities)


def test_arm_identity_refuses_missing_explicit_async_argv() -> None:
    # Reuse the validated factory and remove only the enabled arm control flag.
    def row(async_value: bool) -> dict[str, bytes]:
        from tests.test_dgx_mi_preregistration import _arm_identities
        return _arm_identities()["ASYNC_ENABLED" if async_value else "ASYNC_DISABLED"]
    identities = {"ASYNC_ENABLED": row(True), "ASYNC_DISABLED": row(False)}
    runtime = parse_canonical(identities["ASYNC_ENABLED"]["runtime_identity_sha256"])
    runtime["server_arguments"].remove("--async-scheduling")
    identities["ASYNC_ENABLED"] = {**identities["ASYNC_ENABLED"], "runtime_identity_sha256": canonical_bytes(runtime)}
    with pytest.raises(MiRefusal): validate_arm_identities(identities)


def test_arm_identity_refuses_declared_isolation_bytes_drift() -> None:
    from tests.test_dgx_mi_preregistration import _arm_identities
    identities = _arm_identities()
    for arm in identities:
        identities[arm] = {**identities[arm], "declared_isolation_contract_sha256": canonical_bytes({"not": "q1-v3"})}
    with pytest.raises(MiRefusal): validate_arm_identities(identities)


def test_start_marker_uses_exact_abba_sixteen_attempts(mi_plan_raw: bytes) -> None:
    marker = parse_canonical(make_mi_start_marker(mi_plan_raw))
    assert [(row["arm"], row["block_id"]) for row in parse_canonical(mi_plan_raw)["block_order"]] == list(BLOCKS)
    assert len(marker["scheduled_attempts"]) == 16
    assert marker["scheduled_attempts"][:4] == ["MI-024-V3-ASYNC_ENABLED-B01-R001", "MI-024-V3-ASYNC_ENABLED-B01-R002", "MI-024-V3-ASYNC_ENABLED-B01-R003", "MI-024-V3-ASYNC_ENABLED-B01-R004"]


def test_plan_binds_the_closed_usage_normalization_contract(mi_plan_raw: bytes) -> None:
    assert parse_canonical(mi_plan_raw)["usage_normalization"] == USAGE_NORMALIZATION


def test_plan_refuses_nonzero_retry_or_wrong_budget(mi_plan_raw: bytes) -> None:
    plan = parse_canonical(mi_plan_raw); plan["zero_retry"] = False
    with pytest.raises(MiRefusal): validate_mi_plan(canonical_bytes(plan))
    plan = parse_canonical(mi_plan_raw); plan["budget"] = 96
    with pytest.raises(MiRefusal): validate_mi_plan(canonical_bytes(plan))
    plan = parse_canonical(mi_plan_raw); plan["attempt_ids"] = plan["attempt_ids"][:-1]
    with pytest.raises(MiRefusal): validate_mi_plan(canonical_bytes(plan))
    plan = parse_canonical(mi_plan_raw); del plan["post_result_selection"]["q1_exact_ledger_sha256"]
    with pytest.raises(MiRefusal): validate_mi_plan(canonical_bytes(plan))
    plan = parse_canonical(mi_plan_raw); plan["request_sha256"] = "1" * 64
    with pytest.raises(MiRefusal): validate_mi_plan(canonical_bytes(plan))
