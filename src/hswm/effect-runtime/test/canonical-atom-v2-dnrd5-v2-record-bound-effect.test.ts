import { expect, it } from "@effect/vitest"
import { Either } from "effect"
import { createHash } from "node:crypto"

import { initialCanonicalAtomV2State, makeCanonicalAtomV2AcceptedReceipt } from "../src/canonical-atom-v2-domain.js"
import { canonicalAtomV2EnvelopeBytes, snapshotCanonicalAtomV2WriteContentBinding } from "../src/canonical-atom-v2-content-bound.js"
import { canonicalAtomV2KeyId, type CanonicalAtomV2, type CanonicalAtomV2Key, type CommitCanonicalAtomsV2Command } from "../src/canonical-atom-v2-schema.js"
import { describeCanonicalAtomV2StateJournalRecord, makeCanonicalAtomV2StateJournalCommit, makeCanonicalAtomV2StateJournalGenesis } from "../src/canonical-atom-v2-state-journal.js"
import { DNRD5_V2_OWNER_ROLE_BY_KIND, DNRD5_V2_REFERENCE_TYPE, DNRD5_V2_SCHEMA_VERSION, makeDnrd5V2CanonicalSchema, type Dnrd5V2CanonicalAtomKind } from "../src/canonical-atom-v2-dnrd5-v2-schema.js"
import { validateDnrd5V2RecordBoundEffect } from "../src/canonical-atom-v2-dnrd5-v2-record-bound-effect.js"
import { deriveDnrd5V2PostcommitReceiptIdentity } from "../src/canonical-atom-v2-dnrd5-v2-receipt-identity.js"

const right = <A, E>(value: Either.Either<A, E>): A => { if (Either.isLeft(value)) throw new Error(JSON.stringify(value.left)); return value.right }
const schema = makeDnrd5V2CanonicalSchema(); const sha = (x: string) => x.repeat(64)
const key = (atomUid: string): CanonicalAtomV2Key => ({ schemaVersion: DNRD5_V2_SCHEMA_VERSION, lineageId: "lineage:record-bound", atomUid, revisionId: 0 })
const atom = (uid: string, kind: Dnrd5V2CanonicalAtomKind, refs: ReadonlyArray<CanonicalAtomV2> = []): CanonicalAtomV2 => ({ _tag: "CanonicalAtomV2", contractVersion: "hswm-canonical-atom/v2", key: key(uid), kind: `hswm:dnrd5:v2:${kind}`, responsibilityOwner: `owner:dnrd5:v2:${DNRD5_V2_OWNER_ROLE_BY_KIND[kind]}`, content: { mediaType: "application/json", byteLength: 2, sha256: sha("a") }, provenance: refs.length ? { mode: "DERIVATION", evidenceSha256: sha("b"), sourceRef: refs[0]!.key } : { mode: "BOOTSTRAP", evidenceSha256: sha("b"), sourceRef: null }, lifecycle: "ADMITTED", references: [] })
const rel = (uid: string, kind: Dnrd5V2CanonicalAtomKind, pairs: ReadonlyArray<readonly [string, CanonicalAtomV2]>): CanonicalAtomV2 => ({ ...atom(uid, kind), provenance: { mode: "DERIVATION", evidenceSha256: sha("b"), sourceRef: pairs[0]![1].key }, references: pairs.map(([role, source]) => ({ referenceType: DNRD5_V2_REFERENCE_TYPE, role: `role:dnrd5:v2:${role}`, target: source.key })) })
const command = (revision: number, writes: ReadonlyArray<CanonicalAtomV2>, readSet: ReadonlyArray<CanonicalAtomV2Key> = [], id = `transition:record-bound:${revision}`): CommitCanonicalAtomsV2Command => ({ _tag: "CommitCanonicalAtomsV2", contractVersion: "hswm-canonical-transition/v2", transitionId: id, expectedStateRevision: revision, schemaVersion: DNRD5_V2_SCHEMA_VERSION, actorClaim: "principal:test", authorizationRef: "authorization:test", scope: "scope:test", decidedAt: "2026-08-28T12:00:00.000Z", traceRef: null, readSet, writes, provenanceSha256: sha("c") })
const bound = (writes: ReadonlyArray<CanonicalAtomV2>) => {
  const sorted = [...writes].sort((a, b) => canonicalAtomV2KeyId(a.key).localeCompare(canonicalAtomV2KeyId(b.key)))
  const bytes = sorted.map((a) => right(canonicalAtomV2EnvelopeBytes(a)))
  return { sorted, bytes, bindings: sorted.map((a, i) => snapshotCanonicalAtomV2WriteContentBinding({ key: a.key, payload: a.content, envelope: { mediaType: "application/vnd.hswm.canonical-atom-v2+json", byteLength: bytes[i]!.byteLength, sha256: createHash("sha256").update(bytes[i]!).digest("hex") } })) }
}

it("recomputes a valid effect record and rejects forged bytes, descriptor, receipt, state, binding, grammar/read and reuse", async () => {
  const policy = atom("policy", "permit_policy")
  const randomness = atom("randomness", "study_randomness"), alternateRandomness = atom("alternate-randomness", "study_randomness"), evaluator = atom("evaluator", "evaluator_commitment"), alternateEvaluator = atom("alternate-evaluator", "evaluator_commitment")
  const block = rel("block", "block_spec", [["randomness", randomness], ["evaluator", evaluator]])
  const alternateBlock = rel("alternate-block", "block_spec", [["randomness", alternateRandomness], ["evaluator", alternateEvaluator]])
  const probe = rel("probe", "probe_commitment", [["block-spec", block], ["randomness", randomness]])
  const placebo = rel("placebo", "placebo_commitment", [["block-spec", block], ["randomness", randomness]])
  const w0 = rel("w0", "w0_snapshot", [["block-spec", block]])
  const forks = [1, 2, 3, 4].map((n) => rel(`fork${n}`, "fork_incidence", [["w0", w0]]))
  const foreignFork = rel("foreign-fork", "fork_incidence", [["w0", w0]])
  const assignment = rel("assignment", "block_assignment", [["randomness", randomness], ["block-spec", block], ...forks.map((x) => ["fork", x] as const)])
  const assignmentTwo = rel("assignment-two", "block_assignment", [["randomness", randomness], ["block-spec", block], ...forks.map((x) => ["fork", x] as const)])
  const activation = rel("activation", "episode_activation", [["block-spec", block], ["probe", probe], ["w0", w0], ...forks.map((x) => ["fork", x] as const), ["assignment", assignment], ["evaluator", evaluator]])
  const activationTwo = rel("activation-two", "episode_activation", [["block-spec", block], ["probe", probe], ["w0", w0], ...forks.map((x) => ["fork", x] as const), ["assignment", assignmentTwo], ["evaluator", evaluator]])
  const contract = rel("contract", "trajectory_contract", [["activation", activation]])
  const contractTwo = rel("contract-two", "trajectory_contract", [["activation", activationTwo]])
  const seal = rel("seal", "trajectory_seal", [["activation", activation], ["contract", contract], ["w0", w0]])
  const sealTwo = rel("seal-two", "trajectory_seal", [["activation", activationTwo], ["contract", contractTwo], ["w0", w0]])
  const placeboReceipt = rel("placebo-receipt", "placebo_receipt", [["commitment", placebo], ["randomness", randomness]])
  const feedback = rel("feedback", "feedback_assignment", [["fork", forks[0]!], ["assignment", assignment], ["source", placeboReceipt]])
  const feedbackForeign = rel("feedback-foreign", "feedback_assignment", [["fork", foreignFork], ["assignment", assignment], ["source", placeboReceipt]])
  const proposal = rel("proposal", "revision_proposal", [["trajectory", seal], ["feedback", feedback]])
  const proposalForeign = rel("proposal-foreign", "revision_proposal", [["trajectory", seal], ["feedback", feedbackForeign]])
  const proposalTrajectorySpliced = rel("proposal-trajectory-spliced", "revision_proposal", [["trajectory", sealTwo], ["feedback", feedback]])
  const validation = rel("validation", "candidate_validation", [["proposal", proposal]])
  const validationForeign = rel("validation-foreign", "candidate_validation", [["proposal", proposalForeign]])
  const validationTrajectorySpliced = rel("validation-trajectory-spliced", "candidate_validation", [["proposal", proposalTrajectorySpliced]])
  const authorization = rel("authorization", "authorization_decision", [["policy", policy]])
  const capability = rel("capability", "capability_issuance", [["authorization", authorization], ["policy", policy]])
  const revocation = rel("revocation", "revocation_status", [["authorization", authorization], ["capability", capability]])
  const grant = rel("grant", "grant_snapshot", [["policy", policy], ["authorization", authorization], ["capability", capability], ["revocation", revocation]])
  const authorizationTwo = rel("authorization-two", "authorization_decision", [["policy", policy]])
  const capabilityTwo = rel("capability-two", "capability_issuance", [["authorization", authorizationTwo], ["policy", policy]])
  const revocationTwo = rel("revocation-two", "revocation_status", [["authorization", authorizationTwo], ["capability", capabilityTwo]])
  const grantTwo = rel("grant-two", "grant_snapshot", [["policy", policy], ["authorization", authorizationTwo], ["capability", capabilityTwo], ["revocation", revocationTwo]])
  const grantCrosswired = rel("grant-crosswired", "grant_snapshot", [["policy", policy], ["authorization", authorization], ["capability", capabilityTwo], ["revocation", revocation]])
  const proposalTwo = rel("proposal-two", "revision_proposal", [["trajectory", seal], ["feedback", feedback]])
  const validationSpliced = rel("validation-spliced", "candidate_validation", [["proposal", proposalTwo]])
  const w0Two = rel("w0-two", "w0_snapshot", [["block-spec", block]])
  const credit = rel("credit", "credit_decision", [["trajectory", seal], ["credit-source", placeboReceipt], ["feedback", feedback], ["proposal", proposal], ["grant", grant]])
  const creditForeign = rel("credit-foreign", "credit_decision", [["trajectory", seal], ["credit-source", placeboReceipt], ["feedback", feedbackForeign], ["proposal", proposalForeign], ["grant", grant]])
  const creditTrajectorySpliced = rel("credit-trajectory-spliced", "credit_decision", [["trajectory", sealTwo], ["credit-source", placeboReceipt], ["feedback", feedback], ["proposal", proposalTrajectorySpliced], ["grant", grant]])
  const decision = rel("decision", "revision_admission_decision", [["block", block], ["assignment", assignment], ["fork", forks[0]!], ["proposal", proposal], ["validation", validation], ["credit", credit], ["grant", grant], ["authorization", authorization], ["capability", capability], ["revocation", revocation]])
  const decisionCrosswired = rel("decision-crosswired", "revision_admission_decision", [["block", block], ["assignment", assignment], ["fork", forks[0]!], ["proposal", proposal], ["validation", validation], ["credit", credit], ["grant", grantCrosswired], ["authorization", authorization], ["capability", capability], ["revocation", revocation]])
  const decisionSubjectSpliced = rel("decision-subject-spliced", "revision_admission_decision", [["block", block], ["assignment", assignment], ["fork", forks[0]!], ["proposal", proposal], ["validation", validationSpliced], ["credit", credit], ["grant", grant], ["authorization", authorization], ["capability", capability], ["revocation", revocation]])
  const decisionForeignFork = rel("decision-foreign-fork", "revision_admission_decision", [["block", block], ["assignment", assignment], ["fork", foreignFork], ["proposal", proposalForeign], ["validation", validationForeign], ["credit", creditForeign], ["grant", grant], ["authorization", authorization], ["capability", capability], ["revocation", revocation]])
  const decisionTrajectorySpliced = rel("decision-trajectory-spliced", "revision_admission_decision", [["block", block], ["assignment", assignment], ["fork", forks[0]!], ["proposal", proposalTrajectorySpliced], ["validation", validationTrajectorySpliced], ["credit", creditTrajectorySpliced], ["grant", grant], ["authorization", authorization], ["capability", capability], ["revocation", revocation]])
  const restorePolicy = rel("restore-policy", "restore_policy", [["policy", policy], ["capability", capability]])
  const stagingConsumption = rel("staging-consumption", "capability_consumption", [["grant", grant], ["capability", capability], ["revocation", revocation], ["decision", decision]])
  const stagingMacro = rel("staging-macro", "macro_disposition", [["proposal", proposal], ["revision-admission-decision", decision], ["restore-policy", restorePolicy], ["effect-consumption", stagingConsumption]])
  const restorePolicyTwo = rel("restore-policy-two", "restore_policy", [["policy", policy], ["capability", capabilityTwo]])
  const stagingMacroTwo = rel("staging-macro-two", "macro_disposition", [["proposal", proposal], ["revision-admission-decision", decision], ["restore-policy", restorePolicy], ["effect-consumption", stagingConsumption]])
  const stagingEvidence = rel("staging-evidence", "evidence_seal_consumption", [["grant", grant], ["capability", capability], ["revocation", revocation], ["purpose", decision]])
  const stagingReceipt = rel("staging-receipt", "revision_transition_receipt", [["decision", decision], ["effect-consumption", stagingConsumption], ["successor", stagingMacro], ["evidence-consumption", stagingEvidence]])
  const stagingReceiptSpliced = rel("staging-receipt-spliced", "revision_transition_receipt", [["decision", decision], ["effect-consumption", stagingConsumption], ["successor", stagingMacroTwo], ["evidence-consumption", stagingEvidence]])
  const rollbackDecision = rel("rollback-decision", "rollback_decision", [["block", block], ["assignment", assignment], ["fork", forks[0]!], ["w0", w0], ["grant", grant], ["policy", restorePolicy], ["authorization", authorization], ["capability", capability], ["revocation", revocation], ["staging-successor", stagingMacro], ["staging-receipt", stagingReceipt]])
  const rollbackDecisionTwo = rel("rollback-decision-two", "rollback_decision", [["block", block], ["assignment", assignment], ["fork", forks[0]!], ["w0", w0], ["grant", grant], ["policy", restorePolicy], ["authorization", authorization], ["capability", capability], ["revocation", revocation], ["staging-successor", stagingMacro], ["staging-receipt", stagingReceipt]])
  const rollbackDecisionStagingSpliced = rel("rollback-decision-staging-spliced", "rollback_decision", [["block", block], ["assignment", assignment], ["fork", forks[0]!], ["w0", w0], ["grant", grant], ["policy", restorePolicy], ["authorization", authorization], ["capability", capability], ["revocation", revocation], ["staging-successor", stagingMacro], ["staging-receipt", stagingReceiptSpliced]])
  const genesis = right(makeCanonicalAtomV2StateJournalGenesis("journal:record-bound", schema))
  const genesisDescriptor = right(describeCanonicalAtomV2StateJournalRecord(genesis))
  const bootstrap = command(0, [randomness, alternateRandomness, evaluator, alternateEvaluator, block, alternateBlock, probe, placebo, w0, ...forks, foreignFork, assignment, assignmentTwo, activation, activationTwo, contract, contractTwo, seal, sealTwo, placeboReceipt, feedback, feedbackForeign, proposal, proposalForeign, proposalTrajectorySpliced, validation, validationForeign, validationTrajectorySpliced, policy, authorization, capability, revocation, grant, authorizationTwo, capabilityTwo, revocationTwo, grantTwo, grantCrosswired, proposalTwo, validationSpliced, w0Two, credit, creditForeign, creditTrajectorySpliced, decision, decisionCrosswired, decisionSubjectSpliced, decisionForeignFork, decisionTrajectorySpliced, restorePolicy, stagingConsumption, stagingMacro, restorePolicyTwo, stagingMacroTwo, stagingEvidence, stagingReceipt, stagingReceiptSpliced, rollbackDecision, rollbackDecisionTwo, rollbackDecisionStagingSpliced])
  const bootstrapReceipt = makeCanonicalAtomV2AcceptedReceipt(bootstrap, 0, 1)
  const bootstrapBound = bound(bootstrap.writes)
  const bootstrapRecord = right(makeCanonicalAtomV2StateJournalCommit(schema, { state: initialCanonicalAtomV2State(DNRD5_V2_SCHEMA_VERSION), descriptor: genesisDescriptor, journalLineageId: genesis.journalLineageId, schema: genesis.schema }, bootstrapReceipt, bootstrapBound.bindings, bootstrapBound.bytes))
  // Replay through the journal to obtain the real predecessor state.
  const bootstrapState = right((await import("../src/canonical-atom-v2-state-journal.js")).applyCanonicalAtomV2StateJournalCommit(schema, { state: initialCanonicalAtomV2State(DNRD5_V2_SCHEMA_VERSION), descriptor: genesisDescriptor, journalLineageId: genesis.journalLineageId, schema: genesis.schema }, bootstrapRecord, bootstrapBound.bytes))
  const consumption = rel("consumption", "capability_consumption", [["grant", grant], ["capability", capability], ["revocation", revocation], ["decision", decision]])
  const disposition = rel("disposition", "macro_disposition", [["proposal", proposal], ["revision-admission-decision", decision], ["restore-policy", restorePolicy], ["effect-consumption", consumption]])
  const effect = command(1, [disposition, consumption], [grant.key, capability.key, revocation.key, decision.key, proposal.key, restorePolicy.key], "transition:record-bound:effect")
  const effectBound = bound(effect.writes)
  const effectReceipt = makeCanonicalAtomV2AcceptedReceipt(effect, 1, 2)
  const record = right(makeCanonicalAtomV2StateJournalCommit(schema, { state: bootstrapState.state, descriptor: bootstrapState.descriptor, journalLineageId: genesis.journalLineageId, schema: genesis.schema }, effectReceipt, effectBound.bindings, effectBound.bytes))
  const recordBytes = right((await import("../src/canonical-atom-v2-state-journal.js")).canonicalAtomV2StateJournalRecordBytes(record)); const recordDescriptor = right(describeCanonicalAtomV2StateJournalRecord(record))
  const input = { schema, preState: bootstrapState.state, predecessor: { descriptor: bootstrapState.descriptor, journalLineageId: genesis.journalLineageId, schemaContentSha256: genesis.schema.content.sha256 }, command: effect, record, recordBytes, recordDescriptor, envelopes: effectBound.bytes, usedRecordDescriptorSha256s: [] }
  const validatedEffect = validateDnrd5V2RecordBoundEffect(input)
  expect(Either.isRight(validatedEffect)).toBe(true)
  if (Either.isRight(validatedEffect)) {
    expect(validatedEffect.right.deterministicFuturePostcommitReceiptIdentity).toBe(right(deriveDnrd5V2PostcommitReceiptIdentity({ effectRecordDescriptorSha256: recordDescriptor.sha256, journalLineageId: record.journalLineageId, transitionId: effect.transitionId, decisionAtomKeyId: canonicalAtomV2KeyId(decision.key), effectConsumptionAtomKeyId: canonicalAtomV2KeyId(consumption.key), effectAtomKeyId: canonicalAtomV2KeyId(disposition.key) })))
  }
  expect(Either.isLeft(validateDnrd5V2RecordBoundEffect({ ...input, recordBytes: Uint8Array.from([...recordBytes, 10]) }))).toBe(true)
  expect(Either.isLeft(validateDnrd5V2RecordBoundEffect({ ...input, recordDescriptor: { ...recordDescriptor, sha256: sha("f") } }))).toBe(true)
  expect(Either.isLeft(validateDnrd5V2RecordBoundEffect({ ...input, record: { ...record, receipt: { ...record.receipt, actorClaim: "principal:forged" } } }))).toBe(true)
  expect(Either.isLeft(validateDnrd5V2RecordBoundEffect({ ...input, record: { ...record, resultingStateSha256: sha("e") } }))).toBe(true)
  expect(Either.isLeft(validateDnrd5V2RecordBoundEffect({ ...input, record: { ...record, writeBindings: [...record.writeBindings].reverse() } }))).toBe(true)
  expect(Either.isLeft(validateDnrd5V2RecordBoundEffect({ ...input, command: { ...effect, readSet: effect.readSet.slice(1) } }))).toBe(true)
  const wrongRefConsumption = { ...consumption, references: consumption.references.map((reference) => reference.role === "role:dnrd5:v2:decision" ? { ...reference, target: proposal.key } : reference) }
  expect(Either.isLeft(validateDnrd5V2RecordBoundEffect({ ...input, command: { ...effect, writes: [disposition, wrongRefConsumption] } }))).toBe(true)
  const expectGrammarInvalid = (candidate: Parameters<typeof validateDnrd5V2RecordBoundEffect>[0]) => {
    const result = validateDnrd5V2RecordBoundEffect(candidate)
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) expect(result.left.code).toBe("GRAMMAR_INVALID")
  }
  const alternateAuthorityConsumption = { ...consumption, references: consumption.references.map((reference) => {
    if (reference.role === "role:dnrd5:v2:grant") return { ...reference, target: grantTwo.key }
    if (reference.role === "role:dnrd5:v2:capability") return { ...reference, target: capabilityTwo.key }
    if (reference.role === "role:dnrd5:v2:revocation") return { ...reference, target: revocationTwo.key }
    return reference
  }) }
  expectGrammarInvalid({ ...input, command: { ...effect, readSet: [...effect.readSet, grantTwo.key, capabilityTwo.key, revocationTwo.key], writes: [disposition, alternateAuthorityConsumption] } })
  const alternateProposalDisposition = { ...disposition, references: disposition.references.map((reference) => reference.role === "role:dnrd5:v2:proposal" ? { ...reference, target: proposalTwo.key } : reference) }
  expectGrammarInvalid({ ...input, command: { ...effect, readSet: [...effect.readSet, proposalTwo.key], writes: [alternateProposalDisposition, consumption] } })
  const alternateRestorePolicyDisposition = { ...disposition, references: disposition.references.map((reference) => reference.role === "role:dnrd5:v2:restore-policy" ? { ...reference, target: restorePolicyTwo.key } : reference) }
  expectGrammarInvalid({ ...input, command: { ...effect, readSet: [...effect.readSet, restorePolicyTwo.key, capabilityTwo.key], writes: [alternateRestorePolicyDisposition, consumption] } })
  const crosswiredConsumption = { ...consumption, references: consumption.references.map((reference) => reference.role === "role:dnrd5:v2:grant" ? { ...reference, target: grantCrosswired.key } : reference.role === "role:dnrd5:v2:decision" ? { ...reference, target: decisionCrosswired.key } : reference) }
  const crosswiredDisposition = { ...disposition, references: disposition.references.map((reference) => reference.role === "role:dnrd5:v2:revision-admission-decision" ? { ...reference, target: decisionCrosswired.key } : reference) }
  expectGrammarInvalid({ ...input, command: { ...effect, readSet: [...effect.readSet, grantCrosswired.key, decisionCrosswired.key], writes: [crosswiredDisposition, crosswiredConsumption] } })
  const subjectSplicedConsumption = { ...consumption, references: consumption.references.map((reference) => reference.role === "role:dnrd5:v2:decision" ? { ...reference, target: decisionSubjectSpliced.key } : reference) }
  const subjectSplicedDisposition = { ...disposition, references: disposition.references.map((reference) => reference.role === "role:dnrd5:v2:revision-admission-decision" ? { ...reference, target: decisionSubjectSpliced.key } : reference) }
  expectGrammarInvalid({ ...input, command: { ...effect, readSet: [...effect.readSet, decisionSubjectSpliced.key], writes: [subjectSplicedDisposition, subjectSplicedConsumption] } })
  const foreignForkConsumption = { ...consumption, references: consumption.references.map((reference) => reference.role === "role:dnrd5:v2:decision" ? { ...reference, target: decisionForeignFork.key } : reference) }
  const foreignForkDisposition = { ...disposition, references: disposition.references.map((reference) => reference.role === "role:dnrd5:v2:revision-admission-decision" ? { ...reference, target: decisionForeignFork.key } : reference) }
  expectGrammarInvalid({ ...input, command: { ...effect, readSet: [...effect.readSet, decisionForeignFork.key], writes: [foreignForkDisposition, foreignForkConsumption] } })
  const trajectorySplicedConsumption = { ...consumption, references: consumption.references.map((reference) => reference.role === "role:dnrd5:v2:decision" ? { ...reference, target: decisionTrajectorySpliced.key } : reference) }
  const trajectorySplicedDisposition = { ...disposition, references: disposition.references.map((reference) => reference.role === "role:dnrd5:v2:revision-admission-decision" ? { ...reference, target: decisionTrajectorySpliced.key } : reference) }
  expectGrammarInvalid({ ...input, command: { ...effect, readSet: [...effect.readSet, decisionTrajectorySpliced.key], writes: [trajectorySplicedDisposition, trajectorySplicedConsumption] } })
  const crossWireState = (uid: string, role: string, target: CanonicalAtomV2) => ({ ...bootstrapState.state, atoms: bootstrapState.state.atoms.map((value) => value.key.atomUid === uid ? { ...value, references: value.references.map((reference) => reference.role.endsWith(`:${role}`) ? { ...reference, target: target.key } : reference) } : value) })
  expectGrammarInvalid({ ...input, preState: crossWireState("assignment", "randomness", alternateRandomness) })
  expectGrammarInvalid({ ...input, preState: crossWireState("activation", "evaluator", alternateEvaluator) })
  expectGrammarInvalid({ ...input, preState: crossWireState("probe", "randomness", alternateRandomness) })
  expectGrammarInvalid({ ...input, preState: crossWireState("probe", "block-spec", alternateBlock) })
  expectGrammarInvalid({ ...input, preState: crossWireState("contract", "activation", activationTwo) })
  expect(Either.isLeft(validateDnrd5V2RecordBoundEffect({ ...input, usedRecordDescriptorSha256s: [recordDescriptor.sha256] }))).toBe(true)

  const restoreConsumption = rel("restore-consumption", "capability_consumption", [["grant", grant], ["capability", capability], ["revocation", revocation], ["decision", rollbackDecision]])
  const restore = rel("restore", "restore_transaction", [["w0", w0], ["grant", grant], ["policy", restorePolicy], ["decision", rollbackDecision], ["consumption", restoreConsumption], ["staging-successor", stagingMacro]])
  const restoreCommand = command(1, [restore, restoreConsumption], [w0.key, grant.key, restorePolicy.key, rollbackDecision.key, capability.key, revocation.key, stagingMacro.key], "transition:record-bound:restore")
  const restoreBound = bound(restoreCommand.writes)
  const restoreReceipt = makeCanonicalAtomV2AcceptedReceipt(restoreCommand, 1, 2)
  const restoreRecord = right(makeCanonicalAtomV2StateJournalCommit(schema, { state: bootstrapState.state, descriptor: bootstrapState.descriptor, journalLineageId: genesis.journalLineageId, schema: genesis.schema }, restoreReceipt, restoreBound.bindings, restoreBound.bytes))
  const restoreBytes = right((await import("../src/canonical-atom-v2-state-journal.js")).canonicalAtomV2StateJournalRecordBytes(restoreRecord)); const restoreDescriptor = right(describeCanonicalAtomV2StateJournalRecord(restoreRecord))
  const restoreInput = { schema, preState: bootstrapState.state, predecessor: { descriptor: bootstrapState.descriptor, journalLineageId: genesis.journalLineageId, schemaContentSha256: genesis.schema.content.sha256 }, command: restoreCommand, record: restoreRecord, recordBytes: restoreBytes, recordDescriptor: restoreDescriptor, envelopes: restoreBound.bytes, usedRecordDescriptorSha256s: [] }
  expect(Either.isRight(validateDnrd5V2RecordBoundEffect(restoreInput))).toBe(true)
  const wrongRestoreConsumption = { ...restoreConsumption, references: restoreConsumption.references.map((reference) => reference.role === "role:dnrd5:v2:decision" ? { ...reference, target: decision.key } : reference) }
  expect(Either.isLeft(validateDnrd5V2RecordBoundEffect({ ...restoreInput, command: { ...restoreCommand, writes: [restore, wrongRestoreConsumption] } }))).toBe(true)
  expect(Either.isLeft(validateDnrd5V2RecordBoundEffect({ ...restoreInput, command: { ...restoreCommand, readSet: restoreCommand.readSet.slice(1) } }))).toBe(true)
  const splitDecisionRestore = { ...restore, references: restore.references.map((reference) => reference.role === "role:dnrd5:v2:decision" ? { ...reference, target: rollbackDecisionTwo.key } : reference) }
  const splitDecision = validateDnrd5V2RecordBoundEffect({ ...restoreInput, command: { ...restoreCommand, readSet: [...restoreCommand.readSet, rollbackDecisionTwo.key], writes: [splitDecisionRestore, restoreConsumption] } })
  expect(Either.isLeft(splitDecision)).toBe(true)
  if (Either.isLeft(splitDecision)) expect(splitDecision.left.code).toBe("GRAMMAR_INVALID")
  const alternateW0Restore = { ...restore, references: restore.references.map((reference) => reference.role === "role:dnrd5:v2:w0" ? { ...reference, target: w0Two.key } : reference) }
  expectGrammarInvalid({ ...restoreInput, command: { ...restoreCommand, readSet: [...restoreCommand.readSet, w0Two.key], writes: [alternateW0Restore, restoreConsumption] } })
  const alternatePolicyRestore = { ...restore, references: restore.references.map((reference) => reference.role === "role:dnrd5:v2:policy" ? { ...reference, target: restorePolicyTwo.key } : reference) }
  expectGrammarInvalid({ ...restoreInput, command: { ...restoreCommand, readSet: [...restoreCommand.readSet, restorePolicyTwo.key], writes: [alternatePolicyRestore, restoreConsumption] } })
  const alternateStagingRestore = { ...restore, references: restore.references.map((reference) => reference.role === "role:dnrd5:v2:staging-successor" ? { ...reference, target: stagingMacroTwo.key } : reference) }
  expectGrammarInvalid({ ...restoreInput, command: { ...restoreCommand, readSet: [...restoreCommand.readSet, stagingMacroTwo.key], writes: [alternateStagingRestore, restoreConsumption] } })
  const stagingSplicedConsumption = { ...restoreConsumption, references: restoreConsumption.references.map((reference) => reference.role === "role:dnrd5:v2:decision" ? { ...reference, target: rollbackDecisionStagingSpliced.key } : reference) }
  const stagingSplicedRestore = { ...restore, references: restore.references.map((reference) => reference.role === "role:dnrd5:v2:decision" ? { ...reference, target: rollbackDecisionStagingSpliced.key } : reference) }
  expectGrammarInvalid({ ...restoreInput, command: { ...restoreCommand, readSet: [...restoreCommand.readSet, rollbackDecisionStagingSpliced.key], writes: [stagingSplicedRestore, stagingSplicedConsumption] } })
  const wrongConsumptionRole = { ...restore, references: restore.references.map((reference) => reference.role === "role:dnrd5:v2:consumption" ? { ...reference, role: "role:dnrd5:v2:effect-consumption" } : reference) }
  expect(Either.isLeft(validateDnrd5V2RecordBoundEffect({ ...restoreInput, command: { ...restoreCommand, writes: [wrongConsumptionRole, restoreConsumption] } }))).toBe(true)
  expect(Either.isLeft(validateDnrd5V2RecordBoundEffect({ ...restoreInput, usedRecordDescriptorSha256s: [restoreDescriptor.sha256] }))).toBe(true)
})
