# Runtime conformance progress view

This six-source read-only view selects current observations for T1–T9 while
preserving the immutable plan, replay, adapter, consolidation and preflight
snapshots. It is a research progress projection, not canonical learning state.

| Question | Query | Scope |
| --- | --- | --- |
| Current result and completion criterion | [current](current.rq) | Nine tasks; T1–T4 complete within the original plan criteria, not whole-runtime proof |
| T1 progression | [history](history.rq) | Five observations, exact predecessor UID plus REFERENCES and role/task at every hop |
| Direct source artifacts | [bindings](bindings.rq) | Thirteen artifacts at the recorded code revision |
| Evidence per new observation | [evidence](evidence.rq) | T1–T5; evidence role and exact byte hashes |
| Work with satisfied prerequisites | [next](next.rq) | No locally ready unfinished task; T5 awaits current serving configuration |
| Unfinished prerequisites | [blocked](blocked.rq) | Five dependency rows; T5's external serving gap appears in current.next |
| Actual same-run bytes and Lean exchange | [trace](trace.rq) | Retained synthetic fixture evidence with source revision; two journals remain separate |
| Original proof/efficacy ceilings | [boundaries](boundaries.rq) | PS-1–6, including prior negative findings |

T1 and T2 satisfy the original decoded-model, finite native comparison, and
explicit external-premise criteria. Universal implementation or crypto
refinement is not claimed. T3 completes the stated Linux/tmpfs process-crash
and race scope. T4 retains the actual same-transition bytes, Lean exchange and
recovered read-frame provenance; it does not turn two journals into one atomic
authorization transaction. T5 has no new model observations: the documented
local serving setup was not established. That does not prove all remote
alternatives are absent. T6–T9 retain their original experiment dependencies.

The code revision in the root and evidence nodes identifies code and validation
artifacts. This view, queries, tests and workspace manifest are a subsequent
publication and are pinned by their final byte hashes. The derived
[graph validation report](../../../docs/research/artifacts/hswm_runtime_conformance_2026-10-07/graph-validation.v1.json)
is outside the primary artifact bindings to avoid a hash cycle.

`progress` selects this view. `progress-2026-10-07-preflight` and
`progress-2026-10-07-consolidation` retain historical queries. Their historical
bindings are checked against their recorded publications, not rewritten to
pretend that the current manifest or code still has old bytes.
