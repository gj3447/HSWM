/** Pure contracts for the bounded research-development service projection. */
import { Data, Either } from "effect"
import { decodeNativeTaskJson, renderNativeTaskJson, taskJsonRecord, type TaskJson } from "./native-task-json-domain.js"

export const RESEARCH_FABRIC_STATUS_V1 = "hswm-research-fabric-status/v1" as const
export const RESEARCH_FABRIC_PROCESS_V1 = "hswm-research-fabric-process/v1" as const
export const RESEARCH_FABRIC_SECRET_V1 = "hswm-research-fabric-secrets/v1" as const
export const RESEARCH_FABRIC_CLAIM_BOUNDARY = "bounded infrastructure observation; not HSWM cognition, canonical admission, causal credit, continuous-learning evidence, or efficacy" as const

export class NativeResearchFabricError extends Data.TaggedError("NativeResearchFabricError")<{ readonly detail: string }> {}
export const fabricRefusal = (detail: string): NativeResearchFabricError => new NativeResearchFabricError({ detail })

export interface FabricServiceSpec {
  readonly name: "phoenix" | "temporal"
  readonly executable: string
  readonly argv: ReadonlyArray<string>
  readonly environment: Readonly<Record<string, string>>
  readonly readyHost: "127.0.0.1"
  readonly readyPort: number
  readonly healthUrl: string | null
  readonly responsibility: string
  readonly expectedVersion: string
  readonly expectedExecutableSha256: string | null
}
export interface FabricProcessIdentity { readonly pid: number; readonly startTicks: number; readonly cmdline: ReadonlyArray<string> }
export interface FabricRecord extends FabricProcessIdentity {
  readonly schema: typeof RESEARCH_FABRIC_PROCESS_V1; readonly claim_boundary: typeof RESEARCH_FABRIC_CLAIM_BOUNDARY
  readonly service: FabricServiceSpec["name"]; readonly executable: string; readonly executable_sha256: string; readonly version: string
  readonly public_argv: ReadonlyArray<string>; readonly log_path: string; readonly started_unix_ns: bigint
}
export interface FabricReadiness { readonly ready: boolean; readonly tcp: boolean; readonly http: boolean | null; readonly http_status: number | null }

const temporal = (root: string, bin: string): FabricServiceSpec => Object.freeze({ name: "temporal", executable: `${bin}/temporal`, argv: Object.freeze(["--disable-config-file", "--disable-config-env", "--log-format", "json", "server", "start-dev", "--ip", "127.0.0.1", "--port", "7233", "--ui-ip", "127.0.0.1", "--ui-port", "8233", "--ui-disable-news-fetch", "--http-port", "7243", "--metrics-port", "9464", "--db-filename", `${root}/temporal/temporal.db`, "--namespace", "hswm-dev", "--search-attribute", "HswmRunId=Keyword", "--search-attribute", "HswmSchemaVersion=Keyword", "--search-attribute", "HswmAtomUid=Keyword", "--search-attribute", "HswmOutcome=Keyword"]), environment: Object.freeze({}), readyHost: "127.0.0.1", readyPort: 7233, healthUrl: "http://127.0.0.1:8233/", responsibility: "durable development workflow-history projection", expectedVersion: "1.8.2", expectedExecutableSha256: "95e6043afbbcf71137d3c953e83969e24217ca746bf535dbde561fed83a188e9" })
const phoenix = (root: string, bin: string): FabricServiceSpec => Object.freeze({ name: "phoenix", executable: `${bin}/phoenix`, argv: Object.freeze(["serve"]), environment: Object.freeze({ PHOENIX_HOST: "127.0.0.1", PHOENIX_PORT: "6006", PHOENIX_GRPC_PORT: "4317", PHOENIX_WORKING_DIR: `${root}/phoenix`, PHOENIX_ENABLE_AUTH: "true", PHOENIX_ALLOW_EXTERNAL_RESOURCES: "false", PHOENIX_TELEMETRY_ENABLED: "false", PHOENIX_ALLOWED_PROVIDERS: "NONE", PHOENIX_ENABLE_MCP_SERVER: "true", PHOENIX_ENABLE_MCP_CODE_MODE: "false", PHOENIX_ENABLE_OAUTH2_AUTHORIZATION_SERVER: "false", PHOENIX_OAUTH2_DYNAMIC_CLIENT_REGISTRATION: "disabled" }), readyHost: "127.0.0.1", readyPort: 6006, healthUrl: "http://127.0.0.1:6006/healthz", responsibility: "LLM trajectory, trace, dataset, and evaluation projection", expectedVersion: "20.4.0", expectedExecutableSha256: null })
export const fabricSpecs = (root: string, bin: string): Readonly<Record<FabricServiceSpec["name"], FabricServiceSpec>> => Object.freeze({ phoenix: phoenix(root, bin), temporal: temporal(root, bin) })
export const selectedFabricSpecs = (specs: Readonly<Record<FabricServiceSpec["name"], FabricServiceSpec>>, selected: string): Either.Either<ReadonlyArray<FabricServiceSpec>, NativeResearchFabricError> => selected === "all" ? Either.right(Object.freeze([specs.phoenix, specs.temporal])) : selected === "phoenix" || selected === "temporal" ? Either.right(Object.freeze([specs[selected]])) : Either.left(fabricRefusal("--service must be all, phoenix, or temporal"))
export const safeServiceEnvironment = (source: Readonly<Record<string, string | undefined>>, spec: FabricServiceSpec, secrets: Readonly<Record<string, string>>): Readonly<Record<string, string>> => {
  const names = ["LANG", "LC_ALL", "LOGNAME", "PATH", "SSL_CERT_DIR", "SSL_CERT_FILE", "USER"] as const
  const inherited = Object.fromEntries(names.flatMap((name) => source[name] === undefined ? [] : [[name, source[name]!]]))
  return Object.freeze({ ...inherited, ...spec.environment, ...secrets })
}
export const readiness = (tcp: boolean, http: readonly [boolean, number | null] | null): FabricReadiness => Object.freeze({ ready: tcp && (http === null || http[0]), tcp, http: http === null ? null : http[0], http_status: http === null ? null : http[1] })
export const classifyFabricState = (tracking: string, value: FabricReadiness): string => tracking === "tracked" && value.ready ? "ready" : tracking === "tracked" ? "starting_or_unhealthy" : tracking === "untracked" && value.ready ? "foreign_or_untracked_listener" : tracking === "stale_record" ? "stale_record" : tracking === "untracked" ? "not_running" : tracking
const object = (value: TaskJson): value is Readonly<Record<string, TaskJson>> => taskJsonRecord(value)
const stringArray = (value: TaskJson | undefined): value is readonly string[] => Array.isArray(value) && value.every((entry) => typeof entry === "string")
export const parseFabricRecord = (text: string, service: FabricServiceSpec["name"]): Either.Either<FabricRecord, NativeResearchFabricError> => {
  let value: TaskJson
  try { const decoded = decodeNativeTaskJson(new TextEncoder().encode(text)); if (Either.isLeft(decoded)) return Either.left(fabricRefusal("invalid process record")); value = decoded.right } catch { return Either.left(fabricRefusal("invalid process record")) }
  if (!object(value) || value["schema"] !== RESEARCH_FABRIC_PROCESS_V1 || value["claim_boundary"] !== RESEARCH_FABRIC_CLAIM_BOUNDARY || value["service"] !== service || typeof value["pid"] !== "number" || !Number.isSafeInteger(value["pid"]) || value["pid"] <= 0 || typeof value["start_ticks"] !== "number" || !Number.isSafeInteger(value["start_ticks"]) || value["start_ticks"] < 0 || typeof value["executable"] !== "string" || typeof value["executable_sha256"] !== "string" || typeof value["version"] !== "string" || !stringArray(value["public_argv"]) || typeof value["log_path"] !== "string" || typeof value["started_unix_ns"] !== "bigint" || value["started_unix_ns"] < 0n) return Either.left(fabricRefusal("invalid process record"))
  return Either.right(Object.freeze({ schema: RESEARCH_FABRIC_PROCESS_V1, claim_boundary: RESEARCH_FABRIC_CLAIM_BOUNDARY, service, pid: value["pid"], startTicks: value["start_ticks"], cmdline: Object.freeze([]), executable: value["executable"], executable_sha256: value["executable_sha256"], version: value["version"], public_argv: Object.freeze(value["public_argv"]), log_path: value["log_path"], started_unix_ns: value["started_unix_ns"] }))
}
/** Python emits an integer `time_ns`; native records epoch milliseconds × 1,000,000. */
export const renderFabricRecord = (record: FabricRecord): string => `${renderNativeTaskJson({ schema: record.schema, claim_boundary: record.claim_boundary, service: record.service, pid: record.pid, start_ticks: record.startTicks, executable: record.executable, executable_sha256: record.executable_sha256, version: record.version, public_argv: record.public_argv, log_path: record.log_path, started_unix_ns: record.started_unix_ns }, "pretty")}\n`
