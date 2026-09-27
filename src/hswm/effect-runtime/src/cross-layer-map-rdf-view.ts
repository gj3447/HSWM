/**
 * A deliberately derived, public-field RDF view of one validated MapSpec.
 * It is not the canonical atom projection and has no write-back authority.
 */
import { createHash } from "node:crypto"
import { Data, Effect, Either } from "effect"

import { canonicalJsonBytes } from "./canonical-atom-v2-json.js"
import { canonicalAtomV2KeyId } from "./canonical-atom-v2-schema.js"
import { decodeCrossLayerInputPacket } from "./cross-layer-map-domain.js"
import {
  CROSS_LAYER_MAP_ROLE_REFERENCE_TYPE,
  readCrossLayerMapFrame,
  type CrossLayerMapFrame
} from "./cross-layer-map-runtime.js"
import type { CanonicalAtomV2DurableRuntime } from "./canonical-atom-v2-durable-runtime.js"

const VIEW = "https://hswm.invalid/cross-layer-map-rdf-view/v1/"
const CANONICAL = "https://hswm.invalid/canonical-atom-v2/rdf/v1/vocab/"
// Same fixed v1 atom formula as canonical-atom-v2-rdf-projection.ts atomIri().
const CANONICAL_ATOM = "https://hswm.invalid/canonical-atom-v2/rdf/v1/atom/"
const PROV = "http://www.w3.org/ns/prov#"
const RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
const XSD = "http://www.w3.org/2001/XMLSchema#"
const encoder = new TextEncoder()

export const CROSS_LAYER_MAP_RDF_VIEW_CONTRACT_VERSION = "hswm:cross-layer-map-rdf-view/v1" as const

export class CrossLayerMapRdfViewError extends Data.TaggedError("CrossLayerMapRdfViewError")<{
  readonly code: "PACKET_INVALID" | "FRAME_ROLE_INVALID" | "FRAME_CONTENT_MISMATCH" | "CONTEXT_COMMITMENT_MISMATCH" | "SERIALIZATION_FAILED"
  readonly detail: string
}> {}

export interface CrossLayerMapRdfViewManifest {
  readonly contractVersion: typeof CROSS_LAYER_MAP_RDF_VIEW_CONTRACT_VERSION
  readonly format: "RDF_1_1_NQUADS"
  readonly profile: "DERIVED_MAPSPEC_PUBLIC_FIELDS_V1"
  readonly relationCanonicalKeyId: string
  readonly contextCanonicalKeyId: string
  readonly contextContentSha256: string
  readonly viewIri: string
  readonly relationAtomIri: string
  readonly contextAtomIri: string
  readonly sourceModelIri: string
  readonly targetModelIri: string
  readonly dataset: Readonly<{ readonly sha256: string; readonly byteLength: number }>
  readonly exposes: readonly string[]
  readonly omits: readonly string[]
  readonly provenanceMeaning: "VIEW_DERIVATION_ONLY"
  readonly writeBack: "FORBIDDEN"
}

export interface CrossLayerMapRdfView {
  readonly manifest: CrossLayerMapRdfViewManifest
  readonly nquads: Uint8Array
}

const error = (code: CrossLayerMapRdfViewError["code"], detail: string) =>
  new CrossLayerMapRdfViewError({ code, detail })
const sha256 = (value: Uint8Array): string => createHash("sha256").update(value).digest("hex")
const iri = (value: string): string => `<${value}>`
const literal = (value: string): string => JSON.stringify(value)
const typed = (value: number): string => `${JSON.stringify(String(value))}^^<${XSD}nonNegativeInteger>`
const predicate = (value: string): string => iri(`${VIEW}${value}`)
const canonicalPredicate = (value: string): string => iri(`${CANONICAL}${value}`)
const resource = (kind: string, id: string): string => iri(`${VIEW}${kind}/${encodeURIComponent(id)}`)
const canonicalAtom = (keyId: string): string => iri(`${CANONICAL_ATOM}${encodeURIComponent(keyId)}`)
const triple = (subject: string, predicateIri: string, object: string, graph: string): string =>
  `${subject} ${predicateIri} ${object} ${graph} .\n`

const exactRoles = ["subject", "context", "evidence", "exception"] as const

/**
 * Structurally checks a supplied frame and compiles only a MapSpec whose
 * bytes are committed by its exact context participant. The Effect wrapper is
 * the canonical-runtime authenticity read; this pure function has no such claim.
 */
export const compileCrossLayerMapRdfView = (
  input: CrossLayerMapFrame
): Either.Either<CrossLayerMapRdfView, CrossLayerMapRdfViewError> => {
  const { frame } = input
  const packet = decodeCrossLayerInputPacket(input.packet)
  if (Either.isLeft(packet)) return Either.left(error("PACKET_INVALID", `${packet.left.path}: ${packet.left.detail}`))
  if (frame.roles.length !== exactRoles.length || frame.roles.some((role, index) =>
    role.referenceType !== CROSS_LAYER_MAP_ROLE_REFERENCE_TYPE || role.role !== exactRoles[index])) {
    return Either.left(error("FRAME_ROLE_INVALID", "frame must retain the exact ordered cross-layer roles"))
  }
  const context = frame.roles[1]
  if (context === undefined) return Either.left(error("FRAME_ROLE_INVALID", "context role is absent"))
  if (frame.roles.some((role) => sha256(encoder.encode(role.contentUtf8)) !== role.contentSha256))
    return Either.left(error("FRAME_CONTENT_MISMATCH", "every role content UTF-8 value must match its declared SHA-256"))
  const subjectBytes = canonicalJsonBytes({ subject: packet.right.subject, eventTime: packet.right.eventTime })
  const evidenceBytes = canonicalJsonBytes({ evidence: packet.right.evidence, eventTime: packet.right.eventTime })
  if (Either.isLeft(subjectBytes) || Either.isLeft(evidenceBytes))
    return Either.left(error("SERIALIZATION_FAILED", "packet participant wrapper cannot be canonically serialized"))
  if (frame.roles[0]?.contentUtf8 !== new TextDecoder().decode(subjectBytes.right) ||
    frame.roles[2]?.contentUtf8 !== new TextDecoder().decode(evidenceBytes.right))
    return Either.left(error("FRAME_CONTENT_MISMATCH", "packet subject or evidence differs from its committed frame participant"))
  const canonical = canonicalJsonBytes(packet.right.context)
  if (Either.isLeft(canonical)) return Either.left(error("SERIALIZATION_FAILED", canonical.left.detail))
  const contextTextBytes = encoder.encode(context.contentUtf8)
  if (sha256(contextTextBytes) !== context.contentSha256 ||
    sha256(canonical.right) !== context.contentSha256 ||
    context.contentUtf8 !== new TextDecoder().decode(canonical.right)) {
    return Either.left(error("CONTEXT_COMMITMENT_MISMATCH", "MapSpec does not match the committed context participant bytes and digest"))
  }

  const relationId = canonicalAtomV2KeyId(frame.relation.key)
  const contextId = canonicalAtomV2KeyId(context.key)
  const graph = resource("graph", relationId)
  const view = resource("view", `${relationId}:${context.contentSha256}`)
  const relation = canonicalAtom(relationId)
  const contextAtom = canonicalAtom(contextId)
  const map = resource("map-spec", context.contentSha256)
  const sourceModel = resource("model", `${packet.right.context.source.modelRef}:${packet.right.context.source.digest}`)
  const targetModel = resource("model", `${packet.right.context.target.modelRef}:${packet.right.context.target.digest}`)
  const lines: string[] = []
  const add = (subject: string, predicateIri: string, object: string) => lines.push(triple(subject, predicateIri, object, graph))

  add(view, iri(`${RDF}type`), predicate("DerivedMapSpecView"))
  add(view, iri(`${RDF}type`), iri(`${PROV}Entity`))
  add(view, iri(`${PROV}wasDerivedFrom`), contextAtom)
  add(view, iri(`${PROV}wasDerivedFrom`), relation)
  add(view, predicate("derivedFromContext"), contextAtom)
  add(view, predicate("relation"), relation)
  add(view, predicate("mapSpec"), map)
  add(view, predicate("contextContentSha256"), literal(context.contentSha256))
  add(view, predicate("writeBack"), literal("FORBIDDEN"))
  add(view, predicate("provenanceMeaning"), literal("VIEW_DERIVATION_ONLY"))
  add(relation, iri(`${RDF}type`), predicate("DerivedRelation"))
  add(relation, predicate("canonicalKeyId"), literal(relationId))
  add(relation, predicate("revisionId"), typed(frame.relation.key.revisionId))
  add(contextAtom, predicate("canonicalKeyId"), literal(contextId))
  add(contextAtom, canonicalPredicate("contentSha256"), literal(context.contentSha256))
  add(map, iri(`${RDF}type`), predicate("MapSpec"))
  add(map, predicate("schema"), literal(packet.right.context.schema))
  add(map, predicate("sourceModel"), sourceModel)
  add(map, predicate("targetModel"), targetModel)
  add(sourceModel, predicate("modelRef"), literal(packet.right.context.source.modelRef))
  add(sourceModel, predicate("modelSha256"), literal(packet.right.context.source.digest))
  add(targetModel, predicate("modelRef"), literal(packet.right.context.target.modelRef))
  add(targetModel, predicate("modelSha256"), literal(packet.right.context.target.digest))
  add(map, predicate("sourceModelRef"), literal(packet.right.context.source.modelRef))
  add(map, predicate("sourceModelSha256"), literal(packet.right.context.source.digest))
  add(map, predicate("targetModelRef"), literal(packet.right.context.target.modelRef))
  add(map, predicate("targetModelSha256"), literal(packet.right.context.target.digest))
  add(map, predicate("mappingKind"), literal(packet.right.context.mappingKind))
  add(map, predicate("mappingMethod"), literal(packet.right.context.mappingMethod))
  add(map, predicate("timeUnit"), literal(packet.right.context.time.unit))
  add(map, predicate("timeHorizon"), typed(packet.right.context.time.horizon))
  add(map, predicate("supportWorld"), literal(packet.right.context.supportScope.world))
  // The compiler preserves array positions in ordinal slots. SHACL Core checks
  // each exposed entry's shape but not global ordinal uniqueness.
  const ordered = (property: string, values: readonly string[]) => values.forEach((value, ordinal) => {
    const entry = resource("map-array-entry", `${context.contentSha256}:${property}:${ordinal}`)
    add(map, predicate(property), literal(value))
    add(map, predicate(`${property}Entry`), entry)
    add(entry, predicate("ordinal"), typed(ordinal))
    add(entry, predicate("value"), literal(value))
  })
  ordered("declaredLoss", packet.right.context.declaredLosses)
  ordered("allowedAction", packet.right.context.actionAllowlist)
  ordered("supportContext", packet.right.context.supportScope.contexts)
  ordered("observableField", packet.right.context.supportScope.observableFields)
  frame.roles.forEach((role, ordinal) => {
    const participantId = canonicalAtomV2KeyId(role.key)
    const incidence = resource("incidence", `${relationId}:${ordinal}`)
    const participant = canonicalAtom(participantId)
    add(relation, predicate("hasRoleIncidence"), incidence)
    add(incidence, iri(`${RDF}type`), predicate("RoleIncidence"))
    add(incidence, canonicalPredicate("role"), literal(role.role))
    add(incidence, canonicalPredicate("referenceType"), literal(role.referenceType))
    add(incidence, canonicalPredicate("ordinal"), typed(ordinal))
    add(incidence, canonicalPredicate("sourceAtom"), relation)
    add(incidence, canonicalPredicate("targetAtom"), participant)
    add(participant, predicate("canonicalKeyId"), literal(participantId))
    add(participant, canonicalPredicate("contentSha256"), literal(role.contentSha256))
  })

  const nquads = encoder.encode(lines.join(""))
  const manifest: CrossLayerMapRdfViewManifest = Object.freeze({
    contractVersion: CROSS_LAYER_MAP_RDF_VIEW_CONTRACT_VERSION,
    format: "RDF_1_1_NQUADS",
    profile: "DERIVED_MAPSPEC_PUBLIC_FIELDS_V1",
    relationCanonicalKeyId: relationId,
    contextCanonicalKeyId: contextId,
    contextContentSha256: context.contentSha256,
    viewIri: view.slice(1, -1),
    relationAtomIri: relation.slice(1, -1),
    contextAtomIri: contextAtom.slice(1, -1),
    sourceModelIri: sourceModel.slice(1, -1),
    targetModelIri: targetModel.slice(1, -1),
    dataset: Object.freeze({ sha256: sha256(nquads), byteLength: nquads.byteLength }),
    exposes: Object.freeze(["MAPSPEC_PUBLIC_FIELDS", "RELATION_CONTEXT_IDENTIFIERS", "ROLE_INCIDENCE_ORDER", "VIEW_DERIVATION_LINK"]),
    omits: Object.freeze(["RAW_SUBJECT_EVIDENCE_EXCEPTION_PAYLOADS", "SEMANTIC_RELATION_PAYLOAD", "FULL_CANONICAL_JOURNAL", "CAUSAL_TRUTH_OR_VALIDATION"]),
    provenanceMeaning: "VIEW_DERIVATION_ONLY",
    writeBack: "FORBIDDEN"
  })
  return Either.right(Object.freeze({ manifest, nquads }))
}

/** Read, validate, then derive the bounded public RDF view; it never writes runtime state. */
export const readCrossLayerMapRdfView = (
  runtime: CanonicalAtomV2DurableRuntime["Type"], relationUid: string, event: string
) =>
  readCrossLayerMapFrame(runtime, relationUid, event).pipe(Effect.flatMap((frame) => {
    const compiled = compileCrossLayerMapRdfView(frame)
    return Either.isLeft(compiled) ? Effect.fail(compiled.left) : Effect.succeed(compiled.right)
  }))
