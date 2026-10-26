/** Bounded read-only public HTTP. No credential forwarding, redirects, subscriptions or retries. */
import { Effect } from "effect"
import { parseJson } from "./adaptive-domain.js"
import { checkEvidenceAccess, checkEvidenceObservation, crossrefSearchUrl, decideEvidenceAcquisition, decodeCrossrefHits,
  decodeEvidence, EvidenceAccessSchema, EvidenceNeedSchema, EvidenceTime, evidenceBytesHash, evidenceError, evidenceSourceId, type EvidenceObservation } from "./evidence-acquisition-domain.js"

export interface EvidenceHttpPorts {
  readonly fetch: typeof globalThis.fetch
  readonly now: () => string
}
const collect = (reader: ReadableStreamDefaultReader<Uint8Array>, maximum: number, chunks: ReadonlyArray<Uint8Array> = [], size = 0): Effect.Effect<Uint8Array, ReturnType<typeof evidenceError>> => Effect.gen(function* () {
  const next = yield* Effect.tryPromise({ try: () => reader.read(), catch: () => evidenceError("READ_FAILED", "Response stream failed; no partial evidence") })
  if (next.done) {
    const bytes = new Uint8Array(size)
    let offset = 0
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength }
    return bytes
  }
  if (size + next.value.byteLength > maximum) return yield* Effect.fail(evidenceError("BYTE_BUDGET", "Complete response exceeds the budget; no truncation"))
  if (chunks.length >= 4096) return yield* Effect.fail(evidenceError("CHUNK_BUDGET", "Response fragmentation exceeds the bounded read budget"))
  return yield* collect(reader, maximum, [...chunks, next.value], size + next.value.byteLength)
})

/** Each invocation is one acquisition step; the returned budget belongs to the next decision. */
export const acquireEvidence = (rawNeed: unknown, rawAccess: unknown, previous: EvidenceObservation | null,
  ports: EvidenceHttpPorts) => Effect.gen(function* () {
  const requested = yield* decodeEvidence(EvidenceNeedSchema, rawNeed)
  const cached = previous === null ? null : yield* checkEvidenceObservation(previous)
  const now = yield* decodeEvidence(EvidenceTime, yield* Effect.sync(ports.now))
  if (cached !== null && Date.parse(cached.fetchedAt) > Date.parse(now)) return yield* Effect.fail(evidenceError("CLOCK", "A future observation cannot establish freshness"))
  const stale = cached !== null && cached.url === requested.knownUrl && requested.maximumAgeMs !== undefined &&
    Date.parse(now) - Date.parse(cached.fetchedAt) >= requested.maximumAgeMs && ["MISSING", "STALE"].includes(requested.trigger)
  const decision = yield* decideEvidenceAcquisition(stale ? { ...requested, trigger: "STALE" } : requested)
  const { action, need } = decision
  if (action !== "SEARCH_EXTERNAL" && action !== "FETCH_SOURCE" && action !== "REVALIDATE")
    return { ...decision, observation: null, nextBudget: { remainingRequests: need.remainingRequests, noProgressRounds: need.noProgressRounds } }
  const access = yield* decodeEvidence(EvidenceAccessSchema, rawAccess)
  const query = action === "SEARCH_EXTERNAL" ? need.publicQuery : null
  const url = query === null ? need.knownUrl : crossrefSearchUrl(query)
  if (url === null) return yield* Effect.fail(evidenceError("INVALID", "Acquisition has no selected locator"))
  yield* checkEvidenceAccess(access, url, query, yield* Effect.sync(ports.now))
  if (cached !== null && cached.url !== url) return yield* Effect.fail(evidenceError("CACHE_MISMATCH", "Conditional read must bind the same URL"))
  const conditional = action === "REVALIDATE" && cached !== null ? cached : null
  const observation = yield* Effect.acquireUseRelease(Effect.sync(() => new AbortController()), controller => Effect.gen(function* () {
    const headers: Readonly<Record<string, string>> = { accept: query === null ? "text/plain, text/html, application/json" : "application/json",
      "user-agent": "HSWM-evidence-acquisition/1.0",
      ...(conditional?.etag ? { "if-none-match": conditional.etag } : conditional?.lastModified ? { "if-modified-since": conditional.lastModified } : {}) }
    const response = yield* Effect.tryPromise({
      try: () => ports.fetch(url, { method: "GET", headers, redirect: "error", credentials: "omit", signal: controller.signal }),
      catch: () => evidenceError("HTTP_FAILED", "Public GET failed; no automatic retry or empty-result claim")
    })
    if (response.redirected || response.url && response.url !== url) return yield* Effect.fail(evidenceError("REDIRECT", "Response moved outside the selected exact locator"))
    const fetchedAt = yield* Effect.sync(ports.now)
    yield* checkEvidenceAccess(access, url, query, fetchedAt)
    if (response.status === 304) {
      if (conditional === null || (!conditional.etag && !conditional.lastModified) ||
        response.headers.get("etag") !== null && response.headers.get("etag") !== conditional.etag)
        return yield* Effect.fail(evidenceError("CACHE_MISMATCH", "304 needs an exact stored representation and matching validator"))
      return yield* checkEvidenceObservation({ ...conditional, fetchedAt, httpStatus: 304 })
    }
    if (response.status !== 200 || response.body === null) return yield* Effect.fail(evidenceError("HTTP_STATUS", `GET returned ${response.status}; no source fact inferred`))
    const mediaType = (response.headers.get("content-type") ?? "").split(";")[0]?.trim().toLowerCase() ?? ""
    if (!["text/plain", "text/html", "application/json", "application/xml", "text/xml"].includes(mediaType))
      return yield* Effect.fail(evidenceError("MEDIA_TYPE", "Only complete UTF-8 text representations are supported"))
    const body = response.body
    const bytes = yield* Effect.acquireUseRelease(Effect.sync(() => body.getReader()), reader => collect(reader, access.maximumBytes), reader =>
      Effect.tryPromise({ try: () => reader.cancel(), catch: () => evidenceError("CLEANUP", "Read cleanup failed") }).pipe(Effect.timeout("1 second"), Effect.ignore))
    const bodyUtf8 = yield* Effect.try({ try: () => new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(bytes), catch: () => evidenceError("ENCODING", "Invalid UTF-8; no lossy evidence") })
    const search = query === null ? null : { provider: "crossref" as const, publicQuery: query, hits: yield* decodeCrossrefHits(yield* parseJson(bodyUtf8)) }
    const completedAt = yield* Effect.sync(ports.now)
    yield* checkEvidenceAccess(access, url, query, completedAt)
    return yield* checkEvidenceObservation({ contract: "hswm-evidence-observation/v1", sourceId: evidenceSourceId(url), url,
      kind: query === null ? "SOURCE" : "SEARCH_METADATA", fetchedAt: completedAt, httpStatus: 200, etag: response.headers.get("etag"), lastModified: response.headers.get("last-modified"),
      mediaType, bodySha256: evidenceBytesHash(bodyUtf8), bodyUtf8, search, truth: "NOT_EVALUATED", sufficiency: "NOT_EVALUATED" })
  }).pipe(Effect.timeoutFail({ duration: access.timeoutMs, onTimeout: () => evidenceError("TIMEOUT", "Read deadline exceeded; no automatic retry") })), controller => Effect.sync(() => controller.abort()))
  const noNovelHit = observation.search !== null && (observation.search.hits.length === 0 || cached?.search !== null && cached?.search !== undefined &&
    observation.search.hits.every(hit => cached.search?.hits.some(previousHit => previousHit.doi.toLowerCase() === hit.doi.toLowerCase())))
  return { ...decision, observation, nextBudget: { remainingRequests: need.remainingRequests - 1,
    noProgressRounds: cached?.bodySha256 === observation.bodySha256 || noNovelHit ? Math.min(16, need.noProgressRounds + 1) : 0 } }
})
