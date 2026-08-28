/** Pure DNRD-5 nine-call accounting and caller-attested isolation evidence checker. */
import { Data, Either, Schema } from "effect"
import { createHash } from "node:crypto"
import { canonicalJsonBytes, decodeCanonicalJsonBytes } from "./canonical-atom-v2-json.js"

export const DNRD5_NINE_CALL_V1 = "hswm-dnrd5-nine-call-integrity/v1" as const
const Id = Schema.String.pipe(Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/))
const Sha = Schema.String.pipe(Schema.pattern(/^[0-9a-f]{64}$/))
const Nat = Schema.Number.pipe(Schema.int(), Schema.nonNegative())
const Media = Schema.String.pipe(Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._:/+-]{0,255}$/))
const Desc = Schema.Struct({ mediaType: Media, byteLength: Nat, sha256: Sha })
const CallClass = Schema.Literal("PRE_OUTCOME_TRAJECTORY", "REVISION_PROPOSAL", "FRESH_PROBE")
const Call = Schema.Struct({ callId: Id, callClass: CallClass, sessionId: Id, workerId: Id, privateBindingSha256: Sha, rng: Desc, model: Desc, runtime: Desc, allowedInputBundle: Desc, instruction: Desc, request: Desc, modelRequestProjection: Desc, response: Desc, isolation: Desc, allowedFiles: Desc, retry: Schema.Literal("NONE"), resumed: Schema.Literal(false), cacheSubstitution: Schema.Literal("DISABLED") })
const Manifest = Schema.Struct({ _tag: Schema.Literal("Dnrd5NineCallManifest"), contractVersion: Schema.Literal(DNRD5_NINE_CALL_V1), blockId: Schema.String.pipe(Schema.pattern(/^DNRD5-BLOCK-(000[1-9]|00[1-9]\d|0[12]\d\d|0300)$/)), custodianScope: Schema.Literal("PRIVATE_FORK_CALL_SLOT_BINDINGS"), calls: Schema.Array(Call).pipe(Schema.minItems(9), Schema.maxItems(9)), terminal: Schema.Literal("CALLER_SUPPLIED_ATTESTATION_AND_CONTENT_NOT_OS_OR_PROVIDER_PROOF") })
type Descriptor = Schema.Schema.Type<typeof Desc>
export type Dnrd5NineCallManifest = Schema.Schema.Type<typeof Manifest>
export type Dnrd5NineCallErrorCode = "BYTES_INVALID" | "MANIFEST_INVALID" | "CALL_GRAMMAR_INVALID" | "IDENTITY_DUPLICATE" | "CONTENT_MISSING" | "DESCRIPTOR_MISMATCH" | "REQUEST_LEAKAGE" | "ISOLATION_INVALID"
export class Dnrd5NineCallError extends Data.TaggedError("Dnrd5NineCallError")<{ readonly code: Dnrd5NineCallErrorCode; readonly detail: string }> {}
const fail = (code: Dnrd5NineCallErrorCode, detail: string): Either.Either<never, Dnrd5NineCallError> => Either.left(new Dnrd5NineCallError({ code, detail }))
const same = (a: Descriptor, b: Descriptor) => a.mediaType === b.mediaType && a.byteLength === b.byteLength && a.sha256 === b.sha256
const describe = (bytes: Uint8Array): Descriptor => ({ mediaType: "application/octet-stream", byteLength: bytes.byteLength, sha256: createHash("sha256").update(bytes).digest("hex") })
const freeze = <A>(value: A): A => { const clone = structuredClone(value); const walk = (x: unknown): void => { if (typeof x === "object" && x !== null && !Object.isFrozen(x)) { Object.freeze(x); for (const y of Object.values(x)) walk(y) } }; walk(clone); return clone }
const trajectoryBundle = Schema.Struct({ _tag: Schema.Literal("Dnrd5AllowedInputBundle"), callClass: Schema.Literal("PRE_OUTCOME_TRAJECTORY"), publicTask: Desc, behaviorProjection: Desc })
const revisionBundle = Schema.Struct({ _tag: Schema.Literal("Dnrd5AllowedInputBundle"), callClass: Schema.Literal("REVISION_PROPOSAL"), sealedTrajectory: Desc, assignedFeedback: Desc, revisionRequest: Desc })
const probeBundle = Schema.Struct({ _tag: Schema.Literal("Dnrd5AllowedInputBundle"), callClass: Schema.Literal("FRESH_PROBE"), behaviorProjection: Desc, freshProbe: Desc })
const allowedBundleSchema = Schema.Union(trajectoryBundle, revisionBundle, probeBundle)
const projectionSchema = Schema.Struct({ _tag: Schema.Literal("Dnrd5ModelRequestProjection"), blockId: Id, callId: Id, callClass: CallClass, rng: Desc, model: Desc, runtime: Desc, allowedInputBundle: Desc, instruction: Desc, status: Schema.Literal("MODEL_REQUEST_PROJECTION_ONLY") })
const isolationSchema = Schema.Struct({ blockId: Id, callId: Id, callClass: CallClass, sessionId: Id, workerId: Id, previousSessionId: Schema.Null, previousWorkerId: Schema.Null, network: Schema.Literal("DENIED"), undeclaredFiles: Schema.Literal("DENIED"), providerCache: Schema.Literal("DISABLED"), prefixCache: Schema.Literal("DISABLED"), freshSession: Schema.Literal(true), freshWorker: Schema.Literal(true), allowedFileManifest: Desc })
const sameJsonProjection = (value: Schema.Schema.Type<typeof projectionSchema>, call: Schema.Schema.Type<typeof Call>, blockId: string) => value.blockId === blockId && value.callId === call.callId && value.callClass === call.callClass && same(value.rng, call.rng) && same(value.model, call.model) && same(value.runtime, call.runtime) && same(value.allowedInputBundle, call.allowedInputBundle) && same(value.instruction, call.instruction)
const fixedContentRoles = ["rng", "model", "runtime", "allowedBundle", "instruction", "request", "projection", "response", "isolation", "allowedFiles"] as const
const inputRolesFor = (callClass: Schema.Schema.Type<typeof CallClass>): ReadonlyArray<string> =>
  callClass === "PRE_OUTCOME_TRAJECTORY"
    ? ["publicTask", "behaviorProjection"]
    : callClass === "REVISION_PROPOSAL"
      ? ["sealedTrajectory", "assignedFeedback", "revisionRequest"]
      : ["behaviorProjection", "freshProbe"]

export const validateDnrd5NineCallManifestBytes = (manifestBytes: Uint8Array, content: Readonly<Record<string, Uint8Array>>): Either.Either<{ readonly manifest: Dnrd5NineCallManifest; readonly status: "NINE_CALL_CONTENT_ACCOUNTED_NOT_EXECUTION_OR_OS_PROVIDER_PROOF" }, Dnrd5NineCallError> => {
  if (!(manifestBytes instanceof Uint8Array)) return fail("BYTES_INVALID", "manifest must be Uint8Array")
  const parsed = decodeCanonicalJsonBytes(manifestBytes); if (Either.isLeft(parsed)) return fail("BYTES_INVALID", "manifest is not strict JSON")
  const canonical = canonicalJsonBytes(parsed.right); if (Either.isLeft(canonical) || canonical.right.byteLength !== manifestBytes.byteLength || !canonical.right.every((x, i) => x === manifestBytes[i])) return fail("BYTES_INVALID", "manifest bytes are not exact canonical JSON")
  const decoded = Schema.decodeUnknownEither(Manifest, { onExcessProperty: "error" })(parsed.right); if (Either.isLeft(decoded)) return fail("MANIFEST_INVALID", "manifest shape is not exact")
  if (typeof content !== "object" || content === null || Array.isArray(content)) return fail("CONTENT_MISSING", "content map must be an own-property object")
  const prototype = Object.getPrototypeOf(content)
  if (prototype !== Object.prototype && prototype !== null) return fail("REQUEST_LEAKAGE", "content map cannot inherit an undeclared namespace")
  const own = (key: string): Uint8Array | undefined => {
    const property = Object.getOwnPropertyDescriptor(content, key)
    return property !== undefined && "value" in property && property.value instanceof Uint8Array
      ? property.value
      : undefined
  }
  const m = decoded.right; const classes = m.calls.map(x => x.callClass)
  if (classes.join("|") !== ["PRE_OUTCOME_TRAJECTORY", ...Array(4).fill("REVISION_PROPOSAL"), ...Array(4).fill("FRESH_PROBE")].join("|")) return fail("CALL_GRAMMAR_INVALID", "must be trajectory, four proposals, then four probes")
  for (const field of ["callId", "sessionId", "workerId", "privateBindingSha256"] as const) if (new Set(m.calls.map(x => x[field])).size !== 9) return fail("IDENTITY_DUPLICATE", `${field} must be globally unique`)
  if (m.calls.some((call, index) => m.calls.some((other, otherIndex) => index !== otherIndex && other.callId.startsWith(`${call.callId}:`)))) return fail("IDENTITY_DUPLICATE", "call IDs cannot overlap another call's content namespace")
  if (new Set(m.calls.map(x => x.rng.sha256)).size !== 9) return fail("IDENTITY_DUPLICATE", "RNG descriptors must be globally unique")
  const requiredGlobalKeys = new Set(m.calls.flatMap((call) => [
    ...fixedContentRoles.map((role) => `${call.callId}:${role}`),
    ...inputRolesFor(call.callClass).map((role) => `${call.callId}:input:${role}`)
  ]))
  const actualGlobalKeys = Reflect.ownKeys(content)
  if (
    actualGlobalKeys.length !== requiredGlobalKeys.size ||
    actualGlobalKeys.some((key) => typeof key !== "string" || !requiredGlobalKeys.has(key)) ||
    actualGlobalKeys.some((key) => {
      if (typeof key !== "string") return true
      const property = Object.getOwnPropertyDescriptor(content, key)
      return property === undefined || !("value" in property) || !(property.value instanceof Uint8Array)
    })
  ) return fail("REQUEST_LEAKAGE", "global content map must contain only exact data-property call inputs and evidence")
  for (const call of m.calls) {
    const map: Readonly<Record<string, Descriptor>> = { rng: call.rng, model: call.model, runtime: call.runtime, allowedBundle: call.allowedInputBundle, instruction: call.instruction, request: call.request, projection: call.modelRequestProjection, response: call.response, isolation: call.isolation, allowedFiles: call.allowedFiles }
    for (const [role, expected] of Object.entries(map)) { const bytes = own(`${call.callId}:${role}`); if (!(bytes instanceof Uint8Array)) return fail("CONTENT_MISSING", `missing ${role} content`); if (!same(describe(bytes), expected)) return fail("DESCRIPTOR_MISMATCH", `${role} bytes do not match descriptor`) }
    const projection = own(`${call.callId}:projection`)!; const request = own(`${call.callId}:request`)!; const parseExact = (raw: Uint8Array) => { const value = decodeCanonicalJsonBytes(raw); if (Either.isLeft(value)) return null; const exact = canonicalJsonBytes(value.right); return Either.isRight(exact) && exact.right.byteLength === raw.byteLength && exact.right.every((x, i) => x === raw[i]) ? value.right : null }
    const allowedBundle = parseExact(own(`${call.callId}:allowedBundle`)!); const bundle = allowedBundle === null ? null : Schema.decodeUnknownEither(allowedBundleSchema, { onExcessProperty: "error" })(allowedBundle)
    if (bundle === null || Either.isLeft(bundle) || bundle.right.callClass !== call.callClass) return fail("REQUEST_LEAKAGE", "allowed input bundle is not exact canonical class-bound JSON")
    const inputRoles = inputRolesFor(call.callClass)
    const named = inputRoles.map(role => [role, (bundle.right as Record<string, unknown>)[role] as Descriptor] as const)
    if (new Set(named.map(([, descriptor]) => descriptor.sha256)).size !== named.length) return fail("REQUEST_LEAKAGE", "semantically distinct allowed inputs cannot share a descriptor")
    for (const [role, descriptor] of named) { const bytes = own(`${call.callId}:input:${role}`); if (!(bytes instanceof Uint8Array)) return fail("CONTENT_MISSING", `missing named input ${role}`); if (!same(describe(bytes), descriptor)) return fail("DESCRIPTOR_MISMATCH", `named input ${role} bytes do not match bundle descriptor`) }
    const requiredKeys = new Set([...Object.keys(map).map(role => `${call.callId}:${role}`), ...inputRoles.map(role => `${call.callId}:input:${role}`)])
    const actualKeys = actualGlobalKeys.filter((key): key is string => typeof key === "string" && key.startsWith(`${call.callId}:`))
    if (actualKeys.length !== requiredKeys.size || actualKeys.some(key => !requiredKeys.has(key))) return fail("REQUEST_LEAKAGE", "call content map has unlisted or missing input material")
    const projected = parseExact(projection); const projectionValue = projected === null ? null : Schema.decodeUnknownEither(projectionSchema, { onExcessProperty: "error" })(projected)
    if (request.byteLength !== projection.byteLength || !request.every((x, i) => x === projection[i]) || projectionValue === null || Either.isLeft(projectionValue) || !sameJsonProjection(projectionValue.right, call, m.blockId)) return fail("REQUEST_LEAKAGE", "request projection is not exact, class-bound, or identity-bound")
    const rawIsolation = own(`${call.callId}:isolation`)!; const parsedIsolation = parseExact(rawIsolation); const isolation = parsedIsolation === null ? null : Schema.decodeUnknownEither(isolationSchema, { onExcessProperty: "error" })(parsedIsolation)
    if (isolation === null || Either.isLeft(isolation) || !same(isolation.right.allowedFileManifest, call.allowedFiles) || isolation.right.blockId !== m.blockId || isolation.right.callId !== call.callId || isolation.right.callClass !== call.callClass || isolation.right.sessionId !== call.sessionId || isolation.right.workerId !== call.workerId) return fail("ISOLATION_INVALID", "isolation requires exact canonical call identity, denied flags, fresh identities, and files")
  }
  return Either.right(freeze({ manifest: m, status: "NINE_CALL_CONTENT_ACCOUNTED_NOT_EXECUTION_OR_OS_PROVIDER_PROOF" as const }))
}
