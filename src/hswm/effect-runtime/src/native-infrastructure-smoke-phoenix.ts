/** Exact Phoenix viewer probe contracts and the bounded official MCP transport. */
import { Effect, Either } from "effect";
import { Client } from "@modelcontextprotocol/client";
import { StdioClientTransport } from "@modelcontextprotocol/client/stdio";
import { NativeInfrastructureSmokeError } from "./native-infrastructure-smoke-domain.js";
export const PHOENIX_VIEWER_EXPECTED_TOOLS = Object.freeze(["describeSqlSchema", "executeSql", "getProject", "getProjects"]);
export const PHOENIX_VIEWER_CLAIM_BOUNDARY = "infrastructure smoke only; not HSWM cognition, causal credit, canonical admission, continuous learning, or efficacy evidence";
export interface PhoenixViewerTool {
    readonly name: string;
    readonly readOnlyHint: boolean;
}
export interface PhoenixViewerProbe {
    readonly tools: readonly PhoenixViewerTool[];
    readonly readRows: unknown;
    readonly readIsError: boolean;
    readonly unsafeError: string | null;
    readonly unsafeIsError: boolean;
}
export interface PhoenixViewerSmokeResult {
    readonly schema: "hswm-phoenix-viewer-mcp-smoke/v1";
    readonly claim_boundary: typeof PHOENIX_VIEWER_CLAIM_BOUNDARY;
    readonly status: "PASS";
    readonly tools: readonly string[];
    readonly read_probe_rows: 1;
    readonly unsafe_sql_code: "not_read_only" | "unsupported_syntax";
    readonly mutation_tools_exposed: false;
}
const failure = (detail: string) => new NativeInfrastructureSmokeError({ code: "TRACE_REFUSED", detail });
export const validatePhoenixViewerProbe = (probe: PhoenixViewerProbe): Either.Either<PhoenixViewerSmokeResult, NativeInfrastructureSmokeError> => {
    const names = [...new Set(probe.tools.map(tool => tool.name))].sort();
    if (JSON.stringify(names) !== JSON.stringify(PHOENIX_VIEWER_EXPECTED_TOOLS) || probe.tools.some(tool => !tool.readOnlyHint))
        return Either.left(failure("unexpected tool surface or missing read-only annotations"));
    const rows = probe.readRows;
    if (probe.readIsError || !Array.isArray(rows) || rows.length !== 1 || !Object.hasOwn(rows, 0) || !Array.isArray(rows[0]) || rows[0].length !== 1 || !Object.hasOwn(rows[0], 0) || (rows[0][0] !== 1 && rows[0][0] !== true))
        return Either.left(failure("bounded analytics read probe failed"));
    if (probe.unsafeIsError || (probe.unsafeError !== "not_read_only" && probe.unsafeError !== "unsupported_syntax"))
        return Either.left(failure("unsafe SQL was not refused by the analytics admission gate"));
    return Either.right(Object.freeze({ schema: "hswm-phoenix-viewer-mcp-smoke/v1", claim_boundary: PHOENIX_VIEWER_CLAIM_BOUNDARY, status: "PASS", tools: Object.freeze(names), read_probe_rows: 1, unsafe_sql_code: probe.unsafeError, mutation_tools_exposed: false }));
};
const record = (value: unknown): Readonly<Record<string, unknown>> => typeof value === "object" && value !== null && !Array.isArray(value) ? value as Readonly<Record<string, unknown>> : {};
/** The caller selects one launcher; all SDK resources are released on failure or interruption. */
export const runPhoenixViewerMcpSmoke = (launcher: string): Effect.Effect<PhoenixViewerSmokeResult, NativeInfrastructureSmokeError> => {
    if (launcher.length === 0 || launcher.includes("\0"))
        return Effect.fail(failure("Phoenix launcher path is invalid"));
    return Effect.acquireUseRelease(Effect.try({ try: () => ({ transport: new StdioClientTransport({ command: launcher, args: [], stderr: "ignore", maxBufferSize: 1048576 }), client: new Client({ name: "hswm-phoenix-viewer-smoke", version: "1" }) }), catch: () => failure("Phoenix MCP transport initialization failed") }), ({ client, transport }) => Effect.gen(function* () {
        const invoke = <A>(run: (signal: AbortSignal) => Promise<A>) => Effect.tryPromise({ try: run, catch: () => failure("Phoenix MCP request failed") });
        yield* invoke(signal => client.connect(transport, { signal, timeout: 10000 }));
        const tools: PhoenixViewerTool[] = [];
        const cursors = new Set<string>();
        let cursor: string | undefined;
        for (let page = 0; page < 32; page += 1) {
            const listed = yield* invoke(signal => client.listTools(cursor === undefined ? undefined : { cursor }, { signal, timeout: 10000 }));
            tools.push(...listed.tools.map(tool => ({ name: tool.name, readOnlyHint: tool.annotations?.readOnlyHint === true })));
            if (listed.nextCursor === undefined)
                break;
            if (page === 31 || cursors.has(listed.nextCursor))
                return yield* Effect.fail(failure("Phoenix MCP tool listing exceeded its bounded pagination contract"));
            cursors.add(listed.nextCursor);
            cursor = listed.nextCursor;
        }
        if (JSON.stringify([...new Set(tools.map(tool => tool.name))].sort()) !== JSON.stringify(PHOENIX_VIEWER_EXPECTED_TOOLS) || tools.some(tool => !tool.readOnlyHint))
            return yield* Effect.fail(failure("unexpected tool surface or missing read-only annotations"));
        const read = yield* invoke(signal => client.callTool({ name: "executeSql", arguments: { sql: "SELECT 1 AS read_probe", row_limit: 1 } }, { signal, timeout: 10000 }));
        const unsafe = yield* invoke(signal => client.callTool({ name: "executeSql", arguments: { sql: "CREATE TABLE hswm_mcp_forbidden(x INTEGER)" } }, { signal, timeout: 10000 }));
        const unsafeCode = record(record(unsafe.structuredContent)["error"])["code"];
        const checked = validatePhoenixViewerProbe({ tools, readRows: record(read.structuredContent)["rows"], readIsError: read.isError === true, unsafeError: typeof unsafeCode === "string" ? unsafeCode : null, unsafeIsError: unsafe.isError === true });
        return yield* checked;
    }).pipe(Effect.timeoutFail({ duration: "40 seconds", onTimeout: () => failure("Phoenix MCP smoke exceeded its deadline") })), ({ client, transport }) => Effect.all([() => client.close(), () => transport.close()].map(close => Effect.tryPromise({ try: close, catch: () => failure("Phoenix MCP close failed") }).pipe(Effect.timeoutOption("5 seconds"), Effect.ignore)), { concurrency: 2, discard: true }));
};
