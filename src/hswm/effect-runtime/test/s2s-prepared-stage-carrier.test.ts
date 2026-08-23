import { expect, it } from "@effect/vitest"
import { Either, Schema } from "effect"

import * as PublicApi from "../src/index.js"
import {
  canonicalS2SControlJsonBytes,
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "../src/s2s-canonical.js"
import {
  S2SConfirmatoryEventSchema,
  S2SArtifactEvidenceSchema,
  S2S_CANDIDATE_ARTIFACT_NAME,
  S2S_DRAND_STABLE_PROJECTION_SCHEMA_VERSION,
  S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
  S2S_CONFIRMATORY_EXPERIMENT_ID,
  S2S_CONFIRMATORY_RESOURCE_POLICY_SHA256,
  S2S_GITHUB_ARTIFACT_DOWNLOAD_RECEIPT_SCHEMA_VERSION,
  S2S_GITHUB_OBSERVATION_RECEIPT_SCHEMA_VERSION,
  S2S_NUMERIC_ORACLE_SOURCE_SHA256,
  S2S_PILOT_ADOPTION_RECEIPT_SHA256,
  S2S_PYTHON_EXECUTION_EVIDENCE_SCHEMA_VERSION,
  S2S_REGISTRATION_ARTIFACT_NAME,
  S2S_PROTOCOL_CONFIG_RECEIPT_SHA256,
  S2SSha256Schema,
  advanceS2SConfirmatory,
  initialS2SConfirmatoryState,
  type S2SArtifactEvidence,
  type S2SConfirmatoryEvent,
  type S2SConfirmatoryState
} from "../src/s2s-confirmatory.js"
import {
  prepareS2SCandidateCarrier,
  prepareS2SRegistrationCarrier,
  type S2SCarrierReadback,
  type S2SUploadMember
} from "../src/s2s-job-sequence.js"
import {
  inspectS2SPreparedStageCarrierCapability,
  inspectS2SPreparedStageCarrierTestCapability,
  makeS2SPreparedStageCarrierTestCapability,
  prepareS2SCurrentStageCarrier,
  type S2SPreparedStageCarrierTestSeed
} from "../src/s2s-prepared-stage-carrier.js"
import { inspectS2SStageArtifactReadReplaySnapshot } from "../src/s2s-stage-artifact-read-replay.js"
import { S2S_CONFIRMATORY_WORKFLOW_PATH } from "../src/s2s-workflow-contract.js"
import { buildS2STestActionZip } from "./support/s2s-action-zip.js"

const SOURCE_A = "a".repeat(40)
const REGISTRATION_B = "b".repeat(40)
const WORKFLOW_SHA256 = "c".repeat(64)
const PREREGISTRATION_SHA256 = "d".repeat(64)
const CHAIN_HASH =
  "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971"
const WORKFLOW_RUN_ID = 101
const REGISTER_JOB_ID = 201
const CONFIRM_JOB_ID = 202
const ADJUDICATION_JOB_ID = 203
const WORKFLOW_CREATED_AT_UNIX_SECONDS = 1_692_806_164
const REGISTRATION_STARTED_AT_UNIX_SECONDS = 1_692_806_174
const FUTURE_BEACON_ROUND = 1_000
const FUTURE_ROUND_TIME_UNIX_SECONDS = 1_692_806_364
const REGISTRATION_COMPLETED_AT_UNIX_SECONDS = 1_692_806_274
const CONFIRM_STARTED_AT_UNIX_SECONDS = 1_692_806_284
const CONFIRM_COMPLETED_AT_UNIX_SECONDS = 1_692_806_484
const ADJUDICATION_STARTED_AT_UNIX_SECONDS = 1_692_806_494
const RANDOMNESS =
  "fe290beca10872ef2fb164d2aa4442de4566183ec51c56ff3cd603d930e54fdd"
const SIGNATURE =
  "b44679b9a59af2ec876b1a6b1ad52ea9b1615fc3982b19576350f93447cb1125e342b73a8dd2bacbe47e4b6b63ed5e39"
const EXTERNAL_SEED =
  "552e51d2ff75cb7c5df5b55a166aba12a277c2813bbdd69bc825286e7c26b6f0"
const NUMERIC_CONFIRM_REQUEST_SHA256 = "9".repeat(64)
const NUMERIC_CANDIDATE_RECEIPT_SHA256 = "8".repeat(64)
const encoder = new TextEncoder()

const evidenceHash = (label: string): string =>
  rawS2SFileSha256(encoder.encode(label))

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
  githubObservationSchemaVersion:
    S2S_GITHUB_OBSERVATION_RECEIPT_SCHEMA_VERSION,
  githubArtifactDownloadSchemaVersion:
    S2S_GITHUB_ARTIFACT_DOWNLOAD_RECEIPT_SCHEMA_VERSION,
  predecessorControlReceiptSha256
})

const registrationEvent = (suffix: string) => {
  const state = initialS2SConfirmatoryState()
  const event = decodeEvent({
    schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
    _tag: "BeginRegistration",
    binding: binding(state.latestControlReceiptSha256),
    adoptionReceiptSha256: S2S_PILOT_ADOPTION_RECEIPT_SHA256,
    workflowRunId: WORKFLOW_RUN_ID,
    registrationJobId: REGISTER_JOB_ID,
    workflowRunAttempt: 1,
    workflowHeadSha: REGISTRATION_B,
    workflowCreatedAtUnixSeconds: WORKFLOW_CREATED_AT_UNIX_SECONDS,
    registrationJobStartedAtUnixSeconds:
      REGISTRATION_STARTED_AT_UNIX_SECONDS,
    workflowRunObservationReceiptSha256: evidenceHash(`run-${suffix}`),
    workflowJobsObservationReceiptSha256: evidenceHash(`jobs-${suffix}`),
    workflowRunStatus: "in_progress",
    registrationJobStatus: "in_progress",
    sourceCommitSha: SOURCE_A,
    preregistrationCommitSha: REGISTRATION_B,
    beaconId: "quicknet",
    beaconChainHashHex: CHAIN_HASH,
    futureBeaconRound: 1_000,
    futureRoundCommitmentSelfHashSha256:
      "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f",
    declaredPulseLeadSeconds: 200
  })
  if (event._tag !== "BeginRegistration") throw new Error("wrong event")
  return event
}

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

const advance = (
  state: S2SConfirmatoryState,
  event: S2SConfirmatoryEvent
): S2SConfirmatoryState => requireRight(advanceS2SConfirmatory(state, event))

const pythonExecution = (input: {
  readonly operation: "confirm" | "adjudicate"
  readonly inputRawBytesSha256: string
  readonly outputRawBytesSha256: string
  readonly requestDocumentSha256: string
  readonly requestSelfSha256: string
  readonly elapsedNanoseconds: number
}) => {
  const unsigned = {
    schemaVersion: S2S_PYTHON_EXECUTION_EVIDENCE_SCHEMA_VERSION,
    ...input,
    numericOracleSourceSha256: S2S_NUMERIC_ORACLE_SOURCE_SHA256,
    pythonRuntimeIdentitySha256: evidenceHash("python-runtime-identity"),
    invocationIdentitySha256: evidenceHash(`invocation-${input.operation}`),
    exitCode: 0
  }
  return {
    ...unsigned,
    receiptSha256: requireRight(canonicalS2SControlSha256(unsigned))
  }
}

const verifyRegistration = (
  predecessor: string,
  artifact: S2SArtifactEvidence
) => {
  const event = decodeEvent({
    schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
    _tag: "VerifyRegistration",
    binding: binding(predecessor),
    workflowRunId: WORKFLOW_RUN_ID,
    registrationJobId: REGISTER_JOB_ID,
    workflowRunAttempt: 1,
    workflowHeadSha: REGISTRATION_B,
    registrationJobCompletedAtUnixSeconds:
      REGISTRATION_COMPLETED_AT_UNIX_SECONDS,
    workflowRunObservationReceiptSha256: evidenceHash("run-register-complete"),
    workflowJobsObservationReceiptSha256: evidenceHash("jobs-register-complete"),
    workflowRunStatus: "in_progress",
    registrationJobStatus: "completed",
    registrationJobConclusion: "success",
    registrationArtifactApiObservationReceiptSha256: evidenceHash(
      "artifact-registration-api"
    ),
    registrationArtifactDownloadObservationReceiptSha256: evidenceHash(
      "artifact-registration-download"
    ),
    sourceIsAncestorOfPreregistration: true,
    preregistrationIsDirectChildOfSource: true,
    numericContinuityManifestSha256AtSource: "e".repeat(64),
    numericContinuityManifestSha256AtPreregistration: "e".repeat(64),
    numericContinuityPathsByteEqual: true,
    jobElapsedSeconds: 100,
    artifact,
    archiveMembers: ["control_receipt.json"]
  })
  if (event._tag !== "VerifyRegistration") throw new Error("wrong event")
  return event
}

const beginConfirm = (predecessor: string) => {
  const event = decodeEvent({
    schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
    _tag: "BeginConfirm",
    binding: binding(predecessor),
    workflowRunId: WORKFLOW_RUN_ID,
    confirmJobId: CONFIRM_JOB_ID,
    workflowRunAttempt: 1,
    workflowHeadSha: REGISTRATION_B,
    confirmJobStartedAtUnixSeconds: CONFIRM_STARTED_AT_UNIX_SECONDS,
    workflowRunObservationReceiptSha256: evidenceHash("run-confirm-start"),
    workflowJobsObservationReceiptSha256: evidenceHash("jobs-confirm-start"),
    workflowRunStatus: "in_progress",
    confirmJobStatus: "in_progress",
    attempt: attempt()
  })
  if (event._tag !== "BeginConfirm") throw new Error("wrong event")
  return event
}

const acceptPulse = (predecessor: string) => {
  const event = decodeEvent({
    schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
    _tag: "AcceptVerifiedPulse",
    binding: binding(predecessor),
    workflowRunId: WORKFLOW_RUN_ID,
    confirmJobId: CONFIRM_JOB_ID,
    beaconId: "quicknet",
    beaconChainHashHex: CHAIN_HASH,
    beaconRound: FUTURE_BEACON_ROUND,
    roundTimeUnixSeconds: FUTURE_ROUND_TIME_UNIX_SECONDS,
    pulseWaitStartedAtUnixSeconds: CONFIRM_STARTED_AT_UNIX_SECONDS,
    verifiedAtUnixSeconds: FUTURE_ROUND_TIME_UNIX_SECONDS,
    pulseWaitElapsedSeconds: 80,
    verifiedSignatureHex: SIGNATURE,
    verifiedRandomnessHex: RANDOMNESS,
    externalSeedHex: EXTERNAL_SEED,
    verifierReceiptSha256: "2".repeat(64),
    verifierStableProjectionSchemaVersion:
      S2S_DRAND_STABLE_PROJECTION_SCHEMA_VERSION,
    verifierStableProjectionSha256: evidenceHash("drand-stable-projection"),
    verificationAccepted: true
  })
  if (event._tag !== "AcceptVerifiedPulse") throw new Error("wrong event")
  return event
}

const beginNumericConfirm = (predecessor: string) => {
  const event = decodeEvent({
    schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
    _tag: "BeginNumericConfirm",
    binding: binding(predecessor),
    workflowRunId: WORKFLOW_RUN_ID,
    confirmJobId: CONFIRM_JOB_ID
  })
  if (event._tag !== "BeginNumericConfirm") throw new Error("wrong event")
  return event
}

const recordCandidate = (predecessor: string, candidateSha256: string) => {
  const requestDocumentSha256 = evidenceHash("numeric-confirm-request-raw")
  const event = decodeEvent({
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
    rss: {
      api: "getrusage",
      subject: "RUSAGE_SELF",
      unit: "KiB",
      peakRssKiB: 170_000,
      oomObserved: false
    },
    numericCandidateBytesSha256: candidateSha256,
    numericConfirmRequestSha256: NUMERIC_CONFIRM_REQUEST_SHA256,
    numericConfirmRequestDocumentSha256: requestDocumentSha256,
    pythonExecution: pythonExecution({
      operation: "confirm",
      inputRawBytesSha256: requestDocumentSha256,
      outputRawBytesSha256: candidateSha256,
      requestDocumentSha256,
      requestSelfSha256: NUMERIC_CONFIRM_REQUEST_SHA256,
      elapsedNanoseconds: 90_000_000_000
    }),
    numericCandidateLabel: "NUMERIC_REPLAY_VALIDATED_CANDIDATE_ONLY",
    candidateOnly: true
  })
  if (event._tag !== "RecordCandidateProduced") throw new Error("wrong event")
  return event
}

const verifyCandidate = (
  predecessor: string,
  artifact: S2SArtifactEvidence,
  candidateSha256: string
) => {
  const event = decodeEvent({
    schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
    _tag: "VerifyCandidateArtifact",
    binding: binding(predecessor),
    workflowRunId: WORKFLOW_RUN_ID,
    confirmJobId: CONFIRM_JOB_ID,
    confirmJobCompletedAtUnixSeconds: CONFIRM_COMPLETED_AT_UNIX_SECONDS,
    jobElapsedSeconds: 200,
    workflowRunObservationReceiptSha256: evidenceHash("run-confirm-complete"),
    workflowJobsObservationReceiptSha256: evidenceHash("jobs-confirm-complete"),
    workflowRunStatus: "in_progress",
    confirmJobStatus: "completed",
    confirmJobConclusion: "success",
    candidateArtifactFirstApiObservationReceiptSha256: evidenceHash(
      "artifact-candidate-first-api"
    ),
    candidateArtifactFirstDownloadObservationReceiptSha256: evidenceHash(
      "artifact-candidate-first-download"
    ),
    numericCandidateBytesSha256: candidateSha256,
    artifact,
    archiveMembers: ["control_receipt.json", "numeric_candidate.json"],
    readbackContainsCanonicalCandidate: true
  })
  if (event._tag !== "VerifyCandidateArtifact") throw new Error("wrong event")
  return event
}

const beginAdjudication = (
  predecessor: string,
  candidateArtifact: S2SArtifactEvidence
) => {
  const event = decodeEvent({
    schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
    _tag: "BeginAdjudication",
    binding: binding(predecessor),
    workflowRunId: WORKFLOW_RUN_ID,
    adjudicationJobId: ADJUDICATION_JOB_ID,
    workflowRunAttempt: 1,
    workflowHeadSha: REGISTRATION_B,
    adjudicationJobStartedAtUnixSeconds: ADJUDICATION_STARTED_AT_UNIX_SECONDS,
    workflowRunObservationReceiptSha256: evidenceHash("run-adjudication-start"),
    workflowJobsObservationReceiptSha256: evidenceHash("jobs-adjudication-start"),
    workflowRunStatus: "in_progress",
    adjudicationJobStatus: "in_progress",
    attempt: attempt(),
    candidateArtifactId: candidateArtifact.artifactId,
    expectedCandidateArchiveSha256: candidateArtifact.downloadedArchiveSha256,
    requeriedApiDigestSha256: candidateArtifact.apiDigestSha256,
    redownloadedCandidateArchiveSha256:
      candidateArtifact.downloadedArchiveSha256,
    candidateArtifactRequeryObservationReceiptSha256: evidenceHash(
      "artifact-candidate-requery-api"
    ),
    candidateArtifactRedownloadObservationReceiptSha256: evidenceHash(
      "artifact-candidate-redownload"
    )
  })
  if (event._tag !== "BeginAdjudication") throw new Error("wrong event")
  return event
}

const makeNumericAdjudication = (candidateSha256: string) => {
  const unsigned = {
    candidate_document_sha256: candidateSha256,
    candidate_receipt_sha256: NUMERIC_CANDIDATE_RECEIPT_SHA256,
    canonical_encoding: "ASCII_CANONICAL_UTF8_JSON_PLUS_SINGLE_LF",
    claim_boundary: "NUMERIC_ONLY_NO_EVIDENCE_VERDICT_OR_CHRONOLOGY_CLAIM",
    confirm_request_sha256: NUMERIC_CONFIRM_REQUEST_SHA256,
    numeric_replay: {
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
    },
    schema_version: "hswm-swm0w-s2s-numeric-adjudication/v1",
    scientific_status: "NUMERIC_CANDIDATE_ONLY_UNJUDGED",
    status: "NUMERIC_REPLAY_VALIDATED_CANDIDATE_ONLY"
  }
  const receiptSha256 = requireRight(canonicalS2SControlSha256(unsigned))
  const bytes = requireRight(
    canonicalS2SControlJsonBytes({ ...unsigned, receipt_sha256: receiptSha256 })
  )
  return Object.freeze({ bytes, receiptSha256 })
}

const recordAdjudication = (
  predecessor: string,
  candidateArtifact: S2SArtifactEvidence,
  candidateSha256: string,
  adjudicationBytes: Uint8Array,
  adjudicationReceiptSha256: string
) => {
  const event = decodeEvent({
    schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
    _tag: "RecordAdjudicationProduced",
    binding: binding(predecessor),
    adoptionReceiptSha256: S2S_PILOT_ADOPTION_RECEIPT_SHA256,
    workflowRunId: WORKFLOW_RUN_ID,
    adjudicationJobId: ADJUDICATION_JOB_ID,
    attempt: attempt(),
    candidateArtifactId: candidateArtifact.artifactId,
    externalSeedHex: EXTERNAL_SEED,
    taskCount: 20,
    testWorldsPerTask: 6_250,
    scoreVariantCount: 8,
    domainWorldCount: 15_625,
    optimizerExecutionCount: 0,
    blsVerificationRerun: true,
    drandReplayReceiptSha256: evidenceHash("drand-independent-replay"),
    drandReplayFixtureSha256: evidenceHash("drand-replay-fixture"),
    drandReplayStableProjectionSchemaVersion:
      S2S_DRAND_STABLE_PROJECTION_SCHEMA_VERSION,
    drandReplayStableProjectionSha256: evidenceHash("drand-stable-projection"),
    taskBatchRerun: true,
    testEvaluationRerun: true,
    integrityReducerRerun: true,
    compactCompetitivePhraseAllowed: false,
    numericCandidateDocumentSha256: candidateSha256,
    numericCandidateReceiptSha256: NUMERIC_CANDIDATE_RECEIPT_SHA256,
    numericConfirmRequestSha256: NUMERIC_CONFIRM_REQUEST_SHA256,
    numericAdjudicationReceiptSha256: adjudicationReceiptSha256,
    numericCandidateOutcome: "CANDIDATE_PASS_AWAITING_BUNDLE",
    commandElapsedSeconds: 600,
    rss: {
      api: "getrusage",
      subject: "RUSAGE_SELF",
      unit: "KiB",
      peakRssKiB: 160_000,
      oomObserved: false
    },
    numericAdjudicationBytesSha256: rawS2SFileSha256(adjudicationBytes),
    pythonExecution: pythonExecution({
      operation: "adjudicate",
      inputRawBytesSha256: candidateSha256,
      outputRawBytesSha256: rawS2SFileSha256(adjudicationBytes),
      requestDocumentSha256: candidateSha256,
      requestSelfSha256: NUMERIC_CANDIDATE_RECEIPT_SHA256,
      elapsedNanoseconds: 590_000_000_000
    }),
    candidateOnly: true
  })
  if (event._tag !== "RecordAdjudicationProduced") {
    throw new Error("wrong event")
  }
  return event
}

const zipMembers = (
  members: ReadonlyArray<S2SUploadMember<string>>
): ReadonlyArray<{ readonly name: string; readonly bytes: Uint8Array }> =>
  members.map((member) => ({ name: member.name, bytes: member.readBytes() }))

const artifactFromArchive = (
  artifactName:
    | typeof S2S_REGISTRATION_ARTIFACT_NAME
    | typeof S2S_CANDIDATE_ARTIFACT_NAME,
  artifactId: number,
  archiveBytes: Uint8Array,
  members: ReadonlyArray<{ readonly byteLength: number }>
): S2SArtifactEvidence => {
  const digest = S2SSha256Schema.make(rawS2SFileSha256(archiveBytes))
  return Schema.decodeUnknownSync(S2SArtifactEvidenceSchema, {
    onExcessProperty: "error"
  })({
    artifactName,
    artifactId,
    artifactCount: 1,
    archiveSizeBytes: archiveBytes.byteLength,
    largestMemberSizeBytes: Math.max(
      ...members.map((member) => member.byteLength)
    ),
    compressionLevel: 0,
    retentionDays: 90,
    overwrite: false,
    apiDigestSha256: digest,
    downloadedArchiveSha256: digest
  })
}

const makeThreeStageScenario = () => {
  let state = initialS2SConfirmatoryState()
  const registerEvent = registrationEvent("three-stage")
  const registration = requireRight(
    prepareS2SRegistrationCarrier([registerEvent])
  )
  state = registration.carrier.state
  const registrationArchive = buildS2STestActionZip(
    zipMembers(registration.members)
  )
  const registrationArtifact = artifactFromArchive(
    S2S_REGISTRATION_ARTIFACT_NAME,
    1,
    registrationArchive,
    registration.members
  )
  const registrationReadback: S2SCarrierReadback = {
    artifact: registrationArtifact,
    archiveBytes: registrationArchive
  }

  const numericCandidateBytes = encoder.encode('{"candidate":true}\n')
  const candidateSha256 = rawS2SFileSha256(numericCandidateBytes)
  const registrationVerified = verifyRegistration(
    state.latestControlReceiptSha256,
    registrationArtifact
  )
  state = advance(state, registrationVerified)
  const confirmBegan = beginConfirm(state.latestControlReceiptSha256)
  state = advance(state, confirmBegan)
  const pulse = acceptPulse(state.latestControlReceiptSha256)
  state = advance(state, pulse)
  const numericBegan = beginNumericConfirm(state.latestControlReceiptSha256)
  state = advance(state, numericBegan)
  const candidateProduced = recordCandidate(
    state.latestControlReceiptSha256,
    candidateSha256
  )
  const candidateEvents = [
    registrationVerified,
    confirmBegan,
    pulse,
    numericBegan,
    candidateProduced
  ] as const
  const candidate = requireRight(
    prepareS2SCandidateCarrier({
      registrationReadback,
      numericCandidateBytes,
      events: candidateEvents
    })
  )
  state = candidate.carrier.state
  const candidateArchive = buildS2STestActionZip(zipMembers(candidate.members))
  const candidateArtifact = artifactFromArchive(
    S2S_CANDIDATE_ARTIFACT_NAME,
    2,
    candidateArchive,
    candidate.members
  )
  const candidateReadback: S2SCarrierReadback = {
    artifact: candidateArtifact,
    archiveBytes: candidateArchive
  }

  const candidateVerified = verifyCandidate(
    state.latestControlReceiptSha256,
    candidateArtifact,
    candidateSha256
  )
  state = advance(state, candidateVerified)
  const adjudicationBegan = beginAdjudication(
    state.latestControlReceiptSha256,
    candidateArtifact
  )
  state = advance(state, adjudicationBegan)
  const numericAdjudication = makeNumericAdjudication(candidateSha256)
  const adjudicationProduced = recordAdjudication(
    state.latestControlReceiptSha256,
    candidateArtifact,
    candidateSha256,
    numericAdjudication.bytes,
    numericAdjudication.receiptSha256
  )
  return {
    registrationReadback,
    numericCandidateBytes,
    candidateEvents,
    candidateReadback,
    numericAdjudicationBytes: numericAdjudication.bytes,
    adjudicationEvents: [
      candidateVerified,
      adjudicationBegan,
      adjudicationProduced
    ] as const
  }
}

const makeSeed = (): S2SPreparedStageCarrierTestSeed => ({
  classification: "TEST_ONLY_NON_AUTHORIZING",
  stage: "REGISTER",
  sourceCommitA: SOURCE_A,
  currentRunEvidenceReceiptSha256: "e".repeat(64),
  workflowRunId: WORKFLOW_RUN_ID,
  registrationCommitB: REGISTRATION_B,
  workflowApiPath: S2S_CONFIRMATORY_WORKFLOW_PATH,
  workflowRunCreatedAt: "2023-08-23T00:00:00Z",
  workflowRunCreatedAtUnixSeconds: 1_692_748_800,
  currentJobDatabaseId: REGISTER_JOB_ID,
  predecessorJobDatabaseIds: []
})

const requireRight = <Value, Error>(value: Either.Either<Value, Error>): Value => {
  if (Either.isLeft(value)) throw value.left
  return value.right
}

it("prepares one opaque non-authorizing REGISTER carrier from the exact internal builder", () => {
  const seed = makeSeed()
  const capability = requireRight(
    makeS2SPreparedStageCarrierTestCapability(seed, {
      events: [registrationEvent("first")]
    })
  )
  const snapshot = requireRight(
    inspectS2SPreparedStageCarrierTestCapability(capability)
  )

  expect(Object.isFrozen(capability)).toBe(true)
  expect(Object.isFrozen(snapshot)).toBe(true)
  expect(snapshot.authorityScope).toBe("TEST_ONLY_NON_AUTHORIZING")
  expect(snapshot.authorizationClaimed).toBe(false)
  expect(snapshot.oneSemanticProductionSlotClaimed).toBe(false)
  expect(snapshot.stage).toBe("REGISTER")
  expect(snapshot.role).toBe("REGISTRATION")
  expect(snapshot.jobId).toBe("register")
  expect(snapshot.jobName).toBe("register")
  expect(snapshot.artifactName).toBe("s2s-registration")
  expect(snapshot.archiveLogicalName).toBe(
    "upload/registration_archive.zip"
  )
  expect(snapshot.archiveProfileRole).toBe(
    "REGISTRATION_UPLOAD_ARCHIVE"
  )
  expect(snapshot.carrierSchemaVersion).toBe(
    "hswm-swm0w-s2s-registration-carrier/v1"
  )
  expect(snapshot.currentRunEvidenceReceiptSha256).toBe("e".repeat(64))
  expect(snapshot.predecessorReplayReceiptSha256s).toEqual([])
  expect(snapshot.predecessorReplayCarrierSha256s).toEqual([])
  expect(snapshot.members.map((member) => member.name)).toEqual([
    "control_receipt.json"
  ])
  expect(snapshot.members[0]?.rawBytesSha256).toBe(snapshot.carrierRawSha256)
  expect(snapshot.members[0]?.byteLength).toBe(snapshot.carrierByteLength)
  expect(snapshot.preparationReceiptSha256).toMatch(/^[0-9a-f]{64}$/)
})

it("derives all three stage identities and exact 1/2/2 member rosters internally", () => {
  const scenario = makeThreeStageScenario()
  const confirmCapability = requireRight(
    makeS2SPreparedStageCarrierTestCapability(
      {
        ...makeSeed(),
        stage: "CONFIRM",
        currentJobDatabaseId: CONFIRM_JOB_ID,
        predecessorJobDatabaseIds: [REGISTER_JOB_ID]
      },
      {
        registrationReadback: scenario.registrationReadback,
        numericCandidateBytes: scenario.numericCandidateBytes,
        events: scenario.candidateEvents
      }
    )
  )
  const confirm = requireRight(
    inspectS2SPreparedStageCarrierTestCapability(confirmCapability)
  )
  expect({
    stage: confirm.stage,
    role: confirm.role,
    jobId: confirm.jobId,
    artifactName: confirm.artifactName,
    logicalName: confirm.archiveLogicalName,
    profileRole: confirm.archiveProfileRole,
    schemaVersion: confirm.carrierSchemaVersion,
    members: confirm.members.map((member) => member.name)
  }).toEqual({
    stage: "CONFIRM",
    role: "CANDIDATE",
    jobId: "confirm",
    artifactName: "s2s-candidate",
    logicalName: "upload/candidate_archive.zip",
    profileRole: "CANDIDATE_UPLOAD_ARCHIVE",
    schemaVersion: "hswm-swm0w-s2s-candidate-carrier/v1",
    members: ["control_receipt.json", "numeric_candidate.json"]
  })
  expect(confirm.members[0]?.rawBytesSha256).toBe(confirm.carrierRawSha256)
  expect(confirm.members[1]?.rawBytesSha256).toBe(
    rawS2SFileSha256(scenario.numericCandidateBytes)
  )

  const adjudicateCapability = requireRight(
    makeS2SPreparedStageCarrierTestCapability(
      {
        ...makeSeed(),
        stage: "ADJUDICATE",
        currentJobDatabaseId: ADJUDICATION_JOB_ID,
        predecessorJobDatabaseIds: [REGISTER_JOB_ID, CONFIRM_JOB_ID]
      },
      {
        registrationReadback: scenario.registrationReadback,
        candidateReadback: scenario.candidateReadback,
        numericAdjudicationBytes: scenario.numericAdjudicationBytes,
        events: scenario.adjudicationEvents
      }
    )
  )
  const adjudicate = requireRight(
    inspectS2SPreparedStageCarrierTestCapability(adjudicateCapability)
  )
  expect({
    stage: adjudicate.stage,
    role: adjudicate.role,
    jobId: adjudicate.jobId,
    artifactName: adjudicate.artifactName,
    logicalName: adjudicate.archiveLogicalName,
    profileRole: adjudicate.archiveProfileRole,
    schemaVersion: adjudicate.carrierSchemaVersion,
    members: adjudicate.members.map((member) => member.name)
  }).toEqual({
    stage: "ADJUDICATE",
    role: "ADJUDICATION",
    jobId: "adjudicate",
    artifactName: "s2s-adjudication",
    logicalName: "upload/adjudication_archive.zip",
    profileRole: "ADJUDICATION_UPLOAD_ARCHIVE",
    schemaVersion: "hswm-swm0w-s2s-adjudication-carrier/v1",
    members: ["control_receipt.json", "numeric_adjudication.json"]
  })
  expect(adjudicate.members[0]?.rawBytesSha256).toBe(
    adjudicate.carrierRawSha256
  )
  expect(adjudicate.members[1]?.rawBytesSha256).toBe(
    rawS2SFileSha256(scenario.numericAdjudicationBytes)
  )
})

it("returns exact same capability for one seed and fingerprint, then rejects divergent carrier bytes", () => {
  const seed = makeSeed()
  const input = { events: [registrationEvent("stable")] as const }
  const first = requireRight(
    makeS2SPreparedStageCarrierTestCapability(seed, input)
  )
  const second = requireRight(
    makeS2SPreparedStageCarrierTestCapability(seed, input)
  )
  expect(second).toBe(first)

  const divergent = makeS2SPreparedStageCarrierTestCapability(seed, {
    events: [registrationEvent("divergent")]
  })
  expect(Either.isLeft(divergent)).toBe(true)
  if (Either.isLeft(divergent)) {
    expect(divergent.left._tag).toBe("S2SPreparedStageCarrierError")
    if (divergent.left._tag === "S2SPreparedStageCarrierError") {
      expect(divergent.left.reason).toBe("PREPARATION_CONFLICT")
    }
  }
})

it("keeps prepared member bytes private and returns a defensive copy on every read", () => {
  const capability = requireRight(
    makeS2SPreparedStageCarrierTestCapability(makeSeed(), {
      events: [registrationEvent("defensive")]
    })
  )
  const first = requireRight(
    inspectS2SPreparedStageCarrierTestCapability(capability)
  )
  const member = first.members[0]
  if (member === undefined) throw new Error("missing prepared member")
  const bytes = member.readBytes()
  const originalFirstByte = bytes[0]
  bytes[0] = originalFirstByte === 0 ? 1 : 0

  const second = requireRight(
    inspectS2SPreparedStageCarrierTestCapability(capability)
  )
  expect(second.members[0]?.readBytes()[0]).toBe(originalFirstByte)
  expect(second.members[0]?.readBytes()).not.toBe(member.readBytes())
  expect(second.predecessorJobDatabaseIds).not.toBe(
    first.predecessorJobDatabaseIds
  )
})

it("authenticates capabilities by private WeakMap identity, not brand or frozen shape", () => {
  const capability = requireRight(
    makeS2SPreparedStageCarrierTestCapability(makeSeed(), {
      events: [registrationEvent("authentic")]
    })
  )
  const spread = Object.freeze({ ...capability })
  const copied = inspectS2SPreparedStageCarrierTestCapability(spread)
  expect(Either.isLeft(copied)).toBe(true)
  if (Either.isLeft(copied)) expect(copied.left.reason).toBe("INVALID_CAPABILITY")

  const cloned = inspectS2SPreparedStageCarrierTestCapability(
    structuredClone(capability)
  )
  expect(Either.isLeft(cloned)).toBe(true)
  if (Either.isLeft(cloned)) expect(cloned.left.reason).toBe("INVALID_CAPABILITY")

  let traps = 0
  const throwingProxy = new Proxy(capability, {
    get: () => {
      traps += 1
      throw new Error("capability trap must not run")
    },
    getOwnPropertyDescriptor: () => {
      traps += 1
      throw new Error("capability trap must not run")
    },
    getPrototypeOf: () => {
      traps += 1
      throw new Error("capability trap must not run")
    },
    ownKeys: () => {
      traps += 1
      throw new Error("capability trap must not run")
    }
  })
  const proxy = inspectS2SPreparedStageCarrierTestCapability(throwingProxy)
  expect(Either.isLeft(proxy)).toBe(true)
  if (Either.isLeft(proxy)) expect(proxy.left.reason).toBe("INVALID_CAPABILITY")
  expect(traps).toBe(0)
})

it("keeps the production gate closed for fake authority and all test-only capabilities", () => {
  const capability = requireRight(
    makeS2SPreparedStageCarrierTestCapability(makeSeed(), {
      events: [registrationEvent("closed")]
    })
  )
  const fakeAuthority = Object.freeze({})
  const inspected = inspectS2SPreparedStageCarrierCapability(
    fakeAuthority,
    capability
  )
  expect(Either.isLeft(inspected)).toBe(true)
  if (Either.isLeft(inspected)) {
    expect(inspected.left._tag).toBe("S2SCurrentRunInputError")
  }

  let inputWasRead = false
  const hostileInput = Object.defineProperty({}, "events", {
    enumerable: true,
    get: () => {
      inputWasRead = true
      throw new Error("must not execute")
    }
  })
  const prepared = prepareS2SCurrentStageCarrier(fakeAuthority, hostileInput)
  expect(Either.isLeft(prepared)).toBe(true)
  expect(inputWasRead).toBe(false)
})

it("rejects stage selection through the input and hostile or non-canonical seeds", () => {
  const seed = makeSeed()
  let nestedRead = false
  const nestedAccessor = Object.defineProperty({}, "_tag", {
    enumerable: true,
    get: () => {
      nestedRead = true
      throw new Error("nested selector must not run")
    }
  })
  const excessInput = makeS2SPreparedStageCarrierTestCapability(seed, {
    events: [nestedAccessor],
    stage: "REGISTER"
  })
  expect(Either.isLeft(excessInput)).toBe(true)
  expect(nestedRead).toBe(false)

  const confirmSeed = {
    ...makeSeed(),
    stage: "CONFIRM" as const,
    currentJobDatabaseId: 202,
    predecessorJobDatabaseIds: [REGISTER_JOB_ID]
  }
  const mismatchedInput = makeS2SPreparedStageCarrierTestCapability(
    confirmSeed,
    { events: [registrationEvent("mismatch")] }
  )
  expect(Either.isLeft(mismatchedInput)).toBe(true)

  let getterRead = false
  const hostileSeed = Object.defineProperty({}, "classification", {
    enumerable: true,
    get: () => {
      getterRead = true
      return "TEST_ONLY_NON_AUTHORIZING"
    }
  })
  const hostile = makeS2SPreparedStageCarrierTestCapability(hostileSeed, {
    events: [registrationEvent("hostile")]
  })
  expect(Either.isLeft(hostile)).toBe(true)
  expect(getterRead).toBe(false)

  const proxied = makeS2SPreparedStageCarrierTestCapability(
    new Proxy(makeSeed(), {}),
    { events: [registrationEvent("proxy")] }
  )
  expect(Either.isLeft(proxied)).toBe(true)

  let eventProxyTraps = 0
  const eventProxy = new Proxy(registrationEvent("event-proxy"), {
    get: () => {
      eventProxyTraps += 1
      throw new Error("nested event proxy trap must not run")
    },
    getOwnPropertyDescriptor: () => {
      eventProxyTraps += 1
      throw new Error("nested event proxy trap must not run")
    },
    getPrototypeOf: () => {
      eventProxyTraps += 1
      throw new Error("nested event proxy trap must not run")
    },
    ownKeys: () => {
      eventProxyTraps += 1
      throw new Error("nested event proxy trap must not run")
    }
  })
  const hostileEvent = makeS2SPreparedStageCarrierTestCapability(makeSeed(), {
    events: [eventProxy]
  })
  expect(Either.isLeft(hostileEvent)).toBe(true)
  expect(eventProxyTraps).toBe(0)

  const fakeReplay = inspectS2SStageArtifactReadReplaySnapshot(Object.freeze({}))
  expect(Either.isLeft(fakeReplay)).toBe(true)
  if (Either.isLeft(fakeReplay)) expect(fakeReplay.left.reason).toBe("INPUT_INVALID")
})

it("remains root-private and does not widen the package public API", () => {
  expect("prepareS2SCurrentStageCarrier" in PublicApi).toBe(false)
  expect("inspectS2SPreparedStageCarrierCapability" in PublicApi).toBe(false)
  expect("makeS2SPreparedStageCarrierTestCapability" in PublicApi).toBe(false)
})
