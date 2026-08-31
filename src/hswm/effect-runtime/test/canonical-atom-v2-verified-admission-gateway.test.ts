import { createHash } from "node:crypto"
import { chmodSync, existsSync, mkdirSync, mkdtempSync, rmSync, symlinkSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { expect, it } from "@effect/vitest"
import { Effect, Exit } from "effect"

import {
  makeEphemeralLocalPermitIssuer,
  makeLocalPermitCommitStore,
  makeVerifiedAdmissionGateway,
  type LocalPermitIssuer
} from "../src/index.js"

const hex = (digit: string): string => digit.repeat(64)
const frozenClock = (): Date => new Date("2026-08-31T10:00:00.000Z")
const initial = Uint8Array.from(Buffer.from("verified-admission:zero"))
const next = Uint8Array.from(Buffer.from("verified-admission:one"))
const digest = (value: Uint8Array): string => createHash("sha256").update(value).digest("hex")
const head = (sequence: number, state: Uint8Array, record: string, lineageId = "lineage:verified-admission") => ({ lineageId, sequence, stateDigest: digest(state), recordDigest: hex(record) })
const minted = (issuer: LocalPermitIssuer): string => {
  const result = issuer.mintNonce()
  if (result._tag === "Left") throw result.left
  return result.right.nonceDigest
}

const issueFor = (issuer: LocalPermitIssuer, prior: ReturnType<typeof head>, post: Uint8Array, suffix: string) =>
  issuer.issue({
    permitId: `permit:verified-${suffix}`, executionId: `execution:verified-${suffix}`, executionIntentDigest: hex("3"), permitDigest: hex("4"), proposalDigest: hex("5"), transitionInvariantDigest: hex("6"),
    priorHead: prior, expectedNextHead: head(prior.sequence + 1, post, suffix, prior.lineageId), target: { schemaVersion: "schema:verified", lineageId: "lineage:target", atomUid: "atom:target" }, expectedRevision: `revision:${prior.sequence}`, candidateRevision: `revision:${prior.sequence + 1}`, authorizationRef: "authorization:verified", scope: "scope:verified", nonceDigest: minted(issuer), linearizationIndex: prior.sequence + 1
  }, 60_000)

it.effect("requires the built Lean CLI's exact accepted request reflection before publishing in its protected namespace", () =>
  Effect.gen(function* () {
    const cli = join(process.cwd(), "../../../formal/.lake/build/bin/HSWMAdmissionKernelCli")
    if (!existsSync(cli)) return
    const root = mkdtempSync(join(tmpdir(), "hswm-verified-admission-"))
    const issuer = makeEphemeralLocalPermitIssuer({ keyId: "key:verified", authorizer: "principal:verified", policyVersion: "policy:verified", revocationEpoch: 0, clock: frozenClock })
    if (issuer._tag === "Left") throw issuer.left
    const prior = head(0, initial, "2")
    const issued = issueFor(issuer.right, prior, next, "8")
    if (issued._tag === "Left") throw issued.left
    const gateway = makeVerifiedAdmissionGateway(root, issuer.right, { leanExecutable: cli }, frozenClock)
    expect(gateway._tag).toBe("Right")
    if (gateway._tag === "Left") return
    const receipt = yield* gateway.right.submit({ ...issued.right, preStateBytes: initial, postStateBytes: next })
    expect(receipt.commit.expectedNextHead.sequence).toBe(1)
    expect(receipt.requestSha256).toHaveLength(64)
    expect(receipt.decisionSha256).toHaveLength(64)
    const third = Uint8Array.from(Buffer.from("verified-admission:two"))
    const chained = issueFor(issuer.right, receipt.commit.expectedNextHead, third, "9")
    if (chained._tag === "Left") throw chained.left
    const chainedReceipt = yield* gateway.right.submit({ ...chained.right, preStateBytes: next, postStateBytes: third })
    expect(chainedReceipt.commit.expectedNextHead.sequence).toBe(2)
    const recovered = yield* gateway.right.recover()
    expect(recovered.commits).toHaveLength(2)
    // The public compatibility store names a different namespace and cannot
    // recover protected-gateway records.
    const legacy = yield* makeLocalPermitCommitStore(root, issuer.right, frozenClock).recover()
    expect(legacy.commits).toHaveLength(0)
    const replay = yield* Effect.exit(gateway.right.submit({ ...issued.right, preStateBytes: initial, postStateBytes: next }))
    expect(Exit.isFailure(replay)).toBe(true)
    rmSync(root, { recursive: true, force: true })
  })
)

it.effect("rejects a caller-configured executable's canonical-but-mutated successor before any protected publication", () =>
  Effect.gen(function* () {
    const root = mkdtempSync(join(tmpdir(), "hswm-verified-admission-adversarial-"))
    const executable = join(root, "mutated-admission-response.mjs")
    // It mirrors the exact request but lies about its successor.  `shell` is
    // never involved; this is an ordinary absolute executable boundary.
    writeFileSync(executable, "#!/usr/bin/env node\nlet s='';process.stdin.on('data',c=>s+=c).on('end',()=>process.stdout.write('{\\\"contractVersion\\\":\\\"hswm-verified-admission-wire/v1\\\",\\\"decision\\\":\\\"accepted\\\",\\\"request\\\":'+s+',\\\"successor\\\":{\\\"consumedNonces\\\":[],\\\"head\\\":null}}'))\n", { mode: 0o700 })
    chmodSync(executable, 0o700)
    const issuer = makeEphemeralLocalPermitIssuer({ keyId: "key:adversarial", authorizer: "principal:adversarial", policyVersion: "policy:adversarial", revocationEpoch: 0, clock: frozenClock })
    if (issuer._tag === "Left") throw issuer.left
    const issued = issueFor(issuer.right, head(0, initial, "e"), next, "f")
    if (issued._tag === "Left") throw issued.left
    const gateway = makeVerifiedAdmissionGateway(root, issuer.right, { leanExecutable: executable }, frozenClock)
    if (gateway._tag === "Left") throw gateway.left
    const result = yield* Effect.exit(gateway.right.submit({ ...issued.right, preStateBytes: initial, postStateBytes: next }))
    expect(Exit.isFailure(result)).toBe(true)
    const recovered = yield* gateway.right.recover()
    expect(recovered.commits).toHaveLength(0)
    rmSync(root, { recursive: true, force: true })
  })
)

it.effect("serializes concurrent protected genesis attempts from gateway instances sharing one normalized root", () =>
  Effect.gen(function* () {
    const cli = join(process.cwd(), "../../../formal/.lake/build/bin/HSWMAdmissionKernelCli")
    if (!existsSync(cli)) return
    const root = mkdtempSync(join(tmpdir(), "hswm-verified-admission-race-"))
    const issuer = makeEphemeralLocalPermitIssuer({ keyId: "key:race", authorizer: "principal:race", policyVersion: "policy:race", revocationEpoch: 0, clock: frozenClock })
    if (issuer._tag === "Left") throw issuer.left
    const left = issueFor(issuer.right, head(0, initial, "a", "lineage:race-left"), next, "b")
    const right = issueFor(issuer.right, head(0, initial, "c", "lineage:race-right"), next, "d")
    if (left._tag === "Left" || right._tag === "Left") throw new Error("issue failed")
    const first = makeVerifiedAdmissionGateway(root, issuer.right, { leanExecutable: cli }, frozenClock)
    const second = makeVerifiedAdmissionGateway(root, issuer.right, { leanExecutable: cli }, frozenClock)
    if (first._tag === "Left" || second._tag === "Left") throw new Error("gateway failed")
    const outcomes = yield* Effect.all([
      Effect.exit(first.right.submit({ ...left.right, preStateBytes: initial, postStateBytes: next })),
      Effect.exit(second.right.submit({ ...right.right, preStateBytes: initial, postStateBytes: next }))
    ], { concurrency: "unbounded" })
    expect(outcomes.filter(Exit.isSuccess)).toHaveLength(1)
    const recovered = yield* first.right.recover()
    expect(recovered.commits).toHaveLength(1)
    rmSync(root, { recursive: true, force: true })
  })
)

it.effect("serializes aliases of one physical protected root by realpath identity", () =>
  Effect.gen(function* () {
    const cli = join(process.cwd(), "../../../formal/.lake/build/bin/HSWMAdmissionKernelCli")
    if (!existsSync(cli)) return
    const container = mkdtempSync(join(tmpdir(), "hswm-verified-admission-alias-race-"))
    const physicalRoot = join(container, "physical")
    const firstAlias = join(container, "first-alias")
    const secondAlias = join(container, "second-alias")
    mkdirSync(physicalRoot)
    symlinkSync(physicalRoot, firstAlias, "dir")
    symlinkSync(physicalRoot, secondAlias, "dir")
    const issuer = makeEphemeralLocalPermitIssuer({ keyId: "key:alias-race", authorizer: "principal:alias-race", policyVersion: "policy:alias-race", revocationEpoch: 0, clock: frozenClock })
    if (issuer._tag === "Left") throw issuer.left
    const left = issueFor(issuer.right, head(0, initial, "1", "lineage:alias-left"), next, "2")
    const right = issueFor(issuer.right, head(0, initial, "3", "lineage:alias-right"), next, "4")
    if (left._tag === "Left" || right._tag === "Left") throw new Error("issue failed")
    const first = makeVerifiedAdmissionGateway(firstAlias, issuer.right, { leanExecutable: cli }, frozenClock)
    const second = makeVerifiedAdmissionGateway(secondAlias, issuer.right, { leanExecutable: cli }, frozenClock)
    if (first._tag === "Left" || second._tag === "Left") throw new Error("gateway failed")
    const outcomes = yield* Effect.all([
      Effect.exit(first.right.submit({ ...left.right, preStateBytes: initial, postStateBytes: next })),
      Effect.exit(second.right.submit({ ...right.right, preStateBytes: initial, postStateBytes: next }))
    ], { concurrency: "unbounded" })
    expect(outcomes.filter(Exit.isSuccess)).toHaveLength(1)
    const recovered = yield* first.right.recover()
    expect(recovered.commits).toHaveLength(1)
    rmSync(container, { recursive: true, force: true })
  })
)
