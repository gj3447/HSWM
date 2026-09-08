/** Effect shell for a local authored instrument study; no live KG or LLM calls. */
import { createHash } from "node:crypto"
import { createRequire } from "node:module"
import { readFile, writeFile, mkdir } from "node:fs/promises"
import { dirname, resolve } from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"
import { performance } from "node:perf_hooks"
import { catalogTask, changedOwnerVersion, type CatalogTask } from "./fixtures.mjs"
import { captureUslNativeSnapshot, type UslNativeSnapshot } from "../../../src/hswm/effect-runtime/src/usl-native-snapshot.js"
import { enumerateCandidates, evaluateProgram, fitProgram, programComplexity, type ProgramAST, type RelationGraph, type TrainingExample } from "../../../src/hswm/effect-runtime/src/relation-program-research.js"

const { Effect, Either, Ref } = createRequire(new URL("../../../src/hswm/effect-runtime/package.json", import.meta.url))("effect") as typeof import("effect")
const base = dirname(fileURLToPath(import.meta.url))
const root = resolve(base, "../../..")
const arg = (flag: string, fallback: string) => process.argv[process.argv.indexOf(flag) + 1] && process.argv.includes(flag) ? process.argv[process.argv.indexOf(flag) + 1]! : fallback
const uslRoot = resolve(arg("--usl-root", resolve(root, "../USL")))
const output = resolve(arg("--output", resolve(root, "results/raw/hswm_usl_relation_synthesis_2026-09-08/attempt-01.json")))
const pinFile = resolve(arg("--source-pins",resolve(base,"source-pins.v1.json")))
const sha = (value: string | Buffer) => createHash("sha256").update(value).digest("hex")
const json = (value: unknown) => JSON.stringify(value)
const io = <A,>(f: () => Promise<A>) => Effect.tryPromise({ try: f, catch: (e) => e instanceof Error ? e : new Error(String(e)) })
const ensure = (condition: boolean, detail: string) => condition ? Effect.void : Effect.fail(new Error(detail))
const checked = <A, E>(value: import("effect").Either.Either<A, E>) => Either.isRight(value) ? Effect.succeed(value.right) : Effect.fail(new Error(json(value.left)))
const sameSet = (a: ReadonlyArray<string>, b: ReadonlyArray<string>) => json([...a].sort()) === json([...b].sort())
const semanticView = (graph: RelationGraph) => [...graph.relations].sort((a,b) => a.uid.localeCompare(b.uid)).map(r => ({ ...r, participants: [...r.participants] }))
const graphOf = (snapshot: UslNativeSnapshot): import("effect").Either.Either<RelationGraph, Error> => Either.try({
  try: () => ({ relations: snapshot.relations.map(r => {
    const description = r.meaning.definition["description"]
    if (typeof description !== "string") throw new Error("missing meaning description")
    const meaning = snapshot.native.adapter === "property-graph/v1" ? description : (() => {
      if (snapshot.native.adapter !== "property-graph/v2") throw new Error("unqualified native adapter profile")
      const parsed = JSON.parse(description)
      if (parsed?.schema !== "property-graph-meaning/v2" || typeof parsed.type !== "string" || !parsed.type ||
        typeof parsed.direction?.from_uid !== "string" || typeof parsed.direction?.to_uid !== "string" ||
        !r.participants.some(p => p.nativeUid === parsed.direction.from_uid) || !r.participants.some(p => p.nativeUid === parsed.direction.to_uid)) {
        throw new Error("invalid native directed-meaning profile")
      }
      return `Declared KG relation: ${parsed.type}`
    })()
    return { uid:r.nativeRelationUid,meaning,participants:r.participants.map(p=>({role:p.role,uid:p.nativeUid})) }
  }) }),
  catch: e => e instanceof Error ? e : new Error(String(e))
})

interface Protocol {
  readonly protocol_id: string
  readonly primitive_roles: ReadonlyArray<{ readonly meaning: string; readonly fromRole: string; readonly toRole: string }>
  readonly search: { readonly maxDepth: number; readonly maxNodes: number; readonly maxCandidates: number; readonly executionBudget: number }
  readonly splits: Readonly<Record<string, { readonly seeds: ReadonlyArray<number>; readonly affected_artifacts: number; readonly role_arity: number }>>
  readonly scientific_status: unknown
}

interface UslConnection {
  readonly hswm: (request: unknown, options: unknown, authority: unknown) => import("effect").Effect.Effect<unknown, Error>
}

const run = Effect.gen(function* () {
  const started = performance.now()
  const protocolBytes = yield* io(() => readFile(resolve(base,"protocol.v1.json"), "utf8"))
  const protocol = JSON.parse(protocolBytes) as Protocol
  const pins = JSON.parse(yield* io(() => readFile(pinFile, "utf8"))) as {
    readonly bindings: ReadonlyArray<{ readonly repository: "HSWM" | "USL"; readonly path: string; readonly sha256: string }>
  }
  const checkPins = Effect.forEach(pins.bindings, pin => Effect.gen(function* () {
    const content = yield* io(() => readFile(resolve(pin.repository === "USL" ? uslRoot : root, pin.path)))
    yield* ensure(sha(content) === pin.sha256, `SOURCE_DRIFT:${pin.repository}:${pin.path}`)
  }), { concurrency: 8, discard: true })
  yield* checkPins
  const load = (path: string) => io(() => import(pathToFileURL(resolve(uslRoot,path)).href))
  const adapters = yield* load("src/adapters.ts")
  const pg = yield* load("src/integrations/property-graph.ts")
  const digest = yield* load("src/language/digest.ts")
  const hswm = yield* load("src/integrations/hswm.ts")
  const application = yield* load("src/application.ts")
  const locators = yield* load("src/locator.ts")
  const adapt = (raw: string): import("effect").Either.Either<any, Error> => pg.adaptPropertyGraph(raw, { namespace: "hswm.relation.instrument" })
  const fixedNow = Date.parse("2026-09-08T08:00:00.000Z") / 1000
  const counts = yield* Ref.make({ ownerReads: 0, resolverCalls: 0 })

  // Policies are prepared from the author's owner fixture BEFORE an observation.
  // They are not inferred from a returned report or advertised as real authority.
  const authority = (task: CatalogTask, raw = task.raw) => Effect.gen(function* () {
    const graph: any = yield* checked(adapt(raw))
    const bindings = graph.plan.links.map((link: any, i: number) => ({ link: link.name, role: "reference", field: `available_${i}` }))
    return {
      expected: { nativeSourceDigest: digest.digestSource(raw), hswmPlanDigest: hswm.hswmDigest(graph.plan) },
      input: { policy: { schema_version: "hswm-usl-observation-policy/v2", namespace: graph.plan.namespace,
        plan_digest: hswm.hswmDigest(graph.plan), usl_plan_digest: digest.planDigest(graph.plan), source_digest: null,
        max_age_seconds: 60, bindings,
        resources: graph.plan.resources.filter((r: any) => graph.plan.links.some((l: any) => l.participants.some((p: any) => p.resource === r.name)))
          .map((r: any) => { const locator = locators.formatLocator(r.locator); return { name: r.name, content_hash: task.resourceHashes[locator], resolved_locator: locator } })
      }, allowed_reads: bindings.map((b: any) => [b.role,b.field]), now: fixedNow, revision: task.id }
    }
  })
  const connection = (task: CatalogTask, read: () => import("effect").Effect.Effect<string>, onResolve = Effect.void): UslConnection => adapters.connectUsl({
    read: () => Effect.zipRight(Ref.update(counts,c => ({ ...c,ownerReads:c.ownerReads+1 })), read()), adapt,
    policy: { ...application.DEFAULT_USL_POLICY, allowedLocators: Object.keys(task.resourceHashes), maxResources: 64,
      maxInputBytes: 1_048_576, maxOutputBytes: 1_048_576,
      resolvers: { resolve: (locator: unknown) => Effect.gen(function* () {
        yield* Ref.update(counts,c => ({ ...c,resolverCalls:c.resolverCalls+1 }))
        yield* onResolve
        const address = locators.formatLocator(locator)
        const contentHash = task.resourceHashes[address]
        yield* ensure(typeof contentHash === "string", "resolver escaped authored fixture policy")
        return { locator,resolvedLocator:address,contentHash,resolvedAt:"2026-09-08T08:00:00.000Z",guaranteeLevel:"pure",matchCount:1 }
      }) }
    }
  })
  const observe = (task: CatalogTask) => Effect.gen(function* () {
    const expected = yield* authority(task)
    const usl = connection(task, () => Effect.succeed(task.raw))
    const input = yield* usl.hswm({ task: task.id }, { links: task.graph.relations.map(r => r.uid) }, expected.input)
    const snapshot = yield* checked(captureUslNativeSnapshot(input, expected.expected))
    const graph = yield* checked(graphOf(snapshot))
    yield* ensure(json(semanticView(graph)) === json(semanticView(task.graph)), `native role/meaning mapping lost:${task.id}`)
    return { task, snapshot, graph, snapshotBytes: Buffer.byteLength(json(snapshot)) }
  })

  // The first call changes its owner while resolving. It must still finish v1.
  const probe = catalogTask(1,1,2), revisedRaw = changedOwnerVersion(probe)
  const owner = yield* Ref.make(probe.raw)
  const probeUs = connection(probe, () => Ref.get(owner), Ref.set(owner,revisedRaw))
  const firstAuthority = yield* authority(probe)
  const probeLinks = probe.graph.relations.map(r => r.uid)
  const firstInput = yield* probeUs.hswm(undefined,{links:probeLinks},firstAuthority.input)
  const first = yield* checked(captureUslNativeSnapshot(firstInput,firstAuthority.expected))
  const firstBytes = json(first)
  const oldPinAttempt = yield* Effect.either(probeUs.hswm(undefined,{links:probeLinks},firstAuthority.input))
  yield* ensure(Either.isLeft(oldPinAttempt),"changed owner accepted with old plan authority")
  const secondAuthority = yield* authority(probe,revisedRaw)
  const secondInput = yield* probeUs.hswm(undefined,{links:probeLinks},secondAuthority.input)
  const second = yield* checked(captureUslNativeSnapshot(secondInput,secondAuthority.expected))
  yield* ensure(first.native.sourceDigest !== second.native.sourceDigest && json(first) === firstBytes,"snapshot refresh or immutability failure")
  const probeCounts = yield* Ref.get(counts)
  yield* ensure(probeCounts.ownerReads === 3,"each request must perform exactly one owner read")

  const splits = Object.fromEntries(Object.entries(protocol.splits).map(([name,split]) => [name,split.seeds.map(seed => catalogTask(seed,split.affected_artifacts,split.role_arity))])) as Record<string,ReadonlyArray<CatalogTask>>
  const A = yield* Effect.forEach(splits["A"]!,observe,{concurrency:1})
  const V = yield* Effect.forEach(splits["V"]!,observe,{concurrency:1})
  const enumeration = yield* checked(enumerateCandidates(protocol.primitive_roles,protocol.search))
  const examples = (rows: typeof A, native = false): ReadonlyArray<TrainingExample> => rows.map(r => ({ graph:native?r.task.graph:r.graph,focus:r.task.focus,expected:r.task.expected }))
  const train = yield* checked(fitProgram(enumeration.candidates,examples(A),protocol.search.executionBudget))
  const selected = yield* checked(fitProgram(train.best,examples(V),protocol.search.executionBudget))
  const nativeTrain = yield* checked(fitProgram(enumeration.candidates,examples(A,true),protocol.search.executionBudget))
  const nativeSelected = yield* checked(fitProgram(nativeTrain.best,examples(V,true),protocol.search.executionBudget))
  const program = selected.best[0]!, nativeProgram = nativeSelected.best[0]!
  const oneHop = enumeration.candidates.filter(p => programComplexity(p) <= 2)
  const seedFit = yield* checked(fitProgram(oneHop,examples(A),protocol.search.executionBudget))
  const seedSelect = yield* checked(fitProgram(seedFit.best,examples(V),protocol.search.executionBudget))
  const candidate = { schema_version:"hswm-relation-program-research-candidate/v1", program,
    revision_id:sha(json(program)), responsibility_owner:"relation-synthesis-research-custodian",
    source_snapshot_receipts:A.map(r=>r.snapshot.native.receipt.digest),training_outcome_digest:sha(json(A.map(r=>r.task.expected))),
    admission:"NOT_REQUESTED",causal_credit:"NOT_IDENTIFIED",claim:"FINITE_DSL_RESEARCH_CANDIDATE" }
  // Selection ends here. Serialize before generating/evaluating B observations.
  yield* io(() => mkdir(dirname(output),{recursive:true}))
  const candidateFile = `${output}.candidate.json`
  const candidateBytes = json(candidate)
  yield* io(() => writeFile(candidateFile,candidateBytes,"utf8"))
  const restoredBytes = yield* io(() => readFile(candidateFile,"utf8"))
  yield* ensure(restoredBytes === candidateBytes,"candidate restoration was not byte-identical")
  const restored: ProgramAST = JSON.parse(restoredBytes).program
  const sham: ProgramAST = program.tag === "Traverse" ? { ...program,toRole:"wrong_target_role" } : {tag:"Here"}
  const B = yield* Effect.forEach(splits["B"]!,observe,{concurrency:1})
  const retain = yield* Effect.forEach(splits["A_retain"]!,observe,{concurrency:1})
  const evaluate = (name: string, rows: typeof A, ast: ProgramAST | null, native = false) => Effect.gen(function* () {
    const values = yield* Effect.forEach(rows,row => Effect.gen(function* () {
      const result = ast === null ? { uids:A.find(a=>a.task.focus===row.task.focus)?.task.expected ?? [],counters:{programExecutions:0,nodeSteps:0} }
        : yield* checked(evaluateProgram(native?row.task.graph:row.graph,row.task.focus,ast,protocol.search.executionBudget))
      const actual = new Set(result.uids), expected = new Set(row.task.expected)
      return { task:row.task.id,pass:sameSet(result.uids,row.task.expected),errors:[...actual].filter(x=>!expected.has(x)).length+[...expected].filter(x=>!actual.has(x)).length,
        predicted:result.uids,expected:row.task.expected,snapshotReceipt:row.snapshot.native.receipt.digest,counters:result.counters }
    }))
    return { arm:name,correct:values.filter(v=>v.pass).length,total:values.length,errors:values.reduce((n,v)=>n+v.errors,0),
      counters:values.reduce((c,v)=>({programExecutions:c.programExecutions+v.counters.programExecutions,nodeSteps:c.nodeSteps+v.counters.nodeSteps}),{programExecutions:0,nodeSteps:0}),tasks:values }
  })
  const arms = [
    ["USL_INDUCED_PROGRAM",program,false],["NATIVE_INFORMATION_MATCHED_PROGRAM_INDUCTION",nativeProgram,true],
    ["FIXED_ONE_HOP_LIBRARY",seedSelect.best[0]!,false],["RAW_HISTORY_EXACT_UID_RECALL",null,false],
    ["REMOVE_TO_HERE",{tag:"Here"},false],["BYTE_EXACT_RESTORE",restored,false],["WRONG_TARGET_ROLE_SHAM",sham,false]
  ] as const
  const armResults = yield* Effect.forEach(arms,([name,ast,native]) => evaluate(name,B,ast,native))
  const retention = yield* evaluate("USL_SAME_REGIME_REUSE",retain,program)
  yield* checkPins
  const finalCounts = yield* Ref.get(counts)
  return { schema_version:"hswm-usl-relation-instrument-result/v1",status:"COMPLETED_INSTRUMENT_TRIAL",observed_on:new Date().toISOString(),
    protocol_id:protocol.protocol_id,protocol_sha256:sha(protocolBytes),source_pins_sha256:sha(yield* io(()=>readFile(pinFile))),
    scope:"AUTHORED_SYNTHETIC_SAME_PROCESS_NOT_G0_OR_G1",scientific_status:protocol.scientific_status,
    snapshot_probe:{status:"PASS",owner_reads:probeCounts.ownerReads,old_policy_rejected:true,first_snapshot_unchanged:true,
      first_native_source_digest:first.native.sourceDigest,next_native_source_digest:second.native.sourceDigest,usl_source_digest:first.usl.sourceDigest,
      first_snapshot:first},
    candidate,candidate_bytes_sha256:sha(candidateBytes),candidate_syntactically_absent_from_seed_library:programComplexity(program)>2,
    native_usl_selected_ast_equal:json(program)===json(nativeProgram),
    induction:{candidate_count:enumeration.candidates.length,train,selection:selected,native_train:nativeTrain,native_selection:nativeSelected,seed_train:seedFit,seed_selection:seedSelect},
    evaluation:armResults,same_regime_reuse:retention,
    accounting:{...finalCounts,task_snapshots:A.length+V.length+B.length+retain.length,snapshot_bytes:[...A,...V,...B,...retain].reduce((n,r)=>n+r.snapshotBytes,0),
      wall_seconds:(performance.now()-started)/1000,llm_calls:0,live_kg_calls:0,network_calls:0,
      model_tokens:"NOT_APPLICABLE_NO_LLM",human_minutes:"NOT_MEASURED",independent_seed_replications:0},
    nonclaims:["NO_INDEPENDENT_OUTCOME_CUSTODY","NO_CANONICAL_ADMISSION_OR_CAUSAL_CREDIT","NO_NEW_PRIMITIVE_OR_SCHEMA_INVENTION","NO_FCL_PROMOTION","NATIVE_BASELINE_USES_SAME_INDUCTION_NOT_PUBLISHED_AGENT_BASELINE","REUSE_IS_NOT_POST_SECOND_LEARNING_RETENTION"] }
})

const main = Effect.gen(function* () {
  yield* io(() => mkdir(dirname(output),{recursive:true}))
  // Refuse to replace an earlier attempt, whether positive, invalid or negative.
  yield* io(() => writeFile(output,json({status:"STARTED",started_at:new Date().toISOString()}),{encoding:"utf8",flag:"wx"}))
  const result = yield* Effect.either(run)
  if (Either.isLeft(result)) {
    yield* io(() => writeFile(output,json({status:"INSTRUMENT_ERROR",error:String(result.left),nonclaim:"NO_EFFICACY_VERDICT"})+"\n","utf8"))
    return yield* Effect.fail(result.left)
  }
  yield* io(() => writeFile(output,JSON.stringify(result.right,null,2)+"\n","utf8"))
  process.stdout.write(json({status:result.right.status,output,candidate:result.right.candidate.program,
    arms:result.right.evaluation.map(({arm,correct,total})=>({arm,correct,total})),accounting:result.right.accounting})+"\n")
})
await Effect.runPromise(main)
