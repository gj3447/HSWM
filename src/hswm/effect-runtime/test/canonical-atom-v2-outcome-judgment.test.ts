import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import {
  makeCanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2SchemaContentBinding
} from "../src/canonical-atom-v2-content.js"
import { canonicalJsonBytes } from "../src/canonical-atom-v2-json.js"
import {
  HSWM_CANONICAL_OWNER_BOUND_OUTCOME_V1_CONTRACT_VERSION,
  canonicalAtomV2OwnerBoundOutcomeJudgmentBundleBytes,
  canonicalAtomV2OwnerBoundOutcomeRecordBytes,
  decodeCanonicalAtomV2OwnerBoundOutcomeJudgmentBundleBytes,
  decodeCanonicalAtomV2OwnerBoundOutcomeRecordBytes,
  describeCanonicalAtomV2OwnerBoundOutcomeRecord,
  validateCanonicalAtomV2OwnerBoundOutcomeJudgmentBundle,
  type CanonicalAtomV2OwnerBoundOutcomeJudgmentBundle,
  type CanonicalAtomV2OwnerBoundOutcomeObservation,
  type CanonicalAtomV2RevisionSupportJudgment
} from "../src/canonical-atom-v2-outcome-judgment.js"
import {
  HSWM_SUPERSEDES_REFERENCE_ROLE,
  HSWM_SUPERSEDES_REFERENCE_TYPE,
  type CanonicalAtomV2,
  type CanonicalAtomV2Key,
  type CommitCanonicalAtomsV2Command
} from "../src/canonical-atom-v2-schema.js"
import {
  HSWM_CANONICAL_TRANSITION_PROPOSAL_V1_MEDIA_TYPE,
  describeCanonicalAtomV2TransitionEvidenceRecord,
  type CanonicalAtomV2SealedTrajectoryEvidence
} from "../src/canonical-atom-v2-transition-evidence.js"

const SCHEMA_VERSION = "hswm:test:owner-bound-outcome:v1"
const ACTOR = "principal:actor"
const SEALED_AT = "2026-08-31T10:00:00.000Z"

const unwrap = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw value.left
  return value.right
}

const descriptor = (mediaType: string, value: unknown) =>
  unwrap(
    makeCanonicalAtomV2ContentDescriptor(
      mediaType,
      unwrap(canonicalJsonBytes(value))
    )
  )

const opaque = (id: string): CanonicalAtomV2ContentDescriptor =>
  descriptor("application/json", { id })

const key = (
  atomUid: string,
  lineageId: string,
  revisionId: number
): CanonicalAtomV2Key => ({
  schemaVersion: SCHEMA_VERSION,
  lineageId,
  atomUid,
  revisionId
})

const predecessorKey = key("atom:target", "lineage:a-target", 0)
const candidateKey = key("atom:target", "lineage:a-target", 1)
const traceKey = key("trace:one", "lineage:z-trace", 0)

const schema: CanonicalAtomV2SchemaContentBinding = {
  schemaVersion: SCHEMA_VERSION,
  content: opaque("schema")
}

const candidate: CanonicalAtomV2 = {
  _tag: "CanonicalAtomV2",
  contractVersion: "hswm-canonical-atom/v2",
  key: candidateKey,
  kind: "kind:revision",
  responsibilityOwner: "owner:revision",
  content: {
    mediaType: "application/json",
    byteLength: opaque("candidate").byteLength,
    sha256: opaque("candidate").sha256
  },
  provenance: {
    mode: "DERIVATION",
    evidenceSha256: "1".repeat(64),
    sourceRef: predecessorKey
  },
  lifecycle: "ADMITTED",
  references: [{
    referenceType: HSWM_SUPERSEDES_REFERENCE_TYPE,
    role: HSWM_SUPERSEDES_REFERENCE_ROLE,
    target: predecessorKey
  }]
}

const proposal: CommitCanonicalAtomsV2Command = {
  _tag: "CommitCanonicalAtomsV2",
  contractVersion: "hswm-canonical-transition/v2",
  transitionId: "transition:outcome-judgment",
  expectedStateRevision: 0,
  schemaVersion: SCHEMA_VERSION,
  actorClaim: ACTOR,
  authorizationRef: "authorization:one",
  scope: "scope:revision",
  decidedAt: "2026-08-31T09:59:30.000Z",
  traceRef: traceKey,
  readSet: [predecessorKey, traceKey],
  writes: [candidate],
  provenanceSha256: "2".repeat(64)
}

const proposalDescriptor = descriptor(
  HSWM_CANONICAL_TRANSITION_PROPOSAL_V1_MEDIA_TYPE,
  proposal
)

const trajectory: CanonicalAtomV2SealedTrajectoryEvidence = {
  _tag: "CanonicalAtomV2SealedTrajectoryEvidence",
  contractVersion: "hswm-canonical-transition-evidence/v1",
  traceId: traceKey.atomUid,
  schema,
  claimedPredecessor: opaque("predecessor-state"),
  claimedPredecessorStateRevision: 0,
  proposal: proposalDescriptor,
  traceRef: traceKey,
  claimant: { address: ACTOR },
  sealer: { address: "principal:sealer" },
  readSet: proposal.readSet,
  writeSet: [candidateKey],
  events: [{
    sequence: 0,
    kind: "ACTION",
    content: opaque("trajectory-event")
  }],
  sealedAt: SEALED_AT,
  provenance: {
    collector: { address: "principal:collector" },
    method: "method:sealed-trace",
    collectedAt: "2026-08-31T09:59:59.000Z",
    source: opaque("trajectory-source"),
    status: "CLAIMED_NOT_TRUTH"
  }
}

const trajectoryDescriptor = unwrap(
  describeCanonicalAtomV2TransitionEvidenceRecord(trajectory)
)

interface FixtureOptions {
  readonly observationOwner?: string
  readonly evaluator?: string
  readonly judgmentOwner?: string
  readonly adjudicator?: string
  readonly result?: CanonicalAtomV2OwnerBoundOutcomeObservation["result"]
  readonly verdict?: CanonicalAtomV2RevisionSupportJudgment["verdict"]
}

const makeBundle = (
  options: FixtureOptions = {}
): CanonicalAtomV2OwnerBoundOutcomeJudgmentBundle => {
  const result = options.result ?? "OBSERVED"
  const observation: CanonicalAtomV2OwnerBoundOutcomeObservation = {
    _tag: "CanonicalAtomV2OwnerBoundOutcomeObservation",
    contractVersion: HSWM_CANONICAL_OWNER_BOUND_OUTCOME_V1_CONTRACT_VERSION,
    schema,
    observationId: "observation:one",
    traceId: trajectory.traceId,
    trajectory: trajectoryDescriptor,
    responsibilityOwner: {
      address: options.observationOwner ?? "owner:outcome"
    },
    evaluator: { address: options.evaluator ?? "principal:evaluator" },
    observedAt: "2026-08-31T10:01:00.000Z",
    observation: result === "UNKNOWN" ? null : opaque("observed-value"),
    result,
    evidence: opaque("observation-evidence"),
    ownerStatus: "REPRESENTED_SINGLE_RESPONSIBILITY_OWNER_NOT_AUTHENTICATED",
    independence: "DECLARED_ROLE_SEPARATION_NOT_INDEPENDENTLY_PROVEN",
    observationStatus: "REPRESENTED_OBSERVATION_NOT_TRUTH_NOT_REVISION_SUPPORT"
  }
  const observationDescriptor = unwrap(
    describeCanonicalAtomV2OwnerBoundOutcomeRecord(observation)
  )
  const judgment: CanonicalAtomV2RevisionSupportJudgment = {
    _tag: "CanonicalAtomV2RevisionSupportJudgment",
    contractVersion: HSWM_CANONICAL_OWNER_BOUND_OUTCOME_V1_CONTRACT_VERSION,
    schema,
    judgmentId: "judgment:one",
    traceId: trajectory.traceId,
    observationId: observation.observationId,
    proposal: proposalDescriptor,
    trajectory: trajectoryDescriptor,
    observation: observationDescriptor,
    target: {
      schemaVersion: candidateKey.schemaVersion,
      lineageId: candidateKey.lineageId,
      atomUid: candidateKey.atomUid
    },
    expectedRevisionId: predecessorKey.revisionId,
    candidateRevisionId: candidateKey.revisionId,
    responsibilityOwner: {
      address: options.judgmentOwner ?? "owner:credit-decision"
    },
    adjudicator: {
      address: options.adjudicator ?? "principal:credit-adjudicator"
    },
    criterion: opaque("precommitted-criterion"),
    criterionCommittedAt: "2026-08-31T09:58:00.000Z",
    decidedAt: "2026-08-31T10:02:00.000Z",
    verdict: options.verdict ?? "SUPPORTS",
    evidence: opaque("judgment-evidence"),
    ownerStatus: "REPRESENTED_SINGLE_RESPONSIBILITY_OWNER_NOT_AUTHENTICATED",
    independence: "DECLARED_ROLE_SEPARATION_NOT_INDEPENDENTLY_PROVEN",
    judgmentStatus: "REPRESENTED_REVISION_SUPPORT_JUDGMENT_NOT_TRUTH_NOT_CAUSAL_CREDIT_NOT_PERMIT_NOT_ADMISSION_NOT_LEARNING"
  }
  return {
    _tag: "CanonicalAtomV2OwnerBoundOutcomeJudgmentBundle",
    contractVersion: HSWM_CANONICAL_OWNER_BOUND_OUTCOME_V1_CONTRACT_VERSION,
    schema,
    proposal,
    proposalDescriptor,
    trajectory,
    trajectoryDescriptor,
    observation,
    observationDescriptor,
    judgment,
    judgmentDescriptor: unwrap(
      describeCanonicalAtomV2OwnerBoundOutcomeRecord(judgment)
    ),
    bundleStatus: "STRUCTURALLY_BOUND_NOT_TRUTH_NOT_CAUSAL_CREDIT_NOT_PERMIT_NOT_ADMISSION_NOT_LEARNING"
  }
}

it("binds one observation and separately owned support judgment", () => {
  const checked = unwrap(
    validateCanonicalAtomV2OwnerBoundOutcomeJudgmentBundle(makeBundle())
  )

  expect(checked.judgment.verdict).toBe("SUPPORTS")
  expect(checked.observation.responsibilityOwner.address).not.toBe(
    checked.judgment.responsibilityOwner.address
  )
  expect(checked.observation.evaluator.address).not.toBe(
    checked.judgment.adjudicator.address
  )
  expect(checked.bundleStatus).toContain("NOT_CAUSAL_CREDIT")
  expect(Object.isFrozen(checked)).toBe(true)
  expect(Object.isFrozen(checked.judgment)).toBe(true)
})

it("keeps an observation record explicitly below revision support", () => {
  const observation = makeBundle().observation
  const bytes = unwrap(canonicalAtomV2OwnerBoundOutcomeRecordBytes(observation))
  const decoded = unwrap(
    decodeCanonicalAtomV2OwnerBoundOutcomeRecordBytes(bytes)
  )

  expect(decoded._tag).toBe("CanonicalAtomV2OwnerBoundOutcomeObservation")
  if (decoded._tag === "CanonicalAtomV2OwnerBoundOutcomeObservation") {
    expect(decoded.observationStatus).toBe(
      "REPRESENTED_OBSERVATION_NOT_TRUTH_NOT_REVISION_SUPPORT"
    )
  }
})

it("round-trips the exact canonical bundle bytes", () => {
  const bytes = unwrap(
    canonicalAtomV2OwnerBoundOutcomeJudgmentBundleBytes(makeBundle())
  )
  const decoded = unwrap(
    decodeCanonicalAtomV2OwnerBoundOutcomeJudgmentBundleBytes(bytes)
  )

  expect(decoded.judgment.judgmentId).toBe("judgment:one")
  expect(
    unwrap(canonicalAtomV2OwnerBoundOutcomeJudgmentBundleBytes(decoded))
  ).toEqual(bytes)
})

it("rejects actor-owned outcome evidence and collapsed evaluator roles", () => {
  for (const hostile of [
    makeBundle({ observationOwner: ACTOR }),
    makeBundle({ adjudicator: "principal:evaluator" })
  ]) {
    const rejected = validateCanonicalAtomV2OwnerBoundOutcomeJudgmentBundle(
      hostile
    )
    expect(Either.isLeft(rejected)).toBe(true)
    if (Either.isLeft(rejected)) {
      expect(rejected.left.code).toBe("ROLE_SEPARATION_INVALID")
    }
  }
})

it("represents rejection without turning it into learning", () => {
  const checked = unwrap(
    validateCanonicalAtomV2OwnerBoundOutcomeJudgmentBundle(
      makeBundle({ verdict: "REJECTS" })
    )
  )

  expect(checked.judgment.verdict).toBe("REJECTS")
  expect(checked.judgment.judgmentStatus).toContain("NOT_LEARNING")
})

it("rejects SUPPORTS when no observed outcome content exists", () => {
  const rejected = validateCanonicalAtomV2OwnerBoundOutcomeJudgmentBundle(
    makeBundle({ result: "UNKNOWN", verdict: "SUPPORTS" })
  )

  expect(Either.isLeft(rejected)).toBe(true)
  if (Either.isLeft(rejected)) {
    expect(rejected.left.code).toBe("VERDICT_INVALID")
  }
})

it("rejects a recomputed judgment that names another candidate revision", () => {
  const original = makeBundle()
  const judgment: CanonicalAtomV2RevisionSupportJudgment = {
    ...original.judgment,
    candidateRevisionId: 2
  }
  const hostile: CanonicalAtomV2OwnerBoundOutcomeJudgmentBundle = {
    ...original,
    judgment,
    judgmentDescriptor: unwrap(
      describeCanonicalAtomV2OwnerBoundOutcomeRecord(judgment)
    )
  }
  const rejected = validateCanonicalAtomV2OwnerBoundOutcomeJudgmentBundle(
    hostile
  )

  expect(Either.isLeft(rejected)).toBe(true)
  if (Either.isLeft(rejected)) {
    expect(rejected.left.code).toBe("REVISION_INVALID")
  }
})

it("rejects a supplied descriptor that does not describe its record bytes", () => {
  const original = makeBundle()
  const rejected = validateCanonicalAtomV2OwnerBoundOutcomeJudgmentBundle({
    ...original,
    observationDescriptor: opaque("forged-observation-descriptor")
  })

  expect(Either.isLeft(rejected)).toBe(true)
  if (Either.isLeft(rejected)) {
    expect(rejected.left.code).toBe("DESCRIPTOR_MISMATCH")
  }
})
