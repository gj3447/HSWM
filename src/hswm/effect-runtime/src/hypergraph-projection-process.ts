#!/usr/bin/env node
/**
 * Argv-driven executable for the bounded hypergraph projection.
 *
 * It compiles or decodes one projection, validates the derived RDF dataset
 * with the repository's Python SHACL runtime, optionally publishes and reads
 * back the exact projection namespace in Neo4j, and writes one receipt
 * package into a directory it creates.  The whole invocation is one Effect
 * program: flags parse to typed refusals, files go through `PosixFileSystem`,
 * the SHACL step runs through `BoundedSubprocess`, the Neo4j driver is a
 * bracketed resource, and the executable's only runtime boundary is
 * `runArgvProcessMain`.
 */
import { randomUUID } from "node:crypto"
import { tmpdir } from "node:os"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"

import { Data, Effect, Either } from "effect"

import {
  compileHypergraphProjection,
  decodeHypergraphProjectionBytes,
  type HypergraphProjection,
  type ProjectionGraph
} from "./canonical-atom-v2-hypergraph-projection.js"
import { HSWM_CANONICAL_JSON_V1_MAX_BYTES } from "./canonical-atom-v2-json.js"
import { canonicalAtomV2RdfProjectionBytes } from "./canonical-atom-v2-rdf-projection.js"
import { publishNeo4jHypergraphProjection, rebuildNeo4jHypergraphProjection, withNeo4jDriver } from "./canonical-atom-v2-neo4j-projection.js"
import { makeHypergraphProjectionRehearsal } from "./hypergraph-projection-rehearsal.js"
import { buildHypergraphProjectionPackage, type HypergraphProjectionPackageInput } from "./hypergraph-projection-receipt.js"
import { makeOpenConnectivityRehearsal } from "./open-connectivity-rehearsal.js"
import {
  BoundedSubprocess,
  PosixFileSystem,
  type BoundedSubprocessShape,
  type PosixFileSystemShape
} from "./effect-posix-services.js"
import { runArgvProcessMain } from "./effect-process-main.js"

export const HSWM_HYPERGRAPH_PROJECTION_PROCESS_USAGE =
  "Usage: hswm-hypergraph-projection (--rehearsal | --connectivity-rehearsal | --input canonical-projection.json) --out NEW_DIRECTORY [--repository-root CHECKOUT] [--apply --source-config FILE [--rebuild]]\nDefault: local compilation, real SHACL validation and receipt; no database connection. --connectivity-rehearsal is a synthetic recursive/peer/external metadata example, not a live connection or learning result. Both rehearsals publish only synthetic metadata with --apply, not live connectivity. --rebuild replaces only the exact verified projection namespace.\n"

/** Driver/config/parser details can contain credentials; public output is bounded to this one line. */
export const HSWM_HYPERGRAPH_PROJECTION_PROCESS_FAILURE_MESSAGE =
  "Hypergraph projection failed; no success receipt was emitted. Check source, SHACL runtime, output path and DB configuration."

const MAX_SOURCE_CONFIG_BYTES = 65_536
const SHACL_TIMEOUT_MS = 120_000
const SHACL_MAX_OUTPUT_BYTES = 1_048_576
const NEO4J_TIMEOUT_MS = 10_000
const BOOLEAN_FLAGS: ReadonlySet<string> = new Set(["--rehearsal", "--connectivity-rehearsal", "--apply", "--rebuild", "--help"])
const VALUE_FLAGS: ReadonlySet<string> = new Set(["--input", "--out", "--repository-root", "--source-config"])

export class HypergraphProjectionProcessError extends Data.TaggedError("HypergraphProjectionProcessError")<{
  readonly reason:
    | "CLI_ARGUMENTS_INVALID"
    | "SOURCE_INVALID"
    | "OUTPUT_DIRECTORY_UNAVAILABLE"
    | "VALIDATION_INPUT_UNAVAILABLE"
    | "SHACL_RUNTIME_FAILED"
    | "SHACL_MISMATCH"
    | "SOURCE_CONFIG_INVALID"
    | "NEO4J_PUBLISH_FAILED"
    | "RECEIPT_INVALID"
    | "RECEIPT_WRITE_FAILED"
  readonly detail: string
}> {}

const processError = (
  reason: HypergraphProjectionProcessError["reason"],
  detail: string
): HypergraphProjectionProcessError => new HypergraphProjectionProcessError({ reason, detail })

const right = <A>(
  result: Either.Either<A, unknown>,
  reason: HypergraphProjectionProcessError["reason"],
  detail: string
): Effect.Effect<A, HypergraphProjectionProcessError> =>
  Either.isLeft(result) ? Effect.fail(processError(reason, detail)) : Effect.succeed(result.right)

// ---------------------------------------------------------------------------
// Argument parsing: pure, exhaustive, and typed.
// ---------------------------------------------------------------------------

interface ParsedArguments {
  readonly flags: ReadonlySet<string>
  readonly values: ReadonlyMap<string, string>
}

type ProjectionSource =
  | { readonly kind: "REHEARSAL" }
  | { readonly kind: "CONNECTIVITY_REHEARSAL" }
  | { readonly kind: "INPUT"; readonly path: string }

interface ProjectionInvocation {
  readonly root: string
  readonly output: string
  readonly source: ProjectionSource
  readonly apply: { readonly sourceConfigPath: string; readonly rebuild: boolean } | null
}

const parseArguments = (args: ReadonlyArray<string>): Either.Either<ParsedArguments, HypergraphProjectionProcessError> => {
  const values = new Map<string, string>()
  const flags = new Set<string>()
  for (let index = 0; index < args.length; index++) {
    const arg = args[index]
    if (arg === undefined) break
    if (BOOLEAN_FLAGS.has(arg)) {
      if (flags.has(arg)) return Either.left(processError("CLI_ARGUMENTS_INVALID", "duplicate CLI flag"))
      flags.add(arg)
    } else if (VALUE_FLAGS.has(arg)) {
      const value = args[++index]
      if (values.has(arg) || value === undefined || value.startsWith("--")) {
        return Either.left(processError("CLI_ARGUMENTS_INVALID", "missing or duplicate CLI argument"))
      }
      values.set(arg, value)
    } else return Either.left(processError("CLI_ARGUMENTS_INVALID", "unknown CLI argument"))
  }
  return Either.right({ flags, values })
}

/** `null` means `--help`: print usage and exit successfully without touching anything. */
const planInvocation = (parsed: ParsedArguments): Either.Either<ProjectionInvocation | null, HypergraphProjectionProcessError> => {
  const { flags, values } = parsed
  if (flags.has("--help")) return Either.right(null)
  const input = values.get("--input")
  const out = values.get("--out")
  const sourceCount = Number(flags.has("--rehearsal")) + Number(flags.has("--connectivity-rehearsal")) + Number(input !== undefined)
  const source: ProjectionSource | null = flags.has("--rehearsal")
    ? { kind: "REHEARSAL" }
    : flags.has("--connectivity-rehearsal")
      ? { kind: "CONNECTIVITY_REHEARSAL" }
      : input !== undefined
        ? { kind: "INPUT", path: resolve(input) }
        : null
  if (sourceCount !== 1 || source === null || out === undefined) {
    return Either.left(processError("CLI_ARGUMENTS_INVALID", "supply exactly one source and a new output directory"))
  }
  if (flags.has("--rebuild") && !flags.has("--apply")) return Either.left(processError("CLI_ARGUMENTS_INVALID", "--rebuild requires --apply"))
  const sourceConfig = values.get("--source-config")
  if (flags.has("--apply") && sourceConfig === undefined) return Either.left(processError("CLI_ARGUMENTS_INVALID", "--apply requires --source-config"))
  const repositoryRoot = values.get("--repository-root")
  return Either.right({
    root: resolve(repositoryRoot ?? join(dirname(fileURLToPath(import.meta.url)), "../../../..")),
    output: resolve(out),
    source,
    apply: flags.has("--apply") && sourceConfig !== undefined
      ? { sourceConfigPath: resolve(sourceConfig), rebuild: flags.has("--rebuild") }
      : null
  })
}

// ---------------------------------------------------------------------------
// Filesystem helpers over the service
// ---------------------------------------------------------------------------

/** Read a caller-supplied file the way `readFile` did: follow symlinks, then bound the regular file. */
const readCallerFile = (
  fs: PosixFileSystemShape,
  path: string,
  maximumBytes: number,
  operation: string,
  reason: HypergraphProjectionProcessError["reason"]
): Effect.Effect<Uint8Array, HypergraphProjectionProcessError> =>
  fs.realpath(path, operation).pipe(
    Effect.flatMap((resolved) => fs.readRegularBounded(resolved, { maximumBytes, operation })),
    Effect.map((read) => read.bytes),
    Effect.mapError((cause) => processError(reason, `${operation}: ${cause.code}`))
  )

const loadProjection = (
  fs: PosixFileSystemShape,
  source: ProjectionSource
): Effect.Effect<HypergraphProjection, HypergraphProjectionProcessError> => {
  const detail = "projection contract verification failed"
  switch (source.kind) {
    case "REHEARSAL":
      return right(
        Either.flatMap(makeHypergraphProjectionRehearsal(), (fixture) => compileHypergraphProjection(fixture.schema, fixture.source)),
        "SOURCE_INVALID",
        detail
      )
    case "CONNECTIVITY_REHEARSAL":
      return right(
        Either.flatMap(makeOpenConnectivityRehearsal(), (fixture) => compileHypergraphProjection(fixture.schema, fixture.source)),
        "SOURCE_INVALID",
        detail
      )
    case "INPUT":
      return readCallerFile(fs, source.path, HSWM_CANONICAL_JSON_V1_MAX_BYTES, "projection-input", "SOURCE_INVALID").pipe(
        Effect.flatMap((bytes) => right(decodeHypergraphProjectionBytes(bytes), "SOURCE_INVALID", detail))
      )
  }
}

interface ValidationInputs {
  readonly projectionJsonPath: string
  readonly nquadsPath: string
}

/**
 * The SHACL runtime reads two files.  They are created exclusively under a
 * fresh random name in the temporary directory and unlinked on every exit
 * path, which is the bracketed equivalent of the former mkdtemp/rm pair.
 */
const withValidationInputs = <A, E>(
  fs: PosixFileSystemShape,
  use: (inputs: ValidationInputs) => Effect.Effect<A, E>
): Effect.Effect<A, E> =>
  Effect.acquireUseRelease(
    Effect.sync((): ValidationInputs => {
      const prefix = join(tmpdir(), `hswm-projection-validation-${randomUUID()}`)
      return { projectionJsonPath: `${prefix}.rdf.json`, nquadsPath: `${prefix}.rdf.nq` }
    }),
    use,
    (inputs) => Effect.all([
      fs.unlinkIfPresent(inputs.projectionJsonPath, "validation-cleanup"),
      fs.unlinkIfPresent(inputs.nquadsPath, "validation-cleanup")
    ]).pipe(Effect.ignore)
  )

const writeValidationInputs = (
  fs: PosixFileSystemShape,
  inputs: ValidationInputs,
  projection: HypergraphProjection
): Effect.Effect<void, HypergraphProjectionProcessError> =>
  Effect.gen(function* () {
    const rdfJson = yield* right(canonicalAtomV2RdfProjectionBytes(projection.rdf), "SOURCE_INVALID", "projection contract verification failed")
    const options = { mode: 0o600, sync: false, operation: "validation-input" } as const
    yield* fs.writeExclusive(inputs.projectionJsonPath, rdfJson, options).pipe(
      Effect.mapError((cause) => processError("VALIDATION_INPUT_UNAVAILABLE", `validation-input: ${cause.code}`))
    )
    yield* fs.writeExclusive(inputs.nquadsPath, projection.rdf.nquads, options).pipe(
      Effect.mapError((cause) => processError("VALIDATION_INPUT_UNAVAILABLE", `validation-input: ${cause.code}`))
    )
  })

// ---------------------------------------------------------------------------
// SHACL validation through the bounded subprocess service
// ---------------------------------------------------------------------------

/** The Python SHACL runtime is a repository tool and inherits this process's environment, as `execFile` did. */
const inheritedEnvironment = (): Readonly<Record<string, string>> =>
  Object.freeze(Object.fromEntries(
    Object.entries(process.env).flatMap(([name, value]) => (value === undefined ? [] : [[name, value] as const]))
  ))

const field = (value: unknown, key: string): unknown =>
  typeof value === "object" && value !== null && !Array.isArray(value) ? (value as Readonly<Record<string, unknown>>)[key] : undefined

/** Returns the exact SHACL evidence bytes the runtime printed; they are retained in the receipt. */
const validateWithShacl = (
  subprocess: BoundedSubprocessShape,
  root: string,
  inputs: ValidationInputs,
  projection: HypergraphProjection
): Effect.Effect<Uint8Array, HypergraphProjectionProcessError> =>
  Effect.gen(function* () {
    const observation = yield* subprocess.observe({
      argv: [
        "uv", "run", "--project", join(root, "_research/graph_standards/runtime"), "--locked", "--extra", "graph",
        "python", "-m", "hswm.infrastructure.hypergraph_projection_validation",
        "--projection-json", inputs.projectionJsonPath, "--nquads", inputs.nquadsPath,
        "--shapes", join(root, "schemas/HSWM_CANONICAL_ATOM_V2_RDF_PROJECTION_SHACL_1_0.ttl")
      ],
      cwd: root,
      environment: inheritedEnvironment(),
      timeoutMs: SHACL_TIMEOUT_MS,
      maximumOutputBytes: SHACL_MAX_OUTPUT_BYTES
    }).pipe(Effect.mapError((cause) => processError("SHACL_RUNTIME_FAILED", cause.detail)))
    if (observation.launchError !== null || observation.timedOut || observation.outputTruncated || observation.exitCode !== 0) {
      return yield* Effect.fail(processError("SHACL_RUNTIME_FAILED", "SHACL validation runtime did not complete cleanly"))
    }
    const evidence = yield* Effect.try({
      try: (): unknown => JSON.parse(new TextDecoder().decode(observation.stdout)),
      catch: () => processError("SHACL_RUNTIME_FAILED", "SHACL evidence is not JSON")
    })
    if (field(evidence, "conforms") !== true || field(evidence, "datasetSha256") !== projection.manifest.rdfSha256) {
      return yield* Effect.fail(processError("SHACL_MISMATCH", "SHACL did not verify this exact RDF dataset"))
    }
    return observation.stdout
  })

// ---------------------------------------------------------------------------
// Neo4j publication as a bracketed driver resource
// ---------------------------------------------------------------------------

interface Neo4jSourceConfig {
  readonly uri: string
  readonly user: string
  readonly password: string
  readonly database: string
}

/** Match the repository publisher's flat YAML credential-file convention. */
const decodeSourceConfig = (bytes: Uint8Array): Either.Either<Neo4jSourceConfig, HypergraphProjectionProcessError> => {
  const entries: Array<readonly [string, string]> = []
  for (const line of new TextDecoder().decode(bytes).split(/\r?\n/)) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith("#")) continue
    const split = trimmed.indexOf(":")
    if (split < 0) return Either.left(processError("SOURCE_CONFIG_INVALID", "source-config must be flat YAML"))
    entries.push([trimmed.slice(0, split).trim(), trimmed.slice(split + 1).trim().replace(/^(["'])(.*)\1$/, "$2")])
  }
  const config: Readonly<Record<string, string>> = Object.fromEntries(entries)
  const uri = config["uri"]
  const user = config["user"]
  const password = config["password"]
  const database = config["database"]
  if (!uri || !user || !password || !database) {
    return Either.left(processError("SOURCE_CONFIG_INVALID", "source-config requires uri, user, password and database"))
  }
  return Either.right({ uri, user, password, database })
}

const publishToNeo4j = (
  config: Neo4jSourceConfig,
  projection: HypergraphProjection,
  rebuild: boolean
): Effect.Effect<ProjectionGraph, HypergraphProjectionProcessError> =>
  withNeo4jDriver(
    { uri: config.uri, user: config.user, password: config.password, timeoutMs: NEO4J_TIMEOUT_MS },
    (driver) =>
      (rebuild ? rebuildNeo4jHypergraphProjection : publishNeo4jHypergraphProjection)(driver, projection, { database: config.database, apply: true }).pipe(
        Effect.map((final): ProjectionGraph => ({ nodes: final.readback.nodes, relationships: final.readback.relationships }))
      )
  ).pipe(Effect.mapError((cause) => processError("NEO4J_PUBLISH_FAILED", cause.code)))

// ---------------------------------------------------------------------------
// Receipt package
// ---------------------------------------------------------------------------

const writePackage = (
  fs: PosixFileSystemShape,
  output: string,
  projection: HypergraphProjection,
  input: HypergraphProjectionPackageInput
): Effect.Effect<void, HypergraphProjectionProcessError> =>
  Effect.gen(function* () {
    const packaged = yield* right(buildHypergraphProjectionPackage(projection, input), "RECEIPT_INVALID", "projection contract verification failed")
    for (const [name, content] of packaged.files) {
      yield* fs.writeExclusive(join(output, name), content, { mode: 0o666, sync: false, operation: "receipt-file" }).pipe(
        Effect.mapError((cause) => processError("RECEIPT_WRITE_FAILED", `receipt-file: ${cause.code}`))
      )
    }
  })

// ---------------------------------------------------------------------------
// Program
// ---------------------------------------------------------------------------

/** The whole invocation as one Effect program; the returned text is the exact stdout. */
export const executeHypergraphProjectionProcess = (
  argv: ReadonlyArray<string>
): Effect.Effect<string, HypergraphProjectionProcessError, PosixFileSystem | BoundedSubprocess> =>
  Effect.gen(function* () {
    const invocation = yield* planInvocation(yield* parseArguments(argv))
    if (invocation === null) return HSWM_HYPERGRAPH_PROJECTION_PROCESS_USAGE
    const fs = yield* PosixFileSystem
    const subprocess = yield* BoundedSubprocess
    const startedAt = yield* Effect.sync(() => new Date().toISOString())
    const projection = yield* loadProjection(fs, invocation.source)
    // Reserve a new directory before any DB action; never overwrite user output.
    yield* fs.makeDirectory(invocation.output, { mode: 0o777, recursive: false, operation: "output-directory" }).pipe(
      Effect.mapError((cause) => processError("OUTPUT_DIRECTORY_UNAVAILABLE", `output-directory: ${cause.code}`))
    )
    return yield* withValidationInputs(fs, (inputs) => Effect.gen(function* () {
      yield* writeValidationInputs(fs, inputs, projection)
      const shaclEvidence = yield* validateWithShacl(subprocess, invocation.root, inputs, projection)
      const readbackGraph: ProjectionGraph | null = invocation.apply === null
        ? null
        : yield* readCallerFile(fs, invocation.apply.sourceConfigPath, MAX_SOURCE_CONFIG_BYTES, "source-config", "SOURCE_CONFIG_INVALID").pipe(
          Effect.flatMap(decodeSourceConfig),
          Effect.flatMap((config) => publishToNeo4j(config, projection, invocation.apply?.rebuild === true))
        )
      const evidence = { bytes: shaclEvidence, mediaType: "application/json" } as const
      yield* writePackage(fs, invocation.output, projection, {
        runId: randomUUID(),
        startedAt,
        completedAt: new Date().toISOString(),
        producer: "https://github.com/gj3447/HSWM",
        parity: readbackGraph === null
          ? { mode: "LOCAL_COMPILER_ONLY", shaclEvidence: evidence }
          : {
            mode: "CALLER_REPORTED_LIVE_NEO4J_PARITY",
            readbackGraph,
            shaclEvidence: evidence,
            reportedBy: "hswm-hypergraph-projection CLI managed transaction readback"
          }
      })
      return `${JSON.stringify({
        status: readbackGraph === null ? "LOCAL_COMPILED_SHACL_VALIDATED" : "NEO4J_PUBLISHED_READBACK_VERIFIED",
        rebuilt: invocation.apply?.rebuild === true,
        projectionId: projection.manifest.projectionId,
        graphSha256: projection.manifest.graphSha256,
        output: invocation.output,
        claimCeiling: projection.manifest.claimCeiling
      })}\n`
    }))
  })

/** Every failure renders as the one bounded public line; typed reasons stay in the Effect for callers. */
export const describeHypergraphProjectionProcessFailure = (_error: HypergraphProjectionProcessError): string =>
  HSWM_HYPERGRAPH_PROJECTION_PROCESS_FAILURE_MESSAGE

export const runHypergraphProjectionProcess = (argv: ReadonlyArray<string>): Promise<number> =>
  runArgvProcessMain({
    program: executeHypergraphProjectionProcess,
    describeFailure: describeHypergraphProjectionProcessFailure,
    describeDefect: () => HSWM_HYPERGRAPH_PROJECTION_PROCESS_FAILURE_MESSAGE,
    failureExitCode: 1,
    defectExitCode: 1
  }, argv)

const invokedPath = process.argv[1]
if (invokedPath !== undefined && import.meta.url === pathToFileURL(invokedPath).href) {
  void runHypergraphProjectionProcess(process.argv.slice(2)).then((exitCode) => { process.exitCode = exitCode })
}
