import {
  createHash,
  createPublicKey,
  verify as verifySignature
} from "node:crypto"

import { Data, Either, Schema } from "effect"

import {
  canonicalJsonBytes,
  decodeCanonicalJsonBytes
} from "./canonical-atom-v2-json.js"

/**
 * Read-only authentication envelope for one exact candidate transition.
 *
 * This module can verify a detached signature and exact field matches only
 * against caller-supplied expected bindings, trust bytes, and time. It cannot
 * establish authoritative issuance, consume a nonce, establish a storage
 * linearization point, admit a revision, establish outcome truth, or establish
 * learning.
 */
export const HSWM_CANONICAL_PERMIT_ENVELOPE_V1_CONTRACT_VERSION =
  "hswm-canonical-permit-envelope/v1" as const
export const HSWM_CANONICAL_PERMIT_TRUST_SNAPSHOT_V1_CONTRACT_VERSION =
  "hswm-canonical-permit-trust-snapshot/v1" as const
export const HSWM_CANONICAL_PERMIT_ENVELOPE_V1_MEDIA_TYPE =
  "application/vnd.hswm.canonical-permit-envelope-v1+json" as const
export const HSWM_CANONICAL_PERMIT_SIGNING_DOMAIN =
  "HSWM_CANONICAL_PERMIT_V1" as const
export const HSWM_CANONICAL_PERMIT_PAYLOAD_TYPE =
  "application/vnd.hswm.canonical-permit-claims-v1+json" as const
export const HSWM_CANONICAL_PERMIT_CANONICALIZATION =
  "hswm-canonical-json/v1" as const
export const HSWM_CANONICAL_PERMIT_SIGNATURE_ALGORITHM =
  "Ed25519" as const
export const HSWM_CANONICAL_PERMIT_ENVELOPE_STATUS =
  "SIGNED_AUTHORIZATION_ENVELOPE_NOT_ATOMIC_ADMISSION_NOT_LEARNING" as const
export const HSWM_CANONICAL_PERMIT_CALLER_CONTEXT_VERIFICATION_STATUS =
  "CALLER_RELATIVE_BINDINGS_TRUST_AND_TIME_ENVELOPE_VERIFIED_NOT_AUTHORITATIVE_PERMIT_NOT_ATOMIC_ADMISSION_NOT_LEARNING" as const
export const HSWM_CANONICAL_PERMIT_TRUST_STATUS =
  "CALLER_SUPPLIED_TRUST_SNAPSHOT_NOT_TRANSPARENCY_LOG" as const

const Identifier = Schema.String.pipe(
  Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/)
)
const CanonicalInstant = Schema.String.pipe(
  Schema.pattern(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/)
)
const Sha256 = Schema.String.pipe(Schema.pattern(/^[0-9a-f]{64}$/))
const Base64Url = Schema.String.pipe(
  Schema.pattern(/^[A-Za-z0-9_-]+$/),
  Schema.maxLength(4096)
)
const SafeInteger = Schema.Number.pipe(
  Schema.int(),
  Schema.nonNegative(),
  Schema.lessThanOrEqualTo(Number.MAX_SAFE_INTEGER)
)

export interface CanonicalPermitHeadBinding {
  readonly lineageId: string
  readonly sequence: number
  readonly stateDigest: string
  readonly recordDigest: string
}

export const CanonicalPermitHeadBindingSchema: Schema.Schema<CanonicalPermitHeadBinding> =
  Schema.Struct({
    lineageId: Identifier,
    sequence: SafeInteger,
    stateDigest: Sha256,
    recordDigest: Sha256
  })

export interface CanonicalPermitTargetBinding {
  readonly schemaVersion: string
  readonly lineageId: string
  readonly atomUid: string
}

export const CanonicalPermitTargetBindingSchema: Schema.Schema<CanonicalPermitTargetBinding> =
  Schema.Struct({
    schemaVersion: Identifier,
    lineageId: Identifier,
    atomUid: Identifier
  })

export interface CanonicalPermitEnvelopeHeader {
  readonly domain: typeof HSWM_CANONICAL_PERMIT_SIGNING_DOMAIN
  readonly contractVersion: typeof HSWM_CANONICAL_PERMIT_ENVELOPE_V1_CONTRACT_VERSION
  readonly canonicalization: typeof HSWM_CANONICAL_PERMIT_CANONICALIZATION
  readonly algorithm: typeof HSWM_CANONICAL_PERMIT_SIGNATURE_ALGORITHM
  readonly keyId: string
  readonly payloadType: typeof HSWM_CANONICAL_PERMIT_PAYLOAD_TYPE
}

export const CanonicalPermitEnvelopeHeaderSchema: Schema.Schema<CanonicalPermitEnvelopeHeader> =
  Schema.Struct({
    domain: Schema.Literal(HSWM_CANONICAL_PERMIT_SIGNING_DOMAIN),
    contractVersion: Schema.Literal(
      HSWM_CANONICAL_PERMIT_ENVELOPE_V1_CONTRACT_VERSION
    ),
    canonicalization: Schema.Literal(HSWM_CANONICAL_PERMIT_CANONICALIZATION),
    algorithm: Schema.Literal(HSWM_CANONICAL_PERMIT_SIGNATURE_ALGORITHM),
    keyId: Identifier,
    payloadType: Schema.Literal(HSWM_CANONICAL_PERMIT_PAYLOAD_TYPE)
  })

export interface CanonicalPermitClaims {
  readonly permitId: string
  readonly executionId: string
  /** Digest of the pre-execution intent, never the final signed receipt. */
  readonly executionIntentDigest: string
  readonly permitDigest: string
  readonly proposalDigest: string
  readonly transitionInvariantDigest: string
  readonly priorHead: CanonicalPermitHeadBinding
  readonly expectedNextHead: CanonicalPermitHeadBinding
  readonly target: CanonicalPermitTargetBinding
  readonly expectedRevision: string
  readonly candidateRevision: string
  readonly authorizationRef: string
  readonly authorizer: string
  readonly scope: string
  readonly nonceDigest: string
  readonly keyPolicyVersion: string
  readonly revocationEpoch: number
  readonly linearizationIndex: number
  readonly issuedAt: string
  readonly notBefore: string
  readonly expiresAt: string
}

export const CanonicalPermitClaimsSchema: Schema.Schema<CanonicalPermitClaims> =
  Schema.Struct({
    permitId: Identifier,
    executionId: Identifier,
    executionIntentDigest: Sha256,
    permitDigest: Sha256,
    proposalDigest: Sha256,
    transitionInvariantDigest: Sha256,
    priorHead: CanonicalPermitHeadBindingSchema,
    expectedNextHead: CanonicalPermitHeadBindingSchema,
    target: CanonicalPermitTargetBindingSchema,
    expectedRevision: Identifier,
    candidateRevision: Identifier,
    authorizationRef: Identifier,
    authorizer: Identifier,
    scope: Identifier,
    nonceDigest: Sha256,
    keyPolicyVersion: Identifier,
    revocationEpoch: SafeInteger,
    linearizationIndex: SafeInteger,
    issuedAt: CanonicalInstant,
    notBefore: CanonicalInstant,
    expiresAt: CanonicalInstant
  })

export interface CanonicalPermitSigningDocument {
  readonly _tag: "CanonicalPermitSigningDocument"
  readonly header: CanonicalPermitEnvelopeHeader
  readonly claims: CanonicalPermitClaims
  readonly status: typeof HSWM_CANONICAL_PERMIT_ENVELOPE_STATUS
}

export const CanonicalPermitSigningDocumentSchema: Schema.Schema<CanonicalPermitSigningDocument> =
  Schema.Struct({
    _tag: Schema.Literal("CanonicalPermitSigningDocument"),
    header: CanonicalPermitEnvelopeHeaderSchema,
    claims: CanonicalPermitClaimsSchema,
    status: Schema.Literal(HSWM_CANONICAL_PERMIT_ENVELOPE_STATUS)
  })

export interface CanonicalPermitEnvelope extends CanonicalPermitSigningDocument {
  readonly signature: string
}

export const CanonicalPermitEnvelopeSchema: Schema.Schema<CanonicalPermitEnvelope> =
  Schema.Struct({
    _tag: Schema.Literal("CanonicalPermitSigningDocument"),
    header: CanonicalPermitEnvelopeHeaderSchema,
    claims: CanonicalPermitClaimsSchema,
    status: Schema.Literal(HSWM_CANONICAL_PERMIT_ENVELOPE_STATUS),
    signature: Base64Url
  })

export interface CanonicalPermitTrustedKey {
  readonly keyId: string
  readonly algorithm: typeof HSWM_CANONICAL_PERMIT_SIGNATURE_ALGORITHM
  readonly publicKeySpkiDerBase64Url: string
  readonly authorizedAuthorizer: string
  readonly notBefore: string
  readonly expiresAt: string
  readonly status: "ACTIVE" | "REVOKED"
  readonly revokedAt: string | null
}

export const CanonicalPermitTrustedKeySchema: Schema.Schema<CanonicalPermitTrustedKey> =
  Schema.Struct({
    keyId: Identifier,
    algorithm: Schema.Literal(HSWM_CANONICAL_PERMIT_SIGNATURE_ALGORITHM),
    publicKeySpkiDerBase64Url: Base64Url,
    authorizedAuthorizer: Identifier,
    notBefore: CanonicalInstant,
    expiresAt: CanonicalInstant,
    status: Schema.Literal("ACTIVE", "REVOKED"),
    revokedAt: Schema.NullOr(CanonicalInstant)
  })

export interface CanonicalPermitTrustSnapshot {
  readonly _tag: "CanonicalPermitTrustSnapshot"
  readonly contractVersion: typeof HSWM_CANONICAL_PERMIT_TRUST_SNAPSHOT_V1_CONTRACT_VERSION
  readonly policyVersion: string
  readonly revocationEpoch: number
  readonly snapshotAt: string
  readonly keys: ReadonlyArray<CanonicalPermitTrustedKey>
  readonly status: typeof HSWM_CANONICAL_PERMIT_TRUST_STATUS
}

export const CanonicalPermitTrustSnapshotSchema: Schema.Schema<CanonicalPermitTrustSnapshot> =
  Schema.Struct({
    _tag: Schema.Literal("CanonicalPermitTrustSnapshot"),
    contractVersion: Schema.Literal(
      HSWM_CANONICAL_PERMIT_TRUST_SNAPSHOT_V1_CONTRACT_VERSION
    ),
    policyVersion: Identifier,
    revocationEpoch: SafeInteger,
    snapshotAt: CanonicalInstant,
    keys: Schema.Array(CanonicalPermitTrustedKeySchema).pipe(
      Schema.minItems(1),
      Schema.maxItems(64)
    ),
    status: Schema.Literal(HSWM_CANONICAL_PERMIT_TRUST_STATUS)
  })

export interface CanonicalPermitExpectedBindings {
  readonly permitId: string
  readonly executionId: string
  readonly executionIntentDigest: string
  readonly permitDigest: string
  readonly proposalDigest: string
  readonly transitionInvariantDigest: string
  readonly priorHead: CanonicalPermitHeadBinding
  readonly expectedNextHead: CanonicalPermitHeadBinding
  readonly target: CanonicalPermitTargetBinding
  readonly expectedRevision: string
  readonly candidateRevision: string
  readonly authorizationRef: string
  readonly authorizer: string
  readonly scope: string
  readonly nonceDigest: string
  readonly keyPolicyVersion: string
  readonly revocationEpoch: number
  readonly linearizationIndex: number
}

export const CanonicalPermitExpectedBindingsSchema: Schema.Schema<CanonicalPermitExpectedBindings> =
  Schema.Struct({
    permitId: Identifier,
    executionId: Identifier,
    executionIntentDigest: Sha256,
    permitDigest: Sha256,
    proposalDigest: Sha256,
    transitionInvariantDigest: Sha256,
    priorHead: CanonicalPermitHeadBindingSchema,
    expectedNextHead: CanonicalPermitHeadBindingSchema,
    target: CanonicalPermitTargetBindingSchema,
    expectedRevision: Identifier,
    candidateRevision: Identifier,
    authorizationRef: Identifier,
    authorizer: Identifier,
    scope: Identifier,
    nonceDigest: Sha256,
    keyPolicyVersion: Identifier,
    revocationEpoch: SafeInteger,
    linearizationIndex: SafeInteger
  })

export type CanonicalPermitEnvelopeErrorCode =
  | "CANONICAL_ENCODING_INVALID"
  | "ENVELOPE_SCHEMA_INVALID"
  | "ENVELOPE_BYTES_NONCANONICAL"
  | "SIGNER_FAILED"
  | "SIGNATURE_FORMAT_INVALID"
  | "SIGNATURE_INVALID"
  | "TRUST_SNAPSHOT_INVALID"
  | "TRUST_KEY_DUPLICATE"
  | "TRUST_KEY_UNKNOWN"
  | "TRUST_KEY_INACTIVE"
  | "KEY_POLICY_MISMATCH"
  | "AUTHORIZER_MISMATCH"
  | "TIME_INVALID"
  | "TRANSITION_INVALID"
  | "BINDING_MISMATCH"

export class CanonicalPermitEnvelopeError extends Data.TaggedError(
  "CanonicalPermitEnvelopeError"
)<{
  readonly code: CanonicalPermitEnvelopeErrorCode
  readonly detail: string
}> {}

/** Detached-signature byte assembly; not evidence of authoritative issuance. */
export interface AssembledCanonicalPermitEnvelope {
  readonly envelope: CanonicalPermitEnvelope
  readonly signingBytes: Uint8Array
  readonly envelopeBytes: Uint8Array
  readonly signingBytesSha256: string
  readonly envelopeBytesSha256: string
}

/**
 * A cryptographic result relative only to the caller-provided expected
 * bindings, trust bytes, and verification time passed to the verifier. It is
 * deliberately not an authoritative Permit, a freshness assertion, or an
 * admission receipt.
 */
export interface CallerRelativeCanonicalPermitEnvelopeVerification {
  readonly envelope: CanonicalPermitEnvelope
  readonly envelopeBytesSha256: string
  readonly signingBytesSha256: string
  readonly callerSuppliedExpectedBindingsSha256: string
  readonly callerSuppliedTrustSnapshotSha256: string
  readonly callerSuppliedPublicKeySpkiSha256: string
  readonly callerSuppliedVerificationTime: string
  readonly callerSuppliedTrustPolicyVersion: string
  readonly callerSuppliedTrustRevocationEpoch: number
  readonly callerSuppliedTrustedKeyId: string
  readonly trustStatus: typeof HSWM_CANONICAL_PERMIT_TRUST_STATUS
  readonly status: typeof HSWM_CANONICAL_PERMIT_CALLER_CONTEXT_VERIFICATION_STATUS
}

export type CanonicalPermitDetachedSigner = (
  signingBytes: Uint8Array
) => Uint8Array

const fail = (
  code: CanonicalPermitEnvelopeErrorCode,
  detail: string
): Either.Either<never, CanonicalPermitEnvelopeError> =>
  Either.left(new CanonicalPermitEnvelopeError({ code, detail }))

const sha256 = (bytes: Uint8Array): string =>
  createHash("sha256").update(bytes).digest("hex")

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((byte, index) => byte === right[index])

const sameHead = (
  left: CanonicalPermitHeadBinding,
  right: CanonicalPermitHeadBinding
): boolean =>
  left.lineageId === right.lineageId &&
  left.sequence === right.sequence &&
  left.stateDigest === right.stateDigest &&
  left.recordDigest === right.recordDigest

const sameTarget = (
  left: CanonicalPermitTargetBinding,
  right: CanonicalPermitTargetBinding
): boolean =>
  left.schemaVersion === right.schemaVersion &&
  left.lineageId === right.lineageId &&
  left.atomUid === right.atomUid

const snapshotHead = (
  head: CanonicalPermitHeadBinding
): CanonicalPermitHeadBinding => Object.freeze({ ...head })

const snapshotTarget = (
  target: CanonicalPermitTargetBinding
): CanonicalPermitTargetBinding => Object.freeze({ ...target })

const snapshotClaims = (claims: CanonicalPermitClaims): CanonicalPermitClaims =>
  Object.freeze({
    ...claims,
    priorHead: snapshotHead(claims.priorHead),
    expectedNextHead: snapshotHead(claims.expectedNextHead),
    target: snapshotTarget(claims.target)
  })

const snapshotHeader = (
  header: CanonicalPermitEnvelopeHeader
): CanonicalPermitEnvelopeHeader => Object.freeze({ ...header })

const snapshotEnvelope = (
  envelope: CanonicalPermitEnvelope
): CanonicalPermitEnvelope =>
  Object.freeze({
    ...envelope,
    header: snapshotHeader(envelope.header),
    claims: snapshotClaims(envelope.claims)
  })

const decodeExact = <A>(
  schema: Schema.Schema<A>,
  input: unknown,
  code: "ENVELOPE_SCHEMA_INVALID" | "TRUST_SNAPSHOT_INVALID",
  detail: string
): Either.Either<A, CanonicalPermitEnvelopeError> => {
  const decoded = Schema.decodeUnknownEither(schema, {
    onExcessProperty: "error"
  })(input)
  return Either.isLeft(decoded) ? fail(code, detail) : Either.right(decoded.right)
}

const makeSigningDocument = (
  claims: CanonicalPermitClaims,
  keyId: string
): CanonicalPermitSigningDocument =>
  Object.freeze({
    _tag: "CanonicalPermitSigningDocument",
    header: Object.freeze({
      domain: HSWM_CANONICAL_PERMIT_SIGNING_DOMAIN,
      contractVersion: HSWM_CANONICAL_PERMIT_ENVELOPE_V1_CONTRACT_VERSION,
      canonicalization: HSWM_CANONICAL_PERMIT_CANONICALIZATION,
      algorithm: HSWM_CANONICAL_PERMIT_SIGNATURE_ALGORITHM,
      keyId,
      payloadType: HSWM_CANONICAL_PERMIT_PAYLOAD_TYPE
    }),
    claims: snapshotClaims(claims),
    status: HSWM_CANONICAL_PERMIT_ENVELOPE_STATUS
  })

const validateTransition = (
  claims: CanonicalPermitClaims
): Either.Either<void, CanonicalPermitEnvelopeError> => {
  if (claims.expectedRevision === claims.candidateRevision) {
    return fail(
      "TRANSITION_INVALID",
      "candidate revision must differ from the expected revision"
    )
  }
  if (claims.priorHead.lineageId !== claims.expectedNextHead.lineageId) {
    return fail(
      "TRANSITION_INVALID",
      "prior and expected successor heads must share one lineage"
    )
  }
  if (
    claims.priorHead.sequence >= Number.MAX_SAFE_INTEGER ||
    claims.expectedNextHead.sequence !== claims.priorHead.sequence + 1
  ) {
    return fail(
      "TRANSITION_INVALID",
      "expected successor head must be the next safe sequence"
    )
  }
  return Either.right(undefined)
}

const isRealCanonicalInstant = (value: string): boolean => {
  const milliseconds = Date.parse(value)
  return Number.isFinite(milliseconds) &&
    new Date(milliseconds).toISOString() === value
}

const validateClaimChronology = (
  claims: CanonicalPermitClaims
): Either.Either<void, CanonicalPermitEnvelopeError> => {
  if (
    !isRealCanonicalInstant(claims.issuedAt) ||
    !isRealCanonicalInstant(claims.notBefore) ||
    !isRealCanonicalInstant(claims.expiresAt)
  ) {
    return fail("TIME_INVALID", "Permit contains a nonexistent UTC instant")
  }
  return claims.issuedAt <= claims.notBefore && claims.notBefore < claims.expiresAt
    ? Either.right(undefined)
    : fail(
        "TIME_INVALID",
        "Permit issue, not-before, and expiry times are not strictly ordered"
      )
}

const validateClaimTimes = (
  claims: CanonicalPermitClaims,
  verifiedAt: string
): Either.Either<void, CanonicalPermitEnvelopeError> => {
  const chronology = validateClaimChronology(claims)
  if (Either.isLeft(chronology)) return Either.left(chronology.left)
  return claims.notBefore <= verifiedAt && verifiedAt < claims.expiresAt
    ? Either.right(undefined)
    : fail(
        "TIME_INVALID",
        "Permit is not active at the caller-supplied verification time"
      )
}

const strictBase64UrlBytes = (
  encoded: string
): Either.Either<Uint8Array, CanonicalPermitEnvelopeError> => {
  try {
    const decoded = Buffer.from(encoded, "base64url")
    return decoded.byteLength > 0 && decoded.toString("base64url") === encoded
      ? Either.right(Uint8Array.from(decoded))
      : fail("SIGNATURE_FORMAT_INVALID", "base64url value is not minimally encoded")
  } catch {
    return fail("SIGNATURE_FORMAT_INVALID", "base64url value could not be decoded")
  }
}

const exactBindings = (
  claims: CanonicalPermitClaims,
  expected: CanonicalPermitExpectedBindings
): string | null => {
  const scalarBindings: ReadonlyArray<readonly [string, string | number, string | number]> = [
    ["permitId", claims.permitId, expected.permitId],
    ["executionId", claims.executionId, expected.executionId],
    ["executionIntentDigest", claims.executionIntentDigest, expected.executionIntentDigest],
    ["permitDigest", claims.permitDigest, expected.permitDigest],
    ["proposalDigest", claims.proposalDigest, expected.proposalDigest],
    ["transitionInvariantDigest", claims.transitionInvariantDigest, expected.transitionInvariantDigest],
    ["expectedRevision", claims.expectedRevision, expected.expectedRevision],
    ["candidateRevision", claims.candidateRevision, expected.candidateRevision],
    ["authorizationRef", claims.authorizationRef, expected.authorizationRef],
    ["authorizer", claims.authorizer, expected.authorizer],
    ["scope", claims.scope, expected.scope],
    ["nonceDigest", claims.nonceDigest, expected.nonceDigest],
    ["keyPolicyVersion", claims.keyPolicyVersion, expected.keyPolicyVersion],
    ["revocationEpoch", claims.revocationEpoch, expected.revocationEpoch],
    ["linearizationIndex", claims.linearizationIndex, expected.linearizationIndex]
  ]
  const mismatch = scalarBindings.find(([, actual, wanted]) => actual !== wanted)
  if (mismatch !== undefined) return mismatch[0]
  if (!sameHead(claims.priorHead, expected.priorHead)) return "priorHead"
  if (!sameHead(claims.expectedNextHead, expected.expectedNextHead)) {
    return "expectedNextHead"
  }
  return sameTarget(claims.target, expected.target) ? null : "target"
}

interface PreparedPermitSigningDocument {
  readonly document: CanonicalPermitSigningDocument
  readonly bytes: Uint8Array
}

const preparePermitSigningDocument = (
  claims: CanonicalPermitClaims,
  keyId: string
): Either.Either<PreparedPermitSigningDocument, CanonicalPermitEnvelopeError> => {
  const checkedClaims = decodeExact(
    CanonicalPermitClaimsSchema,
    claims,
    "ENVELOPE_SCHEMA_INVALID",
    "Permit claims do not satisfy the exact v1 schema"
  )
  if (Either.isLeft(checkedClaims)) return Either.left(checkedClaims.left)
  const transition = validateTransition(checkedClaims.right)
  if (Either.isLeft(transition)) return Either.left(transition.left)
  const chronology = validateClaimChronology(checkedClaims.right)
  if (Either.isLeft(chronology)) return Either.left(chronology.left)
  const document = makeSigningDocument(checkedClaims.right, keyId)
  const checkedDocument = decodeExact(
    CanonicalPermitSigningDocumentSchema,
    document,
    "ENVELOPE_SCHEMA_INVALID",
    "Permit signing document does not satisfy the exact v1 schema"
  )
  if (Either.isLeft(checkedDocument)) return Either.left(checkedDocument.left)
  const bytes = canonicalJsonBytes(checkedDocument.right)
  return Either.isLeft(bytes)
    ? fail("CANONICAL_ENCODING_INVALID", bytes.left.detail)
    : Either.right(Object.freeze({
        document: Object.freeze({
          ...checkedDocument.right,
          header: snapshotHeader(checkedDocument.right.header),
          claims: snapshotClaims(checkedDocument.right.claims)
        }),
        bytes: Uint8Array.from(bytes.right)
      }))
}

export const canonicalPermitSigningDocumentBytes = (
  claims: CanonicalPermitClaims,
  keyId: string
): Either.Either<Uint8Array, CanonicalPermitEnvelopeError> => {
  const prepared = preparePermitSigningDocument(claims, keyId)
  return Either.isLeft(prepared)
    ? Either.left(prepared.left)
    : Either.right(Uint8Array.from(prepared.right.bytes))
}

export const assembleCanonicalPermitEnvelope = (
  claims: CanonicalPermitClaims,
  keyId: string,
  signDetached: CanonicalPermitDetachedSigner
): Either.Either<AssembledCanonicalPermitEnvelope, CanonicalPermitEnvelopeError> => {
  const prepared = preparePermitSigningDocument(claims, keyId)
  if (Either.isLeft(prepared)) return Either.left(prepared.left)
  let signatureBytes: Uint8Array
  try {
    const signed = signDetached(Uint8Array.from(prepared.right.bytes))
    if (!(signed instanceof Uint8Array)) {
      return fail("SIGNER_FAILED", "detached signer did not return Uint8Array")
    }
    signatureBytes = Uint8Array.from(signed)
  } catch {
    return fail("SIGNER_FAILED", "detached signer failed")
  }
  if (signatureBytes.byteLength !== 64) {
    return fail("SIGNATURE_FORMAT_INVALID", "Ed25519 signature must contain 64 bytes")
  }

  const envelope = snapshotEnvelope({
    ...prepared.right.document,
    signature: Buffer.from(signatureBytes).toString("base64url")
  })
  const envelopeBytes = canonicalJsonBytes(envelope)
  if (Either.isLeft(envelopeBytes)) {
    return fail("CANONICAL_ENCODING_INVALID", envelopeBytes.left.detail)
  }
  return Either.right(Object.freeze({
    envelope,
    signingBytes: Uint8Array.from(prepared.right.bytes),
    envelopeBytes: Uint8Array.from(envelopeBytes.right),
    signingBytesSha256: sha256(prepared.right.bytes),
    envelopeBytesSha256: sha256(envelopeBytes.right)
  }))
}

export const decodeCanonicalPermitEnvelopeBytes = (
  input: Uint8Array
): Either.Either<CanonicalPermitEnvelope, CanonicalPermitEnvelopeError> => {
  const parsed = decodeCanonicalJsonBytes(input)
  if (Either.isLeft(parsed)) {
    return fail("CANONICAL_ENCODING_INVALID", parsed.left.detail)
  }
  const checked = decodeExact(
    CanonicalPermitEnvelopeSchema,
    parsed.right,
    "ENVELOPE_SCHEMA_INVALID",
    "Permit envelope does not satisfy the exact v1 schema"
  )
  if (Either.isLeft(checked)) return checked
  const canonical = canonicalJsonBytes(checked.right)
  if (Either.isLeft(canonical)) {
    return fail("CANONICAL_ENCODING_INVALID", canonical.left.detail)
  }
  return sameBytes(input, canonical.right)
    ? Either.right(snapshotEnvelope(checked.right))
    : fail(
        "ENVELOPE_BYTES_NONCANONICAL",
        "Permit envelope bytes are not the exact hswm-canonical-json/v1 encoding"
      )
}

export const canonicalPermitTrustSnapshotBytes = (
  snapshot: CanonicalPermitTrustSnapshot
): Either.Either<Uint8Array, CanonicalPermitEnvelopeError> => {
  const checked = decodeExact(
    CanonicalPermitTrustSnapshotSchema,
    snapshot,
    "TRUST_SNAPSHOT_INVALID",
    "trust snapshot does not satisfy the exact v1 schema"
  )
  if (Either.isLeft(checked)) return Either.left(checked.left)
  const bytes = canonicalJsonBytes(checked.right)
  return Either.isLeft(bytes)
    ? fail("TRUST_SNAPSHOT_INVALID", "trust snapshot is not canonically encodable")
    : Either.right(Uint8Array.from(bytes.right))
}

export const decodeCanonicalPermitTrustSnapshotBytes = (
  input: Uint8Array
): Either.Either<CanonicalPermitTrustSnapshot, CanonicalPermitEnvelopeError> => {
  const parsed = decodeCanonicalJsonBytes(input)
  if (Either.isLeft(parsed)) {
    return fail("TRUST_SNAPSHOT_INVALID", parsed.left.detail)
  }
  const checked = decodeExact(
    CanonicalPermitTrustSnapshotSchema,
    parsed.right,
    "TRUST_SNAPSHOT_INVALID",
    "trust snapshot does not satisfy the exact v1 schema"
  )
  if (Either.isLeft(checked)) return Either.left(checked.left)
  const canonical = canonicalJsonBytes(checked.right)
  if (Either.isLeft(canonical) || !sameBytes(input, canonical.right)) {
    return fail(
      "TRUST_SNAPSHOT_INVALID",
      "trust snapshot bytes are not exact hswm-canonical-json/v1"
    )
  }
  return Either.right(Object.freeze({
    ...checked.right,
    keys: Object.freeze(checked.right.keys.map((key) => Object.freeze({ ...key })))
  }))
}

/**
 * Verify envelope bytes only relative to caller-provided expected bindings,
 * canonical trust snapshot bytes, and time. This function MUST NOT be used as
 * an admission authority: it neither derives the expected bindings from a
 * runtime transition, obtains authoritative trust/time, nor consumes a Permit
 * identity or nonce.
 */
export const verifyCanonicalPermitEnvelopeAgainstCallerSuppliedContext = (
  input: Uint8Array,
  callerSuppliedExpectedBindings: CanonicalPermitExpectedBindings,
  callerSuppliedTrustSnapshotBytes: Uint8Array,
  callerSuppliedVerificationTime: string
): Either.Either<CallerRelativeCanonicalPermitEnvelopeVerification, CanonicalPermitEnvelopeError> => {
  const decodedEnvelope = decodeCanonicalPermitEnvelopeBytes(input)
  if (Either.isLeft(decodedEnvelope)) return Either.left(decodedEnvelope.left)
  const envelope = decodedEnvelope.right

  const expected = decodeExact(
    CanonicalPermitExpectedBindingsSchema,
    callerSuppliedExpectedBindings,
    "ENVELOPE_SCHEMA_INVALID",
    "expected Permit bindings do not satisfy the exact v1 schema"
  )
  if (Either.isLeft(expected)) return Either.left(expected.left)
  const expectedBytes = canonicalJsonBytes(expected.right)
  if (Either.isLeft(expectedBytes)) {
    return fail(
      "CANONICAL_ENCODING_INVALID",
      "expected Permit bindings are not canonically encodable"
    )
  }
  const trust = decodeCanonicalPermitTrustSnapshotBytes(callerSuppliedTrustSnapshotBytes)
  if (Either.isLeft(trust)) return Either.left(trust.left)
  const checkedInstant = Schema.decodeUnknownEither(CanonicalInstant)(callerSuppliedVerificationTime)
  if (Either.isLeft(checkedInstant)) {
    return fail("TIME_INVALID", "verification time is not a canonical UTC instant")
  }
  if (!isRealCanonicalInstant(checkedInstant.right)) {
    return fail("TIME_INVALID", "verification time is not a real UTC instant")
  }

  const transition = validateTransition(envelope.claims)
  if (Either.isLeft(transition)) return Either.left(transition.left)
  const times = validateClaimTimes(envelope.claims, checkedInstant.right)
  if (Either.isLeft(times)) return Either.left(times.left)
  if (!isRealCanonicalInstant(trust.right.snapshotAt)) {
    return fail("TRUST_SNAPSHOT_INVALID", "trust snapshot time does not exist")
  }
  if (trust.right.snapshotAt > checkedInstant.right) {
    return fail("TIME_INVALID", "trust snapshot is from after verification time")
  }

  const keyIds = new Set<string>()
  const trustedKeyMaterials = new Map<string, {
    readonly bytes: Uint8Array
    readonly key: ReturnType<typeof createPublicKey>
  }>()
  for (const candidate of trust.right.keys) {
    if (keyIds.has(candidate.keyId)) {
      return fail("TRUST_KEY_DUPLICATE", "trust snapshot contains a duplicate key ID")
    }
    keyIds.add(candidate.keyId)
    if (
      !isRealCanonicalInstant(candidate.notBefore) ||
      !isRealCanonicalInstant(candidate.expiresAt) ||
      (candidate.revokedAt !== null &&
        !isRealCanonicalInstant(candidate.revokedAt)) ||
      !(candidate.notBefore < candidate.expiresAt) ||
      (candidate.status === "ACTIVE" && candidate.revokedAt !== null) ||
      (candidate.status === "REVOKED" && candidate.revokedAt === null) ||
      (candidate.revokedAt !== null &&
        !(candidate.notBefore <= candidate.revokedAt &&
          candidate.revokedAt < candidate.expiresAt))
    ) {
      return fail("TRUST_SNAPSHOT_INVALID", "trust key lifecycle is inconsistent")
    }
    const publicKeyBytes = strictBase64UrlBytes(
      candidate.publicKeySpkiDerBase64Url
    )
    if (Either.isLeft(publicKeyBytes)) {
      return fail(
        "TRUST_SNAPSHOT_INVALID",
        "every trust-snapshot SPKI key must be canonical base64url"
      )
    }
    try {
      const publicKeyObject = createPublicKey({
        key: Buffer.from(publicKeyBytes.right),
        format: "der",
        type: "spki"
      })
      if (publicKeyObject.asymmetricKeyType !== "ed25519") {
        return fail(
          "TRUST_SNAPSHOT_INVALID",
          "every trust-snapshot SPKI key must be Ed25519"
        )
      }
      trustedKeyMaterials.set(candidate.keyId, Object.freeze({
        bytes: Uint8Array.from(publicKeyBytes.right),
        key: publicKeyObject
      }))
    } catch {
      return fail(
        "TRUST_SNAPSHOT_INVALID",
        "every trust-snapshot SPKI key must be valid Ed25519 material"
      )
    }
  }

  if (
    envelope.claims.keyPolicyVersion !== trust.right.policyVersion ||
    envelope.claims.revocationEpoch !== trust.right.revocationEpoch ||
    expected.right.keyPolicyVersion !== trust.right.policyVersion ||
    expected.right.revocationEpoch !== trust.right.revocationEpoch
  ) {
    return fail(
      "KEY_POLICY_MISMATCH",
      "Permit, expected bindings, and trust snapshot policy/epoch differ"
    )
  }

  const key = trust.right.keys.find(
    (candidate) => candidate.keyId === envelope.header.keyId
  )
  if (key === undefined) {
    return fail("TRUST_KEY_UNKNOWN", "Permit signing key is absent from the trust snapshot")
  }
  if (
    key.status !== "ACTIVE" ||
    !(key.notBefore <= envelope.claims.issuedAt &&
      envelope.claims.issuedAt < key.expiresAt) ||
    !(key.notBefore <= checkedInstant.right && checkedInstant.right < key.expiresAt)
  ) {
    return fail(
      "TRUST_KEY_INACTIVE",
      "Permit signing key is not active at both issue and verification time"
    )
  }
  if (
    key.authorizedAuthorizer !== envelope.claims.authorizer ||
    expected.right.authorizer !== envelope.claims.authorizer
  ) {
    return fail(
      "AUTHORIZER_MISMATCH",
      "trusted key authority does not match the exact Permit authorizer"
    )
  }

  const mismatch = exactBindings(envelope.claims, expected.right)
  if (mismatch !== null) {
    return fail("BINDING_MISMATCH", `Permit binding differs at ${mismatch}`)
  }

  const signingBytes = canonicalPermitSigningDocumentBytes(
    envelope.claims,
    envelope.header.keyId
  )
  if (Either.isLeft(signingBytes)) return Either.left(signingBytes.left)
  const signature = strictBase64UrlBytes(envelope.signature)
  if (Either.isLeft(signature) || signature.right.byteLength !== 64) {
    return fail("SIGNATURE_FORMAT_INVALID", "Permit signature is not exact Ed25519 bytes")
  }
  const trustedKeyMaterial = trustedKeyMaterials.get(key.keyId)
  if (trustedKeyMaterial === undefined) {
    return fail("TRUST_SNAPSHOT_INVALID", "selected trusted key material is absent")
  }

  let authenticated = false
  try {
    authenticated = verifySignature(
      null,
      signingBytes.right,
      trustedKeyMaterial.key,
      signature.right
    )
  } catch {
    return fail("SIGNATURE_INVALID", "Ed25519 verifier rejected the supplied material")
  }
  if (!authenticated) {
    return fail("SIGNATURE_INVALID", "Ed25519 signature does not authenticate signing bytes")
  }

  return Either.right(Object.freeze({
    envelope,
    envelopeBytesSha256: sha256(input),
    signingBytesSha256: sha256(signingBytes.right),
    callerSuppliedExpectedBindingsSha256: sha256(expectedBytes.right),
    callerSuppliedTrustSnapshotSha256: sha256(callerSuppliedTrustSnapshotBytes),
    callerSuppliedPublicKeySpkiSha256: sha256(trustedKeyMaterial.bytes),
    callerSuppliedVerificationTime: checkedInstant.right,
    callerSuppliedTrustPolicyVersion: trust.right.policyVersion,
    callerSuppliedTrustRevocationEpoch: trust.right.revocationEpoch,
    callerSuppliedTrustedKeyId: key.keyId,
    trustStatus: HSWM_CANONICAL_PERMIT_TRUST_STATUS,
    status: HSWM_CANONICAL_PERMIT_CALLER_CONTEXT_VERIFICATION_STATUS
  }))
}
