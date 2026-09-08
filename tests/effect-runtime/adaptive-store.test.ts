import { expect, it } from "vitest"
import { createHash } from "node:crypto"
import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { DatabaseSync } from "node:sqlite"
import { Effect } from "effect"

import {
  AdaptiveStore,
  makeAdaptiveStoreSqliteLayer,
  type AdaptiveAtom
} from "../../src/hswm/effect-runtime/src/adaptive-store.js"

const cue: AdaptiveAtom = { uid: "cue", kind: "observation", owner: "sense", refs: [], payload: { value: "old" } }
const policy: AdaptiveAtom = { uid: "policy", kind: "relation", owner: "learn", refs: [{ role: "condition", uid: "cue" }], payload: { action: "wait" } }

const run = <A>(program: Effect.Effect<A, unknown, AdaptiveStore>) =>
  Effect.runPromise(Effect.scoped(program.pipe(Effect.provide(makeAdaptiveStoreSqliteLayer(":memory:")))))

const runAt = <A>(path: string, program: Effect.Effect<A, unknown, AdaptiveStore>) =>
  Effect.runPromise(Effect.scoped(program.pipe(Effect.provide(makeAdaptiveStoreSqliteLayer(path)))))

const temporaryDatabase = () => {
  const directory = mkdtempSync(join(tmpdir(), "hswm-adaptive-store-"))
  const path = join(directory, "store.sqlite")
  return { path, remove: () => rmSync(directory, { recursive: true, force: true }) }
}

it("preserves immutable revisions and makes a rewrite idempotent", async () => {
  const result = await run(Effect.gen(function* () {
    const store = yield* AdaptiveStore
    yield* store.initialize("g", "manifest-1", [cue, policy])
    const first = yield* store.rewrite({
      graphId: "g", eventId: "event-1", expected: { policy: 1, trace: 0 }, source: { episode: "e1" },
      atoms: [
        { ...policy, refs: [...policy.refs, { role: "evidence", uid: "trace" }], payload: { action: "act" } },
        { uid: "trace", kind: "trajectory", owner: "act", refs: [{ role: "policy", uid: "policy" }], payload: { status: "RUNNING" } }
      ]
    })
    const retry = yield* store.rewrite({
      graphId: "g", eventId: "event-1", expected: { policy: 1, trace: 0 }, source: { episode: "e1" },
      atoms: [
        { ...policy, refs: [...policy.refs, { role: "evidence", uid: "trace" }], payload: { action: "act" } },
        { uid: "trace", kind: "trajectory", owner: "act", refs: [{ role: "policy", uid: "policy" }], payload: { status: "RUNNING" } }
      ]
    })
    return { first, retry, before: yield* store.getRevision("g", "policy", 1), after: yield* store.getRevision("g", "policy", 2) }
  }))
  expect(result.first.produced).toEqual(result.retry.produced)
  expect(result.before.payload).toEqual({ action: "wait" })
  expect(result.after.refs[1]).toEqual({ role: "evidence", uid: "trace" })
})

it("rejects a stale CAS without changing the head", async () => {
  const result = await run(Effect.gen(function* () {
    const store = yield* AdaptiveStore
    yield* store.initialize("g", "manifest-1", [cue, policy])
    const attempted = yield* Effect.exit(store.rewrite({ graphId: "g", eventId: "stale", expected: { policy: 0 }, source: {}, atoms: [policy] }))
    return { attempted, head: yield* store.head("g", "policy") }
  }))
  expect(result.attempted._tag).toBe("Failure")
  expect(result.head.revision).toBe(1)
})

it("uses a short lease to prevent concurrent local runtimes", async () => {
  const result = await run(Effect.gen(function* () {
    const store = yield* AdaptiveStore
    yield* store.initialize("g", "manifest-1", [cue])
    const token = yield* store.acquireRuntimeLock("g")
    const duplicate = yield* Effect.exit(store.acquireRuntimeLock("g"))
    yield* store.releaseRuntimeLock("g", token)
    const next = yield* store.acquireRuntimeLock("g")
    yield* store.releaseRuntimeLock("g", next)
    return duplicate
  }))
  expect(result._tag).toBe("Failure")
})

it("excludes a second SQLite connection until the first connection releases its token", async () => {
  const fixture = temporaryDatabase()
  try {
    await runAt(fixture.path, Effect.gen(function* () {
      const store = yield* AdaptiveStore
      yield* store.initialize("g", "manifest-1", [cue])
    }))
    const token = await runAt(fixture.path, Effect.gen(function* () {
      const store = yield* AdaptiveStore
      return yield* store.acquireRuntimeLock("g")
    }))
    const blocked = await runAt(fixture.path, Effect.gen(function* () {
      const store = yield* AdaptiveStore
      return yield* Effect.exit(store.acquireRuntimeLock("g"))
    }))
    expect(blocked._tag).toBe("Failure")
    await runAt(fixture.path, Effect.gen(function* () {
      const store = yield* AdaptiveStore
      yield* store.releaseRuntimeLock("g", token)
    }))
    const next = await runAt(fixture.path, Effect.gen(function* () {
      const store = yield* AdaptiveStore
      return yield* store.acquireRuntimeLock("g")
    }))
    expect(next).not.toBe(token)
  } finally { fixture.remove() }
})

it("reclaims a dead-PID lease", async () => {
  const fixture = temporaryDatabase()
  try {
    await runAt(fixture.path, Effect.gen(function* () {
      const store = yield* AdaptiveStore
      yield* store.initialize("g", "manifest-1", [cue])
    }))
    const database = new DatabaseSync(fixture.path)
    database.prepare("INSERT INTO adaptive_runtime_locks(graph_id,token,pid) VALUES(?,?,?)").run("g", "dead-token", 999_999_999)
    database.close()
    const token = await runAt(fixture.path, Effect.gen(function* () {
      const store = yield* AdaptiveStore
      return yield* store.acquireRuntimeLock("g")
    }))
    expect(token).not.toBe("dead-token")
  } finally { fixture.remove() }
})

it("rolls back a partially started initialization when SQLite rejects an atom write", async () => {
  const fixture = temporaryDatabase()
  try {
    await runAt(fixture.path, Effect.gen(function* () {
      const store = yield* AdaptiveStore
      yield* store.initialize("seed", "manifest-seed", [cue])
    }))
    const database = new DatabaseSync(fixture.path)
    database.exec("CREATE TRIGGER reject_atom BEFORE INSERT ON adaptive_atoms WHEN NEW.graph_id='rolled-back' BEGIN SELECT RAISE(ABORT, 'fixture rejection'); END")
    database.close()
    const rejected = await runAt(fixture.path, Effect.gen(function* () {
      const store = yield* AdaptiveStore
      return yield* Effect.exit(store.initialize("rolled-back", "manifest-1", [cue]))
    }))
    expect(rejected._tag).toBe("Failure")
    const inspect = new DatabaseSync(fixture.path)
    expect(inspect.prepare("SELECT graph_id FROM adaptive_graphs WHERE graph_id=?").get("rolled-back")).toBeUndefined()
    inspect.exec("DROP TRIGGER reject_atom")
    inspect.close()
    const heads = await runAt(fixture.path, Effect.gen(function* () {
      const store = yield* AdaptiveStore
      return yield* store.initialize("rolled-back", "manifest-1", [cue])
    }))
    expect(heads).toHaveLength(1)
  } finally { fixture.remove() }
})

it("verifies historic Python JSON bytes without rewriting a float digest", async () => {
  const fixture = temporaryDatabase()
  try {
    await runAt(fixture.path, Effect.gen(function* () {
      const store = yield* AdaptiveStore
      yield* store.initialize("g", "manifest-1", [cue])
    }))
    const refs = "[]"
    const payload = "{\"value\":1.0}"
    const raw = `{"kind":"legacy","owner":"owner","payload":${payload},"refs":${refs},"uid":"legacy"}`
    const digest = createHash("sha256").update(raw, "utf8").digest("hex")
    const database = new DatabaseSync(fixture.path)
    database.prepare("INSERT INTO adaptive_atoms VALUES(?,?,?,?,?,?,?,?,?)").run("g", "legacy", 1, "legacy", "owner", Buffer.from(refs), Buffer.from(payload), digest, null)
    database.prepare("INSERT INTO adaptive_heads VALUES(?,?,?,?,?,?)").run("g", "legacy", 1, "legacy", "owner", digest)
    database.close()
    const revision = await runAt(fixture.path, Effect.gen(function* () {
      const store = yield* AdaptiveStore
      return yield* store.getRevision("g", "legacy", 1)
    }))
    expect(revision.digest).toBe(digest)
    expect(revision.payload).toEqual({ value: 1 })
    expect(createHash("sha256").update(raw.replace("1.0", "1"), "utf8").digest("hex")).not.toBe(digest)
  } finally { fixture.remove() }
})

it("defers SQLite work until an Effect runs and reevaluates reusable effects", async () => {
  const fixture = temporaryDatabase()
  try {
    const result = await runAt(fixture.path, Effect.gen(function* () {
      const store = yield* AdaptiveStore
      yield* store.initialize("g", "manifest-1", [cue])
      const acquire = store.acquireRuntimeLock("g")
      const before = new DatabaseSync(fixture.path).prepare("SELECT COUNT(*) AS count FROM adaptive_runtime_locks").get() as { count: number }
      const first = yield* acquire
      yield* store.releaseRuntimeLock("g", first)
      const second = yield* acquire
      yield* store.releaseRuntimeLock("g", second)
      return { before: before.count, first, second }
    }))
    expect(result.before).toBe(0)
    expect(result.first).not.toBe(result.second)
  } finally { fixture.remove() }
})
