from pathlib import Path

import e1_conditional_traversal as e1


def test_e1_artifact_paths_are_repository_relative():
    repo = Path(e1.__file__).resolve().parent

    assert e1.INPUT == repo / "traversal_bench_results.json"
    assert e1.OUT_JSON == repo / "EVIDENCE_E1_CONDITIONAL_TRAVERSAL_2026-07-23.json"


# --- v2.4.3 oracle strengthening (vacuity 0/8: the module emits the numbers the
# REJECTED E1 claim rests on — subset boundaries, delta sign/scale, exclusion
# counts — but only the artifact paths were asserted) ---

def test_e1_golden_values_reproduce_checked_in_evidence(tmp_path, monkeypatch):
    """Regenerated analysis must reproduce the checked-in evidence bit-closely.

    Kills: split inversion (cmp@70), exclusion-count corruption (binop@78),
    bridge/factoid boundary and inversion mutants (cmp@82/83), delta sign/scale
    corruption (binop@94 x2, binop@99) — all of which silently change the
    published bridge/factoid deltas the TRAVERSAL_OFF verdict stands on.
    """
    import json

    import pytest

    repo = Path(e1.__file__).resolve().parent
    monkeypatch.setattr(e1, "OUT_JSON", tmp_path / "out.json")
    e1.main()
    out = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    ev = json.loads((repo / "EVIDENCE_E1_CONDITIONAL_TRAVERSAL_2026-07-23.json").read_text(encoding="utf-8"))

    for subset in ("bridge", "factoid"):
        got, want = out["results"][subset], ev["results"][subset]
        assert got["n"] == want["n"], subset
        assert got["delta_best_trav_minus_static_pp"] == pytest.approx(
            want["delta_best_trav_minus_static_pp"], abs=1e-6), subset
        assert got["ci95_pp"] == pytest.approx(want["ci95_pp"], abs=1e-6), subset
        assert got["per_arm_delta_vs_static_pp"]["hswm_traversal"]["delta_pp"] == pytest.approx(
            want["per_arm_delta_vs_static_pp"]["hswm_traversal"]["delta_pp"], abs=1e-6), subset

    assert out["join_coverage"]["n_excluded_no_hop"] == ev["join_coverage"]["n_excluded_no_hop"]
    assert out["join_coverage"]["n_test_with_hop"] == ev["join_coverage"]["n_test_with_hop"]
    assert out["prereg_verdict"]["prereg_call"] == ev["prereg_verdict"]["prereg_call"]
