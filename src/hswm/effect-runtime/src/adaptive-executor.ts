/**
 * Bounded leaf executors for the local adaptive runtime.  These observations
 * are deliberately not outcomes: an LLM HTTP 200 has `success: null`.
 */
import { createHash } from "node:crypto";
import { Context, Data, Effect } from "effect";
import { BoundedSubprocess } from "./effect-bounded-subprocess.js";
export const ADAPTIVE_EXECUTOR_V1 = "hswm-adaptive-executor/v1" as const;
const MAX_INPUT_BYTES = 1000000;
const MAX_OUTPUT_BYTES = 64000;
export type AdaptiveLeafCell = Readonly<Record<string, unknown>>;
export interface AdaptiveExecution {
    readonly status: "SUCCEEDED" | "FAILED" | "UNKNOWN" | "WITHHOLD";
    /** Only an explicitly declared command exit-code checker may set this. */
    readonly success: boolean | null;
    readonly durationSeconds: number;
    readonly output: string;
    readonly outputDigest: string;
    readonly metadata: Readonly<Record<string, unknown>>;
}
export class AdaptiveExecutorError extends Data.TaggedError("AdaptiveExecutorError")<{
    readonly code: "CELL_INVALID" | "INPUT_INVALID" | "HTTP_FAILED" | "HTTP_INVALID";
    readonly detail: string;
}> {
}
export interface AdaptiveHttpRequest {
    readonly url: string;
    readonly headers: Readonly<Record<string, string>>;
    readonly body: Uint8Array;
    readonly timeoutMs: number;
    readonly maximumResponseBytes: number;
}
export interface AdaptiveHttpClientShape {
    readonly postJson: (request: AdaptiveHttpRequest) => Effect.Effect<Uint8Array, AdaptiveExecutorError>;
}
export class AdaptiveHttpClient extends Context.Tag("hswm/AdaptiveHttpClient")<AdaptiveHttpClient, AdaptiveHttpClientShape>() {
}
const digest = (value: string): string => createHash("sha256").update(value, "utf8").digest("hex");
const text = (value: unknown): value is string => typeof value === "string" && value.trim().length > 0 && value.length <= 64000;
const now = Effect.clockWith((clock) => clock.currentTimeMillis);
const jsonInput = (value: unknown) => Effect.try({
    try: () => JSON.stringify(value),
    catch: () => new AdaptiveExecutorError({ code: "INPUT_INVALID", detail: "input is not JSON serializable" })
});
const finish = (status: AdaptiveExecution["status"], success: boolean | null, started: number, ended: number, output: string, metadata: Readonly<Record<string, unknown>>): AdaptiveExecution => Object.freeze({ status, success, durationSeconds: Math.max(0, (ended - started) / 1000), output, outputDigest: digest(output), metadata: Object.freeze(metadata) });
const completed = (status: AdaptiveExecution["status"], success: boolean | null, started: number, output: string, metadata: Readonly<Record<string, unknown>>): Effect.Effect<AdaptiveExecution> => now.pipe(Effect.map((ended) => finish(status, success, started, ended, output, metadata)));
const httpFailure = (cause: unknown) => new AdaptiveExecutorError({ code: "HTTP_FAILED", detail: cause instanceof Error ? cause.message : "unknown HTTP failure" });
const readChunk = (reader: ReadableStreamDefaultReader<Uint8Array>) => Effect.tryPromise({ try: () => reader.read(), catch: httpFailure });
const cancelReader = (reader: ReadableStreamDefaultReader<Uint8Array>) => Effect.tryPromise({ try: () => reader.cancel(), catch: httpFailure }).pipe(Effect.orDie);
const collectResponse = (reader: ReadableStreamDefaultReader<Uint8Array>, maximumResponseBytes: number, chunks: ReadonlyArray<Uint8Array> = [], total = 0): Effect.Effect<Uint8Array, AdaptiveExecutorError> => Effect.gen(function* () {
    const item = yield* readChunk(reader);
    if (item.done) {
        const joined = new Uint8Array(total);
        let offset = 0;
        for (const chunk of chunks) {
            joined.set(chunk, offset);
            offset += chunk.byteLength;
        }
        return joined;
    }
    const nextTotal = total + item.value.byteLength;
    if (nextTotal > maximumResponseBytes)
        return yield* Effect.fail(new AdaptiveExecutorError({ code: "HTTP_FAILED", detail: "RESPONSE_TOO_LARGE" }));
    return yield* collectResponse(reader, maximumResponseBytes, [...chunks, item.value], nextTotal);
});
const boundedNativePostJson = (request: AdaptiveHttpRequest): Effect.Effect<Uint8Array, AdaptiveExecutorError> => Effect.acquireUseRelease(Effect.sync(() => new AbortController()), (controller) => Effect.gen(function* () {
    const response = yield* Effect.tryPromise({
        try: () => fetch(request.url, { method: "POST", headers: request.headers, body: request.body, signal: controller.signal }),
        catch: httpFailure
    });
    if (!response.ok || response.body === null)
        return yield* Effect.fail(new AdaptiveExecutorError({ code: "HTTP_FAILED", detail: `HTTP_${response.status}` }));
    return yield* Effect.acquireUseRelease(Effect.sync(() => response.body!.getReader()), (reader) => collectResponse(reader, request.maximumResponseBytes), (reader) => cancelReader(reader));
}).pipe(Effect.timeoutFail({ duration: request.timeoutMs, onTimeout: () => new AdaptiveExecutorError({ code: "HTTP_FAILED", detail: "HTTP_TIMEOUT" }) })), (controller) => Effect.sync(() => controller.abort()));
export const NativeAdaptiveHttpClient: AdaptiveHttpClientShape = Object.freeze({
    postJson: (request: AdaptiveHttpRequest) => request.timeoutMs < 1 || request.maximumResponseBytes < 1
        ? Effect.fail(new AdaptiveExecutorError({ code: "HTTP_INVALID", detail: "HTTP bounds must be positive" }))
        : boundedNativePostJson(request)
});
const command = (cell: AdaptiveLeafCell): readonly string[] | null => {
    const argv = cell["argv"];
    return Array.isArray(argv) && argv.length > 0 && argv.every((part) => typeof part === "string" && part.length > 0 && !part.includes("\0") && part !== "{input}") ? argv : null;
};
const runCommand = (cell: AdaptiveLeafCell, payload: unknown, workspace: string, timeoutMs: number): Effect.Effect<AdaptiveExecution, never, BoundedSubprocess> => Effect.gen(function* () {
    const started = yield* now;
    const argv = command(cell);
    if (argv === null)
        return yield* completed("FAILED", null, started, "", { kind: "command", error: "literal argv required" });
    const encoded = yield* jsonInput(payload).pipe(Effect.either);
    if (encoded._tag === "Left")
        return yield* completed("FAILED", null, started, "", { kind: "command", error: encoded.left.code });
    const input = encoded.right;
    if (Buffer.byteLength(input, "utf8") > MAX_INPUT_BYTES)
        return yield* completed("FAILED", null, started, "", { kind: "command", error: "input too large" });
    const subprocess = yield* BoundedSubprocess;
    const observed = yield* subprocess.observe({ argv, cwd: workspace, environment: process.env as Record<string, string>, timeoutMs, maximumOutputBytes: MAX_OUTPUT_BYTES, stdin: Buffer.from(input), killProcessGroup: true }).pipe(Effect.catchAll((error) => Effect.succeed({ exitCode: null, signal: null, timedOut: false, outputTruncated: false, launchError: error.code, stdout: new Uint8Array(), stderr: new Uint8Array() })));
    const output = Buffer.concat([Buffer.from(observed.stdout), Buffer.from(observed.stderr)]).toString("utf8");
    if (observed.timedOut || observed.signal !== null || observed.launchError !== null || observed.outputTruncated)
        return yield* completed("UNKNOWN", null, started, output, { kind: "command", timedOut: observed.timedOut, signal: observed.signal, launchError: observed.launchError, outputTruncated: observed.outputTruncated });
    const checker = cell["outcome"] === "exit_code";
    return yield* completed(observed.exitCode === 0 ? "SUCCEEDED" : "FAILED", checker ? observed.exitCode === 0 : null, started, output, { kind: "command", exitCode: observed.exitCode, outputTruncated: observed.outputTruncated });
});
const runLlm = (cell: AdaptiveLeafCell, payload: unknown, timeoutMs: number): Effect.Effect<AdaptiveExecution, never, AdaptiveHttpClient> => Effect.gen(function* () {
    const started = yield* now;
    const baseUrl = cell["base_url"], model = cell["model"];
    if (!text(baseUrl) || !text(model))
        return yield* completed("FAILED", null, started, "", { kind: "llm", error: "base_url and model required" });
    const keyName = cell["api_key_env"];
    const apiKey = typeof keyName === "string" ? process.env[keyName] : undefined;
    const prompt = typeof payload === "object" && payload !== null && typeof (payload as Record<string, unknown>)["prompt"] === "string"
        ? Effect.succeed((payload as Record<string, unknown>)["prompt"] as string)
        : jsonInput(payload);
    const encodedPrompt = yield* prompt.pipe(Effect.either);
    if (encodedPrompt._tag === "Left")
        return yield* completed("FAILED", null, started, "", { kind: "llm", error: encodedPrompt.left.code });
    const requestBody = yield* jsonInput({ model, messages: [{ role: "user", content: encodedPrompt.right }], max_tokens: typeof cell["max_tokens"] === "number" ? cell["max_tokens"] : undefined }).pipe(Effect.either);
    if (requestBody._tag === "Left")
        return yield* completed("FAILED", null, started, "", { kind: "llm", error: requestBody.left.code });
    const body = Buffer.from(requestBody.right, "utf8");
    if (body.byteLength > MAX_INPUT_BYTES)
        return yield* completed("FAILED", null, started, "", { kind: "llm", error: "input too large" });
    const client = yield* AdaptiveHttpClient;
    const normalizedBaseUrl = baseUrl.replace(/\/$/, "");
    const endpoint = normalizedBaseUrl.endsWith("/v1") ? `${normalizedBaseUrl}/chat/completions` : `${normalizedBaseUrl}/v1/chat/completions`;
    const raw = yield* client.postJson({ url: endpoint, headers: Object.freeze({ "content-type": "application/json", ...(apiKey === undefined ? {} : { authorization: `Bearer ${apiKey}` }) }), body, timeoutMs, maximumResponseBytes: MAX_OUTPUT_BYTES }).pipe(Effect.either);
    if (raw._tag === "Left")
        return yield* completed("UNKNOWN", null, started, "", { kind: "llm", error: raw.left.code });
    const output = Buffer.from(raw.right).toString("utf8");
    try {
        const decoded: unknown = JSON.parse(output);
        const content = (decoded as {
            choices?: Array<{
                message?: {
                    content?: unknown;
                };
            }>;
        }).choices?.[0]?.message?.content;
        if (typeof content !== "string")
            return yield* completed("FAILED", null, started, output, { kind: "llm", error: "OpenAI compatible response lacks choices[0].message.content" });
        return yield* completed("SUCCEEDED", null, started, content, { kind: "llm", response: "OBSERVED_NOT_OUTCOME" });
    }
    catch {
        return yield* completed("FAILED", null, started, output, { kind: "llm", error: "invalid JSON" });
    }
});
/** Executes only already-admitted cells; all unknown effect outcomes fail closed. */
export const executeAdaptiveCell = (cell: AdaptiveLeafCell, payload: unknown, workspace: string, timeoutMs: number): Effect.Effect<AdaptiveExecution, never, BoundedSubprocess | AdaptiveHttpClient> => {
    if (!Number.isSafeInteger(timeoutMs) || timeoutMs < 1)
        return now.pipe(Effect.flatMap((started) => completed("UNKNOWN", null, started, "", { error: "invalid timeout" })));
    return cell["kind"] === "command" ? runCommand(cell, payload, workspace, timeoutMs) : cell["kind"] === "llm" ? runLlm(cell, payload, timeoutMs) : now.pipe(Effect.flatMap((started) => completed("FAILED", null, started, "", { error: "not a leaf cell" })));
};
