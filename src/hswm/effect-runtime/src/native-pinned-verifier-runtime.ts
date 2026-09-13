/** Linux descriptor-backed execution for a byte-pinned native verifier. */
import { createHash } from "node:crypto"
import { closeSync, existsSync, fstatSync, openSync, readSync, realpathSync } from "node:fs"

import { Context, Data, Effect, Either, Layer } from "effect"

import { BoundedSubprocess, type SubprocessCommand, type SubprocessObservation } from "./effect-bounded-subprocess.js"

const sha256 = /^[0-9a-f]{64}$/u
const procFd = (fd: number): string => `/proc/self/fd/${fd}`

export class NativePinnedVerifierError extends Data.TaggedError("NativePinnedVerifierError")<{
  readonly code: "PIN_INVALID" | "PIN_MISMATCH" | "DESCRIPTOR_UNAVAILABLE" | "EXECUTION_FAILED"
  readonly detail: string
}> {}

export interface NativePinnedInput {
  readonly path: string
  readonly sha256: string
  /** The path must occur once in verifier argv and is replaced by its held descriptor. */
  readonly argvPath: string
  readonly maximumBytes: number
}

export interface NativePinnedVerifierRequest {
  readonly argv: ReadonlyArray<string>
  readonly executablePath: string
  readonly executableSha256: string
  readonly expectedVersionOutput: string
  /** Defaults to the source-oracle `version` probe. */
  readonly versionArgv?: ReadonlyArray<string>
  readonly pinnedInputs: ReadonlyArray<NativePinnedInput>
  readonly cwd: string
  readonly environment: Readonly<Record<string, string>>
  readonly timeoutMs: number
  readonly maximumOutputBytes: number
}

export interface NativePinnedVerifierResult {
  readonly version: SubprocessObservation
  readonly verification: SubprocessObservation
}

export interface NativePinnedVerifierShape {
  readonly verify: (request: NativePinnedVerifierRequest) => Effect.Effect<NativePinnedVerifierResult, NativePinnedVerifierError, BoundedSubprocess>
}
export class NativePinnedVerifier extends Context.Tag("hswm/NativePinnedVerifier")<NativePinnedVerifier, NativePinnedVerifierShape>() {}

interface HeldFile { readonly fd: number; readonly canonicalPath: string; readonly childFd: number }

const error = (code: NativePinnedVerifierError["code"], detail: string): NativePinnedVerifierError => new NativePinnedVerifierError({ code, detail })
const hashHeldRegular = (path: string, expected: string, maximumBytes: number, childFd: number): Either.Either<HeldFile, NativePinnedVerifierError> => {
  if (!sha256.test(expected) || !Number.isSafeInteger(maximumBytes) || maximumBytes < 1) return Either.left(error("PIN_INVALID", "pinned verifier digest or byte bound is invalid"))
  let fd: number | undefined
  try {
    const canonicalPath = realpathSync(path)
    fd = openSync(canonicalPath, "r")
    if (!fstatSync(fd).isFile()) { closeSync(fd); return Either.left(error("PIN_INVALID", "pinned verifier material must be a regular file")) }
    const digest = createHash("sha256")
    const buffer = Buffer.allocUnsafe(1024 * 1024)
    let total = 0
    for (;;) {
      const bytes = readSync(fd, buffer, 0, buffer.byteLength, null)
      if (bytes === 0) break
      total += bytes
      if (total > maximumBytes) { closeSync(fd); return Either.left(error("PIN_MISMATCH", "pinned verifier material exceeds its byte bound")) }
      digest.update(buffer.subarray(0, bytes))
    }
    if (digest.digest("hex") !== expected) { closeSync(fd); return Either.left(error("PIN_MISMATCH", "pinned verifier material SHA-256 differs")) }
    if (!fstatSync(fd).isFile()) { closeSync(fd); return Either.left(error("PIN_MISMATCH", "pinned verifier material changed type")) }
    return Either.right(Object.freeze({ fd, canonicalPath, childFd }))
  } catch (cause) {
    if (fd !== undefined) closeSync(fd)
    return Either.left(cause instanceof NativePinnedVerifierError ? cause : error("EXECUTION_FAILED", cause instanceof Error ? cause.message : "cannot hold pinned verifier material"))
  }
}

const verifyWithNode = (request: NativePinnedVerifierRequest): Effect.Effect<NativePinnedVerifierResult, NativePinnedVerifierError, BoundedSubprocess> => {
  if (request.argv.length === 0 || request.argv[0] !== request.executablePath || request.argv.some((argument) => argument.includes("\0")) || request.expectedVersionOutput.length === 0) {
    return Effect.fail(error("PIN_INVALID", "pinned verifier argv or version expectation is invalid"))
  }
  const held = Effect.suspend(() => {
      const executable = hashHeldRegular(request.executablePath, request.executableSha256, Number.MAX_SAFE_INTEGER, 3)
      if (Either.isLeft(executable)) return Effect.fail(executable.left)
      const inputs: HeldFile[] = []
      const argvPaths = new Set<string>()
      for (const [index, input] of request.pinnedInputs.entries()) {
        if (argvPaths.has(input.argvPath) || request.argv.filter((argument) => argument === input.argvPath).length !== 1) {
        for (const input of inputs) closeSync(input.fd)
          closeSync(executable.right.fd)
          return Effect.fail(error("PIN_INVALID", "each pinned verifier input must occur exactly once in argv"))
        }
        argvPaths.add(input.argvPath)
        const heldInput = hashHeldRegular(input.path, input.sha256, input.maximumBytes, index + 4)
        if (Either.isLeft(heldInput)) {
          for (const openedInput of inputs) closeSync(openedInput.fd)
          closeSync(executable.right.fd)
          return Effect.fail(heldInput.left)
        }
        inputs.push(heldInput.right)
      }
      if (process.platform !== "linux" || !existsSync(procFd(executable.right.fd))) {
        for (const input of inputs) closeSync(input.fd)
        closeSync(executable.right.fd)
        return Effect.fail(error("DESCRIPTOR_UNAVAILABLE", "immutable descriptor execution requires Linux /proc/self/fd"))
      }
      return Effect.succeed(Object.freeze({ executable: executable.right, inputs: Object.freeze(inputs) }))
  })
  return Effect.acquireUseRelease(held, (files) => {
    const descriptors = Object.freeze([files.executable, ...files.inputs].map((file) => Object.freeze({ parentFd: file.fd, childFd: file.childFd })))
    const rewrite = (argv: ReadonlyArray<string>): ReadonlyArray<string> => Object.freeze(argv.map((argument, index) => {
      if (index === 0) return procFd(files.executable.childFd)
      const input = files.inputs.find((_heldInput, inputIndex) => request.pinnedInputs[inputIndex]?.argvPath === argument)
      return input === undefined ? argument : procFd(input.childFd)
    }))
    const command = (argv: ReadonlyArray<string>): SubprocessCommand => ({ argv, cwd: request.cwd, environment: request.environment, timeoutMs: request.timeoutMs, maximumOutputBytes: request.maximumOutputBytes, inheritedDescriptors: descriptors })
    const program = Effect.gen(function* () {
      const subprocess = yield* BoundedSubprocess
      const versionArguments = request.versionArgv ?? Object.freeze(["version"])
      if (versionArguments.length === 0 || versionArguments.some((argument) => argument.includes("\0"))) return yield* Effect.fail(error("PIN_INVALID", "pinned verifier version argv is invalid"))
      const version = yield* subprocess.observe(command(Object.freeze([procFd(files.executable.childFd), ...versionArguments]))).pipe(Effect.mapError((cause) => error("EXECUTION_FAILED", cause.detail)))
      const versionText = new TextDecoder().decode(version.stdout) + new TextDecoder().decode(version.stderr)
      if (version.launchError !== null || version.timedOut || version.outputTruncated || version.exitCode !== 0 || version.signal !== null || versionText !== request.expectedVersionOutput) return yield* Effect.fail(error("PIN_MISMATCH", "pinned verifier exact version output mismatch"))
      const verification = yield* subprocess.observe(command(rewrite(request.argv))).pipe(Effect.mapError((cause) => error("EXECUTION_FAILED", cause.detail)))
      return Object.freeze({ version, verification })
    })
    return program
  }, (files) => Effect.sync(() => { for (const input of files.inputs) closeSync(input.fd); closeSync(files.executable.fd) }))
}

export const NodePinnedVerifierLive: Layer.Layer<NativePinnedVerifier> = Layer.succeed(NativePinnedVerifier, Object.freeze({ verify: verifyWithNode }))
