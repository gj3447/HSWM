# HSWM — Endogenous Hypergraph Agent + Evidence-Preserving World Compiler

> HSWM's research target is not an agent with a graph attached. The agent's
> computation, action, memory, and learning should occur as activation and
> evidence-bearing rewrite of one evolving semantic hypergraph. Frozen sources
> and recorded observations compile deterministically into an immutable,
> evidence-addressable `WorldArtifactV1`; accepted experience changes the world
> model through explicit, replayable transitions rather than hidden mutable
> state.

Standalone extraction of the `semantic_weight_mapper_prototype` from the SYMPOSIUM
research programme. The compiler/field/readout core is NumPy-only; reproducing
H3 artifact production is a separately attested GPU/LLM workflow.

The repository-wide research map, including the 2026-07-22 open self-similar
composition work and the 2026-07-23 learned-router result, is in
[`INDEX.md`](INDEX.md).

## Research thesis: the agent is the evolving hypergraph

HSWM is not intended to be a conventional knowledge graph used by an otherwise
external agent, nor a GraphRAG pipeline with successively attached retrievers,
routers, memories, and planners. Its hard-core hypothesis is that those roles
can be different read/write views of one shared computational state:

$$
H_t = (V_t, E_t, W_t, A_t, \Pi_t)
$$

$$
z_t = \operatorname{activate}(H_t, o_t), \qquad
a_t = \operatorname{act}(z_t), \qquad
H_{t+1} = \operatorname{rewrite}(H_t, a_t, e_t)
$$

Here `V` and n-ary `E` are the current semantic structure, `W` is durable
semantic binding strength, `A` is volatile activation, `Π` is provenance, `o`
is an observation, and `e` is the evidence that permits a state transition.
Retrieval is activation over `H`; planning is constrained propagation and
coalition formation over `H`; an accepted action is a typed rewrite of `H`;
and later cognition runs on the resulting `H`, not on an unrelated side log.

A mathematical calculation is one instance of this execution model: operands,
operators, intermediate values, constraints, and result dependencies form an
activated hypergraph trajectory. Tool use, planning, and evidence revision
should use the same transition semantics. Recording a completed calculation in
a graph after an external system performed it does not satisfy this thesis; the
causally relevant computation must occur through, and leave an attributable
change in, the shared substrate.

In this view HSWM builds a **world model** rather than merely storing text. The
model contains entities and evidence, but also alternatives, relations,
affordances, revision history, and the observed consequences of action. An
agent is therefore not only a process that traverses the graph: its persistent
computational identity is expressed by the graph's evolving structure, field,
and causally attributable rewrite history.

This becomes **continual learning** only under a falsifiable boundary. With the
base LLM/model frozen, durable hypergraph changes must improve or appropriately
alter future behavior, transfer across tasks or agents, and control destructive
forgetting. Appending conversation records is persistent memory, not by itself
a learning result. A decisive HSWM experiment is therefore: Agent A acts and
writes evidence-bearing rewrites; Agent B receives no parameter update, reads
the same field, and exhibits measured zero-shot transfer that disappears under
the registered topology/weight/rewrite ablations.

### Wolfram-inspired computational commitments

HSWM takes the following ideas seriously as design commitments, without
claiming equivalence to the Wolfram Physics Project or treating the analogy as
evidence:

- **Local hypergraph rewriting:** small typed rules produce state evolution;
  global organization should emerge from their composition rather than from a
  growing catalogue of orchestration exceptions.
- **Multiway-system evolution:** unresolved but admissible alternatives may
  branch, later merge, conflict, or be superseded instead of being silently
  collapsed into one irreversible narrative.
- **Causal history:** rewrite events form an evidence-addressed causal graph so
  a readout can be replayed, challenged, compensated, or refused at an exact
  revision cut.
- **Observer-relative readout:** a query, agent, or typed port exposes a bounded
  view of the same underlying world; it must not fabricate a second hidden
  world to answer conveniently.
- **Causal invariance as a test:** regrouping, composition,
  separation/recomposition, and alternative valid rewrite orderings require
  explicit invariance or divergence tests. They are not assumed from an
  attractive diagram.
- **Computational irreducibility as the default:** a plausible endpoint or
  cached summary does not replace executing the causally relevant transition
  path. An optimization must demonstrate observational equivalence at the
  certified readout boundary.

### One substrate, few laws

The architectural standard is transformer-like economy: a small set of
composable primitives with broad consequences, not a feature pile whose parts
communicate through accidental glue. Atomic and composed HSWMs therefore share
one state type and flat normal form. The same topology, semantic field, typed
ports, connectors, activation, and rewrite vocabulary must account for
retrieval, dispatch, planning, revision, specialization, separation, and
multi-agent transfer wherever the evidence permits it.

An LLM may propose, interpret, or judge a transition, but accepted persistent
state must be materialized in `H` with provenance. A new subsystem must justify
why it cannot be expressed as activation, readout, composition, or typed
rewrite of that shared substrate. Elegance here is an engineering and
scientific constraint: fewer independent mechanisms mean stronger ablations,
clearer causal attribution, and more opportunities for one learned structure
to transfer across behaviors.

### Storage is replaceable; the hypergraph semantics are not

Neo4j is currently an experiment/adapter tier, not the definition of HSWM. A
property graph may reify an n-ary hyperedge as nodes and relationships, but the
database layout must not dictate the mathematical ontology. The required
backend capabilities are native or faithfully encoded n-ary relations, typed
ports and connectors, atomic versioned rewrites, branch/merge or equivalent
multiway history, content-addressed provenance, exact snapshot/replay, and
efficient durable-weight plus volatile-activation access.

If the Neo4j representation makes those laws ambiguous, lossy, or
operationally dominant, HSWM should benchmark and adopt a hypergraph-native or
purpose-built event/field store. Backend migration is justified by semantic
fidelity and measured execution behavior, not novelty alone.

The present repository implements only pieces of this thesis. The compiler,
certified cut, field experiments, and open composition kernel are scaffolding;
they do not yet constitute an autonomous continual learner or prove that HSWM
has achieved world-model learning. The result ledger below deliberately keeps
that distinction visible.

## Honest status (read first)

This is an implemented compiler boundary plus a measurement prototype, not a
reasoner or a proven production runtime. What is real as of 2026-07-23:

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
- ✅ **Open self-similar composition kernel:** fixed layer numbers were removed
  from the composition contract. Atomic and composed HSWMs share one
  mount/typed-port/n-ary-connector type; v2r3 passes the 78-test expanded
  structural regression and two injected-negative checks.
- ❌ **B2.1 learned router:** a preregistered shared-ridge/conformal router over
  frozen A/B/MERGED arms failed all 54 standard cells and reduced to
  `ABSTAIN→MERGED` everywhere. Primary delta was 0 on both datasets; even the
  posthoc gold oracle's minimum frozen-action headroom was only +0.01087, below
  the registered >+0.02 target. This rejects router-only, not semantic-weight or
  topology learning.
- 🧪 **B2.2 bond-weight groundwork:** the manifest's previously inert slow
  `SemanticWeight` and a separate volatile query-bond potential now have a pure,
  fail-closed combination kernel with 19 conformance tests; the B2/OpenHSWM
  adapter and full score pack remain next. A development-only
  top-20 oracle has +0.0489/+0.0833 room, while one conservative static sparse
  edge-ID patch transfers exactly 0 on all six calibration/test cells. No B2.2
  efficacy claim has been registered or made.
- ⚠️ **Open-kernel claim boundary:** LakatoTree judged the composition receipt
  chain `partial` and `certified=false`. Learned semantic-weight deltas and
  CONNECT/SEPARATE/SPECIALIZE topology edits, bounded cyclic readout,
  multi-agent transfer, and retrieval uplift remain unimplemented or unmeasured.
- ✅ **Measured efficacy:** the static additive-j field beats the listed cosine,
  BM25, PPR, and RRF arms on support recall@3, nDCG@10, and downstream F1 in the
  checked-in 300-row ladder. HSWM alone uses 100 offline LLM judgments per run.
- ⚠️ **Traversal:** real MuSiQue and 2Wiki certification selected μ=0. It is
  implemented but deployment-OFF on those worlds; S3 therefore falls back to
  the same snapshot's static field instead of claiming a smart graph win.
- ❌ **Cognitive uplift:** the preregistered cross-dataset claim over direct LLM
  reranking failed (MuSiQue deltas −0.2566/−0.2317; 2Wiki +0.0414,
  paired-bootstrap p=0.084; pooled delta −0.1489).
- ⚠️ **H3:** B1 title-anchor composition is refuted/inconclusive. B3 is
  implemented and preregistered but confirmatory efficacy is unmeasured; the
  checked-in run manifests are historical and rejected by the current loader.
- ⚠️ **QKV / semantic layers:** exact ordered routing passes 64/64 and the
  heterogeneous typed branch/map/reduce/lookup kernel passes 128/128 synthetic
  namespace cases over four templates. The no-label B1 recurrence gate still
  fails. A 132/132 2Wiki comparison result uses evaluator-supplied facts/path
  and is executor coverage, not HSWM reasoning efficacy.
- ❌ **S4 durable revision runtime:** event-folded supersession, as-of replay,
  compensation, concurrent publication, signatures, and external trust
  distribution are not present-tense claims.

See [`EFFICACY.md`](EFFICACY.md) for the full claim ledger, budgets, negative
results, and reproduction boundaries. `verify_efficacy_claims.py` reconstructs
the selected numeric headline directly from checked-in JSON receipts and fails
closed when one of those declared metrics or boundaries drifts.

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
| `certified_cut_compare.py` | independent-oracle controls, 10×40 scope checks, and 9 mutant attacks |
| `EPWC_IMPLEMENTATION_S3_2026-07-20.md` | S3 implementation and comparison receipt; smart-hypergraph boundary |
| `EFFICACY.md` / `verify_efficacy_claims.py` | human and machine-readable current efficacy ledger |
| `INDEX.md` | public research map, 2026-07-22 result ledger, and next frontier |
| `SPEC_OPEN_SELF_SIMILAR_HSWM_2026-07-22.md` | fixed-layer-free open weighted-hypergraph contract |
| `AMENDMENT_OPEN_HSWM_KERNEL_V2_2026-07-22.md` | v2r3 counterexamples, repairs, tests, and claim boundary |
| `prom_search_hswm/hswm_open_kernel.py` | deterministic open-composition v2r3 kernel |
| `prom_search_hswm/prom_b21_learned_router.py` | B2.1 frozen-arm learned router and conformal-abstention harness |
| `prom_search_hswm/docs/B21_LEARNED_ROUTER_RESULTS_2026-07-23.md` | 54-cell result, oracle ceiling diagnosis, LakatoTree disposition, and B2.2 direction |
| `prom_search_hswm/hswm_bond_readout.py` | pure slow-salience + volatile query-bond potential application and deterministic ranking |
| `prom_search_hswm/docs/B22_QUERY_BOND_WEIGHTING_DESIGN_2026-07-23.md` | refined B2.2 design, action-space diagnostics, full-score-pack requirement, and fresh confirmation boundary |
| `H3_B3_RESUME_STATUS_2026-07-20.md` | corrected PRE_RUN boundary, local receipt hashes, and exact next sequence |
| `QKV_STRUCTURE_EXPERIMENT_PLAN_2026-07-20.md` / `QKV_STRUCTURE_RESULTS_2026-07-20.md` | ordered-routing and B1-QKV development protocol, results, and claim boundary |
| `qkv_routing.py` / `qkv_b1_probe.py` | exact symbolic QKV routing and no-label dense B1 value-read research kernels |
| `SEMANTIC_QKV_EXPERIMENT_PLAN_2026-07-20.md` / `SEMANTIC_QKV_RESULTS_2026-07-20.md` | heterogeneous typed-layer protocol, synthetic result, 2Wiki oracle boundary, and next decisive test |
| `semantic_layer_routing.py` / `semantic_layer_falsifier.py` | common evidence-bound branch/map/reduce/lookup kernel and its exhaustive four-template matrix |
| `semantic_2wiki_oracle.py` | evaluator-supplied-memory development executor; explicitly not the common kernel or efficacy |
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
uv run python verify_efficacy_claims.py --pretty
uv run pytest -q
uv run python certified_cut_compare.py
uv run python semantic_layer_falsifier.py --pretty
```

The commands above need the core NumPy dependency plus the pytest development
extra; they need no model endpoint. The real-KG additive-j experiment is a
separate cache/Neo4j tier:
`uv run --extra kg python learned_v3_additive.py`. H3 production additionally needs
PyArrow for 2Wiki decoding, PyTorch/Transformers plus the frozen BGE-M3
snapshot, and an attested OpenAI-compatible LLM endpoint; source-tree tests do
not substitute for those runtime receipts.

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
