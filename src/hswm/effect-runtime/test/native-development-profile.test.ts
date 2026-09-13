import { createHash } from "node:crypto"
import { readFileSync } from "node:fs"
import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { resolve } from "node:path"
import { join } from "node:path"
import { DatabaseSync } from "node:sqlite"
import { Effect } from "effect"
import { expect, it } from "vitest"
import { makeAdaptiveRuntime } from "../src/adaptive-runtime.js"
import { AdaptiveStore, makeAdaptiveStoreSqliteLayer } from "../src/adaptive-store.js"

const root = resolve(import.meta.dirname, "../../../..")
const profile = (name: string): Readonly<Record<string, unknown>> => JSON.parse(readFileSync(resolve(root, "_research/causal_composition/examples", name), "utf8")) as Readonly<Record<string, unknown>>
const command = (program: Readonly<Record<string, unknown>>, cellId: string): readonly string[] => {
  const cells = program["cells"]
  if (!Array.isArray(cells)) throw new Error("development profile cells are missing")
  const cell = cells.find(value => typeof value === "object" && value !== null && !Array.isArray(value) && value["cell_id"] === cellId)
  if (typeof cell !== "object" || cell === null || Array.isArray(cell) || !Array.isArray(cell["argv"]) || !cell["argv"].every(value => typeof value === "string")) throw new Error(`development profile command is missing: ${cellId}`)
  return cell["argv"]
}
const isRecord = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value)
const durable = <Value>(path: string, work: Effect.Effect<Value, unknown, AdaptiveStore>) => Effect.runPromise(Effect.scoped(work.pipe(Effect.provide(makeAdaptiveStoreSqliteLayer(path)))))

it("keeps v3 learning state and routing contracts while replacing only the three Python verification argv routes", () => {
  const v3 = profile("adaptive_hswm_development.v3.json"), v4 = profile("adaptive_hswm_development.v4.json")
  expect(v4["graph_id"]).toBe(v3["graph_id"])
  expect(v4["graph_id"]).toBe("hswm-self-development-feedback-v3")
  expect(v4["relations"]).toEqual(v3["relations"])
  expect(v4["context_domain"]).toEqual(v3["context_domain"])
  expect(command(v4, "runtime")).toEqual(command(v3, "runtime"))
  expect(command(v4, "effect-check")).toEqual(command(v3, "effect-check"))
  expect(command(v4, "usl")).toEqual(["npm", "--prefix", "src/hswm/effect-runtime", "run", "test:usl"])
  expect(command(v4, "ontology")).toEqual(["npm", "--prefix", "src/hswm/effect-runtime", "run", "test:ontology"])
  expect(command(v4, "docs")).toEqual(["npm", "--prefix", "src/hswm/effect-runtime", "run", "test:docs"])
  expect(JSON.stringify(v4)).not.toContain("hswm-python")
  expect(createHash("sha256").update(readFileSync(resolve(root, "_research/causal_composition/examples/adaptive_hswm_development.v3.json"))).digest("hex")).toBe("ea0e78ac43be8a1bdaa12aafd745beb17e4d506102c7d0b73e6e7799ad910667")
})

it("migrates only the pinned v3 HSWM profile to v4 without losing learned relation revisions or event history", async () => {
  const directory = mkdtempSync(join(tmpdir(), "hswm-native-profile-v4-")), state = join(directory, "profile.sqlite")
  const v3 = profile("adaptive_hswm_development.v3.json"), v4 = profile("adaptive_hswm_development.v4.json")
  const malformedV3 = structuredClone(v3) as { cells: Array<{ cell_id: string; argv?: string[] }> }
  const v3Docs = malformedV3.cells.find(cell => cell.cell_id === "docs")
  if (v3Docs === undefined || v3Docs.argv === undefined) throw new Error("v3 docs command is missing")
  v3Docs.argv = ["npm", "run", "unapproved"]
  const malformed = structuredClone(v4) as { cells: Array<{ cell_id: string; argv?: string[] }> }
  const docs = malformed.cells.find(cell => cell.cell_id === "docs")
  if (docs === undefined || docs.argv === undefined) throw new Error("v4 docs command is missing")
  docs.argv = ["npm", "run", "unapproved"]
  try {
    const outcome = await durable(state, Effect.gen(function* () {
      const v3Runtime = yield* makeAdaptiveRuntime(v3, root)
      const store = yield* AdaptiveStore
      const relation = yield* store.getRevision("hswm-self-development-feedback-v3", "relation:ontology-focused", 1)
      if (!isRecord(relation.payload) || !isRecord(relation.payload["model"])) throw new Error("initial relation model is missing")
      const learned = { ...relation.payload, model: { ...relation.payload["model"], n: 1 } }
      yield* store.rewrite({ graphId: "hswm-self-development-feedback-v3", eventId: "profile-test-observation", expected: { [relation.uid]: relation.revision }, atoms: [{ uid: relation.uid, kind: relation.kind, owner: relation.owner, refs: relation.refs, payload: learned }], source: { kind: "TEST_OBSERVATION" } })
      const before = yield* v3Runtime.graph()
      const rejectedV3 = yield* Effect.exit(makeAdaptiveRuntime(malformedV3, root))
      const rejected = yield* Effect.exit(makeAdaptiveRuntime(malformed, root))
      const v4Runtime = yield* makeAdaptiveRuntime(v4, root)
      const after = yield* v4Runtime.graph()
      const afterRestart = yield* (yield* makeAdaptiveRuntime(v4, root)).graph()
      const migration = yield* store.getEvent("hswm-self-development-feedback-v3", "native-profile-migration:hswm-development-v3-to-v4")
      return { after, afterRestart, before, migration, rejected, rejectedV3 }
    }))
    expect(outcome.rejectedV3._tag).toBe("Failure")
    expect(outcome.rejected._tag).toBe("Failure")
    const beforeRelation = (outcome.before["atoms"] as Array<{ uid: string; revision: number; payload: { model?: { n?: number } } }>).find(atom => atom.uid === "relation:ontology-focused")
    const afterRelation = (outcome.after["atoms"] as Array<{ uid: string; revision: number; payload: { model?: { n?: number } } }>).find(atom => atom.uid === "relation:ontology-focused")
    expect(afterRelation).toMatchObject({ revision: beforeRelation?.revision, payload: { model: { n: 1 } } })
    const heads = (value: Record<string, unknown>) => new Map((value["atoms"] as Array<{ uid: string; revision: number; kind: string; owner: string; digest: string }>).map(atom => [atom.uid, { revision: atom.revision, kind: atom.kind, owner: atom.owner, digest: atom.digest }]))
    const beforeHeads = heads(outcome.before), afterHeads = heads(outcome.after)
    for (const [uid, head] of beforeHeads) if (!new Set(["cell:usl", "cell:ontology", "cell:docs"]).has(uid)) expect(afterHeads.get(uid), uid).toEqual(head)
    expect(heads(outcome.afterRestart)).toEqual(afterHeads)
    expect(outcome.migration.source).toMatchObject({ kind: "HSWM_NATIVE_DEVELOPMENT_PROFILE_V3_TO_V4", from_manifest_digest: "cea027bec4234503202f00ab8cbee2ba1fdbd88374e7a6f07bf0428fcc602841", to_manifest_digest: "84d7c0eb6a686ca8a02534835cab924efee384b9646d9b9c34e14c7fa2c58b66" })
    expect(outcome.migration.produced.map(head => head.uid).sort()).toEqual(["cell:docs", "cell:ontology", "cell:usl"])
  } finally {
    rmSync(directory, { recursive: true, force: true })
  }
})

it("refuses v4 migration while the v3 runtime lease is live without changing heads, then migrates after release", async () => {
  const directory = mkdtempSync(join(tmpdir(), "hswm-native-profile-lease-")), state = join(directory, "profile.sqlite")
  const v3 = profile("adaptive_hswm_development.v3.json"), v4 = profile("adaptive_hswm_development.v4.json"), graphId = "hswm-self-development-feedback-v3"
  try {
    const outcome = await durable(state, Effect.gen(function* () {
      yield* makeAdaptiveRuntime(v3, root)
      const store = yield* AdaptiveStore
      const before = yield* store.heads(graphId)
      const token = yield* store.acquireRuntimeLock(graphId)
      const blocked = yield* Effect.exit(makeAdaptiveRuntime(v4, root))
      const afterBlocked = yield* store.heads(graphId)
      yield* store.releaseRuntimeLock(graphId, token)
      const migrated = yield* makeAdaptiveRuntime(v4, root)
      const afterMigration = yield* store.heads(graphId)
      return { before, blocked, afterBlocked, afterMigration, migrated }
    }))
    expect(outcome.blocked._tag).toBe("Failure")
    expect(outcome.before).toEqual(outcome.afterBlocked)
    expect(outcome.afterMigration.filter(head => ["cell:usl", "cell:ontology", "cell:docs"].includes(head.uid)).every(head => head.revision === 2)).toBe(true)
    expect(outcome.migrated).toBeDefined()
  } finally {
    rmSync(directory, { recursive: true, force: true })
  }
})

it("rolls back every v4 replacement when SQLite rejects a migration row", async () => {
  const directory = mkdtempSync(join(tmpdir(), "hswm-native-profile-rollback-")), state = join(directory, "profile.sqlite")
  const v3 = profile("adaptive_hswm_development.v3.json"), v4 = profile("adaptive_hswm_development.v4.json"), graphId = "hswm-self-development-feedback-v3"
  const database = () => new DatabaseSync(state)
  const readHeads = () => { const raw = database(); try { return raw.prepare("SELECT uid, revision, kind, owner, atom_digest FROM adaptive_heads WHERE graph_id=? ORDER BY uid").all(graphId) } finally { raw.close() } }
  try {
    await durable(state, makeAdaptiveRuntime(v3, root))
    const before = readHeads()
    const raw = database()
    raw.exec("CREATE TRIGGER reject_native_profile_migration BEFORE INSERT ON adaptive_atoms WHEN NEW.uid='cell:ontology' AND NEW.event_id='native-profile-migration:hswm-development-v3-to-v4' BEGIN SELECT RAISE(ABORT, 'injected migration failure'); END")
    raw.close()
    const failed = await durable(state, Effect.exit(makeAdaptiveRuntime(v4, root)))
    expect(failed._tag).toBe("Failure")
    expect(readHeads()).toEqual(before)
    const cleanup = database()
    cleanup.exec("DROP TRIGGER reject_native_profile_migration")
    cleanup.close()
    const migrated = await durable(state, makeAdaptiveRuntime(v4, root))
    expect(migrated).toBeDefined()
  } finally {
    rmSync(directory, { recursive: true, force: true })
  }
})
