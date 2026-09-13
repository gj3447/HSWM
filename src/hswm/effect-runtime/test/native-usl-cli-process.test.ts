import { mkdtempSync, readFileSync, symlinkSync, writeFileSync } from "node:fs"
import { execFileSync, spawnSync } from "node:child_process"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import { beforeAll, expect, it } from "vitest"

const runtime = resolve(import.meta.dirname, ".."), root = resolve(runtime, "../../.."), node = process.execPath
let emitted: string | undefined
const emit = (): string => {
  if (emitted !== undefined) return emitted
  const out = mkdtempSync(join(tmpdir(), "native-usl-cli-"));
  symlinkSync(join(runtime, "node_modules"), join(out, "node_modules"), "dir");
  const config = join(out, "tsconfig.json");
  writeFileSync(config, JSON.stringify({extends: join(runtime, "tsconfig.build.json"), compilerOptions: {rootDir: join(runtime,"src"), outDir: out, noEmit: false, declaration: false, declarationMap: false, sourceMap: false}, include: [join(runtime, "src/native-usl-process.ts")], exclude: []}));
  execFileSync(join(runtime, "node_modules/.bin/tsc"), ["-p", config], {cwd: runtime});
  emitted = out;
  return out;
}
beforeAll(() => { emit() }, 30_000)
const fixture = (version: "v1" | "v2") => JSON.parse(readFileSync(resolve(root, `_research/usl_adapter/examples/preview.${version}.json`), "utf8")) as Record<string, unknown>
const project = (value: Record<string, unknown>) => { const checks = (value["preview"] as Record<string, Record<string, unknown>>)["checks"]!; return { plan: value["plan"], report: value["report"], policy: value["policy"], allowed_reads: checks["allowed_reads"], now: checks["now"], revision: checks["revision"] } }

it("emitted process preserves project/preview flags and JSON refusal behavior", () => {
  const out = emit(), directory = mkdtempSync(join(tmpdir(), "native-usl-input-")), projectPath = join(directory, "project.json"), previewPath = join(directory, "preview.json")
  writeFileSync(projectPath, JSON.stringify(project(fixture("v2")))); writeFileSync(previewPath, JSON.stringify(fixture("v1")))
  const run = (args: readonly string[]) => spawnSync(node, [join(out, "native-usl-process.js"), ...args], { encoding: "utf8" })
  const projected = run(["project", "--request", projectPath]), previewed = run(["preview", "--request", previewPath]), bad = run(["adapt", "--request", projectPath])
  expect(projected.status).toBe(0); expect(JSON.parse(projected.stdout)).toMatchObject({ schema_version: "hswm-usl-observation-projection/v2", status: "READY" })
  expect(previewed.status).toBe(0); expect(JSON.parse(previewed.stdout)).toMatchObject({ schema_version: "hswm-usl-preview/v1", preview: { status: "DESIGN_ONLY_NO_EXECUTION" } })
  expect(bad.status).toBe(2); expect(JSON.parse(bad.stderr)).toMatchObject({ status: "REJECTED" })
})
it("keeps a raw v1 decimal token through the emitted process digest and rejects it on the v2 wire", () => {
  const out = emit(), directory = mkdtempSync(join(tmpdir(), "native-usl-number-")), v1Path = join(directory, "v1.json"), v2Path = join(directory, "v2.json")
  const v1 = project(fixture("v1")); ((v1["policy"] as Record<string, unknown>)["max_age_seconds"]) = 60
  const rawV1 = JSON.stringify(v1).replace('"max_age_seconds":60', '"max_age_seconds":60.0'); writeFileSync(v1Path, rawV1)
  const v2 = project(fixture("v2")); const rawV2 = JSON.stringify(v2).replace('"resourceBudget":4', '"resourceBudget":4.0'); writeFileSync(v2Path, rawV2)
  const run = (args: readonly string[]) => spawnSync(node, [join(out, "native-usl-process.js"), ...args], { encoding: "utf8" })
  const decimal = run(["project", "--request", v1Path]), refused = run(["project", "--request", v2Path])
  expect(decimal.status).toBe(0); expect(JSON.parse(decimal.stdout)).toMatchObject({ status: "UNRESOLVED", policy_digest: "2ef0dd690c41d5ee5c71586d0124f55ed308d0f23944d901c10a72ed5059a264", observations: [] })
  expect(refused.status).toBe(2); expect(JSON.parse(refused.stderr)).toMatchObject({ status: "REJECTED" })
})
