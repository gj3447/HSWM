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
- [`v2 current continuation checkpoint`](HSWM_SWM0W_S2S_EFFECT_HANDOFF.v2.json)
  records the bounded GitHub, artifact, exact-round drand, and Python execution
  adapters plus the still-open provenance/composition/workflow/finalizer gates.

They are explicitly not preregistrations, scientific evidence verdicts, HSWM
runtime graphs, or remote Neo4j publications. v2 supersedes v1 only as the
next-session entrypoint; v1 remains an immutable historical projection.
