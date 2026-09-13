import { readFileSync, mkdirSync, writeFileSync, mkdtempSync, symlinkSync, rmSync } from "node:fs"
import { resolve, dirname } from "node:path"
import { tmpdir } from "node:os"
import { createHash } from "node:crypto"
import { execFileSync } from "node:child_process"
import { Effect, Either, Schema } from "effect"
import { describe, expect, it } from "vitest"
import { NodePosixFileSystemLive } from "../src/effect-posix-filesystem.js"
import { NodeBoundedSubprocessLive } from "../src/effect-bounded-subprocess.js"
import { verifyNativeRepositoryOntology } from "../src/native-repository-ontology-runtime.js"
import { REPOSITORY_ONTOLOGY_PATH, validateRepositoryOntologyGraph, validateRepositoryRootBaseline, validateFrozenRepositoryPartition, repositoryRegistryPaths } from "../src/native-repository-ontology-domain.js"
const root = resolve(import.meta.dirname, "../../../..")
const folder = resolve(root, "tests/fixtures/native_migration/repository_ontology_v1")
const corpusSchema = Schema.Array(Schema.Struct({ name: Schema.String, files: Schema.Record({ key: Schema.String, value: Schema.String }), symlinks: Schema.Record({ key: Schema.String, value: Schema.String }), decision: Schema.Literal("ACCEPT", "REJECT"), expected: Schema.Unknown }))
const corpus = Schema.decodeUnknownSync(corpusSchema)(JSON.parse(readFileSync(resolve(folder, "contracts.json"), "utf8")))
const run = (path: string) => Effect.runPromise(verifyNativeRepositoryOntology(path).pipe(Effect.provide(NodePosixFileSystemLive), Effect.provide(NodeBoundedSubprocessLive), Effect.either))

describe("native repository ontology original contracts", () => {
  it("keeps the exact original validator source pins", () => {
    const pins = Schema.decodeUnknownSync(Schema.Struct({ source_pins: Schema.Array(Schema.Struct({ path: Schema.String, sha256: Schema.String })) }))(JSON.parse(readFileSync(resolve(folder, "source-pins.json"), "utf8")))
    for (const pin of pins.source_pins) expect(createHash("sha256").update(readFileSync(resolve(root, pin.path))).digest("hex")).toBe(pin.sha256)
  })
  it.each(corpus)("$name: reproduces original accepted output or refusal", async item => {
    const workspace = mkdtempSync(resolve(tmpdir(), "hswm-native-ontology-"))
    try {
      for (const [path, content] of Object.entries(item.files)) { mkdirSync(dirname(resolve(workspace, path)), { recursive: true }); writeFileSync(resolve(workspace, path), content) }
      for (const [path, target] of Object.entries(item.symlinks)) symlinkSync(target, resolve(workspace, path))
      const result = await run(workspace)
      expect(Either.isRight(result) ? "ACCEPT" : "REJECT").toBe(item.decision)
      if (Either.isRight(result)) expect(result.right).toEqual(item.expected)
    } finally { rmSync(workspace, { recursive: true, force: true }) }
  })
  it("preserves the frozen root/public partition and registry refusal", () => {
    const source: unknown = JSON.parse(readFileSync(resolve(root, REPOSITORY_ONTOLOGY_PATH), "utf8"))
    const data = validateRepositoryOntologyGraph(source)
    expect(Either.isRight(data)).toBe(true)
    if (Either.isLeft(data)) return
    const rawBaseline: unknown = JSON.parse(readFileSync(resolve(root, data.right.root_compatibility_baseline), "utf8"))
    const baseline = validateRepositoryRootBaseline(rawBaseline, data.right, [])
    expect(Either.isRight(baseline)).toBe(true)
    if (Either.isLeft(baseline)) return
    const frozen = { public_root_surface: baseline.right.baseline.source_public_paths }
    const roots = [...baseline.right.baseline.paths, ...baseline.right.baseline.source_public_paths]
    expect(Either.isRight(validateFrozenRepositoryPartition(data.right, baseline.right.baseline, frozen, roots))).toBe(true)
    expect(Either.isLeft(validateFrozenRepositoryPartition({ ...data.right, public_root_surface: data.right.public_root_surface.slice(1) }, baseline.right.baseline, frozen, roots))).toBe(true)
    expect(Either.isLeft(validateFrozenRepositoryPartition(data.right, baseline.right.baseline, frozen, roots.slice(1)))).toBe(true)
    expect(Either.isLeft(repositoryRegistryPaths(["same", "same"], "python_root_migrations"))).toBe(true)
  })
  it("verifies the real checkout including all 296 frozen migration sources", async () => {
    const expectedPaths = execFileSync("git", ["-C", root, "ls-files", "--cached", "--others", "--exclude-standard", "-z"], { encoding: "utf8" }).split("\0").filter(Boolean)
    const actual = await run(root)
    expect(Either.isRight(actual)).toBe(true)
    if (Either.isRight(actual)) { expect(actual.right.paths).toBe(new Set(expectedPaths).size); expect(actual.right.python_root_migrations + actual.right.asset_root_migrations).toBe(296); expect(actual.right.from_git).toBe(true); expect(actual.right.concepts).toBe(10) }
  }, 60_000)
})
