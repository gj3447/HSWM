/** Effect shell for bounded native conditional-task JSON proposals. */
import { pathToFileURL } from "node:url";
import { Data, Effect, Either } from "effect";
import { decodeNativeTaskJson, renderNativeTaskJson, taskJsonRecord } from "./native-task-json-domain.js";
import { NativeTaskIo, NodeNativeTaskIoLive } from "./native-task-io.js";
import { runArgvProcessMain, type ProcessReply } from "./effect-process-main.js";
import { probeNativeTask, previewNativeTask, replayNativeTaskDemo, synthesizeNativeTask, validateNativeTaskRelation, type Json } from "./native-task-domain.js";
export class NativeTaskProcessError extends Data.TaggedError("NativeTaskProcessError")<{
    readonly detail: string;
}> {
}
const fail = (detail: string) => new NativeTaskProcessError({ detail });
const parse = (bytes: Uint8Array): Effect.Effect<Json, NativeTaskProcessError> => { const decoded = decodeNativeTaskJson(bytes); return Either.isLeft(decoded) ? Effect.fail(fail("malformed JSON")) : Effect.succeed(decoded.right as Json); };
const render = (value: Json): string => `${renderNativeTaskJson(value, "pretty")}\n`;
export const nativeTaskProgram = (argv: ReadonlyArray<string>): Effect.Effect<ProcessReply, NativeTaskProcessError, NativeTaskIo> => Effect.gen(function* () {
    const io = yield* NativeTaskIo;
    if (argv.includes("--help") || argv.includes("-h")) return {stdout: "usage: hswm-task {synthesize,preview,probe,demo,validate} INPUT [--output FILE] [--resume-from FILE]\nLocal conditional proposals; no execution or admission.\n", exitCode: 0};
    const [command, path, ...rest] = argv;
    if ((command !== "synthesize" && command !== "validate" && command !== "preview" && command !== "probe" && command !== "demo") || path === undefined)
        return yield* Effect.fail(fail("usage: hswm-task-native <synthesize|preview|probe|demo|validate> INPUT.json [--output FILE] [--resume-from FILE]"));
    let output: string | undefined;
    let resume: string | undefined;
    for (let index = 0; index < rest.length; index += 2) {
        const flag = rest[index], value = rest[index + 1];
        if (value === undefined || (flag !== "--output" && flag !== "--resume-from") || (flag === "--output" ? output !== undefined : resume !== undefined))
            return yield* Effect.fail(fail("invalid CLI options"));
        if (flag === "--output")
            output = value;
        else
            resume = value;
    }
    if (resume !== undefined && command !== "synthesize")
        return yield* Effect.fail(fail("--resume-from only applies to synthesize"));
    const raw = yield* io.read(path).pipe(Effect.mapError((error) => fail(error.detail)));
    let request = yield* parse(raw);
    if (resume !== undefined) {
        if (!taskJsonRecord(request) || Object.hasOwn(request, "resume_cursor"))
            return yield* Effect.fail(fail("resume cursor must have exactly one source"));
        const requestObject = request as {
            readonly [key: string]: Json;
        };
        const prior = yield* io.read(resume).pipe(Effect.mapError((error) => fail(error.detail)));
        const previous = yield* parse(prior);
        const previousObject = previous as {
            readonly [key: string]: Json;
        };
        if (!taskJsonRecord(previous) || !Object.hasOwn(previous, "resume_cursor") || previousObject["resume_cursor"] === null)
            return yield* Effect.fail(fail("prior result has no continuation"));
        request = { ...requestObject, resume_cursor: previousObject["resume_cursor"]! } as Json;
    }
    const result = command === "synthesize" ? synthesizeNativeTask(request) : command === "preview" ? previewNativeTask(request) : command === "probe" ? probeNativeTask(request) : command === "demo" ? replayNativeTaskDemo(request) : validateNativeTaskRelation(request);
    if (Either.isLeft(result))
        return yield* Effect.fail(fail(result.left.detail));
    const text = render(result.right);
    if (output !== undefined)
        yield* io.write(output, text).pipe(Effect.mapError((error) => fail(error.detail)));
    return { stdout: output === undefined ? text : "", exitCode: 0 };
});
export const runNativeTaskProcess = (argv: readonly string[]) => nativeTaskProgram(argv).pipe(Effect.provide(NodeNativeTaskIoLive));
export const describeNativeTaskProcessError = (error: NativeTaskProcessError): string => JSON.stringify({ status: "REJECTED", reason: error.detail });
if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href)
    process.exitCode = await runArgvProcessMain({ program: runNativeTaskProcess, describeFailure: describeNativeTaskProcessError }, process.argv.slice(2));
