"""The B2 v1 pre-lease void is content-addressed without private archive import."""

from hashlib import sha256
import json
from pathlib import Path

from hswm.selfmod.contracts import canonical_sha256


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results/raw/hswm_expel_b2_text_lesson_v1_2026-09-06"
EVIDENCE = ROOT / "evidence/EVIDENCE_HSWM_EXPEL_B2_TEXT_LESSON_V1_2026-09-06.json"


def test_public_void_receipts_and_evidence_preserve_prelease_boundary() -> None:
    evidence = json.loads(EVIDENCE.read_bytes())
    assert evidence["status"] == "VOID_PROTOCOL_OR_EVIDENCE_BINDING_BREACH"
    unsigned = {key: value for key, value in evidence.items() if key != "receipt_sha256"}
    assert evidence["receipt_sha256"] == canonical_sha256(unsigned)
    for artifact in evidence["artifacts"]:
        assert sha256((ROOT / artifact["path"]).read_bytes()).hexdigest() == artifact["sha256"]
    public = json.loads((RAW / "b2.public.json").read_bytes())
    assert public["status"] == evidence["status"] and public["sequence"] == {}
    assert public["private_receipt_sha256"] == evidence["private_archive_verification"]["private_b2_json_serialized_sha256"]
    occurrence = evidence["occurrence"]
    assert occurrence["terminal_before_start_marker"] is True and occurrence["sequence_present"] is False
    assert occurrence["measured_model_call_count"] is None
    assert evidence["claim_boundary"]["b2_success_rate"] is None
    wrappers = {Path(row["path"]).name: json.loads((ROOT / row["path"]).read_bytes()) for row in evidence["artifacts"] if "wrapper" in row["path"]}
    assert wrappers["live-wrapper-receipt.json"]["artifact"]["sha256"] == evidence["private_archive_verification"]["live_archive_sha256"]
    assert wrappers["launcher-noop-wrapper-receipt.json"]["status"] == "success" and wrappers["launcher-noop-wrapper-receipt.json"]["exit_code"] == 0


def test_f1_row_does_not_expose_the_durable_host_name() -> None:
    row = next(line for line in (ROOT / "F1_R8_RESULTS_LOG.md").read_text().splitlines() if "B2 text-lesson v1" in line)
    assert "data-01" not in row and "data01" not in row
