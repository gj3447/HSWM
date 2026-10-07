# Native preflight refinement progress

This is a source-bound follow-up view over the immutable 2026-10-07
consolidation and the earlier plan, replay, and adapter snapshots.  The new
primary view owns only its selectors, two new T1/T2 observations, and its
direct source artifacts.  Original tasks, prior observations, claims,
decisions, and the 39 historical source occurrences stay in their source
bundles.

The source revision `f2de5c0c830fd9e5d8642d6bf41f01445cdc0518` identifies
the eight code and evidence artifacts.  This graph view, its queries, tests,
and workspace manifest are published in a later commit and are pinned by
their final byte hashes; the source revision is not their publication revision.

| Question | Query | Expected scope |
| --- | --- | --- |
| What is selected now? | [current](current.rq) | T1–T9, all `OPEN`; T1/T2 reflect this refinement view |
| How did T1 reach this state? | [history](history.rq) | Four exact observations, orders 0–3 |
| Which new artifacts support it? | [bindings](bindings.rq) | New source-bound artifacts only, at one code revision |
| Which evidence belongs to T1 or T2? | [evidence](evidence.rq) | Direct theorem, runtime, test, and report sources by task |
| What can proceed? | [next](next.rq) | T1 and T2 only; absent or incomplete prerequisites block work |
| Did the proof and efficacy ceilings change? | [boundaries](boundaries.rq) | PS-1–6 retain their original decision boundaries |

`bindings` does not repeat the older 39 occurrence bindings.  Use the
historical `progress-2026-10-07-consolidation` workspace entry for that
reviewed selection and its historical pin states.

[Graph validation record](../../../docs/research/artifacts/hswm_native_preflight_refinement_2026-10-07/graph-validation.v1.json)
records the final composite projection, query, and SHACL checks.  It is linked
as a derived validation report and is intentionally excluded from this
primary bundle's artifact bindings, so the report cannot create a hash cycle.

The view is a read-only standard-graph projection.  It does not prove whole
runtime refinement, canonical authority, signatures, time, nonce persistence,
POSIX publication, external outcome truth, causal credit, or LLM efficacy.
