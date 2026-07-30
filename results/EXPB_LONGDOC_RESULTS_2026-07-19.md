# Experiment B — length vs hop attribution (synthetic, v2) · 2026-07-19

> Files: `synth_longdoc.py` / `expB_longdoc.py` / `stats_protocol.py` (+tests, 30 pass).
> Run log: `expB_longdoc_run.log`. Adversarial review: workflow `wf_a931ba07-21a`
> (21 agents, 14 confirmed findings → v2 rebuild). Scope: **mechanism sufficiency
> in a synthetic world** — NOT a real-document result. Real-data slot (NoCha /
> NarrativeQA / QASPER) remains open.

## Question

Owner's intuition: HSWM beats cosine *more* as units get longer (paragraph→book),
because structural/judgment weights survive where mean-pooled embeddings dilute.
SR-lineage competing explanation: the delta pattern is about **multi-hop
propagation absence**, not length. The two are confounded in real benchmarks;
this experiment crosses the axes (4 length strata × hops 0/1/2, same queries
paired across length strata).

## What happened (honesty first): v1's verdict was an artifact — review caught it

v1 formalized relevance as **containment** ("unit contains topic") with gold
truncated to 3. At chapter length (k=16 of T=60 topics) containment saturates:
gold-vs-non-gold containing units become distributionally identical, the judge's
ceiling collapses with length **by construction**, and the run returned
"length trend REFUTED" (slope −0.02, p=0.999). Adversarial review (CRITICAL ×3)
showed the verdict flips with the nuisance parameter `n_topics` and that
containment is the wrong formalization of the owner's claim ("a chapter *about*
X" ≠ "a chapter that *mentions* X"). v1's refutation is therefore **withdrawn**,
not landed.

v2 premise — **aboutness latent**: each length level has exactly 3 designed
units *about* each topic (constant base rate, no saturation); fill units merely
mention topics; embedding dilution with length is preserved (verified by test).
The simulated pointwise judge reads the aboutness latent at JUDGE_ACC=0.9 and
resolves hop chains only with prob CHAIN_FOLLOW=0.35 (the documented
conditional-relevance failure). λ is **certified-selected** (λ>0 only if paired
validation improvement > 2×SE; a fixed 0.005 margin failed live — a null-world
seed certified λ=0.8 off validation noise and degraded the test split: the
winner's curse inside the harness).

## Result (5 seeds)

| | verdict | key numbers |
|---|---|---|
| **aboutness** | **BOTH** | length: slope +0.0526, p=0.0002, chapter−sentence gap **+0.169** (seed-cluster CI [0.092, 0.247]), monotone 0.354→0.483→0.503→0.523 · hop: drop 0.312 (CI [0.255, 0.373]) vs **mechanical expectation 0.314** · spread arm retains (−0.28 "drop" = rises) |
| **null** | **NO_GAIN** | certified selection sets λ=0 on all 5 seeds → every delta exactly 0; teeth cover both H1 and H2 paths |

## Interpretation (scoped)

1. **Owner's length mechanism is SUFFICIENT**: *if* long units keep a
   judge-readable aboutness signal while their single-vector embedding dilutes,
   the additive-j delta over cosine **grows monotonically with unit length**.
   That is the owner's premise stated as a mechanism, and it holds in the world
   that instantiates it. It is NOT yet evidence that real books satisfy the
   premise — that is exactly what the real-data run must measure.
2. **The hop collapse is a demonstration, not a discovery**: observed drop
   0.3117 vs (1−CHAIN_FOLLOW)·delta_h0 = 0.3137 — the collapse is the
   arithmetic echo of the injected judge chain-resolution failure. It shows the
   conditional-relevance mechanism *suffices* to produce the MuSiQue-style
   pattern; it does not adjudicate SR vs length on real data.
3. **The two axes are separable**: length trend measured at hop=0 (independent
   of CHAIN_FOLLOW); hop measured at fixed length. On real data, run the same
   cross design (Dolce/NovelHopQA-style stratification).
4. **Floor honesty, demonstrated live**: validation-selected λ is a
   winner's-curse channel unless certification is required. This is the
   in-code form of HSWM_STANDARD's "floor holds on the selection set only".

## Review scoreboard (wf_a931ba07-21a)

14 confirmed (3 CRITICAL — gold truncation/base-rate saturation; CHAIN_FOLLOW
readback; null gate H1-only + spread offset; hash(level) nondeterminism; pooled
CI independence; asymmetric H1/H2 standards; arm naming; hump profile; arity
shrink) — all addressed in v2. 4 dismissed (spread-arm oracle access:
intentional C4 control; underpower: reported not hidden; stats core: verified
correct; unit_emb stapling: acknowledged, harmless here).

## Next

- **Real-data Experiment B**: NoCha (native local/global labels) or QASPER
  (gold evidence spans) + NarrativeQA length sweep; arms must include RAPTOR /
  late-chunking (strong-baseline requirement, PROM_6 §5-B); interaction term
  `method × question_type × length` is the headline, preregistered via
  `stats_protocol` (paired permutation + cluster CI + required_n).
- **Spreading readout**: the spread arm's hop retention motivates adding an
  iterated propagation readout to the HSWM field (SYNAPSE/HippoRAG lineage) —
  the one mechanism the static additive field provably lacks.
