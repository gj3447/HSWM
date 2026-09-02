import { createHash } from "node:crypto"
import { createRequire } from "node:module"

import { expect, it } from "@effect/vitest"
import { Either } from "effect"
import { Parser } from "n3"

import {
  canonicalAtomV2EnvelopeBytes,
  canonicalAtomV2SchemaContentBytes,
  describeCanonicalAtomV2Envelope,
  type CanonicalAtomV2WriteContentBinding
} from "../src/canonical-atom-v2-content-bound.js"
import { makeCanonicalAtomV2ContentDescriptor } from "../src/canonical-atom-v2-content.js"
import {
  makeCanonicalAtomV2AcceptedReceipt,
  initialCanonicalAtomV2State
} from "../src/canonical-atom-v2-domain.js"
import {
  HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
  type CanonicalAtomV2,
  type CanonicalAtomV2Content,
  type CanonicalAtomV2Key,
  type CommitCanonicalAtomsV2Command,
  type HSWMCanonicalSchemaV2
} from "../src/canonical-atom-v2-schema.js"
import {
  canonicalAtomV2RdfProjectionBytes,
  compileCanonicalAtomV2RdfProjection,
  decodeCanonicalAtomV2RdfProjectionBytes,
  verifyCanonicalAtomV2RdfProjection,
  type CanonicalAtomV2RdfProjection,
  type CanonicalAtomV2RdfProjectionSource
} from "../src/canonical-atom-v2-rdf-projection.js"
import {
  applyCanonicalAtomV2StateJournalCommit,
  applyCanonicalAtomV2StateJournalGenesis,
  canonicalAtomV2StateJournalRecordBytes,
  describeCanonicalAtomV2StateJournalRecord,
  makeCanonicalAtomV2StateJournalCommit,
  makeCanonicalAtomV2StateJournalGenesis
} from "../src/canonical-atom-v2-state-journal.js"

const VERSION = "hswm:test:rdf-projection:v2"
const rdfCanonize = createRequire(import.meta.url)("rdf-canonize") as {
  readonly canonize: (
    input: string,
    options: {
      readonly algorithm: "RDFC-1.0"
      readonly inputFormat: "application/n-quads"
      readonly maxWorkFactor: number
      readonly rejectURDNA2015: true
    }
  ) => Promise<string>
}
const sha = (value: string): string => createHash("sha256").update(value).digest("hex")
const utf8 = (value: string): Uint8Array => new TextEncoder().encode(value)
const right = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw new Error("fixture construction failed")
  return value.right
}

const schema: HSWMCanonicalSchemaV2 = {
  _tag: "HSWMCanonicalSchemaV2",
  contractVersion: HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  schemaVersion: VERSION,
  scientificStatus: "UNJUDGED",
  bootstrapTrustStatement: "A bounded RDF projection fixture.",
  owners: [{ address: "owner:graph", obligation: "Own graph atom recovery accountability." }],
  kinds: [
    { kind: "kind:entity", form: "ENTITY", revisionPolicy: "SINGLETON", allowedOwners: ["owner:graph"], minimumArity: 0, referenceContracts: [] },
    {
      kind: "kind:relation", form: "RELATION", revisionPolicy: "SINGLETON", allowedOwners: ["owner:graph"], minimumArity: 2,
      referenceContracts: [{
        referenceType: "reference:member",
        roles: [
          { role: "role:left", targetKinds: ["kind:entity"], minimum: 1, maximum: 1 },
          { role: "role:right", targetKinds: ["kind:entity"], minimum: 1, maximum: 1 }
        ]
      }]
    }
  ]
}

const key = (atomUid: string): CanonicalAtomV2Key => ({ schemaVersion: VERSION, lineageId: "lineage:main", atomUid, revisionId: 0 })
const content = (text: string): CanonicalAtomV2Content => ({ mediaType: "text/plain", byteLength: utf8(text).byteLength, sha256: sha(text) })
const atom = (atomUid: string, kind: "kind:entity" | "kind:relation", references: CanonicalAtomV2["references"] = []): CanonicalAtomV2 => ({
  _tag: "CanonicalAtomV2", contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  key: key(atomUid), kind, responsibilityOwner: "owner:graph", content: content(atomUid),
  provenance: { mode: "BOOTSTRAP", evidenceSha256: sha(`evidence:${atomUid}`), sourceRef: null }, lifecycle: "ADMITTED", references
})
const binding = (value: CanonicalAtomV2): CanonicalAtomV2WriteContentBinding => ({ key: value.key, payload: value.content, envelope: right(describeCanonicalAtomV2Envelope(value)) })

const fixture = (): { readonly source: CanonicalAtomV2RdfProjectionSource; readonly state: unknown } => {
  const left = atom("atom:left", "kind:entity")
  const rightEntity = atom("atom:right", "kind:entity")
  const relation = atom("atom:relation", "kind:relation", [
    { referenceType: "reference:member", role: "role:left", target: left.key },
    { referenceType: "reference:member", role: "role:right", target: left.key }
  ])
  const genesis = right(makeCanonicalAtomV2StateJournalGenesis("journal:rdf", schema))
  const prior = right(applyCanonicalAtomV2StateJournalGenesis(schema, genesis))
  const descriptor = right(describeCanonicalAtomV2StateJournalRecord(genesis))
  const command: CommitCanonicalAtomsV2Command = {
    _tag: "CommitCanonicalAtomsV2", contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
    transitionId: "transition:projection", expectedStateRevision: 0, schemaVersion: VERSION,
    actorClaim: "actor:writer", authorizationRef: "authorization:reference", scope: "scope:write",
    decidedAt: "2026-09-01T00:00:00.000Z", traceRef: null, readSet: [], writes: [left, relation, rightEntity], provenanceSha256: sha("transition")
  }
  const receipt = makeCanonicalAtomV2AcceptedReceipt(command, 0, 1)
  const envelopes = [left, relation, rightEntity].map((value) => right(canonicalAtomV2EnvelopeBytes(value)))
  const tail = right(makeCanonicalAtomV2StateJournalCommit(schema, { state: prior, descriptor, journalLineageId: "journal:rdf", schema: genesis.schema }, receipt, [left, relation, rightEntity].map(binding), envelopes))
  const applied = right(applyCanonicalAtomV2StateJournalCommit(schema, { state: prior, descriptor, journalLineageId: "journal:rdf", schema: genesis.schema }, tail, envelopes))
  const schemaBytes = right(canonicalAtomV2SchemaContentBytes(schema))
  const schemaDescriptor = right(makeCanonicalAtomV2ContentDescriptor("application/vnd.hswm.canonical-schema-v2+json", schemaBytes))
  return {
    source: {
      journalLineageId: "journal:rdf",
      schemaBinding: { schemaVersion: VERSION, content: schemaDescriptor },
      state: applied.state,
      tailDescriptor: applied.descriptor,
      tailRecordBytes: right(canonicalAtomV2StateJournalRecordBytes(tail))
    },
    state: applied.state
  }
}

it("deterministically compiles and exact-decodes a self-consistent bundle-bound RDF Dataset", () => {
  const { source } = fixture()
  const first = right(compileCanonicalAtomV2RdfProjection(schema, source))
  const second = right(compileCanonicalAtomV2RdfProjection(schema, source))
  expect(first).toEqual(second)
  expect(first.manifest.rdfProfile).toBe("RDF_1_1_N_QUADS_BLANK_NODE_FREE_DETERMINISTIC_PROFILE")
  expect(first.manifest.writeBack).toBe("FORBIDDEN")
  expect(first.manifest.sourceAttestation).toBe("CALLER_SUPPLIED_SELF_CONSISTENT_BUNDLE_NOT_DURABLE_RECOVERY_ATTESTED")
  expect(first.manifest.compiler.implementationBinding).toBe("PROFILE_BOUND_NOT_EXECUTABLE_ARTIFACT_BOUND")
  expect(first.manifest.manifestOmits).toEqual(["RAW_CONTENT_PAYLOAD_BYTES", "FULL_JOURNAL_CHAIN"])
  expect(first.manifest.rdfDatasetOmits).toContain("SCHEMA_CONSTRAINTS")
  const bytes = right(canonicalAtomV2RdfProjectionBytes(first))
  expect(right(decodeCanonicalAtomV2RdfProjectionBytes(schema, source, bytes))).toEqual(first)
})

it("is a fixed point of the independently qualified external RDFC-1.0 processor", async () => {
  const { source } = fixture()
  const projection = right(compileCanonicalAtomV2RdfProjection(schema, source))
  const nquads = new TextDecoder().decode(projection.nquads)
  const canonical = await rdfCanonize.canonize(nquads, {
    algorithm: "RDFC-1.0",
    inputFormat: "application/n-quads",
    maxWorkFactor: 1,
    rejectURDNA2015: true
  })

  expect(projection.manifest.rdfProfile).toBe("RDF_1_1_N_QUADS_BLANK_NODE_FREE_DETERMINISTIC_PROFILE")
  expect(canonical).toBe(nquads)
})

it("preserves a reified relation and duplicate target references with distinct roles and ordinals", async () => {
  const { source } = fixture()
  const projection = right(compileCanonicalAtomV2RdfProjection(schema, source))
  const nquads = new TextDecoder().decode(projection.nquads)
  expect(projection.manifest.counts).toMatchObject({ atomVersions: 3, typedReferences: 2, relationAtomVersions: 1, emittedQuads: 57, namedGraphs: 4 })
  expect(nquads).toContain("role:left")
  expect(nquads).toContain("role:right")
  expect(nquads).toContain("/graph/state>")
  expect(nquads).toContain("/graph/schema>")
  expect(nquads).toContain("/graph/provenance>")
  expect(nquads).toContain("/graph/evidence>")
  expect(sha(nquads)).toBe("fc9a606f33a7ceb5d4cc735986335b5d9c03d7dd740a77c822fa6fa53f65e1e2")
  const quads = await new Promise<ReadonlyArray<{ readonly subject: { readonly termType: string; readonly value: string }; readonly predicate: { readonly termType: string; readonly value: string }; readonly object: { readonly termType: string; readonly value: string }; readonly graph: { readonly termType: string; readonly value: string } }>>((resolve, reject) => {
    const output: Array<{ readonly subject: { readonly termType: string; readonly value: string }; readonly predicate: { readonly termType: string; readonly value: string }; readonly object: { readonly termType: string; readonly value: string }; readonly graph: { readonly termType: string; readonly value: string } }> = []
    new Parser({ format: "N-Quads" }).parse(nquads, (error, quad) => {
      if (error !== null) reject(error)
      else if (quad !== null) output.push(quad)
      else resolve(output)
    })
  })
  expect(quads).toHaveLength(projection.manifest.counts.emittedQuads)
  const compilerProfileSha256 = projection.manifest.compiler.profile.sha256
  expect(new Set(quads.map((quad) => quad.graph.value))).toEqual(new Set([
    `https://hswm.invalid/canonical-atom-v2/rdf/v1/dataset/${source.tailDescriptor.sha256}/${compilerProfileSha256}/graph/state`,
    `https://hswm.invalid/canonical-atom-v2/rdf/v1/dataset/${source.tailDescriptor.sha256}/${compilerProfileSha256}/graph/schema`,
    `https://hswm.invalid/canonical-atom-v2/rdf/v1/dataset/${source.tailDescriptor.sha256}/${compilerProfileSha256}/graph/provenance`,
    `https://hswm.invalid/canonical-atom-v2/rdf/v1/dataset/${source.tailDescriptor.sha256}/${compilerProfileSha256}/graph/evidence`
  ]))
  expect(quads.flatMap((quad) => [quad.subject, quad.predicate, quad.object, quad.graph]).some((term) => term.termType === "BlankNode")).toBe(false)
  expect(quads.filter((quad) => quad.object.value.endsWith("ReifiedRelationAtomVersion"))).toHaveLength(1)
  expect(new Set(quads.filter((quad) => quad.object.value.endsWith("TypedReference")).map((quad) => quad.subject.value))).toHaveLength(2)
})

it("refuses stale schema, state-tail, tampered, and noncanonical projection material", () => {
  const { source } = fixture()
  const projection = right(compileCanonicalAtomV2RdfProjection(schema, source))
  const staleSchema = { ...source, schemaBinding: { ...source.schemaBinding, content: { ...source.schemaBinding.content, sha256: "0".repeat(64) } } }
  const staleTail = { ...source, tailDescriptor: { ...source.tailDescriptor, sha256: "1".repeat(64) } }
  const tampered = { ...projection, manifest: { ...projection.manifest, counts: { ...projection.manifest.counts, atomVersions: 99 } } }
  expect(Either.isLeft(compileCanonicalAtomV2RdfProjection(schema, staleSchema))).toBe(true)
  expect(Either.isLeft(compileCanonicalAtomV2RdfProjection(schema, staleTail))).toBe(true)
  expect(Either.isLeft(verifyCanonicalAtomV2RdfProjection(schema, source, tampered))).toBe(true)
  const bytes = right(canonicalAtomV2RdfProjectionBytes(projection))
  expect(Either.isLeft(decodeCanonicalAtomV2RdfProjectionBytes(schema, source, utf8(` ${new TextDecoder().decode(bytes)}`)))).toBe(true)
})

it("keeps projection state read-only: source changes invalidate rather than write back", () => {
  const { source } = fixture()
  const projection = right(compileCanonicalAtomV2RdfProjection(schema, source))
  const altered = { ...source, state: initialCanonicalAtomV2State(VERSION) }
  expect(projection.manifest.writeBack).toBe("FORBIDDEN")
  expect(Either.isLeft(verifyCanonicalAtomV2RdfProjection(schema, altered, projection))).toBe(true)
})

it("returns refusal values for malformed nested source or projection values", () => {
  const { source } = fixture()
  expect(Either.isLeft(compileCanonicalAtomV2RdfProjection(schema, { ...source, schemaBinding: null } as unknown as CanonicalAtomV2RdfProjectionSource))).toBe(true)
  expect(Either.isLeft(compileCanonicalAtomV2RdfProjection(schema, { ...source, schemaBinding: { ...source.schemaBinding, content: { ...source.schemaBinding.content, injected: true } } } as unknown as CanonicalAtomV2RdfProjectionSource))).toBe(true)
  expect(Either.isLeft(compileCanonicalAtomV2RdfProjection(schema, { ...source, tailDescriptor: null } as unknown as CanonicalAtomV2RdfProjectionSource))).toBe(true)
  expect(Either.isLeft(compileCanonicalAtomV2RdfProjection(schema, { ...source, tailDescriptor: { ...source.tailDescriptor, injected: true } } as unknown as CanonicalAtomV2RdfProjectionSource))).toBe(true)
  expect(Either.isLeft(compileCanonicalAtomV2RdfProjection(schema, { ...source, state: null } as unknown as CanonicalAtomV2RdfProjectionSource))).toBe(true)
  expect(Either.isLeft(canonicalAtomV2RdfProjectionBytes({ manifest: null, nquads: null } as unknown as CanonicalAtomV2RdfProjection))).toBe(true)
  expect(Either.isLeft(decodeCanonicalAtomV2RdfProjectionBytes(schema, source, utf8("{")))).toBe(true)
})
