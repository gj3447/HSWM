/** Frozen model-byte validator for DNRD-5 revision proposals; never a bridge synthesizer. */
import { Data, Either, Schema } from "effect"
import { canonicalJsonBytes, canonicalJsonSha256, decodeCanonicalJsonBytes } from "./canonical-atom-v2-json.js"

export const DNRD5_REVISION_PROPOSAL_V1 = "hswm-dnrd5-revision-proposal/v1" as const
export const DNRD5_REVISION_STATUS = "MODEL_BYTES_VALIDATED_NOT_SYNTHESIZED_NOT_ADMITTED" as const
export const DNRD5_REVISION_MAX_CANONICAL_BYTES = 16_384 as const
const Id = Schema.String.pipe(Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/))
const Sha = Schema.String.pipe(Schema.pattern(/^[0-9a-f]{64}$/))
const Nat = Schema.Number.pipe(Schema.int(), Schema.nonNegative(), Schema.lessThanOrEqualTo(Number.MAX_SAFE_INTEGER))
const Media = Schema.String.pipe(Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/+-]{0,255}$/))
const Descriptor = Schema.Struct({ mediaType: Media, byteLength: Nat, sha256: Sha })
const BlockId = Schema.String.pipe(
  Schema.pattern(/^DNRD5-BLOCK-(?:0(?:00[1-9]|0[1-9]\d|[12]\d{2})|0300)$/)
)
const Target = Schema.Struct({ uid: Id, kind: Schema.Literal("macro_disposition"), targetOwner: Schema.Literal("canonical_state_custodian"), incidenceSha256: Sha })
const TypedRef = Schema.Struct({ referenceType: Id, role: Id, targetUid: Id })
const Snapshot = Schema.Struct({ journalHead: Descriptor, stateRootSha256: Sha, readsetSha256: Sha })
const Provenance = Schema.Struct({ model: Descriptor, runtime: Descriptor, rng: Descriptor })
const Validator = Schema.Struct({ path: Id, version: Descriptor })
const TaskBoundedSemantic = Schema.Struct({
  operation: Schema.Literal("SELECT_PUBLIC_HYPOTHESIS"),
  selectedHypothesis: Schema.Literal(0, 1),
  publicTaskCommitmentSha256: Sha,
  decisionBasis: Schema.Literal("SEALED_TRAJECTORY_AND_ASSIGNED_FEEDBACK")
})
const SemanticWrite = Schema.Struct({ proposalUid: Id, proposalKind: Schema.Literal("revision_proposal"), proposalOwner: Schema.Literal("revision_proposer"), targetUid: Id, targetKind: Schema.Literal("macro_disposition"), targetOwner: Schema.Literal("canonical_state_custodian"), typedRefs: Schema.Array(TypedRef).pipe(Schema.minItems(1), Schema.maxItems(64)), provenance: Descriptor, semantic: TaskBoundedSemantic })
const Envelope = Schema.Struct({
  _tag: Schema.Literal("Dnrd5RevisionProposal"), contractVersion: Schema.Literal(DNRD5_REVISION_PROPOSAL_V1),
  blockId: BlockId, opaqueCallId: Id, trajectory: Descriptor, feedbackAssignment: Descriptor, snapshot: Snapshot,
  targets: Schema.Array(Target).pipe(Schema.minItems(1), Schema.maxItems(64)), writesetIntentSha256: Sha,
  projectionBudget: Nat, validator: Validator, provenance: Provenance,
  semanticWrites: Schema.Array(SemanticWrite).pipe(Schema.minItems(1), Schema.maxItems(64)), envelopeLengthClass: Schema.Literal("COMPACT", "STANDARD", "EXPANDED")
})
export type Dnrd5RevisionEnvelope = Schema.Schema.Type<typeof Envelope>
const Expected = Schema.Struct({
  blockId: BlockId,
  opaqueCallId: Id,
  trajectory: Descriptor,
  feedbackAssignment: Descriptor,
  snapshot: Snapshot,
  targets: Schema.Array(Target).pipe(Schema.minItems(1), Schema.maxItems(64)),
  writesetIntentSha256: Sha,
  projectionBudget: Nat,
  validator: Validator,
  provenance: Provenance,
  typedRefs: Schema.Array(TypedRef).pipe(Schema.minItems(1), Schema.maxItems(64)),
  publicTaskCommitmentSha256: Sha
})
export type Dnrd5RevisionExpected = Schema.Schema.Type<typeof Expected>
export type Dnrd5RevisionErrorCode = "BYTES_INVALID" | "CANONICAL_BYTES_REQUIRED" | "SHAPE_INVALID" | "BINDING_MISMATCH" | "FORBIDDEN_MATERIAL" | "SEMANTIC_WRITE_INVALID" | "MATCHING_MISMATCH"
export class Dnrd5RevisionError extends Data.TaggedError("Dnrd5RevisionError")<{ readonly code: Dnrd5RevisionErrorCode; readonly detail: string }> {}
const fail = (code: Dnrd5RevisionErrorCode, detail: string): Either.Either<never, Dnrd5RevisionError> => Either.left(new Dnrd5RevisionError({ code, detail }))
const same = (
  a: Schema.Schema.Type<typeof Descriptor>,
  b: Schema.Schema.Type<typeof Descriptor>
) => a.mediaType === b.mediaType && a.byteLength === b.byteLength && a.sha256 === b.sha256
const sameJson = (a: unknown, b: unknown) => { const x = canonicalJsonBytes(a); const y = canonicalJsonBytes(b); return Either.isRight(x) && Either.isRight(y) && x.right.byteLength === y.right.byteLength && x.right.every((v, i) => v === y.right[i]) }
const lengthClass = (n: number) => n <= 4096 ? "COMPACT" : n <= 16384 ? "STANDARD" : "EXPANDED"
const freeze = <A>(value: A): A => { const clone = structuredClone(value); const visit = (x: unknown): void => { if (typeof x === "object" && x !== null && !Object.isFrozen(x)) { Object.freeze(x); for (const y of Object.values(x)) visit(y) } }; visit(clone); return clone }
const forbiddenToken = (value: string): boolean => ["active", "outcomeindependentsham", "delayednocredit", "exactw0rollback", "arm", "fork", "clone", "probe", "answer", "hiddentask", "evaluator", "diagnostic", "otherblock", "alternatefeedback"].some(token => value.toLowerCase().replace(/[^a-z0-9]/g, "").includes(token))
const containsForbidden = (value: unknown): boolean => typeof value === "string" ? forbiddenToken(value) : Array.isArray(value) ? value.some(containsForbidden) : typeof value === "object" && value !== null ? Object.entries(value).some(([k, v]) => forbiddenToken(k) || containsForbidden(v)) : false
const ordered = <A>(items: ReadonlyArray<A>, id: (x: A) => string) => items.every((x, i) => i === 0 || id(items[i - 1]!) < id(x))

/** Only this bytes API exists: an object cannot be accepted as a model proposal. */
export const validateDnrd5RevisionProposalBytes = (bytes: Uint8Array, expected: Dnrd5RevisionExpected): Either.Either<{ readonly proposal: Dnrd5RevisionEnvelope; readonly descriptor: Schema.Schema.Type<typeof Descriptor>; readonly status: typeof DNRD5_REVISION_STATUS; readonly validationTerminal: "CANDIDATE_VALIDATED_PENDING_PERMIT"; readonly nonclaims: "NO_MODEL_CALL_NO_PERMIT_NO_ADMISSION_NO_OCCURRENCE_NO_SCIENCE" }, Dnrd5RevisionError> => {
  if (!(bytes instanceof Uint8Array)) return fail("BYTES_INVALID", "model output must be exact Uint8Array bytes")
  if (bytes.byteLength > DNRD5_REVISION_MAX_CANONICAL_BYTES) return fail("BYTES_INVALID", "model bytes exceed the frozen proposal size bound")
  const decodedExpected = Schema.decodeUnknownEither(Expected, {
    onExcessProperty: "error"
  })(expected)
  if (Either.isLeft(decodedExpected)) {
    return fail("BINDING_MISMATCH", "expected request is not an exact frozen DNRD-5 binding")
  }
  const request = decodedExpected.right
  if (
    !ordered(request.targets, x => x.uid) ||
    new Set(request.targets.map(x => x.uid)).size !== request.targets.length ||
    !ordered(request.typedRefs, x => `${x.referenceType}|${x.role}|${x.targetUid}`) ||
    new Set(request.typedRefs.map(x => `${x.referenceType}|${x.role}|${x.targetUid}`)).size !== request.typedRefs.length
  ) return fail("BINDING_MISMATCH", "expected request ordering or uniqueness drifted")
  const parsed = decodeCanonicalJsonBytes(bytes)
  if (Either.isLeft(parsed)) return fail("BYTES_INVALID", "model bytes are not strict canonical JSON")
  const canonical = canonicalJsonBytes(parsed.right)
  if (Either.isLeft(canonical) || canonical.right.byteLength !== bytes.byteLength || !canonical.right.every((v, i) => v === bytes[i])) return fail("CANONICAL_BYTES_REQUIRED", "model bytes are not exact compact canonical JSON")
  const decoded = Schema.decodeUnknownEither(Envelope, { onExcessProperty: "error" })(parsed.right)
  if (Either.isLeft(decoded)) return fail("SHAPE_INVALID", "proposal has missing, extra, or malformed fields")
  const p = decoded.right
  if (containsForbidden(p)) return fail("FORBIDDEN_MATERIAL", "proposal contains forbidden arm/clone/probe/hidden/evaluator/alternate-feedback material")
  if (p.blockId !== request.blockId || p.opaqueCallId !== request.opaqueCallId || !same(p.trajectory, request.trajectory) || !same(p.feedbackAssignment, request.feedbackAssignment) || !sameJson(p.snapshot, request.snapshot) || p.writesetIntentSha256 !== request.writesetIntentSha256 || p.projectionBudget !== request.projectionBudget || !sameJson(p.validator, request.validator) || !sameJson(p.provenance, request.provenance)) return fail("BINDING_MISMATCH", "proposal does not bind the exact sealed request inputs")
  if (!ordered(p.targets, x => x.uid) || new Set(p.targets.map(x => x.uid)).size !== p.targets.length || !sameJson(p.targets, request.targets)) return fail("BINDING_MISMATCH", "proposal target UID/kind/incidence set drifted")
  if (p.envelopeLengthClass !== lengthClass(bytes.byteLength) || p.semanticWrites.length !== p.targets.length || !ordered(p.semanticWrites, x => x.targetUid) || new Set(p.semanticWrites.map(x => x.proposalUid)).size !== p.semanticWrites.length || p.semanticWrites.some((w, i) => w.targetUid !== p.targets[i]!.uid || w.targetKind !== p.targets[i]!.kind || w.targetOwner !== p.targets[i]!.targetOwner || !sameJson(w.typedRefs, request.typedRefs) || !same(w.provenance, p.provenance.model) || w.semantic.publicTaskCommitmentSha256 !== request.publicTaskCommitmentSha256 || containsForbidden(w.semantic))) return fail("SEMANTIC_WRITE_INVALID", "semantic writes do not have exact owner split, task binding, refs, provenance, or target shape")
  const sha = canonicalJsonSha256(p); if (Either.isLeft(sha)) return fail("BYTES_INVALID", "validated proposal cannot be described")
  return Either.right(freeze({ proposal: p, descriptor: { mediaType: "application/vnd.hswm.dnrd5.revision-proposal-v1+json", byteLength: bytes.byteLength, sha256: sha.right }, status: DNRD5_REVISION_STATUS, validationTerminal: "CANDIDATE_VALIDATED_PENDING_PERMIT" as const, nonclaims: "NO_MODEL_CALL_NO_PERMIT_NO_ADMISSION_NO_OCCURRENCE_NO_SCIENCE" as const }))
}

export const Dnrd5AdmittedRevisionShapeSchema = Schema.Struct({ targetUids: Schema.Array(Id).pipe(Schema.minItems(1)), kindIncidenceSha256: Sha, writesetCardinality: Nat, canonicalEnvelopeLengthClass: Schema.Literal("COMPACT", "STANDARD", "EXPANDED"), projectionBudget: Nat, validatorPath: Id, acceptedTerminal: Schema.Literal("ACCEPTED") })
export type Dnrd5AdmittedRevisionShape = Schema.Schema.Type<typeof Dnrd5AdmittedRevisionShapeSchema>
/** Arm-blind matching: intentionally never compares candidate semantic payload bytes. */
export const matchDnrd5ActiveShamAdmittedShapes = (active: unknown, sham: unknown): Either.Either<readonly [Dnrd5AdmittedRevisionShape, Dnrd5AdmittedRevisionShape], Dnrd5RevisionError> => {
  const decode = (x: unknown) => Schema.decodeUnknownEither(Dnrd5AdmittedRevisionShapeSchema, { onExcessProperty: "error" })(x)
  const a = decode(active); const s = decode(sham)
  if (Either.isLeft(a) || Either.isLeft(s)) return fail("MATCHING_MISMATCH", "admitted shape is malformed")
  if (!ordered(a.right.targetUids, x => x) || !ordered(s.right.targetUids, x => x) || new Set(a.right.targetUids).size !== a.right.targetUids.length || new Set(s.right.targetUids).size !== s.right.targetUids.length || a.right.writesetCardinality !== a.right.targetUids.length || s.right.writesetCardinality !== s.right.targetUids.length || !sameJson(a.right.targetUids, s.right.targetUids) || a.right.kindIncidenceSha256 !== s.right.kindIncidenceSha256 || a.right.writesetCardinality !== s.right.writesetCardinality || a.right.canonicalEnvelopeLengthClass !== s.right.canonicalEnvelopeLengthClass || a.right.projectionBudget !== s.right.projectionBudget || a.right.validatorPath !== s.right.validatorPath || a.right.acceptedTerminal !== s.right.acceptedTerminal) return fail("MATCHING_MISMATCH", "ACTIVE/SHAM admitted shape mismatch")
  return Either.right(freeze([a.right, s.right] as const))
}
