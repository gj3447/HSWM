import { Context, Data, Effect, Either, Layer, Ref, Schema } from "effect"
import type { ParseResult } from "effect"

import {
  canonicalS2SControlJsonBytes,
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "./s2s-canonical.js"
import {
  S2SSha256Schema,
  S2S_PROTOCOL_CONFIG_DOCUMENT_SHA256,
  S2S_PROTOCOL_CONFIG_RECEIPT_SHA256,
  advanceS2SConfirmatory,
  decodeS2SConfirmatoryEvent,
  initialS2SConfirmatoryState,
  type S2SArtifactId,
  type S2SConfirmatoryEvent,
  type S2SConfirmatoryPhase,
  type S2SConfirmatoryState,
  type S2SConfirmatoryTransitionError,
  type S2SGitCommitSha,
  type S2SSha256
} from "./s2s-confirmatory.js"

export interface OpaqueNumericFile {
  readonly memberName: "numeric_candidate.json" | "numeric_adjudication.json"
  readonly schemaVersion:
    | "hswm-swm0w-s2s-numeric-candidate/v1"
    | "hswm-swm0w-s2s-numeric-adjudication/v1"
  readonly canonicalUtf8WithLf: Uint8Array
  readonly rawBytesSha256: S2SSha256
}

export class OpaqueNumericFileError extends Data.TaggedError(
  "OpaqueNumericFileError"
)<{
  readonly reason:
    | "EMPTY_FILE"
    | "HASH_MISMATCH"
    | "MISSING_SINGLE_TERMINAL_LF"
    | "NON_ASCII_BYTE"
}> {}

/**
 * Validate transport properties only. The TypeScript control plane must never
 * parse or reserialize Python's canonical numeric document.
 */
export const makeOpaqueNumericFile = (
  memberName: OpaqueNumericFile["memberName"],
  schemaVersion: OpaqueNumericFile["schemaVersion"],
  bytes: Uint8Array,
  expectedRawBytesSha256: S2SSha256
): Either.Either<OpaqueNumericFile, OpaqueNumericFileError> => {
  if (bytes.byteLength === 0) {
    return Either.left(new OpaqueNumericFileError({ reason: "EMPTY_FILE" }))
  }
  if (
    bytes[bytes.byteLength - 1] !== 0x0a ||
    bytes
      .subarray(0, bytes.byteLength - 1)
      .some((byte) => byte === 0x0a || byte === 0x0d)
  ) {
    return Either.left(
      new OpaqueNumericFileError({ reason: "MISSING_SINGLE_TERMINAL_LF" })
    )
  }
  if (bytes.some((byte) => byte > 0x7f)) {
    return Either.left(
      new OpaqueNumericFileError({ reason: "NON_ASCII_BYTE" })
    )
  }
  if (rawS2SFileSha256(bytes) !== expectedRawBytesSha256) {
    return Either.left(new OpaqueNumericFileError({ reason: "HASH_MISMATCH" }))
  }
  return Either.right(
    Object.freeze({
      memberName,
      schemaVersion,
      canonicalUtf8WithLf: Uint8Array.from(bytes),
      rawBytesSha256: expectedRawBytesSha256
    })
  )
}

const NumericCandidateOutcomeSchema = Schema.Literal(
  "CANDIDATE_PASS_AWAITING_BUNDLE",
  "CANDIDATE_KILL_AWAITING_BUNDLE",
  "CANDIDATE_INCONCLUSIVE_AWAITING_BUNDLE",
  "VOID"
)

const AsciiTextSchema = Schema.String.pipe(
  Schema.minLength(1),
  Schema.pattern(/^[\u0000-\u007f]*$/)
)

const NumericReplayProjectionSchema = Schema.Struct({
  candidate_reducer_canonical_equal: Schema.Literal(true),
  candidate_reducer_receipt_sha256: S2SSha256Schema,
  compact_competitive_phrase_allowed: Schema.Literal(false),
  compact_competitive_phrase_policy: Schema.Literal(
    "DS_SELECTED_CONFIGURATION_NEVER_BEAT_EPOCH_ZERO"
  ),
  numeric_candidate_outcome: NumericCandidateOutcomeSchema,
  numeric_candidate_reason_codes: Schema.Array(AsciiTextSchema).pipe(
    Schema.minItems(1)
  ),
  optimizer_refit_performed: Schema.Literal(false),
  protocol_config_receipt_sha256: Schema.Literal(
    S2S_PROTOCOL_CONFIG_RECEIPT_SHA256
  ),
  task_batch_sha256: S2SSha256Schema,
  task_evaluation_receipt_sha256s: Schema.Array(S2SSha256Schema).pipe(
    Schema.itemsCount(20)
  ),
  test_and_integrity_recomputed_count: Schema.Literal(20)
})

const NumericAdjudicationDocumentSchema = Schema.Struct({
  candidate_document_sha256: S2SSha256Schema,
  candidate_receipt_sha256: S2SSha256Schema,
  canonical_encoding: Schema.Literal(
    "ASCII_CANONICAL_UTF8_JSON_PLUS_SINGLE_LF"
  ),
  claim_boundary: Schema.Literal(
    "NUMERIC_ONLY_NO_EVIDENCE_VERDICT_OR_CHRONOLOGY_CLAIM"
  ),
  confirm_request_sha256: S2SSha256Schema,
  numeric_replay: NumericReplayProjectionSchema,
  receipt_sha256: S2SSha256Schema,
  schema_version: Schema.Literal(
    "hswm-swm0w-s2s-numeric-adjudication/v1"
  ),
  scientific_status: Schema.Literal("NUMERIC_CANDIDATE_ONLY_UNJUDGED"),
  status: Schema.Literal("NUMERIC_REPLAY_VALIDATED_CANDIDATE_ONLY")
})

type NumericCandidateOutcome = Schema.Schema.Type<
  typeof NumericCandidateOutcomeSchema
>

export interface NumericAdjudicationProjection {
  readonly numericAdjudicationBytesSha256: S2SSha256
  readonly numericAdjudicationReceiptSha256: S2SSha256
  readonly numericCandidateDocumentSha256: S2SSha256
  readonly numericCandidateReceiptSha256: S2SSha256
  readonly numericConfirmRequestSha256: S2SSha256
  readonly numericCandidateOutcome: Exclude<NumericCandidateOutcome, "VOID">
  readonly numericCandidateReasonCodes: ReadonlyArray<string>
  readonly candidateReducerReceiptSha256: S2SSha256
  readonly taskBatchSha256: S2SSha256
}

export class NumericAdjudicationProjectionError extends Data.TaggedError(
  "NumericAdjudicationProjectionError"
)<{
  readonly reason:
    | "CANDIDATE_BINDING_MISMATCH"
    | "CANONICAL_BYTES_DRIFT"
    | "DOCUMENT_PARSE_FAILED"
    | "DOCUMENT_SCHEMA_REJECTED"
    | "NUMERIC_OUTCOME_VOID"
    | "RAW_HASH_MISMATCH"
    | "RECEIPT_HASH_MISMATCH"
}> {}

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((byte, index) => byte === right[index])

/**
 * Parse only the frozen adjudication projection needed by the control plane.
 * The original Python bytes remain opaque and are never rewritten or emitted.
 */
export const projectOpaqueNumericAdjudication = (
  file: OpaqueNumericFile,
  expectedCandidateDocumentSha256: S2SSha256,
  expectedConfirmRequestSha256: S2SSha256
): Either.Either<
  NumericAdjudicationProjection,
  NumericAdjudicationProjectionError
> => {
  if (
    file.memberName !== "numeric_adjudication.json" ||
    file.schemaVersion !== "hswm-swm0w-s2s-numeric-adjudication/v1" ||
    rawS2SFileSha256(file.canonicalUtf8WithLf) !== file.rawBytesSha256
  ) {
    return Either.left(
      new NumericAdjudicationProjectionError({ reason: "RAW_HASH_MISMATCH" })
    )
  }
  let parsed: unknown
  try {
    const text = new TextDecoder("utf-8", { fatal: true }).decode(
      file.canonicalUtf8WithLf
    )
    parsed = JSON.parse(text.slice(0, -1))
  } catch {
    return Either.left(
      new NumericAdjudicationProjectionError({
        reason: "DOCUMENT_PARSE_FAILED"
      })
    )
  }
  const canonical = canonicalS2SControlJsonBytes(parsed)
  if (
    Either.isLeft(canonical) ||
    !sameBytes(canonical.right, file.canonicalUtf8WithLf)
  ) {
    return Either.left(
      new NumericAdjudicationProjectionError({ reason: "CANONICAL_BYTES_DRIFT" })
    )
  }
  const decoded = Schema.decodeUnknownEither(NumericAdjudicationDocumentSchema, {
    onExcessProperty: "error"
  })(parsed)
  if (Either.isLeft(decoded)) {
    return Either.left(
      new NumericAdjudicationProjectionError({
        reason: "DOCUMENT_SCHEMA_REJECTED"
      })
    )
  }
  const document = decoded.right
  if (
    document.candidate_document_sha256 !==
      expectedCandidateDocumentSha256 ||
    document.confirm_request_sha256 !== expectedConfirmRequestSha256
  ) {
    return Either.left(
      new NumericAdjudicationProjectionError({
        reason: "CANDIDATE_BINDING_MISMATCH"
      })
    )
  }
  const unsigned = {
    candidate_document_sha256: document.candidate_document_sha256,
    candidate_receipt_sha256: document.candidate_receipt_sha256,
    canonical_encoding: document.canonical_encoding,
    claim_boundary: document.claim_boundary,
    confirm_request_sha256: document.confirm_request_sha256,
    numeric_replay: document.numeric_replay,
    schema_version: document.schema_version,
    scientific_status: document.scientific_status,
    status: document.status
  }
  const receipt = canonicalS2SControlSha256(unsigned)
  if (Either.isLeft(receipt) || receipt.right !== document.receipt_sha256) {
    return Either.left(
      new NumericAdjudicationProjectionError({
        reason: "RECEIPT_HASH_MISMATCH"
      })
    )
  }
  if (document.numeric_replay.numeric_candidate_outcome === "VOID") {
    return Either.left(
      new NumericAdjudicationProjectionError({ reason: "NUMERIC_OUTCOME_VOID" })
    )
  }
  return Either.right(
    Object.freeze({
      numericAdjudicationBytesSha256: file.rawBytesSha256,
      numericAdjudicationReceiptSha256: document.receipt_sha256,
      numericCandidateDocumentSha256: document.candidate_document_sha256,
      numericCandidateReceiptSha256: document.candidate_receipt_sha256,
      numericConfirmRequestSha256: document.confirm_request_sha256,
      numericCandidateOutcome:
        document.numeric_replay.numeric_candidate_outcome,
      numericCandidateReasonCodes: Object.freeze([
        ...document.numeric_replay.numeric_candidate_reason_codes
      ]),
      candidateReducerReceiptSha256:
        document.numeric_replay.candidate_reducer_receipt_sha256,
      taskBatchSha256: document.numeric_replay.task_batch_sha256
    })
  )
}

export interface PythonNumericConfirmInvocation {
  readonly schemaVersion: "hswm-swm0w-s2s-numeric-confirm-request/v1"
  readonly externalSeedHex: S2SSha256
  readonly protocolConfigCanonicalUtf8WithLf: Uint8Array
  readonly protocolConfigReceiptSha256: typeof S2S_PROTOCOL_CONFIG_RECEIPT_SHA256
  readonly protocolConfigDocumentSha256: typeof S2S_PROTOCOL_CONFIG_DOCUMENT_SHA256
  readonly workload: {
    readonly adjudicationOptimizerRefitAllowed: false
    readonly armOrder: readonly ["T16", "P_CAP18", "DS870"]
    readonly cellCount: 60
    readonly domainWorldCountPerTask: 15_625
    readonly drawIndices: ReadonlyArray<number>
    readonly fitExecutionCount: 60
    readonly optimizerExecutionCount: 120
    readonly replayExecutionCount: 60
    readonly scoreVariantCount: 8
    readonly taskCount: 20
    readonly testEvaluationCount: 20
    readonly testMaterializationPolicy: "AFTER_ALL_60_FIT_AND_EXACT_REPLAY_CELLS"
    readonly testWorldCountPerTask: 6_250
  }
}

export class ProtocolConfigDocumentError extends Data.TaggedError(
  "ProtocolConfigDocumentError"
)<{
  readonly reason:
    | "ADOPTED_DOCUMENT_HASH_MISMATCH"
    | "ADOPTED_DOCUMENT_NOT_CANONICAL"
    | "ADOPTED_DOCUMENT_PARSE_FAILED"
}> {}

export const S2S_GOLDEN_CONFIRM_REQUEST_SHA256 =
  "16e4965054165863add0395397cbf3d68d1f3d472b7fc303e40056855368b1d1" as const

export const S2S_GOLDEN_CONFIRM_REQUEST_DOCUMENT_SHA256 =
  "294eb438fe042238bbe725d0473765f3634eb57876e5cae4807915db66034237" as const

export interface PythonNumericConfirmRequestFile {
  readonly schemaVersion: "hswm-swm0w-s2s-numeric-confirm-request/v1"
  readonly requestSha256: S2SSha256
  readonly canonicalUtf8WithLf: Uint8Array
  readonly rawBytesSha256: S2SSha256
}

export const makePythonNumericConfirmInvocation = (
  externalSeedHex: S2SSha256,
  protocolConfigCanonicalUtf8WithLf: Uint8Array
): Either.Either<PythonNumericConfirmInvocation, ProtocolConfigDocumentError> => {
  if (
    rawS2SFileSha256(protocolConfigCanonicalUtf8WithLf) !==
    S2S_PROTOCOL_CONFIG_DOCUMENT_SHA256
  ) {
    return Either.left(
      new ProtocolConfigDocumentError({
        reason: "ADOPTED_DOCUMENT_HASH_MISMATCH"
      })
    )
  }
  return Either.right(
    Object.freeze({
      schemaVersion: "hswm-swm0w-s2s-numeric-confirm-request/v1",
      externalSeedHex,
      protocolConfigCanonicalUtf8WithLf: Uint8Array.from(
        protocolConfigCanonicalUtf8WithLf
      ),
      protocolConfigReceiptSha256: S2S_PROTOCOL_CONFIG_RECEIPT_SHA256,
      protocolConfigDocumentSha256: S2S_PROTOCOL_CONFIG_DOCUMENT_SHA256,
      workload: Object.freeze({
        adjudicationOptimizerRefitAllowed: false,
        armOrder: Object.freeze(["T16", "P_CAP18", "DS870"] as const),
        cellCount: 60,
        domainWorldCountPerTask: 15_625,
        drawIndices: Object.freeze(Array.from({ length: 20 }, (_, index) => index)),
        fitExecutionCount: 60,
        optimizerExecutionCount: 120,
        replayExecutionCount: 60,
        scoreVariantCount: 8,
        taskCount: 20,
        testEvaluationCount: 20,
        testMaterializationPolicy:
          "AFTER_ALL_60_FIT_AND_EXACT_REPLAY_CELLS",
        testWorldCountPerTask: 6_250
      })
    })
  )
}

/** Build the exact Python wire request; callers cannot substitute config. */
export const buildPythonNumericConfirmRequest = (
  externalSeedHex: S2SSha256,
  adoptedProtocolConfigCanonicalUtf8WithLf: Uint8Array
): Either.Either<
  PythonNumericConfirmRequestFile,
  ProtocolConfigDocumentError
> => {
  const invocation = makePythonNumericConfirmInvocation(
    externalSeedHex,
    adoptedProtocolConfigCanonicalUtf8WithLf
  )
  if (Either.isLeft(invocation)) return Either.left(invocation.left)

  let protocolConfig: unknown
  try {
    const text = new TextDecoder("utf-8", { fatal: true }).decode(
      adoptedProtocolConfigCanonicalUtf8WithLf
    )
    protocolConfig = JSON.parse(text.slice(0, -1))
  } catch {
    return Either.left(
      new ProtocolConfigDocumentError({
        reason: "ADOPTED_DOCUMENT_PARSE_FAILED"
      })
    )
  }
  const canonicalConfig = canonicalS2SControlJsonBytes(protocolConfig)
  if (
    Either.isLeft(canonicalConfig) ||
    canonicalConfig.right.byteLength !==
      adoptedProtocolConfigCanonicalUtf8WithLf.byteLength ||
    !canonicalConfig.right.every(
      (byte, index) =>
        byte === adoptedProtocolConfigCanonicalUtf8WithLf[index]
    )
  ) {
    return Either.left(
      new ProtocolConfigDocumentError({
        reason: "ADOPTED_DOCUMENT_NOT_CANONICAL"
      })
    )
  }
  const unsigned = {
    canonical_encoding: "ASCII_CANONICAL_UTF8_JSON_PLUS_SINGLE_LF",
    external_seed_hex: externalSeedHex,
    protocol_config: protocolConfig,
    protocol_config_receipt_sha256: S2S_PROTOCOL_CONFIG_RECEIPT_SHA256,
    schema_version: "hswm-swm0w-s2s-numeric-confirm-request/v1",
    workload: {
      adjudication_optimizer_refit_allowed: false,
      arm_order: ["T16", "P_CAP18", "DS870"],
      cell_count: 60,
      domain_world_count_per_task: 15_625,
      draw_indices: Array.from({ length: 20 }, (_, index) => index),
      fit_execution_count: 60,
      optimizer_execution_count: 120,
      replay_execution_count: 60,
      score_variant_count: 8,
      task_count: 20,
      test_evaluation_count: 20,
      test_materialization_policy:
        "AFTER_ALL_60_FIT_AND_EXACT_REPLAY_CELLS",
      test_world_count_per_task: 6_250
    }
  }
  const requestReceipt = canonicalS2SControlSha256(unsigned)
  if (Either.isLeft(requestReceipt)) {
    return Either.left(
      new ProtocolConfigDocumentError({
        reason: "ADOPTED_DOCUMENT_NOT_CANONICAL"
      })
    )
  }
  const requestBytes = canonicalS2SControlJsonBytes({
    ...unsigned,
    request_sha256: requestReceipt.right
  })
  if (Either.isLeft(requestBytes)) {
    return Either.left(
      new ProtocolConfigDocumentError({
        reason: "ADOPTED_DOCUMENT_NOT_CANONICAL"
      })
    )
  }
  return Either.right(
    Object.freeze({
      schemaVersion: "hswm-swm0w-s2s-numeric-confirm-request/v1",
      requestSha256: S2SSha256Schema.make(requestReceipt.right),
      canonicalUtf8WithLf: requestBytes.right,
      rawBytesSha256: S2SSha256Schema.make(
        rawS2SFileSha256(requestBytes.right)
      )
    })
  )
}

export class PythonNumericOracleError extends Data.TaggedError(
  "PythonNumericOracleError"
)<{
  readonly operation: "BUILD_CANDIDATE" | "REPLAY_CANDIDATE"
  readonly reason:
    | "INTERRUPTED_OR_TIMED_OUT"
    | "NONZERO_EXIT"
    | "OUTPUT_CONTRACT_REJECTED"
    | "SPAWN_FAILED"
}> {}

/** Internal numeric-only capability. No Git, GitHub, drand, time, or RSS. */
export class PythonNumericOracle extends Context.Tag(
  "hswm/S2S/PythonNumericOracle"
)<
  PythonNumericOracle,
  {
    readonly buildCandidate: (
      request: PythonNumericConfirmRequestFile
    ) => Effect.Effect<OpaqueNumericFile, PythonNumericOracleError>
    readonly replayCandidate: (
      candidate: OpaqueNumericFile
    ) => Effect.Effect<OpaqueNumericFile, PythonNumericOracleError>
  }
>() {}

export class VerifiedPulseSourceError extends Data.TaggedError(
  "VerifiedPulseSourceError"
)<{
  readonly reason: "INTERRUPTED_OR_TIMED_OUT" | "PULSE_REJECTED" | "SOURCE_FAILED"
}> {}

export class VerifiedPulseSource extends Context.Tag(
  "hswm/S2S/VerifiedPulseSource"
)<
  VerifiedPulseSource,
  {
    readonly acquire: (request: {
      readonly beaconId: "quicknet"
      readonly beaconChainHashHex: S2SSha256
      readonly futureRound: number
      readonly futureRoundCommitmentSelfHashSha256: S2SSha256
    }) => Effect.Effect<unknown, VerifiedPulseSourceError>
  }
>() {}

export class ConfirmatoryArtifactStoreError extends Data.TaggedError(
  "ConfirmatoryArtifactStoreError"
)<{
  readonly operation: "PUBLISH" | "READ_BACK"
  readonly reason: "INTERRUPTED_OR_TIMED_OUT" | "STORE_FAILED" | "VERIFY_FAILED"
}> {}

export class ConfirmatoryArtifactStore extends Context.Tag(
  "hswm/S2S/ConfirmatoryArtifactStore"
)<
  ConfirmatoryArtifactStore,
  {
    readonly publish: (request: {
      readonly artifactName: string
      readonly exactMembers: ReadonlyArray<{
        readonly name: string
        readonly bytes: Uint8Array
      }>
    }) => Effect.Effect<unknown, ConfirmatoryArtifactStoreError>
    readonly readBack: (request: {
      readonly artifactId: S2SArtifactId
      readonly expectedArchiveSha256: S2SSha256
    }) => Effect.Effect<unknown, ConfirmatoryArtifactStoreError>
  }
>() {}

export class RunEvidenceStoreError extends Data.TaggedError(
  "RunEvidenceStoreError"
)<{
  readonly reason: "STORE_UNAVAILABLE"
}> {}

export class RunEvidenceStore extends Context.Tag("hswm/S2S/RunEvidenceStore")<
  RunEvidenceStore,
  {
    readonly persist: (record: {
      readonly experimentId: string
      readonly sourceCommitA: S2SGitCommitSha
      readonly registrationCommitB: S2SGitCommitSha
      readonly controlReceiptSha256: S2SSha256
      readonly phase: S2SConfirmatoryPhase
    }) => Effect.Effect<void, RunEvidenceStoreError>
  }
>() {}

export interface S2SControlJournalRecord {
  readonly sequence: number
  readonly previousPhase: S2SConfirmatoryPhase
  readonly nextPhase: S2SConfirmatoryPhase
  readonly controlReceiptSha256: S2SSha256
  readonly event: S2SConfirmatoryEvent
}

export class S2SConfirmatoryControlPlane extends Context.Tag(
  "hswm/S2S/ConfirmatoryControlPlane"
)<
  S2SConfirmatoryControlPlane,
  {
    readonly snapshot: Effect.Effect<S2SConfirmatoryState>
    readonly history: Effect.Effect<ReadonlyArray<S2SControlJournalRecord>>
    readonly submit: (
      input: unknown
    ) => Effect.Effect<
      S2SConfirmatoryState,
      ParseResult.ParseError | S2SConfirmatoryTransitionError
    >
  }
>() {}

interface InMemoryControlState {
  readonly state: S2SConfirmatoryState
  readonly journal: ReadonlyArray<S2SControlJournalRecord>
}

type ControlAttempt =
  | { readonly _tag: "Advanced"; readonly state: S2SConfirmatoryState }
  | { readonly _tag: "Rejected"; readonly error: S2SConfirmatoryTransitionError }

const cloneState = (state: S2SConfirmatoryState): S2SConfirmatoryState =>
  structuredClone(state)

const cloneJournal = (
  journal: ReadonlyArray<S2SControlJournalRecord>
): ReadonlyArray<S2SControlJournalRecord> => structuredClone(journal)

/**
 * In-process simulation only. GitHub's three jobs must reconstruct from
 * immutable hash-linked artifacts and fresh API/readback evidence; this Ref is
 * not durable cross-job truth and does not imply exactly-once external work.
 */
export const makeS2SConfirmatoryControlPlaneMemoryForTest = () =>
  Layer.effect(
    S2SConfirmatoryControlPlane,
    Effect.gen(function* () {
      const store = yield* Ref.make<InMemoryControlState>({
        state: initialS2SConfirmatoryState(),
        journal: Object.freeze([])
      })
      return S2SConfirmatoryControlPlane.of({
        snapshot: Ref.get(store).pipe(
          Effect.map(({ state }) => cloneState(state))
        ),
        history: Ref.get(store).pipe(
          Effect.map(({ journal }) => cloneJournal(journal))
        ),
        submit: (input) =>
          Effect.gen(function* () {
            const event = yield* decodeS2SConfirmatoryEvent(input)
            const attempt = yield* Ref.modify(
              store,
              (
                current
              ): readonly [ControlAttempt, InMemoryControlState] => {
                const transition = advanceS2SConfirmatory(current.state, event)
                if (Either.isLeft(transition)) {
                  return [
                    { _tag: "Rejected", error: transition.left },
                    current
                  ]
                }
                const next = transition.right
                const record: S2SControlJournalRecord = Object.freeze({
                  sequence: current.journal.length,
                  previousPhase: current.state._tag,
                  nextPhase: next._tag,
                  controlReceiptSha256: next.latestControlReceiptSha256,
                  event
                })
                return [
                  { _tag: "Advanced", state: next },
                  {
                    state: next,
                    journal: Object.freeze([...current.journal, record])
                  }
                ]
              }
            )
            if (attempt._tag === "Rejected") {
              return yield* Effect.fail(attempt.error)
            }
            return cloneState(attempt.state)
          })
      })
    })
  )
