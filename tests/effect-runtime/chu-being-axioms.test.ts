import { createHash } from "node:crypto"
import { readFile } from "node:fs/promises"
import { fileURLToPath } from "node:url"
import { resolve } from "node:path"
import { Effect, Either } from "effect"
import { beforeAll, expect, it } from "vitest"
import { compileKgBundle, type KgBundle, type KgBundleProjection } from "../../src/hswm/effect-runtime/src/native-kg-bundle-domain.js"
import { queryKgBundle, validateKgShacl } from "../../src/hswm/effect-runtime/src/native-kg-standards.js"

const root = fileURLToPath(new URL("../../", import.meta.url))
const queryRoot = "ontology/queries/chu_being_hswm_structure_2026-10-07"
const artifactRoot = "docs/canon/artifacts/chu_being_hswm_structure_2026-10-07"
const snapshot = "docs/canon/sources/SEONUI_AXIOMS_MIND_SNAPSHOT_2026-10-07.md"
const userPath = "docs/canon/sources/USER_PRIMARY_CHU_BEING_HSWM_STRUCTURE_2026-10-07.txt"
const read = (path: string) => readFile(resolve(root, path))
const hash = (bytes: Uint8Array) => createHash("sha256").update(bytes).digest("hex")
const uid = (key: string, label = "Concept") => `sym:${label}:chu-being-${key}-2026-10-07`
const compile = (value: KgBundle): KgBundleProjection => {
  const result = compileKgBundle([{ sourceId: "chu-being", rawBytes: Buffer.from(JSON.stringify(value)) }], "v2")
  if (Either.isLeft(result)) throw result.left
  return result.right
}
let bundle: KgBundle
let projection: KgBundleProjection
let shapes: Uint8Array
let axiomBytes: Buffer
let user: string
let definitions: { ordinal: number; name: string; definition: string; line: number }[]

beforeAll(async () => {
  bundle = JSON.parse((await read("ontology/identity/hswm_core/CHU_BEING_HSWM_STRUCTURE_ONTOLOGY.v1.json")).toString()) as KgBundle
  shapes = await read(`${queryRoot}/shapes.ttl`)
  projection = compile(bundle)
  axiomBytes = await read(snapshot)
  user = (await read(userPath)).toString().replace(/\n$/, "")
  definitions = axiomBytes.toString().split("\n").flatMap((line, index) => {
    const m = /^(\d+)\. \*\*(.+?)\*\* : (.+)$/.exec(line)
    return m ? [{ ordinal: Number(m[1]), name: m[2]!, definition: m[3]!, line: index + 1 }] : []
  })
})

const rows = async (name: string) => {
  const result = await Effect.runPromise(queryKgBundle(projection, (await read(`${queryRoot}/${name}.rq`)).toString()))
  if (typeof result === "boolean") throw new Error("expected SELECT rows")
  return result.map(row => Object.fromEntries(Object.entries(row).map(([key, term]) => [key, term?.["value"] ?? null])))
}
const sortUid = <T extends { uid: string | null }>(values: T[]) => values.sort((a, b) => String(a.uid).localeCompare(String(b.uid)))

it("preserves the source bytes, original definition occurrences and registered graph endpoints", async () => {
  expect(definitions.map(d => d.ordinal)).toEqual([1,2,3,4,5,6,7,8,9,10,11,12])
  const sourceMap = JSON.parse((await read(`${artifactRoot}/source-map.v1.json`)).toString())
  expect(sourceMap.axiom_source.snapshot_sha256).toBe(hash(axiomBytes))
  expect(sourceMap.axiom_source.sha256).toBe(hash(axiomBytes))
  expect(sourceMap.axiom_source.path).toBe("metahumotonic/선의_공리.md")
  expect(sourceMap.axiom_source.external_artifact_uid).toBe("sym:Chapter:선의_공리")
  expect(sourceMap.axiom_source.last_change_revision).toMatch(/^[a-f0-9]{40}$/)
  for (const binding of bundle.artifact_bindings) expect(hash(await read(binding.path)), binding.path).toBe(binding.sha256)
  for (const node of bundle.nodes) {
    const sourcePath = String(node.properties["source_path"])
    expect(hash(await read(sourcePath)), node.uid).toBe(node.properties["source_sha256"])
    expect(bundle.artifact_bindings.some(b => b.path === sourcePath)).toBe(true)
  }
  const nodes = new Map(bundle.nodes.map(n => [n.uid, n]))
  const contract = JSON.parse((await read(`${artifactRoot}/graph-contract.v1.json`)).toString()) as {
    relation_contracts: { predicate: string; domain_roles: string[]; range_roles: string[] }[]
  }
  expect(contract.relation_contracts.map(r => r.predicate).sort()).toEqual(["CONSTRAINS", "HAS_ASSERTION", "HAS_CONCEPT", "HAS_PARTICIPATION", "HAS_SOURCE", "REFERENCES"])
  for (const edge of bundle.relations) {
    const rule = contract.relation_contracts.find(r => r.predicate === edge.type)!
    expect(rule.domain_roles).toContain(nodes.get(edge.from_uid)?.properties["standard_graph_role"])
    expect(rule.range_roles).toContain(nodes.get(edge.to_uid)?.properties["standard_graph_role"] ?? "EXTERNAL_ANCHOR")
    expect(edge.authority_class).toBe("SECONDARY_AI")
    expect(edge.status).toBe("PROPOSED")
  }
  expect(nodes.get(uid("source"))?.properties["utterance_verbatim"]).toBe(user)
})

it("queries the three user claims and distinct CHU/HSWM roles without upgrading their evidence", async () => {
  const excerpts = [
    ["identity", "STRUCTURE_BEING_DISTINCTION", "HSWM 는 구조를 말하고 그 존재자체는 지능 존재자체는 CHU 로 보는것이 맞는것같아 내생각에는 ㅇㅇ 이해되냐 ㅇㅇ?"],
    ["optimization", "OPTIMIZATION_DIRECTION", "CHU 의 구조가 HSWM 을 향해서 완벽하게 최적화 되어가는거지 ㅇㅇ."],
    ["binding", "AXIOM_BINDING_POSSIBILITY", "그리고 여기에 CHU 에 선의 공리도 완벽하게 그 바인딩해서 의미를 이해시킬수가 있어 ㅇㅇ 내용 확인좀 해줘봐봐 ㅇㅇ"]
  ] as const
  for (const [, , quote] of excerpts) expect(user).toContain(quote)
  const identityRows = await rows("identity")
  expect(identityRows.sort((a,b) => String(a["uid"]).localeCompare(String(b["uid"]))))
    .toEqual(sortUid(excerpts.map(([key, kind, quote]) => ({
      uid: uid(key, "Claim"), kind, quote, authority: "USER_PRIMARY", sourceUid: uid("source"),
      decision: uid(`decision-${key}`), status: "NOT_EVALUATED"
    }))))
  expect((await rows("roles")).sort((a,b) => Number(a["ordinal"]) - Number(b["ordinal"]))).toEqual([
    ["being-subject",uid("subject")], ["intelligence-structure","sym:Concept:hswm"], ["speaker-source",uid("source")]
  ].map(([role,targetUid], i) => ({ uid:uid(`slot-${role}`),role,ordinal:String(i),targetUid,qualification:"STRUCTURE_AND_BEING_ARE_DISTINCT_ROLES" })))
})

it("returns all twelve exact definitions with order, source lines, authority and digest", async () => {
  expect((await rows("axioms")).sort((a,b) => Number(a["ordinal"])-Number(b["ordinal"]))).toEqual(definitions.map(d => ({
    uid:uid(`axiom-${String(d.ordinal).padStart(2,"0")}`), ordinal:String(d.ordinal), name:d.name,
    definition:d.definition, line:String(d.line), sourceHash:hash(axiomBytes), authority:"SOURCE_DECLARED"
  })))
})

it("joins each proposed binding to its own definition and unresolved meaning obligation", async () => {
  const expected = [
    ["state-transition-history","time-identity"], ["state-and-identity-lineage","time-identity"],
    ["outcome-measurement","good-measure"], ["role-bearing-composition","composition-completeness"],
    ["powerset-candidate-domain","composition-completeness"], ["candidate-good-comparison","composition-completeness"],
    ["original-winner-good-difference","good-measure"], ["singularity-dual-condition","metahumotonic-conditions"],
    ["attributed-good-transfer","interaction-nature"], ["complete-interaction-domain","interaction-nature"],
    ["nature-self-identity","metahumotonic-conditions"], ["self-existent-and-singularity","metahumotonic-conditions"]
  ]
  const actual = (await rows("bindings")).sort((a,b) => Number(a["ordinal"])-Number(b["ordinal"]))
  expect(actual).toHaveLength(12)
  for (const [i,[component,gap]] of expected.entries()) {
    const key = String(i+1).padStart(2,"0")
    expect(actual[i]).toMatchObject({uid:uid(`binding-${key}`),ordinal:String(i+1),definitionUid:uid(`axiom-${key}`),
      definition:definitions[i]!.definition,component,gapUid:uid(`gap-${gap}`),authority:"SECONDARY_AI",status:"PROPOSED_NOT_OPERATIONALIZED"})
    expect(actual[i]!["mapping"]).toBe(bundle.nodes.find(n => n.uid === uid(`binding-${key}`))?.properties["mapping_text"])
    expect(actual[i]!["question"]).toBe(bundle.nodes.find(n => n.uid === uid(`gap-${gap}`))?.properties["question"])
  }
  const obligations = await rows("obligations")
  expect(obligations.map(r=>r["uid"]).sort()).toEqual([
    "time-identity","good-measure","composition-completeness","interaction-nature","metahumotonic-conditions","understanding-optimization"
  ].map(g=>uid(`gap-${g}`)).sort())
  expect(obligations.every(r=>r["status"] === "OPEN")).toBe(true)
})

it("passes existing native v2 and content SHACL Core profiles", async () => {
  for (const bytes of [await read("schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl"), shapes]) {
    const result = await Effect.runPromise(validateKgShacl(projection, bytes))
    expect(result.results).toEqual([])
    expect(result.conforms).toBe(true)
  }
})

const mutations = [
  ["remove powerset meaning", "axiom-05", "definition_verbatim", "어떤 존재를 단순히 나눈다."],
  ["erase the singularity self condition", "axiom-08", "definition_verbatim", "어떤 존재의 악이 최소 일 때."],
  ["weaken conjunction to disjunction", "axiom-12", "definition_verbatim", "자존자 또는 특이점이다."],
  ["promote AI binding to user canon", "binding-03", "authority_class", "USER_PRIMARY"],
  ["invent an evil subtraction convention", "binding-07", "formula_status", "WINNER_MINUS_SELF_PROVEN"],
  ["smuggle an unstated evil formula", "binding-07", "evil_formula", "winner - self"],
  ["claim runtime admission", "binding-12", "runtime_admitted", true],
  ["declare perfect understanding", "interpretation", "perfect_understanding_demonstrated", true],
  ["erase source digest", "axiom-03", "source_sha256", ""],
  ["close unresolved meaning", "gap-good-measure", "status", "RESOLVED"],
  ["claim empirical support", "decision-optimization", "evidence_disposition", "SUPPORTED_IN_SCOPE"]
] as const

it.each(mutations)("SHACL rejects %s", async (_name,key,property,value) => {
  const changed: KgBundle = { ...bundle, nodes:bundle.nodes.map(n => n.uid === uid(key) ? {...n,properties:{...n.properties,[property]:value}} : n) }
  expect((await Effect.runPromise(validateKgShacl(compile(changed),shapes))).conforms).toBe(false)
})

it("rejects swapped CHU/HSWM targets and cross-wired axiom sources", async () => {
  for (const [from,to,predicate] of [
    [uid("slot-intelligence-structure"),uid("subject"),"HAS_CONCEPT"],
    [uid("binding-07"),uid("axiom-03"),"HAS_SOURCE"]
  ]) {
    const changed = {...bundle, relations:bundle.relations.map(r=>r.from_uid===from && r.type===predicate ? {...r,to_uid:to!} : r)}
    expect((await Effect.runPromise(validateKgShacl(compile(changed),shapes))).conforms).toBe(false)
  }
})

it("native compilation rejects duplicate identities and dangling references", () => {
  expect(() => compile({...bundle,nodes:[...bundle.nodes,bundle.nodes[0]!]})).toThrow()
  expect(() => compile({...bundle,relations:bundle.relations.map((r,i)=>i===0 ? {...r,to_uid:uid("missing")} : r)})).toThrow()
})
