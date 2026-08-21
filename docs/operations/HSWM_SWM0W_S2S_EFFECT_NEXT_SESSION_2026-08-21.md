# HSWM SWM-0W-S2S TypeScript/Effect next-session handoff

Date: 2026-08-21
Workspace base: `a4bff3b47c64854b424b2dc8a00db07745d6cf9e`
Authority: the TypeScript/Effect direction is `USER_PRIMARY`; the implementation
split and repair plan are `SECONDARY_AI_PROPOSED`.
Checkpoint: `BLOCKED_PRE_PREREG / ENGINEERING_ONLY / SCIENTIFIC_UNJUDGED`.

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

The working tree contains the following not-yet-authorized S2S control slice.
The hashes identify the exact pre-repair bytes to resume from; they are not
approval hashes.

| path | SHA-256 | audit status |
|---|---|---|
| `src/hswm/effect-runtime/src/s2s-canonical.ts` | `c3d8f36853124ad0387cc68b9373571f8d45b888472fc20581e3b7993dacb257` | clear within reviewed scope |
| `src/hswm/effect-runtime/src/s2s-seed.ts` | `bfbdce6f09360c10c989a145c441fbd8bf00d51a607dfc7719170d42820cef2c` | cross-language golden clear |
| `src/hswm/effect-runtime/src/s2s-confirmatory.ts` | `bdada1b126e0d450e36db409c47fd9c77bd64f9bb203f61c2ea7fb79165f20bf` | blocked by three control invariants below |
| `src/hswm/effect-runtime/src/s2s-orchestration.ts` | `d9bbaa35bc8c91576ef5c121699c201c06807da47270e0c63002987d35f7a9c8` | typed ports only; no live adapters |
| `src/hswm/effect-runtime/src/s2s-preregistration.ts` | `9941f46d51a0c4cf99281229bddee057bbb64b50b0eaa0332b3ac6d0cdd9b6d3` | blocked by three source/B invariants below |
| `src/hswm/experiments/swm0w_s2s_numeric_oracle.py` | `27854351f642727dc21ec63e987bf3ae67a205f4664f5e0ad448eb3b7a8c570b` | independent adversarial audit clear |
| `tests/test_hswm_swm0w_s2s_numeric_oracle.py` | `e1921acce5b012d4030602dae57d2a5611ba395346e460cdfd468489694617ca` | 16 focused tests pass |

The operational resource-policy receipt SHA is
`d6a0c679f9ff9c72773f8a3713bffe1f3ac5d2b6f5e53e653603b30204d9c7eb`.
The adopted pilot receipt file is
`artifacts/swm0w_s2s/pilot_adoption/32442437970/pilot_adoption_receipt.json`;
its file SHA-256 is
`fb34e5e9533409810f616815edc8565b244b5067a9bb70f643eb42d8bd044a78`.

## Six blockers to close first

### Preregistration/source boundary

1. **Source A must be a commit.** An annotated-tag object currently passes the
   Git checks even though it cannot be the direct parent of B. Require
   `git cat-file -t <A>` to return exactly `commit` before source-freeze work.
2. **The prereg path must be absent from A.** Reject A if
   `prereg/PREREG_SWM0W_S2S_GATE_V1.json` is already tracked; otherwise the
   required add-only A→B transition is impossible.
3. **B must bind the originally validated bytes.** The parsed preregistration is
   currently mutable and B validation reserializes it. Retain a private
   immutable byte snapshot (or stable original file hash), compare B against
   that snapshot, and reject structurally forged validation objects.

Required regressions: annotated-tag A; preexisting prereg path; nested mutation
after parse; mutation of an exposed byte-array copy; mutated/hash-invalid B;
unchanged canonical B.

### Confirmatory control/evidence boundary

4. **Pulse chronology must be cross-event exact.** Derive Quicknet round time
   from the committed round, require it after workflow creation and registration
   completion, bind declared lead to those timestamps, and bind pulse-wait
   telemetry to an explicitly defined wait-start timestamp. A pulse from time 1
   must not advance a run created at time 100.
5. **The frozen 300-second command slack must be enforced.** In addition to the
   lower accounting bound, require command elapsed time not to exceed wait plus
   post-seed work plus the declared slack, with an explicit integer-second
   rounding rule.
6. **Archives and members must be nonempty.** Registration, candidate, and
   adjudication artifact evidence must reject zero-byte archives and zero-byte
   largest members before digest/readback promotion.

Required regressions: pre-run pulse; mismatched lead; mismatched wait;
registration at/after committed pulse; excessive unaccounted command time; and
zero-byte evidence for all three artifact roles.

## Resume order

1. Verify the protected user changes listed below are still untouched.
2. Patch the six blockers and only their focused tests.
3. Run `npm run verify` in `src/hswm/effect-runtime` and re-run an independent
   read-only adversarial audit on the new exact hashes.
4. Re-run the numeric-oracle focused tests and cross-language golden tests.
5. Implement live adapters only after both prereg and control audits are clear:
   Git/GitHub evidence, isolated pinned drand subprocess, bounded Python process,
   artifact ZIP/readback, and durable cross-job receipts.
6. Add the three-job `register -> confirm -> adjudicate` workflow and audit every
   failure path. Do not select a future pulse yet.
7. Only then freeze source A, create the direct-child add-only B
   preregistration, and proceed to future-seeded measurement.

The next session must not skip directly to preregistration because the current
green test suite does not cover the six reproduced attacks.

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

Last observed results before this handoff were `28/28` Effect-package tests and
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
