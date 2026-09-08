import { mkdtempSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { execFileSync } from "node:child_process"
import { fileURLToPath } from "node:url"
import { expect, it } from "vitest"

const script = fileURLToPath(new URL("../../src/hswm/effect-runtime/scripts/lint-adaptive-functional.mjs", import.meta.url))
const probe = (contents: string) => {
  const root = mkdtempSync(join(tmpdir(), "hswm-adaptive-lint-"))
  try {
    writeFileSync(join(root, "adaptive-domain.ts"), contents)
    try { return execFileSync(process.execPath, [script, "--root", root], { encoding: "utf8" }) }
    catch (cause) { return (cause as { readonly stdout: string }).stdout }
  } finally { rmSync(root, { recursive: true, force: true }) }
}

it("rejects module mutation and Effect aliases", () => {
  const output = probe('import { Effect as Fx } from "effect"; export let state = 0; Fx.runSync(Fx.void)')
  expect(output).toContain("MODULE_MUTABLE")
  expect(output).toContain("EFFECT_RUN")
})

it("accepts a pure Either function", () => {
  const output = probe('import { Either } from "effect"; export const parse = (value: string) => Either.right(value)')
  expect(JSON.parse(output).violations).toEqual([])
})

it("rejects submodule runners, namespace runners, var and filesystem subpaths", () => {
  const output = probe('import * as Fx from "effect/Effect"; import * as E from "effect"; import { runSync as run } from "effect/Effect"; import fs from "node:fs/promises"; export var state = 0; Fx.runSync(Fx.void); E.Effect.runSync(E.Effect.void); run(Fx.void)')
  const violations = JSON.parse(output).violations as ReadonlyArray<{ readonly rule: string }>
  expect(violations.filter((item) => item.rule === "EFFECT_RUN")).toHaveLength(3)
  expect(violations.some((item) => item.rule === "MODULE_MUTABLE")).toBe(true)
  expect(violations.some((item) => item.rule === "DOMAIN_IO_IMPORT")).toBe(true)
})
