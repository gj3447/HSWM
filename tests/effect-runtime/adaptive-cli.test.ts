import { execFileSync, spawnSync } from "node:child_process"
import { mkdtempSync, mkdirSync, readFileSync, rmSync, symlinkSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { fileURLToPath } from "node:url"
import { afterAll, beforeAll, expect, it } from "vitest"

const checkout = fileURLToPath(new URL("../../", import.meta.url))
const packageRoot = join(checkout, "src/hswm/effect-runtime")
const fixture = mkdtempSync(join(tmpdir(), "hswm-native-cli-"))
const nodeOnly = join(fixture, "bin")
const live = join(packageRoot, "dist/hswm-live-process.js")
const development = join(packageRoot, "dist/hswm-dev-process.js")
const invoke = (script: string, args: ReadonlyArray<string>) => {
  const result = spawnSync(process.execPath, [script, ...args], {
    cwd: fixture, env: { ...process.env, PATH: nodeOnly }, encoding: "utf8", timeout: 15_000
  })
  return { ...result, json: result.stdout.trim() ? JSON.parse(result.stdout) as Record<string, unknown> : null }
}
const program = (graphId: string, measured = false) => ({
  schema_version: "hswm-adaptive-program/v1", graph_id: graphId, root: "root",
  context_domain: { focus: ["native"] },
  cells: [
    { cell_id: "root", kind: "router", owner: "owner", input_type: "text", output_type: "text" },
    { cell_id: "leaf", kind: "command", owner: "owner", input_type: "text", output_type: "text",
      argv: [process.execPath, "-e", measured ? "process.exitCode=7" : "process.stdout.write('native result')"],
      ...(measured ? { outcome: "exit_code" } : {}) }
  ],
  relations: [{ uid: "native", source: "root", members: ["leaf"], reads: ["focus"], cost_hint: 0 }]
})
beforeAll(() => {
  execFileSync(process.execPath, [join(packageRoot, "node_modules/typescript/bin/tsc"), "-p", "tsconfig.build.json"], { cwd: packageRoot, timeout: 60_000 })
  mkdirSync(nodeOnly)
  symlinkSync(process.execPath, join(nodeOnly, "node"))
}, 65_000)
afterAll(() => rmSync(fixture, { recursive: true, force: true }))

it("runs and learns across native processes with no Python or uv on PATH", () => {
  const manifest = join(fixture, "program.json")
  writeFileSync(manifest, JSON.stringify(program("cli-native")))
  const common = ["--program", manifest, "--workspace", fixture, "--state", "native.sqlite3"]
  const planned = invoke(live, [...common, "plan", "--context", '{"focus":"native"}'])
  expect(planned.status, planned.stderr).toBe(0)
  expect(planned.json?.["backend"]).toBe("typescript-effect")
  const ran = invoke(live, [...common, "run", "--context", '{"focus":"native"}', "--task", "native loop", "--episode", "native-1"])
  expect(ran.status, ran.stderr).toBe(0)
  expect(ran.json?.["leaf_calls"]).toBe(1)
  expect((ran.json?.["result"] as Record<string, unknown>)["output"]).toContain("native result")
  const feedback = invoke(live, [...common, "feedback", "--episode", "native-1", "--success", "true", "--source", "agent(test): verified native output"])
  expect(feedback.status, feedback.stderr).toBe(0)
  expect(feedback.json?.["status"]).toBe("FEEDBACK_RECORDED")
  const status = invoke(live, [...common, "status"])
  expect(status.status, status.stderr).toBe(0)
  expect(status.json?.["relations"]).toEqual(expect.arrayContaining([expect.objectContaining({ observations: 1 })]))
  const replay = invoke(live, [...common, "run", "--context", '{"focus":"native"}', "--task", "native loop", "--episode", "native-1"])
  expect(replay.status, replay.stderr).toBe(0)
  expect(replay.json?.["replayed"]).toBe(true)
}, 30_000)

it("preserves failed task exit status and returns typed JSON for invalid input", () => {
  const manifest = join(fixture, "measured.json")
  writeFileSync(manifest, JSON.stringify(program("cli-measured", true)))
  const common = ["--program", manifest, "--state", "measured.sqlite3"]
  const failed = invoke(live, [...common, "run", "--context", '{"focus":"native"}', "--task", "known failure"])
  expect(failed.status, failed.stderr).toBe(1)
  expect(failed.json?.["status"]).toBe("FAILED")
  const invalid = invoke(live, [...common, "plan", "--context", '{"focus":"native","focus":"native"}'])
  expect(invalid.status).toBe(2)
  const failureLine = invalid.stderr.trim().split("\n").find((line) => line.startsWith("{"))
  expect(JSON.parse(failureLine ?? "null")["backend"]).toBe("typescript-effect")
}, 30_000)

it("executes symlinked npm entries and resolves every built-in profile natively", () => {
  const linked = join(fixture, "hswm-live")
  symlinkSync(live, linked)
  const help = spawnSync(process.execPath, [linked, "--help"], { encoding: "utf8", env: { ...process.env, PATH: nodeOnly } })
  expect(help.status, help.stderr).toBe(0)
  expect(help.stdout).toContain("TypeScript + Effect")
  for (const project of ["버엑시", "maplelineage", "supullim", "reluvator", "hswm"]) {
    const result = invoke(development, [project, "plan", "--workspace", project === "hswm" ? checkout : fixture,
      "--state", join(fixture, `${project}.sqlite3`)])
    expect(result.status, `${project}: ${result.stderr}`).toBe(0)
    expect(result.json?.["backend"]).toBe("typescript-effect")
  }
  expect(readFileSync(join(packageRoot, "bin/hswm-live"), "utf8")).not.toMatch(/python|\buv\b/)
}, 30_000)
