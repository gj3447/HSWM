# OOPTDD mutation audit — "v22" record (A5 close) — DRAFT for HSWM writer session

> Arc: ooptdd POST_TIER1 front A5 (`/Users/lagyeongjun/CD/ooptdd/docs/POST_TIER1_ARC_HARNESS_2026-07-26.md`)
> Date: 2026-07-28 · Prepared by the A5 scout lane and independently re-measured by
> the A5 implementer pass (`a5_impl_transcript_2026-07-28.log`, same lane; every
> number below reproduced, all steps exit as expected). To be committed and chained
> by the HSWM canonical writer session. Intended home: GIT/HSWM repo root, next to
> `OOPTDD_AUDIT_POLICY_2026-07-24.md`.

## Premise correction (harness rule 4)

The A5 front text (drafted 2026-07-26) carried two stale premises:

1. **Cross-rail path**: it points at `/Users/lagyeongjun/CD/HSWM`, which is a frozen
   archive (2026-07-26 verdict). The live SSOT is `/Users/lagyeongjun/CD/SYMPOSIUM/GIT/HSWM`.
2. **"binop@92 dReLU gate-corruption mutant still unkilled" (8/12)**: that was the
   v2.1 audit state (2026-07-24 morning). The same day, receipt v2.7 added the F6
   train-path canary explicitly to kill binop@88.17 / binop@88.30 / binop@92.19; the
   cross-model audit (`receipts/audit_claude_code_cosine_floor_v27_20260724.txt`)
   verified all three are genuinely caught, and the chained records already show the
   climb: seq 58 = 6/12 → seq 60 (v2.7) = 9/12 → seq 62/63 (v2.7.1 / v2.8b) = 10/12.
   The harness doc was drafted from the v2.1 snapshot, two days behind its own rail.
   ("v21"/"v22" in the front text = receipt audit v2.1 → next audit; the receipt
   itself is at v2.8b.)

What was still genuinely open: `weight_field` 0/11 (source binding without actual
coverage). Confirmed still 0/11 on 2026-07-28 before the battery below.

## Measured state (2026-07-28, .venv python 3.11.15, confirm_kills=True)

Worktree shas at measurement (match chain seq 63 exactly — no drift):
`learned_v3_additive.py 200a953090db… · weight_field.py 29c9b95d4c8e… ·
receipts/receipt_cosine_floor.py 3f004be9feed…`

### learned_v3_additive vs receipt_cosine_floor (12 mutants)

- killed 10 / total 12 / **open gaps 0**
- 2 survivors are allowlisted equivalents (`receipts/mutation_allowlist.json`):
  - `binop@36.8 Sub->Add` — softmax constant-shift invariance (stability-only)
  - `cmp@65.12.0 Gt->GtE` — resid>0 vs >=0 measure-zero gate boundary
- The old binop@92 (dReLU gate, now `binop@65.11 Mult->Add` after the v2.7
  refactor into `_train_score_and_gate`) is **killed** (F6). Explicit GREEN/RED
  demonstration (implementer pass, transcript S3): pristine tree GREEN (exit 0,
  all 12 checks True) → that single mutant injected in place → RED (exit 1, F6
  alone flips to False: "train sc/gate match locked formulas -> FAIL") → source
  restored byte-identical (sha match True) → GREEN again (exit 0). This is the
  A5 front's requested negative oracle; no new test was needed because F6 IS the
  kill test (premise correction above).
- Honest 12/12 reading per the front's own escape clause ("or each exclusion named
  with reason"): 10 killed + 2 named equivalents = 12/12 accounted, 0 open gaps.

### weight_field battery (new receipt, 11 cells)

- Before: `weight_field` vs receipt_cosine_floor = **0/11** (all 11 survive; the
  receipt binds the sha but exercises only `_unit`).
- New `receipts/receipt_weight_field.py` (this lane's patch): one check per cell,
  expectations recomputed through independent implementations; positive run VALID;
  LOCK↔check binding `verified` by `ooptdd.run_receipt.verify_lock_binding`.
- After: `weight_field` vs the battery = **11/11 killed, 0 survivors, 0 exclusions**.
- Battery-level negative oracle (harness rule 2): +0.001 injected into the
  independent combine expectation → receipt INVALID (exit 1, W1/W5 False); restored.

## Steps the HSWM writer session still owns (scout did NOT do these)

1. Copy `receipt_weight_field.py` from the A5 scratchpad lane into
   `receipts/receipt_weight_field.py`.
2. Chain both records (appends to git-tracked `receipts/receipt_log.jsonl`):
   - `.venv/bin/python -m ooptdd.run_receipt receipts/receipt_weight_field.py --source weight_field.py --mutation-target weight_field.py --max-mutants 11`
   - `.venv/bin/python -m ooptdd.run_receipt receipts/receipt_cosine_floor.py --source learned_v3_additive.py --source weight_field.py --mutation-target learned_v3_additive.py --max-mutants 12`
   (optional LakatoTree anchoring via `--anchor-tree LakatosTree_HSWM_20260719
   --anchor-node d1-ooptdd-floor-scope-correction` — root-session verb.)
3. Commit this record + the receipt with pathspec-only staging (live f1 research
   lane shares the repo: untracked `_p1_lab/`, `receipts/f3*`, r6 monitoring loop
   in another session — do not `git add -A`).
4. ooptdd rail: drop the A5 closing receipt in `ooptdd/docs/receipts/` with
   `evidence_tier: local_pass` (+ audit-chain pointer), tick the A5 checkbox on
   issue #6, update the KG front node, and patch the A5 section of
   POST_TIER1_ARC_HARNESS with a premise-correction note (A9 precedent).
