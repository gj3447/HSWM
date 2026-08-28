import { expect, it } from "@effect/vitest"
import { Either } from "effect"
import { canonicalJsonBytes } from "../src/canonical-atom-v2-json.js"
import { matchDnrd5ActiveShamAdmittedShapes, validateDnrd5RevisionProposalBytes } from "../src/canonical-atom-v2-dnrd5-revision.js"

const sha = (x: string) => x.repeat(64)
const d = (x: string) => ({ mediaType: "application/json", byteLength: 1, sha256: sha(x) })
const base = () => ({
  _tag: "Dnrd5RevisionProposal", contractVersion: "hswm-dnrd5-revision-proposal/v1", blockId: "DNRD5-BLOCK-0001", opaqueCallId: "opaque:proposal:1", trajectory: d("a"), feedbackAssignment: d("b"), snapshot: { journalHead: d("c"), stateRootSha256: sha("d"), readsetSha256: sha("e") },
  targets: [{ uid: "atom:macro:1", kind: "macro_disposition", targetOwner: "canonical_state_custodian", incidenceSha256: sha("f") }], writesetIntentSha256: sha("1"), projectionBudget: 12, validator: { path: "validator:dnrd5:v1", version: d("2") }, provenance: { model: d("3"), runtime: d("4"), rng: d("5") }, semanticWrites: [{ proposalUid: "proposal:1", proposalKind: "revision_proposal", proposalOwner: "revision_proposer", targetUid: "atom:macro:1", targetKind: "macro_disposition", targetOwner: "canonical_state_custodian", typedRefs: [{ referenceType: "ref:dnrd5", role: "target", targetUid: "atom:macro:1" }], provenance: d("3"), semantic: { operation: "SELECT_PUBLIC_HYPOTHESIS", selectedHypothesis: 1, publicTaskCommitmentSha256: sha("6"), decisionBasis: "SEALED_TRAJECTORY_AND_ASSIGNED_FEEDBACK" } }], envelopeLengthClass: "COMPACT"
})
const expected = (p: any) => ({ blockId: p.blockId, opaqueCallId: p.opaqueCallId, trajectory: p.trajectory, feedbackAssignment: p.feedbackAssignment, snapshot: p.snapshot, targets: p.targets, writesetIntentSha256: p.writesetIntentSha256, projectionBudget: p.projectionBudget, validator: p.validator, provenance: p.provenance, typedRefs: p.semanticWrites[0].typedRefs, publicTaskCommitmentSha256: p.semanticWrites[0].semantic.publicTaskCommitmentSha256 })
const bytes = (p: any) => { const result = canonicalJsonBytes(p); if (Either.isLeft(result)) throw new Error("fixture bytes"); return result.right }

it("accepts only frozen canonical model bytes and returns a detached frozen proposal", () => {
  const p = base(); const raw = bytes(p); const out = validateDnrd5RevisionProposalBytes(raw, expected(p))
  if (Either.isLeft(out)) throw new Error(`${out.left.code}: ${out.left.detail}`)
  expect(Either.isRight(out)).toBe(true)
  if (Either.isRight(out)) { p.snapshot.journalHead.sha256 = sha("0"); expect(out.right.proposal.snapshot.journalHead.sha256).toBe(sha("c")); expect(Object.isFrozen(out.right.proposal.snapshot)).toBe(true); expect(out.right.status).toContain("NOT_SYNTHESIZED") }
})

it("rejects byte syntax/canonical shape/bindings/semantic material mutations", () => {
  const p = base(); const cases: Array<Uint8Array | ((v: any) => void)> = [
    new TextEncoder().encode('{"_tag":"Dnrd5RevisionProposal","_tag":"Dnrd5RevisionProposal"}'),
    new TextEncoder().encode(" { }"),
    (v) => { v.unexpected = true }, (v) => { delete v.projectionBudget },
    (v) => { v.blockId = "DNRD5-BLOCK-0002" }, (v) => { v.targets[0].uid = "atom:drift" },
    (v) => { v.semanticWrites[0].proposalOwner = "canonical_state_custodian" }, (v) => { v.semanticWrites[0].targetKind = "other" },
    (v) => { v.semanticWrites[0].typedRefs[0].targetUid = "atom:other" }, (v) => { v.semanticWrites[0].provenance = d("0") },
    (v) => { v.semanticWrites[0].semantic = { arbitrary: "channel" } }, (v) => { v.semanticWrites[0].semantic.publicTaskCommitmentSha256 = sha("0") }, (v) => { v.semanticWrites[0].semantic = { arm: "ACTIVE" } },
    (v) => { v.feedbackAssignment = d("0") }, (v) => { v.envelopeLengthClass = "STANDARD" }
  ]
  for (const item of cases) { const value = base(); const raw = item instanceof Uint8Array ? item : (item(value), bytes(value)); expect(Either.isLeft(validateDnrd5RevisionProposalBytes(raw, expected(p)))).toBe(true) }
  // There is deliberately no object-taking bridge API; bytes are mandatory.
  expect(Either.isLeft(validateDnrd5RevisionProposalBytes(base() as any, expected(p)))).toBe(true)
})

it("rejects invalid expected/block/owner split/model terminal/overlength and arm-fork keys", () => {
  const p: any = base(); const badBlock = { ...p, blockId: "DNRD5-BLOCK-0301" }; expect(Either.isLeft(validateDnrd5RevisionProposalBytes(bytes(badBlock), expected(p)))).toBe(true)
  const zeroBlock = { ...p, blockId: "DNRD5-BLOCK-0000" }; expect(Either.isLeft(validateDnrd5RevisionProposalBytes(bytes(zeroBlock), expected(p)))).toBe(true)
  const terminal = { ...p, acceptedTerminal: "CANDIDATE_VALIDATED_PENDING_PERMIT" }; expect(Either.isLeft(validateDnrd5RevisionProposalBytes(bytes(terminal), expected(p)))).toBe(true)
  const armKey: any = base(); armKey.semanticWrites[0].semantic = { ...armKey.semanticWrites[0].semantic, forkMetadata: "x" }; expect(Either.isLeft(validateDnrd5RevisionProposalBytes(bytes(armKey), expected(p)))).toBe(true)
  const badExpected: any = expected(p); badExpected.blockId = "DNRD5-BLOCK-0301"; expect(Either.isLeft(validateDnrd5RevisionProposalBytes(bytes(p), badExpected))).toBe(true)
  const extraExpected: any = { ...expected(p), hiddenAnswer: sha("a") }; expect(Either.isLeft(validateDnrd5RevisionProposalBytes(bytes(p), extraExpected))).toBe(true)
  const duplicateRefExpected: any = expected(p); duplicateRefExpected.typedRefs = [duplicateRefExpected.typedRefs[0], duplicateRefExpected.typedRefs[0]]; expect(Either.isLeft(validateDnrd5RevisionProposalBytes(bytes(p), duplicateRefExpected))).toBe(true)
  const huge = new Uint8Array(16_385); expect(Either.isLeft(validateDnrd5RevisionProposalBytes(huge, expected(p)))).toBe(true)
})

it("matches ACTIVE/SHAM admitted shapes only across all declared nonsemantic dimensions", () => {
  const shape = { targetUids: ["atom:macro:1"], kindIncidenceSha256: sha("a"), writesetCardinality: 1, canonicalEnvelopeLengthClass: "COMPACT", projectionBudget: 12, validatorPath: "validator:dnrd5:v1", acceptedTerminal: "ACCEPTED" }
  expect(Either.isRight(matchDnrd5ActiveShamAdmittedShapes(shape, structuredClone(shape)))).toBe(true)
  const fields = ["targetUids", "kindIncidenceSha256", "writesetCardinality", "canonicalEnvelopeLengthClass", "projectionBudget", "validatorPath", "acceptedTerminal"] as const
  for (const field of fields) { const sham: any = structuredClone(shape); sham[field] = field === "targetUids" ? ["atom:macro:2"] : field === "kindIncidenceSha256" ? sha("b") : field === "writesetCardinality" || field === "projectionBudget" ? 2 : field === "canonicalEnvelopeLengthClass" ? "STANDARD" : field === "validatorPath" ? "validator:other" : "REJECTED"; expect(Either.isLeft(matchDnrd5ActiveShamAdmittedShapes(shape, sham))).toBe(true) }
  expect(Either.isLeft(matchDnrd5ActiveShamAdmittedShapes({ ...shape, writesetCardinality: 2 }, structuredClone(shape)))).toBe(true)
})
