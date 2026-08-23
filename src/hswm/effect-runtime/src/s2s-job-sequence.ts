import { Data, Either, Schema } from "effect"

import { rawS2SFileSha256 } from "./s2s-canonical.js"
import {
  S2SConfirmatoryEventSchema,
  S2S_CONFIRMATORY_POLICY,
  S2S_REGISTRATION_ARCHIVE_EXACT_MEMBERS,
  S2SSha256Schema,
  type S2SArtifactEvidence,
  type S2SConfirmatoryEvent,
  type S2SSha256
} from "./s2s-confirmatory.js"
import {
  S2S_DURABLE_JOURNAL_MAX_FILE_BYTES,
  S2SDurableJournalError,
  buildS2SDurableJournal,
  reconstructS2SDurableJournalChain,
  type S2SDurableJournalSnapshot
} from "./s2s-durable.js"
import {
  NumericAdjudicationProjectionError,
  OpaqueNumericFileError,
  makeOpaqueNumericFile,
  projectOpaqueNumericAdjudication
} from "./s2s-orchestration.js"
import { S2S_NUMERIC_ADJUDICATION_MAX_BYTES } from "./s2s-live-python.js"
import {
  S2SArtifactZipValidationError,
  validateS2SArtifactZip,
  type S2SExpectedZipMember,
  type S2SValidatedArtifactZip,
  type S2SValidatedZipMember
} from "./s2s-zip.js"

type EventOf<Tag extends S2SConfirmatoryEvent["_tag"]> = Extract<
  S2SConfirmatoryEvent,
  { readonly _tag: Tag }
>

export type S2SRegistrationStageEvents = readonly [
  EventOf<"BeginRegistration">
]

export type S2SCandidateStageEvents = readonly [
  EventOf<"VerifyRegistration">,
  EventOf<"BeginConfirm">,
  EventOf<"AcceptVerifiedPulse">,
  EventOf<"BeginNumericConfirm">,
  EventOf<"RecordCandidateProduced">
]

export type S2SAdjudicationStageEvents = readonly [
  EventOf<"VerifyCandidateArtifact">,
  EventOf<"BeginAdjudication">,
  EventOf<"RecordAdjudicationProduced">
]

export interface S2SCarrierReadback {
  readonly artifact: S2SArtifactEvidence
  readonly archiveBytes: Uint8Array
}

export interface S2SUploadMember<Name extends string> {
  readonly name: Name
  readonly byteLength: number
  readonly rawBytesSha256: S2SSha256
  readonly readBytes: () => Uint8Array
}

export interface S2SRegistrationCarrierPlan {
  readonly _tag: "RegistrationCarrierReady"
  readonly carrier: S2SDurableJournalSnapshot
  readonly members: readonly [S2SUploadMember<"control_receipt.json">]
}

export interface S2SCandidateCarrierPlan {
  readonly _tag: "CandidateCarrierReady"
  readonly carrier: S2SDurableJournalSnapshot
  readonly members: readonly [
    S2SUploadMember<"control_receipt.json">,
    S2SUploadMember<"numeric_candidate.json">
  ]
}

export interface S2SAdjudicationCarrierPlan {
  readonly _tag: "AdjudicationCarrierReady"
  readonly carrier: S2SDurableJournalSnapshot
  readonly members: readonly [
    S2SUploadMember<"control_receipt.json">,
    S2SUploadMember<"numeric_adjudication.json">
  ]
}

export class S2SJobSequenceError extends Data.TaggedError(
  "S2SJobSequenceError"
)<{
  readonly stage: "REGISTER" | "CONFIRM" | "ADJUDICATE"
  readonly reason:
    | "ARTIFACT_EVIDENCE_MISMATCH"
    | "EVENT_SEQUENCE_INVALID"
    | "MEMBER_METRICS_MISMATCH"
    | "MEMBER_MISSING"
    | "NUMERIC_PROJECTION_MISMATCH"
    | "PREDECESSOR_PHASE_MISMATCH"
  readonly detail: string
}> {}

export type S2SJobSequenceFailure =
  | S2SJobSequenceError
  | S2SArtifactZipValidationError
  | S2SDurableJournalError
  | OpaqueNumericFileError
  | NumericAdjudicationProjectionError

interface ValidatedCarrierReadback {
  readonly artifact: S2SArtifactEvidence
  readonly archive: S2SValidatedArtifactZip
}

const sequenceError = (
  stage: S2SJobSequenceError["stage"],
  reason: S2SJobSequenceError["reason"],
  detail: string
): S2SJobSequenceError => new S2SJobSequenceError({ stage, reason, detail })

const sequenceFail = (
  stage: S2SJobSequenceError["stage"],
  reason: S2SJobSequenceError["reason"],
  detail: string
): Either.Either<never, S2SJobSequenceError> =>
  Either.left(sequenceError(stage, reason, detail))

const copyArtifactEvidence = (
  artifact: S2SArtifactEvidence
): S2SArtifactEvidence =>
  Object.freeze({
    artifactName: artifact.artifactName,
    artifactId: artifact.artifactId,
    artifactCount: artifact.artifactCount,
    archiveSizeBytes: artifact.archiveSizeBytes,
    largestMemberSizeBytes: artifact.largestMemberSizeBytes,
    compressionLevel: artifact.compressionLevel,
    retentionDays: artifact.retentionDays,
    overwrite: artifact.overwrite,
    apiDigestSha256: artifact.apiDigestSha256,
    downloadedArchiveSha256: artifact.downloadedArchiveSha256
  })

const sameArtifactEvidence = (
  left: S2SArtifactEvidence,
  right: S2SArtifactEvidence
): boolean =>
  left.artifactName === right.artifactName &&
  left.artifactId === right.artifactId &&
  left.artifactCount === right.artifactCount &&
  left.archiveSizeBytes === right.archiveSizeBytes &&
  left.largestMemberSizeBytes === right.largestMemberSizeBytes &&
  left.compressionLevel === right.compressionLevel &&
  left.retentionDays === right.retentionDays &&
  left.overwrite === right.overwrite &&
  left.apiDigestSha256 === right.apiDigestSha256 &&
  left.downloadedArchiveSha256 === right.downloadedArchiveSha256

const artifactUsesFrozenTransportPolicy = (
  artifact: S2SArtifactEvidence
): boolean =>
  artifact.artifactCount ===
    S2S_CONFIRMATORY_POLICY.archive.artifactCountPerJob &&
  artifact.archiveSizeBytes > 0 &&
  artifact.largestMemberSizeBytes > 0 &&
  artifact.largestMemberSizeBytes <= artifact.archiveSizeBytes &&
  artifact.compressionLevel ===
    S2S_CONFIRMATORY_POLICY.archive.compressionLevel &&
  artifact.retentionDays === S2S_CONFIRMATORY_POLICY.archive.retentionDays &&
  artifact.overwrite === S2S_CONFIRMATORY_POLICY.archive.overwrite &&
  artifact.apiDigestSha256 === artifact.downloadedArchiveSha256

const validateReadback = (
  stage: S2SJobSequenceError["stage"],
  readback: S2SCarrierReadback,
  expectedMembers: ReadonlyArray<S2SExpectedZipMember>,
  maximumArchiveBytes: number,
  maximumExpandedBytes: number
): Either.Either<ValidatedCarrierReadback, S2SJobSequenceFailure> => {
  const artifact = copyArtifactEvidence(readback.artifact)
  if (!artifactUsesFrozenTransportPolicy(artifact)) {
    return sequenceFail(
      stage,
      "ARTIFACT_EVIDENCE_MISMATCH",
      "artifact evidence disagrees with the frozen transport policy"
    )
  }
  const archive = validateS2SArtifactZip(readback.archiveBytes, {
    expectedArchiveSha256: artifact.apiDigestSha256,
    expectedArchiveByteLength: artifact.archiveSizeBytes,
    expectedMembers,
    maximumArchiveBytes,
    maximumExpandedBytes
  })
  if (Either.isLeft(archive)) return Either.left(archive.left)
  if (
    archive.right.archiveByteLength !== artifact.archiveSizeBytes ||
    archive.right.archiveSha256 !== artifact.apiDigestSha256 ||
    archive.right.largestMemberByteLength !==
      artifact.largestMemberSizeBytes
  ) {
    return sequenceFail(
      stage,
      "MEMBER_METRICS_MISMATCH",
      "validated ZIP metrics disagree with artifact evidence"
    )
  }
  return Either.right(
    Object.freeze({ artifact, archive: archive.right })
  )
}

const copyBoundedNumericBytes = (
  stage: "CONFIRM" | "ADJUDICATE",
  inputBytes: Uint8Array,
  maximumBytes: number
): Either.Either<Uint8Array, S2SJobSequenceError> => {
  if (inputBytes.byteLength < 1 || inputBytes.byteLength > maximumBytes) {
    return sequenceFail(
      stage,
      "MEMBER_METRICS_MISMATCH",
      "numeric member violates its role-specific byte bound"
    )
  }
  return Either.right(Uint8Array.from(inputBytes))
}

const memberNamed = (
  stage: S2SJobSequenceError["stage"],
  readback: ValidatedCarrierReadback,
  name: string
): Either.Either<S2SValidatedZipMember, S2SJobSequenceError> => {
  const member = readback.archive.members.find((candidate) => candidate.name === name)
  return member === undefined
    ? sequenceFail(stage, "MEMBER_MISSING", `required member is absent: ${name}`)
    : Either.right(member)
}

const decodeEvents = (
  stage: S2SJobSequenceError["stage"],
  inputs: ReadonlyArray<unknown>,
  expectedLength: number
): Either.Either<ReadonlyArray<S2SConfirmatoryEvent>, S2SJobSequenceError> => {
  if (inputs.length !== expectedLength) {
    return sequenceFail(
      stage,
      "EVENT_SEQUENCE_INVALID",
      `stage requires exactly ${expectedLength} event(s)`
    )
  }
  const events: Array<S2SConfirmatoryEvent> = []
  for (const input of inputs) {
    const decoded = Schema.decodeUnknownEither(S2SConfirmatoryEventSchema, {
      onExcessProperty: "error"
    })(input)
    if (Either.isLeft(decoded)) {
      return sequenceFail(
        stage,
        "EVENT_SEQUENCE_INVALID",
        "a stage event failed strict schema decoding"
      )
    }
    events.push(decoded.right)
  }
  return Either.right(Object.freeze(events))
}

const makeUploadMember = <Name extends string>(
  name: Name,
  inputBytes: Uint8Array
): S2SUploadMember<Name> => {
  const bytes = Uint8Array.from(inputBytes)
  return Object.freeze({
    name,
    byteLength: bytes.byteLength,
    rawBytesSha256: S2SSha256Schema.make(rawS2SFileSha256(bytes)),
    readBytes: (): Uint8Array => Uint8Array.from(bytes)
  })
}

const controlPolicy = (): S2SExpectedZipMember => ({
  name: "control_receipt.json",
  maximumBytes: S2S_DURABLE_JOURNAL_MAX_FILE_BYTES
})

const registrationPolicy = (): ReadonlyArray<S2SExpectedZipMember> =>
  Object.freeze([
    {
      name: S2S_REGISTRATION_ARCHIVE_EXACT_MEMBERS[0],
      maximumBytes: S2S_DURABLE_JOURNAL_MAX_FILE_BYTES
    }
  ])

const candidatePolicy = (): ReadonlyArray<S2SExpectedZipMember> =>
  Object.freeze([
    controlPolicy(),
    {
      name: S2S_CONFIRMATORY_POLICY.candidateArchive.exactMembers[1],
      maximumBytes:
        S2S_CONFIRMATORY_POLICY.archive.candidateMemberMaximumBytes
    }
  ])

const validateArtifactBinding = (
  stage: S2SJobSequenceError["stage"],
  observed: S2SArtifactEvidence,
  eventBound: S2SArtifactEvidence,
  label: string
): Either.Either<void, S2SJobSequenceError> =>
  sameArtifactEvidence(observed, eventBound)
    ? Either.right(undefined)
    : sequenceFail(
        stage,
        "ARTIFACT_EVIDENCE_MISMATCH",
        `${label} readback evidence differs from its journal-bound event`
      )

const validateAdjudicationProjection = (
  stage: "ADJUDICATE",
  bytes: Uint8Array,
  state: Extract<
    S2SDurableJournalSnapshot["state"],
    { readonly _tag: "CandidateProduced" | "AdjudicationProduced" }
  >,
  event: EventOf<"RecordAdjudicationProduced">
): Either.Either<void, S2SJobSequenceFailure> => {
  const opaque = makeOpaqueNumericFile(
    "numeric_adjudication.json",
    "hswm-swm0w-s2s-numeric-adjudication/v1",
    bytes,
    event.numericAdjudicationBytesSha256
  )
  if (Either.isLeft(opaque)) return Either.left(opaque.left)
  const projection = projectOpaqueNumericAdjudication(
    opaque.right,
    state.candidate.numericCandidateBytesSha256,
    state.candidate.numericConfirmRequestSha256
  )
  if (Either.isLeft(projection)) return Either.left(projection.left)
  if (
    projection.right.numericAdjudicationBytesSha256 !==
      event.numericAdjudicationBytesSha256 ||
    projection.right.numericAdjudicationReceiptSha256 !==
      event.numericAdjudicationReceiptSha256 ||
    projection.right.numericCandidateDocumentSha256 !==
      event.numericCandidateDocumentSha256 ||
    projection.right.numericCandidateReceiptSha256 !==
      event.numericCandidateReceiptSha256 ||
    projection.right.numericConfirmRequestSha256 !==
      event.numericConfirmRequestSha256 ||
    projection.right.numericCandidateOutcome !== event.numericCandidateOutcome
  ) {
    return sequenceFail(
      stage,
      "NUMERIC_PROJECTION_MISMATCH",
      "numeric adjudication projection differs from its control event"
    )
  }
  return Either.right(undefined)
}

export const prepareS2SRegistrationCarrier = (
  inputs: S2SRegistrationStageEvents
): Either.Either<S2SRegistrationCarrierPlan, S2SJobSequenceFailure> => {
  const decoded = decodeEvents("REGISTER", inputs, 1)
  if (Either.isLeft(decoded)) return Either.left(decoded.left)
  const beginRegistration = decoded.right[0]
  if (beginRegistration?._tag !== "BeginRegistration") {
    return sequenceFail(
      "REGISTER",
      "EVENT_SEQUENCE_INVALID",
      "registration stage requires exactly BeginRegistration"
    )
  }
  const carrier = buildS2SDurableJournal(
    "REGISTRATION_CARRIER",
    [],
    [beginRegistration]
  )
  if (Either.isLeft(carrier)) return Either.left(carrier.left)
  if (carrier.right.state._tag !== "Registering") {
    return sequenceFail(
      "REGISTER",
      "PREDECESSOR_PHASE_MISMATCH",
      "registration carrier did not stop at Registering"
    )
  }
  const members: S2SRegistrationCarrierPlan["members"] = Object.freeze([
    makeUploadMember("control_receipt.json", carrier.right.canonicalBytes)
  ])
  return Either.right(
    Object.freeze({
      _tag: "RegistrationCarrierReady" as const,
      carrier: carrier.right,
      members
    })
  )
}

export const prepareS2SCandidateCarrier = (input: {
  readonly registrationReadback: S2SCarrierReadback
  readonly numericCandidateBytes: Uint8Array
  readonly events: S2SCandidateStageEvents
}): Either.Either<S2SCandidateCarrierPlan, S2SJobSequenceFailure> => {
  const decoded = decodeEvents("CONFIRM", input.events, 5)
  if (Either.isLeft(decoded)) return Either.left(decoded.left)
  const numericCandidate = copyBoundedNumericBytes(
    "CONFIRM",
    input.numericCandidateBytes,
    S2S_CONFIRMATORY_POLICY.archive.candidateMemberMaximumBytes
  )
  if (Either.isLeft(numericCandidate)) return Either.left(numericCandidate.left)
  const numericCandidateBytes = numericCandidate.right
  const verifyRegistration = decoded.right[0]
  const beginConfirm = decoded.right[1]
  const acceptPulse = decoded.right[2]
  const beginNumericConfirm = decoded.right[3]
  const candidateProduced = decoded.right[4]
  if (
    verifyRegistration?._tag !== "VerifyRegistration" ||
    beginConfirm?._tag !== "BeginConfirm" ||
    acceptPulse?._tag !== "AcceptVerifiedPulse" ||
    beginNumericConfirm?._tag !== "BeginNumericConfirm" ||
    candidateProduced?._tag !== "RecordCandidateProduced"
  ) {
    return sequenceFail(
      "CONFIRM",
      "EVENT_SEQUENCE_INVALID",
      "confirm stage requires the exact five-event tuple"
    )
  }
  const registration = validateReadback(
    "CONFIRM",
    input.registrationReadback,
    registrationPolicy(),
    S2S_CONFIRMATORY_POLICY.archive.registrationArchiveMaximumBytes,
    S2S_CONFIRMATORY_POLICY.archive.registrationArchiveMaximumBytes
  )
  if (Either.isLeft(registration)) return Either.left(registration.left)
  const artifactBinding = validateArtifactBinding(
    "CONFIRM",
    registration.right.artifact,
    verifyRegistration.artifact,
    "registration"
  )
  if (Either.isLeft(artifactBinding)) return Either.left(artifactBinding.left)
  const control = memberNamed(
    "CONFIRM",
    registration.right,
    "control_receipt.json"
  )
  if (Either.isLeft(control)) return Either.left(control.left)
  const predecessorBytes = control.right.readBytes()
  const predecessor = reconstructS2SDurableJournalChain([predecessorBytes])
  if (Either.isLeft(predecessor)) return Either.left(predecessor.left)
  if (
    predecessor.right.document.role !== "REGISTRATION_CARRIER" ||
    predecessor.right.state._tag !== "Registering"
  ) {
    return sequenceFail(
      "CONFIRM",
      "PREDECESSOR_PHASE_MISMATCH",
      "confirm stage requires the exact registration carrier"
    )
  }
  const candidate = makeOpaqueNumericFile(
    "numeric_candidate.json",
    "hswm-swm0w-s2s-numeric-candidate/v1",
    numericCandidateBytes,
    candidateProduced.numericCandidateBytesSha256
  )
  if (Either.isLeft(candidate)) return Either.left(candidate.left)
  const carrier = buildS2SDurableJournal(
    "CANDIDATE_CARRIER",
    [predecessorBytes],
    [
      verifyRegistration,
      beginConfirm,
      acceptPulse,
      beginNumericConfirm,
      candidateProduced
    ]
  )
  if (Either.isLeft(carrier)) return Either.left(carrier.left)
  if (carrier.right.state._tag !== "CandidateProduced") {
    return sequenceFail(
      "CONFIRM",
      "PREDECESSOR_PHASE_MISMATCH",
      "candidate carrier did not stop before job completion evidence"
    )
  }
  const members: S2SCandidateCarrierPlan["members"] = Object.freeze([
    makeUploadMember("control_receipt.json", carrier.right.canonicalBytes),
    makeUploadMember("numeric_candidate.json", candidate.right.canonicalUtf8WithLf)
  ])
  return Either.right(
    Object.freeze({
      _tag: "CandidateCarrierReady" as const,
      carrier: carrier.right,
      members
    })
  )
}

export const prepareS2SAdjudicationCarrier = (input: {
  readonly registrationReadback: S2SCarrierReadback
  readonly candidateReadback: S2SCarrierReadback
  readonly numericAdjudicationBytes: Uint8Array
  readonly events: S2SAdjudicationStageEvents
}): Either.Either<S2SAdjudicationCarrierPlan, S2SJobSequenceFailure> => {
  const decoded = decodeEvents("ADJUDICATE", input.events, 3)
  if (Either.isLeft(decoded)) return Either.left(decoded.left)
  const numericAdjudication = copyBoundedNumericBytes(
    "ADJUDICATE",
    input.numericAdjudicationBytes,
    S2S_NUMERIC_ADJUDICATION_MAX_BYTES
  )
  if (Either.isLeft(numericAdjudication)) {
    return Either.left(numericAdjudication.left)
  }
  const numericAdjudicationBytes = numericAdjudication.right
  const verifyCandidate = decoded.right[0]
  const beginAdjudication = decoded.right[1]
  const adjudicationProduced = decoded.right[2]
  if (
    verifyCandidate?._tag !== "VerifyCandidateArtifact" ||
    beginAdjudication?._tag !== "BeginAdjudication" ||
    adjudicationProduced?._tag !== "RecordAdjudicationProduced"
  ) {
    return sequenceFail(
      "ADJUDICATE",
      "EVENT_SEQUENCE_INVALID",
      "adjudication stage requires the exact three-event tuple"
    )
  }
  const registration = validateReadback(
    "ADJUDICATE",
    input.registrationReadback,
    registrationPolicy(),
    S2S_CONFIRMATORY_POLICY.archive.registrationArchiveMaximumBytes,
    S2S_CONFIRMATORY_POLICY.archive.registrationArchiveMaximumBytes
  )
  if (Either.isLeft(registration)) return Either.left(registration.left)
  const candidate = validateReadback(
    "ADJUDICATE",
    input.candidateReadback,
    candidatePolicy(),
    S2S_CONFIRMATORY_POLICY.archive.candidateArchiveMaximumBytes,
    S2S_CONFIRMATORY_POLICY.archive.candidateArchiveMaximumBytes
  )
  if (Either.isLeft(candidate)) return Either.left(candidate.left)
  const registrationControl = memberNamed(
    "ADJUDICATE",
    registration.right,
    "control_receipt.json"
  )
  if (Either.isLeft(registrationControl)) {
    return Either.left(registrationControl.left)
  }
  const candidateControl = memberNamed(
    "ADJUDICATE",
    candidate.right,
    "control_receipt.json"
  )
  if (Either.isLeft(candidateControl)) return Either.left(candidateControl.left)
  const candidateNumeric = memberNamed(
    "ADJUDICATE",
    candidate.right,
    "numeric_candidate.json"
  )
  if (Either.isLeft(candidateNumeric)) return Either.left(candidateNumeric.left)
  const predecessorJournals = [
    registrationControl.right.readBytes(),
    candidateControl.right.readBytes()
  ]
  const predecessor = reconstructS2SDurableJournalChain(predecessorJournals)
  if (Either.isLeft(predecessor)) return Either.left(predecessor.left)
  if (
    predecessor.right.document.role !== "CANDIDATE_CARRIER" ||
    predecessor.right.state._tag !== "CandidateProduced"
  ) {
    return sequenceFail(
      "ADJUDICATE",
      "PREDECESSOR_PHASE_MISMATCH",
      "adjudication stage requires the full candidate carrier chain"
    )
  }
  const registrationBinding = validateArtifactBinding(
    "ADJUDICATE",
    registration.right.artifact,
    predecessor.right.state.registrationEvidence.artifact,
    "registration"
  )
  if (Either.isLeft(registrationBinding)) return Either.left(registrationBinding.left)
  const candidateBinding = validateArtifactBinding(
    "ADJUDICATE",
    candidate.right.artifact,
    verifyCandidate.artifact,
    "candidate"
  )
  if (Either.isLeft(candidateBinding)) return Either.left(candidateBinding.left)
  const opaqueCandidate = makeOpaqueNumericFile(
    "numeric_candidate.json",
    "hswm-swm0w-s2s-numeric-candidate/v1",
    candidateNumeric.right.readBytes(),
    predecessor.right.state.candidate.numericCandidateBytesSha256
  )
  if (Either.isLeft(opaqueCandidate)) return Either.left(opaqueCandidate.left)
  const projection = validateAdjudicationProjection(
    "ADJUDICATE",
    numericAdjudicationBytes,
    predecessor.right.state,
    adjudicationProduced
  )
  if (Either.isLeft(projection)) return Either.left(projection.left)
  const carrier = buildS2SDurableJournal(
    "ADJUDICATION_CARRIER",
    predecessorJournals,
    [verifyCandidate, beginAdjudication, adjudicationProduced]
  )
  if (Either.isLeft(carrier)) return Either.left(carrier.left)
  if (carrier.right.state._tag !== "AdjudicationProduced") {
    return sequenceFail(
      "ADJUDICATE",
      "PREDECESSOR_PHASE_MISMATCH",
      "adjudication carrier did not stop before its completion evidence"
    )
  }
  const members: S2SAdjudicationCarrierPlan["members"] = Object.freeze([
    makeUploadMember("control_receipt.json", carrier.right.canonicalBytes),
    makeUploadMember("numeric_adjudication.json", numericAdjudicationBytes)
  ])
  return Either.right(
    Object.freeze({
      _tag: "AdjudicationCarrierReady" as const,
      carrier: carrier.right,
      members
    })
  )
}
