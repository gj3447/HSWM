/** Static fixture generated once by the source Python integrity helpers. */
import { readFileSync } from "node:fs"
import { createHash } from "node:crypto"
import { expect, it } from "@effect/vitest"
import { Either } from "effect"
import { nativeAssessOccurrenceIntegrity, nativeOccurrenceAssessmentCanonical } from "../src/native-occurrence-integrity-domain.js"
import { renderNativeTaskJson, type TaskJson } from "../src/native-task-json-domain.js"

type Fixture = { readonly source_sha256: string; readonly positive: { readonly input: TaskJson; readonly expected: TaskJson } }
const fixture = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/occurrence_integrity_v1/original_python.json", import.meta.url), "utf8")) as Fixture
const differential = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/occurrence_integrity_v1/differential.original.v1.json", import.meta.url), "utf8")) as { readonly source_sha256: Readonly<Record<string, string>>; readonly integrity: Readonly<Record<string, { readonly terminal: string; readonly reason: string }>> }
const originalIntegrityCase = (name: string): { readonly terminal: string; readonly reason: string } => {
  const value = differential.integrity[name]
  if (value === undefined) throw new Error(`missing original integrity differential case: ${name}`)
  return value
}
const positive = (): Record<string, TaskJson> => fixture.positive.input as Record<string, TaskJson>
const sha = (value: TaskJson): string => createHash("sha256").update(renderNativeTaskJson(value), "utf8").digest("hex")
const run = (input: TaskJson) => {
  const result = nativeAssessOccurrenceIntegrity(input)
  expect(Either.isRight(result)).toBe(true)
  if (Either.isLeft(result)) throw new Error(result.left.detail)
  const canonical = nativeOccurrenceAssessmentCanonical(result.right)
  expect(Either.isRight(canonical)).toBe(true)
  if (Either.isLeft(canonical)) throw new Error(canonical.left.detail)
  return canonical.right
}
it("matches the full static original-Python positive canonical assessment", () => {
  expect(fixture.source_sha256).toBe("377d492643c49a7d76444d55b3d798eeb41dfceb010902aba1aa303d90a77269")
  for (const [path, expected] of Object.entries(differential.source_sha256)) expect(createHash("sha256").update(readFileSync(new URL(`../../../../${path}`, import.meta.url))).digest("hex"), path).toBe(expected)
  expect(run(positive())).toEqual(fixture.positive.expected)
})
it("preserves duplicate and retry terminal precedence", () => {
  const duplicate = run({ ...positive(), duplicate_seen: true, retry_seen: false })
  expect(duplicate).toMatchObject(originalIntegrityCase("duplicate"))
  const both = run({ ...positive(), duplicate_seen: true, retry_seen: true })
  expect(both).toMatchObject(originalIntegrityCase("duplicate_precedes_retry"))
  const retry = run({ ...positive(), duplicate_seen: false, retry_seen: true })
  expect(retry).toMatchObject(originalIntegrityCase("retry"))
})
it("refuses frozen nested schema extras and broken carrier bindings", () => {
  const input = positive() as Record<string, TaskJson>
  const worm = input["worm"] as Record<string, TaskJson>
  expect(run({ ...input, worm: { ...worm, extra: true } })["terminal"]).toBe("VOID_BINDING_CHAIN")
  const actor = input["actor_seal"] as Record<string, TaskJson>
  // The fixture's audit is deliberately not recomputed for a mutation, so the
  // external-audit binding failure precedes chronology.
  expect(run({ ...input, actor_seal: { ...actor, sealed_unix: 200 } })["terminal"]).toBe("VOID_BINDING_CHAIN")
  expect(run({ ...input, external_audit: null })).toMatchObject(originalIntegrityCase("missing_external_audit"))
})

it("fails closed before a coherently rebound non-original evaluator role can reach the candidate ceiling", () => {
  const input = structuredClone(positive()) as Record<string, TaskJson>
  const evaluator = input["evaluator_a"] as Record<string, TaskJson>
  const role = evaluator["evaluator"] as Record<string, TaskJson>
  role["role"] = "unrecognized_evaluator_role"
  const manifest = evaluator["audit_manifest"] as Record<string, TaskJson>
  manifest["sha256"] = sha({ schema: "hswm-evaluation-audit-manifest/v1", occurrence_uid: evaluator["occurrence_uid"]!, evaluator_role: role["role"]!, input: evaluator["input"]!, output: evaluator["output"]!, task: evaluator["task"]!, scorer: evaluator["scorer"]!, config: evaluator["config"]!, implementation: evaluator["implementation"]!, signature_audit: evaluator["signature_audit"]! })
  const evidence = evaluator["evidence"] as Record<string, TaskJson>
  evidence["bound"] = manifest
  const bridge = input["dual_evaluation_bridge"] as Record<string, TaskJson>
  bridge["bridge_manifest"] = { ...(bridge["bridge_manifest"] as Record<string, TaskJson>), sha256: sha({ schema: "hswm-dual-evaluation-bridge/v1", evaluator_a: evaluator, evaluator_b: input["evaluator_b"]!, dual_evaluation_evidence_sha256: bridge["dual_evaluation_evidence_sha256"]! }) }
  const withoutAudit = run({ ...input, external_audit: null })
  const audit = input["external_audit"] as Record<string, TaskJson>
  audit["audited_chain_sha256"] = withoutAudit["chain_digest"]!
  // EvaluationReceiptV1 rejects this role at construction; the native boundary
  // returns a terminal instead, so this verifies fail-closed non-candidacy.
  expect(run(input)).toMatchObject({ terminal: "VOID_BINDING_CHAIN", reason: "evaluation receipt invalid", claim_ceiling: "EXTERNAL_OCCURRENCE_INTEGRITY_CONTRACT_ONLY_NOT_OUTCOME_TRUTH_NOT_CF07_NOT_G0_NOT_G1_NOT_CANONICAL_LEARNING" })
})
