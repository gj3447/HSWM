import { expect, it } from "@effect/vitest"
import { Either } from "effect"
import { createHash } from "node:crypto"

import { makeCanonicalAtomV2ContentDescriptor } from "../src/canonical-atom-v2-content.js"
import { canonicalAtomV2EnvelopeBytes, snapshotCanonicalAtomV2WriteContentBinding } from "../src/canonical-atom-v2-content-bound.js"
import { initialCanonicalAtomV2State, makeCanonicalAtomV2AcceptedReceipt } from "../src/canonical-atom-v2-domain.js"
import { canonicalAtomV2KeyId, type CanonicalAtomV2, type CanonicalAtomV2Key, type CommitCanonicalAtomsV2Command } from "../src/canonical-atom-v2-schema.js"
import { applyCanonicalAtomV2StateJournalCommit, canonicalAtomV2StateJournalRecordBytes, describeCanonicalAtomV2StateJournalRecord, makeCanonicalAtomV2StateJournalCommit, makeCanonicalAtomV2StateJournalGenesis } from "../src/canonical-atom-v2-state-journal.js"
import { DNRD5_V2_OWNER_ROLE_BY_KIND, DNRD5_V2_REFERENCE_TYPE, DNRD5_V2_SCHEMA_VERSION, makeDnrd5V2CanonicalSchema, type Dnrd5V2CanonicalAtomKind } from "../src/canonical-atom-v2-dnrd5-v2-schema.js"
import { validateDnrd5V2RecordBoundEffect } from "../src/canonical-atom-v2-dnrd5-v2-record-bound-effect.js"
import { canonicalDnrd5V2ReceiptPayloadBytes, DNRD5_V2_RECEIPT_PAYLOAD_MEDIA_TYPE, DNRD5_V2_RECEIPT_SEAL_V1, validateDnrd5V2ReceiptSeal } from "../src/canonical-atom-v2-dnrd5-v2-receipt-seal.js"
import {
  DNRD5_V2_AUTHORITY_PAYLOAD_V1,
  DNRD5_V2_AUTHORIZATION_DECISION_MEDIA_TYPE,
  DNRD5_V2_CAPABILITY_ISSUANCE_MEDIA_TYPE,
  DNRD5_V2_GRANT_SNAPSHOT_MEDIA_TYPE,
  DNRD5_V2_PERMIT_POLICY_MEDIA_TYPE,
  DNRD5_V2_REVOCATION_STATUS_MEDIA_TYPE,
  type Dnrd5V2AuthorityChain,
  type Dnrd5V2AuthorityPhase,
  type Dnrd5V2AuthorityStateInput
} from "../src/canonical-atom-v2-dnrd5-v2-authority.js"
import { canonicalJsonBytes, decodeCanonicalJsonBytes } from "../src/canonical-atom-v2-json.js"

const right = <A, E>(v: Either.Either<A, E>): A => { if (Either.isLeft(v)) throw new Error(JSON.stringify(v.left)); return v.right }
const schema = makeDnrd5V2CanonicalSchema(); const sha = (x: string) => x.repeat(64)
const key = (atomUid: string): CanonicalAtomV2Key => ({ schemaVersion: DNRD5_V2_SCHEMA_VERSION, lineageId: "lineage:receipt-seal", atomUid, revisionId: 0 })
const atom = (uid: string, kind: Dnrd5V2CanonicalAtomKind, refs: ReadonlyArray<CanonicalAtomV2> = []): CanonicalAtomV2 => ({ _tag: "CanonicalAtomV2", contractVersion: "hswm-canonical-atom/v2", key: key(uid), kind: `hswm:dnrd5:v2:${kind}`, responsibilityOwner: `owner:dnrd5:v2:${DNRD5_V2_OWNER_ROLE_BY_KIND[kind]}`, content: { mediaType: "application/json", byteLength: 2, sha256: sha("a") }, provenance: refs.length ? { mode: "DERIVATION", evidenceSha256: sha("b"), sourceRef: refs[0]!.key } : { mode: "BOOTSTRAP", evidenceSha256: sha("b"), sourceRef: null }, lifecycle: "ADMITTED", references: [] })
const rel = (uid: string, kind: Dnrd5V2CanonicalAtomKind, pairs: ReadonlyArray<readonly [string, CanonicalAtomV2]>): CanonicalAtomV2 => ({ ...atom(uid, kind), provenance: { mode: "DERIVATION", evidenceSha256: sha("b"), sourceRef: pairs[0]![1].key }, references: pairs.map(([role, source]) => ({ referenceType: DNRD5_V2_REFERENCE_TYPE, role: `role:dnrd5:v2:${role}`, target: source.key })) })
const command = (revision: number, writes: ReadonlyArray<CanonicalAtomV2>, readSet: ReadonlyArray<CanonicalAtomV2Key> = [], id = `transition:receipt-seal:${revision}`): CommitCanonicalAtomsV2Command => ({ _tag: "CommitCanonicalAtomsV2", contractVersion: "hswm-canonical-transition/v2", transitionId: id, expectedStateRevision: revision, schemaVersion: DNRD5_V2_SCHEMA_VERSION, actorClaim: "principal:test", authorizationRef: "authorization:test", scope: "scope:test", decidedAt: "2026-08-28T12:00:00.000Z", traceRef: null, readSet, writes, provenanceSha256: sha("c") })
const bound = (writes: ReadonlyArray<CanonicalAtomV2>) => { const sorted = [...writes].sort((a, b) => canonicalAtomV2KeyId(a.key).localeCompare(canonicalAtomV2KeyId(b.key))); const bytes = sorted.map((a) => right(canonicalAtomV2EnvelopeBytes(a))); return { bytes, bindings: sorted.map((a, i) => snapshotCanonicalAtomV2WriteContentBinding({ key: a.key, payload: a.content, envelope: { mediaType: "application/vnd.hswm.canonical-atom-v2+json", byteLength: bytes[i]!.byteLength, sha256: createHash("sha256").update(bytes[i]!).digest("hex") } })) } }

interface AuthorityContent {
  readonly atom: CanonicalAtomV2
  readonly bytes: Uint8Array
}

const authorityPrincipals = {
  actor: "principal:test",
  authorizer: "principal:test:authorizer",
  canonicalStateCustodian: "principal:test:state-custodian",
  restoreCustodian: "principal:test:restore-custodian",
  creditAdjudicator: "principal:test:credit-adjudicator",
  authorizationRecordCustodian: "principal:test:authorization-custodian"
} as const

const authorityContent = (
  uid: string,
  kind: Dnrd5V2CanonicalAtomKind,
  mediaType: string,
  payload: object,
  pairs: ReadonlyArray<readonly [string, CanonicalAtomV2]> = []
): AuthorityContent => {
  const bytes = right(canonicalJsonBytes(payload))
  const descriptor = right(makeCanonicalAtomV2ContentDescriptor(mediaType, bytes))
  const base = pairs.length === 0 ? atom(uid, kind) : rel(uid, kind, pairs)
  return { atom: { ...base, content: descriptor }, bytes }
}

const receiptAuthority = (
  label: string,
  phase: Dnrd5V2AuthorityPhase,
  purpose: CanonicalAtomV2
): Dnrd5V2AuthorityChain => {
  const policy = authorityContent(
    `${label}-policy`,
    "permit_policy",
    DNRD5_V2_PERMIT_POLICY_MEDIA_TYPE,
    {
      contractVersion: DNRD5_V2_AUTHORITY_PAYLOAD_V1,
      scope: "scope:test",
      allowedActors: ["principal:test"],
      allowedPhases: [phase],
      allowMainReceiptPairing: true,
      generation: 1
    }
  )
  const authorization = authorityContent(
    `${label}-authorization`,
    "authorization_decision",
    DNRD5_V2_AUTHORIZATION_DECISION_MEDIA_TYPE,
    {
      contractVersion: DNRD5_V2_AUTHORITY_PAYLOAD_V1,
      scope: "scope:test",
      actor: "principal:test",
      authorizer: authorityPrincipals.authorizer,
      authorizationRef: `authorization-record:${label}`,
      recordCustodian: authorityPrincipals.authorizationRecordCustodian,
      phase,
      policyAtomKeyId: canonicalAtomV2KeyId(policy.atom.key),
      policyGeneration: 1,
      decidedAt: "2026-08-28T11:00:00.000Z",
      notBefore: "2026-08-28T11:00:00.000Z",
      expiresAt: "2026-08-28T13:00:00.000Z",
      generation: 1
    },
    [["policy", policy.atom]]
  )
  const capability = authorityContent(
    `${label}-capability`,
    "capability_issuance",
    DNRD5_V2_CAPABILITY_ISSUANCE_MEDIA_TYPE,
    {
      contractVersion: DNRD5_V2_AUTHORITY_PAYLOAD_V1,
      scope: "scope:test",
      actor: "principal:test",
      phase,
      purposeAtomKeyId: canonicalAtomV2KeyId(purpose.key),
      capabilityId: "authorization:test",
      nonceSha256: createHash("sha256").update(`nonce:${label}`).digest("hex"),
      policyAtomKeyId: canonicalAtomV2KeyId(policy.atom.key),
      policyGeneration: 1,
      authorizationAtomKeyId: canonicalAtomV2KeyId(authorization.atom.key),
      authorizationRef: `authorization-record:${label}`,
      authorizationGeneration: 1,
      generation: 1,
      issuedAt: "2026-08-28T11:30:00.000Z",
      expiresAt: "2026-08-28T12:30:00.000Z"
    },
    [["authorization", authorization.atom], ["policy", policy.atom]]
  )
  const revocation = authorityContent(
    `${label}-revocation`,
    "revocation_status",
    DNRD5_V2_REVOCATION_STATUS_MEDIA_TYPE,
    {
      contractVersion: DNRD5_V2_AUTHORITY_PAYLOAD_V1,
      status: "CHECKED_NOT_REVOKED",
      checkedAt: "2026-08-28T12:00:00.000Z",
      authorizationAtomKeyId: canonicalAtomV2KeyId(authorization.atom.key),
      authorizationRef: `authorization-record:${label}`,
      capabilityAtomKeyId: canonicalAtomV2KeyId(capability.atom.key),
      capabilityId: "authorization:test",
      policyGeneration: 1,
      authorizationGeneration: 1,
      capabilityGeneration: 1
    },
    [["authorization", authorization.atom], ["capability", capability.atom]]
  )
  const grant = authorityContent(
    `${label}-grant`,
    "grant_snapshot",
    DNRD5_V2_GRANT_SNAPSHOT_MEDIA_TYPE,
    {
      contractVersion: DNRD5_V2_AUTHORITY_PAYLOAD_V1,
      policyAtomKeyId: canonicalAtomV2KeyId(policy.atom.key),
      authorizationAtomKeyId: canonicalAtomV2KeyId(authorization.atom.key),
      authorizationRef: `authorization-record:${label}`,
      capabilityAtomKeyId: canonicalAtomV2KeyId(capability.atom.key),
      capabilityId: "authorization:test",
      revocationAtomKeyId: canonicalAtomV2KeyId(revocation.atom.key),
      policyGeneration: 1,
      authorizationGeneration: 1,
      capabilityGeneration: 1
    },
    [
      ["policy", policy.atom],
      ["authorization", authorization.atom],
      ["capability", capability.atom],
      ["revocation", revocation.atom]
    ]
  )
  return { phase, policy, authorization, capability, revocation, grant }
}

const authorityAtState = (
  state: Dnrd5V2AuthorityStateInput["state"],
  chain: Dnrd5V2AuthorityChain
): Dnrd5V2AuthorityStateInput => ({
  _tag: "Dnrd5V2AuthorityStateInput",
  contractVersion: DNRD5_V2_AUTHORITY_PAYLOAD_V1,
  evaluatedAt: "2026-08-28T12:00:00.000Z",
  principals: authorityPrincipals,
  state,
  chain
})

it("binds raw ADMIT effect and receipt journal records, rejecting forged links", () => {
  const policy = atom("policy", "permit_policy"), randomness = atom("randomness", "study_randomness"), evaluator = atom("evaluator", "evaluator_commitment")
  const block = rel("block", "block_spec", [["randomness", randomness], ["evaluator", evaluator]]), probe = rel("probe", "probe_commitment", [["block-spec", block], ["randomness", randomness]]), placebo = rel("placebo", "placebo_commitment", [["block-spec", block], ["randomness", randomness]])
  const w0 = rel("w0", "w0_snapshot", [["block-spec", block]]), forks = [1, 2, 3, 4].map((n) => rel(`fork${n}`, "fork_incidence", [["w0", w0]])), assignment = rel("assignment", "block_assignment", [["randomness", randomness], ["block-spec", block], ...forks.map((x) => ["fork", x] as const)])
  const activation = rel("activation", "episode_activation", [["block-spec", block], ["probe", probe], ["w0", w0], ...forks.map((x) => ["fork", x] as const), ["assignment", assignment], ["evaluator", evaluator]]), contract = rel("contract", "trajectory_contract", [["activation", activation]]), trajectory = rel("trajectory", "trajectory_seal", [["activation", activation], ["contract", contract], ["w0", w0]])
  const placeboReceipt = rel("placebo-receipt", "placebo_receipt", [["commitment", placebo], ["randomness", randomness]]), feedback = rel("feedback", "feedback_assignment", [["fork", forks[0]!], ["assignment", assignment], ["source", placeboReceipt]]), proposal = rel("proposal", "revision_proposal", [["trajectory", trajectory], ["feedback", feedback]]), validation = rel("validation", "candidate_validation", [["proposal", proposal]])
  const authorization = rel("authorization", "authorization_decision", [["policy", policy]]), capability = rel("capability", "capability_issuance", [["authorization", authorization], ["policy", policy]]), revocation = rel("revocation", "revocation_status", [["authorization", authorization], ["capability", capability]]), grant = rel("grant", "grant_snapshot", [["policy", policy], ["authorization", authorization], ["capability", capability], ["revocation", revocation]])
  const credit = rel("credit", "credit_decision", [["trajectory", trajectory], ["credit-source", placeboReceipt], ["feedback", feedback], ["proposal", proposal], ["grant", grant]]), decision = rel("decision", "revision_admission_decision", [["block", block], ["assignment", assignment], ["fork", forks[0]!], ["proposal", proposal], ["validation", validation], ["credit", credit], ["grant", grant], ["authorization", authorization], ["capability", capability], ["revocation", revocation]]), restorePolicy = rel("restore-policy", "restore_policy", [["policy", policy], ["capability", capability]])
  const alternateAuthorization = rel("authorization-alternate", "authorization_decision", [["policy", policy]]), alternateCapability = rel("capability-alternate", "capability_issuance", [["authorization", alternateAuthorization], ["policy", policy]]), alternateRevocation = rel("revocation-alternate", "revocation_status", [["authorization", alternateAuthorization], ["capability", alternateCapability]]), alternateGrant = rel("grant-alternate", "grant_snapshot", [["policy", policy], ["authorization", alternateAuthorization], ["capability", alternateCapability], ["revocation", alternateRevocation]])
  // Schema-valid alternatives are intentionally present before the effect:
  // cross-wiring them must reach the receipt identity tuple, not kind checking.
  const alternateDecision = rel("decision-alternate", "revision_admission_decision", [["block", block], ["assignment", assignment], ["fork", forks[1]!], ["proposal", proposal], ["validation", validation], ["credit", credit], ["grant", grant], ["authorization", authorization], ["capability", capability], ["revocation", revocation]])
  const alternateConsumption = rel("consumption-alternate", "capability_consumption", [["grant", grant], ["capability", capability], ["revocation", revocation], ["decision", alternateDecision]])
  const alternateDisposition = rel("disposition-alternate", "macro_disposition", [["proposal", proposal], ["revision-admission-decision", alternateDecision], ["restore-policy", restorePolicy], ["effect-consumption", alternateConsumption]])
  const admitEvidenceAuthority = receiptAuthority("evidence-admit", "RECEIPT_ADMIT", decision)
  const restoreEvidenceAuthority = receiptAuthority(
    "evidence-restore",
    "RECEIPT_RESTORE",
    { key: key("rollback-decision") } as CanonicalAtomV2
  )
  const wrongPhaseAuthority = receiptAuthority("evidence-wrong-phase", "MAIN_ADMIT", decision)
  const authorityAtoms = [
    admitEvidenceAuthority,
    restoreEvidenceAuthority,
    wrongPhaseAuthority
  ].flatMap((chain) => [
    chain.policy.atom,
    chain.authorization.atom,
    chain.capability.atom,
    chain.revocation.atom,
    chain.grant.atom
  ])
  const genesis = right(makeCanonicalAtomV2StateJournalGenesis("journal:receipt-seal", schema)), genesisDescriptor = right(describeCanonicalAtomV2StateJournalRecord(genesis))
  const bootstrap = command(0, [policy, randomness, evaluator, block, probe, placebo, w0, ...forks, assignment, activation, contract, trajectory, placeboReceipt, feedback, proposal, validation, authorization, capability, revocation, grant, credit, decision, restorePolicy, alternateAuthorization, alternateCapability, alternateRevocation, alternateGrant, alternateDecision, alternateConsumption, alternateDisposition, ...authorityAtoms]); const bootstrapBound = bound(bootstrap.writes)
  const bootstrapRecord = right(makeCanonicalAtomV2StateJournalCommit(schema, { state: initialCanonicalAtomV2State(DNRD5_V2_SCHEMA_VERSION), descriptor: genesisDescriptor, journalLineageId: genesis.journalLineageId, schema: genesis.schema }, makeCanonicalAtomV2AcceptedReceipt(bootstrap, 0, 1), bootstrapBound.bindings, bootstrapBound.bytes)); const bootstrapState = right(applyCanonicalAtomV2StateJournalCommit(schema, { state: initialCanonicalAtomV2State(DNRD5_V2_SCHEMA_VERSION), descriptor: genesisDescriptor, journalLineageId: genesis.journalLineageId, schema: genesis.schema }, bootstrapRecord, bootstrapBound.bytes))
  const consumption = rel("consumption", "capability_consumption", [["grant", grant], ["capability", capability], ["revocation", revocation], ["decision", decision]]), disposition = rel("disposition", "macro_disposition", [["proposal", proposal], ["revision-admission-decision", decision], ["restore-policy", restorePolicy], ["effect-consumption", consumption]])
  const effectCommand = command(1, [disposition, consumption], [grant.key, capability.key, revocation.key, decision.key, proposal.key, restorePolicy.key], "transition:receipt-seal:effect"), effectBound = bound(effectCommand.writes)
  const effectRecord = right(makeCanonicalAtomV2StateJournalCommit(schema, { state: bootstrapState.state, descriptor: bootstrapState.descriptor, journalLineageId: genesis.journalLineageId, schema: genesis.schema }, makeCanonicalAtomV2AcceptedReceipt(effectCommand, 1, 2), effectBound.bindings, effectBound.bytes)), effectBytes = right(canonicalAtomV2StateJournalRecordBytes(effectRecord)), effectDescriptor = right(describeCanonicalAtomV2StateJournalRecord(effectRecord))
  const mainEffectInput = { schema, preState: bootstrapState.state, predecessor: { descriptor: bootstrapState.descriptor, journalLineageId: genesis.journalLineageId, schemaContentSha256: genesis.schema.content.sha256 }, command: effectCommand, record: effectRecord, recordBytes: effectBytes, recordDescriptor: effectDescriptor, envelopes: effectBound.bytes, usedRecordDescriptorSha256s: [] }
  const validated = right(validateDnrd5V2RecordBoundEffect(mainEffectInput))
  const payload = { contractVersion: DNRD5_V2_RECEIPT_SEAL_V1, receiptKind: "REVISION" as const, precedingEffectRecordDescriptorSha256: effectDescriptor.sha256, postcommitReceiptIdentity: validated.deterministicFuturePostcommitReceiptIdentity, decisionAtomKeyId: canonicalAtomV2KeyId(decision.key), effectConsumptionAtomKeyId: canonicalAtomV2KeyId(consumption.key), effectAtomKeyId: canonicalAtomV2KeyId(disposition.key) }; const payloadBytes = right(canonicalDnrd5V2ReceiptPayloadBytes(payload)), payloadDescriptor = right(makeCanonicalAtomV2ContentDescriptor(DNRD5_V2_RECEIPT_PAYLOAD_MEDIA_TYPE, payloadBytes))
  const evidence = rel("evidence", "evidence_seal_consumption", [["grant", admitEvidenceAuthority.grant.atom], ["capability", admitEvidenceAuthority.capability.atom], ["revocation", admitEvidenceAuthority.revocation.atom], ["purpose", decision]]), receipt = { ...rel(`receipt:${validated.deterministicFuturePostcommitReceiptIdentity}`, "revision_transition_receipt", [["decision", decision], ["effect-consumption", consumption], ["successor", disposition], ["evidence-consumption", evidence]]), content: payloadDescriptor }
  const receiptCommand = command(2, [evidence, receipt], [admitEvidenceAuthority.grant.atom.key, admitEvidenceAuthority.capability.atom.key, admitEvidenceAuthority.revocation.atom.key, decision.key, consumption.key, disposition.key], "transition:receipt-seal:receipt"), receiptBound = bound(receiptCommand.writes)
  const receiptRecord = right(makeCanonicalAtomV2StateJournalCommit(schema, { state: validated.nextState, descriptor: effectDescriptor, journalLineageId: genesis.journalLineageId, schema: genesis.schema }, makeCanonicalAtomV2AcceptedReceipt(receiptCommand, 2, 3), receiptBound.bindings, receiptBound.bytes)), receiptBytes = right(canonicalAtomV2StateJournalRecordBytes(receiptRecord)), receiptDescriptor = right(describeCanonicalAtomV2StateJournalRecord(receiptRecord))
  const input = { schema, preState: validated.nextState, predecessor: { descriptor: effectDescriptor, journalLineageId: genesis.journalLineageId, schemaContentSha256: genesis.schema.content.sha256 }, precedingEffect: mainEffectInput, command: receiptCommand, evidenceAuthority: authorityAtState(validated.nextState, admitEvidenceAuthority), record: receiptRecord, recordBytes: receiptBytes, recordDescriptor: receiptDescriptor, envelopes: receiptBound.bytes, receiptPayloadBytes: payloadBytes, receiptPayloadDescriptor: payloadDescriptor, usedReceiptRecordDescriptorSha256s: [] }
  const revisionSeal = right(validateDnrd5V2ReceiptSeal(input)); expect(revisionSeal.status).toBe("RAW_RECEIPT_SEAL_VALIDATED_NOT_PERMIT_OR_OCCURRENCE")
  expect(Either.isLeft(validateDnrd5V2ReceiptSeal({ ...input, receiptPayloadBytes: Uint8Array.from([...payloadBytes, 10]) }))).toBe(true)
  expect(Either.isLeft(validateDnrd5V2ReceiptSeal({ ...input, receiptPayloadDescriptor: { ...payloadDescriptor, sha256: sha("d") } }))).toBe(true)
  expect(Either.isLeft(validateDnrd5V2ReceiptSeal({ ...input, predecessor: { ...input.predecessor, descriptor: genesisDescriptor } }))).toBe(true)
  expect(Either.isLeft(validateDnrd5V2ReceiptSeal({ ...input, predecessor: { ...input.predecessor, journalLineageId: "journal:forged" } }))).toBe(true)
  expect(Either.isLeft(validateDnrd5V2ReceiptSeal({ ...input, precedingEffect: { ...mainEffectInput, record: { ...effectRecord, resultingStateSha256: sha("e") } } }))).toBe(true)
  for (const commandHeaderCrossWire of [
    { actorClaim: "principal:test:other" },
    { authorizationRef: "authorization:test:other" },
    { scope: "scope:test:other" },
    { decidedAt: "2026-08-28T12:00:01.000Z" }
  ]) {
    const result = validateDnrd5V2ReceiptSeal({
      ...input,
      command: { ...receiptCommand, ...commandHeaderCrossWire }
    })
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) expect(result.left.code).toBe("GRAMMAR_INVALID")
  }
  const wrongPurpose = { ...evidence, references: evidence.references.map((r) => r.role === "role:dnrd5:v2:purpose" ? { ...r, target: proposal.key } : r) }; expect(Either.isLeft(validateDnrd5V2ReceiptSeal({ ...input, command: { ...receiptCommand, writes: [wrongPurpose, receipt] } }))).toBe(true)
  const wrongEffect = { ...receipt, references: receipt.references.map((r) => r.role === "role:dnrd5:v2:successor" ? { ...r, target: proposal.key } : r) }; expect(Either.isLeft(validateDnrd5V2ReceiptSeal({ ...input, command: { ...receiptCommand, writes: [evidence, wrongEffect] } }))).toBe(true)
  const alternateEvidence = { ...evidence, references: evidence.references.map((r) => r.role === "role:dnrd5:v2:purpose" ? { ...r, target: alternateDecision.key } : r) }
  const alternateDecisionReceipt = { ...receipt, references: receipt.references.map((r) => r.role === "role:dnrd5:v2:decision" ? { ...r, target: alternateDecision.key } : r) }
  const decisionCrossWire = validateDnrd5V2ReceiptSeal({ ...input, command: { ...receiptCommand, readSet: [...receiptCommand.readSet, alternateDecision.key], writes: [alternateEvidence, alternateDecisionReceipt] } })
  expect(Either.isLeft(decisionCrossWire)).toBe(true); if (Either.isLeft(decisionCrossWire)) expect(decisionCrossWire.left.code).toBe("GRAMMAR_INVALID")
  const alternateSuccessorReceipt = { ...receipt, references: receipt.references.map((r) => r.role === "role:dnrd5:v2:successor" ? { ...r, target: alternateDisposition.key } : r) }
  const successorCrossWire = validateDnrd5V2ReceiptSeal({ ...input, command: { ...receiptCommand, readSet: [...receiptCommand.readSet, alternateDisposition.key], writes: [evidence, alternateSuccessorReceipt] } })
  expect(Either.isLeft(successorCrossWire)).toBe(true); if (Either.isLeft(successorCrossWire)) expect(successorCrossWire.left.code).toBe("IDENTITY_INVALID")
  // This alternate authority chain is schema-valid and in prestate.  It must
  // reach the receipt-seal grammar check, rather than be rejected merely as a
  // missing/wrong-kind reference.
  const alternateAuthorityEvidence = { ...evidence, references: evidence.references.map((r) => r.role === "role:dnrd5:v2:grant" ? { ...r, target: alternateGrant.key } : r.role === "role:dnrd5:v2:capability" ? { ...r, target: alternateCapability.key } : r.role === "role:dnrd5:v2:revocation" ? { ...r, target: alternateRevocation.key } : r) }
  const authorityCrossWire = validateDnrd5V2ReceiptSeal({ ...input, command: { ...receiptCommand, readSet: [...receiptCommand.readSet, alternateGrant.key, alternateCapability.key, alternateRevocation.key], writes: [alternateAuthorityEvidence, receipt] } })
  expect(Either.isLeft(authorityCrossWire)).toBe(true); if (Either.isLeft(authorityCrossWire)) expect(authorityCrossWire.left.code).toBe("GRAMMAR_INVALID")
  // The old public verifier accepted this when the caller also forged the
  // three ID values.  The evidence atom, its declaration, and the prestate
  // are internally consistent, so simple kind/ID matching is insufficient:
  // the supplied evidence authority must be revalidated as the actual
  // RECEIPT_ADMIT authority chain (including its policy, authorization,
  // revocation, purpose, actor, scope, and evaluation time bindings).
  const forgedMatchedAuthorityTriple = validateDnrd5V2ReceiptSeal({
    ...input,
    evidenceAuthority: authorityAtState(validated.nextState, wrongPhaseAuthority),
    command: {
      ...receiptCommand,
      readSet: [
        ...receiptCommand.readSet,
        wrongPhaseAuthority.grant.atom.key,
        wrongPhaseAuthority.capability.atom.key,
        wrongPhaseAuthority.revocation.atom.key
      ],
      writes: [{
        ...evidence,
        references: evidence.references.map((reference) =>
          reference.role === "role:dnrd5:v2:grant"
            ? { ...reference, target: wrongPhaseAuthority.grant.atom.key }
            : reference.role === "role:dnrd5:v2:capability"
              ? { ...reference, target: wrongPhaseAuthority.capability.atom.key }
              : reference.role === "role:dnrd5:v2:revocation"
                ? { ...reference, target: wrongPhaseAuthority.revocation.atom.key }
                : reference
        )
      }, receipt]
    }
  })
  expect(Either.isLeft(forgedMatchedAuthorityTriple)).toBe(true)
  expect(Either.isLeft(validateDnrd5V2ReceiptSeal({ ...input, command: { ...receiptCommand, writes: [evidence, { ...receipt, key: key("receipt:arbitrary") }] } }))).toBe(true)
  expect(Either.isLeft(validateDnrd5V2ReceiptSeal({ ...input, recordBytes: Uint8Array.from([...receiptBytes, 10]) }))).toBe(true)
  expect(Either.isLeft(validateDnrd5V2ReceiptSeal({ ...input, recordDescriptor: { ...receiptDescriptor, sha256: sha("f") } }))).toBe(true)
  expect(Either.isLeft(validateDnrd5V2ReceiptSeal({ ...input, envelopes: [Uint8Array.from([1]), receiptBound.bytes[1]!] }))).toBe(true)
  expect(Either.isLeft(validateDnrd5V2ReceiptSeal({ ...input, command: { ...receiptCommand, readSet: receiptCommand.readSet.slice(1) } }))).toBe(true)
  expect(Either.isLeft(validateDnrd5V2ReceiptSeal({ ...input, usedReceiptRecordDescriptorSha256s: [receiptDescriptor.sha256] }))).toBe(true)

  // Continue the same journal lineage: the receipt is now durable prestate for
  // the rollback decision, which in turn authorizes a W0 restore and its seal.
  const rollbackDecision = rel("rollback-decision", "rollback_decision", [["block", block], ["assignment", assignment], ["fork", forks[0]!], ["w0", w0], ["grant", grant], ["policy", restorePolicy], ["authorization", authorization], ["capability", capability], ["revocation", revocation], ["staging-successor", disposition], ["staging-receipt", receipt]])
  const rollbackDecisionCommand = command(3, [rollbackDecision], [block.key, assignment.key, forks[0]!.key, w0.key, grant.key, restorePolicy.key, authorization.key, capability.key, revocation.key, disposition.key, receipt.key], "transition:receipt-seal:rollback-decision")
  const rollbackDecisionBound = bound(rollbackDecisionCommand.writes)
  const rollbackDecisionRecord = right(makeCanonicalAtomV2StateJournalCommit(schema, { state: revisionSeal.nextState, descriptor: receiptDescriptor, journalLineageId: genesis.journalLineageId, schema: genesis.schema }, makeCanonicalAtomV2AcceptedReceipt(rollbackDecisionCommand, 3, 4), rollbackDecisionBound.bindings, rollbackDecisionBound.bytes))
  const rollbackDecisionState = right(applyCanonicalAtomV2StateJournalCommit(schema, { state: revisionSeal.nextState, descriptor: receiptDescriptor, journalLineageId: genesis.journalLineageId, schema: genesis.schema }, rollbackDecisionRecord, rollbackDecisionBound.bytes))
  const restoreConsumption = rel("restore-consumption", "capability_consumption", [["grant", grant], ["capability", capability], ["revocation", revocation], ["decision", rollbackDecision]])
  const restore = rel("restore", "restore_transaction", [["w0", w0], ["grant", grant], ["policy", restorePolicy], ["decision", rollbackDecision], ["consumption", restoreConsumption], ["staging-successor", disposition]])
  const restoreCommand = command(4, [restore, restoreConsumption], [w0.key, grant.key, restorePolicy.key, rollbackDecision.key, capability.key, revocation.key, disposition.key], "transition:receipt-seal:restore")
  const restoreBound = bound(restoreCommand.writes)
  const restoreRecord = right(makeCanonicalAtomV2StateJournalCommit(schema, { state: rollbackDecisionState.state, descriptor: rollbackDecisionState.descriptor, journalLineageId: genesis.journalLineageId, schema: genesis.schema }, makeCanonicalAtomV2AcceptedReceipt(restoreCommand, 4, 5), restoreBound.bindings, restoreBound.bytes))
  const restoreBytes = right(canonicalAtomV2StateJournalRecordBytes(restoreRecord)), restoreDescriptor = right(describeCanonicalAtomV2StateJournalRecord(restoreRecord))
  const restoreEffectInput = { schema, preState: rollbackDecisionState.state, predecessor: { descriptor: rollbackDecisionState.descriptor, journalLineageId: genesis.journalLineageId, schemaContentSha256: genesis.schema.content.sha256 }, command: restoreCommand, record: restoreRecord, recordBytes: restoreBytes, recordDescriptor: restoreDescriptor, envelopes: restoreBound.bytes, usedRecordDescriptorSha256s: [] }
  const restored = right(validateDnrd5V2RecordBoundEffect(restoreEffectInput))
  const rollbackPayload = { contractVersion: DNRD5_V2_RECEIPT_SEAL_V1, receiptKind: "ROLLBACK" as const, precedingEffectRecordDescriptorSha256: restoreDescriptor.sha256, postcommitReceiptIdentity: restored.deterministicFuturePostcommitReceiptIdentity, decisionAtomKeyId: canonicalAtomV2KeyId(rollbackDecision.key), effectConsumptionAtomKeyId: canonicalAtomV2KeyId(restoreConsumption.key), effectAtomKeyId: canonicalAtomV2KeyId(restore.key) }
  const rollbackPayloadBytes = right(canonicalDnrd5V2ReceiptPayloadBytes(rollbackPayload)), rollbackPayloadDescriptor = right(makeCanonicalAtomV2ContentDescriptor(DNRD5_V2_RECEIPT_PAYLOAD_MEDIA_TYPE, rollbackPayloadBytes))
  const rollbackEvidence = rel("rollback-evidence", "evidence_seal_consumption", [["grant", restoreEvidenceAuthority.grant.atom], ["capability", restoreEvidenceAuthority.capability.atom], ["revocation", restoreEvidenceAuthority.revocation.atom], ["purpose", rollbackDecision]])
  const rollbackReceipt = { ...rel(`receipt:${restored.deterministicFuturePostcommitReceiptIdentity}`, "rollback_transition_receipt", [["decision", rollbackDecision], ["effect-consumption", restoreConsumption], ["restore", restore], ["evidence-consumption", rollbackEvidence]]), content: rollbackPayloadDescriptor }
  const rollbackSealCommand = command(5, [rollbackEvidence, rollbackReceipt], [restoreEvidenceAuthority.grant.atom.key, restoreEvidenceAuthority.capability.atom.key, restoreEvidenceAuthority.revocation.atom.key, rollbackDecision.key, restoreConsumption.key, restore.key], "transition:receipt-seal:rollback-receipt")
  const rollbackSealBound = bound(rollbackSealCommand.writes)
  const rollbackSealRecord = right(makeCanonicalAtomV2StateJournalCommit(schema, { state: restored.nextState, descriptor: restoreDescriptor, journalLineageId: genesis.journalLineageId, schema: genesis.schema }, makeCanonicalAtomV2AcceptedReceipt(rollbackSealCommand, 5, 6), rollbackSealBound.bindings, rollbackSealBound.bytes))
  const rollbackSealBytes = right(canonicalAtomV2StateJournalRecordBytes(rollbackSealRecord)), rollbackSealDescriptor = right(describeCanonicalAtomV2StateJournalRecord(rollbackSealRecord))
  const rollbackSealInput = { schema, preState: restored.nextState, predecessor: { descriptor: restoreDescriptor, journalLineageId: genesis.journalLineageId, schemaContentSha256: genesis.schema.content.sha256 }, precedingEffect: restoreEffectInput, command: rollbackSealCommand, evidenceAuthority: authorityAtState(restored.nextState, restoreEvidenceAuthority), record: rollbackSealRecord, recordBytes: rollbackSealBytes, recordDescriptor: rollbackSealDescriptor, envelopes: rollbackSealBound.bytes, receiptPayloadBytes: rollbackPayloadBytes, receiptPayloadDescriptor: rollbackPayloadDescriptor, usedReceiptRecordDescriptorSha256s: [] }
  expect(Either.isRight(validateDnrd5V2ReceiptSeal(rollbackSealInput))).toBe(true)
  const admitAuthorityOnRollbackEvidence = {
    ...rollbackEvidence,
    references: rollbackEvidence.references.map((reference) =>
      reference.role === "role:dnrd5:v2:grant"
        ? { ...reference, target: admitEvidenceAuthority.grant.atom.key }
        : reference.role === "role:dnrd5:v2:capability"
          ? { ...reference, target: admitEvidenceAuthority.capability.atom.key }
          : reference.role === "role:dnrd5:v2:revocation"
            ? { ...reference, target: admitEvidenceAuthority.revocation.atom.key }
            : reference
    )
  }
  const validButWrongPhaseAuthority = validateDnrd5V2ReceiptSeal({
    ...rollbackSealInput,
    evidenceAuthority: authorityAtState(restored.nextState, admitEvidenceAuthority),
    command: {
      ...rollbackSealCommand,
      readSet: [
        ...rollbackSealCommand.readSet,
        admitEvidenceAuthority.grant.atom.key,
        admitEvidenceAuthority.capability.atom.key,
        admitEvidenceAuthority.revocation.atom.key
      ],
      writes: [admitAuthorityOnRollbackEvidence, rollbackReceipt]
    }
  })
  expect(Either.isLeft(validButWrongPhaseAuthority)).toBe(true)
  if (Either.isLeft(validButWrongPhaseAuthority)) {
    expect(validButWrongPhaseAuthority.left.code).toBe("GRAMMAR_INVALID")
  }
  const wrongRollbackPurpose = { ...rollbackEvidence, references: rollbackEvidence.references.map((r) => r.role === "role:dnrd5:v2:purpose" ? { ...r, target: decision.key } : r) }
  expect(Either.isLeft(validateDnrd5V2ReceiptSeal({ ...rollbackSealInput, command: { ...rollbackSealCommand, writes: [wrongRollbackPurpose, rollbackReceipt] } }))).toBe(true)
  const wrongRestoreRef = { ...rollbackReceipt, references: rollbackReceipt.references.map((r) => r.role === "role:dnrd5:v2:restore" ? { ...r, target: disposition.key } : r) }
  expect(Either.isLeft(validateDnrd5V2ReceiptSeal({ ...rollbackSealInput, command: { ...rollbackSealCommand, writes: [rollbackEvidence, wrongRestoreRef] } }))).toBe(true)
  expect(Either.isLeft(validateDnrd5V2ReceiptSeal({ ...rollbackSealInput, predecessor: { ...rollbackSealInput.predecessor, journalLineageId: "journal:rollback-forged" } }))).toBe(true)
})

it("canonically encodes the exact, closed receipt payload contract", () => {
  const payload = { contractVersion: DNRD5_V2_RECEIPT_SEAL_V1, receiptKind: "REVISION" as const, precedingEffectRecordDescriptorSha256: "a".repeat(64), postcommitReceiptIdentity: "b".repeat(64), decisionAtomKeyId: "hswm:dnrd5:causal-macroplasticity:v2|lineage:test|decision|0", effectConsumptionAtomKeyId: "hswm:dnrd5:causal-macroplasticity:v2|lineage:test|consumption|0", effectAtomKeyId: "hswm:dnrd5:causal-macroplasticity:v2|lineage:test|successor|0" }; const bytes = canonicalDnrd5V2ReceiptPayloadBytes(payload); expect(Either.isRight(bytes)).toBe(true); if (Either.isRight(bytes)) { const decoded = decodeCanonicalJsonBytes(bytes.right); expect(Either.isRight(decoded)).toBe(true); if (Either.isRight(decoded)) expect(decoded.right).toEqual(payload) }
})
