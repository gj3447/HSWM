import { spawn, type ChildProcess } from "node:child_process"
import { createHash } from "node:crypto"
import { constants } from "node:fs"
import { access, mkdir, mkdtemp, rm, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"

import { expect, it } from "vitest"
import { Effect, Either } from "effect"

import {
  makeEphemeralLocalPermitIssuer,
  makeLocalPermitVerifierContext,
  type LocalPermitCommitRequest,
  type LocalPermitIssuer
} from "../../src/hswm/effect-runtime/src/canonical-atom-v2-local-permit-commit.js"
import { makeVerifiedAdmissionGatewayV2 } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-verified-admission-gateway.js"

type Checkpoint = "prepared-file-fsync:after" | "slot-link:after"
const clockIso = "2026-10-07T00:00:00.000Z"
const pre = Uint8Array.from(Buffer.from("v2-process-crash:pre"))
const post = Uint8Array.from(Buffer.from("v2-process-crash:post"))
const digest = (bytes: Uint8Array): string => createHash("sha256").update(bytes).digest("hex")
const hex = (digit: string): string => digit.repeat(64)

interface Fixture {
  readonly clockIso: string
  readonly leanCli: string
  readonly trustSnapshotBytesBase64Url: string
  readonly envelopeBytesBase64Url: string
  readonly expectedBindings: LocalPermitCommitRequest["expectedBindings"]
  readonly preStateBytesBase64Url: string
  readonly postStateBytesBase64Url: string
}

const nonce = (issuer: LocalPermitIssuer): string => {
  const result = issuer.mintNonce()
  if (Either.isLeft(result)) throw result.left
  return result.right.nonceDigest
}

const fixture = (leanCli: string): Fixture => {
  const issuer = makeEphemeralLocalPermitIssuer({
    keyId: "key:v2-process-crash",
    authorizer: "principal:v2-process-crash",
    policyVersion: "policy:v2-process-crash",
    revocationEpoch: 0,
    clock: () => new Date(clockIso)
  })
  if (Either.isLeft(issuer)) throw issuer.left
  const issued = issuer.right.issue({
    permitId: "permit:v2-process-crash",
    executionId: "execution:v2-process-crash",
    executionIntentDigest: hex("1"), permitDigest: hex("2"), proposalDigest: hex("3"), transitionInvariantDigest: hex("4"),
    priorHead: { lineageId: "lineage:v2-process-crash", sequence: 0, stateDigest: digest(pre), recordDigest: hex("5") },
    expectedNextHead: { lineageId: "lineage:v2-process-crash", sequence: 1, stateDigest: digest(post), recordDigest: hex("6") },
    target: { schemaVersion: "schema:v2-process-crash", lineageId: "lineage:target", atomUid: "atom:target" },
    expectedRevision: "revision:0", candidateRevision: "revision:1", authorizationRef: "authorization:v2-process-crash", scope: "scope:v2-process-crash", nonceDigest: nonce(issuer.right), linearizationIndex: 1
  }, 60_000)
  if (Either.isLeft(issued)) throw issued.left
  return Object.freeze({
    clockIso,
    leanCli,
    trustSnapshotBytesBase64Url: Buffer.from(issuer.right.trustSnapshotBytes).toString("base64url"),
    envelopeBytesBase64Url: Buffer.from(issued.right.envelopeBytes).toString("base64url"),
    expectedBindings: issued.right.expectedBindings,
    preStateBytesBase64Url: Buffer.from(pre).toString("base64url"),
    postStateBytesBase64Url: Buffer.from(post).toString("base64url")
  })
}

const runKilledWorker = async (root: string, fixturePath: string, checkpoint: Checkpoint) => {
  const packageRoot = resolve(import.meta.dirname, "../../src/hswm/effect-runtime")
  const child: ChildProcess = spawn(join(packageRoot, "node_modules/.bin/vite-node"), [
    resolve(import.meta.dirname, "fixtures/journal-v2-durability-worker.ts"), root, fixturePath, checkpoint
  ], { cwd: packageRoot, stdio: ["ignore", "pipe", "pipe"] })
  return await new Promise<{ readonly code: number | null; readonly signal: NodeJS.Signals | null; readonly stdout: string; readonly stderr: string }>((resolveResult, rejectResult) => {
    let stdout = "", stderr = ""
    const timer = setTimeout(() => {
      child.kill("SIGKILL")
      rejectResult(new Error("V2 process-crash worker timed out"))
    }, 15_000)
    child.stdout?.on("data", (chunk: Buffer) => { stdout += chunk.toString("utf8") })
    child.stderr?.on("data", (chunk: Buffer) => { stderr += chunk.toString("utf8") })
    child.once("error", (error) => { clearTimeout(timer); rejectResult(error) })
    child.once("close", (code, signal) => { clearTimeout(timer); resolveResult({ code, signal, stdout, stderr }) })
  })
}

const waitFor = async (path: string): Promise<void> => {
  const deadline = Date.now() + 10_000
  while (true) {
    try { await access(path, constants.F_OK); return } catch { /* wait */ }
    if (Date.now() >= deadline) throw new Error("V2 race worker did not reach checkpoint")
    await new Promise<void>((resolveDelay) => setTimeout(resolveDelay, 5))
  }
}

const runRaceWorker = (root: string, fixturePath: string, ready: string, release: string): Promise<{ readonly code: number | null; readonly signal: NodeJS.Signals | null; readonly stdout: string; readonly stderr: string }> => {
  const packageRoot = resolve(import.meta.dirname, "../../src/hswm/effect-runtime")
  const child = spawn(join(packageRoot, "node_modules/.bin/vite-node"), [
    resolve(import.meta.dirname, "fixtures/journal-v2-durability-worker.ts"), root, fixturePath, "prepared-file-fsync:after", ready, release
  ], { cwd: packageRoot, stdio: ["ignore", "pipe", "pipe"] })
  return new Promise((resolveResult, rejectResult) => {
    let stdout = "", stderr = ""
    const observe = (stream: "stdout" | "stderr", chunk: Buffer): void => {
      if (stream === "stdout") stdout += chunk.toString("utf8"); else stderr += chunk.toString("utf8")
      if (Buffer.byteLength(stdout) + Buffer.byteLength(stderr) > 16384) {
        child.kill("SIGKILL"); rejectResult(new Error("V2 race output exceeded bound"))
      }
    }
    child.stdout?.on("data", (chunk: Buffer) => observe("stdout", chunk))
    child.stderr?.on("data", (chunk: Buffer) => observe("stderr", chunk))
    const timer = setTimeout(() => { child.kill("SIGKILL"); rejectResult(new Error("V2 race worker timed out")) }, 15_000)
    child.once("error", (error) => { clearTimeout(timer); rejectResult(error) })
    child.once("close", (code, signal) => { clearTimeout(timer); resolveResult({ code, signal, stdout, stderr }) })
  })
}

const recover = async (root: string, input: Fixture) => {
  const verifier = makeLocalPermitVerifierContext(Uint8Array.from(Buffer.from(input.trustSnapshotBytesBase64Url, "base64url")))
  if (Either.isLeft(verifier)) throw verifier.left
  const gateway = makeVerifiedAdmissionGatewayV2(root, verifier.right, { leanExecutable: input.leanCli }, () => new Date(input.clockIso))
  if (Either.isLeft(gateway)) throw gateway.left
  return Effect.runPromise(gateway.right.recover())
}

it.skipIf(process.platform !== "linux")(
  "V2 gateway independent processes reconcile an identical no-replace race after the same fsync boundary",
  async () => {
    const base = await mkdtemp(join(tmpdir(), "hswm-v2-process-race-"))
    try {
      const root = join(base, "store")
      await mkdir(root, { mode: 0o700 })
      const input = fixture(resolve(import.meta.dirname, "../../formal/.lake/build/bin/HSWMAdmissionKernelCli"))
      const fixturePath = join(base, "fixture.json")
      await writeFile(fixturePath, JSON.stringify(input), { mode: 0o600 })
      const release = join(base, "release")
      const first = runRaceWorker(root, fixturePath, join(base, "first.ready"), release)
      const second = runRaceWorker(root, fixturePath, join(base, "second.ready"), release)
      await Promise.all([waitFor(join(base, "first.ready")), waitFor(join(base, "second.ready"))])
      await writeFile(release, "release\n", { flag: "wx", mode: 0o400 })
      const outcomes = await Promise.all([first, second])
      expect(outcomes.map((outcome) => outcome.code).sort()).toEqual([0, 1])
      expect(outcomes.every((outcome) => outcome.signal === null)).toBe(true)
      const winner = outcomes.find(outcome => outcome.code === 0)!, loser = outcomes.find(outcome => outcome.code === 1)!
      expect(winner.stderr).toBe("")
      expect(JSON.parse(winner.stdout)).toMatchObject({ status: "PUBLISHED" })
      expect(loser.stdout).toBe("")
      expect(JSON.parse(loser.stderr)).toEqual({ code: "SLOT_ALREADY_COMMITTED" })
      const recovered = await recover(root, input)
      expect(recovered.commits[0]?.commit.recordSha256).toBe(JSON.parse(winner.stdout).recordSha256)
      expect(recovered.commits).toHaveLength(1)
      expect(recovered.commits[0]?.commit.postStateBytes).toEqual(post)
    } finally {
      await rm(base, { recursive: true, force: true })
    }
  },
  30_000
)

for (const [checkpoint, expectedCount] of [
  ["prepared-file-fsync:after", 0],
  ["slot-link:after", 1]
] as const) {
  it.skipIf(process.platform !== "linux")(
    `V2 gateway SIGKILL at ${checkpoint} has the expected restart prefix (process crash, not power loss)`,
    async () => {
      const base = await mkdtemp(join(tmpdir(), "hswm-v2-process-crash-"))
      try {
        const leanCli = resolve(import.meta.dirname, "../../formal/.lake/build/bin/HSWMAdmissionKernelCli")
        const input = fixture(leanCli)
        const fixturePath = join(base, "fixture.json")
        const root = join(base, "store")
        await mkdir(root, { mode: 0o700 })
        await writeFile(fixturePath, JSON.stringify(input), { mode: 0o600 })
        const result = await runKilledWorker(root, fixturePath, checkpoint)
        expect(result).toMatchObject({ code: null, signal: "SIGKILL", stdout: "", stderr: "" })
        const restarted = await recover(root, input)
        expect(restarted.commits).toHaveLength(expectedCount)
        expect(restarted.head?.sequence ?? null).toBe(expectedCount === 0 ? null : 1)
        if (expectedCount === 1) expect(restarted.commits[0]?.commit.postStateBytes).toEqual(post)
        const verifier = makeLocalPermitVerifierContext(Uint8Array.from(Buffer.from(input.trustSnapshotBytesBase64Url, "base64url")))
        if (Either.isLeft(verifier)) throw verifier.left
        const gateway = makeVerifiedAdmissionGatewayV2(root, verifier.right, { leanExecutable: leanCli }, () => new Date(input.clockIso))
        if (Either.isLeft(gateway)) throw gateway.left
        const retry = await Effect.runPromise(Effect.either(gateway.right.submit({
          envelopeBytes: Uint8Array.from(Buffer.from(input.envelopeBytesBase64Url, "base64url")),
          expectedBindings: input.expectedBindings, preStateBytes: pre, postStateBytes: post
        })))
        if (expectedCount === 0) expect(Either.isRight(retry)).toBe(true)
        else {
          expect(Either.isLeft(retry)).toBe(true)
          if (Either.isLeft(retry)) expect(retry.left.code).toBe("NONCE_ALREADY_CONSUMED")
        }
        expect((await recover(root, input)).commits).toHaveLength(1)
      } finally {
        await rm(base, { recursive: true, force: true })
      }
    },
    30_000
  )
}
