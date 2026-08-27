import { createHash } from "node:crypto"

import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import {
  HSWM_CANONICAL_TRANSITION_EVIDENCE_BUNDLE_V1_MEDIA_TYPE,
  HSWM_CANONICAL_TRANSITION_EVIDENCE_RECORD_V1_MEDIA_TYPE,
  HSWM_CANONICAL_TRANSITION_PROPOSAL_V1_MEDIA_TYPE,
  canonicalAtomV2TransitionEvidenceBundleBytes,
  canonicalAtomV2TransitionEvidenceRecordBytes,
  classifyCanonicalAtomV2AuthorizationEvidence,
  decodeCanonicalAtomV2TransitionEvidenceBundleBytes,
  decodeCanonicalAtomV2TransitionEvidenceRecordBytes,
  describeCanonicalAtomV2TransitionEvidenceBundle,
  describeCanonicalAtomV2TransitionEvidenceRecord,
  snapshotCanonicalAtomV2TransitionEvidenceBundle,
  validateCanonicalAtomV2TransitionEvidenceBundle,
  validateCanonicalAtomV2TransitionEvidenceRecord,
  type CanonicalAtomV2TransitionEvidenceError,
  type CanonicalAtomV2TransitionEvidenceBundle
} from "../src/canonical-atom-v2-transition-evidence.js"
import { canonicalJsonBytes } from "../src/canonical-atom-v2-json.js"
import { makeCanonicalAtomV2ContentDescriptor } from "../src/canonical-atom-v2-content.js"

const utf8 = (value: string) => new TextEncoder().encode(value)
const sha256 = (value: Uint8Array) =>
  createHash("sha256").update(value).digest("hex")
const descriptor = (mediaType: string, value: unknown) => {
  const bytes = canonicalJsonBytes(value)
  if (Either.isLeft(bytes)) throw new Error("fixture bytes")
  const made = makeCanonicalAtomV2ContentDescriptor(mediaType, bytes.right)
  if (Either.isLeft(made)) throw new Error("fixture descriptor")
  return made.right
}
const opaque = (id: string) => descriptor("application/json", { id })
const key = (atomUid: string, revisionId = 0) => ({
  schemaVersion: "hswm:test:evidence:v2",
  lineageId: "lineage:evidence",
  atomUid,
  revisionId
})
const schema = {
  schemaVersion: "hswm:test:evidence:v2",
  content: opaque("schema")
}
type SelfWrite = "authorization" | "trace" | null

const proposal = (principal = false, selfWrite: SelfWrite = null) => ({
  _tag: "CommitCanonicalAtomsV2" as const,
  contractVersion: "hswm-canonical-transition/v2" as const,
  transitionId: "transition:evidence",
  expectedStateRevision: 4,
  schemaVersion: schema.schemaVersion,
  actorClaim: principal ? "principal:one" : "principal:claimant",
  authorizationRef: "authorization:evidence",
  scope: "scope:write",
  decidedAt: "2026-08-27T00:00:01.500Z",
  traceRef: key("atom:trace"),
  readSet: [
    key("atom:read"),
    key("atom:subject"),
    key("atom:trace"),
    key("authorization:evidence")
  ],
  writes: [{
    _tag: "CanonicalAtomV2" as const,
    contractVersion: "hswm-canonical-atom/v2" as const,
    key: key(
      selfWrite === "authorization"
        ? "authorization:evidence"
        : selfWrite === "trace"
          ? "atom:trace"
          : "atom:write"
    ),
    kind: "kind:atom",
    responsibilityOwner: principal ? "principal:one" : "principal:owner",
    content: opaque("payload"),
    provenance: { mode: "BOOTSTRAP" as const, evidenceSha256: "a".repeat(64), sourceRef: null },
    lifecycle: "ADMITTED" as const,
    references: []
  }],
  provenanceSha256: "b".repeat(64)
})

const bundle = (
  principal = false,
  selfWrite: SelfWrite = null
): CanonicalAtomV2TransitionEvidenceBundle => {
  const command = proposal(principal, selfWrite)
  const shared = principal ? "principal:one" : "principal:claimant"
  const authorizer = principal ? "principal:one" : "principal:authorizer"
  const owner = principal ? "principal:one" : "principal:owner"
  const sealer = principal ? "principal:one" : "principal:sealer"
  const custodian = principal ? "principal:other-custodian" : "principal:custodian"
  const proposalDescriptor = descriptor(HSWM_CANONICAL_TRANSITION_PROPOSAL_V1_MEDIA_TYPE, command)
  const predecessor = opaque("predecessor")
  const subjects = [{ subject: key("atom:subject"), relation: "relation:affected" }]
  const authorization = {
    _tag: "CanonicalAtomV2AuthorizationDecisionEvidence" as const,
    contractVersion: "hswm-canonical-transition-evidence/v1" as const,
    authorizationRef: command.authorizationRef,
    decisionRef: key(command.authorizationRef),
    schema,
    claimedPredecessor: predecessor,
    claimedPredecessorStateRevision: command.expectedStateRevision,
    proposal: proposalDescriptor,
    claimant: { address: shared },
    subjects,
    authorizer: { address: authorizer },
    scope: command.scope,
    decision: "GRANTED" as const,
    decidedAt: "2026-08-27T00:00:00.000Z",
    notBefore: "2026-08-26T00:00:00.000Z",
    expiresAt: "2026-08-28T00:00:00.000Z",
    decisionEvidence: opaque("authorization"),
    revocationStatus: "CHECKED_NOT_REVOKED" as const,
    revocationCheckedAt: "2026-08-27T00:00:01.000Z",
    revokedAt: null,
    revocationEvidence: opaque("revocation-check"),
    permitStatus: "REPRESENTED_NOT_CANONICAL_PERMIT" as const
  }
  const trajectory = {
    _tag: "CanonicalAtomV2SealedTrajectoryEvidence" as const,
    contractVersion: "hswm-canonical-transition-evidence/v1" as const,
    traceId: command.traceRef!.atomUid,
    schema,
    claimedPredecessor: predecessor,
    claimedPredecessorStateRevision: command.expectedStateRevision,
    proposal: proposalDescriptor,
    traceRef: command.traceRef!,
    claimant: { address: shared },
    sealer: { address: sealer },
    readSet: command.readSet,
    writeSet: command.writes.map(({ key: write }) => write),
    events: [{ sequence: 0, kind: "INPUT" as const, content: opaque("input") }],
    sealedAt: "2026-08-27T00:00:01.000Z",
    provenance: {
      collector: { address: "principal:collector" },
      method: "method:fixture",
      collectedAt: "2026-08-27T00:00:00.000Z",
      source: opaque("provenance-source"),
      status: "CLAIMED_NOT_TRUTH" as const
    }
  }
  const effect = {
    _tag: "CanonicalAtomV2TransitionEffectEvidence" as const,
    contractVersion: "hswm-canonical-transition-evidence/v1" as const,
    schema,
    claimedPredecessor: predecessor,
    claimedPredecessorStateRevision: command.expectedStateRevision,
    proposal: proposalDescriptor,
    authorization: descriptor(HSWM_CANONICAL_TRANSITION_EVIDENCE_RECORD_V1_MEDIA_TYPE, authorization),
    trajectory: descriptor(HSWM_CANONICAL_TRANSITION_EVIDENCE_RECORD_V1_MEDIA_TYPE, trajectory),
    referenceReceipt: opaque("reference-receipt"),
    readSet: command.readSet,
    writeSet: command.writes.map(({ key: write }) => write),
    traceRef: command.traceRef!,
    actorClaim: command.actorClaim,
    authorizationRef: command.authorizationRef,
    scope: command.scope,
    decidedAt: command.decidedAt,
    decision: "ACCEPTED" as const,
    provenanceSha256: command.provenanceSha256,
    guardStatus: "REFERENCE_RECEIPT_DESCRIPTOR_BOUND_NOT_CANONICAL_PERMIT" as const,
    effectStatus: "REFERENCE_EFFECT_NOT_EXTERNAL_EFFECT" as const
  }
  return {
    _tag: "CanonicalAtomV2TransitionEvidenceBundle",
    contractVersion: "hswm-canonical-transition-evidence/v1",
    schema,
    claimedPredecessor: predecessor,
    claimedPredecessorStateRevision: command.expectedStateRevision,
    proposal: command,
    proposalDescriptor,
    roles: {
      owners: [{ write: command.writes[0]!.key, owner: { address: owner } }],
      claimant: { address: shared },
      subjects,
      custodians: [
        {
          custodian: { address: custodian },
          custody: "QUARANTINE",
          object: proposalDescriptor,
          evidence: opaque("quarantine-custody")
        },
        {
          custodian: { address: custodian },
          custody: "TRACE",
          object: descriptor(
            HSWM_CANONICAL_TRANSITION_EVIDENCE_RECORD_V1_MEDIA_TYPE,
            trajectory
          ),
          evidence: opaque("trace-custody")
        }
      ],
      authorizer: { address: authorizer }
    },
    authorization,
    trajectory,
    effect,
    outcome: {
      _tag: "CanonicalAtomV2OutcomeObservationEvidence",
      contractVersion: "hswm-canonical-transition-evidence/v1",
      schema,
      proposal: proposalDescriptor,
      trajectory: descriptor(HSWM_CANONICAL_TRANSITION_EVIDENCE_RECORD_V1_MEDIA_TYPE, trajectory),
      effect: descriptor(HSWM_CANONICAL_TRANSITION_EVIDENCE_RECORD_V1_MEDIA_TYPE, effect),
      evaluator: { address: "principal:evaluator" },
      observedAt: "2026-08-27T00:00:02.000Z",
      observation: opaque("outcome"),
      outcome: "OBSERVED",
      provenance: {
        collector: { address: "principal:outcome-collector" },
        method: "method:outcome-fixture",
        collectedAt: "2026-08-27T00:00:02.000Z",
        source: opaque("outcome-source"),
        status: "CLAIMED_NOT_TRUTH"
      },
      independence: "DECLARED_ROLE_SEPARATION_NOT_PROVEN",
      independenceEvidence: opaque("independence"),
      outcomeStatus: "REPRESENTED_NOT_CAUSAL_CREDIT"
    },
    disposition: {
      _tag: "CanonicalAtomV2TransitionDispositionEvidence",
      contractVersion: "hswm-canonical-transition-evidence/v1",
      disposition: "QUARANTINED",
      stage: "OUTCOME",
      reason: "reason:bounded",
      observedAt: "2026-08-27T00:00:03.000Z",
      candidate: proposalDescriptor,
      evidence: opaque("disposition"),
      decider: { address: "principal:decider" },
      custodian: { address: custodian },
      retention: opaque("retention"),
      admissionStatus: "NOT_ADMITTED_NOT_PERMITTED_NOT_LEARNING"
    }
  }
}

const expectBundleFailure = (
  input: unknown,
  code: CanonicalAtomV2TransitionEvidenceError["code"]
) => {
  const checked = validateCanonicalAtomV2TransitionEvidenceBundle(input)
  expect(Either.isLeft(checked)).toBe(true)
  if (Either.isLeft(checked)) expect(checked.left.code).toBe(code)
}

const minimalBundle = () => ({
  ...bundle(),
  effect: null,
  outcome: null,
  disposition: null
})

it("allows equal named roles without inferring a Permit", () => {
  const value = bundle(true)
  const checked = validateCanonicalAtomV2TransitionEvidenceBundle(value)
  expect(Either.isRight(checked)).toBe(true)
  expect(
    classifyCanonicalAtomV2AuthorizationEvidence(
      value.authorization,
      "2026-08-27T00:00:01.000Z"
    )
  ).toBe("EVIDENCE_GRANTED_NOT_PERMIT")
})

it("classifies exact authorization and revocation boundaries without producing a Permit", () => {
  const value = bundle().authorization
  const interval = {
    ...value,
    decidedAt: "2026-08-25T00:00:00.000Z"
  }
  const revoked = {
    ...value,
    revocationStatus: "REVOKED",
    revokedAt: "2026-08-27T00:00:00.500Z"
  } as const
  const unchecked = {
    ...value,
    revocationStatus: "NOT_CHECKED",
    revocationCheckedAt: null,
    revokedAt: null,
    revocationEvidence: null
  } as const

  const classifications = [
    classifyCanonicalAtomV2AuthorizationEvidence(
      value,
      "2026-08-26T23:59:59.999Z"
    ),
    classifyCanonicalAtomV2AuthorizationEvidence(
      interval,
      "2026-08-25T23:59:59.999Z"
    ),
    classifyCanonicalAtomV2AuthorizationEvidence(
      {
        ...interval,
        revocationCheckedAt: "2026-08-26T00:00:00.000Z"
      },
      "2026-08-26T00:00:00.000Z"
    ),
    classifyCanonicalAtomV2AuthorizationEvidence(
      {
        ...interval,
        revocationCheckedAt: "2026-08-27T23:59:59.999Z"
      },
      "2026-08-27T23:59:59.999Z"
    ),
    classifyCanonicalAtomV2AuthorizationEvidence(
      {
        ...interval,
        revocationCheckedAt: "2026-08-28T00:00:00.000Z"
      },
      "2026-08-28T00:00:00.000Z"
    ),
    classifyCanonicalAtomV2AuthorizationEvidence(
      revoked,
      "2026-08-27T00:00:00.499Z"
    ),
    classifyCanonicalAtomV2AuthorizationEvidence(
      {
        ...revoked,
        revocationCheckedAt: "2026-08-27T00:00:00.500Z"
      },
      "2026-08-27T00:00:00.500Z"
    ),
    classifyCanonicalAtomV2AuthorizationEvidence(
      value,
      "2026-08-27T00:00:01.000Z"
    ),
    classifyCanonicalAtomV2AuthorizationEvidence(
      value,
      "2026-08-27T00:00:01.001Z"
    )
  ]
  expect(classifications).toEqual([
    "EVIDENCE_DECISION_NOT_YET_MADE_NOT_PERMIT",
    "EVIDENCE_NOT_YET_VALID_NOT_PERMIT",
    "EVIDENCE_GRANTED_NOT_PERMIT",
    "EVIDENCE_GRANTED_NOT_PERMIT",
    "EVIDENCE_EXPIRED_NOT_PERMIT",
    "EVIDENCE_REVOCATION_CHECK_FUTURE_NOT_PERMIT",
    "EVIDENCE_REVOKED_NOT_PERMIT",
    "EVIDENCE_GRANTED_NOT_PERMIT",
    "EVIDENCE_REVOCATION_CHECK_STALE_NOT_PERMIT"
  ])
  expect(
    classifyCanonicalAtomV2AuthorizationEvidence(
      { ...value, decision: "DENIED" },
      "2026-08-27T00:00:01.000Z"
    )
  ).toBe("EVIDENCE_DENIED_NOT_PERMIT")
  expect(
    classifyCanonicalAtomV2AuthorizationEvidence(
      unchecked,
      "2026-08-27T00:00:01.000Z"
    )
  ).toBe("EVIDENCE_REVOCATION_UNCHECKED_NOT_PERMIT")
  expect(
    classifyCanonicalAtomV2AuthorizationEvidence(
      { ...value, revocationCheckedAt: null },
      "2026-08-27T00:00:01.000Z"
    )
  ).toBe("EVIDENCE_INVALID_NOT_PERMIT")
  expect(
    classifyCanonicalAtomV2AuthorizationEvidence(value, "not-an-instant")
  ).toBe("EVIDENCE_INVALID_NOT_PERMIT")
  expect(
    classifyCanonicalAtomV2AuthorizationEvidence(
      { ...value, notBefore: value.expiresAt },
      "2026-08-27T00:00:01.000Z"
    )
  ).toBe("EVIDENCE_INVALID_NOT_PERMIT")
  expect(classifications.every((value) => value.endsWith("_NOT_PERMIT"))).toBe(
    true
  )
})

it("keeps unknown outcome and no disposition representable without admitting a candidate", () => {
  const value = bundle()
  const unknown = {
    ...value,
    outcome: {
      ...value.outcome!,
      outcome: "UNKNOWN" as const,
      observation: null,
      independence: "UNKNOWN" as const,
      independenceEvidence: null
    },
    disposition: null
  }
  expect(Either.isRight(validateCanonicalAtomV2TransitionEvidenceBundle(unknown))).toBe(true)
})

it("gives each nested evidence record an independent strict canonical ingress", () => {
  const value = bundle()
  const records = [
    value.authorization,
    value.trajectory,
    value.effect!,
    value.outcome!,
    value.disposition!
  ]
  for (const record of records) {
    const encoded = canonicalAtomV2TransitionEvidenceRecordBytes(record)
    expect(Either.isRight(encoded)).toBe(true)
    if (Either.isLeft(encoded)) continue
    const described = describeCanonicalAtomV2TransitionEvidenceRecord(record)
    expect(Either.isRight(described)).toBe(true)
    if (Either.isRight(described)) {
      expect(described.right.mediaType).toBe(
        HSWM_CANONICAL_TRANSITION_EVIDENCE_RECORD_V1_MEDIA_TYPE
      )
      expect(described.right.byteLength).toBe(encoded.right.byteLength)
      expect(described.right.sha256).toBe(sha256(encoded.right))
    }
    const decoded = decodeCanonicalAtomV2TransitionEvidenceRecordBytes(
      encoded.right
    )
    expect(Either.isRight(decoded)).toBe(true)
    if (Either.isRight(decoded)) {
      expect(decoded.right._tag).toBe(record._tag)
      expect(Object.isFrozen(decoded.right)).toBe(true)
      const reencoded = canonicalAtomV2TransitionEvidenceRecordBytes(decoded.right)
      expect(Either.isRight(reencoded)).toBe(true)
      if (Either.isRight(reencoded)) {
        expect(Array.from(reencoded.right)).toEqual(Array.from(encoded.right))
      }
    }
    const text = new TextDecoder().decode(encoded.right)
    expect(
      Either.isLeft(
        decodeCanonicalAtomV2TransitionEvidenceRecordBytes(utf8(` ${text}`))
      )
    ).toBe(true)
  }
  expect(
    Either.isLeft(
      decodeCanonicalAtomV2TransitionEvidenceRecordBytes(
        utf8('{"_tag":"x","_tag":"y"}')
      )
    )
  ).toBe(true)
  const authorizationBytes = canonicalAtomV2TransitionEvidenceRecordBytes(
    value.authorization
  )
  expect(Either.isRight(authorizationBytes)).toBe(true)
  if (Either.isRight(authorizationBytes)) {
    const text = new TextDecoder().decode(authorizationBytes.right)
    const nestedDuplicate = text.replace(
      '"claimant":{"address":"principal:claimant"}',
      '"claimant":{"address":"principal:claimant","address":"principal:forged"}'
    )
    expect(nestedDuplicate).not.toBe(text)
    expect(
      Either.isLeft(
        decodeCanonicalAtomV2TransitionEvidenceRecordBytes(
          utf8(nestedDuplicate)
        )
      )
    ).toBe(true)
  }
  const {
    admissionStatus: dispositionAdmissionStatus,
    ...dispositionRest
  } = value.disposition!
  const reorderedDisposition = JSON.stringify({
    admissionStatus: dispositionAdmissionStatus,
    ...dispositionRest
  })
  expect(
    Either.isLeft(
      decodeCanonicalAtomV2TransitionEvidenceRecordBytes(
        utf8(reorderedDisposition)
      )
    )
  ).toBe(true)
  expect(
    Either.isLeft(
      decodeCanonicalAtomV2TransitionEvidenceRecordBytes(
        Uint8Array.from([0xff])
      )
    )
  ).toBe(true)
})

it("fails at the intended proposal, self-write, schema, trace, and time guards", () => {
  const minimal = minimalBundle()
  expectBundleFailure(
    {
      ...minimal,
      proposalDescriptor: {
        ...minimal.proposalDescriptor,
        mediaType: "application/json"
      }
    },
    "DESCRIPTOR_INVALID"
  )
  expectBundleFailure(
    { ...minimal, claimedPredecessorStateRevision: 999 },
    "CROSS_FIELD_MISMATCH"
  )
  expectBundleFailure(bundle(false, "authorization"), "CROSS_FIELD_MISMATCH")
  expectBundleFailure(bundle(false, "trace"), "CROSS_FIELD_MISMATCH")
  expectBundleFailure(
    {
      ...minimal,
      trajectory: { ...minimal.trajectory, traceRef: key("wrong-trace-ref") }
    },
    "CROSS_FIELD_MISMATCH"
  )
  expectBundleFailure(
    {
      ...minimal,
      trajectory: { ...minimal.trajectory, traceId: "wrong-trace-id" }
    },
    "CROSS_FIELD_MISMATCH"
  )
  expectBundleFailure(
    {
      ...minimal,
      authorization: {
        ...minimal.authorization,
        decisionRef: minimal.trajectory.traceRef
      }
    },
    "CROSS_FIELD_MISMATCH"
  )
  const otherSchemaSubject = {
    ...minimal.roles.subjects[0]!,
    subject: {
      ...minimal.roles.subjects[0]!.subject,
      schemaVersion: "hswm:other:schema"
    }
  }
  expectBundleFailure(
    {
      ...minimal,
      roles: { ...minimal.roles, subjects: [otherSchemaSubject] },
      authorization: {
        ...minimal.authorization,
        subjects: [otherSchemaSubject]
      }
    },
    "CROSS_FIELD_MISMATCH"
  )
  expectBundleFailure(
    {
      ...minimal,
      trajectory: {
        ...minimal.trajectory,
        events: [{ sequence: 1, kind: "INPUT", content: opaque("gap") }]
      }
    },
    "TRACE_INVALID"
  )
  expectBundleFailure(
    {
      ...minimal,
      trajectory: {
        ...minimal.trajectory,
        events: [
          { sequence: 0, kind: "OUTCOME", content: opaque("post-outcome") }
        ]
      }
    },
    "EVIDENCE_INVALID"
  )
  expectBundleFailure(
    {
      ...minimal,
      trajectory: {
        ...minimal.trajectory,
        sealedAt: "2026-08-27T00:00:01.501Z"
      }
    },
    "TIME_INVALID"
  )
  expectBundleFailure(
    {
      ...minimal,
      authorization: {
        ...minimal.authorization,
        notBefore: minimal.authorization.expiresAt
      }
    },
    "TIME_INVALID"
  )
  expectBundleFailure(
    {
      ...minimal,
      authorization: {
        ...minimal.authorization,
        revocationStatus: "NOT_CHECKED",
        revocationCheckedAt: "2026-08-27T00:00:01.000Z"
      }
    },
    "TIME_INVALID"
  )
})

it("fails at the intended effect, outcome, independence, and disposition guards", () => {
  const value = bundle()
  expectBundleFailure(
    {
      ...value,
      outcome: null,
      disposition: null,
      effect: {
        ...value.effect!,
        authorization: {
          ...value.effect!.authorization,
          mediaType: "application/json"
        }
      }
    },
    "CROSS_FIELD_MISMATCH"
  )
  expectBundleFailure(
    {
      ...value,
      outcome: null,
      disposition: null,
      effect: { ...value.effect!, trajectory: opaque("wrong-trace") }
    },
    "CROSS_FIELD_MISMATCH"
  )
  expectBundleFailure(
    {
      ...value,
      outcome: null,
      disposition: null,
      effect: { ...value.effect!, actorClaim: "principal:forged" }
    },
    "CROSS_FIELD_MISMATCH"
  )

  const outcomeCases: ReadonlyArray<unknown> = [
    { ...value.outcome!, observedAt: "2026-08-27T00:00:00.000Z" },
    {
      ...value.outcome!,
      outcome: "UNKNOWN",
      observation: opaque("forbidden-unknown-payload")
    },
    { ...value.outcome!, outcome: "OBSERVED", observation: null },
    { ...value.outcome!, outcome: "FAILED", observation: null },
    {
      ...value.outcome!,
      independence: "UNKNOWN",
      independenceEvidence: opaque("forbidden")
    },
    {
      ...value.outcome!,
      independence: "DECLARED_ROLE_SEPARATION_NOT_PROVEN",
      independenceEvidence: null
    },
    { ...value.outcome!, evaluator: { address: "principal:claimant" } },
    { ...value.outcome!, evaluator: { address: "principal:authorizer" } },
    { ...value.outcome!, evaluator: { address: "principal:sealer" } },
    { ...value.outcome!, evaluator: { address: "principal:custodian" } },
    { ...value.outcome!, evaluator: { address: "principal:owner" } }
  ]
  for (const outcome of outcomeCases) {
    expectBundleFailure(
      { ...value, outcome, disposition: null },
      "OUTCOME_INVALID"
    )
  }

  expectBundleFailure(
    {
      ...value,
      disposition: { ...value.disposition, disposition: "ACCEPTED" }
    },
    "EVIDENCE_INVALID"
  )
  expectBundleFailure(
    {
      ...value,
      disposition: { ...value.disposition!, retention: null }
    },
    "DISPOSITION_INVALID"
  )
  expectBundleFailure(
    {
      ...value,
      disposition: {
        ...value.disposition!,
        disposition: "REJECTED",
        retention: opaque("forbidden-retention")
      }
    },
    "DISPOSITION_INVALID"
  )
  expectBundleFailure(
    {
      ...value,
      disposition: {
        ...value.disposition,
        candidate: { ...opaque("candidate-with-key"), key: key("forbidden") }
      }
    },
    "EVIDENCE_INVALID"
  )
  expectBundleFailure(
    {
      ...value,
      disposition: { ...value.disposition, candidate: opaque("other") }
    },
    "CROSS_FIELD_MISMATCH"
  )
  expectBundleFailure(
    {
      ...value,
      disposition: {
        ...value.disposition!,
        custodian: { address: "principal:undeclared-custodian" }
      }
    },
    "ROLE_BINDING_INVALID"
  )
  expectBundleFailure(
    {
      ...value,
      roles: {
        ...value.roles,
        custodians: value.roles.custodians.map((custody) =>
          custody.custody === "QUARANTINE"
            ? { ...custody, object: opaque("wrong-quarantine-object") }
            : custody
        )
      }
    },
    "ROLE_BINDING_INVALID"
  )
  expectBundleFailure(
    {
      ...value,
      roles: {
        ...value.roles,
        custodians: value.roles.custodians.filter(
          ({ custody }) => custody !== "QUARANTINE"
        )
      }
    },
    "ROLE_BINDING_INVALID"
  )
})

it("keeps invalid standalone record evidence outside classification", () => {
  const authorization = bundle().authorization
  const checked = validateCanonicalAtomV2TransitionEvidenceRecord({
    ...authorization,
    notBefore: authorization.expiresAt
  })
  expect(Either.isLeft(checked)).toBe(true)
  if (Either.isLeft(checked)) expect(checked.left.code).toBe("EVIDENCE_INVALID")
})

it("rejects noncanonical bundle bytes and returns clone-independent frozen validation", () => {
  const value = bundle()
  const encoded = canonicalAtomV2TransitionEvidenceBundleBytes(value)
  expect(Either.isRight(encoded)).toBe(true)
  if (Either.isLeft(encoded)) return
  const described = describeCanonicalAtomV2TransitionEvidenceBundle(value)
  expect(Either.isRight(described)).toBe(true)
  if (Either.isRight(described)) {
    expect(described.right.mediaType).toBe(
      HSWM_CANONICAL_TRANSITION_EVIDENCE_BUNDLE_V1_MEDIA_TYPE
    )
    expect(described.right.byteLength).toBe(encoded.right.byteLength)
    expect(described.right.sha256).toBe(sha256(encoded.right))
  }
  const decoded = decodeCanonicalAtomV2TransitionEvidenceBundleBytes(
    encoded.right
  )
  expect(Either.isRight(decoded)).toBe(true)
  if (Either.isRight(decoded)) expect(Object.isFrozen(decoded.right)).toBe(true)
  const text = new TextDecoder().decode(encoded.right)
  expect(Either.isLeft(decodeCanonicalAtomV2TransitionEvidenceBundleBytes(utf8(` ${text}`)))).toBe(true)
  expect(Either.isLeft(decodeCanonicalAtomV2TransitionEvidenceBundleBytes(utf8('{"_tag":"x","_tag":"y"}')))).toBe(true)
  const { schema: bundleSchema, ...bundleRest } = value
  expect(
    Either.isLeft(
      decodeCanonicalAtomV2TransitionEvidenceBundleBytes(
        utf8(JSON.stringify({ schema: bundleSchema, ...bundleRest }))
      )
    )
  ).toBe(true)
  const frozen = snapshotCanonicalAtomV2TransitionEvidenceBundle(value)
  expect(Object.isFrozen(frozen)).toBe(true)
  expect(Object.isFrozen(frozen.roles.owners)).toBe(true)
  expect(Object.isFrozen(frozen.roles.owners[0]!.owner)).toBe(true)
  const checked = validateCanonicalAtomV2TransitionEvidenceBundle(value)
  expect(Either.isRight(checked)).toBe(true)
  if (Either.isRight(checked)) {
    const checkedBytes = canonicalAtomV2TransitionEvidenceBundleBytes(
      checked.right
    )
    expect(Either.isRight(checkedBytes)).toBe(true)
    ;(value.roles.owners[0]!.owner as { address: string }).address =
      "principal:mutated"
    expect(checked.right.roles.owners[0]!.owner.address).toBe(
      "principal:owner"
    )
    const afterMutation = canonicalAtomV2TransitionEvidenceBundleBytes(
      checked.right
    )
    expect(Either.isRight(afterMutation)).toBe(true)
    if (Either.isRight(checkedBytes) && Either.isRight(afterMutation)) {
      expect(Array.from(afterMutation.right)).toEqual(
        Array.from(checkedBytes.right)
      )
    }
  }
})
