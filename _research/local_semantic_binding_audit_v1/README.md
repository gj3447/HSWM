# Local semantic binding audit v1

This deterministic, no-model-call instrument enumerates all ten unordered swaps
of the five **values** bound to `subject.dax`, `subject.wug`, `subject.zif`,
`context.pel`, and `exception.nub` in the authored W1 fixture. It leaves the
relation text, role names and order, field locations, and ontology untouched.
It looks up each transformed five-bit input in the same exhaustive 128-case
reference table.

Run without writing an artifact:

```bash
node _research/local_semantic_binding_audit_v1/run.mjs
```

To create a new, exclusive artifact at an absolute path:

```bash
node _research/local_semantic_binding_audit_v1/run.mjs --output /tmp/hswm-binding-audit.json
```

The report has 40 rows: four rule families times ten field-value pairs. Each
row reports 32 source cases, how often the serialized field values changed,
how often `answer` changed, how often any expected intermediate changed, and
one answer-changing witness when present. It also verifies identity lookup and
the inverse-swap round trip for every source case and pair.

The table is authored fixture logic, not independent semantic evidence. It has
`model_calls: 0`; it does not evaluate role-label or ontology exchanges, LLM
understanding, durable state, learning, or efficacy.
