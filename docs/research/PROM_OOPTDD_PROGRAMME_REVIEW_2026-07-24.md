# PROM Programme Review — OOPTDD falsification infrastructure (2026-07-24)

> Lakatosian appraisal of two days of OOPTDD work (v1 critique → v2.4.4),
> written PROM-style: predictions, hits, refutations, problemshift verdict,
> and the next discriminating questions. Tree: LakatosTree_HSWM_20260719,
> node d1-ooptdd-floor-scope-correction.

## Hard core (protected)

A research claim is only as real as its cheapest falsification path. Every
behavioral claim must carry an executable, tamper-evident, *measured*
falsification harness — and the harness itself is a claim, subject to the
same discipline.

## Protective belt (current)

receipts (LOCK + negative oracle) → hash-chained log → LOCK_CHECKS machine
binding → LakatoTree chain-head anchors → automated mutation scoring →
test harvester → suite-wide vacuity map → oracle-strengthening loop.

## Prediction ledger (novel facts vs hits)

| # | prediction (when) | outcome | verdict |
|---|---|---|---|
| 1 | v1 receipts are self-certifying; 7 structural holes exist (07-23) | P1–P7 critique corroborated by design review; v2 built against each | hit |
| 2 | mutation scoring will expose oracle gaps floors alone miss (07-24) | weight_field 0/11 (shallow binding), learned_v3_additive 5/12 → F3/F4 gates → 8/12 | hit |
| 3 | harvester yields ceremony-free coverage (07-24) | 54/54 VALID on first full harvest | hit |
| 4 | vacuity map ranks the weakest tests (07-24) | first map: 50/50 all-zero — **refuted**: instrument bug, not suite (sys.path shadowing) | refuted→repaired |
| 5 | repaired map is stable | flaky kills 3/8↔4/8 — **refuted**: __pycache__ (mtime,size) poisoning | refuted→repaired |
| 6 | red files hide "values published, never asserted" gaps | traversal top-m selection, world_builder df-gate/hop counts, E1 golden reproduction, expB judge/spread behavior — all confirmed and strengthened (0→4/8, 5/5, 8/8, 6/8) | hit ×4 |
| 7 | qkv_b1 flip-flop is test nondeterminism | **refuted**: stable 0/8 locally (genuine guard-path vacuity); the 2/8 map entries were phantom kills under parallel load → kill-confirmation added | refuted→repaired |

## Problemshift verdict: PROGRESSIVE (so far)

Three times the measurement instrument falsified *itself* (#4, #5, #7), and
each repair increased content (col_offset site identity, pyc purge,
kill-confirmation) rather than patching with exceptions. The belt now
contains its own counterexamples in version control. Score: red files 7 → 2,
chain records 58, runner self-oracles 13 tests green.

## Degeneration risks (watch list)

- **R1 infinite self-measurement regress** — harness measuring harness
  forever. Mitigation so far: negative oracles at each layer; the regress
  stops where a layer's test would cost more than the claim it protects.
- **R2 ceremony creep** — harvest + map exist precisely to avoid per-claim
  hand work; if the strengthening loop costs >30 min/file routinely, the
  belt becomes OMD-shaped.
- **R3 manual equivalent-mutant classification** — currently judgment
  calls in commit messages; no machine record. Allowlist still missing.

## Next discriminating questions (falsifiable, ordered)

- **Q1 (instrument)**: with kill-confirmation, phantom-kill rate across a
  full map regen is <10% (else vacuity_map needs quarantine reruns).
- **Q2 (guard paths)**: qkv_b1's 8 first-site mutants all live in
  drift-detection guards; drift-injection fixtures (corrupted segment
  identity / qid dup / digest mismatch) kill ≥7/8.
- **Q3 (pattern)**: h3_title_anchor_falsifier survivors concentrate in the
  same guard class (identity/digest checks), not in scoring logic.
- **Q4 (audit)**: the first cross-model audit (different model family
  reviews a self-valid receipt) finds ≥1 issue self-validation missed.
- **Q5 (integrity)**: a deliberate chain-tamper fire drill is detected by
  the LakatoTree anchor mismatch on next harness run.

## Recommended sequence

1. Regen map with kill-confirmation (settles Q1; makes the map honest).
2. Guard-path fixtures for the 2 remaining red files (Q2, Q3).
3. Equivalents allowlist `mutation_allowlist.json` (closes R3).
4. First cross-model audit experiment (Q4 — activates the `audited` tier).
5. Tamper fire drill + anchor-mismatch assertion (Q5).
