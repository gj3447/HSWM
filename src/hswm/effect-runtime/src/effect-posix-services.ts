/**
 * Effect-native POSIX services for the HSWM runtime shell.
 *
 * Every raw Node filesystem and subprocess primitive that the durable
 * journals, content stores, local Permit commit, and research-job runner
 * need lives here, once, behind two `Context.Tag` services with typed
 * failures.  The primitives are deliberately narrower than a general
 * filesystem API: no-follow opens, bounded reads whose file identity is
 * re-checked after the read, exclusive creation, no-replace hard links, and
 * directory fsync are exactly the operations the no-replace publication
 * discipline relies on.  `@effect/platform` cannot express O_NOFOLLOW,
 * directory fsync, or detached process groups, so this module is the
 * repository's own thin adapter and the only place that may use
 * `async`/`await` for I/O.
 *
 * The services are engineering infrastructure.  They are not canonical HSWM
 * state, a Permit, outcome truth, causal credit, learning, or efficacy.
 */
import { spawn } from "node:child_process"
import { constants } from "node:fs"
import { chmod, link, lstat, mkdir, open, readdir, realpath, unlink } from "node:fs/promises"
import type { FileHandle } from "node:fs/promises"

import { Context, Data, Effect, Layer } from "effect"

export const HSWM_EFFECT_POSIX_SERVICES_V1 = "hswm-effect-posix-services/v1" as const

// ---------------------------------------------------------------------------
// Typed failures
// ---------------------------------------------------------------------------

export type PosixIoErrorCode =
  | "ENOENT"
  | "EEXIST"
  | "ELOOP"
  | "EXDEV"
  | "ENOSYS"
  | "ENOTSUP"
  | "EOPNOTSUPP"
  | "EACCES"
  | "EPERM"
  | "ENOTDIR"
  | "EISDIR"
  | "EINVAL"
  | "IO_FAILED"
  | "NOT_REGULAR_FILE"
  | "NOT_DIRECTORY"
  | "MODE_INVALID"
  | "BYTE_BOUND_EXCEEDED"
  | "IDENTITY_CHANGED"

const KNOWN_CODES: ReadonlySet<string> = new Set<string>([
  "ENOENT", "EEXIST", "ELOOP", "EXDEV", "ENOSYS", "ENOTSUP", "EOPNOTSUPP", "EACCES", "EPERM",
  "ENOTDIR", "EISDIR", "EINVAL"
])

export class PosixIoError extends Data.TaggedError("PosixIoError")<{
  readonly operation: string
  readonly path: string
  readonly code: PosixIoErrorCode
  readonly detail: string
}> {}

const ioError = (operation: string, path: string, cause: unknown): PosixIoError => {
  const code = typeof cause === "object" && cause !== null && "code" in cause && typeof cause.code === "string"
    ? cause.code
    : "IO_FAILED"
  return new PosixIoError({
    operation,
    path,
    code: (KNOWN_CODES.has(code) ? code : "IO_FAILED") as PosixIoErrorCode,
    detail: cause instanceof Error ? cause.message : "unknown I/O failure"
  })
}

// ---------------------------------------------------------------------------
// PosixFileSystem service
// ---------------------------------------------------------------------------

export interface PosixPathIdentity {
  readonly path: string
  readonly device: number
  readonly inode: number
  readonly mode: number
  readonly size: number
  readonly kind: "FILE" | "DIRECTORY" | "SYMLINK" | "OTHER"
}

export interface BoundedReadResult {
  readonly bytes: Uint8Array
  readonly device: number
  readonly inode: number
}

export interface BoundedReadOptions {
  readonly maximumBytes: number
  readonly minimumBytes?: number
  /** When set, the file's permission bits must equal this mode before and after the read. */
  readonly requiredMode?: number
  /** Operation label used in typed failures. */
  readonly operation: string
}

export interface DirectoryEntry {
  readonly name: string
  readonly kind: PosixPathIdentity["kind"]
}

export interface PosixFileSystemShape {
  /** lstat without following symlinks; the caller decides which kinds are acceptable. */
  readonly identity: (path: string, operation: string) => Effect.Effect<PosixPathIdentity, PosixIoError>
  /** Directory entries with their lstat kinds, sorted by name. */
  readonly listDirectory: (path: string, operation: string) => Effect.Effect<ReadonlyArray<DirectoryEntry>, PosixIoError>
  readonly realpath: (path: string, operation: string) => Effect.Effect<string, PosixIoError>
  /** mkdir with an exact mode; EEXIST is reported as a typed failure, never swallowed. */
  readonly makeDirectory: (
    path: string,
    options: { readonly mode: number; readonly recursive?: boolean; readonly operation: string }
  ) => Effect.Effect<void, PosixIoError>
  /** Open the directory O_RDONLY|O_DIRECTORY|O_NOFOLLOW and fsync it. */
  readonly syncDirectory: (path: string, operation: string) => Effect.Effect<void, PosixIoError>
  /** Open O_RDONLY|O_NOFOLLOW|O_NONBLOCK, bound the size, read fully, re-check identity. */
  readonly readRegularBounded: (path: string, options: BoundedReadOptions) => Effect.Effect<BoundedReadResult, PosixIoError>
  /** Create O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW with the given mode, write, optionally chmod and fsync. */
  readonly writeExclusive: (
    path: string,
    bytes: Uint8Array,
    options: { readonly mode: number; readonly finalMode?: number; readonly sync: boolean; readonly operation: string }
  ) => Effect.Effect<void, PosixIoError>
  /** hard link that refuses to replace; EEXIST and EXDEV surface as typed codes. */
  readonly linkNoReplace: (existing: string, target: string, operation: string) => Effect.Effect<void, PosixIoError>
  readonly chmod: (path: string, mode: number, operation: string) => Effect.Effect<void, PosixIoError>
  /** unlink whose ENOENT is not a failure; other failures are typed. */
  readonly unlinkIfPresent: (path: string, operation: string) => Effect.Effect<void, PosixIoError>
}

export class PosixFileSystem extends Context.Tag("hswm/PosixFileSystem")<PosixFileSystem, PosixFileSystemShape>() {}

const kindOf = (stat: { isFile(): boolean; isDirectory(): boolean; isSymbolicLink(): boolean }): PosixPathIdentity["kind"] =>
  stat.isSymbolicLink() ? "SYMLINK" : stat.isDirectory() ? "DIRECTORY" : stat.isFile() ? "FILE" : "OTHER"

const withHandle = <A>(
  operation: string,
  path: string,
  acquire: () => Promise<FileHandle>,
  use: (handle: FileHandle) => Promise<A>
): Effect.Effect<A, PosixIoError> =>
  Effect.acquireUseRelease(
    Effect.tryPromise({ try: acquire, catch: (cause) => ioError(operation, path, cause) }),
    (handle) => Effect.tryPromise({ try: () => use(handle), catch: (cause) => cause instanceof PosixIoError ? cause : ioError(operation, path, cause) }),
    (handle) => Effect.promise(() => handle.close().catch(() => undefined))
  )

const nodePosixFileSystem: PosixFileSystemShape = {
  identity: (path, operation) =>
    Effect.tryPromise({
      try: async (): Promise<PosixPathIdentity> => {
        const stat = await lstat(path)
        return Object.freeze({ path, device: stat.dev, inode: stat.ino, mode: stat.mode & 0o777, size: stat.size, kind: kindOf(stat) })
      },
      catch: (cause) => ioError(operation, path, cause)
    }),
  listDirectory: (path, operation) =>
    Effect.tryPromise({
      try: async (): Promise<ReadonlyArray<DirectoryEntry>> => {
        const entries = await readdir(path, { withFileTypes: true })
        return Object.freeze(
          entries
            .map((entry) => Object.freeze({ name: entry.name, kind: kindOf(entry) }))
            .sort((left, right) => left.name.localeCompare(right.name))
        )
      },
      catch: (cause) => ioError(operation, path, cause)
    }),
  realpath: (path, operation) =>
    Effect.tryPromise({ try: () => realpath(path), catch: (cause) => ioError(operation, path, cause) }),
  makeDirectory: (path, options) =>
    Effect.tryPromise({
      try: async () => { await mkdir(path, { mode: options.mode, recursive: options.recursive === true }) },
      catch: (cause) => ioError(options.operation, path, cause)
    }),
  syncDirectory: (path, operation) =>
    withHandle(operation, path,
      () => open(path, constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW),
      async (handle) => { await handle.sync() }
    ),
  readRegularBounded: (path, options) =>
    withHandle(options.operation, path,
      () => open(path, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK),
      async (handle): Promise<BoundedReadResult> => {
        const before = await handle.stat()
        if (!before.isFile()) throw new PosixIoError({ operation: options.operation, path, code: "NOT_REGULAR_FILE", detail: "path is not a regular file" })
        if (options.requiredMode !== undefined && (before.mode & 0o777) !== options.requiredMode) {
          throw new PosixIoError({ operation: options.operation, path, code: "MODE_INVALID", detail: "file mode differs from the required mode" })
        }
        if (before.size < (options.minimumBytes ?? 0) || before.size > options.maximumBytes) {
          throw new PosixIoError({ operation: options.operation, path, code: "BYTE_BOUND_EXCEEDED", detail: "file size violates the declared byte bound" })
        }
        const buffer = Buffer.alloc(before.size + 1)
        let total = 0
        while (total < buffer.byteLength) {
          const result = await handle.read(buffer, total, buffer.byteLength - total, total)
          if (result.bytesRead === 0) break
          total += result.bytesRead
        }
        const after = await handle.stat()
        if (
          total !== before.size || after.dev !== before.dev || after.ino !== before.ino || after.size !== before.size ||
          (options.requiredMode !== undefined && (after.mode & 0o777) !== options.requiredMode)
        ) {
          throw new PosixIoError({ operation: options.operation, path, code: "IDENTITY_CHANGED", detail: "file changed during the bounded read" })
        }
        return Object.freeze({ bytes: Uint8Array.from(buffer.subarray(0, total)), device: before.dev, inode: before.ino })
      }
    ),
  writeExclusive: (path, bytes, options) =>
    withHandle(options.operation, path,
      () => open(path, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW, options.mode),
      async (handle) => {
        await handle.writeFile(bytes)
        if (options.finalMode !== undefined) await handle.chmod(options.finalMode)
        if (options.sync) await handle.sync()
      }
    ),
  linkNoReplace: (existing, target, operation) =>
    Effect.tryPromise({ try: () => link(existing, target), catch: (cause) => ioError(operation, target, cause) }),
  chmod: (path, mode, operation) =>
    Effect.tryPromise({ try: () => chmod(path, mode), catch: (cause) => ioError(operation, path, cause) }),
  unlinkIfPresent: (path, operation) =>
    Effect.tryPromise({ try: () => unlink(path), catch: (cause) => ioError(operation, path, cause) }).pipe(
      Effect.catchIf((error) => error.code === "ENOENT", () => Effect.void)
    )
}

/** The single Node adapter; compose it exactly once at an executable's root. */
export const NodePosixFileSystem: PosixFileSystemShape = Object.freeze(nodePosixFileSystem)
export const NodePosixFileSystemLive: Layer.Layer<PosixFileSystem> = Layer.succeed(PosixFileSystem, NodePosixFileSystem)

// ---------------------------------------------------------------------------
// BoundedSubprocess service
// ---------------------------------------------------------------------------

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

/** Both Node adapters; the only layer an executable's composition root needs for POSIX effects. */
export const NodePosixServicesLive: Layer.Layer<PosixFileSystem | BoundedSubprocess> =
  Layer.merge(NodePosixFileSystemLive, NodeBoundedSubprocessLive)
