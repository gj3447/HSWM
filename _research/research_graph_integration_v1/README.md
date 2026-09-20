# HSWM research integration snapshot

`build.mts` builds the 2026-09-20 research graph from fixed public source catalogs and the completed DGX study. It uses the repository's existing Effect and KG bundle compiler; no package installation is required.

Run from the repository root:

```sh
npm --prefix src/hswm/effect-runtime run build
node _research/research_graph_integration_v1/build.mts
```

The catalogs record 244 repository sources, 49 existing KG sources, 12 digest-verified private research responses and their public citation locations. Private answers, credentials and account/session identifiers are excluded. The builder never reads the private source store and does not publish or call a model.

The graph is a secondary research projection. Filename-based topic classification is navigation metadata, not semantic adjudication. Prior citations marked unverified remain unverified; exact source hashes do not establish truth. Existing claims, historical RED results and canonical identity remain at their original sources.

See [competency queries and SHACL commands](../../ontology/queries/hswm_research_integration_2026-09-20/README.md), the [research report](../../docs/research/HSWM_RESEARCH_INTEGRATION_2026-09-20.md), and the separate live publication/readback receipt. Publication uses the existing registry-checked transaction adapter with the reviewed bundle digest and does not rewrite any existing node.

`publish.mts PRIVATE_SOURCE_CONFIG` accepts only the hardcoded reviewed bundle digest. It retains the existing publisher's registry, collision, anchor and full readback checks. The first unoptimized attempt failed and a separate read confirmed zero owned nodes and edges. The second adapter adds already-validated endpoint labels to relationship queries: official Neo4j `EXPLAIN` changes the plan from a relationship-type scan to a UID unique index seek. This changes query planning, not graph contents or authority. No indexes or schema entries are created, and no automatic transaction retry is enabled. See the preserved first-attempt report and final publication receipt.
