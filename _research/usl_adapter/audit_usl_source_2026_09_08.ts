/**
 * Source-bound, injected-resolver audit of USL v0.3 behavior relevant to the
 * narrow HSWM adapter boundary.  It intentionally does not contact a host,
 * network endpoint, or HSWM service.
 *
 * Run:
 *   /home/lagyeongjun/CD/USL/node_modules/.bin/tsx \
 *     _research/usl_adapter/audit_usl_source_2026_09_08.ts \
 *     --usl-root /home/lagyeongjun/CD/USL
 */
import { createHash } from "node:crypto"
import { existsSync, readFileSync, readdirSync, writeFileSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"

const here = dirname(fileURLToPath(import.meta.url))
const repoRoot = resolve(here, "../..")
const argument = (name: string) => {
  const index = process.argv.indexOf(name)
  return index < 0 ? undefined : process.argv[index + 1]
}
const uslRoot = resolve(argument("--usl-root") ?? join(repoRoot, "..", "USL"))
const outputPath = resolve(argument("--out") ?? join(here, "source_audit_2026-09-08.json"))
const sha256 = (value: string | Uint8Array) => createHash("sha256").update(value).digest("hex")
const sourceFiles = (relative: string): string[] => readdirSync(join(uslRoot, relative), { withFileTypes: true })
  .flatMap((entry) => entry.isDirectory() ? sourceFiles(`${relative}/${entry.name}`)
    : entry.isFile() && entry.name.endsWith(".ts") ? [`${relative}/${entry.name}`] : [])
const sourcePaths = [...sourceFiles("src"), "package.json", "package-lock.json"].sort()
const sourceHashes = () => Object.fromEntries(sourcePaths.map((relative) => [relative, sha256(readFileSync(join(uslRoot, relative)))]))
const main = async () => {
const before = sourceHashes()
const load = async (relative: string) => import(pathToFileURL(join(uslRoot, relative)).href)
const [language, resolver, locator, effect] = await Promise.all([
  load("src/language/index.ts"), load("src/resolve.ts"), load("src/locator.ts"),
  import(pathToFileURL(join(uslRoot, "node_modules/effect/dist/esm/index.js")).href),
])
const { Effect, Either, Layer } = effect
const compile = (source: string) => Either.getOrThrowWith(language.compileSource(source), (error: unknown) => error)
const fixedAt = "2026-09-08T00:00:00.000Z"
const injectedResolution = (loc: any) => ({
  locator: loc, resolvedLocator: locator.formatLocator(loc), contentHash: sha256(locator.formatLocator(loc)),
  resolvedAt: fixedAt, guaranteeLevel: "pure", matchCount: 1,
})
const runObserve = async (plan: any, behavior: (loc: any) => any) => {
  const layer = Layer.succeed(resolver.Resolvers, { resolve: (loc: any) => behavior(loc) })
  return Effect.runPromise(language.observeProgram(plan).pipe(Effect.provide(layer)))
}
const urlProgram = (description: string, namespace = "audit.same") => `
usl "0.1";
namespace "${namespace}";
resource alpha = "https://alpha.audit/item";
resource beta = "https://beta.audit/item";
meaning relates(subject: url, evidence: url) = ${JSON.stringify(description)};
link chosen = relates(subject: alpha, evidence: beta);
`

const inversionLeft = await runObserve(compile(urlProgram("alpha supports beta")), (loc: any) => Effect.succeed(injectedResolution(loc)))
const inversionRight = await runObserve(compile(urlProgram("alpha contradicts beta")), (loc: any) => Effect.succeed(injectedResolution(loc)))

const unusedPlan = compile(`
usl "0.1";
namespace "audit.unused";
resource selected_one = "https://one.audit/item";
resource selected_two = "https://two.audit/item";
resource unused = "https://unused.audit/item";
meaning relates(subject: url, evidence: url) = "authored relation";
link selected = relates(subject: selected_one, evidence: selected_two);
`)
const unusedCalls: string[] = []
const unusedObservation = await runObserve(unusedPlan, (loc: any) => {
  unusedCalls.push(locator.formatLocator(loc))
  return Effect.succeed(injectedResolution(loc))
})

const groundPlan = compile(`
usl "0.1";
namespace "audit.grounding";
resource left = "https://left.audit/item";
resource right = "https://right.audit/item";
meaning grounded(subject: url, evidence: url) = "authored relation" grounded "kg://canonical-neo4j/sym:Concept:audit-ground";
link selected = grounded(subject: left, evidence: right);
`)
const groundingObservation = await runObserve(groundPlan, (loc: any) => loc.kind === "kg"
  ? Effect.fail(new resolver.ResolveError({ kind: "kg", locator: locator.formatLocator(loc), reason: "ORPHAN", detail: "injected missing grounding" }))
  : Effect.succeed(injectedResolution(loc)))

const rolePlan = compile(`
usl "0.1";
namespace "audit.roles";
resource a = "https://a.audit/item";
resource b = "https://b.audit/item";
resource c = "https://c.audit/item";
meaning tri(subject: url, evidence: url, context: url) = "three roles";
link reordered = tri(context: c, subject: a, evidence: b);
`)

const kgLocator = Either.getOrThrowWith(locator.parseLocator("kg://canonical-neo4j/sym:Concept:audit-hash"), (error: unknown) => error)
const kgRecord = (description: string, projection: string) => ({
  uid: "sym:Concept:audit-hash", uid_match_count: 1, name: "audit_hash", title: "Audit hash",
  legacy_labels: ["Concept"], target_version: "v1", authority_class: "SECONDARY_AI",
  canonical_scope: "PENDING", description, ontology_projection_sha256: projection,
})
const resolveKgWithRecord = async (record: object) => {
  let calls = 0
  const config = {
    hostname: "audit", gitRepos: {}, kgMcpUrl: "http://audit.invalid/mcp", timeoutMs: 1_000,
    fetchImpl: async () => {
      calls += 1
      return new Response(JSON.stringify({ jsonrpc: "2.0", id: 1, result: { content: [{ type: "text", text: JSON.stringify([record]) }] } }), { status: 200 })
    },
  }
  const result = await Effect.runPromise(resolver.resolveWith(config)(kgLocator))
  return { contentHash: result.contentHash, calls }
}
const kgFirst = await resolveKgWithRecord(kgRecord("first semantic contract", "a".repeat(64)))
const kgSecond = await resolveKgWithRecord(kgRecord("opposite semantic contract", "b".repeat(64)))

const pkg = JSON.parse(readFileSync(join(uslRoot, "package.json"), "utf8"))
const ownSourceHash = sha256(readFileSync(fileURLToPath(import.meta.url)))
const after = sourceHashes()
const stable = JSON.stringify(before) === JSON.stringify(after)
const report = {
  schema: "hswm-usl-source-audit/v1",
  date: "2026-09-08",
  status: stable ? "REPRODUCED_SOURCE_BOUND_AUDIT_NOT_HSWM_EFFICACY" : "INVALIDATED_SOURCE_CHANGED_DURING_AUDIT",
  reproduction: { command: "<USL_ROOT>/node_modules/.bin/tsx _research/usl_adapter/audit_usl_source_2026_09_08.ts --usl-root <USL_ROOT>", injected_only: true, network_requests: 0, host_resource_reads: 0 },
  source: { package_name: pkg.name, package_version: pkg.version, license: pkg.license, private: pkg.private, git_commit: null, git_metadata_present: existsSync(join(uslRoot, ".git")), hashes_before: before, hashes_after: after, hashes_stable: stable, audit_program_sha256: ownSourceHash },
  runtime: { node: process.version, tsx: process.env["TSX_VERSION"] ?? "invoked from installed USL tsx" },
  probes: {
    meaning_description_inversion: {
      observation_identical: JSON.stringify(inversionLeft) === JSON.stringify(inversionRight),
      schema: inversionLeft.schema, semantic_truth: inversionLeft.semanticTruth,
      plan_digest_field_present: Object.hasOwn(inversionLeft, "planDigest"),
      interpretation: "Observed program reports omit authored meaning descriptions and a plan digest; this is an HSWM adapter provenance gap, not a claim that USL evaluates semantic truth.",
    },
    unused_declared_resource: {
      selected_link_participants: unusedObservation.links[0].participants.map((p: any) => p.resource),
      resolver_call_count: unusedCalls.length, resolver_call_locators: unusedCalls.sort(),
      all_declared_resources_observed: unusedCalls.length === 3,
      interpretation: "observeProgram resolves the plan resource set, including an unused declaration. A caller needs its own bounded plan/resource allowlist if that distinction matters.",
    },
    orphan_grounding: {
      program_status: groundingObservation.status, grounding_status: groundingObservation.groundings[0].status,
      link_resources_resolve: groundingObservation.links[0].resourcesResolve,
      semantic_truth: groundingObservation.semanticTruth,
      interpretation: "Resource reachability and grounding reachability are separately represented. Treating resourcesResolve as semantic truth would be an adapter error.",
    },
    declared_role_order: {
      supplied_order: ["context", "subject", "evidence"],
      compiled_order: rolePlan.links[0].participants.map((p: any) => p.role),
      preserves_declared_order: JSON.stringify(rolePlan.links[0].participants.map((p: any) => p.role)) === JSON.stringify(["subject", "evidence", "context"]),
      interpretation: "Positive control: current compiler preserves the meaning declaration role order for n-ary links.",
    },
    kg_metadata_content_hash: {
      first_content_hash: kgFirst.contentHash, second_content_hash: kgSecond.contentHash,
      hashes_equal: kgFirst.contentHash === kgSecond.contentHash, fetch_calls: [kgFirst.calls, kgSecond.calls],
      changed_fields: ["description", "ontology_projection_sha256"],
      interpretation: "The bounded v0.1 resolver fingerprint intentionally excludes these fields. It cannot by itself pin an unchanged HSWM semantic contract.",
    },
  },
  boundaries: [
    "This audit does not test HSWM performance, learning, admission, effects, or truth of any relation.",
    "USL runtime labels link semanticTruth NOT_EVALUATED; endpoint resolution is not semantic verification.",
    "The current resolver constructs an MCP tools/call request with protocol version 2026-07-28 without an SDK or initialize exchange in this code path; protocol conformance was not assessed here.",
  ],
}
writeFileSync(outputPath, `${JSON.stringify(report, null, 2)}\n`)
if (!stable) process.exitCode = 2
}
void main()
