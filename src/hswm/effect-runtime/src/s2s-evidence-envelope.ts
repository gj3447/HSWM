import { Data, Either, Schema } from "effect"

import {
  canonicalS2SControlJsonBytes,
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "./s2s-canonical.js"
import {
  S2S_CONFIRMATORY_EXPERIMENT_ID,
  S2SGitCommitShaSchema,
  S2SSha256Schema,
  type S2SGitCommitSha,
  type S2SSha256
} from "./s2s-confirmatory.js"
import {
  S2S_CONFIRMATORY_BRANCH,
  S2S_CONFIRMATORY_WORKFLOW_PATH,
  s2sConfirmatoryWorkflowContractSha256
} from "./s2s-workflow-contract.js"

export const S2S_EVIDENCE_ENVELOPE_SCHEMA_VERSION =
  "hswm-swm0w-s2s-evidence-envelope/v1" as const
export const S2S_EVIDENCE_CLAIM_SCHEMA_VERSION =
  "hswm-swm0w-s2s-evidence-claim/v1" as const
export const S2S_EVIDENCE_ENVELOPE_MAX_ATTACHMENTS = 96 as const
export const S2S_EVIDENCE_ENVELOPE_MAX_ATTACHMENT_BYTES =
  64 * 1_048_576
export const S2S_EVIDENCE_ENVELOPE_MAX_TOTAL_ATTACHMENT_BYTES =
  256 * 1_048_576
export const S2S_EVIDENCE_ENVELOPE_MAX_MANIFEST_BYTES = 1_048_576 as const
export const S2S_EVIDENCE_CLAIM_MAX_BYTES = 16_384 as const

/*
 * Structural, content-addressed stage envelope. Attachment-profile completeness
 * is owned by the future closed stage programs; this module alone does not
 * claim that an arbitrary attachment roster is a complete replay closure.
 */

const PositiveSafeIntegerSchema = Schema.Number.pipe(
  Schema.int(),
  Schema.between(1, Number.MAX_SAFE_INTEGER)
)
const NonNegativeSafeIntegerSchema = Schema.Number.pipe(
  Schema.int(),
  Schema.between(0, Number.MAX_SAFE_INTEGER)
)
const StageSchema = Schema.Literal("REGISTER", "CONFIRM", "ADJUDICATE")
const PriorStageSchema = Schema.Literal("REGISTER", "CONFIRM")
const LogicalNameSchema = Schema.String.pipe(
  Schema.pattern(/^[a-z0-9][a-z0-9._/-]{0,255}$/)
)
const AttachmentRoleSchema = Schema.String.pipe(
  Schema.pattern(/^[A-Z][A-Z0-9_]{0,127}$/)
)
const SchemaVersionSchema = Schema.String.pipe(
  Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/)
)
const WorkflowApiPathSchema = Schema.String.pipe(
  Schema.filter(
    (value) =>
      value === S2S_CONFIRMATORY_WORKFLOW_PATH ||
      value === `${S2S_CONFIRMATORY_WORKFLOW_PATH}@${S2S_CONFIRMATORY_BRANCH}`
  )
)
const MediaTypeSchema = Schema.Literal(
  "application/json",
  "application/octet-stream",
  "application/zip"
)

const PredecessorSchema = Schema.Struct({
  stage: PriorStageSchema,
  manifest_raw_sha256: S2SSha256Schema,
  claim_raw_sha256: S2SSha256Schema
})

const AttachmentDescriptorSchema = Schema.Struct({
  logical_name: LogicalNameSchema,
  role: AttachmentRoleSchema,
  schema_version: Schema.NullOr(SchemaVersionSchema),
  media_type: MediaTypeSchema,
  byte_length: PositiveSafeIntegerSchema.pipe(
    Schema.between(1, S2S_EVIDENCE_ENVELOPE_MAX_ATTACHMENT_BYTES)
  ),
  raw_sha256: S2SSha256Schema
})

const EnvelopeDocumentSchema = Schema.Struct({
  schema_version: Schema.Literal(S2S_EVIDENCE_ENVELOPE_SCHEMA_VERSION),
  experiment_id: Schema.Literal(S2S_CONFIRMATORY_EXPERIMENT_ID),
  claim_scope: Schema.Literal("ONE_REGISTRATION_COMMIT_PER_STAGE"),
  source_commit_a: S2SGitCommitShaSchema,
  registration_commit_b: S2SGitCommitShaSchema,
  workflow_run_id: PositiveSafeIntegerSchema,
  workflow_run_attempt: Schema.Literal(1),
  workflow_head_sha: S2SGitCommitShaSchema,
  workflow_run_created_at_unix_seconds: NonNegativeSafeIntegerSchema,
  workflow_api_path: WorkflowApiPathSchema,
  workflow_file_sha256: S2SSha256Schema,
  workflow_contract_sha256: S2SSha256Schema,
  stage: StageSchema,
  current_job_database_id: PositiveSafeIntegerSchema,
  predecessor: Schema.NullOr(PredecessorSchema),
  attachment_count: Schema.Number.pipe(
    Schema.int(),
    Schema.between(1, S2S_EVIDENCE_ENVELOPE_MAX_ATTACHMENTS)
  ),
  attachment_total_bytes: NonNegativeSafeIntegerSchema.pipe(
    Schema.between(1, S2S_EVIDENCE_ENVELOPE_MAX_TOTAL_ATTACHMENT_BYTES)
  ),
  attachments: Schema.Array(AttachmentDescriptorSchema).pipe(
    Schema.minItems(1),
    Schema.maxItems(S2S_EVIDENCE_ENVELOPE_MAX_ATTACHMENTS)
  ),
  manifest_receipt_sha256: S2SSha256Schema
})

const ClaimDocumentSchema = Schema.Struct({
  schema_version: Schema.Literal(S2S_EVIDENCE_CLAIM_SCHEMA_VERSION),
  experiment_id: Schema.Literal(S2S_CONFIRMATORY_EXPERIMENT_ID),
  claim_scope: Schema.Literal("ONE_REGISTRATION_COMMIT_PER_STAGE"),
  source_commit_a: S2SGitCommitShaSchema,
  registration_commit_b: S2SGitCommitShaSchema,
  workflow_run_id: PositiveSafeIntegerSchema,
  workflow_run_attempt: Schema.Literal(1),
  stage: StageSchema,
  manifest_raw_sha256: S2SSha256Schema,
  predecessor_claim_raw_sha256: Schema.NullOr(S2SSha256Schema),
  claim_receipt_sha256: S2SSha256Schema
})

export type S2SEvidenceStage = Schema.Schema.Type<typeof StageSchema>
export type S2SEvidenceAttachmentDescriptor = Schema.Schema.Type<
  typeof AttachmentDescriptorSchema
>
export type S2SEvidenceEnvelopeDocument = Schema.Schema.Type<
  typeof EnvelopeDocumentSchema
>
export type S2SEvidenceClaimDocument = Schema.Schema.Type<
  typeof ClaimDocumentSchema
>

export interface S2SEvidenceAttachmentInput {
  readonly logicalName: string
  readonly role: string
  readonly schemaVersion: string | null
  readonly mediaType:
    | "application/json"
    | "application/octet-stream"
    | "application/zip"
  readonly bytes: Uint8Array
}

export interface S2SEvidenceEnvelopeInput {
  readonly sourceCommitA: string
  readonly registrationCommitB: string
  readonly workflowRunId: number
  readonly workflowRunCreatedAtUnixSeconds: number
  readonly workflowApiPath: string
  readonly workflowFileSha256: string
  readonly workflowContractSha256: string
  readonly stage: S2SEvidenceStage
  readonly currentJobDatabaseId: number
  readonly predecessor: {
    readonly stage: "REGISTER" | "CONFIRM"
    readonly manifestRawSha256: string
    readonly claimRawSha256: string
  } | null
  readonly attachments: ReadonlyArray<S2SEvidenceAttachmentInput>
}

export interface S2SEvidenceAttachmentSnapshot {
  readonly descriptor: S2SEvidenceAttachmentDescriptor
  readonly readBytes: () => Uint8Array
}

export interface S2SEvidenceEnvelopeSnapshot {
  readonly document: S2SEvidenceEnvelopeDocument
  readonly canonicalBytes: Uint8Array
  readonly manifestRawSha256: S2SSha256
  readonly attachments: ReadonlyArray<S2SEvidenceAttachmentSnapshot>
}

export interface S2SEvidenceClaimSnapshot {
  readonly document: S2SEvidenceClaimDocument
  readonly canonicalBytes: Uint8Array
  readonly claimRawSha256: S2SSha256
}

export class S2SEvidenceEnvelopeError extends Data.TaggedError(
  "S2SEvidenceEnvelopeError"
)<{
  readonly reason:
    | "ATTACHMENT_BYTES_INVALID"
    | "ATTACHMENT_DESCRIPTOR_INVALID"
    | "ATTACHMENT_HASH_MISMATCH"
    | "ATTACHMENT_ORDER_INVALID"
    | "ATTACHMENT_SET_INVALID"
    | "ATTACHMENT_SIZE_INVALID"
    | "CANONICAL_BYTES_DRIFT"
    | "CLAIM_IDENTITY_MISMATCH"
    | "DOCUMENT_PARSE_FAILED"
    | "DOCUMENT_SCHEMA_REJECTED"
    | "ENVELOPE_IDENTITY_INVALID"
    | "MANIFEST_SIZE_INVALID"
    | "PREDECESSOR_INVALID"
    | "SELF_HASH_MISMATCH"
  readonly detail: string
}> {}

const envelopeError = (
  reason: S2SEvidenceEnvelopeError["reason"],
  detail: string
): S2SEvidenceEnvelopeError => new S2SEvidenceEnvelopeError({ reason, detail })

const fail = (
  reason: S2SEvidenceEnvelopeError["reason"],
  detail: string
): Either.Either<never, S2SEvidenceEnvelopeError> =>
  Either.left(envelopeError(reason, detail))

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((byte, index) => byte === right[index])

const compareAscii = (left: string, right: string): number =>
  left < right ? -1 : left > right ? 1 : 0

const exactDataRecord = (
  input: unknown,
  keys: ReadonlyArray<string>
): Readonly<Record<string, unknown>> | null => {
  try {
    if (input === null || typeof input !== "object") return null
    const prototype = Object.getPrototypeOf(input)
    if (prototype !== Object.prototype && prototype !== null) return null
    const ownKeys = Reflect.ownKeys(input)
    if (
      ownKeys.length !== keys.length ||
      ownKeys.some((key) => typeof key !== "string")
    ) {
      return null
    }
    const sorted = ownKeys
      .filter((key): key is string => typeof key === "string")
      .sort()
    const expected = [...keys].sort()
    if (!sorted.every((key, index) => key === expected[index])) return null
    const output: Record<string, unknown> = Object.create(null)
    for (const key of sorted) {
      const descriptor = Object.getOwnPropertyDescriptor(input, key)
      if (
        descriptor === undefined ||
        descriptor.enumerable !== true ||
        !("value" in descriptor)
      ) {
        return null
      }
      output[key] = descriptor.value
    }
    return Object.freeze(output)
  } catch {
    return null
  }
}

const snapshotBoundedArray = (
  input: unknown,
  maximumLength: number,
  allowEmpty: boolean
): ReadonlyArray<unknown> | null => {
  try {
    if (!Array.isArray(input) || Object.getPrototypeOf(input) !== Array.prototype) {
      return null
    }
    const length = input.length
    if (
      !Number.isSafeInteger(length) ||
      length > maximumLength ||
      (!allowEmpty && length < 1)
    ) {
      return null
    }
    const ownKeys = Reflect.ownKeys(input)
    if (ownKeys.length !== length + 1) return null
    const output: Array<unknown> = []
    for (let index = 0; index < length; index += 1) {
      const descriptor = Object.getOwnPropertyDescriptor(input, String(index))
      if (
        descriptor === undefined ||
        descriptor.enumerable !== true ||
        !("value" in descriptor)
      ) {
        return null
      }
      output.push(descriptor.value)
    }
    const lengthDescriptor = Object.getOwnPropertyDescriptor(input, "length")
    if (
      lengthDescriptor === undefined ||
      !("value" in lengthDescriptor) ||
      lengthDescriptor.value !== length
    ) {
      return null
    }
    return Object.freeze(output)
  } catch {
    return null
  }
}

const snapshotPlainBytes = (
  input: unknown,
  maximumBytes: number,
  minimumBytes = 1
): Uint8Array | null => {
  try {
    if (
      Object.getPrototypeOf(input) !== Uint8Array.prototype ||
      !(input instanceof Uint8Array) ||
      Object.getOwnPropertySymbols(input).length !== 0 ||
      Object.getOwnPropertyDescriptor(input, "byteLength") !== undefined ||
      Object.getOwnPropertyDescriptor(input, "buffer") !== undefined ||
      input.byteLength < minimumBytes ||
      input.byteLength > maximumBytes ||
      (typeof SharedArrayBuffer !== "undefined" &&
        input.buffer instanceof SharedArrayBuffer)
    ) {
      return null
    }
    return Uint8Array.from(input)
  } catch {
    return null
  }
}

const hasSafeLogicalName = (name: string): boolean =>
  !name.startsWith("/") &&
  !name.endsWith("/") &&
  !name.includes("//") &&
  name.split("/").every((segment) => segment !== "." && segment !== "..")

const expectedPredecessorStage = (
  stage: S2SEvidenceStage
): "REGISTER" | "CONFIRM" | null => {
  switch (stage) {
    case "REGISTER":
      return null
    case "CONFIRM":
      return "REGISTER"
    case "ADJUDICATE":
      return "CONFIRM"
  }
}

const validatePredecessor = (
  stage: S2SEvidenceStage,
  predecessor: S2SEvidenceEnvelopeDocument["predecessor"]
): Either.Either<void, S2SEvidenceEnvelopeError> => {
  const expected = expectedPredecessorStage(stage)
  if (
    (expected === null && predecessor !== null) ||
    (expected !== null &&
      (predecessor === null || predecessor.stage !== expected))
  ) {
    return fail(
      "PREDECESSOR_INVALID",
      `stage ${stage} requires predecessor ${expected ?? "null"}`
    )
  }
  return Either.right(undefined)
}

const validateAttachmentDescriptors = (
  descriptors: ReadonlyArray<S2SEvidenceAttachmentDescriptor>,
  declaredCount: number,
  declaredTotal: number
): Either.Either<void, S2SEvidenceEnvelopeError> => {
  if (descriptors.length !== declaredCount || descriptors.length === 0) {
    return fail(
      "ATTACHMENT_SET_INVALID",
      "attachment count does not equal the nonempty descriptor roster"
    )
  }
  const names = new Set<string>()
  const roles = new Set<string>()
  let total = 0
  let previousName: string | null = null
  for (const descriptor of descriptors) {
    if (!hasSafeLogicalName(descriptor.logical_name)) {
      return fail(
        "ATTACHMENT_DESCRIPTOR_INVALID",
        `unsafe logical name: ${descriptor.logical_name}`
      )
    }
    if (
      names.has(descriptor.logical_name) ||
      roles.has(descriptor.role)
    ) {
      return fail(
        "ATTACHMENT_SET_INVALID",
        "attachment logical names and roles must both be unique"
      )
    }
    if (
      previousName !== null &&
      compareAscii(previousName, descriptor.logical_name) >= 0
    ) {
      return fail(
        "ATTACHMENT_ORDER_INVALID",
        "attachment descriptors must be strictly ordered by logical name"
      )
    }
    names.add(descriptor.logical_name)
    roles.add(descriptor.role)
    previousName = descriptor.logical_name
    total += descriptor.byte_length
    if (!Number.isSafeInteger(total)) {
      return fail(
        "ATTACHMENT_SIZE_INVALID",
        "attachment total exceeds the safe-integer range"
      )
    }
  }
  if (
    total !== declaredTotal ||
    total > S2S_EVIDENCE_ENVELOPE_MAX_TOTAL_ATTACHMENT_BYTES
  ) {
    return fail(
      "ATTACHMENT_SIZE_INVALID",
      "attachment byte total does not match the bounded declaration"
    )
  }
  return Either.right(undefined)
}

const canonicalDocumentBytes = (
  value: unknown,
  maximumBytes: number
): Either.Either<Uint8Array, S2SEvidenceEnvelopeError> => {
  const encoded = canonicalS2SControlJsonBytes(value)
  if (Either.isLeft(encoded)) {
    return fail(
      "CANONICAL_BYTES_DRIFT",
      "document cannot be encoded as strict canonical control JSON"
    )
  }
  if (encoded.right.byteLength < 1 || encoded.right.byteLength > maximumBytes) {
    return fail("MANIFEST_SIZE_INVALID", "canonical document exceeds its byte bound")
  }
  return Either.right(encoded.right)
}

const decodeCanonicalDocument = <A, I>(
  input: unknown,
  schema: Schema.Schema<A, I, never>,
  maximumBytes: number
): Either.Either<A, S2SEvidenceEnvelopeError> => {
  const bytes = snapshotPlainBytes(input, maximumBytes)
  if (bytes === null) {
    return fail("MANIFEST_SIZE_INVALID", "document bytes violate the fixed bound")
  }
  if (
    bytes[bytes.byteLength - 1] !== 0x0a ||
    bytes.some((byte) => byte > 0x7f) ||
    bytes
      .subarray(0, bytes.byteLength - 1)
      .some((byte) => byte === 0x0a || byte === 0x0d)
  ) {
    return fail("CANONICAL_BYTES_DRIFT", "document is not one canonical ASCII line")
  }
  let parsed: unknown
  try {
    const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes)
    parsed = JSON.parse(text.slice(0, -1))
  } catch {
    return fail("DOCUMENT_PARSE_FAILED", "document JSON parsing failed")
  }
  const decoded = Schema.decodeUnknownEither(schema, {
    onExcessProperty: "error"
  })(parsed)
  if (Either.isLeft(decoded)) {
    return fail("DOCUMENT_SCHEMA_REJECTED", "document schema rejected the input")
  }
  const canonical = canonicalDocumentBytes(decoded.right, maximumBytes)
  if (Either.isLeft(canonical) || !sameBytes(canonical.right, bytes)) {
    return fail("CANONICAL_BYTES_DRIFT", "document bytes are not canonical")
  }
  return Either.right(decoded.right)
}

const makeAttachmentSnapshot = (
  descriptor: S2SEvidenceAttachmentDescriptor,
  bytes: Uint8Array
): S2SEvidenceAttachmentSnapshot => {
  const descriptorSnapshot = structuredClone(descriptor)
  const bytesSnapshot = Uint8Array.from(bytes)
  return Object.freeze({
    get descriptor(): S2SEvidenceAttachmentDescriptor {
      return structuredClone(descriptorSnapshot)
    },
    readBytes: () => Uint8Array.from(bytesSnapshot)
  })
}

const AUTHENTIC_ENVELOPE_SNAPSHOTS = new WeakSet<object>()

const makeEnvelopeSnapshot = (
  document: S2SEvidenceEnvelopeDocument,
  canonicalBytes: Uint8Array,
  attachments: ReadonlyArray<S2SEvidenceAttachmentSnapshot>
): S2SEvidenceEnvelopeSnapshot => {
  const documentSnapshot = structuredClone(document)
  const manifestSnapshot = Uint8Array.from(canonicalBytes)
  const attachmentSnapshots = Object.freeze([...attachments])
  const snapshot = Object.freeze({
    get document(): S2SEvidenceEnvelopeDocument {
      return structuredClone(documentSnapshot)
    },
    get canonicalBytes(): Uint8Array {
      return Uint8Array.from(manifestSnapshot)
    },
    manifestRawSha256: S2SSha256Schema.make(
      rawS2SFileSha256(manifestSnapshot)
    ),
    get attachments(): ReadonlyArray<S2SEvidenceAttachmentSnapshot> {
      return attachmentSnapshots
    }
  })
  AUTHENTIC_ENVELOPE_SNAPSHOTS.add(snapshot)
  return snapshot
}

export const buildS2SEvidenceEnvelope = (
  input: S2SEvidenceEnvelopeInput
): Either.Either<S2SEvidenceEnvelopeSnapshot, S2SEvidenceEnvelopeError> => {
  try {
    const root = exactDataRecord(input, [
      "sourceCommitA",
      "registrationCommitB",
      "workflowRunId",
      "workflowRunCreatedAtUnixSeconds",
      "workflowApiPath",
      "workflowFileSha256",
      "workflowContractSha256",
      "stage",
      "currentJobDatabaseId",
      "predecessor",
      "attachments"
    ])
    const rawAttachments =
      root === null
        ? null
        : snapshotBoundedArray(
            root["attachments"],
            S2S_EVIDENCE_ENVELOPE_MAX_ATTACHMENTS,
            false
          )
    if (root === null || rawAttachments === null) {
      return fail("ENVELOPE_IDENTITY_INVALID", "envelope input shape is not exact")
    }
    const workflowContract = s2sConfirmatoryWorkflowContractSha256()
    if (
      Either.isLeft(workflowContract) ||
      root["workflowContractSha256"] !== workflowContract.right ||
      root["sourceCommitA"] === root["registrationCommitB"]
    ) {
      return fail(
        "ENVELOPE_IDENTITY_INVALID",
        "envelope lifecycle or workflow-contract identity is invalid"
      )
    }
    const attachments: Array<S2SEvidenceAttachmentSnapshot> = []
    let acceptedTotalBytes = 0
    for (const rawAttachment of rawAttachments) {
      const attachment = exactDataRecord(rawAttachment, [
        "logicalName",
        "role",
        "schemaVersion",
        "mediaType",
        "bytes"
      ])
      if (attachment === null) {
        return fail(
          "ATTACHMENT_DESCRIPTOR_INVALID",
          "attachment input shape is not exact"
        )
      }
      const bytes = snapshotPlainBytes(
        attachment["bytes"],
        S2S_EVIDENCE_ENVELOPE_MAX_ATTACHMENT_BYTES
      )
      if (bytes === null) {
        return fail(
          "ATTACHMENT_BYTES_INVALID",
          "attachment must contain one unshared plain Uint8Array"
        )
      }
      acceptedTotalBytes += bytes.byteLength
      if (
        !Number.isSafeInteger(acceptedTotalBytes) ||
        acceptedTotalBytes >
          S2S_EVIDENCE_ENVELOPE_MAX_TOTAL_ATTACHMENT_BYTES
      ) {
        return fail(
          "ATTACHMENT_SIZE_INVALID",
          "attachment roster exceeds the fixed total-byte bound"
        )
      }
      const descriptorCandidate = {
        logical_name: attachment["logicalName"],
        role: attachment["role"],
        schema_version: attachment["schemaVersion"],
        media_type: attachment["mediaType"],
        byte_length: bytes.byteLength,
        raw_sha256: rawS2SFileSha256(bytes)
      }
      const descriptor = Schema.decodeUnknownEither(AttachmentDescriptorSchema, {
        onExcessProperty: "error"
      })(descriptorCandidate)
      if (Either.isLeft(descriptor)) {
        return fail(
          "ATTACHMENT_DESCRIPTOR_INVALID",
          "attachment descriptor violates the fixed schema"
        )
      }
      attachments.push(makeAttachmentSnapshot(descriptor.right, bytes))
    }
    attachments.sort((left, right) =>
      compareAscii(left.descriptor.logical_name, right.descriptor.logical_name)
    )
    const descriptors = attachments.map((attachment) => attachment.descriptor)
    const totalBytes = descriptors.reduce(
      (total, descriptor) => total + descriptor.byte_length,
      0
    )
    const descriptorValidation = validateAttachmentDescriptors(
      descriptors,
      descriptors.length,
      totalBytes
    )
    if (Either.isLeft(descriptorValidation)) {
      return Either.left(descriptorValidation.left)
    }

    const predecessorInput = root["predecessor"]
    const predecessor =
      predecessorInput === null
        ? null
        : (() => {
            const value = exactDataRecord(predecessorInput, [
              "stage",
              "manifestRawSha256",
              "claimRawSha256"
            ])
            return value === null
              ? predecessorInput
              : {
                  stage: value["stage"],
                  manifest_raw_sha256: value["manifestRawSha256"],
                  claim_raw_sha256: value["claimRawSha256"]
                }
          })()
    const unsignedCandidate = {
      schema_version: S2S_EVIDENCE_ENVELOPE_SCHEMA_VERSION,
      experiment_id: S2S_CONFIRMATORY_EXPERIMENT_ID,
      claim_scope: "ONE_REGISTRATION_COMMIT_PER_STAGE" as const,
      source_commit_a: root["sourceCommitA"],
      registration_commit_b: root["registrationCommitB"],
      workflow_run_id: root["workflowRunId"],
      workflow_run_attempt: 1 as const,
      workflow_head_sha: root["registrationCommitB"],
      workflow_run_created_at_unix_seconds:
        root["workflowRunCreatedAtUnixSeconds"],
      workflow_api_path: root["workflowApiPath"],
      workflow_file_sha256: root["workflowFileSha256"],
      workflow_contract_sha256: root["workflowContractSha256"],
      stage: root["stage"],
      current_job_database_id: root["currentJobDatabaseId"],
      predecessor,
      attachment_count: descriptors.length,
      attachment_total_bytes: totalBytes,
      attachments: descriptors
    }
    const stage = unsignedCandidate.stage
    if (stage !== "REGISTER" && stage !== "CONFIRM" && stage !== "ADJUDICATE") {
      return fail("ENVELOPE_IDENTITY_INVALID", "stage is invalid")
    }
    const predecessorValidation = validatePredecessor(
      stage,
      predecessor as S2SEvidenceEnvelopeDocument["predecessor"]
    )
    if (Either.isLeft(predecessorValidation)) {
      return Either.left(predecessorValidation.left)
    }
    const receipt = canonicalS2SControlSha256(unsignedCandidate)
    if (Either.isLeft(receipt)) {
      return fail("CANONICAL_BYTES_DRIFT", "manifest core cannot be hashed")
    }
    const documentCandidate = {
      ...unsignedCandidate,
      manifest_receipt_sha256: receipt.right
    }
    const decoded = Schema.decodeUnknownEither(EnvelopeDocumentSchema, {
      onExcessProperty: "error"
    })(documentCandidate)
    if (Either.isLeft(decoded)) {
      return fail("DOCUMENT_SCHEMA_REJECTED", "built manifest failed its schema")
    }
    const canonical = canonicalDocumentBytes(
      decoded.right,
      S2S_EVIDENCE_ENVELOPE_MAX_MANIFEST_BYTES
    )
    if (Either.isLeft(canonical)) return Either.left(canonical.left)
    return Either.right(makeEnvelopeSnapshot(decoded.right, canonical.right, attachments))
  } catch {
    return fail("ENVELOPE_IDENTITY_INVALID", "envelope construction failed closed")
  }
}

export const validateS2SEvidenceEnvelope = (input: {
  readonly manifestBytes: Uint8Array
  readonly attachments: ReadonlyArray<{
    readonly rawSha256: string
    readonly bytes: Uint8Array
  }>
}): Either.Either<S2SEvidenceEnvelopeSnapshot, S2SEvidenceEnvelopeError> => {
  try {
    const root = exactDataRecord(input, ["manifestBytes", "attachments"])
    const rawAttachments =
      root === null
        ? null
        : snapshotBoundedArray(
            root["attachments"],
            S2S_EVIDENCE_ENVELOPE_MAX_ATTACHMENTS,
            false
          )
    if (root === null || rawAttachments === null) {
      return fail("ATTACHMENT_SET_INVALID", "validation input shape is not exact")
    }
    const manifestBytes = snapshotPlainBytes(
      root["manifestBytes"],
      S2S_EVIDENCE_ENVELOPE_MAX_MANIFEST_BYTES
    )
    if (manifestBytes === null) {
      return fail("MANIFEST_SIZE_INVALID", "manifest bytes are invalid")
    }
    const decoded = decodeCanonicalDocument(
      manifestBytes,
      EnvelopeDocumentSchema,
      S2S_EVIDENCE_ENVELOPE_MAX_MANIFEST_BYTES
    )
    if (Either.isLeft(decoded)) return Either.left(decoded.left)
    const document = decoded.right
    const { manifest_receipt_sha256: declaredReceipt, ...unsigned } = document
    const receipt = canonicalS2SControlSha256(unsigned)
    if (Either.isLeft(receipt) || receipt.right !== declaredReceipt) {
      return fail("SELF_HASH_MISMATCH", "manifest receipt hash does not match its core")
    }
    if (document.workflow_head_sha !== document.registration_commit_b) {
      return fail("ENVELOPE_IDENTITY_INVALID", "workflow head must equal registration B")
    }
    const workflowContract = s2sConfirmatoryWorkflowContractSha256()
    if (
      document.source_commit_a === document.registration_commit_b ||
      Either.isLeft(workflowContract) ||
      document.workflow_contract_sha256 !== workflowContract.right
    ) {
      return fail(
        "ENVELOPE_IDENTITY_INVALID",
        "manifest lifecycle or workflow-contract identity is invalid"
      )
    }
    const predecessor = validatePredecessor(document.stage, document.predecessor)
    if (Either.isLeft(predecessor)) return Either.left(predecessor.left)
    const descriptors = validateAttachmentDescriptors(
      document.attachments,
      document.attachment_count,
      document.attachment_total_bytes
    )
    if (Either.isLeft(descriptors)) return Either.left(descriptors.left)

    const supplied = new Map<string, Uint8Array>()
    let suppliedTotalBytes = 0
    for (const rawAttachment of rawAttachments) {
      const attachment = exactDataRecord(rawAttachment, ["rawSha256", "bytes"])
      if (attachment === null || typeof attachment["rawSha256"] !== "string") {
        return fail("ATTACHMENT_SET_INVALID", "attachment validation entry is invalid")
      }
      const bytes = snapshotPlainBytes(
        attachment["bytes"],
        S2S_EVIDENCE_ENVELOPE_MAX_ATTACHMENT_BYTES
      )
      if (bytes === null) {
        return fail("ATTACHMENT_BYTES_INVALID", "attachment bytes are invalid")
      }
      if (supplied.has(attachment["rawSha256"])) {
        return fail("ATTACHMENT_SET_INVALID", "attachment hash appears more than once")
      }
      suppliedTotalBytes += bytes.byteLength
      if (
        !Number.isSafeInteger(suppliedTotalBytes) ||
        suppliedTotalBytes >
          S2S_EVIDENCE_ENVELOPE_MAX_TOTAL_ATTACHMENT_BYTES
      ) {
        return fail(
          "ATTACHMENT_SIZE_INVALID",
          "supplied attachment bytes exceed the fixed total bound"
        )
      }
      supplied.set(attachment["rawSha256"], bytes)
    }
    const snapshots: Array<S2SEvidenceAttachmentSnapshot> = []
    for (const descriptor of document.attachments) {
      const bytes = supplied.get(descriptor.raw_sha256)
      if (bytes === undefined) {
        return fail("ATTACHMENT_SET_INVALID", "manifest attachment bytes are missing")
      }
      if (
        bytes.byteLength !== descriptor.byte_length ||
        rawS2SFileSha256(bytes) !== descriptor.raw_sha256
      ) {
        return fail(
          "ATTACHMENT_HASH_MISMATCH",
          `attachment ${descriptor.logical_name} does not match its descriptor`
        )
      }
      snapshots.push(makeAttachmentSnapshot(descriptor, bytes))
    }
    if (supplied.size !== new Set(document.attachments.map((value) => value.raw_sha256)).size) {
      return fail("ATTACHMENT_SET_INVALID", "unreferenced attachment bytes were supplied")
    }
    return Either.right(makeEnvelopeSnapshot(document, manifestBytes, snapshots))
  } catch {
    return fail("ATTACHMENT_SET_INVALID", "envelope validation failed closed")
  }
}

const makeClaimSnapshot = (
  document: S2SEvidenceClaimDocument,
  canonicalBytes: Uint8Array
): S2SEvidenceClaimSnapshot => {
  const documentSnapshot = structuredClone(document)
  const bytesSnapshot = Uint8Array.from(canonicalBytes)
  return Object.freeze({
    get document(): S2SEvidenceClaimDocument {
      return structuredClone(documentSnapshot)
    },
    get canonicalBytes(): Uint8Array {
      return Uint8Array.from(bytesSnapshot)
    },
    claimRawSha256: S2SSha256Schema.make(rawS2SFileSha256(bytesSnapshot))
  })
}

export const validateS2SEvidenceEnvelopeSnapshot = (
  input: unknown
): Either.Either<S2SEvidenceEnvelopeSnapshot, S2SEvidenceEnvelopeError> => {
  try {
    if (input === null || typeof input !== "object") {
      return fail("CLAIM_IDENTITY_MISMATCH", "claim input is not an envelope")
    }
    if (AUTHENTIC_ENVELOPE_SNAPSHOTS.has(input)) {
      return Either.right(input as S2SEvidenceEnvelopeSnapshot)
    }
    const manifestBytes = snapshotPlainBytes(
      Reflect.get(input, "canonicalBytes"),
      S2S_EVIDENCE_ENVELOPE_MAX_MANIFEST_BYTES
    )
    const attachmentValues = snapshotBoundedArray(
      Reflect.get(input, "attachments"),
      S2S_EVIDENCE_ENVELOPE_MAX_ATTACHMENTS,
      false
    )
    const declaredManifestRawSha256 = Reflect.get(
      input,
      "manifestRawSha256"
    )
    if (
      manifestBytes === null ||
      attachmentValues === null ||
      typeof declaredManifestRawSha256 !== "string"
    ) {
      return fail(
        "CLAIM_IDENTITY_MISMATCH",
        "claim input does not expose one bounded envelope snapshot"
      )
    }
    const attachments = new Map<
      string,
      { readonly rawSha256: string; readonly bytes: Uint8Array }
    >()
    let totalBytes = 0
    for (const attachment of attachmentValues) {
      if (attachment === null || typeof attachment !== "object") {
        return fail(
          "CLAIM_IDENTITY_MISMATCH",
          "envelope attachment snapshot is invalid"
        )
      }
      const readBytes = Reflect.get(attachment, "readBytes")
      if (typeof readBytes !== "function") {
        return fail(
          "CLAIM_IDENTITY_MISMATCH",
          "envelope attachment lacks its byte reader"
        )
      }
      const bytes = snapshotPlainBytes(
        Reflect.apply(readBytes, undefined, []),
        S2S_EVIDENCE_ENVELOPE_MAX_ATTACHMENT_BYTES
      )
      if (bytes === null) {
        return fail(
          "ATTACHMENT_BYTES_INVALID",
          "envelope attachment reader returned invalid bytes"
        )
      }
      totalBytes += bytes.byteLength
      if (
        !Number.isSafeInteger(totalBytes) ||
        totalBytes > S2S_EVIDENCE_ENVELOPE_MAX_TOTAL_ATTACHMENT_BYTES
      ) {
        return fail(
          "ATTACHMENT_SIZE_INVALID",
          "envelope attachment snapshot exceeds the fixed total bound"
        )
      }
      const rawSha256 = rawS2SFileSha256(bytes)
      if (!attachments.has(rawSha256)) {
        attachments.set(rawSha256, { rawSha256, bytes })
      }
    }
    const validated = validateS2SEvidenceEnvelope({
      manifestBytes,
      attachments: [...attachments.values()]
    })
    if (Either.isLeft(validated)) return Either.left(validated.left)
    if (validated.right.manifestRawSha256 !== declaredManifestRawSha256) {
      return fail(
        "CLAIM_IDENTITY_MISMATCH",
        "envelope manifest address differs from its canonical bytes"
      )
    }
    return validated
  } catch {
    return fail(
      "CLAIM_IDENTITY_MISMATCH",
      "envelope snapshot revalidation failed closed"
    )
  }
}

export const buildS2SEvidenceClaim = (
  envelope: S2SEvidenceEnvelopeSnapshot
): Either.Either<S2SEvidenceClaimSnapshot, S2SEvidenceEnvelopeError> => {
  const validatedEnvelope = validateS2SEvidenceEnvelopeSnapshot(envelope)
  if (Either.isLeft(validatedEnvelope)) {
    return Either.left(validatedEnvelope.left)
  }
  const trustedEnvelope = validatedEnvelope.right
  const document = trustedEnvelope.document
  const unsigned = {
    schema_version: S2S_EVIDENCE_CLAIM_SCHEMA_VERSION,
    experiment_id: S2S_CONFIRMATORY_EXPERIMENT_ID,
    claim_scope: "ONE_REGISTRATION_COMMIT_PER_STAGE" as const,
    source_commit_a: document.source_commit_a,
    registration_commit_b: document.registration_commit_b,
    workflow_run_id: document.workflow_run_id,
    workflow_run_attempt: 1 as const,
    stage: document.stage,
    manifest_raw_sha256: trustedEnvelope.manifestRawSha256,
    predecessor_claim_raw_sha256:
      document.predecessor?.claim_raw_sha256 ?? null
  }
  const receipt = canonicalS2SControlSha256(unsigned)
  if (Either.isLeft(receipt)) {
    return fail("CANONICAL_BYTES_DRIFT", "claim core cannot be hashed")
  }
  const decoded = Schema.decodeUnknownEither(ClaimDocumentSchema, {
    onExcessProperty: "error"
  })({ ...unsigned, claim_receipt_sha256: receipt.right })
  if (Either.isLeft(decoded)) {
    return fail("DOCUMENT_SCHEMA_REJECTED", "built claim failed its schema")
  }
  const canonical = canonicalDocumentBytes(
    decoded.right,
    S2S_EVIDENCE_CLAIM_MAX_BYTES
  )
  if (Either.isLeft(canonical)) return Either.left(canonical.left)
  return Either.right(makeClaimSnapshot(decoded.right, canonical.right))
}

export const validateS2SEvidenceClaim = (
  input: Uint8Array
): Either.Either<S2SEvidenceClaimSnapshot, S2SEvidenceEnvelopeError> => {
  const bytes = snapshotPlainBytes(input, S2S_EVIDENCE_CLAIM_MAX_BYTES)
  if (bytes === null) {
    return fail("MANIFEST_SIZE_INVALID", "claim bytes are invalid")
  }
  const decoded = decodeCanonicalDocument(
    bytes,
    ClaimDocumentSchema,
    S2S_EVIDENCE_CLAIM_MAX_BYTES
  )
  if (Either.isLeft(decoded)) return Either.left(decoded.left)
  const { claim_receipt_sha256: declaredReceipt, ...unsigned } = decoded.right
  const receipt = canonicalS2SControlSha256(unsigned)
  if (Either.isLeft(receipt) || receipt.right !== declaredReceipt) {
    return fail("SELF_HASH_MISMATCH", "claim receipt hash does not match its core")
  }
  if (decoded.right.source_commit_a === decoded.right.registration_commit_b) {
    return fail(
      "CLAIM_IDENTITY_MISMATCH",
      "claim source A must differ from registration B"
    )
  }
  if (
    (decoded.right.stage === "REGISTER" &&
      decoded.right.predecessor_claim_raw_sha256 !== null) ||
    (decoded.right.stage !== "REGISTER" &&
      decoded.right.predecessor_claim_raw_sha256 === null)
  ) {
    return fail(
      "PREDECESSOR_INVALID",
      "claim predecessor presence does not match its stage"
    )
  }
  return Either.right(makeClaimSnapshot(decoded.right, bytes))
}

export const validateS2SEvidenceClaimForEnvelope = (
  claimBytes: Uint8Array,
  envelope: S2SEvidenceEnvelopeSnapshot
): Either.Either<S2SEvidenceClaimSnapshot, S2SEvidenceEnvelopeError> => {
  const claim = validateS2SEvidenceClaim(claimBytes)
  if (Either.isLeft(claim)) return Either.left(claim.left)
  const validatedEnvelope = validateS2SEvidenceEnvelopeSnapshot(envelope)
  if (Either.isLeft(validatedEnvelope)) {
    return Either.left(validatedEnvelope.left)
  }
  const claimDocument = claim.right.document
  const envelopeSnapshot = validatedEnvelope.right
  const envelopeDocument = envelopeSnapshot.document
  if (
    claimDocument.source_commit_a !== envelopeDocument.source_commit_a ||
    claimDocument.registration_commit_b !==
      envelopeDocument.registration_commit_b ||
    claimDocument.workflow_run_id !== envelopeDocument.workflow_run_id ||
    claimDocument.stage !== envelopeDocument.stage ||
    claimDocument.manifest_raw_sha256 !==
      envelopeSnapshot.manifestRawSha256 ||
    claimDocument.predecessor_claim_raw_sha256 !==
      (envelopeDocument.predecessor?.claim_raw_sha256 ?? null)
  ) {
    return fail(
      "CLAIM_IDENTITY_MISMATCH",
      "claim identity does not exactly bind the validated envelope"
    )
  }
  return claim
}

export const s2sEvidenceClaimFileName = (
  registrationCommitB: S2SGitCommitSha,
  stage: S2SEvidenceStage
): string => `${registrationCommitB}.${stage.toLowerCase()}.json`
