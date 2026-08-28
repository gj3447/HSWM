import { expect, it } from "vitest"
import { readdirSync, readFileSync, statSync } from "node:fs"
import { fileURLToPath } from "node:url"

const SOURCE_ROOT = fileURLToPath(new URL("../src/", import.meta.url))
const INTERNAL_DURABLE_CAPABILITIES = [
  "commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal",
  "recoverCanonicalAtomV2DurableFromDnrd5DispatcherInternal"
] as const

const sourceFiles = (root: string): ReadonlyArray<string> =>
  readdirSync(root, { withFileTypes: true })
    .flatMap((entry) => {
      const path = `${root}/${entry.name}`
      if (entry.isDirectory()) return sourceFiles(path)
      return entry.isFile() && entry.name.endsWith(".ts") ? [path] : []
    })
    .sort()

it("restricts root-private durable seams to their definitions and the DNRD-5 Permit dispatcher", () => {
  expect(statSync(SOURCE_ROOT).isDirectory()).toBe(true)
  const source = sourceFiles(SOURCE_ROOT)
    .map((path) => ({ path, source: readFileSync(path, "utf8") }))
  for (const capability of INTERNAL_DURABLE_CAPABILITIES) {
    const importers = source
      .filter((entry) => entry.source.includes(capability))
      .map(({ path }) => path.slice(SOURCE_ROOT.length).replace(/^\/+/, ""))

    expect(importers).toEqual([
      "canonical-atom-v2-dnrd5-durable-permit.ts",
      "canonical-atom-v2-durable-runtime.ts"
    ])
  }
})
