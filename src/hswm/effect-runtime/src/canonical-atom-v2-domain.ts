import { Data, Either, Schema } from "effect"

import {
  CanonicalAtomV2Schema,
  CommitCanonicalAtomsV2CommandSchema,
  HSWM_CANONICAL_RECEIPT_V2_CONTRACT_VERSION,
  HSWM_SUPERSEDES_REFERENCE_ROLE,
  HSWM_SUPERSEDES_REFERENCE_TYPE,
  HSWMCanonicalSchemaV2Schema,
  canonicalAtomV2KeyId,
  snapshotCanonicalAtomV2,
  type CanonicalAtomV2,
  type CanonicalAtomV2Key,
  type CanonicalAtomV2KindContract,
  type CommitCanonicalAtomsV2Command,
  type HSWMCanonicalSchemaV2
} from "./canonical-atom-v2-schema.js"

export type CanonicalAtomV2ErrorCode =
  | "SCHEMA_INVALID"
  | "SCHEMA_VERSION_MISMATCH"
  | "STATE_INVALID"
  | "STATE_REVISION_CONFLICT"
  | "TRANSITION_INVALID"
  | "TRANSITION_DUPLICATE"
  | "READ_SET_INVALID"
  | "ATOM_KEY_DUPLICATE"
  | "KIND_INVALID"
  | "OWNER_INVALID"
  | "REFERENCE_INVALID"
  | "REVISION_INVALID"
  | "PROVENANCE_INVALID"
  | "TRACE_UNSUPPORTED"
  | "MIGRATION_UNSUPPORTED"

export class CanonicalAtomV2Error extends Data.TaggedError(
  "CanonicalAtomV2Error"
)<{
  readonly code: CanonicalAtomV2ErrorCode
  readonly detail: string
}> {}

export interface CanonicalAtomV2State {
  readonly schemaVersion: string
  readonly revision: number
  readonly bootstrapClosed: boolean
  readonly atoms: ReadonlyArray<CanonicalAtomV2>
  readonly acceptedTransitionIds: ReadonlyArray<string>
}

export interface CanonicalAtomV2GuardReceipt {
  readonly schema: "PASSED"
  readonly ownerTotality: "PASSED"
  readonly references: "PASSED"
  readonly revision: "PASSED"
  readonly permission: "REFERENCE_GRANT_MATCHED_NOT_CANONICAL_PERMIT"
}

export interface CanonicalAtomV2EffectReceipt {
  readonly _tag: "CanonicalAtomV2EffectReceipt"
  readonly contractVersion: typeof HSWM_CANONICAL_RECEIPT_V2_CONTRACT_VERSION
  readonly transitionId: string
  readonly schemaVersion: string
  readonly previousStateRevision: number
  readonly nextStateRevision: number
  readonly readSet: ReadonlyArray<CanonicalAtomV2Key>
  readonly writeSet: ReadonlyArray<CanonicalAtomV2Key>
  readonly traceRef: CanonicalAtomV2Key | null
  readonly guard: CanonicalAtomV2GuardReceipt
  readonly actorClaim: string
  readonly authorizationRef: string
  readonly scope: string
  readonly decidedAt: string
  readonly decision: "ACCEPTED"
  readonly provenanceSha256: string
}

export interface CanonicalAtomV2Evolution {
  readonly state: CanonicalAtomV2State
  readonly receipt: CanonicalAtomV2EffectReceipt
}

const fail = (
  code: CanonicalAtomV2ErrorCode,
  detail: string
): Either.Either<never, CanonicalAtomV2Error> =>
  Either.left(new CanonicalAtomV2Error({ code, detail }))

const compareText = (left: string, right: string): number =>
  left < right ? -1 : left > right ? 1 : 0

const compareKeys = (
  left: CanonicalAtomV2Key,
  right: CanonicalAtomV2Key
): number => {
  const schema = compareText(left.schemaVersion, right.schemaVersion)
  if (schema !== 0) return schema
  const lineage = compareText(left.lineageId, right.lineageId)
  if (lineage !== 0) return lineage
  const atom = compareText(left.atomUid, right.atomUid)
  if (atom !== 0) return atom
  return left.revisionId - right.revisionId
}

const sameKey = (
  left: CanonicalAtomV2Key,
  right: CanonicalAtomV2Key
): boolean => canonicalAtomV2KeyId(left) === canonicalAtomV2KeyId(right)

const snapshotKey = (key: CanonicalAtomV2Key): CanonicalAtomV2Key =>
  Object.freeze({ ...key })

export const initialCanonicalAtomV2State = (
  schemaVersion: string
): CanonicalAtomV2State =>
  Object.freeze({
    schemaVersion,
    revision: 0,
    bootstrapClosed: false,
    atoms: Object.freeze([]),
    acceptedTransitionIds: Object.freeze([])
  })

export const snapshotCanonicalAtomV2State = (
  state: CanonicalAtomV2State
): CanonicalAtomV2State =>
  Object.freeze({
    schemaVersion: state.schemaVersion,
    revision: state.revision,
    bootstrapClosed: state.bootstrapClosed,
    atoms: Object.freeze(state.atoms.map(snapshotCanonicalAtomV2)),
    acceptedTransitionIds: Object.freeze([...state.acceptedTransitionIds])
  })

export const snapshotCanonicalAtomV2Receipt = (
  receipt: CanonicalAtomV2EffectReceipt
): CanonicalAtomV2EffectReceipt =>
  Object.freeze({
    _tag: receipt._tag,
    contractVersion: receipt.contractVersion,
    transitionId: receipt.transitionId,
    schemaVersion: receipt.schemaVersion,
    previousStateRevision: receipt.previousStateRevision,
    nextStateRevision: receipt.nextStateRevision,
    readSet: Object.freeze(receipt.readSet.map(snapshotKey)),
    writeSet: Object.freeze(receipt.writeSet.map(snapshotKey)),
    traceRef:
      receipt.traceRef === null ? null : snapshotKey(receipt.traceRef),
    guard: Object.freeze({ ...receipt.guard }),
    actorClaim: receipt.actorClaim,
    authorizationRef: receipt.authorizationRef,
    scope: receipt.scope,
    decidedAt: receipt.decidedAt,
    decision: receipt.decision,
    provenanceSha256: receipt.provenanceSha256
  })

const hasDuplicates = (values: ReadonlyArray<string>): boolean =>
  new Set(values).size !== values.length

export const validateHSWMCanonicalSchemaV2 = (
  schema: HSWMCanonicalSchemaV2
): Either.Either<HSWMCanonicalSchemaV2, CanonicalAtomV2Error> => {
  const decoded = Schema.decodeUnknownEither(HSWMCanonicalSchemaV2Schema, {
    onExcessProperty: "error"
  })(schema)
  if (Either.isLeft(decoded)) {
    return fail(
      "SCHEMA_INVALID",
      "schema does not satisfy the strict v2 structural contract"
    )
  }
  const checked = decoded.right
  const ownerAddresses = checked.owners.map(({ address }) => address)
  if (hasDuplicates(ownerAddresses)) {
    return fail("SCHEMA_INVALID", "owner registry addresses must be unique")
  }
  const ownerSet = new Set(ownerAddresses)
  const kindNames = checked.kinds.map(({ kind }) => kind)
  if (hasDuplicates(kindNames)) {
    return fail("SCHEMA_INVALID", "atom kind names must be unique")
  }
  const kindSet = new Set(kindNames)

  for (const kind of checked.kinds) {
    if (hasDuplicates(kind.allowedOwners)) {
      return fail(
        "SCHEMA_INVALID",
        `kind ${kind.kind} repeats an allowed owner`
      )
    }
    if (kind.allowedOwners.some((owner) => !ownerSet.has(owner))) {
      return fail(
        "SCHEMA_INVALID",
        `kind ${kind.kind} names an owner outside the schema registry`
      )
    }
    if (kind.form === "ENTITY" && kind.minimumArity !== 0) {
      return fail(
        "SCHEMA_INVALID",
        `entity kind ${kind.kind} must have minimumArity 0`
      )
    }
    if (kind.form === "RELATION" && kind.minimumArity < 1) {
      return fail(
        "SCHEMA_INVALID",
        `relation kind ${kind.kind} must declare positive arity`
      )
    }

    const referenceTypes = kind.referenceContracts.map(
      ({ referenceType }) => referenceType
    )
    if (hasDuplicates(referenceTypes)) {
      return fail(
        "SCHEMA_INVALID",
        `kind ${kind.kind} repeats a reference contract`
      )
    }
    for (const reference of kind.referenceContracts) {
      const roles = reference.roles.map(({ role }) => role)
      if (hasDuplicates(roles)) {
        return fail(
          "SCHEMA_INVALID",
          `kind ${kind.kind} repeats a role in one reference contract`
        )
      }
      for (const role of reference.roles) {
        if (role.minimum > role.maximum) {
          return fail(
            "SCHEMA_INVALID",
            `kind ${kind.kind} has an inverted role cardinality`
          )
        }
        if (hasDuplicates(role.targetKinds)) {
          return fail(
            "SCHEMA_INVALID",
            `kind ${kind.kind} repeats a role target kind`
          )
        }
        if (role.targetKinds.some((target) => !kindSet.has(target))) {
          return fail(
            "SCHEMA_INVALID",
            `kind ${kind.kind} references an unknown target kind`
          )
        }
      }
    }

    const supersedes = kind.referenceContracts.find(
      ({ referenceType }) =>
        referenceType === HSWM_SUPERSEDES_REFERENCE_TYPE
    )
    if (kind.revisionPolicy === "LINEAR") {
      if (
        supersedes === undefined ||
        supersedes.roles.length !== 1 ||
        supersedes.roles[0]?.role !== HSWM_SUPERSEDES_REFERENCE_ROLE ||
        supersedes.roles[0]?.minimum !== 0 ||
        supersedes.roles[0]?.maximum !== 1 ||
        !supersedes.roles[0]?.targetKinds.includes(kind.kind)
      ) {
        return fail(
          "SCHEMA_INVALID",
          `linear kind ${kind.kind} requires an optional self-kind supersedes reference`
        )
      }
    } else if (supersedes !== undefined) {
      return fail(
        "SCHEMA_INVALID",
        `singleton kind ${kind.kind} cannot declare supersedes`
      )
    }
  }

  return Either.right(checked)
}

const isCanonicalInstant = (value: string): boolean => {
  const milliseconds = Date.parse(value)
  return (
    Number.isFinite(milliseconds) &&
    new Date(milliseconds).toISOString() === value
  )
}

const logicalAtomId = (key: CanonicalAtomV2Key): string =>
  `${key.schemaVersion}|${key.lineageId}|${key.atomUid}`

const latestVersion = (
  atoms: ReadonlyArray<CanonicalAtomV2>,
  key: CanonicalAtomV2Key
): CanonicalAtomV2 | undefined =>
  atoms
    .filter((atom) => logicalAtomId(atom.key) === logicalAtomId(key))
    .sort((left, right) => right.key.revisionId - left.key.revisionId)[0]

const validateReferenceTarget = (
  reference: CanonicalAtomV2Key,
  atomByKey: ReadonlyMap<string, CanonicalAtomV2>,
  existingKeyIds: ReadonlySet<string>,
  readSetIds: ReadonlySet<string>,
  detail: string
): Either.Either<CanonicalAtomV2, CanonicalAtomV2Error> => {
  const id = canonicalAtomV2KeyId(reference)
  const target = atomByKey.get(id)
  if (target === undefined) {
    return fail("REFERENCE_INVALID", `${detail} points to a missing atom`)
  }
  if (existingKeyIds.has(id) && !readSetIds.has(id)) {
    return fail(
      "READ_SET_INVALID",
      `${detail} observes an existing atom absent from the read set`
    )
  }
  return Either.right(target)
}

const validateRevision = (
  kind: CanonicalAtomV2KindContract,
  atom: CanonicalAtomV2,
  currentAtoms: ReadonlyArray<CanonicalAtomV2>
): Either.Either<void, CanonicalAtomV2Error> => {
  const previous = latestVersion(currentAtoms, atom.key)
  const supersedes = atom.references.filter(
    ({ referenceType }) =>
      referenceType === HSWM_SUPERSEDES_REFERENCE_TYPE
  )

  if (previous === undefined) {
    if (atom.key.revisionId !== 0 || supersedes.length !== 0) {
      return fail(
        "REVISION_INVALID",
        `first revision of ${atom.key.atomUid} must be revision 0 without supersedes`
      )
    }
    return Either.right(undefined)
  }
  if (kind.revisionPolicy !== "LINEAR") {
    return fail(
      "REVISION_INVALID",
      `singleton kind ${kind.kind} cannot be revised`
    )
  }
  if (previous.key.revisionId >= Number.MAX_SAFE_INTEGER) {
    return fail(
      "REVISION_INVALID",
      `revision lineage for ${atom.key.atomUid} is exhausted`
    )
  }
  if (atom.key.revisionId !== previous.key.revisionId + 1) {
    return fail(
      "REVISION_INVALID",
      `revision of ${atom.key.atomUid} must advance the latest version by one`
    )
  }
  if (atom.kind !== previous.kind) {
    return fail(
      "REVISION_INVALID",
      `ordinary revision cannot change kind for ${atom.key.atomUid}`
    )
  }
  if (atom.responsibilityOwner !== previous.responsibilityOwner) {
    return fail(
      "REVISION_INVALID",
      `owner change for ${atom.key.atomUid} requires schema migration`
    )
  }
  if (
    supersedes.length !== 1 ||
    !sameKey(supersedes[0]!.target, previous.key)
  ) {
    return fail(
      "REVISION_INVALID",
      `revision of ${atom.key.atomUid} must supersede exactly its latest version`
    )
  }
  return Either.right(undefined)
}

const validateAtom = (
  schema: HSWMCanonicalSchemaV2,
  atom: CanonicalAtomV2,
  currentAtoms: ReadonlyArray<CanonicalAtomV2>,
  atomByKey: ReadonlyMap<string, CanonicalAtomV2>,
  existingKeyIds: ReadonlySet<string>,
  readSetIds: ReadonlySet<string>
): Either.Either<void, CanonicalAtomV2Error> => {
  if (atom.key.schemaVersion !== schema.schemaVersion) {
    return fail(
      "SCHEMA_VERSION_MISMATCH",
      `atom ${atom.key.atomUid} does not belong to the active schema`
    )
  }
  const kind = schema.kinds.find((entry) => entry.kind === atom.kind)
  if (kind === undefined) {
    return fail("KIND_INVALID", `atom ${atom.key.atomUid} has unknown kind`)
  }
  if (
    !schema.owners.some(
      ({ address }) => address === atom.responsibilityOwner
    ) ||
    !kind.allowedOwners.includes(atom.responsibilityOwner)
  ) {
    return fail(
      "OWNER_INVALID",
      `atom ${atom.key.atomUid} has no schema-valid responsibility owner`
    )
  }
  if (atom.provenance.mode === "MIGRATION") {
    return fail(
      "MIGRATION_UNSUPPORTED",
      "schema migration is outside the v2 reference-kernel commit path"
    )
  }
  if (
    atom.provenance.mode === "BOOTSTRAP" &&
    atom.provenance.sourceRef !== null
  ) {
    return fail(
      "PROVENANCE_INVALID",
      "bootstrap provenance cannot name a canonical predecessor"
    )
  }
  if (
    atom.provenance.mode === "DERIVATION" &&
    atom.provenance.sourceRef === null
  ) {
    return fail(
      "PROVENANCE_INVALID",
      "derived atoms require a canonical provenance source"
    )
  }
  if (atom.provenance.sourceRef !== null) {
    const source = validateReferenceTarget(
      atom.provenance.sourceRef,
      atomByKey,
      existingKeyIds,
      readSetIds,
      `provenance of ${atom.key.atomUid}`
    )
    if (Either.isLeft(source)) return source
  }

  const referenceIds = atom.references.map(
    (reference) =>
      `${reference.referenceType}|${reference.role}|${canonicalAtomV2KeyId(reference.target)}`
  )
  if (hasDuplicates(referenceIds)) {
    return fail(
      "REFERENCE_INVALID",
      `atom ${atom.key.atomUid} repeats an identical typed reference`
    )
  }

  for (const reference of atom.references) {
    const contract = kind.referenceContracts.find(
      ({ referenceType }) => referenceType === reference.referenceType
    )
    if (contract === undefined) {
      return fail(
        "REFERENCE_INVALID",
        `atom ${atom.key.atomUid} uses an undeclared reference type`
      )
    }
    const roleContract = contract.roles.find(
      ({ role }) => role === reference.role
    )
    if (roleContract === undefined) {
      return fail(
        "REFERENCE_INVALID",
        `reference ${reference.referenceType} of ${atom.key.atomUid} uses an undeclared role`
      )
    }
    const target = validateReferenceTarget(
      reference.target,
      atomByKey,
      existingKeyIds,
      readSetIds,
      `reference ${reference.referenceType} of ${atom.key.atomUid}`
    )
    if (Either.isLeft(target)) return target
    if (!roleContract.targetKinds.includes(target.right.kind)) {
      return fail(
        "REFERENCE_INVALID",
        `reference ${reference.referenceType} of ${atom.key.atomUid} targets a forbidden kind`
      )
    }
  }

  for (const contract of kind.referenceContracts) {
    for (const role of contract.roles) {
      const count = atom.references.filter(
        (reference) =>
          reference.referenceType === contract.referenceType &&
          reference.role === role.role
      ).length
      if (count < role.minimum || count > role.maximum) {
        return fail(
          "REFERENCE_INVALID",
          `reference ${contract.referenceType}/${role.role} of ${atom.key.atomUid} violates cardinality`
        )
      }
    }
  }

  const semanticArity = atom.references.filter(
    ({ referenceType }) =>
      referenceType !== HSWM_SUPERSEDES_REFERENCE_TYPE
  ).length
  if (kind.form === "RELATION" && semanticArity < kind.minimumArity) {
    return fail(
      "REFERENCE_INVALID",
      `relation atom ${atom.key.atomUid} is below its declared arity`
    )
  }

  return validateRevision(kind, atom, currentAtoms)
}

const validateAcyclicProvenance = (
  atoms: ReadonlyArray<CanonicalAtomV2>
): Either.Either<void, CanonicalAtomV2Error> => {
  const atomByKey = new Map(
    atoms.map((atom) => [canonicalAtomV2KeyId(atom.key), atom] as const)
  )
  const visiting = new Set<string>()
  const visited = new Set<string>()

  const visit = (
    atom: CanonicalAtomV2
  ): Either.Either<void, CanonicalAtomV2Error> => {
    const id = canonicalAtomV2KeyId(atom.key)
    if (visiting.has(id)) {
      return fail(
        "PROVENANCE_INVALID",
        `canonical provenance contains a cycle at ${atom.key.atomUid}`
      )
    }
    if (visited.has(id)) return Either.right(undefined)
    visiting.add(id)
    if (atom.provenance.sourceRef !== null) {
      const source = atomByKey.get(
        canonicalAtomV2KeyId(atom.provenance.sourceRef)
      )
      if (source !== undefined) {
        const result = visit(source)
        if (Either.isLeft(result)) return result
      }
    }
    visiting.delete(id)
    visited.add(id)
    return Either.right(undefined)
  }

  for (const atom of atoms) {
    const result = visit(atom)
    if (Either.isLeft(result)) return result
  }
  return Either.right(undefined)
}

const IDENTIFIER_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/

export const validateCanonicalAtomV2State = (
  schema: HSWMCanonicalSchemaV2,
  input: unknown
): Either.Either<CanonicalAtomV2State, CanonicalAtomV2Error> => {
  const schemaValidation = validateHSWMCanonicalSchemaV2(schema)
  if (Either.isLeft(schemaValidation)) {
    return Either.left(schemaValidation.left)
  }
  if (typeof input !== "object" || input === null) {
    return fail("STATE_INVALID", "state must be a non-null object")
  }
  const state = input as Partial<CanonicalAtomV2State>
  if (
    state.schemaVersion !== schemaValidation.right.schemaVersion ||
    !Number.isSafeInteger(state.revision) ||
    (state.revision ?? -1) < 0 ||
    typeof state.bootstrapClosed !== "boolean" ||
    !Array.isArray(state.atoms) ||
    !Array.isArray(state.acceptedTransitionIds) ||
    state.acceptedTransitionIds.some(
      (transitionId) =>
        typeof transitionId !== "string" ||
        !IDENTIFIER_PATTERN.test(transitionId)
    )
  ) {
    return fail(
      "STATE_INVALID",
      "state header does not satisfy the active schema boundary"
    )
  }
  if (
    state.revision !== state.acceptedTransitionIds.length ||
    state.bootstrapClosed !== (state.revision > 0) ||
    hasDuplicates(state.acceptedTransitionIds)
  ) {
    return fail(
      "STATE_INVALID",
      "state revision and accepted-transition history are inconsistent"
    )
  }

  const atoms: Array<CanonicalAtomV2> = []
  for (const inputAtom of state.atoms) {
    const decoded = Schema.decodeUnknownEither(CanonicalAtomV2Schema, {
      onExcessProperty: "error"
    })(inputAtom)
    if (Either.isLeft(decoded)) {
      return fail(
        "STATE_INVALID",
        "state contains an atom outside the strict v2 structural contract"
      )
    }
    atoms.push(decoded.right)
  }
  const sortedAtoms = atoms.sort((left, right) =>
    compareKeys(left.key, right.key)
  )
  const atomIds = sortedAtoms.map(({ key }) => canonicalAtomV2KeyId(key))
  if (hasDuplicates(atomIds)) {
    return fail("STATE_INVALID", "state contains duplicate canonical keys")
  }
  const atomIdSet = new Set(atomIds)
  const atomByKey = new Map(
    sortedAtoms.map((atom) => [canonicalAtomV2KeyId(atom.key), atom] as const)
  )
  const prior: Array<CanonicalAtomV2> = []
  for (const atom of sortedAtoms) {
    const validation = validateAtom(
      schemaValidation.right,
      atom,
      prior,
      atomByKey,
      atomIdSet,
      atomIdSet
    )
    if (Either.isLeft(validation)) {
      return fail(
        "STATE_INVALID",
        `state atom ${atom.key.atomUid} violates ${validation.left.code}: ${validation.left.detail}`
      )
    }
    prior.push(atom)
  }
  const provenance = validateAcyclicProvenance(sortedAtoms)
  if (Either.isLeft(provenance)) {
    return fail("STATE_INVALID", provenance.left.detail)
  }

  return Either.right(
    snapshotCanonicalAtomV2State({
      schemaVersion: state.schemaVersion,
      revision: state.revision,
      bootstrapClosed: state.bootstrapClosed,
      atoms: sortedAtoms,
      acceptedTransitionIds: state.acceptedTransitionIds
    })
  )
}

const evolveValidatedCanonicalAtomsV2 = (
  schema: HSWMCanonicalSchemaV2,
  state: CanonicalAtomV2State,
  command: CommitCanonicalAtomsV2Command
): Either.Either<CanonicalAtomV2State, CanonicalAtomV2Error> => {
  if (
    state.schemaVersion !== schema.schemaVersion ||
    command.schemaVersion !== schema.schemaVersion
  ) {
    return fail(
      "SCHEMA_VERSION_MISMATCH",
      "schema, state, and transition must name one schema version"
    )
  }
  if (command.expectedStateRevision !== state.revision) {
    return fail(
      "STATE_REVISION_CONFLICT",
      `expected state revision ${command.expectedStateRevision}, actual ${state.revision}`
    )
  }
  if (state.revision >= Number.MAX_SAFE_INTEGER) {
    return fail("STATE_INVALID", "state revision is exhausted")
  }
  if (state.acceptedTransitionIds.includes(command.transitionId)) {
    return fail(
      "TRANSITION_DUPLICATE",
      `transition ${command.transitionId} was already accepted`
    )
  }
  if (!isCanonicalInstant(command.decidedAt)) {
    return fail(
      "PROVENANCE_INVALID",
      "decidedAt must be a real canonical UTC millisecond instant"
    )
  }

  const existingIds = state.atoms.map(({ key }) => canonicalAtomV2KeyId(key))
  if (hasDuplicates(existingIds)) {
    return fail("STATE_INVALID", "state contains duplicate canonical keys")
  }
  const existingKeyIds = new Set(existingIds)
  const readSetIds = command.readSet.map(canonicalAtomV2KeyId)
  if (hasDuplicates(readSetIds)) {
    return fail("READ_SET_INVALID", "read set contains a duplicate key")
  }
  if (readSetIds.some((id) => !existingKeyIds.has(id))) {
    return fail("READ_SET_INVALID", "read set contains a missing atom")
  }
  const readSet = new Set(readSetIds)

  const writeIds = command.writes.map(({ key }) => canonicalAtomV2KeyId(key))
  if (hasDuplicates(writeIds)) {
    return fail("ATOM_KEY_DUPLICATE", "write set repeats a canonical key")
  }
  if (writeIds.some((id) => existingKeyIds.has(id))) {
    return fail(
      "ATOM_KEY_DUPLICATE",
      "immutable canonical keys cannot be overwritten"
    )
  }
  const logicalWrites = command.writes.map(({ key }) => logicalAtomId(key))
  if (hasDuplicates(logicalWrites)) {
    return fail(
      "REVISION_INVALID",
      "one transition may write at most one revision of a logical atom"
    )
  }

  const atomByKey = new Map<string, CanonicalAtomV2>()
  for (const atom of [...state.atoms, ...command.writes]) {
    atomByKey.set(canonicalAtomV2KeyId(atom.key), atom)
  }

  if (command.traceRef !== null) {
    return fail(
      "TRACE_UNSUPPORTED",
      "trace admission requires a later sealed-trajectory contract"
    )
  }
  if (
    state.bootstrapClosed &&
    command.writes.some(({ provenance }) => provenance.mode === "BOOTSTRAP")
  ) {
    return fail(
      "PROVENANCE_INVALID",
      "bootstrap provenance is permanently closed after the genesis commit"
    )
  }

  for (const atom of command.writes) {
    const validation = validateAtom(
      schema,
      atom,
      state.atoms,
      atomByKey,
      existingKeyIds,
      readSet
    )
    if (Either.isLeft(validation)) return Either.left(validation.left)
  }

  const provenance = validateAcyclicProvenance([
    ...state.atoms,
    ...command.writes
  ])
  if (Either.isLeft(provenance)) return Either.left(provenance.left)

  return Either.right(
    snapshotCanonicalAtomV2State({
      schemaVersion: state.schemaVersion,
      revision: state.revision + 1,
      bootstrapClosed: true,
      atoms: [...state.atoms, ...command.writes].sort((left, right) =>
        compareKeys(left.key, right.key)
      ),
      acceptedTransitionIds: [
        ...state.acceptedTransitionIds,
        command.transitionId
      ]
    })
  )
}

export const evolveCanonicalAtomsV2 = (
  schema: HSWMCanonicalSchemaV2,
  state: CanonicalAtomV2State,
  command: CommitCanonicalAtomsV2Command
): Either.Either<CanonicalAtomV2State, CanonicalAtomV2Error> => {
  const schemaValidation = validateHSWMCanonicalSchemaV2(schema)
  if (Either.isLeft(schemaValidation)) {
    return Either.left(schemaValidation.left)
  }
  const stateValidation = validateCanonicalAtomV2State(
    schemaValidation.right,
    state
  )
  if (Either.isLeft(stateValidation)) {
    return Either.left(stateValidation.left)
  }
  const decodedCommand = Schema.decodeUnknownEither(
    CommitCanonicalAtomsV2CommandSchema,
    { onExcessProperty: "error" }
  )(command)
  if (Either.isLeft(decodedCommand)) {
    return fail(
      "TRANSITION_INVALID",
      "transition does not satisfy the strict v2 structural contract"
    )
  }
  return evolveValidatedCanonicalAtomsV2(
    schemaValidation.right,
    stateValidation.right,
    decodedCommand.right
  )
}

export const makeCanonicalAtomV2AcceptedReceipt = (
  command: CommitCanonicalAtomsV2Command,
  previousStateRevision: number,
  nextStateRevision: number
): CanonicalAtomV2EffectReceipt =>
  snapshotCanonicalAtomV2Receipt({
    _tag: "CanonicalAtomV2EffectReceipt",
    contractVersion: HSWM_CANONICAL_RECEIPT_V2_CONTRACT_VERSION,
    transitionId: command.transitionId,
    schemaVersion: command.schemaVersion,
    previousStateRevision,
    nextStateRevision,
    readSet: [...command.readSet].sort(compareKeys),
    writeSet: command.writes.map(({ key }) => key).sort(compareKeys),
    traceRef: command.traceRef,
    guard: {
      schema: "PASSED",
      ownerTotality: "PASSED",
      references: "PASSED",
      revision: "PASSED",
      permission: "REFERENCE_GRANT_MATCHED_NOT_CANONICAL_PERMIT"
    },
    actorClaim: command.actorClaim,
    authorizationRef: command.authorizationRef,
    scope: command.scope,
    decidedAt: command.decidedAt,
    decision: "ACCEPTED",
    provenanceSha256: command.provenanceSha256
  })
