/** Narrow Effect I/O shell for the native task CLI; proposal files are not admission. */
import { writeFile } from "node:fs/promises";
import { Context, Data, Effect, Layer } from "effect";
import { NodePosixFileSystemLive, PosixFileSystem } from "./effect-posix-filesystem.js";
export class NativeTaskIoError extends Data.TaggedError("NativeTaskIoError")<{
    readonly detail: string;
}> {
}
const fail = (detail: string) => new NativeTaskIoError({ detail });
const readNativeTaskInput = (path: string, maximumBytes = 1048576): Effect.Effect<Uint8Array, NativeTaskIoError> => path === "-" ? Effect.async((resume) => { const chunks: Buffer[] = []; let size = 0; const onData = (chunk: Buffer) => { size += chunk.byteLength; if (size > maximumBytes) {
    process.stdin.pause();
    resume(Effect.fail(fail("input exceeds 1 MiB")));
}
else
    chunks.push(chunk); }; const end = () => resume(Effect.succeed(Uint8Array.from(Buffer.concat(chunks)))); const error = () => resume(Effect.fail(fail("input read failure"))); process.stdin.on("data", onData); process.stdin.once("end", end); process.stdin.once("error", error); return Effect.sync(() => { process.stdin.off("data", onData); process.stdin.off("end", end); process.stdin.off("error", error); }); }) : Effect.gen(function* () {
    const fs = yield* PosixFileSystem;
    const target = yield* fs.realpath(path, "task input");
    const input = yield* fs.readRegularBounded(target, {maximumBytes, operation: "task bounded input"});
    return input.bytes;
}).pipe(Effect.mapError(error => fail(error.code === "BYTE_BOUND_EXCEEDED" ? "input exceeds 1 MiB" : "input read failure")), Effect.provide(NodePosixFileSystemLive));
const writeNativeTaskOutput = (path: string, text: string): Effect.Effect<void, NativeTaskIoError> => Effect.tryPromise({ try: () => writeFile(path, text, { encoding: "utf8" }), catch: () => fail("output write failure") });

export interface NativeTaskIoShape {
  readonly read: (path: string) => Effect.Effect<Uint8Array, NativeTaskIoError>;
  readonly write: (path: string, text: string) => Effect.Effect<void, NativeTaskIoError>;
}
export class NativeTaskIo extends Context.Tag("hswm/NativeTaskIo")<NativeTaskIo, NativeTaskIoShape>() {}
export const NodeNativeTaskIoLive = Layer.succeed(NativeTaskIo, {read: readNativeTaskInput, write: writeNativeTaskOutput});
