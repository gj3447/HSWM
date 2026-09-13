import { join, resolve } from "node:path";
import { parseArgs } from "node:util";
import { Effect } from "effect";
import { PosixFileSystem } from "./effect-posix-filesystem.js";
import { refuse, type ProcessReply } from "./effect-process-main.js";
import { compileKgBundle, type KgBundleSource } from "./native-kg-bundle-domain.js";
import { queryKgBundle, validateKgShacl } from "./native-kg-standards.js";
const usage = "hswm-kg-bundle <project|query|validate> --source ID=PATH [--source ID=PATH] [--profile v1|v2] [--query FILE | --shapes FILE | --output-dir NEW_DIRECTORY]";
export const runNativeKgCli = (argv: readonly string[]) => Effect.gen(function* () {
    const parsed = yield* Effect.try({
        try: () => parseArgs({ args: [...argv], allowPositionals: true, strict: true, options: {
                source: { type: "string", multiple: true }, profile: { type: "string", default: "v2" },
                query: { type: "string" }, shapes: { type: "string" }, "output-dir": { type: "string" }, help: { type: "boolean" }
            } }),
        catch: () => refuse(usage)
    });
    if (parsed.values.help)
        return { stdout: `${usage}\n`, exitCode: 0 } satisfies ProcessReply;
    const command = parsed.positionals[0], profile = parsed.values.profile;
    if (parsed.positionals.length !== 1 || !["project", "query", "validate"].includes(command ?? "") || (profile !== "v1" && profile !== "v2") || parsed.values.source === undefined || parsed.values.source.length === 0 || parsed.values.source.length > 128)
        return yield* Effect.fail(refuse(usage));
    if ((command !== "query" && parsed.values.query !== undefined) || (command !== "validate" && parsed.values.shapes !== undefined) || (command !== "project" && parsed.values["output-dir"] !== undefined))
        return yield* Effect.fail(refuse("option does not apply to this command"));
    const fs = yield* PosixFileSystem;
    const read = (path: string, maximumBytes: number) => fs.readRegularBounded(resolve(path), { maximumBytes, minimumBytes: 1, operation: "native-kg-input" }).pipe(Effect.map(result => result.bytes));
    const sources = yield* Effect.forEach(parsed.values.source, spec => Effect.gen(function* () {
        const split = spec.indexOf("=");
        if (split < 1 || split === spec.length - 1)
            return yield* Effect.fail(refuse("source must be ID=PATH"));
        return { sourceId: spec.slice(0, split), rawBytes: yield* read(spec.slice(split + 1), 16 * 1024 * 1024) } satisfies KgBundleSource;
    }), { concurrency: 1 });
    const projection = yield* compileKgBundle(sources, profile);
    if (command === "query") {
        if (parsed.values.query === undefined)
            return yield* Effect.fail(refuse("query requires --query FILE"));
        const queryBytes = yield* read(parsed.values.query, 65536);
        const query = yield* Effect.try({ try: () => new TextDecoder("utf-8", { fatal: true }).decode(queryBytes), catch: () => refuse("query must be strict UTF-8") });
        const result = yield* queryKgBundle(projection, query);
        return { stdout: `${JSON.stringify(result, null, 2)}\n`, exitCode: 0 };
    }
    if (command === "validate") {
        if (parsed.values.shapes === undefined)
            return yield* Effect.fail(refuse("validate requires --shapes FILE"));
        const result = yield* validateKgShacl(projection, yield* read(parsed.values.shapes, 16 * 1024 * 1024));
        return { stdout: `${JSON.stringify(result, null, 2)}\n`, exitCode: result.conforms ? 0 : 1 };
    }
    const output = parsed.values["output-dir"];
    if (output !== undefined) {
        const path = resolve(output);
        yield* fs.makeDirectory(path, { mode: 0o755, operation: "native-kg-new-projection-directory" });
        for (const [name, bytes] of [["dataset.nq", projection.nquads], ["descriptor.json", Buffer.from(`${JSON.stringify(projection.descriptor, null, 2)}\n`)], ["provenance.jsonld", projection.provO]] as const) {
            yield* fs.writeExclusive(join(path, name), bytes, { mode: 0o644, sync: true, operation: "native-kg-projection-artifact" });
        }
        yield* fs.syncDirectory(path, "native-kg-projection-sync");
    }
    return { stdout: `${JSON.stringify(projection.descriptor, null, 2)}\n`, exitCode: 0 };
}).pipe(Effect.mapError(error => error._tag === "ProcessRefusal" ? error : refuse(error.detail)));
