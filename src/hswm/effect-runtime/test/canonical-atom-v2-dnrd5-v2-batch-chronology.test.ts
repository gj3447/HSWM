import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import { initialCanonicalAtomV2State } from "../src/canonical-atom-v2-domain.js"
import {
  DNRD5_V2_OWNER_ROLE_BY_KIND,
  DNRD5_V2_REFERENCE_TYPE,
  DNRD5_V2_SCHEMA_VERSION,
  makeDnrd5V2CanonicalSchema,
  type Dnrd5V2CanonicalAtomKind
} from "../src/canonical-atom-v2-dnrd5-v2-schema.js"
import {
  DNRD5_V2_ATOMIC_BATCH_TOPOLOGY_BOUNDARY,
  validateDnrd5V2AtomicBatchChronology
} from "../src/canonical-atom-v2-dnrd5-v2-batch-chronology.js"
import {
  HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
  type CanonicalAtomV2,
  type CanonicalAtomV2Key,
  type CanonicalAtomV2Reference,
  type CommitCanonicalAtomsV2Command
} from "../src/canonical-atom-v2-schema.js"

const schema = makeDnrd5V2CanonicalSchema()
const sha = (letter: string): string => letter.repeat(64)
const key = (atomUid: string): CanonicalAtomV2Key => ({
  schemaVersion: DNRD5_V2_SCHEMA_VERSION,
  lineageId: "lineage:dnrd5:v2:batch-test",
  atomUid,
  revisionId: 0
})
const ref = (role: string, target: CanonicalAtomV2): CanonicalAtomV2Reference => ({
  referenceType: DNRD5_V2_REFERENCE_TYPE,
  role: `role:dnrd5:v2:${role}`,
  target: target.key
})
const atom = (
  atomUid: string,
  kind: Dnrd5V2CanonicalAtomKind,
  references: ReadonlyArray<CanonicalAtomV2Reference> = []
): CanonicalAtomV2 => ({
  _tag: "CanonicalAtomV2",
  contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  key: key(atomUid),
  kind: `hswm:dnrd5:v2:${kind}`,
  responsibilityOwner: `owner:dnrd5:v2:${DNRD5_V2_OWNER_ROLE_BY_KIND[kind]}`,
  content: { mediaType: "application/json", byteLength: 2, sha256: sha("a") },
  provenance: references.length === 0
    ? { mode: "BOOTSTRAP", evidenceSha256: sha("b"), sourceRef: null }
    : { mode: "DERIVATION", evidenceSha256: sha("b"), sourceRef: references[0]!.target },
  lifecycle: "ADMITTED",
  references
})
const command = (
  expectedStateRevision: number,
  writes: ReadonlyArray<CanonicalAtomV2>,
  readSet: ReadonlyArray<CanonicalAtomV2Key> = [],
  transitionId = `transition:dnrd5:v2:batch:${expectedStateRevision}`
): CommitCanonicalAtomsV2Command => ({
  _tag: "CommitCanonicalAtomsV2",
  contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
  transitionId,
  expectedStateRevision,
  schemaVersion: DNRD5_V2_SCHEMA_VERSION,
  actorClaim: "principal:dnrd5:v2:test",
  authorizationRef: "authorization:dnrd5:v2:test",
  scope: "scope:dnrd5:v2:test",
  decidedAt: "2026-08-28T12:00:00.000Z",
  traceRef: null,
  readSet,
  writes,
  provenanceSha256: sha("c")
})

it("accepts same-batch dependencies without treating a CAS as serial publication", () => {
  const policy = atom("policy", "permit_policy")
  const decision = atom("decision", "authorization_decision", [ref("policy", policy)])
  const result = validateDnrd5V2AtomicBatchChronology(
    schema,
    initialCanonicalAtomV2State(DNRD5_V2_SCHEMA_VERSION),
    command(0, [decision, policy])
  )
  expect(Either.isRight(result)).toBe(true)
  if (Either.isRight(result)) {
    expect(result.right.topologyAtomKeyIds).toEqual([
      "hswm:dnrd5:causal-macroplasticity:v2|lineage:dnrd5:v2:batch-test|policy|0",
      "hswm:dnrd5:causal-macroplasticity:v2|lineage:dnrd5:v2:batch-test|decision|0"
    ])
    expect(result.right.nextState.revision).toBe(1)
  }
})

it("is write-array-order independent and binds the deterministic topology hash", () => {
  const policy = atom("policy", "permit_policy")
  const decision = atom("decision", "authorization_decision", [ref("policy", policy)])
  const pre = initialCanonicalAtomV2State(DNRD5_V2_SCHEMA_VERSION)
  const forward = validateDnrd5V2AtomicBatchChronology(schema, pre, command(0, [policy, decision]))
  const reverse = validateDnrd5V2AtomicBatchChronology(schema, pre, command(0, [decision, policy]))
  expect(Either.isRight(forward)).toBe(true)
  expect(Either.isRight(reverse)).toBe(true)
  if (Either.isRight(forward) && Either.isRight(reverse)) {
    expect(reverse.right.topologyAtomKeyIds).toEqual(forward.right.topologyAtomKeyIds)
    expect(reverse.right.topologySha256).toBe(forward.right.topologySha256)
  }
})

it("binds typed/provenance edges even when a reference mutation preserves topology order", () => {
  const policyA = atom("policy-a", "permit_policy")
  const policyB = atom("policy-b", "permit_policy")
  const fromA = atom("z-decision", "authorization_decision", [ref("policy", policyA)])
  const fromB = atom("z-decision", "authorization_decision", [ref("policy", policyB)])
  const pre = initialCanonicalAtomV2State(DNRD5_V2_SCHEMA_VERSION)
  const first = validateDnrd5V2AtomicBatchChronology(schema, pre, command(0, [policyA, policyB, fromA]))
  const mutated = validateDnrd5V2AtomicBatchChronology(schema, pre, command(0, [policyA, policyB, fromB]))
  expect(Either.isRight(first)).toBe(true)
  expect(Either.isRight(mutated)).toBe(true)
  if (Either.isRight(first) && Either.isRight(mutated)) {
    expect(mutated.right.topologyAtomKeyIds).toEqual(first.right.topologyAtomKeyIds)
    expect(mutated.right.dependencyEdges).not.toEqual(first.right.dependencyEdges)
    expect(mutated.right.topologySha256).not.toBe(first.right.topologySha256)
  }
})

it("requires a later atomic batch to read every external predecessor", () => {
  const policy = atom("policy", "permit_policy")
  const decision = atom("decision", "authorization_decision", [ref("policy", policy)])
  const admitted = validateDnrd5V2AtomicBatchChronology(
    schema, initialCanonicalAtomV2State(DNRD5_V2_SCHEMA_VERSION), command(0, [policy, decision])
  )
  expect(Either.isRight(admitted)).toBe(true)
  if (Either.isLeft(admitted)) return
  const capability = atom("capability", "capability_issuance", [
    ref("authorization", decision), ref("policy", policy)
  ])
  const later = validateDnrd5V2AtomicBatchChronology(
    schema, admitted.right.nextState, command(1, [capability], [policy.key, decision.key])
  )
  expect(Either.isRight(later)).toBe(true)
  const omittedRead = validateDnrd5V2AtomicBatchChronology(
    schema, admitted.right.nextState, command(1, [capability], [policy.key])
  )
  expect(Either.isLeft(omittedRead)).toBe(true)
  if (Either.isLeft(omittedRead)) expect(omittedRead.left.code).toBe("MISSING_EXTERNAL_READ")
})

it("rejects missing/future, duplicate, self, and cyclic batch dependencies", () => {
  const policy = atom("policy", "permit_policy")
  const absent = atom("absent", "permit_policy")
  const decision = atom("decision", "authorization_decision", [ref("policy", absent)])
  const pre = initialCanonicalAtomV2State(DNRD5_V2_SCHEMA_VERSION)
  const forward = validateDnrd5V2AtomicBatchChronology(schema, pre, command(0, [decision]))
  expect(Either.isLeft(forward)).toBe(true)
  if (Either.isLeft(forward)) expect(forward.left.code).toBe("CROSS_BATCH_FORWARD_REFERENCE")

  const self = atom("self", "authorization_decision")
  const selfRef = { ...self, references: [ref("policy", self)], provenance: { mode: "DERIVATION" as const, evidenceSha256: sha("b"), sourceRef: self.key } }
  const selfResult = validateDnrd5V2AtomicBatchChronology(schema, pre, command(0, [selfRef]))
  expect(Either.isLeft(selfResult)).toBe(true)
  if (Either.isLeft(selfResult)) expect(selfResult.left.code).toBe("SELF_DEPENDENCY")

  const repeated = validateDnrd5V2AtomicBatchChronology(schema, pre, command(0, [policy, policy]))
  expect(Either.isLeft(repeated)).toBe(true)
  if (Either.isLeft(repeated)) expect(repeated.left.code).toBe("DUPLICATE_WRITE")

  const duplicateTyped = atom("duplicate-typed", "authorization_decision", [
    ref("policy", policy), ref("policy", policy)
  ])
  const repeatedTyped = validateDnrd5V2AtomicBatchChronology(
    schema, pre, command(0, [policy, duplicateTyped])
  )
  expect(Either.isLeft(repeatedTyped)).toBe(true)
  if (Either.isLeft(repeatedTyped)) expect(repeatedTyped.left.code).toBe("DUPLICATE_TYPED_REFERENCE")

  const left = atom("left", "authorization_decision")
  const right = atom("right", "authorization_decision")
  const cycleLeft = { ...left, references: [ref("policy", right)], provenance: { mode: "DERIVATION" as const, evidenceSha256: sha("b"), sourceRef: right.key } }
  const cycleRight = { ...right, references: [ref("policy", left)], provenance: { mode: "DERIVATION" as const, evidenceSha256: sha("b"), sourceRef: left.key } }
  const cycle = validateDnrd5V2AtomicBatchChronology(schema, pre, command(0, [cycleLeft, cycleRight]))
  expect(Either.isLeft(cycle)).toBe(true)
  if (Either.isLeft(cycle)) expect(cycle.left.code).toBe("DEPENDENCY_CYCLE")
  expect(DNRD5_V2_ATOMIC_BATCH_TOPOLOGY_BOUNDARY.doesNotValidate).toContain(
    "POSTCOMMIT_DURABLE_RECEIPT_BINDING"
  )
})
