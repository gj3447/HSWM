#!/usr/bin/env node
/** Optional post-run audit; no mutation or admission capability is granted. */
import { createHash } from "node:crypto"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { Effect, Schema } from "effect"
import { CanonicalAtomV2DurableRuntime } from "./canonical-atom-v2-durable-runtime.js"
import { BoundedSubprocess } from "./effect-bounded-subprocess.js"
import { PosixFileSystem } from "./effect-posix-filesystem.js"
import { runArgvProcessMain, refuse } from "./effect-process-main.js"
import { readLifecycleConfig, readLifecycleJson, writeLifecycleJson } from "./semantic-lifecycle-io.js"
import { makeSemanticLifecycleFileLayer, relationUid } from "./semantic-lifecycle-runtime.js"
import { projectSemanticLifecycleRefinement, SemanticRefinementTraceSchema, SemanticRefinementOutcomeSchema, SemanticRefinementSelectionSchema } from "./semantic-lifecycle-refinement.js"

const usage = "Usage: node dist/semantic-lifecycle-refinement-process.js --root EXISTING_SELECTED_LIFECYCLE --output NEW_PRIVATE_DIRECTORY\nUses formal/.lake/build/bin/HSWMSemanticLifecycleCli. Reports structural correspondence only, not selection chronology, LLM efficacy or full TS refinement.\n"
const sha = (raw: Uint8Array | string) => createHash("sha256").update(raw).digest("hex")
const trainingSchema = Schema.Struct({ trace: SemanticRefinementTraceSchema, outcome: SemanticRefinementOutcomeSchema })
const nextSchema = Schema.Struct({ trace: SemanticRefinementTraceSchema, selectedBeforeHeldout: Schema.Literal(true) })
const selectionSchema = Schema.Struct({ decision: SemanticRefinementSelectionSchema })
const resultSchema = Schema.Struct({ contract: Schema.Literal("hswm-semantic-lifecycle-postrun/v1"), accepted: Schema.Boolean })

export const semanticLifecycleRefinementCli = (argv: ReadonlyArray<string>, repository: string,
  environment: Readonly<Record<string, string>>) => Effect.gen(function* () {
  if (argv.length === 1 && argv[0] === "--help") return usage
  const entries = Array.from({ length: Math.floor(argv.length / 2) }, (_, i) => [argv[i * 2], argv[i * 2 + 1]] as const)
  const args = Object.fromEntries(entries)
  if (argv.length !== 4 || new Set(entries.map(([k]) => k)).size !== entries.length ||
    entries.some(([k, v]) => !["--root", "--output"].includes(k ?? "") || !v || v.startsWith("--")) || !args["--root"] || !args["--output"]) return yield* Effect.fail(refuse(usage))
  const root = resolve(args["--root"]), output = resolve(args["--output"])
  const lean = join(repository, "formal/.lake/build/bin/HSWMSemanticLifecycleCli")
  const config = yield* readLifecycleConfig(join(root, "config.json"))
  if (resolve(config.root) !== root) return yield* Effect.fail(refuse("config root differs from requested lifecycle"))
  const training = yield* readLifecycleJson(join(root, "train-base.json")).pipe(Effect.flatMap(Schema.decodeUnknown(trainingSchema)))
  const selected = yield* readLifecycleJson(join(root, "selection.json")).pipe(Effect.flatMap(Schema.decodeUnknown(selectionSchema)))
  const next = yield* readLifecycleJson(join(root, "heldout-selected.json")).pipe(Effect.flatMap(Schema.decodeUnknown(nextSchema)))
  const baselineRoot = join(root, "states/frozen"), candidateRoot = join(root, "states/learned")
  if (selected.decision.baselineBranch.root !== baselineRoot || selected.decision.candidateBranch.root !== candidateRoot) return yield* Effect.fail(refuse("selection roots are outside this lifecycle"))
  const backend = sha(JSON.stringify({ baseUrl: config.cell.base_url, model: config.cell.model, apiKeyEnvironment: config.cell.api_key_env ?? null, maxTokens: config.cell.max_tokens }))
  if (training.trace.backendConfigurationSha256 !== backend || next.trace.backendConfigurationSha256 !== backend) return yield* Effect.fail(refuse("trace backend differs from declared config"))
  const open = (path: string) => CanonicalAtomV2DurableRuntime.pipe(Effect.provide(makeSemanticLifecycleFileLayer(path)))
  const baselineRuntime = yield* open(baselineRoot), candidateRuntime = yield* open(candidateRoot)
  const selectedRuntime = yield* open(selected.decision.selected === "CANDIDATE" ? candidateRoot : baselineRoot)
  const wire = yield* projectSemanticLifecycleRefinement({ baseline: { root: baselineRoot, relationUid, runtime: baselineRuntime },
    candidate: { root: candidateRoot, relationUid, runtime: candidateRuntime }, selectedRuntime, selection: selected.decision,
    trainingTrace: training.trace, trainingOutcome: training.outcome, nextTrace: next.trace })
  const encoded = new TextEncoder().encode(JSON.stringify(wire))
  if (encoded.byteLength > 1_048_576) return yield* Effect.fail(refuse("projected witness exceeds one MiB"))
  const fs = yield* PosixFileSystem
  const binary = yield* fs.readRegularBounded(lean, { maximumBytes: 128 * 1024 * 1024, minimumBytes: 1, operation: "semantic-refinement-checker-pin" })
  const subprocess = yield* BoundedSubprocess
  const result = yield* subprocess.observe({ argv: [lean], cwd: repository, environment, stdin: encoded,
    timeoutMs: 30000, maximumOutputBytes: 16384, killProcessGroup: true })
  if (result.exitCode !== 0 || result.timedOut || result.outputTruncated || result.launchError !== null) return yield* Effect.fail(refuse("Lean witness checker did not complete"))
  const raw = yield* Effect.try({ try: (): unknown => JSON.parse(new TextDecoder().decode(result.stdout)), catch: () => refuse("checker response is not JSON") })
  const checked = yield* Schema.decodeUnknown(resultSchema)(raw, { onExcessProperty: "error" })
  yield* fs.makeDirectory(dirname(output), { recursive: true, mode: 0o700, operation: "semantic-refinement-parent" })
  yield* fs.makeDirectory(output, { mode: 0o700, operation: "semantic-refinement-output" })
  yield* writeLifecycleJson(join(output, "witness.json"), wire)
  const report = { contract: "hswm-semantic-lifecycle-refinement-report/v1", accepted: checked.accepted,
    witnessSha256: sha(`${JSON.stringify(wire, null, 2)}\n`), checkerInputSha256: sha(encoded),
    checkerSha256: sha(binary.bytes), selectedCandidate: wire.selectedCandidate,
    chronologyVerified: false, checkerIdentity: "LOCAL_BUILD_DIGEST_RECORDED_NOT_COMPILER_VERIFIED",
    predecessorRevision: wire.before.relation.key.revisionId, successorRevision: wire.after.relation.key.revisionId,
    nextReadRevision: wire.nextTrace.relationKey.revisionId,
    claimCeiling: "DECODED_STRUCTURAL_WITNESS_WITH_TESTED_BYTE_ADAPTER_NOT_FULL_TS_PROOF_OR_LLM_EFFICACY" }
  yield* writeLifecycleJson(join(output, "report.json"), report)
  return `${JSON.stringify(report)}\n`
})

if (import.meta.main) {
  const repository = resolve(dirname(fileURLToPath(import.meta.url)), "../../../..")
  const environment = Object.fromEntries(Object.entries(process.env).flatMap(([k, v]) => v === undefined ? [] : [[k, v]]))
  process.exitCode = await runArgvProcessMain({ program: argv => semanticLifecycleRefinementCli(argv, repository, environment),
    refusalPrefix: "SEMANTIC_REFINEMENT_REFUSED", describeFailure: error => "detail" in error ? String(error.detail) : String(error), failureExitCode: 1 }, process.argv.slice(2))
}
