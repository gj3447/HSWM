import {
  createHash,
  createPrivateKey,
  sign as signMessage
} from "node:crypto"
import { readFileSync } from "node:fs"

import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import {
  HSWM_CANONICAL_PERMIT_ENVELOPE_STATUS,
  HSWM_CANONICAL_PERMIT_TRUST_SNAPSHOT_V1_CONTRACT_VERSION,
  HSWM_CANONICAL_PERMIT_TRUST_STATUS,
  HSWM_CANONICAL_PERMIT_CALLER_CONTEXT_VERIFICATION_STATUS,
  type CanonicalPermitClaims,
  type CanonicalPermitEnvelopeError,
  type CanonicalPermitExpectedBindings,
  type CanonicalPermitTrustSnapshot,
  canonicalPermitTrustSnapshotBytes,
  decodeCanonicalPermitEnvelopeBytes,
  assembleCanonicalPermitEnvelope,
  verifyCanonicalPermitEnvelopeAgainstCallerSuppliedContext
} from "../src/canonical-atom-v2-permit-envelope.js"
import { canonicalJsonBytes } from "../src/canonical-atom-v2-json.js"

const ED25519_TEST_SEED =
  "9d61b19deffd5a60ba844af492ec2cc4" +
  "4449c5697b326919703bac031cae7f60"
const ED25519_TEST_PUBLIC_KEY =
  "d75a980182b10ab7d54bfed3c964073a" +
  "0ee172f3daa62325af021a68f707511a"
const PKCS8_ED25519_PREFIX = "302e020100300506032b657004220420"
const SPKI_ED25519_PREFIX = "302a300506032b6570032100"

const privateKey = createPrivateKey({
  key: Buffer.from(PKCS8_ED25519_PREFIX + ED25519_TEST_SEED, "hex"),
  format: "der",
  type: "pkcs8"
})
const publicKeySpki = Buffer.from(
  SPKI_ED25519_PREFIX + ED25519_TEST_PUBLIC_KEY,
  "hex"
).toString("base64url")

interface CanonicalPermitEnvelopeVector {
  readonly schema: string
  readonly publicKeySpkiDerBase64Url: string
  readonly signingDocumentCanonicalBase64Url: string
  readonly signingDocumentSha256: string
  readonly envelopeCanonicalBase64Url: string
  readonly envelopeSha256: string
  readonly expectedVerificationStatus: string
}

const vector = JSON.parse(
  readFileSync(
    new URL("./fixtures/canonical-permit-envelope-v1.vector.json", import.meta.url),
    "utf8"
  )
) as CanonicalPermitEnvelopeVector

const signDetached = (bytes: Uint8Array): Uint8Array =>
  Uint8Array.from(signMessage(null, bytes, privateKey))

const claims: CanonicalPermitClaims = Object.freeze({
  permitId: "permit:test-vector-001",
  executionId: "execution:test-vector-001",
  executionIntentDigest: "01".repeat(32),
  permitDigest: "02".repeat(32),
  proposalDigest: "03".repeat(32),
  transitionInvariantDigest: "04".repeat(32),
  priorHead: Object.freeze({
    lineageId: "lineage:test",
    sequence: 40,
    stateDigest: "05".repeat(32),
    recordDigest: "06".repeat(32)
  }),
  expectedNextHead: Object.freeze({
    lineageId: "lineage:test",
    sequence: 41,
    stateDigest: "07".repeat(32),
    recordDigest: "08".repeat(32)
  }),
  target: Object.freeze({
    schemaVersion: "schema:test-v1",
    lineageId: "lineage:atom-test",
    atomUid: "atom:test"
  }),
  expectedRevision: "revision:40",
  candidateRevision: "revision:41",
  authorizationRef: "authorization:test-001",
  authorizer: "principal:permit-issuer",
  scope: "scope:canonical-revision",
  nonceDigest: "09".repeat(32),
  keyPolicyVersion: "key-policy:test-v1",
  revocationEpoch: 7,
  linearizationIndex: 100,
  issuedAt: "2026-08-31T10:00:00.000Z",
  notBefore: "2026-08-31T10:00:01.000Z",
  expiresAt: "2026-09-01T10:00:00.000Z"
})

const expected: CanonicalPermitExpectedBindings = Object.freeze({
  permitId: claims.permitId,
  executionId: claims.executionId,
  executionIntentDigest: claims.executionIntentDigest,
  permitDigest: claims.permitDigest,
  proposalDigest: claims.proposalDigest,
  transitionInvariantDigest: claims.transitionInvariantDigest,
  priorHead: claims.priorHead,
  expectedNextHead: claims.expectedNextHead,
  target: claims.target,
  expectedRevision: claims.expectedRevision,
  candidateRevision: claims.candidateRevision,
  authorizationRef: claims.authorizationRef,
  authorizer: claims.authorizer,
  scope: claims.scope,
  nonceDigest: claims.nonceDigest,
  keyPolicyVersion: claims.keyPolicyVersion,
  revocationEpoch: claims.revocationEpoch,
  linearizationIndex: claims.linearizationIndex
})

const trust: CanonicalPermitTrustSnapshot = Object.freeze({
  _tag: "CanonicalPermitTrustSnapshot",
  contractVersion: HSWM_CANONICAL_PERMIT_TRUST_SNAPSHOT_V1_CONTRACT_VERSION,
  policyVersion: claims.keyPolicyVersion,
  revocationEpoch: claims.revocationEpoch,
  snapshotAt: "2026-08-31T09:00:00.000Z",
  keys: Object.freeze([
    Object.freeze({
      keyId: "key:rfc8032-test-1",
      algorithm: "Ed25519",
      publicKeySpkiDerBase64Url: publicKeySpki,
      authorizedAuthorizer: claims.authorizer,
      notBefore: "2026-08-01T00:00:00.000Z",
      expiresAt: "2026-10-01T00:00:00.000Z",
      status: "ACTIVE",
      revokedAt: null
    })
  ]),
  status: HSWM_CANONICAL_PERMIT_TRUST_STATUS
})

const unwrap = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw value.left
  return value.right
}

const expectLeftCode = <A>(
  value: Either.Either<A, CanonicalPermitEnvelopeError>,
  code: CanonicalPermitEnvelopeError["code"]
): void => {
  expect(Either.isLeft(value)).toBe(true)
  if (Either.isLeft(value)) expect(value.left.code).toBe(code)
}

const assemble = () =>
  unwrap(
    assembleCanonicalPermitEnvelope(
      claims,
      "key:rfc8032-test-1",
      signDetached
    )
  )

const encodeTrust = (
  value: CanonicalPermitTrustSnapshot = trust
): Uint8Array => unwrap(canonicalPermitTrustSnapshotBytes(value))

it("assembles deterministic Ed25519 bytes and verifies them relative to caller inputs", () => {
  const issued = assemble()
  const decoded = unwrap(decodeCanonicalPermitEnvelopeBytes(issued.envelopeBytes))
  expect(decoded).toEqual(issued.envelope)
  expect(decoded.status).toBe(HSWM_CANONICAL_PERMIT_ENVELOPE_STATUS)
  expect(issued.signingBytesSha256).toBe(
    "985d0156c0687de5d3e2a908c93c9aa098932afda9673925e5478dde4ff59c80"
  )
  expect(issued.envelopeBytesSha256).toBe(
    "66af55c2437da2394450bc985f2979176cf44c6b6443a1886c8ed142bc83ed9a"
  )
  expect(vector.schema).toBe("hswm-canonical-permit-envelope-test-vector/v1")
  expect(vector.publicKeySpkiDerBase64Url).toBe(publicKeySpki)
  expect(vector.signingDocumentSha256).toBe(issued.signingBytesSha256)
  expect(vector.envelopeSha256).toBe(issued.envelopeBytesSha256)
  expect(vector.signingDocumentCanonicalBase64Url).toBe(
    Buffer.from(issued.signingBytes).toString("base64url")
  )
  expect(vector.envelopeCanonicalBase64Url).toBe(
    Buffer.from(issued.envelopeBytes).toString("base64url")
  )

  const verified = unwrap(
    verifyCanonicalPermitEnvelopeAgainstCallerSuppliedContext(
      issued.envelopeBytes,
      expected,
      encodeTrust(),
      "2026-08-31T12:00:00.000Z"
    )
  )
  expect(verified.status).toBe(
    HSWM_CANONICAL_PERMIT_CALLER_CONTEXT_VERIFICATION_STATUS
  )
  expect(vector.expectedVerificationStatus).toBe(verified.status)
  expect(verified.callerSuppliedExpectedBindingsSha256).toBe(
    createHash("sha256")
      .update(unwrap(canonicalJsonBytes(expected)))
      .digest("hex")
  )
  expect(verified.callerSuppliedTrustedKeyId).toBe("key:rfc8032-test-1")
  expect(verified.callerSuppliedTrustSnapshotSha256).toMatch(/^[0-9a-f]{64}$/)
  expect(verified.callerSuppliedPublicKeySpkiSha256).toMatch(/^[0-9a-f]{64}$/)
  expect(verified.callerSuppliedVerificationTime).toBe(
    "2026-08-31T12:00:00.000Z"
  )
  expect(verified.trustStatus).toBe(
    "CALLER_SUPPLIED_TRUST_SNAPSHOT_NOT_TRANSPARENCY_LOG"
  )
  expect(verified.envelope.claims.expectedNextHead.sequence).toBe(41)
})

it("rejects noncanonical bytes and a signed-document mutation", () => {
  const issued = assemble()
  const spaced = new TextEncoder().encode(
    JSON.stringify(issued.envelope, null, 2)
  )
  expectLeftCode(
    decodeCanonicalPermitEnvelopeBytes(spaced),
    "ENVELOPE_BYTES_NONCANONICAL"
  )

  const tamperedEnvelope = {
    ...issued.envelope,
    claims: {
      ...issued.envelope.claims,
      proposalDigest: "aa".repeat(32)
    }
  }
  const tamperedBytes = unwrap(canonicalJsonBytes(tamperedEnvelope))
  expectLeftCode(
    verifyCanonicalPermitEnvelopeAgainstCallerSuppliedContext(
      tamperedBytes,
      { ...expected, proposalDigest: "aa".repeat(32) },
      encodeTrust(),
      "2026-08-31T12:00:00.000Z"
    ),
    "SIGNATURE_INVALID"
  )

  const wrongSignatureBytes = unwrap(canonicalJsonBytes({
    ...issued.envelope,
    signature: Buffer.alloc(64).toString("base64url")
  }))
  expectLeftCode(
    verifyCanonicalPermitEnvelopeAgainstCallerSuppliedContext(
      wrongSignatureBytes,
      expected,
      encodeTrust(),
      "2026-08-31T12:00:00.000Z"
    ),
    "SIGNATURE_INVALID"
  )
})

it("fails closed on every exact expected binding mismatch", () => {
  const issued = assemble()
  const mismatches: ReadonlyArray<CanonicalPermitExpectedBindings> = [
    { ...expected, permitId: "permit:other" },
    { ...expected, executionId: "execution:other" },
    { ...expected, executionIntentDigest: "aa".repeat(32) },
    { ...expected, permitDigest: "aa".repeat(32) },
    {
      ...expected,
      priorHead: { ...expected.priorHead, recordDigest: "aa".repeat(32) }
    },
    {
      ...expected,
      expectedNextHead: {
        ...expected.expectedNextHead,
        stateDigest: "aa".repeat(32)
      }
    },
    { ...expected, proposalDigest: "aa".repeat(32) },
    { ...expected, transitionInvariantDigest: "aa".repeat(32) },
    {
      ...expected,
      target: { ...expected.target, schemaVersion: "schema:other" }
    },
    {
      ...expected,
      target: { ...expected.target, lineageId: "lineage:other" }
    },
    {
      ...expected,
      target: { ...expected.target, atomUid: "atom:other" }
    },
    { ...expected, expectedRevision: "revision:other" },
    { ...expected, candidateRevision: "revision:other" },
    { ...expected, authorizationRef: "authorization:other" },
    { ...expected, scope: "scope:other" },
    { ...expected, nonceDigest: "aa".repeat(32) },
    { ...expected, linearizationIndex: 101 }
  ]

  for (const mismatch of mismatches) {
    expectLeftCode(
      verifyCanonicalPermitEnvelopeAgainstCallerSuppliedContext(
        issued.envelopeBytes,
        mismatch,
        encodeTrust(),
        "2026-08-31T12:00:00.000Z"
      ),
      "BINDING_MISMATCH"
    )
  }

  expectLeftCode(
    verifyCanonicalPermitEnvelopeAgainstCallerSuppliedContext(
      issued.envelopeBytes,
      { ...expected, authorizer: "principal:other" },
      encodeTrust(),
      "2026-08-31T12:00:00.000Z"
    ),
    "AUTHORIZER_MISMATCH"
  )
  for (const mismatch of [
    { ...expected, keyPolicyVersion: "key-policy:other" },
    { ...expected, revocationEpoch: 8 }
  ]) {
    expectLeftCode(
      verifyCanonicalPermitEnvelopeAgainstCallerSuppliedContext(
        issued.envelopeBytes,
        mismatch,
        encodeTrust(),
        "2026-08-31T12:00:00.000Z"
      ),
      "KEY_POLICY_MISMATCH"
    )
  }
})

it("fails closed when caller-supplied trust bytes duplicate a key ID", () => {
  const issued = assemble()
  expectLeftCode(
    verifyCanonicalPermitEnvelopeAgainstCallerSuppliedContext(
      issued.envelopeBytes,
      expected,
      new TextEncoder().encode(JSON.stringify(trust, null, 2)),
      "2026-08-31T12:00:00.000Z"
    ),
    "TRUST_SNAPSHOT_INVALID"
  )
  expectLeftCode(
    verifyCanonicalPermitEnvelopeAgainstCallerSuppliedContext(
      issued.envelopeBytes,
      expected,
      encodeTrust({
        ...trust,
        keys: [trust.keys[0]!, { ...trust.keys[0]! }]
      }),
      "2026-08-31T12:00:00.000Z"
    ),
    "TRUST_KEY_DUPLICATE"
  )
})

it("rejects malformed Ed25519 material even on an unselected trust key", () => {
  const issued = assemble()
  expectLeftCode(
    verifyCanonicalPermitEnvelopeAgainstCallerSuppliedContext(
      issued.envelopeBytes,
      expected,
      encodeTrust({
        ...trust,
        keys: [
          trust.keys[0]!,
          {
            ...trust.keys[0]!,
            keyId: "key:unused-invalid",
            publicKeySpkiDerBase64Url: "AA"
          }
        ]
      }),
      "2026-08-31T12:00:00.000Z"
    ),
    "TRUST_SNAPSHOT_INVALID"
  )
})

it("rejects inactive time, unknown or revoked keys, stale policy, and wrong authority", () => {
  const issued = assemble()
  expectLeftCode(
    verifyCanonicalPermitEnvelopeAgainstCallerSuppliedContext(
      issued.envelopeBytes,
      expected,
      encodeTrust(),
      "2026-09-02T00:00:00.000Z"
    ),
    "TIME_INVALID"
  )

  expectLeftCode(
    verifyCanonicalPermitEnvelopeAgainstCallerSuppliedContext(
      issued.envelopeBytes,
      expected,
      encodeTrust({
        ...trust,
        keys: [{
          ...trust.keys[0]!,
          notBefore: "2026-08-31T11:00:00.000Z"
        }]
      }),
      "2026-08-31T12:00:00.000Z"
    ),
    "TRUST_KEY_INACTIVE"
  )
  expectLeftCode(
    verifyCanonicalPermitEnvelopeAgainstCallerSuppliedContext(
      issued.envelopeBytes,
      expected,
      encodeTrust({
        ...trust,
        keys: [{ ...trust.keys[0]!, keyId: "key:other" }]
      }),
      "2026-08-31T12:00:00.000Z"
    ),
    "TRUST_KEY_UNKNOWN"
  )
  expectLeftCode(
    verifyCanonicalPermitEnvelopeAgainstCallerSuppliedContext(
      issued.envelopeBytes,
      expected,
      encodeTrust({
        ...trust,
        keys: [{
          ...trust.keys[0]!,
          status: "REVOKED",
          revokedAt: "2026-08-31T11:00:00.000Z"
        }]
      }),
      "2026-08-31T12:00:00.000Z"
    ),
    "TRUST_KEY_INACTIVE"
  )
  expectLeftCode(
    verifyCanonicalPermitEnvelopeAgainstCallerSuppliedContext(
      issued.envelopeBytes,
      expected,
      encodeTrust({ ...trust, revocationEpoch: 8 }),
      "2026-08-31T12:00:00.000Z"
    ),
    "KEY_POLICY_MISMATCH"
  )
  expectLeftCode(
    verifyCanonicalPermitEnvelopeAgainstCallerSuppliedContext(
      issued.envelopeBytes,
      expected,
      encodeTrust({
        ...trust,
        keys: [{
          ...trust.keys[0]!,
          authorizedAuthorizer: "principal:other"
        }]
      }),
      "2026-08-31T12:00:00.000Z"
    ),
    "AUTHORIZER_MISMATCH"
  )
})

it("refuses invalid successor chronology and malformed signer output", () => {
  expectLeftCode(
    assembleCanonicalPermitEnvelope(
      {
        ...claims,
        expectedNextHead: { ...claims.expectedNextHead, sequence: 42 }
      },
      "key:rfc8032-test-1",
      signDetached
    ),
    "TRANSITION_INVALID"
  )
  expectLeftCode(
    assembleCanonicalPermitEnvelope(
      claims,
      "key:rfc8032-test-1",
      () => new Uint8Array(63)
    ),
    "SIGNATURE_FORMAT_INVALID"
  )
})
