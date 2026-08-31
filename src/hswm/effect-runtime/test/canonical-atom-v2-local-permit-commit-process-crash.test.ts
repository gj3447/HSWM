import { spawn, type ChildProcess } from "node:child_process"
import { createHash } from "node:crypto"
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"

import { expect, it } from "vitest"
import { Either, Effect } from "effect"

import {
  makeEphemeralLocalPermitIssuer,
  makeLocalPermitCommitStore,
  makeLocalPermitVerifierContext,
  type LocalPermitCommitRequest,
  type LocalPermitIssuer
} from "../src/canonical-atom-v2-local-permit-commit.js"

type Checkpoint = "prepared-file-fsync:after" | "slot-link:after"

const OUTPUT_LIMIT = 16_384
const FIXED_CLOCK = "2026-08-31T10:00:00.000Z"
const preStateBytes = Uint8Array.from(Buffer.from("local-process-crash:zero", "utf8"))
const postStateBytes = Uint8Array.from(Buffer.from("local-process-crash:one", "utf8"))
const sha256 = (bytes: Uint8Array): string => createHash("sha256").update(bytes).digest("hex")
const hex = (digit: string): string => digit.repeat(64)

interface PersistedProcessFixture {
  readonly clockIso: string
  readonly trustSnapshotBytesBase64Url: string
  readonly envelopeBytesBase64Url: string
  readonly expectedBindings: LocalPermitCommitRequest["expectedBindings"]
  readonly preStateBytesBase64Url: string
  readonly postStateBytesBase64Url: string
}

const mintedNonce = (issuer: LocalPermitIssuer): string => {
  const nonce = issuer.mintNonce()
  if (Either.isLeft(nonce)) throw nonce.left
  return nonce.right.nonceDigest
}

const claims = (nonceDigest: string) => Object.freeze({
  permitId: "permit:local-process-crash",
  executionId: "execution:local-process-crash",
  executionIntentDigest: hex("1"),
  permitDigest: hex("2"),
  proposalDigest: hex("3"),
  transitionInvariantDigest: hex("4"),
  priorHead: Object.freeze({
    lineageId: "lineage:local-process-crash",
    sequence: 0,
    stateDigest: sha256(preStateBytes),
    recordDigest: hex("5")
  }),
  expectedNextHead: Object.freeze({
    lineageId: "lineage:local-process-crash",
    sequence: 1,
    stateDigest: sha256(postStateBytes),
    recordDigest: hex("6")
  }),
  target: Object.freeze({
    schemaVersion: "schema:local-process-crash-v1",
    lineageId: "lineage:target",
    atomUid: "atom:target"
  }),
  expectedRevision: "revision:0",
  candidateRevision: "revision:1",
  authorizationRef: "authorization:local-process-crash",
  scope: "scope:local-process-crash",
  nonceDigest,
  linearizationIndex: 1
})

const makePersistedFixture = (): PersistedProcessFixture => {
  const issuer = makeEphemeralLocalPermitIssuer({
    keyId: "key:local-process-crash",
    authorizer: "principal:local-process-crash",
    policyVersion: "policy:local-process-crash-v1",
    revocationEpoch: 0,
    clock: () => new Date(FIXED_CLOCK)
  })
  if (Either.isLeft(issuer)) throw issuer.left
  const issued = issuer.right.issue(claims(mintedNonce(issuer.right)), 60_000)
  if (Either.isLeft(issued)) throw issued.left
  return Object.freeze({
    clockIso: FIXED_CLOCK,
    trustSnapshotBytesBase64Url: Buffer.from(issuer.right.trustSnapshotBytes).toString("base64url"),
    envelopeBytesBase64Url: Buffer.from(issued.right.envelopeBytes).toString("base64url"),
    expectedBindings: issued.right.expectedBindings,
    preStateBytesBase64Url: Buffer.from(preStateBytes).toString("base64url"),
    postStateBytesBase64Url: Buffer.from(postStateBytes).toString("base64url")
  })
}

const runCrashWorker = async (
  rootPath: string,
  fixturePath: string,
  checkpoint: Checkpoint
): Promise<{ readonly code: number | null; readonly signal: NodeJS.Signals | null; readonly stdout: string; readonly stderr: string }> => {
  const packageRoot = resolve(import.meta.dirname, "..")
  const worker = join(packageRoot, "test", "fixtures", "canonical-atom-v2-local-permit-commit-process-worker.ts")
  const viteNode = join(packageRoot, "node_modules", ".bin", "vite-node")
  return await new Promise((resolveResult, rejectResult) => {
    const child: ChildProcess = spawn(viteNode, [worker, rootPath, fixturePath, checkpoint], {
      cwd: packageRoot,
      stdio: ["ignore", "pipe", "pipe"]
    })
    let stdout = ""
    let stderr = ""
    let done = false
    const finish = (result: { readonly code: number | null; readonly signal: NodeJS.Signals | null; readonly stdout: string; readonly stderr: string }): void => {
      if (done) return
      done = true
      clearTimeout(timeout)
      resolveResult(result)
    }
    const fail = (cause: Error): void => {
      if (done) return
      done = true
      clearTimeout(timeout)
      if (child.exitCode === null && child.signalCode === null) child.kill("SIGKILL")
      rejectResult(cause)
    }
    const timeout = setTimeout(() => fail(new Error("local Permit process-crash worker timed out")), 15_000)
    child.stdout?.on("data", (chunk: Buffer) => {
      stdout += chunk.toString("utf8")
      if (Buffer.byteLength(stdout, "utf8") > OUTPUT_LIMIT) fail(new Error("local Permit process-crash worker stdout exceeded bound"))
    })
    child.stderr?.on("data", (chunk: Buffer) => {
      stderr += chunk.toString("utf8")
      if (Buffer.byteLength(stderr, "utf8") > OUTPUT_LIMIT) fail(new Error("local Permit process-crash worker stderr exceeded bound"))
    })
    child.once("error", fail)
    child.once("close", (code, signal) => finish({ code, signal, stdout, stderr }))
  })
}

const recoverFromPersistedPublicFixture = async (rootPath: string, fixturePath: string) => {
  const fixture = JSON.parse(await readFile(fixturePath, "utf8")) as PersistedProcessFixture
  const verifier = makeLocalPermitVerifierContext(
    Uint8Array.from(Buffer.from(fixture.trustSnapshotBytesBase64Url, "base64url"))
  )
  if (Either.isLeft(verifier)) throw verifier.left
  return Effect.runPromise(
    makeLocalPermitCommitStore(rootPath, verifier.right, () => new Date(fixture.clockIso)).recover()
  )
}

const assertKilled = (result: { readonly code: number | null; readonly signal: NodeJS.Signals | null; readonly stdout: string; readonly stderr: string }): void => {
  expect(result.code).toBeNull()
  expect(result.signal).toBe("SIGKILL")
  expect(result.stdout).toBe("")
  expect(result.stderr).toBe("")
}

const runProcessCrashCase = async (checkpoint: Checkpoint, expectedCommitCount: number): Promise<void> => {
  const base = await mkdtemp(join(tmpdir(), "hswm-local-permit-process-crash-"))
  const rootPath = join(base, "store")
  const fixturePath = join(base, "public-verifier-and-request.json")
  try {
    await writeFile(fixturePath, JSON.stringify(makePersistedFixture()), { mode: 0o600 })
    assertKilled(await runCrashWorker(rootPath, fixturePath, checkpoint))
    const recovered = await recoverFromPersistedPublicFixture(rootPath, fixturePath)
    expect(recovered.commits).toHaveLength(expectedCommitCount)
    expect(recovered.head?.sequence ?? null).toBe(expectedCommitCount === 0 ? null : 1)
    if (expectedCommitCount === 1) {
      expect(recovered.commits[0]?.postStateBytes).toEqual(postStateBytes)
    }
  } finally {
    await rm(base, { recursive: true, force: true })
  }
}

it.skipIf(process.platform !== "linux")(
  "SIGKILL after prepared-file fsync recovers zero local Permit commits (process crash, not power loss)",
  () => runProcessCrashCase("prepared-file-fsync:after", 0),
  30_000
)

it.skipIf(process.platform !== "linux")(
  "SIGKILL after slot link recovers exactly one valid local Permit commit (process crash, not power loss)",
  () => runProcessCrashCase("slot-link:after", 1),
  30_000
)
