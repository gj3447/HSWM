/** Source-bound v2 observation-contract probe.  No network or host resolver is used. */
import { createHash } from "node:crypto"
import { existsSync, readFileSync, writeFileSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"

const here = dirname(fileURLToPath(import.meta.url))
const hswmRoot = resolve(here, "../..")
const arg = (name: string) => { const i = process.argv.indexOf(name); return i < 0 ? undefined : process.argv[i + 1] }
const uslRoot = resolve(arg("--usl-root") ?? join(hswmRoot, "..", "USL"))
const out = resolve(arg("--out") ?? join(here, "review_v2_digest_probe_2026-09-08.json"))
const sha256 = (value: Uint8Array | string) => createHash("sha256").update(value).digest("hex")
const inputs = ["src/language/runtime.ts", "src/language/comparison.ts", "src/language/digest.ts", "src/language/model.ts", "src/language/compiler.ts", "docs/OBSERVATION_CONTRACTS.md", "examples/game-workflow-result.json"]
const hashes = () => Object.fromEntries(inputs.map((p) => [p, sha256(readFileSync(join(uslRoot, p)))]))

const main = async () => {
  const before = hashes()
  const load = (p: string) => import(pathToFileURL(join(uslRoot, p)).href)
  const [language, resolveModule, locator, effect] = await Promise.all([
    load("src/language/index.ts"), load("src/resolve.ts"), load("src/locator.ts"),
    import(pathToFileURL(join(uslRoot, "node_modules/effect/dist/esm/index.js")).href),
  ])
  const { Effect, Either, Layer } = effect
  const compile = (source: string) => Either.getOrThrowWith(language.compileSource(source), (error: unknown) => error)
  const source = (description: string) => `usl "0.1";
namespace "audit.v2";
resource left = "https://left.audit/item";
resource right = "https://right.audit/item";
resource unused = "https://unused.audit/item";
meaning relates(subject: url, evidence: url) = ${JSON.stringify(description)} applies "audit scope" check check_evidence(subject, evidence) = "inspect";
link chosen = relates(subject: left, evidence: right);`
  const observe = async (text: string, calls: string[]) => {
    const layer = Layer.succeed(resolveModule.Resolvers, { resolve: (loc: any) => {
      const address = locator.formatLocator(loc); calls.push(address)
      return Effect.succeed({ locator: loc, resolvedLocator: address, contentHash: `sha256:${sha256(address)}`, resolvedAt: "2026-09-08T00:00:00.000Z", guaranteeLevel: "pure", matchCount: 1 })
    } })
    return Effect.runPromise(language.observeProgram(compile(text), { links: ["chosen"], sourceText: text }).pipe(Effect.provide(layer)))
  }
  const callsA: string[] = [], callsB: string[] = []
  const first = await observe(source("left supports right"), callsA)
  const second = await observe(source("left contradicts right"), callsB)
  const semantic = Either.getOrThrowWith(language.compareObservations(first, second), (error: unknown) => error)

  // sourceText is caller-owned mutable data at runtime despite its readonly TS
  // type. Mutate it only after observeProgram has compiled it, while its first
  // injected resolver call is pending.
  const originalText = source("left supports right")
  const oppositeText = source("left contradicts right")
  const mutableOptions: any = { links: ["chosen"], sourceText: originalText }
  let mutationCalls = 0
  const mutatingLayer = Layer.succeed(resolveModule.Resolvers, { resolve: (loc: any) => {
    mutationCalls += 1
    mutableOptions.sourceText = oppositeText
    const address = locator.formatLocator(loc)
    return Effect.succeed({ locator: loc, resolvedLocator: address, contentHash: `sha256:${sha256(address)}`, resolvedAt: "2026-09-08T00:00:00.000Z", guaranteeLevel: "pure", matchCount: 1 })
  } })
  const mutableSourceReport = await Effect.runPromise(language.observeProgram(compile(originalText), mutableOptions).pipe(Effect.provide(mutatingLayer)))

  const forged: any = structuredClone(first)
  forged.planDigest = `sha256:${"1".repeat(64)}`
  forged.meaningsDigest = `sha256:${"2".repeat(64)}`
  forged.sourceDigest = `sha256:${"3".repeat(64)}`
  forged.status = "UNRESOLVED"
  forged.readScope = { links: "not-an-array", allowedLocators: 7, requestedLocators: null, resourceBudget: -1 }
  forged.metrics = { declaredResources: "unknown", selectedResources: -1, uniqueLocators: {}, resolverCalls: null, deniedLocators: "x" }
  forged.links[0].resourcesResolve = false
  forged.links[0].verification[0].evidenceAvailable = false
  forged.links[0].verification[0].status = "EXECUTED_AND_PASSED"
  const { observationDigest: _ignored, ...forgedPayload } = forged
  forged.observationDigest = language.digestJson(forgedPayload)
  const forgedAccepted = Either.isRight(language.validateObservation(forged))
  const forgedComparison = language.compareObservations(first, forged)
  const comparisonAccepted = Either.isRight(forgedComparison)
  const after = hashes()
  const stable = JSON.stringify(before) === JSON.stringify(after)
  const report = {
    schema: "hswm-usl-v2-observation-review/v1", date: "2026-09-08",
    status: stable ? "REPRODUCED_SOURCE_BOUND_REVIEW" : "INVALIDATED_SOURCE_CHANGED_DURING_REVIEW",
    reproduce: { command: "<USL_ROOT>/node_modules/.bin/tsx _research/usl_adapter/review_v2_digest_probe_2026_09_08.ts --usl-root <USL_ROOT>", injected_resolvers_only: true, network_requests: 0, host_resource_reads: 0 },
    source: { package_version: JSON.parse(readFileSync(join(uslRoot, "package.json"), "utf8")).version, git_metadata_present: existsSync(join(uslRoot, ".git")), hashes_before: before, hashes_after: after, hashes_stable: stable, program_sha256: sha256(readFileSync(fileURLToPath(import.meta.url))) },
    probes: {
      semantic_identity: { plan_digest_changed: first.planDigest !== second.planDigest, meaning_digest_changed: first.links[0].meaningDigest !== second.links[0].meaningDigest, contract_digest_changed: first.links[0].contractDigest !== second.links[0].contractDigest, comparison_semantic_contract_changed: semantic.links[0].semanticContractChanged, semantic_truth: semantic.semanticTruth },
      selected_read_scope: { resolver_calls: callsA.sort(), unused_resource_read: callsA.includes("https://unused.audit/item"), selected_resource_count: first.metrics.selectedResources, declared_resource_count: first.metrics.declaredResources },
      mutable_source_text_during_io: {
        resolver_calls_before_return: mutationCalls,
        report_plan_digest_is_original: mutableSourceReport.planDigest === language.planDigest(compile(originalText)),
        report_source_digest_is_opposite: mutableSourceReport.sourceDigest === language.digestSource(oppositeText),
        report_source_digest_is_original: mutableSourceReport.sourceDigest === language.digestSource(originalText),
        interpretation: "sourceText is compiled before resolver IO but read again when sourceDigest is constructed. A caller-held mutable options object can therefore bind an original plan digest to a different source digest in one otherwise genuine report.",
      },
      self_consistent_forged_metadata: { validate_observation_accepts: forgedAccepted, comparison_accepts: comparisonAccepted, comparison_current_plan_digest: comparisonAccepted ? (forgedComparison as any).right.currentPlanDigest : null, forged_aggregate_status: forged.status, forged_read_scope_shape: typeof forged.readScope.links, forged_verification_status: forged.links[0].verification[0].status, interpretation: "The outer digest catches accidental corruption only. validateObservation recompiles selected declarations and checks link/meaning digests, but does not recompute or shape-check aggregate status, readScope, metrics, planDigest, meaningsDigest, sourceDigest, resourcesResolve, or verification fields." },
    },
    assessment: [
      "v2 closes the prior description/provenance omission for reports emitted by observeProgram: selected meaning definitions and plan/source/observation digests are present, selected unused resources are excluded, and cloned input prevents a caller plan mutation during resolver IO from mixing report versions.",
      "The mutable sourceText probe is an exception to that snapshot statement: options.sourceText is not snapshotted and is reread after resolver IO.",
      "The forged-metadata result is a report-validation/provenance limitation for untrusted JSON, not evidence that a genuine observeProgram call misclassifies semantic truth. Documentation already says digests are not authorship, but its stated malformed/inconsistent-report rejection is narrower than a consumer may infer.",
    ],
  }
  writeFileSync(out, `${JSON.stringify(report, null, 2)}\n`)
  if (!stable) process.exitCode = 2
}
void main()
