import { Data, Either, Schema } from "effect"

import {
  canonicalS2SControlJsonBytes,
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "./s2s-canonical.js"
import {
  S2SConfirmatoryEventSchema,
  S2SSha256Schema,
  advanceS2SConfirmatory,
  initialS2SConfirmatoryState,
  type S2SConfirmatoryEvent,
  type S2SConfirmatoryPhase,
  type S2SConfirmatoryState,
  type S2SSha256
} from "./s2s-confirmatory.js"

export const S2S_DURABLE_JOURNAL_SCHEMA_VERSION =
  "hswm-swm0w-s2s-durable-control-journal/v1" as const

export const S2S_DURABLE_JOURNAL_MAX_EVENTS = 10 as const
export const S2S_DURABLE_JOURNAL_MAX_FILES = 4 as const
export const S2S_DURABLE_JOURNAL_MAX_FILE_BYTES = 1_048_576 as const

const JournalRoleSchema = Schema.Literal(
  "REGISTRATION_CARRIER",
  "CANDIDATE_CARRIER",
  "ADJUDICATION_CARRIER",
  "FINAL_READBACK",
  "OPERATIONAL_VOID"
)

const PhaseSchema = Schema.Literal(
  "Prepared",
  "Registering",
  "RegistrationVerified",
  "ConfirmWaiting",
  "PulseEligible",
  "ConfirmRunning",
  "CandidateProduced",
  "CandidateArtifactVerified",
  "Adjudicating",
  "AdjudicationProduced",
  "EvidenceArtifactVerified",
  "Voided"
)

const DurableJournalDocumentSchema = Schema.Struct({
  schema_version: Schema.Literal(S2S_DURABLE_JOURNAL_SCHEMA_VERSION),
  role: JournalRoleSchema,
  predecessor_journal_file_sha256: Schema.NullOr(S2SSha256Schema),
  event_count: Schema.Number.pipe(
    Schema.int(),
    Schema.between(1, S2S_DURABLE_JOURNAL_MAX_EVENTS)
  ),
  event_receipt_sha256s: Schema.Array(S2SSha256Schema).pipe(
    Schema.minItems(1),
    Schema.maxItems(S2S_DURABLE_JOURNAL_MAX_EVENTS)
  ),
  events: Schema.Array(S2SConfirmatoryEventSchema).pipe(
    Schema.minItems(1),
    Schema.maxItems(S2S_DURABLE_JOURNAL_MAX_EVENTS)
  ),
  final_phase: PhaseSchema,
  final_control_receipt_sha256: S2SSha256Schema,
  journal_sha256: S2SSha256Schema
})

export type S2SDurableJournalRole = Schema.Schema.Type<
  typeof JournalRoleSchema
>

export type S2SDurableJournalDocument = Schema.Schema.Type<
  typeof DurableJournalDocumentSchema
>

export interface S2SDurableJournalSnapshot {
  readonly document: S2SDurableJournalDocument
  readonly canonicalBytes: Uint8Array
  readonly fileSha256: S2SSha256
  readonly state: S2SConfirmatoryState
}

export class S2SDurableJournalError extends Data.TaggedError(
  "S2SDurableJournalError"
)<{
  readonly reason:
    | "CANONICAL_BYTES_DRIFT"
    | "CHAIN_LENGTH_INVALID"
    | "DOCUMENT_PARSE_FAILED"
    | "DOCUMENT_SCHEMA_REJECTED"
    | "EVENT_PREFIX_MISMATCH"
    | "EVENT_RECEIPT_MISMATCH"
    | "FILE_SIZE_INVALID"
    | "FINAL_STATE_MISMATCH"
    | "PREDECESSOR_HASH_MISMATCH"
    | "ROLE_ORDER_INVALID"
    | "ROLE_PHASE_MISMATCH"
    | "SELF_HASH_MISMATCH"
    | "STATE_REPLAY_REJECTED"
}> {}

const fail = (
  reason: S2SDurableJournalError["reason"]
): Either.Either<never, S2SDurableJournalError> =>
  Either.left(new S2SDurableJournalError({ reason }))

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((byte, index) => byte === right[index])

const sameEvent = (
  left: S2SConfirmatoryEvent,
  right: S2SConfirmatoryEvent
): boolean => {
  const leftBytes = canonicalS2SControlJsonBytes(left)
  const rightBytes = canonicalS2SControlJsonBytes(right)
  return (
    Either.isRight(leftBytes) &&
    Either.isRight(rightBytes) &&
    sameBytes(leftBytes.right, rightBytes.right)
  )
}

const cloneEvent = (event: S2SConfirmatoryEvent): S2SConfirmatoryEvent =>
  structuredClone(event)

const cloneDocument = (
  document: S2SDurableJournalDocument
): S2SDurableJournalDocument => structuredClone(document)

const cloneState = (state: S2SConfirmatoryState): S2SConfirmatoryState =>
  structuredClone(state)

const makeSnapshot = (
  document: S2SDurableJournalDocument,
  canonicalBytes: Uint8Array,
  state: S2SConfirmatoryState
): S2SDurableJournalSnapshot => {
  const documentSnapshot = cloneDocument(document)
  const canonicalBytesSnapshot = Uint8Array.from(canonicalBytes)
  const stateSnapshot = cloneState(state)
  const snapshot: S2SDurableJournalSnapshot = {
    get document(): S2SDurableJournalDocument {
      return cloneDocument(documentSnapshot)
    },
    get canonicalBytes(): Uint8Array {
      return Uint8Array.from(canonicalBytesSnapshot)
    },
    fileSha256: S2SSha256Schema.make(
      rawS2SFileSha256(canonicalBytesSnapshot)
    ),
    get state(): S2SConfirmatoryState {
      return cloneState(stateSnapshot)
    }
  }
  return Object.freeze(snapshot)
}

const decodeDocument = (
  bytes: Uint8Array
): Either.Either<S2SDurableJournalDocument, S2SDurableJournalError> => {
  if (
    bytes.byteLength === 0 ||
    bytes[bytes.byteLength - 1] !== 0x0a ||
    bytes.some((byte) => byte > 0x7f) ||
    bytes
      .subarray(0, bytes.byteLength - 1)
      .some((byte) => byte === 0x0a || byte === 0x0d)
  ) {
    return fail("CANONICAL_BYTES_DRIFT")
  }
  let parsed: unknown
  try {
    const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes)
    parsed = JSON.parse(text.slice(0, -1))
  } catch {
    return fail("DOCUMENT_PARSE_FAILED")
  }
  const decoded = Schema.decodeUnknownEither(DurableJournalDocumentSchema, {
    onExcessProperty: "error"
  })(parsed)
  if (Either.isLeft(decoded)) return fail("DOCUMENT_SCHEMA_REJECTED")
  const canonical = canonicalS2SControlJsonBytes(decoded.right)
  if (Either.isLeft(canonical) || !sameBytes(canonical.right, bytes)) {
    return fail("CANONICAL_BYTES_DRIFT")
  }
  return Either.right(decoded.right)
}

const replayEvents = (
  events: ReadonlyArray<S2SConfirmatoryEvent>
): Either.Either<
  {
    readonly receipts: ReadonlyArray<S2SSha256>
    readonly state: S2SConfirmatoryState
  },
  S2SDurableJournalError
> => {
  let state = initialS2SConfirmatoryState()
  const receipts: Array<S2SSha256> = []
  for (const event of events) {
    const transition = advanceS2SConfirmatory(state, event)
    if (Either.isLeft(transition)) return fail("STATE_REPLAY_REJECTED")
    state = transition.right
    receipts.push(state.latestControlReceiptSha256)
  }
  return Either.right({
    receipts: Object.freeze(receipts.slice()),
    state
  })
}

const roleAcceptsPhase = (
  role: S2SDurableJournalRole,
  phase: S2SConfirmatoryPhase
): boolean => {
  switch (role) {
    case "REGISTRATION_CARRIER":
      return phase === "Registering"
    case "CANDIDATE_CARRIER":
      return phase === "CandidateProduced"
    case "ADJUDICATION_CARRIER":
      return phase === "AdjudicationProduced"
    case "FINAL_READBACK":
      return phase === "EvidenceArtifactVerified"
    case "OPERATIONAL_VOID":
      return phase === "Voided"
  }
}

const healthyRoleSuccessor = (
  predecessor: S2SDurableJournalRole,
  next: S2SDurableJournalRole
): boolean => {
  switch (predecessor) {
    case "REGISTRATION_CARRIER":
      return next === "CANDIDATE_CARRIER" || next === "OPERATIONAL_VOID"
    case "CANDIDATE_CARRIER":
      return next === "ADJUDICATION_CARRIER" || next === "OPERATIONAL_VOID"
    case "ADJUDICATION_CARRIER":
      return next === "FINAL_READBACK" || next === "OPERATIONAL_VOID"
    case "FINAL_READBACK":
    case "OPERATIONAL_VOID":
      return false
  }
}

const initialRoleAcceptsEvents = (
  role: S2SDurableJournalRole,
  events: ReadonlyArray<S2SConfirmatoryEvent>
): boolean =>
  (role === "REGISTRATION_CARRIER" &&
    events.length === 1 &&
    events[0]?._tag === "BeginRegistration") ||
  (role === "OPERATIONAL_VOID" &&
    events.length === 1 &&
    events[0]?._tag === "RecordOperationalVoid")

const voidStateFitsPredecessorRole = (
  predecessorRole: S2SDurableJournalRole,
  state: S2SConfirmatoryState
): boolean => {
  if (state._tag !== "Voided") return false
  switch (predecessorRole) {
    case "REGISTRATION_CARRIER":
      return [
        "Registering",
        "RegistrationVerified",
        "ConfirmWaiting",
        "PulseEligible",
        "ConfirmRunning",
        "CandidateProduced"
      ].includes(state.lastAcceptedPhase)
    case "CANDIDATE_CARRIER":
      return [
        "CandidateProduced",
        "CandidateArtifactVerified",
        "Adjudicating",
        "AdjudicationProduced"
      ].includes(state.lastAcceptedPhase)
    case "ADJUDICATION_CARRIER":
      return state.lastAcceptedPhase === "AdjudicationProduced"
    case "FINAL_READBACK":
    case "OPERATIONAL_VOID":
      return false
  }
}

const validateDocumentSemantics = (
  document: S2SDurableJournalDocument,
  predecessor: S2SDurableJournalSnapshot | null
): Either.Either<S2SConfirmatoryState, S2SDurableJournalError> => {
  if (
    document.event_count !== document.events.length ||
    document.event_count !== document.event_receipt_sha256s.length
  ) {
    return fail("FINAL_STATE_MISMATCH")
  }
  if (predecessor === null) {
    if (
      document.predecessor_journal_file_sha256 !== null ||
      !initialRoleAcceptsEvents(document.role, document.events)
    ) {
      return fail("ROLE_ORDER_INVALID")
    }
  } else {
    if (
      document.predecessor_journal_file_sha256 !== predecessor.fileSha256
    ) {
      return fail("PREDECESSOR_HASH_MISMATCH")
    }
    if (!healthyRoleSuccessor(predecessor.document.role, document.role)) {
      return fail("ROLE_ORDER_INVALID")
    }
    if (document.events.length <= predecessor.document.events.length) {
      return fail("EVENT_PREFIX_MISMATCH")
    }
    for (let index = 0; index < predecessor.document.events.length; index += 1) {
      const previous = predecessor.document.events[index]
      const current = document.events[index]
      if (
        previous === undefined ||
        current === undefined ||
        !sameEvent(previous, current) ||
        document.event_receipt_sha256s[index] !==
          predecessor.document.event_receipt_sha256s[index]
      ) {
        return fail("EVENT_PREFIX_MISMATCH")
      }
    }
  }
  const replay = replayEvents(document.events)
  if (Either.isLeft(replay)) return fail(replay.left.reason)
  if (
    predecessor !== null &&
    document.role === "OPERATIONAL_VOID" &&
    !voidStateFitsPredecessorRole(
      predecessor.document.role,
      replay.right.state
    )
  ) {
    return fail("ROLE_ORDER_INVALID")
  }
  if (
    replay.right.receipts.some(
      (receipt, index) => receipt !== document.event_receipt_sha256s[index]
    )
  ) {
    return fail("EVENT_RECEIPT_MISMATCH")
  }
  if (
    replay.right.state._tag !== document.final_phase ||
    replay.right.state.latestControlReceiptSha256 !==
      document.final_control_receipt_sha256
  ) {
    return fail("FINAL_STATE_MISMATCH")
  }
  if (!roleAcceptsPhase(document.role, replay.right.state._tag)) {
    return fail("ROLE_PHASE_MISMATCH")
  }
  const unsigned = {
    schema_version: document.schema_version,
    role: document.role,
    predecessor_journal_file_sha256:
      document.predecessor_journal_file_sha256,
    event_count: document.event_count,
    event_receipt_sha256s: document.event_receipt_sha256s,
    events: document.events,
    final_phase: document.final_phase,
    final_control_receipt_sha256: document.final_control_receipt_sha256
  }
  const selfHash = canonicalS2SControlSha256(unsigned)
  if (Either.isLeft(selfHash) || selfHash.right !== document.journal_sha256) {
    return fail("SELF_HASH_MISMATCH")
  }
  return Either.right(replay.right.state)
}

const parseOne = (
  bytes: Uint8Array,
  predecessor: S2SDurableJournalSnapshot | null
): Either.Either<S2SDurableJournalSnapshot, S2SDurableJournalError> => {
  const copied = Uint8Array.from(bytes)
  const document = decodeDocument(copied)
  if (Either.isLeft(document)) return fail(document.left.reason)
  const state = validateDocumentSemantics(document.right, predecessor)
  if (Either.isLeft(state)) return fail(state.left.reason)
  return Either.right(makeSnapshot(document.right, copied, state.right))
}

/**
 * Reconstruct a cross-job journal from exact carrier bytes. Callers must pass
 * every predecessor in order; a copied descendant is not accepted by itself.
 */
export const reconstructS2SDurableJournalChain = (
  canonicalJournals: ReadonlyArray<Uint8Array>
): Either.Either<S2SDurableJournalSnapshot, S2SDurableJournalError> => {
  if (
    canonicalJournals.length < 1 ||
    canonicalJournals.length > S2S_DURABLE_JOURNAL_MAX_FILES
  ) {
    return fail("CHAIN_LENGTH_INVALID")
  }
  let snapshot: S2SDurableJournalSnapshot | null = null
  for (const bytes of canonicalJournals) {
    if (
      !(bytes instanceof Uint8Array) ||
      bytes.byteLength < 1 ||
      bytes.byteLength > S2S_DURABLE_JOURNAL_MAX_FILE_BYTES
    ) {
      return fail("FILE_SIZE_INVALID")
    }
    const parsed = parseOne(bytes, snapshot)
    if (Either.isLeft(parsed)) return parsed
    snapshot = parsed.right
  }
  return snapshot === null ? fail("CHAIN_LENGTH_INVALID") : Either.right(snapshot)
}

const decodeEvents = (
  inputs: ReadonlyArray<unknown>
): Either.Either<ReadonlyArray<S2SConfirmatoryEvent>, S2SDurableJournalError> => {
  if (inputs.length < 1 || inputs.length > S2S_DURABLE_JOURNAL_MAX_EVENTS) {
    return fail("CHAIN_LENGTH_INVALID")
  }
  const events: Array<S2SConfirmatoryEvent> = []
  for (const input of inputs) {
    const decoded = Schema.decodeUnknownEither(S2SConfirmatoryEventSchema, {
      onExcessProperty: "error"
    })(input)
    if (Either.isLeft(decoded)) return fail("DOCUMENT_SCHEMA_REJECTED")
    events.push(cloneEvent(decoded.right))
  }
  return Either.right(Object.freeze(events))
}

/** Build one immutable carrier by appending events to the exact prior chain. */
export const buildS2SDurableJournal = (
  role: S2SDurableJournalRole,
  predecessorJournals: ReadonlyArray<Uint8Array>,
  appendedEvents: ReadonlyArray<unknown>
): Either.Either<S2SDurableJournalSnapshot, S2SDurableJournalError> => {
  let predecessor: S2SDurableJournalSnapshot | null = null
  if (predecessorJournals.length > 0) {
    const reconstructed = reconstructS2SDurableJournalChain(
      predecessorJournals
    )
    if (Either.isLeft(reconstructed)) return fail(reconstructed.left.reason)
    predecessor = reconstructed.right
  }
  const decodedEvents = decodeEvents(appendedEvents)
  if (Either.isLeft(decodedEvents)) return fail(decodedEvents.left.reason)
  const previousEvents = predecessor?.document.events ?? []
  const events = Object.freeze([
    ...previousEvents.map(cloneEvent),
    ...decodedEvents.right.map(cloneEvent)
  ])
  if (events.length > S2S_DURABLE_JOURNAL_MAX_EVENTS) {
    return fail("CHAIN_LENGTH_INVALID")
  }
  const replay = replayEvents(events)
  if (Either.isLeft(replay)) return fail(replay.left.reason)
  if (
    predecessor !== null &&
    role === "OPERATIONAL_VOID" &&
    !voidStateFitsPredecessorRole(
      predecessor.document.role,
      replay.right.state
    )
  ) {
    return fail("ROLE_ORDER_INVALID")
  }
  if (!roleAcceptsPhase(role, replay.right.state._tag)) {
    return fail("ROLE_PHASE_MISMATCH")
  }
  if (
    predecessor === null
      ? !initialRoleAcceptsEvents(role, events)
      : !healthyRoleSuccessor(predecessor.document.role, role)
  ) {
    return fail("ROLE_ORDER_INVALID")
  }
  const unsigned = {
    schema_version: S2S_DURABLE_JOURNAL_SCHEMA_VERSION,
    role,
    predecessor_journal_file_sha256:
      predecessor?.fileSha256 ?? null,
    event_count: events.length,
    event_receipt_sha256s: replay.right.receipts,
    events,
    final_phase: replay.right.state._tag,
    final_control_receipt_sha256:
      replay.right.state.latestControlReceiptSha256
  }
  const selfHash = canonicalS2SControlSha256(unsigned)
  if (Either.isLeft(selfHash)) return fail("SELF_HASH_MISMATCH")
  const document = {
    ...unsigned,
    journal_sha256: S2SSha256Schema.make(selfHash.right)
  }
  const canonicalBytes = canonicalS2SControlJsonBytes(document)
  if (Either.isLeft(canonicalBytes)) return fail("CANONICAL_BYTES_DRIFT")
  const decoded = Schema.decodeUnknownEither(DurableJournalDocumentSchema, {
    onExcessProperty: "error"
  })(document)
  if (Either.isLeft(decoded)) return fail("DOCUMENT_SCHEMA_REJECTED")
  return Either.right(
    makeSnapshot(decoded.right, canonicalBytes.right, replay.right.state)
  )
}
