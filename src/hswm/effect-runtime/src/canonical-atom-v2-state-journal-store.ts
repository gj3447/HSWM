import { Context, Data, Effect, Either, Layer, Ref } from "effect"

import { makeCanonicalAtomV2ContentDescriptor } from "./canonical-atom-v2-content.js"
import {
  HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_V1_MEDIA_TYPE,
  type CanonicalAtomV2StateJournalRecordDescriptor
} from "./canonical-atom-v2-state-journal.js"

export const CANONICAL_ATOM_V2_STATE_JOURNAL_MAX_BYTES = 1_048_576 as const
export const HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_MEDIA_TYPE =
  HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_V1_MEDIA_TYPE

export interface CanonicalAtomV2StateJournalEntry {
  readonly descriptor: CanonicalAtomV2StateJournalRecordDescriptor
  readonly bytes: Uint8Array
}

export interface CanonicalAtomV2StateJournalRecoveryLimits {
  readonly maximumRecords: number
  readonly maximumRecoveredJournalBytes: number
}

export interface CanonicalAtomV2StateJournalPublish {
  readonly stateRevision: number
  readonly expectedPredecessor: CanonicalAtomV2StateJournalRecordDescriptor | null
  readonly bytes: Uint8Array
}

export interface CanonicalAtomV2StateJournalPublication {
  readonly _tag: "Committed" | "AlreadyCommitted"
  readonly recovery: ReadonlyArray<CanonicalAtomV2StateJournalEntry>
}

export class CanonicalAtomV2StateJournalStoreError extends Data.TaggedError(
  "CanonicalAtomV2StateJournalStoreError"
)<{
  readonly operation: "INITIALIZE" | "RECOVER" | "PUBLISH"
  readonly reason:
    | "ATOMIC_PUBLICATION_UNSUPPORTED"
    | "BYTE_LENGTH_INVALID"
    | "CONCURRENT_PUBLICATION_CONFLICT"
    | "CORRUPT_ENTRY"
    | "FILE_TYPE_INVALID"
    | "IO_FAILED"
    | "PREDECESSOR_MISMATCH"
    | "PUBLICATION_OUTCOME_UNKNOWN"
    | "RECOVERY_LIMIT_EXCEEDED"
    | "REVISION_CONFLICT"
    | "ROOT_UNSAFE"
    | "SLOT_LAYOUT_INVALID"
  readonly detail: string
}> {}

export type CanonicalAtomV2StateJournalStoreFailure =
  | CanonicalAtomV2StateJournalStoreError

export class CanonicalAtomV2StateJournalStore extends Context.Tag(
  "hswm/CanonicalAtomV2StateJournalStore"
)<
  CanonicalAtomV2StateJournalStore,
  {
    readonly journalLineageId: string
    readonly schemaContentSha256: string
    readonly recover: Effect.Effect<
      ReadonlyArray<CanonicalAtomV2StateJournalEntry>,
      CanonicalAtomV2StateJournalStoreFailure
    >
    readonly recoverWithin: (
      limits: CanonicalAtomV2StateJournalRecoveryLimits
    ) => Effect.Effect<
      ReadonlyArray<CanonicalAtomV2StateJournalEntry>,
      CanonicalAtomV2StateJournalStoreFailure
    >
    readonly publish: (
      input: CanonicalAtomV2StateJournalPublish
    ) => Effect.Effect<
      CanonicalAtomV2StateJournalPublication,
      CanonicalAtomV2StateJournalStoreFailure
    >
  }
>() {}

export const makeCanonicalAtomV2StateJournalStoreError = (
  operation: CanonicalAtomV2StateJournalStoreError["operation"],
  reason: CanonicalAtomV2StateJournalStoreError["reason"],
  detail: string
): CanonicalAtomV2StateJournalStoreError =>
  new CanonicalAtomV2StateJournalStoreError({ operation, reason, detail })

export const snapshotCanonicalAtomV2StateJournalEntry = (
  entry: CanonicalAtomV2StateJournalEntry
): CanonicalAtomV2StateJournalEntry =>
  Object.freeze({ descriptor: Object.freeze({ ...entry.descriptor }), bytes: Uint8Array.from(entry.bytes) })

export const snapshotCanonicalAtomV2StateJournalRecovery = (
  entries: ReadonlyArray<CanonicalAtomV2StateJournalEntry>
): ReadonlyArray<CanonicalAtomV2StateJournalEntry> =>
  Object.freeze(entries.map(snapshotCanonicalAtomV2StateJournalEntry))

const validConfig = (lineage: string, schema: string): boolean =>
  /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/.test(lineage) &&
  /^[0-9a-f]{64}$/.test(schema)

export const snapshotCanonicalAtomV2StateJournalRecoveryLimits = (
  limits: CanonicalAtomV2StateJournalRecoveryLimits
): Either.Either<CanonicalAtomV2StateJournalRecoveryLimits, CanonicalAtomV2StateJournalStoreError> => {
  if (
    typeof limits !== "object" ||
    limits === null ||
    !Number.isSafeInteger(limits.maximumRecords) ||
    limits.maximumRecords < 1 ||
    !Number.isSafeInteger(limits.maximumRecoveredJournalBytes) ||
    limits.maximumRecoveredJournalBytes < 1
  ) {
    return Either.left(makeCanonicalAtomV2StateJournalStoreError(
      "RECOVER",
      "RECOVERY_LIMIT_EXCEEDED",
      "journal recovery limits must be positive safe integers"
    ))
  }
  return Either.right(Object.freeze({
    maximumRecords: limits.maximumRecords,
    maximumRecoveredJournalBytes: limits.maximumRecoveredJournalBytes
  }))
}

const enforceRecoveryLimits = (
  entries: ReadonlyArray<CanonicalAtomV2StateJournalEntry>,
  limits: CanonicalAtomV2StateJournalRecoveryLimits
): Either.Either<void, CanonicalAtomV2StateJournalStoreError> => {
  if (entries.length > limits.maximumRecords) {
    return Either.left(makeCanonicalAtomV2StateJournalStoreError(
      "RECOVER",
      "RECOVERY_LIMIT_EXCEEDED",
      "journal recovery exceeds the record limit"
    ))
  }
  let totalBytes = 0
  for (const entry of entries) {
    totalBytes += entry.bytes.byteLength
    if (
      !Number.isSafeInteger(totalBytes) ||
      totalBytes > limits.maximumRecoveredJournalBytes
    ) {
      return Either.left(makeCanonicalAtomV2StateJournalStoreError(
        "RECOVER",
        "RECOVERY_LIMIT_EXCEEDED",
        "journal recovery exceeds the byte limit"
      ))
    }
  }
  return Either.right(undefined)
}

const descriptorFor = (
  bytes: Uint8Array
): Either.Either<CanonicalAtomV2StateJournalRecordDescriptor, CanonicalAtomV2StateJournalStoreError> => {
  if (bytes.byteLength < 1 || bytes.byteLength > CANONICAL_ATOM_V2_STATE_JOURNAL_MAX_BYTES) {
    return Either.left(makeCanonicalAtomV2StateJournalStoreError("PUBLISH", "BYTE_LENGTH_INVALID", "journal bytes violate the fixed bound"))
  }
  const descriptor = makeCanonicalAtomV2ContentDescriptor(
    HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_MEDIA_TYPE,
    bytes
  )
  return Either.isLeft(descriptor)
    ? Either.left(makeCanonicalAtomV2StateJournalStoreError("PUBLISH", "BYTE_LENGTH_INVALID", "journal descriptor is invalid"))
    : Either.right(Object.freeze({
        mediaType: HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_MEDIA_TYPE,
        byteLength: descriptor.right.byteLength,
        sha256: descriptor.right.sha256
      }))
}

const sameDescriptor = (
  left: CanonicalAtomV2StateJournalRecordDescriptor | null,
  right: CanonicalAtomV2StateJournalRecordDescriptor | null
): boolean =>
  left === null || right === null
    ? left === right
    : left.mediaType === right.mediaType &&
      left.byteLength === right.byteLength &&
      left.sha256 === right.sha256

const snapshotExpectedPredecessor = (
  input: CanonicalAtomV2StateJournalRecordDescriptor | null
): Either.Either<CanonicalAtomV2StateJournalRecordDescriptor | null, CanonicalAtomV2StateJournalStoreError> => {
  if (input === null) return Either.right(null)
  if (
    typeof input !== "object" ||
    input.mediaType !== HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_MEDIA_TYPE ||
    !Number.isSafeInteger(input.byteLength) ||
    input.byteLength < 1 ||
    input.byteLength > CANONICAL_ATOM_V2_STATE_JOURNAL_MAX_BYTES ||
    !/^[0-9a-f]{64}$/.test(input.sha256)
  ) {
    return Either.left(makeCanonicalAtomV2StateJournalStoreError("PUBLISH", "PREDECESSOR_MISMATCH", "predecessor must be an exact journal record descriptor or null"))
  }
  return Either.right(Object.freeze({ ...input }))
}

const validateInput = (
  input: CanonicalAtomV2StateJournalPublish
): Either.Either<{ readonly stateRevision: number; readonly expectedPredecessor: CanonicalAtomV2StateJournalRecordDescriptor | null; readonly bytes: Uint8Array; readonly descriptor: CanonicalAtomV2StateJournalRecordDescriptor }, CanonicalAtomV2StateJournalStoreError> => {
  if (!Number.isSafeInteger(input.stateRevision) || input.stateRevision < 0) {
    return Either.left(makeCanonicalAtomV2StateJournalStoreError("PUBLISH", "REVISION_CONFLICT", "state revision must be a safe nonnegative integer"))
  }
  const expectedPredecessor = snapshotExpectedPredecessor(input.expectedPredecessor)
  if (Either.isLeft(expectedPredecessor)) return Either.left(expectedPredecessor.left)
  if (!(input.bytes instanceof Uint8Array)) {
    return Either.left(makeCanonicalAtomV2StateJournalStoreError("PUBLISH", "BYTE_LENGTH_INVALID", "journal bytes must be Uint8Array"))
  }
  const bytes = Uint8Array.from(input.bytes)
  const descriptor = descriptorFor(bytes)
  return Either.isLeft(descriptor)
    ? Either.left(descriptor.left)
    : Either.right(Object.freeze({ stateRevision: input.stateRevision, expectedPredecessor: expectedPredecessor.right, bytes, descriptor: descriptor.right }))
}

export const makeCanonicalAtomV2StateJournalStoreMemoryLayer = (
  journalLineageId: string,
  schemaContentSha256: string
) =>
  Layer.effect(CanonicalAtomV2StateJournalStore, Effect.gen(function* () {
    if (!validConfig(journalLineageId, schemaContentSha256)) {
      return yield* Effect.fail(makeCanonicalAtomV2StateJournalStoreError("INITIALIZE", "ROOT_UNSAFE", "journal configuration is invalid"))
    }
    const entries = yield* Ref.make<ReadonlyArray<CanonicalAtomV2StateJournalEntry>>(Object.freeze([]))
    return CanonicalAtomV2StateJournalStore.of({
      journalLineageId,
      schemaContentSha256,
      recover: Ref.get(entries).pipe(Effect.map(snapshotCanonicalAtomV2StateJournalRecovery)),
      recoverWithin: (rawLimits) => {
        const limits = snapshotCanonicalAtomV2StateJournalRecoveryLimits(rawLimits)
        if (Either.isLeft(limits)) return Effect.fail(limits.left)
        return Ref.get(entries).pipe(
          Effect.flatMap((current) => {
            const enforced = enforceRecoveryLimits(current, limits.right)
            return Either.isLeft(enforced)
              ? Effect.fail(enforced.left)
              : Effect.succeed(snapshotCanonicalAtomV2StateJournalRecovery(current))
          })
        )
      },
      publish: (input) => {
        const prepared = validateInput(input)
        if (Either.isLeft(prepared)) return Effect.fail(prepared.left)
        type Outcome =
          | { readonly _tag: "Committed"; readonly recovery: ReadonlyArray<CanonicalAtomV2StateJournalEntry> }
          | { readonly _tag: "AlreadyCommitted"; readonly recovery: ReadonlyArray<CanonicalAtomV2StateJournalEntry> }
          | { readonly _tag: "Rejected"; readonly error: CanonicalAtomV2StateJournalStoreError }
        return Ref.modify(entries, (current): readonly [Outcome, ReadonlyArray<CanonicalAtomV2StateJournalEntry>] => {
          const currentPredecessor = current.at(-1)?.descriptor ?? null
          const revisionPredecessor = prepared.right.stateRevision === 0
            ? null
            : current[prepared.right.stateRevision - 1]?.descriptor ?? null
          const existing = current[prepared.right.stateRevision]
          if (!sameDescriptor(prepared.right.expectedPredecessor, revisionPredecessor)) {
            return [{ _tag: "Rejected" as const, error: makeCanonicalAtomV2StateJournalStoreError("PUBLISH", "PREDECESSOR_MISMATCH", "journal predecessor does not match the exact preceding record descriptor") }, current] as const
          }
          if (existing !== undefined) {
            const same =
              existing.descriptor.sha256 === prepared.right.descriptor.sha256 &&
              existing.bytes.byteLength === prepared.right.bytes.byteLength &&
              existing.bytes.every((byte, index) => byte === prepared.right.bytes[index])
            return same
              ? [{ _tag: "AlreadyCommitted" as const, recovery: current }, current] as const
              : [{ _tag: "Rejected" as const, error: makeCanonicalAtomV2StateJournalStoreError("PUBLISH", "CONCURRENT_PUBLICATION_CONFLICT", "journal slot is already occupied by different bytes") }, current] as const
          }
          if (prepared.right.stateRevision !== current.length) {
            return [{ _tag: "Rejected" as const, error: makeCanonicalAtomV2StateJournalStoreError("PUBLISH", "REVISION_CONFLICT", "journal revision is not the next contiguous slot") }, current] as const
          }
          if (!sameDescriptor(prepared.right.expectedPredecessor, currentPredecessor)) {
            return [{ _tag: "Rejected" as const, error: makeCanonicalAtomV2StateJournalStoreError("PUBLISH", "PREDECESSOR_MISMATCH", "journal predecessor does not match recovered tail") }, current] as const
          }
          const next = Object.freeze([...current, Object.freeze({ descriptor: Object.freeze({ ...prepared.right.descriptor }), bytes: Uint8Array.from(prepared.right.bytes) })])
          return [{ _tag: "Committed" as const, recovery: next }, next] as const
        }).pipe(
          Effect.flatMap((outcome) =>
            outcome._tag === "Rejected"
              ? Effect.fail(outcome.error)
              : Effect.succeed(
                  Object.freeze({
                    _tag: outcome._tag,
                    recovery: snapshotCanonicalAtomV2StateJournalRecovery(
                      outcome.recovery
                    )
                  })
                )
          )
        )
      }
    })
  }))
