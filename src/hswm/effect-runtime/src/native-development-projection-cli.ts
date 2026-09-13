import { join, resolve } from "node:path"
import { parseArgs } from "node:util"
import { Effect, Either } from "effect"
import { PosixFileSystem } from "./effect-posix-filesystem.js"
import { BoundedSubprocess } from "./effect-bounded-subprocess.js"
import { refuse, type ProcessReply } from "./effect-process-main.js"
import { decodeGeneralJsonBytes } from "./general-json-domain.js"
import { kgSha256 } from "./native-kg-bundle-domain.js"
import { DEVELOPMENT_WORK_CONTRACT } from "./native-development-work-projection.js"
import { DEVELOPMENT_DAY_CONTRACT } from "./native-development-day-projection.js"
import { FRONTIER_LEARNING_CONTRACT } from "./native-frontier-learning-projection.js"
import { applyReviewedNativeDevelopmentProjection, compileNativeDevelopmentProjection, exportValidatedNativeDevelopmentProjection, NativeDevelopmentProjectionError, type NativeDevelopmentProjectionPublisher, type ProjectionContract } from "./native-development-projection-domain.js"
import { preloadDevelopmentProjectionSources } from "./native-development-projection-io.js"
import { makeNativeDevelopmentProjectionPublisher, parseNativeDevelopmentProjectionSourceConfig } from "./native-development-projection-publisher.js"

const max = 16 * 1024 * 1024
const defaultRoot = resolve(import.meta.dirname, "..", "..", "..", "..")
const shapesPath = "schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl"
const usage = "usage: hswm-development-projection <work|day|frontier> [--repo-root ROOT] [--ontology PATH] [--export-dir NEW_DIRECTORY] [--additional-shapes PATH] [--source-config PATH] [--apply]"
const contracts: Readonly<Record<string, ProjectionContract>> = Object.freeze({ work: DEVELOPMENT_WORK_CONTRACT, day: DEVELOPMENT_DAY_CONTRACT, frontier: FRONTIER_LEARNING_CONTRACT })
const reviewed: Readonly<Record<string, string>> = Object.freeze({ work: "737324f0a9b64d061d7155c207a62877a122c1818b2a56460b54fe6e7050ca64", day: "931f6a7bfe9fa60fc8c543c08d6b293d8e0d3c313f0820dc6effea66481acfd7", frontier: "47fe62066a03f7b8556e9d3f5b45cc583d75ab6696d515a59088cd37d462159a" })
const defaults: Readonly<Record<string, string>> = Object.freeze({ work: "ontology/identity/hswm_core/HSWM_ADAPTIVE_DEVELOPMENT_WORK_ONTOLOGY.v1.json", day: "ontology/identity/hswm_core/HSWM_DEVELOPMENT_DAY_2026-09-08_ONTOLOGY.v1.json", frontier: "ontology/identity/hswm_core/HSWM_FRONTIER_LEARNING_THEORY_ONTOLOGY.v1.json" })
const read = (path: string, operation: string) => Effect.gen(function* () { const fs = yield* PosixFileSystem; return (yield* fs.readRegularBounded(path, { maximumBytes: max, minimumBytes: 1, operation }).pipe(Effect.mapError(error => refuse(error.detail)))).bytes })
const bindings = (value: unknown): readonly string[] | undefined => {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return undefined
  const rows = (value as Readonly<Record<string, unknown>>)["artifact_bindings"]
  if (!Array.isArray(rows) || rows.length === 0) return undefined
  const paths: string[] = []
  for (const row of rows) {
    if (typeof row !== "object" || row === null || Array.isArray(row) || typeof (row as Readonly<Record<string, unknown>>)["path"] !== "string") return undefined
    paths.push((row as Readonly<Record<string, unknown>>)["path"] as string)
  }
  return Object.freeze(paths)
}

/** Public argv surface. Applying requires an injected bounded publisher; no live gateway is embedded here. */
export const runNativeDevelopmentProjectionCli = (argv: readonly string[], publisher?: NativeDevelopmentProjectionPublisher): Effect.Effect<ProcessReply, ReturnType<typeof refuse>, PosixFileSystem | BoundedSubprocess> => Effect.gen(function* () {
  const parsed = yield* Effect.try({ try: () => parseArgs({ args: [...argv], allowPositionals: true, strict: true, options: { "repo-root": { type: "string" }, ontology: { type: "string" }, "export-dir": { type: "string" }, "additional-shapes": { type: "string" }, "source-config": { type: "string" }, apply: { type: "boolean" }, help: { type: "boolean" } } }), catch: () => refuse(usage) })
  if (parsed.values.help) return { stdout: `${usage}\n`, exitCode: 0 }
  const name = parsed.positionals[0]
  if (parsed.positionals.length !== 1 || name === undefined) return yield* Effect.fail(refuse(usage))
  const contract = contracts[name]
  if (contract === undefined || (parsed.values.apply !== true && parsed.values["source-config"] !== undefined)) return yield* Effect.fail(refuse(usage))
  if (parsed.values.apply === true && parsed.values["source-config"] === undefined) return yield* Effect.fail(refuse("--apply requires --source-config"))
  const root = resolve(parsed.values["repo-root"] ?? defaultRoot), ontology = resolve(root, parsed.values.ontology ?? defaults[name]!)
  const raw = yield* read(ontology, "development projection ontology")
  const decoded = decodeGeneralJsonBytes(raw, { maximumBytes: max, maximumDepth: 32 })
  if (Either.isLeft(decoded)) return yield* Effect.fail(refuse("ontology is not JSON"))
  const paths = bindings(decoded.right)
  if (paths === undefined) return yield* Effect.fail(refuse("artifact_bindings must be a non-empty list"))
  const sources = yield* preloadDevelopmentProjectionSources(root, { currentPaths: contract.bindingOrigin === "current" ? paths : [], historical: contract.bindingOrigin === "historical" && contract.sourceCommit !== undefined ? paths.map(path => ({ commit: contract.sourceCommit!, path })) : [] }).pipe(Effect.mapError(error => refuse(error.detail)))
  const compiled = compileNativeDevelopmentProjection(decoded.right, raw, contract, sources)
  if (Either.isLeft(compiled)) return yield* Effect.fail(refuse(compiled.left.detail))
  if (parsed.values["export-dir"] !== undefined) {
    const directory = resolve(parsed.values["export-dir"])
    const generic = yield* read(join(root, shapesPath), "development projection generic SHACL shapes")
    const extra = parsed.values["additional-shapes"] === undefined ? undefined : yield* read(resolve(parsed.values["additional-shapes"]), "development projection additional SHACL shapes")
    const fs = yield* PosixFileSystem
    yield* fs.makeDirectory(directory, { mode: 0o755, operation: "development projection new export directory" }).pipe(Effect.mapError(error => refuse(error.detail)))
    const writer = { write: (name: string, bytes: Uint8Array) => fs.writeExclusive(join(directory, name), bytes, { mode: 0o644, sync: true, operation: "development projection export artifact" }).pipe(Effect.mapError(error => new NativeDevelopmentProjectionError({ detail: error.detail }))) }
    const report = yield* exportValidatedNativeDevelopmentProjection(compiled.right, extra === undefined ? generic : new Uint8Array([...generic, 10, ...extra]), writer).pipe(Effect.mapError(error => refuse(error.detail)))
    yield* fs.syncDirectory(directory, "development projection export sync").pipe(Effect.mapError(error => refuse(error.detail)))
    if (!report.conforms) return { stdout: `${JSON.stringify(report)}\n`, exitCode: 1 }
  }
  if (parsed.values.apply === true) {
    const sourceText = yield* read(resolve(parsed.values["source-config"]!), "development projection source config")
    const config = yield* Effect.try({ try: () => new TextDecoder("utf-8", { fatal: true }).decode(sourceText), catch: () => refuse("source config must be UTF-8") })
    const configured = yield* parseNativeDevelopmentProjectionSourceConfig(config).pipe(Effect.mapError(error => refuse(error.detail)))
    yield* applyReviewedNativeDevelopmentProjection(decoded.right, raw, reviewed[name]!, contract, sources, publisher ?? makeNativeDevelopmentProjectionPublisher(configured)).pipe(Effect.mapError(error => refuse(error.detail)))
    return { stdout: `${JSON.stringify({ status: "APPLIED_OR_VERIFIED_EXACT_PROJECTION", projection_sha256: kgSha256(raw) })}\n`, exitCode: 0 }
  }
  return { stdout: `${JSON.stringify({ status: "VALIDATED_ONLY_NOT_PUBLISHED", projection_sha256: kgSha256(raw), new_nodes: compiled.right.descriptor["nodeCount"], relations: compiled.right.descriptor["relationCount"] })}\n`, exitCode: 0 }
}).pipe(Effect.mapError(error => error._tag === "ProcessRefusal" ? error : refuse(error.detail)))
