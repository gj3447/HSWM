import { createHash } from "node:crypto"

import { expect, it } from "@effect/vitest"
import { Effect, Either } from "effect"

import {
  HSWM_CANONICAL_ATOM_ENVELOPE_V2_MEDIA_TYPE,
  HSWM_CANONICAL_SCHEMA_CONTENT_V2_MEDIA_TYPE,
  canonicalAtomV2SchemaContentBytes,
  describeCanonicalAtomV2Envelope,
  makeCanonicalAtomV2ContentBoundInput,
  type CanonicalAtomV2ContentAuthorizationGrant,
  type CanonicalAtomV2WriteContentBinding
} from "../src/canonical-atom-v2-content-bound.js"
import {
  makeCanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2SchemaContentBinding
} from "../src/canonical-atom-v2-content.js"
import {
  HSWM_CANONICAL_CURRENT_STATE_PERMIT_INPUT_V1_MEDIA_TYPE,
  HSWM_CANONICAL_CURRENT_STATE_PERMIT_RECORD_V1_MEDIA_TYPE,
  HSWM_CANONICAL_CURRENT_STATE_PERMIT_RESOLUTION_V1_MEDIA_TYPE,
  HSWM_CANONICAL_CURRENT_STATE_PERMIT_V1_CONTRACT_VERSION,
  HSWM_CANONICAL_AUTHORIZATION_DECISION_V1_KIND,
  HSWM_CANONICAL_CONSENT_DECISION_V1_KIND,
  HSWM_CANONICAL_PERMIT_AUTHORIZATION_REFERENCE_TYPE,
  HSWM_CANONICAL_PERMIT_AUTHORIZATION_ROLE,
  HSWM_CANONICAL_PERMIT_POLICY_REFERENCE_TYPE,
  HSWM_CANONICAL_PERMIT_POLICY_ROLE,
  HSWM_CANONICAL_PERMIT_POLICY_V1_KIND,
  HSWM_CANONICAL_PERMIT_SUBJECT_REFERENCE_TYPE,
  HSWM_CANONICAL_PERMIT_SUBJECT_ROLE,
  HSWM_CANONICAL_TRAJECTORY_CONTRACT_V1_KIND,
  canonicalAtomV2CurrentStatePermitInputBytes,
  canonicalAtomV2CurrentStatePermitRecordBytes,
  canonicalAtomV2CurrentStatePermitResolutionBytes,
  decodeCanonicalAtomV2CurrentStatePermitInputBytes,
  decodeCanonicalAtomV2CurrentStatePermitRecordBytes,
  decodeCanonicalAtomV2CurrentStatePermitResolutionBytes,
  describeCanonicalAtomV2CurrentStatePermitInput,
  describeCanonicalAtomV2CurrentStatePermitRecord,
  describeCanonicalAtomV2CurrentStatePermitResolution,
  resolveCanonicalAtomV2CurrentStatePermitEligibility,
  resolveCanonicalAtomV2CurrentStatePermitEligibilityAtDurableRuntime,
  validateCanonicalAtomV2CurrentStatePermitInput,
  type CanonicalAtomV2AuthorizationDecisionRecord,
  type CanonicalAtomV2ConsentDecisionRecord,
  type CanonicalAtomV2CurrentStatePermitError,
  type CanonicalAtomV2CurrentStatePermitInput,
  type CanonicalAtomV2PermitPolicyRecord,
  type CanonicalAtomV2TrajectoryContractRecord
} from "../src/canonical-atom-v2-current-state-permit.js"
import {
  CanonicalAtomV2DurableRuntime,
  makeCanonicalAtomV2DurableRuntimeMemoryLayerForTest
} from "../src/canonical-atom-v2-durable-runtime.js"
import { canonicalAtomV2StateSha256 } from "../src/canonical-atom-v2-state-journal.js"
import {
  HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_V1_CONTRACT_VERSION,
  HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_V1_MEDIA_TYPE,
  describeCanonicalAtomV2StateJournalRecord,
  type CanonicalAtomV2StateJournalCommit
} from "../src/canonical-atom-v2-state-journal.js"
import {
  HSWM_CANONICAL_TRANSITION_EVIDENCE_RECORD_V1_MEDIA_TYPE,
  HSWM_CANONICAL_TRANSITION_PROPOSAL_V1_MEDIA_TYPE,
  describeCanonicalAtomV2TransitionEvidenceRecord,
  type CanonicalAtomV2TransitionEvidenceBundle
} from "../src/canonical-atom-v2-transition-evidence.js"
import { canonicalJsonBytes } from "../src/canonical-atom-v2-json.js"
import {
  HSWM_SUPERSEDES_REFERENCE_ROLE,
  HSWM_SUPERSEDES_REFERENCE_TYPE,
  canonicalAtomV2KeyId,
  type CanonicalAtomV2,
  type CanonicalAtomV2Key,
  type HSWMCanonicalSchemaV2
} from "../src/canonical-atom-v2-schema.js"
import type { CanonicalAtomV2State } from "../src/canonical-atom-v2-domain.js"

const SCHEMA_VERSION = "hswm:test:current-permit:v2"
const JOURNAL_LINEAGE = "journal:current-permit"
const EVALUATED_AT = "2026-08-27T12:00:00.000Z"
const PURPOSE = "purpose:canonical-admission"
const SCOPE = "scope:canonical-write"

const unwrap = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw value.left
  return value.right
}

const descriptor = (mediaType: string, value: unknown) => {
  const bytes = unwrap(canonicalJsonBytes(value))
  return unwrap(makeCanonicalAtomV2ContentDescriptor(mediaType, bytes))
}

const opaque = (id: string) => descriptor("application/json", { id })

const key = (
  atomUid: string,
  lineageId = `lineage:${atomUid}`,
  revisionId = 0
): CanonicalAtomV2Key => ({
  schemaVersion: SCHEMA_VERSION,
  lineageId,
  atomUid,
  revisionId
})

const subjectKey = key("atom:subject")
const readKey = key("atom:read")
const policyKey = key("atom:permit-policy")
const authorizationKey = key("authorization:current")
const consentKey = key("atom:consent")
const traceKey = key("atom:trace-contract")
const writeKey = key("atom:candidate-write")

const supersedesContract = (kind: string) => ({
  referenceType: HSWM_SUPERSEDES_REFERENCE_TYPE,
  roles: [{
    role: HSWM_SUPERSEDES_REFERENCE_ROLE,
    targetKinds: [kind],
    minimum: 0,
    maximum: 1
  }]
})

const relationContract = (
  referenceType: string,
  role: string,
  targetKind: string,
  maximum = 1
) => ({
  referenceType,
  roles: [{ role, targetKinds: [targetKind], minimum: 1, maximum }]
})

const schema: HSWMCanonicalSchemaV2 = {
  _tag: "HSWMCanonicalSchemaV2",
  contractVersion: "hswm-canonical-schema-contract/v2",
  schemaVersion: SCHEMA_VERSION,
  scientificStatus: "UNJUDGED",
  bootstrapTrustStatement:
    "Fixture schema for exact local-head-relative Permit eligibility only.",
  owners: [
    { address: "owner:state", obligation: "Own exact state records." },
    { address: "owner:write", obligation: "Own candidate writes." },
    { address: "principal:authorizer", obligation: "May also own records without deriving authority." }
  ],
  kinds: [
    {
      kind: "kind:subject",
      form: "ENTITY",
      revisionPolicy: "SINGLETON",
      allowedOwners: ["owner:state", "principal:authorizer"],
      minimumArity: 0,
      referenceContracts: []
    },
    {
      kind: "kind:read",
      form: "ENTITY",
      revisionPolicy: "SINGLETON",
      allowedOwners: ["owner:state"],
      minimumArity: 0,
      referenceContracts: []
    },
    {
      kind: HSWM_CANONICAL_PERMIT_POLICY_V1_KIND,
      form: "ENTITY",
      revisionPolicy: "LINEAR",
      allowedOwners: ["owner:state", "principal:authorizer"],
      minimumArity: 0,
      referenceContracts: [supersedesContract(HSWM_CANONICAL_PERMIT_POLICY_V1_KIND)]
    },
    {
      kind: HSWM_CANONICAL_AUTHORIZATION_DECISION_V1_KIND,
      form: "RELATION",
      revisionPolicy: "LINEAR",
      allowedOwners: ["owner:state", "principal:authorizer"],
      minimumArity: 2,
      referenceContracts: [
        supersedesContract(HSWM_CANONICAL_AUTHORIZATION_DECISION_V1_KIND),
        relationContract(
          HSWM_CANONICAL_PERMIT_POLICY_REFERENCE_TYPE,
          HSWM_CANONICAL_PERMIT_POLICY_ROLE,
          HSWM_CANONICAL_PERMIT_POLICY_V1_KIND
        ),
        relationContract(
          HSWM_CANONICAL_PERMIT_SUBJECT_REFERENCE_TYPE,
          HSWM_CANONICAL_PERMIT_SUBJECT_ROLE,
          "kind:subject",
          256
        )
      ]
    },
    {
      kind: HSWM_CANONICAL_CONSENT_DECISION_V1_KIND,
      form: "RELATION",
      revisionPolicy: "LINEAR",
      allowedOwners: ["owner:state"],
      minimumArity: 2,
      referenceContracts: [
        supersedesContract(HSWM_CANONICAL_CONSENT_DECISION_V1_KIND),
        relationContract(
          HSWM_CANONICAL_PERMIT_POLICY_REFERENCE_TYPE,
          HSWM_CANONICAL_PERMIT_POLICY_ROLE,
          HSWM_CANONICAL_PERMIT_POLICY_V1_KIND
        ),
        relationContract(
          HSWM_CANONICAL_PERMIT_SUBJECT_REFERENCE_TYPE,
          HSWM_CANONICAL_PERMIT_SUBJECT_ROLE,
          "kind:subject"
        )
      ]
    },
    {
      kind: HSWM_CANONICAL_TRAJECTORY_CONTRACT_V1_KIND,
      form: "RELATION",
      revisionPolicy: "LINEAR",
      allowedOwners: ["owner:state"],
      minimumArity: 2,
      referenceContracts: [
        supersedesContract(HSWM_CANONICAL_TRAJECTORY_CONTRACT_V1_KIND),
        relationContract(
          HSWM_CANONICAL_PERMIT_POLICY_REFERENCE_TYPE,
          HSWM_CANONICAL_PERMIT_POLICY_ROLE,
          HSWM_CANONICAL_PERMIT_POLICY_V1_KIND
        ),
        relationContract(
          HSWM_CANONICAL_PERMIT_AUTHORIZATION_REFERENCE_TYPE,
          HSWM_CANONICAL_PERMIT_AUTHORIZATION_ROLE,
          HSWM_CANONICAL_AUTHORIZATION_DECISION_V1_KIND
        )
      ]
    },
    {
      kind: "kind:write",
      form: "ENTITY",
      revisionPolicy: "SINGLETON",
      allowedOwners: ["owner:write"],
      minimumArity: 0,
      referenceContracts: []
    }
  ]
}

const schemaBinding = (): CanonicalAtomV2SchemaContentBinding => {
  const bytes = unwrap(canonicalAtomV2SchemaContentBytes(schema))
  return {
    schemaVersion: SCHEMA_VERSION,
    content: unwrap(
      makeCanonicalAtomV2ContentDescriptor(
        HSWM_CANONICAL_SCHEMA_CONTENT_V2_MEDIA_TYPE,
        bytes
      )
    )
  }
}

interface FixtureOptions {
  readonly authorizationDecision?: "GRANTED" | "DENIED"
  readonly authorizationRevocation?: "CURRENT" | "REVOKED" | "STALE" | "FUTURE" | "UNCHECKED"
  readonly consentDecision?: "GRANTED" | "WITHDRAWN" | "DENIED"
  readonly consentRevocation?: "CURRENT" | "REVOKED" | "STALE" | "FUTURE" | "UNCHECKED"
  readonly intentPurpose?: string
  readonly policyPurpose?: string
  readonly policyActive?: boolean
  readonly controller?: string
  readonly consenter?: string
  readonly authorizer?: string
  readonly policyAuthorizers?: ReadonlyArray<string>
  readonly recordOwner?: string
  readonly omitPolicyRead?: boolean
  readonly replay?: boolean
  readonly wrongPolicyContent?: boolean
}

const revocation = (
  mode: NonNullable<FixtureOptions["authorizationRevocation"]>
) => {
  switch (mode) {
    case "REVOKED":
      return {
        revocationStatus: "REVOKED" as const,
        revocationCheckedAt: EVALUATED_AT,
        revokedAt: EVALUATED_AT,
        revocationEvidence: opaque("revoked")
      }
    case "STALE":
      return {
        revocationStatus: "CHECKED_NOT_REVOKED" as const,
        revocationCheckedAt: "2026-08-27T11:59:59.999Z",
        revokedAt: null,
        revocationEvidence: opaque("stale-check")
      }
    case "FUTURE":
      return {
        revocationStatus: "CHECKED_NOT_REVOKED" as const,
        revocationCheckedAt: "2026-08-27T12:00:00.001Z",
        revokedAt: null,
        revocationEvidence: opaque("future-check")
      }
    case "UNCHECKED":
      return {
        revocationStatus: "NOT_CHECKED" as const,
        revocationCheckedAt: null,
        revokedAt: null,
        revocationEvidence: null
      }
    default:
      return {
        revocationStatus: "CHECKED_NOT_REVOKED" as const,
        revocationCheckedAt: EVALUATED_AT,
        revokedAt: null,
        revocationEvidence: opaque("current-check")
      }
  }
}

const atom = (
  atomKey: CanonicalAtomV2Key,
  kind: string,
  owner: string,
  content: CanonicalAtomV2ContentDescriptor,
  references: CanonicalAtomV2["references"] = []
): CanonicalAtomV2 => ({
  _tag: "CanonicalAtomV2",
  contractVersion: "hswm-canonical-atom/v2",
  key: atomKey,
  kind,
  responsibilityOwner: owner,
  content,
  provenance: {
    mode: "BOOTSTRAP",
    evidenceSha256: createHash("sha256").update(atomKey.atomUid).digest("hex"),
    sourceRef: null
  },
  lifecycle: "ADMITTED",
  references
})

const permitFixture = (
  options: FixtureOptions = {}
): CanonicalAtomV2CurrentStatePermitInput => {
  const binding = schemaBinding()
  const authorizer = options.authorizer ?? "principal:authorizer"
  const controller = options.controller ?? "principal:controller"
  const consenter = options.consenter ?? controller
  const intentPurpose = options.intentPurpose ?? PURPOSE
  const policyPurpose = options.policyPurpose ?? PURPOSE
  const authorizationRevocation = revocation(
    options.authorizationRevocation ?? "CURRENT"
  )
  const consentRevocation = revocation(options.consentRevocation ?? "CURRENT")
  const subjects = [{
    subject: subjectKey,
    relation: "relation:affected-subject"
  }]
  const policy: CanonicalAtomV2PermitPolicyRecord = {
    _tag: "CanonicalAtomV2PermitPolicyRecord",
    contractVersion: HSWM_CANONICAL_CURRENT_STATE_PERMIT_V1_CONTRACT_VERSION,
    policyRef: policyKey,
    schema: binding,
    decision: options.policyActive === false ? "SUSPENDED" : "ACTIVE",
    scopeRules: [{
      scope: SCOPE,
      purpose: policyPurpose,
      authorizers: (options.policyAuthorizers ?? [authorizer])
        .map((address) => ({ address }))
        .sort((left, right) => left.address.localeCompare(right.address)),
      allowedWriteKinds: ["kind:write"]
    }],
    consentSlots: [{
      subject: subjects[0]!,
      consentLineageId: consentKey.lineageId,
      consentAtomUid: consentKey.atomUid,
      controllers: [{ address: controller }]
    }],
    policyStatus: "REPRESENTED_STATE_POLICY_NOT_CANONICAL_PERMIT"
  }
  const authorizationDecision: CanonicalAtomV2AuthorizationDecisionRecord = {
    _tag: "CanonicalAtomV2AuthorizationDecisionRecord",
    contractVersion: HSWM_CANONICAL_CURRENT_STATE_PERMIT_V1_CONTRACT_VERSION,
    decisionRef: authorizationKey,
    policyRef: policyKey,
    schema: binding,
    authorizationRef: authorizationKey.atomUid,
    claimant: { address: "principal:claimant" },
    subjects,
    authorizer: { address: authorizer },
    scope: SCOPE,
    purpose: intentPurpose,
    decision: options.authorizationDecision ?? "GRANTED",
    decidedAt: "2026-08-27T11:59:00.000Z",
    notBefore: "2026-08-27T11:00:00.000Z",
    expiresAt: "2026-08-27T13:00:00.000Z",
    authorityEvidence: opaque("authority-evidence"),
    ...authorizationRevocation,
    decisionStatus: "REPRESENTED_STATE_AUTHORIZATION_NOT_CANONICAL_PERMIT"
  }
  const consent: CanonicalAtomV2ConsentDecisionRecord = {
    _tag: "CanonicalAtomV2ConsentDecisionRecord",
    contractVersion: HSWM_CANONICAL_CURRENT_STATE_PERMIT_V1_CONTRACT_VERSION,
    consentRef: consentKey,
    policyRef: policyKey,
    schema: binding,
    subject: subjects[0]!,
    consenter: { address: consenter },
    claimant: { address: "principal:claimant" },
    scope: SCOPE,
    purpose: intentPurpose,
    decision: options.consentDecision ?? "GRANTED",
    decidedAt: "2026-08-27T11:58:00.000Z",
    notBefore: "2026-08-27T11:00:00.000Z",
    expiresAt: "2026-08-27T13:00:00.000Z",
    decisionEvidence: opaque("consent-evidence"),
    ...consentRevocation,
    consentStatus: "REPRESENTED_STATE_CONSENT_NOT_CANONICAL_PERMIT"
  }
  const trajectoryContract: CanonicalAtomV2TrajectoryContractRecord = {
    _tag: "CanonicalAtomV2TrajectoryContractRecord",
    contractVersion: HSWM_CANONICAL_CURRENT_STATE_PERMIT_V1_CONTRACT_VERSION,
    traceRef: traceKey,
    policyRef: policyKey,
    schema: binding,
    claimant: { address: "principal:claimant" },
    allowedSealers: [{ address: "principal:sealer" }],
    scope: SCOPE,
    purpose: intentPurpose,
    decision: "ACTIVE",
    contractEvidence: opaque("trajectory-contract"),
    trajectoryStatus: "PRE_EXISTING_CONTRACT_NOT_EXECUTION_NOT_OUTCOME"
  }

  const policyDescriptor = unwrap(
    describeCanonicalAtomV2CurrentStatePermitRecord(policy)
  )
  const authorizationDescriptor = unwrap(
    describeCanonicalAtomV2CurrentStatePermitRecord(authorizationDecision)
  )
  const consentDescriptor = unwrap(
    describeCanonicalAtomV2CurrentStatePermitRecord(consent)
  )
  const trajectoryContractDescriptor = unwrap(
    describeCanonicalAtomV2CurrentStatePermitRecord(trajectoryContract)
  )
  const recordOwner = options.recordOwner ?? "owner:state"
  const atoms: ReadonlyArray<CanonicalAtomV2> = [
    atom(subjectKey, "kind:subject", recordOwner, opaque("subject")),
    atom(readKey, "kind:read", "owner:state", opaque("read")),
    atom(
      policyKey,
      HSWM_CANONICAL_PERMIT_POLICY_V1_KIND,
      recordOwner,
      options.wrongPolicyContent ? opaque("wrong-policy") : policyDescriptor
    ),
    atom(
      authorizationKey,
      HSWM_CANONICAL_AUTHORIZATION_DECISION_V1_KIND,
      recordOwner,
      authorizationDescriptor,
      [
        {
          referenceType: HSWM_CANONICAL_PERMIT_POLICY_REFERENCE_TYPE,
          role: HSWM_CANONICAL_PERMIT_POLICY_ROLE,
          target: policyKey
        },
        {
          referenceType: HSWM_CANONICAL_PERMIT_SUBJECT_REFERENCE_TYPE,
          role: HSWM_CANONICAL_PERMIT_SUBJECT_ROLE,
          target: subjectKey
        }
      ]
    ),
    atom(
      consentKey,
      HSWM_CANONICAL_CONSENT_DECISION_V1_KIND,
      "owner:state",
      consentDescriptor,
      [
        {
          referenceType: HSWM_CANONICAL_PERMIT_POLICY_REFERENCE_TYPE,
          role: HSWM_CANONICAL_PERMIT_POLICY_ROLE,
          target: policyKey
        },
        {
          referenceType: HSWM_CANONICAL_PERMIT_SUBJECT_REFERENCE_TYPE,
          role: HSWM_CANONICAL_PERMIT_SUBJECT_ROLE,
          target: subjectKey
        }
      ]
    ),
    atom(
      traceKey,
      HSWM_CANONICAL_TRAJECTORY_CONTRACT_V1_KIND,
      "owner:state",
      trajectoryContractDescriptor,
      [
        {
          referenceType: HSWM_CANONICAL_PERMIT_POLICY_REFERENCE_TYPE,
          role: HSWM_CANONICAL_PERMIT_POLICY_ROLE,
          target: policyKey
        },
        {
          referenceType: HSWM_CANONICAL_PERMIT_AUTHORIZATION_REFERENCE_TYPE,
          role: HSWM_CANONICAL_PERMIT_AUTHORIZATION_ROLE,
          target: authorizationKey
        }
      ]
    )
  ].sort((left, right) =>
    canonicalAtomV2KeyId(left.key).localeCompare(
      canonicalAtomV2KeyId(right.key)
    )
  )
  const state: CanonicalAtomV2State = {
    schemaVersion: SCHEMA_VERSION,
    revision: 1,
    bootstrapClosed: true,
    atoms,
    acceptedTransitionIds: [
      options.replay ? "transition:permit-candidate" : "transition:bootstrap"
    ]
  }
  const stateSha256 = unwrap(canonicalAtomV2StateSha256(state))
  const headRecord: CanonicalAtomV2StateJournalCommit = {
    _tag: "CanonicalAtomV2StateJournalCommit",
    contractVersion:
      HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_V1_CONTRACT_VERSION,
    encoding: "hswm-canonical-json/v1",
    journalLineageId: JOURNAL_LINEAGE,
    schema: binding,
    stateRevision: state.revision,
    predecessor: {
      mediaType: HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_V1_MEDIA_TYPE,
      byteLength: 1,
      sha256: "1".repeat(64)
    },
    receipt: {
      _tag: "CanonicalAtomV2EffectReceipt",
      contractVersion: "hswm-canonical-effect-receipt/v2",
      transitionId: "transition:bootstrap",
      schemaVersion: SCHEMA_VERSION,
      previousStateRevision: 0,
      nextStateRevision: 1,
      readSet: [],
      writeSet: atoms.map(({ key: atomKey }) => atomKey),
      traceRef: null,
      guard: {
        schema: "PASSED",
        ownerTotality: "PASSED",
        references: "PASSED",
        revision: "PASSED",
        permission: "REFERENCE_GRANT_MATCHED_NOT_CANONICAL_PERMIT"
      },
      actorClaim: "principal:bootstrap",
      authorizationRef: "authorization:bootstrap",
      scope: "scope:bootstrap",
      decidedAt: "2026-08-27T10:00:00.000Z",
      decision: "ACCEPTED",
      provenanceSha256: "2".repeat(64)
    },
    writeBindings: atoms.map((stateAtom) => ({
      key: stateAtom.key,
      payload: stateAtom.content,
      envelope: {
        mediaType: HSWM_CANONICAL_ATOM_ENVELOPE_V2_MEDIA_TYPE,
        byteLength: 1,
        sha256: createHash("sha256")
          .update(canonicalAtomV2KeyId(stateAtom.key))
          .digest("hex")
      }
    })),
    previousStateSha256: "3".repeat(64),
    resultingStateSha256: stateSha256,
    durability:
      "LOCAL_PREDECESSOR_BOUND_JOURNAL_V1_NOT_CANONICAL_PERMIT_NOT_LEARNING"
  }
  const headDescriptor = unwrap(
    describeCanonicalAtomV2StateJournalRecord(headRecord)
  )
  const readSet = [
    authorizationKey,
    consentKey,
    policyKey,
    readKey,
    subjectKey,
    traceKey
  ]
    .filter((entry) => !(options.omitPolicyRead && entry === policyKey))
    .sort((left, right) =>
      canonicalAtomV2KeyId(left).localeCompare(canonicalAtomV2KeyId(right))
    )
  const write = atom(
    writeKey,
    "kind:write",
    "owner:write",
    opaque("candidate-write")
  )
  const proposal = {
    _tag: "CommitCanonicalAtomsV2" as const,
    contractVersion: "hswm-canonical-transition/v2" as const,
    transitionId: "transition:permit-candidate",
    expectedStateRevision: state.revision,
    schemaVersion: SCHEMA_VERSION,
    actorClaim: "principal:claimant",
    authorizationRef: authorizationKey.atomUid,
    scope: SCOPE,
    decidedAt: EVALUATED_AT,
    traceRef: traceKey,
    readSet,
    writes: [write],
    provenanceSha256: "4".repeat(64)
  }
  const proposalDescriptor = descriptor(
    HSWM_CANONICAL_TRANSITION_PROPOSAL_V1_MEDIA_TYPE,
    proposal
  )
  const representedAuthorization = {
    _tag: "CanonicalAtomV2AuthorizationDecisionEvidence" as const,
    contractVersion: "hswm-canonical-transition-evidence/v1" as const,
    authorizationRef: authorizationDecision.authorizationRef,
    decisionRef: authorizationDecision.decisionRef,
    schema: binding,
    claimedPredecessor: headDescriptor,
    claimedPredecessorStateRevision: state.revision,
    proposal: proposalDescriptor,
    claimant: authorizationDecision.claimant,
    subjects,
    authorizer: authorizationDecision.authorizer,
    scope: SCOPE,
    decision: authorizationDecision.decision,
    decidedAt: authorizationDecision.decidedAt,
    notBefore: authorizationDecision.notBefore,
    expiresAt: authorizationDecision.expiresAt,
    decisionEvidence: authorizationDescriptor,
    revocationStatus: authorizationDecision.revocationStatus,
    revocationCheckedAt: authorizationDecision.revocationCheckedAt,
    revokedAt: authorizationDecision.revokedAt,
    revocationEvidence: authorizationDecision.revocationEvidence,
    permitStatus: "REPRESENTED_NOT_CANONICAL_PERMIT" as const
  }
  const trajectory = {
    _tag: "CanonicalAtomV2SealedTrajectoryEvidence" as const,
    contractVersion: "hswm-canonical-transition-evidence/v1" as const,
    traceId: traceKey.atomUid,
    schema: binding,
    claimedPredecessor: headDescriptor,
    claimedPredecessorStateRevision: state.revision,
    proposal: proposalDescriptor,
    traceRef: traceKey,
    claimant: { address: "principal:claimant" },
    sealer: { address: "principal:sealer" },
    readSet,
    writeSet: [writeKey],
    events: [{ sequence: 0, kind: "INPUT" as const, content: opaque("input") }],
    sealedAt: EVALUATED_AT,
    provenance: {
      collector: { address: "principal:collector" },
      method: "method:fixture",
      collectedAt: "2026-08-27T11:59:59.000Z",
      source: opaque("trajectory-source"),
      status: "CLAIMED_NOT_TRUTH" as const
    }
  }
  const evidence: CanonicalAtomV2TransitionEvidenceBundle = {
    _tag: "CanonicalAtomV2TransitionEvidenceBundle",
    contractVersion: "hswm-canonical-transition-evidence/v1",
    schema: binding,
    claimedPredecessor: headDescriptor,
    claimedPredecessorStateRevision: state.revision,
    proposal,
    proposalDescriptor,
    roles: {
      owners: [{ write: writeKey, owner: { address: "owner:write" } }],
      claimant: { address: "principal:claimant" },
      subjects,
      custodians: [],
      authorizer: { address: authorizer }
    },
    authorization: representedAuthorization,
    trajectory,
    effect: null,
    outcome: null,
    disposition: null
  }
  return {
    _tag: "CanonicalAtomV2CurrentStatePermitInput",
    contractVersion: HSWM_CANONICAL_CURRENT_STATE_PERMIT_V1_CONTRACT_VERSION,
    schema,
    state,
    journalHeadRecord: headRecord,
    headObservation: {
      schema: binding,
      journalLineageId: JOURNAL_LINEAGE,
      journalHead: headDescriptor,
      stateRevision: state.revision,
      stateSha256,
      observedAt: EVALUATED_AT,
      clockEvidence: opaque("clock-observation"),
      freshness: "LOCAL_EXACT_HEAD_OBSERVATION_NOT_MONOTONIC_WITNESS"
    },
    evaluatedAt: EVALUATED_AT,
    intent: {
      action: "ADMIT_CANONICAL_ATOM_VERSIONS",
      purpose: intentPurpose
    },
    evidence,
    policy,
    authorizationDecision,
    consents: [consent],
    trajectoryContract
  }
}

const rebindSuppliedHead = (
  input: CanonicalAtomV2CurrentStatePermitInput
): CanonicalAtomV2CurrentStatePermitInput => {
  const rebound = structuredClone(input) as any
  rebound.state.atoms.sort((left: CanonicalAtomV2, right: CanonicalAtomV2) =>
    canonicalAtomV2KeyId(left.key).localeCompare(canonicalAtomV2KeyId(right.key))
  )
  const stateSha256 = unwrap(canonicalAtomV2StateSha256(rebound.state))
  rebound.journalHeadRecord.stateRevision = rebound.state.revision
  rebound.journalHeadRecord.receipt.previousStateRevision = Math.max(
    0,
    rebound.state.revision - 1
  )
  rebound.journalHeadRecord.receipt.nextStateRevision = rebound.state.revision
  rebound.journalHeadRecord.resultingStateSha256 = stateSha256
  rebound.journalHeadRecord.writeBindings = rebound.state.atoms.map(
    (stateAtom: CanonicalAtomV2) => ({
      key: stateAtom.key,
      payload: stateAtom.content,
      envelope: {
        mediaType: HSWM_CANONICAL_ATOM_ENVELOPE_V2_MEDIA_TYPE,
        byteLength: 1,
        sha256: createHash("sha256")
          .update(canonicalAtomV2KeyId(stateAtom.key))
          .digest("hex")
      }
    })
  )
  const headDescriptor = unwrap(
    describeCanonicalAtomV2StateJournalRecord(rebound.journalHeadRecord)
  )
  rebound.headObservation.journalHead = headDescriptor
  rebound.headObservation.stateRevision = rebound.state.revision
  rebound.headObservation.stateSha256 = stateSha256
  rebound.evidence.claimedPredecessor = headDescriptor
  rebound.evidence.claimedPredecessorStateRevision = rebound.state.revision
  rebound.evidence.authorization.claimedPredecessor = headDescriptor
  rebound.evidence.authorization.claimedPredecessorStateRevision =
    rebound.state.revision
  rebound.evidence.trajectory.claimedPredecessor = headDescriptor
  rebound.evidence.trajectory.claimedPredecessorStateRevision =
    rebound.state.revision
  rebound.evidence.proposal.expectedStateRevision = rebound.state.revision
  const proposalDescriptor = descriptor(
    HSWM_CANONICAL_TRANSITION_PROPOSAL_V1_MEDIA_TYPE,
    rebound.evidence.proposal
  )
  rebound.evidence.proposalDescriptor = proposalDescriptor
  rebound.evidence.authorization.proposal = proposalDescriptor
  rebound.evidence.trajectory.proposal = proposalDescriptor
  return rebound
}

const expectFailure = (
  input: unknown,
  code: CanonicalAtomV2CurrentStatePermitError["code"]
) => {
  const result = resolveCanonicalAtomV2CurrentStatePermitEligibility(input)
  expect(Either.isLeft(result)).toBe(true)
  if (Either.isLeft(result)) {
    expect(result.left.code).toBe(code)
    expect(result.left.permitStatus).toBe("NOT_CANONICAL_PERMIT")
  }
}

it("resolves only exact-local-head eligibility and returns no Permit or commit capability", () => {
  const input = permitFixture()
  const result = resolveCanonicalAtomV2CurrentStatePermitEligibility(input)
  expect(Either.isRight(result)).toBe(true)
  if (Either.isRight(result)) {
    expect(result.right.status).toBe(
      "ELIGIBLE_AT_EXACT_SUPPLIED_SNAPSHOT_NOT_CANONICAL_PERMIT"
    )
    expect(result.right.snapshotBasis).toBe(
      "SUPPLIED_STATE_AND_HEAD_RECORD_NOT_JOURNAL_REPLAY"
    )
    expect(result.right.timeBasis).toBe(
      "CALLER_SUPPLIED_INSTANT_NOT_TRUSTED_CURRENT_TIME"
    )
    expect(result.right.capability).toBe(
      "READ_ONLY_EVALUATION_NOT_COMMIT_CAPABILITY"
    )
    expect(result.right.admission).toBe("NOT_ADMITTED_BY_THIS_RESOLUTION")
    expect(result.right.externalEffect).toBe("NOT_DISPATCHED_NOT_OBSERVED")
    expect(result.right.learning).toBe("NOT_CAUSAL_CREDIT_NOT_LEARNING")
    expect(Object.isFrozen(result.right)).toBe(true)
    expect(Object.isFrozen(result.right.consents)).toBe(true)
    expect("submit" in result.right).toBe(false)
    expect("permit" in result.right).toBe(false)
  }
})

it("uses exact canonical bytes and independent media domains for records, inputs and resolutions", () => {
  const input = permitFixture()
  const recordBytes = unwrap(
    canonicalAtomV2CurrentStatePermitRecordBytes(input.policy)
  )
  const inputBytes = unwrap(canonicalAtomV2CurrentStatePermitInputBytes(input))
  const resolution = unwrap(
    resolveCanonicalAtomV2CurrentStatePermitEligibility(input)
  )
  const resolutionBytes = unwrap(
    canonicalAtomV2CurrentStatePermitResolutionBytes(resolution)
  )
  expect(Either.isRight(decodeCanonicalAtomV2CurrentStatePermitRecordBytes(recordBytes))).toBe(true)
  expect(Either.isRight(decodeCanonicalAtomV2CurrentStatePermitInputBytes(inputBytes))).toBe(true)
  expect(Either.isRight(decodeCanonicalAtomV2CurrentStatePermitResolutionBytes(resolutionBytes))).toBe(true)
  expect(unwrap(describeCanonicalAtomV2CurrentStatePermitRecord(input.policy)).mediaType).toBe(
    HSWM_CANONICAL_CURRENT_STATE_PERMIT_RECORD_V1_MEDIA_TYPE
  )
  expect(unwrap(describeCanonicalAtomV2CurrentStatePermitInput(input)).mediaType).toBe(
    HSWM_CANONICAL_CURRENT_STATE_PERMIT_INPUT_V1_MEDIA_TYPE
  )
  expect(unwrap(describeCanonicalAtomV2CurrentStatePermitResolution(resolution)).mediaType).toBe(
    HSWM_CANONICAL_CURRENT_STATE_PERMIT_RESOLUTION_V1_MEDIA_TYPE
  )
  const nonCanonical = new TextEncoder().encode(
    ` ${new TextDecoder().decode(recordBytes)}`
  )
  expect(Either.isLeft(decodeCanonicalAtomV2CurrentStatePermitRecordBytes(nonCanonical))).toBe(true)
  const duplicate = new TextEncoder().encode(
    '{"_tag":"CanonicalAtomV2PermitPolicyRecord","_tag":"CanonicalAtomV2PermitPolicyRecord"}'
  )
  expect(Either.isLeft(decodeCanonicalAtomV2CurrentStatePermitRecordBytes(duplicate))).toBe(true)
})

it("rejects schema, local-head and predecessor substitutions independently", () => {
  const wrongSchema = structuredClone(permitFixture()) as any
  wrongSchema.headObservation.schema.content.sha256 = "f".repeat(64)
  expectFailure(wrongSchema, "SCHEMA_MISMATCH")

  const wrongHead = structuredClone(permitFixture()) as any
  wrongHead.headObservation.journalHead.sha256 = "e".repeat(64)
  expectFailure(wrongHead, "HEAD_MISMATCH")

  const wrongPredecessor = structuredClone(permitFixture()) as any
  const replacement = {
    mediaType: HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_V1_MEDIA_TYPE,
    byteLength: 7,
    sha256: "d".repeat(64)
  }
  wrongPredecessor.evidence.claimedPredecessor = replacement
  wrongPredecessor.evidence.authorization.claimedPredecessor = replacement
  wrongPredecessor.evidence.trajectory.claimedPredecessor = replacement
  expectFailure(wrongPredecessor, "PREDECESSOR_MISMATCH")
})

it("requires exact admitted content for the current policy, decision, consent and trace contract", () => {
  expectFailure(permitFixture({ wrongPolicyContent: true }), "MEMBERSHIP_CONTENT_MISMATCH")

  const missingConsent = structuredClone(permitFixture()) as any
  missingConsent.state.atoms = missingConsent.state.atoms.filter(
    ({ key: atomKey }: CanonicalAtomV2) => !sameKeyForTest(atomKey, consentKey)
  )
  expectFailure(rebindSuppliedHead(missingConsent), "MEMBERSHIP_MISSING")

  const oldPolicy = structuredClone(permitFixture()) as any
  oldPolicy.state.revision = 2
  oldPolicy.state.acceptedTransitionIds.push("transition:policy-revision")
  oldPolicy.state.atoms.push(
    atom(
      key(policyKey.atomUid, policyKey.lineageId, 1),
      HSWM_CANONICAL_PERMIT_POLICY_V1_KIND,
      "owner:state",
      opaque("newer-policy"),
      [{
        referenceType: HSWM_SUPERSEDES_REFERENCE_TYPE,
        role: HSWM_SUPERSEDES_REFERENCE_ROLE,
        target: policyKey
      }]
    )
  )
  expectFailure(rebindSuppliedHead(oldPolicy), "MEMBERSHIP_NOT_CURRENT")
})

it("does not derive authority from owner or authorizer equality", () => {
  const input = permitFixture({
    recordOwner: "principal:authorizer",
    policyAuthorizers: ["principal:other"]
  })
  expectFailure(input, "AUTHORITY_DENIED")
})

it("uses exact scope and purpose rules without prefix or wildcard promotion", () => {
  expectFailure(
    permitFixture({ intentPurpose: "purpose:canonical-admission-admin" }),
    "AUTHORITY_DENIED"
  )
  expectFailure(permitFixture({ policyActive: false }), "AUTHORITY_DENIED")

  const unknownWriteKind = structuredClone(permitFixture()) as any
  unknownWriteKind.policy.scopeRules[0].allowedWriteKinds = ["kind:unknown"]
  expectFailure(unknownWriteKind, "POLICY_INVALID")

  const delegatedGovernance = structuredClone(permitFixture()) as any
  delegatedGovernance.policy.scopeRules[0].allowedWriteKinds = [
    HSWM_CANONICAL_PERMIT_POLICY_V1_KIND,
    "kind:write"
  ]
  expectFailure(delegatedGovernance, "POLICY_INVALID")

  const unapprovedOrdinaryWrite = structuredClone(permitFixture()) as any
  const candidateRead = atom(
    key("atom:candidate-read"),
    "kind:read",
    "owner:state",
    opaque("candidate-read")
  )
  unapprovedOrdinaryWrite.evidence.proposal.writes[0] = candidateRead
  unapprovedOrdinaryWrite.evidence.trajectory.writeSet[0] = candidateRead.key
  unapprovedOrdinaryWrite.evidence.roles.owners[0] = {
    write: candidateRead.key,
    owner: { address: "owner:state" }
  }
  const unapprovedProposal = descriptor(
    HSWM_CANONICAL_TRANSITION_PROPOSAL_V1_MEDIA_TYPE,
    unapprovedOrdinaryWrite.evidence.proposal
  )
  unapprovedOrdinaryWrite.evidence.proposalDescriptor = unapprovedProposal
  unapprovedOrdinaryWrite.evidence.authorization.proposal = unapprovedProposal
  unapprovedOrdinaryWrite.evidence.trajectory.proposal = unapprovedProposal
  expectFailure(unapprovedOrdinaryWrite, "AUTHORITY_DENIED")
})

it("fails closed for denied, revoked, stale, future and unchecked authorization", () => {
  expectFailure(
    permitFixture({ authorizationDecision: "DENIED" }),
    "AUTHORIZATION_NOT_CURRENT"
  )
  for (const mode of ["REVOKED", "STALE", "FUTURE", "UNCHECKED"] as const) {
    expectFailure(
      permitFixture({ authorizationRevocation: mode }),
      "AUTHORIZATION_NOT_CURRENT"
    )
  }
})

it("requires controller-bound, exact-purpose, current consent for every affected subject", () => {
  expectFailure(
    permitFixture({ consenter: "principal:not-controller" }),
    "CONSENT_DENIED"
  )
  for (const decision of ["WITHDRAWN", "DENIED"] as const) {
    expectFailure(permitFixture({ consentDecision: decision }), "CONSENT_NOT_CURRENT")
  }
  for (const mode of ["REVOKED", "STALE", "FUTURE", "UNCHECKED"] as const) {
    expectFailure(permitFixture({ consentRevocation: mode }), "CONSENT_NOT_CURRENT")
  }
})

it("rejects self-authorization, missing policy reads and transition replay", () => {
  expectFailure(permitFixture({ omitPolicyRead: true }), "REQUIRED_READ_MISSING")
  expectFailure(permitFixture({ replay: true }), "PROPOSAL_REPLAY")

  const selfAuthorized = structuredClone(permitFixture()) as any
  selfAuthorized.evidence.proposal.writes[0]!.key = policyKey
  selfAuthorized.evidence.trajectory.writeSet[0] = policyKey
  selfAuthorized.evidence.roles.owners[0]!.write = policyKey
  const selfAuthorizedProposal = descriptor(
    HSWM_CANONICAL_TRANSITION_PROPOSAL_V1_MEDIA_TYPE,
    selfAuthorized.evidence.proposal
  )
  selfAuthorized.evidence.proposalDescriptor = selfAuthorizedProposal
  selfAuthorized.evidence.authorization.proposal = selfAuthorizedProposal
  selfAuthorized.evidence.trajectory.proposal = selfAuthorizedProposal
  expectFailure(selfAuthorized, "SELF_AUTHORIZATION")
})

it("keeps validated snapshots independent of caller mutation", () => {
  const input = permitFixture()
  const checked = validateCanonicalAtomV2CurrentStatePermitInput(input)
  expect(Either.isRight(checked)).toBe(true)
  if (Either.isRight(checked)) {
    ;(input as any).policy.scopeRules[0].authorizers[0].address =
      "principal:mutated"
    expect(checked.right.policy.scopeRules[0]!.authorizers[0]!.address).toBe(
      "principal:authorizer"
    )
    expect(Object.isFrozen(checked.right)).toBe(true)
    expect(Object.isFrozen(checked.right.policy.scopeRules)).toBe(true)
  }
})

const sameKeyForTest = (
  left: CanonicalAtomV2Key,
  right: CanonicalAtomV2Key
) => canonicalAtomV2KeyId(left) === canonicalAtomV2KeyId(right)

it("binds the admitted pre-existing decision record instead of creating a head hash cycle", () => {
  const input = permitFixture()
  const admitted = input.state.atoms.find(({ key: atomKey }) =>
    sameKeyForTest(atomKey, authorizationKey)
  )!
  const stableDescriptor = unwrap(
    describeCanonicalAtomV2CurrentStatePermitRecord(input.authorizationDecision)
  )
  const representedDescriptor = unwrap(
    describeCanonicalAtomV2TransitionEvidenceRecord(input.evidence.authorization)
  )
  expect(admitted.content).toEqual(stableDescriptor)
  expect(admitted.content).not.toEqual(representedDescriptor)
  expect(input.evidence.authorization.decisionEvidence).toEqual(stableDescriptor)
  expect(admitted.content.mediaType).toBe(
    HSWM_CANONICAL_CURRENT_STATE_PERMIT_RECORD_V1_MEDIA_TYPE
  )
  expect(representedDescriptor.mediaType).toBe(
    HSWM_CANONICAL_TRANSITION_EVIDENCE_RECORD_V1_MEDIA_TYPE
  )
})

const prestateBytes = (
  input: CanonicalAtomV2CurrentStatePermitInput,
  stateAtom: CanonicalAtomV2
): Uint8Array => {
  if (sameKeyForTest(stateAtom.key, subjectKey)) {
    return unwrap(canonicalJsonBytes({ id: "subject" }))
  }
  if (sameKeyForTest(stateAtom.key, readKey)) {
    return unwrap(canonicalJsonBytes({ id: "read" }))
  }
  if (sameKeyForTest(stateAtom.key, policyKey)) {
    return unwrap(canonicalAtomV2CurrentStatePermitRecordBytes(input.policy))
  }
  if (sameKeyForTest(stateAtom.key, authorizationKey)) {
    return unwrap(
      canonicalAtomV2CurrentStatePermitRecordBytes(input.authorizationDecision)
    )
  }
  if (sameKeyForTest(stateAtom.key, consentKey)) {
    return unwrap(canonicalAtomV2CurrentStatePermitRecordBytes(input.consents[0]!))
  }
  if (sameKeyForTest(stateAtom.key, traceKey)) {
    return unwrap(
      canonicalAtomV2CurrentStatePermitRecordBytes(input.trajectoryContract)
    )
  }
  throw new Error(`unexpected prestate atom ${stateAtom.key.atomUid}`)
}

const bootstrapPrestateAtDurableRuntime = (
  input: CanonicalAtomV2CurrentStatePermitInput
) => {
  const rawSchema = unwrap(canonicalAtomV2SchemaContentBytes(input.schema))
  const binding = schemaBinding()
  const grants: ReadonlyArray<CanonicalAtomV2ContentAuthorizationGrant> = [{
    authorizationRef: "authorization:bootstrap",
    schemaVersion: SCHEMA_VERSION,
    schemaContentSha256: binding.content.sha256,
    scopes: ["scope:bootstrap"]
  }]
  const layer = makeCanonicalAtomV2DurableRuntimeMemoryLayerForTest(
    JOURNAL_LINEAGE,
    rawSchema,
    grants
  )
  const program = Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const bindings: Array<CanonicalAtomV2WriteContentBinding> = []
    for (const stateAtom of input.state.atoms) {
      const staged = yield* runtime.stageContent(
        stateAtom.content.mediaType,
        prestateBytes(input, stateAtom)
      )
      expect(staged).toEqual(stateAtom.content)
      bindings.push({
        key: stateAtom.key,
        payload: staged,
        envelope: unwrap(describeCanonicalAtomV2Envelope(stateAtom))
      })
    }
    const bootstrap = {
      _tag: "CommitCanonicalAtomsV2" as const,
      contractVersion: "hswm-canonical-transition/v2" as const,
      transitionId: "transition:bootstrap",
      expectedStateRevision: 0,
      schemaVersion: SCHEMA_VERSION,
      actorClaim: "principal:bootstrap",
      authorizationRef: "authorization:bootstrap",
      scope: "scope:bootstrap",
      decidedAt: "2026-08-27T10:00:00.000Z",
      traceRef: null,
      readSet: [],
      writes: input.state.atoms,
      provenanceSha256: "2".repeat(64)
    }
    yield* runtime.submit(
      makeCanonicalAtomV2ContentBoundInput(
        binding.content.sha256,
        bootstrap,
        bindings
      )
    )
    const recovered = yield* runtime.snapshot
    const history = yield* runtime.history
    const exact = structuredClone(input) as CanonicalAtomV2CurrentStatePermitInput
    ;(exact as any).state = structuredClone(recovered.canonical)
    ;(exact as any).journalHeadRecord = structuredClone(history[0]!.commit)
    const rebound = exact as any
    const recoveredStateSha256 = unwrap(
      canonicalAtomV2StateSha256(recovered.canonical)
    )
    rebound.headObservation.journalHead = recovered.journalHead
    rebound.headObservation.stateRevision = recovered.canonical.revision
    rebound.headObservation.stateSha256 = recoveredStateSha256
    rebound.evidence.claimedPredecessor = recovered.journalHead
    rebound.evidence.claimedPredecessorStateRevision = recovered.canonical.revision
    rebound.evidence.authorization.claimedPredecessor = recovered.journalHead
    rebound.evidence.authorization.claimedPredecessorStateRevision = recovered.canonical.revision
    rebound.evidence.trajectory.claimedPredecessor = recovered.journalHead
    rebound.evidence.trajectory.claimedPredecessorStateRevision = recovered.canonical.revision
    rebound.evidence.proposal.expectedStateRevision = recovered.canonical.revision
    const proposal = descriptor(
      HSWM_CANONICAL_TRANSITION_PROPOSAL_V1_MEDIA_TYPE,
      rebound.evidence.proposal
    )
    rebound.evidence.proposalDescriptor = proposal
    rebound.evidence.authorization.proposal = proposal
    rebound.evidence.trajectory.proposal = proposal
    return { runtime, exact: rebound as CanonicalAtomV2CurrentStatePermitInput, recovered, history }
  })
  return { layer, program }
}

it.effect("resolves only against the matching recovered durable head and leaves durable state untouched", () => {
  const { layer, program } = bootstrapPrestateAtDurableRuntime(permitFixture())
  return program.pipe(
    Effect.flatMap(({ runtime, exact, recovered, history }) =>
      Effect.gen(function* () {
        const beforeState = structuredClone(recovered.canonical)
        const beforeHistory = structuredClone(history)
        const resolved = yield* resolveCanonicalAtomV2CurrentStatePermitEligibilityAtDurableRuntime(
          exact
        )
        expect(resolved.status).toBe(
          "ELIGIBLE_AT_RECOVERED_LOCAL_HEAD_FOR_SUPPLIED_TIME_NOT_CANONICAL_PERMIT"
        )
        expect(resolved.snapshotBasis).toBe("ONE_DURABLE_RUNTIME_RECOVERY_SNAPSHOT")
        expect(resolved.timeBasis).toBe("CALLER_SUPPLIED_INSTANT_NOT_TRUSTED_CURRENT_TIME")
        expect((yield* runtime.snapshot).canonical).toEqual(beforeState)
        expect(yield* runtime.history).toEqual(beforeHistory)

        const forged = structuredClone(exact) as any
        forged.headObservation.journalHead.sha256 = "f".repeat(64)
        const rejected = yield* resolveCanonicalAtomV2CurrentStatePermitEligibilityAtDurableRuntime(
          forged
        ).pipe(Effect.either)
        expect(Either.isLeft(rejected)).toBe(true)
        if (Either.isLeft(rejected)) {
          expect(rejected.left).toMatchObject({ code: "HEAD_MISMATCH" })
        }

        const laterBytes = unwrap(canonicalJsonBytes({ id: "later-write" }))
        const laterPayload = yield* runtime.stageContent(
          "application/json",
          laterBytes
        )
        const laterAtom: CanonicalAtomV2 = {
          ...atom(
            key("atom:later-write"),
            "kind:write",
            "owner:write",
            laterPayload
          ),
          provenance: {
            mode: "OBSERVATION",
            evidenceSha256: "6".repeat(64),
            sourceRef: null
          }
        }
        yield* runtime.submit(
          makeCanonicalAtomV2ContentBoundInput(
            schemaBinding().content.sha256,
            {
              _tag: "CommitCanonicalAtomsV2",
              contractVersion: "hswm-canonical-transition/v2",
              transitionId: "transition:later-write",
              expectedStateRevision: 1,
              schemaVersion: SCHEMA_VERSION,
              actorClaim: "principal:bootstrap",
              authorizationRef: "authorization:bootstrap",
              scope: "scope:bootstrap",
              decidedAt: "2026-08-27T12:01:00.000Z",
              traceRef: null,
              readSet: [],
              writes: [laterAtom],
              provenanceSha256: "5".repeat(64)
            },
            [{
              key: laterAtom.key,
              payload: laterPayload,
              envelope: unwrap(describeCanonicalAtomV2Envelope(laterAtom))
            }]
          )
        )
        const stale = yield* resolveCanonicalAtomV2CurrentStatePermitEligibilityAtDurableRuntime(
          exact
        ).pipe(Effect.either)
        expect(Either.isLeft(stale)).toBe(true)
        if (Either.isLeft(stale)) {
          expect(stale.left).toMatchObject({ code: "HEAD_MISMATCH" })
        }
        expect((yield* runtime.snapshot).canonical.revision).toBe(2)
      })
    ),
    Effect.provide(layer)
  )
})

it("rejects a candidate revision of the selected permission-bearing lineage before authority evaluation", () => {
  const candidate = structuredClone(permitFixture()) as any
  const policyRevision = atom(
    key(policyKey.atomUid, policyKey.lineageId, 1),
    HSWM_CANONICAL_PERMIT_POLICY_V1_KIND,
    "owner:state",
    opaque("candidate-policy-revision"),
    [{
      referenceType: HSWM_SUPERSEDES_REFERENCE_TYPE,
      role: HSWM_SUPERSEDES_REFERENCE_ROLE,
      target: policyKey
    }]
  )
  candidate.evidence.proposal.writes[0] = policyRevision
  candidate.evidence.trajectory.writeSet[0] = policyRevision.key
  candidate.evidence.roles.owners[0] = {
    write: policyRevision.key,
    owner: { address: "owner:state" }
  }
  const rebound = descriptor(
    HSWM_CANONICAL_TRANSITION_PROPOSAL_V1_MEDIA_TYPE,
    candidate.evidence.proposal
  )
  candidate.evidence.proposalDescriptor = rebound
  candidate.evidence.authorization.proposal = rebound
  candidate.evidence.trajectory.proposal = rebound
  expectFailure(candidate, "SELF_AUTHORIZATION")
})

it("rejects every new permission-bearing candidate kind outside the selected lineage", () => {
  for (const [index, permissionKind] of [
    HSWM_CANONICAL_PERMIT_POLICY_V1_KIND,
    HSWM_CANONICAL_AUTHORIZATION_DECISION_V1_KIND,
    HSWM_CANONICAL_CONSENT_DECISION_V1_KIND,
    HSWM_CANONICAL_TRAJECTORY_CONTRACT_V1_KIND
  ].entries()) {
    const candidate = structuredClone(permitFixture()) as any
    const candidatePermission = atom(
      key(
        `atom:unselected-permission-${index}`,
        `lineage:unselected-permission-${index}`
      ),
      permissionKind,
      "owner:state",
      opaque(`unselected-permission-${index}`)
    )
    candidate.evidence.proposal.writes[0] = candidatePermission
    candidate.evidence.trajectory.writeSet[0] = candidatePermission.key
    candidate.evidence.roles.owners[0] = {
      write: candidatePermission.key,
      owner: { address: "owner:state" }
    }
    const rebound = descriptor(
      HSWM_CANONICAL_TRANSITION_PROPOSAL_V1_MEDIA_TYPE,
      candidate.evidence.proposal
    )
    candidate.evidence.proposalDescriptor = rebound
    candidate.evidence.authorization.proposal = rebound
    candidate.evidence.trajectory.proposal = rebound
    expectFailure(candidate, "SELF_AUTHORIZATION")
  }
})

it("rejects a disguised successor of an unselected admitted permission lineage", () => {
  const candidate = structuredClone(permitFixture()) as any
  const unselectedPolicyKey = key(
    "atom:unselected-policy",
    "lineage:unselected-policy"
  )
  candidate.state.revision = 2
  candidate.state.acceptedTransitionIds.push("transition:unselected-policy")
  candidate.state.atoms.push(
    atom(
      unselectedPolicyKey,
      HSWM_CANONICAL_PERMIT_POLICY_V1_KIND,
      "owner:state",
      opaque("unselected-policy")
    )
  )
  const reboundState = rebindSuppliedHead(candidate) as any
  const disguisedSuccessor = atom(
    key(unselectedPolicyKey.atomUid, unselectedPolicyKey.lineageId, 1),
    "kind:write",
    "owner:write",
    opaque("disguised-policy-successor"),
    [{
      referenceType: HSWM_SUPERSEDES_REFERENCE_TYPE,
      role: HSWM_SUPERSEDES_REFERENCE_ROLE,
      target: unselectedPolicyKey
    }]
  )
  reboundState.evidence.proposal.writes[0] = disguisedSuccessor
  reboundState.evidence.trajectory.writeSet[0] = disguisedSuccessor.key
  reboundState.evidence.roles.owners[0] = {
    write: disguisedSuccessor.key,
    owner: { address: "owner:write" }
  }
  const reboundProposal = descriptor(
    HSWM_CANONICAL_TRANSITION_PROPOSAL_V1_MEDIA_TYPE,
    reboundState.evidence.proposal
  )
  reboundState.evidence.proposalDescriptor = reboundProposal
  reboundState.evidence.authorization.proposal = reboundProposal
  reboundState.evidence.trajectory.proposal = reboundProposal
  expectFailure(reboundState, "SELF_AUTHORIZATION")
})
