/**
 * Local adversarial check of the installed USL v2 observation validator.
 *
 * This does not contact a resolver or run declared checks.  It begins with the
 * injected fixture, resigns deliberately altered JSON, and records which
 * layer accepts it.  Run from HSWM:
 *   ../USL/node_modules/.bin/tsx _research/usl_adapter/latest_observation_audit_2026_09_08.ts \
 *     --usl-root ../USL --out _research/usl_adapter/latest_observation_audit_2026_09_08.json
 */
import { createHash } from "node:crypto"
import { execFileSync } from "node:child_process"
import { readFileSync, writeFileSync } from "node:fs"
import { dirname, resolve } from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, "../..")
const arg = (name: string) => {
  const index = process.argv.indexOf(name)
  return index < 0 ? undefined : process.argv[index + 1]
}
const uslRoot = resolve(arg("--usl-root") ?? resolve(root, "../USL"))
const fixturePath = resolve(arg("--fixture") ?? resolve(here, "examples/preview.v2.json"))
const outputPath = resolve(arg("--out") ?? resolve(here, "latest_observation_audit_2026_09_08.json"))
const sha256 = (text: string) => createHash("sha256").update(text).digest("hex")
const jsDigest = (value: unknown) => `sha256:${sha256(JSON.stringify(value))}`
const clone = <T>(value: T): T => structuredClone(value)

const resign = (report: Record<string, unknown>) => {
  const { observationDigest: _discard, ...payload } = report
  report.observationDigest = jsDigest(payload)
}

const main = async () => {
  const language = await import(pathToFileURL(resolve(uslRoot, "src/language/index.ts")).href)
  const fixture = JSON.parse(readFileSync(fixturePath, "utf8"))
  const validate = (report: unknown) => language.validateObservation(report)._tag === "Right"
  const hswmAccepts = (value: unknown) => {
    const code = [
      "import json, sys",
      "from hswm.infrastructure.usl_adapter import adapt_usl",
      "from hswm.cells.conditional import Reject",
      "v=json.load(sys.stdin)",
      "try:",
      " r=adapt_usl(v['plan'],v['report'],v['policy'],allowed_reads={tuple(x) for x in v['preview']['checks']['allowed_reads']},now=v['preview']['checks']['now'],revision='audit')",
      " print(json.dumps({'accepted': True, 'status':r['status']}))",
      "except Reject as e: print(json.dumps({'accepted': False, 'reason':str(e)}))",
    ].join("\n")
    return JSON.parse(execFileSync("python3", ["-c", code], {
      cwd: root, input: JSON.stringify(value), encoding: "utf8",
      env: { ...process.env, PYTHONPATH: `${resolve(root, "src")}${process.env.PYTHONPATH ? `:${process.env.PYTHONPATH}` : ""}` },
    })) as { accepted: boolean; status?: string; reason?: string }
  }
  const base = clone(fixture)
  const cases: Array<{ id: string; usl_validator_accepts: boolean; hswm_adapter: object; interpretation: string }> = []
  cases.push({ id: "baseline", usl_validator_accepts: validate(base.report), hswm_adapter: hswmAccepts(base), interpretation: "expected valid injected fixture" })

  const forgedExecution = clone(fixture)
  forgedExecution.report.links[0].verification[0].status = "EXECUTED"
  resign(forgedExecution.report)
  cases.push({ id: "forged_execution_after_resign", usl_validator_accepts: validate(forgedExecution.report), hswm_adapter: hswmAccepts(forgedExecution), interpretation: "must reject; a digest recomputation cannot promote a declared check" })

  const forgedCount = clone(fixture)
  forgedCount.report.metrics.resolverCalls = 99
  resign(forgedCount.report)
  cases.push({ id: "forged_resolver_call_count_after_resign", usl_validator_accepts: validate(forgedCount.report), hswm_adapter: hswmAccepts(forgedCount), interpretation: "must reject; report metrics are recomputed from selected scope" })

  const symbolicHash = clone(fixture)
  for (const row of [...symbolicHash.report.resources, ...symbolicHash.report.groundings]) row.resolution.contentHash = "content"
  for (const pin of symbolicHash.policy.resources) pin.content_hash = "content"
  resign(symbolicHash.report)
  cases.push({ id: "usl_valid_symbolic_content_hash", usl_validator_accepts: validate(symbolicHash.report), hswm_adapter: hswmAccepts(symbolicHash), interpretation: "USL v2 schema permits nonempty text contentHash; current HSWM adapter intentionally rejects it as a raw SHA-256 pin, a cross-language false-reject until USL narrows its contract or HSWM documents/translates the requirement" })

  const future = clone(fixture)
  future.report.resources[0].resolution.resolvedAt = "2030-01-01T00:00:00.000Z"
  resign(future.report)
  cases.push({ id: "valid_future_timestamp", usl_validator_accepts: validate(future.report), hswm_adapter: hswmAccepts(future), interpretation: "USL validates timestamp syntax and report consistency; HSWM applies its separate now/max-age freshness policy and must withhold readiness" })

  const sourceBytes = readFileSync(resolve(uslRoot, "src/language/comparison.ts"))
  const schemaBytes = readFileSync(resolve(uslRoot, "src/language/observation-schema.ts"))
  const runtimeBytes = readFileSync(resolve(uslRoot, "src/language/runtime.ts"))
  const result = {
    schema: "hswm-usl-latest-observation-audit/v1",
    scope: "local injected fixture; no resolver, check execution, or external attestation",
    source: {
      usl_package: JSON.parse(readFileSync(resolve(uslRoot, "package.json"), "utf8")).version,
      comparison_ts_sha256: sha256(sourceBytes.toString("utf8")),
      observation_schema_ts_sha256: sha256(schemaBytes.toString("utf8")),
      runtime_ts_sha256: sha256(runtimeBytes.toString("utf8")),
      fixture_sha256: sha256(readFileSync(fixturePath, "utf8")),
    },
    cases,
    limits: [
      "A self-consistent report digest is not resolver provenance or authorship authentication.",
      "sourceDigest cannot authenticate source bytes without supplied source bytes or an independently pinned source artifact.",
      "The standalone USL validator cannot reconstruct full-plan declarations outside a selected report.",
    ],
  }
  writeFileSync(outputPath, `${JSON.stringify(result, null, 2)}\n`)
}
main().catch((error: unknown) => { console.error(error); process.exitCode = 1 })
