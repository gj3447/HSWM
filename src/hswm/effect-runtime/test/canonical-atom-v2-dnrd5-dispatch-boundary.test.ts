import { expect, it } from "vitest"
import { readdirSync, readFileSync, statSync } from "node:fs"
import { fileURLToPath } from "node:url"

const SOURCE_ROOT = fileURLToPath(new URL("../src/", import.meta.url))
const INTERNAL_COMMIT_CAPABILITY =
  "commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal"

const sourceFiles = (root: string): ReadonlyArray<string> =>
  readdirSync(root, { withFileTypes: true })
    .flatMap((entry) => {
      const path = `${root}/${entry.name}`
      if (entry.isDirectory()) return sourceFiles(path)
      return entry.isFile() && entry.name.endsWith(".ts") ? [path] : []
    })
    .sort()

it("restricts the root-private durable commit seam to its definition and DNRD-5 Permit dispatcher", () => {
  expect(statSync(SOURCE_ROOT).isDirectory()).toBe(true)
  const importers = sourceFiles(SOURCE_ROOT)
    .map((path) => ({ path, source: readFileSync(path, "utf8") }))
    .filter(({ source }) => source.includes(INTERNAL_COMMIT_CAPABILITY))
    .map(({ path }) => path.slice(SOURCE_ROOT.length).replace(/^\/+/, ""))

  expect(importers).toEqual([
    "canonical-atom-v2-dnrd5-durable-permit.ts",
    "canonical-atom-v2-durable-runtime.ts"
  ])
})
