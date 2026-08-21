# HSWM SWM-0W-S2S TypeScript/Effect next-session handoff

Date: 2026-08-21
Repair base: `94eca74cb9d2d3fb4d0738d6d3ab12ddd637019c`
Authority: the TypeScript/Effect direction is `USER_PRIMARY`; the implementation
split and repair plan are `SECONDARY_AI_PROPOSED`.
Checkpoint: `BLOCKED_PRE_PREREG / CONTROL_CORE_AUDIT_CLEAR / ENGINEERING_ONLY /
SCIENTIFIC_UNJUDGED`.

This is an operational checkpoint, not a preregistration, result, or authority
to choose a future beacon round. Its machine-readable local-KG projection is
[`HSWM_SWM0W_S2S_EFFECT_HANDOFF.v1.json`](../../ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v1.json).

## Fixed direction

HSWM's long-lived runtime is TypeScript-first and uses Effect. The current split
is deliberately asymmetric:

- TypeScript/Effect owns `Π`: strict decoding, typed failures, lifecycle state,
  Git/source chronology, resource policy, beacon and artifact boundaries, and
  final evidence envelopes.
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

The following hashes identify the repaired S2S control-core bytes. Independent
read-only review replayed the reproduced source, chronology, accounting, and
artifact-boundary failures against these exact bytes and returned `CLEAR`.
This is engineering clearance for the pure control core, not authorization to
preregister, dispatch, or make an efficacy claim.

| path | SHA-256 | audit status |
|---|---|---|
| `src/hswm/effect-runtime/src/s2s-canonical.ts` | `c3d8f36853124ad0387cc68b9373571f8d45b888472fc20581e3b7993dacb257` | clear within reviewed scope |
| `src/hswm/effect-runtime/src/s2s-seed.ts` | `bfbdce6f09360c10c989a145c441fbd8bf00d51a607dfc7719170d42820cef2c` | cross-language golden clear |
| `src/hswm/effect-runtime/src/s2s-confirmatory.ts` | `eb7e59bb48bb60b71a79e64d0c3e2f10af6e89d2c39be33382d645bf96a08167` | independent exact-byte audit clear |
| `src/hswm/effect-runtime/src/s2s-orchestration.ts` | `d9bbaa35bc8c91576ef5c121699c201c06807da47270e0c63002987d35f7a9c8` | typed ports only; no live adapters |
| `src/hswm/effect-runtime/src/s2s-preregistration.ts` | `7a818b97b749cc72d56ede942b911c8a116ef7358180d75e8df8256f1678855f` | independent exact-byte audit clear |
| `src/hswm/effect-runtime/src/s2s-quicknet.ts` | `a78cb00e11815cc047a069f49a674a6d45f6a9e0947c5685a67d50eec82e21ec` | pure shared Quicknet identity/time arithmetic |
| `src/hswm/effect-runtime/test/s2s-confirmatory.test.ts` | `066ffa96ed40a6561504d5bbf11d14cd040dc066e9cb799422346789206fcadc` | 16 focused tests pass |
| `src/hswm/effect-runtime/test/s2s-preregistration.test.ts` | `bd8c7e93d2de684cafc74ec359b4e5fbb824bd38ccf9dbc46d58d75017539a13` | 17 focused tests pass |
| `src/hswm/experiments/swm0w_s2s_numeric_oracle.py` | `27854351f642727dc21ec63e987bf3ae67a205f4664f5e0ad448eb3b7a8c570b` | independent adversarial audit clear |
| `tests/test_hswm_swm0w_s2s_numeric_oracle.py` | `e1921acce5b012d4030602dae57d2a5611ba395346e460cdfd468489694617ca` | 16 focused tests pass |

The operational resource-policy receipt SHA is
`d6a0c679f9ff9c72773f8a3713bffe1f3ac5d2b6f5e53e653603b30204d9c7eb`.
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

## Remaining blockers before preregistration

1. **Live adapters and durable cross-job receipts are absent.** Implement the
   bounded Git/GitHub evidence adapters, isolated pinned drand subprocess,
   fixed-argv Python oracle process, immutable ZIP/API digest/readback gateway,
   and durable receipt reconstruction. The live ZIP adapter must verify every
   exact member is nonempty—not only the largest member—and reject duplicates,
   traversal paths, symlinks, size drift, and digest drift.
2. **The three-job chronology is absent.** Implement and independently audit the
   exact `register -> confirm -> adjudicate` workflow, one-shot run binding,
   failure/unknown-outcome paths, always-upload operational VOID, and final
   artifact readback. The in-memory Effect `Ref` remains test-only and cannot be
   treated as state shared by those jobs.

## Resume order

1. Verify the protected user changes listed below are still untouched.
2. Reconfirm the frozen hashes and `npm run verify` result before extending the
   control plane; do not weaken or bypass the repaired raw-Git and chronology
   boundaries.
3. Re-run the numeric-oracle focused tests and cross-language golden tests.
4. Implement the live adapters:
   Git/GitHub evidence, isolated pinned drand subprocess, bounded Python process,
   artifact ZIP/readback, and durable cross-job receipts.
5. Add the three-job `register -> confirm -> adjudicate` workflow and audit every
   failure path. Do not select a future pulse yet.
6. Only then freeze source A, create the direct-child add-only B
   preregistration, and proceed to future-seeded measurement.

The next session must not skip directly to preregistration: the pure core is
clear, but no live adapter or cross-job chronology yet establishes the required
external evidence boundary.

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

Current repaired-core results are `43/43` Effect-package tests plus strict
TypeScript, build, and npm-pack checks. The unchanged numerical side last passed
`205/205` relevant Python S2S tests. Passing counts are engineering checks, not
an efficacy verdict.

## Protected scope and nonclaims

The following pre-existing user changes are outside this slice and must remain
untouched:

- `src/hswm/experiments/continual_live.py`
- `tests/test_hswm_continual_live.py`

No future beacon round was selected, no confirmatory job was dispatched, no
scientific candidate was produced, and no remote KG mutation was performed in
this checkpoint. The local KG file is a repository projection for continuity;
it is not HSWM cognition, a live Neo4j publication, or evidence of learned
set-to-set efficacy.
