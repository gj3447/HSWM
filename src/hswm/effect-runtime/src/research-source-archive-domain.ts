/** Immutable request and receipt values for the private research source archive. */
import { createHash } from "node:crypto"

import { Data, Either } from "effect"

export const HSWM_RESEARCH_SOURCE_ARCHIVE_V1 = "hswm-research-source-archive/v1" as const
export const RESEARCH_SOURCE_ARCHIVE_MAX_SOURCES = 4_096
export const RESEARCH_SOURCE_ARCHIVE_DEFAULT_MAXIMUM_BYTES = 32 * 1024 * 1024
export const RESEARCH_SOURCE_ARCHIVE_MAXIMUM_BYTES_CAP = 256 * 1024 * 1024

export class ResearchSourceArchiveDomainError extends Data.TaggedError("ResearchSourceArchiveDomainError")<{
  readonly detail: string
}> {}

export type SourceKind = "pdf" | "html" | "text" | "any"
export interface ResearchSourceManifestEntry {
  readonly id: string
  readonly url: string
  readonly expectedKind: SourceKind
  /** A source-specific bound; higher values require explicit caller declaration. */
  readonly maximumBytes: number
  /** Caller-owned descriptive fields, copied verbatim into the immutable receipt. */
  readonly metadata: Readonly<Record<string, unknown>>
}
export interface ResearchSourceManifest {
  readonly schema: typeof HSWM_RESEARCH_SOURCE_ARCHIVE_V1
  readonly sources: ReadonlyArray<ResearchSourceManifestEntry>
}

export interface SourceResponseHeaders {
  readonly contentType: string | null
  readonly etag: string | null
  readonly lastModified: string | null
}
export type SourceArchiveFailureCode =
  | "HTTP_STATUS" | "HTTP_CHALLENGE" | "CONTENT_TYPE_MISMATCH" | "CONTENT_TYPE_MISSING" | "RESPONSE_TOO_LARGE" | "HTTP_TIMEOUT" | "HTTP_FAILED"
export interface SuccessfulSourceReceipt {
  readonly status: "ARCHIVED"
  readonly id: string
  readonly originalUrl: string
  readonly requestedUrl: string
  readonly finalUrl: string
  readonly retrievedAt: string
  readonly responseHeaders: SourceResponseHeaders
  readonly sha256: string
  readonly size: number
  readonly blobPath: string
  readonly expectedKind: SourceKind
  /** Absent only in archives created before the source-specific bound field; then default applies. */
  readonly maximumBytes?: number
  /** Absent receipts predate transport recording and mean native fetch. */
  readonly transport?: "native" | "curl"
  readonly metadata: Readonly<Record<string, unknown>>
}
export interface FailedSourceReceipt {
  readonly status: "FAILED"
  readonly id: string
  readonly originalUrl: string
  readonly requestedUrl: string
  readonly finalUrl: string | null
  readonly retrievedAt: string
  readonly responseHeaders: SourceResponseHeaders
  readonly failure: SourceArchiveFailureCode
  readonly detail: string
  readonly expectedKind: SourceKind
  readonly maximumBytes?: number
  readonly transport?: "native" | "curl"
  readonly metadata: Readonly<Record<string, unknown>>
}
export type SourceReceipt = SuccessfulSourceReceipt | FailedSourceReceipt
export interface ArchiveManifestReceipt {
  readonly schema: typeof HSWM_RESEARCH_SOURCE_ARCHIVE_V1
  readonly manifestSha256: string
  readonly createdAt: string
  readonly receipts: ReadonlyArray<SourceReceipt>
}

const sourceKinds: ReadonlySet<string> = new Set(["pdf", "html", "text", "any"])
const idPattern = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/
const plainRecord = (value: unknown): value is Readonly<Record<string, unknown>> => typeof value === "object" && value !== null && !Array.isArray(value)
const jsonClone = (value: unknown): Either.Either<Readonly<Record<string, unknown>>, ResearchSourceArchiveDomainError> => {
  if (!plainRecord(value)) return Either.left(new ResearchSourceArchiveDomainError({ detail: "metadata must be an object" }))
  try {
    const encoded = JSON.stringify(value)
    if (encoded === undefined || Buffer.byteLength(encoded, "utf8") > 65_536) return Either.left(new ResearchSourceArchiveDomainError({ detail: "metadata exceeds the 64KiB JSON bound" }))
    const decoded: unknown = JSON.parse(encoded)
    return plainRecord(decoded) ? Either.right(Object.freeze(decoded)) : Either.left(new ResearchSourceArchiveDomainError({ detail: "metadata is not JSON object data" }))
  } catch {
    return Either.left(new ResearchSourceArchiveDomainError({ detail: "metadata must be JSON serializable" }))
  }
}

export const validateSourceUrl = (value: unknown): Either.Either<string, ResearchSourceArchiveDomainError> => {
  if (typeof value !== "string" || value.length < 1 || value.length > 8_192) return Either.left(new ResearchSourceArchiveDomainError({ detail: "url must be a bounded nonempty string" }))
  try {
    const url = new URL(value)
    if ((url.protocol !== "https:" && url.protocol !== "http:") || url.username.length > 0 || url.password.length > 0 || url.hash.length > 0)
      return Either.left(new ResearchSourceArchiveDomainError({ detail: "url must be credential-free HTTP(S) without a fragment" }))
    return Either.right(url.toString())
  } catch { return Either.left(new ResearchSourceArchiveDomainError({ detail: "url is not a valid HTTP(S) URL" })) }
}

const decodeEntry = (value: unknown): Either.Either<ResearchSourceManifestEntry, ResearchSourceArchiveDomainError> => {
  if (!plainRecord(value)) return Either.left(new ResearchSourceArchiveDomainError({ detail: "each source must be an object" }))
  if (typeof value["id"] !== "string" || !idPattern.test(value["id"])) return Either.left(new ResearchSourceArchiveDomainError({ detail: "source id must use [A-Za-z0-9._-] and start alphanumeric" }))
  const url = validateSourceUrl(value["url"]); if (Either.isLeft(url)) return Either.left(url.left)
  const expectedKind = value["expectedKind"] === undefined ? "any" : value["expectedKind"]
  if (typeof expectedKind !== "string" || !sourceKinds.has(expectedKind)) return Either.left(new ResearchSourceArchiveDomainError({ detail: "expectedKind must be pdf, html, text, or any" }))
  const maximumBytes = value["maximumBytes"] === undefined ? RESEARCH_SOURCE_ARCHIVE_DEFAULT_MAXIMUM_BYTES : value["maximumBytes"]
  if (typeof maximumBytes !== "number" || !Number.isSafeInteger(maximumBytes) || maximumBytes < RESEARCH_SOURCE_ARCHIVE_DEFAULT_MAXIMUM_BYTES || maximumBytes > RESEARCH_SOURCE_ARCHIVE_MAXIMUM_BYTES_CAP) return Either.left(new ResearchSourceArchiveDomainError({ detail: "maximumBytes must be an integer from 32MiB through 256MiB" }))
  // The inventory keeps citation and provenance fields at the row's top level.
  // Preserve every caller field other than this archive's control fields.
  const metadataInput = Object.fromEntries(Object.entries(value).filter(([key]) => key !== "id" && key !== "url" && key !== "expectedKind" && key !== "metadata"))
  const declaredMetadata = value["metadata"] === undefined ? {} : value["metadata"]
  if (!plainRecord(declaredMetadata)) return Either.left(new ResearchSourceArchiveDomainError({ detail: "metadata must be an object" }))
  const metadata = jsonClone({ ...metadataInput, ...declaredMetadata }); if (Either.isLeft(metadata)) return Either.left(metadata.left)
  return Either.right(Object.freeze({ id: value["id"], url: url.right, expectedKind: expectedKind as SourceKind, maximumBytes, metadata: metadata.right }))
}

/** Decode the caller supplied finite JSON array. There is deliberately no crawling or URL discovery. */
export const decodeResearchSourceManifest = (source: string): Either.Either<ResearchSourceManifest, ResearchSourceArchiveDomainError> => {
  let parsed: unknown
  try { parsed = JSON.parse(source) } catch { return Either.left(new ResearchSourceArchiveDomainError({ detail: "manifest is not JSON" })) }
  const rows = Array.isArray(parsed) ? parsed : plainRecord(parsed) ? parsed["sources"] : undefined
  if (!Array.isArray(rows) || rows.length === 0 || rows.length > RESEARCH_SOURCE_ARCHIVE_MAX_SOURCES)
    return Either.left(new ResearchSourceArchiveDomainError({ detail: `manifest must be a nonempty array of at most ${RESEARCH_SOURCE_ARCHIVE_MAX_SOURCES} sources` }))
  const entries: ResearchSourceManifestEntry[] = []
  const ids = new Set<string>()
  for (const item of rows) {
    const entry = decodeEntry(item); if (Either.isLeft(entry)) return Either.left(entry.left)
    if (ids.has(entry.right.id)) return Either.left(new ResearchSourceArchiveDomainError({ detail: `duplicate source id: ${entry.right.id}` }))
    ids.add(entry.right.id); entries.push(entry.right)
  }
  return Either.right(Object.freeze({ schema: HSWM_RESEARCH_SOURCE_ARCHIVE_V1, sources: Object.freeze(entries) }))
}

export const sha256Hex = (bytes: Uint8Array): string => createHash("sha256").update(bytes).digest("hex")
export const sourceKindAccepts = (kind: SourceKind, contentType: string | null): boolean => {
  if (kind === "any") return contentType !== null
  if (contentType === null) return false
  const normalized = contentType.toLowerCase().split(";", 1)[0]?.trim() ?? ""
  return (kind === "pdf" && (normalized === "application/pdf" || normalized === "application/octet-stream")) ||
    (kind === "html" && (normalized === "text/html" || normalized === "application/xhtml+xml")) ||
    (kind === "text" && normalized.startsWith("text/"))
}

export const archiveManifestDigest = (source: string): string => sha256Hex(new TextEncoder().encode(source))
