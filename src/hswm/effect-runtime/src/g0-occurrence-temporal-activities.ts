/**
 * Deterministic-shape validation activity for the authoritative G0 Temporal
 * workflow. The activity has no network, filesystem, credential, or evidence
 * authority. Its retry policy is fixed by the workflow at one attempt.
 */
import { Either } from "effect"

import {
  decodeG0OccurrenceTemporalTransitionWire,
  type G0OccurrenceTemporalTransitionIngress
} from "./g0-occurrence-temporal-wire.js"

export interface G0OccurrenceTransitionActivityResult {
  readonly accepted: boolean
  readonly transition: G0OccurrenceTemporalTransitionIngress | null
}

export const hswm_g0_occurrence_validate_transition = async (
  value: unknown
): Promise<G0OccurrenceTransitionActivityResult> => {
  const decoded = decodeG0OccurrenceTemporalTransitionWire(value)
  return Either.isLeft(decoded)
    ? Object.freeze({ accepted: false, transition: null })
    : Object.freeze({ accepted: true, transition: decoded.right })
}
