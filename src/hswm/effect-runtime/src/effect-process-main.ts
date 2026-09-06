/**
 * The one composition root shape for HSWM one-request process executables.
 *
 * A process reads one bounded canonical-JSON request from stdin, runs one
 * Effect program that needs only the Node POSIX services, writes one
 * canonical-JSON reply to stdout, and exits.  Expected failures are typed
 * values mapped to a stable stderr line and exit code 2; defects exit 3.
 * Library and domain modules never call `Effect.run*`; only this helper does,
 * exactly once per executable.
 */
import { Cause, Data, Effect, Either, Exit, Layer } from "effect"

import { canonicalJsonBytes, decodeCanonicalJsonBytes, type CanonicalJson } from "./canonical-atom-v2-json.js"
import { NodePosixServicesLive, type BoundedSubprocess, type PosixFileSystem } from "./effect-posix-services.js"

export const HSWM_PROCESS_MAIN_V1 = "hswm-effect-process-main/v1" as const
export const DEFAULT_MAX_STDIN_BYTES = 1_048_576

/** A refusal is an expected, typed process failure with a stable prefix on stderr. */
export class ProcessRefusal extends Data.TaggedError("ProcessRefusal")<{
  readonly detail: string
}> {}

export const refuse = (detail: string): ProcessRefusal => new ProcessRefusal({ detail })

export interface ProcessMainSpec<A extends CanonicalJson, E> {
  /** Stable stderr prefix, e.g. HSWM_LOCAL_PERMIT_COMMIT_REFUSED. */
  readonly refusalPrefix: string
  readonly maximumStdinBytes?: number
  /** The program: decoded stdin -> reply; may require the Node POSIX services. */
  readonly program: (request: CanonicalJson) => Effect.Effect<A, E, PosixFileSystem | BoundedSubprocess>
  /** Render an expected failure as one stderr line (without the prefix). */
  readonly describeFailure: (error: E) => string
}

export interface ProcessIo {
  readonly readStdin: (maximumBytes: number) => Effect.Effect<string, ProcessRefusal>
  readonly writeStdout: (text: string) => Effect.Effect<void>
  readonly writeStderr: (text: string) => Effect.Effect<void>
}

export const readNodeStdin = (maximumBytes: number): Effect.Effect<string, ProcessRefusal> =>
  Effect.async<string, ProcessRefusal>((resume) => {
    const chunks: Array<string> = []
    const progress = { bytes: 0, settled: false }
    process.stdin.setEncoding("utf8")
    const onData = (chunk: string): void => {
      progress.bytes += Buffer.byteLength(chunk, "utf8")
      if (progress.bytes > maximumBytes) {
        if (!progress.settled) {
          progress.settled = true
          process.stdin.pause()
          resume(Effect.fail(refuse("stdin exceeds the bounded canonical JSON limit")))
        }
        return
      }
      chunks.push(chunk)
    }
    const onEnd = (): void => { if (!progress.settled) { progress.settled = true; resume(Effect.succeed(chunks.join(""))) } }
    const onError = (): void => { if (!progress.settled) { progress.settled = true; resume(Effect.fail(refuse("stdin read failure"))) } }
    process.stdin.on("data", onData)
    process.stdin.once("end", onEnd)
    process.stdin.once("error", onError)
    return Effect.sync(() => {
      process.stdin.off("data", onData)
      process.stdin.off("end", onEnd)
      process.stdin.off("error", onError)
    })
  })

const nodeIo: ProcessIo = {
  readStdin: readNodeStdin,
  writeStdout: (text) => Effect.sync(() => { process.stdout.write(text) }),
  writeStderr: (text) => Effect.sync(() => { process.stderr.write(text) })
}
export const nodeProcessIo: ProcessIo = Object.freeze(nodeIo)

export const decodeStdinRequest = (source: string): Effect.Effect<CanonicalJson, ProcessRefusal> => {
  const decoded = decodeCanonicalJsonBytes(new TextEncoder().encode(source))
  return Either.isLeft(decoded) ? Effect.fail(refuse("stdin must be canonical JSON")) : Effect.succeed(decoded.right)
}

export const encodeReply = (value: CanonicalJson): Effect.Effect<string, ProcessRefusal> => {
  const encoded = canonicalJsonBytes(value)
  return Either.isLeft(encoded)
    ? Effect.fail(refuse("process output cannot form canonical JSON"))
    : Effect.succeed(`${new TextDecoder().decode(encoded.right)}\n`)
}

/**
 * Run one request end to end and return the exit code.  This is the only
 * `Effect.run*` call an executable should contain.  It is exported so tests can
 * drive it with an in-memory `ProcessIo` and a stubbed layer.
 */
export const runProcessMain = <A extends CanonicalJson, E>(
  spec: ProcessMainSpec<A, E>,
  io: ProcessIo = nodeProcessIo,
  services: Layer.Layer<PosixFileSystem | BoundedSubprocess> = NodePosixServicesLive
): Promise<number> => {
  const program = Effect.gen(function* () {
    const source = yield* io.readStdin(spec.maximumStdinBytes ?? DEFAULT_MAX_STDIN_BYTES)
    const request = yield* decodeStdinRequest(source)
    const reply = yield* spec.program(request)
    const text = yield* encodeReply(reply)
    yield* io.writeStdout(text)
    return 0
  }).pipe(Effect.provide(services))
  return Effect.runPromiseExit(program).then((exit) =>
    Exit.match(exit, {
      onSuccess: (code) => code,
      onFailure: (cause) => {
        const failure = Cause.failureOption(cause)
        const line = failure._tag === "Some"
          ? (failure.value instanceof ProcessRefusal ? failure.value.detail : spec.describeFailure(failure.value as E))
          : `defect: ${Cause.pretty(cause).split("\n")[0] ?? "unknown"}`
        return Effect.runPromise(io.writeStderr(`${spec.refusalPrefix}: ${line}\n`)).then(() => (failure._tag === "Some" ? 2 : 3))
      }
    })
  )
}
