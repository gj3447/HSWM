/** Read-only, code-relative serialization experiments on the existing semantic frame. */
import { createHash } from "node:crypto"
import { Either, Schema } from "effect"
import { canonicalJsonBytes, decodeCanonicalJsonBytes } from "./canonical-atom-v2-json.js"
import { CanonicalAtomV2KeySchema, canonicalAtomV2KeyId } from "./canonical-atom-v2-schema.js"
import { CanonicalAtomV2ContentDescriptorSchema } from "./canonical-atom-v2-content.js"
import type { SemanticReadFrame } from "./canonical-atom-v2-llm-semantic-runtime.js"

export type SemanticFrameRepresentationKind = "direct_json" | "incidence" | "role_table"
export interface SemanticFrameRepresentationError {
  readonly code: "INVALID_REPRESENTATION" | "INVALID_FRAME" | "CANONICAL_JSON" | "COMMITMENT_MISMATCH"
  readonly detail: string
}
export interface SemanticFrameRepresentation {
  readonly kind: SemanticFrameRepresentationKind
  readonly payload: unknown
  readonly bytes: Uint8Array
  readonly sha256: string
  readonly sourceCanonicalSha256: string
  readonly serializationBytes: number
  readonly costScope: "SERIALIZATION_BYTES_ONLY"
}
export interface SemanticFrameRepresentationComparison {
  readonly representations: readonly SemanticFrameRepresentation[]
  readonly sourceCanonicalSha256: string
  readonly fullRoundTripFidelity: true
  readonly conclusion: "NO_UNIVERSAL_MINIMUM_WINNER"
  readonly excludedCosts: readonly string[]
}

const contract = "hswm-semantic-frame-representation/v1"
const outcomeStatus = "CALLER_DECLARED_NOT_INDEPENDENTLY_VERIFIED"
const columns = Object.freeze(["ordinal", "referenceType", "role", "schemaVersion", "lineageId", "atomUid", "revisionId", "owner", "contentSha256", "contentUtf8"])
const utf8 = new TextEncoder()
const hash = (value: Uint8Array | string): string => createHash("sha256").update(value).digest("hex")
const record = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value)
const exact = (value: unknown, keys: readonly string[]): value is Record<string, unknown> => record(value) && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key))
const text = (value: unknown): value is string => typeof value === "string" && value.length > 0 && value.length <= 8192
const digest = (value: unknown): value is string => typeof value === "string" && /^[a-f0-9]{64}$/u.test(value)
const integer = (value: unknown): value is number => typeof value === "number" && Number.isSafeInteger(value) && value >= 0
const key = (value: unknown): boolean => Either.isRight(Schema.decodeUnknownEither(CanonicalAtomV2KeySchema)(value, { onExcessProperty: "error" }))
const descriptor = (value: unknown, mediaType: string, outcome = false): boolean => {
  if (!exact(value, outcome ? ["sha256", "mediaType", "byteLength", "status"] : ["sha256", "mediaType", "byteLength"])) return false
  return value["mediaType"] === mediaType && (!outcome || value["status"] === outcomeStatus) && Either.isRight(Schema.decodeUnknownEither(CanonicalAtomV2ContentDescriptorSchema)({ sha256: value["sha256"], mediaType: value["mediaType"], byteLength: value["byteLength"] }))
}
const fail = <A = never>(code: SemanticFrameRepresentationError["code"], detail: string): Either.Either<A, SemanticFrameRepresentationError> => Either.left(Object.freeze({ code, detail }))
const freezeDeep = <T>(value: T): T => {
  if (Array.isArray(value)) value.forEach(freezeDeep)
  else if (record(value)) Object.values(value).forEach(freezeDeep)
  if (value !== null && typeof value === "object") Object.freeze(value)
  return value
}
const canonical = (value: unknown): Either.Either<Uint8Array, SemanticFrameRepresentationError> => {
  const result = canonicalJsonBytes(value)
  return Either.isLeft(result) ? fail("CANONICAL_JSON", result.left.detail) : Either.right(result.right)
}

/** Structural/content integrity only: this does not authenticate an external caller. */
const validFrame = (value: unknown): value is SemanticReadFrame => {
  if (!exact(value, ["event", "stateRevision", "relation", "roles", "priorEvidence", "frameSha256"]) || !text(value["event"]) || !integer(value["stateRevision"]) || !digest(value["frameSha256"])) return false
  const relation = value["relation"]
  if (!exact(relation, ["key", "owner", "semantic"]) || !key(relation["key"]) || !text(relation["owner"])) return false
  const semantic = relation["semantic"]
  if (!record(semantic) || !exact(semantic, ["semanticText", "disposition", "uncertainty", "exceptionRefs", "trace", "outcome", ...(Object.hasOwn(semantic, "revisionEvidence") ? ["revisionEvidence"] : [])])) return false
  if (![semantic["semanticText"], semantic["disposition"], semantic["uncertainty"]].every(text) || !Array.isArray(semantic["exceptionRefs"]) || !semantic["exceptionRefs"].every(text) || new Set(semantic["exceptionRefs"]).size !== semantic["exceptionRefs"].length) return false
  if ((semantic["trace"] === null) !== (semantic["outcome"] === null)) return false
  if (semantic["trace"] !== null && !descriptor(semantic["trace"], "application/vnd.hswm.llm-semantic-trace-v1+json")) return false
  if (semantic["outcome"] !== null && !descriptor(semantic["outcome"], "application/vnd.hswm.llm-semantic-outcome-v1+json", true)) return false
  if (Object.hasOwn(semantic, "revisionEvidence") && !descriptor(semantic["revisionEvidence"], "application/vnd.hswm.llm-semantic-revision-v1+json")) return false
  const roles = value["roles"]
  if (!Array.isArray(roles)) return false
  const targets = new Map<string, string>()
  for (const role of roles) {
    if (!exact(role, ["referenceType", "role", "key", "owner", "contentSha256", "contentUtf8"]) || ![role["referenceType"], role["role"], role["owner"]].every(text) || !key(role["key"]) || !digest(role["contentSha256"]) || typeof role["contentUtf8"] !== "string") return false
    if (utf8.encode(role["contentUtf8"]).byteLength > 65_536 || hash(role["contentUtf8"]) !== role["contentSha256"]) return false
    const id = canonical(role["key"]), endpoint = canonical({ owner: role["owner"], contentSha256: role["contentSha256"], contentUtf8: role["contentUtf8"] })
    if (Either.isLeft(id) || Either.isLeft(endpoint)) return false
    const address = hash(id.right), fingerprint = hash(endpoint.right)
    if (targets.has(address) && targets.get(address) !== fingerprint) return false
    targets.set(address, fingerprint)
  }
  if (!["subject", "context", "evidence"].every(name => roles.some(role => role["role"] === name))) return false
  if (!semantic["exceptionRefs"].every(id => roles.some(role => role["role"] === "exception" && record(role["key"]) && role["key"]["atomUid"] === id))) return false
  const prior = value["priorEvidence"]
  return semantic["trace"] === null ? prior === null : exact(prior, ["prediction", "uncertainty", "observed", "source", "status"]) && [prior["prediction"], prior["uncertainty"], prior["observed"], prior["source"]].every(text) && prior["status"] === outcomeStatus
}

const kinds: readonly string[] = Object.freeze(["direct_json", "incidence", "role_table"])
const header = (frame: SemanticReadFrame) => ({ event: frame.event, stateRevision: frame.stateRevision, relation: frame.relation, priorEvidence: frame.priorEvidence, frameSha256: frame.frameSha256 })
const makeBody = (frame: SemanticReadFrame, kind: SemanticFrameRepresentationKind): unknown => {
  if (kind === "direct_json") return { frame }
  if (kind === "role_table") return { header: header(frame), roleCount: frame.roles.length, columns, rows: frame.roles.map((role, ordinal) => [ordinal, role.referenceType, role.role, role.key.schemaVersion, role.key.lineageId, role.key.atomUid, role.key.revisionId, role.owner, role.contentSha256, role.contentUtf8]) }
  const participants = new Map<string, unknown>()
  const incidences = frame.roles.map((role, ordinal) => {
    const id = canonicalAtomV2KeyId(role.key)
    if (!participants.has(id)) participants.set(id, { id, key: role.key, owner: role.owner, contentSha256: role.contentSha256, contentUtf8: role.contentUtf8 })
    return { ordinal, referenceType: role.referenceType, role: role.role, target: id }
  })
  return { header: header(frame), roleCount: frame.roles.length, participants: [...participants.values()], incidences }
}

const reconstruct = (kind: SemanticFrameRepresentationKind, body: unknown): Either.Either<unknown, SemanticFrameRepresentationError> => {
  if (kind === "direct_json") return exact(body, ["frame"]) ? Either.right(body["frame"]) : fail("INVALID_REPRESENTATION", "direct body requires exactly frame")
  if (!exact(body, kind === "incidence" ? ["header", "roleCount", "participants", "incidences"] : ["header", "roleCount", "columns", "rows"]) || !exact(body["header"], ["event", "stateRevision", "relation", "priorEvidence", "frameSha256"]) || !integer(body["roleCount"])) return fail("INVALID_REPRESENTATION", "incomplete header or role count")
  const roles: unknown[] = []
  if (kind === "role_table") {
    if (!Array.isArray(body["columns"]) || JSON.stringify(body["columns"]) !== JSON.stringify(columns) || !Array.isArray(body["rows"]) || body["rows"].length !== body["roleCount"]) return fail("INVALID_REPRESENTATION", "table columns or row count mismatch")
    for (const [ordinal, row] of body["rows"].entries()) {
      if (!Array.isArray(row) || row.length !== columns.length || row[0] !== ordinal) return fail("INVALID_REPRESENTATION", "tuple row arity or ordinal mismatch")
      roles.push({ referenceType: row[1], role: row[2], key: { schemaVersion: row[3], lineageId: row[4], atomUid: row[5], revisionId: row[6] }, owner: row[7], contentSha256: row[8], contentUtf8: row[9] })
    }
  } else {
    if (!Array.isArray(body["participants"]) || !Array.isArray(body["incidences"]) || body["incidences"].length !== body["roleCount"]) return fail("INVALID_REPRESENTATION", "incidence count mismatch")
    const participants = new Map<string, Record<string, unknown>>()
    for (const entry of body["participants"]) {
      if (!exact(entry, ["id", "key", "owner", "contentSha256", "contentUtf8"]) || !text(entry["id"]) || !key(entry["key"]) || participants.has(entry["id"])) return fail("INVALID_REPRESENTATION", "invalid or repeated participant")
      const decodedKey = Schema.decodeUnknownEither(CanonicalAtomV2KeySchema)(entry["key"])
      if (Either.isLeft(decodedKey) || canonicalAtomV2KeyId(decodedKey.right) !== entry["id"]) return fail("INVALID_REPRESENTATION", "participant id does not match endpoint key")
      participants.set(entry["id"], entry)
    }
    const used = new Set<string>()
    for (const [ordinal, entry] of body["incidences"].entries()) {
      if (!exact(entry, ["ordinal", "referenceType", "role", "target"]) || entry["ordinal"] !== ordinal || !text(entry["target"])) return fail("INVALID_REPRESENTATION", "incidence ordinal or target mismatch")
      const participant = participants.get(entry["target"])
      if (participant === undefined) return fail("INVALID_REPRESENTATION", "incidence has a dangling endpoint")
      used.add(entry["target"])
      roles.push({ referenceType: entry["referenceType"], role: entry["role"], key: participant["key"], owner: participant["owner"], contentSha256: participant["contentSha256"], contentUtf8: participant["contentUtf8"] })
    }
    if (used.size !== participants.size) return fail("INVALID_REPRESENTATION", "unreferenced participant is outside this frame")
  }
  return Either.right({ ...body["header"], roles })
}

export const decodeSemanticFrameRepresentationBytes = (kind: SemanticFrameRepresentationKind, bytes: Uint8Array): Either.Either<SemanticReadFrame, SemanticFrameRepresentationError> => {
  if (!kinds.includes(kind)) return fail("INVALID_REPRESENTATION", "unknown representation kind")
  const parsed = decodeCanonicalJsonBytes(bytes)
  if (Either.isLeft(parsed)) return fail("CANONICAL_JSON", parsed.left.detail)
  const encoded = canonical(parsed.right)
  if (Either.isLeft(encoded)) return Either.left(encoded.left)
  if (encoded.right.byteLength !== bytes.byteLength || !encoded.right.every((value, index) => value === bytes[index])) return fail("CANONICAL_JSON", "representation bytes must use the declared canonical encoding")
  const value = parsed.right
  if (!exact(value, ["schema", "kind", "sourceCanonicalSha256", "body"]) || value["schema"] !== contract || value["kind"] !== kind || !digest(value["sourceCanonicalSha256"])) return fail("INVALID_REPRESENTATION", "invalid representation envelope")
  const reconstructed = reconstruct(kind, value["body"])
  if (Either.isLeft(reconstructed)) return Either.left(reconstructed.left)
  if (!validFrame(reconstructed.right)) return fail("INVALID_FRAME", "frame structure, content digest, endpoint consistency or evidence fields are invalid")
  const canonicalFrame = canonical(reconstructed.right)
  if (Either.isLeft(canonicalFrame)) return Either.left(canonicalFrame.left)
  if (hash(canonicalFrame.right) !== value["sourceCanonicalSha256"]) return fail("COMMITMENT_MISMATCH", "decoded frame differs from the declared canonical source value")
  // Legacy frameSha256 commits runtime JSON property order. Preserve it without
  // recomputing it under this different canonical encoding or authenticating it.
  return Either.right(freezeDeep(reconstructed.right))
}

export const decodeSemanticFrameRepresentation = (view: Pick<SemanticFrameRepresentation, "kind" | "payload">): Either.Either<SemanticReadFrame, SemanticFrameRepresentationError> =>
  Either.flatMap(canonical(view.payload), bytes => decodeSemanticFrameRepresentationBytes(view.kind, bytes))

export const encodeSemanticFrameRepresentation = (frame: SemanticReadFrame, kind: SemanticFrameRepresentationKind): Either.Either<SemanticFrameRepresentation, SemanticFrameRepresentationError> => {
  if (!kinds.includes(kind)) return fail("INVALID_REPRESENTATION", "unknown representation kind")
  const source = canonical(frame)
  if (Either.isLeft(source)) return Either.left(source.left)
  const parsed = decodeCanonicalJsonBytes(source.right)
  if (Either.isLeft(parsed) || !validFrame(parsed.right)) return fail("INVALID_FRAME", "source must be a complete content-bound semantic frame")
  const sourceCanonicalSha256 = hash(source.right)
  const payload = freezeDeep({ schema: contract, kind, sourceCanonicalSha256, body: makeBody(parsed.right, kind) })
  const bytes = canonical(payload)
  if (Either.isLeft(bytes)) return Either.left(bytes.left)
  const recovered = decodeSemanticFrameRepresentationBytes(kind, bytes.right)
  if (Either.isLeft(recovered)) return Either.left(recovered.left)
  return Either.right(Object.freeze({ kind, payload, bytes: bytes.right, sha256: hash(bytes.right), sourceCanonicalSha256, serializationBytes: bytes.right.byteLength, costScope: "SERIALIZATION_BYTES_ONLY" }))
}

export const compareSemanticFrameRepresentations = (frame: SemanticReadFrame): Either.Either<SemanticFrameRepresentationComparison, SemanticFrameRepresentationError> => {
  const encoded = Either.all((["direct_json", "incidence", "role_table"] as const).map(kind => encodeSemanticFrameRepresentation(frame, kind)))
  if (Either.isLeft(encoded)) return Either.left(encoded.left)
  return Either.right(Object.freeze({ representations: Object.freeze(encoded.right), sourceCanonicalSha256: encoded.right[0]!.sourceCanonicalSha256, fullRoundTripFidelity: true, conclusion: "NO_UNIVERSAL_MINIMUM_WINNER", excludedCosts: Object.freeze(["MODEL_TOKENS_NOT_MEASURED", "LATENCY_NOT_MEASURED", "INDEX_AND_UPDATE_NOT_MEASURED", "LEARNING_EFFICACY_NOT_MEASURED", "ENCODER_DECODER_DEPLOYMENT_AND_SHARED_SCHEMA_EXCLUDED"]) }))
}
