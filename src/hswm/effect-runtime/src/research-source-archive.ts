/** Bounded, private, content-addressed capture of a caller-provided source list. */
import { join, resolve } from "node:path"

import { Context, Data, Effect, Either } from "effect"

import { PosixFileSystem, type PosixIoError } from "./effect-posix-filesystem.js"
import { BoundedSubprocess } from "./effect-bounded-subprocess.js"
import {
  HSWM_RESEARCH_SOURCE_ARCHIVE_V1, RESEARCH_SOURCE_ARCHIVE_DEFAULT_MAXIMUM_BYTES, archiveManifestDigest, decodeResearchSourceManifest, sha256Hex, sourceKindAccepts, validateSourceUrl,
  type ArchiveManifestReceipt, type FailedSourceReceipt, type ResearchSourceManifest, type ResearchSourceManifestEntry,
  type SourceArchiveFailureCode, type SourceReceipt, type SourceResponseHeaders, type SuccessfulSourceReceipt
} from "./research-source-archive-domain.js"

export const RESEARCH_SOURCE_ARCHIVE_MAX_BYTES = RESEARCH_SOURCE_ARCHIVE_DEFAULT_MAXIMUM_BYTES
export const RESEARCH_SOURCE_ARCHIVE_TIMEOUT_MS = 30_000
export const RESEARCH_SOURCE_ARCHIVE_CONCURRENCY = 4
const MANIFEST_RECEIPT = "manifest.receipt.v1.json"
const INPUT_MANIFEST = "manifest.input.v1.json"
const encoder = new TextEncoder()
const decoder = new TextDecoder()

export class ResearchSourceArchiveError extends Data.TaggedError("ResearchSourceArchiveError")<{
  readonly detail: string
}> {}
export interface ResearchSourceHttpResponse {
  readonly status: number
  readonly finalUrl: string
  readonly headers: SourceResponseHeaders
  readonly bytes: Uint8Array
  readonly transport?: "native" | "curl"
}
export interface ResearchSourceHttpShape {
  /** Declared at the service boundary so failures before a response remain attributable. */
  readonly transport?: "native" | "curl"
  readonly get: (request: { readonly url: string; readonly timeoutMs: number; readonly maximumBytes: number }) => Effect.Effect<ResearchSourceHttpResponse, ResearchSourceArchiveError, BoundedSubprocess>
}
/** Injectable boundary: tests never make external requests. */
export class ResearchSourceHttp extends Context.Tag("hswm/ResearchSourceHttp")<ResearchSourceHttp, ResearchSourceHttpShape>() {}

const archiveError = (detail: string): ResearchSourceArchiveError => new ResearchSourceArchiveError({ detail })
const relevantHeaders = (headers: Headers): SourceResponseHeaders => Object.freeze({ contentType: headers.get("content-type"), etag: headers.get("etag"), lastModified: headers.get("last-modified") })
const collect = (reader: ReadableStreamDefaultReader<Uint8Array>, maximumBytes: number, chunks: ReadonlyArray<Uint8Array> = [], size = 0): Effect.Effect<Uint8Array, ResearchSourceArchiveError> => Effect.gen(function* () {
  const item = yield* Effect.tryPromise({ try: () => reader.read(), catch: () => archiveError("HTTP_FAILED") })
  if (item.done) { const all = new Uint8Array(size); let offset = 0; for (const chunk of chunks) { all.set(chunk, offset); offset += chunk.byteLength } return all }
  const next = size + item.value.byteLength
  if (next > maximumBytes) return yield* Effect.fail(archiveError("RESPONSE_TOO_LARGE"))
  return yield* collect(reader, maximumBytes, [...chunks, item.value], next)
})
const nativeGet = (request: { readonly url: string; readonly timeoutMs: number; readonly maximumBytes: number }): Effect.Effect<ResearchSourceHttpResponse, ResearchSourceArchiveError> =>
  Effect.acquireUseRelease(Effect.sync(() => new AbortController()), controller => Effect.gen(function* () {
    const response = yield* Effect.tryPromise({ try: () => fetch(request.url, { method: "GET", redirect: "follow", signal: controller.signal }), catch: () => archiveError("HTTP_FAILED") })
    const headers = relevantHeaders(response.headers)
    if (!response.ok || response.body === null) return yield* Effect.succeed(Object.freeze({ status: response.status, finalUrl: response.url, headers, bytes: new Uint8Array(), transport: "native" as const }))
    const bytes = yield* Effect.acquireUseRelease(Effect.sync(() => response.body!.getReader()), reader => collect(reader, request.maximumBytes), reader => Effect.tryPromise({ try: () => reader.cancel(), catch: () => archiveError("HTTP_FAILED") }).pipe(Effect.ignore))
    return Object.freeze({ status: response.status, finalUrl: response.url, headers, bytes, transport: "native" as const })
  }).pipe(Effect.timeoutFail({ duration: request.timeoutMs, onTimeout: () => archiveError("HTTP_TIMEOUT") })), controller => Effect.sync(() => controller.abort()))
export const NativeResearchSourceHttp: ResearchSourceHttpShape = Object.freeze({ transport: "native", get: nativeGet })
const curlHeadersAndBody = (bytes: Uint8Array): ResearchSourceHttpResponse | null => {
  let offset = 0; let status = -1; let headers: SourceResponseHeaders = Object.freeze({ contentType: null, etag: null, lastModified: null })
  while (decoder.decode(bytes.subarray(offset, Math.min(bytes.byteLength, offset + 8))).startsWith("HTTP/")) {
    let marker = -1
    for (let index = offset; index + 3 < bytes.byteLength; index += 1) if (bytes[index] === 13 && bytes[index + 1] === 10 && bytes[index + 2] === 13 && bytes[index + 3] === 10) { marker = index; break }
    if (marker < 0) return null
    const lines = decoder.decode(bytes.subarray(offset, marker)).split("\r\n"); const code = /^HTTP\/\S+\s+(\d{3})/.exec(lines[0] ?? "")
    if (code === null) return null; status = Number(code[1]); const fields = new Map<string, string>()
    for (const line of lines.slice(1)) { const colon = line.indexOf(":"); if (colon > 0) fields.set(line.slice(0, colon).toLowerCase(), line.slice(colon + 1).trim()) }
    headers = Object.freeze({ contentType: fields.get("content-type") ?? null, etag: fields.get("etag") ?? null, lastModified: fields.get("last-modified") ?? null }); offset = marker + 4
  }
  return status < 0 ? null : Object.freeze({ status, finalUrl: "", headers, bytes: bytes.subarray(offset), transport: "curl" as const })
}
const curlGet = (request: { readonly url: string; readonly timeoutMs: number; readonly maximumBytes: number }): Effect.Effect<ResearchSourceHttpResponse, ResearchSourceArchiveError, BoundedSubprocess> => Effect.gen(function* () {
  const subprocess = yield* BoundedSubprocess; const seconds = Math.max(1, Math.ceil(request.timeoutMs / 1000))
  const observed = yield* subprocess.observe({ argv: ["curl", "--disable", "--globoff", "--location", "--silent", "--show-error", "--dump-header", "-", "--output", "-", "--proto", "=http,https", "--proto-redir", "=http,https", "--max-redirs", "10", "--max-time", String(seconds), "--connect-timeout", String(seconds), "--max-filesize", String(request.maximumBytes), "--write-out", "%{stderr}__HSWM_FINAL_URL__%{url_effective}\\n", request.url], cwd: process.cwd(), environment: Object.fromEntries(Object.entries(process.env).flatMap(([key, value]) => value === undefined ? [] : [[key, value]])), timeoutMs: request.timeoutMs, maximumOutputBytes: request.maximumBytes + 1_048_576, killProcessGroup: true }).pipe(Effect.mapError(error => archiveError(error.detail)))
  if (observed.timedOut) return yield* Effect.fail(archiveError("HTTP_TIMEOUT")); if (observed.outputTruncated) return yield* Effect.fail(archiveError("RESPONSE_TOO_LARGE")); if (observed.launchError !== null || observed.signal !== null || observed.exitCode !== 0) return yield* Effect.fail(archiveError("HTTP_FAILED"))
  const parsed = curlHeadersAndBody(observed.stdout); const stderr = decoder.decode(observed.stderr); const marker = stderr.lastIndexOf("__HSWM_FINAL_URL__"); const finalUrl = marker < 0 ? undefined : stderr.slice(marker + "__HSWM_FINAL_URL__".length).trim().split("\n", 1)[0]
  if (parsed === null || typeof finalUrl !== "string" || finalUrl.length === 0) return yield* Effect.fail(archiveError("HTTP_FAILED"))
  if (parsed.bytes.byteLength > request.maximumBytes) return yield* Effect.fail(archiveError("RESPONSE_TOO_LARGE"))
  return Object.freeze({ ...parsed, finalUrl })
})
export const CurlResearchSourceHttp: ResearchSourceHttpShape = Object.freeze({ transport: "curl", get: curlGet })

const receiptPath = (root: string, id: string): string => join(root, "receipts", `${id}.receipt.v1.json`)
const blobPath = (root: string, digest: string): string => join(root, "blobs", "sha256", digest)
const json = (value: unknown): Uint8Array => encoder.encode(`${JSON.stringify(value, null, 2)}\n`)
const io = (error: PosixIoError): ResearchSourceArchiveError => archiveError(error.detail)
const decodeReceipt = (bytes: Uint8Array): Effect.Effect<SourceReceipt, ResearchSourceArchiveError> => Effect.try({ try: () => JSON.parse(decoder.decode(bytes)) as SourceReceipt, catch: () => archiveError("existing receipt is invalid JSON") })
const record = (value: unknown): value is Readonly<Record<string, unknown>> => typeof value === "object" && value !== null && !Array.isArray(value)
const sha = (value: unknown): value is string => typeof value === "string" && /^[a-f0-9]{64}$/.test(value)
const receiptIsWellFormed = (value: unknown): value is SourceReceipt => {
  if (!record(value) || typeof value["id"] !== "string" || typeof value["originalUrl"] !== "string" || typeof value["requestedUrl"] !== "string" || typeof value["retrievedAt"] !== "string" || !record(value["responseHeaders"])) return false
  if (value["status"] === "FAILED") return typeof value["failure"] === "string" && (value["finalUrl"] === null || typeof value["finalUrl"] === "string")
  return value["status"] === "ARCHIVED" && typeof value["finalUrl"] === "string" && sha(value["sha256"]) && typeof value["size"] === "number" && Number.isSafeInteger(value["size"]) && value["size"] > 0 && value["blobPath"] === `blobs/sha256/${value["sha256"]}`
}
const existingReceipt = (root: string, id: string): Effect.Effect<SourceReceipt | null, ResearchSourceArchiveError, PosixFileSystem> => Effect.gen(function* () {
  const fs = yield* PosixFileSystem
  const read = yield* fs.readRegularBounded(receiptPath(root, id), { maximumBytes: 256 * 1024, minimumBytes: 1, requiredMode: 0o400, operation: "read source archive receipt" }).pipe(Effect.either)
  if (Either.isLeft(read)) { if (read.left.code === "ENOENT") return null; return yield* Effect.fail(io(read.left)) }
  return yield* decodeReceipt(read.right.bytes)
})
const failure = (entry: ResearchSourceManifestEntry, code: SourceArchiveFailureCode, detail: string, finalUrl: string | null, headers: SourceResponseHeaders, retrievedAt: string, transport: "native" | "curl" = "native"): FailedSourceReceipt => Object.freeze({ status: "FAILED", id: entry.id, originalUrl: entry.url, requestedUrl: entry.url, finalUrl, retrievedAt, responseHeaders: headers, failure: code, detail, expectedKind: entry.expectedKind, maximumBytes: entry.maximumBytes, transport, metadata: entry.metadata })
const emptyHeaders: SourceResponseHeaders = Object.freeze({ contentType: null, etag: null, lastModified: null })
const receiptBindsEntry = (receipt: SourceReceipt, entry: ResearchSourceManifestEntry): boolean => receiptIsWellFormed(receipt) && receipt.id === entry.id && receipt.originalUrl === entry.url && receipt.requestedUrl === entry.url && receipt.expectedKind === entry.expectedKind && (receipt.maximumBytes ?? RESEARCH_SOURCE_ARCHIVE_MAX_BYTES) === entry.maximumBytes && JSON.stringify(receipt.metadata) === JSON.stringify(entry.metadata)
const validateReusablePartialReceipt = (root: string, entry: ResearchSourceManifestEntry, receipt: SourceReceipt): Effect.Effect<boolean, ResearchSourceArchiveError, PosixFileSystem> => Effect.gen(function* () {
  if (!receiptBindsEntry(receipt, entry)) return false
  if (receipt.status === "FAILED") return true
  const fs = yield* PosixFileSystem
  const blob = yield* fs.readRegularBounded(join(root, receipt.blobPath), { maximumBytes: entry.maximumBytes, minimumBytes: 1, requiredMode: 0o400, operation: "validate partial source archive blob" }).pipe(Effect.either)
  return Either.isRight(blob) && blob.right.bytes.byteLength === receipt.size && sha256Hex(blob.right.bytes) === receipt.sha256
})
/** A small conservative deny-list avoids preserving known bot/challenge pages as sources. */
const challengePage = (contentType: string, bytes: Uint8Array): boolean => {
  const normalized = contentType.toLowerCase()
  if (!normalized.startsWith("text/html") && !normalized.startsWith("application/xhtml+xml")) return false
  const prefix = decoder.decode(bytes.subarray(0, Math.min(bytes.byteLength, 1_048_576))).toLowerCase()
  const title = /<title[^>]*>([^<]*)<\/title>/i.exec(prefix)?.[1]?.trim() ?? ""
  return ["just a moment...", "access denied", "verify you are human", "checking your browser", "attention required! | cloudflare", "verifying your browser | openreview", "client challenge", "checking your browser - recaptcha"].includes(title)
}
const writeReceipt = (root: string, receipt: SourceReceipt): Effect.Effect<SourceReceipt, ResearchSourceArchiveError, PosixFileSystem> => Effect.gen(function* () {
  const fs = yield* PosixFileSystem
  yield* fs.writeExclusive(receiptPath(root, receipt.id), json(receipt), { mode: 0o600, finalMode: 0o400, sync: true, operation: "write source archive receipt" }).pipe(Effect.mapError(io))
  return receipt
})
const archiveOne = (root: string, entry: ResearchSourceManifestEntry): Effect.Effect<SourceReceipt, ResearchSourceArchiveError, PosixFileSystem | ResearchSourceHttp | BoundedSubprocess> => Effect.gen(function* () {
  const already = yield* existingReceipt(root, entry.id); if (already !== null) { if (!(yield* validateReusablePartialReceipt(root, entry, already))) return yield* Effect.fail(archiveError(`partial receipt for ${entry.id} is invalid or does not bind the pinned source`)); return already }
  const http = yield* ResearchSourceHttp
  const observed = yield* http.get({ url: entry.url, timeoutMs: RESEARCH_SOURCE_ARCHIVE_TIMEOUT_MS, maximumBytes: entry.maximumBytes }).pipe(Effect.either)
  const retrievedAt = new Date(yield* Effect.clockWith(clock => clock.currentTimeMillis)).toISOString()
  if (Either.isLeft(observed)) {
    const code: SourceArchiveFailureCode = observed.left.detail === "HTTP_TIMEOUT" ? "HTTP_TIMEOUT" : observed.left.detail === "RESPONSE_TOO_LARGE" ? "RESPONSE_TOO_LARGE" : "HTTP_FAILED"
    return yield* writeReceipt(root, failure(entry, code, observed.left.detail, null, emptyHeaders, retrievedAt, http.transport ?? "native"))
  }
  const response = observed.right
  const finalUrl = validateSourceUrl(response.finalUrl)
  if (Either.isLeft(finalUrl)) return yield* writeReceipt(root, failure(entry, "HTTP_FAILED", "response final URL is not credential-free HTTP(S)", null, response.headers, retrievedAt, http.transport ?? "native"))
  const transport = response.transport ?? "native"
  if (response.status < 200 || response.status > 299) return yield* writeReceipt(root, failure(entry, "HTTP_STATUS", `HTTP_${response.status}`, finalUrl.right, response.headers, retrievedAt, transport))
  if (response.headers.contentType === null) return yield* writeReceipt(root, failure(entry, "CONTENT_TYPE_MISSING", "successful response lacks content-type", finalUrl.right, response.headers, retrievedAt, transport))
  if (!sourceKindAccepts(entry.expectedKind, response.headers.contentType)) return yield* writeReceipt(root, failure(entry, "CONTENT_TYPE_MISMATCH", `expected ${entry.expectedKind}, received ${response.headers.contentType}`, finalUrl.right, response.headers, retrievedAt, transport))
  if (response.bytes.byteLength === 0) return yield* writeReceipt(root, failure(entry, "CONTENT_TYPE_MISMATCH", "successful source response is empty", finalUrl.right, response.headers, retrievedAt, transport))
  if (challengePage(response.headers.contentType, response.bytes)) return yield* writeReceipt(root, failure(entry, "HTTP_CHALLENGE", "recognized access challenge page", finalUrl.right, response.headers, retrievedAt, transport))
  const receivedType = response.headers.contentType.toLowerCase().split(";", 1)[0]?.trim() ?? ""
  if ((receivedType === "application/pdf" || (receivedType === "application/octet-stream" && entry.expectedKind === "pdf")) && (response.bytes.byteLength < 5 || decoder.decode(response.bytes.subarray(0, 5)) !== "%PDF-")) return yield* writeReceipt(root, failure(entry, "CONTENT_TYPE_MISMATCH", "PDF response lacks PDF signature", finalUrl.right, response.headers, retrievedAt, transport))
  const digest = sha256Hex(response.bytes); const relative = `blobs/sha256/${digest}`; const fs = yield* PosixFileSystem
  const write = yield* fs.writeExclusive(blobPath(root, digest), response.bytes, { mode: 0o600, finalMode: 0o400, sync: true, operation: "write source archive blob" }).pipe(Effect.either)
  if (Either.isLeft(write)) {
    if (write.left.code !== "EEXIST") return yield* Effect.fail(io(write.left))
    const existing = yield* fs.readRegularBounded(blobPath(root, digest), { maximumBytes: entry.maximumBytes, minimumBytes: 1, requiredMode: 0o400, operation: "verify existing source archive blob" }).pipe(Effect.mapError(io))
    if (existing.bytes.byteLength !== response.bytes.byteLength || sha256Hex(existing.bytes) !== digest) return yield* Effect.fail(archiveError("existing content-addressed blob differs from its SHA-256 path"))
  }
  const receipt: SuccessfulSourceReceipt = Object.freeze({ status: "ARCHIVED", id: entry.id, originalUrl: entry.url, requestedUrl: entry.url, finalUrl: finalUrl.right, retrievedAt, responseHeaders: response.headers, sha256: digest, size: response.bytes.byteLength, blobPath: relative, expectedKind: entry.expectedKind, maximumBytes: entry.maximumBytes, transport, metadata: entry.metadata })
  return yield* writeReceipt(root, receipt)
})

export interface ArchiveRun { readonly root: string; readonly manifest: ArchiveManifestReceipt; readonly resumed: boolean }
const ensureDirectories = (root: string): Effect.Effect<void, ResearchSourceArchiveError, PosixFileSystem> => Effect.gen(function* () { const fs = yield* PosixFileSystem; for (const path of [root, join(root, "blobs"), join(root, "blobs", "sha256"), join(root, "receipts")]) yield* fs.makeDirectory(path, { mode: 0o700, recursive: true, operation: "create source archive directory" }).pipe(Effect.mapError(io)) })
const readManifestReceipt = (root: string): Effect.Effect<ArchiveManifestReceipt | null, ResearchSourceArchiveError, PosixFileSystem> => Effect.gen(function* () { const fs = yield* PosixFileSystem; const read = yield* fs.readRegularBounded(join(root, MANIFEST_RECEIPT), { maximumBytes: 4 * 1024 * 1024, minimumBytes: 1, requiredMode: 0o400, operation: "read archive manifest receipt" }).pipe(Effect.either); if (Either.isLeft(read)) { if (read.left.code === "ENOENT") return null; return yield* Effect.fail(io(read.left)) }; return yield* Effect.try({ try: () => JSON.parse(decoder.decode(read.right.bytes)) as ArchiveManifestReceipt, catch: () => archiveError("archive manifest receipt is invalid JSON") }) })
const readPinnedManifest = (root: string): Effect.Effect<ResearchSourceManifest, ResearchSourceArchiveError, PosixFileSystem> => Effect.gen(function* () { const fs = yield* PosixFileSystem; const read = yield* fs.readRegularBounded(join(root, INPUT_MANIFEST), { maximumBytes: 4 * 1024 * 1024, minimumBytes: 1, requiredMode: 0o400, operation: "read pinned source archive input manifest" }).pipe(Effect.mapError(io)); const decoded = decodeResearchSourceManifest(decoder.decode(read.bytes)); return Either.isLeft(decoded) ? yield* Effect.fail(archiveError(decoded.left.detail)) : decoded.right })
const pinInputManifest = (root: string, input: Uint8Array): Effect.Effect<void, ResearchSourceArchiveError, PosixFileSystem> => Effect.gen(function* () {
  const fs = yield* PosixFileSystem; const path = join(root, INPUT_MANIFEST)
  const written = yield* fs.writeExclusive(path, input, { mode: 0o600, finalMode: 0o400, sync: true, operation: "pin source archive input manifest" }).pipe(Effect.either)
  if (Either.isRight(written)) return
  if (written.left.code !== "EEXIST") return yield* Effect.fail(io(written.left))
  const present = yield* fs.readRegularBounded(path, { maximumBytes: 4 * 1024 * 1024, minimumBytes: 1, requiredMode: 0o400, operation: "read pinned source archive input manifest" }).pipe(Effect.mapError(io))
  if (present.bytes.byteLength !== input.byteLength || sha256Hex(present.bytes) !== sha256Hex(input)) return yield* Effect.fail(archiveError("pinned input manifest differs; immutable archive cannot be extended or replaced"))
})
export const archiveResearchSources = (rootInput: string, sourceManifestJson: string): Effect.Effect<ArchiveRun, ResearchSourceArchiveError, PosixFileSystem | ResearchSourceHttp | BoundedSubprocess> => Effect.gen(function* () {
  const decoded = decodeResearchSourceManifest(sourceManifestJson); if (Either.isLeft(decoded)) return yield* Effect.fail(archiveError(decoded.left.detail))
  const root = resolve(rootInput); const manifestDigest = archiveManifestDigest(sourceManifestJson); yield* ensureDirectories(root); yield* pinInputManifest(root, encoder.encode(sourceManifestJson))
  const prior = yield* readManifestReceipt(root)
  if (prior !== null) { if (prior.schema !== HSWM_RESEARCH_SOURCE_ARCHIVE_V1 || prior.manifestSha256 !== manifestDigest) return yield* Effect.fail(archiveError("existing archive manifest differs; immutable archive cannot be extended or replaced")); const checked = yield* verifyResearchSourceArchive(root); if (!checked.valid) return yield* Effect.fail(archiveError("existing archive integrity verification failed")); return { root, manifest: prior, resumed: true } }
  const receipts = yield* Effect.forEach(decoded.right.sources, entry => archiveOne(root, entry), { concurrency: RESEARCH_SOURCE_ARCHIVE_CONCURRENCY })
  const manifest: ArchiveManifestReceipt = Object.freeze({ schema: HSWM_RESEARCH_SOURCE_ARCHIVE_V1, manifestSha256: manifestDigest, createdAt: new Date(yield* Effect.clockWith(clock => clock.currentTimeMillis)).toISOString(), receipts: Object.freeze(receipts) })
  const fs = yield* PosixFileSystem; yield* fs.writeExclusive(join(root, MANIFEST_RECEIPT), json(manifest), { mode: 0o600, finalMode: 0o400, sync: true, operation: "write archive manifest receipt" }).pipe(Effect.mapError(io))
  return { root, manifest, resumed: false }
})

export interface ArchiveVerification { readonly root: string; readonly receipts: ReadonlyArray<{ readonly id: string; readonly valid: boolean; readonly detail: string }>; readonly valid: boolean }
export const verifyResearchSourceArchive = (rootInput: string): Effect.Effect<ArchiveVerification, ResearchSourceArchiveError, PosixFileSystem> => Effect.gen(function* () {
  const root = resolve(rootInput); const manifest = yield* readManifestReceipt(root); if (manifest === null) return yield* Effect.fail(archiveError("archive manifest receipt is absent")); const pinned = yield* readPinnedManifest(root); const fs = yield* PosixFileSystem
  if (manifest.schema !== HSWM_RESEARCH_SOURCE_ARCHIVE_V1 || !sha(manifest.manifestSha256) || !Array.isArray(manifest.receipts) || manifest.manifestSha256 !== archiveManifestDigest(decoder.decode((yield* fs.readRegularBounded(join(root, INPUT_MANIFEST), { maximumBytes: 4 * 1024 * 1024, minimumBytes: 1, requiredMode: 0o400, operation: "rehash pinned source manifest" }).pipe(Effect.mapError(io))).bytes)) || manifest.receipts.length !== pinned.sources.length || new Set(manifest.receipts.map(receipt => receipt.id)).size !== pinned.sources.length || !manifest.receipts.every(receiptIsWellFormed)) return Object.freeze({ root, receipts: Object.freeze([{ id: "archive", valid: false, detail: "manifest receipt or pinned source membership is malformed" }]), valid: false })
  const expected = new Map<string, ResearchSourceManifestEntry>(pinned.sources.map(source => [source.id, source]))
  const results: ReadonlyArray<{ readonly id: string; readonly valid: boolean; readonly detail: string }> = yield* Effect.forEach(manifest.receipts, receipt => {
    const source = expected.get(receipt.id)
    const receiptMaximumBytes = receipt.maximumBytes ?? RESEARCH_SOURCE_ARCHIVE_MAX_BYTES
    if (source === undefined || source.url !== receipt.originalUrl || source.url !== receipt.requestedUrl || source.expectedKind !== receipt.expectedKind || source.maximumBytes !== receiptMaximumBytes || JSON.stringify(source.metadata) !== JSON.stringify(receipt.metadata)) return Effect.succeed(Object.freeze({ id: receipt.id, valid: false, detail: "receipt does not bind the pinned source entry" }))
    return Effect.gen(function* () {
      const perSource = yield* fs.readRegularBounded(receiptPath(root, receipt.id), { maximumBytes: 256 * 1024, minimumBytes: 1, requiredMode: 0o400, operation: "verify per-source archive receipt" }).pipe(Effect.map(read => read.bytes), Effect.flatMap(decodeReceipt), Effect.either)
      if (Either.isLeft(perSource) || JSON.stringify(perSource.right) !== JSON.stringify(receipt) || !receiptIsWellFormed(perSource.right)) return Object.freeze({ id: receipt.id, valid: false, detail: "per-source receipt differs or is invalid" })
      if (receipt.status === "FAILED") return Object.freeze({ id: receipt.id, valid: true, detail: `recorded failure: ${receipt.failure}` })
      return yield* fs.readRegularBounded(join(root, receipt.blobPath), { maximumBytes: receiptMaximumBytes, minimumBytes: 0, requiredMode: 0o400, operation: "verify source archive blob" }).pipe(Effect.map(read => Object.freeze({ id: receipt.id, valid: read.bytes.byteLength === receipt.size && sha256Hex(read.bytes) === receipt.sha256, detail: "blob digest and size" })), Effect.catchAll(error => Effect.succeed(Object.freeze({ id: receipt.id, valid: false, detail: error.detail }))))
    })
  }, { concurrency: RESEARCH_SOURCE_ARCHIVE_CONCURRENCY })
  return Object.freeze({ root, receipts: Object.freeze(results), valid: results.every(result => result.valid) })
})
