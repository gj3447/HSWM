# HSWM — Evidence-Preserving World Compiler and Neural-Substrate Research

> Frozen sources and recorded observations compile deterministically into an
> immutable, evidence-addressable `WorldArtifactV1`. Stable IDs are projected
> into the existing hypergraph field/readout prototype through an explicit
> legacy layout rather than being confused with positional numpy indices.

Standalone extraction of the `semantic_weight_mapper_prototype` from the SYMPOSIUM
research programme. The compiler/field/readout core is NumPy-only; reproducing
H3 artifact production is a separately attested GPU/LLM workflow.

The repository-wide research map, including the 2026-07-22 open self-similar
composition work and the 2026-07-23 learned-router result, is in
[`INDEX.md`](INDEX.md).

## Target architecture and present boundary

**HSWM means Hypergraph Semantic Weight Map.** Its target form is a giant
hypergraph-based semantic neural network whose neural functional units are
executed by LLMs:

\[
f_i^t := \operatorname{LLM}(\rho_i, x_i^t, a_{\mathcal N(i)}^t),
\qquad
\mathrm{HSWM}_t := (H_t, W_t, A_t, \{f_i^t\})
\]

- `H`: the hypergraph topology that binds semantic states and functions through
  n-ary relations;
- `W`: the Semantic Weight Map that controls macro-synaptic strength, activation,
  and routing between those functions;
- `f_i`: an LLM-executed semantic function (an agent/process role), not a
  conventional scalar neuron;
- `A`: recurrent activation and persistent state carried by the whole HSWM.

The same foundation model may realize many `f_i` calls; the claim does not
require one separately trained LLM per function. LLM parameter weights remain
inside the function implementation, while HSWM weights describe the semantic
connections *between* functions and states. The whole hypergraph-weighted
function network is HSWM. It is not “an LLM plus an external memory”.

HSWM therefore owns the persistent hypergraph state, global routing, recurrence,
credit assignment, acceptance, and weight/topology rewrites. CAS, CRDT, replay,
and validation reducers form its deterministic safety/control plane; they are
not being mislabeled as LLM neurons.

The detailed function contract, runtime cycle, code-to-architecture map,
feasibility verdict, failure modes, and decisive P1–P4 experiments are in
[`HSWM_LLM_FUNCTION_NETWORK_ARCHITECTURE_AND_FEASIBILITY_2026-07-23.md`](HSWM_LLM_FUNCTION_NETWORK_ARCHITECTURE_AND_FEASIBILITY_2026-07-23.md).

That paragraph is a target identity, not a present-tense efficacy claim. The
repository currently has a mature evidence/compiler/replay substrate and several
measured field mechanisms. The P1 engineering loop is now closed, but its first
causal efficacy trial was rejected:

| phase | repository state | completion gate |
|---|---|---|
| P0 — identity and metrics | **specified** in the [canonical direction](CANON_DIRECTION_NEURAL_COGNITIVE_ENTITY_2026-07-23.md): neural functions are LLM-executed; `H` and `W` form their macro-network | target identity, claim boundary, and learning metric are explicit |
| P1 — closed weight-learning loop | **implemented and measured RED** ([result](P1_CLOSED_LEARNING_LOOP_RESULTS_2026-07-23.md), [evidence](EVIDENCE_P1_CLOSED_LEARNING_LOOP_2026-07-23.json)): 12/12 candidates had fresh Δ=0 and were rejected; A1−A2=0 | per prereg K1, stop this slow-weight route and test the typed text-lesson fallback |
| P2 — shared-network transfer | **not implemented or measured** | Agent A writes; frozen Agent B gains on sealed unseen work under equal compute |
| P3 — structural plasticity | deterministic edits and a shadow gate exist; the first candidate policy was **rejected** | a learned candidate policy passes fresh, target, and canary gates |
| P4 — federation and sleep | field federation is partial; consolidation/homeostasis remain design work | recover in-field interference and demonstrate stable long-horizon learning |

### Checked-in experiment ledger (2026-07-23)

These results constrain the next implementation; none establishes a general
intelligence or production claim.

| experiment | measured result | disposition |
|---|---|---|
| B2.1 frozen-arm learned router | all 54 standard cells collapsed to `ABSTAIN→MERGED`; primary Δ=0 | **rejected**; router-only action space is insufficient |
| [B2 routing-signal audit](B2_ROUTING_SIGNAL_RESULTS_2026-07-23.md) | best MuSiQue slice oracle gap +9.92pp, 75% ties; pooled retrieval slices exceed the 80% tie kill line | a thin, concentrated oracle signal exists; this is not a learned-router success |
| [E1 conditional traversal](E1_CONDITIONAL_TRAVERSAL_RESULTS_2026-07-23.md) | bridge −13.89pp, CI95 [−19.44, −8.33]; factoid −7.27pp | **rejected**; traversal remains deployment-OFF |
| [shadow-gated topology absorption](SHADOW_GATED_ABSORPTION_RESULTS_2026-07-23.md) | 0/3 rounds accepted, 100% canary preservation, sealed Δ=0 | **rejected for no target gain**; the gate was safe, the candidate generator was ineffective |
| cognitive-uplift reranking | pooled F1 Δ=−0.1489 | **rejected** |
| [P1 eligibility/judgment learning](P1_CLOSED_LEARNING_LOOP_RESULTS_2026-07-23.md) | loop/runtime implemented; 12 candidates proposed, 0 fresh-gate passes, A1−A2=0, slope −0.0271 | **rejected for no behavioral movement**; canary/CAS safety held, ExpeL-style typed lesson is the preregistered fallback |

The [Phasor Agents prior-art tribunal](TRIBUNAL_PHASOR_AGENTS_PRIOR_ART_2026-07-23.md)
also narrows novelty: generic graph three-factor plasticity and sleep-staged
learning are adopted prior art, not HSWM claims. The remaining research slots
are n-ary credit assignment, semantic LLM-operator verdicts, topology
plasticity, and a persistent multi-agent field with provenance/CRDT receipts.

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
- 🧪 **B2.2 Gate-0 metrology:** the full-candidate component-pack compiler,
  exact neutral replay, frozen-B2 reproduction, pinned B2.1 continuity,
  three-role acceptance lock, and detached learner view are implemented with
  fail-closed synthetic/attack tests. The real 2Wiki/MuSiQue packs have not been
  built; no learner has been fitted and no B2.2 efficacy claim has been
  registered or made.
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
- 🧰 **Generic feedback runtime:** a capability-separated, SQLite-backed
  `ATTACH → PROPOSE → OBSERVE → JUDGE → COMMIT → DISPATCH` kernel now provides
  canonical replay, request conflict refusal, verdict-bound cuts, and restart
  recovery. It is an operational mechanism, not a live outer dispatcher,
  LakatoTree dependency, scientific verdict, or external exactly-once claim.

These engineering mechanisms do not establish that the HSWM function network is intelligent or already learns continually; its plasticity loop is not yet closed. That stronger claim still requires a
preregistered frozen-model comparison of no memory, transcript/vector memory,
dynamic KG/event-log memory, full HSWM, and causal-rewrite ablation under equal
compute, held-out behavior, rejection controls, forgetting bounds, and receipt
replay.

See [`EFFICACY.md`](EFFICACY.md) for the full claim ledger, budgets, negative
results, and reproduction boundaries. `verify_efficacy_claims.py` reconstructs
the selected numeric headline directly from checked-in JSON receipts and fails
closed when one of those declared metrics or boundaries drifts.

Score-floor language is layered: the positive semantic residual is per-edge
`S_sem >= cosine`; temporal decay may intentionally go below cosine, and a
positive traversal residual does not guarantee ranking/nDCG improvement.

## Falsifiable shared-field hypothesis

The next discriminating question is narrower than “a new Hypergraph RAG”: can one
versioned semantic field serve retrieval, independent selection, and knowledge
revision better than three task-specific heads under the same measured budget?
The current repository implements shared scoring only. `plan()` remains a
compatibility alias, `supersede()` receives an externally chosen write, and a
separated revision-metadata arm can reproduce the graded scores bit-exactly.

The repository-local [shared-field research nest](_research/shared_field_hypothesis/)
now contains independent selection and versioned-revision fixtures plus an E1
replay, isolation, inventory, and budget verifier. It binds the canonical A/B/C/D
roles, requires exact A/B parity, keeps C/D as explicitly different controls,
and refuses missing shared immutable components or replay-counter drift. The
retrieval fixture, executable model arms, frozen confirmatory inputs, numeric
thresholds, and G4 preregistration remain unresolved; therefore no efficacy run
is authorized. No winner, production, closed-learning, or novelty claim follows
from these engineering receipts. The longer user direction and SECONDARY_AI
formalization remain in
[`SPEC_SHARED_HYPERGRAPH_NN_SEMANTIC_WEIGHT_2026-07-22.md`](SPEC_SHARED_HYPERGRAPH_NN_SEMANTIC_WEIGHT_2026-07-22.md).

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
| `CANON_DIRECTION_NEURAL_COGNITIVE_ENTITY_2026-07-23.md` | target identity: a hypergraph Semantic Weight Map whose neural functions are executed by LLMs |
| `HSWM_LLM_FUNCTION_NETWORK_ARCHITECTURE_AND_FEASIBILITY_2026-07-23.md` | precise LLM-function contract, runtime semantics, current code mapping, feasibility verdict, risks, and decisive gates |
| `PREREG_P1_CLOSED_LEARNING_LOOP_2026-07-23.json` / `P1_CLOSED_LEARNING_LOOP_RESULTS_2026-07-23.md` / `EVIDENCE_P1_CLOSED_LEARNING_LOOP_2026-07-23.json` | frozen P1 contract, implementation/result closeout, and measured RED receipt |
| `B2_ROUTING_SIGNAL_RESULTS_2026-07-23.md` / `b2_routing_signal.py` | oracle routing-signal audit and deterministic evidence generator |
| `E1_CONDITIONAL_TRAVERSAL_RESULTS_2026-07-23.md` / `e1_conditional_traversal.py` | bridge/factoid traversal falsifier and evidence generator |
| `SHADOW_GATED_ABSORPTION_RESULTS_2026-07-23.md` / `prom_search_hswm/hswm_shadow_gate.py` | topology-candidate shadow-gate result, reducer, preregistration, and receipt |
| `GENERIC_FEEDBACK_RUNTIME_ACCEPTANCE.md` / `feedback_runtime.py` / `feedback_store.py` | generic authority-separated feedback kernel, durable replay, and explicit non-claims |
| `INDEX.md` | public research map, 2026-07-22 result ledger, and next frontier |
| `SPEC_OPEN_SELF_SIMILAR_HSWM_2026-07-22.md` | fixed-layer-free open weighted-hypergraph contract |
| `AMENDMENT_OPEN_HSWM_KERNEL_V2_2026-07-22.md` | v2r3 counterexamples, repairs, tests, and claim boundary |
| `prom_search_hswm/hswm_open_kernel.py` | deterministic open-composition v2r3 kernel |
| `prom_search_hswm/prom_b21_learned_router.py` | B2.1 frozen-arm learned router and conformal-abstention harness |
| `prom_search_hswm/docs/B21_LEARNED_ROUTER_RESULTS_2026-07-23.md` | 54-cell result, oracle ceiling diagnosis, LakatoTree disposition, and B2.2 direction |
| `prom_search_hswm/hswm_bond_readout.py` | pure slow-salience + volatile query-bond potential application and deterministic ranking |
| `prom_search_hswm/docs/B22_QUERY_BOND_WEIGHTING_DESIGN_2026-07-23.md` | refined B2.2 design, action-space diagnostics, full-score-pack requirement, and fresh confirmation boundary |
| `prom_search_hswm/hswm_b22_gate0_harness.py` / `prom_search_hswm/docs/B22_GATE0_HARNESS_CONTRACT_20260723.md` | full-candidate Gate-0 compiler, replay, locked acceptance, and trusted-ingestion boundary |
| `_research/shared_field_hypothesis/task_contracts.v1.json` / `e1_contract.v1.json` | independent task/control roles and engineering-only replay/budget receipt contracts |
| `prom_search_hswm/docs/PROM_HSWM_REMAINING_ISSUES_RESOLUTION_20260723.md` | evidence-backed dependency graph from implemented gates to G4 preregistration |
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

## Verification tiers

Tier 1 is the fresh-clone/CI boundary. The default pytest command collects the
core suite, the PROM research suite, and the shared-field contract suite. Its
only PROM data dependency is the tracked, content-addressed Badiou structure
fixture.

```bash
uv sync --extra dev
uv run --extra dev pytest -q
uv run python verify_efficacy_claims.py --pretty
```

Tier 2 is deterministic extended verification over checked-in artifacts:

```bash
uv run python certified_cut_compare.py
uv run python semantic_layer_falsifier.py --pretty
uv run python b2_routing_signal.py
uv run python e1_conditional_traversal.py
```

Tiers 1 and 2 need the core NumPy dependency plus the pytest development extra;
they need no model endpoint, Neo4j, or untracked benchmark corpus. Tier 3 is the
external/live research boundary: ignored benchmark inputs, the real-KG
additive-j experiment, H3 model snapshots, GPU/LLM execution, and their runtime
receipts. The real-KG entrypoint is:
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

Dual-licensed under AGPL-3.0-or-later or a separate commercial license. See
[`LICENSING.md`](LICENSING.md) and `LICENSE`.
