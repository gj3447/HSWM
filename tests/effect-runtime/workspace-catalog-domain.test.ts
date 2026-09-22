import { readFileSync } from "node:fs"
import { Either } from "effect"
import { expect, it } from "vitest"

import {
  inspectWorkspaceBundle,
  summarizeWorkspaceBundles,
  type WorkspaceBundleSummary
} from "../../src/hswm/effect-runtime/src/workspace-catalog-domain.js"

const bytes = (value: unknown): Uint8Array => new TextEncoder().encode(JSON.stringify(value))
const right = <A>(value: Either.Either<A, unknown>): A => {
  if (Either.isLeft(value)) throw new Error("expected inventory result")
  return value.right
}
const historicalPath = "ontology/development/HSWM_JEV_GRAPH_ENGINEERING_2026-09-22.v1.json"
const historical = (): WorkspaceBundleSummary => {
  const fixture = new URL("../../ontology/development/HSWM_JEV_GRAPH_ENGINEERING_2026-09-22.v1.json", import.meta.url)
  const result = right(inspectWorkspaceBundle({ path: historicalPath, bytes: readFileSync(fixture) }))
  if (result === null) throw new Error("expected checked-in graph bundle")
  return result
}

it("summarizes a checked-in bundle and keeps a conflicting local UID as separate occurrences", () => {
  const prior = historical()
  const repeatedUid = prior.nodeUids[0]
  expect(repeatedUid).toBeTruthy()
  const local = right(inspectWorkspaceBundle({ path: "scratch/conflict.json", bytes: bytes({
    bundle_uid: "sym:AbstractNode:local-conflict", nodes: [{ uid: repeatedUid }], anchors: [], relations: []
  }) }))
  if (local === null) throw new Error("expected local graph bundle")
  const inventory = summarizeWorkspaceBundles([prior, local])
  const duplicate = inventory.duplicateUids.find((item) => item.uid === repeatedUid)
  expect(duplicate?.occurrences).toEqual([
    { path: historicalPath, bundleUid: prior.bundleUid },
    { path: "scratch/conflict.json", bundleUid: "sym:AbstractNode:local-conflict" }
  ])
  expect(inventory.nodeOccurrenceCount).toBe(prior.nodeCount + 1)
  expect(Object.isFrozen(inventory.duplicateUids)).toBe(true)
})

it("reports local cardinality and endpoint defects while treating anchors as known endpoints", () => {
  const value = right(inspectWorkspaceBundle({ path: "scratch/candidate.json", bytes: bytes({
    bundle_uid: "candidate", source_base_commit: "a".repeat(40),
    expected_counts: { nodes: 1, anchors: 1, relations: 2 },
    artifact_bindings: [{ path: "frozen/doc.md", sha256: "not-repaired" }],
    nodes: [{ uid: "node:a" }, { uid: "node:a" }], anchors: [{ uid: "anchor:prior" }],
    relations: [
      { from_uid: "node:a", to_uid: "anchor:prior" },
      { from_uid: "node:a", to_uid: "node:absent" }
    ]
  }) }))
  if (value === null) throw new Error("expected candidate graph bundle")
  expect(value.sourceCut).toBe("a".repeat(40))
  expect(value.bindings).toEqual([{ path: "frozen/doc.md", sha256: "not-repaired" }])
  expect(value.issues).toContain("duplicate_local_uid:node:a:2")
  expect(value.issues).toContain("cardinality_mismatch:nodes:1:2")
  expect(value.issues).toContain("relation_to_uid_missing:1")
  expect(value.issues).not.toContain("relation_to_uid_missing:0")
})

it("does not silently union local duplicate UIDs", () => {
  const first = right(inspectWorkspaceBundle({ path: "one.json", bytes: bytes({ nodes: [{ uid: "same" }, { uid: "same" }], relations: [] }) }))
  if (first === null) throw new Error("expected graph bundle")
  const inventory = summarizeWorkspaceBundles([first])
  expect(first.nodeUids).toEqual(["same", "same"])
  expect(inventory.nodeOccurrenceCount).toBe(2)
  expect(inventory.duplicateUids).toEqual([{ uid: "same", occurrences: [{ path: "one.json", bundleUid: null }, { path: "one.json", bundleUid: null }] }])
})

it("returns null for valid non-bundles and an Either error for malformed bytes", () => {
  expect(right(inspectWorkspaceBundle({ path: "plain.json", bytes: bytes({ hello: "world" }) }))).toBeNull()
  expect(Either.isLeft(inspectWorkspaceBundle({ path: "bad.json", bytes: new TextEncoder().encode("{not json") }))).toBe(true)
})
