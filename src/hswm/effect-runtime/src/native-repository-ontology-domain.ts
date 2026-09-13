/** Immutable decisions for the repository layout contract; never HSWM cognition. */
import { Data, Either, Schema } from "effect"
import { canonicalRepositoryPath, type LegacyMigrationEntry } from "./native-legacy-replay-domain.js"

export const REPOSITORY_ONTOLOGY_PATH = "ontology/HSWM_REPOSITORY_ONTOLOGY.v1.json"
export const ROOT_BASELINE_COMMIT = "33556a55530bdc0912154abc8c19897f89b0dcda"
export class NativeRepositoryOntologyError extends Data.TaggedError("NativeRepositoryOntologyError")<{ readonly detail: string }> {}
export const repositoryOntologyFailure = (detail: string) => new NativeRepositoryOntologyError({ detail })
const fail = (detail: string) => Either.left(repositoryOntologyFailure(detail))
const paths = Schema.Array(Schema.String)
const registry = Schema.Union(Schema.String, paths)
const concept = Schema.Struct({ uid: Schema.String, directory: Schema.String })
const contractSchema = Schema.Struct({
  schema_version: Schema.Literal("hswm-repository-ontology/v1"), root_uid: Schema.String,
  concepts: Schema.Array(concept),
  relations: Schema.Array(Schema.Struct({ from: Schema.String, to: Schema.String, type: Schema.String })),
  mounts: Schema.Array(Schema.Struct({ id: Schema.String, concepts: paths, patterns: Schema.optional(paths), root_patterns: Schema.optional(paths) })),
  public_root_surface: paths, root_compatibility_baseline: Schema.String,
  python_root_migrations: registry, asset_root_migrations: registry
})
export type RepositoryOntologyContract = typeof contractSchema.Type
const baselineSchema = Schema.Struct({
  $schema: Schema.Literal("../../schemas/hswm_root_compatibility_baseline.v1.schema.json"),
  schema_version: Schema.Literal("hswm-root-compatibility-baseline/v1"), status: Schema.Literal("FROZEN_BASELINE"),
  source_commit: Schema.Literal(ROOT_BASELINE_COMMIT), source_public_paths: paths, paths
})
export type RepositoryRootBaseline = typeof baselineSchema.Type
const unique = (values: readonly string[]) => new Set(values).size === values.length
const rootPath = (path: string) => path.length > 0 && !path.includes("/") && !path.includes("\\")
export const samePathSet = (left: readonly string[], right: readonly string[]) => left.length === right.length && left.every(path => right.includes(path))
export const validateRepositoryOntologyGraph = (value: unknown): Either.Either<RepositoryOntologyContract, NativeRepositoryOntologyError> => Either.gen(function* () {
  const data = yield* Schema.decodeUnknownEither(contractSchema)(value).pipe(Either.mapLeft(() => repositoryOntologyFailure("unsupported repository ontology schema or graph shape")))
  const ids = data.concepts.map(row => row.uid)
  if (!unique(ids) || ids.includes(data.root_uid)) return yield* fail("concept UIDs must be present and unique; root_uid must identify repository")
  if (data.relations.some(row => !ids.includes(row.from) || !ids.includes(row.to) || !row.type)) return yield* fail("relation has unknown endpoint or no type")
  if (!unique(data.mounts.map(row => row.id)) || data.mounts.some(row => !row.id || row.concepts.some(id => !ids.includes(id)) || !(row.patterns?.length || row.root_patterns?.length))) return yield* fail("mount id, concept or pattern drift")
  if (!unique(data.public_root_surface) || data.public_root_surface.some(path => path.includes("/"))) return yield* fail("public_root_surface must contain unique root paths")
  if (!canonicalRepositoryPath(data.root_compatibility_baseline)) return yield* fail("invalid root compatibility baseline path")
  return data
})
export const validateRepositoryRootBaseline = (value: unknown, data: RepositoryOntologyContract, entries: readonly LegacyMigrationEntry[]): Either.Either<{ readonly baseline: RepositoryRootBaseline; readonly activeLegacy: readonly string[] }, NativeRepositoryOntologyError> => Either.gen(function* () {
  const baseline = yield* Schema.decodeUnknownEither(baselineSchema)(value).pipe(Either.mapLeft(() => repositoryOntologyFailure("root compatibility baseline schema, status or commit drift")))
  if (!baseline.source_public_paths.length || !unique(baseline.source_public_paths) || !baseline.source_public_paths.every(rootPath) || !unique(baseline.paths) || !baseline.paths.every(rootPath)) return yield* fail("root compatibility baseline paths are invalid")
  if (baseline.paths.some(path => baseline.source_public_paths.includes(path))) return yield* fail("baseline public and compatibility paths overlap")
  const moved = entries.map(entry => entry.old_path)
  const activeLegacy = baseline.paths.filter(path => !moved.includes(path))
  if (activeLegacy.some(path => data.public_root_surface.includes(path))) return yield* fail("public and legacy root surfaces overlap")
  return { baseline, activeLegacy }
})
export const validateRepositoryRootSurface = (observed: readonly string[], publicPaths: readonly string[], legacy: readonly string[], allowMissing: boolean): Either.Either<readonly string[], NativeRepositoryOntologyError> => {
  const roots = [...new Set(observed.filter(path => !path.includes("/")))], allowed = [...publicPaths, ...legacy]
  const unexpected = roots.filter(path => !allowed.includes(path)).sort(), missing = allowMissing ? [] : allowed.filter(path => !roots.includes(path)).sort()
  return unexpected.length || missing.length ? fail(`root surface drift: unexpected=${JSON.stringify(unexpected)}, missing=${JSON.stringify(missing)}`) : Either.right(roots)
}
export const repositoryRegistryPaths = (value: unknown, key: string): Either.Either<readonly string[], NativeRepositoryOntologyError> => {
  const rows = typeof value === "string" && value ? [value] : Array.isArray(value) && value.length && value.every((item): item is string => typeof item === "string" && !!item) ? value : undefined
  return rows === undefined || !unique(rows) ? fail(`repository ontology has invalid or repeated ${key}`) : Either.right(rows)
}
export const validateFrozenRepositoryPartition = (data: RepositoryOntologyContract, baseline: RepositoryRootBaseline, frozen: unknown, rootFiles: readonly string[]): Either.Either<void, NativeRepositoryOntologyError> => Either.gen(function* () {
  if (frozen === null || typeof frozen !== "object" || !("public_root_surface" in frozen) || !Array.isArray(frozen.public_root_surface) || !frozen.public_root_surface.every((p): p is string => typeof p === "string") || !samePathSet([...new Set(frozen.public_root_surface)], [...new Set(baseline.source_public_paths)])) return yield* fail("baseline source public paths differ from the frozen ontology")
  if (!samePathSet([...new Set(data.public_root_surface)], [...new Set(baseline.source_public_paths)])) return yield* fail("current public root surface differs from the frozen ontology")
  if (!samePathSet([...new Set(rootFiles)], [...new Set([...baseline.paths, ...baseline.source_public_paths])])) return yield* fail("root compatibility baseline drift")
})
