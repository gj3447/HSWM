import { createHash } from "node:crypto"
import { mkdtempSync, readFileSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { describe, expect, it } from "vitest"

import {
  HSWM_LOCAL_PERMIT_COMMIT_PROCESS_V1_CONTRACT_VERSION,
  executeLocalPermitCommitProcess
} from "../src/canonical-atom-v2-local-permit-commit-process.js"

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

describe("local Permit commit process bridge", () => {
  it("commits one exact transition with an ephemeral key and recovers it in a fresh process", async () => {
    const root = mkdtempSync(join(tmpdir(), "hswm-permit-bridge-"))
    const result = await executeLocalPermitCommitProcess(request(root) as never)
    expect(result["operation"]).toBe("commit")
    const receipt = result["receipt"] as Record<string, unknown>
    expect(receipt["postStateSha256"]).toBe(sha(POST))
    expect((receipt["priorHead"] as Record<string, unknown>)["stateDigest"]).toBe(sha(PRE))
    expect(result["preStateSha256"]).toBe(sha(PRE))
    expect(result["trustSnapshotSha256"]).toBe(sha(readFileSync(join(root, "trust-snapshot.json"))))
    const slot = readFileSync(String(receipt["slotPath"]))
    expect(sha(slot)).toBe(receipt["recordSha256"])

    const recovered = await executeLocalPermitCommitProcess({
      contractVersion: HSWM_LOCAL_PERMIT_COMMIT_PROCESS_V1_CONTRACT_VERSION,
      operation: "recover",
      rootPath: root,
      trustSnapshotPath: join(root, "trust-snapshot.json")
    } as never)
    const commits = recovered["commits"] as Array<Record<string, unknown>>
    expect(commits).toHaveLength(1)
    expect(commits[0]!["recordSha256"]).toBe(receipt["recordSha256"])
    expect((recovered["head"] as Record<string, unknown>)["sequence"]).toBe(1)
    rmSync(root, { recursive: true, force: true })
  })

  it("refuses a second commit into the same root and any digest or shape drift", async () => {
    const root = mkdtempSync(join(tmpdir(), "hswm-permit-bridge-"))
    await executeLocalPermitCommitProcess(request(root) as never)
    await expect(executeLocalPermitCommitProcess(request(root) as never)).rejects.toThrow(/trust snapshot path already exists/)
    const other = mkdtempSync(join(tmpdir(), "hswm-permit-bridge-"))
    await expect(executeLocalPermitCommitProcess(request(other, { postStateBase64Url: PRE.toString("base64url") }) as never))
      .rejects.toThrow(/post-state bytes do not match/)
    await expect(executeLocalPermitCommitProcess(request(other, { operation: "delete" }) as never))
      .rejects.toThrow(/operation must be commit or recover/)
    await expect(executeLocalPermitCommitProcess(request(other, { extra: 1 }) as never))
      .rejects.toThrow(/missing or excess fields/)
    await expect(executeLocalPermitCommitProcess(request(other, { rootPath: "relative/root" }) as never))
      .rejects.toThrow(/must be absolute/)
    rmSync(root, { recursive: true, force: true })
    rmSync(other, { recursive: true, force: true })
  })
})
