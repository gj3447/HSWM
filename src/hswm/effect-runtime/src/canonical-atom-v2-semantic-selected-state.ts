/** Finite selection over existing CanonicalAtomV2 durable branches. */
import { createHash } from "node:crypto"
import { Data, Effect } from "effect"

import { canonicalAtomV2KeyId, HSWM_SUPERSEDES_REFERENCE_ROLE, HSWM_SUPERSEDES_REFERENCE_TYPE, type CanonicalAtomV2Key } from "./canonical-atom-v2-schema.js"
import { CanonicalAtomV2DurableRuntime } from "./canonical-atom-v2-durable-runtime.js"
import { canonicalAtomV2StateSha256 } from "./canonical-atom-v2-state-journal.js"
import { readLlmSemanticFrame } from "./canonical-atom-v2-llm-semantic-runtime.js"
import { selectSemanticLearningCandidate, type SemanticLearningSelectionRequest, type SemanticLearningSelectionResult } from "./semantic-learning-selection-domain.js"

export const HSWM_SEMANTIC_SELECTED_STATE_V1 = "hswm-canonical-atom-v2-semantic-selected-state/v1" as const
const claimCeiling = "FINITE_DECLARED_GUARD_EXISTING_LOCAL_DURABLE_BRANCH_NOT_CALIBRATED_STATISTICS_CANONICAL_PERMIT_REAL_LLM_OR_HSWM_EFFICACY" as const

export class SemanticSelectedStateError extends Data.TaggedError("SemanticSelectedStateError")<{
  readonly code: "BRANCH_INVALID" | "CANDIDATE_INVALID" | "SELECTED_STATE_CHANGED"
  readonly detail: string
}> {}
const fail = (code: SemanticSelectedStateError["code"], detail: string) => new SemanticSelectedStateError({ code, detail })

export interface SemanticDurableBranch {
  readonly root: string
  readonly relationUid: string
  readonly runtime: CanonicalAtomV2DurableRuntime["Type"]
}
export interface DerivedSemanticBranch {
  readonly root: string
  readonly relationUid: string
  readonly schemaContentSha256: string
  readonly stateSha256: string
  readonly relationKey: CanonicalAtomV2Key
  readonly owner: string
  readonly roles: ReadonlyArray<Readonly<{ referenceType: string; role: string; key: string; owner: string; contentSha256: string }>>
  readonly predecessorKey: string | null
  readonly traceSha256: string | null
  readonly outcomeSha256: string | null
}
export interface FrozenSemanticCandidateRound {
  readonly baseline: SemanticDurableBranch
  readonly candidate: SemanticDurableBranch
  /** Supplied evaluation rows are declared evidence, not authenticated model measurements. */
  readonly selection: SemanticLearningSelectionRequest
  readonly selectionSetId: string
  readonly expectedTraining: Readonly<{ traceSha256: string; outcomeSha256: string }>
  readonly assumptions: "CALLER_DECLARED_FINITE_CONTAMINATION_ALLOWANCE_AND_COST"
}
export interface SelectedSemanticBranch {
  readonly contract: typeof HSWM_SEMANTIC_SELECTED_STATE_V1
  readonly selected: "BASELINE" | "CANDIDATE"
  readonly selectionSetId: string
  readonly selectionInputSha256: string
  readonly baselineBranch: DerivedSemanticBranch
  readonly candidateBranch: DerivedSemanticBranch
  readonly selectedBranch: DerivedSemanticBranch
  readonly guard: SemanticLearningSelectionResult
  readonly claimCeiling: typeof claimCeiling
}

// Copy value inputs before the first asynchronous read. Services remain caller-supplied capabilities.
const captureRound = (round: FrozenSemanticCandidateRound): FrozenSemanticCandidateRound => Object.freeze({
  baseline: Object.freeze({ ...round.baseline }),
  candidate: Object.freeze({ ...round.candidate }),
  selectionSetId: round.selectionSetId,
  assumptions: round.assumptions,
  expectedTraining: Object.freeze({ ...round.expectedTraining }),
  selection: Object.freeze({
    observations: Object.freeze(round.selection.observations.map(row => Object.freeze({ ...row }))),
    currentPredictions: Object.freeze({ ...round.selection.currentPredictions }),
    candidatePredictions: Object.freeze({ ...round.selection.candidatePredictions }),
    allowance: round.selection.allowance,
    debit: round.selection.debit
  })
})
const selectionDigest = (round: FrozenSemanticCandidateRound): string => createHash("sha256").update(JSON.stringify([
  round.selectionSetId, round.assumptions,
  round.expectedTraining.traceSha256, round.expectedTraining.outcomeSha256,
  round.selection.observations.map(row => [row.inputKey, row.label, row.mass.toString()]),
  Object.keys(round.selection.currentPredictions).sort().map(key => [key, round.selection.currentPredictions[key]]),
  Object.keys(round.selection.candidatePredictions).sort().map(key => [key, round.selection.candidatePredictions[key]]),
  round.selection.allowance.toString(), round.selection.debit.toString()
])).digest("hex")

const captureBinding = (branch: DerivedSemanticBranch): DerivedSemanticBranch => Object.freeze({
  ...branch,
  relationKey: Object.freeze({ ...branch.relationKey }),
  roles: Object.freeze(branch.roles.map(role => Object.freeze({ ...role })))
})
const bindingValue = (branch: DerivedSemanticBranch): string => JSON.stringify([
  branch.root, branch.relationUid, branch.schemaContentSha256, branch.stateSha256, canonicalAtomV2KeyId(branch.relationKey), branch.owner,
  branch.roles.map(role => [role.referenceType, role.role, role.key, role.owner, role.contentSha256]),
  branch.predecessorKey, branch.traceSha256, branch.outcomeSha256
])
const guardValue = (guard: SemanticLearningSelectionResult): string => JSON.stringify([
  guard.schemaVersion, guard.selection, guard.reason, guard.observationCount,
  guard.totalMass.toString(), guard.currentObservedScore.toString(), guard.candidateObservedScore.toString(),
  guard.requiredCandidateObservedScore.toString(), guard.allowance.toString(), guard.debit.toString(),
  guard.observedGuardPasses, guard.claimCeiling
])

/** Derives protected fields from parsed durable state and its actual semantic frame. */
export const deriveSemanticDurableBranch = (input: SemanticDurableBranch, event = "semantic-selection:derive") => Effect.gen(function* () {
  const branch = Object.freeze({ ...input })
  if (!branch.root || !branch.relationUid) return yield* Effect.fail(fail("BRANCH_INVALID", "branch root and relation UID are required"))
  const snapshot = yield* branch.runtime.snapshot
  const frame = yield* readLlmSemanticFrame(branch.runtime, branch.relationUid, event)
  const after = yield* branch.runtime.snapshot
  const stateDigest = yield* canonicalAtomV2StateSha256(snapshot.canonical)
  const afterDigest = yield* canonicalAtomV2StateSha256(after.canonical)
  if (snapshot.canonical.revision !== frame.stateRevision || stateDigest !== afterDigest || snapshot.schema.content.sha256 !== after.schema.content.sha256) {
    return yield* Effect.fail(fail("BRANCH_INVALID", "durable snapshot and semantic frame changed during the read"))
  }
  const atom = snapshot.canonical.atoms.find(item => canonicalAtomV2KeyId(item.key) === canonicalAtomV2KeyId(frame.relation.key))
  if (atom === undefined || atom.responsibilityOwner !== frame.relation.owner) {
    return yield* Effect.fail(fail("BRANCH_INVALID", "semantic frame does not resolve to its durable relation atom"))
  }
  const predecessors = atom.references.filter(reference => reference.referenceType === HSWM_SUPERSEDES_REFERENCE_TYPE)
  if (predecessors.length > 1 || predecessors.some(reference => reference.role !== HSWM_SUPERSEDES_REFERENCE_ROLE)) {
    return yield* Effect.fail(fail("BRANCH_INVALID", "semantic successor must have one correctly typed predecessor"))
  }
  const predecessor = predecessors[0]
  return captureBinding({
    root: branch.root, relationUid: branch.relationUid, schemaContentSha256: snapshot.schema.content.sha256, stateSha256: stateDigest,
    relationKey: frame.relation.key, owner: frame.relation.owner,
    roles: frame.roles.map(role => ({ referenceType: role.referenceType, role: role.role, key: canonicalAtomV2KeyId(role.key), owner: role.owner, contentSha256: role.contentSha256 })),
    predecessorKey: predecessor === undefined ? null : canonicalAtomV2KeyId(predecessor.target),
    traceSha256: frame.relation.semantic.trace?.sha256 ?? null,
    outcomeSha256: frame.relation.semantic.outcome?.sha256 ?? null
  })
})

const selectCapturedRound = (round: FrozenSemanticCandidateRound) => Effect.gen(function* () {
  if (!round.selectionSetId || round.assumptions !== "CALLER_DECLARED_FINITE_CONTAMINATION_ALLOWANCE_AND_COST" ||
    !/^[0-9a-f]{64}$/.test(round.expectedTraining.traceSha256) || !/^[0-9a-f]{64}$/.test(round.expectedTraining.outcomeSha256)) {
    return yield* Effect.fail(fail("BRANCH_INVALID", "selection set, training digests and finite-bound assumption are required"))
  }
  const guard = yield* selectSemanticLearningCandidate(round.selection)
  const inputDigest = selectionDigest(round)
  const baseline = yield* deriveSemanticDurableBranch(round.baseline)
  const candidate = yield* deriveSemanticDurableBranch(round.candidate)
  if (baseline.relationUid !== candidate.relationUid || candidate.schemaContentSha256 !== baseline.schemaContentSha256 || candidate.relationKey.schemaVersion !== baseline.relationKey.schemaVersion ||
    candidate.relationKey.lineageId !== baseline.relationKey.lineageId || candidate.predecessorKey !== canonicalAtomV2KeyId(baseline.relationKey) ||
    candidate.owner !== baseline.owner || JSON.stringify(candidate.roles) !== JSON.stringify(baseline.roles) ||
    candidate.traceSha256 !== round.expectedTraining.traceSha256 || candidate.outcomeSha256 !== round.expectedTraining.outcomeSha256) {
    return yield* Effect.fail(fail("CANDIDATE_INVALID", "candidate must preserve exact graph bindings and expected stored training receipt"))
  }
  const selected = guard.selection === "CANDIDATE" ? "CANDIDATE" : "BASELINE"
  return Object.freeze({
    contract: HSWM_SEMANTIC_SELECTED_STATE_V1, selected, selectionSetId: round.selectionSetId,
    selectionInputSha256: inputDigest, baselineBranch: baseline, candidateBranch: candidate,
    selectedBranch: selected === "CANDIDATE" ? candidate : baseline, guard, claimCeiling
  } satisfies SelectedSemanticBranch)
})

export const selectFrozenSemanticDurableCandidate = (round: FrozenSemanticCandidateRound) =>
  Effect.suspend(() => selectCapturedRound(captureRound(round)))

/**
 * Recompute the declared round, reopen its selected branch and call the next operation.
 * The record is not a Permit or authentication token. Callers must keep both roots
 * quiescent across this operation and the next execution; no cross-root lock is added.
 */
export const reopenSelectedSemanticBranch = <R, E, A>(
  round: FrozenSemanticCandidateRound,
  selected: SelectedSemanticBranch,
  open: (root: string) => Effect.Effect<CanonicalAtomV2DurableRuntime["Type"], E, R>,
  next: (runtime: CanonicalAtomV2DurableRuntime["Type"], relationUid: string) => Effect.Effect<A, E, R>
) => Effect.gen(function* () {
  const input = captureRound(round)
  const decision = Object.freeze({
    ...selected, guard: Object.freeze({ ...selected.guard }),
    baselineBranch: captureBinding(selected.baselineBranch), candidateBranch: captureBinding(selected.candidateBranch),
    selectedBranch: captureBinding(selected.selectedBranch)
  })
  const recomputed = yield* selectCapturedRound(input)
  if (decision.contract !== recomputed.contract || decision.claimCeiling !== recomputed.claimCeiling ||
    decision.selected !== recomputed.selected || decision.selectionSetId !== recomputed.selectionSetId ||
    decision.selectionInputSha256 !== recomputed.selectionInputSha256 || guardValue(decision.guard) !== guardValue(recomputed.guard) ||
    bindingValue(decision.baselineBranch) !== bindingValue(recomputed.baselineBranch) ||
    bindingValue(decision.candidateBranch) !== bindingValue(recomputed.candidateBranch) ||
    bindingValue(decision.selectedBranch) !== bindingValue(recomputed.selectedBranch)) {
    return yield* Effect.fail(fail("SELECTED_STATE_CHANGED", "selection record differs from the original round and current branch bindings"))
  }
  const branch = recomputed.selectedBranch
  const runtime = yield* open(branch.root)
  const rebound = yield* deriveSemanticDurableBranch({ root: branch.root, relationUid: branch.relationUid, runtime }, "semantic-selection:fresh-reopen")
  if (bindingValue(rebound) !== bindingValue(branch)) {
    return yield* Effect.fail(fail("SELECTED_STATE_CHANGED", "fresh durable reopen no longer matches selected branch"))
  }
  return yield* next(runtime, branch.relationUid)
})
