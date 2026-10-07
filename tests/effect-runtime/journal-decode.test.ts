import { createHash } from "node:crypto"
import { execFileSync } from "node:child_process"
import { resolve } from "node:path"

import { Either } from "effect"
import { expect, it } from "vitest"
import { describeCanonicalAtomV2Envelope, canonicalAtomV2EnvelopeBytes, type CanonicalAtomV2WriteContentBinding } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-content-bound.js"
import { makeCanonicalAtomV2ContentDescriptor } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-content.js"
import { decodeCanonicalAtomV2JournalWriteEnvelopes } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-journal-decode-guards.js"
import { HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION, type CanonicalAtomV2 } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-schema.js"

const right = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw new Error(JSON.stringify(value.left))
  return value.right
}
const utf8 = (value: string) => new TextEncoder().encode(value)
const atom: CanonicalAtomV2 = {
  _tag: "CanonicalAtomV2", contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION,
  key: { schemaVersion: "fixture:v1", lineageId: "lineage:fixture", atomUid: "atom:fixture", revisionId: 0 },
  kind: "fixture:kind", responsibilityOwner: "owner:fixture",
  content: right(makeCanonicalAtomV2ContentDescriptor("application/json", utf8('{"fixture":true}'))),
  provenance: { mode: "OBSERVATION", evidenceSha256: createHash("sha256").update("fixture").digest("hex"), sourceRef: null },
  lifecycle: "ADMITTED", references: []
}
const raw = right(canonicalAtomV2EnvelopeBytes(atom))
const binding: CanonicalAtomV2WriteContentBinding = { key: atom.key, payload: atom.content, envelope: right(describeCanonicalAtomV2Envelope(atom)) }
const code = (value: Either.Either<unknown, string>) => Either.isLeft(value) ? value.left : "ACCEPTED"
const leanPath = resolve(import.meta.dirname, "../../formal/.lake/build/bin/HSWMJournalDecodeCli")

it("strictly decodes canonical envelope bytes and rejects finite parser, descriptor and binding substitutions", () => {
  expect(code(decodeCanonicalAtomV2JournalWriteEnvelopes([raw], [binding]))).toBe("ACCEPTED")
  const source = new TextDecoder().decode(raw)
  const cases: ReadonlyArray<readonly [Uint8Array[], CanonicalAtomV2WriteContentBinding[], string]> = [
    [[utf8(source.slice(0, -1))], [binding], "JSON_INVALID"],
    [[utf8(source.replace("{", '{"_tag":"CanonicalAtomV2",'))], [binding], "JSON_INVALID"],
    [[utf8(source + "\n")], [binding], "NOT_CANONICAL"],
    [[raw], [{ ...binding, envelope: { ...binding.envelope, sha256: "0".repeat(64) } }], "BINDING_MISMATCH"],
    [[raw], [{ ...binding, key: { ...binding.key, atomUid: "atom:substituted" } }], "BINDING_MISMATCH"],
    [[raw], [{ ...binding, payload: { ...binding.payload, byteLength: binding.payload.byteLength + 1 } }], "BINDING_MISMATCH"],
    [[], [binding], "COUNT_MISMATCH"]
  ]
  for (const [inputs, bindings, expected] of cases) {
    expect(code(decodeCanonicalAtomV2JournalWriteEnvelopes(inputs, bindings))).toBe(expected)
  }
  expect(code(decodeCanonicalAtomV2JournalWriteEnvelopes([atom], [binding]))).toBe("ACCEPTED")
})

it.skipIf(process.env["HSWM_RUN_SEMANTIC_LEAN"] !== "1")("computes actual decoded fields in Lean and compares native envelope acceptance", () => {
  const variants = [binding,
    { ...binding, envelope: { ...binding.envelope, mediaType: "application/other" } },
    { ...binding, envelope: { ...binding.envelope, byteLength: binding.envelope.byteLength + 1 } },
    { ...binding, envelope: { ...binding.envelope, sha256: "0".repeat(64) } },
    { ...binding, key: { ...binding.key, schemaVersion: "schema:other" } },
    { ...binding, key: { ...binding.key, lineageId: "lineage:other" } },
    { ...binding, key: { ...binding.key, atomUid: "atom:other" } },
    { ...binding, key: { ...binding.key, revisionId: 1 } },
    { ...binding, payload: { ...binding.payload, mediaType: "application/other" } },
    { ...binding, payload: { ...binding.payload, byteLength: binding.payload.byteLength + 1 } },
    { ...binding, payload: { ...binding.payload, sha256: "0".repeat(64) } }
  ]
  const samples = [...variants.map(b => ({ raw, binding: b })),
    { raw: utf8(new TextDecoder().decode(raw) + "\n"), binding }]
  const native = samples.map(s => Either.isRight(decodeCanonicalAtomV2JournalWriteEnvelopes([s.raw], [s.binding])))
  const wire = { contract: "hswm-journal-decode/v1", writes: samples.map(s => ({
    atom: { key: atom.key, content: atom.content, envelopeUtf8: new TextDecoder().decode(raw) },
    observedEnvelope: { ...binding.envelope, byteLength: s.raw.byteLength, sha256: createHash("sha256").update(s.raw).digest("hex") },
    bindingEnvelope: s.binding.envelope, bindingKey: s.binding.key, payload: s.binding.payload,
    raw: [...s.raw], canonical: [...raw]
  })) }
  const output = JSON.parse(execFileSync(leanPath, [], { input: JSON.stringify(wire), encoding: "utf8", timeout: 10000, maxBuffer: 1024 * 1024 })) as {
    writes: { accepted: boolean }[]; allWritesMatch: boolean; jsonParserProved: boolean; nativeValidationProved: boolean; hashProved: boolean
  }
  expect(native).toEqual([true, ...Array<boolean>(11).fill(false)])
  expect(output.writes.map(v => v.accepted)).toEqual(native)
  expect(output.allWritesMatch).toBe(false)
  expect(output.jsonParserProved || output.nativeValidationProved || output.hashProved).toBe(false)
})
