"""The completed public B2 v3 receipt remains bounded and content-addressed."""

from hashlib import sha256
import json
from pathlib import Path

from hswm.selfmod.contracts import canonical_sha256


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results/raw/hswm_expel_b2_text_lesson_v3_2026-09-06"
EVIDENCE = ROOT / "evidence/EVIDENCE_HSWM_EXPEL_B2_TEXT_LESSON_V3_2026-09-06.json"


def _verify_projection(receipt: dict[str, object]) -> None:
    unsigned = dict(receipt)
    actual = unsigned.pop("public_projection_sha256")
    assert actual == canonical_sha256(unsigned)


def test_v3_publication_binds_all_public_artifacts_and_complete_aggregate_audit() -> None:
    evidence = json.loads(EVIDENCE.read_bytes())
    unsigned = {key: value for key, value in evidence.items() if key != "receipt_sha256"}
    assert evidence["receipt_sha256"] == canonical_sha256(unsigned)
    for artifact in evidence["artifacts"]:
        assert sha256((ROOT / artifact["path"]).read_bytes()).hexdigest() == artifact["sha256"]

    selection = json.loads((RAW / "selection.public.json").read_bytes())
    public = json.loads((RAW / "b2.public.json").read_bytes())
    _verify_projection(selection)
    _verify_projection(public)
    assert selection["selection_identity"]["occurrence_uid"] == evidence["occurrence"]["occurrence_uid"]
    assert public["private_receipt_sha256"] == evidence["private_archive_audit"]["private_b2_serialized_sha256"]
    assert public["status"] == evidence["status"] == "EXPLORATORY_B2_COMPARATOR_COMPLETE_G0_NOT_PASSED"

    sequence = public["sequence"]
    assert sequence["splits"] == {
        "train": {"attempted": 8, "completed": 8, "scheduled": 8, "success_rate": 0.125, "successes": 1},
        "valid_seen": {"attempted": 4, "completed": 4, "scheduled": 4, "success_rate": 0.0, "successes": 0},
    }
    assert sequence["request_counts"] == {
        "action_completion": 225,
        "action_tokenize": 225,
        "reflection_completion": 1,
        "reflection_tokenize": 1,
    }
    assert sequence["usage"]["completion"] == {
        "input_tokens": {"observed_total": 193228, "unknown_request_count": 0},
        "output_tokens": {"observed_total": 3869, "unknown_request_count": 0},
    }
    assert sequence["usage"]["tokenize"]["input_tokens"] == {
        "observed_total": 193228,
        "unknown_request_count": 0,
    }

    audit = evidence["private_archive_audit"]
    assert audit["checked_outside_repository"] is True
    assert audit["archive_matches_live_wrapper"] is True
    assert audit["public_binding_matches"] is True
    assert audit["sequence_public_replayed_from_private"] is True
    assert audit["journal_hash_chain_verified"] is True
    assert audit["journal_event_count"] == 1846
    assert audit["sealed_valid_terminal_count"] == 12
    assert audit["all_episode_terminals_complete"] is True
    assert audit["successful_train_terminal_count"] == audit["reflection_count"] == audit["retained_rule_count"] == 1
    assert audit["frozen_before_valid_seen"] is True
    assert evidence["occurrence"]["request_counts"]["service_observed"] == {"tokenize": 226, "completion": 226}
    assert evidence["claim_boundary"]["b0_comparison"] is None
