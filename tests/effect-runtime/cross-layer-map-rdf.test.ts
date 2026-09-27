import { createHash } from "node:crypto"
import { readFileSync as readFile } from "node:fs"
import { fileURLToPath } from "node:url"

import { expect, it } from "@effect/vitest"
import { Effect, Either } from "effect"
import { Parser } from "n3"

import {
  canonicalAtomV2EnvelopeBytes,
  canonicalAtomV2SchemaContentBytes,
  describeCanonicalAtomV2Envelope,
  type CanonicalAtomV2WriteContentBinding
} from "../../src/hswm/effect-runtime/src/canonical-atom-v2-content-bound.js"
import { makeCanonicalAtomV2ContentDescriptor } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-content.js"
import { makeCanonicalAtomV2AcceptedReceipt } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-domain.js"
import {
  HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
  canonicalAtomV2KeyId,
  type CanonicalAtomV2,
  type CanonicalAtomV2Key,
  type CommitCanonicalAtomsV2Command
} from "../../src/hswm/effect-runtime/src/canonical-atom-v2-schema.js"
import { compileCanonicalAtomV2RdfProjection } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-rdf-projection.js"
import {
  applyCanonicalAtomV2StateJournalCommit,
  applyCanonicalAtomV2StateJournalGenesis,
  canonicalAtomV2StateJournalRecordBytes,
  describeCanonicalAtomV2StateJournalRecord,
  makeCanonicalAtomV2StateJournalCommit,
  makeCanonicalAtomV2StateJournalGenesis
} from "../../src/hswm/effect-runtime/src/canonical-atom-v2-state-journal.js"
import {
  CROSS_LAYER_MAP_PARTICIPANT_KIND,
  CROSS_LAYER_MAP_PARTICIPANT_MEDIA_TYPE,
  CROSS_LAYER_MAP_RELATION_KIND,
  CROSS_LAYER_MAP_ROLE_REFERENCE_TYPE,
  createCrossLayerMapSchema
} from "../../src/hswm/effect-runtime/src/cross-layer-map-runtime.js"
import { kgSha256, type KgBundleProjection } from "../../src/hswm/effect-runtime/src/native-kg-bundle-domain.js"
import { queryKgBundle, validateKgShacl } from "../../src/hswm/effect-runtime/src/native-kg-standards.js"

const utf8 = new TextEncoder()
const schemaVersion = "hswm:test:cross-layer-map-rdf:v1"
const lineageId = "lineage:cross-layer-map-rdf:test"
const journalLineage = "journal:cross-layer-map-rdf:test"
const owner = "owner:cross-layer-map:test"
const sha256 = (value: string): string => createHash("sha256").update(value).digest("hex")

const right = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw new Error(`cross-layer RDF fixture construction failed: ${JSON.stringify(value.left)}`)
  return value.right
}

const key = (atomUid: string, revisionId = 0): CanonicalAtomV2Key =>
  ({ schemaVersion, lineageId, atomUid, revisionId })

const descriptor = (mediaType: string, payload: string) =>
  right(makeCanonicalAtomV2ContentDescriptor(mediaType, utf8.encode(payload)))

const atom = (
  atomUid: string,
  kind: string,
  payload: string,
  references: CanonicalAtomV2["references"] = [],
  revisionId = 0,
  sourceRef: CanonicalAtomV2Key | null = null
): CanonicalAtomV2 => ({
  _tag: "CanonicalAtomV2",
  contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  key: key(atomUid, revisionId),
  kind,
  responsibilityOwner: owner,
  content: descriptor(kind === CROSS_LAYER_MAP_RELATION_KIND
    ? "application/vnd.hswm.llm-semantic-relation-v1+json"
    : CROSS_LAYER_MAP_PARTICIPANT_MEDIA_TYPE, payload),
  provenance: sourceRef === null
    ? { mode: "OBSERVATION", evidenceSha256: sha256(`evidence:${atomUid}`), sourceRef: null }
    : { mode: "DERIVATION", evidenceSha256: sha256(`evidence:${atomUid}:${revisionId}`), sourceRef },
  lifecycle: "ADMITTED",
  references
})

const bind = (value: CanonicalAtomV2): CanonicalAtomV2WriteContentBinding => ({
  key: value.key,
  payload: value.content,
  envelope: right(describeCanonicalAtomV2Envelope(value))
})

const fixture = () => {
  const schema = createCrossLayerMapSchema(schemaVersion, owner)
  const subject = atom("participant:subject", CROSS_LAYER_MAP_PARTICIPANT_KIND, '{"subject":"toy-physical-observable"}')
  // This MapSpec is deliberately content-addressed only in RDF. It must never
  // become visible merely because a graph projection is queried.
  const context = atom("participant:context", CROSS_LAYER_MAP_PARTICIPANT_KIND, '{"mapSpec":{"source":"physics","target":"semantic","timeUnit":"ms","loss":"declared"}}')
  const evidence = atom("participant:evidence", CROSS_LAYER_MAP_PARTICIPANT_KIND, '{"observation":"synthetic","uncertainty":"unknown"}')
  const exception = atom("participant:exception", CROSS_LAYER_MAP_PARTICIPANT_KIND, '{"exception":"not-a-causal-correspondence-claim"}')
  const relationV0 = atom("relation:cross-layer-map", CROSS_LAYER_MAP_RELATION_KIND, '{"semanticText":"fixture relation","disposition":"predict-under-context","uncertainty":"declared-unknown","exceptionRefs":["participant:exception"],"trace":null,"outcome":null}', [
    { referenceType: CROSS_LAYER_MAP_ROLE_REFERENCE_TYPE, role: "subject", target: subject.key },
    { referenceType: CROSS_LAYER_MAP_ROLE_REFERENCE_TYPE, role: "context", target: context.key },
    { referenceType: CROSS_LAYER_MAP_ROLE_REFERENCE_TYPE, role: "evidence", target: evidence.key },
    { referenceType: CROSS_LAYER_MAP_ROLE_REFERENCE_TYPE, role: "exception", target: exception.key }
  ])
  const relation = atom("relation:cross-layer-map", CROSS_LAYER_MAP_RELATION_KIND, '{"semanticText":"fixture relation","disposition":"predict-under-context","uncertainty":"declared-unknown","exceptionRefs":["participant:exception"],"trace":null,"outcome":null}', [
    { referenceType: "hswm:reference:supersedes", role: "hswm:role:predecessor", target: relationV0.key },
    { referenceType: CROSS_LAYER_MAP_ROLE_REFERENCE_TYPE, role: "subject", target: subject.key },
    { referenceType: CROSS_LAYER_MAP_ROLE_REFERENCE_TYPE, role: "context", target: context.key },
    { referenceType: CROSS_LAYER_MAP_ROLE_REFERENCE_TYPE, role: "evidence", target: evidence.key },
    { referenceType: CROSS_LAYER_MAP_ROLE_REFERENCE_TYPE, role: "exception", target: exception.key }
  ], 1, relationV0.key)
  const initialAtoms = [subject, context, evidence, exception, relationV0].sort((left, right) => {
    const atom = Buffer.from(left.key.atomUid).compare(Buffer.from(right.key.atomUid))
    return atom === 0 ? left.key.revisionId - right.key.revisionId : atom
  })
  const genesis = right(makeCanonicalAtomV2StateJournalGenesis(journalLineage, schema))
  const prior = right(applyCanonicalAtomV2StateJournalGenesis(schema, genesis))
  const genesisDescriptor = right(describeCanonicalAtomV2StateJournalRecord(genesis))
  const initialCommand: CommitCanonicalAtomsV2Command = {
    _tag: "CommitCanonicalAtomsV2", contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
    transitionId: "cross-layer-map-rdf:fixture:initial", expectedStateRevision: 0, schemaVersion,
    actorClaim: "fixture:cross-layer-map", authorizationRef: "authorization:fixture", scope: "scope:fixture",
    decidedAt: "2026-09-27T00:00:00.000Z", traceRef: null, readSet: [], writes: initialAtoms,
    provenanceSha256: sha256("cross-layer-map-rdf:fixture:initial")
  }
  const initialReceipt = makeCanonicalAtomV2AcceptedReceipt(initialCommand, 0, 1)
  const initialEnvelopes = right(Either.all(initialAtoms.map(canonicalAtomV2EnvelopeBytes)))
  const initialBindings = initialAtoms.map(bind)
  const initialTail = right(makeCanonicalAtomV2StateJournalCommit(schema, { state: prior, descriptor: genesisDescriptor, journalLineageId: journalLineage, schema: genesis.schema }, initialReceipt, initialBindings, initialEnvelopes))
  const initialApplied = right(applyCanonicalAtomV2StateJournalCommit(schema, { state: prior, descriptor: genesisDescriptor, journalLineageId: journalLineage, schema: genesis.schema }, initialTail, initialEnvelopes))
  const successorCommand: CommitCanonicalAtomsV2Command = {
    _tag: "CommitCanonicalAtomsV2", contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
    transitionId: "cross-layer-map-rdf:fixture:successor", expectedStateRevision: 1, schemaVersion,
    actorClaim: "fixture:cross-layer-map", authorizationRef: "authorization:fixture", scope: "scope:fixture",
    decidedAt: "2026-09-27T00:00:01.000Z", traceRef: null, readSet: [relationV0.key, subject.key, context.key, evidence.key, exception.key], writes: [relation],
    provenanceSha256: sha256("cross-layer-map-rdf:fixture:successor")
  }
  const successorReceipt = makeCanonicalAtomV2AcceptedReceipt(successorCommand, 1, 2)
  const successorEnvelopes = right(Either.all([relation].map(canonicalAtomV2EnvelopeBytes)))
  const successorTail = right(makeCanonicalAtomV2StateJournalCommit(schema, { state: initialApplied.state, descriptor: initialApplied.descriptor, journalLineageId: journalLineage, schema: genesis.schema }, successorReceipt, [bind(relation)], successorEnvelopes))
  const applied = right(applyCanonicalAtomV2StateJournalCommit(schema, { state: initialApplied.state, descriptor: initialApplied.descriptor, journalLineageId: journalLineage, schema: genesis.schema }, successorTail, successorEnvelopes))
  const schemaBytes = right(canonicalAtomV2SchemaContentBytes(schema))
  const schemaContent = right(makeCanonicalAtomV2ContentDescriptor("application/vnd.hswm.canonical-schema-v2+json", schemaBytes))
  const tailBytes = right(canonicalAtomV2StateJournalRecordBytes(successorTail))
  return right(compileCanonicalAtomV2RdfProjection(schema, {
    journalLineageId: journalLineage,
    schemaBinding: { schemaVersion, content: schemaContent },
    state: applied.state,
    tailDescriptor: applied.descriptor,
    tailRecordBytes: tailBytes
  }))
}

const researchFile = (relative: string): Uint8Array =>
  new Uint8Array(readFile(fileURLToPath(new URL(`../../_research/cross_layer_map_v1/${relative}`, import.meta.url))))

const viewOf = (nquads: Uint8Array): KgBundleProjection => ({
  nquads,
  descriptor: { dataset: { sha256: kgSha256(nquads), byteLength: nquads.byteLength } },
  provO: new Uint8Array()
})

it.effect("projects the existing semantic relation as role-preserving RDF and keeps MapSpec payload bytes absent", () => {
  const projection = fixture()
  const nquads = new TextDecoder().decode(projection.nquads)
  expect(new Parser({ format: "N-Quads" }).parse(nquads)).not.toHaveLength(0)
  expect(projection.manifest.mapping).toBe("ROLE_PRESERVING_REIFIED_TYPED_REFERENCE")
  expect(projection.manifest.rdfDatasetOmits).toContain("RAW_CONTENT_PAYLOAD_BYTES")
  expect(projection.manifest.writeBack).toBe("FORBIDDEN")
  expect(nquads).not.toContain("toy-physical-observable")
  expect(nquads).not.toContain("not-a-causal-correspondence-claim")

  const view = viewOf(projection.nquads)
  return Effect.gen(function* () {
    const rows = yield* queryKgBundle(view, new TextDecoder().decode(researchFile("queries/current-map-roles.rq")))
    expect(Array.isArray(rows)).toBe(true)
    const values = (rows as ReadonlyArray<Readonly<Record<string, { readonly value: string } | null>>>)
    expect(values).toHaveLength(4)
    expect(values.map((row) => row["role"]?.value)).toEqual(["subject", "context", "evidence", "exception"])
    // The current relation is revision 1, whose supersedes reference occupies
    // ordinal 0. The projection preserves source reference-array indices.
    expect(values.map((row) => row["ordinal"]?.value)).toEqual(["1", "2", "3", "4"])
    expect(values.every((row) => /^[0-9a-f]{64}$/.test(row["participantContentSha256"]?.value ?? ""))).toBe(true)
    expect(values.every((row) => row["participantProvenanceMode"]?.value === "OBSERVATION")).toBe(true)
    const shacl = yield* validateKgShacl(view, researchFile("shapes/map-profile.ttl"))
    expect(shacl.conforms).toBe(true)
    expect(shacl.profile).toBe("SHACL_1_0_CORE_NO_IMPORTS_NO_EXTENSIONS")
  })
})

it.effect("rejects a parseable RDF view when a role participant loses its content digest", () => {
  const projection = fixture()
  const contextAtom = encodeURIComponent(canonicalAtomV2KeyId(key("participant:context")))
  const altered = new TextDecoder().decode(projection.nquads)
    .split("\n")
    .filter((line) => !(line.includes(`/atom/${contextAtom}>`) && line.includes("/contentSha256>")))
    .join("\n")
  const bytes = utf8.encode(altered)
  expect(new Parser({ format: "N-Quads" }).parse(altered)).not.toHaveLength(0)
  return validateKgShacl(viewOf(bytes), researchFile("shapes/map-profile.ttl")).pipe(
    Effect.tap((result) => Effect.sync(() => {
      expect(result.conforms).toBe(false)
      expect(result.profile).toBe("SHACL_1_0_CORE_NO_IMPORTS_NO_EXTENSIONS")
    }))
  )
})
