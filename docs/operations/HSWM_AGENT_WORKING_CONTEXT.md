# Agent working context as a local HSWM

2026-10-24 · implementation/design: `agent(codex) / SECONDARY_AI`.

The consumer keeps task memory as a native `working_context` relation with exact
source/role dependencies and a shared activation-policy reference. Task contexts
and shared knowledge are logical subgraphs in **one existing native journal**.
The LLM input is a bounded projection of persisted memory plus selected complete
semantic frames. This implements the smallest useful bidirectional loop; it does
not install a second graph engine or a background multi-agent service.

## Completion contract

1. A fresh OS process recovers the goal, constraints, completion criteria,
   progress, unresolved gaps and exact source revisions without chat history.
2. A source correction makes only dependent contexts stale. Refresh preserves
   history, updates their references, and reopens gaps whose evidence changed.
3. An observed execution outcome enters the existing activation/owner path.
   The learned shared policy and the task's completed-run record commit together;
   another task/process reads that revision on its next selection. Replaying the
   same run must not execute or learn twice.

Model quality, source truth and transport success remain separate from these
integration checks. Scripted tests do not establish real-model execution or
generalization. A nonzero model revision alone does not establish useful learning.

## Consumer API

Implementation: `src/hswm/effect-runtime/src/working-context-{domain,runtime,process}.ts`.
Add `workingContextKind(allowedOwners)` to a **new** schema/journal, or use the
owner's schema-migration path. Never rewrite an existing schema binding in place.

```ts
const created = yield* prepareWorkingContextCreation(runtime, {
  agentId, taskId,
  memory: { goal, constraints, completionCriteria, progress, gaps },
  spec, // existing ContextSpec: required roots, scoped candidates, byte budget
  policyFamily: { lineageId, atomUid, config } // existing activation encoder/config
}, target)
yield* owner.admit(created)

const result = yield* executeWorkingContextLoop(runtime, created.contextKey, {
  runId, mode: "TRAIN", cell, featureValues, presentation: "execution_tail"
}, writerContext, {
  http,
  evaluate, // observed outcome -> reward/null, observed, source, continue
  admit: proposal => owner.admit(proposal)
})
```

The caller supplies an existing authorized owner adapter. No function grants
authority, submits to a KG, changes another owner's source, or invents an external
reward. Normal use calls the loop; it does not add a separate manual W update.

- `openWorkingContext`: explicitly recover the latest revision of a stable ID.
  Use the returned exact key for subsequent writes. `readWorkingContext` requires
  the exact current revision and refuses stale clients.
- `prepareWorkingContextRefresh`: derive an owner proposal, or `null` for no
  change. Execution invokes this automatically at its boundary. There is no
  background broadcast; a caller can also invoke it when a source event arrives.
- `prepareWorkingMemoryUpdate`: persist user corrections/progress. Resolved gaps
  require current, exact dependency keys. This validates provenance coverage,
  not semantic sufficiency or the truth of a caller's assessment.
- `executeWorkingContextLoop`: reserve one durable run, invoke the existing
  activation loop, and atomically publish policy plus task completion. Shared
  policies are scoped by family, owner, encoder/config, source revisions,
  candidate roles and preservation contract. New source scope gets a new policy;
  old weights/history survive without unsupported numerical transfer.
- `prepareWorkingContextReconciliation`: explicitly record an uncertain pending
  attempt as `UNKNOWN`, with observed/source attribution. It can retain stale
  references for later refresh. This never invents success or updates W.

Run identity is `(context identity, runId)` and binds the exact original request.
A repeated identical completed run returns `REPLAYED`; conflicting reuse refuses.
An interrupted/evaluation-failed/owner-rejected attempt remains `PENDING` and is
not retried. Explicit reconciliation permits a new run ID; the old uncertain ID
stays non-replayable. This is conservative duplicate suppression, not exactly-once
external side effects. The existing journal rejects competing stale writers.

Dependencies retain original keys, owners and content descriptors. A round trip
does not create another source or independent corroboration. If a participant
has advanced but its source relation still binds the old participant, refresh
refuses until the source owner repairs that relation. Required exceptions and
roles are never dropped to fit a prompt. Byte-limit overflow is a refusal.

## Recovery command and bounded execution check

```sh
src/hswm/effect-runtime/bin/hswm-working-context --help
node _research/agent_working_context_v1/run.mjs --help
```

The recovery command takes one JSON request on stdin: `contract:
hswm-working-context-cli/v1`, `action: open|select`, an existing `durableRoot`,
`journalLineageId`, full pinned `schema`, and `contextKey`. `select` additionally
takes `featureValues`; it reports the current policy key and complete assembled
frames without HTTP or graph admission. Source drift refuses selection.

The bounded runner's `prepare NEW_PRIVATE_ROOT PRIVATE_CELL_JSON` creates three local task scopes
and an **unapproved** access proposal. `run ROOT` requires existing owner-approved
project/provider scope and performs one actual source-heading model call, a
fresh-process learned-policy selection, replay suppression, and selective source
refresh. `check ROOT` independently rereads persisted memory, trace, feedback and
policy linkage. Raw inputs/results remain private; commands regenerate checks.
The private cell supplies the existing vLLM `base_url`, `model` and `max_tokens`;
the diagnostic does not forward credentials. The general runtime accepts the
existing caller transport. The local source correction is an authored integration probe, not a change to
human canon or the original source document.

## Verification and practical limits

Run `npm run check` and `npm run build` in `src/hswm/effect-runtime`, then focused
Vitest files `working-context.test.ts`, `semantic-context-activation.test.ts`, and
`semantic-context-traversal.test.ts` from `tests/effect-runtime`.
Use the managed runner and a bounded local POSIX scratch filesystem where required.
The first bulk-scratch run failed in native immutable-content publication; the
same checks ran on managed tmpfs without weakening file or journal guarantees.

`npm run check`, `npm run build`, and **19 tests in 3 files passed**. Automated
cases cover persistence, scoped refresh, shared policy use, duplicate
runs, competing writes, rejected joint admission, uncertain outcomes, AUDIT,
null rewards and invalid gap evidence.

The bounded live check made **one real model call**, reproduced the selected
source's exact heading (reward 1), and admitted policy revision **0 → 1** together
with task completion. A different task in a fresh OS process used revision 1.
The repeated run returned `REPLAYED` without another call or state change. A local
source-rule successor made dependent contexts stale; the refreshed worker reached
revision 3 while the unrelated task remained at revision 0. The fresh-process
read preserved the goal, constraints, criteria, progress and open gap.
The independent checker reread the old/new neural parameters and recomputed the
fresh-process scores: `extract` changed from 0.4713819 to 0.4958019. These are
gate scores, not calibrated probabilities or a generalization measurement.

Private evidence is in `.hswm-local/agent-working-context-2026-10-24/`; the
`result.json` is consumed by the runner's `check` command. Native trace and outcome
descriptors resolve to content stored in that journal. No source/implementation
snapshot or raw model output is committed. These are integration observations
on one source-heading task, not a natural-task learning benchmark.

This version provides local logical task scopes and automatic refresh on use.
It does not provide separate-host replication, distributed transactions, A2A
transport, autonomous Internet search/subscriptions, or semantic sufficiency
judgment. Open gaps are durable inputs to a future acquisition policy. The shared
native journal still performs global recovery/commit validation; semantic locality
is not a claim of constant-time storage access or process-level confidentiality.
