/** Scoped private copy of verified P1 artifacts; SDK code only sees this copy. */
import { createHash } from "node:crypto";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { Data, Effect, Scope } from "effect";
import { PosixFileSystem } from "./effect-posix-filesystem.js";
export class NativeP1ArtifactSnapshotError extends Data.TaggedError("NativeP1ArtifactSnapshotError")<{
    readonly detail: string;
}> {
}
export interface NativeP1ArtifactSnapshot {
    readonly directory: string;
}
const fail = (detail: string) => new NativeP1ArtifactSnapshotError({ detail });
const local = <A>(work: () => Promise<A>, detail: string): Effect.Effect<A, NativeP1ArtifactSnapshotError> => Effect.tryPromise({ try: work, catch: e => fail(e instanceof Error ? `${detail}: ${e.message}` : detail) });
export const captureNativeP1ArtifactSnapshot = (sourceDirectory: string, expected: Readonly<Record<string, string>>): Effect.Effect<NativeP1ArtifactSnapshot, NativeP1ArtifactSnapshotError, Scope.Scope | PosixFileSystem> => Effect.gen(function* () { const fs = yield* PosixFileSystem, entries = Object.entries(expected); if (entries.length === 0 || entries.some(([path, hash]) => !/^([A-Za-z0-9._-]+\/)*[A-Za-z0-9._-]+$/.test(path) || path.split("/").some(part => part === "." || part === "..") || !/^[0-9a-f]{64}$/.test(hash)))
    return yield* Effect.fail(fail("invalid P1 artifact manifest")); const captured: readonly (readonly [
    string,
    Uint8Array
])[] = yield* Effect.forEach(entries, ([relative, digest]) => fs.readRegularBounded(join(sourceDirectory, relative), { maximumBytes: 128 * 1024 * 1024, minimumBytes: 1, operation: `capture P1 artifact ${relative}` }).pipe(Effect.mapError(e => fail(e.detail)), Effect.flatMap(read => createHash("sha256").update(read.bytes).digest("hex") === digest ? Effect.succeed(Object.freeze([relative, read.bytes] as const)) : Effect.fail(fail(`P1 artifact digest mismatch: ${relative}`)))), { concurrency: 1 }); const directory = yield* local(() => mkdtemp(join(tmpdir(), "hswm-p1-onnx-")), "cannot create P1 snapshot"); yield* Effect.addFinalizer(() => Effect.promise(() => rm(directory, { recursive: true, force: true })).pipe(Effect.orDie)); for (const [relative, bytes] of captured) {
    const parent = dirname(relative);
    if (parent !== ".")
        yield* fs.makeDirectory(join(directory, parent), { mode: 0o700, recursive: true, operation: "create P1 snapshot directory" }).pipe(Effect.mapError(e => fail(e.detail)));
    yield* fs.writeExclusive(join(directory, relative), bytes, { mode: 0o400, sync: true, operation: "write captured P1 artifact" }).pipe(Effect.mapError(e => fail(e.detail)));
} return Object.freeze({ directory }); });
