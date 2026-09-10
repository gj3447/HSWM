/** Read-only structural check of the existing authored calibration, without LLM calls. */
import { createHash } from "node:crypto"
import { createRequire } from "node:module"
import { readFileSync } from "node:fs"
import { catalogTask } from "../relation_synthesis_usl_v1/fixtures.mts"
import { CALIBRATION_PUBLIC_PRIMITIVES, evaluateIndependentProgram,
  type CalibrationProgram } from "../../../src/hswm/effect-runtime/src/research-relation-comparison.ts"

const { Either } = createRequire(new URL("../../../src/hswm/effect-runtime/package.json", import.meta.url))("effect") as typeof import("effect")
const root = new URL("../../../", import.meta.url)
const digest = (bytes: Uint8Array) => createHash("sha256").update(bytes).digest("hex")
const protocolPath = "_research/causal_composition/relation_llm_comparison_v1/protocol.v1.json"
const protocol = JSON.parse(readFileSync(new URL(protocolPath, root), "utf8")) as {
  training: { seeds: number[]; affected_artifacts: number; role_arity: number }
  calibration: { seeds: number[]; affected_artifacts: number; role_arity: number }
}

// Authored from the public schema and source BEFORE executing any row. This is
// a hand-written structural witness, not a learned program or a model output.
const program = CALIBRATION_PUBLIC_PRIMITIVES.reduce<CalibrationProgram>((input, primitive) =>
  ({ tag: "Traverse", input, ...primitive }), { tag: "Here" })
const rows = (["training", "calibration"] as const).flatMap((split) => {
  const spec = protocol[split]
  return spec.seeds.map((seed) => {
    const task = catalogTask(seed, spec.affected_artifacts, spec.role_arity)
    const predicted = evaluateIndependentProgram(task.graph, task.focus, program)
    if (Either.isLeft(predicted)) throw predicted.left
    const expected = [...task.expected].sort()
    const actual = [...predicted.right.uids].sort()
    return { split, seed, taskId: task.id, expected, actual,
      exact: JSON.stringify(expected) === JSON.stringify(actual), nodeSteps: predicted.right.nodeSteps }
  })
})
const paths = [
  "_research/causal_composition/relation_calibration_structure_v1/run.mts", protocolPath,
  "_research/causal_composition/relation_synthesis_usl_v1/fixtures.mts",
  "src/hswm/effect-runtime/src/research-relation-comparison.ts",
  "src/hswm/effect-runtime/src/relation-program-research.ts",
  "src/hswm/effect-runtime/package-lock.json"
]
const result = {
  schema_version: "hswm-calibration-structure-observation/v1",
  authority: "SECONDARY_AI_ENGINEERING_OBSERVATION",
  status: "AUTHORED_FIXED_PROGRAM_STRUCTURAL_CHECK",
  claim_ceiling: "NO_MODEL_SCORE_NO_LEARNING_RESULT_NO_NEW_INDEPENDENT_HOLDOUT_NO_HSWM_EFFICACY",
  selection: "Hand-written ordered composition of existing public primitives after source inspection; no outcome-dependent search.",
  protocol: protocolPath, program,
  bindings: paths.map((path) => ({ path, sha256: digest(readFileSync(new URL(path, root))) })),
  runtime: { version: process.version, binarySha256: digest(readFileSync(process.execPath)) },
  totals: { training: rows.filter((r) => r.split === "training" && r.exact).length,
    calibration: rows.filter((r) => r.split === "calibration" && r.exact).length,
    cases: rows.length, modelCalls: 0, learningUpdates: 0 }, rows,
  limitations: ["Known authored schema and generator; task answers share that construction.",
    "Does not measure whether any model discovers this program or saturates the calibration.",
    "Does not meet matched model-cost comparison or independent outcome custody."]
}
process.stdout.write(`${JSON.stringify(result, null, 2)}\n`)
