import { execFileSync } from "node:child_process"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { Effect, Either } from "effect"
import { Parser, Store } from "n3"
import { expect, it } from "vitest"
import { makeHypergraphProjectionRehearsal } from "../../src/hswm/effect-runtime/src/hypergraph-projection-rehearsal.js"
import { compileHypergraphProjection, type HypergraphProjection } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-hypergraph-projection.js"
import { validateNativeHypergraphShacl } from "../../src/hswm/effect-runtime/src/native-hypergraph-shacl.js"
import { canonicalAtomV2KeyId, HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-schema.js"
import { canonicalAtomV2EnvelopeBytes, describeCanonicalAtomV2Envelope } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-content-bound.js"
import { makeCanonicalAtomV2AcceptedReceipt } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-domain.js"
import { makeCanonicalAtomV2StateJournalGenesis, applyCanonicalAtomV2StateJournalGenesis, describeCanonicalAtomV2StateJournalRecord, makeCanonicalAtomV2StateJournalCommit, applyCanonicalAtomV2StateJournalCommit, canonicalAtomV2StateJournalRecordBytes } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-state-journal.js"

const base = "https://hswm.invalid/canonical-atom-v2/rdf/v1/"
const vocab = `${base}vocab/`
const rdfType = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
const xsd = "http://www.w3.org/2001/XMLSchema#"
const root = resolve(import.meta.dirname, "../..")
const right = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw new Error(JSON.stringify(value.left))
  return value.right
}

// Exercise the real schema validator, journal builder and RDF compiler at
// different key counts and arities. This remains a synthetic read-only fixture.
const fixture = (arity = 3, extraAtoms = 0) => {
  const original = right(makeHypergraphProjectionRehearsal())
  const roles = ["subject", "context", "exception", "evidence"]
  const schema = { ...original.schema, kinds: original.schema.kinds.map(kind => kind.form === "RELATION" ? {
    ...kind, minimumArity: 1, referenceContracts: [{ referenceType: "reference:rehearsal-member",
      roles: roles.map(role => ({ role: `role:${role}`, targetKinds: ["kind:trajectory"], minimum: 0, maximum: 1 })) }]
  } : kind) }
  const entity = original.source.state.atoms.find(a => a.kind === "kind:trajectory")!
  const atoms = [...original.source.state.atoms.map(atom => atom.kind === "kind:ternary-relation" ? {
    ...atom, references: roles.slice(0, arity).map(role => ({ referenceType: "reference:rehearsal-member", role: `role:${role}`, target: entity.key }))
  } : atom), ...Array.from({ length: extraAtoms }, (_, index) => ({ ...entity, key: { ...entity.key, atomUid: `atom:extra:${index}` } }))]
    .sort((left, right) => canonicalAtomV2KeyId(left.key) < canonicalAtomV2KeyId(right.key) ? -1 : 1)
  const journalLineageId = "journal:standard-graph-proof"
  const genesis = right(makeCanonicalAtomV2StateJournalGenesis(journalLineageId, schema))
  const context = { state: right(applyCanonicalAtomV2StateJournalGenesis(schema, genesis)),
    descriptor: right(describeCanonicalAtomV2StateJournalRecord(genesis)), journalLineageId, schema: genesis.schema }
  const command = { _tag: "CommitCanonicalAtomsV2" as const, contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
    transitionId: "transition:standard-graph-proof", expectedStateRevision: 0, schemaVersion: schema.schemaVersion,
    actorClaim: "fixture:actor", authorizationRef: "authorization:fixture", scope: "scope:fixture", decidedAt: "2026-10-05T00:00:00.000Z",
    traceRef: null, readSet: [], writes: atoms, provenanceSha256: entity.content.sha256 }
  const envelopes = atoms.map(atom => right(canonicalAtomV2EnvelopeBytes(atom)))
  const bindings = atoms.map(atom => ({ key: atom.key, payload: atom.content, envelope: right(describeCanonicalAtomV2Envelope(atom)) }))
  const tail = right(makeCanonicalAtomV2StateJournalCommit(schema, context, makeCanonicalAtomV2AcceptedReceipt(command, 0, 1), bindings, envelopes))
  const applied = right(applyCanonicalAtomV2StateJournalCommit(schema, context, tail, envelopes))
  const source = { journalLineageId, schemaBinding: genesis.schema, state: applied.state,
    tailDescriptor: applied.descriptor, tailRecordBytes: right(canonicalAtomV2StateJournalRecordBytes(tail)) }
  const projection = right(compileHypergraphProjection(schema, source))
  const native = atoms.map(atom => ({ key: canonicalAtomV2KeyId(atom.key), metadata: {
    kind: atom.kind, kindForm: schema.kinds.find(kind => kind.kind === atom.kind)!.form,
    responsibilityOwner: atom.responsibilityOwner, contentMediaType: atom.content.mediaType,
    contentByteLength: atom.content.byteLength, contentSha256: atom.content.sha256,
    provenanceMode: atom.provenance.mode, evidenceSha256: atom.provenance.evidenceSha256,
    provenanceSource: atom.provenance.sourceRef === null ? null : canonicalAtomV2KeyId(atom.provenance.sourceRef)
  }, references: atom.references.map(ref => ({ referenceType: ref.referenceType, role: ref.role, target: canonicalAtomV2KeyId(ref.target) })) }))
  return { projection, native }
}

// This adapter independently reads actual N-Quads, not the retained manifest
// state or property-graph nodes. RDF statement order has no slot meaning.
const readRdf = (projection: HypergraphProjection, input = projection.rdf.nquads) => {
  const store = new Store(new Parser({ format: "N-Quads" }).parse(new TextDecoder().decode(input)))
  const quads = store.getQuads(null, null, null, null)
  const graphPrefix = `${base}dataset/${projection.rdf.manifest.source.tailDescriptor.sha256}/${projection.rdf.manifest.compiler.profile.sha256}/graph/`
  const matches = (subject: string, predicate: string, graph: string) => quads.filter(q =>
    q.subject.value === subject && q.predicate.value === predicate && q.graph.value === graphPrefix + graph)
  const single = (subject: string, predicate: string, graph: string, kind: "NamedNode" | "Literal", datatype = `${xsd}string`) => {
    const found = matches(subject, predicate, graph)
    if (found.length !== 1 || found[0]!.object.termType !== kind) throw new Error(`RDF cardinality or term kind: ${predicate}`)
    const value = found[0]!.object
    if (value.termType === "Literal" && (value.datatype.value !== datatype || value.language !== "")) throw new Error("RDF literal datatype")
    return value.value
  }
  const literal = (s: string, p: string, g: string) => single(s, vocab + p, g, "Literal")
  const natural = (s: string, p: string) => {
    const text = single(s, vocab + p, "state", "Literal", `${xsd}nonNegativeInteger`)
    const value = Number(text)
    if (!/^(0|[1-9][0-9]*)$/.test(text) || !Number.isSafeInteger(value)) throw new Error("RDF natural number")
    return value
  }
  const typed = (name: string) => quads.filter(q => q.predicate.value === rdfType && q.object.value === vocab + name && q.graph.value === graphPrefix + "state").map(q => {
    if (q.subject.termType !== "NamedNode" || q.object.termType !== "NamedNode") throw new Error("RDF named identity")
    return q.subject.value
  })
  const subjects = [...typed("CanonicalAtomVersion"), ...typed("ReifiedRelationAtomVersion")]
  const keys = new Map(subjects.map(subject => [subject, literal(subject, "canonicalKey", "state")]))
  const keyAt = (subject: string) => {
    const key = keys.get(subject)
    if (!key || subject !== `${base}atom/${encodeURIComponent(key)}`) throw new Error("RDF canonical identity or endpoint")
    return key
  }
  const headers = subjects.map(subject => {
    const kindForm = literal(subject, "kindForm", "schema")
    const expectedType = kindForm === "RELATION" ? "ReifiedRelationAtomVersion" : kindForm === "ENTITY" ? "CanonicalAtomVersion" : "INVALID"
    if (single(subject, rdfType, "state", "NamedNode") !== vocab + expectedType) throw new Error("RDF kind form")
    const provenance = matches(subject, vocab + "provenanceSource", "provenance")
    if (provenance.length > 1) throw new Error("RDF provenance cardinality")
    return { key: keyAt(subject), metadata: {
      kind: literal(subject, "kind", "schema"), kindForm, responsibilityOwner: literal(subject, "responsibilityOwner", "schema"),
      contentMediaType: literal(subject, "contentMediaType", "state"), contentByteLength: natural(subject, "contentByteLength"),
      contentSha256: literal(subject, "contentSha256", "evidence"), provenanceMode: literal(subject, "provenanceMode", "provenance"),
      evidenceSha256: literal(subject, "evidenceSha256", "evidence"),
      provenanceSource: provenance.length === 0 ? null : keyAt(single(subject, vocab + "provenanceSource", "provenance", "NamedNode"))
    } }
  })
  const referenceSubjects = typed("TypedReference")
  const rows = referenceSubjects.map(subject => {
    const sourceIri = single(subject, vocab + "sourceAtom", "state", "NamedNode")
    const source = keyAt(sourceIri), ordinal = natural(subject, "ordinal")
    if (subject !== `${base}reference/${encodeURIComponent(source)}/${ordinal}`) throw new Error("RDF participation identity")
    const links = quads.filter(q => q.predicate.value === vocab + "hasTypedReference" && q.object.value === subject)
    if (links.length !== 1 || links[0]!.subject.value !== sourceIri || links[0]!.object.termType !== "NamedNode" || links[0]!.graph.value !== graphPrefix + "state") throw new Error("RDF incidence backlink")
    return { source, ordinal, reference: { referenceType: literal(subject, "referenceType", "schema"), role: literal(subject, "role", "schema"),
      target: keyAt(single(subject, vocab + "targetAtom", "state", "NamedNode")) } }
  })
  if (quads.filter(q => q.predicate.value === vocab + "hasTypedReference").length !== rows.length) throw new Error("RDF dangling incidence link")
  return { headers, rows }
}

const wire = (f: ReturnType<typeof fixture>, bytes?: Uint8Array) => ({ contract: "hswm-standard-graph-incidence/v1", atoms: f.native, ...readRdf(f.projection, bytes) })
const checkLean = (cases: readonly ReturnType<typeof wire>[]) => JSON.parse(execFileSync(resolve(root, "formal/.lake/build/bin/HSWMStandardGraphIncidenceCli"), [], {
  input: JSON.stringify(cases), encoding: "utf8", timeout: 15000, stdio: ["pipe", "pipe", "pipe"]
})) as { matches: boolean; exactView: boolean; endpointsResolve: boolean; admissionProved: boolean; fullCanonicalStateProved: boolean }[]

it("reads actual RDF role slots, named graph provenance and metadata independently of statement order", async () => {
  const f = fixture(), first = wire(f)
  const lines = new TextDecoder().decode(f.projection.rdf.nquads).trimEnd().split("\n")
  const reordered = new TextEncoder().encode([...lines].reverse().concat(lines[0]!).join("\n") + "\n")
  // Repeated identical RDF statements are one set member, not extra incidences.
  const again = wire(f, reordered)
  const normalize = (w: ReturnType<typeof wire>) => ({ ...w,
    headers: [...w.headers].sort((a, b) => a.key.localeCompare(b.key)),
    rows: [...w.rows].sort((a, b) => a.source.localeCompare(b.source) || a.ordinal - b.ordinal) })
  expect(normalize(again)).toEqual(normalize(first))
  expect(first.rows.map(row => row.reference.role).sort()).toEqual(["role:context", "role:exception", "role:subject"])
  expect(new Set(first.rows.map(row => row.reference.target)).size).toBe(1)
  expect(first.headers).toEqual(expect.arrayContaining(f.native.map(({ key, metadata }) => ({ key, metadata }))))
  const shapes = readFileSync(resolve(root, "schemas/HSWM_CANONICAL_ATOM_V2_RDF_PROJECTION_SHACL_1_0.ttl"))
  const shacl = await Effect.runPromise(validateNativeHypergraphShacl(f.projection, shapes))
  expect(shacl.conforms).toBe(true)
  expect(shacl.datasetSha256).toBe(f.projection.manifest.rdfSha256)
})

it("rejects RDF cardinality, graph, datatype, identity and backlink corruption", () => {
  const f = fixture(), text = new TextDecoder().decode(f.projection.rdf.nquads)
  const variants = [
    text.replace('"role:subject"', '"role:subject"@ko'),
    text.replace('/graph/schema>', '/graph/wrong>'),
    text.replace('"0"^^<http://www.w3.org/2001/XMLSchema#nonNegativeInteger>', '"9"^^<http://www.w3.org/2001/XMLSchema#nonNegativeInteger>'),
    text.split("\n").filter(line => !line.includes(`${vocab}hasTypedReference`)).join("\n"),
    text.replace(`${vocab}sourceAtom`, `${vocab}unknownPredicate`)
  ]
  for (const value of variants) expect(() => readRdf(f.projection, new TextEncoder().encode(value))).toThrow()
})

it.runIf(process.env["HSWM_RUN_SEMANTIC_LEAN"] === "1")("compares real RDF with Lean across arity changes and rejects lost or forged graph information", () => {
  const positive = [1, 2, 3, 4].map((arity, index) => wire(fixture(arity, index)))
  const f = fixture(), original = wire(f)
  const rdf = new TextDecoder().decode(f.projection.rdf.nquads)
  positive.push(wire(f, new TextEncoder().encode(rdf.trimEnd().split("\n").reverse().join("\n") + "\n")))
  const bad: ReturnType<typeof wire>[] = []
  const mutate = (change: (w: ReturnType<typeof wire>) => void) => { const value = structuredClone(original); change(value); bad.push(value) }
  for (const field of ["kind", "kindForm", "responsibilityOwner", "contentMediaType", "contentSha256", "provenanceMode", "evidenceSha256"] as const) mutate(w => { w.headers[0]!.metadata[field] = "changed" })
  mutate(w => { w.headers[0]!.metadata.contentByteLength++ })
  mutate(w => { w.headers[0]!.metadata.provenanceSource = "missing" })
  mutate(w => { w.headers.pop() })
  mutate(w => { w.headers.push(w.headers[0]!) })
  mutate(w => { w.atoms.push(w.atoms[0]!) })
  mutate(w => { w.rows.pop() })
  mutate(w => { w.rows.push(w.rows[0]!) })
  mutate(w => { w.rows[0]!.ordinal = 99 })
  mutate(w => { w.rows[0]!.source = "orphan" })
  mutate(w => { w.rows[0]!.reference.target = "absent" })
  mutate(w => { w.rows[0]!.reference.referenceType = "unknown" })
  mutate(w => { w.rows[0]!.reference.role = "unknown" })
  mutate(w => { const role = w.rows[0]!.reference.role; w.rows[0]!.reference.role = w.rows[1]!.reference.role; w.rows[1]!.reference.role = role })
  const changedRoleRdf = wire(f, new TextEncoder().encode(rdf.replace('"role:subject"', '"role:changed"')))
  bad.push(changedRoleRdf)
  const results = checkLean([...positive, ...bad])
  expect(results.slice(0, positive.length).every(result => result.matches)).toBe(true)
  expect(results.slice(positive.length).every(result => !result.matches)).toBe(true)
  expect(results.every(result => !result.admissionProved && !result.fullCanonicalStateProved)).toBe(true)
  // Schema-invalid or missing information is never repaired with a default.
  const negative = structuredClone(original); negative.rows[0]!.ordinal = -1
  expect(() => checkLean([negative])).toThrow()
}, 30000)
