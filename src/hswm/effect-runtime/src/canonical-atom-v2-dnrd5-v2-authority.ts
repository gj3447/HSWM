/**
 * DNRD-5 v2 authority-payload verifier for a supplied canonical state.
 *
 * The verifier decodes exact content bytes and checks their membership in a
 * structurally valid DNRD-5 v2 state. A caller-supplied state is not proof of
 * durable recovery. Success is therefore not a Permit, a journal/CAS result,
 * an occurrence, learning, or scientific efficacy.
 */
import { createHash } from "node:crypto"

import { Data, Either, Schema } from "effect"

import {
  validateCanonicalAtomV2State,
  type CanonicalAtomV2State
} from "./canonical-atom-v2-domain.js"
import {
  DNRD5_V2_REFERENCE_TYPE,
  DNRD5_V2_SCHEMA_VERSION,
  makeDnrd5V2CanonicalSchema
} from "./canonical-atom-v2-dnrd5-v2-schema.js"
import {
  canonicalJsonBytes,
  decodeCanonicalJsonBytes
} from "./canonical-atom-v2-json.js"
import {
  CanonicalAtomV2Schema,
  canonicalAtomV2KeyId,
  type CanonicalAtomV2
} from "./canonical-atom-v2-schema.js"
import { canonicalAtomV2StateSha256 } from "./canonical-atom-v2-state-journal.js"

export const DNRD5_V2_AUTHORITY_PAYLOAD_V1 =
  "hswm-dnrd5-v2-authority-payload/v1" as const
export const DNRD5_V2_PERMIT_POLICY_MEDIA_TYPE =
  "application/vnd.hswm.dnrd5.v2.permit-policy-v1+json" as const
export const DNRD5_V2_AUTHORIZATION_DECISION_MEDIA_TYPE =
  "application/vnd.hswm.dnrd5.v2.authorization-decision-v1+json" as const
export const DNRD5_V2_CAPABILITY_ISSUANCE_MEDIA_TYPE =
  "application/vnd.hswm.dnrd5.v2.capability-issuance-v1+json" as const
export const DNRD5_V2_REVOCATION_STATUS_MEDIA_TYPE =
  "application/vnd.hswm.dnrd5.v2.revocation-status-v1+json" as const
export const DNRD5_V2_GRANT_SNAPSHOT_MEDIA_TYPE =
  "application/vnd.hswm.dnrd5.v2.grant-snapshot-v1+json" as const

export type Dnrd5V2AuthorityPhase =
  | "MAIN_ADMIT"
  | "MAIN_RESTORE"
  | "RECEIPT_ADMIT"
  | "RECEIPT_RESTORE"

const Phase = Schema.Literal(
  "MAIN_ADMIT",
  "MAIN_RESTORE",
  "RECEIPT_ADMIT",
  "RECEIPT_RESTORE"
)
const Identifier = Schema.String.pipe(
  Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/)
)
const CanonicalKeyIdText = Schema.String.pipe(
  Schema.minLength(7),
  Schema.maxLength(1_027)
)
const Sha256 = Schema.String.pipe(Schema.pattern(/^[0-9a-f]{64}$/))
const Instant = Schema.String.pipe(
  Schema.pattern(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/)
)
const Generation = Schema.Number.pipe(
  Schema.int(),
  Schema.nonNegative(),
  Schema.lessThanOrEqualTo(Number.MAX_SAFE_INTEGER)
)

const PolicyPayload = Schema.Struct({
  contractVersion: Schema.Literal(DNRD5_V2_AUTHORITY_PAYLOAD_V1),
  scope: Identifier,
  allowedActors: Schema.Array(Identifier).pipe(
    Schema.minItems(1),
    Schema.maxItems(128)
  ),
  allowedPhases: Schema.Array(Phase).pipe(
    Schema.minItems(1),
    Schema.maxItems(4)
  ),
  allowMainReceiptPairing: Schema.Boolean,
  generation: Generation
})
const AuthorizationPayload = Schema.Struct({
  contractVersion: Schema.Literal(DNRD5_V2_AUTHORITY_PAYLOAD_V1),
  scope: Identifier,
  actor: Identifier,
  authorizer: Identifier,
  authorizationRef: Identifier,
  recordCustodian: Identifier,
  phase: Phase,
  policyAtomKeyId: CanonicalKeyIdText,
  policyGeneration: Generation,
  decidedAt: Instant,
  notBefore: Instant,
  expiresAt: Instant,
  generation: Generation
})
const CapabilityPayload = Schema.Struct({
  contractVersion: Schema.Literal(DNRD5_V2_AUTHORITY_PAYLOAD_V1),
  scope: Identifier,
  actor: Identifier,
  phase: Phase,
  purposeAtomKeyId: CanonicalKeyIdText,
  capabilityId: Identifier,
  nonceSha256: Sha256,
  policyAtomKeyId: CanonicalKeyIdText,
  policyGeneration: Generation,
  authorizationAtomKeyId: CanonicalKeyIdText,
  authorizationRef: Identifier,
  authorizationGeneration: Generation,
  generation: Generation,
  issuedAt: Instant,
  expiresAt: Instant
})
const RevocationPayload = Schema.Struct({
  contractVersion: Schema.Literal(DNRD5_V2_AUTHORITY_PAYLOAD_V1),
  status: Schema.Literal("CHECKED_NOT_REVOKED"),
  checkedAt: Instant,
  authorizationAtomKeyId: CanonicalKeyIdText,
  authorizationRef: Identifier,
  capabilityAtomKeyId: CanonicalKeyIdText,
  capabilityId: Identifier,
  policyGeneration: Generation,
  authorizationGeneration: Generation,
  capabilityGeneration: Generation
})
const GrantPayload = Schema.Struct({
  contractVersion: Schema.Literal(DNRD5_V2_AUTHORITY_PAYLOAD_V1),
  policyAtomKeyId: CanonicalKeyIdText,
  authorizationAtomKeyId: CanonicalKeyIdText,
  authorizationRef: Identifier,
  capabilityAtomKeyId: CanonicalKeyIdText,
  capabilityId: Identifier,
  revocationAtomKeyId: CanonicalKeyIdText,
  policyGeneration: Generation,
  authorizationGeneration: Generation,
  capabilityGeneration: Generation
})

type Policy = Schema.Schema.Type<typeof PolicyPayload>
type Authorization = Schema.Schema.Type<typeof AuthorizationPayload>
type Capability = Schema.Schema.Type<typeof CapabilityPayload>
type Revocation = Schema.Schema.Type<typeof RevocationPayload>
type Grant = Schema.Schema.Type<typeof GrantPayload>

export interface Dnrd5V2AuthorityContent {
  readonly atom: CanonicalAtomV2
  readonly bytes: Uint8Array
}

export interface Dnrd5V2AuthorityChain {
  readonly phase: Dnrd5V2AuthorityPhase
  readonly policy: Dnrd5V2AuthorityContent
  readonly authorization: Dnrd5V2AuthorityContent
  readonly capability: Dnrd5V2AuthorityContent
  readonly revocation: Dnrd5V2AuthorityContent
  readonly grant: Dnrd5V2AuthorityContent
}

export interface Dnrd5V2AuthorityPrincipals {
  readonly actor: string
  readonly authorizer: string
  readonly canonicalStateCustodian: string
  readonly restoreCustodian: string
  readonly creditAdjudicator: string
  readonly authorizationRecordCustodian: string
}

export interface Dnrd5V2AuthorityStateInput {
  readonly _tag: "Dnrd5V2AuthorityStateInput"
  readonly contractVersion: typeof DNRD5_V2_AUTHORITY_PAYLOAD_V1
  readonly evaluatedAt: string
  readonly principals: Dnrd5V2AuthorityPrincipals
  /** Supplied state. Durable recovery has to be established by the caller. */
  readonly state: CanonicalAtomV2State
  readonly chain: Dnrd5V2AuthorityChain
}

export type Dnrd5V2AuthorityErrorCode =
  | "INPUT_INVALID"
  | "STATE_INVALID"
  | "ATOM_INVALID"
  | "PAYLOAD_INVALID"
  | "PAYLOAD_BINDING_INVALID"
  | "REFERENCE_CLOSURE_INVALID"
  | "TIME_INVALID"
  | "SNAPSHOT_MEMBERSHIP_INVALID"
  | "PRINCIPAL_INEQUALITY"
  | "PURPOSE_INVALID"
  | "CHAIN_INVALID"
  | "CHAIN_REUSE_INVALID"
  | "SEQUENCE_INVALID"

export class Dnrd5V2AuthorityError extends Data.TaggedError(
  "Dnrd5V2AuthorityError"
)<{
  readonly code: Dnrd5V2AuthorityErrorCode
  readonly detail: string
}> {}

const fail = (
  code: Dnrd5V2AuthorityErrorCode,
  detail: string
): Either.Either<never, Dnrd5V2AuthorityError> =>
  Either.left(new Dnrd5V2AuthorityError({ code, detail }))

const IDENTIFIER_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/
const key = (atom: CanonicalAtomV2): string => canonicalAtomV2KeyId(atom.key)
const isIdentifier = (value: unknown): value is string =>
  typeof value === "string" && IDENTIFIER_PATTERN.test(value)
const isCanonicalKeyId = (value: string): boolean => {
  const parts = value.split("|")
  if (
    parts.length !== 4 ||
    !parts.slice(0, 3).every((part) => IDENTIFIER_PATTERN.test(part)) ||
    !/^(?:0|[1-9]\d*)$/.test(parts[3]!)
  ) return false
  const revisionId = Number(parts[3])
  return Number.isSafeInteger(revisionId) && revisionId >= 0
}
const isInstant = (value: string): boolean => {
  const parsed = Date.parse(value)
  return Number.isFinite(parsed) && new Date(parsed).toISOString() === value
}
const bytesEqual = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((value, index) => value === right[index])
const isPlainObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value)
const hasExactKeys = (
  value: object,
  keys: ReadonlyArray<string>
): boolean =>
  Object.keys(value).length === keys.length &&
  keys.every((candidate) => Object.prototype.hasOwnProperty.call(value, candidate))
const isContentShape = (value: unknown): boolean =>
  isPlainObject(value) &&
  hasExactKeys(value, ["atom", "bytes"]) &&
  value["bytes"] instanceof Uint8Array
const isChainShape = (value: unknown): boolean =>
  isPlainObject(value) &&
  hasExactKeys(value, [
    "phase",
    "policy",
    "authorization",
    "capability",
    "revocation",
    "grant"
  ]) &&
  typeof value["phase"] === "string" &&
  isContentShape(value["policy"]) &&
  isContentShape(value["authorization"]) &&
  isContentShape(value["capability"]) &&
  isContentShape(value["revocation"]) &&
  isContentShape(value["grant"])
const isStateShape = (value: unknown): boolean =>
  isPlainObject(value) &&
  hasExactKeys(value, [
    "schemaVersion",
    "revision",
    "bootstrapClosed",
    "atoms",
    "acceptedTransitionIds"
  ])
const isSortedUnique = (values: ReadonlyArray<string>): boolean =>
  values.every((value, index) => index === 0 || values[index - 1]! < value)
const sameAtom = (left: CanonicalAtomV2, right: CanonicalAtomV2): boolean => {
  const leftBytes = canonicalJsonBytes(left)
  const rightBytes = canonicalJsonBytes(right)
  return Either.isRight(leftBytes) &&
    Either.isRight(rightBytes) &&
    bytesEqual(leftBytes.right, rightBytes.right)
}
const hasExactReference = (
  source: CanonicalAtomV2,
  role: string,
  target: CanonicalAtomV2
): boolean =>
  source.references.filter(
    (reference) =>
      reference.referenceType === DNRD5_V2_REFERENCE_TYPE &&
      reference.role === `role:dnrd5:v2:${role}` &&
      canonicalAtomV2KeyId(reference.target) === key(target)
  ).length === 1
const hasExactReferenceClosure = (
  source: CanonicalAtomV2,
  expected: Readonly<Record<string, CanonicalAtomV2>>
): boolean =>
  source.references.length === Object.keys(expected).length &&
  Object.entries(expected).every(([role, target]) =>
    hasExactReference(source, role, target)
  )

interface DecodedContent<A> {
  readonly atom: CanonicalAtomV2
  readonly payload: A
}

const decodeContent = <A>(
  content: Dnrd5V2AuthorityContent,
  kind: string,
  mediaType: string,
  schema: Schema.Schema<A>
): Either.Either<DecodedContent<A>, Dnrd5V2AuthorityError> => {
  const atom = Schema.decodeUnknownEither(CanonicalAtomV2Schema, {
    onExcessProperty: "error"
  })(content.atom)
  if (
    Either.isLeft(atom) ||
    atom.right.key.schemaVersion !== DNRD5_V2_SCHEMA_VERSION ||
    atom.right.kind !== `hswm:dnrd5:v2:${kind}` ||
    atom.right.content.mediaType !== mediaType
  ) {
    return fail("ATOM_INVALID", `expected exact admitted v2 ${kind} atom`)
  }
  if (
    !(content.bytes instanceof Uint8Array) ||
    atom.right.content.byteLength !== content.bytes.byteLength ||
    atom.right.content.sha256 !==
      createHash("sha256").update(content.bytes).digest("hex")
  ) {
    return fail(
      "PAYLOAD_BINDING_INVALID",
      `${kind} descriptor does not bind supplied bytes`
    )
  }
  const raw = decodeCanonicalJsonBytes(content.bytes)
  if (Either.isLeft(raw) || !isPlainObject(raw.right)) {
    return fail("PAYLOAD_INVALID", `${kind} payload is not canonical JSON object`)
  }
  const canonical = canonicalJsonBytes(raw.right)
  if (Either.isLeft(canonical) || !bytesEqual(canonical.right, content.bytes)) {
    return fail(
      "PAYLOAD_INVALID",
      `${kind} payload bytes are not exact canonical JSON`
    )
  }
  const payload = Schema.decodeUnknownEither(schema, {
    onExcessProperty: "error"
  })(raw.right)
  return Either.isLeft(payload)
    ? fail("PAYLOAD_INVALID", `${kind} payload has invalid or excess fields`)
    : Either.right({ atom: atom.right, payload: payload.right })
}

interface CheckedAuthority {
  readonly validated: Dnrd5V2AuthorityValidated
  readonly state: CanonicalAtomV2State
  readonly principals: Dnrd5V2AuthorityPrincipals
  readonly policy: Policy
  readonly authorization: Authorization
  readonly capability: Capability
  readonly revocation: Revocation
  readonly grant: Grant
}

const checkAuthorityChain = (
  input: Dnrd5V2AuthorityStateInput,
  state: CanonicalAtomV2State
): Either.Either<CheckedAuthority, Dnrd5V2AuthorityError> => {
  const policy = decodeContent(
    input.chain.policy,
    "permit_policy",
    DNRD5_V2_PERMIT_POLICY_MEDIA_TYPE,
    PolicyPayload
  )
  if (Either.isLeft(policy)) return Either.left(policy.left)
  const authorization = decodeContent(
    input.chain.authorization,
    "authorization_decision",
    DNRD5_V2_AUTHORIZATION_DECISION_MEDIA_TYPE,
    AuthorizationPayload
  )
  if (Either.isLeft(authorization)) return Either.left(authorization.left)
  const capability = decodeContent(
    input.chain.capability,
    "capability_issuance",
    DNRD5_V2_CAPABILITY_ISSUANCE_MEDIA_TYPE,
    CapabilityPayload
  )
  if (Either.isLeft(capability)) return Either.left(capability.left)
  const revocation = decodeContent(
    input.chain.revocation,
    "revocation_status",
    DNRD5_V2_REVOCATION_STATUS_MEDIA_TYPE,
    RevocationPayload
  )
  if (Either.isLeft(revocation)) return Either.left(revocation.left)
  const grant = decodeContent(
    input.chain.grant,
    "grant_snapshot",
    DNRD5_V2_GRANT_SNAPSHOT_MEDIA_TYPE,
    GrantPayload
  )
  if (Either.isLeft(grant)) return Either.left(grant.left)

  const chainAtoms = [
    policy.right.atom,
    authorization.right.atom,
    capability.right.atom,
    revocation.right.atom,
    grant.right.atom
  ]
  if (
    new Set(chainAtoms.map(key)).size !== chainAtoms.length ||
    !hasExactReferenceClosure(authorization.right.atom, {
      policy: policy.right.atom
    }) ||
    !hasExactReferenceClosure(capability.right.atom, {
      authorization: authorization.right.atom,
      policy: policy.right.atom
    }) ||
    !hasExactReferenceClosure(revocation.right.atom, {
      authorization: authorization.right.atom,
      capability: capability.right.atom
    }) ||
    !hasExactReferenceClosure(grant.right.atom, {
      policy: policy.right.atom,
      authorization: authorization.right.atom,
      capability: capability.right.atom,
      revocation: revocation.right.atom
    })
  ) {
    return fail(
      "REFERENCE_CLOSURE_INVALID",
      "authority typed-reference closure is not exact"
    )
  }

  const p = input.principals
  const policyPayload = policy.right.payload
  const authorizationPayload = authorization.right.payload
  const capabilityPayload = capability.right.payload
  const revocationPayload = revocation.right.payload
  const grantPayload = grant.right.payload
  const keyIds = [
    authorizationPayload.policyAtomKeyId,
    capabilityPayload.purposeAtomKeyId,
    capabilityPayload.policyAtomKeyId,
    capabilityPayload.authorizationAtomKeyId,
    revocationPayload.authorizationAtomKeyId,
    revocationPayload.capabilityAtomKeyId,
    grantPayload.policyAtomKeyId,
    grantPayload.authorizationAtomKeyId,
    grantPayload.capabilityAtomKeyId,
    grantPayload.revocationAtomKeyId
  ]
  if (!keyIds.every(isCanonicalKeyId)) {
    return fail("CHAIN_INVALID", "authority payload contains a non-canonical key id")
  }

  const instants = [
    input.evaluatedAt,
    authorizationPayload.decidedAt,
    authorizationPayload.notBefore,
    authorizationPayload.expiresAt,
    capabilityPayload.issuedAt,
    capabilityPayload.expiresAt,
    revocationPayload.checkedAt
  ]
  if (
    !instants.every(isInstant) ||
    Date.parse(authorizationPayload.decidedAt) >
      Date.parse(authorizationPayload.notBefore) ||
    Date.parse(authorizationPayload.notBefore) > Date.parse(input.evaluatedAt) ||
    Date.parse(input.evaluatedAt) >= Date.parse(authorizationPayload.expiresAt) ||
    Date.parse(capabilityPayload.issuedAt) <
      Date.parse(authorizationPayload.notBefore) ||
    Date.parse(capabilityPayload.issuedAt) > Date.parse(input.evaluatedAt) ||
    Date.parse(input.evaluatedAt) >= Date.parse(capabilityPayload.expiresAt) ||
    Date.parse(capabilityPayload.expiresAt) >
      Date.parse(authorizationPayload.expiresAt) ||
    revocationPayload.checkedAt !== input.evaluatedAt
  ) {
    return fail(
      "TIME_INVALID",
      "authority records are outside their declared interval or snapshot evaluation time"
    )
  }

  if (
    authorizationPayload.actor !== p.actor ||
    authorizationPayload.authorizer !== p.authorizer ||
    authorizationPayload.recordCustodian !== p.authorizationRecordCustodian ||
    [
      p.actor,
      p.canonicalStateCustodian,
      p.restoreCustodian,
      p.creditAdjudicator,
      p.authorizationRecordCustodian
    ].includes(p.authorizer)
  ) {
    return fail(
      "PRINCIPAL_INEQUALITY",
      "the declared authorizer must be exact and separate from actor and state-change custodians"
    )
  }

  if (
    !isSortedUnique(policyPayload.allowedActors) ||
    !isSortedUnique(policyPayload.allowedPhases) ||
    !policyPayload.allowedActors.includes(p.actor) ||
    !policyPayload.allowedPhases.includes(input.chain.phase) ||
    authorizationPayload.scope !== policyPayload.scope ||
    authorizationPayload.phase !== input.chain.phase ||
    authorizationPayload.policyAtomKeyId !== key(policy.right.atom) ||
    authorizationPayload.policyGeneration !== policyPayload.generation ||
    capabilityPayload.scope !== policyPayload.scope ||
    capabilityPayload.actor !== p.actor ||
    capabilityPayload.phase !== input.chain.phase ||
    capabilityPayload.policyAtomKeyId !== key(policy.right.atom) ||
    capabilityPayload.policyGeneration !== policyPayload.generation ||
    capabilityPayload.authorizationAtomKeyId !== key(authorization.right.atom) ||
    capabilityPayload.authorizationRef !== authorizationPayload.authorizationRef ||
    capabilityPayload.authorizationGeneration !== authorizationPayload.generation ||
    revocationPayload.authorizationAtomKeyId !== key(authorization.right.atom) ||
    revocationPayload.authorizationRef !== authorizationPayload.authorizationRef ||
    revocationPayload.capabilityAtomKeyId !== key(capability.right.atom) ||
    revocationPayload.capabilityId !== capabilityPayload.capabilityId ||
    revocationPayload.policyGeneration !== policyPayload.generation ||
    revocationPayload.authorizationGeneration !== authorizationPayload.generation ||
    revocationPayload.capabilityGeneration !== capabilityPayload.generation ||
    grantPayload.policyAtomKeyId !== key(policy.right.atom) ||
    grantPayload.authorizationAtomKeyId !== key(authorization.right.atom) ||
    grantPayload.authorizationRef !== authorizationPayload.authorizationRef ||
    grantPayload.capabilityAtomKeyId !== key(capability.right.atom) ||
    grantPayload.capabilityId !== capabilityPayload.capabilityId ||
    grantPayload.revocationAtomKeyId !== key(revocation.right.atom) ||
    grantPayload.policyGeneration !== policyPayload.generation ||
    grantPayload.authorizationGeneration !== authorizationPayload.generation ||
    grantPayload.capabilityGeneration !== capabilityPayload.generation
  ) {
    return fail(
      "CHAIN_INVALID",
      "policy, authorization, capability, revocation, and grant semantic closure is not exact"
    )
  }

  if (
    !chainAtoms.every((atom) =>
      state.atoms.some((actual) => key(actual) === key(atom) && sameAtom(actual, atom))
    )
  ) {
    return fail(
      "SNAPSHOT_MEMBERSHIP_INVALID",
      "authority atom is not the exact atom in the supplied validated state"
    )
  }

  const purpose = state.atoms.find(
    (atom) => key(atom) === capabilityPayload.purposeAtomKeyId
  )
  const expectedPurposeKind =
    input.chain.phase === "MAIN_ADMIT" || input.chain.phase === "RECEIPT_ADMIT"
      ? "hswm:dnrd5:v2:revision_admission_decision"
      : "hswm:dnrd5:v2:rollback_decision"
  if (purpose === undefined || purpose.kind !== expectedPurposeKind) {
    return fail(
      "PURPOSE_INVALID",
      "capability purpose must be the exact phase-appropriate decision atom in the supplied state"
    )
  }
  if (
    (input.chain.phase === "MAIN_ADMIT" || input.chain.phase === "MAIN_RESTORE") &&
    (!hasExactReference(purpose, "grant", grant.right.atom) ||
      !hasExactReference(purpose, "authorization", authorization.right.atom) ||
      !hasExactReference(purpose, "capability", capability.right.atom) ||
      !hasExactReference(purpose, "revocation", revocation.right.atom))
  ) {
    return fail(
      "PURPOSE_INVALID",
      "main authority chain must be the exact authority closure referenced by its decision"
    )
  }

  const revocationsForCapability = state.atoms.filter(
    (atom) =>
      atom.kind === "hswm:dnrd5:v2:revocation_status" &&
      atom.references.some(
        (reference) =>
          reference.referenceType === DNRD5_V2_REFERENCE_TYPE &&
          reference.role === "role:dnrd5:v2:capability" &&
          canonicalAtomV2KeyId(reference.target) === key(capability.right.atom)
      )
  )
  if (
    revocationsForCapability.length !== 1 ||
    key(revocationsForCapability[0]!) !== key(revocation.right.atom)
  ) {
    return fail(
      "SNAPSHOT_MEMBERSHIP_INVALID",
      "the supplied state must contain exactly one status atom for this capability"
    )
  }

  const stateSha256 = canonicalAtomV2StateSha256(state)
  if (Either.isLeft(stateSha256)) {
    return fail("STATE_INVALID", "validated state cannot be canonically committed")
  }
  const validated = deepFreeze({
    _tag: "Dnrd5V2AuthorityValidated",
    contractVersion: DNRD5_V2_AUTHORITY_PAYLOAD_V1,
    status:
      "STRUCTURAL_AUTHORITY_PAYLOAD_AT_CALLER_STATE_NOT_RECOVERY_OR_PERMIT",
    evaluatedAt: input.evaluatedAt,
    stateRevision: state.revision,
    stateSha256: stateSha256.right,
    chain: {
      phase: input.chain.phase,
      scope: policyPayload.scope,
      actor: p.actor,
      purposeAtomKeyId: capabilityPayload.purposeAtomKeyId,
      policyAtomKeyId: key(policy.right.atom),
      authorizationAtomKeyId: key(authorization.right.atom),
      capabilityAtomKeyId: key(capability.right.atom),
      revocationAtomKeyId: key(revocation.right.atom),
      grantAtomKeyId: key(grant.right.atom),
      authorizationRef: authorizationPayload.authorizationRef,
      capabilityId: capabilityPayload.capabilityId,
      nonceSha256: capabilityPayload.nonceSha256
    },
    terminal:
      "NOT_DURABLE_RECOVERY_NOT_EXTERNAL_AUTHORITY_NOT_CAS_NOT_OCCURRENCE_NOT_LEARNING_NOT_EFFICACY"
  } satisfies Dnrd5V2AuthorityValidated)
  return Either.right({
    validated,
    state,
    principals: input.principals,
    policy: policyPayload,
    authorization: authorizationPayload,
    capability: capabilityPayload,
    revocation: revocationPayload,
    grant: grantPayload
  })
}

export interface Dnrd5V2AuthorityValidated {
  readonly _tag: "Dnrd5V2AuthorityValidated"
  readonly contractVersion: typeof DNRD5_V2_AUTHORITY_PAYLOAD_V1
  readonly status: "STRUCTURAL_AUTHORITY_PAYLOAD_AT_CALLER_STATE_NOT_RECOVERY_OR_PERMIT"
  readonly evaluatedAt: string
  readonly stateRevision: number
  readonly stateSha256: string
  readonly chain: {
    readonly phase: Dnrd5V2AuthorityPhase
    readonly scope: string
    readonly actor: string
    readonly purposeAtomKeyId: string
    readonly policyAtomKeyId: string
    readonly authorizationAtomKeyId: string
    readonly capabilityAtomKeyId: string
    readonly revocationAtomKeyId: string
    readonly grantAtomKeyId: string
    readonly authorizationRef: string
    readonly capabilityId: string
    readonly nonceSha256: string
  }
  readonly terminal: "NOT_DURABLE_RECOVERY_NOT_EXTERNAL_AUTHORITY_NOT_CAS_NOT_OCCURRENCE_NOT_LEARNING_NOT_EFFICACY"
}

export interface Dnrd5V2AuthorityPairValidated {
  readonly _tag: "Dnrd5V2AuthorityPairValidated"
  readonly contractVersion: typeof DNRD5_V2_AUTHORITY_PAYLOAD_V1
  readonly status: "STRUCTURAL_APPEND_ONLY_STATE_PAIR_AND_DISJOINT_AUTHORITY_NOT_CAS"
  readonly main: Dnrd5V2AuthorityValidated
  readonly evidence: Dnrd5V2AuthorityValidated
  readonly terminal: "NOT_EXACT_CAS1_RESULT_NOT_DURABLE_RECOVERY_NOT_PERMIT_NOT_OCCURRENCE_NOT_LEARNING_NOT_EFFICACY"
}

const deepFreeze = <A>(value: A): A => {
  if (typeof value === "object" && value !== null && !Object.isFrozen(value)) {
    Object.freeze(value)
    for (const nested of Object.values(value)) deepFreeze(nested)
  }
  return value
}

const validateInternal = (
  input: unknown
): Either.Either<CheckedAuthority, Dnrd5V2AuthorityError> => {
  if (
    !isPlainObject(input) ||
    !hasExactKeys(input, [
      "_tag",
      "contractVersion",
      "evaluatedAt",
      "principals",
      "state",
      "chain"
    ]) ||
    input["_tag"] !== "Dnrd5V2AuthorityStateInput" ||
    input["contractVersion"] !== DNRD5_V2_AUTHORITY_PAYLOAD_V1 ||
    !isPlainObject(input["principals"]) ||
    !hasExactKeys(input["principals"], [
      "actor",
      "authorizer",
      "canonicalStateCustodian",
      "restoreCustodian",
      "creditAdjudicator",
      "authorizationRecordCustodian"
    ]) ||
    !Object.values(input["principals"]).every(isIdentifier) ||
    !isStateShape(input["state"]) ||
    !isChainShape(input["chain"])
  ) {
    return fail("INPUT_INVALID", "input is not the exact v2 authority-state contract")
  }
  const value = input as unknown as Dnrd5V2AuthorityStateInput
  if (
    value.chain.phase !== "MAIN_ADMIT" &&
    value.chain.phase !== "MAIN_RESTORE" &&
    value.chain.phase !== "RECEIPT_ADMIT" &&
    value.chain.phase !== "RECEIPT_RESTORE"
  ) {
    return fail("CHAIN_INVALID", "invalid authority phase")
  }
  const state = validateCanonicalAtomV2State(
    makeDnrd5V2CanonicalSchema(),
    value.state
  )
  if (Either.isLeft(state)) {
    return fail("STATE_INVALID", state.left.detail)
  }
  return checkAuthorityChain(value, state.right)
}

export const validateDnrd5V2AuthorityPayloadAtState = (
  input: unknown
): Either.Either<Dnrd5V2AuthorityValidated, Dnrd5V2AuthorityError> => {
  try {
    const checked = validateInternal(input)
    return Either.isLeft(checked)
      ? Either.left(checked.left)
      : Either.right(checked.right.validated)
  } catch {
    return fail("INPUT_INVALID", "authority-state input could not be safely inspected")
  }
}

const samePrincipals = (
  left: Dnrd5V2AuthorityPrincipals,
  right: Dnrd5V2AuthorityPrincipals
): boolean =>
  left.actor === right.actor &&
  left.authorizer === right.authorizer &&
  left.canonicalStateCustodian === right.canonicalStateCustodian &&
  left.restoreCustodian === right.restoreCustodian &&
  left.creditAdjudicator === right.creditAdjudicator &&
  left.authorizationRecordCustodian === right.authorizationRecordCustodian

const isAppendOnlySuccessor = (
  before: CanonicalAtomV2State,
  after: CanonicalAtomV2State
): boolean => {
  if (
    after.revision !== before.revision + 1 ||
    after.acceptedTransitionIds.length !== before.acceptedTransitionIds.length + 1 ||
    !before.acceptedTransitionIds.every(
      (transitionId, index) => after.acceptedTransitionIds[index] === transitionId
    ) ||
    after.atoms.length <= before.atoms.length
  ) return false
  return before.atoms.every((atom) =>
    after.atoms.some(
      (candidate) => key(candidate) === key(atom) && sameAtom(candidate, atom)
    )
  )
}

export const validateDnrd5V2AuthorityDisjointPair = (
  mainInput: unknown,
  evidenceInput: unknown
): Either.Either<Dnrd5V2AuthorityPairValidated, Dnrd5V2AuthorityError> => {
  try {
    const main = validateInternal(mainInput)
    if (Either.isLeft(main)) return Either.left(main.left)
    const evidence = validateInternal(evidenceInput)
    if (Either.isLeft(evidence)) return Either.left(evidence.left)

    const mainPhase = main.right.validated.chain.phase
    const evidencePhase = evidence.right.validated.chain.phase
    const expectedEvidencePhase = mainPhase === "MAIN_ADMIT"
      ? "RECEIPT_ADMIT"
      : mainPhase === "MAIN_RESTORE"
        ? "RECEIPT_RESTORE"
        : undefined
    if (expectedEvidencePhase === undefined || evidencePhase !== expectedEvidencePhase) {
      return fail(
        "CHAIN_INVALID",
        "pair must contain a corresponding MAIN then RECEIPT phase"
      )
    }

    if (
      !samePrincipals(main.right.principals, evidence.right.principals) ||
      main.right.capability.actor !== evidence.right.capability.actor ||
      main.right.capability.scope !== evidence.right.capability.scope ||
      main.right.capability.purposeAtomKeyId !==
        evidence.right.capability.purposeAtomKeyId
    ) {
      return fail(
        "CHAIN_INVALID",
        "main and evidence authority must bind the same principals, actor, scope, and purpose"
      )
    }

    const mainIds = [
      main.right.validated.chain.authorizationAtomKeyId,
      main.right.validated.chain.capabilityAtomKeyId,
      main.right.validated.chain.revocationAtomKeyId,
      main.right.validated.chain.grantAtomKeyId
    ]
    const evidenceIds = [
      evidence.right.validated.chain.authorizationAtomKeyId,
      evidence.right.validated.chain.capabilityAtomKeyId,
      evidence.right.validated.chain.revocationAtomKeyId,
      evidence.right.validated.chain.grantAtomKeyId
    ]
    if (
      mainIds.some((id) => evidenceIds.includes(id)) ||
      main.right.authorization.authorizationRef ===
        evidence.right.authorization.authorizationRef ||
      main.right.capability.capabilityId === evidence.right.capability.capabilityId ||
      main.right.capability.nonceSha256 === evidence.right.capability.nonceSha256
    ) {
      return fail(
        "CHAIN_REUSE_INVALID",
        "main and evidence authorization records, references, capabilities, and nonces must be distinct"
      )
    }

    if (
      main.right.validated.chain.policyAtomKeyId ===
        evidence.right.validated.chain.policyAtomKeyId &&
      (!main.right.policy.allowMainReceiptPairing ||
        !evidence.right.policy.allowMainReceiptPairing)
    ) {
      return fail(
        "CHAIN_REUSE_INVALID",
        "a shared policy must explicitly allow main/receipt pairing"
      )
    }

    if (
      Date.parse(evidence.right.validated.evaluatedAt) <
        Date.parse(main.right.validated.evaluatedAt) ||
      !isAppendOnlySuccessor(main.right.state, evidence.right.state)
    ) {
      return fail(
        "SEQUENCE_INVALID",
        "evidence state must be a one-revision append-only successor with nondecreasing evaluation time"
      )
    }

    return Either.right(deepFreeze({
      _tag: "Dnrd5V2AuthorityPairValidated",
      contractVersion: DNRD5_V2_AUTHORITY_PAYLOAD_V1,
      status: "STRUCTURAL_APPEND_ONLY_STATE_PAIR_AND_DISJOINT_AUTHORITY_NOT_CAS",
      main: main.right.validated,
      evidence: evidence.right.validated,
      terminal:
        "NOT_EXACT_CAS1_RESULT_NOT_DURABLE_RECOVERY_NOT_PERMIT_NOT_OCCURRENCE_NOT_LEARNING_NOT_EFFICACY"
    } satisfies Dnrd5V2AuthorityPairValidated))
  } catch {
    return fail("INPUT_INVALID", "authority pair input could not be safely inspected")
  }
}
