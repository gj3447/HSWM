#!/usr/bin/env node
/**
 * One-request CLI bridge for the standard LE-0 subprocess runner.
 *
 * It is intentionally a wrapper around an already declared action command
 * and separately declared verifier command.  It never shells out, invents a
 * graph delta, or upgrades a verifier exit status into causal evidence.
 *
 * The whole request is one Effect program: the request is decoded by Schema
 * with exact keys, every refusal is a typed failure, the schema, grants, and
 * declared frozen inputs are read through the `PosixFileSystem` service, the
 * action and verifier run through `BoundedSubprocess`, and the executable's
 * only runtime boundary is `runProcessMain`.
 */
import { isAbsolute } from "node:path"
import { pathToFileURL } from "node:url"

import type { ParseResult } from "effect"
import { Effect, Either, Schema } from "effect"

import type {
  CanonicalAtomV2ContentDescriptor,
  CanonicalAtomV2ContentStoreError
} from "./canonical-atom-v2-content.js"
import type { CanonicalAtomV2ContentAuthorizationConfigurationError } from "./canonical-atom-v2-content-runtime.js"
import {
  CanonicalAtomV2DurableGraphView,
  type CanonicalAtomV2DurableRecoveryFailure
} from "./canonical-atom-v2-durable-runtime.js"
import { canonicalJsonBytes, decodeCanonicalJsonBytes, type CanonicalJson } from "./canonical-atom-v2-json.js"
import {
  makeGraphLoopEngineeringFileLayer,
  type GraphLoopControlError,
  type GraphLoopControlJournalError
} from "./canonical-atom-v2-graph-loop-engineering.js"
import {
  HSWM_GRAPH_LOOP_RESEARCH_FROZEN_INPUTS_V1_MEDIA_TYPE,
  GraphLoopResearchProcessRunner,
  makeGraphLoopResearchProcessRunnerLayerWithBoundedSubprocess,
  type GraphLoopResearchJobError,
  type GraphLoopResearchJobResult
} from "./canonical-atom-v2-graph-loop-research-job.js"
import { PosixFileSystem, type BoundedSubprocess, type PosixFileSystemShape } from "./effect-posix-services.js"
import { ProcessRefusal, refuse, runProcessMain } from "./effect-process-main.js"

export const HSWM_GRAPH_LOOP_RESEARCH_JOB_PROCESS_V1_CONTRACT_VERSION =
  "hswm-graph-loop-research-job-process/v1" as const

const MAX_INPUT_BYTES = 1_048_576
const MAX_FROZEN_INPUT_BYTES = 16 * 1_024 * 1_024
const MAX_TOTAL_FROZEN_INPUT_BYTES = 64 * 1_024 * 1_024
const SCHEMA_MEDIA_TYPE = "application/vnd.hswm.canonical-atom-v2-schema+json"
const GRANTS_MEDIA_TYPE = "application/vnd.hswm.canonical-atom-v2-grants+json"

// ---------------------------------------------------------------------------
// Request schemas: exact keys at every level, declared rather than hand-parsed.
// ---------------------------------------------------------------------------

const Identifier = Schema.String.pipe(Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/))
const MediaType = Schema.String.pipe(
  Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,126}\/[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,126}$/)
)
const NonemptyString = Schema.String.pipe(Schema.minLength(1))
const SafeInteger = Schema.Number.pipe(
  Schema.int(),
  Schema.greaterThanOrEqualTo(Number.MIN_SAFE_INTEGER),
  Schema.lessThanOrEqualTo(Number.MAX_SAFE_INTEGER)
)
const AbsolutePath = Schema.String.pipe(
  Schema.minLength(1),
  Schema.maxLength(4096),
  Schema.filter((value) => !value.includes("\0") && isAbsolute(value), { message: () => "path must be absolute" })
)

const CommandSchema = Schema.Struct({
  argv: Schema.Array(NonemptyString),
  cwd: AbsolutePath,
  timeoutMs: SafeInteger,
  environment: Schema.optionalWith(Schema.Record({ key: Schema.String, value: Schema.String }), { exact: true })
}).annotations({ identifier: "GraphLoopResearchCommand" })

const ContractSchema = Schema.Struct({
  runId: NonemptyString,
  triggerId: NonemptyString,
  actorId: NonemptyString,
  verifierId: NonemptyString,
  maximumAttempts: SafeInteger,
  maximumActions: SafeInteger
}).annotations({ identifier: "GraphLoopContract" })

const VerifierSchema = Schema.Struct({
  command: CommandSchema,
  acceptExitCodes: Schema.Array(SafeInteger),
  retryExitCodes: Schema.Array(SafeInteger)
}).annotations({ identifier: "GraphLoopResearchVerifier" })

const JobSchema = Schema.Struct({ contract: ContractSchema, action: CommandSchema, verifier: VerifierSchema })
  .annotations({ identifier: "GraphLoopResearchJob" })

const FrozenInputSchema = Schema.Struct({ path: AbsolutePath, mediaType: MediaType })
  .annotations({ identifier: "GraphLoopResearchFrozenInput" })

const RequestSchema = Schema.Struct({
  _tag: Schema.Literal("GraphLoopResearchJobProcessRequest"),
  contractVersion: Schema.Literal(HSWM_GRAPH_LOOP_RESEARCH_JOB_PROCESS_V1_CONTRACT_VERSION),
  durableRoot: AbsolutePath,
  controlJournalRoot: AbsolutePath,
  journalLineageId: Identifier,
  schemaPath: AbsolutePath,
  grantsPath: AbsolutePath,
  frozenInputs: Schema.Array(FrozenInputSchema).pipe(Schema.minItems(1), Schema.maxItems(32)),
  job: JobSchema
}).annotations({ identifier: "GraphLoopResearchJobProcessRequest" })

type ProcessRequest = typeof RequestSchema.Type
type ProcessFrozenInput = typeof FrozenInputSchema.Type

interface FrozenInputBytes extends ProcessFrozenInput {
  readonly role: "DURABLE_SCHEMA" | "DURABLE_GRANTS" | "DECLARED_FROZEN_INPUT"
  readonly bytes: Uint8Array
}

interface FrozenInputBundle {
  readonly schemaBytes: Uint8Array
  readonly grants: CanonicalJson
  readonly inputs: ReadonlyArray<FrozenInputBytes>
}

export type GraphLoopResearchJobProcessError =
  | ProcessRefusal
  | GraphLoopResearchJobError
  | GraphLoopControlError
  | GraphLoopControlJournalError
  | CanonicalAtomV2ContentStoreError
  | CanonicalAtomV2ContentAuthorizationConfigurationError
  | CanonicalAtomV2DurableRecoveryFailure
  | ParseResult.ParseError

// ---------------------------------------------------------------------------
// Request decoding
// ---------------------------------------------------------------------------

const asObject = (value: CanonicalJson): Readonly<Record<string, CanonicalJson>> | null =>
  typeof value === "object" && value !== null && !Array.isArray(value) ? (value as Readonly<Record<string, CanonicalJson>>) : null

/** One line from the parse tree: identifiers and path segments, without the tree drawing. */
const describeParseError = (error: ParseResult.ParseError): string =>
  error.message.replace(/[│└├─]+/g, " ").replace(/\s+/g, " ").trim()

const decodeRequest = (request: CanonicalJson): Effect.Effect<ProcessRequest, ProcessRefusal> => {
  const decoded = Schema.decodeUnknownEither(RequestSchema, { onExcessProperty: "error" })(request)
  if (Either.isLeft(decoded)) {
    const shape = asObject(request)
    if (shape === null) return Effect.fail(refuse("request must be an object"))
    if (
      shape["_tag"] !== "GraphLoopResearchJobProcessRequest" ||
      shape["contractVersion"] !== HSWM_GRAPH_LOOP_RESEARCH_JOB_PROCESS_V1_CONTRACT_VERSION
    ) return Effect.fail(refuse("request tag or contract version is invalid"))
    return Effect.fail(refuse(`request is not a valid research job request: ${describeParseError(decoded.left)}`))
  }
  const paths = decoded.right.frozenInputs.map((input) => input.path)
  if (new Set(paths).size !== paths.length) return Effect.fail(refuse("request.frozenInputs cannot repeat a source path"))
  return Effect.succeed(Object.freeze({
    ...decoded.right,
    frozenInputs: Object.freeze([...decoded.right.frozenInputs].sort((left, right) => left.path.localeCompare(right.path)))
  }))
}

// ---------------------------------------------------------------------------
// Frozen inputs through the filesystem service
// ---------------------------------------------------------------------------

/** Schema and grants are caller-declared paths: follow symlinks as before, then bound the regular file. */
const readDeclaredFile = (
  fs: PosixFileSystemShape,
  path: string,
  label: string
): Effect.Effect<Uint8Array, ProcessRefusal> =>
  fs.realpath(path, label).pipe(
    Effect.flatMap((resolved) => fs.readRegularBounded(resolved, { maximumBytes: MAX_TOTAL_FROZEN_INPUT_BYTES, operation: label })),
    Effect.map((read) => read.bytes),
    Effect.mapError((cause) => refuse(cause.code === "BYTE_BOUND_EXCEEDED"
      ? `${label} exceeds the total frozen-input byte limit`
      : `${label} is not a readable regular file: ${cause.code}`))
  )

/** A declared frozen input must itself be a regular file: symlinks are refused, never followed. */
const readFrozenInput = (
  fs: PosixFileSystemShape,
  input: ProcessFrozenInput
): Effect.Effect<FrozenInputBytes, ProcessRefusal> =>
  Effect.gen(function* () {
    const notRegular = refuse(`frozen input is not a regular non-symlink file: ${input.path}`)
    const tooLarge = refuse(`frozen input exceeds the per-file byte limit: ${input.path}`)
    const identity = yield* fs.identity(input.path, "frozen-input").pipe(Effect.mapError(() => notRegular))
    if (identity.kind !== "FILE") return yield* Effect.fail(notRegular)
    if (identity.size > MAX_FROZEN_INPUT_BYTES) return yield* Effect.fail(tooLarge)
    const read = yield* fs.readRegularBounded(input.path, { maximumBytes: MAX_FROZEN_INPUT_BYTES, operation: "frozen-input" }).pipe(
      Effect.mapError((cause) => (cause.code === "BYTE_BOUND_EXCEEDED" ? tooLarge : notRegular))
    )
    return Object.freeze({ role: "DECLARED_FROZEN_INPUT" as const, path: input.path, mediaType: input.mediaType, bytes: read.bytes })
  })

const readFrozenInputBundle = (
  fs: PosixFileSystemShape,
  request: ProcessRequest
): Effect.Effect<FrozenInputBundle, ProcessRefusal> =>
  Effect.gen(function* () {
    const schemaBytes = yield* readDeclaredFile(fs, request.schemaPath, "schemaPath")
    const grantsBytes = yield* readDeclaredFile(fs, request.grantsPath, "grantsPath")
    const grants = decodeCanonicalJsonBytes(grantsBytes)
    if (Either.isLeft(grants)) return yield* Effect.fail(refuse("grantsPath must contain canonical JSON bytes"))
    const declared: Array<FrozenInputBytes> = []
    let total = schemaBytes.byteLength + grantsBytes.byteLength
    for (const input of request.frozenInputs) {
      const read = yield* readFrozenInput(fs, input)
      total += read.bytes.byteLength
      if (total > MAX_TOTAL_FROZEN_INPUT_BYTES) {
        return yield* Effect.fail(refuse("schema, grants, and declared frozen inputs exceed the total byte limit"))
      }
      declared.push(read)
    }
    return Object.freeze({
      schemaBytes,
      grants: grants.right,
      inputs: Object.freeze([
        Object.freeze({ role: "DURABLE_SCHEMA" as const, path: request.schemaPath, mediaType: SCHEMA_MEDIA_TYPE, bytes: schemaBytes }),
        Object.freeze({ role: "DURABLE_GRANTS" as const, path: request.grantsPath, mediaType: GRANTS_MEDIA_TYPE, bytes: grantsBytes }),
        ...declared
      ])
    })
  })

// ---------------------------------------------------------------------------
// Content-addressed manifest and reply
// ---------------------------------------------------------------------------

const descriptorJson = (descriptor: CanonicalAtomV2ContentDescriptor): CanonicalJson =>
  Object.freeze({ mediaType: descriptor.mediaType, byteLength: descriptor.byteLength, sha256: descriptor.sha256 })

const stageFrozenInputManifest = (
  view: CanonicalAtomV2DurableGraphView["Type"],
  inputs: ReadonlyArray<FrozenInputBytes>
): Effect.Effect<CanonicalAtomV2ContentDescriptor, CanonicalAtomV2ContentStoreError | ProcessRefusal> =>
  Effect.gen(function* () {
    const records: Array<CanonicalJson> = []
    for (const input of inputs) {
      const content = yield* view.stageContent(input.mediaType, input.bytes)
      records.push(Object.freeze({ role: input.role, sourcePath: input.path, content: descriptorJson(content) }))
    }
    const encoded = canonicalJsonBytes({
      _tag: "GraphLoopResearchFrozenInputs",
      contractVersion: HSWM_GRAPH_LOOP_RESEARCH_JOB_PROCESS_V1_CONTRACT_VERSION,
      inputs: Object.freeze(records)
    })
    if (Either.isLeft(encoded)) return yield* Effect.fail(refuse("frozen-input manifest cannot form canonical JSON"))
    return yield* view.stageContent(HSWM_GRAPH_LOOP_RESEARCH_FROZEN_INPUTS_V1_MEDIA_TYPE, encoded.right)
  })

const replyJson = (result: GraphLoopResearchJobResult): CanonicalJson =>
  Object.freeze({
    _tag: "GraphLoopResearchJobProcessResult",
    contractVersion: HSWM_GRAPH_LOOP_RESEARCH_JOB_PROCESS_V1_CONTRACT_VERSION,
    terminal: result.terminal,
    attempts: result.attempts,
    frozenInputs: result.frozenInputs === null ? null : descriptorJson(result.frozenInputs),
    action: descriptorJson(result.action),
    verifier: result.verifier === null ? null : descriptorJson(result.verifier)
  })

// ---------------------------------------------------------------------------
// Program
// ---------------------------------------------------------------------------

/**
 * Executes one standard research job as one Effect program: decode, read the
 * frozen inputs, build the protected runtime, stage the manifest, and run the
 * action and verifier through the bounded subprocess service.
 */
export const executeGraphLoopResearchJobProcess = (
  request: CanonicalJson
): Effect.Effect<CanonicalJson, GraphLoopResearchJobProcessError, PosixFileSystem | BoundedSubprocess> =>
  Effect.gen(function* () {
    const parsed = yield* decodeRequest(request)
    const fs = yield* PosixFileSystem
    const bundle = yield* readFrozenInputBundle(fs, parsed)
    const standard = makeGraphLoopEngineeringFileLayer(
      parsed.durableRoot,
      parsed.controlJournalRoot,
      parsed.journalLineageId,
      bundle.schemaBytes,
      bundle.grants
    )
    const result = yield* Effect.gen(function* () {
      const view = yield* CanonicalAtomV2DurableGraphView
      const inputManifest = yield* stageFrozenInputManifest(view, bundle.inputs)
      const runner = yield* GraphLoopResearchProcessRunner
      return yield* runner.run({ ...parsed.job, frozenInputs: inputManifest })
    }).pipe(
      Effect.provide(makeGraphLoopResearchProcessRunnerLayerWithBoundedSubprocess),
      Effect.provide(standard)
    )
    return replyJson(result)
  })

const stringField = (error: object, key: string): string | null => {
  const value = (error as Readonly<Record<string, unknown>>)[key]
  return typeof value === "string" ? value : null
}

/** One stderr line: the refusal detail, or the error tag with its coded fields. */
export const describeGraphLoopResearchJobProcessFailure = (error: GraphLoopResearchJobProcessError): string => {
  if (error._tag === "ProcessRefusal") return error.detail
  return [error._tag, stringField(error, "operation"), stringField(error, "reason"), stringField(error, "code"), stringField(error, "detail") ?? error.message]
    .filter((part): part is string => part !== null && part.length > 0)
    .join(": ")
}

export const runGraphLoopResearchJobProcess = (): Promise<number> =>
  runProcessMain({
    refusalPrefix: "HSWM_GRAPH_LOOP_RESEARCH_JOB_REFUSED",
    maximumStdinBytes: MAX_INPUT_BYTES,
    program: executeGraphLoopResearchJobProcess,
    describeFailure: describeGraphLoopResearchJobProcessFailure
  })

const invokedPath = process.argv[1]
if (invokedPath !== undefined && import.meta.url === pathToFileURL(invokedPath).href) {
  void runGraphLoopResearchJobProcess().then((exitCode) => { process.exitCode = exitCode })
}
