# Evidence lifecycle

Research artifacts keep their operational kind at the top level so existing
resolvers and receipts remain valid:

```text
prereg/ -> manifests/ -> evidence/ -> results/ -> receipts/
```

These are evidence roles, not rigid neural layers. A path may also belong to a
field, learning, runtime, or evaluation concept in the repository ontology.

The SWM-0W-S2S TypeScript/Effect handoffs are local, machine-readable
engineering checkpoints:

- [`v1 historical control-core checkpoint`](HSWM_SWM0W_S2S_EFFECT_HANDOFF.v1.json)
  records the user-directed runtime boundary and the pre-adapter state.
- [`v2 historical bounded-adapter checkpoint`](HSWM_SWM0W_S2S_EFFECT_HANDOFF.v2.json)
  records the bounded GitHub, artifact, exact-round drand, and Python execution
  adapters plus the still-open provenance/composition/workflow/finalizer gates.
- [`v3 historical authority checkpoint`](HSWM_SWM0W_S2S_EFFECT_HANDOFF.v3.json)
  records request-distinct GitHub receipts, the runtime-authentic
  registration-B capability, and the still-open current-run,
  composition/workflow/evidence-envelope/finalizer gates.
- [`v4 historical invocation-authority checkpoint`](HSWM_SWM0W_S2S_EFFECT_HANDOFF.v4.json)
  records the exact workflow identity/stage contract, strict process-local
  current-invocation authority, conditional source-workflow-row inspector, and
  the still-open workflow-source, unique-run, run/stage, envelope, and
  finalizer gates.
- [`v5 historical observation-authority design checkpoint`](HSWM_SWM0W_S2S_EFFECT_HANDOFF.v5.json)
  freezes the next strict TypeScript/Effect implementation contract for
  standalone raw-byte observation recomputation, the exact bounded
  workflow-runs-for-head query, and the separation between multiplicity
  observation, GitHub origin, and unique-run authority.
- [`v6 historical observation implementation checkpoint`](HSWM_SWM0W_S2S_EFFECT_HANDOFF.v6.json)
  records lazy run/jobs/list revalidation and the exact multiplicity-preserving
  workflow-runs-for-head observation as engineering-clear for retained-byte
  consistency. It explicitly does not establish GitHub origin or unique
  current-run authority, and production issuance remains fail-closed while
  workflow source bytes are absent.
- [`v7 historical run-authority implementation checkpoint`](HSWM_SWM0W_S2S_EFFECT_HANDOFF.v7.json)
  records authentic registration/invocation cross-binding, the exact four-read
  current-run acquisition/revalidation path, stage/job policy, capability
  containment, and a closed production Layer graph. Positive verification is
  non-authorizing under an injected observer; production issuance remains
  closed while workflow bytes and API path policy are OPEN, so GitHub origin and
  a genuine current-run capability are not claimed.
- [`v8 historical stage-artifact permit implementation checkpoint`](HSWM_SWM0W_S2S_EFFECT_HANDOFF.v8.json)
  records fixed zero-identity stage Effects, authority-derived atomically spent
  permits, one seeded bounded request/receipt ledger, fresh run/job/artifact
  validation, and independent candidate reread. Production remains dormant
  while workflow bytes and API path policy are OPEN; its one-use claim is only
  for one trusted process/module identity slot, not durable replay prevention.
- [`v9 historical durable-evidence substrate checkpoint`](HSWM_SWM0W_S2S_EFFECT_HANDOFF.v9.json)
  records canonical predecessor-linked stage envelopes, bounded content
  objects, and create-only B/stage claim anchors on one caller-provisioned
  shared POSIX root. It is structural durability only: complete replay
  attachment profiles, closed stage programs, upload postconditions, external
  storage wiring, and the terminal finalizer remain OPEN.
- [`v10 historical replay-prerequisite checkpoint`](HSWM_SWM0W_S2S_EFFECT_HANDOFF.v10.json)
  records the pinned production protocol asset, selector-free current-run and
  partial registration replay projections, exact drand-pulse retention, Python
  peak-RSS telemetry, coherent response/output caps, and the exact top-level
  healthy-success rosters. Nested replay semantics, complete source/read
  snapshots, failure/VOID profiles, closed stage programs, upload
  postconditions, external storage, and the finalizer remain OPEN.
- [`v11 historical lookup-trace/shared-Layer checkpoint`](HSWM_SWM0W_S2S_EFFECT_HANDOFF.v11.json)
  records complete bounded raw observation retention for successful poll-one,
  poll-two, and poll-three artifact lookup, plus one closed Effect Layer graph
  that, within one build, shares a single current-run service between replay
  and fixed reads while preserving the legacy read-only Layer signature. A
  durable stage-read replay is still OPEN: its 16 MiB profile and 64 MiB
  envelope cap cannot contain the 75 MiB worst-case candidate read before
  framing.
- [`v12 current stage-read replay-core checkpoint`](HSWM_SWM0W_S2S_EFFECT_HANDOFF.v12.json)
  records the frozen two-member stored-ZIP representation, exact
  12,583,176-byte profile cap, strict unknown-input reconstruction, source-chain
  and permit cross-bindings, and candidate FIRST/REREAD current-receipt plus
  ledger-prefix validation. This is a bounded structural core only: recovered
  getters/readers, the full hostile and every-phase matrix, production stage
  emission, external durability, and GitHub origin remain OPEN. Continue from
  [`HSWM_SWM0W_S2S_STAGE_READ_REPLAY_CORE_IMPLEMENTED_NEXT_SESSION_2026-08-23.md`](../../docs/operations/HSWM_SWM0W_S2S_STAGE_READ_REPLAY_CORE_IMPLEMENTED_NEXT_SESSION_2026-08-23.md).

They are explicitly not preregistrations, scientific evidence verdicts, HSWM
runtime graphs, or remote Neo4j publications. v12 supersedes v11 only as the
next-session entrypoint; v1 through v11 remain immutable historical
projections.
