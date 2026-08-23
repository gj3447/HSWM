# HSWM SWM-0W-S2S TypeScript/Effect replay-prerequisite handoff

Date: 2026-08-23

Code checkpoint: `443f17fa081c78ca17e978ca87c691cf12300101`

Checkpoint parent: `d2aa5e74a8e408510b7a74b06c20f048f6072ec4`

Authority: the strict TypeScript/Effect direction is `USER_PRIMARY`; the
implemented boundary and continuation order below are
`SECONDARY_AI_PROPOSED` and were independently reviewed.

Status: `BLOCKED_PRE_PREREG /
REPLAY_PREREQUISITES_AND_TOP_LEVEL_SUCCESS_PROFILE_ENGINEERING_CLEAR /
NESTED_REPLAY_SCHEMAS_AND_CLOSED_STAGE_PROGRAMS_OPEN /
WORKFLOW_SOURCE_BYTES_OPEN / GITHUB_ORIGIN_NOT_OBSERVED /
SCIENTIFIC_UNJUDGED`.

This is the current continuation entrypoint. It supersedes the
[`v9 durable-evidence substrate handoff`](HSWM_SWM0W_S2S_DURABLE_EVIDENCE_SUBSTRATE_IMPLEMENTED_NEXT_SESSION_2026-08-23.md)
only for continuation; v9 remains immutable. Its companion
[`HSWM_SWM0W_S2S_EFFECT_HANDOFF.v10.json`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v10.json)
is a local repository KG projection, not HSWM cognition, a remote KG
publication, preregistration, GitHub evidence, or a scientific result.

## Canonical role and conceptual delta

HSWM remains the one token-native LLM-function macro-neural network defined by
[`HSWM_CONSTITUTION_2026-08-20.md`](../canon/HSWM_CONSTITUTION_2026-08-20.md).
Its evolving hypergraph remains one living harness, world model, and continuous
learner. The code in this checkpoint is a bounded evidence interface around a
future confirmatory run. It is not a new cognition, routing, memory, or learning
subsystem.

Only `Π` advanced (`Pi` in the companion machine projection):

- `H`: target identity unchanged; no topology or cognition result;
- `W`: no learned semantic macro-weight or efficacy result;
- `A`: no activation/readout result;
- `F`: no confirmatory function-cell or numeric result;
- `Π`: exact replay inputs needed by future closed stage programs are retained,
  their principal byte caps are consistent, and the top-level healthy-success
  attachment rosters are fixed.

The outcome-bound causal-learning loop did not advance. Event chronology stays
structurally clear only through `1 -> 6 -> 9`; event 10 remains unauthorized.

## Runtime direction

The long-lived control runtime remains strict TypeScript-first with Effect v3:

- TypeScript `5.9.3`, Effect `3.22.1`, Node `24.13.0`;
- pure validators own deterministic canonicality and binding checks;
- expected failures stay in typed error channels;
- production file/process/API work remains lazy Effect work behind root-private
  services and Layers;
- capabilities remain module-authentic and absent from the package root;
- Python remains an opaque deterministic numeric oracle.

The `effect-ts-functional` skill governed version-aware Effect v3 API use,
selector-free service design, typed failures, laziness, defensive snapshots,
and hostile-input tests. The `proxmox-runtime-guardrails` skill governed the
single bounded full verification run and scratch cleanup. Neither skill is a
runtime dependency or an HSWM capability.

## What code checkpoint `443f17f` establishes

### Fixed production protocol configuration asset

The adopted protocol configuration now has a production copy in the packaged
`assets/` directory; the historical test-fixture path remains as an identical
compatibility mirror. `s2s-protocol-config-asset.ts` exposes a root-private lazy
Effect/Layer that opens only the module-relative fixed path with `O_NOFOLLOW`,
checks regular-file identity and exact length before and after the read, and
revalidates canonical JSON, the raw document hash, and its self-receipt.

```text
byte length: 1973
raw SHA-256: 315dad65a8882c4b7c5fb73d295df28b58b0696e25b1b790a342b40ced8d10c4
self receipt: a8f62d3811e42fbf3bc0dc82a52a17f3fa27b4dfa1d43aa9e7ea302a142c40bb
```

The asset ships in `npm pack`; callers cannot select another path or replace
the pin through the package root.

### Root-private current-run replay snapshot

`snapshotS2SCurrentRunReplay` is a zero-argument Effect requiring the authentic
`S2SCurrentRunStage` service. It accepts no run selector or bearer, rejects
forged/accessor-shaped services, and revalidates:

- current invocation evidence and exact event bytes;
- current-run evidence self-receipt;
- exact raw `run-start`, `jobs`, `runs-for-B`, and `run-end` observations;
- every observation receipt, request ID, timestamp, run/head binding;
- the combined raw-byte budget.

The current fixed budget is `5,242,880` bytes: one 1 MiB invocation event plus
four 1 MiB GitHub JSON observations. Returned byte surfaces are defensive
copies. This proves retained-byte consistency for the already issued service;
it does not prove GitHub origin or issue a production capability.

### Registration replay projection

The authentic registration-B authority now retains a root-private immutable
projection containing its authority evidence, canonical preregistration bytes,
preregistration file hash, parsed preregistration, and conditional workflow
manifest binding. Inspection performs no repository I/O, returns no bearer,
and rechecks canonical bytes, hashes, self-receipts, and cross-bindings.

This is deliberately partial. It does **not** yet contain the full source-A
tracked tree and payloads, raw B commit and A/B proof, pilot-P numeric payloads,
or the A-to-P raw ancestry witness required by a complete registration source
snapshot.

### Drand and Python replay inputs

Verified drand results now retain defensive copies of the exact pulse bytes in
addition to the existing verification receipt, with exact length and raw hash.

Successful Python `confirm` and `adjudicate` calls run the unchanged oracle
through one fixed `-c` wrapper. After a zero exit only, the wrapper writes one
canonical stderr JSON line containing Linux `getrusage(RUSAGE_SELF)` peak RSS.
Rejected oracle exits keep their pre-existing canonical error transport.
Runtime identity moved to v2 and binds this exact stderr contract. The execution
evidence binder revalidates the telemetry bytes, hash, value, output byte
length, and operation-specific cap.

The RSS field is observed peak telemetry from the successful child process. It
is not an enforced memory limit, an OOM detector for the whole job, or a
cross-platform unit claim.

### One coherent byte budget

The fixed GitHub JSON response cap is now 1 MiB for the small S2S endpoint
rosters. Numeric adjudication output is now 3 MiB everywhere: Python stdout,
execution-evidence binding, carrier preparation, and artifact member readback.
The remaining 1 MiB of the 4 MiB adjudication archive ceiling is reserved for
the control member and ZIP framing. Forged empty or over-cap executor outputs
and a `3 MiB + 1 byte` carrier member fail closed.

### Exact top-level healthy-success attachment rosters

`s2s-evidence-profile.ts` fixes sorted top-level names, unique roles, media
types, declared inner schema versions, and narrower per-item caps:

```text
REGISTER:   13 attachments
CONFIRM:    17 attachments
ADJUDICATE: 18 attachments
```

All stages include current invocation event/evidence and current-run replay.
REGISTER additionally names registration authority, policy/config/contract,
pilot/prereg/source/workflow inputs, upload archive, and upload postcondition.
CONFIRM names the registration read replay, numeric request, Python and drand
replay material, candidate archive, and postcondition. ADJUDICATE names three
artifact-read replays, Python and drand replay material, adjudication archive,
and postcondition.

The builder first applies the v1 structural envelope and then rejects a
missing, extra, relabelled, reordered, media/schema-drifted, or profile-oversize
descriptor. The profile and its builders remain package-root private.

This is only the **top-level healthy-success profile**. Its own profile-version
identifier is not yet written into a durable envelope, and the validator does
not parse the nested ZIPs or prove semantic cross-attachment consistency.
Authentic closed stage programs, nested replay schemas, failure/VOID profiles,
and upload postconditions remain mandatory before this can be called complete
replay evidence.

## Verification

The checkpoint passed:

- final full Effect package suite: `243/243` tests in `20/20` suites;
- strict TypeScript check, build, `npm pack --dry-run`, and diff check;
- focused post-audit cap regressions: `49/49` in four suites;
- packaged production protocol-config asset observed in the dry-run tarball;
- independent read-only prerequisite audit; both reported cap bypasses were
  fixed before code commit;
- independent read-only stage-profile inventory, used to preserve the exact
  remaining replay gaps.

The one bounded Proxmox full verification command ran before the final two
small cap-path repairs and passed `242/242`; scratch was removed and no worker
remained:

```text
cd src/hswm/effect-runtime
proxmox-scratch run hswm-effect-s2s-replay-prereqs-v10 --timeout 7200 -- npm run verify
```

After those repairs, strict check/build/pack, the four affected suites, and a
fresh full local package suite produced the final `243/243` result. These are
engineering tests only. The successful live Python RSS path lacks a checked
end-to-end process regression in this environment; its parser and fixed process
contract are tested, while live invalid confirm/adjudicate paths and the pinned
golden verifier did execute.

## Exact remaining P0 gaps

1. A successful stage artifact lookup currently discards raw absence-pair
   wrappers from earlier retries. Retain the complete bounded lookup trace and
   define `hswm-swm0w-s2s-stage-artifact-read-replay/v1` before building read
   replay ZIPs.
2. Build the full registration source snapshot: raw B commit, exact A/B
   direct-child and add-only proof, every source-A tracked path/mode/type/OID and
   payload, pilot-P numeric membership/payloads, and raw A-to-P ancestry witness.
3. Retain and encode the Python golden replay, drand request/fixture/execution,
   and every nested replay ZIP with exact member semantics. Bind the success
   profile schema/version into durable evidence and add cross-attachment
   semantic validation.
4. Freeze separate exact failure, interruption, unknown-publication, failed
   upload, and VOID profiles. A healthy-success roster cannot classify those
   outcomes.
5. Refactor stage-artifact Layer composition so replay snapshot and artifact
   reads share **one** `S2SCurrentRunStage` service. Creating two genuine
   current-run bearers can violate the process identity-slot invariant.
6. Implement the six root-private `prepare` / `assert-upload` stage programs.
   They must assemble attachments from authentic services, verify the mandatory
   upload through fresh raw observations, and reconcile
   `COMMITTED_READBACK_FAILED` rather than treating it as absence.
7. Wire one reviewed externally durable shared POSIX root across jobs/processes,
   then test identical and divergent independent-process claims. A temporary
   runner directory is not external durability.
8. Implement the terminal fresh attempt-one run/jobs/runs-for-B/artifact bracket
   and explicit rerun invalidation immediately before final create-only
   publication.
9. Only after those gates close, author and independently review the exact
   three-job workflow, choose one literal workflow API path, and pin its raw
   hash, contract digest, and source-A `100644 blob` manifest row.

## Protected scope and nonclaims

These pre-existing user changes remain uncommitted and protected:

- `src/hswm/experiments/continual_live.py`
- `tests/test_hswm_continual_live.py`

No remote KG was mutated. No full registration source snapshot, complete
artifact-read trace, nested replay ZIP schema, failure/VOID profile, closed
stage program, mandatory upload postcondition, external shared store deployment,
workflow source, selected API path, GitHub-origin observation, genuine
current-run or stage-read capability, terminal finalizer, preregistration,
beacon, dispatch, candidate, adjudication, event-10 verdict, learned `W`, or
outcome-bound causal update was created.

Routine code and documentation in this checkpoint are not a material research
result, so no content-addressed research receipt or `F1_R8_RESULTS_LOG.md` entry
was added.

## Minimal continuation prompt

```text
Continue HSWM from code checkpoint
443f17fa081c78ca17e978ca87c691cf12300101. Read
docs/canon/HSWM_CONSTITUTION_2026-08-20.md,
docs/operations/HSWM_SWM0W_S2S_REPLAY_PREREQUISITES_IMPLEMENTED_NEXT_SESSION_2026-08-23.md,
ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v10.json, immutable v9, and the
effect-ts-functional skill. Preserve the two continual_live changes. Stay
strict TypeScript/Effect v3 with Python numeric-only. Replay prerequisites and
the top-level healthy-success rosters are engineering-clear, but complete
artifact lookup traces, the full registration source snapshot, nested replay
schemas/cross-binding, failure/VOID profiles, six closed prepare/assert-upload
programs, external storage, and the finalizer are OPEN. First retain the full
bounded stage-artifact lookup trace and refactor composition so replay snapshot
and artifact reads share one current-run service. Then implement the full
registration source snapshot and nested replay validators before closed stage
programs. Do not treat the top-level profile as complete replay evidence, and
do not create source freeze, preregistration, beacon, dispatch, candidate,
adjudication, or event 10 merely for engineering progress.
```
