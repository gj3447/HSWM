# HSWM — Hypergraph Semantic Weight Map

**A research program for turning hand-written AI coordination into a persistent,
learnable semantic field.** LLMs execute local functions; HSWM is the larger
recurrent network that connects them, remembers outcomes, and is intended to
change its own routing and topology through experience.

> **Research status:** HSWM is not yet that complete system. This repository
> contains a tested world/evidence substrate, deterministic field and runtime
> components, narrow measured results, and several failed or unfinished
> plasticity experiments. No checked-in run has yet produced a
> `CAUSALLY_VALIDATED` outcome → credit → durable `ΔW/ΔH` → changed-behavior
> result.

<p align="center">
  <img src="https://raw.githubusercontent.com/gj3447/HSWM/main/docs/assets/hswm-semantic-weight-field-hero.png"
       alt="A translucent semantic-weight landscape with one amber activation trajectory"
       width="100%">
</p>

<p align="center"><em>Conceptual illustration of a living semantic-weight field—not an architecture diagram or experimental result.</em></p>

> **Target intuition:** an input activates a trajectory through the field. An
> independently measured outcome may validate a bounded durable update. Only an
> activated update conditions later behavior.

## Why HSWM

Modern agent systems commonly coordinate models, tools, memories, and roles with
prompt rules, routers, workflow graphs, and exception handling. As their number
of combinations grows, the coordination layer can consume more effort and model
context than the task itself.

### The transformer-training analogy

HSWM starts from an analogy, not an equivalence. Rule-heavy AI systems shifted
toward transformer networks whose behavior is shaped by data instead of an
enumerated rulebook. HSWM applies that move one level above the foundation
model: it is intended to turn AI token, action, tool-use, and outcome
trajectories into the implicit coordination of a larger multi-agent neural
system.

| transformer training | HSWM macro-training |
|---|---|
| training data | token/action/tool/outcome trajectories |
| learned parameters | durable `W`, routing policy, and `H` topology |
| objective and optimizer | external outcome, eligibility, causal credit, and bounded update |
| forward pass | recurrent activation across LLM function cells |
| held-out validation | fresh/equal-budget evaluation and removal ablation |

The distinction matters: placing tokens in a transformer's context window does
not train it. Likewise, pouring tokens into HSWM supplies candidate training
observations, not learned rules by itself. The goal is not to write the
“perfect AI rulebook”; it is to learn an increasingly capable behavioral field
whose durable parameters change future behavior. In the intended sense, this
is the pursuit of the most capable AI behavior-rule system that experience can
teach—not a claim that the current HSWM is already perfect. A learning claim
becomes valid only when an outcome-bound update survives fresh tests and its
effect disappears when the update is removed.

This repository calls that hypothesized failure mode **LX3 Ragnarok**: stronger
models spend an increasing share of their reasoning budget interpreting and
obeying a growing static harness. HSWM's research bet is that successful and
failed trajectories can instead supply evidence for bounded semantic-weight,
routing, and connectivity candidates; only independently validated candidates
become persistent. This is a direction under test, not a demonstrated
uniqueness or production claim.

HSWM does not try to remove every deterministic rule. Authority, types,
transactions, provenance, budgets, rollback, and safety constraints remain a
thin execution boundary. The part intended to become learned is the cognitive
wiring: which functions should activate, communicate, and change together.

The preserved user direction and its evidence boundary are recorded in
[`USER_PRIMARY_HSWM_TOKEN_LEARNING_RAGNAROK_2026-08-14.md`](USER_PRIMARY_HSWM_TOKEN_LEARNING_RAGNAROK_2026-08-14.md).

## One field, four coupled views

The target state is:

```math
\mathrm{HSWM}_t = (H_t, W_t, A_t, \{f_i^t\}),
\qquad
f_i^t = \mathrm{LLM}(\rho_i, x_i^t, a_{\mathcal N(i)}^t)
```

| view | role |
|---|---|
| `H` | mutable hypergraph topology: the n-ary relations that determine what can interact |
| `W` | durable slow semantic coupling plus run-local fast/query potential; fast activation alone is not learning |
| `A` | volatile current activation; persistence belongs to durable `H/W` and certified snapshots |
| `f_i` | a local semantic function executed by an LLM under a typed port/role contract |

`A`: recurrent run-local activation and working state. It is deliberately
volatile; durable `H/W` and certified snapshots carry persistence across runs.

These are coupled views, not four rigid floors. An HSWM may contain and compose
smaller HSWMs through the same ports and connectors; the architecture is meant
to remain open and self-similar rather than acquire a new fixed layer for every
new capability. See the
[`open self-similar kernel`](docs/canon/SPEC_OPEN_SELF_SIMILAR_HSWM_2026-07-22.md).

Foundation-model parameters are the **micro-weights inside** each `f_i`. HSWM's
`W` and `H` are **macro-weights and connectivity between** those functions. The
target is therefore not “an LLM plus an external memory” or a conventional
multi-agent wrapper: the whole persistent function field is the neural system.

One foundation model may execute many logical cells. Cell identity comes from
role, ports, local state, position, and authority—not from requiring a separate
model checkpoint per cell.

The hero image compresses the idea into one continuous field disturbed by a
single activation trajectory. It is deliberately a mental image, not a
one-to-one rendering of discrete hypergraph incidence or a learning claim.

## What counts as learning

Putting more tokens in a database is memory. Reinjecting them is retrieval.
Editing a prompt rule is a useful baseline. HSWM counts a trajectory as learned
only when it closes a causal loop:

```text
token / action / tool trajectory
  → sealed run-local activation
  → external outcome
  → eligibility and causal credit
  → bounded ΔW / routing / ΔH candidate
  → fresh, retention, and canary evaluation
  → atomic activation in a new durable snapshot
  → changed future behavior
  → removal ablation that removes the effect
```

The executable receipt contract
[`token_learning_contract.py`](src/hswm/learning/token_learning_contract.py)
distinguishes `OBSERVED_ONLY`, `DURABLE_UPDATE`, and `CAUSALLY_VALIDATED`, and
hash-binds a claimed causal-test receipt. The replay, equal-budget, and removal
tests named by that receipt remain a separate evidence boundary; the current
contract does not inspect their scientific contents.

## Topology and sheaf: core versus research lens

Topology is central in the concrete sense of mutable hypergraph connectivity:
HSWM must eventually learn not only bond strength but also which relations and
coalitions should exist. This does not require importing all of topological
geometry into the runtime.

Sheaf theory is an optional research lens for heterogeneous local states. A
stalk can model a cell's local state space, a restriction map can model transport
through a typed port, and seam residuals can expose where local outputs fail to
fit together. In HSWM, that residual should begin as an **observation feature**,
not a hard-coded truth test, forced consensus rule, or efficacy claim:

```text
local states → port transports → seam residuals
             → observation tokens → outcome-bound H/W/routing learning
```

The definitions, sources, caveats, and machine-readable ontology are in
[`ontology/field/sheaf/README.md`](ontology/field/sheaf/README.md)
and [`ontology/field/sheaf/HSWM_SHEAF_ONTOLOGY.v1.json`](ontology/field/sheaf/HSWM_SHEAF_ONTOLOGY.v1.json).

## Current evidence boundary

Repository state as of 2026-08-16:

| area | honest status |
|---|---|
| evidence-preserving world compiler, stable IDs, immutable cuts, and fail-closed readout | implemented and locally tested |
| static additive semantic field | narrow positive checked-in retrieval measurement with an asymmetric budget: 100 offline LLM judgments for HSWM and zero for cosine/BM25/PPR/RRF; not continual learning |
| scalar slow-weight P1 | **scientific RED**: 12 staged candidates, 0 fresh-gate passes/activations, and 0/456 measured top-10 rank changes |
| typed-policy P1v3/P1v4 | narrow local `n=6` L0 observation; not durable `ΔW`, transfer, or topology learning |
| token-driven durable macro-learning | trajectory/eligibility/activation receipt binding implemented; no optimizer or causally validated macro-update demonstrated |
| cross-agent transfer, learned topology, and consolidation | incomplete or unmeasured |

Tests establish implementation and invariant closure, not intelligence or
production readiness. Numerical claims, negative results, budgets, and exact
reproduction boundaries live in [`EFFICACY.md`](EFFICACY.md).

## Quick start

Requirements: Python 3.11+ and [`uv`](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/gj3447/HSWM.git
cd HSWM
uv sync --locked --extra dev
uv run --locked --extra dev pytest -q
uv run --locked hswm-verify-efficacy --pretty
```

The default suite uses checked-in fixtures and does not require a live model,
Neo4j, or an external benchmark corpus. GPU/LLM experiments and real-KG runs are
a separate, explicitly configured boundary; source-tree tests do not substitute
for their runtime receipts. `hswm-verify-efficacy` validates checkout-bound
evidence; when invoked from an installed wheel outside that checkout, pass
`--root /path/to/HSWM` explicitly.

## Read next

| question | document |
|---|---|
| How do the fragmented identity, mathematics, runtime, learning, and evidence meanings fit together? | [`HSWM unified meaning map`](docs/research/HSWM_UNIFIED_MEANING_MAP_2026-08-16.md) |
| Why replace static agent glue, and what is token learning? | [`USER_PRIMARY_HSWM_TOKEN_LEARNING_RAGNAROK_2026-08-14.md`](USER_PRIMARY_HSWM_TOKEN_LEARNING_RAGNAROK_2026-08-14.md) |
| What exactly are `H`, `W`, `A`, and the LLM functions? | [`HSWM_LLM_FUNCTION_NETWORK_ARCHITECTURE_AND_FEASIBILITY_2026-07-23.md`](docs/canon/HSWM_LLM_FUNCTION_NETWORK_ARCHITECTURE_AND_FEASIBILITY_2026-07-23.md) |
| What is implemented, rejected, or still open? | [`EFFICACY.md`](EFFICACY.md) |
| What is the broader world-memory purpose? | [`THE_WORLD_REMEMBERS.md`](THE_WORLD_REMEMBERS.md) |
| Where is the full research chronology? | [`INDEX.md`](INDEX.md) |
| How is the whole repository organized by meaning? | [`ontology/`](ontology/) |
| How might sheaf theory help without becoming another static harness? | [`ontology/field/sheaf/`](ontology/field/sheaf/) |

## Repository map

| path | purpose |
|---|---|
| `ontology/` | canonical semantic navigation, path catalog, and concept relations |
| `src/hswm/` | canonical package surface, organized by semantic responsibility |
| `src/hswm/cells/` | cellular kernel, durable store, model ports, and bounded live probe |
| `src/hswm/prototypes/` | bounded early learning and synthetic-world prototypes |
| `src/hswm/substrate/` | canonical hypergraph, document/world construction, immutable field cuts, certified readout, and convergence substrate |
| `src/hswm/learning/` | token-learning contracts and learning diagnostics |
| `src/hswm/evaluation/`, `_research/` | falsification code and source-only experiment programs |
| `world_ir.py`, `world_compiler.py` | immutable evidence model and deterministic world compilation |
| `src/hswm/substrate/doc_builder.py`, `src/hswm/substrate/world_builder.py` | deterministic document and corpus hypergraph construction |
| `src/hswm/substrate/field_snapshot.py`, `src/hswm/substrate/certified_readout.py` | certified field cuts and exact-scope admission |
| `hswm_weight_store.py`, `src/hswm/learning/token_learning_contract.py` | durable weight state and causal-learning evidence boundary |
| `prom_search_hswm/` | open composition, field algebra, retrieval, routing, and plasticity experiments |
| `tests/`, `_research/shared_field_hypothesis/` | core regression and fail-closed research contracts |
| `research/`, `schemas/`, `scripts/` | machine-readable contracts, schemas, and validators |
| `evidence/`, `prereg/`, `manifests/`, `results/`, `receipts/` | typed research artifacts and direct measurements |
| `docs/research/`, `docs/assets/` | narrative research material and public visual assets |

The root Python count is now **73**, down from 148. The remaining files are an
explicit compatibility surface: 63 are byte-bound by checked-in SHA evidence and
10 belong to replay clusters that still share current root-relative topology.
There are no unexplained review candidates. The exact disjoint partition is
machine-readable in
[`PYTHON_ROOT_CLASSIFICATION.v1.json`](ontology/history/PYTHON_ROOT_CLASSIFICATION.v1.json);
new Python implementation may not enter the root compatibility inventory.

Every checked-in path is projected into the machine-readable
[`repository ontology`](ontology/HSWM_REPOSITORY_ONTOLOGY.v1.json) and
[`path catalog`](ontology/HSWM_PATH_CATALOG.v1.json). Historical modules and
hash-bound artifacts remain at the repository root only where old receipts,
imports, or `__file__`-relative execution bind that location. The frozen
exceptions are explicit in
[`LEGACY_ROOT_PATHS.v1.json`](ontology/history/LEGACY_ROOT_PATHS.v1.json).
Completed Python moves are source-pinned in
[`PYTHON_ROOT_MIGRATIONS.v1.json`](ontology/history/PYTHON_ROOT_MIGRATIONS.v1.json)
and
[`PYTHON_ROOT_MIGRATIONS.W2.v2.json`](ontology/history/PYTHON_ROOT_MIGRATIONS.W2.v2.json),
with later replay-backed waves in
[`PYTHON_ROOT_MIGRATIONS.W3.v2.json`](ontology/history/PYTHON_ROOT_MIGRATIONS.W3.v2.json),
[`PYTHON_ROOT_MIGRATIONS.W4.v2.json`](ontology/history/PYTHON_ROOT_MIGRATIONS.W4.v2.json),
[`PYTHON_ROOT_MIGRATIONS.W5.v2.json`](ontology/history/PYTHON_ROOT_MIGRATIONS.W5.v2.json),
[`PYTHON_ROOT_MIGRATIONS.W6.v2.json`](ontology/history/PYTHON_ROOT_MIGRATIONS.W6.v2.json),
[`PYTHON_ROOT_MIGRATIONS.W7.v2.json`](ontology/history/PYTHON_ROOT_MIGRATIONS.W7.v2.json),
[`PYTHON_ROOT_MIGRATIONS.W8.v2.json`](ontology/history/PYTHON_ROOT_MIGRATIONS.W8.v2.json),
and
[`PYTHON_ROOT_MIGRATIONS.W9.v2.json`](ontology/history/PYTHON_ROOT_MIGRATIONS.W9.v2.json).
The first non-Python cleanup wave is source-pinned in
[`ROOT_ASSET_MIGRATIONS.W10.v1.json`](ontology/history/ROOT_ASSET_MIGRATIONS.W10.v1.json):
58 root documents, records, logs, and one maintenance shell entry now live in
typed directories while their original layout remains replayable.
**New Python modules or research artifacts must not be added to the root.** New
code goes under `src/hswm/`; artifacts are routed by kind according to
[`docs/research/ARTIFACT_LAYOUT.md`](docs/research/ARTIFACT_LAYOUT.md).

Old commands are reproduced in their original root layout without restoring
those files into the active checkout:

```bash
uv run hswm-legacy-replay verify f3_agent_ab_transfer_r3.py
uv run hswm-legacy-replay materialize \
  f3_agent_ab_transfer_r3.py /tmp/hswm-f3-r3-replay
cd /tmp/hswm-f3-r3-replay
uv run python f3_agent_ab_transfer_r3.py --smoke
```

The materializer creates a clean detached standalone clone at the manifest's
exact source commit, verifies every bound source SHA-256, and writes its receipt
inside `.git/`; it never writes an old path into this working tree. Git-tracked
code and paths are reproduced exactly. External datasets, model services, and
ignored caches remain separate evidence dependencies and are not invented by
the materializer.

## Method and contribution boundary

The maintainer research workflow is intentionally short:

```text
implement or run → measure directly → emit one receipt for a material result
                 → commit and push
```

Current claims rely only on checked-in direct measurements and reproducible
tests. The active bounded policy is
[`research/HSWM_MINIMAL_GOVERNANCE.v1.json`](research/HSWM_MINIMAL_GOVERNANCE.v1.json).

Contributions are welcome through [`CONTRIBUTING.md`](CONTRIBUTING.md) and require
the contributor agreement in [`CLA.md`](CLA.md).

## License

Dual-licensed under AGPL-3.0-or-later or a separate commercial license. See
[`LICENSING.md`](LICENSING.md) and [`LICENSE`](LICENSE).
