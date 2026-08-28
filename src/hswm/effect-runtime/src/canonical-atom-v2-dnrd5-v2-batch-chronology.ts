/**
 * DNRD-5 successor-schema atomic-commit topology instrument.
 *
 * This does not serialise a command's writes into publication events.  It
 * verifies the dependency graph inside one already-decoded generic-v2 commit,
 * while requiring every dependency outside that batch to have been read from
 * the pre-commit state.  A later commit (for example an exact-W0 restore) is
 * therefore a separate invocation with the preceding committed state.
 */
import { Data, Either } from "effect"

import {
  evolveCanonicalAtomsV2,
  type CanonicalAtomV2State
} from "./canonical-atom-v2-domain.js"
import {
  canonicalAtomV2KeyId,
  type CanonicalAtomV2,
  type CommitCanonicalAtomsV2Command,
  type HSWMCanonicalSchemaV2
} from "./canonical-atom-v2-schema.js"
import { canonicalJsonSha256 } from "./canonical-atom-v2-json.js"
import { validateDnrd5V2CanonicalSchema } from "./canonical-atom-v2-dnrd5-v2-schema.js"

export const DNRD5_V2_ATOMIC_BATCH_TOPOLOGY_V1 =
  "hswm-dnrd5-v2-atomic-batch-topology/v1" as const

/** Explicit boundary: this is a graph primitive, not the effect protocol. */
export const DNRD5_V2_ATOMIC_BATCH_TOPOLOGY_BOUNDARY = Object.freeze({
  validates: "ONE_GENERIC_V2_ATOMIC_COMMAND_TYPED_AND_PROVENANCE_DEPENDENCY_DAG",
  doesNotValidate: Object.freeze([
    "PHASE_OR_WRITE_GRAMMAR",
    "POSTCOMMIT_DURABLE_RECEIPT_BINDING",
    "ARM_OR_BLOCK_SCOPE",
    "CRASH_OR_REPLAY_BEHAVIOR",
    "PROBE_GATE",
    "PERMIT_OR_OCCURRENCE"
  ])
} as const)

export type Dnrd5V2AtomicBatchChronologyErrorCode =
  | "SCHEMA_INVALID"
  | "GENERIC_KERNEL_REJECTED"
  | "DUPLICATE_WRITE"
  | "DUPLICATE_READ"
  | "DUPLICATE_TYPED_REFERENCE"
  | "SELF_DEPENDENCY"
  | "CROSS_BATCH_FORWARD_REFERENCE"
  | "MISSING_EXTERNAL_READ"
  | "DEPENDENCY_CYCLE"
  | "TOPOLOGY_HASH_INVALID"

export class Dnrd5V2AtomicBatchChronologyError extends Data.TaggedError(
  "Dnrd5V2AtomicBatchChronologyError"
)<{
  readonly code: Dnrd5V2AtomicBatchChronologyErrorCode
  readonly detail: string
}> {}

export interface Dnrd5V2AtomicBatchChronology {
  /** Canonical-key order after deterministic topological sorting, not write order. */
  readonly topologyAtomKeyIds: ReadonlyArray<string>
  /** Every typed/provenance dependency, including dependencies in pre-state. */
  readonly dependencyEdges: ReadonlyArray<Dnrd5V2AtomicBatchDependencyEdge>
  /** SHA-256 of the schema/version/transition-bound topology projection. */
  readonly topologySha256: string
  /** The generic kernel's independently validated next state. */
  readonly nextState: CanonicalAtomV2State
}

export interface Dnrd5V2AtomicBatchDependencyEdge {
  readonly dependentAtomKeyId: string
  readonly dependencyAtomKeyId: string
  readonly edgeKind: "TYPED_REFERENCE" | "PROVENANCE"
  readonly referenceType: string | null
  readonly role: string | null
}

const fail = (
  code: Dnrd5V2AtomicBatchChronologyErrorCode,
  detail: string
): Either.Either<never, Dnrd5V2AtomicBatchChronologyError> =>
  Either.left(new Dnrd5V2AtomicBatchChronologyError({ code, detail }))

const duplicate = (values: ReadonlyArray<string>): string | undefined => {
  const seen = new Set<string>()
  for (const value of values) {
    if (seen.has(value)) return value
    seen.add(value)
  }
  return undefined
}

const dependenciesFor = (atom: CanonicalAtomV2) =>
  [
    ...atom.references.map(({ referenceType, role, target }) => ({
      id: canonicalAtomV2KeyId(target), source: "typed reference" as const,
      edgeKind: "TYPED_REFERENCE" as const, referenceType, role
    })),
    ...(atom.provenance.sourceRef === null
      ? []
      : [{
          id: canonicalAtomV2KeyId(atom.provenance.sourceRef),
          source: "provenance" as const, edgeKind: "PROVENANCE" as const,
          referenceType: null, role: null
        }])
  ]

const compareEdges = (
  left: Dnrd5V2AtomicBatchDependencyEdge,
  right: Dnrd5V2AtomicBatchDependencyEdge
): number => {
  const leftProjection = `${left.dependentAtomKeyId}\u0000${left.dependencyAtomKeyId}\u0000${left.edgeKind}\u0000${left.referenceType ?? ""}\u0000${left.role ?? ""}`
  const rightProjection = `${right.dependentAtomKeyId}\u0000${right.dependencyAtomKeyId}\u0000${right.edgeKind}\u0000${right.referenceType ?? ""}\u0000${right.role ?? ""}`
  return leftProjection < rightProjection ? -1 : leftProjection > rightProjection ? 1 : 0
}

/**
 * Validates one atomic command against the exact successor schema.
 *
 * The generic kernel remains authoritative for all generic-v2 invariants. This
 * instrument adds an explicit, order-independent topology proof for typed and
 * provenance dependencies; it does not provide a Permit or publish a command.
 */
export const validateDnrd5V2AtomicBatchChronology = (
  schema: HSWMCanonicalSchemaV2,
  preState: CanonicalAtomV2State,
  command: CommitCanonicalAtomsV2Command
): Either.Either<Dnrd5V2AtomicBatchChronology, Dnrd5V2AtomicBatchChronologyError> => {
  const exactSchema = validateDnrd5V2CanonicalSchema(schema)
  if (Either.isLeft(exactSchema)) {
    return fail("SCHEMA_INVALID", "atomic chronology requires the exact DNRD-5 successor schema")
  }

  const writeIds = command.writes.map(({ key }) => canonicalAtomV2KeyId(key))
  const repeatedWrite = duplicate(writeIds)
  if (repeatedWrite !== undefined) return fail("DUPLICATE_WRITE", `write batch repeats ${repeatedWrite}`)
  const writeIdSet = new Set(writeIds)

  const readIds = command.readSet.map(canonicalAtomV2KeyId)
  const repeatedRead = duplicate(readIds)
  if (repeatedRead !== undefined) return fail("DUPLICATE_READ", `read set repeats ${repeatedRead}`)
  const readIdSet = new Set(readIds)
  const preIds = new Set(preState.atoms.map(({ key }) => canonicalAtomV2KeyId(key)))

  // `dependency -> dependent`, so Kahn's algorithm emits dependencies first.
  const successors = new Map<string, Set<string>>(writeIds.map((id) => [id, new Set<string>()]))
  const indegree = new Map<string, number>(writeIds.map((id) => [id, 0]))
  const dependencyEdges: Dnrd5V2AtomicBatchDependencyEdge[] = []
  for (const atom of command.writes) {
    const atomId = canonicalAtomV2KeyId(atom.key)
    const typedIds = atom.references.map(({ referenceType, role, target }) =>
      `${referenceType}|${role}|${canonicalAtomV2KeyId(target)}`
    )
    const repeatedTyped = duplicate(typedIds)
    if (repeatedTyped !== undefined) {
      return fail("DUPLICATE_TYPED_REFERENCE", `atom ${atomId} repeats ${repeatedTyped}`)
    }
    for (const dependency of dependenciesFor(atom)) {
      dependencyEdges.push(Object.freeze({
        dependentAtomKeyId: atomId,
        dependencyAtomKeyId: dependency.id,
        edgeKind: dependency.edgeKind,
        referenceType: dependency.referenceType,
        role: dependency.role
      }))
      if (dependency.id === atomId) {
        return fail("SELF_DEPENDENCY", `atom ${atomId} has a self ${dependency.source}`)
      }
      if (writeIdSet.has(dependency.id)) {
        const targets = successors.get(dependency.id)!
        if (!targets.has(atomId)) {
          targets.add(atomId)
          indegree.set(atomId, indegree.get(atomId)! + 1)
        }
        continue
      }
      if (!preIds.has(dependency.id)) {
        return fail(
          "CROSS_BATCH_FORWARD_REFERENCE",
          `atom ${atomId} ${dependency.source} targets ${dependency.id}, absent from pre-state and batch`
        )
      }
      if (!readIdSet.has(dependency.id)) {
        return fail(
          "MISSING_EXTERNAL_READ",
          `atom ${atomId} ${dependency.source} targets pre-state atom ${dependency.id} outside command readSet`
        )
      }
    }
  }

  const ready = [...writeIds.filter((id) => indegree.get(id) === 0)].sort()
  const topology: string[] = []
  while (ready.length > 0) {
    const current = ready.shift()!
    topology.push(current)
    for (const dependent of [...successors.get(current)!].sort()) {
      const next = indegree.get(dependent)! - 1
      indegree.set(dependent, next)
      if (next === 0) {
        ready.push(dependent)
        ready.sort()
      }
    }
  }
  if (topology.length !== writeIds.length) {
    const blocked = writeIds.filter((id) => !topology.includes(id)).sort()
    return fail("DEPENDENCY_CYCLE", `typed/provenance batch dependency cycle: ${blocked.join(",")}`)
  }

  const digest = canonicalJsonSha256({
    contractVersion: DNRD5_V2_ATOMIC_BATCH_TOPOLOGY_V1,
    schemaVersion: schema.schemaVersion,
    transitionId: command.transitionId,
    topologyAtomKeyIds: topology,
    dependencyEdges: dependencyEdges.sort(compareEdges)
  })
  if (Either.isLeft(digest)) return fail("TOPOLOGY_HASH_INVALID", digest.left.detail)
  // The topology calculation is deliberately not an alternate admission
  // kernel.  The generic kernel must independently accept precisely this
  // command and yields the state to which a later atomic batch may refer.
  const evolved = evolveCanonicalAtomsV2(schema, preState, command)
  if (Either.isLeft(evolved)) {
    return fail("GENERIC_KERNEL_REJECTED", `${evolved.left.code}: ${evolved.left.detail}`)
  }
  return Either.right(Object.freeze({
    topologyAtomKeyIds: Object.freeze(topology),
    dependencyEdges: Object.freeze(dependencyEdges.sort(compareEdges)),
    topologySha256: digest.right,
    nextState: evolved.right
  }))
}
