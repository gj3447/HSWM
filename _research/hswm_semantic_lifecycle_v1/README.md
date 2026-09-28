# Semantic graph lifecycle diagnostic

2026-09-27. This is the first executable slice of the
[implementation architecture](../../docs/research/HSWM_IMPLEMENTABLE_ARCHITECTURE_2026-09-27.md).
It reuses the existing native semantic runtime, content-bound file journal and
graph-loop admission. No new database, model dependency or canonical-write path.

The three philosophical directions connect to specific engineering questions:

| Direction | This slice | What it does not establish |
| --- | --- | --- |
| The agent models the world across abstraction layers; M = Map | A small authored environment provides observations to a semantic state | Fidelity to a physical world, or equivalence of all abstraction layers |
| Hypergraphs as a low-cost representation of the world | A relation preserves typed subject/context/evidence/exception participation | Universal minimum cost; representation, inference and update costs still need comparison |
| AI as software; LLM as local execution, Semantic Weight as program/state | A bound observation leads to a relation revision read by a later process | CHU as a whole, real-model learning, or CR/FCL closure |

These are an implementation interpretation of the user's direction, not new
user definitions or a proof of the minimum-cost conjecture.

## Run

Use Node 24 and the existing locked TypeScript/Effect runtime (Effect 3.22.1).
Build before running, so the source and compiled modules agree. The runner
records source and compiled hashes and refuses source drift during an attempt;
this is not a reproducible-build attestation. The direct executable is the
compiled TypeScript process; `run.mjs` is only a compatibility launcher.

```sh
npm --prefix src/hswm/effect-runtime run build
node src/hswm/effect-runtime/dist/semantic-lifecycle-process.js \
  --output .hswm-local/semantic-lifecycle-new-attempt --transport scripted
```

`--output` must be new. Partial failed attempts are retained and cannot be reused.
The output directory is private (0700); request/response and configuration files
are 0600. Keep these runtime files out of public KG and Git.

`scripted` never calls a model. Its deliberately authored responder recognizes
the initial, equivalent-sham and corrected relation texts. It makes a known
behavior change available for testing persistence and controls. Its accuracy
numbers are **not evidence of LLM improvement**.

To use a real compatible serving endpoint, supply an explicit private cell file:

```json
{"base_url":"http://127.0.0.1:8001/v1","model":"served-model-id","max_tokens":512}
```

```sh
node src/hswm/effect-runtime/dist/semantic-lifecycle-process.js \
  --output .hswm-local/semantic-lifecycle-new-http-attempt \
  --transport http --cell /absolute/private/cell.json
```

An optional `api_key_env` names an existing environment variable; credential
values never belong in the file or request logs. On maintainer Mac/DGX, use the
documented `hswm-run` preflight and execution wrapper. This change does not
repair or bypass that infrastructure. No real model run is reported here.
Model ID alone is not a checkpoint/tokenizer/template pin: a confirmatory
experiment must additionally freeze those serving artifacts and its protocol.

## Execution and controls

The pure environment has 16 boolean cases, a fixed 8/4/4 train/development/heldout
split, and the authored rule `manualRelease || (pressed && power && !locked)`.
Model-visible cases contain only inputs and neutral task context. IDs, split
names and labels remain in the runner/evaluator. This is data-flow separation;
the local evaluator and scripted transport are not independent scientific observers.

1. A child process seeds one relation, predicts the training batch, obtains the
   environment's training outcomes and stages a bound outcome. The initial
   hypothesis is that pressing alone opens the door.
2. After the child exits, the native durable tree is copied into four conditions
   with `cp -a` through the existing bounded-subprocess Effect service. This
   preserves internal journal slot/object hard links; ordinary `fs.cp` does not
   preserve that contract.
3. Three separate children construct revisions through the existing graph-loop
   admission. `frozen` remains unchanged; `evidence_only` keeps all semantic fields;
   `sham` substitutes a declared equivalent sentence; `learned` uses the configured
   revision transport. The three revised conditions use the exact same training
   trace and outcome. Mechanical acceptance is not an efficacy judgment.
4. Separate new OS processes reopen each condition for development and then
   heldout prediction. Before/after canonical digests must match. The prediction
   trace, actual wire request, accepted relation key and role references must agree.

By default there is one predeclared candidate and **no development-based selection**
or feedback after development/heldout evaluation. Both phases are diagnostics;
the fixed heldout split is tiny and contains three manual-release positives
and one negative. It does not establish broad generalization or a powered W2 result.
Existing W1 census and W2 success criteria remain unchanged.

The opt-in [selected execution path](../../docs/operations/HSWM_SEMANTIC_SELECTED_EXECUTION.md)
adds `--allowance NATURAL --debit NATURAL`. It recomputes development scores
from stored prediction traces, persists the decision, freshly opens the chosen
branch and executes heldout once. The eight training/revision/development child
stages remain isolated; selected heldout uses a fresh runtime in the parent.
Bounds remain caller-declared. Invalid predictions, an uncommitted revision or
unchanged semantic fields retain the baseline. No heldout-driven reselection.

Invalid/refused evaluation batches receive null predictions for every case and
remain in the denominator. A typed failed revision is recorded and subsequent
evaluation uses the retained parent state; failures are not removed as unsuccessful
learners. Such an attempt is `COMPLETED_WITH_REVISION_FAILURES`, with
`sharedEvidence: false`; equal evidence is asserted only when all three revisions
commit with the same trace and outcome hashes. A process/setup or training-transport
failure leaves `failure.json` and no success summary.
The runner makes no automatic model retries. In the default diagnostic there are at most 10 model requests
(one training prediction, one revision, eight evaluation batches), with two
additional authored control constructions. Calls, latency, raw reported usage and
actual request/response bytes are recorded; absent usage is not zero cost.
The learned arm's model revision and the authored controls have different
construction costs. This is not an equal-compute optimizer comparison.
The selected path performs at most seven model requests: training, revision,
four development batches and one selected heldout batch. The declared budget
of ten is still an upper bound; two authored control constructions add no calls.

`SemanticOutcome.status` remains `CALLER_DECLARED_NOT_INDEPENDENTLY_VERIFIED`.
The graph-loop credit field explicitly says `NOT_ESTABLISHED`. This diagnostic
does not produce a canonical Permit, revise public KG or alter CR/FCL status.

## Files and validation

- [Pure environment](../../src/hswm/effect-runtime/src/semantic-rule-environment.ts):
  immutable cases, model view, typed evaluator errors and denominator-preserving scoring.
- `semantic-lifecycle-domain.ts`: immutable CLI, cell, arm and configuration contracts.
- `semantic-lifecycle-runtime.ts`: schema, local grants, bootstrap and existing admission adapter.
- `semantic-lifecycle-transport.ts`: separately labeled scripted/HTTP/control execution and private wire receipts.
- `semantic-lifecycle-worker.ts`: training, revision and evaluation; model input contains no evaluation labels.
- `semantic-lifecycle-runner.ts`: source pins for the compiled/source closure,
  Effect package and lockfile; sequential process lifecycle and four conditions.
- `semantic-lifecycle-process.ts` and `semantic-lifecycle-worker-process.ts`:
  parent and child executable composition roots. They supply typed POSIX filesystem
  and bounded-subprocess services; cancellation and resource cleanup follow the
  existing Effect service boundary. See the official
  [Effect resource-management documentation](https://effect.website/docs/v3/resource-management/scope).
- `run.mjs`: compatibility launcher only; it contains no lifecycle algorithm or I/O.

Focused checks after building:

```sh
npm --prefix src/hswm/effect-runtime run test -- \
  ../../../tests/effect-runtime/semantic-rule-environment.test.ts \
  ../../../tests/effect-runtime/semantic-lifecycle-domain.test.ts \
  ../../../tests/effect-runtime/semantic-lifecycle-transport.test.ts \
  ../../../tests/effect-runtime/semantic-lifecycle-runner.test.ts \
  ../../../tests/effect-runtime/canonical-atom-v2-llm-semantic-runtime.test.ts --maxWorkers=1
src/hswm/development/bin/hswm-python core pytest -q tests/test_hswm_semantic_lifecycle_runner.py
```

The end-to-end test checks actual process exits/reopening, equal bound training
evidence, unchanged evaluation state, semantic/no-semantic delta controls,
model-visible field boundaries, parse-failure denominators and overwrite refusal.
The next research step is a pinned real-model run, followed by a richer task
population and predeclared candidate search/retention evaluation. Active read and
topology revision remain later work.
