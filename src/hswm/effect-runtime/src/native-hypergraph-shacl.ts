/** Source-bound SHACL Core validation using the qualified native RDF engine. */
import { Effect } from "effect"
import { verifyHypergraphProjection, type HypergraphProjection } from "./canonical-atom-v2-hypergraph-projection.js"
import { validateKgShacl } from "./native-kg-standards.js"
import { kgSha256 } from "./native-kg-bundle-domain.js"

export const validateNativeHypergraphShacl=(projection:HypergraphProjection,shapes:Uint8Array)=>Effect.gen(function*(){
 yield* verifyHypergraphProjection(projection)
 const result=yield* validateKgShacl({nquads:projection.rdf.nquads,descriptor:{...projection.rdf.manifest},provO:new Uint8Array()},shapes)
 return Object.freeze({
  contract:"hswm-hypergraph-projection-shacl-validation/v1",
  conforms:result.conforms,
  datasetSha256:kgSha256(projection.rdf.nquads),
  sourceStateSha256:projection.rdf.manifest.source.stateSha256,
  shapesSha256:kgSha256(shapes),
  mappingLoss:[...projection.rdf.manifest.rdfDatasetOmits],
  claimCeiling:"SHACL_1_0_DERIVED_RDF_STRUCTURE_ONLY_NOT_FULL_GRAPH_LOSSLESSNESS_CANONICAL_ADMISSION_PERMIT_CAUSAL_CREDIT_LEARNING_OR_EFFICACY",
  report:JSON.stringify(result.results),
  engine:result.engine,
  profile:result.profile,
  engineAuthority:"INDEPENDENT_IMPLEMENTATION_QUALIFIED_AGAINST_PINNED_W3C_CORE_SUITE"
 })
})
