/** Python 3.12 JSON-value equality and int conversion used by frozen receipt verifiers. */
import { isTaskNumber, taskJsonRecord, taskNumberValue, type TaskJson } from "./native-task-json-domain.js";
import { PYTHON_JSON_CASEFOLD } from "./native-python-casefold-data.js";
const stripSpace = /^[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+|[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+$/gu;
const splitSpace = /[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/u;
export const pythonJsonStrip = (value: string): string => value.replace(stripSpace, "");
export const pythonJsonCasefold = (value: string): string => Array.from(value, character => PYTHON_JSON_CASEFOLD[String(character.codePointAt(0)!)] ?? character).join("");
export const pythonJsonNormalizeAnswer = (value: string): string => pythonJsonStrip(pythonJsonCasefold(value)).split(splitSpace).filter(Boolean).join(" ");
const numericValue = (value: TaskJson): number | bigint | undefined => isTaskNumber(value) ? taskNumberValue(value) : typeof value === "boolean" ? Number(value) : undefined;
export const pythonJsonEqual = (left: TaskJson, right: TaskJson): boolean => {
    const a = numericValue(left), b = numericValue(right);
    if (a !== undefined && b !== undefined)
        return a <= b && a >= b;
    if (Array.isArray(left) && Array.isArray(right))
        return left.length === right.length && left.every((value, index) => pythonJsonEqual(value, right[index]!));
    if (taskJsonRecord(left) && taskJsonRecord(right))
        return Object.keys(left).length === Object.keys(right).length && Object.keys(left).every(key => Object.hasOwn(right, key) && pythonJsonEqual(left[key]!, right[key]!));
    return left === right;
};
// Source: the original Python 3.12 interpreter's unicodedata 15.0.0; the complete
// table is independently pinned by the receipt semantics oracle. Do not inherit
// a newer Node Unicode version when replaying the original verifier.
export const PYTHON_JSON_DECIMAL_ZEROS = Object.freeze([
    48, 1632, 1776, 1984, 2406, 2534, 2662, 2790, 2918, 3046, 3174, 3302,
    3430, 3558, 3664, 3792, 3872, 4160, 4240, 6112, 6160, 6470, 6608, 6784,
    6800, 6992, 7088, 7232, 7248, 42528, 43216, 43264, 43472, 43504, 43600,
    44016, 65296, 66720, 68912, 69734, 69872, 69942, 70096, 70384, 70736,
    70864, 71248, 71360, 71472, 71904, 72016, 72784, 73040, 73120, 73552,
    92768, 92864, 93008, 120782, 120792, 120802, 120812, 120822, 123200,
    123632, 124144, 125264, 130032,
]);
const intSpace = /^[\u0009-\u000d\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+|[\u0009-\u000d\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+$/gu;
/** Undefined is conversion failure; callers must apply their own dict.get default. */
export const pythonJsonInt = (value: TaskJson | undefined): bigint | undefined => {
    if (value === undefined)
        return undefined;
    const numeric = numericValue(value);
    if (numeric !== undefined)
        return typeof numeric === "bigint" ? numeric : BigInt(Math.trunc(numeric));
    if (typeof value !== "string")
        return undefined;
    const ascii = Array.from(value.replace(intSpace, ""), character => {
        const codepoint = character.codePointAt(0)!;
        const zero = PYTHON_JSON_DECIMAL_ZEROS.find(start => codepoint >= start && codepoint < start + 10);
        return zero === undefined ? character : String(codepoint - zero);
    }).join("");
    if (!/^[+-]?[0-9](?:_?[0-9])*$/u.test(ascii))
        return undefined;
    const digits = ascii.replaceAll("_", "");
    const length = /^[+-]/.test(digits) ? digits.length - 1 : digits.length;
    return length > 4300 ? undefined : BigInt(digits);
};
