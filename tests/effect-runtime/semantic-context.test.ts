import { createHash } from "node:crypto"
import { mkdir, readFile, writeFile } from "node:fs/promises"
import { join } from "node:path"
import { fileURLToPath } from "node:url"
import { Effect, Either, Layer } from "effect"
import { expect, it } from "vitest"
import { NodePosixServicesLive } from "../../src/hswm/effect-runtime/src/effect-posix-services.js"
import { BoundedSubprocess } from "../../src/hswm/effect-runtime/src/effect-bounded-subprocess.js"
import { type AdaptiveHttpClientShape } from "../../src/hswm/effect-runtime/src/adaptive-executor.js"
import { buildContextPlan, contextHash, selectContext } from "../../src/hswm/effect-runtime/src/semantic-context-domain.js"
import { prepareSemanticContext, assembleSemanticContext, executeSemanticContext, stageSemanticContextOutcome } from "../../src/hswm/effect-runtime/src/semantic-context-runtime.js"
import { requestOpenJevContext } from "../../src/hswm/effect-runtime/src/semantic-context-jev.js"
import { projectSemanticContext } from "../../src/hswm/effect-runtime/src/semantic-context-graph.js"
import { semanticContextProcess, semanticContextStdinProcess } from "../../src/hswm/effect-runtime/src/semantic-context-process.js"
import { compileKgBundle } from "../../src/hswm/effect-runtime/src/native-kg-bundle-domain.js"
import { queryKgBundle, validateKgShacl } from "../../src/hswm/effect-runtime/src/native-kg-standards.js"
import { schema, spec, decisionFor, unwrap, withContextFixture } from "./semantic-context-fixture.js"

const root = fileURLToPath(new URL("../../", import.meta.url))
const run = <A, E>(program: Effect.Effect<A, E, never>) => Effect.runPromise(program.pipe(Effect.mapError(e => new Error(JSON.stringify(e)))))
const cell = { base_url: "https://fixture.invalid/v1", model: "SCRIPTED_CONTEXT_FIXTURE", max_tokens: 128 }
const fixtureHttp = (inspect: (body: string) => void = () => {}): AdaptiveHttpClientShape => ({
  postJson: request => Effect.sync(() => {
    inspect(new TextDecoder().decode(request.body))
    return new TextEncoder().encode(JSON.stringify({ choices: [{ message: { content: JSON.stringify({ prediction: "deny", uncertainty: "scripted fixture" }) } }] }))
  })
})
const noHttp: AdaptiveHttpClientShape = { postJson: () => Effect.die("Abstention must not invoke the LLM") }
const fixture = <A, E>(use: Parameters<typeof withContextFixture<A, E, BoundedSubprocess>>[0]) => run(withContextFixture(use).pipe(Effect.provide(NodePosixServicesLive)))

it("prepares metadata-only candidates and reads only the selected bundle plus mandatory roles", () => fixture(runtime => Effect.gen(function* () {
  let reads = 0
  const scoped = { ...runtime, readContent: (d: Parameters<typeof runtime.readContent>[0]) => Effect.suspend(() => { reads += 1; return runtime.readContent(d) }) }
  const plan = yield* prepareSemanticContext(scoped, spec)
  expect(reads).toBe(0)
  expect(plan.requestSha256).toBe(createHash("sha256").update(JSON.stringify(plan.request)).digest("hex"))
  expect(plan.request.state).not.toContain("complete source")
  const result = yield* assembleSemanticContext(scoped, plan, decisionFor(plan))
  expect(reads).toBe(15) // 3 relation payloads + 4 pinned roles each; no calendar payloads.
  expect(result.assembly?.payload.frames.map(f => f.relation.key.atomUid)).toEqual(["relation:mandatory", "relation:door", "relation:companion"])
  expect(result.assembly?.payload.frames.every(f => f.roles.map(r => r.role).join(",") === "subject,context,evidence,exception")).toBe(true)
})))

it.each(["NONE", "NEED_MORE"])("keeps %s as an explicit abstention without payload reads or model calls", choice => fixture(runtime => Effect.gen(function* () {
  const plan = yield* prepareSemanticContext(runtime, spec)
  const guarded = { ...runtime, readContent: () => Effect.die("No content read on abstention") }
  const result = yield* executeSemanticContext(guarded, plan, decisionFor(plan, choice), cell, noHttp)
  expect(result.selection.status).toBe(choice)
  expect(result.assembly).toBeNull()
  expect(result.trace).toBeNull()
})))

it("rejects foreign requests, malformed probabilities and threshold ties", () => fixture(runtime => Effect.gen(function* () {
  const plan = yield* prepareSemanticContext(runtime, spec)
  const receipt = decisionFor(plan)
  expect(selectContext(plan, { ...receipt, requestSha256: "0".repeat(64) })._tag).toBe("Left")
  expect(selectContext(plan, { ...receipt, truncated: true })._tag).toBe("Left")
  expect(selectContext(plan, { ...receipt, weightUpdate: 1 })._tag).toBe("Left")
  const answer = receipt.decisions[0]!
  for (const probabilities of [{ door: 1 }, { door: 0.9, calendar: 0.5, NONE: 0, NEED_MORE: 0 }, { door: NaN, calendar: 0, NONE: 0, NEED_MORE: 0 }]) {
    expect(selectContext(plan, { ...receipt, decisions: [{ ...answer, probabilities }] })._tag).toBe("Left")
  }
  const tied = unwrap(selectContext(plan, { ...receipt, decisions: [{ ...answer, probabilities: { door: 0.5, calendar: 0.5, NONE: 0, NEED_MORE: 0 }, confidence: 0.5 }] }))
  expect(tied.status).toBe("NEED_MORE")
  expect(tied.reason).toBe("UNCERTAIN_SELECTION")
  const oversize = unwrap(selectContext(plan, { ...receipt, status: "needs_original_selection", decisions: [] }))
  expect(oversize.reason).toBe("BACKEND_INPUT_LIMIT")
})))

it("rejects unknown roots, duplicate candidates and budget overflow without truncating exceptions", () => fixture(runtime => Effect.gen(function* () {
  const snapshot = yield* runtime.snapshot
  expect(buildContextPlan({ ...spec, candidates: [spec.candidates[0], spec.candidates[0]] }, snapshot.canonical)._tag).toBe("Left")
  expect(buildContextPlan({ ...spec, mandatoryRelationUids: ["missing"] }, snapshot.canonical)._tag).toBe("Left")
  const plan = yield* prepareSemanticContext(runtime, { ...spec, maximumContextBytes: 50 })
  const result = yield* Effect.either(executeSemanticContext(runtime, plan, decisionFor(plan), cell, noHttp))
  expect(Either.isLeft(result) && "code" in result.left && result.left.code).toBe("CONTEXT_BUDGET_EXCEEDED")
})))

it("refuses stale plans before and after a model call", () => fixture(runtime => Effect.gen(function* () {
  const snapshot = yield* runtime.snapshot
  const plan = yield* prepareSemanticContext(runtime, spec)
  const changed = { ...snapshot, canonical: { ...snapshot.canonical, revision: snapshot.canonical.revision + 1 } }
  const stale = { ...runtime, snapshot: Effect.succeed(changed) }
  const before = yield* Effect.either(executeSemanticContext(stale, plan, decisionFor(plan), cell, noHttp))
  expect(Either.isLeft(before) && "code" in before.left && before.left.code).toBe("PLAN_STALE")
  let called = false
  const racing = { ...runtime, snapshot: Effect.suspend(() => Effect.succeed(called ? changed : snapshot)) }
  const after = yield* Effect.either(executeSemanticContext(racing, plan, decisionFor(plan), cell, fixtureHttp(() => { called = true })))
  expect(called).toBe(true)
  expect(Either.isLeft(after) && "code" in after.left && after.left.code).toBe("PLAN_STALE")
})))

it("refuses missing required exception references", () => fixture(runtime => Effect.gen(function* () {
  const snapshot = yield* runtime.snapshot
  const atoms = snapshot.canonical.atoms.map(a => a.key.atomUid === "relation:door" ? { ...a, references: a.references.filter(r => r.role !== "exception") } : a)
  const altered = { ...runtime, snapshot: Effect.succeed({ ...snapshot, canonical: { ...snapshot.canonical, atoms } }) }
  const plan = yield* prepareSemanticContext(altered, spec)
  const result = yield* Effect.either(assembleSemanticContext(altered, plan, decisionFor(plan)))
  expect(Either.isLeft(result) && "code" in result.left && result.left.code).toBe("ROLE_INVALID")
})))

it("keeps two role occurrences when one participant fills two roles", () => fixture(runtime => Effect.gen(function* () {
  const snapshot = yield* runtime.snapshot
  const atoms = snapshot.canonical.atoms.map(a => a.key.atomUid === "relation:door" ? {
    ...a, references: a.references.map(r => r.role === "evidence" ? { ...r, target: { ...r.target, atomUid: "door:subject" } } : r)
  } : a)
  const shared = { ...runtime, snapshot: Effect.succeed({ ...snapshot, canonical: { ...snapshot.canonical, atoms } }) }
  const plan = yield* prepareSemanticContext(shared, spec)
  const result = yield* assembleSemanticContext(shared, plan, decisionFor(plan))
  const roles = result.assembly?.payload.frames[1]?.roles
  expect(roles?.map(r => r.role)).toEqual(["subject", "context", "evidence", "exception"])
  expect(roles?.[0]?.key).toEqual(roles?.[2]?.key)
  const bundle = projectSemanticContext(plan, result.selection, result.assembly, { path: "fixture.json", sha256: contextHash(result) })
  expect(bundle.nodes.filter(n => n.properties["standard_graph_role"] === "CONTEXT_ROLE")).toHaveLength(12)
  expect(bundle.nodes.filter(n => n.properties["standard_graph_role"] === "CONTEXT_PARTICIPANT")).toHaveLength(11)
})))

it("executes one complete joint context, then records an attributed outcome without canonical mutation", () => fixture(runtime => Effect.gen(function* () {
  const before = yield* runtime.snapshot
  const plan = yield* prepareSemanticContext(runtime, spec)
  const prompts: string[] = []
  const result = yield* executeSemanticContext(runtime, plan, decisionFor(plan), cell, fixtureHttp(body => { prompts.push(body) }))
  expect(prompts).toHaveLength(1)
  expect(prompts[0]).toContain("relation:mandatory")
  expect(prompts[0]).toContain("relation:companion")
  expect(prompts[0]).toContain("door:exception")
  expect(prompts[0]).not.toContain("calendar")
  if (result.trace === null) return yield* Effect.die("fixture did not execute")
  const outcome = yield* stageSemanticContextOutcome(runtime, { traceContent: result.trace.traceContent, observed: "door stayed closed", source: "SCRIPTED_TEST_OBSERVATION" })
  expect(outcome.selectionSha256).toBe(contextHash(result.selection))
  expect(outcome.status).toBe("CALLER_DECLARED_NOT_INDEPENDENTLY_VERIFIED")
  expect(outcome.weightUpdate).toBeNull()
  expect((yield* runtime.snapshot).canonical).toEqual(before.canonical)
})))

it("exports actual role-preserving RDF queried and checked by existing standards tools", () => fixture(runtime => Effect.gen(function* () {
  const plan = yield* prepareSemanticContext(runtime, spec)
  const result = yield* assembleSemanticContext(runtime, plan, decisionFor(plan))
  const artifactDirectory = "docs/operations/artifacts/jev_context_2026-10-09"
  const assemblyBytes = new TextEncoder().encode(`${JSON.stringify(result, null, 2)}\n`)
  const bundle = projectSemanticContext(plan, result.selection, result.assembly, { path: `${artifactDirectory}/fixture-assembly.json`, sha256: createHash("sha256").update(assemblyBytes).digest("hex") })
  const projection = unwrap(compileKgBundle([{ sourceId: "context", rawBytes: new TextEncoder().encode(JSON.stringify(bundle)) }], "v2"))
  const prefix = "PREFIX p: <https://hswm.invalid/kg-bundle-rdf/v1/prop/> PREFIX r: <https://hswm.invalid/kg-bundle-rdf/v1/rel/> PREFIX role: <https://hswm.invalid/kg-bundle-rdf/v1/role/> "
  const rows = yield* queryKgBundle(projection, prefix+"SELECT ?name ?ordinal ?content WHERE { ?f a role:CONTEXT_FRAME ; p:name ?name ; r:HAS_PARTICIPATION ?slot . ?slot p:role \"exception\" ; p:ordinal ?ordinal ; r:REFERENCES/p:content_utf8 ?content }")
  expect(Array.isArray(rows) && rows.length).toBe(3)
  for (const file of ["schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl", "ontology/queries/hswm_jev_context_2026-10-09/shapes.ttl"]) {
    const bytes = yield* Effect.promise(() => readFile(join(root, file)))
    const report = yield* validateKgShacl(projection, bytes)
    expect(report.results).toEqual([])
    expect(report.conforms).toBe(true)
  }
  const broken = { ...bundle, relations: bundle.relations.filter(r => !r.from_uid.includes("context-role-")) }
  const invalid = unwrap(compileKgBundle([{ sourceId: "broken", rawBytes: new TextEncoder().encode(JSON.stringify({ ...broken, expected_counts: { ...bundle.expected_counts, relations: broken.relations.length } })) }], "v2"))
  const shapes = yield* Effect.promise(() => readFile(join(root, "ontology/queries/hswm_jev_context_2026-10-09/shapes.ttl")))
  expect((yield* validateKgShacl(invalid, shapes)).conforms).toBe(false)
  if (process.env["HSWM_EXPORT_CONTEXT_FIXTURE"] === "1") {
    yield* Effect.promise(() => mkdir(join(root, artifactDirectory), { recursive: true }))
    for (const [name, value] of [["fixture-plan.json", plan], ["fixture-decision.json", decisionFor(plan)], ["fixture-assembly.json", result], ["fixture-graph.v1.json", bundle]] as const) {
      yield* Effect.promise(() => writeFile(join(root, artifactDirectory, name), `${JSON.stringify(value, null, 2)}\n`, { flag: "wx" }))
    }
  }
})))

it("handles bounded Jev transport and retains infrastructure failure as failure", () => fixture(runtime => Effect.gen(function* () {
  const plan = yield* prepareSemanticContext(runtime, spec)
  const layer = Layer.succeed(BoundedSubprocess, { observe: command => {
    expect(command.argv).toEqual(["jev-dgx", "decide", "-"])
    expect(command.timeoutMs).toBe(240000)
    expect(command.killProcessGroup).toBe(true)
    expect(JSON.parse(new TextDecoder().decode(command.stdin))).toEqual(plan.request)
    return Effect.succeed({ exitCode: 0, signal: null, timedOut: false, outputTruncated: false, launchError: null, stdout: new TextEncoder().encode(JSON.stringify(decisionFor(plan))), stderr: new Uint8Array() })
  } })
  const receipt = yield* requestOpenJevContext(plan, "jev-dgx", root, {}).pipe(Effect.provide(layer))
  expect(unwrap(selectContext(plan, receipt)).status).toBe("SELECTED")
  const failed = Layer.succeed(BoundedSubprocess, { observe: () => Effect.succeed({ exitCode: null, signal: "SIGTERM", timedOut: true, outputTruncated: false, launchError: null, stdout: new Uint8Array(), stderr: new Uint8Array() }) })
  const outcome = yield* Effect.either(requestOpenJevContext(plan, "jev-dgx", root, {}).pipe(Effect.provide(failed)))
  expect(Either.isLeft(outcome) && "code" in outcome.left && outcome.left.code).toBe("JEV_TRANSPORT_FAILED")
})))

it("uses the CLI composition root to prepare and assemble the same real file store", () => run(withContextFixture((runtime, durableRoot) => Effect.gen(function* () {
  const base = { contract: "hswm-semantic-context-cli/v1", durableRoot, journalLineageId: "context-journal", schema, spec }
  const plan = yield* prepareSemanticContext(runtime, spec)
  const prepared = yield* semanticContextProcess({ ...base, action: "prepare" })
  expect(prepared).toEqual(JSON.parse(JSON.stringify(plan)))
  expect(JSON.parse(yield* semanticContextStdinProcess(JSON.stringify({ ...base, action: "prepare" })))).toEqual(prepared)
  const assembled = yield* semanticContextProcess({ ...base, action: "assemble", expectedPlanSha256: plan.planSha256, decision: decisionFor(plan) })
  expect(assembled).toEqual(JSON.parse(JSON.stringify(yield* assembleSemanticContext(runtime, plan, decisionFor(plan)))))
  const sourcePath = join(durableRoot, "assembled.json")
  yield* Effect.promise(() => writeFile(sourcePath, JSON.stringify(assembled)))
  const projectRequest = { ...base, action: "project", expectedPlanSha256: plan.planSha256, decision: decisionFor(plan), assemblySourcePath: "assembled.json" }
  const projected = yield* semanticContextProcess(projectRequest, durableRoot)
  expect(projected).toEqual(projectSemanticContext(plan, (yield* assembleSemanticContext(runtime, plan, decisionFor(plan))).selection, (yield* assembleSemanticContext(runtime, plan, decisionFor(plan))).assembly, { path: "assembled.json", sha256: contextHash(assembled) }))
  yield* Effect.promise(() => writeFile(sourcePath, "{}"))
  const mismatch = yield* Effect.either(semanticContextProcess(projectRequest, durableRoot))
  expect(Either.isLeft(mismatch) && "code" in mismatch.left && mismatch.left.code).toBe("ASSEMBLY_SOURCE_MISMATCH")
  expect(Either.isLeft(yield* Effect.either(semanticContextProcess({ ...projectRequest, assemblySourcePath: "../outside.json" }, durableRoot)))).toBe(true)
})).pipe(Effect.provide(NodePosixServicesLive))))

it("refuses duplicate JSON keys and oversized stdin before opening any store", () => run(Effect.gen(function* () {
  for (const source of ['{"action":"prepare","action":"execute"}', " ".repeat(1048577), '{"threshold":1e999}']) {
    expect(Either.isLeft(yield* Effect.either(semanticContextStdinProcess(source)))).toBe(true)
  }
}).pipe(Effect.provide(NodePosixServicesLive))))
