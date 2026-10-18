#!/usr/bin/env node
/** Bounded stdin diagnostic over an explicit HSWM semantic frame; never admits revisions. */
import { Effect } from "effect"
import { decodeGeneralJsonBytes } from "./general-json-domain.js"
import { readNodeStdin, runArgvProcessMain } from "./effect-process-main.js"
import { reviewFiniteSemanticRequest } from "./semantic-context-finite-domain.js"

export const finiteSemanticStdinProcess = (input: string) => Effect.gen(function* () {
  const raw = yield* decodeGeneralJsonBytes(new TextEncoder().encode(input))
  const result = yield* reviewFiniteSemanticRequest(raw)
  return JSON.stringify(result) + "\n"
})
const help = `hswm-semantic-finite < request.json
Read-only semantic diagnostic. No model call, network, state mutation or automatic W update.
Input: hswm-finite-semantic-review/v1 with representation {kind,payload} from the native frame representation codec.
The frame semanticText must be JSON hswm-finite-semantic-program/v1, not free prose.
Optional proposedSemanticText compares allowed assignments with the identical variable/role/domain binding.
Optional factorBags: 1..8 variable-ID arrays, collectively covering the declared domain.
Complete enumeration: at most 4096 assignments, 16 variables, 128 ordered expression nodes, 32 clauses.
Output: clause-removal witnesses, equivalence/strengthening/weakening/incomparable change, lossless/lossy projection join.
Logical strengthening is a restriction of allowed interpretations, not measured neural/semantic connection strength.
Exit 0 means the diagnostic completed, including lossy/contradictory results; 2 refusal, 3 defect.
Guide: docs/operations/HSWM_LIKENESS_RESEARCH_TRANSFER_2026-10-18.md
`
if (import.meta.main) {
  if (process.argv.length === 3 && process.argv[2] === "--help") process.stdout.write(help)
  else if (process.argv.length !== 2) { process.stderr.write(help); process.exitCode = 2 }
  else process.exitCode = await runArgvProcessMain({ refusalPrefix: "HSWM_FINITE_REFUSED", program: () => readNodeStdin(1048576).pipe(Effect.flatMap(finiteSemanticStdinProcess)), describeFailure: error => error.detail }, [])
}
