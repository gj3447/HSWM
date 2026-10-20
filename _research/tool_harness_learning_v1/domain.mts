/** Fixed, bounded owner task: native context-policy learning from actual CLI output. */
export const focuses = ["navigation", "structure", "sources"] as const
export type Focus = typeof focuses[number]
export const commands = ["show", "validate", "bindings"] as const
export type Command = typeof commands[number]
export interface Task { readonly id: string; readonly focus: Focus; readonly bundle: string }
export const config = { encoderRevision: "declared-workspace-intent-onehot/v1", featureNames: focuses, alpha: 1 }
export const tasks = (phase: string, bundles: readonly string[], repeats = 1): readonly Task[] =>
  Array.from({ length: repeats }, (_, repeat) => focuses.flatMap(focus =>
    bundles.map(bundle => ({ id: `${phase}-${repeat}-${focus}-${bundle}`, focus, bundle })))).flat()
export const protocol = {
  contract: "hswm-tool-harness-learning/v1",
  scope: "Native context-policy adaptation for three declared workspace intents; no semantic-text or model-weight training",
  train: tasks("train", ["tool-harness", "identity"], 3),
  holdout: tasks("holdout", ["semantic-w-plan", "jev-context"]),
  conditions: ["baseline", "learned", "observations-only", "removed", "restored"],
  maximumProviderCalls: 64, expectedProviderCalls: 51, wallLimitMs: 1_800_000, perCallTimeoutMs: 30_000,
  maximumCommandMs: 30_000, maximumOutputBytes: 1_048_576, concurrency: 1,
  criteria: {
    developmentCommandViolations: 0, learnedCorrect: 6, gainOverBaseline: "STRICTLY_POSITIVE",
    gainOverObservationsOnly: "STRICTLY_POSITIVE", removedEqualsBaseline: true, restoredEqualsLearned: true,
    freshProcessUsesExactPolicy: true, duplicateFeedbackRejected: true, nonPolicyAtomsPreserved: true
  },
  units: "Six fixed intent-by-heldout-bundle cases; correlated authored tasks, not six independent population samples",
  selection: "Existing disjoint LinUCB, declared intent features, deterministic exploration; never IPS or a learned intent encoder",
  reward: "Required information is present in completed typed CLI JSON, including a negative conformance report; never award from chosen command name",
  failures: "Preserve every attempt; no provider retry, cohort resume, threshold change or holdout-based training",
  effect: "Persisted native semantic_context_policy A/b statistics; LLM executes the selected graph-resident usage rule",
  comparison: "Identical source, model and inference settings; fresh processes for all post-training conditions",
  cost: "All development, training, checks, controls and restarts count; provider tokens are unknown if any response omits usage"
} as const
export const record = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v)
export const features = (task: Task): readonly number[] => focuses.map(focus => Number(task.focus === focus))

/** This is a declared information-retrieval contract, not semantic usefulness judgment. */
export const evaluate = (task: Task, exitCode: number | null, output: unknown): boolean => {
  if (!record(output) || output["schema_version"] !== "hswm-workspace-observation/v1") return false
  if (exitCode !== 0 && !(task.focus === "structure" && exitCode === 1 && output["conforms"] === false)) return false
  if (task.focus === "navigation") {
    const entry = output["entry"]
    return record(entry) && entry["id"] === task.bundle && typeof entry["document"] === "string" &&
      Array.isArray(entry["queries"]) && Array.isArray(entry["shapes"])
  }
  if (output["id"] !== task.bundle) return false
  if (task.focus === "structure") return typeof output["conforms"] === "boolean" &&
    Array.isArray(output["structuralIssues"]) && Array.isArray(output["shapes"]) && output["shapes"].length > 0
  return Array.isArray(output["rows"]) && output["rows"].length > 0 && output["rows"].every(row =>
    record(row) && typeof row["path"] === "string" && typeof row["sha256"] === "string" && typeof row["status"] === "string")
}
export const parseCommand = (prediction: string, task: Task): readonly [Command, string] | null => {
  // No shell, paths, flags, chained commands or invented workspace IDs.
  const match = /^(show|validate|bindings) ([a-z0-9-]+)$/.exec(prediction)
  return match && match[0] === prediction && match[2] === task.bundle ? [match[1] as Command, task.bundle] : null
}
export interface Row {
  readonly phase: string; readonly task: Task; readonly candidate: string | null; readonly prediction: string
  readonly correct: boolean; readonly policyRevision: number; readonly traceSha256: string
  readonly outputSha256: string | null; readonly executionId: string
}
export const assess = (rows: readonly Row[]) => {
  const phases = protocol.conditions.map(phase => {
    const selected = rows.filter(row => row.phase === phase)
    return { phase, complete: selected.length === protocol.holdout.length &&
      new Set(selected.map(r => r.task.id)).size === protocol.holdout.length &&
      selected.every(row => protocol.holdout.some(task => task.id === row.task.id && task.bundle === row.task.bundle && task.focus === row.task.focus)),
    correct: selected.filter(row => row.correct).length }
  })
  const score = (phase: string) => phases.find(p => p.phase === phase)?.correct ?? -1
  const paired = (a: string, b: string) => protocol.holdout.every(task => {
    const left = rows.find(row => row.phase === a && row.task.id === task.id)
    const right = rows.find(row => row.phase === b && row.task.id === task.id)
    return left !== undefined && right !== undefined && left.correct === right.correct && left.prediction === right.prediction
  })
  const accepted = phases.every(p => p.complete) && score("learned") === 6 &&
    score("learned") > score("baseline") && score("learned") > score("observations-only") &&
    paired("removed", "baseline") && paired("restored", "learned")
  return { accepted, phases, claim: accepted ? "BOUNDED_NATIVE_ACTIVATION_LEARNING_EFFECT_OBSERVED" : "CRITERIA_NOT_MET" }
}
