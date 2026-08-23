import { types as nodeTypes } from "node:util"

import { Data, Effect, Either } from "effect"

import { rawS2SFileSha256 } from "./s2s-canonical.js"
import {
  buildS2SEvidenceClaim,
  type S2SEvidenceAttachmentDescriptor,
  type S2SEvidenceEnvelopeError,
  type S2SEvidenceEnvelopeInput,
  type S2SEvidenceEnvelopeSnapshot
} from "./s2s-evidence-envelope.js"
import {
  S2SDurableEvidenceFileStore,
  isAuthenticS2SDurableEvidenceRecovery,
  type S2SDurableEvidenceFileStoreFailure,
  type S2SDurableEvidenceRecovery
} from "./s2s-evidence-file.js"
import {
  buildS2SSuccessStageEvidenceEnvelope,
  validateS2SSuccessStageEvidenceEnvelope,
  type S2SEvidenceProfileError
} from "./s2s-evidence-profile.js"
import type { S2SCurrentRunStageEvidence } from "./s2s-run-authority.js"
import {
  validateS2SCandidateReadReplayPair,
  validateS2SCurrentRunStageEvidenceForArtifactReplay,
  validateS2SStageArtifactReadReplay,
  type S2SStageArtifactReadReplayError,
  type S2SStageArtifactReadReplayManifest,
  type S2SStageArtifactReadReplaySnapshot
} from "./s2s-stage-artifact-read-replay.js"

/**
 * Root-private bridge between fully validated stage-read replay carriers and
 * the local create-only evidence store. It deliberately validates only the
 * reserved replay slots; the other success-profile attachments still require
 * their later nested validators and closed stage programs.
 */

type ConsumerStage = "CONFIRM" | "ADJUDICATE"
type ReplayOperation = S2SStageArtifactReadReplayManifest["operation"]
type ReplayRole = S2SStageArtifactReadReplayManifest["role"]

interface ReplaySlotSpec {
  readonly logicalName: string
  readonly operation: ReplayOperation
  readonly role: ReplayRole
}

const CONFIRM_REPLAY_SLOTS: ReadonlyArray<ReplaySlotSpec> = Object.freeze([
  Object.freeze({
    logicalName: "input/registration_read.zip",
    operation: "CONFIRM_READ_REGISTRATION",
    role: "REGISTRATION"
  })
])

const ADJUDICATE_REPLAY_SLOTS: ReadonlyArray<ReplaySlotSpec> = Object.freeze([
  Object.freeze({
    logicalName: "input/candidate_first_read.zip",
    operation: "ADJUDICATE_READ_CANDIDATE_FIRST",
    role: "CANDIDATE"
  }),
  Object.freeze({
    logicalName: "input/candidate_reread.zip",
    operation: "ADJUDICATE_REREAD_CANDIDATE",
    role: "CANDIDATE"
  }),
  Object.freeze({
    logicalName: "input/registration_read.zip",
    operation: "ADJUDICATE_READ_REGISTRATION",
    role: "REGISTRATION"
  })
])

const replaySlotsFor = (
  stage: ConsumerStage
): ReadonlyArray<ReplaySlotSpec> =>
  stage === "CONFIRM" ? CONFIRM_REPLAY_SLOTS : ADJUDICATE_REPLAY_SLOTS

export interface S2SStageReadReplayDurableProfileInput {
  readonly envelopeInput: S2SEvidenceEnvelopeInput
  readonly currentRunEvidence: unknown
}

export interface S2SDurableReplayAttachmentBinding {
  readonly logicalName: string
  readonly operation: ReplayOperation
  readonly role: ReplayRole
  readonly carrierByteLength: number
  readonly carrierRawSha256: string
  readonly replayManifestRawSha256: string
  readonly replayReceiptSha256: string
}

export interface S2SStageReadReplayDurablePublication {
  readonly _tag:
    | "StageReadReplayProfileCommitted"
    | "StageReadReplayProfileAlreadyCommitted"
  readonly stage: ConsumerStage
  readonly manifestRawSha256: string
  readonly claimRawSha256: string
  readonly replayAttachments: ReadonlyArray<S2SDurableReplayAttachmentBinding>
  readonly recovery: S2SDurableEvidenceRecovery
}

export class S2SStageReadReplayDurableProfileError extends Data.TaggedError(
  "S2SStageReadReplayDurableProfileError"
)<{
  readonly stage: ConsumerStage | "REGISTER" | "UNKNOWN"
  readonly reason:
    | "INPUT_INVALID"
    | "REGISTER_UNSUPPORTED"
    | "CURRENT_RUN_ENVELOPE_MISMATCH"
    | "PREDECESSOR_RECOVERY_UNAUTHENTIC"
    | "PREDECESSOR_ENVELOPE_MISMATCH"
    | "REPLAY_ATTACHMENT_MISSING"
    | "REPLAY_ATTACHMENT_MISMATCH"
    | "REPLAY_OPERATION_MISMATCH"
    | "PUBLICATION_RECOVERY_UNAUTHENTIC"
    | "RECOVERED_ENVELOPE_MISMATCH"
    | "RECOVERED_PREDECESSOR_MISMATCH"
    | "RECOVERED_REPLAY_MISMATCH"
  readonly logicalName: string | null
  readonly detail: string
}> {}

export type S2SStageReadReplayDurableFailure =
  | S2SEvidenceEnvelopeError
  | S2SEvidenceProfileError
  | S2SDurableEvidenceFileStoreFailure
  | S2SStageArtifactReadReplayError
  | S2SStageReadReplayDurableProfileError

interface ExactBridgeInput {
  readonly envelopeInput: S2SEvidenceEnvelopeInput
  readonly currentRunEvidence: unknown
}

interface PrevalidatedReplaySlot {
  readonly spec: ReplaySlotSpec
  readonly descriptor: S2SEvidenceAttachmentDescriptor
  readonly carrierBytes: Uint8Array
  readonly replay: S2SStageArtifactReadReplaySnapshot
}

interface DurableStageDigest {
  readonly manifestRawSha256: string
  readonly manifestBytes: Uint8Array
  readonly claimRawSha256: string
  readonly claimBytes: Uint8Array
}

const failure = (
  stage: ConsumerStage | "REGISTER" | "UNKNOWN",
  reason: S2SStageReadReplayDurableProfileError["reason"],
  detail: string,
  logicalName: string | null = null
): S2SStageReadReplayDurableProfileError =>
  new S2SStageReadReplayDurableProfileError({
    stage,
    reason,
    logicalName,
    detail
  })

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((value, index) => value === right[index])

const sameDescriptor = (
  left: S2SEvidenceAttachmentDescriptor,
  right: S2SEvidenceAttachmentDescriptor
): boolean =>
  left.logical_name === right.logical_name &&
  left.role === right.role &&
  left.schema_version === right.schema_version &&
  left.media_type === right.media_type &&
  left.byte_length === right.byte_length &&
  left.raw_sha256 === right.raw_sha256

const exactBridgeInput = (
  input: unknown
): Either.Either<ExactBridgeInput, S2SStageReadReplayDurableProfileError> => {
  try {
    if (
      input === null ||
      typeof input !== "object" ||
      nodeTypes.isProxy(input) ||
      Object.getPrototypeOf(input) !== Object.prototype
    ) {
      return Either.left(
        failure("UNKNOWN", "INPUT_INVALID", "bridge input is not plain data")
      )
    }
    const descriptors = Object.getOwnPropertyDescriptors(input)
    if (
      Reflect.ownKeys(input).length !== 2 ||
      !("envelopeInput" in descriptors) ||
      !("currentRunEvidence" in descriptors) ||
      descriptors["envelopeInput"]?.get !== undefined ||
      descriptors["envelopeInput"]?.set !== undefined ||
      descriptors["currentRunEvidence"]?.get !== undefined ||
      descriptors["currentRunEvidence"]?.set !== undefined
    ) {
      return Either.left(
        failure("UNKNOWN", "INPUT_INVALID", "bridge input shape is not exact")
      )
    }
    return Either.right(
      Object.freeze({
        envelopeInput: descriptors["envelopeInput"]
          ?.value as S2SEvidenceEnvelopeInput,
        currentRunEvidence: descriptors["currentRunEvidence"]?.value
      })
    )
  } catch {
    return Either.left(
      failure("UNKNOWN", "INPUT_INVALID", "bridge input inspection failed")
    )
  }
}

const currentMatchesEnvelope = (
  current: S2SCurrentRunStageEvidence,
  envelope: S2SEvidenceEnvelopeSnapshot
): boolean => {
  const document = envelope.document
  return (
    document.stage === current.stage &&
    document.source_commit_a === current.sourceCommitA &&
    document.registration_commit_b === current.registrationCommitB &&
    document.workflow_run_id === current.workflowRunId &&
    document.workflow_run_attempt === current.workflowRunAttempt &&
    document.workflow_head_sha === current.registrationCommitB &&
    document.workflow_run_created_at_unix_seconds ===
      current.workflowRunCreatedAtUnixSeconds &&
    document.workflow_api_path === current.workflowApiPath &&
    document.workflow_file_sha256 === current.workflowFileSha256 &&
    document.workflow_contract_sha256 === current.workflowContractSha256 &&
    document.current_job_database_id === current.currentJobDatabaseId &&
    document.predecessor !== null &&
    document.predecessor.stage ===
      (current.stage === "CONFIRM" ? "REGISTER" : "CONFIRM")
  )
}

const attachmentNamed = (
  envelope: S2SEvidenceEnvelopeSnapshot,
  stage: ConsumerStage,
  logicalName: string
) => {
  const matches = envelope.attachments.filter(
    (attachment) => attachment.descriptor.logical_name === logicalName
  )
  return matches.length === 1
    ? Either.right(matches[0] as (typeof matches)[number])
    : Either.left(
        failure(
          stage,
          "REPLAY_ATTACHMENT_MISSING",
          "reserved replay attachment is not unique",
          logicalName
        )
      )
}

const validateReplaySlots = (
  stage: ConsumerStage,
  envelope: S2SEvidenceEnvelopeSnapshot,
  current: S2SCurrentRunStageEvidence,
  predecessorRecovery: S2SDurableEvidenceRecovery
): Either.Either<
  ReadonlyArray<PrevalidatedReplaySlot>,
  S2SStageArtifactReadReplayError | S2SStageReadReplayDurableProfileError
> => {
  const slots: Array<PrevalidatedReplaySlot> = []
  for (const spec of replaySlotsFor(stage)) {
    const attachment = attachmentNamed(envelope, stage, spec.logicalName)
    if (Either.isLeft(attachment)) return Either.left(attachment.left)
    const carrierBytes = attachment.right.readBytes()
    const replay = validateS2SStageArtifactReadReplay({
      carrierBytes,
      currentRunEvidence: current,
      predecessorRecovery
    })
    if (Either.isLeft(replay)) return Either.left(replay.left)
    const manifest = replay.right.manifest
    if (manifest.operation !== spec.operation || manifest.role !== spec.role) {
      return Either.left(
        failure(
          stage,
          "REPLAY_OPERATION_MISMATCH",
          "reserved replay attachment carries the wrong operation or role",
          spec.logicalName
        )
      )
    }
    const descriptor = attachment.right.descriptor
    if (
      descriptor.byte_length !== replay.right.carrierByteLength ||
      descriptor.raw_sha256 !== replay.right.carrierRawSha256 ||
      !sameBytes(carrierBytes, replay.right.readCarrierBytes())
    ) {
      return Either.left(
        failure(
          stage,
          "REPLAY_ATTACHMENT_MISMATCH",
          "reserved replay descriptor differs from validated carrier bytes",
          spec.logicalName
        )
      )
    }
    slots.push(
      Object.freeze({
        spec,
        descriptor: structuredClone(descriptor),
        carrierBytes: Uint8Array.from(carrierBytes),
        replay: replay.right
      })
    )
  }
  if (stage === "ADJUDICATE") {
    const first = slots.find(
      ({ spec }) => spec.operation === "ADJUDICATE_READ_CANDIDATE_FIRST"
    )
    const reread = slots.find(
      ({ spec }) => spec.operation === "ADJUDICATE_REREAD_CANDIDATE"
    )
    if (first === undefined || reread === undefined) {
      return Either.left(
        failure(
          stage,
          "REPLAY_ATTACHMENT_MISSING",
          "candidate first-read and reread slots are both required"
        )
      )
    }
    const pair = validateS2SCandidateReadReplayPair(first.replay, reread.replay)
    if (Either.isLeft(pair)) return Either.left(pair.left)
  }
  return Either.right(Object.freeze(slots))
}

const stageDigests = (
  recovery: S2SDurableEvidenceRecovery
): ReadonlyArray<DurableStageDigest> =>
  Object.freeze(
    recovery.chain.map(({ envelope, claim }) =>
      Object.freeze({
        manifestRawSha256: envelope.manifestRawSha256,
        manifestBytes: envelope.canonicalBytes,
        claimRawSha256: claim.claimRawSha256,
        claimBytes: claim.canonicalBytes
      })
    )
  )

const sameStageDigest = (
  stage: {
    readonly envelope: S2SEvidenceEnvelopeSnapshot
    readonly claim: {
      readonly claimRawSha256: string
      readonly canonicalBytes: Uint8Array
    }
  },
  digest: DurableStageDigest
): boolean =>
  stage.envelope.manifestRawSha256 === digest.manifestRawSha256 &&
  sameBytes(stage.envelope.canonicalBytes, digest.manifestBytes) &&
  stage.claim.claimRawSha256 === digest.claimRawSha256 &&
  sameBytes(stage.claim.canonicalBytes, digest.claimBytes)

const recoveredPublicationMatches = (
  stage: ConsumerStage,
  submitted: S2SEvidenceEnvelopeSnapshot,
  submittedClaimRawSha256: string,
  submittedClaimBytes: Uint8Array,
  predecessor: ReadonlyArray<DurableStageDigest>,
  slots: ReadonlyArray<PrevalidatedReplaySlot>,
  recovery: S2SDurableEvidenceRecovery
): Either.Either<void, S2SStageReadReplayDurableProfileError> => {
  const chain = recovery.chain
  const latest = recovery.latest
  const expectedLength = stage === "CONFIRM" ? 2 : 3
  if (
    chain.length !== expectedLength ||
    latest !== chain[chain.length - 1] ||
    predecessor.length !== expectedLength - 1 ||
    predecessor.some(
      (digest, index) =>
        chain[index] === undefined ||
        !sameStageDigest(chain[index], digest)
    )
  ) {
    return Either.left(
      failure(
        stage,
        "RECOVERED_PREDECESSOR_MISMATCH",
        "publication recovery changed the prevalidated predecessor prefix"
      )
    )
  }
  if (
    latest.envelope.manifestRawSha256 !== submitted.manifestRawSha256 ||
    !sameBytes(latest.envelope.canonicalBytes, submitted.canonicalBytes) ||
    latest.claim.claimRawSha256 !== submittedClaimRawSha256 ||
    !sameBytes(latest.claim.canonicalBytes, submittedClaimBytes)
  ) {
    return Either.left(
      failure(
        stage,
        "RECOVERED_ENVELOPE_MISMATCH",
        "publication recovery differs from the submitted envelope or claim"
      )
    )
  }
  const profile = validateS2SSuccessStageEvidenceEnvelope(latest.envelope)
  if (Either.isLeft(profile)) {
    return Either.left(
      failure(
        stage,
        "RECOVERED_ENVELOPE_MISMATCH",
        "publication recovery no longer satisfies the success profile"
      )
    )
  }
  for (const slot of slots) {
    const recovered = attachmentNamed(
      profile.right,
      stage,
      slot.spec.logicalName
    )
    if (Either.isLeft(recovered)) return Either.left(recovered.left)
    const descriptor = recovered.right.descriptor
    const bytes = recovered.right.readBytes()
    if (
      !sameDescriptor(descriptor, slot.descriptor) ||
      descriptor.raw_sha256 !== rawS2SFileSha256(bytes) ||
      !sameBytes(bytes, slot.carrierBytes)
    ) {
      return Either.left(
        failure(
          stage,
          "RECOVERED_REPLAY_MISMATCH",
          "recovered carrier is not byte-identical to its full prevalidation",
          slot.spec.logicalName
        )
      )
    }
  }
  return Either.right(undefined)
}

const makePublication = (
  stage: ConsumerStage,
  committed: "Committed" | "AlreadyCommitted",
  envelope: S2SEvidenceEnvelopeSnapshot,
  claimRawSha256: string,
  slots: ReadonlyArray<PrevalidatedReplaySlot>,
  recovery: S2SDurableEvidenceRecovery
): S2SStageReadReplayDurablePublication =>
  Object.freeze({
    _tag:
      committed === "Committed"
        ? "StageReadReplayProfileCommitted"
        : "StageReadReplayProfileAlreadyCommitted",
    stage,
    manifestRawSha256: envelope.manifestRawSha256,
    claimRawSha256,
    replayAttachments: Object.freeze(
      slots.map(({ spec, replay }) =>
        Object.freeze({
          logicalName: spec.logicalName,
          operation: spec.operation,
          role: spec.role,
          carrierByteLength: replay.carrierByteLength,
          carrierRawSha256: replay.carrierRawSha256,
          replayManifestRawSha256: replay.manifestRawSha256,
          replayReceiptSha256: replay.manifest.replay_receipt_sha256
        })
      )
    ),
    recovery
  })

export const commitS2SStageReadReplayProfileAttachments = (
  input: unknown
): Effect.Effect<
  S2SStageReadReplayDurablePublication,
  S2SStageReadReplayDurableFailure,
  S2SDurableEvidenceFileStore
> =>
  Effect.suspend(() =>
    Effect.gen(function* () {
      const exactInput = exactBridgeInput(input)
      if (Either.isLeft(exactInput)) return yield* exactInput.left
      const current =
        validateS2SCurrentRunStageEvidenceForArtifactReplay(
          exactInput.right.currentRunEvidence
        )
      if (Either.isLeft(current)) return yield* current.left
      const built = buildS2SSuccessStageEvidenceEnvelope(
        exactInput.right.envelopeInput
      )
      if (Either.isLeft(built)) return yield* built.left
      if (built.right.document.stage === "REGISTER") {
        return yield* failure(
          "REGISTER",
          "REGISTER_UNSUPPORTED",
          "registration has no predecessor-read replay slot"
        )
      }
      const stage = built.right.document.stage
      if (!currentMatchesEnvelope(current.right, built.right)) {
        return yield* failure(
          stage,
          "CURRENT_RUN_ENVELOPE_MISMATCH",
          "success envelope identity differs from strict current-run evidence"
        )
      }
      const predecessorStage = stage === "CONFIRM" ? "REGISTER" : "CONFIRM"
      const store = yield* S2SDurableEvidenceFileStore
      const predecessorRecovery = yield* store.recover({
        sourceCommitA: built.right.document.source_commit_a,
        registrationCommitB: built.right.document.registration_commit_b,
        workflowRunId: built.right.document.workflow_run_id,
        stage: predecessorStage
      })
      if (!isAuthenticS2SDurableEvidenceRecovery(predecessorRecovery)) {
        return yield* failure(
          stage,
          "PREDECESSOR_RECOVERY_UNAUTHENTIC",
          "predecessor recovery was not issued by the durable file store"
        )
      }
      const predecessor = built.right.document.predecessor
      const recoveredPredecessor = predecessorRecovery.latest
      if (
        predecessor === null ||
        predecessor.stage !== recoveredPredecessor.envelope.document.stage ||
        predecessor.manifest_raw_sha256 !==
          recoveredPredecessor.envelope.manifestRawSha256 ||
        predecessor.claim_raw_sha256 !==
          recoveredPredecessor.claim.claimRawSha256
      ) {
        return yield* failure(
          stage,
          "PREDECESSOR_ENVELOPE_MISMATCH",
          "success envelope does not extend the recovered predecessor"
        )
      }
      const predecessorDigests = stageDigests(predecessorRecovery)
      const slots = validateReplaySlots(
        stage,
        built.right,
        current.right,
        predecessorRecovery
      )
      if (Either.isLeft(slots)) return yield* slots.left
      const claim = buildS2SEvidenceClaim(built.right)
      if (Either.isLeft(claim)) return yield* claim.left

      // Exactly one call: store errors, including unknown publication outcome,
      // remain typed and are never converted into an implicit retry.
      const publication = yield* store.commit(built.right)
      if (!isAuthenticS2SDurableEvidenceRecovery(publication.recovery)) {
        return yield* failure(
          stage,
          "PUBLICATION_RECOVERY_UNAUTHENTIC",
          "commit returned a recovery not issued by the durable file store"
        )
      }
      const recovered = recoveredPublicationMatches(
        stage,
        built.right,
        claim.right.claimRawSha256,
        claim.right.canonicalBytes,
        predecessorDigests,
        slots.right,
        publication.recovery
      )
      if (Either.isLeft(recovered)) return yield* recovered.left
      return makePublication(
        stage,
        publication._tag,
        built.right,
        claim.right.claimRawSha256,
        slots.right,
        publication.recovery
      )
    })
  )
