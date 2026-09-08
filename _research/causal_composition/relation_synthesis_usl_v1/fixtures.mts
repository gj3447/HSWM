/** Authored owner-side catalog fixture. This is not a USL database or real KG. */
import { createHash } from "node:crypto"
import type { RelationGraph } from "../../../src/hswm/effect-runtime/src/relation-program-research.js"

export interface CatalogTask {
  readonly id: string
  readonly focus: string
  readonly raw: string
  readonly graph: RelationGraph
  readonly expected: ReadonlyArray<string>
  readonly resourceHashes: Readonly<Record<string, string>>
}

const hash = (text: string): string => createHash("sha256").update(text).digest("hex")
const uid = (seed: number, name: string): string => `fixture:${hash(`${seed}:${name}`).slice(0, 20)}`
const ordered = <T,>(items: ReadonlyArray<T>, seed: number): ReadonlyArray<T> =>
  [...items].sort((a, b) => hash(`${seed}:${JSON.stringify(a)}`).localeCompare(hash(`${seed}:${JSON.stringify(b)}`)))

export const catalogTask = (seed: number, affectedCount: number, arity: number): CatalogTask => {
  const focus = uid(seed, "change"), unrelated = uid(seed, "unrelated_change"), scope = uid(seed, "scope")
  const artifacts = Array.from({ length: affectedCount + 2 }, (_, i) => uid(seed, `artifact_${i}`))
  const requirements = artifacts.flatMap((artifact, index) =>
    Array.from({ length: 1 + ((seed + index) % 2) }, (_, j) => ({ artifact, requirement: uid(seed, `req_${index}_${j}`) })))
  const checks = requirements.flatMap(({ requirement }, index) =>
    Array.from({ length: 1 + ((seed + index) % 2) }, (_, j) => ({ requirement, check: uid(seed, `check_${index}_${j}`) })))
  const changes = artifacts.map((artifact, index) => ({ change: index < affectedCount ? focus : unrelated, artifact }))
  const entities = [...new Set([focus, unrelated, scope, ...artifacts, ...requirements.map(r => r.requirement), ...checks.map(c => c.check)])]
  const locator = (nativeUid: string) => `https://hswm-fixture.invalid/${nativeUid}`
  const resourceHashes = Object.fromEntries(entities.map(id => [locator(id), hash(`owner-fixture-observation:${id}`)]))
  const relation = (index: number, type: string, from: string, to: string, fromRole: string, toRole: string) => ({
    uid: uid(seed, `relation_${type}_${index}`), from_uid: from, to_uid: to, type,
    properties: { participants: ordered([
      { role: fromRole, uid: from }, { role: toRole, uid: to },
      ...(arity === 3 ? [{ role: "context", uid: scope }] : [])
    ], seed + index) }
  })
  const relations = ordered([
    ...changes.map((r, i) => relation(i, "INVALIDATES", r.change, r.artifact, "change", "artifact")),
    ...requirements.map((r, i) => relation(i, "REQUIRES", r.artifact, r.requirement, "artifact", "requirement")),
    ...checks.map((r, i) => relation(i, "CHECKS", r.check, r.requirement, "check", "requirement"))
  ], seed)
  // Independent code path from the DSL evaluator, but NOT an independent custodian.
  const affected = new Set(changes.filter(r => r.change === focus).map(r => r.artifact))
  const required = new Set(requirements.filter(r => affected.has(r.artifact)).map(r => r.requirement))
  const expected = [...new Set(checks.filter(r => required.has(r.requirement)).map(r => r.check))].sort()
  const raw = JSON.stringify({ nodes: ordered(entities.map(id => ({ uid: id, properties: { locator: locator(id) } })), seed), relations })
  const graph = { relations: relations.map(r => ({ uid: r.uid, meaning: `Declared KG relation: ${r.type}`, participants: r.properties.participants })) }
  return Object.freeze({ id: `catalog-${seed}`, focus, raw, graph, expected: Object.freeze(expected), resourceHashes })
}

/** Changes only the first declared relation meaning, keeping resources fixed. */
export const changedOwnerVersion = (task: CatalogTask): string => {
  const graph = JSON.parse(task.raw)
  graph.relations[0].type = `${graph.relations[0].type}_CHANGED`
  return JSON.stringify(graph)
}
