# HSWM efficacy status

Last reconciled: 2026-07-20.

## Bottom line

HSWM currently has one measured positive efficacy result: on the checked-in
closed MuSiQue/2Wiki ladder, its **static additive-j retrieval field** beats the
listed cosine/BM25/PPR/RRF retrieval arms on support recall, nDCG, and
downstream answer F1. That result is useful but narrow. HSWM alone receives 100
offline LLM judgments per run, query-time traversal is certified OFF, and no
strong late-interaction or production graph-retrieval baseline was tested.

The broader claims do not pass:

| claim | current verdict | evidence boundary |
|---|---|---|
| static retrieval substrate | **measured positive, budget caveat** | 300 evaluation rows across three checked-in runs |
| cognitive uplift over direct LLM reranking | **preregistered cross-dataset claim failed** | two negative MuSiQue runs; one small, non-significant positive 2Wiki run |
| query-time graph traversal | **OFF** | `mu=0` selected on both real datasets; every tested traversal grid setting had worse hop-drop than static |
| graded supersession | **pointwise capability survives; architectural novelty retracted** | stale suppression succeeds, but an external graded revision arm is bit-exact |
| long-document advantage | **synthetic mechanism only** | no real NoCha/QASPER/NarrativeQA/book-scale result |
| EPWC + certified readout | **local conformance, not efficacy** | deterministic compiler and fail-closed admission tests |
| H3 relation composition | **not established** | B1 title-anchor result is refuted/inconclusive; B3 confirmatory efficacy is unmeasured |
| QKV-style recurrent query state | **synthetic mechanism passes; B1 real-data gate fails** | 64/64 ordered-routing teeth; K2 loses nDCG to matched K1 on both development datasets |
| S4 durable revision runtime | **absent** | no replay/WAL/concurrent publication/signature system |

Run `python verify_efficacy_claims.py --pretty` to reconstruct the selected
machine-readable headline from the checked-in JSON receipts. The command fails
closed if one of its declared metrics or claim boundaries drifts; qualitative
non-claims still require this document and the linked receipts.

## 1. Static retrieval substrate: positive within the tested ladder

The aggregate comprises 300 evaluation rows: MuSiQue seeds 7 and 13, and 2Wiki
seed 7, with 100 rows per run.

| metric | HSWM | cosine | HSWM - cosine |
|---|---:|---:|---:|
| support recall@3 | **0.7061** | 0.6697 | **+0.0364** |
| nDCG@10 | **0.8388** | 0.8129 | **+0.0259** |
| downstream answer F1 | **0.5414** | 0.4685 | **+0.0729** |
| hit@3 | 0.9733 | **0.9767** | -0.0034 |
| MRR | 0.9231 | **0.9271** | -0.0040 |

Displayed deltas above subtract the four-decimal aggregate values. Recomputing
directly from the 300 per-query F1 rows gives `+0.072834` for HSWM minus cosine.

The checked-in paired bootstrap reports `p=0.0004` for support recall@3 and
`p=0.0` at the stored precision for nDCG@10 against cosine. HSWM also leads the
listed BM25, pure-PPR, and cosine+BM25 RRF arms on support recall, nDCG, and
downstream F1. Cosine still leads hit@3 and MRR, so this is not a universal
ranking win.

### Budget and attribution caveat

- HSWM uses BGE-M3 embeddings plus 100 **offline** LLM judgment calls per run
  (300 across the three runs). The listed cosine/BM25/PPR/RRF retrieval arms use
  zero LLM calls.
- The direct reference arm uses 100 LLM rerank calls **at inference** per run;
  it is a reasoner/reference ceiling, not a like-for-like substrate.
- Current traversal certificates select `mu=0`. The positive result is therefore
  a static learned field result. It is not evidence that query-time graph
  propagation caused the lift.
- ColBERT-style late interaction, RAPTOR, HippoRAG, and another strong graph
  retriever are not in the checked-in ladder. No state-of-the-art claim is
  allowed from these results.

Sources: `substrate_bench_results.json`, `ab_p5_full_results.json`, and the three
`ab_p5_full_<dataset>_s<seed>.json` receipts.

## 2. Cognitive uplift over direct LLM: failed

The preregistered cognitive criterion required `HSWM F1 - direct-LLM F1 >=
+0.03` on every dataset and the worst seed. It did not replicate.

| dataset / seed | HSWM F1 | direct F1 | delta |
|---|---:|---:|---:|
| MuSiQue / 7 | 0.4443 | **0.7009** | **-0.2566** |
| MuSiQue / 13 | 0.4590 | **0.6907** | **-0.2317** |
| 2Wiki / 7 | **0.7208** | 0.6794 | +0.0414 |
| pooled descriptive aggregate | 0.5414 | **0.6903** | **-0.1489** |

The displayed pooled delta subtracts four-decimal aggregate values; the direct
mean of the 300 per-query F1 differences is `-0.148971`.

The positive 2Wiki delta has stored paired-bootstrap `p=0.084`; both MuSiQue
runs are materially negative. The safe statement is therefore: **HSWM improves
retrieval over the listed lightweight baselines on this ladder, but does not
establish general cognitive uplift over direct LLM reranking.**

## 3. Traversal and relational composition

### Current traversal: certified OFF

- MuSiQue certificate: `chosen_mu=0.0`.
- 2Wiki certificate: `chosen_mu=0.0`.
- In the synthetic/closed hop-drop grid, static support-recall hop-drop is
  `0.2409`; the selected traversal setting is worse at `0.3539`.
- None of the nine tested `(a, K)` traversal settings beats static hop-drop.

S3 correctly falls back to the same snapshot's static field. It must not be
described as successful graph reasoning.

### H3

The evidence-blind B1 title-anchor falsifier ends in
`H3_REFUTED_OR_INCONCLUSIVE`. H3-B3 has an implemented evidence-bound n-ary
claim builder, typed composition kernel, lifecycle gates, and preregistration,
but it has **no valid confirmatory efficacy result**.

The two checked-in `H3_B3_RUN_MANIFEST*.json` files are historical receipts and
are rejected by the current schema-v2 loader. The partial 434/3,599 development
extraction cache under `.ab_p5_cache/` predates a valid current manifest and
lifecycle OPEN receipt; it is a pilot/negative receipt, not resumable
confirmatory evidence.

This continuation repaired two PRE_RUN provenance blockers in
`h3_b3_prepare.py`:

1. multi-support gold evidence now preserves first candidate occurrence instead
   of sorting content hashes; and
2. question text now uses the same whitespace normalization as evaluator
   provenance.

Freshly generated v4 segments match source-bound evaluator provenance with zero
mismatches across MuSiQue development 200, 2Wiki development 200, MuSiQue fresh
300, and 2Wiki fresh 250 rows. These ignored local preimages prepare a new run;
they are not efficacy evidence.

A post-fix local preflight passes 9/9 gates and an exact BGE-M3 attestation has
been prepared. They are operational cache receipts, not efficacy results. The
remaining valid continuation must bind a live Qwen deployment receipt, freeze a
new schema-v2 manifest with unused first-write output paths, and run development
only. Fresh production remains forbidden unless both development certificates
pass. See `H3_B3_RESUME_STATUS_2026-07-20.md` for receipt hashes and the exact
resume sequence.

Sources: `traversal_bench_results.json`, `cert_musique_result.json`,
`cert_2wiki_result.json`, `h3_title_anchor_result.json`, and
`H3_B3_COMPOSITION_PREREG_2026-07-20.md`.

### QKV structure probe

The QKV hypothesis has now been separated from the neural-network analogy. An
exact research kernel treats the current frontier and ordered relation as Q,
the source frontier/predicate as K, and the evidenced target frontier as V.
Selected V becomes the next Q frontier. It passes 64/64 synthetic
order-collision cases; matched K1 and second-edge key/value nulls reach 0/64
depth-two terminals. This establishes a deterministic ordered-routing
mechanism, not real-data intelligence.

The stronger no-label B1 development probe uses the existing BGE query vector
as Q, paragraph vectors as K, and only exact-title-linked paragraph vectors as
V. A relation/evidence-disjoint validation half selected one K2 policy per
dataset before evaluation on the held development-test half.

| dataset | cosine nDCG / ASR | QKV K1 | QKV K2 | K2 - K1 nDCG / ASR |
|---|---:|---:|---:|---:|
| 2Wiki | .678094 / .091837 | **.763328 / .204082** | .727862 / **.214286** | **-.035466 / +.010204** |
| MuSiQue | **.585216** / .160000 | .582733 / **.210000** | .567494 / .170000 | **-.015238 / -.040000** |

2Wiki K2 beats cosine and five degree-preserving Value shuffles, but its second
layer is worse than matched K1 on nDCG. MuSiQue K2 is worse than K1 and cosine,
fails the null comparisons, and has only 0.40 full-depth apply coverage. Thus
the cross-dataset real-data gate fails. The correct current statement is:
**HSWM has a coherent evidence-bound Q/K/V routing algebra, but stacking the
available B1 reads does not establish reasoning uplift.**

Sources: `QKV_STRUCTURE_EXPERIMENT_PLAN_2026-07-20.md`,
`QKV_STRUCTURE_RESULTS_2026-07-20.md`, `qkv_routing_result.json`, and
`qkv_b1_development_result.json`.

## 4. Graded supersession: useful behavior, narrower novelty

At full dose `b=0.1`, a non-destructive supersede write reduces the maximally
confusable stale fact's top-10 presence to zero on both datasets while retaining
the old fact for audit. Dose response is something a binary hard filter cannot
express.

Two novelty claims fail:

- kill(i) fires on both datasets: supersession inside traversal adds no measured
  advantage over `kappa=0` here; and
- kill(iii) fires on both: the external separated-graded revision arm is
  bit-exact with the one-field arm, so graded behavior does not require revision
  state to live inside one field object.

Wrong writes are costly. One wrong full-dose supersede reduces primary current
recall by **12.69 points on MuSiQue** and **31.0 points on 2Wiki**. Deployment
would need durable replay, correction/compensation, and operator-visible
provenance next to the positive behavior.

Source: `STALE_POISONING_RESULTS_2026-07-19.md` and the two real-data stale
poisoning JSON receipts.

## 5. Long documents: mechanism sufficiency only

The synthetic aboutness experiment shows that, when a judge-readable aboutness
signal is explicitly preserved while a single-vector embedding dilutes, the
additive-j advantage can grow with unit length. That establishes mechanism
sufficiency in the constructed world. It does not show that real books satisfy
the premise. No real NoCha, QASPER, NarrativeQA, or book-scale run has landed.

Source: `EXPB_LONGDOC_RESULTS_2026-07-19.md`.

## 6. Compiler and certified readout: conformance, not quality

The Evidence-Preserving World Compiler and certified readout have strong local
conformance receipts:

- 40/40 valid controls admitted and matched the independent oracle;
- 400/400 scope-fault calls returned typed, payload-free pre-kernel refusals;
- 9/9 distinct mutants were refused with no payload and zero kernel calls.

These measurements establish deterministic local behavior for the tested cut.
They do not establish retrieval quality, cryptographic authenticity, exhaustive
security, crash-safe replay, or production readiness.

Source: `certified_cut_comparison_result.json` and
`EPWC_IMPLEMENTATION_S3_2026-07-20.md`.

## Verification tiers

Core source-tree verification is lightweight:

```bash
uv sync --extra dev
uv run python verify_efficacy_claims.py --pretty
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run pytest -q -p no:cacheprovider
```

The compiler, field, readout, and checked-receipt verifier require only the core
NumPy dependency. Reproducing H3 artifact production is a separate heavy tier:
2Wiki decoding needs PyArrow, BGE-M3 production needs PyTorch/Transformers plus
the frozen model snapshot, and LLM extraction needs an attested OpenAI-compatible
endpoint. A source-tree test pass is not a replacement for those runtime
receipts.

## Explicit non-claims

- no general cognitive uplift;
- no successful query-time graph reasoning on the two certified worlds;
- no real book-scale advantage;
- no H3-B3 confirmatory efficacy result;
- no real-data reasoning uplift from the current QKV-style recurrent query state;
- no state-of-the-art retrieval comparison;
- no production durability, external trust, or cryptographic certificate claim.
