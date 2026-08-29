/** Durable DNRD-5 admission seam with same-command one-shot consumption. */
import { Data, Effect, Either, Schema } from "effect"

import {
  CommitCanonicalAtomsV2ContentBoundSchema,
  describeCanonicalAtomV2Envelope,
  makeCanonicalAtomV2ContentBoundInput,
  validateCanonicalAtomV2WriteContentBindings,
  type CommitCanonicalAtomsV2ContentBound
} from "./canonical-atom-v2-content-bound.js"
import {
  makeCanonicalAtomV2ContentDescriptor,
  sameCanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2ContentDescriptor
} from "./canonical-atom-v2-content.js"
import {
  CanonicalAtomV2DurableRuntime,
  commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal,
  recoverCanonicalAtomV2DurableFromDnrd5DispatcherInternal,
  type CanonicalAtomV2DurableEvolution,
  type CanonicalAtomV2DurableRecoveryWitness,
  type CanonicalAtomV2DurableSubmitFailure
} from "./canonical-atom-v2-durable-runtime.js"
import {
  HSWM_CANONICAL_JSON_MEDIA_TYPE,
  canonicalJsonBytes,
  canonicalJsonSha256,
  decodeCanonicalJsonBytes
} from "./canonical-atom-v2-json.js"
import {
  applyCanonicalAtomV2StateJournalCommit,
  applyCanonicalAtomV2StateJournalGenesis,
  canonicalAtomV2StateSha256,
  canonicalAtomV2StateJournalRecordBytes,
  decodeCanonicalAtomV2StateJournalRecordBytes,
  describeCanonicalAtomV2StateJournalRecord
} from "./canonical-atom-v2-state-journal.js"
import {
  canonicalAtomV2KeyId,
  type CanonicalAtomV2,
  type CommitCanonicalAtomsV2Command
} from "./canonical-atom-v2-schema.js"
import {
  type CanonicalAtomV2StateJournalRecordDescriptor,
  type CanonicalAtomV2StateJournalCommit
} from "./canonical-atom-v2-state-journal.js"
import {
  DNRD5_V2_CAPABILITY_CONSUMPTION_MEDIA_TYPE,
  DNRD5_V2_CONSUMPTION_COMMAND_INTENT_MEDIA_TYPE,
  Dnrd5V2ConsumptionCommandIntentSchema,
  Dnrd5V2ConsumptionCommandProjectionSchema,
  Dnrd5V2ConsumptionPayloadSchema,
  DNRD5_V2_EVIDENCE_SEAL_CONSUMPTION_MEDIA_TYPE,
  dnrd5V2ConsumptionAtomUid,
  validateDnrd5V2Consumption,
  type Dnrd5V2ConsumptionInput,
  type Dnrd5V2ConsumptionPayload,
  type Dnrd5V2ConsumptionValidated
} from "./canonical-atom-v2-dnrd5-v2-consumption.js"
import {
  validateDnrd5V2AuthorityDisjointPair,
  validateDnrd5V2AuthorityPayloadAtState,
  type Dnrd5V2AuthorityStateInput
} from "./canonical-atom-v2-dnrd5-v2-authority.js"
import {
  validateDnrd5V2EffectCommandCandidate,
  validateDnrd5V2RecordBoundEffect
} from "./canonical-atom-v2-dnrd5-v2-record-bound-effect.js"
import {
  DNRD5_V2_RECEIPT_PAYLOAD_MEDIA_TYPE,
  DNRD5_V2_RECEIPT_SEAL_V1,
  canonicalDnrd5V2ReceiptPayloadBytes,
  validateDnrd5V2ReceiptSealCandidate,
  validateDnrd5V2ReceiptSeal,
  type Dnrd5V2ReceiptPayload
} from "./canonical-atom-v2-dnrd5-v2-receipt-seal.js"
import {
  DNRD5_V2_REFERENCE_TYPE,
  DNRD5_V2_SCHEMA_VERSION,
  validateDnrd5V2CanonicalSchema
} from "./canonical-atom-v2-dnrd5-v2-schema.js"
import {
  DNRD5_CAPABILITY_CONSUMPTION_KIND,
  DNRD5_CAPABILITY_CONSUMPTION_MEDIA_TYPE,
  dnrd5CapabilityConsumptionAtomUid,
  validateDnrd5CapabilityConsumptionAtom,
  type Dnrd5CapabilityConsumptionReferenceAtoms
} from "./canonical-atom-v2-dnrd5-capability-consumption.js"
import {
  Dnrd5LocalExperimentalPermitInputSchema,
  resolveDnrd5LocalExperimentalPermit,
  type Dnrd5LocalExperimentalPermitInput
} from "./canonical-atom-v2-dnrd5-permit.js"
import {
  DNRD5_SCHEMA_VERSION,
  validateDnrd5CanonicalSchemaV2
} from "./canonical-atom-v2-dnrd5-schema.js"

export const DNRD5_DURABLE_PERMIT_SUBMIT_V1 =
  "hswm-dnrd5-durable-permit-submit/v1" as const
export const DNRD5_COMMAND_INTENT_V1 =
  "hswm-dnrd5-capability-consumption-command-intent/v1" as const
export const DNRD5_COMMAND_SET_PROJECTION_V1 =
  "hswm-dnrd5-command-set-projection/v1" as const

export interface Dnrd5DurablePermitSubmitInput {
  readonly _tag: "Dnrd5DurablePermitSubmitInput"
  readonly contractVersion: typeof DNRD5_DURABLE_PERMIT_SUBMIT_V1
  readonly permitInput: Dnrd5LocalExperimentalPermitInput
  readonly transition: CommitCanonicalAtomsV2ContentBound
  readonly consumptionContentBytes: Uint8Array
}

export type Dnrd5DurablePermitErrorCode =
  | "INPUT_INVALID"
  | "SCHEMA_INVALID"
  | "SNAPSHOT_STALE"
  | "CURRENT_RECORD_INVALID"
  | "PERMIT_DENIED"
  | "COMMAND_INVALID"
  | "CONSUMPTION_INVALID"
  | "NONCE_ALREADY_CONSUMED"
  | "POSTCONDITION_INVALID"

export class Dnrd5DurablePermitError extends Data.TaggedError(
  "Dnrd5DurablePermitError"
)<{
  readonly code: Dnrd5DurablePermitErrorCode
  readonly detail: string
}> {}

export type Dnrd5DurablePermitSubmitFailure =
  | Dnrd5DurablePermitError
  | CanonicalAtomV2DurableSubmitFailure

/**
 * Explicitly non-success terminal states for the successor two-CAS path.
 * A main effect is never reported as sealed until the independent R2 receipt
 * record has been recovered and checked.
 */
export type Dnrd5V2TwoCasMilestone =
  | "CAS1_EXACT_R1_RECEIPT_PENDING"
  | "CAS2_EXACT_R2_CONFIRMED"
  | "CAS1_PREDECESSOR_LOST"
  | "CAS2_PREDECESSOR_LOST"
  | "RECOVERY_INDETERMINATE"

export class Dnrd5V2TwoCasRecoveryError extends Data.TaggedError(
  "Dnrd5V2TwoCasRecoveryError"
)<{
  readonly milestone: Exclude<Dnrd5V2TwoCasMilestone, "CAS2_EXACT_R2_CONFIRMED">
  readonly detail: string
}> {}

/**
 * Re-reads the durable prefix rather than trusting a process-local CAS
 * return.  It is intentionally usable before any v2 submission: callers use
 * it to classify a crash window as pending/indeterminate, never as success.
 */
export const recoverDnrd5V2DurableHistoryBinding = (): Effect.Effect<
  {
    readonly snapshot: CanonicalAtomV2DurableEvolution["state"]
    readonly history: ReadonlyArray<CanonicalAtomV2DurableEvolution["receipt"]>
  },
  CanonicalAtomV2DurableSubmitFailure | Dnrd5V2TwoCasRecoveryError,
  CanonicalAtomV2DurableRuntime
> =>
  Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const witness = yield* recoverCanonicalAtomV2DurableFromDnrd5DispatcherInternal(runtime)
    const snapshot = witness.state
    const history = witness.history
    if (history.length !== snapshot.canonical.revision || witness.journal.length !== history.length + 1) {
      return yield* new Dnrd5V2TwoCasRecoveryError({
        milestone: "RECOVERY_INDETERMINATE",
        detail: "recovered history length is not the recovered state revision"
      })
    }
    const tail = history.at(-1)
    if (
      (tail === undefined && snapshot.canonical.revision !== 0) ||
      (tail !== undefined && !sameCanonicalAtomV2ContentDescriptor(tail.record, snapshot.journalHead))
    ) {
      return yield* new Dnrd5V2TwoCasRecoveryError({
        milestone: "RECOVERY_INDETERMINATE",
        detail: "recovered history tail is not the recovered durable head"
      })
    }
    for (let index = 0; index < history.length; index += 1) {
      const entry = history.at(index)
      const raw = witness.journal.at(index + 1)
      if (entry === undefined || raw === undefined) {
        return yield* new Dnrd5V2TwoCasRecoveryError({
          milestone: "RECOVERY_INDETERMINATE",
          detail: "recovered journal prefix is shorter than its declared revision"
        })
      }
      const bytes = canonicalAtomV2StateJournalRecordBytes(entry.commit)
      const descriptor = describeCanonicalAtomV2StateJournalRecord(entry.commit)
      if (
        Either.isLeft(bytes) ||
        Either.isLeft(descriptor) ||
        !sameCanonicalAtomV2ContentDescriptor(descriptor.right, entry.record) ||
        !sameCanonicalAtomV2ContentDescriptor(raw.descriptor, entry.record) ||
        !exactBytes(bytes.right, raw.bytes) ||
        entry.commit.stateRevision !== index + 1
      ) {
        return yield* new Dnrd5V2TwoCasRecoveryError({
          milestone: "RECOVERY_INDETERMINATE",
          detail: "recovered durable history contains a non-canonical or non-contiguous record"
        })
      }
    }
    return Object.freeze({ snapshot, history })
  })

const error = (
  code: Dnrd5DurablePermitErrorCode,
  detail: string
): Dnrd5DurablePermitError => new Dnrd5DurablePermitError({ code, detail })

const isSubmitConcurrencyConflict = (
  failure: CanonicalAtomV2DurableSubmitFailure
): boolean => {
  if (
    failure._tag === "CanonicalAtomV2Error" &&
    [
      "STATE_REVISION_CONFLICT",
      "TRANSITION_DUPLICATE",
      "ATOM_KEY_DUPLICATE"
    ].includes(failure.code)
  ) {
    return true
  }
  return (
    failure._tag === "CanonicalAtomV2StateJournalStoreError" &&
    failure.operation === "PUBLISH" &&
    [
      "CONCURRENT_PUBLICATION_CONFLICT",
      "PREDECESSOR_MISMATCH",
      "REVISION_CONFLICT"
    ].includes(failure.reason)
  )
}

const snapshot = <A>(value: A): A => {
  const cloned = structuredClone(value)
  const freeze = (candidate: unknown): void => {
    if (ArrayBuffer.isView(candidate)) return
    if (
      typeof candidate === "object" &&
      candidate !== null &&
      !Object.isFrozen(candidate)
    ) {
      Object.freeze(candidate)
      for (const child of Object.values(candidate)) freeze(child)
    }
  }
  freeze(cloned)
  return cloned
}

const sortedUnique = (values: ReadonlyArray<string>): ReadonlyArray<string> =>
  Object.freeze([...new Set(values)].sort())

export const describeDnrd5CommandSets = (
  command: CommitCanonicalAtomsV2Command,
  currentAtoms: ReadonlyArray<CanonicalAtomV2>
): Either.Either<
  {
    readonly readKindsSha256: string
    readonly writeKindsSha256: string
    readonly targetKindsSha256: string
    readonly readsetSha256: string
    readonly writesetSha256: string
    readonly targetAtomKeysSha256: string
  },
  Dnrd5DurablePermitError
> => {
  const byKey = new Map(
    currentAtoms.map((atom) => [canonicalAtomV2KeyId(atom.key), atom] as const)
  )
  const readKeys = command.readSet.map(canonicalAtomV2KeyId)
  const writeKeys = command.writes.map(({ key }) => canonicalAtomV2KeyId(key))
  if (
    new Set(readKeys).size !== readKeys.length ||
    new Set(writeKeys).size !== writeKeys.length ||
    readKeys.some((key) => !byKey.has(key))
  ) {
    return Either.left(
      error("COMMAND_INVALID", "command set projection contains duplicate or missing keys")
    )
  }
  const projections = {
    readKinds: sortedUnique(readKeys.map((key) => byKey.get(key)!.kind)),
    writeKinds: sortedUnique(command.writes.map(({ kind }) => kind)),
    targetKinds: sortedUnique(command.writes.map(({ kind }) => kind)),
    readset: Object.freeze([...readKeys].sort()),
    writeset: Object.freeze([...writeKeys].sort()),
    targetAtomKeys: Object.freeze([...writeKeys].sort())
  }
  const digest = (setName: string, values: ReadonlyArray<string>) =>
    canonicalJsonSha256({
      contractVersion: DNRD5_COMMAND_SET_PROJECTION_V1,
      setName,
      values
    })
  const hashes = {
    readKindsSha256: digest("READ_KINDS", projections.readKinds),
    writeKindsSha256: digest("WRITE_KINDS", projections.writeKinds),
    targetKindsSha256: digest("TARGET_KINDS", projections.targetKinds),
    readsetSha256: digest("READ_SET", projections.readset),
    writesetSha256: digest("WRITE_SET", projections.writeset),
    targetAtomKeysSha256: digest("TARGET_ATOM_KEYS", projections.targetAtomKeys)
  }
  const failed = Object.values(hashes).find(Either.isLeft)
  if (failed !== undefined && Either.isLeft(failed)) {
    return Either.left(
      error("COMMAND_INVALID", "command set projection is not canonical JSON")
    )
  }
  if (
    Either.isLeft(hashes.readKindsSha256) ||
    Either.isLeft(hashes.writeKindsSha256) ||
    Either.isLeft(hashes.targetKindsSha256) ||
    Either.isLeft(hashes.readsetSha256) ||
    Either.isLeft(hashes.writesetSha256) ||
    Either.isLeft(hashes.targetAtomKeysSha256)
  ) {
    throw new Error("unreachable Either narrowing failure")
  }
  return Either.right(
    Object.freeze({
      readKindsSha256: hashes.readKindsSha256.right,
      writeKindsSha256: hashes.writeKindsSha256.right,
      targetKindsSha256: hashes.targetKindsSha256.right,
      readsetSha256: hashes.readsetSha256.right,
      writesetSha256: hashes.writesetSha256.right,
      targetAtomKeysSha256: hashes.targetAtomKeysSha256.right
    })
  )
}

export const describeDnrd5CapabilityConsumptionCommandIntent = (
  command: CommitCanonicalAtomsV2Command,
  consumptionAtomUid: string
): Either.Either<
  {
    readonly bytes: Uint8Array
    readonly descriptor: CanonicalAtomV2ContentDescriptor
    readonly sha256: string
  },
  Dnrd5DurablePermitError
> => {
  const consumptionWrites = command.writes.filter(
    ({ key }) => key.atomUid === consumptionAtomUid
  )
  if (
    consumptionWrites.length !== 1 ||
    consumptionWrites[0]!.kind !== DNRD5_CAPABILITY_CONSUMPTION_KIND ||
    command.writes.some(
      (atom) =>
        atom.kind === DNRD5_CAPABILITY_CONSUMPTION_KIND &&
        atom.key.atomUid !== consumptionAtomUid
    )
  ) {
    return Either.left(
      error(
        "COMMAND_INVALID",
        "command must contain exactly the nonce-derived consumption atom"
      )
    )
  }
  const projection = {
    contractVersion: DNRD5_COMMAND_INTENT_V1,
    capabilityConsumptionAtomUid: consumptionAtomUid,
    command: {
      ...command,
      writes: command.writes.filter(
        ({ key }) => key.atomUid !== consumptionAtomUid
      )
    }
  }
  const bytes = canonicalJsonBytes(projection)
  const digest = canonicalJsonSha256(projection)
  if (Either.isLeft(bytes) || Either.isLeft(digest)) {
    return Either.left(
      error("COMMAND_INVALID", "command intent is not canonical JSON")
    )
  }
  return Either.right(
    Object.freeze({
      get bytes(): Uint8Array {
        return Uint8Array.from(bytes.right)
      },
      descriptor: Object.freeze({
        mediaType: HSWM_CANONICAL_JSON_MEDIA_TYPE,
        byteLength: bytes.right.byteLength,
        sha256: digest.right
      }),
      sha256: digest.right
    })
  )
}

const decodeInput = (
  input: unknown
): Either.Either<Dnrd5DurablePermitSubmitInput, Dnrd5DurablePermitError> => {
  if (
    typeof input !== "object" ||
    input === null ||
    Array.isArray(input) ||
    Object.getPrototypeOf(input) !== Object.prototype ||
    Object.keys(input).length !== 5 ||
    ![
      "_tag",
      "contractVersion",
      "permitInput",
      "transition",
      "consumptionContentBytes"
    ].every((key) => Object.prototype.hasOwnProperty.call(input, key))
  ) {
    return Either.left(error("INPUT_INVALID", "durable Permit input key set drifted"))
  }
  const candidate = input as Record<string, unknown>
  if (
    candidate["_tag"] !== "Dnrd5DurablePermitSubmitInput" ||
    candidate["contractVersion"] !== DNRD5_DURABLE_PERMIT_SUBMIT_V1 ||
    !(candidate["consumptionContentBytes"] instanceof Uint8Array)
  ) {
    return Either.left(error("INPUT_INVALID", "durable Permit input identity drifted"))
  }
  const permit = Schema.decodeUnknownEither(
    Dnrd5LocalExperimentalPermitInputSchema,
    { onExcessProperty: "error" }
  )(candidate["permitInput"])
  const transition = Schema.decodeUnknownEither(
    CommitCanonicalAtomsV2ContentBoundSchema,
    { onExcessProperty: "error" }
  )(candidate["transition"])
  if (Either.isLeft(permit) || Either.isLeft(transition)) {
    return Either.left(
      error("INPUT_INVALID", "Permit or content-bound transition shape is invalid")
    )
  }
  const retainedBytes = Uint8Array.from(
    candidate["consumptionContentBytes"] as Uint8Array
  )
  return Either.right(
    Object.freeze({
      _tag: "Dnrd5DurablePermitSubmitInput" as const,
      contractVersion: DNRD5_DURABLE_PERMIT_SUBMIT_V1,
      permitInput: snapshot(permit.right),
      transition: snapshot(transition.right),
      get consumptionContentBytes(): Uint8Array {
        return Uint8Array.from(retainedBytes)
      }
    })
  )
}

const atomForDescriptor = (
  atoms: ReadonlyArray<CanonicalAtomV2>,
  kind: string,
  descriptor: CanonicalAtomV2ContentDescriptor,
  label: string
): Either.Either<CanonicalAtomV2, Dnrd5DurablePermitError> => {
  const matches = atoms.filter(
    (atom) =>
      atom.kind === kind &&
      sameCanonicalAtomV2ContentDescriptor(atom.content, descriptor)
  )
  return matches.length === 1
    ? Either.right(matches[0]!)
    : Either.left(
        error(
          "CURRENT_RECORD_INVALID",
          `current state must contain exactly one descriptor-bound ${label}`
        )
      )
}

const referenceTarget = (
  atom: CanonicalAtomV2,
  role: string,
  atomsByKey: ReadonlyMap<string, CanonicalAtomV2>
): Either.Either<CanonicalAtomV2, Dnrd5DurablePermitError> => {
  const references = atom.references.filter(
    (reference) =>
      reference.referenceType === "hswm:dnrd5:reference" &&
      reference.role === `role:dnrd5:${role}`
  )
  const target =
    references.length === 1
      ? atomsByKey.get(canonicalAtomV2KeyId(references[0]!.target))
      : undefined
  return target === undefined
    ? Either.left(
        error("CONSUMPTION_INVALID", `consumption ${role} reference is not current`)
      )
    : Either.right(target)
}

const referenceAtomsFor = (
  consumption: CanonicalAtomV2,
  currentAtoms: ReadonlyArray<CanonicalAtomV2>
): Either.Either<
  Dnrd5CapabilityConsumptionReferenceAtoms,
  Dnrd5DurablePermitError
> => {
  const byKey = new Map(
    currentAtoms.map((atom) => [canonicalAtomV2KeyId(atom.key), atom] as const)
  )
  const required = (role: string) => referenceTarget(consumption, role, byKey)
  const grant = required("grant")
  const capability = required("capability")
  const revocation = required("revocation")
  if (Either.isLeft(grant)) return Either.left(grant.left)
  if (Either.isLeft(capability)) return Either.left(capability.left)
  if (Either.isLeft(revocation)) return Either.left(revocation.left)
  const optional = (role: string): Either.Either<CanonicalAtomV2 | null, Dnrd5DurablePermitError> => {
    const matching = consumption.references.filter(
      (reference) => reference.role === `role:dnrd5:${role}`
    )
    if (matching.length === 0) return Either.right(null)
    if (matching.length !== 1) {
      return Either.left(
        error("CONSUMPTION_INVALID", `consumption ${role} reference repeats`)
      )
    }
    const target = byKey.get(canonicalAtomV2KeyId(matching[0]!.target))
    return target === undefined
      ? Either.left(
          error("CONSUMPTION_INVALID", `consumption ${role} target is not current`)
        )
      : Either.right(target)
  }
  const credit = optional("credit")
  const validation = optional("validation")
  const restorePolicy = optional("restore-policy")
  const staging = optional("staging-successor")
  const w0 = optional("w0")
  for (const candidate of [credit, validation, restorePolicy, staging, w0]) {
    if (Either.isLeft(candidate)) return Either.left(candidate.left)
  }
  if (
    Either.isLeft(credit) ||
    Either.isLeft(validation) ||
    Either.isLeft(restorePolicy) ||
    Either.isLeft(staging) ||
    Either.isLeft(w0)
  ) {
    throw new Error("unreachable Either narrowing failure")
  }
  return Either.right({
    grantSnapshot: grant.right,
    capabilityIssuance: capability.right,
    currentRevocation: revocation.right,
    creditDecision: credit.right,
    candidateValidation: validation.right,
    restorePolicy: restorePolicy.right,
    stagingSuccessor: staging.right,
    w0Snapshot: w0.right
  })
}

const validateCurrentRevocationUniqueness = (
  atoms: ReadonlyArray<CanonicalAtomV2>,
  capability: CanonicalAtomV2,
  expectedRevocation: CanonicalAtomV2
): Either.Either<void, Dnrd5DurablePermitError> => {
  const capabilityKey = canonicalAtomV2KeyId(capability.key)
  const statuses = atoms.filter(
    (atom) =>
      atom.kind === "hswm:dnrd5:revocation_status" &&
      atom.references.some(
        (reference) =>
          reference.role === "role:dnrd5:capability" &&
          canonicalAtomV2KeyId(reference.target) === capabilityKey
      )
  )
  return statuses.length === 1 &&
    canonicalAtomV2KeyId(statuses[0]!.key) ===
      canonicalAtomV2KeyId(expectedRevocation.key)
    ? Either.right(undefined)
    : Either.left(
        error(
          "CURRENT_RECORD_INVALID",
          "capability must have exactly one current revocation-status atom"
        )
      )
}

const hasExactDnrd5Reference = (
  source: CanonicalAtomV2,
  role: string,
  target: CanonicalAtomV2
): boolean => {
  const matching = source.references.filter(
    (reference) =>
      reference.referenceType === "hswm:dnrd5:reference" &&
      reference.role === `role:dnrd5:${role}`
  )
  return (
    matching.length === 1 &&
    canonicalAtomV2KeyId(matching[0]!.target) ===
      canonicalAtomV2KeyId(target.key)
  )
}

const exactBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((value, index) => value === right[index])

export const submitDnrd5LocalExperimentalState = (
  input: unknown
): Effect.Effect<
  CanonicalAtomV2DurableEvolution,
  Dnrd5DurablePermitSubmitFailure,
  CanonicalAtomV2DurableRuntime
> =>
  Effect.gen(function* () {
    const decoded = decodeInput(input)
    if (Either.isLeft(decoded)) return yield* decoded.left
    const supplied = decoded.right
    const permit = resolveDnrd5LocalExperimentalPermit(supplied.permitInput)
    if (Either.isLeft(permit)) {
      return yield* error("PERMIT_DENIED", permit.left.detail)
    }
    const runtime = yield* CanonicalAtomV2DurableRuntime
    if (
      runtime.schema.schemaVersion !== DNRD5_SCHEMA_VERSION ||
      Either.isLeft(validateDnrd5CanonicalSchemaV2(runtime.schema))
    ) {
      return yield* error("SCHEMA_INVALID", "runtime does not use the exact DNRD-5 schema")
    }
    const current = yield* runtime.snapshot
    const stateSha = canonicalAtomV2StateSha256(current.canonical)
    if (Either.isLeft(stateSha)) return yield* stateSha.left
    const consumptionUid = dnrd5CapabilityConsumptionAtomUid(
      supplied.permitInput.capability.oneShotNonceSha256
    )
    if (Either.isLeft(consumptionUid)) {
      return yield* error("CONSUMPTION_INVALID", consumptionUid.left.detail)
    }
    if (
      current.canonical.atoms.some(
        ({ key }) => key.atomUid === consumptionUid.right
      )
    ) {
      return yield* error(
        "NONCE_ALREADY_CONSUMED",
        "one-shot capability nonce already has a persistent consumption atom"
      )
    }
    const expectedSnapshot = supplied.permitInput.snapshot
    if (
      current.journalLineageId !== expectedSnapshot.journalLineageId ||
      !sameCanonicalAtomV2ContentDescriptor(
        current.journalHead,
        expectedSnapshot.journalHead
      ) ||
      current.canonical.revision !== expectedSnapshot.stateRevision ||
      stateSha.right !== expectedSnapshot.stateSha256
    ) {
      return yield* error(
        "SNAPSHOT_STALE",
        "Permit snapshot is not the exact recovered durable head and state"
      )
    }
    const command = supplied.transition.command
    if (
      supplied.transition.schemaContentSha256 !== current.schema.content.sha256 ||
      command.schemaVersion !== DNRD5_SCHEMA_VERSION ||
      command.expectedStateRevision !== current.canonical.revision ||
      command.actorClaim !== supplied.permitInput.principals.actor ||
      command.authorizationRef !== supplied.permitInput.capability.capabilityId ||
      command.scope !== supplied.permitInput.policy.scope ||
      command.decidedAt !== supplied.permitInput.evaluatedAt ||
      command.traceRef !== null
    ) {
      return yield* error(
        "COMMAND_INVALID",
        "transition does not bind the exact Permit actor, scope, capability, time, schema, and snapshot"
      )
    }
    const consumptionWrites = command.writes.filter(
      ({ key }) => key.atomUid === consumptionUid.right
    )
    if (consumptionWrites.length !== 1) {
      return yield* error(
        "COMMAND_INVALID",
        "transition lacks exactly one nonce-derived consumption atom"
      )
    }
    const consumption = consumptionWrites[0]!
    const writeKinds = command.writes.map(({ kind }) => kind).sort()
    const expectedWriteKinds = supplied.permitInput.effect === "ADMIT_REVISION"
      ? [
          DNRD5_CAPABILITY_CONSUMPTION_KIND,
          "hswm:dnrd5:macro_disposition",
          "hswm:dnrd5:transition_receipt"
        ].sort()
      : [
          DNRD5_CAPABILITY_CONSUMPTION_KIND,
          "hswm:dnrd5:restore_transaction"
        ].sort()
    if (
      writeKinds.length !== expectedWriteKinds.length ||
      writeKinds.some((kind, index) => kind !== expectedWriteKinds[index])
    ) {
      return yield* error(
        "COMMAND_INVALID",
        "effect command does not have the exact consumption plus admission/restore write grammar"
      )
    }
    const references = referenceAtomsFor(consumption, current.canonical.atoms)
    if (Either.isLeft(references)) return yield* references.left
    const checkedConsumption = validateDnrd5CapabilityConsumptionAtom(
      consumption,
      supplied.consumptionContentBytes,
      references.right
    )
    if (Either.isLeft(checkedConsumption)) {
      return yield* error("CONSUMPTION_INVALID", checkedConsumption.left.detail)
    }
    const grant = atomForDescriptor(
      current.canonical.atoms,
      "hswm:dnrd5:grant_snapshot",
      supplied.permitInput.grantSnapshot.descriptor,
      "grant snapshot"
    )
    const capability = atomForDescriptor(
      current.canonical.atoms,
      "hswm:dnrd5:capability_issuance",
      supplied.permitInput.capability.issuance,
      "capability issuance"
    )
    const revocation = atomForDescriptor(
      current.canonical.atoms,
      "hswm:dnrd5:revocation_status",
      supplied.permitInput.currentRevocation.descriptor,
      "current revocation"
    )
    const policy = atomForDescriptor(
      current.canonical.atoms,
      "hswm:dnrd5:permit_policy",
      supplied.permitInput.policy.descriptor,
      "Permit policy"
    )
    const authorization = atomForDescriptor(
      current.canonical.atoms,
      "hswm:dnrd5:authorization_decision",
      supplied.permitInput.authorizationDecision.descriptor,
      "authorization decision"
    )
    for (const candidate of [
      grant,
      capability,
      revocation,
      policy,
      authorization
    ]) {
      if (Either.isLeft(candidate)) return yield* candidate.left
    }
    if (
      Either.isLeft(grant) ||
      Either.isLeft(capability) ||
      Either.isLeft(revocation) ||
      Either.isLeft(policy) ||
      Either.isLeft(authorization)
    ) {
      throw new Error("unreachable Either narrowing failure")
    }
    if (
      canonicalAtomV2KeyId(grant.right.key) !==
        canonicalAtomV2KeyId(references.right.grantSnapshot.key) ||
      canonicalAtomV2KeyId(capability.right.key) !==
        canonicalAtomV2KeyId(references.right.capabilityIssuance.key) ||
      canonicalAtomV2KeyId(revocation.right.key) !==
        canonicalAtomV2KeyId(references.right.currentRevocation.key)
    ) {
      return yield* error(
        "CURRENT_RECORD_INVALID",
        "consumption references differ from exact Permit record descriptors"
      )
    }
    if (
      !hasExactDnrd5Reference(authorization.right, "policy", policy.right) ||
      !hasExactDnrd5Reference(capability.right, "authorization", authorization.right) ||
      !hasExactDnrd5Reference(capability.right, "policy", policy.right) ||
      !hasExactDnrd5Reference(revocation.right, "authorization", authorization.right) ||
      !hasExactDnrd5Reference(revocation.right, "capability", capability.right) ||
      !hasExactDnrd5Reference(grant.right, "policy", policy.right) ||
      !hasExactDnrd5Reference(grant.right, "authorization", authorization.right) ||
      !hasExactDnrd5Reference(grant.right, "capability", capability.right) ||
      !hasExactDnrd5Reference(grant.right, "revocation", revocation.right)
    ) {
      return yield* error(
        "CURRENT_RECORD_INVALID",
        "durable Permit records do not close over the exact typed-reference chain"
      )
    }
    const semanticRecords = [
      {
        label: "Permit policy",
        descriptor: supplied.permitInput.policy.descriptor,
        core: {
          scope: supplied.permitInput.policy.scope,
          allowedEffects: supplied.permitInput.policy.allowedEffects,
          allowedActors: supplied.permitInput.policy.allowedActors,
          validator: supplied.permitInput.policy.validator,
          validatorPrincipal: supplied.permitInput.policy.validatorPrincipal,
          allowedReadKindsSha256:
            supplied.permitInput.policy.allowedReadKindsSha256,
          allowedWriteKindsSha256:
            supplied.permitInput.policy.allowedWriteKindsSha256,
          allowedTargetKindsSha256:
            supplied.permitInput.policy.allowedTargetKindsSha256,
          exactReadsetSha256: supplied.permitInput.policy.exactReadsetSha256,
          exactWritesetSha256: supplied.permitInput.policy.exactWritesetSha256,
          exactTargetAtomKeysSha256:
            supplied.permitInput.policy.exactTargetAtomKeysSha256,
          restore: supplied.permitInput.policy.restore
        }
      },
      {
        label: "authorization decision",
        descriptor: supplied.permitInput.authorizationDecision.descriptor,
        core: {
          decision: supplied.permitInput.authorizationDecision.decision,
          actor: supplied.permitInput.authorizationDecision.actor,
          authorizer: supplied.permitInput.authorizationDecision.authorizer,
          recordCustodian:
            supplied.permitInput.authorizationDecision.recordCustodian,
          effect: supplied.permitInput.authorizationDecision.effect,
          scope: supplied.permitInput.authorizationDecision.scope,
          decidedAt: supplied.permitInput.authorizationDecision.decidedAt,
          notBefore: supplied.permitInput.authorizationDecision.notBefore,
          expiresAt: supplied.permitInput.authorizationDecision.expiresAt,
          generation: supplied.permitInput.authorizationDecision.generation
        }
      },
      {
        label: "capability issuance",
        descriptor: supplied.permitInput.capability.issuance,
        core: {
          capabilityId: supplied.permitInput.capability.capabilityId,
          issuedAt: supplied.permitInput.capability.issuedAt,
          expiresAt: supplied.permitInput.capability.expiresAt,
          scope: supplied.permitInput.capability.scope,
          allowedEffect: supplied.permitInput.capability.allowedEffect,
          oneShotNonceSha256:
            supplied.permitInput.capability.oneShotNonceSha256,
          policy: supplied.permitInput.capability.policy,
          authorization: supplied.permitInput.capability.authorization,
          authorizationGeneration:
            supplied.permitInput.capability.authorizationGeneration,
          capabilityGeneration:
            supplied.permitInput.capability.capabilityGeneration
        }
      },
      {
        label: "current revocation",
        descriptor: supplied.permitInput.currentRevocation.descriptor,
        core: {
          checkedAt: supplied.permitInput.currentRevocation.checkedAt,
          status: supplied.permitInput.currentRevocation.status,
          authorization: supplied.permitInput.currentRevocation.authorization,
          capability: supplied.permitInput.currentRevocation.capability,
          authorizationGeneration:
            supplied.permitInput.currentRevocation.authorizationGeneration,
          capabilityGeneration:
            supplied.permitInput.currentRevocation.capabilityGeneration
        }
      },
      {
        label: "grant snapshot",
        descriptor: supplied.permitInput.grantSnapshot.descriptor,
        core: {
          policy: supplied.permitInput.grantSnapshot.policy,
          authorization: supplied.permitInput.grantSnapshot.authorization,
          capability: supplied.permitInput.grantSnapshot.capability,
          revocation: supplied.permitInput.grantSnapshot.revocation
        }
      }
    ] as const
    for (const record of semanticRecords) {
      const expected = canonicalJsonBytes(record.core)
      if (Either.isLeft(expected)) {
        return yield* error(
          "CURRENT_RECORD_INVALID",
          `${record.label} cannot be canonically reconstructed`
        )
      }
      const durableBytes = yield* runtime.readContent(record.descriptor)
      if (!exactBytes(durableBytes, expected.right)) {
        return yield* error(
          "CURRENT_RECORD_INVALID",
          `${record.label} durable payload differs from the Permit semantic core`
        )
      }
    }
    const currentness = validateCurrentRevocationUniqueness(
      current.canonical.atoms,
      capability.right,
      revocation.right
    )
    if (Either.isLeft(currentness)) return yield* currentness.left
    const commandIntent = describeDnrd5CapabilityConsumptionCommandIntent(
      command,
      consumptionUid.right
    )
    if (Either.isLeft(commandIntent)) return yield* commandIntent.left
    const commandSets = describeDnrd5CommandSets(
      command,
      current.canonical.atoms
    )
    if (Either.isLeft(commandSets)) return yield* commandSets.left
    const declaredSets = supplied.permitInput.transition
    if (
      commandSets.right.readKindsSha256 !== declaredSets.readKindsSha256 ||
      commandSets.right.writeKindsSha256 !== declaredSets.writeKindsSha256 ||
      commandSets.right.targetKindsSha256 !== declaredSets.targetKindsSha256 ||
      commandSets.right.readsetSha256 !== declaredSets.readsetSha256 ||
      commandSets.right.writesetSha256 !== declaredSets.writesetSha256 ||
      commandSets.right.targetAtomKeysSha256 !==
        declaredSets.targetAtomKeysSha256
    ) {
      return yield* error(
        "COMMAND_INVALID",
        "Permit transition set commitments do not equal the recovered command"
      )
    }
    const content = checkedConsumption.right.content
    if (
      content.effect !== supplied.permitInput.effect ||
      content.capabilityNonceSha256 !==
        supplied.permitInput.capability.oneShotNonceSha256 ||
      content.permitInputSha256 !== permit.right.inputSha256 ||
      content.permitResolutionCoreSha256 !== permit.right.resolutionCoreSha256 ||
      !sameCanonicalAtomV2ContentDescriptor(
        content.expectedJournalHead,
        current.journalHead
      ) ||
      content.expectedStateRevision !== current.canonical.revision ||
      content.expectedStateSha256 !== stateSha.right ||
      content.transitionId !== command.transitionId ||
      content.commandIntentSha256 !== commandIntent.right.sha256 ||
      content.evaluatedAt !== supplied.permitInput.evaluatedAt ||
      !sameCanonicalAtomV2ContentDescriptor(
        supplied.permitInput.transition.command,
        commandIntent.right.descriptor
      )
    ) {
      return yield* error(
        "CONSUMPTION_INVALID",
        "consumption content does not bind the current Permit resolution and exact command intent"
      )
    }
    const staged = yield* runtime.stageContent(
      DNRD5_CAPABILITY_CONSUMPTION_MEDIA_TYPE,
      supplied.consumptionContentBytes
    )
    if (!sameCanonicalAtomV2ContentDescriptor(staged, consumption.content)) {
      return yield* error(
        "CONSUMPTION_INVALID",
        "staged consumption payload differs from the command atom"
      )
    }
    const result = yield* commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal(
      runtime,
      supplied.transition
    ).pipe(
      Effect.catchAll((submitFailure) =>
        isSubmitConcurrencyConflict(submitFailure)
          ? runtime.snapshot.pipe(
              Effect.map((recovered) => {
                const matches = recovered.canonical.atoms.filter(
                  ({ key }) =>
                    key.schemaVersion === consumption.key.schemaVersion &&
                    key.lineageId === consumption.key.lineageId &&
                    key.atomUid === consumption.key.atomUid &&
                    key.revisionId === consumption.key.revisionId
                )
                if (
                  matches.length !== 1 ||
                  !sameCanonicalAtomV2ContentDescriptor(
                    matches[0]!.content,
                    consumption.content
                  )
                ) {
                  return false
                }
                const recoveredReferences = referenceAtomsFor(
                  matches[0]!,
                  recovered.canonical.atoms
                )
                return (
                  Either.isRight(recoveredReferences) &&
                  Either.isRight(
                    validateDnrd5CapabilityConsumptionAtom(
                      matches[0]!,
                      supplied.consumptionContentBytes,
                      recoveredReferences.right
                    )
                  )
                )
              }),
              Effect.catchAll(() => Effect.succeed(false)),
              Effect.flatMap((wasConsumed) => {
                const failure: Dnrd5DurablePermitSubmitFailure = wasConsumed
                  ? error(
                      "NONCE_ALREADY_CONSUMED",
                      "a concurrent durable winner committed the exact one-shot consumption"
                    )
                  : submitFailure
                return Effect.fail(failure)
              })
            )
          : Effect.fail(submitFailure)
      )
    )
    const committed = result.state.canonical.atoms.filter(
      ({ key }) => key.atomUid === consumptionUid.right
    )
    if (
      committed.length !== 1 ||
      !sameCanonicalAtomV2ContentDescriptor(
        committed[0]!.content,
        consumption.content
      )
    ) {
      return yield* error(
        "POSTCONDITION_INVALID",
        "durable successor lacks the exact same-command consumption atom"
      )
    }
    return result
  })

/**
 * DNRD-5 v2's deliberately narrow durable ADMIT/RESTORE boundary.  Supplied
 * bytes remain candidates until the raw journal is recovered twice.  In
 * particular, this function makes no provider, occurrence, learning, or
 * efficacy claim.
 */
export const DNRD5_V2_TWO_CAS_ADMIT_V1 = "hswm-dnrd5-v2-two-cas-admit/v1" as const
export const DNRD5_V2_TWO_CAS_RESTORE_V1 = "hswm-dnrd5-v2-two-cas-restore/v1" as const

export interface Dnrd5V2TwoCasPhaseInput {
  readonly authority: Dnrd5V2AuthorityStateInput
  readonly consumption: Dnrd5V2ConsumptionInput
  readonly transition: CommitCanonicalAtomsV2ContentBound
  /** Exact raw payload bytes, one for every command write. */
  readonly writePayloads: ReadonlyArray<{ readonly atomKeyId: string; readonly bytes: Uint8Array }>
}

interface Dnrd5V2TwoCasInputBase {
  readonly main: Dnrd5V2TwoCasPhaseInput
  readonly receipt: Dnrd5V2TwoCasPhaseInput
}

export interface Dnrd5V2TwoCasAdmitInput extends Dnrd5V2TwoCasInputBase {
  readonly _tag: "Dnrd5V2TwoCasAdmitInput"
  readonly contractVersion: typeof DNRD5_V2_TWO_CAS_ADMIT_V1
}

export interface Dnrd5V2TwoCasRestoreInput extends Dnrd5V2TwoCasInputBase {
  readonly _tag: "Dnrd5V2TwoCasRestoreInput"
  readonly contractVersion: typeof DNRD5_V2_TWO_CAS_RESTORE_V1
}

export interface Dnrd5V2TwoCasAdmitConfirmed {
  readonly milestone: "CAS2_EXACT_R2_CONFIRMED"
  readonly mainRecord: CanonicalAtomV2ContentDescriptor
  readonly receiptRecord: CanonicalAtomV2ContentDescriptor
  readonly mainConsumptionAtomKeyId: string
  readonly receiptConsumptionAtomKeyId: string
  readonly terminal: "NOT_PROVIDER_CALL_NOT_OCCURRENCE_NOT_LEARNING_NOT_EFFICACY"
}

/** RESTORE has the same historical confirmation shape as ADMIT. */
export type Dnrd5V2TwoCasRestoreConfirmed = Dnrd5V2TwoCasAdmitConfirmed

interface Dnrd5V2TwoCasContract {
  readonly transitionKind: "ADMIT" | "RESTORE"
  readonly tag: Dnrd5V2TwoCasAdmitInput["_tag"] | Dnrd5V2TwoCasRestoreInput["_tag"]
  readonly version: typeof DNRD5_V2_TWO_CAS_ADMIT_V1 | typeof DNRD5_V2_TWO_CAS_RESTORE_V1
  readonly mainPhase: "MAIN_ADMIT" | "MAIN_RESTORE"
  readonly receiptPhase: "RECEIPT_ADMIT" | "RECEIPT_RESTORE"
  readonly receiptKind: Dnrd5V2ReceiptPayload["receiptKind"]
  readonly receiptAtomKind: "hswm:dnrd5:v2:revision_transition_receipt" | "hswm:dnrd5:v2:rollback_transition_receipt"
}

const ADMIT_TWO_CAS_CONTRACT: Dnrd5V2TwoCasContract = Object.freeze({
  transitionKind: "ADMIT", tag: "Dnrd5V2TwoCasAdmitInput", version: DNRD5_V2_TWO_CAS_ADMIT_V1,
  mainPhase: "MAIN_ADMIT", receiptPhase: "RECEIPT_ADMIT", receiptKind: "REVISION",
  receiptAtomKind: "hswm:dnrd5:v2:revision_transition_receipt"
})

const RESTORE_TWO_CAS_CONTRACT: Dnrd5V2TwoCasContract = Object.freeze({
  transitionKind: "RESTORE", tag: "Dnrd5V2TwoCasRestoreInput", version: DNRD5_V2_TWO_CAS_RESTORE_V1,
  mainPhase: "MAIN_RESTORE", receiptPhase: "RECEIPT_RESTORE", receiptKind: "ROLLBACK",
  receiptAtomKind: "hswm:dnrd5:v2:rollback_transition_receipt"
})

const v2Failure = (milestone: Exclude<Dnrd5V2TwoCasMilestone, "CAS2_EXACT_R2_CONFIRMED">, detail: string) =>
  new Dnrd5V2TwoCasRecoveryError({ milestone, detail })

const exactDataObject = (
  value: unknown,
  fields: ReadonlyArray<string>
): value is Record<string, unknown> => {
  if (
    typeof value !== "object" ||
    value === null ||
    Object.getPrototypeOf(value) !== Object.prototype
  ) return false
  const keys = Reflect.ownKeys(value)
  if (
    keys.length !== fields.length ||
    keys.some((key) => typeof key !== "string" || !fields.includes(key))
  ) return false
  const descriptors = Object.getOwnPropertyDescriptors(value)
  return fields.every((field) => {
    const descriptor = descriptors[field]
    return descriptor !== undefined && Object.prototype.hasOwnProperty.call(descriptor, "value")
  })
}

const cloneBytes = (value: Uint8Array): Uint8Array => Uint8Array.from(value)

const sameDescriptor = (left: CanonicalAtomV2ContentDescriptor, right: CanonicalAtomV2ContentDescriptor): boolean =>
  sameCanonicalAtomV2ContentDescriptor(left, right)

const sameCanonicalValue = (left: unknown, right: unknown): boolean => {
  const leftBytes = canonicalJsonBytes(left)
  const rightBytes = canonicalJsonBytes(right)
  return Either.isRight(leftBytes) && Either.isRight(rightBytes) &&
    exactBytes(leftBytes.right, rightBytes.right)
}

const decodeTwoCasPhase = (
  value: unknown,
  label: "main" | "receipt"
): Either.Either<Dnrd5V2TwoCasPhaseInput, Dnrd5V2TwoCasRecoveryError> => {
  if (
    !exactDataObject(value, ["authority", "consumption", "transition", "writePayloads"]) ||
    !exactDataObject(value["authority"], ["_tag", "contractVersion", "evaluatedAt", "principals", "state", "chain"]) ||
    !exactDataObject(value["consumption"], [
      "_tag",
      "payloadBytes",
      "commandIntentBytes",
      "commandProjectionBytes",
      "atom",
      "authorizationSnapshot",
      "state"
    ]) ||
    !(value["consumption"]["payloadBytes"] instanceof Uint8Array) ||
    !(value["consumption"]["commandIntentBytes"] instanceof Uint8Array) ||
    !(value["consumption"]["commandProjectionBytes"] instanceof Uint8Array) ||
    !Array.isArray(value["writePayloads"])
  ) {
    return Either.left(v2Failure(
      "RECOVERY_INDETERMINATE",
      `${label} phase is not the exact two-CAS input contract`
    ))
  }
  const transition = Schema.decodeUnknownEither(
    CommitCanonicalAtomsV2ContentBoundSchema,
    { onExcessProperty: "error" }
  )(value["transition"])
  if (Either.isLeft(transition)) {
    return Either.left(v2Failure(
      "RECOVERY_INDETERMINATE",
      `${label} transition is not the exact content-bound contract`
    ))
  }
  const writePayloads: Array<{ readonly atomKeyId: string; readonly bytes: Uint8Array }> = []
  for (const candidate of value["writePayloads"]) {
    if (
      !exactDataObject(candidate, ["atomKeyId", "bytes"]) ||
      typeof candidate["atomKeyId"] !== "string" ||
      !(candidate["bytes"] instanceof Uint8Array)
    ) {
      return Either.left(v2Failure(
        "RECOVERY_INDETERMINATE",
        `${label} write payload set is not an exact key/bytes array`
      ))
    }
    writePayloads.push(Object.freeze({
      atomKeyId: candidate["atomKeyId"],
      bytes: cloneBytes(candidate["bytes"])
    }))
  }
  try {
    return Either.right(Object.freeze({
      authority: snapshot(value["authority"]) as unknown as Dnrd5V2AuthorityStateInput,
      consumption: snapshot(value["consumption"]) as unknown as Dnrd5V2ConsumptionInput,
      transition: snapshot(transition.right),
      writePayloads: Object.freeze(writePayloads)
    }))
  } catch {
    return Either.left(v2Failure(
      "RECOVERY_INDETERMINATE",
      `${label} phase could not be defensively snapshotted`
    ))
  }
}

const decodeTwoCasInput = (
  input: unknown,
  contract: Dnrd5V2TwoCasContract
): Either.Either<Dnrd5V2TwoCasInputBase, Dnrd5V2TwoCasRecoveryError> => {
  try {
    if (
      !exactDataObject(input, ["_tag", "contractVersion", "main", "receipt"]) ||
      input["_tag"] !== contract.tag ||
      input["contractVersion"] !== contract.version
    ) {
      return Either.left(v2Failure(
        "RECOVERY_INDETERMINATE",
        `two-CAS ${contract.transitionKind} input must have the exact root contract`
      ))
    }
    const main = decodeTwoCasPhase(input["main"], "main")
    if (Either.isLeft(main)) return Either.left(main.left)
    const receipt = decodeTwoCasPhase(input["receipt"], "receipt")
    if (Either.isLeft(receipt)) return Either.left(receipt.left)
    return Either.right(Object.freeze({
      main: main.right,
      receipt: receipt.right
    }))
  } catch {
    return Either.left(v2Failure(
      "RECOVERY_INDETERMINATE",
      `two-CAS ${contract.transitionKind} input could not be safely inspected`
    ))
  }
}

const verifyAuthorityBytes = (
  runtime: CanonicalAtomV2DurableRuntime["Type"],
  authority: Dnrd5V2AuthorityStateInput
): Effect.Effect<void, CanonicalAtomV2DurableSubmitFailure | Dnrd5V2TwoCasRecoveryError> =>
  Effect.gen(function* () {
    const chain = authority.chain
    for (const content of [chain.policy, chain.authorization, chain.capability, chain.revocation, chain.grant]) {
      const durable = yield* runtime.readContent(content.atom.content)
      if (!exactBytes(durable, cloneBytes(content.bytes))) {
        return yield* v2Failure("RECOVERY_INDETERMINATE", "authority content bytes differ from their supplied exact durable descriptor")
      }
    }
  })

const decodeV2ConsumptionPayload = (
  bytes: Uint8Array
): Either.Either<Dnrd5V2ConsumptionPayload, Dnrd5V2TwoCasRecoveryError> => {
  const decoded = decodeCanonicalJsonBytes(bytes)
  if (Either.isLeft(decoded)) {
    return Either.left(v2Failure(
      "RECOVERY_INDETERMINATE",
      "consumption payload bytes are not canonical JSON"
    ))
  }
  const payload = Schema.decodeUnknownEither(
    Dnrd5V2ConsumptionPayloadSchema,
    { onExcessProperty: "error" }
  )(decoded.right)
  const canonical = Either.isRight(payload)
    ? canonicalJsonBytes(payload.right)
    : undefined
  return Either.isLeft(payload) || canonical === undefined || Either.isLeft(canonical) ||
    !exactBytes(bytes, canonical.right)
    ? Either.left(v2Failure(
        "RECOVERY_INDETERMINATE",
        "consumption payload is not the exact canonical v2 contract"
      ))
    : Either.right(payload.right)
}

const decodeV2IntentForPayload = (
  bytes: Uint8Array,
  payload: Dnrd5V2ConsumptionPayload
): Either.Either<Schema.Schema.Type<typeof Dnrd5V2ConsumptionCommandIntentSchema>, Dnrd5V2TwoCasRecoveryError> => {
  const decoded = decodeCanonicalJsonBytes(bytes)
  if (Either.isLeft(decoded)) {
    return Either.left(v2Failure(
      "RECOVERY_INDETERMINATE",
      "consumption command-intent bytes are not canonical JSON"
    ))
  }
  const intent = Schema.decodeUnknownEither(
    Dnrd5V2ConsumptionCommandIntentSchema,
    { onExcessProperty: "error" }
  )(decoded.right)
  if (Either.isLeft(intent)) {
    return Either.left(v2Failure(
      "RECOVERY_INDETERMINATE",
      "consumption command intent is not the exact v2 contract"
    ))
  }
  const canonical = canonicalJsonBytes(intent.right)
  const descriptor = makeCanonicalAtomV2ContentDescriptor(
    DNRD5_V2_CONSUMPTION_COMMAND_INTENT_MEDIA_TYPE,
    bytes
  )
  if (
    Either.isLeft(canonical) ||
    !exactBytes(bytes, canonical.right) ||
    Either.isLeft(descriptor) ||
    !sameDescriptor(descriptor.right, payload.commandIntent) ||
    intent.right.phase !== payload.phase ||
    intent.right.capabilityNonceSha256 !== payload.capabilityNonceSha256 ||
    intent.right.purposeAtomKeyId !== payload.purposeAtomKeyId ||
    !sameCanonicalValue(intent.right.authority, payload.authority) ||
    !sameCanonicalValue(intent.right.authorizationSnapshot, payload.authorizationSnapshot) ||
    intent.right.evaluatedAt !== payload.evaluatedAt
  ) {
    return Either.left(v2Failure(
      "RECOVERY_INDETERMINATE",
      "consumption command intent does not exactly bind its payload"
    ))
  }
  return Either.right(intent.right)
}

const stageV2ConsumptionSupport = (
  runtime: CanonicalAtomV2DurableRuntime["Type"],
  consumption: Dnrd5V2ConsumptionInput,
  payload: Dnrd5V2ConsumptionPayload
): Effect.Effect<void, CanonicalAtomV2DurableSubmitFailure | Dnrd5V2TwoCasRecoveryError> =>
  Effect.gen(function* () {
    const intent = decodeV2IntentForPayload(consumption.commandIntentBytes, payload)
    if (Either.isLeft(intent)) return yield* intent.left
    const staged = yield* runtime.stageContent(
      DNRD5_V2_CONSUMPTION_COMMAND_INTENT_MEDIA_TYPE,
      cloneBytes(consumption.commandIntentBytes)
    )
    if (!sameDescriptor(staged, payload.commandIntent)) {
      return yield* v2Failure(
        "RECOVERY_INDETERMINATE",
        "staged command-intent bytes differ from their payload descriptor"
      )
    }
  })

const decodeV2ProjectionCommand = (
  consumption: Dnrd5V2ConsumptionInput
): Either.Either<CommitCanonicalAtomsV2Command, Dnrd5V2TwoCasRecoveryError> => {
  const decoded = decodeCanonicalJsonBytes(consumption.commandProjectionBytes)
  if (Either.isLeft(decoded)) return Either.left(v2Failure("RECOVERY_INDETERMINATE", "consumption projection bytes are not canonical JSON"))
  const projection = Schema.decodeUnknownEither(Dnrd5V2ConsumptionCommandProjectionSchema, { onExcessProperty: "error" })(decoded.right)
  if (Either.isLeft(projection)) {
    return Either.left(v2Failure("RECOVERY_INDETERMINATE", "consumption projection is not the exact v2 command contract"))
  }
  const canonical = canonicalJsonBytes(projection.right)
  if (Either.isLeft(canonical) || !exactBytes(canonical.right, consumption.commandProjectionBytes)) {
    return Either.left(v2Failure("RECOVERY_INDETERMINATE", "consumption projection bytes are not exact canonical bytes"))
  }
  const companion = projection.right.command.writes[0]
  if (projection.right.command.writes.length !== 1 || companion === undefined) {
    return Either.left(v2Failure("RECOVERY_INDETERMINATE", "consumption projection must carry exactly one companion write"))
  }
  return Either.right(snapshot({
    ...projection.right.command,
    writes: [consumption.atom, companion]
  }))
}

const stageV2Transition = (
  runtime: CanonicalAtomV2DurableRuntime["Type"],
  phase: Dnrd5V2TwoCasPhaseInput,
  command: CommitCanonicalAtomsV2Command
): Effect.Effect<CommitCanonicalAtomsV2ContentBound, CanonicalAtomV2DurableSubmitFailure | Dnrd5V2TwoCasRecoveryError> =>
  Effect.gen(function* () {
    if (
      phase.transition.schemaContentSha256 !== runtime.schemaContent.content.sha256 ||
      !sameCanonicalValue(phase.transition.command, command)
    ) {
      return yield* v2Failure("RECOVERY_INDETERMINATE", "content-bound transition does not equal the reconstructed consumption command")
    }
    const payloads = phase.writePayloads
    if (payloads.length !== command.writes.length) {
      return yield* v2Failure("RECOVERY_INDETERMINATE", "write payload set must bijectively cover the two command writes")
    }
    const payloadById = new Map(payloads.map((payload) => [payload.atomKeyId, payload] as const))
    if (payloadById.size !== payloads.length) {
      return yield* v2Failure("RECOVERY_INDETERMINATE", "write payload mapping repeats an atom key")
    }
    const suppliedBindings = validateCanonicalAtomV2WriteContentBindings(
      command.writes,
      phase.transition.writeBindings
    )
    if (Either.isLeft(suppliedBindings)) {
      return yield* v2Failure("RECOVERY_INDETERMINATE", "supplied write bindings are not the exact command bijection")
    }
    const atomById = new Map(
      command.writes.map((atom) => [canonicalAtomV2KeyId(atom.key), atom] as const)
    )
    const bindings: Array<CommitCanonicalAtomsV2ContentBound["writeBindings"][number]> = []
    for (const binding of suppliedBindings.right) {
      const id = canonicalAtomV2KeyId(binding.key)
      const atom = atomById.get(id)
      const payload = payloadById.get(id)
      if (atom === undefined || payload === undefined) {
        return yield* v2Failure("RECOVERY_INDETERMINATE", "write payloads are not an exact one-to-one atom-key mapping")
      }
      const staged = yield* runtime.stageContent(atom.content.mediaType, cloneBytes(payload.bytes))
      if (!sameDescriptor(staged, atom.content)) {
        return yield* v2Failure("RECOVERY_INDETERMINATE", "staged payload descriptor does not equal command atom content")
      }
      const envelope = describeCanonicalAtomV2Envelope(atom)
      if (
        Either.isLeft(envelope) ||
        !sameDescriptor(binding.payload, staged) ||
        !sameDescriptor(binding.envelope, envelope.right)
      ) {
        return yield* v2Failure("RECOVERY_INDETERMINATE", "supplied transition bindings differ from freshly derived content bindings")
      }
      bindings.push(Object.freeze({
        key: snapshot(binding.key),
        payload: snapshot(staged),
        envelope: snapshot(envelope.right)
      }))
    }
    const consumptionPayload = payloadById.get(canonicalAtomV2KeyId(phase.consumption.atom.key))
    if (
      consumptionPayload === undefined ||
      !exactBytes(consumptionPayload.bytes, phase.consumption.payloadBytes)
    ) {
      return yield* v2Failure("RECOVERY_INDETERMINATE", "consumption write bytes differ from the validated candidate bytes")
    }
    return makeCanonicalAtomV2ContentBoundInput(
      runtime.schemaContent.content.sha256,
      command,
      bindings
    )
  })

/** Pure counterpart of staging: used by resume before it can classify R1/R2. */
const validateV2TransitionCandidate = (
  schemaContentSha256: string,
  phase: Dnrd5V2TwoCasPhaseInput,
  command: CommitCanonicalAtomsV2Command
): Either.Either<void, Dnrd5V2TwoCasRecoveryError> => {
  if (
    phase.transition.schemaContentSha256 !== schemaContentSha256 ||
    !sameCanonicalValue(phase.transition.command, command) ||
    phase.writePayloads.length !== command.writes.length
  ) return Either.left(v2Failure("RECOVERY_INDETERMINATE", "resume transition does not exactly bind its reconstructed command"))
  const payloadById = new Map(phase.writePayloads.map((payload) => [payload.atomKeyId, payload] as const))
  if (payloadById.size !== phase.writePayloads.length) {
    return Either.left(v2Failure("RECOVERY_INDETERMINATE", "resume write payload mapping repeats an atom key"))
  }
  const bindings = validateCanonicalAtomV2WriteContentBindings(command.writes, phase.transition.writeBindings)
  if (Either.isLeft(bindings)) return Either.left(v2Failure("RECOVERY_INDETERMINATE", "resume write bindings are not the exact command bijection"))
  for (const binding of bindings.right) {
    const id = canonicalAtomV2KeyId(binding.key)
    const atom = command.writes.find((candidate) => canonicalAtomV2KeyId(candidate.key) === id)
    const payload = payloadById.get(id)
    if (atom === undefined || payload === undefined) {
      return Either.left(v2Failure("RECOVERY_INDETERMINATE", "resume write payloads do not bijectively cover command writes"))
    }
    const descriptor = makeCanonicalAtomV2ContentDescriptor(atom.content.mediaType, payload.bytes)
    const envelope = describeCanonicalAtomV2Envelope(atom)
    if (
      Either.isLeft(descriptor) || Either.isLeft(envelope) ||
      !sameDescriptor(descriptor.right, atom.content) ||
      !sameDescriptor(binding.payload, descriptor.right) ||
      !sameDescriptor(binding.envelope, envelope.right)
    ) return Either.left(v2Failure("RECOVERY_INDETERMINATE", "resume write bytes or descriptors do not exactly bind the command"))
  }
  const consumptionPayload = payloadById.get(canonicalAtomV2KeyId(phase.consumption.atom.key))
  return consumptionPayload === undefined || !exactBytes(consumptionPayload.bytes, phase.consumption.payloadBytes)
    ? Either.left(v2Failure("RECOVERY_INDETERMINATE", "resume consumption payload bytes differ from the candidate"))
    : Either.right(undefined)
}

interface Dnrd5V2RawCommitEvidence {
  readonly commit: CanonicalAtomV2StateJournalCommit
  readonly bytes: Uint8Array
  readonly descriptor: CanonicalAtomV2StateJournalRecordDescriptor
}

const rawCommitAt = (
  witness: CanonicalAtomV2DurableRecoveryWitness,
  revision: number
): Either.Either<Dnrd5V2RawCommitEvidence, Dnrd5V2TwoCasRecoveryError> => {
  const entry = witness.journal.at(revision)
  if (entry === undefined) return Either.left(v2Failure("RECOVERY_INDETERMINATE", "expected raw journal record is absent"))
  const decoded = decodeCanonicalAtomV2StateJournalRecordBytes(entry.bytes)
  if (
    Either.isLeft(decoded) ||
    decoded.right._tag !== "CanonicalAtomV2StateJournalCommit" ||
    decoded.right.stateRevision !== revision
  ) {
    return Either.left(v2Failure("RECOVERY_INDETERMINATE", "raw journal record is not the exact expected commit"))
  }
  const canonical = canonicalAtomV2StateJournalRecordBytes(decoded.right)
  const descriptor = describeCanonicalAtomV2StateJournalRecord(decoded.right)
  if (
    Either.isLeft(canonical) ||
    Either.isLeft(descriptor) ||
    !exactBytes(canonical.right, entry.bytes) ||
    !sameDescriptor(descriptor.right, entry.descriptor)
  ) {
    return Either.left(v2Failure("RECOVERY_INDETERMINATE", "raw journal bytes and descriptor are not canonical"))
  }
  return Either.right(Object.freeze({
    commit: decoded.right,
    bytes: cloneBytes(entry.bytes),
    descriptor: descriptor.right
  }))
}

const recoveredEnvelopesFor = (
  runtime: CanonicalAtomV2DurableRuntime["Type"],
  record: CanonicalAtomV2StateJournalCommit
): Effect.Effect<ReadonlyArray<Uint8Array>, CanonicalAtomV2DurableSubmitFailure | Dnrd5V2TwoCasRecoveryError> =>
  Effect.forEach(record.writeBindings, (binding) =>
    runtime.readContent(binding.envelope).pipe(Effect.flatMap((bytes) => {
      const described = makeCanonicalAtomV2ContentDescriptor(binding.envelope.mediaType, bytes)
      return Either.isRight(described) && sameDescriptor(described.right, binding.envelope)
        ? Effect.succeed(cloneBytes(bytes))
        : Effect.fail(v2Failure("RECOVERY_INDETERMINATE", "recovered raw envelope bytes do not equal the journal binding descriptor"))
    }
    )), { concurrency: 1 })

const consumptionMatchesAuthority = (
  consumption: { readonly phase: string; readonly purposeAtomKeyId: string; readonly capabilityNonceSha256: string; readonly evaluatedAt: string; readonly authority: { readonly grantAtomKeyId: string; readonly capabilityAtomKeyId: string; readonly revocationAtomKeyId: string } },
  authority: { readonly chain: { readonly phase: string; readonly purposeAtomKeyId: string; readonly nonceSha256: string; readonly grantAtomKeyId: string; readonly capabilityAtomKeyId: string; readonly revocationAtomKeyId: string }; readonly evaluatedAt: string }
): boolean => consumption.phase === authority.chain.phase && consumption.purposeAtomKeyId === authority.chain.purposeAtomKeyId && consumption.capabilityNonceSha256 === authority.chain.nonceSha256 && consumption.evaluatedAt === authority.evaluatedAt && consumption.authority.grantAtomKeyId === authority.chain.grantAtomKeyId && consumption.authority.capabilityAtomKeyId === authority.chain.capabilityAtomKeyId && consumption.authority.revocationAtomKeyId === authority.chain.revocationAtomKeyId

const commandMatchesAuthority = (
  command: CommitCanonicalAtomsV2Command,
  authority: {
    readonly evaluatedAt: string
    readonly chain: {
      readonly actor: string
      readonly scope: string
      readonly capabilityId: string
    }
  }
): boolean =>
  command.actorClaim === authority.chain.actor &&
  command.authorizationRef === authority.chain.capabilityId &&
  command.scope === authority.chain.scope &&
  command.decidedAt === authority.evaluatedAt

interface RecoveredV2Consumption {
  readonly atom: CanonicalAtomV2
  readonly atomKeyId: string
  readonly phase: Dnrd5V2ConsumptionPayload["phase"]
  readonly nonceSha256: string
}

const consumptionPhaseBinding = (phase: Dnrd5V2ConsumptionPayload["phase"]) =>
  phase === "MAIN_ADMIT"
    ? Object.freeze({
        kind: "hswm:dnrd5:v2:capability_consumption",
        owner: "owner:dnrd5:v2:capability_consumption_custodian",
        mediaType: DNRD5_V2_CAPABILITY_CONSUMPTION_MEDIA_TYPE,
        purposeRole: "role:dnrd5:v2:decision",
        purposeKind: "hswm:dnrd5:v2:revision_admission_decision"
      })
    : phase === "MAIN_RESTORE"
      ? Object.freeze({
          kind: "hswm:dnrd5:v2:capability_consumption",
          owner: "owner:dnrd5:v2:capability_consumption_custodian",
          mediaType: DNRD5_V2_CAPABILITY_CONSUMPTION_MEDIA_TYPE,
          purposeRole: "role:dnrd5:v2:decision",
          purposeKind: "hswm:dnrd5:v2:rollback_decision"
        })
      : phase === "RECEIPT_ADMIT"
        ? Object.freeze({
            kind: "hswm:dnrd5:v2:evidence_seal_consumption",
            owner: "owner:dnrd5:v2:evidence_seal_consumption_custodian",
            mediaType: DNRD5_V2_EVIDENCE_SEAL_CONSUMPTION_MEDIA_TYPE,
            purposeRole: "role:dnrd5:v2:purpose",
            purposeKind: "hswm:dnrd5:v2:revision_admission_decision"
          })
        : Object.freeze({
            kind: "hswm:dnrd5:v2:evidence_seal_consumption",
            owner: "owner:dnrd5:v2:evidence_seal_consumption_custodian",
            mediaType: DNRD5_V2_EVIDENCE_SEAL_CONSUMPTION_MEDIA_TYPE,
            purposeRole: "role:dnrd5:v2:purpose",
            purposeKind: "hswm:dnrd5:v2:rollback_decision"
          })

const recoveredV2Consumptions = (
  runtime: CanonicalAtomV2DurableRuntime["Type"],
  atoms: ReadonlyArray<CanonicalAtomV2>
): Effect.Effect<ReadonlyMap<string, RecoveredV2Consumption>, CanonicalAtomV2DurableSubmitFailure | Dnrd5V2TwoCasRecoveryError> =>
  Effect.gen(function* () {
    const byNonce = new Map<string, RecoveredV2Consumption>()
    const members = new Map(
      atoms.map((atom) => [canonicalAtomV2KeyId(atom.key), atom] as const)
    )
    for (const atom of atoms) {
      if (atom.kind !== "hswm:dnrd5:v2:capability_consumption" && atom.kind !== "hswm:dnrd5:v2:evidence_seal_consumption") continue
      const bytes = yield* runtime.readContent(atom.content)
      const described = makeCanonicalAtomV2ContentDescriptor(atom.content.mediaType, bytes)
      if (Either.isLeft(described) || !sameDescriptor(described.right, atom.content)) {
        return yield* v2Failure("RECOVERY_INDETERMINATE", "a recovered v2 consumption descriptor does not bind its durable bytes")
      }
      const payload = decodeV2ConsumptionPayload(bytes)
      if (Either.isLeft(payload)) return yield* payload.left
      const binding = consumptionPhaseBinding(payload.right.phase)
      const intentBytes = yield* runtime.readContent(payload.right.commandIntent)
      const intent = decodeV2IntentForPayload(intentBytes, payload.right)
      if (Either.isLeft(intent)) return yield* intent.left
      const uid = dnrd5V2ConsumptionAtomUid(
        payload.right.phase,
        payload.right.capabilityNonceSha256,
        payload.right.purposeAtomKeyId
      )
      if (
        Either.isLeft(uid) ||
        atom.key.schemaVersion !== DNRD5_V2_SCHEMA_VERSION ||
        atom.key.revisionId !== 0 ||
        atom.key.atomUid !== uid.right ||
        atom.kind !== binding.kind ||
        atom.responsibilityOwner !== binding.owner ||
        atom.lifecycle !== "ADMITTED" ||
        atom.content.mediaType !== binding.mediaType ||
        atom.provenance.mode !== "DERIVATION" ||
        atom.provenance.sourceRef === null ||
        canonicalAtomV2KeyId(atom.provenance.sourceRef) !== payload.right.purposeAtomKeyId ||
        atom.provenance.evidenceSha256 !== intent.right.commandProjectionSha256
      ) {
        return yield* v2Failure("RECOVERY_INDETERMINATE", "a recovered v2 consumption atom is inconsistent with its durable payload")
      }
      if (
        members.get(payload.right.authority.grantAtomKeyId)?.kind !== "hswm:dnrd5:v2:grant_snapshot" ||
        members.get(payload.right.authority.capabilityAtomKeyId)?.kind !== "hswm:dnrd5:v2:capability_issuance" ||
        members.get(payload.right.authority.revocationAtomKeyId)?.kind !== "hswm:dnrd5:v2:revocation_status" ||
        members.get(payload.right.purposeAtomKeyId)?.kind !== binding.purposeKind
      ) {
        return yield* v2Failure("RECOVERY_INDETERMINATE", "a recovered v2 consumption references absent or wrong-kind state members")
      }
      const expectedReferences = new Map<string, string>([
        ["role:dnrd5:v2:grant", payload.right.authority.grantAtomKeyId],
        ["role:dnrd5:v2:capability", payload.right.authority.capabilityAtomKeyId],
        ["role:dnrd5:v2:revocation", payload.right.authority.revocationAtomKeyId],
        [binding.purposeRole, payload.right.purposeAtomKeyId]
      ])
      if (
        atom.references.length !== expectedReferences.size ||
        new Set(atom.references.map((reference) => reference.role)).size !== atom.references.length ||
        atom.references.some((reference) =>
          reference.referenceType !== DNRD5_V2_REFERENCE_TYPE ||
          expectedReferences.get(reference.role) !== canonicalAtomV2KeyId(reference.target)
        )
      ) {
        return yield* v2Failure("RECOVERY_INDETERMINATE", "a recovered v2 consumption has invalid typed-reference closure")
      }
      if (byNonce.has(payload.right.capabilityNonceSha256)) {
        return yield* v2Failure("RECOVERY_INDETERMINATE", "a recovered v2 history contains a cross-phase or duplicate capability nonce")
      }
      byNonce.set(payload.right.capabilityNonceSha256, Object.freeze({
        atom,
        atomKeyId: canonicalAtomV2KeyId(atom.key),
        phase: payload.right.phase,
        nonceSha256: payload.right.capabilityNonceSha256
      }))
    }
    return byNonce
  })

const exactRecoveredTail = (
  witness: CanonicalAtomV2DurableRecoveryWitness,
  revision: number,
  milestone: "CAS1_PREDECESSOR_LOST" | "CAS2_PREDECESSOR_LOST"
): Either.Either<Dnrd5V2RawCommitEvidence, Dnrd5V2TwoCasRecoveryError> => {
  if (
    witness.state.canonical.revision !== revision ||
    witness.journal.length !== revision + 1 ||
    witness.history.length !== revision
  ) {
    return Either.left(v2Failure(milestone, "recovered durable journal is not the exact expected successor length"))
  }
  const raw = rawCommitAt(witness, revision)
  if (Either.isLeft(raw)) return Either.left(raw.left)
  const tail = witness.history.at(-1)
  if (
    tail === undefined ||
    !sameDescriptor(tail.record, raw.right.descriptor) ||
    !sameDescriptor(witness.state.journalHead, raw.right.descriptor)
  ) {
    return Either.left(v2Failure(milestone, "recovered raw record is not the exact semantic and durable tail"))
  }
  return raw
}

const prevalidateTwoCasReceipt = (
  contract: Dnrd5V2TwoCasContract,
  phase: Dnrd5V2TwoCasPhaseInput,
  command: CommitCanonicalAtomsV2Command,
  effect: {
    readonly effectRecordDescriptor: CanonicalAtomV2StateJournalRecordDescriptor
    readonly deterministicFuturePostcommitReceiptIdentity: string
  },
  mainConsumption: Dnrd5V2ConsumptionValidated
): Either.Either<{
  readonly bytes: Uint8Array
  readonly descriptor: CanonicalAtomV2ContentDescriptor
}, Dnrd5V2TwoCasRecoveryError> => {
  const receipts = command.writes.filter(
    (atom) => atom.kind === contract.receiptAtomKind
  )
  if (receipts.length !== 1) {
    return Either.left(v2Failure("CAS1_EXACT_R1_RECEIPT_PENDING", `receipt command lacks exactly one ${contract.receiptKind} receipt atom`))
  }
  const receipt = receipts[0]!
  const payloads = phase.writePayloads.filter(
    (candidate) => candidate.atomKeyId === canonicalAtomV2KeyId(receipt.key)
  )
  if (payloads.length !== 1) {
    return Either.left(v2Failure("CAS1_EXACT_R1_RECEIPT_PENDING", "receipt command lacks exactly one raw receipt payload"))
  }
  const expected: Dnrd5V2ReceiptPayload = {
    contractVersion: DNRD5_V2_RECEIPT_SEAL_V1,
    receiptKind: contract.receiptKind,
    precedingEffectRecordDescriptorSha256: effect.effectRecordDescriptor.sha256,
    postcommitReceiptIdentity: effect.deterministicFuturePostcommitReceiptIdentity,
    decisionAtomKeyId: mainConsumption.purposeAtomKeyId,
    effectConsumptionAtomKeyId: mainConsumption.atomKeyId,
    effectAtomKeyId: mainConsumption.companionAtomKeyId
  }
  const expectedBytes = canonicalDnrd5V2ReceiptPayloadBytes(expected)
  if (Either.isLeft(expectedBytes) || !exactBytes(expectedBytes.right, payloads[0]!.bytes)) {
    return Either.left(v2Failure("CAS1_EXACT_R1_RECEIPT_PENDING", "receipt payload does not exactly bind the recovered R1 effect"))
  }
  const descriptor = makeCanonicalAtomV2ContentDescriptor(
    DNRD5_V2_RECEIPT_PAYLOAD_MEDIA_TYPE,
    expectedBytes.right
  )
  if (
    Either.isLeft(descriptor) ||
    receipt.key.atomUid !== `receipt:${effect.deterministicFuturePostcommitReceiptIdentity}` ||
    !sameDescriptor(receipt.content, descriptor.right)
  ) {
    return Either.left(v2Failure("CAS1_EXACT_R1_RECEIPT_PENDING", "receipt UID or content descriptor does not bind the recovered R1 identity"))
  }
  return Either.right(Object.freeze({
    bytes: cloneBytes(expectedBytes.right),
    descriptor: descriptor.right
  }))
}

/**
 * Replays a bounded raw prefix from one recovery witness.  Resume must never
 * trust a caller's S0 object: its state and head are established only here.
 */
const replayRecoveredPrefixAt = (
  runtime: CanonicalAtomV2DurableRuntime["Type"],
  witness: CanonicalAtomV2DurableRecoveryWitness,
  revision: number
): Effect.Effect<{
  readonly state: CanonicalAtomV2DurableEvolution["state"]["canonical"]
  readonly head: CanonicalAtomV2StateJournalRecordDescriptor
}, CanonicalAtomV2DurableSubmitFailure | Dnrd5V2TwoCasRecoveryError> =>
  Effect.gen(function* () {
    if (!Number.isSafeInteger(revision) || revision < 0 || witness.journal.length < revision + 1) {
      return yield* v2Failure("RECOVERY_INDETERMINATE", "requested raw prefix is outside the one recovered journal witness")
    }
    const genesisEntry = witness.journal[0]
    if (genesisEntry === undefined) {
      return yield* v2Failure("RECOVERY_INDETERMINATE", "recovered journal has no genesis for prefix replay")
    }
    const genesis = decodeCanonicalAtomV2StateJournalRecordBytes(genesisEntry.bytes)
    if (Either.isLeft(genesis) || genesis.right._tag !== "CanonicalAtomV2StateJournalGenesis") {
      return yield* v2Failure("RECOVERY_INDETERMINATE", "raw genesis is not a canonical descriptor-bound journal record")
    }
    const genesisDescriptor = describeCanonicalAtomV2StateJournalRecord(genesis.right)
    const genesisBytes = canonicalAtomV2StateJournalRecordBytes(genesis.right)
    if (Either.isLeft(genesisDescriptor) || Either.isLeft(genesisBytes) || !sameDescriptor(genesisDescriptor.right, genesisEntry.descriptor) || !exactBytes(genesisBytes.right, genesisEntry.bytes)) {
      return yield* v2Failure("RECOVERY_INDETERMINATE", "raw genesis is not a canonical descriptor-bound journal record")
    }
    const initial = applyCanonicalAtomV2StateJournalGenesis(runtime.schema, genesis.right)
    if (Either.isLeft(initial)) return yield* v2Failure("RECOVERY_INDETERMINATE", "raw genesis cannot establish the active canonical state")
    let state = initial.right
    let head = genesisDescriptor.right
    for (let index = 1; index <= revision; index += 1) {
      const raw = rawCommitAt(witness, index)
      if (Either.isLeft(raw)) return yield* raw.left
      const envelopes = yield* recoveredEnvelopesFor(runtime, raw.right.commit)
      const applied = applyCanonicalAtomV2StateJournalCommit(
        runtime.schema,
        { state, descriptor: head, journalLineageId: witness.state.journalLineageId, schema: runtime.schemaContent },
        raw.right.commit,
        envelopes
      )
      if (Either.isLeft(applied) || !sameDescriptor(applied.right.descriptor, raw.right.descriptor)) {
        return yield* v2Failure("RECOVERY_INDETERMINATE", "raw prefix commit cannot be replayed to its exact descriptor")
      }
      state = applied.right.state
      head = applied.right.descriptor
    }
    return Object.freeze({ state, head })
  })

const submitDnrd5V2TwoCas = (
  input: unknown,
  contract: Dnrd5V2TwoCasContract
): Effect.Effect<
  Dnrd5V2TwoCasAdmitConfirmed,
  CanonicalAtomV2DurableSubmitFailure | Dnrd5V2TwoCasRecoveryError,
  CanonicalAtomV2DurableRuntime
> => Effect.gen(function* () {
  const decoded = decodeTwoCasInput(input, contract)
  if (Either.isLeft(decoded)) return yield* decoded.left
  const supplied = decoded.right
  const mainPayload = decodeV2ConsumptionPayload(supplied.main.consumption.payloadBytes)
  const receiptPayload = decodeV2ConsumptionPayload(supplied.receipt.consumption.payloadBytes)
  if (Either.isLeft(mainPayload)) return yield* mainPayload.left
  if (Either.isLeft(receiptPayload)) return yield* receiptPayload.left
  if (
    mainPayload.right.phase !== contract.mainPhase ||
    receiptPayload.right.phase !== contract.receiptPhase ||
    mainPayload.right.capabilityNonceSha256 === receiptPayload.right.capabilityNonceSha256
  ) {
    return yield* v2Failure(
      "RECOVERY_INDETERMINATE",
      `${contract.transitionKind} requires distinct ${contract.mainPhase} and ${contract.receiptPhase} consumption candidates`
    )
  }
  const mainIntent = decodeV2IntentForPayload(
    supplied.main.consumption.commandIntentBytes,
    mainPayload.right
  )
  const receiptIntent = decodeV2IntentForPayload(
    supplied.receipt.consumption.commandIntentBytes,
    receiptPayload.right
  )
  if (Either.isLeft(mainIntent)) return yield* mainIntent.left
  if (Either.isLeft(receiptIntent)) return yield* receiptIntent.left

  const runtime = yield* CanonicalAtomV2DurableRuntime
  if (Either.isLeft(validateDnrd5V2CanonicalSchema(runtime.schema))) {
    return yield* v2Failure(
      "RECOVERY_INDETERMINATE",
      "runtime does not carry the exact DNRD-5 v2 schema"
    )
  }

  // Initial-only entry: one raw recovery observation defines S0. A stale or
  // retried candidate is rejected before CAS1; crash-resume is a later,
  // prefix-identity-bound contract.
  const s0 = yield* recoverCanonicalAtomV2DurableFromDnrd5DispatcherInternal(runtime)
  const pre = s0.state
  const s0Sha = canonicalAtomV2StateSha256(pre.canonical)
  if (Either.isLeft(s0Sha)) {
    return yield* v2Failure("RECOVERY_INDETERMINATE", "cannot hash recovered S0")
  }
  const recoveredS0Snapshot = Object.freeze({
    stateRevision: pre.canonical.revision,
    stateSha256: s0Sha.right,
    journalLineageId: pre.journalLineageId,
    journalHead: pre.journalHead
  })
  if (
    !sameCanonicalValue(
      supplied.main.consumption.authorizationSnapshot,
      recoveredS0Snapshot
    ) ||
    !sameCanonicalValue(supplied.main.consumption.state, pre.canonical) ||
    !sameCanonicalValue(supplied.main.authority.state, pre.canonical)
  ) {
    return yield* v2Failure(
      "CAS1_PREDECESSOR_LOST",
      `initial-only ${contract.transitionKind} submission requires supplied main state and snapshot to equal recovered S0`
    )
  }

  const mainAuthority = validateDnrd5V2AuthorityPayloadAtState({
    ...supplied.main.authority,
    state: pre.canonical
  })
  if (
    Either.isLeft(mainAuthority) ||
    mainAuthority.right.chain.phase !== contract.mainPhase
  ) {
    return yield* v2Failure(
      "RECOVERY_INDETERMINATE",
      `recovered S0 does not validate the exact ${contract.mainPhase} authority`
    )
  }
  yield* verifyAuthorityBytes(runtime, supplied.main.authority)

  const s0Consumptions = yield* recoveredV2Consumptions(
    runtime,
    pre.canonical.atoms
  )
  if (
    s0Consumptions.has(mainPayload.right.capabilityNonceSha256) ||
    s0Consumptions.has(receiptPayload.right.capabilityNonceSha256) ||
    pre.canonical.atoms.some((atom) =>
      canonicalAtomV2KeyId(atom.key) ===
        canonicalAtomV2KeyId(supplied.main.consumption.atom.key) ||
      canonicalAtomV2KeyId(atom.key) ===
        canonicalAtomV2KeyId(supplied.receipt.consumption.atom.key)
    )
  ) {
    return yield* v2Failure(
      "CAS1_PREDECESSOR_LOST",
      "a candidate nonce or consumption identity already exists in recovered S0"
    )
  }

  const mainConsumption = validateDnrd5V2Consumption({
    ...supplied.main.consumption,
    state: pre.canonical,
    authorizationSnapshot: recoveredS0Snapshot
  })
  if (Either.isLeft(mainConsumption)) {
    return yield* v2Failure(
      "RECOVERY_INDETERMINATE",
      "main consumption candidate is invalid: " + mainConsumption.left.code
    )
  }
  if (!consumptionMatchesAuthority(mainConsumption.right, mainAuthority.right)) {
    return yield* v2Failure(
      "RECOVERY_INDETERMINATE",
      "main consumption does not bind the recovered main authority chain"
    )
  }
  const mainCommand = decodeV2ProjectionCommand(supplied.main.consumption)
  if (Either.isLeft(mainCommand)) return yield* mainCommand.left
  if (!commandMatchesAuthority(mainCommand.right, mainAuthority.right)) {
    return yield* v2Failure(
      "RECOVERY_INDETERMINATE",
      "main command header does not bind the validated actor, capability, scope, and time"
    )
  }
  const mainPreflight = validateDnrd5V2EffectCommandCandidate(
    runtime.schema,
    pre.canonical,
    mainCommand.right
  )
  if (Either.isLeft(mainPreflight)) {
    return yield* v2Failure(
      "RECOVERY_INDETERMINATE",
      "main effect failed pre-CAS DNRD grammar: " + mainPreflight.left.code
    )
  }
  yield* stageV2ConsumptionSupport(
    runtime,
    supplied.main.consumption,
    mainPayload.right
  )
  const mainTransition = yield* stageV2Transition(
    runtime,
    supplied.main,
    mainCommand.right
  )

  const expectedR1 = pre.canonical.revision + 1
  const mainAttempt = yield* Effect.either(
    commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal(
      runtime,
      mainTransition
    )
  )
  const r1Witness =
    yield* recoverCanonicalAtomV2DurableFromDnrd5DispatcherInternal(runtime)
  if (r1Witness.state.canonical.revision === pre.canonical.revision) {
    if (Either.isLeft(mainAttempt)) return yield* Effect.fail(mainAttempt.left)
    return yield* v2Failure(
      "RECOVERY_INDETERMINATE",
      "CAS1 returned without an exact recovered durable successor"
    )
  }
  if (r1Witness.state.canonical.revision !== expectedR1) {
    return yield* v2Failure(
      "CAS1_PREDECESSOR_LOST",
      "recovered durable tail advanced outside the exact S0 to R1 window"
    )
  }
  const r1 = exactRecoveredTail(
    r1Witness,
    expectedR1,
    "CAS1_PREDECESSOR_LOST"
  )
  if (Either.isLeft(r1)) return yield* r1.left
  const mainRawEnvelopes = yield* recoveredEnvelopesFor(
    runtime,
    r1.right.commit
  )
  const mainEffectInput = Object.freeze({
    schema: runtime.schema,
    preState: pre.canonical,
    predecessor: Object.freeze({
      descriptor: pre.journalHead,
      journalLineageId: pre.journalLineageId,
      schemaContentSha256: pre.schema.content.sha256
    }),
    command: mainCommand.right,
    record: r1.right.commit,
    recordBytes: r1.right.bytes,
    recordDescriptor: r1.right.descriptor,
    envelopes: mainRawEnvelopes,
    usedRecordDescriptorSha256s: s0.history.map(
      (entry) => entry.record.sha256
    )
  })
  const mainEffect = validateDnrd5V2RecordBoundEffect(mainEffectInput)
  if (Either.isLeft(mainEffect)) {
    return yield* v2Failure(
      "CAS1_PREDECESSOR_LOST",
      "R1 is not the exact reconstructed main effect: " + mainEffect.left.code
    )
  }
  if (!sameCanonicalValue(
    mainEffect.right.nextState,
    r1Witness.state.canonical
  )) {
    return yield* v2Failure(
      "CAS1_PREDECESSOR_LOST",
      "raw R1 replay state differs from the recovered R1 state"
    )
  }

  const r1Consumptions = yield* recoveredV2Consumptions(
    runtime,
    r1Witness.state.canonical.atoms
  )
  const recoveredMainConsumption = r1Consumptions.get(
    mainConsumption.right.capabilityNonceSha256
  )
  if (
    recoveredMainConsumption === undefined ||
    recoveredMainConsumption.phase !== contract.mainPhase ||
    recoveredMainConsumption.atomKeyId !== mainConsumption.right.atomKeyId ||
    !sameCanonicalValue(
      recoveredMainConsumption.atom,
      supplied.main.consumption.atom
    ) ||
    r1Consumptions.has(receiptPayload.right.capabilityNonceSha256)
  ) {
    return yield* v2Failure(
      "CAS1_PREDECESSOR_LOST",
      "R1 lacks the exact main consumption or already contains the receipt nonce"
    )
  }

  const r1Sha = canonicalAtomV2StateSha256(mainEffect.right.nextState)
  if (Either.isLeft(r1Sha)) {
    return yield* v2Failure(
      "CAS1_EXACT_R1_RECEIPT_PENDING",
      "cannot hash exact recovered R1 for receipt sealing"
    )
  }
  const recoveredR1Snapshot = Object.freeze({
    stateRevision: mainEffect.right.nextState.revision,
    stateSha256: r1Sha.right,
    journalLineageId: r1Witness.state.journalLineageId,
    journalHead: r1.right.descriptor
  })
  if (
    !sameCanonicalValue(
      supplied.receipt.consumption.authorizationSnapshot,
      recoveredR1Snapshot
    ) ||
    !sameCanonicalValue(
      supplied.receipt.consumption.state,
      mainEffect.right.nextState
    ) ||
    !sameCanonicalValue(
      supplied.receipt.authority.state,
      mainEffect.right.nextState
    )
  ) {
    return yield* v2Failure(
      "CAS1_EXACT_R1_RECEIPT_PENDING",
      "receipt state and snapshot do not equal the raw-replayed R1"
    )
  }

  const receiptAuthority = validateDnrd5V2AuthorityPayloadAtState({
    ...supplied.receipt.authority,
    state: mainEffect.right.nextState
  })
  const authorityPair = validateDnrd5V2AuthorityDisjointPair(
    { ...supplied.main.authority, state: pre.canonical },
    { ...supplied.receipt.authority, state: mainEffect.right.nextState }
  )
  if (
    Either.isLeft(receiptAuthority) ||
    receiptAuthority.right.chain.phase !== contract.receiptPhase ||
    Either.isLeft(authorityPair)
  ) {
    return yield* v2Failure(
      "CAS1_EXACT_R1_RECEIPT_PENDING",
      "R1 does not validate distinct main and evidence authority chains"
    )
  }
  yield* verifyAuthorityBytes(runtime, supplied.receipt.authority)

  const receiptConsumption = validateDnrd5V2Consumption({
    ...supplied.receipt.consumption,
    state: mainEffect.right.nextState,
    authorizationSnapshot: recoveredR1Snapshot
  })
  if (Either.isLeft(receiptConsumption)) {
    return yield* v2Failure(
      "CAS1_EXACT_R1_RECEIPT_PENDING",
      "receipt consumption candidate is invalid: " +
        receiptConsumption.left.code
    )
  }
  if (!consumptionMatchesAuthority(
    receiptConsumption.right,
    receiptAuthority.right
  )) {
    return yield* v2Failure(
      "CAS1_EXACT_R1_RECEIPT_PENDING",
      "receipt consumption does not bind the recovered evidence authority chain"
    )
  }
  const receiptCommand = decodeV2ProjectionCommand(
    supplied.receipt.consumption
  )
  if (Either.isLeft(receiptCommand)) {
    return yield* v2Failure(
      "CAS1_EXACT_R1_RECEIPT_PENDING",
      receiptCommand.left.detail
    )
  }
  if (!commandMatchesAuthority(receiptCommand.right, receiptAuthority.right)) {
    return yield* v2Failure(
      "CAS1_EXACT_R1_RECEIPT_PENDING",
      "receipt command header does not bind the validated actor, capability, scope, and time"
    )
  }

  // This check uses the actual raw R1 descriptor and happens before CAS2.
  const exactReceipt = prevalidateTwoCasReceipt(
    contract,
    supplied.receipt,
    receiptCommand.right,
    mainEffect.right,
    mainConsumption.right
  )
  if (Either.isLeft(exactReceipt)) return yield* exactReceipt.left
  const receiptPreflight = validateDnrd5V2ReceiptSealCandidate({
    schema: runtime.schema,
    preState: mainEffect.right.nextState,
    predecessor: {
      descriptor: r1.right.descriptor,
      journalLineageId: r1Witness.state.journalLineageId,
      schemaContentSha256: r1Witness.state.schema.content.sha256
    },
    precedingEffect: mainEffectInput,
    command: receiptCommand.right,
    evidenceAuthority: decoded.right.receipt.authority,
    receiptPayloadBytes: exactReceipt.right.bytes,
    receiptPayloadDescriptor: exactReceipt.right.descriptor
  })
  if (Either.isLeft(receiptPreflight)) {
    return yield* v2Failure(
      "CAS1_EXACT_R1_RECEIPT_PENDING",
      "receipt failed pre-CAS DNRD grammar: " + receiptPreflight.left.code
    )
  }
  yield* stageV2ConsumptionSupport(
    runtime,
    supplied.receipt.consumption,
    receiptPayload.right
  )
  const receiptTransition = yield* stageV2Transition(
    runtime,
    supplied.receipt,
    receiptCommand.right
  )

  const expectedR2 = expectedR1 + 1
  const receiptAttempt = yield* Effect.either(
    commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal(
      runtime,
      receiptTransition
    )
  )
  const r2Witness =
    yield* recoverCanonicalAtomV2DurableFromDnrd5DispatcherInternal(runtime)
  if (r2Witness.state.canonical.revision === expectedR1) {
    return yield* v2Failure(
      "CAS1_EXACT_R1_RECEIPT_PENDING",
      Either.isLeft(receiptAttempt)
        ? "CAS2 did not append; exact R1 remains durably receipt-pending"
        : "CAS2 returned without an exact recovered durable successor"
    )
  }
  if (r2Witness.state.canonical.revision !== expectedR2) {
    return yield* v2Failure(
      "CAS2_PREDECESSOR_LOST",
      "recovered durable tail advanced outside the exact R1 to R2 window"
    )
  }
  const r2 = exactRecoveredTail(
    r2Witness,
    expectedR2,
    "CAS2_PREDECESSOR_LOST"
  )
  if (Either.isLeft(r2)) return yield* r2.left
  const receiptRawEnvelopes = yield* recoveredEnvelopesFor(
    runtime,
    r2.right.commit
  )
  const seal = validateDnrd5V2ReceiptSeal({
    schema: runtime.schema,
    preState: mainEffect.right.nextState,
    predecessor: {
      descriptor: r1.right.descriptor,
      journalLineageId: r1Witness.state.journalLineageId,
      schemaContentSha256: r1Witness.state.schema.content.sha256
    },
    precedingEffect: mainEffectInput,
    command: receiptCommand.right,
    evidenceAuthority: decoded.right.receipt.authority,
    record: r2.right.commit,
    recordBytes: r2.right.bytes,
    recordDescriptor: r2.right.descriptor,
    envelopes: receiptRawEnvelopes,
    receiptPayloadBytes: exactReceipt.right.bytes,
    receiptPayloadDescriptor: exactReceipt.right.descriptor,
    usedReceiptRecordDescriptorSha256s: r1Witness.history.map(
      (entry) => entry.record.sha256
    )
  })
  if (Either.isLeft(seal)) {
    return yield* v2Failure(
      "CAS2_PREDECESSOR_LOST",
      "R2 is not the exact receipt seal: " + seal.left.code
    )
  }
  if (!sameCanonicalValue(seal.right.nextState, r2Witness.state.canonical)) {
    return yield* v2Failure(
      "CAS2_PREDECESSOR_LOST",
      "raw R2 replay state differs from the recovered R2 state"
    )
  }

  const r2Consumptions = yield* recoveredV2Consumptions(
    runtime,
    r2Witness.state.canonical.atoms
  )
  const recoveredReceiptConsumption = r2Consumptions.get(
    receiptConsumption.right.capabilityNonceSha256
  )
  if (
    recoveredReceiptConsumption === undefined ||
    recoveredReceiptConsumption.phase !== contract.receiptPhase ||
    recoveredReceiptConsumption.atomKeyId !==
      receiptConsumption.right.atomKeyId ||
    !sameCanonicalValue(
      recoveredReceiptConsumption.atom,
      supplied.receipt.consumption.atom
    )
  ) {
    return yield* v2Failure(
      "CAS2_PREDECESSOR_LOST",
      "R2 lacks the exact evidence-seal consumption"
    )
  }

  return snapshot({
    milestone: "CAS2_EXACT_R2_CONFIRMED" as const,
    mainRecord: r1.right.descriptor,
    receiptRecord: r2.right.descriptor,
    mainConsumptionAtomKeyId: mainConsumption.right.atomKeyId,
    receiptConsumptionAtomKeyId: receiptConsumption.right.atomKeyId,
    terminal:
      "NOT_PROVIDER_CALL_NOT_OCCURRENCE_NOT_LEARNING_NOT_EFFICACY" as const
  })
})

/** Crash/lost-return continuation; it never invokes CAS1. */
const resumeDnrd5V2TwoCas = (
  input: unknown,
  contract: Dnrd5V2TwoCasContract
): Effect.Effect<
  Dnrd5V2TwoCasAdmitConfirmed,
  CanonicalAtomV2DurableSubmitFailure | Dnrd5V2TwoCasRecoveryError,
  CanonicalAtomV2DurableRuntime
> => Effect.gen(function* () {
  const decoded = decodeTwoCasInput(input, contract)
  if (Either.isLeft(decoded)) return yield* decoded.left
  const supplied = decoded.right
  const mainPayload = decodeV2ConsumptionPayload(supplied.main.consumption.payloadBytes)
  const receiptPayload = decodeV2ConsumptionPayload(supplied.receipt.consumption.payloadBytes)
  if (Either.isLeft(mainPayload)) return yield* mainPayload.left
  if (Either.isLeft(receiptPayload)) return yield* receiptPayload.left
  if (
    mainPayload.right.phase !== contract.mainPhase ||
    receiptPayload.right.phase !== contract.receiptPhase ||
    mainPayload.right.capabilityNonceSha256 === receiptPayload.right.capabilityNonceSha256
  ) return yield* v2Failure("RECOVERY_INDETERMINATE", `resume requires distinct ${contract.mainPhase} and ${contract.receiptPhase} candidates`)

  const runtime = yield* CanonicalAtomV2DurableRuntime
  if (Either.isLeft(validateDnrd5V2CanonicalSchema(runtime.schema))) {
    return yield* v2Failure("RECOVERY_INDETERMINATE", "runtime does not carry the exact DNRD-5 v2 schema")
  }
  const witness = yield* recoverCanonicalAtomV2DurableFromDnrd5DispatcherInternal(runtime)
  const s0Revision = mainPayload.right.authorizationSnapshot.stateRevision
  const expectedR1 = s0Revision + 1
  const expectedR2 = expectedR1 + 1
  if (witness.state.canonical.revision === s0Revision) {
    return yield* v2Failure("RECOVERY_INDETERMINATE", "resume requires an exact durable R1 and will never submit CAS1")
  }
  if (witness.state.canonical.revision !== expectedR1 && witness.state.canonical.revision !== expectedR2) {
    return yield* v2Failure("CAS2_PREDECESSOR_LOST", "resume refuses a journal tail other than exact R1 or exact R2")
  }

  const s0 = yield* replayRecoveredPrefixAt(runtime, witness, s0Revision)
  const s0Sha = canonicalAtomV2StateSha256(s0.state)
  if (Either.isLeft(s0Sha)) return yield* v2Failure("RECOVERY_INDETERMINATE", "cannot hash raw-replayed S0")
  const s0Snapshot = Object.freeze({
    stateRevision: s0Revision,
    stateSha256: s0Sha.right,
    journalLineageId: witness.state.journalLineageId,
    journalHead: s0.head
  })
  if (
    !sameCanonicalValue(supplied.main.consumption.authorizationSnapshot, s0Snapshot) ||
    !sameCanonicalValue(supplied.main.consumption.state, s0.state) ||
    !sameCanonicalValue(supplied.main.authority.state, s0.state)
  ) return yield* v2Failure("RECOVERY_INDETERMINATE", "resume candidate S0 does not equal the raw-replayed prefix")

  const mainAuthority = validateDnrd5V2AuthorityPayloadAtState({ ...supplied.main.authority, state: s0.state })
  if (Either.isLeft(mainAuthority) || mainAuthority.right.chain.phase !== contract.mainPhase) {
    return yield* v2Failure("RECOVERY_INDETERMINATE", `raw-replayed S0 does not validate ${contract.mainPhase} authority`)
  }
  yield* verifyAuthorityBytes(runtime, supplied.main.authority)
  const s0Consumptions = yield* recoveredV2Consumptions(runtime, s0.state.atoms)
  if (s0Consumptions.has(mainPayload.right.capabilityNonceSha256) || s0Consumptions.has(receiptPayload.right.capabilityNonceSha256)) {
    return yield* v2Failure("RECOVERY_INDETERMINATE", "resume S0 already contains a candidate nonce")
  }
  const mainConsumption = validateDnrd5V2Consumption({ ...supplied.main.consumption, state: s0.state, authorizationSnapshot: s0Snapshot })
  if (Either.isLeft(mainConsumption) || !consumptionMatchesAuthority(mainConsumption.right, mainAuthority.right)) {
    return yield* v2Failure("RECOVERY_INDETERMINATE", "resume main consumption does not bind raw S0 authority")
  }
  const mainCommand = decodeV2ProjectionCommand(supplied.main.consumption)
  if (Either.isLeft(mainCommand) || !commandMatchesAuthority(mainCommand.right, mainAuthority.right)) {
    return yield* v2Failure("RECOVERY_INDETERMINATE", "resume main command is not authority-bound")
  }
  const mainTransitionCandidate = validateV2TransitionCandidate(
    runtime.schemaContent.content.sha256,
    supplied.main,
    mainCommand.right
  )
  if (Either.isLeft(mainTransitionCandidate)) return yield* mainTransitionCandidate.left
  const mainPreflight = validateDnrd5V2EffectCommandCandidate(runtime.schema, s0.state, mainCommand.right)
  if (Either.isLeft(mainPreflight)) return yield* v2Failure("RECOVERY_INDETERMINATE", "resume main effect candidate fails DNRD grammar")

  const r1 = rawCommitAt(witness, expectedR1)
  if (Either.isLeft(r1)) return yield* r1.left
  const replayedR1 = yield* replayRecoveredPrefixAt(runtime, witness, expectedR1)
  const r1Envelopes = yield* recoveredEnvelopesFor(runtime, r1.right.commit)
  const mainEffectInput = Object.freeze({
    schema: runtime.schema,
    preState: s0.state,
    predecessor: Object.freeze({ descriptor: s0.head, journalLineageId: witness.state.journalLineageId, schemaContentSha256: runtime.schemaContent.content.sha256 }),
    command: mainCommand.right,
    record: r1.right.commit,
    recordBytes: r1.right.bytes,
    recordDescriptor: r1.right.descriptor,
    envelopes: r1Envelopes,
    usedRecordDescriptorSha256s: witness.history.slice(0, s0Revision).map((entry) => entry.record.sha256)
  })
  const mainEffect = validateDnrd5V2RecordBoundEffect(mainEffectInput)
  if (Either.isLeft(mainEffect) || !sameCanonicalValue(mainEffect.right.nextState, replayedR1.state)) {
    return yield* v2Failure("RECOVERY_INDETERMINATE", "raw record at exact S0+1 is not this candidate's R1")
  }
  const r1Consumptions = yield* recoveredV2Consumptions(runtime, replayedR1.state.atoms)
  const recoveredMain = r1Consumptions.get(mainConsumption.right.capabilityNonceSha256)
  if (
    recoveredMain === undefined || recoveredMain.phase !== contract.mainPhase ||
    recoveredMain.atomKeyId !== mainConsumption.right.atomKeyId ||
    !sameCanonicalValue(recoveredMain.atom, supplied.main.consumption.atom) ||
    r1Consumptions.has(receiptPayload.right.capabilityNonceSha256)
  ) return yield* v2Failure("RECOVERY_INDETERMINATE", "raw R1 does not contain exactly the candidate main consumption")

  const r1Sha = canonicalAtomV2StateSha256(replayedR1.state)
  if (Either.isLeft(r1Sha)) return yield* v2Failure("RECOVERY_INDETERMINATE", "cannot hash raw-replayed R1")
  const r1Snapshot = Object.freeze({ stateRevision: expectedR1, stateSha256: r1Sha.right, journalLineageId: witness.state.journalLineageId, journalHead: r1.right.descriptor })
  if (
    !sameCanonicalValue(supplied.receipt.consumption.authorizationSnapshot, r1Snapshot) ||
    !sameCanonicalValue(supplied.receipt.consumption.state, replayedR1.state) ||
    !sameCanonicalValue(supplied.receipt.authority.state, replayedR1.state)
  ) return yield* v2Failure("RECOVERY_INDETERMINATE", "receipt candidate does not bind raw-replayed R1")

  const receiptAuthority = validateDnrd5V2AuthorityPayloadAtState({ ...supplied.receipt.authority, state: replayedR1.state })
  const authorityPair = validateDnrd5V2AuthorityDisjointPair(
    { ...supplied.main.authority, state: s0.state },
    { ...supplied.receipt.authority, state: replayedR1.state }
  )
  if (Either.isLeft(receiptAuthority) || receiptAuthority.right.chain.phase !== contract.receiptPhase || Either.isLeft(authorityPair)) {
    return yield* v2Failure("RECOVERY_INDETERMINATE", "raw R1 does not validate distinct receipt authority")
  }
  yield* verifyAuthorityBytes(runtime, supplied.receipt.authority)
  const receiptConsumption = validateDnrd5V2Consumption({ ...supplied.receipt.consumption, state: replayedR1.state, authorizationSnapshot: r1Snapshot })
  if (Either.isLeft(receiptConsumption) || !consumptionMatchesAuthority(receiptConsumption.right, receiptAuthority.right)) {
    return yield* v2Failure("RECOVERY_INDETERMINATE", "receipt consumption does not bind raw R1 authority")
  }
  const receiptCommand = decodeV2ProjectionCommand(supplied.receipt.consumption)
  if (Either.isLeft(receiptCommand) || !commandMatchesAuthority(receiptCommand.right, receiptAuthority.right)) {
    return yield* v2Failure("RECOVERY_INDETERMINATE", "receipt command is not authority-bound")
  }
  const receiptTransitionCandidate = validateV2TransitionCandidate(
    runtime.schemaContent.content.sha256,
    supplied.receipt,
    receiptCommand.right
  )
  if (Either.isLeft(receiptTransitionCandidate)) return yield* receiptTransitionCandidate.left
  const exactReceipt = prevalidateTwoCasReceipt(contract, supplied.receipt, receiptCommand.right, mainEffect.right, mainConsumption.right)
  if (Either.isLeft(exactReceipt)) return yield* exactReceipt.left
  const receiptPreflight = validateDnrd5V2ReceiptSealCandidate({
    schema: runtime.schema,
    preState: replayedR1.state,
    predecessor: { descriptor: r1.right.descriptor, journalLineageId: witness.state.journalLineageId, schemaContentSha256: runtime.schemaContent.content.sha256 },
    precedingEffect: mainEffectInput,
    command: receiptCommand.right,
    evidenceAuthority: supplied.receipt.authority,
    receiptPayloadBytes: exactReceipt.right.bytes,
    receiptPayloadDescriptor: exactReceipt.right.descriptor
  })
  if (Either.isLeft(receiptPreflight)) return yield* v2Failure("RECOVERY_INDETERMINATE", "receipt candidate fails pre-CAS DNRD grammar")

  const confirmR2 = (r2Witness: CanonicalAtomV2DurableRecoveryWitness) => Effect.gen(function* () {
    if (r2Witness.state.canonical.revision !== expectedR2) return yield* v2Failure("CAS2_PREDECESSOR_LOST", "resume recovery does not end at exact R2")
    const r2 = rawCommitAt(r2Witness, expectedR2)
    if (Either.isLeft(r2)) return yield* r2.left
    const r2Prefix = yield* replayRecoveredPrefixAt(runtime, r2Witness, expectedR2)
    if (!sameCanonicalValue(r2Prefix.state, r2Witness.state.canonical)) return yield* v2Failure("CAS2_PREDECESSOR_LOST", "R2 raw prefix is not the recovered durable state")
    const envelopes = yield* recoveredEnvelopesFor(runtime, r2.right.commit)
    const seal = validateDnrd5V2ReceiptSeal({
      schema: runtime.schema, preState: replayedR1.state,
      predecessor: { descriptor: r1.right.descriptor, journalLineageId: witness.state.journalLineageId, schemaContentSha256: runtime.schemaContent.content.sha256 },
      precedingEffect: mainEffectInput, command: receiptCommand.right, evidenceAuthority: supplied.receipt.authority,
      record: r2.right.commit, recordBytes: r2.right.bytes, recordDescriptor: r2.right.descriptor, envelopes,
      receiptPayloadBytes: exactReceipt.right.bytes, receiptPayloadDescriptor: exactReceipt.right.descriptor,
      usedReceiptRecordDescriptorSha256s: r2Witness.history.slice(0, expectedR1).map((entry) => entry.record.sha256)
    })
    if (Either.isLeft(seal) || !sameCanonicalValue(seal.right.nextState, r2Witness.state.canonical)) return yield* v2Failure("CAS2_PREDECESSOR_LOST", "raw R2 is not the exact receipt seal")
    const r2Consumptions = yield* recoveredV2Consumptions(runtime, r2Witness.state.canonical.atoms)
    const recoveredReceipt = r2Consumptions.get(receiptConsumption.right.capabilityNonceSha256)
    if (recoveredReceipt === undefined || recoveredReceipt.phase !== contract.receiptPhase || recoveredReceipt.atomKeyId !== receiptConsumption.right.atomKeyId || !sameCanonicalValue(recoveredReceipt.atom, supplied.receipt.consumption.atom)) {
      return yield* v2Failure("CAS2_PREDECESSOR_LOST", "raw R2 lacks the exact receipt consumption")
    }
    return snapshot({ milestone: "CAS2_EXACT_R2_CONFIRMED" as const, mainRecord: r1.right.descriptor, receiptRecord: r2.right.descriptor, mainConsumptionAtomKeyId: mainConsumption.right.atomKeyId, receiptConsumptionAtomKeyId: receiptConsumption.right.atomKeyId, terminal: "NOT_PROVIDER_CALL_NOT_OCCURRENCE_NOT_LEARNING_NOT_EFFICACY" as const })
  })

  if (witness.state.canonical.revision === expectedR2) return yield* confirmR2(witness)

  yield* stageV2ConsumptionSupport(runtime, supplied.receipt.consumption, receiptPayload.right)
  const transition = yield* stageV2Transition(runtime, supplied.receipt, receiptCommand.right)
  yield* Effect.either(commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal(runtime, transition))
  const after = yield* recoverCanonicalAtomV2DurableFromDnrd5DispatcherInternal(runtime)
  if (after.state.canonical.revision === expectedR1) return yield* v2Failure("CAS1_EXACT_R1_RECEIPT_PENDING", "CAS2 did not append; exact R1 remains receipt-pending")
  return yield* confirmR2(after)
})

/** Initial-only ADMIT entry.  RESTORE phases are rejected at this boundary. */
export const submitDnrd5V2AdmitTwoCas = (input: unknown): Effect.Effect<
  Dnrd5V2TwoCasAdmitConfirmed,
  CanonicalAtomV2DurableSubmitFailure | Dnrd5V2TwoCasRecoveryError,
  CanonicalAtomV2DurableRuntime
> => submitDnrd5V2TwoCas(input, ADMIT_TWO_CAS_CONTRACT)

/** Initial-only RESTORE entry; exact-W0 projection remains an external companion gate. */
export const submitDnrd5V2RestoreTwoCas = (input: unknown): Effect.Effect<
  Dnrd5V2TwoCasRestoreConfirmed,
  CanonicalAtomV2DurableSubmitFailure | Dnrd5V2TwoCasRecoveryError,
  CanonicalAtomV2DurableRuntime
> => submitDnrd5V2TwoCas(input, RESTORE_TWO_CAS_CONTRACT)

/** Resume never invokes CAS1; it only confirms exact R1/R2 for ADMIT. */
export const resumeDnrd5V2AdmitTwoCas = (input: unknown): Effect.Effect<
  Dnrd5V2TwoCasAdmitConfirmed,
  CanonicalAtomV2DurableSubmitFailure | Dnrd5V2TwoCasRecoveryError,
  CanonicalAtomV2DurableRuntime
> => resumeDnrd5V2TwoCas(input, ADMIT_TWO_CAS_CONTRACT)

/** Resume never invokes CAS1; exact-W0 projection remains an external companion gate. */
export const resumeDnrd5V2RestoreTwoCas = (input: unknown): Effect.Effect<
  Dnrd5V2TwoCasRestoreConfirmed,
  CanonicalAtomV2DurableSubmitFailure | Dnrd5V2TwoCasRecoveryError,
  CanonicalAtomV2DurableRuntime
> => resumeDnrd5V2TwoCas(input, RESTORE_TWO_CAS_CONTRACT)
