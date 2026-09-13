/**
 * Pure validation for the three source-pinned development KG projections.
 * These projections are read-only engineering references, never canonical
 * state, a Permit, learning admission, causal credit, or efficacy evidence.
 */
import { Data, Effect, Either } from "effect"
import { compileKgBundle, kgCanonicalJson, kgSha256, type KgBundle, type KgBundleProjection } from "./native-kg-bundle-domain.js"
import { decodeGeneralJsonBytes } from "./general-json-domain.js"
import { validateKgShacl } from "./native-kg-standards.js"

export class NativeDevelopmentProjectionError extends Data.TaggedError("NativeDevelopmentProjectionError")<{
  readonly detail: string
}> {}

export type ProjectionKind = "development-work" | "frontier-learning" | "development-day"
export interface ProjectionContract {
  readonly kind: ProjectionKind
  readonly sourceId: string
  readonly bundleUid: string
  readonly schemaVersion: string
  readonly sourceCommit?: string
  readonly primarySourcePath?: string
  readonly userUid?: string
  readonly owner?: string
  readonly relations: readonly string[]
  readonly bindingOrigin: "historical" | "current"
  readonly expectedStatus: string
  readonly expectedAuthorityBoundary?: string
  readonly requiredTop: readonly string[]
  readonly optionalTop: readonly string[]
}
export interface HistoricalBlobSource {
  readonly readBlob: (commit: string, path: string) => Uint8Array | undefined
  /** Current checked-out bytes used only by the frontier source-index contract. */
  readonly readPath: (path: string) => Uint8Array | undefined
}
const fail = (detail: string): Either.Either<never, NativeDevelopmentProjectionError> => Either.left(new NativeDevelopmentProjectionError({ detail }))
const record = (value: unknown): value is Readonly<Record<string, unknown>> => typeof value === "object" && value !== null && !Array.isArray(value)
const text = (value: unknown): value is string => typeof value === "string"
const rows = (value: unknown): readonly Readonly<Record<string, unknown>>[] | undefined => Array.isArray(value) && value.every(record) ? value : undefined
const exactKeys = (value: Readonly<Record<string, unknown>>, required: readonly string[], optional: readonly string[]): boolean => {
  const keys = Object.keys(value)
  return keys.length >= required.length && required.every(key => Object.hasOwn(value, key)) && keys.every(key => required.includes(key) || optional.includes(key))
}
const safePath = (value: unknown): value is string => text(value) && value.length > 0 && !value.startsWith("/") && !value.split("/").some(part => part === "." || part === "..") && /^[A-Za-z0-9_][A-Za-z0-9_./:+-]{0,255}$/.test(value)
const sha = (value: unknown): value is string => text(value) && /^[0-9a-f]{64}$/.test(value)
const asBundle = (value: unknown): KgBundle | undefined => record(value) ? value as KgBundle : undefined

/** Validates authority, fixed snapshot bindings, endpoints, and KG semantics. */
export const validateNativeDevelopmentProjection = (
  value: unknown,
  contract: ProjectionContract,
  blobs: HistoricalBlobSource
): Either.Either<KgBundle, NativeDevelopmentProjectionError> => {
  if (!record(value) || !exactKeys(value, contract.requiredTop, contract.optionalTop)) return fail("ontology top-level shape drift")
  if (value["schema_version"] !== contract.schemaVersion || value["bundle_uid"] !== contract.bundleUid) return fail("ontology identity drift")
  if (value["status"] !== contract.expectedStatus || !text(value["nonclaim"]) || (contract.expectedAuthorityBoundary !== undefined && value["authority_boundary"] !== contract.expectedAuthorityBoundary)) return fail("ontology status or authority boundary drift")
  if (contract.sourceCommit !== undefined && (!/^[0-9a-f]{40}$/.test(contract.sourceCommit) || value["source_accessed_on"] !== undefined && !text(value["source_accessed_on"]))) return fail("fixed source commit is invalid")
  const bindings = rows(value["artifact_bindings"])
  if (bindings === undefined || bindings.length === 0) return fail("artifact_bindings must be non-empty")
  const bound = new Map<string, string>()
  for (const binding of bindings) {
    if (Object.keys(binding).length !== 2 || !safePath(binding["path"]) || !sha(binding["sha256"]) || bound.has(binding["path"])) return fail("artifact binding shape is invalid")
    const blob = contract.bindingOrigin === "current" ? blobs.readPath(binding["path"]) : blobs.readBlob(contract.sourceCommit ?? "", binding["path"])
    if (blob === undefined || kgSha256(blob) !== binding["sha256"]) return fail(contract.bindingOrigin === "current" ? "artifact binding hash drift" : `source-commit artifact hash drift: ${binding["path"]}`)
    bound.set(binding["path"], binding["sha256"])
  }
  if (contract.primarySourcePath !== undefined && !bound.has(contract.primarySourcePath)) return fail("primary source binding is required")
  const nodes = rows(value["nodes"])
  const anchors = rows(value["anchors"])
  const relations = rows(value["relations"])
  if (nodes === undefined || nodes.length === 0 || anchors === undefined || relations === undefined) return fail("node, anchor, or relation shape")
  const nodeIds = new Set<string>()
  let userFound = false
  for (const node of nodes) {
    const properties = record(node["properties"]) ? node["properties"] : undefined
    const labels = Array.isArray(node["labels"]) && node["labels"].every(text) ? node["labels"] : undefined
    if (!text(node["uid"]) || nodeIds.has(node["uid"]) || properties === undefined || labels === undefined || labels.length === 0) return fail("node identity or shape")
    if ((contract.kind === "development-work" || contract.kind === "development-day") && properties["source_commit"] !== contract.sourceCommit) return fail("node source_commit must equal fixed snapshot")
    if ((contract.kind === "development-work" || contract.kind === "development-day") && (labels.length !== 2 || !labels.includes("AbstractNode") || !labels.includes("Concept"))) return fail("development projection node labels must be AbstractNode and Concept")
    const sourcePaths = properties["source_paths"]
    if (sourcePaths !== undefined && (!Array.isArray(sourcePaths) || !sourcePaths.every(path => text(path) && bound.has(path)))) return fail("node source_paths must be bound")
    if (node["uid"] === contract.userUid) {
      userFound = true
      if (properties["authority_class"] !== "USER_PRIMARY" || properties["ontology_authority"] !== "USER_PRIMARY" || properties["ontology_authority_class_v1"] !== "USER_PRIMARY" || properties["responsibility_owner"] !== "user:hswm-development-direction" || properties["role"] !== "USER_DIRECT_REQUEST" || properties["standard_graph_role"] !== "USER_DIRECT_REQUEST" || properties["status"] !== "USER_REQUEST_RECORDED_NOT_EFFICACY") return fail("user request authority, role, or status")
      if (contract.primarySourcePath === undefined || properties["source_path"] !== contract.primarySourcePath || properties["source_sha256"] !== bound.get(contract.primarySourcePath)) return fail("user request quote/source binding")
      const source = blobs.readBlob(contract.sourceCommit ?? "", contract.primarySourcePath)
      let quote: string | undefined
      try { quote = source === undefined ? undefined : new TextDecoder("utf-8", { fatal: true }).decode(source).replace(/\n+$/, "") } catch { quote = undefined }
      if (quote === undefined || properties["verbatim_text"] !== quote) return fail("user request quote/source binding")
    } else if (contract.kind === "frontier-learning") {
      const authority = properties["authority_class"], role = properties["standard_graph_role"]
      if (authority !== "SECONDARY_AI" && (authority !== "USER_PRIMARY" || role !== "USER_DIRECT_REQUEST")) return fail("only explicit USER_PRIMARY direct-request records are allowed")
      if (node["uid"] === contract.bundleUid && (!text(properties["source_commit"]) || !/^[0-9a-f]{40}$/.test(properties["source_commit"]))) return fail("bundle node must carry source_commit")
    } else if (contract.kind === "development-day") {
      if (properties["authority_class"] !== "SECONDARY_AI" || properties["ontology_authority"] === "USER_PRIMARY" || properties["ontology_authority_class_v1"] !== "SECONDARY_AI" || properties["responsibility_owner"] !== contract.owner) return fail("non-user node authority promotion or owner drift")
    } else if (contract.kind === "development-work" && (properties["authority_class"] !== "SECONDARY_AI" || properties["ontology_authority_class_v1"] !== "SECONDARY_AI")) return fail("development-work nodes must be SECONDARY_AI")
    nodeIds.add(node["uid"])
  }
  if (!nodeIds.has(contract.bundleUid) || (contract.userUid !== undefined && !userFound)) return fail("bundle root or user request missing")
  const anchorIds = new Set<string>()
  for (const anchor of anchors) {
    if (!text(anchor["uid"]) || anchor["uid"].length === 0 || anchorIds.has(anchor["uid"]) || nodeIds.has(anchor["uid"])) return fail("anchor identity")
    anchorIds.add(anchor["uid"])
  }
  const primaryPath = contract.primarySourcePath
  const primarySources = new Set(primaryPath === undefined ? [] : nodes.filter(node => node["uid"] !== contract.userUid && record(node["properties"]) && node["properties"]["source_path"] === primaryPath && node["properties"]["source_sha256"] === bound.get(primaryPath) && Array.isArray(node["properties"]["source_paths"]) && node["properties"]["source_paths"].includes(primaryPath) && (node["properties"]["role"] === "SOURCE_ARTIFACT" || node["properties"]["standard_graph_role"] === "SOURCE_ARTIFACT")).map(node => String(node["uid"])))
  let userSource = false
  for (const relation of relations) {
    if (!text(relation["type"]) || !contract.relations.includes(relation["type"])) return fail("relation type outside allowlist")
    if (relation["authority_class"] !== "SECONDARY_AI" || !text(relation["from_uid"]) || !nodeIds.has(relation["from_uid"]) || !text(relation["to_uid"]) || !(nodeIds.has(relation["to_uid"]) || anchorIds.has(relation["to_uid"]))) return fail("relation authority or endpoint")
    if (contract.userUid !== undefined && relation["from_uid"] === contract.userUid && relation["type"] === "HAS_SOURCE" && primarySources.has(String(relation["to_uid"]))) userSource = true
  }
  if (contract.userUid !== undefined && !userSource) return fail("user request must HAS_SOURCE its primary artifact node")
  const counts = record(value["expected_counts"]) ? value["expected_counts"] : undefined
  if (counts === undefined || counts["nodes"] !== nodes.length || counts["anchors"] !== anchors.length || counts["relations"] !== relations.length) return fail("expected graph counts drift")
  const raw = new TextEncoder().encode(kgCanonicalJson(value))
  const compiled = compileKgBundle([{ sourceId: `native-${contract.kind}`, rawBytes: raw, sha256: kgSha256(raw), byteLength: raw.byteLength }])
  return Either.isLeft(compiled) ? fail(compiled.left.detail) : Either.right(asBundle(value)!)
}

export const developmentProjectionDigest = (value: unknown): string => kgSha256(kgCanonicalJson(value))
/** Compiles only a previously validated source-bound bundle into its read-only KG view. */
export const compileNativeDevelopmentProjection = (value: unknown, rawBytes: Uint8Array, contract: ProjectionContract, blobs: HistoricalBlobSource): Either.Either<KgBundleProjection, NativeDevelopmentProjectionError> => {
  const decoded = decodeGeneralJsonBytes(rawBytes, { maximumBytes: 16 * 1024 * 1024, maximumDepth: 32 })
  if (Either.isLeft(decoded) || kgCanonicalJson(decoded.right) !== kgCanonicalJson(value)) return fail("raw source bytes do not decode to supplied projection")
  const valid = validateNativeDevelopmentProjection(value, contract, blobs)
  if (Either.isLeft(valid)) return fail(valid.left.detail)
  const compiled = compileKgBundle([{ sourceId: contract.sourceId, rawBytes, sha256: kgSha256(rawBytes), byteLength: rawBytes.byteLength }])
  return Either.isLeft(compiled) ? fail(compiled.left.detail) : Either.right(compiled.right)
}
/** Explicitly injected bounded publisher; this domain never provides a live gateway. */
export interface NativeDevelopmentProjectionPublisher {
  readonly publish: (bundle: KgBundle, projectionSha256: string) => Effect.Effect<Readonly<Record<string, number>>, NativeDevelopmentProjectionError>
}
/** Bounded export sink. Callers choose a directory; this domain only names the four derived files. */
export interface NativeDevelopmentProjectionExportWriter {
  readonly write: (relativePath: string, bytes: Uint8Array) => Effect.Effect<void, NativeDevelopmentProjectionError>
}
export interface NativeDevelopmentProjectionShaclReport {
  readonly conforms: boolean
  readonly results: readonly unknown[]
  readonly claim_ceiling: string
  readonly engine: string
  readonly profile: string
}
export const exportNativeDevelopmentProjection = (projection: KgBundleProjection, writer: NativeDevelopmentProjectionExportWriter): Effect.Effect<void, NativeDevelopmentProjectionError> =>
  Effect.gen(function* () {
    const manifest = new TextEncoder().encode(`${kgCanonicalJson(projection.descriptor)}\n`)
    yield* writer.write("view.nq", projection.nquads)
    yield* writer.write("manifest.json", manifest)
    yield* writer.write("prov.jsonld", new Uint8Array([...projection.provO, 10]))
  })
/** Writes the historical four-file export only after bounded SHACL Core validation. */
export const exportValidatedNativeDevelopmentProjection = (projection: KgBundleProjection, shapes: Uint8Array, writer: NativeDevelopmentProjectionExportWriter): Effect.Effect<NativeDevelopmentProjectionShaclReport, NativeDevelopmentProjectionError> =>
  Effect.gen(function* () {
    const report = yield* validateKgShacl(projection, shapes).pipe(Effect.mapError(error => new NativeDevelopmentProjectionError({ detail: error.detail })))
    yield* exportNativeDevelopmentProjection(projection, writer)
    yield* writer.write("validation.json", new TextEncoder().encode(`${kgCanonicalJson(report)}\n`))
    return report
  })
/** Dispatches only reviewed exact bytes after full source-bound validation. */
export const applyReviewedNativeDevelopmentProjection = (value: unknown, rawBytes: Uint8Array, reviewedSha256: string, contract: ProjectionContract, blobs: HistoricalBlobSource, publisher: NativeDevelopmentProjectionPublisher): Effect.Effect<Readonly<Record<string, number>>, NativeDevelopmentProjectionError> => {
  if (!/^[0-9a-f]{64}$/.test(reviewedSha256) || kgSha256(rawBytes) !== reviewedSha256) return Effect.fail(new NativeDevelopmentProjectionError({ detail: "reviewed artifact SHA pin is not installed or does not match" }))
  const decoded = decodeGeneralJsonBytes(rawBytes, { maximumBytes: 16 * 1024 * 1024, maximumDepth: 32 })
  if (Either.isLeft(decoded) || kgCanonicalJson(decoded.right) !== kgCanonicalJson(value)) return Effect.fail(new NativeDevelopmentProjectionError({ detail: "reviewed raw bytes do not match the supplied projection value" }))
  const valid = validateNativeDevelopmentProjection(value, contract, blobs)
  return Either.isLeft(valid) ? Effect.fail(valid.left) : publisher.publish(valid.right, reviewedSha256)
}
