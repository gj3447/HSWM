import { createHash } from "node:crypto"

import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import {
  canonicalAtomV2EnvelopeBytes,
  describeCanonicalAtomV2Envelope,
  type CanonicalAtomV2WriteContentBinding
} from "../src/canonical-atom-v2-content-bound.js"
import {
  initialCanonicalAtomV2State,
  makeCanonicalAtomV2AcceptedReceipt
} from "../src/canonical-atom-v2-domain.js"
import {
  HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
  HSWM_SUPERSEDES_REFERENCE_ROLE,
  HSWM_SUPERSEDES_REFERENCE_TYPE,
  type CanonicalAtomV2,
  type CanonicalAtomV2Content,
  type CanonicalAtomV2Key,
  type CommitCanonicalAtomsV2Command,
  type HSWMCanonicalSchemaV2
} from "../src/canonical-atom-v2-schema.js"
import {
  applyCanonicalAtomV2StateJournalCommit,
  applyCanonicalAtomV2StateJournalGenesis,
  canonicalAtomV2StateJournalRecordBytes,
  decodeCanonicalAtomV2StateJournalRecordBytes,
  describeCanonicalAtomV2StateJournalRecord,
  makeCanonicalAtomV2StateJournalCommit,
  makeCanonicalAtomV2StateJournalGenesis,
  type CanonicalAtomV2StateJournalCommit
} from "../src/canonical-atom-v2-state-journal.js"

const VERSION = "hswm:test:journal:v2"
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
  bootstrapTrustStatement: "A bounded fixture trust statement.",
  owners: [{ address: "owner:atom", obligation: "Own atom recovery accountability." }],
  kinds: [{
    kind: "kind:atom",
    form: "ENTITY",
    revisionPolicy: "LINEAR",
    allowedOwners: ["owner:atom"],
    minimumArity: 0,
    referenceContracts: [{
      referenceType: HSWM_SUPERSEDES_REFERENCE_TYPE,
      roles: [{
        role: HSWM_SUPERSEDES_REFERENCE_ROLE,
        targetKinds: ["kind:atom"],
        minimum: 0,
        maximum: 1
      }]
    }]
  }]
}

const key = (revisionId = 0): CanonicalAtomV2Key => ({
  schemaVersion: VERSION,
  lineageId: "lineage:atom",
  atomUid: "atom:one",
  revisionId
})

const content = (value: string): CanonicalAtomV2Content => ({
  mediaType: "text/plain",
  byteLength: utf8(value).byteLength,
  sha256: sha(value)
})

const atom = (revisionId: number, body: string): CanonicalAtomV2 => ({
  _tag: "CanonicalAtomV2",
  contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  key: key(revisionId),
  kind: "kind:atom",
  responsibilityOwner: "owner:atom",
  content: content(body),
  provenance: revisionId === 0
    ? { mode: "BOOTSTRAP", evidenceSha256: "a".repeat(64), sourceRef: null }
    : { mode: "DERIVATION", evidenceSha256: "b".repeat(64), sourceRef: key(0) },
  lifecycle: "ADMITTED",
  references: revisionId === 0 ? [] : [{
    referenceType: HSWM_SUPERSEDES_REFERENCE_TYPE,
    role: HSWM_SUPERSEDES_REFERENCE_ROLE,
    target: key(0)
  }]
})

const binding = (value: CanonicalAtomV2): CanonicalAtomV2WriteContentBinding => ({
  key: value.key,
  payload: value.content,
  envelope: right(describeCanonicalAtomV2Envelope(value))
})

const command = (
  value: CanonicalAtomV2,
  expectedStateRevision: number,
  readSet: ReadonlyArray<CanonicalAtomV2Key> = []
): CommitCanonicalAtomsV2Command => ({
  _tag: "CommitCanonicalAtomsV2",
  contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
  transitionId: `transition:${value.key.revisionId}`,
  expectedStateRevision,
  schemaVersion: VERSION,
  actorClaim: "actor:writer",
  authorizationRef: "authorization:reference",
  scope: "scope:write",
  decidedAt: `2026-08-26T02:00:0${value.key.revisionId}.000Z`,
  traceRef: null,
  readSet,
  writes: [value],
  provenanceSha256: "c".repeat(64)
})

it("makes exact canonical genesis bytes and rejects a noncanonical journal spelling", () => {
  const genesis = right(makeCanonicalAtomV2StateJournalGenesis("journal:main", schema))
  const bytes = right(canonicalAtomV2StateJournalRecordBytes(genesis))
  expect(right(decodeCanonicalAtomV2StateJournalRecordBytes(bytes))).toEqual(genesis)
  expect(Either.isLeft(decodeCanonicalAtomV2StateJournalRecordBytes(utf8(` ${new TextDecoder().decode(bytes)}`)))).toBe(true)
  expect(right(applyCanonicalAtomV2StateJournalGenesis(schema, genesis))).toEqual(
    initialCanonicalAtomV2State(VERSION)
  )
})

it("applies an immutable predecessor-bound two-step journal only from exact envelopes", () => {
  const genesis = right(makeCanonicalAtomV2StateJournalGenesis("journal:main", schema))
  const genesisState = right(applyCanonicalAtomV2StateJournalGenesis(schema, genesis))
  const genesisDescriptor = right(describeCanonicalAtomV2StateJournalRecord(genesis))
  const first = atom(0, "one")
  const firstCommand = command(first, 0)
  const firstReceipt = makeCanonicalAtomV2AcceptedReceipt(firstCommand, 0, 1)
  const firstRecord = right(makeCanonicalAtomV2StateJournalCommit(
    schema,
    { state: genesisState, descriptor: genesisDescriptor, journalLineageId: "journal:main", schema: genesis.schema },
    firstReceipt,
    [binding(first)],
    [right(canonicalAtomV2EnvelopeBytes(first))]
  ))
  const firstApplied = right(applyCanonicalAtomV2StateJournalCommit(
    schema,
    { state: genesisState, descriptor: genesisDescriptor, journalLineageId: "journal:main", schema: genesis.schema },
    firstRecord,
    [right(canonicalAtomV2EnvelopeBytes(first))]
  ))
  const second = atom(1, "two")
  const secondCommand = command(second, 1, [key(0)])
  const secondReceipt = makeCanonicalAtomV2AcceptedReceipt(secondCommand, 1, 2)
  const secondRecord = right(makeCanonicalAtomV2StateJournalCommit(
    schema,
    { state: firstApplied.state, descriptor: firstApplied.descriptor, journalLineageId: "journal:main", schema: genesis.schema },
    secondReceipt,
    [binding(second)],
    [right(canonicalAtomV2EnvelopeBytes(second))]
  ))
  const secondApplied = right(applyCanonicalAtomV2StateJournalCommit(
    schema,
    { state: firstApplied.state, descriptor: firstApplied.descriptor, journalLineageId: "journal:main", schema: genesis.schema },
    secondRecord,
    [right(canonicalAtomV2EnvelopeBytes(second))]
  ))
  expect(secondApplied.state.revision).toBe(2)
  expect(secondApplied.state.atoms.map((item) => item.key.revisionId)).toEqual([0, 1])
  expect(secondRecord.durability).toBe("LOCAL_PREDECESSOR_BOUND_JOURNAL_V1_NOT_CANONICAL_PERMIT_NOT_LEARNING")
})

it("fails closed on a forged receipt, binding, state digest, or noncanonical envelope", () => {
  const genesis = right(makeCanonicalAtomV2StateJournalGenesis("journal:main", schema))
  const state = right(applyCanonicalAtomV2StateJournalGenesis(schema, genesis))
  const descriptor = right(describeCanonicalAtomV2StateJournalRecord(genesis))
  const value = atom(0, "one")
  const receipt = makeCanonicalAtomV2AcceptedReceipt(command(value, 0), 0, 1)
  const record = right(makeCanonicalAtomV2StateJournalCommit(
    schema,
    { state, descriptor, journalLineageId: "journal:main", schema: genesis.schema },
    receipt,
    [binding(value)],
    [value]
  ))
  const prior = { state, descriptor, journalLineageId: "journal:main", schema: genesis.schema }
  const forgedReceipt = { ...record, receipt: { ...record.receipt, transitionId: "transition:forged" } } as CanonicalAtomV2StateJournalCommit
  const forgedBinding = { ...record, writeBindings: [{ ...record.writeBindings[0]!, payload: { ...record.writeBindings[0]!.payload, sha256: "d".repeat(64) } }] } as CanonicalAtomV2StateJournalCommit
  const forgedDigest = { ...record, resultingStateSha256: "e".repeat(64) } as CanonicalAtomV2StateJournalCommit
  const envelope = right(canonicalAtomV2EnvelopeBytes(value))
  const noncanonicalEnvelope = utf8(` ${new TextDecoder().decode(envelope)}`)
  for (const candidate of [forgedReceipt, forgedBinding, forgedDigest]) {
    expect(Either.isLeft(applyCanonicalAtomV2StateJournalCommit(schema, prior, candidate, [value]))).toBe(true)
  }
  expect(Either.isLeft(applyCanonicalAtomV2StateJournalCommit(schema, prior, record, [noncanonicalEnvelope]))).toBe(true)
})
