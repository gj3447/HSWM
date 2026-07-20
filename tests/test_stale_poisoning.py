"""T4 teeth: injection, actual writes, separated control, trips, kill verdicts."""
import numpy as np

import stale_poisoning as sp
import world_builder as wb
from tests.test_traversal_cert import _corpus_rows


def _world():
    w = wb.build(_corpus_rows())
    q_e = wb.hash_embed([q.question for q in w.queries], wb.DEFAULT_DIM)
    return w, q_e


def test_injection_places_stale_within_cos_tolerance():
    w, q_e = _world()
    pw = sp.inject(w, q_e, dose=0.5)
    assert len(pw.stale_of) > 0
    assert pw.cos_err <= sp.STALE_COS_TOL          # cosine-matched by construction
    for qi, eid in pw.stale_of.items():
        assert np.array_equal(pw.hg.members[eid], w.hg.members[pw.bridge_of[qi]])
        assert pw.hg.base_salience[eid] == 0.5     # the supersede write landed
    assert len(pw.write_receipts) == len(pw.stale_of)
    assert all(r.write_path == "readouts.supersede" for r in pw.write_receipts)
    assert all(r.before == 1.0 and r.after == 0.5 for r in pw.write_receipts)


def test_injection_calls_public_supersede_path(monkeypatch):
    w, q_e = _world()
    calls = []
    original = sp.readouts.supersede

    def tracked(field, edge_id, decay=0.5):
        calls.append((edge_id, decay))
        return original(field, edge_id, decay)

    monkeypatch.setattr(sp.readouts, "supersede", tracked)
    pw = sp.inject(w, q_e, dose=0.25)
    assert calls == [(eid, 0.25) for eid in pw.stale_of.values()]


def test_separated_graded_arm_is_external_and_bit_exact():
    w, q_e = _world()
    import traversal as tv
    for dose in sp.B_DOSE_GRID:
        pw = sp.inject(w, q_e, dose)
        idx = tv.build_index(pw.hg)
        qi, eid = next(iter(pw.stale_of.items()))
        a = sp.arm_scores("a", pw, q_e[qi], idx)
        e = sp.arm_scores("e", pw, q_e[qi], idx)
        assert np.array_equal(a, e)
        assert pw.revisions[0].strength == dose
        # External arm (e) does not read a later Hypergraph salience mutation.
        before_e = e.copy()
        pw.hg.base_salience[eid] *= 0.5
        assert np.array_equal(sp.arm_scores("e", pw, q_e[qi], idx), before_e)
        assert not np.array_equal(sp.arm_scores("a", pw, q_e[qi], idx), before_e)


def test_spearman_uses_tie_correct_midranks():
    # Naive argsort(argsort) spuriously gives 1.0 by breaking the y tie in input
    # order. Midranks give the correct sqrt(3)/2 and are permutation-invariant.
    expected = np.sqrt(3.0) / 2.0
    assert np.isclose(sp._spearman_midrank([1, 2, 3], [1, 1, 2]), expected)
    assert np.isclose(sp._spearman_midrank([2, 1, 3], [1, 1, 2]), expected)
    assert sp._spearman_midrank([1, 2, 3], [4, 4, 4]) == 0.0


def test_pointwise_arm_sinks_stale_monotonically_with_dose():
    """Graded supersession must express dose-response at the MECHANISM level:
    lower b ⇒ strictly lower stale score (rank movement needs a dense score
    space — the 58-edge hash fixture has gaps wider than the λ·Δlog b shift,
    so rank-based dose-response is the real-data report's job, not this test's)."""
    w, q_e = _world()
    import traversal as tv
    mean_score = {}
    for dose in sp.B_DOSE_GRID:
        pw = sp.inject(w, q_e, dose)
        idx = tv.build_index(pw.hg)
        scores = [float(sp.arm_scores("a", pw, q_e[qi], idx)[eid])
                  for qi, eid in pw.stale_of.items()]
        mean_score[dose] = float(np.mean(scores))
    assert mean_score[0.5] > mean_score[0.25] > mean_score[0.1]   # strict monotone sink


def test_filter_arm_excludes_stale_but_audits_perfectly():
    w, q_e = _world()
    pw = sp.inject(w, q_e, dose=0.1)
    import traversal as tv
    idx = tv.build_index(pw.hg)
    for qi, eid in pw.stale_of.items():
        s = sp.arm_scores("b", pw, q_e[qi], idx)
        assert s[eid] == -np.inf                   # hard-filtered from current mode
    # graded arm keeps stale REACHABLE under audit (Eilu-va-Eilu) even at max
    # dose — reachability, not top-10 (the λ·log b penalty applies to audit
    # queries too, so graded audit@10 may honestly degrade with dose)
    qi, eid = next(iter(pw.stale_of.items()))
    sa = sp.arm_scores("a", pw, pw.unit_emb[eid], idx)
    assert np.isfinite(sa[eid])
    assert sp._rank_of(sa, eid) <= pw.hg.M // 2


def test_run_produces_kill_verdicts_and_collateral():
    w, q_e = _world()
    # One held-out hop-4 query proves prereg primary and all-hop populations
    # remain distinct; all other fixture queries are hop 2.
    w.queries[-1].hop = 4
    rep = sp.run(w, q_e, "fixture", write_result=False)
    for key in ("kill_i", "kill_ii", "kill_iii", "per_dose",
                "collateral_H_T3b_current_recall_after_WRONG_supersede"):
        assert key in rep, key
    assert isinstance(rep["kill_i"]["survives"], bool)
    assert isinstance(rep["kill_iii"]["fires"], bool)
    assert rep["kill_iii"]["arm_a_vs_e_bit_exact"] is True
    assert rep["metric_population"]["n_primary_hop2_3"] == 11
    assert rep["metric_population"]["n_all_hops"] == 12
    assert rep["metric_population"]["hop_composition_all"] == {"2": 11, "4": 1}
    assert rep["kill_ii"]["n_current"] == 11
    assert rep["kill_iii"]["metrics"]["current_recall"]["n"] == 11
    assert rep["kill_iii"]["metrics"]["stale_suppression"]["n"] == 12
    assert set(rep["kill_iii"]["metrics"]) == {
        "stale_suppression", "current_recall", "historical_audit_recall",
        "dose_response",
    }
    for dose in map(str, sp.B_DOSE_GRID):
        assert rep["actual_supersede_write_receipts"]["injected_stale"][dose][
            "all_applied_exactly"] is True
        assert rep["traversal_trip_receipts"][dose]["c"]["current"]["calls"] > 0
        assert rep["arm_a_vs_e_equivalence_receipt"][dose]["current_max_abs"] == 0.0
        assert rep["per_dose"][dose]["a"]["cur"] == rep["per_dose"][dose]["a"][
            "cur_hop2_3"]
        assert "cur_all_hops" in rep["per_dose"][dose]["a"]
    assert "0.5" in rep["pointwise_current_recall_delta_vs_hard_filter"]
    assert "0.5" in rep["pointwise_current_recall_delta_vs_hard_filter_all_hops"]
    assert "collateral_H_T3b_current_recall_after_WRONG_supersede_all_hops" in rep
