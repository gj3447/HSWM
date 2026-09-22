/** Independent pinned RDF/JS engines, confined to a fresh local dataset per operation. */
import { Context, Effect, Either, Layer } from "effect";
import { Parser, Store, DataFactory } from "n3";
import type { Term } from "@rdfjs/types";
import { loadKgVendorEngines } from "./native-kg-vendor.js";
import { KgBundleError, KG_CLAIM_CEILING, kgCanonicalJson, kgSha256, type KgBundleProjection } from "./native-kg-bundle-domain.js";
export type KgTerm = Readonly<Record<string, string>>;
export type KgQueryResult = boolean | readonly Readonly<Record<string, KgTerm | null>>[];
export interface KgShaclResult {
    readonly conforms: boolean;
    readonly results: readonly Readonly<Record<string, unknown>>[];
    readonly claim_ceiling: string;
    readonly engine: string;
    readonly profile: string;
}
const failure = (detail: string): KgBundleError => new KgBundleError({ detail });
const attempt = <A>(operation: () => A, detail: string): Effect.Effect<A, KgBundleError> => Effect.try({ try: operation, catch: () => failure(detail) });
const promised = <A>(operation: () => Promise<A>, detail: string): Effect.Effect<A, KgBundleError> => Effect.tryPromise({ try: operation, catch: () => failure(detail) });
const term = (value: Term): KgTerm => value.termType === "NamedNode" ? { kind: "iri", value: value.value } : value.termType === "BlankNode" ? { kind: "blank_node", value: value.value } : value.termType === "Literal" ? { kind: "literal", value: value.value, ...(value.language ? { language: value.language } : value.datatype.value === "http://www.w3.org/2001/XMLSchema#string" ? {} : { datatype: value.datatype.value }) } : { kind: "unsupported", value: value.value };
const optionalTerm = (value: Term | null | undefined): KgTerm | null => value === null || value === undefined ? null : term(value);
/** Blank comments, quoted strings and IRIs before checking forbidden operations. */
const sparqlCode = (query: string): string => {
    const result: string[] = [];
    for (let i = 0; i < query.length;) {
        const c = query[i];
        if (c === "#") {
            const end = query.indexOf("\n", i);
            i = end < 0 ? query.length : end;
            result.push(" ");
            continue;
        }
        if (c === "<") {
            const match = /^<[^\s<>]*>/.exec(query.slice(i));
            if (match !== null) {
                i += match[0].length;
                result.push(" ");
                continue;
            }
        }
        if (c === "'" || c === '"') {
            const delimiter = query.startsWith(c.repeat(3), i) ? c.repeat(3) : c;
            i += delimiter.length;
            while (i < query.length) {
                if (query[i] === "\\") {
                    i += 2;
                    continue;
                }
                if (query.startsWith(delimiter, i)) {
                    i += delimiter.length;
                    break;
                }
                i += 1;
            }
            result.push(" ");
            continue;
        }
        result.push(c ?? "");
        i += 1;
    }
    return result.join("");
};
export const validateKgQuery = (query: string): Either.Either<"SELECT" | "ASK", KgBundleError> => {
    const head = /^\s*(?:(?:#.*\n)|(?:BASE\s+<[^>]*>\s*)|(?:PREFIX\s+[^\s:]*:\s*<[^>]*>\s*))*(SELECT|ASK)\b/i.exec(query);
    return query.length > 65536 || head === null || /\b(?:SERVICE|FROM|LOAD|CLEAR|CREATE|DROP|COPY|MOVE|ADD|WITH|USING|INSERT|DELETE)\b/i.test(sparqlCode(query))
        ? Either.left(failure("only bounded local SELECT/ASK without SERVICE, datasets or updates is allowed"))
        : Either.right(head[1]?.toUpperCase() as "SELECT" | "ASK");
};
const localUnion = (projection: KgBundleProjection): Effect.Effect<Store, KgBundleError> => Effect.gen(function* () {
    const dataset = projection.descriptor["dataset"];
    if (dataset === null || typeof dataset !== "object" || !("sha256" in dataset) || !("byteLength" in dataset) || dataset.sha256 !== kgSha256(projection.nquads) || dataset.byteLength !== projection.nquads.byteLength)
        return yield* Effect.fail(failure("projection byte binding changed"));
    const quads = yield* attempt(() => new Parser({ format: "N-Quads" }).parse(new TextDecoder("utf-8", { fatal: true }).decode(projection.nquads)), "invalid UTF-8 RDF 1.1 N-Quads");
    if (quads.some(q => [q.subject, q.predicate, q.object, q.graph].some(t => !["NamedNode", "Literal", "DefaultGraph"].includes(t.termType))))
        return yield* Effect.fail(failure("blank nodes and RDF-star are outside the KG data profile"));
    return new Store(quads.map(q => DataFactory.quad(q.subject, q.predicate, q.object)));
});
export const queryKgBundle = (projection: KgBundleProjection, query: string): Effect.Effect<KgQueryResult, KgBundleError> => Effect.gen(function* () {
    yield* validateKgQuery(query);
    const union = yield* localUnion(projection);
    const { QueryEngine } = yield* loadKgVendorEngines;
    const engine = yield* attempt(() => new QueryEngine(), "SPARQL engine initialization failed");
    const result = yield* promised(() => engine.query(query, { sources: [union], fetch: () => Promise.reject(failure("network is forbidden")) }), "local SPARQL parsing/evaluation failed");
    if (result.resultType === "boolean")
        return yield* promised(() => result.execute(), "ASK execution failed");
    if (result.resultType !== "bindings")
        return yield* Effect.fail(failure("query engine returned a non-read-only result"));
    const metadata = yield* promised(() => result.metadata(), "SELECT metadata failed");
    const bindings = yield* promised(() => result.execute().then(stream => stream.toArray()), "SELECT execution failed");
    const rows = bindings.map(binding => Object.fromEntries(metadata.variables.map(v => { const value = binding.get(v); return [v.value, value === undefined ? null : term(value)]; })));
    return rows.sort((a, b) => Buffer.compare(Buffer.from(kgCanonicalJson(a)), Buffer.from(kgCanonicalJson(b))));
});
export const validateKgShacl = (projection: KgBundleProjection, shapes: Uint8Array): Effect.Effect<KgShaclResult, KgBundleError> => Effect.gen(function* () {
    if (shapes.byteLength === 0 || shapes.byteLength > 16 * 1024 * 1024)
        return yield* Effect.fail(failure("SHACL shape bytes exceed the nonempty bounded contract"));
    const union = yield* localUnion(projection);
    const { SHACLValidator } = yield* loadKgVendorEngines;
    const shapeQuads = yield* attempt(() => new Parser({ format: "Turtle" }).parse(new TextDecoder("utf-8", { fatal: true }).decode(shapes)), "invalid Turtle shape graph");
    const sh = "http://www.w3.org/ns/shacl#";
    const forbidden = ["sparql", "js", "jsFunctionName", "jsLibrary", "select", "ask", "rule", "SPARQLConstraint", "SPARQLConstraintComponent", "JSConstraint", "SPARQLTarget", "SPARQLTargetType"].map(x => sh + x);
    if (shapeQuads.some(q => forbidden.includes(q.predicate.value) || forbidden.includes(q.object.value) || q.predicate.value === "http://www.w3.org/2002/07/owl#imports"))
        return yield* Effect.fail(failure("only local SHACL Core is supported; extensions and imports are refused"));
    const validator = yield* attempt(() => new SHACLValidator(new Store(shapeQuads), { importGraph: () => Promise.reject(failure("shape imports forbidden")) }), "SHACL engine initialization failed");
    const report = yield* promised(() => validator.validate(union), "SHACL Core validation failed");
    const results = report.results.map(r => ({ focusNode: term(r.focusNode), path: optionalTerm(r.path), severity: term(r.severity), sourceConstraintComponent: term(r.sourceConstraintComponent), sourceShape: term(r.sourceShape), messages: r.message.map(term) }));
    return { conforms: report.conforms, results, claim_ceiling: KG_CLAIM_CEILING, engine: "rdf-validate-shacl@0.6.5", profile: "SHACL_1_0_CORE_NO_IMPORTS_NO_EXTENSIONS" };
});
export class NativeKgStandards extends Context.Tag("@hswm/NativeKgStandards")<NativeKgStandards, {
    readonly query: typeof queryKgBundle;
    readonly validateShacl: typeof validateKgShacl;
}>() {
}
export const NativeKgStandardsLive = Layer.succeed(NativeKgStandards, { query: queryKgBundle, validateShacl: validateKgShacl });
