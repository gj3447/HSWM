import { execFileSync, spawnSync } from "node:child_process"
import { createHash } from "node:crypto"
import { existsSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import { Effect, Either } from "effect"
import { describe, expect, it } from "vitest"
import { NodePosixFileSystemLive } from "../src/effect-posix-filesystem.js"
import { runNativeProm9F1Cli } from "../src/native-prom9-f1-cli.js"
import { judgeNativeProm9F1Suite, verifyNativeProm9F1Suite } from "../src/native-prom9-f1-domain.js"
import { decodeNativeTaskJson, renderNativeTaskJson, type TaskJson } from "../src/native-task-json-domain.js"

const runtime = resolve(import.meta.dirname, ".."), root = resolve(runtime, "../../.."), fixtureRoot = resolve(root, "tests/fixtures/prom9_f1_v1")
type FixtureCase = Readonly<{ readonly name: string; readonly mode: string; readonly suite: string; readonly gold: string; readonly expected: Readonly<Record<string, TaskJson>>; readonly expected_canonical: Readonly<Record<string, string>> }>
type Refusal = Readonly<{ readonly name: string; readonly suite: string; readonly gold: string; readonly error_type: string; readonly error: string }>
const fixture = JSON.parse(readFileSync(join(fixtureRoot, "original.v1.json"), "utf8")) as Readonly<{ readonly classification: string; readonly source_pins: Readonly<Record<string, string>>; readonly scaffold_artifact_pins: Readonly<Record<string, string>>; readonly generator_sha256: string; readonly cases: readonly FixtureCase[]; readonly refusals: readonly Refusal[] }>
const load = (path: string): TaskJson => Either.getOrThrow(decodeNativeTaskJson(readFileSync(join(fixtureRoot, path))))
const expectedCanonical = (value: TaskJson): string => renderNativeTaskJson(value)

const emit = (): string => {
  const output = mkdtempSync(join(tmpdir(), "native-prom9-f1-cli-"))
  symlinkSync(join(runtime, "node_modules"), join(output, "node_modules"), "dir")
  const config = join(output, "tsconfig.json")
  writeFileSync(config, JSON.stringify({ extends: join(runtime, "tsconfig.build.json"), compilerOptions: { rootDir: join(runtime, "src"), outDir: output, noEmit: false, declaration: false, declarationMap: false, sourceMap: false }, include: [join(runtime, "src/native-prom9-f1-process.ts")], exclude: [] }))
  execFileSync(join(runtime, "node_modules/.bin/tsc"), ["-p", config], { cwd: runtime })
  return output
}

describe("native PROM-9 F1 adversarial synthetic fixtures", () => {
  it("matches the full Python-oracle canonical judgments across supported, rejected, and development cases", () => {
    expect(fixture.classification).toBe("SYNTHETIC_ENGINEERING_FIXTURE_NOT_RESEARCH")
    for (const [path, digest] of Object.entries(fixture.source_pins)) expect(createHash("sha256").update(readFileSync(join(root, "prom_search_hswm", path))).digest("hex")).toBe(digest)
    for (const [path, digest] of Object.entries(fixture.scaffold_artifact_pins)) expect(createHash("sha256").update(readFileSync(join(root, "_research/prom9_runs/f1-2wiki-dev-r5-live", path))).digest("hex")).toBe(digest)
    expect(fixture.generator_sha256).toMatch(/^[0-9a-f]{64}$/)
    for (const row of fixture.cases) {
      const suite = load(row.suite), gold = load(row.gold)
      expect(verifyNativeProm9F1Suite(suite), row.name).toMatchObject({ _tag: "Right" })
      for (const setting of Object.keys(row.expected)) {
        const [reps, seed] = setting.split(":").map(Number)
        const actual = Either.getOrThrow(judgeNativeProm9F1Suite(suite, gold, reps, seed))
        expect(expectedCanonical(actual), `${row.name}/${setting}`).toBe(row.expected_canonical[setting])
      }
    }
    for (const refusal of fixture.refusals) expect(judgeNativeProm9F1Suite(load(refusal.suite), load(refusal.gold)), refusal.name).toMatchObject({ _tag: "Left", left: { detail: refusal.error } })
  })

  it("exercises emitted CLI write-once publication and preserves conflicts and stale partials", async () => {
    const emitted = emit(), directory = mkdtempSync(join(tmpdir(), "native-prom9-f1-output-")), positive = fixture.cases.find(row => row.name === "positive")!
    const suite = join(fixtureRoot, positive.suite), gold = join(fixtureRoot, positive.gold), output = join(directory, "judgment.json")
    const run = (args: readonly string[]) => spawnSync(process.execPath, [join(emitted, "native-prom9-f1-process.js"), ...args], { encoding: "utf8" })
    try {
      expect(run(["--help"])).toMatchObject({ status: 0 })
      expect(run(["wrong"])).toMatchObject({ status: 2 })
      const first = run(["judge", "--suite", suite, "--gold", gold, "--output", output, "--bootstrap-reps", "101", "--bootstrap-seed", "42"])
      expect(first.status).toBe(0)
      const saved = readFileSync(output, "utf8")
      expect(JSON.parse(saved)).toMatchObject({ verdict: "F1_SUPPORTED_NARROW" })
      const repeated = run(["judge", "--suite", suite, "--gold", gold, "--output", output, "--bootstrap-reps", "101", "--bootstrap-seed", "42"])
      expect(repeated.status).toBe(2)
      expect(repeated.stderr).toContain("refusing to replace output")
      expect(readFileSync(output, "utf8")).toBe(saved)
      const negative = fixture.cases.find(row => row.name === "negative")!
      const conflict = run(["judge", "--suite", join(fixtureRoot, negative.suite), "--gold", join(fixtureRoot, negative.gold), "--output", output, "--bootstrap-reps", "101", "--bootstrap-seed", "42"])
      expect(conflict.status).toBe(2)
      expect(readFileSync(output, "utf8")).toBe(saved)
      const staleOutput = join(directory, "stale.json"), stale = join(directory, `.stale.json.partial-${process.pid}`)
      writeFileSync(stale, "retain this partial")
      const staleResult = await Effect.runPromise(runNativeProm9F1Cli(["judge", "--suite", suite, "--gold", gold, "--output", staleOutput, "--bootstrap-reps", "101", "--bootstrap-seed", "42"]).pipe(Effect.either, Effect.provide(NodePosixFileSystemLive)))
      expect(staleResult).toMatchObject({ _tag: "Left", left: { detail: `stale partial output requires inspection: ${stale}` } })
      expect(readFileSync(stale, "utf8")).toBe("retain this partial")
      expect(existsSync(staleOutput)).toBe(false)
    } finally { rmSync(directory, { recursive: true, force: true }); rmSync(emitted, { recursive: true, force: true }) }
  }, 60_000)
})
