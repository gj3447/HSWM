"""v2.7 mechanical counterexample probes — F5 (val-selection) + F6 (train canary).

Mechanical side of the claude-code cross-model re-audit. 10 attacks on the
NEW v2.7 surface only (F1-F4 covered by the v2.6 battery).
"""
import numpy as np
import sys

sys.path.insert(0, ".")
from learned_v3_additive import _train_score_and_gate, score_additive
from weight_field import _unit

import importlib.util
spec = importlib.util.spec_from_file_location("rcf", "receipts/receipt_cosine_floor.py")
# load only the helper, not the script main
src = open("receipts/receipt_cosine_floor.py").read()
ns = {}
exec(compile(src.split("def main(")[0], "receipts/receipt_cosine_floor.py", "exec"), ns)
_f5 = ns["_f5_selection_consistent"]

RESULTS = []


def probe(name, fn):
    try:
        ok, detail = fn()
    except Exception as e:
        ok, detail = False, f"EXCEPTION {type(e).__name__}: {e}"
    RESULTS.append((name, ok, detail))
    print(f"[{'holds' if ok else 'BREAKS'}] {name}: {detail}")


d = 16
rng = np.random.default_rng(99)
pe = _unit(rng.normal(size=(20, d)))
q = _unit(rng.normal(size=(1, d)))[0]
M = rng.normal(size=(d, d)) / np.sqrt(d)

# --- F5 attacks on the checker itself ---
good_diag = {"val_ndcg_by_lambda": {0.0: 0.7, 1.0: 0.8, 2.0: 0.75}, "val_q": [1, 2]}
good_rec = {0.0: 0.7001, 1.0: 0.8001, 2.0: 0.7501}

probe("F5-tie: exact tie between lam* and 0", lambda: (
    _f5(1.0, {"val_ndcg_by_lambda": {0.0: 0.8, 1.0: 0.8}, "val_q": []}, {0.0: 0.8, 1.0: 0.8}),
    "tie accepted as honest argmax (max includes 0)"))
probe("F5-grid-without-0 must reject", lambda: (
    not _f5(2.0, {"val_ndcg_by_lambda": {1.0: 0.8, 2.0: 0.9}, "val_q": []}, {1.0: 0.8, 2.0: 0.9}),
    "missing 0.0 -> rejected"))
probe("F5-non-argmax selection must reject", lambda: (
    not _f5(0.0, good_diag, good_rec),
    "selected 0.0 while 1.0 scores higher -> rejected"))
probe("F5-bookkeeping lie must reject", lambda: (
    not _f5(1.0, {"val_ndcg_by_lambda": {0.0: 0.7, 1.0: 0.99, 2.0: 0.75}, "val_q": []}, good_rec),
    "diag inflates lam* score vs recompute -> rejected"))
probe("F5-val-floor violated must reject", lambda: (
    not _f5(2.0, {"val_ndcg_by_lambda": {0.0: 0.9, 2.0: 0.9}, "val_q": []}, {0.0: 0.9, 2.0: 0.9 - 1e-9}),
    "val[lam*] < val[0] beyond tol -> rejected"))

# --- F6 attacks on the canary surface ---
def _resid_zero_boundary():
    pe0 = _unit(rng.normal(size=(8, d)))
    sc, gate = _train_score_and_gate(pe0, q, np.zeros((d, d)), 1.5)
    return bool((gate == 0.0).all() and np.allclose(sc, pe0 @ q)), "M=0 => resid==0 => gate==0, sc==cos"
probe("F6-resid==0 boundary: gate exactly 0", _resid_zero_boundary)

def _lam_train_zero():
    sc, gate = _train_score_and_gate(pe, q, M, 0.0)
    return bool(np.allclose(sc, _unit(pe) @ q) and (gate == 0).all()), "zero train boost degenerates exactly"
probe("F6-lam_train=0: sc==cos, gate==0", _lam_train_zero)

def _mixed_signs():
    resid = (pe @ M) @ q
    sc, gate = _train_score_and_gate(pe, q, M, 2.5)
    ok = np.allclose(sc, (_unit(pe) @ q) + 2.5 * np.maximum(0.0, resid), atol=1e-12) \
        and np.allclose(gate, 2.5 * (resid > 0), atol=1e-12)
    return bool(ok), "lam_train=2.5 exact both sides"
probe("F6-mixed signs: per-edge exactness (new seed)", _mixed_signs)

def _huge_lam():
    resid = (pe @ M) @ q
    sc, gate = _train_score_and_gate(pe, q, M, 1e6)
    ok = np.allclose(sc, (_unit(pe) @ q) + 1e6 * np.maximum(0.0, resid)) \
        and np.allclose(gate, 1e6 * (resid > 0))
    return bool(ok), "lam=1e6 exact"
probe("F6-huge lam_train scales linearly", _huge_lam)

def _nan_resid():
    sc, gate = _train_score_and_gate(pe, q, np.full((d, d), np.nan), 1.0)
    return bool((gate == 0).all() and np.isnan(sc).all()), "NaN>0 False => gate 0; NaN propagates (no silent green)"
probe("F6-NaN resid: gate=0, sc loud", _nan_resid)

holds = sum(1 for _, ok, _ in RESULTS if ok)
print(f"\n== {holds}/{len(RESULTS)} v2.7 attacks absorbed; breaks: {[n for n, ok, _ in RESULTS if not ok] or 'none'}")
