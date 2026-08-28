import { expect, it } from "@effect/vitest"
import { execFileSync, spawnSync } from "node:child_process"
import { readdirSync } from "node:fs"
import { fileURLToPath, pathToFileURL } from "node:url"

const packageRoot = fileURLToPath(new URL("..", import.meta.url))
const script = fileURLToPath(new URL("../scripts/emit-dnrd5-source-closure.mjs", import.meta.url))

const emit = (): string => execFileSync(process.execPath, [script], {
  cwd: packageRoot,
  encoding: "utf8",
  stdio: ["ignore", "pipe", "pipe"]
})

const scan = (source: string) => spawnSync(process.execPath, [
  "--input-type=module",
  "--eval",
  [
    "import ts from \"typescript\";",
    `import { assertStaticClosureSyntax } from ${JSON.stringify(pathToFileURL(script).href)};`,
    `assertStaticClosureSyntax(ts.createSourceFile(${JSON.stringify("src/closure-mutation.ts")}, ${JSON.stringify(source)}, ts.ScriptTarget.Latest, true));`
  ].join("\n")
], {
  cwd: packageRoot,
  encoding: "utf8"
})

it("emits a canonical local-only source/build/import closure", () => {
  const raw = emit()
  expect(emit()).toBe(raw)
  expect(raw.endsWith("\n")).toBe(false)
  expect(readdirSync(packageRoot).filter((name) => name.startsWith(".dnrd5-source-closure-out-"))).toEqual([])
  const closure = JSON.parse(raw) as {
    readonly contractVersion: string
    readonly dispatchAuthorized: boolean
    readonly dispatchBudget: number
    readonly emitted: { readonly files: ReadonlyArray<unknown>; readonly rootSha256: string }
    readonly resolvedExternalFiles: ReadonlyArray<unknown>
    readonly sources: ReadonlyArray<{
      readonly path: string
      readonly imports: ReadonlyArray<{
        readonly kind: string
        readonly names: ReadonlyArray<{ readonly imported: string }>
        readonly typeOnly: boolean
      }>
    }>
    readonly sourceFreezeEligible: boolean
    readonly terminal: string
  }
  expect(closure.contractVersion).toBe("hswm-dnrd5-local-source-build-import-closure/v1")
  expect(closure.dispatchAuthorized).toBe(false)
  expect(closure.dispatchBudget).toBe(0)
  expect(closure.emitted.files.length).toBeGreaterThan(0)
  expect(closure.emitted.rootSha256).toMatch(/^[0-9a-f]{64}$/)
  expect(closure.resolvedExternalFiles.length).toBeGreaterThan(0)
  expect(closure.sourceFreezeEligible).toBe(false)
  expect(closure.terminal).toBe("LOCAL_SOURCE_BUILD_IMPORT_CLOSURE_ONLY_NOT_SOURCE_A_PROVIDER_OR_EFFICACY")
  const imports = closure.sources.flatMap((source) => source.imports)
  expect(imports.some((item) => item.kind === "type-import" && item.typeOnly)).toBe(true)
  expect(imports.some((item) => item.kind === "runtime-dynamic-import" && !item.typeOnly)).toBe(false)
  const durableDispatcherImporters = closure.sources.filter((source) =>
    source.imports.some((item) =>
      item.names.some((name) =>
        name.imported === "commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal" ||
        name.imported === "recoverCanonicalAtomV2DurableFromDnrd5DispatcherInternal"
      )
    )
  )
  expect(durableDispatcherImporters.map((source) => source.path)).toEqual([
    "src/canonical-atom-v2-dnrd5-durable-permit.ts"
  ])
}, 120_000)

it("refuses dynamically composed and constructor-chain loader properties while allowing ordinary indexing", () => {
  for (const [source, detail] of [
    ["export const mutation = (globalThis as Record<string, unknown>)[\"ev\" + \"al\"]", "computed property access"],
    ["export const mutation = (globalThis as Record<string, unknown>)[\"req\" + \"uire\"]", "computed property access"],
    ["export const mutation = (() => {})[\"constructor\"](\"return process\")()", "indirect runtime loader"],
    ["export const mutation = ({} as Record<string, unknown>)[\"constructor\"][\"constructor\"]", "indirect runtime loader"],
    ["export const mutation = ({} as Record<string, unknown>)[String(\"constructor\")]", "computed property access"]
  ] as const) {
    const result = scan(source)
    expect(result.status).toBe(1)
    expect(result.stderr).toContain("RUNTIME_LOADER_FORBIDDEN")
    expect(result.stderr).toContain(detail)
  }
  const allowed = scan("export const ordinary = [\"ok\"][0]; export const selected = ordinary[0]")
  expect(allowed.status).toBe(0)
}, 30_000)
