# HSWM SWM-0W-S2S test-only hosted process continuity implemented — next-session handoff

Date: 2026-08-23
Workspace parent: `d18adeeba9dffdf4fcb403c6c9b1f7b42b71cad9`
Primary implementation commit: `9063716116943967143dc647292533a6defa51e7`
Hosted race repair commit: `e729ef240fca3e6f961f5293b9f7667f6468b63e`
Accepted hosted occurrence: [GitHub Actions run 32654010771](https://github.com/gj3447/HSWM/actions/runs/32654010771)
Continuation KG: `ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v24.json`
Predecessor KG: `ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v23.json`
Status: `TEST_ONLY HOSTED PROCESS-CONTINUITY FEASIBILITY OBSERVED / PRODUCTION AND SCIENTIFIC PATHS UNAUTHORIZED AND UNPASSED`

## Resume capsule

The v22-selected background TypeScript/Effect root plus authenticated one-shot
IPC now exists as a package-internal, dispatch-only, non-authorizing test
probe. The second GitHub-hosted occurrence completed successfully on pinned
commit `e729ef2`: both jobs concluded `success`, three distinct scoped Effect
roots survived across their foreground steps, REGISTER and ADJUDICATE produced
real hosted uploads, CONFIRM exercised the pinned uploader's deterministic
no-files failure, and a separate READY root was explicitly cancelled by the
runner without a terminal or occurrence record.

This closes only `TEST_ONLY_S2S_HOSTED_PROCESS_CONTINUITY_FEASIBILITY_V1`.
It does not execute or authorize the production assertion shell, establish a
complete durable stage-profile commit, prove external exactly-once behavior,
freeze production workflow policy, preregister a scientific run, open future
randomness, or produce a Q/B/R verdict.

The earlier v23 T16 capsule remains package-root private. The existing scalar
`SemanticWeight` is outcome-credit/theta-like state, while the T16 object is a
recipient-conditioned forward operator. This session deliberately refused to
compose or rename them. Public export or migration stays closed until a
source-pinned raw-byte adapter can pass the authoritative Python archive parser
and the missing evolve, credit-authorizer, trajectory, provenance, rollback,
and state-ownership semantics are explicitly designed.

Use the complete `effect-ts-functional` skill before changing this slice.
Keep TypeScript `5.9.3`, Effect `3.22.1`, Node `24.13.0`, and Vitest `3.2.7`
pinned unless a separate version migration is reviewed.

## Canonical role, current evidence, and conceptual delta

HSWM remains the one token-native LLM-function macro-neural network defined by
`docs/canon/HSWM_CONSTITUTION_2026-08-20.md`. Its evolving hypergraph is one
living harness, world model, and continuous learner. TypeScript, Effect,
Python, workflows, GitHub artifacts, the repository KG, and MCPs are bounded
projections and interfaces, not HSWM cognition or learning by themselves.

### Target identity

```text
role-bearing n-ary H
  -> recipient-conditioned operator W
  -> token activation A
  -> typed LLM function cell F
  -> attributable external outcome
  -> causal credit
  -> accepted versioned delta-W/delta-H under Pi
  -> changed next activation or behavior
```

### Evidence now checked in or externally pinned

- `H`: unchanged from v23. No canonical persistent hypergraph, new relation,
  topology rewrite, or provenance edge was added.
- `W`: unchanged from v23. The fixed T16 parameter projection was neither
  trained nor composed with scalar outcome credit.
- `A`: unchanged from v23. No token-native trajectory, recurrence, or routing
  was added.
- `F`: unchanged. No LLM-executed typed semantic function cell was added.
- `Pi`: advanced narrowly. A test-only scoped Effect process root,
  authenticated READY/RECONCILE/TERMINAL protocol, strict private filesystem
  boundary, runner background/wait/cancel wiring, and hosted occurrence
  diagnostics were implemented and observed.
- outcome-bound causal-learning loop: unchanged. The uploaded ZIPs are
  structural shapes only and contain no outcome attribution, credit, accepted
  state transition, or learned next behavior.

### Conceptual delta from v23

V22 selected the process topology, and v23 inherited it while leaving IPC,
hosted-runner survival, and workflow bytes open. V24 demonstrates that the
selected topology can preserve
one local Effect root across the relevant foreground action inside a hosted
job and can cleanly observe an explicit READY cancellation. It does not bridge
that test root into the root-private production authority graph. Therefore the
production `workflow_process_continuity_resolved` flag remains false even
though `test_only_hosted_process_continuity_observed` is true.

Tests and hosted artifacts below are evidence instruments for this narrow
mechanics claim. Their success is not HSWM scientific progress beyond `Pi`.

## Implemented files and Effect ownership

```text
.github/workflows/s2s-test-only-hosted-process-continuity.yml
src/hswm/effect-runtime/src/s2s-hosted-process-continuity-contract.ts
src/hswm/effect-runtime/src/s2s-test-only-hosted-process-protocol.ts
src/hswm/effect-runtime/src/s2s-test-only-hosted-process-root.ts
src/hswm/effect-runtime/src/s2s-test-only-hosted-process-cli.ts
src/hswm/effect-runtime/test/fixtures/s2s-test-only-hosted-process-cli-entry.ts
src/hswm/effect-runtime/test/s2s-hosted-process-continuity-contract.test.ts
src/hswm/effect-runtime/test/s2s-test-only-hosted-process-protocol.test.ts
src/hswm/effect-runtime/test/s2s-test-only-hosted-process-root.test.ts
src/hswm/effect-runtime/test/s2s-test-only-hosted-process-workflow.test.ts
```

One `Effect.acquireUseRelease` scope owns each root. Connection wait remains
interruptible, while an accepted reconciliation enters one masked commit so
finalization cannot race occurrence and terminal publication. The protocol
uses a random 32-byte session token only as a local HMAC key for
domain-separated READY, RECONCILE, and TERMINAL frames. The raw token is
zeroized by clients and never uploaded or logged.

Canonical JSON is snapshotted before asynchronous use and rejects proxies,
accessors, duplicates, hostile unknown values, oversized structure, and more
than 2,048 encoded bytes. Attempt/stage/job binding is exact:
`1/REGISTER/register`, `2/CONFIRM/confirm`, and
`3/ADJUDICATE/adjudicate`. Terminal status and uploader diagnostic are
cross-validated; `unknown` never triggers an HSWM retry.

The runner and session directories are exact mode `0700`; files and the Unix
socket are exact mode `0600`; owner and device/inode identities are rechecked.
Only one exact ZIP file is exposed to each real upload action. Prepared-file
device, inode, byte length, and raw SHA-256 are rechecked after the action.
The occurrence is create-only and committed before the terminal frame; the
client independently recomputes it before reporting success.

These tests also freeze the current limits: a malformed first same-UID
connection burns its one-shot session, SIGTERM cleans a pre-terminal root, and
SIGKILL necessarily may leave inert local files. Same-UID denial of service,
mid-action mutation restored before postcheck, shared storage durability,
artifact readback authority, and external exactly-once behavior remain open.

None of the new modules is exported by `src/index.ts`.

## Timing candidate is not production policy

The additive arithmetic candidate is:

| Stage | Preparation | Upload/action | Whole assertion | Reconcile/finalize | Margin | Candidate timeout |
|---|---:|---:|---:|---:|---:|---:|
| REGISTER | 20 min | 10 min | 30 min | 10 min | 5 min | 75 min |
| CONFIRM | 190 min | 10 min | 30 min | 10 min | 5 min | 245 min |
| ADJUDICATE | 20 min | 10 min | 30 min | 10 min | 5 min | 75 min |

Each candidate is below GitHub's documented six-hour job cap, but this is only
an arithmetic feasibility object. The hosted probe deliberately used 20- and
10-minute test-only timeouts. It neither validates the candidate budgets nor
changes the existing production workflow/resource policy.

## Hosted occurrences

### Superseded failed occurrence — retained, not rewritten as success

Run [32653755145](https://github.com/gj3447/HSWM/actions/runs/32653755145)
used head `9063716116943967143dc647292533a6defa51e7`, attempt 1, event
`workflow_dispatch`, and branch `main`. The READY client did authenticate the
root, but shell `tee` opened the root-owned evidence path before the root had
created it. `pipefail` therefore failed both foreground READY steps. The run
was cancelled after diagnosis to stop the still-waiting root. Its final
conclusion is `cancelled`; continuity job `97229219015` is `cancelled`, cancel
job `97229219133` is `failure`, and it has zero artifacts.

The repair at `e729ef2` first captures the successful READY summary, then writes
it only after the root-owned evidence directory exists. A workflow regression
test requires this ordering for all four READY steps. The failed run remains an
explicit diagnostic occurrence rather than being hidden by a rerun.

### Accepted occurrence

Run [32654010771](https://github.com/gj3447/HSWM/actions/runs/32654010771)
is attempt 1, event `workflow_dispatch`, branch `main`, head
`e729ef240fca3e6f961f5293b9f7667f6468b63e`, created
`2026-08-23T17:11:03Z`. Its last job completed at
`2026-08-23T17:11:57Z`, and the run metadata was last updated at
`2026-08-23T17:11:58Z`; its overall conclusion is `success`.

- Job `97229862495`, “Three local shapes, two uploads, and diagnostics”:
  `success`.
- Job `97229862414`, “Explicit runner cancel of the scoped root”: `success`.
  Its background root step is expectedly `cancelled`; readiness, runner cancel,
  cleanup assertion, and non-completion upload all concluded `success`.
- REGISTER action outcome: `success`; terminal status:
  `RECONCILED_ACTION_SUCCESS`.
- CONFIRM pinned action outcome: expected `failure` for the intentionally
  missing path; the continued step and reconciliation concluded `success`;
  terminal status: `RECONCILED_ACTION_FAILURE`.
- ADJUDICATE real action outcome: `success`; the separately injected local
  diagnostic is `unknown`; terminal status:
  `RECONCILED_ACTION_UNKNOWN_NO_RETRY`.
- Every occurrence says `production_authority_claimed=false`,
  `production_completion_claimed=false`, `external_exactly_once_claimed=false`,
  `scientific_result_claimed=false`, and `causal_learning_claimed=false`.

## Hosted artifact metadata and immediate readback

The four accepted artifacts were downloaded and inspected during their
one-day retention window. GitHub's artifact-level digests and metadata are:

| Artifact ID | Name | API size | GitHub digest | Expires |
|---:|---|---:|---|---|
| 9496963517 | `hswm-test-only-pc-32654010771-occurrence-evidence` | 14,004 | `sha256:814afae4c1fb85bdb3bf0d08204d206c303439c77be00969aca41ed3eb51019c` | `2026-08-24T17:11:55Z` |
| 9496963147 | `hswm-test-only-pc-32654010771-adjudicate-a3` | 1,117 | `sha256:9daf389973a27cf4e51c26f84b2352c687e1967ad4190389bb151db18ac65abf` | `2026-08-24T17:11:54Z` |
| 9496962072 | `hswm-test-only-pc-32654010771-register-a1` | 639 | `sha256:d1eca6139a43a24d5aef2d276bed3c0b30b297adb440dfd49aee6a6d32b7c5ac` | `2026-08-24T17:11:49Z` |
| 9496957226 | `hswm-test-only-pc-32654010771-cancel-observation` | 357 | `sha256:6b8c7170cae68b140cd4c8817de8733e94ed3509f994b7934cc7b7fd4e624513` | `2026-08-24T17:11:28Z` |

Immediate readback established:

- all 13 hosted evidence JSON files parse strictly;
- no downloaded path or text contains `client.token`, `raw token`, or
  `secret`;
- the cancel artifact contains only the authenticated READY client summary and
  contains no terminal or occurrence;
- the REGISTER inner ZIP SHA-256 is
  `2d1faaeb6ee046e25f548c3d5f750364aa37e46f95445c2e5a7da1bf1d91a53e`
  and contains exactly `control_receipt.json`;
- the ADJUDICATE inner ZIP SHA-256 is
  `1645e61bcc4849bd85231fc75a3c2b5ffa432c5b43d60489903c3a18a8cf9d7a`
  and contains exactly `control_receipt.json` and
  `numeric_adjudication.json`;
- each occurrence's prepared-archive hash matches the downloaded corresponding
  inner ZIP where a real hosted upload exists;
- each occurrence's READY and TERMINAL hashes match the downloaded raw frame
  files.

The CONFIRM candidate ZIP existed only inside its private hosted runner root.
The uploader was intentionally pointed at a distinct missing path, so no
CONFIRM artifact was created and no hosted-upload success is claimed for that
candidate.

Downloaded artifact bytes remain ephemeral inspection material and are not
checked into the repository. The repository KG records the GitHub metadata and
the independently observed inner hashes; after expiry, the checked-in record is
not a substitute for artifact availability or production provenance.

## Verification

- `npm run verify`: TypeScript check PASS; 34 Vitest files and 415 tests PASS;
  build PASS; package dry-run PASS.
- hosted workflow self-check: the four focused files passed before the hosted
  process observations.
- independent lifecycle review: no unresolved blocker after socket-lifetime,
  filesystem-phase, and canonical pre-encoding budget repairs.
- independent protocol/security review: no unresolved blocker for binding,
  terminal invariants, hostile unknown values, occurrence ordering, or exact
  ZIP paths.
- independent workflow/claim review: no unresolved syntax or claim-boundary
  blocker before dispatch.
- `git diff --check`: PASS.
- protected unrelated paths remained uncommitted.

This is routine engineering evidence. It creates no material scientific result
and requires no `F1_R8_RESULTS_LOG.md` entry or research-result receipt.

## Exact next-session entrypoint

1. Read the constitution, Occam core, S2S gate, v23, this handoff, v24 KG, and
   the complete `effect-ts-functional` skill.
2. Preserve the unrelated dirty files
   `src/hswm/experiments/continual_live.py` and
   `tests/test_hswm_continual_live.py`.
3. Treat the scalar-credit/T16 composition as explicitly refused, not pending
   implicit implementation. Do not export the T16 modules or add an optimizer.
4. Treat the accepted hosted run as test-only mechanics evidence. Do not wire
   it into `S2SArtifactEvidence`, a production completion bearer,
   preregistration, or event 10.
5. The next claim-critical gate is
   `SWM0W_S2S_PRE_FREEZE_RESOURCE_POLICY_REVIEW_V1`: review the disclosed
   timing/convergence evidence and accept, revise, or reject the 75/245/75
   amendment candidate without opening a future seed or mutating a production
   workflow by default.
6. Only after that review may a separately source-pinned preregistration freeze
   the task generator, arm budgets, epsilon/reduction order, bootstrap rule,
   Q/B/R thresholds, intervention order, image, and timeout.
7. Keep production assertion authority, complete stage-profile durability,
   artifact readback authority, exactly-once semantics, preregistration,
   future randomness, confirmatory dispatch, event 10, and all scientific
   verdicts closed until their own evidence gates pass.

The essential scientific promotion path remains exactly:

```text
LCB(mean Q_t) >= 0.80
LCB(mean B_t) >= 0.10
LCB(mean R_t) >= 0.10
```

No remote KG connector publication was attempted; the requested continuation
record is the repository-local v24 KG. The repeated personal stop-hook
`Bad for loop variable` message was treated as external telemetry. No personal
hook file, retired governance loop, or canonical-write MCP path was modified.
