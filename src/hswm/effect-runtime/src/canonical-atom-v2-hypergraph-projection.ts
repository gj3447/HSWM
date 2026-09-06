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

type RdfSource = CanonicalAtomV2RdfProjection["manifest"]["source"]

const failure = (
  code: HypergraphProjectionError["code"],
  detail: string
): Either.Either<never, HypergraphProjectionError> => Either.left(new HypergraphProjectionError({ code, detail }))

const sha256 = (bytes: Uint8Array): string => createHash("sha256").update(bytes).digest("hex")
const sameBytes = (left: Uint8Array, right: Uint8Array): boolean => Buffer.from(left).equals(Buffer.from(right))
const isRecord = (value: unknown): value is Readonly<Record<string, unknown>> =>
  typeof value === "object" && value !== null && !Array.isArray(value)

/** Bounded canonical JSON bytes of a value; a bound violation is a typed failure. */
const canonicalBytes = (value: unknown): Either.Either<Uint8Array, HypergraphProjectionError> => {
  const result = canonicalJsonBytes(value)
  return Either.isLeft(result) ? failure("PROJECTION_INVALID", "value is outside bounded canonical JSON") : Either.right(result.right)
}
const digestOf = (value: unknown): Either.Either<string, HypergraphProjectionError> => Either.map(canonicalBytes(value), sha256)

const compare = (left: string, right: string): number => Buffer.from(left).compare(Buffer.from(right))
const orderedGraph = (graph: ProjectionGraph): ProjectionGraph => ({
  nodes: graph.nodes.map((node) => ({ ...node, labels: [...node.labels].sort(compare) })).sort((a, b) => compare(a.id, b.id)),
  relationships: [...graph.relationships].sort((a, b) => compare(a.id, b.id))
})

/** Hashes returned graph content, including labels, endpoints and every property. */
export const projectionGraphDigest = (graph: ProjectionGraph): Either.Either<string, HypergraphProjectionError> =>
  digestOf(orderedGraph(graph))

/**
 * String-returning form of `projectionGraphDigest` kept for the Neo4j publisher
 * and receipt builder; a graph outside bounded canonical JSON raises the same
 * typed `HypergraphProjectionError` that the Either form returns.
 */
export const projectionGraphSha256 = (graph: ProjectionGraph): string =>
  Either.getOrThrowWith(projectionGraphDigest(graph), (error) => error)

const schemaKinds = (value: unknown): HSWMCanonicalSchemaV2["kinds"] | null => {
  const kinds = isRecord(value) ? value["kinds"] : undefined
  return Array.isArray(kinds) ? (kinds as unknown as HSWMCanonicalSchemaV2["kinds"]) : null
}

const fromRdf = (rdf: CanonicalAtomV2RdfProjection): Either.Either<HypergraphProjection, HypergraphProjectionError> =>
  Either.gen(function* () {
    const schemaBytes = Buffer.from(rdf.manifest.source.schemaCanonicalBase64Url, "base64url")
    const schemaResult = decodeCanonicalJsonBytes(schemaBytes)
    if (Either.isLeft(schemaResult)) return yield* failure("SOURCE_INVALID", "invalid schema bytes")
    const kinds = schemaKinds(schemaResult.right)
    if (kinds === null) return yield* failure("SOURCE_INVALID", "schema does not declare atom kinds")
    const profileSha256 = yield* digestOf(HYPERGRAPH_PROJECTION_PROFILE)
    const sourceSha256 = yield* digestOf(rdf.manifest.source)
    const identitySha256 = yield* digestOf({ sourceSha256, profileSha256, rdfSha256: rdf.manifest.dataset.sha256 })
    const projectionId = `hswm-projection-v1:${identitySha256}`
    const id = (category: string, key: unknown): Either.Either<string, HypergraphProjectionError> =>
      Either.map(digestOf(key), (digest) => `${projectionId}:${category}:${digest}`)
    const atomId = (key: Parameters<typeof canonicalAtomV2KeyId>[0]): Either.Either<string, HypergraphProjectionError> =>
      id("atom", canonicalAtomV2KeyId(key))
    const nodes: ProjectionNode[] = []
    const relationships: ProjectionRelationship[] = []
    const node = (nodeId: string, labels: string[], properties: ProjectionProperties): void => {
      nodes.push(Object.freeze({ id: nodeId, labels: Object.freeze(["HSWMProjectionV1", ...labels].sort(compare)), properties: Object.freeze({ ...properties, id: nodeId, projectionId }) }))
    }
    const relationship = (from: string, to: string, type: string): Either.Either<void, HypergraphProjectionError> =>
      Either.map(id("relationship", { from, to, type }), (relationshipId) => {
        relationships.push(Object.freeze({ id: relationshipId, from, to, type, properties: Object.freeze({ id: relationshipId, projectionId }) }))
      })
    const runId = yield* id("run", sourceSha256)
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
      const sourceAtomId = yield* atomId(atom.key)
      const form = kinds.find((kind) => kind.kind === atom.kind)?.form
      if (form === undefined) return yield* failure("SOURCE_INVALID", "schema does not admit atom kind")
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
      yield* relationship(runId, sourceAtomId, "PROJECTED")
      if (atom.provenance.sourceRef !== null) {
        const provenanceAtomId = yield* atomId(atom.provenance.sourceRef)
        yield* relationship(sourceAtomId, provenanceAtomId, "DERIVED_FROM")
      }
      for (const [ordinal, reference] of atom.references.entries()) {
        const participationId = yield* id("participation", { sourceAtomKey: canonicalAtomV2KeyId(atom.key), ordinal })
        const targetAtomId = yield* atomId(reference.target)
        node(participationId, ["Participation"], {
          sourceAtomId, targetAtomId, referenceType: reference.referenceType,
          role: reference.role, ordinal, sourceOwnerUid: atom.responsibilityOwner,
          provenanceMode: atom.provenance.mode, evidenceSha256: atom.provenance.evidenceSha256,
          provenanceScope: "INHERITED_SOURCE_ATOM_NOT_INDEPENDENT_INCIDENCE_ATTESTATION",
          authority: "DERIVED_REFERENCE_VIEW", sourceSha256
        })
        yield* relationship(sourceAtomId, participationId, "HAS_PARTICIPATION")
        yield* relationship(participationId, targetAtomId, "TARGET")
      }
    }
    const nodeIds = new Set(nodes.map((n) => n.id))
    if (nodeIds.size !== nodes.length || new Set(relationships.map((r) => r.id)).size !== relationships.length || relationships.some((r) => !nodeIds.has(r.from) || !nodeIds.has(r.to))) {
      return yield* failure("PROJECTION_INVALID", "projection identity collision or unresolved endpoint")
    }
    const graph = orderedGraph({ nodes, relationships })
    const graphSha256 = yield* projectionGraphDigest(graph)
    return Object.freeze({
      manifest: Object.freeze({
        contractVersion: HSWM_HYPERGRAPH_PROJECTION_V1, projectionId, sourceSha256,
        graphSha256, profileSha256, rdfSha256: rdf.manifest.dataset.sha256,
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
  })

export const compileHypergraphProjection = (
  schema: HSWMCanonicalSchemaV2, source: CanonicalAtomV2RdfProjectionSource
): Either.Either<HypergraphProjection, HypergraphProjectionError> =>
  Either.flatMap(compileCanonicalAtomV2RdfProjection(schema, source), fromRdf).pipe(
    Either.mapLeft(() => new HypergraphProjectionError({ code: "SOURCE_INVALID", detail: "schema, state, tail, or bounded graph source failed verification" }))
  )

const artifactBytes = (projection: HypergraphProjection): Either.Either<Uint8Array, HypergraphProjectionError> => canonicalBytes({
  manifest: projection.manifest, nodes: projection.nodes, relationships: projection.relationships,
  rdf: { manifest: projection.rdf.manifest, nquadsBase64Url: Buffer.from(projection.rdf.nquads).toString("base64url") }
})

/** The caller-supplied bundle's RDF source fields that recompilation decodes before trusting anything else. */
const rdfSourceOf = (projection: HypergraphProjection): Either.Either<RdfSource, HypergraphProjectionError> => {
  const candidate: unknown = projection
  const rdf = isRecord(candidate) ? candidate["rdf"] : undefined
  const manifest = isRecord(rdf) ? rdf["manifest"] : undefined
  const source = isRecord(manifest) ? manifest["source"] : undefined
  return isRecord(source) && typeof source["schemaCanonicalBase64Url"] === "string" && typeof source["tailRecordBase64Url"] === "string"
    ? Either.right(source as unknown as RdfSource)
    : failure("PROJECTION_INVALID", "projection bundle lacks a decodable RDF source")
}

const recompile = (projection: HypergraphProjection): Either.Either<HypergraphProjection, HypergraphProjectionError> =>
  Either.gen(function* () {
    const source = yield* rdfSourceOf(projection)
    const schema = decodeCanonicalJsonBytes(Buffer.from(source.schemaCanonicalBase64Url, "base64url"))
    if (Either.isLeft(schema)) return yield* failure("SOURCE_INVALID", "invalid schema")
    const rdf = verifyCanonicalAtomV2RdfProjection(schema.right as unknown as HSWMCanonicalSchemaV2, {
      journalLineageId: source.journalLineageId, schemaBinding: source.schemaBinding,
      state: source.state, tailDescriptor: source.tailDescriptor,
      tailRecordBytes: Buffer.from(source.tailRecordBase64Url, "base64url")
    }, projection.rdf)
    if (Either.isLeft(rdf)) return yield* failure("PROJECTION_TAMPERED", "invalid RDF")
    const expected = yield* fromRdf(rdf.right)
    const expectedBytes = yield* artifactBytes(expected)
    const actualBytes = yield* artifactBytes(projection)
    if (!sameBytes(expectedBytes, actualBytes)) return yield* failure("PROJECTION_TAMPERED", "tampered projection")
    return expected
  })

/** Self-consistency verification does not attest source custody or current durable tail. */
export const verifyHypergraphProjection = (projection: HypergraphProjection): Either.Either<HypergraphProjection, HypergraphProjectionError> =>
  Either.mapLeft(recompile(projection), () =>
    new HypergraphProjectionError({ code: "PROJECTION_TAMPERED", detail: "artifact differs from source-bound deterministic recompilation" })
  )

export const hypergraphProjectionBytes = (projection: HypergraphProjection): Either.Either<Uint8Array, HypergraphProjectionError> =>
  Either.flatMap(verifyHypergraphProjection(projection), artifactBytes)

export const decodeHypergraphProjectionBytes = (input: Uint8Array): Either.Either<HypergraphProjection, HypergraphProjectionError> => {
  const invalid = failure("PROJECTION_INVALID", "expected bounded canonical hypergraph projection JSON")
  const parsed = decodeCanonicalJsonBytes(input)
  if (Either.isLeft(parsed)) return invalid
  const reencoded = canonicalBytes(parsed.right)
  if (Either.isLeft(reencoded) || !sameBytes(reencoded.right, input)) return invalid
  const rdf = isRecord(parsed.right) ? parsed.right["rdf"] : undefined
  const nquadsBase64Url = isRecord(rdf) ? rdf["nquadsBase64Url"] : undefined
  if (!isRecord(rdf) || typeof nquadsBase64Url !== "string") return invalid
  const envelope = parsed.right as unknown as Omit<HypergraphProjection, "rdf">
  const checked = verifyHypergraphProjection({
    ...envelope,
    rdf: { manifest: rdf["manifest"] as unknown as CanonicalAtomV2RdfProjection["manifest"], nquads: Buffer.from(nquadsBase64Url, "base64url") }
  })
  if (Either.isLeft(checked)) return checked
  const canonical = artifactBytes(checked.right)
  return Either.isLeft(canonical) || !sameBytes(canonical.right, input) ? invalid : checked
}

/** Preserve the existing recovery witness separately; never upgrade bundle self-consistency. */
export const compileDurableHypergraphProjection = (runtime: CanonicalAtomV2DurableRuntime["Type"]) =>
  Effect.gen(function* () {
    const durableRdf = yield* compileCanonicalAtomV2DurableRdfProjection(runtime)
    const projection = yield* Either.mapLeft(fromRdf(durableRdf.projection), () =>
      new HypergraphProjectionError({ code: "SOURCE_INVALID", detail: "durable recovery could not be projected" })
    )
    return { projection, durableRdf }
  })
