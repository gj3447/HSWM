/** Python JSON number kinds survive the native proposal boundary and its digests. */
import { decodeGeneralJsonThroughNumberLexemes, type GeneralJson, type GeneralJsonOptions } from "./general-json-domain.js"

class TaskFloat {
  private constructor(readonly value: number) { Object.freeze(this) }
  static fromFiniteToken(token: string): TaskFloat { return new TaskFloat(Number(token)) }
}
export type TaskNumber = number | bigint | TaskFloat
export type TaskJson = null | boolean | string | TaskNumber | readonly TaskJson[] | {readonly [key: string]: TaskJson}
export const taskNumberValue = (n: TaskNumber): number | bigint => n instanceof TaskFloat ? n.value : n
export const isTaskNumber = (n: TaskJson): n is TaskNumber => typeof n === "bigint" || typeof n === "number" && Number.isFinite(n) || n instanceof TaskFloat && Number.isFinite(n.value)
export const taskJsonRecord = (v: TaskJson): v is {readonly [key: string]: TaskJson} => typeof v === "object" && v !== null && !Array.isArray(v) && !(v instanceof TaskFloat)
export const validNativeTaskJson = (value: unknown, depth = 0): value is TaskJson => {
  if (depth > 128) return false
  if (value === null || typeof value === "string" || typeof value === "boolean" || typeof value === "bigint") return true
  if (typeof value === "number") return Number.isFinite(value)
  if (value instanceof TaskFloat) return Number.isFinite(value.value)
  if (Array.isArray(value)) return Array.from({length: value.length}, (_, i) => i).every(i => Object.hasOwn(value, i) && validNativeTaskJson(value[i], depth + 1))
  if (typeof value !== "object" || ![Object.prototype, null].includes(Object.getPrototypeOf(value))) return false
  return Object.values(value).every(child => validNativeTaskJson(child, depth + 1))
}
export const taskTextCompare = (a: string, b: string): number => Buffer.compare(Buffer.from(a), Buffer.from(b))
const pointer = (path: string, key: string | number): string => `${path}/${String(key).replaceAll("~", "~0").replaceAll("/", "~1")}`
const sourceKeyOrder = Symbol("task-json-source-key-order")
export const decodeNativeTaskJson = (bytes: Uint8Array, options: GeneralJsonOptions = {}) => decodeGeneralJsonThroughNumberLexemes(bytes, decoded => {
  const restore = (value: GeneralJson, path: string): TaskJson => {
    if (typeof value === "number") {
      const token = decoded.numberLexemes[path]!
      return /[.eE]/.test(token) ? TaskFloat.fromFiniteToken(token) : Number.isSafeInteger(Number(token)) ? Number(token) : BigInt(token)
    }
    if (Array.isArray(value)) return value.map((child, index) => restore(child, pointer(path, index)))
    if (value !== null && typeof value === "object") return Object.defineProperty(Object.fromEntries(Object.entries(value).map(([key, child]) => [key, restore(child, pointer(path, key))])), sourceKeyOrder, {value: decoded.objectKeys[path], enumerable: false})
    return value as null | boolean | string
  }
  return restore(decoded.value, "")
}, options)
export const taskFloatText = (value: number): string => {
  if (Object.is(value, -0)) return "-0.0"
  const expanded = value !== 0 && (Math.abs(value) >= 1e16 || Math.abs(value) < 1e-4) ? value.toExponential() : String(value)
  if (expanded.includes("e")) return expanded.replace(/e([+-]?)(\d+)$/, (_, sign: string, digits: string) => `e${sign || "+"}${digits.padStart(2, "0")}`)
  return expanded.includes(".") ? expanded : `${expanded}.0`
}
export const renderNativeTaskJson = (value: TaskJson, mode: "canonical" | "relation" | "pretty" = "canonical", depth = 0): string => {
  if (value instanceof TaskFloat) return taskFloatText(value.value)
  if (typeof value === "bigint") return String(value)
  const separator = mode === "canonical" ? "," : ", ", colon = mode === "canonical" ? ":" : ": "
  const render = (v: TaskJson) => renderNativeTaskJson(v, mode, depth + 1)
  const wrap = (entries: readonly string[], start: string, end: string) => mode === "pretty" && entries.length > 0 ? `${start}\n${"  ".repeat(depth + 1)}${entries.join(`,\n${"  ".repeat(depth + 1)}`)}\n${"  ".repeat(depth)}${end}` : `${start}${entries.join(separator)}${end}`
  if (Array.isArray(value)) return wrap(value.map(render), "[", "]")
  if (taskJsonRecord(value)) {
    const originalKeys = (value as {[sourceKeyOrder]?: readonly string[]})[sourceKeyOrder] ?? Object.keys(value)
    return wrap((mode === "relation" ? originalKeys : Object.keys(value).sort(taskTextCompare)).map(k => `${render(k)}${colon}${render(value[k]!)}`), "{", "}")
  }
  const encoded = JSON.stringify(value)
  return mode === "relation" && typeof value === "string" ? encoded.replace(/[\u007f-\uffff]/g, c => `\\u${c.charCodeAt(0).toString(16).padStart(4, "0")}`) : encoded
}
const numeric = (value: TaskJson): value is TaskNumber | boolean => isTaskNumber(value) || typeof value === "boolean"
const numericValue = (value: TaskNumber | boolean): number | bigint => typeof value === "boolean" ? Number(value) : taskNumberValue(value)
const numericEqual = (a: number | bigint, b: number | bigint): boolean => a <= b && a >= b
const nestedSame = (a: TaskJson, b: TaskJson): boolean => numeric(a) && numeric(b) ? numericEqual(numericValue(a), numericValue(b)) : Array.isArray(a) && Array.isArray(b) ? a.length === b.length && a.every((v,i) => nestedSame(v,b[i]!)) : taskJsonRecord(a) && taskJsonRecord(b) ? Object.keys(a).length === Object.keys(b).length && Object.keys(a).every(k => Object.hasOwn(b,k) && nestedSame(a[k]!,b[k]!)) : a === b
const kind = (v: TaskJson): string => v instanceof TaskFloat ? "float" : typeof v === "number" || typeof v === "bigint" ? "int" : Array.isArray(v) ? "array" : typeof v
export const sameNativeTaskValue = (a: TaskJson, b: TaskJson): boolean => kind(a) === kind(b) && nestedSame(a,b)
