# Generic Feedback Runtime — Minimum Completion Gate

> **Status:** normative implementation gate, not an efficacy claim.
>
> HSWM is not complete as an agent/world-model runtime until this vertical
> slice passes end to end.  New architectural concepts and broader research
> surfaces do not substitute for this gate.

## Cold assessment of the current repository

The repository already has useful substrate pieces:

- content-addressed immutable world artifacts in `world_ir.py` and
  `world_compiler.py`;
- immutable revision cuts and certified reads in `field_snapshot.py` and
  `certified_readout.py`;
- duplicate-immune deterministic folding for the restricted commutative
  supersession stream in `supersede_ledger.py`;
- a pure, idempotency-aware candidate reducer in
  `prom_search_hswm/hswm_absorption_fsm.py`.

Those pieces are not yet one generic feedback runtime.  In particular, the
current code has no generic agent attachment, proposal protocol, external
action executor, LakatoTree verdict port, durable ordered judgment/commit
stream, or dispatcher whose next action is causally changed by a verdict.
`readouts.dispatch()` is a score argmax, not an agent scheduler.  The
absorption FSM is experiment-specific, persists nothing by itself, and records
an `actor` string without enforcing a runtime authority boundary.  The
supersession ledger explicitly excludes the ordered judgment stream that this
gate requires.

## Required vertical slice

One generic agent must complete exactly this path:

1. attach to the runtime under a bounded agent capability;
2. read one version-pinned immutable causal cut;
3. submit one prediction/action proposal bound to that cut;
4. have an executor perform the action and return an external receipt;
5. have LakatoTree, under authority separate from the proposer, judge the
   proposal and observation;
6. commit the verdict to a new immutable cut and make that verdict change the
   next agent dispatch;
7. close the process, reopen durable state, replay the event stream, and
   reproduce the same cut, dispatch, and replay hash.

The implementation may use one canonical event envelope with six event kinds:

```text
ATTACH -> PROPOSE -> OBSERVE -> JUDGE -> COMMIT -> DISPATCH
```

Every event must bind at least:

```text
stream_id, sequence, request_id, kind, principal_id,
input_cut_id, causal_parent_ids, payload_sha256,
previous_event_sha256, event_sha256
```

The append-only event stream is authoritative.  Graph, field, and database
views are deterministic projections of that stream, not competing sources of
truth.

## Minimal implementation surface

Keep the first implementation deliberately small and in the repository's
top-level core rather than under an experiment directory:

| file | minimum responsibility |
|---|---|
| `feedback_runtime.py` | immutable event envelope, authority/phase guards, pure `fold(events)`, commit projection, and next-dispatch decision |
| `feedback_store.py` | SQLite append-only store, first-write-wins idempotency, conflict refusal, hash-chain verification, and ordered replay |
| `lakatotree_adapter.py` | map an observation to a LakatoTree judgment and bind the returned receipt to the proposal, observation, cut, and judge identity |
| `demo_feedback_runtime.py` | run the one-agent A/B vertical slice, restart the store, replay it, and emit the demo receipt |
| `tests/test_feedback_runtime.py` | causal A/B, phase, stale-cut, and authority tests |
| `tests/test_feedback_store.py` | duplicate, conflict, crash-recovery, tamper, and restart-replay tests |
| `tests/test_feedback_lakatotree.py` | recorded-contract test for the LakatoTree adapter plus an opt-in live integration check |

SQLite is sufficient for this gate.  Neo4j or a hypergraph-native database may
later serve projections or execution at scale, but no database migration is
allowed to block the first causal loop.

## Authority boundary

Authority must come from a trusted runtime context or adapter, never from an
unverified `actor` field supplied in event JSON.

| authority | permitted transition |
|---|---|
| agent/proposer | attach, read cut, propose |
| executor | execute and publish observation receipt |
| LakatoTree judge | judge only |
| committer | validate the complete chain and publish the next cut |
| dispatcher | read a committed cut and emit the next work item |

The same principal must not act as both proposer and judge for one stream.
Changing the payload to claim `actor="lakatotree"` must not grant judgment
authority.  A commit must refuse any missing, stale, unauthorized, or
hash-mismatched predecessor.

## Normative acceptance tests

### A. Verdict-to-dispatch causality

Run two isolated streams with the same initial cut, agent, proposal, executor
receipt, and dispatch policy.  Change only the judgment verdict:

```text
ACCEPT -> committed cut A -> next dispatch A
REJECT -> committed cut B -> next dispatch B
```

The test must prove all of the following:

- the event root through `OBSERVE` is identical in both streams;
- the `JUDGE` event is the first divergence;
- the resulting cut IDs differ;
- the next dispatch IDs differ;
- the commit causally references the judgment;
- the dispatch causally references the commit.

This is a mechanism test, not evidence that the chosen policy is scientifically
superior.

### B. Idempotency and conflicts

- same `request_id` and same canonical payload returns the original result;
- retrying it does not change event count, event root, cut, or dispatch;
- same `request_id` with a different payload fails closed;
- concurrent duplicate attempts append at most one event.

### C. Authority separation

- proposer cannot publish an observation, judgment, or commit;
- executor cannot judge;
- judge cannot propose or commit;
- committer cannot fabricate a missing executor or judge receipt;
- forged actor strings and altered receipt identities fail closed.

### D. Durable deterministic replay

- close the SQLite connection after the judgment and before the commit;
- reopen it and resume the commit exactly once;
- close and reopen again after dispatch;
- fold from the initial cut and reproduce bit-identical `event_root_sha256`,
  `final_cut_id`, `next_dispatch_id`, and `replay_sha256`;
- modifying any stored receipt byte makes verification fail.

### E. Stale and incomplete chains

- a proposal bound to a non-current cut is refused;
- observation without a proposal is refused;
- judgment without an external receipt is refused;
- dispatch before a committed verdict is refused.

## Completion receipt

Completion evidence is not prose.  A successful run must write
`receipts/feedback_runtime_vertical_slice_v1.json` containing at least:

```text
schema_version
initial_cut_id
agent_attachment_event_id
proposal_event_id
executor_receipt_sha256
lakatotree_receipt_id
judgment_event_id
commit_event_id
final_cut_id
next_dispatch_id
event_root_sha256
replay_sha256
replayed_after_restart
accept_branch
reject_branch
test_command
test_result
```

The checked-in receipt must be reproducible by `demo_feedback_runtime.py`; it
must not be a manually authored success declaration.

## Explicit deferrals

Until the acceptance tests and completion receipt pass, defer:

- advanced hypergraph optimization or a new storage backend;
- multiple agents, federation, and distributed consensus;
- UI and operator dashboards;
- additional KG mirrors;
- broader related-work or philosophical expansion;
- new learned routers, topology learners, and performance claims unrelated to
  closing this loop.

Existing research artifacts remain valid within their stated boundaries, but
they do not close this gate.

## Definition of done

The gate is complete only when all statements below are true:

1. the default test suite collects and passes the new `tests/test_feedback_*`
   files;
2. the A/B test changes the next dispatch by changing only the verdict;
3. duplicate, authority, stale-cut, crash-recovery, and tamper tests pass;
4. a real LakatoTree receipt is bound into the demo chain;
5. restart replay reproduces the exact terminal hashes and dispatch;
6. the generated completion receipt is checked in and independently
   verifiable.

Until then, the honest status is: **HSWM has an evidence-preserving world/read
substrate and research kernels, but not yet a generic continual feedback
runtime.**
