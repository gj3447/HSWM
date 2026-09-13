/** Pure v1 USL reachability projection. It never resolves or executes a locator. */
import { createHash } from "node:crypto"
import { Data, Either } from "effect"
import { isTaskNumber, renderNativeTaskJson, taskJsonRecord, taskNumberValue, type TaskJson } from "./native-task-json-domain.js"

export class NativeUslV1Error extends Data.TaggedError("NativeUslV1Error")<{ readonly detail: string }> {}
type JsonObject = Readonly<Record<string, TaskJson>>
const fail = <A = never>(detail: string): Either.Either<A, NativeUslV1Error> => Either.left(new NativeUslV1Error({ detail }))
const object = (value: TaskJson | undefined): value is JsonObject => taskJsonRecord(value as TaskJson)
const text = (value: TaskJson | undefined): value is string => typeof value === "string" && value.length > 0
const exact = (value: TaskJson | undefined, keys: readonly string[]): value is JsonObject => object(value) && Object.keys(value).length === keys.length && keys.every((key) => Object.hasOwn(value, key))
const digest = (value: TaskJson): string => createHash("sha256").update(renderNativeTaskJson(value), "utf8").digest("hex")
const rows = (value: TaskJson | undefined, label: string): Either.Either<ReadonlyArray<JsonObject>, NativeUslV1Error> => !Array.isArray(value) ? fail(label) : value.every(object) ? Either.right(value) : fail(label)
const named = (value: TaskJson | undefined, label: string): Either.Either<ReadonlyMap<string, JsonObject>, NativeUslV1Error> => {
  const parsed = rows(value, label)
  if (Either.isLeft(parsed)) return fail(parsed.left.detail)
  const found = new Map<string, JsonObject>()
  for (const row of parsed.right) {
    if (!text(row["name"]) || found.has(row["name"])) return fail(`duplicate ${label}`)
    found.set(row["name"], row)
  }
  return Either.right(found)
}
const timestamp = (value: TaskJson | undefined): Either.Either<number, NativeUslV1Error> => {
  if (!text(value)) return fail("resolvedAt")
  const parsed = Date.parse(value)
  return Number.isFinite(parsed) ? Either.right(parsed / 1000) : fail("resolvedAt")
}

/** Validate caller policy pins and project only fresh selected reference reads. */
export const adaptNativeUslV1 = (input: TaskJson): Either.Either<TaskJson, NativeUslV1Error> => {
  if (!exact(input, ["plan", "report", "policy", "allowed_reads", "now", "revision"])) return fail("request shape")
  const plan = input["plan"], report = input["report"], policy = input["policy"]
  if (!object(plan) || !object(report) || !object(policy) || !Array.isArray(input["allowed_reads"]) || !isTaskNumber(input["now"]!) || !Number.isFinite(Number(taskNumberValue(input["now"]!))) || !text(input["revision"])) return fail("observation context")
  if (plan["schema"] !== "usl-semantic-plan/v1" || plan["languageVersion"] !== "0.1" || plan["declarationStatus"] !== "DECLARED" || !text(plan["namespace"])) return fail("plan version")
  const planResources = named(plan["resources"], "resource"), planLinks = named(plan["links"], "link")
  if (Either.isLeft(planResources)) return fail(planResources.left.detail)
  if (Either.isLeft(planLinks)) return fail(planLinks.left.detail)
  if (report["schema"] !== "usl-program-observation/v1" || report["namespace"] !== plan["namespace"] || report["semanticTruth"] !== "NOT_EVALUATED") return fail("report identity or semantic truth")
  if (policy["schema_version"] !== "hswm-usl-observation-policy/v1" || policy["namespace"] !== plan["namespace"] || policy["plan_digest"] !== digest(plan) || !isTaskNumber(policy["max_age_seconds"]!) || Number(taskNumberValue(policy["max_age_seconds"]!)) <= 0) return fail("policy identity or plan digest")
  const bindings = rows(policy["bindings"], "policy bindings"), pins = named(policy["resources"], "policy resource"), observed = named(report["resources"], "report observation")
  if (Either.isLeft(bindings)) return fail(bindings.left.detail)
  if (Either.isLeft(pins)) return fail(pins.left.detail)
  if (Either.isLeft(observed)) return fail(observed.left.detail)
  const allowed = new Set(input["allowed_reads"].map((entry) => Array.isArray(entry) && entry.length === 2 ? `${entry[0]}\u0000${entry[1]}` : ""))
  const outputLinks: TaskJson[] = [], outputObservations: TaskJson[] = []
  const source = digest({ plan_digest: digest(plan), report_digest: digest(report), policy_digest: digest(policy) })
  for (const binding of bindings.right) {
    if (!exact(binding, ["link", "role", "field"]) || !text(binding["link"]) || !text(binding["role"]) || !text(binding["field"]) || !allowed.has(`${binding["role"]}\u0000${binding["field"]}`)) return fail("unauthorized mapped read")
    const link = planLinks.right.get(binding["link"])
    if (link === undefined || !Array.isArray(link["participants"]) || !text(link["meaning"])) return fail("selected link")
    const reasons: string[] = []; let expiry = Infinity
    for (const participant of link["participants"]) {
      if (!object(participant) || !text(participant["resource"])) return fail("participant shape")
      const name = participant["resource"], row = observed.right.get(name), pin = pins.right.get(name)
      if (row === undefined || pin === undefined || row["status"] !== "RESOLVES" || !object(row["resolution"])) { reasons.push(`RESOURCE:${name}_ORPHAN`); continue }
      const resolution = row["resolution"]
      if (resolution["contentHash"] !== pin["content_hash"] || resolution["resolvedLocator"] !== pin["resolved_locator"]) return fail(`resource pin mismatch: ${name}`)
      const at = timestamp(resolution["resolvedAt"])
      if (Either.isLeft(at)) return fail(at.left.detail)
      const now = Number(taskNumberValue(input["now"]!)), age = Number(taskNumberValue(policy["max_age_seconds"]!))
      if (at.right > now) { reasons.push(`RESOURCE:${name}_FUTURE_TIMESTAMP`); continue }
      const end = at.right + age
      if (now >= end) reasons.push(`RESOURCE:${name}_STALE`); else expiry = Math.min(expiry, end)
    }
    const ready = reasons.length === 0
    outputLinks.push({ name: binding["link"], meaning: link["meaning"], participants: link["participants"], status: ready ? "READY" : "UNKNOWN", reasons })
    if (ready) outputObservations.push({ role: binding["role"], field: binding["field"], value: true, revision: input["revision"], expires_at: expiry, source })
  }
  return Either.right({ schema_version: "hswm-usl-observation-projection/v1", status: outputObservations.length === bindings.right.length ? "READY" : "UNRESOLVED", plan_digest: digest(plan), report_digest: digest(report), policy_digest: digest(policy), namespace: plan["namespace"], observations: outputObservations, links: outputLinks, mapping_loss: ["reference resolution only", "no semantic truth", "caller-bound report not attestation", "no content extraction/credit/admission"] })
}
