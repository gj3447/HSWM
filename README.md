# HSWM — Hypergraph Semantic Weight Map

> A hypergraph knowledge-graph weight field where **retrieval, plan, and non-destructive
> supersession are readouts of one shared field**, `W(e|c) = cosine(α) + λ_b·log(b) + λ_j·j`,
> with a **construction-guaranteed cosine floor** (never worse than cosine) and an
> **LLM-judgment loop** as the weight-adjustment mechanism.

Standalone extraction of the `semantic_weight_mapper_prototype` from the SYMPOSIUM
research programme. Numpy-only, no heavy ML deps.

## Honest status (read first)

This is a **design draft + measurement harness**, not a proven system. What is real:

- ✅ **Substrate + readouts** (incidence, pooling, retrieve/plan/dispatch, non-destructive
  supersede) — implemented, 17 tests.
- ✅ **Cosine floor (D1)** — `additive-j` design (`W = cosine + λ·ReLU(residual)`, λ chosen on
  validation incl. 0) provably never underperforms cosine; on real KG λ→0, synthetic dev1 gain +0.116.
- ⚠️ **LLM-judgment "learning"** — the weight adjustment is done by an LLM's judgment feedback
  loop, **not SGD**. Current judge is a *simulated oracle* (mechanism only).
- ❌ **System efficacy — UNMEASURED.** The matched-budget A/B vs `direct-LLM-rerank` on
  downstream answer EM/F1 has **not been run**. Honest prior: **operational-not-cognitive**
  (the field is a *geometry cache of LLM judgment*, so by the data-processing inequality its
  cognitive ceiling is ≤ direct-LLM). Do **not** cite the directional-judge probe (0.872 vs
  0.5) as HSWM efficacy — that measures the *LLM ingredient*, not the field (attribution error).

Full canon: SYMPOSIUM `THEORY/재배맨/HSWM_STANDARD.md`, `WHY_NO_COGNITIVE_UPLIFT_2026-07-19.md`.

## Layout

| file | role |
|---|---|
| `hypergraph.py` | reified hypergraph (nodes+embeddings, incidence = field support) |
| `weight_field.py` | `W(e|c)` = cosine ⊕ base-salience; heuristic scorers |
| `readouts.py` | retrieve / plan·dispatch / supersede (one shared field) |
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
uv run pytest -q          # 17 passed
uv run python learned_v3_additive.py   # D1 floor + dev1 efficacy
```

Real-KG (needs Neo4j): `uv sync --extra kg && NEO4J_URI=bolt://127.0.0.1:7687 uv run --extra kg python neo4j_loader.py`.

## Methodology

- **ooptdd** (measurement): every behavioral claim carries an executable receipt with a
  pre-run locked trace gate, real-code execution, positive readback, source binding, and an
  injected negative oracle. See `receipts/`.
- **OMD** (parallel-agent coordination): **deliberately NOT applied.** OMD coordinates *N agents
  in parallel on one repo*; HSWM is a single-track prototype, so OMD adds only its orphan-server /
  stale-lock fragility with no benefit. Re-introduce only if parallel-agent development starts.

## License

Apache-2.0. See `LICENSE`.
