/**
 * A bounded engineering fixture for the Hypergraph Projection Contract.
 *
 * This is deliberately a synthetic journal replay.  It is neither a G0
 * result nor evidence of HSWM learning, cognition, or a canonical write path.
 */
import { createHash } from "node:crypto"

import { Either } from "effect"

import {
  canonicalAtomV2EnvelopeBytes,
  canonicalAtomV2SchemaContentBytes,
  describeCanonicalAtomV2Envelope,
  type CanonicalAtomV2WriteContentBinding
} from "./canonical-atom-v2-content-bound.js"
import { makeCanonicalAtomV2ContentDescriptor } from "./canonical-atom-v2-content.js"
import { makeCanonicalAtomV2AcceptedReceipt } from "./canonical-atom-v2-domain.js"
import {
  HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
  type CanonicalAtomV2,
  type CanonicalAtomV2Content,
  type CanonicalAtomV2Key,
  type CommitCanonicalAtomsV2Command,
  type HSWMCanonicalSchemaV2
} from "./canonical-atom-v2-schema.js"
import type { CanonicalAtomV2RdfProjectionSource } from "./canonical-atom-v2-rdf-projection.js"
import {
  applyCanonicalAtomV2StateJournalCommit,
  applyCanonicalAtomV2StateJournalGenesis,
  canonicalAtomV2StateJournalRecordBytes,
  describeCanonicalAtomV2StateJournalRecord,
  makeCanonicalAtomV2StateJournalCommit,
  makeCanonicalAtomV2StateJournalGenesis
} from "./canonical-atom-v2-state-journal.js"

const VERSION = "hswm:hypergraph-projection-rehearsal:v1"
const DEFAULT_JOURNAL_LINEAGE = "journal:hypergraph-projection-rehearsal"
const sha256 = (value: string): string => createHash("sha256").update(value).digest("hex")
const utf8 = (value: string): Uint8Array => new TextEncoder().encode(value)
const right = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw new Error("bounded hypergraph rehearsal construction failed")
  return value.right
}

const schema = (): HSWMCanonicalSchemaV2 => ({
  _tag: "HSWMCanonicalSchemaV2",
  contractVersion: HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  schemaVersion: VERSION,
  scientificStatus: "UNJUDGED",
  bootstrapTrustStatement: "Synthetic bounded engineering rehearsal for a read-only hypergraph projection.",
  owners: [{ address: "owner:projection-rehearsal", obligation: "Own bounded fixture recovery accountability." }],
  kinds: [
    ...["trajectory", "outcome", "disposition"].map((name) => ({
      kind: `kind:${name}`, form: "ENTITY" as const, revisionPolicy: "SINGLETON" as const,
      allowedOwners: ["owner:projection-rehearsal"], minimumArity: 0, referenceContracts: []
    })),
    {
      kind: "kind:ternary-relation", form: "RELATION", revisionPolicy: "SINGLETON",
      allowedOwners: ["owner:projection-rehearsal"], minimumArity: 3,
      referenceContracts: [{
        referenceType: "reference:rehearsal-member",
        roles: [
          { role: "role:trajectory", targetKinds: ["kind:trajectory", "kind:outcome", "kind:disposition"], minimum: 1, maximum: 1 },
          { role: "role:compared-trajectory", targetKinds: ["kind:trajectory", "kind:outcome", "kind:disposition"], minimum: 1, maximum: 1 },
          { role: "role:outcome", targetKinds: ["kind:trajectory", "kind:outcome", "kind:disposition"], minimum: 1, maximum: 1 }
        ]
      }]
    }
  ]
})

const key = (atomUid: string): CanonicalAtomV2Key => ({ schemaVersion: VERSION, lineageId: "lineage:projection-rehearsal", atomUid, revisionId: 0 })
const content = (text: string): CanonicalAtomV2Content => ({ mediaType: "text/plain", byteLength: utf8(text).byteLength, sha256: sha256(text) })
const atom = (atomUid: string, kind: string, references: CanonicalAtomV2["references"] = [], sourceRef: CanonicalAtomV2Key | null = null): CanonicalAtomV2 => ({
  _tag: "CanonicalAtomV2", contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  key: key(atomUid), kind, responsibilityOwner: "owner:projection-rehearsal", content: content(atomUid),
  provenance: { mode: sourceRef === null ? "BOOTSTRAP" : "DERIVATION", evidenceSha256: sha256(`evidence:${atomUid}`), sourceRef },
  lifecycle: "ADMITTED", references
})
const binding = (value: CanonicalAtomV2): CanonicalAtomV2WriteContentBinding => ({ key: value.key, payload: value.content, envelope: right(describeCanonicalAtomV2Envelope(value)) })

export const makeHypergraphProjectionRehearsal = (journalLineageId = DEFAULT_JOURNAL_LINEAGE): {
  readonly schema: HSWMCanonicalSchemaV2
  readonly source: CanonicalAtomV2RdfProjectionSource
} => {
  const activeSchema = schema()
  const trajectory = atom("atom:trajectory", "kind:trajectory")
  const outcome = atom("atom:outcome", "kind:outcome", [], trajectory.key)
  const disposition = atom("atom:disposition", "kind:disposition", [], trajectory.key)
  const relation = atom("atom:ternary", "kind:ternary-relation", [
    { referenceType: "reference:rehearsal-member", role: "role:trajectory", target: trajectory.key },
    { referenceType: "reference:rehearsal-member", role: "role:compared-trajectory", target: trajectory.key },
    { referenceType: "reference:rehearsal-member", role: "role:outcome", target: outcome.key }
  ], trajectory.key)
  const atoms = [disposition, outcome, relation, trajectory]
  const genesis = right(makeCanonicalAtomV2StateJournalGenesis(journalLineageId, activeSchema))
  const prior = right(applyCanonicalAtomV2StateJournalGenesis(activeSchema, genesis))
  const descriptor = right(describeCanonicalAtomV2StateJournalRecord(genesis))
  const command: CommitCanonicalAtomsV2Command = {
    _tag: "CommitCanonicalAtomsV2", contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
    transitionId: "transition:hypergraph-projection-rehearsal", expectedStateRevision: 0, schemaVersion: VERSION,
    actorClaim: "actor:projection-rehearsal", authorizationRef: "authorization:fixture-reference", scope: "scope:bounded-projection-rehearsal",
    decidedAt: "2026-09-05T00:00:00.000Z", traceRef: null, readSet: [], writes: atoms, provenanceSha256: sha256("transition:hypergraph-projection-rehearsal")
  }
  const receipt = makeCanonicalAtomV2AcceptedReceipt(command, 0, 1)
  const envelopes = atoms.map((value) => right(canonicalAtomV2EnvelopeBytes(value)))
  const tail = right(makeCanonicalAtomV2StateJournalCommit(activeSchema, { state: prior, descriptor, journalLineageId, schema: genesis.schema }, receipt, atoms.map(binding), envelopes))
  const applied = right(applyCanonicalAtomV2StateJournalCommit(activeSchema, { state: prior, descriptor, journalLineageId, schema: genesis.schema }, tail, envelopes))
  const schemaBytes = right(canonicalAtomV2SchemaContentBytes(activeSchema))
  const schemaDescriptor = right(makeCanonicalAtomV2ContentDescriptor("application/vnd.hswm.canonical-schema-v2+json", schemaBytes))
  return {
    schema: activeSchema,
    source: {
      journalLineageId,
      schemaBinding: { schemaVersion: VERSION, content: schemaDescriptor },
      state: applied.state,
      tailDescriptor: applied.descriptor,
      tailRecordBytes: right(canonicalAtomV2StateJournalRecordBytes(tail))
    }
  }
}
