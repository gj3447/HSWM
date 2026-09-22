# Deep research graph queries

Bundle: `sym:AbstractNode:hswm-deep-research-2026-09-22`.

`decisions.rq` returns source-backed W1–W5 decisions; `inherited_negatives.rq`
returns the preserved JEV negative; `experiments_not_run.rq` lists planned,
unrun empirical protocols; `unsupported.rq` expects zero rows. These checks are
bounded source/claim coverage, never a truth or efficacy audit.

```sh
npm --prefix src/hswm/effect-runtime run build
node _research/hswm_deep_research_v1/build.mts
src/hswm/effect-runtime/bin/hswm-kg-bundle validate --source deep_research=ontology/development/HSWM_DEEP_RESEARCH_2026-09-22.v1.json --profile v2 --shapes schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl
```
