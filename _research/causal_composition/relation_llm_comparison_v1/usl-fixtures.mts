/** Local calibration observation bridge derived from source-pinned predecessor run.mts.
 * Same-read native metadata is retained; this is an authored fixture, not live KG.
 */
import { createHash } from "node:crypto"
import { createRequire } from "node:module"
import { readFile } from "node:fs/promises"
import { resolve } from "node:path"
import { pathToFileURL } from "node:url"
import type { CatalogTask } from "../relation_synthesis_usl_v1/fixtures.mjs"
import { captureUslNativeSnapshot, type UslNativeSnapshot } from "../../../src/hswm/effect-runtime/src/usl-native-snapshot.js"
import type { RelationGraph } from "../../../src/hswm/effect-runtime/src/relation-program-research.js"
const { Effect, Either, Ref } = createRequire(new URL("../../../src/hswm/effect-runtime/package.json", import.meta.url))("effect") as typeof import("effect")
const sha = (value: string | Buffer) => createHash("sha256").update(value).digest("hex")
const json = (value: unknown) => JSON.stringify(value)
const io = <A,>(f: () => Promise<A>) => Effect.tryPromise({try:f,catch:()=>new Error("USL_FIXTURE_IO_FAILED")})
const ensure = (v:boolean,code:string) => v ? Effect.void : Effect.fail(new Error(code))
const checked = <A,E>(v:import("effect").Either.Either<A,E>) => Either.isRight(v) ? Effect.succeed(v.right) : Effect.fail(new Error("USL_FIXTURE_INVALID"))
interface UslConnection { readonly hswm:(request:unknown,options:unknown,authority:unknown)=>import("effect").Effect.Effect<unknown,Error> }
const semanticView = (graph: RelationGraph) => [...graph.relations].sort((a,b) => a.uid.localeCompare(b.uid)).map(r => ({ ...r, participants: [...r.participants] }))
const graphOf = (snapshot: UslNativeSnapshot, owner: CatalogTask): import("effect").Either.Either<RelationGraph, Error> => Either.try({
  try: () => {
    // The read callback returned these exact bytes in this invocation. Preserve
    // owner serialization order explicitly; v2 USL canonicalizes named roles.
    // Only UID/role ordering is read here, never the task's outcome labels.
    if (snapshot.native.sourceDigest !== `sha256:${sha(owner.raw)}`) throw new Error("owner order metadata source mismatch")
    return { relations: snapshot.relations.map(r => {
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
    const order = owner.graph.relations.find(native => native.uid === r.nativeRelationUid)?.participants
    if (!order || order.length !== r.participants.length || order.some(p => !r.participants.some(q => q.role === p.role && q.nativeUid === p.uid))) {
      throw new Error("owner order metadata cannot restore a lost or changed role binding")
    }
    return { uid:r.nativeRelationUid,meaning,participants:order.map(p=>({role:p.role,uid:p.uid})) }
  }) } },
  catch: e => e instanceof Error ? e : new Error(String(e))
})

export const observeCalibrationTasks = (uslRoot:string,tasks:ReadonlyArray<CatalogTask>) => Effect.gen(function* () {
  const pins = JSON.parse(yield* io(()=>readFile(new URL("../relation_synthesis_usl_v1/source-pins.v4.json",import.meta.url),"utf8"))) as {bindings:ReadonlyArray<{repository:string,path:string,sha256:string}>}
  const sourcePins = pins.bindings.filter(p=>p.repository==="USL")
  const checkPins = Effect.forEach(sourcePins,p=>Effect.gen(function*(){
    const bytes = yield* io(()=>readFile(resolve(uslRoot,p.path)))
    yield* ensure(sha(bytes)===p.sha256,"USL_SOURCE_DRIFT:"+p.path)
  }),{concurrency:4,discard:true})
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
    const graph = yield* checked(graphOf(snapshot,task))
    yield* ensure(json(semanticView(graph)) === json(semanticView(task.graph)), `native role/meaning mapping lost:${task.id}`)
    return { task, snapshot, graph, snapshotBytes: Buffer.byteLength(json(snapshot)) }
  })

  const rows = yield* Effect.forEach(tasks,observe,{concurrency:1})
  yield* checkPins
  return {rows,counts:yield* Ref.get(counts),sourcePins}
})
