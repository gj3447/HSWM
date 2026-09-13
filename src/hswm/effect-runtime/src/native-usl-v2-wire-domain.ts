/** Bounded, I/O-free USL v2 wire validation. JSON object insertion order is significant. */
import { createHash } from "node:crypto"
import { Data, Either } from "effect"
import { isTaskNumber, renderNativeTaskJson, taskJsonRecord, type TaskJson } from "./native-task-json-domain.js"

export class NativeUslV2WireError extends Data.TaggedError("NativeUslV2WireError")<{ readonly detail: string }> {}
type JsonObject = Readonly<Record<string, TaskJson>>
const fail = <A = never>(detail: string): Either.Either<A, NativeUslV2WireError> => Either.left(new NativeUslV2WireError({ detail }))
const object = (value: TaskJson | undefined): value is JsonObject => taskJsonRecord(value as TaskJson)
const text = (value: TaskJson | undefined): value is string => typeof value === "string" && value.length > 0 && value.length <= 4096
const exact = (value: TaskJson | undefined, keys: readonly string[]): value is JsonObject => object(value) && Object.keys(value).length === keys.length && keys.every((key) => Object.hasOwn(value, key))
const digestPattern = /^sha256:[0-9a-f]{64}$/
const safe = Number.MAX_SAFE_INTEGER
/** JSON.stringify-compatible insertion order, retaining TaskFloat lexemes at leaves. */
const wireJson = (value: TaskJson): string => Array.isArray(value)
  ? `[${value.map(wireJson).join(",")}]`
  : taskJsonRecord(value)
    ? `{${Object.keys(value).map(key => `${JSON.stringify(key)}:${wireJson(value[key]!)}`).join(",")}}`
    : renderNativeTaskJson(value)

const wire = (value: TaskJson, depth = 0): Either.Either<void, NativeUslV2WireError> => {
  if (depth >= 24) return fail("USL v2 JSON depth")
  if (value === null || typeof value === "string" || typeof value === "boolean") return Either.right(undefined)
  if (isTaskNumber(value)) return typeof value === "number" && Number.isSafeInteger(value) ? Either.right(undefined) : fail("USL v2 unsupported JSON value")
  if (Array.isArray(value)) { for (const item of value) { const valid = wire(item, depth + 1); if (Either.isLeft(valid)) return valid }; return Either.right(undefined) }
  for (const [key, item] of Object.entries(value)) { if (/^\d+$/.test(key)) return fail("USL v2 JSON object key"); const valid = wire(item, depth + 1); if (Either.isLeft(valid)) return valid }
  return Either.right(undefined)
}
/** Equivalent to the supported JSON.stringify subset: no sorting or normalization. */
export const nativeUslV2Digest = (value: TaskJson): Either.Either<string, NativeUslV2WireError> => {
  const valid = wire(value); if (Either.isLeft(valid)) return fail(valid.left.detail)
  return Either.right(`sha256:${createHash("sha256").update(wireJson(value), "utf8").digest("hex")}`)
}
/** Python's conditional digest: recursively sorted keys, compact UTF-8 JSON. */
const hswmDigest = (value: TaskJson): string => createHash("sha256").update(renderNativeTaskJson(value), "utf8").digest("hex")
const locator = (value: TaskJson | undefined): Either.Either<string, NativeUslV2WireError> => {
  if (!text(value) || value !== value.trim() || /\s/.test(value)) return fail("USL v2 locator whitespace")
  if (/^https?:\/\//i.test(value)) {
    if (!/^[\x00-\x7f]*$/.test(value) || /[\\<>"`{}\x00-\x20\x7f]/.test(value)) return fail("USL v2 unsupported URL spelling")
    try { const parsed = new URL(value); if (!/^https?:$/.test(parsed.protocol) || parsed.username || parsed.password || !parsed.hostname || /(^|\/)\.\.?(\/|$)/.test(parsed.pathname)) return fail("USL v2 unsupported URL authority"); return Either.right(parsed.href) } catch { return fail("USL v2 unsupported URL spelling") }
  }
  if (/^kg:\/\/[A-Za-z0-9._-]+\/\S+$/.test(value) || /^file:\/\/[A-Za-z0-9._-]+\/(?!\/)[^#\s]*(?:#L\d+-L\d+)?$/.test(value) || /^git:\/\/[^@\s:]+(?:@[0-9a-fA-F]{7,64})?(?::[^:\s@]+(?:::[^@\s]+)?(?:@L\d+-L\d+)?)?$/.test(value)) return Either.right(value)
  return fail("USL v2 locator scheme")
}
const named = (value: TaskJson | undefined, label: string): Either.Either<ReadonlyMap<string, JsonObject>, NativeUslV2WireError> => {
  if (!Array.isArray(value) || value.length > 256 || !value.every(object)) return fail(label)
  const rows = new Map<string, JsonObject>(); for (const row of value) { if (!text(row["name"]) || rows.has(row["name"])) return fail(label); rows.set(row["name"], row) }; return Either.right(rows)
}
export const validateNativeUslV2Wire = (input: TaskJson): Either.Either<void, NativeUslV2WireError> => {
  if (!exact(input, ["plan", "report", "policy"]) || !object(input["plan"]) || !object(input["report"]) || !object(input["policy"])) return fail("USL v2 request shape")
  const { plan, report, policy } = input
  if (plan["schema"] !== "usl-semantic-plan/v1" || plan["languageVersion"] !== "0.1" || plan["declarationStatus"] !== "DECLARED" || !text(plan["namespace"])) return fail("USL v2 plan shape")
  if (!exact(report, ["schema", "namespace", "planDigest", "meaningsDigest", "sourceDigest", "digestFormat", "status", "readScope", "metrics", "resources", "groundings", "meanings", "links", "semanticTruth", "observationDigest"]) || report["schema"] !== "usl-program-observation/v2" || report["namespace"] !== plan["namespace"] || report["semanticTruth"] !== "NOT_EVALUATED" || report["digestFormat"] !== "sha256:utf8:JSON.stringify/v1") return fail("USL v2 report shape")
  if (!exact(policy, ["schema_version", "namespace", "plan_digest", "usl_plan_digest", "source_digest", "max_age_seconds", "bindings", "resources"]) || policy["schema_version"] !== "hswm-usl-observation-policy/v2" || policy["namespace"] !== plan["namespace"] || !text(policy["plan_digest"]) || typeof policy["max_age_seconds"] !== "number" || !Number.isFinite(policy["max_age_seconds"]) || policy["max_age_seconds"] <= 0 || policy["max_age_seconds"] > 86400) return fail("USL v2 policy shape")
  const planDigest = nativeUslV2Digest(plan); if (Either.isLeft(planDigest)) return planDigest
  if (report["planDigest"] !== planDigest.right || policy["usl_plan_digest"] !== planDigest.right || !text(report["meaningsDigest"]) || !text(report["observationDigest"])) return fail("USL v2 plan digest binding")
  const meaningsDigest = nativeUslV2Digest(plan["meanings"]!); if (Either.isLeft(meaningsDigest) || report["meaningsDigest"] !== meaningsDigest.right) return fail("USL v2 meanings digest")
  if (report["sourceDigest"] !== null && (!text(report["sourceDigest"]) || !digestPattern.test(report["sourceDigest"]))) return fail("USL v2 source digest")
  if (report["sourceDigest"] !== policy["source_digest"]) return fail("USL v2 source digest pin")
  const unsigned: JsonObject = Object.fromEntries(Object.entries(report).filter(([key]) => key !== "observationDigest")); const observationDigest = nativeUslV2Digest(unsigned); if (Either.isLeft(observationDigest) || report["observationDigest"] !== observationDigest.right) return fail("USL v2 observation digest")
  const scope = report["readScope"]; if (!exact(scope, ["links", "allowedLocators", "requestedLocators", "resourceBudget"]) || !Array.isArray(scope["links"]) || !Array.isArray(scope["allowedLocators"]) || !Array.isArray(scope["requestedLocators"]) || !Number.isInteger(scope["resourceBudget"]) || (scope["resourceBudget"] as number) > safe) return fail("USL v2 read scope shape")
  for (const item of [...scope["allowedLocators"], ...scope["requestedLocators"]]) { const checked = locator(item); if (Either.isLeft(checked)) return checked }
  for (const list of [report["resources"], report["groundings"], report["meanings"], report["links"], policy["resources"]]) { const checked = named(list, "USL v2 rows"); if (Either.isLeft(checked)) return fail(checked.left.detail) }
  if (!Array.isArray(policy["bindings"]) || policy["bindings"].length === 0 || !policy["bindings"].every(object)) return fail("USL v2 bindings")
  return Either.right(undefined)
}

/** Project validated v2 reference observations without executing declared checks. */
export const adaptNativeUslV2 = (input: TaskJson): Either.Either<TaskJson, NativeUslV2WireError> => {
  if (!object(input) || !object(input["plan"]) || !object(input["report"]) || !object(input["policy"]) || !Array.isArray(input["allowed_reads"]) || typeof input["now"] !== "number" || !Number.isFinite(input["now"]) || !text(input["revision"])) return fail("USL v2 observation context")
  const checked = validateNativeUslV2Wire({ plan: input["plan"], report: input["report"], policy: input["policy"] })
  if (Either.isLeft(checked)) return fail(checked.left.detail)
  const plan = input["plan"], report = input["report"], policy = input["policy"]
  const allowed = new Set<string>()
  for (const entry of input["allowed_reads"]) { if (!Array.isArray(entry) || entry.length !== 2 || !text(entry[0]) || !text(entry[1])) return fail("USL v2 allowed reads"); allowed.add(`${entry[0]}\u0000${entry[1]}`) }
  const bindings = policy["bindings"] as ReadonlyArray<JsonObject>
  const selected = new Map<string, JsonObject>()
  for (const binding of bindings) { if (!exact(binding, ["link", "role", "field"]) || !text(binding["link"]) || !text(binding["role"]) || !text(binding["field"]) || selected.has(binding["link"]) || !allowed.has(`${binding["role"]}\u0000${binding["field"]}`)) return fail("USL v2 binding"); selected.set(binding["link"], binding) }
  const resources = named(report["resources"], "USL v2 resources"), groundings = named(report["groundings"], "USL v2 groundings"), pins = named(policy["resources"], "USL v2 pins"), meanings = named(plan["meanings"], "USL v2 meanings"), reportLinks = named(report["links"], "USL v2 links")
  if (Either.isLeft(resources)) return fail(resources.left.detail)
  if (Either.isLeft(groundings)) return fail(groundings.left.detail)
  if (Either.isLeft(pins)) return fail(pins.left.detail)
  if (Either.isLeft(meanings)) return fail(meanings.left.detail)
  if (Either.isLeft(reportLinks)) return fail(reportLinks.left.detail)
  const reportDigest = hswmDigest(report), policyDigest = hswmDigest(policy)
  const source = hswmDigest({ plan_digest: hswmDigest(plan), report_digest: reportDigest, policy_digest: policyDigest })
  const links: TaskJson[] = [], observations: TaskJson[] = []
  for (const linkValue of plan["links"] as ReadonlyArray<TaskJson>) {
    if (!object(linkValue) || !text(linkValue["name"]) || !selected.has(linkValue["name"])) continue
    const binding = selected.get(linkValue["name"])!, reasons: string[] = []; let expires = Infinity
    if (!Array.isArray(linkValue["participants"])) return fail("USL v2 participant shape")
    for (const participant of linkValue["participants"]) {
      if (!object(participant) || !text(participant["resource"])) return fail("USL v2 participant shape")
      const name = participant["resource"], row = resources.right.get(name), pin = pins.right.get(name)
      if (!row || !pin || row["status"] !== "RESOLVES" || !object(row["resolution"])) { reasons.push(`RESOURCE:${name}_${row?.["status"] ?? "ORPHAN"}`); continue }
      const resolution = row["resolution"]
      if (resolution["contentHash"] !== pin["content_hash"] || resolution["resolvedLocator"] !== pin["resolved_locator"]) return fail(`resource pin mismatch: ${name}`)
      const at = Date.parse(String(resolution["resolvedAt"])) / 1000, expiry = at + (policy["max_age_seconds"] as number)
      if (!Number.isFinite(at) || at > input["now"]) reasons.push(`RESOURCE:${name}_FUTURE_TIMESTAMP`); else if (input["now"] >= expiry) reasons.push(`RESOURCE:${name}_STALE`); else expires = Math.min(expires, expiry)
    }
    const meaning = meanings.right.get(String(linkValue["meaning"]))
    if (meaning?.["grounded"] !== undefined) {
      const name = meaning["name"]
      if (!text(name)) return fail("USL v2 meaning shape")
      const row = groundings.right.get(name), pin = pins.right.get(`meaning:${name}`)
      if (!row || !pin || row["status"] !== "RESOLVES" || !object(row["resolution"])) reasons.push(`GROUNDING:${name}_${row?.["status"] ?? "ORPHAN"}`)
      else {
        const resolution = row["resolution"]
        if (resolution["contentHash"] !== pin["content_hash"] || resolution["resolvedLocator"] !== pin["resolved_locator"]) return fail(`grounding pin mismatch: ${name}`)
        const at = Date.parse(String(resolution["resolvedAt"])) / 1000, expiry = at + (policy["max_age_seconds"] as number)
        if (!Number.isFinite(at) || at > input["now"]) reasons.push(`GROUNDING:${name}_FUTURE_TIMESTAMP`); else if (input["now"] >= expiry) reasons.push(`GROUNDING:${name}_STALE`); else expires = Math.min(expires, expiry)
      }
    }
    const ready = reasons.length === 0
    const reportLink = reportLinks.right.get(linkValue["name"])
    links.push({ name: linkValue["name"], meaning: linkValue["meaning"]!, participants: linkValue["participants"]!, status: ready ? "READY" : "UNKNOWN", reasons, ...(reportLink === undefined ? {} : { meaningDigest: reportLink["meaningDigest"]!, contractDigest: reportLink["contractDigest"]!, verification: reportLink["verification"]! }) })
    if (ready) observations.push({ role: binding["role"]!, field: binding["field"]!, value: true, revision: input["revision"], expires_at: expires, source })
  }
  return Either.right({ schema_version: "hswm-usl-observation-projection/v2", status: observations.length === selected.size ? "READY" : "UNRESOLVED", plan_digest: policy["plan_digest"]!, report_digest: reportDigest, policy_digest: policyDigest, namespace: plan["namespace"]!, observations, links, mapping_loss: ["reference resolution only", "no semantic truth", "caller-bound report not attestation", "no content extraction/credit/admission", "declared checks preserved but not executed", "source digest caller-pinned, source not recompiled", "KG_METADATA is not full graph semantics", "noncanonical HTTP URL forms outside the supported subset reject"], meanings: report["meanings"]!, usl: { report_schema: report["schema"]!, plan_digest: report["planDigest"]!, meanings_digest: report["meaningsDigest"]!, source_digest: report["sourceDigest"]!, observation_digest: report["observationDigest"]!, digest_format: report["digestFormat"]!, source_binding: report["sourceDigest"] === null ? "ABSENT" : "CALLER_PINNED_NOT_RECOMPILED" }, read_scope: report["readScope"]!, metrics: report["metrics"]! })
}
