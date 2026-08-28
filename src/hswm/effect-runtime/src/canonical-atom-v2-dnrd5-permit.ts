/** Pure, non-human DNRD-5 experimental-state Permit eligibility resolver. */
import { Data, Either, Schema } from "effect"

import { canonicalJsonBytes, canonicalJsonSha256 } from "./canonical-atom-v2-json.js"

export const DNRD5_LOCAL_EXPERIMENTAL_PERMIT_V1 =
  "hswm-dnrd5-local-experimental-state-permit/v1" as const
export const DNRD5_LOCAL_EXPERIMENTAL_DOMAIN =
  "LOCAL_NON_HUMAN_EXPERIMENTAL_STATE" as const

const Identifier = Schema.String.pipe(Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/))
const Sha256 = Schema.String.pipe(Schema.pattern(/^[0-9a-f]{64}$/))
const Instant = Schema.String.pipe(Schema.pattern(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/))
const SafeInteger = Schema.Number.pipe(Schema.int(), Schema.nonNegative(), Schema.lessThanOrEqualTo(Number.MAX_SAFE_INTEGER))
const MediaType = Schema.String.pipe(Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/+-]{0,255}$/))
const Descriptor = Schema.Struct({ mediaType: MediaType, byteLength: SafeInteger, sha256: Sha256 })
export const DNRD5_PERMIT_POLICY_MEDIA_TYPE = "application/vnd.hswm.dnrd5.local-experimental-permit-policy-v1+json" as const
export const DNRD5_AUTHORIZATION_DECISION_MEDIA_TYPE = "application/vnd.hswm.dnrd5.local-experimental-authorization-decision-v1+json" as const
export const DNRD5_CAPABILITY_ISSUANCE_MEDIA_TYPE = "application/vnd.hswm.dnrd5.local-experimental-capability-v1+json" as const
export const DNRD5_REVOCATION_MEDIA_TYPE = "application/vnd.hswm.dnrd5.local-experimental-revocation-v1+json" as const
export const DNRD5_GRANT_SNAPSHOT_MEDIA_TYPE = "application/vnd.hswm.dnrd5.local-experimental-grant-snapshot-v1+json" as const

const Snapshot = Schema.Struct({ journalLineageId: Identifier, journalHead: Descriptor, stateRevision: SafeInteger, stateSha256: Sha256 })
const Principals = Schema.Struct({
  actor: Identifier, authorizer: Identifier, canonicalStateCustodian: Identifier,
  restoreCustodian: Identifier, creditAdjudicator: Identifier,
  authorizationDecisionRecordCustodian: Identifier, validator: Identifier,
  provenanceSealer: Identifier, trajectorySealer: Identifier
})
const Restore = Schema.Struct({ w0Snapshot: Descriptor, expectedRootSha256: Sha256, expectedReadsetSha256: Sha256, restorePolicy: Descriptor })
const Policy = Schema.Struct({
  descriptor: Descriptor, scope: Identifier,
  allowedEffects: Schema.Array(Schema.Literal("ADMIT_REVISION", "RESTORE_W0")).pipe(Schema.minItems(1), Schema.maxItems(2)),
  allowedActors: Schema.Array(Identifier).pipe(Schema.minItems(1), Schema.maxItems(256)), validator: Descriptor, validatorPrincipal: Identifier,
  allowedReadKindsSha256: Sha256, allowedWriteKindsSha256: Sha256,
  allowedTargetKindsSha256: Sha256, exactReadsetSha256: Sha256, exactWritesetSha256: Sha256,
  exactTargetAtomKeysSha256: Sha256, restore: Schema.NullOr(Restore)
})
const AuthorizationDecision = Schema.Struct({
  descriptor: Descriptor, decision: Schema.Literal("GRANTED"), actor: Identifier, authorizer: Identifier, recordCustodian: Identifier,
  effect: Schema.Literal("ADMIT_REVISION", "RESTORE_W0"), scope: Identifier,
  decidedAt: Instant, notBefore: Instant, expiresAt: Instant, generation: SafeInteger
})
const Capability = Schema.Struct({
  issuance: Descriptor, capabilityId: Identifier, issuedAt: Instant, expiresAt: Instant,
  scope: Identifier, allowedEffect: Schema.Literal("ADMIT_REVISION", "RESTORE_W0"), oneShotNonceSha256: Sha256,
  policy: Descriptor, authorization: Descriptor, authorizationGeneration: SafeInteger, capabilityGeneration: SafeInteger
})
const Revocation = Schema.Struct({
  descriptor: Descriptor, checkedAt: Instant, status: Schema.Literal("CHECKED_NOT_REVOKED"),
  authorization: Descriptor, capability: Descriptor, authorizationGeneration: SafeInteger, capabilityGeneration: SafeInteger
})
const GrantSnapshot = Schema.Struct({
  descriptor: Descriptor, policy: Descriptor, authorization: Descriptor,
  capability: Descriptor, revocation: Descriptor, snapshotSha256: Sha256
})
const Transition = Schema.Struct({
  command: Descriptor, readKindsSha256: Sha256, writeKindsSha256: Sha256, targetKindsSha256: Sha256,
  readsetSha256: Sha256, writesetSha256: Sha256, targetAtomKeysSha256: Sha256,
  validator: Descriptor, validatorPrincipal: Identifier, provenance: Descriptor, provenanceSealer: Identifier,
  trajectoryContract: Descriptor, trajectorySeal: Descriptor, trajectorySealer: Identifier
})

export const Dnrd5LocalExperimentalPermitInputSchema = Schema.Struct({
  _tag: Schema.Literal("Dnrd5LocalExperimentalPermitInput"),
  contractVersion: Schema.Literal(DNRD5_LOCAL_EXPERIMENTAL_PERMIT_V1),
  domain: Schema.Literal(DNRD5_LOCAL_EXPERIMENTAL_DOMAIN), evaluatedAt: Instant,
  effect: Schema.Literal("ADMIT_REVISION", "RESTORE_W0"), snapshot: Snapshot,
  principals: Principals, policy: Policy, authorizationDecision: AuthorizationDecision, capability: Capability, currentRevocation: Revocation,
  grantSnapshot: GrantSnapshot, transition: Transition, restore: Schema.NullOr(Restore)
})
export type Dnrd5LocalExperimentalPermitInput = Schema.Schema.Type<typeof Dnrd5LocalExperimentalPermitInputSchema>

export type Dnrd5LocalExperimentalPermitErrorCode =
  | "INPUT_INVALID" | "TIME_INVALID" | "PRINCIPAL_INEQUALITY" | "POLICY_SCOPE_INVALID"
  | "EFFECT_INVALID" | "CAPABILITY_INVALID" | "REVOCATION_INVALID" | "GRANT_CLOSURE_INVALID"
  | "RESTORE_BRANCH_INVALID" | "CANONICAL_ENCODING_INVALID"
export class Dnrd5LocalExperimentalPermitError extends Data.TaggedError("Dnrd5LocalExperimentalPermitError")<{
  readonly code: Dnrd5LocalExperimentalPermitErrorCode
  readonly detail: string
}> {}
const fail = (code: Dnrd5LocalExperimentalPermitErrorCode, detail: string): Either.Either<never, Dnrd5LocalExperimentalPermitError> =>
  Either.left(new Dnrd5LocalExperimentalPermitError({ code, detail }))
const sameDescriptor = (left: Schema.Schema.Type<typeof Descriptor>, right: Schema.Schema.Type<typeof Descriptor>) =>
  left.mediaType === right.mediaType && left.byteLength === right.byteLength && left.sha256 === right.sha256
const validTime = (value: string) => Number.isFinite(Date.parse(value)) && new Date(Date.parse(value)).toISOString() === value
const strictlyAscending = (values: ReadonlyArray<string>) => values.every((value, index) => index === 0 || values[index - 1]! < value)
const descriptorFor = (mediaType: string, core: unknown): Either.Either<Schema.Schema.Type<typeof Descriptor>, Dnrd5LocalExperimentalPermitError> => {
  const bytes = canonicalJsonBytes(core)
  const hash = canonicalJsonSha256(core)
  if (Either.isLeft(bytes) || Either.isLeft(hash)) return fail("CANONICAL_ENCODING_INVALID", "semantic record cannot be canonically described")
  return Either.right({ mediaType, byteLength: bytes.right.byteLength, sha256: hash.right })
}
const policyCore = (value: Dnrd5LocalExperimentalPermitInput["policy"]) => ({ scope: value.scope, allowedEffects: value.allowedEffects, allowedActors: value.allowedActors, validator: value.validator, validatorPrincipal: value.validatorPrincipal, allowedReadKindsSha256: value.allowedReadKindsSha256, allowedWriteKindsSha256: value.allowedWriteKindsSha256, allowedTargetKindsSha256: value.allowedTargetKindsSha256, exactReadsetSha256: value.exactReadsetSha256, exactWritesetSha256: value.exactWritesetSha256, exactTargetAtomKeysSha256: value.exactTargetAtomKeysSha256, restore: value.restore })
const authorizationDecisionCore = (value: Dnrd5LocalExperimentalPermitInput["authorizationDecision"]) => ({ decision: value.decision, actor: value.actor, authorizer: value.authorizer, recordCustodian: value.recordCustodian, effect: value.effect, scope: value.scope, decidedAt: value.decidedAt, notBefore: value.notBefore, expiresAt: value.expiresAt, generation: value.generation })
const capabilityCore = (value: Dnrd5LocalExperimentalPermitInput["capability"]) => ({ capabilityId: value.capabilityId, issuedAt: value.issuedAt, expiresAt: value.expiresAt, scope: value.scope, allowedEffect: value.allowedEffect, oneShotNonceSha256: value.oneShotNonceSha256, policy: value.policy, authorization: value.authorization, authorizationGeneration: value.authorizationGeneration, capabilityGeneration: value.capabilityGeneration })
const revocationCore = (value: Dnrd5LocalExperimentalPermitInput["currentRevocation"]) => ({ checkedAt: value.checkedAt, status: value.status, authorization: value.authorization, capability: value.capability, authorizationGeneration: value.authorizationGeneration, capabilityGeneration: value.capabilityGeneration })

const validate = (input: unknown): Either.Either<Dnrd5LocalExperimentalPermitInput, Dnrd5LocalExperimentalPermitError> => {
  const decoded = Schema.decodeUnknownEither(Dnrd5LocalExperimentalPermitInputSchema, { onExcessProperty: "error" })(input)
  if (Either.isLeft(decoded)) return fail("INPUT_INVALID", "input is not the exact DNRD-5 local experimental Permit shape")
  const value = decoded.right
  const authorization = value.authorizationDecision
  if (!validTime(value.evaluatedAt) || !validTime(authorization.decidedAt) || !validTime(authorization.notBefore) || !validTime(authorization.expiresAt) || !validTime(value.capability.issuedAt) || !validTime(value.capability.expiresAt) || !validTime(value.currentRevocation.checkedAt) ||
      Date.parse(authorization.decidedAt) > Date.parse(authorization.notBefore) || Date.parse(authorization.notBefore) > Date.parse(value.evaluatedAt) || Date.parse(value.evaluatedAt) >= Date.parse(authorization.expiresAt) ||
      Date.parse(value.capability.issuedAt) > Date.parse(value.evaluatedAt) || Date.parse(value.evaluatedAt) >= Date.parse(value.capability.expiresAt) || Date.parse(value.currentRevocation.checkedAt) !== Date.parse(value.evaluatedAt)) {
    return fail("TIME_INVALID", "authorization, issuance, expiry, evaluation, and current revocation time must be exact and current")
  }
  const p = value.principals
  if ([p.actor, p.canonicalStateCustodian, p.restoreCustodian, p.creditAdjudicator, p.authorizationDecisionRecordCustodian].includes(p.authorizer))
    return fail("PRINCIPAL_INEQUALITY", "authorizer must differ from actor and all DNRD-5 state-change custodians")
  if (!strictlyAscending(value.policy.allowedEffects) || new Set(value.policy.allowedEffects).size !== value.policy.allowedEffects.length ||
      !strictlyAscending(value.policy.allowedActors) || new Set(value.policy.allowedActors).size !== value.policy.allowedActors.length ||
      !value.policy.allowedEffects.includes(value.effect) || !value.policy.allowedActors.includes(p.actor) || !sameDescriptor(value.policy.validator, value.transition.validator) || value.policy.validatorPrincipal !== p.validator ||
      value.transition.validatorPrincipal !== p.validator || value.transition.provenanceSealer !== p.provenanceSealer || value.transition.trajectorySealer !== p.trajectorySealer ||
      authorization.actor !== p.actor || authorization.authorizer !== p.authorizer || authorization.recordCustodian !== p.authorizationDecisionRecordCustodian || authorization.effect !== value.effect || authorization.scope !== value.policy.scope ||
      value.capability.scope !== value.policy.scope || value.capability.allowedEffect !== value.effect ||
      value.capability.scope !== authorization.scope || value.capability.allowedEffect !== authorization.effect ||
      Date.parse(value.capability.issuedAt) < Date.parse(authorization.decidedAt) || Date.parse(value.capability.expiresAt) > Date.parse(authorization.expiresAt))
    return fail("POLICY_SCOPE_INVALID", "actor, validator, authorization, capability, and effect must be an exact policy-authorized scope")
  if (value.transition.readKindsSha256 !== value.policy.allowedReadKindsSha256 || value.transition.writeKindsSha256 !== value.policy.allowedWriteKindsSha256 ||
      value.transition.targetKindsSha256 !== value.policy.allowedTargetKindsSha256 || value.transition.readsetSha256 !== value.policy.exactReadsetSha256 || value.transition.writesetSha256 !== value.policy.exactWritesetSha256 || value.transition.targetAtomKeysSha256 !== value.policy.exactTargetAtomKeysSha256)
    return fail("POLICY_SCOPE_INVALID", "transition read/write/target kinds and exact sets must equal the policy binding")
  if (value.currentRevocation.status !== "CHECKED_NOT_REVOKED") return fail("REVOCATION_INVALID", "current revocation must be checked-not-revoked")
  const expectedPolicy = descriptorFor(DNRD5_PERMIT_POLICY_MEDIA_TYPE, policyCore(value.policy))
  const expectedAuthorization = descriptorFor(DNRD5_AUTHORIZATION_DECISION_MEDIA_TYPE, authorizationDecisionCore(authorization))
  const expectedCapability = descriptorFor(DNRD5_CAPABILITY_ISSUANCE_MEDIA_TYPE, capabilityCore(value.capability))
  const expectedRevocation = descriptorFor(DNRD5_REVOCATION_MEDIA_TYPE, revocationCore(value.currentRevocation))
  if (Either.isLeft(expectedPolicy) || Either.isLeft(expectedAuthorization) || Either.isLeft(expectedCapability) || Either.isLeft(expectedRevocation)) return fail("CANONICAL_ENCODING_INVALID", "semantic descriptor reconstruction failed")
  if (!sameDescriptor(value.policy.descriptor, expectedPolicy.right) || !sameDescriptor(authorization.descriptor, expectedAuthorization.right) || !sameDescriptor(value.capability.issuance, expectedCapability.right) || !sameDescriptor(value.currentRevocation.descriptor, expectedRevocation.right))
    return fail("GRANT_CLOSURE_INVALID", "policy/authorization/capability/revocation descriptor does not equal its semantic core")
  if (!sameDescriptor(value.capability.policy, value.policy.descriptor) || !sameDescriptor(value.capability.authorization, authorization.descriptor) ||
      value.capability.authorizationGeneration !== authorization.generation ||
      !sameDescriptor(value.currentRevocation.authorization, authorization.descriptor) || !sameDescriptor(value.currentRevocation.capability, value.capability.issuance) ||
      value.currentRevocation.authorizationGeneration !== authorization.generation || value.currentRevocation.capabilityGeneration !== value.capability.capabilityGeneration)
    return fail("GRANT_CLOSURE_INVALID", "capability and revocation must close over exact policy/authorization/capability generations")
  if (!sameDescriptor(value.grantSnapshot.policy, value.policy.descriptor) || !sameDescriptor(value.grantSnapshot.authorization, authorization.descriptor) || !sameDescriptor(value.grantSnapshot.capability, value.capability.issuance) || !sameDescriptor(value.grantSnapshot.revocation, value.currentRevocation.descriptor))
    return fail("GRANT_CLOSURE_INVALID", "grant snapshot must close over exact policy/authorization/capability/revocation descriptors")
  const grantCore = { policy: value.grantSnapshot.policy, authorization: value.grantSnapshot.authorization, capability: value.grantSnapshot.capability, revocation: value.grantSnapshot.revocation }
  const expectedGrant = descriptorFor(DNRD5_GRANT_SNAPSHOT_MEDIA_TYPE, grantCore)
  if (Either.isLeft(expectedGrant) || value.grantSnapshot.snapshotSha256 !== expectedGrant.right.sha256 || !sameDescriptor(value.grantSnapshot.descriptor, expectedGrant.right))
    return fail("GRANT_CLOSURE_INVALID", "grant snapshot descriptor closure hash is not exact")
  if (value.effect === "ADMIT_REVISION" && (value.restore !== null || value.policy.restore !== null)) return fail("RESTORE_BRANCH_INVALID", "revision admission must not carry restore fields")
  if (value.effect === "RESTORE_W0" && (value.restore === null || value.policy.restore === null ||
      !sameDescriptor(value.restore.w0Snapshot, value.policy.restore.w0Snapshot) || value.restore.expectedRootSha256 !== value.policy.restore.expectedRootSha256 ||
      value.restore.expectedReadsetSha256 !== value.policy.restore.expectedReadsetSha256 || !sameDescriptor(value.restore.restorePolicy, value.policy.restore.restorePolicy)))
    return fail("RESTORE_BRANCH_INVALID", "W0 restore requires the exact policy-bound W0/root/readset/restore-policy fields")
  return Either.right(value)
}

export interface Dnrd5LocalExperimentalPermitResolution {
  readonly _tag: "Dnrd5LocalExperimentalPermitResolution"
  readonly contractVersion: typeof DNRD5_LOCAL_EXPERIMENTAL_PERMIT_V1
  readonly status: "ELIGIBLE_AT_EXACT_SUPPLIED_SNAPSHOT_NOT_COMMIT_CAPABILITY"
  readonly domain: typeof DNRD5_LOCAL_EXPERIMENTAL_DOMAIN
  readonly effect: "ADMIT_REVISION" | "RESTORE_W0"
  readonly snapshot: Schema.Schema.Type<typeof Snapshot>
  readonly inputSha256: string
  readonly resolutionCoreSha256: string
  readonly snapshotBasis: "CALLER_SUPPLIED_SNAPSHOT_AND_RECORD_DESCRIPTORS_NOT_STATE_CONTENT_READ"
  readonly capability: "NOT_ISSUED_NOT_CONSUMED_NOT_COMMIT_CAPABILITY"
  readonly admission: "NOT_ADMITTED_BY_PURE_RESOLUTION"
  readonly terminal: "NOT_CHRONOLOGY_NOT_ISOLATION_NOT_EXECUTION_NOT_SCIENTIFIC_RESULT"
}

const deepSnapshot = <A>(value: A): A => {
  const cloned = structuredClone(value)
  const freeze = (candidate: unknown): void => {
    if (typeof candidate === "object" && candidate !== null && !Object.isFrozen(candidate)) {
      Object.freeze(candidate)
      for (const nested of Object.values(candidate)) freeze(nested)
    }
  }
  freeze(cloned)
  return cloned
}

export const resolveDnrd5LocalExperimentalPermit = (input: unknown): Either.Either<Dnrd5LocalExperimentalPermitResolution, Dnrd5LocalExperimentalPermitError> => {
  const checked = validate(input)
  if (Either.isLeft(checked)) return Either.left(checked.left)
  const inputBytes = canonicalJsonBytes(checked.right)
  if (Either.isLeft(inputBytes)) return fail("CANONICAL_ENCODING_INVALID", inputBytes.left.detail)
  const inputHash = canonicalJsonSha256(checked.right)
  if (Either.isLeft(inputHash)) return fail("CANONICAL_ENCODING_INVALID", inputHash.left.detail)
  const core = { contractVersion: DNRD5_LOCAL_EXPERIMENTAL_PERMIT_V1, domain: DNRD5_LOCAL_EXPERIMENTAL_DOMAIN, effect: checked.right.effect, snapshot: checked.right.snapshot, inputSha256: inputHash.right }
  const coreHash = canonicalJsonSha256(core)
  if (Either.isLeft(coreHash)) return fail("CANONICAL_ENCODING_INVALID", coreHash.left.detail)
  return Either.right(deepSnapshot({ _tag: "Dnrd5LocalExperimentalPermitResolution", contractVersion: DNRD5_LOCAL_EXPERIMENTAL_PERMIT_V1, status: "ELIGIBLE_AT_EXACT_SUPPLIED_SNAPSHOT_NOT_COMMIT_CAPABILITY", domain: DNRD5_LOCAL_EXPERIMENTAL_DOMAIN, effect: checked.right.effect, snapshot: checked.right.snapshot, inputSha256: inputHash.right, resolutionCoreSha256: coreHash.right, snapshotBasis: "CALLER_SUPPLIED_SNAPSHOT_AND_RECORD_DESCRIPTORS_NOT_STATE_CONTENT_READ", capability: "NOT_ISSUED_NOT_CONSUMED_NOT_COMMIT_CAPABILITY", admission: "NOT_ADMITTED_BY_PURE_RESOLUTION", terminal: "NOT_CHRONOLOGY_NOT_ISOLATION_NOT_EXECUTION_NOT_SCIENTIFIC_RESULT" } satisfies Dnrd5LocalExperimentalPermitResolution))
}
