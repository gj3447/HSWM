import type { ParseResult } from "effect"
import { Context, Data, Effect, Either, Layer } from "effect"

import {
  CanonicalAtomV2ContentStore,
  CanonicalAtomV2ContentStoreError,
  makeCanonicalAtomV2ContentStoreMemoryLayer,
  sameCanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2SchemaContentBinding
} from "./canonical-atom-v2-content.js"
import { makeCanonicalAtomV2ContentFileStoreLayer } from "./canonical-atom-v2-content-file.js"
import {
  CanonicalAtomV2ContentBindingError,
  decodeCanonicalAtomV2SchemaContent,
  sameCanonicalAtomV2SchemaBinding,
  snapshotCanonicalAtomV2SchemaContentBinding,
  snapshotCanonicalAtomV2WriteContentBinding,
  validateCanonicalAtomV2WriteContentBindings,
  type CanonicalAtomV2ValidatedSchemaContent,
  type CanonicalAtomV2WriteContentBinding,
  type CommitCanonicalAtomsV2ContentBound
} from "./canonical-atom-v2-content-bound.js"
import {
  CanonicalAtomV2ContentAuthorizationDenied,
  decodeCanonicalAtomV2ContentBoundInput,
  decodeCanonicalAtomV2ContentGrants,
  makeCanonicalAtomV2ContentAuthorizer,
  prepareCanonicalAtomV2WriteContent,
  validateCanonicalAtomV2ContentGrantConfiguration
} from "./canonical-atom-v2-content-runtime.js"
import {
  CanonicalAtomV2Error,
  evolveCanonicalAtomsV2,
  makeCanonicalAtomV2AcceptedReceipt,
  snapshotCanonicalAtomV2State,
  type CanonicalAtomV2State
} from "./canonical-atom-v2-domain.js"
import {
  HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_V1_MEDIA_TYPE,
  CanonicalAtomV2StateJournalError,
  applyCanonicalAtomV2StateJournalCommit,
  applyCanonicalAtomV2StateJournalGenesis,
  canonicalAtomV2StateJournalRecordBytes,
  decodeCanonicalAtomV2StateJournalRecordBytes,
  describeCanonicalAtomV2StateJournalRecord,
  makeCanonicalAtomV2StateJournalCommit,
  makeCanonicalAtomV2StateJournalGenesis,
  snapshotCanonicalAtomV2StateJournalRecord,
  type CanonicalAtomV2StateJournalCommit,
  type CanonicalAtomV2StateJournalRecordDescriptor
} from "./canonical-atom-v2-state-journal.js"
import { makeCanonicalAtomV2StateJournalFileStoreLayer } from "./canonical-atom-v2-state-journal-file.js"
import {
  CanonicalAtomV2StateJournalStore,
  CanonicalAtomV2StateJournalStoreError,
  makeCanonicalAtomV2StateJournalStoreMemoryLayer,
  type CanonicalAtomV2StateJournalEntry
} from "./canonical-atom-v2-state-journal-store.js"
import {
  canonicalAtomV2KeyId,
  snapshotCommitCanonicalAtomsV2Command,
  type CanonicalAtomV2,
  type HSWMCanonicalSchemaV2
} from "./canonical-atom-v2-schema.js"
import { DNRD5_SCHEMA_VERSION } from "./canonical-atom-v2-dnrd5-identity.js"

export const HSWM_CANONICAL_ATOM_V2_LOCAL_DURABLE_STATE =
  "LOCAL_PREDECESSOR_BOUND_STATE_AND_RECEIPT_JOURNAL_V1" as const

export class CanonicalAtomV2DurableRuntimeError extends Data.TaggedError(
  "CanonicalAtomV2DurableRuntimeError"
)<{
  readonly reason:
    | "CONFIGURATION_INVALID"
    | "GENESIS_MISSING"
    | "JOURNAL_DESCRIPTOR_MISMATCH"
    | "JOURNAL_HEAD_MISMATCH"
    | "JOURNAL_RECORD_ORDER_INVALID"
    | "DNRD5_PERMIT_DISPATCH_REQUIRED"
  readonly detail: string
}> {}

export interface CanonicalAtomV2DurableReceipt {
  readonly record: CanonicalAtomV2StateJournalRecordDescriptor
  readonly commit: CanonicalAtomV2StateJournalCommit
}

export interface CanonicalAtomV2DurableState {
  readonly journalLineageId: string
  readonly journalHead: CanonicalAtomV2StateJournalRecordDescriptor
  readonly schema: CanonicalAtomV2SchemaContentBinding
  readonly canonical: CanonicalAtomV2State
  readonly atomBindings: ReadonlyArray<CanonicalAtomV2WriteContentBinding>
  readonly stateDurability: typeof HSWM_CANONICAL_ATOM_V2_LOCAL_DURABLE_STATE
}

export interface CanonicalAtomV2DurableEvolution {
  readonly state: CanonicalAtomV2DurableState
  readonly receipt: CanonicalAtomV2DurableReceipt
}

export type CanonicalAtomV2DurableRecoveryFailure =
  | CanonicalAtomV2ContentBindingError
  | CanonicalAtomV2ContentStoreError
  | CanonicalAtomV2DurableRuntimeError
  | CanonicalAtomV2Error
  | CanonicalAtomV2StateJournalError
  | CanonicalAtomV2StateJournalStoreError

export type CanonicalAtomV2DurableSubmitFailure =
  | ParseResult.ParseError
  | CanonicalAtomV2ContentAuthorizationDenied
  | CanonicalAtomV2DurableRecoveryFailure

export class CanonicalAtomV2DurableRuntime extends Context.Tag(
  "hswm/CanonicalAtomV2DurableRuntime"
)<
  CanonicalAtomV2DurableRuntime,
  {
    readonly schema: HSWMCanonicalSchemaV2
    readonly schemaContent: CanonicalAtomV2SchemaContentBinding
    readonly journalLineageId: string
    readonly stateDurability: typeof HSWM_CANONICAL_ATOM_V2_LOCAL_DURABLE_STATE
    readonly stageContent: (
      mediaType: string,
      bytes: Uint8Array
    ) => Effect.Effect<
      CanonicalAtomV2ContentDescriptor,
      CanonicalAtomV2ContentStoreError
    >
    readonly readContent: (
      descriptor: CanonicalAtomV2ContentDescriptor
    ) => Effect.Effect<Uint8Array, CanonicalAtomV2ContentStoreError>
    readonly snapshot: Effect.Effect<
      CanonicalAtomV2DurableState,
      CanonicalAtomV2DurableRecoveryFailure
    >
    readonly history: Effect.Effect<
      ReadonlyArray<CanonicalAtomV2DurableReceipt>,
      CanonicalAtomV2DurableRecoveryFailure
    >
    readonly submit: (
      input: unknown
    ) => Effect.Effect<
      CanonicalAtomV2DurableEvolution,
      CanonicalAtomV2DurableSubmitFailure
    >
  }
>() {}

type CanonicalAtomV2DurableCommit = (
  input: unknown
) => Effect.Effect<
  CanonicalAtomV2DurableEvolution,
  CanonicalAtomV2DurableSubmitFailure
>

/**
 * Module-held capability registry for schema-specific dispatchers.
 *
 * This seam is intentionally absent from the package root export.  It is not
 * an authority by itself: the DNRD-5 dispatcher must validate and atomically
 * consume the durable Permit before invoking it.  Source qualification must
 * also reject any other repository-internal importer of this seam.
 */
const internalCommitByRuntime = new WeakMap<
  CanonicalAtomV2DurableRuntime["Type"],
  CanonicalAtomV2DurableCommit
>()

export const commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal = (
  runtime: CanonicalAtomV2DurableRuntime["Type"],
  input: unknown
): Effect.Effect<
  CanonicalAtomV2DurableEvolution,
  CanonicalAtomV2DurableSubmitFailure
> => {
  const commit = internalCommitByRuntime.get(runtime)
  return commit === undefined
    ? Effect.fail(
        runtimeError(
          "CONFIGURATION_INVALID",
          "durable runtime is not registered for internal dispatcher commit"
        )
      )
    : commit(input)
}

interface RecoveredJournal {
  readonly state: CanonicalAtomV2State
  readonly atomBindings: ReadonlyArray<CanonicalAtomV2WriteContentBinding>
  readonly head: CanonicalAtomV2StateJournalRecordDescriptor
  readonly history: ReadonlyArray<CanonicalAtomV2DurableReceipt>
}

const runtimeError = (
  reason: CanonicalAtomV2DurableRuntimeError["reason"],
  detail: string
): CanonicalAtomV2DurableRuntimeError =>
  new CanonicalAtomV2DurableRuntimeError({ reason, detail })

const sameJournalDescriptor = (
  left: CanonicalAtomV2StateJournalRecordDescriptor,
  right: CanonicalAtomV2ContentDescriptor
): boolean =>
  left.mediaType === right.mediaType &&
  left.byteLength === right.byteLength &&
  left.sha256 === right.sha256

const snapshotJournalDescriptor = (
  descriptor: CanonicalAtomV2StateJournalRecordDescriptor
): CanonicalAtomV2StateJournalRecordDescriptor =>
  Object.freeze({ ...descriptor })

const snapshotDurableReceipt = (
  receipt: CanonicalAtomV2DurableReceipt
): CanonicalAtomV2DurableReceipt =>
  Object.freeze({
    record: snapshotJournalDescriptor(receipt.record),
    commit: snapshotCanonicalAtomV2StateJournalRecord(
      receipt.commit
    ) as CanonicalAtomV2StateJournalCommit
  })

const snapshotDurableState = (
  journalLineageId: string,
  schema: CanonicalAtomV2SchemaContentBinding,
  recovered: RecoveredJournal
): CanonicalAtomV2DurableState =>
  Object.freeze({
    journalLineageId,
    journalHead: snapshotJournalDescriptor(recovered.head),
    schema: snapshotCanonicalAtomV2SchemaContentBinding(schema),
    canonical: snapshotCanonicalAtomV2State(recovered.state),
    atomBindings: Object.freeze(
      recovered.atomBindings.map(snapshotCanonicalAtomV2WriteContentBinding)
    ),
    stateDurability: HSWM_CANONICAL_ATOM_V2_LOCAL_DURABLE_STATE
  })

const descriptorFromEntry = (
  entry: CanonicalAtomV2StateJournalEntry
): Effect.Effect<
  CanonicalAtomV2StateJournalRecordDescriptor,
  CanonicalAtomV2DurableRuntimeError
> =>
  entry.descriptor.mediaType ===
    HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_V1_MEDIA_TYPE
    ? Effect.succeed(
        Object.freeze({
          mediaType: HSWM_CANONICAL_ATOM_V2_STATE_JOURNAL_V1_MEDIA_TYPE,
          byteLength: entry.descriptor.byteLength,
          sha256: entry.descriptor.sha256
        })
      )
    : Effect.fail(
        runtimeError(
          "JOURNAL_DESCRIPTOR_MISMATCH",
          "journal store returned an entry in another media domain"
        )
      )

const orderedAtomsForBindings = (
  writes: ReadonlyArray<CanonicalAtomV2>,
  bindings: ReadonlyArray<CanonicalAtomV2WriteContentBinding>
): Effect.Effect<
  ReadonlyArray<CanonicalAtomV2>,
  CanonicalAtomV2DurableRuntimeError
> => {
  const byKey = new Map(
    writes.map((atom) => [canonicalAtomV2KeyId(atom.key), atom] as const)
  )
  const ordered: Array<CanonicalAtomV2> = []
  for (const binding of bindings) {
    const atom = byKey.get(canonicalAtomV2KeyId(binding.key))
    if (atom === undefined) {
      return Effect.fail(
        runtimeError(
          "JOURNAL_RECORD_ORDER_INVALID",
          "validated journal binding lost its corresponding write atom"
        )
      )
    }
    ordered.push(atom)
  }
  return Effect.succeed(Object.freeze(ordered))
}

const recoverCanonicalAtomV2Journal = (
  contentStore: CanonicalAtomV2ContentStore["Type"],
  journalStore: CanonicalAtomV2StateJournalStore["Type"],
  schemaContent: CanonicalAtomV2ValidatedSchemaContent
): Effect.Effect<RecoveredJournal, CanonicalAtomV2DurableRecoveryFailure> =>
  Effect.gen(function* () {
    yield* contentStore.verify(schemaContent.binding.content)
    const entries = yield* journalStore.recover
    const first = entries[0]
    if (first === undefined) {
      return yield* runtimeError(
        "GENESIS_MISSING",
        "durable journal has no revision-zero genesis"
      )
    }

    const genesis = decodeCanonicalAtomV2StateJournalRecordBytes(first.bytes)
    if (Either.isLeft(genesis)) return yield* genesis.left
    if (
      genesis.right._tag !== "CanonicalAtomV2StateJournalGenesis" ||
      genesis.right.journalLineageId !== journalStore.journalLineageId ||
      genesis.right.stateRevision !== 0 ||
      !sameCanonicalAtomV2SchemaBinding(
        genesis.right.schema,
        schemaContent.binding
      )
    ) {
      return yield* runtimeError(
        "JOURNAL_RECORD_ORDER_INVALID",
        "revision zero is not the exact active-lineage genesis"
      )
    }
    const genesisDescriptor = describeCanonicalAtomV2StateJournalRecord(
      genesis.right
    )
    if (Either.isLeft(genesisDescriptor)) return yield* genesisDescriptor.left
    const storedGenesisDescriptor = yield* descriptorFromEntry(first)
    if (
      !sameJournalDescriptor(genesisDescriptor.right, first.descriptor) ||
      !sameJournalDescriptor(storedGenesisDescriptor, first.descriptor)
    ) {
      return yield* runtimeError(
        "JOURNAL_DESCRIPTOR_MISMATCH",
        "revision-zero bytes do not match their recovered descriptor"
      )
    }
    const initial = applyCanonicalAtomV2StateJournalGenesis(
      schemaContent.schema,
      genesis.right
    )
    if (Either.isLeft(initial)) return yield* initial.left

    let state = initial.right
    let head = genesisDescriptor.right
    const atomBindings: Array<CanonicalAtomV2WriteContentBinding> = []
    const history: Array<CanonicalAtomV2DurableReceipt> = []

    for (let index = 1; index < entries.length; index += 1) {
      const entry = entries[index]!
      const decoded = decodeCanonicalAtomV2StateJournalRecordBytes(entry.bytes)
      if (Either.isLeft(decoded)) return yield* decoded.left
      if (
        decoded.right._tag !== "CanonicalAtomV2StateJournalCommit" ||
        decoded.right.stateRevision !== index
      ) {
        return yield* runtimeError(
          "JOURNAL_RECORD_ORDER_INVALID",
          "journal records must be a genesis followed by contiguous commits"
        )
      }
      const envelopes = yield* Effect.forEach(
        decoded.right.writeBindings,
        (binding) =>
          contentStore.verify(binding.payload).pipe(
            Effect.zipRight(contentStore.get(binding.envelope))
          ),
        { concurrency: 1 }
      )
      const applied = applyCanonicalAtomV2StateJournalCommit(
        schemaContent.schema,
        {
          state,
          descriptor: head,
          journalLineageId: journalStore.journalLineageId,
          schema: schemaContent.binding
        },
        decoded.right,
        envelopes
      )
      if (Either.isLeft(applied)) return yield* applied.left
      const storedDescriptor = yield* descriptorFromEntry(entry)
      if (
        !sameJournalDescriptor(applied.right.descriptor, entry.descriptor) ||
        !sameJournalDescriptor(storedDescriptor, entry.descriptor)
      ) {
        return yield* runtimeError(
          "JOURNAL_DESCRIPTOR_MISMATCH",
          `journal revision ${index} bytes differ from the recovered descriptor`
        )
      }
      state = applied.right.state
      head = applied.right.descriptor
      atomBindings.push(
        ...applied.right.record.writeBindings.map(
          snapshotCanonicalAtomV2WriteContentBinding
        )
      )
      history.push(
        snapshotDurableReceipt({
          record: applied.right.descriptor,
          commit: applied.right.record
        })
      )
    }

    if (state.revision !== entries.length - 1) {
      return yield* runtimeError(
        "JOURNAL_RECORD_ORDER_INVALID",
        "replayed state revision differs from the durable journal length"
      )
    }
    return Object.freeze({
      state: snapshotCanonicalAtomV2State(state),
      atomBindings: Object.freeze(atomBindings),
      head: snapshotJournalDescriptor(head),
      history: Object.freeze(history)
    })
  })

/**
 * Internal composition seam. The supplied journal is the recovery truth; no
 * process-local Ref or snapshot is accepted as canonical state.
 */
export const makeCanonicalAtomV2DurableRuntimeLayer = (
  journalLineageId: string,
  rawSchemaBytes: Uint8Array,
  rawGrants: unknown = []
) => {
  const retainedSchemaBytes =
    rawSchemaBytes instanceof Uint8Array
      ? Uint8Array.from(rawSchemaBytes)
      : null
  return Layer.effect(
    CanonicalAtomV2DurableRuntime,
    Effect.gen(function* () {
      if (retainedSchemaBytes === null) {
        return yield* new CanonicalAtomV2ContentBindingError({
          reason: "SCHEMA_BYTES_INVALID",
          detail: "schema ingress must be Uint8Array"
        })
      }
      const contentStore = yield* CanonicalAtomV2ContentStore
      const journalStore = yield* CanonicalAtomV2StateJournalStore
      const decodedSchema = decodeCanonicalAtomV2SchemaContent(
        retainedSchemaBytes
      )
      if (Either.isLeft(decodedSchema)) return yield* decodedSchema.left
      const schemaContent = decodedSchema.right
      if (
        journalStore.journalLineageId !== journalLineageId ||
        journalStore.schemaContentSha256 !==
          schemaContent.binding.content.sha256
      ) {
        return yield* runtimeError(
          "CONFIGURATION_INVALID",
          "journal store does not match the requested lineage and exact schema bytes"
        )
      }

      const storedSchema = yield* contentStore.put(
        schemaContent.binding.content.mediaType,
        schemaContent.canonicalBytes
      )
      if (
        !sameCanonicalAtomV2ContentDescriptor(
          storedSchema,
          schemaContent.binding.content
        )
      ) {
        return yield* new CanonicalAtomV2ContentBindingError({
          reason: "SCHEMA_CONTENT_MISMATCH",
          detail: "stored schema bytes differ from the durable runtime binding"
        })
      }
      yield* contentStore.bindSchema(schemaContent.binding)
      const resolvedSchema = yield* contentStore.resolveSchema(
        schemaContent.binding.schemaVersion
      )
      if (
        !sameCanonicalAtomV2ContentDescriptor(
          resolvedSchema,
          schemaContent.binding.content
        )
      ) {
        return yield* new CanonicalAtomV2ContentBindingError({
          reason: "SCHEMA_CONTENT_MISMATCH",
          detail: "content store resolved a different durable schema binding"
        })
      }

      const decodedGrants = yield* decodeCanonicalAtomV2ContentGrants(
        rawGrants
      )
      const grants = yield* validateCanonicalAtomV2ContentGrantConfiguration(
        schemaContent.binding,
        decodedGrants
      )
      const authorize = makeCanonicalAtomV2ContentAuthorizer(
        schemaContent.binding,
        grants
      )

      const genesis = makeCanonicalAtomV2StateJournalGenesis(
        journalLineageId,
        schemaContent.schema
      )
      if (Either.isLeft(genesis)) return yield* genesis.left
      const genesisBytes = canonicalAtomV2StateJournalRecordBytes(genesis.right)
      if (Either.isLeft(genesisBytes)) return yield* genesisBytes.left
      yield* journalStore.publish({
        stateRevision: 0,
        expectedPredecessor: null,
        bytes: genesisBytes.right
      })
      yield* recoverCanonicalAtomV2Journal(
        contentStore,
        journalStore,
        schemaContent
      )

      const recover = () =>
        recoverCanonicalAtomV2Journal(
          contentStore,
          journalStore,
          schemaContent
        )

      const commit: CanonicalAtomV2DurableCommit = (input) =>
        Effect.gen(function* () {
          const decoded = yield* decodeCanonicalAtomV2ContentBoundInput(input)
          const command = snapshotCommitCanonicalAtomsV2Command(
            decoded.command
          )
          const contentInput: CommitCanonicalAtomsV2ContentBound =
            Object.freeze({
              _tag: decoded._tag,
              contractVersion: decoded.contractVersion,
              schemaContentSha256: decoded.schemaContentSha256,
              command,
              writeBindings: Object.freeze(
                decoded.writeBindings.map(
                  snapshotCanonicalAtomV2WriteContentBinding
                )
              )
            })
          yield* authorize(contentInput)
          const current = yield* recover()
          const candidate = evolveCanonicalAtomsV2(
            schemaContent.schema,
            current.state,
            command
          )
          if (Either.isLeft(candidate)) return yield* candidate.left

          const checkedBindings = validateCanonicalAtomV2WriteContentBindings(
            command.writes,
            contentInput.writeBindings
          )
          if (Either.isLeft(checkedBindings)) {
            return yield* checkedBindings.left
          }
          const orderedAtoms = yield* orderedAtomsForBindings(
            command.writes,
            checkedBindings.right
          )
          const receipt = makeCanonicalAtomV2AcceptedReceipt(
            command,
            current.state.revision,
            candidate.right.revision
          )
          const record = makeCanonicalAtomV2StateJournalCommit(
            schemaContent.schema,
            {
              state: current.state,
              descriptor: current.head,
              journalLineageId,
              schema: schemaContent.binding
            },
            receipt,
            checkedBindings.right,
            orderedAtoms
          )
          if (Either.isLeft(record)) return yield* record.left
          const recordBytes = canonicalAtomV2StateJournalRecordBytes(
            record.right
          )
          if (Either.isLeft(recordBytes)) return yield* recordBytes.left
          const expectedRecord = describeCanonicalAtomV2StateJournalRecord(
            record.right
          )
          if (Either.isLeft(expectedRecord)) return yield* expectedRecord.left

          const durableBindings = yield* prepareCanonicalAtomV2WriteContent(
            contentStore,
            command,
            checkedBindings.right
          )
          yield* journalStore.publish({
            stateRevision: candidate.right.revision,
            expectedPredecessor: current.head,
            bytes: recordBytes.right
          })
          const recovered = yield* recover()
          if (!sameJournalDescriptor(expectedRecord.right, recovered.head)) {
            return yield* runtimeError(
              "JOURNAL_HEAD_MISMATCH",
              "published record is not the exact recovered journal head"
            )
          }
          const committed = recovered.history.at(-1)
          if (
            committed === undefined ||
            committed.commit.receipt.transitionId !== command.transitionId ||
            committed.commit.writeBindings.length !== durableBindings.length
          ) {
            return yield* runtimeError(
              "JOURNAL_HEAD_MISMATCH",
              "recovered head does not contain the submitted receipt"
            )
          }
          return Object.freeze({
            state: snapshotDurableState(
              journalLineageId,
              schemaContent.binding,
              recovered
            ),
            receipt: snapshotDurableReceipt(committed)
          })
        })

      const runtime = CanonicalAtomV2DurableRuntime.of({
        schema: schemaContent.schema,
        schemaContent: snapshotCanonicalAtomV2SchemaContentBinding(
          schemaContent.binding
        ),
        journalLineageId,
        stateDurability: HSWM_CANONICAL_ATOM_V2_LOCAL_DURABLE_STATE,
        stageContent: (mediaType, inputBytes) =>
          contentStore.put(mediaType, Uint8Array.from(inputBytes)),
        readContent: (descriptor) => contentStore.get(descriptor),
        snapshot: recover().pipe(
          Effect.map((recovered) =>
            snapshotDurableState(
              journalLineageId,
              schemaContent.binding,
              recovered
            )
          )
        ),
        history: recover().pipe(
          Effect.map((recovered) =>
            Object.freeze(recovered.history.map(snapshotDurableReceipt))
          )
        ),
        submit: (input) =>
          schemaContent.binding.schemaVersion === DNRD5_SCHEMA_VERSION
            ? Effect.fail(
                runtimeError(
                  "DNRD5_PERMIT_DISPATCH_REQUIRED",
                  "DNRD-5 durable state changes require the Permit dispatcher"
                )
              )
            : commit(input)
      })
      internalCommitByRuntime.set(runtime, commit)
      return runtime
    })
  )
}

/** Process-local journal witness for deterministic tests; not restart durable. */
export const makeCanonicalAtomV2DurableRuntimeMemoryLayerForTest = (
  journalLineageId: string,
  rawSchemaBytes: Uint8Array,
  rawGrants: unknown = []
) => {
  const decoded = decodeCanonicalAtomV2SchemaContent(rawSchemaBytes)
  if (Either.isLeft(decoded)) return Layer.fail(decoded.left)
  return makeCanonicalAtomV2DurableRuntimeLayer(
    journalLineageId,
    rawSchemaBytes,
    rawGrants
  ).pipe(
    Layer.provide([
      makeCanonicalAtomV2ContentStoreMemoryLayer(),
      makeCanonicalAtomV2StateJournalStoreMemoryLayer(
        journalLineageId,
        decoded.right.binding.content.sha256
      )
    ])
  )
}

/**
 * Local POSIX content and predecessor-bound state/receipt durability. This is
 * neither distributed consensus nor canonical Permit or learning evidence.
 */
export const makeCanonicalAtomV2DurableRuntimeFileLayer = (
  rootPath: string,
  journalLineageId: string,
  rawSchemaBytes: Uint8Array,
  rawGrants: unknown = []
) => {
  const decoded = decodeCanonicalAtomV2SchemaContent(rawSchemaBytes)
  if (Either.isLeft(decoded)) return Layer.fail(decoded.left)
  return makeCanonicalAtomV2DurableRuntimeLayer(
    journalLineageId,
    rawSchemaBytes,
    rawGrants
  ).pipe(
    Layer.provide([
      makeCanonicalAtomV2ContentFileStoreLayer(rootPath),
      makeCanonicalAtomV2StateJournalFileStoreLayer(
        rootPath,
        journalLineageId,
        decoded.right.binding.content.sha256
      )
    ])
  )
}
