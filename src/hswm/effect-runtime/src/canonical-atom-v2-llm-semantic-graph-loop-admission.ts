import { Effect } from "effect"

import type { CanonicalAtomV2ContentDescriptor } from "./canonical-atom-v2-content.js"
import {
  GraphLoopEngineeringController,
  type GraphDeltaEvidence,
  type GraphDeltaResult,
  type GraphLoopContract,
  type GraphLoopControlJournalEntry,
  type GraphLoopControlError,
  type GraphLoopControlJournalError
} from "./canonical-atom-v2-graph-loop-engineering.js"
import type {
  LlmSemanticRevisionAdmission,
  LlmSemanticRevisionProposal
} from "./canonical-atom-v2-llm-semantic-runtime.js"

type Decision = "ACCEPT" | "RETRY" | "REJECT"
type Descriptor = CanonicalAtomV2ContentDescriptor
const descriptor = (value: Descriptor): Descriptor => Object.freeze({ mediaType: value.mediaType, byteLength: value.byteLength, sha256: value.sha256 })

/** Caller-owned graph-loop material. No semantic record is promoted to verifier evidence here. */
export interface LlmSemanticGraphLoopAdmissionInput {
  readonly contract: GraphLoopContract
  readonly transactionId: string
  readonly action: Descriptor
  readonly verification: Readonly<{ readonly decision: Decision; readonly outcome: Descriptor }>
  readonly evidence: GraphDeltaEvidence
}

export type LlmSemanticGraphLoopAdmissionResult =
  | GraphDeltaResult
  | Readonly<{ readonly disposition: "RETRY_SCHEDULED"; readonly control: GraphLoopControlJournalEntry }>
  | Readonly<{ readonly disposition: "ESCALATED"; readonly control: GraphLoopControlJournalEntry }>

const snapshot = (input: LlmSemanticGraphLoopAdmissionInput) => Object.freeze({
  contract: Object.freeze({ ...input.contract }),
  transactionId: input.transactionId,
  action: descriptor(input.action),
  verification: Object.freeze({ decision: input.verification.decision, outcome: descriptor(input.verification.outcome) }),
  evidence: Object.freeze({
    sealedTrajectory: descriptor(input.evidence.sealedTrajectory), outcome: descriptor(input.evidence.outcome),
    credit: descriptor(input.evidence.credit), authorization: descriptor(input.evidence.authorization), invariant: descriptor(input.evidence.invariant),
    authorizationStatus: input.evidence.authorizationStatus, conflictPolicy: input.evidence.conflictPolicy
  })
})

/** ACCEPT alone reaches submitDelta; RETRY is scheduled and REJECT is stopped without durable mutation. */
export const makeLlmSemanticGraphLoopAdmission = (
  controller: GraphLoopEngineeringController["Type"], input: LlmSemanticGraphLoopAdmissionInput
): LlmSemanticRevisionAdmission<never, GraphLoopControlError | GraphLoopControlJournalError, LlmSemanticGraphLoopAdmissionResult> => {
  const frozen = snapshot(input)
  return Object.freeze({
    admit: (proposal: LlmSemanticRevisionProposal) => Effect.gen(function* () {
      yield* controller.trigger(frozen.contract)
      yield* controller.sealAction(frozen.contract.runId, frozen.action)
      yield* controller.recordVerification(frozen.contract.runId, frozen.verification.decision, frozen.verification.outcome)
      if (frozen.verification.decision === "RETRY") {
        const state = (yield* controller.recover).get(frozen.contract.runId)
        if (state === undefined) return yield* Effect.die("triggered graph-loop run disappeared before retry policy")
        if (state.attempt >= state.contract.maximumAttempts || state.actionCount >= state.contract.maximumActions) {
          const control = yield* controller.escalate(frozen.contract.runId, "RETRY_BUDGET_EXHAUSTED")
          return Object.freeze({ disposition: "ESCALATED" as const, control })
        }
        const control = yield* controller.scheduleRetry(frozen.contract.runId, "VERIFIER_RETRY")
        return Object.freeze({ disposition: "RETRY_SCHEDULED" as const, control })
      }
      if (frozen.verification.decision === "REJECT") {
        yield* controller.stop(frozen.contract.runId, "VERIFIER_REJECTED")
        return Object.freeze({ disposition: "REJECTED" as const, evolution: null })
      }
      const result = yield* controller.submitDelta({ runId: frozen.contract.runId, transactionId: frozen.transactionId, affectedKeys: proposal.affectedKeys, evidence: frozen.evidence, candidate: proposal.candidate })
      return result
    })
  })
}
