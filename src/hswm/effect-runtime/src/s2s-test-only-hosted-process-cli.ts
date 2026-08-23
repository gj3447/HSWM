import { pathToFileURL } from "node:url"

import { Cause, Effect, Exit } from "effect"

import {
  S2S_TEST_ONLY_HOSTED_PROCESS_CLASSIFICATION,
  s2sTestOnlyHostedProcessAttemptStageJobMatches
} from "./s2s-test-only-hosted-process-protocol.js"
import {
  awaitS2STestOnlyHostedProcessReady,
  reconcileS2STestOnlyHostedProcess,
  runS2STestOnlyHostedProcessRoot
} from "./s2s-test-only-hosted-process-root.js"

type Command = "root" | "await-ready" | "reconcile"

interface ParsedArguments {
  readonly command: Command
  readonly seed: {
    readonly classification: typeof S2S_TEST_ONLY_HOSTED_PROCESS_CLASSIFICATION
    readonly runnerTempPath: string
    readonly sessionName: string
    readonly workflowRunId: number
    readonly workflowRunAttempt: 1
    readonly feasibilityAttempt: 1 | 2 | 3
    readonly stage: "REGISTER" | "CONFIRM" | "ADJUDICATE"
    readonly jobId: "register" | "confirm" | "adjudicate"
  }
  readonly outcome: "success" | "failure" | "cancelled" | "skipped" | "unknown" | null
}

const OPTIONS = Object.freeze([
  "--runner-temp",
  "--session",
  "--workflow-run-id",
  "--workflow-run-attempt",
  "--feasibility-attempt",
  "--stage",
  "--job-id"
] as const)

const parsePositiveSafeInteger = (value: string, name: string): number => {
  if (!/^[1-9][0-9]*$/.test(value)) {
    throw new Error(`${name} must be a positive decimal integer`)
  }
  const parsed = Number(value)
  if (!Number.isSafeInteger(parsed)) {
    throw new Error(`${name} exceeds the safe-integer range`)
  }
  return parsed
}

const parseArguments = (argv: ReadonlyArray<string>): ParsedArguments => {
  const command = argv[0]
  if (
    command !== "root" &&
    command !== "await-ready" &&
    command !== "reconcile"
  ) {
    throw new Error("command must be root, await-ready, or reconcile")
  }
  const values = new Map<string, string>()
  for (let index = 1; index < argv.length; index += 2) {
    const key = argv[index]
    const value = argv[index + 1]
    if (
      key === undefined ||
      value === undefined ||
      !key.startsWith("--") ||
      values.has(key)
    ) {
      throw new Error("CLI options must be unique key/value pairs")
    }
    values.set(key, value)
  }
  const expected =
    command === "reconcile"
      ? Object.freeze([...OPTIONS, "--outcome"])
      : OPTIONS
  if (
    values.size !== expected.length ||
    expected.some((key) => !values.has(key)) ||
    [...values.keys()].some((key) => !expected.includes(key))
  ) {
    throw new Error("CLI options are missing or excess")
  }
  const get = (key: string): string => {
    const value = values.get(key)
    if (value === undefined) throw new Error(`missing ${key}`)
    return value
  }
  const workflowRunId = parsePositiveSafeInteger(
    get("--workflow-run-id"),
    "workflow run ID"
  )
  const workflowRunAttempt = parsePositiveSafeInteger(
    get("--workflow-run-attempt"),
    "workflow run attempt"
  )
  const feasibilityAttempt = parsePositiveSafeInteger(
    get("--feasibility-attempt"),
    "feasibility attempt"
  )
  const stage = get("--stage")
  const jobId = get("--job-id")
  const outcome = command === "reconcile" ? get("--outcome") : null
  if (workflowRunAttempt !== 1) {
    throw new Error("workflow run attempt is fixed at one")
  }
  if (
    feasibilityAttempt !== 1 &&
    feasibilityAttempt !== 2 &&
    feasibilityAttempt !== 3
  ) {
    throw new Error("feasibility attempt must be one, two, or three")
  }
  if (stage !== "REGISTER" && stage !== "CONFIRM" && stage !== "ADJUDICATE") {
    throw new Error("stage is invalid")
  }
  if (jobId !== "register" && jobId !== "confirm" && jobId !== "adjudicate") {
    throw new Error("job ID is invalid")
  }
  if (
    !s2sTestOnlyHostedProcessAttemptStageJobMatches(
      feasibilityAttempt,
      stage,
      jobId
    )
  ) {
    throw new Error("attempt, stage, and job ID are not the fixed sequence")
  }
  if (
    outcome !== null &&
    outcome !== "success" &&
    outcome !== "failure" &&
    outcome !== "cancelled" &&
    outcome !== "skipped" &&
    outcome !== "unknown"
  ) {
    throw new Error("outcome diagnostic is invalid")
  }
  return Object.freeze({
    command,
    seed: Object.freeze({
      classification: S2S_TEST_ONLY_HOSTED_PROCESS_CLASSIFICATION,
      runnerTempPath: get("--runner-temp"),
      sessionName: get("--session"),
      workflowRunId,
      workflowRunAttempt,
      feasibilityAttempt,
      stage,
      jobId
    }),
    outcome
  })
}

const safeSummary = (value: Readonly<Record<string, string | number | boolean>>): void => {
  process.stdout.write(`${JSON.stringify(value)}\n`)
}

export const runS2STestOnlyHostedProcessCli = async (
  argv: ReadonlyArray<string>
): Promise<number> => {
  let parsed: ParsedArguments
  try {
    parsed = parseArguments(argv)
  } catch (error: unknown) {
    const detail = error instanceof Error ? error.message : "invalid arguments"
    process.stderr.write(`S2S_TEST_ONLY_HOSTED_PROCESS_INPUT_REJECTED: ${detail}\n`)
    return 2
  }
  const controller = new AbortController()
  const interrupt = (): void => controller.abort()
  if (parsed.command === "root") {
    process.once("SIGINT", interrupt)
    process.once("SIGTERM", interrupt)
  }
  const program =
    parsed.command === "root"
      ? runS2STestOnlyHostedProcessRoot(parsed.seed).pipe(
          Effect.tap((terminal) =>
            Effect.sync(() =>
              safeSummary({
                classification: terminal.classification,
                command: "root",
                rootPid: terminal.binding.runtimeIdentity.rootPid,
                terminalStatus: terminal.terminalStatus,
                publicationRetryCount: terminal.publicationRetryCount
              })
            )
          ),
          Effect.asVoid
        )
      : parsed.command === "await-ready"
        ? awaitS2STestOnlyHostedProcessReady(parsed.seed).pipe(
            Effect.tap((observation) =>
              Effect.sync(() =>
                safeSummary({
                  classification: observation.ready.classification,
                  command: "await-ready",
                  rootPid: observation.ready.binding.runtimeIdentity.rootPid,
                  feasibilityAttempt:
                    observation.ready.binding.feasibilityAttempt,
                  readyFrameSha256: observation.readyFrameSha256
                })
              )
            ),
            Effect.asVoid
          )
        : reconcileS2STestOnlyHostedProcess(
            parsed.seed,
            parsed.outcome
          ).pipe(
            Effect.tap((observation) =>
              Effect.sync(() =>
                safeSummary({
                  classification: observation.terminal.classification,
                  command: "reconcile",
                  rootPid:
                    observation.terminal.binding.runtimeIdentity.rootPid,
                  terminalStatus: observation.terminal.terminalStatus,
                  terminalFrameSha256: observation.terminalFrameSha256,
                  productionCompletionClaimed:
                    observation.terminal.productionCompletionClaimed
                })
              )
            ),
            Effect.asVoid
          )
  const exit = await Effect.runPromiseExit(program, {
    signal: controller.signal
  })
  process.removeListener("SIGINT", interrupt)
  process.removeListener("SIGTERM", interrupt)
  if (Exit.isSuccess(exit)) return 0
  process.stderr.write(
    `S2S_TEST_ONLY_HOSTED_PROCESS_FAILED: ${Cause.pretty(exit.cause)}\n`
  )
  return 1
}

const invokedPath = process.argv[1]
if (
  invokedPath !== undefined &&
  import.meta.url === pathToFileURL(invokedPath).href
) {
  void runS2STestOnlyHostedProcessCli(process.argv.slice(2)).then((exitCode) => {
    process.exitCode = exitCode
  })
}

export { parseArguments as parseS2STestOnlyHostedProcessCliArguments }
