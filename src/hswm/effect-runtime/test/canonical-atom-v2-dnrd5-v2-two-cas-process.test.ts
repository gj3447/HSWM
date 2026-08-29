import { spawn, type ChildProcess } from "node:child_process"
import { constants } from "node:fs"
import { access, chmod, mkdtemp, mkdir, rm, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"

import { expect, it } from "vitest"
import { Effect } from "effect"

import { CanonicalAtomV2DurableRuntime, recoverCanonicalAtomV2DurableFromDnrd5DispatcherInternal } from "../src/canonical-atom-v2-durable-runtime.js"
import { resumeDnrd5V2AdmitTwoCas, submitDnrd5V2AdmitTwoCas } from "../src/canonical-atom-v2-dnrd5-durable-permit.js"
import { canonicalAtomV2KeyId } from "../src/canonical-atom-v2-schema.js"
import { makeDnrd5V2TwoCasFileLayer, makeDnrd5V2TwoCasLayer, prepareDnrd5V2TwoCasFixture, type Dnrd5V2TwoCasPreparedFixture } from "./fixtures/canonical-atom-v2-dnrd5-v2-two-cas.js"

const LIMIT = 16_384
const children = new Set<ChildProcess>()
const waitFor = async (path: string) => {
  const deadline = Date.now() + 10_000
  while (true) {
    try { await access(path, constants.F_OK); return } catch (cause) {
      if (typeof cause !== "object" || cause === null || !("code" in cause) || cause.code !== "ENOENT") throw cause
    }
    if (Date.now() >= deadline) throw new Error(`barrier timed out: ${path}`)
    await new Promise<void>((resolveDelay) => setTimeout(resolveDelay, 5))
  }
}
interface ChildFrame { readonly pid: number; readonly milestone: "CAS2_EXACT_R2_CONFIRMED" }
const decodeFrame = (text: string, pid: number | undefined): ChildFrame => {
  const lines = text.trimEnd().split("\n")
  if (lines.length !== 1 || lines[0] === "") throw new Error("worker did not emit exactly one JSON frame")
  const value: unknown = JSON.parse(lines[0]!)
  const record = typeof value === "object" && value !== null && !Array.isArray(value) ? value as Record<string, unknown> : undefined
  const framePid = record?.["pid"]
  if (record === undefined || Object.keys(record).length !== 2 || typeof framePid !== "number" || !Number.isSafeInteger(framePid) || framePid < 1 || record["milestone"] !== "CAS2_EXACT_R2_CONFIRMED" || pid === undefined || framePid !== pid) throw new Error("worker emitted malformed or wrong-process frame")
  return value as ChildFrame
}
const runChild = (args: string[], expectKill = false) => new Promise<{ code: number | null; signal: NodeJS.Signals | null; stdout: string; stderr: string; pid: number | undefined }>((resolveResult, rejectResult) => {
  const packageRoot = resolve(import.meta.dirname, "..")
  const child = spawn(join(packageRoot, "node_modules", ".bin", "vite-node"), [join(packageRoot, "test/fixtures/canonical-atom-v2-dnrd5-v2-two-cas-process-worker.ts"), ...args], { cwd: packageRoot, stdio: ["ignore", "pipe", "pipe"] })
  children.add(child)
  let stdout = ""; let stderr = ""; let done = false
  const finish = (value: { code: number | null; signal: NodeJS.Signals | null; stdout: string; stderr: string; pid: number | undefined }) => { if (!done) { done = true; clearTimeout(timer); children.delete(child); resolveResult(value) } }
  const fail = (cause: Error) => { if (!done) { done = true; clearTimeout(timer); if (child.exitCode === null) child.kill("SIGKILL"); children.delete(child); rejectResult(cause) } }
  const timer = setTimeout(() => fail(new Error("two-CAS worker timed out")), 15_000)
  child.stdout?.on("data", (chunk: Buffer) => { stdout += chunk; if (Buffer.byteLength(stdout) > LIMIT) fail(new Error("worker stdout exceeded bound")) })
  child.stderr?.on("data", (chunk: Buffer) => { stderr += chunk; if (Buffer.byteLength(stderr) > LIMIT) fail(new Error("worker stderr exceeded bound")) })
  child.once("error", fail)
  child.once("close", (code, signal) => finish({ code, signal, stdout, stderr, pid: child.pid }))
}).then((result) => {
  if (expectKill) {
    if (result.signal !== "SIGKILL" || result.stdout !== "" || result.stderr !== "") throw new Error(`killed worker exit code=${String(result.code)} signal=${String(result.signal)} stdout=${result.stdout} stderr=${result.stderr}`)
    return result
  }
  if (result.code !== 0 || result.signal !== null || result.stderr !== "") throw new Error(`worker exit code=${String(result.code)} signal=${String(result.signal)} stderr=${result.stderr}`)
  return { ...result, frame: decodeFrame(result.stdout, result.pid) }
})

const fixtureInput = () => Effect.runPromise(prepareDnrd5V2TwoCasFixture().pipe(Effect.provide(makeDnrd5V2TwoCasLayer())))
const seed = (root: string) => Effect.runPromise(prepareDnrd5V2TwoCasFixture().pipe(Effect.provide(makeDnrd5V2TwoCasFileLayer(root))))
const resume = (root: string, input: Awaited<ReturnType<typeof fixtureInput>>["input"]) => Effect.runPromise(resumeDnrd5V2AdmitTwoCas(input).pipe(Effect.provide(makeDnrd5V2TwoCasFileLayer(root))))
const exact = (root: string, fixture: Dnrd5V2TwoCasPreparedFixture, phase: "S0" | "R1" | "R2") => Effect.runPromise(Effect.gen(function* () {
  const runtime = yield* CanonicalAtomV2DurableRuntime; const witness = yield* recoverCanonicalAtomV2DurableFromDnrd5DispatcherInternal(runtime)
  const revision = fixture.s0Revision + (phase === "S0" ? 0 : phase === "R1" ? 1 : 2)
  expect(witness.state.canonical.revision).toBe(revision); expect(witness.history).toHaveLength(revision); expect(witness.journal).toHaveLength(revision + 1); expect(witness.state.journalHead).toEqual(witness.journal.at(-1)?.descriptor)
  if (phase !== "S0") { expect(witness.journal[fixture.s0Revision + 1]?.descriptor).toEqual(fixture.expectedR1); expect(witness.journal.filter((entry) => entry.descriptor.sha256 === fixture.expectedR1.sha256)).toHaveLength(1) }
  if (phase === "R2") { expect(witness.journal[fixture.s0Revision + 2]?.descriptor).toEqual(fixture.expectedR2); expect(witness.state.journalHead).toEqual(fixture.expectedR2); expect(witness.journal.filter((entry) => entry.descriptor.sha256 === fixture.expectedR2.sha256)).toHaveLength(1) }
  return witness
}).pipe(Effect.provide(makeDnrd5V2TwoCasFileLayer(root))))
const makeR1 = async (root: string) => {
  const fixture = await fixtureInput()
  const receiptId = fixture.input.receipt.writePayloads.find((x) => x.atomKeyId !== canonicalAtomV2KeyId(fixture.input.receipt.consumption.atom.key))!.atomKeyId
  const forged = { ...fixture.input, receipt: { ...fixture.input.receipt, writePayloads: fixture.input.receipt.writePayloads.map((x) => x.atomKeyId === receiptId ? { ...x, bytes: Uint8Array.from([...x.bytes, 10]) } : x) } }
  await Effect.runPromise(submitDnrd5V2AdmitTwoCas(forged).pipe(Effect.provide(makeDnrd5V2TwoCasFileLayer(root)), Effect.either))
  return fixture
}

const withRoot = async (run: (root: string, barrier: string) => Promise<void>) => {
  const base = await mkdtemp(join(tmpdir(), "hswm-dnrd5-v2-process-")); await chmod(base, 0o700); const root = join(base, "durable"); const barrier = join(base, "barrier"); await mkdir(root, { mode: 0o700 }); await mkdir(barrier, { mode: 0o700 })
  try { await run(root, barrier) } finally { for (const child of children) if (child.exitCode === null) child.kill("SIGKILL"); children.clear(); await rm(base, { recursive: true, force: true }) }
}

it.skipIf(process.platform !== "linux")("CAS1 post-link SIGKILL recovers exact R1 then parent resumes exact R2", async () => withRoot(async (root) => {
  const seeded = await seed(root); const killed = await runChild(["kill-cas1", root], true); expect(killed.stdout).toBe("")
  await exact(root, seeded, "R1"); const fixture = await fixtureInput(); const confirmed = await resume(root, fixture.input); expect(confirmed).toMatchObject({ milestone: "CAS2_EXACT_R2_CONFIRMED", mainRecord: fixture.expectedR1, receiptRecord: fixture.expectedR2 }); await exact(root, fixture, "R2")
}), 30_000)

it.skipIf(process.platform !== "linux")("CAS2 post-link SIGKILL reopens to an exact-R2 no-write confirmation", async () => withRoot(async (root) => {
  await seed(root); const fixture = await makeR1(root); await runChild(["kill-cas2", root], true); const before = await exact(root, fixture, "R2"); const confirmed = await resume(root, fixture.input); expect(confirmed).toMatchObject({ milestone: "CAS2_EXACT_R2_CONFIRMED", receiptRecord: fixture.expectedR2 }); const after = await exact(root, fixture, "R2"); expect(after.journal).toEqual(before.journal); expect(after.history).toEqual(before.history)
}), 30_000)

it.skipIf(process.platform !== "linux")("two fresh resume processes converge on exact R2 without R3", async () => withRoot(async (root, barrier) => {
  await seed(root); const fixture = await makeR1(root); const release = join(barrier, "release"); const leftReady = join(barrier, "left.ready"); const rightReady = join(barrier, "right.ready"); const left = runChild(["race", root, leftReady, release]); const right = runChild(["race", root, rightReady, release]); await Promise.all([waitFor(leftReady), waitFor(rightReady)]); await writeFile(release, "release\n", { flag: "wx", mode: 0o400 }); const results = await Promise.all([left, right]); if (!("frame" in results[0]) || !("frame" in results[1])) throw new Error("non-kill worker did not return a frame"); expect(results.map((x) => (x as { readonly frame: ChildFrame }).frame.milestone)).toEqual(["CAS2_EXACT_R2_CONFIRMED", "CAS2_EXACT_R2_CONFIRMED"]); expect((results[0] as { readonly frame: ChildFrame }).frame.pid).not.toBe((results[1] as { readonly frame: ChildFrame }).frame.pid); await exact(root, fixture, "R2")
}), 30_000)
