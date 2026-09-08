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
  /** Isolate and terminate the whole POSIX process group for effectful tool cells. */
  readonly killProcessGroup?: boolean
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
    let groupProbe: NodeJS.Timeout | undefined
    let pendingFinish: readonly [number | null, string | null, string | null] | undefined
    const terminationWaiters: Array<() => void> = []
    const complete = (exitCode: number | null, signal: string | null, launchError: string | null): void => {
      if (progress.completed) return
      progress.completed = true
      if (timeout !== undefined) clearTimeout(timeout)
      if (forceKill !== undefined) clearTimeout(forceKill)
      if (groupProbe !== undefined) clearTimeout(groupProbe)
      for (const waiter of terminationWaiters) waiter()
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
        stdio: [command.stdin === undefined ? "ignore" : "pipe", "pipe", "pipe"],
        detached: command.killProcessGroup === true
      })
    } catch (cause) {
      complete(null, null, cause instanceof Error ? cause.name : "SPAWN_FAILED")
      return
    }
    const groupIsLive = (): boolean => {
      if (child.pid === undefined) return false
      try { process.kill(-child.pid, 0); return true } catch { return false }
    }
    const probeForGroupExit = (): void => {
      if (progress.completed || command.killProcessGroup !== true) return
      if (pendingFinish === undefined || groupIsLive()) {
        groupProbe = setTimeout(probeForGroupExit, 10)
        return
      }
      complete(...pendingFinish)
    }
    const finish = (exitCode: number | null, signal: string | null, launchError: string | null): void => {
      if (progress.completed) return
      if (command.killProcessGroup === true && progress.terminating) {
        pendingFinish = [exitCode, signal, launchError]
        return
      }
      complete(exitCode, signal, launchError)
    }
    const terminate = (): void => {
      if (progress.terminating) return
      progress.terminating = true
      const kill = (signal: NodeJS.Signals): void => {
        if (command.killProcessGroup === true && child.pid !== undefined) {
          try { process.kill(-child.pid, signal) } catch { /* An exited group needs no further signal. */ }
        } else {
          child.kill(signal)
        }
      }
      kill("SIGTERM")
      forceKill = setTimeout(() => { kill("SIGKILL"); forceKill = undefined; probeForGroupExit() }, 1_000)
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
    return Effect.async<void>((done) => {
      if (progress.completed) { done(Effect.void); return Effect.void }
      terminationWaiters.push(() => done(Effect.void))
      terminate()
      return Effect.void
    })
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
