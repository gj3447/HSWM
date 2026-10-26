/** Acquisition decisions are separate from relevance, source truth and learned activation. */
import { createHash } from "node:crypto"
import { Either, Schema } from "effect"
import { contextError, contextHash } from "./semantic-context-domain.js"

const text = (max: number) => Schema.NonEmptyString.pipe(Schema.maxLength(max), Schema.filter(s => s.trim().length > 0))
export const evidenceError = (code: string, detail: string) => contextError(`EVIDENCE_${code}`, detail)
export const decodeEvidence = <A, I>(schema: Schema.Schema<A, I>, raw: unknown) =>
  Schema.decodeUnknownEither(schema)(raw, { onExcessProperty: "error" }).pipe(Either.mapLeft(() => evidenceError("INVALID", "Malformed bounded acquisition contract")))
export const evidenceBytesHash = (body: string) => createHash("sha256").update(body, "utf8").digest("hex")
export const PublicEvidenceUrl = text(2048).pipe(Schema.filter(value => {
  try {
    const url = new URL(value)
    return url.href === value && url.protocol === "https:" && !url.username && !url.password && !url.hash
  } catch { return false }
}))
export const EvidenceTime = text(32).pipe(Schema.filter(value => Number.isFinite(Date.parse(value)) && new Date(value).toISOString() === value))
const sha = Schema.String.pipe(Schema.pattern(/^[a-f0-9]{64}$/))
export const EvidenceNeedSchema = Schema.Struct({
  gapId: text(128), question: text(512),
  trigger: Schema.Literal("MISSING", "STALE", "CONFLICT", "EXPLICIT_SEARCH", "PRIVATE_INPUT", "REASONING_FAILURE"),
  sufficiency: Schema.Literal("SUFFICIENT", "INSUFFICIENT", "CONFLICTED", "UNKNOWN"),
  knownUrl: Schema.NullOr(PublicEvidenceUrl), publicQuery: Schema.NullOr(text(256)),
  localAvailable: Schema.Boolean,
  maximumAgeMs: Schema.optional(Schema.Number.pipe(Schema.int(), Schema.between(1, 31536000000))),
  remainingRequests: Schema.Number.pipe(Schema.int(), Schema.between(0, 16)),
  noProgressRounds: Schema.Number.pipe(Schema.int(), Schema.between(0, 16))
})
export type EvidenceNeed = typeof EvidenceNeedSchema.Type
export type AcquisitionAction = "USE_CURRENT" | "LOCAL_READ" | "FETCH_SOURCE" | "SEARCH_EXTERNAL" | "REVALIDATE" | "ASK_HUMAN" | "DIAGNOSE_REASONING" | "DEFER"
/** Caller-supplied sufficiency is an assessment, never inferred from scores or HTTP success. */
export const decideEvidenceAcquisition = (raw: unknown) => decodeEvidence(EvidenceNeedSchema, raw).pipe(Either.map(need => {
  const action: AcquisitionAction = need.trigger === "PRIVATE_INPUT" ? "ASK_HUMAN"
    : need.trigger === "REASONING_FAILURE" ? "DIAGNOSE_REASONING"
    : need.sufficiency === "SUFFICIENT" && need.trigger === "MISSING" ? "USE_CURRENT"
    : need.localAvailable && need.trigger === "MISSING" && need.sufficiency !== "CONFLICTED" ? "LOCAL_READ"
    : need.remainingRequests === 0 || need.noProgressRounds >= 2 ? "DEFER"
    : need.trigger === "EXPLICIT_SEARCH" || need.trigger === "CONFLICT" || need.sufficiency === "CONFLICTED"
      ? need.publicQuery === null ? "ASK_HUMAN" : "SEARCH_EXTERNAL"
    : need.knownUrl !== null ? need.trigger === "STALE" ? "REVALIDATE" : "FETCH_SOURCE"
    : need.publicQuery !== null ? "SEARCH_EXTERNAL" : "ASK_HUMAN"
  return { action, need, sufficiency: need.sufficiency, budgetIsEvidenceOfAbsence: false as const }
}))

/** A concrete scholarly provider, not a claim of whole-web coverage. Queries are explicitly public. */
export const crossrefSearchUrl = (query: string): string => {
  const url = new URL("https://api.crossref.org/works")
  url.searchParams.set("query.bibliographic", query)
  url.searchParams.set("rows", "3")
  url.searchParams.set("select", "DOI,title,URL,publisher")
  return url.href
}
export const EvidenceAccessSchema = Schema.Struct({
  projectId: text(256), linkId: text(256), resource: text(256), purpose: text(512),
  recipient: text(256), expiresAt: EvidenceTime, revoked: Schema.Boolean,
  allowedUrls: Schema.Array(PublicEvidenceUrl).pipe(Schema.minItems(1), Schema.maxItems(16)),
  publicQueries: Schema.Array(text(256)).pipe(Schema.maxItems(8)),
  maximumBytes: Schema.Number.pipe(Schema.int(), Schema.between(1, 262144)),
  timeoutMs: Schema.Number.pipe(Schema.int(), Schema.between(1, 30000))
})
export type EvidenceAccess = typeof EvidenceAccessSchema.Type
/** Access comes from the caller, never from a search hit, source body or graph observation. */
export const checkEvidenceAccess = (access: EvidenceAccess, url: string, query: string | null, now: string) =>
  decodeEvidence(EvidenceTime, now).pipe(Either.flatMap(() => access.revoked || Date.parse(access.expiresAt) <= Date.parse(now) ||
    !access.allowedUrls.includes(url) || (query !== null && !access.publicQueries.includes(query))
    ? Either.left(evidenceError("NOT_READY", "Caller-selected unexpired URL and public-query scope required")) : Either.right(undefined)))

export const EvidenceObservationSchema = Schema.Struct({
  contract: Schema.Literal("hswm-evidence-observation/v1"), sourceId: sha, url: PublicEvidenceUrl,
  kind: Schema.Literal("SOURCE", "SEARCH_METADATA"), fetchedAt: EvidenceTime,
  httpStatus: Schema.Literal(200, 304), etag: Schema.NullOr(text(1024)), lastModified: Schema.NullOr(text(128)),
  mediaType: text(128), bodySha256: sha, bodyUtf8: text(262144),
  search: Schema.NullOr(Schema.Struct({ provider: Schema.Literal("crossref"), publicQuery: text(256),
    hits: Schema.Array(Schema.Struct({ doi: text(256), title: text(2048), url: PublicEvidenceUrl, publisher: text(512) })).pipe(Schema.maxItems(3)) })),
  truth: Schema.Literal("NOT_EVALUATED"), sufficiency: Schema.Literal("NOT_EVALUATED")
})
export type EvidenceObservation = typeof EvidenceObservationSchema.Type
export const evidenceSourceId = (url: string) => contextHash({ origin: url })
export const checkEvidenceObservation = (raw: unknown) => decodeEvidence(EvidenceObservationSchema, raw).pipe(Either.flatMap(observation => {
  if (observation.sourceId !== evidenceSourceId(observation.url) || observation.bodySha256 !== evidenceBytesHash(observation.bodyUtf8) ||
    new TextEncoder().encode(observation.bodyUtf8).byteLength > 262144 ||
    (observation.kind === "SOURCE" ? observation.search !== null : observation.search === null || observation.url !== crossrefSearchUrl(observation.search.publicQuery)))
    return Either.left(evidenceError("INTEGRITY", "Origin, complete bytes or provider binding does not match"))
  return Either.right(observation)
}))

const CrossrefResponse = Schema.Struct({ status: Schema.Literal("ok"), message: Schema.Struct({ items: Schema.Array(Schema.Struct({
  DOI: text(256), title: Schema.Array(text(2048)).pipe(Schema.minItems(1)), URL: PublicEvidenceUrl, publisher: text(512)
})).pipe(Schema.maxItems(3)) }) })
/** A metadata hit supplies a locator. It is not a read of the paper or independent corroboration. */
export const decodeCrossrefHits = (raw: unknown) => Schema.decodeUnknownEither(CrossrefResponse)(raw).pipe(
  Either.mapLeft(() => evidenceError("SEARCH_RESPONSE", "Expected bounded Crossref metadata; no guessed result")),
  Either.map(value => value.message.items.map(item => ({ doi: item.DOI, title: item.title.join(" — "), url: item.URL, publisher: item.publisher }))))
