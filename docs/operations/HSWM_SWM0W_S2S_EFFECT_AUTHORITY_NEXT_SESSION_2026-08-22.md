# HSWM SWM-0W-S2S TypeScript/Effect authority handoff

Date: 2026-08-22

Code checkpoint: `4da46051f697fada418f52c681834e5d4ea91fdc`

Checkpoint parent: `e8cf3ee80c76f2fc57f804b64f38e8bdefd58580`

Authority: the TypeScript/Effect direction is `USER_PRIMARY`; the concrete
provenance, capability, and continuation design is `SECONDARY_AI_PROPOSED`.

Status: `BLOCKED_PRE_PREREG / STRUCTURAL_1_6_9_CLEAR /
REQUEST_PROVENANCE_CLEAR / REGISTRATION_B_CAPABILITY_CLEAR /
CURRENT_RUN_AUTHORITY_OPEN / SCIENTIFIC_UNJUDGED`.

This document supersedes the earlier 2026-08-22 adapter handoff only as the
continuation entrypoint. It does not rewrite that historical checkpoint or its
v2 KG projection. The companion
[`HSWM_SWM0W_S2S_EFFECT_HANDOFF.v3.json`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v3.json)
is a local repository projection, not HSWM cognition, a remote KG publication,
a preregistration, or a scientific result.

## Canonical role and conceptual delta

HSWM remains the one token-native LLM-function macro-neural network defined by
[`HSWM_CONSTITUTION_2026-08-20.md`](../canon/HSWM_CONSTITUTION_2026-08-20.md).
The evolving hypergraph remains simultaneously living harness, world model,
and continuous learner; GitHub, repository ontology, and Effect services are
bounded evidence interfaces rather than substitute cognition.

This checkpoint strengthens only `Π`:

- `H`: no new hypergraph cognition or substrate evidence;
- `W`: no learned semantic-weight result;
- `A`: no activation/readout efficacy result;
- `F`: no valid confirmatory candidate or adjudication execution;
- `Π`: GitHub calls are now request-distinct and source/preregistration
  validation retains runtime-authentic authority through registration commit B.

The outcome-bound causal-learning loop did not advance. Event counts remain
structurally valid only through `1 -> 6 -> 9`; no trusted path appends event 10,
exposes a verdict, changes learned `W`, or authorizes a future measurement.

## Runtime direction remains fixed

- TypeScript-first, strict TypeScript `5.9.3`, Effect `3.22.1`, Node `24.13.0`.
- Effect v3 `Schema`, `Context.Tag`, `Layer`, typed `Data.TaggedError`, immutable
  snapshots, and explicit environment requirements remain the runtime idiom.
- TypeScript owns chronology, authority, external observation, control
  receipts, and eventual evidence-envelope composition.
- Python owns deterministic numerical generation, fit/replay/evaluation, and
  canonical candidate/adjudication bytes. TypeScript hashes those bytes without
  parsing and reserializing the numerical receipt tree.
- Privileged live adapters and capability issuers remain absent from the
  package root export.

## What code checkpoint `4da4605` establishes

### Request-distinct GitHub receipts v2

`s2s-live-github.ts` now captures and validates the response provenance that
the previous checkpoint discarded.

- Every accepted metadata observation requires a bounded
  `X-GitHub-Request-Id`, exact `X-GitHub-Api-Version-Selected: 2022-11-28`, and
  a bounded opaque `ETag`.
- Observation receipts bind all three values in their v2 self-hash. Two reads
  of the same endpoint, body, projection, ETag, and integer second remain
  distinct when GitHub issued distinct request IDs.
- The artifact-download v2 receipt separately binds the API 302 status,
  request ID, selected version, optional redirect ETag, signed-object 200
  status, normalized media type, optional object ETag, redirect URL hash, and
  exact archive bytes.
- Missing, malformed, accessor-backed, hidden-extra, overlong, version-drifted,
  and hash-tampered provenance fails closed with typed errors.
- `s2s-live-artifact.ts` no longer treats receipt-hash inequality alone as
  proof of independent calls. Issuance, absence polling, metadata requery,
  download, and readback brackets reject any reused GitHub request ID,
  including receipts made distinct only by changing the local timestamp.

The exact metadata endpoints were checked read-only against GitHub and carried
the pinned selected-version header, distinct request IDs, and ETags. ETag is a
protocol-level fail-closed availability choice for these exact endpoints, not a
claim that every GitHub REST endpoint universally supplies one. The design
basis is GitHub's [REST response-header documentation](https://docs.github.com/en/rest/using-the-rest-api/getting-started-with-the-rest-api),
[conditional-request guidance](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api),
and [artifact 302 contract](https://docs.github.com/en/rest/actions/artifacts).

### Operational policy and event contract v4

The GitHub receipt schema upgrade is reflected coherently in
`s2s-confirmatory.ts`, rather than allowing the adapter and lifecycle binding
to disagree. The operational policy and event schema are v4. The canonical
resource-policy SHA is now:

`b2c631ff80922800d06ac7e31c0632e02e1b560a31759cd0d11ae0a39c374351`

`s2s-preregistration.ts` pins the same value. No preregistration document has
been created, so this pre-registration upgrade does not rewrite committed
measurement evidence.

### Runtime-authentic registration-B capability

`validateS2SRegistrationCommitB` no longer degrades a verified preregistration
lineage back into a caller-usable commit-SHA string. After validating raw
parentage, the add-only diff, exact path bytes, and the exact Git tree entry, it
returns a module-issued `S2SRegistrationCommitAuthority`.

- The token is authenticated by a module-private `WeakMap`; a TypeScript cast,
  copied brand, plain object, or hostile Proxy cannot mint one.
- Its immutable evidence binds source A, registration B, preregistration
  self-hash and raw-file hash, registration core, source-freeze and manifest
  hashes, resource policy, registration time, committed future round, and
  future-round commitment.
- The evidence is itself canonical and self-hashed as
  `hswm-swm0w-s2s-registration-commit-authority-evidence/v1`.
- B must contain exactly one `100644 blob` at the preregistration path.
  Executable blobs, symlinks, and gitlinks are rejected before authority
  issuance even if other visible bytes or diff status appear acceptable.
- The capability is process-local and intentionally non-serializable. Each
  isolated GitHub job must revalidate durable bytes and mint fresh local
  authority; serializing a brand is never an authority transfer.

This closes the source/preregistration lineage only through B. It does not yet
authenticate a workflow invocation, dispatch, run ID, head SHA, or stage role.

## Exact source anchors

| path | SHA-256 | role |
|---|---|---|
| `src/hswm/effect-runtime/src/s2s-confirmatory.ts` | `37461b7d8f6e3a8c73f2fe1aee7342441e564697669bbaf87e97e11a22d5ad0f` | policy/event v4 and receipt v2 pins |
| `src/hswm/effect-runtime/src/s2s-preregistration.ts` | `2c1ef25b00c11bbcd486830e6fd4daac28ffc9c152e6c50d3a3653a343b90f89` | registration-B capability boundary |
| `src/hswm/effect-runtime/src/s2s-live-github.ts` | `7e050c2a8dbf5ce91ed991ddf7e18e2cffbed5ecbb60be68a5e1e8e9cb4c42c6` | request-distinct observer/download receipts |
| `src/hswm/effect-runtime/src/s2s-live-artifact.ts` | `eb800d68824568fd7053d18ebe8c519c6d7ec7269d1e3cce76bcd733a8382947` | request-independent artifact issuance/readback |
| `src/hswm/effect-runtime/test/s2s-live-github.test.ts` | `efb36858043cd5f8ae4b8a63e5d57686e095859eac1b0c4818ad8ddbade0bf6f` | provenance and tamper regressions |
| `src/hswm/effect-runtime/test/s2s-live-artifact.test.ts` | `a9fc9a63d6e76ed815d148bf4cdc5b62a8a9991bcc31cc2d018309d403791c03` | repeated-request rejection regressions |
| `src/hswm/effect-runtime/test/s2s-preregistration.test.ts` | `c97e8be959d23389980531a7fb776b5e0a305fb48bd2fab070c3e305eb6cb42c` | capability and Git-mode regressions |

These are engineering source anchors, not a material-research receipt. This
routine control-plane work does not add an `F1_R8_RESULTS_LOG.md` entry.

## Remaining P0 authority blockers

1. **Current-run authority is still absent.** The internal artifact service
   still accepts caller-selected `(workflowRunId, expectedHeadSha, role)`.
   Self-consistency of that supplied run is not dispatch authority.
2. **There is no strict current-invocation evidence decoder.** GitHub Actions
   environment/event bytes, repository/ref/event/workflow/job identity, run ID,
   attempt, and head SHA are not yet decoded into one self-hashed immutable
   invocation receipt.
3. **There is no run/stage capability issuer.** A new Layer must combine an
   authentic registration-B capability, current invocation evidence, and a
   fresh GitHub run observation, then issue stage-scoped capabilities without
   any public run/head/role parameters.
4. **The exact workflow does not exist.** The expected path is
   `.github/workflows/swm0w-s2s-confirmatory.yml`. It must exist in source A's
   tracked-byte manifest before source freeze and be hash-bound by the run
   authority. Do not add a dispatchable workflow before the invocation and
   authority contract is implemented and reviewed.
5. **There is no authoritative composition root or durable external evidence
   envelope.** Full observations exist in memory, but no closed Effect program
   owns and persists the complete replay closure.
6. **Rerun invalidation remains finalizer-owned.** A rerun can begin after any
   adapter check. The finalizer must perform the terminal attempt-one check
   immediately before create-only publication and define invalidation.
7. **Upload absence is not a VOID fact.** The future workflow must bind exact
   mandatory upload postconditions. Three empty list observations remain
   `RECONCILED_ABSENCE_NOT_PROOF`.
8. **Event 10 remains closed.** No path may append
   `VerifyEvidenceArtifact`, expose `PASS/KILL/INCONCLUSIVE`, or update learned
   state before all prior gates are independently replayed.

## Exact resume order

1. Start from code commit `4da46051f697fada418f52c681834e5d4ea91fdc`
   and read this document, the constitution, and the v3 KG projection.
2. Preserve the two protected unrelated user-modified files listed below.
3. Add one internal `s2s-workflow-contract.ts` as the single source for exact
   repository/ref/event/workflow path/name, attempt-one, job names, and
   stage-to-artifact-role mapping.
4. Add `s2s-invocation.ts`: strict bounded decoding of the current GitHub
   Actions event/environment into immutable self-hashed invocation evidence.
   Reject excess keys, malformed IDs/SHAs, pull-request/fork/manual events,
   reruns, and any repository/ref/workflow/job mismatch.
5. Add `s2s-run-authority.ts`: consume authentic registration-B authority,
   verify the workflow manifest row and current invocation, acquire a fresh
   request-distinct run observation, and issue Layer-local run/stage
   capabilities. No public function accepts a historical run ID or head SHA.
6. Replace the raw artifact triple with stage-specific methods. The capability
   snapshot supplies run/head and the method fixes the permitted role. Keep
   raw observer, issuer, and generic artifact authority absent from `index.ts`.
7. Implement the content-addressed durable evidence envelope and stage programs
   before adding the exact three-job workflow and mandatory uploads.
8. Implement the separate terminal finalizer, complete failure matrix, and
   event-10 creation only after independent adversarial review.
9. Only after all gates clear: freeze source A, create direct-child add-only B,
   select the future Quicknet round under preregistration, and dispatch once.

Do not create a preregistration file, select a future beacon, dispatch a
workflow, or compose event 10 during steps 3–8.

## Verification

```sh
cd src/hswm/effect-runtime
npm run verify
```

Result at code checkpoint `4da4605`: strict TypeScript, `151/151` Vitest tests
across 13 suites, production build, and npm pack dry run passed. The previous
Python S2S suite result remains recorded in the v2 handoff; it was not rerun for
this TypeScript-only authority slice. Green tests are engineering evidence
instruments, not a learned S2S efficacy verdict.

Independent read-only adversarial review found and drove closure of two
otherwise hidden paths: reused request IDs in intermediate absence run brackets
and non-`100644` preregistration tree entries. The final review found no
remaining local commit blocker. Standalone observation-receipt validation,
redirect-origin allowlisting, body chunk-count bounds, aggregate deadlines, and
injected clocks remain hardening or later composition work.

## Protected scope and nonclaims

These pre-existing user changes remain unstaged and untouched:

- `src/hswm/experiments/continual_live.py`
- `tests/test_hswm_continual_live.py`

No future round was selected, no preregistration was created, no confirmatory
workflow was dispatched, no candidate/adjudication result was produced, no
event-10 verdict was composed, no learned `W` changed, and no remote KG was
mutated.

## Minimal continuation prompt

```text
Continue HSWM from code checkpoint 4da46051f697fada418f52c681834e5d4ea91fdc.
Read docs/canon/HSWM_CONSTITUTION_2026-08-20.md,
docs/operations/HSWM_SWM0W_S2S_EFFECT_AUTHORITY_NEXT_SESSION_2026-08-22.md,
and ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v3.json. Preserve the two
protected continual_live changes. Stay strict TypeScript/Effect v3 and keep
Python numeric-only. Begin with the exact workflow contract, strict current
invocation evidence, and a Layer-local run/stage capability that consumes the
authentic registration-B capability. Remove caller-selected run/head/role from
the artifact boundary. Do not create preregistration B, select a future pulse,
dispatch, or compose event 10 before all gates clear.
```
