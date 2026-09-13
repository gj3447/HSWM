import {readFileSync} from "node:fs"
import {Either} from "effect"
import {expect,it} from "vitest"
import {readNativeP1Npz,decodeNativeP1Npy} from "../src/native-p1-npy-domain.js"
const encoded=readFileSync(new URL("../../../../tests/fixtures/native_migration/p1_gate_v1/embedding-cache.npz.base64",import.meta.url),"utf8")
const bytes=Buffer.from(encoded,"base64")
const unwrap=<A,E>(value:Either.Either<A,E>):A=>{if(Either.isLeft(value))throw new Error(JSON.stringify(value.left));return value.right}
it("decodes the actual original NumPy compressed ZIP64 cache and UTF-32 arrays",()=>{
 const members=unwrap(readNativeP1Npz(bytes))
 expect(Object.keys(members).sort()).toEqual(["documents.npy","manifest.npy","question_ids.npy","questions.npy"])
 expect(unwrap(decodeNativeP1Npy(members["documents.npy"]!))).toEqual({dtype:"f8",shape:[390,1],values:Array(390).fill(0)})
 const ids=unwrap(decodeNativeP1Npy(members["question_ids.npy"]!));expect(ids.shape).toEqual([390]);expect(ids.values.every(value=>typeof value==="string"&&/^q\d{3}$/.test(value))).toBe(true)
 expect(unwrap(decodeNativeP1Npy(members["manifest.npy"]!)).shape).toEqual([])
})
it("rejects corrupt compressed data and truncated central records without untyped exceptions",()=>{
 const damaged=Buffer.from(bytes);damaged[120]=damaged[120]!^0xff
 expect(Either.isLeft(readNativeP1Npz(damaged))).toBe(true)
 expect(Either.isLeft(readNativeP1Npz(bytes.subarray(0,-1)))).toBe(true)
})
