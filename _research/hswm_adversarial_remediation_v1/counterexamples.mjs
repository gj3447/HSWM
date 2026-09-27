#!/usr/bin/env node
/** Deterministic design witnesses only: no model calls, writes, or efficacy claim. */
import { createHash } from "node:crypto"
import { readFile } from "node:fs/promises"
import { fileURLToPath, pathToFileURL } from "node:url"
import { resolve, relative } from "node:path"

const root = resolve(fileURLToPath(new URL("../../", import.meta.url)))
const sourcePath = resolve(root, "src/hswm/effect-runtime/src/local-semantic-execution-domain.ts")
const scriptPath = fileURLToPath(import.meta.url)
const sha256 = bytes => createHash("sha256").update(bytes).digest("hex")
const fail = message => { throw new Error(message) }
const bit = value => value === 0 || value === 1
const key = (b, c, e) => `${b}${c}${e}`

// Literal truth tables in b,c,e order (000 through 111), deliberately not an
// alternate implementation of the prose laws.
const lawTables = Object.freeze({
  A: Object.freeze({ "000": 0, "001": 0, "010": 1, "011": 0, "100": 1, "101": 0, "110": 1, "111": 0 }),
  B: Object.freeze({ "000": 0, "001": 1, "010": 0, "011": 0, "100": 1, "101": 1, "110": 0, "111": 0 })
})
const bits = Object.freeze(Array.from({ length: 8 }, (_, index) => Object.freeze({
  b: (index >> 2) & 1, c: (index >> 1) & 1, e: index & 1
})))
const answer = (law, values) => lawTables[law][key(values.b, values.c, values.e)]
const swapped = values => Object.freeze({ b: values.b, c: values.e, e: values.c })

export async function runCounterexamples() {
  const [{ localSemanticCases }, domainBytes, scriptBytes] = await Promise.all([
    import(pathToFileURL(sourcePath).href), readFile(sourcePath), readFile(scriptPath)
  ])
  if (!Array.isArray(localSemanticCases) || localSemanticCases.length !== 128) fail("EXPECTED_128_W1_CASES")

  let copiedFieldMatches = 0
  for (const entry of localSemanticCases) {
    const copied = { context_flip: entry.input.fields.context.pel, exception_flip: entry.input.fields.exception.nub }
    if (!bit(copied.context_flip) || !bit(copied.exception_flip)) fail(`INVALID_W1_BITS:${entry.caseId}`)
    copiedFieldMatches += Number(copied.context_flip === entry.expected.context_flip) + Number(copied.exception_flip === entry.expected.exception_flip)
  }
  if (copiedFieldMatches !== 256) fail("E2_COPY_COUNT")

  const lawChanged = bits.filter(values => answer("A", values) !== answer("B", values))
  const swapChanged = Object.fromEntries(Object.keys(lawTables).map(law => [law,
    bits.filter(values => answer(law, values) !== answer(law, swapped(values)))
  ]))
  if (lawChanged.length !== 4 || swapChanged.A.length !== 4 || swapChanged.B.length !== 4) fail("ASYMMETRIC_COUNTS")
  const lawBlindCorrect = bits.reduce((total, values) => {
    const labels = [answer("A", values), answer("B", values)]
    return total + Math.max(labels.filter(value => value === 0).length, labels.filter(value => value === 1).length)
  }, 0)
  if (lawBlindCorrect !== 12) fail("LAW_BLIND_CEILING")

  const visible = Object.freeze({ b: 0, c: 1 })
  const hiddenCases = Object.freeze([0, 1].map(e => Object.freeze({ ...visible, hidden_e: e, answer: answer("A", { ...visible, e }) })))
  if (hiddenCases[0].answer !== 1 || hiddenCases[1].answer !== 0) fail("HIDDEN_ALIAS_ANSWERS")

  return Object.freeze({
    schema_version: "hswm-adversarial-remediation-counterexamples/v1",
    scope: "AUTHORED_FINITE_DESIGN_WITNESSES_ONLY_NO_MODEL_CALLS_NO_WORLD_PREDICTION_NO_LEARNING_OR_EFFICACY_CLAIM",
    source: Object.freeze({
      local_semantic_domain: relative(root, sourcePath), local_semantic_domain_sha256: sha256(domainBytes),
      counterexamples: relative(root, scriptPath), counterexamples_sha256: sha256(scriptBytes), node_version: process.version
    }),
    existing_w1_e2_copy_witness: Object.freeze({
      source_cases: 128, copied_named_fields: ["context_flip<-context.pel", "exception_flip<-exception.nub"],
      field_matches: copiedFieldMatches,
      observation: "EVALUATOR_TABLE_EQUALITY_ONLY_NOT_OBSERVED_MODEL_BEHAVIOR",
      nonclaim: "DOES_NOT_CLAIM_BASE_MATCH_FINAL_ANSWER_MATCH_OR_COMPLETE_E2_PASS"
    }),
    asymmetric_relation_witness: Object.freeze({
      laws: Object.freeze({ A: "e?0:c?1:b", B: "c?0:e?1:b" }),
      population: 8, paired_law_answer_changed: lawChanged.length,
      same_law_context_exception_value_swap_changed: Object.freeze({ A: swapChanged.A.length, B: swapChanged.B.length }),
      law_blind_best_deterministic_correct: lawBlindCorrect, law_blind_population: 16,
      assumptions: "UNIFORM_16_CASE_POPULATION;_PREDICTOR_USES_ONLY_b_c_e;_NO_LAW_ID_HISTORY_OR_OTHER_SIDE_CHANNEL",
      cases_to_inspect: Object.freeze({ law_difference: lawChanged, law_A_swap_difference: swapChanged.A, law_B_swap_difference: swapChanged.B })
    }),
    partial_read_alias_witness: Object.freeze({
      visible_payload: visible, law: "A", hidden_cases: hiddenCases, best_visible_only_correct: 1, population: 2,
      assumptions: "UNIFORM_TWO_CASE_POPULATION;_ONLY_FIXED_VISIBLE_PAYLOAD_AND_LAW_A;_NO_HISTORY_OR_SIDE_CHANNEL_FOR_e",
      caveat: "QUERYING_HIDDEN_E_WOULD_CHANGE_THE_INFORMATION_SET;_NO_ACTIVE_READ_POLICY_IS_IMPLEMENTED"
    })
  })
}

if (process.argv[1] && resolve(process.argv[1]) === scriptPath) {
  console.log(JSON.stringify(await runCounterexamples(), null, 2))
}
