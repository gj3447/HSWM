import { expect, it } from "@effect/vitest"
import { Effect, Either } from "effect"
import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

import {
  canonicalAtomV2SchemaContentBytes,
  decodeCanonicalAtomV2SchemaContent,
  describeCanonicalAtomV2Envelope,
  makeCanonicalAtomV2ContentBoundInput,
  type CanonicalAtomV2ContentAuthorizationGrant,
  type CanonicalAtomV2WriteContentBinding,
  type CommitCanonicalAtomsV2ContentBound
} from "../src/canonical-atom-v2-content-bound.js"
import {
  makeCanonicalAtomV2ContentDescriptor,
  sameCanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2ContentDescriptor
} from "../src/canonical-atom-v2-content.js"
import {
  CanonicalAtomV2DurableRuntime,
  makeCanonicalAtomV2DurableRuntimeFileLayer,
  makeCanonicalAtomV2DurableRuntimeMemoryLayerForTest
} from "../src/canonical-atom-v2-durable-runtime.js"
import {
  DNRD5_CAPABILITY_CONSUMPTION_KIND,
  DNRD5_CAPABILITY_CONSUMPTION_OWNER,
  DNRD5_CAPABILITY_CONSUMPTION_TERMINAL,
  dnrd5CapabilityConsumptionAtomUid,
  makeDnrd5CapabilityConsumptionAtom,
  type Dnrd5CapabilityConsumptionReferenceAtoms
} from "../src/canonical-atom-v2-dnrd5-capability-consumption.js"
import {
  DNRD5_DURABLE_PERMIT_SUBMIT_V1,
  describeDnrd5CapabilityConsumptionCommandIntent,
  describeDnrd5CommandSets,
  submitDnrd5LocalExperimentalState,
  type Dnrd5DurablePermitSubmitInput
} from "../src/canonical-atom-v2-dnrd5-durable-permit.js"
import {
  DNRD5_AUTHORIZATION_DECISION_MEDIA_TYPE,
  DNRD5_CAPABILITY_ISSUANCE_MEDIA_TYPE,
  DNRD5_GRANT_SNAPSHOT_MEDIA_TYPE,
  DNRD5_LOCAL_EXPERIMENTAL_DOMAIN,
  DNRD5_LOCAL_EXPERIMENTAL_PERMIT_V1,
  DNRD5_PERMIT_POLICY_MEDIA_TYPE,
  DNRD5_REVOCATION_MEDIA_TYPE,
  resolveDnrd5LocalExperimentalPermit,
  type Dnrd5LocalExperimentalPermitInput
} from "../src/canonical-atom-v2-dnrd5-permit.js"
import {
  DNRD5_OWNER_ROLE_BY_KIND,
  DNRD5_REFERENCE_TYPE,
  DNRD5_SCHEMA_VERSION,
  makeDnrd5CanonicalSchemaV2,
  type Dnrd5CanonicalAtomKind
} from "../src/canonical-atom-v2-dnrd5-schema.js"
import { canonicalJsonBytes } from "../src/canonical-atom-v2-json.js"
import { canonicalAtomV2StateSha256 } from "../src/canonical-atom-v2-state-journal.js"
import {
  HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
  type CanonicalAtomV2,
  type CanonicalAtomV2Key,
  type CanonicalAtomV2Reference,
  type CommitCanonicalAtomsV2Command
} from "../src/canonical-atom-v2-schema.js"

const JOURNAL_LINEAGE = "journal:dnrd5:durable-permit-test"
const ATOM_LINEAGE = "lineage:dnrd5:durable-permit-test"
const BOOTSTRAP_AUTHORIZATION = "authorization:dnrd5:test-bootstrap"
const BOOTSTRAP_SCOPE = "scope:dnrd5:test-bootstrap"
const CAPABILITY_ID = "capability:dnrd5:test-one-shot"
const SCOPE = "scope:dnrd5:local-experiment"
const ACTOR = "principal:dnrd5:actor"
const EVALUATED_AT = "2026-08-28T12:00:01.000Z"
const NONCE_SHA256 = "4".repeat(64)
const EVIDENCE_SHA256 = "e".repeat(64)

const rightOrThrow = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw new Error("DNRD-5 durable fixture construction failed")
  return value.right
}

interface Payload {
  readonly mediaType: string
  readonly bytes: Uint8Array
  readonly descriptor: CanonicalAtomV2ContentDescriptor
}

const payload = (mediaType: string, core: unknown): Payload => {
  const bytes = rightOrThrow(canonicalJsonBytes(core))
  return {
    mediaType,
    bytes,
    descriptor: rightOrThrow(makeCanonicalAtomV2ContentDescriptor(mediaType, bytes))
  }
}

const key = (atomUid: string): CanonicalAtomV2Key => ({
  schemaVersion: DNRD5_SCHEMA_VERSION,
  lineageId: ATOM_LINEAGE,
  atomUid,
  revisionId: 0
})

const reference = (
  role: string,
  target: CanonicalAtomV2
): CanonicalAtomV2Reference => ({
  referenceType: DNRD5_REFERENCE_TYPE,
  role: `role:dnrd5:${role}`,
  target: target.key
})

const atom = (
  atomUid: string,
  kind: Dnrd5CanonicalAtomKind,
  content: CanonicalAtomV2ContentDescriptor,
  references: ReadonlyArray<CanonicalAtomV2Reference> = []
): CanonicalAtomV2 => ({
  _tag: "CanonicalAtomV2",
  contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  key: key(atomUid),
  kind: `hswm:dnrd5:${kind}`,
  responsibilityOwner: `owner:dnrd5:${DNRD5_OWNER_ROLE_BY_KIND[kind]}`,
  content,
  provenance:
    references.length === 0
      ? { mode: "BOOTSTRAP", evidenceSha256: EVIDENCE_SHA256, sourceRef: null }
      : {
          mode: "DERIVATION",
          evidenceSha256: EVIDENCE_SHA256,
          sourceRef: references[0]!.target
        },
  lifecycle: "ADMITTED",
  references
})

const plain = (atomUid: string): Payload =>
  payload("application/json", {
    fixture: atomUid,
    terminal: "TEST_ONLY_NOT_PRODUCTION_EVIDENCE"
  })

const bindingFor = (candidate: CanonicalAtomV2): CanonicalAtomV2WriteContentBinding => ({
  key: candidate.key,
  payload: candidate.content,
  envelope: rightOrThrow(describeCanonicalAtomV2Envelope(candidate))
})

const schemaBytes = rightOrThrow(
  canonicalAtomV2SchemaContentBytes(makeDnrd5CanonicalSchemaV2())
)
const schemaContent = rightOrThrow(decodeCanonicalAtomV2SchemaContent(schemaBytes))
const grants: ReadonlyArray<CanonicalAtomV2ContentAuthorizationGrant> = [
  {
    authorizationRef: BOOTSTRAP_AUTHORIZATION,
    schemaVersion: DNRD5_SCHEMA_VERSION,
    schemaContentSha256: schemaContent.binding.content.sha256,
    scopes: [BOOTSTRAP_SCOPE]
  },
  {
    authorizationRef: CAPABILITY_ID,
    schemaVersion: DNRD5_SCHEMA_VERSION,
    schemaContentSha256: schemaContent.binding.content.sha256,
    scopes: [SCOPE]
  }
]

const consumptionUid = rightOrThrow(
  dnrd5CapabilityConsumptionAtomUid(NONCE_SHA256)
)

const finalReadKinds: ReadonlyArray<readonly [string, Dnrd5CanonicalAtomKind]> = [
  ["grant", "grant_snapshot"],
  ["capability", "capability_issuance"],
  ["revocation", "revocation_status"],
  ["credit", "credit_decision"],
  ["validation", "candidate_validation"],
  ["proposal", "revision_proposal"],
  ["restore-policy", "restore_policy"]
]

const projectionAtoms = finalReadKinds.map(([atomUid, kind]) =>
  atom(atomUid, kind, plain(`projection:${atomUid}`).descriptor)
)
const projectionWrites = [
  atom(
    consumptionUid,
    "capability_consumption",
    plain("projection:consumption").descriptor
  ),
  atom(
    "transition-receipt:admit",
    "transition_receipt",
    plain("projection:receipt").descriptor
  ),
  atom(
    "macro-disposition:admit",
    "macro_disposition",
    plain("projection:macro").descriptor
  )
]

const command = (
  writes: ReadonlyArray<CanonicalAtomV2>,
  transitionId = "transition:dnrd5:admit-one-shot"
): CommitCanonicalAtomsV2Command => ({
  _tag: "CommitCanonicalAtomsV2",
  contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
  transitionId,
  expectedStateRevision: 1,
  schemaVersion: DNRD5_SCHEMA_VERSION,
  actorClaim: ACTOR,
  authorizationRef: CAPABILITY_ID,
  scope: SCOPE,
  decidedAt: EVALUATED_AT,
  traceRef: null,
  readSet: finalReadKinds.map(([atomUid]) => key(atomUid)),
  writes,
  provenanceSha256: "d".repeat(64)
})

const commandSets = rightOrThrow(
  describeDnrd5CommandSets(command(projectionWrites), projectionAtoms)
)

interface DurableFixture {
  readonly input: Dnrd5DurablePermitSubmitInput
  readonly consumptionUid: string
}

const stage = (
  runtime: CanonicalAtomV2DurableRuntime["Type"],
  item: Payload
) =>
  runtime.stageContent(item.mediaType, item.bytes).pipe(
    Effect.tap((stored) =>
      Effect.sync(() =>
        expect(sameCanonicalAtomV2ContentDescriptor(stored, item.descriptor)).toBe(true)
      )
    )
  )

const buildFixture = Effect.gen(function* () {
  const runtime = yield* CanonicalAtomV2DurableRuntime
  const validatorPayload = plain("validation")
  const policyCore = {
    scope: SCOPE,
    allowedEffects: ["ADMIT_REVISION"] as const,
    allowedActors: [ACTOR],
    validator: validatorPayload.descriptor,
    validatorPrincipal: "principal:dnrd5:validator",
    allowedReadKindsSha256: commandSets.readKindsSha256,
    allowedWriteKindsSha256: commandSets.writeKindsSha256,
    allowedTargetKindsSha256: commandSets.targetKindsSha256,
    exactReadsetSha256: commandSets.readsetSha256,
    exactWritesetSha256: commandSets.writesetSha256,
    exactTargetAtomKeysSha256: commandSets.targetAtomKeysSha256,
    restore: null
  }
  const policyPayload = payload(DNRD5_PERMIT_POLICY_MEDIA_TYPE, policyCore)
  const authorizationCore = {
    decision: "GRANTED" as const,
    actor: ACTOR,
    authorizer: "principal:dnrd5:authorizer",
    recordCustodian: "principal:dnrd5:authorization-record",
    effect: "ADMIT_REVISION" as const,
    scope: SCOPE,
    decidedAt: "2026-08-28T12:00:00.000Z",
    notBefore: "2026-08-28T12:00:00.500Z",
    expiresAt: "2026-08-28T12:02:00.000Z",
    generation: 1
  }
  const authorizationPayload = payload(
    DNRD5_AUTHORIZATION_DECISION_MEDIA_TYPE,
    authorizationCore
  )
  const capabilityCore = {
    capabilityId: CAPABILITY_ID,
    issuedAt: "2026-08-28T12:00:00.750Z",
    expiresAt: "2026-08-28T12:01:30.000Z",
    scope: SCOPE,
    allowedEffect: "ADMIT_REVISION" as const,
    oneShotNonceSha256: NONCE_SHA256,
    policy: policyPayload.descriptor,
    authorization: authorizationPayload.descriptor,
    authorizationGeneration: 1,
    capabilityGeneration: 2
  }
  const capabilityPayload = payload(
    DNRD5_CAPABILITY_ISSUANCE_MEDIA_TYPE,
    capabilityCore
  )
  const revocationCore = {
    checkedAt: EVALUATED_AT,
    status: "CHECKED_NOT_REVOKED" as const,
    authorization: authorizationPayload.descriptor,
    capability: capabilityPayload.descriptor,
    authorizationGeneration: 1,
    capabilityGeneration: 2
  }
  const revocationPayload = payload(DNRD5_REVOCATION_MEDIA_TYPE, revocationCore)
  const grantCore = {
    policy: policyPayload.descriptor,
    authorization: authorizationPayload.descriptor,
    capability: capabilityPayload.descriptor,
    revocation: revocationPayload.descriptor
  }
  const grantPayload = payload(DNRD5_GRANT_SNAPSHOT_MEDIA_TYPE, grantCore)

  const payloads = new Map<string, Payload>()
  const plainFor = (atomUid: string): Payload => {
    const existing = payloads.get(atomUid)
    if (existing !== undefined) return existing
    const created = atomUid === "validation" ? validatorPayload : plain(atomUid)
    payloads.set(atomUid, created)
    return created
  }
  for (const [atomUid, item] of [
    ["policy", policyPayload],
    ["authorization", authorizationPayload],
    ["capability", capabilityPayload],
    ["revocation", revocationPayload],
    ["grant", grantPayload],
    ["validation", validatorPayload]
  ] as const) payloads.set(atomUid, item)

  const randomness = atom("randomness", "study_randomness", plainFor("randomness").descriptor)
  const evaluator = atom("evaluator", "evaluator_commitment", plainFor("evaluator").descriptor)
  const block = atom("block", "block_spec", plainFor("block").descriptor, [
    reference("randomness", randomness),
    reference("evaluator", evaluator)
  ])
  const probe = atom("probe", "probe_commitment", plainFor("probe").descriptor, [
    reference("block-spec", block),
    reference("randomness", randomness)
  ])
  const w0 = atom("w0", "w0_snapshot", plainFor("w0").descriptor, [
    reference("block-spec", block)
  ])
  const forks = [1, 2, 3, 4].map((index) =>
    atom(`fork-${index}`, "fork_incidence", plainFor(`fork-${index}`).descriptor, [
      reference("w0", w0)
    ])
  )
  const assignment = atom(
    "assignment",
    "block_assignment",
    plainFor("assignment").descriptor,
    [
      reference("randomness", randomness),
      reference("block-spec", block),
      ...forks.map((fork) => reference("fork", fork))
    ]
  )
  const activation = atom(
    "activation",
    "episode_activation",
    plainFor("activation").descriptor,
    [
      reference("block-spec", block),
      reference("probe", probe),
      reference("w0", w0),
      ...forks.map((fork) => reference("fork", fork)),
      reference("assignment", assignment),
      reference("evaluator", evaluator)
    ]
  )
  const trajectoryContract = atom(
    "trajectory-contract",
    "trajectory_contract",
    plainFor("trajectory-contract").descriptor,
    [reference("activation", activation)]
  )
  const trajectorySeal = atom(
    "trajectory-seal",
    "trajectory_seal",
    plainFor("trajectory-seal").descriptor,
    [
      reference("activation", activation),
      reference("contract", trajectoryContract),
      reference("w0", w0)
    ]
  )
  const policyAtom = atom("policy", "permit_policy", policyPayload.descriptor)
  const authorizationAtom = atom(
    "authorization",
    "authorization_decision",
    authorizationPayload.descriptor,
    [reference("policy", policyAtom)]
  )
  const capabilityAtom = atom(
    "capability",
    "capability_issuance",
    capabilityPayload.descriptor,
    [
      reference("authorization", authorizationAtom),
      reference("policy", policyAtom)
    ]
  )
  const revocationAtom = atom(
    "revocation",
    "revocation_status",
    revocationPayload.descriptor,
    [
      reference("authorization", authorizationAtom),
      reference("capability", capabilityAtom)
    ]
  )
  const evaluatorCapability = atom(
    "evaluator-capability",
    "evaluator_capability",
    plainFor("evaluator-capability").descriptor,
    [
      reference("commitment", evaluator),
      reference("capability", capabilityAtom),
      reference("authorization", authorizationAtom),
      reference("revocation", revocationAtom)
    ]
  )
  const evaluatorRelease = atom(
    "evaluator-release",
    "evaluator_release",
    plainFor("evaluator-release").descriptor,
    [
      reference("trajectory", trajectorySeal),
      reference("capability", evaluatorCapability),
      reference("authorization", authorizationAtom),
      reference("revocation", revocationAtom)
    ]
  )
  const hiddenOutcome = atom(
    "hidden-outcome",
    "hidden_outcome",
    plainFor("hidden-outcome").descriptor,
    [
      reference("trajectory", trajectorySeal),
      reference("release", evaluatorRelease),
      reference("commitment", evaluator)
    ]
  )
  const feedback = atom(
    "feedback",
    "feedback_assignment",
    plainFor("feedback").descriptor,
    [
      reference("fork", forks[0]!),
      reference("assignment", assignment),
      reference("source", hiddenOutcome)
    ]
  )
  const grantAtom = atom("grant", "grant_snapshot", grantPayload.descriptor, [
    reference("policy", policyAtom),
    reference("authorization", authorizationAtom),
    reference("capability", capabilityAtom),
    reference("revocation", revocationAtom)
  ])
  const proposal = atom(
    "proposal",
    "revision_proposal",
    plainFor("proposal").descriptor,
    [
      reference("trajectory", trajectorySeal),
      reference("feedback", feedback)
    ]
  )
  const validation = atom(
    "validation",
    "candidate_validation",
    validatorPayload.descriptor,
    [reference("proposal", proposal)]
  )
  const credit = atom("credit", "credit_decision", plainFor("credit").descriptor, [
    reference("trajectory", trajectorySeal),
    reference("outcome", hiddenOutcome),
    reference("feedback", feedback),
    reference("proposal", proposal),
    reference("grant", grantAtom)
  ])
  const restorePolicy = atom(
    "restore-policy",
    "restore_policy",
    plainFor("restore-policy").descriptor,
    [reference("policy", policyAtom), reference("capability", capabilityAtom)]
  )
  const initialAtoms = [
    randomness,
    evaluator,
    block,
    probe,
    w0,
    ...forks,
    assignment,
    activation,
    trajectoryContract,
    trajectorySeal,
    policyAtom,
    authorizationAtom,
    capabilityAtom,
    revocationAtom,
    evaluatorCapability,
    evaluatorRelease,
    hiddenOutcome,
    feedback,
    grantAtom,
    proposal,
    validation,
    credit,
    restorePolicy
  ]
  for (const item of payloads.values()) yield* stage(runtime, item)
  const initialCommand: CommitCanonicalAtomsV2Command = {
    _tag: "CommitCanonicalAtomsV2",
    contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
    transitionId: "transition:dnrd5:test-bootstrap",
    expectedStateRevision: 0,
    schemaVersion: DNRD5_SCHEMA_VERSION,
    actorClaim: "principal:dnrd5:test-bootstrap",
    authorizationRef: BOOTSTRAP_AUTHORIZATION,
    scope: BOOTSTRAP_SCOPE,
    decidedAt: "2026-08-28T11:59:59.000Z",
    traceRef: null,
    readSet: [],
    writes: initialAtoms,
    provenanceSha256: "b".repeat(64)
  }
  yield* runtime.submit(
    makeCanonicalAtomV2ContentBoundInput(
      schemaContent.binding.content.sha256,
      initialCommand,
      initialAtoms.map(bindingFor)
    )
  )
  const current = yield* runtime.snapshot
  const stateSha256 = rightOrThrow(canonicalAtomV2StateSha256(current.canonical))

  const receiptPayload = plain("transition-receipt:admit")
  const macroPayload = plain("macro-disposition:admit")
  const transitionReceipt = atom(
    "transition-receipt:admit",
    "transition_receipt",
    receiptPayload.descriptor,
    [
      reference("credit", credit),
      reference("validation", validation),
      reference("grant", grantAtom)
    ]
  )
  const macroDisposition = atom(
    "macro-disposition:admit",
    "macro_disposition",
    macroPayload.descriptor,
    [
      reference("proposal", proposal),
      reference("receipt", transitionReceipt),
      reference("restore-policy", restorePolicy)
    ]
  )
  const placeholderConsumption: CanonicalAtomV2 = {
    ...atom(
      consumptionUid,
      "capability_consumption",
      plain("consumption-placeholder").descriptor,
      [
        reference("grant", grantAtom),
        reference("capability", capabilityAtom),
        reference("revocation", revocationAtom),
        reference("credit", credit),
        reference("validation", validation)
      ]
    ),
    responsibilityOwner: DNRD5_CAPABILITY_CONSUMPTION_OWNER,
    kind: DNRD5_CAPABILITY_CONSUMPTION_KIND
  }
  const provisionalCommand = command([
    placeholderConsumption,
    transitionReceipt,
    macroDisposition
  ])
  const commandIntent = rightOrThrow(
    describeDnrd5CapabilityConsumptionCommandIntent(
      provisionalCommand,
      consumptionUid
    )
  )
  const permitInput: Dnrd5LocalExperimentalPermitInput = {
    _tag: "Dnrd5LocalExperimentalPermitInput",
    contractVersion: DNRD5_LOCAL_EXPERIMENTAL_PERMIT_V1,
    domain: DNRD5_LOCAL_EXPERIMENTAL_DOMAIN,
    evaluatedAt: EVALUATED_AT,
    effect: "ADMIT_REVISION",
    snapshot: {
      journalLineageId: JOURNAL_LINEAGE,
      journalHead: current.journalHead,
      stateRevision: current.canonical.revision,
      stateSha256
    },
    principals: {
      actor: ACTOR,
      authorizer: "principal:dnrd5:authorizer",
      canonicalStateCustodian: "principal:dnrd5:state",
      restoreCustodian: "principal:dnrd5:restore",
      creditAdjudicator: "principal:dnrd5:credit",
      authorizationDecisionRecordCustodian:
        "principal:dnrd5:authorization-record",
      validator: "principal:dnrd5:validator",
      provenanceSealer: "principal:dnrd5:provenance",
      trajectorySealer: "principal:dnrd5:trajectory"
    },
    policy: { descriptor: policyPayload.descriptor, ...policyCore },
    authorizationDecision: {
      descriptor: authorizationPayload.descriptor,
      ...authorizationCore
    },
    capability: { issuance: capabilityPayload.descriptor, ...capabilityCore },
    currentRevocation: {
      descriptor: revocationPayload.descriptor,
      ...revocationCore
    },
    grantSnapshot: {
      descriptor: grantPayload.descriptor,
      ...grantCore,
      snapshotSha256: grantPayload.descriptor.sha256
    },
    transition: {
      command: commandIntent.descriptor,
      readKindsSha256: commandSets.readKindsSha256,
      writeKindsSha256: commandSets.writeKindsSha256,
      targetKindsSha256: commandSets.targetKindsSha256,
      readsetSha256: commandSets.readsetSha256,
      writesetSha256: commandSets.writesetSha256,
      targetAtomKeysSha256: commandSets.targetAtomKeysSha256,
      validator: validatorPayload.descriptor,
      validatorPrincipal: "principal:dnrd5:validator",
      provenance: trajectoryContract.content,
      provenanceSealer: "principal:dnrd5:provenance",
      trajectoryContract: trajectoryContract.content,
      trajectorySeal: trajectorySeal.content,
      trajectorySealer: "principal:dnrd5:trajectory"
    },
    restore: null
  }
  const permit = rightOrThrow(resolveDnrd5LocalExperimentalPermit(permitInput))
  const consumptionReferences: Dnrd5CapabilityConsumptionReferenceAtoms = {
    grantSnapshot: grantAtom,
    capabilityIssuance: capabilityAtom,
    currentRevocation: revocationAtom,
    creditDecision: credit,
    candidateValidation: validation,
    restorePolicy: null,
    stagingSuccessor: null,
    w0Snapshot: null
  }
  const consumption = rightOrThrow(
    makeDnrd5CapabilityConsumptionAtom(
      {
        _tag: "Dnrd5CapabilityConsumption",
        contractVersion: "hswm-dnrd5-capability-consumption/v1",
        effect: "ADMIT_REVISION",
        capabilityNonceSha256: NONCE_SHA256,
        grantSnapshot: grantPayload.descriptor,
        capabilityIssuance: capabilityPayload.descriptor,
        currentRevocation: revocationPayload.descriptor,
        permitInputSha256: permit.inputSha256,
        permitResolutionCoreSha256: permit.resolutionCoreSha256,
        expectedJournalHead: current.journalHead,
        expectedStateRevision: current.canonical.revision,
        expectedStateSha256: stateSha256,
        transitionId: provisionalCommand.transitionId,
        commandIntentSha256: commandIntent.sha256,
        evaluatedAt: EVALUATED_AT,
        terminal: DNRD5_CAPABILITY_CONSUMPTION_TERMINAL
      },
      consumptionReferences
    )
  )
  const finalCommand = command([
    consumption.atom,
    transitionReceipt,
    macroDisposition
  ])
  const finalIntent = rightOrThrow(
    describeDnrd5CapabilityConsumptionCommandIntent(finalCommand, consumptionUid)
  )
  expect(finalIntent.sha256).toBe(commandIntent.sha256)
  yield* stage(runtime, receiptPayload)
  yield* stage(runtime, macroPayload)
  const transition: CommitCanonicalAtomsV2ContentBound =
    makeCanonicalAtomV2ContentBoundInput(
      schemaContent.binding.content.sha256,
      finalCommand,
      [consumption.atom, transitionReceipt, macroDisposition].map(bindingFor)
    )
  return {
    input: {
      _tag: "Dnrd5DurablePermitSubmitInput",
      contractVersion: DNRD5_DURABLE_PERMIT_SUBMIT_V1,
      permitInput,
      transition,
      consumptionContentBytes: consumption.bytes
    },
    consumptionUid
  } satisfies DurableFixture
})

const layer = () =>
  makeCanonicalAtomV2DurableRuntimeMemoryLayerForTest(
    JOURNAL_LINEAGE,
    schemaBytes,
    grants
  )

const withTemporaryRoot = <A, E>(
  use: (root: string) => Effect.Effect<A, E>
): Effect.Effect<A, E> => {
  const root = mkdtempSync(join(tmpdir(), "hswm-dnrd5-durable-permit-"))
  return use(root).pipe(
    Effect.ensuring(
      Effect.sync(() => rmSync(root, { recursive: true, force: true }))
    )
  )
}

it.effect("commits admission and one-shot capability consumption in one durable command", () =>
  Effect.gen(function* () {
    const fixture = yield* buildFixture
    const result = yield* submitDnrd5LocalExperimentalState(fixture.input)
    expect(result.state.canonical.revision).toBe(2)
    expect(result.receipt.commit.receipt.transitionId).toBe(
      "transition:dnrd5:admit-one-shot"
    )
    expect(
      result.state.canonical.atoms.filter(
        ({ key: atomKey }) => atomKey.atomUid === fixture.consumptionUid
      )
    ).toHaveLength(1)
    expect(
      result.receipt.commit.writeBindings.map(({ key: atomKey }) => atomKey.atomUid)
    ).toEqual([
      fixture.consumptionUid,
      "macro-disposition:admit",
      "transition-receipt:admit"
    ])

    const replay = yield* submitDnrd5LocalExperimentalState(fixture.input).pipe(
      Effect.either
    )
    expect(Either.isLeft(replay)).toBe(true)
    if (Either.isLeft(replay)) {
      expect(replay.left).toMatchObject({
        _tag: "Dnrd5DurablePermitError",
        code: "NONCE_ALREADY_CONSUMED"
      })
    }
    const runtime = yield* CanonicalAtomV2DurableRuntime
    expect((yield* runtime.history)).toHaveLength(2)
  }).pipe(Effect.provide(layer()))
)

it.effect("classifies exactly one of two concurrent same-nonce submissions as consumed", () =>
  Effect.gen(function* () {
    const fixture = yield* buildFixture
    const attempts = yield* Effect.all(
      [
        submitDnrd5LocalExperimentalState(fixture.input).pipe(Effect.either),
        submitDnrd5LocalExperimentalState(fixture.input).pipe(Effect.either)
      ],
      { concurrency: "unbounded" }
    )
    expect(attempts.filter(Either.isRight)).toHaveLength(1)
    const failures = attempts.filter(Either.isLeft)
    expect(failures).toHaveLength(1)
    expect(failures[0]!.left).toMatchObject({
      _tag: "Dnrd5DurablePermitError",
      code: "NONCE_ALREADY_CONSUMED"
    })
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const current = yield* runtime.snapshot
    expect(current.canonical.revision).toBe(2)
    expect(
      current.canonical.atoms.filter(
        ({ key: atomKey }) => atomKey.atomUid === fixture.consumptionUid
      )
    ).toHaveLength(1)
  }).pipe(Effect.provide(layer()))
)

it.effect("recovers the consumption atom after a fresh file-runtime open", () =>
  withTemporaryRoot((root) => {
    const fileLayer = () =>
      makeCanonicalAtomV2DurableRuntimeFileLayer(
        root,
        JOURNAL_LINEAGE,
        schemaBytes,
        grants
      )
    return Effect.gen(function* () {
      const fixture = yield* buildFixture
      yield* submitDnrd5LocalExperimentalState(fixture.input)
      return fixture
    }).pipe(
      Effect.provide(fileLayer()),
      Effect.flatMap((fixture) =>
        Effect.gen(function* () {
          const replay = yield* submitDnrd5LocalExperimentalState(
            fixture.input
          ).pipe(Effect.either)
          expect(Either.isLeft(replay)).toBe(true)
          if (Either.isLeft(replay)) {
            expect(replay.left).toMatchObject({ code: "NONCE_ALREADY_CONSUMED" })
          }
          const runtime = yield* CanonicalAtomV2DurableRuntime
          const recovered = yield* runtime.snapshot
          expect(recovered.canonical.revision).toBe(2)
          expect(
            recovered.canonical.atoms.filter(
              ({ key: atomKey }) => atomKey.atomUid === fixture.consumptionUid
            )
          ).toHaveLength(1)
          expect(yield* runtime.history).toHaveLength(2)
        }).pipe(Effect.provide(fileLayer()))
      )
    )
  })
)

it.effect("rejects a stale snapshot and an altered command before durable admission", () =>
  Effect.gen(function* () {
    const fixture = yield* buildFixture
    const stale: any = structuredClone(fixture.input)
    stale.permitInput.snapshot.stateSha256 = "0".repeat(64)
    const staleAttempt = yield* submitDnrd5LocalExperimentalState(stale).pipe(
      Effect.either
    )
    expect(Either.isLeft(staleAttempt)).toBe(true)
    if (Either.isLeft(staleAttempt)) {
      expect(staleAttempt.left).toMatchObject({ code: "SNAPSHOT_STALE" })
    }

    const altered: any = structuredClone(fixture.input)
    altered.transition.command.transitionId = "transition:dnrd5:altered"
    const alteredAttempt = yield* submitDnrd5LocalExperimentalState(altered).pipe(
      Effect.either
    )
    expect(Either.isLeft(alteredAttempt)).toBe(true)
    if (Either.isLeft(alteredAttempt)) {
      expect(alteredAttempt.left).toMatchObject({ code: "CONSUMPTION_INVALID" })
    }
    const runtime = yield* CanonicalAtomV2DurableRuntime
    expect((yield* runtime.snapshot).canonical.revision).toBe(1)
  }).pipe(Effect.provide(layer()))
)
