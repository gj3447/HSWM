import { createHash } from "node:crypto"
import { chmodSync, existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { expect, it } from "@effect/vitest"
import { Effect, Exit } from "effect"

import { canonicalJsonBytes } from "../src/canonical-atom-v2-json.js"
import {
  makeEphemeralLocalPermitIssuer,
  makeLocalPermitCommitStore,
  makeVerifiedAdmissionGateway,
  makeVerifiedAdmissionGatewayV2,
  type LocalPermitIssuer
} from "../src/index.js"

const hex = (digit: string): string => digit.repeat(64)
const frozenClock = (): Date => new Date("2026-08-31T10:00:00.000Z")
const initial = Uint8Array.from(Buffer.from("verified-admission-v2:zero"))
const next = Uint8Array.from(Buffer.from("verified-admission-v2:one"))
const third = Uint8Array.from(Buffer.from("verified-admission-v2:two"))
const digest = (value: Uint8Array): string => createHash("sha256").update(value).digest("hex")
const head = (sequence: number, state: Uint8Array, record: string) => ({
  lineageId: "lineage:verified-admission-v2", sequence, stateDigest: digest(state), recordDigest: hex(record)
})

const minted = (issuer: LocalPermitIssuer): string => {
  const result = issuer.mintNonce()
  if (result._tag === "Left") throw result.left
  return result.right.nonceDigest
}

const issueFor = (issuer: LocalPermitIssuer, prior: ReturnType<typeof head>, post: Uint8Array, suffix: string) =>
  issuer.issue({
    permitId: `permit:verified-v2-${suffix}`, executionId: `execution:verified-v2-${suffix}`,
    executionIntentDigest: hex("3"), permitDigest: hex("4"), proposalDigest: hex("5"), transitionInvariantDigest: hex("6"),
    priorHead: prior, expectedNextHead: head(prior.sequence + 1, post, suffix),
    target: { schemaVersion: "schema:verified-v2", lineageId: "lineage:target", atomUid: "atom:target" },
    expectedRevision: `revision:${prior.sequence}`, candidateRevision: `revision:${prior.sequence + 1}`,
    authorizationRef: "authorization:verified-v2", scope: "scope:verified-v2", nonceDigest: minted(issuer), linearizationIndex: prior.sequence + 1
  }, 60_000)

const cliPath = (): string => join(process.cwd(), "../../../formal/.lake/build/bin/HSWMAdmissionKernelCli")

it.effect("persists the exact accepted Lean exchange with its protected commit and revalidates it after restart", () =>
  Effect.gen(function* () {
    const cli = cliPath()
    if (!existsSync(cli)) return
    const root = mkdtempSync(join(tmpdir(), "hswm-verified-admission-v2-restart-"))
    try {
      const issuer = makeEphemeralLocalPermitIssuer({ keyId: "key:verified-v2", authorizer: "principal:verified-v2", policyVersion: "policy:verified-v2", revocationEpoch: 0, clock: frozenClock })
      if (issuer._tag === "Left") throw issuer.left
      const issued = issueFor(issuer.right, head(0, initial, "2"), next, "8")
      if (issued._tag === "Left") throw issued.left
      const first = makeVerifiedAdmissionGatewayV2(root, issuer.right, { leanExecutable: cli }, frozenClock)
      if (first._tag === "Left") throw first.left
      const published = yield* first.right.submit({ ...issued.right, preStateBytes: initial, postStateBytes: next })
      expect(published.commit.expectedNextHead.sequence).toBe(1)
      expect(published.decision.requestSha256).toHaveLength(64)
      expect(published.decision.decisionSha256).toHaveLength(64)
      const secondPermit = issueFor(issuer.right, published.commit.expectedNextHead, third, "9")
      if (secondPermit._tag === "Left") throw secondPermit.left
      const second = yield* first.right.submit({ ...secondPermit.right, preStateBytes: next, postStateBytes: third })
      expect(second.commit.expectedNextHead.sequence).toBe(2)

      const restarted = makeVerifiedAdmissionGatewayV2(root, issuer.right, { leanExecutable: cli }, frozenClock)
      if (restarted._tag === "Left") throw restarted.left
      const recovered = yield* restarted.right.recover()
      expect(recovered.commits).toHaveLength(2)
      for (const [restored, expected] of [[recovered.commits[0]!, published], [recovered.commits[1]!, second]] as const) {
        expect(restored.commit.recordSha256).toBe(expected.commit.recordSha256)
        expect(restored.commit.priorHead).toEqual(expected.commit.priorHead)
        expect(restored.commit.expectedNextHead).toEqual(expected.commit.expectedNextHead)
        expect(restored.commit.nonceDigest).toBe(expected.commit.nonceDigest)
        expect(restored.decision.requestSha256).toBe(expected.decision.requestSha256)
        expect(restored.decision.decisionSha256).toBe(expected.decision.decisionSha256)
        expect(restored.decision.canonicalRequestBytes).toEqual(expected.decision.canonicalRequestBytes)
        expect(restored.decision.canonicalResponseBytes).toEqual(expected.decision.canonicalResponseBytes)
      }
      expect(recovered.commits[1]!.commit.priorHead).toEqual(published.commit.expectedNextHead)
      expect(recovered.head).toEqual(second.commit.expectedNextHead)

      // V2 is deliberately a new protected namespace; neither compatibility
      // path may silently treat the v2 record as its own committed history.
      expect((yield* makeLocalPermitCommitStore(root, issuer.right, frozenClock).recover()).commits).toHaveLength(0)
      const v1 = makeVerifiedAdmissionGateway(root, issuer.right, { leanExecutable: cli }, frozenClock)
      if (v1._tag === "Left") throw v1.left
      expect((yield* v1.right.recover()).commits).toHaveLength(0)
    } finally {
      rmSync(root, { recursive: true, force: true })
    }
  })
)

it.effect("fails closed on any canonical persisted verified-admission field rewrite", () =>
  Effect.gen(function* () {
    const cli = cliPath()
    if (!existsSync(cli)) return
    const fields = [
      "canonicalRequestBytesBase64Url",
      "canonicalResponseBytesBase64Url",
      "requestSha256",
      "decisionSha256"
    ] as const
    for (const field of fields) {
      const root = mkdtempSync(join(tmpdir(), `hswm-verified-admission-v2-tamper-${field}-`))
      try {
        const issuer = makeEphemeralLocalPermitIssuer({ keyId: `key:v2-tamper-${field}`, authorizer: "principal:verified-v2", policyVersion: "policy:verified-v2", revocationEpoch: 0, clock: frozenClock })
        if (issuer._tag === "Left") throw issuer.left
        const issued = issueFor(issuer.right, head(0, initial, "2"), next, "8")
        if (issued._tag === "Left") throw issued.left
        const gateway = makeVerifiedAdmissionGatewayV2(root, issuer.right, { leanExecutable: cli }, frozenClock)
        if (gateway._tag === "Left") throw gateway.left
        const published = yield* gateway.right.submit({ ...issued.right, preStateBytes: initial, postStateBytes: next })
        const record = JSON.parse(readFileSync(published.commit.slotPath, "utf8")) as { verifiedAdmission: Record<string, string> }
        const old = record.verifiedAdmission[field]
        if (old === undefined) throw new Error(`published v2 record omitted ${field}`)
        record.verifiedAdmission[field] = field.endsWith("Sha256")
          ? (old[0] === "0" ? `1${old.slice(1)}` : `0${old.slice(1)}`)
          : `${old.slice(0, -1)}${old.endsWith("A") ? "B" : "A"}`
        const canonical = canonicalJsonBytes(record)
        if (canonical._tag === "Left") throw canonical.left
        chmodSync(published.commit.slotPath, 0o600)
        writeFileSync(published.commit.slotPath, canonical.right)
        chmodSync(published.commit.slotPath, 0o400)
        const restarted = makeVerifiedAdmissionGatewayV2(root, issuer.right, { leanExecutable: cli }, frozenClock)
        if (restarted._tag === "Left") throw restarted.left
        const recovered = yield* Effect.exit(restarted.right.recover())
        expect(Exit.isFailure(recovered)).toBe(true)
        if (Exit.isFailure(recovered) && recovered.cause._tag === "Fail") {
          expect(recovered.cause.error.code).toBe("RECOVERY_INVALID")
        }
      } finally {
        rmSync(root, { recursive: true, force: true })
      }
    }

    // This is intentionally stronger than a stale-hash check: give recovery a
    // newly canonical response and its matching digest, but make the accepted
    // successor disagree with the reconstructed journal successor.
    const root = mkdtempSync(join(tmpdir(), "hswm-verified-admission-v2-semantic-tamper-"))
    try {
      const issuer = makeEphemeralLocalPermitIssuer({ keyId: "key:v2-semantic-tamper", authorizer: "principal:verified-v2", policyVersion: "policy:verified-v2", revocationEpoch: 0, clock: frozenClock })
      if (issuer._tag === "Left") throw issuer.left
      const issued = issueFor(issuer.right, head(0, initial, "2"), next, "8")
      if (issued._tag === "Left") throw issued.left
      const gateway = makeVerifiedAdmissionGatewayV2(root, issuer.right, { leanExecutable: cli }, frozenClock)
      if (gateway._tag === "Left") throw gateway.left
      const published = yield* gateway.right.submit({ ...issued.right, preStateBytes: initial, postStateBytes: next })
      const record = JSON.parse(readFileSync(published.commit.slotPath, "utf8")) as { verifiedAdmission: Record<string, string> }
      const response = JSON.parse(Buffer.from(record.verifiedAdmission["canonicalResponseBytesBase64Url"]!, "base64url").toString("utf8")) as {
        successor: { head: { sequence: number } | null }
      }
      if (response.successor.head === null) throw new Error("accepted response unexpectedly has no successor head")
      response.successor.head.sequence += 1
      const responseBytes = canonicalJsonBytes(response)
      if (responseBytes._tag === "Left") throw responseBytes.left
      record.verifiedAdmission["canonicalResponseBytesBase64Url"] = Buffer.from(responseBytes.right).toString("base64url")
      record.verifiedAdmission["decisionSha256"] = digest(responseBytes.right)
      const rewritten = canonicalJsonBytes(record)
      if (rewritten._tag === "Left") throw rewritten.left
      chmodSync(published.commit.slotPath, 0o600)
      writeFileSync(published.commit.slotPath, rewritten.right)
      chmodSync(published.commit.slotPath, 0o400)
      const restarted = makeVerifiedAdmissionGatewayV2(root, issuer.right, { leanExecutable: cli }, frozenClock)
      if (restarted._tag === "Left") throw restarted.left
      const recovered = yield* Effect.exit(restarted.right.recover())
      expect(Exit.isFailure(recovered)).toBe(true)
      if (Exit.isFailure(recovered) && recovered.cause._tag === "Fail") {
        expect(recovered.cause.error.code).toBe("RECOVERY_INVALID")
      }
    } finally {
      rmSync(root, { recursive: true, force: true })
    }
  })
)

it.effect("rejects a canonical-but-mutated Lean successor before v2 publication", () =>
  Effect.gen(function* () {
    const root = mkdtempSync(join(tmpdir(), "hswm-verified-admission-v2-adversarial-"))
    try {
      const executable = join(root, "mutated-admission-response.mjs")
      writeFileSync(executable, "#!/usr/bin/env node\nlet s='';process.stdin.on('data',c=>s+=c).on('end',()=>process.stdout.write('{\\\"contractVersion\\\":\\\"hswm-verified-admission-wire/v1\\\",\\\"decision\\\":\\\"accepted\\\",\\\"request\\\":'+s+',\\\"successor\\\":{\\\"consumedNonces\\\":[],\\\"head\\\":null}}'))\n", { mode: 0o700 })
      chmodSync(executable, 0o700)
      const issuer = makeEphemeralLocalPermitIssuer({ keyId: "key:verified-v2-adversarial", authorizer: "principal:verified-v2", policyVersion: "policy:verified-v2", revocationEpoch: 0, clock: frozenClock })
      if (issuer._tag === "Left") throw issuer.left
      const issued = issueFor(issuer.right, head(0, initial, "e"), next, "f")
      if (issued._tag === "Left") throw issued.left
      const gateway = makeVerifiedAdmissionGatewayV2(root, issuer.right, { leanExecutable: executable }, frozenClock)
      if (gateway._tag === "Left") throw gateway.left
      expect(Exit.isFailure(yield* Effect.exit(gateway.right.submit({ ...issued.right, preStateBytes: initial, postStateBytes: next })))).toBe(true)
      expect((yield* gateway.right.recover()).commits).toHaveLength(0)
      expect((yield* makeLocalPermitCommitStore(root, issuer.right, frozenClock).recover()).commits).toHaveLength(0)
    } finally {
      rmSync(root, { recursive: true, force: true })
    }
  })
)
