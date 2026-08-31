import { createHash } from "node:crypto"
import { chmodSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { expect, it } from "@effect/vitest"
import { Effect, Exit } from "effect"

import {
  HSWM_LOCAL_PERMIT_COMMIT_STATUS,
  makeEphemeralLocalPermitIssuer,
  makeLocalPermitCommitStore,
  makeLocalPermitVerifierContext,
  type LocalPermitCommitRequest,
  type LocalPermitIssuer
} from "../src/canonical-atom-v2-local-permit-commit.js"

const hex = (digit: string): string => digit.repeat(64)
const frozenClock = (): Date => new Date("2026-08-31T10:00:00.000Z")
const stateDigest = (bytes: Uint8Array): string => createHash("sha256").update(bytes).digest("hex")
const INITIAL_STATE = Uint8Array.from(Buffer.from("local-state:zero", "utf8"))
const NEXT_STATE = Uint8Array.from(Buffer.from("local-state:one", "utf8"))

const head = (sequence: number, state: Uint8Array, record: string) => Object.freeze({
  lineageId: "lineage:local-permit-test",
  sequence,
  stateDigest: stateDigest(state),
  recordDigest: hex(record)
})

const mintedNonce = (issuer: LocalPermitIssuer): string => {
  const minted = issuer.mintNonce()
  if (minted._tag === "Left") throw minted.left
  return minted.right.nonceDigest
}

const makeClaims = (nonceDigest: string, prior = head(0, INITIAL_STATE, "2"), postState = NEXT_STATE) => Object.freeze({
  permitId: `permit:local-${nonceDigest.slice(0, 8)}`,
  executionId: `execution:local-${nonceDigest.slice(0, 8)}`,
  executionIntentDigest: hex("3"),
  permitDigest: hex("4"),
  proposalDigest: hex("5"),
  transitionInvariantDigest: hex("6"),
  priorHead: prior,
  expectedNextHead: head(prior.sequence + 1, postState, "8"),
  target: Object.freeze({ schemaVersion: "schema:local-v1", lineageId: "lineage:target", atomUid: "atom:target" }),
  expectedRevision: `revision:${prior.sequence}`,
  candidateRevision: `revision:${prior.sequence + 1}`,
  authorizationRef: "authorization:local",
  scope: "scope:local",
  nonceDigest,
  linearizationIndex: prior.sequence + 1
})

const request = (
  issued: Pick<LocalPermitCommitRequest, "envelopeBytes" | "expectedBindings">,
  preStateBytes: Uint8Array = INITIAL_STATE,
  postStateBytes: Uint8Array = NEXT_STATE
) => Object.freeze({ ...issued, preStateBytes, postStateBytes })

it("fails closed with a typed issuance error when the caller-relative clock is invalid", () => {
  const issuer = makeEphemeralLocalPermitIssuer({
    keyId: "key:invalid-clock", authorizer: "principal:local-issuer",
    policyVersion: "policy:local-v1", revocationEpoch: 0,
    clock: () => new Date(Number.NaN)
  })
  expect(issuer._tag).toBe("Left")
  if (issuer._tag === "Left") expect(issuer.left.code).toBe("ISSUANCE_INVALID")
})

it.effect("uses a generated Ed25519 key to bind verification, nonce consumption, and an fsync'd local journal slot", () =>
  Effect.gen(function* () {
    const root = mkdtempSync(join(tmpdir(), "hswm-local-permit-"))
    const issuer = makeEphemeralLocalPermitIssuer({
      keyId: "key:ephemeral-local", authorizer: "principal:local-issuer",
      policyVersion: "policy:local-v1", revocationEpoch: 0, clock: frozenClock
    })
    expect(issuer._tag).toBe("Right")
    if (issuer._tag === "Left") return
    const unknown = issuer.right.issue(makeClaims(hex("9")), 60_000)
    expect(unknown._tag).toBe("Left")
    if (unknown._tag === "Left") expect(unknown.left.code).toBe("NONCE_NOT_MINTED_OR_ALREADY_ISSUED")
    const nonceDigest = mintedNonce(issuer.right)
    const issued = issuer.right.issue(makeClaims(nonceDigest), 60_000)
    expect(issued._tag).toBe("Right")
    if (issued._tag === "Left") return
    const reissued = issuer.right.issue(makeClaims(nonceDigest), 60_000)
    expect(reissued._tag).toBe("Left")
    if (reissued._tag === "Left") {
      expect(reissued.left.code).toBe("NONCE_NOT_MINTED_OR_ALREADY_ISSUED")
    }
    const store = makeLocalPermitCommitStore(root, issuer.right, frozenClock)
    const receipt = yield* store.commit(request(issued.right))
    expect(receipt.status).toBe(HSWM_LOCAL_PERMIT_COMMIT_STATUS)
    expect(receipt.nonceDigest).toBe(nonceDigest)
    const recovered = yield* store.recover()
    expect(recovered.commits).toHaveLength(1)
    expect(recovered.head?.sequence).toBe(1)
    const replay = yield* Effect.exit(store.commit(request(issued.right)))
    expect(Exit.isFailure(replay)).toBe(true)
    if (Exit.isFailure(replay)) {
      expect(replay.cause._tag).toBe("Fail")
      if (replay.cause._tag === "Fail") expect(replay.cause.error.code).toBe("NONCE_ALREADY_CONSUMED")
    }
    rmSync(root, { recursive: true, force: true })
  })
)

it.effect("recovers the local commit after a fresh store instance and rejects a stale predecessor", () =>
  Effect.gen(function* () {
    const root = mkdtempSync(join(tmpdir(), "hswm-local-permit-recovery-"))
    const issuer = makeEphemeralLocalPermitIssuer({
      keyId: "key:ephemeral-recovery", authorizer: "principal:local-issuer",
      policyVersion: "policy:local-v1", revocationEpoch: 0, clock: frozenClock
    })
    if (issuer._tag === "Left") throw issuer.left
    const first = issuer.right.issue(makeClaims(mintedNonce(issuer.right)), 60_000)
    if (first._tag === "Left") throw first.left
    const firstStore = makeLocalPermitCommitStore(root, issuer.right, frozenClock)
    yield* firstStore.commit(request(first.right))
    // Simulates a new process loading persisted public trust bytes; no private
    // signing key is restored or asserted.
    const loadedVerifier = makeLocalPermitVerifierContext(issuer.right.trustSnapshotBytes)
    if (loadedVerifier._tag === "Left") throw loadedVerifier.left
    const restarted = makeLocalPermitCommitStore(root, loadedVerifier.right, frozenClock)
    const recovered = yield* restarted.recover()
    expect(recovered.head?.sequence).toBe(1)
    const conflicting = issuer.right.issue(makeClaims(mintedNonce(issuer.right)), 60_000)
    if (conflicting._tag === "Left") throw conflicting.left
    const exit = yield* Effect.exit(restarted.commit(request(conflicting.right)))
    expect(Exit.isFailure(exit)).toBe(true)
    if (Exit.isFailure(exit) && exit.cause._tag === "Fail") expect(exit.cause.error.code).toBe("PREDECESSOR_MISMATCH")
    rmSync(root, { recursive: true, force: true })
  })
)

it.effect("allows only one of two distinct valid same-head Permits to claim an exact successor slot", () =>
  Effect.gen(function* () {
    const root = mkdtempSync(join(tmpdir(), "hswm-local-permit-slot-race-"))
    const issuer = makeEphemeralLocalPermitIssuer({
      keyId: "key:ephemeral-race", authorizer: "principal:local-issuer",
      policyVersion: "policy:local-v1", revocationEpoch: 0, clock: frozenClock
    })
    if (issuer._tag === "Left") throw issuer.left
    const left = issuer.right.issue(makeClaims(mintedNonce(issuer.right)), 60_000)
    const right = issuer.right.issue(makeClaims(mintedNonce(issuer.right)), 60_000)
    if (left._tag === "Left") throw left.left
    if (right._tag === "Left") throw right.left
    const leftStore = makeLocalPermitCommitStore(root, issuer.right, frozenClock)
    const rightStore = makeLocalPermitCommitStore(root, issuer.right, frozenClock)
    const outcomes = yield* Effect.all([
      Effect.exit(leftStore.commit(request(left.right))),
      Effect.exit(rightStore.commit(request(right.right)))
    ], { concurrency: "unbounded" })
    expect(outcomes.filter(Exit.isSuccess)).toHaveLength(1)
    const recovered = yield* makeLocalPermitCommitStore(root, issuer.right, frozenClock).recover()
    expect(recovered.commits).toHaveLength(1)
    rmSync(root, { recursive: true, force: true })
  })
)

it.effect("rejects expired or forged Permits before publication and leaves the recovered prefix empty", () =>
  Effect.gen(function* () {
    const root = mkdtempSync(join(tmpdir(), "hswm-local-permit-reject-"))
    const issuer = makeEphemeralLocalPermitIssuer({
      keyId: "key:ephemeral-reject", authorizer: "principal:local-issuer",
      policyVersion: "policy:local-v1", revocationEpoch: 0, clock: frozenClock
    })
    if (issuer._tag === "Left") throw issuer.left
    const issued = issuer.right.issue(makeClaims(mintedNonce(issuer.right)), 1)
    if (issued._tag === "Left") throw issued.left
    const expiredStore = makeLocalPermitCommitStore(root, issuer.right, () => new Date("2026-08-31T10:00:01.000Z"))
    const expired = yield* Effect.exit(expiredStore.commit(request(issued.right)))
    expect(Exit.isFailure(expired)).toBe(true)
    const forged = Uint8Array.from(issued.right.envelopeBytes)
    forged[forged.byteLength - 2] = forged[forged.byteLength - 2] === 65 ? 66 : 65
    const validClockStore = makeLocalPermitCommitStore(root, issuer.right, frozenClock)
    const forgedExit = yield* Effect.exit(validClockStore.commit({ ...request(issued.right), envelopeBytes: forged }))
    expect(Exit.isFailure(forgedExit)).toBe(true)
    const wrongPost = yield* Effect.exit(validClockStore.commit(request(issued.right, INITIAL_STATE, Uint8Array.from(Buffer.from("wrong-post-state", "utf8")))))
    expect(Exit.isFailure(wrongPost)).toBe(true)
    const recovered = yield* validClockStore.recover()
    expect(recovered.commits).toHaveLength(0)
    rmSync(root, { recursive: true, force: true })
  })
)

it.effect("rejects a validly signed non-genesis Permit when the local journal is empty", () =>
  Effect.gen(function* () {
    const root = mkdtempSync(join(tmpdir(), "hswm-local-permit-non-genesis-"))
    const issuer = makeEphemeralLocalPermitIssuer({
      keyId: "key:ephemeral-non-genesis", authorizer: "principal:local-issuer",
      policyVersion: "policy:local-v1", revocationEpoch: 0, clock: frozenClock
    })
    if (issuer._tag === "Left") throw issuer.left
    const issued = issuer.right.issue(
      makeClaims(mintedNonce(issuer.right), head(4, INITIAL_STATE, "2")),
      60_000
    )
    if (issued._tag === "Left") throw issued.left
    const store = makeLocalPermitCommitStore(root, issuer.right, frozenClock)
    const exit = yield* Effect.exit(store.commit(request(issued.right)))
    expect(Exit.isFailure(exit)).toBe(true)
    if (Exit.isFailure(exit) && exit.cause._tag === "Fail") {
      expect(exit.cause.error.code).toBe("PREDECESSOR_MISMATCH")
    }
    expect((yield* store.recover()).commits).toHaveLength(0)
    rmSync(root, { recursive: true, force: true })
  })
)

it.effect("fails closed when an on-disk verification time is canonically rewritten", () =>
  Effect.gen(function* () {
    const root = mkdtempSync(join(tmpdir(), "hswm-local-permit-mutated-"))
    const issuer = makeEphemeralLocalPermitIssuer({
      keyId: "key:ephemeral-mutated", authorizer: "principal:local-issuer",
      policyVersion: "policy:local-v1", revocationEpoch: 0, clock: frozenClock
    })
    if (issuer._tag === "Left") throw issuer.left
    const issued = issuer.right.issue(makeClaims(mintedNonce(issuer.right)), 60_000)
    if (issued._tag === "Left") throw issued.left
    const store = makeLocalPermitCommitStore(root, issuer.right, frozenClock)
    const receipt = yield* store.commit(request(issued.right))
    const record = JSON.parse(readFileSync(receipt.slotPath, "utf8")) as Record<string, unknown>
    record["committedAt"] = "2026-08-31T10:00:00.001Z"
    chmodSync(receipt.slotPath, 0o600)
    writeFileSync(receipt.slotPath, JSON.stringify(record))
    chmodSync(receipt.slotPath, 0o400)
    const failure = yield* Effect.exit(store.recover())
    expect(Exit.isFailure(failure)).toBe(true)
    rmSync(root, { recursive: true, force: true })
  })
)
