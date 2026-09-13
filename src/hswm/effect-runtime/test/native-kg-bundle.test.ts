import { readFileSync, readdirSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"
import { Effect, Either } from "effect"
import { compileKgBundle, kgCanonicalJson, kgSha256, type KgBundleProjection } from "../src/native-kg-bundle-domain.js"
import { queryKgBundle, validateKgQuery, validateKgShacl } from "../src/native-kg-standards.js"

const root = resolve(import.meta.dirname, "../../../..")
const bytes = (path: string): Uint8Array => readFileSync(resolve(root, path))
const json = (path: string): unknown => JSON.parse(Buffer.from(bytes(path)).toString("utf8"))
const cases = [
  { id: "hswm-knowledge-map-2026-09-13", bundle: "ontology/knowledge_map/HSWM_KNOWLEDGE_MAP_2026-09-13.v1.json", artifacts: "docs/operations/artifacts/hswm_knowledge_map_2026-09-13", nq: "knowledge-map.nq", queries: "ontology/queries/hswm_knowledge_map_2026-09-13" },
  { id: "hswm-research-tooling-2026-09-13", bundle: "ontology/research_tooling/HSWM_SCIENTIFIC_RESEARCH_TOOLING_2026-09-13.v1.json", artifacts: "docs/research/artifacts/hswm_research_tooling_2026-09-13", nq: "research-tooling.nq", queries: "ontology/queries/hswm_research_tooling_2026-09-13" }
]
const compile = (id: string, rawBytes: Uint8Array): KgBundleProjection => {
  const result = compileKgBundle([{ sourceId: id, rawBytes }])
  if (Either.isLeft(result)) throw result.left
  return result.right
}
const minimal = () => ({ schema_version: "hswm-native-kg-test/v1", bundle_uid: "sym:AbstractNode:test", status: "TEST", nonclaim: "TEST_ONLY", artifact_bindings: [{ path: "test.txt", sha256: "a".repeat(64) }], expected_counts: { nodes: 1, anchors: 0, relations: 0 }, anchors: [], nodes: [{ uid: "sym:AbstractNode:test", labels: ["AbstractNode"], properties: { name: "test", authority_class: "SECONDARY_AI" } }], relations: [] })
const encoded = (value: unknown): Uint8Array => Buffer.from(JSON.stringify(value))

describe("native KG migration: actual published evidence", () => {
  for (const fixture of cases) it(`recreates ${fixture.id} N-Quads, manifest and PROV bytes`, () => {
    const projection = compile(fixture.id, bytes(fixture.bundle))
    expect(projection.descriptor).toEqual(json(`${fixture.artifacts}/descriptor.json`))
    expect(kgSha256(projection.nquads)).toBe(kgSha256(bytes(`${fixture.artifacts}/${fixture.nq}`)))
    expect(JSON.parse(Buffer.from(projection.provO).toString("utf8"))).toEqual(json(`${fixture.artifacts}/provenance.jsonld`))
  })
  it("validates actual SHACL Core shapes and rejects a missing node name", async () => {
    const fixture = cases[0]!
    const shapes = bytes("schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl")
    const projection = compile(fixture.id, bytes(fixture.bundle))
    expect((await Effect.runPromise(validateKgShacl(projection, shapes))).conforms).toBe(true)
    const changed = Buffer.from(projection.nquads).toString("utf8").split("\n").filter(line => !line.includes("/prop/name>")).join("\n")
    const corrupted = { ...projection, nquads: Buffer.from(changed), descriptor: { ...projection.descriptor, dataset: { sha256: kgSha256(changed), byteLength: Buffer.byteLength(changed) } } }
    expect((await Effect.runPromise(validateKgShacl(corrupted, shapes))).conforms).toBe(false)
  }, 30_000)
  it("executes every published SELECT locally with bound projection bytes", async () => {
    for (const fixture of cases) {
      const projection = compile(fixture.id, bytes(fixture.bundle))
      const queryFiles = readdirSync(resolve(root, fixture.queries)).filter(path => path.endsWith(".sparql"))
      expect(queryFiles).toHaveLength(6)
      const golden = json(`${fixture.artifacts}/query-results.json`) as Readonly<Record<string, unknown>>
      for (const file of queryFiles) {
        const result = await Effect.runPromise(queryKgBundle(projection, Buffer.from(bytes(`${fixture.queries}/${file}`)).toString("utf8")))
        expect(Array.isArray(result), file).toBe(true)
        if (typeof result === "boolean") throw new Error("SELECT did not return rows")
        const normalized = result.map(row => Object.fromEntries(Object.entries(row).map(([key, value]) => [key, file.startsWith("Q3_coverage") && ["mappedFcls", "requiredFclObligations", "requiredFcls"].includes(key) && value !== null ? { ...value, value: [...new Set((value["value"] ?? "").split("|"))].sort().join("|") } : value])))
        const ordered = normalized.sort((a, b) => Buffer.compare(Buffer.from(kgCanonicalJson(a)), Buffer.from(kgCanonicalJson(b))))
        expect(ordered, file).toEqual(golden[file])
      }
    }
  }, 60_000)
})

describe("native KG refusal contracts", () => {
  it("rejects forged source bytes, counts, ownership and duplicate JSON keys", () => {
    const rawBytes = encoded(minimal())
    expect(Either.isLeft(compileKgBundle([{ sourceId: "fixture", rawBytes, sha256: "b".repeat(64) }]))).toBe(true)
    expect(Either.isLeft(compileKgBundle([{ sourceId: "fixture", rawBytes: encoded({ ...minimal(), expected_counts: { nodes: 2 } }) }]))).toBe(true)
    expect(Either.isLeft(compileKgBundle([{ sourceId: "fixture", rawBytes: Buffer.from('{"schema_version":1,"schema_version":2}') }]))).toBe(true)
    const node = minimal().nodes[0]!
    expect(Either.isLeft(compileKgBundle([{ sourceId: "fixture", rawBytes: encoded({ ...minimal(), nodes: [node, node] }) }]))).toBe(true)
  })
  it("retains numeric RDF datatypes, property array order and finite decimals", () => {
    const raw = JSON.stringify(minimal()).replace('"name":"test"', '"name":"test","numbers":[1,1.0,0.125]')
    const text = Buffer.from(compile("fixture", Buffer.from(raw)).nquads).toString("utf8")
    expect(text).toContain('"1"^^<http://www.w3.org/2001/XMLSchema#integer>')
    expect(text).toContain('"1.0"^^<http://www.w3.org/2001/XMLSchema#double>')
    expect(text).toContain('"0.125"^^<http://www.w3.org/2001/XMLSchema#double>')
    expect(text).toContain('"[1,1.0,0.125]"')
  })
  it("rejects remote/update operations without rejecting keywords in quoted literals", () => {
    for (const query of ['SELECT * FROM <https://example.org> WHERE {?s ?p ?o}', 'ASK { SERVICE <https://example.org> {?s ?p ?o} }', 'INSERT DATA {<urn:a> <urn:b> <urn:c>}', 'SELECT * WHERE {?s ?p ?o}; CLEAR ALL']) expect(Either.isLeft(validateKgQuery(query))).toBe(true)
    expect(Either.isRight(validateKgQuery('SELECT * WHERE { ?s ?p "SERVICE FROM DELETE" }'))).toBe(true)
  })
  it("refuses unsupported SHACL extensions instead of silently reporting conformance", async () => {
    const projection = compile("fixture", encoded(minimal()))
    const shapes = Buffer.from('@prefix sh: <http://www.w3.org/ns/shacl#>. <urn:shape> sh:sparql [ sh:select "SELECT * WHERE {}" ].')
    expect(Either.isLeft(await Effect.runPromise(Effect.either(validateKgShacl(projection, shapes))))).toBe(true)
    projection.nquads[0] = 0
    expect(Either.isLeft(await Effect.runPromise(Effect.either(queryKgBundle(projection, "ASK {}"))))).toBe(true)
  })
})
