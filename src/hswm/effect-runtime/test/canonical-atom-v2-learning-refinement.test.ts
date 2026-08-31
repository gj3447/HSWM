import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import {
  HSWM_CANONICAL_LEARNING_REFINEMENT_LEAN_BOUNDARY,
  HSWM_CANONICAL_LEARNING_REFINEMENT_V1_CONTRACT_VERSION,
  canonicalAtomV2LearningRefinementProfile,
  canonicalAtomV2LearningRefinementProfileBytes,
  decodeCanonicalAtomV2LearningRefinementProfileBytes
} from "../src/canonical-atom-v2-learning-refinement.js"
import { canonicalJsonBytes } from "../src/canonical-atom-v2-json.js"

const unwrap = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw value.left
  return value.right
}

it("projects the exact checked-in v1 semantics without promoting learning", () => {
  const profile = canonicalAtomV2LearningRefinementProfile()

  expect(profile.contractVersion).toBe(
    HSWM_CANONICAL_LEARNING_REFINEMENT_V1_CONTRACT_VERSION
  )
  expect(profile.leanBoundary).toBe(
    HSWM_CANONICAL_LEARNING_REFINEMENT_LEAN_BOUNDARY
  )
  expect(profile.sourceSemantics).toEqual({
    permitCapability: "READ_ONLY_EVALUATION_NOT_COMMIT_CAPABILITY",
    permitAdmission: "NOT_ADMITTED_BY_THIS_RESOLUTION",
    permitLearning: "NOT_CAUSAL_CREDIT_NOT_LEARNING",
    outcomeStatus: "REPRESENTED_NOT_CAUSAL_CREDIT"
  })
  expect(profile.verdict).toBe("BLOCKED_NOT_REFINED_TO_LEAN_LEARN")
  expect(profile.scientificStatus).toBe("SCIENTIFIC_UNJUDGED")
  expect(profile.blockingObligations).toEqual([
    "TRUSTED_CURRENT_HEAD_NOT_ESTABLISHED",
    "EXACT_ONE_TARGET_CURRENT_REVISION_NOT_ESTABLISHED",
    "EVALUATOR_INDEPENDENCE_NOT_PROVEN",
    "OUTCOME_RESPONSIBILITY_OWNER_MISSING",
    "OUTCOME_SUPPORTS_REVISION_MISSING",
    "CANONICAL_PERMIT_MISSING",
    "SCHEMA_INVARIANT_WITNESS_MISSING",
    "ATOMIC_ADMISSION_MISSING"
  ])
})

it("keeps the profile and every nested collection immutable", () => {
  const profile = canonicalAtomV2LearningRefinementProfile()

  expect(Object.isFrozen(profile)).toBe(true)
  expect(Object.isFrozen(profile.sourceSemantics)).toBe(true)
  expect(Object.isFrozen(profile.mappedObligations)).toBe(true)
  expect(Object.isFrozen(profile.blockingObligations)).toBe(true)
})

it("round-trips only the exact canonical obstruction bytes", () => {
  const bytes = unwrap(canonicalAtomV2LearningRefinementProfileBytes())
  const decoded = unwrap(
    decodeCanonicalAtomV2LearningRefinementProfileBytes(bytes)
  )

  expect(decoded).toBe(canonicalAtomV2LearningRefinementProfile())

  const changed = {
    ...decoded,
    blockingObligations: [...decoded.blockingObligations].reverse()
  }
  const changedBytes = unwrap(canonicalJsonBytes(changed))
  const rejected = decodeCanonicalAtomV2LearningRefinementProfileBytes(
    changedBytes
  )
  expect(Either.isLeft(rejected)).toBe(true)
  if (Either.isLeft(rejected)) {
    expect(rejected.left.code).toBe("PROFILE_MISMATCH")
  }
})

it("rejects noncanonical JSON even when it describes the same profile", () => {
  const profile = canonicalAtomV2LearningRefinementProfile()
  const noncanonical = new TextEncoder().encode(JSON.stringify(profile))
  const rejected = decodeCanonicalAtomV2LearningRefinementProfileBytes(
    noncanonical
  )

  expect(Either.isLeft(rejected)).toBe(true)
  if (Either.isLeft(rejected)) {
    expect(rejected.left.code).toBe("PROFILE_MISMATCH")
  }
})
