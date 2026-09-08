/**
 * Regenerate the source-bound, injected-only USL v2 adapter fixture.
 *
 * Run from the HSWM checkout:
 *   <USL_ROOT>/node_modules/.bin/tsx _research/usl_adapter/regenerate_preview_v2_2026_09_08.ts \
 *     --usl-root <USL_ROOT> --out _research/usl_adapter/examples/preview.v2.json
 */
import { createHash } from "node:crypto"
import { readFileSync, writeFileSync } from "node:fs"
import { dirname, resolve } from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"

const here = dirname(fileURLToPath(import.meta.url))
const repository = resolve(here, "../..")
const argument = (name: string) => {
  const index = process.argv.indexOf(name)
  return index < 0 ? undefined : process.argv[index + 1]
}
const uslRoot = resolve(argument("--usl-root") ?? resolve(repository, "../USL"))
const sourcePath = resolve(argument("--source") ?? resolve(here, "examples/development_reference.v2.usl"))
const outputPath = resolve(argument("--out") ?? resolve(here, "examples/preview.v2.json"))
const sha256 = (value: string) => createHash("sha256").update(value).digest("hex")
const sorted = (value: unknown): unknown => Array.isArray(value) ? value.map(sorted) : value !== null && typeof value === "object"
  ? Object.fromEntries(Object.entries(value as Record<string, unknown>).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0).map(([key, child]) => [key, sorted(child)]))
  : value
const hswmDigest = (value: unknown) => sha256(JSON.stringify(sorted(value)))

const main = async () => {
  const [language, resolver, locator, effect] = await Promise.all([
    import(pathToFileURL(resolve(uslRoot, "src/language/index.ts")).href),
    import(pathToFileURL(resolve(uslRoot, "src/resolve.ts")).href),
    import(pathToFileURL(resolve(uslRoot, "src/locator.ts")).href),
    import(pathToFileURL(resolve(uslRoot, "node_modules/effect/dist/esm/index.js")).href),
  ])
  const source = readFileSync(sourcePath, "utf8")
  const plan = effect.Either.getOrThrowWith(language.compileSource(source), (error: unknown) => error)
  const resolvedAt = "2026-09-08T12:00:00.000Z"
  const injected = (item: any) => {
    const resolvedLocator = locator.formatLocator(item)
    return {
      locator: item,
      resolvedLocator,
      contentHash: sha256(`injected-usl-v2:${resolvedLocator}`),
      resolvedAt,
      guaranteeLevel: "pure",
      matchCount: 1,
    }
  }
  const selected = plan.links.find((link: any) => link.name === "development")
  if (!selected) throw new Error("development link missing")
  const meaning = plan.meanings.find((item: any) => item.name === selected.meaning)
  if (!meaning?.grounded) throw new Error("development grounding missing")
  const selectedLocators = [
    ...selected.participants.map((item: any) => locator.formatLocator(plan.resources.find((resource: any) => resource.name === item.resource).locator)),
    locator.formatLocator(meaning.grounded),
  ]
  const layer = effect.Layer.succeed(resolver.Resolvers, {
    resolve: (item: any, options: { allowedLocators?: readonly string[] } | undefined) => {
      if (!options?.allowedLocators?.includes(resolver.locatorKey(item))) {
        return effect.Effect.fail(new resolver.ResolveError({ kind: item.kind, locator: locator.formatLocator(item), reason: "DENIED", detail: "fixture allowlist" }))
      }
      return effect.Effect.succeed(injected(item))
    },
  })
  const report = await effect.Effect.runPromise(language.observeProgram(plan, {
    links: ["development"],
    allowedLocators: selectedLocators,
    maxResources: selectedLocators.length,
    sourceText: source,
  }).pipe(effect.Effect.provide(layer)))
  if (report.links.length !== 1 || report.links[0].name !== "development" || report.resources.length !== selected.participants.length || report.groundings.length !== 1 || report.metrics.resolverCalls !== selectedLocators.length) {
    throw new Error("unexpected selected observation scope")
  }
  const resourcePins = report.resources.map((row: any) => ({ name: row.name, content_hash: row.resolution.contentHash, resolved_locator: row.resolution.resolvedLocator }))
  const grounding = report.groundings[0]
  resourcePins.push({ name: `meaning:${grounding.name}`, content_hash: grounding.resolution.contentHash, resolved_locator: grounding.resolution.resolvedLocator })
  const policy = {
    schema_version: "hswm-usl-observation-policy/v2",
    namespace: plan.namespace,
    plan_digest: hswmDigest(plan),
    usl_plan_digest: report.planDigest,
    source_digest: report.sourceDigest,
    max_age_seconds: 120,
    bindings: [{ link: "development", role: "usl", field: "references_resolve" }],
    resources: resourcePins,
  }
  const preview = {
    domain: [{ role: "usl", field: "references_resolve", values: [false, true] }],
    relation: {
      uid: "hswm-usl-development-reference",
      revision: "r1",
      ast: { op: "eq", left: { role: "usl", field: "references_resolve" }, right: true },
      source: "authored:development-reference-policy",
    },
    action: "inspect-development-references",
    checks: {
      scope: "hswm.usl.development.example",
      expected_scope: "hswm.usl.development.example",
      revision: "authored-observation-r1",
      expected_revision: "authored-observation-r1",
      now: 1788868860.0,
      allowed_reads: [["usl", "references_resolve"]],
      permitted: ["inspect-development-references", "OBSERVE"],
      available: ["inspect-development-references", "OBSERVE"],
      costs: { "inspect-development-references": 1, "OBSERVE": 1 },
      budget: 2,
      source: "authored:usl-adapter-fixture",
    },
  }
  writeFileSync(outputPath, `${JSON.stringify({ plan, report, policy, preview }, null, 2)}\n`, { encoding: "utf8", flag: "w" })
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.stack ?? error.message : String(error))
  process.exitCode = 1
})
