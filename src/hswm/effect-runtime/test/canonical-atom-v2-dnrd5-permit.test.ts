import { expect, it } from "@effect/vitest"
import { Either } from "effect"
import { DNRD5_AUTHORIZATION_DECISION_MEDIA_TYPE, DNRD5_CAPABILITY_ISSUANCE_MEDIA_TYPE, DNRD5_GRANT_SNAPSHOT_MEDIA_TYPE, DNRD5_PERMIT_POLICY_MEDIA_TYPE, DNRD5_REVOCATION_MEDIA_TYPE, resolveDnrd5LocalExperimentalPermit } from "../src/canonical-atom-v2-dnrd5-permit.js"
import { canonicalJsonBytes, canonicalJsonSha256 } from "../src/canonical-atom-v2-json.js"

const sha = (x: string) => x.repeat(64)
const d = (x: string) => ({ mediaType: "application/json", byteLength: 1, sha256: sha(x) })
const descriptor = (mediaType: string, core: unknown) => {
  const bytes = canonicalJsonBytes(core); const hash = canonicalJsonSha256(core)
  if (Either.isLeft(bytes) || Either.isLeft(hash)) throw new Error("fixture canonicalization failed")
  return { mediaType, byteLength: bytes.right.byteLength, sha256: hash.right }
}
const input = (effect: "ADMIT_REVISION" | "RESTORE_W0" = "ADMIT_REVISION") => {
  const restore = effect === "RESTORE_W0" ? { w0Snapshot: d("1"), expectedRootSha256: sha("2"), expectedReadsetSha256: sha("3"), restorePolicy: d("4") } : null
  return {
    _tag: "Dnrd5LocalExperimentalPermitInput", contractVersion: "hswm-dnrd5-local-experimental-state-permit/v1", domain: "LOCAL_NON_HUMAN_EXPERIMENTAL_STATE", evaluatedAt: "2026-08-28T00:00:01.000Z", effect,
    snapshot: { journalLineageId: "lineage:dnrd5", journalHead: d("a"), stateRevision: 2, stateSha256: sha("b") },
    principals: { actor: "p:actor", authorizer: "p:authorizer", canonicalStateCustodian: "p:state", restoreCustodian: "p:restore", creditAdjudicator: "p:credit", authorizationDecisionRecordCustodian: "p:record", validator: "p:validator", provenanceSealer: "p:provenance", trajectorySealer: "p:trajectory" },
    policy: { descriptor: d("c"), scope: "scope:dnrd5", allowedEffects: [effect], allowedActors: ["p:actor"], validator: d("8"), validatorPrincipal: "p:validator", allowedReadKindsSha256: sha("d"), allowedWriteKindsSha256: sha("e"), allowedTargetKindsSha256: sha("f"), exactReadsetSha256: sha("1"), exactWritesetSha256: sha("2"), exactTargetAtomKeysSha256: sha("b"), restore },
    authorizationDecision: { descriptor: d("7"), decision: "GRANTED", actor: "p:actor", authorizer: "p:authorizer", recordCustodian: "p:record", effect, scope: "scope:dnrd5", decidedAt: "2026-08-28T00:00:00.000Z", notBefore: "2026-08-28T00:00:00.500Z", expiresAt: "2026-08-28T00:02:00.000Z", generation: 1 },
    capability: { issuance: d("3"), capabilityId: "cap:one", issuedAt: "2026-08-28T00:00:00.000Z", expiresAt: "2026-08-28T00:01:00.000Z", scope: "scope:dnrd5", allowedEffect: effect, oneShotNonceSha256: sha("4"), policy: d("c"), authorization: d("7"), authorizationGeneration: 1, capabilityGeneration: 2 },
    currentRevocation: { descriptor: d("5"), checkedAt: "2026-08-28T00:00:01.000Z", status: "CHECKED_NOT_REVOKED", authorization: d("7"), capability: d("3"), authorizationGeneration: 1, capabilityGeneration: 2 },
    grantSnapshot: { descriptor: d("6"), policy: d("c"), authorization: d("7"), capability: d("3"), revocation: d("5"), snapshotSha256: "" },
    transition: { command: d("9"), readKindsSha256: sha("d"), writeKindsSha256: sha("e"), targetKindsSha256: sha("f"), readsetSha256: sha("1"), writesetSha256: sha("2"), targetAtomKeysSha256: sha("b"), validator: d("8"), validatorPrincipal: "p:validator", provenance: d("d"), provenanceSealer: "p:provenance", trajectoryContract: d("e"), trajectorySeal: d("f"), trajectorySealer: "p:trajectory" }, restore
  }
}
const rehash = (v: any) => {
  v.policy.descriptor = descriptor(DNRD5_PERMIT_POLICY_MEDIA_TYPE, { scope: v.policy.scope, allowedEffects: v.policy.allowedEffects, allowedActors: v.policy.allowedActors, validator: v.policy.validator, validatorPrincipal: v.policy.validatorPrincipal, allowedReadKindsSha256: v.policy.allowedReadKindsSha256, allowedWriteKindsSha256: v.policy.allowedWriteKindsSha256, allowedTargetKindsSha256: v.policy.allowedTargetKindsSha256, exactReadsetSha256: v.policy.exactReadsetSha256, exactWritesetSha256: v.policy.exactWritesetSha256, exactTargetAtomKeysSha256: v.policy.exactTargetAtomKeysSha256, restore: v.policy.restore })
  v.authorizationDecision.descriptor = descriptor(DNRD5_AUTHORIZATION_DECISION_MEDIA_TYPE, { decision: v.authorizationDecision.decision, actor: v.authorizationDecision.actor, authorizer: v.authorizationDecision.authorizer, recordCustodian: v.authorizationDecision.recordCustodian, effect: v.authorizationDecision.effect, scope: v.authorizationDecision.scope, decidedAt: v.authorizationDecision.decidedAt, notBefore: v.authorizationDecision.notBefore, expiresAt: v.authorizationDecision.expiresAt, generation: v.authorizationDecision.generation })
  v.capability.issuance = descriptor(DNRD5_CAPABILITY_ISSUANCE_MEDIA_TYPE, { capabilityId: v.capability.capabilityId, issuedAt: v.capability.issuedAt, expiresAt: v.capability.expiresAt, scope: v.capability.scope, allowedEffect: v.capability.allowedEffect, oneShotNonceSha256: v.capability.oneShotNonceSha256, policy: v.capability.policy, authorization: v.capability.authorization, authorizationGeneration: v.capability.authorizationGeneration, capabilityGeneration: v.capability.capabilityGeneration })
  v.currentRevocation.descriptor = descriptor(DNRD5_REVOCATION_MEDIA_TYPE, { checkedAt: v.currentRevocation.checkedAt, status: v.currentRevocation.status, authorization: v.currentRevocation.authorization, capability: v.currentRevocation.capability, authorizationGeneration: v.currentRevocation.authorizationGeneration, capabilityGeneration: v.currentRevocation.capabilityGeneration })
  v.grantSnapshot.descriptor = descriptor(DNRD5_GRANT_SNAPSHOT_MEDIA_TYPE, { policy: v.grantSnapshot.policy, authorization: v.grantSnapshot.authorization, capability: v.grantSnapshot.capability, revocation: v.grantSnapshot.revocation })
  v.grantSnapshot.snapshotSha256 = v.grantSnapshot.descriptor.sha256
}
const valid = (effect: "ADMIT_REVISION" | "RESTORE_W0" = "ADMIT_REVISION") => {
  const v = input(effect); rehash(v)
  v.capability.policy = v.policy.descriptor; v.capability.authorization = v.authorizationDecision.descriptor; rehash(v)
  v.currentRevocation.authorization = v.authorizationDecision.descriptor; v.currentRevocation.capability = v.capability.issuance; rehash(v)
  v.grantSnapshot.policy = v.policy.descriptor; v.grantSnapshot.authorization = v.authorizationDecision.descriptor; v.grantSnapshot.capability = v.capability.issuance; v.grantSnapshot.revocation = v.currentRevocation.descriptor; rehash(v)
  return v
}

it("resolves only exact supplied non-human snapshot eligibility", () => {
  const result = resolveDnrd5LocalExperimentalPermit(valid())
  expect(Either.isRight(result)).toBe(true)
  if (Either.isRight(result)) expect(result.right.capability).toContain("NOT_ISSUED")
})

it("rejects opaque authorization and authorization actor/authorizer/effect/scope/time/generation drift", () => {
  const cases = [
    (v: any) => { v.grantSnapshot.authorization = d("0") },
    (v: any) => { v.authorizationDecision.actor = "p:other"; rehash(v) },
    (v: any) => { v.authorizationDecision.authorizer = "p:other"; rehash(v) },
    (v: any) => { v.authorizationDecision.effect = "RESTORE_W0"; rehash(v) },
    (v: any) => { v.authorizationDecision.scope = "scope:other"; rehash(v) },
    (v: any) => { v.authorizationDecision.expiresAt = "2026-08-28T00:00:01.000Z"; rehash(v) },
    (v: any) => { v.authorizationDecision.decidedAt = "2026-08-28T00:00:00.750Z"; v.authorizationDecision.notBefore = "2026-08-28T00:00:00.500Z"; rehash(v) },
    (v: any) => { v.authorizationDecision.recordCustodian = "p:other"; rehash(v) },
    (v: any) => { v.authorizationDecision.generation = 3; rehash(v) }
  ]
  for (const mutate of cases) { const v = valid(); mutate(v); expect(Either.isLeft(resolveDnrd5LocalExperimentalPermit(v))).toBe(true) }
})

it("requires exact policy actor/validator, capability/revocation closure, and rejects sibling rehashes", () => {
  const cases = [
    (v: any) => { v.principals.authorizer = v.principals.actor },
    (v: any) => { v.principals.authorizer = v.principals.restoreCustodian },
    (v: any) => { v.policy.allowedActors = ["p:other"]; rehash(v) },
    (v: any) => { v.policy.allowedActors = ["p:actor", "p:actor"]; rehash(v) },
    (v: any) => { v.policy.validator = d("0"); rehash(v) },
    (v: any) => { v.policy.validatorPrincipal = "p:other"; rehash(v) },
    (v: any) => { v.transition.validatorPrincipal = "p:other" },
    (v: any) => { v.transition.provenanceSealer = "p:other" },
    (v: any) => { v.transition.trajectorySealer = "p:other" },
    (v: any) => { v.capability.policy = d("0"); rehash(v) },
    (v: any) => { v.capability.authorization = d("0"); rehash(v) },
    (v: any) => { v.currentRevocation.authorization = d("0"); rehash(v) },
    (v: any) => { v.currentRevocation.capability = d("0"); rehash(v) },
    (v: any) => { v.currentRevocation.capabilityGeneration = 3; rehash(v) },
    (v: any) => { v.authorizationDecision.authorizer = "p:state"; rehash(v) }
  ]
  for (const mutate of cases) { const v = valid(); mutate(v); expect(Either.isLeft(resolveDnrd5LocalExperimentalPermit(v))).toBe(true) }
})

it("requires exact policy-bound restore W0/root/readset/restore-policy", () => {
  expect(Either.isRight(resolveDnrd5LocalExperimentalPermit(valid("RESTORE_W0")))).toBe(true)
  const cases = [
    (v: any) => { v.restore.expectedRootSha256 = sha("0"); rehash(v) },
    (v: any) => { v.restore.restorePolicy = d("0"); rehash(v) },
    (v: any) => { v.policy.restore.expectedReadsetSha256 = sha("0"); rehash(v) },
    (v: any) => { v.restore = null; rehash(v) }
  ]
  for (const mutate of cases) { const v = valid("RESTORE_W0"); mutate(v); expect(Either.isLeft(resolveDnrd5LocalExperimentalPermit(v))).toBe(true) }
})

it("rejects excess keys and deep-snapshots output", () => {
  const excess: any = valid(); excess.authorizationDecision.undeclared = "no"; expect(Either.isLeft(resolveDnrd5LocalExperimentalPermit(excess))).toBe(true)
  const supplied: any = valid(); const result = resolveDnrd5LocalExperimentalPermit(supplied)
  if (Either.isRight(result)) { supplied.snapshot.journalHead.sha256 = sha("0"); expect(result.right.snapshot.journalHead.sha256).toBe(sha("a")); expect(Object.isFrozen(result.right.snapshot.journalHead)).toBe(true) } else throw new Error("valid fixture rejected")
})
