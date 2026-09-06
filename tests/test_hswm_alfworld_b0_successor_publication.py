"""The S-5 completed B0 floor retains its original and derived projections."""
from hashlib import sha256
import json
from pathlib import Path

from hswm.selfmod.contracts import canonical_sha256

ROOT = Path(__file__).resolve().parents[1]


def test_b0_successor_publication_preserves_complete_floor_and_content_bindings():
    evidence = json.loads((ROOT / "evidence/EVIDENCE_HSWM_ALFWORLD_B0_SUCCESSOR_2026-09-06.json").read_bytes())
    assert evidence["receipt_sha256"] == canonical_sha256({k: v for k, v in evidence.items() if k != "receipt_sha256"})
    for artifact in evidence["artifacts"]:
        assert sha256((ROOT / artifact["path"]).read_bytes()).hexdigest() == artifact["sha256"]
    raw = ROOT / "results/raw/hswm_alfworld_b0_successor_2026-09-06"
    original = json.loads((raw / "b0.public.json").read_bytes())
    derived = json.loads((raw / "posthoc.public.json").read_bytes())
    assert original["public_projection_sha256"] == canonical_sha256({k: v for k, v in original.items() if k != "public_projection_sha256"})
    assert original["private_receipt_sha256"] == evidence["occurrence"]["private_receipt_file_sha256"]
    assert original["resource_totals"] == {}  # Preserved original wrapper omission.
    assert derived["derived_public_projection_sha256"] == canonical_sha256({k: v for k, v in derived.items() if k != "derived_public_projection_sha256"})
    assert derived["source_archive"] == {"bytes": evidence["occurrence"]["archive_bytes"], "sha256": evidence["occurrence"]["archive_sha256"]}
    aggregate = derived["calibration_aggregate"]
    assert original["status"] == aggregate["status"] == "EXPLORATORY_B0_CALIBRATION_COMPLETE_G0_NOT_PASSED"
    assert aggregate["headroom_classification"] == "FLOOR_OR_INSTRUMENT_REPAIR"
    assert aggregate["split_counts"] == {"train": 8, "valid_seen": 4}
    assert aggregate["success_counts"] == aggregate["invalid_counts"] == {"train": 0, "valid_seen": 0}
    assert aggregate["failure_class"] is None
    totals = aggregate["resource_totals"]
    assert totals["completed_episode_count"] == 12
    assert totals["actor_call_count"] == totals["environment_step_count"] == totals["validated_model_response_count"] == 240
    assert totals["issued_tokenize_post_count"] == totals["issued_completion_post_count"] == 240
    assert totals["issued_http_post_count"] == 480
    assert totals["input_token_count"] == totals["token_preflight_token_count"] == 179468
    assert totals["output_token_count"] == 4265
    assert evidence["claim_boundary"] == {"d4": "NOT_COMPLETE", "efficacy_established": False,
                                         "g0": "NOT_PASSED", "g1": "NOT_EVALUATED",
                                         "s5_complete": True, "s6": "OPEN"}
