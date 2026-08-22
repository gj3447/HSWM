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
import { isAbsolute, join, relative, resolve, sep } from "node:path"

import { Context, Data, Effect, Either, Layer } from "effect"

import {
  canonicalS2SControlJsonBytes,
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "./s2s-canonical.js"
import {
  runS2SBoundedProcess,
  type S2SBoundedProcessError,
  type S2SBoundedProcessResult
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
export const S2S_NUMERIC_CONFIRM_TIMEOUT_MILLIS = 7_200_000 as const
export const S2S_NUMERIC_ADJUDICATE_TIMEOUT_MILLIS = 1_200_000 as const
export const S2S_NUMERIC_CONFIRM_REQUEST_MAX_BYTES = 65_536 as const
export const S2S_NUMERIC_CANDIDATE_MAX_BYTES = 60 * 1_048_576
export const S2S_NUMERIC_ADJUDICATION_MAX_BYTES = 4 * 1_048_576
export const S2S_NUMERIC_STDERR_MAX_BYTES = 8_192 as const
export const S2S_PYTHON_RUNTIME_SOURCE_IDENTITY_SCHEMA_VERSION =
  "hswm-swm0w-s2s-python-runtime-source-identity/v1" as const

const PYTHON_EXECUTABLE_MAX_BYTES = 128 * 1_048_576
const GOLDEN_STDERR_MAX_BYTES = 8_192
const RUNTIME_PROBE_MAX_BYTES = 32_768
const LOCAL_SOURCE_CLOSURE_MAX_BYTES = 4 * 1_048_576
const PRIVATE_PYCACHE_IDENTITY_VALUE = "SCOPED_PRIVATE_DIRECTORY"
const NUMERIC_ORACLE_MODULE = "hswm.experiments.swm0w_s2s_numeric_oracle"
const NUMERIC_ERROR_SCHEMA_VERSION =
  "hswm-swm0w-s2s-numeric-error/v1" as const
const NUMERIC_CANONICAL_ENCODING =
  "ASCII_CANONICAL_UTF8_JSON_PLUS_SINGLE_LF" as const
const NUMERIC_REJECTED_STATUS =
  "NUMERIC_ORACLE_REJECTED_NO_PARTIAL_OUTPUT" as const
const LOCAL_SOURCE_CLOSURE_SCHEMA_VERSION =
  "hswm-swm0w-s2s-python-local-source-closure/v1" as const

export const S2S_NUMERIC_CONFIRM_ARGUMENTS = Object.freeze([
  "-B",
  "-P",
  "-s",
  "-m",
  NUMERIC_ORACLE_MODULE,
  "confirm"
] as const)
export const S2S_NUMERIC_ADJUDICATE_ARGUMENTS = Object.freeze([
  "-B",
  "-P",
  "-s",
  "-m",
  NUMERIC_ORACLE_MODULE,
  "adjudicate"
] as const)
const S2S_NUMERIC_GOLDEN_ARGUMENTS = Object.freeze([
  "-B",
  "-P",
  "-s",
  "-m",
  NUMERIC_ORACLE_MODULE,
  "golden"
] as const)
const NUMERIC_MODULE_PATHS = Object.freeze({
  "src/hswm/__init__.py": "hswm",
  "src/hswm/experiments/__init__.py": "hswm.experiments",
  "src/hswm/experiments/swm0w_s2s_family.py":
    "hswm.experiments.swm0w_s2s_family",
  "src/hswm/experiments/swm0w_s2s_numeric_oracle.py":
    "hswm.experiments.swm0w_s2s_numeric_oracle",
  "src/hswm/experiments/swm0w_s2s_operator.py":
    "hswm.experiments.swm0w_s2s_operator",
  "src/hswm/experiments/swm0w_s2s_protocol.py":
    "hswm.experiments.swm0w_s2s_protocol",
  "src/hswm/experiments/swm0w_s2s_training.py":
    "hswm.experiments.swm0w_s2s_training",
  "src/hswm/experiments/swm0w_s2s_worlds.py":
    "hswm.experiments.swm0w_s2s_worlds"
} as const)

export const S2S_NUMERIC_LOCAL_SOURCE_CLOSURE = Object.freeze([
  Object.freeze({
    path: "pyproject.toml",
    sha256: "67deb563870b314d8da0cba25abdd8dc39f87559232edcf1c1d616de6536171f"
  }),
  Object.freeze({
    path: "src/hswm/__init__.py",
    sha256: "09d5be5cf85a6574c76c8a741f1bcc931159f4cec0ef1c885309a545431e3303"
  }),
  Object.freeze({
    path: "src/hswm/experiments/__init__.py",
    sha256: "db4aea80994b7d0be1f7eeeab4b33defe6a1e8cd58d649cf756dd28092fed070"
  }),
  Object.freeze({
    path: "src/hswm/experiments/swm0w_s2s_family.py",
    sha256: "e00a3365e89592038b66820f57655d28e908425e3586385fd2be1e407944e93a"
  }),
  Object.freeze({
    path: "src/hswm/experiments/swm0w_s2s_numeric_oracle.py",
    sha256: S2S_NUMERIC_ORACLE_SOURCE_SHA256
  }),
  Object.freeze({
    path: "src/hswm/experiments/swm0w_s2s_operator.py",
    sha256: "7b16eccc74059c6c6dd537ea219c458d7015eadf070d77e1c34ad75c2c828151"
  }),
  Object.freeze({
    path: "src/hswm/experiments/swm0w_s2s_protocol.py",
    sha256: "c0df25e37d0e54c792f0eca9f78d83029e4fedd8f837743096eef2b29a62a2c1"
  }),
  Object.freeze({
    path: "src/hswm/experiments/swm0w_s2s_training.py",
    sha256: "d84b8336d8bcbe89aeba7f2d2c915fd294b9ee24425e6092505069a74f9cba94"
  }),
  Object.freeze({
    path: "src/hswm/experiments/swm0w_s2s_worlds.py",
    sha256: "365a2d57e9988f1223b5ea39e26c9196c0d26400c821acbcd8c62a6f224d4f81"
  }),
  Object.freeze({
    path: "uv.lock",
    sha256: "6b05d72b97246fd19c99adeb36120dc030bdb52c869fb49e6be210d3b2783bfd"
  })
] as const)

const PYTHON_RUNTIME_PROBE = [
  "import json,os,platform,sys,numpy",
  "import hswm,hswm.experiments",
  "from hswm.experiments import swm0w_s2s_family as family,swm0w_s2s_numeric_oracle as oracle,swm0w_s2s_operator as operator,swm0w_s2s_protocol as protocol,swm0w_s2s_training as training,swm0w_s2s_worlds as worlds",
  "mods={'src/hswm/__init__.py':hswm,'src/hswm/experiments/__init__.py':hswm.experiments,'src/hswm/experiments/swm0w_s2s_family.py':family,'src/hswm/experiments/swm0w_s2s_numeric_oracle.py':oracle,'src/hswm/experiments/swm0w_s2s_operator.py':operator,'src/hswm/experiments/swm0w_s2s_protocol.py':protocol,'src/hswm/experiments/swm0w_s2s_training.py':training,'src/hswm/experiments/swm0w_s2s_worlds.py':worlds}",
  "value={'byteorder':sys.byteorder,'cache_tag':sys.implementation.cache_tag or '','implementation':platform.python_implementation(),'module_paths':{key:os.path.realpath(module.__file__) for key,module in mods.items()},'numpy_module_path':os.path.realpath(numpy.__file__),'numpy_version':numpy.__version__,'pycache_prefix':os.path.realpath(sys.pycache_prefix or ''),'python_version':platform.python_version()}",
  "sys.stdout.write(json.dumps(value,ensure_ascii=True,separators=(',',':'),sort_keys=True)+'\\n')"
].join(";")

// The private cache prevents ambient repository bytecode from becoming the
// import input. The exact environment is intentionally smaller than the host
// environment and includes the pilot-frozen OpenBLAS dispatch core.
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
    OPENBLAS_CORETYPE: "Haswell",
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
  readonly expectedNumpyVersion: string
}

export interface S2SPythonSourceIdentityEntry {
  readonly path: string
  readonly byteLength: number
  readonly rawBytesSha256: S2SSha256
}

export interface S2SPythonRuntimeSourceIdentityReceipt {
  readonly schemaVersion: typeof S2S_PYTHON_RUNTIME_SOURCE_IDENTITY_SCHEMA_VERSION
  readonly pythonExecutableSha256: S2SSha256
  readonly pythonVersion: string
  readonly pythonImplementation: "CPython"
  readonly pythonCacheTag: string
  readonly byteorder: "little" | "big"
  readonly numpyVersion: string
  readonly numpyModulePath: string
  readonly modulePaths: Readonly<Record<string, string>>
  readonly repositoryRoot: string
  readonly pythonExecutableArgv0: string
  readonly processEnvironmentContract: Readonly<Record<string, string>>
  readonly processEnvironmentContractSha256: S2SSha256
  readonly sourceClosure: ReadonlyArray<S2SPythonSourceIdentityEntry>
  readonly sourceClosureSha256: S2SSha256
  readonly receiptSha256: S2SSha256
  readonly readCanonicalBytes: () => Uint8Array
}

export interface S2SPythonGoldenVerification {
  readonly schemaVersion: typeof S2S_NUMERIC_GOLDEN_VECTOR_SCHEMA_VERSION
  readonly documentByteLength: typeof S2S_NUMERIC_GOLDEN_VECTOR_BYTE_LENGTH
  readonly rawBytesSha256: S2SSha256
  readonly receiptSha256: S2SSha256
  readonly commandElapsedNanoseconds: number
  readonly runtimeSourceIdentityReceiptSha256: S2SSha256
}

export class S2SPythonGoldenVerificationError extends Data.TaggedError(
  "S2SPythonGoldenVerificationError"
)<{
  readonly reason:
    | "CONFIGURATION_INVALID"
    | "GOLDEN_HASH_MISMATCH"
    | "LOCAL_SOURCE_CLOSURE_DRIFT"
    | "NONZERO_EXIT"
    | "NUMERIC_SOURCE_DRIFT"
    | "RUNTIME_IDENTITY_DRIFT"
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
    readonly runtimeSourceIdentity: S2SPythonRuntimeSourceIdentityReceipt
    readonly verify: Effect.Effect<
      S2SPythonGoldenVerification,
      S2SPythonGoldenVerificationError
    >
  }
>() {}

export type S2SPythonNumericOperation = "CONFIRM" | "ADJUDICATE"

export interface S2SPythonNumericOutput {
  readonly operation: S2SPythonNumericOperation
  readonly memberName: "numeric_candidate.json" | "numeric_adjudication.json"
  readonly inputRawBytesSha256: S2SSha256
  readonly rawBytesSha256: S2SSha256
  readonly byteLength: number
  readonly commandElapsedNanoseconds: number
  readonly runtimeSourceIdentityReceiptSha256: S2SSha256
  readonly readCanonicalBytes: () => Uint8Array
}

export class S2SPythonNumericExecutionError extends Data.TaggedError(
  "S2SPythonNumericExecutionError"
)<{
  readonly operation: S2SPythonNumericOperation
  readonly reason:
    | "CONFIGURATION_INVALID"
    | "ERROR_DOCUMENT_REJECTED"
    | "INPUT_CONTRACT_REJECTED"
    | "LOCAL_SOURCE_CLOSURE_DRIFT"
    | "NONZERO_EXIT"
    | "NUMERIC_ORACLE_REJECTED"
    | "OUTPUT_CONTRACT_REJECTED"
    | "PARTIAL_STDOUT_OBSERVED"
    | "PROCESS_FAILED"
    | "RUNTIME_IDENTITY_DRIFT"
    | "STDERR_CONTRACT_REJECTED"
  readonly exitCode: number | null
  readonly detail: string
  readonly oracleErrorCode: string | null
  readonly oracleStage: string | null
  readonly oracleReceiptSha256: S2SSha256 | null
}> {}

/**
 * Internal module capability. It is deliberately absent from `src/index.ts`;
 * the later authoritative composition root must own this Layer and its input
 * bytes before any lifecycle event can bind the result.
 */
export class S2SPythonNumericExecutor extends Context.Tag(
  "hswm/S2S/PythonNumericExecutor"
)<
  S2SPythonNumericExecutor,
  {
    readonly runtimeSourceIdentity: S2SPythonRuntimeSourceIdentityReceipt
    readonly confirm: (
      canonicalRequestBytes: Uint8Array
    ) => Effect.Effect<S2SPythonNumericOutput, S2SPythonNumericExecutionError>
    readonly adjudicate: (
      canonicalCandidateBytes: Uint8Array
    ) => Effect.Effect<S2SPythonNumericOutput, S2SPythonNumericExecutionError>
  }
>() {}

interface PreparedPythonConfig {
  readonly repositoryRoot: string
  readonly pythonExecutable: string
  readonly pythonExecutableRealPath: string
  readonly expectedPythonExecutableSha256: S2SSha256
  readonly expectedPythonVersion: string
  readonly expectedNumpyVersion: string
}

interface PinnedPythonExecutable {
  readonly handle: FileHandle
  readonly procExecutablePath: string
}

interface PinnedPythonProcessInvocation {
  readonly operation: string
  readonly arguments: ReadonlyArray<string>
  readonly stdin: Uint8Array | null
  readonly timeoutMillis: number
  readonly stdoutLimitBytes: number
  readonly stderrLimitBytes: number
}

interface VerifiedSourceClosure {
  readonly entries: ReadonlyArray<S2SPythonSourceIdentityEntry>
  readonly sha256: S2SSha256
}

interface PythonRuntimeProbe {
  readonly pythonVersion: string
  readonly pythonImplementation: "CPython"
  readonly pythonCacheTag: string
  readonly byteorder: "little" | "big"
  readonly numpyVersion: string
  readonly numpyModulePath: string
  readonly modulePaths: Readonly<Record<string, string>>
}

interface NumericOracleErrorDocument {
  readonly errorCode: string
  readonly stage: string
  readonly receiptSha256: S2SSha256
}

const verificationError = (
  reason: S2SPythonGoldenVerificationError["reason"],
  detail: string,
  exitCode: number | null = null
): S2SPythonGoldenVerificationError =>
  new S2SPythonGoldenVerificationError({ reason, exitCode, detail })

const numericError = (
  operation: S2SPythonNumericOperation,
  reason: S2SPythonNumericExecutionError["reason"],
  detail: string,
  exitCode: number | null = null,
  oracleErrorCode: string | null = null,
  oracleStage: string | null = null,
  oracleReceiptSha256: S2SSha256 | null = null
): S2SPythonNumericExecutionError =>
  new S2SPythonNumericExecutionError({
    operation,
    reason,
    exitCode,
    detail,
    oracleErrorCode,
    oracleStage,
    oracleReceiptSha256
  })

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((byte, index) => byte === right[index])

const isPlainDataRecord = (value: object): boolean => {
  const prototype = Object.getPrototypeOf(value)
  return prototype === Object.prototype || prototype === null
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  value !== null &&
  typeof value === "object" &&
  !Array.isArray(value) &&
  isPlainDataRecord(value)

const hasExactKeys = (
  value: Record<string, unknown>,
  expectedKeys: ReadonlyArray<string>
): boolean => {
  const keys = Reflect.ownKeys(value)
  if (keys.some((key) => typeof key !== "string")) return false
  const sorted = keys.filter((key): key is string => typeof key === "string").sort()
  const expected = [...expectedKeys].sort()
  return (
    sorted.length === expected.length &&
    sorted.every((key, index) => key === expected[index])
  )
}

const isAsciiString = (value: unknown): value is string =>
  typeof value === "string" && /^[\u0000-\u007f]*$/.test(value)

const canonicalHash = (
  value: unknown,
  detail: string
): S2SSha256 => {
  const result = canonicalS2SControlSha256(value)
  if (Either.isLeft(result)) {
    throw verificationError("CONFIGURATION_INVALID", detail)
  }
  return S2SSha256Schema.make(result.right)
}

const canonicalBytes = (value: unknown, detail: string): Uint8Array => {
  const result = canonicalS2SControlJsonBytes(value)
  if (Either.isLeft(result)) {
    throw verificationError("CONFIGURATION_INVALID", detail)
  }
  return result.right
}

const snapshotPythonConfig = (
  input: S2SPythonGoldenProcessConfig
): Either.Either<
  Readonly<S2SPythonGoldenProcessConfig>,
  S2SPythonGoldenVerificationError
> => {
  if (input === null || typeof input !== "object" || !isPlainDataRecord(input)) {
    return Either.left(
      verificationError(
        "CONFIGURATION_INVALID",
        "Python process configuration must be one exact plain data record"
      )
    )
  }
  const expectedKeys = [
    "expectedNumpyVersion",
    "expectedPythonExecutableSha256",
    "expectedPythonVersion",
    "pythonExecutable",
    "repositoryRoot"
  ] as const
  const ownKeys = Reflect.ownKeys(input)
  if (
    ownKeys.length !== expectedKeys.length ||
    ownKeys.some((key) => typeof key !== "string") ||
    !expectedKeys.every((key) => ownKeys.includes(key))
  ) {
    return Either.left(
      verificationError(
        "CONFIGURATION_INVALID",
        "Python process configuration key roster drifted"
      )
    )
  }
  const values: Record<(typeof expectedKeys)[number], string> = {
    expectedNumpyVersion: "",
    expectedPythonExecutableSha256: "",
    expectedPythonVersion: "",
    pythonExecutable: "",
    repositoryRoot: ""
  }
  for (const key of expectedKeys) {
    const descriptor = Object.getOwnPropertyDescriptor(input, key)
    if (
      descriptor === undefined ||
      !("value" in descriptor) ||
      descriptor.enumerable !== true ||
      typeof descriptor.value !== "string"
    ) {
      return Either.left(
        verificationError(
          "CONFIGURATION_INVALID",
          "Python process configuration must contain enumerable string data values"
        )
      )
    }
    values[key] = descriptor.value
  }
  return Either.right(Object.freeze({ ...values }))
}

const preparePythonConfig = async (
  input: Readonly<S2SPythonGoldenProcessConfig>
): Promise<PreparedPythonConfig> => {
  if (
    !isAbsolute(input.repositoryRoot) ||
    !isAbsolute(input.pythonExecutable) ||
    input.repositoryRoot.includes("\0") ||
    input.pythonExecutable.includes("\0") ||
    !/^[\u0000-\u007f]+$/.test(input.repositoryRoot) ||
    !/^[\u0000-\u007f]+$/.test(input.pythonExecutable) ||
    !/^[0-9a-f]{64}$/.test(input.expectedPythonExecutableSha256) ||
    !/^[0-9]+\.[0-9]+\.[0-9]+$/.test(input.expectedPythonVersion) ||
    !/^[0-9]+\.[0-9]+\.[0-9]+(?:[A-Za-z0-9._-]*)?$/.test(
      input.expectedNumpyVersion
    )
  ) {
    throw verificationError(
      "CONFIGURATION_INVALID",
      "Python process configuration contains an invalid fixed value"
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
  const pythonExecutable = resolve(input.pythonExecutable)
  const pythonExecutableRealPath = await realpath(pythonExecutable)
  const pythonStat = await lstat(pythonExecutableRealPath)
  if (
    !pythonStat.isFile() ||
    (pythonStat.mode & 0o111) === 0 ||
    pythonStat.size < 1 ||
    pythonStat.size > PYTHON_EXECUTABLE_MAX_BYTES
  ) {
    throw verificationError(
      "CONFIGURATION_INVALID",
      "resolved Python executable is not one bounded executable file"
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
    rawS2SFileSha256(executableBytes) !== input.expectedPythonExecutableSha256
  ) {
    throw verificationError(
      "CONFIGURATION_INVALID",
      "resolved Python executable differs from its runtime pin"
    )
  }
  return Object.freeze({
    repositoryRoot,
    pythonExecutable,
    pythonExecutableRealPath,
    expectedPythonExecutableSha256: S2SSha256Schema.make(
      input.expectedPythonExecutableSha256
    ),
    expectedPythonVersion: input.expectedPythonVersion,
    expectedNumpyVersion: input.expectedNumpyVersion
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

const mapProcessError = (
  error: S2SBoundedProcessError
): S2SPythonGoldenVerificationError =>
  verificationError(
    "PROCESS_FAILED",
    `bounded process rejected: ${error.reason}`,
    error.exitCode
  )

const runPinnedPythonProcess = (
  config: PreparedPythonConfig,
  privatePycacheRoot: string,
  invocation: PinnedPythonProcessInvocation
): Effect.Effect<
  S2SBoundedProcessResult,
  S2SPythonGoldenVerificationError
> =>
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
        stdin: invocation.stdin,
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

const assertPlainParentDirectories = async (
  repositoryRoot: string,
  relativePath: string
): Promise<string> => {
  const targetPath = resolve(repositoryRoot, ...relativePath.split("/"))
  const boundedRelative = relative(repositoryRoot, targetPath)
  if (
    boundedRelative === ".." ||
    boundedRelative.startsWith(`..${sep}`) ||
    isAbsolute(boundedRelative) ||
    boundedRelative.split(sep).join("/") !== relativePath
  ) {
    throw verificationError(
      "LOCAL_SOURCE_CLOSURE_DRIFT",
      "local source closure path escaped the canonical repository root"
    )
  }
  const parts = relativePath.split("/")
  let current = repositoryRoot
  for (const part of parts.slice(0, -1)) {
    current = join(current, part)
    const stat = await lstat(current)
    if (stat.isSymbolicLink() || !stat.isDirectory()) {
      throw verificationError(
        "LOCAL_SOURCE_CLOSURE_DRIFT",
        "local source closure contains a non-plain parent directory"
      )
    }
  }
  return targetPath
}

const verifyLocalSourceClosure = (
  config: PreparedPythonConfig
): Effect.Effect<VerifiedSourceClosure, S2SPythonGoldenVerificationError> =>
  Effect.tryPromise({
    try: async () => {
      const entries: Array<S2SPythonSourceIdentityEntry> = []
      let aggregateBytes = 0
      for (const expected of S2S_NUMERIC_LOCAL_SOURCE_CLOSURE) {
        const path = await assertPlainParentDirectories(
          config.repositoryRoot,
          expected.path
        )
        const handle = await open(
          path,
          constants.O_RDONLY | constants.O_NOFOLLOW
        )
        try {
          const before = await handle.stat()
          if (
            !before.isFile() ||
            before.size < 0 ||
            before.size > LOCAL_SOURCE_CLOSURE_MAX_BYTES
          ) {
            throw verificationError(
              "LOCAL_SOURCE_CLOSURE_DRIFT",
              "local source closure member is not one bounded regular file"
            )
          }
          const bytes = new Uint8Array(await handle.readFile())
          const after = await handle.stat()
          const rawHash = rawS2SFileSha256(bytes)
          if (
            bytes.byteLength !== before.size ||
            after.size !== before.size ||
            after.ino !== before.ino ||
            rawHash !== expected.sha256
          ) {
            throw verificationError(
              "LOCAL_SOURCE_CLOSURE_DRIFT",
              `local source closure member drifted: ${expected.path}`
            )
          }
          aggregateBytes += bytes.byteLength
          if (aggregateBytes > LOCAL_SOURCE_CLOSURE_MAX_BYTES) {
            throw verificationError(
              "LOCAL_SOURCE_CLOSURE_DRIFT",
              "local source closure exceeds its aggregate byte bound"
            )
          }
          entries.push(
            Object.freeze({
              path: expected.path,
              byteLength: bytes.byteLength,
              rawBytesSha256: S2SSha256Schema.make(rawHash)
            })
          )
        } finally {
          await handle.close()
        }
      }
      const frozenEntries = Object.freeze(entries)
      const sha256 = canonicalHash(
        {
          files: frozenEntries.map((entry) => ({
            byte_length: entry.byteLength,
            path: entry.path,
            raw_bytes_sha256: entry.rawBytesSha256
          })),
          schema_version: LOCAL_SOURCE_CLOSURE_SCHEMA_VERSION
        },
        "local source closure receipt could not be encoded"
      )
      return Object.freeze({ entries: frozenEntries, sha256 })
    },
    catch: (error) =>
      error instanceof S2SPythonGoldenVerificationError
        ? error
        : verificationError(
            "LOCAL_SOURCE_CLOSURE_DRIFT",
            "local source closure could not be verified"
          )
  })

const RUNTIME_PROBE_ARGUMENTS = Object.freeze([
  "-B",
  "-P",
  "-s",
  "-c",
  PYTHON_RUNTIME_PROBE
] as const)

const decodeRuntimeProbe = (
  config: PreparedPythonConfig,
  privatePycacheRoot: string,
  result: S2SBoundedProcessResult
): Either.Either<PythonRuntimeProbe, S2SPythonGoldenVerificationError> => {
  if (result.exitCode !== 0 || result.stderr.byteLength !== 0) {
    return Either.left(
      verificationError(
        "RUNTIME_IDENTITY_DRIFT",
        "Python runtime identity probe did not complete cleanly",
        result.exitCode
      )
    )
  }
  if (!isOneAsciiJsonLine(result.stdout, RUNTIME_PROBE_MAX_BYTES)) {
    return Either.left(
      verificationError(
        "RUNTIME_IDENTITY_DRIFT",
        "Python runtime identity probe emitted invalid transport bytes"
      )
    )
  }
  let parsed: unknown
  try {
    parsed = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(result.stdout))
  } catch {
    return Either.left(
      verificationError(
        "RUNTIME_IDENTITY_DRIFT",
        "Python runtime identity probe did not emit JSON"
      )
    )
  }
  const expectedKeys = [
    "byteorder",
    "cache_tag",
    "implementation",
    "module_paths",
    "numpy_module_path",
    "numpy_version",
    "pycache_prefix",
    "python_version"
  ]
  if (!isRecord(parsed) || !hasExactKeys(parsed, expectedKeys)) {
    return Either.left(
      verificationError(
        "RUNTIME_IDENTITY_DRIFT",
        "Python runtime identity probe key roster drifted"
      )
    )
  }
  const canonical = canonicalS2SControlJsonBytes(parsed)
  if (Either.isLeft(canonical) || !sameBytes(canonical.right, result.stdout)) {
    return Either.left(
      verificationError(
        "RUNTIME_IDENTITY_DRIFT",
        "Python runtime identity probe was not canonical JSON"
      )
    )
  }
  const modulePathsValue = parsed["module_paths"]
  const moduleKeys = Object.keys(NUMERIC_MODULE_PATHS)
  if (
    parsed["python_version"] !== config.expectedPythonVersion ||
    parsed["numpy_version"] !== config.expectedNumpyVersion ||
    parsed["implementation"] !== "CPython" ||
    (parsed["byteorder"] !== "little" && parsed["byteorder"] !== "big") ||
    !isAsciiString(parsed["cache_tag"]) ||
    parsed["cache_tag"].length === 0 ||
    parsed["pycache_prefix"] !== privatePycacheRoot ||
    !isAsciiString(parsed["numpy_module_path"]) ||
    !isAbsolute(parsed["numpy_module_path"]) ||
    !isRecord(modulePathsValue) ||
    !hasExactKeys(modulePathsValue, moduleKeys)
  ) {
    return Either.left(
      verificationError(
        "RUNTIME_IDENTITY_DRIFT",
        "Python, NumPy, cache, or module identity differs from its pin"
      )
    )
  }
  const modulePaths: Record<string, string> = {}
  for (const relativePath of moduleKeys) {
    const actual = modulePathsValue[relativePath]
    const expected = join(config.repositoryRoot, ...relativePath.split("/"))
    if (!isAsciiString(actual) || actual !== expected) {
      return Either.left(
        verificationError(
          "RUNTIME_IDENTITY_DRIFT",
          `Python imported an unbound local module: ${relativePath}`
        )
      )
    }
    modulePaths[relativePath] = actual
  }
  return Either.right(
    Object.freeze({
      pythonVersion: config.expectedPythonVersion,
      pythonImplementation: "CPython" as const,
      pythonCacheTag: parsed["cache_tag"],
      byteorder: parsed["byteorder"],
      numpyVersion: config.expectedNumpyVersion,
      numpyModulePath: parsed["numpy_module_path"],
      modulePaths: Object.freeze(modulePaths)
    })
  )
}

const probePythonRuntime = (
  config: PreparedPythonConfig,
  privatePycacheRoot: string
): Effect.Effect<PythonRuntimeProbe, S2SPythonGoldenVerificationError> =>
  Effect.gen(function* () {
    const result = yield* runPinnedPythonProcess(config, privatePycacheRoot, {
      operation: "PYTHON_RUNTIME_PROBE",
      arguments: RUNTIME_PROBE_ARGUMENTS,
      stdin: null,
      timeoutMillis: S2S_NUMERIC_GOLDEN_TIMEOUT_MILLIS,
      stdoutLimitBytes: RUNTIME_PROBE_MAX_BYTES,
      stderrLimitBytes: S2S_NUMERIC_STDERR_MAX_BYTES
    })
    const decoded = decodeRuntimeProbe(config, privatePycacheRoot, result)
    if (Either.isLeft(decoded)) return yield* decoded.left
    return decoded.right
  })

const makeRuntimeSourceIdentity = (
  config: PreparedPythonConfig,
  closure: VerifiedSourceClosure,
  runtime: PythonRuntimeProbe
): S2SPythonRuntimeSourceIdentityReceipt => {
  const processEnvironmentContract = pythonProcessEnvironment(
    PRIVATE_PYCACHE_IDENTITY_VALUE
  )
  const processEnvironmentContractSha256 = canonicalHash(
    processEnvironmentContract,
    "Python process environment contract could not be encoded"
  )
  const invocationContracts = {
    adjudicate: {
      arguments: [...S2S_NUMERIC_ADJUDICATE_ARGUMENTS],
      stdin_contract: "SNAPSHOTTED_OPAQUE_CANONICAL_NUMERIC_CANDIDATE_BYTES",
      stderr_limit_bytes: S2S_NUMERIC_STDERR_MAX_BYTES,
      stdout_limit_bytes: S2S_NUMERIC_ADJUDICATION_MAX_BYTES,
      timeout_millis: S2S_NUMERIC_ADJUDICATE_TIMEOUT_MILLIS
    },
    confirm: {
      arguments: [...S2S_NUMERIC_CONFIRM_ARGUMENTS],
      stdin_contract: "SNAPSHOTTED_OPAQUE_CANONICAL_CONFIRM_REQUEST_BYTES",
      stderr_limit_bytes: S2S_NUMERIC_STDERR_MAX_BYTES,
      stdout_limit_bytes: S2S_NUMERIC_CANDIDATE_MAX_BYTES,
      timeout_millis: S2S_NUMERIC_CONFIRM_TIMEOUT_MILLIS
    },
    golden: {
      arguments: [...S2S_NUMERIC_GOLDEN_ARGUMENTS],
      stdin_contract: "NONE",
      stderr_limit_bytes: GOLDEN_STDERR_MAX_BYTES,
      stdout_limit_bytes: S2S_NUMERIC_GOLDEN_VECTOR_BYTE_LENGTH,
      timeout_millis: S2S_NUMERIC_GOLDEN_TIMEOUT_MILLIS
    },
    runtime_probe: {
      arguments: [...RUNTIME_PROBE_ARGUMENTS],
      stdin_contract: "NONE",
      stderr_limit_bytes: S2S_NUMERIC_STDERR_MAX_BYTES,
      stdout_limit_bytes: RUNTIME_PROBE_MAX_BYTES,
      timeout_millis: S2S_NUMERIC_GOLDEN_TIMEOUT_MILLIS
    }
  }
  const sourceClosure = closure.entries.map((entry) => ({
    byte_length: entry.byteLength,
    path: entry.path,
    raw_bytes_sha256: entry.rawBytesSha256
  }))
  const unsigned = {
    byteorder: runtime.byteorder,
    invocation_contracts: invocationContracts,
    module_imports: NUMERIC_MODULE_PATHS,
    module_paths: runtime.modulePaths,
    numpy_module_path: runtime.numpyModulePath,
    numpy_version: runtime.numpyVersion,
    process_contract: {
      argv0: config.pythonExecutable,
      cwd: config.repositoryRoot,
      executable_transport: "PINNED_PROC_SELF_FILE_DESCRIPTOR",
      retry_count: 0,
      success_stderr_byte_length: 0
    },
    process_environment_contract: processEnvironmentContract,
    process_environment_contract_sha256: processEnvironmentContractSha256,
    python_cache_tag: runtime.pythonCacheTag,
    python_executable_sha256: config.expectedPythonExecutableSha256,
    python_implementation: runtime.pythonImplementation,
    python_version: runtime.pythonVersion,
    schema_version: S2S_PYTHON_RUNTIME_SOURCE_IDENTITY_SCHEMA_VERSION,
    source_closure: sourceClosure,
    source_closure_sha256: closure.sha256
  }
  const receiptSha256 = canonicalHash(
    unsigned,
    "runtime/source identity receipt hash could not be encoded"
  )
  const encoded = canonicalBytes(
    { ...unsigned, receipt_sha256: receiptSha256 },
    "runtime/source identity receipt could not be encoded"
  )
  return Object.freeze({
    schemaVersion: S2S_PYTHON_RUNTIME_SOURCE_IDENTITY_SCHEMA_VERSION,
    pythonExecutableSha256: config.expectedPythonExecutableSha256,
    pythonVersion: runtime.pythonVersion,
    pythonImplementation: runtime.pythonImplementation,
    pythonCacheTag: runtime.pythonCacheTag,
    byteorder: runtime.byteorder,
    numpyVersion: runtime.numpyVersion,
    numpyModulePath: runtime.numpyModulePath,
    modulePaths: runtime.modulePaths,
    repositoryRoot: config.repositoryRoot,
    pythonExecutableArgv0: config.pythonExecutable,
    processEnvironmentContract,
    processEnvironmentContractSha256,
    sourceClosure: closure.entries,
    sourceClosureSha256: closure.sha256,
    receiptSha256,
    readCanonicalBytes: () => new Uint8Array(encoded)
  })
}

const acquireRuntimeSourceIdentity = (
  config: PreparedPythonConfig,
  privatePycacheRoot: string
): Effect.Effect<
  S2SPythonRuntimeSourceIdentityReceipt,
  S2SPythonGoldenVerificationError
> =>
  Effect.gen(function* () {
    const closure = yield* verifyLocalSourceClosure(config)
    const runtime = yield* probePythonRuntime(config, privatePycacheRoot)
    const postProbeClosure = yield* verifyLocalSourceClosure(config)
    if (
      closure.sha256 !== postProbeClosure.sha256 ||
      !sameBytes(
        canonicalBytes(
          closure.entries.map((entry) => ({ ...entry })),
          "source closure comparison could not be encoded"
        ),
        canonicalBytes(
          postProbeClosure.entries.map((entry) => ({ ...entry })),
          "source closure comparison could not be encoded"
        )
      )
    ) {
      return yield* verificationError(
        "LOCAL_SOURCE_CLOSURE_DRIFT",
        "local source closure changed while probing the runtime"
      )
    }
    return makeRuntimeSourceIdentity(config, postProbeClosure, runtime)
  })

const assertRuntimeSourceIdentity = (
  config: PreparedPythonConfig,
  privatePycacheRoot: string,
  expected: S2SPythonRuntimeSourceIdentityReceipt
): Effect.Effect<void, S2SPythonGoldenVerificationError> =>
  Effect.gen(function* () {
    const current = yield* acquireRuntimeSourceIdentity(config, privatePycacheRoot)
    if (
      current.receiptSha256 !== expected.receiptSha256 ||
      !sameBytes(current.readCanonicalBytes(), expected.readCanonicalBytes())
    ) {
      return yield* verificationError(
        "RUNTIME_IDENTITY_DRIFT",
        "Python runtime/source identity differs from the acquired receipt"
      )
    }
  })

const isOneAsciiJsonLine = (
  bytes: Uint8Array,
  maximumBytes: number
): boolean => {
  if (
    bytes.byteLength < 2 ||
    bytes.byteLength > maximumBytes ||
    bytes[bytes.byteLength - 1] !== 0x0a ||
    bytes.some((byte) => byte > 0x7f) ||
    bytes
      .subarray(0, bytes.byteLength - 1)
      .some((byte) => byte === 0x0a || byte === 0x0d)
  ) {
    return false
  }
  try {
    JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes))
    return true
  } catch {
    return false
  }
}

const snapshotNumericInput = (
  operation: S2SPythonNumericOperation,
  input: Uint8Array
): Either.Either<Uint8Array, S2SPythonNumericExecutionError> => {
  const maximumBytes =
    operation === "CONFIRM"
      ? S2S_NUMERIC_CONFIRM_REQUEST_MAX_BYTES
      : S2S_NUMERIC_CANDIDATE_MAX_BYTES
  if (
    !(input instanceof Uint8Array) ||
    Object.getPrototypeOf(input) !== Uint8Array.prototype ||
    Object.getOwnPropertySymbols(input).length !== 0 ||
    Object.getOwnPropertyDescriptor(input, "byteLength") !== undefined ||
    Object.getOwnPropertyDescriptor(input, "buffer") !== undefined ||
    (typeof SharedArrayBuffer !== "undefined" &&
      input.buffer instanceof SharedArrayBuffer)
  ) {
    return Either.left(
      numericError(
        operation,
        "INPUT_CONTRACT_REJECTED",
        "numeric stdin must be one plain unshared Uint8Array"
      )
    )
  }
  const snapshot = new Uint8Array(input)
  if (!isOneAsciiJsonLine(snapshot, maximumBytes)) {
    return Either.left(
      numericError(
        operation,
        "INPUT_CONTRACT_REJECTED",
        "numeric stdin must be one bounded opaque canonical ASCII JSON line"
      )
    )
  }
  return Either.right(snapshot)
}

const NUMERIC_ERROR_CODES = new Set([
  "INVALID_CANONICAL_DOCUMENT",
  "INVALID_CONFIRM_REQUEST",
  "NON_ADOPTED_PROTOCOL_CONFIG",
  "TASK_BATCH_GENERATION_FAILED",
  "FIT_REPLAY_FAILED",
  "TEST_EVALUATION_FAILED",
  "CANDIDATE_FINALIZATION_FAILED",
  "INVALID_NUMERIC_CANDIDATE",
  "ADJUDICATION_REPLAY_MISMATCH",
  "INVALID_NUMERIC_ADJUDICATION",
  "INVALID_CLI_INVOCATION",
  "INTERNAL_NUMERIC_FAILURE"
])

const decodeNumericOracleError = (
  operation: S2SPythonNumericOperation,
  bytes: Uint8Array
): Either.Either<NumericOracleErrorDocument, S2SPythonNumericExecutionError> => {
  if (!isOneAsciiJsonLine(bytes, S2S_NUMERIC_STDERR_MAX_BYTES)) {
    return Either.left(
      numericError(
        operation,
        "ERROR_DOCUMENT_REJECTED",
        "numeric oracle error transport is malformed"
      )
    )
  }
  let parsed: unknown
  try {
    parsed = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes))
  } catch {
    return Either.left(
      numericError(
        operation,
        "ERROR_DOCUMENT_REJECTED",
        "numeric oracle error is not JSON"
      )
    )
  }
  const keys = [
    "canonical_encoding",
    "error_code",
    "operation",
    "receipt_sha256",
    "schema_version",
    "stage",
    "status"
  ]
  const expectedOperation = operation === "CONFIRM" ? "confirm" : "adjudicate"
  if (
    !isRecord(parsed) ||
    !hasExactKeys(parsed, keys) ||
    parsed["canonical_encoding"] !== NUMERIC_CANONICAL_ENCODING ||
    parsed["schema_version"] !== NUMERIC_ERROR_SCHEMA_VERSION ||
    parsed["status"] !== NUMERIC_REJECTED_STATUS ||
    parsed["operation"] !== expectedOperation ||
    !isAsciiString(parsed["error_code"]) ||
    !NUMERIC_ERROR_CODES.has(parsed["error_code"]) ||
    !isAsciiString(parsed["stage"]) ||
    parsed["stage"].length === 0 ||
    !isAsciiString(parsed["receipt_sha256"]) ||
    !/^[0-9a-f]{64}$/.test(parsed["receipt_sha256"])
  ) {
    return Either.left(
      numericError(
        operation,
        "ERROR_DOCUMENT_REJECTED",
        "numeric oracle error fixed projection drifted"
      )
    )
  }
  const canonical = canonicalS2SControlJsonBytes(parsed)
  const unsigned = {
    canonical_encoding: parsed["canonical_encoding"],
    error_code: parsed["error_code"],
    operation: parsed["operation"],
    schema_version: parsed["schema_version"],
    stage: parsed["stage"],
    status: parsed["status"]
  }
  const expectedReceipt = canonicalS2SControlSha256(unsigned)
  if (
    Either.isLeft(canonical) ||
    !sameBytes(canonical.right, bytes) ||
    Either.isLeft(expectedReceipt) ||
    expectedReceipt.right !== parsed["receipt_sha256"]
  ) {
    return Either.left(
      numericError(
        operation,
        "ERROR_DOCUMENT_REJECTED",
        "numeric oracle error is not canonically receipt-bound"
      )
    )
  }
  return Either.right(
    Object.freeze({
      errorCode: parsed["error_code"],
      stage: parsed["stage"],
      receiptSha256: S2SSha256Schema.make(parsed["receipt_sha256"])
    })
  )
}

export const interpretS2SPythonNumericProcessResult = (
  operation: S2SPythonNumericOperation,
  inputBytes: Uint8Array,
  runtimeSourceIdentityReceiptSha256: S2SSha256,
  result: S2SBoundedProcessResult
): Either.Either<S2SPythonNumericOutput, S2SPythonNumericExecutionError> => {
  if (result.exitCode !== 0 && result.stdout.byteLength !== 0) {
    return Either.left(
      numericError(
        operation,
        "PARTIAL_STDOUT_OBSERVED",
        "failed numeric process emitted partial stdout",
        result.exitCode
      )
    )
  }
  if (result.exitCode === 2 || result.exitCode === 3) {
    const decoded = decodeNumericOracleError(operation, result.stderr)
    if (Either.isLeft(decoded)) {
      return Either.left(
        numericError(
          operation,
          decoded.left.reason,
          decoded.left.detail,
          result.exitCode,
          decoded.left.oracleErrorCode,
          decoded.left.oracleStage,
          decoded.left.oracleReceiptSha256
        )
      )
    }
    return Either.left(
      numericError(
        operation,
        "NUMERIC_ORACLE_REJECTED",
        `numeric oracle rejected the input at ${decoded.right.stage}`,
        result.exitCode,
        decoded.right.errorCode,
        decoded.right.stage,
        decoded.right.receiptSha256
      )
    )
  }
  if (result.exitCode !== 0) {
    return Either.left(
      numericError(
        operation,
        "NONZERO_EXIT",
        "numeric process exited outside the canonical error contract",
        result.exitCode
      )
    )
  }
  if (result.stderr.byteLength !== 0) {
    return Either.left(
      numericError(
        operation,
        "STDERR_CONTRACT_REJECTED",
        "successful numeric process emitted stderr",
        result.exitCode
      )
    )
  }
  const maximumBytes =
    operation === "CONFIRM"
      ? S2S_NUMERIC_CANDIDATE_MAX_BYTES
      : S2S_NUMERIC_ADJUDICATION_MAX_BYTES
  const outputBytes = new Uint8Array(result.stdout)
  if (!isOneAsciiJsonLine(outputBytes, maximumBytes)) {
    return Either.left(
      numericError(
        operation,
        "OUTPUT_CONTRACT_REJECTED",
        "numeric output is not one bounded opaque canonical ASCII JSON line",
        result.exitCode
      )
    )
  }
  if (
    !Number.isSafeInteger(result.elapsedNanoseconds) ||
    result.elapsedNanoseconds < 0
  ) {
    return Either.left(
      numericError(
        operation,
        "OUTPUT_CONTRACT_REJECTED",
        "numeric process elapsed time is invalid",
        result.exitCode
      )
    )
  }
  return Either.right(
    Object.freeze({
      operation,
      memberName:
        operation === "CONFIRM"
          ? "numeric_candidate.json"
          : "numeric_adjudication.json",
      inputRawBytesSha256: S2SSha256Schema.make(rawS2SFileSha256(inputBytes)),
      rawBytesSha256: S2SSha256Schema.make(rawS2SFileSha256(outputBytes)),
      byteLength: outputBytes.byteLength,
      commandElapsedNanoseconds: result.elapsedNanoseconds,
      runtimeSourceIdentityReceiptSha256,
      readCanonicalBytes: () => new Uint8Array(outputBytes)
    })
  )
}

const mapVerificationToNumericError = (
  operation: S2SPythonNumericOperation,
  error: S2SPythonGoldenVerificationError
): S2SPythonNumericExecutionError => {
  const reason: S2SPythonNumericExecutionError["reason"] =
    error.reason === "CONFIGURATION_INVALID"
      ? "CONFIGURATION_INVALID"
      : error.reason === "LOCAL_SOURCE_CLOSURE_DRIFT" ||
          error.reason === "NUMERIC_SOURCE_DRIFT"
        ? "LOCAL_SOURCE_CLOSURE_DRIFT"
        : error.reason === "RUNTIME_IDENTITY_DRIFT"
          ? "RUNTIME_IDENTITY_DRIFT"
          : "PROCESS_FAILED"
  return numericError(operation, reason, error.detail, error.exitCode)
}

const executeNumericOperation = (
  config: PreparedPythonConfig,
  privatePycacheRoot: string,
  identity: S2SPythonRuntimeSourceIdentityReceipt,
  operation: S2SPythonNumericOperation,
  input: Uint8Array
): Effect.Effect<S2SPythonNumericOutput, S2SPythonNumericExecutionError> => {
  const snapshotted = snapshotNumericInput(operation, input)
  if (Either.isLeft(snapshotted)) return Effect.fail(snapshotted.left)
  const stdin = snapshotted.right
  const invocation: PinnedPythonProcessInvocation =
    operation === "CONFIRM"
      ? {
          operation: "PYTHON_NUMERIC_CONFIRM",
          arguments: S2S_NUMERIC_CONFIRM_ARGUMENTS,
          stdin,
          timeoutMillis: S2S_NUMERIC_CONFIRM_TIMEOUT_MILLIS,
          stdoutLimitBytes: S2S_NUMERIC_CANDIDATE_MAX_BYTES,
          stderrLimitBytes: S2S_NUMERIC_STDERR_MAX_BYTES
        }
      : {
          operation: "PYTHON_NUMERIC_ADJUDICATE",
          arguments: S2S_NUMERIC_ADJUDICATE_ARGUMENTS,
          stdin,
          timeoutMillis: S2S_NUMERIC_ADJUDICATE_TIMEOUT_MILLIS,
          stdoutLimitBytes: S2S_NUMERIC_ADJUDICATION_MAX_BYTES,
          stderrLimitBytes: S2S_NUMERIC_STDERR_MAX_BYTES
        }
  return Effect.gen(function* () {
    yield* assertRuntimeSourceIdentity(
      config,
      privatePycacheRoot,
      identity
    ).pipe(Effect.mapError((error) => mapVerificationToNumericError(operation, error)))
    const result = yield* runPinnedPythonProcess(
      config,
      privatePycacheRoot,
      invocation
    ).pipe(Effect.mapError((error) => mapVerificationToNumericError(operation, error)))
    yield* assertRuntimeSourceIdentity(
      config,
      privatePycacheRoot,
      identity
    ).pipe(Effect.mapError((error) => mapVerificationToNumericError(operation, error)))
    const interpreted = interpretS2SPythonNumericProcessResult(
      operation,
      stdin,
      identity.receiptSha256,
      result
    )
    if (Either.isLeft(interpreted)) return yield* interpreted.left
    return interpreted.right
  })
}

const validateGoldenBytes = (
  bytes: Uint8Array,
  elapsedNanoseconds: number,
  runtimeSourceIdentityReceiptSha256: S2SSha256
): Either.Either<
  S2SPythonGoldenVerification,
  S2SPythonGoldenVerificationError
> => {
  if (
    bytes.byteLength !== S2S_NUMERIC_GOLDEN_VECTOR_BYTE_LENGTH ||
    !isOneAsciiJsonLine(bytes, S2S_NUMERIC_GOLDEN_VECTOR_BYTE_LENGTH)
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
      verificationError("OUTPUT_CONTRACT_REJECTED", "golden output is not JSON")
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
      commandElapsedNanoseconds: elapsedNanoseconds,
      runtimeSourceIdentityReceiptSha256
    })
  )
}

const prepareRuntime = (
  snapshot: Either.Either<
    Readonly<S2SPythonGoldenProcessConfig>,
    S2SPythonGoldenVerificationError
  >
) =>
  Effect.gen(function* () {
    if (Either.isLeft(snapshot)) return yield* snapshot.left
    const config = yield* Effect.tryPromise({
      try: () => preparePythonConfig(snapshot.right),
      catch: (error) =>
        error instanceof S2SPythonGoldenVerificationError
          ? error
          : verificationError(
              "CONFIGURATION_INVALID",
              "Python process configuration could not be resolved"
            )
    })
    const privatePycacheRoot = yield* acquirePrivatePycacheRoot
    const identity = yield* acquireRuntimeSourceIdentity(config, privatePycacheRoot)
    return Object.freeze({ config, privatePycacheRoot, identity })
  })

export const makeS2SPythonGoldenVerifierProcessLayer = (
  input: S2SPythonGoldenProcessConfig
) => {
  const snapshot = snapshotPythonConfig(input)
  return Layer.scoped(
    S2SPythonGoldenVerifier,
    Effect.gen(function* () {
      const runtime = yield* prepareRuntime(snapshot)
      return S2SPythonGoldenVerifier.of({
        runtimeSourceIdentity: runtime.identity,
        verify: Effect.gen(function* () {
          yield* assertRuntimeSourceIdentity(
            runtime.config,
            runtime.privatePycacheRoot,
            runtime.identity
          )
          const result = yield* runPinnedPythonProcess(
            runtime.config,
            runtime.privatePycacheRoot,
            {
              operation: "PYTHON_NUMERIC_GOLDEN",
              arguments: S2S_NUMERIC_GOLDEN_ARGUMENTS,
              stdin: null,
              timeoutMillis: S2S_NUMERIC_GOLDEN_TIMEOUT_MILLIS,
              stdoutLimitBytes: S2S_NUMERIC_GOLDEN_VECTOR_BYTE_LENGTH,
              stderrLimitBytes: GOLDEN_STDERR_MAX_BYTES
            }
          )
          yield* assertRuntimeSourceIdentity(
            runtime.config,
            runtime.privatePycacheRoot,
            runtime.identity
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
            result.elapsedNanoseconds,
            runtime.identity.receiptSha256
          )
          if (Either.isLeft(verified)) return yield* verified.left
          return verified.right
        })
      })
    })
  )
}

export const makeS2SPythonNumericExecutorProcessLayer = (
  input: S2SPythonGoldenProcessConfig
) => {
  const snapshot = snapshotPythonConfig(input)
  return Layer.scoped(
    S2SPythonNumericExecutor,
    Effect.gen(function* () {
      const runtime = yield* prepareRuntime(snapshot)
      return S2SPythonNumericExecutor.of({
        runtimeSourceIdentity: runtime.identity,
        confirm: (canonicalRequestBytes) =>
          executeNumericOperation(
            runtime.config,
            runtime.privatePycacheRoot,
            runtime.identity,
            "CONFIRM",
            canonicalRequestBytes
          ),
        adjudicate: (canonicalCandidateBytes) =>
          executeNumericOperation(
            runtime.config,
            runtime.privatePycacheRoot,
            runtime.identity,
            "ADJUDICATE",
            canonicalCandidateBytes
          )
      })
    })
  )
}
