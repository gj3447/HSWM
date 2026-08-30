"""Immutable public projection checks for the sealed v5 vLLM metrics probe."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from _research.dnrd5.canonical_json import canonical_bytes


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPOSITORY_ROOT / "manifests/HSWM_ALFWORLD_B0_VLLM_METRICS_QUALIFICATION_2026-08-30.json"
FILE_SHA256 = "5a3e2ddfae77d37e1e858ebc42267b76a61805dc3dc4fcce92ec2fd706464b12"
PREDECESSOR_PROTOCOL_SHA256 = "f754cb5fb6db2b97fa1b1a2055946f7dc63ce7c754909eec894e1848d07bc548"
PRIVATE_RECEIPT_FILE_SHA256 = "94971d57e8f69410a4398f3f5f8cc622c88fabd8df9a6c40b0eb6c46a1f95a60"
SOURCE_CLOSURE = {
    "_research/causal_composition/preregistrations/alfworld_b0_calibration_2026-08-30/protocol.v1.json": PREDECESSOR_PROTOCOL_SHA256,
    "_research/dgx_mi2/experiment.py": "364792bd6cbc25f9470d2864603c043601fae28f645901e7a4a358aebb602aad",
    "_research/dgx_q1/live_launcher.py": "96eaa33136c9bf845bd728634fa7a27b204034f8ea48849be6d607c2896eef47",
    "_research/dgx_q1/model_snapshot_manifest.py": "8376516734d76681f3fa8000de342d29a621bec5ea6428789e6b3c1caf5c66b2",
    "_research/dnrd5/canonical_json.py": "1e048548679c5e7fecbb84a66b8477077e37d6e94ccae44999e5598cc8eb6b39",
    "scripts/qualify_hswm_alfworld_b0_vllm_metrics.py": "7cce8ad3682d22797c8db770c21f68f99b1c600454b491ead602156636df1195",
    "src/hswm/experiments/alfworld_b0_dgx.py": "09924baa4c982360c421f8bf00bafa7f4292351d37d398b66a7a37c778a524a4",
    "src/hswm/experiments/alfworld_b0_vllm_metrics.py": "c00615b6488f139833a1aea41f1153822fbaf120e799a73ab8a8fa7f6c91f7ee",
    "src/hswm/selfmod/contracts.py": "f7529f15000963d8584f3a971a6b603f24ff623984127dea354b7fe2d5f7c920",
}


def _manifest() -> tuple[bytes, dict[str, object]]:
    raw = MANIFEST.read_bytes()
    value = json.loads(raw)
    assert isinstance(value, dict)
    return raw, value


def test_v5_public_metrics_manifest_is_exact_canonical_and_self_receipted() -> None:
    raw, value = _manifest()
    assert raw.endswith(b"\n") and raw.count(b"\n") == 1
    assert sha256(raw).hexdigest() == FILE_SHA256
    assert canonical_bytes(value) + b"\n" == raw
    unsigned = {key: item for key, item in value.items() if key != "receipt_sha256"}
    assert value["receipt_sha256"] == sha256(canonical_bytes(unsigned)).hexdigest()
    assert value["schema_version"] == "hswm-alfworld-b0-vllm-metrics-public/v1"
    assert value["status"] == "ENGINEERING_VLLM_METRICS_SEMANTICS_QUALIFIED_B0_NOT_RUN"
    assert value["claim_ceiling"] == "FRESH_SERVICE_COUNTER_SEMANTICS_ONLY_NOT_ALFWORLD_NOT_AGENT_EFFICACY_NOT_G0_NOT_G1"


def test_v5_public_metrics_manifest_binds_p1_closure_and_only_expected_counter_deltas() -> None:
    _raw, value = _manifest()
    binding = value["source_binding"]
    assert isinstance(binding, dict)
    assert binding["protocol_relative_path"] == (
        "_research/causal_composition/preregistrations/alfworld_b0_calibration_2026-08-30/protocol.v1.json"
    )
    assert binding["protocol_file_sha256"] == PREDECESSOR_PROTOCOL_SHA256
    assert binding["declared_source_sha256"] == SOURCE_CLOSURE
    assert value["private_receipt_file_sha256"] == PRIVATE_RECEIPT_FILE_SHA256
    assert value["counter_deltas"] == {
        "tokenize": {"running": 0, "success_total": 0, "prefix_hits": 0, "prefix_queries": 0},
        "completion": {"running": 0, "success_total": 1, "prefix_hits": 0, "prefix_queries": 0},
    }
    metrics = value["metrics"]
    assert isinstance(metrics, dict) and set(metrics) == {"startup", "after_tokenize", "after_completion"}
    assert [metrics[stage]["success_total"] for stage in ("startup", "after_tokenize", "after_completion")] == [0, 0, 1]
    for snapshot in metrics.values():
        assert snapshot["running"] == snapshot["prefix_hits"] == snapshot["prefix_queries"] == 0


def test_v5_public_metrics_manifest_contains_no_private_game_or_raw_payload_fields() -> None:
    raw, value = _manifest()
    forbidden = (
        "opaque_uid", "task_group_uid", "relative_path", "episode_uid", "observation",
        "outcome_receipt", "private_binding", "private_raw", "base64", "prompt", "message", "content",
    )
    rendered = raw.decode("utf-8", "strict").lower()
    keys = " ".join(_all_keys(value)).lower()
    for token in forbidden:
        assert f'"{token}":' not in rendered
        assert token not in keys.split()


def _all_keys(value: object) -> list[str]:
    if isinstance(value, dict):
        return [str(key) for key in value] + [child for item in value.values() for child in _all_keys(item)]
    if isinstance(value, list):
        return [child for item in value for child in _all_keys(item)]
    return []
