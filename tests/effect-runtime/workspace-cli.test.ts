import { execFileSync } from "node:child_process"
import { createHash } from "node:crypto"
import { mkdtemp, mkdir, readFile, rm, symlink, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { Cause, Effect, Exit, Option } from "effect"
import { afterEach, expect, it } from "vitest"

import { runWorkspaceCli } from "../../src/hswm/effect-runtime/src/workspace-cli.js"
import { NodePosixServicesLive } from "../../src/hswm/effect-runtime/src/effect-posix-services.js"

const roots: string[] = []
const outsideFiles: string[] = []
const sha256 = (value: string): string => createHash("sha256").update(value).digest("hex")
const json = (stdout: string): Record<string, unknown> => JSON.parse(stdout) as Record<string, unknown>
const run = (argv: readonly string[]) => Effect.runPromise(runWorkspaceCli(argv).pipe(Effect.provide(NodePosixServicesLive)))
const refusal = async (argv: readonly string[]): Promise<string> => {
  const exit = await Effect.runPromise(Effect.exit(runWorkspaceCli(argv).pipe(Effect.provide(NodePosixServicesLive))))
  if (Exit.isSuccess(exit)) throw new Error("expected workspace CLI refusal")
  const error = Option.getOrUndefined(Cause.failureOption(exit.cause))
  return typeof error === "object" && error !== null && "detail" in error && typeof error.detail === "string"
    ? error.detail
    : Cause.pretty(exit.cause)
}
const git = (root: string, args: readonly string[]): void => {
  execFileSync("git", ["-C", root, ...args], { stdio: "pipe" })
}
const bundle = (bindings: readonly { readonly path: string; readonly sha256: string }[]) => ({
  schema_version: "hswm-native-kg-test/v1",
  bundle_uid: "sym:AbstractNode:workspace-fixture",
  status: "TEST",
  nonclaim: "TEST_ONLY",
  artifact_bindings: bindings,
  expected_counts: { nodes: 1, anchors: 0, relations: 0 },
  anchors: [],
  nodes: [{ uid: "sym:AbstractNode:workspace-fixture", labels: ["AbstractNode"], properties: { name: "workspace fixture", authority_class: "SECONDARY_AI" } }],
  relations: []
})

const createCheckout = async (): Promise<{ readonly root: string; readonly bound: string }> => {
  const root = await mkdtemp(join(tmpdir(), "hswm-workspace-cli-"))
  roots.push(root)
  await Promise.all(["ontology/workspace", "ontology/queries", "schemas", "docs"].map(path => mkdir(join(root, path), { recursive: true })))
  const bound = "declared binding bytes\n"
  const manifest = {
    schema_version: "hswm-workspace-manifest/v1",
    authority: "SECONDARY_AI_NAVIGATION_ONLY",
    entries: [{
      id: "fixture", title: "Fixture", lane: "ENGINEERING", reading: "Bounded fixture entry.",
      bundle: "ontology/fixture.json", document: "docs/fixture.md",
      queries: [{ id: "nodes", path: "ontology/queries/nodes.rq" }, { id: "escape", path: "docs/escape.rq" }],
      shapes: ["schemas/fixture.ttl"]
    }],
    workflows: []
  }
  await Promise.all([
    writeFile(join(root, "ontology/workspace/HSWM_WORKSPACE.v1.json"), JSON.stringify(manifest)),
    writeFile(join(root, "ontology/fixture.json"), JSON.stringify(bundle([
      { path: "docs/bound.txt", sha256: sha256(bound) },
      { path: "docs/ignored-external.txt", sha256: "f".repeat(64) }
    ]))),
    writeFile(join(root, "ontology/queries/nodes.rq"), "SELECT ?node WHERE { ?node <https://hswm.invalid/kg-bundle-rdf/v1/prop/name> \"workspace fixture\" }"),
    writeFile(join(root, "schemas/fixture.ttl"), `@prefix sh: <http://www.w3.org/ns/shacl#> .
<urn:workspace-shape> a sh:NodeShape ;
  sh:targetSubjectsOf <https://hswm.invalid/kg-bundle-rdf/v1/prop/name> ;
  sh:property [ sh:path <https://hswm.invalid/kg-bundle-rdf/v1/prop/name> ; sh:minCount 1 ] .`),
    writeFile(join(root, "docs/fixture.md"), "# fixture\n"),
    writeFile(join(root, "docs/bound.txt"), bound),
    writeFile(join(root, ".gitignore"), "docs/ignored-external.txt\ndocs/escape.rq\n")
  ])
  git(root, ["init"])
  git(root, ["config", "user.email", "workspace-test@example.invalid"])
  git(root, ["config", "user.name", "Workspace Test"])
  git(root, ["add", "."])
  git(root, ["commit", "-m", "fixture"])
  const outside = `${root}-outside`
  outsideFiles.push(outside)
  await writeFile(outside, "outside\n")
  await symlink(outside, join(root, "docs/ignored-external.txt"))
  await symlink(outside, join(root, "docs/escape.rq"))
  return { root, bound }
}

afterEach(async () => {
  await Promise.all(roots.splice(0).map(root => rm(root, { recursive: true, force: true })))
  await Promise.all(outsideFiles.splice(0).map(path => rm(path, { force: true })))
})

it("reads status and a declared entry from an explicit tracked checkout", async () => {
  const { root } = await createCheckout()
  const status = json((await run(["status", "--checkout", root])).stdout)
  expect(status["scope"]).toBe("READ_ONLY_WORKTREE_OBSERVATION")
  expect(status["entries"]).toEqual([expect.objectContaining({ id: "fixture" })])

  const shown = json((await run(["show", "fixture", "--checkout", root])).stdout)
  expect(shown["entry"]).toEqual(expect.objectContaining({ id: "fixture" }))
  expect(shown["bundle"]).toEqual(expect.objectContaining({ bundleUid: "sym:AbstractNode:workspace-fixture" }))
})

it("runs declared query aliases and structural validation without treating binding drift as structural failure", async () => {
  const { root } = await createCheckout()
  await writeFile(join(root, "docs/bound.txt"), "changed worktree bytes\n")

  const queried = json((await run(["query", "fixture", "nodes", "--checkout", root])).stdout)
  expect(queried["query"]).toBe("nodes")
  expect(queried["result"]).toEqual([expect.objectContaining({ node: expect.objectContaining({ kind: "iri" }) })])

  const validated = json((await run(["validate", "fixture", "--checkout", root])).stdout)
  expect(validated["conforms"]).toBe(true)
  expect(validated["worktreeBindingsMatch"]).toBe(false)
  expect(validated["bindingSummary"]).toEqual(expect.objectContaining({ WORKTREE_DIFFERS: 1, NOT_TRACKED_NOT_READ: 1 }))
})

it("does not read an ignored untracked binding", async () => {
  const { root } = await createCheckout()
  const observed = json((await run(["bindings", "fixture", "--checkout", root])).stdout)
  const rows = observed["rows"] as Array<Record<string, unknown>>
  expect(rows).toEqual(expect.arrayContaining([
    expect.objectContaining({ path: "docs/ignored-external.txt", status: "NOT_TRACKED_NOT_READ", actualSha256: null })
  ]))
})

it("refuses manifest traversal and a declared symlink that resolves outside the checkout", async () => {
  const { root } = await createCheckout()
  expect(await refusal(["query", "fixture", "escape", "--checkout", root])).toContain("resolves outside checkout")

  const manifest = join(root, "ontology/workspace/HSWM_WORKSPACE.v1.json")
  const value = JSON.parse(await readFile(manifest, "utf8")) as { entries: Array<{ queries: Array<{ path: string }> }> }
  value.entries[0]!.queries[0]!.path = "../outside.rq"
  await writeFile(manifest, JSON.stringify(value))
  expect(await refusal(["status", "--checkout", root])).toContain("invalid workspace manifest")
})

it("refuses unknown entries and query aliases", async () => {
  const { root } = await createCheckout()
  expect(await refusal(["show", "unknown", "--checkout", root])).toContain("unknown workspace ID")
  expect(await refusal(["query", "fixture", "unknown", "--checkout", root])).toContain("unknown query alias")
})

it("keeps a created_at historical bundle inspectable while refusing native-v2 validation", async () => {
  const { root } = await createCheckout()
  const historicalDocument = "historical source binding\n"
  const manifestPath = join(root, "ontology/workspace/HSWM_WORKSPACE.v1.json")
  const manifest = JSON.parse(await readFile(manifestPath, "utf8")) as { entries: unknown[] }
  manifest.entries.push({
    id: "historical-created-at",
    title: "Historical created_at fixture",
    lane: "HISTORY",
    reading: "A preserved historical source bundle.",
    projection_profile: "SOURCE_ONLY",
    projection_reason: "The created_at historical schema is retained as source evidence and has no native-v2 projection.",
    bundle: "ontology/historical-created-at.json",
    document: "docs/historical-created-at.md",
    queries: [],
    shapes: []
  })
  await Promise.all([
    writeFile(manifestPath, JSON.stringify(manifest)),
    writeFile(join(root, "ontology/historical-created-at.json"), JSON.stringify({
      schema_version: "hswm-historical-ontology/v1",
      created_at: "2026-08-15T00:00:00Z",
      authority: "SECONDARY_AI",
      nodes: [{ uid: "sym:AbstractNode:historical-created-at-fixture", kind: "AbstractNode" }],
      relations: [],
      artifact_bindings: [{ path: "docs/historical-created-at.md", sha256: sha256(historicalDocument) }]
    })),
    writeFile(join(root, "docs/historical-created-at.md"), historicalDocument)
  ])
  git(root, ["add", "ontology/workspace/HSWM_WORKSPACE.v1.json", "ontology/historical-created-at.json", "docs/historical-created-at.md"])
  git(root, ["commit", "-m", "historical source-only fixture"])

  const shown = json((await run(["show", "historical-created-at", "--checkout", root])).stdout)
  expect(shown["entry"]).toEqual(expect.objectContaining({ projection_profile: "SOURCE_ONLY" }))
  expect(shown["bundle"]).toEqual(expect.objectContaining({ bundleUid: null, nodeCount: 1 }))

  const observedBindings = json((await run(["bindings", "historical-created-at", "--checkout", root])).stdout)
  expect(observedBindings["summary"]).toEqual({ MATCH: 1 })

  const validation = await run(["validate", "historical-created-at", "--checkout", root])
  expect(validation.exitCode).toBe(2)
  expect(json(validation.stdout)).toEqual(expect.objectContaining({
    id: "historical-created-at",
    status: "SOURCE_ONLY_NOT_NATIVE_V2",
    reason: "The created_at historical schema is retained as source evidence and has no native-v2 projection."
  }))
})
