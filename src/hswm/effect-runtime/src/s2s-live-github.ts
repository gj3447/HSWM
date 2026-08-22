import { Context, Data, Effect, Either, Layer } from "effect"

import {
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "./s2s-canonical.js"
import { parseS2SJsonBytes, type S2SJson } from "./s2s-json.js"
import { S2S_CONFIRMATORY_REPOSITORY } from "./s2s-workflow-contract.js"

export const S2S_GITHUB_API_VERSION = "2022-11-28" as const
export const S2S_GITHUB_REPOSITORY = S2S_CONFIRMATORY_REPOSITORY
export const S2S_GITHUB_OBSERVATION_SCHEMA_VERSION =
  "hswm-swm0w-s2s-github-observation-receipt/v2" as const
export const S2S_GITHUB_JSON_MAX_BYTES = 8 * 1_048_576
export const S2S_GITHUB_PAGE_SIZE = 100 as const
export const S2S_GITHUB_METADATA_TIMEOUT_MILLIS = 120_000 as const
export const S2S_GITHUB_ARCHIVE_TIMEOUT_MILLIS = 300_000 as const
export const S2S_GITHUB_REDIRECT_BODY_MAX_BYTES = 4_096 as const
export const S2S_GITHUB_ARTIFACT_ARCHIVE_MAX_BYTES = 64 * 1_048_576
export const S2S_GITHUB_ARTIFACT_DOWNLOAD_SCHEMA_VERSION =
  "hswm-swm0w-s2s-github-artifact-download-receipt/v2" as const

const SHA256_PATTERN = /^[0-9a-f]{64}$/
const GIT_SHA_PATTERN = /^[0-9a-f]{40}$/
const ASCII_TEXT_PATTERN = /^[\u0020-\u007e]*$/
const GITHUB_REQUEST_ID_PATTERN = /^[\u0021-\u007e]{1,256}$/
const HTTP_ETAG_PATTERN = /^(?:W\/)?"[\u0021\u0023-\u007e]{0,508}"$/
const REPOSITORY_PATTERN = /^[A-Za-z0-9_.-]{1,100}\/[A-Za-z0-9_.-]{1,100}$/
const WORKFLOW_PATH_PATTERN =
  /^\.github\/workflows\/[A-Za-z0-9._/-]{1,220}(?:@[A-Za-z0-9._/@-]{1,220})?$/
const RFC3339_UTC_SECONDS_PATTERN =
  /^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\dZ$/

export type S2SGitHubRunStatus =
  | "queued"
  | "in_progress"
  | "completed"
  | "waiting"
  | "pending"
  | "requested"

export type S2SGitHubConclusion =
  | "success"
  | "failure"
  | "cancelled"
  | "skipped"
  | "timed_out"
  | "action_required"
  | "neutral"
  | "stale"
  | "startup_failure"
  | null

export interface S2SGitHubWorkflowRunProjection {
  readonly id: number
  readonly runAttempt: number
  readonly name: string
  readonly path: string
  readonly event: string
  readonly headBranch: string
  readonly headSha: string
  readonly repository: string
  readonly headRepository: string
  readonly status: S2SGitHubRunStatus
  readonly conclusion: S2SGitHubConclusion
  readonly createdAt: string
  readonly createdAtUnixSeconds: number
}

export interface S2SGitHubWorkflowJobProjection {
  readonly id: number
  readonly runId: number
  readonly runAttempt: number
  readonly name: string
  readonly headSha: string
  readonly status: S2SGitHubRunStatus
  readonly conclusion: S2SGitHubConclusion
  readonly startedAt: string
  readonly startedAtUnixSeconds: number
  readonly completedAt: string | null
  readonly completedAtUnixSeconds: number | null
  readonly labels: ReadonlyArray<string>
}

export interface S2SGitHubWorkflowJobsProjection {
  readonly totalCount: number
  readonly jobs: ReadonlyArray<S2SGitHubWorkflowJobProjection>
}

export interface S2SGitHubArtifactProjection {
  readonly id: number
  readonly name: string
  readonly sizeInBytes: number
  readonly digestSha256: string
  readonly expired: boolean
  readonly createdAt: string
  readonly createdAtUnixSeconds: number
  readonly expiresAt: string
  readonly expiresAtUnixSeconds: number
  readonly workflowRunId: number
  readonly workflowHeadSha: string
}

export interface S2SGitHubArtifactsProjection {
  readonly totalCount: number
  readonly artifacts: ReadonlyArray<S2SGitHubArtifactProjection>
}

export type S2SGitHubProjection =
  | S2SGitHubWorkflowRunProjection
  | S2SGitHubWorkflowJobsProjection
  | S2SGitHubArtifactProjection
  | S2SGitHubArtifactsProjection

export type S2SGitHubObservationKind =
  | "WORKFLOW_RUN"
  | "WORKFLOW_ATTEMPT_JOBS"
  | "RUN_ARTIFACTS"
  | "ARTIFACT"

export interface S2SGitHubObservationReceipt<
  Projection extends S2SGitHubProjection = S2SGitHubProjection
> {
  readonly schemaVersion: typeof S2S_GITHUB_OBSERVATION_SCHEMA_VERSION
  readonly kind: S2SGitHubObservationKind
  readonly apiVersion: typeof S2S_GITHUB_API_VERSION
  readonly repository: typeof S2S_GITHUB_REPOSITORY
  readonly endpointPathAndQuery: string
  readonly observedAtUnixSeconds: number
  readonly httpStatus: 200
  readonly githubRequestId: string
  readonly githubApiVersionSelected: typeof S2S_GITHUB_API_VERSION
  readonly responseEtag: string
  readonly rawBodyByteLength: number
  readonly rawBodySha256: string
  readonly projection: Projection
  readonly projectionSha256: string
  readonly receiptSha256: string
}

export interface S2SGitHubObservation<
  Projection extends S2SGitHubProjection = S2SGitHubProjection
> {
  readonly receipt: S2SGitHubObservationReceipt<Projection>
  readonly readRawBody: () => Uint8Array
}

export class S2SGitHubObservationError extends Data.TaggedError(
  "S2SGitHubObservationError"
)<{
  readonly reason:
    | "IDENTITY_MISMATCH"
    | "INVALID_ARGUMENT"
    | "JSON_REJECTED"
    | "PROVENANCE_REJECTED"
    | "PROJECTION_NOT_CANONICAL"
    | "PROJECTION_REJECTED"
  readonly path: string
  readonly detail: string
}> {}

export interface S2SGitHubHttpResponse {
  readonly status: number
  readonly contentType: string | null
  readonly location: string | null
  readonly githubRequestId: string | null
  readonly githubApiVersionSelected: string | null
  readonly etag: string | null
  readonly body: Uint8Array
}

export interface S2SGitHubApiResponseProvenance {
  readonly githubRequestId: string
  readonly githubApiVersionSelected: typeof S2S_GITHUB_API_VERSION
  readonly responseEtag: string
}

export class S2SGitHubTransportError extends Data.TaggedError(
  "S2SGitHubTransportError"
)<{
  readonly reason:
    | "BODY_READ_FAILED"
    | "CONFIGURATION_INVALID"
    | "CONTENT_TYPE_REJECTED"
    | "HTTP_STATUS_UNEXPECTED"
    | "REDIRECT_REJECTED"
    | "REQUEST_FAILED"
    | "RESPONSE_HEADERS_REJECTED"
    | "RESPONSE_LIMIT_EXCEEDED"
    | "TIMED_OUT"
  readonly operation: string
  readonly httpStatus: number | null
  readonly responseBodySha256: string | null
  readonly detail: string
}> {}

export type S2SGitHubArchiveMediaType =
  | "application/octet-stream"
  | "application/zip"
  | "binary/octet-stream"

export interface S2SGitHubArtifactDownloadReceipt {
  readonly schemaVersion: typeof S2S_GITHUB_ARTIFACT_DOWNLOAD_SCHEMA_VERSION
  readonly apiVersion: typeof S2S_GITHUB_API_VERSION
  readonly repository: typeof S2S_GITHUB_REPOSITORY
  readonly artifactId: number
  readonly endpointPathAndQuery: string
  readonly downloadedAtUnixSeconds: number
  readonly redirectHttpStatus: 302
  readonly redirectGitHubRequestId: string
  readonly redirectGitHubApiVersionSelected: typeof S2S_GITHUB_API_VERSION
  readonly redirectResponseEtag: string | null
  readonly redirectUrlSha256: string
  readonly redirectOrigin: string
  readonly archiveHttpStatus: 200
  readonly archiveMediaType: S2SGitHubArchiveMediaType
  readonly archiveResponseEtag: string | null
  readonly archiveByteLength: number
  readonly downloadedArchiveSha256: string
  readonly receiptSha256: string
}

export interface S2SGitHubArtifactDownload {
  readonly receipt: S2SGitHubArtifactDownloadReceipt
  readonly readArchiveBytes: () => Uint8Array
}

export class S2SGitHubArtifactDownloadValidationError extends Data.TaggedError(
  "S2SGitHubArtifactDownloadValidationError"
)<{
  readonly reason:
    | "ARCHIVE_BYTES_DRIFT"
    | "INVALID_ARGUMENT"
    | "RECEIPT_SCHEMA_MISMATCH"
    | "RECEIPT_SELF_HASH_MISMATCH"
}> {}

export interface S2SGitHubLiveTransportConfig {
  readonly token: string
}

/** Internal Effect port. The authoritative composition root supplies Live. */
export class S2SGitHubHttpTransport extends Context.Tag(
  "hswm/S2S/GitHubHttpTransport"
)<
  S2SGitHubHttpTransport,
  {
    readonly getJson: (
      endpointPathAndQuery: string
    ) => Effect.Effect<S2SGitHubHttpResponse, S2SGitHubTransportError>
    readonly downloadArtifactArchive: (
      artifactId: number,
      maximumBytes: number
    ) => Effect.Effect<S2SGitHubArtifactDownload, S2SGitHubTransportError>
  }
>() {}

export type S2SGitHubObserverError =
  | S2SGitHubObservationError
  | S2SGitHubTransportError

/** Read-only authority adapter. It does not dispatch, rerun, delete, or upload. */
export class S2SGitHubObserver extends Context.Tag("hswm/S2S/GitHubObserver")<
  S2SGitHubObserver,
  {
    readonly observeWorkflowRun: (
      workflowRunId: number
    ) => Effect.Effect<
      S2SGitHubObservation<S2SGitHubWorkflowRunProjection>,
      S2SGitHubObserverError
    >
    readonly observeWorkflowAttemptJobs: (
      workflowRunId: number
    ) => Effect.Effect<
      S2SGitHubObservation<S2SGitHubWorkflowJobsProjection>,
      S2SGitHubObserverError
    >
    readonly observeRunArtifacts: (
      workflowRunId: number
    ) => Effect.Effect<
      S2SGitHubObservation<S2SGitHubArtifactsProjection>,
      S2SGitHubObserverError
    >
    readonly observeArtifact: (
      artifactId: number
    ) => Effect.Effect<
      S2SGitHubObservation<S2SGitHubArtifactProjection>,
      S2SGitHubObserverError
    >
    readonly downloadArtifactArchive: (
      artifactId: number,
      maximumBytes: number
    ) => Effect.Effect<S2SGitHubArtifactDownload, S2SGitHubTransportError>
  }
>() {}

type JsonRecord = { readonly [key: string]: S2SJson }

const observationError = (
  reason: S2SGitHubObservationError["reason"],
  path: string,
  detail: string
): S2SGitHubObservationError =>
  new S2SGitHubObservationError({ reason, path, detail })

const failProjection = (path: string, detail: string): never => {
  throw observationError("PROJECTION_REJECTED", path, detail)
}

const isRecord = (value: S2SJson): value is JsonRecord =>
  value !== null && !Array.isArray(value) && typeof value === "object"

const required = (record: JsonRecord, key: string, path: string): S2SJson => {
  const descriptor = Object.getOwnPropertyDescriptor(record, key)
  if (
    descriptor === undefined ||
    descriptor.enumerable !== true ||
    !("value" in descriptor)
  ) {
    return failProjection(`${path}.${key}`, "required API field is absent")
  }
  return descriptor.value
}

const asRecord = (value: S2SJson, path: string): JsonRecord => {
  if (!isRecord(value)) return failProjection(path, "expected an object")
  return value
}

const asArray = (value: S2SJson, path: string): ReadonlyArray<S2SJson> => {
  if (!Array.isArray(value)) return failProjection(path, "expected an array")
  return value
}

const asBoolean = (value: S2SJson, path: string): boolean => {
  if (typeof value !== "boolean") return failProjection(path, "expected a boolean")
  return value
}

const asInteger = (
  value: S2SJson,
  path: string,
  minimum: number = 0
): number => {
  if (!Number.isSafeInteger(value) || typeof value !== "number" || value < minimum) {
    return failProjection(path, "expected an exact bounded integer")
  }
  return value
}

const asAsciiString = (
  value: S2SJson,
  path: string,
  maximumBytes: number,
  pattern?: RegExp
): string => {
  if (
    typeof value !== "string" ||
    !ASCII_TEXT_PATTERN.test(value) ||
    Buffer.byteLength(value, "utf8") > maximumBytes ||
    (pattern !== undefined && !pattern.test(value))
  ) {
    return failProjection(path, "expected a bounded ASCII string")
  }
  return value
}

const asRunStatus = (value: S2SJson, path: string): S2SGitHubRunStatus => {
  const status = asAsciiString(value, path, 32)
  switch (status) {
    case "queued":
    case "in_progress":
    case "completed":
    case "waiting":
    case "pending":
    case "requested":
      return status
    default:
      return failProjection(path, "unknown GitHub Actions status")
  }
}

const asConclusion = (value: S2SJson, path: string): S2SGitHubConclusion => {
  if (value === null) return null
  const conclusion = asAsciiString(value, path, 32)
  switch (conclusion) {
    case "success":
    case "failure":
    case "cancelled":
    case "skipped":
    case "timed_out":
    case "action_required":
    case "neutral":
    case "stale":
    case "startup_failure":
      return conclusion
    default:
      return failProjection(path, "unknown GitHub Actions conclusion")
  }
}

const asGitSha = (value: S2SJson, path: string): string =>
  asAsciiString(value, path, 40, GIT_SHA_PATTERN)

const parseUtcSeconds = (value: S2SJson, path: string): readonly [string, number] => {
  const timestamp = asAsciiString(value, path, 20, RFC3339_UTC_SECONDS_PATTERN)
  const milliseconds = Date.parse(timestamp)
  if (
    !Number.isSafeInteger(milliseconds) ||
    milliseconds < 0 ||
    new Date(milliseconds).toISOString().replace(".000Z", "Z") !== timestamp
  ) {
    return failProjection(path, "timestamp is not a real canonical UTC second")
  }
  return [timestamp, milliseconds / 1_000]
}

const parseNullableUtcSeconds = (
  value: S2SJson,
  path: string
): readonly [string | null, number | null] =>
  value === null ? [null, null] : parseUtcSeconds(value, path)

const parseRepositoryFullName = (value: S2SJson, path: string): string => {
  const repository = asRecord(value, path)
  return asAsciiString(
    required(repository, "full_name", path),
    `${path}.full_name`,
    201,
    REPOSITORY_PATTERN
  )
}

const parseRoot = (rawBody: Uint8Array): S2SJson => {
  const decoded = parseS2SJsonBytes(rawBody, S2S_GITHUB_JSON_MAX_BYTES)
  if (Either.isLeft(decoded)) {
    throw observationError(
      "JSON_REJECTED",
      `$[${decoded.left.offset}]`,
      `${decoded.left.reason}: ${decoded.left.detail}`
    )
  }
  return decoded.right
}

const parseWorkflowRunProjection = (
  root: S2SJson
): S2SGitHubWorkflowRunProjection => {
  const run = asRecord(root, "$")
  const created = parseUtcSeconds(required(run, "created_at", "$"), "$.created_at")
  return Object.freeze({
    id: asInteger(required(run, "id", "$"), "$.id", 1),
    runAttempt: asInteger(required(run, "run_attempt", "$"), "$.run_attempt", 1),
    name: asAsciiString(required(run, "name", "$"), "$.name", 256),
    path: asAsciiString(
      required(run, "path", "$"),
      "$.path",
      512,
      WORKFLOW_PATH_PATTERN
    ),
    event: asAsciiString(required(run, "event", "$"), "$.event", 64),
    headBranch: asAsciiString(
      required(run, "head_branch", "$"),
      "$.head_branch",
      256
    ),
    headSha: asGitSha(required(run, "head_sha", "$"), "$.head_sha"),
    repository: parseRepositoryFullName(
      required(run, "repository", "$"),
      "$.repository"
    ),
    headRepository: parseRepositoryFullName(
      required(run, "head_repository", "$"),
      "$.head_repository"
    ),
    status: asRunStatus(required(run, "status", "$"), "$.status"),
    conclusion: asConclusion(required(run, "conclusion", "$"), "$.conclusion"),
    createdAt: created[0],
    createdAtUnixSeconds: created[1]
  })
}

const parseWorkflowJobProjection = (
  value: S2SJson,
  path: string
): S2SGitHubWorkflowJobProjection => {
  const job = asRecord(value, path)
  const started = parseUtcSeconds(required(job, "started_at", path), `${path}.started_at`)
  const completed = parseNullableUtcSeconds(
    required(job, "completed_at", path),
    `${path}.completed_at`
  )
  const labelValues = asArray(required(job, "labels", path), `${path}.labels`)
  const labels = labelValues.map((label, index) =>
    asAsciiString(label, `${path}.labels[${index}]`, 256)
  )
  labels.sort()
  if (labels.some((label, index) => index > 0 && label === labels[index - 1])) {
    return failProjection(`${path}.labels`, "job labels must be unique")
  }
  return Object.freeze({
    id: asInteger(required(job, "id", path), `${path}.id`, 1),
    runId: asInteger(required(job, "run_id", path), `${path}.run_id`, 1),
    runAttempt: asInteger(
      required(job, "run_attempt", path),
      `${path}.run_attempt`,
      1
    ),
    name: asAsciiString(required(job, "name", path), `${path}.name`, 256),
    headSha: asGitSha(required(job, "head_sha", path), `${path}.head_sha`),
    status: asRunStatus(required(job, "status", path), `${path}.status`),
    conclusion: asConclusion(
      required(job, "conclusion", path),
      `${path}.conclusion`
    ),
    startedAt: started[0],
    startedAtUnixSeconds: started[1],
    completedAt: completed[0],
    completedAtUnixSeconds: completed[1],
    labels: Object.freeze(labels)
  })
}

const parseWorkflowJobsProjection = (
  root: S2SJson
): S2SGitHubWorkflowJobsProjection => {
  const response = asRecord(root, "$")
  const totalCount = asInteger(
    required(response, "total_count", "$"),
    "$.total_count"
  )
  const values = asArray(required(response, "jobs", "$"), "$.jobs")
  if (totalCount !== values.length || totalCount > S2S_GITHUB_PAGE_SIZE) {
    return failProjection(
      "$.total_count",
      "single-page job observation must be complete and within the fixed roster bound"
    )
  }
  const jobs = values.map((value, index) =>
    parseWorkflowJobProjection(value, `$.jobs[${index}]`)
  )
  jobs.sort((left, right) => left.id - right.id)
  if (jobs.some((job, index) => index > 0 && job.id === jobs[index - 1]?.id)) {
    return failProjection("$.jobs", "workflow jobs contain a duplicate id")
  }
  return Object.freeze({ totalCount, jobs: Object.freeze(jobs) })
}

const parseArtifactProjection = (
  value: S2SJson,
  path: string
): S2SGitHubArtifactProjection => {
  const artifact = asRecord(value, path)
  const workflowRun = asRecord(
    required(artifact, "workflow_run", path),
    `${path}.workflow_run`
  )
  const digest = asAsciiString(
    required(artifact, "digest", path),
    `${path}.digest`,
    71,
    /^sha256:[0-9a-f]{64}$/
  )
  const created = parseUtcSeconds(
    required(artifact, "created_at", path),
    `${path}.created_at`
  )
  const expires = parseUtcSeconds(
    required(artifact, "expires_at", path),
    `${path}.expires_at`
  )
  return Object.freeze({
    id: asInteger(required(artifact, "id", path), `${path}.id`, 1),
    name: asAsciiString(required(artifact, "name", path), `${path}.name`, 256),
    sizeInBytes: asInteger(
      required(artifact, "size_in_bytes", path),
      `${path}.size_in_bytes`,
      1
    ),
    digestSha256: digest.slice("sha256:".length),
    expired: asBoolean(required(artifact, "expired", path), `${path}.expired`),
    createdAt: created[0],
    createdAtUnixSeconds: created[1],
    expiresAt: expires[0],
    expiresAtUnixSeconds: expires[1],
    workflowRunId: asInteger(
      required(workflowRun, "id", `${path}.workflow_run`),
      `${path}.workflow_run.id`,
      1
    ),
    workflowHeadSha: asGitSha(
      required(workflowRun, "head_sha", `${path}.workflow_run`),
      `${path}.workflow_run.head_sha`
    )
  })
}

const parseArtifactsProjection = (
  root: S2SJson
): S2SGitHubArtifactsProjection => {
  const response = asRecord(root, "$")
  const totalCount = asInteger(
    required(response, "total_count", "$"),
    "$.total_count"
  )
  const values = asArray(required(response, "artifacts", "$"), "$.artifacts")
  if (totalCount !== values.length || totalCount > S2S_GITHUB_PAGE_SIZE) {
    return failProjection(
      "$.total_count",
      "single-page artifact observation must be complete and within the fixed roster bound"
    )
  }
  const artifacts = values.map((value, index) =>
    parseArtifactProjection(value, `$.artifacts[${index}]`)
  )
  artifacts.sort((left, right) => left.id - right.id)
  if (
    artifacts.some(
      (artifact, index) => index > 0 && artifact.id === artifacts[index - 1]?.id
    )
  ) {
    return failProjection("$.artifacts", "artifacts contain a duplicate id")
  }
  return Object.freeze({ totalCount, artifacts: Object.freeze(artifacts) })
}

const snapshotRawBody = (input: unknown): Uint8Array => {
  if (
    !(input instanceof Uint8Array) ||
    Object.getPrototypeOf(input) !== Uint8Array.prototype ||
    Object.getOwnPropertySymbols(input).length !== 0 ||
    input.byteLength > S2S_GITHUB_JSON_MAX_BYTES ||
    (typeof SharedArrayBuffer !== "undefined" &&
      input.buffer instanceof SharedArrayBuffer)
  ) {
    throw observationError(
      "INVALID_ARGUMENT",
      "$rawBody",
      "raw body must be one bounded, unshared plain Uint8Array"
    )
  }
  return new Uint8Array(input)
}

const validateObservationArguments = (
  identity: number,
  observedAtUnixSeconds: number
): void => {
  if (
    !Number.isSafeInteger(identity) ||
    identity < 1 ||
    !Number.isSafeInteger(observedAtUnixSeconds) ||
    observedAtUnixSeconds < 0
  ) {
    throw observationError(
      "INVALID_ARGUMENT",
      "$metadata",
      "observation identity and timestamp must be exact bounded integers"
    )
  }
}

const snapshotObservationProvenance = (
  input: unknown
): S2SGitHubApiResponseProvenance => {
  try {
    if (input === null || typeof input !== "object") {
      throw observationError(
        "PROVENANCE_REJECTED",
        "$provenance",
        "response provenance must be one exact plain data record"
      )
    }
    const prototype = Object.getPrototypeOf(input)
    if (prototype !== Object.prototype && prototype !== null) {
      throw observationError(
        "PROVENANCE_REJECTED",
        "$provenance",
        "response provenance must be one exact plain data record"
      )
    }
    const ownKeys = Reflect.ownKeys(input)
    if (ownKeys.some((key) => typeof key !== "string")) {
      throw observationError(
        "PROVENANCE_REJECTED",
        "$provenance",
        "response provenance has an unexpected shape"
      )
    }
    const keys = ownKeys
      .filter((key): key is string => typeof key === "string")
      .sort()
    if (
      keys.length !== 3 ||
      keys[0] !== "githubApiVersionSelected" ||
      keys[1] !== "githubRequestId" ||
      keys[2] !== "responseEtag"
    ) {
      throw observationError(
        "PROVENANCE_REJECTED",
        "$provenance",
        "response provenance has an unexpected shape"
      )
    }
    const record = input as Readonly<Record<string, unknown>>
    const requestIdDescriptor = Object.getOwnPropertyDescriptor(
      record,
      "githubRequestId"
    )
    const versionDescriptor = Object.getOwnPropertyDescriptor(
      record,
      "githubApiVersionSelected"
    )
    const etagDescriptor = Object.getOwnPropertyDescriptor(record, "responseEtag")
    if (
      requestIdDescriptor === undefined ||
      requestIdDescriptor.enumerable !== true ||
      !("value" in requestIdDescriptor) ||
      typeof requestIdDescriptor.value !== "string" ||
      !GITHUB_REQUEST_ID_PATTERN.test(requestIdDescriptor.value) ||
      versionDescriptor === undefined ||
      versionDescriptor.enumerable !== true ||
      !("value" in versionDescriptor) ||
      versionDescriptor.value !== S2S_GITHUB_API_VERSION ||
      etagDescriptor === undefined ||
      etagDescriptor.enumerable !== true ||
      !("value" in etagDescriptor) ||
      typeof etagDescriptor.value !== "string" ||
      !HTTP_ETAG_PATTERN.test(etagDescriptor.value)
    ) {
      throw observationError(
        "PROVENANCE_REJECTED",
        "$provenance",
        "response provenance headers are absent or noncanonical"
      )
    }
    return Object.freeze({
      githubRequestId: requestIdDescriptor.value,
      githubApiVersionSelected: S2S_GITHUB_API_VERSION,
      responseEtag: etagDescriptor.value
    })
  } catch (error: unknown) {
    if (error instanceof S2SGitHubObservationError) throw error
    throw observationError(
      "PROVENANCE_REJECTED",
      "$provenance",
      "response provenance inspection failed closed"
    )
  }
}

const makeObservation = <Projection extends S2SGitHubProjection>(
  rawInput: unknown,
  kind: S2SGitHubObservationKind,
  endpointPathAndQuery: string,
  observedAtUnixSeconds: number,
  provenanceInput: unknown,
  parseProjection: (root: S2SJson) => Projection,
  identityCheck: (projection: Projection) => boolean
): Either.Either<S2SGitHubObservation<Projection>, S2SGitHubObservationError> => {
  try {
    const rawBody = snapshotRawBody(rawInput)
    const provenance = snapshotObservationProvenance(provenanceInput)
    const projection = parseProjection(parseRoot(rawBody))
    if (!identityCheck(projection)) {
      throw observationError(
        "IDENTITY_MISMATCH",
        "$projection",
        "API projection does not match the requested run, attempt, or artifact identity"
      )
    }
    const projectionHash = canonicalS2SControlSha256(projection)
    if (Either.isLeft(projectionHash) || !SHA256_PATTERN.test(projectionHash.right)) {
      throw observationError(
        "PROJECTION_NOT_CANONICAL",
        "$projection",
        "API projection cannot be encoded as canonical control JSON"
      )
    }
    const receiptCore = Object.freeze({
      schemaVersion: S2S_GITHUB_OBSERVATION_SCHEMA_VERSION,
      kind,
      apiVersion: S2S_GITHUB_API_VERSION,
      repository: S2S_GITHUB_REPOSITORY,
      endpointPathAndQuery,
      observedAtUnixSeconds,
      httpStatus: 200 as const,
      githubRequestId: provenance.githubRequestId,
      githubApiVersionSelected: provenance.githubApiVersionSelected,
      responseEtag: provenance.responseEtag,
      rawBodyByteLength: rawBody.byteLength,
      rawBodySha256: rawS2SFileSha256(rawBody),
      projection,
      projectionSha256: projectionHash.right
    })
    const receiptHash = canonicalS2SControlSha256(receiptCore)
    if (Either.isLeft(receiptHash) || !SHA256_PATTERN.test(receiptHash.right)) {
      throw observationError(
        "PROJECTION_NOT_CANONICAL",
        "$receipt",
        "observation receipt cannot be encoded as canonical control JSON"
      )
    }
    return Either.right(
      Object.freeze({
        receipt: Object.freeze({
          ...receiptCore,
          receiptSha256: receiptHash.right
        }),
        readRawBody: () => new Uint8Array(rawBody)
      })
    )
  } catch (error: unknown) {
    return Either.left(
      error instanceof S2SGitHubObservationError
        ? error
        : observationError(
            "PROJECTION_REJECTED",
            "$",
            "GitHub observation projection failed closed"
          )
    )
  }
}

const repositoryEndpoint = (suffix: string): string =>
  `/repos/${S2S_GITHUB_REPOSITORY}${suffix}`

export const observeS2SGitHubWorkflowRun = (
  rawBody: unknown,
  workflowRunId: number,
  observedAtUnixSeconds: number,
  provenance: unknown
): Either.Either<
  S2SGitHubObservation<S2SGitHubWorkflowRunProjection>,
  S2SGitHubObservationError
> => {
  try {
    validateObservationArguments(workflowRunId, observedAtUnixSeconds)
  } catch (error: unknown) {
    return Either.left(error as S2SGitHubObservationError)
  }
  return makeObservation(
    rawBody,
    "WORKFLOW_RUN",
    repositoryEndpoint(`/actions/runs/${workflowRunId}`),
    observedAtUnixSeconds,
    provenance,
    parseWorkflowRunProjection,
    (projection) =>
      projection.id === workflowRunId &&
      projection.runAttempt === 1 &&
      projection.repository === S2S_GITHUB_REPOSITORY &&
      projection.headRepository === S2S_GITHUB_REPOSITORY
  )
}

export const observeS2SGitHubWorkflowAttemptJobs = (
  rawBody: unknown,
  workflowRunId: number,
  workflowRunAttempt: number,
  observedAtUnixSeconds: number,
  provenance: unknown
): Either.Either<
  S2SGitHubObservation<S2SGitHubWorkflowJobsProjection>,
  S2SGitHubObservationError
> => {
  try {
    validateObservationArguments(workflowRunId, observedAtUnixSeconds)
    if (workflowRunAttempt !== 1) {
      throw observationError(
        "INVALID_ARGUMENT",
        "$workflowRunAttempt",
        "confirmatory observation permits attempt one only"
      )
    }
  } catch (error: unknown) {
    return Either.left(error as S2SGitHubObservationError)
  }
  return makeObservation(
    rawBody,
    "WORKFLOW_ATTEMPT_JOBS",
    repositoryEndpoint(
      `/actions/runs/${workflowRunId}/attempts/${workflowRunAttempt}/jobs?per_page=${S2S_GITHUB_PAGE_SIZE}`
    ),
    observedAtUnixSeconds,
    provenance,
    parseWorkflowJobsProjection,
    (projection) =>
      projection.jobs.every(
        (job) =>
          job.runId === workflowRunId && job.runAttempt === workflowRunAttempt
      )
  )
}

export const observeS2SGitHubRunArtifacts = (
  rawBody: unknown,
  workflowRunId: number,
  observedAtUnixSeconds: number,
  provenance: unknown
): Either.Either<
  S2SGitHubObservation<S2SGitHubArtifactsProjection>,
  S2SGitHubObservationError
> => {
  try {
    validateObservationArguments(workflowRunId, observedAtUnixSeconds)
  } catch (error: unknown) {
    return Either.left(error as S2SGitHubObservationError)
  }
  return makeObservation(
    rawBody,
    "RUN_ARTIFACTS",
    repositoryEndpoint(
      `/actions/runs/${workflowRunId}/artifacts?per_page=${S2S_GITHUB_PAGE_SIZE}`
    ),
    observedAtUnixSeconds,
    provenance,
    parseArtifactsProjection,
    (projection) =>
      projection.artifacts.every(
        (artifact) => artifact.workflowRunId === workflowRunId
      )
  )
}

export const observeS2SGitHubArtifact = (
  rawBody: unknown,
  artifactId: number,
  observedAtUnixSeconds: number,
  provenance: unknown
): Either.Either<
  S2SGitHubObservation<S2SGitHubArtifactProjection>,
  S2SGitHubObservationError
> => {
  try {
    validateObservationArguments(artifactId, observedAtUnixSeconds)
  } catch (error: unknown) {
    return Either.left(error as S2SGitHubObservationError)
  }
  return makeObservation(
    rawBody,
    "ARTIFACT",
    repositoryEndpoint(`/actions/artifacts/${artifactId}`),
    observedAtUnixSeconds,
    provenance,
    (root) => parseArtifactProjection(root, "$"),
    (projection) => projection.id === artifactId
  )
}

const transportError = (
  reason: S2SGitHubTransportError["reason"],
  operation: string,
  detail: string,
  httpStatus: number | null = null,
  responseBodySha256: string | null = null
): S2SGitHubTransportError =>
  new S2SGitHubTransportError({
    reason,
    operation,
    httpStatus,
    responseBodySha256,
    detail
  })

const snapshotLiveTransportConfig = (
  input: unknown
): S2SGitHubLiveTransportConfig => {
  if (
    input === null ||
    typeof input !== "object" ||
    (Object.getPrototypeOf(input) !== Object.prototype &&
      Object.getPrototypeOf(input) !== null) ||
    Reflect.ownKeys(input).length !== 1
  ) {
    throw transportError(
      "CONFIGURATION_INVALID",
      "CONFIGURE_GITHUB_TRANSPORT",
      "transport configuration must be an exact plain data record"
    )
  }
  const descriptor = Object.getOwnPropertyDescriptor(input, "token")
  const token: unknown = descriptor !== undefined && "value" in descriptor
    ? descriptor.value
    : undefined
  if (
    descriptor === undefined ||
    descriptor.enumerable !== true ||
    typeof token !== "string" ||
    token.length < 1 ||
    token.length > 4_096 ||
    !/^[\u0021-\u007e]+$/.test(token)
  ) {
    throw transportError(
      "CONFIGURATION_INVALID",
      "CONFIGURE_GITHUB_TRANSPORT",
      "token must be one bounded non-whitespace ASCII value"
    )
  }
  return Object.freeze({ token })
}

const validateEndpoint = (endpointPathAndQuery: string): void => {
  const repositoryPrefix = `/repos/${S2S_GITHUB_REPOSITORY}`
  const allowed = [
    new RegExp(`^${repositoryPrefix}/actions/runs/[1-9][0-9]*$`),
    new RegExp(
      `^${repositoryPrefix}/actions/runs/[1-9][0-9]*/attempts/1/jobs\\?per_page=${S2S_GITHUB_PAGE_SIZE}$`
    ),
    new RegExp(
      `^${repositoryPrefix}/actions/runs/[1-9][0-9]*/artifacts\\?per_page=${S2S_GITHUB_PAGE_SIZE}$`
    ),
    new RegExp(`^${repositoryPrefix}/actions/artifacts/[1-9][0-9]*$`),
    new RegExp(`^${repositoryPrefix}/actions/artifacts/[1-9][0-9]*/zip$`)
  ]
  let parsed: URL | null = null
  try {
    parsed = new URL(endpointPathAndQuery, "https://api.github.com")
  } catch {
    // Rejected below without reflecting caller-controlled endpoint text.
  }
  if (
    endpointPathAndQuery.length > 512 ||
    !allowed.some((pattern) => pattern.test(endpointPathAndQuery)) ||
    parsed === null ||
    parsed.origin !== "https://api.github.com" ||
    `${parsed.pathname}${parsed.search}` !== endpointPathAndQuery ||
    parsed.hash !== ""
  ) {
    throw transportError(
      "CONFIGURATION_INVALID",
      "GITHUB_API_GET",
      "endpoint is outside the fixed repository Actions namespace"
    )
  }
}

const boundedResponseBody = async (
  response: Response,
  maximumBytes: number,
  operation: string
): Promise<Uint8Array> => {
  const cancelUnconsumedBody = async (): Promise<void> => {
    if (response.body !== null) {
      await response.body.cancel().catch(() => undefined)
    }
  }
  const contentLength = response.headers.get("content-length")
  if (contentLength !== null) {
    if (!/^(0|[1-9][0-9]*)$/.test(contentLength)) {
      await cancelUnconsumedBody()
      throw transportError(
        "BODY_READ_FAILED",
        operation,
        "response Content-Length is not a canonical integer",
        response.status
      )
    }
    const declared = Number(contentLength)
    if (!Number.isSafeInteger(declared) || declared > maximumBytes) {
      await cancelUnconsumedBody()
      throw transportError(
        "RESPONSE_LIMIT_EXCEEDED",
        operation,
        "declared response size exceeds the fixed byte bound",
        response.status
      )
    }
  }
  if (response.body === null) return new Uint8Array()
  const reader = response.body.getReader()
  const chunks: Array<Uint8Array> = []
  let total = 0
  try {
    while (true) {
      const result = await reader.read()
      if (result.done) break
      const chunk = result.value
      total += chunk.byteLength
      if (total > maximumBytes) {
        await reader.cancel().catch(() => undefined)
        throw transportError(
          "RESPONSE_LIMIT_EXCEEDED",
          operation,
          "streamed response exceeds the fixed byte bound",
          response.status
        )
      }
      chunks.push(new Uint8Array(chunk))
    }
  } catch (error: unknown) {
    if (error instanceof S2SGitHubTransportError) throw error
    throw transportError(
      "BODY_READ_FAILED",
      operation,
      "response stream could not be read to completion",
      response.status
    )
  } finally {
    reader.releaseLock()
  }
  return Uint8Array.from(
    Buffer.concat(chunks.map((chunk) => Buffer.from(chunk)), total)
  )
}

interface FetchRequest {
  readonly operation: string
  readonly url: string
  readonly headers: Readonly<Record<string, string>>
  readonly redirect: "error" | "manual"
  readonly timeoutMillis: number
  readonly maximumBytes: number
  readonly interruptSignal: AbortSignal
}

const performBoundedFetch = async (
  request: FetchRequest
): Promise<S2SGitHubHttpResponse> => {
  const controller = new AbortController()
  let didTimeOut = false
  const abortFromInterruption = (): void => controller.abort()
  if (request.interruptSignal.aborted) controller.abort()
  request.interruptSignal.addEventListener("abort", abortFromInterruption, {
    once: true
  })
  let timeout: ReturnType<typeof setTimeout> | null = null
  try {
    const deadline = new Promise<never>((_resolve, reject) => {
      timeout = setTimeout(() => {
        didTimeOut = true
        controller.abort()
        reject(
          transportError(
            "TIMED_OUT",
            request.operation,
            "request exceeded the fixed timeout"
          )
        )
      }, request.timeoutMillis)
    })
    const operation = (async (): Promise<S2SGitHubHttpResponse> => {
      const response = await fetch(request.url, {
        method: "GET",
        headers: request.headers,
        redirect: request.redirect,
        signal: controller.signal
      })
      const body = await boundedResponseBody(
        response,
        request.maximumBytes,
        request.operation
      )
      return Object.freeze({
        status: response.status,
        contentType: response.headers.get("content-type"),
        location: response.headers.get("location"),
        githubRequestId: response.headers.get("x-github-request-id"),
        githubApiVersionSelected: response.headers.get(
          "x-github-api-version-selected"
        ),
        etag: response.headers.get("etag"),
        body
      })
    })()
    return await Promise.race([operation, deadline])
  } catch (error: unknown) {
    if (didTimeOut) {
      throw transportError(
        "TIMED_OUT",
        request.operation,
        "request exceeded the fixed timeout"
      )
    }
    if (error instanceof S2SGitHubTransportError) throw error
    throw transportError(
      controller.signal.aborted ? "TIMED_OUT" : "REQUEST_FAILED",
      request.operation,
      controller.signal.aborted
        ? "request exceeded the fixed timeout"
        : "request failed before a complete bounded response was observed"
    )
  } finally {
    if (timeout !== null) clearTimeout(timeout)
    request.interruptSignal.removeEventListener(
      "abort",
      abortFromInterruption
    )
    controller.abort()
  }
}

interface ValidatedGitHubApiHeaders {
  readonly githubRequestId: string
  readonly githubApiVersionSelected: typeof S2S_GITHUB_API_VERSION
  readonly etag: string | null
}

const validateOptionalEtag = (
  value: string | null,
  operation: string,
  httpStatus: number
): string | null => {
  if (value !== null && !HTTP_ETAG_PATTERN.test(value)) {
    throw transportError(
      "RESPONSE_HEADERS_REJECTED",
      operation,
      "response ETag is not a bounded canonical HTTP entity tag",
      httpStatus
    )
  }
  return value
}

const validateGitHubApiHeaders = (
  response: S2SGitHubHttpResponse,
  operation: string,
  etagRequired: boolean
): ValidatedGitHubApiHeaders => {
  if (
    response.githubRequestId === null ||
    !GITHUB_REQUEST_ID_PATTERN.test(response.githubRequestId) ||
    response.githubApiVersionSelected !== S2S_GITHUB_API_VERSION
  ) {
    throw transportError(
      "RESPONSE_HEADERS_REJECTED",
      operation,
      "GitHub request identity or selected API version is absent or noncanonical",
      response.status,
      rawS2SFileSha256(response.body)
    )
  }
  const etag = validateOptionalEtag(response.etag, operation, response.status)
  if (etagRequired && etag === null) {
    throw transportError(
      "RESPONSE_HEADERS_REJECTED",
      operation,
      "GitHub metadata response does not carry the required ETag validator",
      response.status,
      rawS2SFileSha256(response.body)
    )
  }
  return Object.freeze({
    githubRequestId: response.githubRequestId,
    githubApiVersionSelected: S2S_GITHUB_API_VERSION,
    etag
  })
}

interface S2SGitHubValidatedJsonResponse extends S2SGitHubHttpResponse {
  readonly status: 200
  readonly location: null
  readonly githubRequestId: string
  readonly githubApiVersionSelected: typeof S2S_GITHUB_API_VERSION
  readonly etag: string
}

const ensureJsonResponse = (
  response: S2SGitHubHttpResponse,
  operation: string
): S2SGitHubValidatedJsonResponse => {
  if (response.status !== 200) {
    throw transportError(
      "HTTP_STATUS_UNEXPECTED",
      operation,
      "GitHub metadata request did not return HTTP 200",
      response.status,
      rawS2SFileSha256(response.body)
    )
  }
  const mediaType = response.contentType?.split(";", 1)[0]?.trim().toLowerCase()
  if (mediaType !== "application/json") {
    throw transportError(
      "CONTENT_TYPE_REJECTED",
      operation,
      "GitHub metadata response is not application/json",
      response.status,
      rawS2SFileSha256(response.body)
    )
  }
  if (response.location !== null) {
    throw transportError(
      "HTTP_STATUS_UNEXPECTED",
      operation,
      "HTTP 200 metadata response unexpectedly carries a redirect location",
      response.status,
      rawS2SFileSha256(response.body)
    )
  }
  const headers = validateGitHubApiHeaders(response, operation, true)
  if (headers.etag === null) {
    throw transportError(
      "RESPONSE_HEADERS_REJECTED",
      operation,
      "GitHub metadata response ETag validation failed closed",
      response.status,
      rawS2SFileSha256(response.body)
    )
  }
  return Object.freeze({
    status: 200,
    contentType: response.contentType,
    location: null,
    githubRequestId: headers.githubRequestId,
    githubApiVersionSelected: headers.githubApiVersionSelected,
    etag: headers.etag,
    body: response.body
  })
}

const requireJsonResponse = (
  response: S2SGitHubHttpResponse,
  operation: string
): Effect.Effect<S2SGitHubValidatedJsonResponse, S2SGitHubTransportError> =>
  Effect.try({
    try: () => ensureJsonResponse(response, operation),
    catch: (error: unknown) =>
      error instanceof S2SGitHubTransportError
        ? error
        : transportError(
            "REQUEST_FAILED",
            operation,
            "transport response validation failed closed"
          )
  })

const validateDownloadRedirect = (location: string | null): URL => {
  if (location === null || location.length < 1 || location.length > 16_384) {
    throw transportError(
      "REDIRECT_REJECTED",
      "DOWNLOAD_ARTIFACT_REDIRECT",
      "GitHub artifact redirect is absent or exceeds the fixed bound",
      302
    )
  }
  let redirect: URL
  try {
    redirect = new URL(location)
  } catch {
    throw transportError(
      "REDIRECT_REJECTED",
      "DOWNLOAD_ARTIFACT_REDIRECT",
      "GitHub artifact redirect is not an absolute URL",
      302
    )
  }
  const hostname = redirect.hostname.toLowerCase()
  const isIpv4Literal = /^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$/.test(hostname)
  const isLocalName =
    hostname === "localhost" ||
    hostname.endsWith(".localhost") ||
    hostname.endsWith(".local") ||
    hostname.endsWith(".internal") ||
    hostname.endsWith(".home.arpa")
  if (
    redirect.protocol !== "https:" ||
    redirect.username !== "" ||
    redirect.password !== "" ||
    redirect.hash !== "" ||
    redirect.port !== "" ||
    hostname === "api.github.com" ||
    !hostname.includes(".") ||
    hostname.includes(":") ||
    isIpv4Literal ||
    isLocalName
  ) {
    throw transportError(
      "REDIRECT_REJECTED",
      "DOWNLOAD_ARTIFACT_REDIRECT",
      "GitHub artifact redirect is not a credential-free cross-origin HTTPS URL",
      302
    )
  }
  return redirect
}

const makeArtifactDownload = (
  artifactId: number,
  redirect: URL,
  archive: Uint8Array,
  downloadedAtUnixSeconds: number,
  redirectHeaders: ValidatedGitHubApiHeaders,
  archiveMediaType: S2SGitHubArchiveMediaType,
  archiveResponseEtag: string | null
): S2SGitHubArtifactDownload => {
  const endpointPathAndQuery = repositoryEndpoint(
    `/actions/artifacts/${artifactId}/zip`
  )
  const receiptCore = Object.freeze({
    schemaVersion: S2S_GITHUB_ARTIFACT_DOWNLOAD_SCHEMA_VERSION,
    apiVersion: S2S_GITHUB_API_VERSION,
    repository: S2S_GITHUB_REPOSITORY,
    artifactId,
    endpointPathAndQuery,
    downloadedAtUnixSeconds,
    redirectHttpStatus: 302 as const,
    redirectGitHubRequestId: redirectHeaders.githubRequestId,
    redirectGitHubApiVersionSelected:
      redirectHeaders.githubApiVersionSelected,
    redirectResponseEtag: redirectHeaders.etag,
    redirectUrlSha256: rawS2SFileSha256(
      new TextEncoder().encode(redirect.toString())
    ),
    redirectOrigin: redirect.origin,
    archiveHttpStatus: 200 as const,
    archiveMediaType,
    archiveResponseEtag,
    archiveByteLength: archive.byteLength,
    downloadedArchiveSha256: rawS2SFileSha256(archive)
  })
  const receiptHash = canonicalS2SControlSha256(receiptCore)
  if (Either.isLeft(receiptHash)) {
    throw transportError(
      "REDIRECT_REJECTED",
      "DOWNLOAD_ARTIFACT_ARCHIVE",
      "artifact download receipt is not canonical"
    )
  }
  return Object.freeze({
    receipt: Object.freeze({ ...receiptCore, receiptSha256: receiptHash.right }),
    readArchiveBytes: () => new Uint8Array(archive)
  })
}

const downloadValidationError = (
  reason: S2SGitHubArtifactDownloadValidationError["reason"]
): S2SGitHubArtifactDownloadValidationError =>
  new S2SGitHubArtifactDownloadValidationError({ reason })

const exactDataRecord = (
  input: unknown,
  expectedKeys: ReadonlyArray<string>
): Readonly<Record<string, unknown>> | null => {
  try {
    if (input === null || typeof input !== "object") {
      return null
    }
    const prototype = Object.getPrototypeOf(input)
    if (prototype !== Object.prototype && prototype !== null) return null
    const keys = Reflect.ownKeys(input)
    if (
      keys.some((key) => typeof key !== "string") ||
      keys.length !== expectedKeys.length
    ) {
      return null
    }
    const sorted = keys
      .filter((key): key is string => typeof key === "string")
      .sort()
    const expected = [...expectedKeys].sort()
    if (!sorted.every((key, index) => key === expected[index])) return null
    const output: Record<string, unknown> = Object.create(null)
    for (const key of sorted) {
      const descriptor = Object.getOwnPropertyDescriptor(input, key)
      if (
        descriptor === undefined ||
        descriptor.enumerable !== true ||
        !("value" in descriptor)
      ) {
        return null
      }
      output[key] = descriptor.value
    }
    return Object.freeze(output)
  } catch {
    return null
  }
}

export const validateS2SGitHubArtifactDownload = (
  input: unknown,
  expectedArtifactId: number,
  maximumArchiveBytes: number
): Either.Either<
  S2SGitHubArtifactDownload,
  S2SGitHubArtifactDownloadValidationError
> => {
  const root = exactDataRecord(input, ["readArchiveBytes", "receipt"])
  const receipt = exactDataRecord(root?.["receipt"], [
    "apiVersion",
    "archiveByteLength",
    "archiveHttpStatus",
    "archiveMediaType",
    "archiveResponseEtag",
    "artifactId",
    "downloadedArchiveSha256",
    "downloadedAtUnixSeconds",
    "endpointPathAndQuery",
    "receiptSha256",
    "redirectGitHubApiVersionSelected",
    "redirectGitHubRequestId",
    "redirectHttpStatus",
    "redirectOrigin",
    "redirectResponseEtag",
    "redirectUrlSha256",
    "repository",
    "schemaVersion"
  ])
  if (
    root === null ||
    receipt === null ||
    typeof root["readArchiveBytes"] !== "function" ||
    !Number.isSafeInteger(expectedArtifactId) ||
    expectedArtifactId < 1 ||
    !Number.isSafeInteger(maximumArchiveBytes) ||
    maximumArchiveBytes < 1 ||
    maximumArchiveBytes > S2S_GITHUB_ARTIFACT_ARCHIVE_MAX_BYTES
  ) {
    return Either.left(downloadValidationError("INVALID_ARGUMENT"))
  }
  const expectedEndpoint = repositoryEndpoint(
    `/actions/artifacts/${expectedArtifactId}/zip`
  )
  const archiveByteLength = receipt["archiveByteLength"]
  const downloadedAtUnixSeconds = receipt["downloadedAtUnixSeconds"]
  if (
    receipt["schemaVersion"] !== S2S_GITHUB_ARTIFACT_DOWNLOAD_SCHEMA_VERSION ||
    receipt["apiVersion"] !== S2S_GITHUB_API_VERSION ||
    receipt["repository"] !== S2S_GITHUB_REPOSITORY ||
    receipt["artifactId"] !== expectedArtifactId ||
    receipt["endpointPathAndQuery"] !== expectedEndpoint ||
    receipt["redirectHttpStatus"] !== 302 ||
    typeof receipt["redirectGitHubRequestId"] !== "string" ||
    !GITHUB_REQUEST_ID_PATTERN.test(receipt["redirectGitHubRequestId"]) ||
    receipt["redirectGitHubApiVersionSelected"] !== S2S_GITHUB_API_VERSION ||
    (receipt["redirectResponseEtag"] !== null &&
      (typeof receipt["redirectResponseEtag"] !== "string" ||
        !HTTP_ETAG_PATTERN.test(receipt["redirectResponseEtag"]))) ||
    receipt["archiveHttpStatus"] !== 200 ||
    (receipt["archiveMediaType"] !== "application/octet-stream" &&
      receipt["archiveMediaType"] !== "application/zip" &&
      receipt["archiveMediaType"] !== "binary/octet-stream") ||
    (receipt["archiveResponseEtag"] !== null &&
      (typeof receipt["archiveResponseEtag"] !== "string" ||
        !HTTP_ETAG_PATTERN.test(receipt["archiveResponseEtag"]))) ||
    !Number.isSafeInteger(downloadedAtUnixSeconds) ||
    typeof downloadedAtUnixSeconds !== "number" ||
    downloadedAtUnixSeconds < 0 ||
    !Number.isSafeInteger(archiveByteLength) ||
    typeof archiveByteLength !== "number" ||
    archiveByteLength < 1 ||
    archiveByteLength > maximumArchiveBytes ||
    typeof receipt["redirectUrlSha256"] !== "string" ||
    !SHA256_PATTERN.test(receipt["redirectUrlSha256"]) ||
    typeof receipt["downloadedArchiveSha256"] !== "string" ||
    !SHA256_PATTERN.test(receipt["downloadedArchiveSha256"]) ||
    typeof receipt["receiptSha256"] !== "string" ||
    !SHA256_PATTERN.test(receipt["receiptSha256"])
  ) {
    return Either.left(downloadValidationError("RECEIPT_SCHEMA_MISMATCH"))
  }
  if (typeof receipt["redirectOrigin"] !== "string") {
    return Either.left(downloadValidationError("RECEIPT_SCHEMA_MISMATCH"))
  }
  try {
    const origin = new URL(receipt["redirectOrigin"])
    if (
      origin.protocol !== "https:" ||
      origin.origin !== receipt["redirectOrigin"] ||
      origin.pathname !== "/" ||
      origin.search !== "" ||
      origin.hash !== "" ||
      origin.username !== "" ||
      origin.password !== "" ||
      origin.port !== "" ||
      origin.hostname.toLowerCase() === "api.github.com"
    ) {
      return Either.left(downloadValidationError("RECEIPT_SCHEMA_MISMATCH"))
    }
  } catch {
    return Either.left(downloadValidationError("RECEIPT_SCHEMA_MISMATCH"))
  }
  const receiptCore = Object.freeze({
    schemaVersion: receipt["schemaVersion"],
    apiVersion: receipt["apiVersion"],
    repository: receipt["repository"],
    artifactId: receipt["artifactId"],
    endpointPathAndQuery: receipt["endpointPathAndQuery"],
    downloadedAtUnixSeconds,
    redirectHttpStatus: receipt["redirectHttpStatus"],
    redirectGitHubRequestId: receipt["redirectGitHubRequestId"],
    redirectGitHubApiVersionSelected:
      receipt["redirectGitHubApiVersionSelected"],
    redirectResponseEtag: receipt["redirectResponseEtag"],
    redirectUrlSha256: receipt["redirectUrlSha256"],
    redirectOrigin: receipt["redirectOrigin"],
    archiveHttpStatus: receipt["archiveHttpStatus"],
    archiveMediaType: receipt["archiveMediaType"],
    archiveResponseEtag: receipt["archiveResponseEtag"],
    archiveByteLength,
    downloadedArchiveSha256: receipt["downloadedArchiveSha256"]
  })
  const expectedReceipt = canonicalS2SControlSha256(receiptCore)
  if (
    Either.isLeft(expectedReceipt) ||
    expectedReceipt.right !== receipt["receiptSha256"]
  ) {
    return Either.left(downloadValidationError("RECEIPT_SELF_HASH_MISMATCH"))
  }
  let snapshot: Uint8Array
  try {
    const archive = (root["readArchiveBytes"] as () => unknown)()
    if (
      !(archive instanceof Uint8Array) ||
      Object.getPrototypeOf(archive) !== Uint8Array.prototype ||
      Object.getOwnPropertySymbols(archive).length !== 0 ||
      Object.getOwnPropertyDescriptor(archive, "byteLength") !== undefined ||
      Object.getOwnPropertyDescriptor(archive, "buffer") !== undefined ||
      (typeof SharedArrayBuffer !== "undefined" &&
        archive.buffer instanceof SharedArrayBuffer) ||
      archive.byteLength !== archiveByteLength ||
      rawS2SFileSha256(archive) !== receipt["downloadedArchiveSha256"]
    ) {
      return Either.left(downloadValidationError("ARCHIVE_BYTES_DRIFT"))
    }
    snapshot = new Uint8Array(archive)
  } catch {
    return Either.left(downloadValidationError("ARCHIVE_BYTES_DRIFT"))
  }
  return Either.right(
    Object.freeze({
      receipt: Object.freeze(
        receipt as unknown as S2SGitHubArtifactDownloadReceipt
      ),
      readArchiveBytes: () => new Uint8Array(snapshot)
    })
  )
}

export const makeS2SGitHubHttpTransportLiveLayer = (
  input: S2SGitHubLiveTransportConfig
) =>
  Layer.effect(
    S2SGitHubHttpTransport,
    Effect.gen(function* () {
      const config = yield* Effect.try({
        try: () => snapshotLiveTransportConfig(input),
        catch: (error: unknown) =>
          error instanceof S2SGitHubTransportError
            ? error
            : transportError(
                "CONFIGURATION_INVALID",
                "CONFIGURE_GITHUB_TRANSPORT",
                "transport configuration failed closed"
              )
      })
      const authorizedHeaders = Object.freeze({
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${config.token}`,
        "User-Agent": "hswm-s2s-effect-runtime",
        "X-GitHub-Api-Version": S2S_GITHUB_API_VERSION
      })
      return S2SGitHubHttpTransport.of({
        getJson: (endpointPathAndQuery) =>
          Effect.tryPromise({
            try: async (signal) => {
              validateEndpoint(endpointPathAndQuery)
              const response = await performBoundedFetch({
                operation: "GITHUB_API_GET",
                url: `https://api.github.com${endpointPathAndQuery}`,
                headers: authorizedHeaders,
                redirect: "error",
                timeoutMillis: S2S_GITHUB_METADATA_TIMEOUT_MILLIS,
                maximumBytes: S2S_GITHUB_JSON_MAX_BYTES,
                interruptSignal: signal
              })
              return ensureJsonResponse(response, "GITHUB_API_GET")
            },
            catch: (error: unknown) =>
              error instanceof S2SGitHubTransportError
                ? error
                : transportError(
                    "REQUEST_FAILED",
                    "GITHUB_API_GET",
                    "GitHub metadata request failed closed"
                  )
          }),
        downloadArtifactArchive: (artifactId, maximumBytes) =>
          Effect.tryPromise({
            try: async (signal) => {
              if (
                !Number.isSafeInteger(artifactId) ||
                artifactId < 1 ||
                !Number.isSafeInteger(maximumBytes) ||
                maximumBytes < 1 ||
                maximumBytes > S2S_GITHUB_ARTIFACT_ARCHIVE_MAX_BYTES
              ) {
                throw transportError(
                  "CONFIGURATION_INVALID",
                  "DOWNLOAD_ARTIFACT_ARCHIVE",
                  "artifact identity or selected archive bound is invalid"
                )
              }
              const endpoint = repositoryEndpoint(
                `/actions/artifacts/${artifactId}/zip`
              )
              validateEndpoint(endpoint)
              const redirectResponse = await performBoundedFetch({
                operation: "DOWNLOAD_ARTIFACT_REDIRECT",
                url: `https://api.github.com${endpoint}`,
                headers: authorizedHeaders,
                redirect: "manual",
                timeoutMillis: S2S_GITHUB_METADATA_TIMEOUT_MILLIS,
                maximumBytes: S2S_GITHUB_REDIRECT_BODY_MAX_BYTES,
                interruptSignal: signal
              })
              if (
                redirectResponse.status !== 302
              ) {
                throw transportError(
                  "HTTP_STATUS_UNEXPECTED",
                  "DOWNLOAD_ARTIFACT_REDIRECT",
                  "artifact API must return one bounded HTTP 302 redirect response",
                  redirectResponse.status,
                  rawS2SFileSha256(redirectResponse.body)
                )
              }
              const redirectHeaders = validateGitHubApiHeaders(
                redirectResponse,
                "DOWNLOAD_ARTIFACT_REDIRECT",
                false
              )
              const redirect = validateDownloadRedirect(redirectResponse.location)
              // Deliberately omit Authorization and every GitHub API header on
              // the cross-origin signed-object request.
              const archiveResponse = await performBoundedFetch({
                operation: "DOWNLOAD_ARTIFACT_ARCHIVE",
                url: redirect.toString(),
                headers: Object.freeze({
                  Accept: "application/octet-stream, application/zip",
                  "User-Agent": "hswm-s2s-effect-runtime"
                }),
                redirect: "error",
                timeoutMillis: S2S_GITHUB_ARCHIVE_TIMEOUT_MILLIS,
                maximumBytes,
                interruptSignal: signal
              })
              if (archiveResponse.status !== 200) {
                throw transportError(
                  "HTTP_STATUS_UNEXPECTED",
                  "DOWNLOAD_ARTIFACT_ARCHIVE",
                  "signed artifact request did not return HTTP 200",
                  archiveResponse.status,
                  rawS2SFileSha256(archiveResponse.body)
                )
              }
              const mediaType = archiveResponse.contentType
                ?.split(";", 1)[0]
                ?.trim()
                .toLowerCase()
              if (
                mediaType !== "application/octet-stream" &&
                mediaType !== "application/zip" &&
                mediaType !== "binary/octet-stream"
              ) {
                throw transportError(
                  "CONTENT_TYPE_REJECTED",
                  "DOWNLOAD_ARTIFACT_ARCHIVE",
                  "signed artifact response has an unsupported media type",
                  archiveResponse.status,
                  rawS2SFileSha256(archiveResponse.body)
                )
              }
              const archiveResponseEtag = validateOptionalEtag(
                archiveResponse.etag,
                "DOWNLOAD_ARTIFACT_ARCHIVE",
                archiveResponse.status
              )
              return makeArtifactDownload(
                artifactId,
                redirect,
                archiveResponse.body,
                Math.floor(Date.now() / 1_000),
                redirectHeaders,
                mediaType,
                archiveResponseEtag
              )
            },
            catch: (error: unknown) =>
              error instanceof S2SGitHubTransportError
                ? error
                : transportError(
                    "REQUEST_FAILED",
                    "DOWNLOAD_ARTIFACT_ARCHIVE",
                    "artifact download failed closed"
                  )
          })
      })
    })
  )

const fromObservation = <Projection extends S2SGitHubProjection>(
  outcome: Either.Either<
    S2SGitHubObservation<Projection>,
    S2SGitHubObservationError
  >
): Effect.Effect<
  S2SGitHubObservation<Projection>,
  S2SGitHubObservationError
> => (Either.isLeft(outcome) ? Effect.fail(outcome.left) : Effect.succeed(outcome.right))

const currentUnixSeconds = (): number => Math.floor(Date.now() / 1_000)

const observationProvenanceFromResponse = (
  response: S2SGitHubValidatedJsonResponse
): S2SGitHubApiResponseProvenance =>
  Object.freeze({
    githubRequestId: response.githubRequestId,
    githubApiVersionSelected: response.githubApiVersionSelected,
    responseEtag: response.etag
  })

export const S2SGitHubObserverLive = Layer.effect(
  S2SGitHubObserver,
  Effect.gen(function* () {
    const transport = yield* S2SGitHubHttpTransport
    return S2SGitHubObserver.of({
      observeWorkflowRun: (workflowRunId) =>
        Effect.gen(function* () {
          const endpoint = repositoryEndpoint(`/actions/runs/${workflowRunId}`)
          const untrustedResponse = yield* transport.getJson(endpoint)
          const response = yield* requireJsonResponse(
            untrustedResponse,
            "OBSERVE_WORKFLOW_RUN"
          )
          return yield* fromObservation(
            observeS2SGitHubWorkflowRun(
              response.body,
              workflowRunId,
              currentUnixSeconds(),
              observationProvenanceFromResponse(response)
            )
          )
        }),
      observeWorkflowAttemptJobs: (workflowRunId) =>
        Effect.gen(function* () {
          const endpoint = repositoryEndpoint(
            `/actions/runs/${workflowRunId}/attempts/1/jobs?per_page=${S2S_GITHUB_PAGE_SIZE}`
          )
          const untrustedResponse = yield* transport.getJson(endpoint)
          const response = yield* requireJsonResponse(
            untrustedResponse,
            "OBSERVE_WORKFLOW_ATTEMPT_JOBS"
          )
          return yield* fromObservation(
            observeS2SGitHubWorkflowAttemptJobs(
              response.body,
              workflowRunId,
              1,
              currentUnixSeconds(),
              observationProvenanceFromResponse(response)
            )
          )
        }),
      observeRunArtifacts: (workflowRunId) =>
        Effect.gen(function* () {
          const endpoint = repositoryEndpoint(
            `/actions/runs/${workflowRunId}/artifacts?per_page=${S2S_GITHUB_PAGE_SIZE}`
          )
          const untrustedResponse = yield* transport.getJson(endpoint)
          const response = yield* requireJsonResponse(
            untrustedResponse,
            "OBSERVE_RUN_ARTIFACTS"
          )
          return yield* fromObservation(
            observeS2SGitHubRunArtifacts(
              response.body,
              workflowRunId,
              currentUnixSeconds(),
              observationProvenanceFromResponse(response)
            )
          )
        }),
      observeArtifact: (artifactId) =>
        Effect.gen(function* () {
          const endpoint = repositoryEndpoint(`/actions/artifacts/${artifactId}`)
          const untrustedResponse = yield* transport.getJson(endpoint)
          const response = yield* requireJsonResponse(
            untrustedResponse,
            "OBSERVE_ARTIFACT"
          )
          return yield* fromObservation(
            observeS2SGitHubArtifact(
              response.body,
              artifactId,
              currentUnixSeconds(),
              observationProvenanceFromResponse(response)
            )
          )
        }),
      downloadArtifactArchive: (artifactId, maximumBytes) =>
        transport.downloadArtifactArchive(artifactId, maximumBytes)
    })
  })
)
