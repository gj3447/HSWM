/**
 * Pure W0/four-fork byte-identity boundary.
 *
 * The caller supplies both an exact canonical manifest and a content-addressed
 * byte map. This checker verifies those bytes but does not recover a durable
 * runtime, enforce process isolation, assign arms, restore state, or issue a
 * Permit or scientific terminal.
 */
import { Data, Either, Schema } from "effect"

import {
  CanonicalAtomV2ContentDescriptorSchema,
  makeCanonicalAtomV2ContentDescriptor,
  sameCanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2ContentDescriptor
} from "./canonical-atom-v2-content.js"
import {
  canonicalJsonBytes,
  decodeCanonicalJsonBytes
} from "./canonical-atom-v2-json.js"

export const DNRD5_W0_FORK_V1 = "hswm-dnrd5-w0-four-fork-identity/v1" as const
export const DNRD5_W0_STATUS =
  "CALLER_SUPPLIED_CONTENT_MAP_NOT_DURABLE_RECOVERY_OR_ISOLATION_PROOF_RESTORE_AND_PROJECTION_PENDING" as const

const Identifier = Schema.String.pipe(
  Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/)
)
const BlockId = Schema.String.pipe(
  Schema.pattern(/^DNRD5-BLOCK-(?:0(?:00[1-9]|0[1-9]\d|[12]\d{2})|0300)$/)
)
const OpaqueForkId = Schema.String.pipe(
  Schema.pattern(/^opaque:fork:[a-z0-9][a-z0-9._/-]{0,127}$/)
)

const W0Snapshot = Schema.Struct({
  w0Id: Identifier,
  state: CanonicalAtomV2ContentDescriptorSchema,
  behaviorReadset: CanonicalAtomV2ContentDescriptorSchema,
  journalHead: CanonicalAtomV2ContentDescriptorSchema,
  projectionPolicy: CanonicalAtomV2ContentDescriptorSchema
})

const Fork = Schema.Struct({
  opaqueForkId: OpaqueForkId,
  w0Id: Identifier,
  state: CanonicalAtomV2ContentDescriptorSchema,
  behaviorReadset: CanonicalAtomV2ContentDescriptorSchema,
  isolationReceipt: CanonicalAtomV2ContentDescriptorSchema,
  assignmentStatus: Schema.Literal("UNASSIGNED")
})

const Manifest = Schema.Struct({
  _tag: Schema.Literal("Dnrd5W0ForkManifest"),
  contractVersion: Schema.Literal(DNRD5_W0_FORK_V1),
  blockId: BlockId,
  w0: W0Snapshot,
  forks: Schema.Array(Fork).pipe(Schema.minItems(4), Schema.maxItems(4)),
  terminal: Schema.Literal(
    "CALLER_SUPPLIED_CONTENT_MAP_NOT_DURABLE_RECOVERY_OR_ISOLATION_PROOF"
  )
})

export type Dnrd5W0ForkManifest = Schema.Schema.Type<typeof Manifest>

export type Dnrd5W0ErrorCode =
  | "BYTES_INVALID"
  | "MANIFEST_INVALID"
  | "CONTENT_MISSING"
  | "DESCRIPTOR_MISMATCH"
  | "FORK_IDENTITY_INVALID"
  | "W0_BYTE_IDENTITY_INVALID"

export class Dnrd5W0Error extends Data.TaggedError("Dnrd5W0Error")<{
  readonly code: Dnrd5W0ErrorCode
  readonly detail: string
}> {}

const fail = (code: Dnrd5W0ErrorCode, detail: string) =>
  Either.left(new Dnrd5W0Error({ code, detail }))

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((byte, index) => byte === right[index])

const armMaterial = (value: string): boolean => {
  const normalized = value.toLowerCase().replace(/[^a-z0-9]/g, "")
  return [
    "active",
    "outcomeindependentsham",
    "delayednocredit",
    "exactw0rollback",
    "armlabel"
  ].some((token) => normalized.includes(token))
}

const deepSnapshot = <A>(value: A): A => {
  const cloned = structuredClone(value)
  const freeze = (candidate: unknown): void => {
    if (typeof candidate === "object" && candidate !== null && !Object.isFrozen(candidate)) {
      Object.freeze(candidate)
      for (const nested of Object.values(candidate)) freeze(nested)
    }
  }
  freeze(cloned)
  return cloned
}

const verifiedContent = (
  descriptor: CanonicalAtomV2ContentDescriptor,
  content: ReadonlyMap<string, Uint8Array>,
  label: string
): Either.Either<Uint8Array, Dnrd5W0Error> => {
  const bytes = content.get(descriptor.sha256)
  if (!(bytes instanceof Uint8Array)) {
    return fail("CONTENT_MISSING", `${label} content is absent at its exact SHA-256 key`)
  }
  const described = makeCanonicalAtomV2ContentDescriptor(descriptor.mediaType, bytes)
  if (
    Either.isLeft(described) ||
    !sameCanonicalAtomV2ContentDescriptor(descriptor, described.right)
  ) {
    return fail("DESCRIPTOR_MISMATCH", `${label} bytes do not match their descriptor`)
  }
  return Either.right(Uint8Array.from(bytes))
}

export interface Dnrd5ValidatedW0ForkIdentity {
  readonly manifest: Dnrd5W0ForkManifest
  readonly w0StateSha256: string
  readonly w0BehaviorReadsetSha256: string
  readonly status: typeof DNRD5_W0_STATUS
  readonly terminal: "NOT_ARM_ASSIGNMENT_NOT_RESTORE_NOT_PROJECTION_NOT_EXECUTION_NOT_SCIENCE"
}

export const validateDnrd5W0ForkManifestBytes = (
  manifestBytes: Uint8Array,
  content: ReadonlyMap<string, Uint8Array>
): Either.Either<Dnrd5ValidatedW0ForkIdentity, Dnrd5W0Error> => {
  if (!(manifestBytes instanceof Uint8Array) || !(content instanceof Map)) {
    return fail("BYTES_INVALID", "manifest must be Uint8Array and content must be a Map")
  }
  const parsed = decodeCanonicalJsonBytes(manifestBytes)
  if (Either.isLeft(parsed)) {
    return fail("BYTES_INVALID", "manifest is not strict canonical JSON")
  }
  const canonical = canonicalJsonBytes(parsed.right)
  if (Either.isLeft(canonical) || !sameBytes(canonical.right, manifestBytes)) {
    return fail("BYTES_INVALID", "manifest bytes are not exact compact canonical JSON")
  }
  const decoded = Schema.decodeUnknownEither(Manifest, {
    onExcessProperty: "error"
  })(parsed.right)
  if (Either.isLeft(decoded)) {
    return fail("MANIFEST_INVALID", "manifest has missing, extra, or malformed fields")
  }
  const manifest = decoded.right
  const forkIds = manifest.forks.map(({ opaqueForkId }) => opaqueForkId)
  if (
    new Set(forkIds).size !== 4 ||
    forkIds.some(armMaterial) ||
    !forkIds.every((forkId, index) => index === 0 || forkIds[index - 1]! < forkId)
  ) {
    return fail(
      "FORK_IDENTITY_INVALID",
      "four fork IDs must be distinct, arm-free, and canonically ordered"
    )
  }

  const w0State = verifiedContent(manifest.w0.state, content, "W0 state")
  if (Either.isLeft(w0State)) return Either.left(w0State.left)
  const w0Readset = verifiedContent(
    manifest.w0.behaviorReadset,
    content,
    "W0 behavior readset"
  )
  if (Either.isLeft(w0Readset)) return Either.left(w0Readset.left)
  const journal = verifiedContent(manifest.w0.journalHead, content, "W0 journal head")
  if (Either.isLeft(journal)) return Either.left(journal.left)
  const policy = verifiedContent(
    manifest.w0.projectionPolicy,
    content,
    "W0 projection policy"
  )
  if (Either.isLeft(policy)) return Either.left(policy.left)

  for (const fork of manifest.forks) {
    if (fork.w0Id !== manifest.w0.w0Id) {
      return fail("FORK_IDENTITY_INVALID", "fork binds a different W0 identity")
    }
    const state = verifiedContent(fork.state, content, `${fork.opaqueForkId} state`)
    if (Either.isLeft(state)) return Either.left(state.left)
    const readset = verifiedContent(
      fork.behaviorReadset,
      content,
      `${fork.opaqueForkId} behavior readset`
    )
    if (Either.isLeft(readset)) return Either.left(readset.left)
    const isolation = verifiedContent(
      fork.isolationReceipt,
      content,
      `${fork.opaqueForkId} isolation receipt`
    )
    if (Either.isLeft(isolation)) return Either.left(isolation.left)
    if (
      !sameCanonicalAtomV2ContentDescriptor(fork.state, manifest.w0.state) ||
      !sameCanonicalAtomV2ContentDescriptor(
        fork.behaviorReadset,
        manifest.w0.behaviorReadset
      ) ||
      !sameBytes(state.right, w0State.right) ||
      !sameBytes(readset.right, w0Readset.right)
    ) {
      return fail(
        "W0_BYTE_IDENTITY_INVALID",
        "every pre-assignment fork state and behavior readset must be byte-identical to W0"
      )
    }
  }

  return Either.right(
    deepSnapshot({
      manifest,
      w0StateSha256: manifest.w0.state.sha256,
      w0BehaviorReadsetSha256: manifest.w0.behaviorReadset.sha256,
      status: DNRD5_W0_STATUS,
      terminal:
        "NOT_ARM_ASSIGNMENT_NOT_RESTORE_NOT_PROJECTION_NOT_EXECUTION_NOT_SCIENCE"
    })
  )
}
