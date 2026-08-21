import { expect, it } from "@effect/vitest"
import { Either, Schema } from "effect"

import {
  canonicalS2SControlJsonBytes,
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "../src/s2s-canonical.js"
import {
  S2SConfirmatoryEventSchema,
  S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
  S2S_CONFIRMATORY_EXPERIMENT_ID,
  S2S_CONFIRMATORY_RESOURCE_POLICY_SHA256,
  S2S_PILOT_ADOPTION_RECEIPT_SHA256,
  S2S_PROTOCOL_CONFIG_RECEIPT_SHA256,
  S2SSha256Schema,
  advanceS2SConfirmatory,
  initialS2SConfirmatoryState,
  type S2SArtifactEvidence,
  type S2SConfirmatoryEvent,
  type S2SConfirmatoryState
} from "../src/s2s-confirmatory.js"
import {
  prepareS2SAdjudicationCarrier,
  prepareS2SCandidateCarrier,
  prepareS2SRegistrationCarrier,
  type S2SAdjudicationStageEvents,
  type S2SCandidateStageEvents,
  type S2SCarrierReadback,
  type S2SRegistrationStageEvents,
  type S2SUploadMember
} from "../src/s2s-job-sequence.js"
import { buildS2STestActionZip } from "./support/s2s-action-zip.js"

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
const FUTURE_BEACON_ROUND = 1_000
const FUTURE_ROUND_TIME_UNIX_SECONDS = 1_692_806_364
const WORKFLOW_CREATED_AT_UNIX_SECONDS =
  FUTURE_ROUND_TIME_UNIX_SECONDS - 200
const REGISTRATION_STARTED_AT_UNIX_SECONDS =
  FUTURE_ROUND_TIME_UNIX_SECONDS - 190
const REGISTRATION_COMPLETED_AT_UNIX_SECONDS =
  FUTURE_ROUND_TIME_UNIX_SECONDS - 90
const CONFIRM_STARTED_AT_UNIX_SECONDS =
  FUTURE_ROUND_TIME_UNIX_SECONDS - 80
const CONFIRM_COMPLETED_AT_UNIX_SECONDS = CONFIRM_STARTED_AT_UNIX_SECONDS + 200
const ADJUDICATION_STARTED_AT_UNIX_SECONDS =
  CONFIRM_COMPLETED_AT_UNIX_SECONDS + 10
const NUMERIC_CONFIRM_REQUEST_SHA256 = "9".repeat(64)
const NUMERIC_CANDIDATE_RECEIPT_SHA256 = "8".repeat(64)
const encoder = new TextEncoder()

const decodeEvent = Schema.decodeUnknownSync(S2SConfirmatoryEventSchema, {
  onExcessProperty: "error"
})

const requireRight = <Value, Error>(
  either: Either.Either<Value, Error>
): Value => {
  if (Either.isLeft(either)) throw either.left
  return either.right
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

const advance = (
  state: S2SConfirmatoryState,
  event: S2SConfirmatoryEvent
): S2SConfirmatoryState =>
  requireRight(advanceS2SConfirmatory(state, event))

const beginRegistration = (predecessor: string) => {
  const event = decodeEvent({
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
    sourceCommitSha: SOURCE_A,
    preregistrationCommitSha: REGISTRATION_B,
    beaconId: "quicknet",
    beaconChainHashHex: CHAIN_HASH,
    futureBeaconRound: FUTURE_BEACON_ROUND,
    futureRoundCommitmentSelfHashSha256: FUTURE_COMMITMENT,
    declaredPulseLeadSeconds: 200
  })
  if (event._tag !== "BeginRegistration") throw new Error("wrong event")
  return event
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
    registrationJobCompletedAtUnixSeconds: REGISTRATION_COMPLETED_AT_UNIX_SECONDS,
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
    verifiedRandomnessHex: RANDOMNESS,
    externalSeedHex: EXTERNAL_SEED,
    verifierReceiptSha256: "2".repeat(64),
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
    attempt: attempt(),
    candidateArtifactId: candidateArtifact.artifactId,
    expectedCandidateArchiveSha256: candidateArtifact.downloadedArchiveSha256,
    requeriedApiDigestSha256: candidateArtifact.apiDigestSha256,
    redownloadedCandidateArchiveSha256:
      candidateArtifact.downloadedArchiveSha256
  })
  if (event._tag !== "BeginAdjudication") throw new Error("wrong event")
  return event
}

const makeNumericAdjudication = (candidateSha256: string) => {
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
    candidate_document_sha256: candidateSha256,
    candidate_receipt_sha256: NUMERIC_CANDIDATE_RECEIPT_SHA256,
    canonical_encoding: "ASCII_CANONICAL_UTF8_JSON_PLUS_SINGLE_LF",
    claim_boundary: "NUMERIC_ONLY_NO_EVIDENCE_VERDICT_OR_CHRONOLOGY_CLAIM",
    confirm_request_sha256: NUMERIC_CONFIRM_REQUEST_SHA256,
    numeric_replay: replay,
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
    candidateOnly: true
  })
  if (event._tag !== "RecordAdjudicationProduced") {
    throw new Error("wrong event")
  }
  return event
}

const artifactFromArchive = (
  artifactName: string,
  artifactId: number,
  archiveBytes: Uint8Array,
  members: ReadonlyArray<{ readonly byteLength: number }>
): S2SArtifactEvidence => {
  const largestMemberSizeBytes = Math.max(
    ...members.map((member) => member.byteLength)
  )
  const digest = S2SSha256Schema.make(rawS2SFileSha256(archiveBytes))
  const carrier = decodeEvent({
    schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
    _tag: "VerifyRegistration",
    binding: binding(S2S_PILOT_ADOPTION_RECEIPT_SHA256),
    workflowRunId: WORKFLOW_RUN_ID,
    registrationJobId: REGISTER_JOB_ID,
    workflowRunAttempt: 1,
    workflowHeadSha: REGISTRATION_B,
    registrationJobCompletedAtUnixSeconds: REGISTRATION_COMPLETED_AT_UNIX_SECONDS,
    sourceIsAncestorOfPreregistration: true,
    preregistrationIsDirectChildOfSource: true,
    numericContinuityManifestSha256AtSource: "e".repeat(64),
    numericContinuityManifestSha256AtPreregistration: "e".repeat(64),
    numericContinuityPathsByteEqual: true,
    jobElapsedSeconds: 100,
    artifact: {
      artifactName,
      artifactId,
      artifactCount: 1,
      archiveSizeBytes: archiveBytes.byteLength,
      largestMemberSizeBytes,
      compressionLevel: 0,
      retentionDays: 90,
      overwrite: false,
      apiDigestSha256: digest,
      downloadedArchiveSha256: digest
    },
    archiveMembers: ["control_receipt.json"]
  })
  if (carrier._tag !== "VerifyRegistration") throw new Error("wrong event")
  return carrier.artifact
}

const zipMembers = (
  members: ReadonlyArray<S2SUploadMember<string>>
): ReadonlyArray<{ readonly name: string; readonly bytes: Uint8Array }> =>
  members.map((member) => ({ name: member.name, bytes: member.readBytes() }))

const makeHealthyScenario = () => {
  let state = initialS2SConfirmatoryState()
  const registrationEvent = beginRegistration(state.latestControlReceiptSha256)
  const registrationEvents: S2SRegistrationStageEvents = [registrationEvent]
  const registration = requireRight(
    prepareS2SRegistrationCarrier(registrationEvents)
  )
  state = registration.carrier.state
  const registrationArchive = buildS2STestActionZip(
    zipMembers(registration.members)
  )
  const registrationArtifact = artifactFromArchive(
    "s2s-registration",
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
  const candidateEvents: S2SCandidateStageEvents = [
    registrationVerified,
    confirmBegan,
    pulse,
    numericBegan,
    candidateProduced
  ]
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
    "s2s-candidate",
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
  const adjudicationEvents: S2SAdjudicationStageEvents = [
    candidateVerified,
    adjudicationBegan,
    adjudicationProduced
  ]
  const adjudication = requireRight(
    prepareS2SAdjudicationCarrier({
      registrationReadback,
      candidateReadback,
      numericAdjudicationBytes: numericAdjudication.bytes,
      events: adjudicationEvents
    })
  )
  return {
    registration,
    registrationReadback,
    candidate,
    candidateReadback,
    candidateEvents,
    numericCandidateBytes,
    adjudication,
    adjudicationEvents,
    numericAdjudication
  }
}

it("composes exact 1→6→9 candidate-only carriers without exposing a verdict", () => {
  const scenario = makeHealthyScenario()
  expect(scenario.registration.carrier.document.event_count).toBe(1)
  expect(scenario.candidate.carrier.document.event_count).toBe(6)
  expect(scenario.adjudication.carrier.document.event_count).toBe(9)
  expect(scenario.registration.carrier.state._tag).toBe("Registering")
  expect(scenario.candidate.carrier.state._tag).toBe("CandidateProduced")
  expect(scenario.adjudication.carrier.state._tag).toBe(
    "AdjudicationProduced"
  )
  expect("verdict" in scenario.candidate).toBe(false)
  expect("verdict" in scenario.adjudication).toBe(false)
  expect(
    scenario.candidate.carrier.document.events.some(
      (event) => event._tag === "VerifyCandidateArtifact"
    )
  ).toBe(false)
  expect(
    scenario.adjudication.carrier.document.events.some(
      (event) => event._tag === "VerifyEvidenceArtifact"
    )
  ).toBe(false)
})

it("rejects API/readback evidence drift before carrier hydration", () => {
  const scenario = makeHealthyScenario()
  const result = prepareS2SCandidateCarrier({
    registrationReadback: {
      ...scenario.registrationReadback,
      artifact: {
        ...scenario.registrationReadback.artifact,
        downloadedArchiveSha256: S2SSha256Schema.make("f".repeat(64))
      }
    },
    numericCandidateBytes: scenario.numericCandidateBytes,
    events: scenario.candidateEvents
  })
  expect(Either.isLeft(result)).toBe(true)
  if (Either.isLeft(result)) {
    expect(result.left._tag).toBe("S2SJobSequenceError")
  }
})

it("rejects a replaced control member even when the replacement ZIP is hash-bound", () => {
  const scenario = makeHealthyScenario()
  const replacementArchive = buildS2STestActionZip([
    {
      name: "control_receipt.json",
      bytes: scenario.registration.members[0].readBytes()
    },
    {
      name: "numeric_candidate.json",
      bytes: scenario.candidate.members[1].readBytes()
    }
  ])
  const replacementArtifact = artifactFromArchive(
    "s2s-candidate-replaced",
    4,
    replacementArchive,
    [
      { byteLength: scenario.registration.members[0].byteLength },
      scenario.candidate.members[1]
    ]
  )
  let state = scenario.candidate.carrier.state
  const candidateVerified = verifyCandidate(
    state.latestControlReceiptSha256,
    replacementArtifact,
    rawS2SFileSha256(scenario.numericCandidateBytes)
  )
  state = advance(state, candidateVerified)
  const adjudicationBegan = beginAdjudication(
    state.latestControlReceiptSha256,
    replacementArtifact
  )
  state = advance(state, adjudicationBegan)
  const adjudicationProduced = recordAdjudication(
    state.latestControlReceiptSha256,
    replacementArtifact,
    rawS2SFileSha256(scenario.numericCandidateBytes),
    scenario.numericAdjudication.bytes,
    scenario.numericAdjudication.receiptSha256
  )
  const events: S2SAdjudicationStageEvents = [
    candidateVerified,
    adjudicationBegan,
    adjudicationProduced
  ]
  const result = prepareS2SAdjudicationCarrier({
    registrationReadback: scenario.registrationReadback,
    candidateReadback: {
      artifact: replacementArtifact,
      archiveBytes: replacementArchive
    },
    numericAdjudicationBytes: scenario.numericAdjudication.bytes,
    events
  })
  expect(Either.isLeft(result)).toBe(true)
  if (Either.isLeft(result)) {
    expect(result.left._tag).toBe("S2SDurableJournalError")
  }
})

it("rejects adjudication byte drift before carrier emission", () => {
  const scenario = makeHealthyScenario()
  const mutatedAdjudication = Uint8Array.from(scenario.numericAdjudication.bytes)
  mutatedAdjudication[0] = 0x20
  const result = prepareS2SAdjudicationCarrier({
    registrationReadback: scenario.registrationReadback,
    candidateReadback: scenario.candidateReadback,
    numericAdjudicationBytes: mutatedAdjudication,
    events: scenario.adjudicationEvents
  })
  expect(Either.isLeft(result)).toBe(true)
})

it("rejects a valid event prefix followed by an extra event at every stage", () => {
  const scenario = makeHealthyScenario()
  const registration = prepareS2SRegistrationCarrier([
    scenario.registration.carrier.document.events[0],
    scenario.registration.carrier.document.events[0]
  ] as unknown as S2SRegistrationStageEvents)
  const candidate = prepareS2SCandidateCarrier({
    registrationReadback: scenario.registrationReadback,
    numericCandidateBytes: scenario.numericCandidateBytes,
    events: [
      ...scenario.candidateEvents,
      scenario.candidateEvents[0]
    ] as unknown as S2SCandidateStageEvents
  })
  const adjudication = prepareS2SAdjudicationCarrier({
    registrationReadback: scenario.registrationReadback,
    candidateReadback: scenario.candidateReadback,
    numericAdjudicationBytes: scenario.numericAdjudication.bytes,
    events: [
      ...scenario.adjudicationEvents,
      scenario.adjudicationEvents[0]
    ] as unknown as S2SAdjudicationStageEvents
  })
  expect(Either.isLeft(registration)).toBe(true)
  expect(Either.isLeft(candidate)).toBe(true)
  expect(Either.isLeft(adjudication)).toBe(true)
  if (
    Either.isLeft(registration) &&
    registration.left._tag === "S2SJobSequenceError"
  ) {
    expect(registration.left.reason).toBe("EVENT_SEQUENCE_INVALID")
  }
  if (Either.isLeft(candidate) && candidate.left._tag === "S2SJobSequenceError") {
    expect(candidate.left.reason).toBe("EVENT_SEQUENCE_INVALID")
  }
  if (
    Either.isLeft(adjudication) &&
    adjudication.left._tag === "S2SJobSequenceError"
  ) {
    expect(adjudication.left.reason).toBe("EVENT_SEQUENCE_INVALID")
  }
})

it("copies accepted numeric and carrier bytes at every output boundary", () => {
  const scenario = makeHealthyScenario()
  const numericInput = Uint8Array.from(scenario.numericCandidateBytes)
  const produced = requireRight(
    prepareS2SCandidateCarrier({
      registrationReadback: scenario.registrationReadback,
      numericCandidateBytes: numericInput,
      events: scenario.candidateEvents
    })
  )
  const expectedNumericSha256 = produced.members[1].rawBytesSha256
  const firstNumericRead = produced.members[1].readBytes()
  const firstCarrierRead = produced.carrier.canonicalBytes

  numericInput.fill(0)
  firstNumericRead.fill(0)
  firstCarrierRead.fill(0)

  expect(rawS2SFileSha256(produced.members[1].readBytes())).toBe(
    expectedNumericSha256
  )
  expect(rawS2SFileSha256(produced.members[0].readBytes())).toBe(
    produced.members[0].rawBytesSha256
  )
  expect(rawS2SFileSha256(produced.carrier.canonicalBytes)).toBe(
    produced.carrier.fileSha256
  )
})

it("rejects an oversized adjudication member before copying it", () => {
  const scenario = makeHealthyScenario()
  const result = prepareS2SAdjudicationCarrier({
    registrationReadback: scenario.registrationReadback,
    candidateReadback: scenario.candidateReadback,
    numericAdjudicationBytes: new Uint8Array(4 * 1_048_576 + 1),
    events: scenario.adjudicationEvents
  })
  expect(Either.isLeft(result)).toBe(true)
  if (Either.isLeft(result)) {
    expect(result.left._tag).toBe("S2SJobSequenceError")
    if (result.left._tag === "S2SJobSequenceError") {
      expect(result.left.reason).toBe("MEMBER_METRICS_MISMATCH")
    }
  }
})
