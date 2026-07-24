# OOPTDD v2 Design — Audited, Chained, Measured Receipts (2026-07-23)

> Implements the mitigations proposed in
> [`OOPTDD_CRITIQUE_2026-07-23.md`](OOPTDD_CRITIQUE_2026-07-23.md) (P1–P7).
> v1 kept: pre-run locked trace, real execution, positive readback, source
> binding, injected negative oracle. v2 adds: **status lifecycle, hash-chained
> receipt log, machine-extracted lock hashing, mutation-score field, Tier-3
> attestation with decay, and claim→receipt link enforcement.**

This document is the v2 contract. The reference implementation lives in
`ooptdd/` and is itself receipted: `tests/test_receipt_log.py` contains the
negative oracles for the chain (tamper and deletion must be detected).

## 1. Status lifecycle (P1 — self-certification)

```
draft  →  self-valid  →  audited
```

- `draft`: receipt written, not yet run to VALID.
- `self-valid`: receipt ran green locally; record appended to the chain.
- `audited`: an auditor **that is not the receipt author** (different agent
  session or human) attempted to break the LOCK within a declared budget and
  recorded the outcome as a new chain record of kind `audit` referencing the
  target record hash.

Rules:

- An audit record must state `budget` (wall-clock, mutant count, or counterexample
  attempts) and `auditor_id`. "Who audits" is thus explicit, and audit depth is a
  visible budget parameter, not a binary (the open question from the critique).
- README/EFFICACY claims may cite `self-valid` receipts only as ⚠️; ✅ requires
  `audited`. This is enforced socially until `verify_efficacy_claims.py` learns
  the check (§6).

## 2. Hash-chained receipt log (P4 — receipt mutability)

Every executed receipt run appends one JSON record to
`receipts/receipt_log.jsonl` (genesis `prev_hash = "0"*64`):

```json
{
  "seq": 0,
  "kind": "receipt",
  "receipt_id": "receipt_cosine_floor",
  "receipt_sha": "<sha256 of receipt source>",
  "source_shas": {"learned_v3_additive.py": "…", "weight_field.py": "…"},
  "lock_sha": "<sha256 of canonical JSON of the LOCK dict>",
  "verdict": "VALID | INVALID | ERROR",
  "exit_code": 0,
  "status": "self-valid",
  "mutation_score": null,
  "attestation": null,
  "timestamp": "2026-07-23T09:00:00+00:00",
  "prev_hash": "<sha256 of previous record>",
  "hash": "<sha256 of canonical JSON of this record minus 'hash'>"
}
```

Properties:

- **Append-only, fail-closed:** `append()` re-verifies the whole chain before
  writing; a corrupted chain refuses new appends (no silent continuation).
- **Post-hoc edits break the chain:** changing any past verdict, lock, or
  source sha invalidates every later `hash` link; deleting a record breaks
  `prev_hash`. Both are detected by `verify()` (negative oracles in
  `tests/test_receipt_log.py`).
- `kind` is `receipt` for claim runs and `audit` for auditor attestations
  (`audit` records carry `target_hash` of the receipt they judge).

## 3. Machine-bound locks (P3 — LOCK is prose)

Interim (implemented): the harness extracts the module-level `LOCK` dict from
the receipt source **via AST** (`ast.literal_eval`, no import side effects) and
hashes its canonical JSON into `lock_sha`. Prose drift between runs is then
visible in the chain; a lock edited after a VALID run produces a different
`lock_sha` on the next run, which the ledger diff exposes.

Target (future): locks become executable predicates (Hypothesis strategies);
prose is generated from the predicate. Receipts should migrate claim-by-claim;
`lock_sha` stays as the continuity anchor.

## 4. Measured oracles (P2, P7 — sensitivity ≠ correctness; manual re-invention)

- Record schema carries `mutation_score` (`{"killed": int, "total": int}`).
  Until an automated mutant generator is wired in, receipts must record at
  least one **domain counterexample** (an adversarial input from the problem
  space, e.g. an adversarial embedding configuration — not only a code mutant)
  in the LOCK under `negative_oracle`, as v1 already does for signed-j.
- v2.1 work: run mutmut/cosmic-ray against the module under test in CI and
  fill `mutation_score` mechanically; hand-written oracles shrink to domain
  counterexamples only.

## 5. Tier-3 attestation and decay (P6 — strong claims outside the gate)

Tier-3 runs (LLM/GPU/real corpora) append records with an `attestation` block:

```json
"attestation": {"pip_lock_sha": "…", "gpu": "…", "endpoint_fingerprint": "…",
                "prompt_shas": ["…"], "valid_until": "2026-08-22T00:00:00+00:00"}
```

A Tier-3 claim whose `valid_until` is past decays from ✅ to ⚠️ in the ledger
until re-attested. Decay enforcement lands in `verify_efficacy_claims.py`
(§6); the schema field exists now so new receipts can start attesting.

## 6. Claim→receipt link enforcement (P5 — atomization)

Every ✅ claim in README/EFFICACY must name at least one `receipt_id` present
in the chain with `status=audited`; ⚠️ claims must name a `self-valid` receipt
or an explicit non-claim note. Enforcement is a planned
`verify_efficacy_claims.py` extension (fail-closed when a declared receipt id
is absent from the chain). System-level behavior gets **composition receipts**
(one end-to-end run over a small fixed fixture) instead of one receipt per
micro-claim, bounding receipt-count growth.

## 7. Reference implementation map

| file | role |
|---|---|
| `ooptdd/receipt_log.py` | canonical JSON, hashing, append (fail-closed), verify |
| `ooptdd/run_receipt.py` | harness: AST lock extraction, source shas, subprocess run, chain append |
| `tests/test_receipt_log.py` | chain roundtrip + tamper/deletion negative oracles |
| `receipts/receipt_log.jsonl` | the append-only chain (created on first harness run) |

Usage:

```bash
uv run python -m ooptdd.run_receipt receipts/receipt_cosine_floor.py \
  --source learned_v3_additive.py --source weight_field.py
uv run python -c "from ooptdd.receipt_log import verify; ok, errs = verify('receipts/receipt_log.jsonl'); print(ok, errs)"
```

## 8. Non-goals / open questions

- v2 does not make receipts independently *true*; it makes them **expensive to
  fake and cheap to audit**. Truth still comes from the adversarial process.
- Auditor assignment/rotation and budget calibration are open; the schema
  records `auditor_id`/`budget` so policy can evolve without format changes.
- Cross-machine anchoring (e.g. periodically committing the chain head hash
  into LakatoTree as a verdict receipt) is desirable and deliberately left to
  a separate proposal.
