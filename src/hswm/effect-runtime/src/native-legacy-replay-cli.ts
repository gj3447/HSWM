import { dirname, join, resolve } from "node:path"
import { Effect, Either } from "effect"
import { BoundedSubprocess } from "./effect-bounded-subprocess.js"
import { PosixFileSystem, type PosixFileSystemShape } from "./effect-posix-filesystem.js"
import { LEGACY_REPLAY_LIST_V1 as LIST, LEGACY_REPLAY_ONTOLOGY as ONTO, LEGACY_REPLAY_RECEIPT_NAME as RECEIPT_NAME, LEGACY_REPLAY_RECEIPT_V1 as RECEIPT, LEGACY_REPLAY_VERIFICATION_V1 as VERIFY, legacyRefusal as refuse, parseEntries, receiptHash, renderCanonicalJson as json, sha256, destinationOverlaps, selectedManifestReferences, type LegacyMigrationEntry, type ManifestSource } from "./native-legacy-replay-domain.js"

const dec = new TextDecoder(), enc = new TextEncoder(), max = 16 * 1024 * 1024
const env = Object.freeze({ ...process.env, GIT_CONFIG_NOSYSTEM: "1", GIT_TERMINAL_PROMPT: "0", LC_ALL: "C" })
const usage = "usage: hswm-legacy-replay [--repo REPOSITORY] <list|verify|materialize> [old_path] [destination]"
const git = (cwd:string, args:ReadonlyArray<string>, check = true) => Effect.gen(function* () {
  const subprocess = yield* BoundedSubprocess
  const result = yield* subprocess.observe({ argv: ["git", "-C", cwd, ...args], cwd, environment: env, timeoutMs: 30_000, maximumOutputBytes: max }).pipe(Effect.mapError(e => refuse(e.detail)))
  if (check && (result.exitCode !== 0 || result.timedOut || result.outputTruncated || result.launchError)) return yield* Effect.fail(refuse(dec.decode(result.stderr).trim().split("\n").at(-1) || "Git command failed"))
  return result
})
const regular = (fs:PosixFileSystemShape, path:string, label:string) => Effect.gen(function* () {
  const id = yield* fs.identity(path, label).pipe(Effect.mapError(e => refuse(e.detail)))
  if (id.kind !== "FILE") return yield* Effect.fail(refuse(`${label} must be a regular file`))
  return yield* fs.realpath(path, label).pipe(Effect.mapError(e => refuse(e.detail)))
})
const read = (fs:PosixFileSystemShape, path:string, label:string) => fs.readRegularBounded(path, { maximumBytes: max, operation: label }).pipe(Effect.mapError(e => refuse(e.detail)), Effect.map(x => dec.decode(x.bytes)))

const discover = (anchor:string) => Effect.gen(function* () {
  const fs = yield* PosixFileSystem
  let current = yield* fs.realpath(resolve(anchor), "repository anchor").pipe(Effect.mapError(() => refuse(`repository anchor does not exist: ${anchor}`)))
  if ((yield* fs.identity(current, "repository anchor").pipe(Effect.mapError(e => refuse(e.detail)))).kind === "FILE") current = dirname(current)
  while (true) {
    const [project, ontology] = yield* Effect.all([fs.identity(join(current, "pyproject.toml"), "marker").pipe(Effect.either), fs.identity(join(current, ONTO), "marker").pipe(Effect.either)])
    if (Either.isRight(project) && project.right.kind === "FILE" && Either.isRight(ontology) && ontology.right.kind === "FILE") return current
    const parent = dirname(current)
    if (parent === current) return yield* Effect.fail(refuse(`cannot discover HSWM repository root from ${anchor}`))
    current = parent
  }
})
const load = (repo:string) => Effect.gen(function* () {
  const fs = yield* PosixFileSystem
  const ontology = yield* read(fs, yield* regular(fs, join(repo, ONTO), "repository ontology"), "repository ontology")
  const selected = selectedManifestReferences(ontology)
  if (Either.isLeft(selected)) return yield* Effect.fail(selected.left)
  const manifests:ReadonlyArray<ManifestSource> = yield* Effect.forEach(selected.right, ([path, family]) => Effect.gen(function* () {
    return [path, family, yield* read(fs, yield* regular(fs, join(repo, path), "migration manifest"), "migration manifest")] as const
  }))
  const parsed = parseEntries(ontology, manifests)
  if (Either.isLeft(parsed)) return yield* Effect.fail(parsed.left)
  return parsed.right
})
const ensureCheckout = (repo:string) => Effect.gen(function* () {
  const top = dec.decode((yield* git(repo, ["rev-parse", "--show-toplevel"])).stdout).trim()
  if (resolve(top) !== resolve(repo)) return yield* Effect.fail(refuse(`repository root is nested in another Git checkout: ${repo}`))
  return repo
})
const verifyOne = (repo:string, entry:LegacyMigrationEntry) => Effect.gen(function* () {
  const commit = dec.decode((yield* git(repo, ["rev-parse", "--verify", `${entry.source_commit}^{commit}`])).stdout).trim()
  if (commit !== entry.source_commit) return yield* Effect.fail(refuse(`source commit did not resolve exactly for ${entry.old_path}: ${commit}`))
  if ((yield* git(repo, ["merge-base", "--is-ancestor", entry.source_commit, "HEAD"], false)).exitCode !== 0) return yield* Effect.fail(refuse(`source commit is not reachable from HEAD for ${entry.old_path}`))
  const observed = sha256((yield* git(repo, ["show", `${entry.source_commit}:${entry.old_path}`])).stdout)
  if (observed !== entry.source_sha256) return yield* Effect.fail(refuse(`source blob SHA-256 mismatch for ${entry.old_path}: ${observed}`))
  return { ...entry, observed_source_sha256: observed, source_tree: dec.decode((yield* git(repo, ["rev-parse", `${entry.source_commit}^{tree}`])).stdout).trim(), verified: true }
})
const verify = (repo:string, old:string|undefined) => Effect.gen(function* () {
  const all = yield* load(repo), selected = old === undefined ? all : all.filter(x => x.old_path === old)
  if (selected.length === 0) return yield* Effect.fail(refuse(`unknown migrated old_path: ${old}`))
  const entries = yield* Effect.forEach(selected, x => verifyOne(repo, x))
  return { schema_version: VERIFY, repository_head: dec.decode((yield* git(repo, ["rev-parse", "HEAD"])).stdout).trim(), count: entries.length, entries }
})
const materialize = (repo:string, old:string, destination:string) => Effect.gen(function* () {
  const fs = yield* PosixFileSystem, entries = yield* load(repo), requested = entries.find(x => x.old_path === old)
  if (!requested) return yield* Effect.fail(refuse(`unknown migrated old_path: ${old}`))
  if (destination.split(/[\\/]/).includes("..")) return yield* Effect.fail(refuse("destination may not contain '..'"))
  const raw = resolve(destination), parent = dirname(raw)
  const parentId = yield* fs.identity(parent, "destination parent").pipe(Effect.mapError(() => refuse("destination parent must already exist")))
  if (parentId.kind !== "DIRECTORY") return yield* Effect.fail(refuse("destination parent must be a directory"))
  const basename = raw.split(/[\\/]/).at(-1)
  if (basename === undefined || basename.length === 0) return yield* Effect.fail(refuse("destination must name a path"))
  const target = join(yield* fs.realpath(parent, "destination parent").pipe(Effect.mapError(() => refuse("destination parent must already exist"))), basename)
  if (destinationOverlaps(resolve(repo), target)) return yield* Effect.fail(refuse("destination may not equal, contain, or be inside repository"))
  if (Either.isRight(yield* fs.identity(raw, "destination").pipe(Effect.either))) return yield* Effect.fail(refuse("destination must not exist"))
  const same = entries.filter(x => x.source_commit === requested.source_commit)
  const verified = yield* Effect.forEach(same, x => verifyOne(repo, x))
  yield* git(repo, ["-c", "core.hooksPath=/dev/null", "clone", "--no-hardlinks", "--no-checkout", "--", repo, target])
  yield* git(target, ["-c", "core.hooksPath=/dev/null", "checkout", "--detach", requested.source_commit])
  if (dec.decode((yield* git(target, ["rev-parse", "HEAD"])).stdout).trim() !== requested.source_commit) return yield* Effect.fail(refuse("materialized checkout HEAD differs from source commit"))
  if ((yield* git(target, ["symbolic-ref", "-q", "HEAD"], false)).exitCode !== 1) return yield* Effect.fail(refuse("materialized checkout is not detached"))
  const alternate = yield* fs.identity(join(target, ".git/objects/info/alternates"), "alternates").pipe(Effect.either)
  if (Either.isRight(alternate)) return yield* Effect.fail(refuse("materialized clone is not object-standalone"))
  const sources = yield* Effect.forEach(same, entry => Effect.gen(function* () {
    const sourcePath = yield* regular(fs, join(target, entry.old_path), `materialized source ${entry.old_path}`)
    const observed = sha256((yield* fs.readRegularBounded(sourcePath, { maximumBytes: max, operation: `materialized source ${entry.old_path}` }).pipe(Effect.mapError(e => refuse(e.detail)))).bytes)
    if (observed !== entry.source_sha256) return yield* Effect.fail(refuse(`checkout file SHA-256 mismatch for ${entry.old_path}: ${observed}`))
    return { old_path: entry.old_path, source_sha256: entry.source_sha256, checkout_sha256: observed, migration_manifest: entry.migration_manifest }
  }))
  if (dec.decode((yield* git(target, ["status", "--porcelain=v1", "--untracked-files=all"])).stdout)) return yield* Effect.fail(refuse("materialized checkout is not clean"))
  const receipt = { schema_version: RECEIPT, status: "VERIFIED", workspace_kind: "detached-standalone-clone", requested_old_path: old, source_repository: repo, source_repository_head: dec.decode((yield* git(repo, ["rev-parse", "HEAD"])).stdout).trim(), source_commit: requested.source_commit, source_tree: dec.decode((yield* git(repo, ["rev-parse", `${requested.source_commit}^{tree}`])).stdout).trim(), git_metadata: true, detached_head: true, clean_checkout: true, objects_standalone: true, verified_sources: sources.sort((a, b) => a.old_path < b.old_path ? -1 : a.old_path > b.old_path ? 1 : 0), pre_materialization_verification_count: verified.length, receipt_sha256: "" }
  receipt.receipt_sha256 = receiptHash(receipt)
  yield* fs.writeExclusive(join(target, ".git", RECEIPT_NAME), enc.encode(`${json(receipt)}\n`), { mode: 0o600, sync: true, operation: "write replay receipt" }).pipe(Effect.mapError(e => refuse(e.detail)))
  if (dec.decode((yield* git(target, ["status", "--porcelain=v1", "--untracked-files=all"])).stdout)) return yield* Effect.fail(refuse("receipt publication dirtied the replay checkout"))
  return receipt
})
export const runNativeLegacyReplayCli = (argv:ReadonlyArray<string>) => Effect.gen(function* () {
  let args = [...argv], anchor
  if (args[0] === "--repo" && args[1]) { anchor = args[1]; args = args.slice(2) }
  if (args[0] === "--help") return { stdout: `${usage}\n`, exitCode: 0 }
  const command = args[0]
  if (command !== "list" && command !== "verify" && command !== "materialize") return yield* Effect.fail(refuse(usage))
  const repo = yield* ensureCheckout(yield* discover(anchor ?? process.cwd()))
  if (command === "list") { if (args.length !== 1) return yield* Effect.fail(refuse(usage)); const entries = yield* load(repo); return { stdout: `${json({ schema_version: LIST, count: entries.length, entries })}\n`, exitCode: 0 } }
  if (command === "verify") { if (args.length > 2) return yield* Effect.fail(refuse(usage)); return { stdout: `${json(yield* verify(repo, args[1]))}\n`, exitCode: 0 } }
  if (args.length !== 3) return yield* Effect.fail(refuse(usage))
  const oldPath = args[1], destination = args[2]
  if (oldPath === undefined || destination === undefined) return yield* Effect.fail(refuse(usage))
  return { stdout: `${json(yield* materialize(repo, oldPath, destination))}\n`, exitCode: 0 }
})
export const describeNativeLegacyReplayError = (error:import("./native-legacy-replay-domain.js").NativeLegacyReplayError):string => `legacy replay refused: ${error.detail}`
