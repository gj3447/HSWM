/**
 * A standards-oriented, read-only PROV-O / JSON-LD 1.1 exchange view over a
 * bounded research coordination graph. It is a declared local coordination
 * record and does not write back, adjudicate provenance, or establish HSWM
 * causal learning or efficacy.
 */
import { createHash } from "node:crypto"

import { Data, Effect, Either } from "effect"
import jsonld from "jsonld"

import { canonicalJsonBytes } from "./canonical-atom-v2-json.js"
import { parseResearchGraph, researchGraphState, type ResearchGraph, type ResearchEvent, type ResearchManifest } from "./research-graph-domain.js"

const BASE = "https://hswm.invalid/research-coordination/v1/"
const PROV = "http://www.w3.org/ns/prov#"
const RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"

export const HSWM_RESEARCH_GRAPH_PROJECTION_V1 = "hswm-research-graph-projection/v1" as const
export const HSWM_RESEARCH_GRAPH_RDF_PROFILE = "RDF_1_1_N_QUADS_BLANK_NODE_FREE_LEXICALLY_SORTED_PROFILE" as const
export const HSWM_RESEARCH_GRAPH_CLAIM_CEILING = "LOCAL_RESEARCH_COORDINATION_DECLARATION_ONLY_NOT_PROVENANCE_TRUTH_NOT_CANONICAL_AUTHORITY_NOT_CAUSAL_CREDIT_NOT_LEARNING_NOT_EFFICACY" as const

type Json = null | boolean | number | string | readonly Json[] | { readonly [key: string]: Json }
type JsonObject = { readonly [key: string]: Json }

export interface ResearchGraphProjection {
  readonly jsonld: JsonObject
  readonly nquads: string
  readonly manifest: JsonObject
}

export class ResearchGraphProjectionError extends Data.TaggedError("ResearchGraphProjectionError")<{
  readonly code: "INVALID_GRAPH" | "JSONLD_PROCESSING_FAILED" | "PROFILE_VIOLATION"
  readonly detail: string
}> {}

const hash = (value: string | Uint8Array): string => createHash("sha256").update(value).digest("hex")
const encoded = (value: string): string => encodeURIComponent(value)
const resource = (scope: string, kind: string, id: string): string => `${BASE}graph/${scope}/${kind}/${encoded(id)}`
const literal = (value: string | number | boolean): readonly JsonObject[] => [{ "@value": value }]
const dateTime = (value: string): readonly JsonObject[] => [{ "@value": value, "@type": "http://www.w3.org/2001/XMLSchema#dateTime" }]
const idRef = (id: string): readonly JsonObject[] => [{ "@id": id }]
const types = (...values: readonly string[]): readonly string[] => values
const rejectRemoteDocument = (_url: string): Promise<never> =>
  Promise.reject(new Error("remote JSON-LD document loading is forbidden"))

const node = (id: string, type: readonly string[], properties: Readonly<Record<string, Json>>): JsonObject =>
  Object.freeze({ "@id": id, "@type": types(...type), ...properties })

const context: JsonObject = Object.freeze({
  rc: BASE,
  prov: PROV,
  rdf: RDF,
  contractVersion: "rc:contractVersion",
  rdfProfile: "rc:rdfProfile",
  sourceGraphSha256: "rc:sourceGraphSha256",
  jsonldSha256: "rc:jsonldSha256",
  nquadsSha256: "rc:nquadsSha256",
  writeBack: "rc:writeBack",
  claimCeiling: "rc:claimCeiling",
  sourceLocator: "rc:sourceLocator",
  goal: "rc:goal",
  targetRef: "rc:targetRef",
  maxParallelism: "rc:maxParallelism",
  nativeId: "rc:nativeId",
  authority: "rc:authority",
  scope: "rc:scope",
  disposition: "rc:disposition",
  claim: "rc:claim",
  falsifier: "rc:falsifier",
  role: "rc:role",
  question: "rc:question",
  acceptance: "rc:acceptance",
  budgetTokens: "rc:budgetTokens",
  usedTokens: "rc:usedTokens",
  overBudget: "rc:overBudget",
  dependsOn: { "@id": "rc:dependsOn", "@type": "@id" },
  refutes: { "@id": "rc:refutes", "@type": "@id" },
  recordsEvent: { "@id": "rc:recordsEvent", "@type": "@id" },
  model: "rc:model",
  summary: "rc:summary",
  eventType: "rc:eventType",
  taskStatus: "rc:taskStatus",
  sha256: "rc:sha256",
  locator: "rc:locator",
  title: "rc:title"
})

const eventActivity = (event: Extract<ResearchEvent, { readonly type: "START" }>, finish: Extract<ResearchEvent, { readonly type: "FINISH" }> | null, manifest: ResearchManifest, scope: string): readonly JsonObject[] => {
  const plan = manifest.tasks.find((task) => task.id === event.taskId)
  const planId = plan === undefined ? resource(scope, "task", event.taskId) : resource(scope, "task", plan.id)
  const actorId = resource(scope, "agent", event.actor)
  const activityId = resource(scope, "activity", event.taskId)
  const agent = node(actorId, ["prov:Agent", "rc:RecordedAgent"], { "rc:nativeId": literal(event.actor) })
  const activity = node(activityId, ["prov:Activity", "rc:RecordedActivity"], {
    "prov:wasAssociatedWith": idRef(actorId),
    "prov:used": idRef(planId),
    "prov:startedAtTime": dateTime(event.at),
    ...(finish === null ? {} : { "prov:endedAtTime": dateTime(finish.at), "prov:generated": idRef(resource(scope, "result", finish.id)) }),
    "rc:eventType": literal(finish === null ? "START" : "START_FINISH"),
    "rc:scope": literal(`Recorded start for task ${event.taskId}`),
    "rc:disposition": literal(finish === null ? "RECORDED_START" : finish.disposition),
    "rc:model": literal(event.model)
  })
  return [agent, activity]
}

const projectionDocument = (graph: ResearchGraph, sourceGraphSha256: string): JsonObject => {
  const state = researchGraphState(graph)
  const graphId = resource(sourceGraphSha256, "source-graph", state.manifest.id)
  const items: JsonObject[] = []
  for (const source of state.manifest.sources) {
    items.push(node(resource(sourceGraphSha256, "source", source.id), ["prov:Entity", "rc:Source"], {
      "rc:nativeId": literal(source.id),
      "rc:title": literal(source.title), "rc:locator": literal(source.locator), "rc:authority": literal(source.authority),
      ...(source.sha256 === null ? {} : { "rc:sha256": literal(source.sha256) })
    }))
  }
  for (const hypothesis of state.manifest.hypotheses) {
    items.push(node(resource(sourceGraphSha256, "hypothesis", hypothesis.id), ["prov:Entity", "rc:Hypothesis"], {
      "rc:nativeId": literal(hypothesis.id),
      "rc:claim": literal(hypothesis.claim), "rc:scope": literal(hypothesis.scope), "rc:falsifier": literal(hypothesis.falsifier),
      "rc:disposition": literal("CANDIDATE"),
      "prov:wasDerivedFrom": hypothesis.sourceIds.map((id) => ({ "@id": resource(sourceGraphSha256, "source", id) })),
      ...(hypothesis.predecessorIds.length === 0 ? {} : { "prov:wasInfluencedBy": hypothesis.predecessorIds.map((id) => ({ "@id": resource(sourceGraphSha256, "hypothesis", id) })) })
    }))
  }
  for (const entry of state.tasks) {
    const task = entry.task
    const taskDisposition = entry.status === "COMPLETE" ? "COMPLETED" : entry.status === "RUNNING" ? "ACTIVE" : "PLANNED"
    items.push(node(resource(sourceGraphSha256, "task", task.id), ["prov:Plan", "rc:TaskPlan"], {
      "rc:nativeId": literal(task.id), "prov:wasDerivedFrom": idRef(resource(sourceGraphSha256, "hypothesis", task.hypothesisId)),
      "rc:role": literal(task.role), "rc:question": literal(task.question), "rc:acceptance": literal(task.acceptance),
      "rc:scope": literal(`Declared task ${task.id}`), "rc:disposition": literal(taskDisposition),
      "rc:taskStatus": literal(entry.status), "rc:budgetTokens": literal(task.budgetTokens), "rc:overBudget": literal(entry.overBudget),
      ...(task.dependsOn.length === 0 ? {} : { "rc:dependsOn": task.dependsOn.map((id) => ({ "@id": resource(sourceGraphSha256, "task", id) })) })
    }))
  }
  const finishes = new Map(graph.events.filter((event): event is Extract<ResearchEvent, { readonly type: "FINISH" }> => event.type === "FINISH").map((event) => [event.taskId, event]))
  for (const event of graph.events) {
    if (event.type === "START") items.push(...eventActivity(event, finishes.get(event.taskId) ?? null, state.manifest, sourceGraphSha256))
    if (event.type === "FINISH") {
      const task = state.manifest.tasks.find((candidate) => candidate.id === event.taskId)
      const hypothesisId = task === undefined ? null : task.hypothesisId
      items.push(node(resource(sourceGraphSha256, "result", event.id), ["prov:Entity", "rc:Result"], {
        "rc:nativeId": literal(event.id), "rc:scope": literal(`Recorded result for task ${event.taskId}`), "rc:disposition": literal(event.disposition),
        "rc:summary": literal(event.summary), "rc:usedTokens": literal(event.usedTokens),
        "prov:wasDerivedFrom": event.sourceIds.map((id) => ({ "@id": resource(sourceGraphSha256, "source", id) })),
        "prov:wasGeneratedBy": idRef(resource(sourceGraphSha256, "activity", event.taskId)),
        ...(event.disposition === "REFUTED_IN_SCOPE" && hypothesisId !== null ? { "rc:refutes": idRef(resource(sourceGraphSha256, "hypothesis", hypothesisId)) } : {})
      }))
    }
  }
  items.push(node(graphId, ["prov:Entity", "rc:SourceGraph"], {
    "rc:sourceLocator": literal(`CALLER_AUTHORED_RESEARCH_GRAPH:${state.manifest.id}`), "rc:sourceGraphSha256": literal(sourceGraphSha256),
    "rc:goal": literal(state.manifest.goal), "rc:targetRef": literal(state.manifest.targetRef), "rc:maxParallelism": literal(state.manifest.maxParallelism)
  }))
  items.push(node(resource(sourceGraphSha256, "projection", state.manifest.id), ["prov:Entity", "rc:ResearchGraphProjection"], {
    "prov:wasDerivedFrom": idRef(graphId),
    "rc:contractVersion": literal(HSWM_RESEARCH_GRAPH_PROJECTION_V1),
    "rc:rdfProfile": literal(HSWM_RESEARCH_GRAPH_RDF_PROFILE),
    "rc:sourceGraphSha256": literal(sourceGraphSha256),
    "rc:writeBack": literal("FORBIDDEN"),
    "rc:claimCeiling": literal(HSWM_RESEARCH_GRAPH_CLAIM_CEILING)
  }))
  return Object.freeze({ "@context": context, "@graph": Object.freeze(items) })
}

/** Finds an RDF blank-node token without confusing a literal or IRI's text for a term. */
const hasBlankNode = (nquads: string): boolean => {
  let quoted = false, iri = false, escaped = false
  for (let index = 0; index < nquads.length; index += 1) {
    const character = nquads[index]!
    if (quoted) {
      if (escaped) escaped = false
      else if (character === "\\") escaped = true
      else if (character === '"') quoted = false
      continue
    }
    if (iri) { if (character === ">") iri = false; continue }
    if (character === '"') { quoted = true; continue }
    if (character === "<") { iri = true; continue }
    if (character === "_" && nquads[index + 1] === ":") return true
  }
  return false
}

/** Compiles an immutable local graph into JSON-LD 1.1 and an RDF 1.1 N-Quads view. */
export const makeResearchGraphProjection = (graph: ResearchGraph): Effect.Effect<ResearchGraphProjection, ResearchGraphProjectionError> => {
  const valid = parseResearchGraph(graph)
  if (Either.isLeft(valid)) return Effect.fail(new ResearchGraphProjectionError({ code: "INVALID_GRAPH", detail: valid.left.detail }))
  const graphBytes = canonicalJsonBytes(valid.right)
  if (Either.isLeft(graphBytes)) return Effect.fail(new ResearchGraphProjectionError({ code: "INVALID_GRAPH", detail: "research graph cannot be represented in canonical JSON" }))
  const sourceGraphSha256 = hash(graphBytes.right)
  const jsonldDocument = projectionDocument(valid.right, sourceGraphSha256)
  return Effect.tryPromise({
    try: () => {
      const toRdf = jsonld.toRDF as unknown as (input: unknown, options: unknown) => Promise<unknown>
      return toRdf(jsonldDocument, {
        format: "application/n-quads", processingMode: "json-ld-1.1", documentLoader: rejectRemoteDocument
      }).then((produced) => {
        if (typeof produced !== "string" || hasBlankNode(produced)) return Promise.reject(new Error("RDF output is not a blank-node-free N-Quads string"))
        const nquads = `${produced.split("\n").filter((line: string) => line.length > 0).sort((left: string, right: string) => Buffer.compare(Buffer.from(left), Buffer.from(right))).join("\n")}\n`
        const jsonldBytes = canonicalJsonBytes(jsonldDocument)
        if (Either.isLeft(jsonldBytes)) return Promise.reject(new Error("JSON-LD document cannot be represented in canonical JSON"))
        const jsonldSha256 = hash(jsonldBytes.right)
        const manifest = Object.freeze({
          contractVersion: HSWM_RESEARCH_GRAPH_PROJECTION_V1,
          rdfProfile: HSWM_RESEARCH_GRAPH_RDF_PROFILE,
          canonicalGraphSha256: sourceGraphSha256,
          jsonldSha256,
          nquadsSha256: hash(nquads),
          mappingLoss: Object.freeze(["EXTEND_EVENT_HISTORY_OMITTED_FROM_RDF_ACTIVITY_VIEW", "DECLARED_AUTHORITY_AND_DISPOSITIONS_NOT_INDEPENDENTLY_VERIFIED", "NO_CANONICAL_WRITE_BACK"]),
          writeBack: "FORBIDDEN",
          claimCeiling: HSWM_RESEARCH_GRAPH_CLAIM_CEILING,
          source: Object.freeze({ locator: `CALLER_AUTHORED_RESEARCH_GRAPH:${valid.right.manifest.id}`, canonicalGraphSha256: sourceGraphSha256 })
        })
        return Object.freeze({ jsonld: jsonldDocument, nquads, manifest })
      })
    },
    catch: (error) => new ResearchGraphProjectionError({ code: "JSONLD_PROCESSING_FAILED", detail: error instanceof Error ? `pinned JSON-LD processor rejected the bounded local projection: ${error.message}` : "pinned JSON-LD processor rejected the bounded local projection" })
  })
}

/** Exact USL property-graph/v2 input shape. It is another read-only view. */
export const researchGraphPropertyView = (graph: ResearchGraph): JsonObject => {
  const state = researchGraphState(graph)
  const part = (value: string): string => encodeURIComponent(value)
  const nodes: Json[] = [
    ...state.manifest.sources.map((source) => Object.freeze({ uid: `source:${source.id}`, labels: ["Source"], properties: Object.freeze({ title: source.title, declaredLocator: source.locator, authority: source.authority, sha256: source.sha256 }) })),
    ...state.manifest.hypotheses.map((hypothesis) => Object.freeze({ uid: `hypothesis:${hypothesis.id}`, labels: ["Hypothesis"], properties: Object.freeze({ claim: hypothesis.claim, scope: hypothesis.scope, falsifier: hypothesis.falsifier, disposition: "CANDIDATE" }) })),
    ...state.tasks.map((entry) => Object.freeze({ uid: `task:${entry.task.id}`, labels: ["TaskPlan"], properties: Object.freeze({ role: entry.task.role, question: entry.task.question, acceptance: entry.task.acceptance, status: entry.status, budgetTokens: entry.task.budgetTokens, overBudget: entry.overBudget }) })),
    ...graph.events.filter((event): event is Extract<ResearchEvent, { readonly type: "FINISH" }> => event.type === "FINISH").map((event) => Object.freeze({ uid: `result:${event.id}`, labels: ["Result"], properties: Object.freeze({ disposition: event.disposition, summary: event.summary, usedTokens: event.usedTokens }) }))
  ]
  const relationships: Json[] = [
    ...state.manifest.hypotheses.flatMap((hypothesis) => hypothesis.sourceIds.map((sourceId) => Object.freeze({ uid: `hypothesis-source:${part(hypothesis.id)}:${part(sourceId)}`, from_uid: `hypothesis:${hypothesis.id}`, to_uid: `source:${sourceId}`, type: "HAS_DECLARED_SOURCE", properties: Object.freeze({ description: "Declared source reference; no authority grant.", participants: [{ role: "hypothesis", uid: `hypothesis:${hypothesis.id}` }, { role: "source", uid: `source:${sourceId}` }] }) }))),
    ...state.tasks.map((entry) => Object.freeze({ uid: `task-hypothesis:${part(entry.task.id)}:${part(entry.task.hypothesisId)}`, from_uid: `task:${entry.task.id}`, to_uid: `hypothesis:${entry.task.hypothesisId}`, type: "EVALUATES", properties: Object.freeze({ description: "Task plan declares a hypothesis reference.", participants: [{ role: "task", uid: `task:${entry.task.id}` }, { role: "hypothesis", uid: `hypothesis:${entry.task.hypothesisId}` }] }) })),
    ...state.tasks.flatMap((entry) => entry.task.dependsOn.map((dependency) => Object.freeze({ uid: `task-dependency:${part(entry.task.id)}:${part(dependency)}`, from_uid: `task:${entry.task.id}`, to_uid: `task:${dependency}`, type: "DEPENDS_ON", properties: Object.freeze({ description: "Declared task dependency.", participants: [{ role: "dependent", uid: `task:${entry.task.id}` }, { role: "dependency", uid: `task:${dependency}` }] }) }))),
    ...graph.events.filter((event): event is Extract<ResearchEvent, { readonly type: "FINISH" }> => event.type === "FINISH").flatMap((event) => [
      Object.freeze({ uid: `task-result:${part(event.taskId)}:${part(event.id)}`, from_uid: `task:${event.taskId}`, to_uid: `result:${event.id}`, type: "PRODUCED_RESULT", properties: Object.freeze({ description: "Recorded task result.", participants: [{ role: "task", uid: `task:${event.taskId}` }, { role: "result", uid: `result:${event.id}` }] }) }),
      ...event.sourceIds.map((sourceId) => Object.freeze({ uid: `result-source:${part(event.id)}:${part(sourceId)}`, from_uid: `result:${event.id}`, to_uid: `source:${sourceId}`, type: "USES_DECLARED_SOURCE", properties: Object.freeze({ description: "Result self-reports a declared source reference.", participants: [{ role: "result", uid: `result:${event.id}` }, { role: "source", uid: `source:${sourceId}` }] }) })),
      ...(event.disposition === "REFUTED_IN_SCOPE" ? [Object.freeze({ uid: `result-refutes:${part(event.id)}`, from_uid: `result:${event.id}`, to_uid: `hypothesis:${state.manifest.tasks.find((task) => task.id === event.taskId)?.hypothesisId ?? "missing"}`, type: "REFUTES_IN_SCOPE", properties: Object.freeze({ description: "Recorded scoped refutation; it does not prove a general claim.", participants: [{ role: "result", uid: `result:${event.id}` }, { role: "hypothesis", uid: `hypothesis:${state.manifest.tasks.find((task) => task.id === event.taskId)?.hypothesisId ?? "missing"}` }] }) })] : [])
    ])
  ]
  return Object.freeze({ nodes: Object.freeze(nodes), relations: Object.freeze(relationships) })
}
