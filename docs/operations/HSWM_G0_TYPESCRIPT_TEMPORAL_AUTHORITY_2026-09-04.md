# HSWM G0 TypeScript/Effect Temporal execution implementation

> **Date:** 2026-09-04
>
> **Engineering status:** `TYPESCRIPT_TEMPORAL_EXECUTION_IMPLEMENTATION_SELECTED / PYTHON_EXECUTION_ENTRYPOINTS_RETIRED / LIVE_EXTERNAL_ADMISSION_FAIL_CLOSED / COMPLETION_AUTHORITY_UNCHANGED`
>
> **Rehearsal status:** `PINNED_LOCAL_TEMPORAL_SIMULATED_OPERATOR_PASSED`
>
> **Scientific status:** `NOT_PREREGISTERED / NOT_EXECUTED / G0_NOT_PASSED / G1_LOCKED`
>
> **Claim ceiling:** a production-oriented TypeScript Temporal implementation,
> deterministic replay, and an executable non-qualifying local rehearsal only;
> not external operator qualification, real OSF/WORM/Sigstore/RFC3161/drand
> evidence, independent custody or judgment, completion-audit acceptance, G0,
> publication eligibility, Permit, causal credit, or learning.

## 1. Decision and HSWM role

The target identity does not change. HSWM remains one token-native
LLM-function macro-neural network whose evolving hypergraph is its living
harness, world model, and continuous learner. G0 orchestration is an evidence-
integrity prerequisite for the outcome-bound causal-learning loop; it is not
HSWM cognition or learning.

For any future G0 occurrence, TypeScript Temporal is now the sole selected
execution implementation, but this build is not authorized for live external
execution. The Python Temporal worker's `serve` and
`start_one_shot` entrypoints refuse execution and remain checked in only as a
historical reference and cross-language oracle. There are not two admitted
live writers.

This resolves the Python-versus-TypeScript implementation choice without
pretending that external admission is complete. Both the public start adapter
and the replayed workflow reject `LIVE_EXTERNAL_OPERATOR`; only
`SIMULATED_OPERATOR_REHEARSAL` is executable. External qualification,
authenticated signal ingress, credentials, endpoints, private holdout, real
evidence, and independent audit remain absent and outside the repository.

The existing Python integrity/completion verifier remains the completion
authority. This change moves Temporal execution, not the whole HSWM repository
or the independent Cosign completion judgment, to TypeScript.

## 2. Conceptual and implementation delta

The implementation has three deliberate layers:

| Layer | Responsibility | Explicit non-responsibility |
|---|---|---|
| dependency-free TypeScript domain | strict Python-v1-compatible descriptor wire, ordered immutable state, first-`VOID` immutability, transition timing and evidence uniqueness | networking, clocks, credentials, external facts, G0 |
| Temporal deterministic workflow | durable event history, deterministic `Date.now()`, signal handlers, FIFO queue bounded at eight, deadline, one-attempt validation activity, terminal projection | authenticating a signal sender, verifying evidence bytes, outcome truth |
| Effect runtime boundary | exact rehearsal start plan, official Client/Worker calls, typed failures, explicit Node-only package subpath | live admission, workflow determinism, secret storage, automatic publication or learning |

Effect is intentionally outside the Temporal workflow sandbox. The first live
integration attempt demonstrated that importing Effect itself into the
deterministic sandbox tries to modify a frozen JavaScript error constructor.
The accepted architecture therefore keeps the workflow domain dependency-free
and uses Effect at ingress, client, worker, and audit boundaries. This is the
functional boundary appropriate to Temporal replay, not a retreat to mutable
application control flow.

No ontology kind, canonical atom, responsibility registry, Permit path, or
learning transition is added. State and receipt objects are bounded graph
projections linked by occurrence UID and content digests.

## 3. Selected TypeScript surface

The implementation is located under `src/hswm/effect-runtime/`:

- `g0-occurrence-temporal-domain.ts`: dependency-free deterministic reducer;
- `g0-occurrence-temporal-wire.ts`: strict Effect-facing snake-case codec;
- `g0-occurrence-temporal-contract.ts`: stable workflow, signal, query, and
  authority envelope names;
- `g0-occurrence-temporal-workflow.ts`: Temporal workflow and bounded signal
  processing;
- `g0-occurrence-temporal-activities.ts`: one-attempt transition validation;
- `g0-occurrence-temporal-runtime.ts`: Effect Client/Worker adapter;
- `g0-occurrence-temporal-audit.ts`: complete normalized-history exporter and
  explicitly unsigned audit-candidate material;
- `g0-occurrence-temporal-worker-process.ts`: explicit `--preflight` or
  loopback-only `--serve-rehearsal` process entrypoint; and
- `g0-occurrence-temporal-public.ts`: explicit Node-only
  `@hswm/effect-runtime/g0-temporal` package subpath.

The package root does not export execution, signal, worker, or simulator
authority. The simulator is also absent from the Node-only selected subpath.
The subpath exports the read-only audit-candidate builder but not the local
plaintext worker runner.

### 3.1 One-shot policy

The start adapter fixes all of the following:

- workflow type `hswm_g0_occurrence_one_shot_workflow`;
- workflow ID `g0-occurrence/<occurrence_uid>`;
- closed-ID reuse policy `REJECT_DUPLICATE`;
- running-ID conflict policy `FAIL`;
- workflow maximum attempts `1`;
- validation activity maximum attempts `1` and start-to-close timeout 30
  seconds;
- no replacement round and no `signalWithStart`;
- occurrence deadline from deterministic workflow time;
- execution/run timeout equal to occurrence timeout plus 60 seconds;
- workflow-task timeout 10 seconds;
- post-start evidence accepted only as a signal; and
- FIFO pending-signal capacity eight.

The extra 60 seconds on the Temporal execution/run timeout is terminal-close
headroom only. It is not an in-workflow audit or receipt-finalization phase;
the workflow returns immediately after `SEALED` or `VOID` and marks the external
completion handshake as still required.

The TS authority closes one ambiguity in the retired Python adapter: after a
validation activity returns, the workflow checks the occurrence deadline again
before admitting the transition. A result arriving at or after the deadline becomes
`VOID/LATE`.

### 3.2 Wire and authorization boundary

The inner occurrence and transition wire remains strict snake case and retains
the Python-v1 descriptor mapping. The TypeScript authority adds a versioned
outer start envelope containing only:

- the inner descriptor-only occurrence;
- execution classification;
- operator-qualification receipt digest; and
- signal-authorization policy digest.

Each signal carries the exact policy digest in a versioned envelope. A mismatch
becomes terminal `VOID/INVALID_EVIDENCE_DESCRIPTOR`. Digest agreement is a
deterministic binding and a public bearer value in workflow history, not proof
of the sender's identity. It must never be treated as authentication. Until an
authenticated gateway binds sender, key, expiry, workflow/run ID, and signed
capability, the live classification remains fail-closed. Namespace, mTLS/API
key, service-account, and transport authorization remain an external deployment
responsibility and must be qualified independently.

## 4. Simulated external operator

Testing as an external operator is implemented in two lanes.

1. `g0-test-only-operator-simulation.ts` is a server-free deterministic
   rehearsal classified exactly as
   `TEST_ONLY_NON_QUALIFYING_NON_AUTHORIZING`. It has no endpoint, credential,
   filesystem, clock, queue, or private-material field. Its synthetic receipt
   wrappers are occurrence-bound and explicitly production-incompatible, and
   its transcript hard-codes
   external qualification, external execution, scientific evidence, G0, and
   publication claims to `false`.
2. `g0-occurrence-temporal.integration.test.ts` starts the pinned disposable
   Temporal server and drives a real TypeScript Worker and Client as
   `SIMULATED_OPERATOR_REHEARSAL`.

The live-shaped rehearsal verifies:

- an ordered happy path ending in workflow `SEALED` while remaining below G0;
- rejection of a second start with the same closed workflow ID;
- deterministic replay of the fetched Temporal history;
- signal-policy digest mismatch to terminal `VOID`;
- pre-worker signal backlog, eight-item bound, and post-seal re-entry to
  terminal `VOID`; and
- preservation of an earlier non-`SEALED` `VOID` despite signal overflow;
- rejection of a raw SDK attempt to bypass the blocked live classification;
- exact deadline-boundary handling; and
- deterministic deadline expiry to `VOID/LATE`.

The local server is disposable and uses synthetic digests. It establishes
engineering behavior only. It cannot simulate control-domain independence,
WORM retention, public timestamps, unpredictable drand output, hidden holdout,
or genuinely independent evaluators.

### 4.1 History and audit boundary

The read-only exporter accepts neither raw Temporal protobuf nor a separately
supplied terminal result. A source-pinned normalizer must provide the complete,
identity-bound event list and embed the decoded start input and completion
result into the first and last events. The exporter requires contiguous event
IDs and ordered timestamps, then compares occurrence UID, workflow ID,
classification, policy/qualification digests, and the initial evidence chain.

Its output is `hswm-temporal-terminal-audit-candidate/v1`, not the
`hswm-temporal-terminal-execution-audit-receipt/v1` accepted by completion.
Therefore local code cannot impersonate the independent auditor. Raw protobuf
normalization, external signature verification, and the final receipt remain
live-admission gates.

## 5. Official dependencies and qualification

All official Temporal packages are pinned at exactly `1.23.0` and MIT:

- `@temporalio/activity`;
- `@temporalio/client`;
- `@temporalio/common`;
- `@temporalio/worker`;
- `@temporalio/workflow`; and
- test-only `@temporalio/testing`.

Their npm integrity values, along with the official Temporal CLI `1.8.3`, embedded
Server `1.31.2`, Linux x86-64 binary SHA-256, sources, and licenses, are fixed in
`assets/g0-temporal-test-toolchain.json` and checked against the lockfile. The
CLI manifest also binds source tag commit, official release-archive checksum,
the extracted executable checksum, and license bytes. Each SDK package's
installed license bytes are checked against the shared recorded digest.
The older hash-bound
`HSWM_G0_OCCURRENCE_TOOLCHAIN_CANDIDATES.v1.json` remains the 2026-09-03
pre-cutover discovery record; it is not rewritten. A future qualified handoff
must bind this TypeScript manifest (or its independently qualified successor)
in addition to that historical record.

Temporal's official
[TypeScript SDK guide](https://docs.temporal.io/develop/typescript/) defines the
Client, Worker, Workflow, Activity, signal, and deterministic execution model.
The official
[testing guide](https://docs.temporal.io/develop/typescript/best-practices/testing-suite)
recommends integration tests while warning that a test server does not replace
a production server. The official
[SDK repository](https://github.com/temporalio/sdk-typescript) requires all
`@temporalio/*` packages in one project to use the same version.

The official SDK's schedule declaration currently fails this repository's
global `exactOptionalPropertyTypes` declaration check. The repository does not
weaken its general TypeScript policy: `skipLibCheck` is enabled only in the two
Temporal-specific tsconfigs. HSWM source remains under strict, exact-optional,
unchecked-index, unused, and Effect diagnostics.

## 6. Operator process boundary

Only non-secret coordinates are accepted by the checked-in process:

```text
HSWM_G0_TEMPORAL_ADDRESS
HSWM_G0_TEMPORAL_NAMESPACE
HSWM_G0_TEMPORAL_TASK_QUEUE
HSWM_G0_TEMPORAL_SIGNAL_AUTHORIZATION_BINDING
```

The checked-in process accepts exactly `--preflight` or `--serve-rehearsal`.
The former emits only configured booleans and never coordinate values; the
latter requires a loopback address and makes no live claim. The spelling
`--serve` is an explicit refusal. A future hosted process must receive a
separately constructed authenticated connection and verified admission
capability; authentication material must not appear in a repository input,
handoff, workflow argument, memo, search attribute, log, or test fixture.

The external release operator must still:

1. qualify the production Temporal service, SDK/binary, authorization policy,
   identity, retention, and endpoint outside the repository;
2. verify the real OSF and candidate WORM receipts before constructing the
   descriptor-only start envelope;
3. start the exact workflow once and submit later evidence only by authorized
   signal;
4. export the complete terminal history and obtain the independent completion
   audit; and
5. provide only content-addressed public receipts to the handoff.

## 7. Verification commands

```bash
cd src/hswm/effect-runtime
npm run check
npx vitest run \
  test/g0-occurrence-phase-kernel.test.ts \
  test/g0-occurrence-temporal-domain.test.ts \
  test/g0-occurrence-temporal-wire.test.ts \
  test/g0-occurrence-temporal-runtime.test.ts \
  test/g0-occurrence-temporal-audit.test.ts \
  test/g0-occurrence-temporal-worker-process.test.ts \
  test/g0-test-only-operator-simulation.test.ts \
  test/g0-temporal-toolchain.test.ts \
  test/public-api.test.ts

HSWM_G0_TEMPORAL_CLI_PATH=/qualified/path/to/temporal \
  npm run test:g0-temporal:integration

uv run --locked --extra dev pytest -q \
  tests/test_occurrence_workflow_parity_vectors.py \
  tests/test_occurrence_workflow.py \
  tests/test_occurrence_temporal_worker.py
```

At this checkpoint the focused TypeScript suite passes 48 tests and the pinned
Temporal lane passes seven tests (six active server scenarios plus its explicit
opt-in guard). Passing them cannot change the scientific status.

## 8. Remaining live-admission gates

The execution implementation is selected, but there is deliberately no live
serve/start path. Enabling one requires a new reviewed version only after an
independent external qualification supplies:

1. production server identity, namespace retention, transport authentication,
   authorization enforcement, endpoint, and disaster-recovery evidence;
2. real operator and custodian identities in separate control domains;
3. real OSF/WORM/DSSE/Rekor/RFC3161/drand/dual-evaluator descriptor lineage;
4. source-pinned raw-protobuf normalization, complete history export, and the
   exact candidate-to-`SEALED` completion handshake;
5. independently qualified Cosign verification and terminal audit receipt; and
6. an authenticated, signed signal gateway and a non-forgeable live-start
   admission capability; and
7. a production rehearsal on the qualified deployment using a non-scientific
   UID before the single scientific occurrence is armed.

Until those facts exist, the correct status remains
`NOT_PREREGISTERED / NOT_EXECUTED / G0_NOT_PASSED / G1_LOCKED`. This change is
routine engineering and creates no research-result receipt or
`F1_R8_RESULTS_LOG.md` entry.
