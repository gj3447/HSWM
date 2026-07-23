# Generic Feedback Runtime — G1 Acceptance Contract

## Scope and boundary

This vertical slice is a generic `L_RT` feedback kernel. It owns one immutable,
per-stream chain:

`ATTACH → PROPOSE → OBSERVE → JUDGE → COMMIT → DISPATCH`

The kernel has no LakatoTree, HSWM, scientific-progress, or domain-model
dependency. `JudgmentPort` means an injected operational evaluator. It is not a
scientific judge and the runtime does not claim that a verdict establishes
truth, progress, efficacy, or self-correction.

## Accepted invariants

1. Commands carry a trusted `CapabilityContext`; payload fields such as `actor`
   never grant authority. The HMAC proof binds authority, stream, principal,
   and exact role.
2. A stream binds each role to one principal, and one principal cannot occupy
   multiple stream roles in v1. In particular, proposer and judge are distinct.
3. Each event records the input cut, exact ordered causal parents, canonical
   payload digest, prior-event digest, and full-envelope digest.
4. Canonical JSON is UTF-8 with sorted keys, compact separators,
   `ensure_ascii=False`, and `allow_nan=False`.
5. `decide`, `evolve`, and `fold` are pure. Invalid phase, stale cut, wrong
   parents, forged capability, or malformed receipt causes rejection without an
   authoritative append.
6. Request idempotency is first-write-wins. An exact retry returns the recorded
   event; the same `(stream_id, request_id)` with different intent conflicts.
7. `ACCEPT` and `REJECT` first diverge at `JUDGE`. Both produce a verdict-bound
   final cut; dispatch routes are respectively `integrate` and `revise`.
8. Adapter ports receive a pinned cut and idempotency key. Adapter effects stay
   outside the reducer.

## Durability and recovery

`SQLiteFeedbackStore` is the single durable writer. It uses `BEGIN IMMEDIATE`,
a `(stream_id, sequence)` primary key, a unique request key, WAL journaling,
and `synchronous=FULL`. Every read verifies canonical bytes, duplicated SQL
columns, recomputed request intent, the full hash chain, exact transitions, and
the pure fold. Ordered replay reconstructs the same projection after a normal
process restart or a transaction rollback.

This slice does **not** claim proof against abrupt power loss, filesystem or
storage-controller lies, hostile full-database rewriting, distributed
single-writer consensus, external exactly-once delivery, or adapter-side effect
recovery. The loop contract specifies intent/reconciliation control for a later
outer dispatcher; that dispatcher is not implemented here.

## Acceptance evidence

- Runtime tests cover ACCEPT/REJECT divergence, verdict-dependent cut/route,
  capability and role separation, forbidden phases, stale cuts, wrong parents,
  idempotent retries, conflicts, and the `JudgmentPort` narrow waist.
- Store tests cover WAL/FULL settings, ordered replay across reopen, byte and
  duplicated-column tampering, request-hash tampering, retry-path chain
  corruption, and two-writer races.
- `engine_spec.v1.json`, `fsm_spec.v1.json`, `fsm_traces.v1.json`, and
  `loop_contract.v1.json` are validator inputs, not user canon.
