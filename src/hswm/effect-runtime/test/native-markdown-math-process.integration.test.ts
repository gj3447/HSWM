import { execFileSync, spawnSync } from "node:child_process"
import { mkdtemp, mkdir, readFile, writeFile, rm } from "node:fs/promises"
import { mkdtempSync, readFileSync, symlinkSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { describe, expect, it } from "vitest"

const runtime = new URL("../", import.meta.url).pathname
interface ProcessFixture { readonly source_commit: string; readonly inputs: Readonly<Record<string, string>>; readonly directory_report: unknown; readonly derived: Readonly<Record<string, string>>; readonly single_report: unknown }
const fixture = JSON.parse(readFileSync(join(runtime, "test/fixtures/native-markdown-math-process.v1.json"), "utf8")) as ProcessFixture
/** The emitted process has no external runtime dependency, including Python. */
const run = (args: string[], cwd: string) => spawnSync(process.execPath, args, { cwd, encoding: "utf8", env: { PATH: "" } })
let emitted = ""
const emit = (): string => {
  if (emitted !== "") return emitted
  const output = mkdtempSync(join(tmpdir(), "native-markdown-math-emit-"))
  symlinkSync(join(runtime, "node_modules"), join(output, "node_modules"), "dir")
  const config = join(output, "tsconfig.json")
  writeFileSync(config, JSON.stringify({ extends: join(runtime, "tsconfig.build.json"), compilerOptions: { rootDir: join(runtime, "src"), outDir: output, noEmit: false, declaration: false, declarationMap: false, sourceMap: false }, include: [join(runtime, "src/native-markdown-math-process.ts")], exclude: [] }))
  execFileSync(join(runtime, "node_modules/.bin/tsc"), ["-p", config], { cwd: runtime })
  emitted = output
  return output
}
describe("native Markdown math process", () => {
  it("matches Python reports and derived projections without source mutation", async () => {
    const emitted = emit()
    expect(fixture.source_commit).toBe("5870f1ead147f5d868aaa0a8d2595b5f1556c533")
    const work = await mkdtemp(join(tmpdir(), "hswm-markdown-math-"))
    try {
      await mkdir(join(work, "input"))
      for (const [path, contents] of Object.entries(fixture.inputs)) await writeFile(join(work, path), contents)
      const node = run([join(emitted, "native-markdown-math-process.js"), "input", "--output-dir", "native-out"], work)
      expect(node.status).toBe(0)
      expect(JSON.parse(node.stdout)).toEqual(fixture.directory_report)
      for (const [path, expected] of Object.entries(fixture.derived)) expect(await readFile(join(work, "native-out", path), "utf8")).toBe(expected)
      expect(await readFile(join(work, "input", "one.md"), "utf8")).toContain("\\operatorname")
      const nodeSingle = run([join(emitted, "native-markdown-math-process.js"), "input/one.md", "--output", "native-single.md"], work)
      expect(JSON.parse(nodeSingle.stdout)).toEqual(fixture.single_report)
      expect(await readFile(join(work, "native-single.md"), "utf8")).toBe(fixture.derived["input/one.md"])
      expect(run([join(emitted, "native-markdown-math-process.js"), "input/one.md", "input/two.md", "--output", "bad.md"], work).status).toBe(2)
      expect(run([join(emitted, "native-markdown-math-process.js"), "input/one.md", "--output", "input/one.md"], work).status).toBe(2)
      expect(run([join(emitted, "native-markdown-math-process.js"), "--help"], work).stdout).toContain("hswm-markdown-math")
    } finally { await rm(work, { recursive: true, force: true }) }
  }, 120_000)
})
