import { expect, it } from "@effect/vitest"
import { createHash } from "node:crypto"
import { readFileSync } from "node:fs"
import { decodeNativeTaskJson, validNativeTaskJson } from "../src/native-task-json-domain.js"
import { PYTHON312_UCD15_NONPRINTABLE_RANGES_SHA256, PYTHON312_UCD15_PRINTABLE_BITMAP_SHA256 } from "../src/native-python-isprintable-data.js"
import { pythonJsonIsPrintable, pythonJsonString } from "../src/native-python-string-domain.js"

interface OracleRow { readonly json: string; readonly python_str: string }
interface Oracle { readonly values: readonly OracleRow[] }
const oracle = JSON.parse(readFileSync(new URL("../../../../tests/fixtures/native_migration/python_string_v1/original_python.json", import.meta.url), "utf8")) as Oracle
const decode = (text: string) => {
  const parsed = decodeNativeTaskJson(Buffer.from(text, "utf8"))
  if (parsed._tag === "Right") return parsed.right
  const fallback: unknown = JSON.parse(text)
  expect(validNativeTaskJson(fallback)).toBe(true)
  if (validNativeTaskJson(fallback)) return fallback
  throw new Error("unexpected invalid oracle JSON")
}

it("matches the Python 3.12 str oracle across JSON scalars, containers, controls, and Unicode", () => {
  for (const row of oracle.values) expect(pythonJsonString(decode(row.json))).toBe(row.python_str)
})

it("pins Python 3.12 UCD 15 isprintable over every Unicode scalar", () => {
  const bitmap = Buffer.alloc(0x110000)
  for (let codepoint = 0; codepoint <= 0x10ffff; codepoint += 1) bitmap[codepoint] = pythonJsonIsPrintable(String.fromCodePoint(codepoint)) ? 1 : 0
  expect(createHash("sha256").update(bitmap).digest("hex")).toBe(PYTHON312_UCD15_PRINTABLE_BITMAP_SHA256)
  expect(PYTHON312_UCD15_NONPRINTABLE_RANGES_SHA256).toBe("df676bdb3710ab543ea929c757277c079700bb640d60cc58baea8a72fafdec5f")
})
