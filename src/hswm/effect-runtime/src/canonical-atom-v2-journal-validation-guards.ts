/** Pure decoded structural guards shared by native evolution and the Lean
 * boundary test. JSON/schema decoding, atom validation and authorization are
 * intentionally outside this small key-set check. */
export type CanonicalAtomV2ReadSetDecision =
  | "PASSED"
  | "STATE_KEY_DUPLICATE"
  | "READ_SET_DUPLICATE"
  | "READ_SET_MISSING"

const hasDuplicates = (values: ReadonlyArray<string>): boolean =>
  new Set(values).size !== values.length

/** Preserves the native check order: duplicate existing keys, then duplicate
 * read keys, then a missing read key. */
export const canonicalAtomV2ReadSetDecision = (
  existingKeyIds: ReadonlyArray<string>,
  readSetKeyIds: ReadonlyArray<string>
): CanonicalAtomV2ReadSetDecision => {
  if (hasDuplicates(existingKeyIds)) return "STATE_KEY_DUPLICATE"
  if (hasDuplicates(readSetKeyIds)) return "READ_SET_DUPLICATE"
  const existing = new Set(existingKeyIds)
  return readSetKeyIds.some((id) => !existing.has(id))
    ? "READ_SET_MISSING"
    : "PASSED"
}
