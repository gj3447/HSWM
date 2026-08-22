import { expect, it } from "@effect/vitest"
import { Cause, Effect, Either, Exit, Fiber } from "effect"
import {
  existsSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  realpathSync
} from "node:fs"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"

import {
  S2S_PROCESS_MAX_ENVIRONMENT_VALUE_BYTES,
  S2S_PROCESS_MAX_PATH_BYTES,
  runS2SBoundedProcess,
  type S2SBoundedProcessSpec
} from "../src/s2s-bounded-process.js"
import {
  canonicalS2SControlJsonBytes,
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "../src/s2s-canonical.js"
import { S2SSha256Schema } from "../src/s2s-confirmatory.js"
import * as PublicApi from "../src/index.js"
import {
  S2S_NUMERIC_ADJUDICATE_ARGUMENTS,
  S2S_NUMERIC_ADJUDICATE_TIMEOUT_MILLIS,
  S2S_NUMERIC_ADJUDICATION_MAX_BYTES,
  S2S_NUMERIC_CANDIDATE_MAX_BYTES,
  S2S_NUMERIC_CONFIRM_ARGUMENTS,
  S2S_NUMERIC_CONFIRM_TIMEOUT_MILLIS,
  S2S_NUMERIC_GOLDEN_VECTOR_BYTE_LENGTH,
  S2S_NUMERIC_GOLDEN_VECTOR_DOCUMENT_SHA256,
  S2S_NUMERIC_GOLDEN_VECTOR_RECEIPT_SHA256,
  S2S_NUMERIC_LOCAL_SOURCE_CLOSURE,
  S2S_NUMERIC_STDERR_MAX_BYTES,
  S2SPythonGoldenVerifier,
  S2SPythonNumericExecutor,
  interpretS2SPythonNumericProcessResult,
  makeS2SPythonGoldenVerifierProcessLayer,
  makeS2SPythonNumericExecutorProcessLayer
} from "../src/s2s-live-python.js"

const PACKAGE_ROOT = process.cwd()
const REPOSITORY_ROOT = resolve(PACKAGE_ROOT, "../../..")
const PINNED_VENV_PYTHON = join(REPOSITORY_ROOT, ".venv/bin/python")
const textEncoder = new TextEncoder()
const TEST_IDENTITY_SHA256 = S2SSha256Schema.make("0".repeat(64))

const numericErrorBytes = (
  operation: "confirm" | "adjudicate",
  errorCode = "INVALID_CANONICAL_DOCUMENT",
  stage = "CANONICAL_DOCUMENT"
): Uint8Array => {
  const unsigned = {
    canonical_encoding: "ASCII_CANONICAL_UTF8_JSON_PLUS_SINGLE_LF",
    error_code: errorCode,
    operation,
    schema_version: "hswm-swm0w-s2s-numeric-error/v1",
    stage,
    status: "NUMERIC_ORACLE_REJECTED_NO_PARTIAL_OUTPUT"
  }
  const receipt = canonicalS2SControlSha256(unsigned)
  if (Either.isLeft(receipt)) throw receipt.left
  const bytes = canonicalS2SControlJsonBytes({
    ...unsigned,
    receipt_sha256: receipt.right
  })
  if (Either.isLeft(bytes)) throw bytes.left
  return bytes.right
}

const baseSpec = (
  overrides: Partial<S2SBoundedProcessSpec> = {}
): S2SBoundedProcessSpec => ({
  operation: "BOUNDED_PROCESS_TEST",
  executable: process.execPath,
  arguments: ["-e", "process.stdout.write('ok')"],
  cwd: PACKAGE_ROOT,
  environment: { LANG: "C", PATH: "/usr/bin:/bin" },
  stdin: null,
  timeoutMillis: 5_000,
  stdoutLimitBytes: 1_024,
  stderrLimitBytes: 1_024,
  ...overrides
})

const delay = (milliseconds: number): Promise<void> =>
  new Promise((resolveDelay) => setTimeout(resolveDelay, milliseconds))

const readPidEventually = async (path: string): Promise<number | null> => {
  for (let attempt = 0; attempt < 200; attempt += 1) {
    try {
      const value = Number(readFileSync(path, "utf8"))
      if (Number.isSafeInteger(value) && value > 0) return value
    } catch {
      // The leader has not written its descendant PID yet.
    }
    await delay(10)
  }
  return null
}

const waitForProcessToDisappear = async (pid: number): Promise<boolean> => {
  for (let attempt = 0; attempt < 200; attempt += 1) {
    try {
      process.kill(pid, 0)
    } catch {
      return true
    }
    await delay(10)
  }
  return false
}

it.effect("snapshots the command boundary and accepts output exactly at its cap", () => {
  const arguments_ = [
    "-e",
    "process.stdout.write(`${process.env.MARKER}:original`)"
  ]
  const environment: Record<string, string> = {
    LANG: "C",
    MARKER: "snapshotted",
    PATH: "/usr/bin:/bin"
  }
  const effect = runS2SBoundedProcess(
    baseSpec({
      arguments: arguments_,
      environment,
      stdoutLimitBytes: Buffer.byteLength("snapshotted:original")
    })
  )
  arguments_[1] = "process.stdout.write('mutated')"
  environment["MARKER"] = "mutated"
  environment["NODE_OPTIONS"] = "--inspect"

  return Effect.gen(function* () {
    const result = yield* effect
    expect(new TextDecoder().decode(result.stdout)).toBe(
      "snapshotted:original"
    )
    expect(result.stderr.byteLength).toBe(0)
    expect(result.exitCode).toBe(0)
  })
})

it.effect("rejects outer accessors and custom argv iterators without invoking them", () => {
  let executableAccessorInvoked = false
  const accessorSpec = baseSpec()
  Object.defineProperty(accessorSpec, "executable", {
    enumerable: true,
    get: () => {
      executableAccessorInvoked = true
      return process.execPath
    }
  })

  let argumentIteratorInvoked = false
  const arguments_ = ["-e", "process.stdout.write('safe')"]
  Object.defineProperty(arguments_, Symbol.iterator, {
    enumerable: false,
    get: () => {
      argumentIteratorInvoked = true
      return Array.prototype[Symbol.iterator]
    }
  })

  let stdinIteratorInvoked = false
  const stdin = new Uint8Array([0x70])
  Object.defineProperty(stdin, Symbol.iterator, {
    enumerable: false,
    get: () => {
      stdinIteratorInvoked = true
      return Uint8Array.prototype[Symbol.iterator]
    }
  })

  return Effect.gen(function* () {
    const accessorOutcome = yield* runS2SBoundedProcess(
      accessorSpec
    ).pipe(Effect.either)
    const iteratorOutcome = yield* runS2SBoundedProcess(
      baseSpec({ arguments: arguments_ })
    ).pipe(Effect.either)
    const stdinOutcome = yield* runS2SBoundedProcess(
      baseSpec({ stdin })
    ).pipe(Effect.either)
    expect(Either.isLeft(accessorOutcome)).toBe(true)
    expect(Either.isLeft(iteratorOutcome)).toBe(true)
    expect(Either.isLeft(stdinOutcome)).toBe(true)
    expect(executableAccessorInvoked).toBe(false)
    expect(argumentIteratorInvoked).toBe(false)
    expect(stdinIteratorInvoked).toBe(false)
  })
})

it.effect("snapshots plain stdin bytes and preserves a bounded argv0", () => {
  const stdin = new Uint8Array([0x70, 0x69, 0x6e])
  const stdinEffect = runS2SBoundedProcess(
    baseSpec({
      arguments: ["-e", "process.stdin.pipe(process.stdout)"],
      stdin,
      stdoutLimitBytes: stdin.byteLength
    })
  )
  stdin[0] = 0x78

  const argv0 = "/pinned/venv/bin/python"
  const argv0Effect = runS2SBoundedProcess(
    baseSpec({
      argv0,
      arguments: ["-e", "process.stdout.write(process.argv0)"],
      stdoutLimitBytes: Buffer.byteLength(argv0)
    })
  )

  return Effect.gen(function* () {
    const stdinResult = yield* stdinEffect
    expect(new TextDecoder().decode(stdinResult.stdout)).toBe("pin")
    const argv0Result = yield* argv0Effect
    expect(new TextDecoder().decode(argv0Result.stdout)).toBe(argv0)
  })
})

it.effect("rejects oversized paths and aggregate environments", () => {
  const environment: Record<string, string> = {}
  for (let index = 0; index < 32; index += 1) {
    environment[`KEY_${String(index).padStart(2, "0")}`] = "x".repeat(
      S2S_PROCESS_MAX_ENVIRONMENT_VALUE_BYTES
    )
  }
  return Effect.gen(function* () {
    const pathOutcome = yield* runS2SBoundedProcess(
      baseSpec({ cwd: `/${"x".repeat(S2S_PROCESS_MAX_PATH_BYTES)}` })
    ).pipe(Effect.either)
    const environmentOutcome = yield* runS2SBoundedProcess(
      baseSpec({ environment })
    ).pipe(Effect.either)
    expect(Either.isLeft(pathOutcome)).toBe(true)
    expect(Either.isLeft(environmentOutcome)).toBe(true)
    if (Either.isLeft(pathOutcome)) {
      expect(pathOutcome.left.reason).toBe("INVALID_SPECIFICATION")
    }
    if (Either.isLeft(environmentOutcome)) {
      expect(environmentOutcome.left.reason).toBe("INVALID_SPECIFICATION")
    }
  })
})

it.effect("rejects stdout and stderr at cap plus one and discards prefixes", () =>
  Effect.gen(function* () {
    const stdout = yield* runS2SBoundedProcess(
      baseSpec({
        arguments: ["-e", "process.stdout.write(Buffer.alloc(9))"],
        stdoutLimitBytes: 8
      })
    ).pipe(Effect.either)
    const stderr = yield* runS2SBoundedProcess(
      baseSpec({
        arguments: ["-e", "process.stderr.write(Buffer.alloc(9))"],
        stderrLimitBytes: 8
      })
    ).pipe(Effect.either)

    expect(Either.isLeft(stdout)).toBe(true)
    expect(Either.isLeft(stderr)).toBe(true)
    if (Either.isLeft(stdout)) {
      expect(stdout.left.reason).toBe("STDOUT_LIMIT_EXCEEDED")
    }
    if (Either.isLeft(stderr)) {
      expect(stderr.left.reason).toBe("STDERR_LIMIT_EXCEEDED")
    }
  })
)

it.effect("rejects accessor environments without invoking the accessor", () => {
  let invoked = false
  const environment: Record<string, string> = {}
  Object.defineProperty(environment, "PATH", {
    enumerable: true,
    get: () => {
      invoked = true
      return "/usr/bin:/bin"
    }
  })
  return Effect.gen(function* () {
    const outcome = yield* runS2SBoundedProcess(
      baseSpec({ environment })
    ).pipe(Effect.either)
    expect(Either.isLeft(outcome)).toBe(true)
    if (Either.isLeft(outcome)) {
      expect(outcome.left.reason).toBe("INVALID_SPECIFICATION")
    }
    expect(invoked).toBe(false)
  })
})

it.effect("waits for inherited pipes, times out, and kills the process group", () => {
  const temporaryRoot = mkdtempSync(join(tmpdir(), "hswm-s2s-process-"))
  const pidPath = join(temporaryRoot, "descendant.pid")
  const descendantCode = "setInterval(() => undefined, 1000)"
  const leaderCode = [
    "const { spawn } = require('node:child_process')",
    "const { writeFileSync } = require('node:fs')",
    `const child = spawn(process.execPath, ['-e', ${JSON.stringify(descendantCode)}], { stdio: ['ignore', 1, 2] })`,
    "writeFileSync(process.argv[1], String(child.pid))",
    "child.unref()"
  ].join(";")

  const program = Effect.gen(function* () {
    const outcome = yield* runS2SBoundedProcess(
      baseSpec({
        arguments: ["-e", leaderCode, pidPath],
        timeoutMillis: 100
      })
    ).pipe(Effect.either)
    expect(Either.isLeft(outcome)).toBe(true)
    if (Either.isLeft(outcome)) {
      expect(outcome.left.reason).toBe("TIMED_OUT")
    }
    const pid = yield* Effect.promise(() => readPidEventually(pidPath))
    expect(pid).not.toBeNull()
    if (pid !== null) {
      expect(
        yield* Effect.promise(() => waitForProcessToDisappear(pid))
      ).toBe(true)
    }
  })

  return program.pipe(
    Effect.ensuring(
      Effect.sync(() => rmSync(temporaryRoot, { force: true, recursive: true }))
    )
  )
})

it.effect("does not return success while a closed-stdio descendant remains live", () => {
  const temporaryRoot = mkdtempSync(join(tmpdir(), "hswm-s2s-descendant-"))
  const pidPath = join(temporaryRoot, "descendant.pid")
  const descendantCode = "setInterval(() => undefined, 1000)"
  const leaderCode = [
    "const { spawn } = require('node:child_process')",
    "const { writeFileSync } = require('node:fs')",
    `const child = spawn(process.execPath, ['-e', ${JSON.stringify(descendantCode)}], { stdio: 'ignore' })`,
    "writeFileSync(process.argv[1], String(child.pid))",
    "child.unref()"
  ].join(";")

  const program = Effect.gen(function* () {
    const result = yield* runS2SBoundedProcess(
      baseSpec({ arguments: ["-e", leaderCode, pidPath] })
    )
    expect(result.exitCode).toBe(0)
    const pid = yield* Effect.promise(() => readPidEventually(pidPath))
    expect(pid).not.toBeNull()
    if (pid !== null) {
      expect(
        yield* Effect.promise(() => waitForProcessToDisappear(pid))
      ).toBe(true)
    }
  })

  return program.pipe(
    Effect.ensuring(
      Effect.sync(() => rmSync(temporaryRoot, { force: true, recursive: true }))
    )
  )
})

it.effect("interrupts only after the detached process group is terminated", () => {
  const temporaryRoot = mkdtempSync(join(tmpdir(), "hswm-s2s-interrupt-"))
  const pidPath = join(temporaryRoot, "leader.pid")
  const childCode = [
    "const { writeFileSync } = require('node:fs')",
    "writeFileSync(process.argv[1], String(process.pid))",
    "setInterval(() => undefined, 1000)"
  ].join(";")

  const program = Effect.gen(function* () {
    const fiber = yield* Effect.fork(
      runS2SBoundedProcess(
        baseSpec({
          arguments: ["-e", childCode, pidPath],
          timeoutMillis: 5_000
        })
      )
    )
    const pid = yield* Effect.promise(() => readPidEventually(pidPath))
    expect(pid).not.toBeNull()
    yield* Fiber.interrupt(fiber)
    if (pid !== null) {
      expect(
        yield* Effect.promise(() => waitForProcessToDisappear(pid))
      ).toBe(true)
    }
  })

  return program.pipe(
    Effect.ensuring(
      Effect.sync(() => rmSync(temporaryRoot, { force: true, recursive: true }))
    )
  )
})

it.effect("surfaces process-group observation denial as an interruption defect", () => {
  const temporaryRoot = mkdtempSync(join(tmpdir(), "hswm-s2s-eperm-"))
  const pidPath = join(temporaryRoot, "leader.pid")
  const childCode = [
    "const { writeFileSync } = require('node:fs')",
    "writeFileSync(process.argv[1], String(process.pid))",
    "setInterval(() => undefined, 1000)"
  ].join(";")
  const originalKill = process.kill

  const program = Effect.gen(function* () {
    const fiber = yield* Effect.fork(
      runS2SBoundedProcess(
        baseSpec({
          arguments: ["-e", childCode, pidPath],
          timeoutMillis: 5_000
        })
      )
    )
    const pid = yield* Effect.promise(() => readPidEventually(pidPath))
    expect(pid).not.toBeNull()
    process.kill = (targetPid: number, signal?: string | number): true => {
      if (targetPid < 0 && signal === 0) {
        const error = new Error("synthetic process-group observation denial")
        Object.defineProperty(error, "code", {
          enumerable: true,
          value: "EPERM"
        })
        throw error
      }
      return originalKill(targetPid, signal)
    }
    const interrupted = yield* Fiber.interrupt(fiber)
    process.kill = originalKill
    expect(Exit.isFailure(interrupted)).toBe(true)
    if (Exit.isFailure(interrupted)) {
      const defects = Array.from(Cause.defects(interrupted.cause))
      expect(
        defects.some(
          (defect) =>
            typeof defect === "object" &&
            defect !== null &&
            "reason" in defect &&
            defect.reason === "PROCESS_GROUP_LIFECYCLE_FAILED"
        )
      ).toBe(true)
    }
    if (pid !== null) {
      expect(
        yield* Effect.promise(() => waitForProcessToDisappear(pid))
      ).toBe(true)
    }
  })

  return program.pipe(
    Effect.ensuring(
      Effect.sync(() => {
        process.kill = originalKill
        rmSync(temporaryRoot, { force: true, recursive: true })
      })
    )
  )
})

it("freezes the confirm and adjudicate process contracts", () => {
  expect("S2SPythonNumericExecutor" in PublicApi).toBe(false)
  expect("makeS2SPythonNumericExecutorProcessLayer" in PublicApi).toBe(false)
  expect([...S2S_NUMERIC_CONFIRM_ARGUMENTS]).toEqual([
    "-B",
    "-P",
    "-s",
    "-m",
    "hswm.experiments.swm0w_s2s_numeric_oracle",
    "confirm"
  ])
  expect([...S2S_NUMERIC_ADJUDICATE_ARGUMENTS]).toEqual([
    "-B",
    "-P",
    "-s",
    "-m",
    "hswm.experiments.swm0w_s2s_numeric_oracle",
    "adjudicate"
  ])
  expect(S2S_NUMERIC_CONFIRM_TIMEOUT_MILLIS).toBe(7_200_000)
  expect(S2S_NUMERIC_ADJUDICATE_TIMEOUT_MILLIS).toBe(1_200_000)
  expect(S2S_NUMERIC_CANDIDATE_MAX_BYTES).toBe(60 * 1_048_576)
  expect(S2S_NUMERIC_ADJUDICATION_MAX_BYTES).toBe(4 * 1_048_576)
  expect(S2S_NUMERIC_STDERR_MAX_BYTES).toBe(8_192)
})

it.effect("rejects an accessor-bearing Python configuration without reading it", () => {
  let invoked = false
  const config: Record<string, string> = {
    expectedNumpyVersion: "2.5.2",
    expectedPythonExecutableSha256: "0".repeat(64),
    expectedPythonVersion: "3.12.13",
    pythonExecutable: "/not/read",
    repositoryRoot: "/not/read"
  }
  Object.defineProperty(config, "repositoryRoot", {
    enumerable: true,
    get: () => {
      invoked = true
      return REPOSITORY_ROOT
    }
  })
  const layer = makeS2SPythonNumericExecutorProcessLayer(
    config as unknown as Parameters<
      typeof makeS2SPythonNumericExecutorProcessLayer
    >[0]
  )
  return Effect.gen(function* () {
    const outcome = yield* Effect.gen(function* () {
      return yield* S2SPythonNumericExecutor
    }).pipe(Effect.provide(layer), Effect.either)
    expect(Either.isLeft(outcome)).toBe(true)
    if (Either.isLeft(outcome)) {
      expect(outcome.left.reason).toBe("CONFIGURATION_INVALID")
    }
    expect(invoked).toBe(false)
  })
})

it("decodes canonical exit-2 errors and rejects partial stdout first", () => {
  const input = textEncoder.encode("{}\n")
  const stderr = numericErrorBytes("confirm")
  const rejected = interpretS2SPythonNumericProcessResult(
    "CONFIRM",
    input,
    TEST_IDENTITY_SHA256,
    {
      exitCode: 2,
      stdout: new Uint8Array(),
      stderr,
      elapsedNanoseconds: 10
    }
  )
  expect(Either.isLeft(rejected)).toBe(true)
  if (Either.isLeft(rejected)) {
    expect(rejected.left.reason).toBe("NUMERIC_ORACLE_REJECTED")
    expect(rejected.left.oracleErrorCode).toBe("INVALID_CANONICAL_DOCUMENT")
    expect(rejected.left.oracleStage).toBe("CANONICAL_DOCUMENT")
    expect(rejected.left.oracleReceiptSha256).toMatch(/^[0-9a-f]{64}$/)
  }

  const partial = interpretS2SPythonNumericProcessResult(
    "CONFIRM",
    input,
    TEST_IDENTITY_SHA256,
    {
      exitCode: 2,
      stdout: textEncoder.encode("{\"partial\":true}\n"),
      stderr,
      elapsedNanoseconds: 10
    }
  )
  expect(Either.isLeft(partial)).toBe(true)
  if (Either.isLeft(partial)) {
    expect(partial.left.reason).toBe("PARTIAL_STDOUT_OBSERVED")
  }
})

it("validates opaque float-bearing output and returns defensive byte copies", () => {
  const input = textEncoder.encode("{}\n")
  const stdout = textEncoder.encode('{"metric":1.25}\n')
  const outcome = interpretS2SPythonNumericProcessResult(
    "CONFIRM",
    input,
    TEST_IDENTITY_SHA256,
    {
      exitCode: 0,
      stdout,
      stderr: new Uint8Array(),
      elapsedNanoseconds: 10
    }
  )
  expect(Either.isRight(outcome)).toBe(true)
  if (Either.isRight(outcome)) {
    stdout[0] = 0x78
    const first = outcome.right.readCanonicalBytes()
    expect(new TextDecoder().decode(first)).toBe('{"metric":1.25}\n')
    first[0] = 0x78
    expect(new TextDecoder().decode(outcome.right.readCanonicalBytes())).toBe(
      '{"metric":1.25}\n'
    )
  }

  const stderrOutcome = interpretS2SPythonNumericProcessResult(
    "ADJUDICATE",
    input,
    TEST_IDENTITY_SHA256,
    {
      exitCode: 0,
      stdout: textEncoder.encode("{}\n"),
      stderr: textEncoder.encode("unexpected"),
      elapsedNanoseconds: 10
    }
  )
  expect(Either.isLeft(stderrOutcome)).toBe(true)
  if (Either.isLeft(stderrOutcome)) {
    expect(stderrOutcome.left.reason).toBe("STDERR_CONTRACT_REJECTED")
  }
})

it("rejects malformed canonical numeric error receipts", () => {
  const errorBytes = numericErrorBytes("adjudicate")
  const errorText = new TextDecoder().decode(errorBytes)
  const receiptOffset =
    errorText.indexOf('"receipt_sha256":"') +
    Buffer.byteLength('"receipt_sha256":"')
  errorBytes[receiptOffset] = errorBytes[receiptOffset] === 0x30 ? 0x31 : 0x30
  const outcome = interpretS2SPythonNumericProcessResult(
    "ADJUDICATE",
    textEncoder.encode("{}\n"),
    TEST_IDENTITY_SHA256,
    {
      exitCode: 3,
      stdout: new Uint8Array(),
      stderr: errorBytes,
      elapsedNanoseconds: 10
    }
  )
  expect(Either.isLeft(outcome)).toBe(true)
  if (Either.isLeft(outcome)) {
    expect(outcome.left.reason).toBe("ERROR_DOCUMENT_REJECTED")
    expect(outcome.left.exitCode).toBe(3)
  }

  const validExitThree = interpretS2SPythonNumericProcessResult(
    "ADJUDICATE",
    textEncoder.encode("{}\n"),
    TEST_IDENTITY_SHA256,
    {
      exitCode: 3,
      stdout: new Uint8Array(),
      stderr: numericErrorBytes(
        "adjudicate",
        "INTERNAL_NUMERIC_FAILURE",
        "PROCESS_ADAPTER"
      ),
      elapsedNanoseconds: 10
    }
  )
  expect(Either.isLeft(validExitThree)).toBe(true)
  if (Either.isLeft(validExitThree)) {
    expect(validExitThree.left.reason).toBe("NUMERIC_ORACLE_REJECTED")
    expect(validExitThree.left.exitCode).toBe(3)
    expect(validExitThree.left.oracleErrorCode).toBe(
      "INTERNAL_NUMERIC_FAILURE"
    )
  }
})

it.effect.skipIf(!existsSync(PINNED_VENV_PYTHON))(
  "runs the pinned golden-only Python boundary and returns an immutable receipt",
  () => {
    const resolvedPython = realpathSync(PINNED_VENV_PYTHON)
    const executableSha256 = rawS2SFileSha256(
      readFileSync(resolvedPython)
    )
    return Effect.gen(function* () {
      const verifier = yield* S2SPythonGoldenVerifier
      const identity = verifier.runtimeSourceIdentity
      const receipt = yield* verifier.verify
      expect(receipt.documentByteLength).toBe(
        S2S_NUMERIC_GOLDEN_VECTOR_BYTE_LENGTH
      )
      expect(receipt.rawBytesSha256).toBe(
        S2S_NUMERIC_GOLDEN_VECTOR_DOCUMENT_SHA256
      )
      expect(receipt.receiptSha256).toBe(
        S2S_NUMERIC_GOLDEN_VECTOR_RECEIPT_SHA256
      )
      expect(receipt.commandElapsedNanoseconds).toBeGreaterThan(0)
      expect(receipt.runtimeSourceIdentityReceiptSha256).toBe(
        identity.receiptSha256
      )
      expect("canonicalUtf8WithLf" in receipt).toBe(false)
      expect(identity.sourceClosure).toHaveLength(10)
      expect(
        identity.sourceClosure.map((entry) => ({
          path: entry.path,
          sha256: entry.rawBytesSha256
        }))
      ).toEqual([...S2S_NUMERIC_LOCAL_SOURCE_CLOSURE])
      expect(identity.processEnvironmentContract).toEqual({
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
        PYTHONPYCACHEPREFIX: "SCOPED_PRIVATE_DIRECTORY",
        PYTHONUTF8: "1",
        TZ: "UTC",
        VECLIB_MAXIMUM_THREADS: "1"
      })
      const identityBytes = identity.readCanonicalBytes()
      const identityDocument = JSON.parse(
        new TextDecoder().decode(identityBytes)
      ) as Record<string, unknown>
      expect(identityDocument["process_contract"]).toEqual({
        argv0: PINNED_VENV_PYTHON,
        cwd: REPOSITORY_ROOT,
        executable_transport: "PINNED_PROC_SELF_FILE_DESCRIPTOR",
        retry_count: 0,
        success_stderr_byte_length: 0
      })
      expect(identityDocument["invocation_contracts"]).toMatchObject({
        adjudicate: {
          arguments: [...S2S_NUMERIC_ADJUDICATE_ARGUMENTS],
          stdin_contract:
            "SNAPSHOTTED_OPAQUE_CANONICAL_NUMERIC_CANDIDATE_BYTES",
          stderr_limit_bytes: 8_192,
          stdout_limit_bytes: 4 * 1_048_576,
          timeout_millis: 1_200_000
        },
        confirm: {
          arguments: [...S2S_NUMERIC_CONFIRM_ARGUMENTS],
          stdin_contract:
            "SNAPSHOTTED_OPAQUE_CANONICAL_CONFIRM_REQUEST_BYTES",
          stderr_limit_bytes: 8_192,
          stdout_limit_bytes: 60 * 1_048_576,
          timeout_millis: 7_200_000
        }
      })
      const receiptSha256 = identityDocument["receipt_sha256"]
      delete identityDocument["receipt_sha256"]
      const recomputed = canonicalS2SControlSha256(identityDocument)
      expect(Either.isRight(recomputed)).toBe(true)
      if (Either.isRight(recomputed)) {
        expect(recomputed.right).toBe(receiptSha256)
      }
      identityBytes[0] = 0x78
      expect(identity.readCanonicalBytes()[0]).toBe(0x7b)
    }).pipe(
      Effect.provide(
        makeS2SPythonGoldenVerifierProcessLayer({
          repositoryRoot: REPOSITORY_ROOT,
          pythonExecutable: PINNED_VENV_PYTHON,
          expectedPythonExecutableSha256: executableSha256,
          expectedPythonVersion: "3.12.13",
          expectedNumpyVersion: "2.5.2"
        })
      )
    )
  }
)

it.effect.skipIf(!existsSync(PINNED_VENV_PYTHON))(
  "runs only invalid confirm/adjudicate inputs through the fixed production CLI",
  () => {
    const resolvedPython = realpathSync(PINNED_VENV_PYTHON)
    const executableSha256 = rawS2SFileSha256(readFileSync(resolvedPython))
    return Effect.gen(function* () {
      const executor = yield* S2SPythonNumericExecutor
      const confirmInput = textEncoder.encode("{}\n")
      const confirmEffect = executor.confirm(confirmInput)
      confirmInput[0] = 0xff
      const confirm = yield* confirmEffect.pipe(Effect.either)
      expect(Either.isLeft(confirm)).toBe(true)
      if (Either.isLeft(confirm)) {
        expect(confirm.left.reason).toBe("NUMERIC_ORACLE_REJECTED")
        expect(confirm.left.exitCode).toBe(2)
        expect(confirm.left.oracleErrorCode).toBe("INVALID_CONFIRM_REQUEST")
      }

      const adjudicate = yield* executor
        .adjudicate(textEncoder.encode("{}\n"))
        .pipe(Effect.either)
      expect(Either.isLeft(adjudicate)).toBe(true)
      if (Either.isLeft(adjudicate)) {
        expect(adjudicate.left.reason).toBe("NUMERIC_ORACLE_REJECTED")
        expect(adjudicate.left.exitCode).toBe(2)
        expect(adjudicate.left.oracleErrorCode).toBe(
          "INVALID_NUMERIC_CANDIDATE"
        )
      }
    }).pipe(
      Effect.provide(
        makeS2SPythonNumericExecutorProcessLayer({
          repositoryRoot: REPOSITORY_ROOT,
          pythonExecutable: PINNED_VENV_PYTHON,
          expectedPythonExecutableSha256: executableSha256,
          expectedPythonVersion: "3.12.13",
          expectedNumpyVersion: "2.5.2"
        })
      )
    )
  }
)
