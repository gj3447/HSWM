/**
 * Reproduces source/plan provenance binding at the USL projection boundary.
 * It writes only a local audit result; no KG bundle is published.
 *
 * Run from HSWM:
 *   ../USL/node_modules/.bin/tsx _research/usl_adapter/latest_projection_audit_2026_09_08.ts \
 *     --usl-root ../USL --out _research/usl_adapter/latest_projection_audit_2026_09_08.json
 */
import { createHash } from "node:crypto"
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
const outputPath = resolve(arg("--out") ?? resolve(here, "latest_projection_audit_2026_09_08.json"))
const sha256 = (text: string) => createHash("sha256").update(text).digest("hex")

const original = `usl "0.1";
namespace "audit.projection";
resource code = "https://example.invalid/code";
resource target = "https://example.invalid/target";
meaning implements(code: url, target: url) = "code implements the target";
link development = implements(code: code, target: target);`
const opposite = original.replace("code implements the target", "code does not implement the target")

const main = async () => {
  const language = await import(pathToFileURL(resolve(uslRoot, "src/language/index.ts")).href)
  const effect = await import(pathToFileURL(resolve(uslRoot, "node_modules/effect/dist/esm/index.js")).href)
  const plan = effect.Either.getOrThrow(language.compileSource(original))
  const projected = language.toSemanticBundle(plan, {
    bundle_uid: "audit:projection-source-binding",
    title: "local projection provenance audit",
    trigger: { user_utterance_verbatim: "audit source binding", utterance_date: "2026-09-08", tool: "local-audit" },
    source: { name: "opposite.usl", text: opposite },
  })
  const bundle = effect.Either.getOrThrow(projected)
  const meaning = bundle.nodes.find((node: any) => node.properties.name === "implements")
  let observationControlRejected = false
  let observationControlDetail = ""
  try {
    await effect.Effect.runPromise(language.observeProgram(plan, { sourceText: opposite }))
  } catch (error) {
    observationControlRejected = true
    observationControlDetail = error instanceof Error ? error.message : String(error)
  }
  const projectPath = resolve(uslRoot, "src/language/project.ts")
  const cliPath = resolve(uslRoot, "src/cli.ts")
  const result = {
    schema: "hswm-usl-latest-projection-audit/v1",
    scope: "local compile/project/control only; no resolver, KG publish, or check execution",
    source: {
      usl_package: JSON.parse(readFileSync(resolve(uslRoot, "package.json"), "utf8")).version,
      project_ts_sha256: sha256(readFileSync(projectPath, "utf8")),
      cli_ts_sha256: sha256(readFileSync(cliPath, "utf8")),
      original_source_sha256: sha256(original),
      opposite_source_sha256: sha256(opposite),
    },
    projection: {
      api_accepts_mismatched_source: projected._tag === "Right",
      projected_meaning_description: meaning?.properties.description ?? null,
      projected_source_sha256: meaning?.properties.source_sha256 ?? null,
      expected_description_from_plan: "code implements the target",
      expected_source_sha256_from_supplied_option: sha256(opposite),
    },
    observation_control: {
      rejected_mismatched_source: observationControlRejected,
      detail: observationControlDetail,
    },
    cli_path_assessment: "CLI project reads sourceText, compiles that same sourceText, then passes the same sourceText as options.source; this specific mismatch is not reachable through the source-file CLI path.",
    finding: "P2 provenance binding defect: direct toSemanticBundle accepts a plan and options.source.text that describe different declarations, combining plan-derived node descriptions with the supplied source hash.",
    acceptance_criteria: [
      "When options.source is supplied, compile options.source.text and require its plan digest to equal the supplied plan before creating a bundle.",
      "Snapshot plan and options.source.text before projection so caller mutation cannot mix identities during processing.",
      "Add a direct API regression: original plan plus opposite source must return LanguageError; matching source must preserve description and source_sha256.",
      "Keep the CLI's same-text compile/project path as a control, but do not rely on it to make the public API provenance-safe.",
    ],
  }
  writeFileSync(outputPath, `${JSON.stringify(result, null, 2)}\n`)
}
main().catch((error: unknown) => { console.error(error); process.exitCode = 1 })
