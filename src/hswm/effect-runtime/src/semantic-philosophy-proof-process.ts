#!/usr/bin/env node
/**
 * Bounded Lean audit for the three-philosophies finite formal witnesses.
 * This records compiler/kernel facts only; it is not an HSWM efficacy gate.
 */
import { createHash } from "node:crypto"
import { dirname, isAbsolute, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { Context, Data, Effect, Layer, Schema } from "effect"
import { BoundedSubprocess } from "./effect-bounded-subprocess.js"
import { runArgvProcessMain } from "./effect-process-main.js"
import { PosixFileSystem } from "./effect-posix-filesystem.js"

const utf8 = new TextDecoder()
const bytes = new TextEncoder()
const sha256 = (value: Uint8Array): string => createHash("sha256").update(value).digest("hex")
const threePhilosophiesSourceOrder = Object.freeze([
  "HSWMSemanticWeightDefinition", "HSWMHypergraphRepresentation", "HSWMLocalEnsembleGain",
  "HSWMOutcomeLearningGain", "HSWMSemanticQuotient", "HSWMConstructiveRelationSynthesis",
  "HSWMCorrelatedReliability", "HSWMNoisyFeedback", "HSWMRecursiveLearningComposition",
  "HSWMGeneratedLearningBridge", "HSWMMultiscaleSimulation", "HSWMHypergraphCostConditions",
  "HSWMSemanticSoftware"
] as const)
const threePhilosophiesAuditedSources = Object.freeze(["HSWMMultiscaleSimulation", "HSWMHypergraphCostConditions", "HSWMSemanticSoftware"] as const)
const integratedHswmSourceOrder = Object.freeze([...threePhilosophiesSourceOrder,
  "HSWMLLMSemanticGraph", "HSWMIntegratedClosedLoop", "HSWMClosedLoopEvaluation"] as const)
const integratedHswmAuditedSources = Object.freeze([...threePhilosophiesAuditedSources,
  "HSWMIntegratedClosedLoop", "HSWMClosedLoopEvaluation"] as const)
const operationalPhilosophyAuditedSources = Object.freeze([
  "HSWMOperationalAbstraction", "HSWMBehavioralMinimality", "HSWMExecutableGraphEncoding"
] as const)
const operationalPhilosophySourceOrder = Object.freeze([
  ...threePhilosophiesSourceOrder, ...operationalPhilosophyAuditedSources
] as const)
type ProfileName = "three-philosophies" | "integrated-hswm" | "operational-philosophy"
interface ProofProfile {
  readonly name: ProfileName
  readonly sourceOrder: ReadonlyArray<string>
  readonly auditedSources: ReadonlyArray<string>
  readonly schemaVersion: string
  readonly claimCeiling: string
}
const profiles: Readonly<Record<ProfileName, ProofProfile>> = Object.freeze({
  "three-philosophies": Object.freeze({ name: "three-philosophies", sourceOrder: threePhilosophiesSourceOrder,
    auditedSources: threePhilosophiesAuditedSources, schemaVersion: "hswm-three-philosophies-lean-verification/v1",
    claimCeiling: "FINITE_CONDITIONAL_FORMAL_WITNESSES_NOT_UNIVERSAL_MINIMUM_COST_OUTERMOST_SIMULATOR_CHU_REALITY_LLM_FIDELITY_OR_HSWM_EFFICACY" }),
  "integrated-hswm": Object.freeze({ name: "integrated-hswm", sourceOrder: integratedHswmSourceOrder,
    auditedSources: integratedHswmAuditedSources, schemaVersion: "hswm-integrated-hswm-lean-verification/v1",
    claimCeiling: "CONDITIONAL_FINITE_CANONICAL_CLOSED_LOOP_NOT_FULL_HSWM_OR_REAL_LLM" }),
  "operational-philosophy": Object.freeze({ name: "operational-philosophy", sourceOrder: operationalPhilosophySourceOrder,
    auditedSources: operationalPhilosophyAuditedSources, schemaVersion: "hswm-operational-philosophy-lean-verification/v1",
    claimCeiling: "DECLARED_DETERMINISTIC_ABSTRACTION_BEHAVIORAL_MINIMALITY_AND_STORAGE_EXECUTION_NOT_UNIVERSAL_COST_WORLD_TRUTH_REAL_LLM_OR_FULL_HSWM" })
})
const permittedAxioms = Object.freeze(["propext", "Quot.sound", "Classical.choice"] as const)
const stripLeanComments = (source: string): string => source.replace(/\/\-[\s\S]*?\-\//g, "").replace(/--[^\n]*/g, "")
const hasForbiddenProofShortcut = (source: string): boolean => {
  const code = stripLeanComments(source)
  return /\b(?:sorry|admit|native_decide)\b/.test(code) ||
    /(^|\n)\s*(?:axiom|opaque|unsafe|meta)\b/.test(code) ||
    /(^|\n)\s*set_option\s+(?!(?:linter\.unusedSimpArgs\s+false)\s*(?:\n|$))/.test(code)
}

export class SemanticPhilosophyProofError extends Data.TaggedError("SemanticPhilosophyProofError")<{
  readonly code: "CLI_INVALID" | "PIN_INVALID" | "TOOLCHAIN_MISMATCH" | "SOURCE_INVALID" | "COMPILER_FAILED" | "AXIOM_REJECTED" | "SOURCE_CHANGED"
  readonly detail: string
}> {}
const fail = (code: SemanticPhilosophyProofError["code"], detail: string) => new SemanticPhilosophyProofError({ code, detail })
export class SemanticPhilosophyProofHost extends Context.Tag("hswm/SemanticPhilosophyProofHost")<SemanticPhilosophyProofHost, {
  readonly repository: string
  readonly environment: Readonly<Record<string, string>>
}>() {}

interface Options { readonly output: string; readonly lean: string | null; readonly profile: ProofProfile }
const parse = (argv: ReadonlyArray<string>, cwd: string): Effect.Effect<Options | null, SemanticPhilosophyProofError> => {
  if (argv.length === 1 && argv[0] === "--help") return Effect.succeed(null)
  if (argv.length !== 2 && argv.length !== 4 && argv.length !== 6) return Effect.fail(fail("CLI_INVALID", "Expected --output NEW_DIRECTORY [--profile three-philosophies|integrated-hswm|operational-philosophy] [--lean ABSOLUTE_PATH]"))
  const pairs = Array.from({ length: argv.length / 2 }, (_, index) => [argv[index * 2], argv[index * 2 + 1]] as const)
  const values = Object.fromEntries(pairs)
  if (pairs.some(([key, value]) => !["--output", "--lean", "--profile"].includes(key ?? "") || !value || value.startsWith("--")) ||
      pairs.length !== new Set(pairs.map(([key]) => key)).size || typeof values["--output"] !== "string")
    return Effect.fail(fail("CLI_INVALID", "Invalid or duplicate CLI option"))
  const suppliedLean = values["--lean"]
  if (suppliedLean !== undefined && (!isAbsolute(suppliedLean) || suppliedLean.includes("\0")))
    return Effect.fail(fail("CLI_INVALID", "--lean must be an absolute regular-file path"))
  const profileName: unknown = values["--profile"] ?? "three-philosophies"
  if (profileName !== "three-philosophies" && profileName !== "integrated-hswm" && profileName !== "operational-philosophy")
    return Effect.fail(fail("CLI_INVALID", "--profile must be three-philosophies, integrated-hswm or operational-philosophy"))
  const profile = profiles[profileName]
  return Effect.succeed({ output: resolve(cwd, values["--output"]), lean: suppliedLean ?? null, profile })
}

const read = (path: string, operation: string) => PosixFileSystem.pipe(Effect.flatMap(fs =>
  fs.readRegularBounded(path, { maximumBytes: 16 * 1024 * 1024, minimumBytes: 1, operation })))
const writeJson = (path: string, value: unknown) => PosixFileSystem.pipe(Effect.flatMap(fs =>
  fs.writeExclusive(path, bytes.encode(`${JSON.stringify(value, null, 2)}\n`), { mode: 0o600, sync: true, operation: "semantic-philosophy-proof-report" })))
const command = (argv: ReadonlyArray<string>, cwd: string, environment: Readonly<Record<string, string>>, stdin?: Uint8Array) =>
  BoundedSubprocess.pipe(Effect.flatMap(subprocess => subprocess.observe({ argv, cwd, environment, ...(stdin === undefined ? {} : { stdin }), timeoutMs: 120_000, maximumOutputBytes: 2 * 1024 * 1024, killProcessGroup: true })))
const requireSuccess = (label: string, effect: ReturnType<typeof command>) => effect.pipe(Effect.flatMap(result =>
  result.exitCode === 0 && !result.timedOut && !result.outputTruncated && result.launchError === null
    ? Effect.succeed(result) : Effect.fail(fail("COMPILER_FAILED", `${label} did not complete successfully`))))

const priorToolchainSchema = Schema.Struct({
  toolchain: Schema.Struct({ name: Schema.String, version_output: Schema.String, source_commit: Schema.String,
    lean_binary_sha256: Schema.String, pin_path: Schema.String, pin_sha256: Schema.String })
})
const theoremNames = (source: string): ReadonlyArray<string> => Array.from(source.matchAll(/^\s*(?:theorem|lemma)\s+([A-Za-z_][A-Za-z0-9_']*)/gm), match => match[1] ?? "")
  .filter(name => name.length > 0)
const namespaceName = (source: string): string | null => /^\s*namespace\s+([A-Za-z0-9_.]+)/m.exec(source)?.[1] ?? null
export interface TheoremAxiomRecord { readonly theorem: string; readonly axioms: ReadonlyArray<string> }
export const parseTheoremAxioms = (output: string, expected: ReadonlyArray<string>): ReadonlyArray<TheoremAxiomRecord> | null => {
  const rows = Array.from(output.matchAll(/^'([^']+)' (?:does not depend on any axioms|depends on axioms: \[([^\]]*)\])$/gm), match =>
    Object.freeze({ theorem: match[1] ?? "", axioms: Object.freeze((match[2] ?? "").split(",").map(name => name.trim()).filter(name => name.length > 0).sort()) }))
  if (rows.length !== expected.length || new Set(rows.map(row => row.theorem)).size !== rows.length ||
      expected.some(theorem => !rows.some(row => row.theorem === theorem))) return null
  return Object.freeze(rows.sort((left, right) => left.theorem.localeCompare(right.theorem)))
}

export const runSemanticPhilosophyProof = (options: Options) => Effect.gen(function* () {
  const fs = yield* PosixFileSystem
  const host = yield* SemanticPhilosophyProofHost
  const formal = join(host.repository, "formal")
  const historical = yield* read(join(host.repository, "_research/llm_semantic_graph_v1/lean-verification.v1.json"), "semantic-philosophy-historical-pin")
  const historicalJson = yield* Effect.try({ try: () => JSON.parse(utf8.decode(historical.bytes)),
    catch: () => fail("PIN_INVALID", "Existing Lean verification pin is not JSON") })
  const decoded = yield* Schema.decodeUnknown(priorToolchainSchema)(historicalJson).pipe(
    Effect.mapError(() => fail("PIN_INVALID", "Existing Lean verification pin has an invalid minimal schema")))
  const pin = yield* read(join(host.repository, decoded.toolchain.pin_path), "semantic-philosophy-toolchain-pin")
  if (sha256(pin.bytes) !== decoded.toolchain.pin_sha256 || utf8.decode(pin.bytes).trim() !== decoded.toolchain.name)
    return yield* Effect.fail(fail("PIN_INVALID", "Lean toolchain pin differs from the existing source-bound record"))
  yield* fs.makeDirectory(dirname(options.output), { recursive: true, mode: 0o700, operation: "semantic-philosophy-parent" })
  yield* fs.makeDirectory(options.output, { mode: 0o700, operation: "semantic-philosophy-output" })
  const compiled = join(options.output, "olean")
  yield* fs.makeDirectory(compiled, { mode: 0o700, operation: "semantic-philosophy-olean" })
  const leanPathResult = options.lean === null
    ? yield* requireSuccess("resolve Lean", command(["lake", "env", "which", "lean"], formal, host.environment))
    : null
  const lean = options.lean ?? utf8.decode(leanPathResult?.stdout ?? new Uint8Array()).trim()
  if (!isAbsolute(lean) || lean.includes("\n")) return yield* Effect.fail(fail("TOOLCHAIN_MISMATCH", "Resolved Lean path is not one absolute path"))
  const leanIdentity = yield* fs.identity(lean, "semantic-philosophy-lean-identity")
  if (leanIdentity.kind !== "FILE") return yield* Effect.fail(fail("TOOLCHAIN_MISMATCH", "Resolved Lean is not a regular file"))
  const leanBytes = yield* read(lean, "semantic-philosophy-lean-hash")
  const version = yield* requireSuccess("Lean version", command([lean, "--version"], formal, host.environment))
  const versionText = utf8.decode(version.stdout).trim()
  if (sha256(leanBytes.bytes) !== decoded.toolchain.lean_binary_sha256 || versionText !== decoded.toolchain.version_output)
    return yield* Effect.fail(fail("TOOLCHAIN_MISMATCH", "Lean binary or exact version differs from existing pin"))
  const leanRoot = resolve(dirname(lean), "..")
  const freshEnvironment = Object.freeze({ PATH: host.environment["PATH"] ?? "/usr/bin:/bin", LEAN_PATH: `${compiled}:${join(leanRoot, "src/lean/Std")}` })
  const runnerPath = join(host.repository, "src/hswm/effect-runtime/src/semantic-philosophy-proof-process.ts")
  const runnerBefore = yield* read(runnerPath, "semantic-philosophy-runner-before")
  const sourcesBefore = new Map<string, string>()
  const sourceRecords: Array<Record<string, unknown>> = []
  for (const moduleName of options.profile.sourceOrder) {
    const relativePath = `formal/${moduleName}.lean`, sourcePath = join(host.repository, relativePath)
    const before = yield* read(sourcePath, "semantic-philosophy-source-before")
    sourcesBefore.set(relativePath, sha256(before.bytes))
    const source = utf8.decode(before.bytes)
    if (hasForbiddenProofShortcut(source)) return yield* Effect.fail(fail("SOURCE_INVALID", `Forbidden proof shortcut in ${relativePath}`))
    const outputPath = join(compiled, `${moduleName}.olean`)
    const compiledResult = yield* requireSuccess(`compile ${moduleName}`, command(
      [lean, "--trust=0", "-o", outputPath, sourcePath], formal, freshEnvironment))
    const after = yield* read(sourcePath, "semantic-philosophy-source-after")
    if (sha256(before.bytes) !== sha256(after.bytes)) return yield* Effect.fail(fail("SOURCE_CHANGED", `Proof source changed while compiling: ${relativePath}`))
    const isNewSource = options.profile.auditedSources.includes(moduleName)
    const publicTheorems = isNewSource ? theoremNames(source) : []
    const namespace = namespaceName(source)
    if (isNewSource && (namespace === null || publicTheorems.length === 0))
      return yield* Effect.fail(fail("SOURCE_INVALID", `New proof source lacks a namespace or public theorem: ${relativePath}`))
    const qualified = publicTheorems.map(name => `${namespace}.${name}`)
    const auditInput = isNewSource
      ? bytes.encode(`${source}\n${qualified.map(name => `#print axioms ${name}`).join("\n")}\n`) : undefined
    const audit = auditInput === undefined ? null : yield* requireSuccess(`audit ${moduleName}`, command(
      [lean, "--trust=0", "--stdin"], formal, freshEnvironment, auditInput))
    const theoremAxioms = audit === null ? [] : parseTheoremAxioms(utf8.decode(audit.stdout), qualified)
    if (theoremAxioms === null) return yield* Effect.fail(fail("AXIOM_REJECTED", `Axiom output was incomplete or ambiguous for ${moduleName}`))
    const axiomList = theoremAxioms.flatMap(row => row.axioms).filter((name, index, names) => names.indexOf(name) === index).sort()
    const rejected = axiomList.filter(name => !permittedAxioms.includes(name as typeof permittedAxioms[number]))
    if (rejected.length > 0) return yield* Effect.fail(fail("AXIOM_REJECTED", `Unpermitted axiom(s) in ${moduleName}: ${rejected.join(", ")}`))
    sourceRecords.push(Object.freeze({ path: relativePath, sha256: sha256(before.bytes), byteLength: before.bytes.byteLength,
      exitCode: compiledResult.exitCode, compiler_stdout_sha256: sha256(compiledResult.stdout), compiler_stderr_sha256: sha256(compiledResult.stderr),
      named_theorem_count: publicTheorems.length, named_theorems: qualified, theorem_axioms: theoremAxioms, axioms: axiomList,
      audit_stdout_sha256: audit === null ? null : sha256(audit.stdout), audit_stderr_sha256: audit === null ? null : sha256(audit.stderr) }))
  }
  yield* Effect.forEach(options.profile.sourceOrder, moduleName => Effect.gen(function* () {
    const relativePath = `formal/${moduleName}.lean`, current = yield* read(join(host.repository, relativePath), "semantic-philosophy-final-rebind")
    if (sha256(current.bytes) !== sourcesBefore.get(relativePath)) return yield* Effect.fail(fail("SOURCE_CHANGED", `Proof source changed before final report: ${relativePath}`))
  }), { discard: true })
  const runnerAfter = yield* read(runnerPath, "semantic-philosophy-runner-after")
  if (sha256(runnerBefore.bytes) !== sha256(runnerAfter.bytes)) return yield* Effect.fail(fail("SOURCE_CHANGED", "Proof audit runner changed during execution"))
  const report = Object.freeze({ schema_version: options.profile.schemaVersion, profile: options.profile.name, recorded_at: new Date().toISOString(),
    status: "EXACT_SOURCE_KERNEL_CHECKED", claim_ceiling: options.profile.claimCeiling,
    toolchain: { name: decoded.toolchain.name, version_output: versionText, source_commit: decoded.toolchain.source_commit,
      lean_binary_sha256: sha256(leanBytes.bytes), lean_path: lean, pin_path: decoded.toolchain.pin_path, pin_sha256: sha256(pin.bytes),
      resolved_by: options.lean === null ? "lake env which lean" : "explicit --lean", execution_binary: lean,
      lean_path_entries: [compiled, join(leanRoot, "src/lean/Std")] },
    compile_order: options.profile.sourceOrder, audited_sources: options.profile.auditedSources, source_records: sourceRecords, allowed_axioms: [...permittedAxioms].sort(),
    runner_source: { path: "src/hswm/effect-runtime/src/semantic-philosophy-proof-process.ts", sha256: sha256(runnerBefore.bytes) },
    auditor_interface: "ADDITIVE_PROFILE_EXTENSION_SUPERSEDES_PRIOR_PRIVATE_AUDITOR_INTERFACE_WITHOUT_MUTATING_HISTORICAL_RECEIPTS",
    statement_semantics_validated: false, new_dependencies_installed: false })
  yield* writeJson(join(options.output, "lean-verification.v1.json"), report)
  return `${JSON.stringify({ output: options.output, status: report.status, sources: sourceRecords.length, claimCeiling: report.claim_ceiling })}\n`
}).pipe(Effect.catchAll(error => Effect.fail(error)))

const usage = "Usage: semantic-philosophy-proof-process --output NEW_PRIVATE_DIRECTORY [--profile three-philosophies|integrated-hswm|operational-philosophy] [--lean ABSOLUTE_PATH]\n"
export const semanticPhilosophyProofCli = (argv: ReadonlyArray<string>) => Effect.gen(function* () {
  const options = yield* parse(argv, process.cwd())
  if (options === null) return usage
  return yield* runSemanticPhilosophyProof(options)
})
export const semanticPhilosophyProofMain = (argv: ReadonlyArray<string>) => {
  const environment = Object.fromEntries(Object.entries(process.env).flatMap(([key, value]) => value === undefined ? [] : [[key, value]]))
  const host = Layer.succeed(SemanticPhilosophyProofHost, { repository: resolve(dirname(fileURLToPath(import.meta.url)), "../../../.."), environment })
  return runArgvProcessMain({ program: argv => semanticPhilosophyProofCli(argv).pipe(Effect.provide(host)), refusalPrefix: "SEMANTIC_PHILOSOPHY_PROOF_REFUSED", describeFailure: error => `${error.code}: ${error.detail}` }, argv)
}
if (import.meta.main) process.exitCode = await semanticPhilosophyProofMain(process.argv.slice(2))
