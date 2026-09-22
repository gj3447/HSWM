/** Read-only workspace shell: fixed navigation, Git-tracked inventory and native KG engines. */
import { createHash } from "node:crypto"
import { isAbsolute, relative, resolve, sep } from "node:path"
import { parseArgs } from "node:util"
import { Effect, Either } from "effect"
import { BoundedSubprocess, PosixFileSystem } from "./effect-posix-services.js"
import { refuse, type ProcessReply } from "./effect-process-main.js"
import { compileKgBundle } from "./native-kg-bundle-domain.js"
import { queryKgBundle, validateKgShacl } from "./native-kg-standards.js"
import { inspectWorkspaceBundle, summarizeWorkspaceBundles, type WorkspaceBundleSummary } from "./workspace-catalog-domain.js"
import { decodeWorkspaceManifest, type WorkspaceEntry } from "./workspace-manifest-domain.js"

export const WORKSPACE_MANIFEST_PATH = "ontology/workspace/HSWM_WORKSPACE.v1.json"
const usage = "hswm-workspace <status|doctor|inventory|show ID|bindings ID|validate ID|query ID QUERY> [--checkout PATH] [--uid UID] [--details]"
const sha = (bytes: Uint8Array) => createHash("sha256").update(bytes).digest("hex")
const reply = (value: unknown, exitCode = 0): ProcessReply => ({ stdout: `${JSON.stringify(value, null, 2)}\n`, exitCode })
const parseJson = (bytes: Uint8Array) => Effect.try({ try: () => JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)) as unknown, catch: () => refuse("invalid UTF-8 JSON") })
const contained = (checkout: string, path: string) => {
  const rel = relative(checkout, path)
  return rel !== ".." && !rel.startsWith(`..${sep}`) && !isAbsolute(rel)
}
const read = (checkout: string, path: string, maximumBytes = 16 * 1024 * 1024) => Effect.gen(function* () {
  const fs = yield* PosixFileSystem
  if (isAbsolute(path) || path.includes("\\") || path.split("/").some(p => p === ".." || p === "." || p === ""))
    return yield* Effect.fail(refuse("workspace input must be a relative repository path"))
  const target = resolve(checkout, path)
  const actual = yield* fs.realpath(target, "workspace-contained-read")
  if (!contained(checkout, actual)) return yield* Effect.fail(refuse("workspace input resolves outside checkout"))
  return (yield* fs.readRegularBounded(target, { maximumBytes, minimumBytes: 1, operation: "workspace-read" })).bytes
})
const git = (checkout: string, args: readonly string[]) => Effect.gen(function* () {
  const subprocess = yield* BoundedSubprocess
  const result = yield* subprocess.observe({ argv: ["git", "-C", checkout, ...args], cwd: checkout,
    environment: { PATH: process.env["PATH"] ?? "/usr/bin:/bin" }, timeoutMs: 20_000, maximumOutputBytes: 8 * 1024 * 1024 })
  if (result.exitCode !== 0 || result.timedOut || result.outputTruncated || result.launchError !== null)
    return yield* Effect.fail(refuse("bounded Git inventory unavailable"))
  return new TextDecoder().decode(result.stdout)
})
const inspect = (checkout: string, path: string) => Effect.gen(function* () {
  const result = inspectWorkspaceBundle({ path, bytes: yield* read(checkout, path) })
  if (Either.isLeft(result)) return yield* Effect.fail(refuse(result.left.message))
  return result.right
})
const bindings = (checkout: string, item: WorkspaceBundleSummary, tracked: ReadonlySet<string>) => Effect.forEach(item.bindings, binding => Effect.gen(function* () {
  if (!tracked.has(binding.path)) return { ...binding, actualSha256: null, status: "NOT_TRACKED_NOT_READ" }
  if (binding.sha256 === null) return { ...binding, actualSha256: null, status: "NO_EXPECTED_DIGEST" }
  return yield* read(checkout, binding.path).pipe(
    Effect.map(bytes => ({ ...binding, actualSha256: sha(bytes), status: sha(bytes) === binding.sha256 ? "MATCH" : "WORKTREE_DIFFERS" })),
    Effect.catchAll(() => Effect.succeed({ ...binding, actualSha256: null, status: "UNAVAILABLE" })),
  )
}), { concurrency: 8 })
const countStatuses = (rows: readonly { readonly status: string }[]) => Object.fromEntries([...new Set(rows.map(r => r.status))].sort().map(s => [s, rows.filter(r => r.status === s).length]))

export const runWorkspaceCli = (argv: readonly string[]) => Effect.gen(function* () {
  const parsed = yield* Effect.try({ try: () => parseArgs({ args: [...argv], allowPositionals: true, strict: true,
    options: { checkout: { type: "string" }, uid: { type: "string" }, details: { type: "boolean" }, help: { type: "boolean" } } }), catch: () => refuse(usage) })
  if (parsed.values.help) return { stdout: `${usage}\nRead-only; no model call, install, database write or workflow execution.\n`, exitCode: 0 }
  const [command, id, queryId] = parsed.positionals
  if (!command || !["status", "doctor", "inventory", "show", "bindings", "validate", "query"].includes(command)) return yield* Effect.fail(refuse(usage))
  const expected = command === "query" ? 3 : ["show", "bindings", "validate"].includes(command) ? 2 : 1
  if (parsed.positionals.length !== expected || (command !== "inventory" && parsed.values.uid !== undefined) || (command !== "inventory" && parsed.values.details)) return yield* Effect.fail(refuse(usage))
  const fs = yield* PosixFileSystem
  const checkout = yield* fs.realpath(resolve(parsed.values.checkout ?? process.cwd()), "workspace-checkout")
  const decoded = decodeWorkspaceManifest(yield* parseJson(yield* read(checkout, WORKSPACE_MANIFEST_PATH, 1024 * 1024)))
  if (Either.isLeft(decoded)) return yield* Effect.fail(refuse(decoded.left.message))
  const manifest = decoded.right
  const tracked = new Set((yield* git(checkout, ["ls-files", "-z"])).split("\0").filter(Boolean))
  const base = { schema_version: "hswm-workspace-observation/v1", scope: "READ_ONLY_WORKTREE_OBSERVATION", claim_ceiling: "NAVIGATION_AND_ENGINEERING_NOT_HSWM_EFFICACY", manifest: WORKSPACE_MANIFEST_PATH }
  if (command === "status") return reply({ ...base, entries: manifest.entries, workflows: manifest.workflows })
  if (command === "inventory") {
    const paths = [...tracked].filter(p => p.startsWith("ontology/") && p.endsWith(".json")).sort()
    if (paths.length > 4096) return yield* Effect.fail(refuse("ontology inventory exceeds 4096 files"))
    const observations = yield* Effect.forEach(paths, path => inspect(checkout, path).pipe(
      Effect.map(item => ({ path, item, error: null as string | null })),
      Effect.catchAll(error => Effect.succeed({ path, item: null, error: error._tag === "ProcessRefusal" ? error.detail : "unavailable or non-regular source" })),
    ), { concurrency: 8 })
    const items = observations.flatMap(o => o.item === null ? [] : [o.item])
    if (parsed.values.uid !== undefined) return reply({ ...base, uid: parsed.values.uid,
      occurrences: items.filter(b => b.nodeUids.includes(parsed.values.uid!)).map(b => ({ path: b.path, bundleUid: b.bundleUid, sha256: b.sha256 })),
      interpretation: "Occurrences remain scoped to source bytes; no UID merge or owner selection." })
    return reply({ ...base, trackedOntologyJson: paths.length, summary: summarizeWorkspaceBundles(items),
      errors: observations.filter(o => o.error !== null).map(o => ({ path: o.path, error: o.error })),
      ...(parsed.values.details ? { bundles: items } : {}),
      binding_note: "Inventory does not revalidate historical bindings. Use bindings ID for a worktree comparison, not a historical integrity verdict." })
  }
  if (command === "doctor") {
    const packageValue = yield* parseJson(yield* read(checkout, "src/hswm/effect-runtime/package.json", 1024 * 1024))
    const pkg = packageValue as { engines?: { node?: string }; bin?: Record<string, string> }
    const paths = [...new Set(manifest.entries.flatMap(e => [e.bundle, e.document, ...e.queries.map(q => q.path), ...e.shapes]))].sort()
    const checks = yield* Effect.forEach(paths, path => read(checkout, path).pipe(Effect.map(bytes => ({ path, status: "AVAILABLE", sha256: sha(bytes) })), Effect.catchAll(() => Effect.succeed({ path, status: "UNAVAILABLE", sha256: null }))), { concurrency: 8 })
    const bins = yield* Effect.forEach(Object.entries(pkg.bin ?? {}), ([name, target]) => Effect.gen(function* () {
      const wrapper = yield* fs.identity(resolve(checkout, "src/hswm/effect-runtime/bin", name), "workspace-launcher").pipe(Effect.map(x => x.kind === "FILE"), Effect.catchAll(() => Effect.succeed(false)))
      const built = yield* fs.identity(resolve(checkout, "src/hswm/effect-runtime", target), "workspace-dist").pipe(Effect.map(x => x.kind === "FILE"), Effect.catchAll(() => Effect.succeed(false)))
      return { name, surface: wrapper ? "CHECKOUT_AND_PACKAGE" : "PACKAGE_ONLY", built }
    }), { concurrency: 8 })
    return reply({ ...base, status: checks.every(c => c.status === "AVAILABLE") ? "READY_WITH_DECLARED_LIMITS" : "MISSING_ENTRYPOINTS",
      node: { declared: pkg.engines?.node ?? null, observed: process.versions.node, exactMatch: pkg.engines?.node === process.versions.node },
      entrypoints: checks, packageLaunchers: bins,
      workspaceLauncher: "CHECKOUT_ONLY; package registration not changed", buildNote: "Built-file presence is not build freshness. Run the native build after source changes.",
      sourceOnlyEntries: manifest.entries.filter(e => e.projection_profile === "SOURCE_ONLY").map(e => ({ id: e.id, reason: e.projection_reason })),
      historicalNote: "No historical source pin is rewritten, and no binding integrity follows from path availability." }, checks.some(c => c.status !== "AVAILABLE") ? 1 : 0)
  }
  const entry: WorkspaceEntry | undefined = manifest.entries.find(e => e.id === id)
  if (!entry) return yield* Effect.fail(refuse("unknown workspace ID; use status"))
  const item = yield* inspect(checkout, entry.bundle)
  if (item === null) return yield* Effect.fail(refuse("workspace entry does not reference a bundle"))
  if (command === "show") return reply({ ...base, entry, bundle: item })
  const rows = yield* bindings(checkout, item, tracked)
  if (command === "bindings") return reply({ ...base, id, sourceCut: item.sourceCut, reading: entry.reading, summary: countStatuses(rows), rows,
    interpretation: "WORKTREE_DIFFERS or unavailable does not invalidate a frozen snapshot. Historical reconstruction needs its pinned Git source." })
  if (entry.projection_profile === "SOURCE_ONLY") return reply({ ...base, id, status: "SOURCE_ONLY_NOT_NATIVE_V2",
    reason: entry.projection_reason, bindingSummary: countStatuses(rows),
    interpretation: "This historical format remains available through show, bindings and inventory; no structural conformance is asserted." }, 2)
  const bundleBytes = yield* read(checkout, entry.bundle)
  if (sha(bundleBytes) !== item.sha256) return yield* Effect.fail(refuse("bundle changed during observation"))
  const projection = yield* compileKgBundle([{ sourceId: entry.id, rawBytes: bundleBytes }], "v2")
  if (command === "query") {
    const query = entry.queries.find(q => q.id === queryId)
    if (!query) return yield* Effect.fail(refuse("unknown query alias; use show ID"))
    const result = yield* queryKgBundle(projection, new TextDecoder().decode(yield* read(checkout, query.path, 65536)))
    return reply({ ...base, id, bundleSha256: item.sha256, query: query.id, bindingSummary: countStatuses(rows), result })
  }
  const shapes = yield* Effect.forEach(entry.shapes, path => Effect.gen(function* () {
    const result = yield* validateKgShacl(projection, yield* read(checkout, path))
    return { path, ...result }
  }))
  const conforms = shapes.length > 0 && shapes.every(s => s.conforms) && item.issues.length === 0
  return reply({ ...base, id, conforms, structuralIssues: item.issues, shapes, bindingSummary: countStatuses(rows),
    worktreeBindingsMatch: rows.length > 0 && rows.every(r => r.status === "MATCH"),
    interpretation: "Exit status reports declared structural checks only. Worktree binding differences are separately reported; not silently repaired." }, conforms ? 0 : 1)
}).pipe(Effect.mapError(error => error._tag === "ProcessRefusal" ? error : refuse("detail" in error ? String(error.detail) : String(error))))
