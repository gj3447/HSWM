/** Pure Python 3.12 str() projection for validated JSON-domain values. */
import { inflateSync } from "node:zlib";
import { isTaskNumber, nativeTaskSourceKeys, renderNativeTaskJson, taskJsonRecord, taskNumberIsFloat, type TaskJson } from "./native-task-json-domain.js";
import { PYTHON312_UCD15_NONPRINTABLE_RANGES_ZLIB_BASE64 } from "./native-python-isprintable-data.js";
const hex = (value: number, width: number): string => value.toString(16).padStart(width, "0");
type Range = readonly [
    number,
    number
];
const ranges = (): readonly Range[] => {
    const decoded: unknown = JSON.parse(inflateSync(Buffer.from(PYTHON312_UCD15_NONPRINTABLE_RANGES_ZLIB_BASE64, "base64")).toString("utf8"));
    if (!Array.isArray(decoded))
        return Object.freeze([]);
    const output: Range[] = [];
    for (const entry of decoded) {
        if (!Array.isArray(entry) || entry.length !== 2 || !Number.isInteger(entry[0]) || !Number.isInteger(entry[1]) || entry[0]! < 0 || entry[1]! < entry[0]!)
            return Object.freeze([]);
        output.push(Object.freeze([entry[0]!, entry[1]!] as const));
    }
    return Object.freeze(output);
};
const nonPrintableRanges = ranges();
export const pythonJsonIsPrintable = (character: string): boolean => {
    const codepoint = character.codePointAt(0);
    if (codepoint === undefined || character !== String.fromCodePoint(codepoint))
        return false;
    let low = 0, high = nonPrintableRanges.length - 1;
    while (low <= high) {
        const middle = Math.floor((low + high) / 2), range = nonPrintableRanges[middle]!;
        if (codepoint < range[0])
            high = middle - 1;
        else if (codepoint > range[1])
            low = middle + 1;
        else
            return false;
    }
    return true;
};
const pythonStringRepr = (value: string): string => {
    const quote = value.includes("'") && !value.includes("\"") ? "\"" : "'";
    let output = quote;
    for (const character of value) {
        const codepoint = character.codePointAt(0)!;
        if (character === "\\")
            output += "\\\\";
        else if (character === quote)
            output += `\\${quote}`;
        else if (character === "\t")
            output += "\\t";
        else if (character === "\n")
            output += "\\n";
        else if (character === "\r")
            output += "\\r";
        else if (pythonJsonIsPrintable(character))
            output += character;
        else if (codepoint <= 0xff)
            output += `\\x${hex(codepoint, 2)}`;
        else if (codepoint <= 0xffff)
            output += `\\u${hex(codepoint, 4)}`;
        else
            output += `\\U${hex(codepoint, 8)}`;
    }
    return output + quote;
};
const pythonJsonRepr = (value: TaskJson): string => {
    if (value === null)
        return "None";
    if (typeof value === "boolean")
        return value ? "True" : "False";
    if (typeof value === "string")
        return pythonStringRepr(value);
    if (isTaskNumber(value))
        return taskNumberIsFloat(value) ? renderNativeTaskJson(value) : String(value);
    if (Array.isArray(value))
        return `[${value.map(pythonJsonRepr).join(", ")}]`;
    if (taskJsonRecord(value))
        return `{${nativeTaskSourceKeys(value).map(key => `${pythonStringRepr(key)}: ${pythonJsonRepr(value[key]!)}`).join(", ")}}`;
    return "";
};
/** Exact Python str(value) for a prevalidated TaskJson value. */
export const pythonJsonString = (value: TaskJson): string => typeof value === "string" ? value : pythonJsonRepr(value);
