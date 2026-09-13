/** Execute the bounded, pinned RDF 1.1 N-Quads syntax profile. */
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { isAbsolute, relative, resolve, sep } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { Data, Effect, Either } from "effect";
import { Parser, type Quad } from "n3";
import { PosixFileSystem } from "./effect-posix-filesystem.js";
const RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type";
const MF_ACTION = "http://www.w3.org/2001/sw/DataAccess/tests/test-manifest#action";
const RDFT_APPROVAL = "http://www.w3.org/ns/rdftest#approval";
const RDFT_APPROVED = "http://www.w3.org/ns/rdftest#Approved";
const POSITIVE = "http://www.w3.org/ns/rdftest#TestNQuadsPositiveSyntax";
const NEGATIVE = "http://www.w3.org/ns/rdftest#TestNQuadsNegativeSyntax";
const PROFILE = "native-nquads-inspection-unqualified";
const MAXIMUM_MANIFEST_BYTES = 4 * 1024 * 1024;
const MAXIMUM_ACTION_BYTES = 4 * 1024 * 1024;
type Expected = "ACCEPT" | "REJECT";
export interface NativeNQuadsRecord {
    readonly id: string;
    readonly action: string;
    readonly expected: Expected;
}
export interface NativeNQuadsSuiteResult {
    readonly schema_version: "hswm-native-graph-standards-successor-result/v1";
    readonly profile: typeof PROFILE;
    readonly status: "PASS" | "FAIL";
    readonly manifest_sha256: string;
    readonly adapter: Readonly<{
        readonly package: "n3";
        readonly version: string;
    }>;
    readonly runtime: Readonly<{
        readonly node: string;
    }>;
    readonly counts: Readonly<{
        readonly positive: number;
        readonly negative: number;
        readonly total: number;
        readonly passed: number;
        readonly failed: number;
    }>;
    readonly failures: readonly Readonly<{
        readonly id: string;
        readonly expected: Expected;
        readonly observed: Expected;
    }>[];
}
export class NativeNQuadsSuiteError extends Data.TaggedError("NativeNQuadsSuiteError")<{
    readonly detail: string;
}> {
}
const failure = (detail: string) => new NativeNQuadsSuiteError({ detail });
const sha256 = (bytes: Uint8Array): string => createHash("sha256").update(bytes).digest("hex");
const n3Version = (createRequire(import.meta.url)("n3/package.json") as {
    readonly version: string;
}).version;
const decodeUtf8 = (bytes: Uint8Array, label: string): Either.Either<string, NativeNQuadsSuiteError> => Either.try({ try: () => new TextDecoder("utf-8", { fatal: true }).decode(bytes), catch: () => failure(`${label} is not valid UTF-8`) });
/** Pure manifest discovery. The Effect shell owns all path resolution and reads. */
export const discoverApprovedNQuadsRecords = (manifest: string, manifestUrl: string): Either.Either<readonly NativeNQuadsRecord[], NativeNQuadsSuiteError> => Either.gen(function* () {
    const quads = yield* Either.try({ try: () => new Parser({ baseIRI: manifestUrl, format: "text/turtle" }).parse(manifest), catch: () => failure("manifest cannot be parsed") });
    const values = (subject: string, predicate: string): readonly Quad[] => quads.filter(quad => quad.subject.value === subject && quad.predicate.value === predicate);
    const subjects = [...new Set(quads.filter(quad => quad.predicate.value === RDF_TYPE && (quad.object.value === POSITIVE || quad.object.value === NEGATIVE)).map(quad => quad.subject.value))].sort((left, right) => left.localeCompare(right));
    const records: NativeNQuadsRecord[] = [];
    for (const id of subjects) {
        const types = values(id, RDF_TYPE).filter(quad => quad.object.value === POSITIVE || quad.object.value === NEGATIVE);
        if (types.length !== 1)
            return yield* Either.left(failure(`manifest test needs exactly one N-Quads syntax type: ${id}`));
        const approvals = [...new Set(values(id, RDFT_APPROVAL).map(quad => quad.object.value))];
        if (!approvals.includes(RDFT_APPROVED))
            continue;
        if (approvals.length !== 1)
            return yield* Either.left(failure(`approved manifest test has conflicting approval values: ${id}`));
        const actions = values(id, MF_ACTION);
        if (actions.length !== 1 || actions[0]!.object.termType !== "NamedNode")
            return yield* Either.left(failure(`manifest test needs exactly one local action: ${id}`));
        if (!actions[0]!.object.value.startsWith("file:"))
            return yield* Either.left(failure(`manifest action is not a local file: ${id}`));
        records.push(Object.freeze({ id, action: actions[0]!.object.value, expected: types[0]!.object.value === POSITIVE ? "ACCEPT" : "REJECT" }));
    }
    if (records.length === 0)
        return yield* Either.left(failure("official approved N-Quads syntax test set is empty"));
    return Object.freeze(records);
});
const contained = (root: string, candidate: string): boolean => { const path = relative(root, candidate); return path !== "" && path !== ".." && !path.startsWith(`..${sep}`) && !isAbsolute(path); };
const assertBoundHash = (root: string, path: string, bytes: Uint8Array, expected: Readonly<Record<string, string>> | undefined, label: string): Effect.Effect<void, NativeNQuadsSuiteError> => {
    if (expected === undefined)
        return Effect.void;
    const hash = expected[relative(root, path).split(sep).join("/")];
    return hash === undefined ? Effect.fail(failure(`pinned suite hash is missing for ${label}`)) : hash === sha256(bytes) ? Effect.void : Effect.fail(failure(`pinned suite hash drift for ${label}`));
};
export const runNativeRdf11NQuadsSuite = (suiteRoot: string, expectedFileSha256?: Readonly<Record<string, string>>): Effect.Effect<NativeNQuadsSuiteResult, NativeNQuadsSuiteError, PosixFileSystem> => Effect.gen(function* () {
    const fs = yield* PosixFileSystem;
    const root = yield* fs.realpath(suiteRoot, "N-Quads suite root").pipe(Effect.mapError(error => failure(`suite root is unavailable: ${error.detail}`)));
    const manifestCanonical = yield* fs.realpath(resolve(root, "manifest.ttl"), "N-Quads manifest").pipe(Effect.mapError(error => failure(`manifest is unavailable: ${error.detail}`)));
    if (!contained(root, manifestCanonical))
        return yield* Effect.fail(failure("manifest escapes suite root"));
    const manifestBytes = (yield* fs.readRegularBounded(manifestCanonical, { maximumBytes: MAXIMUM_MANIFEST_BYTES, minimumBytes: 1, operation: "N-Quads manifest" }).pipe(Effect.mapError(error => failure(`manifest cannot be read: ${error.detail}`)))).bytes;
    yield* assertBoundHash(root, manifestCanonical, manifestBytes, expectedFileSha256, "manifest");
    const manifest = decodeUtf8(manifestBytes, "manifest");
    if (Either.isLeft(manifest))
        return yield* Effect.fail(manifest.left);
    const records = discoverApprovedNQuadsRecords(manifest.right, pathToFileURL(manifestCanonical).href);
    if (Either.isLeft(records))
        return yield* Effect.fail(records.left);
    const failures: Array<Readonly<{
        readonly id: string;
        readonly expected: Expected;
        readonly observed: Expected;
    }>> = [];
    for (const record of records.right) {
        const actionPath = yield* Effect.try({ try: () => fileURLToPath(record.action), catch: () => failure(`manifest action is not a local file: ${record.id}`) });
        const actionCanonical = yield* fs.realpath(actionPath, `N-Quads action ${record.id}`).pipe(Effect.mapError(error => failure(`test action ${record.id} is unavailable: ${error.detail}`)));
        if (!contained(root, actionCanonical))
            return yield* Effect.fail(failure(`test action ${record.id} escapes suite root`));
        const bytes = (yield* fs.readRegularBounded(actionCanonical, { maximumBytes: MAXIMUM_ACTION_BYTES, operation: `N-Quads action ${record.id}` }).pipe(Effect.mapError(error => failure(`test action ${record.id} cannot be read: ${error.detail}`)))).bytes;
        yield* assertBoundHash(root, actionCanonical, bytes, expectedFileSha256, `action ${record.id}`);
        const text = decodeUtf8(bytes, `test action ${record.id}`);
        if (Either.isLeft(text))
            return yield* Effect.fail(text.left);
        const observed: Expected = Either.isRight(Either.try({ try: () => new Parser({ format: "N-Quads" }).parse(text.right), catch: () => failure("N-Quads parser rejected input") })) ? "ACCEPT" : "REJECT";
        if (observed !== record.expected)
            failures.push(Object.freeze({ id: record.id, expected: record.expected, observed }));
    }
    const positive = records.right.filter(record => record.expected === "ACCEPT").length, negative = records.right.length - positive;
    return Object.freeze({ schema_version: "hswm-native-graph-standards-successor-result/v1", profile: PROFILE, status: failures.length === 0 ? "PASS" : "FAIL", manifest_sha256: sha256(manifestBytes), adapter: Object.freeze({ package: "n3", version: n3Version }), runtime: Object.freeze({ node: process.version }), counts: Object.freeze({ positive, negative, total: records.right.length, passed: records.right.length - failures.length, failed: failures.length }), failures: Object.freeze(failures) });
});
