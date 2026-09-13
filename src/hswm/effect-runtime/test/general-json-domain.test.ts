import { Either } from "effect"
import { expect,it } from "vitest"
import { decodeGeneralJsonBytes, decodeGeneralJsonWithNumberLexemesBytes } from "../src/general-json-domain.js"
const bytes=(s:string)=>new TextEncoder().encode(s)
it("accepts finite decimal and exponent values while retaining their source lexemes",()=>{const result=decodeGeneralJsonWithNumberLexemesBytes(bytes('{"a":1.0,"b":1e2,"c":-2.5}'));expect(Either.isRight(result)).toBe(true);if(Either.isRight(result)){expect(result.right.value).toEqual({a:1,b:100,c:-2.5});expect(result.right.numberLexemes).toEqual({"/a":"1.0","/b":"1e2","/c":"-2.5"})}})
it("rejects duplicate keys, unsafe integers, non-finite spellings and invalid UTF-8",()=>{for(const input of ['{"a":1,"a":2}','9007199254740992','1e999'])expect(Either.isLeft(decodeGeneralJsonBytes(bytes(input)))).toBe(true);const negativeZero=decodeGeneralJsonWithNumberLexemesBytes(bytes('-0'));expect(Either.isRight(negativeZero)).toBe(true);if(Either.isRight(negativeZero)){expect(negativeZero.right.value).toBe(0);expect(negativeZero.right.numberLexemes).toEqual({'':'-0'})}expect(Either.isLeft(decodeGeneralJsonBytes(Uint8Array.from([0xff])))).toBe(true)})
it("enforces caller byte and nesting bounds",()=>{expect(Either.isLeft(decodeGeneralJsonBytes(bytes('[]'),{maximumBytes:1}))).toBe(true);expect(Either.isLeft(decodeGeneralJsonBytes(bytes('[[0]]'),{maximumDepth:1}))).toBe(true)})
it("refuses lone surrogates while preserving complete Unicode pairs", () => {
  for (const text of ['"\\ud800"', '"\\udfff"']) expect(Either.isLeft(decodeGeneralJsonBytes(bytes(text)))).toBe(true)
  expect(decodeGeneralJsonBytes(bytes('"\\ud83e\\udd8b"'))).toMatchObject({_tag: "Right", right: "🦋"})
})
