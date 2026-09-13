/** Pure, source-bound KG exchange compiler. This is never canonical state. */
import { createHash } from "node:crypto";
import { Data, Either, Schema } from "effect";
import { decodeGeneralJsonWithNumberLexemesBytes } from "./general-json-domain.js";
export const KG_VOCAB = "https://hswm.invalid/kg-bundle-rdf/v1/";
export const KG_PROV = "http://www.w3.org/ns/prov#";
export const KG_RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type";
export const KG_XSD = "http://www.w3.org/2001/XMLSchema#";
export const KG_PROFILE = "RDF_1_1_N_QUADS_BLANK_NODE_FREE_DETERMINISTIC_PROFILE";
export const KG_NONCLAIM = "DERIVED_READ_ONLY_KG_BUNDLE_EXCHANGE_NOT_CANONICAL_STATE_NOT_PERMIT_NOT_USER_RATIFICATION_NOT_GATE_PASS_NOT_CAUSAL_CREDIT_NOT_LEARNING_NOT_EFFICACY";
export const KG_CLAIM_CEILING = "KG_BUNDLE_STRUCTURE_AND_BYTE_BINDING_ONLY_NOT_LIVE_KG_STATE_NOT_PROVENANCE_TRUTH_NOT_CANONICAL_AUTHORITY_NOT_PERMIT_NOT_OUTCOME_TRUTH_NOT_CAUSAL_CREDIT_NOT_LEARNING_NOT_EFFICACY";
export class KgBundleError extends Data.TaggedError("KgBundleError")<{
    readonly detail: string;
}> {
}
const fail = (detail: string): Either.Either<never, KgBundleError> => Either.left(new KgBundleError({ detail }));
export const kgSha256 = (bytes: string | Uint8Array): string => createHash("sha256").update(bytes).digest("hex");
const uid = Schema.String.pipe(Schema.pattern(/^sym:[A-Za-z][A-Za-z0-9_]*:[A-Za-z0-9][A-Za-z0-9._-]*$/));
const nonempty = Schema.String.pipe(Schema.minLength(1));
const label = Schema.String.pipe(Schema.pattern(/^[A-Za-z_][A-Za-z0-9_]*$/));
const propertyKey = Schema.String.pipe(Schema.pattern(/^[a-z][a-z0-9_]*$/));
const scalar = Schema.Union(Schema.String, Schema.Boolean, Schema.Number.pipe(Schema.finite()));
const nodeSchema = Schema.Struct({ uid, labels: Schema.Array(label).pipe(Schema.minItems(1)), properties: Schema.Record({ key: propertyKey, value: Schema.Union(scalar, Schema.Array(scalar)) }) });
const anchorSchema = Schema.Struct({ uid, name: nonempty, required_labels: Schema.Array(label).pipe(Schema.minItems(1)) });
const relationSchema = Schema.Struct({ from_uid: uid, to_uid: uid, type: Schema.String.pipe(Schema.pattern(/^[A-Z][A-Z0-9_]*$/)), authority_class: nonempty, scope: nonempty, status: nonempty });
const bundleSchema = Schema.Struct({
    schema_version: nonempty, bundle_uid: uid, status: nonempty, nonclaim: nonempty,
    authority_boundary: Schema.optional(nonempty), source_accessed_on: Schema.optional(nonempty),
    artifact_bindings: Schema.Array(Schema.Struct({ path: Schema.String.pipe(Schema.pattern(/^[A-Za-z0-9_][A-Za-z0-9_./:+-]{0,255}$/)), sha256: Schema.String.pipe(Schema.pattern(/^[0-9a-f]{64}$/)) })).pipe(Schema.minItems(1)),
    expected_counts: Schema.Record({ key: propertyKey, value: Schema.Number.pipe(Schema.int(), Schema.nonNegative()) }),
    anchors: Schema.Array(anchorSchema), nodes: Schema.Array(nodeSchema).pipe(Schema.minItems(1)), relations: Schema.Array(relationSchema)
});
export type KgBundle = typeof bundleSchema.Type;
export interface KgBundleSource {
    readonly sourceId: string;
    readonly rawBytes: Uint8Array;
    readonly sha256?: string;
    readonly byteLength?: number;
}
interface BoundSource {
    readonly sourceId: string;
    readonly sha256: string;
    readonly byteLength: number;
    readonly bundle: KgBundle;
    readonly numberLexemes: Readonly<Record<string, string>>;
}
export interface KgBundleProjection {
    readonly nquads: Uint8Array;
    readonly descriptor: Readonly<Record<string, unknown>>;
    readonly provO: Uint8Array;
}
const unique = (values: readonly string[]): boolean => new Set(values).size === values.length;
const compare = (left: string, right: string): number => Buffer.compare(Buffer.from(left), Buffer.from(right));
/** Python's historical bundle hash uses Unicode code-point key ordering. */
export const kgCanonicalJson = (value: unknown): string => {
    if (Array.isArray(value))
        return `[${value.map(kgCanonicalJson).join(",")}]`;
    if (value !== null && typeof value === "object")
        return `{${Object.entries(value).sort(([a], [b]) => compare(a, b)).map(([key, item]) => `${JSON.stringify(key)}:${kgCanonicalJson(item)}`).join(",")}}`;
    return JSON.stringify(value) ?? "null";
};
const digest = (value: unknown): string => kgSha256(kgCanonicalJson(value));
const roleInventories: Readonly<Record<string, Readonly<Record<string, number>>>> = {
    "hswm-hypergraph-learning-plan/v1": { DESIGN_INTUITION: 4, EVIDENCE_BOUNDARY: 1, LEARNING_ASSERTION: 4, LEARNING_CONCEPT: 20, LEARNING_PLAN_BUNDLE: 1, LEARNING_PLAN_STEP: 6, PLAN_SOURCE: 1, ROLE_PARTICIPATION: 25, USER_DIRECT_REQUEST: 1 },
    "hswm-workshop-c1-c3-concept-projection/v1": { AUTHORED_SCENE: 4, ILLUSTRATIVE_HYPOTHESIS: 3, ILLUSTRATIVE_PROBE: 3, OPEN_MECHANISM_PROBLEM: 2, WORKED_COMPOSITION_QUESTION: 1, WORKED_DESIGN_INSIGHT: 4, WORKED_REVISION_CANDIDATE: 3, WORKED_SCOPE_GUARD: 4, WORKED_SPEC_BUNDLE: 1, WORKED_SPEC_SECTION: 3, WORKED_SPEC_SOURCE: 1 }
};
const semanticError = (bundle: KgBundle): string | undefined => {
    const nodes = new Map(bundle.nodes.map(node => [node.uid, node]));
    const inventory = roleInventories[bundle.schema_version];
    if (inventory !== undefined) {
        const actual = bundle.nodes.reduce<Readonly<Record<string, number>>>((counts, node) => {
            const role = String(node.properties["standard_graph_role"]);
            return { ...counts, [role]: (counts[role] ?? 0) + 1 };
        }, {});
        if (kgCanonicalJson(actual) !== kgCanonicalJson(inventory))
            return "source-revision domain role inventory drift";
    }
    for (const node of bundle.nodes) {
        const p = node.properties;
        if (p["ontology_authority_class_v1"] !== undefined && p["ontology_authority_class_v1"] !== p["authority_class"])
            return `${node.uid}: conflicting authority classes`;
        if (p["standard_graph_role"] === "AUTHORED_SCENE" && p["status"] !== "AUTHORED_ILLUSTRATION_NOT_OBSERVATION")
            return `${node.uid}: authored scene promoted to observation`;
        if (p["current_decision_uid"] !== undefined) {
            const decision = typeof p["current_decision_uid"] === "string" ? nodes.get(p["current_decision_uid"]) : undefined;
            if (p["standard_graph_role"] !== "CLAIM" || decision === undefined || !["DECISION", "USER_PRIMARY_DECISION"].includes(String(decision.properties["standard_graph_role"])) || decision.properties["assesses_claim_uid"] !== node.uid || !bundle.relations.some(r => r.from_uid === node.uid && r.to_uid === decision.uid && r.type === "HAS_CONCEPT"))
                return `${node.uid}: invalid current decision binding`;
        }
        if (p["standard_graph_role"] === "LEARNING_ASSERTION") {
            const participants = bundle.relations.filter(r => r.from_uid === node.uid && r.type === "HAS_PARTICIPATION").map(r => nodes.get(r.to_uid));
            if (participants.some(p => p?.properties["standard_graph_role"] !== "ROLE_PARTICIPATION" || typeof p.properties["ordinal"] !== "number" || !Number.isSafeInteger(p.properties["ordinal"]) || p.properties["ordinal"] < 0) || !unique(participants.map(p => String(p?.properties["ordinal"]))))
                return `${node.uid}: invalid participation ordinals`;
        }
    }
    return undefined;
};
export const decodeKgBundleSource = (source: KgBundleSource, profile: "v1" | "v2" = "v2"): Either.Either<BoundSource, KgBundleError> => Either.gen(function* () {
    if (!/^[A-Za-z][A-Za-z0-9._:-]{0,127}$/.test(source.sourceId) || source.rawBytes.byteLength === 0)
        return yield* fail("invalid source ID or empty bytes");
    const sha256 = kgSha256(source.rawBytes);
    if ((source.sha256 !== undefined && source.sha256 !== sha256) || (source.byteLength !== undefined && source.byteLength !== source.rawBytes.byteLength))
        return yield* fail("source digest or byte length mismatch");
    const decoded = yield* Either.mapLeft(decodeGeneralJsonWithNumberLexemesBytes(source.rawBytes, { maximumBytes: 16 * 1024 * 1024, maximumDepth: 32 }), error => new KgBundleError({ detail: error.detail }));
    const bundle = yield* Either.mapLeft(Schema.decodeUnknownEither(bundleSchema, { onExcessProperty: "error" })(decoded.value), error => new KgBundleError({ detail: String(error) }));
    if (!bundle.bundle_uid.startsWith("sym:AbstractNode:"))
        return yield* fail("bundle UID must be AbstractNode");
    if (!unique(bundle.artifact_bindings.map(b => b.path)) || bundle.artifact_bindings.some(b => b.path.startsWith("/") || b.path.split("/").includes("..")))
        return yield* fail("duplicate or unsafe artifact path");
    const allUids = [...bundle.nodes, ...bundle.anchors].map(n => n.uid);
    if (!unique(allUids))
        return yield* fail("duplicate node or anchor UID");
    const owned = new Set(bundle.nodes.map(n => n.uid)), known = new Set(allUids);
    for (const node of bundle.nodes) {
        if (!unique(node.labels) || typeof node.properties["name"] !== "string" || !node.properties["name"])
            return yield* fail(`${node.uid}: missing name or duplicate labels`);
        if (Object.keys(node.properties).some(k => ["password", "secret", "token", "api_key", "apikey", "private_key", "credential"].includes(k)))
            return yield* fail(`${node.uid}: forbidden property key`);
        for (const key of ["standard_graph_role", "plan_graph_role"]) {
            const role = node.properties[key];
            if (role !== undefined && (typeof role !== "string" || !/^[A-Za-z_][A-Za-z0-9_]*$/.test(role)))
                return yield* fail(`${node.uid}: invalid role`);
        }
    }
    if (!unique(bundle.relations.map(r => kgCanonicalJson([r.from_uid, r.type, r.to_uid]))) || bundle.relations.some(r => !owned.has(r.from_uid) || !known.has(r.to_uid)))
        return yield* fail("duplicate relation or invalid ownership/reference");
    for (const key of ["nodes", "anchors", "relations"] as const)
        if (bundle.expected_counts[key] !== undefined && bundle.expected_counts[key] !== bundle[key].length)
            return yield* fail(`expected_counts.${key} mismatch`);
    const problem = profile === "v2" ? semanticError(bundle) : undefined;
    if (problem !== undefined)
        return yield* fail(problem);
    return { sourceId: source.sourceId, sha256, byteLength: source.rawBytes.byteLength, bundle, numberLexemes: decoded.numberLexemes };
});
type Quad = readonly [
    string,
    string,
    string,
    string
];
const literal = (value: string): string => JSON.stringify(value);
const typed = (value: string, datatype: string): string => `${literal(value)}^^<${KG_XSD}${datatype}>`;
const nodeIri = (uid: string): string => `urn:hswm:kg:node:${uid}`;
const pointer = (key: string): string => key.replaceAll("~", "~0").replaceAll("/", "~1");
const pythonFloat = (value: number, lexeme?: string): string => {
    if (value === 0 && lexeme?.startsWith("-")) return "-0.0";
    const text = Object.is(value, -0) ? "-0" : String(value);
    const exponent = text.includes("e") || (value !== 0 && (Math.abs(value) >= 1e16 || Math.abs(value) < 1e-4));
    const expanded = exponent ? value.toExponential() : text;
    if (expanded.includes("e"))
        return expanded.replace(/e([+-]?)(\d+)$/, (_, sign: string, digits: string) => `e${sign || "+"}${digits.padStart(2, "0")}`);
    return expanded.includes(".") ? expanded : `${expanded}.0`;
};
const scalarLiteral = (value: string | number | boolean, lexeme?: string): string => typeof value === "string" ? literal(value) : typeof value === "boolean" ? typed(String(value), "boolean") : lexeme !== undefined && /[.eE]/.test(lexeme) ? typed(pythonFloat(value, lexeme), "double") : typed(String(value), "integer");
export const compileKgBundle = (sources: readonly KgBundleSource[], profile: "v1" | "v2" = "v2"): Either.Either<KgBundleProjection, KgBundleError> => Either.gen(function* () {
    if (sources.length === 0 || !["v1", "v2"].includes(profile))
        return yield* fail("nonempty sources and supported profile required");
    const ordered = yield* Either.all([...sources].sort((a, b) => compare(a.sourceId, b.sourceId)).map(s => decodeKgBundleSource(s, profile)));
    if (![ordered.map(s => s.sourceId), ordered.map(s => s.sha256), ordered.map(s => s.bundle.bundle_uid)].every(unique))
        return yield* fail("source IDs, digests and bundle UIDs must be unique");
    const allOwned = ordered.flatMap(s => s.bundle.nodes);
    if (!unique(allOwned.map(n => n.uid)))
        return yield* fail("node owned by two bundles");
    const owners = new Map(allOwned.map(n => [n.uid, n]));
    for (const source of ordered)
        for (const anchor of source.bundle.anchors) {
            const owner = owners.get(anchor.uid);
            if (profile === "v2" && owner !== undefined && anchor.required_labels.some(l => !owner.labels.includes(l)))
                return yield* fail("anchor labels disagree with owner");
        }
    const compilerId = `hswm-kg-bundle-rdf-compiler/${profile}`, contractVersion = `hswm-kg-bundle-rdf-projection/${profile}`;
    const sourceSet = ordered.map(s => ({ id: s.sourceId, mediaType: "application/json", sha256: s.sha256, byteLength: s.byteLength, bundleUid: s.bundle.bundle_uid }));
    const sourceSetSha256 = digest(sourceSet), projectionIdentitySha256 = digest({ compilerId, contractVersion, rdfProfile: KG_PROFILE, sourceSetSha256 });
    const projectionIri = `urn:hswm:kg-bundle-projection:${projectionIdentitySha256}`, activity = `${projectionIri}:derivation`, meta = `${projectionIri}:metadata`, prov = `${projectionIri}:provenance`;
    const lines: Quad[] = [[projectionIri, KG_RDF_TYPE, `${KG_VOCAB}Projection`, meta], [projectionIri, KG_RDF_TYPE, `${KG_PROV}Entity`, prov], [projectionIri, `${KG_PROV}wasGeneratedBy`, activity, prov], [activity, KG_RDF_TYPE, `${KG_PROV}Activity`, prov]];
    for (const [key, value] of Object.entries({ contractVersion, compilerId, rdfProfile: KG_PROFILE, writeBack: "FORBIDDEN", nonclaim: KG_NONCLAIM, claimCeiling: KG_CLAIM_CEILING, sourceSetSha256 }))
        lines.push([projectionIri, KG_VOCAB + key, literal(value), meta]);
    for (const source of ordered) {
        const b = source.bundle, bi = `urn:sha256:${source.sha256}`, graph = `urn:hswm:kg-bundle:${source.sha256}`;
        lines.push([bi, KG_RDF_TYPE, KG_VOCAB + "Bundle", meta], [bi, KG_RDF_TYPE, KG_PROV + "Entity", prov], [bi, KG_VOCAB + "dataGraph", graph, meta], [activity, KG_PROV + "used", bi, prov], [projectionIri, KG_PROV + "wasDerivedFrom", bi, prov]);
        for (const [key, value] of Object.entries({ sourceId: source.sourceId, sourceSha256: source.sha256, mediaType: "application/json", bundleUid: b.bundle_uid, schemaVersion: b.schema_version, status: b["status"], nonclaim: b.nonclaim, ...(b.authority_boundary === undefined ? {} : { authorityBoundary: b.authority_boundary }), ...(b.source_accessed_on === undefined ? {} : { sourceAccessedOn: b.source_accessed_on }) }))
            lines.push([bi, KG_VOCAB + key, literal(value), meta]);
        for (const [key, value] of Object.entries({ sourceByteLength: source.byteLength, nodeCount: b.nodes.length, relationCount: b.relations.length, anchorCount: b.anchors.length, ...Object.fromEntries(Object.entries(b.expected_counts).map(([k, v]) => [`expectedCount/${k}`, v])) }))
            lines.push([bi, KG_VOCAB + key, typed(String(value), "nonNegativeInteger"), meta]);
        for (const binding of b.artifact_bindings) {
            const content = `urn:sha256:${binding.sha256}`, id = profile === "v1" ? content : `urn:hswm:kg:artifact-binding:${digest({ bundleSha256: source.sha256, ...binding })}`;
            if (profile === "v2")
                lines.push([content, KG_RDF_TYPE, KG_VOCAB + "ArtifactContent", meta], [content, KG_RDF_TYPE, KG_PROV + "Entity", prov], [id, KG_VOCAB + "bindsArtifact", content, meta]);
            lines.push([id, KG_RDF_TYPE, KG_VOCAB + "ArtifactBinding", meta], [id, KG_RDF_TYPE, KG_PROV + "Entity", prov], [id, KG_VOCAB + "bindingPath", literal(binding.path), meta], [id, KG_VOCAB + "bindingSha256", literal(binding.sha256), meta], [bi, KG_VOCAB + "hasArtifactBinding", id, meta], [bi, KG_PROV + "wasDerivedFrom", id, prov]);
        }
        for (const anchor of b.anchors) {
            const id = nodeIri(anchor.uid);
            lines.push([bi, KG_VOCAB + "anchorsTo", id, graph]);
            if (profile === "v1" && owners.has(anchor.uid))
                continue;
            const ref = profile === "v1" ? id : `urn:hswm:kg:anchor-reference:${digest({ bundleSha256: source.sha256, ...anchor })}`;
            if (profile === "v2")
                lines.push([ref, KG_RDF_TYPE, KG_VOCAB + "AnchorReference", graph], [ref, KG_VOCAB + "declaredBy", bi, graph], [ref, KG_VOCAB + "anchorTarget", id, graph]);
            lines.push([ref, KG_VOCAB + "anchorName", literal(anchor["name"]), graph]);
            for (const label of anchor.required_labels)
                lines.push([ref, KG_VOCAB + "requiredLabel", literal(label), graph]);
            if (!owners.has(anchor.uid))
                lines.push([id, KG_RDF_TYPE, KG_VOCAB + "Anchor", graph], [id, KG_VOCAB + "uid", literal(anchor.uid), graph]);
        }
        for (const [index, node] of b.nodes.entries()) {
            const id = nodeIri(node.uid);
            lines.push([id, KG_RDF_TYPE, KG_VOCAB + "Node", graph], [id, KG_VOCAB + "uid", literal(node.uid), graph], [id, KG_VOCAB + "ownedBy", bi, graph], [bi, KG_VOCAB + "ownsNode", id, graph]);
            for (const label of node.labels)
                lines.push([id, KG_RDF_TYPE, KG_VOCAB + "label/" + label, graph], [id, KG_VOCAB + "label", literal(label), graph]);
            for (const [key, value] of Object.entries(node.properties)) {
                const path = `/nodes/${index}/properties/${pointer(key)}`;
                if (Array.isArray(value)) {
                    for (const [i, item] of value.entries())
                        lines.push([id, KG_VOCAB + "prop/" + key, scalarLiteral(item, source.numberLexemes[`${path}/${i}`]), graph]);
                    if (value.length > 1) {
                        const arrayJson = `[${value.map((item, i) => typeof item === "number" && /[.eE]/.test(source.numberLexemes[`${path}/${i}`] ?? "") ? pythonFloat(item, source.numberLexemes[`${path}/${i}`]) : kgCanonicalJson(item)).join(",")}]`;
                        lines.push([id, KG_VOCAB + "propOrder/" + key, literal(arrayJson), graph]);
                    }
                }
                else
                    lines.push([id, KG_VOCAB + "prop/" + key, scalarLiteral(value as string | number | boolean, source.numberLexemes[path]), graph]);
                if (["standard_graph_role", "plan_graph_role"].includes(key))
                    lines.push([id, KG_RDF_TYPE, KG_VOCAB + "role/" + String(value), graph]);
            }
        }
        for (const relation of b.relations) {
            const id = `urn:hswm:kg:relation:${digest(relation)}`, from = nodeIri(relation.from_uid), to = nodeIri(relation.to_uid);
            lines.push([id, KG_RDF_TYPE, KG_VOCAB + "Relation", graph], [id, KG_VOCAB + "from", from, graph], [id, KG_VOCAB + "to", to, graph], [id, KG_VOCAB + "ownedBy", bi, graph], [bi, KG_VOCAB + "ownsRelation", id, graph], [from, KG_VOCAB + "rel/" + relation.type, to, graph]);
            for (const [key, value] of Object.entries({ relationType: relation.type, authorityClass: relation["authority_class"], scope: relation.scope, status: relation["status"] }))
                lines.push([id, KG_VOCAB + key, literal(value), graph]);
        }
    }
    const sorted = [...new Map(lines.map(q => [kgCanonicalJson(q), q])).values()].sort((a, b) => {
        for (const i of [0, 1, 2, 3] as const) {
            const order = compare(a[i], b[i]);
            if (order !== 0)
                return order;
        }
        return 0;
    });
    const nquads = new TextEncoder().encode(sorted.map(([s, p, o, g]) => `<${s}> <${p}> ${o.startsWith('"') ? o : `<${o}>`} <${g}> .\n`).join(""));
    const dataset = { mediaType: "application/n-quads", sha256: kgSha256(nquads), byteLength: nquads.byteLength };
    const descriptor = { _tag: "HSWMKgBundleRdfProjectionManifest", contractVersion, compilerId, rdfProfile: KG_PROFILE, mapping: "ROLE_PRESERVING_REIFIED_RELATIONS_WITH_DIRECT_TYPED_EDGES", dataset, sources: sourceSet, sourceSetSha256, projectionIdentitySha256, projectionIri, nodeCount: allOwned.length, relationCount: ordered.reduce((n, s) => n + s.bundle.relations.length, 0), writeBack: "FORBIDDEN", nonclaim: KG_NONCLAIM, claimCeiling: KG_CLAIM_CEILING, invalidatedBy: ["ANY_BOUND_BUNDLE_BYTES_CHANGED", "PROJECTION_PROFILE_OR_COMPILER_CHANGED"], rdfDatasetOmits: ["LIVE_KG_STATE_AND_PUBLICATION_STATUS", "ARTIFACT_BINDING_CONTENT_BYTES", "CANONICAL_STATE_AND_PERMIT_CONTENT", "CAUSAL_CREDIT_AND_LEARNING_ASSERTIONS"] };
    const sourceRefs = sourceSet.map(s => ({ "@id": `urn:sha256:${s.sha256}` }));
    const provO = new TextEncoder().encode(kgCanonicalJson({ "@context": { prov: KG_PROV, kb: KG_VOCAB }, "@graph": [{ "@id": activity, "@type": "prov:Activity", "prov:used": sourceRefs }, { "@id": projectionIri, "@type": "prov:Entity", "prov:wasDerivedFrom": sourceRefs, "prov:wasGeneratedBy": { "@id": activity }, "kb:datasetSha256": dataset.sha256, "kb:writeBack": "FORBIDDEN", "kb:claimCeiling": KG_CLAIM_CEILING }] }));
    return { nquads, descriptor, provO };
});
