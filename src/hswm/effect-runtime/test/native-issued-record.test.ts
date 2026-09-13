import { expect, it } from "vitest"
import { makeNativeIssuedRecordFactory } from "../src/native-issued-record-domain.js"

it("preserves an immutable record without accepting copied brands or a public constructor", () => {
  const factory = makeNativeIssuedRecordFactory<{ readonly terminal: string; readonly digest: string }>()
  const other = makeNativeIssuedRecordFactory<{ readonly terminal: string; readonly digest: string }>()
  const input = { terminal: "candidate", digest: "source-bound" }
  const record = factory.issue(input)
  expect(factory.isIssued(record)).toBe(true)
  expect(Object.isFrozen(record)).toBe(true)
  expect(other.isIssued(record)).toBe(false)
  expect(factory.isIssued({ ...record })).toBe(false)
  expect(factory.isIssued(Object.create(Object.getPrototypeOf(record)))).toBe(false)
  const forged: unknown = Reflect.construct(record.constructor, [{}])
  expect(factory.isIssued(forged)).toBe(false)
  input.terminal = "forged"
  expect(record.terminal).toBe("candidate")
  expect(JSON.stringify(record)).toBe('{"terminal":"candidate","digest":"source-bound"}')
})
