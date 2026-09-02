import { createHash, randomUUID } from "node:crypto"
import { constants } from "node:fs"
import {
  link,
  lstat,
  mkdir,
  open,
  readdir,
  readFile,
  realpath,
  unlink
} from "node:fs/promises"
import { isAbsolute, join, resolve } from "node:path"

import { Context, Data, Effect, Either, Layer } from "effect"

import {
  HSWM_CANONICAL_ATOM_V2_DURABLE_RDF_PROJECTION_V1_MEDIA_TYPE,
  canonicalAtomV2DurableRdfProjectionBytes,
  compileCanonicalAtomV2DurableRdfProjection
} from "./canonical-atom-v2-durable-rdf-projection.js"
import {
  decodeCanonicalAtomV2ContentBoundInput,
} from "./canonical-atom-v2-content-runtime.js"
import type { CommitCanonicalAtomsV2ContentBound } from "./canonical-atom-v2-content-bound.js"
import {
  sameCanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2SchemaContentBinding
} from "./canonical-atom-v2-content.js"
import {
  CanonicalAtomV2DurableRuntime,
  commitCanonicalAtomV2DurableFromGraphLoopInternal,
  makeCanonicalAtomV2DurableGraphViewLayer,
  makeCanonicalAtomV2DurableRuntimeFileLayer,
  type CanonicalAtomV2DurableEvolution,
  type CanonicalAtomV2DurableState
} from "./canonical-atom-v2-durable-runtime.js"
import { canonicalAtomV2StateSha256 } from "./canonical-atom-v2-state-journal.js"
import { canonicalJsonBytes, decodeCanonicalJsonBytes, type CanonicalJson } from "./canonical-atom-v2-json.js"
import { canonicalAtomV2KeyId, type CanonicalAtomV2Key } from "./canonical-atom-v2-schema.js"

/**
 * GE-2 / LE-0 engineering profile.
 *
 * The local control journal is deliberately a research-harness record, not
 * canonical HSWM state. Every graph mutation still goes through the existing
 * schema-bound durable runtime and its predecessor-bound CAS journal.
 */
export const HSWM_GRAPH_LOOP_ENGINEERING_V1_CONTRACT_VERSION =
  "hswm-graph-loop-engineering/v1" as const
export const HSWM_GRAPH_LOOP_CONTROL_JOURNAL_V1_MEDIA_TYPE =
  "application/vnd.hswm.graph-loop-control-journal-v1+json" as const
export const HSWM_GRAPH_LOOP_CONTROL_MAX_EVENTS = 1_024 as const
export const HSWM_GRAPH_LOOP_CONTROL_MAX_EVENT_BYTES = 1_048_576 as const

type GraphLoopPhase =
  | "TRIGGERED"
  | "ACTION_SEALED"
  | "VERIFIED_ACCEPT"
  | "VERIFIED_RETRY"
  | "VERIFIED_REJECT"
  | "DELTA_INTENT"
  | "COMMITTED"
  | "REJECTED"
  | "QUARANTINED"
  | "RETRY_SCHEDULED"
  | "RESTORE_INTENT"
  | "RESTORED"
  | "STOPPED"
  | "ESCALATED"

type GraphLoopVerification = "NONE" | "ACCEPT" | "RETRY" | "REJECT" | "ESCALATE"

export interface GraphLoopSnapshot {
  readonly journalLineageId: string
  readonly schema: CanonicalAtomV2SchemaContentBinding
  readonly stateRevision: number
  readonly stateSha256: string
  readonly journalHead: {
    readonly mediaType: string
    readonly byteLength: number
    readonly sha256: string
  }
  readonly compiledProjection: CanonicalAtomV2ContentDescriptor
}

export interface GraphLoopContract {
  readonly runId: string
  readonly triggerId: string
  readonly actorId: string
  readonly verifierId: string
  readonly maximumAttempts: number
  readonly maximumActions: number
}

export interface GraphLoopControlEvent {
  readonly _tag: "GraphLoopControlEvent"
  readonly contractVersion: typeof HSWM_GRAPH_LOOP_ENGINEERING_V1_CONTRACT_VERSION
  readonly ordinal: number
  readonly predecessorSha256: string | null
  readonly runId: string
  readonly triggerId: string
  readonly actorId: string
  readonly verifierId: string
  readonly maximumAttempts: number
  readonly maximumActions: number
  readonly attempt: number
  readonly phase: GraphLoopPhase
  readonly snapshot: GraphLoopSnapshot
  readonly action: CanonicalAtomV2ContentDescriptor | null
  readonly outcome: CanonicalAtomV2ContentDescriptor | null
  readonly verification: GraphLoopVerification
  readonly transactionId: string | null
  readonly transitionId: string | null
  readonly keyIds: ReadonlyArray<string>
  readonly reason: string | null
}

type GraphLoopControlEventDraft = Omit<
  GraphLoopControlEvent,
  "_tag" | "contractVersion" | "ordinal" | "predecessorSha256"
>

export interface GraphLoopControlJournalEntry {
  readonly event: GraphLoopControlEvent
  readonly bytes: Uint8Array
  readonly sha256: string
}

export class GraphLoopControlJournalError extends Data.TaggedError(
  "GraphLoopControlJournalError"
)<{
  readonly operation: "INITIALIZE" | "RECOVER" | "APPEND"
  readonly reason:
    | "ATOMIC_PUBLICATION_UNSUPPORTED"
    | "CHAIN_FULL"
    | "CONCURRENT_APPEND"
    | "EVENT_INVALID"
    | "FILE_TOO_LARGE"
    | "FILE_TYPE_INVALID"
    | "IO_FAILED"
    | "ROOT_UNSAFE"
    | "SLOT_GAP"
  readonly detail: string
}> {}

export class GraphLoopControlError extends Data.TaggedError(
  "GraphLoopControlError"
)<{
  readonly reason:
    | "ACTION_BUDGET_EXHAUSTED"
    | "CONTRACT_INVALID"
    | "DELTA_INVALID"
    | "PHASE_INVALID"
    | "PROJECTION_INVALID"
    | "RESTORE_INVALID"
    | "RUN_ALREADY_EXISTS"
    | "RUN_NOT_FOUND"
    | "SNAPSHOT_STALE"
    | "VERIFIER_NOT_INDEPENDENT"
  readonly detail: string
}> {}

export class GraphLoopControlJournal extends Context.Tag(
  "hswm/GraphLoopControlJournal"
)<
  GraphLoopControlJournal,
  {
    readonly recover: Effect.Effect<
      ReadonlyArray<GraphLoopControlJournalEntry>,
      GraphLoopControlJournalError
    >
    readonly append: (
      event: GraphLoopControlEventDraft
    ) => Effect.Effect<GraphLoopControlJournalEntry, GraphLoopControlJournalError>
  }
>() {}

export interface GraphLoopRunState {
  readonly contract: GraphLoopContract
  readonly phase: GraphLoopPhase
  readonly attempt: number
  readonly actionCount: number
  readonly snapshot: GraphLoopSnapshot
  readonly action: CanonicalAtomV2ContentDescriptor | null
  readonly outcome: CanonicalAtomV2ContentDescriptor | null
  readonly transactionId: string | null
  readonly transitionId: string | null
  readonly keyIds: ReadonlyArray<string>
  readonly terminal: boolean
}

export interface GraphDeltaEvidence {
  readonly sealedTrajectory: CanonicalAtomV2ContentDescriptor
  readonly outcome: CanonicalAtomV2ContentDescriptor
  readonly credit: CanonicalAtomV2ContentDescriptor
  readonly authorization: CanonicalAtomV2ContentDescriptor
  readonly invariant: CanonicalAtomV2ContentDescriptor
  readonly authorizationStatus: "REFERENCE_AUTHORIZATION_NOT_CANONICAL_PERMIT"
  readonly conflictPolicy: "SERIALIZABLE_COMPARE_AND_SWAP"
}

export interface GraphDeltaRequest {
  readonly runId: string
  readonly transactionId: string
  readonly affectedKeys: ReadonlyArray<CanonicalAtomV2Key>
  readonly evidence: GraphDeltaEvidence
  readonly candidate: unknown
}

export interface GraphLoopRestoreRequest {
  readonly runId: string
  readonly transactionId: string
  readonly sourceKeys: ReadonlyArray<CanonicalAtomV2Key>
  readonly candidate: unknown
}

export interface GraphDeltaResult {
  readonly disposition: "COMMITTED" | "REJECTED" | "QUARANTINED"
  readonly evolution: CanonicalAtomV2DurableEvolution | null
}

export class GraphLoopEngineeringController extends Context.Tag(
  "hswm/GraphLoopEngineeringController"
)<
  GraphLoopEngineeringController,
  {
    readonly recover: Effect.Effect<
      ReadonlyMap<string, GraphLoopRunState>,
      GraphLoopControlJournalError | GraphLoopControlError
    >
    readonly trigger: (
      contract: GraphLoopContract
    ) => Effect.Effect<
      GraphLoopControlJournalEntry,
      GraphLoopControlJournalError | GraphLoopControlError
    >
    readonly sealAction: (
      runId: string,
      action: CanonicalAtomV2ContentDescriptor
    ) => Effect.Effect<
      GraphLoopControlJournalEntry,
      GraphLoopControlJournalError | GraphLoopControlError
    >
    readonly recordVerification: (
      runId: string,
      decision: Exclude<GraphLoopVerification, "NONE">,
      outcome: CanonicalAtomV2ContentDescriptor
    ) => Effect.Effect<
      GraphLoopControlJournalEntry,
      GraphLoopControlJournalError | GraphLoopControlError
    >
    readonly submitDelta: (
      request: GraphDeltaRequest
    ) => Effect.Effect<
      GraphDeltaResult,
      GraphLoopControlJournalError | GraphLoopControlError
    >
    readonly scheduleRetry: (
      runId: string,
      reason: string
    ) => Effect.Effect<
      GraphLoopControlJournalEntry,
      GraphLoopControlJournalError | GraphLoopControlError
    >
    readonly restore: (
      request: GraphLoopRestoreRequest
    ) => Effect.Effect<
      GraphDeltaResult,
      GraphLoopControlJournalError | GraphLoopControlError
    >
    readonly stop: (
      runId: string,
      reason: string
    ) => Effect.Effect<
      GraphLoopControlJournalEntry,
      GraphLoopControlJournalError | GraphLoopControlError
    >
    readonly escalate: (
      runId: string,
      reason: string,
      outcome?: CanonicalAtomV2ContentDescriptor
    ) => Effect.Effect<
      GraphLoopControlJournalEntry,
      GraphLoopControlJournalError | GraphLoopControlError
    >
  }
>() {}

const Identifier = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/
const Sha256 = /^[0-9a-f]{64}$/
const EVENT_PATTERN = /^graph-loop-event-(\d{4})\.json$/

interface DirectoryIdentity {
  readonly root: string
  readonly device: number
  readonly inode: number
}

const journalError = (
  operation: GraphLoopControlJournalError["operation"],
  reason: GraphLoopControlJournalError["reason"],
  detail: string
): GraphLoopControlJournalError =>
  new GraphLoopControlJournalError({ operation, reason, detail })

const controlError = (
  reason: GraphLoopControlError["reason"],
  detail: string
): GraphLoopControlError => new GraphLoopControlError({ reason, detail })

const sha256 = (bytes: Uint8Array): string =>
  createHash("sha256").update(bytes).digest("hex")

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((value, index) => value === right[index])

const sameDescriptor = (
  left: CanonicalAtomV2ContentDescriptor,
  right: CanonicalAtomV2ContentDescriptor
): boolean => sameCanonicalAtomV2ContentDescriptor(left, right)

const exactlyKeys = (value: object, keys: ReadonlyArray<string>): boolean => {
  const actual = Reflect.ownKeys(value)
  return actual.length === keys.length && keys.every((key) => actual.includes(key))
}

const object = (value: CanonicalJson): Readonly<Record<string, CanonicalJson>> | null =>
  typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as Readonly<Record<string, CanonicalJson>>
    : null

const descriptor = (value: CanonicalJson): CanonicalAtomV2ContentDescriptor | null => {
  const item = object(value)
  const mediaType = item?.["mediaType"]
  const byteLength = item?.["byteLength"]
  const digest = item?.["sha256"]
  if (
    item === null ||
    !exactlyKeys(item, ["mediaType", "byteLength", "sha256"]) ||
    typeof mediaType !== "string" ||
    typeof byteLength !== "number" ||
    typeof digest !== "string" ||
    !Number.isSafeInteger(byteLength) ||
    byteLength < 0 ||
    !Sha256.test(digest)
  ) return null
  return Object.freeze({
    mediaType,
    byteLength,
    sha256: digest
  })
}

const snapshot = (value: CanonicalJson): GraphLoopSnapshot | null => {
  const item = object(value)
  const journalLineageId = item?.["journalLineageId"]
  const stateRevision = item?.["stateRevision"]
  const stateSha256 = item?.["stateSha256"]
  const schemaRaw = item?.["schema"]
  const journalHeadRaw = item?.["journalHead"]
  const projectionRaw = item?.["compiledProjection"]
  if (
    item === null ||
    !exactlyKeys(item, [
      "journalLineageId", "schema", "stateRevision", "stateSha256", "journalHead", "compiledProjection"
    ]) ||
    typeof journalLineageId !== "string" ||
    !Identifier.test(journalLineageId) ||
    typeof stateRevision !== "number" ||
    !Number.isSafeInteger(stateRevision) || stateRevision < 0 ||
    typeof stateSha256 !== "string" || !Sha256.test(stateSha256)
  ) return null
  const schemaValue = schemaRaw === undefined ? null : object(schemaRaw)
  const headValue = journalHeadRaw === undefined ? null : object(journalHeadRaw)
  const schemaContent = schemaValue === null ? null : descriptor(schemaValue["content"] ?? null)
  const head = headValue === null ? null : descriptor(headValue as CanonicalJson)
  const projection = projectionRaw === undefined ? null : descriptor(projectionRaw)
  if (
    schemaValue === null ||
    !exactlyKeys(schemaValue, ["schemaVersion", "content"]) ||
    typeof schemaValue["schemaVersion"] !== "string" ||
    !Identifier.test(schemaValue["schemaVersion"]) ||
    schemaContent === null || head === null || projection === null
  ) return null
  return Object.freeze({
    journalLineageId,
    schema: Object.freeze({ schemaVersion: schemaValue["schemaVersion"], content: schemaContent }),
    stateRevision,
    stateSha256,
    journalHead: head,
    compiledProjection: projection
  })
}

const eventFromCanonicalJson = (
  value: CanonicalJson
): Either.Either<GraphLoopControlEvent, GraphLoopControlJournalError> => {
  const item = object(value)
  const keys = [
    "_tag", "contractVersion", "ordinal", "predecessorSha256", "runId", "triggerId", "actorId", "verifierId",
    "maximumAttempts", "maximumActions", "attempt", "phase", "snapshot", "action", "outcome", "verification",
    "transactionId", "transitionId", "keyIds", "reason"
  ]
  const tag = item?.["_tag"]
  const contractVersion = item?.["contractVersion"]
  const ordinal = item?.["ordinal"]
  const predecessorSha256 = item?.["predecessorSha256"]
  const runId = item?.["runId"]
  const triggerId = item?.["triggerId"]
  const actorId = item?.["actorId"]
  const verifierId = item?.["verifierId"]
  const maximumAttempts = item?.["maximumAttempts"]
  const maximumActions = item?.["maximumActions"]
  const attempt = item?.["attempt"]
  const phase = item?.["phase"]
  const rawSnapshot = item?.["snapshot"]
  const rawAction = item?.["action"]
  const rawOutcome = item?.["outcome"]
  const verification = item?.["verification"]
  const transactionId = item?.["transactionId"]
  const transitionId = item?.["transitionId"]
  const rawKeyIds = item?.["keyIds"]
  const reason = item?.["reason"]
  if (
    item === null || !exactlyKeys(item, keys) ||
    tag !== "GraphLoopControlEvent" ||
    contractVersion !== HSWM_GRAPH_LOOP_ENGINEERING_V1_CONTRACT_VERSION ||
    typeof ordinal !== "number" || !Number.isSafeInteger(ordinal) || ordinal < 1 ||
    !(predecessorSha256 === null || (typeof predecessorSha256 === "string" && Sha256.test(predecessorSha256))) ||
    [runId, triggerId, actorId, verifierId].some((identifier) => typeof identifier !== "string" || !Identifier.test(identifier)) ||
    [maximumAttempts, maximumActions, attempt].some((count) => typeof count !== "number" || !Number.isSafeInteger(count) || count < 1) ||
    typeof phase !== "string" || ![
      "TRIGGERED", "ACTION_SEALED", "VERIFIED_ACCEPT", "VERIFIED_RETRY", "VERIFIED_REJECT", "DELTA_INTENT",
      "COMMITTED", "REJECTED", "QUARANTINED", "RETRY_SCHEDULED", "RESTORE_INTENT", "RESTORED", "STOPPED", "ESCALATED"
    ].includes(phase) ||
    typeof verification !== "string" || !["NONE", "ACCEPT", "RETRY", "REJECT", "ESCALATE"].includes(verification) ||
    !(transactionId === null || (typeof transactionId === "string" && Identifier.test(transactionId))) ||
    !(transitionId === null || (typeof transitionId === "string" && Identifier.test(transitionId))) ||
    !(reason === null || (typeof reason === "string" && Identifier.test(reason))) ||
    !Array.isArray(rawKeyIds) || rawKeyIds.some((key: CanonicalJson) => typeof key !== "string" || key.length < 1 || key.length > 1_024)
  ) return Either.left(journalError("RECOVER", "EVENT_INVALID", "control event has an invalid strict shape"))
  const captured = rawSnapshot === undefined ? null : snapshot(rawSnapshot)
  const action = rawAction === null ? null : rawAction === undefined ? null : descriptor(rawAction)
  const outcome = rawOutcome === null ? null : rawOutcome === undefined ? null : descriptor(rawOutcome)
  if (captured === null || (rawAction !== null && action === null) || (rawOutcome !== null && outcome === null)) {
    return Either.left(journalError("RECOVER", "EVENT_INVALID", "control event has invalid graph artifacts"))
  }
  const keyIds = [...rawKeyIds] as string[]
  if (new Set(keyIds).size !== keyIds.length || [...keyIds].sort().some((key, index) => key !== keyIds[index])) {
    return Either.left(journalError("RECOVER", "EVENT_INVALID", "control event key ids must be sorted and unique"))
  }
  return Either.right(Object.freeze({
    _tag: "GraphLoopControlEvent",
    contractVersion: HSWM_GRAPH_LOOP_ENGINEERING_V1_CONTRACT_VERSION,
    ordinal,
    predecessorSha256,
    runId: runId as string,
    triggerId: triggerId as string,
    actorId: actorId as string,
    verifierId: verifierId as string,
    maximumAttempts: maximumAttempts as number,
    maximumActions: maximumActions as number,
    attempt: attempt as number,
    phase: phase as GraphLoopPhase,
    snapshot: captured,
    action,
    outcome,
    verification: verification as GraphLoopVerification,
    transactionId,
    transitionId,
    keyIds: Object.freeze(keyIds),
    reason
  }))
}

const eventBytes = (event: GraphLoopControlEvent): Either.Either<Uint8Array, GraphLoopControlJournalError> => {
  const encoded = canonicalJsonBytes(event as unknown as CanonicalJson)
  return Either.isLeft(encoded)
    ? Either.left(journalError("APPEND", "EVENT_INVALID", "control event is not canonical JSON"))
    : Either.right(encoded.right)
}

const decodeEventBytes = (bytes: Uint8Array): Either.Either<GraphLoopControlEvent, GraphLoopControlJournalError> => {
  const parsed = decodeCanonicalJsonBytes(bytes)
  if (Either.isLeft(parsed)) return Either.left(journalError("RECOVER", "EVENT_INVALID", "control event bytes are not canonical JSON"))
  const event = eventFromCanonicalJson(parsed.right)
  if (Either.isLeft(event)) return event
  const canonical = eventBytes(event.right)
  return Either.isLeft(canonical) || !sameBytes(canonical.right, bytes)
    ? Either.left(journalError("RECOVER", "EVENT_INVALID", "control event bytes drift from their canonical form"))
    : event
}

const fileName = (ordinal: number): string =>
  `graph-loop-event-${String(ordinal).padStart(4, "0")}.json`

const initializeDirectory = async (input: string): Promise<DirectoryIdentity> => {
  if (!isAbsolute(input)) throw journalError("INITIALIZE", "ROOT_UNSAFE", "control-journal root must be absolute")
  const root = resolve(input)
  await mkdir(root, { recursive: true, mode: 0o700 })
  const requested = await lstat(root)
  if (requested.isSymbolicLink() || !requested.isDirectory() || (requested.mode & 0o077) !== 0) {
    throw journalError("INITIALIZE", "ROOT_UNSAFE", "control-journal root must be a private plain directory")
  }
  const canonical = await realpath(root)
  const current = await lstat(canonical)
  if (current.isSymbolicLink() || !current.isDirectory() || (current.mode & 0o077) !== 0) {
    throw journalError("INITIALIZE", "ROOT_UNSAFE", "control-journal canonical root is unsafe")
  }
  return Object.freeze({ root: canonical, device: current.dev, inode: current.ino })
}

const assertDirectory = async (identity: DirectoryIdentity, operation: GraphLoopControlJournalError["operation"]): Promise<void> => {
  const current = await lstat(identity.root)
  if (current.isSymbolicLink() || !current.isDirectory() || current.dev !== identity.device || current.ino !== identity.inode || (current.mode & 0o077) !== 0) {
    throw journalError(operation, "ROOT_UNSAFE", "control-journal root changed identity or permissions")
  }
}

const recoverFromDisk = (identity: DirectoryIdentity): Effect.Effect<ReadonlyArray<GraphLoopControlJournalEntry>, GraphLoopControlJournalError> =>
  Effect.tryPromise({
    try: async () => {
      await assertDirectory(identity, "RECOVER")
      const entries = await readdir(identity.root, { withFileTypes: true })
      const ordinals: number[] = []
      for (const entry of entries) {
        if (!entry.name.startsWith("graph-loop-event-")) continue
        const match = EVENT_PATTERN.exec(entry.name)
        if (match === null || !entry.isFile()) throw journalError("RECOVER", "FILE_TYPE_INVALID", "invalid control-journal slot")
        const ordinal = Number(match[1])
        if (!Number.isSafeInteger(ordinal) || ordinal < 1 || ordinal > HSWM_GRAPH_LOOP_CONTROL_MAX_EVENTS) {
          throw journalError("RECOVER", "SLOT_GAP", "control-journal slot is outside the fixed bound")
        }
        ordinals.push(ordinal)
      }
      ordinals.sort((left, right) => left - right)
      if (ordinals.some((ordinal, index) => ordinal !== index + 1)) {
        throw journalError("RECOVER", "SLOT_GAP", "control-journal slots must form a contiguous prefix")
      }
      const recovered: GraphLoopControlJournalEntry[] = []
      let predecessor: string | null = null
      for (const ordinal of ordinals) {
        const path = join(identity.root, fileName(ordinal))
        const stat = await lstat(path)
        if (stat.isSymbolicLink() || !stat.isFile()) throw journalError("RECOVER", "FILE_TYPE_INVALID", "control-journal slot is not a regular file")
        if (stat.size < 1 || stat.size > HSWM_GRAPH_LOOP_CONTROL_MAX_EVENT_BYTES) throw journalError("RECOVER", "FILE_TOO_LARGE", "control-journal event exceeds its byte bound")
        const bytes = Uint8Array.from(await readFile(path))
        if (bytes.byteLength !== stat.size) throw journalError("RECOVER", "IO_FAILED", "control-journal event changed while being read")
        const event = decodeEventBytes(bytes)
        if (Either.isLeft(event) || event.right.ordinal !== ordinal || event.right.predecessorSha256 !== predecessor) {
          throw Either.isLeft(event) ? event.left : journalError("RECOVER", "EVENT_INVALID", "control-journal hash chain is invalid")
        }
        const digest = sha256(bytes)
        recovered.push(Object.freeze({ event: event.right, bytes, sha256: digest }))
        predecessor = digest
      }
      await assertDirectory(identity, "RECOVER")
      return Object.freeze(recovered)
    },
    catch: (error) => error instanceof GraphLoopControlJournalError
      ? error
      : journalError("RECOVER", "IO_FAILED", "control-journal recovery failed")
  })

const publishCreateOnly = async (identity: DirectoryIdentity, ordinal: number, bytes: Uint8Array): Promise<void> => {
  await assertDirectory(identity, "APPEND")
  const finalPath = join(identity.root, fileName(ordinal))
  const temporaryPath = join(identity.root, `.graph-loop-${randomUUID()}.tmp`)
  let temporary = false
  try {
    const handle = await open(temporaryPath, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW, 0o600)
    temporary = true
    try {
      await handle.writeFile(bytes)
      await handle.chmod(0o400)
      await handle.sync()
    } finally {
      await handle.close()
    }
    try {
      await link(temporaryPath, finalPath)
    } catch (error) {
      const code = typeof error === "object" && error !== null && "code" in error ? (error as { code?: string }).code : undefined
      if (code === "EEXIST") throw journalError("APPEND", "CONCURRENT_APPEND", "another writer occupied the next control-journal slot")
      if (code === "EPERM" || code === "EOPNOTSUPP") throw journalError("APPEND", "ATOMIC_PUBLICATION_UNSUPPORTED", "create-only link publication is unavailable")
      throw error
    }
    const directory = await open(identity.root, constants.O_RDONLY | constants.O_DIRECTORY)
    try {
      await directory.sync()
    } finally {
      await directory.close()
    }
  } finally {
    if (temporary) await unlink(temporaryPath).catch(() => undefined)
  }
}

/**
 * Local POSIX-only, append-only research-control ledger. It is intentionally
 * not a canonical HSWM store, an external notary, or distributed consensus.
 */
export const makeGraphLoopControlJournalFileLayer = (root: string) =>
  Layer.effect(GraphLoopControlJournal, Effect.gen(function* () {
    const identity = yield* Effect.tryPromise({
      try: () => initializeDirectory(root),
      catch: (error) => error instanceof GraphLoopControlJournalError
        ? error
        : journalError("INITIALIZE", "IO_FAILED", "control-journal initialization failed")
    })
    return GraphLoopControlJournal.of({
      recover: recoverFromDisk(identity),
      append: (draft) => Effect.gen(function* () {
        const current = yield* recoverFromDisk(identity)
        if (current.length >= HSWM_GRAPH_LOOP_CONTROL_MAX_EVENTS) {
          return yield* journalError("APPEND", "CHAIN_FULL", "control-journal reached its fixed event limit")
        }
        const event: GraphLoopControlEvent = Object.freeze({
          _tag: "GraphLoopControlEvent",
          contractVersion: HSWM_GRAPH_LOOP_ENGINEERING_V1_CONTRACT_VERSION,
          ordinal: current.length + 1,
          predecessorSha256: current.at(-1)?.sha256 ?? null,
          ...draft,
          keyIds: Object.freeze([...draft.keyIds])
        })
        const bytes = eventBytes(event)
        if (Either.isLeft(bytes) || bytes.right.byteLength > HSWM_GRAPH_LOOP_CONTROL_MAX_EVENT_BYTES) {
          return yield* journalError("APPEND", "EVENT_INVALID", "control event violates canonical byte limits")
        }
        yield* Effect.tryPromise({
          try: () => publishCreateOnly(identity, event.ordinal, bytes.right),
          catch: (error) => error instanceof GraphLoopControlJournalError
            ? error
            : journalError("APPEND", "IO_FAILED", "control-journal publication failed")
        })
        const recovered = yield* recoverFromDisk(identity)
        const stored = recovered.at(-1)
        if (stored === undefined || !sameBytes(stored.bytes, bytes.right)) {
          return yield* journalError("APPEND", "IO_FAILED", "published control event did not round-trip exactly")
        }
        return stored
      })
    })
  }))

const stateFor = (
  entries: ReadonlyArray<GraphLoopControlJournalEntry>
): Either.Either<ReadonlyMap<string, GraphLoopRunState>, GraphLoopControlError> => {
  const states = new Map<string, GraphLoopRunState>()
  for (const { event } of entries) {
    const existing = states.get(event.runId)
    const contract: GraphLoopContract = Object.freeze({
      runId: event.runId,
      triggerId: event.triggerId,
      actorId: event.actorId,
      verifierId: event.verifierId,
      maximumAttempts: event.maximumAttempts,
      maximumActions: event.maximumActions
    })
    const sameContract = existing !== undefined &&
      existing.contract.triggerId === contract.triggerId &&
      existing.contract.actorId === contract.actorId &&
      existing.contract.verifierId === contract.verifierId &&
      existing.contract.maximumAttempts === contract.maximumAttempts &&
      existing.contract.maximumActions === contract.maximumActions
    if (existing !== undefined && !sameContract) return Either.left(controlError("CONTRACT_INVALID", "one run cannot alter its trigger, principals, or budgets"))
    if (existing?.terminal === true) return Either.left(controlError("PHASE_INVALID", "a terminal run cannot accept another event"))
    const next = (phase: GraphLoopPhase, terminal = false): GraphLoopRunState => Object.freeze({
      contract,
      phase,
      attempt: event.attempt,
      actionCount: (existing?.actionCount ?? 0) + (event.phase === "ACTION_SEALED" ? 1 : 0),
      snapshot: event.snapshot,
      action: event.action,
      outcome: event.outcome,
      transactionId: event.transactionId,
      transitionId: event.transitionId,
      keyIds: event.keyIds,
      terminal
    })
    switch (event.phase) {
      case "TRIGGERED":
        if ((existing === undefined && event.attempt !== 1) || (existing !== undefined && (existing.phase !== "RETRY_SCHEDULED" || event.attempt !== existing.attempt + 1))) {
          return Either.left(controlError("PHASE_INVALID", "trigger must start attempt one or follow an explicit retry"))
        }
        if (event.attempt > contract.maximumAttempts || event.action !== null || event.outcome !== null || event.verification !== "NONE") return Either.left(controlError("CONTRACT_INVALID", "trigger violates its declared budget or event shape"))
        states.set(event.runId, next("TRIGGERED"))
        break
      case "ACTION_SEALED":
        if (existing?.phase !== "TRIGGERED" || event.attempt !== existing.attempt || event.action === null || event.verification !== "NONE" || event.outcome !== null) return Either.left(controlError("PHASE_INVALID", "action must follow a trigger and bind exactly one sealed action"))
        if ((existing.actionCount + 1) > contract.maximumActions) return Either.left(controlError("ACTION_BUDGET_EXHAUSTED", "action budget is exhausted"))
        states.set(event.runId, next("ACTION_SEALED"))
        break
      case "VERIFIED_ACCEPT":
      case "VERIFIED_RETRY":
      case "VERIFIED_REJECT": {
        if (existing?.phase !== "ACTION_SEALED" || event.attempt !== existing.attempt || event.action === null || event.outcome === null) return Either.left(controlError("PHASE_INVALID", "verification must follow a sealed action and bind an outcome"))
        const expected: GraphLoopVerification = event.phase === "VERIFIED_ACCEPT" ? "ACCEPT" : event.phase === "VERIFIED_RETRY" ? "RETRY" : "REJECT"
        if (event.verification !== expected) return Either.left(controlError("PHASE_INVALID", "verification phase and decision disagree"))
        states.set(event.runId, next(event.phase))
        break
      }
      case "DELTA_INTENT":
        if (existing?.phase !== "VERIFIED_ACCEPT" || event.transactionId === null || event.transitionId === null || event.verification !== "ACCEPT") return Either.left(controlError("PHASE_INVALID", "delta intent requires independent acceptance and identities"))
        states.set(event.runId, next("DELTA_INTENT"))
        break
      case "COMMITTED":
      case "REJECTED":
      case "QUARANTINED":
        if (existing === undefined || !["DELTA_INTENT", "RESTORE_INTENT"].includes(existing.phase) || event.transactionId !== existing.transactionId || event.transitionId !== existing.transitionId) return Either.left(controlError("PHASE_INVALID", "delta or restore disposition must close the exact pending intent"))
        states.set(event.runId, next(event.phase))
        break
      case "RETRY_SCHEDULED":
        if (existing === undefined || !["VERIFIED_RETRY", "QUARANTINED"].includes(existing.phase) || existing.attempt >= contract.maximumAttempts) return Either.left(controlError("PHASE_INVALID", "retry requires a retry/quarantine verdict and remaining attempt budget"))
        states.set(event.runId, next("RETRY_SCHEDULED"))
        break
      case "RESTORE_INTENT":
        if (existing?.phase !== "COMMITTED" || event.transactionId !== existing.transactionId || event.transitionId === null) return Either.left(controlError("PHASE_INVALID", "restore intent requires the exact committed graph delta"))
        states.set(event.runId, next("RESTORE_INTENT"))
        break
      case "RESTORED":
        if (existing?.phase !== "RESTORE_INTENT" || event.transactionId !== existing.transactionId || event.transitionId !== existing.transitionId) return Either.left(controlError("PHASE_INVALID", "restore disposition must close the exact restore intent"))
        states.set(event.runId, next("RESTORED"))
        break
      case "STOPPED":
        if (existing === undefined || !["VERIFIED_ACCEPT", "VERIFIED_REJECT", "COMMITTED", "REJECTED", "RESTORED"].includes(existing.phase)) return Either.left(controlError("PHASE_INVALID", "stop requires an explicit verifier verdict, disposition, or restore"))
        states.set(event.runId, next("STOPPED", true))
        break
      case "ESCALATED":
        if (existing === undefined) return Either.left(controlError("PHASE_INVALID", "escalation requires a triggered run"))
        states.set(event.runId, next("ESCALATED", true))
        break
    }
  }
  return Either.right(new Map(states))
}

const sortedKeyIds = (keys: ReadonlyArray<CanonicalAtomV2Key>): Either.Either<ReadonlyArray<string>, GraphLoopControlError> => {
  const ids = keys.map(canonicalAtomV2KeyId).sort()
  return ids.length === 0 || new Set(ids).size !== ids.length
    ? Either.left(controlError("DELTA_INVALID", "affected graph keys must be non-empty and unique"))
    : Either.right(Object.freeze(ids))
}

const captureSnapshot = (
  runtime: CanonicalAtomV2DurableRuntime["Type"]
): Effect.Effect<GraphLoopSnapshot, GraphLoopControlError> =>
  Effect.gen(function* () {
    const projection = yield* compileCanonicalAtomV2DurableRdfProjection(runtime).pipe(
      Effect.mapError(() => controlError("PROJECTION_INVALID", "durable compiled graph projection could not be captured"))
    )
    const bytes = canonicalAtomV2DurableRdfProjectionBytes(projection)
    if (Either.isLeft(bytes)) return yield* controlError("PROJECTION_INVALID", "compiled graph artifact has no canonical bytes")
    const stored = yield* runtime.stageContent(HSWM_CANONICAL_ATOM_V2_DURABLE_RDF_PROJECTION_V1_MEDIA_TYPE, bytes.right).pipe(
      Effect.mapError(() => controlError("PROJECTION_INVALID", "compiled graph artifact could not be staged"))
    )
    const current = yield* runtime.snapshot.pipe(
      Effect.mapError(() => controlError("SNAPSHOT_STALE", "durable canonical snapshot could not be recovered"))
    )
    const digest = canonicalAtomV2StateSha256(current.canonical)
    if (Either.isLeft(digest) ||
      projection.manifest.source.journalLineageId !== current.journalLineageId ||
      projection.manifest.source.stateRevision !== current.canonical.revision ||
      projection.manifest.source.stateSha256 !== digest.right ||
      projection.manifest.source.journalHead.sha256 !== current.journalHead.sha256 ||
      projection.manifest.source.schemaBinding.schemaVersion !== current.schema.schemaVersion ||
      !sameDescriptor(projection.manifest.source.schemaBinding.content, current.schema.content) ||
      projection.manifest.writeBack !== "FORBIDDEN"
    ) return yield* controlError("SNAPSHOT_STALE", "compiled projection and recovered canonical snapshot differ")
    return Object.freeze({
      journalLineageId: current.journalLineageId,
      schema: current.schema,
      stateRevision: current.canonical.revision,
      stateSha256: digest.right,
      journalHead: current.journalHead,
      compiledProjection: stored
    })
  })

const eventDraft = (
  state: GraphLoopRunState,
  phase: GraphLoopPhase,
  options: Partial<Pick<GraphLoopControlEventDraft, "snapshot" | "action" | "outcome" | "verification" | "transactionId" | "transitionId" | "keyIds" | "reason">> = {}
): GraphLoopControlEventDraft => Object.freeze({
  runId: state.contract.runId,
  triggerId: state.contract.triggerId,
  actorId: state.contract.actorId,
  verifierId: state.contract.verifierId,
  maximumAttempts: state.contract.maximumAttempts,
  maximumActions: state.contract.maximumActions,
  attempt: state.attempt,
  phase,
  snapshot: options.snapshot ?? state.snapshot,
  action: options.action ?? state.action,
  outcome: options.outcome ?? state.outcome,
  verification: options.verification ?? "NONE",
  transactionId: options.transactionId ?? state.transactionId,
  transitionId: options.transitionId ?? state.transitionId,
  keyIds: options.keyIds ?? state.keyIds,
  reason: options.reason ?? null
})

const currentRun = (
  journal: GraphLoopControlJournal["Type"],
  runId: string
): Effect.Effect<GraphLoopRunState, GraphLoopControlJournalError | GraphLoopControlError> =>
  journal.recover.pipe(Effect.flatMap((entries) => {
    const states = stateFor(entries)
    if (Either.isLeft(states)) return Effect.fail(states.left)
    const state = states.right.get(runId)
    return state === undefined
      ? Effect.fail(controlError("RUN_NOT_FOUND", "control-journal run does not exist"))
      : Effect.succeed(state)
  }))

const freshSnapshotMatches = (
  runtime: CanonicalAtomV2DurableRuntime["Type"],
  expected: GraphLoopSnapshot
): Effect.Effect<CanonicalAtomV2DurableState, GraphLoopControlError> =>
  runtime.snapshot.pipe(
    Effect.mapError(() => controlError("SNAPSHOT_STALE", "durable canonical state could not be recovered")),
    Effect.flatMap((state) => {
      const digest = canonicalAtomV2StateSha256(state.canonical)
      const matches = Either.isRight(digest) &&
        expected.journalLineageId === state.journalLineageId &&
        expected.stateRevision === state.canonical.revision &&
        expected.stateSha256 === digest.right &&
        expected.journalHead.sha256 === state.journalHead.sha256 &&
        expected.journalHead.byteLength === state.journalHead.byteLength &&
        expected.journalHead.mediaType === state.journalHead.mediaType &&
        expected.schema.schemaVersion === state.schema.schemaVersion &&
        sameDescriptor(expected.schema.content, state.schema.content)
      return matches ? Effect.succeed(state) : Effect.fail(controlError("SNAPSHOT_STALE", "graph delta source snapshot is no longer the canonical head"))
    })
  )

const verifyEvidenceDescriptors = (
  runtime: CanonicalAtomV2DurableRuntime["Type"],
  evidence: GraphDeltaEvidence,
  outcome: CanonicalAtomV2ContentDescriptor
): Effect.Effect<void, GraphLoopControlError> =>
  Effect.gen(function* () {
    if (evidence.authorizationStatus !== "REFERENCE_AUTHORIZATION_NOT_CANONICAL_PERMIT" || evidence.conflictPolicy !== "SERIALIZABLE_COMPARE_AND_SWAP" || !sameDescriptor(evidence.outcome, outcome)) {
      return yield* controlError("DELTA_INVALID", "graph delta lacks the exact independent outcome or engineering-only authority status")
    }
    const descriptors = [evidence.sealedTrajectory, evidence.outcome, evidence.credit, evidence.authorization, evidence.invariant]
    for (const item of descriptors) {
      yield* runtime.readContent(item).pipe(
        Effect.asVoid,
        Effect.mapError(() => controlError("DELTA_INVALID", "graph delta evidence content is absent or tampered"))
      )
    }
  })

const validateCandidate = (
  state: CanonicalAtomV2DurableState,
  source: GraphLoopSnapshot,
  candidate: CommitCanonicalAtomsV2ContentBound,
  affectedKeyIds: ReadonlyArray<string>
): Either.Either<void, GraphLoopControlError> => {
  const command = candidate.command
  const stateKeys = new Set(state.canonical.atoms.map((atom) => canonicalAtomV2KeyId(atom.key)))
  const readKeys = new Set(command.readSet.map(canonicalAtomV2KeyId))
  if (
    candidate.schemaContentSha256 !== source.schema.content.sha256 ||
    command.schemaVersion !== source.schema.schemaVersion ||
    command.expectedStateRevision !== source.stateRevision ||
    command.traceRef !== null || command.writes.length === 0 ||
    affectedKeyIds.some((key) => !readKeys.has(key)) ||
    command.readSet.some((key) => !stateKeys.has(canonicalAtomV2KeyId(key)))
  ) return Either.left(controlError("DELTA_INVALID", "graph delta is not bound to the exact snapshot and match read-set, or asks the current runtime to admit an unsupported trace"))
  return Either.right(undefined)
}

const isConflict = (error: unknown): boolean =>
  error instanceof Error && (
    ("code" in error && (error as { code?: string }).code === "STATE_REVISION_CONFLICT") ||
    ("reason" in error && ["CONCURRENT_PUBLICATION_CONFLICT", "PREDECESSOR_MISMATCH", "REVISION_CONFLICT"].includes((error as { reason?: string }).reason ?? ""))
  )

const rejectionReason = (error: unknown): string => {
  if (typeof error === "object" && error !== null) {
    const code = "code" in error ? (error as { readonly code?: unknown }).code : undefined
    const reason = "reason" in error ? (error as { readonly reason?: unknown }).reason : undefined
    const tag = "_tag" in error ? (error as { readonly _tag?: unknown })._tag : undefined
    if (typeof code === "string" && Identifier.test(code)) return code
    if (typeof reason === "string" && Identifier.test(reason)) return reason
    if (typeof tag === "string" && Identifier.test(tag)) return tag
  }
  return "RUNTIME_REJECTED"
}

export const makeGraphLoopEngineeringControllerLayer =
  Layer.effect(GraphLoopEngineeringController, Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const journal = yield* GraphLoopControlJournal
    const recover = journal.recover.pipe(Effect.flatMap((entries) => {
      const states = stateFor(entries)
      return Either.isLeft(states) ? Effect.fail(states.left) : Effect.succeed(states.right)
    }))
    return GraphLoopEngineeringController.of({
      recover,
      trigger: (contract) => Effect.gen(function* () {
        if (!Identifier.test(contract.runId) || !Identifier.test(contract.triggerId) || !Identifier.test(contract.actorId) || !Identifier.test(contract.verifierId) || contract.actorId === contract.verifierId || !Number.isSafeInteger(contract.maximumAttempts) || contract.maximumAttempts < 1 || contract.maximumAttempts > 16 || !Number.isSafeInteger(contract.maximumActions) || contract.maximumActions < 1 || contract.maximumActions > 64) {
          return yield* controlError(contract.actorId === contract.verifierId ? "VERIFIER_NOT_INDEPENDENT" : "CONTRACT_INVALID", "loop contract requires distinct actor/verifier and bounded positive budgets")
        }
        const entries = yield* journal.recover
        const states = stateFor(entries)
        if (Either.isLeft(states)) return yield* states.left
        const prior = states.right.get(contract.runId)
        if (prior?.terminal === true || (prior !== undefined && prior.phase !== "RETRY_SCHEDULED")) return yield* controlError("RUN_ALREADY_EXISTS", "run is active, terminal, or lacks an explicit retry schedule")
        const captured = yield* captureSnapshot(runtime)
        return yield* journal.append(Object.freeze({
          runId: contract.runId,
          triggerId: contract.triggerId,
          actorId: contract.actorId,
          verifierId: contract.verifierId,
          maximumAttempts: contract.maximumAttempts,
          maximumActions: contract.maximumActions,
          attempt: prior === undefined ? 1 : prior.attempt + 1,
          phase: "TRIGGERED",
          snapshot: captured,
          action: null,
          outcome: null,
          verification: "NONE",
          transactionId: null,
          transitionId: null,
          keyIds: Object.freeze([]),
          reason: null
        }))
      }),
      sealAction: (runId, action) => Effect.gen(function* () {
        const state = yield* currentRun(journal, runId)
        if (state.phase !== "TRIGGERED") return yield* controlError("PHASE_INVALID", "action can be sealed only after a trigger")
        if (state.actionCount >= state.contract.maximumActions) return yield* controlError("ACTION_BUDGET_EXHAUSTED", "loop action budget is exhausted")
        yield* runtime.readContent(action).pipe(Effect.asVoid, Effect.mapError(() => controlError("DELTA_INVALID", "sealed action content is absent")))
        return yield* journal.append(eventDraft(state, "ACTION_SEALED", { action, outcome: null, verification: "NONE", transactionId: null, transitionId: null, keyIds: Object.freeze([]) }))
      }),
      recordVerification: (runId, decision, outcome) => Effect.gen(function* () {
        const state = yield* currentRun(journal, runId)
        if (state.phase !== "ACTION_SEALED" || state.action === null || !["ACCEPT", "RETRY", "REJECT"].includes(decision)) return yield* controlError("PHASE_INVALID", "verification requires a sealed action and an explicit non-escalation verdict")
        yield* runtime.readContent(outcome).pipe(Effect.asVoid, Effect.mapError(() => controlError("DELTA_INVALID", "independent outcome content is absent")))
        const phase: GraphLoopPhase = decision === "ACCEPT" ? "VERIFIED_ACCEPT" : decision === "RETRY" ? "VERIFIED_RETRY" : "VERIFIED_REJECT"
        return yield* journal.append(eventDraft(state, phase, { outcome, verification: decision }))
      }),
      submitDelta: (request) => Effect.gen(function* () {
        const state = yield* currentRun(journal, request.runId)
        if (state.phase !== "VERIFIED_ACCEPT" || state.outcome === null || state.terminal) return yield* controlError("PHASE_INVALID", "graph delta requires one accepted independent verification")
        if (!Identifier.test(request.transactionId)) return yield* controlError("DELTA_INVALID", "transaction id is invalid")
        const affected = sortedKeyIds(request.affectedKeys)
        if (Either.isLeft(affected)) return yield* affected.left
        yield* verifyEvidenceDescriptors(runtime, request.evidence, state.outcome)
        const decoded = yield* decodeCanonicalAtomV2ContentBoundInput(request.candidate).pipe(
          Effect.mapError(() => controlError("DELTA_INVALID", "graph delta candidate fails strict content-bound decoding"))
        )
        const fresh = yield* freshSnapshotMatches(runtime, state.snapshot).pipe(Effect.either)
        if (Either.isLeft(fresh)) {
          const intentState = { ...state, phase: "DELTA_INTENT" as const, transactionId: request.transactionId, transitionId: decoded.command.transitionId, keyIds: affected.right }
          yield* journal.append(eventDraft(state, "DELTA_INTENT", {
            verification: "ACCEPT",
            transactionId: request.transactionId,
            transitionId: decoded.command.transitionId,
            keyIds: affected.right
          }))
          yield* journal.append(eventDraft(intentState, "QUARANTINED", { verification: "ACCEPT", reason: "SNAPSHOT_STALE" }))
          return Object.freeze({ disposition: "QUARANTINED" as const, evolution: null })
        }
        const valid = validateCandidate(fresh.right, state.snapshot, decoded, affected.right)
        if (Either.isLeft(valid)) return yield* valid.left
        yield* journal.append(eventDraft(state, "DELTA_INTENT", {
          verification: "ACCEPT",
          transactionId: request.transactionId,
          transitionId: decoded.command.transitionId,
          keyIds: affected.right
        }))
        const submitted = yield* commitCanonicalAtomV2DurableFromGraphLoopInternal(runtime, decoded).pipe(
          Effect.map((evolution) => ({ _tag: "Committed" as const, evolution })),
          Effect.catchAll((error) => Effect.succeed({ _tag: isConflict(error) ? "Quarantined" as const : "Rejected" as const, error }))
        )
        if (submitted._tag === "Committed") {
          yield* journal.append(eventDraft({ ...state, phase: "DELTA_INTENT", transactionId: request.transactionId, transitionId: decoded.command.transitionId, keyIds: affected.right }, "COMMITTED", { verification: "ACCEPT" }))
          return Object.freeze({ disposition: "COMMITTED" as const, evolution: submitted.evolution })
        }
        const phase = submitted._tag === "Quarantined" ? "QUARANTINED" : "REJECTED"
        yield* journal.append(eventDraft({ ...state, phase: "DELTA_INTENT", transactionId: request.transactionId, transitionId: decoded.command.transitionId, keyIds: affected.right }, phase, { verification: "ACCEPT", reason: submitted._tag === "Quarantined" ? "CAS_CONFLICT" : rejectionReason(submitted.error) }))
        return Object.freeze({ disposition: submitted._tag === "Quarantined" ? "QUARANTINED" as const : "REJECTED" as const, evolution: null })
      }),
      scheduleRetry: (runId, reason) => Effect.gen(function* () {
        const state = yield* currentRun(journal, runId)
        if (!Identifier.test(reason) || !["VERIFIED_RETRY", "QUARANTINED"].includes(state.phase) || state.attempt >= state.contract.maximumAttempts) return yield* controlError("PHASE_INVALID", "retry requires a bounded retry or quarantine disposition")
        return yield* journal.append(eventDraft(state, "RETRY_SCHEDULED", { reason, verification: state.phase === "VERIFIED_RETRY" ? "RETRY" : "ACCEPT" }))
      }),
      restore: (request) => Effect.gen(function* () {
        const state = yield* currentRun(journal, request.runId)
        if (state.phase !== "COMMITTED" || state.transactionId !== request.transactionId) return yield* controlError("RESTORE_INVALID", "restore requires the exact currently committed graph delta")
        const sources = sortedKeyIds(request.sourceKeys)
        if (Either.isLeft(sources)) return yield* sources.left
        const captured = yield* captureSnapshot(runtime)
        const current = yield* freshSnapshotMatches(runtime, captured)
        const decoded = yield* decodeCanonicalAtomV2ContentBoundInput(request.candidate).pipe(Effect.mapError(() => controlError("RESTORE_INVALID", "restore candidate fails strict content-bound decoding")))
        const readKeys = new Set(decoded.command.readSet.map(canonicalAtomV2KeyId))
        const originals = new Map(current.canonical.atoms.map((atom) => [canonicalAtomV2KeyId(atom.key), atom] as const))
        if (decoded.command.expectedStateRevision !== captured.stateRevision || decoded.command.traceRef !== null || sources.right.some((key) => !readKeys.has(key) || !originals.has(key)) || sources.right.some((key) => !decoded.command.writes.some((write) => sameDescriptor(write.content, originals.get(key)!.content)))) {
          return yield* controlError("RESTORE_INVALID", "restore must read each original source and write an exact original payload")
        }
        yield* journal.append(eventDraft({ ...state, snapshot: captured }, "RESTORE_INTENT", { transactionId: request.transactionId, transitionId: decoded.command.transitionId, keyIds: sources.right, verification: "ACCEPT" }))
        const submitted = yield* commitCanonicalAtomV2DurableFromGraphLoopInternal(runtime, decoded).pipe(
          Effect.map((evolution) => ({ _tag: "Committed" as const, evolution })),
          Effect.catchAll((error) => Effect.succeed({ _tag: isConflict(error) ? "Quarantined" as const : "Rejected" as const, error }))
        )
        const intentState = { ...state, phase: "RESTORE_INTENT" as const, snapshot: captured, transitionId: decoded.command.transitionId, keyIds: sources.right }
        if (submitted._tag === "Committed") {
          yield* journal.append(eventDraft(intentState, "RESTORED", { verification: "ACCEPT" }))
          return Object.freeze({ disposition: "COMMITTED" as const, evolution: submitted.evolution })
        }
        const phase = submitted._tag === "Quarantined" ? "QUARANTINED" : "REJECTED"
        yield* journal.append(eventDraft(intentState, phase, { verification: "ACCEPT", reason: submitted._tag === "Quarantined" ? "CAS_CONFLICT" : rejectionReason(submitted.error) }))
        return Object.freeze({ disposition: submitted._tag === "Quarantined" ? "QUARANTINED" as const : "REJECTED" as const, evolution: null })
      }),
      stop: (runId, reason) => Effect.gen(function* () {
        const state = yield* currentRun(journal, runId)
        if (!Identifier.test(reason) || !["VERIFIED_ACCEPT", "VERIFIED_REJECT", "COMMITTED", "REJECTED", "RESTORED"].includes(state.phase)) return yield* controlError("PHASE_INVALID", "stop requires a declared verifier verdict or terminal disposition")
        return yield* journal.append(eventDraft(state, "STOPPED", { reason }))
      }),
      escalate: (runId, reason, outcome) => Effect.gen(function* () {
        const state = yield* currentRun(journal, runId)
        if (!Identifier.test(reason) || state.terminal) return yield* controlError("PHASE_INVALID", "escalation requires one active nonterminal run")
        if (outcome !== undefined) {
          yield* runtime.readContent(outcome).pipe(Effect.asVoid, Effect.mapError(() => controlError("DELTA_INVALID", "escalation outcome content is absent")))
        }
        return yield* journal.append(
          outcome === undefined
            ? eventDraft(state, "ESCALATED", { reason, verification: "ESCALATE" })
            : eventDraft(state, "ESCALATED", { reason, outcome, verification: "ESCALATE" })
        )
      })
    })
  }))

/**
 * Standard externally composable GE-2/LE-0 runtime.
 *
 * It deliberately exports only the controller and read/stage/snapshot graph
 * view. The mutable durable runtime and its raw `submit` method stay behind
 * the package-private composition boundary; only `submitDelta` and `restore`
 * can reach the internal graph-loop mutation port.
 */
export const makeGraphLoopEngineeringFileLayer = (
  durableRoot: string,
  controlJournalRoot: string,
  journalLineageId: string,
  rawSchemaBytes: Uint8Array,
  rawGrants: unknown = []
) =>
  Layer.provide(
    Layer.merge(
      makeGraphLoopEngineeringControllerLayer,
      makeCanonicalAtomV2DurableGraphViewLayer
    ),
    Layer.merge(
      makeCanonicalAtomV2DurableRuntimeFileLayer(
        durableRoot,
        journalLineageId,
        rawSchemaBytes,
        rawGrants
      ),
      makeGraphLoopControlJournalFileLayer(controlJournalRoot)
    )
  )
