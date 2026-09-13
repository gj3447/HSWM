/** Reproducible qualification against the pinned official SHACL Core suite. */
import { isAbsolute, relative, resolve, sep } from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"
import { Effect, Either } from "effect"
import { Parser, Store, Writer, DataFactory } from "n3"
import type { Term, DatasetCore, Quad_Object } from "@rdfjs/types"
import { PosixFileSystem } from "./effect-posix-filesystem.js"
import { BoundedSubprocess } from "./effect-bounded-subprocess.js"
import { KgBundleError, kgCanonicalJson, kgSha256 } from "./native-kg-bundle-domain.js"
import { loadKgVendorEngines } from "./native-kg-vendor.js"

const MF = "http://www.w3.org/2001/sw/DataAccess/tests/test-manifest#"
const SH = "http://www.w3.org/ns/shacl#"
const SHT = "http://www.w3.org/ns/shacl-test#"
const RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
const COMMIT = "b7844c776844b4927e1e79393ed05ed8bb80ee11"
const TREE = "04c1b65bd3e338546ba2d99174f3c5a305da04d3"
const error = (detail: string) => new KgBundleError({ detail })
const objects = (graph: DatasetCore, subject: Term | null, predicate: string): readonly Term[] => [...graph].filter(q => (subject === null || subject.equals(q.subject)) && q.predicate.value === predicate).map(q => q.object)
const one = (graph: DatasetCore, subject: Term, predicate: string): Effect.Effect<Term, KgBundleError> => {
  const values = objects(graph, subject, predicate)
  return values.length === 1 ? Effect.succeed(values[0]!) : Effect.fail(error(`expected exactly one ${predicate}`))
}
/** Official W3C comparison normalization: pinned index.html lines 158–203.
 * Remove nested details, retain expected messages, clone path structures.
 * Read paths from each report, never by merging it with the shapes graph.
 */
export const normalizedShaclReport = (graph: DatasetCore, report: Term, expectedMessages: readonly Term[]): Either.Either<string, KgBundleError> => Either.gen(function* () {
  if (!objects(graph, report, RDF + "type").some(t => t.value === SH + "ValidationReport")) return yield* Either.left(error("report lacks ValidationReport type"))
  const conforms = objects(graph, report, SH + "conforms")
  if (conforms.length !== 1 || conforms[0]!.termType !== "Literal" || !["true", "false"].includes(conforms[0]!.value) || conforms[0]!.datatype.value !== "http://www.w3.org/2001/XMLSchema#boolean") return yield* Either.left(error("report needs one canonical boolean conforms value"))
  const output = new Store(), root = DataFactory.blankNode()
  const clonePath = (value: Term, ancestors: ReadonlySet<string> = new Set()): Either.Either<Quad_Object, KgBundleError> => Either.gen(function* () {
    if (value.termType === "NamedNode" || value.termType === "Literal") return value
    if (value.termType !== "BlankNode" || ancestors.has(value.value)) return yield* Either.left(error("invalid or cyclic report path"))
    const node = DataFactory.blankNode(), next = new Set([...ancestors, value.value])
    const rows = [...graph].filter(q => q.subject.equals(value))
    const sequence = rows.some(q => q.predicate.value === RDF + "first")
    const relevant = rows.filter(q => sequence ? [RDF + "first", RDF + "rest"].includes(q.predicate.value) : ["alternativePath", "inversePath", "zeroOrMorePath", "oneOrMorePath", "zeroOrOnePath"].some(p => q.predicate.value === SH + p))
    if (relevant.length === 0) return yield* Either.left(error("report path has no RDF structure"))
    for (const row of relevant) output.addQuad(node, row.predicate, yield* clonePath(row.object, next))
    return node
  })
  output.addQuad(root, DataFactory.namedNode(RDF + "type"), DataFactory.namedNode(SH + "ValidationReport"))
  for (const value of objects(graph, report, SH + "conforms")) {
    if (value.termType !== "Literal") return yield* Either.left(error("conforms must be a literal"))
    output.addQuad(root, DataFactory.namedNode(SH + "conforms"), value)
  }
  for (const result of objects(graph, report, SH + "result")) {
    if (!objects(graph, result, RDF + "type").some(t => t.value === SH + "ValidationResult")) return yield* Either.left(error("result lacks ValidationResult type"))
    const node = DataFactory.blankNode()
    output.addQuad(root, DataFactory.namedNode(SH + "result"), node)
    output.addQuad(node, DataFactory.namedNode(RDF + "type"), DataFactory.namedNode(SH + "ValidationResult"))
    for (const key of ["focusNode", "resultPath", "resultSeverity", "sourceConstraint", "sourceConstraintComponent", "sourceShape", "value", "resultMessage"]) for (const value of objects(graph, result, SH + key)) {
      if (key === "resultMessage" && !expectedMessages.some(t => t.equals(value))) continue
      if (!["NamedNode", "Literal", "BlankNode"].includes(value.termType)) return yield* Either.left(error("unsupported report term"))
      const object = key === "resultPath" ? yield* clonePath(value) : value as Quad_Object
      output.addQuad(node, DataFactory.namedNode(SH + key), object)
    }
  }
  return new Writer({ format: "N-Quads" }).quadsToString([...output])
})
export const qualifyNativeShaclCore = (checkout: string) => Effect.gen(function* () {
  const fs = yield* PosixFileSystem, subprocess = yield* BoundedSubprocess
  const root = yield* fs.realpath(resolve(checkout), "qualification checkout")
  const git = (args: readonly string[]) => subprocess.observe({ argv: ["git", "-C", root, ...args], cwd: root, environment: {}, timeoutMs: 30_000, maximumOutputBytes: 4096 }).pipe(Effect.flatMap(result => result.exitCode === 0 && result.launchError === null && !result.timedOut && !result.outputTruncated ? Effect.succeed(Buffer.from(result.stdout).toString("utf8").trim()) : Effect.fail(error("suite Git source pin check failed"))))
  if ((yield* git(["rev-parse", "HEAD"])) !== COMMIT || (yield* git(["rev-parse", "HEAD:data-shapes-test-suite"])) !== TREE) return yield* Effect.fail(error("official SHACL suite commit/tree mismatch"))
  if ((yield* git(["status", "--porcelain", "--", "data-shapes-test-suite", "LICENSE.md"])) !== "") return yield* Effect.fail(error("official SHACL checkout has modified or untracked suite files"))
  const license = yield* fs.readRegularBounded(resolve(root, "LICENSE.md"), { maximumBytes: 1_048_576, operation: "suite license" })
  if (kgSha256(license.bytes) !== "6e57fea82f0488b42c47fee06e66b98849b64cc721714ad5fb520d3e84b4d4b9") return yield* Effect.fail(error("suite license pin mismatch"))
  const selected = resolve(root, "data-shapes-test-suite")
  const loaded = new Map<string, { readonly graph: Store; readonly sha256: string }>()
  const load = (uri: string) => Effect.gen(function* () {
    const path = yield* Effect.try({ try: () => fileURLToPath(uri), catch: () => error("suite reference must be local file URI") })
    const canonical = yield* fs.realpath(path, "suite reference containment")
    const rel = relative(selected, canonical)
    if (isAbsolute(rel) || rel === ".." || rel.startsWith(`..${sep}`)) return yield* Effect.fail(error("suite reference escapes pinned tree"))
    const cached = loaded.get(canonical)
    if (cached !== undefined) return cached.graph
    const input = yield* fs.readRegularBounded(canonical, { maximumBytes: 16 * 1024 * 1024, operation: "suite RDF input" })
    const graph = yield* Effect.try({ try: () => new Store(new Parser({ format: "Turtle", baseIRI: pathToFileURL(canonical).href }).parse(new TextDecoder("utf-8", { fatal: true }).decode(input.bytes))), catch: () => error("suite Turtle parse failed") })
    loaded.set(canonical, { graph, sha256: kgSha256(input.bytes) })
    return graph
  })
  const pending = [pathToFileURL(resolve(selected, "tests/core/manifest.ttl")).href]
  const visited = new Set<string>()
  const entries: { readonly graph: Store; readonly entry: Term }[] = []
  while (pending.length > 0) {
    const uri = pending.pop()!
    if (visited.has(uri)) continue
    visited.add(uri)
    const graph = yield* load(uri)
    pending.push(...objects(graph, null, MF + "include").map(t => t.value))
    for (const q of graph) if (q.predicate.value === RDF + "type" && q.object.value === SHT + "Validate" && objects(graph, q.subject, MF + "status").some(t => t.value === SHT + "approved")) entries.push({ graph, entry: q.subject })
  }
  if (entries.length === 0) return yield* Effect.fail(error("official approved Core test set is empty"))
  const { SHACLValidator, canonize } = yield* loadKgVendorEngines
  const results = yield* Effect.forEach(entries.sort((a, b) => a.entry.value.localeCompare(b.entry.value)), ({ graph, entry }) => Effect.gen(function* () {
    const action = yield* one(graph, entry, MF + "action"), expected = yield* one(graph, entry, MF + "result")
    const data = yield* load((yield* one(graph, action, SHT + "dataGraph")).value)
    const shapes = yield* load((yield* one(graph, action, SHT + "shapesGraph")).value)
    const expectedConforms = (yield* one(graph, expected, SH + "conforms")).value === "true"
    const report = yield* Effect.tryPromise({ try: () => new SHACLValidator(shapes, { importGraph: () => Promise.reject(error("suite OWL imports forbidden")) }).validate(data), catch: cause => error(cause instanceof Error ? cause.message : "SHACL validation failed") })
    const expectedResults = objects(graph, expected, SH + "result")
    const messages = expectedResults.flatMap(r => objects(graph, r, SH + "resultMessage"))
    const expectedNq = yield* normalizedShaclReport(graph, expected, messages)
    const actualNq = yield* normalizedShaclReport(report.dataset, report.term, messages)
    const canonicalize = (nq: string) => Effect.tryPromise({ try: signal => canonize(nq, { algorithm: "RDFC-1.0", inputFormat: "application/n-quads", format: "application/n-quads", maxWorkFactor: 4, signal }), catch: cause => error(`report graph isomorphism comparison failed: ${cause instanceof Error ? cause.message : "unknown vendor error"}`) }).pipe(Effect.timeoutFail({ duration: "30 seconds", onTimeout: () => error("bounded report canonicalization timed out") }))
    const expectedSignature = yield* canonicalize(expectedNq)
    const actualSignature = yield* canonicalize(actualNq)
    return { id: entry.value.replace(pathToFileURL(selected).href, ""), passed: expectedConforms === report.conforms && kgCanonicalJson(expectedSignature) === kgCanonicalJson(actualSignature), expectedConforms, actualConforms: report.conforms, expectedResultCount: expectedResults.length, actualResultCount: report.results.length, expectedSha256: kgSha256(kgCanonicalJson(expectedSignature)), actualSha256: kgSha256(kgCanonicalJson(actualSignature)), ...(kgCanonicalJson(expectedSignature) === kgCanonicalJson(actualSignature) ? {} : { expectedSignature, actualSignature }) }
  }).pipe(Effect.either, Effect.map(result => Either.isRight(result) ? result.right : { id: entry.value.replace(pathToFileURL(selected).href, ""), passed: false, error: result.left.detail })), { concurrency: 1 })
  return { schema_version: "hswm-native-shacl-qualification/v1", authority: "INDEPENDENT_ENGINE_AGAINST_PINNED_OFFICIAL_W3C_SUITE", engine: "rdf-validate-shacl@0.6.5", source: { commit: COMMIT, tree: TREE, licenseSha256: kgSha256(license.bytes) }, comparison: "OFFICIAL_W3C_REPORT_NORMALIZATION_THEN_RDFC10_GRAPH_ISOMORPHISM", canonicalization: { engine: "rdf-canonize@5.0.0", algorithm: "RDFC-1.0", maxWorkFactor: 4, timeoutMs: 30_000 }, selected: entries.length, passed: results.filter(r => r.passed).length, failed: results.filter(r => !r.passed).length, excluded: [], status: results.every(r => r.passed) ? "PASS" : "FAIL", files: [...loaded.entries()].map(([path, record]) => ({ path: relative(root, path), sha256: record.sha256 })).sort((a, b) => a.path.localeCompare(b.path)), results, claim_ceiling: "ENGINEERING_QUALIFICATION_ONLY_NOT_HSWM_EFFICACY_OR_CANONICAL_AUTHORITY" }
})
