#!/usr/bin/env node
/**
 * One-request CLI bridge for the standard LE-0 subprocess runner.
 *
 * It is intentionally a wrapper around an already declared action command
 * and separately declared verifier command.  It never shells out, invents a
 * graph delta, or upgrades a verifier exit status into causal evidence.
 */
import { lstat, readFile } from "node:fs/promises"
import { isAbsolute } from "node:path"
import { pathToFileURL } from "node:url"

import { Effect, Either } from "effect"

import { CanonicalAtomV2DurableGraphView } from "./canonical-atom-v2-durable-runtime.js"
import { canonicalJsonBytes, decodeCanonicalJsonBytes, type CanonicalJson } from "./canonical-atom-v2-json.js"
import { makeGraphLoopEngineeringFileLayer } from "./canonical-atom-v2-graph-loop-engineering.js"
import {
  HSWM_GRAPH_LOOP_RESEARCH_FROZEN_INPUTS_V1_MEDIA_TYPE,
  GraphLoopResearchProcessRunner,
  type GraphLoopResearchCommand,
  type GraphLoopResearchJobRequest,
  type GraphLoopResearchVerifier,
  makeGraphLoopResearchProcessRunnerLayer
} from "./canonical-atom-v2-graph-loop-research-job.js"

export const HSWM_GRAPH_LOOP_RESEARCH_JOB_PROCESS_V1_CONTRACT_VERSION =
  "hswm-graph-loop-research-job-process/v1" as const

const MAX_INPUT_BYTES = 1_048_576
const MAX_FROZEN_INPUT_BYTES = 16 * 1_024 * 1_024
const MAX_TOTAL_FROZEN_INPUT_BYTES = 64 * 1_024 * 1_024
const Identifier = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/
const MediaType = /^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,126}\/[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,126}$/

type JsonObject = Readonly<Record<string, CanonicalJson>>

class ProcessRefusal extends Error {
  constructor(readonly detail: string) {
    super(detail)
    this.name = "GraphLoopResearchJobProcessRefusal"
  }
}

interface ProcessRequest {
  readonly durableRoot: string
  readonly controlJournalRoot: string
  readonly journalLineageId: string
  readonly schemaPath: string
  readonly grantsPath: string
  readonly frozenInputs: ReadonlyArray<ProcessFrozenInput>
  readonly job: GraphLoopResearchJobRequest
}

interface ProcessFrozenInput {
  readonly path: string
  readonly mediaType: string
}

interface FrozenInputBytes extends ProcessFrozenInput {
  readonly role: "DURABLE_SCHEMA" | "DURABLE_GRANTS" | "DECLARED_FROZEN_INPUT"
  readonly bytes: Uint8Array
}

const asObject = (value: CanonicalJson, label: string): JsonObject => {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new ProcessRefusal(`${label} must be an object`)
  }
  return value as JsonObject
}

const exactKeys = (
  value: JsonObject,
  expected: ReadonlyArray<string>,
  label: string
): void => {
  const actual = Object.keys(value).sort()
  const sorted = [...expected].sort()
  if (
    actual.length !== sorted.length ||
    actual.some((key, index) => key !== sorted[index])
  ) throw new ProcessRefusal(`${label} has missing or excess fields`)
}

const string = (value: CanonicalJson | undefined, label: string): string => {
  if (typeof value !== "string" || value.length < 1) {
    throw new ProcessRefusal(`${label} must be a nonempty string`)
  }
  return value
}

const integer = (value: CanonicalJson | undefined, label: string): number => {
  if (typeof value !== "number" || !Number.isSafeInteger(value)) {
    throw new ProcessRefusal(`${label} must be a safe integer`)
  }
  return value
}

const array = (value: CanonicalJson | undefined, label: string): ReadonlyArray<CanonicalJson> => {
  if (!Array.isArray(value)) throw new ProcessRefusal(`${label} must be an array`)
  return value
}

const path = (value: CanonicalJson | undefined, label: string): string => {
  const parsed = string(value, label)
  if (!isAbsolute(parsed)) throw new ProcessRefusal(`${label} must be absolute`)
  return parsed
}

const parseEnvironment = (value: CanonicalJson | undefined): Readonly<Record<string, string>> => {
  const input = asObject(value ?? {}, "command.environment")
  const result: Record<string, string> = Object.create(null)
  for (const [name, item] of Object.entries(input)) {
    if (typeof item !== "string") throw new ProcessRefusal("command.environment values must be strings")
    result[name] = item
  }
  return Object.freeze(result)
}

const parseCommand = (value: CanonicalJson, label: string): GraphLoopResearchCommand => {
  const input = asObject(value, label)
  const hasEnvironment = Object.hasOwn(input, "environment")
  exactKeys(input, hasEnvironment ? ["argv", "cwd", "environment", "timeoutMs"] : ["argv", "cwd", "timeoutMs"], label)
  return Object.freeze({
    argv: Object.freeze(array(input["argv"], `${label}.argv`).map((item, index) => string(item, `${label}.argv[${index}]`))),
    cwd: path(input["cwd"], `${label}.cwd`),
    timeoutMs: integer(input["timeoutMs"], `${label}.timeoutMs`),
    ...(hasEnvironment ? { environment: parseEnvironment(input["environment"]) } : {})
  })
}

const parseVerifier = (value: CanonicalJson): GraphLoopResearchVerifier => {
  const input = asObject(value, "job.verifier")
  exactKeys(input, ["acceptExitCodes", "command", "retryExitCodes"], "job.verifier")
  return Object.freeze({
    command: parseCommand(input["command"]!, "job.verifier.command"),
    acceptExitCodes: Object.freeze(array(input["acceptExitCodes"], "job.verifier.acceptExitCodes").map((item, index) => integer(item, `job.verifier.acceptExitCodes[${index}]`))),
    retryExitCodes: Object.freeze(array(input["retryExitCodes"], "job.verifier.retryExitCodes").map((item, index) => integer(item, `job.verifier.retryExitCodes[${index}]`)))
  })
}

const parseFrozenInputs = (
  value: CanonicalJson | undefined
): ReadonlyArray<ProcessFrozenInput> => {
  const rows = array(value, "request.frozenInputs")
  if (rows.length < 1 || rows.length > 32) {
    throw new ProcessRefusal("request.frozenInputs must declare between one and 32 regular files")
  }
  const parsed = rows.map((row, index) => {
    const input = asObject(row, `request.frozenInputs[${index}]`)
    exactKeys(input, ["mediaType", "path"], `request.frozenInputs[${index}]`)
    const mediaType = string(input["mediaType"], `request.frozenInputs[${index}].mediaType`)
    if (!MediaType.test(mediaType)) {
      throw new ProcessRefusal(`request.frozenInputs[${index}].mediaType is invalid`)
    }
    return Object.freeze({
      path: path(input["path"], `request.frozenInputs[${index}].path`),
      mediaType
    })
  })
  const paths = parsed.map((input) => input.path)
  if (new Set(paths).size !== paths.length) {
    throw new ProcessRefusal("request.frozenInputs cannot repeat a source path")
  }
  return Object.freeze([...parsed].sort((left, right) => left.path.localeCompare(right.path)))
}

const parseJob = (value: CanonicalJson): GraphLoopResearchJobRequest => {
  const input = asObject(value, "job")
  exactKeys(input, ["action", "contract", "verifier"], "job")
  const contract = asObject(input["contract"]!, "job.contract")
  exactKeys(contract, ["actorId", "maximumActions", "maximumAttempts", "runId", "triggerId", "verifierId"], "job.contract")
  return Object.freeze({
    contract: Object.freeze({
      runId: string(contract["runId"], "job.contract.runId"),
      triggerId: string(contract["triggerId"], "job.contract.triggerId"),
      actorId: string(contract["actorId"], "job.contract.actorId"),
      verifierId: string(contract["verifierId"], "job.contract.verifierId"),
      maximumAttempts: integer(contract["maximumAttempts"], "job.contract.maximumAttempts"),
      maximumActions: integer(contract["maximumActions"], "job.contract.maximumActions")
    }),
    action: parseCommand(input["action"]!, "job.action"),
    verifier: parseVerifier(input["verifier"]!)
  })
}

const parseRequest = (value: CanonicalJson): ProcessRequest => {
  const input = asObject(value, "request")
  exactKeys(
    input,
    [
      "_tag",
      "contractVersion",
      "controlJournalRoot",
      "durableRoot",
      "frozenInputs",
      "grantsPath",
      "job",
      "journalLineageId",
      "schemaPath"
    ],
    "request"
  )
  if (
    input["_tag"] !== "GraphLoopResearchJobProcessRequest" ||
    input["contractVersion"] !== HSWM_GRAPH_LOOP_RESEARCH_JOB_PROCESS_V1_CONTRACT_VERSION
  ) throw new ProcessRefusal("request tag or contract version is invalid")
  const journalLineageId = string(input["journalLineageId"], "request.journalLineageId")
  if (!Identifier.test(journalLineageId)) throw new ProcessRefusal("request.journalLineageId is invalid")
  return Object.freeze({
    durableRoot: path(input["durableRoot"], "request.durableRoot"),
    controlJournalRoot: path(input["controlJournalRoot"], "request.controlJournalRoot"),
    journalLineageId,
    schemaPath: path(input["schemaPath"], "request.schemaPath"),
    grantsPath: path(input["grantsPath"], "request.grantsPath"),
    frozenInputs: parseFrozenInputs(input["frozenInputs"]),
    job: parseJob(input["job"]!)
  })
}

const decodeCanonicalJsonFile = (bytes: Uint8Array, label: string): CanonicalJson => {
  const decoded = decodeCanonicalJsonBytes(bytes)
  if (Either.isLeft(decoded)) throw new ProcessRefusal(`${label} must contain canonical JSON bytes`)
  return decoded.right
}

const readFrozenInputBytes = async (
  input: ProcessFrozenInput
): Promise<FrozenInputBytes> => {
  const metadata = await lstat(input.path)
  if (!metadata.isFile() || metadata.isSymbolicLink()) {
    throw new ProcessRefusal(`frozen input is not a regular non-symlink file: ${input.path}`)
  }
  if (metadata.size > MAX_FROZEN_INPUT_BYTES) {
    throw new ProcessRefusal(`frozen input exceeds the per-file byte limit: ${input.path}`)
  }
  return Object.freeze({
    role: "DECLARED_FROZEN_INPUT",
    path: input.path,
    mediaType: input.mediaType,
    bytes: Uint8Array.from(await readFile(input.path))
  })
}

const stageFrozenInputManifest = (
  view: CanonicalAtomV2DurableGraphView["Type"],
  inputs: ReadonlyArray<FrozenInputBytes>
) => Effect.gen(function* () {
  const records: Array<Readonly<Record<string, unknown>>> = []
  for (const input of inputs) {
    const content = yield* view.stageContent(input.mediaType, input.bytes)
    records.push(Object.freeze({
      role: input.role,
      sourcePath: input.path,
      content
    }))
  }
  const encoded = canonicalJsonBytes({
    _tag: "GraphLoopResearchFrozenInputs",
    contractVersion: HSWM_GRAPH_LOOP_RESEARCH_JOB_PROCESS_V1_CONTRACT_VERSION,
    inputs: Object.freeze(records)
  } as CanonicalJson)
  if (Either.isLeft(encoded)) {
    return yield* Effect.die(new ProcessRefusal("frozen-input manifest cannot form canonical JSON"))
  }
  return yield* view.stageContent(
    HSWM_GRAPH_LOOP_RESEARCH_FROZEN_INPUTS_V1_MEDIA_TYPE,
    encoded.right
  )
})

/** Executes one parsed standard research job. */
export const executeGraphLoopResearchJobProcess = async (
  request: unknown
): Promise<Readonly<Record<string, unknown>>> => {
  const parsed = parseRequest(request as CanonicalJson)
  const schemaBytes = Uint8Array.from(await readFile(parsed.schemaPath))
  const grantsBytes = Uint8Array.from(await readFile(parsed.grantsPath))
  const grants = decodeCanonicalJsonFile(grantsBytes, "grantsPath")
  const declaredInputs: FrozenInputBytes[] = []
  let totalFrozenInputBytes = schemaBytes.byteLength + grantsBytes.byteLength
  for (const input of parsed.frozenInputs) {
    const bytes = await readFrozenInputBytes(input)
    totalFrozenInputBytes += bytes.bytes.byteLength
    if (totalFrozenInputBytes > MAX_TOTAL_FROZEN_INPUT_BYTES) {
      throw new ProcessRefusal("schema, grants, and declared frozen inputs exceed the total byte limit")
    }
    declaredInputs.push(bytes)
  }
  const frozenInputs = Object.freeze([
    Object.freeze({
      role: "DURABLE_SCHEMA" as const,
      path: parsed.schemaPath,
      mediaType: "application/vnd.hswm.canonical-atom-v2-schema+json",
      bytes: schemaBytes
    }),
    Object.freeze({
      role: "DURABLE_GRANTS" as const,
      path: parsed.grantsPath,
      mediaType: "application/vnd.hswm.canonical-atom-v2-grants+json",
      bytes: grantsBytes
    }),
    ...declaredInputs
  ])
  const standard = makeGraphLoopEngineeringFileLayer(
    parsed.durableRoot,
    parsed.controlJournalRoot,
    parsed.journalLineageId,
    schemaBytes,
    grants
  )
  const result = await Effect.runPromise(
    Effect.gen(function* () {
      const view = yield* CanonicalAtomV2DurableGraphView
      const inputManifest = yield* stageFrozenInputManifest(view, frozenInputs)
      const runner = yield* GraphLoopResearchProcessRunner
      return yield* runner.run({ ...parsed.job, frozenInputs: inputManifest })
    }).pipe(
      Effect.provide(makeGraphLoopResearchProcessRunnerLayer),
      Effect.provide(standard)
    )
  )
  return Object.freeze({
    _tag: "GraphLoopResearchJobProcessResult",
    contractVersion: HSWM_GRAPH_LOOP_RESEARCH_JOB_PROCESS_V1_CONTRACT_VERSION,
    terminal: result.terminal,
    attempts: result.attempts,
    frozenInputs: result.frozenInputs,
    action: result.action,
    verifier: result.verifier
  })
}

const output = (value: unknown): string => {
  const encoded = canonicalJsonBytes(value as CanonicalJson)
  if (Either.isLeft(encoded)) throw new ProcessRefusal("process output cannot form canonical JSON")
  return `${new TextDecoder().decode(encoded.right)}\n`
}

export const runGraphLoopResearchJobProcess = async (stdin: string): Promise<number> => {
  try {
    if (Buffer.byteLength(stdin, "utf8") > MAX_INPUT_BYTES) {
      throw new ProcessRefusal("stdin exceeds the bounded canonical JSON limit")
    }
    const decoded = decodeCanonicalJsonBytes(new TextEncoder().encode(stdin))
    if (Either.isLeft(decoded)) throw new ProcessRefusal("stdin must be canonical JSON")
    process.stdout.write(output(await executeGraphLoopResearchJobProcess(decoded.right)))
    return 0
  } catch (error) {
    const detail = error instanceof Error ? error.message : "unknown research job process refusal"
    process.stderr.write(`HSWM_GRAPH_LOOP_RESEARCH_JOB_REFUSED: ${detail}\n`)
    return 2
  }
}

const invokedPath = process.argv[1]
if (invokedPath !== undefined && import.meta.url === pathToFileURL(invokedPath).href) {
  let source = ""
  process.stdin.setEncoding("utf8")
  process.stdin.on("data", (chunk: string) => {
    source += chunk
    if (Buffer.byteLength(source, "utf8") > MAX_INPUT_BYTES) process.stdin.pause()
  })
  process.stdin.once("end", () => {
    void runGraphLoopResearchJobProcess(source).then((exitCode) => {
      process.exitCode = exitCode
    })
  })
  process.stdin.once("error", () => {
    process.stderr.write("HSWM_GRAPH_LOOP_RESEARCH_JOB_REFUSED: stdin read failure\n")
    process.exitCode = 2
  })
}
