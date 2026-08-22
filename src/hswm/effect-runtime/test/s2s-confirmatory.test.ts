import { expect, it } from "@effect/vitest"
import { Effect, Either, Exit, Option, Schema } from "effect"
import {
  constants,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  statSync,
  symlinkSync,
  writeFileSync
} from "node:fs"
import { open } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { vi } from "vitest"

import {
  canonicalS2SControlJson,
  canonicalS2SControlJsonBytes,
  canonicalS2SControlSha256,
  deriveS2SExternalSeed,
  rawS2SFileSha256
} from "../src/index.js"
import {
  S2SConfirmatoryEventSchema,
  S2S_DRAND_STABLE_PROJECTION_SCHEMA_VERSION,
  S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
  S2S_CONFIRMATORY_EXPERIMENT_ID,
  S2S_CONFIRMATORY_POLICY,
  S2S_CONFIRMATORY_POLICY_SCHEMA_VERSION,
  S2S_CONFIRMATORY_RESOURCE_POLICY_SHA256,
  S2S_GITHUB_ARTIFACT_DOWNLOAD_RECEIPT_SCHEMA_VERSION,
  S2S_GITHUB_OBSERVATION_RECEIPT_SCHEMA_VERSION,
  S2S_NUMERIC_ORACLE_SOURCE_SHA256,
  S2S_PILOT_ADOPTION_RECEIPT_SHA256,
  S2S_PYTHON_EXECUTION_EVIDENCE_SCHEMA_VERSION,
  S2S_PROTOCOL_CONFIG_DOCUMENT_SHA256,
  S2S_PROTOCOL_CONFIG_RECEIPT_SHA256,
  S2SSha256Schema,
  advanceS2SConfirmatory,
  initialS2SConfirmatoryState,
  type S2SConfirmatoryEvent,
  type S2SConfirmatoryState,
  type S2SOperationalVoidReason
} from "../src/s2s-confirmatory.js"
import {
  buildS2SDurableJournal,
  reconstructS2SDurableJournalChain
} from "../src/s2s-durable.js"
import {
  S2S_DURABLE_JOURNAL_MAX_FILE_BYTES,
  S2SDurableJournalFileStore,
  makeS2SDurableJournalFileStoreLayer
} from "../src/s2s-durable-file.js"
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
import {
  S2S_QUICKNET_CHAIN_HASH,
  S2S_QUICKNET_GENESIS_TIME,
  S2S_QUICKNET_PERIOD_SECONDS,
  s2sQuicknetRoundTimeUnix
} from "../src/s2s-quicknet.js"

const SOURCE_A = "a".repeat(40)
const REGISTRATION_B = "b".repeat(40)
const WORKFLOW_SHA256 = "c".repeat(64)
const PREREGISTRATION_SHA256 = "d".repeat(64)
const CHAIN_HASH =
  "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971"
const RANDOMNESS =
  "fe290beca10872ef2fb164d2aa4442de4566183ec51c56ff3cd603d930e54fdd"
const SIGNATURE =
  "b44679b9a59af2ec876b1a6b1ad52ea9b1615fc3982b19576350f93447cb1125e342b73a8dd2bacbe47e4b6b63ed5e39"
const FUTURE_COMMITMENT =
  "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"
const EXTERNAL_SEED =
  "552e51d2ff75cb7c5df5b55a166aba12a277c2813bbdd69bc825286e7c26b6f0"
const WORKFLOW_RUN_ID = 101
const REGISTER_JOB_ID = 201
const CONFIRM_JOB_ID = 202
const ADJUDICATION_JOB_ID = 203
const FUTURE_BEACON_ROUND = 1_000
// Quicknet: 1_692_803_367 + (round - 1) * 3.
const FUTURE_ROUND_TIME_UNIX_SECONDS = 1_692_806_364
const WORKFLOW_CREATED_AT_UNIX_SECONDS =
  FUTURE_ROUND_TIME_UNIX_SECONDS - 200
const REGISTRATION_STARTED_AT_UNIX_SECONDS =
  FUTURE_ROUND_TIME_UNIX_SECONDS - 190
const REGISTRATION_COMPLETED_AT_UNIX_SECONDS =
  FUTURE_ROUND_TIME_UNIX_SECONDS - 90
const CONFIRM_STARTED_AT_UNIX_SECONDS =
  FUTURE_ROUND_TIME_UNIX_SECONDS - 80
const CONFIRM_COMPLETED_AT_UNIX_SECONDS =
  CONFIRM_STARTED_AT_UNIX_SECONDS + 200
const ADJUDICATION_STARTED_AT_UNIX_SECONDS =
  CONFIRM_COMPLETED_AT_UNIX_SECONDS + 10
const ADJUDICATION_COMPLETED_AT_UNIX_SECONDS =
  ADJUDICATION_STARTED_AT_UNIX_SECONDS + 700

const decodeEvent = Schema.decodeUnknownSync(S2SConfirmatoryEventSchema, {
  onExcessProperty: "error"
})

const evidenceHash = (label: string): string =>
  rawS2SFileSha256(new TextEncoder().encode(label))

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
    exitCode: 0 as const
  }
  const receipt = canonicalS2SControlSha256(unsigned)
  if (Either.isLeft(receipt)) throw receipt.left
  return { ...unsigned, receiptSha256: receipt.right }
}

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
  workflowCreatedAtUnixSeconds: WORKFLOW_CREATED_AT_UNIX_SECONDS,
  registrationJobStartedAtUnixSeconds: REGISTRATION_STARTED_AT_UNIX_SECONDS,
  workflowRunObservationReceiptSha256: evidenceHash("run-register-start"),
  workflowJobsObservationReceiptSha256: evidenceHash("jobs-register-start"),
  workflowRunStatus: "in_progress",
  registrationJobStatus: "in_progress",
  sourceCommitSha: SOURCE_A,
  preregistrationCommitSha: REGISTRATION_B,
  beaconId: "quicknet",
  beaconChainHashHex: CHAIN_HASH,
  futureBeaconRound: FUTURE_BEACON_ROUND,
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
  registrationJobCompletedAtUnixSeconds: REGISTRATION_COMPLETED_AT_UNIX_SECONDS,
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
  artifact: artifact("s2s-registration", 301, "1"),
  archiveMembers: ["control_receipt.json"]
})

const beginConfirm = (predecessor: string) => ({
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

const acceptPulse = (predecessor: string) => ({
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
  rss: {
    api: "getrusage",
    subject: "RUSAGE_SELF",
    unit: "KiB",
    peakRssKiB: 171_108,
    oomObserved: false
  },
  numericCandidateBytesSha256: "3".repeat(64),
  numericConfirmRequestSha256: "9".repeat(64),
  numericConfirmRequestDocumentSha256: evidenceHash(
    "numeric-confirm-request-raw"
  ),
  pythonExecution: pythonExecution({
    operation: "confirm",
    inputRawBytesSha256: evidenceHash("numeric-confirm-request-raw"),
    outputRawBytesSha256: "3".repeat(64),
    requestDocumentSha256: evidenceHash("numeric-confirm-request-raw"),
    requestSelfSha256: "9".repeat(64),
    elapsedNanoseconds: 90_000_000_000
  }),
  numericCandidateLabel: "NUMERIC_REPLAY_VALIDATED_CANDIDATE_ONLY",
  candidateOnly: true
})

const verifyCandidateArtifact = (predecessor: string) => ({
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
  adjudicationJobStartedAtUnixSeconds: ADJUDICATION_STARTED_AT_UNIX_SECONDS,
  workflowRunObservationReceiptSha256: evidenceHash("run-adjudication-start"),
  workflowJobsObservationReceiptSha256: evidenceHash(
    "jobs-adjudication-start"
  ),
  workflowRunStatus: "in_progress",
  adjudicationJobStatus: "in_progress",
  attempt: attempt(),
  candidateArtifactId: 302,
  expectedCandidateArchiveSha256: "4".repeat(64),
  requeriedApiDigestSha256: "4".repeat(64),
  redownloadedCandidateArchiveSha256: "4".repeat(64),
  candidateArtifactRequeryObservationReceiptSha256: evidenceHash(
    "artifact-candidate-requery-api"
  ),
  candidateArtifactRedownloadObservationReceiptSha256: evidenceHash(
    "artifact-candidate-redownload"
  )
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
  drandReplayReceiptSha256: evidenceHash("drand-independent-replay"),
  drandReplayFixtureSha256: evidenceHash("drand-replay-fixture"),
  drandReplayStableProjectionSchemaVersion:
    S2S_DRAND_STABLE_PROJECTION_SCHEMA_VERSION,
  drandReplayStableProjectionSha256: evidenceHash("drand-stable-projection"),
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
  rss: {
    api: "getrusage",
    subject: "RUSAGE_SELF",
    unit: "KiB",
    peakRssKiB: 160_000,
    oomObserved: false
  },
  numericAdjudicationBytesSha256: "5".repeat(64),
  pythonExecution: pythonExecution({
    operation: "adjudicate",
    inputRawBytesSha256: "3".repeat(64),
    outputRawBytesSha256: "5".repeat(64),
    requestDocumentSha256: "3".repeat(64),
    requestSelfSha256: "8".repeat(64),
    elapsedNanoseconds: 590_000_000_000
  }),
  candidateOnly: true
})

const verifyEvidenceArtifact = (predecessor: string) => ({
  schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
  _tag: "VerifyEvidenceArtifact",
  binding: binding(predecessor),
  workflowRunId: WORKFLOW_RUN_ID,
  adjudicationJobId: ADJUDICATION_JOB_ID,
  adjudicationJobCompletedAtUnixSeconds: ADJUDICATION_COMPLETED_AT_UNIX_SECONDS,
  jobElapsedSeconds: 700,
  workflowRunCompletedAtUnixSeconds: ADJUDICATION_COMPLETED_AT_UNIX_SECONDS + 1,
  finalizerObservedAtUnixSeconds: ADJUDICATION_COMPLETED_AT_UNIX_SECONDS + 2,
  workflowRunCompletedObservationReceiptSha256: evidenceHash(
    "run-final-completed"
  ),
  workflowJobsCompletedObservationReceiptSha256: evidenceHash(
    "jobs-final-completed"
  ),
  workflowRunStatus: "completed",
  workflowRunConclusion: "success",
  registrationJobStatus: "completed",
  registrationJobConclusion: "success",
  confirmJobStatus: "completed",
  confirmJobConclusion: "success",
  adjudicationJobStatus: "completed",
  adjudicationJobConclusion: "success",
  adjudicationArtifactApiObservationReceiptSha256: evidenceHash(
    "artifact-adjudication-api"
  ),
  adjudicationArtifactDownloadObservationReceiptSha256: evidenceHash(
    "artifact-adjudication-download"
  ),
  numericAdjudicationBytesSha256: "5".repeat(64),
  artifact: artifact("s2s-adjudication", 303, "6"),
  archiveMembers: ["control_receipt.json", "numeric_adjudication.json"],
  readbackContainsCanonicalAdjudication: true,
  compactCompetitivePhraseAllowed: false
})

const operationalVoid = (
  predecessor: string,
  workflowJobId: number,
  reason: S2SOperationalVoidReason
) => ({
  schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
  _tag: "RecordOperationalVoid",
  binding: binding(predecessor),
  workflowRunId: WORKFLOW_RUN_ID,
  workflowJobId,
  workflowRunAttempt: 1,
  reason,
  evidenceSha256: "7".repeat(64),
  workflowRunObservationReceiptSha256: evidenceHash("void-run-observation"),
  workflowJobsObservationReceiptSha256: evidenceHash("void-jobs-observation")
})

const advance = (
  state: S2SConfirmatoryState,
  input: unknown
): S2SConfirmatoryState => {
  const result = advanceS2SConfirmatory(state, decodeEvent(input))
  if (Either.isLeft(result)) throw result.left
  return result.right
}

const throughConfirmWaiting = (): S2SConfirmatoryState => {
  let state: S2SConfirmatoryState = initialS2SConfirmatoryState()
  state = advance(state, beginRegistration(state.latestControlReceiptSha256))
  state = advance(state, verifyRegistration(state.latestControlReceiptSha256))
  return advance(state, beginConfirm(state.latestControlReceiptSha256))
}

const throughConfirmRunning = (): S2SConfirmatoryState => {
  let state = throughConfirmWaiting()
  state = advance(state, acceptPulse(state.latestControlReceiptSha256))
  return advance(state, beginNumericConfirm(state.latestControlReceiptSha256))
}

const throughCandidateProduced = (): S2SConfirmatoryState => {
  const running = throughConfirmRunning()
  return advance(running, recordCandidate(running.latestControlReceiptSha256))
}

const healthyEventSequence = (): ReadonlyArray<S2SConfirmatoryEvent> => {
  let state = initialS2SConfirmatoryState()
  const events: Array<S2SConfirmatoryEvent> = []
  const append = (input: unknown): void => {
    const event = decodeEvent(input)
    const result = advanceS2SConfirmatory(state, event)
    if (Either.isLeft(result)) throw result.left
    events.push(event)
    state = result.right
  }

  append(beginRegistration(state.latestControlReceiptSha256))
  append(verifyRegistration(state.latestControlReceiptSha256))
  append(beginConfirm(state.latestControlReceiptSha256))
  append(acceptPulse(state.latestControlReceiptSha256))
  append(beginNumericConfirm(state.latestControlReceiptSha256))
  append(recordCandidate(state.latestControlReceiptSha256))
  append(verifyCandidateArtifact(state.latestControlReceiptSha256))
  append(beginAdjudication(state.latestControlReceiptSha256))
  append(recordAdjudication(state.latestControlReceiptSha256))
  append(verifyEvidenceArtifact(state.latestControlReceiptSha256))
  return Object.freeze(events.slice())
}

const rightOrThrow = <A, E>(either: Either.Either<A, E>): A => {
  if (Either.isLeft(either)) throw either.left
  return either.right
}

const healthyDurableChain = () => {
  const events = healthyEventSequence()
  const registration = rightOrThrow(
    buildS2SDurableJournal("REGISTRATION_CARRIER", [], events.slice(0, 1))
  )
  const candidate = rightOrThrow(
    buildS2SDurableJournal(
      "CANDIDATE_CARRIER",
      [registration.canonicalBytes],
      events.slice(1, 6)
    )
  )
  const adjudication = rightOrThrow(
    buildS2SDurableJournal(
      "ADJUDICATION_CARRIER",
      [registration.canonicalBytes, candidate.canonicalBytes],
      events.slice(6, 9)
    )
  )
  const finalReadback = rightOrThrow(
    buildS2SDurableJournal(
      "FINAL_READBACK",
      [
        registration.canonicalBytes,
        candidate.canonicalBytes,
        adjudication.canonicalBytes
      ],
      events.slice(9)
    )
  )
  return { registration, candidate, adjudication, finalReadback }
}

it("freezes the adopted resource policy and disables the DS-derived phrase", () => {
  expect(S2S_CONFIRMATORY_POLICY_SCHEMA_VERSION).toBe(
    "hswm-swm0w-s2s-confirmatory-operational-policy/v4"
  )
  expect(S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION).toBe(
    "hswm-swm0w-s2s-confirmatory-control-event/v4"
  )
  expect(S2S_CONFIRMATORY_RESOURCE_POLICY_SHA256).toBe(
    "b2c631ff80922800d06ac7e31c0632e02e1b560a31759cd0d11ae0a39c374351"
  )
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

it("binds pulse chronology to the independently derived Quicknet round", () => {
  expect(S2S_QUICKNET_CHAIN_HASH).toBe(CHAIN_HASH)
  expect(
    S2S_QUICKNET_GENESIS_TIME +
      (FUTURE_BEACON_ROUND - 1) * S2S_QUICKNET_PERIOD_SECONDS
  ).toBe(FUTURE_ROUND_TIME_UNIX_SECONDS)
  expect(s2sQuicknetRoundTimeUnix(FUTURE_BEACON_ROUND)).toBe(
    FUTURE_ROUND_TIME_UNIX_SECONDS
  )

  const initial = initialS2SConfirmatoryState()

  const mismatchedLead = advanceS2SConfirmatory(
    initial,
    decodeEvent({
      ...beginRegistration(initial.latestControlReceiptSha256),
      declaredPulseLeadSeconds: 199
    })
  )
  expect(Either.isLeft(mismatchedLead)).toBe(true)

  const wrongQuicknetChain = advanceS2SConfirmatory(
    initial,
    decodeEvent({
      ...beginRegistration(initial.latestControlReceiptSha256),
      beaconChainHashHex: "f".repeat(64)
    })
  )
  expect(Either.isLeft(wrongQuicknetChain)).toBe(true)

  const nonfutureRound = advanceS2SConfirmatory(
    initial,
    decodeEvent({
      ...beginRegistration(initial.latestControlReceiptSha256),
      workflowCreatedAtUnixSeconds: FUTURE_ROUND_TIME_UNIX_SECONDS,
      registrationJobStartedAtUnixSeconds: FUTURE_ROUND_TIME_UNIX_SECONDS,
      declaredPulseLeadSeconds: 0
    })
  )
  expect(Either.isLeft(nonfutureRound)).toBe(true)

  const maximumLead = advanceS2SConfirmatory(
    initial,
    decodeEvent({
      ...beginRegistration(initial.latestControlReceiptSha256),
      workflowCreatedAtUnixSeconds:
        FUTURE_ROUND_TIME_UNIX_SECONDS -
        S2S_CONFIRMATORY_POLICY.deadlines.maximumDeclaredPulseLeadSeconds,
      declaredPulseLeadSeconds:
        S2S_CONFIRMATORY_POLICY.deadlines.maximumDeclaredPulseLeadSeconds
    })
  )
  expect(Either.isRight(maximumLead)).toBe(true)

  let state = advance(
    initial,
    beginRegistration(initial.latestControlReceiptSha256)
  )
  for (const completedAt of [
    FUTURE_ROUND_TIME_UNIX_SECONDS,
    FUTURE_ROUND_TIME_UNIX_SECONDS + 1
  ]) {
    const registrationAtOrAfterPulse = advanceS2SConfirmatory(
      state,
      decodeEvent({
        ...verifyRegistration(state.latestControlReceiptSha256),
        registrationJobCompletedAtUnixSeconds: completedAt,
        jobElapsedSeconds:
          completedAt - REGISTRATION_STARTED_AT_UNIX_SECONDS
      })
    )
    expect(Either.isLeft(registrationAtOrAfterPulse)).toBe(true)
  }

  state = advance(state, verifyRegistration(state.latestControlReceiptSha256))
  state = advance(state, beginConfirm(state.latestControlReceiptSha256))

  const preWorkflowPulse = advanceS2SConfirmatory(
    state,
    decodeEvent({
      ...acceptPulse(state.latestControlReceiptSha256),
      roundTimeUnixSeconds: 1,
      pulseWaitStartedAtUnixSeconds: 1,
      verifiedAtUnixSeconds: 1,
      pulseWaitElapsedSeconds: 0
    })
  )
  expect(Either.isLeft(preWorkflowPulse)).toBe(true)

  const wrongRoundTime = advanceS2SConfirmatory(
    state,
    decodeEvent({
      ...acceptPulse(state.latestControlReceiptSha256),
      roundTimeUnixSeconds: FUTURE_ROUND_TIME_UNIX_SECONDS - 1
    })
  )
  expect(Either.isLeft(wrongRoundTime)).toBe(true)

  const waitBeforeConfirm = advanceS2SConfirmatory(
    state,
    decodeEvent({
      ...acceptPulse(state.latestControlReceiptSha256),
      pulseWaitStartedAtUnixSeconds: CONFIRM_STARTED_AT_UNIX_SECONDS - 1,
      pulseWaitElapsedSeconds: 81
    })
  )
  expect(Either.isLeft(waitBeforeConfirm)).toBe(true)

  const verificationBeforeRound = advanceS2SConfirmatory(
    state,
    decodeEvent({
      ...acceptPulse(state.latestControlReceiptSha256),
      verifiedAtUnixSeconds: FUTURE_ROUND_TIME_UNIX_SECONDS - 1,
      pulseWaitElapsedSeconds: 79
    })
  )
  expect(Either.isLeft(verificationBeforeRound)).toBe(true)

  const mismatchedWait = advanceS2SConfirmatory(
    state,
    decodeEvent({
      ...acceptPulse(state.latestControlReceiptSha256),
      pulseWaitElapsedSeconds: 79
    })
  )
  expect(Either.isLeft(mismatchedWait)).toBe(true)

  const maximumWait = advanceS2SConfirmatory(
    state,
    decodeEvent({
      ...acceptPulse(state.latestControlReceiptSha256),
      pulseWaitStartedAtUnixSeconds: FUTURE_ROUND_TIME_UNIX_SECONDS,
      verifiedAtUnixSeconds:
        FUTURE_ROUND_TIME_UNIX_SECONDS +
        S2S_CONFIRMATORY_POLICY.deadlines.confirmWaitBudgetSeconds,
      pulseWaitElapsedSeconds:
        S2S_CONFIRMATORY_POLICY.deadlines.confirmWaitBudgetSeconds
    })
  )
  expect(Either.isRight(maximumWait)).toBe(true)

  const excessiveWait = advanceS2SConfirmatory(
    state,
    decodeEvent({
      ...acceptPulse(state.latestControlReceiptSha256),
      pulseWaitStartedAtUnixSeconds: FUTURE_ROUND_TIME_UNIX_SECONDS,
      verifiedAtUnixSeconds:
        FUTURE_ROUND_TIME_UNIX_SECONDS +
        S2S_CONFIRMATORY_POLICY.deadlines.confirmWaitBudgetSeconds +
        1,
      pulseWaitElapsedSeconds:
        S2S_CONFIRMATORY_POLICY.deadlines.confirmWaitBudgetSeconds + 1
    })
  )
  expect(Either.isLeft(excessiveWait)).toBe(true)

  state = advance(state, acceptPulse(state.latestControlReceiptSha256))
  expect(state._tag).toBe("PulseEligible")
})

it("permits a confirm wait that starts after the committed pulse", () => {
  let state: S2SConfirmatoryState = initialS2SConfirmatoryState()
  state = advance(state, beginRegistration(state.latestControlReceiptSha256))
  state = advance(state, verifyRegistration(state.latestControlReceiptSha256))
  state = advance(
    state,
    {
      ...beginConfirm(state.latestControlReceiptSha256),
      confirmJobStartedAtUnixSeconds: FUTURE_ROUND_TIME_UNIX_SECONDS + 10
    }
  )
  state = advance(
    state,
    {
      ...acceptPulse(state.latestControlReceiptSha256),
      pulseWaitStartedAtUnixSeconds: FUTURE_ROUND_TIME_UNIX_SECONDS + 10,
      verifiedAtUnixSeconds: FUTURE_ROUND_TIME_UNIX_SECONDS + 10,
      pulseWaitElapsedSeconds: 0
    }
  )
  expect(state._tag).toBe("PulseEligible")
})

it("accounts confirm command time with ceiling seconds and exactly 300 seconds of slack", () => {
  const state = throughConfirmRunning()
  const result = (
    postSeedWorkElapsedNanoseconds: number,
    commandElapsedSeconds: number
  ) =>
    advanceS2SConfirmatory(
      state,
      decodeEvent({
        ...recordCandidate(state.latestControlReceiptSha256),
        postSeedWorkElapsedNanoseconds,
        commandElapsedSeconds,
        pythonExecution: pythonExecution({
          operation: "confirm",
          inputRawBytesSha256: evidenceHash("numeric-confirm-request-raw"),
          outputRawBytesSha256: "3".repeat(64),
          requestDocumentSha256: evidenceHash("numeric-confirm-request-raw"),
          requestSelfSha256: "9".repeat(64),
          elapsedNanoseconds: postSeedWorkElapsedNanoseconds
        })
      })
    )

  expect(Either.isLeft(result(1, 80))).toBe(true)
  expect(Either.isRight(result(1, 81))).toBe(true)
  expect(Either.isRight(result(1, 381))).toBe(true)
  expect(Either.isLeft(result(1, 382))).toBe(true)

  expect(Either.isLeft(result(1_000_000_000, 80))).toBe(true)
  expect(Either.isRight(result(1_000_000_000, 81))).toBe(true)

  expect(Either.isLeft(result(1_000_000_001, 81))).toBe(true)
  expect(Either.isRight(result(1_000_000_001, 82))).toBe(true)
  expect(Either.isRight(result(1_000_000_001, 382))).toBe(true)
  expect(Either.isLeft(result(1_000_000_001, 383))).toBe(true)
})

it("rejects empty archives and largest members for every artifact role", () => {
  const predecessor = initialS2SConfirmatoryState().latestControlReceiptSha256
  const roleEvents = [
    verifyRegistration(predecessor),
    verifyCandidateArtifact(predecessor),
    verifyEvidenceArtifact(predecessor)
  ]

  for (const event of roleEvents) {
    for (const field of [
      "archiveSizeBytes",
      "largestMemberSizeBytes"
    ] as const) {
      expect(() =>
        decodeEvent({
          ...event,
          artifact: { ...event.artifact, [field]: 0 }
        })
      ).toThrow()
    }
  }
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
  expect(() =>
    decodeEvent({
      ...beginRegistration(initial.latestControlReceiptSha256),
      schemaVersion: "hswm-swm0w-s2s-confirmatory-control-event/v2"
    })
  ).toThrow()
  expect(() =>
    decodeEvent({
      ...beginRegistration(initial.latestControlReceiptSha256),
      workflowRunObservationReceiptSha256: undefined
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

it("reconstructs the exact four-file durable chronology through external final readback", () => {
  const { registration, candidate, adjudication, finalReadback } =
    healthyDurableChain()

  expect(registration.document.final_phase).toBe("Registering")
  expect(candidate.document.final_phase).toBe("CandidateProduced")
  expect(adjudication.document.final_phase).toBe("AdjudicationProduced")
  expect(finalReadback.document.final_phase).toBe(
    "EvidenceArtifactVerified"
  )
  expect([
    registration.document.event_count,
    candidate.document.event_count,
    adjudication.document.event_count,
    finalReadback.document.event_count
  ]).toEqual([1, 6, 9, 10])

  const reconstructed = rightOrThrow(
    reconstructS2SDurableJournalChain([
      registration.canonicalBytes,
      candidate.canonicalBytes,
      adjudication.canonicalBytes,
      finalReadback.canonicalBytes
    ])
  )
  expect(reconstructed.fileSha256).toBe(finalReadback.fileSha256)
  expect(reconstructed.state._tag).toBe("EvidenceArtifactVerified")
  if (reconstructed.state._tag === "EvidenceArtifactVerified") {
    expect(reconstructed.state.verdict).toBe("PASS")
  }
})

it("returns defensive durable snapshots and rejects oversized journal input", () => {
  const { registration } = healthyDurableChain()
  const exposedBytes = registration.canonicalBytes
  const exposedDocument = registration.document as unknown as {
    event_count: number
  }
  const exposedState = registration.state as unknown as { _tag: string }

  exposedBytes.fill(0)
  exposedDocument.event_count = 99
  exposedState._tag = "Voided"

  expect(rawS2SFileSha256(registration.canonicalBytes)).toBe(
    registration.fileSha256
  )
  expect(registration.document.event_count).toBe(1)
  expect(registration.state._tag).toBe("Registering")

  const oversized = reconstructS2SDurableJournalChain([
    new Uint8Array(S2S_DURABLE_JOURNAL_MAX_FILE_BYTES + 1)
  ])
  expect(Either.isLeft(oversized)).toBe(true)
  if (Either.isLeft(oversized)) {
    expect(oversized.left.reason).toBe("FILE_SIZE_INVALID")
  }
})

it("rejects detached descendants, valid predecessor forks, and self-hash drift", () => {
  const { registration, candidate } = healthyDurableChain()

  const detached = reconstructS2SDurableJournalChain([
    candidate.canonicalBytes
  ])
  expect(Either.isLeft(detached)).toBe(true)
  if (Either.isLeft(detached)) {
    expect(detached.left.reason).toBe("ROLE_ORDER_INVALID")
  }

  const events = healthyEventSequence()
  const forkedRegistration = rightOrThrow(
    buildS2SDurableJournal(
      "REGISTRATION_CARRIER",
      [],
      [
        {
          ...events[0],
          registrationJobId: REGISTER_JOB_ID + 1
        }
      ]
    )
  )
  const forkedChain = reconstructS2SDurableJournalChain([
    forkedRegistration.canonicalBytes,
    candidate.canonicalBytes
  ])
  expect(Either.isLeft(forkedChain)).toBe(true)
  if (Either.isLeft(forkedChain)) {
    expect(forkedChain.left.reason).toBe("PREDECESSOR_HASH_MISMATCH")
  }

  const wrongSelfHash = canonicalS2SControlJsonBytes({
    ...candidate.document,
    journal_sha256: "f".repeat(64)
  })
  expect(Either.isRight(wrongSelfHash)).toBe(true)
  if (Either.isLeft(wrongSelfHash)) return
  const selfHashDrift = reconstructS2SDurableJournalChain([
    registration.canonicalBytes,
    wrongSelfHash.right
  ])
  expect(Either.isLeft(selfHashDrift)).toBe(true)
  if (Either.isLeft(selfHashDrift)) {
    expect(selfHashDrift.left.reason).toBe("SELF_HASH_MISMATCH")
  }
})

it("keeps job completion evidence outside the artifacts produced by that job", () => {
  const { candidate, adjudication, finalReadback } = healthyDurableChain()

  expect(candidate.document.events.at(-1)?._tag).toBe(
    "RecordCandidateProduced"
  )
  expect(adjudication.document.events.at(-1)?._tag).toBe(
    "RecordAdjudicationProduced"
  )
  expect(finalReadback.document.events.at(-1)?._tag).toBe(
    "VerifyEvidenceArtifact"
  )

  const candidateProduced = candidate.document.events.at(-1)
  const adjudicationProduced = adjudication.document.events.at(-1)
  expect(
    candidateProduced !== undefined &&
      "jobElapsedSeconds" in candidateProduced
  ).toBe(false)
  expect(
    adjudicationProduced !== undefined &&
      "jobElapsedSeconds" in adjudicationProduced
  ).toBe(false)
})

it.effect("publishes immutable slots and recovers the exact chain after layer restart", () => {
  const temporaryRoot = mkdtempSync(join(tmpdir(), "hswm-s2s-durable-"))
  const storeRoot = join(temporaryRoot, "journal")
  const { registration, candidate, adjudication, finalReadback } =
    healthyDurableChain()

  const program = Effect.gen(function* () {
    const publications = yield* Effect.gen(function* () {
      const store = yield* S2SDurableJournalFileStore
      const empty = yield* store.recover
      expect(empty.exactJournals).toEqual([])
      expect(Option.isNone(empty.latest)).toBe(true)

      const copiedAtCallBoundary = Uint8Array.from(
        registration.canonicalBytes
      )
      const firstEffect = store.publishNext(copiedAtCallBoundary)
      copiedAtCallBoundary.fill(0)
      const first = yield* firstEffect
      const duplicate = yield* store.publishNext(
        registration.canonicalBytes
      )
      const second = yield* store.publishNext(candidate.canonicalBytes)
      const third = yield* store.publishNext(adjudication.canonicalBytes)
      const fourth = yield* store.publishNext(finalReadback.canonicalBytes)
      return { first, duplicate, second, third, fourth }
    }).pipe(Effect.provide(makeS2SDurableJournalFileStoreLayer(storeRoot)))

    expect(publications.first._tag).toBe("Published")
    expect(publications.duplicate._tag).toBe("AlreadyPresent")
    expect([
      publications.first.slot,
      publications.second.slot,
      publications.third.slot,
      publications.fourth.slot
    ]).toEqual([1, 2, 3, 4])

    const recovered = yield* Effect.gen(function* () {
      const store = yield* S2SDurableJournalFileStore
      return yield* store.recover
    }).pipe(Effect.provide(makeS2SDurableJournalFileStoreLayer(storeRoot)))
    expect(recovered.exactJournals).toHaveLength(4)
    const exposedFirstJournal = recovered.exactJournals[0]
    expect(exposedFirstJournal).toBeDefined()
    exposedFirstJournal?.fill(0)
    const defensiveFirstJournal = recovered.exactJournals[0]
    expect(defensiveFirstJournal).toBeDefined()
    if (defensiveFirstJournal !== undefined) {
      expect(rawS2SFileSha256(defensiveFirstJournal)).toBe(
        registration.fileSha256
      )
    }
    expect(Option.isSome(recovered.latest)).toBe(true)
    if (Option.isSome(recovered.latest)) {
      expect(recovered.latest.value.fileSha256).toBe(
        finalReadback.fileSha256
      )
      expect(recovered.latest.value.state._tag).toBe(
        "EvidenceArtifactVerified"
      )
    }
    for (let slot = 1; slot <= 4; slot += 1) {
      const mode = statSync(
        join(storeRoot, `control-journal-0${slot}.json`)
      ).mode
      expect(mode & 0o777).toBe(0o400)
    }
  })

  return program.pipe(
    Effect.ensuring(
      Effect.sync(() => rmSync(temporaryRoot, { force: true, recursive: true }))
    )
  )
})

it.effect("rejects oversized publication at the call boundary", () => {
  const temporaryRoot = mkdtempSync(join(tmpdir(), "hswm-s2s-publish-bound-"))
  const storeRoot = join(temporaryRoot, "journal")
  const program = Effect.gen(function* () {
    const result = yield* Effect.gen(function* () {
      const store = yield* S2SDurableJournalFileStore
      return yield* store
        .publishNext(
          new Uint8Array(S2S_DURABLE_JOURNAL_MAX_FILE_BYTES + 1)
        )
        .pipe(Effect.either)
    }).pipe(Effect.provide(makeS2SDurableJournalFileStoreLayer(storeRoot)))
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) {
      expect(result.left._tag).toBe("S2SDurableJournalFileStoreError")
      if (result.left._tag === "S2SDurableJournalFileStoreError") {
        expect(result.left.reason).toBe("FILE_TOO_LARGE")
      }
    }
  })
  return program.pipe(
    Effect.ensuring(
      Effect.sync(() => rmSync(temporaryRoot, { force: true, recursive: true }))
    )
  )
})

it.effect("does not promote an existing slot when directory sync stays unsupported", () => {
  const temporaryRoot = mkdtempSync(join(tmpdir(), "hswm-s2s-resync-"))
  const storeRoot = join(temporaryRoot, "journal")
  const { registration } = healthyDurableChain()

  const program = Effect.gen(function* () {
    const store = yield* S2SDurableJournalFileStore
    const first = yield* store.publishNext(registration.canonicalBytes)
    expect(first._tag).toBe("Published")

    const directoryHandle = yield* Effect.promise(() =>
      open(storeRoot, constants.O_RDONLY)
    )
    const fileHandlePrototype = Object.getPrototypeOf(directoryHandle) as {
      sync: () => Promise<void>
    }
    yield* Effect.promise(() => directoryHandle.close())
    const unsupported = Object.assign(new Error("synthetic fsync rejection"), {
      code: "ENOTSUP"
    })
    const syncSpy = vi
      .spyOn(fileHandlePrototype, "sync")
      .mockRejectedValue(unsupported)
    try {
      const duplicate = yield* store
        .publishNext(registration.canonicalBytes)
        .pipe(Effect.either)
      expect(Either.isLeft(duplicate)).toBe(true)
      if (
        Either.isLeft(duplicate) &&
        duplicate.left._tag === "S2SDurableJournalFileStoreError"
      ) {
        expect(duplicate.left.reason).toBe("ATOMIC_PUBLICATION_UNSUPPORTED")
      }
    } finally {
      syncSpy.mockRestore()
    }
  }).pipe(Effect.provide(makeS2SDurableJournalFileStoreLayer(storeRoot)))

  return program.pipe(
    Effect.ensuring(
      Effect.sync(() => rmSync(temporaryRoot, { force: true, recursive: true }))
    )
  )
})

it.effect("reconciles identical concurrent publication and rejects a valid fork", () => {
  const temporaryRoot = mkdtempSync(join(tmpdir(), "hswm-s2s-cas-"))
  const identicalRoot = join(temporaryRoot, "identical")
  const forkRoot = join(temporaryRoot, "fork")
  const { registration } = healthyDurableChain()
  const events = healthyEventSequence()
  const forkedRegistration = rightOrThrow(
    buildS2SDurableJournal(
      "REGISTRATION_CARRIER",
      [],
      [{ ...events[0], registrationJobId: REGISTER_JOB_ID + 1 }]
    )
  )

  const program = Effect.gen(function* () {
    const identical = yield* Effect.gen(function* () {
      const store = yield* S2SDurableJournalFileStore
      return yield* Effect.all(
        [
          store.publishNext(registration.canonicalBytes),
          store.publishNext(registration.canonicalBytes)
        ],
        { concurrency: 2 }
      )
    }).pipe(
      Effect.provide(makeS2SDurableJournalFileStoreLayer(identicalRoot))
    )
    expect(identical.map(({ _tag }) => _tag).sort()).toEqual([
      "AlreadyPresent",
      "Published"
    ])

    const divergent = yield* Effect.gen(function* () {
      const store = yield* S2SDurableJournalFileStore
      const outcomes = yield* Effect.all(
        [
          store.publishNext(registration.canonicalBytes).pipe(Effect.either),
          store
            .publishNext(forkedRegistration.canonicalBytes)
            .pipe(Effect.either)
        ],
        { concurrency: 2 }
      )
      const recovery = yield* store.recover
      return { outcomes, recovery }
    }).pipe(Effect.provide(makeS2SDurableJournalFileStoreLayer(forkRoot)))
    expect(divergent.outcomes.filter(Either.isRight)).toHaveLength(1)
    expect(divergent.outcomes.filter(Either.isLeft)).toHaveLength(1)
    const rejected = divergent.outcomes.find(Either.isLeft)
    expect(rejected?.left._tag).toBe("S2SDurableJournalFileStoreError")
    if (
      rejected !== undefined &&
      rejected.left._tag === "S2SDurableJournalFileStoreError"
    ) {
      expect(rejected.left.reason).toBe(
        "CONCURRENT_PUBLICATION_CONFLICT"
      )
    }
    expect(divergent.recovery.exactJournals).toHaveLength(1)
  })

  return program.pipe(
    Effect.ensuring(
      Effect.sync(() => rmSync(temporaryRoot, { force: true, recursive: true }))
    )
  )
})

it.effect("rejects symlink, gap, oversized, truncated, and relative-root recovery", () => {
  const temporaryRoot = mkdtempSync(join(tmpdir(), "hswm-s2s-recover-"))
  const { registration } = healthyDurableChain()
  const makeRoot = (name: string): string => {
    const root = join(temporaryRoot, name)
    mkdirSync(root, { mode: 0o700 })
    return root
  }
  const symlinkRoot = makeRoot("symlink")
  const externalPath = join(temporaryRoot, "external.txt")
  writeFileSync(externalPath, "unchanged\n", { mode: 0o600 })
  symlinkSync(externalPath, join(symlinkRoot, "control-journal-01.json"))

  const gapRoot = makeRoot("gap")
  writeFileSync(
    join(gapRoot, "control-journal-02.json"),
    registration.canonicalBytes,
    { mode: 0o400 }
  )
  const oversizedRoot = makeRoot("oversized")
  writeFileSync(
    join(oversizedRoot, "control-journal-01.json"),
    Buffer.alloc(S2S_DURABLE_JOURNAL_MAX_FILE_BYTES + 1),
    { mode: 0o400 }
  )
  const truncatedRoot = makeRoot("truncated")
  writeFileSync(
    join(truncatedRoot, "control-journal-01.json"),
    registration.canonicalBytes.subarray(
      0,
      registration.canonicalBytes.byteLength - 1
    ),
    { mode: 0o400 }
  )

  const recover = (root: string) =>
    Effect.gen(function* () {
      const store = yield* S2SDurableJournalFileStore
      return yield* store.recover
    }).pipe(
      Effect.provide(makeS2SDurableJournalFileStoreLayer(root)),
      Effect.either
    )

  const program = Effect.gen(function* () {
    const symlinked = yield* recover(symlinkRoot)
    const gap = yield* recover(gapRoot)
    const oversized = yield* recover(oversizedRoot)
    const truncated = yield* recover(truncatedRoot)
    const relative = yield* recover("relative-journal-root")

    expect(Either.isLeft(symlinked)).toBe(true)
    expect(Either.isLeft(gap)).toBe(true)
    expect(Either.isLeft(oversized)).toBe(true)
    expect(Either.isLeft(truncated)).toBe(true)
    expect(Either.isLeft(relative)).toBe(true)
    if (Either.isLeft(symlinked)) {
      expect(symlinked.left._tag).toBe(
        "S2SDurableJournalFileStoreError"
      )
      expect(symlinked.left.reason).toBe("FILE_TYPE_INVALID")
    }
    if (Either.isLeft(gap)) expect(gap.left.reason).toBe("SLOT_GAP")
    if (Either.isLeft(oversized)) {
      expect(oversized.left.reason).toBe("FILE_TOO_LARGE")
    }
    if (Either.isLeft(truncated)) {
      expect(truncated.left.reason).toBe("CANONICAL_BYTES_DRIFT")
    }
    if (Either.isLeft(relative)) {
      expect(relative.left.reason).toBe("ROOT_UNSAFE")
    }
    expect(readFileSync(externalPath, "utf8")).toBe("unchanged\n")
  })

  return program.pipe(
    Effect.ensuring(
      Effect.sync(() => rmSync(temporaryRoot, { force: true, recursive: true }))
    )
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

it("rejects forged authority receipts, replay drift, and Python evidence drift", () => {
  const waiting = throughConfirmWaiting()
  const signatureDrift = advanceS2SConfirmatory(
    waiting,
    decodeEvent({
      ...acceptPulse(waiting.latestControlReceiptSha256),
      verifiedSignatureHex: `${SIGNATURE.slice(0, -1)}8`
    })
  )
  expect(Either.isLeft(signatureDrift)).toBe(true)
  if (Either.isLeft(signatureDrift)) {
    expect(signatureDrift.left._tag).toBe("S2SOperationalPolicyViolation")
    if (signatureDrift.left._tag === "S2SOperationalPolicyViolation") {
      expect(signatureDrift.left.reason).toBe("PULSE_BINDING_MISMATCH")
    }
  }

  const running = throughConfirmRunning()
  const candidate = recordCandidate(running.latestControlReceiptSha256)
  const pythonDrift = advanceS2SConfirmatory(
    running,
    decodeEvent({
      ...candidate,
      pythonExecution: pythonExecution({
        operation: "confirm",
        inputRawBytesSha256: evidenceHash("numeric-confirm-request-raw"),
        outputRawBytesSha256: "6".repeat(64),
        requestDocumentSha256: evidenceHash("numeric-confirm-request-raw"),
        requestSelfSha256: "9".repeat(64),
        elapsedNanoseconds: 90_000_000_000
      })
    })
  )
  expect(Either.isLeft(pythonDrift)).toBe(true)
  if (
    Either.isLeft(pythonDrift) &&
    pythonDrift.left._tag === "S2SOperationalPolicyViolation"
  ) {
    expect(pythonDrift.left.reason).toBe(
      "PYTHON_EXECUTION_EVIDENCE_MISMATCH"
    )
  }

  let state = throughCandidateProduced()
  const candidateEvidence = verifyCandidateArtifact(
    state.latestControlReceiptSha256
  )
  const wrongName = advanceS2SConfirmatory(
    state,
    decodeEvent({
      ...candidateEvidence,
      artifact: { ...candidateEvidence.artifact, artifactName: "candidate" }
    })
  )
  expect(Either.isLeft(wrongName)).toBe(true)
  if (
    Either.isLeft(wrongName) &&
    wrongName.left._tag === "S2SOperationalPolicyViolation"
  ) {
    expect(wrongName.left.reason).toBe("ARCHIVE_POLICY_MISMATCH")
  }

  state = advance(state, candidateEvidence)
  if (state._tag !== "CandidateArtifactVerified") return
  const adjudicationStart = beginAdjudication(
    state.latestControlReceiptSha256
  )
  const reusedReadback = advanceS2SConfirmatory(
    state,
    decodeEvent({
      ...adjudicationStart,
      candidateArtifactRequeryObservationReceiptSha256:
        state.candidateArtifact
          .candidateArtifactFirstApiObservationReceiptSha256
    })
  )
  expect(Either.isLeft(reusedReadback)).toBe(true)
  if (
    Either.isLeft(reusedReadback) &&
    reusedReadback.left._tag === "S2SOperationalPolicyViolation"
  ) {
    expect(reusedReadback.left.reason).toBe("GITHUB_OBSERVATION_MISMATCH")
  }

  state = advance(state, adjudicationStart)
  if (state._tag !== "Adjudicating") return
  const adjudication = recordAdjudication(state.latestControlReceiptSha256)
  const replayDrift = advanceS2SConfirmatory(
    state,
    decodeEvent({
      ...adjudication,
      drandReplayStableProjectionSha256: evidenceHash(
        "different-drand-stable-projection"
      )
    })
  )
  expect(Either.isLeft(replayDrift)).toBe(true)
  if (
    Either.isLeft(replayDrift) &&
    replayDrift.left._tag === "S2SOperationalPolicyViolation"
  ) {
    expect(replayDrift.left.reason).toBe("DRAND_REPLAY_MISMATCH")
  }

  state = advance(state, adjudication)
  if (state._tag !== "AdjudicationProduced") return
  const staleFinalization = advanceS2SConfirmatory(
    state,
    decodeEvent({
      ...verifyEvidenceArtifact(state.latestControlReceiptSha256),
      workflowRunCompletedObservationReceiptSha256:
        state.adjudication.workflowRunObservationReceiptSha256
    })
  )
  expect(Either.isLeft(staleFinalization)).toBe(true)
  if (
    Either.isLeft(staleFinalization) &&
    staleFinalization.left._tag === "S2SOperationalPolicyViolation"
  ) {
    expect(staleFinalization.left.reason).toBe(
      "FINALIZATION_OBSERVATION_MISMATCH"
    )
  }
})

it("maps a run-bound failure to terminal VOID with no retry path", () => {
  const running = throughConfirmRunning()
  const voided = advance(
    running,
    operationalVoid(
      running.latestControlReceiptSha256,
      CONFIRM_JOB_ID,
      "CONFIRM_JOB_DID_NOT_COMPLETE_SUCCESSFULLY"
    )
  )
  expect(voided._tag).toBe("Voided")
  if (voided._tag !== "Voided") return
  expect(voided.retryAllowed).toBe(false)
  expect(voided.candidateConsumable).toBe(false)
  expect(voided.lastAcceptedPhase).toBe("ConfirmRunning")
  expect(voided.failedJob).toBe("CONFIRM")
  expect(voided.workflowJobId).toBe(CONFIRM_JOB_ID)

  const retry = advanceS2SConfirmatory(
    voided,
    decodeEvent(recordCandidate(voided.latestControlReceiptSha256))
  )
  expect(Either.isLeft(retry)).toBe(true)
})

it("records a caller-supplied root VOID without inventing BeginRegistration", () => {
  const initial = initialS2SConfirmatoryState()
  const rootVoidEvent = decodeEvent(
    operationalVoid(
      initial.latestControlReceiptSha256,
      REGISTER_JOB_ID,
      "REGISTER_JOB_DID_NOT_COMPLETE_SUCCESSFULLY"
    )
  )
  const rootVoid = rightOrThrow(
    buildS2SDurableJournal("OPERATIONAL_VOID", [], [rootVoidEvent])
  )
  expect(rootVoid.document.event_count).toBe(1)
  expect(rootVoid.document.events[0]?._tag).toBe("RecordOperationalVoid")
  expect(rootVoid.state._tag).toBe("Voided")
  if (rootVoid.state._tag !== "Voided") return
  expect(rootVoid.state.lastAcceptedPhase).toBe("Prepared")
  expect(rootVoid.state.failedJob).toBe("REGISTER")

  const wrongReason = advanceS2SConfirmatory(
    initial,
    decodeEvent(
      operationalVoid(
        initial.latestControlReceiptSha256,
        REGISTER_JOB_ID,
        "REGISTRATION_ARTIFACT_UNAVAILABLE"
      )
    )
  )
  expect(Either.isLeft(wrongReason)).toBe(true)

  const began = advance(
    initial,
    beginRegistration(initial.latestControlReceiptSha256)
  )
  const synthetic = buildS2SDurableJournal(
    "OPERATIONAL_VOID",
    [],
    [
      beginRegistration(initial.latestControlReceiptSha256),
      operationalVoid(
        began.latestControlReceiptSha256,
        REGISTER_JOB_ID,
        "REGISTER_JOB_DID_NOT_COMPLETE_SUCCESSFULLY"
      )
    ]
  )
  expect(Either.isLeft(synthetic)).toBe(true)

  const successor = buildS2SDurableJournal(
    "REGISTRATION_CARRIER",
    [rootVoid.canonicalBytes],
    [beginRegistration(rootVoid.state.latestControlReceiptSha256)]
  )
  expect(Either.isLeft(successor)).toBe(true)
})

it("binds caller-supplied stage VOID reasons to the declared failed job", () => {
  const candidateProduced = throughCandidateProduced()
  const confirmFailed = advance(
    candidateProduced,
    operationalVoid(
      candidateProduced.latestControlReceiptSha256,
      CONFIRM_JOB_ID,
      "CONFIRM_JOB_DID_NOT_COMPLETE_SUCCESSFULLY"
    )
  )
  expect(confirmFailed._tag).toBe("Voided")

  let candidateVerified = candidateProduced
  candidateVerified = advance(
    candidateVerified,
    verifyCandidateArtifact(candidateVerified.latestControlReceiptSha256)
  )
  const beforeAdjudication = advance(
    candidateVerified,
    operationalVoid(
      candidateVerified.latestControlReceiptSha256,
      ADJUDICATION_JOB_ID,
      "ADJUDICATION_JOB_DID_NOT_COMPLETE_SUCCESSFULLY"
    )
  )
  expect(beforeAdjudication._tag).toBe("Voided")
  if (beforeAdjudication._tag === "Voided") {
    expect(beforeAdjudication.lastAcceptedPhase).toBe(
      "CandidateArtifactVerified"
    )
    expect(beforeAdjudication.failedJob).toBe("ADJUDICATE")
  }

  let adjudicating = candidateVerified
  adjudicating = advance(
    adjudicating,
    beginAdjudication(adjudicating.latestControlReceiptSha256)
  )
  const prematureUnavailable = advanceS2SConfirmatory(
    adjudicating,
    decodeEvent(
      operationalVoid(
        adjudicating.latestControlReceiptSha256,
        ADJUDICATION_JOB_ID,
        "ADJUDICATION_ARTIFACT_UNAVAILABLE"
      )
    )
  )
  expect(Either.isLeft(prematureUnavailable)).toBe(true)
})

it("reconstructs VOID only after the exact durable prefix that existed", () => {
  const events = healthyEventSequence()
  const registration = rightOrThrow(
    buildS2SDurableJournal("REGISTRATION_CARRIER", [], events.slice(0, 1))
  )
  const registrationVoidEvent = operationalVoid(
    registration.state.latestControlReceiptSha256,
    REGISTER_JOB_ID,
    "REGISTRATION_ARTIFACT_UNAVAILABLE"
  )
  const registrationVoid = rightOrThrow(
    buildS2SDurableJournal(
      "OPERATIONAL_VOID",
      [registration.canonicalBytes],
      [registrationVoidEvent]
    )
  )
  expect(
    Either.isRight(
      reconstructS2SDurableJournalChain([
        registration.canonicalBytes,
        registrationVoid.canonicalBytes
      ])
    )
  ).toBe(true)

  const candidate = rightOrThrow(
    buildS2SDurableJournal(
      "CANDIDATE_CARRIER",
      [registration.canonicalBytes],
      events.slice(1, 6)
    )
  )
  const candidateVoid = rightOrThrow(
    buildS2SDurableJournal(
      "OPERATIONAL_VOID",
      [registration.canonicalBytes, candidate.canonicalBytes],
      [
        operationalVoid(
          candidate.state.latestControlReceiptSha256,
          CONFIRM_JOB_ID,
          "CONFIRM_JOB_DID_NOT_COMPLETE_SUCCESSFULLY"
        )
      ]
    )
  )
  expect(candidateVoid.document.event_count).toBe(7)

  const adjudication = rightOrThrow(
    buildS2SDurableJournal(
      "ADJUDICATION_CARRIER",
      [registration.canonicalBytes, candidate.canonicalBytes],
      events.slice(6, 9)
    )
  )
  const adjudicationVoid = rightOrThrow(
    buildS2SDurableJournal(
      "OPERATIONAL_VOID",
      [
        registration.canonicalBytes,
        candidate.canonicalBytes,
        adjudication.canonicalBytes
      ],
      [
        operationalVoid(
          adjudication.state.latestControlReceiptSha256,
          ADJUDICATION_JOB_ID,
          "ADJUDICATION_JOB_DID_NOT_COMPLETE_SUCCESSFULLY"
        )
      ]
    )
  )
  expect(adjudicationVoid.document.event_count).toBe(10)
  expect(
    Either.isRight(
      reconstructS2SDurableJournalChain([
        registration.canonicalBytes,
        candidate.canonicalBytes,
        adjudication.canonicalBytes,
        adjudicationVoid.canonicalBytes
      ])
    )
  ).toBe(true)
})

it("rejects a VOID journal that skips a required candidate carrier", () => {
  const events = healthyEventSequence()
  const registration = rightOrThrow(
    buildS2SDurableJournal("REGISTRATION_CARRIER", [], events.slice(0, 1))
  )
  let state = initialS2SConfirmatoryState()
  for (const event of events.slice(0, 7)) state = advance(state, event)
  expect(state._tag).toBe("CandidateArtifactVerified")

  const skippedCandidate = buildS2SDurableJournal(
    "OPERATIONAL_VOID",
    [registration.canonicalBytes],
    [
      ...events.slice(1, 7),
      operationalVoid(
        state.latestControlReceiptSha256,
        ADJUDICATION_JOB_ID,
        "ADJUDICATION_JOB_DID_NOT_COMPLETE_SUCCESSFULLY"
      )
    ]
  )
  expect(Either.isLeft(skippedCandidate)).toBe(true)
  if (Either.isLeft(skippedCandidate)) {
    expect(skippedCandidate.left.reason).toBe("ROLE_ORDER_INVALID")
  }
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
