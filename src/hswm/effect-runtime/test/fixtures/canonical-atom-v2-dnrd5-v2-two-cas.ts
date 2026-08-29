import { createHash } from "node:crypto"

import { Effect, Either, Layer } from "effect"

import {
  canonicalAtomV2EnvelopeBytes,
  canonicalAtomV2SchemaContentBytes,
  decodeCanonicalAtomV2SchemaContent,
  describeCanonicalAtomV2Envelope,
  makeCanonicalAtomV2ContentBoundInput,
  type CanonicalAtomV2ContentAuthorizationGrant,
  type CommitCanonicalAtomsV2ContentBound
} from "../../src/canonical-atom-v2-content-bound.js"
import {
  makeCanonicalAtomV2ContentDescriptor,
  sameCanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2ContentDescriptor
} from "../../src/canonical-atom-v2-content.js"
import {
  CanonicalAtomV2DurableRuntime,
  commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal,
  makeCanonicalAtomV2DurableRuntimeFileLayer,
  makeCanonicalAtomV2DurableRuntimeFileLayerWithBeforeSlotLinkForTest,
  makeCanonicalAtomV2DurableRuntimeFileLayerWithIoFaultsForTest,
  makeCanonicalAtomV2DurableRuntimeMemoryLayerForTest,
  type CanonicalAtomV2DurableState
} from "../../src/canonical-atom-v2-durable-runtime.js"
import type { CanonicalAtomV2StateJournalFileIoFaultForTest } from "../../src/canonical-atom-v2-state-journal-file.js"
import {
  DNRD5_V2_AUTHORITY_PAYLOAD_V1,
  DNRD5_V2_AUTHORIZATION_DECISION_MEDIA_TYPE,
  DNRD5_V2_CAPABILITY_ISSUANCE_MEDIA_TYPE,
  DNRD5_V2_GRANT_SNAPSHOT_MEDIA_TYPE,
  DNRD5_V2_PERMIT_POLICY_MEDIA_TYPE,
  DNRD5_V2_REVOCATION_STATUS_MEDIA_TYPE,
  type Dnrd5V2AuthorityChain,
  type Dnrd5V2AuthorityPrincipals,
  type Dnrd5V2AuthorityStateInput
} from "../../src/canonical-atom-v2-dnrd5-v2-authority.js"
import {
  DNRD5_V2_CAPABILITY_CONSUMPTION_MEDIA_TYPE,
  DNRD5_V2_CONSUMPTION_COMMAND_INTENT_MEDIA_TYPE,
  DNRD5_V2_CONSUMPTION_COMMAND_INTENT_V1,
  DNRD5_V2_CONSUMPTION_COMMAND_PROJECTION_V1,
  DNRD5_V2_CONSUMPTION_PAYLOAD_V1,
  DNRD5_V2_CONSUMPTION_TERMINAL,
  DNRD5_V2_EVIDENCE_SEAL_CONSUMPTION_MEDIA_TYPE,
  dnrd5V2ConsumptionAtomUid,
  validateDnrd5V2Consumption,
  type Dnrd5V2ConsumptionInput,
  type Dnrd5V2ConsumptionPhase
} from "../../src/canonical-atom-v2-dnrd5-v2-consumption.js"
import {
  DNRD5_V2_RECEIPT_PAYLOAD_MEDIA_TYPE,
  DNRD5_V2_RECEIPT_SEAL_V1,
  canonicalDnrd5V2ReceiptPayloadBytes,
  validateDnrd5V2ReceiptSeal
} from "../../src/canonical-atom-v2-dnrd5-v2-receipt-seal.js"
import {
  validateDnrd5V2RecordBoundEffect
} from "../../src/canonical-atom-v2-dnrd5-v2-record-bound-effect.js"
import {
  DNRD5_V2_OWNER_ROLE_BY_KIND,
  DNRD5_V2_REFERENCE_TYPE,
  DNRD5_V2_SCHEMA_VERSION,
  makeDnrd5V2CanonicalSchema,
  type Dnrd5V2CanonicalAtomKind
} from "../../src/canonical-atom-v2-dnrd5-v2-schema.js"
import {
  DNRD5_V2_BEHAVIORAL_ROOT_V1,
  DNRD5_V2_COMPILED_BEHAVIOR_READSET_V1,
  DNRD5_V2_EXACT_W0_PROJECTION_MEDIA_TYPE,
  DNRD5_V2_EXACT_W0_RESTORE_PROJECTION_V1,
  DNRD5_V2_EXACT_W0_TARGET_MEDIA_TYPE,
  type Dnrd5V2ExactW0RestoreProjectionInput
} from "../../src/canonical-atom-v2-dnrd5-v2-exact-w0-restore-projection.js"
import {
  DNRD5_V2_TWO_CAS_ADMIT_V1,
  type Dnrd5V2TwoCasAdmitInput,
  DNRD5_V2_TWO_CAS_RESTORE_V1,
  type Dnrd5V2TwoCasRestoreInput,
  type Dnrd5V2TwoCasPhaseInput
} from "../../src/canonical-atom-v2-dnrd5-durable-permit.js"
import {
  applyCanonicalAtomV2StateJournalCommit,
  canonicalAtomV2StateJournalRecordBytes,
  canonicalAtomV2StateSha256,
  describeCanonicalAtomV2StateJournalRecord,
  makeCanonicalAtomV2StateJournalCommit
} from "../../src/canonical-atom-v2-state-journal.js"
import { makeCanonicalAtomV2AcceptedReceipt } from "../../src/canonical-atom-v2-domain.js"
import { canonicalJsonBytes } from "../../src/canonical-atom-v2-json.js"
import {
  HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
  canonicalAtomV2KeyId,
  type CanonicalAtomV2,
  type CanonicalAtomV2Key,
  type CanonicalAtomV2Reference,
  type CommitCanonicalAtomsV2Command
} from "../../src/canonical-atom-v2-schema.js"

const JOURNAL_LINEAGE = "journal:dnrd5:v2:two-cas-positive"
const ATOM_LINEAGE = "lineage:dnrd5:v2:two-cas-positive"
const AT = "2026-08-28T12:00:00.000Z"
const BOOTSTRAP_AUTHORIZATION = "authorization:dnrd5:v2:bootstrap"
const BOOTSTRAP_SCOPE = "scope:dnrd5:v2:bootstrap"
const MAIN_CAPABILITY_ID = "capability:dnrd5:v2:main"
const EVIDENCE_CAPABILITY_ID = "capability:dnrd5:v2:evidence"
const RESTORE_MAIN_CAPABILITY_ID = "capability:dnrd5:v2:restore-main"
const RESTORE_EVIDENCE_CAPABILITY_ID = "capability:dnrd5:v2:restore-evidence"
const SCOPE = "scope:dnrd5:v2:experiment"
const ACTOR = "principal:dnrd5:v2:actor"

const hash = (value: Uint8Array | string): string =>
  createHash("sha256").update(value).digest("hex")

const right = <A, E>(value: Either.Either<A, E>, label: string): A => {
  if (Either.isLeft(value)) {
    throw new Error(
      "two-CAS fixture failed: " + label + ": " + JSON.stringify(value.left)
    )
  }
  return value.right
}

interface Content {
  readonly atom: CanonicalAtomV2
  readonly bytes: Uint8Array
}

interface AuthorityFixture {
  readonly chain: Dnrd5V2AuthorityChain
  readonly nonceSha256: string
  readonly capabilityId: string
}

const schema = makeDnrd5V2CanonicalSchema()
export const dnrd5V2TwoCasSchemaBytes = right(
  canonicalAtomV2SchemaContentBytes(schema),
  "schema bytes"
)
const schemaContent = right(
  decodeCanonicalAtomV2SchemaContent(dnrd5V2TwoCasSchemaBytes),
  "schema content"
)

const grants: ReadonlyArray<CanonicalAtomV2ContentAuthorizationGrant> = [
  {
    authorizationRef: BOOTSTRAP_AUTHORIZATION,
    schemaVersion: DNRD5_V2_SCHEMA_VERSION,
    schemaContentSha256: schemaContent.binding.content.sha256,
    scopes: [BOOTSTRAP_SCOPE]
  },
  {
    authorizationRef: MAIN_CAPABILITY_ID,
    schemaVersion: DNRD5_V2_SCHEMA_VERSION,
    schemaContentSha256: schemaContent.binding.content.sha256,
    scopes: [SCOPE]
  },
  {
    authorizationRef: EVIDENCE_CAPABILITY_ID,
    schemaVersion: DNRD5_V2_SCHEMA_VERSION,
    schemaContentSha256: schemaContent.binding.content.sha256,
    scopes: [SCOPE]
  },
  {
    authorizationRef: RESTORE_MAIN_CAPABILITY_ID,
    schemaVersion: DNRD5_V2_SCHEMA_VERSION,
    schemaContentSha256: schemaContent.binding.content.sha256,
    scopes: [SCOPE]
  },
  {
    authorizationRef: RESTORE_EVIDENCE_CAPABILITY_ID,
    schemaVersion: DNRD5_V2_SCHEMA_VERSION,
    schemaContentSha256: schemaContent.binding.content.sha256,
    scopes: [SCOPE]
  }
]

export const makeDnrd5V2TwoCasLayer = () =>
  makeCanonicalAtomV2DurableRuntimeMemoryLayerForTest(
    JOURNAL_LINEAGE,
    dnrd5V2TwoCasSchemaBytes,
    grants
  )

/** Fresh calls over the same root reopen only file-backed durable state. */
export const makeDnrd5V2TwoCasFileLayer = (rootPath: string) =>
  makeCanonicalAtomV2DurableRuntimeFileLayer(
    rootPath,
    JOURNAL_LINEAGE,
    dnrd5V2TwoCasSchemaBytes,
    grants
  )

export const makeDnrd5V2TwoCasIoFaultFileLayer = (
  rootPath: string,
  faults: ReadonlyArray<CanonicalAtomV2StateJournalFileIoFaultForTest>
): Layer.Layer<CanonicalAtomV2DurableRuntime, unknown, never> =>
  makeCanonicalAtomV2DurableRuntimeFileLayerWithIoFaultsForTest(
    rootPath,
    JOURNAL_LINEAGE,
    dnrd5V2TwoCasSchemaBytes,
    faults,
    grants
  )

export const makeDnrd5V2TwoCasBeforeSlotLinkFileLayer = (
  rootPath: string,
  beforeSlotLink: () => Promise<void>
): Layer.Layer<CanonicalAtomV2DurableRuntime, unknown, never> =>
  makeCanonicalAtomV2DurableRuntimeFileLayerWithBeforeSlotLinkForTest(
    rootPath,
    JOURNAL_LINEAGE,
    dnrd5V2TwoCasSchemaBytes,
    beforeSlotLink,
    grants
  )

const key = (atomUid: string): CanonicalAtomV2Key => ({
  schemaVersion: DNRD5_V2_SCHEMA_VERSION,
  lineageId: ATOM_LINEAGE,
  atomUid,
  revisionId: 0
})

const id = (atom: CanonicalAtomV2): string => canonicalAtomV2KeyId(atom.key)

const reference = (
  role: string,
  target: CanonicalAtomV2
): CanonicalAtomV2Reference => ({
  referenceType: DNRD5_V2_REFERENCE_TYPE,
  role: "role:dnrd5:v2:" + role,
  target: target.key
})

const contentFromBytes = (
  atomUid: string,
  kind: Dnrd5V2CanonicalAtomKind,
  mediaType: string,
  bytes: Uint8Array,
  references: ReadonlyArray<CanonicalAtomV2Reference> = [],
  provenanceEvidenceSha256 = hash("fixture-evidence:" + atomUid)
): Content => {
  const descriptor = right(
    makeCanonicalAtomV2ContentDescriptor(mediaType, bytes),
    "content descriptor"
  )
  return {
    bytes: Uint8Array.from(bytes),
    atom: {
      _tag: "CanonicalAtomV2",
      contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
      key: key(atomUid),
      kind: "hswm:dnrd5:v2:" + kind,
      responsibilityOwner:
        "owner:dnrd5:v2:" + DNRD5_V2_OWNER_ROLE_BY_KIND[kind],
      content: descriptor,
      provenance: references.length === 0
        ? {
            mode: "BOOTSTRAP",
            evidenceSha256: provenanceEvidenceSha256,
            sourceRef: null
          }
        : {
            mode: "DERIVATION",
            evidenceSha256: provenanceEvidenceSha256,
            sourceRef: references[0]!.target
          },
      lifecycle: "ADMITTED",
      references
    }
  }
}

const content = (
  atomUid: string,
  kind: Dnrd5V2CanonicalAtomKind,
  mediaType: string,
  payload: object,
  references: ReadonlyArray<CanonicalAtomV2Reference> = []
): Content => contentFromBytes(
  atomUid,
  kind,
  mediaType,
  right(canonicalJsonBytes(payload), "payload bytes"),
  references
)

const support = (
  atomUid: string,
  kind: Dnrd5V2CanonicalAtomKind,
  pairs: ReadonlyArray<readonly [string, CanonicalAtomV2]> = []
): Content => content(
  atomUid,
  kind,
  "application/json",
  { fixture: atomUid },
  pairs.map(([role, target]) => reference(role, target))
)

const stub = (atomUid: string): CanonicalAtomV2 => ({
  key: key(atomUid)
} as CanonicalAtomV2)

const principals: Dnrd5V2AuthorityPrincipals = {
  actor: ACTOR,
  authorizer: "principal:dnrd5:v2:authorizer",
  canonicalStateCustodian: "principal:dnrd5:v2:state-custodian",
  restoreCustodian: "principal:dnrd5:v2:restore-custodian",
  creditAdjudicator: "principal:dnrd5:v2:credit-adjudicator",
  authorizationRecordCustodian:
    "principal:dnrd5:v2:authorization-record-custodian"
}

const authority = (
  label: "main" | "evidence" | "restore-main" | "restore-evidence",
  phase: Dnrd5V2ConsumptionPhase,
  policy: Content,
  purpose: CanonicalAtomV2
): AuthorityFixture => {
  const capabilityId = label === "main"
    ? MAIN_CAPABILITY_ID
    : label === "evidence"
      ? EVIDENCE_CAPABILITY_ID
      : label === "restore-main"
        ? RESTORE_MAIN_CAPABILITY_ID
        : RESTORE_EVIDENCE_CAPABILITY_ID
  const authorizationRef = "authorization-ref:dnrd5:v2:" + label
  const nonceSha256 = hash("nonce:dnrd5:v2:" + label)
  const authorization = content(
    "authorization-" + label,
    "authorization_decision",
    DNRD5_V2_AUTHORIZATION_DECISION_MEDIA_TYPE,
    {
      contractVersion: DNRD5_V2_AUTHORITY_PAYLOAD_V1,
      scope: SCOPE,
      actor: ACTOR,
      authorizer: principals.authorizer,
      authorizationRef,
      recordCustodian: principals.authorizationRecordCustodian,
      phase,
      policyAtomKeyId: id(policy.atom),
      policyGeneration: 1,
      decidedAt: "2026-08-28T11:00:00.000Z",
      notBefore: "2026-08-28T11:00:00.000Z",
      expiresAt: "2026-08-28T13:00:00.000Z",
      generation: 1
    },
    [reference("policy", policy.atom)]
  )
  const capability = content(
    "capability-" + label,
    "capability_issuance",
    DNRD5_V2_CAPABILITY_ISSUANCE_MEDIA_TYPE,
    {
      contractVersion: DNRD5_V2_AUTHORITY_PAYLOAD_V1,
      scope: SCOPE,
      actor: ACTOR,
      phase,
      purposeAtomKeyId: id(purpose),
      capabilityId,
      nonceSha256,
      policyAtomKeyId: id(policy.atom),
      policyGeneration: 1,
      authorizationAtomKeyId: id(authorization.atom),
      authorizationRef,
      authorizationGeneration: 1,
      generation: 1,
      issuedAt: "2026-08-28T11:30:00.000Z",
      expiresAt: "2026-08-28T12:30:00.000Z"
    },
    [
      reference("authorization", authorization.atom),
      reference("policy", policy.atom)
    ]
  )
  const revocation = content(
    "revocation-" + label,
    "revocation_status",
    DNRD5_V2_REVOCATION_STATUS_MEDIA_TYPE,
    {
      contractVersion: DNRD5_V2_AUTHORITY_PAYLOAD_V1,
      status: "CHECKED_NOT_REVOKED",
      checkedAt: AT,
      authorizationAtomKeyId: id(authorization.atom),
      authorizationRef,
      capabilityAtomKeyId: id(capability.atom),
      capabilityId,
      policyGeneration: 1,
      authorizationGeneration: 1,
      capabilityGeneration: 1
    },
    [
      reference("authorization", authorization.atom),
      reference("capability", capability.atom)
    ]
  )
  const grant = content(
    "grant-" + label,
    "grant_snapshot",
    DNRD5_V2_GRANT_SNAPSHOT_MEDIA_TYPE,
    {
      contractVersion: DNRD5_V2_AUTHORITY_PAYLOAD_V1,
      policyAtomKeyId: id(policy.atom),
      authorizationAtomKeyId: id(authorization.atom),
      authorizationRef,
      capabilityAtomKeyId: id(capability.atom),
      capabilityId,
      revocationAtomKeyId: id(revocation.atom),
      policyGeneration: 1,
      authorizationGeneration: 1,
      capabilityGeneration: 1
    },
    [
      reference("policy", policy.atom),
      reference("authorization", authorization.atom),
      reference("capability", capability.atom),
      reference("revocation", revocation.atom)
    ]
  )
  return {
    chain: {
      phase,
      policy,
      authorization,
      capability,
      revocation,
      grant
    },
    nonceSha256,
    capabilityId
  }
}

const makeGraph = () => {
  const policy = content(
    "policy",
    "permit_policy",
    DNRD5_V2_PERMIT_POLICY_MEDIA_TYPE,
    {
      contractVersion: DNRD5_V2_AUTHORITY_PAYLOAD_V1,
      scope: SCOPE,
      allowedActors: [ACTOR],
      allowedPhases: ["MAIN_ADMIT", "RECEIPT_ADMIT"],
      allowMainReceiptPairing: true,
      generation: 1
    }
  )
  const randomness = support("randomness", "study_randomness")
  const evaluator = support("evaluator", "evaluator_commitment")
  const block = support("block", "block_spec", [
    ["randomness", randomness.atom],
    ["evaluator", evaluator.atom]
  ])
  const probe = support("probe", "probe_commitment", [
    ["block-spec", block.atom],
    ["randomness", randomness.atom]
  ])
  const placebo = support("placebo", "placebo_commitment", [
    ["block-spec", block.atom],
    ["randomness", randomness.atom]
  ])
  const projectionPolicy = support("projection-policy", "projection_policy")
  // Fixture-only structural W0 subset: it is typed/provenance-closed and is
  // not a behavioral execution, occurrence, or learning observation.
  const w0ReadIds = [policy, randomness, evaluator, block, probe].map((value) => id(value.atom)).sort()
  const rootBytes = right(canonicalJsonBytes({ _tag: "Dnrd5V2BehavioralRoot", contractVersion: DNRD5_V2_BEHAVIORAL_ROOT_V1, atomKeyIds: w0ReadIds }), "fixture W0 root")
  const rootDescriptor = right(makeCanonicalAtomV2ContentDescriptor("application/json", rootBytes), "fixture W0 root descriptor")
  const readsetBytes = right(canonicalJsonBytes({ _tag: "Dnrd5V2CompiledBehaviorReadset", contractVersion: DNRD5_V2_COMPILED_BEHAVIOR_READSET_V1, behavioralRootSha256: rootDescriptor.sha256, atomKeyIds: w0ReadIds }), "fixture W0 readset")
  const readsetDescriptor = right(makeCanonicalAtomV2ContentDescriptor("application/json", readsetBytes), "fixture W0 readset descriptor")
  const targetBytes = right(canonicalJsonBytes({ _tag: "Dnrd5V2ExactW0Target", contractVersion: DNRD5_V2_EXACT_W0_RESTORE_PROJECTION_V1, declaredW0StateRevision: 0, declaredW0StateSha256: hash("fixture-only-declared-w0-not-custody"), behavioralRoot: rootDescriptor, compiledReadset: readsetDescriptor }), "fixture W0 target")
  const w0 = contentFromBytes("w0", "w0_snapshot", DNRD5_V2_EXACT_W0_TARGET_MEDIA_TYPE, targetBytes, [reference("block-spec", block.atom)])
  const forks = [1, 2, 3, 4].map((index) =>
    support("fork-" + index, "fork_incidence", [["w0", w0.atom]])
  )
  const assignment = support("assignment", "block_assignment", [
    ["randomness", randomness.atom],
    ["block-spec", block.atom],
    ...forks.map((fork) => ["fork", fork.atom] as const)
  ])
  const activation = support("activation", "episode_activation", [
    ["block-spec", block.atom],
    ["probe", probe.atom],
    ["w0", w0.atom],
    ...forks.map((fork) => ["fork", fork.atom] as const),
    ["assignment", assignment.atom],
    ["evaluator", evaluator.atom]
  ])
  const contract = support("contract", "trajectory_contract", [
    ["activation", activation.atom]
  ])
  const trajectory = support("trajectory", "trajectory_seal", [
    ["activation", activation.atom],
    ["contract", contract.atom],
    ["w0", w0.atom]
  ])
  const placeboReceipt = support("placebo-receipt", "placebo_receipt", [
    ["commitment", placebo.atom],
    ["randomness", randomness.atom]
  ])
  const feedback = support("feedback", "feedback_assignment", [
    ["fork", forks[0]!.atom],
    ["assignment", assignment.atom],
    ["source", placeboReceipt.atom]
  ])
  const proposal = support("proposal", "revision_proposal", [
    ["trajectory", trajectory.atom],
    ["feedback", feedback.atom]
  ])
  const alternateProposal = support("proposal-alternate", "revision_proposal", [
    ["trajectory", trajectory.atom],
    ["feedback", feedback.atom]
  ])
  const validation = support("validation", "candidate_validation", [
    ["proposal", proposal.atom]
  ])
  const main = authority(
    "main",
    "MAIN_ADMIT",
    policy,
    stub("decision")
  )
  const credit = support("credit", "credit_decision", [
    ["trajectory", trajectory.atom],
    ["credit-source", placeboReceipt.atom],
    ["feedback", feedback.atom],
    ["proposal", proposal.atom],
    ["grant", main.chain.grant.atom]
  ])
  const decision = support("decision", "revision_admission_decision", [
    ["block", block.atom],
    ["assignment", assignment.atom],
    ["fork", forks[0]!.atom],
    ["proposal", proposal.atom],
    ["validation", validation.atom],
    ["credit", credit.atom],
    ["grant", main.chain.grant.atom],
    ["authorization", main.chain.authorization.atom],
    ["capability", main.chain.capability.atom],
    ["revocation", main.chain.revocation.atom]
  ])
  const alternateDecision = support(
    "decision-alternate",
    "revision_admission_decision",
    [
      ["block", block.atom],
      ["assignment", assignment.atom],
      ["fork", forks[1]!.atom],
      ["proposal", alternateProposal.atom],
      ["validation", validation.atom],
      ["credit", credit.atom],
      ["grant", main.chain.grant.atom],
      ["authorization", main.chain.authorization.atom],
      ["capability", main.chain.capability.atom],
      ["revocation", main.chain.revocation.atom]
    ]
  )
  const restorePolicy = support("restore-policy", "restore_policy", [
    ["policy", policy.atom],
    ["capability", main.chain.capability.atom]
  ])
  const evidence = authority(
    "evidence",
    "RECEIPT_ADMIT",
    policy,
    decision.atom
  )
  const contents = [
    policy,
    randomness,
    evaluator,
    block,
    probe,
    projectionPolicy,
    placebo,
    w0,
    ...forks,
    assignment,
    activation,
    contract,
    trajectory,
    placeboReceipt,
    feedback,
    proposal,
    alternateProposal,
    validation,
    main.chain.authorization,
    main.chain.capability,
    main.chain.revocation,
    main.chain.grant,
    credit,
    decision,
    alternateDecision,
    restorePolicy,
    evidence.chain.authorization,
    evidence.chain.capability,
    evidence.chain.revocation,
    evidence.chain.grant
  ]
  return {
    contents,
    main,
    evidence,
    proposal,
    alternateProposal,
    decision,
    alternateDecision,
    restorePolicy,
    projectionPolicy,
    w0Projection: { rootBytes, readsetBytes, targetBytes, rootDescriptor, readsetDescriptor }
  }
}

const command = (
  transitionId: string,
  revision: number,
  actorClaim: string,
  authorizationRef: string,
  scope: string,
  writes: ReadonlyArray<CanonicalAtomV2>,
  readSet: ReadonlyArray<CanonicalAtomV2Key>
): CommitCanonicalAtomsV2Command => ({
  _tag: "CommitCanonicalAtomsV2",
  contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
  transitionId,
  expectedStateRevision: revision,
  schemaVersion: DNRD5_V2_SCHEMA_VERSION,
  actorClaim,
  authorizationRef,
  scope,
  decidedAt: AT,
  traceRef: null,
  readSet,
  writes,
  provenanceSha256: hash("provenance:" + transitionId)
})

const bindCommand = (
  runtime: CanonicalAtomV2DurableRuntime["Type"],
  value: CommitCanonicalAtomsV2Command,
  payloads: ReadonlyMap<string, Uint8Array>
): Effect.Effect<CommitCanonicalAtomsV2ContentBound, unknown> =>
  Effect.gen(function* () {
    const sorted = [...value.writes].sort((left, rightAtom) =>
      id(left).localeCompare(id(rightAtom))
    )
    const bindings = []
    for (const atom of sorted) {
      const bytes = payloads.get(id(atom))
      if (bytes === undefined) throw new Error("fixture payload is absent")
      const staged = yield* runtime.stageContent(atom.content.mediaType, bytes)
      if (!sameCanonicalAtomV2ContentDescriptor(staged, atom.content)) {
        throw new Error("fixture staged descriptor drifted")
      }
      bindings.push({
        key: atom.key,
        payload: staged,
        envelope: right(describeCanonicalAtomV2Envelope(atom), "envelope")
      })
    }
    return makeCanonicalAtomV2ContentBoundInput(
      runtime.schemaContent.content.sha256,
      value,
      bindings
    )
  })

const snapshotFor = (
  state: CanonicalAtomV2DurableState
) => ({
  stateRevision: state.canonical.revision,
  stateSha256: right(canonicalAtomV2StateSha256(state.canonical), "state hash"),
  journalLineageId: state.journalLineageId,
  journalHead: state.journalHead
})

const externalReadSet = (
  writes: ReadonlyArray<CanonicalAtomV2>
): ReadonlyArray<CanonicalAtomV2Key> => {
  const writeIds = new Set(writes.map(id))
  const targets = writes.flatMap((atom) => [
    ...atom.references.map((candidate) => candidate.target),
    ...(atom.provenance.sourceRef === null ? [] : [atom.provenance.sourceRef])
  ])
  return [...new Map(
    targets
      .filter((target) => !writeIds.has(canonicalAtomV2KeyId(target)))
      .map((target) => [canonicalAtomV2KeyId(target), target] as const)
  ).values()].sort((left, rightKey) =>
    canonicalAtomV2KeyId(left).localeCompare(canonicalAtomV2KeyId(rightKey))
  )
}

interface ConsumptionFixture {
  readonly input: Dnrd5V2ConsumptionInput
  readonly command: CommitCanonicalAtomsV2Command
  readonly consumption: Content
  readonly companion: Content
}

const consumptionCandidate = (
  phase: Dnrd5V2ConsumptionPhase,
  state: CanonicalAtomV2DurableState["canonical"],
  authorizationSnapshot: ReturnType<typeof snapshotFor>,
  authorityFixture: AuthorityFixture,
  purpose: CanonicalAtomV2,
  companionFor: (consumptionStub: CanonicalAtomV2) => Content
): ConsumptionFixture => {
  const consumptionUid = right(
    dnrd5V2ConsumptionAtomUid(
      phase,
      authorityFixture.nonceSha256,
      id(purpose)
    ),
    "consumption UID"
  )
  const consumptionStub = stub(consumptionUid)
  const companion = companionFor(consumptionStub)
  const mainPhase = phase === "MAIN_ADMIT" || phase === "MAIN_RESTORE"
  const purposeRole = mainPhase ? "decision" : "purpose"
  const consumptionReferences = [
    reference("grant", authorityFixture.chain.grant.atom),
    reference("capability", authorityFixture.chain.capability.atom),
    reference("revocation", authorityFixture.chain.revocation.atom),
    reference(purposeRole, purpose)
  ]
  const shell: CanonicalAtomV2 = {
    ...consumptionStub,
    _tag: "CanonicalAtomV2",
    contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
    kind: mainPhase
      ? "hswm:dnrd5:v2:capability_consumption"
      : "hswm:dnrd5:v2:evidence_seal_consumption",
    responsibilityOwner: mainPhase
      ? "owner:dnrd5:v2:capability_consumption_custodian"
      : "owner:dnrd5:v2:evidence_seal_consumption_custodian",
    content: companion.atom.content,
    provenance: {
      mode: "DERIVATION",
      evidenceSha256: hash("projection-shell:" + phase),
      sourceRef: purpose.key
    },
    lifecycle: "ADMITTED",
    references: consumptionReferences
  }
  const projectedCommand = command(
    "transition:dnrd5:v2:" + phase.toLowerCase(),
    state.revision,
    ACTOR,
    authorityFixture.capabilityId,
    SCOPE,
    [companion.atom],
    externalReadSet([shell, companion.atom])
  )
  const projectionBytes = right(canonicalJsonBytes({
    contractVersion: DNRD5_V2_CONSUMPTION_COMMAND_PROJECTION_V1,
    phase,
    consumptionAtomKeyId: canonicalAtomV2KeyId(consumptionStub.key),
    command: projectedCommand
  }), "projection bytes")
  const authorityIds = {
    grantAtomKeyId: id(authorityFixture.chain.grant.atom),
    capabilityAtomKeyId: id(authorityFixture.chain.capability.atom),
    revocationAtomKeyId: id(authorityFixture.chain.revocation.atom)
  }
  const intentBytes = right(canonicalJsonBytes({
    contractVersion: DNRD5_V2_CONSUMPTION_COMMAND_INTENT_V1,
    phase,
    capabilityNonceSha256: authorityFixture.nonceSha256,
    purposeAtomKeyId: id(purpose),
    authority: authorityIds,
    authorizationSnapshot,
    evaluatedAt: AT,
    commandProjectionSha256: hash(projectionBytes)
  }), "intent bytes")
  const payloadBytes = right(canonicalJsonBytes({
    _tag: "Dnrd5V2ConsumptionPayload",
    contractVersion: DNRD5_V2_CONSUMPTION_PAYLOAD_V1,
    phase,
    capabilityNonceSha256: authorityFixture.nonceSha256,
    purposeAtomKeyId: id(purpose),
    authority: authorityIds,
    authorizationSnapshot,
    commandIntent: right(makeCanonicalAtomV2ContentDescriptor(
      DNRD5_V2_CONSUMPTION_COMMAND_INTENT_MEDIA_TYPE,
      intentBytes
    ), "intent descriptor"),
    evaluatedAt: AT,
    terminal: DNRD5_V2_CONSUMPTION_TERMINAL
  }), "consumption payload bytes")
  const consumptionBase = contentFromBytes(
    consumptionUid,
    mainPhase
      ? "capability_consumption"
      : "evidence_seal_consumption",
    mainPhase
      ? DNRD5_V2_CAPABILITY_CONSUMPTION_MEDIA_TYPE
      : DNRD5_V2_EVIDENCE_SEAL_CONSUMPTION_MEDIA_TYPE,
    payloadBytes,
    consumptionReferences,
    hash(projectionBytes)
  )
  const consumption: Content = {
    ...consumptionBase,
    atom: {
      ...consumptionBase.atom,
      provenance: {
        mode: "DERIVATION",
        evidenceSha256: hash(projectionBytes),
        sourceRef: purpose.key
      }
    }
  }
  const input: Dnrd5V2ConsumptionInput = {
    _tag: "Dnrd5V2ConsumptionInput",
    payloadBytes,
    commandIntentBytes: intentBytes,
    commandProjectionBytes: projectionBytes,
    atom: consumption.atom,
    authorizationSnapshot,
    state
  }
  right(validateDnrd5V2Consumption(input), "consumption validation")
  return {
    input,
    command: { ...projectedCommand, writes: [consumption.atom, companion.atom] },
    consumption,
    companion
  }
}

const phaseInput = (
  authorityInput: Dnrd5V2AuthorityStateInput,
  candidate: ConsumptionFixture,
  transition: CommitCanonicalAtomsV2ContentBound
): Dnrd5V2TwoCasPhaseInput => ({
  authority: authorityInput,
  consumption: candidate.input,
  transition,
  writePayloads: [candidate.consumption, candidate.companion].map((value) => ({
    atomKeyId: id(value.atom),
    bytes: Uint8Array.from(value.bytes)
  }))
})

const stageConsumptionIntent = (
  runtime: CanonicalAtomV2DurableRuntime["Type"],
  candidate: ConsumptionFixture
): Effect.Effect<void, unknown> =>
  Effect.gen(function* () {
    const expected = right(makeCanonicalAtomV2ContentDescriptor(
      DNRD5_V2_CONSUMPTION_COMMAND_INTENT_MEDIA_TYPE,
      candidate.input.commandIntentBytes
    ), "fixture command-intent descriptor")
    const staged = yield* runtime.stageContent(
      DNRD5_V2_CONSUMPTION_COMMAND_INTENT_MEDIA_TYPE,
      candidate.input.commandIntentBytes
    )
    if (!sameCanonicalAtomV2ContentDescriptor(staged, expected)) {
      throw new Error("fixture command-intent durable descriptor drifted")
    }
  })

const authorityInput = (
  state: CanonicalAtomV2DurableState["canonical"],
  chain: Dnrd5V2AuthorityChain
): Dnrd5V2AuthorityStateInput => ({
  _tag: "Dnrd5V2AuthorityStateInput",
  contractVersion: DNRD5_V2_AUTHORITY_PAYLOAD_V1,
  evaluatedAt: AT,
  principals,
  state,
  chain
})

const payloadMap = (values: ReadonlyArray<Content>): ReadonlyMap<string, Uint8Array> =>
  new Map(values.map((value) => [id(value.atom), value.bytes] as const))

const recordFor = (
  previous: CanonicalAtomV2DurableState,
  value: CommitCanonicalAtomsV2Command,
  transition: CommitCanonicalAtomsV2ContentBound
) => {
  const byId = new Map(value.writes.map((atom) => [id(atom), atom] as const))
  const envelopes = transition.writeBindings.map((binding) =>
    right(
      canonicalAtomV2EnvelopeBytes(byId.get(canonicalAtomV2KeyId(binding.key))!),
      "record envelope"
    )
  )
  const receipt = makeCanonicalAtomV2AcceptedReceipt(
    value,
    previous.canonical.revision,
    previous.canonical.revision + 1
  )
  const record = right(makeCanonicalAtomV2StateJournalCommit(
    schema,
    {
      state: previous.canonical,
      descriptor: previous.journalHead,
      journalLineageId: previous.journalLineageId,
      schema: previous.schema
    },
    receipt,
    transition.writeBindings,
    envelopes
  ), "journal record")
  const applied = right(applyCanonicalAtomV2StateJournalCommit(
    schema,
    {
      state: previous.canonical,
      descriptor: previous.journalHead,
      journalLineageId: previous.journalLineageId,
      schema: previous.schema
    },
    record,
    envelopes
  ), "journal replay")
  return {
    record,
    bytes: right(canonicalAtomV2StateJournalRecordBytes(record), "record bytes"),
    descriptor: right(describeCanonicalAtomV2StateJournalRecord(record), "record descriptor"),
    envelopes,
    state: {
      ...previous,
      canonical: applied.state,
      journalHead: applied.descriptor
    } satisfies CanonicalAtomV2DurableState
  }
}

export interface Dnrd5V2TwoCasPreparedFixture {
  readonly input: Dnrd5V2TwoCasAdmitInput
  readonly s0Revision: number
  readonly expectedR1: CanonicalAtomV2ContentDescriptor
  readonly expectedR2: CanonicalAtomV2ContentDescriptor
}

export interface Dnrd5V2TwoCasFixtureOptions {
  readonly mainEffectGrammarCrosswire?: boolean
  readonly receiptGrammarCrosswire?: boolean
}

export const prepareDnrd5V2TwoCasFixture = (
  options: Dnrd5V2TwoCasFixtureOptions = {}
): Effect.Effect<
  Dnrd5V2TwoCasPreparedFixture,
  unknown,
  CanonicalAtomV2DurableRuntime
> => Effect.gen(function* () {
  const runtime = yield* CanonicalAtomV2DurableRuntime
  const graph = makeGraph()
  const bootstrapCommand = command(
    "transition:dnrd5:v2:bootstrap",
    0,
    "principal:dnrd5:v2:bootstrap",
    BOOTSTRAP_AUTHORIZATION,
    BOOTSTRAP_SCOPE,
    graph.contents.map((value) => value.atom),
    []
  )
  const bootstrapTransition = yield* bindCommand(
    runtime,
    bootstrapCommand,
    payloadMap(graph.contents)
  )
  yield* commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal(
    runtime,
    bootstrapTransition
  )
  const s0 = yield* runtime.snapshot
  const makeMainCandidate = (proposal: CanonicalAtomV2) => consumptionCandidate(
    "MAIN_ADMIT",
    s0.canonical,
    snapshotFor(s0),
    graph.main,
    graph.decision.atom,
    (consumptionStub) => support("main-macro", "macro_disposition", [
      ["proposal", proposal],
      ["revision-admission-decision", graph.decision.atom],
      ["restore-policy", graph.restorePolicy.atom],
      ["effect-consumption", consumptionStub]
    ])
  )
  const validMainCandidate = makeMainCandidate(graph.proposal.atom)
  const mainCandidate = options.mainEffectGrammarCrosswire
    ? makeMainCandidate(graph.alternateProposal.atom)
    : validMainCandidate
  const mainTransition = yield* bindCommand(
    runtime,
    mainCandidate.command,
    payloadMap([mainCandidate.consumption, mainCandidate.companion])
  )
  const validMainTransition = mainCandidate === validMainCandidate
    ? mainTransition
    : yield* bindCommand(
        runtime,
        validMainCandidate.command,
        payloadMap([
          validMainCandidate.consumption,
          validMainCandidate.companion
        ])
      )
  const expectedMain = recordFor(
    s0,
    validMainCandidate.command,
    validMainTransition
  )
  const mainEffectInput = {
    schema,
    preState: s0.canonical,
    predecessor: {
      descriptor: s0.journalHead,
      journalLineageId: s0.journalLineageId,
      schemaContentSha256: s0.schema.content.sha256
    },
    command: validMainCandidate.command,
    record: expectedMain.record,
    recordBytes: expectedMain.bytes,
    recordDescriptor: expectedMain.descriptor,
    envelopes: expectedMain.envelopes,
    usedRecordDescriptorSha256s: []
  }
  const mainEffect = right(
    validateDnrd5V2RecordBoundEffect(mainEffectInput),
    "main record-bound effect"
  )
  const receiptPayloadBytes = right(canonicalDnrd5V2ReceiptPayloadBytes({
    contractVersion: DNRD5_V2_RECEIPT_SEAL_V1,
    receiptKind: "REVISION",
    precedingEffectRecordDescriptorSha256: expectedMain.descriptor.sha256,
    postcommitReceiptIdentity:
      mainEffect.deterministicFuturePostcommitReceiptIdentity,
    decisionAtomKeyId: id(graph.decision.atom),
    effectConsumptionAtomKeyId: id(validMainCandidate.consumption.atom),
    effectAtomKeyId: id(validMainCandidate.companion.atom)
  }), "receipt payload")
  const receiptCandidate = consumptionCandidate(
    "RECEIPT_ADMIT",
    expectedMain.state.canonical,
    snapshotFor(expectedMain.state),
    graph.evidence,
    graph.decision.atom,
    (consumptionStub) => contentFromBytes(
      "receipt:" + mainEffect.deterministicFuturePostcommitReceiptIdentity,
      "revision_transition_receipt",
      DNRD5_V2_RECEIPT_PAYLOAD_MEDIA_TYPE,
      receiptPayloadBytes,
      [
        reference(
          "decision",
          options.receiptGrammarCrosswire
            ? graph.alternateDecision.atom
            : graph.decision.atom
        ),
        reference("effect-consumption", validMainCandidate.consumption.atom),
        reference("successor", validMainCandidate.companion.atom),
        reference("evidence-consumption", consumptionStub)
      ]
    )
  )
  const receiptTransition = yield* bindCommand(
    runtime,
    receiptCandidate.command,
    payloadMap([receiptCandidate.consumption, receiptCandidate.companion])
  )
  const expectedReceipt = recordFor(
    expectedMain.state,
    receiptCandidate.command,
    receiptTransition
  )
  const input: Dnrd5V2TwoCasAdmitInput = {
    _tag: "Dnrd5V2TwoCasAdmitInput",
    contractVersion: DNRD5_V2_TWO_CAS_ADMIT_V1,
    main: phaseInput(
      authorityInput(s0.canonical, graph.main.chain),
      mainCandidate,
      mainTransition
    ),
    receipt: phaseInput(
      authorityInput(expectedMain.state.canonical, graph.evidence.chain),
      receiptCandidate,
      receiptTransition
    )
  }
  return {
    input,
    s0Revision: s0.canonical.revision,
    expectedR1: expectedMain.descriptor,
    expectedR2: expectedReceipt.descriptor
  }
})

/** Durable-ready symmetric RESTORE path; internal test fixture only. */
export interface Dnrd5V2RestorePreparedFixture {
  readonly input: Dnrd5V2TwoCasRestoreInput
  readonly s0Revision: number
  readonly expectedR1: CanonicalAtomV2ContentDescriptor
  readonly expectedR2: CanonicalAtomV2ContentDescriptor
  /** Fixture-only raw R1/R2/R3 structural witness; not execution evidence. */
  readonly projectionInput: Dnrd5V2ExactW0RestoreProjectionInput
  readonly projectionTransition: CommitCanonicalAtomsV2ContentBound
  readonly expectedR3: CanonicalAtomV2ContentDescriptor
}

export interface Dnrd5V2RestoreFixtureOptions {
  readonly receiptGrammarCrosswire?: boolean
}

export const prepareDnrd5V2RestoreFixture = (
  options: Dnrd5V2RestoreFixtureOptions = {}
): Effect.Effect<Dnrd5V2RestorePreparedFixture, unknown, CanonicalAtomV2DurableRuntime> =>
  Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const graph = makeGraph()
    const bootstrap = command(
      "transition:dnrd5:v2:restore-bootstrap", 0,
      "principal:dnrd5:v2:bootstrap", BOOTSTRAP_AUTHORIZATION, BOOTSTRAP_SCOPE,
      graph.contents.map((value) => value.atom), []
    )
    const bootstrapTransition = yield* bindCommand(runtime, bootstrap, payloadMap(graph.contents))
    yield* commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal(runtime, bootstrapTransition)
    // Detached W0 root/readset are durable content addressed blobs, not atoms.
    if (!sameCanonicalAtomV2ContentDescriptor(yield* runtime.stageContent("application/json", graph.w0Projection.rootBytes), graph.w0Projection.rootDescriptor) || !sameCanonicalAtomV2ContentDescriptor(yield* runtime.stageContent("application/json", graph.w0Projection.readsetBytes), graph.w0Projection.readsetDescriptor)) throw new Error("fixture W0 detached content descriptor drifted")
    const preAdmit = yield* runtime.snapshot
    const stagingMain = consumptionCandidate(
      "MAIN_ADMIT", preAdmit.canonical, snapshotFor(preAdmit), graph.main,
      graph.decision.atom,
      (consumptionStub) => support("staging-macro", "macro_disposition", [
        ["proposal", graph.proposal.atom],
        ["revision-admission-decision", graph.decision.atom],
        ["restore-policy", graph.restorePolicy.atom],
        ["effect-consumption", consumptionStub]
      ])
    )
    const stagingMainTransition = yield* bindCommand(
      runtime, stagingMain.command, payloadMap([stagingMain.consumption, stagingMain.companion])
    )
    yield* stageConsumptionIntent(runtime, stagingMain)
    yield* commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal(runtime, stagingMainTransition)
    const afterStagingMain = yield* runtime.snapshot
    const stagingRecord = recordFor(preAdmit, stagingMain.command, stagingMainTransition)
    const stagingEffectInput = {
      schema, preState: preAdmit.canonical,
      predecessor: { descriptor: preAdmit.journalHead, journalLineageId: preAdmit.journalLineageId, schemaContentSha256: preAdmit.schema.content.sha256 },
      command: stagingMain.command, record: stagingRecord.record, recordBytes: stagingRecord.bytes,
      recordDescriptor: stagingRecord.descriptor, envelopes: stagingRecord.envelopes,
      usedRecordDescriptorSha256s: []
    } as const
    const stagingEffect = right(
      validateDnrd5V2RecordBoundEffect(stagingEffectInput),
      "staging effect"
    )
    const stagingReceiptBytes = right(canonicalDnrd5V2ReceiptPayloadBytes({
      contractVersion: DNRD5_V2_RECEIPT_SEAL_V1, receiptKind: "REVISION",
      precedingEffectRecordDescriptorSha256: stagingRecord.descriptor.sha256,
      postcommitReceiptIdentity: stagingEffect.deterministicFuturePostcommitReceiptIdentity,
      decisionAtomKeyId: id(graph.decision.atom),
      effectConsumptionAtomKeyId: id(stagingMain.consumption.atom),
      effectAtomKeyId: id(stagingMain.companion.atom)
    }), "staging receipt")
    const stagingReceipt = consumptionCandidate(
      "RECEIPT_ADMIT", afterStagingMain.canonical, snapshotFor(afterStagingMain), graph.evidence,
      graph.decision.atom,
      (consumptionStub) => contentFromBytes(
        "receipt:" + stagingEffect.deterministicFuturePostcommitReceiptIdentity,
        "revision_transition_receipt", DNRD5_V2_RECEIPT_PAYLOAD_MEDIA_TYPE, stagingReceiptBytes,
        [reference("decision", graph.decision.atom), reference("effect-consumption", stagingMain.consumption.atom),
          reference("successor", stagingMain.companion.atom), reference("evidence-consumption", consumptionStub)]
      )
    )
    const stagingReceiptTransition = yield* bindCommand(
      runtime, stagingReceipt.command, payloadMap([stagingReceipt.consumption, stagingReceipt.companion])
    )
    yield* stageConsumptionIntent(runtime, stagingReceipt)
    const stagingReceiptRecord = recordFor(
      afterStagingMain,
      stagingReceipt.command,
      stagingReceiptTransition
    )
    right(validateDnrd5V2ReceiptSeal({
      schema,
      preState: afterStagingMain.canonical,
      predecessor: {
        descriptor: stagingRecord.descriptor,
        journalLineageId: afterStagingMain.journalLineageId,
        schemaContentSha256: afterStagingMain.schema.content.sha256
      },
      precedingEffect: stagingEffectInput,
      command: stagingReceipt.command,
      evidenceAuthority: authorityInput(
        afterStagingMain.canonical,
        graph.evidence.chain
      ),
      receiptPayloadBytes: stagingReceiptBytes,
      receiptPayloadDescriptor: stagingReceipt.companion.atom.content,
      record: stagingReceiptRecord.record,
      recordBytes: stagingReceiptRecord.bytes,
      recordDescriptor: stagingReceiptRecord.descriptor,
      envelopes: stagingReceiptRecord.envelopes,
      usedReceiptRecordDescriptorSha256s: []
    }), "staging receipt seal")
    yield* commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal(runtime, stagingReceiptTransition)
    const afterStaging = yield* runtime.snapshot

    const restoreAuthorityPolicyBase = content("restore-authority-policy", "permit_policy", DNRD5_V2_PERMIT_POLICY_MEDIA_TYPE, {
      contractVersion: DNRD5_V2_AUTHORITY_PAYLOAD_V1, scope: SCOPE, allowedActors: [ACTOR],
      allowedPhases: ["MAIN_RESTORE", "RECEIPT_RESTORE"], allowMainReceiptPairing: true, generation: 1
    })
    const restoreAuthorityPolicy: Content = {
      ...restoreAuthorityPolicyBase,
      atom: {
        ...restoreAuthorityPolicyBase.atom,
        provenance: {
          mode: "DERIVATION",
          evidenceSha256: restoreAuthorityPolicyBase.atom.provenance.evidenceSha256,
          sourceRef: graph.restorePolicy.atom.key
        }
      }
    }
    // The main RESTORE authority can be made before its purpose exists; its
    // payload binds only the eventual purpose key.  The rollback decision and
    // restore transaction then share this exact grant/policy lineage.
    const restoreMain = authority("restore-main", "MAIN_RESTORE", restoreAuthorityPolicy, stub("rollback-decision"))
    const restorePolicy = support("restore-policy-restore", "restore_policy", [
      ["policy", restoreAuthorityPolicy.atom], ["capability", restoreMain.chain.capability.atom]
    ])
    const rollback = support("rollback-decision", "rollback_decision", [
      ["block", graph.contents.find((value) => value.atom.key.atomUid === "block")!.atom],
      ["assignment", graph.contents.find((value) => value.atom.key.atomUid === "assignment")!.atom],
      ["fork", graph.contents.find((value) => value.atom.key.atomUid === "fork-1")!.atom],
      ["w0", graph.contents.find((value) => value.atom.key.atomUid === "w0")!.atom],
      ["grant", restoreMain.chain.grant.atom], ["policy", restorePolicy.atom],
      ["authorization", restoreMain.chain.authorization.atom], ["capability", restoreMain.chain.capability.atom],
      ["revocation", restoreMain.chain.revocation.atom], ["staging-successor", stagingMain.companion.atom],
      ["staging-receipt", stagingReceipt.companion.atom]
    ])
    const alternateRollback = support(
      "rollback-decision-alternate",
      "rollback_decision",
      [
        ["block", graph.contents.find((value) => value.atom.key.atomUid === "block")!.atom],
        ["assignment", graph.contents.find((value) => value.atom.key.atomUid === "assignment")!.atom],
        ["fork", graph.contents.find((value) => value.atom.key.atomUid === "fork-2")!.atom],
        ["w0", graph.contents.find((value) => value.atom.key.atomUid === "w0")!.atom],
        ["grant", restoreMain.chain.grant.atom], ["policy", restorePolicy.atom],
        ["authorization", restoreMain.chain.authorization.atom], ["capability", restoreMain.chain.capability.atom],
        ["revocation", restoreMain.chain.revocation.atom], ["staging-successor", stagingMain.companion.atom],
        ["staging-receipt", stagingReceipt.companion.atom]
      ]
    )
    const restoreEvidence = authority("restore-evidence", "RECEIPT_RESTORE", restoreAuthorityPolicy, rollback.atom)
    const restoreSupport = [restoreAuthorityPolicy, restorePolicy, rollback, alternateRollback,
      restoreMain.chain.authorization, restoreMain.chain.capability, restoreMain.chain.revocation, restoreMain.chain.grant,
      restoreEvidence.chain.authorization, restoreEvidence.chain.capability, restoreEvidence.chain.revocation, restoreEvidence.chain.grant]
    const supportCommand = command("transition:dnrd5:v2:restore-support", afterStaging.canonical.revision, ACTOR, MAIN_CAPABILITY_ID, SCOPE,
      restoreSupport.map((value) => value.atom), externalReadSet(restoreSupport.map((value) => value.atom)))
    const supportTransition = yield* bindCommand(runtime, supportCommand, payloadMap(restoreSupport))
    yield* commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal(runtime, supportTransition)
    const s0 = yield* runtime.snapshot
    const main = consumptionCandidate("MAIN_RESTORE", s0.canonical, snapshotFor(s0), restoreMain, rollback.atom,
      (consumptionStub) => support("restore-transaction", "restore_transaction", [
        ["w0", graph.contents.find((value) => value.atom.key.atomUid === "w0")!.atom],
        ["grant", restoreMain.chain.grant.atom], ["policy", restorePolicy.atom], ["decision", rollback.atom],
        ["consumption", consumptionStub], ["staging-successor", stagingMain.companion.atom]
      ])
    )
    const mainTransition = yield* bindCommand(runtime, main.command, payloadMap([main.consumption, main.companion]))
    const expectedMain = recordFor(s0, main.command, mainTransition)
    const restoreEffectInput = {
      schema, preState: s0.canonical,
      predecessor: { descriptor: s0.journalHead, journalLineageId: s0.journalLineageId, schemaContentSha256: s0.schema.content.sha256 },
      command: main.command, record: expectedMain.record, recordBytes: expectedMain.bytes, recordDescriptor: expectedMain.descriptor,
      envelopes: expectedMain.envelopes, usedRecordDescriptorSha256s: []
    } as const
    const effect = right(validateDnrd5V2RecordBoundEffect(restoreEffectInput), "restore effect")
    const rollbackReceiptBytes = right(canonicalDnrd5V2ReceiptPayloadBytes({
      contractVersion: DNRD5_V2_RECEIPT_SEAL_V1, receiptKind: "ROLLBACK",
      precedingEffectRecordDescriptorSha256: expectedMain.descriptor.sha256,
      postcommitReceiptIdentity: effect.deterministicFuturePostcommitReceiptIdentity,
      decisionAtomKeyId: id(rollback.atom), effectConsumptionAtomKeyId: id(main.consumption.atom), effectAtomKeyId: id(main.companion.atom)
    }), "rollback receipt")
    const receipt = consumptionCandidate("RECEIPT_RESTORE", expectedMain.state.canonical, snapshotFor(expectedMain.state), restoreEvidence, rollback.atom,
      (consumptionStub) => contentFromBytes("receipt:" + effect.deterministicFuturePostcommitReceiptIdentity,
        "rollback_transition_receipt", DNRD5_V2_RECEIPT_PAYLOAD_MEDIA_TYPE, rollbackReceiptBytes,
        [reference("decision", options.receiptGrammarCrosswire ? alternateRollback.atom : rollback.atom),
          reference("effect-consumption", main.consumption.atom), reference("restore", main.companion.atom), reference("evidence-consumption", consumptionStub)])
    )
    const receiptTransition = yield* bindCommand(runtime, receipt.command, payloadMap([receipt.consumption, receipt.companion]))
    const expectedReceipt = recordFor(expectedMain.state, receipt.command, receiptTransition)
    const rollbackSealInput = {
      schema, preState: expectedMain.state.canonical,
      predecessor: { descriptor: expectedMain.descriptor, journalLineageId: expectedMain.state.journalLineageId, schemaContentSha256: expectedMain.state.schema.content.sha256 },
      precedingEffect: restoreEffectInput, command: receipt.command,
      evidenceAuthority: authorityInput(expectedMain.state.canonical, restoreEvidence.chain),
      receiptPayloadBytes: rollbackReceiptBytes, receiptPayloadDescriptor: receipt.companion.atom.content,
      record: expectedReceipt.record, recordBytes: expectedReceipt.bytes, recordDescriptor: expectedReceipt.descriptor,
      envelopes: expectedReceipt.envelopes, usedReceiptRecordDescriptorSha256s: []
    } as const
    if (!options.receiptGrammarCrosswire) right(validateDnrd5V2ReceiptSeal(rollbackSealInput), "rollback receipt seal")
    const projectionId = id(support("post-restore-projection", "behavior_projection", [["source", main.companion.atom], ["policy", graph.projectionPolicy.atom]]).atom)
    const selected = right(canonicalJsonBytes({ _tag: "Dnrd5V2CompiledBehaviorReadset", contractVersion: DNRD5_V2_COMPILED_BEHAVIOR_READSET_V1, behavioralRootSha256: graph.w0Projection.rootDescriptor.sha256, atomKeyIds: [graph.contents.find((value) => value.atom.key.atomUid === "policy")!, graph.contents.find((value) => value.atom.key.atomUid === "randomness")!, graph.contents.find((value) => value.atom.key.atomUid === "evaluator")!, graph.contents.find((value) => value.atom.key.atomUid === "block")!, graph.contents.find((value) => value.atom.key.atomUid === "probe")!].map((value) => id(value.atom)).sort() }), "fixture selected W0 readset")
    if (!sameCanonicalAtomV2ContentDescriptor(right(makeCanonicalAtomV2ContentDescriptor("application/json", selected), "selected descriptor"), graph.w0Projection.readsetDescriptor)) throw new Error("fixture W0 readset bytes drifted")
    const selectedIds = [graph.contents.find((value) => value.atom.key.atomUid === "policy")!, graph.contents.find((value) => value.atom.key.atomUid === "randomness")!, graph.contents.find((value) => value.atom.key.atomUid === "evaluator")!, graph.contents.find((value) => value.atom.key.atomUid === "block")!, graph.contents.find((value) => value.atom.key.atomUid === "probe")!].map((value) => id(value.atom)).sort()
    const excludedAtomKeyIds = [...expectedReceipt.state.canonical.atoms.map(id), projectionId].filter((atomId) => !selectedIds.includes(atomId)).sort()
    const projectionBytes = right(canonicalJsonBytes({ _tag: "Dnrd5V2ExactW0BehaviorProjection", contractVersion: DNRD5_V2_EXACT_W0_RESTORE_PROJECTION_V1, w0SnapshotAtomKeyId: id(graph.contents.find((value) => value.atom.key.atomUid === "w0")!.atom), restoreTransactionAtomKeyId: id(main.companion.atom), behavioralRoot: graph.w0Projection.rootDescriptor, compiledReadset: graph.w0Projection.readsetDescriptor, excludedAtomKeyIds }), "fixture R3 projection")
    const projection = contentFromBytes("post-restore-projection", "behavior_projection", DNRD5_V2_EXACT_W0_PROJECTION_MEDIA_TYPE, projectionBytes, [reference("source", main.companion.atom), reference("policy", graph.projectionPolicy.atom)])
    const projectionCommand = command("transition:dnrd5:v2:exact-w0-projection-r3", expectedReceipt.state.canonical.revision, ACTOR, MAIN_CAPABILITY_ID, SCOPE, [projection.atom], [main.companion.atom.key, graph.projectionPolicy.atom.key].sort((a, b) => canonicalAtomV2KeyId(a).localeCompare(canonicalAtomV2KeyId(b))))
    const projectionTransition = yield* bindCommand(runtime, projectionCommand, payloadMap([projection]))
    const expectedProjection = recordFor(expectedReceipt.state, projectionCommand, projectionTransition)
    return {
      input: { _tag: "Dnrd5V2TwoCasRestoreInput", contractVersion: DNRD5_V2_TWO_CAS_RESTORE_V1,
        main: phaseInput(authorityInput(s0.canonical, restoreMain.chain), main, mainTransition),
        receipt: phaseInput(authorityInput(expectedMain.state.canonical, restoreEvidence.chain), receipt, receiptTransition) },
      s0Revision: s0.canonical.revision, expectedR1: expectedMain.descriptor, expectedR2: expectedReceipt.descriptor,
      expectedR3: expectedProjection.descriptor, projectionTransition,
      projectionInput: {
        schema, restoreEffect: restoreEffectInput, rollbackSeal: rollbackSealInput,
        projectionCommit: { command: projectionCommand, record: expectedProjection.record, recordBytes: expectedProjection.bytes, recordDescriptor: expectedProjection.descriptor, envelope: expectedProjection.envelopes[0]! },
        postProjectionState: expectedProjection.state.canonical, postProjectionStateRevision: expectedProjection.state.canonical.revision, postProjectionStateSha256: right(canonicalAtomV2StateSha256(expectedProjection.state.canonical), "R3 state hash"),
        projection: { _tag: "Dnrd5V2ExactW0BehaviorProjection", contractVersion: DNRD5_V2_EXACT_W0_RESTORE_PROJECTION_V1, w0SnapshotAtomKeyId: id(graph.contents.find((value) => value.atom.key.atomUid === "w0")!.atom), restoreTransactionAtomKeyId: id(main.companion.atom), behavioralRoot: graph.w0Projection.rootDescriptor, compiledReadset: graph.w0Projection.readsetDescriptor, excludedAtomKeyIds },
        contentBySha256: new Map([[graph.contents.find((value) => value.atom.key.atomUid === "w0")!.atom.content.sha256, graph.w0Projection.targetBytes], [graph.w0Projection.rootDescriptor.sha256, graph.w0Projection.rootBytes], [graph.w0Projection.readsetDescriptor.sha256, graph.w0Projection.readsetBytes], [projection.atom.content.sha256, projectionBytes]])
      }
    }
  })

/** Optional fixture-level generic-durable self-check; no dispatcher claim. */
export const verifyDnrd5V2RestoreFixtureGenericDurability = () =>
  Effect.gen(function* () {
    const fixture = yield* prepareDnrd5V2RestoreFixture()
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const first = yield* commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal(
      runtime,
      fixture.input.main.transition
    )
    if (!sameCanonicalAtomV2ContentDescriptor(first.receipt.record, fixture.expectedR1)) {
      throw new Error("restore fixture generic R1 descriptor drifted")
    }
    const second = yield* commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal(
      runtime,
      fixture.input.receipt.transition
    )
    if (!sameCanonicalAtomV2ContentDescriptor(second.receipt.record, fixture.expectedR2)) {
      throw new Error("restore fixture generic R2 descriptor drifted")
    }
    const state = yield* runtime.snapshot
    if (state.canonical.revision !== fixture.s0Revision + 2) {
      throw new Error("restore fixture generic commits did not advance two revisions")
    }
    return fixture
  })
