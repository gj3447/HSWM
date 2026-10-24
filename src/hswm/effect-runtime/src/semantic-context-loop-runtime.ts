/** One native activation use, with automatic feedback and existing owner admission. */
import { Effect, Schema } from "effect"
import type { CanonicalAtomV2DurableRuntime } from "./canonical-atom-v2-durable-runtime.js"
import type { AdaptiveHttpClientShape } from "./adaptive-executor.js"
import { contextError, contextHash, type ContextPlan } from "./semantic-context-domain.js"
import { prepareSemanticContext } from "./semantic-context-runtime.js"
import { executeContextActivation, prepareActivationLearning, readActivationPolicy } from "./semantic-context-activation-runtime.js"
import type { ContextPresentation } from "./semantic-context-presentation-domain.js"

type Runtime = CanonicalAtomV2DurableRuntime["Type"]
export type ActivationExecution = Effect.Effect.Success<ReturnType<typeof executeContextActivation>>
export type ActivationProposal = Effect.Effect.Success<ReturnType<typeof prepareActivationLearning>>
export const ActivationAssessmentSchema = Schema.Struct({
  reward: Schema.NullOr(Schema.Number.pipe(Schema.finite(), Schema.between(0, 1))),
  observed: Schema.NonEmptyString.pipe(Schema.maxLength(8192)),
  source: Schema.NonEmptyString.pipe(Schema.maxLength(2048)),
  continue: Schema.Boolean
})
export type ActivationAssessment = typeof ActivationAssessmentSchema.Type
export interface ActivationLoopPorts<E, R> {
  readonly http: AdaptiveHttpClientShape
  /** External outcome contract; never the executing model's confidence. */
  readonly evaluate: (execution: ActivationExecution) => Effect.Effect<ActivationAssessment, E, R>
  readonly admit: (proposal: ActivationProposal) => Effect.Effect<unknown, E, R>
}

export const executeActivationLoop = <E, R>(runtime: Runtime, plan: ContextPlan, request: {
  readonly decision: unknown; readonly cell: unknown; readonly mode: "TRAIN" | "AUDIT"
  readonly target: unknown; readonly presentation?: ContextPresentation; readonly verification?: unknown
}, ports: ActivationLoopPorts<E, R>) => Effect.gen(function* () {
  const execution = yield* executeContextActivation(runtime, plan, request.decision, request.cell, ports.http,
    request.presentation ?? "execution_tail", request.verification)
  const assessment = yield* Schema.decodeUnknown(ActivationAssessmentSchema)(yield* ports.evaluate(execution), { onExcessProperty: "error" })
  if (request.mode === "AUDIT" || assessment.reward === null || execution.trace === null) {
    return { status: request.mode === "AUDIT" ? "AUDITED" as const : "NO_UPDATE" as const,
      execution, assessment, proposal: null, readback: null }
  }
  const proposal = yield* prepareActivationLearning(runtime, plan, {
    traceContent: execution.trace.traceContent, reward: assessment.reward,
    observed: assessment.observed, source: assessment.source
  }, request.target)
  // No automatic retry: a rejected/uncertain commit retains its staged execution and feedback.
  yield* ports.admit(proposal)
  const fresh = yield* prepareSemanticContext(runtime, plan.spec)
  const readback = yield* readActivationPolicy(runtime, fresh, proposal.policyKey)
  if (contextHash(readback.policy) !== contextHash(proposal.policy)) {
    return yield* Effect.fail(contextError("ACTIVATION_READBACK_MISMATCH", "Owner readback differs from the exact outcome-bound successor"))
  }
  return { status: "UPDATED" as const, execution, assessment, proposal, readback }
})
