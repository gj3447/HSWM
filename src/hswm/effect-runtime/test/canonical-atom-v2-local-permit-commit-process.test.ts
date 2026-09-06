import { createHash } from "node:crypto"
import { mkdtempSync, readFileSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { describe, expect, it } from "vitest"
import { Effect, Either } from "effect"

import { canonicalJsonBytes } from "../src/canonical-atom-v2-json.js"

import {
  HSWM_LOCAL_PERMIT_COMMIT_PROCESS_V1_CONTRACT_VERSION,
  describeLocalPermitCommitProcessFailure,
  executeLocalPermitCommitProcess
} from "../src/canonical-atom-v2-local-permit-commit-process.js"
import { NodePosixFileSystemLive } from "../src/effect-posix-services.js"
import { runProcessMain, type ProcessIo } from "../src/effect-process-main.js"

const sha = (bytes: Uint8Array | string): string => createHash("sha256").update(bytes).digest("hex")
const hex = (digit: string): string => digit.repeat(64)
const PRE = Buffer.from('{"dispositions":[],"owner_uid":"o","schema_version":"s"}', "utf8")
const POST = Buffer.from('{"dispositions":[{"x":1}],"owner_uid":"o","schema_version":"s"}', "utf8")

const request = (root: string, overrides: Record<string, unknown> = {}) => ({
  contractVersion: HSWM_LOCAL_PERMIT_COMMIT_PROCESS_V1_CONTRACT_VERSION,
  operation: "commit",
  rootPath: root,
  trustSnapshotPath: join(root, "trust-snapshot.json"),
  issuer: { keyId: "key:g1-micro-bridge", authorizer: "principal:g1-micro-owner", policyVersion: "policy:g1-micro-v1", revocationEpoch: 0 },
  lifetimeMs: 60_000,
  claims: {
    permitId: "permit:episode-1",
    executionId: "execution:episode-1",
    executionIntentDigest: hex("3"),
    permitDigest: hex("4"),
    proposalDigest: hex("5"),
    transitionInvariantDigest: hex("6"),
    priorHead: { lineageId: "lineage:episode-1", sequence: 0, stateDigest: sha(PRE), recordDigest: hex("2") },
    expectedNextHead: { lineageId: "lineage:episode-1", sequence: 1, stateDigest: sha(POST), recordDigest: hex("8") },
    target: { schemaVersion: "schema:g1-micro-state-v1", lineageId: "lineage:episode-1", atomUid: "atom:disposition" },
    expectedRevision: "revision:0",
    candidateRevision: "revision:1",
    authorizationRef: "authorization:local-permit-policy",
    scope: "scope:g1-micro-episode",
    linearizationIndex: 1
  },
  preStateBase64Url: PRE.toString("base64url"),
  postStateBase64Url: POST.toString("base64url"),
  ...overrides
})

type Reply = Record<string, unknown>
const run = (input: unknown): Promise<Reply> =>
  Effect.runPromise(executeLocalPermitCommitProcess(input as never).pipe(Effect.provide(NodePosixFileSystemLive))) as Promise<Reply>
const refusal = (input: unknown): Promise<string> =>
  Effect.runPromise(
    executeLocalPermitCommitProcess(input as never).pipe(
      Effect.flip,
      Effect.map(describeLocalPermitCommitProcessFailure),
      Effect.provide(NodePosixFileSystemLive)
    )
  )

describe("local Permit commit process bridge", () => {
  it("commits one exact transition with an ephemeral key and recovers it in a fresh process", async () => {
    const root = mkdtempSync(join(tmpdir(), "hswm-permit-bridge-"))
    const result = await run(request(root))
    expect(result["operation"]).toBe("commit")
    const receipt = result["receipt"] as Reply
    expect(receipt["postStateSha256"]).toBe(sha(POST))
    expect((receipt["priorHead"] as Reply)["stateDigest"]).toBe(sha(PRE))
    expect(result["preStateSha256"]).toBe(sha(PRE))
    expect(result["trustSnapshotSha256"]).toBe(sha(readFileSync(join(root, "trust-snapshot.json"))))
    const slot = readFileSync(String(receipt["slotPath"]))
    expect(sha(slot)).toBe(receipt["recordSha256"])

    const recovered = await run({
      contractVersion: HSWM_LOCAL_PERMIT_COMMIT_PROCESS_V1_CONTRACT_VERSION,
      operation: "recover",
      rootPath: root,
      trustSnapshotPath: join(root, "trust-snapshot.json")
    })
    const commits = recovered["commits"] as Array<Reply>
    expect(commits).toHaveLength(1)
    expect(commits[0]!["recordSha256"]).toBe(receipt["recordSha256"])
    expect((recovered["head"] as Reply)["sequence"]).toBe(1)
    rmSync(root, { recursive: true, force: true })
  })

  it("refuses a second commit into the same root and any digest or shape drift as typed failures", async () => {
    const root = mkdtempSync(join(tmpdir(), "hswm-permit-bridge-"))
    await run(request(root))
    expect(await refusal(request(root))).toMatch(/trust snapshot path already exists/)
    const other = mkdtempSync(join(tmpdir(), "hswm-permit-bridge-"))
    expect(await refusal(request(other, { postStateBase64Url: PRE.toString("base64url") }))).toMatch(/post-state bytes do not match/)
    expect(await refusal(request(other, { operation: "delete" }))).toMatch(/operation must be commit or recover/)
    expect(await refusal(request(other, { extra: 1 }))).toMatch(/not a valid commit request/)
    expect(await refusal(request(other, { rootPath: "relative/root" }))).toMatch(/not a valid commit request/)
    rmSync(root, { recursive: true, force: true })
    rmSync(other, { recursive: true, force: true })
  })

  it("runs the whole request through the single process boundary with in-memory io", async () => {
    const root = mkdtempSync(join(tmpdir(), "hswm-permit-bridge-"))
    const stdout: Array<string> = []
    const stderr: Array<string> = []
    const io = (input: string): ProcessIo => ({
      readStdin: () => Effect.succeed(input),
      writeStdout: (text) => Effect.sync(() => { stdout.push(text) }),
      writeStderr: (text) => Effect.sync(() => { stderr.push(text) })
    })
    const canonical = new TextDecoder().decode(Either.getOrThrow(canonicalJsonBytes(request(root) as never)))
    const spec = {
      refusalPrefix: "HSWM_LOCAL_PERMIT_COMMIT_REFUSED",
      program: executeLocalPermitCommitProcess,
      describeFailure: describeLocalPermitCommitProcessFailure
    }
    expect(await runProcessMain(spec, io(canonical))).toBe(0)
    expect(stdout).toHaveLength(1)
    expect(JSON.parse(stdout[0]!)["operation"]).toBe("commit")
    expect(await runProcessMain(spec, io("not json"))).toBe(2)
    expect(stderr[0]).toMatch(/^HSWM_LOCAL_PERMIT_COMMIT_REFUSED: stdin must be canonical JSON/)
    rmSync(root, { recursive: true, force: true })
  })
})
