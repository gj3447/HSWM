import { createHash } from "node:crypto"

import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import { canonicalAtomV2SchemaContentBytes } from "../src/canonical-atom-v2-content-bound.js"
import { DNRD5_SCHEMA_VERSION, makeDnrd5CanonicalSchemaV2 } from "../src/canonical-atom-v2-dnrd5-schema.js"
import {
  DNRD5_V2_OWNER_ROLE_BY_KIND,
  DNRD5_V2_REFERENCE_TYPE,
  DNRD5_V2_SCHEMA_CONTENT_BYTE_LENGTH,
  DNRD5_V2_SCHEMA_CONTENT_SHA256,
  DNRD5_V2_SCHEMA_VERSION,
  makeDnrd5V2CanonicalSchema,
  validateDnrd5V2CanonicalSchema
} from "../src/canonical-atom-v2-dnrd5-v2-schema.js"

const owner = (kind: keyof typeof DNRD5_V2_OWNER_ROLE_BY_KIND) =>
  `owner:dnrd5:v2:${DNRD5_V2_OWNER_ROLE_BY_KIND[kind]}`
const role = (kind: string, roleName: string) =>
  makeDnrd5V2CanonicalSchema().kinds.find(({ kind: candidate }) => candidate === `hswm:dnrd5:v2:${kind}`)
    ?.referenceContracts[0]?.roles.find(({ role: candidate }) => candidate === `role:dnrd5:v2:${roleName}`)

it("defines a distinct v2 successor identity and retains exactly one owner per kind", () => {
  const schema = makeDnrd5V2CanonicalSchema()
  expect(Either.isRight(validateDnrd5V2CanonicalSchema(schema))).toBe(true)
  expect(schema.schemaVersion).toBe("hswm:dnrd5:causal-macroplasticity:v2")
  expect(schema.schemaVersion).toBe(DNRD5_V2_SCHEMA_VERSION)
  expect(schema.kinds).toHaveLength(44)
  expect(schema.kinds.every(({ allowedOwners }) => allowedOwners.length === 1)).toBe(true)
  expect(schema.kinds.find(({ kind }) => kind === "hswm:dnrd5:v2:transition_receipt")).toBeUndefined()
  expect(schema.kinds.find(({ kind }) => kind === "hswm:dnrd5:v2:revision_transition_receipt")?.allowedOwners).toEqual([owner("revision_transition_receipt")])
  expect(schema.kinds.find(({ kind }) => kind === "hswm:dnrd5:v2:rollback_transition_receipt")?.allowedOwners).toEqual([owner("rollback_transition_receipt")])
  const bytes = canonicalAtomV2SchemaContentBytes(schema)
  expect(Either.isRight(bytes)).toBe(true)
  if (Either.isRight(bytes)) {
    expect(bytes.right.byteLength).toBe(DNRD5_V2_SCHEMA_CONTENT_BYTE_LENGTH)
    expect(createHash("sha256").update(bytes.right).digest("hex")).toBe(
      DNRD5_V2_SCHEMA_CONTENT_SHA256
    )
  }
})

it("separates precommit decisions and effect consumption from postcommit seal consumption", () => {
  expect(role("revision_admission_decision", "block")?.targetKinds).toEqual(["hswm:dnrd5:v2:block_spec"])
  expect(role("revision_admission_decision", "assignment")?.targetKinds).toEqual(["hswm:dnrd5:v2:block_assignment"])
  expect(role("revision_admission_decision", "fork")?.targetKinds).toEqual(["hswm:dnrd5:v2:fork_incidence"])
  expect(role("credit_decision", "credit-source")?.targetKinds).toEqual([
    "hswm:dnrd5:v2:hidden_outcome", "hswm:dnrd5:v2:placebo_receipt", "hswm:dnrd5:v2:outcome_credit_escrow"
  ])
  expect(role("macro_disposition", "proposal")?.targetKinds).toEqual(["hswm:dnrd5:v2:revision_proposal"])
  expect(role("macro_disposition", "revision-admission-decision")?.targetKinds).toEqual(["hswm:dnrd5:v2:revision_admission_decision"])
  expect(role("macro_disposition", "restore-policy")?.targetKinds).toEqual(["hswm:dnrd5:v2:restore_policy"])
  expect(role("macro_disposition", "effect-consumption")?.targetKinds).toEqual(["hswm:dnrd5:v2:capability_consumption"])
  expect(role("macro_disposition", "receipt")).toBeUndefined()
  expect(role("capability_consumption", "decision")?.targetKinds).toEqual([
    "hswm:dnrd5:v2:revision_admission_decision", "hswm:dnrd5:v2:rollback_decision"
  ])
  expect(role("evidence_seal_consumption", "decision")).toBeUndefined()
  expect(role("evidence_seal_consumption", "purpose")?.targetKinds).toEqual([
    "hswm:dnrd5:v2:revision_admission_decision", "hswm:dnrd5:v2:rollback_decision", "hswm:dnrd5:v2:audit_release_capability"
  ])
  expect(role("revision_transition_receipt", "decision")?.targetKinds).toEqual(["hswm:dnrd5:v2:revision_admission_decision"])
  expect(role("revision_transition_receipt", "effect-consumption")?.targetKinds).toEqual(["hswm:dnrd5:v2:capability_consumption"])
  expect(role("revision_transition_receipt", "evidence-consumption")?.targetKinds).toEqual(["hswm:dnrd5:v2:evidence_seal_consumption"])
  expect(role("rollback_transition_receipt", "restore")?.targetKinds).toEqual(["hswm:dnrd5:v2:restore_transaction"])
  expect(role("rollback_decision", "staging-receipt")?.targetKinds).toEqual(["hswm:dnrd5:v2:revision_transition_receipt"])
  expect(role("restore_transaction", "grant")?.targetKinds).toEqual(["hswm:dnrd5:v2:grant_snapshot"])
  expect(role("restore_transaction", "policy")?.targetKinds).toEqual(["hswm:dnrd5:v2:restore_policy"])
  expect(role("block_evidence_manifest", "revision-receipt")?.minimum).toBe(3)
  expect(role("block_evidence_manifest", "revision-receipt")?.maximum).toBe(3)
  expect(role("block_evidence_manifest", "rollback-receipt")?.minimum).toBe(1)
  expect(role("block_evidence_manifest", "restore")?.minimum).toBe(1)
})

it("requires complete delayed-audit and manifest closure before a block seal", () => {
  const audit = ["block", "assignment", "outcome", "escrow", "probe-trajectory", "probe-outcome", "evaluator-capability", "release-capability", "evaluator-release", "evidence-consumption"].map((name) => role("audit_release", name))
  expect(audit.every((entry) => entry !== undefined)).toBe(true)
  expect(role("audit_release_capability", "block")?.targetKinds).toEqual(["hswm:dnrd5:v2:block_spec"])
  expect(role("audit_release_capability", "policy")?.targetKinds).toEqual(["hswm:dnrd5:v2:permit_policy"])
  expect(role("audit_release", "release-capability")?.targetKinds).toEqual(["hswm:dnrd5:v2:audit_release_capability"])
  expect(role("audit_release", "probe-trajectory")?.minimum).toBe(4)
  expect(role("audit_release", "probe-outcome")?.minimum).toBe(4)
  expect(role("audit_release", "evaluator-release")?.minimum).toBe(4)
  expect(role("audit_release", "evaluator-release")?.maximum).toBe(4)
  expect(role("block_seal", "manifest")?.targetKinds).toEqual(["hswm:dnrd5:v2:block_evidence_manifest"])
  expect(role("block_seal", "audit-release")?.targetKinds).toEqual(["hswm:dnrd5:v2:audit_release"])
  expect(makeDnrd5V2CanonicalSchema().kinds.find(({ kind }) => kind === "hswm:dnrd5:v2:block_seal")?.referenceContracts[0]?.referenceType).toBe(DNRD5_V2_REFERENCE_TYPE)
})

it("fails closed for schema mutation while preserving the v1 byte and kind universe", () => {
  const successor = makeDnrd5V2CanonicalSchema()
  const strippedAudit = {
    ...successor,
    kinds: successor.kinds.filter(({ kind }) => kind !== "hswm:dnrd5:v2:audit_release")
  }
  expect(Either.isLeft(validateDnrd5V2CanonicalSchema(strippedAudit))).toBe(true)

  const v1 = makeDnrd5CanonicalSchemaV2()
  const v1Bytes = canonicalAtomV2SchemaContentBytes(v1)
  expect(Either.isRight(v1Bytes)).toBe(true)
  if (Either.isLeft(v1Bytes)) return
  expect(createHash("sha256").update(v1Bytes.right).digest("hex")).toBe("03c44dec6907d16955927a2ab2886c03db97f1dd5746bc5f343ce853864592a0")
  expect(v1.schemaVersion).toBe(DNRD5_SCHEMA_VERSION)
  expect(v1.kinds).toHaveLength(37)
  expect(v1.kinds.some(({ kind }) => kind === "hswm:dnrd5:audit_release")).toBe(false)
})
