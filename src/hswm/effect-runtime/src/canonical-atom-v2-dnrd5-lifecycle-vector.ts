/**
 * Cross-language DNRD-5 lifecycle rehearsal validator.
 *
 * This joins one exact canonical vector to the TypeScript lifecycle checker
 * and rederives every synthetic artifact descriptor from its actual content.
 * It is not a production block, Permit, model call, occurrence, or result.
 */
import { createHash } from "node:crypto"

import { Data, Either, Schema } from "effect"

import {
  makeCanonicalAtomV2ContentDescriptor,
  sameCanonicalAtomV2ContentDescriptor
} from "./canonical-atom-v2-content.js"
import {
  HSWM_CANONICAL_JSON_V1_CONTRACT_VERSION,
  canonicalJsonBytes,
  canonicalJsonSha256,
  decodeCanonicalJsonBytes
} from "./canonical-atom-v2-json.js"
import {
  validateDnrd5SealedBlockLifecycle,
  type Dnrd5LifecycleArtifact,
  type Dnrd5SealedBlockLifecycle
} from "./canonical-atom-v2-dnrd5-lifecycle.js"
import { DNRD5_ARM_LABELS } from "./canonical-atom-v2-dnrd5-schema.js"

export const DNRD5_LIFECYCLE_VECTOR_V1 =
  "hswm-dnrd5-lifecycle-cross-language-vector/v1" as const
export const DNRD5_LIFECYCLE_VECTOR_FIXTURE_SCOPE =
  "ONE_SYNTHETIC_BLOCK_DESCRIPTOR_REHEARSAL_ONLY" as const
export const DNRD5_LIFECYCLE_VECTOR_CONTENT_SCOPE =
  "SYNTHETIC_DESCRIPTOR_CONTENT_ONLY" as const
export const DNRD5_LIFECYCLE_VECTOR_TERMINAL =
  "SYNTHETIC_LIFECYCLE_REHEARSAL_ONLY_NOT_EXECUTION_NOT_OCCURRENCE_NOT_INTEGRITY_EVIDENCE_NOT_SCIENTIFIC_RESULT" as const
export const DNRD5_LIFECYCLE_VECTOR_CONTENT_MEDIA_TYPE =
  "application/vnd.hswm.dnrd5.synthetic-lifecycle-artifact-v1+json" as const

const Identifier = Schema.String.pipe(
  Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/)
)
const Arm = Schema.Literal(...DNRD5_ARM_LABELS)
const ContentCore = Schema.Struct({
  _tag: Schema.Literal("Dnrd5SyntheticLifecycleArtifactContent"),
  arm: Schema.NullOr(Arm),
  artifactId: Identifier,
  fixtureScope: Schema.Literal(DNRD5_LIFECYCLE_VECTOR_CONTENT_SCOPE),
  kind: Identifier
})
const ContentRow = Schema.Struct({ artifactId: Identifier, content: ContentCore })
const Vector = Schema.Struct({
  _tag: Schema.Literal("Dnrd5LifecycleCrossLanguageVector"),
  contractVersion: Schema.Literal(DNRD5_LIFECYCLE_VECTOR_V1),
  canonicalJsonVersion: Schema.Literal(HSWM_CANONICAL_JSON_V1_CONTRACT_VERSION),
  fixtureScope: Schema.Literal(DNRD5_LIFECYCLE_VECTOR_FIXTURE_SCOPE),
  expectedTerminal: Schema.Literal(DNRD5_LIFECYCLE_VECTOR_TERMINAL),
  artifactContents: Schema.Array(ContentRow),
  lifecycle: Schema.Unknown
})

export type Dnrd5LifecycleCrossLanguageVector = Schema.Schema.Type<typeof Vector>
export type Dnrd5LifecycleVectorErrorCode =
  | "BYTES_INVALID"
  | "VECTOR_INVALID"
  | "LIFECYCLE_INVALID"
  | "CONTENT_CLOSURE_INVALID"
  | "DESCRIPTOR_MISMATCH"

export class Dnrd5LifecycleVectorError extends Data.TaggedError(
  "Dnrd5LifecycleVectorError"
)<{
  readonly code: Dnrd5LifecycleVectorErrorCode
  readonly detail: string
}> {}

const fail = (code: Dnrd5LifecycleVectorErrorCode, detail: string) =>
  Either.left(new Dnrd5LifecycleVectorError({ code, detail }))

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((byte, index) => byte === right[index])

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

export interface Dnrd5ValidatedLifecycleVector {
  readonly vector: Omit<Dnrd5LifecycleCrossLanguageVector, "lifecycle"> & {
    readonly lifecycle: Dnrd5SealedBlockLifecycle
  }
  readonly vectorSha256: string
  readonly lifecycleSha256: string
  readonly artifactCount: number
  readonly generationCallCount: 9
  readonly status: "CROSS_LANGUAGE_SYNTHETIC_LIFECYCLE_AND_CONTENT_DESCRIPTORS_REDERIVED"
  readonly terminal: typeof DNRD5_LIFECYCLE_VECTOR_TERMINAL
  readonly productionContentValidated: false
  readonly occurrenceEstablished: false
  readonly scientificTerminalIssued: false
}

export const validateDnrd5LifecycleVectorBytes = (
  raw: Uint8Array
): Either.Either<Dnrd5ValidatedLifecycleVector, Dnrd5LifecycleVectorError> => {
  if (!(raw instanceof Uint8Array)) {
    return fail("BYTES_INVALID", "lifecycle vector must be exact Uint8Array bytes")
  }
  const parsed = decodeCanonicalJsonBytes(raw)
  if (Either.isLeft(parsed)) {
    return fail("BYTES_INVALID", "lifecycle vector is not strict bounded UTF-8 JSON")
  }
  const canonical = canonicalJsonBytes(parsed.right)
  if (Either.isLeft(canonical) || !sameBytes(canonical.right, raw)) {
    return fail("BYTES_INVALID", "lifecycle vector is not exact canonical-json/v1")
  }
  const decoded = Schema.decodeUnknownEither(Vector, {
    onExcessProperty: "error"
  })(parsed.right)
  if (Either.isLeft(decoded)) {
    return fail("VECTOR_INVALID", "lifecycle vector root has missing, extra, or malformed fields")
  }
  const vector = decoded.right
  const lifecycle = validateDnrd5SealedBlockLifecycle(vector.lifecycle)
  if (Either.isLeft(lifecycle)) {
    return fail("LIFECYCLE_INVALID", lifecycle.left.detail)
  }

  const artifacts: ReadonlyArray<Dnrd5LifecycleArtifact> =
    lifecycle.right.events.flatMap((event) => event.artifacts)
  if (vector.artifactContents.length !== artifacts.length) {
    return fail("CONTENT_CLOSURE_INVALID", "artifact content rows do not close every lifecycle artifact")
  }
  const seen = new Set<string>()
  for (const [index, artifact] of artifacts.entries()) {
    const row = vector.artifactContents[index]
    if (
      row === undefined ||
      seen.has(row.artifactId) ||
      row.artifactId !== artifact.artifactId ||
      row.content.artifactId !== artifact.artifactId ||
      row.content.kind !== artifact.kind ||
      row.content.arm !== artifact.arm
    ) {
      return fail(
        "CONTENT_CLOSURE_INVALID",
        "artifact content identity, order, kind, or arm does not match the lifecycle"
      )
    }
    seen.add(row.artifactId)
    const bytes = canonicalJsonBytes(row.content)
    if (Either.isLeft(bytes)) {
      return fail("CONTENT_CLOSURE_INVALID", "synthetic artifact content is not canonical JSON")
    }
    const descriptor = makeCanonicalAtomV2ContentDescriptor(
      DNRD5_LIFECYCLE_VECTOR_CONTENT_MEDIA_TYPE,
      bytes.right
    )
    if (
      Either.isLeft(descriptor) ||
      !sameCanonicalAtomV2ContentDescriptor(descriptor.right, artifact.content)
    ) {
      return fail(
        "DESCRIPTOR_MISMATCH",
        `artifact ${artifact.artifactId} descriptor does not match its actual bytes`
      )
    }
  }

  const lifecycleSha256 = canonicalJsonSha256(lifecycle.right)
  if (Either.isLeft(lifecycleSha256)) {
    return fail("LIFECYCLE_INVALID", "validated lifecycle cannot be canonically hashed")
  }
  const vectorSnapshot = {
    ...vector,
    lifecycle: lifecycle.right
  }
  return Either.right(
    deepSnapshot({
      vector: vectorSnapshot,
      vectorSha256: createHash("sha256").update(raw).digest("hex"),
      lifecycleSha256: lifecycleSha256.right,
      artifactCount: artifacts.length,
      generationCallCount: 9 as const,
      status: "CROSS_LANGUAGE_SYNTHETIC_LIFECYCLE_AND_CONTENT_DESCRIPTORS_REDERIVED" as const,
      terminal: DNRD5_LIFECYCLE_VECTOR_TERMINAL,
      productionContentValidated: false as const,
      occurrenceEstablished: false as const,
      scientificTerminalIssued: false as const
    })
  )
}
