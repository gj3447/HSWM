#!/usr/bin/env node
/** Read-only recovery/selection bridge; mutation stays with the caller's existing owner. */
import { Effect, Schema } from "effect"
import { canonicalJsonBytes, decodeCanonicalJsonBytes } from "./canonical-atom-v2-json.js"
import { CanonicalAtomV2KeySchema } from "./canonical-atom-v2-schema.js"
import { CanonicalAtomV2DurableRuntime, makeCanonicalAtomV2DurableRuntimeFileLayer } from "./canonical-atom-v2-durable-runtime.js"
import { contextHash, contextJson } from "./semantic-context-domain.js"
import { prepareSemanticContext } from "./semantic-context-runtime.js"
import { assembleContextActivation } from "./semantic-context-activation-runtime.js"
import { workingSpec, latestWorkingAtom, workingError } from "./working-context-domain.js"
import { openWorkingContext } from "./working-context-runtime.js"
import { decodeGeneralJsonBytes } from "./general-json-domain.js"
import { readNodeStdin, runArgvProcessMain, refuse } from "./effect-process-main.js"
import { PosixFileSystem } from "./effect-posix-filesystem.js"

const base = { contract: Schema.Literal("hswm-working-context-cli/v1"), durableRoot: Schema.String.pipe(Schema.pattern(/^\//)),
  journalLineageId: Schema.NonEmptyString, schema: Schema.Unknown, contextKey: CanonicalAtomV2KeySchema }
const Request = Schema.Union(
  Schema.Struct({ ...base, action: Schema.Literal("open") }),
  Schema.Struct({ ...base, action: Schema.Literal("select"), featureValues: Schema.Array(Schema.Number.pipe(Schema.finite(), Schema.between(-1, 1))).pipe(Schema.minItems(1), Schema.maxItems(16)) })
)
export const workingContextProcess = (raw: unknown) => Effect.gen(function* () {
  const request = yield* Schema.decodeUnknown(Request)(raw, { onExcessProperty: "error" })
  const fs = yield* PosixFileSystem
  if ((yield* fs.identity(request.durableRoot, "working-context-recovery")).kind !== "DIRECTORY") return yield* Effect.fail(refuse("Existing durableRoot required"))
  const bytes = yield* canonicalJsonBytes(yield* decodeCanonicalJsonBytes(new TextEncoder().encode(contextJson(request.schema))))
  return yield* Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const opened = yield* openWorkingContext(runtime, request.contextKey)
    if (request.action === "open") return opened
    if (opened.status !== "CURRENT") return yield* Effect.fail(workingError("DEPENDENCY_STALE", "Refresh affected sources through the owner before selection"))
    const plan = yield* prepareSemanticContext(runtime, yield* workingSpec(opened.context))
    const policy = latestWorkingAtom((yield* runtime.snapshot).canonical.atoms, opened.context.policyKey)
    if (!policy) return yield* Effect.fail(workingError("POLICY_MISSING", "Shared policy is absent"))
    const selected = yield* assembleContextActivation(runtime, plan, { policyKey: policy.key, mode: "EXPLOIT",
      features: { encoderRevision: opened.context.policyFamily.config.encoderRevision, eventSha256: contextHash(plan.spec.event), values: request.featureValues } })
    return { contextKey: opened.atom.key, ...selected }
  }).pipe(Effect.provide(makeCanonicalAtomV2DurableRuntimeFileLayer(request.durableRoot, request.journalLineageId, bytes)))
})
const help = `hswm-working-context --help | < request.json
Read-only hswm-working-context-cli/v1: action open|select; existing absolute durableRoot;
journalLineageId; full pinned native schema; contextKey (schemaVersion,lineageId,atomUid,revisionId).
open explicitly resolves the latest revision of that stable identity and returns memory, exact dependency pins and staleness.
select additionally requires featureValues; reads the current shared policy and assembles complete selected frames.
Superseded source dependencies refuse select. Policy revisions are returned explicitly. No HTTP, admission or W mutation.
Create, refresh, memory updates and executeWorkingContextLoop use working-context-runtime's existing owner callback API.
Exit 0 success, 2 refusal, 3 defect. Guide: docs/operations/HSWM_AGENT_WORKING_CONTEXT.md
`
if (import.meta.main) {
  if (process.argv.length === 3 && process.argv[2] === "--help") process.stdout.write(help)
  else if (process.argv.length !== 2) { process.stderr.write(help); process.exitCode = 2 }
  else process.exitCode = await runArgvProcessMain({ refusalPrefix: "HSWM_WORKING_CONTEXT_REFUSED",
    program: () => readNodeStdin(1048576).pipe(Effect.flatMap(source => decodeGeneralJsonBytes(new TextEncoder().encode(source))), Effect.flatMap(workingContextProcess), Effect.map(value => `${contextJson(value)}\n`)),
    describeFailure: error => String(error) }, [])
}
