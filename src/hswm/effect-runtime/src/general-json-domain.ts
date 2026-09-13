/** General JSON decoder for bounded local CLI input.  Unlike canonical-json/v1,
 * it accepts finite decimal/exponent numbers but rejects duplicate keys and
 * unsafe integers before JavaScript number conversion. */
import { Data, Either } from "effect";
export type GeneralJson = null | boolean | string | number | ReadonlyArray<GeneralJson> | {
    readonly [key: string]: GeneralJson;
};
export class GeneralJsonError extends Data.TaggedError("GeneralJsonError")<{
    readonly code: "BYTE_LIMIT_EXCEEDED" | "UTF8_INVALID" | "JSON_INVALID" | "DUPLICATE_KEY" | "DEPTH_LIMIT_EXCEEDED" | "NUMBER_INVALID" | "STRING_INVALID";
    readonly detail: string;
}> {
}
export interface GeneralJsonOptions {
    readonly maximumBytes?: number;
    readonly maximumDepth?: number;
}
export interface GeneralJsonWithNumberLexemes {
    readonly value: GeneralJson;
    readonly numberLexemes: Readonly<Record<string, string>>;
    readonly objectKeys: Readonly<Record<string, readonly string[]>>;
}
const fail = <A = never>(code: GeneralJsonError["code"], detail: string): Either.Either<A, GeneralJsonError> => Either.left(new GeneralJsonError({ code, detail }));
const retype = <A>(value: Either.Either<unknown, GeneralJsonError>): Either.Either<A, GeneralJsonError> => Either.isLeft(value) ? Either.left(value.left) : fail("JSON_INVALID", "unexpected parser branch");
const ws = (x: string) => x === " " || x === "\n" || x === "\r" || x === "\t";
const pointer = (base: string, key: string | number) => `${base}/${String(key).replace(/~/g, "~0").replace(/\//g, "~1")}`;
const surrogate = (value: string) => { for (let i = 0; i < value.length; i++) {
    const n = value.charCodeAt(i);
    if (n >= 0xd800 && n <= 0xdbff) {
        const next = value.charCodeAt(i + 1);
        if (!Number.isFinite(next) || next < 0xdc00 || next > 0xdfff)
            return true;
        i++;
    }
    else if (n >= 0xdc00 && n <= 0xdfff)
        return true;
} return false; };
class Parser {
    private at = 0;
    private readonly lexemes: Record<string, string> = Object.create(null);
    private readonly objectKeyOrder: Record<string, string[]> = Object.create(null);
    constructor(private readonly text: string, private readonly maxDepth: number, private readonly preserveUnsafeIntegers = false) { }
    parse(): Either.Either<GeneralJsonWithNumberLexemes, GeneralJsonError> { this.space(); const value = this.value("", 0); if (Either.isLeft(value))
        return retype(value); this.space(); return this.at === this.text.length ? Either.right({ value: value.right, numberLexemes: Object.freeze({ ...this.lexemes }), objectKeys: Object.freeze(Object.fromEntries(Object.entries(this.objectKeyOrder).map(([path, keys]) => [path, Object.freeze(keys)]))) }) : fail("JSON_INVALID", "trailing non-whitespace data follows JSON value"); }
    private space() { while (ws(this.text[this.at] ?? ""))
        this.at++; }
    private value(path: string, depth: number): Either.Either<GeneralJson, GeneralJsonError> { if (depth > this.maxDepth)
        return fail("DEPTH_LIMIT_EXCEEDED", "JSON nesting exceeds declared bound"); const c = this.text[this.at]; if (c === '"')
        return this.string(); if (c === "{")
        return this.object(path, depth + 1); if (c === "[")
        return this.array(path, depth + 1); if (c === "t" && this.take("true"))
        return Either.right(true); if (c === "f" && this.take("false"))
        return Either.right(false); if (c === "n" && this.take("null"))
        return Either.right(null); if (c === "-" || (c !== undefined && c >= "0" && c <= "9"))
        return this.number(path); return fail("JSON_INVALID", `invalid JSON value at offset ${this.at}`); }
    private take(word: string) { if (!this.text.startsWith(word, this.at))
        return false; this.at += word.length; return true; }
    private string(): Either.Either<string, GeneralJsonError> { this.at++; let out = ""; while (this.at < this.text.length) {
        const c = this.text[this.at++]!;
        if (c === '"')
            return surrogate(out) ? fail("STRING_INVALID", "JSON string contains a lone surrogate") : Either.right(out);
        if (c.charCodeAt(0) < 32)
            return fail("JSON_INVALID", "unescaped control character");
        if (c !== "\\") {
            out += c;
            continue;
        }
        const esc = this.text[this.at++];
        if (esc === undefined)
            return fail("JSON_INVALID", "unterminated JSON escape");
        const simple: Record<string, string> = { '"': '"', '\\': '\\', '/': '/', 'b': '\b', 'f': '\f', 'n': '\n', 'r': '\r', 't': '\t' };
        if (esc === "u") {
            const hex = this.text.slice(this.at, this.at + 4);
            if (!/^[0-9a-fA-F]{4}$/.test(hex))
                return fail("JSON_INVALID", "invalid unicode escape");
            out += String.fromCharCode(parseInt(hex, 16));
            this.at += 4;
        }
        else if (Object.hasOwn(simple, esc))
            out += simple[esc]!;
        else
            return fail("JSON_INVALID", "invalid JSON escape");
    } return fail("JSON_INVALID", "unterminated JSON string"); }
    private number(path: string): Either.Either<number, GeneralJsonError> { const start = this.at; if (this.text[this.at] === "-")
        this.at++; if (this.text[this.at] === "0")
        this.at++;
    else if (/[1-9]/.test(this.text[this.at] ?? "")) {
        this.at++;
        while (/[0-9]/.test(this.text[this.at] ?? ""))
            this.at++;
    }
    else
        return fail("NUMBER_INVALID", "invalid JSON number"); if (this.text[this.at] === ".") {
        this.at++;
        if (!/[0-9]/.test(this.text[this.at] ?? ""))
            return fail("NUMBER_INVALID", "invalid decimal number");
        while (/[0-9]/.test(this.text[this.at] ?? ""))
            this.at++;
    } if (this.text[this.at] === "e" || this.text[this.at] === "E") {
        this.at++;
        if (this.text[this.at] === "+" || this.text[this.at] === "-")
            this.at++;
        if (!/[0-9]/.test(this.text[this.at] ?? ""))
            return fail("NUMBER_INVALID", "invalid exponent");
        while (/[0-9]/.test(this.text[this.at] ?? ""))
            this.at++;
    } const raw = this.text.slice(start, this.at); const value = Number(raw); const integer = !/[.eE]/.test(raw); if (integer && this.preserveUnsafeIntegers && raw.replace(/^-/, "").length > 4300) return fail("NUMBER_INVALID", "integer exceeds the historical 4300-digit input bound"); if (integer && this.preserveUnsafeIntegers && !Number.isSafeInteger(value)) { this.lexemes[path] = raw; return Either.right(0); } if (!Number.isFinite(value) || (integer && !Number.isSafeInteger(value)))
        return fail("NUMBER_INVALID", "number is non-finite or unsafe integer"); this.lexemes[path] = raw; return Either.right(Object.is(value, -0) ? 0 : value); }
    private array(path: string, depth: number): Either.Either<ReadonlyArray<GeneralJson>, GeneralJsonError> { this.at++; this.space(); const out: GeneralJson[] = []; if (this.text[this.at] === "]") {
        this.at++;
        return Either.right(out);
    } for (let i = 0;; i++) {
        this.space();
        const child = this.value(pointer(path, i), depth);
        if (Either.isLeft(child))
            return retype(child);
        out.push(child.right);
        this.space();
        if (this.text[this.at] === "]") {
            this.at++;
            return Either.right(out);
        }
        if (this.text[this.at++] !== ",")
            return fail("JSON_INVALID", "array separator missing");
    } }
    private object(path: string, depth: number): Either.Either<{
        readonly [key: string]: GeneralJson;
    }, GeneralJsonError> { this.at++; this.space(); const out: Record<string, GeneralJson> = Object.create(null); const keys: string[] = []; this.objectKeyOrder[path] = keys; if (this.text[this.at] === "}") {
        this.at++;
        return Either.right(out);
    } for (;;) {
        this.space();
        if (this.text[this.at] !== "\"")
            return fail("JSON_INVALID", "object key must be string");
        const k = this.string();
        if (Either.isLeft(k))
            return retype(k);
        if (Object.hasOwn(out, k.right))
            return fail("DUPLICATE_KEY", `duplicate JSON key ${k.right}`);
        this.space();
        if (this.text[this.at++] !== ":")
            return fail("JSON_INVALID", "object colon missing");
        this.space();
        const child = this.value(pointer(path, k.right), depth);
        if (Either.isLeft(child))
            return retype(child);
        out[k.right] = child.right;
        keys.push(k.right);
        this.space();
        if (this.text[this.at] === "}") {
            this.at++;
            return Either.right(out);
        }
        if (this.text[this.at++] !== ",")
            return fail("JSON_INVALID", "object separator missing");
    } }
}
const decode = (bytes: Uint8Array, options: GeneralJsonOptions, preserveUnsafeIntegers = false): Either.Either<GeneralJsonWithNumberLexemes, GeneralJsonError> => { const maximum = options.maximumBytes ?? 1048576; const depth = options.maximumDepth ?? 128; if (!Number.isSafeInteger(maximum) || maximum < 1 || !Number.isSafeInteger(depth) || depth < 0)
    return fail("JSON_INVALID", "decoder bounds invalid"); if (bytes.byteLength > maximum)
    return fail("BYTE_LIMIT_EXCEEDED", "input exceeds declared byte bound"); let text: string; try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
}
catch {
    return fail("UTF8_INVALID", "input is not strict UTF-8");
} return new Parser(text, depth, preserveUnsafeIntegers).parse(); };
/** Token-preserving callback is mandatory: unsafe integer placeholders never escape this API. */
export const decodeGeneralJsonThroughNumberLexemes = <A>(bytes: Uint8Array, restore: (decoded: GeneralJsonWithNumberLexemes) => A, options: GeneralJsonOptions = {}): Either.Either<A, GeneralJsonError> => decode(bytes, options, true).pipe(Either.map(restore));
export const decodeGeneralJsonWithNumberLexemesBytes = (bytes: Uint8Array, options: GeneralJsonOptions = {}): Either.Either<GeneralJsonWithNumberLexemes, GeneralJsonError> => decode(bytes, options);
export const decodeGeneralJsonBytes = (bytes: Uint8Array, options: GeneralJsonOptions = {}): Either.Either<GeneralJson, GeneralJsonError> => decode(bytes, options).pipe(Either.map((decoded) => decoded.value));
