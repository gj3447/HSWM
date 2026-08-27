import { spawn, type ChildProcess } from "node:child_process"
import { createHash } from "node:crypto"
import { constants } from "node:fs"
import {
  access,
  chmod,
  lstat,
  mkdir,
  mkdtemp,
  readdir,
  rm,
  writeFile
} from "node:fs/promises"
import { setPriority, tmpdir } from "node:os"
import { join, resolve } from "node:path"

import { afterEach, expect, it } from "vitest"

import { canonicalAtomV2StateJournalSlotName } from "../src/canonical-atom-v2-state-journal-file.js"

const LINEAGE = "lineage:journal:process-race"
const SCHEMA = "d".repeat(64)
const MAX_OUTPUT_BYTES = 16_384
const SHA256 = /^[0-9a-f]{64}$/
const children = new Set<ChildProcess>()
const temporaryRoots: Array<string> = []

interface PublishSuccessFrame {
  readonly mode: "publish"
  readonly pid: number
  readonly workerId: string
  readonly ok: true
  readonly tag: "Committed" | "AlreadyCommitted"
  readonly sha256: string
}

interface PublishFailureFrame {
  readonly mode: "publish"
  readonly pid: number
  readonly workerId: string
  readonly ok: false
  readonly operation: string
  readonly reason: string
}

interface RecoveryEntryFrame {
  readonly descriptor: {
    readonly mediaType: string
    readonly byteLength: number
    readonly sha256: string
  }
  readonly bytesBase64: string
}

interface RecoverSuccessFrame {
  readonly mode: "recover"
  readonly pid: number
  readonly ok: true
  readonly entries: ReadonlyArray<RecoveryEntryFrame>
}

interface RecoverFailureFrame {
  readonly mode: "recover"
  readonly pid: number
  readonly ok: false
  readonly operation: string
  readonly reason: string
}

type PublishFrame = PublishSuccessFrame | PublishFailureFrame
type RecoverFrame = RecoverSuccessFrame | RecoverFailureFrame
type WorkerFrame = PublishFrame | RecoverFrame

const isObject = (input: unknown): input is Record<string, unknown> =>
  typeof input === "object" && input !== null && !Array.isArray(input)
const isCanonicalBase64 = (input: string): boolean =>
  Buffer.from(input, "base64").toString("base64") === input

const decodeWorkerFrame = (text: string): WorkerFrame => {
  const parsed: unknown = JSON.parse(text)
  if (
    !isObject(parsed) ||
    (parsed["mode"] !== "publish" && parsed["mode"] !== "recover") ||
    typeof parsed["pid"] !== "number" ||
    !Number.isSafeInteger(parsed["pid"]) ||
    parsed["pid"] < 1 ||
    typeof parsed["ok"] !== "boolean"
  ) {
    throw new Error("worker emitted a malformed terminal frame")
  }
  if (parsed["mode"] === "publish") {
    if (typeof parsed["workerId"] !== "string") {
      throw new Error("publish frame has no worker identity")
    }
    if (parsed["ok"] === true) {
      if (
        (parsed["tag"] !== "Committed" &&
          parsed["tag"] !== "AlreadyCommitted") ||
        typeof parsed["sha256"] !== "string" ||
        !SHA256.test(parsed["sha256"])
      ) {
        throw new Error("successful publish frame is malformed")
      }
      return parsed as unknown as PublishSuccessFrame
    }
    if (
      typeof parsed["operation"] !== "string" ||
      typeof parsed["reason"] !== "string"
    ) {
      throw new Error("failed publish frame is malformed")
    }
    return parsed as unknown as PublishFailureFrame
  }
  if (parsed["ok"] === true) {
    if (
      !Array.isArray(parsed["entries"]) ||
      parsed["entries"].some((entry) =>
        !isObject(entry) ||
        !isObject(entry["descriptor"]) ||
        typeof entry["descriptor"]["mediaType"] !== "string" ||
        typeof entry["descriptor"]["byteLength"] !== "number" ||
        !Number.isSafeInteger(entry["descriptor"]["byteLength"]) ||
        entry["descriptor"]["byteLength"] < 1 ||
        typeof entry["descriptor"]["sha256"] !== "string" ||
        !SHA256.test(entry["descriptor"]["sha256"]) ||
        typeof entry["bytesBase64"] !== "string" ||
        !isCanonicalBase64(entry["bytesBase64"])
      )
    ) {
      throw new Error("successful recovery frame is malformed")
    }
    return parsed as unknown as RecoverSuccessFrame
  }
  if (
    typeof parsed["operation"] !== "string" ||
    typeof parsed["reason"] !== "string"
  ) {
    throw new Error("failed recovery frame is malformed")
  }
  return parsed as unknown as RecoverFailureFrame
}

const waitForPath = async (path: string): Promise<void> => {
  const deadline = Date.now() + 5_000
  while (true) {
    try {
      await access(path, constants.F_OK)
      return
    } catch (cause) {
      if (
        typeof cause !== "object" ||
        cause === null ||
        !("code" in cause) ||
        cause.code !== "ENOENT"
      ) {
        throw cause
      }
    }
    if (Date.now() >= deadline) {
      throw new Error(`worker barrier marker did not appear: ${path}`)
    }
    await new Promise<void>((resolveDelay) => setTimeout(resolveDelay, 5))
  }
}

const terminateAndWait = (child: ChildProcess): Promise<void> =>
  new Promise((resolveTermination) => {
    let settled = false
    const settle = (): void => {
      if (settled) return
      settled = true
      clearTimeout(fallback)
      resolveTermination()
    }
    const fallback = setTimeout(settle, 1_000)
    child.once("close", settle)
    child.once("error", settle)
    if (child.exitCode === null && child.signalCode === null) {
      child.kill("SIGKILL")
    }
  })

afterEach(async () => {
  const terminations: Array<Promise<void>> = []
  for (const child of children) {
    terminations.push(terminateAndWait(child))
  }
  await Promise.all(terminations)
  children.clear()
  for (const path of temporaryRoots.splice(0)) {
    await rm(path, { recursive: true, force: true })
  }
})

const spawnWorker = (
  arguments_: ReadonlyArray<string>
): Promise<WorkerFrame> => {
  const packageRoot = resolve(import.meta.dirname, "..")
  const viteNode = join(packageRoot, "node_modules", ".bin", "vite-node")
  const worker = join(
    packageRoot,
    "test",
    "fixtures",
    "canonical-atom-v2-state-journal-process-worker.ts"
  )
  const child = spawn(viteNode, [worker, ...arguments_], {
    cwd: packageRoot,
    stdio: ["ignore", "pipe", "pipe"]
  })
  child.once("spawn", () => {
    if (child.pid === undefined) return
    try {
      setPriority(child.pid, 10)
    } catch {
      // Priority is only a contention hint; process identity and assertions remain unchanged.
    }
  })
  children.add(child)
  const completed = new Promise<WorkerFrame>((resolveFrame, rejectFrame) => {
    let stdout = ""
    let stderr = ""
    let terminalError: Error | null = null
    let settled = false
    const rejectOnce = (cause: unknown): void => {
      if (settled) return
      settled = true
      clearTimeout(timeout)
      rejectFrame(cause)
    }
    const resolveOnce = (frame: WorkerFrame): void => {
      if (settled) return
      settled = true
      clearTimeout(timeout)
      resolveFrame(frame)
    }
    const terminate = (cause: Error): void => {
      if (terminalError === null) terminalError = cause
      if (child.exitCode === null && child.signalCode === null) {
        child.kill("SIGKILL")
      }
      setTimeout(() => {
        if (settled) return
        children.delete(child)
        rejectOnce(terminalError ?? cause)
      }, 1_000)
    }
    const timeout = setTimeout(() => {
      terminate(new Error("journal worker did not close within 15 seconds"))
    }, 15_000)
    child.stdout?.on("data", (chunk: Buffer) => {
      stdout += chunk.toString("utf8")
      if (Buffer.byteLength(stdout, "utf8") > MAX_OUTPUT_BYTES) {
        terminate(new Error("journal worker stdout exceeded its bound"))
      }
    })
    child.stderr?.on("data", (chunk: Buffer) => {
      stderr += chunk.toString("utf8")
      if (Buffer.byteLength(stderr, "utf8") > MAX_OUTPUT_BYTES) {
        terminate(new Error("journal worker stderr exceeded its bound"))
      }
    })
    child.once("error", (cause) => {
      children.delete(child)
      rejectOnce(cause)
    })
    child.once("close", (code, signal) => {
      children.delete(child)
      if (settled) return
      if (terminalError !== null) {
        rejectOnce(terminalError)
        return
      }
      if (code !== 0 || signal !== null) {
        rejectOnce(
          new Error(
            `journal worker failed code=${String(code)} signal=${String(signal)} stderr=${stderr}`
          )
        )
        return
      }
      const lines = stdout.trim().split("\n")
      if (lines.length !== 1 || lines[0] === undefined || lines[0] === "") {
        rejectOnce(new Error("journal worker did not emit exactly one frame"))
        return
      }
      try {
        resolveOnce(decodeWorkerFrame(lines[0]))
      } catch (cause) {
        rejectOnce(cause)
      }
    })
  })
  void completed.catch(() => undefined)
  return completed
}

const makeCaseRoot = async () => {
  const base = await mkdtemp(join(tmpdir(), "hswm-canonical-v2-process-race-"))
  await chmod(base, 0o700)
  temporaryRoots.push(base)
  const root = join(base, "journal")
  const barrier = join(base, "barrier")
  await mkdir(root, { mode: 0o700 })
  await mkdir(barrier, { mode: 0o700 })
  return Object.freeze({ base, root, barrier })
}

const hash = (input: Uint8Array): string =>
  createHash("sha256").update(input).digest("hex")

const runBarrierPair = async (
  left: Uint8Array,
  right: Uint8Array
): Promise<{
  readonly root: string
  readonly frames: readonly [PublishFrame, PublishFrame]
  readonly observer: RecoverSuccessFrame
}> => {
  const paths = await makeCaseRoot()
  const release = join(paths.barrier, "release")
  const leftReady = join(paths.barrier, "left.ready")
  const rightReady = join(paths.barrier, "right.ready")
  const leftResult = spawnWorker([
    "publish",
    paths.root,
    LINEAGE,
    SCHEMA,
    "left",
    Buffer.from(left).toString("base64"),
    leftReady,
    release
  ])
  const rightResult = spawnWorker([
    "publish",
    paths.root,
    LINEAGE,
    SCHEMA,
    "right",
    Buffer.from(right).toString("base64"),
    rightReady,
    release
  ])
  await Promise.all([waitForPath(leftReady), waitForPath(rightReady)])
  await writeFile(release, "release\n", { flag: "wx", mode: 0o400 })
  const frames = await Promise.all([leftResult, rightResult])
  if (frames[0].mode !== "publish" || frames[1].mode !== "publish") {
    throw new Error("publisher emitted a non-publish frame")
  }
  const observed = await spawnWorker([
    "recover",
    paths.root,
    LINEAGE,
    SCHEMA
  ])
  if (observed.mode !== "recover" || observed.ok === false) {
    throw new Error("fresh observer could not recover the process-race journal")
  }
  const publishFrames: readonly [PublishFrame, PublishFrame] = [
    frames[0],
    frames[1]
  ]
  return Object.freeze({
    root: paths.root,
    frames: publishFrames,
    observer: observed
  })
}

it.skipIf(process.platform === "win32")(
  "has one exact hard-link winner in a deterministic independent-process race",
  async () => {
    const left = Buffer.from("left", "utf8")
    const right = Buffer.from("right", "utf8")
    const result = await runBarrierPair(left, right)
    const successes = result.frames.filter(
      (frame): frame is PublishSuccessFrame => frame.ok
    )
    const failures = result.frames.filter(
      (frame): frame is PublishFailureFrame => !frame.ok
    )
    expect(successes).toHaveLength(1)
    expect(failures).toHaveLength(1)
    expect(successes[0]?.tag).toBe("Committed")
    expect(failures[0]).toMatchObject({
      operation: "PUBLISH",
      reason: "CONCURRENT_PUBLICATION_CONFLICT"
    })
    expect(result.frames.map((frame) => frame.workerId).sort()).toEqual([
      "left",
      "right"
    ])
    expect(result.frames[0].pid).not.toBe(result.frames[1].pid)
    expect(result.frames[0].pid).not.toBe(process.pid)
    expect(result.frames[1].pid).not.toBe(process.pid)

    const winnerBytes = successes[0]?.workerId === "left" ? left : right
    const loserBytes = successes[0]?.workerId === "left" ? right : left
    const winnerHash = hash(winnerBytes)
    expect(successes[0]?.sha256).toBe(winnerHash)
    expect(result.observer.pid).not.toBe(process.pid)
    expect(result.observer.pid).not.toBe(result.frames[0].pid)
    expect(result.observer.pid).not.toBe(result.frames[1].pid)
    expect(result.observer.entries).toHaveLength(1)
    expect(result.observer.entries[0]?.descriptor.sha256).toBe(winnerHash)
    expect(result.observer.entries[0]?.bytesBase64).toBe(
      Buffer.from(winnerBytes).toString("base64")
    )
    expect(result.observer.entries[0]?.bytesBase64).not.toBe(
      Buffer.from(loserBytes).toString("base64")
    )

    const slotNames = await readdir(join(result.root, "journal-slots"))
    expect(slotNames).toEqual([
      canonicalAtomV2StateJournalSlotName(LINEAGE, SCHEMA, 0)
    ])
    const slotStat = await lstat(
      join(result.root, "journal-slots", slotNames[0]!)
    )
    const objectStat = await lstat(
      join(result.root, "journal-objects", winnerHash)
    )
    expect({ device: slotStat.dev, inode: slotStat.ino }).toEqual({
      device: objectStat.dev,
      inode: objectStat.ino
    })
    expect(slotStat.nlink).toBe(2)
    expect(objectStat.nlink).toBe(2)
  },
  30_000
)

it.skipIf(process.platform === "win32")(
  "reconciles identical independent-process racers as Committed plus AlreadyCommitted",
  async () => {
    const record = Buffer.from("same-process-record", "utf8")
    const result = await runBarrierPair(record, record)
    expect(result.frames.every((frame) => frame.ok)).toBe(true)
    const tags = result.frames
      .filter((frame): frame is PublishSuccessFrame => frame.ok)
      .map((frame) => frame.tag)
      .sort()
    expect(tags).toEqual(["AlreadyCommitted", "Committed"])
    expect(result.frames.map((frame) => frame.workerId).sort()).toEqual([
      "left",
      "right"
    ])
    expect(
      result.frames
        .filter((frame): frame is PublishSuccessFrame => frame.ok)
        .every((frame) => frame.sha256 === hash(record))
    ).toBe(true)
    expect(result.frames[0].pid).not.toBe(result.frames[1].pid)
    expect(result.observer.pid).not.toBe(result.frames[0].pid)
    expect(result.observer.pid).not.toBe(result.frames[1].pid)
    expect(result.observer.entries).toHaveLength(1)
    expect(result.observer.entries[0]?.descriptor.sha256).toBe(hash(record))
    expect(result.observer.entries[0]?.bytesBase64).toBe(
      Buffer.from(record).toString("base64")
    )
  },
  20_000
)
