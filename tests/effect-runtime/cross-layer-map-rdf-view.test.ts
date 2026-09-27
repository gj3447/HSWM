import { createHash } from "node:crypto"
import { readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"

import { expect, it } from "@effect/vitest"
import { Effect, Either } from "effect"
import { Parser } from "n3"

import { canonicalJsonBytes } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-json.js"
import { canonicalAtomV2KeyId, type CanonicalAtomV2Key } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-schema.js"
import { compileCrossLayerMapRdfView, CROSS_LAYER_MAP_RDF_VIEW_CONTRACT_VERSION, type CrossLayerMapRdfView } from "../../src/hswm/effect-runtime/src/cross-layer-map-rdf-view.js"
import { kgSha256, type KgBundleProjection } from "../../src/hswm/effect-runtime/src/native-kg-bundle-domain.js"
import { queryKgBundle, validateKgShacl } from "../../src/hswm/effect-runtime/src/native-kg-standards.js"
import type { MapSpec } from "../../src/hswm/effect-runtime/src/cross-layer-map-domain.js"
import type { CrossLayerMapFrame } from "../../src/hswm/effect-runtime/src/cross-layer-map-runtime.js"

const encoder = new TextEncoder()
const decoder = new TextDecoder()
const sha256 = (value: Uint8Array | string) => createHash("sha256").update(value).digest("hex")
const key = (atomUid: string, revisionId = 0): CanonicalAtomV2Key => ({
  schemaVersion: "hswm:test:cross-layer-map-rdf-view:v1",
  lineageId: "lineage:cross-layer-map-rdf-view",
  atomUid,
  revisionId
})
const content = (value: unknown) => {
  const encoded = canonicalJsonBytes(value)
  if (Either.isLeft(encoded)) throw new Error(encoded.left.detail)
  return Object.freeze({ utf8: decoder.decode(encoded.right), sha256: sha256(encoded.right) })
}
const context = Object.freeze({
  schema: "hswm-cross-layer-map/v1" as const,
  source: Object.freeze({ modelRef: "toy:physical \"r\\\\h\"", digest: "a".repeat(64) }),
  target: Object.freeze({ modelRef: "toy:semantic \"r\\\\h\"", digest: "b".repeat(64) }),
  mappingKind: "preserve_r_h" as const,
  mappingMethod: "authored_deterministic" as const,
  declaredLosses: Object.freeze([]),
  actionAllowlist: Object.freeze(["wait", "pulse"] as const),
  time: Object.freeze({ unit: "tick" as const, horizon: 1 as const }),
  supportScope: Object.freeze({ world: "finite-toy-rh/v1" as const, contexts: Object.freeze(["fixture:\"a\"", "fixture:\\b"]), observableFields: Object.freeze(["r", "h"] as const) })
})
const dropContext = Object.freeze({
  ...context,
  mappingKind: "drop_refractory" as const,
  declaredLosses: Object.freeze(["refractory-state-r"]),
  supportScope: Object.freeze({ world: "finite-toy-rh/v1" as const, contexts: Object.freeze(["fixture:lossy"]), observableFields: Object.freeze(["h"] as const) })
})
const emptyContexts = Object.freeze({
  ...context,
  supportScope: Object.freeze({ world: "finite-toy-rh/v1" as const, contexts: Object.freeze([]), observableFields: Object.freeze(["r", "h"] as const) })
})
const frame = (map: MapSpec = context): CrossLayerMapFrame => {
  const observation = map.mappingKind === "drop_refractory" ? Object.freeze({ h: 0 }) : Object.freeze({ r: 0, h: 0 })
  const subject = Object.freeze({ observation, asOf: 1, requested: Object.freeze({ action: "pulse" as const, horizon: 1 as const, window: Object.freeze({ start: 2, end: 3 }) }) })
  const roleContent = [content({ subject, eventTime: 2 }), content(map), content({ evidence: [], eventTime: 2 }), content({ exception: "none" })] as const
  return Object.freeze({
  frame: Object.freeze({
    event: "rdf-view:fixture",
    stateRevision: 7,
    relation: Object.freeze({ key: key("relation:map", 2), owner: "owner:map", semantic: Object.freeze({ semanticText: "fixture", disposition: "fixture", uncertainty: "unknown", exceptionRefs: Object.freeze(["exception:0"]), trace: null, outcome: null }) }),
    roles: Object.freeze(["subject", "context", "evidence", "exception"].map((role, index) => Object.freeze({
      referenceType: "hswm:semantic:role",
      role,
      key: key(`${role}:0`),
      owner: "owner:map",
      contentSha256: roleContent[index]!.sha256,
      contentUtf8: roleContent[index]!.utf8
    }))),
    priorEvidence: null,
    frameSha256: "f".repeat(64)
  }),
  packet: Object.freeze({
    subject,
    context: map,
    evidence: Object.freeze([]),
    eventTime: 2
  })
  })
}
const projection = (view: CrossLayerMapRdfView): KgBundleProjection => ({
  nquads: view.nquads,
  descriptor: { dataset: view.manifest.dataset },
  provO: new Uint8Array()
})
const researchFile = (relative: string): Uint8Array => new Uint8Array(readFileSync(fileURLToPath(new URL(`../../_research/semantic_map_engineering_v1/${relative}`, import.meta.url))))

it.effect("derives a committed public MapSpec RDF 1.1 view with queryable fields and ordered incidences", () => {
  const result = compileCrossLayerMapRdfView(frame())
  expect(Either.isRight(result)).toBe(true)
  if (Either.isLeft(result)) throw new Error(result.left.detail)
  const view = result.right
  const nquads = decoder.decode(view.nquads)
  expect(new Parser({ format: "N-Quads" }).parse(nquads)).not.toHaveLength(0)
  expect(view.manifest.contractVersion).toBe(CROSS_LAYER_MAP_RDF_VIEW_CONTRACT_VERSION)
  expect(view.manifest.dataset.sha256).toBe(kgSha256(view.nquads))
  expect(view.manifest.writeBack).toBe("FORBIDDEN")
  expect(view.manifest.relationAtomIri).toBe(`https://hswm.invalid/canonical-atom-v2/rdf/v1/atom/${encodeURIComponent(canonicalAtomV2KeyId(key("relation:map", 2)))}`)
  expect(view.manifest.contextAtomIri).toBe(`https://hswm.invalid/canonical-atom-v2/rdf/v1/atom/${encodeURIComponent(canonicalAtomV2KeyId(key("context:0")))}`)
  expect(nquads).toContain("http://www.w3.org/ns/prov#wasDerivedFrom")
  expect(nquads).toContain("toy:physical")
  expect(nquads).toContain(canonicalAtomV2KeyId(key("context:0")))
  expect(nquads).toContain(view.manifest.relationAtomIri)
  expect(nquads).toContain(view.manifest.contextAtomIri)
  return Effect.gen(function* () {
    const rows = yield* queryKgBundle(projection(view), decoder.decode(researchFile("queries/map-spec.rq")))
    expect(Array.isArray(rows)).toBe(true)
    const values = rows as ReadonlyArray<Readonly<Record<string, { readonly value: string } | null>>>
    expect(values.length).toBeGreaterThan(0)
    expect(values.every((row) => row["sourceRef"]?.value === context.source.modelRef)).toBe(true)
    expect(values.every((row) => row["mappingKind"]?.value === "preserve_r_h")).toBe(true)
    expect(values.every((row) => row["timeUnit"]?.value === "tick" && row["horizon"]?.value === "1")).toBe(true)
    expect(new Set(values.map((row) => row["actionOrdinal"]?.value))).toEqual(new Set(["0", "1"]))
    expect(new Set(values.map((row) => row["scopeContextOrdinal"]?.value))).toEqual(new Set(["0", "1"]))
    expect(new Set(values.map((row) => row["observableOrdinal"]?.value))).toEqual(new Set(["0", "1"]))
    const validation = yield* validateKgShacl(projection(view), researchFile("shapes/map-spec.ttl"))
    expect(validation.conforms).toBe(true)
    expect(validation.profile).toBe("SHACL_1_0_CORE_NO_IMPORTS_NO_EXTENSIONS")
  })
})

it.effect("rejects an uncommitted packet context and SHACL rejects a parseable malformed derived view", () => {
  const original = frame()
  const mismatch: CrossLayerMapFrame = Object.freeze({ ...original, packet: Object.freeze({ ...original.packet, context: Object.freeze({ ...context, mappingMethod: "llm_proposed" as const }) }) })
  const rejected = compileCrossLayerMapRdfView(mismatch)
  expect(Either.isLeft(rejected)).toBe(true)
  if (Either.isLeft(rejected)) expect(rejected.left.code).toBe("CONTEXT_COMMITMENT_MISMATCH")
  const subjectMismatch: CrossLayerMapFrame = Object.freeze({ ...original, packet: Object.freeze({ ...original.packet, subject: Object.freeze({ ...original.packet.subject, asOf: 0 }) }) })
  const wrongSubject = compileCrossLayerMapRdfView(subjectMismatch)
  expect(Either.isLeft(wrongSubject)).toBe(true)
  if (Either.isLeft(wrongSubject)) expect(wrongSubject.left.code).toBe("FRAME_CONTENT_MISMATCH")
  const lossy = compileCrossLayerMapRdfView(frame(dropContext))
  expect(Either.isRight(lossy)).toBe(true)
  if (Either.isRight(lossy)) expect(decoder.decode(lossy.right.nquads)).toContain("refractory-state-r")
  const valid = compileCrossLayerMapRdfView(original)
  if (Either.isLeft(valid)) throw new Error(valid.left.detail)
  const malformed = decoder.decode(valid.right.nquads)
    .split("\n")
    .filter((line) => !line.includes("/sourceModelSha256>"))
    .join("\n")
  expect(new Parser({ format: "N-Quads" }).parse(malformed)).not.toHaveLength(0)
  const bytes = encoder.encode(malformed)
  const broken: KgBundleProjection = { nquads: bytes, descriptor: { dataset: { sha256: kgSha256(bytes), byteLength: bytes.byteLength } }, provO: new Uint8Array() }
  return validateKgShacl(broken, researchFile("shapes/map-spec.ttl")).pipe(Effect.tap((validation) => Effect.sync(() => {
    expect(validation.conforms).toBe(false)
  })))
})

it.effect("allows a decoder-valid MapSpec with an empty support-context array", () => {
  const result = compileCrossLayerMapRdfView(frame(emptyContexts))
  expect(Either.isRight(result)).toBe(true)
  if (Either.isLeft(result)) throw new Error(result.left.detail)
  return Effect.gen(function* () {
    const rows = yield* queryKgBundle(projection(result.right), decoder.decode(researchFile("queries/map-spec.rq")))
    expect(Array.isArray(rows)).toBe(true)
    const values = rows as ReadonlyArray<Readonly<Record<string, { readonly value: string } | null>>>
    expect(values.length).toBeGreaterThan(0)
    expect(values.every((row) => row["scopeContext"] === null && row["scopeContextOrdinal"] === null)).toBe(true)
    const validation = yield* validateKgShacl(projection(result.right), researchFile("shapes/map-spec.ttl"))
    expect(validation.conforms).toBe(true)
  })
})
