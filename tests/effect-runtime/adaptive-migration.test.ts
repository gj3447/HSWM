import { readFileSync, mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { DatabaseSync } from "node:sqlite"
import { expect, it } from "vitest"
import { Effect, Layer } from "effect"

import { makeAdaptiveRuntime } from "../../src/hswm/effect-runtime/src/adaptive-runtime.js"
import { makeAdaptiveStoreSqliteLayer } from "../../src/hswm/effect-runtime/src/adaptive-store.js"
import { NodeBoundedSubprocessLive } from "../../src/hswm/effect-runtime/src/effect-bounded-subprocess.js"

const fixture = JSON.parse(readFileSync(join(process.cwd(), "../../../tests/fixtures/adaptive-native/python-sqlite-history.v1.json"), "utf8")) as {
  readonly program: Record<string, unknown>
  readonly oracle: { readonly episode_id: string; readonly task: string; readonly context: Record<string, string | boolean>; readonly force_route: string }
  readonly tables: Record<string, { readonly columns: ReadonlyArray<string>; readonly rows: ReadonlyArray<ReadonlyArray<unknown>> }>
}
const schema = `CREATE TABLE adaptive_graphs (graph_id TEXT PRIMARY KEY, manifest_digest TEXT NOT NULL);
CREATE TABLE adaptive_atoms (graph_id TEXT NOT NULL, uid TEXT NOT NULL, revision INTEGER NOT NULL, kind TEXT NOT NULL, owner TEXT NOT NULL, refs_json BLOB NOT NULL, payload_json BLOB NOT NULL, atom_digest TEXT NOT NULL, event_id TEXT, PRIMARY KEY (graph_id, uid, revision));
CREATE TABLE adaptive_heads (graph_id TEXT NOT NULL, uid TEXT NOT NULL, revision INTEGER NOT NULL, kind TEXT NOT NULL, owner TEXT NOT NULL, atom_digest TEXT NOT NULL, PRIMARY KEY (graph_id, uid));
CREATE TABLE adaptive_events (graph_id TEXT NOT NULL, event_id TEXT NOT NULL, intent_digest TEXT NOT NULL, source_json BLOB NOT NULL, consumed_json BLOB NOT NULL, produced_json BLOB NOT NULL, PRIMARY KEY (graph_id, event_id));`
const seedPythonHistory = (path: string) => {
  const database = new DatabaseSync(path)
  database.exec(schema)
  for (const [table, data] of Object.entries(fixture.tables)) {
    const statement = database.prepare(`INSERT INTO ${table}(${data.columns.join(",")}) VALUES(${data.columns.map(() => "?").join(",")})`)
    for (const source of data.rows) statement.run(...source.map((value) => typeof value === "object" && value !== null && "base64" in value ? Buffer.from(String((value as { base64: string }).base64), "base64") : value) as [])
  }
  database.close()
}
const durable = <A, R>(path: string, effect: Effect.Effect<A, unknown, R>) =>
  Effect.runPromise(Effect.scoped(effect.pipe(Effect.provide(Layer.mergeAll(makeAdaptiveStoreSqliteLayer(path), NodeBoundedSubprocessLive))) as Effect.Effect<A, unknown, never>))

it("resumes the fixed Python-oracle stock/boolean history without a Python runtime", async () => {
  const directory = mkdtempSync(join(tmpdir(), "hswm-native-migration-"))
  const state = join(directory, "history.sqlite")
  try {
    const legacy = fixture.oracle
    seedPythonHistory(state)
    const raw = new DatabaseSync(state)
    const historic = raw.prepare("SELECT payload_json,atom_digest FROM adaptive_atoms WHERE uid=? AND revision=2").get("relation:stock-open") as { payload_json: Uint8Array; atom_digest: string }
    const rawPayload = Buffer.from(historic.payload_json)
    const rawDigest = historic.atom_digest
    raw.close()
    const resumed = await durable(state, Effect.gen(function* () {
      const runtime = yield* makeAdaptiveRuntime(fixture.program, "/tmp")
      const before = yield* runtime.graph()
      const replay = yield* runtime.run(legacy.task, legacy.context, { episodeId: legacy.episode_id, budget: 60, maxCalls: 16, forceRoute: legacy.force_route, exploration: 0, learn: true })
      const after = yield* runtime.graph()
      const plan = yield* runtime.plan(legacy.context, { exploration: 0 })
      const learned = yield* runtime.run("native continuation", legacy.context, { episodeId: "native-after-migration", forceRoute: legacy.force_route, exploration: 0 })
      const continued = yield* runtime.graph()
      return { before, replay, after, plan, learned, continued }
    }))
    expect(resumed.replay["replayed"]).toBe(true)
    expect((resumed.after["events"] as ReadonlyArray<unknown>).length).toBe((resumed.before["events"] as ReadonlyArray<unknown>).length)
    expect(resumed.plan.selected?.uid).toBe("relation:stock-open")
    expect(resumed.learned["status"]).toBe("SUCCEEDED")
    const route = (resumed.continued["atoms"] as ReadonlyArray<{ readonly uid: string; readonly payload: { readonly model: { readonly n: number } } }>).find((atom) => atom.uid === "relation:stock-open")
    expect(route?.payload.model.n).toBe(2)
    const verification = new DatabaseSync(state)
    const verified = verification.prepare("SELECT payload_json,atom_digest FROM adaptive_atoms WHERE uid=? AND revision=2").get("relation:stock-open") as { payload_json: Uint8Array; atom_digest: string }
    expect(Buffer.from(verified.payload_json)).toEqual(rawPayload)
    expect(verified.atom_digest).toBe(rawDigest)
    verification.close()
  } finally { rmSync(directory, { recursive: true, force: true }) }
})
