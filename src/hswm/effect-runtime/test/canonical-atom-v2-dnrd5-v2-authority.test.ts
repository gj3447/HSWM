import { createHash } from "node:crypto"

import { Either } from "effect"
import { describe, expect, it } from "vitest"

import {
  DNRD5_V2_AUTHORITY_PAYLOAD_V1,
  DNRD5_V2_AUTHORIZATION_DECISION_MEDIA_TYPE,
  DNRD5_V2_CAPABILITY_ISSUANCE_MEDIA_TYPE,
  DNRD5_V2_GRANT_SNAPSHOT_MEDIA_TYPE,
  DNRD5_V2_PERMIT_POLICY_MEDIA_TYPE,
  DNRD5_V2_REVOCATION_STATUS_MEDIA_TYPE,
  validateDnrd5V2AuthorityDisjointPair,
  validateDnrd5V2AuthorityPayloadAtState
} from "../src/canonical-atom-v2-dnrd5-v2-authority.js"
import { canonicalJsonBytes } from "../src/canonical-atom-v2-json.js"
import {
  DNRD5_V2_OWNER_ROLE_BY_KIND,
  DNRD5_V2_REFERENCE_TYPE,
  DNRD5_V2_SCHEMA_VERSION,
  type Dnrd5V2CanonicalAtomKind
} from "../src/canonical-atom-v2-dnrd5-v2-schema.js"
import { canonicalAtomV2KeyId, type CanonicalAtomV2 } from "../src/canonical-atom-v2-schema.js"

const VERSION = DNRD5_V2_AUTHORITY_PAYLOAD_V1
const LINEAGE = "lineage:dnrd5-v2-authority-test"
const AT = "2026-08-28T12:00:00.000Z"
const hash = (value: Uint8Array | string): string =>
  createHash("sha256").update(value).digest("hex")
const right = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw new Error(JSON.stringify(value.left))
  return value.right
}
const bytes = (value: object): Uint8Array => right(canonicalJsonBytes(value))
const atomKeyId = (atom: CanonicalAtomV2): string => canonicalAtomV2KeyId(atom.key)
type Content = { readonly atom: CanonicalAtomV2; readonly bytes: Uint8Array }
type Ref = readonly [string, CanonicalAtomV2]

const stub = (atomUid: string): CanonicalAtomV2 => ({
  key: { schemaVersion: DNRD5_V2_SCHEMA_VERSION, lineageId: LINEAGE, atomUid, revisionId: 0 }
} as CanonicalAtomV2)

const content = (
  atomUid: string,
  kind: Dnrd5V2CanonicalAtomKind,
  mediaType: string,
  payload: object,
  references: ReadonlyArray<Ref> = []
): Content => {
  const raw = bytes(payload)
  return {
    atom: {
      _tag: "CanonicalAtomV2",
      contractVersion: "hswm-canonical-atom/v2",
      key: { schemaVersion: DNRD5_V2_SCHEMA_VERSION, lineageId: LINEAGE, atomUid, revisionId: 0 },
      kind: `hswm:dnrd5:v2:${kind}`,
      responsibilityOwner: `owner:dnrd5:v2:${DNRD5_V2_OWNER_ROLE_BY_KIND[kind]}`,
      content: { mediaType, byteLength: raw.byteLength, sha256: hash(raw) },
      provenance: references.length === 0
        ? { mode: "BOOTSTRAP", evidenceSha256: "a".repeat(64), sourceRef: null }
        : { mode: "DERIVATION", evidenceSha256: "a".repeat(64), sourceRef: references[0]![1].key },
      lifecycle: "ADMITTED",
      references: references.map(([role, target]) => ({
        referenceType: DNRD5_V2_REFERENCE_TYPE,
        role: `role:dnrd5:v2:${role}`,
        target: target.key
      }))
    },
    bytes: raw
  }
}
const support = (
  atomUid: string,
  kind: Dnrd5V2CanonicalAtomKind,
  references: ReadonlyArray<Ref> = []
): CanonicalAtomV2 => content(atomUid, kind, "application/json", {}, references).atom
const replacePayload = (original: Content, payload: object): Content => {
  const raw = bytes(payload)
  return { atom: { ...original.atom, content: { ...original.atom.content, byteLength: raw.byteLength, sha256: hash(raw) } }, bytes: raw }
}
const parsePayload = (value: Content): Record<string, unknown> =>
  JSON.parse(new TextDecoder().decode(value.bytes)) as Record<string, unknown>

const principals = (actor = "principal:actor") => ({
  actor,
  authorizer: "principal:authorizer",
  canonicalStateCustodian: "principal:state-custodian",
  restoreCustodian: "principal:restore-custodian",
  creditAdjudicator: "principal:credit-adjudicator",
  authorizationRecordCustodian: "principal:authorization-record-custodian"
})
const history = (revision: number): ReadonlyArray<string> =>
  Array.from({ length: revision }, (_, index) => `transition:authority:${index + 1}`)

interface FixtureOptions {
  readonly evidenceActor?: string
  readonly evidenceScope?: string
  readonly alternatePurpose?: boolean
  readonly evidenceAuthorizationRef?: string
  readonly evidenceCapabilityId?: string
  readonly evidenceNonceSha256?: string
}

const makeFixture = (options: FixtureOptions = {}) => {
  const mainPrincipals = principals()
  const evidencePrincipals = principals(options.evidenceActor ?? mainPrincipals.actor)
  const mainScope = "scope:authority"
  const evidenceScope = options.evidenceScope ?? mainScope
  const allowedActors = [mainPrincipals.actor, evidencePrincipals.actor]
    .filter((value, index, values) => values.indexOf(value) === index)
    .sort()
  const policy = (uid: string, scope: string) => content(uid, "permit_policy", DNRD5_V2_PERMIT_POLICY_MEDIA_TYPE, {
    contractVersion: VERSION,
    scope,
    allowedActors,
    allowedPhases: ["MAIN_ADMIT", "RECEIPT_ADMIT"],
    allowMainReceiptPairing: true,
    generation: 1
  })
  const mainPolicy = policy("policy-main", mainScope)
  const evidencePolicy = evidenceScope === mainScope ? mainPolicy : policy("policy-evidence", evidenceScope)

  const randomness = support("randomness", "study_randomness")
  const evaluator = support("evaluator", "evaluator_commitment")
  const block = support("block", "block_spec", [["randomness", randomness], ["evaluator", evaluator]])
  const probe = support("probe", "probe_commitment", [["block-spec", block], ["randomness", randomness]])
  const placebo = support("placebo", "placebo_commitment", [["block-spec", block], ["randomness", randomness]])
  const w0 = support("w0", "w0_snapshot", [["block-spec", block]])
  const forks = [1, 2, 3, 4].map((index) => support(`fork-${index}`, "fork_incidence", [["w0", w0]]))
  const assignment = support("assignment", "block_assignment", [["randomness", randomness], ["block-spec", block], ...forks.map((fork) => ["fork", fork] as const)])
  const activation = support("activation", "episode_activation", [["block-spec", block], ["probe", probe], ["w0", w0], ...forks.map((fork) => ["fork", fork] as const), ["assignment", assignment], ["evaluator", evaluator]])
  const contract = support("contract", "trajectory_contract", [["activation", activation]])
  const trajectory = support("trajectory", "trajectory_seal", [["activation", activation], ["contract", contract], ["w0", w0]])
  const placeboReceipt = support("placebo-receipt", "placebo_receipt", [["commitment", placebo], ["randomness", randomness]])
  const feedback = support("feedback", "feedback_assignment", [["fork", forks[0]!], ["assignment", assignment], ["source", placeboReceipt]])
  const proposal = support("proposal", "revision_proposal", [["trajectory", trajectory], ["feedback", feedback]])
  const validation = support("validation", "candidate_validation", [["proposal", proposal]])

  const authority = (
    label: "main" | "evidence",
    phase: "MAIN_ADMIT" | "RECEIPT_ADMIT",
    activePolicy: Content,
    activePrincipals: ReturnType<typeof principals>,
    purpose: CanonicalAtomV2
  ) => {
    const policyPayload = parsePayload(activePolicy)
    const authorizationRef = label === "main" ? "authorization-ref:main" : options.evidenceAuthorizationRef ?? "authorization-ref:evidence"
    const capabilityId = label === "main" ? "capability:main" : options.evidenceCapabilityId ?? "capability:evidence"
    const nonceSha256 = label === "main" ? hash("nonce:main") : options.evidenceNonceSha256 ?? hash("nonce:evidence")
    const authorization = content(`authorization-${label}`, "authorization_decision", DNRD5_V2_AUTHORIZATION_DECISION_MEDIA_TYPE, {
      contractVersion: VERSION, scope: policyPayload["scope"], actor: activePrincipals.actor,
      authorizer: activePrincipals.authorizer, authorizationRef,
      recordCustodian: activePrincipals.authorizationRecordCustodian, phase,
      policyAtomKeyId: atomKeyId(activePolicy.atom), policyGeneration: 1,
      decidedAt: "2026-08-28T11:00:00.000Z", notBefore: "2026-08-28T11:00:00.000Z",
      expiresAt: "2026-08-28T13:00:00.000Z", generation: 1
    }, [["policy", activePolicy.atom]])
    const capability = content(`capability-${label}`, "capability_issuance", DNRD5_V2_CAPABILITY_ISSUANCE_MEDIA_TYPE, {
      contractVersion: VERSION, scope: policyPayload["scope"], actor: activePrincipals.actor, phase,
      purposeAtomKeyId: atomKeyId(purpose), capabilityId, nonceSha256,
      policyAtomKeyId: atomKeyId(activePolicy.atom), policyGeneration: 1,
      authorizationAtomKeyId: atomKeyId(authorization.atom), authorizationRef,
      authorizationGeneration: 1, generation: 1,
      issuedAt: "2026-08-28T11:30:00.000Z", expiresAt: "2026-08-28T12:30:00.000Z"
    }, [["authorization", authorization.atom], ["policy", activePolicy.atom]])
    const revocation = content(`revocation-${label}`, "revocation_status", DNRD5_V2_REVOCATION_STATUS_MEDIA_TYPE, {
      contractVersion: VERSION, status: "CHECKED_NOT_REVOKED", checkedAt: AT,
      authorizationAtomKeyId: atomKeyId(authorization.atom), authorizationRef,
      capabilityAtomKeyId: atomKeyId(capability.atom), capabilityId,
      policyGeneration: 1, authorizationGeneration: 1, capabilityGeneration: 1
    }, [["authorization", authorization.atom], ["capability", capability.atom]])
    const grant = content(`grant-${label}`, "grant_snapshot", DNRD5_V2_GRANT_SNAPSHOT_MEDIA_TYPE, {
      contractVersion: VERSION, policyAtomKeyId: atomKeyId(activePolicy.atom),
      authorizationAtomKeyId: atomKeyId(authorization.atom), authorizationRef,
      capabilityAtomKeyId: atomKeyId(capability.atom), capabilityId,
      revocationAtomKeyId: atomKeyId(revocation.atom), policyGeneration: 1,
      authorizationGeneration: 1, capabilityGeneration: 1
    }, [["policy", activePolicy.atom], ["authorization", authorization.atom], ["capability", capability.atom], ["revocation", revocation.atom]])
    return { phase, policy: activePolicy, authorization, capability, revocation, grant }
  }

  // The purpose and its authority refer to one another by immutable key, not by
  // content.  Stubs make that forward key reference explicit without weakening
  // the eventual state membership checks.
  const main = authority("main", "MAIN_ADMIT", mainPolicy, mainPrincipals, stub("decision-main"))
  const credit = support("credit", "credit_decision", [["trajectory", trajectory], ["credit-source", placeboReceipt], ["feedback", feedback], ["proposal", proposal], ["grant", main.grant.atom]])
  const decision = support("decision-main", "revision_admission_decision", [
    ["block", block], ["assignment", assignment], ["fork", forks[0]!], ["proposal", proposal],
    ["validation", validation], ["credit", credit], ["grant", main.grant.atom],
    ["authorization", main.authorization.atom], ["capability", main.capability.atom], ["revocation", main.revocation.atom]
  ])
  const alternateDecision = support("decision-alternate", "revision_admission_decision", [
    ["block", block], ["assignment", assignment], ["fork", forks[1]!], ["proposal", proposal],
    ["validation", validation], ["credit", credit], ["grant", main.grant.atom],
    ["authorization", main.authorization.atom], ["capability", main.capability.atom], ["revocation", main.revocation.atom]
  ])
  const evidence = authority("evidence", "RECEIPT_ADMIT", evidencePolicy, evidencePrincipals, options.alternatePurpose ? alternateDecision : decision)
  const baseAtoms = [mainPolicy.atom, randomness, evaluator, block, probe, placebo, w0, ...forks, assignment, activation, contract, trajectory, placeboReceipt, feedback, proposal, validation, main.authorization.atom, main.capability.atom, main.revocation.atom, main.grant.atom, credit, decision]
  const evidenceAtoms = [...baseAtoms, ...(evidencePolicy === mainPolicy ? [] : [evidencePolicy.atom]), evidence.authorization.atom, evidence.capability.atom, evidence.revocation.atom, evidence.grant.atom, ...(options.alternatePurpose ? [alternateDecision] : [])]
  const input = (state: object, activePrincipals: ReturnType<typeof principals>, chain: ReturnType<typeof authority>) => ({
    _tag: "Dnrd5V2AuthorityStateInput" as const,
    contractVersion: VERSION,
    evaluatedAt: AT,
    principals: activePrincipals,
    state,
    chain
  })
  return {
    main: input({ schemaVersion: DNRD5_V2_SCHEMA_VERSION, revision: 7, bootstrapClosed: true, atoms: baseAtoms, acceptedTransitionIds: history(7) }, mainPrincipals, main),
    evidence: input({ schemaVersion: DNRD5_V2_SCHEMA_VERSION, revision: 8, bootstrapClosed: true, atoms: evidenceAtoms, acceptedTransitionIds: history(8) }, evidencePrincipals, evidence),
    proposal
  }
}

const invalid = (value: unknown): void =>
  expect(Either.isLeft(validateDnrd5V2AuthorityPayloadAtState(value))).toBe(true)
const replaceChainPayload = (
  input: any,
  role: "policy" | "authorization" | "capability" | "revocation" | "grant",
  mutate: (payload: Record<string, unknown>) => Record<string, unknown>
): void => {
  const original = input.chain[role] as Content
  const replacement = replacePayload(original, mutate(parsePayload(original)))
  input.chain[role] = replacement
  input.state = { ...input.state, atoms: input.state.atoms.map((atom: CanonicalAtomV2) => atomKeyId(atom) === atomKeyId(original.atom) ? replacement.atom : atom) }
}

describe("DNRD-5 v2 authority payload at a supplied validated state", () => {
  it("accepts distinct MAIN_ADMIT and RECEIPT_ADMIT chains at append-only S0/R1", () => {
    const { main, evidence } = makeFixture()
    expect(Either.isRight(validateDnrd5V2AuthorityPayloadAtState(main))).toBe(true)
    expect(Either.isRight(validateDnrd5V2AuthorityPayloadAtState(evidence))).toBe(true)
    const pair = validateDnrd5V2AuthorityDisjointPair(main, evidence)
    expect(Either.isRight(pair)).toBe(true)
    if (Either.isRight(pair)) {
      expect(pair.right.main.stateRevision).toBe(7)
      expect(pair.right.evidence.stateRevision).toBe(8)
      expect(pair.right.main.chain.purposeAtomKeyId).toBe(pair.right.evidence.chain.purposeAtomKeyId)
      expect(pair.right.status).toBe("STRUCTURAL_APPEND_ONLY_STATE_PAIR_AND_DISJOINT_AUTHORITY_NOT_CAS")
      expect(pair.right.terminal).toContain("NOT_EXACT_CAS1_RESULT")
    }
  })

  it("rejects malformed state shape, history, descriptor bytes, and missing state atoms", () => {
    const malformed = makeFixture().main as any
    malformed.state.extra = true
    invalid(malformed)
    const badHistory = makeFixture().main as any
    badHistory.state.acceptedTransitionIds = badHistory.state.acceptedTransitionIds.slice(1)
    invalid(badHistory)
    const duplicateHistory = makeFixture().main as any
    duplicateHistory.state.acceptedTransitionIds[1] = duplicateHistory.state.acceptedTransitionIds[0]
    invalid(duplicateHistory)
    const byteDrift = makeFixture().main as any
    byteDrift.chain.policy.atom.content.sha256 = "f".repeat(64)
    invalid(byteDrift)
    const absent = makeFixture().main as any
    absent.state.atoms = absent.state.atoms.filter((atom: CanonicalAtomV2) => atomKeyId(atom) !== atomKeyId(absent.chain.grant.atom))
    invalid(absent)
  })

  it("rejects noncanonical, missing, wrong-kind, and crosswired purpose/authority payloads", () => {
    const missingPurpose = makeFixture().main as any
    replaceChainPayload(missingPurpose, "capability", (payload) => ({ ...payload, purposeAtomKeyId: `${DNRD5_V2_SCHEMA_VERSION}|${LINEAGE}|absent|0` }))
    invalid(missingPurpose)
    const noncanonicalPurpose = makeFixture().main as any
    replaceChainPayload(noncanonicalPurpose, "capability", (payload) => ({ ...payload, purposeAtomKeyId: "not-a-key" }))
    invalid(noncanonicalPurpose)
    const wrongKind = makeFixture()
    replaceChainPayload(wrongKind.main as any, "capability", (payload) => ({ ...payload, purposeAtomKeyId: atomKeyId(wrongKind.proposal) }))
    invalid(wrongKind.main)
    const crosswired = makeFixture().main as any
    replaceChainPayload(crosswired, "capability", (payload) => ({ ...payload, authorizationAtomKeyId: atomKeyId(crosswired.chain.policy.atom) }))
    invalid(crosswired)
  })

  it("rejects time, generation, self-authority, excess/revoked payloads, and duplicate revocation", () => {
    const early = makeFixture().main as any
    replaceChainPayload(early, "capability", (payload) => ({ ...payload, issuedAt: "2026-08-28T10:59:59.999Z" }))
    invalid(early)
    const generation = makeFixture().main as any
    replaceChainPayload(generation, "grant", (payload) => ({ ...payload, capabilityGeneration: 2 }))
    invalid(generation)
    const selfAuthority = makeFixture().main as any
    replaceChainPayload(selfAuthority, "authorization", (payload) => ({ ...payload, authorizer: selfAuthority.principals.actor }))
    invalid(selfAuthority)
    const excess = makeFixture().main as any
    replaceChainPayload(excess, "revocation", (payload) => ({ ...payload, excess: true }))
    invalid(excess)
    const revoked = makeFixture().main as any
    replaceChainPayload(revoked, "revocation", (payload) => ({ ...payload, status: "REVOKED" }))
    invalid(revoked)
    const duplicate = makeFixture().main as any
    const original = duplicate.chain.revocation.atom as CanonicalAtomV2
    duplicate.state.atoms = [...duplicate.state.atoms, { ...original, key: { ...original.key, atomUid: "revocation-duplicate" } }]
    invalid(duplicate)
  })

  it("rejects pair actor/scope/principal/purpose mismatch, reuse, and non-successors", () => {
    const actor = makeFixture({ evidenceActor: "principal:other" })
    expect(Either.isRight(validateDnrd5V2AuthorityPayloadAtState(actor.evidence))).toBe(true)
    expect(Either.isLeft(validateDnrd5V2AuthorityDisjointPair(actor.main, actor.evidence))).toBe(true)
    const scope = makeFixture({ evidenceScope: "scope:other" })
    expect(Either.isRight(validateDnrd5V2AuthorityPayloadAtState(scope.evidence))).toBe(true)
    expect(Either.isLeft(validateDnrd5V2AuthorityDisjointPair(scope.main, scope.evidence))).toBe(true)
    const purpose = makeFixture({ alternatePurpose: true })
    expect(Either.isRight(validateDnrd5V2AuthorityPayloadAtState(purpose.evidence))).toBe(true)
    expect(Either.isLeft(validateDnrd5V2AuthorityDisjointPair(purpose.main, purpose.evidence))).toBe(true)
    for (const options of [
      { evidenceAuthorizationRef: "authorization-ref:main" },
      { evidenceCapabilityId: "capability:main" },
      { evidenceNonceSha256: hash("nonce:main") }
    ]) {
      const reused = makeFixture(options)
      expect(Either.isLeft(validateDnrd5V2AuthorityDisjointPair(reused.main, reused.evidence))).toBe(true)
    }
    const nonSuccessor = makeFixture() as any
    nonSuccessor.evidence.state = { ...nonSuccessor.evidence.state, revision: 7, acceptedTransitionIds: history(7) }
    expect(Either.isRight(validateDnrd5V2AuthorityPayloadAtState(nonSuccessor.evidence))).toBe(true)
    expect(Either.isLeft(validateDnrd5V2AuthorityDisjointPair(nonSuccessor.main, nonSuccessor.evidence))).toBe(true)
  })

  it("returns a frozen structural snapshot, not a Permit or occurrence claim", () => {
    const result = validateDnrd5V2AuthorityPayloadAtState(makeFixture().main)
    expect(Either.isRight(result)).toBe(true)
    if (Either.isRight(result)) {
      expect(Object.isFrozen(result.right)).toBe(true)
      expect(Object.isFrozen(result.right.chain)).toBe(true)
      expect(() => { ;(result.right.chain as { actor: string }).actor = "principal:mutated" }).toThrow(TypeError)
      expect(result.right.status).toBe("STRUCTURAL_AUTHORITY_PAYLOAD_AT_CALLER_STATE_NOT_RECOVERY_OR_PERMIT")
      expect(result.right.terminal).toContain("NOT_DURABLE_RECOVERY")
    }
  })
})
