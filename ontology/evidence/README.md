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
- [`v6 current observation implementation checkpoint`](HSWM_SWM0W_S2S_EFFECT_HANDOFF.v6.json)
  records lazy run/jobs/list revalidation and the exact multiplicity-preserving
  workflow-runs-for-head observation as engineering-clear for retained-byte
  consistency. It explicitly does not establish GitHub origin or unique
  current-run authority, and production issuance remains fail-closed while
  workflow source bytes are absent.

They are explicitly not preregistrations, scientific evidence verdicts, HSWM
runtime graphs, or remote Neo4j publications. v6 supersedes v5 only as the
next-session entrypoint; v1 through v5 remain immutable historical
projections.
