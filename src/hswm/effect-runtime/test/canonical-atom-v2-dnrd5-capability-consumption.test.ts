import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import {
  DNRD5_CAPABILITY_CONSUMPTION_KIND,
  DNRD5_CAPABILITY_CONSUMPTION_OWNER,
  DNRD5_CAPABILITY_CONSUMPTION_TERMINAL,
  dnrd5CapabilityConsumptionAtomUid,
  makeDnrd5CapabilityConsumptionAtom,
  validateDnrd5CapabilityConsumptionAtom,
  type Dnrd5CapabilityConsumptionReferenceAtoms
} from "../src/canonical-atom-v2-dnrd5-capability-consumption.js"
import { DNRD5_SCHEMA_VERSION } from "../src/canonical-atom-v2-dnrd5-schema.js"
import {
  HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  type CanonicalAtomV2
} from "../src/canonical-atom-v2-schema.js"

const sha = (letter: string): string => letter.repeat(64)
const descriptor = (letter: string) => ({
  mediaType: "application/json",
  byteLength: 1,
  sha256: sha(letter)
})
const atom = (
  atomUid: string,
  kind: string,
  responsibilityOwner: string,
  contentLetter: string
): CanonicalAtomV2 => ({
  _tag: "CanonicalAtomV2",
  contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  key: {
    schemaVersion: DNRD5_SCHEMA_VERSION,
    lineageId: "lineage:dnrd5:consumption-test",
    atomUid,
    revisionId: 0
  },
  kind,
  responsibilityOwner,
  content: descriptor(contentLetter),
  provenance: {
    mode: "BOOTSTRAP",
    evidenceSha256: sha("f"),
    sourceRef: null
  },
  lifecycle: "ADMITTED",
  references: []
})

const common = {
  grantSnapshot: atom(
    "grant",
    "hswm:dnrd5:grant_snapshot",
    "owner:dnrd5:grant_custodian",
    "a"
  ),
  capabilityIssuance: atom(
    "capability",
    "hswm:dnrd5:capability_issuance",
    "owner:dnrd5:capability_custodian",
    "b"
  ),
  currentRevocation: atom(
    "revocation",
    "hswm:dnrd5:revocation_status",
    "owner:dnrd5:revocation_custodian",
    "c"
  )
}

const admissionReferences = (): Dnrd5CapabilityConsumptionReferenceAtoms => ({
  ...common,
  creditDecision: atom(
    "credit",
    "hswm:dnrd5:credit_decision",
    "owner:dnrd5:credit_adjudicator",
    "d"
  ),
  candidateValidation: atom(
    "validation",
    "hswm:dnrd5:candidate_validation",
    "owner:dnrd5:revision_validator",
    "e"
  ),
  restorePolicy: null,
  stagingSuccessor: null,
  w0Snapshot: null
})

const restoreReferences = (): Dnrd5CapabilityConsumptionReferenceAtoms => ({
  ...common,
  creditDecision: null,
  candidateValidation: null,
  restorePolicy: atom(
    "restore-policy",
    "hswm:dnrd5:restore_policy",
    "owner:dnrd5:restore_policy_custodian",
    "d"
  ),
  stagingSuccessor: atom(
    "staging-successor",
    "hswm:dnrd5:macro_disposition",
    "owner:dnrd5:canonical_state_custodian",
    "e"
  ),
  w0Snapshot: atom(
    "w0",
    "hswm:dnrd5:w0_snapshot",
    "owner:dnrd5:canonical_state_custodian",
    "f"
  )
})

const content = (effect: "ADMIT_REVISION" | "RESTORE_W0" = "ADMIT_REVISION") => ({
  _tag: "Dnrd5CapabilityConsumption",
  contractVersion: "hswm-dnrd5-capability-consumption/v1",
  effect,
  capabilityNonceSha256: sha("1"),
  grantSnapshot: common.grantSnapshot.content,
  capabilityIssuance: common.capabilityIssuance.content,
  currentRevocation: common.currentRevocation.content,
  permitInputSha256: sha("2"),
  permitResolutionCoreSha256: sha("3"),
  expectedJournalHead: descriptor("4"),
  expectedStateRevision: 7,
  expectedStateSha256: sha("5"),
  transitionId: "transition:dnrd5:one",
  commandIntentSha256: sha("6"),
  evaluatedAt: "2026-08-28T12:00:00.000Z",
  terminal: DNRD5_CAPABILITY_CONSUMPTION_TERMINAL
})

it("constructs one nonce-derived admission consumption atom with exact branch refs", () => {
  const built = makeDnrd5CapabilityConsumptionAtom(
    content(),
    admissionReferences()
  )
  expect(Either.isRight(built)).toBe(true)
  if (Either.isLeft(built)) return
  const uid = dnrd5CapabilityConsumptionAtomUid(sha("1"))
  expect(Either.isRight(uid)).toBe(true)
  if (Either.isLeft(uid)) return
  expect(built.right.atom.key.atomUid).toBe(uid.right)
  expect(built.right.atom.kind).toBe(DNRD5_CAPABILITY_CONSUMPTION_KIND)
  expect(built.right.atom.responsibilityOwner).toBe(
    DNRD5_CAPABILITY_CONSUMPTION_OWNER
  )
  expect(built.right.atom.references.map(({ role }) => role)).toEqual([
    "role:dnrd5:grant",
    "role:dnrd5:capability",
    "role:dnrd5:revocation",
    "role:dnrd5:credit",
    "role:dnrd5:validation"
  ])
  const checked = validateDnrd5CapabilityConsumptionAtom(
    built.right.atom,
    built.right.bytes,
    admissionReferences()
  )
  expect(Either.isRight(checked)).toBe(true)
  if (Either.isRight(checked)) {
    expect(checked.right.status).toBe(
      "EXACT_ONE_SHOT_CONSUMPTION_ATOM_VALIDATED_NOT_SUBMITTED"
    )
    expect(Object.isFrozen(checked.right.atom.references)).toBe(true)
  }
})

it("uses the disjoint restore evidence branch", () => {
  const built = makeDnrd5CapabilityConsumptionAtom(
    content("RESTORE_W0"),
    restoreReferences()
  )
  expect(Either.isRight(built)).toBe(true)
  if (Either.isLeft(built)) return
  expect(built.right.atom.references.map(({ role }) => role)).toEqual([
    "role:dnrd5:grant",
    "role:dnrd5:capability",
    "role:dnrd5:revocation",
    "role:dnrd5:restore-policy",
    "role:dnrd5:staging-successor",
    "role:dnrd5:w0"
  ])
})

it("rejects alternate UID, nonce/content drift, and noncanonical bytes", () => {
  const built = makeDnrd5CapabilityConsumptionAtom(
    content(),
    admissionReferences()
  )
  if (Either.isLeft(built)) throw new Error("fixture construction failed")
  expect(Either.isLeft(validateDnrd5CapabilityConsumptionAtom(
    { ...built.right.atom, key: { ...built.right.atom.key, atomUid: "cap-consume:alias" } },
    built.right.bytes,
    admissionReferences()
  ))).toBe(true)
  expect(Either.isLeft(validateDnrd5CapabilityConsumptionAtom(
    built.right.atom,
    Uint8Array.from([...built.right.bytes, 10]),
    admissionReferences()
  ))).toBe(true)
  const other = makeDnrd5CapabilityConsumptionAtom(
    { ...content(), capabilityNonceSha256: sha("2") },
    admissionReferences()
  )
  if (Either.isRight(other)) {
    expect(other.right.atom.key.atomUid).not.toBe(built.right.atom.key.atomUid)
  }
})

it("rejects descriptor, owner, lineage, and effect-branch drift", () => {
  const mismatchedDescriptor = {
    ...content(),
    grantSnapshot: descriptor("f")
  }
  expect(Either.isLeft(makeDnrd5CapabilityConsumptionAtom(
    mismatchedDescriptor,
    admissionReferences()
  ))).toBe(true)

  const baseWrongOwner = admissionReferences()
  const wrongOwner = {
    ...baseWrongOwner,
    currentRevocation: {
      ...baseWrongOwner.currentRevocation,
      responsibilityOwner: "owner:dnrd5:wrong"
    }
  }
  expect(Either.isLeft(makeDnrd5CapabilityConsumptionAtom(
    content(),
    wrongOwner
  ))).toBe(true)

  const baseWrongLineage = admissionReferences()
  const wrongLineage = {
    ...baseWrongLineage,
    creditDecision: {
      ...baseWrongLineage.creditDecision!,
      key: {
        ...baseWrongLineage.creditDecision!.key,
        lineageId: "lineage:dnrd5:other"
      }
    }
  }
  expect(Either.isLeft(makeDnrd5CapabilityConsumptionAtom(
    content(),
    wrongLineage
  ))).toBe(true)

  expect(Either.isLeft(makeDnrd5CapabilityConsumptionAtom(
    content("RESTORE_W0"),
    admissionReferences()
  ))).toBe(true)
})
