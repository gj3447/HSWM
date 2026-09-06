"""Public B2 v2 failure receipt remains content-addressed and non-estimating."""

from hashlib import sha256
import json
from pathlib import Path

from hswm.selfmod.contracts import canonical_sha256


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence/EVIDENCE_HSWM_EXPEL_B2_TEXT_LESSON_V2_2026-09-06.json"


def test_v2_publication_binds_all_public_artifacts_and_preserves_unknown_usage() -> None:
    evidence = json.loads(EVIDENCE.read_bytes())
    unsigned = {key: value for key, value in evidence.items() if key != "receipt_sha256"}
    assert evidence["receipt_sha256"] == canonical_sha256(unsigned)
    for artifact in evidence["artifacts"]:
        assert sha256((ROOT / artifact["path"]).read_bytes()).hexdigest() == artifact["sha256"]
    raw = ROOT / "results/raw/hswm_expel_b2_text_lesson_v2_2026-09-06"
    public = json.loads((raw / "b2.public.json").read_bytes())
    assert public["private_receipt_sha256"] == evidence["private_archive_verification"]["private_b2_serialized_sha256"]
    assert public["status"] == evidence["status"] == "INCONCLUSIVE_MEASUREMENT_NOT_READY"
    sequence = public["sequence"]
    assert sequence["request_counts"] == {"action_completion": 0, "action_tokenize": 1, "reflection_completion": 0, "reflection_tokenize": 0}
    assert sequence["usage"]["tokenize"]["input_tokens"] == {"observed_total": 0, "unknown_request_count": 1}
    assert sequence["splits"]["train"] == {"attempted": 1, "completed": 0, "scheduled": 8, "success_rate": None, "successes": 0}
    assert sequence["splits"]["valid_seen"]["attempted"] == 0
    assert sequence["frozen_state_sha256"] is None and sequence["retained_rule_count"] == 0
    assert evidence["claim_boundary"]["performance_estimate"] is None
