/** Read only the non-pickle NumPy arrays written by frozen P1 `np.savez_compressed`. */
import { inflateRawSync } from "node:zlib"
import { Data, Either } from "effect"

export class NativeP1NpyError extends Data.TaggedError("NativeP1NpyError")<{readonly detail:string}>{}
const failure=(detail:string)=>new NativeP1NpyError({detail})
const utf8=new TextDecoder("utf-8",{fatal:true}),ascii=new TextDecoder("ascii",{fatal:true})
const u16=(bytes:Uint8Array,offset:number)=>bytes[offset]!|(bytes[offset+1]!<<8)
const u32=(bytes:Uint8Array,offset:number)=>((bytes[offset]!|(bytes[offset+1]!<<8)|(bytes[offset+2]!<<16)|(bytes[offset+3]!<<24))>>>0)
const u64=(bytes:Uint8Array,offset:number):number=>Number(BigInt(u32(bytes,offset))|(BigInt(u32(bytes,offset+4))<<32n))
const product=(shape:readonly number[]):number=>shape.reduce((total,value)=>total*value,1)

export type NativeP1NpyArray=Readonly<{readonly dtype:"f8"|"unicode";readonly shape:readonly number[];readonly values:readonly number[]|readonly string[]}>
const MAX_NPY_BYTES = 128 * 1024 * 1024
const crc32 = (bytes: Uint8Array): number => {
 let crc = 0xffffffff
 for (const byte of bytes) { crc ^= byte; for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ ((crc & 1) === 0 ? 0 : 0xedb88320) }
 return (crc ^ 0xffffffff) >>> 0
}
/** Central-directory sizes also cover NumPy's force_zip64 local headers and data descriptors. */
export const readNativeP1Npz = (archive: Uint8Array): Either.Either<Readonly<Record<string, Uint8Array>>, NativeP1NpyError> => {
 const fail = (detail: string) => Either.left(failure(detail))
 let end = -1
 for (let position = archive.length - 22; position >= Math.max(0, archive.length - 65557); position--) {
  if (u32(archive, position) === 0x06054b50 && position + 22 + u16(archive, position + 20) === archive.length) { end = position; break }
 }
 if (end < 0 || u16(archive,end+4)!==0 || u16(archive,end+6)!==0 || u16(archive,end+8)!==u16(archive,end+10)) return fail("invalid ZIP central directory")
 const count = u16(archive,end+10), directoryStart = u32(archive,end+16), directorySize = u32(archive,end+12)
 if (count===0 || count>1024 || directoryStart+directorySize!==end) return fail("unsupported ZIP central directory boundary")
 let position=directoryStart, inflatedTotal=0
 const entries: Record<string,Uint8Array> = {}, spans: Array<readonly [number,number]> = []
 for(let index=0;index<count;index++) {
  if(position+46>end || u32(archive,position)!==0x02014b50) return fail("truncated ZIP central record")
  const flags=u16(archive,position+8),method=u16(archive,position+10),crc=u32(archive,position+16)
  const nameLength=u16(archive,position+28),extraLength=u16(archive,position+30),commentLength=u16(archive,position+32)
  const nameStart=position+46,extraStart=nameStart+nameLength,extraEnd=extraStart+extraLength,recordEnd=extraEnd+commentLength
  if(recordEnd>end || (flags&1)!==0 || (method!==0&&method!==8) || u16(archive,position+34)!==0) return fail("unsupported ZIP entry")
  let name:string
  try{name=utf8.decode(archive.subarray(nameStart,extraStart))}catch{return fail("invalid ZIP member name")}
  if(!/^[A-Za-z0-9_]+\.npy$/.test(name)||Object.hasOwn(entries,name)) return fail("unsafe or duplicate ZIP member")
  let compressed=u32(archive,position+20),uncompressed=u32(archive,position+24),local=u32(archive,position+42)
  const needs64=compressed===0xffffffff||uncompressed===0xffffffff||local===0xffffffff
  if(needs64) {
   let cursor=extraStart,found=false
   while(cursor+4<=extraEnd) {
    const id=u16(archive,cursor),size=u16(archive,cursor+2),limit=cursor+4+size
    if(limit>extraEnd)return fail("truncated ZIP extra field")
    if(id===1) {
     let field=cursor+4
     if(uncompressed===0xffffffff){if(field+8>limit)return fail("missing ZIP64 size");uncompressed=u64(archive,field);field+=8}
     if(compressed===0xffffffff){if(field+8>limit)return fail("missing ZIP64 size");compressed=u64(archive,field);field+=8}
     if(local===0xffffffff){if(field+8>limit)return fail("missing ZIP64 offset");local=u64(archive,field)}
     found=true;break
    }
    cursor=limit
   }
   if(!found)return fail("missing ZIP64 extension")
  }
  if(![compressed,uncompressed,local].every(value=>Number.isSafeInteger(value)&&value>=0)||uncompressed>MAX_NPY_BYTES||local+30>directoryStart||u32(archive,local)!==0x04034b50)return fail("invalid ZIP member boundary")
  if(u16(archive,local+6)!==flags||u16(archive,local+8)!==method)return fail("ZIP local and central records disagree")
  const localNameLength=u16(archive,local+26),dataStart=local+30+localNameLength+u16(archive,local+28),dataEnd=dataStart+compressed
  if(dataEnd>directoryStart||dataStart<local+30||localNameLength!==nameLength)return fail("unsupported ZIP member boundary")
  for(let byte=0;byte<nameLength;byte++)if(archive[local+30+byte]!==archive[nameStart+byte])return fail("ZIP local member name differs")
  if(spans.some(([start,finish])=>local<finish&&dataEnd>start))return fail("overlapping ZIP members")
  let bytes:Uint8Array
  try{bytes=method===0?archive.slice(dataStart,dataEnd):new Uint8Array(inflateRawSync(archive.subarray(dataStart,dataEnd),{maxOutputLength:Math.max(1,uncompressed)}))}catch{return fail("invalid or oversized deflated ZIP member")}
  inflatedTotal+=bytes.length
  if(bytes.length!==uncompressed||crc32(bytes)!==crc||inflatedTotal>MAX_NPY_BYTES)return fail("ZIP member length or CRC mismatch")
  spans.push([local,dataEnd]);entries[name]=bytes;position=recordEnd
 }
 return position!==end?fail("ZIP central directory count drift"):Either.right(Object.freeze(entries))
}
export const decodeNativeP1Npy=(bytes:Uint8Array):Either.Either<NativeP1NpyArray,NativeP1NpyError>=>{
 if(bytes.length<10||bytes[0]!==0x93||ascii.decode(bytes.slice(1,6))!=="NUMPY")return Either.left(failure("invalid NPY magic"))
 const major=bytes[6]!,minor=bytes[7]!,headerLength=major===1&&minor===0?u16(bytes,8):major===2&&minor===0?u32(bytes,8):0,headerStart=major===1?10:12,headerEnd=headerStart+headerLength
 if(headerLength===0||headerEnd>bytes.length)return Either.left(failure("unsupported or truncated NPY header"))
 let header:string
 try{header=ascii.decode(bytes.slice(headerStart,headerEnd))}catch{return Either.left(failure("invalid NPY header"))}
 const dtype=/'descr':\s*'([^']+)'/.exec(header)?.[1],fortran=/'fortran_order':\s*(True|False)/.exec(header)?.[1],shapeText=/'shape':\s*\(([^)]*)\)/.exec(header)?.[1]
 if((dtype!=="<f8"&&!/^<U\d+$/.test(dtype??""))||fortran!=="False"||shapeText===undefined)return Either.left(failure("unsupported NPY dtype or layout"))
 const shape=shapeText.split(",").map(value=>value.trim()).filter(value=>value!=="").map(value=>Number(value))
 if(shape.some(value=>!Number.isSafeInteger(value)||value<0)||product(shape)>16_000_000)return Either.left(failure("invalid NPY shape"))
 const count=product(shape),data=bytes.slice(headerEnd)
 if(dtype==="<f8"){
  if(data.length!==count*8)return Either.left(failure("NPY float payload length drift"))
  const view=new DataView(data.buffer,data.byteOffset,data.byteLength),values=Object.freeze(Array.from({length:count},(_,index)=>view.getFloat64(index*8,true)))
  return values.some(value=>!Number.isFinite(value))?Either.left(failure("NPY float payload is non-finite")):Either.right(Object.freeze({dtype:"f8",shape:Object.freeze(shape),values}))
 }
 const width=Number(dtype!.slice(2))
 if(!Number.isSafeInteger(width)||width<1||data.length!==count*width*4)return Either.left(failure("NPY unicode payload length drift"))
 const view = new DataView(data.buffer,data.byteOffset,data.byteLength),values:string[]=[]
 for(let index=0;index<count;index++) {
  const points:number[]=[]
  for(let offset=0;offset<width;offset++){const point=view.getUint32((index*width+offset)*4,true);if(point>0x10ffff||(point>=0xd800&&point<=0xdfff))return Either.left(failure("invalid NPY unicode payload"));points.push(point)}
  while(points.at(-1)===0)points.pop()
  values.push(points.map(point=>String.fromCodePoint(point)).join(""))
 }
 return Either.right(Object.freeze({dtype:"unicode",shape:Object.freeze(shape),values:Object.freeze(values)}))
}
export const decodeNativeP1EmbeddingCache=(archive:Uint8Array,expectedManifest:string):Either.Either<Readonly<{readonly documents:NativeP1NpyArray;readonly questionIds:NativeP1NpyArray;readonly questions:NativeP1NpyArray}>,NativeP1NpyError>=>{
 const entries=readNativeP1Npz(archive);if(Either.isLeft(entries))return Either.left(entries.left)
 const manifest=decodeNativeP1Npy(entries.right["manifest.npy"]??new Uint8Array());if(Either.isLeft(manifest))return Either.left(manifest.left)
 const documents=decodeNativeP1Npy(entries.right["documents.npy"]??new Uint8Array());if(Either.isLeft(documents))return Either.left(documents.left)
 const questionIds=decodeNativeP1Npy(entries.right["question_ids.npy"]??new Uint8Array());if(Either.isLeft(questionIds))return Either.left(questionIds.left)
 const questions=decodeNativeP1Npy(entries.right["questions.npy"]??new Uint8Array());if(Either.isLeft(questions))return Either.left(questions.left)
 if(manifest.right.dtype!=="unicode"||manifest.right.shape.length!==0||manifest.right.values[0]!==expectedManifest)return Either.left(failure("embedding cache manifest drift"))
 if(documents.right.dtype!=="f8"||documents.right.shape.length!==2||questions.right.dtype!=="f8"||questions.right.shape.length!==2||questionIds.right.dtype!=="unicode"||questionIds.right.shape.length!==1||questions.right.shape[0]!==questionIds.right.shape[0]||documents.right.shape[1]!==questions.right.shape[1])return Either.left(failure("embedding cache array shape or dtype drift"))
 return Either.right(Object.freeze({documents:documents.right,questionIds:questionIds.right,questions:questions.right}))
}
