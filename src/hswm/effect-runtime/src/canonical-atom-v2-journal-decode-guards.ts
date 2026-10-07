/** Strict, pure decoding of the content envelopes named by a decoded state-journal
 * commit. This is deliberately below the journal replay boundary: it does not
 * authorize a transition or evolve state. */
import { createHash } from "node:crypto"

import { Either, Schema } from "effect"

import { canonicalAtomV2ExactBytes } from "./canonical-atom-v2-durable-guards.js"
import {
  HSWM_CANONICAL_ATOM_ENVELOPE_V2_MEDIA_TYPE,
  canonicalAtomV2EnvelopeBytes,
  type CanonicalAtomV2WriteContentBinding
} from "./canonical-atom-v2-content-bound.js"
import { canonicalAtomV2JournalEnvelopeMatches } from "./canonical-atom-v2-journal-adapter.js"
import { CanonicalAtomV2Schema, snapshotCanonicalAtomV2, type CanonicalAtomV2 } from "./canonical-atom-v2-schema.js"
import { decodeCanonicalJsonBytes } from "./canonical-atom-v2-json.js"

export type CanonicalAtomV2JournalEnvelopeInput =
  | ReadonlyArray<CanonicalAtomV2>
  | ReadonlyArray<Uint8Array>

export type CanonicalAtomV2JournalEnvelopeDecodeFailure =
  | "COUNT_MISMATCH"
  | "JSON_INVALID"
  | "ATOM_INVALID"
  | "NOT_CANONICAL"
  | "OBJECT_CANONICAL_INVALID"
  | "BINDING_MISMATCH"

const sha256 = (bytes: Uint8Array): string =>
  createHash("sha256").update(bytes).digest("hex")

/**
 * Decodes exactly one envelope for every persisted write binding. Byte inputs
 * must parse through the bounded duplicate-free JSON decoder and equal their
 * canonical v1 encoding. Object inputs remain for in-process construction;
 * they are schema-decoded and re-encoded before their binding is checked.
 *
 * This function makes no claim that the JSON parser itself has been formally
 * verified. Callers must still validate binding order, receipt construction,
 * hashes and state evolution.
 */
export const decodeCanonicalAtomV2JournalWriteEnvelopes = (
  inputs: CanonicalAtomV2JournalEnvelopeInput,
  bindings: ReadonlyArray<CanonicalAtomV2WriteContentBinding>
): Either.Either<ReadonlyArray<CanonicalAtomV2>, CanonicalAtomV2JournalEnvelopeDecodeFailure> => {
  if (inputs.length !== bindings.length) return Either.left("COUNT_MISMATCH")
  const atoms: Array<CanonicalAtomV2> = []
  for (let index = 0; index < inputs.length; index += 1) {
    const input = inputs[index]!
    let atom: CanonicalAtomV2
    let bytes: Uint8Array
    if (input instanceof Uint8Array) {
      const parsed = decodeCanonicalJsonBytes(input)
      if (Either.isLeft(parsed)) return Either.left("JSON_INVALID")
      const decoded = Schema.decodeUnknownEither(CanonicalAtomV2Schema, { onExcessProperty: "error" })(parsed.right)
      if (Either.isLeft(decoded)) return Either.left("ATOM_INVALID")
      atom = snapshotCanonicalAtomV2(decoded.right)
      const canonical = canonicalAtomV2EnvelopeBytes(atom)
      if (Either.isLeft(canonical) || !canonicalAtomV2ExactBytes(input, canonical.right)) return Either.left("NOT_CANONICAL")
      bytes = canonical.right
    } else {
      const decoded = Schema.decodeUnknownEither(CanonicalAtomV2Schema, { onExcessProperty: "error" })(input)
      if (Either.isLeft(decoded)) return Either.left("ATOM_INVALID")
      atom = snapshotCanonicalAtomV2(decoded.right)
      const canonical = canonicalAtomV2EnvelopeBytes(atom)
      if (Either.isLeft(canonical)) return Either.left("OBJECT_CANONICAL_INVALID")
      bytes = canonical.right
    }
    if (!canonicalAtomV2JournalEnvelopeMatches(atom, {
      mediaType: HSWM_CANONICAL_ATOM_ENVELOPE_V2_MEDIA_TYPE,
      byteLength: bytes.byteLength,
      sha256: sha256(bytes)
    }, bindings[index]!)) return Either.left("BINDING_MISMATCH")
    atoms.push(atom)
  }
  return Either.right(Object.freeze(atoms))
}
