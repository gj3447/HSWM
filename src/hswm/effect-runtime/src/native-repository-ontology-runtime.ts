/** Read-only Effect shell for Git and source-distribution layout verification. */
import { join, resolve, sep } from "node:path"
import { Effect, Either } from "effect"
import { PosixFileSystem } from "./effect-posix-filesystem.js"
import { BoundedSubprocess } from "./effect-bounded-subprocess.js"
import { decodeGeneralJsonBytes } from "./general-json-domain.js"
import { canonicalRepositoryPath, parseEntries, selectedManifestReferences, sha256 } from "./native-legacy-replay-domain.js"
import { runNativeLegacyReplayCli } from "./native-legacy-replay-cli.js"
import { REPOSITORY_ONTOLOGY_PATH, ROOT_BASELINE_COMMIT, repositoryOntologyFailure as failure, repositoryRegistryPaths, validateFrozenRepositoryPartition, validateRepositoryOntologyGraph, validateRepositoryRootBaseline, validateRepositoryRootSurface } from "./native-repository-ontology-domain.js"

const maximumBytes = 16 * 1024 * 1024
const decode = (bytes: Uint8Array) => Effect.try({ try: () => new TextDecoder("utf-8", { fatal: true }).decode(bytes), catch: () => failure("repository input is not valid UTF-8") })
const json = (bytes: Uint8Array) => decodeGeneralJsonBytes(bytes, { maximumBytes, maximumDepth: 64 }).pipe(Either.mapLeft(e => failure(e.detail)))
const object = (value: unknown): value is Readonly<Record<string, unknown>> => value !== null && typeof value === "object" && !Array.isArray(value)
const ignored: readonly string[] = Object.freeze([".git", ".hypothesis", ".pytest_cache", ".venv", "__pycache__", "build", "dist", "hswm.egg-info"])

export const verifyNativeRepositoryOntology = (repositoryRoot: string) => Effect.gen(function* () {
  const fs = yield* PosixFileSystem, subprocess = yield* BoundedSubprocess
  const root = yield* fs.realpath(resolve(repositoryRoot), "repository-root")
  const identity = (relative: string) => fs.identity(join(root, relative), "repository-path").pipe(Effect.catchAll(error => error.code === "ENOENT" ? Effect.succeed(null) : Effect.fail(error)))
  const safe = (relative: string) => Effect.gen(function* () {
    if (!canonicalRepositoryPath(relative)) return yield* Effect.fail(failure(`invalid repository path: ${relative}`))
    const observed = yield* identity(relative)
    if (observed?.kind !== "FILE") return yield* Effect.fail(failure(`repository path is not a regular file: ${relative}`))
    const path = yield* fs.realpath(join(root, relative), "repository-path")
    if (!path.startsWith(root + sep)) return yield* Effect.fail(failure(`repository path escapes the repository: ${relative}`))
    return path
  })
  const read = (relative: string) => Effect.gen(function* () {
    const path = yield* safe(relative)
    return (yield* fs.readRegularBounded(path, { maximumBytes, operation: "repository-source" })).bytes
  })
  const readJson = (relative: string) => Effect.gen(function* () { return yield* json(yield* read(relative)) })
  const git = (args: readonly string[], checked = true) => Effect.gen(function* () {
    const result = yield* subprocess.observe({ argv: ["git", "-C", root, ...args], cwd: root, environment: { ...process.env, GIT_CONFIG_NOSYSTEM: "1", GIT_TERMINAL_PROMPT: "0", LC_ALL: "C" }, timeoutMs: 30_000, maximumOutputBytes: maximumBytes })
    if (result.timedOut || result.outputTruncated || result.signal !== null || (checked && (result.exitCode !== 0 || result.launchError !== null))) return yield* Effect.fail(failure("Git repository observation failed or exceeded its bound"))
    return result
  })
  const blob = (commit: string, relative: string) => Effect.gen(function* () {
    if (!/^[0-9a-f]{40}$/.test(commit) || !canonicalRepositoryPath(relative)) return yield* Effect.fail(failure("invalid frozen repository path"))
    return (yield* git(["show", `${commit}:${relative}`])).stdout
  })
  const ontologyBytes = yield* read(REPOSITORY_ONTOLOGY_PATH), value = yield* json(ontologyBytes)
  const data = yield* validateRepositoryOntologyGraph(value)
  for (const concept of data.concepts) {
    if ((yield* fs.identity(resolve(root, concept.directory), "concept-directory")).kind !== "DIRECTORY" || (yield* fs.identity(resolve(root, concept.directory, "README.md"), "concept-readme")).kind !== "FILE") return yield* Effect.fail(failure(`concept directory lacks README: ${concept.directory}`))
  }
  const refs = yield* selectedManifestReferences(yield* decode(ontologyBytes))
  const manifests = yield* Effect.forEach(refs, ([path, family]) => Effect.gen(function* () { return [path, family, yield* decode(yield* read(path))] as const }))
  const entries = yield* parseEntries(yield* decode(ontologyBytes), manifests)
  const { baseline, activeLegacy } = yield* validateRepositoryRootBaseline(yield* readJson(data.root_compatibility_baseline), data, entries)
  const localGit = yield* identity(".git"), top = yield* git(["rev-parse", "--show-toplevel"], false)
  const fromGit = top.exitCode === 0 && top.launchError === null && resolve((yield* decode(top.stdout)).trim()) === root
  if (!fromGit && localGit !== null) return yield* Effect.fail(failure("Git checkout metadata cannot be read or resolves to the wrong repository root"))
  const walk = (relative: string): Effect.Effect<readonly string[], import("./effect-posix-filesystem.js").PosixIoError> => Effect.gen(function* () {
    const rows = yield* fs.listDirectory(join(root, relative), "repository-fallback")
    const nested = yield* Effect.forEach(rows.filter(row => !ignored.includes(row.name) && !(relative === "" && ["PKG-INFO", "setup.cfg"].includes(row.name))), row => {
      const path = relative ? `${relative}/${row.name}` : row.name
      return row.kind === "DIRECTORY" ? walk(path) : Effect.succeed(row.kind === "FILE" || row.kind === "SYMLINK" ? [path] : [])
    }, { concurrency: 1 })
    return nested.flat()
  })
  const observed = fromGit ? (yield* decode((yield* git(["ls-files", "--cached", "--others", "--exclude-standard", "-z"])).stdout)).split("\0").filter(Boolean) : yield* walk("")
  const existing = yield* Effect.filter([...new Set(observed)], path => identity(path).pipe(Effect.map(id => id !== null)))
  for (const entry of entries) {
    if (activeLegacy.includes(entry.old_path) || (yield* identity(entry.old_path)) !== null) return yield* Effect.fail(failure(`migrated path still occupies root: ${entry.old_path}`))
    yield* safe(entry.canonical_path)
  }
  const roots = yield* validateRepositoryRootSurface(existing, data.public_root_surface, activeLegacy, !fromGit)
  for (const path of roots) yield* safe(path)
  if (fromGit) {
    const verified = yield* runNativeLegacyReplayCli(["--repo", root, "verify"])
    const result = yield* json(new TextEncoder().encode(verified.stdout))
    if (!object(result) || result["count"] !== entries.length) return yield* Effect.fail(failure("legacy replay verification count mismatch"))
    if ((yield* git(["merge-base", "--is-ancestor", ROOT_BASELINE_COMMIT, "HEAD"], false)).exitCode !== 0) return yield* Effect.fail(failure("root compatibility baseline is not reachable from HEAD"))
    const frozen = yield* json(yield* blob(ROOT_BASELINE_COMMIT, REPOSITORY_ONTOLOGY_PATH))
    const tree = (yield* decode((yield* git(["ls-tree", "-z", ROOT_BASELINE_COMMIT])).stdout)).split("\0").filter(Boolean)
    const rootFiles = tree.filter(row => row.split("\t")[0]?.split(" ")[1] === "blob").map(row => row.slice(row.indexOf("\t") + 1))
    yield* validateFrozenRepositoryPartition(data, baseline, frozen, rootFiles)
    if (!object(frozen)) return yield* Effect.fail(failure("frozen repository ontology is not an object"))
    for (const key of ["python_root_migrations", "asset_root_migrations"] as const) {
      const old = yield* repositoryRegistryPaths(frozen[key], key), current = yield* repositoryRegistryPaths(data[key], key)
      if (old.some(path => !current.includes(path))) return yield* Effect.fail(failure("migration registry dropped frozen manifests"))
      for (const path of old) if (sha256(yield* read(path)) !== sha256(yield* blob(ROOT_BASELINE_COMMIT, path))) return yield* Effect.fail(failure(`frozen migration manifest changed: ${path}`))
    }
    for (const path of activeLegacy) if (sha256(yield* read(path)) !== sha256(yield* blob(ROOT_BASELINE_COMMIT, path))) return yield* Effect.fail(failure(`frozen root path changed: ${path}`))
  }
  const python = entries.filter(entry => entry.old_path.endsWith(".py")).length
  return { paths: existing.length, legacy_root_paths: activeLegacy.length, concepts: data.concepts.length, python_root_migrations: python, asset_root_migrations: entries.length - python, from_git: fromGit }
}).pipe(Effect.mapError(error => failure(error.detail)))
