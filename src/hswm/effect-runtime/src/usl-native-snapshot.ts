/**
 * A caller-owned, immutable record of one `connectUsl(...).hswm(...)` result.
 *
 * This is an observation transport seam only.  It neither imports USL, reads a
 * host, resolves a locator, nor grants execution/admission/learning authority.
 * In particular, `native.sourceDigest` identifies the host response while
 * `usl.sourceDigest` identifies authored USL text and may legitimately be null
 * for a graph adapter.
 */
import { createHash } from "node:crypto"
import { Data, Either } from "effect"

export const USL_NATIVE_SNAPSHOT_SCHEMA = "hswm-usl-native-snapshot/v1" as const

type Json = null | boolean | string | number | Json[] | { readonly [key: string]: Json }
type JsonRecord = { readonly [key: string]: Json }

export class UslNativeSnapshotError extends Data.TaggedError("UslNativeSnapshotError")<{
  readonly code: "INPUT_INVALID" | "EXPECTED_DIGEST_INVALID" | "NATIVE_BINDING_INVALID" | "RECEIPT_INVALID" | "PLAN_BINDING_INVALID" | "OBSERVATION_INVALID"
  readonly detail: string
}> {}

export interface UslNativeSnapshotExpected {
  /** SHA-256 of the exact raw native response, with USL's `sha256:` prefix. */
  readonly nativeSourceDigest: string
  /** HSWM sorted-key JSON SHA-256 of the full plan, without a prefix. */
  readonly hswmPlanDigest: string
}

export interface UslNativeRelationView {
  readonly nativeRelationUid: string
  readonly meaning: { readonly name: string; readonly definition: JsonRecord }
  /** The source plan's order is intentionally retained. */
  readonly participants: ReadonlyArray<{ readonly role: string; readonly nativeUid: string }>
}

export interface UslNativeSnapshot {
  readonly schema: typeof USL_NATIVE_SNAPSHOT_SCHEMA
  readonly native: {
    readonly adapter: string
    readonly sourceDigest: string
    readonly identities: { readonly resources: Readonly<Record<string, string>>; readonly links: Readonly<Record<string, string>> }
    readonly receipt: { readonly sourceDigest: string; readonly planDigest: string; readonly resultDigest: string; readonly digest: string }
  }
  /** Exact, JSON-safe HSWM handoff prepared by USL.  This does not contain host raw bytes. */
  readonly prepared: {
    readonly plan: JsonRecord
    readonly report: JsonRecord
    readonly policy: JsonRecord
    readonly allowed_reads: ReadonlyArray<readonly [string, string]>
    readonly now: number
    readonly revision: string
  }
  readonly usl: {
    readonly planDigest: string
    readonly sourceDigest: string | null
    readonly semanticTruth: "NOT_EVALUATED"
  }
  readonly relations: ReadonlyArray<UslNativeRelationView>
  /** A digest binds the supplied adapter output; it cannot attest hidden host bytes. */
  readonly integrity: "TRUSTED_ADAPTER_OUTPUT_INTEGRITY_NOT_NATIVE_SOURCE_ATTESTATION"
  readonly claim: "NATIVE_REFERENCE_SNAPSHOT_NOT_SEMANTIC_TRUTH_EXECUTION_ADMISSION_OR_LEARNING"
}

const prefixedSha = /^sha256:[0-9a-f]{64}$/
const bareSha = /^[0-9a-f]{64}$/
const fail = (code: UslNativeSnapshotError["code"], detail: string): Either.Either<never, UslNativeSnapshotError> =>
  Either.left(new UslNativeSnapshotError({ code, detail }))
const retype = <A>(value: Either.Either<unknown, UslNativeSnapshotError>): Either.Either<A, UslNativeSnapshotError> => Either.isLeft(value) ? Either.left(value.left) : fail("INPUT_INVALID", "unexpected successful error branch")
const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value)
const hasOnly = (value: Record<string, unknown>, keys: readonly string[]): boolean =>
  Object.keys(value).length === keys.length && keys.every((key) => Object.hasOwn(value, key))
const text = (value: unknown): value is string => typeof value === "string" && value.length > 0 && value.trim() === value && value.length <= 16_384
const identifier = (value: unknown): value is string => typeof value === "string" && /^[A-Za-z_][A-Za-z0-9_]*$/.test(value)

const jsonValue = (value: unknown, ancestors = new Set<object>(), depth = 0): value is Json => {
  if (depth > 64 || value === null || typeof value === "boolean" || typeof value === "string") return depth <= 64
  if (typeof value === "number") return Number.isFinite(value) && !Object.is(value, -0)
  if (typeof value !== "object" || ancestors.has(value)) return false
  const prototype = Object.getPrototypeOf(value)
  if (prototype !== Object.prototype && prototype !== null && !Array.isArray(value)) return false
  ancestors.add(value)
  const valid = Array.isArray(value)
    ? Object.keys(value).length === value.length && value.every((entry) => jsonValue(entry, ancestors, depth + 1))
    : Object.keys(value).every((key) => jsonValue((value as Record<string, unknown>)[key], ancestors, depth + 1))
  ancestors.delete(value)
  return valid
}

const cloneJson = (value: unknown): Either.Either<Json, UslNativeSnapshotError> => {
  const cloned = Either.try({
    try: () => structuredClone(value),
    catch: () => new UslNativeSnapshotError({ code: "INPUT_INVALID", detail: "input is not cloneable JSON" }),
  })
  return Either.isLeft(cloned) || !jsonValue(cloned.right)
    ? fail("INPUT_INVALID", "input is not bounded JSON data")
    : Either.right(cloned.right)
}

const uslDigest = (value: Json): string => `sha256:${createHash("sha256").update(JSON.stringify(value)).digest("hex")}`
const hswmJson = (value: Json): string => {
  if (value === null || typeof value === "boolean" || typeof value === "string" || typeof value === "number") return JSON.stringify(value)
  if (Array.isArray(value)) return `[${value.map(hswmJson).join(",")}]`
  return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${hswmJson(value[key]!)}`).join(",")}}`
}
const hswmDigest = (value: Json): string => createHash("sha256").update(hswmJson(value)).digest("hex")
const frozen = <A>(value: A): A => {
  if (value !== null && typeof value === "object") {
    for (const child of Object.values(value)) frozen(child)
    Object.freeze(value)
  }
  return value
}

const mappings = (value: unknown, expectedNames: ReadonlySet<string>, label: string): Either.Either<Readonly<Record<string, string>>, UslNativeSnapshotError> => {
  if (!isRecord(value) || !jsonValue(value)) return fail("NATIVE_BINDING_INVALID", `${label} identity map`)
  const result: Record<string, string> = Object.create(null)
  const mapped = new Set<string>()
  for (const [nativeUid, name] of Object.entries(value)) {
    if (!text(nativeUid) || !identifier(name) || !expectedNames.has(name) || mapped.has(name)) return fail("NATIVE_BINDING_INVALID", `${label} identity map coverage`)
    result[nativeUid] = name
    mapped.add(name)
  }
  return mapped.size !== expectedNames.size ? fail("NATIVE_BINDING_INVALID", `${label} identity map is incomplete`) : Either.right(result)
}

const readPrepared = (value: Json): Either.Either<UslNativeSnapshot["prepared"], UslNativeSnapshotError> => {
  if (!isRecord(value) || !hasOnly(value, ["plan", "report", "policy", "allowed_reads", "now", "revision"]) || !isRecord(value["plan"]) || !isRecord(value["report"]) || !isRecord(value["policy"]) || !Array.isArray(value["allowed_reads"]) || typeof value["now"] !== "number" || !Number.isFinite(value["now"]) || !text(value["revision"])) return fail("INPUT_INVALID", "prepared HSWM arguments")
  const reads: Array<readonly [string, string]> = []
  for (const row of value["allowed_reads"]) {
    if (!Array.isArray(row) || row.length !== 2 || !identifier(row[0]) || !identifier(row[1])) return fail("INPUT_INVALID", "prepared allowed_reads")
    reads.push([row[0], row[1]])
  }
  return Either.right({ plan: value["plan"] as JsonRecord, report: value["report"] as JsonRecord, policy: value["policy"] as JsonRecord, allowed_reads: reads, now: value["now"], revision: value["revision"] })
}

const relations = (plan: JsonRecord, resources: Readonly<Record<string, string>>, links: Readonly<Record<string, string>>): Either.Either<ReadonlyArray<UslNativeRelationView>, UslNativeSnapshotError> => {
  if (!Array.isArray(plan["resources"]) || !Array.isArray(plan["meanings"]) || !Array.isArray(plan["links"])) return fail("PLAN_BINDING_INVALID", "plan declarations")
  const meanings = new Map<string, JsonRecord>()
  for (const meaning of plan["meanings"]) {
    if (!isRecord(meaning) || !identifier(meaning["name"])) return fail("PLAN_BINDING_INVALID", "plan meaning")
    meanings.set(meaning["name"], meaning as JsonRecord)
  }
  const nativeByResource = new Map(Object.entries(resources).map(([nativeUid, name]) => [name, nativeUid]))
  const nativeByLink = new Map(Object.entries(links).map(([nativeUid, name]) => [name, nativeUid]))
  const views: UslNativeRelationView[] = []
  for (const link of plan["links"]) {
    if (!isRecord(link) || !identifier(link["name"]) || !identifier(link["meaning"]) || !Array.isArray(link["participants"])) return fail("PLAN_BINDING_INVALID", "plan link")
    const nativeRelationUid = nativeByLink.get(link["name"])
    const definition = meanings.get(link["meaning"])
    if (nativeRelationUid === undefined || definition === undefined) return fail("NATIVE_BINDING_INVALID", "link identity or meaning binding")
    const participants: Array<{ readonly role: string; readonly nativeUid: string }> = []
    const roles = new Set<string>()
    for (const participant of link["participants"]) {
      if (!isRecord(participant) || !identifier(participant["role"]) || !identifier(participant["resource"]) || roles.has(participant["role"])) return fail("PLAN_BINDING_INVALID", "ordered participant")
      const nativeUid = nativeByResource.get(participant["resource"])
      if (nativeUid === undefined) return fail("NATIVE_BINDING_INVALID", "resource identity binding")
      roles.add(participant["role"])
      participants.push({ role: participant["role"], nativeUid })
    }
    views.push({ nativeRelationUid, meaning: { name: link["meaning"], definition }, participants })
  }
  return Either.right(views)
}

/**
 * Validate and freeze a single actual `connectUsl.hswm` adapter result.
 * The next host read must call this again; this function deliberately has no
 * cache or refresh operation. The native digest proves only that the trusted
 * adapter supplied a self-consistent result, never authorship of unseen raw
 * host bytes or the native UID map.
 */
export const captureUslNativeSnapshot = (input: unknown, expected: UslNativeSnapshotExpected): Either.Either<UslNativeSnapshot, UslNativeSnapshotError> => {
  if (!text(expected.nativeSourceDigest) || !prefixedSha.test(expected.nativeSourceDigest) || !text(expected.hswmPlanDigest) || !bareSha.test(expected.hswmPlanDigest)) return fail("EXPECTED_DIGEST_INVALID", "expected native or HSWM plan digest")
  const copied = cloneJson(input)
  if (Either.isLeft(copied) || !isRecord(copied.right) || !hasOnly(copied.right, ["source", "identities", "result", "receipt"])) return Either.isLeft(copied) ? retype(copied) : fail("INPUT_INVALID", "adapter result envelope")
  const outer = copied.right
  if (!isRecord(outer["source"]) || !hasOnly(outer["source"], ["adapter", "digest"]) || !text(outer["source"]["adapter"]) || !text(outer["source"]["digest"]) || !prefixedSha.test(outer["source"]["digest"]) || outer["source"]["digest"] !== expected.nativeSourceDigest) return fail("NATIVE_BINDING_INVALID", "native source digest binding")
  const source = outer["source"]
  const prepared = readPrepared(outer["result"]!)
  if (Either.isLeft(prepared)) return retype(prepared)
  const { plan, report, policy } = prepared.right
  if (!isRecord(outer["identities"]) || !hasOnly(outer["identities"], ["resources", "links"]) || !isRecord(outer["receipt"]) || !hasOnly(outer["receipt"], ["sourceDigest", "planDigest", "resultDigest", "digest"])) return fail("INPUT_INVALID", "adapter identities or receipt")
  const identities = outer["identities"]
  const planResources = new Set(Array.isArray(plan["resources"]) ? plan["resources"].filter((row): row is JsonRecord => isRecord(row)).map((row) => row["name"]).filter(identifier) : [])
  const planLinks = new Set(Array.isArray(plan["links"]) ? plan["links"].filter((row): row is JsonRecord => isRecord(row)).map((row) => row["name"]).filter(identifier) : [])
  const resourceMap = mappings(identities["resources"], planResources, "resource")
  if (Either.isLeft(resourceMap)) return retype(resourceMap)
  const linkMap = mappings(identities["links"], planLinks, "link")
  if (Either.isLeft(linkMap)) return retype(linkMap)
  const receipt = outer["receipt"]
  if (!text(receipt["sourceDigest"]) || !text(receipt["planDigest"]) || !text(receipt["resultDigest"]) || !text(receipt["digest"]) || receipt["sourceDigest"] !== source["digest"] || receipt["planDigest"] !== uslDigest(plan) || receipt["resultDigest"] !== uslDigest(outer["result"]!) || receipt["digest"] !== uslDigest({ source, identities, sourceDigest: receipt["sourceDigest"], planDigest: receipt["planDigest"], resultDigest: receipt["resultDigest"] })) return fail("RECEIPT_INVALID", "adapter receipt digest binding")
  if (!isRecord(policy) || policy["schema_version"] !== "hswm-usl-observation-policy/v2" || policy["plan_digest"] !== expected.hswmPlanDigest || hswmDigest(plan) !== expected.hswmPlanDigest || policy["usl_plan_digest"] !== uslDigest(plan)) return fail("PLAN_BINDING_INVALID", "HSWM and USL plan digest binding")
  if (!isRecord(report) || report["schema"] !== "usl-program-observation/v2" || report["planDigest"] !== uslDigest(plan) || report["sourceDigest"] !== policy["source_digest"] || report["semanticTruth"] !== "NOT_EVALUATED") return fail("OBSERVATION_INVALID", "report plan, source, or semantic truth binding")
  const view = relations(plan, resourceMap.right, linkMap.right)
  if (Either.isLeft(view)) return retype(view)
  return Either.right(frozen({
    schema: USL_NATIVE_SNAPSHOT_SCHEMA,
    native: { adapter: source["adapter"] as string, sourceDigest: source["digest"] as string, identities: { resources: resourceMap.right, links: linkMap.right }, receipt: receipt as UslNativeSnapshot["native"]["receipt"] },
    prepared: prepared.right,
    usl: { planDigest: report["planDigest"] as string, sourceDigest: report["sourceDigest"] as string | null, semanticTruth: "NOT_EVALUATED" },
    relations: view.right,
    integrity: "TRUSTED_ADAPTER_OUTPUT_INTEGRITY_NOT_NATIVE_SOURCE_ATTESTATION",
    claim: "NATIVE_REFERENCE_SNAPSHOT_NOT_SEMANTIC_TRUTH_EXECUTION_ADMISSION_OR_LEARNING",
  }))
}
