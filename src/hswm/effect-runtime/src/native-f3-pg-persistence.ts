import { randomUUID } from "node:crypto";
import type { Pool, PoolClient, QueryResult, QueryResultRow } from "pg";
import { Data, Effect, Either, Exit, Layer } from "effect";
import {
  NativeF3CachePersistence,
  NativeF3CachePersistenceError,
  type NativeF3CachePersistenceShape,
  type NativeF3CacheReservation
} from "./native-f3-cache-runtime.js";
import {
  nativeF3DecodeCachedMeta,
  nativeF3DecodeChatState,
  nativeF3ChatCacheTransition,
  type NativeF3ChatState,
  type NativeF3ChatIdentity,
  type NativeF3OpenAiMeta
} from "./native-f3-chat-domain.js";

export class NativeF3PgError extends Data.TaggedError("NativeF3PgError")<{
  readonly operation: "INIT_RUN" | "ACQUIRE" | "COMPLETE" | "FAIL_KNOWN";
  readonly detail: string;
}> {}

export type NativeF3PgRun = Readonly<{ readonly runId: string; readonly configDigest: string; readonly maxCalls: number }>;
export type NativeF3PgConfig = Readonly<{ readonly pool: Pick<Pool, "connect">; readonly schema: string; readonly run: NativeF3PgRun }>;
type Client = Pick<PoolClient, "query" | "release">;
type RunRow = QueryResultRow & Readonly<{ config_digest: string; max_calls: string; used: string }>;
type ClientRow = QueryResultRow & Readonly<{ hits: string; misses: string }>;
type EntryRow = QueryResultRow & Readonly<{ request_sha256: string; status: "RESERVED" | "COMPLETED" | "FAILED_KNOWN"; reservation_id: string; document: unknown }>;
type BooleanRow = QueryResultRow & Readonly<{ same: boolean }>;
type IdRow = QueryResultRow & Readonly<{ run_id: string }>;
const failure = (operation: NativeF3PgError["operation"], detail: string) => new NativeF3PgError({ operation, detail });
const lift = <A>(value: Either.Either<A, NativeF3PgError>): Effect.Effect<A, NativeF3PgError> => Either.isLeft(value) ? Effect.fail(value.left) : Effect.succeed(value.right);
const validSchema = (value: string): Either.Either<string, NativeF3PgError> => /^[a-z_][a-z0-9_]{0,62}$/u.test(value) ? Either.right(value) : Either.left(failure("INIT_RUN", "invalid PostgreSQL schema identifier"));
const validRun = (value: NativeF3PgRun): Either.Either<NativeF3PgRun, NativeF3PgError> => value.runId.length > 0 && value.runId.length <= 256 && /^[0-9a-f]{64}$/u.test(value.configDigest) && Number.isSafeInteger(value.maxCalls) && value.maxCalls >= 0 ? Either.right(value) : Either.left(failure("INIT_RUN", "invalid durable run snapshot"));
const query = <A extends QueryResultRow>(client: Client, operation: NativeF3PgError["operation"], sql: string, values: readonly unknown[] = []): Effect.Effect<QueryResult<A>, NativeF3PgError> => Effect.tryPromise({ try: () => client.query<A>(sql, [...values]), catch: () => failure(operation, "PostgreSQL query failed") });
const row = <A extends QueryResultRow>(result: QueryResult<A>, operation: NativeF3PgError["operation"]): Effect.Effect<A, NativeF3PgError> => result.rows[0] === undefined ? Effect.fail(failure(operation, "expected PostgreSQL row absent")) : Effect.succeed(result.rows[0]);
const state = (input: RunRow, operation: NativeF3PgError["operation"]) => {
  const decoded = nativeF3DecodeChatState({ maxCalls: Number(input.max_calls), used: Number(input.used), hits: 0, misses: 0 });
  return Either.isLeft(decoded) ? Effect.fail(failure(operation, "invalid persisted run counters")) : Effect.succeed(decoded.right);
};
const nextState = (before: NativeF3ChatState, cache: "HIT" | "MISS") => {
  const next = nativeF3ChatCacheTransition(before, cache);
  return Either.isLeft(next) ? Effect.fail(failure("ACQUIRE", next.left.detail)) : Effect.succeed(next.right.state);
};
const release = (client: Client, exit: Exit.Exit<unknown, unknown>) => Effect.sync(() => {
  if (Exit.isSuccess(exit)) client.release();
  else client.release(new Error("discard failed PostgreSQL transaction client"));
}).pipe(Effect.ignore);
/** A client that had any unsuccessful/interrupted transaction is discarded, never pooled dirty. */
const transaction = <A>(pool: Pick<Pool, "connect">, operation: NativeF3PgError["operation"], work: (client: Client) => Effect.Effect<A, NativeF3PgError>): Effect.Effect<A, NativeF3PgError> => Effect.acquireUseRelease(
  Effect.tryPromise({ try: () => pool.connect(), catch: () => failure(operation, "PostgreSQL connection failed") }),
  (client) => Effect.uninterruptibleMask((restore) => Effect.gen(function* () {
    yield* query<QueryResultRow>(client, operation, "BEGIN");
    const outcome = yield* Effect.exit(restore(work(client)));
    if (Exit.isSuccess(outcome)) {
      yield* query<QueryResultRow>(client, operation, "COMMIT");
      return outcome.value;
    }
    yield* query<QueryResultRow>(client, operation, "ROLLBACK").pipe(Effect.ignore);
    return yield* Effect.failCause(outcome.cause);
  })),
  release
);
const bytes = (document: Readonly<{ readonly response_meta: NativeF3OpenAiMeta }>): Either.Either<void, NativeF3PgError> => Buffer.byteLength(JSON.stringify(document), "utf8") <= 1_048_576 ? Either.right(undefined) : Either.left(failure("COMPLETE", "cache document exceeds 1 MiB"));

/** Idempotent only for the exact run identity/configuration tuple. */
export const initializeNativeF3PgRun = (config: NativeF3PgConfig): Effect.Effect<void, NativeF3PgError> => Effect.gen(function* () {
  const schema = yield* lift(validSchema(config.schema));
  const run = yield* lift(validRun(config.run));
  yield* transaction(config.pool, "INIT_RUN", (client) => query<IdRow>(client, "INIT_RUN", `INSERT INTO ${schema}.runs (run_id,config_digest,max_calls) VALUES($1,$2,$3) ON CONFLICT(run_id) DO UPDATE SET updated_at=${schema}.runs.updated_at WHERE ${schema}.runs.config_digest=EXCLUDED.config_digest AND ${schema}.runs.max_calls=EXCLUDED.max_calls RETURNING run_id`, [run.runId, run.configDigest, run.maxCalls]).pipe(Effect.flatMap((result) => row(result, "INIT_RUN")), Effect.asVoid));
});

/**
 * Engineering policy: cache entries are scoped to the durable run id. The
 * source Cache_DIR may share files across runs; that parity is intentionally
 * not claimed here until a separately qualified cache namespace is designed.
 */
export const makeNativeF3PgPersistence = (config: NativeF3PgConfig): NativeF3CachePersistenceShape => {
  const acquire: NativeF3CachePersistenceShape["acquire"] = (input) => Effect.gen(function* () {
    const schema = yield* lift(validSchema(config.schema));
    yield* lift(validRun(config.run));
    if (typeof input.clientId !== "string" || !input.clientId.length || input.clientId.length > 256 || input.clientId.includes("\u0000")) return yield* Effect.fail(failure("ACQUIRE", "invalid client identifier"));
    const result = yield* transaction(config.pool, "ACQUIRE", (client) => Effect.gen(function* () {
      const lockedRun = yield* query<RunRow>(client, "ACQUIRE", `SELECT config_digest,max_calls,used FROM ${schema}.runs WHERE run_id=$1 FOR UPDATE`, [config.run.runId]).pipe(Effect.flatMap((value) => row(value, "ACQUIRE")));
      if (lockedRun.config_digest !== config.run.configDigest || Number(lockedRun.max_calls) !== config.run.maxCalls) return yield* Effect.fail(failure("ACQUIRE", "durable run configuration mismatch"));
      const global = yield* state(lockedRun, "ACQUIRE");
      const counter = (yield* query<ClientRow>(client, "ACQUIRE", `SELECT hits,misses FROM ${schema}.client_counters WHERE run_id=$1 AND client_id=$2 FOR UPDATE`, [config.run.runId, input.clientId])).rows[0];
      const before = { ...global, hits: counter === undefined ? 0 : Number(counter.hits), misses: counter === undefined ? 0 : Number(counter.misses) };
      if (Either.isLeft(nativeF3DecodeChatState(before))) return yield* Effect.fail(failure("ACQUIRE", "invalid persisted client counters"));
      const cached = (yield* query<EntryRow>(client, "ACQUIRE", `SELECT request_sha256,status,reservation_id::text,document FROM ${schema}.cache_entries WHERE run_id=$1 AND request_sha256=$2 FOR UPDATE`, [config.run.runId, input.identity.requestSha256])).rows[0];
      if (cached !== undefined) {
        if (cached.status === "RESERVED") return { terminal: "UNRESOLVED_DISPATCH" as const, state: before, detail: "same request has an unresolved durable reservation" };
        if (cached.status === "COMPLETED") {
          const cachedMeta = nativeF3DecodeCachedMeta(cached.document);
          if (Either.isLeft(cachedMeta) || cachedMeta.right["request_sha256"] !== input.identity.requestSha256) return { terminal: "CACHE_CORRUPT" as const, state: before, detail: "completed cache document failed decoder or request correlation" };
          const next = yield* nextState(before, "HIT");
          yield* query<QueryResultRow>(client, "ACQUIRE", `INSERT INTO ${schema}.client_counters(run_id,client_id,hits,misses) VALUES($1,$2,1,0) ON CONFLICT(run_id,client_id) DO UPDATE SET hits=${schema}.client_counters.hits+1`, [config.run.runId, input.clientId]);
          return { terminal: "CACHE_HIT" as const, state: next, document: cached.document };
        }
        if (before.used >= before.maxCalls) return { terminal: "BUDGET_EXHAUSTED" as const, state: before, detail: "global F3 budget exhausted" };
        const next = yield* nextState(before, "MISS");
        const reservationId = randomUUID();
        yield* query<QueryResultRow>(client, "ACQUIRE", `INSERT INTO ${schema}.attempt_history(reservation_id,run_id,request_sha256,terminal) VALUES($1,$2,$3,'FAILED_KNOWN')`, [cached.reservation_id, config.run.runId, cached.request_sha256]);
        yield* query<QueryResultRow>(client, "ACQUIRE", `UPDATE ${schema}.cache_entries SET status='RESERVED',reservation_id=$3,document=NULL,known_terminal=NULL,completed_at=NULL WHERE run_id=$1 AND request_sha256=$2`, [config.run.runId, input.identity.requestSha256, reservationId]);
        yield* query<QueryResultRow>(client, "ACQUIRE", `UPDATE ${schema}.runs SET used=used+1,misses=misses+1,updated_at=clock_timestamp() WHERE run_id=$1`, [config.run.runId]);
        yield* query<QueryResultRow>(client, "ACQUIRE", `INSERT INTO ${schema}.client_counters(run_id,client_id,hits,misses) VALUES($1,$2,0,1) ON CONFLICT(run_id,client_id) DO UPDATE SET misses=${schema}.client_counters.misses+1`, [config.run.runId, input.clientId]);
        return { terminal: "MISS_RESERVED" as const, state: next, reservation: { reservationId } };
      }
      if (before.used >= before.maxCalls) return { terminal: "BUDGET_EXHAUSTED" as const, state: before, detail: "global F3 budget exhausted" };
      const next = yield* nextState(before, "MISS");
      const reservationId = randomUUID();
      yield* query<QueryResultRow>(client, "ACQUIRE", `INSERT INTO ${schema}.cache_entries(run_id,request_sha256,status,reservation_id) VALUES($1,$2,'RESERVED',$3)`, [config.run.runId, input.identity.requestSha256, reservationId]);
      yield* query<QueryResultRow>(client, "ACQUIRE", `UPDATE ${schema}.runs SET used=used+1,misses=misses+1,updated_at=clock_timestamp() WHERE run_id=$1`, [config.run.runId]);
      yield* query<QueryResultRow>(client, "ACQUIRE", `INSERT INTO ${schema}.client_counters(run_id,client_id,hits,misses) VALUES($1,$2,0,1) ON CONFLICT(run_id,client_id) DO UPDATE SET misses=${schema}.client_counters.misses+1`, [config.run.runId, input.clientId]);
      return { terminal: "MISS_RESERVED" as const, state: next, reservation: { reservationId } };
    }));
    return result;
  }).pipe(Effect.mapError((error): NativeF3CachePersistenceError => new NativeF3CachePersistenceError({ operation: "ACQUIRE", detail: error.detail })));

  const settle = (operation: "COMPLETE" | "FAIL_KNOWN", reservation: NativeF3CacheReservation, identity: NativeF3ChatIdentity | undefined, document: Readonly<{ readonly response_meta: NativeF3OpenAiMeta }> | undefined, known: "TRANSPORT_ERROR" | "RESPONSE_SCHEMA_ERROR" | undefined): Effect.Effect<void, NativeF3CachePersistenceError> => Effect.gen(function* () {
    const schema = yield* lift(validSchema(config.schema));
    yield* lift(validRun(config.run));
    if (document !== undefined) {
      if (Either.isLeft(nativeF3DecodeCachedMeta(document))) return yield* Effect.fail(failure("COMPLETE", "completed document failed source cache decoder"));
      if (identity === undefined || document.response_meta.request_sha256 !== identity.requestSha256) return yield* Effect.fail(failure("COMPLETE", "document request identity mismatch"));
      yield* lift(bytes(document));
    }
    yield* transaction(config.pool, operation, (client) => Effect.gen(function* () {
      const lockedRun = yield* query<RunRow>(client, operation, `SELECT config_digest,max_calls,used FROM ${schema}.runs WHERE run_id=$1 FOR UPDATE`, [config.run.runId]).pipe(Effect.flatMap((value) => row(value, operation)));
      if (lockedRun.config_digest !== config.run.configDigest || Number(lockedRun.max_calls) !== config.run.maxCalls) return yield* Effect.fail(failure(operation, "durable run configuration mismatch"));
      const existing = yield* query<EntryRow>(client, operation, `SELECT request_sha256,status,reservation_id::text,document FROM ${schema}.cache_entries WHERE run_id=$1 AND reservation_id=$2 FOR UPDATE`, [config.run.runId, reservation.reservationId]).pipe(Effect.flatMap((value) => row(value, operation)));
      if (identity !== undefined && existing.request_sha256 !== identity.requestSha256) return yield* Effect.fail(failure(operation, "reservation identity mismatch"));
      if (document !== undefined && existing.status === "COMPLETED") {
        const same = yield* query<BooleanRow>(client, operation, `SELECT document=$3::jsonb AS same FROM ${schema}.cache_entries WHERE run_id=$1 AND reservation_id=$2`, [config.run.runId, reservation.reservationId, JSON.stringify(document)]).pipe(Effect.flatMap((value) => row(value, operation)));
        if (same.same) return;
        return yield* Effect.fail(failure(operation, "completed reservation differs from supplied source meta"));
      }
      if (existing.status !== "RESERVED") return yield* Effect.fail(failure(operation, "reservation is not open"));
      if (document !== undefined) yield* query<QueryResultRow>(client, operation, `UPDATE ${schema}.cache_entries SET status='COMPLETED',document=$3::jsonb,completed_at=clock_timestamp() WHERE run_id=$1 AND reservation_id=$2`, [config.run.runId, reservation.reservationId, JSON.stringify(document)]);
      else yield* query<QueryResultRow>(client, operation, `UPDATE ${schema}.cache_entries SET status='FAILED_KNOWN',known_terminal=$3,completed_at=clock_timestamp() WHERE run_id=$1 AND reservation_id=$2`, [config.run.runId, reservation.reservationId, known]);
    }));
  }).pipe(Effect.mapError((error): NativeF3CachePersistenceError => new NativeF3CachePersistenceError({ operation, detail: error.detail })));

  return Object.freeze({
    acquire,
    complete: (input: Parameters<NativeF3CachePersistenceShape["complete"]>[0]) => settle("COMPLETE", input.reservation, input.identity, input.document, undefined),
    failKnown: (input: Parameters<NativeF3CachePersistenceShape["failKnown"]>[0]) => input.delivery === (input.terminal === "TRANSPORT_ERROR" ? "NOT_SENT" : "RESPONSE_RECEIVED")
      ? settle("FAIL_KNOWN", input.reservation, undefined, undefined, input.terminal)
      : Effect.fail(new NativeF3CachePersistenceError({ operation: "FAIL_KNOWN", detail: "confirmed delivery evidence is required to release a reservation" }))
  });
};
export const makeNativeF3PgPersistenceLayer = (config: NativeF3PgConfig) => Layer.succeed(NativeF3CachePersistence, makeNativeF3PgPersistence(config));
