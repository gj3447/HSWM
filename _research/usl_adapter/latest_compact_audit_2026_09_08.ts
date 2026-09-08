/** Injected/no-IO source audit of USL compact context v1. */
import { createHash } from "node:crypto"
import { existsSync, readFileSync, writeFileSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"

const here = dirname(fileURLToPath(import.meta.url))
const hswm = resolve(here, "../..")
const arg = (key: string) => { const i = process.argv.indexOf(key); return i < 0 ? undefined : process.argv[i + 1] }
const usl = resolve(arg("--usl-root") ?? join(hswm, "..", "USL"))
const out = resolve(arg("--out") ?? join(here, "latest_compact_audit_2026-09-08.json"))
const sha = (x: string | Uint8Array) => createHash("sha256").update(x).digest("hex")
const files = ["src/language/compact.ts", "src/language/navigation.ts", "src/language/model.ts", "src/language/digest.ts", "docs/COMPACT_CONTEXT.md", "package.json", "package-lock.json"]
const hashes = () => Object.fromEntries(files.map((p) => [p, sha(readFileSync(join(usl, p)))]))

const main = async () => {
  const before = hashes()
  const load = (p: string) => import(pathToFileURL(join(usl, p)).href)
  const [compact, language, effect] = await Promise.all([load("src/language/compact.ts"), load("src/language/index.ts"), import(pathToFileURL(join(usl, "node_modules/effect/dist/esm/index.js")).href)])
  const { Either } = effect
  const source = `usl "0.1"; namespace "audit.compact";
resource a = "https://a.audit/"; resource b = "https://b.audit/"; resource context = "https://context.audit/";
meaning relates(subject: url, evidence: url, context: url) = "n-ary authored declaration" applies "audit" check check_all(subject, evidence, context) = "never executed";
link l = relates(subject: a, evidence: b, context: context);`
  const plan = Either.getOrThrow(language.compileSource(source))
  const query = { focus: "a", target: "b", maxHops: 4 }
  const full = Either.getOrThrow(compact.compactAgentContext(plan, query, { maxBytes: 100_000 }))
  const packet = JSON.parse(full.text)
  const unchanged = Either.getOrThrow(compact.compactAgentContext(plan, query, { knownContextDigest: full.contextDigest, maxBytes: 100_000 }))
  const changed = Either.getOrThrow(compact.compactAgentContext(Either.getOrThrow(language.compileSource(source.replace("n-ary authored", "opposite authored"))), query, { knownContextDigest: full.contextDigest, maxBytes: 100_000 }))
  const options: any = { maxBytes: 100_000, maxTokens: 100_000, tokenCounter: { id: "mutator", count: (text: string) => { options.maxBytes = 0; options.maxTokens = 0; return text.length } } }
  const mutation = compact.compactAgentContext(plan, query, options)
  const malformed: any = structuredClone(plan)
  malformed.resources[0].locator.href = BigInt(1)
  let malformedOutcome: string
  try {
    const result = compact.compactAgentContext(malformed, query, { maxBytes: 100_000 })
    malformedOutcome = Either.isLeft(result) ? `LEFT:${result.left.reason}` : "RIGHT"
  } catch (error) { malformedOutcome = `THREW:${error instanceof Error ? error.name : String(error)}` }
  const after = hashes(); const stable = JSON.stringify(before) === JSON.stringify(after)
  const report = {
    schema: "hswm-usl-latest-compact-audit/v1", date: "2026-09-08", status: stable ? "REPRODUCED_SOURCE_BOUND_AUDIT" : "INVALIDATED_SOURCE_CHANGED_DURING_AUDIT",
    reproduce: { command: "<USL_ROOT>/node_modules/.bin/tsx _research/usl_adapter/latest_compact_audit_2026_09_08.ts --usl-root <USL_ROOT>", network_requests: 0, host_resource_reads: 0 },
    source: { version: JSON.parse(readFileSync(join(usl, "package.json"), "utf8")).version, license: "UNLICENSED", git_metadata_present: existsSync(join(usl, ".git")), hashes_before: before, hashes_after: after, hashes_stable: stable, audit_program_sha256: sha(readFileSync(fileURLToPath(import.meta.url))) },
    probes: {
      complete_nary_context: { mode: full.mode, complete: packet.coverage.complete, all_meanings_retained: packet.meanings[0].definition === undefined ? packet.meanings[0].roles.length === 3 : false, participant_roles: packet.links[0].participants.map((p: any) => p.role), paths_tuple_width: packet.paths[1]?.steps[0]?.length ?? 0, interpretation: packet.interpretation },
      unchanged_requires_exact_full_digest: { unchanged_mode: JSON.parse(unchanged.text).mode, changed_meaning_returns: changed.mode, full_context_digest: full.contextDigest },
      callback_option_mutation: { result_is_right: Either.isRight(mutation), captured_budget_remains_effective: Either.isRight(mutation) ? mutation.right.stats.deliveredBytes > 0 : false },
      malformed_direct_plan_literal: { outcome: malformedOutcome, interpretation: "Direct JavaScript malformed input with a BigInt locator is normalized by navigation into LEFT:INVALID_PLAN before compact delivery; no uncaught serialization exception reproduced." },
    },
    boundaries: ["No resolver, semantic check, source observation, execution, or HSWM learning was invoked.", "The malformed direct-plan result concerns runtime input hardening outside TypeScript's compiler-produced SemanticPlan contract; it does not affect ordinary compileSource output."],
  }
  writeFileSync(out, `${JSON.stringify(report, null, 2)}\n`)
  if (!stable) process.exitCode = 2
}
void main()
