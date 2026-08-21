import { expect, it } from "@effect/vitest"
import { Effect, Either, Exit, Schema } from "effect"
import { readFileSync } from "node:fs"

import {
  canonicalS2SControlJson,
  canonicalS2SControlJsonBytes,
  canonicalS2SControlSha256,
  deriveS2SExternalSeed,
  rawS2SFileSha256
} from "../src/index.js"
import {
  S2SConfirmatoryEventSchema,
  S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
  S2S_CONFIRMATORY_EXPERIMENT_ID,
  S2S_CONFIRMATORY_POLICY,
  S2S_CONFIRMATORY_RESOURCE_POLICY_SHA256,
  S2S_PILOT_ADOPTION_RECEIPT_SHA256,
  S2S_PROTOCOL_CONFIG_DOCUMENT_SHA256,
  S2S_PROTOCOL_CONFIG_RECEIPT_SHA256,
  S2SSha256Schema,
  advanceS2SConfirmatory,
  initialS2SConfirmatoryState,
  type S2SConfirmatoryState
} from "../src/s2s-confirmatory.js"
import {
  S2SConfirmatoryControlPlane,
  S2S_GOLDEN_CONFIRM_REQUEST_DOCUMENT_SHA256,
  S2S_GOLDEN_CONFIRM_REQUEST_SHA256,
  buildPythonNumericConfirmRequest,
  makeOpaqueNumericFile,
  makePythonNumericConfirmInvocation,
  projectOpaqueNumericAdjudication,
  makeS2SConfirmatoryControlPlaneMemoryForTest
} from "../src/s2s-orchestration.js"

const SOURCE_A = "a".repeat(40)
const REGISTRATION_B = "b".repeat(40)
const WORKFLOW_SHA256 = "c".repeat(64)
const PREREGISTRATION_SHA256 = "d".repeat(64)
const CHAIN_HASH =
  "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971"
const RANDOMNESS =
  "fe290beca10872ef2fb164d2aa4442de4566183ec51c56ff3cd603d930e54fdd"
const FUTURE_COMMITMENT =
  "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"
const EXTERNAL_SEED =
  "552e51d2ff75cb7c5df5b55a166aba12a277c2813bbdd69bc825286e7c26b6f0"
const WORKFLOW_RUN_ID = 101
const REGISTER_JOB_ID = 201
const CONFIRM_JOB_ID = 202
const ADJUDICATION_JOB_ID = 203

const decodeEvent = Schema.decodeUnknownSync(S2SConfirmatoryEventSchema, {
  onExcessProperty: "error"
})

const binding = (predecessorControlReceiptSha256: string) => ({
  experimentId: S2S_CONFIRMATORY_EXPERIMENT_ID,
  sourceCommitA: SOURCE_A,
  registrationCommitB: REGISTRATION_B,
  workflowRunId: WORKFLOW_RUN_ID,
  workflowRunAttempt: 1,
  workflowHeadSha: REGISTRATION_B,
  workflowSha256: WORKFLOW_SHA256,
  preregistrationSha256: PREREGISTRATION_SHA256,
  resourcePolicySha256: S2S_CONFIRMATORY_RESOURCE_POLICY_SHA256,
  protocolConfigSha256: S2S_PROTOCOL_CONFIG_RECEIPT_SHA256,
  predecessorControlReceiptSha256
})

const attempt = () => ({
  workflowRunAttempt: 1,
  resume: false,
  checkpointResume: false,
  rerun: false,
  reroll: false,
  cellRetry: false,
  taskRetry: false,
  taskSkip: false,
  partialCandidate: false
})

const artifact = (
  artifactName: string,
  artifactId: number,
  digestCharacter: string,
  archiveSizeBytes = 1_024,
  largestMemberSizeBytes = 512
) => ({
  artifactName,
  artifactId,
  artifactCount: 1,
  archiveSizeBytes,
  largestMemberSizeBytes,
  compressionLevel: 0,
  retentionDays: 90,
  overwrite: false,
  apiDigestSha256: digestCharacter.repeat(64),
  downloadedArchiveSha256: digestCharacter.repeat(64)
})

const beginRegistration = (predecessor: string) => ({
  schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
  _tag: "BeginRegistration",
  binding: binding(predecessor),
  adoptionReceiptSha256: S2S_PILOT_ADOPTION_RECEIPT_SHA256,
  workflowRunId: WORKFLOW_RUN_ID,
  registrationJobId: REGISTER_JOB_ID,
  workflowRunAttempt: 1,
  workflowHeadSha: REGISTRATION_B,
  workflowCreatedAtUnixSeconds: 100,
  registrationJobStartedAtUnixSeconds: 110,
  sourceCommitSha: SOURCE_A,
  preregistrationCommitSha: REGISTRATION_B,
  beaconId: "quicknet",
  beaconChainHashHex: CHAIN_HASH,
  futureBeaconRound: 1_000,
  futureRoundCommitmentSelfHashSha256: FUTURE_COMMITMENT,
  declaredPulseLeadSeconds: 200
})

const verifyRegistration = (predecessor: string) => ({
  schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
  _tag: "VerifyRegistration",
  binding: binding(predecessor),
  workflowRunId: WORKFLOW_RUN_ID,
  registrationJobId: REGISTER_JOB_ID,
  workflowRunAttempt: 1,
  workflowHeadSha: REGISTRATION_B,
  registrationJobCompletedAtUnixSeconds: 210,
  sourceIsAncestorOfPreregistration: true,
  preregistrationIsDirectChildOfSource: true,
  numericContinuityManifestSha256AtSource: "e".repeat(64),
  numericContinuityManifestSha256AtPreregistration: "e".repeat(64),
  numericContinuityPathsByteEqual: true,
  jobElapsedSeconds: 100,
  artifact: artifact("s2s-registration", 301, "1")
})

const beginConfirm = (predecessor: string) => ({
  schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
  _tag: "BeginConfirm",
  binding: binding(predecessor),
  workflowRunId: WORKFLOW_RUN_ID,
  confirmJobId: CONFIRM_JOB_ID,
  workflowRunAttempt: 1,
  workflowHeadSha: REGISTRATION_B,
  confirmJobStartedAtUnixSeconds: 220,
  attempt: attempt()
})

const acceptPulse = (predecessor: string) => ({
  schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
  _tag: "AcceptVerifiedPulse",
  binding: binding(predecessor),
  workflowRunId: WORKFLOW_RUN_ID,
  confirmJobId: CONFIRM_JOB_ID,
  beaconId: "quicknet",
  beaconChainHashHex: CHAIN_HASH,
  beaconRound: 1_000,
  roundTimeUnixSeconds: 300,
  verifiedAtUnixSeconds: 300,
  pulseWaitElapsedSeconds: 80,
  verifiedRandomnessHex: RANDOMNESS,
  externalSeedHex: EXTERNAL_SEED,
  verifierReceiptSha256: "2".repeat(64),
  verificationAccepted: true
})

const beginNumericConfirm = (predecessor: string) => ({
  schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
  _tag: "BeginNumericConfirm",
  binding: binding(predecessor),
  workflowRunId: WORKFLOW_RUN_ID,
  confirmJobId: CONFIRM_JOB_ID
})

const recordCandidate = (predecessor: string) => ({
  schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
  _tag: "RecordCandidateProduced",
  binding: binding(predecessor),
  adoptionReceiptSha256: S2S_PILOT_ADOPTION_RECEIPT_SHA256,
  workflowRunId: WORKFLOW_RUN_ID,
  confirmJobId: CONFIRM_JOB_ID,
  attempt: attempt(),
  externalSeedHex: EXTERNAL_SEED,
  taskCount: 20,
  armOrder: ["T16", "P_CAP18", "DS870"],
  cellCount: 60,
  optimizerExecutionsPerCell: 2,
  optimizerExecutionCount: 120,
  completedFitReplayCellCount: 60,
  testWorldsPerTask: 6_250,
  scoreVariantCount: 8,
  domainWorldCount: 15_625,
  allFitReplayCompletedBeforeAnyTestMaterialization: true,
  postSeedWorkElapsedNanoseconds: 100_000_000_000,
  commandElapsedSeconds: 180,
  jobElapsedSeconds: 200,
  rss: {
    api: "getrusage",
    subject: "RUSAGE_SELF",
    unit: "KiB",
    peakRssKiB: 171_108,
    oomObserved: false
  },
  numericCandidateBytesSha256: "3".repeat(64),
  numericConfirmRequestSha256: "9".repeat(64),
  numericCandidateLabel: "NUMERIC_REPLAY_VALIDATED_CANDIDATE_ONLY",
  candidateOnly: true
})

const verifyCandidateArtifact = (predecessor: string) => ({
  schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
  _tag: "VerifyCandidateArtifact",
  binding: binding(predecessor),
  workflowRunId: WORKFLOW_RUN_ID,
  confirmJobId: CONFIRM_JOB_ID,
  confirmJobCompletedAtUnixSeconds: 420,
  numericCandidateBytesSha256: "3".repeat(64),
  artifact: artifact("s2s-candidate", 302, "4"),
  archiveMembers: ["control_receipt.json", "numeric_candidate.json"],
  readbackContainsCanonicalCandidate: true
})

const beginAdjudication = (predecessor: string) => ({
  schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
  _tag: "BeginAdjudication",
  binding: binding(predecessor),
  workflowRunId: WORKFLOW_RUN_ID,
  adjudicationJobId: ADJUDICATION_JOB_ID,
  workflowRunAttempt: 1,
  workflowHeadSha: REGISTRATION_B,
  adjudicationJobStartedAtUnixSeconds: 430,
  attempt: attempt(),
  candidateArtifactId: 302,
  expectedCandidateArchiveSha256: "4".repeat(64),
  requeriedApiDigestSha256: "4".repeat(64),
  redownloadedCandidateArchiveSha256: "4".repeat(64)
})

const recordAdjudication = (predecessor: string) => ({
  schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
  _tag: "RecordAdjudicationProduced",
  binding: binding(predecessor),
  adoptionReceiptSha256: S2S_PILOT_ADOPTION_RECEIPT_SHA256,
  workflowRunId: WORKFLOW_RUN_ID,
  adjudicationJobId: ADJUDICATION_JOB_ID,
  attempt: attempt(),
  candidateArtifactId: 302,
  externalSeedHex: EXTERNAL_SEED,
  taskCount: 20,
  testWorldsPerTask: 6_250,
  scoreVariantCount: 8,
  domainWorldCount: 15_625,
  optimizerExecutionCount: 0,
  blsVerificationRerun: true,
  taskBatchRerun: true,
  testEvaluationRerun: true,
  integrityReducerRerun: true,
  compactCompetitivePhraseAllowed: false,
  numericCandidateDocumentSha256: "3".repeat(64),
  numericCandidateReceiptSha256: "8".repeat(64),
  numericConfirmRequestSha256: "9".repeat(64),
  numericAdjudicationReceiptSha256: "a".repeat(64),
  numericCandidateOutcome: "CANDIDATE_PASS_AWAITING_BUNDLE",
  commandElapsedSeconds: 600,
  jobElapsedSeconds: 700,
  rss: {
    api: "getrusage",
    subject: "RUSAGE_SELF",
    unit: "KiB",
    peakRssKiB: 160_000,
    oomObserved: false
  },
  numericAdjudicationBytesSha256: "5".repeat(64),
  candidateOnly: true
})

const verifyEvidenceArtifact = (predecessor: string) => ({
  schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
  _tag: "VerifyEvidenceArtifact",
  binding: binding(predecessor),
  workflowRunId: WORKFLOW_RUN_ID,
  adjudicationJobId: ADJUDICATION_JOB_ID,
  adjudicationJobCompletedAtUnixSeconds: 1_130,
  numericAdjudicationBytesSha256: "5".repeat(64),
  artifact: artifact("s2s-adjudication", 303, "6"),
  readbackContainsCanonicalAdjudication: true,
  compactCompetitivePhraseAllowed: false
})

const advance = (
  state: S2SConfirmatoryState,
  input: unknown
): S2SConfirmatoryState => {
  const result = advanceS2SConfirmatory(state, decodeEvent(input))
  if (Either.isLeft(result)) throw result.left
  return result.right
}

const throughConfirmRunning = (): S2SConfirmatoryState => {
  let state: S2SConfirmatoryState = initialS2SConfirmatoryState()
  state = advance(state, beginRegistration(state.latestControlReceiptSha256))
  state = advance(state, verifyRegistration(state.latestControlReceiptSha256))
  state = advance(state, beginConfirm(state.latestControlReceiptSha256))
  state = advance(state, acceptPulse(state.latestControlReceiptSha256))
  return advance(state, beginNumericConfirm(state.latestControlReceiptSha256))
}

const throughCandidateProduced = (): S2SConfirmatoryState => {
  const running = throughConfirmRunning()
  return advance(running, recordCandidate(running.latestControlReceiptSha256))
}

it("freezes the adopted resource policy and disables the DS-derived phrase", () => {
  expect(S2S_CONFIRMATORY_POLICY.adoptionReceiptSha256).toBe(
    S2S_PILOT_ADOPTION_RECEIPT_SHA256
  )
  expect(S2S_CONFIRMATORY_POLICY.claims).toEqual({
    compactCompetitivePhraseAllowed: false,
    compactCompetitivePhraseDisabledReason:
      "DS_SELECTED_CONFIGURATION_NEVER_BEAT_EPOCH_ZERO"
  })
  expect(
    S2S_CONFIRMATORY_POLICY.resourceBasis.projectedPreEvaluationNanoseconds
  ).toBe(
    S2S_CONFIRMATORY_POLICY.resourceBasis
      .projectedTwentyTaskFitReplayNanoseconds +
      S2S_CONFIRMATORY_POLICY.resourceBasis.projectedTaskPreparationNanoseconds
  )
  expect(
    S2S_CONFIRMATORY_POLICY.resourceBasis.postSeedReserveNanoseconds
  ).toBe(
    S2S_CONFIRMATORY_POLICY.resourceBasis.postSeedWorkCapNanoseconds -
      S2S_CONFIRMATORY_POLICY.resourceBasis.projectedPreEvaluationNanoseconds
  )
  expect(
    S2S_CONFIRMATORY_POLICY.deadlines.confirmCommandTimeoutSeconds
  ).toBe(3_900 + 7_200 + 300)
  const receipt = canonicalS2SControlSha256(S2S_CONFIRMATORY_POLICY)
  expect(Either.isRight(receipt)).toBe(true)
  if (Either.isRight(receipt)) {
    expect(receipt.right).toBe(S2S_CONFIRMATORY_RESOURCE_POLICY_SHA256)
  }
})

it("matches the external-seed raw-byte golden vector", () => {
  const result = deriveS2SExternalSeed({
    beaconChainHashHex: CHAIN_HASH,
    round: 1_000,
    verifiedRandomnessHex: RANDOMNESS,
    futureRoundCommitmentSelfHashHex: FUTURE_COMMITMENT
  })
  expect(Either.isRight(result)).toBe(true)
  if (Either.isLeft(result)) return
  expect(result.right.materialByteLength).toBe(139)
  expect(result.right.materialHex).toBe(
    "4853574d2d53574d30572d5332532d45585445524e414c2d534545442d563100" +
      "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971" +
      "0000000000000003e800" +
      "fe290beca10872ef2fb164d2aa4442de4566183ec51c56ff3cd603d930e54fdd" +
      "00" + FUTURE_COMMITMENT
  )
  expect(result.right.externalSeedHex).toBe(EXTERNAL_SEED)
})

it("uses the same float-free canonical JSON surface as the Python boundary", () => {
  const fixture = {
    z: null,
    a: [true, false, 7, "0x1.0000000000000p+0"],
    nested: { beta: "x", alpha: 1 }
  }
  const expected =
    '{"a":[true,false,7,"0x1.0000000000000p+0"],"nested":{"alpha":1,"beta":"x"},"z":null}'
  expect(canonicalS2SControlJson(fixture)).toEqual(Either.right(expected))
  const bytes = canonicalS2SControlJsonBytes(fixture)
  expect(Either.isRight(bytes)).toBe(true)
  if (Either.isRight(bytes)) {
    expect(new TextDecoder().decode(bytes.right)).toBe(`${expected}\n`)
  }
  expect(Either.isLeft(canonicalS2SControlJson({ value: 0.5 }))).toBe(true)
  expect(Either.isLeft(canonicalS2SControlJson({ value: -0 }))).toBe(true)
  expect(Either.isLeft(canonicalS2SControlJson({ value: "한글" }))).toBe(true)

  let accessorInvoked = false
  const accessorArray = [1]
  Object.defineProperty(accessorArray, "0", {
    configurable: true,
    enumerable: true,
    get: () => {
      accessorInvoked = true
      return 1
    }
  })
  expect(Either.isLeft(canonicalS2SControlJson(accessorArray))).toBe(true)
  expect(accessorInvoked).toBe(false)

  const customArray = [1]
  Object.defineProperty(customArray, "extra", {
    configurable: true,
    enumerable: true,
    value: 2
  })
  expect(Either.isLeft(canonicalS2SControlJson(customArray))).toBe(true)
})

it("binds the exact adopted protocol-config document at the Python port", () => {
  const bytes = readFileSync(
    new URL("./fixtures/adopted-protocol-config.json", import.meta.url)
  )
  expect(rawS2SFileSha256(bytes)).toBe(S2S_PROTOCOL_CONFIG_DOCUMENT_SHA256)
  const invocation = makePythonNumericConfirmInvocation(
    S2SSha256Schema.make(EXTERNAL_SEED),
    bytes
  )
  expect(Either.isRight(invocation)).toBe(true)
  if (Either.isLeft(invocation)) return
  expect(invocation.right.workload.drawIndices).toEqual(
    Array.from({ length: 20 }, (_, index) => index)
  )
  expect(invocation.right.workload.adjudicationOptimizerRefitAllowed).toBe(
    false
  )
  expect(invocation.right.protocolConfigReceiptSha256).toBe(
    S2S_PROTOCOL_CONFIG_RECEIPT_SHA256
  )
  const request = buildPythonNumericConfirmRequest(
    S2SSha256Schema.make(EXTERNAL_SEED),
    bytes
  )
  expect(Either.isRight(request)).toBe(true)
  if (Either.isRight(request)) {
    expect(request.right.requestSha256).toBe(
      S2S_GOLDEN_CONFIRM_REQUEST_SHA256
    )
    expect(request.right.rawBytesSha256).toBe(
      S2S_GOLDEN_CONFIRM_REQUEST_DOCUMENT_SHA256
    )
    expect(request.right.canonicalUtf8WithLf.byteLength).toBe(2_861)
  }

  const drifted = Uint8Array.from(bytes)
  drifted[0] = 0x20
  expect(
    Either.isLeft(
      makePythonNumericConfirmInvocation(
        S2SSha256Schema.make(EXTERNAL_SEED),
        drifted
      )
    )
  ).toBe(true)
})

it("derives the final verdict from a hash-bound Python replay projection", () => {
  const replay = {
    candidate_reducer_canonical_equal: true,
    candidate_reducer_receipt_sha256: "b".repeat(64),
    compact_competitive_phrase_allowed: false,
    compact_competitive_phrase_policy:
      "DS_SELECTED_CONFIGURATION_NEVER_BEAT_EPOCH_ZERO",
    numeric_candidate_outcome: "CANDIDATE_PASS_AWAITING_BUNDLE",
    numeric_candidate_reason_codes: ["ESSENTIAL_Q_B_R_PASS"],
    optimizer_refit_performed: false,
    protocol_config_receipt_sha256: S2S_PROTOCOL_CONFIG_RECEIPT_SHA256,
    task_batch_sha256: "c".repeat(64),
    task_evaluation_receipt_sha256s: Array.from(
      { length: 20 },
      () => "d".repeat(64)
    ),
    test_and_integrity_recomputed_count: 20
  }
  const unsigned = {
    candidate_document_sha256: "3".repeat(64),
    candidate_receipt_sha256: "8".repeat(64),
    canonical_encoding: "ASCII_CANONICAL_UTF8_JSON_PLUS_SINGLE_LF",
    claim_boundary: "NUMERIC_ONLY_NO_EVIDENCE_VERDICT_OR_CHRONOLOGY_CLAIM",
    confirm_request_sha256: "9".repeat(64),
    numeric_replay: replay,
    schema_version: "hswm-swm0w-s2s-numeric-adjudication/v1",
    scientific_status: "NUMERIC_CANDIDATE_ONLY_UNJUDGED",
    status: "NUMERIC_REPLAY_VALIDATED_CANDIDATE_ONLY"
  }
  const receipt = canonicalS2SControlSha256(unsigned)
  expect(Either.isRight(receipt)).toBe(true)
  if (Either.isLeft(receipt)) return
  const bytes = canonicalS2SControlJsonBytes({
    ...unsigned,
    receipt_sha256: receipt.right
  })
  expect(Either.isRight(bytes)).toBe(true)
  if (Either.isLeft(bytes)) return
  const opaque = makeOpaqueNumericFile(
    "numeric_adjudication.json",
    "hswm-swm0w-s2s-numeric-adjudication/v1",
    bytes.right,
    S2SSha256Schema.make(rawS2SFileSha256(bytes.right))
  )
  expect(Either.isRight(opaque)).toBe(true)
  if (Either.isLeft(opaque)) return
  const projection = projectOpaqueNumericAdjudication(
    opaque.right,
    S2SSha256Schema.make("3".repeat(64)),
    S2SSha256Schema.make("9".repeat(64))
  )
  expect(Either.isRight(projection)).toBe(true)
  if (Either.isRight(projection)) {
    expect(projection.right.numericCandidateOutcome).toBe(
      "CANDIDATE_PASS_AWAITING_BUNDLE"
    )
  }

  const wrongCandidate = projectOpaqueNumericAdjudication(
    opaque.right,
    S2SSha256Schema.make("e".repeat(64)),
    S2SSha256Schema.make("9".repeat(64))
  )
  expect(Either.isLeft(wrongCandidate)).toBe(true)

  const emptyReasonUnsigned = {
    ...unsigned,
    numeric_replay: {
      ...replay,
      numeric_candidate_reason_codes: [""]
    }
  }
  const emptyReasonReceipt = canonicalS2SControlSha256(emptyReasonUnsigned)
  expect(Either.isRight(emptyReasonReceipt)).toBe(true)
  if (Either.isLeft(emptyReasonReceipt)) return
  const emptyReasonBytes = canonicalS2SControlJsonBytes({
    ...emptyReasonUnsigned,
    receipt_sha256: emptyReasonReceipt.right
  })
  expect(Either.isRight(emptyReasonBytes)).toBe(true)
  if (Either.isLeft(emptyReasonBytes)) return
  const emptyReasonOpaque = makeOpaqueNumericFile(
    "numeric_adjudication.json",
    "hswm-swm0w-s2s-numeric-adjudication/v1",
    emptyReasonBytes.right,
    S2SSha256Schema.make(rawS2SFileSha256(emptyReasonBytes.right))
  )
  expect(Either.isRight(emptyReasonOpaque)).toBe(true)
  if (Either.isRight(emptyReasonOpaque)) {
    expect(
      Either.isLeft(
        projectOpaqueNumericAdjudication(
          emptyReasonOpaque.right,
          S2SSha256Schema.make("3".repeat(64)),
          S2SSha256Schema.make("9".repeat(64))
        )
      )
    ).toBe(true)
  }

  const tamperedBytes = canonicalS2SControlJsonBytes({
    ...unsigned,
    numeric_replay: {
      ...replay,
      numeric_candidate_outcome: "CANDIDATE_KILL_AWAITING_BUNDLE"
    },
    receipt_sha256: receipt.right
  })
  expect(Either.isRight(tamperedBytes)).toBe(true)
  if (Either.isLeft(tamperedBytes)) return
  const tamperedOpaque = makeOpaqueNumericFile(
    "numeric_adjudication.json",
    "hswm-swm0w-s2s-numeric-adjudication/v1",
    tamperedBytes.right,
    S2SSha256Schema.make(rawS2SFileSha256(tamperedBytes.right))
  )
  expect(Either.isRight(tamperedOpaque)).toBe(true)
  if (Either.isRight(tamperedOpaque)) {
    expect(
      Either.isLeft(
        projectOpaqueNumericAdjudication(
          tamperedOpaque.right,
          S2SSha256Schema.make("3".repeat(64)),
          S2SSha256Schema.make("9".repeat(64))
        )
      )
    ).toBe(true)
  }
})

it("strictly decodes events and rejects excess fields and enabled compact claims", () => {
  const initial = initialS2SConfirmatoryState()
  expect(() =>
    decodeEvent({
      ...beginRegistration(initial.latestControlReceiptSha256),
      unexpected: true
    })
  ).toThrow()

  let state = throughCandidateProduced()
  state = advance(
    state,
    verifyCandidateArtifact(state.latestControlReceiptSha256)
  )
  state = advance(state, beginAdjudication(state.latestControlReceiptSha256))
  expect(() =>
    decodeEvent({
      ...recordAdjudication(state.latestControlReceiptSha256),
      compactCompetitivePhraseAllowed: true
    })
  ).toThrow()
})

it("advances monotonically and exposes a verdict only after final readback", () => {
  let state = throughConfirmRunning()
  expect(state._tag).toBe("ConfirmRunning")
  if (state._tag !== "ConfirmRunning") return
  expect(state.numericPlan.optimizerExecutionCount).toBe(120)
  expect("rerunBlsVerification" in state.numericPlan).toBe(false)

  state = advance(state, recordCandidate(state.latestControlReceiptSha256))
  expect(state._tag).toBe("CandidateProduced")
  expect("verdict" in state).toBe(false)

  state = advance(
    state,
    verifyCandidateArtifact(state.latestControlReceiptSha256)
  )
  expect(state._tag).toBe("CandidateArtifactVerified")
  state = advance(state, beginAdjudication(state.latestControlReceiptSha256))
  expect(state._tag).toBe("Adjudicating")
  if (state._tag !== "Adjudicating") return
  expect(state.numericPlan.optimizerExecutionCount).toBe(0)
  expect("rerunBlsVerification" in state.numericPlan).toBe(false)

  state = advance(state, recordAdjudication(state.latestControlReceiptSha256))
  expect(state._tag).toBe("AdjudicationProduced")
  expect("verdict" in state).toBe(false)
  state = advance(
    state,
    verifyEvidenceArtifact(state.latestControlReceiptSha256)
  )
  expect(state._tag).toBe("EvidenceArtifactVerified")
  if (state._tag !== "EvidenceArtifactVerified") return
  expect(state.verdict).toBe("PASS")
  expect(state.compactCompetitivePhraseAllowed).toBe(false)
  expect(state.registration.workflowRunId).toBe(state.confirm.workflowRunId)
  expect(state.confirm.workflowRunId).toBe(state.adjudication.workflowRunId)
  expect(state.candidate.numericCandidateBytesSha256).not.toBe(
    state.candidateArtifact.artifact.downloadedArchiveSha256
  )
})

it("fails closed on predecessor, workload, and artifact-readback drift", () => {
  const initial = initialS2SConfirmatoryState()
  const wrongPredecessor = decodeEvent(beginRegistration("f".repeat(64)))
  const chainResult = advanceS2SConfirmatory(initial, wrongPredecessor)
  expect(Either.isLeft(chainResult)).toBe(true)
  if (Either.isLeft(chainResult)) {
    expect(chainResult.left._tag).toBe("S2SOperationalPolicyViolation")
  }

  const running = throughConfirmRunning()
  const invalidCandidate = decodeEvent({
    ...recordCandidate(running.latestControlReceiptSha256),
    completedFitReplayCellCount: 59
  })
  const workloadResult = advanceS2SConfirmatory(running, invalidCandidate)
  expect(Either.isLeft(workloadResult)).toBe(true)

  const produced = throughCandidateProduced()
  const driftedArtifact = verifyCandidateArtifact(
    produced.latestControlReceiptSha256
  )
  const readbackResult = advanceS2SConfirmatory(
    produced,
    decodeEvent({
      ...driftedArtifact,
      artifact: {
        ...driftedArtifact.artifact,
        downloadedArchiveSha256: "9".repeat(64)
      }
    })
  )
  expect(Either.isLeft(readbackResult)).toBe(true)
})

it("maps a run-bound failure to terminal VOID with no retry path", () => {
  const running = throughConfirmRunning()
  const voided = advance(
    running,
    {
      schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
      _tag: "RecordOperationalVoid",
      binding: binding(running.latestControlReceiptSha256),
      workflowRunId: WORKFLOW_RUN_ID,
      workflowJobId: CONFIRM_JOB_ID,
      workflowRunAttempt: 1,
      reason: "CONFIRM_JOB_DID_NOT_COMPLETE_SUCCESSFULLY",
      evidenceSha256: "7".repeat(64)
    }
  )
  expect(voided._tag).toBe("Voided")
  if (voided._tag !== "Voided") return
  expect(voided.retryAllowed).toBe(false)
  expect(voided.candidateConsumable).toBe(false)

  const retry = advanceS2SConfirmatory(
    voided,
    decodeEvent(recordCandidate(voided.latestControlReceiptSha256))
  )
  expect(Either.isLeft(retry)).toBe(true)
})

it("keeps opaque Python bytes distinct and rejects transport drift", () => {
  const bytes = new TextEncoder().encode('{"schema_version":"x"}\n')
  const rawSha = S2SSha256Schema.make(rawS2SFileSha256(bytes))
  const accepted = makeOpaqueNumericFile(
    "numeric_candidate.json",
    "hswm-swm0w-s2s-numeric-candidate/v1",
    bytes,
    rawSha
  )
  expect(Either.isRight(accepted)).toBe(true)
  const rejected = makeOpaqueNumericFile(
    "numeric_candidate.json",
    "hswm-swm0w-s2s-numeric-candidate/v1",
    bytes,
    S2SSha256Schema.make("f".repeat(64))
  )
  expect(Either.isLeft(rejected)).toBe(true)
})

it.effect("atomically serializes state and journal in the memory simulation", () => {
  const program = Effect.gen(function* () {
    const control = yield* S2SConfirmatoryControlPlane
    const initial = yield* control.snapshot
    const first = beginRegistration(initial.latestControlReceiptSha256)
    const second = {
      ...beginRegistration(initial.latestControlReceiptSha256),
      registrationJobId: REGISTER_JOB_ID + 100
    }
    const outcomes = yield* Effect.all(
      [
        control.submit(first).pipe(Effect.either),
        control.submit(second).pipe(Effect.either)
      ],
      { concurrency: 2 }
    )
    const state = yield* control.snapshot
    const history = yield* control.history
    expect(outcomes.filter(Either.isRight)).toHaveLength(1)
    expect(outcomes.filter(Either.isLeft)).toHaveLength(1)
    expect(state._tag).toBe("Registering")
    expect(history).toHaveLength(1)
    expect(history[0]?.previousPhase).toBe("Prepared")
    expect(history[0]?.nextPhase).toBe("Registering")
  })
  return program.pipe(
    Effect.provide(makeS2SConfirmatoryControlPlaneMemoryForTest())
  )
})

it.effect("rejects an invalid boundary object without mutating simulation state", () => {
  const program = Effect.gen(function* () {
    const control = yield* S2SConfirmatoryControlPlane
    const result = yield* Effect.exit(
      control.submit({ schemaVersion: "wrong", _tag: "BeginRegistration" })
    )
    expect(Exit.isFailure(result)).toBe(true)
    expect((yield* control.snapshot)._tag).toBe("Prepared")
    expect(yield* control.history).toEqual([])
  })
  return program.pipe(
    Effect.provide(makeS2SConfirmatoryControlPlaneMemoryForTest())
  )
})
