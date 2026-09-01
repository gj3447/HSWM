import { createHash } from "node:crypto"

import { Data, Either } from "effect"

import {
  canonicalAtomV2SchemaContentBytes,
  sameCanonicalAtomV2SchemaBinding
} from "./canonical-atom-v2-content-bound.js"
import {
  makeCanonicalAtomV2ContentDescriptor,
  sameCanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2SchemaContentBinding
} from "./canonical-atom-v2-content.js"
import {
  snapshotCanonicalAtomV2State,
  validateHSWMCanonicalSchemaV2,
  validateCanonicalAtomV2State,
  type CanonicalAtomV2State
} from "./canonical-atom-v2-domain.js"
import {
  canonicalAtomV2KeyId,
  type HSWMCanonicalSchemaV2
} from "./canonical-atom-v2-schema.js"
import {
  canonicalAtomV2StateSha256,
  decodeCanonicalAtomV2StateJournalRecordBytes,
  describeCanonicalAtomV2StateJournalRecord,
  type CanonicalAtomV2StateJournalRecordDescriptor
} from "./canonical-atom-v2-state-journal.js"
import {
  canonicalJsonBytes,
  decodeCanonicalJsonBytes,
  HSWM_CANONICAL_JSON_VERSION
} from "./canonical-atom-v2-json.js"

/** A deterministic, blank-node-free RDF 1.1 N-Quads profile; not an RDFC claim. */
export const HSWM_CANONICAL_ATOM_V2_RDF_PROJECTION_V1_CONTRACT_VERSION =
  "hswm-canonical-atom-v2-rdf-projection/v1" as const
export const HSWM_CANONICAL_ATOM_V2_RDF_PROJECTION_V1_MEDIA_TYPE =
  "application/vnd.hswm.canonical-atom-v2-rdf-projection+json" as const
export const HSWM_CANONICAL_ATOM_V2_RDF_NQUADS_MEDIA_TYPE =
  "application/n-quads" as const
export const HSWM_CANONICAL_ATOM_V2_RDF_PROFILE =
  "RDF_1_1_N_QUADS_BLANK_NODE_FREE_DETERMINISTIC_PROFILE" as const

const BASE = "https://hswm.invalid/canonical-atom-v2/rdf/v1/"
const XSD = "http://www.w3.org/2001/XMLSchema#"
const RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
const HSWM = `${BASE}vocab/`

export interface CanonicalAtomV2RdfProjectionSource {
  readonly journalLineageId: string
  readonly schemaBinding: CanonicalAtomV2SchemaContentBinding
  readonly state: CanonicalAtomV2State
  readonly tailDescriptor: CanonicalAtomV2StateJournalRecordDescriptor
  readonly tailRecordBytes: Uint8Array
}

export interface CanonicalAtomV2RdfProjectionManifest {
  readonly _tag: "CanonicalAtomV2RdfProjectionManifest"
  readonly contractVersion: typeof HSWM_CANONICAL_ATOM_V2_RDF_PROJECTION_V1_CONTRACT_VERSION
  readonly encoding: typeof HSWM_CANONICAL_JSON_VERSION
  readonly rdfProfile: typeof HSWM_CANONICAL_ATOM_V2_RDF_PROFILE
  readonly source: {
    readonly journalLineageId: string
    readonly schemaBinding: CanonicalAtomV2SchemaContentBinding
    readonly schemaCanonicalBase64Url: string
    readonly state: CanonicalAtomV2State
    readonly stateSha256: string
    readonly tailDescriptor: CanonicalAtomV2StateJournalRecordDescriptor
    readonly tailRecordBase64Url: string
  }
  readonly compiler: {
    readonly contractVersion: typeof HSWM_CANONICAL_ATOM_V2_RDF_PROJECTION_V1_CONTRACT_VERSION
    readonly contractSha256: string
    readonly profileCanonicalBase64Url: string
    readonly profile: CanonicalAtomV2ContentDescriptor
    readonly implementationBinding: "PROFILE_BOUND_NOT_EXECUTABLE_ARTIFACT_BOUND"
  }
  readonly mapping: "ROLE_PRESERVING_REIFIED_TYPED_REFERENCE"
  readonly manifestRetains: ReadonlyArray<"CANONICAL_SCHEMA_BYTES" | "CANONICAL_STATE_METADATA" | "TAIL_RECORD_BYTES" | "ATOM_KEY_OWNER_CONTENT_DESCRIPTOR_PROVENANCE_TYPED_REFERENCE">
  readonly rdfDatasetOmits: ReadonlyArray<
    | "RAW_CONTENT_PAYLOAD_BYTES"
    | "FULL_JOURNAL_CHAIN"
    | "TAIL_RECORD_STRUCTURE"
    | "STATE_BOOTSTRAP_AND_ACCEPTED_TRANSITIONS"
    | "ATOM_LIFECYCLE_AND_DECOMPOSED_KEY"
    | "SCHEMA_CONSTRAINTS"
  >
  readonly manifestOmits: ReadonlyArray<"RAW_CONTENT_PAYLOAD_BYTES" | "FULL_JOURNAL_CHAIN">
  readonly referenceOrder: "SOURCE_REFERENCE_ARRAY_INDEX_IS_RDF_ORDINAL"
  readonly writeBack: "FORBIDDEN"
  readonly invalidatedBy: ReadonlyArray<"SCHEMA_CONTENT_BINDING_CHANGED" | "STATE_DIGEST_CHANGED" | "TAIL_DESCRIPTOR_OR_BYTES_CHANGED" | "COMPILER_PROFILE_CHANGED">
  readonly nonclaim: "RDF_PROJECTION_ONLY_NOT_CANONICAL_HSWM_STATE_COGNITION_LEARNING_PERMISSION_OR_EFFICACY"
  readonly sourceAttestation: "CALLER_SUPPLIED_SELF_CONSISTENT_BUNDLE_NOT_DURABLE_RECOVERY_ATTESTED"
  readonly counts: {
    readonly atomVersions: number
    readonly typedReferences: number
    readonly relationAtomVersions: number
    readonly emittedQuads: number
    readonly namedGraphs: 4
    readonly sourceTraceCoverage: {
      readonly schemaContentBinding: "EXACT"
      readonly stateDigest: "EXACT"
      readonly tailDescriptorAndBytes: "EXACT"
    }
  }
  readonly dataset: CanonicalAtomV2ContentDescriptor
}

export interface CanonicalAtomV2RdfProjection {
  readonly manifest: CanonicalAtomV2RdfProjectionManifest
  readonly nquads: Uint8Array
}

export class CanonicalAtomV2RdfProjectionError extends Data.TaggedError(
  "CanonicalAtomV2RdfProjectionError"
)<{
  readonly code:
    | "INPUT_INVALID"
    | "SCHEMA_BINDING_STALE"
    | "STATE_INVALID"
    | "TAIL_INVALID"
    | "TAIL_STALE"
    | "CANONICAL_ENCODING_INVALID"
    | "PROJECTION_INVALID"
    | "PROJECTION_TAMPERED"
  readonly detail: string
}> {}

const fail = (
  code: CanonicalAtomV2RdfProjectionError["code"],
  detail: string
): Either.Either<never, CanonicalAtomV2RdfProjectionError> =>
  Either.left(new CanonicalAtomV2RdfProjectionError({ code, detail }))

const total = <A>(run: () => Either.Either<A, CanonicalAtomV2RdfProjectionError>): Either.Either<A, CanonicalAtomV2RdfProjectionError> => {
  try { return run() } catch { return fail("INPUT_INVALID", "runtime input raised while validating the fail-closed RDF projection boundary") }
}

const sha256 = (bytes: Uint8Array): string =>
  createHash("sha256").update(bytes).digest("hex")

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength && left.every((byte, index) => byte === right[index])

const iri = (segment: string): string => `<${BASE}${segment}>`
const encoded = (value: string): string => encodeURIComponent(value)
const atomIri = (keyId: string): string => iri(`atom/${encoded(keyId)}`)
const referenceIri = (keyId: string, ordinal: number): string =>
  iri(`reference/${encoded(keyId)}/${ordinal}`)
const graph = (
  sourceSha256: string,
  compilerProfileSha256: string,
  name: "state" | "schema" | "provenance" | "evidence"
): string => iri(`dataset/${sourceSha256}/${compilerProfileSha256}/graph/${name}`)
const predicate = (name: string): string => `<${HSWM}${name}>`
const type = (name: string): string => `<${HSWM}${name}>`
const literal = (value: string): string =>
  `"${value.replace(/\\/g, "\\\\").replace(/"/g, "\\\"").replace(/\n/g, "\\n").replace(/\r/g, "\\r").replace(/\t/g, "\\t").replace(/[\u0000-\u001f]/g, (character) => `\\u${character.charCodeAt(0).toString(16).padStart(4, "0")}`)}"`
const typed = (value: string | number, datatype: string): string =>
  `${literal(String(value))}^^<${datatype}>`
const quad = (subject: string, predicateTerm: string, object: string, graphTerm: string): string =>
  `${subject} ${predicateTerm} ${object} ${graphTerm} .\n`

const compilerContractBytes = (): Either.Either<Uint8Array, CanonicalAtomV2RdfProjectionError> => {
  const bytes = canonicalJsonBytes({
    blankNodePolicy: "FORBIDDEN_BY_CONSTRUCTION",
    canonicalization: "NONE_LOCAL_DETERMINISTIC_PROFILE_NOT_RDFC",
    contractVersion: HSWM_CANONICAL_ATOM_V2_RDF_PROJECTION_V1_CONTRACT_VERSION,
    graphNaming: "TAIL_AND_COMPILER_PROFILE_SHA256_SCOPED_FIXED_ROLE_SUFFIX",
    iriEscaping: "PERCENT_ENCODED_HTTPS",
    mapping: "ROLE_PRESERVING_REIFIED_TYPED_REFERENCE",
    rdfProfile: HSWM_CANONICAL_ATOM_V2_RDF_PROFILE,
    serialization: "NQUADS_UTF8_LF",
    sortComparator: "UTF8_BYTE_LEXICOGRAPHIC"
  })
  return Either.isLeft(bytes)
    ? fail("CANONICAL_ENCODING_INVALID", "compiler contract cannot be canonically encoded")
    : Either.right(Uint8Array.from(bytes.right))
}

const descriptorEqual = (
  left: CanonicalAtomV2StateJournalRecordDescriptor,
  right: CanonicalAtomV2StateJournalRecordDescriptor
): boolean => left.mediaType === right.mediaType && left.byteLength === right.byteLength && left.sha256 === right.sha256

const snapshotDescriptor = (input: CanonicalAtomV2ContentDescriptor): CanonicalAtomV2ContentDescriptor =>
  Object.freeze({
    mediaType: input.mediaType,
    byteLength: input.byteLength,
    sha256: input.sha256
  })

const snapshotTailDescriptor = (input: CanonicalAtomV2StateJournalRecordDescriptor): CanonicalAtomV2StateJournalRecordDescriptor =>
  Object.freeze({
    mediaType: input.mediaType,
    byteLength: input.byteLength,
    sha256: input.sha256
  })

const hasExactOwnKeys = (
  input: object,
  expected: ReadonlyArray<string>
): boolean => {
  const keys = Reflect.ownKeys(input)
  return keys.length === expected.length && expected.every((key) => keys.includes(key))
}

const isDescriptor = (input: unknown): input is CanonicalAtomV2ContentDescriptor =>
  typeof input === "object" && input !== null &&
  hasExactOwnKeys(input, ["mediaType", "byteLength", "sha256"]) &&
  typeof (input as { mediaType?: unknown }).mediaType === "string" &&
  typeof (input as { byteLength?: unknown }).byteLength === "number" &&
  Number.isSafeInteger((input as { byteLength: number }).byteLength) &&
  (input as { byteLength: number }).byteLength >= 0 &&
  (input as { byteLength: number }).byteLength <= 16_777_216 &&
  typeof (input as { sha256?: unknown }).sha256 === "string"

const isSchemaBinding = (input: unknown): input is CanonicalAtomV2SchemaContentBinding =>
  typeof input === "object" && input !== null &&
  hasExactOwnKeys(input, ["schemaVersion", "content"]) &&
  typeof (input as { schemaVersion?: unknown }).schemaVersion === "string" &&
  isDescriptor((input as { content?: unknown }).content)

const validateSource = (
  schemaInput: HSWMCanonicalSchemaV2,
  input: CanonicalAtomV2RdfProjectionSource
): Either.Either<{
  readonly schema: HSWMCanonicalSchemaV2
  readonly schemaBytes: Uint8Array
  readonly state: CanonicalAtomV2State
  readonly stateSha256: string
  readonly tailBytes: Uint8Array
}, CanonicalAtomV2RdfProjectionError> => {
  if (typeof input !== "object" || input === null || typeof input.journalLineageId !== "string" || input.journalLineageId.length === 0 || !(input.tailRecordBytes instanceof Uint8Array) || !isSchemaBinding(input.schemaBinding) || !isDescriptor(input.tailDescriptor)) {
    return fail("INPUT_INVALID", "projection source has an invalid journal lineage or tail bytes")
  }
  const schemaValidation = validateHSWMCanonicalSchemaV2(schemaInput)
  if (Either.isLeft(schemaValidation)) return fail("INPUT_INVALID", "schema is not semantically valid")
  const schemaBytes = canonicalAtomV2SchemaContentBytes(schemaValidation.right)
  if (Either.isLeft(schemaBytes)) return fail("INPUT_INVALID", "schema is not strictly valid")
  const schemaDescriptor = makeCanonicalAtomV2ContentDescriptor(
    "application/vnd.hswm.canonical-schema-v2+json", schemaBytes.right
  )
  if (Either.isLeft(schemaDescriptor)) return fail("INPUT_INVALID", "schema descriptor is invalid")
  const schema = schemaValidation.right
  if (!sameCanonicalAtomV2SchemaBinding(input.schemaBinding, {
    schemaVersion: schema.schemaVersion,
    content: schemaDescriptor.right
  })) return fail("SCHEMA_BINDING_STALE", "source schema binding differs from the exact validated schema bytes")
  const state = validateCanonicalAtomV2State(schema, input.state)
  if (Either.isLeft(state)) return fail("STATE_INVALID", state.left.detail)
  const stateSha = canonicalAtomV2StateSha256(state.right)
  if (Either.isLeft(stateSha)) return fail("STATE_INVALID", stateSha.left.detail)
  const tailBytes = Uint8Array.from(input.tailRecordBytes)
  const tail = decodeCanonicalAtomV2StateJournalRecordBytes(tailBytes)
  if (Either.isLeft(tail)) return fail("TAIL_INVALID", "tail record bytes are not strict canonical journal bytes")
  const tailDescriptor = describeCanonicalAtomV2StateJournalRecord(tail.right)
  if (Either.isLeft(tailDescriptor) || !descriptorEqual(input.tailDescriptor, tailDescriptor.right)) {
    return fail("TAIL_STALE", "tail descriptor does not exactly describe the supplied tail record bytes")
  }
  if (tail.right.journalLineageId !== input.journalLineageId || !sameCanonicalAtomV2SchemaBinding(tail.right.schema, input.schemaBinding) || tail.right.stateRevision !== state.right.revision || tail.right.resultingStateSha256 !== stateSha.right) {
    return fail("TAIL_STALE", "tail record does not bind this journal lineage, schema, revision, and state digest")
  }
  return Either.right(Object.freeze({ schema, schemaBytes: Uint8Array.from(schemaBytes.right), state: state.right, stateSha256: stateSha.right, tailBytes }))
}

const compileNquads = (source: {
  readonly schema: HSWMCanonicalSchemaV2
  readonly state: CanonicalAtomV2State
  readonly stateSha256: string
  readonly tailDescriptor: CanonicalAtomV2StateJournalRecordDescriptor
  readonly journalLineageId: string
  readonly schemaContentSha256: string
  readonly compilerContractSha256: string
}): Uint8Array => {
  const projectionIdentity = `${source.tailDescriptor.sha256}/${source.compilerContractSha256}`
  const dataset = iri(`dataset/${projectionIdentity}`)
  const stateGraph = graph(source.tailDescriptor.sha256, source.compilerContractSha256, "state")
  const schemaGraph = graph(source.tailDescriptor.sha256, source.compilerContractSha256, "schema")
  const provenanceGraph = graph(source.tailDescriptor.sha256, source.compilerContractSha256, "provenance")
  const evidenceGraph = graph(source.tailDescriptor.sha256, source.compilerContractSha256, "evidence")
  const lines: Array<string> = []
  lines.push(quad(dataset, `<${RDF}type>`, type("Dataset"), stateGraph))
  lines.push(quad(dataset, predicate("stateSha256"), literal(source.stateSha256), stateGraph))
  lines.push(quad(dataset, predicate("stateRevision"), typed(source.state.revision, `${XSD}nonNegativeInteger`), stateGraph))
  lines.push(quad(dataset, predicate("schemaVersion"), literal(source.schema.schemaVersion), schemaGraph))
  lines.push(quad(dataset, predicate("schemaContentSha256"), literal(source.schemaContentSha256), evidenceGraph))
  lines.push(quad(dataset, predicate("journalLineageId"), literal(source.journalLineageId), evidenceGraph))
  lines.push(quad(dataset, predicate("tailSha256"), literal(source.tailDescriptor.sha256), evidenceGraph))
  lines.push(quad(dataset, predicate("rdfProfile"), literal(HSWM_CANONICAL_ATOM_V2_RDF_PROFILE), evidenceGraph))
  lines.push(quad(dataset, predicate("mapping"), literal("ROLE_PRESERVING_REIFIED_TYPED_REFERENCE"), evidenceGraph))
  lines.push(quad(dataset, predicate("writeBack"), literal("FORBIDDEN"), evidenceGraph))
  lines.push(quad(dataset, predicate("nonclaim"), literal("RDF_PROJECTION_ONLY_NOT_CANONICAL_HSWM_STATE_COGNITION_LEARNING_PERMISSION_OR_EFFICACY"), evidenceGraph))
  lines.push(quad(dataset, predicate("compilerContractVersion"), literal(HSWM_CANONICAL_ATOM_V2_RDF_PROJECTION_V1_CONTRACT_VERSION), evidenceGraph))
  lines.push(quad(dataset, predicate("compilerContractSha256"), literal(source.compilerContractSha256), evidenceGraph))
  for (const atom of source.state.atoms) {
    const atomId = canonicalAtomV2KeyId(atom.key)
    const atomTerm = atomIri(atomId)
    const kindForm = source.schema.kinds.find((kind) => kind.kind === atom.kind)?.form
    lines.push(quad(atomTerm, `<${RDF}type>`, type(kindForm === "RELATION" ? "ReifiedRelationAtomVersion" : "CanonicalAtomVersion"), stateGraph))
    lines.push(quad(atomTerm, predicate("canonicalKey"), literal(atomId), stateGraph))
    lines.push(quad(atomTerm, predicate("kind"), literal(atom.kind), schemaGraph))
    lines.push(quad(atomTerm, predicate("kindForm"), literal(kindForm ?? "UNKNOWN"), schemaGraph))
    lines.push(quad(atomTerm, predicate("responsibilityOwner"), literal(atom.responsibilityOwner), schemaGraph))
    lines.push(quad(atomTerm, predicate("contentMediaType"), literal(atom.content.mediaType), stateGraph))
    lines.push(quad(atomTerm, predicate("contentByteLength"), typed(atom.content.byteLength, `${XSD}nonNegativeInteger`), stateGraph))
    lines.push(quad(atomTerm, predicate("contentSha256"), literal(atom.content.sha256), evidenceGraph))
    lines.push(quad(atomTerm, predicate("provenanceMode"), literal(atom.provenance.mode), provenanceGraph))
    lines.push(quad(atomTerm, predicate("evidenceSha256"), literal(atom.provenance.evidenceSha256), evidenceGraph))
    if (atom.provenance.sourceRef !== null) lines.push(quad(atomTerm, predicate("provenanceSource"), atomIri(canonicalAtomV2KeyId(atom.provenance.sourceRef)), provenanceGraph))
    atom.references.forEach((reference, ordinal) => {
      const ref = referenceIri(atomId, ordinal)
      lines.push(quad(atomTerm, predicate("hasTypedReference"), ref, stateGraph))
      lines.push(quad(ref, `<${RDF}type>`, type("TypedReference"), stateGraph))
      lines.push(quad(ref, predicate("sourceAtom"), atomTerm, stateGraph))
      lines.push(quad(ref, predicate("targetAtom"), atomIri(canonicalAtomV2KeyId(reference.target)), stateGraph))
      lines.push(quad(ref, predicate("referenceType"), literal(reference.referenceType), schemaGraph))
      lines.push(quad(ref, predicate("role"), literal(reference.role), schemaGraph))
      lines.push(quad(ref, predicate("ordinal"), typed(ordinal, `${XSD}nonNegativeInteger`), stateGraph))
    })
  }
  return new TextEncoder().encode(lines.sort((left, right) => Buffer.from(left).compare(Buffer.from(right))).join(""))
}

const compileCanonicalAtomV2RdfProjectionUnsafe = (
  schema: HSWMCanonicalSchemaV2,
  source: CanonicalAtomV2RdfProjectionSource
): Either.Either<CanonicalAtomV2RdfProjection, CanonicalAtomV2RdfProjectionError> => {
  const checked = validateSource(schema, source)
  if (Either.isLeft(checked)) return Either.left(checked.left)
  const compiler = compilerContractBytes()
  if (Either.isLeft(compiler)) return Either.left(compiler.left)
  const compilerProfile = makeCanonicalAtomV2ContentDescriptor("application/vnd.hswm.canonical-json+json", compiler.right)
  if (Either.isLeft(compilerProfile)) return fail("CANONICAL_ENCODING_INVALID", "compiler profile descriptor is invalid")
  const nquads = compileNquads({
    schema: checked.right.schema,
    state: checked.right.state,
    stateSha256: checked.right.stateSha256,
    tailDescriptor: source.tailDescriptor,
    journalLineageId: source.journalLineageId,
    schemaContentSha256: source.schemaBinding.content.sha256,
    compilerContractSha256: compilerProfile.right.sha256
  })
  const dataset = makeCanonicalAtomV2ContentDescriptor(HSWM_CANONICAL_ATOM_V2_RDF_NQUADS_MEDIA_TYPE, nquads)
  if (Either.isLeft(dataset)) return fail("CANONICAL_ENCODING_INVALID", "N-Quads dataset descriptor is invalid")
  const atomVersions = checked.right.state.atoms.length
  const typedReferences = checked.right.state.atoms.reduce((total, atom) => total + atom.references.length, 0)
  const manifest: CanonicalAtomV2RdfProjectionManifest = Object.freeze({
    _tag: "CanonicalAtomV2RdfProjectionManifest",
    contractVersion: HSWM_CANONICAL_ATOM_V2_RDF_PROJECTION_V1_CONTRACT_VERSION,
    encoding: HSWM_CANONICAL_JSON_VERSION,
    rdfProfile: HSWM_CANONICAL_ATOM_V2_RDF_PROFILE,
    source: Object.freeze({
      journalLineageId: source.journalLineageId,
      schemaBinding: Object.freeze({ schemaVersion: source.schemaBinding.schemaVersion, content: snapshotDescriptor(source.schemaBinding.content) }),
      schemaCanonicalBase64Url: Buffer.from(checked.right.schemaBytes).toString("base64url"),
      state: snapshotCanonicalAtomV2State(checked.right.state),
      stateSha256: checked.right.stateSha256,
      tailDescriptor: snapshotTailDescriptor(source.tailDescriptor),
      tailRecordBase64Url: Buffer.from(checked.right.tailBytes).toString("base64url")
    }),
    compiler: Object.freeze({
      contractVersion: HSWM_CANONICAL_ATOM_V2_RDF_PROJECTION_V1_CONTRACT_VERSION,
      contractSha256: sha256(compiler.right),
      profileCanonicalBase64Url: Buffer.from(compiler.right).toString("base64url"),
      profile: snapshotDescriptor(compilerProfile.right),
      implementationBinding: "PROFILE_BOUND_NOT_EXECUTABLE_ARTIFACT_BOUND"
    }),
    mapping: "ROLE_PRESERVING_REIFIED_TYPED_REFERENCE",
    writeBack: "FORBIDDEN",
    manifestRetains: Object.freeze(["CANONICAL_SCHEMA_BYTES", "CANONICAL_STATE_METADATA", "TAIL_RECORD_BYTES", "ATOM_KEY_OWNER_CONTENT_DESCRIPTOR_PROVENANCE_TYPED_REFERENCE"] as const),
    rdfDatasetOmits: Object.freeze([
      "RAW_CONTENT_PAYLOAD_BYTES",
      "FULL_JOURNAL_CHAIN",
      "TAIL_RECORD_STRUCTURE",
      "STATE_BOOTSTRAP_AND_ACCEPTED_TRANSITIONS",
      "ATOM_LIFECYCLE_AND_DECOMPOSED_KEY",
      "SCHEMA_CONSTRAINTS"
    ] as const),
    manifestOmits: Object.freeze(["RAW_CONTENT_PAYLOAD_BYTES", "FULL_JOURNAL_CHAIN"] as const),
    referenceOrder: "SOURCE_REFERENCE_ARRAY_INDEX_IS_RDF_ORDINAL",
    invalidatedBy: Object.freeze(["SCHEMA_CONTENT_BINDING_CHANGED", "STATE_DIGEST_CHANGED", "TAIL_DESCRIPTOR_OR_BYTES_CHANGED", "COMPILER_PROFILE_CHANGED"] as const),
    nonclaim: "RDF_PROJECTION_ONLY_NOT_CANONICAL_HSWM_STATE_COGNITION_LEARNING_PERMISSION_OR_EFFICACY",
    sourceAttestation: "CALLER_SUPPLIED_SELF_CONSISTENT_BUNDLE_NOT_DURABLE_RECOVERY_ATTESTED",
    counts: Object.freeze({
      atomVersions,
      typedReferences,
      relationAtomVersions: checked.right.state.atoms.filter((atom) => checked.right.schema.kinds.find((kind) => kind.kind === atom.kind)?.form === "RELATION").length,
      emittedQuads: new TextDecoder().decode(nquads).split("\n").filter(Boolean).length,
      namedGraphs: 4,
      sourceTraceCoverage: Object.freeze({ schemaContentBinding: "EXACT", stateDigest: "EXACT", tailDescriptorAndBytes: "EXACT" })
    }),
    dataset: snapshotDescriptor(dataset.right)
  })
  const projection = Object.freeze({ manifest, nquads: Uint8Array.from(nquads) })
  const projectionBytes = canonicalAtomV2RdfProjectionBytesUnsafe(projection)
  return Either.isLeft(projectionBytes)
    ? Either.left(projectionBytes.left)
    : Either.right(projection)
}

export const compileCanonicalAtomV2RdfProjection = (
  schema: HSWMCanonicalSchemaV2,
  source: CanonicalAtomV2RdfProjectionSource
): Either.Either<CanonicalAtomV2RdfProjection, CanonicalAtomV2RdfProjectionError> =>
  total(() => compileCanonicalAtomV2RdfProjectionUnsafe(schema, source))

const canonicalAtomV2RdfProjectionBytesUnsafe = (
  projection: CanonicalAtomV2RdfProjection
): Either.Either<Uint8Array, CanonicalAtomV2RdfProjectionError> => {
  if (typeof projection !== "object" || projection === null || !(projection.nquads instanceof Uint8Array) || typeof projection.manifest !== "object" || projection.manifest === null) {
    return fail("PROJECTION_INVALID", "projection object, manifest, or N-Quads bytes are invalid")
  }
  const encoded = canonicalJsonBytes({
    manifest: projection.manifest,
    nquadsBase64Url: Buffer.from(projection.nquads).toString("base64url")
  })
  return Either.isLeft(encoded)
    ? fail("CANONICAL_ENCODING_INVALID", "RDF projection cannot be canonically encoded")
    : Either.right(Uint8Array.from(encoded.right))
}

export const canonicalAtomV2RdfProjectionBytes = (
  projection: CanonicalAtomV2RdfProjection
): Either.Either<Uint8Array, CanonicalAtomV2RdfProjectionError> =>
  total(() => canonicalAtomV2RdfProjectionBytesUnsafe(projection))

const verifyCanonicalAtomV2RdfProjectionUnsafe = (
  schema: HSWMCanonicalSchemaV2,
  source: CanonicalAtomV2RdfProjectionSource,
  projection: CanonicalAtomV2RdfProjection
): Either.Either<CanonicalAtomV2RdfProjection, CanonicalAtomV2RdfProjectionError> => {
  const expected = compileCanonicalAtomV2RdfProjection(schema, source)
  if (Either.isLeft(expected)) return expected
  const actual = canonicalAtomV2RdfProjectionBytes(projection)
  const expectedBytes = canonicalAtomV2RdfProjectionBytes(expected.right)
  if (Either.isLeft(actual) || Either.isLeft(expectedBytes) || !sameBytes(actual.right, expectedBytes.right)) {
    return fail("PROJECTION_TAMPERED", "projection differs from deterministic recompilation of the exact source")
  }
  const descriptor = makeCanonicalAtomV2ContentDescriptor(HSWM_CANONICAL_ATOM_V2_RDF_NQUADS_MEDIA_TYPE, projection.nquads)
  if (Either.isLeft(descriptor) || !sameCanonicalAtomV2ContentDescriptor(descriptor.right, projection.manifest.dataset)) {
    return fail("PROJECTION_INVALID", "dataset bytes or descriptor is invalid")
  }
  return Either.right(expected.right)
}

export const verifyCanonicalAtomV2RdfProjection = (
  schema: HSWMCanonicalSchemaV2,
  source: CanonicalAtomV2RdfProjectionSource,
  projection: CanonicalAtomV2RdfProjection
): Either.Either<CanonicalAtomV2RdfProjection, CanonicalAtomV2RdfProjectionError> =>
  total(() => verifyCanonicalAtomV2RdfProjectionUnsafe(schema, source, projection))

const decodeCanonicalAtomV2RdfProjectionBytesUnsafe = (
  schema: HSWMCanonicalSchemaV2,
  source: CanonicalAtomV2RdfProjectionSource,
  bytes: Uint8Array
): Either.Either<CanonicalAtomV2RdfProjection, CanonicalAtomV2RdfProjectionError> => {
  const parsed = decodeCanonicalJsonBytes(bytes)
  if (Either.isLeft(parsed) || typeof parsed.right !== "object" || parsed.right === null || Array.isArray(parsed.right)) {
    return fail("PROJECTION_INVALID", "projection bytes are not a strict canonical JSON object")
  }
  const value = parsed.right as { readonly manifest?: unknown; readonly nquadsBase64Url?: unknown }
  if (typeof value.nquadsBase64Url !== "string" || !("manifest" in value)) return fail("PROJECTION_INVALID", "projection JSON shape is invalid")
  let nquads: Uint8Array
  try { nquads = Uint8Array.from(Buffer.from(value.nquadsBase64Url, "base64url")) } catch { return fail("PROJECTION_INVALID", "projection N-Quads base64url is invalid") }
  const candidate = { manifest: value.manifest, nquads } as CanonicalAtomV2RdfProjection
  const encoded = canonicalAtomV2RdfProjectionBytes(candidate)
  if (Either.isLeft(encoded) || !sameBytes(encoded.right, bytes)) return fail("PROJECTION_INVALID", "projection JSON is noncanonical or has an invalid manifest")
  return verifyCanonicalAtomV2RdfProjection(schema, source, candidate)
}

export const decodeCanonicalAtomV2RdfProjectionBytes = (
  schema: HSWMCanonicalSchemaV2,
  source: CanonicalAtomV2RdfProjectionSource,
  bytes: Uint8Array
): Either.Either<CanonicalAtomV2RdfProjection, CanonicalAtomV2RdfProjectionError> =>
  total(() => decodeCanonicalAtomV2RdfProjectionBytesUnsafe(schema, source, bytes))
