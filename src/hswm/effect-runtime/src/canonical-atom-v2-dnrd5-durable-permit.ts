/** Durable DNRD-5 admission seam with same-command one-shot consumption. */
import { Data, Effect, Either, Schema } from "effect"

import {
  CommitCanonicalAtomsV2ContentBoundSchema,
  type CommitCanonicalAtomsV2ContentBound
} from "./canonical-atom-v2-content-bound.js"
import {
  sameCanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2ContentDescriptor
} from "./canonical-atom-v2-content.js"
import {
  CanonicalAtomV2DurableRuntime,
  commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal,
  recoverCanonicalAtomV2DurableFromDnrd5DispatcherInternal,
  type CanonicalAtomV2DurableEvolution,
  type CanonicalAtomV2DurableSubmitFailure
} from "./canonical-atom-v2-durable-runtime.js"
import {
  HSWM_CANONICAL_JSON_MEDIA_TYPE,
  canonicalJsonBytes,
  canonicalJsonSha256
} from "./canonical-atom-v2-json.js"
import { canonicalAtomV2StateSha256 } from "./canonical-atom-v2-state-journal.js"
import {
  canonicalAtomV2StateJournalRecordBytes,
  describeCanonicalAtomV2StateJournalRecord
} from "./canonical-atom-v2-state-journal.js"
import {
  canonicalAtomV2KeyId,
  type CanonicalAtomV2,
  type CommitCanonicalAtomsV2Command
} from "./canonical-atom-v2-schema.js"
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
