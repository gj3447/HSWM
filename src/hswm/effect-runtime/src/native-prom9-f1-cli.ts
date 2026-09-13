/** Bounded `hswm-prom9-f1 judge` command; it only reads sealed artifacts. */
import { basename, dirname, resolve } from "node:path";
import { parseArgs } from "node:util";
import { Data, Effect, Either } from "effect";
import { PosixFileSystem } from "./effect-posix-filesystem.js";
import { decodeNativeTaskJson, renderNativeTaskJson } from "./native-task-json-domain.js";
import { judgeNativeProm9F1Suite } from "./native-prom9-f1-domain.js";
export class NativeProm9F1CliError extends Data.TaggedError("NativeProm9F1CliError")<{
    readonly detail: string;
}> {
}
const fail = (detail: string) => new NativeProm9F1CliError({ detail });
const usage = "usage: hswm-prom9-f1 judge --suite FILE --gold FILE --output FILE [--bootstrap-reps N] [--bootstrap-seed N]";
const maximumBytes = 64 * 1024 * 1024;
const input = (path: string, label: string): Effect.Effect<ReturnType<typeof decodeNativeTaskJson> extends Either.Either<infer A, unknown> ? A : never, NativeProm9F1CliError, PosixFileSystem> => Effect.gen(function* () { const fs = yield* PosixFileSystem; const bytes = yield* fs.readRegularBounded(path, { maximumBytes, operation: `read F1 ${label}` }).pipe(Effect.mapError(error => fail(error.detail))); const parsed = decodeNativeTaskJson(bytes.bytes); return yield* Either.match(parsed, { onLeft: () => Effect.fail(fail(`${label} JSON is invalid`)), onRight: Effect.succeed }); });
const writeOnce = (path: string, source: string): Effect.Effect<void, NativeProm9F1CliError, PosixFileSystem> => Effect.gen(function* () {
    const fs = yield* PosixFileSystem;
    yield* fs.makeDirectory(dirname(path), { mode: 0o755, recursive: true, operation: "create F1 output directory" }).pipe(Effect.mapError(error => fail(error.detail)));
    const temp = resolve(dirname(path), `.${basename(path)}.partial-${process.pid}`);
    const bytes = new TextEncoder().encode(source);
    const acquire = fs.writeExclusive(temp, bytes, { mode: 0o644, sync: true, operation: "write F1 partial" }).pipe(Effect.mapError(error => fail(error.code === "EEXIST" ? `stale partial output requires inspection: ${temp}` : error.detail)));
    yield* Effect.acquireUseRelease(acquire, () => Effect.gen(function* () { yield* fs.linkNoReplace(temp, path, "publish F1 judgment").pipe(Effect.mapError(error => fail(error.code === "EEXIST" ? `refusing to replace output: ${path}` : error.detail))); yield* fs.syncDirectory(dirname(path), "sync F1 judgment directory").pipe(Effect.mapError(error => fail(error.detail))); }), () => fs.unlinkIfPresent(temp, "remove F1 partial").pipe(Effect.ignore));
});
export const runNativeProm9F1Cli = (argv: readonly string[]): Effect.Effect<string, NativeProm9F1CliError, PosixFileSystem> => Effect.gen(function* () {
    const parsed = yield* Effect.try({ try: () => parseArgs({ args: [...argv], strict: true, allowPositionals: true as const, options: { suite: { type: "string" }, gold: { type: "string" }, output: { type: "string" }, "bootstrap-reps": { type: "string" }, "bootstrap-seed": { type: "string" }, help: { type: "boolean", short: "h" } } }), catch: () => fail(usage) });
    if (parsed.values.help)
        return `${usage}\nReads a bounded suite and separate gold file; output is no-replace.\n`;
    if (parsed.positionals.length !== 1 || parsed.positionals[0] !== "judge" || typeof parsed.values.suite !== "string" || typeof parsed.values.gold !== "string" || typeof parsed.values.output !== "string")
        return yield* Effect.fail(fail(usage));
    const parseInteger = (raw: string | undefined, fallback: number): number | undefined => raw === undefined ? fallback : /^[+-]?\d+$/u.test(raw) && Number.isSafeInteger(Number(raw)) ? Number(raw) : undefined;
    const reps = parseInteger(parsed.values["bootstrap-reps"], 10000), seed = parseInteger(parsed.values["bootstrap-seed"], 20260724);
    if (reps === undefined || reps < 1 || seed === undefined)
        return yield* Effect.fail(fail("bootstrap reps and seed must be integers"));
    const suite = yield* input(resolve(parsed.values.suite), "suite"), gold = yield* input(resolve(parsed.values.gold), "gold"), judgment = judgeNativeProm9F1Suite(suite, gold, reps, seed);
    const value = yield* Either.match(judgment, { onLeft: error => Effect.fail(fail(error.detail)), onRight: Effect.succeed });
    const source = `${renderNativeTaskJson(value, "pretty")}\n`;
    yield* writeOnce(resolve(parsed.values.output), source);
    return source;
});
