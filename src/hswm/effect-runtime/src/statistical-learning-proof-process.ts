#!/usr/bin/env node
/**
 * Source-bound Lean kernel audit for the isolated finite statistical-learning
 * package.  It checks declared proof artifacts; it does not establish real
 * LLM performance, distributional premises, or HSWM efficacy.
 */
import { createHash } from "node:crypto"
import { dirname, isAbsolute, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { Context, Data, Effect, Layer } from "effect"
import { BoundedSubprocess } from "./effect-bounded-subprocess.js"
import { runArgvProcessMain } from "./effect-process-main.js"
import { PosixFileSystem } from "./effect-posix-filesystem.js"
import { parseTheoremAxioms } from "./semantic-philosophy-proof-process.js"

const encoder = new TextEncoder()
const decoder = new TextDecoder()
const sha256 = (value: Uint8Array): string => createHash("sha256").update(value).digest("hex")
const permittedAxioms = Object.freeze(["propext", "Quot.sound", "Classical.choice"] as const)
const modules = Object.freeze([
  { name: "HSWMLLMSemanticGraph", path: "formal/HSWMLLMSemanticGraph.lean", audit: false },
  { name: "HSWMStatisticalLearning.Concentration", path: "formal/statistical-learning/HSWMStatisticalLearning/Concentration.lean", audit: true },
  { name: "HSWMStatisticalLearning.Selection", path: "formal/statistical-learning/HSWMStatisticalLearning/Selection.lean", audit: true },
  { name: "HSWMStatisticalLearning.Integration", path: "formal/statistical-learning/HSWMStatisticalLearning/Integration.lean", audit: true },
  { name: "HSWMStatisticalLearning.CanonicalBridge", path: "formal/statistical-learning/HSWMStatisticalLearning/CanonicalBridge.lean", audit: true }
] as const)
interface LockedLakePackage { readonly name: string; readonly url: string; readonly revision: string; readonly inputRevision: string | null }

export class StatisticalLearningProofError extends Data.TaggedError("StatisticalLearningProofError")<{
  readonly code: "CLI_INVALID" | "PACKAGE_PIN_INVALID" | "TOOLCHAIN_MISMATCH" | "SOURCE_INVALID" | "COMPILER_FAILED" | "AXIOM_REJECTED" | "SOURCE_CHANGED"
  readonly detail: string
}> {}
const fail = (code: StatisticalLearningProofError["code"], detail: string) => new StatisticalLearningProofError({ code, detail })
export class StatisticalLearningProofHost extends Context.Tag("hswm/StatisticalLearningProofHost")<StatisticalLearningProofHost, {
  readonly repository: string
  readonly environment: Readonly<Record<string, string>>
}>() {}

interface Options { readonly output: string; readonly lean: string | null }
const parse = (argv: ReadonlyArray<string>, cwd: string): Effect.Effect<Options | null, StatisticalLearningProofError> => {
  if (argv.length === 1 && argv[0] === "--help") return Effect.succeed(null)
  if (argv.length !== 2 && argv.length !== 4) return Effect.fail(fail("CLI_INVALID", "Expected --output NEW_PRIVATE_DIRECTORY [--lean ABSOLUTE_PATH]"))
  const pairs = Array.from({ length: argv.length / 2 }, (_, index) => [argv[index * 2], argv[index * 2 + 1]] as const)
  const values = Object.fromEntries(pairs)
  if (pairs.some(([key, value]) => !["--output", "--lean"].includes(key ?? "") || !value || value.startsWith("--")) ||
      new Set(pairs.map(([key]) => key)).size !== pairs.length || typeof values["--output"] !== "string")
    return Effect.fail(fail("CLI_INVALID", "Invalid or duplicate CLI option"))
  const lean = values["--lean"]
  if (lean !== undefined && (!isAbsolute(lean) || lean.includes("\0"))) return Effect.fail(fail("CLI_INVALID", "--lean must be an absolute path"))
  return Effect.succeed({ output: resolve(cwd, values["--output"]), lean: lean ?? null })
}
const read = (path: string, operation: string) => PosixFileSystem.pipe(Effect.flatMap(fs => fs.readRegularBounded(path, { maximumBytes: 32 * 1024 * 1024, minimumBytes: 1, operation })))
const command = (argv: ReadonlyArray<string>, cwd: string, environment: Readonly<Record<string, string>>, stdin?: Uint8Array) =>
  BoundedSubprocess.pipe(Effect.flatMap(service => service.observe({ argv, cwd, environment, ...(stdin === undefined ? {} : { stdin }), timeoutMs: 300_000, maximumOutputBytes: 4 * 1024 * 1024, killProcessGroup: true })))
const successful = (label: string, effect: ReturnType<typeof command>) => effect.pipe(Effect.flatMap(result =>
  result.exitCode === 0 && !result.timedOut && !result.outputTruncated && result.launchError === null
    ? Effect.succeed(result) : Effect.fail(fail("COMPILER_FAILED", `${label} did not complete successfully`))))
const stripComments = (source: string): string => source.replace(/\/\-[\s\S]*?\-\//g, "").replace(/--[^\n]*/g, "")
const unsafeSource = (source: string): boolean => {
  const code = stripComments(source)
  return /\b(?:sorry|admit|native_decide)\b/.test(code) || /(^|\n)\s*(?:axiom|opaque|unsafe|meta)\b/.test(code) || /(^|\n)\s*set_option\s+(?!(?:linter\.unusedSimpArgs\s+false)\s*(?:\n|$))/.test(code)
}
const publicDeclarationNames = (source: string): ReadonlyArray<string> => Array.from(source.matchAll(/^\s*(?:theorem|lemma)\s+([A-Za-z_][A-Za-z0-9_']*)/gm), row => row[1] ?? "").filter(Boolean)
// These proof modules use one file-wide namespace stack.  Joining each
// declaration preserves nested `namespace Selection` theorem names.
const namespaceName = (source: string): string | null => {
  const parts = Array.from(source.matchAll(/^\s*namespace\s+([A-Za-z0-9_.]+)/gm), row => row[1] ?? "").filter(Boolean)
  return parts.length === 0 ? null : parts.join(".")
}
const oleanName = (name: string): string => `${name.replaceAll(".", "/")}.olean`

export const runStatisticalLearningProof = (options: Options) => Effect.gen(function* () {
  const fs = yield* PosixFileSystem
  const host = yield* StatisticalLearningProofHost
  const pkg = join(host.repository, "formal/statistical-learning")
  const manifestPath = join(pkg, "lake-manifest.json")
  const toolchainPath = join(pkg, "lean-toolchain")
  const lakefilePath = join(pkg, "lakefile.toml")
  const manifest = yield* read(manifestPath, "statistical-learning-manifest")
  const toolchain = yield* read(toolchainPath, "statistical-learning-toolchain")
  const lakefile = yield* read(lakefilePath, "statistical-learning-lakefile")
  const historicalPinPath = join(host.repository, "_research/llm_semantic_graph_v1/lean-verification.v1.json")
  const historicalPin = yield* read(historicalPinPath, "statistical-learning-historical-lean-pin")
  const manifestJson = yield* Effect.try({ try: () => JSON.parse(decoder.decode(manifest.bytes)) as unknown, catch: () => fail("PACKAGE_PIN_INVALID", "lake-manifest.json is not JSON") })
  const mathlib = typeof manifestJson === "object" && manifestJson !== null && "packages" in manifestJson && Array.isArray(manifestJson.packages)
    ? manifestJson.packages.find((item): item is Record<string, unknown> => typeof item === "object" && item !== null && (item as Record<string, unknown>)["name"] === "mathlib") : undefined
  if (mathlib === undefined || typeof mathlib["rev"] !== "string" || !/^[0-9a-f]{40}$/.test(mathlib["rev"])) return yield* Effect.fail(fail("PACKAGE_PIN_INVALID", "Mathlib must have a 40-hex locked revision in lake-manifest.json"))
  const lockedPackages: ReadonlyArray<LockedLakePackage> = typeof manifestJson === "object" && manifestJson !== null && "packages" in manifestJson && Array.isArray(manifestJson.packages)
    ? manifestJson.packages.map((item): LockedLakePackage | null => {
      if (typeof item !== "object" || item === null) return null
      const record = item as Record<string, unknown>
      return typeof record["name"] === "string" && /^[A-Za-z0-9_-]+$/.test(record["name"]) && typeof record["url"] === "string" && record["url"].startsWith("https://github.com/") && typeof record["rev"] === "string" && /^[0-9a-f]{40}$/.test(record["rev"])
        ? Object.freeze({ name: record["name"], url: record["url"], revision: record["rev"], inputRevision: typeof record["inputRev"] === "string" ? record["inputRev"] : null }) : null
    }).filter((item): item is LockedLakePackage => item !== null) : []
  if (lockedPackages.length === 0 || lockedPackages.length !== (typeof manifestJson === "object" && manifestJson !== null && "packages" in manifestJson && Array.isArray(manifestJson.packages) ? manifestJson.packages.length : 0)) return yield* Effect.fail(fail("PACKAGE_PIN_INVALID", "Every manifest package needs a safe name, HTTPS GitHub URL, and exact revision"))
  const historical = yield* Effect.try({ try: () => JSON.parse(decoder.decode(historicalPin.bytes)) as unknown, catch: () => fail("PACKAGE_PIN_INVALID", "Historical Lean pin is not JSON") })
  const historicalToolchain = typeof historical === "object" && historical !== null && "toolchain" in historical && typeof historical.toolchain === "object" && historical.toolchain !== null ? historical.toolchain as Record<string, unknown> : null
  const historicalLeanHash = historicalToolchain?.["lean_binary_sha256"]
  const historicalVersion = historicalToolchain?.["version_output"]
  if (typeof historicalLeanHash !== "string" || !/^[0-9a-f]{64}$/.test(historicalLeanHash) || typeof historicalVersion !== "string") return yield* Effect.fail(fail("PACKAGE_PIN_INVALID", "Historical Lean receipt lacks exact binary/version pins"))
  if (decoder.decode(toolchain.bytes).trim() !== "leanprover/lean4:v4.32.1") return yield* Effect.fail(fail("PACKAGE_PIN_INVALID", "The isolated package must pin Lean v4.32.1"))
  yield* fs.makeDirectory(dirname(options.output), { recursive: true, mode: 0o700, operation: "statistical-learning-parent" })
  yield* fs.makeDirectory(options.output, { mode: 0o700, operation: "statistical-learning-output" })
  const compiled = join(options.output, "olean")
  yield* fs.makeDirectory(compiled, { mode: 0o700, operation: "statistical-learning-olean" })
  const resolved = yield* successful("resolve package Lean", command(["lake", "env", "which", "lean"], pkg, host.environment))
  const resolvedLean = decoder.decode(resolved.stdout).trim()
  const lean = options.lean ?? resolvedLean
  if (!isAbsolute(lean) || lean.includes("\n") || (options.lean !== null && lean !== resolvedLean)) return yield* Effect.fail(fail("TOOLCHAIN_MISMATCH", "--lean must equal the isolated package resolved Lean binary"))
  const leanIdentity = yield* fs.identity(lean, "statistical-learning-lean")
  if (leanIdentity.kind !== "FILE") return yield* Effect.fail(fail("TOOLCHAIN_MISMATCH", "Resolved Lean is not a regular file"))
  const leanBytes = yield* read(lean, "statistical-learning-lean-hash")
  const version = yield* successful("Lean version", command([lean, "--version"], pkg, host.environment))
  const versionText = decoder.decode(version.stdout).trim()
  if (versionText !== historicalVersion || sha256(leanBytes.bytes) !== historicalLeanHash) return yield* Effect.fail(fail("TOOLCHAIN_MISMATCH", "Resolved Lean does not match the prior exact binary/version pin"))
  const lakePath = yield* successful("resolve package LEAN_PATH", command(["lake", "env", "printenv", "LEAN_PATH"], pkg, host.environment))
  const packageBuild = join(pkg, ".lake/build/lib/lean")
  const leanRoot = resolve(dirname(lean), "..")
  const dependencyEntries = decoder.decode(lakePath.stdout).trim().split(":").filter(Boolean).map(entry => resolve(pkg, entry)).filter(entry => entry !== packageBuild)
  if (!dependencyEntries.some(entry => entry.endsWith("/.lake/packages/mathlib/.lake/build/lib/lean"))) return yield* Effect.fail(fail("PACKAGE_PIN_INVALID", "Resolved package LEAN_PATH lacks pinned Mathlib build output"))
  if (dependencyEntries.some(entry => entry !== join(leanRoot, "lib/lean") && !entry.startsWith(`${join(pkg, ".lake/packages")}/`))) return yield* Effect.fail(fail("PACKAGE_PIN_INVALID", "Package LEAN_PATH contains an undeclared non-package dependency"))
  const freshEnvironment = Object.freeze({ PATH: host.environment["PATH"] ?? "/usr/bin:/bin", LEAN_PATH: [compiled, ...dependencyEntries].join(":") })
  const runnerPath = join(host.repository, "src/hswm/effect-runtime/src/statistical-learning-proof-process.ts")
  const parserPath = join(host.repository, "src/hswm/effect-runtime/src/semantic-philosophy-proof-process.ts")
  const runnerBefore = yield* read(runnerPath, "statistical-learning-runner-before")
  const parserBefore = yield* read(parserPath, "statistical-learning-parser-before")
  const actualPackageRevisions = new Map<string, string>()
  for (const dependency of lockedPackages) {
    const checkout = yield* successful(`resolve ${dependency.name} checkout`, command(["git", "-C", join(pkg, ".lake/packages", dependency.name), "rev-parse", "HEAD"], pkg, host.environment))
    const revision = decoder.decode(checkout.stdout).trim()
    if (revision !== dependency.revision) return yield* Effect.fail(fail("PACKAGE_PIN_INVALID", `${dependency.name} checkout HEAD differs from lake-manifest lock`))
    const clean = yield* successful(`inspect ${dependency.name} worktree`, command(["git", "-C", join(pkg, ".lake/packages", dependency.name), "status", "--porcelain", "--untracked-files=all"], pkg, host.environment))
    if (decoder.decode(clean.stdout).trim().length !== 0) return yield* Effect.fail(fail("PACKAGE_PIN_INVALID", `${dependency.name} dependency worktree is not clean`))
    actualPackageRevisions.set(dependency.name, revision)
  }
  const bound = new Map<string, string>()
  const records: Array<Record<string, unknown>> = []
  for (const module of modules) {
    const sourcePath = join(host.repository, module.path)
    const sourceRoot = module.path.startsWith("formal/statistical-learning/") ? pkg : join(host.repository, "formal")
    const before = yield* read(sourcePath, "statistical-learning-source-before")
    bound.set(module.path, sha256(before.bytes))
    const source = decoder.decode(before.bytes)
    if (unsafeSource(source)) return yield* Effect.fail(fail("SOURCE_INVALID", `Forbidden proof shortcut in ${module.path}`))
    const output = join(compiled, oleanName(module.name))
    yield* fs.makeDirectory(dirname(output), { recursive: true, mode: 0o700, operation: "statistical-learning-module-olean" })
    const compilation = yield* successful(`compile ${module.name}`, command([lean, "--trust=0", `--root=${sourceRoot}`, "-o", output, sourcePath], pkg, freshEnvironment))
    const after = yield* read(sourcePath, "statistical-learning-source-after")
    if (sha256(before.bytes) !== sha256(after.bytes)) return yield* Effect.fail(fail("SOURCE_CHANGED", `Source changed while compiling: ${module.path}`))
    const names = module.audit ? publicDeclarationNames(source) : []
    const namespace = module.audit ? namespaceName(source) : null
    if (module.audit && (namespace === null || names.length === 0)) return yield* Effect.fail(fail("SOURCE_INVALID", `Audited module lacks namespace/theorem: ${module.path}`))
    const qualified = names.map(name => `${namespace}.${name}`)
    const audit = module.audit ? yield* successful(`audit ${module.name}`, command([lean, "--trust=0", "--stdin"], pkg, freshEnvironment, encoder.encode(`${source}\n${qualified.map(name => `#print axioms ${name}`).join("\n")}\n`))) : null
    const theoremAxioms = audit === null ? [] : parseTheoremAxioms(decoder.decode(audit.stdout), qualified)
    if (theoremAxioms === null) return yield* Effect.fail(fail("AXIOM_REJECTED", `Incomplete theorem axiom output: ${module.path}`))
    const axioms = theoremAxioms.flatMap(row => row.axioms).filter((name, index, all) => all.indexOf(name) === index).sort()
    const rejected = axioms.filter(axiom => !permittedAxioms.includes(axiom as typeof permittedAxioms[number]))
    if (rejected.length > 0) return yield* Effect.fail(fail("AXIOM_REJECTED", `Unpermitted axiom(s) in ${module.path}: ${rejected.join(", ")}`))
    records.push(Object.freeze({ path: module.path, module: module.name, sha256: sha256(before.bytes), byte_length: before.bytes.byteLength, compiler_stdout_sha256: sha256(compilation.stdout), compiler_stderr_sha256: sha256(compilation.stderr), named_declarations: qualified, declaration_axioms: theoremAxioms, axioms, audit_stdout_sha256: audit === null ? null : sha256(audit.stdout), audit_stderr_sha256: audit === null ? null : sha256(audit.stderr) }))
  }
  for (const module of modules) { const current = yield* read(join(host.repository, module.path), "statistical-learning-final-rebind"); if (sha256(current.bytes) !== bound.get(module.path)) return yield* Effect.fail(fail("SOURCE_CHANGED", `Source changed before report: ${module.path}`)) }
  const runnerAfter = yield* read(runnerPath, "statistical-learning-runner-after")
  const parserAfter = yield* read(parserPath, "statistical-learning-parser-after")
  const manifestAfter = yield* read(manifestPath, "statistical-learning-manifest-final")
  const toolchainAfter = yield* read(toolchainPath, "statistical-learning-toolchain-final")
  const lakefileAfter = yield* read(lakefilePath, "statistical-learning-lakefile-final")
  if (sha256(runnerBefore.bytes) !== sha256(runnerAfter.bytes)) return yield* Effect.fail(fail("SOURCE_CHANGED", "Audit runner changed during execution"))
  for (const dependency of lockedPackages) {
    const checkout = yield* successful(`rebind ${dependency.name} checkout`, command(["git", "-C", join(pkg, ".lake/packages", dependency.name), "rev-parse", "HEAD"], pkg, host.environment))
    if (decoder.decode(checkout.stdout).trim() !== actualPackageRevisions.get(dependency.name)) return yield* Effect.fail(fail("SOURCE_CHANGED", `${dependency.name} checkout changed during execution`))
    const clean = yield* successful(`rebind ${dependency.name} worktree`, command(["git", "-C", join(pkg, ".lake/packages", dependency.name), "status", "--porcelain", "--untracked-files=all"], pkg, host.environment))
    if (decoder.decode(clean.stdout).trim().length !== 0) return yield* Effect.fail(fail("SOURCE_CHANGED", `${dependency.name} dependency worktree became dirty during execution`))
  }
  if (sha256(parserBefore.bytes) !== sha256(parserAfter.bytes) || sha256(manifest.bytes) !== sha256(manifestAfter.bytes) || sha256(toolchain.bytes) !== sha256(toolchainAfter.bytes) || sha256(lakefile.bytes) !== sha256(lakefileAfter.bytes)) return yield* Effect.fail(fail("SOURCE_CHANGED", "Auditor parser or package lock/configuration changed during execution"))
  const report = Object.freeze({ schema_version: "hswm-t1-statistical-learning-lean-verification/v1", recorded_at: new Date().toISOString(), status: "EXACT_SOURCE_KERNEL_CHECKED", claim_ceiling: "FINITE_IID_BOUNDED_LOSS_CONCENTRATION_UNDER_DECLARED_PREMISES_NOT_REAL_LLM_OR_HSWM_EFFICACY", statement_semantics_validated: false, auditor_installs_dependencies: false, toolchain: { package_path: "formal/statistical-learning", pin_path: "formal/statistical-learning/lean-toolchain", pin_sha256: sha256(toolchain.bytes), version_output: versionText, lean_binary_sha256: sha256(leanBytes.bytes), historical_exact_binary_pin: { path: "_research/llm_semantic_graph_v1/lean-verification.v1.json", sha256: sha256(historicalPin.bytes), lean_binary_sha256: historicalLeanHash }, resolved_by: options.lean === null ? "lake env which lean" : "explicit --lean equal to lake env which lean" }, dependency_boundary: { lake_manifest_path: "formal/statistical-learning/lake-manifest.json", lake_manifest_sha256: sha256(manifest.bytes), lakefile_path: "formal/statistical-learning/lakefile.toml", lakefile_sha256: sha256(lakefile.bytes), dependency_worktrees_clean_before_and_after: true, locked_packages: lockedPackages.map(dependency => Object.freeze({ name: dependency.name, url: dependency.url, revision: dependency.revision, checkout_head: actualPackageRevisions.get(dependency.name), input_revision: dependency.inputRevision })), trusted_import_cache_entries: dependencyEntries.map(entry => entry.startsWith(host.repository) ? entry.slice(host.repository.length + 1) : "EXTERNAL_LEAN_TOOLCHAIN_PATH"), note: "Pinned compiled imports are a transitive trust boundary; theorem axiom output does not independently re-audit dependency source." }, compile_order: modules.map(module => module.name), audited_modules: modules.filter(module => module.audit).map(module => module.name), allowed_axioms: [...permittedAxioms].sort(), source_records: records, runner_source: { path: "src/hswm/effect-runtime/src/statistical-learning-proof-process.ts", sha256: sha256(runnerBefore.bytes) }, parser_source: { path: "src/hswm/effect-runtime/src/semantic-philosophy-proof-process.ts", sha256: sha256(parserBefore.bytes) }, receipt_visibility: "PRIVATE_RAW_RECEIPT; any public projection must omit absolute host paths", auditor_interface: "ADDITIVE_ISOLATED_STATISTICAL_LEARNING_AUDITOR; HISTORICAL_RECEIPTS_UNMODIFIED" })
  yield* fs.writeExclusive(join(options.output, "lean-verification.v1.json"), encoder.encode(`${JSON.stringify(report, null, 2)}\n`), { mode: 0o600, sync: true, operation: "statistical-learning-report" })
  return `${JSON.stringify({ output: options.output, status: report.status, sources: records.length, claimCeiling: report.claim_ceiling })}\n`
})
const usage = "Usage: statistical-learning-proof-process --output NEW_PRIVATE_DIRECTORY [--lean ABSOLUTE_PATH]\n"
export const statisticalLearningProofCli = (argv: ReadonlyArray<string>) => Effect.gen(function* () { const options = yield* parse(argv, process.cwd()); return options === null ? usage : yield* runStatisticalLearningProof(options) })
export const statisticalLearningProofMain = (argv: ReadonlyArray<string>) => {
  const environment = Object.fromEntries(Object.entries(process.env).flatMap(([key, value]) => value === undefined ? [] : [[key, value]]))
  const host = Layer.succeed(StatisticalLearningProofHost, { repository: resolve(dirname(fileURLToPath(import.meta.url)), "../../../.."), environment })
  return runArgvProcessMain({ program: args => statisticalLearningProofCli(args).pipe(Effect.provide(host)), refusalPrefix: "STATISTICAL_LEARNING_PROOF_REFUSED", describeFailure: error => `${error.code}: ${error.detail}` }, argv)
}
if (import.meta.main) process.exitCode = await statisticalLearningProofMain(process.argv.slice(2))
