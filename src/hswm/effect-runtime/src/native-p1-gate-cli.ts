/** CLI shell for P1 post-hoc diagnostics with frozen-cache or pinned local inference. */
import { resolve } from "node:path"
import { createHash } from "node:crypto"
import { parseArgs } from "node:util"
import { Data, Effect, Either } from "effect"
import { PosixFileSystem } from "./effect-posix-filesystem.js"
import { decodeNativeP1GateCommand, evaluateNativeP1Gate } from "./native-p1-gate-runtime.js"
import { writeNativeP1OutputAtomic } from "./native-p1-output-runtime.js"
import { decodeNativeTaskJson, renderNativeTaskJson, taskFloatText, type TaskJson } from "./native-task-json-domain.js"

export class NativeP1GateCliError extends Data.TaggedError("NativeP1GateCliError")<{ readonly detail: string }> {}
const usage = "usage: hswm-p1-gate-diagnostic --evidence FILE --dataset-root DIR --experiment-directory DIR --embedding-cache-folder DIR --output FILE"
const float = (value: number): Effect.Effect<TaskJson, NativeP1GateCliError> =>
  decodeNativeTaskJson(new TextEncoder().encode(taskFloatText(value))).pipe(
    Either.match({ onLeft: () => Effect.fail(new NativeP1GateCliError({ detail: "cannot encode non-finite P1 float" })), onRight: Effect.succeed }),
  )

export const runNativeP1GateCli = (argv: readonly string[]): Effect.Effect<string, NativeP1GateCliError, PosixFileSystem> => Effect.gen(function* () {
  const parsed = yield* Effect.try({
    try: () => parseArgs({ args: [...argv], strict: true, allowPositionals: false, options: {
      evidence: { type: "string" }, "dataset-root": { type: "string" }, "experiment-directory": { type: "string" },
      "embedding-cache-folder": { type: "string" }, output: { type: "string" }, help: { type: "boolean", short: "h" },
    } }),
    catch: () => new NativeP1GateCliError({ detail: usage }),
  })
  if (parsed.values.help) return `${usage}\nReplays frozen candidate snapshots. If the embedding cache is absent, uses the pinned local native-p1-onnx artifacts; does not create a new arm outcome.\n`
  const flat = Object.entries(parsed.values).flatMap(([key, value]) => typeof value === "string" ? [`--${key}`, value] : [])
  const command = decodeNativeP1GateCommand(flat)
  if (Either.isLeft(command)) return yield* Effect.fail(new NativeP1GateCliError({ detail: usage }))
  const inputs = command.right
  const diagnostic = yield* evaluateNativeP1Gate(resolve(inputs.evidence), resolve(inputs.datasetRoot), resolve(inputs.experimentDirectory), resolve(inputs.embeddingCacheFolder))
    .pipe(Effect.mapError(error => new NativeP1GateCliError({ detail: error.detail })))
  const candidates = yield* Effect.forEach(diagnostic.candidate_gates, row => Effect.gen(function* () {
    return Object.freeze({
      arm_id: row.arm_id, candidate_id: row.candidate_id, episode_index: row.episode_index,
      fresh_gate_pass: row.fresh_gate_pass, recorded_fsm_final_state: row.recorded_fsm_final_state,
      unseen_ci_low: yield* float(row.unseen_ci_low), unseen_delta: yield* float(row.unseen_delta),
    })
  }))
  const summary = Object.freeze({ candidates: candidates.length, fresh_gate_passes: candidates.filter(row => row.fresh_gate_pass).length,
    nonzero_unseen_delta: diagnostic.candidate_gates.filter(row => row.unseen_delta !== 0).length })
  const output: TaskJson = Object.freeze({
    schema_version: diagnostic.embedding_backend === undefined ? "hswm-p1-posthoc-gate-diagnostic/v1" : "hswm-p1-posthoc-gate-diagnostic/v2", scientific_status: "POSTHOC_DIAGNOSTIC_NOT_A_NEW_ARM_OUTCOME",
    source_evidence_sha256: diagnostic.source_evidence_sha256, frozen_split_manifest_sha256: diagnostic.frozen_split_manifest_sha256,
    candidate_gates: Object.freeze(candidates), summary,
    ...(diagnostic.embedding_backend === undefined ? {} : { embedding_backend: diagnostic.embedding_backend }),
  })
  const digest = createHash("sha256").update(renderNativeTaskJson(output)).digest("hex")
  const document: TaskJson = Object.freeze({ ...output, diagnostic_sha256: digest })
  yield* writeNativeP1OutputAtomic(resolve(inputs.output), new TextEncoder().encode(renderNativeTaskJson(document, "pretty")))
    .pipe(Effect.mapError(error => new NativeP1GateCliError({ detail: error.detail })))
  return `${renderNativeTaskJson(summary, "pretty")}\n`
})
