import { constants } from "node:fs"
import {
  chmod,
  lstat,
  mkdtemp,
  open,
  realpath,
  rm,
  type FileHandle
} from "node:fs/promises"
import { tmpdir } from "node:os"
import { isAbsolute, join, resolve } from "node:path"

import { Context, Data, Effect, Either, Layer } from "effect"

import {
  canonicalS2SControlJsonBytes,
  rawS2SFileSha256
} from "./s2s-canonical.js"
import {
  runS2SBoundedProcess,
  type S2SBoundedProcessError
} from "./s2s-bounded-process.js"
import { S2SSha256Schema, type S2SSha256 } from "./s2s-confirmatory.js"

export const S2S_NUMERIC_ORACLE_SOURCE_SHA256 =
  "27854351f642727dc21ec63e987bf3ae67a205f4664f5e0ad448eb3b7a8c570b" as const
export const S2S_NUMERIC_GOLDEN_VECTOR_SCHEMA_VERSION =
  "hswm-swm0w-s2s-numeric-golden-vector/v1" as const
export const S2S_NUMERIC_GOLDEN_VECTOR_DOCUMENT_SHA256 =
  "ae30799cc30eb146f69b8884aac1c137ec3fc34e835bcb009351f3889697cf43" as const
export const S2S_NUMERIC_GOLDEN_VECTOR_RECEIPT_SHA256 =
  "c6f487a192177adf654fada8dca9b8768391fb9f2e39a6b50214db557439618f" as const
export const S2S_NUMERIC_GOLDEN_VECTOR_BYTE_LENGTH = 5_795 as const
export const S2S_NUMERIC_GOLDEN_TIMEOUT_MILLIS = 120_000 as const

const NUMERIC_ORACLE_RELATIVE_PATH =
  "src/hswm/experiments/swm0w_s2s_numeric_oracle.py"
const NUMERIC_SOURCE_MAX_BYTES = 1_048_576
const PYTHON_EXECUTABLE_MAX_BYTES = 128 * 1_048_576
const GOLDEN_STDERR_MAX_BYTES = 8_192
const PYTHON_RUNTIME_PROBE = [
  "import os,sys",
  "from hswm.experiments import swm0w_s2s_numeric_oracle as oracle",
  "version='.'.join(str(part) for part in sys.version_info[:3])",
  "cache_prefix=os.path.realpath(sys.pycache_prefix or '')",
  "sys.stdout.write(version+'\\n'+os.path.realpath(oracle.__file__)+'\\n'+cache_prefix+'\\n')"
].join(";")

// The private cache makes the reviewed top-level oracle source, rather than an
// ambient .pyc, the import input. Imported dependency modules remain unpinned;
// this adapter is a golden compatibility preflight, not numeric-run evidence.
const pythonProcessEnvironment = (
  privatePycacheRoot: string
): Readonly<Record<string, string>> =>
  Object.freeze({
    BLIS_NUM_THREADS: "1",
    LANG: "C",
    LC_ALL: "C",
    MKL_NUM_THREADS: "1",
    NUMEXPR_NUM_THREADS: "1",
    OMP_NUM_THREADS: "1",
    OPENBLAS_NUM_THREADS: "1",
    PATH: "/usr/bin:/bin",
    PYTHONDONTWRITEBYTECODE: "1",
    PYTHONHASHSEED: "0",
    PYTHONNOUSERSITE: "1",
    PYTHONPYCACHEPREFIX: privatePycacheRoot,
    PYTHONUTF8: "1",
    TZ: "UTC",
    VECLIB_MAXIMUM_THREADS: "1"
  })

export interface S2SPythonGoldenProcessConfig {
  readonly repositoryRoot: string
  readonly pythonExecutable: string
  readonly expectedPythonExecutableSha256: string
  readonly expectedPythonVersion: string
}

export interface S2SPythonGoldenVerification {
  readonly schemaVersion: typeof S2S_NUMERIC_GOLDEN_VECTOR_SCHEMA_VERSION
  readonly documentByteLength: typeof S2S_NUMERIC_GOLDEN_VECTOR_BYTE_LENGTH
  readonly rawBytesSha256: S2SSha256
  readonly receiptSha256: S2SSha256
  readonly commandElapsedNanoseconds: number
}

export class S2SPythonGoldenVerificationError extends Data.TaggedError(
  "S2SPythonGoldenVerificationError"
)<{
  readonly reason:
    | "CONFIGURATION_INVALID"
    | "GOLDEN_HASH_MISMATCH"
    | "NONZERO_EXIT"
    | "NUMERIC_SOURCE_DRIFT"
    | "OUTPUT_CONTRACT_REJECTED"
    | "PARTIAL_STDOUT_OBSERVED"
    | "PROCESS_FAILED"
    | "STDERR_CONTRACT_REJECTED"
  readonly exitCode: number | null
  readonly detail: string
}> {}

export class S2SPythonGoldenVerifier extends Context.Tag(
  "hswm/S2S/PythonGoldenVerifier"
)<
  S2SPythonGoldenVerifier,
  {
    readonly verify: Effect.Effect<
      S2SPythonGoldenVerification,
      S2SPythonGoldenVerificationError
    >
  }
>() {}

interface PreparedPythonConfig {
  readonly repositoryRoot: string
  readonly oracleSourcePath: string
  readonly pythonExecutable: string
  readonly pythonExecutableRealPath: string
  readonly expectedPythonExecutableSha256: S2SSha256
  readonly expectedPythonVersion: string
}

interface PinnedPythonExecutable {
  readonly handle: FileHandle
  readonly procExecutablePath: string
}

interface PinnedPythonProcessInvocation {
  readonly operation: string
  readonly arguments: ReadonlyArray<string>
  readonly timeoutMillis: number
  readonly stdoutLimitBytes: number
  readonly stderrLimitBytes: number
}

const verificationError = (
  reason: S2SPythonGoldenVerificationError["reason"],
  detail: string,
  exitCode: number | null = null
): S2SPythonGoldenVerificationError =>
  new S2SPythonGoldenVerificationError({ reason, exitCode, detail })

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((byte, index) => byte === right[index])

const preparePythonConfig = async (
  input: S2SPythonGoldenProcessConfig
): Promise<PreparedPythonConfig> => {
  if (
    !isAbsolute(input.repositoryRoot) ||
    !isAbsolute(input.pythonExecutable) ||
    input.repositoryRoot.includes("\0") ||
    input.pythonExecutable.includes("\0") ||
    !/^[0-9a-f]{64}$/.test(input.expectedPythonExecutableSha256) ||
    !/^[0-9]+\.[0-9]+\.[0-9]+$/.test(input.expectedPythonVersion)
  ) {
    throw verificationError(
      "CONFIGURATION_INVALID",
      "repository root and Python executable must be absolute paths"
    )
  }
  const requestedRoot = resolve(input.repositoryRoot)
  const requestedRootStat = await lstat(requestedRoot)
  if (requestedRootStat.isSymbolicLink() || !requestedRootStat.isDirectory()) {
    throw verificationError(
      "CONFIGURATION_INVALID",
      "repository root must be a plain directory"
    )
  }
  const repositoryRoot = await realpath(requestedRoot)
  const sourceRoot = join(repositoryRoot, "src")
  const sourceRootStat = await lstat(sourceRoot)
  if (sourceRootStat.isSymbolicLink() || !sourceRootStat.isDirectory()) {
    throw verificationError(
      "CONFIGURATION_INVALID",
      "repository source root must be a plain directory"
    )
  }
  const pythonExecutable = resolve(input.pythonExecutable)
  const pythonExecutableRealPath = await realpath(pythonExecutable)
  const pythonStat = await lstat(pythonExecutableRealPath)
  if (!pythonStat.isFile() || (pythonStat.mode & 0o111) === 0) {
    throw verificationError(
      "CONFIGURATION_INVALID",
      "resolved Python executable must be an executable regular file"
    )
  }
  if (
    pythonStat.size < 1 ||
    pythonStat.size > PYTHON_EXECUTABLE_MAX_BYTES
  ) {
    throw verificationError(
      "CONFIGURATION_INVALID",
      "resolved Python executable violates the fixed byte bound"
    )
  }
  const executableHandle = await open(
    pythonExecutableRealPath,
    constants.O_RDONLY | constants.O_NOFOLLOW
  )
  let executableBytes: Uint8Array
  try {
    executableBytes = new Uint8Array(await executableHandle.readFile())
  } finally {
    await executableHandle.close()
  }
  if (
    executableBytes.byteLength !== pythonStat.size ||
    rawS2SFileSha256(executableBytes) !==
      input.expectedPythonExecutableSha256
  ) {
    throw verificationError(
      "CONFIGURATION_INVALID",
      "resolved Python executable differs from its runtime pin"
    )
  }
  return Object.freeze({
    repositoryRoot,
    oracleSourcePath: join(repositoryRoot, NUMERIC_ORACLE_RELATIVE_PATH),
    pythonExecutable,
    pythonExecutableRealPath,
    expectedPythonExecutableSha256: S2SSha256Schema.make(
      input.expectedPythonExecutableSha256
    ),
    expectedPythonVersion: input.expectedPythonVersion
  })
}

const openPinnedPythonExecutable = async (
  config: PreparedPythonConfig
): Promise<PinnedPythonExecutable> => {
  const currentExecutableRealPath = await realpath(config.pythonExecutable)
  if (currentExecutableRealPath !== config.pythonExecutableRealPath) {
    throw verificationError(
      "CONFIGURATION_INVALID",
      "Python executable link target changed"
    )
  }
  const handle = await open(
    config.pythonExecutableRealPath,
    constants.O_RDONLY | constants.O_NOFOLLOW
  )
  try {
    const stat = await handle.stat()
    if (
      !stat.isFile() ||
      stat.size < 1 ||
      stat.size > PYTHON_EXECUTABLE_MAX_BYTES
    ) {
      throw verificationError(
        "CONFIGURATION_INVALID",
        "Python executable identity is no longer bounded"
      )
    }
    const bytes = new Uint8Array(await handle.readFile())
    if (
      bytes.byteLength !== stat.size ||
      rawS2SFileSha256(bytes) !== config.expectedPythonExecutableSha256
    ) {
      throw verificationError(
        "CONFIGURATION_INVALID",
        "opened Python executable inode differs from its runtime pin"
      )
    }
    if (!Number.isSafeInteger(handle.fd) || handle.fd < 0) {
      throw verificationError(
        "CONFIGURATION_INVALID",
        "opened Python executable has no stable file descriptor"
      )
    }
    return {
      handle,
      procExecutablePath: `/proc/${process.pid}/fd/${handle.fd}`
    }
  } catch (error) {
    await handle.close()
    throw error
  }
}

const runPinnedPythonProcess = (
  config: PreparedPythonConfig,
  privatePycacheRoot: string,
  invocation: PinnedPythonProcessInvocation
) =>
  Effect.acquireUseRelease(
    Effect.tryPromise({
      try: () => openPinnedPythonExecutable(config),
      catch: (error) =>
        error instanceof S2SPythonGoldenVerificationError
          ? error
          : verificationError(
              "CONFIGURATION_INVALID",
              "Python executable inode could not be pinned"
            )
    }),
    (pinned) =>
      runS2SBoundedProcess({
        operation: invocation.operation,
        executable: pinned.procExecutablePath,
        argv0: config.pythonExecutable,
        arguments: invocation.arguments,
        cwd: config.repositoryRoot,
        environment: pythonProcessEnvironment(privatePycacheRoot),
        stdin: null,
        timeoutMillis: invocation.timeoutMillis,
        stdoutLimitBytes: invocation.stdoutLimitBytes,
        stderrLimitBytes: invocation.stderrLimitBytes
      }).pipe(Effect.mapError(mapProcessError)),
    (pinned) =>
      Effect.tryPromise({
        try: () => pinned.handle.close(),
        catch: () =>
          verificationError(
            "CONFIGURATION_INVALID",
            "pinned Python executable handle could not be closed"
          )
      }).pipe(Effect.orDie)
  )

const acquirePrivatePycacheRoot = Effect.acquireRelease(
  Effect.tryPromise({
    try: async () => {
      const path = await mkdtemp(join(tmpdir(), "hswm-s2s-pycache-"))
      try {
        await chmod(path, 0o700)
        const stat = await lstat(path)
        if (
          stat.isSymbolicLink() ||
          !stat.isDirectory() ||
          (stat.mode & 0o077) !== 0
        ) {
          throw verificationError(
            "CONFIGURATION_INVALID",
            "private Python bytecode-cache root is not a private directory"
          )
        }
        return await realpath(path)
      } catch (error) {
        await rm(path, { force: true, recursive: true })
        throw error
      }
    },
    catch: (error) =>
      error instanceof S2SPythonGoldenVerificationError
        ? error
        : verificationError(
            "CONFIGURATION_INVALID",
            "private Python bytecode-cache root could not be created"
          )
  }),
  (path) =>
    Effect.tryPromise({
      try: () => rm(path, { force: true, recursive: true }),
      catch: () =>
        verificationError(
          "CONFIGURATION_INVALID",
          "private Python bytecode-cache root could not be removed"
        )
    }).pipe(Effect.orDie)
)

const readBoundedOracleSource = async (
  path: string
): Promise<Uint8Array> => {
  const flags = constants.O_RDONLY | constants.O_NOFOLLOW
  const handle = await open(path, flags)
  try {
    const stat = await handle.stat()
    if (
      !stat.isFile() ||
      stat.size < 1 ||
      stat.size > NUMERIC_SOURCE_MAX_BYTES
    ) {
      throw verificationError(
        "CONFIGURATION_INVALID",
        "numeric oracle source is not a bounded regular file"
      )
    }
    const bytes = new Uint8Array(await handle.readFile())
    if (bytes.byteLength !== stat.size) {
      throw verificationError(
        "CONFIGURATION_INVALID",
        "numeric oracle source changed during read"
      )
    }
    return bytes
  } finally {
    await handle.close()
  }
}

const assertNumericSource = (
  config: PreparedPythonConfig
): Effect.Effect<void, S2SPythonGoldenVerificationError> =>
  Effect.tryPromise({
    try: async () => {
      const bytes = await readBoundedOracleSource(config.oracleSourcePath)
      if (rawS2SFileSha256(bytes) !== S2S_NUMERIC_ORACLE_SOURCE_SHA256) {
        throw verificationError(
          "NUMERIC_SOURCE_DRIFT",
          "numeric oracle source differs from the reviewed adapter boundary"
        )
      }
    },
    catch: (error) =>
      error instanceof S2SPythonGoldenVerificationError
        ? error
        : verificationError(
            "CONFIGURATION_INVALID",
            "numeric oracle source could not be verified"
          )
  })

const assertPythonRuntime = (
  config: PreparedPythonConfig,
  privatePycacheRoot: string
): Effect.Effect<void, S2SPythonGoldenVerificationError> =>
  Effect.gen(function* () {
    const expectedProbe = new TextEncoder().encode(
      `${config.expectedPythonVersion}\n${config.oracleSourcePath}\n${privatePycacheRoot}\n`
    )
    const probe = yield* runPinnedPythonProcess(config, privatePycacheRoot, {
      operation: "PYTHON_RUNTIME_PROBE",
      arguments: ["-B", "-P", "-s", "-c", PYTHON_RUNTIME_PROBE],
      timeoutMillis: 120_000,
      stdoutLimitBytes: expectedProbe.byteLength,
      stderrLimitBytes: GOLDEN_STDERR_MAX_BYTES
    })
    if (
      probe.exitCode !== 0 ||
      probe.stderr.byteLength !== 0 ||
      !sameBytes(probe.stdout, expectedProbe)
    ) {
      return yield* verificationError(
        "CONFIGURATION_INVALID",
        "Python version, imported numeric-oracle path, or private cache prefix differs from its pin",
        probe.exitCode
      )
    }
  })

const mapProcessError = (
  error: S2SBoundedProcessError
): S2SPythonGoldenVerificationError =>
  verificationError(
    "PROCESS_FAILED",
    `bounded process rejected: ${error.reason}`,
    error.exitCode
  )

const isRecord = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value)

const validateGoldenBytes = (
  bytes: Uint8Array,
  elapsedNanoseconds: number
): Either.Either<
  S2SPythonGoldenVerification,
  S2SPythonGoldenVerificationError
> => {
  if (
    bytes.byteLength !== S2S_NUMERIC_GOLDEN_VECTOR_BYTE_LENGTH ||
    bytes[bytes.byteLength - 1] !== 0x0a ||
    bytes.some((byte) => byte > 0x7f) ||
    bytes
      .subarray(0, bytes.byteLength - 1)
      .some((byte) => byte === 0x0a || byte === 0x0d)
  ) {
    return Either.left(
      verificationError(
        "OUTPUT_CONTRACT_REJECTED",
        "golden output is not one bounded canonical ASCII line"
      )
    )
  }
  const rawHash = rawS2SFileSha256(bytes)
  if (rawHash !== S2S_NUMERIC_GOLDEN_VECTOR_DOCUMENT_SHA256) {
    return Either.left(
      verificationError(
        "GOLDEN_HASH_MISMATCH",
        "golden document bytes differ from the frozen cross-language vector"
      )
    )
  }
  let parsed: unknown
  try {
    parsed = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes))
  } catch {
    return Either.left(
      verificationError(
        "OUTPUT_CONTRACT_REJECTED",
        "golden output is not valid UTF-8 JSON"
      )
    )
  }
  if (
    !isRecord(parsed) ||
    parsed["schema_version"] !== S2S_NUMERIC_GOLDEN_VECTOR_SCHEMA_VERSION ||
    parsed["purpose"] !==
      "CROSS_LANGUAGE_TEST_VECTOR_NOT_CONFIRMATORY_EVIDENCE" ||
    parsed["receipt_sha256"] !== S2S_NUMERIC_GOLDEN_VECTOR_RECEIPT_SHA256
  ) {
    return Either.left(
      verificationError(
        "OUTPUT_CONTRACT_REJECTED",
        "golden output fixed projection disagrees"
      )
    )
  }
  const canonical = canonicalS2SControlJsonBytes(parsed)
  if (Either.isLeft(canonical) || !sameBytes(canonical.right, bytes)) {
    return Either.left(
      verificationError(
        "OUTPUT_CONTRACT_REJECTED",
        "golden output is not the exact canonical JSON encoding"
      )
    )
  }
  return Either.right(
    Object.freeze({
      schemaVersion: S2S_NUMERIC_GOLDEN_VECTOR_SCHEMA_VERSION,
      documentByteLength: S2S_NUMERIC_GOLDEN_VECTOR_BYTE_LENGTH,
      rawBytesSha256: S2SSha256Schema.make(rawHash),
      receiptSha256: S2SSha256Schema.make(
        S2S_NUMERIC_GOLDEN_VECTOR_RECEIPT_SHA256
      ),
      commandElapsedNanoseconds: elapsedNanoseconds
    })
  )
}

export const makeS2SPythonGoldenVerifierProcessLayer = (
  input: S2SPythonGoldenProcessConfig
) => {
  const snapshot = Object.freeze({
    repositoryRoot: input.repositoryRoot,
    pythonExecutable: input.pythonExecutable,
    expectedPythonExecutableSha256: input.expectedPythonExecutableSha256,
    expectedPythonVersion: input.expectedPythonVersion
  })
  return Layer.scoped(
    S2SPythonGoldenVerifier,
    Effect.gen(function* () {
      const privatePycacheRoot = yield* acquirePrivatePycacheRoot
      const config = yield* Effect.tryPromise({
        try: () => preparePythonConfig(snapshot),
        catch: (error) =>
          error instanceof S2SPythonGoldenVerificationError
            ? error
            : verificationError(
                "CONFIGURATION_INVALID",
                "Python golden process configuration could not be resolved"
              )
      })
      yield* assertNumericSource(config)
      yield* assertPythonRuntime(config, privatePycacheRoot)
      return S2SPythonGoldenVerifier.of({
        verify: Effect.gen(function* () {
          yield* assertNumericSource(config)
          yield* assertPythonRuntime(config, privatePycacheRoot)
          const result = yield* runPinnedPythonProcess(
            config,
            privatePycacheRoot,
            {
              operation: "PYTHON_NUMERIC_GOLDEN",
              arguments: [
                "-B",
                "-P",
                "-s",
                "-m",
                "hswm.experiments.swm0w_s2s_numeric_oracle",
                "golden"
              ],
              timeoutMillis: S2S_NUMERIC_GOLDEN_TIMEOUT_MILLIS,
              stdoutLimitBytes: S2S_NUMERIC_GOLDEN_VECTOR_BYTE_LENGTH,
              stderrLimitBytes: GOLDEN_STDERR_MAX_BYTES
            }
          )
          if (result.exitCode !== 0) {
            return yield* verificationError(
              result.stdout.byteLength === 0
                ? "NONZERO_EXIT"
                : "PARTIAL_STDOUT_OBSERVED",
              "Python golden process did not complete cleanly",
              result.exitCode
            )
          }
          if (result.stderr.byteLength !== 0) {
            return yield* verificationError(
              "STDERR_CONTRACT_REJECTED",
              "successful Python golden process emitted stderr",
              result.exitCode
            )
          }
          const verified = validateGoldenBytes(
            result.stdout,
            result.elapsedNanoseconds
          )
          if (Either.isLeft(verified)) return yield* verified.left
          return verified.right
        })
      })
    })
  )
}
