/**
 * Bounded subprocess adapter for the HSWM Effect runtime.
 *
 * Split from effect-posix-services.ts so that files inside the DNRD-5 static
 * source closure can import the POSIX filesystem service without pulling
 * node:child_process into the judged closure.  The observation contract is
 * unchanged: one Effect.async around spawn, SIGTERM then SIGKILL on timeout,
 * output truncation at the declared byte bound.
 */
import { spawn } from "node:child_process"

import { Context, Data, Effect, Layer } from "effect"

export const HSWM_EFFECT_BOUNDED_SUBPROCESS_V1 = "hswm-effect-bounded-subprocess/v1" as const

export interface SubprocessCommand {
  readonly argv: ReadonlyArray<string>
  readonly cwd: string
  readonly environment: Readonly<Record<string, string>>
  readonly timeoutMs: number
  readonly maximumOutputBytes: number
  readonly stdin?: Uint8Array
}

export interface SubprocessObservation {
  readonly exitCode: number | null
  readonly signal: string | null
  readonly timedOut: boolean
  readonly outputTruncated: boolean
  readonly launchError: string | null
  readonly stdout: Uint8Array
  readonly stderr: Uint8Array
}

export class SubprocessError extends Data.TaggedError("SubprocessError")<{
  readonly code: "COMMAND_INVALID" | "SPAWN_FAILED"
  readonly detail: string
}> {}

export interface BoundedSubprocessShape {
  /** Spawn without a shell, bound output bytes and wall time, and always reap the child. */
  readonly observe: (command: SubprocessCommand) => Effect.Effect<SubprocessObservation, SubprocessError>
}

export class BoundedSubprocess extends Context.Tag("hswm/BoundedSubprocess")<BoundedSubprocess, BoundedSubprocessShape>() {}

const observeWithNode = (command: SubprocessCommand): Effect.Effect<SubprocessObservation, SubprocessError> =>
  Effect.async<SubprocessObservation, SubprocessError>((resume) => {
    const stdout: Array<Buffer> = []
    const stderr: Array<Buffer> = []
    const progress = { outputBytes: 0, timedOut: false, outputTruncated: false, completed: false, terminating: false }
    let timeout: NodeJS.Timeout | undefined
    let forceKill: NodeJS.Timeout | undefined
    const finish = (exitCode: number | null, signal: string | null, launchError: string | null): void => {
      if (progress.completed) return
      progress.completed = true
      if (timeout !== undefined) clearTimeout(timeout)
      if (forceKill !== undefined) clearTimeout(forceKill)
      resume(Effect.succeed(Object.freeze({
        exitCode, signal, timedOut: progress.timedOut, outputTruncated: progress.outputTruncated, launchError,
        stdout: Uint8Array.from(Buffer.concat(stdout)), stderr: Uint8Array.from(Buffer.concat(stderr))
      })))
    }
    const [executable, ...rest] = command.argv
    if (executable === undefined) {
      resume(Effect.fail(new SubprocessError({ code: "COMMAND_INVALID", detail: "argv must name an executable" })))
      return
    }
    let child: ReturnType<typeof spawn>
    try {
      child = spawn(executable, rest, {
        cwd: command.cwd, env: command.environment, shell: false,
        stdio: [command.stdin === undefined ? "ignore" : "pipe", "pipe", "pipe"]
      })
    } catch (cause) {
      finish(null, null, cause instanceof Error ? cause.name : "SPAWN_FAILED")
      return
    }
    const terminate = (): void => {
      if (progress.terminating) return
      progress.terminating = true
      child.kill("SIGTERM")
      forceKill = setTimeout(() => child.kill("SIGKILL"), 1_000)
      forceKill.unref()
    }
    const append = (chunks: Array<Buffer>, chunk: Buffer): void => {
      const available = command.maximumOutputBytes - progress.outputBytes
      if (available <= 0) { progress.outputTruncated = true; terminate(); return }
      if (chunk.byteLength > available) {
        chunks.push(chunk.subarray(0, available)); progress.outputBytes += available; progress.outputTruncated = true; terminate(); return
      }
      chunks.push(chunk); progress.outputBytes += chunk.byteLength
    }
    child.on("error", (cause) => finish(null, null, cause instanceof Error ? cause.name : "SPAWN_FAILED"))
    child.stdout?.on("data", (chunk: Buffer) => append(stdout, chunk))
    child.stderr?.on("data", (chunk: Buffer) => append(stderr, chunk))
    child.on("close", (code, signal) => finish(code, signal, null))
    timeout = setTimeout(() => { progress.timedOut = true; terminate() }, command.timeoutMs)
    timeout.unref()
    if (command.stdin !== undefined && child.stdin !== null) {
      child.stdin.on("error", () => undefined)
      child.stdin.end(Buffer.from(command.stdin))
    }
    return Effect.sync(() => { if (!progress.completed) terminate() })
  })

const nodeBoundedSubprocess: BoundedSubprocessShape = {
    observe: (command) => {
      if (
        !Number.isSafeInteger(command.timeoutMs) || command.timeoutMs < 1 ||
        !Number.isSafeInteger(command.maximumOutputBytes) || command.maximumOutputBytes < 1 ||
        command.argv.length < 1
      ) {
        return Effect.fail(new SubprocessError({ code: "COMMAND_INVALID", detail: "subprocess command bounds are invalid" }))
      }
      return observeWithNode(command)
    }
}

export const NodeBoundedSubprocessLive: Layer.Layer<BoundedSubprocess> = Layer.succeed(BoundedSubprocess, Object.freeze(nodeBoundedSubprocess))
