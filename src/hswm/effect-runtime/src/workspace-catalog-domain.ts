/**
 * Read-only inventory summaries for checked-in graph bundles.  This module
 * deliberately does not read paths, repair bindings, or assign ownership.
 */
import { createHash } from "node:crypto"
import { Data, Either } from "effect"
import { decodeGeneralJsonBytes, type GeneralJson } from "./general-json-domain.js"

const MAXIMUM_BYTES = 16 * 1024 * 1024
const MAXIMUM_ITEMS = 250_000
const MAXIMUM_PATH_LENGTH = 4_096
const SHA1_HEX = /^[0-9a-f]{40}$/

export class WorkspaceCatalogError extends Data.TaggedError("WorkspaceCatalogError")<{
  readonly detail: string
}> {}

export interface WorkspaceBundleBinding {
  readonly path: string
  readonly sha256: string | null
}

export interface WorkspaceBundleSummary {
  readonly path: string
  readonly sha256: string
  readonly byteLength: number
  readonly bundleUid: string | null
  readonly nodeCount: number
  readonly anchorCount: number
  readonly relationCount: number
  readonly nodeUids: readonly string[]
  readonly bindings: readonly WorkspaceBundleBinding[]
  readonly sourceCut: string | null
  readonly issues: readonly string[]
}

export interface WorkspaceBundleDuplicateUid {
  readonly uid: string
  readonly occurrences: readonly {
    readonly path: string
    readonly bundleUid: string | null
  }[]
}

export interface WorkspaceBundleInventory {
  readonly bundleCount: number
  readonly nodeOccurrenceCount: number
  readonly duplicateUidCount: number
  readonly duplicateUids: readonly WorkspaceBundleDuplicateUid[]
}

type JsonRecord = Readonly<Record<string, GeneralJson>>

const isRecord = (value: GeneralJson): value is JsonRecord => value !== null && typeof value === "object" && !Array.isArray(value)
const freezeArray = <A>(items: readonly A[]): readonly A[] => Object.freeze([...items])
const freezeBinding = (binding: WorkspaceBundleBinding): WorkspaceBundleBinding => Object.freeze(binding)
const sha256 = (bytes: Uint8Array): string => createHash("sha256").update(bytes).digest("hex")
const isSourceCut = (value: GeneralJson | undefined): value is string => typeof value === "string" && SHA1_HEX.test(value)

const issueCardinality = (issues: string[], kind: string, count: number): void => {
  if (count > MAXIMUM_ITEMS) issues.push(`${kind}_count_exceeds_bound:${count}`)
}

const inspectDeclaredCardinality = (value: GeneralJson | undefined, actual: Readonly<Record<string, number>>, issues: string[]): void => {
  if (value === undefined) return
  if (!isRecord(value)) {
    issues.push("expected_counts_not_object")
    return
  }
  for (const [kind, count] of Object.entries(actual)) {
    const expected = value[kind]
    if (expected !== undefined && (typeof expected !== "number" || !Number.isSafeInteger(expected) || expected < 0 || expected !== count)) {
      issues.push(`cardinality_mismatch:${kind}:${String(expected)}:${count}`)
    }
  }
}

const readUid = (value: GeneralJson): string | null => {
  if (!isRecord(value)) return null
  const uid = value["uid"]
  return typeof uid === "string" && uid.length > 0 ? uid : null
}

const inspectBindings = (value: GeneralJson | undefined, issues: string[]): readonly WorkspaceBundleBinding[] => {
  if (!Array.isArray(value)) return freezeArray([])
  issueCardinality(issues, "artifact_binding", value.length)
  const bindings: WorkspaceBundleBinding[] = []
  for (let index = 0; index < value.length; index += 1) {
    const row = value[index]
    if (!isRecord(row) || typeof row["path"] !== "string") {
      issues.push(`artifact_binding_path_missing:${index}`)
      continue
    }
    const declaredSha = row["sha256"]
    bindings.push(freezeBinding({ path: row["path"], sha256: typeof declaredSha === "string" ? declaredSha : null }))
  }
  return freezeArray(bindings)
}

/** Parses a bounded JSON bundle occurrence without consulting the filesystem. */
export const inspectWorkspaceBundle = (input: {
  readonly path: string
  readonly bytes: Uint8Array
}): Either.Either<WorkspaceBundleSummary | null, WorkspaceCatalogError> => {
  if (input.path.length === 0 || input.path.length > MAXIMUM_PATH_LENGTH) {
    return Either.left(new WorkspaceCatalogError({ detail: "bundle path is empty or exceeds the declared bound" }))
  }
  const decoded = decodeGeneralJsonBytes(input.bytes, { maximumBytes: MAXIMUM_BYTES, maximumDepth: 64 })
  if (Either.isLeft(decoded)) return Either.left(new WorkspaceCatalogError({ detail: decoded.left.detail }))
  if (!isRecord(decoded.right)) return Either.right(null)
  const record = decoded.right
  const rawNodes = record["nodes"]
  const rawRelations = record["relations"]
  if (!Array.isArray(rawNodes) || !Array.isArray(rawRelations)) return Either.right(null)
  const nodes: readonly GeneralJson[] = rawNodes
  const relations: readonly GeneralJson[] = rawRelations
  const anchors = Array.isArray(record["anchors"]) ? record["anchors"] : []
  const issues: string[] = []
  issueCardinality(issues, "node", nodes.length)
  issueCardinality(issues, "relation", relations.length)
  issueCardinality(issues, "anchor", anchors.length)
  inspectDeclaredCardinality(record["expected_counts"], { nodes: nodes.length, anchors: anchors.length, relations: relations.length }, issues)
  if (record["anchors"] !== undefined && !Array.isArray(record["anchors"])) issues.push("anchors_not_array")

  const nodeUids: string[] = []
  const knownEndpoints = new Set<string>()
  const localCounts = new Map<string, number>()
  for (let index = 0; index < nodes.length; index += 1) {
    const uid = readUid(nodes[index]!)
    if (uid === null) {
      issues.push(`node_uid_missing:${index}`)
      continue
    }
    nodeUids.push(uid)
    knownEndpoints.add(uid)
    localCounts.set(uid, (localCounts.get(uid) ?? 0) + 1)
  }
  for (const [uid, count] of localCounts) if (count > 1) issues.push(`duplicate_local_uid:${uid}:${count}`)
  for (let index = 0; index < anchors.length; index += 1) {
    const uid = readUid(anchors[index]!)
    if (uid === null) issues.push(`anchor_uid_missing:${index}`)
    else knownEndpoints.add(uid)
  }
  for (let index = 0; index < relations.length; index += 1) {
    const relation = relations[index]!
    if (!isRecord(relation)) {
      issues.push(`relation_not_object:${index}`)
      continue
    }
    for (const endpoint of ["from_uid", "to_uid"] as const) {
      const uid = relation[endpoint]
      if (typeof uid !== "string" || !knownEndpoints.has(uid)) issues.push(`relation_${endpoint}_missing:${index}`)
    }
  }

  const sourceCut = isSourceCut(record["source_commit"])
    ? record["source_commit"]
    : isSourceCut(record["source_base_commit"])
      ? record["source_base_commit"]
      : null
  const bundleUid = typeof record["bundle_uid"] === "string" ? record["bundle_uid"] : null
  return Either.right(Object.freeze({
    path: input.path,
    sha256: sha256(input.bytes),
    byteLength: input.bytes.byteLength,
    bundleUid,
    nodeCount: nodes.length,
    anchorCount: anchors.length,
    relationCount: relations.length,
    nodeUids: freezeArray(nodeUids),
    bindings: inspectBindings(record["artifact_bindings"], issues),
    sourceCut,
    issues: freezeArray(issues)
  }))
}

/** Keeps every occurrence: cross-bundle duplicate UIDs are inventory findings, never merged nodes. */
export const summarizeWorkspaceBundles = (items: readonly WorkspaceBundleSummary[]): WorkspaceBundleInventory => {
  const occurrences = new Map<string, { path: string; bundleUid: string | null }[]>()
  let nodeOccurrenceCount = 0
  for (const item of items) {
    for (const uid of item.nodeUids) {
      nodeOccurrenceCount += 1
      const rows = occurrences.get(uid) ?? []
      rows.push(Object.freeze({ path: item.path, bundleUid: item.bundleUid }))
      occurrences.set(uid, rows)
    }
  }
  const duplicateUids = [...occurrences.entries()]
    .filter(([, rows]) => rows.length > 1)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([uid, rows]) => Object.freeze({ uid, occurrences: freezeArray(rows) }))
  return Object.freeze({
    bundleCount: items.length,
    nodeOccurrenceCount,
    duplicateUidCount: duplicateUids.length,
    duplicateUids: freezeArray(duplicateUids)
  })
}
