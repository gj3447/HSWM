# Shared field vs separate heads

Status: **DESIGN_LOCKED_NOT_PREREGISTERED**.

This folder turns GitHub issue #1 into one narrow, falsifiable comparison:

> Can one versioned semantic weight field serve retrieval, independent
> selection, and knowledge revision better than separate task-specific heads
> under the same measured budget?

The distinction matters. Today `retrieve()` and `selection_distribution()` read
one score vector, but `plan()` is only a compatibility alias and `supersede()`
applies a write chosen elsewhere. Shared storage or shared scoring alone cannot
win this trial. The selection task must require an independent cost/risk action,
and the revision task must include contradictions, stale facts, as-of queries,
repeated revisions, and confluence.

## The narrow waist

- `manifest.v1.json` names eight candidate arms, three tasks, budget dimensions,
  capped resources, metrics, success paths, attribution, and claim boundary.
- `verify_contract.py` checks the mechanism baseline, verifier bytes, and one
  digest over every experimental meaning. Protocol v1 refuses every run: a
  caller-supplied `equal_budget=true` or hash-shaped placeholder has no authority.
- `test_verify_contract.py` injects self-reported budget parity, altered task and
  arm semantics, fake registration, source/protocol conflation, result leakage,
  and duplicate JSON keys.

The current manifest is intentionally not run-admissible. Before any measurement
it still needs:

1. an external LakatoTree prediction receipt;
2. a neutral exact-replay receipt and full-candidate score pack;
3. frozen dataset, split, query, candidate, model, topology, revision-stream,
   and evaluator hashes; and
4. executable arms and independent selection/revision tasks, event-ledger-derived
   counters, a parameter inventory, per-task and per-split parity, numeric
   resource caps, cost-equivalence rules, and a complete statistical plan.

## Legacy supersession warning

`readouts.supersede()` is retained only for historical measurement replay. Its
in-place multiplicative update is non-idempotent: the injected negative oracle
`tests/test_supersede_confluence.py::test_t2_negative_oracle_legacy_path_does_corrupt_on_double_apply`
demonstrates squared-decay corruption after duplicate delivery. New durable
writes must use the G-Set CRDT event fold in `supersede_ledger.py`.

This warning deliberately lives outside the byte-locked mechanism sources.
Changing a v1 mechanism byte requires a new reviewed protocol version; a
documentation-only warning does not silently rebaseline that design lock.

Those additions require a new, reviewed protocol version; filling nulls or
changing the status string cannot promote v1. Only that later version may become
`PREREGISTERED_UNRUN`. Contract or provenance failure yields `VOID`, not a
negative scientific result. A valid future run can support the shared field only
through quality gain under a v2-registered cost-equivalence rule, or quality
non-inferiority plus materially lower cross-port inconsistency and stronger
audit/replay behavior.
Otherwise the claim is rejected or narrowed.

LakatoTree owns registration, receipts, and scientific verdicts. HSWM owns the
mechanism under test. This folder contains no result, winner, efficacy,
production, or novelty claim.
