import { spawn } from "node:child_process"
import { isAbsolute } from "node:path"

import { Data, Effect, Either } from "effect"

export const S2S_PROCESS_MAX_ARGUMENTS = 16 as const
export const S2S_PROCESS_MAX_ARGUMENT_BYTES = 4_096 as const
export const S2S_PROCESS_MAX_ENVIRONMENT_ENTRIES = 32 as const
export const S2S_PROCESS_MAX_ENVIRONMENT_KEY_BYTES = 256 as const
export const S2S_PROCESS_MAX_ENVIRONMENT_VALUE_BYTES = 4_096 as const
export const S2S_PROCESS_MAX_ENVIRONMENT_BYTES = 128 * 1_024
export const S2S_PROCESS_MAX_PATH_BYTES = 4_096 as const
export const S2S_PROCESS_MAX_STDIN_BYTES = 64 * 1_048_576
export const S2S_PROCESS_MAX_STDOUT_BYTES = 64 * 1_048_576
export const S2S_PROCESS_MAX_STDERR_BYTES = 1_048_576
export const S2S_PROCESS_MAX_TIMEOUT_MILLIS = 21_600_000 as const

export interface S2SBoundedProcessSpec {
  readonly operation: string
  readonly executable: string
  readonly argv0?: string
  readonly arguments: ReadonlyArray<string>
  readonly cwd: string
  readonly environment: Readonly<Record<string, string>>
  readonly stdin: Uint8Array | null
  readonly timeoutMillis: number
  readonly stdoutLimitBytes: number
  readonly stderrLimitBytes: number
}

export interface S2SBoundedProcessResult {
  readonly exitCode: number
  readonly stdout: Uint8Array
  readonly stderr: Uint8Array
  readonly elapsedNanoseconds: number
}

export class S2SBoundedProcessError extends Data.TaggedError(
  "S2SBoundedProcessError"
)<{
  readonly operation: string
  readonly reason:
    | "CHILD_PROCESS_ERROR"
    | "EXIT_STATUS_UNAVAILABLE"
    | "INVALID_SPECIFICATION"
    | "PROCESS_IO_FAILED"
    | "PROCESS_GROUP_LIFECYCLE_FAILED"
    | "REAP_TIMED_OUT"
    | "SPAWN_FAILED"
    | "STDERR_LIMIT_EXCEEDED"
    | "STDIN_DELIVERY_FAILED"
    | "STDOUT_LIMIT_EXCEEDED"
    | "TERMINATED_BY_SIGNAL"
    | "TIMED_OUT"
    | "UNSUPPORTED_PLATFORM"
  readonly exitCode: number | null
  readonly detail: string
}> {}

interface PreparedProcessSpec {
  readonly operation: string
  readonly executable: string
  readonly argv0: string | undefined
  readonly arguments: ReadonlyArray<string>
  readonly cwd: string
  readonly environment: Readonly<Record<string, string>>
  readonly stdin: Uint8Array | null
  readonly timeoutMillis: number
  readonly stdoutLimitBytes: number
  readonly stderrLimitBytes: number
}

const processError = (
  operation: string,
  reason: S2SBoundedProcessError["reason"],
  detail: string,
  exitCode: number | null = null
): S2SBoundedProcessError =>
  new S2SBoundedProcessError({ operation, reason, exitCode, detail })

const isSafePositiveBound = (value: number, maximum: number): boolean =>
  Number.isSafeInteger(value) && value >= 1 && value <= maximum

const isPlainDataRecord = (value: object): boolean => {
  const prototype = Object.getPrototypeOf(value)
  return prototype === Object.prototype || prototype === null
}

const INVALID_DATA_VALUE = Object.freeze({})

const ownEnumerableDataValue = (
  input: object,
  key: string
): unknown | typeof INVALID_DATA_VALUE => {
  const descriptor = Object.getOwnPropertyDescriptor(input, key)
  if (
    descriptor === undefined ||
    !("value" in descriptor) ||
    descriptor.enumerable !== true
  ) {
    return INVALID_DATA_VALUE
  }
  const value: unknown = descriptor.value
  return value
}

const exactSpecKeys = (input: object): boolean => {
  const keys = Reflect.ownKeys(input)
  if (keys.some((key) => typeof key !== "string")) return false
  const stringKeys = keys.filter((key): key is string => typeof key === "string")
  stringKeys.sort()
  const requiredKeys = [
    "arguments",
    "cwd",
    "environment",
    "executable",
    "operation",
    "stderrLimitBytes",
    "stdin",
    "stdoutLimitBytes",
    "timeoutMillis"
  ]
  const expectedKeys = stringKeys.includes("argv0")
    ? [...requiredKeys, "argv0"].sort()
    : requiredKeys
  return (
    stringKeys.length === expectedKeys.length &&
    stringKeys.every((key, index) => key === expectedKeys[index])
  )
}

const snapshotArguments = (
  operation: string,
  input: unknown
): Either.Either<ReadonlyArray<string>, S2SBoundedProcessError> => {
  if (!Array.isArray(input) || Object.getPrototypeOf(input) !== Array.prototype) {
    return Either.left(
      processError(
        operation,
        "INVALID_SPECIFICATION",
        "arguments must be a plain dense data array"
      )
    )
  }
  const lengthDescriptor = Object.getOwnPropertyDescriptor(input, "length")
  const lengthValue: unknown = lengthDescriptor?.value
  if (
    lengthDescriptor === undefined ||
    !("value" in lengthDescriptor) ||
    !Number.isSafeInteger(lengthValue) ||
    typeof lengthValue !== "number" ||
    lengthValue < 0 ||
    lengthValue > S2S_PROCESS_MAX_ARGUMENTS
  ) {
    return Either.left(
      processError(
        operation,
        "INVALID_SPECIFICATION",
        "argument roster exceeds the fixed contract"
      )
    )
  }
  const ownKeys = Reflect.ownKeys(input)
  if (
    ownKeys.length !== lengthValue + 1 ||
    ownKeys.some(
      (key) =>
        typeof key !== "string" ||
        (key !== "length" && !/^(0|[1-9][0-9]*)$/.test(key))
    )
  ) {
    return Either.left(
      processError(
        operation,
        "INVALID_SPECIFICATION",
        "arguments must not contain holes, accessors, symbols, or extra keys"
      )
    )
  }
  const output: Array<string> = []
  for (let index = 0; index < lengthValue; index += 1) {
    const value = ownEnumerableDataValue(input, String(index))
    if (
      typeof value !== "string" ||
      value.includes("\0") ||
      Buffer.byteLength(value, "utf8") > S2S_PROCESS_MAX_ARGUMENT_BYTES
    ) {
      return Either.left(
        processError(
          operation,
          "INVALID_SPECIFICATION",
          "arguments contain a non-data or out-of-bound value"
        )
      )
    }
    output.push(value)
  }
  return Either.right(Object.freeze(output))
}

const snapshotStdin = (
  operation: string,
  input: unknown
): Either.Either<Uint8Array | null, S2SBoundedProcessError> => {
  if (input === null) return Either.right(null)
  if (
    !(input instanceof Uint8Array) ||
    Object.getPrototypeOf(input) !== Uint8Array.prototype ||
    Object.getOwnPropertySymbols(input).length !== 0 ||
    Object.getOwnPropertyDescriptor(input, "byteLength") !== undefined ||
    Object.getOwnPropertyDescriptor(input, "buffer") !== undefined ||
    input.byteLength > S2S_PROCESS_MAX_STDIN_BYTES ||
    (typeof SharedArrayBuffer !== "undefined" &&
      input.buffer instanceof SharedArrayBuffer)
  ) {
    return Either.left(
      processError(
        operation,
        "INVALID_SPECIFICATION",
        "stdin must be one bounded, unshared plain Uint8Array"
      )
    )
  }
  return Either.right(new Uint8Array(input))
}

const snapshotEnvironment = (
  operation: string,
  input: unknown
): Either.Either<Readonly<Record<string, string>>, S2SBoundedProcessError> => {
  if (input === null || typeof input !== "object" || !isPlainDataRecord(input)) {
    return Either.left(
      processError(
        operation,
        "INVALID_SPECIFICATION",
        "environment must be a plain data record"
      )
    )
  }
  const keys = Reflect.ownKeys(input)
  if (
    keys.length > S2S_PROCESS_MAX_ENVIRONMENT_ENTRIES ||
    keys.some((key) => typeof key !== "string")
  ) {
    return Either.left(
      processError(
        operation,
        "INVALID_SPECIFICATION",
        "environment key roster exceeds the fixed contract"
      )
    )
  }
  const output: Record<string, string> = Object.create(null)
  const stringKeys = keys.filter((key): key is string => typeof key === "string")
  stringKeys.sort()
  let aggregateBytes = 0
  for (const key of stringKeys) {
    const descriptor = Object.getOwnPropertyDescriptor(input, key)
    if (
      descriptor === undefined ||
      !("value" in descriptor) ||
      descriptor.enumerable !== true ||
      typeof descriptor.value !== "string" ||
      !/^[A-Z_][A-Z0-9_]*$/.test(key) ||
      Buffer.byteLength(key, "utf8") >
        S2S_PROCESS_MAX_ENVIRONMENT_KEY_BYTES ||
      descriptor.value.includes("\0") ||
      Buffer.byteLength(descriptor.value, "utf8") >
        S2S_PROCESS_MAX_ENVIRONMENT_VALUE_BYTES
    ) {
      return Either.left(
        processError(
          operation,
          "INVALID_SPECIFICATION",
          "environment contains a non-data or out-of-bound entry"
        )
      )
    }
    aggregateBytes +=
      Buffer.byteLength(key, "utf8") +
      1 +
      Buffer.byteLength(descriptor.value, "utf8") +
      1
    if (aggregateBytes > S2S_PROCESS_MAX_ENVIRONMENT_BYTES) {
      return Either.left(
        processError(
          operation,
          "INVALID_SPECIFICATION",
          "environment exceeds the fixed aggregate byte bound"
        )
      )
    }
    output[key] = descriptor.value
  }
  return Either.right(Object.freeze(output))
}

const prepareSpec = (
  input: S2SBoundedProcessSpec
): Either.Either<PreparedProcessSpec, S2SBoundedProcessError> => {
  const fallbackOperation = "INVALID_PROCESS_SPECIFICATION"
  if (!isPlainDataRecord(input) || !exactSpecKeys(input)) {
    return Either.left(
      processError(
        fallbackOperation,
        "INVALID_SPECIFICATION",
        "process specification must be one exact plain data record"
      )
    )
  }
  const operationValue = ownEnumerableDataValue(input, "operation")
  const operation =
    typeof operationValue === "string" ? operationValue : fallbackOperation
  const executable = ownEnumerableDataValue(input, "executable")
  const hasArgv0 = Object.hasOwn(input, "argv0")
  const argv0 = hasArgv0
    ? ownEnumerableDataValue(input, "argv0")
    : undefined
  const argumentsValue = ownEnumerableDataValue(input, "arguments")
  const cwd = ownEnumerableDataValue(input, "cwd")
  const environmentValue = ownEnumerableDataValue(input, "environment")
  const stdinValue = ownEnumerableDataValue(input, "stdin")
  const timeoutMillis = ownEnumerableDataValue(input, "timeoutMillis")
  const stdoutLimitBytes = ownEnumerableDataValue(input, "stdoutLimitBytes")
  const stderrLimitBytes = ownEnumerableDataValue(input, "stderrLimitBytes")
  if (
    !/^[A-Z][A-Z0-9_]{0,63}$/.test(operation) ||
    typeof executable !== "string" ||
    !isAbsolute(executable) ||
    executable.includes("\0") ||
    Buffer.byteLength(executable, "utf8") > S2S_PROCESS_MAX_PATH_BYTES ||
    (hasArgv0 &&
      (typeof argv0 !== "string" ||
        argv0.length === 0 ||
        argv0.includes("\0") ||
        Buffer.byteLength(argv0, "utf8") >
          S2S_PROCESS_MAX_ARGUMENT_BYTES)) ||
    typeof cwd !== "string" ||
    !isAbsolute(cwd) ||
    cwd.includes("\0") ||
    Buffer.byteLength(cwd, "utf8") > S2S_PROCESS_MAX_PATH_BYTES ||
    typeof timeoutMillis !== "number" ||
    !isSafePositiveBound(timeoutMillis, S2S_PROCESS_MAX_TIMEOUT_MILLIS) ||
    typeof stdoutLimitBytes !== "number" ||
    !isSafePositiveBound(stdoutLimitBytes, S2S_PROCESS_MAX_STDOUT_BYTES) ||
    typeof stderrLimitBytes !== "number" ||
    !isSafePositiveBound(stderrLimitBytes, S2S_PROCESS_MAX_STDERR_BYTES)
  ) {
    return Either.left(
      processError(
        operation,
        "INVALID_SPECIFICATION",
        "process specification violates a fixed bound"
      )
    )
  }
  const arguments_ = snapshotArguments(operation, argumentsValue)
  if (Either.isLeft(arguments_)) return Either.left(arguments_.left)
  const environment = snapshotEnvironment(operation, environmentValue)
  if (Either.isLeft(environment)) return Either.left(environment.left)
  const stdin = snapshotStdin(operation, stdinValue)
  if (Either.isLeft(stdin)) return Either.left(stdin.left)
  const preparedArgv0 = typeof argv0 === "string" ? argv0 : undefined
  return Either.right(
    Object.freeze({
      operation,
      executable,
      argv0: preparedArgv0,
      arguments: arguments_.right,
      cwd,
      environment: environment.right,
      stdin: stdin.right,
      timeoutMillis,
      stdoutLimitBytes,
      stderrLimitBytes
    })
  )
}

const errorCode = (error: unknown): string | null => {
  if (error === null || typeof error !== "object") return null
  const descriptor = Object.getOwnPropertyDescriptor(error, "code")
  if (descriptor === undefined || !("value" in descriptor)) return null
  const value: unknown = descriptor.value
  return typeof value === "string" ? value : null
}

const lifecycleError = (
  operation: string,
  action: string,
  error: unknown
): S2SBoundedProcessError =>
  processError(
    operation,
    "PROCESS_GROUP_LIFECYCLE_FAILED",
    `${action} failed with ${errorCode(error) ?? "UNKNOWN_ERROR"}`
  )

const killProcessGroup = (
  operation: string,
  child: ReturnType<typeof spawn>
): S2SBoundedProcessError | null => {
  const childPid = child.pid
  if (childPid === undefined) return null
  try {
    process.kill(-childPid, "SIGKILL")
    return null
  } catch (error) {
    if (errorCode(error) !== "ESRCH") {
      return lifecycleError(operation, "signalling the detached process group", error)
    }
  }
  // ESRCH means that the detached group is already absent. A direct-child
  // fallback covers the narrow pre-group race without masking other failures.
  if (child.exitCode !== null || child.signalCode !== null) return null
  try {
    if (child.kill("SIGKILL")) return null
    if (child.exitCode !== null || child.signalCode !== null) return null
    return processError(
      operation,
      "PROCESS_GROUP_LIFECYCLE_FAILED",
      "direct-child SIGKILL was not accepted"
    )
  } catch (error) {
    if (errorCode(error) === "ESRCH") return null
    return lifecycleError(operation, "signalling the direct child", error)
  }
}

type ProcessGroupObservation =
  | { readonly kind: "ABSENT" }
  | { readonly kind: "PRESENT" }
  | {
      readonly kind: "FAILED"
      readonly error: S2SBoundedProcessError
    }

const observeProcessGroup = (
  operation: string,
  processGroupId: number | undefined
): ProcessGroupObservation => {
  if (processGroupId === undefined) return { kind: "ABSENT" }
  try {
    process.kill(-processGroupId, 0)
    return { kind: "PRESENT" }
  } catch (error) {
    if (errorCode(error) === "ESRCH") return { kind: "ABSENT" }
    return {
      kind: "FAILED",
      error: lifecycleError(
        operation,
        "observing the detached process group",
        error
      )
    }
  }
}

const collectProcess = (
  spec: PreparedProcessSpec
): Effect.Effect<S2SBoundedProcessResult, S2SBoundedProcessError> =>
  Effect.async<S2SBoundedProcessResult, S2SBoundedProcessError>((resume) => {
    const started = process.hrtime.bigint()
    let settled = false
    let closed = false
    let spawned = false
    let terminationRequested = false
    let pendingFailure: S2SBoundedProcessError | null = null
    let deadlineTimer: ReturnType<typeof setTimeout> | null = null
    let reapTimer: ReturnType<typeof setTimeout> | null = null
    let groupPollTimer: ReturnType<typeof setTimeout> | null = null
    let stdoutSize = 0
    let stderrSize = 0
    const stdout: Array<Buffer> = []
    const stderr: Array<Buffer> = []
    let child: ReturnType<typeof spawn>
    try {
      child = spawn(spec.executable, spec.arguments, {
        ...(spec.argv0 === undefined ? {} : { argv0: spec.argv0 }),
        cwd: spec.cwd,
        detached: true,
        env: spec.environment,
        shell: false,
        stdio: [spec.stdin === null ? "ignore" : "pipe", "pipe", "pipe"]
      })
    } catch {
      resume(
        Effect.fail(
          processError(
            spec.operation,
            "SPAWN_FAILED",
            "child process spawn threw synchronously"
          )
        )
      )
      return
    }

    const finish = (
      effect: Effect.Effect<S2SBoundedProcessResult, S2SBoundedProcessError>
    ): void => {
      if (settled) return
      settled = true
      if (deadlineTimer !== null) clearTimeout(deadlineTimer)
      if (reapTimer !== null) clearTimeout(reapTimer)
      if (groupPollTimer !== null) clearTimeout(groupPollTimer)
      resume(effect)
    }

    const markFailure = (error: S2SBoundedProcessError): void => {
      if (settled) return
      if (pendingFailure === null) {
        pendingFailure = error
        stdout.length = 0
        stderr.length = 0
      }
      if (!terminationRequested) {
        terminationRequested = true
        const terminationFailure = killProcessGroup(spec.operation, child)
        if (terminationFailure !== null) pendingFailure = terminationFailure
      }
      if (reapTimer === null) {
        reapTimer = setTimeout(() => {
          if (settled || closed) return
          finish(
            Effect.fail(
              processError(
                spec.operation,
                "REAP_TIMED_OUT",
                `child did not close after ${pendingFailure?.reason ?? "failure"}`
              )
            )
          )
        }, 5_000)
      }
    }

    child.once("spawn", () => {
      spawned = true
    })
    child.on("error", () => {
      markFailure(
        processError(
          spec.operation,
          spawned ? "CHILD_PROCESS_ERROR" : "SPAWN_FAILED",
          spawned
            ? "spawned child emitted a process error"
            : "child process could not be spawned"
        )
      )
    })
    const childStdout = child.stdout
    const childStderr = child.stderr
    if (childStdout === null || childStderr === null) {
      markFailure(
        processError(
          spec.operation,
          "PROCESS_IO_FAILED",
          "child output pipes were not created"
        )
      )
    } else {
      childStdout.on("error", () => {
        markFailure(
          processError(
            spec.operation,
            "PROCESS_IO_FAILED",
            "child stdout stream emitted an error"
          )
        )
      })
      childStderr.on("error", () => {
        markFailure(
          processError(
            spec.operation,
            "PROCESS_IO_FAILED",
            "child stderr stream emitted an error"
          )
        )
      })
      childStdout.on("data", (chunk: Buffer) => {
        if (settled || pendingFailure !== null) return
        stdoutSize += chunk.byteLength
        if (stdoutSize > spec.stdoutLimitBytes) {
          markFailure(
            processError(
              spec.operation,
              "STDOUT_LIMIT_EXCEEDED",
              "child stdout exceeded the fixed byte bound"
            )
          )
          return
        }
        stdout.push(Buffer.from(chunk))
      })
      childStderr.on("data", (chunk: Buffer) => {
        if (settled || pendingFailure !== null) return
        stderrSize += chunk.byteLength
        if (stderrSize > spec.stderrLimitBytes) {
          markFailure(
            processError(
              spec.operation,
              "STDERR_LIMIT_EXCEEDED",
              "child stderr exceeded the fixed byte bound"
            )
          )
          return
        }
        stderr.push(Buffer.from(chunk))
      })
    }
    let stdinFinished = spec.stdin === null || spec.stdin.byteLength === 0
    if (child.stdin !== null) {
      child.stdin.once("finish", () => {
        stdinFinished = true
      })
      child.stdin.once("error", () => {
        if (
          !spawned ||
          spec.stdin === null ||
          spec.stdin.byteLength === 0 ||
          stdinFinished
        ) {
          return
        }
        markFailure(
          processError(
            spec.operation,
            "STDIN_DELIVERY_FAILED",
            "nonempty stdin was not fully accepted by the child pipe"
          )
        )
      })
    }
    const finishFromClose = (
      code: number | null,
      signal: NodeJS.Signals | null
    ): void => {
      if (pendingFailure !== null) {
        finish(Effect.fail(pendingFailure))
        return
      }
      if (!stdinFinished) {
        finish(
          Effect.fail(
            processError(
              spec.operation,
              "STDIN_DELIVERY_FAILED",
              "child closed before nonempty stdin was fully accepted"
            )
          )
        )
        return
      }
      if (code === null) {
        finish(
          Effect.fail(
            processError(
              spec.operation,
              signal === null
                ? "EXIT_STATUS_UNAVAILABLE"
                : "TERMINATED_BY_SIGNAL",
              signal === null
                ? "child closed without exit status or signal"
                : `child terminated by ${signal}`
            )
          )
        )
        return
      }
      const elapsed = process.hrtime.bigint() - started
      const elapsedNanoseconds = Number(elapsed)
      if (!Number.isSafeInteger(elapsedNanoseconds)) {
        finish(
          Effect.fail(
            processError(
              spec.operation,
              "EXIT_STATUS_UNAVAILABLE",
              "child elapsed time exceeded safe integer telemetry"
            )
          )
        )
        return
      }
      finish(
        Effect.succeed(
          Object.freeze({
            exitCode: code,
            stdout: new Uint8Array(Buffer.concat(stdout)),
            stderr: new Uint8Array(Buffer.concat(stderr)),
            elapsedNanoseconds
          })
        )
      )
    }
    child.once("close", (code, signal) => {
      closed = true
      if (deadlineTimer !== null) clearTimeout(deadlineTimer)
      if (reapTimer !== null) clearTimeout(reapTimer)
      if (settled) return
      const terminationFailure = killProcessGroup(spec.operation, child)
      if (terminationFailure !== null) pendingFailure = terminationFailure
      let checksRemaining = 500
      const observeTermination = (): void => {
        if (settled) return
        const observation = observeProcessGroup(spec.operation, child.pid)
        if (observation.kind === "FAILED") {
          finish(Effect.fail(observation.error))
          return
        }
        if (observation.kind === "ABSENT") {
          finishFromClose(code, signal)
          return
        }
        if (checksRemaining === 0) {
          finish(
            Effect.fail(
              processError(
                spec.operation,
                "REAP_TIMED_OUT",
                "process group remained live after child close"
              )
            )
          )
          return
        }
        checksRemaining -= 1
        groupPollTimer = setTimeout(observeTermination, 10)
      }
      observeTermination()
    })
    deadlineTimer = setTimeout(() => {
      if (settled || closed) return
      markFailure(
        processError(
          spec.operation,
          "TIMED_OUT",
          "child exceeded the fixed wall-clock deadline"
        )
      )
    }, spec.timeoutMillis)
    if (child.stdin !== null && spec.stdin !== null) {
      try {
        child.stdin.end(Buffer.from(spec.stdin))
      } catch {
        markFailure(
          processError(
            spec.operation,
            "STDIN_DELIVERY_FAILED",
            "writing child stdin threw synchronously"
          )
        )
      }
    }

    return Effect.async<void>((cleanupResume) => {
      if (settled) {
        cleanupResume(Effect.void)
        return
      }
      let cleanupSettled = false
      const finishCleanup = (effect: Effect.Effect<void>): void => {
        if (cleanupSettled) return
        cleanupSettled = true
        cleanupResume(effect)
      }
      settled = true
      if (deadlineTimer !== null) clearTimeout(deadlineTimer)
      if (reapTimer !== null) clearTimeout(reapTimer)
      if (groupPollTimer !== null) clearTimeout(groupPollTimer)
      const terminationFailure = killProcessGroup(spec.operation, child)
      if (terminationFailure !== null) {
        finishCleanup(Effect.die(terminationFailure))
        return
      }
      let cleanupClosed = closed
      let cleanupChecksRemaining = 500
      if (!cleanupClosed) {
        child.once("close", () => {
          cleanupClosed = true
          const closeTerminationFailure = killProcessGroup(spec.operation, child)
          if (closeTerminationFailure !== null) {
            finishCleanup(Effect.die(closeTerminationFailure))
          }
        })
      }
      const observeCleanup = (): void => {
        if (cleanupSettled) return
        const observation = observeProcessGroup(spec.operation, child.pid)
        if (observation.kind === "FAILED") {
          finishCleanup(Effect.die(observation.error))
          return
        }
        if (cleanupClosed && observation.kind === "ABSENT") {
          finishCleanup(Effect.void)
          return
        }
        if (cleanupChecksRemaining === 0) {
          finishCleanup(
            Effect.die(
              processError(
                spec.operation,
                "REAP_TIMED_OUT",
                "interruption cleanup could not prove process-group termination"
              )
            )
          )
          return
        }
        cleanupChecksRemaining -= 1
        setTimeout(observeCleanup, 10)
      }
      observeCleanup()
    })
  })

export const runS2SBoundedProcess = (
  input: S2SBoundedProcessSpec
): Effect.Effect<S2SBoundedProcessResult, S2SBoundedProcessError> => {
  const prepared = prepareSpec(input)
  if (Either.isLeft(prepared)) return Effect.fail(prepared.left)
  if (process.platform !== "linux") {
    return Effect.fail(
      processError(
        prepared.right.operation,
        "UNSUPPORTED_PLATFORM",
        "bounded process groups are frozen to Linux"
      )
    )
  }
  return collectProcess(prepared.right)
}
