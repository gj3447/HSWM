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

The initial 2026-10-24 version provides local logical task scopes and automatic refresh on use.
It does not provide separate-host replication, distributed transactions, A2A
transport, autonomous Internet search/subscriptions, or semantic sufficiency
judgment. Its open gaps feed the acquisition extension below. The shared
native journal still performs global recovery/commit validation; semantic locality
is not a claim of constant-time storage access or process-level confidentiality.

## Public evidence acquisition and agent handoff — 2026-10-26

Implementation: `evidence-acquisition-{domain,http,runtime}.ts` in the Effect
runtime. This increment connects an exact open working-context gap to a bounded
public read, source admission and task-context extension. It also shares the
original source relation with another local agent context. It does not introduce
a second database or imply separate-host replication.

`decideEvidenceAcquisition` takes an explicit task assessment and distinguishes
`USE_CURRENT`, `LOCAL_READ`, `FETCH_SOURCE`, `SEARCH_EXTERNAL`, `REVALIDATE`,
`ASK_HUMAN`, `DIAGNOSE_REASONING` and `DEFER`. Private preferences require human
input; reasoning failures do not automatically cause more searching. When the
caller supplies `maximumAgeMs`, `acquireEvidence` automatically revalidates an
older cached representation, even if its previous assessment was sufficient.
This is representation freshness, not verification that its claims remain true.
Semantic sufficiency is a caller assessment, not an automated entailment judgment.

The initial search adapter is **Crossref scholarly metadata search**, capped at
three hits. It preserves DOI, title, publisher and locator. It does not search the
whole web or count a search hit as a read of the paper. A known source can be read
as complete UTF-8 text. The HTTP reader caps response bytes and duration, rejects
redirects, binary/invalid UTF-8 and incomplete reads, and forwards no credentials.
Every network step requires caller-selected project/resource/link, purpose,
recipient, exact allowed URLs, expiry/revocation and public-query scope. Private
task memory is never converted into a search query by this adapter. Returned
locators do not expand that scope.

`acquireWorkingContextEvidence(runtime, contextKey, need, access, previousKey,
writer, ports)` performs one gap-bound step. `ports.fetch` is the caller's HTTP
transport, `ports.now` its clock, and `ports.admit` the existing native owner
writer. It reads back the admitted source and context. Each result carries
`nextBudget`: successful requests consume one unit; identical content, empty
results or repeated DOI hits count as no progress. Two such rounds or exhaustion
yield `DEFER`, never a claim that the missing fact does not exist. Errors stop the
step without retries; a supervisor must count failed dispatches against its own
overall attempt budget. There is no autonomous daemon or subscription loop.

Each observation preserves the URL-based source ID, complete body hash, media
type, fetch-completion time, HTTP status and validators. Search responses remain
`SEARCH_METADATA`; originals are `SOURCE`. Both retain `truth: NOT_EVALUATED`
and `sufficiency: NOT_EVALUATED`. HTTP 304 requires the same cached URL and a
matching validator; it reuses the original bytes. The source relation advances
when its observation metadata changes, including a new validation time. A 304
can therefore stale a dependent context without changing the body hash.

`prepareEvidencePublication` produces a native owner proposal. After genesis,
new evidence must cite its admitted task/source predecessor; the native engine
rejects any attempt to reopen bootstrap. Bodies over the existing native role
limit of 65,536 bytes refuse admission rather than being truncated. Identical
observations are reused; older observations, conflicting identities and another
owner's binding refuse. Immutable roles retain their original provenance.

`prepareWorkingContextExtension` adds complete mandatory frames while retaining
existing rules and unresolved gaps. New scope uses the existing policy-family
rules; it does not copy incompatible W. `prepareWorkingEvidenceHandoff` requires
the sender's exact current source dependency and proposes the same source root
for the recipient. Repeated and return handoffs are no-ops. Neither copies the
sender's sufficiency judgment, closes a gap, creates an independent corroborating
source, nor trains W. Separate URLs can still be mirrors of one original: that
cross-URL provenance/semantic assessment remains the caller's responsibility.
Subsequent model use follows `executeWorkingContextLoop` and its existing
automatic outcome-bound W path.

Source admission and context attachment are separate owner transactions. If a
context write races or fails, the admitted source survives, while the function
refuses to claim successful attachment. Reopen the task and explicitly attach or
refresh that source; do not infer exactly-once external delivery. The native
journal remains the final admission and stale-writer boundary.

The transport semantics follow [Crossref's REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)
and [RFC 9111 validation](https://www.rfc-editor.org/rfc/rfc9111.html#section-4.3).
The live read used the complete original [RFC 5861](https://www.rfc-editor.org/rfc/rfc5861.txt).

### Verification and remaining completion gate

The live read-only check on 2026-10-26 made three real public GETs: Crossref
returned DOI `10.17487/rfc5861`, RFC Editor returned 10,359 bytes, and conditional
revalidation returned 304 with the same body SHA-256
`1193f1c8710af162e1b9fb4250d79bc6dd26497df4caeeaaa8bcb2fefdd2529e`.
This proves that transport path only; no model call or W update was performed.

**10 focused tests passed; one file-journal test remains unexecuted.** Tests use
the existing native memory layer for source admission, gap binding, owner
readback, handoff deduplication, observation successors and selective refresh.
Transport cases cover scope/expiry refusal, time/byte limits, UTF-8, HTTP failures,
conditional validators, automatic age-based refresh and repeated hits. The
initial native test correctly rejected bootstrap after genesis; publication now
requires a task/source predecessor. The successor test exceeded Vitest's default
five seconds and passed with the documented 30-second limit.
The full read-only `npm run check`, runner syntax check, Markdown math compilation
and whitespace validation passed. The checks used Node 24.20.0, Effect 3.22.1 and
Vitest 3.2.7. These results include the current checkout's unrelated native-runtime
edits; isolated committed-source validation remains part of the capacity-dependent
verification, not an already established result.

The managed runner refused the build/disk test job because the host thin pool
was critical (98.19%, later 98.24%). Read-only type checking, memory-only tests
and live public reads are separate from the unexecuted disk check.
**Do not claim this increment's disk persistence or fresh-process live integration
complete until the following managed checks pass.** The earlier 2026-10-24
working-context/model result remains separate evidence.

After capacity recovery, run the runtime's `npm run check`, `npm run build`, and
focused `evidence-acquisition.test.ts` / `working-context.test.ts` with a 30-second
test timeout under `proxmox-scratch`. Use managed memory scratch for native
filesystem tests, as documented above. Then run:

```sh
node _research/agent_working_context_v1/evidence.mjs run NEW_PRIVATE_ROOT
node _research/agent_working_context_v1/evidence.mjs check NEW_PRIVATE_ROOT
```

The bounded runner uses at most three public GETs, creates an isolated native
journal, hands the source to a peer, checks duplicate and return handoffs,
revalidates, refreshes only dependents and reads the peer from a fresh OS process.
The `check` command independently consumes its private `result.json` and native
source/context records. The runner's full execution is pending the capacity gate;
its source is a reproducible verification path, not a claim that it has passed.
