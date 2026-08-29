from pathlib import Path

from _research.dgx_q1.independent_live_verifier import VOID, verify


def test_independent_verifier_closes_missing_or_malformed_roots_to_void(tmp_path: Path) -> None:
    assert verify(tmp_path / "missing")["terminal"] == VOID
    root = tmp_path / "malformed"
    root.mkdir()
    (root / "content").mkdir()
    (root / "q1_live_ledger.jsonl").write_bytes(b"not-json\n")
    assert verify(root)["terminal"] == VOID
