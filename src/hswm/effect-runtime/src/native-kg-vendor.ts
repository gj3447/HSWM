/** Narrow runtime boundary for pinned vendors with incomplete upstream .d.ts.
 * The HSWM compiler retains strict checking; vendor internals are not its types.
 * Contracts below are exercised by the pinned conformance and projection tests.
 */
import { Effect } from "effect";
import type { DatasetCore, Term, Variable } from "@rdfjs/types";
import { KgBundleError } from "./native-kg-bundle-domain.js";
interface Binding {
    readonly get: (variable: Variable) => Term | undefined;
}
type QueryResult = {
    readonly resultType: "boolean";
    readonly execute: () => Promise<boolean>;
} | {
    readonly resultType: "bindings";
    readonly metadata: () => Promise<{
        readonly variables: readonly Variable[];
    }>;
    readonly execute: () => Promise<{
        readonly toArray: () => Promise<readonly Binding[]>;
    }>;
};
interface NativeQueryEngine {
    readonly query: (query: string, context: {
        readonly sources: readonly DatasetCore[];
        readonly fetch: () => Promise<never>;
    }) => Promise<QueryResult>;
}
interface ValidationResult {
    readonly focusNode: Term;
    readonly path?: Term;
    readonly severity: Term;
    readonly sourceConstraintComponent: Term;
    readonly sourceShape: Term;
    readonly message: readonly Term[];
}
interface NativeShaclValidator {
    readonly validate: (data: DatasetCore) => Promise<{
        readonly conforms: boolean;
        readonly results: readonly ValidationResult[];
        readonly dataset: DatasetCore;
        readonly term: Term;
    }>;
}
export interface KgVendorEngines {
    readonly QueryEngine: new () => NativeQueryEngine;
    readonly SHACLValidator: new (shapes: DatasetCore, options: {
        readonly importGraph: () => Promise<never>;
    }) => NativeShaclValidator;
    readonly canonize: (input: string, options: { readonly algorithm: "RDFC-1.0"; readonly inputFormat: "application/n-quads"; readonly format: "application/n-quads"; readonly maxWorkFactor?: number; readonly signal?: AbortSignal }) => Promise<string>;
}
const queryPackage: string = "@comunica/query-sparql-rdfjs";
const shaclPackage: string = "rdf-validate-shacl";
const canonPackage: string = "rdf-canonize";
const moduleMember = (module: unknown, key: string): unknown => typeof module === "object" && module !== null && key in module ? (module as Readonly<Record<string, unknown>>)[key] : undefined;
export const loadKgVendorEngines: Effect.Effect<KgVendorEngines, KgBundleError> = Effect.gen(function* () {
    const query: unknown = yield* Effect.tryPromise({ try: () => import(queryPackage), catch: () => new KgBundleError({ detail: "pinned local SPARQL package load failed" }) });
    const shacl: unknown = yield* Effect.tryPromise({ try: () => import(shaclPackage), catch: () => new KgBundleError({ detail: "pinned local SHACL package load failed" }) });
    const canon: unknown = yield* Effect.tryPromise({ try: () => import(canonPackage), catch: () => new KgBundleError({ detail: "pinned local RDF canonicalizer load failed" }) });
    const QueryEngine = moduleMember(query, "QueryEngine"), SHACLValidator = moduleMember(shacl, "default");
    const canonize = moduleMember(canon, "canonize") ?? moduleMember(moduleMember(canon, "default"), "canonize");
    if (typeof QueryEngine !== "function" || typeof SHACLValidator !== "function" || typeof canonize !== "function")
        return yield* Effect.fail(new KgBundleError({ detail: "pinned vendor constructor contract changed" }));
    return { QueryEngine: QueryEngine as KgVendorEngines["QueryEngine"], SHACLValidator: SHACLValidator as KgVendorEngines["SHACLValidator"], canonize: canonize as KgVendorEngines["canonize"] };
});
