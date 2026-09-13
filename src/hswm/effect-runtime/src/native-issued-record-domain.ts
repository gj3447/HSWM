/** Immutable nominal records. Issuance is local validation, never external truth. */
export const makeNativeIssuedRecordFactory = <Value extends object>() => {
  const token = Object.freeze({})
  class IssuedRecord {
    readonly #issued: boolean
    constructor(key: object) { this.#issued = key === token }
    static isIssued(value: unknown): value is IssuedRecord {
      return typeof value === "object" && value !== null && #issued in value && value.#issued
    }
  }
  return Object.freeze({
    issue: (value: Value): Readonly<Value> => Object.freeze(Object.assign(new IssuedRecord(token), value)),
    isIssued: (value: unknown): value is Readonly<Value> => IssuedRecord.isIssued(value)
  })
}
