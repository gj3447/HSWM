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
import { rawS2SFileSha256 } from "../src/s2s-canonical.js"
import {
  S2S_NUMERIC_GOLDEN_VECTOR_BYTE_LENGTH,
  S2S_NUMERIC_GOLDEN_VECTOR_DOCUMENT_SHA256,
  S2S_NUMERIC_GOLDEN_VECTOR_RECEIPT_SHA256,
  S2SPythonGoldenVerifier,
  makeS2SPythonGoldenVerifierProcessLayer
} from "../src/s2s-live-python.js"

const PACKAGE_ROOT = process.cwd()
const REPOSITORY_ROOT = resolve(PACKAGE_ROOT, "../../..")
const PINNED_VENV_PYTHON = join(REPOSITORY_ROOT, ".venv/bin/python")

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

it.effect.skipIf(!existsSync(PINNED_VENV_PYTHON))(
  "runs the pinned golden-only Python boundary and returns an immutable receipt",
  () => {
    const resolvedPython = realpathSync(PINNED_VENV_PYTHON)
    const executableSha256 = rawS2SFileSha256(
      readFileSync(resolvedPython)
    )
    return Effect.gen(function* () {
      const verifier = yield* S2SPythonGoldenVerifier
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
      expect("canonicalUtf8WithLf" in receipt).toBe(false)
    }).pipe(
      Effect.provide(
        makeS2SPythonGoldenVerifierProcessLayer({
          repositoryRoot: REPOSITORY_ROOT,
          pythonExecutable: PINNED_VENV_PYTHON,
          expectedPythonExecutableSha256: executableSha256,
          expectedPythonVersion: "3.12.13"
        })
      )
    )
  }
)
