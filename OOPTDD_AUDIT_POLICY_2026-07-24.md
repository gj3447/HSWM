# OOPTDD Audit Policy — Assignment, Rotation, Budget (v2.6, 2026-07-24)

> Closes the policy half of the v2 open question
> ([`OOPTDD_V2_DESIGN_2026-07-23.md`](OOPTDD_V2_DESIGN_2026-07-23.md) §8,
> KG `ooptdd-v2-auditor-budget` on `LakatosTree_HSWM_20260719`).
> v2.5 (`ooptdd/audit.py`) gave the audit *workflow*; v2.6 answers **who may
> audit next, with what minimum budget** — and refuses policy-violating audits
> before they reach the chain. Fail-closed, like `receipt_log`.

## Rules

| rule | what | enforcement |
|---|---|---|
| **R1 no-self-audit** | `auditor_id` ≠ receipt's `author_id` | **hard** — a self-audit `upheld`/`broken` is refused (`PolicyRefusal`). Receipts record `author_id` via `run_receipt --author` / `OOPTDD_AUTHOR`. Receipts without one degrade honestly: the audit chains with `policy.no_self_audit = "unverifiable"` |
| **R2 rotation** | `next_assignment` picks the eligible auditor with the oldest last-audit (never-audited first, ties by `auditor_id`) | **advisory** — deterministic (same chain → same answer), not a gate; auditor availability is social, hard-gating deadlocks. Registry: `receipts/auditors.json` |
| **R3 budget calibration** | base `{mutants: 10, counterexamples: 20, wall_clock_min: 30}`; every `broken` audit on the same receipt **doubles** the minimum (cap ×8) | **hard for structured budgets** — an `upheld` below the calibrated minimum is refused (ceremony is not chained). A `broken` verdict is **always** chained: falsify needs no budget. Free-text budgets chain flagged `policy.budget_check = "unverifiable"` |

Progressive enforcement (house pattern, cf. `lock_binding: absent`, `derived_self`
demotion): what the machine can see, it enforces; what it cannot, it flags as
`unverifiable` in the chained record — never silently trusted.

## Usage

```bash
# receipt side — record the author so R1 can see it
.venv/bin/python -m ooptdd.run_receipt receipts/receipt_cosine_floor.py \
    --source learned_v3_additive.py --author kimi-code

# auditor side — registry + rotation + calibrated minimum
.venv/bin/python -m ooptdd.audit_policy register --auditor-id claude-opus-4.5 --kind agent
.venv/bin/python -m ooptdd.audit_policy assign receipts/receipt_cosine_floor.py
.venv/bin/python -m ooptdd.audit_policy budget receipts/receipt_cosine_floor.py

# record — structured budget is machine-checked; a break always chains
.venv/bin/python -m ooptdd.audit record receipts/receipt_cosine_floor.py \
    --auditor-id claude-opus-4.5 --verdict upheld \
    --mutants 12 --counterexamples 20 --minutes 35 --notes "no break found"
```

Every audit record now carries a `policy` block:
`{no_self_audit, budget_check, budget_min, budget_factor, assigned}` — the
assignment that was live when the audit chained.

## Files

| file | role |
|---|---|
| `ooptdd/audit_policy.py` | registry, rotation, calibration, `enforce`/`record_audit`, CLI |
| `ooptdd/audit.py` | `record()` delegates to the enforced path; `--mutants/--counterexamples/--minutes` |
| `ooptdd/run_receipt.py` | `--author` / `OOPTDD_AUTHOR` → `author_id` on receipt records |
| `receipts/auditors.json` | auditor registry (idempotent `register`) |
| `tests/test_audit_policy.py` | 11 negative oracles: self-audit/under-budget refusal, break-always-chains, escalation ×2 cap ×8, LRU rotation determinism, corrupt-chain refusal |

## Non-goals / open

- Cross-machine chain-head anchoring already lives in
  `run_receipt.anchor_chain_head` (precedent: KG event
  `ooptdd-chain-head-receipt_cosine_floor-seq3`, 2026-07-24) — untouched here.
- Rotation is deliberately advisory; making assignment a hard gate needs an
  auditor-availability protocol first (deadlock risk otherwise).
- `who audits the auditor` regresses one level up: budget escalation makes
  rubber-stamping progressively more expensive, but no mechanism proves an
  auditor *tried*. That remains the adversarial process's job.
