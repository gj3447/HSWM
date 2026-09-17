import { randomBytes } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { Pool, type PoolConfig } from "pg";
import { Effect, Either } from "effect";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { makeNativeF3PgPersistence, initializeNativeF3PgRun, type NativeF3PgConfig } from "../src/native-f3-pg-persistence.js";
import { nativeF3ChatRequestIdentity, type NativeF3ChatIdentity } from "../src/native-f3-chat-domain.js";

const configPath = process.env["HSWM_F3_PG_TEST_CONFIG"];
const integration = configPath === undefined ? describe.skip : describe;
const source = configPath === undefined ? null : JSON.parse(readFileSync(configPath, "utf8")) as PoolConfig;
const migration = readFileSync(join(process.cwd(), "migrations", "0001_native_f3_pg.sql"), "utf8");
const digest = "a".repeat(64);
const identity = (user: string): NativeF3ChatIdentity => {
  const value = nativeF3ChatRequestIdentity({ endpoint: "https://provider.invalid", model: "f3", system: "system", user, seed: 1, maxTokens: 8 });
  if (Either.isLeft(value)) throw new Error("fixture identity invalid");
  return value.right;
};
const document = (text: string, request: NativeF3ChatIdentity) => Object.freeze({ response_meta: Object.freeze({ text, finish_reason: "stop", response_model: "f3", usage: Object.freeze({ prompt_tokens: 1, completion_tokens: 1 }), request_sha256: request.requestSha256 }) });

type Fixture = { readonly pool: Pool; readonly schema: string; readonly config: NativeF3PgConfig };
let fixture: Fixture | null = null;
const run = <A>(value: Effect.Effect<A, unknown>) => Effect.runPromise(value);
const state = async (clientId: string) => {
  if (fixture === null) throw new Error("fixture absent");
  const runRow = await fixture.pool.query<{ used: string }>(`SELECT used FROM ${fixture.schema}.runs WHERE run_id=$1`, [fixture.config.run.runId]);
  const client = await fixture.pool.query<{ hits: string; misses: string }>(`SELECT hits,misses FROM ${fixture.schema}.client_counters WHERE run_id=$1 AND client_id=$2`, [fixture.config.run.runId, clientId]);
  return { used: runRow.rows[0]?.used, hits: client.rows[0]?.hits ?? "0", misses: client.rows[0]?.misses ?? "0" };
};

integration("native F3 PostgreSQL persistence", () => {
  beforeEach(async () => {
    const schema = `f3t_${randomBytes(10).toString("hex")}`;
    const pool = new Pool(source ?? undefined);
    await pool.query(migration.replaceAll("hswm_f3", schema));
    const config: NativeF3PgConfig = Object.freeze({ pool, schema, run: Object.freeze({ runId: `run-${schema}`, configDigest: digest, maxCalls: 2 }) });
    fixture = { pool, schema, config };
    await run(initializeNativeF3PgRun(config));
  });
  afterEach(async () => {
    if (fixture !== null) {
      const value = fixture;
      fixture = null;
      await value.pool.query(`DROP SCHEMA ${value.schema} CASCADE`);
      await value.pool.end();
    }
  });

  it("atomically permits one concurrent reservation and blocks a duplicate dispatch", async () => {
    if (fixture === null) throw new Error("fixture absent");
    const adapter = makeNativeF3PgPersistence(fixture.config);
    const same = identity("same");
    const [left, right] = await Promise.all([run(adapter.acquire({ clientId: "left", identity: same })), run(adapter.acquire({ clientId: "right", identity: same }))]);
    expect([left.terminal, right.terminal].sort()).toEqual(["MISS_RESERVED", "UNRESOLVED_DISPATCH"]);
    const reserver = left.terminal === "MISS_RESERVED" ? "left" : "right";
    expect(await state(reserver)).toEqual({ used: "1", hits: "0", misses: "1" });
  });

  it("shares a run-wide miss budget across clients while retaining completed cache hits after restart", async () => {
    if (fixture === null) throw new Error("fixture absent");
    const oneCall = fixture.config;
    const first = makeNativeF3PgPersistence(oneCall);
    const reserved = await run(first.acquire({ clientId: "a", identity: identity("cached") }));
    expect(reserved.terminal).toBe("MISS_RESERVED");
    if (reserved.terminal !== "MISS_RESERVED") throw new Error("missing reservation");
    await run(first.complete({ reservation: reserved.reservation, identity: identity("cached"), document: document("answer", identity("cached")) }));
    const restarted = makeNativeF3PgPersistence(oneCall);
    expect((await run(restarted.acquire({ clientId: "b", identity: identity("cached") }))).terminal).toBe("CACHE_HIT");
    expect((await run(restarted.acquire({ clientId: "b", identity: identity("new") }))).terminal).toBe("MISS_RESERVED");
    expect((await run(restarted.acquire({ clientId: "b", identity: identity("budget") }))).terminal).toBe("BUDGET_EXHAUSTED");
    expect(await state("b")).toEqual({ used: "2", hits: "1", misses: "1" });
  });

  it("keeps unknown and known failed reservations non-replayable while each known miss remains consumed", async () => {
    if (fixture === null) throw new Error("fixture absent");
    const adapter = makeNativeF3PgPersistence(fixture.config);
    const known = identity("known");
    const failed = await run(adapter.acquire({ clientId: "a", identity: known }));
    expect(failed.terminal).toBe("MISS_RESERVED");
    if (failed.terminal !== "MISS_RESERVED") throw new Error("missing reservation");
    await run(adapter.failKnown({ reservation: failed.reservation, terminal: "TRANSPORT_ERROR", delivery: "NOT_SENT", detail: "NOT_SENT" }));
    const retried = await run(adapter.acquire({ clientId: "b", identity: known }));
    expect(retried.terminal).toBe("MISS_RESERVED");
    expect(await state("a")).toEqual({ used: "2", hits: "0", misses: "1" });
    expect(await state("b")).toEqual({ used: "2", hits: "0", misses: "1" });
  });

  it("rejects mismatched completion identity or meta while allowing exact replay", async () => {
    if (fixture === null) throw new Error("fixture absent");
    const adapter = makeNativeF3PgPersistence(fixture.config);
    const expected = identity("expected");
    const acquired = await run(adapter.acquire({ clientId: "a", identity: expected }));
    if (acquired.terminal !== "MISS_RESERVED") throw new Error("missing reservation");
    expect(Either.isLeft(await run(adapter.complete({ reservation: acquired.reservation, identity: identity("different"), document: document("one", identity("different")) }).pipe(Effect.either)))).toBe(true);
    expect(Either.isLeft(await run(adapter.complete({ reservation: acquired.reservation, identity: expected, document: document("one", identity("different")) }).pipe(Effect.either)))).toBe(true);
    await run(adapter.complete({ reservation: acquired.reservation, identity: expected, document: document("one", expected) }));
    await run(adapter.complete({ reservation: acquired.reservation, identity: expected, document: document("one", expected) }));
    expect(Either.isLeft(await run(adapter.complete({ reservation: acquired.reservation, identity: expected, document: document("two", expected) }).pipe(Effect.either)))).toBe(true);
  });

  it("discards a client after a failed transaction instead of returning it clean to the pool", async () => {
    const released: unknown[] = [];
    const fakePool = Object.freeze({ connect: async () => Object.freeze({
      query: async (sql: string) => {
        if (sql === "BEGIN" || sql === "ROLLBACK") return { rows: [] };
        throw new Error("forced query failure");
      },
      release: (error?: Error) => { released.push(error); }
    }) }) as unknown as NativeF3PgConfig["pool"];
    const config: NativeF3PgConfig = Object.freeze({ pool: fakePool, schema: "f3test", run: Object.freeze({ runId: "failed-cleanup", configDigest: digest, maxCalls: 1 }) });
    const result = await run(makeNativeF3PgPersistence(config).acquire({ clientId: "a", identity: identity("failure") }).pipe(Effect.either));
    expect(Either.isLeft(result)).toBe(true);
    expect(released).toHaveLength(1);
    expect(released[0]).toBeInstanceOf(Error);
  });

  it("returns CACHE_CORRUPT without consuming a hit or another miss", async () => {
    if (fixture === null) throw new Error("fixture absent");
    const adapter = makeNativeF3PgPersistence(fixture.config);
    const corrupt = identity("corrupt");
    const acquired = await run(adapter.acquire({ clientId: "a", identity: corrupt }));
    if (acquired.terminal !== "MISS_RESERVED") throw new Error("missing reservation");
    await fixture.pool.query(`UPDATE ${fixture.schema}.cache_entries SET status='COMPLETED', document='{}'::jsonb WHERE run_id=$1 AND reservation_id=$2`, [fixture.config.run.runId, acquired.reservation.reservationId]);
    expect((await run(adapter.acquire({ clientId: "b", identity: corrupt }))).terminal).toBe("CACHE_CORRUPT");
    await fixture.pool.query(`UPDATE ${fixture.schema}.cache_entries SET document=$3::jsonb WHERE run_id=$1 AND reservation_id=$2`, [fixture.config.run.runId, acquired.reservation.reservationId, JSON.stringify(document("otherwise valid but wrong request", identity("wrong")))]);
    expect((await run(adapter.acquire({ clientId: "b", identity: corrupt }))).terminal).toBe("CACHE_CORRUPT");
    expect(await state("a")).toEqual({ used: "1", hits: "0", misses: "1" });
    expect(await state("b")).toEqual({ used: "1", hits: "0", misses: "0" });
  });

  it("refuses configuration drift for acquisition and both settlement operations", async () => {
    if (fixture === null) throw new Error("fixture absent");
    const request = identity("config drift");
    const adapter = makeNativeF3PgPersistence(fixture.config);
    const reserved = await run(adapter.acquire({ clientId: "a", identity: request }));
    if (reserved.terminal !== "MISS_RESERVED") throw new Error("missing reservation");
    await expect(run(adapter.failKnown({ reservation: reserved.reservation, terminal: "TRANSPORT_ERROR", delivery: "RESPONSE_RECEIVED", detail: "insufficient evidence" }))).rejects.toThrow();
    const changed = { ...fixture.config, run: { ...fixture.config.run, configDigest: "c".repeat(64) } };
    const wrong = makeNativeF3PgPersistence(changed);
    for (const operation of [initializeNativeF3PgRun(changed), wrong.acquire({ clientId: "a", identity: request }), wrong.complete({ reservation: reserved.reservation, identity: request, document: document("ok", request) }), wrong.failKnown({ reservation: reserved.reservation, terminal: "TRANSPORT_ERROR", delivery: "NOT_SENT", detail: "NOT_SENT" })]) {
      await expect(run(operation)).rejects.toThrow();
    }
    expect((await run(adapter.acquire({ clientId: "a", identity: request }))).terminal).toBe("UNRESOLVED_DISPATCH");
    expect(await state("a")).toEqual({ used: "1", hits: "0", misses: "1" });
  });

  it("rejects oversized cache documents and counter overflow before any persisted mutation", async () => {
    if (fixture === null) throw new Error("fixture absent");
    const request = identity("bounded");
    const adapter = makeNativeF3PgPersistence(fixture.config);
    const reserved = await run(adapter.acquire({ clientId: "a", identity: request }));
    if (reserved.terminal !== "MISS_RESERVED") throw new Error("missing reservation");
    await expect(run(adapter.complete({ reservation: reserved.reservation, identity: request, document: document("x".repeat(1_048_576), request) }))).rejects.toThrow();
    expect((await run(adapter.acquire({ clientId: "a", identity: request }))).terminal).toBe("UNRESOLVED_DISPATCH");
    await run(adapter.complete({ reservation: reserved.reservation, identity: request, document: document("ok", request) }));
    await fixture.pool.query(`UPDATE ${fixture.schema}.client_counters SET hits=$3,misses=$3 WHERE run_id=$1 AND client_id=$2`, [fixture.config.run.runId, "a", Number.MAX_SAFE_INTEGER]);
    await expect(run(adapter.acquire({ clientId: "a", identity: request }))).rejects.toThrow();
    await expect(run(adapter.acquire({ clientId: "a", identity: identity("new bounded") }))).rejects.toThrow();
    expect(await state("a")).toEqual({ used: "1", hits: String(Number.MAX_SAFE_INTEGER), misses: String(Number.MAX_SAFE_INTEGER) });
  });
});
