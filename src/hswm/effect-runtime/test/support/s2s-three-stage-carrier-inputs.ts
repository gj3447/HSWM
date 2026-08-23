import { Either, Schema } from "effect"

import {
  canonicalS2SControlJsonBytes,
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "../../src/s2s-canonical.js"
import {
  S2SArtifactEvidenceSchema,
  S2SConfirmatoryEventSchema,
  S2S_CANDIDATE_ARTIFACT_NAME,
  S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
  S2S_CONFIRMATORY_EXPERIMENT_ID,
  S2S_CONFIRMATORY_RESOURCE_POLICY_SHA256,
  S2S_DRAND_STABLE_PROJECTION_SCHEMA_VERSION,
  S2S_GITHUB_ARTIFACT_DOWNLOAD_RECEIPT_SCHEMA_VERSION,
  S2S_GITHUB_OBSERVATION_RECEIPT_SCHEMA_VERSION,
  S2S_NUMERIC_ORACLE_SOURCE_SHA256,
  S2S_PILOT_ADOPTION_RECEIPT_SHA256,
  S2S_PROTOCOL_CONFIG_RECEIPT_SHA256,
  S2S_PYTHON_EXECUTION_EVIDENCE_SCHEMA_VERSION,
  S2S_REGISTRATION_ARTIFACT_NAME,
  S2SSha256Schema,
  advanceS2SConfirmatory,
  initialS2SConfirmatoryState,
  type S2SArtifactEvidence,
  type S2SConfirmatoryEvent,
  type S2SConfirmatoryState
} from "../../src/s2s-confirmatory.js"
import {
  prepareS2SCandidateCarrier,
  prepareS2SRegistrationCarrier,
  type S2SCarrierReadback,
  type S2SUploadMember
} from "../../src/s2s-job-sequence.js"
import type {
  S2SAdjudicatePreparedCarrierTestInput,
  S2SConfirmPreparedCarrierTestInput,
  S2SRegisterPreparedCarrierInput
} from "../../src/s2s-prepared-stage-carrier.js"
import { buildS2STestActionZip } from "./s2s-action-zip.js"

const CHAIN_HASH =
  "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971"
const RANDOMNESS =
  "fe290beca10872ef2fb164d2aa4442de4566183ec51c56ff3cd603d930e54fdd"
const SIGNATURE =
  "b44679b9a59af2ec876b1a6b1ad52ea9b1615fc3982b19576350f93447cb1125e342b73a8dd2bacbe47e4b6b63ed5e39"
const EXTERNAL_SEED =
  "552e51d2ff75cb7c5df5b55a166aba12a277c2813bbdd69bc825286e7c26b6f0"
const NUMERIC_CONFIRM_REQUEST_SHA256 = "9".repeat(64)
const NUMERIC_CANDIDATE_RECEIPT_SHA256 = "8".repeat(64)
const ENCODER = new TextEncoder()

export interface S2SThreeStageCarrierInputConfig {
  readonly sourceCommitA: string
  readonly registrationCommitB: string
  readonly workflowSha256: string
  readonly preregistrationSha256: string
  readonly workflowRunId: number
  readonly registerJobDatabaseId: number
  readonly confirmJobDatabaseId: number
  readonly adjudicateJobDatabaseId: number
  readonly workflowCreatedAtUnixSeconds: number
}

export interface S2SThreeStageCarrierInputs {
  readonly register: S2SRegisterPreparedCarrierInput
  readonly confirm: S2SConfirmPreparedCarrierTestInput
  readonly adjudicate: S2SAdjudicatePreparedCarrierTestInput
}

const right = <A, E>(outcome: Either.Either<A, E>): A => {
  if (Either.isLeft(outcome)) throw outcome.left
  return outcome.right
}

const decodeEvent = Schema.decodeUnknownSync(S2SConfirmatoryEventSchema, {
  onExcessProperty: "error"
})

const evidenceHash = (label: string): string =>
  rawS2SFileSha256(ENCODER.encode(label))

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
): S2SConfirmatoryState => right(advanceS2SConfirmatory(state, event))

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

export const makeS2SThreeStageCarrierInputs = (
  config: S2SThreeStageCarrierInputConfig
): S2SThreeStageCarrierInputs => {
  const registrationStartedAt = config.workflowCreatedAtUnixSeconds + 10
  const registrationCompletedAt = config.workflowCreatedAtUnixSeconds + 110
  const confirmStartedAt = config.workflowCreatedAtUnixSeconds + 120
  const futureRoundTime = config.workflowCreatedAtUnixSeconds + 200
  const confirmCompletedAt = config.workflowCreatedAtUnixSeconds + 320
  const adjudicationStartedAt = config.workflowCreatedAtUnixSeconds + 330
  const binding = (predecessorControlReceiptSha256: string) => ({
    experimentId: S2S_CONFIRMATORY_EXPERIMENT_ID,
    sourceCommitA: config.sourceCommitA,
    registrationCommitB: config.registrationCommitB,
    workflowRunId: config.workflowRunId,
    workflowRunAttempt: 1,
    workflowHeadSha: config.registrationCommitB,
    workflowSha256: config.workflowSha256,
    preregistrationSha256: config.preregistrationSha256,
    resourcePolicySha256: S2S_CONFIRMATORY_RESOURCE_POLICY_SHA256,
    protocolConfigSha256: S2S_PROTOCOL_CONFIG_RECEIPT_SHA256,
    githubObservationSchemaVersion:
      S2S_GITHUB_OBSERVATION_RECEIPT_SCHEMA_VERSION,
    githubArtifactDownloadSchemaVersion:
      S2S_GITHUB_ARTIFACT_DOWNLOAD_RECEIPT_SCHEMA_VERSION,
    predecessorControlReceiptSha256
  })
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
      receiptSha256: right(canonicalS2SControlSha256(unsigned))
    }
  }

  const initial = initialS2SConfirmatoryState()
  const registrationEvent = decodeEvent({
    schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
    _tag: "BeginRegistration",
    binding: binding(initial.latestControlReceiptSha256),
    adoptionReceiptSha256: S2S_PILOT_ADOPTION_RECEIPT_SHA256,
    workflowRunId: config.workflowRunId,
    registrationJobId: config.registerJobDatabaseId,
    workflowRunAttempt: 1,
    workflowHeadSha: config.registrationCommitB,
    workflowCreatedAtUnixSeconds: config.workflowCreatedAtUnixSeconds,
    registrationJobStartedAtUnixSeconds: registrationStartedAt,
    workflowRunObservationReceiptSha256: evidenceHash("run-registration"),
    workflowJobsObservationReceiptSha256: evidenceHash("jobs-registration"),
    workflowRunStatus: "in_progress",
    registrationJobStatus: "in_progress",
    sourceCommitSha: config.sourceCommitA,
    preregistrationCommitSha: config.registrationCommitB,
    beaconId: "quicknet",
    beaconChainHashHex: CHAIN_HASH,
    futureBeaconRound: 1_000,
    futureRoundCommitmentSelfHashSha256:
      "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f",
    declaredPulseLeadSeconds: 200
  })
  if (registrationEvent._tag !== "BeginRegistration") {
    throw new Error("wrong registration event")
  }
  let state = advance(initial, registrationEvent)
  const registration = right(prepareS2SRegistrationCarrier([registrationEvent]))
  const registrationArchive = buildS2STestActionZip(
    zipMembers(registration.members)
  )
  const registrationArtifact = artifactFromArchive(
    S2S_REGISTRATION_ARTIFACT_NAME,
    1,
    registrationArchive,
    registration.members
  )
  const registrationReadback: S2SCarrierReadback = Object.freeze({
    artifact: registrationArtifact,
    archiveBytes: registrationArchive
  })

  const registrationVerified = decodeEvent({
    schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
    _tag: "VerifyRegistration",
    binding: binding(state.latestControlReceiptSha256),
    workflowRunId: config.workflowRunId,
    registrationJobId: config.registerJobDatabaseId,
    workflowRunAttempt: 1,
    workflowHeadSha: config.registrationCommitB,
    registrationJobCompletedAtUnixSeconds: registrationCompletedAt,
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
    artifact: registrationArtifact,
    archiveMembers: ["control_receipt.json"]
  })
  if (registrationVerified._tag !== "VerifyRegistration") {
    throw new Error("wrong registration verification event")
  }
  state = advance(state, registrationVerified)
  const confirmBegan = decodeEvent({
    schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
    _tag: "BeginConfirm",
    binding: binding(state.latestControlReceiptSha256),
    workflowRunId: config.workflowRunId,
    confirmJobId: config.confirmJobDatabaseId,
    workflowRunAttempt: 1,
    workflowHeadSha: config.registrationCommitB,
    confirmJobStartedAtUnixSeconds: confirmStartedAt,
    workflowRunObservationReceiptSha256: evidenceHash("run-confirm-start"),
    workflowJobsObservationReceiptSha256: evidenceHash("jobs-confirm-start"),
    workflowRunStatus: "in_progress",
    confirmJobStatus: "in_progress",
    attempt: attempt()
  })
  if (confirmBegan._tag !== "BeginConfirm") {
    throw new Error("wrong confirm event")
  }
  state = advance(state, confirmBegan)
  const pulse = decodeEvent({
    schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
    _tag: "AcceptVerifiedPulse",
    binding: binding(state.latestControlReceiptSha256),
    workflowRunId: config.workflowRunId,
    confirmJobId: config.confirmJobDatabaseId,
    beaconId: "quicknet",
    beaconChainHashHex: CHAIN_HASH,
    beaconRound: 1_000,
    roundTimeUnixSeconds: futureRoundTime,
    pulseWaitStartedAtUnixSeconds: confirmStartedAt,
    verifiedAtUnixSeconds: futureRoundTime,
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
  if (pulse._tag !== "AcceptVerifiedPulse") {
    throw new Error("wrong pulse event")
  }
  state = advance(state, pulse)
  const numericConfirmBegan = decodeEvent({
    schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
    _tag: "BeginNumericConfirm",
    binding: binding(state.latestControlReceiptSha256),
    workflowRunId: config.workflowRunId,
    confirmJobId: config.confirmJobDatabaseId
  })
  if (numericConfirmBegan._tag !== "BeginNumericConfirm") {
    throw new Error("wrong numeric-confirm event")
  }
  state = advance(state, numericConfirmBegan)
  const numericCandidateBytes = ENCODER.encode('{"candidate":true}\n')
  const candidateSha256 = rawS2SFileSha256(numericCandidateBytes)
  const requestDocumentSha256 = evidenceHash("numeric-confirm-request-raw")
  const candidateProduced = decodeEvent({
    schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
    _tag: "RecordCandidateProduced",
    binding: binding(state.latestControlReceiptSha256),
    adoptionReceiptSha256: S2S_PILOT_ADOPTION_RECEIPT_SHA256,
    workflowRunId: config.workflowRunId,
    confirmJobId: config.confirmJobDatabaseId,
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
  if (candidateProduced._tag !== "RecordCandidateProduced") {
    throw new Error("wrong candidate event")
  }
  const candidateEvents = Object.freeze(
    [
      registrationVerified,
      confirmBegan,
      pulse,
      numericConfirmBegan,
      candidateProduced
    ] as const
  )
  const candidate = right(
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
  const candidateReadback: S2SCarrierReadback = Object.freeze({
    artifact: candidateArtifact,
    archiveBytes: candidateArchive
  })

  const candidateVerified = decodeEvent({
    schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
    _tag: "VerifyCandidateArtifact",
    binding: binding(state.latestControlReceiptSha256),
    workflowRunId: config.workflowRunId,
    confirmJobId: config.confirmJobDatabaseId,
    confirmJobCompletedAtUnixSeconds: confirmCompletedAt,
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
    artifact: candidateArtifact,
    archiveMembers: ["control_receipt.json", "numeric_candidate.json"],
    readbackContainsCanonicalCandidate: true
  })
  if (candidateVerified._tag !== "VerifyCandidateArtifact") {
    throw new Error("wrong candidate verification event")
  }
  state = advance(state, candidateVerified)
  const adjudicationBegan = decodeEvent({
    schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
    _tag: "BeginAdjudication",
    binding: binding(state.latestControlReceiptSha256),
    workflowRunId: config.workflowRunId,
    adjudicationJobId: config.adjudicateJobDatabaseId,
    workflowRunAttempt: 1,
    workflowHeadSha: config.registrationCommitB,
    adjudicationJobStartedAtUnixSeconds: adjudicationStartedAt,
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
  if (adjudicationBegan._tag !== "BeginAdjudication") {
    throw new Error("wrong adjudication event")
  }
  state = advance(state, adjudicationBegan)
  const adjudicationUnsigned = {
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
  const adjudicationReceiptSha256 = right(
    canonicalS2SControlSha256(adjudicationUnsigned)
  )
  const numericAdjudicationBytes = right(
    canonicalS2SControlJsonBytes({
      ...adjudicationUnsigned,
      receipt_sha256: adjudicationReceiptSha256
    })
  )
  const adjudicationProduced = decodeEvent({
    schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
    _tag: "RecordAdjudicationProduced",
    binding: binding(state.latestControlReceiptSha256),
    adoptionReceiptSha256: S2S_PILOT_ADOPTION_RECEIPT_SHA256,
    workflowRunId: config.workflowRunId,
    adjudicationJobId: config.adjudicateJobDatabaseId,
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
    numericAdjudicationBytesSha256: rawS2SFileSha256(
      numericAdjudicationBytes
    ),
    pythonExecution: pythonExecution({
      operation: "adjudicate",
      inputRawBytesSha256: candidateSha256,
      outputRawBytesSha256: rawS2SFileSha256(numericAdjudicationBytes),
      requestDocumentSha256: candidateSha256,
      requestSelfSha256: NUMERIC_CANDIDATE_RECEIPT_SHA256,
      elapsedNanoseconds: 590_000_000_000
    }),
    candidateOnly: true
  })
  if (adjudicationProduced._tag !== "RecordAdjudicationProduced") {
    throw new Error("wrong adjudication-produced event")
  }

  return Object.freeze({
    register: Object.freeze({
      events: Object.freeze([registrationEvent] as const)
    }),
    confirm: Object.freeze({
      registrationReadback,
      numericCandidateBytes,
      events: candidateEvents
    }),
    adjudicate: Object.freeze({
      registrationReadback,
      candidateReadback,
      numericAdjudicationBytes,
      events: Object.freeze(
        [candidateVerified, adjudicationBegan, adjudicationProduced] as const
      )
    })
  })
}
