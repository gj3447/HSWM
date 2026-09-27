#!/usr/bin/env node
/**
 * Deterministic audit of value-binding swaps in the finite W1 fixture.
 * It never contacts a model and does not alter relation text, role labels, or
 * ontology.  It is therefore a reference-table sensitivity census only.
 */
import { createHash } from "node:crypto"
import { readFile, writeFile } from "node:fs/promises"
import { resolve, relative } from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"

const repositoryRoot = resolve(fileURLToPath(new URL("../../", import.meta.url)))
const scriptPath = fileURLToPath(import.meta.url)
const domainPath = resolve(repositoryRoot, "src/hswm/effect-runtime/src/local-semantic-execution-domain.ts")
const protocolPath = resolve(repositoryRoot, "_research/local_semantic_execution_v1/protocol.v1.json")
const sha256 = value => createHash("sha256").update(value).digest("hex")
const canonical = value => `${JSON.stringify(value, null, 2)}\n`
const positions = Object.freeze([
  Object.freeze({ role: "subject", field: "dax" }),
  Object.freeze({ role: "subject", field: "wug" }),
  Object.freeze({ role: "subject", field: "zif" }),
  Object.freeze({ role: "context", field: "pel" }),
  Object.freeze({ role: "exception", field: "nub" })
])
const positionId = position => `${position.role}.${position.field}`
const pairs = Object.freeze(positions.flatMap((left, index) => positions.slice(index + 1).map(right => Object.freeze({ left, right }))))

const fail = detail => { throw new Error(detail) }
const get = (fields, position) => fields[position.role]?.[position.field]
const swap = (fields, left, right) => {
  const copy = {
    subject: { ...fields.subject }, context: { ...fields.context }, exception: { ...fields.exception }
  }
  const leftValue = get(fields, left), rightValue = get(fields, right)
  copy[left.role][left.field] = rightValue
  copy[right.role][right.field] = leftValue
  return copy
}
const fieldKey = fields => positions.map(position => get(fields, position)).join("")
const expectedKey = expected => `${expected.base}${expected.context_flip}${expected.exception_flip}${expected.answer}`
const intermediateKey = expected => `${expected.base}${expected.context_flip}${expected.exception_flip}`
const structuralInput = input => JSON.stringify({ relation: input.relation, roles: input.roles, priorEvidence: input.priorEvidence })

const assertFixture = cases => {
  const familyNames = ["xor", "role_selection", "conjunction", "conditional"]
  const ids = new Set()
  for (let familyIndex = 0; familyIndex < 4; familyIndex += 1) {
    const familyCases = cases.filter(entry => entry.familyIndex === familyIndex)
    if (familyCases.length !== 32) fail(`EXPECTED_32_CASES_FOR_FAMILY:${familyIndex}`)
    const patterns = new Set()
    for (const entry of familyCases) {
      if (entry.familyName !== familyNames[familyIndex] || typeof entry.caseId !== "string" || ids.has(entry.caseId)) fail(`INVALID_CASE_ID_OR_FAMILY:${entry.caseId}`)
      ids.add(entry.caseId)
      const fields = entry.input?.fields
      if (!fields || Object.keys(fields).sort().join(",") !== "context,exception,subject" || Object.keys(fields.subject ?? {}).sort().join(",") !== "dax,wug,zif" || Object.keys(fields.context ?? {}).join(",") !== "pel" || Object.keys(fields.exception ?? {}).join(",") !== "nub") fail(`INVALID_FIELD_SHAPE:${entry.caseId}`)
      const pattern = fieldKey(fields)
      if (!/^[01]{5}$/.test(pattern)) fail(`INVALID_FIELD_BIT:${entry.caseId}`)
      patterns.add(pattern)
    }
    if (patterns.size !== 32 || Array.from({ length: 32 }, (_, index) => index.toString(2).padStart(5, "0")).some(pattern => !patterns.has(pattern))) fail(`INCOMPLETE_FIVE_BIT_CENSUS:${familyIndex}`)
  }
  if (ids.size !== 128) fail("NONUNIQUE_CASE_IDS")
}

export async function bindingAudit() {
  const [{ localSemanticCases }, domainBytes, protocolBytes, scriptBytes] = await Promise.all([
    import(pathToFileURL(domainPath).href), readFile(domainPath), readFile(protocolPath), readFile(scriptPath)
  ])
  if (!Array.isArray(localSemanticCases) || localSemanticCases.length !== 128) fail("EXPECTED_128_SOURCE_CASES")
  assertFixture(localSemanticCases)
  const byFamilyAndFieldValues = new Map()
  for (const entry of localSemanticCases) {
    const key = `${entry.familyIndex}:${fieldKey(entry.input.fields)}`
    if (byFamilyAndFieldValues.has(key)) fail(`DUPLICATE_REFERENCE_CASE:${key}`)
    byFamilyAndFieldValues.set(key, entry)
  }
  const rows = []
  for (let familyIndex = 0; familyIndex < 4; familyIndex += 1) {
    const familyCases = localSemanticCases.filter(entry => entry.familyIndex === familyIndex)
    if (familyCases.length !== 32) fail(`EXPECTED_32_CASES_FOR_FAMILY:${familyIndex}`)
    for (const pair of pairs) {
      let actualInputChanged = 0, finalAnswerChanged = 0, intermediateChanged = 0
      let witness = null
      for (const source of familyCases) {
        const transformedFields = swap(source.input.fields, pair.left, pair.right)
        const transformed = byFamilyAndFieldValues.get(`${familyIndex}:${fieldKey(transformedFields)}`)
        if (!transformed) fail(`MISSING_EXHAUSTIVE_REFERENCE:${familyIndex}:${fieldKey(transformedFields)}`)
        if (structuralInput(source.input) !== structuralInput(transformed.input)) fail(`NON_VALUE_STRUCTURE_CHANGED:${source.caseId}`)
        if (fieldKey(transformed.input.fields) !== fieldKey(transformedFields)) fail(`REFERENCE_FIELDS_MISMATCH:${source.caseId}`)
        const inverse = swap(transformedFields, pair.left, pair.right)
        if (fieldKey(inverse) !== fieldKey(source.input.fields)) fail(`INVERSE_SWAP_FAILURE:${source.caseId}`)
        if (fieldKey(transformedFields) !== fieldKey(source.input.fields)) actualInputChanged += 1
        if (transformed.expected.answer !== source.expected.answer) {
          finalAnswerChanged += 1
          if (witness === null) witness = Object.freeze({
            source_case_id: source.caseId,
            transformed_case_id: transformed.caseId,
            source_bound_values: source.input.fields,
            transformed_bound_values: transformedFields,
            source_expected: source.expected,
            transformed_expected: transformed.expected
          })
        }
        if (intermediateKey(transformed.expected) !== intermediateKey(source.expected)) intermediateChanged += 1
      }
      rows.push(Object.freeze({
        family_index: familyIndex,
        family_name: familyCases[0].familyName,
        value_binding_swap: Object.freeze([positionId(pair.left), positionId(pair.right)]),
        total: familyCases.length,
        actual_input_changed: actualInputChanged,
        final_answer_changed: finalAnswerChanged,
        intermediate_changed: intermediateChanged,
        final_changing_witness: witness
      }))
    }
  }
  const identityCases = localSemanticCases.filter(entry => {
    const self = byFamilyAndFieldValues.get(`${entry.familyIndex}:${fieldKey(entry.input.fields)}`)
    return self?.caseId === entry.caseId && expectedKey(self.expected) === expectedKey(entry.expected)
  }).length
  if (identityCases !== localSemanticCases.length) fail("IDENTITY_REFERENCE_LOOKUP_FAILURE")
  return Object.freeze({
    schema_version: "hswm-local-semantic-binding-audit/v1",
    status: "COMPLETE_AUTHORED_REFERENCE_TABLE_CENSUS",
    source: Object.freeze({
      domain_path: relative(repositoryRoot, domainPath), domain_sha256: sha256(domainBytes),
      protocol_path: relative(repositoryRoot, protocolPath), protocol_sha256: sha256(protocolBytes),
      run_mjs_path: relative(repositoryRoot, scriptPath), run_mjs_sha256: sha256(scriptBytes), node_version: process.version,
      source_cases: localSemanticCases.length, families: 4, cases_per_family: 32,
      exact_field_coverage: positions.map(positionId), unordered_value_binding_swaps: pairs.length
    }),
    transformation: Object.freeze({
      kind: "VALUE_BINDING_SWAP_ONLY",
      changed: "Only the values stored at two declared field locations.",
      preserved: "relation.semanticText, relation metadata, ordered role labels/ordinals, and field locations.",
      not_tested: "Role-label exchange, ontology exchange, model behavior, durable revision, or efficacy."
    }),
    checks: Object.freeze({
      identity_reference_lookup_cases: identityCases,
      identity_reference_lookup_expected: localSemanticCases.length,
      inverse_swap_roundtrips: localSemanticCases.length * pairs.length,
      inverse_swap_roundtrips_expected: localSemanticCases.length * pairs.length,
      exhaustive_transformed_reference_lookups: localSemanticCases.length * pairs.length,
      exhaustive_transformed_reference_lookups_expected: localSemanticCases.length * pairs.length
    }),
    rows,
    model_calls: 0,
    evidence_kind: "AUTHORED_FINITE_REFERENCE_TABLE_ONLY",
    independent_jev_support: "NOT_USED; this census evaluates the fixture's own exhaustive reference table and is not independent semantic proof.",
    claim_ceiling: "REFERENCE_TABLE_SENSITIVITY_DIAGNOSTIC_ONLY_NOT_MODEL_EVIDENCE_NOT_SEMANTIC_UNDERSTANDING_NOT_LEARNING_NOT_EFFICACY"
  })
}

async function main(argv) {
  if (argv.length > 2 || argv.length === 1 || (argv.length === 2 && argv[0] !== "--output")) {
    fail("Usage: node _research/local_semantic_binding_audit_v1/run.mjs [--output NEW_ABSOLUTE_PATH]")
  }
  const report = await bindingAudit()
  const bytes = canonical(report)
  if (argv.length === 2) {
    const destination = resolve(argv[1])
    if (destination !== argv[1]) fail("OUTPUT_MUST_BE_ABSOLUTE")
    await writeFile(destination, bytes, { encoding: "utf8", flag: "wx", mode: 0o600 })
  }
  process.stdout.write(bytes)
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main(process.argv.slice(2)).catch(error => { process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`); process.exitCode = 1 })
}
