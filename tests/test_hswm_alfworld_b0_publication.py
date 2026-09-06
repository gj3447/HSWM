"""Verify the recovered B0 occurrence's public evidence joins and claim ceiling."""

from hashlib import sha256
import json
from pathlib import Path

from _research.dnrd5.canonical_json import canonical_bytes


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results/raw/hswm_alfworld_b0_calibration_2026-08-30"
EVIDENCE = ROOT / "evidence/EVIDENCE_HSWM_ALFWORLD_B0_CALIBRATION_2026-08-30.json"


def read(path: Path) -> dict:
    return json.loads(path.read_bytes())


def assert_semantic_digest(value: dict, key: str) -> None:
    payload = {k: v for k, v in value.items() if k != key}
    assert sha256(canonical_bytes(payload)).hexdigest() == value[key]


def test_recovered_b0_artifacts_and_historical_execution_join() -> None:
    evidence = read(EVIDENCE)
    assert_semantic_digest(evidence, "receipt_sha256")
    for artifact in evidence["artifacts"]:
        assert sha256((ROOT / artifact["path"]).read_bytes()).hexdigest() == artifact["sha256"]
    for field in ("path", "selection_path"):
        digest_key = "sha256" if field == "path" else "selection_file_sha256"
        assert sha256((ROOT / evidence["protocol"][field]).read_bytes()).hexdigest() == evidence["protocol"][digest_key]
    original = read(RAW / "posthoc.public.json")
    live = read(RAW / "live.public.json")
    wrapper = read(RAW / "live-wrapper-receipt.json")
    assert_semantic_digest(live, "public_projection_sha256")
    assert original["source_archive"] == {k: wrapper["artifact"][k] for k in ("sha256", "bytes")}
    assert original["execution"]["commit"] == wrapper["source_commit"] == evidence["occurrence"]["source_commit"]
    assert original["execution"] == live["execution"]
    assert original["source_commitments"]["original_live_public_file_sha256"] == sha256((RAW / "live.public.json").read_bytes()).hexdigest()
    assert original["source_commitments"]["outer_private_receipt_file_sha256"] == live["private_receipt_sha256"]
    assert wrapper["exit_code"] == 2 and wrapper["status"] == "failed"
    assert wrapper["started_at"].startswith("2026-08-30")
    assert evidence["published_on"] == "2026-09-06"


def test_reprojection_preserves_observations_and_does_not_replace_terminal() -> None:
    old, new = (read(RAW / name) for name in ("posthoc.public.json", "reverified.public.json"))
    excluded = {"projection_execution", "derived_public_projection_sha256"}
    for value in (old, new):
        assert_semantic_digest(value, "derived_public_projection_sha256")
        assert value["status"] == "INCONCLUSIVE_MEASUREMENT_NOT_READY"
    assert {k: v for k, v in old.items() if k not in excluded} == {k: v for k, v in new.items() if k not in excluded}
    for value, name in ((old, "projection-wrapper-receipt.json"), (new, "verification-wrapper-receipt.json")):
        wrapper = read(RAW / name)
        assert wrapper["status"] == "success" and wrapper["exit_code"] == 0
        assert wrapper["source_commit"] == value["projection_execution"]["commit"]


def test_invalid_prefix_has_no_success_rate_or_comparator_claim() -> None:
    evidence = read(EVIDENCE)
    aggregate = read(RAW / "posthoc.public.json")["calibration_aggregate"]
    assert evidence["measurement"] == aggregate
    assert aggregate["split_counts"] == {"train": 1, "valid_seen": 0}
    assert aggregate["invalid_counts"] == {"train": 1, "valid_seen": 0}
    assert aggregate["failure_class"] == "AlfworldTextRuntimeError"
    assert aggregate["confidence_intervals"] is None
    for name, count in aggregate["resource_totals"].items():
        if name != "wall_microseconds":
            assert count == 0
    assert evidence["interpretation"]["success_rate"] is None
    assert evidence["interpretation"]["headroom_estimable"] is False
    assert evidence["claim_boundary"] == {
        "g0": "NOT_PASSED", "g1": "NOT_EVALUATED",
        "canonical_hswm_admission_performed": False,
        "hswm_learning_or_efficacy_established": False,
        "d4_heldout_behavior_evaluated": False,
        "usable_b0_comparator_ceiling_available": False,
        "s5_complete": False,
    }
    assert evidence["occurrence"]["retry_or_resume_permitted"] is False
    assert evidence["confidentiality"]["private_archive_checked_in"] is False
