import { constants } from "node:fs"
import { open } from "node:fs/promises"
import { isAbsolute } from "node:path"

import { Clock, Context, Data, Effect, Either, Layer, Schema } from "effect"

import {
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "./s2s-canonical.js"
import { parseS2SJsonBytes, type S2SJson } from "./s2s-json.js"
import {
  S2S_CONFIRMATORY_BRANCH,
  S2S_CONFIRMATORY_EVENT,
  S2S_CONFIRMATORY_JOB_IDS,
  S2S_CONFIRMATORY_REF,
  S2S_CONFIRMATORY_REPOSITORY,
  S2S_CONFIRMATORY_WORKFLOW_CONTRACT,
  S2S_CONFIRMATORY_WORKFLOW_NAME,
  S2S_CONFIRMATORY_WORKFLOW_PATH,
  S2S_CONFIRMATORY_WORKFLOW_REF,
  S2S_CONFIRMATORY_WORKFLOW_RUN_ATTEMPT,
  s2sConfirmatoryWorkflowContractSha256,
  s2sStageForJobId,
  type S2SConfirmatoryJobId,
  type S2SConfirmatoryJobStage
} from "./s2s-workflow-contract.js"

export const S2S_CURRENT_INVOCATION_EVIDENCE_SCHEMA_VERSION =
  "hswm-swm0w-s2s-current-invocation-evidence/v1" as const
export const S2S_CURRENT_INVOCATION_EVENT_MAX_BYTES = 1_048_576 as const
export const S2S_CURRENT_INVOCATION_EVENT_PATH_MAX_LENGTH = 4_096 as const

export const S2S_CURRENT_INVOCATION_ENVIRONMENT_KEYS = Object.freeze([
  "GITHUB_ACTIONS",
  "GITHUB_API_URL",
  "GITHUB_EVENT_NAME",
  "GITHUB_JOB",
  "GITHUB_REF",
  "GITHUB_REF_NAME",
  "GITHUB_REF_TYPE",
  "GITHUB_REPOSITORY",
  "GITHUB_RUN_ATTEMPT",
  "GITHUB_RUN_ID",
  "GITHUB_SERVER_URL",
  "GITHUB_SHA",
  "GITHUB_WORKFLOW",
  "GITHUB_WORKFLOW_REF",
  "GITHUB_WORKFLOW_SHA",
  "RUNNER_ARCH",
  "RUNNER_ENVIRONMENT",
  "RUNNER_OS"
] as const)

const GIT_SHA_PATTERN = /^[0-9a-f]{40}$/
const POSITIVE_DECIMAL_PATTERN = /^[1-9][0-9]{0,15}$/

const GitShaSchema = Schema.String.pipe(Schema.pattern(GIT_SHA_PATTERN))
const PositiveDecimalSchema = Schema.String.pipe(
  Schema.pattern(POSITIVE_DECIMAL_PATTERN)
)

const CurrentInvocationEnvironmentSchema = Schema.Struct({
  GITHUB_ACTIONS: Schema.Literal("true"),
  GITHUB_API_URL: Schema.Literal("https://api.github.com"),
  GITHUB_EVENT_NAME: Schema.Literal(S2S_CONFIRMATORY_EVENT),
  GITHUB_JOB: Schema.Literal(...S2S_CONFIRMATORY_JOB_IDS),
  GITHUB_REF: Schema.Literal(S2S_CONFIRMATORY_REF),
  GITHUB_REF_NAME: Schema.Literal(S2S_CONFIRMATORY_BRANCH),
  GITHUB_REF_TYPE: Schema.Literal("branch"),
  GITHUB_REPOSITORY: Schema.Literal(S2S_CONFIRMATORY_REPOSITORY),
  GITHUB_RUN_ATTEMPT: Schema.Literal(
    String(S2S_CONFIRMATORY_WORKFLOW_RUN_ATTEMPT)
  ),
  GITHUB_RUN_ID: PositiveDecimalSchema,
  GITHUB_SERVER_URL: Schema.Literal("https://github.com"),
  GITHUB_SHA: GitShaSchema,
  GITHUB_WORKFLOW: Schema.Literal(S2S_CONFIRMATORY_WORKFLOW_NAME),
  GITHUB_WORKFLOW_REF: Schema.Literal(S2S_CONFIRMATORY_WORKFLOW_REF),
  GITHUB_WORKFLOW_SHA: GitShaSchema,
  RUNNER_ARCH: Schema.Literal("X64"),
  RUNNER_ENVIRONMENT: Schema.Literal("github-hosted"),
  RUNNER_OS: Schema.Literal("Linux")
})

type CurrentInvocationEnvironment = Schema.Schema.Type<
  typeof CurrentInvocationEnvironmentSchema
>

export interface S2SCurrentInvocationEnvironmentProjection {
  readonly githubActions: true
  readonly githubApiUrl: "https://api.github.com"
  readonly eventName: typeof S2S_CONFIRMATORY_EVENT
  readonly jobId: S2SConfirmatoryJobId
  readonly ref: typeof S2S_CONFIRMATORY_REF
  readonly refName: typeof S2S_CONFIRMATORY_BRANCH
  readonly refType: "branch"
  readonly repository: typeof S2S_CONFIRMATORY_REPOSITORY
  readonly runAttempt: typeof S2S_CONFIRMATORY_WORKFLOW_RUN_ATTEMPT
  readonly runId: number
  readonly serverUrl: "https://github.com"
  readonly commitSha: string
  readonly workflowName: typeof S2S_CONFIRMATORY_WORKFLOW_NAME
  readonly workflowRef: typeof S2S_CONFIRMATORY_WORKFLOW_REF
  readonly workflowSourceCommitSha: string
  readonly runnerArch: "X64"
  readonly runnerEnvironment: "github-hosted"
  readonly runnerOs: "Linux"
}

export interface S2SCurrentPushEventProjection {
  readonly ref: typeof S2S_CONFIRMATORY_REF
  readonly before: string
  readonly after: string
  readonly created: false
  readonly deleted: false
  readonly forced: false
  readonly baseRef: null
  readonly repository: typeof S2S_CONFIRMATORY_REPOSITORY
  readonly repositoryFork: false
  readonly repositoryDefaultBranch: typeof S2S_CONFIRMATORY_BRANCH
  readonly commitIds: readonly [string]
  readonly headCommitId: string
}

export interface S2SCurrentInvocationEvidence {
  readonly schemaVersion: typeof S2S_CURRENT_INVOCATION_EVIDENCE_SCHEMA_VERSION
  readonly workflowContractSchemaVersion:
    typeof S2S_CONFIRMATORY_WORKFLOW_CONTRACT.schemaVersion
  readonly workflowContractSha256: string
  readonly pushBeforeSha: string
  readonly pushAfterSha: string
  readonly workflowRunId: number
  readonly workflowRunAttempt: typeof S2S_CONFIRMATORY_WORKFLOW_RUN_ATTEMPT
  readonly jobId: S2SConfirmatoryJobId
  readonly stage: S2SConfirmatoryJobStage
  readonly workflowPath: typeof S2S_CONFIRMATORY_WORKFLOW_PATH
  readonly capturedAtUnixSeconds: number
  readonly environmentProjection: S2SCurrentInvocationEnvironmentProjection
  readonly environmentProjectionSha256: string
  readonly eventBodyByteLength: number
  readonly eventBodySha256: string
  readonly eventProjection: S2SCurrentPushEventProjection
  readonly eventProjectionSha256: string
  readonly receiptSha256: string
}

export class S2SCurrentInvocationValidationError extends Data.TaggedError(
  "S2SCurrentInvocationValidationError"
)<{
  readonly reason:
    | "ENVIRONMENT_REJECTED"
    | "EVENT_BYTES_REJECTED"
    | "EVENT_JSON_REJECTED"
    | "EVENT_PROJECTION_REJECTED"
    | "IDENTITY_MISMATCH"
    | "EVIDENCE_NOT_CANONICAL"
    | "INVALID_INVOCATION_AUTHORITY"
  readonly path: string
  readonly detail: string
}> {}

export class S2SCurrentInvocationSourceError extends Data.TaggedError(
  "S2SCurrentInvocationSourceError"
)<{
  readonly reason:
    | "EVENT_PATH_REJECTED"
    | "EVENT_FILE_OPEN_FAILED"
    | "EVENT_FILE_NOT_REGULAR"
    | "EVENT_FILE_SIZE_REJECTED"
    | "EVENT_FILE_CHANGED"
    | "EVENT_FILE_READ_FAILED"
  readonly detail: string
}> {}

const invocationError = (
  reason: S2SCurrentInvocationValidationError["reason"],
  path: string,
  detail: string
): S2SCurrentInvocationValidationError =>
  new S2SCurrentInvocationValidationError({ reason, path, detail })

const snapshotExactEnvironment = (
  input: unknown
): Either.Either<
  Readonly<Record<string, string>>,
  S2SCurrentInvocationValidationError
> => {
  try {
    if (input === null || typeof input !== "object") {
      return Either.left(
        invocationError(
          "ENVIRONMENT_REJECTED",
          "$environment",
          "environment must be one exact plain data record"
        )
      )
    }
    const prototype = Object.getPrototypeOf(input)
    if (prototype !== Object.prototype && prototype !== null) {
      return Either.left(
        invocationError(
          "ENVIRONMENT_REJECTED",
          "$environment",
          "environment must be one exact plain data record"
        )
      )
    }
    const ownKeys = Reflect.ownKeys(input)
    if (
      ownKeys.length !== S2S_CURRENT_INVOCATION_ENVIRONMENT_KEYS.length ||
      ownKeys.some(
        (key) =>
          typeof key !== "string" ||
          !S2S_CURRENT_INVOCATION_ENVIRONMENT_KEYS.includes(
            key as (typeof S2S_CURRENT_INVOCATION_ENVIRONMENT_KEYS)[number]
          )
      )
    ) {
      return Either.left(
        invocationError(
          "ENVIRONMENT_REJECTED",
          "$environment",
          "environment keys differ from the fixed invocation projection"
        )
      )
    }
    const output: Record<string, string> = Object.create(null)
    for (const key of S2S_CURRENT_INVOCATION_ENVIRONMENT_KEYS) {
      const descriptor = Object.getOwnPropertyDescriptor(input, key)
      if (
        descriptor === undefined ||
        descriptor.enumerable !== true ||
        !("value" in descriptor) ||
        typeof descriptor.value !== "string"
      ) {
        return Either.left(
          invocationError(
            "ENVIRONMENT_REJECTED",
            `$environment.${key}`,
            "environment value must be one enumerable string data property"
          )
        )
      }
      output[key] = descriptor.value
    }
    return Either.right(Object.freeze(output))
  } catch {
    return Either.left(
      invocationError(
        "ENVIRONMENT_REJECTED",
        "$environment",
        "environment inspection failed closed"
      )
    )
  }
}

const decodeEnvironment = (
  input: unknown
): Either.Either<
  CurrentInvocationEnvironment,
  S2SCurrentInvocationValidationError
> => {
  const snapshot = snapshotExactEnvironment(input)
  if (Either.isLeft(snapshot)) return Either.left(snapshot.left)
  const decoded = Schema.decodeUnknownEither(CurrentInvocationEnvironmentSchema, {
    onExcessProperty: "error"
  })(snapshot.right)
  return Either.isLeft(decoded)
    ? Either.left(
        invocationError(
          "ENVIRONMENT_REJECTED",
          "$environment",
          "environment values disagree with the exact workflow contract"
        )
      )
    : Either.right(decoded.right)
}

type JsonRecord = { readonly [key: string]: S2SJson }

const isJsonRecord = (value: S2SJson): value is JsonRecord =>
  value !== null && !Array.isArray(value) && typeof value === "object"

const failEventProjection = (path: string, detail: string): never => {
  throw invocationError("EVENT_PROJECTION_REJECTED", path, detail)
}

const asRecord = (value: S2SJson, path: string): JsonRecord => {
  if (!isJsonRecord(value)) {
    return failEventProjection(path, "expected an object")
  }
  return value
}

const required = (record: JsonRecord, key: string, path: string): S2SJson => {
  if (!Object.hasOwn(record, key)) {
    return failEventProjection(`${path}.${key}`, "required event field is absent")
  }
  const value = record[key]
  return value === undefined
    ? failEventProjection(`${path}.${key}`, "required event field is absent")
    : value
}

const asLiteralString = <Value extends string>(
  value: S2SJson,
  expected: Value,
  path: string
): Value =>
  value === expected
    ? expected
    : failEventProjection(path, `expected exact value ${expected}`)

const asGitSha = (value: S2SJson, path: string): string =>
  typeof value === "string" && GIT_SHA_PATTERN.test(value)
    ? value
    : failEventProjection(path, "expected a lowercase 40-hex Git SHA")

const asFalse = (value: S2SJson, path: string): false =>
  value === false ? false : failEventProjection(path, "expected false")

const parsePushEventProjection = (
  value: S2SJson
): S2SCurrentPushEventProjection => {
  const root = asRecord(value, "$event")
  const repository = asRecord(
    required(root, "repository", "$event"),
    "$event.repository"
  )
  const commitsValue = required(root, "commits", "$event")
  if (!Array.isArray(commitsValue) || commitsValue.length !== 1) {
    return failEventProjection(
      "$event.commits",
      "registration push must contain exactly one commit"
    )
  }
  const commit = asRecord(commitsValue[0] ?? null, "$event.commits[0]")
  if (required(commit, "distinct", "$event.commits[0]") !== true) {
    return failEventProjection(
      "$event.commits[0].distinct",
      "registration commit must be distinct in the push"
    )
  }
  const headCommit = asRecord(
    required(root, "head_commit", "$event"),
    "$event.head_commit"
  )
  const baseRef = required(root, "base_ref", "$event")
  if (baseRef !== null) {
    return failEventProjection("$event.base_ref", "branch push base_ref must be null")
  }
  return Object.freeze({
    ref: asLiteralString(
      required(root, "ref", "$event"),
      S2S_CONFIRMATORY_REF,
      "$event.ref"
    ),
    before: asGitSha(required(root, "before", "$event"), "$event.before"),
    after: asGitSha(required(root, "after", "$event"), "$event.after"),
    created: asFalse(required(root, "created", "$event"), "$event.created"),
    deleted: asFalse(required(root, "deleted", "$event"), "$event.deleted"),
    forced: asFalse(required(root, "forced", "$event"), "$event.forced"),
    baseRef: null,
    repository: asLiteralString(
      required(repository, "full_name", "$event.repository"),
      S2S_CONFIRMATORY_REPOSITORY,
      "$event.repository.full_name"
    ),
    repositoryFork: asFalse(
      required(repository, "fork", "$event.repository"),
      "$event.repository.fork"
    ),
    repositoryDefaultBranch: asLiteralString(
      required(repository, "default_branch", "$event.repository"),
      S2S_CONFIRMATORY_BRANCH,
      "$event.repository.default_branch"
    ),
    commitIds: Object.freeze([
      asGitSha(required(commit, "id", "$event.commits[0]"), "$event.commits[0].id")
    ]) as readonly [string],
    headCommitId: asGitSha(
      required(headCommit, "id", "$event.head_commit"),
      "$event.head_commit.id"
    )
  })
}

const snapshotEventBytes = (
  input: unknown
): Either.Either<Uint8Array, S2SCurrentInvocationValidationError> => {
  try {
    if (
      !(input instanceof Uint8Array) ||
      Object.getPrototypeOf(input) !== Uint8Array.prototype ||
      Object.getOwnPropertySymbols(input).length !== 0 ||
      Object.getOwnPropertyDescriptor(input, "byteLength") !== undefined ||
      Object.getOwnPropertyDescriptor(input, "buffer") !== undefined ||
      input.byteLength < 2 ||
      input.byteLength > S2S_CURRENT_INVOCATION_EVENT_MAX_BYTES ||
      (typeof SharedArrayBuffer !== "undefined" &&
        input.buffer instanceof SharedArrayBuffer)
    ) {
      return Either.left(
        invocationError(
          "EVENT_BYTES_REJECTED",
          "$eventBytes",
          "event bytes must be one bounded unshared plain Uint8Array"
        )
      )
    }
    return Either.right(new Uint8Array(input))
  } catch {
    return Either.left(
      invocationError(
        "EVENT_BYTES_REJECTED",
        "$eventBytes",
        "event byte inspection failed closed"
      )
    )
  }
}

const canonicalHash = (
  value: unknown,
  path: string
): Either.Either<string, S2SCurrentInvocationValidationError> => {
  const digest = canonicalS2SControlSha256(value)
  return Either.isLeft(digest)
    ? Either.left(
        invocationError(
          "EVIDENCE_NOT_CANONICAL",
          path,
          "invocation projection cannot be canonically hashed"
        )
      )
    : Either.right(digest.right)
}

export const validateS2SCurrentInvocation = (
  environmentInput: unknown,
  eventBytesInput: unknown,
  capturedAtUnixSeconds: unknown
): Either.Either<
  S2SCurrentInvocationEvidence,
  S2SCurrentInvocationValidationError
> => {
  try {
    const environment = decodeEnvironment(environmentInput)
    if (Either.isLeft(environment)) return Either.left(environment.left)
    const eventBytes = snapshotEventBytes(eventBytesInput)
    if (Either.isLeft(eventBytes)) return Either.left(eventBytes.left)
    if (
      typeof capturedAtUnixSeconds !== "number" ||
      !Number.isSafeInteger(capturedAtUnixSeconds) ||
      capturedAtUnixSeconds < 0
    ) {
      return Either.left(
        invocationError(
          "ENVIRONMENT_REJECTED",
          "$capturedAtUnixSeconds",
          "capture time must be one nonnegative safe-integer Unix second"
        )
      )
    }
    const parsed = parseS2SJsonBytes(
      eventBytes.right,
      S2S_CURRENT_INVOCATION_EVENT_MAX_BYTES
    )
    if (Either.isLeft(parsed)) {
      return Either.left(
        invocationError(
          "EVENT_JSON_REJECTED",
          `$eventBytes[${parsed.left.offset}]`,
          `${parsed.left.reason}: ${parsed.left.detail}`
        )
      )
    }
    const eventProjection = parsePushEventProjection(parsed.right)
    const environmentValue = environment.right
    const workflowRunId = Number(environmentValue.GITHUB_RUN_ID)
    const stage = s2sStageForJobId(environmentValue.GITHUB_JOB)
    if (
      !Number.isSafeInteger(workflowRunId) ||
      workflowRunId < 1 ||
      stage === undefined ||
      environmentValue.GITHUB_SHA !== environmentValue.GITHUB_WORKFLOW_SHA ||
      environmentValue.GITHUB_SHA !== eventProjection.after ||
      eventProjection.commitIds[0] !== eventProjection.after ||
      eventProjection.headCommitId !== eventProjection.after ||
      eventProjection.before === eventProjection.after
    ) {
      return Either.left(
        invocationError(
          "IDENTITY_MISMATCH",
          "$invocation",
          "environment, push event, workflow commit, or job identity disagrees"
        )
      )
    }
    const environmentProjection: S2SCurrentInvocationEnvironmentProjection =
      Object.freeze({
        githubActions: true,
        githubApiUrl: "https://api.github.com",
        eventName: S2S_CONFIRMATORY_EVENT,
        jobId: environmentValue.GITHUB_JOB,
        ref: S2S_CONFIRMATORY_REF,
        refName: S2S_CONFIRMATORY_BRANCH,
        refType: "branch",
        repository: S2S_CONFIRMATORY_REPOSITORY,
        runAttempt: S2S_CONFIRMATORY_WORKFLOW_RUN_ATTEMPT,
        runId: workflowRunId,
        serverUrl: "https://github.com",
        commitSha: environmentValue.GITHUB_SHA,
        workflowName: S2S_CONFIRMATORY_WORKFLOW_NAME,
        workflowRef: S2S_CONFIRMATORY_WORKFLOW_REF,
        workflowSourceCommitSha: environmentValue.GITHUB_WORKFLOW_SHA,
        runnerArch: "X64",
        runnerEnvironment: "github-hosted",
        runnerOs: "Linux"
      })
    const contractHash = s2sConfirmatoryWorkflowContractSha256()
    if (Either.isLeft(contractHash)) {
      return Either.left(
        invocationError(
          "EVIDENCE_NOT_CANONICAL",
          "$workflowContract",
          "workflow contract cannot be canonically hashed"
        )
      )
    }
    const environmentHash = canonicalHash(
      environmentProjection,
      "$environmentProjection"
    )
    if (Either.isLeft(environmentHash)) return Either.left(environmentHash.left)
    const eventHash = canonicalHash(eventProjection, "$eventProjection")
    if (Either.isLeft(eventHash)) return Either.left(eventHash.left)
    const evidenceCore = Object.freeze({
      schemaVersion: S2S_CURRENT_INVOCATION_EVIDENCE_SCHEMA_VERSION,
      workflowContractSchemaVersion:
        S2S_CONFIRMATORY_WORKFLOW_CONTRACT.schemaVersion,
      workflowContractSha256: contractHash.right,
      pushBeforeSha: eventProjection.before,
      pushAfterSha: eventProjection.after,
      workflowRunId,
      workflowRunAttempt: S2S_CONFIRMATORY_WORKFLOW_RUN_ATTEMPT,
      jobId: environmentValue.GITHUB_JOB,
      stage,
      workflowPath: S2S_CONFIRMATORY_WORKFLOW_PATH,
      capturedAtUnixSeconds,
      environmentProjection,
      environmentProjectionSha256: environmentHash.right,
      eventBodyByteLength: eventBytes.right.byteLength,
      eventBodySha256: rawS2SFileSha256(eventBytes.right),
      eventProjection,
      eventProjectionSha256: eventHash.right
    })
    const evidenceHash = canonicalHash(evidenceCore, "$evidence")
    return Either.isLeft(evidenceHash)
      ? Either.left(evidenceHash.left)
      : Either.right(
          Object.freeze({
            ...evidenceCore,
            receiptSha256: evidenceHash.right
          })
        )
  } catch (error: unknown) {
    return Either.left(
      error instanceof S2SCurrentInvocationValidationError
        ? error
        : invocationError(
            "EVENT_PROJECTION_REJECTED",
            "$event",
            "invocation projection failed closed"
          )
    )
  }
}

const S2S_CURRENT_INVOCATION_AUTHORITY_BRAND: unique symbol = Symbol(
  "hswm/S2SCurrentInvocationAuthority"
)

export interface S2SCurrentInvocationAuthority {
  readonly [S2S_CURRENT_INVOCATION_AUTHORITY_BRAND]: true
}

interface S2SCurrentInvocationSnapshot {
  readonly evidence: S2SCurrentInvocationEvidence
  readonly eventBytes: Uint8Array
}

const S2S_CURRENT_INVOCATION_SNAPSHOTS = new WeakMap<
  object,
  S2SCurrentInvocationSnapshot
>()

const issueCurrentInvocationAuthority = (
  environment: unknown,
  eventBytes: unknown,
  capturedAtUnixSeconds: unknown
): Either.Either<
  S2SCurrentInvocationAuthority,
  S2SCurrentInvocationValidationError
> => {
  const evidence = validateS2SCurrentInvocation(
    environment,
    eventBytes,
    capturedAtUnixSeconds
  )
  if (Either.isLeft(evidence)) return Either.left(evidence.left)
  const eventSnapshot = snapshotEventBytes(eventBytes)
  if (Either.isLeft(eventSnapshot)) return Either.left(eventSnapshot.left)
  const authority: S2SCurrentInvocationAuthority = Object.freeze({
    [S2S_CURRENT_INVOCATION_AUTHORITY_BRAND]: true as const
  })
  S2S_CURRENT_INVOCATION_SNAPSHOTS.set(authority, {
    evidence: evidence.right,
    eventBytes: eventSnapshot.right
  })
  return Either.right(authority)
}

export const inspectS2SCurrentInvocationAuthority = (
  input: unknown
): Either.Either<
  S2SCurrentInvocationEvidence,
  S2SCurrentInvocationValidationError
> => {
  try {
    if (input === null || typeof input !== "object") {
      return Either.left(
        invocationError(
          "INVALID_INVOCATION_AUTHORITY",
          "$authority",
          "current invocation authority is not an issued object"
        )
      )
    }
    const snapshot = S2S_CURRENT_INVOCATION_SNAPSHOTS.get(input)
    return snapshot === undefined
      ? Either.left(
          invocationError(
            "INVALID_INVOCATION_AUTHORITY",
            "$authority",
            "current invocation authority was not issued by this module"
          )
        )
      : Either.right(snapshot.evidence)
  } catch {
    return Either.left(
      invocationError(
        "INVALID_INVOCATION_AUTHORITY",
        "$authority",
        "current invocation authority inspection failed closed"
      )
    )
  }
}

export const readS2SCurrentInvocationEventBytes = (
  input: unknown
): Either.Either<Uint8Array, S2SCurrentInvocationValidationError> => {
  try {
    if (input === null || typeof input !== "object") {
      return Either.left(
        invocationError(
          "INVALID_INVOCATION_AUTHORITY",
          "$authority",
          "current invocation authority is not an issued object"
        )
      )
    }
    const snapshot = S2S_CURRENT_INVOCATION_SNAPSHOTS.get(input)
    return snapshot === undefined
      ? Either.left(
          invocationError(
            "INVALID_INVOCATION_AUTHORITY",
            "$authority",
            "current invocation authority was not issued by this module"
          )
        )
      : Either.right(new Uint8Array(snapshot.eventBytes))
  } catch {
    return Either.left(
      invocationError(
        "INVALID_INVOCATION_AUTHORITY",
        "$authority",
        "current invocation event-byte inspection failed closed"
      )
    )
  }
}

export class S2SCurrentInvocation extends Context.Tag(
  "hswm/S2S/CurrentInvocation"
)<
  S2SCurrentInvocation,
  { readonly authority: S2SCurrentInvocationAuthority }
>() {}

const fromEither = <Success, Failure>(
  value: Either.Either<Success, Failure>
): Effect.Effect<Success, Failure> =>
  Either.isLeft(value) ? Effect.fail(value.left) : Effect.succeed(value.right)

export const makeS2SCurrentInvocationTestLayer = (
  environment: unknown,
  eventBytes: unknown,
  capturedAtUnixSeconds: unknown
) =>
  Layer.effect(
    S2SCurrentInvocation,
    fromEither(
      issueCurrentInvocationAuthority(
        environment,
        eventBytes,
        capturedAtUnixSeconds
      )
    ).pipe(
      Effect.map((authority) => S2SCurrentInvocation.of({ authority }))
    )
  )

const readBoundedEventFile = (
  path: string
): Effect.Effect<Uint8Array, S2SCurrentInvocationSourceError> =>
  Effect.tryPromise({
    try: async () => {
      let handle: Awaited<ReturnType<typeof open>>
      try {
        handle = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW)
      } catch {
        throw new S2SCurrentInvocationSourceError({
          reason: "EVENT_FILE_OPEN_FAILED",
          detail: "GitHub event file could not be opened without following links"
        })
      }
      try {
        const initialStat = await handle.stat()
        if (!initialStat.isFile()) {
          throw new S2SCurrentInvocationSourceError({
            reason: "EVENT_FILE_NOT_REGULAR",
            detail: "GitHub event source is not a regular file"
          })
        }
        if (
          !Number.isSafeInteger(initialStat.size) ||
          initialStat.size < 2 ||
          initialStat.size > S2S_CURRENT_INVOCATION_EVENT_MAX_BYTES
        ) {
          throw new S2SCurrentInvocationSourceError({
            reason: "EVENT_FILE_SIZE_REJECTED",
            detail: "GitHub event file size is outside the fixed bound"
          })
        }
        const output = new Uint8Array(
          S2S_CURRENT_INVOCATION_EVENT_MAX_BYTES + 1
        )
        let offset = 0
        while (offset < output.byteLength) {
          const read = await handle.read(
            output,
            offset,
            output.byteLength - offset,
            null
          )
          if (read.bytesRead === 0) break
          offset += read.bytesRead
        }
        if (offset < 2 || offset > S2S_CURRENT_INVOCATION_EVENT_MAX_BYTES) {
          throw new S2SCurrentInvocationSourceError({
            reason: "EVENT_FILE_SIZE_REJECTED",
            detail: "GitHub event bytes changed outside the fixed read bound"
          })
        }
        const finalStat = await handle.stat()
        if (
          offset !== initialStat.size ||
          finalStat.size !== initialStat.size ||
          finalStat.dev !== initialStat.dev ||
          finalStat.ino !== initialStat.ino ||
          finalStat.mode !== initialStat.mode ||
          finalStat.mtimeMs !== initialStat.mtimeMs ||
          finalStat.ctimeMs !== initialStat.ctimeMs
        ) {
          throw new S2SCurrentInvocationSourceError({
            reason: "EVENT_FILE_CHANGED",
            detail: "GitHub event file identity or bytes changed during capture"
          })
        }
        return output.slice(0, offset)
      } finally {
        await handle.close()
      }
    },
    catch: (error) =>
      error instanceof S2SCurrentInvocationSourceError
        ? error
        : new S2SCurrentInvocationSourceError({
            reason: "EVENT_FILE_READ_FAILED",
            detail: "GitHub event file read failed closed"
          })
  })

const selectedProcessEnvironment = (): Readonly<Record<string, unknown>> => {
  const output: Record<string, unknown> = Object.create(null)
  for (const key of S2S_CURRENT_INVOCATION_ENVIRONMENT_KEYS) {
    output[key] = process.env[key]
  }
  return Object.freeze(output)
}

export const S2SCurrentInvocationLive = Layer.effect(
  S2SCurrentInvocation,
  Effect.gen(function* () {
    const eventPath = process.env["GITHUB_EVENT_PATH"]
    if (
      typeof eventPath !== "string" ||
      eventPath.length < 1 ||
      eventPath.length > S2S_CURRENT_INVOCATION_EVENT_PATH_MAX_LENGTH ||
      eventPath.includes("\u0000") ||
      !isAbsolute(eventPath)
    ) {
      return yield* new S2SCurrentInvocationSourceError({
        reason: "EVENT_PATH_REJECTED",
        detail: "GITHUB_EVENT_PATH must be one bounded absolute path"
      })
    }
    const eventBytes = yield* readBoundedEventFile(eventPath)
    const capturedAtMillis = yield* Clock.currentTimeMillis
    const capturedAtUnixSeconds = Math.floor(capturedAtMillis / 1_000)
    const authority = yield* fromEither(
      issueCurrentInvocationAuthority(
        selectedProcessEnvironment(),
        eventBytes,
        capturedAtUnixSeconds
      )
    )
    return S2SCurrentInvocation.of({ authority })
  })
)
