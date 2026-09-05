import { createHash } from "node:crypto"

import { Data, Effect, Either } from "effect"

import { canonicalJsonBytes, decodeCanonicalJsonBytes } from "./canonical-atom-v2-json.js"
import { canonicalAtomV2KeyId, type HSWMCanonicalSchemaV2 } from "./canonical-atom-v2-schema.js"
import {
  compileCanonicalAtomV2RdfProjection,
  verifyCanonicalAtomV2RdfProjection,
  type CanonicalAtomV2RdfProjection,
  type CanonicalAtomV2RdfProjectionSource
} from "./canonical-atom-v2-rdf-projection.js"
import { compileCanonicalAtomV2DurableRdfProjection } from "./canonical-atom-v2-durable-rdf-projection.js"
import { type CanonicalAtomV2DurableRuntime } from "./canonical-atom-v2-durable-runtime.js"

export const HSWM_HYPERGRAPH_PROJECTION_V1 = "hswm-hypergraph-projection/v1" as const
export const HYPERGRAPH_PROJECTION_PROFILE = Object.freeze({
  contractVersion: HSWM_HYPERGRAPH_PROJECTION_V1,
  atomIdentity: "SCHEMA_LINEAGE_UID_REVISION",
  relationMapping: "SCHEMA_RELATION_ATOM_IS_HYPEREDGE",
  participationIdentity: "SOURCE_ATOM_KEY_AND_REFERENCE_ARRAY_ORDINAL",
  participationAuthority: "DERIVED_REFERENCE_VIEW_NO_INDEPENDENT_CANONICAL_OWNER_OR_PERMISSION",
  namespace: "HSWMProjectionV1",
  ordering: "UTF8_BYTE_LEXICOGRAPHIC_NODE_AND_RELATIONSHIP_ID",
  writeBack: "FORBIDDEN"
})

export type ProjectionProperties = Readonly<Record<string, string | number | boolean>>
export interface ProjectionNode {
  readonly id: string
  readonly labels: ReadonlyArray<string>
  readonly properties: ProjectionProperties
}
export interface ProjectionRelationship {
  readonly id: string
  readonly from: string
  readonly to: string
  readonly type: string
  readonly properties: ProjectionProperties
}
export interface ProjectionGraph {
  readonly nodes: ReadonlyArray<ProjectionNode>
  readonly relationships: ReadonlyArray<ProjectionRelationship>
}
export interface HypergraphProjection extends ProjectionGraph {
  readonly manifest: {
    readonly contractVersion: typeof HSWM_HYPERGRAPH_PROJECTION_V1
    readonly projectionId: string
    /** Digest of the complete retained source bundle, not only state or tail. */
    readonly sourceSha256: string
    readonly graphSha256: string
    readonly profileSha256: string
    readonly rdfSha256: string
    readonly sourceAttestation: CanonicalAtomV2RdfProjection["manifest"]["sourceAttestation"]
    readonly mapping: "ATOM_HYPEREDGE_ROLE_ORDER_PRESERVING_PARTICIPATION"
    readonly graphRetains: ReadonlyArray<string>
    readonly graphOmits: ReadonlyArray<string>
    readonly bundleOmits: ReadonlyArray<string>
    readonly writeBack: "FORBIDDEN"
    readonly proposalAuthority: "NONE_USE_EXISTING_CANONICAL_ADMISSION"
    readonly claimCeiling: "BOUNDED_METADATA_PARITY_NOT_HSWM_REALIZATION_OR_LEARNING"
    readonly implementationBinding: "PROFILE_BOUND_NOT_EXECUTABLE_ARTIFACT_BOUND"
  }
  readonly rdf: CanonicalAtomV2RdfProjection
}

export class HypergraphProjectionError extends Data.TaggedError("HypergraphProjectionError")<{
  readonly code: "SOURCE_INVALID" | "PROJECTION_INVALID" | "PROJECTION_TAMPERED"
  readonly detail: string
}> {}

const sha256 = (bytes: Uint8Array): string => createHash("sha256").update(bytes).digest("hex")
const bytes = (value: unknown): Uint8Array => {
  const result = canonicalJsonBytes(value)
  if (Either.isLeft(result)) throw new Error("value is outside bounded canonical JSON")
  return result.right
}
const compare = (left: string, right: string): number => Buffer.from(left).compare(Buffer.from(right))
const orderedGraph = (graph: ProjectionGraph): ProjectionGraph => ({
  nodes: graph.nodes.map((node) => ({ ...node, labels: [...node.labels].sort(compare) })).sort((a, b) => compare(a.id, b.id)),
  relationships: [...graph.relationships].sort((a, b) => compare(a.id, b.id))
})

/** Hashes returned graph content, including labels, endpoints and every property. */
export const projectionGraphSha256 = (graph: ProjectionGraph): string => sha256(bytes(orderedGraph(graph)))

const fromRdf = (rdf: CanonicalAtomV2RdfProjection): HypergraphProjection => {
  const schemaBytes = Buffer.from(rdf.manifest.source.schemaCanonicalBase64Url, "base64url")
  const schemaResult = decodeCanonicalJsonBytes(schemaBytes)
  if (Either.isLeft(schemaResult)) throw new Error("invalid schema bytes")
  const schema = schemaResult.right as unknown as HSWMCanonicalSchemaV2
  const profileSha256 = sha256(bytes(HYPERGRAPH_PROJECTION_PROFILE))
  const sourceSha256 = sha256(bytes(rdf.manifest.source))
  const projectionId = `hswm-projection-v1:${sha256(bytes({ sourceSha256, profileSha256, rdfSha256: rdf.manifest.dataset.sha256 }))}`
  const id = (category: string, key: unknown): string => `${projectionId}:${category}:${sha256(bytes(key))}`
  const atomId = (key: Parameters<typeof canonicalAtomV2KeyId>[0]): string => id("atom", canonicalAtomV2KeyId(key))
  const nodes: ProjectionNode[] = []
  const relationships: ProjectionRelationship[] = []
  const node = (nodeId: string, labels: string[], properties: ProjectionProperties): void => {
    nodes.push(Object.freeze({ id: nodeId, labels: Object.freeze(["HSWMProjectionV1", ...labels].sort(compare)), properties: Object.freeze({ ...properties, id: nodeId, projectionId }) }))
  }
  const relationship = (from: string, to: string, type: string): void => {
    const relationshipId = id("relationship", { from, to, type })
    relationships.push(Object.freeze({ id: relationshipId, from, to, type, properties: Object.freeze({ id: relationshipId, projectionId }) }))
  }
  const runId = id("run", sourceSha256)
  node(runId, ["ProjectionRun"], {
    contractVersion: HSWM_HYPERGRAPH_PROJECTION_V1, sourceSha256, profileSha256,
    outputRdfSha256: rdf.manifest.dataset.sha256, stateSha256: rdf.manifest.source.stateSha256,
    schemaSha256: rdf.manifest.source.schemaBinding.content.sha256,
    tailSha256: rdf.manifest.source.tailDescriptor.sha256,
    journalLineageId: rdf.manifest.source.journalLineageId,
    writeBack: "FORBIDDEN", runMeaning: "DETERMINISTIC_COMPILATION_NOT_DATABASE_EXECUTION",
    sourceAttestation: rdf.manifest.sourceAttestation
  })
  for (const atom of rdf.manifest.source.state.atoms) {
    const sourceAtomId = atomId(atom.key)
    const form = schema.kinds.find((kind) => kind.kind === atom.kind)?.form
    if (form === undefined) throw new Error("schema does not admit atom kind")
    node(sourceAtomId, form === "RELATION" ? ["Atom", "Hyperedge"] : ["Atom"], {
      canonicalKey: canonicalAtomV2KeyId(atom.key), uid: atom.key.atomUid,
      schemaVersion: atom.key.schemaVersion, lineageId: atom.key.lineageId,
      revisionId: atom.key.revisionId, kind: atom.kind, kindForm: form,
      ownerUid: atom.responsibilityOwner, lifecycle: atom.lifecycle,
      contentSha256: atom.content.sha256, contentByteLength: atom.content.byteLength,
      contentMediaType: atom.content.mediaType, provenanceMode: atom.provenance.mode,
      evidenceSha256: atom.provenance.evidenceSha256,
      provenanceSourceKey: atom.provenance.sourceRef === null ? "" : canonicalAtomV2KeyId(atom.provenance.sourceRef),
      sourceSha256
    })
    relationship(runId, sourceAtomId, "PROJECTED")
    if (atom.provenance.sourceRef !== null) relationship(sourceAtomId, atomId(atom.provenance.sourceRef), "DERIVED_FROM")
    atom.references.forEach((reference, ordinal) => {
      const participationId = id("participation", { sourceAtomKey: canonicalAtomV2KeyId(atom.key), ordinal })
      const targetAtomId = atomId(reference.target)
      node(participationId, ["Participation"], {
        sourceAtomId, targetAtomId, referenceType: reference.referenceType,
        role: reference.role, ordinal, sourceOwnerUid: atom.responsibilityOwner,
        provenanceMode: atom.provenance.mode, evidenceSha256: atom.provenance.evidenceSha256,
        provenanceScope: "INHERITED_SOURCE_ATOM_NOT_INDEPENDENT_INCIDENCE_ATTESTATION",
        authority: "DERIVED_REFERENCE_VIEW", sourceSha256
      })
      relationship(sourceAtomId, participationId, "HAS_PARTICIPATION")
      relationship(participationId, targetAtomId, "TARGET")
    })
  }
  const nodeIds = new Set(nodes.map((n) => n.id))
  if (nodeIds.size !== nodes.length || new Set(relationships.map((r) => r.id)).size !== relationships.length || relationships.some((r) => !nodeIds.has(r.from) || !nodeIds.has(r.to))) {
    throw new Error("projection identity collision or unresolved endpoint")
  }
  const graph = orderedGraph({ nodes, relationships })
  return Object.freeze({
    manifest: Object.freeze({
      contractVersion: HSWM_HYPERGRAPH_PROJECTION_V1, projectionId, sourceSha256,
      graphSha256: projectionGraphSha256(graph), profileSha256, rdfSha256: rdf.manifest.dataset.sha256,
      sourceAttestation: rdf.manifest.sourceAttestation,
      mapping: "ATOM_HYPEREDGE_ROLE_ORDER_PRESERVING_PARTICIPATION",
      graphRetains: Object.freeze(["FORK_SAFE_ATOM_KEY", "SCHEMA_RELATIVE_OWNER", "CONTENT_DESCRIPTOR", "ATOM_PROVENANCE", "TYPED_REFERENCE_ROLE_ORDINAL_MULTIPLICITY"]),
      graphOmits: Object.freeze(["RAW_CONTENT_PAYLOAD_BYTES", "FULL_JOURNAL_CHAIN", "SCHEMA_CONSTRAINTS", "TAIL_RECORD_STRUCTURE", "STATE_BOOTSTRAP_AND_ACCEPTED_TRANSITIONS"]),
      bundleOmits: Object.freeze(["RAW_CONTENT_PAYLOAD_BYTES", "FULL_JOURNAL_CHAIN"]),
      writeBack: "FORBIDDEN", proposalAuthority: "NONE_USE_EXISTING_CANONICAL_ADMISSION",
      claimCeiling: "BOUNDED_METADATA_PARITY_NOT_HSWM_REALIZATION_OR_LEARNING",
      implementationBinding: "PROFILE_BOUND_NOT_EXECUTABLE_ARTIFACT_BOUND"
    }),
    nodes: Object.freeze(graph.nodes), relationships: Object.freeze(graph.relationships), rdf
  })
}

export const compileHypergraphProjection = (
  schema: HSWMCanonicalSchemaV2, source: CanonicalAtomV2RdfProjectionSource
): Either.Either<HypergraphProjection, HypergraphProjectionError> => {
  try {
    const rdf = compileCanonicalAtomV2RdfProjection(schema, source)
    if (Either.isLeft(rdf)) throw new Error("RDF source verification failed")
    return Either.right(fromRdf(rdf.right))
  } catch {
    return Either.left(new HypergraphProjectionError({ code: "SOURCE_INVALID", detail: "schema, state, tail, or bounded graph source failed verification" }))
  }
}

const artifactBytes = (projection: HypergraphProjection): Uint8Array => bytes({
  manifest: projection.manifest, nodes: projection.nodes, relationships: projection.relationships,
  rdf: { manifest: projection.rdf.manifest, nquadsBase64Url: Buffer.from(projection.rdf.nquads).toString("base64url") }
})

/** Self-consistency verification does not attest source custody or current durable tail. */
export const verifyHypergraphProjection = (projection: HypergraphProjection): Either.Either<HypergraphProjection, HypergraphProjectionError> => {
  try {
    const source = projection.rdf.manifest.source
    const schema = decodeCanonicalJsonBytes(Buffer.from(source.schemaCanonicalBase64Url, "base64url"))
    if (Either.isLeft(schema)) throw new Error("invalid schema")
    const rdf = verifyCanonicalAtomV2RdfProjection(schema.right as unknown as HSWMCanonicalSchemaV2, {
      journalLineageId: source.journalLineageId, schemaBinding: source.schemaBinding,
      state: source.state, tailDescriptor: source.tailDescriptor,
      tailRecordBytes: Buffer.from(source.tailRecordBase64Url, "base64url")
    }, projection.rdf)
    if (Either.isLeft(rdf)) throw new Error("invalid RDF")
    const expected = fromRdf(rdf.right)
    if (!Buffer.from(artifactBytes(expected)).equals(Buffer.from(artifactBytes(projection)))) throw new Error("tampered projection")
    return Either.right(expected)
  } catch {
    return Either.left(new HypergraphProjectionError({ code: "PROJECTION_TAMPERED", detail: "artifact differs from source-bound deterministic recompilation" }))
  }
}

export const hypergraphProjectionBytes = (projection: HypergraphProjection): Either.Either<Uint8Array, HypergraphProjectionError> =>
  Either.map(verifyHypergraphProjection(projection), artifactBytes)

export const decodeHypergraphProjectionBytes = (input: Uint8Array): Either.Either<HypergraphProjection, HypergraphProjectionError> => {
  try {
    const parsed = decodeCanonicalJsonBytes(input)
    if (Either.isLeft(parsed) || !Buffer.from(bytes(parsed.right)).equals(Buffer.from(input))) throw new Error("noncanonical JSON")
    const value = parsed.right as unknown as Omit<HypergraphProjection, "rdf"> & { readonly rdf: { readonly manifest: CanonicalAtomV2RdfProjection["manifest"]; readonly nquadsBase64Url: string } }
    const checked = verifyHypergraphProjection({ ...value, rdf: { manifest: value.rdf.manifest, nquads: Buffer.from(value.rdf.nquadsBase64Url, "base64url") } })
    if (Either.isRight(checked) && !Buffer.from(artifactBytes(checked.right)).equals(Buffer.from(input))) throw new Error("noncanonical artifact envelope")
    return checked
  } catch {
    return Either.left(new HypergraphProjectionError({ code: "PROJECTION_INVALID", detail: "expected bounded canonical hypergraph projection JSON" }))
  }
}

/** Preserve the existing recovery witness separately; never upgrade bundle self-consistency. */
export const compileDurableHypergraphProjection = (runtime: CanonicalAtomV2DurableRuntime["Type"]) =>
  compileCanonicalAtomV2DurableRdfProjection(runtime).pipe(Effect.flatMap((durableRdf) =>
    Effect.try({
      try: () => ({ projection: fromRdf(durableRdf.projection), durableRdf }),
      catch: () => new HypergraphProjectionError({ code: "SOURCE_INVALID", detail: "durable recovery could not be projected" })
    })
  ))
