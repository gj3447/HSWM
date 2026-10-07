import { execFileSync } from "node:child_process"
import { createHash } from "node:crypto"
import { symlinkSync, unlinkSync } from "node:fs"
import { mkdtemp, mkdir, readFile, rename, rm, symlink, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { Cause, Effect, Exit, Layer, Option } from "effect"
import { afterEach, expect, it } from "vitest"

import { NodeBoundedSubprocessLive, NodePosixFileSystem, NodePosixServicesLive, PosixFileSystem } from "../src/effect-posix-services.js"
import { runWorkspaceCli } from "../src/workspace-cli.js"

const roots: string[] = []
const sha256 = (value: string | Uint8Array): string => createHash("sha256").update(value).digest("hex")
const fixtureDocument = "# fixture\n"
const json = (stdout: string): Record<string, unknown> => JSON.parse(stdout) as Record<string, unknown>
const run = (argv: readonly string[]) => Effect.runPromise(runWorkspaceCli(argv).pipe(Effect.provide(NodePosixServicesLive)))
const refusal = async (argv: readonly string[]): Promise<string> => {
  const exit = await Effect.runPromise(Effect.exit(runWorkspaceCli(argv).pipe(Effect.provide(NodePosixServicesLive))))
  if (Exit.isSuccess(exit)) throw new Error("expected workspace CLI refusal")
  const error = Option.getOrUndefined(Cause.failureOption(exit.cause))
  return typeof error === "object" && error !== null && "detail" in error && typeof error.detail === "string" ? error.detail : Cause.pretty(exit.cause)
}
const git = (root: string, args: readonly string[]): void => { execFileSync("git", ["-C", root, ...args], { stdio: "pipe" }) }
const graph = (uid: string, anchors: readonly { readonly uid: string; readonly name: string; readonly required_labels: readonly string[] }[] = []) => ({
  schema_version: "hswm-native-kg-test/v1",
  bundle_uid: `sym:AbstractNode:${uid}-bundle`, status: "TEST", nonclaim: "TEST_ONLY",
  artifact_bindings: [{ path: "docs/fixture.md", sha256: sha256(fixtureDocument) }], expected_counts: { nodes: 1, anchors: anchors.length, relations: 0 }, anchors,
  nodes: [{ uid: `sym:AbstractNode:${uid}`, labels: ["AbstractNode"], properties: { name: uid, authority_class: "SECONDARY_AI" } }], relations: []
})

const createCheckout = async (): Promise<{ readonly root: string; readonly manifest: string; readonly primary: string; readonly additional: string }> => {
  const root = await mkdtemp(join(tmpdir(), "hswm-workspace-composite-"))
  roots.push(root)
  await Promise.all(["ontology/workspace", "ontology/queries", "docs", "schemas", "src/hswm/effect-runtime"].map(path => mkdir(join(root, path), { recursive: true })))
  const manifest = join(root, "ontology/workspace/HSWM_WORKSPACE.v1.json")
  const primary = join(root, "ontology/primary.json"), additional = join(root, "ontology/additional.json")
  const primaryValue = graph("primary", [{ uid: "sym:AbstractNode:additional", name: "additional", required_labels: ["AbstractNode"] }])
  const additionalValue = graph("additional")
  await Promise.all([
    writeFile(primary, JSON.stringify(primaryValue)), writeFile(additional, JSON.stringify(additionalValue)),
    writeFile(join(root, "docs/fixture.md"), fixtureDocument),
    writeFile(join(root, "src/hswm/effect-runtime/package.json"), JSON.stringify({ engines: { node: process.versions.node }, bin: {} })),
    writeFile(join(root, "ontology/queries/anchors.rq"), "SELECT ?node WHERE { ?node <https://hswm.invalid/kg-bundle-rdf/v1/uid> \"sym:AbstractNode:additional\" }"),
    writeFile(manifest, JSON.stringify({ schema_version: "hswm-workspace-manifest/v1", authority: "SECONDARY_AI_NAVIGATION_ONLY", entries: [{
      id: "primary", title: "Primary", lane: "ENGINEERING", reading: "Fixture.", bundle: "ontology/primary.json", document: "docs/fixture.md",
      additional_sources: [{ id: "additional", bundle: "ontology/additional.json", sha256: sha256(JSON.stringify(additionalValue)) }],
      queries: [{ id: "anchors", path: "ontology/queries/anchors.rq" }], shapes: []
    }], workflows: [] }))
  ])
  git(root, ["init"]); git(root, ["config", "user.email", "composite@example.invalid"]); git(root, ["config", "user.name", "Composite Test"])
  git(root, ["add", "."]); git(root, ["commit", "-m", "fixture"])
  return { root, manifest, primary, additional }
}

afterEach(async () => { await Promise.all(roots.splice(0).map(root => rm(root, { recursive: true, force: true }))) })

it("compiles a composite bundle and distinguishes observed primary bytes from manifest pins", async () => {
  const { root } = await createCheckout()
  const observed = json((await run(["query", "primary", "anchors", "--checkout", root])).stdout)
  expect(observed["result"]).toEqual([expect.objectContaining({ node: expect.objectContaining({ kind: "iri" }) })])
  expect(observed["selectedSources"]).toEqual([
    expect.objectContaining({ id: "primary", bundle: "ontology/primary.json", binding: "CURRENT_OBSERVED" }),
    expect.objectContaining({ id: "additional", bundle: "ontology/additional.json", binding: "MANIFEST_PINNED" })
  ])
  const doctor = json((await run(["doctor", "--checkout", root])).stdout)
  expect(doctor["entrypoints"]).toEqual(expect.arrayContaining([
    expect.objectContaining({ path: "ontology/primary.json", status: "AVAILABLE" }),
    expect.objectContaining({ path: "ontology/additional.json", status: "AVAILABLE" })
  ]))
  expect(execFileSync("git", ["-C", root, "status", "--porcelain"], { encoding: "utf8" })).toBe("")
})

it("keeps a single-bundle entry compatible and reports its one selected source", async () => {
  const { root, manifest } = await createCheckout()
  const value = JSON.parse(await readFile(manifest, "utf8")) as { entries: Array<Record<string, unknown>> }
  delete value.entries[0]!["additional_sources"]
  await writeFile(manifest, JSON.stringify(value))
  const observed = json((await run(["query", "primary", "anchors", "--checkout", root])).stdout)
  expect(observed["selectedSources"]).toEqual([expect.objectContaining({ id: "primary", bundle: "ontology/primary.json", binding: "CURRENT_OBSERVED" })])
})

it("refuses stale source pins and duplicate source ownership", async () => {
  const { root, additional, manifest } = await createCheckout()
  await writeFile(additional, JSON.stringify(graph("additional-changed")))
  expect(await refusal(["query", "primary", "anchors", "--checkout", root])).toContain("additional workspace source digest mismatch: additional")

  const original = JSON.parse(await readFile(manifest, "utf8")) as { entries: Array<Record<string, unknown>> }
  const duplicate = { ...graph("primary"), bundle_uid: "sym:AbstractNode:conflicting-owner-bundle",
    nodes: [{ uid: "sym:AbstractNode:primary", labels: ["AbstractNode"], properties: { name: "conflicting owner", authority_class: "SECONDARY_AI" } }] }
  await writeFile(additional, JSON.stringify(duplicate))
  original.entries[0]!["additional_sources"] = [{ id: "additional", bundle: "ontology/additional.json", sha256: sha256(JSON.stringify(duplicate)) }]
  await writeFile(manifest, JSON.stringify(original))
  expect(await refusal(["query", "primary", "anchors", "--checkout", root])).toContain("node owned by two bundles")
})

it("refuses repeated and malformed additional source declarations before reading them", async () => {
  const { root, manifest } = await createCheckout()
  const value = JSON.parse(await readFile(manifest, "utf8")) as { entries: Array<Record<string, unknown>> }
  value.entries[0]!["additional_sources"] = [
    { id: "primary", bundle: "ontology/additional.json", sha256: "a".repeat(64) }
  ]
  await writeFile(manifest, JSON.stringify(value))
  expect(await refusal(["status", "--checkout", root])).toContain("additional workspace source IDs and bundle paths must be unique")

  value.entries[0]!["additional_sources"] = [
    { id: "additional", bundle: "ontology/primary.json", sha256: "A".repeat(64) }
  ]
  await writeFile(manifest, JSON.stringify(value))
  expect(await refusal(["status", "--checkout", root])).toContain("invalid workspace manifest")
})

it("reads the resolved canonical file when a leaf symlink changes after realpath", async () => {
  const { root, manifest, primary } = await createCheckout()
  const original = join(root, "ontology/primary-original.json")
  const replacement = join(root, "ontology/primary-replacement.json")
  const link = join(root, "ontology/primary-link.json")
  await rename(primary, original)
  await writeFile(replacement, JSON.stringify(graph("replacement")))
  await symlink(original, link)
  const value = JSON.parse(await readFile(manifest, "utf8")) as { entries: Array<Record<string, unknown>> }
  value.entries[0]!["bundle"] = "ontology/primary-link.json"
  await writeFile(manifest, JSON.stringify(value))
  const expected = sha256(await readFile(original))
  let swapped = false, linkResolutions = 0
  const filesystem = Object.freeze({ ...NodePosixFileSystem,
    realpath: (path: string, operation: string) => NodePosixFileSystem.realpath(path, operation).pipe(Effect.tap(actual => Effect.sync(() => {
      if (path === link) linkResolutions += 1
      if (!swapped && path === link && linkResolutions === 2) { swapped = true; unlinkSync(link); symlinkSync(replacement, link) }
      return actual
    })))
  })
  const observed = json((await Effect.runPromise(runWorkspaceCli(["query", "primary", "anchors", "--checkout", root]).pipe(
    Effect.provide(Layer.merge(Layer.succeed(PosixFileSystem, filesystem), NodeBoundedSubprocessLive))
  ))).stdout)
  expect(swapped).toBe(true)
  expect((observed["selectedSources"] as Array<Record<string, unknown>>)[0]).toEqual(expect.objectContaining({ sha256: expected, binding: "CURRENT_OBSERVED" }))
})
