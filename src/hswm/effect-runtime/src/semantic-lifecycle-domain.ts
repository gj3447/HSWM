/** Pure contracts for the finite semantic lifecycle diagnostic. */
import { resolve } from "node:path"
import { Data, Either, Schema } from "effect"

export class LifecycleError extends Data.TaggedError("LifecycleError")<{
  readonly code: string
  readonly detail: string
}> {}
export const lifecycleFailure = (code: string, detail: string): LifecycleError => new LifecycleError({ code, detail })
export const lifecycleArms = Object.freeze(["frozen", "evidence_only", "sham", "learned"] as const)
export const LifecycleArmSchema = Schema.Literal("base", ...lifecycleArms)
export type LifecycleArm = typeof LifecycleArmSchema.Type
export const LifecycleStageSchema = Schema.Literal("train", "revise", "development", "heldout")
export type LifecycleStage = typeof LifecycleStageSchema.Type
const nonempty = Schema.String.pipe(Schema.filter(value => value.trim().length > 0))
export const LifecycleCellSchema = Schema.Struct({
  base_url: nonempty,
  model: nonempty,
  max_tokens: Schema.Number.pipe(Schema.filter(value => Number.isSafeInteger(value) && value >= 1 && value <= 4096)),
  api_key_env: Schema.optional(Schema.String.pipe(Schema.pattern(/^[A-Za-z_][A-Za-z0-9_]*$/)))
})
export type LifecycleCell = typeof LifecycleCellSchema.Type
export const decodeLifecycleCell = (input: unknown): Either.Either<LifecycleCell, LifecycleError> =>
  Schema.decodeUnknownEither(LifecycleCellSchema)(input, { onExcessProperty: "error" }).pipe(
    Either.mapLeft(() => lifecycleFailure("CELL_INVALID", "Invalid bounded cell")),
    Either.flatMap(cell => Either.try({
      try: () => new URL(cell.base_url),
      catch: () => lifecycleFailure("CELL_INVALID", "Invalid endpoint")
    }).pipe(Either.flatMap(endpoint =>
      !["http:", "https:"].includes(endpoint.protocol) || endpoint.username || endpoint.password || endpoint.search || endpoint.hash
        ? Either.left(lifecycleFailure("CELL_INVALID", "Invalid endpoint; credentials belong in the environment"))
        : Either.right(cell))))
  )

export const LifecycleConfigSchema = Schema.Struct({
  contract: Schema.Literal("hswm-semantic-lifecycle/v1"), root: nonempty,
  transport: Schema.Literal("scripted", "http"), cell: LifecycleCellSchema,
  arms: Schema.Tuple(Schema.Literal("frozen"), Schema.Literal("evidence_only"), Schema.Literal("sham"), Schema.Literal("learned")),
  environmentSha256: Schema.String.pipe(Schema.pattern(/^[a-f0-9]{64}$/)),
  candidateCount: Schema.Literal(1), developmentUsedForSelection: Schema.Boolean, heldoutUsedForRevision: Schema.Literal(false),
  selection: Schema.optional(Schema.Struct({ allowance: Schema.String.pipe(Schema.pattern(/^(?:0|[1-9][0-9]*)$/)), debit: Schema.String.pipe(Schema.pattern(/^(?:0|[1-9][0-9]*)$/)) })),
  budget: Schema.Struct({ maximumModelRequests: Schema.Literal(10), maximumWorkerMs: Schema.Literal(75000), automaticRetries: Schema.Literal(0) }),
  modelExecutionStatus: Schema.Literal("NO_MODEL", "CALLER_DECLARED_HTTP_ENDPOINT_NOT_INDEPENDENTLY_VERIFIED"),
  claimCeiling: Schema.Literal("SCRIPTED_WIRING_ONLY_NOT_MODEL_EFFICACY", "FINITE_AUTHORED_DIAGNOSTIC_NOT_CONFIRMATORY_EFFICACY")
})
export type LifecycleConfig = typeof LifecycleConfigSchema.Type
export interface LifecycleOptions {
  readonly output: string
  readonly transport: "scripted" | "http"
  readonly cellPath: string | null
  readonly selection?: Readonly<{ readonly allowance: string; readonly debit: string }> | null
}

export const parseLifecycleArgs = (argv: ReadonlyArray<string>, cwd: string): Either.Either<LifecycleOptions | null, LifecycleError> => {
  if (argv.length === 1 && argv[0] === "--help") return Either.right(null)
  const parse = (index: number, values: Readonly<Record<string, string>>): Either.Either<Readonly<Record<string, string>>, LifecycleError> => {
    if (index === argv.length) return Either.right(values)
    const option = argv[index], value = argv[index + 1]
    if (option === undefined || !["--output", "--transport", "--cell", "--allowance", "--debit"].includes(option) || option in values || !value || value.startsWith("--"))
      return Either.left(lifecycleFailure("CLI_INVALID", "Invalid or duplicate option"))
    return parse(index + 2, { ...values, [option]: value })
  }
  return parse(0, {}).pipe(Either.flatMap(values => {
    const mode = values["--transport"], output = values["--output"], cell = values["--cell"]
    if (!output || (mode !== "scripted" && mode !== "http")) return Either.left(lifecycleFailure("CLI_INVALID", "Explicit new output and transport are required"))
    if ((mode === "http") !== (cell !== undefined)) return Either.left(lifecycleFailure("CLI_INVALID", "Only HTTP mode requires --cell"))
    const allowance = values["--allowance"], debit = values["--debit"]
    if ((allowance === undefined) !== (debit === undefined) || (allowance !== undefined && (!/^(?:0|[1-9][0-9]*)$/.test(allowance) || !/^(?:0|[1-9][0-9]*)$/.test(debit!)))) return Either.left(lifecycleFailure("CLI_INVALID", "--allowance and --debit must be supplied together as exact naturals"))
    return Either.right({ output: resolve(cwd, output), transport: mode, cellPath: cell === undefined ? null : resolve(cwd, cell), ...(allowance === undefined ? {} : { selection: Object.freeze({ allowance, debit: debit! }) }) })
  }))
}
