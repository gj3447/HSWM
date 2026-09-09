/** Local research coordination; no tool execution, canonical write, or learning admission. */
import { createHash, randomUUID } from "node:crypto"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { parseArgs } from "node:util"
import { Effect, Either } from "effect"

import { canonicalJsonBytes, decodeCanonicalJsonBytes } from "./canonical-atom-v2-json.js"
import { PosixFileSystem, type PosixFileSystemShape } from "./effect-posix-filesystem.js"
import { refuse, type ProcessReply, type ProcessRefusal } from "./effect-process-main.js"
import { appendResearchEvent, parseResearchGraph, researchGraphState, researchTaskContext } from "./research-graph-domain.js"
import { makeResearchGraphProjection, researchGraphPropertyView } from "./research-graph-projection.js"

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../../../..")
const TEMPLATE = resolve(ROOT, "_research/research_coordination/hswm_relation_learning.v1.json")
const OPERATION = "hswm-research-graph"
const CLAIM = "LOCAL_RESEARCH_COORDINATION_NOT_CANONICAL_ADMISSION_OR_HSWM_EFFICACY"
const HELP = `hswm-research-graph (TypeScript + Effect)
  init --out NEW_FILE [--template FILE]
  validate --graph FILE
  plan --graph FILE
  context --graph FILE --task ID
  append --graph FILE --event FILE --out NEW_FILE [--expected-sha256 HASH]
  export --graph FILE [--out NEW_FILE]
  property-view --graph FILE [--out NEW_FILE]

Snapshots are immutable files. append preserves all prior events and creates a successor.
plan/context describe work; they never launch agents, fetch sources, or grant access.
export returns JSON-LD, N-Quads, and their source-bound descriptor.
`

const unwrap = <A, E extends { readonly detail: string }>(value: Either.Either<A, E>): Effect.Effect<A, ProcessRefusal> =>
  Either.isLeft(value) ? Effect.fail(refuse(value.left.detail)) : Effect.succeed(value.right)
const sha = (bytes: Uint8Array): string => createHash("sha256").update(bytes).digest("hex")
const reply = (value: unknown): ProcessReply => ({ stdout: `${JSON.stringify(value)}\n`, exitCode: 0 })
const ioError = (error: { readonly detail: string }) => refuse(error.detail)

const readJson = (fs: PosixFileSystemShape, path: string) => Effect.gen(function* () {
  const read = yield* fs.readRegularBounded(resolve(path), { maximumBytes: 1_048_576, minimumBytes: 1, operation: OPERATION }).pipe(Effect.mapError(ioError))
  const value = yield* unwrap(decodeCanonicalJsonBytes(read.bytes))
  return { value, sha256: sha(read.bytes) }
})

const writeNew = (fs: PosixFileSystemShape, path: string, value: unknown) => Effect.gen(function* () {
  const output = resolve(path)
  const bytes = yield* unwrap(canonicalJsonBytes(value))
  yield* fs.makeDirectory(dirname(output), { mode: 0o700, recursive: true, operation: OPERATION }).pipe(Effect.mapError(ioError))
  const temporary = resolve(dirname(output), `.hswm-research-${randomUUID()}.tmp`)
  yield* Effect.gen(function* () {
    yield* fs.writeExclusive(temporary, bytes, { mode: 0o600, finalMode: 0o400, sync: true, operation: OPERATION }).pipe(Effect.mapError(ioError))
    yield* fs.linkNoReplace(temporary, output, OPERATION).pipe(Effect.mapError(ioError))
    yield* fs.syncDirectory(dirname(output), OPERATION).pipe(Effect.mapError(ioError))
  }).pipe(Effect.ensuring(fs.unlinkIfPresent(temporary, OPERATION).pipe(Effect.ignore)))
  return { path: output, sha256: sha(bytes), byteLength: bytes.byteLength }
})

export const runResearchGraphCli = (argv: ReadonlyArray<string>): Effect.Effect<ProcessReply, ProcessRefusal, PosixFileSystem> => Effect.gen(function* () {
  const parsed = yield* Effect.try({
    try: () => parseArgs({ args: [...argv], allowPositionals: true, strict: true, options: {
      graph: { type: "string" }, template: { type: "string" }, task: { type: "string" },
      event: { type: "string" }, out: { type: "string" }, "expected-sha256": { type: "string" },
      help: { type: "boolean", short: "h" }
    }, tokens: true }),
    catch: () => refuse("invalid command or options; use --help")
  })
  const { values, positionals, tokens } = parsed
  if (values.help || argv.length === 0) return { stdout: HELP, exitCode: 0 }
  const action = positionals[0]
  const allowed: Readonly<Record<string, readonly string[]>> = {
    init: ["out", "template"], validate: ["graph"], plan: ["graph"], context: ["graph", "task"],
    append: ["graph", "event", "out", "expected-sha256"], export: ["graph", "out"], "property-view": ["graph", "out"]
  }
  const optionNames = tokens.filter((token) => token.kind === "option").map((token) => token.name)
  if (positionals.length !== 1 || action === undefined || !Object.hasOwn(allowed, action)
    || optionNames.some((name, index) => !allowed[action]!.includes(name) || optionNames.indexOf(name) !== index)) {
    return yield* Effect.fail(refuse("command has unexpected or duplicate arguments; use --help"))
  }
  if ((action === "init" && !values.out) || (action !== "init" && !values.graph)
    || (action === "context" && !values.task) || (action === "append" && (!values.event || !values.out))) {
    return yield* Effect.fail(refuse("command is missing a required argument; use --help"))
  }
  const fs = yield* PosixFileSystem
  const input = yield* readJson(fs, action === "init" ? values.template ?? TEMPLATE : values.graph!)
  const graph = yield* unwrap(parseResearchGraph(input.value))
  if (values["expected-sha256"] !== undefined && values["expected-sha256"] !== input.sha256) {
    return yield* Effect.fail(refuse("source SHA-256 differs from the caller's expected snapshot"))
  }
  if (action === "init") {
    if (graph.events.length !== 0) return yield* Effect.fail(refuse("init requires an unexecuted template; use append for existing work"))
    return reply({ status: "INITIALIZED", claim: CLAIM, output: yield* writeNew(fs, values.out!, graph) })
  }
  if (action === "validate") return reply({ status: "VALID", sourceSha256: input.sha256, claim: CLAIM, graphId: graph.manifest.id, eventCount: graph.events.length })
  if (action === "plan") {
    const state = researchGraphState(graph)
    return reply({ sourceSha256: input.sha256, claim: CLAIM, ...state })
  }
  if (action === "context") return reply({ sourceSha256: input.sha256, claim: CLAIM, context: yield* unwrap(researchTaskContext(graph, values.task!)) })
  if (action === "append") {
    const event = yield* readJson(fs, values.event!)
    const next = yield* unwrap(appendResearchEvent(graph, event.value))
    return reply({ status: "RECORDED", claim: CLAIM, predecessorSha256: input.sha256, eventSha256: event.sha256, output: yield* writeNew(fs, values.out!, next) })
  }
  const view = action === "property-view" ? null
    : yield* makeResearchGraphProjection(graph).pipe(Effect.mapError(ioError))
  const projection = view === null ? researchGraphPropertyView(graph)
    : { ...view, manifest: { ...view.manifest, sourceFileSha256: input.sha256 } }
  return values.out === undefined ? reply(projection)
    : reply({ status: "EXPORTED", sourceSha256: input.sha256, claim: CLAIM, output: yield* writeNew(fs, values.out, projection) })
})
