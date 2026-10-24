/** Effect shell for explicit, bounded navigation through existing native KG bundles. */
import { Effect, Either } from "effect"
import { refuse, type ProcessReply } from "./effect-process-main.js"
import { decodeKgBundleSource, kgSha256 } from "./native-kg-bundle-domain.js"
import { workspaceNeighborhood, workspaceNodeSource } from "./workspace-navigation-domain.js"
import { type WorkspaceManifest } from "./workspace-manifest-domain.js"

export const runWorkspaceNavigation = <E, R>(input: {
  readonly command: "navigate" | "follow" | "read"
  readonly entryId: string
  readonly uid: string | undefined
  readonly expectedSha256: string | undefined
  readonly offset: number
  readonly limit: number
  readonly maximumBytes: number
  readonly manifest: WorkspaceManifest
  readonly read: (path: string, maximumBytes?: number) => Effect.Effect<Uint8Array, E, R>
}) => Effect.gen(function* () {
  const entry = input.manifest.entries.find(entry => entry.id === input.entryId)
  if (!entry) return yield* Effect.fail(refuse("unknown workspace ID; use status"))
  if (entry.projection_profile === "SOURCE_ONLY")
    return yield* Effect.fail(refuse("source-only historical bundles retain show/bindings; native navigation is unavailable"))
  const rawBytes = yield* input.read(entry.bundle)
  const decoded = decodeKgBundleSource({ sourceId: entry.id, rawBytes, ...(input.expectedSha256 === undefined ? {} : { sha256: input.expectedSha256 }) })
  if (Either.isLeft(decoded)) return yield* Effect.fail(refuse(decoded.left.detail))
  const current = decoded.right
  const uid = input.uid ?? current.bundle.bundle_uid
  const base = {
    schema_version: "hswm-workspace-navigation/v1",
    scope: "READ_ONLY_SOURCE_SCOPED_NAVIGATION",
    claim_ceiling: "CONTENT_NAVIGATION_NOT_CANONICAL_EXECUTION_OR_LEARNING",
    entry: entry.id,
    bundle: entry.bundle,
    bundleSha256: current.sha256,
  }
  const boundedReply = (value: unknown): Effect.Effect<ProcessReply, ReturnType<typeof refuse>> => {
    const stdout = `${JSON.stringify(value, null, 2)}\n`
    return new TextEncoder().encode(stdout).byteLength > input.maximumBytes
      ? Effect.fail(refuse("navigation output exceeds --max-bytes; reduce --limit or explicitly increase the budget; no partial source returned"))
      : Effect.succeed({ stdout, exitCode: 0 })
  }
  if (input.command === "read") {
    const source = workspaceNodeSource(current.bundle, uid)
    if (Either.isLeft(source)) return yield* Effect.fail(refuse(source.left.message))
    const bytes = yield* input.read(source.right.path, input.maximumBytes)
    if (kgSha256(bytes) !== source.right.sha256)
      return yield* Effect.fail(refuse("source digest mismatch; preserve historical pins and select the intended revision"))
    const text = yield* Effect.try({
      try: () => new TextDecoder("utf-8", { fatal: true }).decode(bytes),
      catch: () => refuse("bound source is not UTF-8 text"),
    })
    return yield* boundedReply({ ...base, source: source.right, byteLength: bytes.byteLength,
      complete: true, selection: "COMPLETE_BOUND_SOURCE", text })
  }
  if (input.command === "follow") {
    const anchor = current.bundle.anchors.find(anchor => anchor.uid === uid)
    const route = entry.anchor_routes?.find(route => route.uid === uid)
    if (!anchor || !route) return yield* Effect.fail(refuse("follow requires an explicit route for this bundle's external anchor"))
    const targetEntry = input.manifest.entries.find(entry => entry.id === route.entry)
    if (!targetEntry || targetEntry.projection_profile === "SOURCE_ONLY")
      return yield* Effect.fail(refuse("anchor target is unavailable for native navigation"))
    const targetBytes = yield* input.read(targetEntry.bundle)
    const target = decodeKgBundleSource({ sourceId: targetEntry.id, rawBytes: targetBytes, sha256: route.sha256 })
    if (Either.isLeft(target)) return yield* Effect.fail(refuse(`anchor target: ${target.left.detail}`))
    const node = target.right.bundle.nodes.find(node => node.uid === uid)
    if (!node || !anchor.required_labels.every(label => node.labels.includes(label)))
      return yield* Effect.fail(refuse("anchor target UID or required labels do not match; no inferred identity merge"))
    const neighborhood = workspaceNeighborhood(target.right.bundle, targetEntry, uid, input.offset, input.limit)
    if (Either.isLeft(neighborhood)) return yield* Effect.fail(refuse(neighborhood.left.message))
    return yield* boundedReply({ ...base,
      hop: { from: entry.id, to: targetEntry.id, uid, targetBundle: targetEntry.bundle, targetSha256: target.right.sha256 },
      next: { entry: targetEntry.id, uid, sha256: target.right.sha256 },
      neighborhood: neighborhood.right,
      interpretation: "Explicit source-bound reference; edge status and node authority remain separate. Following grants no execution permission.",
    })
  }
  const neighborhood = workspaceNeighborhood(current.bundle, entry, uid, input.offset, input.limit)
  if (Either.isLeft(neighborhood)) return yield* Effect.fail(refuse(neighborhood.left.message))
  return yield* boundedReply({ ...base, neighborhood: neighborhood.right,
    interpretation: "One bundle and one neighborhood read. Unvisited anchors remain unresolved; this is not a complete activated execution context.",
  })
})
