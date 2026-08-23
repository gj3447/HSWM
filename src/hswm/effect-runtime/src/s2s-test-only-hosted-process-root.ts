import { createHash, randomBytes } from "node:crypto"
import { constants, createReadStream } from "node:fs"
import {
  chmod,
  lstat,
  mkdir,
  open,
  readFile,
  realpath,
  rename,
  rm,
  stat,
  unlink
} from "node:fs/promises"
import { createConnection, createServer, type Server, type Socket } from "node:net"
import { basename, dirname, isAbsolute, join, resolve } from "node:path"
import { isProxy } from "node:util/types"

import { Data, Effect, Either, Schema } from "effect"

import {
  canonicalS2SControlJsonBytes,
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "./s2s-canonical.js"
import { S2S_STAGE_ARTIFACT_SPECS } from "./s2s-stage-artifact-spec.js"
import {
  S2S_TEST_ONLY_HOSTED_PROCESS_CLASSIFICATION,
  S2S_TEST_ONLY_HOSTED_PROCESS_MAX_FRAME_BYTES,
  S2S_TEST_ONLY_HOSTED_PROCESS_PROTOCOL_VERSION,
  canonicalS2STestOnlyHostedProcessFrame,
  decodeS2STestOnlyHostedProcessReadyFrame,
  decodeS2STestOnlyHostedProcessReconcileFrame,
  decodeS2STestOnlyHostedProcessTerminalFrame,
  makeS2STestOnlyHostedProcessBinding,
  makeS2STestOnlyHostedProcessReady,
  makeS2STestOnlyHostedProcessReconcileFrame,
  makeS2STestOnlyHostedProcessTerminal,
  s2sTestOnlyHostedProcessAttemptStageJobMatches,
  type S2STestOnlyHostedProcessBinding,
  type S2STestOnlyHostedProcessReady,
  type S2STestOnlyHostedProcessTerminal,
  type S2STestOnlyHostedProcessUploadStepOutcome
} from "./s2s-test-only-hosted-process-protocol.js"
import {
  type S2SConfirmatoryJobId,
  type S2SConfirmatoryJobStage
} from "./s2s-workflow-contract.js"
import { buildS2SStoredZip } from "./s2s-zip.js"

export const S2S_TEST_ONLY_HOSTED_PROCESS_SESSION_TIMEOUT_MILLIS =
  900_000 as const
export const S2S_TEST_ONLY_HOSTED_PROCESS_FRAME_TIMEOUT_MILLIS = 5_000 as const
export const S2S_TEST_ONLY_HOSTED_PROCESS_READY_TIMEOUT_MILLIS = 30_000 as const
export const S2S_TEST_ONLY_HOSTED_PROCESS_SOCKET_PATH_MAX_BYTES = 100 as const
export const S2S_TEST_ONLY_HOSTED_PROCESS_OCCURRENCE_MAX_BYTES = 4_096 as const

export const S2S_TEST_ONLY_HOSTED_PROCESS_READY_FILE = "ready.json" as const
export const S2S_TEST_ONLY_HOSTED_PROCESS_TOKEN_FILE = "client.token" as const
export const S2S_TEST_ONLY_HOSTED_PROCESS_SOCKET_FILE = "control.sock" as const
export const S2S_TEST_ONLY_HOSTED_PROCESS_EVIDENCE_DIRECTORY = "evidence" as const
export const S2S_TEST_ONLY_HOSTED_PROCESS_UPLOAD_DIRECTORY = "upload" as const
export const S2S_TEST_ONLY_HOSTED_PROCESS_TERMINAL_FILE = "terminal.json" as const
export const S2S_TEST_ONLY_HOSTED_PROCESS_OCCURRENCE_FILE = "occurrence.json" as const
export const S2S_TEST_ONLY_HOSTED_PROCESS_READY_CONSUMED_FILE =
  "ready.consumed.json" as const

const SESSION_NAME_PATTERN = /^hswm-s2s-pc-[a-z0-9-]{1,48}$/
const SHA256_PATTERN = /^[0-9a-f]{64}$/

const RootInputSchema = Schema.Struct({
  classification: Schema.Literal(
    S2S_TEST_ONLY_HOSTED_PROCESS_CLASSIFICATION
  ),
  runnerTempPath: Schema.String.pipe(
    Schema.minLength(1),
    Schema.maxLength(512)
  ),
  sessionName: Schema.String.pipe(Schema.pattern(SESSION_NAME_PATTERN)),
  workflowRunId: Schema.Number.pipe(
    Schema.int(),
    Schema.between(1, Number.MAX_SAFE_INTEGER)
  ),
  workflowRunAttempt: Schema.Literal(1),
  feasibilityAttempt: Schema.Literal(1, 2, 3),
  stage: Schema.Literal("REGISTER", "CONFIRM", "ADJUDICATE"),
  jobId: Schema.Literal("register", "confirm", "adjudicate")
})

const ClientInputSchema = RootInputSchema

const ROOT_INPUT_KEYS = Object.freeze([
  "classification",
  "runnerTempPath",
  "sessionName",
  "workflowRunId",
  "workflowRunAttempt",
  "feasibilityAttempt",
  "stage",
  "jobId"
] as const)

export type S2STestOnlyHostedProcessRootInput = typeof RootInputSchema.Type
export type S2STestOnlyHostedProcessClientInput = typeof ClientInputSchema.Type

export interface S2STestOnlyHostedProcessPaths {
  readonly runnerTempPath: string
  readonly runnerTempDevice: number
  readonly runnerTempInode: number
  readonly sessionPath: string
  readonly uploadPath: string
  readonly evidencePath: string
  readonly readyPath: string
  readonly consumedReadyPath: string
  readonly tokenPath: string
  readonly socketPath: string
  readonly terminalPath: string
  readonly occurrencePath: string
}

export interface S2STestOnlyHostedProcessReadyObservation {
  readonly ready: S2STestOnlyHostedProcessReady
  readonly paths: S2STestOnlyHostedProcessPaths
  readonly readyFrameSha256: string
}

export interface S2STestOnlyHostedProcessReconcileObservation {
  readonly terminal: S2STestOnlyHostedProcessTerminal
  readonly paths: S2STestOnlyHostedProcessPaths
  readonly readyFrameSha256: string
  readonly terminalFrameSha256: string
}

export class S2STestOnlyHostedProcessRuntimeError extends Data.TaggedError(
  "S2STestOnlyHostedProcessRuntimeError"
)<{
  readonly phase:
    | "INPUT"
    | "ALLOCATE"
    | "PREPARE"
    | "LISTEN"
    | "READY"
    | "RECONCILE"
    | "TERMINAL"
    | "CLEANUP"
  readonly reason:
    | "UNSUPPORTED_PLATFORM"
    | "INPUT_REJECTED"
    | "RUNNER_TEMP_REJECTED"
    | "CONTROL_DIRECTORY_REJECTED"
    | "SOCKET_PATH_REJECTED"
    | "CONTROL_FILE_POLICY_REJECTED"
    | "SOCKET_POLICY_REJECTED"
    | "ARCHIVE_PREPARATION_FAILED"
    | "SESSION_TIMED_OUT"
    | "FRAME_TIMED_OUT"
    | "FRAME_LIMIT_EXCEEDED"
    | "FRAME_REJECTED"
    | "AUTHENTICATION_FAILED"
    | "BINDING_MISMATCH"
    | "ROOT_IDENTITY_DRIFT"
    | "PREPARED_FILES_DRIFTED"
    | "TERMINAL_DELIVERY_UNKNOWN"
    | "REPLAY_REJECTED"
    | "IO_FAILED"
  readonly detail: string
  readonly causeTag: string | null
}> {}

const runtimeError = (
  phase: S2STestOnlyHostedProcessRuntimeError["phase"],
  reason: S2STestOnlyHostedProcessRuntimeError["reason"],
  detail: string,
  causeTag: string | null = null
): S2STestOnlyHostedProcessRuntimeError =>
  new S2STestOnlyHostedProcessRuntimeError({
    phase,
    reason,
    detail,
    causeTag
  })

const hasCode = (input: unknown): input is { readonly code: string } =>
  typeof input === "object" &&
  input !== null &&
  "code" in input &&
  typeof input.code === "string"

const ioError = (
  phase: S2STestOnlyHostedProcessRuntimeError["phase"],
  error: unknown,
  detail: string
): S2STestOnlyHostedProcessRuntimeError =>
  error instanceof S2STestOnlyHostedProcessRuntimeError
    ? error
    : runtimeError(
        phase,
        "IO_FAILED",
        detail,
        hasCode(error) ? error.code : "UNKNOWN_IO_ERROR"
      )

const effectiveUid = (): number => {
  if (process.geteuid === undefined) {
    throw runtimeError(
      "ALLOCATE",
      "UNSUPPORTED_PLATFORM",
      "effective UID inspection is unavailable"
    )
  }
  return process.geteuid()
}

const decodeInput = (
  input: unknown
): Either.Either<
  S2STestOnlyHostedProcessRootInput,
  S2STestOnlyHostedProcessRuntimeError
> => {
  let candidate: Readonly<Record<string, unknown>>
  try {
    if (
      input === null ||
      typeof input !== "object" ||
      isProxy(input) ||
      Object.getPrototypeOf(input) !== Object.prototype
    ) {
      return Either.left(
        runtimeError("INPUT", "INPUT_REJECTED", "root/client input was rejected")
      )
    }
    const keys = Reflect.ownKeys(input)
    if (
      keys.length !== ROOT_INPUT_KEYS.length ||
      keys.some(
        (key) =>
          typeof key !== "string" ||
          !ROOT_INPUT_KEYS.some((expected) => expected === key)
      )
    ) {
      return Either.left(
        runtimeError("INPUT", "INPUT_REJECTED", "root/client input was rejected")
      )
    }
    const values = new Map<string, unknown>()
    for (const key of ROOT_INPUT_KEYS) {
      const descriptor = Object.getOwnPropertyDescriptor(input, key)
      if (
        descriptor === undefined ||
        !descriptor.enumerable ||
        !("value" in descriptor)
      ) {
        return Either.left(
          runtimeError("INPUT", "INPUT_REJECTED", "root/client input was rejected")
        )
      }
      values.set(key, descriptor.value)
    }
    candidate = Object.freeze({
      classification: values.get("classification"),
      runnerTempPath: values.get("runnerTempPath"),
      sessionName: values.get("sessionName"),
      workflowRunId: values.get("workflowRunId"),
      workflowRunAttempt: values.get("workflowRunAttempt"),
      feasibilityAttempt: values.get("feasibilityAttempt"),
      stage: values.get("stage"),
      jobId: values.get("jobId")
    })
  } catch {
    return Either.left(
      runtimeError("INPUT", "INPUT_REJECTED", "root/client input was rejected")
    )
  }
  let decoded: Either.Either<S2STestOnlyHostedProcessRootInput, unknown>
  try {
    decoded = Schema.decodeUnknownEither(RootInputSchema, {
      onExcessProperty: "error"
    })(candidate)
  } catch {
    return Either.left(
      runtimeError("INPUT", "INPUT_REJECTED", "root/client input was rejected")
    )
  }
  if (Either.isLeft(decoded)) {
    return Either.left(
      runtimeError("INPUT", "INPUT_REJECTED", "root/client input was rejected")
    )
  }
  if (!s2sTestOnlyHostedProcessAttemptStageJobMatches(
    decoded.right.feasibilityAttempt,
    decoded.right.stage,
    decoded.right.jobId
  )) {
    return Either.left(
      runtimeError(
        "INPUT",
        "INPUT_REJECTED",
        "attempt, stage, and job ID do not match the fixed workflow contract"
      )
    )
  }
  return Either.right(Object.freeze({ ...decoded.right }))
}

const resolvePaths = async (
  input: S2STestOnlyHostedProcessRootInput
): Promise<S2STestOnlyHostedProcessPaths> => {
  if (process.platform !== "linux") {
    throw runtimeError(
      "ALLOCATE",
      "UNSUPPORTED_PLATFORM",
      "hosted process continuity feasibility is Linux-only"
    )
  }
  if (!isAbsolute(input.runnerTempPath)) {
    throw runtimeError(
      "ALLOCATE",
      "RUNNER_TEMP_REJECTED",
      "runner temp must be an absolute path"
    )
  }
  const runnerTempPath = await realpath(input.runnerTempPath)
  const runnerStat = await lstat(runnerTempPath)
  if (
    runnerStat.isSymbolicLink() ||
    !runnerStat.isDirectory() ||
    runnerStat.uid !== effectiveUid() ||
    (runnerStat.mode & 0o777) !== 0o700
  ) {
    throw runtimeError(
      "ALLOCATE",
      "RUNNER_TEMP_REJECTED",
      "canonical process temp must be a same-euid private directory"
    )
  }
  const runnerParentStat = await lstat(dirname(runnerTempPath))
  const peerWritable = (runnerParentStat.mode & 0o022) !== 0
  const sticky = (runnerParentStat.mode & 0o1000) !== 0
  if (
    runnerParentStat.isSymbolicLink() ||
    !runnerParentStat.isDirectory() ||
    (peerWritable && !sticky)
  ) {
    throw runtimeError(
      "ALLOCATE",
      "RUNNER_TEMP_REJECTED",
      "process-temp parent must be non-peer-writable or sticky"
    )
  }
  const sessionPath = resolve(runnerTempPath, input.sessionName)
  if (dirname(sessionPath) !== runnerTempPath) {
    throw runtimeError(
      "ALLOCATE",
      "CONTROL_DIRECTORY_REJECTED",
      "session path must be one direct runner-temp child"
    )
  }
  const socketPath = join(sessionPath, S2S_TEST_ONLY_HOSTED_PROCESS_SOCKET_FILE)
  if (
    Buffer.byteLength(socketPath, "utf8") >
    S2S_TEST_ONLY_HOSTED_PROCESS_SOCKET_PATH_MAX_BYTES
  ) {
    throw runtimeError(
      "ALLOCATE",
      "SOCKET_PATH_REJECTED",
      "Unix socket path exceeds the fixed 100-byte portability bound"
    )
  }
  const evidencePath = join(
    sessionPath,
    S2S_TEST_ONLY_HOSTED_PROCESS_EVIDENCE_DIRECTORY
  )
  return Object.freeze({
    runnerTempPath,
    runnerTempDevice: runnerStat.dev,
    runnerTempInode: runnerStat.ino,
    sessionPath,
    uploadPath: join(
      sessionPath,
      S2S_TEST_ONLY_HOSTED_PROCESS_UPLOAD_DIRECTORY
    ),
    evidencePath,
    readyPath: join(sessionPath, S2S_TEST_ONLY_HOSTED_PROCESS_READY_FILE),
    consumedReadyPath: join(
      evidencePath,
      S2S_TEST_ONLY_HOSTED_PROCESS_READY_CONSUMED_FILE
    ),
    tokenPath: join(sessionPath, S2S_TEST_ONLY_HOSTED_PROCESS_TOKEN_FILE),
    socketPath,
    terminalPath: join(
      evidencePath,
      S2S_TEST_ONLY_HOSTED_PROCESS_TERMINAL_FILE
    ),
    occurrencePath: join(
      evidencePath,
      S2S_TEST_ONLY_HOSTED_PROCESS_OCCURRENCE_FILE
    )
  })
}

interface DirectoryIdentity {
  readonly device: number
  readonly inode: number
}

const assertPrivateDirectory = async (
  path: string,
  expected: DirectoryIdentity | null = null,
  phase: S2STestOnlyHostedProcessRuntimeError["phase"] = "ALLOCATE"
): Promise<DirectoryIdentity> => {
  try {
    const fileStat = await lstat(path)
    if (
      fileStat.isSymbolicLink() ||
      !fileStat.isDirectory() ||
      fileStat.uid !== effectiveUid() ||
      (fileStat.mode & 0o777) !== 0o700 ||
      (expected !== null &&
        (fileStat.dev !== expected.device || fileStat.ino !== expected.inode))
    ) {
      throw runtimeError(
        phase,
        "CONTROL_DIRECTORY_REJECTED",
        "session directories must be plain, same-euid, and mode 0700"
      )
    }
    return Object.freeze({ device: fileStat.dev, inode: fileStat.ino })
  } catch (error) {
    throw ioError(phase, error, "private directory inspection failed")
  }
}

const writeExclusiveFile = async (
  path: string,
  bytes: Uint8Array,
  phase: S2STestOnlyHostedProcessRuntimeError["phase"] = "PREPARE"
): Promise<void> => {
  try {
    const handle = await open(
      path,
      constants.O_WRONLY |
        constants.O_CREAT |
        constants.O_EXCL |
        constants.O_NOFOLLOW,
      0o600
    )
    try {
      await handle.writeFile(bytes)
      await handle.sync()
      const fileStat = await handle.stat()
      if (
        !fileStat.isFile() ||
        fileStat.uid !== effectiveUid() ||
        (fileStat.mode & 0o777) !== 0o600 ||
        fileStat.size !== bytes.byteLength
      ) {
        throw runtimeError(
          phase,
          "CONTROL_FILE_POLICY_REJECTED",
          "created control file violates type, owner, mode, or size policy"
        )
      }
    } finally {
      await handle.close()
    }
  } catch (error) {
    throw ioError(phase, error, "exclusive private file write failed")
  }
}

interface BoundedFileSnapshot {
  readonly bytes: Uint8Array
  readonly device: number
  readonly inode: number
  readonly byteLength: number
  readonly sha256: string
}

const readPrivateRegularFile = async (
  path: string,
  maximumBytes: number,
  expectedBytes: number | null = null,
  phase: S2STestOnlyHostedProcessRuntimeError["phase"] = "READY"
): Promise<BoundedFileSnapshot> => {
  try {
    const handle = await open(
      path,
      constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK
    )
    try {
      const before = await handle.stat()
      if (
        !before.isFile() ||
        before.uid !== effectiveUid() ||
        (before.mode & 0o777) !== 0o600 ||
        before.size < 1 ||
        before.size > maximumBytes ||
        (expectedBytes !== null && before.size !== expectedBytes)
      ) {
        throw runtimeError(
          phase,
          "CONTROL_FILE_POLICY_REJECTED",
          "control file violates type, owner, mode, or byte policy"
        )
      }
      const output = new Uint8Array(before.size)
      let offset = 0
      while (offset < output.byteLength) {
        const read = await handle.read(
          output,
          offset,
          output.byteLength - offset,
          offset
        )
        if (read.bytesRead === 0) break
        offset += read.bytesRead
      }
      const after = await handle.stat()
      if (
        offset !== output.byteLength ||
        after.dev !== before.dev ||
        after.ino !== before.ino ||
        after.size !== before.size
      ) {
        throw runtimeError(
          phase,
          "CONTROL_FILE_POLICY_REJECTED",
          "control file changed while it was read"
        )
      }
      return Object.freeze({
        bytes: output,
        device: before.dev,
        inode: before.ino,
        byteLength: before.size,
        sha256: rawS2SFileSha256(output)
      })
    } finally {
      await handle.close()
    }
  } catch (error) {
    throw ioError(phase, error, "bounded private file read failed")
  }
}

const hashRegularFile = async (path: string): Promise<string> =>
  new Promise((resolveHash, rejectHash) => {
    const hash = createHash("sha256")
    const stream = createReadStream(path)
    stream.on("data", (chunk: string | Buffer) => hash.update(chunk))
    stream.once("error", rejectHash)
    stream.once("end", () => resolveHash(hash.digest("hex")))
  })

const procStartTicks = async (pid: number): Promise<string> => {
  const raw = await readFile(`/proc/${pid}/stat`, "utf8")
  const close = raw.lastIndexOf(")")
  const fields = close >= 0 ? raw.slice(close + 1).trim().split(/\s+/) : []
  const startTicks = fields[19]
  if (startTicks === undefined || !/^[1-9][0-9]*$/.test(startTicks)) {
    throw runtimeError(
      "PREPARE",
      "ROOT_IDENTITY_DRIFT",
      "Linux process start-time ticks are unavailable"
    )
  }
  return startTicks
}

const observeRuntimeIdentity = async (instanceId: string, pid: number) => {
  const executablePath = await realpath(`/proc/${pid}/exe`)
  const executableStat = await stat(executablePath)
  const bootId = (await readFile("/proc/sys/kernel/random/boot_id", "utf8")).trim()
  const bootIdSha256 = createHash("sha256").update(bootId, "ascii").digest("hex")
  return Object.freeze({
    rootPid: pid,
    procStartTicks: await procStartTicks(pid),
    bootIdSha256,
    nodeVersion: process.version,
    nodeExecutableSha256: await hashRegularFile(executablePath),
    nodeExecutableDevice: executableStat.dev,
    nodeExecutableInode: executableStat.ino,
    instanceId
  })
}

const runtimeIdentityMatches = async (
  expected: S2STestOnlyHostedProcessBinding["runtimeIdentity"]
): Promise<boolean> => {
  const observed = await observeRuntimeIdentity(
    expected.instanceId,
    expected.rootPid
  )
  return (
    observed.rootPid === expected.rootPid &&
    observed.procStartTicks === expected.procStartTicks &&
    observed.bootIdSha256 === expected.bootIdSha256 &&
    observed.nodeVersion === expected.nodeVersion &&
    observed.nodeExecutableSha256 === expected.nodeExecutableSha256 &&
    observed.nodeExecutableDevice === expected.nodeExecutableDevice &&
    observed.nodeExecutableInode === expected.nodeExecutableInode &&
    observed.instanceId === expected.instanceId
  )
}

const makeArchiveMemberBytes = (
  input: S2STestOnlyHostedProcessRootInput,
  memberName: string
): Uint8Array => {
  const encoded = canonicalS2SControlJsonBytes(
    Object.freeze({
      schema_version:
        "hswm-swm0w-s2s-test-only-hosted-archive-shape-member/v1",
      classification: S2S_TEST_ONLY_HOSTED_PROCESS_CLASSIFICATION,
      stage: input.stage,
      job_id: input.jobId,
      feasibility_attempt: input.feasibilityAttempt,
      member_name: memberName,
      structural_shape_only: true,
      production_evidence_claimed: false,
      scientific_evidence_claimed: false
    })
  )
  if (Either.isLeft(encoded)) {
    throw runtimeError(
      "PREPARE",
      "ARCHIVE_PREPARATION_FAILED",
      "structural archive member could not be encoded"
    )
  }
  return encoded.right
}

interface PreparedArchive {
  readonly path: string
  readonly logicalName: string
  readonly snapshot: BoundedFileSnapshot
}

const prepareStructuralArchive = async (
  input: S2STestOnlyHostedProcessRootInput,
  paths: S2STestOnlyHostedProcessPaths
): Promise<PreparedArchive> => {
  const spec = S2S_STAGE_ARTIFACT_SPECS[input.stage]
  const built = buildS2SStoredZip(
    spec.expectedMembers.map((member) =>
      Object.freeze({
        name: member.name,
        bytes: makeArchiveMemberBytes(input, member.name)
      })
    )
  )
  if (Either.isLeft(built)) {
    throw runtimeError(
      "PREPARE",
      "ARCHIVE_PREPARATION_FAILED",
      "structural action-compatible ZIP construction failed"
    )
  }
  const path = join(paths.uploadPath, basename(spec.archiveLogicalName))
  const bytes = built.right.readArchiveBytes()
  await writeExclusiveFile(path, bytes)
  const snapshot = await readPrivateRegularFile(path, spec.maximumArchiveBytes)
  if (
    snapshot.sha256 !== built.right.archiveSha256 ||
    snapshot.byteLength !== built.right.archiveByteLength
  ) {
    throw runtimeError(
      "PREPARE",
      "ARCHIVE_PREPARATION_FAILED",
      "prepared ZIP bytes diverged from the deterministic builder"
    )
  }
  return Object.freeze({
    path,
    logicalName: spec.archiveLogicalName,
    snapshot
  })
}

interface AcceptedConnection {
  readonly socket: Socket
  readonly frame: Uint8Array | null
  readonly errorReason:
    | "FRAME_TIMED_OUT"
    | "FRAME_LIMIT_EXCEEDED"
    | "FRAME_REJECTED"
    | null
}

const readOneFrame = (socket: Socket): Promise<AcceptedConnection> =>
  new Promise((resolveFrame) => {
    const chunks: Array<Uint8Array> = []
    let total = 0
    let finished = false
    const finish = (
      frame: Uint8Array | null,
      errorReason: AcceptedConnection["errorReason"]
    ): void => {
      if (finished) return
      finished = true
      socket.setTimeout(0)
      socket.removeListener("data", onData)
      socket.removeListener("end", onEnd)
      socket.removeListener("error", onError)
      socket.removeListener("timeout", onTimeout)
      resolveFrame(Object.freeze({ socket, frame, errorReason }))
    }
    const onData = (chunk: Buffer): void => {
      total += chunk.byteLength
      if (total > S2S_TEST_ONLY_HOSTED_PROCESS_MAX_FRAME_BYTES) {
        finish(null, "FRAME_LIMIT_EXCEEDED")
        return
      }
      chunks.push(new Uint8Array(chunk))
    }
    const onEnd = (): void => {
      if (total < 2) {
        finish(null, "FRAME_REJECTED")
        return
      }
      const frame = new Uint8Array(total)
      let offset = 0
      for (const chunk of chunks) {
        frame.set(chunk, offset)
        offset += chunk.byteLength
      }
      finish(frame, null)
    }
    const onError = (): void => finish(null, "FRAME_REJECTED")
    const onTimeout = (): void => finish(null, "FRAME_TIMED_OUT")
    socket.setTimeout(S2S_TEST_ONLY_HOSTED_PROCESS_FRAME_TIMEOUT_MILLIS)
    socket.on("data", onData)
    socket.once("end", onEnd)
    socket.once("error", onError)
    socket.once("timeout", onTimeout)
  })

interface RootResource {
  readonly paths: S2STestOnlyHostedProcessPaths
  readonly input: S2STestOnlyHostedProcessRootInput
  readonly token: Uint8Array
  readonly binding: S2STestOnlyHostedProcessBinding
  readonly ready: S2STestOnlyHostedProcessReady
  readonly readyFrame: Uint8Array
  readonly prepared: PreparedArchive
  readonly directoryIdentities: {
    readonly runnerTemp: DirectoryIdentity
    readonly session: DirectoryIdentity
    readonly upload: DirectoryIdentity
    readonly evidence: DirectoryIdentity
  }
  readonly server: Server
  readonly sockets: Set<Socket>
  readonly firstConnection: Promise<AcceptedConnection>
  readonly closeCompletion: Promise<void>
  readonly capability: object
}

const ROOT_CAPABILITIES = new WeakMap<
  object,
  Readonly<{
    binding: S2STestOnlyHostedProcessBinding
    preparedSha256: string
  }>
>()

const listen = async (
  paths: S2STestOnlyHostedProcessPaths
): Promise<{
  readonly server: Server
  readonly sockets: Set<Socket>
  readonly firstConnection: Promise<AcceptedConnection>
  readonly closeCompletion: Promise<void>
}> => {
  const sockets = new Set<Socket>()
  let resolveFirst: ((connection: AcceptedConnection) => void) | undefined
  let rejectFirst: ((error: unknown) => void) | undefined
  const firstConnection = new Promise<AcceptedConnection>((resolveConnection, rejectConnection) => {
    resolveFirst = resolveConnection
    rejectFirst = rejectConnection
  })
  let consumed = false
  const server = createServer({ allowHalfOpen: true }, (socket) => {
    sockets.add(socket)
    socket.on("error", () => undefined)
    socket.once("close", () => sockets.delete(socket))
    if (consumed || resolveFirst === undefined) {
      socket.destroy()
      return
    }
    consumed = true
    if (server.listening) server.close()
    void unlink(paths.socketPath).catch(() => undefined)
    void readOneFrame(socket).then(resolveFirst)
  })
  const closeCompletion = new Promise<void>((resolveClose) => {
    server.once("close", () => resolveClose())
  })
  server.maxConnections = 1
  let started = false
  const persistentError = (error: Error): void => {
    if (consumed || rejectFirst === undefined) return
    consumed = true
    if (server.listening) server.close()
    void unlink(paths.socketPath).catch(() => undefined)
    rejectFirst(ioError("LISTEN", error, "listening server failed"))
  }
  try {
    await new Promise<void>((resolveListen, rejectListen) => {
      server.once("error", rejectListen)
      server.listen({ path: paths.socketPath, backlog: 1 }, () => {
        server.removeListener("error", rejectListen)
        started = true
        resolveListen()
      })
    })
    server.on("error", persistentError)
    await chmod(paths.socketPath, 0o600)
    const socketStat = await lstat(paths.socketPath)
    if (
      !socketStat.isSocket() ||
      socketStat.uid !== effectiveUid() ||
      (socketStat.mode & 0o777) !== 0o600
    ) {
      throw runtimeError(
        "LISTEN",
        "SOCKET_POLICY_REJECTED",
        "Unix socket violates type, owner, or mode policy"
      )
    }
    return Object.freeze({
      server,
      sockets,
      firstConnection,
      closeCompletion
    })
  } catch (error) {
    for (const socket of sockets) socket.destroy()
    if (server.listening) {
      server.close()
    }
    if (started) await closeCompletion.catch(() => undefined)
    await unlink(paths.socketPath).catch(() => undefined)
    server.removeListener("error", persistentError)
    throw error
  }
}

const acquireRoot = async (
  input: S2STestOnlyHostedProcessRootInput
): Promise<RootResource> => {
  const paths = await resolvePaths(input)
  let sessionCreated = false
  let token: Uint8Array | undefined
  let listening:
    | Awaited<ReturnType<typeof listen>>
    | undefined
  try {
    await mkdir(paths.sessionPath, { mode: 0o700 })
    sessionCreated = true
    await mkdir(paths.uploadPath, { mode: 0o700 })
    await mkdir(paths.evidencePath, { mode: 0o700 })
    const runnerTempIdentity = await assertPrivateDirectory(
      paths.runnerTempPath,
      Object.freeze({
        device: paths.runnerTempDevice,
        inode: paths.runnerTempInode
      })
    )
    const sessionIdentity = await assertPrivateDirectory(paths.sessionPath)
    const uploadIdentity = await assertPrivateDirectory(paths.uploadPath)
    const evidenceIdentity = await assertPrivateDirectory(paths.evidencePath)

    const prepared = await prepareStructuralArchive(input, paths)
    token = new Uint8Array(randomBytes(32))
    const nonce = randomBytes(32).toString("hex")
    const instanceId = randomBytes(32).toString("hex")
    const runtimeIdentity = await observeRuntimeIdentity(instanceId, process.pid)
    const bindingResult = makeS2STestOnlyHostedProcessBinding({
      protocolVersion: S2S_TEST_ONLY_HOSTED_PROCESS_PROTOCOL_VERSION,
      nonce,
      workflowRunId: input.workflowRunId,
      workflowRunAttempt: input.workflowRunAttempt,
      feasibilityAttempt: input.feasibilityAttempt,
      stage: input.stage,
      jobId: input.jobId,
      runtimeIdentity
    })
    if (Either.isLeft(bindingResult)) {
      throw runtimeError(
        "PREPARE",
        "ROOT_IDENTITY_DRIFT",
        "root binding construction failed"
      )
    }
    const binding = bindingResult.right
    const readyResult = makeS2STestOnlyHostedProcessReady(
      binding,
      token,
      rawS2SFileSha256(token)
    )
    if (Either.isLeft(readyResult)) {
      throw runtimeError(
        "PREPARE",
        "AUTHENTICATION_FAILED",
        "ready authentication construction failed"
      )
    }
    const ready = readyResult.right
    const readyFrameResult = canonicalS2STestOnlyHostedProcessFrame(ready, "READY")
    if (Either.isLeft(readyFrameResult)) {
      throw runtimeError(
        "PREPARE",
        "FRAME_REJECTED",
        "ready frame construction failed"
      )
    }
    listening = await listen(paths)
    await writeExclusiveFile(paths.tokenPath, token, "READY")
    await writeExclusiveFile(paths.readyPath, readyFrameResult.right, "READY")
    const capability = Object.freeze({})
    ROOT_CAPABILITIES.set(
      capability,
      Object.freeze({ binding, preparedSha256: prepared.snapshot.sha256 })
    )
    return Object.freeze({
      paths,
      input,
      token,
      binding,
      ready,
      readyFrame: readyFrameResult.right,
      prepared,
      directoryIdentities: Object.freeze({
        runnerTemp: runnerTempIdentity,
        session: sessionIdentity,
        upload: uploadIdentity,
        evidence: evidenceIdentity
      }),
      server: listening.server,
      sockets: listening.sockets,
      firstConnection: listening.firstConnection,
      closeCompletion: listening.closeCompletion,
      capability
    })
  } catch (error) {
    let cleanupFailure: unknown = null
    try {
      if (listening !== undefined) {
        for (const socket of listening.sockets) socket.destroy()
        if (listening.server.listening) listening.server.close()
        await listening.closeCompletion
      }
      if (sessionCreated) {
        for (const directory of [
          paths.sessionPath,
          paths.uploadPath,
          paths.evidencePath
        ]) {
          try {
            await chmod(directory, 0o700)
          } catch (chmodError) {
            if (!hasCode(chmodError) || chmodError.code !== "ENOENT") {
              throw chmodError
            }
          }
        }
        await rm(paths.sessionPath, {
          recursive: true,
          force: true,
          maxRetries: 2,
          retryDelay: 25
        })
      }
    } catch (cleanupError) {
      cleanupFailure = cleanupError
    } finally {
      token?.fill(0)
    }
    if (cleanupFailure !== null) {
      throw ioError(
        "CLEANUP",
        cleanupFailure,
        "partial root acquisition cleanup failed"
      )
    }
    throw error
  }
}

const waitForFirstConnection = (
  resource: RootResource,
  signal: AbortSignal
): Promise<AcceptedConnection> =>
  new Promise((resolveConnection, rejectConnection) => {
    let settled = false
    let timeout: NodeJS.Timeout
    const finish = (
      connection: AcceptedConnection | null,
      error: unknown | null
    ): void => {
      if (settled) return
      settled = true
      clearTimeout(timeout)
      signal.removeEventListener("abort", abort)
      if (connection !== null) resolveConnection(connection)
      else rejectConnection(error)
    }
    const abort = (): void => {
      finish(
        null,
        runtimeError(
          "RECONCILE",
          "REPLAY_REJECTED",
          "owning Effect root was interrupted"
        )
      )
    }
    timeout = setTimeout(() => {
      finish(
        null,
        runtimeError(
          "RECONCILE",
          "SESSION_TIMED_OUT",
          "no one-shot reconcile connection arrived within 900 seconds"
        )
      )
    }, S2S_TEST_ONLY_HOSTED_PROCESS_SESSION_TIMEOUT_MILLIS)
    signal.addEventListener("abort", abort, { once: true })
    if (signal.aborted) abort()
    void resource.firstConnection.then(
      (connection) => finish(connection, null),
      (error: unknown) => finish(null, error)
    )
  })

const writeSocketResponse = (
  socket: Socket,
  frame: Uint8Array
): Promise<void> =>
  new Promise((resolveWrite, rejectWrite) => {
    let settled = false
    const finish = (error: S2STestOnlyHostedProcessRuntimeError | null): void => {
      if (settled) return
      settled = true
      clearTimeout(timeout)
      if (error === null) resolveWrite()
      else rejectWrite(error)
    }
    const timeout = setTimeout(() => {
      socket.destroy()
      finish(
        runtimeError(
          "TERMINAL",
          "TERMINAL_DELIVERY_UNKNOWN",
          "terminal response write timed out"
        )
      )
    }, S2S_TEST_ONLY_HOSTED_PROCESS_FRAME_TIMEOUT_MILLIS)
    socket.once("error", () => {
      finish(
        runtimeError(
          "TERMINAL",
          "TERMINAL_DELIVERY_UNKNOWN",
          "terminal response delivery failed"
        )
      )
    })
    socket.end(frame, () => {
      finish(null)
    })
  })

const terminalStatus = (
  outcome: S2STestOnlyHostedProcessUploadStepOutcome
):
  | "RECONCILED_ACTION_SUCCESS"
  | "RECONCILED_ACTION_FAILURE"
  | "RECONCILED_ACTION_UNKNOWN_NO_RETRY" =>
  outcome === "success"
    ? "RECONCILED_ACTION_SUCCESS"
    : outcome === "unknown"
      ? "RECONCILED_ACTION_UNKNOWN_NO_RETRY"
      : "RECONCILED_ACTION_FAILURE"

const consumeControlFiles = async (resource: RootResource): Promise<void> => {
  await rename(resource.paths.readyPath, resource.paths.consumedReadyPath)
  await unlink(resource.paths.tokenPath)
}

const preparedArchiveUnchanged = async (
  prepared: PreparedArchive
): Promise<boolean> => {
  try {
    const current = await readPrivateRegularFile(
      prepared.path,
      prepared.snapshot.byteLength,
      prepared.snapshot.byteLength,
      "RECONCILE"
    )
    return (
      current.device === prepared.snapshot.device &&
      current.inode === prepared.snapshot.inode &&
      current.byteLength === prepared.snapshot.byteLength &&
      current.sha256 === prepared.snapshot.sha256
    )
  } catch {
    return false
  }
}

interface OccurrenceSeed {
  readonly binding: S2STestOnlyHostedProcessBinding
  readonly preparedLogicalName: string
  readonly preparedSha256: string
  readonly preparedByteLength: number
  readonly readyFrameSha256: string
  readonly terminalFrameSha256: string
  readonly outcome: S2STestOnlyHostedProcessUploadStepOutcome
}

const makeOccurrenceBytes = (seed: OccurrenceSeed): Uint8Array => {
  const core = Object.freeze({
    schema_version:
      "hswm-swm0w-s2s-test-only-hosted-process-occurrence/v1",
    classification: S2S_TEST_ONLY_HOSTED_PROCESS_CLASSIFICATION,
    claim_scope: "HOSTED_PROCESS_CONTINUITY_MECHANICS_ONLY",
    binding: seed.binding,
    prepared_archive: Object.freeze({
      logical_name: seed.preparedLogicalName,
      raw_sha256: seed.preparedSha256,
      byte_length: seed.preparedByteLength,
      structural_shape_only: true
    }),
    ready_frame_sha256: seed.readyFrameSha256,
    terminal_frame_sha256: seed.terminalFrameSha256,
    publisher_diagnostic: seed.outcome,
    publisher_diagnostic_used_as_authority: false,
    publication_retry_count: 0,
    same_effect_root_process_observed: true,
    production_authority_claimed: false,
    production_completion_claimed: false,
    external_exactly_once_claimed: false,
    scientific_result_claimed: false,
    causal_learning_claimed: false
  })
  const receipt = canonicalS2SControlSha256(core)
  if (Either.isLeft(receipt) || !SHA256_PATTERN.test(receipt.right)) {
    throw runtimeError(
      "TERMINAL",
      "FRAME_REJECTED",
      "occurrence receipt construction failed"
    )
  }
  const bytes = canonicalS2SControlJsonBytes(
    Object.freeze({ ...core, receipt_sha256: receipt.right })
  )
  if (Either.isLeft(bytes)) {
    throw runtimeError(
      "TERMINAL",
      "FRAME_REJECTED",
      "occurrence evidence encoding failed"
    )
  }
  return bytes.right
}

const assertRootDirectoryIdentities = async (
  resource: RootResource
): Promise<void> => {
  await assertPrivateDirectory(
    resource.paths.runnerTempPath,
    resource.directoryIdentities.runnerTemp,
    "RECONCILE"
  )
  await assertPrivateDirectory(
    resource.paths.sessionPath,
    resource.directoryIdentities.session,
    "RECONCILE"
  )
  await assertPrivateDirectory(
    resource.paths.uploadPath,
    resource.directoryIdentities.upload,
    "RECONCILE"
  )
  await assertPrivateDirectory(
    resource.paths.evidencePath,
    resource.directoryIdentities.evidence,
    "RECONCILE"
  )
}

const completeRoot = async (
  resource: RootResource,
  connection: AcceptedConnection
): Promise<S2STestOnlyHostedProcessTerminal> => {
  let reconcileOutcome: S2STestOnlyHostedProcessUploadStepOutcome | null = null
  let rejectedReason: S2STestOnlyHostedProcessRuntimeError["reason"] =
    connection.errorReason ?? "FRAME_REJECTED"
  if (connection.frame !== null) {
    const decoded = decodeS2STestOnlyHostedProcessReconcileFrame(
      connection.frame,
      resource.binding,
      resource.token
    )
    if (Either.isRight(decoded)) {
      reconcileOutcome = decoded.right.uploadStepOutcome
    } else {
      rejectedReason =
        decoded.left.reason === "AUTHENTICATION_FAILED"
          ? "AUTHENTICATION_FAILED"
          : decoded.left.reason === "BINDING_MISMATCH"
            ? "BINDING_MISMATCH"
            : "FRAME_REJECTED"
    }
  }

  await assertRootDirectoryIdentities(resource)
  await consumeControlFiles(resource)

  const capability = ROOT_CAPABILITIES.get(resource.capability)
  const capabilityAuthentic =
    capability !== undefined &&
    capability.binding === resource.binding &&
    capability.preparedSha256 === resource.prepared.snapshot.sha256
  const runtimeAuthentic = await runtimeIdentityMatches(
    resource.binding.runtimeIdentity
  )
  const preparedAuthentic = await preparedArchiveUnchanged(resource.prepared)

  const accepted =
    reconcileOutcome !== null &&
    capabilityAuthentic &&
    runtimeAuthentic &&
    preparedAuthentic
  const outcome = reconcileOutcome ?? "unknown"
  const status = accepted ? terminalStatus(outcome) : "VOID_NO_COMPLETION"
  const terminalResult = makeS2STestOnlyHostedProcessTerminal(
    resource.binding,
    outcome,
    status,
    accepted ? 1 : 0,
    resource.token
  )
  if (Either.isLeft(terminalResult)) {
    throw runtimeError(
      "TERMINAL",
      "AUTHENTICATION_FAILED",
      "terminal authentication construction failed"
    )
  }
  const terminal = terminalResult.right
  const terminalFrameResult = canonicalS2STestOnlyHostedProcessFrame(
    terminal,
    "TERMINAL"
  )
  if (Either.isLeft(terminalFrameResult)) {
    throw runtimeError(
      "TERMINAL",
      "FRAME_REJECTED",
      "terminal frame construction failed"
    )
  }
  const terminalFrame = terminalFrameResult.right
  const occurrenceBytes = makeOccurrenceBytes({
    binding: resource.binding,
    preparedLogicalName: resource.prepared.logicalName,
    preparedSha256: resource.prepared.snapshot.sha256,
    preparedByteLength: resource.prepared.snapshot.byteLength,
    readyFrameSha256: rawS2SFileSha256(resource.readyFrame),
    terminalFrameSha256: rawS2SFileSha256(terminalFrame),
    outcome
  })
  await writeExclusiveFile(
    resource.paths.occurrencePath,
    occurrenceBytes,
    "TERMINAL"
  )
  await writeExclusiveFile(resource.paths.terminalPath, terminalFrame, "TERMINAL")
  await writeSocketResponse(connection.socket, terminalFrame)
  if (!accepted) {
    throw runtimeError(
      "RECONCILE",
      reconcileOutcome === null
        ? rejectedReason
        : !runtimeAuthentic || !capabilityAuthentic
          ? "ROOT_IDENTITY_DRIFT"
          : "PREPARED_FILES_DRIFTED",
      "one-shot session terminated without feasibility completion"
    )
  }
  return terminal
}

const closeServer = async (resource: RootResource): Promise<void> => {
  if (resource.server.listening) resource.server.close()
  await resource.closeCompletion
  resource.server.removeAllListeners("error")
}

const unlinkIfPresent = async (path: string): Promise<void> => {
  try {
    await unlink(path)
  } catch (error) {
    if (!hasCode(error) || error.code !== "ENOENT") throw error
  }
}

const releaseRoot = async (resource: RootResource): Promise<void> => {
  let firstFailure: unknown = null
  const attempt = async (operation: () => Promise<void>): Promise<void> => {
    try {
      await operation()
    } catch (error) {
      if (firstFailure === null) firstFailure = error
    }
  }
  try {
    for (const socket of resource.sockets) socket.destroy()
    await attempt(() => closeServer(resource))
    await attempt(() => unlinkIfPresent(resource.paths.socketPath))
    await attempt(() => unlinkIfPresent(resource.paths.tokenPath))
    await attempt(() => unlinkIfPresent(resource.paths.readyPath))
  } finally {
    ROOT_CAPABILITIES.delete(resource.capability)
    resource.token.fill(0)
  }
  if (firstFailure !== null) throw firstFailure
}

/**
 * One scoped, package-internal Effect root for test-only hosted continuity.
 * It never imports or issues production current-run, prepared-carrier,
 * assertion, completion, replay, preregistration, or scientific authority.
 */
export const runS2STestOnlyHostedProcessRoot = (
  input: unknown
): Effect.Effect<
  S2STestOnlyHostedProcessTerminal,
  S2STestOnlyHostedProcessRuntimeError
> =>
  Effect.suspend(() => {
    const decoded = decodeInput(input)
    if (Either.isLeft(decoded)) return Effect.fail(decoded.left)
    const acquire = Effect.tryPromise({
      try: () => acquireRoot(decoded.right),
      catch: (error) => ioError("ALLOCATE", error, "root acquisition failed")
    })
    return Effect.acquireUseRelease(
      acquire,
      (resource) =>
        Effect.uninterruptibleMask((restore) =>
          restore(
            Effect.tryPromise({
              try: (signal) => waitForFirstConnection(resource, signal),
              catch: (error) =>
                ioError("RECONCILE", error, "root connection wait failed")
            })
          ).pipe(
            Effect.flatMap((connection) =>
              Effect.tryPromise({
                try: () => completeRoot(resource, connection),
                catch: (error) =>
                  ioError("RECONCILE", error, "root reconciliation failed")
              })
            )
          )
        ),
      (resource) =>
        Effect.tryPromise({
          try: () => releaseRoot(resource),
          catch: (error) => ioError("CLEANUP", error, "root cleanup failed")
        }).pipe(Effect.orDie)
    ).pipe(Effect.scoped)
  })

const assertPathAbsent = async (path: string, detail: string): Promise<void> => {
  try {
    await lstat(path)
  } catch (error) {
    if (hasCode(error) && error.code === "ENOENT") return
    throw error
  }
  throw runtimeError("READY", "REPLAY_REJECTED", detail)
}

const abortableDelay = (
  delayMillis: number,
  signal: AbortSignal
): Promise<void> =>
  new Promise((resolveDelay, rejectDelay) => {
    let settled = false
    const finish = (interrupted: boolean): void => {
      if (settled) return
      settled = true
      clearTimeout(timeout)
      signal.removeEventListener("abort", abort)
      if (interrupted) {
        rejectDelay(
          runtimeError(
            "READY",
            "REPLAY_REJECTED",
            "client observation was interrupted"
          )
        )
      } else {
        resolveDelay()
      }
    }
    const abort = (): void => finish(true)
    const timeout = setTimeout(() => finish(false), delayMillis)
    signal.addEventListener("abort", abort, { once: true })
    if (signal.aborted) abort()
  })

const readReadyAndToken = async (
  input: S2STestOnlyHostedProcessClientInput,
  timeoutMillis: number,
  signal: AbortSignal
): Promise<{
  readonly paths: S2STestOnlyHostedProcessPaths
  readonly token: Uint8Array
  readonly readyFrame: Uint8Array
  readonly ready: S2STestOnlyHostedProcessReady
}> => {
  const paths = await resolvePaths(input)
  const deadline = Date.now() + timeoutMillis
  while (true) {
    try {
      if (signal.aborted) {
        throw runtimeError(
          "READY",
          "REPLAY_REJECTED",
          "client observation was interrupted"
        )
      }
      await assertPrivateDirectory(
        paths.runnerTempPath,
        Object.freeze({
          device: paths.runnerTempDevice,
          inode: paths.runnerTempInode
        }),
        "READY"
      )
      await assertPrivateDirectory(paths.sessionPath, null, "READY")
      await assertPrivateDirectory(paths.uploadPath, null, "READY")
      await assertPrivateDirectory(paths.evidencePath, null, "READY")
      await assertPathAbsent(
        paths.terminalPath,
        "the one-shot session is already terminal"
      )
      await assertPathAbsent(
        paths.consumedReadyPath,
        "the one-shot READY record was already consumed"
      )
      const tokenSnapshot = await readPrivateRegularFile(paths.tokenPath, 32, 32)
      let transferred = false
      try {
        const readySnapshot = await readPrivateRegularFile(
          paths.readyPath,
          S2S_TEST_ONLY_HOSTED_PROCESS_MAX_FRAME_BYTES
        )
        const decoded = decodeS2STestOnlyHostedProcessReadyFrame(
          readySnapshot.bytes,
          tokenSnapshot.bytes
        )
        if (Either.isLeft(decoded)) {
          throw runtimeError(
            "READY",
            decoded.left.reason === "AUTHENTICATION_FAILED"
              ? "AUTHENTICATION_FAILED"
              : "FRAME_REJECTED",
            "ready frame failed authentication or schema validation"
          )
        }
        const ready = decoded.right
        if (
          ready.binding.workflowRunId !== input.workflowRunId ||
          ready.binding.workflowRunAttempt !== input.workflowRunAttempt ||
          ready.binding.feasibilityAttempt !== input.feasibilityAttempt ||
          ready.binding.stage !== input.stage ||
          ready.binding.jobId !== input.jobId ||
          !(await runtimeIdentityMatches(ready.binding.runtimeIdentity))
        ) {
          throw runtimeError(
            "READY",
            "BINDING_MISMATCH",
            "ready binding or live root runtime does not match the client expectation"
          )
        }
        const socketStat = await lstat(paths.socketPath)
        if (
        !socketStat.isSocket() ||
        socketStat.uid !== effectiveUid() ||
          (socketStat.mode & 0o777) !== 0o600
        ) {
          throw runtimeError(
            "READY",
            "SOCKET_POLICY_REJECTED",
            "ready socket violates type, owner, or mode policy"
          )
        }
        transferred = true
        return Object.freeze({
          paths,
          token: tokenSnapshot.bytes,
          readyFrame: readySnapshot.bytes,
          ready
        })
      } finally {
        if (!transferred) tokenSnapshot.bytes.fill(0)
      }
    } catch (error) {
      if (
        error instanceof S2STestOnlyHostedProcessRuntimeError &&
        error.reason !== "IO_FAILED"
      ) {
        throw error
      }
      if (Date.now() >= deadline) {
        throw runtimeError(
          "READY",
          "SESSION_TIMED_OUT",
          "ready/token/socket did not appear within the bounded wait"
        )
      }
      await abortableDelay(100, signal)
    }
  }
}

export const awaitS2STestOnlyHostedProcessReady = (
  input: unknown
): Effect.Effect<
  S2STestOnlyHostedProcessReadyObservation,
  S2STestOnlyHostedProcessRuntimeError
> =>
  Effect.suspend(() => {
    const decoded = decodeInput(input)
    if (Either.isLeft(decoded)) return Effect.fail(decoded.left)
    return Effect.tryPromise({
      try: async (signal) => {
        const observed = await readReadyAndToken(
          decoded.right,
          S2S_TEST_ONLY_HOSTED_PROCESS_READY_TIMEOUT_MILLIS,
          signal
        )
        try {
          return Object.freeze({
            ready: observed.ready,
            paths: observed.paths,
            readyFrameSha256: rawS2SFileSha256(observed.readyFrame)
          })
        } finally {
          observed.token.fill(0)
        }
      },
      catch: (error) => ioError("READY", error, "ready observation failed")
    })
  })

const exchangeOneFrame = async (
  socketPath: string,
  request: Uint8Array,
  signal: AbortSignal
): Promise<Uint8Array> =>
  new Promise((resolveResponse, rejectResponse) => {
    const socket = createConnection(socketPath)
    const chunks: Array<Uint8Array> = []
    let total = 0
    let settled = false
    const cleanup = (): void => {
      clearTimeout(timeout)
      signal.removeEventListener("abort", onAbort)
      socket.removeListener("connect", onConnect)
      socket.removeListener("data", onData)
      socket.removeListener("end", onEnd)
      socket.removeListener("error", onError)
    }
    const finish = (
      output: Uint8Array | null,
      error: S2STestOnlyHostedProcessRuntimeError | null
    ): void => {
      if (settled) return
      settled = true
      cleanup()
      if (output !== null) {
        resolveResponse(output)
      } else {
        socket.destroy()
        rejectResponse(error)
      }
    }
    const onConnect = (): void => {
      if (signal.aborted) {
        onAbort()
        return
      }
      socket.end(request)
    }
    const onData = (chunk: Buffer): void => {
      total += chunk.byteLength
      if (total > S2S_TEST_ONLY_HOSTED_PROCESS_MAX_FRAME_BYTES) {
        finish(
          null,
          runtimeError(
            "RECONCILE",
            "FRAME_LIMIT_EXCEEDED",
            "terminal response exceeded the frame bound"
          )
        )
        return
      }
      chunks.push(new Uint8Array(chunk))
    }
    const onEnd = (): void => {
      const output = new Uint8Array(total)
      let offset = 0
      for (const chunk of chunks) {
        output.set(chunk, offset)
        offset += chunk.byteLength
      }
      finish(output, null)
    }
    const onError = (error: Error): void =>
      finish(null, ioError("RECONCILE", error, "socket exchange failed"))
    const onAbort = (): void =>
      finish(
        null,
        runtimeError(
          "RECONCILE",
          "REPLAY_REJECTED",
          "client exchange was interrupted after possible request delivery"
        )
      )
    const timeout = setTimeout(
      () =>
        finish(
          null,
          runtimeError(
            "RECONCILE",
            "FRAME_TIMED_OUT",
            "one-shot client exchange timed out"
          )
        ),
      S2S_TEST_ONLY_HOSTED_PROCESS_FRAME_TIMEOUT_MILLIS
    )
    socket.once("connect", onConnect)
    socket.on("data", onData)
    socket.once("end", onEnd)
    socket.once("error", onError)
    signal.addEventListener("abort", onAbort, { once: true })
    if (signal.aborted) onAbort()
  })

export const reconcileS2STestOnlyHostedProcess = (
  input: unknown,
  outcome: unknown
): Effect.Effect<
  S2STestOnlyHostedProcessReconcileObservation,
  S2STestOnlyHostedProcessRuntimeError
> =>
  Effect.suspend(() => {
    const decoded = decodeInput(input)
    if (Either.isLeft(decoded)) return Effect.fail(decoded.left)
    let decodedOutcome: Either.Either<
      S2STestOnlyHostedProcessUploadStepOutcome,
      unknown
    >
    try {
      decodedOutcome = Schema.decodeUnknownEither(
        Schema.Literal("success", "failure", "cancelled", "skipped", "unknown")
      )(outcome)
    } catch {
      decodedOutcome = Either.left("outcome inspection failed")
    }
    if (Either.isLeft(decodedOutcome)) {
      return Effect.fail(
        runtimeError(
          "INPUT",
          "INPUT_REJECTED",
          "upload step outcome diagnostic was rejected"
        )
      )
    }
    return Effect.tryPromise({
      try: async (signal) => {
        const observed = await readReadyAndToken(
          decoded.right,
          S2S_TEST_ONLY_HOSTED_PROCESS_READY_TIMEOUT_MILLIS,
          signal
        )
        try {
          const request = makeS2STestOnlyHostedProcessReconcileFrame(
            observed.ready,
            decodedOutcome.right,
            observed.token
          )
          if (Either.isLeft(request)) {
            throw runtimeError(
              "RECONCILE",
              "FRAME_REJECTED",
              "reconcile request construction failed"
            )
          }
          const response = await exchangeOneFrame(
            observed.paths.socketPath,
            request.right,
            signal
          )
          const terminal = decodeS2STestOnlyHostedProcessTerminalFrame(
            response,
            observed.ready.binding,
            observed.token
          )
          if (Either.isLeft(terminal)) {
            throw runtimeError(
              "TERMINAL",
              terminal.left.reason === "AUTHENTICATION_FAILED"
                ? "AUTHENTICATION_FAILED"
                : terminal.left.reason === "BINDING_MISMATCH"
                  ? "BINDING_MISMATCH"
                  : "FRAME_REJECTED",
              "terminal response failed authentication or binding validation"
            )
          }
          if (
            terminal.right.terminalStatus === "VOID_NO_COMPLETION" ||
            terminal.right.reconciliationProbeCount !== 1
          ) {
            throw runtimeError(
              "TERMINAL",
              "FRAME_REJECTED",
              "root returned a non-completing feasibility terminal"
            )
          }
          await assertPrivateDirectory(observed.paths.sessionPath, null, "TERMINAL")
          await assertPrivateDirectory(observed.paths.uploadPath, null, "TERMINAL")
          await assertPrivateDirectory(observed.paths.evidencePath, null, "TERMINAL")
          const persisted = await readPrivateRegularFile(
            observed.paths.terminalPath,
            S2S_TEST_ONLY_HOSTED_PROCESS_MAX_FRAME_BYTES,
            null,
            "TERMINAL"
          )
          if (
            persisted.sha256 !== rawS2SFileSha256(response) ||
            persisted.byteLength !== response.byteLength
          ) {
            throw runtimeError(
              "TERMINAL",
              "TERMINAL_DELIVERY_UNKNOWN",
              "persisted and delivered terminal frames differ"
            )
          }
          const spec = S2S_STAGE_ARTIFACT_SPECS[observed.ready.binding.stage]
          const prepared = await readPrivateRegularFile(
            join(observed.paths.uploadPath, basename(spec.archiveLogicalName)),
            spec.maximumArchiveBytes,
            null,
            "TERMINAL"
          )
          const expectedOccurrence = makeOccurrenceBytes({
            binding: observed.ready.binding,
            preparedLogicalName: spec.archiveLogicalName,
            preparedSha256: prepared.sha256,
            preparedByteLength: prepared.byteLength,
            readyFrameSha256: rawS2SFileSha256(observed.readyFrame),
            terminalFrameSha256: rawS2SFileSha256(response),
            outcome: decodedOutcome.right
          })
          const occurrence = await readPrivateRegularFile(
            observed.paths.occurrencePath,
            S2S_TEST_ONLY_HOSTED_PROCESS_OCCURRENCE_MAX_BYTES,
            null,
            "TERMINAL"
          )
          if (
            occurrence.byteLength !== expectedOccurrence.byteLength ||
            occurrence.sha256 !== rawS2SFileSha256(expectedOccurrence)
          ) {
            throw runtimeError(
              "TERMINAL",
              "TERMINAL_DELIVERY_UNKNOWN",
              "committed occurrence does not bind the delivered terminal"
            )
          }
          return Object.freeze({
            terminal: terminal.right,
            paths: observed.paths,
            readyFrameSha256: rawS2SFileSha256(observed.readyFrame),
            terminalFrameSha256: rawS2SFileSha256(response)
          })
        } finally {
          observed.token.fill(0)
        }
      },
      catch: (error) =>
        ioError("RECONCILE", error, "one-shot reconciliation failed")
    })
  })

export const s2sTestOnlyHostedProcessSessionPath = (
  runnerTempPath: string,
  sessionName: string
): string => resolve(runnerTempPath, sessionName)

export const s2sTestOnlyHostedProcessUploadPath = (
  runnerTempPath: string,
  sessionName: string
): string =>
  join(
    s2sTestOnlyHostedProcessSessionPath(runnerTempPath, sessionName),
    S2S_TEST_ONLY_HOSTED_PROCESS_UPLOAD_DIRECTORY
  )

export type {
  S2SConfirmatoryJobId,
  S2SConfirmatoryJobStage
}
