# Jev standard graph engineering — query checks

Bundle: `sym:AbstractNode:hswm-jev-graph-engineering-2026-09-22`.

`mapping.rq` expects six P1–P6 rows. `next_work.rq` expects five W1–W5 rows.
`contracts.rq` expects the eight §3 data-dictionary rows.
`unsupported.rq` expects zero rows for a missing source or an invalid CR/FCL
promotion. Its bounded coverage checks listed source-bound research roles and
every owned node's explicit `cr_fcl_promotion: false`; it is not a truth audit.
`inherited_negative.rq` expects one preserved negative finding.

```sh
npm --prefix src/hswm/effect-runtime run build
node _research/jev_graph_engineering_v1/build.mts
src/hswm/effect-runtime/bin/hswm-kg-bundle validate --source jev_graph_engineering=ontology/development/HSWM_JEV_GRAPH_ENGINEERING_2026-09-22.v1.json --profile v2 --shapes schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl
src/hswm/effect-runtime/bin/hswm-kg-bundle query --source jev_graph_engineering=ontology/development/HSWM_JEV_GRAPH_ENGINEERING_2026-09-22.v1.json --profile v2 --query ontology/queries/hswm_jev_graph_engineering_2026-09-22/mapping.rq
```

The RDF 1.1 / PROV-O projection and SHACL/SPARQL checks validate a bounded,
read-only exchange view. They do not implement HSWM state, admission, learning,
causal credit, efficacy, or a CR/FCL closure.
