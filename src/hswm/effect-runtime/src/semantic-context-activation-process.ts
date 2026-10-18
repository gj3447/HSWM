#!/usr/bin/env node
/** One-request activation CLI. Proposals never grant canonical write authority. */
import { Effect, Either, Schema } from "effect"
import { canonicalJson } from "./adaptive-domain.js"
import { NativeAdaptiveHttpClient } from "./adaptive-executor.js"
import { canonicalJsonBytes, decodeCanonicalJsonBytes } from "./canonical-atom-v2-json.js"
import { CanonicalAtomV2DurableRuntime, makeCanonicalAtomV2DurableRuntimeFileLayer } from "./canonical-atom-v2-durable-runtime.js"
import { runArgvProcessMain, readNodeStdin, refuse } from "./effect-process-main.js"
import { decodeGeneralJsonBytes } from "./general-json-domain.js"
import { PosixFileSystem } from "./effect-posix-filesystem.js"
import { ContextSpecSchema, contextJson } from "./semantic-context-domain.js"
import { prepareSemanticContext } from "./semantic-context-runtime.js"
import { ActivationConfigSchema } from "./semantic-context-activation-domain.js"
import { ActivationDecisionSchema, ActivationFeedbackSchema, prepareActivationInitialization, prepareActivationLearning, selectContextActivation, assembleContextActivation, executeContextActivation } from "./semantic-context-activation-runtime.js"

const base = { contract: Schema.Literal("hswm-context-activation-cli/v1"), durableRoot: Schema.String.pipe(Schema.pattern(/^\//)),
  journalLineageId: Schema.NonEmptyString, schema: Schema.Unknown, spec: ContextSpecSchema }
const pinned = { ...base, expectedPlanSha256: Schema.String.pipe(Schema.pattern(/^[a-f0-9]{64}$/)) }
const Request = Schema.Union(
  Schema.Struct({ ...base, action: Schema.Literal("prepare") }),
  Schema.Struct({ ...pinned, action: Schema.Literal("initialize"), config: ActivationConfigSchema, target: Schema.Unknown }),
  Schema.Struct({ ...pinned, action: Schema.Literal("learn"), feedback: ActivationFeedbackSchema, target: Schema.Unknown }),
  Schema.Struct({ ...pinned, action: Schema.Literal("select", "assemble"), decision: ActivationDecisionSchema }),
  Schema.Struct({ ...pinned, action: Schema.Literal("execute"), decision: ActivationDecisionSchema, cell: Schema.Unknown })
)
export const contextActivationProcess = (raw: unknown) => Effect.gen(function* () {
  const request = yield* Schema.decodeUnknownEither(Request)(raw, { onExcessProperty: "error" }).pipe(Either.mapLeft(() => refuse("Invalid activation request; see --help")))
  const fs = yield* PosixFileSystem
  if ((yield* fs.identity(request.durableRoot, "activation-existing-store")).kind !== "DIRECTORY") return yield* Effect.fail(refuse("durableRoot must exist"))
  const schemaBytes = yield* canonicalJsonBytes(yield* decodeCanonicalJsonBytes(new TextEncoder().encode(contextJson(request.schema))))
  return yield* Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const plan = yield* prepareSemanticContext(runtime, request.spec)
    if (request.action === "prepare") return plan
    if (request.expectedPlanSha256 !== plan.planSha256) return yield* Effect.fail(refuse("Stale activation plan"))
    switch (request.action) {
      case "initialize": return yield* prepareActivationInitialization(runtime, plan, request.config, request.target)
      case "learn": return yield* prepareActivationLearning(runtime, plan, request.feedback, request.target)
      case "select": return yield* selectContextActivation(runtime, plan, request.decision)
      case "assemble": return yield* assembleContextActivation(runtime, plan, request.decision)
      case "execute": return yield* executeContextActivation(runtime, plan, request.decision, request.cell, NativeAdaptiveHttpClient)
    }
  }).pipe(Effect.provide(makeCanonicalAtomV2DurableRuntimeFileLayer(request.durableRoot, request.journalLineageId, schemaBytes)))
})
export const contextActivationStdinProcess = (source: string) => Effect.gen(function* () {
  const result = yield* contextActivationProcess(yield* decodeGeneralJsonBytes(new TextEncoder().encode(source)))
  yield* canonicalJson(result)
  return `${contextJson(result)}\n`
})
const help = `hswm-activation --help | < request.json
Contract hswm-context-activation-cli/v1. Common fields: action, durableRoot (existing absolute directory), journalLineageId, full native schema, spec.
prepare -> plan. Other actions require its exact expectedPlanSha256.
initialize + config {encoderRevision,featureNames,alpha} + target -> initial policy proposal.
select / assemble + decision {policyKey,features:{encoderRevision,eventSha256,values},mode:EXPLORE|EXPLOIT} -> contextual selection / complete selected and mandatory frames.
execute + decision + cell {base_url,model,max_tokens} -> one explicit model call and stored trace.
learn + feedback {traceContent,reward,observed,source} + target -> outcome-bound successor proposal.
target: {key:{schemaVersion,lineageId,atomUid,revisionId},owner,authorizationRef,scope,decidedAt}.
All admission uses the existing owner writer; this CLI never submits a proposal.
Requires schema-admitted semantic_context_policy with candidate-root and supersedes references.
LinUCB ridge=1, deterministic top-1 bundle; mandatory roles remain active. Scores are not probabilities.
Features are caller encoded and versioned; rewards are caller attributed, not authenticated ground truth.
No neural weight training, automatic rule retirement, or claim of general intelligence.
Exit 0 success, 2 refusal, 3 defect. Guide: docs/operations/HSWM_LOCAL_ACTIVATION_2026-10-18.md
`
if (import.meta.main) {
  if (process.argv.length === 3 && process.argv[2] === "--help") process.stdout.write(help)
  else if (process.argv.length !== 2) { process.stderr.write(help); process.exitCode = 2 }
  else process.exitCode = await runArgvProcessMain({ refusalPrefix: "HSWM_ACTIVATION_REFUSED", program: () => readNodeStdin(1048576).pipe(Effect.flatMap(contextActivationStdinProcess)), describeFailure: error => String(error) }, [])
}
