/**
 * Synthetic, source-bound representation rehearsal for open HSWM connectivity.
 *
 * It demonstrates typed composition and bounded external descriptors only.  The
 * payload bytes named by atom content descriptors are deliberately omitted by
 * the RDF/property-graph projection.  This is not a live port, consent check,
 * Permit, canonical-write authority, learning result, or cognition claim.
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

const VERSION = "hswm:open-connectivity-rehearsal:v1"
const DEFAULT_JOURNAL_LINEAGE = "journal:open-connectivity-rehearsal"
const sha256 = (value: string): string => createHash("sha256").update(value).digest("hex")
const utf8 = (value: string): Uint8Array => new TextEncoder().encode(value)
const right = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw new Error("open connectivity rehearsal construction failed")
  return value.right
}

const owners = [
  ["owner:cell-steward", "Own candidate HSWM-cell identity and composition accountability."],
  ["owner:port-custodian", "Own public port descriptors and their host bindings."],
  ["owner:endpoint-custodian", "Own synthetic external endpoint descriptors."],
  ["owner:exchange-custodian", "Own bounded packet and temporary-activation descriptors."],
  ["owner:disposition-custodian", "Own durable connection and disposition descriptors."]
] as const

const entity = (kind: string, owner: string, referenceContracts: HSWMCanonicalSchemaV2["kinds"][number]["referenceContracts"] = []) => ({
  kind, form: "ENTITY" as const, revisionPolicy: "SINGLETON" as const,
  allowedOwners: [owner], minimumArity: 0, referenceContracts
})
const relation = (kind: string, owner: string, minimumArity: number, roles: HSWMCanonicalSchemaV2["kinds"][number]["referenceContracts"][number]["roles"]) => ({
  kind, form: "RELATION" as const, revisionPolicy: "SINGLETON" as const,
  allowedOwners: [owner], minimumArity,
  referenceContracts: [{ referenceType: "reference:member", roles }]
})
const role = (name: string, targetKinds: ReadonlyArray<string>, minimum = 1, maximum = 1) => ({ role: name, targetKinds, minimum, maximum })

const schema = (): HSWMCanonicalSchemaV2 => ({
  _tag: "HSWMCanonicalSchemaV2",
  contractVersion: HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  schemaVersion: VERSION,
  scientificStatus: "UNJUDGED",
  bootstrapTrustStatement: "Synthetic semantic representation rehearsal: bounded connectivity is not a live authority, network validator, learning result, or cognition claim.",
  owners: owners.map(([address, obligation]) => ({ address, obligation })),
  kinds: [
    entity("kind:candidate-hswm-cell", "owner:cell-steward"),
    ...["human-endpoint", "tool-endpoint", "sensor-endpoint", "knowledge-endpoint"].map((name) =>
      entity(`kind:${name}`, "owner:endpoint-custodian")),
    entity("kind:port", "owner:port-custodian", [{
      referenceType: "reference:host", roles: [role("role:host", ["kind:candidate-hswm-cell"])]
    }]),
    entity("kind:observation-packet", "owner:exchange-custodian", [{
      referenceType: "reference:exchange-party", roles: [
        role("role:sender", ["kind:port", "kind:sensor-endpoint"]),
        role("role:receiver", ["kind:port"])
      ]
    }]),
    entity("kind:context-proposal-packet", "owner:exchange-custodian", [{
      referenceType: "reference:exchange-party", roles: [
        role("role:sender", ["kind:port"]),
        role("role:receiver", ["kind:port", "kind:tool-endpoint"])
      ]
    }]),
    entity("kind:temporary-activation", "owner:exchange-custodian", [{
      referenceType: "reference:activation-member", roles: [
        role("role:host", ["kind:candidate-hswm-cell"]),
        role("role:packet", ["kind:observation-packet", "kind:context-proposal-packet"])
      ]
    }]),
    entity("kind:durable-disposition", "owner:disposition-custodian", [{
      referenceType: "reference:disposition-member", roles: [
        role("role:host", ["kind:candidate-hswm-cell"]),
        role("role:port", ["kind:port"])
      ]
    }]),
    relation("kind:composition", "owner:cell-steward", 3, [
      role("role:member", ["kind:candidate-hswm-cell"], 2, 16),
      role("role:composite", ["kind:candidate-hswm-cell"])
    ]),
    relation("kind:lateral-peer-connection", "owner:cell-steward", 2, [
      role("role:left-peer", ["kind:candidate-hswm-cell"]),
      role("role:right-peer", ["kind:candidate-hswm-cell"])
    ]),
    relation("kind:external-nary-binding", "owner:endpoint-custodian", 5, [
      role("role:hswm", ["kind:candidate-hswm-cell"]),
      role("role:human", ["kind:human-endpoint"]),
      role("role:tool", ["kind:tool-endpoint"]),
      role("role:sensor", ["kind:sensor-endpoint"]),
      role("role:knowledge", ["kind:knowledge-endpoint"])
    ])
  ]
})

const key = (atomUid: string): CanonicalAtomV2Key => ({ schemaVersion: VERSION, lineageId: "lineage:open-connectivity-rehearsal", atomUid, revisionId: 0 })
const content = (payload: string): CanonicalAtomV2Content => ({ mediaType: "application/json", byteLength: utf8(payload).byteLength, sha256: sha256(payload) })
const atom = (
  atomUid: string,
  kind: string,
  responsibilityOwner: string,
  payload: string,
  references: CanonicalAtomV2["references"] = []
): CanonicalAtomV2 => ({
  _tag: "CanonicalAtomV2", contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  key: key(atomUid), kind, responsibilityOwner, content: content(payload),
  provenance: { mode: "BOOTSTRAP", evidenceSha256: sha256(`fixture-evidence:${atomUid}`), sourceRef: null },
  lifecycle: "ADMITTED", references
})
const binding = (value: CanonicalAtomV2): CanonicalAtomV2WriteContentBinding => ({ key: value.key, payload: value.content, envelope: right(describeCanonicalAtomV2Envelope(value)) })
const ref = (referenceType: string, roleName: string, target: CanonicalAtomV2): CanonicalAtomV2["references"][number] => ({ referenceType, role: roleName, target: target.key })

/**
 * Build a sealed synthetic snapshot. Each packet's exchange class is retained
 * as its schema kind; sender/receiver references retain its direction. The existing
 * RDF/property-graph projection retains descriptors, hashes, roles, and
 * provenance but deliberately omits the raw payload bytes.
 */
export const makeOpenConnectivityRehearsal = (journalLineageId = DEFAULT_JOURNAL_LINEAGE): {
  readonly schema: HSWMCanonicalSchemaV2
  readonly source: CanonicalAtomV2RdfProjectionSource
} => {
  const activeSchema = schema()
  const alpha = atom("atom:cell-alpha", "kind:candidate-hswm-cell", "owner:cell-steward", '{"candidate":"alpha","claim":"synthetic-cell"}')
  const beta = atom("atom:cell-beta", "kind:candidate-hswm-cell", "owner:cell-steward", '{"candidate":"beta","claim":"synthetic-cell"}')
  const collective = atom("atom:cell-collective", "kind:candidate-hswm-cell", "owner:cell-steward", '{"candidate":"collective","claim":"synthetic-cell"}')
  const macro = atom("atom:cell-macro", "kind:candidate-hswm-cell", "owner:cell-steward", '{"candidate":"macro","claim":"synthetic-cell"}')
  const human = atom("atom:endpoint-human", "kind:human-endpoint", "owner:endpoint-custodian", '{"endpointClass":"human","fixtureConsent":"NOT_LIVE_OR_VALIDATED"}')
  const tool = atom("atom:endpoint-tool", "kind:tool-endpoint", "owner:endpoint-custodian", '{"endpointClass":"tool","fixtureCapability":"DESCRIPTOR_ONLY"}')
  const sensor = atom("atom:endpoint-sensor", "kind:sensor-endpoint", "owner:endpoint-custodian", '{"endpointClass":"sensor","fixtureCapability":"DESCRIPTOR_ONLY"}')
  const knowledge = atom("atom:endpoint-knowledge", "kind:knowledge-endpoint", "owner:endpoint-custodian", '{"endpointClass":"knowledge_projection","fixtureAuthority":"READ_MODEL_ONLY"}')
  const alphaObservationOut = atom("atom:port-alpha-observation-out", "kind:port", "owner:port-custodian", '{"port":"alpha-observation-out","polarity":"out","semanticType":"observation"}', [ref("reference:host", "role:host", alpha)])
  const ingress = atom("atom:port-collective-ingress", "kind:port", "owner:port-custodian", '{"port":"collective-ingress","polarity":"in","semanticType":"observation"}', [ref("reference:host", "role:host", collective)])
  const egress = atom("atom:port-macro-egress", "kind:port", "owner:port-custodian", '{"port":"macro-egress","polarity":"out","semanticType":"context-proposal"}', [ref("reference:host", "role:host", macro)])
  const collectiveContextIn = atom("atom:port-collective-context-in", "kind:port", "owner:port-custodian", '{"port":"collective-context-in","polarity":"in","semanticType":"context-proposal"}', [ref("reference:host", "role:host", collective)])
  const observation = atom("atom:packet-observation", "kind:observation-packet", "owner:exchange-custodian", '{"payload":"synthetic bottom-up observation; not live input","payloadStatus":"FIXTURE_SOURCE_BYTES_ONLY"}', [ref("reference:exchange-party", "role:sender", alphaObservationOut), ref("reference:exchange-party", "role:receiver", ingress)])
  const contextProposal = atom("atom:packet-context-proposal", "kind:context-proposal-packet", "owner:exchange-custodian", '{"payload":"synthetic top-down context; not an instruction or authority","payloadStatus":"FIXTURE_SOURCE_BYTES_ONLY"}', [ref("reference:exchange-party", "role:sender", egress), ref("reference:exchange-party", "role:receiver", collectiveContextIn)])
  const externalObservation = atom("atom:packet-external-observation", "kind:observation-packet", "owner:exchange-custodian", '{"payload":"synthetic sensor boundary observation; not live input","payloadStatus":"FIXTURE_SOURCE_BYTES_ONLY"}', [ref("reference:exchange-party", "role:sender", sensor), ref("reference:exchange-party", "role:receiver", ingress)])
  const externalContextProposal = atom("atom:packet-external-context-proposal", "kind:context-proposal-packet", "owner:exchange-custodian", '{"payload":"synthetic tool boundary context; not an instruction or authority","payloadStatus":"FIXTURE_SOURCE_BYTES_ONLY"}', [ref("reference:exchange-party", "role:sender", egress), ref("reference:exchange-party", "role:receiver", tool)])
  const activation = atom("atom:activation-temporary", "kind:temporary-activation", "owner:exchange-custodian", '{"lifecycle":"temporary","status":"synthetic descriptor only"}', [ref("reference:activation-member", "role:host", collective), ref("reference:activation-member", "role:packet", observation)])
  const disposition = atom("atom:disposition-durable", "kind:durable-disposition", "owner:disposition-custodian", '{"lifecycle":"durable","meaning":"connection disposition descriptor; no weight update or learning claim"}', [ref("reference:disposition-member", "role:host", collective), ref("reference:disposition-member", "role:port", ingress)])
  const localComposition = atom("atom:composition-local", "kind:composition", "owner:cell-steward", '{"composition":"local","fixedLayer":false}', [ref("reference:member", "role:member", alpha), ref("reference:member", "role:member", beta), ref("reference:member", "role:composite", collective)])
  const nestedComposition = atom("atom:composition-nested", "kind:composition", "owner:cell-steward", '{"composition":"nested","fixedLayer":false}', [ref("reference:member", "role:member", collective), ref("reference:member", "role:member", beta), ref("reference:member", "role:composite", macro)])
  const lateral = atom("atom:lateral-alpha-beta", "kind:lateral-peer-connection", "owner:cell-steward", '{"connection":"lateral-peer","fixedLayer":false}', [ref("reference:member", "role:left-peer", alpha), ref("reference:member", "role:right-peer", beta)])
  const externalBinding = atom("atom:binding-external-nary", "kind:external-nary-binding", "owner:endpoint-custodian", '{"binding":"synthetic external n-ary descriptor","permit":"NOT_PRESENT"}', [ref("reference:member", "role:hswm", collective), ref("reference:member", "role:human", human), ref("reference:member", "role:tool", tool), ref("reference:member", "role:sensor", sensor), ref("reference:member", "role:knowledge", knowledge)])
  const atoms = [activation, alpha, alphaObservationOut, beta, collective, collectiveContextIn, contextProposal, disposition, egress, externalBinding, externalContextProposal, externalObservation, human, ingress, knowledge, lateral, localComposition, macro, nestedComposition, observation, sensor, tool].sort((left, right) => Buffer.from(left.key.atomUid).compare(Buffer.from(right.key.atomUid)))
  const genesis = right(makeCanonicalAtomV2StateJournalGenesis(journalLineageId, activeSchema))
  const prior = right(applyCanonicalAtomV2StateJournalGenesis(activeSchema, genesis))
  const descriptor = right(describeCanonicalAtomV2StateJournalRecord(genesis))
  const command: CommitCanonicalAtomsV2Command = {
    _tag: "CommitCanonicalAtomsV2", contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
    transitionId: "transition:open-connectivity-rehearsal", expectedStateRevision: 0, schemaVersion: VERSION,
    actorClaim: "actor:open-connectivity-rehearsal", authorizationRef: "authorization:fixture-reference", scope: "scope:open-connectivity-rehearsal",
    decidedAt: "2026-09-05T00:00:00.000Z", traceRef: null, readSet: [], writes: atoms, provenanceSha256: sha256("transition:open-connectivity-rehearsal")
  }
  const receipt = makeCanonicalAtomV2AcceptedReceipt(command, 0, 1)
  const envelopes = atoms.map((value) => right(canonicalAtomV2EnvelopeBytes(value)))
  const tail = right(makeCanonicalAtomV2StateJournalCommit(activeSchema, { state: prior, descriptor, journalLineageId, schema: genesis.schema }, receipt, atoms.map(binding), envelopes))
  const applied = right(applyCanonicalAtomV2StateJournalCommit(activeSchema, { state: prior, descriptor, journalLineageId, schema: genesis.schema }, tail, envelopes))
  const schemaBytes = right(canonicalAtomV2SchemaContentBytes(activeSchema))
  const schemaDescriptor = right(makeCanonicalAtomV2ContentDescriptor("application/vnd.hswm.canonical-schema-v2+json", schemaBytes))
  return { schema: activeSchema, source: { journalLineageId, schemaBinding: { schemaVersion: VERSION, content: schemaDescriptor }, state: applied.state, tailDescriptor: applied.descriptor, tailRecordBytes: right(canonicalAtomV2StateJournalRecordBytes(tail)) } }
}
