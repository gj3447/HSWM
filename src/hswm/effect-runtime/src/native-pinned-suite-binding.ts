/** Bind an official-suite runner to the exact files in a pinned Git subtree. */
import { createHash } from "node:crypto";
import { join, relative, resolve, sep } from "node:path";
import { Data, Effect } from "effect";
import { BoundedSubprocess } from "./effect-bounded-subprocess.js";
import { PosixFileSystem } from "./effect-posix-filesystem.js";
const MAXIMUM_FILE_BYTES = 16 * 1024 * 1024;
const decoder = new TextDecoder("utf-8", { fatal: true });
export interface PinnedSuiteSpec {
    readonly commit: string;
    readonly suitePath: string;
    readonly tree: string;
    readonly archiveSha256: string;
}
export interface PinnedSuiteBinding {
    readonly root: string;
    readonly fileSha256: Readonly<Record<string, string>>;
}
export class PinnedSuiteBindingError extends Data.TaggedError("PinnedSuiteBindingError")<{
    readonly detail: string;
}> {
}
const failure = (detail: string): PinnedSuiteBindingError => new PinnedSuiteBindingError({ detail });
const digest = (bytes: Uint8Array): string => createHash("sha256").update(bytes).digest("hex");
const git = (cwd: string, args: readonly string[]) => Effect.gen(function* () {
    const subprocess = yield* BoundedSubprocess;
    const observed = yield* subprocess.observe({
        argv: ["git", "-C", cwd, ...args], cwd,
        environment: { PATH: process.env["PATH"] ?? "", LANG: "C.UTF-8", LC_ALL: "C.UTF-8" },
        timeoutMs: 30000, maximumOutputBytes: MAXIMUM_FILE_BYTES
    }).pipe(Effect.mapError(() => failure("pinned suite Git verification failed")));
    if (observed.exitCode !== 0 || observed.timedOut || observed.outputTruncated || observed.launchError !== null) {
        return yield* Effect.fail(failure("pinned suite Git verification failed"));
    }
    return observed.stdout;
});
const text = (bytes: Uint8Array): Effect.Effect<string, PinnedSuiteBindingError> => Effect.try({ try: () => decoder.decode(bytes), catch: () => failure("pinned suite Git output is not UTF-8") });
const contained = (root: string, child: string): boolean => {
    const path = relative(root, child);
    return path === "" || (path !== ".." && !path.startsWith(`..${sep}`));
};
const collectDiskFiles = (root: string): Effect.Effect<ReadonlySet<string>, PinnedSuiteBindingError, PosixFileSystem> => Effect.gen(function* () {
    const fs = yield* PosixFileSystem;
    const files = new Set<string>();
    const visit = (directory: string): Effect.Effect<void, PinnedSuiteBindingError> => Effect.gen(function* () {
        const identity = yield* fs.identity(directory, "inspect pinned suite directory").pipe(Effect.mapError(error => failure(error.detail)));
        if (identity.kind === "SYMLINK")
            return yield* Effect.fail(failure("pinned suite contains a symbolic-link directory"));
        if (identity.kind !== "DIRECTORY")
            return yield* Effect.fail(failure("pinned suite contains a non-directory path"));
        const entries = yield* fs.listDirectory(directory, "list pinned suite directory").pipe(Effect.mapError(error => failure(error.detail)));
        for (const entry of entries) {
            const path = join(directory, entry.name);
            if (entry.kind === "SYMLINK")
                return yield* Effect.fail(failure("pinned suite contains a symbolic-link path"));
            if (entry.kind === "DIRECTORY") {
                yield* visit(path);
                continue;
            }
            if (entry.kind !== "FILE")
                return yield* Effect.fail(failure("pinned suite contains a non-regular file"));
            const pathFromRoot = relative(root, path).split(sep).join("/");
            files.add(pathFromRoot);
        }
    });
    yield* visit(root);
    return files;
});
/**
 * Resolve the supplied suite directory, require it to be the pinned subtree,
 * and compare every regular on-disk file to `git show COMMIT:path`.
 */
export const bindPinnedSuiteRoot = (suiteRoot: string, spec: PinnedSuiteSpec): Effect.Effect<PinnedSuiteBinding, PinnedSuiteBindingError, PosixFileSystem | BoundedSubprocess> => Effect.gen(function* () {
    const fs = yield* PosixFileSystem;
    const supplied = yield* fs.identity(suiteRoot, "inspect supplied suite root").pipe(Effect.mapError(error => failure(error.detail)));
    if (supplied.kind === "SYMLINK")
        return yield* Effect.fail(failure("supplied suite root must not be a symbolic link"));
    if (supplied.kind !== "DIRECTORY")
        return yield* Effect.fail(failure("supplied suite root must be a directory"));
    const canonicalRoot = yield* fs.realpath(suiteRoot, "resolve supplied suite root").pipe(Effect.mapError(error => failure(error.detail)));
    const repositoryTop = (yield* text(yield* git(canonicalRoot, ["rev-parse", "--show-toplevel"]))).trim();
    const expectedPinnedRoot = resolve(repositoryTop, spec.suitePath);
    const pinnedRoot = yield* fs.realpath(expectedPinnedRoot, "resolve pinned suite root").pipe(Effect.mapError(error => failure(error.detail)));
    if (pinnedRoot !== expectedPinnedRoot || canonicalRoot !== pinnedRoot || !contained(repositoryTop, canonicalRoot))
        return yield* Effect.fail(failure("supplied suite root is not the pinned Git subtree"));
    let selected = repositoryTop;
    for (const segment of spec.suitePath.split("/")) {
        selected = join(selected, segment);
        const identity = yield* fs.identity(selected, "inspect pinned suite path ancestor").pipe(Effect.mapError(error => failure(error.detail)));
        if (identity.kind === "SYMLINK")
            return yield* Effect.fail(failure("pinned suite path contains a symbolic-link ancestor"));
        if (identity.kind !== "DIRECTORY")
            return yield* Effect.fail(failure("pinned suite path contains a non-directory ancestor"));
    }
    if ((yield* text(yield* git(repositoryTop, ["rev-parse", "HEAD"]))).trim() !== spec.commit)
        return yield* Effect.fail(failure("pinned suite commit drift"));
    if ((yield* text(yield* git(repositoryTop, ["rev-parse", `HEAD:${spec.suitePath}`]))).trim() !== spec.tree)
        return yield* Effect.fail(failure("pinned suite tree drift"));
    if (digest(yield* git(repositoryTop, ["archive", "--format=tar", spec.commit, "--", spec.suitePath])) !== spec.archiveSha256)
        return yield* Effect.fail(failure("pinned suite archive drift"));
    const expected = new Set((yield* text(yield* git(repositoryTop, ["ls-tree", "-r", "--name-only", spec.commit, "--", spec.suitePath]))).trim().split("\n").filter(Boolean).map(path => path.slice(spec.suitePath.length + 1)));
    const disk = yield* collectDiskFiles(canonicalRoot);
    if (disk.size !== expected.size || [...disk].some(path => !expected.has(path)))
        return yield* Effect.fail(failure("pinned suite disk files differ from the pinned Git subtree"));
    const fileSha256: Record<string, string> = {};
    for (const path of [...expected].sort((left, right) => left.localeCompare(right))) {
        const diskPath = join(canonicalRoot, ...path.split("/"));
        const bytes = (yield* fs.readRegularBounded(diskPath, { maximumBytes: MAXIMUM_FILE_BYTES, operation: "read pinned suite file" }).pipe(Effect.mapError(error => failure(error.detail)))).bytes;
        const gitBytes = yield* git(repositoryTop, ["show", "--no-textconv", `${spec.commit}:${spec.suitePath}/${path}`]);
        const expectedHash = digest(gitBytes);
        if (digest(bytes) !== expectedHash)
            return yield* Effect.fail(failure("pinned suite file content drift"));
        fileSha256[path] = expectedHash;
    }
    return Object.freeze({ root: canonicalRoot, fileSha256: Object.freeze(fileSha256) });
});
