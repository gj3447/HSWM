import { Data, Effect, Either } from "effect"

import { rawS2SFileSha256 } from "./s2s-canonical.js"
import { S2SSha256Schema } from "./s2s-confirmatory.js"
import {
  S2SPythonGoldenVerifier,
  S2SPythonNumericExecutor,
  validateS2SPythonRssTelemetryBytes,
  type S2SPythonGoldenVerificationError,
  type S2SPythonNumericExecutionError,
  type S2SPythonNumericOperation,
  type S2SPythonNumericOutput,
  type S2SPythonRuntimeSourceIdentityReceipt
} from "./s2s-live-python.js"
import {
  buildPythonNumericConfirmRequest,
  makeOpaqueNumericFile,
  projectOpaqueNumericAdjudication,
  type NumericAdjudicationProjection,
  type NumericAdjudicationProjectionError,
  type OpaqueNumericFileError,
  type OpaqueNumericFile,
  type ProtocolConfigDocumentError
} from "./s2s-orchestration.js"
import {
  bindS2SPythonExecutionEvidence,
  S2SPythonExecutionEvidenceError
} from "./s2s-python-evidence.js"
import {
  loadS2SAdoptedProtocolConfigAsset,
  type S2SAdoptedProtocolConfigAssetError
} from "./s2s-protocol-config-asset.js"
import {
  S2STestOnlyGoldenArtifactStore,
  type S2STestOnlyGoldenArtifactPublicationReceipt,
  type S2STestOnlyGoldenArtifactReadback,
  type S2STestOnlyGoldenArtifactStoreError
} from "./s2s-test-only-golden-artifact-store.js"
import {
  S2S_TEST_ONLY_GOLDEN_ARTIFACT_SPECS,
  reconstructS2STestOnlyGoldenUploadPostcondition,
  type S2STestOnlyGoldenMemberName,
  type S2STestOnlyGoldenRole
} from "./s2s-test-only-golden-upload.js"

const GOLDEN_EXTERNAL_SEED_HEX = S2SSha256Schema.make(
  "552e51d2ff75cb7c5df5b55a166aba12a277c2813bbdd69bc825286e7c26b6f0"
)

export const S2S_GOLDEN_NUMERIC_DRY_RUN_SUMMARY_SCHEMA_VERSION =
  "hswm-swm0w-s2s-test-only-golden-numeric-dry-run-summary/v1" as const

export interface S2SGoldenNumericStageHashSummary {
  readonly inputRawBytesSha256: string
  readonly outputRawBytesSha256: string
  readonly runtimeSourceIdentityReceiptSha256: string
  readonly rssTelemetryRawSha256: string
}

export interface S2SGoldenArtifactBindingSummary {
  readonly role: S2STestOnlyGoldenRole
  readonly publicationKey: string
  readonly archiveSha256: string
  readonly archiveByteLength: number
  readonly postconditionPublicationKey: string
  readonly postconditionSha256: string
  readonly postconditionByteLength: number
  readonly memberName: S2STestOnlyGoldenMemberName
  readonly memberRawSha256: string
  readonly memberByteLength: number
}

export interface S2SGoldenNumericDryRunVoid {
  readonly _tag: "S2SGoldenNumericDryRunVoid"
  readonly schemaVersion: typeof S2S_GOLDEN_NUMERIC_DRY_RUN_SUMMARY_SCHEMA_VERSION
  readonly classification: "TEST_ONLY_NON_AUTHORIZING"
  readonly origin: "LOCAL_TEST_LAYER"
  readonly status: "NUMERIC_OUTCOME_VOID"
  readonly confirmEvidenceReceiptSha256: string
  readonly candidateArtifact: S2SGoldenArtifactBindingSummary
  readonly confirm: S2SGoldenNumericStageHashSummary
  readonly adjudicate: S2SGoldenNumericStageHashSummary
}

export interface S2SGoldenNumericDryRunCompleted {
  readonly _tag: "S2SGoldenNumericDryRunCompleted"
  readonly schemaVersion: typeof S2S_GOLDEN_NUMERIC_DRY_RUN_SUMMARY_SCHEMA_VERSION
  readonly classification: "TEST_ONLY_NON_AUTHORIZING"
  readonly origin: "LOCAL_TEST_LAYER"
  readonly scientificStatus: "NUMERIC_CANDIDATE_ONLY_UNJUDGED"
  readonly numericCandidateOutcome: NumericAdjudicationProjection["numericCandidateOutcome"]
  readonly numericCandidateReasonCodes: ReadonlyArray<string>
  readonly confirmEvidenceReceiptSha256: string
  readonly adjudicationEvidenceReceiptSha256: string
  readonly candidateArtifact: S2SGoldenArtifactBindingSummary
  readonly adjudicationArtifact: S2SGoldenArtifactBindingSummary
  readonly confirm: S2SGoldenNumericStageHashSummary
  readonly adjudicate: S2SGoldenNumericStageHashSummary
}

export type S2SGoldenNumericDryRunResult =
  | S2SGoldenNumericDryRunVoid
  | S2SGoldenNumericDryRunCompleted

export type S2SGoldenNumericDryRunFailure =
  | S2SAdoptedProtocolConfigAssetError
  | ProtocolConfigDocumentError
  | S2SPythonGoldenVerificationError
  | S2SPythonNumericExecutionError
  | S2SPythonExecutionEvidenceError
  | OpaqueNumericFileError
  | NumericAdjudicationProjectionError
  | S2STestOnlyGoldenArtifactStoreError
  | S2SGoldenNumericDryRunError

export class S2SGoldenNumericDryRunError extends Data.TaggedError(
  "S2SGoldenNumericDryRunError"
)<{
  readonly reason:
    | "READBACK_MISMATCH"
    | "RECOVERY_MISMATCH"
    | "RUNTIME_IDENTITY_MISMATCH"
  readonly detail: string
}> {}

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((byte, index) => byte === right[index])

const failDryRun = (
  reason: S2SGoldenNumericDryRunError["reason"],
  detail: string
): S2SGoldenNumericDryRunError =>
  new S2SGoldenNumericDryRunError({ reason, detail })

interface ValidatedArtifactBindingSnapshot {
  readonly summary: S2SGoldenArtifactBindingSummary
  readonly archiveBytes: Uint8Array
  readonly postconditionArchiveBytes: Uint8Array
  readonly postconditionDocumentBytes: Uint8Array
  readonly memberBytes: Uint8Array
}

const validateArtifactBinding = (
  receipt: S2STestOnlyGoldenArtifactPublicationReceipt,
  readback: S2STestOnlyGoldenArtifactReadback,
  expectedRole: S2STestOnlyGoldenRole,
  expectedMemberName: S2STestOnlyGoldenMemberName,
  expectedMemberBytes: Uint8Array,
  mismatchReason: "READBACK_MISMATCH" | "RECOVERY_MISMATCH"
): Either.Either<
  ValidatedArtifactBindingSnapshot,
  S2SGoldenNumericDryRunError
> => {
  const spec = S2S_TEST_ONLY_GOLDEN_ARTIFACT_SPECS[expectedRole]
  let receiptArchive: Uint8Array
  let readbackArchive: Uint8Array
  let postconditionArchive: Uint8Array
  let postconditionDocument: Uint8Array
  let memberBytes: Uint8Array
  try {
    receiptArchive = Uint8Array.from(receipt.readArchiveBytes())
    readbackArchive = Uint8Array.from(readback.readArchiveBytes())
    postconditionArchive = Uint8Array.from(
      readback.readPostconditionArchiveBytes()
    )
    postconditionDocument = Uint8Array.from(
      readback.readPostconditionDocumentBytes()
    )
    memberBytes = Uint8Array.from(readback.member.readBytes())
  } catch {
    return Either.left(
      failDryRun(
        mismatchReason,
        "golden receipt or readback bytes could not be snapshotted"
      )
    )
  }
  const reconstructedPostcondition =
    reconstructS2STestOnlyGoldenUploadPostcondition(postconditionArchive, {
      role: expectedRole,
      publicationKey: spec.publicationKey,
      publicationDisposition: "CREATED",
      archiveBytes: receiptArchive,
      readbackBytes: readbackArchive
    })
  if (
    Either.isLeft(reconstructedPostcondition) ||
    (Either.isRight(reconstructedPostcondition) &&
      (!sameBytes(
        reconstructedPostcondition.right.readArchiveBytes(),
        postconditionArchive
      ) ||
        !sameBytes(
          reconstructedPostcondition.right.readDocumentBytes(),
          postconditionDocument
        )))
  ) {
    return Either.left(
      failDryRun(
        mismatchReason,
        "golden upload postcondition could not be independently reconstructed"
      )
    )
  }
  if (
    receipt._tag !== "S2STestOnlyGoldenArtifactPublicationReceipt" ||
    receipt.classification !== "TEST_ONLY_NON_AUTHORIZING" ||
    receipt.origin !== "LOCAL_TEST_LAYER" ||
    receipt.disposition !== "CREATED" ||
    receipt.role !== expectedRole ||
    readback._tag !== "S2STestOnlyGoldenArtifactReadback" ||
    readback.classification !== "TEST_ONLY_NON_AUTHORIZING" ||
    readback.origin !== "LOCAL_TEST_LAYER" ||
    readback.role !== expectedRole ||
    receipt.publicationKey !== spec.publicationKey ||
    readback.publicationKey !== spec.publicationKey ||
    receipt.postconditionPublicationKey !== spec.postconditionPublicationKey ||
    readback.postconditionPublicationKey !== spec.postconditionPublicationKey ||
    receipt.archiveSha256 !== readback.archiveSha256 ||
    receipt.archiveByteLength !== readback.archiveByteLength ||
    receipt.postconditionSha256 !== readback.postconditionSha256 ||
    receipt.postconditionByteLength !== readback.postconditionByteLength ||
    receipt.archiveSha256 !== rawS2SFileSha256(receiptArchive) ||
    readback.archiveSha256 !== rawS2SFileSha256(readbackArchive) ||
    readback.postconditionSha256 !== rawS2SFileSha256(postconditionArchive) ||
    receipt.archiveByteLength !== receiptArchive.byteLength ||
    readback.archiveByteLength !== readbackArchive.byteLength ||
    readback.postconditionByteLength !== postconditionArchive.byteLength ||
    postconditionDocument.byteLength < 1 ||
    readback.member.name !== expectedMemberName ||
    readback.member.rawSha256 !== rawS2SFileSha256(memberBytes) ||
    readback.member.byteLength !== memberBytes.byteLength ||
    !sameBytes(receiptArchive, readbackArchive) ||
    !sameBytes(memberBytes, expectedMemberBytes)
  ) {
    return Either.left(
      failDryRun(
        mismatchReason,
        "golden publication receipt, postcondition, member, and readback bindings diverged"
      )
    )
  }
  return Either.right(
    Object.freeze({
      summary: Object.freeze({
        role: expectedRole,
        publicationKey: readback.publicationKey,
        archiveSha256: readback.archiveSha256,
        archiveByteLength: readback.archiveByteLength,
        postconditionPublicationKey: readback.postconditionPublicationKey,
        postconditionSha256: readback.postconditionSha256,
        postconditionByteLength: readback.postconditionByteLength,
        memberName: expectedMemberName,
        memberRawSha256: readback.member.rawSha256,
        memberByteLength: readback.member.byteLength
      }),
      archiveBytes: receiptArchive,
      postconditionArchiveBytes: postconditionArchive,
      postconditionDocumentBytes: postconditionDocument,
      memberBytes
    })
  )
}

const sameArtifactBindingSnapshots = (
  left: ValidatedArtifactBindingSnapshot,
  right: ValidatedArtifactBindingSnapshot
): boolean =>
  left.summary.role === right.summary.role &&
  left.summary.publicationKey === right.summary.publicationKey &&
  left.summary.archiveSha256 === right.summary.archiveSha256 &&
  left.summary.archiveByteLength === right.summary.archiveByteLength &&
  left.summary.postconditionPublicationKey ===
    right.summary.postconditionPublicationKey &&
  left.summary.postconditionSha256 === right.summary.postconditionSha256 &&
  left.summary.postconditionByteLength ===
    right.summary.postconditionByteLength &&
  left.summary.memberName === right.summary.memberName &&
  left.summary.memberRawSha256 === right.summary.memberRawSha256 &&
  left.summary.memberByteLength === right.summary.memberByteLength &&
  sameBytes(left.archiveBytes, right.archiveBytes) &&
  sameBytes(left.postconditionArchiveBytes, right.postconditionArchiveBytes) &&
  sameBytes(
    left.postconditionDocumentBytes,
    right.postconditionDocumentBytes
  ) &&
  sameBytes(left.memberBytes, right.memberBytes)

const snapshotRuntimeIdentityBytes = (
  identity: S2SPythonRuntimeSourceIdentityReceipt
): Either.Either<Uint8Array, S2SGoldenNumericDryRunError> => {
  try {
    const bytes = identity.readCanonicalBytes()
    if (!(bytes instanceof Uint8Array) || bytes.byteLength < 1) {
      return Either.left(
        failDryRun(
          "RUNTIME_IDENTITY_MISMATCH",
          "runtime/source identity did not expose non-empty canonical bytes"
        )
      )
    }
    return Either.right(Uint8Array.from(bytes))
  } catch {
    return Either.left(
      failDryRun(
        "RUNTIME_IDENTITY_MISMATCH",
        "runtime/source identity bytes could not be snapshotted"
      )
    )
  }
}

interface ValidatedNumericOutputSnapshot {
  readonly file: OpaqueNumericFile
  readonly summary: S2SGoldenNumericStageHashSummary
}

const independentlyValidateNumericOutput = (
  output: S2SPythonNumericOutput,
  operation: S2SPythonNumericOperation,
  expectedInputRawBytesSha256: string,
  expectedRuntimeSourceIdentityReceiptSha256: string
): Either.Either<
  ValidatedNumericOutputSnapshot,
  | S2SPythonExecutionEvidenceError
  | S2SPythonNumericExecutionError
  | OpaqueNumericFileError
> => {
  const expectedMemberName =
    operation === "CONFIRM"
      ? ("numeric_candidate.json" as const)
      : ("numeric_adjudication.json" as const)
  const expectedSchemaVersion =
    operation === "CONFIRM"
      ? ("hswm-swm0w-s2s-numeric-candidate/v1" as const)
      : ("hswm-swm0w-s2s-numeric-adjudication/v1" as const)
  let bytes: Uint8Array
  let rssBytes: Uint8Array
  try {
    bytes = Uint8Array.from(output.readCanonicalBytes())
    rssBytes = Uint8Array.from(output.readRssTelemetryCanonicalBytes())
  } catch {
    return Either.left(
      new S2SPythonExecutionEvidenceError({
        reason: "EXECUTOR_OUTPUT_DRIFT",
        detail: "executor output bytes could not be snapshotted"
      })
    )
  }
  const telemetry = validateS2SPythonRssTelemetryBytes(operation, rssBytes)
  if (Either.isLeft(telemetry)) return Either.left(telemetry.left)
  if (
    output.operation !== operation ||
    output.memberName !== expectedMemberName ||
    output.inputRawBytesSha256 !== expectedInputRawBytesSha256 ||
    output.runtimeSourceIdentityReceiptSha256 !==
      expectedRuntimeSourceIdentityReceiptSha256 ||
    output.byteLength !== bytes.byteLength ||
    output.rawBytesSha256 !== rawS2SFileSha256(bytes) ||
    !Number.isSafeInteger(output.commandElapsedNanoseconds) ||
    output.commandElapsedNanoseconds < 1 ||
    output.peakRssKiB !== telemetry.right.peakRssKiB ||
    output.rssTelemetryRawSha256 !== telemetry.right.rawBytesSha256
  ) {
    return Either.left(
      new S2SPythonExecutionEvidenceError({
        reason: "EXECUTOR_OUTPUT_DRIFT",
        detail: "executor output identity, runtime, or RSS binding drifted"
      })
    )
  }
  const file = makeOpaqueNumericFile(
    expectedMemberName,
    expectedSchemaVersion,
    bytes,
    output.rawBytesSha256
  )
  if (Either.isLeft(file)) return Either.left(file.left)
  return Either.right(
    Object.freeze({
      file: file.right,
      summary: Object.freeze({
        inputRawBytesSha256: output.inputRawBytesSha256,
        outputRawBytesSha256: output.rawBytesSha256,
        runtimeSourceIdentityReceiptSha256:
          output.runtimeSourceIdentityReceiptSha256,
        rssTelemetryRawSha256: output.rssTelemetryRawSha256
      })
    })
  )
}

const frozenBase = () => ({
  schemaVersion: S2S_GOLDEN_NUMERIC_DRY_RUN_SUMMARY_SCHEMA_VERSION,
  classification: "TEST_ONLY_NON_AUTHORIZING" as const,
  origin: "LOCAL_TEST_LAYER" as const
})

/**
 * Root-private, lazy test-only composition. It does not synthesize production
 * lifecycle authority, events, carriers, profiles, durable evidence, or verdicts.
 */
const program: Effect.Effect<
  S2SGoldenNumericDryRunResult,
  S2SGoldenNumericDryRunFailure,
  | S2SPythonGoldenVerifier
  | S2SPythonNumericExecutor
  | S2STestOnlyGoldenArtifactStore
> = Effect.gen(function* () {
  const asset = yield* loadS2SAdoptedProtocolConfigAsset
  const requestResult = buildPythonNumericConfirmRequest(
    GOLDEN_EXTERNAL_SEED_HEX,
    asset.readCanonicalBytes()
  )
  if (Either.isLeft(requestResult)) return yield* requestResult.left
  const request = requestResult.right

  const verifier = yield* S2SPythonGoldenVerifier
  const executor = yield* S2SPythonNumericExecutor
  const store = yield* S2STestOnlyGoldenArtifactStore
  const verification = yield* verifier.verify
  const verifierIdentityBytes = snapshotRuntimeIdentityBytes(
    verifier.runtimeSourceIdentity
  )
  if (Either.isLeft(verifierIdentityBytes)) return yield* verifierIdentityBytes.left
  const executorIdentityBytes = snapshotRuntimeIdentityBytes(
    executor.runtimeSourceIdentity
  )
  if (Either.isLeft(executorIdentityBytes)) return yield* executorIdentityBytes.left
  if (
    verification.runtimeSourceIdentityReceiptSha256 !==
      verifier.runtimeSourceIdentity.receiptSha256 ||
    verifier.runtimeSourceIdentity.receiptSha256 !==
      executor.runtimeSourceIdentity.receiptSha256 ||
    !sameBytes(verifierIdentityBytes.right, executorIdentityBytes.right)
  ) {
    return yield* failDryRun(
      "RUNTIME_IDENTITY_MISMATCH",
      "golden verifier and numeric executor must share one exact runtime/source receipt"
    )
  }

  const confirmOutput = yield* executor.confirm(
    Uint8Array.from(request.canonicalUtf8WithLf)
  )
  const confirmBinding = bindS2SPythonExecutionEvidence({
    output: confirmOutput,
    runtimeSourceIdentity: executor.runtimeSourceIdentity,
    requestDocumentSha256: request.rawBytesSha256,
    requestSelfSha256: request.requestSha256
  })
  if (Either.isLeft(confirmBinding)) return yield* confirmBinding.left
  const confirmSnapshot = independentlyValidateNumericOutput(
    confirmOutput,
    "CONFIRM",
    request.rawBytesSha256,
    executor.runtimeSourceIdentity.receiptSha256
  )
  if (Either.isLeft(confirmSnapshot)) return yield* confirmSnapshot.left

  const candidateReceipt = yield* store.publishGoldenArtifact(
    "GOLDEN_CANDIDATE",
    [
      {
        name: "numeric_candidate.json",
        bytes: Uint8Array.from(
          confirmSnapshot.right.file.canonicalUtf8WithLf
        )
      }
    ]
  )
  const candidateFirst = yield* store.readBackGoldenArtifact(candidateReceipt)
  const candidateSecond = yield* store.readBackGoldenArtifact(candidateReceipt)

  const candidateFirstBinding = validateArtifactBinding(
    candidateReceipt,
    candidateFirst,
    "GOLDEN_CANDIDATE",
    "numeric_candidate.json",
    confirmSnapshot.right.file.canonicalUtf8WithLf,
    "READBACK_MISMATCH"
  )
  if (Either.isLeft(candidateFirstBinding)) {
    return yield* candidateFirstBinding.left
  }
  const candidateSecondBinding = validateArtifactBinding(
    candidateReceipt,
    candidateSecond,
    "GOLDEN_CANDIDATE",
    "numeric_candidate.json",
    confirmSnapshot.right.file.canonicalUtf8WithLf,
    "READBACK_MISMATCH"
  )
  if (Either.isLeft(candidateSecondBinding)) {
    return yield* candidateSecondBinding.left
  }
  if (
    !sameArtifactBindingSnapshots(
      candidateFirstBinding.right,
      candidateSecondBinding.right
    )
  ) {
    return yield* failDryRun(
      "READBACK_MISMATCH",
      "two independent candidate readbacks must exactly match the published candidate"
    )
  }
  const candidateRecovered =
    yield* store.recoverGoldenArtifactWithFreshLayer(candidateReceipt)
  const candidateRecoveryBinding = validateArtifactBinding(
    candidateReceipt,
    candidateRecovered,
    "GOLDEN_CANDIDATE",
    "numeric_candidate.json",
    confirmSnapshot.right.file.canonicalUtf8WithLf,
    "RECOVERY_MISMATCH"
  )
  if (Either.isLeft(candidateRecoveryBinding)) {
    return yield* candidateRecoveryBinding.left
  }
  if (
    !sameArtifactBindingSnapshots(
      candidateSecondBinding.right,
      candidateRecoveryBinding.right
    )
  ) {
    return yield* failDryRun(
      "RECOVERY_MISMATCH",
      "fresh candidate recovery must exactly match the second direct readback"
    )
  }

  // Adjudication is deliberately fed by the second direct readback, not the
  // recovery result; recovery is an independent prerequisite observation.
  const adjudicationInput = Uint8Array.from(
    candidateSecondBinding.right.memberBytes
  )
  const adjudicationOutput = yield* executor.adjudicate(adjudicationInput)
  const adjudicationSnapshot = independentlyValidateNumericOutput(
    adjudicationOutput,
    "ADJUDICATE",
    rawS2SFileSha256(adjudicationInput),
    executor.runtimeSourceIdentity.receiptSha256
  )
  if (Either.isLeft(adjudicationSnapshot)) {
    return yield* adjudicationSnapshot.left
  }
  const projection = projectOpaqueNumericAdjudication(
    adjudicationSnapshot.right.file,
    confirmOutput.rawBytesSha256,
    request.requestSha256
  )
  if (Either.isLeft(projection)) {
    if (projection.left.reason === "NUMERIC_OUTCOME_VOID") {
      return Object.freeze({
        _tag: "S2SGoldenNumericDryRunVoid" as const,
        ...frozenBase(),
        status: "NUMERIC_OUTCOME_VOID" as const,
        confirmEvidenceReceiptSha256:
          confirmBinding.right.evidence.receiptSha256,
        candidateArtifact: candidateRecoveryBinding.right.summary,
        confirm: confirmSnapshot.right.summary,
        adjudicate: adjudicationSnapshot.right.summary
      })
    }
    return yield* projection.left
  }

  const adjudicationBinding = bindS2SPythonExecutionEvidence({
    output: adjudicationOutput,
    runtimeSourceIdentity: executor.runtimeSourceIdentity,
    requestDocumentSha256: projection.right.numericCandidateDocumentSha256,
    requestSelfSha256: projection.right.numericCandidateReceiptSha256
  })
  if (Either.isLeft(adjudicationBinding)) {
    return yield* adjudicationBinding.left
  }
  const adjudicationReceipt = yield* store.publishGoldenArtifact(
    "GOLDEN_ADJUDICATION",
    [
      {
        name: "numeric_adjudication.json",
        bytes: Uint8Array.from(
          adjudicationSnapshot.right.file.canonicalUtf8WithLf
        )
      }
    ]
  )
  const adjudicationReadback = yield* store.readBackGoldenArtifact(
    adjudicationReceipt
  )
  const adjudicationArtifactBinding = validateArtifactBinding(
    adjudicationReceipt,
    adjudicationReadback,
    "GOLDEN_ADJUDICATION",
    "numeric_adjudication.json",
    adjudicationSnapshot.right.file.canonicalUtf8WithLf,
    "READBACK_MISMATCH"
  )
  if (Either.isLeft(adjudicationArtifactBinding)) {
    return yield* adjudicationArtifactBinding.left
  }
  const adjudicationRecovered =
    yield* store.recoverGoldenArtifactWithFreshLayer(adjudicationReceipt)
  const adjudicationRecoveryBinding = validateArtifactBinding(
    adjudicationReceipt,
    adjudicationRecovered,
    "GOLDEN_ADJUDICATION",
    "numeric_adjudication.json",
    adjudicationSnapshot.right.file.canonicalUtf8WithLf,
    "RECOVERY_MISMATCH"
  )
  if (Either.isLeft(adjudicationRecoveryBinding)) {
    return yield* adjudicationRecoveryBinding.left
  }
  if (
    !sameArtifactBindingSnapshots(
      adjudicationArtifactBinding.right,
      adjudicationRecoveryBinding.right
    )
  ) {
    return yield* failDryRun(
      "RECOVERY_MISMATCH",
      "fresh adjudication recovery must exactly match its direct readback"
    )
  }
  return Object.freeze({
    _tag: "S2SGoldenNumericDryRunCompleted" as const,
    ...frozenBase(),
    scientificStatus: "NUMERIC_CANDIDATE_ONLY_UNJUDGED" as const,
    numericCandidateOutcome: projection.right.numericCandidateOutcome,
    numericCandidateReasonCodes: Object.freeze([
      ...projection.right.numericCandidateReasonCodes
    ]),
    confirmEvidenceReceiptSha256:
      confirmBinding.right.evidence.receiptSha256,
    adjudicationEvidenceReceiptSha256:
      adjudicationBinding.right.evidence.receiptSha256,
    candidateArtifact: candidateRecoveryBinding.right.summary,
    adjudicationArtifact: adjudicationRecoveryBinding.right.summary,
    confirm: confirmSnapshot.right.summary,
    adjudicate: adjudicationSnapshot.right.summary
  })
})

export const runS2SGoldenNumericDryRun = program
