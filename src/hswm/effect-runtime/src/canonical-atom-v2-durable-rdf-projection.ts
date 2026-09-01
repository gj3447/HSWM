import { createHash } from "node:crypto"

import { Data, Effect, Either } from "effect"

import {
  HSWM_CANONICAL_SCHEMA_CONTENT_V2_MEDIA_TYPE,
  sameCanonicalAtomV2SchemaBinding,
  snapshotCanonicalAtomV2SchemaContentBinding
} from "./canonical-atom-v2-content-bound.js"
import {
  CANONICAL_ATOM_V2_CONTENT_MAX_BYTES,
  makeCanonicalAtomV2ContentDescriptor,
  sameCanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2SchemaContentBinding
} from "./canonical-atom-v2-content.js"
import {
  HSWM_CANONICAL_ATOM_V2_LOCAL_DURABLE_STATE,
  recoverCanonicalAtomV2DurableForReadOnlyProjectionInternal,
  type CanonicalAtomV2DurableRecoveryWitness,
  type CanonicalAtomV2DurableRuntime
} from "./canonical-atom-v2-durable-runtime.js"
import {
  HSWM_CANONICAL_ATOM_V2_RDF_PROJECTION_V1_MEDIA_TYPE,
  canonicalAtomV2RdfProjectionBytes,
  compileCanonicalAtomV2RdfProjection,
  type CanonicalAtomV2RdfProjection
} from "./canonical-atom-v2-rdf-projection.js"
import {
  HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_V1_MEDIA_TYPE,
  canonicalAtomV2StateSha256,
  decodeCanonicalAtomV2StateJournalRecordBytes,
  describeCanonicalAtomV2StateJournalRecord,
  type CanonicalAtomV2StateJournalRecordDescriptor
} from "./canonical-atom-v2-state-journal.js"
import {
  CANONICAL_ATOM_V2_STATE_JOURNAL_MAX_BYTES,
  CanonicalAtomV2StateJournalStoreError
} from "./canonical-atom-v2-state-journal-store.js"
import {
  canonicalJsonBytes,
  decodeCanonicalJsonBytes,
  HSWM_CANONICAL_JSON_VERSION
} from "./canonical-atom-v2-json.js"

export const HSWM_CANONICAL_ATOM_V2_DURABLE_RDF_PROJECTION_V1_CONTRACT_VERSION =
  "hswm-canonical-atom-v2-durable-rdf-projection/v1" as const
export const HSWM_CANONICAL_ATOM_V2_DURABLE_RDF_PROJECTION_V1_MEDIA_TYPE =
  "application/vnd.hswm.canonical-atom-v2-durable-rdf-projection+json" as const
export const HSWM_CANONICAL_ATOM_V2_DURABLE_RDF_PREFIX_COMMITMENT_V1 =
  "HSWM_CANONICAL_JSON_SHA256_PREDECESSOR_CHAIN_OVER_ORDERED_RECORD_DESCRIPTORS_V1" as const
export const HSWM_CANONICAL_ATOM_V2_DURABLE_RDF_MAX_RECORDS = 4_096 as const
export const HSWM_CANONICAL_ATOM_V2_DURABLE_RDF_MAX_JOURNAL_BYTES =
  67_108_864 as const

const DURABLE_RDF_INVALIDATED_BY = Object.freeze([
  "VISIBLE_JOURNAL_PREFIX_CHANGED",
  "SCHEMA_CONTENT_BINDING_CHANGED",
  "RECOVERED_STATE_CHANGED",
  "INNER_RDF_COMPILER_PROFILE_CHANGED"
] as const)

const DURABLE_RDF_NONCLAIMS = Object.freeze([
  "NOT_GLOBAL_COMPLETE_TAIL_OR_ANTI_ROLLBACK",
  "NOT_DISTRIBUTED_STORAGE_OR_EXTERNAL_NOTARY",
  "NOT_EXECUTABLE_COMPILER_ARTIFACT_BOUND",
  "NOT_TOTAL_CONTENT_REPLAY_IO_OR_CPU_BUDGET",
  "NOT_RDFC_SHACL_PROV_CAUSAL_CREDIT_OR_LLM_EFFICACY",
  "NOT_CANONICAL_HSWM_STATE_COGNITION_LEARNING_OR_PERMISSION"
] as const)

export interface CanonicalAtomV2DurableRdfProjectionManifest {
  readonly _tag: "CanonicalAtomV2DurableRdfProjectionManifest"
  readonly contractVersion: typeof HSWM_CANONICAL_ATOM_V2_DURABLE_RDF_PROJECTION_V1_CONTRACT_VERSION
  readonly encoding: typeof HSWM_CANONICAL_JSON_VERSION
  readonly source: {
    readonly journalLineageId: string
    readonly schemaBinding: CanonicalAtomV2SchemaContentBinding
    readonly stateRevision: number
    readonly stateSha256: string
    readonly journalHead: CanonicalAtomV2StateJournalRecordDescriptor
    readonly recoveredRecordCount: number
    readonly recoveredJournalByteLength: number
    readonly journalPrefixCommitment: {
      readonly algorithm: typeof HSWM_CANONICAL_ATOM_V2_DURABLE_RDF_PREFIX_COMMITMENT_V1
      readonly sha256: string
    }
  }
  readonly innerProjection: CanonicalAtomV2ContentDescriptor
  readonly innerProjectionBinding: "EXACT_CANONICAL_BYTES_RECOMPILED_FROM_THE_SAME_RECOVERY_WITNESS"
  readonly sourceAttestation: "LOCAL_POSIX_FILE_RUNTIME_ONE_RECOVERY_OBSERVATION_PREFIX_ATTESTED_GLOBAL_TAIL_AND_ANTIROLLBACK_NOT_ATTESTED"
  readonly recoveryObservation: "ONE_JOURNAL_STORE_RECOVERY_OBSERVATION_FOR_RAW_PREFIX_AND_SEMANTIC_REPLAY"
  readonly prefixCoverage: "ALL_ORDERED_RECORDS_RETURNED_IN_THE_RECOVERY_OBSERVATION_BIND_EXACT_BYTES_BY_SHA256"
  readonly tailCompleteness: "ONE_RECOVERY_OBSERVATION_CONTIGUOUS_PREFIX_ONLY"
  readonly antiRollback: "NOT_ATTESTED"
  readonly storageScope: typeof HSWM_CANONICAL_ATOM_V2_LOCAL_DURABLE_STATE
  readonly writeBack: "FORBIDDEN"
  readonly journalPrefixRecoveryLimits: {
    readonly maximumRecords: typeof HSWM_CANONICAL_ATOM_V2_DURABLE_RDF_MAX_RECORDS
    readonly maximumRecoveredJournalBytes: typeof HSWM_CANONICAL_ATOM_V2_DURABLE_RDF_MAX_JOURNAL_BYTES
  }
  readonly invalidatedBy: ReadonlyArray<
    | "VISIBLE_JOURNAL_PREFIX_CHANGED"
    | "SCHEMA_CONTENT_BINDING_CHANGED"
    | "RECOVERED_STATE_CHANGED"
    | "INNER_RDF_COMPILER_PROFILE_CHANGED"
  >
  readonly nonclaims: ReadonlyArray<
    | "NOT_GLOBAL_COMPLETE_TAIL_OR_ANTI_ROLLBACK"
    | "NOT_DISTRIBUTED_STORAGE_OR_EXTERNAL_NOTARY"
    | "NOT_EXECUTABLE_COMPILER_ARTIFACT_BOUND"
    | "NOT_TOTAL_CONTENT_REPLAY_IO_OR_CPU_BUDGET"
    | "NOT_RDFC_SHACL_PROV_CAUSAL_CREDIT_OR_LLM_EFFICACY"
    | "NOT_CANONICAL_HSWM_STATE_COGNITION_LEARNING_OR_PERMISSION"
  >
}

export interface CanonicalAtomV2DurableRdfProjection {
  readonly manifest: CanonicalAtomV2DurableRdfProjectionManifest
  readonly projection: CanonicalAtomV2RdfProjection
}

const compiledCanonicalBytesByArtifact = new WeakMap<
  CanonicalAtomV2DurableRdfProjection,
  Uint8Array
>()

export class CanonicalAtomV2DurableRdfProjectionError extends Data.TaggedError(
  "CanonicalAtomV2DurableRdfProjectionError"
)<{
  readonly code:
    | "RECOVERY_FAILED"
    | "RECOVERY_WITNESS_INVALID"
    | "RESOURCE_LIMIT_EXCEEDED"
    | "PREFIX_COMMITMENT_FAILED"
    | "INNER_PROJECTION_FAILED"
    | "CANONICAL_ENCODING_INVALID"
    | "ARTIFACT_INVALID"
    | "ARTIFACT_TAMPERED"
  readonly detail: string
}> {}

const failure = (
  code: CanonicalAtomV2DurableRdfProjectionError["code"],
  detail: string
): CanonicalAtomV2DurableRdfProjectionError =>
  new CanonicalAtomV2DurableRdfProjectionError({ code, detail })

const fail = (
  code: CanonicalAtomV2DurableRdfProjectionError["code"],
  detail: string
): Either.Either<never, CanonicalAtomV2DurableRdfProjectionError> =>
  Either.left(failure(code, detail))

const total = <A>(
  run: () => Either.Either<A, CanonicalAtomV2DurableRdfProjectionError>
): Either.Either<A, CanonicalAtomV2DurableRdfProjectionError> => {
  try {
    return run()
  } catch {
    return fail(
      "ARTIFACT_INVALID",
      "runtime input raised while validating the fail-closed durable RDF boundary"
    )
  }
}

const sha256 = (bytes: Uint8Array): string =>
  createHash("sha256").update(bytes).digest("hex")

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((byte, index) => byte === right[index])

const sameDescriptor = (
  left: CanonicalAtomV2StateJournalRecordDescriptor,
  right: CanonicalAtomV2StateJournalRecordDescriptor
): boolean =>
  left.mediaType === right.mediaType &&
  left.byteLength === right.byteLength &&
  left.sha256 === right.sha256

const hasExactOwnKeys = (
  input: object,
  expected: ReadonlyArray<string>
): boolean => {
  const keys = Reflect.ownKeys(input)
  return keys.length === expected.length && expected.every((key) => keys.includes(key))
}

const isDescriptor = (input: unknown): input is CanonicalAtomV2ContentDescriptor =>
  typeof input === "object" &&
  input !== null &&
  hasExactOwnKeys(input, ["mediaType", "byteLength", "sha256"]) &&
  typeof (input as { readonly mediaType?: unknown }).mediaType === "string" &&
  /^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*\/[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*$/.test(
    (input as { readonly mediaType: string }).mediaType
  ) &&
  (input as { readonly mediaType: string }).mediaType.length <= 255 &&
  typeof (input as { readonly byteLength?: unknown }).byteLength === "number" &&
  Number.isSafeInteger((input as { readonly byteLength: number }).byteLength) &&
  (input as { readonly byteLength: number }).byteLength >= 0 &&
  (input as { readonly byteLength: number }).byteLength <= CANONICAL_ATOM_V2_CONTENT_MAX_BYTES &&
  typeof (input as { readonly sha256?: unknown }).sha256 === "string" &&
  /^[0-9a-f]{64}$/.test((input as { readonly sha256: string }).sha256)

const isSchemaBinding = (input: unknown): input is CanonicalAtomV2SchemaContentBinding =>
  typeof input === "object" &&
  input !== null &&
  hasExactOwnKeys(input, ["schemaVersion", "content"]) &&
  typeof (input as { readonly schemaVersion?: unknown }).schemaVersion === "string" &&
  /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/.test(
    (input as { readonly schemaVersion: string }).schemaVersion
  ) &&
  isDescriptor((input as { readonly content?: unknown }).content) &&
  (input as CanonicalAtomV2SchemaContentBinding).content.mediaType ===
    HSWM_CANONICAL_SCHEMA_CONTENT_V2_MEDIA_TYPE &&
  (input as CanonicalAtomV2SchemaContentBinding).content.byteLength >= 1

const isJournalDescriptor = (
  input: unknown
): input is CanonicalAtomV2StateJournalRecordDescriptor =>
  isDescriptor(input) &&
  input.mediaType === HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_V1_MEDIA_TYPE &&
  input.byteLength >= 1 &&
  input.byteLength <= CANONICAL_ATOM_V2_STATE_JOURNAL_MAX_BYTES

const exactStringArray = (
  input: unknown,
  expected: ReadonlyArray<string>
): boolean =>
  Array.isArray(input) &&
  input.length === expected.length &&
  input.every((value, index) => value === expected[index])

const isDurableManifest = (
  input: unknown
): input is CanonicalAtomV2DurableRdfProjectionManifest => {
  if (
    typeof input !== "object" ||
    input === null ||
    !hasExactOwnKeys(input, [
      "_tag",
      "contractVersion",
      "encoding",
      "source",
      "innerProjection",
      "innerProjectionBinding",
      "sourceAttestation",
      "recoveryObservation",
      "prefixCoverage",
      "tailCompleteness",
      "antiRollback",
      "storageScope",
      "writeBack",
      "journalPrefixRecoveryLimits",
      "invalidatedBy",
      "nonclaims"
    ])
  ) return false
  const manifest = input as CanonicalAtomV2DurableRdfProjectionManifest
  const source = manifest.source
  const commitment = source?.journalPrefixCommitment
  const limits = manifest.journalPrefixRecoveryLimits
  return manifest._tag === "CanonicalAtomV2DurableRdfProjectionManifest" &&
    manifest.contractVersion === HSWM_CANONICAL_ATOM_V2_DURABLE_RDF_PROJECTION_V1_CONTRACT_VERSION &&
    manifest.encoding === HSWM_CANONICAL_JSON_VERSION &&
    typeof source === "object" &&
    source !== null &&
    hasExactOwnKeys(source, [
      "journalLineageId",
      "schemaBinding",
      "stateRevision",
      "stateSha256",
      "journalHead",
      "recoveredRecordCount",
      "recoveredJournalByteLength",
      "journalPrefixCommitment"
    ]) &&
    /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/.test(source.journalLineageId) &&
    isSchemaBinding(source.schemaBinding) &&
    Number.isSafeInteger(source.stateRevision) &&
    source.stateRevision >= 0 &&
    /^[0-9a-f]{64}$/.test(source.stateSha256) &&
    isJournalDescriptor(source.journalHead) &&
    Number.isSafeInteger(source.recoveredRecordCount) &&
    source.recoveredRecordCount >= 1 &&
    source.recoveredRecordCount <= HSWM_CANONICAL_ATOM_V2_DURABLE_RDF_MAX_RECORDS &&
    source.stateRevision === source.recoveredRecordCount - 1 &&
    Number.isSafeInteger(source.recoveredJournalByteLength) &&
    source.recoveredJournalByteLength >= 1 &&
    source.recoveredJournalByteLength <= HSWM_CANONICAL_ATOM_V2_DURABLE_RDF_MAX_JOURNAL_BYTES &&
    source.journalHead.byteLength <= source.recoveredJournalByteLength &&
    typeof commitment === "object" &&
    commitment !== null &&
    hasExactOwnKeys(commitment, ["algorithm", "sha256"]) &&
    commitment.algorithm === HSWM_CANONICAL_ATOM_V2_DURABLE_RDF_PREFIX_COMMITMENT_V1 &&
    /^[0-9a-f]{64}$/.test(commitment.sha256) &&
    isDescriptor(manifest.innerProjection) &&
    manifest.innerProjection.mediaType === HSWM_CANONICAL_ATOM_V2_RDF_PROJECTION_V1_MEDIA_TYPE &&
    manifest.innerProjection.byteLength >= 1 &&
    manifest.innerProjectionBinding === "EXACT_CANONICAL_BYTES_RECOMPILED_FROM_THE_SAME_RECOVERY_WITNESS" &&
    manifest.sourceAttestation === "LOCAL_POSIX_FILE_RUNTIME_ONE_RECOVERY_OBSERVATION_PREFIX_ATTESTED_GLOBAL_TAIL_AND_ANTIROLLBACK_NOT_ATTESTED" &&
    manifest.recoveryObservation === "ONE_JOURNAL_STORE_RECOVERY_OBSERVATION_FOR_RAW_PREFIX_AND_SEMANTIC_REPLAY" &&
    manifest.prefixCoverage === "ALL_ORDERED_RECORDS_RETURNED_IN_THE_RECOVERY_OBSERVATION_BIND_EXACT_BYTES_BY_SHA256" &&
    manifest.tailCompleteness === "ONE_RECOVERY_OBSERVATION_CONTIGUOUS_PREFIX_ONLY" &&
    manifest.antiRollback === "NOT_ATTESTED" &&
    manifest.storageScope === HSWM_CANONICAL_ATOM_V2_LOCAL_DURABLE_STATE &&
    manifest.writeBack === "FORBIDDEN" &&
    typeof limits === "object" &&
    limits !== null &&
    hasExactOwnKeys(limits, ["maximumRecords", "maximumRecoveredJournalBytes"]) &&
    limits.maximumRecords === HSWM_CANONICAL_ATOM_V2_DURABLE_RDF_MAX_RECORDS &&
    limits.maximumRecoveredJournalBytes === HSWM_CANONICAL_ATOM_V2_DURABLE_RDF_MAX_JOURNAL_BYTES &&
    exactStringArray(manifest.invalidatedBy, DURABLE_RDF_INVALIDATED_BY) &&
    exactStringArray(manifest.nonclaims, DURABLE_RDF_NONCLAIMS)
}

const snapshotDescriptor = (
  descriptor: CanonicalAtomV2StateJournalRecordDescriptor
): CanonicalAtomV2StateJournalRecordDescriptor =>
  Object.freeze({
    mediaType: descriptor.mediaType,
    byteLength: descriptor.byteLength,
    sha256: descriptor.sha256
  })

const exactDescriptorForBytes = (
  descriptor: CanonicalAtomV2StateJournalRecordDescriptor,
  bytes: Uint8Array
): Either.Either<CanonicalAtomV2StateJournalRecordDescriptor, CanonicalAtomV2DurableRdfProjectionError> => {
  const decoded = decodeCanonicalAtomV2StateJournalRecordBytes(bytes)
  if (Either.isLeft(decoded)) {
    return fail(
      "RECOVERY_WITNESS_INVALID",
      "recovered journal contains noncanonical record bytes"
    )
  }
  const described = describeCanonicalAtomV2StateJournalRecord(decoded.right)
  if (Either.isLeft(described) || !sameDescriptor(descriptor, described.right)) {
    return fail(
      "RECOVERY_WITNESS_INVALID",
      "recovered journal descriptor does not bind its exact record bytes"
    )
  }
  return Either.right(snapshotDescriptor(described.right))
}

const prefixCommitmentSeed = (
  journalLineageId: string,
  schemaBinding: CanonicalAtomV2SchemaContentBinding
): Either.Either<string, CanonicalAtomV2DurableRdfProjectionError> => {
  const bytes = canonicalJsonBytes({
    contractVersion: HSWM_CANONICAL_ATOM_V2_DURABLE_RDF_PROJECTION_V1_CONTRACT_VERSION,
    journalLineageId,
    schemaBinding,
    step: "SEED"
  })
  return Either.isLeft(bytes)
    ? fail("PREFIX_COMMITMENT_FAILED", "journal prefix seed cannot be canonically encoded")
    : Either.right(sha256(bytes.right))
}

const extendPrefixCommitment = (
  previousCommitmentSha256: string,
  stateRevision: number,
  descriptor: CanonicalAtomV2StateJournalRecordDescriptor
): Either.Either<string, CanonicalAtomV2DurableRdfProjectionError> => {
  const bytes = canonicalJsonBytes({
    contractVersion: HSWM_CANONICAL_ATOM_V2_DURABLE_RDF_PROJECTION_V1_CONTRACT_VERSION,
    previousCommitmentSha256,
    record: {
      descriptor,
      stateRevision
    },
    step: "RECORD"
  })
  return Either.isLeft(bytes)
    ? fail("PREFIX_COMMITMENT_FAILED", "journal prefix record cannot be canonically encoded")
    : Either.right(sha256(bytes.right))
}

interface PreparedWitness {
  readonly journalLineageId: string
  readonly schemaBinding: CanonicalAtomV2SchemaContentBinding
  readonly stateRevision: number
  readonly stateSha256: string
  readonly journalHead: CanonicalAtomV2StateJournalRecordDescriptor
  readonly recoveredRecordCount: number
  readonly recoveredJournalByteLength: number
  readonly journalPrefixCommitmentSha256: string
  readonly tailRecordBytes: Uint8Array
}

const prepareWitness = (
  witness: CanonicalAtomV2DurableRecoveryWitness
): Either.Either<PreparedWitness, CanonicalAtomV2DurableRdfProjectionError> => {
  const entries = witness.journal
  if (entries.length < 1) {
    return fail("RECOVERY_WITNESS_INVALID", "durable recovery witness has no genesis record")
  }
  if (entries.length > HSWM_CANONICAL_ATOM_V2_DURABLE_RDF_MAX_RECORDS) {
    return fail("RESOURCE_LIMIT_EXCEEDED", "recovered journal exceeds the durable RDF record budget")
  }
  if (
    witness.state.journalLineageId.length === 0 ||
    witness.state.stateDurability !== HSWM_CANONICAL_ATOM_V2_LOCAL_DURABLE_STATE ||
    witness.state.canonical.revision !== entries.length - 1 ||
    witness.history.length !== entries.length - 1
  ) {
    return fail("RECOVERY_WITNESS_INVALID", "durable replay metadata does not match the recovered prefix")
  }

  const seed = prefixCommitmentSeed(
    witness.state.journalLineageId,
    witness.state.schema
  )
  if (Either.isLeft(seed)) return Either.left(seed.left)
  let prefixCommitment = seed.right
  let totalBytes = 0
  let previous: CanonicalAtomV2StateJournalRecordDescriptor | null = null

  for (let index = 0; index < entries.length; index += 1) {
    const entry = entries[index]!
    if (!(entry.bytes instanceof Uint8Array)) {
      return fail("RECOVERY_WITNESS_INVALID", "recovered journal entry bytes are invalid")
    }
    totalBytes += entry.bytes.byteLength
    if (
      !Number.isSafeInteger(totalBytes) ||
      totalBytes > HSWM_CANONICAL_ATOM_V2_DURABLE_RDF_MAX_JOURNAL_BYTES
    ) {
      return fail("RESOURCE_LIMIT_EXCEEDED", "recovered journal exceeds the durable RDF byte budget")
    }
    const exact = exactDescriptorForBytes(entry.descriptor, entry.bytes)
    if (Either.isLeft(exact)) return Either.left(exact.left)
    const decoded = decodeCanonicalAtomV2StateJournalRecordBytes(entry.bytes)
    if (Either.isLeft(decoded)) {
      return fail("RECOVERY_WITNESS_INVALID", "recovered journal record cannot be decoded")
    }
    if (
      decoded.right.stateRevision !== index ||
      decoded.right.journalLineageId !== witness.state.journalLineageId ||
      !sameCanonicalAtomV2SchemaBinding(decoded.right.schema, witness.state.schema) ||
      (index === 0
        ? decoded.right._tag !== "CanonicalAtomV2StateJournalGenesis"
        : decoded.right._tag !== "CanonicalAtomV2StateJournalCommit" ||
          previous === null ||
          !sameDescriptor(decoded.right.predecessor, previous))
    ) {
      return fail("RECOVERY_WITNESS_INVALID", "recovered journal is not one exact ordered predecessor chain")
    }
    if (index > 0 && !sameDescriptor(witness.history[index - 1]!.record, exact.right)) {
      return fail("RECOVERY_WITNESS_INVALID", "semantic replay history differs from the recovered raw prefix")
    }
    const extended = extendPrefixCommitment(prefixCommitment, index, exact.right)
    if (Either.isLeft(extended)) return Either.left(extended.left)
    prefixCommitment = extended.right
    previous = exact.right
  }

  const tail = entries.at(-1)!
  if (previous === null || !sameDescriptor(previous, witness.state.journalHead)) {
    return fail("RECOVERY_WITNESS_INVALID", "durable state head differs from the recovered prefix tail")
  }
  const stateSha = canonicalAtomV2StateSha256(witness.state.canonical)
  if (Either.isLeft(stateSha)) {
    return fail("RECOVERY_WITNESS_INVALID", "recovered state cannot produce its canonical commitment")
  }

  return Either.right(Object.freeze({
    journalLineageId: witness.state.journalLineageId,
    schemaBinding: snapshotCanonicalAtomV2SchemaContentBinding(witness.state.schema),
    stateRevision: witness.state.canonical.revision,
    stateSha256: stateSha.right,
    journalHead: snapshotDescriptor(previous),
    recoveredRecordCount: entries.length,
    recoveredJournalByteLength: totalBytes,
    journalPrefixCommitmentSha256: prefixCommitment,
    tailRecordBytes: Uint8Array.from(tail.bytes)
  }))
}

const compileFromWitness = (
  runtime: CanonicalAtomV2DurableRuntime["Type"],
  witness: CanonicalAtomV2DurableRecoveryWitness
): Either.Either<CanonicalAtomV2DurableRdfProjection, CanonicalAtomV2DurableRdfProjectionError> => {
  const prepared = prepareWitness(witness)
  if (Either.isLeft(prepared)) return Either.left(prepared.left)
  const inner = compileCanonicalAtomV2RdfProjection(runtime.schema, {
    journalLineageId: prepared.right.journalLineageId,
    schemaBinding: prepared.right.schemaBinding,
    state: witness.state.canonical,
    tailDescriptor: prepared.right.journalHead,
    tailRecordBytes: prepared.right.tailRecordBytes
  })
  if (Either.isLeft(inner)) {
    return fail("INNER_PROJECTION_FAILED", "verified durable recovery could not compile the RDF projection")
  }
  const innerBytes = canonicalAtomV2RdfProjectionBytes(inner.right)
  if (Either.isLeft(innerBytes)) {
    return fail("INNER_PROJECTION_FAILED", "inner RDF projection has no canonical artifact bytes")
  }
  const innerDescriptor = makeCanonicalAtomV2ContentDescriptor(
    HSWM_CANONICAL_ATOM_V2_RDF_PROJECTION_V1_MEDIA_TYPE,
    innerBytes.right
  )
  if (Either.isLeft(innerDescriptor)) {
    return fail("INNER_PROJECTION_FAILED", "inner RDF projection descriptor cannot be constructed")
  }

  const manifest: CanonicalAtomV2DurableRdfProjectionManifest = Object.freeze({
    _tag: "CanonicalAtomV2DurableRdfProjectionManifest",
    contractVersion: HSWM_CANONICAL_ATOM_V2_DURABLE_RDF_PROJECTION_V1_CONTRACT_VERSION,
    encoding: HSWM_CANONICAL_JSON_VERSION,
    source: Object.freeze({
      journalLineageId: prepared.right.journalLineageId,
      schemaBinding: prepared.right.schemaBinding,
      stateRevision: prepared.right.stateRevision,
      stateSha256: prepared.right.stateSha256,
      journalHead: prepared.right.journalHead,
      recoveredRecordCount: prepared.right.recoveredRecordCount,
      recoveredJournalByteLength: prepared.right.recoveredJournalByteLength,
      journalPrefixCommitment: Object.freeze({
        algorithm: HSWM_CANONICAL_ATOM_V2_DURABLE_RDF_PREFIX_COMMITMENT_V1,
        sha256: prepared.right.journalPrefixCommitmentSha256
      })
    }),
    innerProjection: Object.freeze({ ...innerDescriptor.right }),
    innerProjectionBinding: "EXACT_CANONICAL_BYTES_RECOMPILED_FROM_THE_SAME_RECOVERY_WITNESS",
    sourceAttestation: "LOCAL_POSIX_FILE_RUNTIME_ONE_RECOVERY_OBSERVATION_PREFIX_ATTESTED_GLOBAL_TAIL_AND_ANTIROLLBACK_NOT_ATTESTED",
    recoveryObservation: "ONE_JOURNAL_STORE_RECOVERY_OBSERVATION_FOR_RAW_PREFIX_AND_SEMANTIC_REPLAY",
    prefixCoverage: "ALL_ORDERED_RECORDS_RETURNED_IN_THE_RECOVERY_OBSERVATION_BIND_EXACT_BYTES_BY_SHA256",
    tailCompleteness: "ONE_RECOVERY_OBSERVATION_CONTIGUOUS_PREFIX_ONLY",
    antiRollback: "NOT_ATTESTED",
    storageScope: HSWM_CANONICAL_ATOM_V2_LOCAL_DURABLE_STATE,
    writeBack: "FORBIDDEN",
    journalPrefixRecoveryLimits: Object.freeze({
      maximumRecords: HSWM_CANONICAL_ATOM_V2_DURABLE_RDF_MAX_RECORDS,
      maximumRecoveredJournalBytes: HSWM_CANONICAL_ATOM_V2_DURABLE_RDF_MAX_JOURNAL_BYTES
    }),
    invalidatedBy: DURABLE_RDF_INVALIDATED_BY,
    nonclaims: DURABLE_RDF_NONCLAIMS
  })
  const artifact = Object.freeze({ manifest, projection: inner.right })
  const encoded = canonicalAtomV2DurableRdfProjectionBytesUnsafe(artifact)
  if (Either.isLeft(encoded)) return Either.left(encoded.left)
  compiledCanonicalBytesByArtifact.set(artifact, Uint8Array.from(encoded.right))
  return Either.right(artifact)
}

const canonicalAtomV2DurableRdfProjectionBytesUnsafe = (
  artifact: CanonicalAtomV2DurableRdfProjection
): Either.Either<Uint8Array, CanonicalAtomV2DurableRdfProjectionError> => {
  if (
    typeof artifact !== "object" ||
    artifact === null ||
    !hasExactOwnKeys(artifact, ["manifest", "projection"]) ||
    !isDurableManifest(artifact.manifest) ||
    typeof artifact.projection !== "object" ||
    artifact.projection === null
  ) {
    return fail("ARTIFACT_INVALID", "durable RDF artifact shape or contract version is invalid")
  }
  const innerBytes = canonicalAtomV2RdfProjectionBytes(artifact.projection)
  if (Either.isLeft(innerBytes)) {
    return fail("ARTIFACT_INVALID", "durable RDF artifact contains an invalid inner projection")
  }
  const innerDescriptor = makeCanonicalAtomV2ContentDescriptor(
    HSWM_CANONICAL_ATOM_V2_RDF_PROJECTION_V1_MEDIA_TYPE,
    innerBytes.right
  )
  if (
    Either.isLeft(innerDescriptor) ||
    !sameCanonicalAtomV2ContentDescriptor(innerDescriptor.right, artifact.manifest.innerProjection)
  ) {
    return fail("ARTIFACT_INVALID", "inner projection bytes differ from the durable manifest descriptor")
  }
  const bytes = canonicalJsonBytes({
    manifest: artifact.manifest,
    projectionBase64Url: Buffer.from(innerBytes.right).toString("base64url")
  })
  return Either.isLeft(bytes)
    ? fail("CANONICAL_ENCODING_INVALID", "durable RDF artifact exceeds or violates canonical JSON/v1")
    : Either.right(Uint8Array.from(bytes.right))
}

/**
 * Issues canonical bytes only for an unchanged artifact compiled by this
 * module instance. External objects and bytes must first pass `verify` or
 * `decode`, both of which recompile from a fresh durable recovery observation.
 */
export const canonicalAtomV2DurableRdfProjectionBytes = (
  artifact: CanonicalAtomV2DurableRdfProjection
): Either.Either<Uint8Array, CanonicalAtomV2DurableRdfProjectionError> =>
  total(() => {
    const compiledBytes = compiledCanonicalBytesByArtifact.get(artifact)
    if (compiledBytes === undefined) {
      return fail(
        "ARTIFACT_INVALID",
        "durable RDF evidence bytes may be issued only for an artifact compiled by this module"
      )
    }
    const current = canonicalAtomV2DurableRdfProjectionBytesUnsafe(artifact)
    if (Either.isLeft(current) || !sameBytes(current.right, compiledBytes)) {
      return fail(
        "ARTIFACT_TAMPERED",
        "compiled durable RDF artifact changed after its canonical bytes were recorded"
      )
    }
    return Either.right(Uint8Array.from(compiledBytes))
  })

export const compileCanonicalAtomV2DurableRdfProjection = (
  runtime: CanonicalAtomV2DurableRuntime["Type"]
): Effect.Effect<CanonicalAtomV2DurableRdfProjection, CanonicalAtomV2DurableRdfProjectionError> =>
  recoverCanonicalAtomV2DurableForReadOnlyProjectionInternal(runtime, {
    maximumRecords: HSWM_CANONICAL_ATOM_V2_DURABLE_RDF_MAX_RECORDS,
    maximumRecoveredJournalBytes: HSWM_CANONICAL_ATOM_V2_DURABLE_RDF_MAX_JOURNAL_BYTES
  }).pipe(
    Effect.mapError((cause) =>
      cause instanceof CanonicalAtomV2StateJournalStoreError &&
      cause.reason === "RECOVERY_LIMIT_EXCEEDED"
        ? failure("RESOURCE_LIMIT_EXCEEDED", "durable journal prefix exceeds the projection recovery limits")
        : failure("RECOVERY_FAILED", "durable runtime refused the graph recovery observation")
    ),
    Effect.flatMap((witness) => {
      const compiled = total(() => compileFromWitness(runtime, witness))
      return Either.isLeft(compiled)
        ? Effect.fail(compiled.left)
        : Effect.succeed(compiled.right)
    })
  )

export const verifyCanonicalAtomV2DurableRdfProjection = (
  runtime: CanonicalAtomV2DurableRuntime["Type"],
  artifact: CanonicalAtomV2DurableRdfProjection
): Effect.Effect<CanonicalAtomV2DurableRdfProjection, CanonicalAtomV2DurableRdfProjectionError> =>
  compileCanonicalAtomV2DurableRdfProjection(runtime).pipe(
    Effect.flatMap((expected) => {
      const actualBytes = total(() => canonicalAtomV2DurableRdfProjectionBytesUnsafe(artifact))
      const expectedBytes = canonicalAtomV2DurableRdfProjectionBytes(expected)
      return Either.isLeft(actualBytes) ||
        Either.isLeft(expectedBytes) ||
        !sameBytes(actualBytes.right, expectedBytes.right)
        ? Effect.fail(failure("ARTIFACT_TAMPERED", "artifact differs from the current exact durable recovery projection"))
        : Effect.succeed(expected)
    })
  )

export const decodeCanonicalAtomV2DurableRdfProjectionBytes = (
  runtime: CanonicalAtomV2DurableRuntime["Type"],
  bytes: Uint8Array
): Effect.Effect<CanonicalAtomV2DurableRdfProjection, CanonicalAtomV2DurableRdfProjectionError> => {
  const decoded = total(() => {
    if (!(bytes instanceof Uint8Array)) {
      return fail("ARTIFACT_INVALID", "durable RDF artifact bytes must be Uint8Array")
    }
    const parsed = decodeCanonicalJsonBytes(bytes)
    if (Either.isLeft(parsed)) {
      return fail("ARTIFACT_INVALID", "durable RDF artifact bytes are not bounded duplicate-free JSON")
    }
    const canonical = canonicalJsonBytes(parsed.right)
    if (Either.isLeft(canonical) || !sameBytes(bytes, canonical.right)) {
      return fail("ARTIFACT_INVALID", "durable RDF artifact bytes must be exact canonical JSON/v1")
    }
    return Either.right(undefined)
  })
  if (Either.isLeft(decoded)) return Effect.fail(decoded.left)
  return compileCanonicalAtomV2DurableRdfProjection(runtime).pipe(
    Effect.flatMap((expected) => {
      const expectedBytes = canonicalAtomV2DurableRdfProjectionBytes(expected)
      return Either.isLeft(expectedBytes) || !sameBytes(bytes, expectedBytes.right)
        ? Effect.fail(failure("ARTIFACT_TAMPERED", "artifact bytes differ from the current exact durable recovery projection"))
        : Effect.succeed(expected)
    })
  )
}
