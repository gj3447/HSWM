/**
 * Small v1 bridge from a cross-layer input packet to the existing semantic
 * relation runtime.  It deliberately leaves the semantic-relation payload
 * unchanged: the map lives in the immutable `context` participant.
 */
import { createHash } from "node:crypto"
import { Data, Effect, Either } from "effect"

import {
  canonicalJsonBytes,
  decodeCanonicalJsonBytes
} from "./canonical-atom-v2-json.js"
import {
  describeCanonicalAtomV2Envelope,
  makeCanonicalAtomV2ContentBoundInput,
  type CommitCanonicalAtomsV2ContentBound,
  type CanonicalAtomV2WriteContentBinding
} from "./canonical-atom-v2-content-bound.js"
import { CanonicalAtomV2DurableRuntime } from "./canonical-atom-v2-durable-runtime.js"
import {
  HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
  HSWM_SUPERSEDES_REFERENCE_ROLE,
  HSWM_SUPERSEDES_REFERENCE_TYPE,
  canonicalAtomV2KeyId,
  type CanonicalAtomV2,
  type CanonicalAtomV2Key,
  type CanonicalAtomV2Reference,
  type HSWMCanonicalSchemaV2
} from "./canonical-atom-v2-schema.js"
import {
  decodeCrossLayerInputPacket,
  type CrossLayerInputPacket
} from "./cross-layer-map-domain.js"
import {
  executeLlmSemanticRelation,
  readLlmSemanticFrame,
  LlmSemanticRuntimeError,
  type LlmSemanticCell,
  type SemanticReadFrame
} from "./canonical-atom-v2-llm-semantic-runtime.js"
import type { AdaptiveHttpClientShape } from "./adaptive-executor.js"

export const CROSS_LAYER_MAP_PARTICIPANT_MEDIA_TYPE =
  "application/vnd.hswm.cross-layer-map-participant-v1+json" as const
/** Reuse the v1 semantic runtime's established participant reference type. */
export const CROSS_LAYER_MAP_ROLE_REFERENCE_TYPE = "hswm:semantic:role" as const
export const CROSS_LAYER_MAP_RELATION_KIND = "semantic_relation" as const
export const CROSS_LAYER_MAP_PARTICIPANT_KIND = "semantic_participant" as const

export class CrossLayerMapRuntimeError extends Data.TaggedError("CrossLayerMapRuntimeError")<{
  readonly code: "PACKET_INVALID" | "CONTENT_INVALID" | "RELATION_INVALID" | "PARTICIPANT_INVALID" | "STATE_STALE"
  readonly detail: string
}> {}

const fail = (code: CrossLayerMapRuntimeError["code"], detail: string) =>
  new CrossLayerMapRuntimeError({ code, detail })

const bytes = (value: unknown): Either.Either<Uint8Array, CrossLayerMapRuntimeError> => {
  const result = canonicalJsonBytes(value)
  return Either.isLeft(result)
    ? Either.left(fail("CONTENT_INVALID", result.left.detail))
    : Either.right(Uint8Array.from(result.right))
}

const keyId = canonicalAtomV2KeyId
const sha256 = (value: Uint8Array): string => createHash("sha256").update(value).digest("hex")

export const createCrossLayerMapSchema = (
  schemaVersion: string,
  owner: string
): HSWMCanonicalSchemaV2 => Object.freeze({
  _tag: "HSWMCanonicalSchemaV2",
  contractVersion: HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  schemaVersion,
  scientificStatus: "UNJUDGED",
  bootstrapTrustStatement: "Local cross-layer map integration fixture; no brain, world, or efficacy claim.",
  owners: Object.freeze([{ address: owner, obligation: "Owns cross-layer semantic relation revisions." }]),
  kinds: Object.freeze([
    Object.freeze({
      kind: CROSS_LAYER_MAP_PARTICIPANT_KIND,
      form: "ENTITY" as const,
      revisionPolicy: "SINGLETON" as const,
      allowedOwners: Object.freeze([owner]),
      minimumArity: 0,
      referenceContracts: Object.freeze([])
    }),
    Object.freeze({
      kind: CROSS_LAYER_MAP_RELATION_KIND,
      form: "RELATION" as const,
      revisionPolicy: "LINEAR" as const,
      allowedOwners: Object.freeze([owner]),
      minimumArity: 4,
      referenceContracts: Object.freeze([
        Object.freeze({
          referenceType: CROSS_LAYER_MAP_ROLE_REFERENCE_TYPE,
          roles: Object.freeze(["subject", "context", "evidence", "exception"].map((role) => Object.freeze({
            role,
            targetKinds: Object.freeze([CROSS_LAYER_MAP_PARTICIPANT_KIND]),
            minimum: 1,
            maximum: 1
          })))
        }),
        Object.freeze({
          referenceType: HSWM_SUPERSEDES_REFERENCE_TYPE,
          roles: Object.freeze([Object.freeze({
            role: HSWM_SUPERSEDES_REFERENCE_ROLE,
            targetKinds: Object.freeze([CROSS_LAYER_MAP_RELATION_KIND]),
            minimum: 0,
            maximum: 1
          })])
        })
      ])
    })
  ])
})

export interface CrossLayerMapParticipantKeys {
  readonly subject: CanonicalAtomV2Key
  readonly context: CanonicalAtomV2Key
  readonly evidence: CanonicalAtomV2Key
}

export interface StagedCrossLayerMapInput {
  readonly packet: CrossLayerInputPacket
  readonly participants: Readonly<{
    readonly subject: CanonicalAtomV2
    readonly context: CanonicalAtomV2
    readonly evidence: CanonicalAtomV2
  }>
}

/** Decode and stage a bounded v1 input packet before any LLM transport. */
export const stageCrossLayerMapInput = (
  runtime: CanonicalAtomV2DurableRuntime["Type"],
  rawPacket: unknown,
  keys: CrossLayerMapParticipantKeys,
  owner: string
) => Effect.gen(function* () {
  const decoded = decodeCrossLayerInputPacket(rawPacket)
  if (Either.isLeft(decoded)) return yield* Effect.fail(fail("PACKET_INVALID", decoded.left.detail))
  if ([keys.subject, keys.context, keys.evidence].some((key) => key.revisionId !== 0))
    return yield* Effect.fail(fail("PARTICIPANT_INVALID", "v1 input participants are fresh singleton revision zero atoms"))
  if (new Set([keyId(keys.subject), keyId(keys.context), keyId(keys.evidence)]).size !== 3)
    return yield* Effect.fail(fail("PARTICIPANT_INVALID", "subject, context, and evidence keys must be distinct"))
  const subjectBytes = bytes(Object.freeze({ subject: decoded.right.subject, eventTime: decoded.right.eventTime }))
  const contextBytes = bytes(decoded.right.context)
  const evidenceBytes = bytes(Object.freeze({ evidence: decoded.right.evidence, eventTime: decoded.right.eventTime }))
  if (Either.isLeft(subjectBytes)) return yield* Effect.fail(subjectBytes.left)
  if (Either.isLeft(contextBytes)) return yield* Effect.fail(contextBytes.left)
  if (Either.isLeft(evidenceBytes)) return yield* Effect.fail(evidenceBytes.left)
  const current = yield* runtime.snapshot
  const make = (key: CanonicalAtomV2Key, payload: Uint8Array, mode: "BOOTSTRAP" | "OBSERVATION") => Effect.gen(function* () {
    if (key.schemaVersion !== runtime.schema.schemaVersion)
      return yield* Effect.fail(fail("PARTICIPANT_INVALID", "participant schema version differs from runtime schema"))
    const content = yield* runtime.stageContent(CROSS_LAYER_MAP_PARTICIPANT_MEDIA_TYPE, payload)
    return Object.freeze({
      _tag: "CanonicalAtomV2" as const,
      contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
      key,
      kind: CROSS_LAYER_MAP_PARTICIPANT_KIND,
      responsibilityOwner: owner,
      content,
      provenance: { mode, evidenceSha256: content.sha256, sourceRef: null },
      lifecycle: "ADMITTED" as const,
      references: Object.freeze([])
    }) satisfies CanonicalAtomV2
  })
  const subject = yield* make(keys.subject, subjectBytes.right, "OBSERVATION")
  // The map is authored context at this first slice. Later input packets must
  // name and reuse its immutable atom; replacing a MapSpec is a distinct,
  // explicit binding/mapping transition rather than an observation write.
  const knownContext = current.canonical.atoms.find((atom) => keyId(atom.key) === keyId(keys.context))
  const context = knownContext === undefined
    ? (current.canonical.bootstrapClosed
      ? yield* Effect.fail(fail("PARTICIPANT_INVALID", "a new authored MapSpec requires an explicit map-binding transition after bootstrap"))
      : yield* make(keys.context, contextBytes.right, "BOOTSTRAP"))
    : (() => {
      if (knownContext.kind !== CROSS_LAYER_MAP_PARTICIPANT_KIND || knownContext.content.sha256 !== sha256(contextBytes.right))
        return null
      return knownContext
    })()
  if (context === null) return yield* Effect.fail(fail("PARTICIPANT_INVALID", "existing context key does not bind this exact MapSpec"))
  const evidence = yield* make(keys.evidence, evidenceBytes.right, "OBSERVATION")
  return Object.freeze({ packet: decoded.right, participants: Object.freeze({ subject, context, evidence }) }) satisfies StagedCrossLayerMapInput
})

const binding = (atom: CanonicalAtomV2): Either.Either<CanonicalAtomV2WriteContentBinding, CrossLayerMapRuntimeError> => {
  const envelope = describeCanonicalAtomV2Envelope(atom)
  return Either.isLeft(envelope)
    ? Either.left(fail("CONTENT_INVALID", "cannot bind canonical atom envelope"))
    : Either.right(Object.freeze({ key: atom.key, payload: atom.content, envelope: envelope.right }))
}

export interface CrossLayerMapBindingRequest {
  readonly relationUid: string
  readonly subject: CanonicalAtomV2Key
  readonly context: CanonicalAtomV2Key
  readonly evidence: CanonicalAtomV2Key
  readonly authorizationRef: string
  readonly scope: string
  readonly decidedAt: string
}

export interface CrossLayerMapBindingProposal {
  readonly candidate: CommitCanonicalAtomsV2ContentBound
  readonly affectedKeys: ReadonlyArray<CanonicalAtomV2Key>
  readonly priorRelation: CanonicalAtomV2Key
  readonly nextRelation: CanonicalAtomV2Key
}

const readBoundJson = (runtime: CanonicalAtomV2DurableRuntime["Type"], atom: CanonicalAtomV2) =>
  runtime.readContent(atom.content).pipe(Effect.flatMap((raw) => {
    if (raw.byteLength > 65_536 || raw.byteLength !== atom.content.byteLength || sha256(raw) !== atom.content.sha256)
      return Effect.fail(fail("CONTENT_INVALID", "participant content does not match its descriptor"))
    const decoded = decodeCanonicalJsonBytes(raw)
    return Either.isLeft(decoded)
      ? Effect.fail(fail("CONTENT_INVALID", "participant content is not canonical JSON"))
      : Effect.succeed(decoded.right)
  }))

const packetFromValues = (
  subject: unknown, context: unknown, evidence: unknown
): Either.Either<CrossLayerInputPacket, CrossLayerMapRuntimeError> => {
  const exact = (value: unknown, keys: ReadonlyArray<string>): value is Readonly<Record<string, unknown>> =>
    value !== null && typeof value === "object" && !Array.isArray(value) && Object.keys(value).length === keys.length && keys.every((key) => Object.hasOwn(value, key))
  if (!exact(subject, ["subject", "eventTime"]) || !exact(evidence, ["evidence", "eventTime"]) || subject["eventTime"] !== evidence["eventTime"])
    return Either.left(fail("PACKET_INVALID", "participant wrappers are incomplete or have extra fields"))
  const decoded = decodeCrossLayerInputPacket({ subject: subject["subject"], context, evidence: evidence["evidence"], eventTime: subject["eventTime"] })
  return Either.isLeft(decoded) ? Either.left(fail("PACKET_INVALID", decoded.left.detail)) : Either.right(decoded.right)
}

const packetFromParticipants = (
  runtime: CanonicalAtomV2DurableRuntime["Type"],
  subject: CanonicalAtomV2,
  context: CanonicalAtomV2,
  evidence: CanonicalAtomV2
) => Effect.gen(function* () {
  const [subjectRaw, contextRaw, evidenceRaw] = yield* Effect.all([
    readBoundJson(runtime, subject), readBoundJson(runtime, context), readBoundJson(runtime, evidence)
  ])
  const decoded = packetFromValues(subjectRaw, contextRaw, evidenceRaw)
  if (Either.isLeft(decoded)) return yield* Effect.fail(decoded.left)
  return decoded.right
})

const packetFromFrame = (frame: SemanticReadFrame): Either.Either<CrossLayerInputPacket, CrossLayerMapRuntimeError> => {
  const expected = ["subject", "context", "evidence", "exception"]
  if (frame.roles.length !== expected.length || frame.roles.some((role, index) =>
    role.referenceType !== CROSS_LAYER_MAP_ROLE_REFERENCE_TYPE || role.role !== expected[index]))
    return Either.left(fail("RELATION_INVALID", "frame roles must be exact ordered subject/context/evidence/exception"))
  const parse = (text: string): Either.Either<unknown, CrossLayerMapRuntimeError> => {
    const decoded = decodeCanonicalJsonBytes(new TextEncoder().encode(text))
    return Either.isLeft(decoded) ? Either.left(fail("CONTENT_INVALID", "frame participant is not duplicate-free canonical JSON")) : Either.right(decoded.right)
  }
  const subject = parse(frame.roles[0]!.contentUtf8), context = parse(frame.roles[1]!.contentUtf8), evidence = parse(frame.roles[2]!.contentUtf8)
  if (Either.isLeft(subject)) return Either.left(subject.left)
  if (Either.isLeft(context)) return Either.left(context.left)
  if (Either.isLeft(evidence)) return Either.left(evidence.left)
  return packetFromValues(subject.right, context.right, evidence.right)
}

export interface CrossLayerMapFrame {
  readonly frame: SemanticReadFrame
  readonly packet: CrossLayerInputPacket
}

/** Read the exact current semantic frame and enforce the bounded v1 packet profile. */
export const readCrossLayerMapFrame = (
  runtime: CanonicalAtomV2DurableRuntime["Type"], relationUid: string, event: string
) => readLlmSemanticFrame(runtime, relationUid, event).pipe(Effect.flatMap((frame) => {
  const packet = packetFromFrame(frame)
  return Either.isLeft(packet)
    ? Effect.fail(packet.left)
    : Effect.succeed(Object.freeze({ frame, packet: packet.right }) satisfies CrossLayerMapFrame)
}))

/**
 * Execute only after the semantic runtime has validated this exact read frame.
 * The optional validator added to the v1 executor closes the read-to-transport
 * race without changing its payload or admission behavior.
 */
export const executeCrossLayerMapRelation = (
  runtime: CanonicalAtomV2DurableRuntime["Type"],
  relationUid: string,
  event: string,
  cell: LlmSemanticCell,
  http: AdaptiveHttpClientShape
) => Effect.gen(function* () {
  const checked = yield* readCrossLayerMapFrame(runtime, relationUid, event)
  if (checked.frame.relation.semantic.trace !== null) {
    const traceBytes = yield* runtime.readContent(checked.frame.relation.semantic.trace)
    let trace: { request?: { sha256?: unknown; mediaType?: unknown; byteLength?: unknown } }
    try { trace = JSON.parse(new TextDecoder().decode(traceBytes)) } catch { return yield* Effect.fail(fail("CONTENT_INVALID", "prior trace is not readable JSON")) }
    if (trace.request === undefined || typeof trace.request.sha256 !== "string" || typeof trace.request.mediaType !== "string" || typeof trace.request.byteLength !== "number")
      return yield* Effect.fail(fail("CONTENT_INVALID", "prior trace has no bound request"))
    const requestBytes = yield* runtime.readContent({ sha256: trace.request.sha256, mediaType: trace.request.mediaType, byteLength: trace.request.byteLength })
    let request: { frame?: { roles?: Array<{ role?: unknown; contentUtf8?: unknown }> } }
    try { request = JSON.parse(new TextDecoder().decode(requestBytes)) } catch { return yield* Effect.fail(fail("CONTENT_INVALID", "prior request is not readable JSON")) }
    if (!Array.isArray(request.frame?.roles))
      return yield* Effect.fail(fail("CONTENT_INVALID", "prior request has no role array"))
    const oldSubject = request.frame.roles.find((role) => role !== null && typeof role === "object" && role.role === "subject")?.contentUtf8
    try {
      const old = JSON.parse(typeof oldSubject === "string" ? oldSubject : "") as { subject?: { requested?: { window?: { end?: unknown } } } }
      const end = old.subject?.requested?.window?.end
      if (typeof end !== "number" || !Number.isSafeInteger(end) || end < 0 || checked.packet.subject.asOf < end)
        return yield* Effect.fail(fail("STATE_STALE", "next input must begin after the prior prediction window"))
    } catch { return yield* Effect.fail(fail("CONTENT_INVALID", "prior subject window is invalid")) }
  }
  return yield* executeLlmSemanticRelation(runtime, relationUid, event, cell, http, (frame) => {
    const packet = packetFromFrame(frame)
    return frame.frameSha256 !== checked.frame.frameSha256 || Either.isLeft(packet)
      ? Either.left(new LlmSemanticRuntimeError({ code: "CONTENT_INVALID", detail: Either.isLeft(packet) ? packet.left.detail : "cross-layer frame changed before transport" }))
      : Either.right(undefined)
  })
})

/**
 * Bind already-admitted fresh immutable input participants to a successor
 * relation.  It changes no v1 semantic payload fields and has no submit power.
 */
export const prepareCrossLayerMapBindingSuccessor = (
  runtime: CanonicalAtomV2DurableRuntime["Type"],
  request: CrossLayerMapBindingRequest
) => Effect.gen(function* () {
  const state = yield* runtime.snapshot
  const candidates = state.canonical.atoms.filter((atom) => atom.key.atomUid === request.relationUid)
  if (new Set(candidates.map((atom) => JSON.stringify([atom.key.schemaVersion, atom.key.lineageId]))).size > 1)
    return yield* Effect.fail(fail("RELATION_INVALID", "relation UID is ambiguous across schema or lineage"))
  const relation = candidates.reduce<CanonicalAtomV2 | undefined>((prior, atom) =>
    prior === undefined || atom.key.revisionId > prior.key.revisionId ? atom : prior, undefined)
  if (relation === undefined || relation.kind !== CROSS_LAYER_MAP_RELATION_KIND)
    return yield* Effect.fail(fail("RELATION_INVALID", "current semantic relation is absent"))
  const oldRoles = relation.references.filter((entry) => entry.referenceType !== HSWM_SUPERSEDES_REFERENCE_TYPE)
  const expectedRoles = ["subject", "context", "evidence", "exception"]
  if (oldRoles.length !== 4 || oldRoles.some((entry, index) => entry.referenceType !== CROSS_LAYER_MAP_ROLE_REFERENCE_TYPE || entry.role !== expectedRoles[index]))
    return yield* Effect.fail(fail("RELATION_INVALID", "relation roles must be the exact ordered v1 map profile"))
  const existing = new Map(state.canonical.atoms.map((atom) => [keyId(atom.key), atom] as const))
  for (const key of [request.subject, request.context, request.evidence]) {
    const atom = existing.get(keyId(key))
    if (atom === undefined || atom.kind !== CROSS_LAYER_MAP_PARTICIPANT_KIND || atom.key.revisionId !== 0)
      return yield* Effect.fail(fail("PARTICIPANT_INVALID", "new binding participants must be existing fresh singleton atoms"))
  }
  const newSubject = existing.get(keyId(request.subject))!
  const newContext = existing.get(keyId(request.context))!
  const newEvidence = existing.get(keyId(request.evidence))!
  const nextPacket = yield* packetFromParticipants(runtime, newSubject, newContext, newEvidence)
  const oldSubject = existing.get(keyId(oldRoles[0]!.target))
  if (oldSubject !== undefined) {
    const oldRaw = yield* readBoundJson(runtime, oldSubject)
    const oldWindow = (oldRaw as { subject?: { requested?: { window?: { end?: unknown } } } }).subject?.requested?.window?.end
    const nextWindow = (nextPacket.subject.requested as { window?: { start?: unknown } }).window?.start
    if (typeof oldWindow === "number" && typeof nextWindow === "number" && nextWindow < oldWindow)
      return yield* Effect.fail(fail("STATE_STALE", "new subject window begins before the prior bound subject window ends"))
  }
  const exception = oldRoles[3]!.target
  const nextKey = Object.freeze({ ...relation.key, revisionId: relation.key.revisionId + 1 })
  const roles: ReadonlyArray<CanonicalAtomV2Reference> = Object.freeze([
    Object.freeze({ referenceType: CROSS_LAYER_MAP_ROLE_REFERENCE_TYPE, role: "subject", target: request.subject }),
    Object.freeze({ referenceType: CROSS_LAYER_MAP_ROLE_REFERENCE_TYPE, role: "context", target: request.context }),
    Object.freeze({ referenceType: CROSS_LAYER_MAP_ROLE_REFERENCE_TYPE, role: "evidence", target: request.evidence }),
    Object.freeze({ referenceType: CROSS_LAYER_MAP_ROLE_REFERENCE_TYPE, role: "exception", target: exception })
  ])
  const successor = Object.freeze({
    _tag: "CanonicalAtomV2" as const,
    contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
    key: nextKey,
    kind: relation.kind,
    responsibilityOwner: relation.responsibilityOwner,
    content: relation.content,
    provenance: { mode: "DERIVATION" as const, evidenceSha256: newEvidence.content.sha256, sourceRef: relation.key },
    lifecycle: "ADMITTED" as const,
    references: Object.freeze([
      Object.freeze({ referenceType: HSWM_SUPERSEDES_REFERENCE_TYPE, role: HSWM_SUPERSEDES_REFERENCE_ROLE, target: relation.key }),
      ...roles
    ])
  }) satisfies CanonicalAtomV2
  const write = binding(successor)
  if (Either.isLeft(write)) return yield* Effect.fail(write.left)
  const uniqueKeys = (keys: ReadonlyArray<CanonicalAtomV2Key>): ReadonlyArray<CanonicalAtomV2Key> =>
    Object.freeze([...new Map(keys.map((key) => [keyId(key), key] as const)).values()])
  const readSet = uniqueKeys([relation.key, ...oldRoles.map((role) => role.target), request.subject, request.context, request.evidence])
  const command = {
    _tag: "CommitCanonicalAtomsV2" as const,
    contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
    transitionId: `cross-layer-bind:${sha256(new TextEncoder().encode(JSON.stringify([
      relation.key, request.subject, request.context, request.evidence
    ])))}`,
    expectedStateRevision: state.canonical.revision,
    schemaVersion: relation.key.schemaVersion,
    actorClaim: "hswm:cross-layer-map-binder",
    authorizationRef: request.authorizationRef,
    scope: request.scope,
    decidedAt: request.decidedAt,
    traceRef: null,
    readSet,
    writes: [successor],
    provenanceSha256: successor.provenance.evidenceSha256
  }
  return Object.freeze({
    candidate: makeCanonicalAtomV2ContentBoundInput(runtime.schemaContent.content.sha256, command, [write.right]),
    affectedKeys: uniqueKeys([relation.key, ...oldRoles.map((role) => role.target), request.subject, request.context, request.evidence]),
    priorRelation: relation.key,
    nextRelation: nextKey
  }) satisfies CrossLayerMapBindingProposal
})
