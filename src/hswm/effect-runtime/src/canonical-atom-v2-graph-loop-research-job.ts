/**
 * Bounded subprocess runner for the LE-0 control contract.
 *
 * This executes a declared research action and a separately identified
 * verifier command without a shell.  It records their content-addressed
 * observations through GraphLoopEngineeringController.  It neither treats an
 * exit code as external truth nor automatically admits a graph delta: callers
 * must provide the later GE-2 evidence and candidate explicitly.
 */
import { spawn } from "node:child_process"
import { createHash } from "node:crypto"
import { isAbsolute } from "node:path"

import { Context, Data, Effect, Either, Layer } from "effect"

import {
  CanonicalAtomV2DurableGraphView
} from "./canonical-atom-v2-durable-runtime.js"
import type { CanonicalAtomV2ContentDescriptor } from "./canonical-atom-v2-content.js"
import { canonicalJsonBytes, type CanonicalJson } from "./canonical-atom-v2-json.js"
import {
  GraphLoopControlError,
  GraphLoopControlJournalError,
  GraphLoopEngineeringController,
  type GraphLoopContract
} from "./canonical-atom-v2-graph-loop-engineering.js"

export const HSWM_GRAPH_LOOP_RESEARCH_JOB_V1_CONTRACT_VERSION =
  "hswm-graph-loop-research-job/v1" as const
export const HSWM_GRAPH_LOOP_RESEARCH_ACTION_V1_MEDIA_TYPE =
  "application/vnd.hswm.graph-loop-research-action-v1+json" as const
export const HSWM_GRAPH_LOOP_RESEARCH_VERIFIER_V1_MEDIA_TYPE =
  "application/vnd.hswm.graph-loop-research-verifier-v1+json" as const
export const HSWM_GRAPH_LOOP_RESEARCH_FROZEN_INPUTS_V1_MEDIA_TYPE =
  "application/vnd.hswm.graph-loop-research-frozen-inputs-v1+json" as const
export const HSWM_GRAPH_LOOP_RESEARCH_STDOUT_V1_MEDIA_TYPE =
  "application/vnd.hswm.graph-loop-research-stdout-v1+octets" as const
export const HSWM_GRAPH_LOOP_RESEARCH_STDERR_V1_MEDIA_TYPE =
  "application/vnd.hswm.graph-loop-research-stderr-v1+octets" as const
export const HSWM_GRAPH_LOOP_RESEARCH_MAX_OUTPUT_BYTES = 1_048_576 as const
/** A bounded long-running research action may hold the LE-0 lease for one day. */
export const HSWM_GRAPH_LOOP_RESEARCH_MAX_TIMEOUT_MS = 86_400_000 as const

type ResearchJobTerminal =
  | "STOPPED_ACCEPTED_NO_GRAPH_DELTA"
  | "STOPPED_REJECTED"
  | "ESCALATED"

type ResearchJobDecision = "ACCEPT" | "RETRY" | "REJECT"

export interface GraphLoopResearchCommand {
  /** Executed directly with `shell: false`; argv[0] is the executable. */
  readonly argv: ReadonlyArray<string>
  readonly cwd: string
  readonly timeoutMs: number
  /** Values are passed to the child but never written to its control artifact. */
  readonly environment?: Readonly<Record<string, string>>
}

export interface GraphLoopResearchVerifier {
  readonly command: GraphLoopResearchCommand
  /** A verifier exit code in this set means a bounded engineering accept. */
  readonly acceptExitCodes: ReadonlyArray<number>
  /** A verifier exit code in this set explicitly requests another attempt. */
  readonly retryExitCodes: ReadonlyArray<number>
}

export interface GraphLoopResearchJobRequest {
  readonly contract: GraphLoopContract
  readonly action: GraphLoopResearchCommand
  readonly verifier: GraphLoopResearchVerifier
  /**
   * A content-addressed manifest of schema/grants and declared frozen research
   * inputs. The process entrypoint always supplies it; programmatic callers
   * may omit it only for bounded local engineering fixtures.
   */
  readonly frozenInputs?: CanonicalAtomV2ContentDescriptor
}

export interface GraphLoopResearchJobResult {
  readonly terminal: ResearchJobTerminal
  readonly attempts: number
  readonly frozenInputs: CanonicalAtomV2ContentDescriptor | null
  readonly action: CanonicalAtomV2ContentDescriptor
  /** Null only when the action itself could not produce a valid execution observation. */
  readonly verifier: CanonicalAtomV2ContentDescriptor | null
}

export class GraphLoopResearchJobError extends Data.TaggedError(
  "GraphLoopResearchJobError"
)<{
  readonly reason:
    | "COMMAND_INVALID"
    | "COMMAND_OBSERVATION_FAILED"
    | "COMMAND_OUTPUT_INVALID"
    | "RETRY_CONFIGURATION_INVALID"
    | "STAGING_FAILED"
  readonly detail: string
}> {}

export class GraphLoopResearchProcessRunner extends Context.Tag(
  "hswm/GraphLoopResearchProcessRunner"
)<
  GraphLoopResearchProcessRunner,
  {
    readonly run: (
      request: GraphLoopResearchJobRequest
    ) => Effect.Effect<
      GraphLoopResearchJobResult,
      | GraphLoopControlError
      | GraphLoopControlJournalError
      | GraphLoopResearchJobError
    >
  }
>() {}

interface CommandObservation {
  readonly exitCode: number | null
  readonly signal: string | null
  readonly timedOut: boolean
  readonly outputTruncated: boolean
  readonly launchError: string | null
  readonly stdout: Uint8Array
  readonly stderr: Uint8Array
}

const Identifier = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/
const EnvironmentName = /^[A-Z_][A-Z0-9_]{0,127}$/
const SAFE_INHERITED_ENVIRONMENT = [
  "HOME",
  "LANG",
  "LC_ALL",
  "LOGNAME",
  "PATH",
  "SSL_CERT_DIR",
  "SSL_CERT_FILE",
  "USER"
] as const

const jobError = (
  reason: GraphLoopResearchJobError["reason"],
  detail: string
): GraphLoopResearchJobError => new GraphLoopResearchJobError({ reason, detail })

const sha256 = (bytes: Uint8Array): string =>
  createHash("sha256").update(bytes).digest("hex")

const canonicalBytes = (
  value: unknown,
  reason: GraphLoopResearchJobError["reason"],
  detail: string
): Either.Either<Uint8Array, GraphLoopResearchJobError> => {
  const encoded = canonicalJsonBytes(value as CanonicalJson)
  return Either.isLeft(encoded)
    ? Either.left(jobError(reason, detail))
    : Either.right(Uint8Array.from(encoded.right))
}

const commandHash = (
  command: GraphLoopResearchCommand
): Either.Either<string, GraphLoopResearchJobError> => {
  const encoded = canonicalBytes(
    Object.freeze({
      argv: Object.freeze([...command.argv]),
      cwd: command.cwd,
      timeoutMs: command.timeoutMs,
      environmentKeys: Object.freeze(Object.keys(command.environment ?? {}).sort())
    }),
    "COMMAND_INVALID",
    "research command cannot form a canonical identity"
  )
  return Either.isLeft(encoded)
    ? Either.left(encoded.left)
    : Either.right(sha256(encoded.right))
}

const validExitCodes = (values: ReadonlyArray<number>): boolean =>
  values.length > 0 &&
  values.every((value) => Number.isSafeInteger(value) && value >= 0 && value <= 255) &&
  new Set(values).size === values.length

const validateCommand = (
  command: GraphLoopResearchCommand,
  role: "action" | "verifier"
): Either.Either<void, GraphLoopResearchJobError> => {
  if (
    !Array.isArray(command.argv) ||
    command.argv.length < 1 ||
    command.argv.length > 64 ||
    command.argv.some(
      (argument) =>
        typeof argument !== "string" ||
        argument.length < 1 ||
        argument.length > 16_384 ||
        argument.includes("\u0000")
    ) ||
    typeof command.cwd !== "string" ||
    !isAbsolute(command.cwd) ||
    command.cwd.length > 1_024 ||
    !Number.isSafeInteger(command.timeoutMs) ||
    command.timeoutMs < 1 ||
    command.timeoutMs > HSWM_GRAPH_LOOP_RESEARCH_MAX_TIMEOUT_MS
  ) {
    return Either.left(jobError("COMMAND_INVALID", `${role} command has an unsafe argv, cwd, or timeout`))
  }
  const environment = command.environment ?? {}
  const names = Object.keys(environment)
  if (
    names.length > 64 ||
    names.some((name) => !EnvironmentName.test(name)) ||
    names.some((name) => {
      const value = environment[name]
      return typeof value !== "string" || value.length > 8_192 || value.includes("\u0000")
    })
  ) {
    return Either.left(jobError("COMMAND_INVALID", `${role} command environment is outside the bounded vocabulary`))
  }
  return Either.right(undefined)
}

const childEnvironment = (
  command: GraphLoopResearchCommand,
  additions: Readonly<Record<string, string>>
): NodeJS.ProcessEnv => {
  const result: NodeJS.ProcessEnv = Object.create(null) as NodeJS.ProcessEnv
  for (const name of SAFE_INHERITED_ENVIRONMENT) {
    const value = process.env[name]
    if (value !== undefined) result[name] = value
  }
  for (const [name, value] of Object.entries(command.environment ?? {})) {
    result[name] = value
  }
  for (const [name, value] of Object.entries(additions)) result[name] = value
  return result
}

const observeCommand = async (
  command: GraphLoopResearchCommand,
  additions: Readonly<Record<string, string>>
): Promise<CommandObservation> =>
  new Promise((resolve) => {
    const stdout: Buffer[] = []
    const stderr: Buffer[] = []
    let outputBytes = 0
    let timedOut = false
    let outputTruncated = false
    let launchError: string | null = null
    let completed = false
    let terminating = false
    let timeout: NodeJS.Timeout | undefined
    let forceKill: NodeJS.Timeout | undefined
    const finish = (exitCode: number | null, signal: string | null): void => {
      if (completed) return
      completed = true
      if (timeout !== undefined) clearTimeout(timeout)
      if (forceKill !== undefined) clearTimeout(forceKill)
      resolve(
        Object.freeze({
          exitCode,
          signal,
          timedOut,
          outputTruncated,
          launchError,
          stdout: Uint8Array.from(Buffer.concat(stdout)),
          stderr: Uint8Array.from(Buffer.concat(stderr))
        })
      )
    }
    let child
    try {
      child = spawn(command.argv[0]!, command.argv.slice(1), {
        cwd: command.cwd,
        env: childEnvironment(command, additions),
        shell: false,
        stdio: ["ignore", "pipe", "pipe"]
      })
    } catch (error) {
      launchError = error instanceof Error ? error.name : "SPAWN_FAILED"
      finish(null, null)
      return
    }
    const terminate = (): void => {
      if (terminating) return
      terminating = true
      child.kill("SIGTERM")
      forceKill = setTimeout(() => child.kill("SIGKILL"), 1_000)
      forceKill.unref()
    }
    const append = (chunks: Buffer[], chunk: Buffer): void => {
      const available = HSWM_GRAPH_LOOP_RESEARCH_MAX_OUTPUT_BYTES - outputBytes
      if (available <= 0) {
        outputTruncated = true
        terminate()
        return
      }
      if (chunk.byteLength > available) {
        chunks.push(chunk.subarray(0, available))
        outputBytes += available
        outputTruncated = true
        terminate()
        return
      }
      chunks.push(chunk)
      outputBytes += chunk.byteLength
    }
    child.stdout?.on("data", (chunk: Buffer) => {
      append(stdout, chunk)
    })
    child.stderr?.on("data", (chunk: Buffer) => {
      append(stderr, chunk)
    })
    child.once("error", (error) => {
      launchError = error instanceof Error ? error.name : "SPAWN_FAILED"
      finish(null, null)
    })
    child.once("close", (exitCode, signal) => finish(exitCode, signal))
    timeout = setTimeout(() => {
      timedOut = true
      terminate()
    }, command.timeoutMs)
  })

const stageRecord = (
  view: CanonicalAtomV2DurableGraphView["Type"],
  mediaType: string,
  value: unknown
): Effect.Effect<CanonicalAtomV2ContentDescriptor, GraphLoopResearchJobError> =>
  Effect.gen(function* () {
    const bytes = canonicalBytes(value, "COMMAND_OUTPUT_INVALID", "research command observation is not canonical JSON")
    if (Either.isLeft(bytes)) return yield* bytes.left
    return yield* view.stageContent(mediaType, bytes.right).pipe(
      Effect.mapError(() => jobError("STAGING_FAILED", "research command observation could not be content-addressed"))
    )
  })

const stageObservation = (
  view: CanonicalAtomV2DurableGraphView["Type"],
  runId: string,
  attempt: number,
  role: "ACTION" | "VERIFIER",
  frozenInputs: CanonicalAtomV2ContentDescriptor | null,
  command: GraphLoopResearchCommand,
  observation: CommandObservation
): Effect.Effect<CanonicalAtomV2ContentDescriptor, GraphLoopResearchJobError> =>
  Effect.gen(function* () {
    const hash = commandHash(command)
    if (Either.isLeft(hash)) return yield* hash.left
    const stdout = yield* view.stageContent(
      HSWM_GRAPH_LOOP_RESEARCH_STDOUT_V1_MEDIA_TYPE,
      observation.stdout
    ).pipe(
      Effect.mapError(() => jobError("STAGING_FAILED", "research command stdout could not be content-addressed"))
    )
    const stderr = yield* view.stageContent(
      HSWM_GRAPH_LOOP_RESEARCH_STDERR_V1_MEDIA_TYPE,
      observation.stderr
    ).pipe(
      Effect.mapError(() => jobError("STAGING_FAILED", "research command stderr could not be content-addressed"))
    )
    return yield* stageRecord(
      view,
      role === "ACTION"
        ? HSWM_GRAPH_LOOP_RESEARCH_ACTION_V1_MEDIA_TYPE
        : HSWM_GRAPH_LOOP_RESEARCH_VERIFIER_V1_MEDIA_TYPE,
      Object.freeze({
        _tag: "GraphLoopResearchCommandObservation",
        contractVersion: HSWM_GRAPH_LOOP_RESEARCH_JOB_V1_CONTRACT_VERSION,
        runId,
        attempt,
        role,
        frozenInputs,
        commandSha256: hash.right,
        cwd: command.cwd,
        environmentKeys: Object.freeze(Object.keys(command.environment ?? {}).sort()),
        exitCode: observation.exitCode,
        signal: observation.signal,
        timedOut: observation.timedOut,
        outputTruncated: observation.outputTruncated,
        launchError: observation.launchError,
        stdout,
        stderr
      })
    )
  })

const decisionFor = (
  observation: CommandObservation,
  verifier: GraphLoopResearchVerifier
): ResearchJobDecision | null => {
  if (
    observation.exitCode === null ||
    observation.timedOut ||
    observation.outputTruncated ||
    observation.launchError !== null
  ) return null
  if (verifier.acceptExitCodes.includes(observation.exitCode)) return "ACCEPT"
  if (verifier.retryExitCodes.includes(observation.exitCode)) return "RETRY"
  return "REJECT"
}

const executionInvalid = (observation: CommandObservation): boolean =>
  observation.exitCode === null ||
  observation.timedOut ||
  observation.outputTruncated ||
  observation.launchError !== null

const descriptorEnvironment = (
  prefix: string,
  descriptor: CanonicalAtomV2ContentDescriptor | null
): Readonly<Record<string, string>> =>
  descriptor === null
    ? Object.freeze({})
    : Object.freeze({
        [`${prefix}_MEDIA_TYPE`]: descriptor.mediaType,
        [`${prefix}_BYTE_LENGTH`]: String(descriptor.byteLength),
        [`${prefix}_SHA256`]: descriptor.sha256
      })

const validateRequest = (
  request: GraphLoopResearchJobRequest
): Either.Either<void, GraphLoopResearchJobError> => {
  const action = validateCommand(request.action, "action")
  if (Either.isLeft(action)) return action
  const verifier = validateCommand(request.verifier.command, "verifier")
  if (Either.isLeft(verifier)) return verifier
  if (
    !validExitCodes(request.verifier.acceptExitCodes) ||
    !Array.isArray(request.verifier.retryExitCodes) ||
    !request.verifier.retryExitCodes.every(
      (value) => Number.isSafeInteger(value) && value >= 0 && value <= 255
    ) ||
    new Set(request.verifier.retryExitCodes).size !== request.verifier.retryExitCodes.length ||
    request.verifier.retryExitCodes.some((value) => request.verifier.acceptExitCodes.includes(value))
  ) {
    return Either.left(jobError("RETRY_CONFIGURATION_INVALID", "verifier accept/retry exit-code sets must be bounded, unique, and disjoint"))
  }
  if (
    !Number.isSafeInteger(request.contract.maximumAttempts) ||
    request.contract.maximumAttempts < 1 ||
    !Number.isSafeInteger(request.contract.maximumActions) ||
    request.contract.maximumActions < request.contract.maximumAttempts ||
    !Identifier.test(request.contract.runId)
  ) {
    return Either.left(jobError("RETRY_CONFIGURATION_INVALID", "one research action per attempt requires an identifier and action budget at least as large as attempt budget"))
  }
  return Either.right(undefined)
}

/**
 * Executes declared action/verifier subprocesses under LE-0.  A verifier ID
 * distinct from the actor ID is enforced by `trigger`; its exit-code mapping
 * is a bounded engineering verdict, not a proof of evaluator independence.
 */
export const makeGraphLoopResearchProcessRunnerLayer = Layer.effect(
  GraphLoopResearchProcessRunner,
  Effect.gen(function* () {
    const controller = yield* GraphLoopEngineeringController
    const view = yield* CanonicalAtomV2DurableGraphView
    return GraphLoopResearchProcessRunner.of({
      run: (request) => Effect.gen(function* () {
        const valid = validateRequest(request)
        if (Either.isLeft(valid)) return yield* valid.left
        const frozenInputs = request.frozenInputs ?? null
        if (frozenInputs !== null) {
          yield* view.readContent(frozenInputs).pipe(
            Effect.asVoid,
            Effect.mapError(() => jobError("STAGING_FAILED", "frozen-input manifest is absent or tampered"))
          )
        }
        let attempts = 0
        for (;;) {
          yield* controller.trigger(request.contract)
          attempts += 1
          const actionObservation = yield* Effect.tryPromise({
            try: () => observeCommand(request.action, Object.freeze({
              HSWM_LE0_RUN_ID: request.contract.runId,
              HSWM_LE0_ATTEMPT: String(attempts),
              HSWM_LE0_ROLE: "ACTOR",
              ...descriptorEnvironment("HSWM_LE0_FROZEN_INPUTS", frozenInputs)
            })),
            catch: () => jobError("COMMAND_OBSERVATION_FAILED", "research action observation failed")
          })
          const action = yield* stageObservation(
            view,
            request.contract.runId,
            attempts,
            "ACTION",
            frozenInputs,
            request.action,
            actionObservation
          )
          yield* controller.sealAction(request.contract.runId, action)
          if (executionInvalid(actionObservation)) {
            yield* controller.escalate(
              request.contract.runId,
              "ACTION_EXECUTION_INVALID",
              action
            )
            return Object.freeze({ terminal: "ESCALATED" as const, attempts, frozenInputs, action, verifier: null })
          }

          const verifierObservation = yield* Effect.tryPromise({
            try: () => observeCommand(request.verifier.command, Object.freeze({
              HSWM_LE0_RUN_ID: request.contract.runId,
              HSWM_LE0_ATTEMPT: String(attempts),
              HSWM_LE0_ROLE: "VERIFIER",
              HSWM_LE0_ACTION_MEDIA_TYPE: action.mediaType,
              HSWM_LE0_ACTION_BYTE_LENGTH: String(action.byteLength),
              HSWM_LE0_ACTION_SHA256: action.sha256,
              ...descriptorEnvironment("HSWM_LE0_FROZEN_INPUTS", frozenInputs)
            })),
            catch: () => jobError("COMMAND_OBSERVATION_FAILED", "research verifier observation failed")
          })
          const verifier = yield* stageObservation(
            view,
            request.contract.runId,
            attempts,
            "VERIFIER",
            frozenInputs,
            request.verifier.command,
            verifierObservation
          )
          const decision = decisionFor(verifierObservation, request.verifier)
          if (decision === null) {
            yield* controller.escalate(
              request.contract.runId,
              "VERIFIER_EXECUTION_INVALID",
              verifier
            )
            return Object.freeze({ terminal: "ESCALATED" as const, attempts, frozenInputs, action, verifier })
          }
          yield* controller.recordVerification(request.contract.runId, decision, verifier)
          if (decision === "ACCEPT") {
            yield* controller.stop(
              request.contract.runId,
              "VERIFIED_ACCEPT_NO_GRAPH_DELTA"
            )
            return Object.freeze({ terminal: "STOPPED_ACCEPTED_NO_GRAPH_DELTA" as const, attempts, frozenInputs, action, verifier })
          }
          if (decision === "REJECT") {
            yield* controller.stop(request.contract.runId, "VERIFIER_REJECTED")
            return Object.freeze({ terminal: "STOPPED_REJECTED" as const, attempts, frozenInputs, action, verifier })
          }
          if (attempts >= request.contract.maximumAttempts) {
            yield* controller.escalate(
              request.contract.runId,
              "RETRY_BUDGET_EXHAUSTED",
              verifier
            )
            return Object.freeze({ terminal: "ESCALATED" as const, attempts, frozenInputs, action, verifier })
          }
          yield* controller.scheduleRetry(request.contract.runId, "VERIFIER_RETRY")
        }
      })
    })
  })
)
