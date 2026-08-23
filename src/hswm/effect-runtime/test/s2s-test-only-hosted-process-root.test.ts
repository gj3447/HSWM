import { spawn, type ChildProcess } from "node:child_process"
import { constants } from "node:fs"
import {
  access,
  appendFile,
  lstat,
  mkdtemp,
  readFile,
  rm,
  writeFile
} from "node:fs/promises"
import { createConnection } from "node:net"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"

import { expect, it } from "@effect/vitest"
import { afterEach } from "vitest"
import { Effect, Either, Exit, Fiber } from "effect"

import * as publicApi from "../src/index.js"
import { S2S_STAGE_ARTIFACT_SPECS } from "../src/s2s-stage-artifact-spec.js"
import {
  S2S_TEST_ONLY_HOSTED_PROCESS_CLASSIFICATION,
  decodeS2STestOnlyHostedProcessTerminalFrame,
  makeS2STestOnlyHostedProcessReconcileFrame
} from "../src/s2s-test-only-hosted-process-protocol.js"
import {
  awaitS2STestOnlyHostedProcessReady,
  reconcileS2STestOnlyHostedProcess,
  runS2STestOnlyHostedProcessRoot,
  s2sTestOnlyHostedProcessSessionPath,
  type S2STestOnlyHostedProcessRootInput
} from "../src/s2s-test-only-hosted-process-root.js"

const temporaryRoots: Array<string> = []
const children = new Set<ChildProcess>()

afterEach(async () => {
  for (const child of children) {
    if (child.exitCode === null && child.signalCode === null) child.kill("SIGKILL")
  }
  children.clear()
  for (const path of temporaryRoots.splice(0)) {
    await rm(path, { recursive: true, force: true })
  }
})

const temporaryRoot = async (): Promise<string> => {
  const path = await mkdtemp(join(tmpdir(), "hswm-pc-test-"))
  await (await import("node:fs/promises")).chmod(path, 0o700)
  temporaryRoots.push(path)
  return path
}

const input = (
  runnerTempPath: string,
  stage: "REGISTER" | "CONFIRM" | "ADJUDICATE" = "REGISTER",
  jobId: "register" | "confirm" | "adjudicate" = "register",
  feasibilityAttempt: 1 | 2 | 3 = 1,
  suffix = "one"
): S2STestOnlyHostedProcessRootInput =>
  Object.freeze({
    classification: S2S_TEST_ONLY_HOSTED_PROCESS_CLASSIFICATION,
    runnerTempPath,
    sessionName: `hswm-s2s-pc-${suffix}`,
    workflowRunId: 101,
    workflowRunAttempt: 1,
    feasibilityAttempt,
    stage,
    jobId
  })

const expectAbsent = async (path: string): Promise<void> => {
  await expect(access(path, constants.F_OK)).rejects.toMatchObject({
    code: "ENOENT"
  })
}

const waitForPath = async (path: string): Promise<void> => {
  const deadline = Date.now() + 5_000
  while (true) {
    try {
      await access(path, constants.F_OK)
      return
    } catch (error) {
      if (
        typeof error !== "object" ||
        error === null ||
        !("code" in error) ||
        error.code !== "ENOENT"
      ) {
        throw error
      }
    }
    if (Date.now() >= deadline) throw new Error(`path did not appear: ${path}`)
    await new Promise<void>((resolveDelay) => setTimeout(resolveDelay, 5))
  }
}

const exchangeRawFrame = (
  socketPath: string,
  frame: Uint8Array
): Promise<Uint8Array> =>
  new Promise((resolveFrame, rejectFrame) => {
    const socket = createConnection(socketPath)
    const chunks: Array<Uint8Array> = []
    socket.once("connect", () => socket.end(frame))
    socket.on("data", (chunk: Buffer) => chunks.push(new Uint8Array(chunk)))
    socket.once("end", () => {
      const byteLength = chunks.reduce(
        (total, chunk) => total + chunk.byteLength,
        0
      )
      const output = new Uint8Array(byteLength)
      let offset = 0
      for (const chunk of chunks) {
        output.set(chunk, offset)
        offset += chunk.byteLength
      }
      resolveFrame(output)
    })
    socket.once("error", rejectFrame)
  })

it("runs READY to RECONCILE to TERMINAL once under one scoped Effect root", async () => {
  const runnerTempPath = await temporaryRoot()
  const seed = input(runnerTempPath)
  const root = Effect.runFork(runS2STestOnlyHostedProcessRoot(seed))
  const ready = await Effect.runPromise(
    awaitS2STestOnlyHostedProcessReady(seed)
  )
  expect(ready.ready.binding.runtimeIdentity.rootPid).toBe(process.pid)

  const sessionPath = s2sTestOnlyHostedProcessSessionPath(
    runnerTempPath,
    seed.sessionName
  )
  const sessionStat = await lstat(sessionPath)
  const tokenStat = await lstat(join(sessionPath, "client.token"))
  const socketStat = await lstat(join(sessionPath, "control.sock"))
  expect(sessionStat.mode & 0o777).toBe(0o700)
  expect(tokenStat.mode & 0o777).toBe(0o600)
  expect(socketStat.mode & 0o777).toBe(0o600)
  expect(socketStat.isSocket()).toBe(true)

  const reconciled = await Effect.runPromise(
    reconcileS2STestOnlyHostedProcess(seed, "success")
  )
  const completed = await Effect.runPromise(Fiber.join(root))
  expect(completed).toEqual(reconciled.terminal)
  expect(completed.terminalStatus).toBe("RECONCILED_ACTION_SUCCESS")
  expect(completed.rootPidObservations).toEqual([
    process.pid,
    process.pid,
    process.pid
  ])
  expect(completed.publicationRetryCount).toBe(0)
  expect(completed.productionCompletionClaimed).toBe(false)
  await expectAbsent(join(sessionPath, "client.token"))
  await expectAbsent(join(sessionPath, "control.sock"))
  await expectAbsent(join(sessionPath, "ready.json"))
  expect(
    await lstat(join(sessionPath, "evidence", "ready.consumed.json"))
  ).toMatchObject({ size: expect.any(Number) })
  expect(
    await lstat(join(sessionPath, "evidence", "terminal.json"))
  ).toMatchObject({ size: expect.any(Number) })
  expect(
    await lstat(join(sessionPath, "evidence", "occurrence.json"))
  ).toMatchObject({ size: expect.any(Number) })

  const replay = await Effect.runPromiseExit(
    reconcileS2STestOnlyHostedProcess(seed, "success")
  )
  expect(Exit.isFailure(replay)).toBe(true)
})

it("uses all three exact structural archive rosters without scientific content", async () => {
  const cases = [
    ["REGISTER", "register", 1, "success", "register"],
    ["CONFIRM", "confirm", 2, "failure", "confirm"],
    ["ADJUDICATE", "adjudicate", 3, "unknown", "adjudicate"]
  ] as const
  const runnerTempPath = await temporaryRoot()
  for (const [stage, jobId, attempt, outcome, suffix] of cases) {
    const seed = input(
      runnerTempPath,
      stage,
      jobId,
      attempt,
      suffix
    )
    const root = Effect.runFork(runS2STestOnlyHostedProcessRoot(seed))
    await Effect.runPromise(awaitS2STestOnlyHostedProcessReady(seed))
    const spec = S2S_STAGE_ARTIFACT_SPECS[stage]
    const archivePath = join(
      runnerTempPath,
      seed.sessionName,
      "upload",
      spec.archiveLogicalName.split("/").at(-1) ?? "missing"
    )
    const archiveStat = await lstat(archivePath)
    expect(archiveStat.isFile()).toBe(true)
    expect(archiveStat.mode & 0o777).toBe(0o600)
    expect(archiveStat.size).toBeGreaterThan(0)

    const reconciled = await Effect.runPromise(
      reconcileS2STestOnlyHostedProcess(seed, outcome)
    )
    await Effect.runPromise(Fiber.join(root))
    expect(reconciled.terminal.terminalStatus).toBe(
      outcome === "success"
        ? "RECONCILED_ACTION_SUCCESS"
        : outcome === "unknown"
          ? "RECONCILED_ACTION_UNKNOWN_NO_RETRY"
          : "RECONCILED_ACTION_FAILURE"
    )
    const occurrence = JSON.parse(
      await readFile(
        join(
          runnerTempPath,
          seed.sessionName,
          "evidence",
          "occurrence.json"
        ),
        "utf8"
      )
    )
    expect(occurrence).toMatchObject({
      classification: "TEST_ONLY_NON_AUTHORIZING",
      claim_scope: "HOSTED_PROCESS_CONTINUITY_MECHANICS_ONLY",
      publisher_diagnostic: outcome,
      publisher_diagnostic_used_as_authority: false,
      publication_retry_count: 0,
      production_authority_claimed: false,
      production_completion_claimed: false,
      scientific_result_claimed: false,
      causal_learning_claimed: false
    })
  }
})

const cliArguments = (
  seed: S2STestOnlyHostedProcessRootInput
): ReadonlyArray<string> =>
  Object.freeze([
    "--runner-temp",
    seed.runnerTempPath,
    "--session",
    seed.sessionName,
    "--workflow-run-id",
    String(seed.workflowRunId),
    "--workflow-run-attempt",
    String(seed.workflowRunAttempt),
    "--feasibility-attempt",
    String(seed.feasibilityAttempt),
    "--stage",
    seed.stage,
    "--job-id",
    seed.jobId
  ])

const waitChild = (
  child: ChildProcess
): Promise<{ readonly code: number | null; readonly signal: NodeJS.Signals | null }> =>
  new Promise((resolveExit, rejectExit) => {
    if (child.exitCode !== null || child.signalCode !== null) {
      resolveExit(
        Object.freeze({ code: child.exitCode, signal: child.signalCode })
      )
      return
    }
    const timeout = setTimeout(() => {
      child.kill("SIGKILL")
      rejectExit(new Error("child did not exit within 15 seconds"))
    }, 15_000)
    child.once("exit", (code, signal) => {
      clearTimeout(timeout)
      resolveExit(Object.freeze({ code, signal }))
    })
    child.once("error", (error) => {
      clearTimeout(timeout)
      rejectExit(error)
    })
  })

const spawnRoot = (
  seed: S2STestOnlyHostedProcessRootInput
): ChildProcess => {
  const packageRoot = resolve(import.meta.dirname, "..")
  const viteNode = join(packageRoot, "node_modules", ".bin", "vite-node")
  const cli = join(
    packageRoot,
    "test",
    "fixtures",
    "s2s-test-only-hosted-process-cli-entry.ts"
  )
  const child = spawn(viteNode, [cli, "root", ...cliArguments(seed)], {
    cwd: packageRoot,
    stdio: ["ignore", "pipe", "pipe"]
  })
  children.add(child)
  return child
}

it("keeps one child root identity across separate foreground processes", async () => {
  const runnerTempPath = await temporaryRoot()
  const seed = input(runnerTempPath, "REGISTER", "register", 1, "child")
  const child = spawnRoot(seed)
  const ready = await Effect.runPromise(
    awaitS2STestOnlyHostedProcessReady(seed)
  )
  expect(ready.ready.binding.runtimeIdentity.rootPid).toBe(child.pid)
  expect(child.pid).not.toBe(process.pid)

  const reconciled = await Effect.runPromise(
    reconcileS2STestOnlyHostedProcess(seed, "unknown")
  )
  expect(reconciled.terminal.binding.runtimeIdentity.rootPid).toBe(child.pid)
  const exited = await waitChild(child)
  children.delete(child)
  expect(exited).toEqual({ code: 0, signal: null })
  expect(reconciled.terminal.terminalStatus).toBe(
    "RECONCILED_ACTION_UNKNOWN_NO_RETRY"
  )
}, 20_000)

it("burns the first malformed connection to a VOID terminal", async () => {
  const runnerTempPath = await temporaryRoot()
  const seed = input(runnerTempPath, "REGISTER", "register", 1, "malformed")
  const root = Effect.runFork(runS2STestOnlyHostedProcessRoot(seed))
  const ready = await Effect.runPromise(
    awaitS2STestOnlyHostedProcessReady(seed)
  )
  await new Promise<void>((resolveSocket, rejectSocket) => {
    const socket = createConnection(ready.paths.socketPath)
    socket.once("connect", () => socket.end(new TextEncoder().encode("{}\n")))
    socket.once("end", resolveSocket)
    socket.once("error", rejectSocket)
    socket.resume()
  })
  const exited = await Effect.runPromiseExit(Fiber.join(root))
  expect(Exit.isFailure(exited)).toBe(true)
  const terminal = JSON.parse(
    await readFile(ready.paths.terminalPath, "utf8")
  )
  expect(terminal).toMatchObject({
    transition: "TERMINAL",
    terminalStatus: "VOID_NO_COMPLETION",
    reconciliationProbeCount: 0,
    productionCompletionClaimed: false,
    publicationRetryCount: 0
  })
  await expectAbsent(ready.paths.tokenPath)
  await expectAbsent(ready.paths.socketPath)
}, 20_000)

it("turns post-READY prepared-byte drift into VOID with zero probe calls", async () => {
  const runnerTempPath = await temporaryRoot()
  const seed = input(runnerTempPath, "CONFIRM", "confirm", 2, "drift")
  const root = Effect.runFork(runS2STestOnlyHostedProcessRoot(seed))
  const ready = await Effect.runPromise(
    awaitS2STestOnlyHostedProcessReady(seed)
  )
  const archiveName =
    S2S_STAGE_ARTIFACT_SPECS.CONFIRM.archiveLogicalName.split("/").at(-1) ??
    "missing"
  await appendFile(join(ready.paths.uploadPath, archiveName), new Uint8Array([0]))
  const reconciled = await Effect.runPromiseExit(
    reconcileS2STestOnlyHostedProcess(seed, "success")
  )
  expect(Exit.isFailure(reconciled)).toBe(true)
  const rootExit = await Effect.runPromiseExit(Fiber.join(root))
  expect(Exit.isFailure(rootExit)).toBe(true)
  const terminal = JSON.parse(
    await readFile(ready.paths.terminalPath, "utf8")
  )
  expect(terminal).toMatchObject({
    terminalStatus: "VOID_NO_COMPLETION",
    reconciliationProbeCount: 0,
    productionCompletionClaimed: false
  })
}, 20_000)

it("rejects hostile root inputs and attempt-stage drift before allocation", async () => {
  const runnerTempPath = await temporaryRoot()
  const valid = input(runnerTempPath, "REGISTER", "register", 1, "hostile")
  let reads = 0
  const accessor = { ...valid }
  Object.defineProperty(accessor, "runnerTempPath", {
    enumerable: true,
    get: () => {
      reads += 1
      throw new Error("accessor must not execute")
    }
  })
  const accessorExit = await Effect.runPromiseExit(
    runS2STestOnlyHostedProcessRoot(accessor)
  )
  expect(Exit.isFailure(accessorExit)).toBe(true)
  expect(reads).toBe(0)

  let traps = 0
  const proxy = new Proxy(valid, {
    ownKeys: () => {
      traps += 1
      throw new Error("proxy trap must not execute")
    }
  })
  const proxyExit = await Effect.runPromiseExit(
    runS2STestOnlyHostedProcessRoot(proxy)
  )
  expect(Exit.isFailure(proxyExit)).toBe(true)
  expect(traps).toBe(0)

  const mismatched = input(
    runnerTempPath,
    "REGISTER",
    "register",
    2,
    "mismatch"
  )
  const mismatchExit = await Effect.runPromiseExit(
    runS2STestOnlyHostedProcessRoot(mismatched)
  )
  expect(Exit.isFailure(mismatchExit)).toBe(true)
  await expectAbsent(join(runnerTempPath, mismatched.sessionName))
})

it("removes a partially allocated session when restrictive creation mode aborts acquire", async () => {
  const runnerTempPath = await temporaryRoot()
  const seed = input(runnerTempPath, "REGISTER", "register", 1, "partial")
  const previousUmask = process.umask(0o777)
  const rootExit = await (async () => {
    try {
      return await Effect.runPromiseExit(
        runS2STestOnlyHostedProcessRoot(seed)
      )
    } finally {
      process.umask(previousUmask)
    }
  })()
  expect(Exit.isFailure(rootExit)).toBe(true)
  await expectAbsent(join(runnerTempPath, seed.sessionName))
}, 20_000)

it("stops an interrupted pre-READY reconcile client before it can burn a later session", async () => {
  const runnerTempPath = await temporaryRoot()
  const seed = input(runnerTempPath, "REGISTER", "register", 1, "client-abort")
  const staleClient = Effect.runFork(
    reconcileS2STestOnlyHostedProcess(seed, "success")
  )
  await new Promise<void>((resolveDelay) => setTimeout(resolveDelay, 75))
  await Effect.runPromise(Fiber.interrupt(staleClient))
  await new Promise<void>((resolveDelay) => setTimeout(resolveDelay, 150))

  const root = Effect.runFork(runS2STestOnlyHostedProcessRoot(seed))
  await Effect.runPromise(awaitS2STestOnlyHostedProcessReady(seed))
  const reconciled = await Effect.runPromise(
    reconcileS2STestOnlyHostedProcess(seed, "success")
  )
  expect(reconciled.terminal.terminalStatus).toBe(
    "RECONCILED_ACTION_SUCCESS"
  )
  await Effect.runPromise(Fiber.join(root))
}, 20_000)

it("finishes an accepted reconcile under one uninterruptible commit with the original token", async () => {
  const runnerTempPath = await temporaryRoot()
  const seed = input(runnerTempPath, "REGISTER", "register", 1, "linearized")
  const root = Effect.runFork(runS2STestOnlyHostedProcessRoot(seed))
  const ready = await Effect.runPromise(
    awaitS2STestOnlyHostedProcessReady(seed)
  )
  const originalToken = new Uint8Array(await readFile(ready.paths.tokenPath))
  const request = makeS2STestOnlyHostedProcessReconcileFrame(
    ready.ready,
    "success",
    originalToken
  )
  expect(Either.isRight(request)).toBe(true)
  if (Either.isLeft(request)) throw new Error("reconcile frame construction failed")
  const responsePromise = exchangeRawFrame(ready.paths.socketPath, request.right)
  await waitForPath(ready.paths.consumedReadyPath)
  const interruption = Effect.runPromise(Fiber.interrupt(root))
  const response = await responsePromise
  await interruption

  const decoded = decodeS2STestOnlyHostedProcessTerminalFrame(
    response,
    ready.ready.binding,
    originalToken
  )
  expect(Either.isRight(decoded)).toBe(true)
  if (Either.isRight(decoded)) {
    expect(decoded.right.terminalStatus).toBe("RECONCILED_ACTION_SUCCESS")
  }
  expect(
    Either.isLeft(
      decodeS2STestOnlyHostedProcessTerminalFrame(
        response,
        ready.ready.binding,
        new Uint8Array(32)
      )
    )
  ).toBe(true)
}, 20_000)

it("contains an accepted-socket abort without an uncaught process error", async () => {
  const runnerTempPath = await temporaryRoot()
  const seed = input(runnerTempPath, "REGISTER", "register", 1, "reset")
  const root = Effect.runFork(runS2STestOnlyHostedProcessRoot(seed))
  const ready = await Effect.runPromise(
    awaitS2STestOnlyHostedProcessReady(seed)
  )
  const originalToken = new Uint8Array(await readFile(ready.paths.tokenPath))
  const request = makeS2STestOnlyHostedProcessReconcileFrame(
    ready.ready,
    "success",
    originalToken
  )
  expect(Either.isRight(request)).toBe(true)
  if (Either.isLeft(request)) throw new Error("reconcile frame construction failed")
  await new Promise<void>((resolveReset, rejectReset) => {
    const socket = createConnection(ready.paths.socketPath)
    socket.once("connect", () => {
      socket.write(request.right, () => {
        socket.destroy()
        resolveReset()
      })
    })
    socket.once("error", rejectReset)
  })
  const rootExit = await Effect.runPromiseExit(Fiber.join(root))
  if (Exit.isSuccess(rootExit)) {
    expect(rootExit.value.externalExactlyOnceClaimed).toBe(false)
  }
  await expectAbsent(ready.paths.tokenPath)
  await expectAbsent(ready.paths.socketPath)
}, 20_000)

it("never returns client success when occurrence commit is preoccupied", async () => {
  const runnerTempPath = await temporaryRoot()
  const seed = input(runnerTempPath, "REGISTER", "register", 1, "split-brain")
  const root = Effect.runFork(runS2STestOnlyHostedProcessRoot(seed))
  const ready = await Effect.runPromise(
    awaitS2STestOnlyHostedProcessReady(seed)
  )
  await writeFile(ready.paths.occurrencePath, "occupied\n", {
    flag: "wx",
    mode: 0o600
  })
  const clientExit = await Effect.runPromiseExit(
    reconcileS2STestOnlyHostedProcess(seed, "success")
  )
  const rootExit = await Effect.runPromiseExit(Fiber.join(root))
  expect(Exit.isFailure(clientExit)).toBe(true)
  expect(Exit.isFailure(rootExit)).toBe(true)
  await expectAbsent(ready.paths.terminalPath)
  expect(await readFile(ready.paths.occurrencePath, "utf8")).toBe("occupied\n")
}, 20_000)

it("SIGTERM interrupts the scoped root without a terminal or orphaned socket", async () => {
  const runnerTempPath = await temporaryRoot()
  const seed = input(runnerTempPath, "REGISTER", "register", 1, "sigterm")
  const child = spawnRoot(seed)
  await Effect.runPromise(awaitS2STestOnlyHostedProcessReady(seed))
  expect(child.kill("SIGTERM")).toBe(true)
  const exited = await waitChild(child)
  children.delete(child)
  expect(exited.code).toBe(1)
  const sessionPath = join(runnerTempPath, seed.sessionName)
  await expectAbsent(join(sessionPath, "client.token"))
  await expectAbsent(join(sessionPath, "control.sock"))
  await expectAbsent(join(sessionPath, "ready.json"))
  await expectAbsent(join(sessionPath, "evidence", "terminal.json"))
}, 20_000)

it("SIGKILL root death emits no terminal or completion", async () => {
  const runnerTempPath = await temporaryRoot()
  const seed = input(runnerTempPath, "REGISTER", "register", 1, "sigkill")
  const child = spawnRoot(seed)
  const ready = await Effect.runPromise(
    awaitS2STestOnlyHostedProcessReady(seed)
  )
  expect(child.kill("SIGKILL")).toBe(true)
  const exited = await waitChild(child)
  children.delete(child)
  expect(exited.signal).toBe("SIGKILL")
  await expectAbsent(ready.paths.terminalPath)
  expect((await lstat(ready.paths.tokenPath)).isFile()).toBe(true)
  expect((await lstat(ready.paths.readyPath)).isFile()).toBe(true)
  expect((await lstat(ready.paths.socketPath)).isSocket()).toBe(true)
  expect(child.exitCode === null || child.exitCode !== 0).toBe(true)
}, 20_000)

it("keeps root, client, CLI, and path helpers absent from the package root", () => {
  for (const key of [
    "runS2STestOnlyHostedProcessRoot",
    "awaitS2STestOnlyHostedProcessReady",
    "reconcileS2STestOnlyHostedProcess",
    "parseS2STestOnlyHostedProcessCliArguments",
    "s2sTestOnlyHostedProcessSessionPath"
  ]) {
    expect(key in publicApi).toBe(false)
  }
})
