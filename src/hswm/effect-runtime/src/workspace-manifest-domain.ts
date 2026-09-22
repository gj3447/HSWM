/** Curated navigation contracts; these do not define HSWM cognition or authority. */
import { Either, Schema } from "effect"

const Id = Schema.String.pipe(Schema.pattern(/^[a-z][a-z0-9-]{0,79}$/))
const Path = Schema.String.pipe(Schema.filter(value =>
  /^(ontology|schemas|docs|_research|src|\.vscode)\//.test(value) &&
  !value.includes("\\") && !value.includes("\0") &&
  value.split("/").every(part => part !== "" && part !== "." && part !== "..")
))
const Query = Schema.Struct({ id: Id, path: Path })
const Entry = Schema.Struct({
  id: Id, title: Schema.NonEmptyString,
  lane: Schema.Literal("IDENTITY", "THEORY", "RESEARCH", "PLAN", "ENGINEERING", "HISTORY"),
  reading: Schema.NonEmptyString,
  projection_profile: Schema.optional(Schema.Literal("NATIVE_V2", "SOURCE_ONLY")),
  projection_reason: Schema.optional(Schema.NonEmptyString),
  bundle: Path, document: Path,
  queries: Schema.Array(Query).pipe(Schema.maxItems(32)),
  shapes: Schema.Array(Path).pipe(Schema.maxItems(8)),
})
const Workflow = Schema.Struct({
  id: Id, title: Schema.NonEmptyString,
  surface: Schema.Literal("ACTIVE_CHECKOUT", "HISTORICAL_REPLAY", "PYTHON_COMPARISON", "CI_ONLY"),
  argv: Schema.Array(Schema.String).pipe(Schema.minItems(1), Schema.maxItems(32)),
  writes: Schema.String, network: Schema.String,
})
const Manifest = Schema.Struct({
  schema_version: Schema.Literal("hswm-workspace-manifest/v1"),
  authority: Schema.Literal("SECONDARY_AI_NAVIGATION_ONLY"),
  entries: Schema.Array(Entry).pipe(Schema.minItems(1), Schema.maxItems(64)),
  workflows: Schema.Array(Workflow).pipe(Schema.maxItems(64)),
})
export type WorkspaceManifest = typeof Manifest.Type
export type WorkspaceEntry = typeof Entry.Type
export const decodeWorkspaceManifest = (value: unknown): Either.Either<WorkspaceManifest, Error> => {
  const decoded = Schema.decodeUnknownEither(Manifest, { onExcessProperty: "error" })(value)
  if (Either.isLeft(decoded)) return Either.left(new Error("invalid workspace manifest"))
  const manifest = decoded.right
  if (manifest.entries.some(e => e.projection_profile === "SOURCE_ONLY" &&
      (e.queries.length !== 0 || e.shapes.length !== 0 || e.projection_reason === undefined)))
    return Either.left(new Error("source-only entries require a reason and no executable queries or shapes"))
  if (new Set(manifest.entries.map(e => e.id)).size !== manifest.entries.length ||
      new Set(manifest.workflows.map(w => w.id)).size !== manifest.workflows.length ||
      manifest.entries.some(e => new Set(e.queries.map(q => q.id)).size !== e.queries.length))
    return Either.left(new Error("duplicate workspace entry, query or workflow ID"))
  return Either.right(Object.freeze({ ...manifest,
    entries: Object.freeze(manifest.entries.map(e => Object.freeze({ ...e,
      queries: Object.freeze(e.queries.map(q => Object.freeze({ ...q }))), shapes: Object.freeze([...e.shapes]),
    }))),
    workflows: Object.freeze(manifest.workflows.map(w => Object.freeze({ ...w, argv: Object.freeze([...w.argv]) }))),
  }))
}
