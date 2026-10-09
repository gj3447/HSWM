#!/usr/bin/env node
/** One-request CLI, with separate preparation, decision, execution and observation effects. */
import { Effect, Either, Schema } from "effect"
import { createHash } from "node:crypto"
import { resolve } from "node:path"
import { canonicalJson, parseJson } from "./adaptive-domain.js"
import { NativeAdaptiveHttpClient } from "./adaptive-executor.js"
import { canonicalJsonBytes, decodeCanonicalJsonBytes } from "./canonical-atom-v2-json.js"
import { CanonicalAtomV2DurableRuntime, makeCanonicalAtomV2DurableRuntimeFileLayer } from "./canonical-atom-v2-durable-runtime.js"
import { runArgvProcessMain, readNodeStdin, refuse } from "./effect-process-main.js"
import { decodeGeneralJsonBytes } from "./general-json-domain.js"
import { ContextSpecSchema, selectContext, contextError, contextJson } from "./semantic-context-domain.js"
import { prepareSemanticContext, assembleSemanticContext, executeSemanticContext, stageSemanticContextOutcome } from "./semantic-context-runtime.js"
import { requestOpenJevContext } from "./semantic-context-jev.js"
import { PosixFileSystem } from "./effect-posix-filesystem.js"
import { projectSemanticContext } from "./semantic-context-graph.js"

const RequestSchema = Schema.Struct({
  contract: Schema.Literal("hswm-semantic-context-cli/v1"),
  action: Schema.Literal("prepare", "decide", "assemble", "execute", "observe", "project"),
  durableRoot: Schema.String.pipe(Schema.pattern(/^\//)),
  journalLineageId: Schema.String.pipe(Schema.minLength(1)),
  schema: Schema.Unknown,
  spec: Schema.optional(ContextSpecSchema),
  expectedPlanSha256: Schema.optional(Schema.String.pipe(Schema.pattern(/^[a-f0-9]{64}$/))),
  decision: Schema.optional(Schema.Unknown),
  cell: Schema.optional(Schema.Unknown),
  outcome: Schema.optional(Schema.Unknown),
  assemblySourcePath: Schema.optional(Schema.String.pipe(Schema.pattern(/^[A-Za-z0-9_][A-Za-z0-9_./-]{0,255}$/), Schema.filter(p => !p.split("/").some(s => s === ".." || s === ""))))
})
export const semanticContextProcess = (raw: unknown, cwd = process.cwd()) => Effect.gen(function* () {
  const request = yield* Schema.decodeUnknownEither(RequestSchema)(raw, { onExcessProperty: "error" }).pipe(Either.mapLeft(() => refuse("Invalid semantic-context request; see --help")))
  const fs = yield* PosixFileSystem
  const identity = yield* fs.identity(request.durableRoot, "semantic-context-existing-store")
  if (identity.kind !== "DIRECTORY") return yield* Effect.fail(refuse("durableRoot must be an existing directory"))
  if ((request.action === "project") !== (request.assemblySourcePath !== undefined)) return yield* Effect.fail(refuse("Only project requires assemblySourcePath"))
  const schemaJson = yield* decodeCanonicalJsonBytes(new TextEncoder().encode(contextJson(request.schema)))
  const schemaBytes = yield* canonicalJsonBytes(schemaJson)
  const run = Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    if (request.action === "observe") {
      if (request.spec !== undefined || request.decision !== undefined || request.cell !== undefined || request.expectedPlanSha256 !== undefined || request.outcome === undefined) return yield* Effect.fail(refuse("observe accepts outcome only"))
      return yield* stageSemanticContextOutcome(runtime, request.outcome)
    }
    if (request.spec === undefined || request.outcome !== undefined) return yield* Effect.fail(refuse("A spec is required; outcome is only valid for observe"))
    const plan = yield* prepareSemanticContext(runtime, request.spec)
    if (request.action === "prepare") {
      if (request.decision !== undefined || request.cell !== undefined || request.expectedPlanSha256 !== undefined) return yield* Effect.fail(refuse("prepare accepts spec only"))
      return plan
    }
    if (request.expectedPlanSha256 !== plan.planSha256) return yield* Effect.fail(contextError("PLAN_STALE", "Explicit expectedPlanSha256 must match the current graph and spec"))
    if (request.action === "decide") {
      if (request.decision !== undefined || request.cell !== undefined) return yield* Effect.fail(refuse("decide invokes the existing jev-dgx bridge; it does not accept a receipt or LLM cell"))
      const environment = Object.fromEntries(Object.entries(process.env).filter((entry): entry is [string, string] => entry[1] !== undefined))
      const receipt = yield* requestOpenJevContext(plan, "jev-dgx", cwd, environment)
      const selection = yield* selectContext(plan, receipt)
      return { selection, decision: receipt }
    }
    if (request.decision === undefined) return yield* Effect.fail(refuse("assemble/execute requires the exact Jev receipt"))
    if (request.action === "assemble") {
      if (request.cell !== undefined) return yield* Effect.fail(refuse("assemble does not execute an LLM"))
      return yield* assembleSemanticContext(runtime, plan, request.decision)
    }
    if (request.action === "project") {
      if (request.cell !== undefined || request.assemblySourcePath === undefined) return yield* Effect.fail(refuse("project needs a saved assemble result, no LLM cell"))
      const assembled = yield* assembleSemanticContext(runtime, plan, request.decision)
      const source = yield* fs.readRegularBounded(resolve(cwd, request.assemblySourcePath), { maximumBytes: 1048576, operation: "semantic-context-assembly-source" })
      const decoded = yield* parseJson(new TextDecoder().decode(source.bytes))
      const recorded = yield* canonicalJson(decoded)
      const current = yield* canonicalJson(assembled)
      if (recorded !== current) return yield* Effect.fail(contextError("ASSEMBLY_SOURCE_MISMATCH", "Saved assemble output does not match this exact plan and receipt"))
      return projectSemanticContext(plan, assembled.selection, assembled.assembly, { path: request.assemblySourcePath, sha256: createHash("sha256").update(source.bytes).digest("hex") })
    }
    if (request.cell === undefined) return yield* Effect.fail(refuse("execute requires an explicit LLM cell"))
    return yield* executeSemanticContext(runtime, plan, request.decision, request.cell, NativeAdaptiveHttpClient)
  }).pipe(Effect.provide(makeCanonicalAtomV2DurableRuntimeFileLayer(request.durableRoot, request.journalLineageId, schemaBytes)))
  return yield* run
})

/** General JSON preserves finite Jev probabilities; canonical atom JSON remains integer-only. */
export const semanticContextStdinProcess = (source: string) => Effect.gen(function* () {
  const input = yield* decodeGeneralJsonBytes(new TextEncoder().encode(source))
  const result = yield* semanticContextProcess(input)
  yield* canonicalJson(result) // Validate finite JSON without reordering receipt bytes.
  return `${contextJson(result)}\n`
})

const help = `hswm-context --help | < request.json
One bounded JSON request on stdin; contract hswm-semantic-context-cli/v1.
Required: action, durableRoot (absolute existing store), journalLineageId, schema (full native schema).
prepare: spec -> pinned candidate plan + jev-request/v1; no model calls or explicit frame reads.
decide: spec + expectedPlanSha256 -> existing jev-dgx subprocess (explicit remote inference).
assemble: spec + expectedPlanSha256 + decision -> complete selected/mandatory frames; no model calls.
execute: assemble inputs + cell -> one LLM call and staged trace; no canonical write.
observe: outcome {traceContent, observed, source} -> attributed immutable observation; no W update.
project: assemble inputs + assemblySourcePath (relative saved assemble JSON) -> source-bound native RDF v2 bundle.
NONE/NEED_MORE never trigger LLM execution. Missing roles, stale state or excess bytes refuse.
Exit 0: complete observation, including abstention; 2: typed refusal; 3: defect.
decide requires the existing authorized DGX/HSWM transport; preparation never invokes it.
Guide: docs/operations/HSWM_JEV_CONTEXT_SELECTION_2026-10-09.md
`
if (import.meta.main) {
  if (process.argv.length === 3 && process.argv[2] === "--help") process.stdout.write(help)
  else if (process.argv.length !== 2) { process.stderr.write(help); process.exitCode = 2 }
  else process.exitCode = await runArgvProcessMain({ refusalPrefix: "HSWM_CONTEXT_REFUSED", program: () => readNodeStdin(1048576).pipe(Effect.flatMap(semanticContextStdinProcess)), describeFailure: error => String(error) }, [])
}
