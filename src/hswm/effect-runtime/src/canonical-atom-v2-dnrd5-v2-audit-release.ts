/**
 * Raw delayed-audit-release record verifier for DNRD-5 v2.
 *
 * This is deliberately a local, raw structural check.  It neither grants a
 * Permit nor proves custody, occurrence, learning, efficacy, or a result.
 */
import { Data, Either } from "effect"

import { canonicalAtomV2EnvelopeBytes } from "./canonical-atom-v2-content-bound.js"
import { makeCanonicalAtomV2AcceptedReceipt, type CanonicalAtomV2State } from "./canonical-atom-v2-domain.js"
import { canonicalAtomV2KeyId, type CanonicalAtomV2, type CanonicalAtomV2Key, type CommitCanonicalAtomsV2Command, type HSWMCanonicalSchemaV2 } from "./canonical-atom-v2-schema.js"
import { applyCanonicalAtomV2StateJournalCommit, canonicalAtomV2StateJournalRecordBytes, canonicalAtomV2StateSha256, describeCanonicalAtomV2StateJournalRecord, type CanonicalAtomV2StateJournalCommit, type CanonicalAtomV2StateJournalRecordDescriptor } from "./canonical-atom-v2-state-journal.js"
import { DNRD5_V2_REFERENCE_TYPE, validateDnrd5V2CanonicalSchema } from "./canonical-atom-v2-dnrd5-v2-schema.js"
import { validateDnrd5V2AtomicBatchChronology, type Dnrd5V2AtomicBatchChronology } from "./canonical-atom-v2-dnrd5-v2-batch-chronology.js"

export const DNRD5_V2_AUDIT_RELEASE_V1 = "hswm-dnrd5-v2-audit-release/v1" as const
export const DNRD5_V2_AUDIT_RELEASE_BOUNDARY = Object.freeze({
  validates: "RAW_DELAYED_AUDIT_RELEASE_TWO_WRITE_JOURNAL_AND_TYPED_STRUCTURAL_CROSS_LINKS",
  doesNotValidate: Object.freeze(["PERMIT", "GLOBAL_CUSTODY_OR_REPLAY_REGISTRY", "OCCURRENCE", "LEARNING", "EFFICACY", "SCIENTIFIC_RESULT"]),
  residual: "Opaque content still cannot prove provider occurrence, arm semantics, delayed timing, or scientific causal claims; those require a later occurrence validator."
} as const)

export type Dnrd5V2AuditReleaseErrorCode = "SCHEMA_INVALID" | "BATCH_INVALID" | "PREDECESSOR_INVALID" | "GRAMMAR_INVALID" | "CROSS_LINK_INVALID" | "RECORD_INVALID" | "DESCRIPTOR_INVALID" | "REPLAY_INVALID"
export class Dnrd5V2AuditReleaseError extends Data.TaggedError("Dnrd5V2AuditReleaseError")<{ readonly code: Dnrd5V2AuditReleaseErrorCode; readonly detail: string }> {}
const fail = (code: Dnrd5V2AuditReleaseErrorCode, detail: string) => Either.left(new Dnrd5V2AuditReleaseError({ code, detail }))
const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)
const bytesSame = (a: Uint8Array, b: Uint8Array) => a.byteLength === b.byteLength && a.every((byte, index) => byte === b[index])
const descriptorSame = (a: CanonicalAtomV2StateJournalRecordDescriptor, b: CanonicalAtomV2StateJournalRecordDescriptor) => a.mediaType === b.mediaType && a.byteLength === b.byteLength && a.sha256 === b.sha256
const id = (key: CanonicalAtomV2Key) => canonicalAtomV2KeyId(key)
const ref = (atom: CanonicalAtomV2, role: string) => atom.references.filter((row) => row.referenceType === DNRD5_V2_REFERENCE_TYPE && row.role === `role:dnrd5:v2:${role}`)
/** Exact-cardinality helpers deliberately do not silently choose a reference. */
const one = (atom: CanonicalAtomV2, role: string) => { const rows = ref(atom, role); return rows.length === 1 ? rows[0] : undefined }
const fourDistinct = (atom: CanonicalAtomV2, role: string) => {
  const rows = ref(atom, role)
  return rows.length === 4 && new Set(rows.map((row) => id(row.target))).size === 4 ? rows : undefined
}
const sameTargetSet = (left: ReadonlyArray<{ readonly target: CanonicalAtomV2Key }>, right: ReadonlyArray<{ readonly target: CanonicalAtomV2Key }>) => left.length === right.length && new Set(left.map((row) => id(row.target))).size === new Set(right.map((row) => id(row.target))).size && left.every((row) => right.some((other) => id(other.target) === id(row.target)))
const preAtom = (state: CanonicalAtomV2State, key: CanonicalAtomV2Key) => state.atoms.find((atom) => id(atom.key) === id(key))

export interface Dnrd5V2AuditReleaseInput {
  readonly schema: HSWMCanonicalSchemaV2
  readonly preState: CanonicalAtomV2State
  readonly predecessor: { readonly descriptor: CanonicalAtomV2StateJournalRecordDescriptor; readonly journalLineageId: string; readonly schemaContentSha256: string }
  readonly command: CommitCanonicalAtomsV2Command
  readonly record: CanonicalAtomV2StateJournalCommit
  readonly recordBytes: Uint8Array
  readonly recordDescriptor: CanonicalAtomV2StateJournalRecordDescriptor
  readonly envelopes: ReadonlyArray<Uint8Array>
  /** Bounded supplied scope only; global replay/custody remains out of scope. */
  readonly usedAuditReleaseRecordDescriptorSha256s: ReadonlyArray<string>
}
export interface Dnrd5V2AuditReleaseValidated {
  readonly status: "RAW_AUDIT_RELEASE_STRUCTURALLY_VALIDATED_NOT_PERMIT_OR_OCCURRENCE"
  readonly topology: Dnrd5V2AtomicBatchChronology
  readonly nextState: CanonicalAtomV2State
  readonly auditReleaseRecordDescriptor: CanonicalAtomV2StateJournalRecordDescriptor
}

const auditCrossLinks = (preState: CanonicalAtomV2State, evidence: CanonicalAtomV2, audit: CanonicalAtomV2): Either.Either<void, Dnrd5V2AuditReleaseError> => {
  const block = one(audit, "block"), assignment = one(audit, "assignment"), outcome = one(audit, "outcome"), escrow = one(audit, "escrow"), evaluatorCapability = one(audit, "evaluator-capability"), releaseCapability = one(audit, "release-capability"), consumption = one(audit, "evidence-consumption")
  const trajectories = fourDistinct(audit, "probe-trajectory"), outcomes = fourDistinct(audit, "probe-outcome"), releases = fourDistinct(audit, "evaluator-release")
  if ([block, assignment, outcome, escrow, evaluatorCapability, releaseCapability, consumption, trajectories, outcomes, releases].some((value) => value === undefined)) return fail("GRAMMAR_INVALID", "audit release must have its exact singleton and four-way references")
  const auditTrajectories = trajectories!, auditOutcomes = outcomes!, auditReleases = releases!
  if (id(consumption!.target) !== id(evidence.key)) return fail("CROSS_LINK_INVALID", "audit release must bind the same-batch evidence consumption")
  const purpose = one(evidence, "purpose")
  if (purpose === undefined || id(purpose.target) !== id(releaseCapability!.target)) return fail("CROSS_LINK_INVALID", "evidence purpose must be the audit release's distinct release capability")
  const capability = preAtom(preState, releaseCapability!.target), evaluator = preAtom(preState, evaluatorCapability!.target), blockAtom = preAtom(preState, block!.target)
  const assignmentAtom = preAtom(preState, assignment!.target)
  if (blockAtom?.kind !== "hswm:dnrd5:v2:block_spec" || capability === undefined || capability.kind !== "hswm:dnrd5:v2:audit_release_capability" || id(one(capability, "block")?.target ?? audit.key) !== id(block!.target) || assignmentAtom?.kind !== "hswm:dnrd5:v2:block_assignment" || id(one(assignmentAtom, "block-spec")?.target ?? audit.key) !== id(block!.target)) return fail("CROSS_LINK_INVALID", "audit release capability and assignment must bind the audit block")
  const capCommitment = one(capability, "commitment"), capPolicy = one(capability, "policy"), capAuthorization = one(capability, "authorization"), capIssuance = one(capability, "capability"), capRevocation = one(capability, "revocation")
  if ([capCommitment, capPolicy, capAuthorization, capIssuance, capRevocation].some((value) => value === undefined) || id(one(blockAtom, "evaluator")?.target ?? audit.key) !== id(capCommitment!.target) || evaluator?.kind !== "hswm:dnrd5:v2:evaluator_capability" || id(one(evaluator, "commitment")?.target ?? audit.key) !== id(capCommitment!.target) || id(one(evaluator, "capability")?.target ?? audit.key) !== id(capIssuance!.target) || id(one(evaluator, "authorization")?.target ?? audit.key) !== id(capAuthorization!.target) || id(one(evaluator, "revocation")?.target ?? audit.key) !== id(capRevocation!.target)) return fail("CROSS_LINK_INVALID", "audit evaluator capability must share the selected block's evaluator and release-capability authority/commitment chain")
  const policyAtom = preAtom(preState, capPolicy!.target), authorizationAtom = preAtom(preState, capAuthorization!.target), issuanceAtom = preAtom(preState, capIssuance!.target), revocationAtom = preAtom(preState, capRevocation!.target)
  if (policyAtom?.kind !== "hswm:dnrd5:v2:permit_policy" || authorizationAtom?.kind !== "hswm:dnrd5:v2:authorization_decision" || issuanceAtom?.kind !== "hswm:dnrd5:v2:capability_issuance" || revocationAtom?.kind !== "hswm:dnrd5:v2:revocation_status" || id(one(authorizationAtom, "policy")?.target ?? audit.key) !== id(policyAtom.key) || id(one(issuanceAtom, "authorization")?.target ?? audit.key) !== id(authorizationAtom.key) || id(one(issuanceAtom, "policy")?.target ?? audit.key) !== id(policyAtom.key) || id(one(revocationAtom, "authorization")?.target ?? audit.key) !== id(authorizationAtom.key) || id(one(revocationAtom, "capability")?.target ?? audit.key) !== id(issuanceAtom.key)) return fail("CROSS_LINK_INVALID", "audit release authority atoms must form one internally closed policy/authorization/capability/revocation chain")
  const evidenceGrant = one(evidence, "grant"), evidenceCapability = one(evidence, "capability"), evidenceRevocation = one(evidence, "revocation"), grant = evidenceGrant === undefined ? undefined : preAtom(preState, evidenceGrant.target)
  if (evidenceGrant === undefined || evidenceCapability === undefined || evidenceRevocation === undefined || id(evidenceCapability.target) !== id(capIssuance!.target) || id(evidenceRevocation.target) !== id(capRevocation!.target) || grant?.kind !== "hswm:dnrd5:v2:grant_snapshot" || id(one(grant, "policy")?.target ?? audit.key) !== id(capPolicy!.target) || id(one(grant, "authorization")?.target ?? audit.key) !== id(capAuthorization!.target) || id(one(grant, "capability")?.target ?? audit.key) !== id(capIssuance!.target) || id(one(grant, "revocation")?.target ?? audit.key) !== id(capRevocation!.target)) return fail("CROSS_LINK_INVALID", "evidence consumption must share the release-capability authority chain through its grant")
  const trajectoryIds = new Set(auditTrajectories.map((row) => id(row.target)))
  const outcomeTrajectoryIds: string[] = []
  const releaseTrajectoryIds: string[] = []
  const releaseByTrajectory = new Map<string, CanonicalAtomV2>()
  for (const row of auditReleases) {
    const atom = preAtom(preState, row.target); const trajectory = atom === undefined ? undefined : one(atom, "trajectory")
    if (atom?.kind !== "hswm:dnrd5:v2:evaluator_release" || trajectory === undefined || !trajectoryIds.has(id(trajectory.target)) || id(one(atom, "capability")?.target ?? audit.key) !== id(evaluatorCapability!.target) || id(one(atom, "authorization")?.target ?? audit.key) !== id(capAuthorization!.target) || id(one(atom, "revocation")?.target ?? audit.key) !== id(capRevocation!.target)) return fail("CROSS_LINK_INVALID", "every audit evaluator release must bind its exact trajectory and audit authority chain")
    releaseTrajectoryIds.push(id(trajectory.target)); releaseByTrajectory.set(id(trajectory.target), atom)
  }
  for (const row of auditOutcomes) {
    const atom = preAtom(preState, row.target); const trajectory = atom === undefined ? undefined : one(atom, "trajectory"), release = atom === undefined ? undefined : one(atom, "release")
    const trajectoryAtom = trajectory === undefined ? undefined : preAtom(preState, trajectory.target), probe = atom === undefined ? undefined : one(atom, "probe")
    if (atom?.kind !== "hswm:dnrd5:v2:probe_outcome" || trajectory === undefined || release === undefined || probe === undefined || !trajectoryIds.has(id(trajectory.target)) || id(releaseByTrajectory.get(id(trajectory.target))?.key ?? audit.key) !== id(release.target) || trajectoryAtom?.kind !== "hswm:dnrd5:v2:probe_trajectory" || id(one(trajectoryAtom, "probe")?.target ?? audit.key) !== id(probe.target)) return fail("CROSS_LINK_INVALID", "every audit probe outcome must bind its exact trajectory, probe, and matching evaluator release")
    outcomeTrajectoryIds.push(id(trajectory.target))
  }
  if (new Set(outcomeTrajectoryIds).size !== 4 || new Set(releaseTrajectoryIds).size !== 4) return fail("CROSS_LINK_INVALID", "the four probe outcomes and four evaluator releases must each bijectively cover the four audit trajectories")
  const hidden = preAtom(preState, outcome!.target), escrowAtom = preAtom(preState, escrow!.target), sealedTrajectory = hidden === undefined ? undefined : preAtom(preState, one(hidden, "trajectory")?.target ?? audit.key), activation = sealedTrajectory === undefined ? undefined : preAtom(preState, one(sealedTrajectory, "activation")?.target ?? audit.key)
  const hiddenRelease = hidden === undefined ? undefined : preAtom(preState, one(hidden, "release")?.target ?? audit.key)
  const sealedW0 = sealedTrajectory === undefined ? undefined : one(sealedTrajectory, "w0"), sealedContractRef = sealedTrajectory === undefined ? undefined : one(sealedTrajectory, "contract"), sealedContract = sealedContractRef === undefined ? undefined : preAtom(preState, sealedContractRef.target)
  const activationW0 = activation === undefined ? undefined : one(activation, "w0"), activationProbe = activation === undefined ? undefined : one(activation, "probe"), activationProbeAtom = activationProbe === undefined ? undefined : preAtom(preState, activationProbe.target), activationForks = activation === undefined ? undefined : fourDistinct(activation, "fork"), assignmentForks = fourDistinct(assignmentAtom, "fork"), assignmentRandomness = one(assignmentAtom, "randomness"), blockRandomness = one(blockAtom, "randomness"), w0 = activationW0 === undefined ? undefined : preAtom(preState, activationW0.target)
  const forksPointToW0 = activationForks?.every((row) => {
    const fork = preAtom(preState, row.target)
    return fork?.kind === "hswm:dnrd5:v2:fork_incidence" && id(one(fork, "w0")?.target ?? audit.key) === id(activationW0!.target)
  }) === true
  if (hidden?.kind !== "hswm:dnrd5:v2:hidden_outcome" || escrowAtom?.kind !== "hswm:dnrd5:v2:outcome_credit_escrow" || id(one(escrowAtom, "outcome")?.target ?? audit.key) !== id(hidden.key) || id(one(escrowAtom, "capability")?.target ?? audit.key) !== id(capIssuance!.target) || id(one(escrowAtom, "policy")?.target ?? audit.key) !== id(capPolicy!.target) || id(one(hidden, "commitment")?.target ?? audit.key) !== id(capCommitment!.target) || sealedTrajectory?.kind !== "hswm:dnrd5:v2:trajectory_seal" || sealedContract?.kind !== "hswm:dnrd5:v2:trajectory_contract" || id(one(sealedContract, "activation")?.target ?? audit.key) !== id(activation?.key ?? audit.key) || hiddenRelease?.kind !== "hswm:dnrd5:v2:evaluator_release" || id(one(hiddenRelease, "trajectory")?.target ?? audit.key) !== id(sealedTrajectory.key) || id(one(hiddenRelease, "capability")?.target ?? audit.key) !== id(evaluatorCapability!.target) || id(one(hiddenRelease, "authorization")?.target ?? audit.key) !== id(capAuthorization!.target) || id(one(hiddenRelease, "revocation")?.target ?? audit.key) !== id(capRevocation!.target) || activation?.kind !== "hswm:dnrd5:v2:episode_activation" || id(one(activation, "block-spec")?.target ?? audit.key) !== id(block!.target) || id(one(activation, "assignment")?.target ?? audit.key) !== id(assignment!.target) || id(one(activation, "evaluator")?.target ?? audit.key) !== id(capCommitment!.target) || activationProbeAtom?.kind !== "hswm:dnrd5:v2:probe_commitment" || id(one(activationProbeAtom, "block-spec")?.target ?? audit.key) !== id(block!.target) || blockRandomness === undefined || assignmentRandomness === undefined || id(assignmentRandomness.target) !== id(blockRandomness.target) || id(one(activationProbeAtom, "randomness")?.target ?? audit.key) !== id(blockRandomness.target) || activationW0 === undefined || sealedW0 === undefined || id(sealedW0.target) !== id(activationW0.target) || activationForks === undefined || assignmentForks === undefined || !sameTargetSet(activationForks, assignmentForks) || w0?.kind !== "hswm:dnrd5:v2:w0_snapshot" || id(one(w0, "block-spec")?.target ?? audit.key) !== id(block!.target) || !forksPointToW0) return fail("CROSS_LINK_INVALID", "hidden outcome must resolve through the exact trajectory contract, audit evaluator, randomness, assignment, four-fork W0 scope, and authority chain")
  const probeIds: string[] = []
  for (const row of auditTrajectories) { const trajectory = preAtom(preState, row.target); const probe = trajectory === undefined ? undefined : preAtom(preState, one(trajectory, "probe")?.target ?? audit.key); if (trajectory?.kind !== "hswm:dnrd5:v2:probe_trajectory" || probe?.kind !== "hswm:dnrd5:v2:probe_commitment" || id(one(probe, "block-spec")?.target ?? audit.key) !== id(block!.target) || id(one(probe, "randomness")?.target ?? audit.key) !== id(blockRandomness!.target)) return fail("CROSS_LINK_INVALID", "every audit probe trajectory must resolve through a probe committed to the audit block and randomness"); probeIds.push(id(probe.key)) }
  if (new Set(probeIds).size !== 4) return fail("CROSS_LINK_INVALID", "the four audit probe trajectories must resolve to four distinct probe commitments")
  return Either.right(undefined)
}

export const validateDnrd5V2AuditRelease = (input: Dnrd5V2AuditReleaseInput): Either.Either<Dnrd5V2AuditReleaseValidated, Dnrd5V2AuditReleaseError> => {
  if (Either.isLeft(validateDnrd5V2CanonicalSchema(input.schema))) return fail("SCHEMA_INVALID", "requires the exact DNRD-5 v2 schema")
  if (input.record.schema.content.sha256 !== input.predecessor.schemaContentSha256 || input.record.journalLineageId !== input.predecessor.journalLineageId || !descriptorSame(input.record.predecessor, input.predecessor.descriptor) || input.record.stateRevision !== input.preState.revision + 1) return fail("PREDECESSOR_INVALID", "record does not bind the exact immediate predecessor")
  const topology = validateDnrd5V2AtomicBatchChronology(input.schema, input.preState, input.command)
  if (Either.isLeft(topology)) return fail("BATCH_INVALID", `${topology.left.code}: ${topology.left.detail}`)
  if (input.command.writes.length !== 2) return fail("GRAMMAR_INVALID", "audit release command must have exactly two writes")
  const evidence = input.command.writes.find((atom) => atom.kind === "hswm:dnrd5:v2:evidence_seal_consumption")
  const audit = input.command.writes.find((atom) => atom.kind === "hswm:dnrd5:v2:audit_release")
  if (evidence === undefined || audit === undefined) return fail("GRAMMAR_INVALID", "writes must be evidence consumption and audit release")
  const links = auditCrossLinks(input.preState, evidence, audit); if (Either.isLeft(links)) return Either.left(links.left)
  const before = canonicalAtomV2StateSha256(input.preState); const expected = makeCanonicalAtomV2AcceptedReceipt(input.command, input.preState.revision, topology.right.nextState.revision)
  if (Either.isLeft(before) || input.record.previousStateSha256 !== before.right || !same(input.record.receipt, expected)) return fail("RECORD_INVALID", "record does not match exact command/prestate receipt")
  const sorted = [...input.command.writes].sort((a, b) => id(a.key).localeCompare(id(b.key)))
  if (!same(input.record.writeBindings.map((binding) => id(binding.key)), sorted.map((atom) => id(atom.key))) || input.envelopes.length !== 2) return fail("RECORD_INVALID", "record bindings must be exact canonical write order")
  for (let index = 0; index < sorted.length; index += 1) { const expectedEnvelope = canonicalAtomV2EnvelopeBytes(sorted[index]!); if (Either.isLeft(expectedEnvelope) || !bytesSame(expectedEnvelope.right, input.envelopes[index]!)) return fail("RECORD_INVALID", "record envelope bytes differ from exact writes") }
  const applied = applyCanonicalAtomV2StateJournalCommit(input.schema, { state: input.preState, descriptor: input.predecessor.descriptor, journalLineageId: input.predecessor.journalLineageId, schema: input.record.schema }, input.record, input.envelopes)
  if (Either.isLeft(applied) || !same(applied.right.state, topology.right.nextState)) return fail("RECORD_INVALID", "journal replay differs from generic batch replay")
  const bytes = canonicalAtomV2StateJournalRecordBytes(input.record), descriptor = describeCanonicalAtomV2StateJournalRecord(input.record)
  if (Either.isLeft(bytes) || Either.isLeft(descriptor) || !bytesSame(bytes.right, input.recordBytes) || !descriptorSame(descriptor.right, input.recordDescriptor)) return fail("DESCRIPTOR_INVALID", "record bytes/descriptor are not recomputed exactly")
  if (input.usedAuditReleaseRecordDescriptorSha256s.includes(input.recordDescriptor.sha256)) return fail("REPLAY_INVALID", "record descriptor was already used in supplied audit scope")
  return Either.right(Object.freeze({ status: "RAW_AUDIT_RELEASE_STRUCTURALLY_VALIDATED_NOT_PERMIT_OR_OCCURRENCE" as const, topology: topology.right, nextState: applied.right.state, auditReleaseRecordDescriptor: descriptor.right }))
}
