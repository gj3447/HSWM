/** Pure native counterpart of usl_cli.py project/preview; it performs no resolver I/O. */
import { Data, Either } from "effect"
import { adaptNativeUslV1 } from "./native-usl-v1-domain.js"
import { adaptNativeUslV2 } from "./native-usl-v2-wire-domain.js"
import { previewNativeTask } from "./native-task-domain.js"
import { taskJsonRecord, type TaskJson } from "./native-task-json-domain.js"

export class NativeUslCliError extends Data.TaggedError("NativeUslCliError")<{ readonly detail: string }> {}
type ObjectJson = Readonly<Record<string, TaskJson>>
const fail = <A = never>(detail: string): Either.Either<A, NativeUslCliError> => Either.left(new NativeUslCliError({ detail }))
const object = (value: TaskJson | undefined): value is ObjectJson => taskJsonRecord(value as TaskJson)
const exact = (value: TaskJson, keys: readonly string[]): value is ObjectJson => object(value) && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key))
const text = (value: TaskJson | undefined): value is string => typeof value === "string" && value.length > 0
const retype = <A>(value: Either.Either<unknown, { readonly detail: string }>): Either.Either<A, NativeUslCliError> => Either.isLeft(value) ? fail(value.left.detail) : fail("unexpected successful error branch")

/** Project a complete caller-owned v1 or v2 USL request, exactly as `project_request`. */
export const projectNativeUsl = (request: TaskJson): Either.Either<TaskJson, NativeUslCliError> => {
  if (!exact(request, ["plan", "report", "policy", "allowed_reads", "now", "revision"])) return fail("invalid JSON object fields")
  if (!object(request["report"])) return fail("invalid JSON object fields")
  if (request["report"]["schema"] === "usl-program-observation/v2") {
    const result = adaptNativeUslV2(request)
    return Either.isLeft(result) ? retype(result) : Either.right(result.right)
  }
  const result = adaptNativeUslV1(request)
  return Either.isLeft(result) ? retype(result) : Either.right(result.right)
}

/** Compose the native projection with the existing pure conditional-task preview. */
export const previewNativeUsl = (request: TaskJson): Either.Either<TaskJson, NativeUslCliError> => {
  if (!exact(request, ["plan", "report", "policy", "preview"]) || !object(request["preview"]) || !object(request["policy"])) return fail("invalid JSON object fields")
  const preview = request["preview"], policy = request["policy"]
  if (!exact(preview, ["domain", "relation", "action", "checks"]) || !object(preview["checks"]) || !Array.isArray(policy["bindings"])) return fail("invalid JSON object fields")
  const checks = preview["checks"]
  if (!Object.hasOwn(checks, "allowed_reads") || !Object.hasOwn(checks, "now") || !Object.hasOwn(checks, "revision") || !Object.hasOwn(checks, "scope") || !Object.hasOwn(checks, "expected_scope") || checks["scope"] !== policy["namespace"] || checks["expected_scope"] !== policy["namespace"]) return fail("USL preview requires explicit HSWM observation checks")
  const expected = new Set<string>()
  for (const binding of policy["bindings"]) {
    if (!object(binding) || !text(binding["role"]) || !text(binding["field"])) return fail("invalid JSON object fields")
    expected.add(JSON.stringify([binding["role"],binding["field"]]))
  }
  if (!Array.isArray(preview["domain"]) || preview["domain"].length !== expected.size) return fail("USL preview domain must contain exactly the mapped Boolean reference fields")
  for (const row of preview["domain"]) {
    if (!object(row) || !text(row["role"]) || !text(row["field"]) || !Array.isArray(row["values"]) || row["values"].length !== 2 || !row["values"].includes(false) || !row["values"].includes(true) || !expected.delete(JSON.stringify([row["role"],row["field"]]))) return fail("USL preview domain must contain exactly the mapped Boolean reference fields")
  }
  if (expected.size !== 0) return fail("USL preview domain must contain exactly the mapped Boolean reference fields")
  const projectionRequest: TaskJson = { plan: request["plan"]!, report: request["report"]!, policy, allowed_reads: checks["allowed_reads"]!, now: checks["now"]!, revision: checks["revision"]! }
  const adapter = projectNativeUsl(projectionRequest)
  if (Either.isLeft(adapter)) return adapter
  if (!taskJsonRecord(adapter.right) || !Array.isArray(adapter.right["observations"]) || !text(adapter.right["schema_version"])) return fail("native USL projection shape")
  const projected = adapter.right
  const result = previewNativeTask({ ...preview, observations: projected["observations"] } as TaskJson)
  if (Either.isLeft(result)) return retype(result)
  return Either.right({ schema_version: `hswm-usl-preview/${(projected["schema_version"] as string).endsWith("/v2") ? "v2" : "v1"}`, adapter: projected, preview: result.right, claim: "REFERENCE_READINESS_PROPOSAL_NOT_SEMANTIC_TRUTH_EXECUTION_OR_LEARNING" } as TaskJson)
}
