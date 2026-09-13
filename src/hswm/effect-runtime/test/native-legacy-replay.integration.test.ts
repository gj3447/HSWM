import { execFileSync } from "node:child_process"
import { createHash } from "node:crypto"
import { existsSync, mkdirSync, mkdtempSync, rmSync, symlinkSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import { describe, expect, it } from "vitest"
import { renderCanonicalJson, selectedManifestReferences } from "../src/native-legacy-replay-domain.js"
import { Either } from "effect"

const root = resolve(import.meta.dirname, "../../../..")
const sourceCut = "974c64418c9f29248eb538ffa78912bfa12eb0ea"
const nativeToolPath = mkdtempSync(join(tmpdir(), "hswm-native-legacy-tools-"))
symlinkSync("/usr/bin/git", join(nativeToolPath, "git"))
let emitted: string | undefined
const emit = (): string => {
  if (emitted !== undefined) return emitted
  const output = mkdtempSync(join(tmpdir(), "native-legacy-replay-emit-"))
  symlinkSync(join(root, "src/hswm/effect-runtime/node_modules"), join(output, "node_modules"), "dir")
  const config = join(output, "tsconfig.json")
  writeFileSync(config, JSON.stringify({ extends: join(root, "src/hswm/effect-runtime/tsconfig.build.json"), compilerOptions: { rootDir: join(root, "src/hswm/effect-runtime/src"), outDir: output, noEmit: false, declaration: false, declarationMap: false, sourceMap: false }, include: [join(root, "src/hswm/effect-runtime/src/native-legacy-replay-process.ts")], exclude: [] }))
  execFileSync(join(root, "src/hswm/effect-runtime/node_modules/.bin/tsc"), ["-p", config], { cwd: root })
  emitted = output
  return output
}
const invoke = (repository: string, args: ReadonlyArray<string>): string => execFileSync(process.execPath, [join(emit(), "native-legacy-replay-process.js"), "--repo", repository, ...args], { encoding: "utf8", env: { PATH: nativeToolPath } })
const run = (...args: string[]) => invoke(root, args)
const digest = (value: unknown) => createHash("sha256").update(JSON.stringify(value)).digest("hex")
const cloneFixture = (): string => {
  const destination = mkdtempSync(join(tmpdir(), "hswm-native-replay-fixture-"))
  rmSync(destination, { recursive: true })
  execFileSync("git", ["clone", "--no-hardlinks", root, destination], { encoding: "utf8" })
  return destination
}
const cloneSourceCut = (): string => {
  const destination = cloneFixture()
  execFileSync("git", ["-C", destination, "checkout", "--detach", sourceCut], { encoding: "utf8" })
  return destination
}
const runAt = (repository: string, ...args: string[]): string => invoke(repository, args)

describe("native legacy replay CLI", () => {
  it("uses Python code-point order when canonicalizing Unicode JSON keys", () => {
    expect(renderCanonicalJson({ "𐀀": 2, "": 1 })).toBe('{"":1,"𐀀":2}')
  })

  it("emits source-bound list and verification records", () => {
    const fixture = cloneSourceCut()
    try {
      const listed = JSON.parse(runAt(fixture, "list"))
      expect(listed.schema_version).toBe("hswm-legacy-replay-list/v1")
      expect(listed.count).toBeGreaterThan(0)
      expect(digest(listed)).toBe("4570abbbc41926416271542af9e05a7a3fb9b89d87dbe4b5da9dc48c0fa6e4c2")
      const entry = listed.entries[0]
      const verified = JSON.parse(runAt(fixture, "verify", entry.old_path))
      expect(verified.entries[0]).toMatchObject({ old_path: entry.old_path, verified: true, observed_source_sha256: entry.source_sha256 })
      expect(digest(JSON.parse(runAt(fixture, "verify")))).toBe("0075ca9f638ed3cc7eee57bc28b69250df37b0759fb731fce3b6984bbcc9e123")
    } finally { rmSync(fixture, { recursive: true, force: true }) }
  }, 30_000)

  it("materializes a clean detached standalone replay checkout", () => {
    const listed = JSON.parse(run("list")), destination = mkdtempSync(join(tmpdir(), "hswm-native-replay-"))
    rmSync(destination, { recursive: true })
    try {
      const receipt = JSON.parse(run("materialize", listed.entries[0].old_path, destination))
      expect(receipt).toMatchObject({ status: "VERIFIED", detached_head: true, objects_standalone: true })
      expect(existsSync(join(destination, ".git", "hswm-legacy-replay.json"))).toBe(true)
      expect(execFileSync("git", ["-C", destination, "status", "--porcelain=v1", "--untracked-files=all"], { encoding: "utf8" })).toBe("")
      const unsigned = { ...receipt, receipt_sha256: "" }
      expect(receipt.receipt_sha256).toBe(createHash("sha256").update(JSON.stringify(unsigned)).digest("hex"))
    } finally { rmSync(destination, { recursive: true, force: true }) }
  })

  it("refuses unsafe destinations without creating them", () => {
    const entry = JSON.parse(run("list")).entries[0]
    const outside = mkdtempSync(join(tmpdir(), "hswm-native-refusal-"))
    const target = join(outside, "new")
    try {
      expect(() => run("materialize", entry.old_path, join(root, "forbidden-replay"))).toThrow(/destination may not equal, contain, or be inside repository/)
      expect(() => run("materialize", entry.old_path, `${outside}/../escape`)).toThrow(/destination may not contain/)
      expect(() => run("materialize", entry.old_path, target)).not.toThrow()
      expect(() => run("materialize", entry.old_path, target)).toThrow(/destination must not exist/)
    } finally { rmSync(outside, { recursive: true, force: true }) }
  })

  it("refuses uncanonical and symlinked manifest routes before reading outside the clone", () => {
    const fixture = cloneFixture()
    try {
      const ontology = join(fixture, "ontology/HSWM_REPOSITORY_ONTOLOGY.v1.json")
      const original = JSON.parse(execFileSync("git", ["-C", fixture, "show", "HEAD:ontology/HSWM_REPOSITORY_ONTOLOGY.v1.json"], { encoding: "utf8" }))
      const uncanonical = selectedManifestReferences(JSON.stringify({ ...original, python_root_migrations: ["../outside.json"] }))
      expect(Either.isLeft(uncanonical)).toBe(true)
      writeFileSync(ontology, JSON.stringify({ ...original, python_root_migrations: ["ontology/migrations/linked.json"] }))
      mkdirSync(join(fixture, "ontology/migrations"), { recursive: true })
      symlinkSync("/etc/hosts", join(fixture, "ontology/migrations/linked.json"))
      expect(() => runAt(fixture, "list")).toThrow(/migration manifest must be a regular file/)
    } finally { rmSync(fixture, { recursive: true, force: true }) }
  })

  it("materializes outside a dirty source clone and leaves its staged and untracked state untouched", () => {
    const fixture = cloneFixture()
    const outside = mkdtempSync(join(tmpdir(), "hswm-native-replay-dirty-parent-"))
    const target = join(outside, "replay")
    try {
      writeFileSync(join(fixture, "dirty-staged.txt"), "staged\n")
      execFileSync("git", ["-C", fixture, "add", "dirty-staged.txt"])
      writeFileSync(join(fixture, "dirty-untracked.txt"), "untracked\n")
      const before = execFileSync("git", ["-C", fixture, "status", "--porcelain=v1", "--untracked-files=all"], { encoding: "utf8" })
      const oldPath = JSON.parse(runAt(fixture, "list")).entries[0].old_path
      const receipt = JSON.parse(runAt(fixture, "materialize", oldPath, target))
      const after = execFileSync("git", ["-C", fixture, "status", "--porcelain=v1", "--untracked-files=all"], { encoding: "utf8" })
      expect(after).toBe(before)
      expect(receipt.source_repository).toBe(fixture)
      expect(target.startsWith(fixture)).toBe(false)
      expect(receipt).toMatchObject({ clean_checkout: true, pre_materialization_verification_count: expect.any(Number) })
    } finally { rmSync(fixture, { recursive: true, force: true }); rmSync(outside, { recursive: true, force: true }) }
  })
})
