/** Pure composition of already projected artifacts. Lean, not this assembler,
 * checks each round's semantics. No admission, model call, or filesystem I/O. */
import { Data, Either, type Effect } from "effect"
import { canonicalJson } from "./adaptive-domain.js"
import type { projectSemanticLifecycleRefinement } from "./semantic-lifecycle-refinement.js"

export type SemanticLifecycleWire = Effect.Effect.Success<ReturnType<typeof projectSemanticLifecycleRefinement>>
export class SemanticLifecycleChainError extends Data.TaggedError("SemanticLifecycleChainError")<{
  readonly code: "EMPTY_OR_OVERSIZED_CHAIN" | "DISCONNECTED_STATE" | "INVALID_DATA"
  readonly roundIndex: number
}> {}

/** Copies all data so later caller mutation cannot change the chain. The bridge
 * concerns the relation view and state revision; full-store equality is not implied. */
export const assembleSemanticLifecycleChain = (supplied: readonly SemanticLifecycleWire[]) => Either.gen(function* () {
  if (supplied.length === 0 || supplied.length > 1000) return yield* Either.left(new SemanticLifecycleChainError({ code: "EMPTY_OR_OVERSIZED_CHAIN", roundIndex: 0 }))
  const rounds = yield* Either.try({ try: () => structuredClone(supplied), catch: () => new SemanticLifecycleChainError({ code: "INVALID_DATA", roundIndex: 0 }) })
  for (const [index, wire] of rounds.entries()) {
    const prior = rounds[index - 1]
    const expected = prior === undefined ? wire.before : prior.selectedCandidate ? prior.after : prior.before
    const left = canonicalJson(expected), right = canonicalJson(wire.before)
    if (Either.isLeft(left) || Either.isLeft(right)) return yield* Either.left(new SemanticLifecycleChainError({ code: "INVALID_DATA", roundIndex: index }))
    if (left.right !== right.right) return yield* Either.left(new SemanticLifecycleChainError({ code: "DISCONNECTED_STATE", roundIndex: index }))
  }
  const freeze = <T>(value: T): T => {
    if (value !== null && typeof value === "object") {
      Object.values(value).forEach(freeze)
      Object.freeze(value)
    }
    return value
  }
  return freeze({ contract: "hswm-semantic-lifecycle-chain/v1" as const, rounds })
})
