import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import {
  DNRD5_BLOCK_EVENT_SEQUENCE,
  DNRD5_LIFECYCLE_BOUNDARY,
  DNRD5_LIFECYCLE_CONTRACT_VERSION,
  makeDnrd5LifecycleEventSeal,
  validateDnrd5SealedBlockLifecycle,
  type Dnrd5BlockEvent,
  type Dnrd5LifecycleArtifact,
  type Dnrd5SealedBlockLifecycle
} from "../src/canonical-atom-v2-dnrd5-lifecycle.js"
import { DNRD5_ARM_LABELS, DNRD5_SCHEMA_VERSION, type Dnrd5ArmLabel } from "../src/canonical-atom-v2-dnrd5-schema.js"

const sha = (letter: string) => letter.repeat(64)
const arms = [...DNRD5_ARM_LABELS]
const requirements: Readonly<Record<Dnrd5BlockEvent, ReadonlyArray<string>>> = {
  STUDY_AND_TASK_COMMITMENTS: ["STUDY_RANDOMNESS", "BLOCK_SPEC", "EVALUATOR_COMMITMENT"],
  PROBE_AND_PLACEBO_COMMITMENTS: ["PROBE_COMMITMENT", "PLACEBO_COMMITMENT"],
  W0_AND_FOUR_FORKS: ["W0_SNAPSHOT", ...Array(4).fill("FORK_INCIDENCE")],
  ARM_ASSIGNMENT: Array(4).fill("ARM_ASSIGNMENT"),
  EPISODE_AND_TRAJECTORY_CONTRACT: ["EPISODE_ACTIVATION", "TRAJECTORY_CONTRACT"],
  TRAJECTORY_SEAL: ["TRAJECTORY_SEAL"],
  EVALUATOR_RELEASE_AND_HIDDEN_OUTCOME: ["EVALUATOR_RELEASE", "HIDDEN_OUTCOME"],
  ESCROW_PLACEBO_AND_FEEDBACK_ASSIGNMENTS: ["OUTCOME_CREDIT_ESCROW", "PLACEBO_RECEIPT", ...Array(4).fill("FEEDBACK_ASSIGNMENT")],
  FOUR_PROPOSALS: Array(4).fill("REVISION_PROPOSAL"),
  VALIDATION_CREDIT_TRANSITIONS_AND_RESTORE: [
    ...Array(4).fill("CANDIDATE_VALIDATION"),
    ...Array(4).fill("CREDIT_DECISION"),
    ...Array(4).fill("ARM_TRANSITION"),
    ...Array(3).fill("TRANSITION_RECEIPT"),
    "RESTORE_TRANSACTION"
  ],
  FOUR_BEHAVIOR_PROJECTIONS: Array(4).fill("BEHAVIOR_PROJECTION"),
  FOUR_PROBE_RESPONSE_SEALS: Array(4).fill("PROBE_RESPONSE_SEAL"),
  FOUR_BLIND_PROBE_OUTCOMES: Array(4).fill("PROBE_OUTCOME"),
  DELAYED_OUTCOME_AUDIT_RELEASE: ["DELAYED_AUDIT_RELEASE"],
  BLOCK_SEAL: ["BLOCK_SEAL"]
}
const calls: Readonly<Record<Dnrd5BlockEvent, number>> = {
  STUDY_AND_TASK_COMMITMENTS: 0, PROBE_AND_PLACEBO_COMMITMENTS: 0, W0_AND_FOUR_FORKS: 0, ARM_ASSIGNMENT: 0,
  EPISODE_AND_TRAJECTORY_CONTRACT: 0, TRAJECTORY_SEAL: 1, EVALUATOR_RELEASE_AND_HIDDEN_OUTCOME: 0,
  ESCROW_PLACEBO_AND_FEEDBACK_ASSIGNMENTS: 0, FOUR_PROPOSALS: 4, VALIDATION_CREDIT_TRANSITIONS_AND_RESTORE: 0, FOUR_BEHAVIOR_PROJECTIONS: 0,
  FOUR_PROBE_RESPONSE_SEALS: 4, FOUR_BLIND_PROBE_OUTCOMES: 0, DELAYED_OUTCOME_AUDIT_RELEASE: 0, BLOCK_SEAL: 0
}
const armKinds = new Set(["ARM_ASSIGNMENT", "FEEDBACK_ASSIGNMENT", "REVISION_PROPOSAL", "CANDIDATE_VALIDATION", "CREDIT_DECISION", "ARM_TRANSITION", "TRANSITION_RECEIPT", "RESTORE_TRANSACTION", "BEHAVIOR_PROJECTION", "PROBE_RESPONSE_SEAL", "PROBE_OUTCOME"])
const armsForKind: Readonly<Record<string, ReadonlyArray<Dnrd5ArmLabel>>> = {
  TRANSITION_RECEIPT: ["ACTIVE", "OUTCOME_INDEPENDENT_SHAM", "EXACT_W0_ROLLBACK"],
  RESTORE_TRANSACTION: ["EXACT_W0_ROLLBACK"]
}

const artifacts = (event: Dnrd5BlockEvent): ReadonlyArray<Dnrd5LifecycleArtifact> => {
  const armIndices = new Map<string, number>()
  return requirements[event].map((kind, index) => {
    const arm = armKinds.has(kind)
      ? (armsForKind[kind] ?? arms)[armIndices.get(kind) ?? 0]!
      : null
    if (arm !== null) armIndices.set(kind, (armIndices.get(kind) ?? 0) + 1)
    return {
      artifactId: `artifact:${event}:${index}`,
      kind: kind as Dnrd5LifecycleArtifact["kind"],
      arm,
      content: { mediaType: "application/json", byteLength: index, sha256: sha("a") }
    }
  })
}

const sealed = (): Dnrd5SealedBlockLifecycle => {
  const blockId = "DNRD5-BLOCK-0001"
  let previousManifestSha256: string | null = null
  let previousSealSha256: string | null = null
  const prior: string[] = []
  const events = DNRD5_BLOCK_EVENT_SEQUENCE.map((event, index) => {
    const made = makeDnrd5LifecycleEventSeal({
      blockId,
      ordinal: index + 1,
      event,
      artifacts: artifacts(event),
      generationCallCount: calls[event],
      previousManifestSha256,
      previousSealSha256,
      blockSealPriorSealHashes: event === "BLOCK_SEAL" ? [...prior] : null
    })
    if (Either.isLeft(made)) throw new Error(`${event}: ${made.left.detail}`)
    previousManifestSha256 = made.right.manifestSha256
    previousSealSha256 = made.right.sealSha256
    prior.push(made.right.sealSha256)
    return made.right
  })
  return { contractVersion: DNRD5_LIFECYCLE_CONTRACT_VERSION, schemaVersion: DNRD5_SCHEMA_VERSION, blockId, events }
}

it("validates the exact fifteen-event R2 chronology with four-arm cardinalities and nine calls", () => {
  const lifecycle = sealed()
  expect(Either.isRight(validateDnrd5SealedBlockLifecycle(lifecycle))).toBe(true)
  expect(lifecycle.events).toHaveLength(15)
  expect(lifecycle.events.at(-1)?.blockSealPriorSealHashes).toHaveLength(14)
  expect(DNRD5_LIFECYCLE_BOUNDARY.contentSemantics).toBe("CONTENT_DESCRIPTOR_BINDING_ONLY")
  expect(DNRD5_LIFECYCLE_BOUNDARY.scientificTerminal).toBe("NOT_ISSUED_BY_PURE_LIFECYCLE_VALIDATOR")
  expect(DNRD5_LIFECYCLE_BOUNDARY.armLabelManifest).toBe("EXPERIMENT_CUSTODIAN_PRIVATE_VIEW_NOT_MODEL_OR_EVALUATOR_PROJECTION")
})

it("fails closed for order, early probe, count, chain, duplicate, and alias attacks", () => {
  const lifecycle = sealed()
  const reordered = { ...lifecycle, events: [...lifecycle.events.slice(0, 2), lifecycle.events[3]!, lifecycle.events[2]!, ...lifecycle.events.slice(4)] }
  expect(Either.isLeft(validateDnrd5SealedBlockLifecycle(reordered))).toBe(true)
  const earlyProbe = { ...lifecycle, events: lifecycle.events.map((event, index) => index === 9 ? { ...event, event: "FOUR_PROBE_RESPONSE_SEALS" as Dnrd5BlockEvent } : event) }
  expect(Either.isLeft(validateDnrd5SealedBlockLifecycle(earlyProbe))).toBe(true)
  const missingFork = { ...lifecycle, events: lifecycle.events.map((event) => event.event === "W0_AND_FOUR_FORKS" ? { ...event, artifacts: event.artifacts.slice(0, -1) } : event) }
  expect(Either.isLeft(validateDnrd5SealedBlockLifecycle(missingFork))).toBe(true)
  const brokenChain = { ...lifecycle, events: lifecycle.events.map((event, index) => index === 5 ? { ...event, previousSealSha256: sha("f") } : event) }
  expect(Either.isLeft(validateDnrd5SealedBlockLifecycle(brokenChain))).toBe(true)
  const duplicateArtifact = { ...lifecycle, events: lifecycle.events.map((event) => event.event === "FOUR_PROPOSALS" ? { ...event, artifacts: event.artifacts.map((artifact, index) => index === 1 ? { ...artifact, artifactId: event.artifacts[0]!.artifactId } : artifact) } : event) }
  expect(Either.isLeft(validateDnrd5SealedBlockLifecycle(duplicateArtifact))).toBe(true)
  const alias = { ...lifecycle, events: lifecycle.events.map((event, index) => index === 0 ? { ...event, event: "W0_ALIAS" as unknown as Dnrd5BlockEvent } : event) }
  expect(Either.isLeft(validateDnrd5SealedBlockLifecycle(alias))).toBe(true)
})

it("requires the exact arm-specific validation, credit, receipt, and restore closure", () => {
  const lifecycle = sealed()
  const mutateTransition = (
    mutate: (artifacts: ReadonlyArray<Dnrd5LifecycleArtifact>) => ReadonlyArray<Dnrd5LifecycleArtifact>
  ) => ({
    ...lifecycle,
    events: lifecycle.events.map((event) => event.event === "VALIDATION_CREDIT_TRANSITIONS_AND_RESTORE"
      ? { ...event, artifacts: mutate(event.artifacts) }
      : event)
  })
  for (const kind of ["CANDIDATE_VALIDATION", "CREDIT_DECISION", "TRANSITION_RECEIPT", "RESTORE_TRANSACTION"]) {
    expect(Either.isLeft(validateDnrd5SealedBlockLifecycle(mutateTransition((items) => {
      const index = items.findIndex((item) => item.kind === kind)
      return items.filter((_item, itemIndex) => itemIndex !== index)
    })))).toBe(true)
  }
  const wrongRestoreArm = mutateTransition((items) => items.map((item) => item.kind === "RESTORE_TRANSACTION" ? { ...item, arm: "ACTIVE" } : item))
  expect(Either.isLeft(validateDnrd5SealedBlockLifecycle(wrongRestoreArm))).toBe(true)
  const delayedReceipt = mutateTransition((items) => items.map((item) => item.kind === "TRANSITION_RECEIPT" && item.arm === "EXACT_W0_ROLLBACK" ? { ...item, arm: "DELAYED_NO_CREDIT" } : item))
  expect(Either.isLeft(validateDnrd5SealedBlockLifecycle(delayedReceipt))).toBe(true)
  const duplicateValidationArm = mutateTransition((items) => {
    const first = items.find((item) => item.kind === "CANDIDATE_VALIDATION")!
    let changed = false
    return items.map((item) => item.kind === "CANDIDATE_VALIDATION" && item.arm !== "ACTIVE" && !changed
      ? (changed = true, { ...item, arm: first.arm })
      : item)
  })
  expect(Either.isLeft(validateDnrd5SealedBlockLifecycle(duplicateValidationArm))).toBe(true)
  const incorrectReceiptSet = mutateTransition((items) => items.map((item) => item.kind === "TRANSITION_RECEIPT" && item.arm === "OUTCOME_INDEPENDENT_SHAM" ? { ...item, arm: "DELAYED_NO_CREDIT" } : item))
  expect(Either.isLeft(validateDnrd5SealedBlockLifecycle(incorrectReceiptSet))).toBe(true)
  expect(Either.isRight(validateDnrd5SealedBlockLifecycle(lifecycle))).toBe(true)
})

it("rejects extra keys and global artifact-ID reuse, then returns a deep immutable snapshot", () => {
  const lifecycle = sealed()
  expect(Either.isLeft(validateDnrd5SealedBlockLifecycle({ ...lifecycle, extra: true }))).toBe(true)
  expect(Either.isLeft(validateDnrd5SealedBlockLifecycle({
    ...lifecycle,
    events: lifecycle.events.map((event, index) => index === 0 ? { ...event, extra: true } : event)
  }))).toBe(true)
  expect(Either.isLeft(validateDnrd5SealedBlockLifecycle({
    ...lifecycle,
    events: lifecycle.events.map((event, index) => index === 0 ? {
      ...event,
      artifacts: event.artifacts.map((artifact, artifactIndex) => artifactIndex === 0 ? { ...artifact, extra: true } : artifact)
    } : event)
  }))).toBe(true)
  expect(Either.isLeft(validateDnrd5SealedBlockLifecycle({
    ...lifecycle,
    events: lifecycle.events.map((event, index) => index === 1 ? {
      ...event,
      artifacts: event.artifacts.map((artifact, artifactIndex) => artifactIndex === 0 ? { ...artifact, artifactId: lifecycle.events[0]!.artifacts[0]!.artifactId } : artifact)
    } : event)
  }))).toBe(true)

  const mutable = JSON.parse(JSON.stringify(lifecycle)) as {
    events: Array<{ artifacts: Array<{ content: { sha256: string } }> }>
  }
  const validated = validateDnrd5SealedBlockLifecycle(mutable)
  expect(Either.isRight(validated)).toBe(true)
  if (Either.isLeft(validated)) return
  const outputSha = validated.right.events[0]!.artifacts[0]!.content.sha256
  mutable.events[0]!.artifacts[0]!.content.sha256 = sha("f")
  expect(validated.right.events[0]!.artifacts[0]!.content.sha256).toBe(outputSha)
  expect(Object.isFrozen(validated.right.events[0]!.artifacts[0]!.content)).toBe(true)
})
