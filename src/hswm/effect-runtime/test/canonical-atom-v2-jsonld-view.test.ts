import { createHash } from "node:crypto"

import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import {
  HSWM_CANONICAL_ATOM_V2_JSONLD_MEDIA_TYPE,
  HSWM_JSONLD_CLAIM_CEILING,
  compileCanonicalAtomV2JsonLdView,
  type CanonicalAtomV2RdfViewInput
} from "../src/canonical-atom-v2-jsonld-view.js"
import {
  HSWM_CANONICAL_ATOM_V2_RDF_PROFILE,
  HSWM_CANONICAL_ATOM_V2_RDF_PROJECTION_V1_CONTRACT_VERSION
} from "../src/canonical-atom-v2-rdf-projection.js"

const bytes = (value: string): Uint8Array => new TextEncoder().encode(value)
const sha256 = (value: Uint8Array): string => createHash("sha256").update(value).digest("hex")
const nquads = bytes([
  '<https://example.test/s> <https://example.test/name> "HSWM" <https://example.test/graph> .',
  '<https://example.test/s> <https://example.test/target> <https://example.test/o> <https://example.test/graph> .',
  ""
].join("\n"))

const projection = (source = nquads): CanonicalAtomV2RdfViewInput => {
  const snapshot = Uint8Array.from(source)
  return {
    manifest: {
      _tag: "CanonicalAtomV2RdfProjectionManifest",
      contractVersion: HSWM_CANONICAL_ATOM_V2_RDF_PROJECTION_V1_CONTRACT_VERSION,
      dataset: { mediaType: "application/n-quads", byteLength: snapshot.byteLength, sha256: sha256(snapshot) },
      invalidatedBy: ["SCHEMA_CONTENT_BINDING_CHANGED", "STATE_DIGEST_CHANGED", "TAIL_DESCRIPTOR_OR_BYTES_CHANGED", "COMPILER_PROFILE_CHANGED"],
      mapping: "ROLE_PRESERVING_REIFIED_TYPED_REFERENCE",
      rdfProfile: HSWM_CANONICAL_ATOM_V2_RDF_PROFILE,
      rdfDatasetOmits: ["RAW_CONTENT_PAYLOAD_BYTES", "FULL_JOURNAL_CHAIN"],
      writeBack: "FORBIDDEN",
      nonclaim: "RDF_PROJECTION_ONLY_NOT_CANONICAL_HSWM_STATE_COGNITION_LEARNING_PERMISSION_OR_EFFICACY"
    },
    nquads: snapshot
  }
}

it("emits source-bound deterministic JSON-LD 1.1 exchange bytes", async () => {
  const first = await compileCanonicalAtomV2JsonLdView(projection(), {
    name: "https://example.test/name",
    target: "https://example.test/target"
  })
  const second = await compileCanonicalAtomV2JsonLdView(projection(), {
    target: "https://example.test/target",
    name: "https://example.test/name"
  })
  if (Either.isLeft(first)) throw new Error(`${first.left.code}: ${first.left.detail}`)
  if (Either.isLeft(second)) throw new Error(`${second.left.code}: ${second.left.detail}`)
  expect(first.right.expanded).toEqual(second.right.expanded)
  expect(first.right.compacted).toEqual(second.right.compacted)
  expect(first.right.manifest.expanded.mediaType).toBe(HSWM_CANONICAL_ATOM_V2_JSONLD_MEDIA_TYPE)
  expect(first.right.manifest.sourceDataset.sha256).toBe(sha256(nquads))
  expect(first.right.manifest.writeBack).toBe("FORBIDDEN")
  expect(first.right.manifest.claimCeiling).toBe(HSWM_JSONLD_CLAIM_CEILING)
  expect(JSON.parse(new TextDecoder().decode(first.right.compacted))["@context"]).toEqual({
    name: "https://example.test/name",
    target: "https://example.test/target"
  })
})

it("rejects stale RDF bytes and remote or unsafe contexts", async () => {
  const stale = projection()
  stale.nquads[0] = 0x20
  expect(Either.isLeft(await compileCanonicalAtomV2JsonLdView(stale, {}))).toBe(true)
  expect(Either.isLeft(await compileCanonicalAtomV2JsonLdView(projection(), {
    "@context": "https://remote.example/context"
  }))).toBe(true)
  expect(Either.isLeft(await compileCanonicalAtomV2JsonLdView(projection(), {
    bad: "relative/context"
  }))).toBe(true)
})

it("refuses blank nodes from the blank-node-free projection profile", async () => {
  const blank = bytes(
    '_:subject <https://example.test/name> "HSWM" <https://example.test/graph> .\n'
  )
  const result = await compileCanonicalAtomV2JsonLdView(projection(blank), {})

  expect(Either.isLeft(result)).toBe(true)
  if (Either.isLeft(result)) expect(result.left.code).toBe("PROFILE_VIOLATION")
})

it("snapshots manifest evidence before asynchronous JSON-LD processing", async () => {
  const candidate = projection()
  const originalSourceSha256 = candidate.manifest.dataset.sha256
  const pending = compileCanonicalAtomV2JsonLdView(candidate, {})
  const mutableManifest = candidate.manifest as unknown as {
    dataset: { mediaType: string; byteLength: number; sha256: string }
    rdfDatasetOmits: Array<string>
  }
  mutableManifest.dataset.sha256 = "0".repeat(64)
  mutableManifest.rdfDatasetOmits.push("FORGED_AFTER_VALIDATION")
  const result = await pending

  if (Either.isLeft(result)) throw new Error(`${result.left.code}: ${result.left.detail}`)
  expect(result.right.manifest.sourceDataset.sha256).toBe(originalSourceSha256)
  expect(result.right.manifest.mappingLoss).not.toContain("FORGED_AFTER_VALIDATION")
})
