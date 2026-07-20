# HSWM — Evidence-Preserving World Compiler + Field Substrate

> Frozen sources and recorded observations compile deterministically into an
> immutable, evidence-addressable `WorldArtifactV1`. Stable IDs are projected
> into the existing hypergraph field/readout prototype through an explicit
> legacy layout rather than being confused with positional numpy indices.

Standalone extraction of the `semantic_weight_mapper_prototype` from the SYMPOSIUM
research programme. Numpy-only, no heavy ML deps.

## Honest status (read first)

This is an implemented compiler boundary plus a measurement prototype, not a
reasoner or a proven production runtime. What is real as of 2026-07-20:

- ✅ **S0 falsifier repair:** separated-graded arm (e), actual
  `readouts.supersede()` writes, kill(iii), write/trip receipts, and corrected
  current-recall costs are implemented with regenerated result artifacts.
- ✅ **S1 evidence compiler:** exact source selectors, content-addressed IDs,
  immutable records, deterministic manifests, and typed fail-closed rejection.
- ✅ **S2 legacy parity:** evaluation labels are separated from world inputs;
  old paragraph ordering lives only in `LegacyProjectionLayoutV1`; valid legacy
  field/retrieve/selection/μ=0 behavior remains bit-identical.
- ✅ **S3 certified cut:** immutable byte-addressed `FieldSnapshotV1` records
  bind world, dense layout, embeddings, topology, revision cut, kernel, field
  policy, and candidates. `read_certified(...)` admits only the exact certified
  tuple and otherwise returns a payload-free typed refusal before scoring.
- ✅ **Field experiments:** additive-j, traversal certification, and stale
  poisoning remain measured research paths with their checked-in receipts.
- ⚠️ **Traversal:** real MuSiQue and 2Wiki certification selected μ=0. It is
  implemented but deployment-OFF on those worlds; S3 therefore falls back to
  the same snapshot's static field instead of claiming a smart graph win.
- ❌ **S4 durable revision runtime:** event-folded supersession, as-of replay,
  compensation, concurrent publication, signatures, and external trust
  distribution are not present-tense claims.

Score-floor language is layered: the positive semantic residual is per-edge
`S_sem >= cosine`; temporal decay may intentionally go below cosine, and a
positive traversal residual does not guarantee ranking/nDCG improvement.

## Layout

| file | role |
|---|---|
| `world_ir.py` | immutable source/evidence/observation/entity/target records and stable IDs |
| `world_compiler.py` | pure `compile_world(...) -> WorldArtifactV1 | CompileRejectionV1` |
| `legacy_adapter.py` | QA-label split, two-call embed protocol, stable-ID ↔ dense-ID parity seam |
| `EPWC_IMPLEMENTATION_S0_S2_2026-07-20.md` | implemented-scope, validation, falsifier result, and S3 boundary receipt |
| `field_snapshot.py` | immutable float64 material, component receipts, and exact field hydration |
| `certified_readout.py` | certificate-bound retrieve / selection / dispatch / traversal admission |
| `certified_cut_compare.py` | independent-oracle controls, 10×40 scope checks, and 8 mutant attacks |
| `EPWC_IMPLEMENTATION_S3_2026-07-20.md` | S3 implementation and comparison receipt; smart-hypergraph boundary |
| `world_builder.py` | legacy corpus builder retained as the parity oracle |
| `hypergraph.py` | reified hypergraph (nodes+embeddings, incidence = field support) |
| `weight_field.py` | `W(e|c)` = cosine ⊕ base-salience; heuristic scorers |
| `readouts.py` | retrieve / selection distribution / dispatch / supersede prototype |
| `traversal.py` / `traversal_cert.py` | optional traversal kernel, trip receipts, empirical μ gate |
| `stale_poisoning.py` | five-arm temporal falsifier and wrong-write collateral |
| `learned_v3_additive.py` | **D1**: additive-j on frozen cosine — the cosine-floor fix |
| `llm_judgment_loop.py` | LLM-judgment weight loop (learning = judgment feedback, not SGD) |
| `falsifier.py` | prereg falsifier harness (learned vs heuristic + null-head + gates) |
| `neo4j_loader.py` / `real_run.py` | real-KG loader + link-prediction run (SECONDARY) |
| `diagnose.py` | capacity sweep + headroom knob ("why learning ≠ cosine") |
| `metrics.py` | fair-tie nDCG@k, answer-EM, paired bootstrap |
| `receipts/` | ooptdd behavior receipts (executable, source-bound, negative-oracle) |

## Run

```bash
uv sync --extra dev
uv run pytest -q
uv run python certified_cut_compare.py
uv run python learned_v3_additive.py   # D1 floor + dev1 efficacy
```

Real-KG (needs Neo4j): `uv sync --extra kg && NEO4J_URI=bolt://127.0.0.1:7687 uv run --extra kg python neo4j_loader.py`.

## Methodology

- **ooptdd** (measurement): every behavioral claim carries an executable receipt with a
  pre-run locked trace gate, real-code execution, positive readback, source binding, and an
  injected negative oracle. See `receipts/`.
- **Deployment claims:** a passing source-tree test is not a production
  certificate. S3 implements exact local scope/admission and fail-closed
  refusal, but its trusted certificate-ID allowlist is not a signature system;
  durable event replay and external trust remain S4+ work.

## License

Apache-2.0. See `LICENSE`.
