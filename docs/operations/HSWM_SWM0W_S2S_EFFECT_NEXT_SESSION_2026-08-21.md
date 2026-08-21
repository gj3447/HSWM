# HSWM SWM-0W-S2S TypeScript/Effect next-session handoff

Date: 2026-08-21
Continuation base: `762430de85839a398d61b604021f39e1fe6606c2`
Authority: the TypeScript/Effect direction is `USER_PRIMARY`; the implementation
split and repair plan are `SECONDARY_AI_PROPOSED`.
Checkpoint: `BLOCKED_PRE_PREREG / STRUCTURAL_1_6_9_CLEAR / ENGINEERING_ONLY /
SCIENTIFIC_UNJUDGED`.

This is an operational checkpoint, not a preregistration, result, or authority
to choose a future beacon round. The existing
[`HSWM_SWM0W_S2S_EFFECT_HANDOFF.v1.json`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v1.json)
is a hash-bound projection of the preceding checkpoint and is intentionally not
rewritten to describe this continuation.

## Fixed direction

HSWM's long-lived runtime is TypeScript-first and uses Effect. The current split
is deliberately asymmetric:

- TypeScript/Effect owns `Π`: strict decoding, typed failures, lifecycle state,
  Git/source chronology, resource policy, beacon and artifact boundaries. A
  final evidence envelope is still a target contract, not a live capability.
- Python owns the deterministic numerical oracle only: task generation,
  train/dev fitting and replay, test/integrity evaluation, and the candidate
  reducer.
- Python does not query Git, GitHub, drand, wall clocks, or host policy. The
  TypeScript control plane does not reserialize Python's numerical receipt tree;
  it binds the exact canonical bytes and their SHA-256.
- The in-memory Effect `Ref` Layer is a test simulation. It is not durable truth
  across the planned register, confirm, and adjudicate jobs.

Effect is pinned at `3.22.1`. The implementation uses the v3 `Schema`,
`Context.Tag`, `Layer`, typed `Data.TaggedError`, and atomic `Ref.modify`
contracts. No Effect v4 API is mixed in.

## Present implementation checkpoint

The conceptual delta is narrow: `H/W/A/F` are unchanged and only `Π` is
strengthened. The hashes below identify the new or changed boundary bytes after
independent read-only reviews. They are engineering review anchors, not a
scientific receipt or authorization to preregister or dispatch.

| path | SHA-256 | present scope |
|---|---|---|
| `src/hswm/effect-runtime/src/s2s-confirmatory.ts` | `55f8d0b17dd4bb7e4eca14a6f0b5cff7767a644c410e84e8e056a0f2d17cfb38` | event/policy v2, chronology and VOID model |
| `src/hswm/effect-runtime/src/s2s-preregistration.ts` | `777f502c3591696b2922d2caf89fe8b95e997ab834a9cb9c7a9b899c619fd3da` | prereg sibling policy-hash pin updated |
| `src/hswm/effect-runtime/src/s2s-bounded-process.ts` | `57ea49333a2422c3e90322dcadf6bd94749f8a88b2685a9ee8f8560d41a1423a` | bounded process-group lifecycle |
| `src/hswm/effect-runtime/src/s2s-durable.ts` | `4e5cc00f1fe3b59854522ceec1d5ac8a012c55397ef982f4d6e2ad006e0845c6` | canonical predecessor journal and defensive recovery |
| `src/hswm/effect-runtime/src/s2s-durable-file.ts` | `de8dec3f7a6a3cdb45d5ff26a8edb1ebc355b1ad777e5fdc1095735047394398` | POSIX private-root create-only publication |
| `src/hswm/effect-runtime/src/s2s-live-python.ts` | `4218ef0a3b5f999362db2d03905c6e95b71889fcebf6568b2452f9dbb0e8a00c` | golden-only pinned Python preflight |
| `src/hswm/effect-runtime/src/s2s-zip.ts` | `1758fdba78598f06084a459d8d4eb1d60f225b7e66e290af98b759b49cbc72d2` | exact stored-entry artifact ZIP validator |
| `src/hswm/effect-runtime/src/s2s-job-sequence.ts` | `89d56620c080e7fbcd88482b32e1357cdeaf33b40b16cbd75868906f22d5f038` | structural `1 -> 6 -> 9` carrier composition only |
| `src/hswm/effect-runtime/test/s2s-confirmatory.test.ts` | `83207800b9ab6fd41435d864fcfec3c0a3f9dda766c18be07fa4f69714b86ee2` | chronology, durable, and VOID regressions |
| `src/hswm/effect-runtime/test/s2s-live-python.test.ts` | `7b8b540ea0dc500f7ba5489e6da9a91bf29464b6e893ed4d849d4491a0fc1446` | process and golden-layer regressions |
| `src/hswm/effect-runtime/test/s2s-zip.test.ts` | `e61093d06e24430f0e7fa76f0e5099b0fdd81788f09c624df6c6d47ed3c59481` | synthetic and checked-in real-artifact ZIP regressions |
| `src/hswm/effect-runtime/test/s2s-job-sequence.test.ts` | `3192db6320a436122ad920e8f872cf600a8362ec165bb27b27c7ca977fb3aef9` | isolated carrier and mutation regressions |

Operational policy v2 has receipt SHA
`7e4d7252962e53d70f4e74b5117338ced55a645c431e9173256de9f514043ad9`.
The adopted pilot receipt file is
`artifacts/swm0w_s2s/pilot_adoption/32442437970/pilot_adoption_receipt.json`;
its file SHA-256 is
`fb34e5e9533409810f616815edc8565b244b5067a9bb70f643eb42d8bd044a78`.

## Repaired control invariants

### Preregistration/source boundary

1. **Source A is an exact raw commit object.** The process adapter uses the
   pinned Ubuntu `/usr/bin/git`, a minimal fixed environment, and
   `--no-replace-objects`. P→A ancestry is proved by bounded traversal of raw
   commit parent headers, not `merge-base`; replacement refs, grafts, inherited
   Git identity variables, and `PATH` wrappers cannot redefine the graph.
2. **The prereg path is absent from A.** Both source construction and parsed
   source-freeze semantics reject an A that already tracks
   `prereg/PREREG_SWM0W_S2S_GATE_V1.json`.
3. **B binds the originally validated bytes.** A private `WeakMap` capability,
   entry-time byte copy, deep-frozen decoded view, defensive byte getter, raw
   single-parent check, and exact private-byte comparison close structural
   forgery, post-parse mutation, and asynchronous input-buffer TOCTOU.

The raw traversal is fail-closed at 4,096 unique commits, 64 parents per commit,
4 MiB per commit, 64 MiB total, and 120 seconds. Regressions cover annotated
tags, replace refs, grafted ancestry and B parentage, redirected `GIT_DIR`, fake
`PATH`, cycles, bounds, preexisting prereg paths, nested/byte-copy mutation,
hash-invalid B, and unchanged canonical A/B.

### Confirmatory control/evidence boundary

4. **Pulse chronology is cross-event exact.** The shared pure Quicknet module
   derives round time from the official chain/genesis/period; workflow creation,
   registration completion, explicit wait start, verification, declared lead,
   and wait telemetry are checked on one integer-second timeline.
5. **The frozen 300-second command slack is enforced.** Command accounting uses
   `wait + ceil(postSeedNanoseconds / 1e9)` as its lower bound and that value plus
   exactly 300 seconds as its inclusive upper bound.
6. **Archives and largest members are nonempty.** Registration, candidate, and
   adjudication evidence rejects zero-byte archives and zero-byte largest
   members at both decoding and policy validation.

Regressions cover the pre-run pulse, wrong chain/time/lead/wait, wait budget
3,900/3,901, confirm-after-pulse zero wait, nanosecond ceiling and slack
boundaries, and zero-byte evidence for all three artifact roles.

### Durable carrier and process boundary

7. **Production and completion evidence are chronologically separated.** A
   candidate carrier ends at `RecordCandidateProduced`; an adjudication carrier
   ends at `RecordAdjudicationProduced`. Their own job-completion/readback event
   can only be appended by a later job or external process.
8. **Cross-job state is reconstructed from exact bytes.** Carrier journals bind
   predecessor file SHA, the full event prefix, per-event receipts, final state,
   and a journal self-hash. The Linux/POSIX store uses a private fixed root,
   no-follow reads, bounded files, temp-file fsync, create-only hard-link CAS,
   and directory fsync. A byte-equal retry must re-establish directory
   durability before it can return `AlreadyPresent`. Restart, duplicate
   publication, fsync failure, fork, gap, symlink, truncation, and oversize
   cases are covered.
9. **Subprocess failure is bounded and reaped.** The runner uses no shell,
   takes one data-only snapshot of argv/env/stdin, caps paths and every byte
   surface, and kills the detached process group on timeout, cancellation, or
   stream failure. Cleanup failure is observable rather than reported as
   success. The Python adapter rehashes an open executable FD, invokes that FD
   through `/proc`, preserves the reviewed venv path as `argv0`, and confines
   bytecode cache state to a private scoped directory.
10. **Python integration is still golden-only.** The current Layer pins the
    executable hash and version, imported module path, oracle source SHA, and
    exact 5,795-byte golden result. It never invokes confirmatory `confirm` or
    `adjudicate`, does not pin the complete imported dependency closure, and
    therefore yields no candidate evidence.

### Artifact and job-sequence boundary

11. **ZIP validation is producer-specific and seekable.** It accepts only the
    pinned `actions/upload-artifact` v4.6.2 stored-entry dialect: exact root
    member roster, method 0, signed 16-byte data descriptor, local/central
    agreement, bounded regular files, CRC remeasurement, and exact API/download
    digest and byte length. A checked-in GitHub artifact and an independently
    emitted deterministic fixture lock the dialect. This is not a general ZIP
    extractor.
12. **The structural sequence is exactly `1 -> 6 -> 9`.** Each stage strictly
    decodes an exact-length tuple, validates all predecessor ZIPs, reconstructs
    the complete prefix, checks raw numeric-member hashes and adjudication
    projection bindings, and returns defensive upload members. Extra events and
    post-call byte mutation are rejected or isolated.
13. **There is no verdict composition path.** Review reproduced a false-`PASS`
    construction from an arbitrary ASCII candidate and caller-authored
    self-consistent adjudication. The event-10 finalizer was therefore removed.
    `VerifyEvidenceArtifact` remains a target-state transition, but no production
    composition function appends it until real Python replay and authoritative
    GitHub readback are composed directly.

The ZIP dialect was checked against the pinned action dependency graph and the
PKWARE APPNOTE, but repository tests—not generic ZIP compatibility claims—define
the accepted byte boundary.

## Remaining blockers before preregistration

1. **No authoritative composition root exists.** It must construct lifecycle
   events from a validated source/preregistration capability and external
   observations; accepting caller-completed event objects is not authority.
2. **GitHub run/job/artifact observation is absent.** Bind exact job IDs, names,
   run, attempt, head SHA, completion status/conclusion, and canonical observation
   digests. Candidate verification and the pre-adjudication requery/redownload
   must be independent observations, not one readback reused twice.
3. **Verified future-pulse input is absent.** Add the isolated pinned drand
   verifier without selecting or querying a future round during development.
4. **Actual Python candidate/replay execution is absent.** The Effect shell must
   run the pinned oracle's `confirm` and `adjudicate` operations itself, bind
   their exact input/output hashes and full runtime/source dependency identity,
   and admit no caller-fabricated numeric attestation. The golden verifier is
   only preflight.
5. **External finalization is absent.** Only after all three jobs have completed
   and the adjudication artifact has been independently queried and downloaded
   may a separate process append event 10 and expose `PASS`, `KILL`, or
   `INCONCLUSIVE`.
6. **Failure authority is incomplete.** Direct pre-stage VOID IDs and
   `evidenceSha256` are caller-supplied in the pure model. A live adapter must
   derive them from canonical GitHub observations. “Always upload VOID” is not
   claimable when the artifact service itself is unavailable; that case must
   remain non-evidentiary and explicitly reconciled.
7. **The actual workflow is absent.** The register/confirm/adjudicate jobs,
   publication-unknown reconciliation, external finalizer, and all failure paths
   require independent audit. The in-memory `Ref` and local file adapter do not
   by themselves establish GitHub Actions authority.

## Resume order

1. Verify the protected user changes listed below are still untouched.
2. Reconfirm `npm run verify`, the 205-test Python S2S baseline, policy v2 SHA,
   and the source hashes above before extending the boundary.
3. Implement one production `Effect.runPromise` composition root around the
   validated preregistration capability, canonical GitHub observation adapter,
   and isolated verified-pulse adapter. Do not select a future pulse.
4. Extend the pinned Python process Layer with actual fixed `confirm` and
   `adjudicate` operations. The composition root—not a caller-supplied interface
   value—must own execution and produce runtime-authentic bindings.
5. Add two independent candidate artifact observations and one post-job
   adjudication readback, then implement the external event-10 finalizer.
6. Add the exact register/confirm/adjudicate workflow, reconcile publication
   outcomes without blind retry, and audit the full failure/VOID matrix.
7. Only after those reviews freeze source A, create direct-child add-only B, and
   proceed to future-seeded measurement.

The next session must not skip directly to preregistration: durable structural
carriers now exist, but no live authority composition establishes the required
external evidence boundary or permits event 10.

## Verification commands

```sh
cd src/hswm/effect-runtime
npm ci --ignore-scripts --no-audit --no-fund
npm run verify
```

```sh
uv run pytest -q \
  tests/test_hswm_swm0w_s2s_worlds.py \
  tests/test_hswm_swm0w_s2s_family.py \
  tests/test_hswm_swm0w_s2s_operator.py \
  tests/test_hswm_swm0w_s2s_training.py \
  tests/test_hswm_swm0w_s2s_protocol.py \
  tests/test_hswm_swm0w_s2s_pilot.py \
  tests/test_hswm_swm0w_s2s_pilot_adoption.py \
  tests/test_hswm_swm0w_s2s_numeric_oracle.py
```

Current results are `83/83` Effect-package tests plus strict TypeScript, build,
and npm-pack dry-run checks. The unchanged numerical side passed `205/205`
relevant Python S2S tests. Passing counts are engineering checks, not an efficacy
verdict.

## Protected scope and nonclaims

The following pre-existing user changes are outside this slice and must remain
untouched:

- `src/hswm/experiments/continual_live.py`
- `tests/test_hswm_continual_live.py`

No future beacon round was selected, no confirmatory job was dispatched, no
scientific candidate was produced, and no remote KG mutation was performed in
this checkpoint. No research-result receipt or `F1_R8_RESULTS_LOG.md` entry is
warranted for this control engineering. The historical local KG file is a
repository projection for continuity; it is not HSWM cognition, a live Neo4j
publication, or evidence of learned set-to-set efficacy.
