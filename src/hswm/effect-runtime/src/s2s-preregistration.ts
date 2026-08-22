import { spawn } from "node:child_process"
import { createHash } from "node:crypto"
import { devNull } from "node:os"
import { resolve } from "node:path"
import { TextDecoder, TextEncoder } from "node:util"

import { Context, Data, Effect, Either, Layer, Schema } from "effect"

import {
  S2S_QUICKNET_CHAIN_HASH,
  S2S_QUICKNET_GENESIS_TIME,
  s2sQuicknetRoundTimeUnix
} from "./s2s-quicknet.js"
import { S2S_EXTERNAL_SEED_DOMAIN } from "./s2s-seed.js"
import {
  S2S_CONFIRMATORY_PREREGISTRATION_PATH,
  S2S_CONFIRMATORY_REF,
  S2S_CONFIRMATORY_REPOSITORY,
  S2S_CONFIRMATORY_WORKFLOW_PATH
} from "./s2s-workflow-contract.js"

export {
  S2S_QUICKNET_CHAIN_HASH,
  S2S_QUICKNET_GENESIS_TIME,
  S2S_QUICKNET_PERIOD_SECONDS
} from "./s2s-quicknet.js"

/**
 * Source-freeze and preregistration boundary for the SWM-0W-S2S gate.
 *
 * This module owns only the constitutional/evidence boundary (Pi): exact Git
 * object bytes, the disclosed-pilot numeric continuity check, and a noncyclic
 * future-round preregistration. It does not choose a future round, contact a
 * beacon or GitHub, or execute the Python numerical oracle.
 */

export const S2S_PREREG_PILOT_SOURCE_COMMIT =
  "75686549b1f6c65aea87ebd0f912a6e62909445a" as const

export const S2S_PREREG_PILOT_ADOPTION_RECEIPT_SHA256 =
  "97a752fea5ae45a311a2e8cf2376b391d76a8269dbab20f60688f543bcc5dea1" as const

export const S2S_PREREG_PROTOCOL_CONFIG_SHA256 =
  "a8f62d3811e42fbf3bc0dc82a52a17f3fa27b4dfa1d43aa9e7ea302a142c40bb" as const

/**
 * Raw SHA-256 of the sibling module's canonical float-free operational policy.
 * Kept as a literal to avoid a preregistration/control-state import cycle.
 */
export const S2S_PREREG_RESOURCE_POLICY_SHA256 =
  "b2c631ff80922800d06ac7e31c0632e02e1b560a31759cd0d11ae0a39c374351" as const

export const S2S_PREREG_REPOSITORY = S2S_CONFIRMATORY_REPOSITORY
export const S2S_PREREG_REF = S2S_CONFIRMATORY_REF
export const S2S_PREREGISTRATION_PATH =
  S2S_CONFIRMATORY_PREREGISTRATION_PATH
export const S2S_PREREGISTRATION_COMMIT_RULE = "DIRECT_CHILD_ADD_ONLY" as const
export const S2S_PREREG_CLAIM_SCOPE =
  "SYNTHETIC_SET_TO_SET_CANDIDATE_GATE_ONLY" as const

export const S2S_PREREG_NUMERIC_PATHS = Object.freeze([
  "pyproject.toml",
  "src/hswm/experiments/swm0w_s2s_worlds.py",
  "src/hswm/experiments/swm0w_s2s_family.py",
  "src/hswm/experiments/swm0w_s2s_operator.py",
  "src/hswm/experiments/swm0w_s2s_training.py",
  "src/hswm/experiments/swm0w_s2s_protocol.py",
  "src/hswm/experiments/swm0w_s2s_pilot.py",
  "uv.lock"
] as const)

export const S2S_TRACKED_BYTES_MANIFEST_SCHEMA_VERSION =
  "hswm-swm0w-s2s-tracked-bytes-manifest/v1" as const
export const S2S_NUMERIC_CONTINUITY_SCHEMA_VERSION =
  "hswm-swm0w-s2s-numeric-continuity/v1" as const
export const S2S_SOURCE_FREEZE_SCHEMA_VERSION =
  "hswm-swm0w-s2s-source-freeze/v1" as const
export const S2S_FUTURE_ROUND_COMMITMENT_SCHEMA_VERSION =
  "hswm-swm0w-s2s-drand-future-round-commitment/v1" as const
export const S2S_REGISTRATION_CORE_SCHEMA_VERSION =
  "hswm-swm0w-s2s-registration-core/v1" as const
export const S2S_PREREGISTRATION_SCHEMA_VERSION =
  "hswm-swm0w-s2s-preregistration/v1" as const
export const S2S_REGISTRATION_COMMIT_AUTHORITY_EVIDENCE_SCHEMA_VERSION =
  "hswm-swm0w-s2s-registration-commit-authority-evidence/v1" as const

export const S2S_PREREG_TASK_COUNT = 20 as const
export const S2S_PREREG_GIT_COMMAND_TIMEOUT_MILLIS = 120_000 as const
export const S2S_PREREG_ANCESTRY_MAX_COMMITS = 4_096 as const
export const S2S_PREREG_ANCESTRY_MAX_COMMIT_BYTES = 4 * 1_048_576
export const S2S_PREREG_ANCESTRY_MAX_PARENTS_PER_COMMIT = 64 as const
export const S2S_PREREG_ANCESTRY_MAX_TOTAL_BYTES = 64 * 1_048_576
export const S2S_PREREG_ANCESTRY_TIMEOUT_MILLIS = 120_000 as const

const MAX_PREREGISTRATION_BYTES = 4 * 1_048_576
const MAX_GIT_STDOUT_BYTES = 128 * 1_048_576
const MAX_GIT_STDERR_BYTES = 65_536
const PINNED_LINUX_GIT_EXECUTABLE = "/usr/bin/git"
/** Linux is the pinned execution target; devNull keeps config null portable. */
const GIT_PROCESS_ENVIRONMENT: NodeJS.ProcessEnv = Object.freeze({
  PATH: "/usr/bin:/bin",
  LANG: "C",
  LC_ALL: "C",
  GIT_CONFIG_NOSYSTEM: "1",
  GIT_CONFIG_GLOBAL: devNull,
  GIT_TERMINAL_PROMPT: "0"
})
const UTF8_ENCODER = new TextEncoder()
const UTF8_DECODER = new TextDecoder("utf-8", { fatal: true })
const ASCII_DECODER = new TextDecoder("ascii", { fatal: true })
const SHA256_PATTERN = /^[0-9a-f]{64}$/
const GIT_SHA_PATTERN = /^[0-9a-f]{40}$/
const EXPERIMENT_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/
const MODE_PATTERN = /^[0-7]{6}$/

export class S2SPreregCanonicalJsonError extends Data.TaggedError(
  "S2SPreregCanonicalJsonError"
)<{
  readonly reason:
    | "UNSUPPORTED_VALUE"
    | "NON_SAFE_INTEGER"
    | "INVALID_UNICODE"
    | "CYCLIC_VALUE"
  readonly path: string
}> {}

export class S2SPreregistrationValidationError extends Data.TaggedError(
  "S2SPreregistrationValidationError"
)<{
  readonly reason:
    | "INVALID_INPUT"
    | "INVALID_CANONICAL_JSON"
    | "SCHEMA_MISMATCH"
    | "HASH_MISMATCH"
    | "FIXED_BINDING_DRIFT"
    | "FUTURE_ROUND_INVALID"
    | "SOURCE_FREEZE_MISMATCH"
  readonly detail: string
}> {}

export class S2SSourceFreezeError extends Data.TaggedError(
  "S2SSourceFreezeError"
)<{
  readonly reason:
    | "INVALID_GIT_IDENTITY"
    | "PREREGISTRATION_PATH_PRESENT"
    | "UNSUPPORTED_GIT_ENTRY"
    | "MALFORMED_GIT_OUTPUT"
    | "MALFORMED_COMMIT_OBJECT"
    | "ANCESTRY_CYCLE"
    | "ANCESTRY_LIMIT_EXCEEDED"
    | "PILOT_NOT_ANCESTOR"
    | "NUMERIC_PATH_MISSING"
    | "NUMERIC_BYTES_DRIFT"
  readonly detail: string
}> {}

export class S2SRegistrationCommitError extends Data.TaggedError(
  "S2SRegistrationCommitError"
)<{
  readonly reason:
    | "INVALID_VALIDATION_SNAPSHOT"
    | "INVALID_REGISTRATION_AUTHORITY"
    | "INVALID_COMMIT"
    | "NOT_DIRECT_CHILD"
    | "DIFF_NOT_ADD_ONLY_PREREGISTRATION"
    | "PREREGISTRATION_ENTRY_INVALID"
    | "PREREGISTRATION_BYTES_DRIFT"
    | "AUTHORITY_EVIDENCE_NOT_CANONICAL"
    | "WORKFLOW_MANIFEST_BINDING_INVALID"
  readonly detail: string
}> {}

export class S2SGitRepositoryError extends Data.TaggedError(
  "S2SGitRepositoryError"
)<{
  readonly operation: string
  readonly reason:
    | "SPAWN_FAILED"
    | "OUTPUT_LIMIT_EXCEEDED"
    | "COMMAND_TIMED_OUT"
    | "COMMAND_FAILED"
  readonly exitCode: number | null
  readonly detail: string
}> {}

class S2SRawCommitObjectError extends Data.TaggedError(
  "S2SRawCommitObjectError"
)<{
  readonly reason: "INVALID_IDENTITY" | "MALFORMED" | "LIMIT_EXCEEDED"
  readonly detail: string
}> {}

type CanonicalJson =
  | null
  | boolean
  | string
  | number
  | ReadonlyArray<CanonicalJson>
  | { readonly [key: string]: CanonicalJson }

const hasValidUnicodeScalars = (value: string): boolean => {
  for (let index = 0; index < value.length; index += 1) {
    const unit = value.charCodeAt(index)
    if (unit >= 0xd800 && unit <= 0xdbff) {
      const next = value.charCodeAt(index + 1)
      if (!(next >= 0xdc00 && next <= 0xdfff)) return false
      index += 1
    } else if (unit >= 0xdc00 && unit <= 0xdfff) {
      return false
    }
  }
  return true
}

const compareUnicodeCodePoints = (left: string, right: string): number => {
  const toCodePoints = (value: string): ReadonlyArray<number> => {
    const points: Array<number> = []
    for (const scalar of value) {
      const point = scalar.codePointAt(0)
      if (point !== undefined) points.push(point)
    }
    return points
  }
  const leftPoints = toCodePoints(left)
  const rightPoints = toCodePoints(right)
  const length = Math.min(leftPoints.length, rightPoints.length)
  for (let index = 0; index < length; index += 1) {
    const leftPoint = leftPoints[index]
    const rightPoint = rightPoints[index]
    if (leftPoint === undefined || rightPoint === undefined) break
    if (leftPoint !== rightPoint) return leftPoint < rightPoint ? -1 : 1
  }
  return leftPoints.length < rightPoints.length
    ? -1
    : leftPoints.length > rightPoints.length
      ? 1
      : 0
}

const canonicalize = (
  value: unknown,
  path: string,
  ancestors: Set<object>
): Either.Either<CanonicalJson, S2SPreregCanonicalJsonError> => {
  if (value === null || typeof value === "boolean") return Either.right(value)
  if (typeof value === "string") {
    return hasValidUnicodeScalars(value)
      ? Either.right(value)
      : Either.left(new S2SPreregCanonicalJsonError({ reason: "INVALID_UNICODE", path }))
  }
  if (typeof value === "number") {
    return Number.isSafeInteger(value) && !Object.is(value, -0)
      ? Either.right(value)
      : Either.left(new S2SPreregCanonicalJsonError({ reason: "NON_SAFE_INTEGER", path }))
  }
  if (typeof value !== "object" || value === undefined) {
    return Either.left(new S2SPreregCanonicalJsonError({ reason: "UNSUPPORTED_VALUE", path }))
  }
  if (ancestors.has(value)) {
    return Either.left(new S2SPreregCanonicalJsonError({ reason: "CYCLIC_VALUE", path }))
  }
  ancestors.add(value)
  try {
    if (Array.isArray(value)) {
      const ownKeys = Reflect.ownKeys(value)
      const lengthDescriptor = Object.getOwnPropertyDescriptor(value, "length")
      const arrayLength: unknown =
        lengthDescriptor !== undefined && "value" in lengthDescriptor
          ? lengthDescriptor.value
          : undefined
      if (
        lengthDescriptor === undefined ||
        !("value" in lengthDescriptor) ||
        typeof arrayLength !== "number" ||
        !Number.isSafeInteger(arrayLength) ||
        arrayLength < 0 ||
        lengthDescriptor.enumerable !== false ||
        lengthDescriptor.configurable !== false ||
        ownKeys.some(
          (key) =>
            typeof key !== "string" ||
            (key !== "length" && !/^(0|[1-9][0-9]*)$/.test(key))
        ) ||
        ownKeys.length !== arrayLength + 1 ||
        Object.keys(value).length !== arrayLength
      ) {
        return Either.left(
          new S2SPreregCanonicalJsonError({ reason: "UNSUPPORTED_VALUE", path })
        )
      }
      const output: Array<CanonicalJson> = []
      for (let index = 0; index < arrayLength; index += 1) {
        const descriptor = Object.getOwnPropertyDescriptor(value, String(index))
        if (
          descriptor === undefined ||
          descriptor.enumerable !== true ||
          !("value" in descriptor)
        ) {
          return Either.left(
            new S2SPreregCanonicalJsonError({
              reason: "UNSUPPORTED_VALUE",
              path: `${path}[${index}]`
            })
          )
        }
        const item = canonicalize(
          descriptor.value,
          `${path}[${index}]`,
          ancestors
        )
        if (Either.isLeft(item)) return item
        output.push(item.right)
      }
      return Either.right(output)
    }
    const prototype = Object.getPrototypeOf(value)
    if (prototype !== Object.prototype && prototype !== null) {
      return Either.left(new S2SPreregCanonicalJsonError({ reason: "UNSUPPORTED_VALUE", path }))
    }
    const descriptors = Object.getOwnPropertyDescriptors(value)
    const keys = Reflect.ownKeys(value)
    const stringKeys: Array<string> = []
    for (const key of keys) {
      if (typeof key !== "string") {
        return Either.left(
          new S2SPreregCanonicalJsonError({ reason: "UNSUPPORTED_VALUE", path })
        )
      }
      const descriptor = descriptors[key]
      if (
        descriptor === undefined ||
        descriptor.enumerable !== true ||
        !("value" in descriptor) ||
        !hasValidUnicodeScalars(key)
      ) {
        return Either.left(
          new S2SPreregCanonicalJsonError({ reason: "UNSUPPORTED_VALUE", path })
        )
      }
      stringKeys.push(key)
    }
    const output: Record<string, CanonicalJson> = Object.create(null)
    for (const key of stringKeys.sort(compareUnicodeCodePoints)) {
      const descriptor = descriptors[key]
      if (descriptor === undefined || !("value" in descriptor)) {
        return Either.left(
          new S2SPreregCanonicalJsonError({ reason: "UNSUPPORTED_VALUE", path })
        )
      }
      const item = canonicalize(descriptor.value, `${path}.${key}`, ancestors)
      if (Either.isLeft(item)) return item
      output[key] = item.right
    }
    return Either.right(output)
  } catch {
    return Either.left(
      new S2SPreregCanonicalJsonError({ reason: "UNSUPPORTED_VALUE", path })
    )
  } finally {
    ancestors.delete(value)
  }
}

/**
 * Canonical UTF-8, float-free JSON for preregistration and Git-path receipts.
 * This is deliberately distinct from the ASCII-only Python numeric wire.
 */
export const s2sPreregCanonicalJson = (
  value: unknown
): Either.Either<string, S2SPreregCanonicalJsonError> => {
  const canonical = canonicalize(value, "$", new Set())
  if (Either.isLeft(canonical)) return Either.left(canonical.left)
  return Either.right(JSON.stringify(canonical.right))
}

export const s2sPreregCanonicalSha256 = (
  value: unknown
): Either.Either<string, S2SPreregCanonicalJsonError> =>
  Either.map(s2sPreregCanonicalJson(value), (encoded) =>
    createHash("sha256").update(encoded, "utf8").digest("hex")
  )

export const s2sPreregSha256Bytes = (value: Uint8Array): string =>
  createHash("sha256").update(value).digest("hex")

const canonicalBytesWithLf = (
  value: unknown
): Either.Either<Uint8Array, S2SPreregCanonicalJsonError> =>
  Either.map(s2sPreregCanonicalJson(value), (encoded) => UTF8_ENCODER.encode(`${encoded}\n`))

const canonicalDigestOrFail = (
  value: unknown
): Effect.Effect<string, S2SPreregCanonicalJsonError> =>
  effectFromEither(s2sPreregCanonicalSha256(value))

const effectFromEither = <A, E>(
  value: Either.Either<A, E>
): Effect.Effect<A, E> =>
  Either.match(value, {
    onLeft: (error) => Effect.fail(error),
    onRight: (result) => Effect.succeed(result)
  })

const Sha256Schema = Schema.String.pipe(Schema.pattern(SHA256_PATTERN))
const GitShaSchema = Schema.String.pipe(Schema.pattern(GIT_SHA_PATTERN))
const SafeIntegerSchema = Schema.Number.pipe(
  Schema.int(),
  Schema.between(0, Number.MAX_SAFE_INTEGER)
)
const PositiveSafeIntegerSchema = Schema.Number.pipe(
  Schema.int(),
  Schema.between(1, Number.MAX_SAFE_INTEGER)
)
const ExperimentIdSchema = Schema.String.pipe(Schema.pattern(EXPERIMENT_ID_PATTERN))
const ModeSchema = Schema.String.pipe(Schema.pattern(MODE_PATTERN))

const TrackedBytesRowSchema = Schema.Struct({
  mode: ModeSchema,
  object_type: Schema.Union(Schema.Literal("blob"), Schema.Literal("commit")),
  path: Schema.String,
  sha256: Sha256Schema
})

const TrackedBytesManifestSchema = Schema.Struct({
  schema_version: Schema.Literal(S2S_TRACKED_BYTES_MANIFEST_SCHEMA_VERSION),
  commit: GitShaSchema,
  tree_oid: GitShaSchema,
  rows: Schema.Array(TrackedBytesRowSchema).pipe(Schema.minItems(1)),
  manifest_sha256: Sha256Schema
})

const NumericContinuityRowSchema = Schema.Struct({
  path: Schema.String,
  pilot_sha256: Sha256Schema,
  source_sha256: Sha256Schema
})

const NumericContinuitySchema = Schema.Struct({
  schema_version: Schema.Literal(S2S_NUMERIC_CONTINUITY_SCHEMA_VERSION),
  pilot_source_commit_p: Schema.Literal(S2S_PREREG_PILOT_SOURCE_COMMIT),
  source_commit_a: GitShaSchema,
  paths: Schema.Tuple(
    Schema.Literal("pyproject.toml"),
    Schema.Literal("src/hswm/experiments/swm0w_s2s_worlds.py"),
    Schema.Literal("src/hswm/experiments/swm0w_s2s_family.py"),
    Schema.Literal("src/hswm/experiments/swm0w_s2s_operator.py"),
    Schema.Literal("src/hswm/experiments/swm0w_s2s_training.py"),
    Schema.Literal("src/hswm/experiments/swm0w_s2s_protocol.py"),
    Schema.Literal("src/hswm/experiments/swm0w_s2s_pilot.py"),
    Schema.Literal("uv.lock")
  ),
  rows: Schema.Array(NumericContinuityRowSchema),
  pilot_is_ancestor_of_source: Schema.Literal(true),
  byte_equal: Schema.Literal(true),
  receipt_sha256: Sha256Schema
})

const SourceFreezeSchema = Schema.Struct({
  schema_version: Schema.Literal(S2S_SOURCE_FREEZE_SCHEMA_VERSION),
  tracked_bytes_manifest: TrackedBytesManifestSchema,
  numeric_continuity: NumericContinuitySchema,
  receipt_sha256: Sha256Schema
})

const FutureRoundCommitmentSchema = Schema.Struct({
  schema_version: Schema.Literal(S2S_FUTURE_ROUND_COMMITMENT_SCHEMA_VERSION),
  experiment_id: ExperimentIdSchema,
  registration_evidence_sha256: Sha256Schema,
  registered_at_unix: SafeIntegerSchema,
  chain_hash: Schema.Literal(S2S_QUICKNET_CHAIN_HASH),
  round: PositiveSafeIntegerSchema,
  round_time_unix: SafeIntegerSchema,
  task_count: Schema.Literal(S2S_PREREG_TASK_COUNT),
  seed_domain: Schema.Literal(S2S_EXTERNAL_SEED_DOMAIN),
  chronology_claim_allowed: Schema.Literal(false),
  commitment_sha256: Sha256Schema
})

const RegistrationCoreSchema = Schema.Struct({
  schema_version: Schema.Literal(S2S_REGISTRATION_CORE_SCHEMA_VERSION),
  experiment_id: ExperimentIdSchema,
  claim_scope: Schema.Literal(S2S_PREREG_CLAIM_SCOPE),
  repository_binding: Schema.Struct({
    repository: Schema.Literal(S2S_PREREG_REPOSITORY),
    ref: Schema.Literal(S2S_PREREG_REF),
    source_commit_a: GitShaSchema,
    preregistration_path: Schema.Literal(S2S_PREREGISTRATION_PATH),
    registration_commit_rule: Schema.Literal(S2S_PREREGISTRATION_COMMIT_RULE)
  }),
  evidence_binding: Schema.Struct({
    pilot_adoption_receipt_sha256: Schema.Literal(
      S2S_PREREG_PILOT_ADOPTION_RECEIPT_SHA256
    ),
    protocol_config_sha256: Schema.Literal(S2S_PREREG_PROTOCOL_CONFIG_SHA256),
    resource_policy_sha256: Schema.Literal(S2S_PREREG_RESOURCE_POLICY_SHA256)
  }),
  execution_binding: Schema.Struct({
    task_count: Schema.Literal(S2S_PREREG_TASK_COUNT),
    external_seed_count: Schema.Literal(1),
    workflow_run_attempt: Schema.Literal(1),
    rerun_allowed: Schema.Literal(false),
    reroll_allowed: Schema.Literal(false),
    post_pulse_resume_allowed: Schema.Literal(false),
    task_skip_allowed: Schema.Literal(false),
    partial_candidate_allowed: Schema.Literal(false)
  }),
  source_freeze: SourceFreezeSchema
})

const PreregistrationSchema = Schema.Struct({
  schema_version: Schema.Literal(S2S_PREREGISTRATION_SCHEMA_VERSION),
  registration_core: RegistrationCoreSchema,
  registration_core_sha256: Sha256Schema,
  future_round_commitment: FutureRoundCommitmentSchema,
  preregistration_sha256: Sha256Schema
})

const BuildPreregistrationInputSchema = Schema.Struct({
  experimentId: ExperimentIdSchema,
  resourcePolicySha256: Schema.Literal(S2S_PREREG_RESOURCE_POLICY_SHA256),
  sourceCommitA: GitShaSchema,
  registeredAtUnix: SafeIntegerSchema,
  futureRound: PositiveSafeIntegerSchema
})

export type S2STrackedBytesManifest = Schema.Schema.Type<
  typeof TrackedBytesManifestSchema
>
export type S2SNumericContinuity = Schema.Schema.Type<
  typeof NumericContinuitySchema
>
export type S2SSourceFreeze = Schema.Schema.Type<typeof SourceFreezeSchema>
export type S2SFutureRoundCommitment = Schema.Schema.Type<
  typeof FutureRoundCommitmentSchema
>
export type S2SRegistrationCore = Schema.Schema.Type<typeof RegistrationCoreSchema>
export type S2SPreregistration = Schema.Schema.Type<typeof PreregistrationSchema>
export type BuildS2SPreregistrationInput = Schema.Schema.Type<
  typeof BuildPreregistrationInputSchema
>

export interface S2SGitCommand {
  readonly operation: string
  readonly arguments: ReadonlyArray<string>
  readonly stdin: Uint8Array | null
}

export interface S2SGitCommandResult {
  readonly exitCode: number
  readonly stdout: Uint8Array
  readonly stderr: Uint8Array
}

/** @internal Not exported from the package index. */
export class S2SPreregGitRepository extends Context.Tag(
  "hswm/S2SPreregGitRepository"
)<
  S2SPreregGitRepository,
  {
    readonly execute: (
      command: S2SGitCommand
    ) => Effect.Effect<S2SGitCommandResult, S2SGitRepositoryError>
  }
>() {}

const collectGitProcess = (
  repoRoot: string,
  command: S2SGitCommand
): Effect.Effect<S2SGitCommandResult, S2SGitRepositoryError> =>
  Effect.async<S2SGitCommandResult, S2SGitRepositoryError>((resume) => {
    let settled = false
    let stdoutSize = 0
    let stderrSize = 0
    const stdout: Array<Buffer> = []
    const stderr: Array<Buffer> = []
    const child = spawn(
      PINNED_LINUX_GIT_EXECUTABLE,
      ["-C", repoRoot, ...command.arguments],
      {
        env: GIT_PROCESS_ENVIRONMENT,
        shell: false,
        stdio: ["pipe", "pipe", "pipe"]
      }
    )

    const finish = (
      effect: Effect.Effect<S2SGitCommandResult, S2SGitRepositoryError>
    ): void => {
      if (settled) return
      settled = true
      resume(effect)
    }
    child.once("error", (error) =>
      finish(
        Effect.fail(
          new S2SGitRepositoryError({
            operation: command.operation,
            reason: "SPAWN_FAILED",
            exitCode: null,
            detail: String(error.message).slice(-500)
          })
        )
      )
    )
    child.stdout.on("data", (chunk: Buffer) => {
      stdoutSize += chunk.length
      if (stdoutSize > MAX_GIT_STDOUT_BYTES) {
        child.kill("SIGTERM")
        finish(
          Effect.fail(
            new S2SGitRepositoryError({
              operation: command.operation,
              reason: "OUTPUT_LIMIT_EXCEEDED",
              exitCode: null,
              detail: "Git stdout exceeded the fixed bound"
            })
          )
        )
      } else {
        stdout.push(Buffer.from(chunk))
      }
    })
    child.stderr.on("data", (chunk: Buffer) => {
      stderrSize += chunk.length
      if (stderrSize <= MAX_GIT_STDERR_BYTES) stderr.push(Buffer.from(chunk))
    })
    // A command may reject stdin before the parent finishes writing it. Its
    // close status remains the authoritative result; suppress the stream's
    // otherwise-unhandled EPIPE while preserving that status.
    child.stdin.on("error", () => undefined)
    child.once("close", (code) => {
      const exitCode = code ?? 1
      finish(
        Effect.succeed({
          exitCode,
          stdout: new Uint8Array(Buffer.concat(stdout)),
          stderr: new Uint8Array(Buffer.concat(stderr))
        })
      )
    })
    if (command.stdin === null) {
      child.stdin.end()
    } else {
      child.stdin.end(Buffer.from(command.stdin))
    }
    return Effect.sync(() => {
      if (!settled) child.kill("SIGTERM")
    })
  })

export const makeS2SPreregGitRepositoryProcessLayer = (repoRoot: string) => {
  const root = resolve(repoRoot)
  return Layer.succeed(
    S2SPreregGitRepository,
    S2SPreregGitRepository.of({
      execute: (command) => collectGitProcess(root, command)
    })
  )
}

export const makeS2SPreregGitRepositoryTestLayer = (
  execute: (
    command: S2SGitCommand
  ) => Effect.Effect<S2SGitCommandResult, S2SGitRepositoryError>
) =>
  Layer.succeed(
    S2SPreregGitRepository,
    S2SPreregGitRepository.of({ execute })
  )

const decodeUtf8 = (
  value: Uint8Array,
  detail: string
): Effect.Effect<string, S2SSourceFreezeError> =>
  Effect.try({
    try: () => UTF8_DECODER.decode(value),
    catch: () =>
      new S2SSourceFreezeError({
        reason: "MALFORMED_GIT_OUTPUT",
        detail
      })
  })

const decodeAscii = (
  value: Uint8Array,
  detail: string
): Effect.Effect<string, S2SSourceFreezeError> =>
  Effect.try({
    try: () => ASCII_DECODER.decode(value),
    catch: () =>
      new S2SSourceFreezeError({
        reason: "MALFORMED_GIT_OUTPUT",
        detail
      })
  })

const runGit = (
  operation: string,
  args: ReadonlyArray<string>,
  stdin: Uint8Array | null = null,
  allowedExitCodes: ReadonlyArray<number> = [0]
): Effect.Effect<S2SGitCommandResult, S2SGitRepositoryError, S2SPreregGitRepository> =>
  Effect.gen(function* () {
    const repository = yield* S2SPreregGitRepository
    const result = yield* repository
      .execute({
        operation,
        arguments: Object.freeze(["--no-replace-objects", ...args]),
        stdin
      })
      .pipe(
        Effect.timeoutFail({
          duration: S2S_PREREG_GIT_COMMAND_TIMEOUT_MILLIS,
          onTimeout: () =>
            new S2SGitRepositoryError({
              operation,
              reason: "COMMAND_TIMED_OUT",
              exitCode: null,
              detail: "Git command exceeded the fixed 120-second deadline"
            })
        })
      )
    if (!allowedExitCodes.includes(result.exitCode)) {
      let detail = "Git command failed"
      try {
        detail = UTF8_DECODER.decode(result.stderr).trim().slice(-500) || detail
      } catch {
        // Keep a fixed detail for malformed stderr.
      }
      return yield* new S2SGitRepositoryError({
        operation,
        reason: "COMMAND_FAILED",
        exitCode: result.exitCode,
        detail
      })
    }
    return result
  })

const isGitSha = (value: unknown): value is string =>
  typeof value === "string" && GIT_SHA_PATTERN.test(value)

const assertExactSourceCommitObject = (
  sourceCommitA: string
): Effect.Effect<
  void,
  S2SGitRepositoryError | S2SSourceFreezeError,
  S2SPreregGitRepository
> =>
  Effect.gen(function* () {
    if (!isGitSha(sourceCommitA)) {
      return yield* new S2SSourceFreezeError({
        reason: "INVALID_GIT_IDENTITY",
        detail: "source commit A must be a lowercase 40-hex Git SHA"
      })
    }
    const result = yield* runGit("verify source commit object type", [
      "cat-file",
      "-t",
      sourceCommitA
    ])
    const objectType = yield* decodeAscii(
      result.stdout,
      "source A Git object type"
    )
    if (objectType === "commit\n") return
    const knownNonCommit =
      objectType === "tag\n" || objectType === "tree\n" || objectType === "blob\n"
    return yield* new S2SSourceFreezeError({
      reason: knownNonCommit ? "INVALID_GIT_IDENTITY" : "MALFORMED_GIT_OUTPUT",
      detail: knownNonCommit
        ? "source A must name an exact commit object, not a peeled or tag object"
        : "source A Git object type output is malformed"
    })
  })

const assertPreregistrationPathAbsentAtSource = (
  sourceCommitA: string
): Effect.Effect<
  void,
  S2SGitRepositoryError | S2SSourceFreezeError,
  S2SPreregGitRepository
> =>
  Effect.gen(function* () {
    const result = yield* runGit("verify preregistration path absence at source A", [
      "ls-tree",
      "--name-only",
      "-z",
      "--full-tree",
      sourceCommitA,
      "--",
      S2S_PREREGISTRATION_PATH
    ])
    if (result.stdout.length === 0) return
    const expected = UTF8_ENCODER.encode(`${S2S_PREREGISTRATION_PATH}\0`)
    if (
      result.stdout.length !== expected.length ||
      !result.stdout.every((value, index) => value === expected[index])
    ) {
      return yield* new S2SSourceFreezeError({
        reason: "MALFORMED_GIT_OUTPUT",
        detail: "preregistration path absence query returned unexpected bytes"
      })
    }
    return yield* new S2SSourceFreezeError({
      reason: "PREREGISTRATION_PATH_PRESENT",
      detail: "source A already tracks the preregistration path"
    })
  })

interface GitTreeEntry {
  readonly mode: string
  readonly objectType: "blob" | "commit"
  readonly path: string
  readonly oid: string
}

const splitAtNul = (value: Uint8Array): ReadonlyArray<Uint8Array> => {
  const output: Array<Uint8Array> = []
  let start = 0
  for (let index = 0; index < value.length; index += 1) {
    if (value[index] === 0) {
      output.push(value.slice(start, index))
      start = index + 1
    }
  }
  output.push(value.slice(start))
  return output
}

const parseTreeEntries = (
  value: Uint8Array
): Effect.Effect<ReadonlyArray<GitTreeEntry>, S2SSourceFreezeError> =>
  Effect.gen(function* () {
    const entries: Array<GitTreeEntry> = []
    const records = splitAtNul(value)
    for (let index = 0; index < records.length; index += 1) {
      const record = records[index]
      if (record === undefined) {
        return yield* new S2SSourceFreezeError({
          reason: "MALFORMED_GIT_OUTPUT",
          detail: "Git tree record indexing drifted"
        })
      }
      if (record.length === 0) {
        if (index !== records.length - 1) {
          return yield* new S2SSourceFreezeError({
            reason: "MALFORMED_GIT_OUTPUT",
            detail: "Git tree contains an empty entry"
          })
        }
        continue
      }
      const tab = record.indexOf(9)
      if (tab <= 0 || tab === record.length - 1) {
        return yield* new S2SSourceFreezeError({
          reason: "MALFORMED_GIT_OUTPUT",
          detail: "Git tree entry lacks metadata or path"
        })
      }
      const metadata = yield* decodeAscii(record.slice(0, tab), "Git tree metadata")
      const path = yield* decodeUtf8(record.slice(tab + 1), "Git tree path")
      const parts = metadata.split(" ")
      const mode = parts[0]
      const rawObjectType = parts[1]
      const oid = parts[2]
      const objectType =
        rawObjectType === "blob"
          ? "blob"
          : rawObjectType === "commit"
            ? "commit"
            : null
      if (
        parts.length !== 3 ||
        mode === undefined ||
        !MODE_PATTERN.test(mode) ||
        objectType === null ||
        oid === undefined ||
        !GIT_SHA_PATTERN.test(oid) ||
        path.length === 0 ||
        path.includes("\0")
      ) {
        return yield* new S2SSourceFreezeError({
          reason: "UNSUPPORTED_GIT_ENTRY",
          detail: `unsupported Git tree entry at ${path || "<empty>"}`
        })
      }
      entries.push({
        mode,
        objectType,
        path,
        oid
      })
    }
    return entries
  })

const parseCatFileBatch = (
  value: Uint8Array,
  expectedOids: ReadonlyArray<string>
): Effect.Effect<ReadonlyMap<string, Uint8Array>, S2SSourceFreezeError> =>
  Effect.gen(function* () {
    const bytes = Buffer.from(value)
    let cursor = 0
    const output = new Map<string, Uint8Array>()
    for (const expectedOid of expectedOids) {
      const newline = bytes.indexOf(10, cursor)
      if (newline < 0) {
        return yield* new S2SSourceFreezeError({
          reason: "MALFORMED_GIT_OUTPUT",
          detail: "Git cat-file batch header is truncated"
        })
      }
      const header = yield* decodeAscii(
        bytes.subarray(cursor, newline),
        "Git cat-file header"
      )
      const parts = header.split(" ")
      const size = parts.length === 3 ? Number(parts[2]) : Number.NaN
      if (
        parts.length !== 3 ||
        parts[0] !== expectedOid ||
        parts[1] !== "blob" ||
        !Number.isSafeInteger(size) ||
        size < 0
      ) {
        return yield* new S2SSourceFreezeError({
          reason: "MALFORMED_GIT_OUTPUT",
          detail: "Git cat-file batch identity/type/size drifted"
        })
      }
      const start = newline + 1
      const end = start + size
      if (end >= bytes.length || bytes[end] !== 10) {
        return yield* new S2SSourceFreezeError({
          reason: "MALFORMED_GIT_OUTPUT",
          detail: "Git cat-file batch payload is truncated"
        })
      }
      output.set(expectedOid, new Uint8Array(bytes.subarray(start, end)))
      cursor = end + 1
    }
    if (cursor !== bytes.length) {
      return yield* new S2SSourceFreezeError({
        reason: "MALFORMED_GIT_OUTPUT",
        detail: "Git cat-file batch has trailing bytes"
      })
    }
    return output
  })

interface RawCommitObject {
  readonly parents: ReadonlyArray<string>
  readonly byteLength: number
}

interface AncestryFrame {
  readonly oid: string
  parents: ReadonlyArray<string> | null
  nextParentIndex: number
}

const strictAscii = (value: Uint8Array): string | null => {
  let output = ""
  for (const byte of value) {
    if (byte > 0x7f) return null
    output += String.fromCharCode(byte)
  }
  return output
}

const hasAsciiPrefix = (value: Uint8Array, prefix: string): boolean => {
  if (value.length < prefix.length) return false
  for (let index = 0; index < prefix.length; index += 1) {
    if (value[index] !== prefix.charCodeAt(index)) return false
  }
  return true
}

const parseCommitOidHeader = (
  line: Uint8Array,
  keyword: "tree" | "parent"
): string | null => {
  const prefix = `${keyword} `
  if (line.length !== prefix.length + 40 || !hasAsciiPrefix(line, prefix)) {
    return null
  }
  const oid = strictAscii(line.slice(prefix.length))
  return oid !== null && isGitSha(oid) ? oid : null
}

const splitRawCommitHeader = (
  payload: Uint8Array
): ReadonlyArray<Uint8Array> | null => {
  let headerEnd = -1
  for (let index = 0; index + 1 < payload.length; index += 1) {
    if (payload[index] === 10 && payload[index + 1] === 10) {
      headerEnd = index
      break
    }
  }
  if (headerEnd <= 0) return null
  const lines: Array<Uint8Array> = []
  let start = 0
  for (let index = 0; index <= headerEnd; index += 1) {
    if (index === headerEnd || payload[index] === 10) {
      if (index === start) return null
      lines.push(payload.slice(start, index))
      start = index + 1
    }
  }
  return lines
}

const hasForbiddenCommitHeaderByte = (line: Uint8Array): boolean =>
  line.some((byte) => byte === 0 || byte === 13)

const isAdditionalCommitHeader = (line: Uint8Array): boolean => {
  const separator = line.indexOf(32)
  if (separator <= 0 || separator === line.length - 1) return false
  const key = strictAscii(line.slice(0, separator))
  if (
    key === null ||
    !/^[a-z][a-z0-9-]*$/.test(key) ||
    key === "tree" ||
    key === "parent" ||
    key === "author" ||
    key === "committer"
  ) {
    return false
  }
  return true
}

const parseRawCommitPayload = (
  payload: Uint8Array
): Either.Either<RawCommitObject, S2SRawCommitObjectError> => {
  const lines = splitRawCommitHeader(payload)
  if (lines === null || lines.length < 3) {
    return Either.left(
      new S2SRawCommitObjectError({
        reason: "MALFORMED",
        detail: "raw commit lacks the required header/message boundary"
      })
    )
  }
  if (lines.some(hasForbiddenCommitHeaderByte)) {
    return Either.left(
      new S2SRawCommitObjectError({
        reason: "MALFORMED",
        detail: "raw commit header contains a forbidden byte"
      })
    )
  }
  const treeLine = lines[0]
  if (treeLine === undefined || parseCommitOidHeader(treeLine, "tree") === null) {
    return Either.left(
      new S2SRawCommitObjectError({
        reason: "MALFORMED",
        detail: "raw commit must begin with one exact tree header"
      })
    )
  }

  const parents: Array<string> = []
  const uniqueParents = new Set<string>()
  let index = 1
  while (index < lines.length) {
    const line = lines[index]
    if (line === undefined || !hasAsciiPrefix(line, "parent ")) break
    const parent = parseCommitOidHeader(line, "parent")
    if (parent === null || uniqueParents.has(parent)) {
      return Either.left(
        new S2SRawCommitObjectError({
          reason: "MALFORMED",
          detail: "raw commit parent headers are malformed or duplicated"
        })
      )
    }
    if (parents.length >= S2S_PREREG_ANCESTRY_MAX_PARENTS_PER_COMMIT) {
      return Either.left(
        new S2SRawCommitObjectError({
          reason: "LIMIT_EXCEEDED",
          detail: "raw commit parent count exceeds the fixed bound"
        })
      )
    }
    uniqueParents.add(parent)
    parents.push(parent)
    index += 1
  }

  const authorLine = lines[index]
  const committerLine = lines[index + 1]
  if (
    authorLine === undefined ||
    !hasAsciiPrefix(authorLine, "author ") ||
    authorLine.length <= "author ".length ||
    committerLine === undefined ||
    !hasAsciiPrefix(committerLine, "committer ") ||
    committerLine.length <= "committer ".length
  ) {
    return Either.left(
      new S2SRawCommitObjectError({
        reason: "MALFORMED",
        detail: "raw commit author/committer headers are absent or out of order"
      })
    )
  }
  index += 2
  let continuationAllowed = false
  for (; index < lines.length; index += 1) {
    const line = lines[index]
    if (line === undefined) {
      return Either.left(
        new S2SRawCommitObjectError({
          reason: "MALFORMED",
          detail: "raw commit header indexing drifted"
        })
      )
    }
    if (line[0] === 32) {
      if (!continuationAllowed) {
        return Either.left(
          new S2SRawCommitObjectError({
            reason: "MALFORMED",
            detail: "raw commit has an orphan continuation header"
          })
        )
      }
      continue
    }
    if (!isAdditionalCommitHeader(line)) {
      return Either.left(
        new S2SRawCommitObjectError({
          reason: "MALFORMED",
          detail: "raw commit has a duplicate, late, or malformed header"
        })
      )
    }
    continuationAllowed = true
  }
  return Either.right({ parents, byteLength: payload.length })
}

const parseSingleRawCommitBatch = (
  value: Uint8Array,
  expectedOid: string
): Either.Either<RawCommitObject, S2SRawCommitObjectError> => {
  const newline = value.indexOf(10)
  if (newline <= 0) {
    return Either.left(
      new S2SRawCommitObjectError({
        reason: "MALFORMED",
        detail: "raw commit batch header is truncated"
      })
    )
  }
  const header = strictAscii(value.slice(0, newline))
  const parts = header === null ? [] : header.split(" ")
  const sizeText = parts[2]
  const size =
    sizeText !== undefined && /^(0|[1-9][0-9]*)$/.test(sizeText)
      ? Number(sizeText)
      : Number.NaN
  if (
    parts.length !== 3 ||
    parts[0] !== expectedOid ||
    parts[1] !== "commit" ||
    !Number.isSafeInteger(size) ||
    size < 0
  ) {
    return Either.left(
      new S2SRawCommitObjectError({
        reason:
          parts.length === 3 && parts[0] === expectedOid && parts[1] !== "commit"
            ? "INVALID_IDENTITY"
            : "MALFORMED",
        detail: "raw commit batch identity/type/size drifted"
      })
    )
  }
  if (size > S2S_PREREG_ANCESTRY_MAX_COMMIT_BYTES) {
    return Either.left(
      new S2SRawCommitObjectError({
        reason: "LIMIT_EXCEEDED",
        detail: "raw commit bytes exceed the fixed per-commit bound"
      })
    )
  }
  const start = newline + 1
  const end = start + size
  if (end + 1 !== value.length || value[end] !== 10) {
    return Either.left(
      new S2SRawCommitObjectError({
        reason: "MALFORMED",
        detail: "raw commit batch payload is truncated or has trailing bytes"
      })
    )
  }
  return parseRawCommitPayload(value.slice(start, end))
}

const readRawCommitObject = (
  oid: string,
  operation: string
): Effect.Effect<
  RawCommitObject,
  S2SGitRepositoryError | S2SRawCommitObjectError,
  S2SPreregGitRepository
> =>
  Effect.gen(function* () {
    if (!isGitSha(oid)) {
      return yield* new S2SRawCommitObjectError({
        reason: "INVALID_IDENTITY",
        detail: "raw commit OID must be a lowercase 40-hex Git SHA"
      })
    }
    const result = yield* runGit(
      operation,
      ["cat-file", "--batch"],
      UTF8_ENCODER.encode(`${oid}\n`)
    )
    return yield* effectFromEither(parseSingleRawCommitBatch(result.stdout, oid))
  })

const sourceRawCommitFailure = (
  error: S2SRawCommitObjectError
): S2SSourceFreezeError =>
  new S2SSourceFreezeError({
    reason:
      error.reason === "LIMIT_EXCEEDED"
        ? "ANCESTRY_LIMIT_EXCEEDED"
        : "MALFORMED_COMMIT_OBJECT",
    detail: error.detail
  })

const assertPilotIsRawAncestor = (
  sourceCommitA: string
): Effect.Effect<
  void,
  S2SGitRepositoryError | S2SSourceFreezeError,
  S2SPreregGitRepository
> => {
  const traversal = Effect.gen(function* () {
    const active = new Set<string>([sourceCommitA])
    const completed = new Set<string>()
    const stack: Array<AncestryFrame> = [
      { oid: sourceCommitA, parents: null, nextParentIndex: 0 }
    ]
    let uniqueCommits = 0
    let totalBytes = 0

    while (stack.length > 0) {
      const frame = stack[stack.length - 1]
      if (frame === undefined) break
      if (frame.parents === null) {
        if (uniqueCommits >= S2S_PREREG_ANCESTRY_MAX_COMMITS) {
          return yield* new S2SSourceFreezeError({
            reason: "ANCESTRY_LIMIT_EXCEEDED",
            detail: "raw ancestry unique-commit count exceeds the fixed bound"
          })
        }
        const raw = yield* readRawCommitObject(
          frame.oid,
          `read raw ancestry commit ${frame.oid}`
        ).pipe(
          Effect.catchTag("S2SRawCommitObjectError", (error) =>
            Effect.fail(sourceRawCommitFailure(error))
          )
        )
        uniqueCommits += 1
        totalBytes += raw.byteLength
        if (totalBytes > S2S_PREREG_ANCESTRY_MAX_TOTAL_BYTES) {
          return yield* new S2SSourceFreezeError({
            reason: "ANCESTRY_LIMIT_EXCEEDED",
            detail: "raw ancestry total bytes exceed the fixed bound"
          })
        }
        frame.parents = raw.parents
        if (frame.oid === S2S_PREREG_PILOT_SOURCE_COMMIT) return
      }

      const parent = frame.parents[frame.nextParentIndex]
      if (parent === undefined) {
        active.delete(frame.oid)
        completed.add(frame.oid)
        stack.pop()
        continue
      }
      frame.nextParentIndex += 1
      if (active.has(parent)) {
        return yield* new S2SSourceFreezeError({
          reason: "ANCESTRY_CYCLE",
          detail: "raw ancestry contains a parent cycle"
        })
      }
      if (completed.has(parent)) continue
      active.add(parent)
      stack.push({ oid: parent, parents: null, nextParentIndex: 0 })
    }

    return yield* new S2SSourceFreezeError({
      reason: "PILOT_NOT_ANCESTOR",
      detail: "the disclosed pilot source P is not a raw parent ancestor of source A"
    })
  })
  return traversal.pipe(
    Effect.timeoutFail({
      duration: S2S_PREREG_ANCESTRY_TIMEOUT_MILLIS,
      onTimeout: () =>
        new S2SSourceFreezeError({
          reason: "ANCESTRY_LIMIT_EXCEEDED",
          detail: "raw ancestry traversal exceeded the fixed total deadline"
        })
    })
  )
}

const buildS2STrackedBytesManifestUnchecked = (
  sourceCommitA: string
): Effect.Effect<
  S2STrackedBytesManifest,
  S2SGitRepositoryError | S2SSourceFreezeError | S2SPreregCanonicalJsonError,
  S2SPreregGitRepository
> =>
  Effect.gen(function* () {
    const treeResult = yield* runGit("resolve source tree", [
      "rev-parse",
      `${sourceCommitA}^{tree}`
    ])
    const treeOid = (yield* decodeAscii(treeResult.stdout, "source tree OID")).trim()
    if (!isGitSha(treeOid)) {
      return yield* new S2SSourceFreezeError({
        reason: "MALFORMED_GIT_OUTPUT",
        detail: "source tree OID is malformed"
      })
    }
    const listing = yield* runGit("list source tree", [
      "ls-tree",
      "-r",
      "-z",
      "--full-tree",
      sourceCommitA
    ])
    const entries = yield* parseTreeEntries(listing.stdout)
    if (entries.some((entry) => entry.path === S2S_PREREGISTRATION_PATH)) {
      return yield* new S2SSourceFreezeError({
        reason: "PREREGISTRATION_PATH_PRESENT",
        detail: "source A already tracks the preregistration path"
      })
    }
    if (entries.length === 0) {
      return yield* new S2SSourceFreezeError({
        reason: "MALFORMED_GIT_OUTPUT",
        detail: "source tree is empty"
      })
    }
    const blobOids = entries
      .filter((entry) => entry.objectType === "blob")
      .map((entry) => entry.oid)
    const blobBytes =
      blobOids.length === 0
        ? new Map<string, Uint8Array>()
        : yield* Effect.gen(function* () {
            const batchInput = UTF8_ENCODER.encode(`${blobOids.join("\n")}\n`)
            const batch = yield* runGit(
              "read source blobs",
              ["cat-file", "--batch"],
              batchInput
            )
            return yield* parseCatFileBatch(batch.stdout, blobOids)
          })
    const unsortedRows = yield* Effect.forEach(entries, (entry) =>
      Effect.gen(function* () {
        const payload =
          entry.objectType === "blob"
            ? blobBytes.get(entry.oid)
            : UTF8_ENCODER.encode(entry.oid)
        if (payload === undefined) {
          return yield* new S2SSourceFreezeError({
            reason: "MALFORMED_GIT_OUTPUT",
            detail: `missing Git object bytes for ${entry.path}`
          })
        }
        return {
          mode: entry.mode,
          object_type: entry.objectType,
          path: entry.path,
          sha256: s2sPreregSha256Bytes(payload)
        } as const
      })
    )
    const rows = unsortedRows
      .slice()
      .sort((left, right) => compareUnicodeCodePoints(left.path, right.path))
    if (
      rows.some((row, index) => index > 0 && row.path === rows[index - 1]?.path)
    ) {
      return yield* new S2SSourceFreezeError({
        reason: "MALFORMED_GIT_OUTPUT",
        detail: "source tree paths are not unique"
      })
    }
    const unsigned = {
      schema_version: S2S_TRACKED_BYTES_MANIFEST_SCHEMA_VERSION,
      commit: sourceCommitA,
      tree_oid: treeOid,
      rows
    }
    return {
      ...unsigned,
      manifest_sha256: yield* canonicalDigestOrFail(unsigned)
    }
  })

export const buildS2STrackedBytesManifest = (
  sourceCommitA: string
): Effect.Effect<
  S2STrackedBytesManifest,
  S2SGitRepositoryError | S2SSourceFreezeError | S2SPreregCanonicalJsonError,
  S2SPreregGitRepository
> =>
  Effect.gen(function* () {
    yield* assertExactSourceCommitObject(sourceCommitA)
    yield* assertPreregistrationPathAbsentAtSource(sourceCommitA)
    return yield* buildS2STrackedBytesManifestUnchecked(sourceCommitA)
  })

const readPathAtCommit = (
  commit: string,
  path: string,
  operation: string
): Effect.Effect<Uint8Array, S2SGitRepositoryError, S2SPreregGitRepository> =>
  Effect.map(runGit(operation, ["show", `${commit}:${path}`]), (result) => result.stdout)

const validateRegistrationPreregistrationEntry = (
  registrationCommitB: string
): Effect.Effect<
  void,
  S2SRegistrationCommitError | S2SGitRepositoryError,
  S2SPreregGitRepository
> =>
  Effect.gen(function* () {
    const listing = yield* runGit("verify registration preregistration entry", [
      "ls-tree",
      "-z",
      "--full-tree",
      registrationCommitB,
      "--",
      S2S_PREREGISTRATION_PATH
    ])
    const entries = yield* parseTreeEntries(listing.stdout).pipe(
      Effect.mapError(
        (error) =>
          new S2SRegistrationCommitError({
            reason: "PREREGISTRATION_ENTRY_INVALID",
            detail: `registration preregistration entry is malformed: ${error.detail}`
          })
      )
    )
    const entry = entries[0]
    if (
      entries.length !== 1 ||
      entry === undefined ||
      entry.path !== S2S_PREREGISTRATION_PATH ||
      entry.mode !== "100644" ||
      entry.objectType !== "blob"
    ) {
      return yield* new S2SRegistrationCommitError({
        reason: "PREREGISTRATION_ENTRY_INVALID",
        detail: "registration preregistration entry must be one exact 100644 blob"
      })
    }
  })

const verifyS2SNumericContinuityUnchecked = (
  sourceCommitA: string
): Effect.Effect<
  S2SNumericContinuity,
  S2SGitRepositoryError | S2SSourceFreezeError | S2SPreregCanonicalJsonError,
  S2SPreregGitRepository
> =>
  Effect.gen(function* () {
    yield* assertPilotIsRawAncestor(sourceCommitA)
    const rows = yield* Effect.forEach(
      S2S_PREREG_NUMERIC_PATHS,
      (path) =>
        Effect.gen(function* () {
          const pilot = yield* readPathAtCommit(
            S2S_PREREG_PILOT_SOURCE_COMMIT,
            path,
            `read pilot numeric path ${path}`
          ).pipe(
            Effect.mapError((error) =>
              error.reason === "COMMAND_FAILED"
                ? new S2SSourceFreezeError({
                    reason: "NUMERIC_PATH_MISSING",
                    detail: `pilot numeric path is unavailable: ${path}`
                  })
                : error
            )
          )
          const source = yield* readPathAtCommit(
            sourceCommitA,
            path,
            `read source numeric path ${path}`
          ).pipe(
            Effect.mapError((error) =>
              error.reason === "COMMAND_FAILED"
                ? new S2SSourceFreezeError({
                    reason: "NUMERIC_PATH_MISSING",
                    detail: `source numeric path is unavailable: ${path}`
                  })
                : error
            )
          )
          const pilotSha256 = s2sPreregSha256Bytes(pilot)
          const sourceSha256 = s2sPreregSha256Bytes(source)
          if (pilotSha256 !== sourceSha256) {
            return yield* new S2SSourceFreezeError({
              reason: "NUMERIC_BYTES_DRIFT",
              detail: `numeric bytes changed between pilot P and source A: ${path}`
            })
          }
          return {
            path,
            pilot_sha256: pilotSha256,
            source_sha256: sourceSha256
          }
        }),
      { concurrency: 4 }
    )
    const unsigned = {
      schema_version: S2S_NUMERIC_CONTINUITY_SCHEMA_VERSION,
      pilot_source_commit_p: S2S_PREREG_PILOT_SOURCE_COMMIT,
      source_commit_a: sourceCommitA,
      paths: S2S_PREREG_NUMERIC_PATHS,
      rows,
      pilot_is_ancestor_of_source: true as const,
      byte_equal: true as const
    }
    return {
      ...unsigned,
      receipt_sha256: yield* canonicalDigestOrFail(unsigned)
    }
  })

export const verifyS2SNumericContinuity = (
  sourceCommitA: string
): Effect.Effect<
  S2SNumericContinuity,
  S2SGitRepositoryError | S2SSourceFreezeError | S2SPreregCanonicalJsonError,
  S2SPreregGitRepository
> =>
  Effect.gen(function* () {
    yield* assertExactSourceCommitObject(sourceCommitA)
    return yield* verifyS2SNumericContinuityUnchecked(sourceCommitA)
  })

export const buildS2SSourceFreeze = (
  sourceCommitA: string
): Effect.Effect<
  S2SSourceFreeze,
  S2SGitRepositoryError | S2SSourceFreezeError | S2SPreregCanonicalJsonError,
  S2SPreregGitRepository
> =>
  Effect.gen(function* () {
    yield* assertExactSourceCommitObject(sourceCommitA)
    yield* assertPreregistrationPathAbsentAtSource(sourceCommitA)
    const [trackedBytesManifest, numericContinuity] = yield* Effect.all(
      [
        buildS2STrackedBytesManifestUnchecked(sourceCommitA),
        verifyS2SNumericContinuityUnchecked(sourceCommitA)
      ],
      { concurrency: 2 }
    )
    const unsigned = {
      schema_version: S2S_SOURCE_FREEZE_SCHEMA_VERSION,
      tracked_bytes_manifest: trackedBytesManifest,
      numeric_continuity: numericContinuity
    }
    return {
      ...unsigned,
      receipt_sha256: yield* canonicalDigestOrFail(unsigned)
    }
  })

export const s2sQuicknetRoundTime = (
  round: number
): Either.Either<number, S2SPreregistrationValidationError> => {
  if (!Number.isSafeInteger(round) || round < 1) {
    return Either.left(
      new S2SPreregistrationValidationError({
        reason: "FUTURE_ROUND_INVALID",
        detail: "Quicknet round must be a positive safe integer"
      })
    )
  }
  const value = s2sQuicknetRoundTimeUnix(round)
  return value !== null
    ? Either.right(value)
    : Either.left(
        new S2SPreregistrationValidationError({
          reason: "FUTURE_ROUND_INVALID",
          detail: "Quicknet round time exceeds the safe-integer range"
        })
      )
}

export interface BuiltS2SPreregistration {
  readonly preregistration: S2SPreregistration
  readonly canonicalBytes: Uint8Array
  readonly fileSha256: string
}

const makeFutureRoundCommitment = (
  experimentId: string,
  registrationCoreSha256: string,
  registeredAtUnix: number,
  futureRound: number
): Effect.Effect<
  S2SFutureRoundCommitment,
  S2SPreregistrationValidationError | S2SPreregCanonicalJsonError
> =>
  Effect.gen(function* () {
    if (
      !EXPERIMENT_ID_PATTERN.test(experimentId) ||
      !SHA256_PATTERN.test(registrationCoreSha256) ||
      !Number.isSafeInteger(registeredAtUnix) ||
      registeredAtUnix < S2S_QUICKNET_GENESIS_TIME
    ) {
      return yield* new S2SPreregistrationValidationError({
        reason: "INVALID_INPUT",
        detail: "future-round commitment inputs are malformed"
      })
    }
    const roundTime = yield* effectFromEither(s2sQuicknetRoundTime(futureRound))
    if (roundTime <= registeredAtUnix) {
      return yield* new S2SPreregistrationValidationError({
        reason: "FUTURE_ROUND_INVALID",
        detail: "committed Quicknet round must be strictly after registration"
      })
    }
    const unsigned = {
      schema_version: S2S_FUTURE_ROUND_COMMITMENT_SCHEMA_VERSION,
      experiment_id: experimentId,
      registration_evidence_sha256: registrationCoreSha256,
      registered_at_unix: registeredAtUnix,
      chain_hash: S2S_QUICKNET_CHAIN_HASH,
      round: futureRound,
      round_time_unix: roundTime,
      task_count: S2S_PREREG_TASK_COUNT,
      seed_domain: S2S_EXTERNAL_SEED_DOMAIN,
      chronology_claim_allowed: false as const
    }
    return {
      ...unsigned,
      commitment_sha256: yield* canonicalDigestOrFail(unsigned)
    }
  })

export const buildS2SPreregistration = (
  input: unknown
): Effect.Effect<
  BuiltS2SPreregistration,
  | S2SPreregistrationValidationError
  | S2SPreregCanonicalJsonError
  | S2SGitRepositoryError
  | S2SSourceFreezeError,
  S2SPreregGitRepository
> =>
  Effect.gen(function* () {
    const decodedInput = yield* Schema.decodeUnknown(BuildPreregistrationInputSchema, {
      onExcessProperty: "error"
    })(input).pipe(
      Effect.mapError(() =>
        validationFailure(
          "INVALID_INPUT",
          "preregistration input keys or values disagree with the exact schema"
        )
      )
    )
    const sourceCommitA = decodedInput.sourceCommitA
    const sourceFreeze = yield* buildS2SSourceFreeze(sourceCommitA)
    const coreUnsigned = {
      schema_version: S2S_REGISTRATION_CORE_SCHEMA_VERSION,
      experiment_id: decodedInput.experimentId,
      claim_scope: S2S_PREREG_CLAIM_SCOPE,
      repository_binding: {
        repository: S2S_PREREG_REPOSITORY,
        ref: S2S_PREREG_REF,
        source_commit_a: sourceCommitA,
        preregistration_path: S2S_PREREGISTRATION_PATH,
        registration_commit_rule: S2S_PREREGISTRATION_COMMIT_RULE
      },
      evidence_binding: {
        pilot_adoption_receipt_sha256:
          S2S_PREREG_PILOT_ADOPTION_RECEIPT_SHA256,
        protocol_config_sha256: S2S_PREREG_PROTOCOL_CONFIG_SHA256,
        resource_policy_sha256: decodedInput.resourcePolicySha256
      },
      execution_binding: {
        task_count: S2S_PREREG_TASK_COUNT,
        external_seed_count: 1 as const,
        workflow_run_attempt: 1 as const,
        rerun_allowed: false as const,
        reroll_allowed: false as const,
        post_pulse_resume_allowed: false as const,
        task_skip_allowed: false as const,
        partial_candidate_allowed: false as const
      },
      source_freeze: sourceFreeze
    }
    const registrationCore: S2SRegistrationCore = coreUnsigned
    const registrationCoreSha256 = yield* canonicalDigestOrFail(registrationCore)
    const futureRoundCommitment = yield* makeFutureRoundCommitment(
      decodedInput.experimentId,
      registrationCoreSha256,
      decodedInput.registeredAtUnix,
      decodedInput.futureRound
    )
    const unsigned = {
      schema_version: S2S_PREREGISTRATION_SCHEMA_VERSION,
      registration_core: registrationCore,
      registration_core_sha256: registrationCoreSha256,
      future_round_commitment: futureRoundCommitment
    }
    const preregistration: S2SPreregistration = {
      ...unsigned,
      preregistration_sha256: yield* canonicalDigestOrFail(unsigned)
    }
    const canonicalBytes = yield* effectFromEither(
      canonicalBytesWithLf(preregistration)
    )
    return {
      preregistration,
      canonicalBytes,
      fileSha256: s2sPreregSha256Bytes(canonicalBytes)
    }
  })

export interface ParseS2SPreregistrationOptions {
  readonly expectedResourcePolicySha256: string
}

const VALIDATED_S2S_PREREGISTRATION_BRAND: unique symbol = Symbol(
  "hswm/ValidatedS2SPreregistration"
)

export interface ValidatedS2SPreregistration {
  readonly [VALIDATED_S2S_PREREGISTRATION_BRAND]: true
  readonly preregistration: S2SPreregistration
  readonly canonicalBytes: Uint8Array
  readonly fileSha256: string
}

interface ValidatedS2SPreregistrationSnapshot {
  readonly preregistration: S2SPreregistration
  readonly canonicalBytes: Uint8Array
  readonly fileSha256: string
  readonly sourceCommitA: string
}

const VALIDATED_S2S_PREREGISTRATION_SNAPSHOTS = new WeakMap<
  object,
  ValidatedS2SPreregistrationSnapshot
>()

const S2S_REGISTRATION_COMMIT_AUTHORITY_BRAND: unique symbol = Symbol(
  "hswm/S2SRegistrationCommitAuthority"
)

export interface S2SRegistrationCommitAuthority {
  readonly [S2S_REGISTRATION_COMMIT_AUTHORITY_BRAND]: true
}

export interface S2SRegistrationCommitAuthorityEvidence {
  readonly schemaVersion:
    typeof S2S_REGISTRATION_COMMIT_AUTHORITY_EVIDENCE_SCHEMA_VERSION
  readonly sourceCommitA: string
  readonly registrationCommitB: string
  readonly preregistrationSha256: string
  readonly preregistrationFileSha256: string
  readonly registrationCoreSha256: string
  readonly sourceFreezeReceiptSha256: string
  readonly trackedBytesManifestSha256: string
  readonly resourcePolicySha256: typeof S2S_PREREG_RESOURCE_POLICY_SHA256
  readonly registeredAtUnixSeconds: number
  readonly futureRound: number
  readonly futureRoundCommitmentSha256: string
  readonly receiptSha256: string
}

export interface S2SRegistrationWorkflowManifestBinding {
  readonly workflowPath: typeof S2S_CONFIRMATORY_WORKFLOW_PATH
  readonly mode: "100644"
  readonly objectType: "blob"
  readonly workflowFileSha256: string
  readonly trackedBytesManifestSha256: string
}

const S2S_REGISTRATION_COMMIT_AUTHORITY_EVIDENCE = new WeakMap<
  object,
  S2SRegistrationCommitAuthorityEvidence
>()

const S2S_REGISTRATION_WORKFLOW_MANIFEST_BINDINGS = new WeakMap<
  object,
  S2SRegistrationWorkflowManifestBinding | null
>()

export const inspectS2SRegistrationCommitAuthority = (
  input: unknown
): Either.Either<
  S2SRegistrationCommitAuthorityEvidence,
  S2SRegistrationCommitError
> => {
  try {
    if (input === null || typeof input !== "object") {
      return Either.left(
        new S2SRegistrationCommitError({
          reason: "INVALID_REGISTRATION_AUTHORITY",
          detail: "registration authority is not an issued object"
        })
      )
    }
    const evidence = S2S_REGISTRATION_COMMIT_AUTHORITY_EVIDENCE.get(input)
    return evidence === undefined
      ? Either.left(
          new S2SRegistrationCommitError({
            reason: "INVALID_REGISTRATION_AUTHORITY",
            detail: "registration authority was not issued by this module"
          })
        )
      : Either.right(evidence)
  } catch {
    return Either.left(
      new S2SRegistrationCommitError({
        reason: "INVALID_REGISTRATION_AUTHORITY",
        detail: "registration authority inspection failed closed"
      })
    )
  }
}

export const inspectS2SRegistrationWorkflowManifestBinding = (
  input: unknown
): Either.Either<
  S2SRegistrationWorkflowManifestBinding,
  S2SRegistrationCommitError
> => {
  try {
    if (input === null || typeof input !== "object") {
      return Either.left(
        new S2SRegistrationCommitError({
          reason: "INVALID_REGISTRATION_AUTHORITY",
          detail: "registration authority is not an issued object"
        })
      )
    }
    const binding = S2S_REGISTRATION_WORKFLOW_MANIFEST_BINDINGS.get(input)
    return binding === undefined
      ? Either.left(
          new S2SRegistrationCommitError({
            reason: "INVALID_REGISTRATION_AUTHORITY",
            detail: "registration authority was not issued by this module"
          })
        )
      : binding === null
        ? Either.left(
            new S2SRegistrationCommitError({
              reason: "WORKFLOW_MANIFEST_BINDING_INVALID",
              detail:
                "source A manifest lacks one exact 100644 blob workflow row"
            })
          )
        : Either.right(binding)
  } catch {
    return Either.left(
      new S2SRegistrationCommitError({
        reason: "INVALID_REGISTRATION_AUTHORITY",
        detail: "registration workflow binding inspection failed closed"
      })
    )
  }
}

const deepFreezePreregistrationSnapshot = (
  value: S2SPreregistration
): S2SPreregistration => {
  const seen = new Set<object>()
  const freeze = (current: unknown): void => {
    if (current === null || typeof current !== "object" || seen.has(current)) return
    seen.add(current)
    for (const descriptor of Object.values(
      Object.getOwnPropertyDescriptors(current)
    )) {
      if ("value" in descriptor) freeze(descriptor.value)
    }
    Object.freeze(current)
  }
  freeze(value)
  return value
}

const validationFailure = (
  reason: S2SPreregistrationValidationError["reason"],
  detail: string
) => new S2SPreregistrationValidationError({ reason, detail })

const isUnknownRecord = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value)

const isCanonicalRecord = (
  value: CanonicalJson
): value is { readonly [key: string]: CanonicalJson } =>
  value !== null && typeof value === "object" && !Array.isArray(value)

const parseCanonicalRoot = (
  bytes: Uint8Array
): Effect.Effect<Record<string, unknown>, S2SPreregistrationValidationError> =>
  Effect.gen(function* () {
    if (bytes.length < 3 || bytes.length > MAX_PREREGISTRATION_BYTES) {
      return yield* validationFailure(
        "INVALID_CANONICAL_JSON",
        "preregistration byte length is outside the fixed bound"
      )
    }
    let text: string
    try {
      text = UTF8_DECODER.decode(bytes)
    } catch {
      return yield* validationFailure(
        "INVALID_CANONICAL_JSON",
        "preregistration is not strict UTF-8"
      )
    }
    let parsed: unknown
    try {
      parsed = JSON.parse(text)
    } catch {
      return yield* validationFailure(
        "INVALID_CANONICAL_JSON",
        "preregistration JSON decoding failed"
      )
    }
    const encoded = s2sPreregCanonicalJson(parsed)
    if (Either.isLeft(encoded) || `${encoded.right}\n` !== text) {
      return yield* validationFailure(
        "INVALID_CANONICAL_JSON",
        "preregistration is not the unique canonical JSON+LF encoding"
      )
    }
    if (!isUnknownRecord(parsed)) {
      return yield* validationFailure(
        "INVALID_CANONICAL_JSON",
        "preregistration root must be an object"
      )
    }
    return parsed
  })

const decodePreregistration = (
  value: unknown
): Effect.Effect<S2SPreregistration, S2SPreregistrationValidationError> =>
  Schema.decodeUnknown(PreregistrationSchema, {
    onExcessProperty: "error"
  })(value).pipe(
    Effect.mapError(() =>
      validationFailure(
        "SCHEMA_MISMATCH",
        "preregistration keys or primitive types disagree with the exact schema"
      )
    )
  )

const verifySelfHash = (
  value: unknown,
  hashField: string,
  expected: string,
  detail: string
): Effect.Effect<void, S2SPreregistrationValidationError | S2SPreregCanonicalJsonError> =>
  Effect.gen(function* () {
    const canonical = canonicalize(value, "$", new Set())
    if (Either.isLeft(canonical)) return yield* canonical.left
    if (!isCanonicalRecord(canonical.right)) {
      return yield* validationFailure(
        "SCHEMA_MISMATCH",
        `${detail}: hashed value is not an object`
      )
    }
    const unsigned: Record<string, CanonicalJson> = { ...canonical.right }
    delete unsigned[hashField]
    const actual = yield* canonicalDigestOrFail(unsigned)
    if (actual !== expected) {
      return yield* validationFailure("HASH_MISMATCH", detail)
    }
  })

const validateSourceFreezeSemantics = (
  sourceFreeze: S2SSourceFreeze
): Effect.Effect<
  void,
  S2SPreregistrationValidationError | S2SPreregCanonicalJsonError
> =>
  Effect.gen(function* () {
    const manifest = sourceFreeze.tracked_bytes_manifest
    const continuity = sourceFreeze.numeric_continuity
    if (
      continuity.source_commit_a !== manifest.commit ||
      continuity.rows.length !== S2S_PREREG_NUMERIC_PATHS.length ||
      continuity.paths.length !== S2S_PREREG_NUMERIC_PATHS.length ||
      continuity.rows.some(
        (row, index) =>
          row.path !== S2S_PREREG_NUMERIC_PATHS[index] ||
          continuity.paths[index] !== S2S_PREREG_NUMERIC_PATHS[index] ||
          row.pilot_sha256 !== row.source_sha256
      )
    ) {
      return yield* validationFailure(
        "FIXED_BINDING_DRIFT",
        "source-freeze numeric continuity bindings drifted"
      )
    }
    if (
      manifest.rows.some((row) => row.path === S2S_PREREGISTRATION_PATH)
    ) {
      return yield* validationFailure(
        "FIXED_BINDING_DRIFT",
        "source A manifest must not contain the preregistration path"
      )
    }
    const sortedPaths = manifest.rows
      .map((row) => row.path)
      .slice()
      .sort(compareUnicodeCodePoints)
    if (
      manifest.rows.some((row, index) => row.path !== sortedPaths[index]) ||
      new Set(sortedPaths).size !== sortedPaths.length
    ) {
      return yield* validationFailure(
        "FIXED_BINDING_DRIFT",
        "tracked manifest paths are not unique and canonically sorted"
      )
    }
    yield* verifySelfHash(
      manifest,
      "manifest_sha256",
      manifest.manifest_sha256,
      "tracked manifest self-hash mismatch"
    )
    yield* verifySelfHash(
      continuity,
      "receipt_sha256",
      continuity.receipt_sha256,
      "numeric continuity self-hash mismatch"
    )
    yield* verifySelfHash(
      sourceFreeze,
      "receipt_sha256",
      sourceFreeze.receipt_sha256,
      "source-freeze self-hash mismatch"
    )
  })

const validateDecodedSemantics = (
  value: S2SPreregistration,
  expectedResourcePolicySha256: string
): Effect.Effect<
  void,
  S2SPreregistrationValidationError | S2SPreregCanonicalJsonError
> =>
  Effect.gen(function* () {
    if (expectedResourcePolicySha256 !== S2S_PREREG_RESOURCE_POLICY_SHA256) {
      return yield* validationFailure(
        "INVALID_INPUT",
        "expected resource-policy SHA differs from the frozen sibling policy"
      )
    }
    const core = value.registration_core
    const manifest = core.source_freeze.tracked_bytes_manifest
    if (
      core.evidence_binding.resource_policy_sha256 !==
        expectedResourcePolicySha256 ||
      core.repository_binding.source_commit_a !== manifest.commit ||
      value.future_round_commitment.experiment_id !== core.experiment_id
    ) {
      return yield* validationFailure(
        "FIXED_BINDING_DRIFT",
        "preregistration evidence/source bindings drifted"
      )
    }
    yield* validateSourceFreezeSemantics(core.source_freeze)
    const coreSha = yield* canonicalDigestOrFail(core)
    if (
      coreSha !== value.registration_core_sha256 ||
      value.future_round_commitment.registration_evidence_sha256 !== coreSha
    ) {
      return yield* validationFailure(
        "HASH_MISMATCH",
        "registration core or future commitment link mismatch"
      )
    }
    yield* verifySelfHash(
      value.future_round_commitment,
      "commitment_sha256",
      value.future_round_commitment.commitment_sha256,
      "future-round commitment self-hash mismatch"
    )
    const expectedRoundTime = yield* effectFromEither(
      s2sQuicknetRoundTime(value.future_round_commitment.round)
    )
    if (
      value.future_round_commitment.round_time_unix !== expectedRoundTime ||
      value.future_round_commitment.registered_at_unix <
        S2S_QUICKNET_GENESIS_TIME ||
      expectedRoundTime <= value.future_round_commitment.registered_at_unix
    ) {
      return yield* validationFailure(
        "FUTURE_ROUND_INVALID",
        "future-round time/ordering is invalid"
      )
    }
    yield* verifySelfHash(
      value,
      "preregistration_sha256",
      value.preregistration_sha256,
      "preregistration self-hash mismatch"
    )
  })

export const parseAndValidateS2SPreregistration = (
  bytes: Uint8Array,
  options: ParseS2SPreregistrationOptions
): Effect.Effect<
  ValidatedS2SPreregistration,
  | S2SPreregistrationValidationError
  | S2SPreregCanonicalJsonError
  | S2SGitRepositoryError
  | S2SSourceFreezeError,
  S2SPreregGitRepository
> =>
  Effect.gen(function* () {
    const originalBytes = new Uint8Array(bytes)
    const root = yield* parseCanonicalRoot(originalBytes)
    const decoded = yield* decodePreregistration(root)
    yield* validateDecodedSemantics(
      decoded,
      options.expectedResourcePolicySha256
    )
    const recomputed = yield* buildS2SSourceFreeze(
      decoded.registration_core.repository_binding.source_commit_a
    )
    const expectedFreeze = yield* canonicalDigestOrFail(
      decoded.registration_core.source_freeze
    )
    const actualFreeze = yield* canonicalDigestOrFail(recomputed)
    if (actualFreeze !== expectedFreeze) {
      return yield* validationFailure(
        "SOURCE_FREEZE_MISMATCH",
        "source A no longer reproduces the registered source freeze"
      )
    }
    const canonicalBytes = originalBytes
    const fileSha256 = s2sPreregSha256Bytes(canonicalBytes)
    const preregistration = deepFreezePreregistrationSnapshot(decoded)
    const validated: ValidatedS2SPreregistration = Object.freeze({
      [VALIDATED_S2S_PREREGISTRATION_BRAND]: true as const,
      get preregistration(): S2SPreregistration {
        return preregistration
      },
      get canonicalBytes(): Uint8Array {
        return new Uint8Array(canonicalBytes)
      },
      fileSha256
    })
    VALIDATED_S2S_PREREGISTRATION_SNAPSHOTS.set(validated, {
      preregistration,
      canonicalBytes,
      fileSha256,
      sourceCommitA:
        preregistration.registration_core.repository_binding.source_commit_a
    })
    return validated
  })

const validatedSnapshot = (
  value: unknown
): ValidatedS2SPreregistrationSnapshot | undefined => {
  if (value === null || typeof value !== "object") return undefined
  return VALIDATED_S2S_PREREGISTRATION_SNAPSHOTS.get(value)
}

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean => {
  if (left.length !== right.length) return false
  for (let index = 0; index < left.length; index += 1) {
    if (left[index] !== right[index]) return false
  }
  return true
}

export const validateS2SRegistrationCommitB = (
  validated: ValidatedS2SPreregistration,
  registrationCommitB: string
): Effect.Effect<
  S2SRegistrationCommitAuthority,
  S2SRegistrationCommitError | S2SGitRepositoryError | S2SSourceFreezeError,
  S2SPreregGitRepository
> =>
  Effect.gen(function* () {
    const snapshot = validatedSnapshot(validated)
    if (snapshot === undefined) {
      return yield* new S2SRegistrationCommitError({
        reason: "INVALID_VALIDATION_SNAPSHOT",
        detail: "registration validation requires an authentic parsed snapshot"
      })
    }
    if (!isGitSha(registrationCommitB)) {
      return yield* new S2SRegistrationCommitError({
        reason: "INVALID_COMMIT",
        detail: "registration commit B must be a lowercase 40-hex Git SHA"
      })
    }
    const sourceCommitA = snapshot.sourceCommitA
    const rawRegistrationCommit = yield* readRawCommitObject(
      registrationCommitB,
      "read raw registration commit"
    ).pipe(
      Effect.catchTag("S2SRawCommitObjectError", (error) =>
        Effect.fail(
          new S2SRegistrationCommitError({
            reason: "INVALID_COMMIT",
            detail: `registration commit object is invalid: ${error.detail}`
          })
        )
      )
    )
    if (
      rawRegistrationCommit.parents.length !== 1 ||
      rawRegistrationCommit.parents[0] !== sourceCommitA
    ) {
      return yield* new S2SRegistrationCommitError({
        reason: "NOT_DIRECT_CHILD",
        detail: "registration commit B is not the direct child of source A"
      })
    }
    const diffResult = yield* runGit("validate registration diff", [
      "diff-tree",
      "--no-commit-id",
      "--name-status",
      "-r",
      "-z",
      sourceCommitA,
      registrationCommitB
    ])
    const diffEntries = yield* Effect.forEach(
      splitAtNul(diffResult.stdout).filter((entry) => entry.length > 0),
      (entry) => decodeUtf8(entry, "registration diff entry")
    )
    if (
      diffEntries.length !== 2 ||
      diffEntries[0] !== "A" ||
      diffEntries[1] !== S2S_PREREGISTRATION_PATH
    ) {
      return yield* new S2SRegistrationCommitError({
        reason: "DIFF_NOT_ADD_ONLY_PREREGISTRATION",
        detail: "registration commit must add only the exact preregistration path"
      })
    }
    yield* validateRegistrationPreregistrationEntry(registrationCommitB)
    const committed = yield* readPathAtCommit(
      registrationCommitB,
      S2S_PREREGISTRATION_PATH,
      "read committed preregistration"
    )
    if (!sameBytes(committed, snapshot.canonicalBytes)) {
      return yield* new S2SRegistrationCommitError({
        reason: "PREREGISTRATION_BYTES_DRIFT",
        detail: "commit B preregistration bytes differ from validated bytes"
      })
    }
    const preregistration = snapshot.preregistration
    const authorityEvidenceCore = Object.freeze({
      schemaVersion:
        S2S_REGISTRATION_COMMIT_AUTHORITY_EVIDENCE_SCHEMA_VERSION,
      sourceCommitA,
      registrationCommitB,
      preregistrationSha256: preregistration.preregistration_sha256,
      preregistrationFileSha256: snapshot.fileSha256,
      registrationCoreSha256: preregistration.registration_core_sha256,
      sourceFreezeReceiptSha256:
        preregistration.registration_core.source_freeze.receipt_sha256,
      trackedBytesManifestSha256:
        preregistration.registration_core.source_freeze.tracked_bytes_manifest
          .manifest_sha256,
      resourcePolicySha256: S2S_PREREG_RESOURCE_POLICY_SHA256,
      registeredAtUnixSeconds:
        preregistration.future_round_commitment.registered_at_unix,
      futureRound: preregistration.future_round_commitment.round,
      futureRoundCommitmentSha256:
        preregistration.future_round_commitment.commitment_sha256
    })
    const evidenceHash = s2sPreregCanonicalSha256(authorityEvidenceCore)
    if (Either.isLeft(evidenceHash)) {
      return yield* new S2SRegistrationCommitError({
        reason: "AUTHORITY_EVIDENCE_NOT_CANONICAL",
        detail: "registration authority evidence is not canonical"
      })
    }
    const evidence: S2SRegistrationCommitAuthorityEvidence = Object.freeze({
      ...authorityEvidenceCore,
      receiptSha256: evidenceHash.right
    })
    const authority: S2SRegistrationCommitAuthority = Object.freeze({
      [S2S_REGISTRATION_COMMIT_AUTHORITY_BRAND]: true as const
    })
    S2S_REGISTRATION_COMMIT_AUTHORITY_EVIDENCE.set(authority, evidence)
    const workflowRows = preregistration.registration_core.source_freeze
      .tracked_bytes_manifest.rows.filter(
        (row) => row.path === S2S_CONFIRMATORY_WORKFLOW_PATH
      )
    const workflowRow = workflowRows[0]
    const workflowBinding =
      workflowRows.length === 1 &&
      workflowRow !== undefined &&
      workflowRow.mode === "100644" &&
      workflowRow.object_type === "blob"
        ? Object.freeze({
            workflowPath: S2S_CONFIRMATORY_WORKFLOW_PATH,
            mode: "100644" as const,
            objectType: "blob" as const,
            workflowFileSha256: workflowRow.sha256,
            trackedBytesManifestSha256:
              preregistration.registration_core.source_freeze
                .tracked_bytes_manifest.manifest_sha256
          })
        : null
    S2S_REGISTRATION_WORKFLOW_MANIFEST_BINDINGS.set(
      authority,
      workflowBinding
    )
    return authority
  })
