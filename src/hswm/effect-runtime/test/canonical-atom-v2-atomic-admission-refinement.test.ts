import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import {
  HSWM_CANONICAL_ATOMIC_ADMISSION_LEAN_BOUNDARY,
  HSWM_CANONICAL_ATOMIC_ADMISSION_REFINEMENT_V1_CONTRACT_VERSION,
  canonicalAtomV2AtomicAdmissionRefinementProfile,
  canonicalAtomV2AtomicAdmissionRefinementProfileBytes,
  decodeCanonicalAtomV2AtomicAdmissionRefinementProfileBytes
} from "../src/canonical-atom-v2-atomic-admission-refinement.js"
import { canonicalJsonBytes } from "../src/canonical-atom-v2-json.js"

const unwrap = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw value.left
  return value.right
}

it("keeps the two present boundaries separate from atomic learning", () => {
  const profile = canonicalAtomV2AtomicAdmissionRefinementProfile()

  expect(profile.contractVersion).toBe(
    HSWM_CANONICAL_ATOMIC_ADMISSION_REFINEMENT_V1_CONTRACT_VERSION
  )
  expect(profile.leanBoundary).toBe(
    HSWM_CANONICAL_ATOMIC_ADMISSION_LEAN_BOUNDARY
  )
  expect(profile.presentBoundaries).toEqual([
    "OWNER_BOUND_OUTCOME_SHAPE_PRESENT",
    "DNRD5_TWO_CAS_HISTORY_BOUNDARY_PRESENT"
  ])
  expect(profile.verdict).toBe(
    "BLOCKED_NOT_REFINED_TO_LEAN_ATOMIC_ADMISSION"
  )
  expect(profile.scientificStatus).toBe("SCIENTIFIC_UNJUDGED")
})

it("preserves exact checked-in nonclaim literals and all five blockers", () => {
  const profile = canonicalAtomV2AtomicAdmissionRefinementProfile()

  expect(profile.sourceSemantics).toEqual({
    outcomeBundleStatus:
      "STRUCTURALLY_BOUND_NOT_TRUTH_NOT_CAUSAL_CREDIT_NOT_PERMIT_NOT_ADMISSION_NOT_LEARNING",
    genericPermitCapability: "READ_ONLY_EVALUATION_NOT_COMMIT_CAPABILITY",
    genericPermitAdmission: "NOT_ADMITTED_BY_THIS_RESOLUTION",
    dnrdTwoCasTerminal:
      "NOT_PROVIDER_CALL_NOT_OCCURRENCE_NOT_LEARNING_NOT_EFFICACY"
  })
  expect(profile.blockingObligations).toEqual([
    "OUTCOME_SUPPORT_WITNESS_NOT_ESTABLISHED",
    "CANONICAL_PERMIT_AT_LINEARIZATION_NOT_ESTABLISHED",
    "EXACT_TRANSITION_INVARIANT_WITNESS_NOT_ESTABLISHED",
    "SAME_TRANSITION_COMPOSITION_NOT_ESTABLISHED",
    "ATOMIC_ADMISSION_RUNTIME_MAPPING_NOT_ESTABLISHED"
  ])
})

it("freezes the profile and all nested collections", () => {
  const profile = canonicalAtomV2AtomicAdmissionRefinementProfile()

  expect(Object.isFrozen(profile)).toBe(true)
  expect(Object.isFrozen(profile.sourceSemantics)).toBe(true)
  expect(Object.isFrozen(profile.presentBoundaries)).toBe(true)
  expect(Object.isFrozen(profile.blockingObligations)).toBe(true)
})

it("round-trips only the exact canonical obstruction bytes", () => {
  const bytes = unwrap(
    canonicalAtomV2AtomicAdmissionRefinementProfileBytes()
  )
  const decoded = unwrap(
    decodeCanonicalAtomV2AtomicAdmissionRefinementProfileBytes(bytes)
  )
  expect(decoded).toBe(canonicalAtomV2AtomicAdmissionRefinementProfile())

  const promoted = {
    ...decoded,
    blockingObligations: decoded.blockingObligations.slice(1)
  }
  const promotedBytes = unwrap(canonicalJsonBytes(promoted))
  const rejected =
    decodeCanonicalAtomV2AtomicAdmissionRefinementProfileBytes(promotedBytes)
  expect(Either.isLeft(rejected)).toBe(true)
  if (Either.isLeft(rejected)) {
    expect(rejected.left.code).toBe("PROFILE_MISMATCH")
  }
})

it("rejects noncanonical JSON even when it carries the same values", () => {
  const noncanonical = new TextEncoder().encode(
    JSON.stringify(canonicalAtomV2AtomicAdmissionRefinementProfile())
  )
  const rejected =
    decodeCanonicalAtomV2AtomicAdmissionRefinementProfileBytes(noncanonical)

  expect(Either.isLeft(rejected)).toBe(true)
  if (Either.isLeft(rejected)) {
    expect(rejected.left.code).toBe("PROFILE_MISMATCH")
  }
})
