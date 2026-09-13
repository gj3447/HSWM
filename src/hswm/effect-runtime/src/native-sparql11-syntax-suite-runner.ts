/** Purely syntax-scoped execution of the W3C SPARQL 1.1 syntax-query manifest. */
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { relative, resolve, sep, isAbsolute } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { Data, Effect, Either } from "effect";
import { Parser as RdfParser } from "n3";
import { Parser as SparqlParser } from "@traqula/parser-sparql-1-2";
import { PosixFileSystem } from "./effect-posix-filesystem.js";
const RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", ACTION = "http://www.w3.org/2001/sw/DataAccess/tests/test-manifest#action", POS = "http://www.w3.org/2001/sw/DataAccess/tests/test-manifest#PositiveSyntaxTest11", NEG = "http://www.w3.org/2001/sw/DataAccess/tests/test-manifest#NegativeSyntaxTest11";
export class NativeSparqlSyntaxError extends Data.TaggedError("NativeSparqlSyntaxError")<{
    readonly detail: string;
}> {
}
const fail = (detail: string) => new NativeSparqlSyntaxError({ detail }), decode = (b: Uint8Array, l: string) => Either.try({ try: () => new TextDecoder("utf-8", { fatal: true }).decode(b), catch: () => fail(`${l} is not valid UTF-8`) });
const traqulaVersion = (createRequire(import.meta.url)("@traqula/parser-sparql-1-2/package.json") as {
    readonly version: string;
}).version;
const inside = (root: string, path: string) => { const r = relative(root, path); return r !== "" && r !== ".." && !r.startsWith(`..${sep}`) && !isAbsolute(r); };
const assertBoundHash = (root: string, path: string, bytes: Uint8Array, expected: Readonly<Record<string, string>> | undefined, label: string): Effect.Effect<void, NativeSparqlSyntaxError> => { if (expected === undefined)
    return Effect.void; const hash = expected[relative(root, path).split(sep).join("/")], actual = createHash("sha256").update(bytes).digest("hex"); return hash === undefined ? Effect.fail(fail(`pinned suite hash is missing for ${label}`)) : hash === actual ? Effect.void : Effect.fail(fail(`pinned suite hash drift for ${label}`)); };
export const runNativeSparql11SyntaxSuite = (suiteRoot: string, expectedFileSha256?: Readonly<Record<string, string>>) => Effect.gen(function* () { const fs = yield* PosixFileSystem, root = yield* fs.realpath(suiteRoot, "SPARQL suite root").pipe(Effect.mapError(e => fail(e.detail))), manifestPath = yield* fs.realpath(resolve(root, "manifest.ttl"), "SPARQL manifest").pipe(Effect.mapError(e => fail(e.detail))); if (!inside(root, manifestPath))
    return yield* Effect.fail(fail("manifest escapes suite root")); const bytes = (yield* fs.readRegularBounded(manifestPath, { maximumBytes: 4 * 1024 * 1024, minimumBytes: 1, operation: "SPARQL manifest" }).pipe(Effect.mapError(e => fail(e.detail)))).bytes; yield* assertBoundHash(root, manifestPath, bytes, expectedFileSha256, "manifest"); const text = decode(bytes, "manifest"); if (Either.isLeft(text))
    return yield* Effect.fail(text.left); const quads = yield* Effect.try({ try: () => new RdfParser({ baseIRI: pathToFileURL(manifestPath).href, format: "text/turtle" }).parse(text.right), catch: () => fail("manifest cannot be parsed") }); const entries = quads.filter(q => q.predicate.value === RDF && (q.object.value === POS || q.object.value === NEG)).map(q => ({ id: q.subject.value, expected: q.object.value === POS ? "ACCEPT" as const : "REJECT" as const, action: quads.filter(x => x.subject.equals(q.subject) && x.predicate.value === ACTION) })).sort((a, b) => a.id.localeCompare(b.id)); if (entries.length === 0)
    return yield* Effect.fail(fail("official SPARQL syntax set is empty")); const failures: {
    id: string;
    expected: "ACCEPT" | "REJECT";
    observed: "ACCEPT" | "REJECT";
}[] = []; for (const e of entries) {
    if (e.action.length !== 1 || e.action[0]!.object.termType !== "NamedNode")
        return yield* Effect.fail(fail(`manifest action drift: ${e.id}`));
    const path = yield* Effect.try({ try: () => fileURLToPath(e.action[0]!.object.value), catch: () => fail(`action is not local: ${e.id}`) }), canonical = yield* fs.realpath(path, `SPARQL action ${e.id}`).pipe(Effect.mapError(x => fail(x.detail)));
    if (!inside(root, canonical))
        return yield* Effect.fail(fail(`action escapes suite root: ${e.id}`));
    const input = (yield* fs.readRegularBounded(canonical, { maximumBytes: 4 * 1024 * 1024, operation: `SPARQL action ${e.id}` }).pipe(Effect.mapError(x => fail(x.detail)))).bytes;
    yield* assertBoundHash(root, canonical, input, expectedFileSha256, `action ${e.id}`);
    const source = decode(input, `SPARQL action ${e.id}`);
    if (Either.isLeft(source))
        return yield* Effect.fail(source.left);
    const observed = Either.isRight(Either.try({ try: () => new SparqlParser().parse(source.right, { baseIRI: e.action[0]!.object.value }), catch: () => fail("parser rejected input") })) ? "ACCEPT" as const : "REJECT" as const;
    if (observed !== e.expected)
        failures.push({ id: e.id, expected: e.expected, observed });
} const positive = entries.filter(e => e.expected === "ACCEPT").length; return { schema_version: "hswm-native-sparql11-syntax-result/v1", profile: "native-sparql11-syntax-inspection-unqualified", status: failures.length === 0 ? "PASS" as const : "FAIL" as const, manifest_sha256: createHash("sha256").update(bytes).digest("hex"), adapter: { package: "@traqula/parser-sparql-1-2", version: traqulaVersion }, runtime: { node: process.version }, counts: { positive, negative: entries.length - positive, total: entries.length, passed: entries.length - failures.length, failed: failures.length }, failures: Object.freeze(failures) }; });
