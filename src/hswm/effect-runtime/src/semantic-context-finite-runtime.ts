/** Read an admitted relation under an exact context plan before finite interpretation review. */
import { Effect } from "effect"
import type { CanonicalAtomV2DurableRuntime } from "./canonical-atom-v2-durable-runtime.js"
import { readLlmSemanticFrame } from "./canonical-atom-v2-llm-semantic-runtime.js"
import { contextByteLength, contextError, type ContextPlan } from "./semantic-context-domain.js"
import { checkSemanticContextPlan } from "./semantic-context-runtime.js"
import { reviewFiniteSemanticFrame, type FiniteReviewOptionsSchema } from "./semantic-context-finite-domain.js"

export const reviewPlannedFiniteSemantics = (
  runtime: CanonicalAtomV2DurableRuntime["Type"], plan: ContextPlan, relationUid: string,
  options: typeof FiniteReviewOptionsSchema.Type = {}
) => Effect.gen(function* () {
  yield* checkSemanticContextPlan(runtime, plan)
  if (!plan.bindings.some(b => b.key.atomUid === relationUid)) return yield* Effect.fail(contextError("REVIEW_OUTSIDE_PLAN", "Review target must be explicitly bound in this plan"))
  const frame = yield* readLlmSemanticFrame(runtime, relationUid, plan.spec.event)
  yield* checkSemanticContextPlan(runtime, plan)
  if (frame.stateRevision !== plan.stateRevision) return yield* Effect.fail(contextError("PLAN_STALE", "Review frame belongs to a different snapshot"))
  if (contextByteLength(frame) > plan.spec.maximumContextBytes) return yield* Effect.fail(contextError("CONTEXT_BUDGET_EXCEEDED", "Complete finite review frame exceeds the plan budget; no role truncation"))
  const review = yield* reviewFiniteSemanticFrame(frame, options)
  return { ...review, planSha256: plan.planSha256, sourceAuthority: "ADMITTED_STORE_READ_AT_PINNED_PLAN" as const }
})
