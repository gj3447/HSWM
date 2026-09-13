/** Native commands for the two bounded infrastructure probes. */
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import { randomUUID } from "node:crypto";
import { parseArgs } from "node:util";
import { Effect } from "effect";
import { PosixFileSystem } from "./effect-posix-filesystem.js";
import { decodeGeneralJsonBytes, type GeneralJson } from "./general-json-domain.js";
import { completeResearchFabricSmoke, NativeInfrastructureSmokeError, validateResearchFabricRunId } from "./native-infrastructure-smoke-domain.js";
import { emitResearchFabricTrace, runResearchFabricTemporalLifecycle } from "./native-infrastructure-smoke-runtime.js";
import { runPhoenixViewerMcpSmoke } from "./native-infrastructure-smoke-phoenix.js";
import { renderNativeTaskJson, type TaskJson } from "./native-task-json-domain.js";
const usage = "hswm-infrastructure-smoke <fabric|phoenix> [--launcher FILE] [--secret-file FILE] [--run-id ID]";
const failure = (code: NativeInfrastructureSmokeError["code"], detail: string) => new NativeInfrastructureSmokeError({ code, detail });
const isRecord = (value: GeneralJson): value is Readonly<Record<string, GeneralJson>> => typeof value === "object" && value !== null && !Array.isArray(value);
export const runNativeInfrastructureSmokeCli = (argv: readonly string[]) => Effect.gen(function* () {
    const parsed = yield* Effect.try({ try: () => parseArgs({ args: [...argv], allowPositionals: true, strict: true, options: { help: { type: "boolean" }, launcher: { type: "string" }, "secret-file": { type: "string" }, "run-id": { type: "string" } } }), catch: () => failure("USAGE", usage) });
    if (parsed.values.help)
        return `${usage}\nConnects only to the configured local infrastructure; does not run a research experiment.\n`;
    const kind = parsed.positionals[0];
    if (parsed.positionals.length !== 1 || !["fabric", "phoenix"].includes(kind ?? ""))
        return yield* Effect.fail(failure("USAGE", usage));
    if (kind === "phoenix") {
        if (parsed.values["secret-file"] !== undefined || parsed.values["run-id"] !== undefined)
            return yield* Effect.fail(failure("USAGE", "fabric options do not apply to phoenix"));
        const result = yield* runPhoenixViewerMcpSmoke(resolve(parsed.values.launcher ?? join(homedir(), ".local/libexec/hswm-phoenix-viewer-mcp")));
        return `${renderNativeTaskJson({ ...result }, "pretty")}\n`;
    }
    if (parsed.values.launcher !== undefined)
        return yield* Effect.fail(failure("USAGE", "launcher does not apply to fabric"));
    const runId = yield* validateResearchFabricRunId(parsed.values["run-id"] ?? `${BigInt(Date.now()) * 1000000n}-${randomUUID().replaceAll("-", "").slice(0, 12)}`);
    const fs = yield* PosixFileSystem;
    const secretPath = resolve(parsed.values["secret-file"] ?? join(homedir(), ".local/state/hswm-research-fabric/secrets/phoenix.json"));
    const bytes = yield* fs.readRegularBounded(secretPath, { maximumBytes: 65536, minimumBytes: 1, operation: "private Phoenix smoke configuration" }).pipe(Effect.mapError(() => failure("SECRET_INVALID", "Phoenix smoke configuration is unavailable")));
    const decoded = yield* decodeGeneralJsonBytes(bytes.bytes, { maximumBytes: 65536 }).pipe(Effect.mapError(() => failure("SECRET_INVALID", "Phoenix smoke configuration is invalid")));
    if (!isRecord(decoded) || typeof decoded["phoenix_admin_secret"] !== "string" || decoded["phoenix_admin_secret"].length === 0)
        return yield* Effect.fail(failure("SECRET_INVALID", "Phoenix smoke secret is missing"));
    const temporal = yield* runResearchFabricTemporalLifecycle(runId, resolve(import.meta.dirname, "native-infrastructure-smoke-workflow.js"));
    const result = yield* completeResearchFabricSmoke(runId, temporal);
    yield* emitResearchFabricTrace(result, decoded["phoenix_admin_secret"]);
    const output: TaskJson = { ...result, temporal: { ...result.temporal, result: { ...result.temporal.result } } };
    return `${renderNativeTaskJson(output, "pretty")}\n`;
});
