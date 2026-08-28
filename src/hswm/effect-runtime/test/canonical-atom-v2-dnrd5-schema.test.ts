import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import {
  DNRD5_ARM_LABELS,
  DNRD5_CURRENT_STATE_PERMIT_BOUNDARY,
  DNRD5_OWNER_ROLE_BY_KIND,
  DNRD5_SCHEMA_VERSION,
  makeDnrd5CanonicalSchemaV2,
  validateDnrd5ArmLabel,
  validateDnrd5CanonicalSchemaV2,
  validateDnrd5ChronologicalAtoms,
  validateDnrd5StateChangePrincipals
} from "../src/canonical-atom-v2-dnrd5-schema.js"
import {
  HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  type CanonicalAtomV2
} from "../src/canonical-atom-v2-schema.js"

const sha = (letter: string) => letter.repeat(64)
const owner = (kind: keyof typeof DNRD5_OWNER_ROLE_BY_KIND) =>
  `owner:dnrd5:${DNRD5_OWNER_ROLE_BY_KIND[kind]}`
const atom = (uid: string, kind: string, owner: string, references: CanonicalAtomV2["references"] = []): CanonicalAtomV2 => ({
  _tag: "CanonicalAtomV2",
  contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  key: { schemaVersion: DNRD5_SCHEMA_VERSION, lineageId: "lineage:dnrd5:test", atomUid: uid, revisionId: 0 },
  kind,
  responsibilityOwner: owner,
  content: { mediaType: "application/json", byteLength: 2, sha256: sha("a") },
  provenance: references.length === 0 ? { mode: "BOOTSTRAP", evidenceSha256: sha("b"), sourceRef: null } : { mode: "DERIVATION", evidenceSha256: sha("b"), sourceRef: references[0]!.target },
  lifecycle: "ADMITTED",
  references
})

it("defines the exact DNRD-5 registry with one owner and typed references per kind", () => {
  const schema = makeDnrd5CanonicalSchemaV2()
  expect(Either.isRight(validateDnrd5CanonicalSchemaV2(schema))).toBe(true)
  expect(schema.kinds).toHaveLength(37)
  expect(schema.kinds.every((kind) => kind.allowedOwners.length === 1)).toBe(true)
  expect(schema.kinds.find(({ kind }) => kind === "hswm:dnrd5:block_spec")?.allowedOwners).toEqual([owner("block_spec")])
  expect(schema.kinds.find(({ kind }) => kind === "hswm:dnrd5:episode_activation")?.allowedOwners).toEqual([owner("episode_activation")])
  expect(schema.owners.filter(({ address }) => address === owner("block_spec"))).toHaveLength(1)
  expect(schema.kinds.find(({ kind }) => kind === "hswm:dnrd5:block_assignment")?.referenceContracts[0]?.roles.find(({ role }) => role === "role:dnrd5:fork")?.minimum).toBe(4)
  expect(schema.kinds.find(({ kind }) => kind === "hswm:dnrd5:restore_transaction")?.referenceContracts[0]?.roles.find(({ role }) => role === "role:dnrd5:staging-successor")?.targetKinds).toEqual(["hswm:dnrd5:macro_disposition"])
  const consumption = schema.kinds.find(({ kind }) => kind === "hswm:dnrd5:capability_consumption")
  expect(consumption?.allowedOwners).toEqual([owner("capability_consumption")])
  expect(consumption?.revisionPolicy).toBe("SINGLETON")
  expect(consumption?.referenceContracts[0]?.roles.map(({ role, minimum, maximum }) => ({ role, minimum, maximum }))).toEqual([
    { role: "role:dnrd5:grant", minimum: 1, maximum: 1 },
    { role: "role:dnrd5:capability", minimum: 1, maximum: 1 },
    { role: "role:dnrd5:revocation", minimum: 1, maximum: 1 },
    { role: "role:dnrd5:credit", minimum: 0, maximum: 1 },
    { role: "role:dnrd5:validation", minimum: 0, maximum: 1 },
    { role: "role:dnrd5:restore-policy", minimum: 0, maximum: 1 },
    { role: "role:dnrd5:staging-successor", minimum: 0, maximum: 1 },
    { role: "role:dnrd5:w0", minimum: 0, maximum: 1 }
  ])
  expect(DNRD5_CURRENT_STATE_PERMIT_BOUNDARY.currentStatePermit).toBe("READ_ONLY_EVALUATION_NOT_COMMIT_CAPABILITY")
  expect(DNRD5_CURRENT_STATE_PERMIT_BOUNDARY.traceRef).toBe("NULL_REQUIRED_BY_GENERIC_V2")
})

it("uses immutable fresh schema snapshots and fails closed for aliases, owners, arms, and principals", () => {
  const schema = makeDnrd5CanonicalSchemaV2()
  const second = makeDnrd5CanonicalSchemaV2()
  expect(schema).not.toBe(second)
  expect(schema.kinds[0]).not.toBe(second.kinds[0])
  const changedOwner = { ...schema, kinds: schema.kinds.map((kind, index) => index === 0 ? { ...kind, allowedOwners: ["owner:dnrd5:alias"] } : kind) }
  expect(Either.isLeft(validateDnrd5CanonicalSchemaV2(changedOwner))).toBe(true)
  const changedForm = { ...schema, kinds: schema.kinds.map((kind, index) => index === 0 ? { ...kind, form: "RELATION" as const, minimumArity: 1 } : kind) }
  expect(Either.isLeft(validateDnrd5CanonicalSchemaV2(changedForm))).toBe(true)
  expect(Either.isRight(validateDnrd5CanonicalSchemaV2(second))).toBe(true)
  expect(DNRD5_ARM_LABELS).toEqual(["ACTIVE", "OUTCOME_INDEPENDENT_SHAM", "DELAYED_NO_CREDIT", "EXACT_W0_ROLLBACK"])
  expect(Either.isRight(validateDnrd5ArmLabel("ACTIVE"))).toBe(true)
  expect(Either.isLeft(validateDnrd5ArmLabel("SHAM"))).toBe(true)
  expect(Either.isLeft(validateDnrd5StateChangePrincipals({
    actorClaim: "principal:actor", authorizer: "principal:state", canonicalStateCustodian: "principal:state", restoreCustodian: "principal:restore", creditAdjudicator: "principal:credit", authorizationDecisionRecordCustodian: "principal:record"
  }))).toBe(true)
  expect(Either.isLeft(validateDnrd5StateChangePrincipals({
    actorClaim: "principal:actor", authorizer: "", canonicalStateCustodian: "principal:state", restoreCustodian: "principal:restore", creditAdjudicator: "principal:credit", authorizationDecisionRecordCustodian: "principal:record"
  }))).toBe(true)
  expect(Either.isRight(validateDnrd5StateChangePrincipals({
    actorClaim: "principal:actor", authorizer: "principal:authorizer", canonicalStateCustodian: "principal:state", restoreCustodian: "principal:restore", creditAdjudicator: "principal:credit", authorizationDecisionRecordCustodian: "principal:record"
  }))).toBe(true)
  expect(Either.isLeft(validateDnrd5StateChangePrincipals({
    actorClaim: "principal:actor", authorizer: "principal:authorizer", canonicalStateCustodian: "principal:state", restoreCustodian: "principal:restore", creditAdjudicator: "principal:credit", authorizationDecisionRecordCustodian: "principal:record", extra: "principal:extra"
  } as any))).toBe(true)
})

it("fails closed for duplicate, owner-mismatched, alias, and forward typed references", () => {
  const schema = makeDnrd5CanonicalSchemaV2()
  const randomness = atom("randomness", "hswm:dnrd5:study_randomness", owner("study_randomness"))
  const evaluator = atom("evaluator", "hswm:dnrd5:evaluator_commitment", owner("evaluator_commitment"))
  const block = atom("block", "hswm:dnrd5:block_spec", owner("block_spec"), [
    { referenceType: "hswm:dnrd5:reference", role: "role:dnrd5:randomness", target: randomness.key },
    { referenceType: "hswm:dnrd5:reference", role: "role:dnrd5:evaluator", target: evaluator.key }
  ])
  expect(Either.isRight(validateDnrd5ChronologicalAtoms(schema, [randomness, evaluator, block]))).toBe(true)
  expect(Either.isLeft(validateDnrd5ChronologicalAtoms(schema, [block, randomness, evaluator]))).toBe(true)
  expect(Either.isLeft(validateDnrd5ChronologicalAtoms(schema, [randomness, randomness]))).toBe(true)
  expect(Either.isLeft(validateDnrd5ChronologicalAtoms(schema, [{ ...randomness, responsibilityOwner: "owner:dnrd5:wrong" }]))).toBe(true)
  expect(Either.isLeft(validateDnrd5ChronologicalAtoms(schema, [{ ...randomness, kind: "hswm:dnrd5:randomness-alias" }]))).toBe(true)
  expect(Either.isLeft(validateDnrd5ChronologicalAtoms(schema, [randomness, evaluator, {
    ...block,
    references: [
      ...block.references,
      { referenceType: "hswm:dnrd5:reference", role: "role:dnrd5:randomness-alias", target: randomness.key }
    ]
  }]))).toBe(true)
})

it("rejects duplicate fork refs plus invalid singleton revision and provenance", () => {
  const schema = makeDnrd5CanonicalSchemaV2()
  const randomness = atom("randomness", "hswm:dnrd5:study_randomness", owner("study_randomness"))
  const evaluator = atom("evaluator", "hswm:dnrd5:evaluator_commitment", owner("evaluator_commitment"))
  const block = atom("block", "hswm:dnrd5:block_spec", owner("block_spec"), [
    { referenceType: "hswm:dnrd5:reference", role: "role:dnrd5:randomness", target: randomness.key },
    { referenceType: "hswm:dnrd5:reference", role: "role:dnrd5:evaluator", target: evaluator.key }
  ])
  const probe = atom("probe", "hswm:dnrd5:probe_commitment", owner("probe_commitment"), [
    { referenceType: "hswm:dnrd5:reference", role: "role:dnrd5:block-spec", target: block.key },
    { referenceType: "hswm:dnrd5:reference", role: "role:dnrd5:randomness", target: randomness.key }
  ])
  const w0 = atom("w0", "hswm:dnrd5:w0_snapshot", owner("w0_snapshot"), [{ referenceType: "hswm:dnrd5:reference", role: "role:dnrd5:block-spec", target: block.key }])
  const forks = [0, 1, 2, 3].map((index) => atom(`fork:${index}`, "hswm:dnrd5:fork_incidence", owner("fork_incidence"), [{ referenceType: "hswm:dnrd5:reference", role: "role:dnrd5:w0", target: w0.key }]))
  const assignment = atom("assignment", "hswm:dnrd5:block_assignment", owner("block_assignment"), [
    { referenceType: "hswm:dnrd5:reference", role: "role:dnrd5:randomness", target: randomness.key },
    { referenceType: "hswm:dnrd5:reference", role: "role:dnrd5:block-spec", target: block.key },
    ...forks.map((fork) => ({ referenceType: "hswm:dnrd5:reference", role: "role:dnrd5:fork", target: fork.key } as const))
  ])
  const activation = atom("activation", "hswm:dnrd5:episode_activation", owner("episode_activation"), [
    { referenceType: "hswm:dnrd5:reference", role: "role:dnrd5:block-spec", target: block.key },
    { referenceType: "hswm:dnrd5:reference", role: "role:dnrd5:probe", target: probe.key },
    { referenceType: "hswm:dnrd5:reference", role: "role:dnrd5:w0", target: w0.key },
    ...[0, 1, 2, 3].map(() => ({ referenceType: "hswm:dnrd5:reference", role: "role:dnrd5:fork", target: forks[0]!.key } as const)),
    { referenceType: "hswm:dnrd5:reference", role: "role:dnrd5:assignment", target: assignment.key },
    { referenceType: "hswm:dnrd5:reference", role: "role:dnrd5:evaluator", target: evaluator.key }
  ])
  const prefix = [randomness, evaluator, block, probe, w0, ...forks, assignment]
  expect(Either.isLeft(validateDnrd5ChronologicalAtoms(schema, [...prefix, activation]))).toBe(true)
  expect(Either.isLeft(validateDnrd5ChronologicalAtoms(schema, [{ ...randomness, key: { ...randomness.key, revisionId: 1 } }]))).toBe(true)
  expect(Either.isLeft(validateDnrd5ChronologicalAtoms(schema, [{ ...randomness, provenance: { ...randomness.provenance, sourceRef: randomness.key } }]))).toBe(true)
})

it("requires relation provenance to name a declared predecessor and returns a detached frozen snapshot", () => {
  const schema = makeDnrd5CanonicalSchemaV2()
  const randomness = atom("randomness", "hswm:dnrd5:study_randomness", owner("study_randomness"))
  const evaluator = atom("evaluator", "hswm:dnrd5:evaluator_commitment", owner("evaluator_commitment"))
  const policy = atom("policy", "hswm:dnrd5:permit_policy", owner("permit_policy"))
  const block = atom("block", "hswm:dnrd5:block_spec", owner("block_spec"), [
    { referenceType: "hswm:dnrd5:reference", role: "role:dnrd5:randomness", target: randomness.key },
    { referenceType: "hswm:dnrd5:reference", role: "role:dnrd5:evaluator", target: evaluator.key }
  ])

  expect(Either.isLeft(validateDnrd5ChronologicalAtoms(schema, [
    randomness,
    evaluator,
    { ...block, provenance: { ...block.provenance, mode: "BOOTSTRAP", sourceRef: null } }
  ]))).toBe(true)
  expect(Either.isLeft(validateDnrd5ChronologicalAtoms(schema, [
    randomness,
    evaluator,
    policy,
    { ...block, provenance: { ...block.provenance, sourceRef: policy.key } }
  ]))).toBe(true)
  expect(Either.isLeft(validateDnrd5ChronologicalAtoms(schema, [
    evaluator,
    { ...randomness, provenance: { ...randomness.provenance, mode: "DERIVATION", sourceRef: evaluator.key } }
  ]))).toBe(true)

  const input = [randomness, evaluator, block]
  const validated = validateDnrd5ChronologicalAtoms(schema, input)
  expect(Either.isRight(validated)).toBe(true)
  if (Either.isLeft(validated)) return
  const retainedSha = validated.right[2]!.content.sha256
  ;(input[2]!.content as { sha256: string }).sha256 = sha("f")
  expect(validated.right[2]!.content.sha256).toBe(retainedSha)
  expect(Object.isFrozen(validated.right[2]!.references)).toBe(true)
})
