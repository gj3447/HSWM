/** Offline, non-canonical package for a verified HypergraphProjection. */
import { createHash } from "node:crypto"
import { Data, Either } from "effect"
import { canonicalJsonBytes } from "./canonical-atom-v2-json.js"
import { hypergraphProjectionBytes, projectionGraphSha256, verifyHypergraphProjection, type HypergraphProjection, type ProjectionGraph } from "./canonical-atom-v2-hypergraph-projection.js"

export const HSWM_HYPERGRAPH_PROJECTION_RECEIPT_V1 = "hswm-hypergraph-projection-receipt/v1" as const
export const OPENLINEAGE_RUN_EVENT_SCHEMA_URL = "https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunEvent" as const
export const HSWM_ARTIFACT_FACET_SCHEMA_URL = "https://raw.githubusercontent.com/gj3447/HSWM/6108410a90f5caf8b367bb1fce5282c96744d24e/schemas/hswm_openlineage_artifact_facet.v1.schema.json" as const
export const HSWM_HYPERGRAPH_PROJECTION_CLAIM_BOUNDARY = "offline projection compilation evidence only; non-canonical, non-promoting, not an HSWM atom, Permit, outcome owner, causal-credit path, learning result, or independent evidence of live Neo4j parity" as const
export interface HypergraphProjectionShaclEvidence { readonly bytes: Uint8Array; readonly mediaType: string }
export interface HypergraphProjectionParityReport { readonly mode: "LOCAL_COMPILER_ONLY" | "CALLER_REPORTED_LIVE_NEO4J_PARITY"; readonly readbackGraph?: ProjectionGraph; readonly shaclEvidence: HypergraphProjectionShaclEvidence; readonly reportedBy?: string }
export interface HypergraphProjectionPackageInput { readonly runId: string; readonly startedAt: string; readonly completedAt: string; readonly producer: string; readonly parity?: HypergraphProjectionParityReport }
export interface HypergraphProjectionPackage { readonly receipt: Readonly<Record<string, unknown>>; readonly files: ReadonlyMap<string, Uint8Array> }
export class HypergraphProjectionReceiptError extends Data.TaggedError("HypergraphProjectionReceiptError")<{ readonly code: "PROJECTION_INVALID" | "EXECUTION_INVALID" | "PARITY_INVALID" | "ENCODING_INVALID"; readonly detail: string }> {}
const encoder = new TextEncoder()
const sha = (value: Uint8Array): string => createHash("sha256").update(value).digest("hex")
const text = (value: unknown): value is string => typeof value === "string" && value.length > 0 && value.trim() === value
const fail = (code: HypergraphProjectionReceiptError["code"], detail: string): Either.Either<never, HypergraphProjectionReceiptError> => Either.left(new HypergraphProjectionReceiptError({ code, detail }))
const bytes = (value: unknown): Either.Either<Uint8Array, HypergraphProjectionReceiptError> => { const result = canonicalJsonBytes(value); return Either.isLeft(result) ? fail("ENCODING_INVALID", result.left.detail) : Either.right(result.right) }
const validTimestamp = (value: string): boolean => { const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{3})?(Z|[+-]\d{2}:\d{2})$/.exec(value); if (!match) return false; const [, y, mo, d, h, mi, s] = match; const year = Number(y), month = Number(mo), day = Number(d); return month >= 1 && month <= 12 && day >= 1 && day <= new Date(Date.UTC(year, month, 0)).getUTCDate() && Number(h) <= 23 && Number(mi) <= 59 && Number(s) <= 59 && Number.isFinite(Date.parse(value)) }
const validProducer = (value: string): boolean => { try { const url = new URL(value); return url.protocol === "https:" && !!url.hostname && !url.username && !url.password && !url.search && !url.hash } catch { return false } }
const artifact = (path: string, value: Uint8Array, mediaType: string) => ({ path, bytes: value.byteLength, mediaType, sha256: sha(value) })
const validShaclEvidence = (evidence: HypergraphProjectionShaclEvidence, projection: HypergraphProjection): boolean => {
  try {
    const parsed: unknown = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(evidence.bytes))
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) return false
    const row = parsed as Record<string, unknown>
    return row["conforms"] === true && row["datasetSha256"] === projection.manifest.rdfSha256 && row["sourceStateSha256"] === projection.rdf.manifest.source.stateSha256
  } catch { return false }
}

const buildHypergraphProjectionPackageInternal = (projection: HypergraphProjection, input: HypergraphProjectionPackageInput): Either.Either<HypergraphProjectionPackage, HypergraphProjectionReceiptError> => {
  const verified = verifyHypergraphProjection(projection)
  if (Either.isLeft(verified)) return fail("PROJECTION_INVALID", verified.left.detail)
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(input.runId) || !text(input.producer) || !validProducer(input.producer) || !validTimestamp(input.startedAt) || !validTimestamp(input.completedAt) || Date.parse(input.completedAt) < Date.parse(input.startedAt)) return fail("EXECUTION_INVALID", "runId must be UUID and timestamps/producer must be explicit valid execution metadata")
  const sourceBytes = bytes(projection.rdf.manifest.source), graphBytes = bytes({ nodes: projection.nodes, relationships: projection.relationships }), projectionBytes = hypergraphProjectionBytes(projection)
  if (Either.isLeft(sourceBytes)) return Either.left(sourceBytes.left); if (Either.isLeft(graphBytes)) return Either.left(graphBytes.left); if (Either.isLeft(projectionBytes)) return fail("PROJECTION_INVALID", projectionBytes.left.detail)
  if (sha(sourceBytes.right) !== projection.manifest.sourceSha256 || projectionGraphSha256(projection) !== projection.manifest.graphSha256) return fail("PROJECTION_INVALID", "verified projection source or graph digest mismatch")
  const parity = input.parity
  if (!parity || !text(parity.shaclEvidence.mediaType) || parity.shaclEvidence.bytes.byteLength === 0 || !validShaclEvidence(parity.shaclEvidence, projection)) return fail("PARITY_INVALID", "package requires exact conforming SHACL evidence for this RDF dataset and source state")
  let parityReceipt: Record<string, unknown> = { mode: "LOCAL_COMPILER_ONLY" }; const shaclBytes = parity.shaclEvidence.bytes; const shacl = artifact("shacl-evidence.json", shaclBytes, parity.shaclEvidence.mediaType)
  if (parity.mode === "CALLER_REPORTED_LIVE_NEO4J_PARITY") { if (!parity.readbackGraph) return fail("PARITY_INVALID", "caller-reported live parity requires normalized readback"); const readbackGraphSha256 = projectionGraphSha256(parity.readbackGraph); if (readbackGraphSha256 !== projection.manifest.graphSha256) return fail("PARITY_INVALID", "caller readback graph differs from compiled graph"); parityReceipt = { mode: "CALLER_REPORTED_LIVE_NEO4J_PARITY", readbackGraphSha256, shaclEvidenceSha256: shacl.sha256, reportedBy: parity.reportedBy ?? null, claimCeiling: "CALLER_REPORTED_READBACK_NOT_INDEPENDENT_DATABASE_CUSTODY_OR_CANONICAL_AUTHORITY" } } else if (parity.mode !== "LOCAL_COMPILER_ONLY") return fail("PARITY_INVALID", "unknown parity mode")
  const runIri = `urn:hswm:projection-run:${input.runId}`
  const provBytes = encoder.encode([
    `<${runIri}> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/ns/prov#Activity> .`,
    `<${runIri}> <http://www.w3.org/ns/prov#used> <urn:hswm:sha256:${projection.manifest.sourceSha256}> .`,
    `<${runIri}> <http://www.w3.org/ns/prov#startedAtTime> "${input.startedAt}"^^<http://www.w3.org/2001/XMLSchema#dateTime> .`,
    `<${runIri}> <http://www.w3.org/ns/prov#endedAtTime> "${input.completedAt}"^^<http://www.w3.org/2001/XMLSchema#dateTime> .`,
    `<urn:hswm:sha256:${projection.manifest.graphSha256}> <http://www.w3.org/ns/prov#wasGeneratedBy> <${runIri}> .`,
    `<urn:hswm:sha256:${projection.manifest.graphSha256}> <http://www.w3.org/ns/prov#wasDerivedFrom> <urn:hswm:sha256:${projection.manifest.sourceSha256}> .`,
    ""
  ].join("\n"))
  const fixed = [artifact("projection-source.json", sourceBytes.right, "application/json"), artifact("projection-graph.json", graphBytes.right, "application/json"), artifact("hypergraph-projection.json", projectionBytes.right, "application/json"), artifact("projection.rdf.nq", projection.rdf.nquads, "application/n-quads"), artifact("projection-run.prov.nq", provBytes, "application/n-quads")], artifacts = [...fixed, shacl]
  const receipt = { contractVersion: HSWM_HYPERGRAPH_PROJECTION_RECEIPT_V1, claimBoundary: HSWM_HYPERGRAPH_PROJECTION_CLAIM_BOUNDARY, runId: input.runId, startedAt: input.startedAt, completedAt: input.completedAt, producer: input.producer, compiler: { projectionId: projection.manifest.projectionId, sourceSha256: projection.manifest.sourceSha256, graphSha256: projection.manifest.graphSha256, profileSha256: projection.manifest.profileSha256, rdfSha256: projection.manifest.rdfSha256, writeBack: "FORBIDDEN" }, parity: parityReceipt, artifacts }
  const receiptBytes = bytes(receipt); if (Either.isLeft(receiptBytes)) return Either.left(receiptBytes.left)
  const facet = (entry: ReturnType<typeof artifact>) => ({ _producer: input.producer, _schemaURL: HSWM_ARTIFACT_FACET_SCHEMA_URL, bytes: entry.bytes, path: entry.path, sha256: entry.sha256 }); const datasets = artifacts.map((entry) => ({ namespace: "hswm.hypergraph-projection.artifact", name: entry.sha256, facets: { hswmArtifact: facet(entry) } })); const common = { schemaURL: OPENLINEAGE_RUN_EVENT_SCHEMA_URL, producer: input.producer, job: { namespace: "hswm.hypergraph-projection", name: projection.manifest.projectionId }, run: { runId: input.runId }, inputs: datasets.filter((entry) => entry.name === projection.manifest.sourceSha256), outputs: datasets.filter((entry) => entry.name !== projection.manifest.sourceSha256) }
  const startBytes = bytes({ eventType: "START", eventTime: input.startedAt, ...common }), completeBytes = bytes({ eventType: "COMPLETE", eventTime: input.completedAt, ...common }); if (Either.isLeft(startBytes)) return Either.left(startBytes.left); if (Either.isLeft(completeBytes)) return Either.left(completeBytes.left)
  const crateArtifacts = [
    ...artifacts,
    artifact("projection-receipt.json", receiptBytes.right, "application/json"),
    artifact("openlineage-start.json", startBytes.right, "application/json"),
    artifact("openlineage-complete.json", completeBytes.right, "application/json")
  ]
  const crate = { "@context": "https://w3id.org/ro/crate/1.3/context", "@graph": [{ "@id": "./", "@type": "Dataset", name: `HSWM hypergraph projection: ${projection.manifest.projectionId}`, description: HSWM_HYPERGRAPH_PROJECTION_CLAIM_BOUNDARY, datePublished: input.completedAt, license: "No license is granted by this projection package.", conformsTo: { "@id": "https://w3id.org/ro/crate/1.3" }, hasPart: crateArtifacts.map((entry) => ({ "@id": entry.path })) }, { "@id": "ro-crate-metadata.json", "@type": "CreativeWork", about: { "@id": "./" }, conformsTo: { "@id": "https://w3id.org/ro/crate/1.3" } }, ...crateArtifacts.map((entry) => ({ "@id": entry.path, "@type": "File", contentSize: String(entry.bytes), encodingFormat: entry.mediaType, [HSWM_ARTIFACT_FACET_SCHEMA_URL + "#sha256"]: entry.sha256 }))] }
  const crateBytes = bytes(crate); if (Either.isLeft(crateBytes)) return Either.left(crateBytes.left)
  const files = new Map<string, Uint8Array>([["projection-source.json", sourceBytes.right], ["projection-graph.json", graphBytes.right], ["hypergraph-projection.json", projectionBytes.right], ["projection.rdf.nq", projection.rdf.nquads], ["projection-run.prov.nq", provBytes], ["projection-receipt.json", receiptBytes.right], ["openlineage-start.json", startBytes.right], ["openlineage-complete.json", completeBytes.right], ["ro-crate-metadata.json", crateBytes.right], ["shacl-evidence.json", shaclBytes]])
  return Either.right({ receipt: { ...receipt, receiptSha256: sha(receiptBytes.right) }, files })
}

/** Fail closed even when an untyped external caller passes malformed runtime input. */
export const buildHypergraphProjectionPackage = (
  projection: HypergraphProjection,
  input: HypergraphProjectionPackageInput
): Either.Either<HypergraphProjectionPackage, HypergraphProjectionReceiptError> => {
  try {
    return buildHypergraphProjectionPackageInternal(projection, input)
  } catch {
    return fail("EXECUTION_INVALID", "malformed caller runtime input")
  }
}
