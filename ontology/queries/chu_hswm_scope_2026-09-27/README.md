# CHU / HSWM software-scope queries

These SPARQL 1.1 queries are for the source-bound, read-only RDF view of
`CHU_HSWM_SOFTWARE_SCOPE_ONTOLOGY.v1.json`. They identify declared scope and
contracts; they do not invoke a program, establish world-model efficacy, or
write canonical HSWM state.

- `scope.rq` returns the CHU-rooted HSWM and non-LLM profiles, their declared
  `llm_required` booleans, and their shared target capability.
- `execution_contracts.rq` returns paths declared by computational contracts.
  A returned path is a mapping record, not an executable permission.
- `sources_and_gaps.rq` returns literature connections and open research gaps.

Run the bounded verifier after building the native runtime:

```sh
npm --prefix src/hswm/effect-runtime run build
node _research/chu_hswm_scope_v1/verify.mjs
```

The verifier compiles the local bundle with the existing native KG v2 compiler,
runs the generic and local SHACL 1.0 Core profiles, reads all three queries,
and proves three isolated negative mutations are rejected. It neither publishes
to a live KG nor edits the source bundle.
