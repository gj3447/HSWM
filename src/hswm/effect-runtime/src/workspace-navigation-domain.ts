/** One source-scoped neighborhood at a time. No global UID merge or graph execution. */
import { Either } from "effect"
import { type KgBundle, kgCanonicalJson, kgSha256 } from "./native-kg-bundle-domain.js"
import { type WorkspaceEntry } from "./workspace-manifest-domain.js"

export const workspaceNeighborhood = (
  bundle: KgBundle,
  entry: WorkspaceEntry,
  uid: string,
  offset: number,
  limit: number,
) => Either.gen(function* () {
  if (!Number.isSafeInteger(offset) || offset < 0 || !Number.isSafeInteger(limit) || limit < 1 || limit > 50)
    return yield* Either.left(new Error("offset must be nonnegative and limit must be 1..50"))
  const node = bundle.nodes.find(node => node.uid === uid)
  const anchor = bundle.anchors.find(anchor => anchor.uid === uid)
  if (!node && !anchor) return yield* Either.left(new Error("UID absent from this bundle; no global lookup was performed"))
  const incident = bundle.relations.filter(edge => edge.from_uid === uid || edge.to_uid === uid)
  if (offset > incident.length) return yield* Either.left(new Error("offset exceeds neighborhood size"))
  const neighbors = incident.slice(offset, offset + limit).map(edge => {
    const otherUid = edge.from_uid === uid ? edge.to_uid : edge.from_uid
    const other = bundle.nodes.find(candidate => candidate.uid === otherUid)
    const external = bundle.anchors.find(candidate => candidate.uid === otherUid)
    const route = entry.anchor_routes?.find(route => route.uid === otherUid)
    return {
      edgeId: kgSha256(kgCanonicalJson(edge)),
      direction: edge.from_uid === uid ? "OUTGOING" : "INCOMING",
      // Preserve relation authority, scope and raw status independently of its endpoint.
      edge,
      target: {
        uid: otherUid,
        name: other?.properties["name"] ?? external?.name,
        kind: other ? "LOCAL_NODE" : "EXTERNAL_ANCHOR",
        authority: other?.properties["authority_class"] ?? null,
        status: other?.properties["status"] ?? null,
        route: external ? route ?? null : null,
      },
    }
  })
  return {
    node: node ?? anchor,
    kind: node ? "LOCAL_NODE" : "EXTERNAL_ANCHOR",
    route: anchor ? entry.anchor_routes?.find(route => route.uid === uid) ?? null : null,
    neighbors,
    total: incident.length,
    offset,
    nextOffset: offset + neighbors.length < incident.length ? offset + neighbors.length : null,
    complete: offset + neighbors.length === incident.length,
  }
})

/** A source link is readable only when the same bytes are bound by the bundle. */
export const workspaceNodeSource = (bundle: KgBundle, uid: string) => Either.gen(function* () {
  const node = bundle.nodes.find(node => node.uid === uid)
  if (!node) return yield* Either.left(new Error("read requires a local node; follow an external anchor first"))
  const path = node.properties["source_path"]
  const sha256 = node.properties["source_sha256"]
  if (typeof path !== "string" || !/^(docs|ontology|schemas|src|_research|tests)\//.test(path) || typeof sha256 !== "string" ||
      !bundle.artifact_bindings.some(binding => binding.path === path && binding.sha256 === sha256))
    return yield* Either.left(new Error("node has no matching source_path/source_sha256 artifact binding"))
  return {
    uid, path, sha256,
    authority: node.properties["authority_class"] ?? null,
    fragment: node.properties["source_fragment"] ?? null,
  }
})
