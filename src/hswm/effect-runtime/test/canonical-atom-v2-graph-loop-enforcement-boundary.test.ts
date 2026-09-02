import { readFileSync, readdirSync } from "node:fs"
import { join } from "node:path"
import { fileURLToPath } from "node:url"

import { expect, it } from "@effect/vitest"

import * as PublicApi from "../src/index.js"

const source = (name: string): string =>
  readFileSync(new URL(`../src/${name}`, import.meta.url), "utf8")

const rawSubmitProductionSources = (): ReadonlyArray<string> => {
  const root = fileURLToPath(new URL("../src/", import.meta.url))
  return readdirSync(root, { recursive: true })
    .filter((entry): entry is string => typeof entry === "string" && entry.endsWith(".ts"))
    .filter((entry) => readFileSync(join(root, entry), "utf8").includes("runtime.submit("))
}

it("keeps raw durable mutation outside the published API and production graph-loop paths", () => {
  expect("CanonicalAtomV2DurableRuntime" in PublicApi).toBe(false)
  expect("makeCanonicalAtomV2DurableRuntimeFileLayer" in PublicApi).toBe(
    false
  )
  expect("makeGraphLoopEngineeringFileLayer" in PublicApi).toBe(true)
  expect(source("canonical-atom-v2-graph-loop-engineering.ts")).not.toContain(
    "runtime.submit("
  )
  expect(source("canonical-atom-v2-routing-diagnostic-file.ts")).not.toContain(
    "runtime.submit("
  )
  expect(rawSubmitProductionSources()).toEqual([])
})
