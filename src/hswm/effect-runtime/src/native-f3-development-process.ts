#!/usr/bin/env node
/** One source-shaped F3 development call with durable run-scoped PG state. */
import { isAbsolute } from "node:path";
import { Pool } from "pg";
import { Effect, Either } from "effect";
import { decodeCanonicalJsonBytes, type CanonicalJson } from "./canonical-atom-v2-json.js";
import { PosixFileSystem } from "./effect-posix-services.js";
import { refuse, runProcessMain, type ProcessRefusal } from "./effect-process-main.js";
import { nativeF3ChatRequestIdentity, type NativeF3ChatRequest } from "./native-f3-chat-domain.js";
import { makeNativeF3PersistentChat, type NativeF3CacheProviderShape } from "./native-f3-cache-runtime.js";
import { NativeF3FetchProviderLive } from "./native-f3-fetch-provider.js";
import { initializeNativeF3PgRun, makeNativeF3PgPersistence, type NativeF3PgRun } from "./native-f3-pg-persistence.js";

const object = (value: unknown): value is Readonly<Record<string, unknown>> => typeof value === "object" && value !== null && !Array.isArray(value);
const exact = (value: Readonly<Record<string, unknown>>, keys: readonly string[]): boolean => Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
const validId = (value: unknown): value is string => typeof value === "string" && value.length > 0 && value.length <= 256 && !value.includes("\u0000");

type Request = Readonly<{ configPath: string; schema: string; run: NativeF3PgRun; clientId: string; request: NativeF3ChatRequest; timeoutSeconds: number }>;
export const decodeNativeF3DevelopmentRequest = (input: unknown): Either.Either<Request, ProcessRefusal> => {
  if (!object(input) || !exact(input, ["schema_version", "mode", "config_path", "database_schema", "run", "client_id", "request", "timeout_seconds"]) || input["schema_version"] !== "hswm-native-f3-development-request/v1" || input["mode"] !== "DEVELOPMENT_ONLY") return Either.left(refuse("expected an explicit development-only F3 request"));
  const run = input["run"], request = input["request"], configPath = input["config_path"], schema = input["database_schema"], clientId = input["client_id"], timeout = input["timeout_seconds"];
  if (typeof configPath !== "string" || !isAbsolute(configPath) || configPath.includes("\u0000") || typeof schema !== "string" || !/^[a-z_][a-z0-9_]{0,62}$/.test(schema) || !validId(clientId) || typeof timeout !== "number" || !Number.isSafeInteger(timeout) || timeout <= 0 || timeout > 86400) return Either.left(refuse("invalid F3 development configuration"));
  if (!object(run) || !exact(run, ["runId", "configDigest", "maxCalls"]) || !validId(run["runId"]) || typeof run["configDigest"] !== "string" || !/^[0-9a-f]{64}$/.test(run["configDigest"]) || typeof run["maxCalls"] !== "number" || !Number.isSafeInteger(run["maxCalls"]) || run["maxCalls"] < 0) return Either.left(refuse("invalid F3 durable run identity"));
  if (!object(request) || Either.isLeft(nativeF3ChatRequestIdentity(request as NativeF3ChatRequest))) return Either.left(refuse("invalid source-shaped F3 chat request"));
  return Either.right(Object.freeze({ configPath, schema, clientId, timeoutSeconds: timeout, run: Object.freeze({ runId: run["runId"], configDigest: run["configDigest"], maxCalls: run["maxCalls"] }), request: Object.freeze({ ...request }) as NativeF3ChatRequest }));
};

export const executeNativeF3Development = (input: CanonicalJson, provider: NativeF3CacheProviderShape = NativeF3FetchProviderLive): Effect.Effect<CanonicalJson, ProcessRefusal, PosixFileSystem> => Effect.gen(function* () {
  const parsed = decodeNativeF3DevelopmentRequest(input);
  if (Either.isLeft(parsed)) return yield* Effect.fail(parsed.left);
  const request = parsed.right, fs = yield* PosixFileSystem;
  const bytes = yield* fs.readRegularBounded(request.configPath, { maximumBytes: 65536, minimumBytes: 1, requiredMode: 0o600, operation: "read private F3 PostgreSQL config" }).pipe(Effect.mapError(() => refuse("private F3 database configuration could not be read")));
  const config = decodeCanonicalJsonBytes(bytes.bytes);
  if (Either.isLeft(config) || !object(config.right) || !exact(config.right, ["connectionString"]) || typeof config.right["connectionString"] !== "string" || !/^postgres(?:ql)?:\/\//.test(config.right["connectionString"])) return yield* Effect.fail(refuse("invalid private F3 database configuration"));
  const connectionString = config.right["connectionString"];
  return yield* Effect.acquireUseRelease(
    Effect.try({ try: () => new Pool({ connectionString, max: 1, connectionTimeoutMillis: 5000, idleTimeoutMillis: 1000, statement_timeout: 10000 }), catch: () => refuse("F3 database pool initialization failed") }),
    pool => Effect.gen(function* () {
      const durable = { pool, schema: request.schema, run: request.run };
      yield* initializeNativeF3PgRun(durable).pipe(Effect.mapError(() => refuse("F3 database schema unavailable or durable run configuration changed")));
      const outcome = yield* makeNativeF3PersistentChat(makeNativeF3PgPersistence(durable), provider)(request.request, request.clientId, request.timeoutSeconds).pipe(Effect.mapError(() => refuse("F3 request failed domain validation")));
      const common = { schema_version: "hswm-native-f3-development-result/v1", mode: "DEVELOPMENT_ONLY", run_id: request.run.runId, client_id: request.clientId, request_sha256: outcome.identity.requestSha256, terminal: outcome.terminal, state: outcome.state };
      return "meta" in outcome ? { ...common, response_meta: outcome.meta } : { ...common, detail: outcome.detail };
    }),
    pool => Effect.promise(() => pool.end()).pipe(Effect.ignore)
  );
});

if (import.meta.main) process.exitCode = await runProcessMain({ refusalPrefix: "HSWM_F3_DEVELOPMENT_REFUSED", program: executeNativeF3Development, describeFailure: error => error.detail });
