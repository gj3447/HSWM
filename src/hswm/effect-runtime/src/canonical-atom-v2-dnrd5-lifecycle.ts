/**
 * Pure DNRD-5 block-lifecycle integrity validator.
 *
 * It binds opaque content descriptors into a sealed chronology. It neither
 * reads their bytes nor establishes Permit, admission, external occurrence,
 * causal learning, or a scientific result.
 */
import { Data, Either, Schema } from "effect"

import {
  CanonicalAtomV2ContentDescriptorSchema,
  type CanonicalAtomV2ContentDescriptor
} from "./canonical-atom-v2-content.js"
import { canonicalJsonSha256 } from "./canonical-atom-v2-json.js"
import {
  DNRD5_ARM_LABELS,
  DNRD5_SCHEMA_VERSION,
  type Dnrd5ArmLabel
} from "./canonical-atom-v2-dnrd5-schema.js"

export const DNRD5_LIFECYCLE_CONTRACT_VERSION =
  "hswm-dnrd5-lifecycle-integrity/v1" as const

export const DNRD5_BLOCK_EVENT_SEQUENCE = [
  "STUDY_AND_TASK_COMMITMENTS",
  "PROBE_AND_PLACEBO_COMMITMENTS",
  "W0_AND_FOUR_FORKS",
  "ARM_ASSIGNMENT",
  "EPISODE_AND_TRAJECTORY_CONTRACT",
  "TRAJECTORY_SEAL",
  "EVALUATOR_RELEASE_AND_HIDDEN_OUTCOME",
  "ESCROW_PLACEBO_AND_FEEDBACK_ASSIGNMENTS",
  "FOUR_PROPOSALS",
  "VALIDATION_CREDIT_TRANSITIONS_AND_RESTORE",
  "FOUR_BEHAVIOR_PROJECTIONS",
  "FOUR_PROBE_RESPONSE_SEALS",
  "FOUR_BLIND_PROBE_OUTCOMES",
  "DELAYED_OUTCOME_AUDIT_RELEASE",
  "BLOCK_SEAL"
] as const

export type Dnrd5BlockEvent = (typeof DNRD5_BLOCK_EVENT_SEQUENCE)[number]

export const DNRD5_LIFECYCLE_BOUNDARY = Object.freeze({
  contentSemantics: "CONTENT_DESCRIPTOR_BINDING_ONLY",
  permit: "NOT_ISSUED_BY_PURE_LIFECYCLE_VALIDATOR",
  admission: "NOT_IMPLEMENTED_BY_PURE_LIFECYCLE_VALIDATOR",
  scientificTerminal: "NOT_ISSUED_BY_PURE_LIFECYCLE_VALIDATOR",
  blockSealClosure: "SEAL_HASH_CLOSURE_ONLY_CONTENT_SEMANTICS_DEFERRED",
  armLabelManifest: "EXPERIMENT_CUSTODIAN_PRIVATE_VIEW_NOT_MODEL_OR_EVALUATOR_PROJECTION",
  isolation: "MODEL_EVALUATOR_AND_CROSS_SESSION_ISOLATION_NOT_ENFORCED_BY_PURE_LIFECYCLE_VALIDATOR"
} as const)

type ArmArtifactKind =
  | "ARM_ASSIGNMENT"
  | "FEEDBACK_ASSIGNMENT"
  | "REVISION_PROPOSAL"
  | "CANDIDATE_VALIDATION"
  | "CREDIT_DECISION"
  | "ARM_TRANSITION"
  | "TRANSITION_RECEIPT"
  | "RESTORE_TRANSACTION"
  | "BEHAVIOR_PROJECTION"
  | "PROBE_RESPONSE_SEAL"
  | "PROBE_OUTCOME"

export type Dnrd5LifecycleArtifactKind =
  | "STUDY_RANDOMNESS"
  | "BLOCK_SPEC"
  | "EVALUATOR_COMMITMENT"
  | "PROBE_COMMITMENT"
  | "PLACEBO_COMMITMENT"
  | "W0_SNAPSHOT"
  | "FORK_INCIDENCE"
  | "ARM_ASSIGNMENT"
  | "EPISODE_ACTIVATION"
  | "TRAJECTORY_CONTRACT"
  | "TRAJECTORY_SEAL"
  | "EVALUATOR_RELEASE"
  | "HIDDEN_OUTCOME"
  | "OUTCOME_CREDIT_ESCROW"
  | "PLACEBO_RECEIPT"
  | "FEEDBACK_ASSIGNMENT"
  | "REVISION_PROPOSAL"
  | "CANDIDATE_VALIDATION"
  | "CREDIT_DECISION"
  | "ARM_TRANSITION"
  | "TRANSITION_RECEIPT"
  | "RESTORE_TRANSACTION"
  | "BEHAVIOR_PROJECTION"
  | "PROBE_RESPONSE_SEAL"
  | "PROBE_OUTCOME"
  | "DELAYED_AUDIT_RELEASE"
  | "BLOCK_SEAL"

export interface Dnrd5LifecycleArtifact {
  readonly artifactId: string
  readonly kind: Dnrd5LifecycleArtifactKind
  readonly arm: Dnrd5ArmLabel | null
  readonly content: CanonicalAtomV2ContentDescriptor
}

export interface Dnrd5LifecycleEventSeal {
  readonly ordinal: number
  readonly event: Dnrd5BlockEvent
  readonly artifacts: ReadonlyArray<Dnrd5LifecycleArtifact>
  readonly generationCallCount: number
  readonly previousManifestSha256: string | null
  readonly previousSealSha256: string | null
  readonly manifestSha256: string
  readonly blockSealPriorSealHashes: ReadonlyArray<string> | null
  readonly sealSha256: string
}

export interface Dnrd5SealedBlockLifecycle {
  readonly contractVersion: typeof DNRD5_LIFECYCLE_CONTRACT_VERSION
  readonly schemaVersion: typeof DNRD5_SCHEMA_VERSION
  readonly blockId: string
  readonly events: ReadonlyArray<Dnrd5LifecycleEventSeal>
}

export type Dnrd5LifecycleErrorCode =
  | "BLOCK_ID_INVALID"
  | "STRUCTURE_INVALID"
  | "EVENT_ORDER_INVALID"
  | "EVENT_DUPLICATE"
  | "CARDINALITY_INVALID"
  | "ARM_INVALID"
  | "MANIFEST_INVALID"
  | "HASH_CHAIN_INVALID"
  | "BLOCK_SEAL_INVALID"

export class Dnrd5LifecycleError extends Data.TaggedError("Dnrd5LifecycleError")<{
  readonly code: Dnrd5LifecycleErrorCode
  readonly detail: string
}> {}

const fail = (code: Dnrd5LifecycleErrorCode, detail: string) =>
  Either.left(new Dnrd5LifecycleError({ code, detail }))
const releft = <A>(error: Dnrd5LifecycleError): Either.Either<A, Dnrd5LifecycleError> =>
  Either.left(error)

const artifactKinds = new Set<Dnrd5LifecycleArtifactKind>([
  "STUDY_RANDOMNESS", "BLOCK_SPEC", "EVALUATOR_COMMITMENT", "PROBE_COMMITMENT", "PLACEBO_COMMITMENT",
  "W0_SNAPSHOT", "FORK_INCIDENCE", "ARM_ASSIGNMENT", "EPISODE_ACTIVATION", "TRAJECTORY_CONTRACT",
  "TRAJECTORY_SEAL", "EVALUATOR_RELEASE", "HIDDEN_OUTCOME", "OUTCOME_CREDIT_ESCROW", "PLACEBO_RECEIPT",
  "FEEDBACK_ASSIGNMENT", "REVISION_PROPOSAL", "CANDIDATE_VALIDATION", "CREDIT_DECISION", "ARM_TRANSITION", "TRANSITION_RECEIPT", "RESTORE_TRANSACTION", "BEHAVIOR_PROJECTION", "PROBE_RESPONSE_SEAL",
  "PROBE_OUTCOME", "DELAYED_AUDIT_RELEASE", "BLOCK_SEAL"
])
const armArtifactKinds = new Set<ArmArtifactKind>([
  "ARM_ASSIGNMENT", "FEEDBACK_ASSIGNMENT", "REVISION_PROPOSAL", "CANDIDATE_VALIDATION",
  "CREDIT_DECISION", "ARM_TRANSITION", "TRANSITION_RECEIPT", "RESTORE_TRANSACTION",
  "BEHAVIOR_PROJECTION", "PROBE_RESPONSE_SEAL", "PROBE_OUTCOME"
])
const sha = /^[0-9a-f]{64}$/
const identifier = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/
const exactKeys = (value: object, keys: ReadonlyArray<string>): boolean => {
  const actual = Object.keys(value).sort()
  const expected = [...keys].sort()
  return actual.length === expected.length && actual.every((key, index) => key === expected[index])
}

const snapshotArtifact = (artifact: Dnrd5LifecycleArtifact): Dnrd5LifecycleArtifact =>
  Object.freeze({
    artifactId: artifact.artifactId,
    kind: artifact.kind,
    arm: artifact.arm,
    content: Object.freeze({ ...artifact.content })
  })

const snapshotEvent = (event: Dnrd5LifecycleEventSeal): Dnrd5LifecycleEventSeal =>
  Object.freeze({
    ordinal: event.ordinal,
    event: event.event,
    artifacts: Object.freeze(event.artifacts.map(snapshotArtifact)),
    generationCallCount: event.generationCallCount,
    previousManifestSha256: event.previousManifestSha256,
    previousSealSha256: event.previousSealSha256,
    manifestSha256: event.manifestSha256,
    blockSealPriorSealHashes: event.blockSealPriorSealHashes === null
      ? null
      : Object.freeze([...event.blockSealPriorSealHashes]),
    sealSha256: event.sealSha256
  })

interface Dnrd5ArtifactRequirement {
  readonly count: number
  readonly arms: ReadonlyArray<Dnrd5ArmLabel> | null
}

const allArms: ReadonlyArray<Dnrd5ArmLabel> = DNRD5_ARM_LABELS
const stateChangingArms: ReadonlyArray<Dnrd5ArmLabel> = [
  "ACTIVE", "OUTCOME_INDEPENDENT_SHAM", "EXACT_W0_ROLLBACK"
]
const rollbackOnly: ReadonlyArray<Dnrd5ArmLabel> = ["EXACT_W0_ROLLBACK"]
const requirement = (count: number, arms: ReadonlyArray<Dnrd5ArmLabel> | null = null): Dnrd5ArtifactRequirement => ({ count, arms })

const eventRequirements: Readonly<Record<Dnrd5BlockEvent, Readonly<Record<string, Dnrd5ArtifactRequirement>>>> = {
  STUDY_AND_TASK_COMMITMENTS: { STUDY_RANDOMNESS: requirement(1), BLOCK_SPEC: requirement(1), EVALUATOR_COMMITMENT: requirement(1) },
  PROBE_AND_PLACEBO_COMMITMENTS: { PROBE_COMMITMENT: requirement(1), PLACEBO_COMMITMENT: requirement(1) },
  W0_AND_FOUR_FORKS: { W0_SNAPSHOT: requirement(1), FORK_INCIDENCE: requirement(4) },
  ARM_ASSIGNMENT: { ARM_ASSIGNMENT: requirement(4, allArms) },
  EPISODE_AND_TRAJECTORY_CONTRACT: { EPISODE_ACTIVATION: requirement(1), TRAJECTORY_CONTRACT: requirement(1) },
  TRAJECTORY_SEAL: { TRAJECTORY_SEAL: requirement(1) },
  EVALUATOR_RELEASE_AND_HIDDEN_OUTCOME: { EVALUATOR_RELEASE: requirement(1), HIDDEN_OUTCOME: requirement(1) },
  ESCROW_PLACEBO_AND_FEEDBACK_ASSIGNMENTS: { OUTCOME_CREDIT_ESCROW: requirement(1), PLACEBO_RECEIPT: requirement(1), FEEDBACK_ASSIGNMENT: requirement(4, allArms) },
  FOUR_PROPOSALS: { REVISION_PROPOSAL: requirement(4, allArms) },
  VALIDATION_CREDIT_TRANSITIONS_AND_RESTORE: {
    CANDIDATE_VALIDATION: requirement(4, allArms),
    CREDIT_DECISION: requirement(4, allArms),
    ARM_TRANSITION: requirement(4, allArms),
    TRANSITION_RECEIPT: requirement(3, stateChangingArms),
    RESTORE_TRANSACTION: requirement(1, rollbackOnly)
  },
  FOUR_BEHAVIOR_PROJECTIONS: { BEHAVIOR_PROJECTION: requirement(4, allArms) },
  FOUR_PROBE_RESPONSE_SEALS: { PROBE_RESPONSE_SEAL: requirement(4, allArms) },
  FOUR_BLIND_PROBE_OUTCOMES: { PROBE_OUTCOME: requirement(4, allArms) },
  DELAYED_OUTCOME_AUDIT_RELEASE: { DELAYED_AUDIT_RELEASE: requirement(1) },
  BLOCK_SEAL: { BLOCK_SEAL: requirement(1) }
}
const eventCallCounts: Readonly<Record<Dnrd5BlockEvent, number>> = {
  STUDY_AND_TASK_COMMITMENTS: 0, PROBE_AND_PLACEBO_COMMITMENTS: 0, W0_AND_FOUR_FORKS: 0, ARM_ASSIGNMENT: 0,
  EPISODE_AND_TRAJECTORY_CONTRACT: 0, TRAJECTORY_SEAL: 1, EVALUATOR_RELEASE_AND_HIDDEN_OUTCOME: 0,
  ESCROW_PLACEBO_AND_FEEDBACK_ASSIGNMENTS: 0, FOUR_PROPOSALS: 4, VALIDATION_CREDIT_TRANSITIONS_AND_RESTORE: 0, FOUR_BEHAVIOR_PROJECTIONS: 0,
  FOUR_PROBE_RESPONSE_SEALS: 4, FOUR_BLIND_PROBE_OUTCOMES: 0, DELAYED_OUTCOME_AUDIT_RELEASE: 0, BLOCK_SEAL: 0
}

const canonicalHash = (value: unknown): Either.Either<string, Dnrd5LifecycleError> => {
  const hashed = canonicalJsonSha256(value)
  return Either.isLeft(hashed)
    ? fail("STRUCTURE_INVALID", `lifecycle value is not canonical JSON: ${hashed.left.detail}`)
    : Either.right(hashed.right)
}

const validateBlockId = (blockId: string): Either.Either<string, Dnrd5LifecycleError> => {
  const match = /^DNRD5-BLOCK-(\d{4})$/.exec(blockId)
  if (match === null) return fail("BLOCK_ID_INVALID", "block ID must match DNRD5-BLOCK-0001 through DNRD5-BLOCK-0300")
  const ordinal = Number(match[1])
  return ordinal >= 1 && ordinal <= 300
    ? Either.right(blockId)
    : fail("BLOCK_ID_INVALID", "block ID is outside the frozen 300-block universe")
}

const manifestProjection = (
  blockId: string,
  ordinal: number,
  event: Dnrd5BlockEvent,
  artifacts: ReadonlyArray<Dnrd5LifecycleArtifact>
) => ({ blockId, ordinal, event, artifacts })

const sealProjection = (
  blockId: string,
  ordinal: number,
  event: Dnrd5BlockEvent,
  manifestSha256: string,
  previousManifestSha256: string | null,
  previousSealSha256: string | null,
  generationCallCount: number,
  blockSealPriorSealHashes: ReadonlyArray<string> | null
) => ({ blockId, ordinal, event, manifestSha256, previousManifestSha256, previousSealSha256, generationCallCount, blockSealPriorSealHashes })

export const makeDnrd5LifecycleEventSeal = (
  input: Omit<Dnrd5LifecycleEventSeal, "manifestSha256" | "sealSha256">
  & { readonly blockId: string }
): Either.Either<Dnrd5LifecycleEventSeal, Dnrd5LifecycleError> => {
  const manifestSha256 = canonicalHash(manifestProjection(input.blockId, input.ordinal, input.event, input.artifacts))
  if (Either.isLeft(manifestSha256)) return releft(manifestSha256.left)
  const sealSha256 = canonicalHash(sealProjection(input.blockId, input.ordinal, input.event, manifestSha256.right, input.previousManifestSha256, input.previousSealSha256, input.generationCallCount, input.blockSealPriorSealHashes))
  if (Either.isLeft(sealSha256)) return releft(sealSha256.left)
  const { blockId: _blockId, ...event } = input
  return Either.right(snapshotEvent({ ...event, manifestSha256: manifestSha256.right, sealSha256: sealSha256.right }))
}

const validateArtifacts = (
  event: Dnrd5LifecycleEventSeal
): Either.Either<void, Dnrd5LifecycleError> => {
  const required = eventRequirements[event.event]
  const counts = new Map<string, number>()
  const ids = new Set<string>()
  const arms = new Map<string, Set<string>>()
  for (const artifact of event.artifacts) {
    if (typeof artifact !== "object" || artifact === null) {
      return fail("MANIFEST_INVALID", "artifact must be an object")
    }
    if (!exactKeys(artifact, ["artifactId", "kind", "arm", "content"])) {
      return fail("MANIFEST_INVALID", "artifact key set drifted")
    }
    if (!identifier.test(artifact.artifactId) || ids.has(artifact.artifactId) || !artifactKinds.has(artifact.kind)) {
      return fail("MANIFEST_INVALID", "artifact ID is invalid/duplicate or artifact kind is unknown")
    }
    const descriptor = Schema.decodeUnknownEither(CanonicalAtomV2ContentDescriptorSchema, { onExcessProperty: "error" })(artifact.content)
    if (Either.isLeft(descriptor)) return fail("MANIFEST_INVALID", `artifact ${artifact.artifactId} has an invalid content descriptor`)
    const isArmArtifact = armArtifactKinds.has(artifact.kind as ArmArtifactKind)
    if (isArmArtifact !== (artifact.arm !== null) || (artifact.arm !== null && !(DNRD5_ARM_LABELS as ReadonlyArray<string>).includes(artifact.arm))) {
      return fail("ARM_INVALID", `artifact ${artifact.artifactId} has an invalid arm binding`)
    }
    ids.add(artifact.artifactId)
    counts.set(artifact.kind, (counts.get(artifact.kind) ?? 0) + 1)
    if (artifact.arm !== null) {
      const kindArms = arms.get(artifact.kind) ?? new Set<string>()
      kindArms.add(artifact.arm)
      arms.set(artifact.kind, kindArms)
    }
  }
  for (const [kind, requirement] of Object.entries(required)) {
    if (counts.get(kind) !== requirement.count) return fail("CARDINALITY_INVALID", `${event.event} requires exactly ${requirement.count} ${kind} artifacts`)
    if (requirement.arms !== null) {
      const actual = arms.get(kind)
      if (actual === undefined || actual.size !== requirement.arms.length || requirement.arms.some((arm) => !actual.has(arm))) {
        return fail("ARM_INVALID", `${event.event} requires the exact declared arm set for ${kind}`)
      }
    }
  }
  if (event.artifacts.length !== Object.values(required).reduce((total, requirement) => total + requirement.count, 0)) {
    return fail("CARDINALITY_INVALID", `${event.event} contains undeclared extra artifacts`)
  }
  return Either.right(undefined)
}

export const validateDnrd5SealedBlockLifecycle = (
  input: unknown
): Either.Either<Dnrd5SealedBlockLifecycle, Dnrd5LifecycleError> => {
  if (typeof input !== "object" || input === null) return fail("STRUCTURE_INVALID", "lifecycle must be an object")
  if (!exactKeys(input, ["contractVersion", "schemaVersion", "blockId", "events"])) {
    return fail("STRUCTURE_INVALID", "lifecycle root key set drifted")
  }
  const lifecycle = input as Partial<Dnrd5SealedBlockLifecycle>
  if (lifecycle.contractVersion !== DNRD5_LIFECYCLE_CONTRACT_VERSION || lifecycle.schemaVersion !== DNRD5_SCHEMA_VERSION || !Array.isArray(lifecycle.events) || typeof lifecycle.blockId !== "string") {
    return fail("STRUCTURE_INVALID", "lifecycle contract/schema/events are invalid")
  }
  const blockId = validateBlockId(lifecycle.blockId)
  if (Either.isLeft(blockId)) return releft(blockId.left)
  if (lifecycle.events.length !== DNRD5_BLOCK_EVENT_SEQUENCE.length) return fail("EVENT_ORDER_INVALID", "block lifecycle must contain all 15 exact events")
  let previousManifestSha256: string | null = null
  let previousSealSha256: string | null = null
  const priorSealHashes: string[] = []
  const globalArtifactIds = new Set<string>()
  let totalCalls = 0
  const validated: Dnrd5LifecycleEventSeal[] = []
  for (const [index, candidate] of lifecycle.events.entries()) {
    if (typeof candidate !== "object" || candidate === null) return fail("STRUCTURE_INVALID", "event seal must be an object")
    if (!exactKeys(candidate, ["ordinal", "event", "artifacts", "generationCallCount", "previousManifestSha256", "previousSealSha256", "manifestSha256", "blockSealPriorSealHashes", "sealSha256"])) {
      return fail("STRUCTURE_INVALID", "event seal key set drifted")
    }
    const event = candidate as Dnrd5LifecycleEventSeal
    if (
      !Number.isSafeInteger(event.ordinal) ||
      typeof event.event !== "string" ||
      !Array.isArray(event.artifacts) ||
      !Number.isSafeInteger(event.generationCallCount) ||
      (event.previousManifestSha256 !== null && (typeof event.previousManifestSha256 !== "string" || !sha.test(event.previousManifestSha256))) ||
      (event.previousSealSha256 !== null && (typeof event.previousSealSha256 !== "string" || !sha.test(event.previousSealSha256))) ||
      typeof event.manifestSha256 !== "string" ||
      !sha.test(event.manifestSha256) ||
      typeof event.sealSha256 !== "string" ||
      !sha.test(event.sealSha256) ||
      (event.blockSealPriorSealHashes !== null && !Array.isArray(event.blockSealPriorSealHashes))
    ) return fail("STRUCTURE_INVALID", "event seal has malformed structural fields")
    const expectedEvent = DNRD5_BLOCK_EVENT_SEQUENCE[index]
    if (event.ordinal !== index + 1 || event.event !== expectedEvent) return fail("EVENT_ORDER_INVALID", "event ordinal or exact R2 event sequence drifted")
    if (event.previousManifestSha256 !== previousManifestSha256 || event.previousSealSha256 !== previousSealSha256) return fail("HASH_CHAIN_INVALID", "event does not bind the immediately prior manifest and seal")
    if (event.generationCallCount !== eventCallCounts[event.event]) return fail("CARDINALITY_INVALID", `${event.event} has an invalid generation-call count`)
    const artifacts = validateArtifacts(event)
    if (Either.isLeft(artifacts)) return releft(artifacts.left)
    for (const artifact of event.artifacts) {
      if (globalArtifactIds.has(artifact.artifactId)) {
        return fail("MANIFEST_INVALID", `artifact ID ${artifact.artifactId} repeats across block events`)
      }
      globalArtifactIds.add(artifact.artifactId)
    }
    const manifest = canonicalHash(manifestProjection(blockId.right, event.ordinal, event.event, event.artifacts))
    if (Either.isLeft(manifest) || event.manifestSha256 !== manifest.right) return fail("MANIFEST_INVALID", "event artifact manifest hash does not match canonical descriptor binding")
    const finalEvent = event.event === "BLOCK_SEAL"
    if (finalEvent) {
      if (event.blockSealPriorSealHashes === null || event.blockSealPriorSealHashes.length !== priorSealHashes.length || event.blockSealPriorSealHashes.some((hash, position) => hash !== priorSealHashes[position])) {
        return fail("BLOCK_SEAL_INVALID", "block seal must bind every prior event seal hash in order")
      }
    } else if (event.blockSealPriorSealHashes !== null) {
      return fail("BLOCK_SEAL_INVALID", "only the terminal block seal may bind the prior seal-hash closure")
    }
    const seal = canonicalHash(sealProjection(blockId.right, event.ordinal, event.event, event.manifestSha256, event.previousManifestSha256, event.previousSealSha256, event.generationCallCount, event.blockSealPriorSealHashes))
    if (Either.isLeft(seal) || event.sealSha256 !== seal.right || !sha.test(event.sealSha256)) return fail("HASH_CHAIN_INVALID", "event seal hash does not match immutable canonical chain")
    previousManifestSha256 = event.manifestSha256
    previousSealSha256 = event.sealSha256
    priorSealHashes.push(event.sealSha256)
    totalCalls += event.generationCallCount
    validated.push(snapshotEvent(event))
  }
  if (totalCalls !== 9) return fail("CARDINALITY_INVALID", "one shared trajectory, four proposals, and four probes must total exactly nine calls")
  return Either.right(Object.freeze({ contractVersion: DNRD5_LIFECYCLE_CONTRACT_VERSION, schemaVersion: DNRD5_SCHEMA_VERSION, blockId: blockId.right, events: Object.freeze(validated) }))
}
