/**
 * DNRD-5 one-shot capability-consumption atom contract.
 *
 * This module constructs and validates the persistent atom that must accompany
 * an admission or restore in the same durable command. It does not itself
 * submit that command or turn the pure Permit resolver into a capability.
 */
import { createHash } from "node:crypto"

import { Data, Either, Schema } from "effect"

import {
  canonicalJsonBytes,
  canonicalJsonSha256,
  decodeCanonicalJsonBytes
} from "./canonical-atom-v2-json.js"
import {
  sameCanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2ContentDescriptor
} from "./canonical-atom-v2-content.js"
import {
  HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  CanonicalAtomV2Schema,
  type CanonicalAtomV2,
  type CanonicalAtomV2Reference
} from "./canonical-atom-v2-schema.js"
import {
  DNRD5_REFERENCE_TYPE,
  DNRD5_SCHEMA_VERSION
} from "./canonical-atom-v2-dnrd5-schema.js"

export const DNRD5_CAPABILITY_CONSUMPTION_V1 =
  "hswm-dnrd5-capability-consumption/v1" as const
export const DNRD5_CAPABILITY_CONSUMPTION_MEDIA_TYPE =
  "application/vnd.hswm.dnrd5-capability-consumption-v1+json" as const
export const DNRD5_CAPABILITY_CONSUMPTION_KIND =
  "hswm:dnrd5:capability_consumption" as const
export const DNRD5_CAPABILITY_CONSUMPTION_OWNER =
  "owner:dnrd5:capability_consumption_custodian" as const
export const DNRD5_CAPABILITY_CONSUMPTION_TERMINAL =
  "PERSISTENT_ONE_SHOT_AUDIT_ATOM_NOT_GENERIC_PERMIT_EXECUTION_OR_SCIENTIFIC_RESULT" as const

const Identifier = Schema.String.pipe(
  Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/)
)
const Sha256 = Schema.String.pipe(Schema.pattern(/^[0-9a-f]{64}$/))
const SafeInteger = Schema.Number.pipe(
  Schema.int(),
  Schema.nonNegative(),
  Schema.lessThanOrEqualTo(Number.MAX_SAFE_INTEGER)
)
const Instant = Schema.String.pipe(
  Schema.pattern(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/)
)
const MediaType = Schema.String.pipe(
  Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/+-]{0,255}$/)
)
const Descriptor = Schema.Struct({
  mediaType: MediaType,
  byteLength: SafeInteger,
  sha256: Sha256
})

export const Dnrd5CapabilityConsumptionContentSchema = Schema.Struct({
  _tag: Schema.Literal("Dnrd5CapabilityConsumption"),
  contractVersion: Schema.Literal(DNRD5_CAPABILITY_CONSUMPTION_V1),
  effect: Schema.Literal("ADMIT_REVISION", "RESTORE_W0"),
  capabilityNonceSha256: Sha256,
  grantSnapshot: Descriptor,
  capabilityIssuance: Descriptor,
  currentRevocation: Descriptor,
  permitInputSha256: Sha256,
  permitResolutionCoreSha256: Sha256,
  expectedJournalHead: Descriptor,
  expectedStateRevision: SafeInteger,
  expectedStateSha256: Sha256,
  transitionId: Identifier,
  commandIntentSha256: Sha256,
  evaluatedAt: Instant,
  terminal: Schema.Literal(DNRD5_CAPABILITY_CONSUMPTION_TERMINAL)
})

export type Dnrd5CapabilityConsumptionContent = Schema.Schema.Type<
  typeof Dnrd5CapabilityConsumptionContentSchema
>

export interface Dnrd5CapabilityConsumptionReferenceAtoms {
  readonly grantSnapshot: CanonicalAtomV2
  readonly capabilityIssuance: CanonicalAtomV2
  readonly currentRevocation: CanonicalAtomV2
  readonly creditDecision: CanonicalAtomV2 | null
  readonly candidateValidation: CanonicalAtomV2 | null
  readonly restorePolicy: CanonicalAtomV2 | null
  readonly stagingSuccessor: CanonicalAtomV2 | null
  readonly w0Snapshot: CanonicalAtomV2 | null
}

export type Dnrd5CapabilityConsumptionErrorCode =
  | "CONTENT_INVALID"
  | "CANONICAL_ENCODING_INVALID"
  | "ATOM_INVALID"
  | "UID_INVALID"
  | "REFERENCE_INVALID"
  | "BRANCH_INVALID"
  | "DESCRIPTOR_MISMATCH"
  | "TIME_INVALID"

export class Dnrd5CapabilityConsumptionError extends Data.TaggedError(
  "Dnrd5CapabilityConsumptionError"
)<{
  readonly code: Dnrd5CapabilityConsumptionErrorCode
  readonly detail: string
}> {}

const fail = (
  code: Dnrd5CapabilityConsumptionErrorCode,
  detail: string
): Either.Either<never, Dnrd5CapabilityConsumptionError> =>
  Either.left(new Dnrd5CapabilityConsumptionError({ code, detail }))

const sha256 = (bytes: Uint8Array): string =>
  createHash("sha256").update(bytes).digest("hex")

const descriptorFor = (
  bytes: Uint8Array
): CanonicalAtomV2ContentDescriptor =>
  Object.freeze({
    mediaType: DNRD5_CAPABILITY_CONSUMPTION_MEDIA_TYPE,
    byteLength: bytes.byteLength,
    sha256: sha256(bytes)
  })

const exactInstant = (value: string): boolean => {
  const milliseconds = Date.parse(value)
  return Number.isFinite(milliseconds) && new Date(milliseconds).toISOString() === value
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

export const dnrd5CapabilityConsumptionAtomUid = (
  capabilityNonceSha256: string
): Either.Either<string, Dnrd5CapabilityConsumptionError> => {
  if (!/^[0-9a-f]{64}$/.test(capabilityNonceSha256)) {
    return fail("UID_INVALID", "capability nonce must be lowercase SHA-256")
  }
  const digest = canonicalJsonSha256({
    contractVersion: DNRD5_CAPABILITY_CONSUMPTION_V1,
    capabilityNonceSha256
  })
  return Either.isLeft(digest)
    ? fail("CANONICAL_ENCODING_INVALID", digest.left.detail)
    : Either.right(`cap-consume:${digest.right}`)
}

export const makeDnrd5CapabilityConsumptionContent = (
  input: unknown
): Either.Either<
  {
    readonly content: Dnrd5CapabilityConsumptionContent
    readonly bytes: Uint8Array
    readonly descriptor: CanonicalAtomV2ContentDescriptor
    readonly atomUid: string
  },
  Dnrd5CapabilityConsumptionError
> => {
  const decoded = Schema.decodeUnknownEither(
    Dnrd5CapabilityConsumptionContentSchema,
    { onExcessProperty: "error" }
  )(input)
  if (Either.isLeft(decoded)) {
    return fail("CONTENT_INVALID", "capability consumption content shape is not exact")
  }
  if (!exactInstant(decoded.right.evaluatedAt)) {
    return fail("TIME_INVALID", "evaluatedAt is not a real canonical UTC instant")
  }
  const bytes = canonicalJsonBytes(decoded.right)
  if (Either.isLeft(bytes)) {
    return fail("CANONICAL_ENCODING_INVALID", bytes.left.detail)
  }
  const atomUid = dnrd5CapabilityConsumptionAtomUid(
    decoded.right.capabilityNonceSha256
  )
  if (Either.isLeft(atomUid)) return Either.left(atomUid.left)
  const retainedBytes = Uint8Array.from(bytes.right)
  return Either.right(
    Object.freeze({
      content: snapshot(decoded.right),
      get bytes(): Uint8Array {
        return Uint8Array.from(retainedBytes)
      },
      descriptor: snapshot(descriptorFor(bytes.right)),
      atomUid: atomUid.right
    })
  )
}

const role = (name: string, target: CanonicalAtomV2): CanonicalAtomV2Reference => ({
  referenceType: DNRD5_REFERENCE_TYPE,
  role: `role:dnrd5:${name}`,
  target: target.key
})

const decodedAtom = (
  input: unknown,
  expectedKind: string,
  expectedOwner: string,
  label: string
): Either.Either<CanonicalAtomV2, Dnrd5CapabilityConsumptionError> => {
  const decoded = Schema.decodeUnknownEither(CanonicalAtomV2Schema, {
    onExcessProperty: "error"
  })(input)
  if (
    Either.isLeft(decoded) ||
    decoded.right.key.schemaVersion !== DNRD5_SCHEMA_VERSION ||
    decoded.right.kind !== expectedKind ||
    decoded.right.responsibilityOwner !== expectedOwner ||
    decoded.right.key.revisionId !== 0 ||
    decoded.right.lifecycle !== "ADMITTED"
  ) {
    return fail("REFERENCE_INVALID", `${label} is not the exact admitted DNRD-5 atom kind`)
  }
  return Either.right(decoded.right)
}

const validateReferenceAtoms = (
  effect: Dnrd5CapabilityConsumptionContent["effect"],
  atoms: Dnrd5CapabilityConsumptionReferenceAtoms
): Either.Either<Dnrd5CapabilityConsumptionReferenceAtoms, Dnrd5CapabilityConsumptionError> => {
  const common = [
    decodedAtom(atoms.grantSnapshot, "hswm:dnrd5:grant_snapshot", "owner:dnrd5:grant_custodian", "grant snapshot"),
    decodedAtom(atoms.capabilityIssuance, "hswm:dnrd5:capability_issuance", "owner:dnrd5:capability_custodian", "capability issuance"),
    decodedAtom(atoms.currentRevocation, "hswm:dnrd5:revocation_status", "owner:dnrd5:revocation_custodian", "current revocation")
  ]
  const failure = common.find(Either.isLeft)
  if (failure !== undefined && Either.isLeft(failure)) return Either.left(failure.left)
  if (effect === "ADMIT_REVISION") {
    if (
      atoms.creditDecision === null ||
      atoms.candidateValidation === null ||
      atoms.restorePolicy !== null ||
      atoms.stagingSuccessor !== null ||
      atoms.w0Snapshot !== null
    ) {
      return fail("BRANCH_INVALID", "admission consumption requires only credit and validation branch evidence")
    }
    const credit = decodedAtom(
      atoms.creditDecision,
      "hswm:dnrd5:credit_decision",
      "owner:dnrd5:credit_adjudicator",
      "credit decision"
    )
    const validation = decodedAtom(
      atoms.candidateValidation,
      "hswm:dnrd5:candidate_validation",
      "owner:dnrd5:revision_validator",
      "candidate validation"
    )
    if (Either.isLeft(credit)) return Either.left(credit.left)
    if (Either.isLeft(validation)) return Either.left(validation.left)
  } else {
    if (
      atoms.creditDecision !== null ||
      atoms.candidateValidation !== null ||
      atoms.restorePolicy === null ||
      atoms.stagingSuccessor === null ||
      atoms.w0Snapshot === null
    ) {
      return fail("BRANCH_INVALID", "restore consumption requires only policy, staging-successor, and W0 branch evidence")
    }
    for (const [candidate, kind, owner, label] of [
      [atoms.restorePolicy, "hswm:dnrd5:restore_policy", "owner:dnrd5:restore_policy_custodian", "restore policy"],
      [atoms.stagingSuccessor, "hswm:dnrd5:macro_disposition", "owner:dnrd5:canonical_state_custodian", "staging successor"],
      [atoms.w0Snapshot, "hswm:dnrd5:w0_snapshot", "owner:dnrd5:canonical_state_custodian", "W0 snapshot"]
    ] as const) {
      const checked = decodedAtom(candidate, kind, owner, label)
      if (Either.isLeft(checked)) return Either.left(checked.left)
    }
  }
  const all = [
    atoms.grantSnapshot,
    atoms.capabilityIssuance,
    atoms.currentRevocation,
    atoms.creditDecision,
    atoms.candidateValidation,
    atoms.restorePolicy,
    atoms.stagingSuccessor,
    atoms.w0Snapshot
  ].filter((atom): atom is CanonicalAtomV2 => atom !== null)
  const lineages = new Set(all.map(({ key }) => key.lineageId))
  if (lineages.size !== 1) {
    return fail("REFERENCE_INVALID", "consumption evidence atoms must share one lineage")
  }
  return Either.right(atoms)
}

const referencesFor = (
  content: Dnrd5CapabilityConsumptionContent,
  atoms: Dnrd5CapabilityConsumptionReferenceAtoms
): ReadonlyArray<CanonicalAtomV2Reference> =>
  content.effect === "ADMIT_REVISION"
    ? [
        role("grant", atoms.grantSnapshot),
        role("capability", atoms.capabilityIssuance),
        role("revocation", atoms.currentRevocation),
        role("credit", atoms.creditDecision!),
        role("validation", atoms.candidateValidation!)
      ]
    : [
        role("grant", atoms.grantSnapshot),
        role("capability", atoms.capabilityIssuance),
        role("revocation", atoms.currentRevocation),
        role("restore-policy", atoms.restorePolicy!),
        role("staging-successor", atoms.stagingSuccessor!),
        role("w0", atoms.w0Snapshot!)
      ]

export const makeDnrd5CapabilityConsumptionAtom = (
  contentInput: unknown,
  referenceAtoms: Dnrd5CapabilityConsumptionReferenceAtoms
): Either.Either<
  {
    readonly atom: CanonicalAtomV2
    readonly content: Dnrd5CapabilityConsumptionContent
    readonly bytes: Uint8Array
    readonly descriptor: CanonicalAtomV2ContentDescriptor
  },
  Dnrd5CapabilityConsumptionError
> => {
  const built = makeDnrd5CapabilityConsumptionContent(contentInput)
  if (Either.isLeft(built)) return Either.left(built.left)
  const checkedReferences = validateReferenceAtoms(
    built.right.content.effect,
    referenceAtoms
  )
  if (Either.isLeft(checkedReferences)) return Either.left(checkedReferences.left)
  if (
    !sameCanonicalAtomV2ContentDescriptor(
      built.right.content.grantSnapshot,
      referenceAtoms.grantSnapshot.content
    ) ||
    !sameCanonicalAtomV2ContentDescriptor(
      built.right.content.capabilityIssuance,
      referenceAtoms.capabilityIssuance.content
    ) ||
    !sameCanonicalAtomV2ContentDescriptor(
      built.right.content.currentRevocation,
      referenceAtoms.currentRevocation.content
    )
  ) {
    return fail("DESCRIPTOR_MISMATCH", "consumption content does not bind common reference payloads")
  }
  const atom: CanonicalAtomV2 = {
    _tag: "CanonicalAtomV2",
    contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
    key: {
      schemaVersion: DNRD5_SCHEMA_VERSION,
      lineageId: referenceAtoms.grantSnapshot.key.lineageId,
      atomUid: built.right.atomUid,
      revisionId: 0
    },
    kind: DNRD5_CAPABILITY_CONSUMPTION_KIND,
    responsibilityOwner: DNRD5_CAPABILITY_CONSUMPTION_OWNER,
    content: built.right.descriptor,
    provenance: {
      mode: "DERIVATION",
      evidenceSha256: built.right.content.permitResolutionCoreSha256,
      sourceRef: referenceAtoms.grantSnapshot.key
    },
    lifecycle: "ADMITTED",
    references: referencesFor(built.right.content, referenceAtoms)
  }
  const retainedBytes = built.right.bytes
  return Either.right(
    Object.freeze({
      atom: snapshot(atom),
      content: snapshot(built.right.content),
      get bytes(): Uint8Array {
        return Uint8Array.from(retainedBytes)
      },
      descriptor: snapshot(built.right.descriptor)
    })
  )
}

export const validateDnrd5CapabilityConsumptionAtom = (
  atomInput: unknown,
  contentBytes: Uint8Array,
  referenceAtoms: Dnrd5CapabilityConsumptionReferenceAtoms
): Either.Either<
  {
    readonly atom: CanonicalAtomV2
    readonly content: Dnrd5CapabilityConsumptionContent
    readonly status: "EXACT_ONE_SHOT_CONSUMPTION_ATOM_VALIDATED_NOT_SUBMITTED"
  },
  Dnrd5CapabilityConsumptionError
> => {
  if (!(contentBytes instanceof Uint8Array)) {
    return fail("CONTENT_INVALID", "consumption payload must be Uint8Array")
  }
  const parsed = decodeCanonicalJsonBytes(contentBytes)
  if (Either.isLeft(parsed)) {
    return fail("CONTENT_INVALID", "consumption payload is not strict bounded JSON")
  }
  const canonical = canonicalJsonBytes(parsed.right)
  if (
    Either.isLeft(canonical) ||
    canonical.right.byteLength !== contentBytes.byteLength ||
    !canonical.right.every((value, index) => value === contentBytes[index])
  ) {
    return fail("CANONICAL_ENCODING_INVALID", "consumption payload is not exact canonical JSON")
  }
  const rebuilt = makeDnrd5CapabilityConsumptionAtom(
    parsed.right,
    referenceAtoms
  )
  if (Either.isLeft(rebuilt)) return Either.left(rebuilt.left)
  const decoded = Schema.decodeUnknownEither(CanonicalAtomV2Schema, {
    onExcessProperty: "error"
  })(atomInput)
  if (Either.isLeft(decoded)) {
    return fail("ATOM_INVALID", "consumption atom shape is not exact")
  }
  const suppliedBytes = canonicalJsonBytes(decoded.right)
  const expectedBytes = canonicalJsonBytes(rebuilt.right.atom)
  if (
    Either.isLeft(suppliedBytes) ||
    Either.isLeft(expectedBytes) ||
    suppliedBytes.right.byteLength !== expectedBytes.right.byteLength ||
    !suppliedBytes.right.every((value, index) => value === expectedBytes.right[index])
  ) {
    return fail("ATOM_INVALID", "consumption atom differs from its deterministic construction")
  }
  return Either.right(
    snapshot({
      atom: decoded.right,
      content: rebuilt.right.content,
      status: "EXACT_ONE_SHOT_CONSUMPTION_ATOM_VALIDATED_NOT_SUBMITTED" as const
    })
  )
}
