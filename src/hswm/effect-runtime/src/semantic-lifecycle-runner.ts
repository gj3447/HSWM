/** Finite process-isolated diagnostic, composed entirely through Effect services. */
import { createHash } from "node:crypto"
import { dirname, isAbsolute, join, relative, resolve } from "node:path"
import { Cause, Context, Effect, Ref, Schema } from "effect"
import { BoundedSubprocess } from "./effect-bounded-subprocess.js"
import { PosixFileSystem, type PosixIoError } from "./effect-posix-filesystem.js"
import { decodeLifecycleCell, lifecycleArms, lifecycleFailure, type LifecycleConfig, type LifecycleOptions, type LifecycleStage, type LifecycleArm, type LifecycleError } from "./semantic-lifecycle-domain.js"
import { readLifecycleJson, writeLifecycleJson } from "./semantic-lifecycle-io.js"
import { prepareLifecycleSelection } from "./semantic-lifecycle-selected-execution.js"
import { evaluateLifecycleRuntime, SEMANTIC_LIFECYCLE_WORKER_V1 } from "./semantic-lifecycle-worker.js"
import { createSemanticLifecycleTransport } from "./semantic-lifecycle-transport.js"

export class LifecycleHost extends Context.Tag("hswm/LifecycleHost")<LifecycleHost, {
  readonly repository: string
  readonly nodeExecutable: string
  readonly nodeVersion: string
  readonly environment: Readonly<Record<string, string>>
}>() {}
export interface LifecycleSourcePin { readonly path: string; readonly sha256: string; readonly byteLength: number }
const sha = (raw: Uint8Array): string => createHash("sha256").update(raw).digest("hex")
const runtimeRoot = "src/hswm/effect-runtime"
const readSource = (repository: string, path: string) => PosixFileSystem.pipe(Effect.flatMap(fs =>
  fs.readRegularBounded(join(repository, path), { maximumBytes: 16_777_216, operation: "semantic-lifecycle-source-pin" })))

/** Bind static local imported source/compiled closure and installed Effect metadata. */
export const lifecycleSourcePins = Effect.gen(function* () {
  const host = yield* LifecycleHost
  type Pins = Readonly<Record<string, LifecycleSourcePin>>
  const collect = (path: string, pins: Pins): Effect.Effect<Pins, PosixIoError | LifecycleError, PosixFileSystem> => Effect.gen(function* () {
    if (pins[path] !== undefined) return pins
    if (path.startsWith("..") || isAbsolute(path)) return yield* Effect.fail(lifecycleFailure("SOURCE_INVALID", "Source is outside the repository"))
    const raw = yield* readSource(host.repository, path)
    const next: Pins = { ...pins, [path]: { path, sha256: sha(raw.bytes), byteLength: raw.bytes.byteLength } }
    const source = path.includes("/dist/") && path.endsWith(".js") ? [path.replace("/dist/", "/src/").replace(/\.js$/, ".ts")] : []
    const imports = /\.(mjs|js)$/.test(path) && !path.includes("/node_modules/")
      ? [...new TextDecoder().decode(raw.bytes).matchAll(/(?:from\s*|import\s*)['"]([^'"]+)['"]/g)]
        .flatMap(match => match[1]?.startsWith(".") && !match[1].includes("node_modules")
          ? [relative(host.repository, resolve(host.repository, dirname(path), match[1]))] : [])
      : []
    return yield* Effect.reduce([...source, ...imports], next, (state, dependency) => collect(dependency, state))
  })
  const entries = yield* Effect.reduce([
    `${runtimeRoot}/dist/semantic-lifecycle-process.js`, `${runtimeRoot}/dist/semantic-lifecycle-worker-process.js`,
    "_research/hswm_semantic_lifecycle_v1/run.mjs", `${runtimeRoot}/package-lock.json`, `${runtimeRoot}/node_modules/effect/package.json`
  ], {} as Pins, (state, path) => collect(path, state))
  return Object.values(entries).sort((a, b) => a.path.localeCompare(b.path))
})
export const verifyLifecyclePins = (pins: ReadonlyArray<LifecycleSourcePin>) => Effect.gen(function* () {
  const host = yield* LifecycleHost
  yield* Effect.forEach(pins, pin => readSource(host.repository, pin.path).pipe(Effect.flatMap(raw => sha(raw.bytes) === pin.sha256
    ? Effect.void : Effect.fail(lifecycleFailure("SOURCE_CHANGED", `Source changed during run: ${pin.path}`)))), { discard: true })
})

const content = Schema.Struct({ sha256: Schema.String })
const key = Schema.Struct({ revisionId: Schema.Number })
const state = Schema.Struct({ canonicalSha256: Schema.String, relationKey: key, roleRefs: Schema.Array(Schema.Unknown),
  semantic: Schema.Struct({ trace: Schema.NullOr(content), outcome: Schema.NullOr(content) }) })
const call = Schema.Struct({ httpModelRequest: Schema.Boolean, frameSha256: Schema.String, usage: Schema.Unknown })
const baseReport = { processId: Schema.Number, arm: Schema.String, calls: Schema.Array(call) }
const TrainingSchema = Schema.Struct({ ...baseReport, state, trace: Schema.Struct({ traceContent: content }), outcome: Schema.Struct({ outcomeContent: content, status: Schema.String }) })
const RevisionSchema = Schema.Struct({ ...baseReport, committed: Schema.Boolean, disposition: Schema.String, errorCode: Schema.NullOr(Schema.String), after: state })
const EvaluationSchema = Schema.Struct({ ...baseReport, stage: Schema.Literal("development", "heldout"), before: state, canonicalUnchanged: Schema.Boolean,
  trace: Schema.NullOr(Schema.Struct({ relationKey: key, frameSha256: Schema.String })), assessment: Schema.Struct({ correct: Schema.Number, denominator: Schema.Number }) })
const decodeReport = <A, I>(schema: Schema.Schema<A, I>) => (raw: unknown) => Schema.decodeUnknown(schema)(raw).pipe(
  Effect.mapError(() => lifecycleFailure("REPORT_INVALID", "Worker report did not satisfy lifecycle binding contract")))
export interface LifecycleLaunch { readonly stage: LifecycleStage; readonly arm: LifecycleArm; readonly childPid: number; readonly exitedBeforeNextStage: true }

export const runLifecycle = (input: LifecycleOptions) => Effect.gen(function* () {
  const options = Object.freeze({ ...input, ...(input.selection == null ? {} : { selection: Object.freeze({ ...input.selection }) }) })
  const fs = yield* PosixFileSystem
  const host = yield* LifecycleHost
  const subprocess = yield* BoundedSubprocess
  const cell = options.transport === "scripted"
    ? { base_url: "https://fixture.invalid/v1", model: "SCRIPTED_NOT_A_MODEL", max_tokens: 512 }
    : yield* readLifecycleJson(options.cellPath ?? "").pipe(Effect.flatMap(decodeLifecycleCell))
  if ("api_key_env" in cell && cell.api_key_env !== undefined && !host.environment[cell.api_key_env])
    return yield* Effect.fail(lifecycleFailure("CELL_INVALID", "Missing named credential environment"))
  const pins = yield* lifecycleSourcePins
  const environmentSha256 = pins.find(pin => pin.path === `${runtimeRoot}/src/semantic-rule-environment.ts`)?.sha256
  if (!environmentSha256) return yield* Effect.fail(lifecycleFailure("BUILD_REQUIRED", "Build the environment before running"))
  yield* fs.makeDirectory(dirname(options.output), { recursive: true, mode: 0o700, operation: "semantic-lifecycle-parent" })
  yield* fs.makeDirectory(options.output, { mode: 0o700, operation: "semantic-lifecycle-attempt" })
  const config: LifecycleConfig = {
    contract: "hswm-semantic-lifecycle/v1", root: options.output, transport: options.transport, cell, arms: lifecycleArms, environmentSha256,
    candidateCount: 1, developmentUsedForSelection: options.selection !== null && options.selection !== undefined, heldoutUsedForRevision: false,
    ...(options.selection == null ? {} : { selection: options.selection }),
    budget: { maximumModelRequests: 10, maximumWorkerMs: 75000, automaticRetries: 0 },
    modelExecutionStatus: options.transport === "scripted" ? "NO_MODEL" : "CALLER_DECLARED_HTTP_ENDPOINT_NOT_INDEPENDENTLY_VERIFIED",
    claimCeiling: options.transport === "scripted" ? "SCRIPTED_WIRING_ONLY_NOT_MODEL_EFFICACY" : "FINITE_AUTHORED_DIAGNOSTIC_NOT_CONFIRMATORY_EFFICACY"
  }
  const configPath = join(options.output, "config.json")
  const launches = yield* Ref.make<ReadonlyArray<LifecycleLaunch>>([])
  const observe = (argv: ReadonlyArray<string>) => subprocess.observe({ argv, cwd: host.repository, environment: host.environment,
    timeoutMs: config.budget.maximumWorkerMs, maximumOutputBytes: 4096, killProcessGroup: true }).pipe(Effect.flatMap(result =>
    result.exitCode === 0 && !result.timedOut && !result.outputTruncated && result.launchError === null
      ? Effect.void : Effect.fail(lifecycleFailure("PROCESS_FAILED", `Lifecycle subprocess failed (${result.timedOut ? "timeout" : result.exitCode ?? "launch"})`))))
  const launch = (stage: LifecycleStage, arm: LifecycleArm) => Effect.gen(function* () {
    yield* verifyLifecyclePins(pins)
    yield* observe([host.nodeExecutable, join(host.repository, runtimeRoot, "dist/semantic-lifecycle-worker-process.js"), stage, configPath, arm]).pipe(
      Effect.mapError(error => lifecycleFailure("PROCESS_FAILED", `Worker ${stage}/${arm}: ${error.detail}`)))
    const raw = yield* readLifecycleJson(join(options.output, `${stage}-${arm}.json`))
    const row = yield* decodeReport(Schema.Struct({ processId: Schema.Number }))(raw)
    yield* Ref.update(launches, rows => [...rows, { stage, arm, childPid: row.processId, exitedBeforeNextStage: true as const }])
  })
  return yield* Effect.gen(function* () {
    yield* writeLifecycleJson(configPath, config)
    yield* writeLifecycleJson(join(options.output, "source-pins.json"), { node: host.nodeVersion, pins })
    yield* fs.makeDirectory(join(options.output, "states"), { mode: 0o700, operation: "semantic-lifecycle-states" })
    yield* launch("train", "base")
    // cp -a retains internal slot/object hard links required by native journal recovery.
    yield* Effect.forEach(lifecycleArms, arm => observe(["cp", "-a", "--", join(options.output, "states/base"), join(options.output, "states", arm)]), { discard: true })
    const revisedArms = ["evidence_only", "sham", "learned"] as const
    yield* Effect.forEach(revisedArms, arm => launch("revise", arm), { discard: true })
    const developmentPlan = lifecycleArms.map(arm => ({ stage: "development" as const, arm }))
    yield* Effect.forEach(developmentPlan, ({ stage, arm }) => launch(stage, arm), { discard: true })
    const training = yield* readLifecycleJson(join(options.output, "train-base.json"))
    const revisions = yield* Effect.forEach(revisedArms, arm => readLifecycleJson(join(options.output, `revise-${arm}.json`)))
    const development = yield* Effect.forEach(developmentPlan, ({ stage, arm }) => readLifecycleJson(join(options.output, `${stage}-${arm}.json`)))
    const selected = options.selection == null ? null : yield* prepareLifecycleSelection(config, {
      training, baselineDevelopment: development[0], candidateDevelopment: development[3], candidateRevision: revisions[2],
      allowance: options.selection.allowance, debit: options.selection.debit
    })
    const heldoutReports = selected === null ? yield* Effect.gen(function* () {
      yield* Effect.forEach(lifecycleArms, arm => launch("heldout", arm), { discard: true })
      return yield* Effect.forEach(lifecycleArms, arm => readLifecycleJson(join(options.output, `heldout-${arm}.json`)))
    }) : yield* Effect.gen(function* () {
      // The decision is durable before any heldout call is made. Never revise it from heldout.
      yield* writeLifecycleJson(join(options.output, "selection.json"), selected.report)
      yield* verifyLifecyclePins(pins)
      const transport = yield* createSemanticLifecycleTransport({ mode: config.transport, logRoot: join(options.output, "http", "heldout-selected") })
      const evaluated = yield* selected.executeNext(runtime => evaluateLifecycleRuntime(config, "heldout", runtime, transport.http)).pipe(
        Effect.timeoutFail({ duration: config.budget.maximumWorkerMs, onTimeout: () => lifecycleFailure("SELECTED_EXECUTION_TIMEOUT", "Selected execution exceeded the bounded stage time") }))
      const processInfo = yield* Effect.sync(() => ({ processId: process.pid, parentProcessId: process.ppid }))
      const report = { contract: SEMANTIC_LIFECYCLE_WORKER_V1, stage: "heldout", arm: selected.selectedArm,
        ...processInfo, ...evaluated, calls: yield* transport.calls, selectedBeforeHeldout: true,
        executionBoundary: "FRESH_DURABLE_RUNTIME_IN_PARENT_AFTER_DEVELOPMENT_CHILDREN_EXIT" }
      yield* writeLifecycleJson(join(options.output, "heldout-selected.json"), report)
      return [report]
    })
    const evaluations = [...development, ...heldoutReports]
    const trainingCheck = yield* decodeReport(TrainingSchema)(training)
    const revisionChecks = yield* Effect.forEach(revisions, decodeReport(RevisionSchema))
    const evaluationChecks = yield* Effect.forEach(evaluations, decodeReport(EvaluationSchema))
    const committedEvidenceBindingsValid = revisionChecks.filter(row => row.committed).every(row =>
      row.after.semantic.trace?.sha256 === trainingCheck.trace.traceContent.sha256 && row.after.semantic.outcome?.sha256 === trainingCheck.outcome.outcomeContent.sha256)
    const revisionFailures = revisionChecks.filter(row => !row.committed).map(row => ({ arm: row.arm, disposition: row.disposition, errorCode: row.errorCode }))
    const sharedEvidence = revisionChecks.length === 3 && revisionFailures.length === 0 && committedEvidenceBindingsValid
    const reopened = evaluationChecks.every(row => {
      const revision = revisionChecks.find(r => r.arm === row.arm)
      const prior = revision?.after ?? trainingCheck.state
      return row.before.canonicalSha256 === prior.canonicalSha256 && row.canonicalUnchanged &&
        (row.trace === null || (row.trace.relationKey.revisionId === prior.relationKey.revisionId && row.calls.some(call => call.frameSha256 === row.trace?.frameSha256))) &&
        JSON.stringify(row.before.roleRefs) === JSON.stringify(trainingCheck.state.roleRefs) &&
        row.processId !== trainingCheck.processId && row.processId !== revision?.processId
    })
    if (!committedEvidenceBindingsValid || !reopened) return yield* Effect.fail(lifecycleFailure("BINDING_FAILED", "Lifecycle binding checks failed"))
    yield* verifyLifecyclePins(pins)
    const callLists = yield* Effect.forEach([training, ...revisions, ...evaluations], decodeReport(Schema.Struct({ calls: Schema.Array(Schema.Unknown) })))
    const calls = callLists.flatMap(row => row.calls)
    const callChecks = [trainingCheck, ...revisionChecks, ...evaluationChecks].flatMap(row => row.calls)
    const report = { ...config, status: revisionFailures.length ? "COMPLETED_WITH_REVISION_FAILURES" : "COMPLETED_DIAGNOSTIC",
      launches: yield* Ref.get(launches), sharedEvidence, committedEvidenceBindingsValid, revisionFailures, reopened, training, revisions, evaluations, calls,
      ...(selected === null ? {} : { selection: selected.report }),
      httpModelRequests: callChecks.filter(row => row.httpModelRequest).length,
      usageStatus: callChecks.filter(row => row.httpModelRequest).every(row => row.usage !== null) ? "RAW_USAGE_PRESENT_OR_NO_HTTP_REQUESTS" : "PARTIALLY_UNAVAILABLE_NOT_ZERO",
      scientificStatus: "NOT_ADJUDICATED", outcomeAuthority: trainingCheck.outcome.status }
    yield* writeLifecycleJson(join(options.output, "summary.json"), report)
    return { report, heldout: evaluationChecks.filter(row => row.stage === "heldout").map(row => ({ arm: row.arm, correct: row.assessment.correct, total: row.assessment.denominator })) }
  }).pipe(Effect.onError(cause => Effect.gen(function* () {
    const failure = Cause.failureOption(cause)
    yield* writeLifecycleJson(join(options.output, "failure.json"), { status: "FAILED_DIAGNOSTIC", launches: yield* Ref.get(launches), plannedHeldoutCasesPerArm: 4,
      errorCode: failure._tag === "Some" && "code" in failure.value ? failure.value.code : "INTERRUPTED_OR_DEFECT",
      message: failure._tag === "Some" && "detail" in failure.value ? failure.value.detail : "Lifecycle effect interrupted or defected", scientificStatus: "NOT_ADJUDICATED" })
  }).pipe(Effect.orDie)))
})
