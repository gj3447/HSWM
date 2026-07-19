"""T4 teeth (offline): injection honesty, dose monotonicity, filter semantics."""
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
    rep = sp.run(w, q_e, "fixture")
    for key in ("kill_i", "kill_ii", "kill_iii", "per_dose",
                "collateral_H_T3b_current_recall_after_WRONG_supersede"):
        assert key in rep, key
    assert isinstance(rep["kill_i"]["survives"], bool)
    assert rep["kill_iii"].startswith("DEFERRED")   # honesty: (e) not built ⇒ OPEN
