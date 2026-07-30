"""Regression harness for the 2026-07-28 cross-model audit seam.

Chain seq=2 (auditor kimi-k2.5, verdict upheld) documented one non-breaking
seam: the F1/F3 gating checks evaluated `score_additive(..., lam=max(lam, 1.0))`
instead of the DEPLOYED lam, so a lam<0 selection bug would violate the F1
pointwise prose (W >= cosine) while f1_ok stayed True.

The seam is closed by LAYERED DEFENSE — either layer alone suffices, both are
pinned here so neither can silently regress:

  layer 1 (source, v2.7 by the parallel session): `score_additive` fail-closes
          on lam<0 — a negative-lam evasion raises instead of silently breaking
          the floor, so gate-level substitution of the lam argument is harmless
          (the field's domain is j>=0 by construction).
  layer 2 (gate, v2.6 by this session): if the source guard is ever removed,
          the receipt must bind the deployed lam directly (no lam=max()
          substitution) AND carry an explicit `lam >= 0` conjunct in f1_ok.

  1. static  — at least one layer must hold.
  2. dynamic — the guard raises on lam<0; the underlying floor violation
               (computed without the guarded wrapper) is real (worst < 0).
  3. e2e     — the receipt still runs green end to end (F1..F7 + oracles).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RECEIPT = ROOT / "receipts" / "receipt_cosine_floor.py"
MODULE = ROOT / "learned_v3_additive.py"

GUARD_RE = re.compile(r"if\s+lam\s*<\s*0\s*:\s*\n\s*raise\s+ValueError")
SUBST_RE = re.compile(r"score_additive\([^\n]*lam\s*=\s*max\s*\(")


def test_lam_evasion_closed_at_some_layer_statically():
    mod_src = MODULE.read_text()
    rcpt_src = RECEIPT.read_text()
    layer1_source_guard = bool(GUARD_RE.search(mod_src))
    layer2_gate_binding = (not SUBST_RE.search(rcpt_src)) and bool(
        re.search(r"f1_ok\s*=\s*\(lam >= 0\)", rcpt_src)
    )
    assert layer1_source_guard or layer2_gate_binding, (
        "lam<0 evasion open at BOTH layers: score_additive has no fail-closed "
        "guard AND the receipt neither binds the deployed lam nor conjuncts lam>=0"
    )
    # the dangerous combination is substitution WITHOUT the guard
    if SUBST_RE.search(rcpt_src):
        assert layer1_source_guard, (
            "receipt substitutes lam=max(...) but score_additive lost its lam<0 "
            "guard — the seq=2 seam is fully open again"
        )


def test_lam_negative_evasion_blocked_dynamically():
    import numpy as np
    import pytest

    import synth
    from learned_v3_additive import score_additive, train_additive_j
    from weight_field import _unit

    ds = synth.generate("semantics", seed=0, deviation=1.0, n_queries=200)
    rng = np.random.default_rng(0)
    perm = rng.permutation(ds.Q)
    train_q, test_q = perm[: int(ds.Q * 0.6)], perm[int(ds.Q * 0.6):]
    pooled = _unit(ds.hg.pooled_emb("mean"))
    M, lam, _ = train_additive_j(ds, train_q, seed=0)

    # (a) the deployed field itself is inside the locked domain
    assert lam >= 0, f"deployed lam went negative: {lam}"

    # (b) layer 1 — the source fail-closes on lam<0
    with pytest.raises(ValueError, match="lam must be >= 0"):
        score_additive(pooled[:4], ds.query_emb[int(test_q[0])], M, lam=-2.0)

    # (c) the evidence behind the audit: computed WITHOUT the guarded wrapper,
    # lam=-2 does violate the pointwise floor — the guard is not decoration
    worst = np.inf
    for q in list(test_q)[:20]:
        pool = np.arange(ds.hg.M)
        peu = _unit(pooled[pool])
        qu = ds.query_emb[int(q)] / np.linalg.norm(ds.query_emb[int(q)])
        W_manual = (peu @ qu) + (-2.0) * np.maximum(0.0, (peu @ M) @ qu)
        worst = min(worst, float((W_manual - (peu @ qu)).min()))
    assert worst < 0, "probe sanity: lam<0 must actually violate the pointwise floor"


def test_receipt_end_to_end_green():
    r = subprocess.run(
        [sys.executable, str(RECEIPT)], cwd=ROOT, capture_output=True, text=True
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "RECEIPT: VALID" in r.stdout
    # the full v2.8b/v3 gate set must actually have run (not silently skipped)
    for marker in ("F1 xlock", "F5 positive", "F6 positive", "F7 positive"):
        assert marker in r.stdout, f"gate output missing: {marker}"
