import { Data, Either } from "effect"
import * as jsonld from "jsonld"
import type { ContextDefinition } from "jsonld"

import {
  makeCanonicalAtomV2ContentDescriptor,
  sameCanonicalAtomV2ContentDescriptor,
  type CanonicalAtomV2ContentDescriptor
} from "./canonical-atom-v2-content.js"
import { canonicalJsonBytes } from "./canonical-atom-v2-json.js"
import {
  HSWM_CANONICAL_ATOM_V2_RDF_NQUADS_MEDIA_TYPE,
  HSWM_CANONICAL_ATOM_V2_RDF_PROFILE,
  HSWM_CANONICAL_ATOM_V2_RDF_PROJECTION_V1_CONTRACT_VERSION,
  type CanonicalAtomV2RdfProjectionManifest
} from "./canonical-atom-v2-rdf-projection.js"

/**
 * A JSON-LD 1.1 API view over the source-bound RDF projection.
 *
 * This is a read-only exchange representation. It is never a canonical HSWM
 * writer, Permit issuer, provenance adjudicator, causal-credit signal, or
 * learning transition.
 */
export const HSWM_CANONICAL_ATOM_V2_JSONLD_VIEW_V1_CONTRACT_VERSION =
  "hswm-canonical-atom-v2-jsonld-view/v1" as const
export const HSWM_CANONICAL_ATOM_V2_JSONLD_MEDIA_TYPE =
  "application/ld+json" as const
export const HSWM_JSONLD_IMPLEMENTATION = "jsonld.js@9.0.0" as const
export const HSWM_JSONLD_CLAIM_CEILING =
  "SOURCE_BOUND_READ_ONLY_JSONLD_1_1_EXCHANGE_VIEW_NOT_CANONICAL_STATE_PROV_TRUTH_PERMIT_CAUSAL_CREDIT_LEARNING_OR_EFFICACY" as const

type SimpleContext = Readonly<Record<string, string>>

export interface CanonicalAtomV2RdfViewInput {
  readonly manifest: Pick<CanonicalAtomV2RdfProjectionManifest,
    "_tag" | "contractVersion" | "dataset" | "invalidatedBy" | "mapping" |
    "nonclaim" | "rdfDatasetOmits" | "rdfProfile" | "writeBack">
  readonly nquads: Uint8Array
}

export interface CanonicalAtomV2JsonLdViewManifest {
  readonly contractVersion: typeof HSWM_CANONICAL_ATOM_V2_JSONLD_VIEW_V1_CONTRACT_VERSION
  readonly algorithm: "JSON_LD_1_1_FROM_RDF_THEN_COMPACTION"
  readonly implementation: typeof HSWM_JSONLD_IMPLEMENTATION
  readonly sourceDataset: CanonicalAtomV2ContentDescriptor
  readonly sourceRdfProfile: typeof HSWM_CANONICAL_ATOM_V2_RDF_PROFILE
  readonly context: CanonicalAtomV2ContentDescriptor
  readonly expanded: CanonicalAtomV2ContentDescriptor
  readonly compacted: CanonicalAtomV2ContentDescriptor
  readonly mappingLoss: ReadonlyArray<string>
  readonly documentLoader: "NETWORK_AND_REMOTE_CONTEXTS_FORBIDDEN"
  readonly writeBack: "FORBIDDEN"
  readonly claimCeiling: typeof HSWM_JSONLD_CLAIM_CEILING
}

export interface CanonicalAtomV2JsonLdView {
  readonly manifest: CanonicalAtomV2JsonLdViewManifest
  readonly expanded: Uint8Array
  readonly compacted: Uint8Array
}

export class CanonicalAtomV2JsonLdViewError extends Data.TaggedError(
  "CanonicalAtomV2JsonLdViewError"
)<{
  readonly code:
    | "INPUT_INVALID"
    | "PROFILE_VIOLATION"
    | "SOURCE_DESCRIPTOR_STALE"
    | "CONTEXT_INVALID"
    | "JSONLD_PROCESSING_FAILED"
    | "CANONICAL_ENCODING_FAILED"
  readonly detail: string
}> {}

const failure = (
  code: CanonicalAtomV2JsonLdViewError["code"],
  detail: string
): Either.Either<never, CanonicalAtomV2JsonLdViewError> =>
  Either.left(new CanonicalAtomV2JsonLdViewError({ code, detail }))

const descriptor = (
  mediaType: string,
  bytes: Uint8Array
): Either.Either<CanonicalAtomV2ContentDescriptor, CanonicalAtomV2JsonLdViewError> => {
  const value = makeCanonicalAtomV2ContentDescriptor(mediaType, bytes)
  return Either.isLeft(value)
    ? failure("CANONICAL_ENCODING_FAILED", "view descriptor could not be constructed")
    : Either.right(value.right)
}

const isAbsoluteIri = (value: string): boolean =>
  /^[A-Za-z][A-Za-z0-9+.-]*:[^\s]*$/u.test(value)

const contextObject = (
  input: SimpleContext
): Either.Either<{ readonly bytes: Uint8Array; readonly value: ContextDefinition }, CanonicalAtomV2JsonLdViewError> => {
  if (
    typeof input !== "object" || input === null || Array.isArray(input) ||
    ![Object.prototype, null].includes(Object.getPrototypeOf(input))
  ) return failure("CONTEXT_INVALID", "JSON-LD context must be a plain local alias object")
  const entries = Object.entries(input)
  if (entries.length > 256) return failure("CONTEXT_INVALID", "JSON-LD context exceeds 256 local aliases")
  const forbidden = new Set(["__proto__", "constructor", "prototype"])
  for (const [term, iri] of entries) {
    if (
      term.length === 0 || term.startsWith("@") || forbidden.has(term) ||
      typeof iri !== "string" || !isAbsoluteIri(iri)
    ) return failure("CONTEXT_INVALID", "JSON-LD context contains an unsafe alias or non-absolute IRI")
  }
  const sorted = Object.fromEntries(entries.sort(([left], [right]) => left.localeCompare(right)))
  const bytes = canonicalJsonBytes(sorted)
  return Either.isLeft(bytes)
    ? failure("CANONICAL_ENCODING_FAILED", "JSON-LD context is not canonical JSON")
    : Either.right({ bytes: Uint8Array.from(bytes.right), value: sorted as ContextDefinition })
}

const rejectRemoteDocument = async (_url: string): Promise<never> => {
  throw new Error("remote JSON-LD document loading is forbidden")
}

const containsBlankNodeIdentifier = (value: unknown): boolean => {
  if (Array.isArray(value)) return value.some(containsBlankNodeIdentifier)
  if (typeof value !== "object" || value === null) return false
  return Object.entries(value).some(([key, item]) =>
    (key === "@id" && typeof item === "string" && item.startsWith("_:")) ||
    containsBlankNodeIdentifier(item)
  )
}

const canonicalBytes = (
  value: unknown
): Either.Either<Uint8Array, CanonicalAtomV2JsonLdViewError> => {
  const encoded = canonicalJsonBytes(value)
  return Either.isLeft(encoded)
    ? failure("CANONICAL_ENCODING_FAILED", "JSON-LD processor returned non-canonical JSON data")
    : Either.right(Uint8Array.from(encoded.right))
}

export const compileCanonicalAtomV2JsonLdView = async (
  projection: CanonicalAtomV2RdfViewInput,
  context: SimpleContext
): Promise<Either.Either<CanonicalAtomV2JsonLdView, CanonicalAtomV2JsonLdViewError>> => {
  try {
    if (
      typeof projection !== "object" || projection === null ||
      !(projection.nquads instanceof Uint8Array) || projection.nquads.byteLength === 0 ||
      typeof projection.manifest !== "object" || projection.manifest === null ||
      projection.manifest._tag !== "CanonicalAtomV2RdfProjectionManifest" ||
      projection.manifest.contractVersion !== HSWM_CANONICAL_ATOM_V2_RDF_PROJECTION_V1_CONTRACT_VERSION ||
      projection.manifest.rdfProfile !== HSWM_CANONICAL_ATOM_V2_RDF_PROFILE ||
      projection.manifest.mapping !== "ROLE_PRESERVING_REIFIED_TYPED_REFERENCE" ||
      projection.manifest.writeBack !== "FORBIDDEN" ||
      typeof projection.manifest.nonclaim !== "string" ||
      !projection.manifest.nonclaim.includes("RDF_PROJECTION_ONLY") ||
      !Array.isArray(projection.manifest.rdfDatasetOmits) ||
      projection.manifest.rdfDatasetOmits.some((item) => typeof item !== "string") ||
      !Array.isArray(projection.manifest.invalidatedBy) ||
      !([
        "SCHEMA_CONTENT_BINDING_CHANGED",
        "STATE_DIGEST_CHANGED",
        "TAIL_DESCRIPTOR_OR_BYTES_CHANGED",
        "COMPILER_PROFILE_CHANGED"
      ] as const).every((item) => projection.manifest.invalidatedBy.includes(item))
    ) return failure("INPUT_INVALID", "input is not the bounded read-only HSWM RDF projection profile")
    const sourceDataset = Object.freeze({ ...projection.manifest.dataset })
    const mappingLoss = Object.freeze([...projection.manifest.rdfDatasetOmits].sort())
    const observedSource = makeCanonicalAtomV2ContentDescriptor(
      HSWM_CANONICAL_ATOM_V2_RDF_NQUADS_MEDIA_TYPE,
      projection.nquads
    )
    if (
      Either.isLeft(observedSource) ||
      !sameCanonicalAtomV2ContentDescriptor(observedSource.right, sourceDataset)
    ) return failure("SOURCE_DESCRIPTOR_STALE", "RDF bytes differ from the source-bound dataset descriptor")
    const checkedContext = contextObject(context)
    if (Either.isLeft(checkedContext)) return Either.left(checkedContext.left)
    const nquads = new TextDecoder("utf-8", { fatal: true }).decode(projection.nquads)
    let expandedValue: Awaited<ReturnType<typeof jsonld.fromRDF>>
    let compactedValue: Awaited<ReturnType<typeof jsonld.compact>>
    try {
      expandedValue = await jsonld.fromRDF(nquads, {
        format: "application/n-quads",
        useNativeTypes: false,
        useRdfType: false
      })
      if (containsBlankNodeIdentifier(expandedValue)) {
        return failure("PROFILE_VIOLATION", "blank nodes are forbidden by the exact HSWM RDF projection profile")
      }
      const compactOptions = {
        compactArrays: true,
        compactToRelative: false,
        documentLoader: rejectRemoteDocument,
        processingMode: "json-ld-1.1"
      } as unknown as jsonld.Options.Compact
      compactedValue = await jsonld.compact(expandedValue, checkedContext.right.value, compactOptions)
    } catch {
      return failure("JSONLD_PROCESSING_FAILED", "pinned JSON-LD processor rejected the bounded RDF view")
    }
    const expanded = canonicalBytes(expandedValue)
    const compacted = canonicalBytes(compactedValue)
    if (Either.isLeft(expanded)) return Either.left(expanded.left)
    if (Either.isLeft(compacted)) return Either.left(compacted.left)
    const contextDescriptor = descriptor(HSWM_CANONICAL_ATOM_V2_JSONLD_MEDIA_TYPE, checkedContext.right.bytes)
    const expandedDescriptor = descriptor(HSWM_CANONICAL_ATOM_V2_JSONLD_MEDIA_TYPE, expanded.right)
    const compactedDescriptor = descriptor(HSWM_CANONICAL_ATOM_V2_JSONLD_MEDIA_TYPE, compacted.right)
    if (Either.isLeft(contextDescriptor)) return Either.left(contextDescriptor.left)
    if (Either.isLeft(expandedDescriptor)) return Either.left(expandedDescriptor.left)
    if (Either.isLeft(compactedDescriptor)) return Either.left(compactedDescriptor.left)
    return Either.right(Object.freeze({
      manifest: Object.freeze({
        contractVersion: HSWM_CANONICAL_ATOM_V2_JSONLD_VIEW_V1_CONTRACT_VERSION,
        algorithm: "JSON_LD_1_1_FROM_RDF_THEN_COMPACTION",
        implementation: HSWM_JSONLD_IMPLEMENTATION,
        sourceDataset,
        sourceRdfProfile: HSWM_CANONICAL_ATOM_V2_RDF_PROFILE,
        context: Object.freeze({ ...contextDescriptor.right }),
        expanded: Object.freeze({ ...expandedDescriptor.right }),
        compacted: Object.freeze({ ...compactedDescriptor.right }),
        mappingLoss,
        documentLoader: "NETWORK_AND_REMOTE_CONTEXTS_FORBIDDEN",
        writeBack: "FORBIDDEN",
        claimCeiling: HSWM_JSONLD_CLAIM_CEILING
      }),
      expanded: Uint8Array.from(expanded.right),
      compacted: Uint8Array.from(compacted.right)
    }))
  } catch {
    return failure("INPUT_INVALID", "runtime input raised at the fail-closed JSON-LD boundary")
  }
}
