/** Typed Effect services for native research-fabric observation and control. */
import { spawn } from "node:child_process"
import { createHash, randomBytes } from "node:crypto"
import { constants } from "node:fs"
import { access, lstat, mkdir, open, readFile, realpath, unlink } from "node:fs/promises"
import type { FileHandle } from "node:fs/promises"
import { request } from "node:http"
import { connect } from "node:net"
import { Context, Data, Effect, Layer } from "effect"
import type { FabricProcessIdentity, FabricServiceSpec } from "./native-research-fabric-domain.js"

export class ResearchFabricRuntimeError extends Data.TaggedError("ResearchFabricRuntimeError")<{ readonly detail: string; readonly causeCode?: string | null }> {}
export interface ResearchFabricRuntimeShape {
  readonly environment: Effect.Effect<Readonly<Record<string, string | undefined>>>
  readonly processIdentity: (pid: number) => Effect.Effect<FabricProcessIdentity | null>
  readonly tcpReady: (host: string, port: number) => Effect.Effect<boolean>
  readonly httpReady: (url: string) => Effect.Effect<readonly [boolean, number | null]>
  readonly executable: (path: string) => Effect.Effect<{ readonly sha256: string; readonly realpath: string } | null, ResearchFabricRuntimeError>
  readonly readText: (path: string, maximumBytes: number) => Effect.Effect<string | null, ResearchFabricRuntimeError>
  readonly readPrivateText: (path: string, maximumBytes: number) => Effect.Effect<string | null, ResearchFabricRuntimeError>
  readonly writePrivateExclusive: (path: string, text: string) => Effect.Effect<void, ResearchFabricRuntimeError>
  readonly ensurePrivateDirectory: (path: string) => Effect.Effect<void, ResearchFabricRuntimeError>
  readonly unlinkIfPresent: (path: string) => Effect.Effect<void, ResearchFabricRuntimeError>
  readonly randomHex: (bytes: number) => Effect.Effect<string>
  readonly nowUnixNs: Effect.Effect<bigint>
  readonly monotonicMs: Effect.Effect<number>
  readonly launch: (spec: FabricServiceSpec, environment: Readonly<Record<string, string>>, logPath: string) => Effect.Effect<FabricProcessIdentity, ResearchFabricRuntimeError>
  readonly signalGroup: (pid: number, signal: NodeJS.Signals) => Effect.Effect<void, ResearchFabricRuntimeError>
  readonly sleep: (milliseconds: number) => Effect.Effect<void>
}
export class ResearchFabricRuntime extends Context.Tag("hswm/ResearchFabricRuntime")<ResearchFabricRuntime, ResearchFabricRuntimeShape>() {}
const runtimeError = (detail: string, cause?: unknown): ResearchFabricRuntimeError => new ResearchFabricRuntimeError({ detail, causeCode: typeof cause === "object" && cause !== null && "code" in cause && typeof cause.code === "string" ? cause.code : null })
const attempt = <A>(work: () => Promise<A>, detail: string): Effect.Effect<A, ResearchFabricRuntimeError> => Effect.tryPromise({ try: work, catch: cause => runtimeError(detail,cause) })
const processStartTicks = (stat: string): number | null => { const close=stat.lastIndexOf(")"),start=close<0?undefined:stat.slice(close+1).trim().split(/\s+/)[19];return start!==undefined&&/^\d+$/u.test(start)&&Number.isSafeInteger(Number(start))?Number(start):null }
const cmdline = (value: string): readonly string[] => Object.freeze(value.split("\0").filter(Boolean))
const currentUid = (): number | null => process.getuid?.() ?? null
const withFile = <A>(path:string, flags:number, mode:number, work:(handle:FileHandle)=>Effect.Effect<A,ResearchFabricRuntimeError>):Effect.Effect<A,ResearchFabricRuntimeError> => Effect.acquireUseRelease(attempt(()=>open(path,flags,mode),"cannot open fabric file"),work,handle=>attempt(()=>handle.close(),"cannot close fabric file").pipe(Effect.orDie))
const readBounded = (path:string,maximumBytes:number,privateOnly:boolean):Effect.Effect<string|null,ResearchFabricRuntimeError> => withFile(path,constants.O_RDONLY|constants.O_NOFOLLOW,0,handle=>Effect.gen(function*(){
 const info=yield*attempt(()=>handle.stat(),"cannot inspect fabric file")
 if(!info.isFile()||info.size>maximumBytes||privateOnly&&(currentUid()===null||info.uid!==currentUid()||(info.mode&0o077)!==0))return yield*Effect.fail(runtimeError("unsafe or oversized fabric file"))
 const buffer=Buffer.alloc(maximumBytes+1)
 let total=0
 while(total<buffer.length){const offset=total,part=yield*attempt(()=>handle.read(buffer,offset,buffer.length-offset,null),"cannot read fabric file");if(part.bytesRead===0)break;total+=part.bytesRead}
 const after=yield*attempt(()=>handle.stat(),"cannot recheck fabric file")
 if(total>maximumBytes||info.size!==after.size||info.mtimeMs!==after.mtimeMs||privateOnly&&(after.uid!==info.uid||after.mode!==info.mode))return yield*Effect.fail(runtimeError("fabric file changed or exceeded read bound"))
 return yield*Effect.try({try:()=>new TextDecoder("utf-8",{fatal:true}).decode(buffer.subarray(0,total)),catch:()=>runtimeError("fabric file is not UTF-8")})
})).pipe(Effect.catchIf(error=>error.causeCode==="ENOENT",()=>Effect.succeed(null)))
const executable = (path:string):Effect.Effect<{readonly sha256:string;readonly realpath:string}|null,ResearchFabricRuntimeError> => Effect.gen(function*(){
 yield*attempt(()=>access(path,constants.X_OK),"cannot access executable")
 const resolved=yield*attempt(()=>realpath(path),"cannot resolve executable")
 const sha256=yield*withFile(resolved,constants.O_RDONLY|constants.O_NOFOLLOW,0,handle=>Effect.gen(function*(){
  const before=yield*attempt(()=>handle.stat(),"cannot inspect executable")
  if(!before.isFile()||before.size>512*1024*1024)return yield*Effect.fail(runtimeError("executable exceeds 512 MiB bound"))
  const digest=createHash("sha256"),buffer=Buffer.alloc(1024*1024)
  let total=0
  while(true){const part=yield*attempt(()=>handle.read(buffer,0,buffer.length,null),"cannot hash executable");if(part.bytesRead===0)break;total+=part.bytesRead;if(total>512*1024*1024)return yield*Effect.fail(runtimeError("executable grew beyond byte bound"));digest.update(buffer.subarray(0,part.bytesRead))}
  const after=yield*attempt(()=>handle.stat(),"cannot recheck executable")
  if(before.size!==after.size||before.mtimeMs!==after.mtimeMs)return yield*Effect.fail(runtimeError("executable changed while hashing"))
  return digest.digest("hex")
 }))
 return Object.freeze({sha256,realpath:resolved})
}).pipe(Effect.catchAll(()=>Effect.succeed(null)))
const processIdentity = (pid:number):Effect.Effect<FabricProcessIdentity|null> => Effect.gen(function*(){
 if(!Number.isSafeInteger(pid)||pid<=0)return null
 const [stat,raw]=yield*attempt(()=>Promise.all([readFile(`/proc/${pid}/stat`,"utf8"),readFile(`/proc/${pid}/cmdline`,"utf8")]),"cannot inspect process identity")
 const startTicks=processStartTicks(stat),args=cmdline(raw)
 return startTicks===null||args.length===0?null:Object.freeze({pid,startTicks,cmdline:args})
}).pipe(Effect.catchAll(()=>Effect.succeed(null)))
const launch = (spec:FabricServiceSpec,environment:Readonly<Record<string,string>>,logPath:string):Effect.Effect<FabricProcessIdentity,ResearchFabricRuntimeError> => withFile(logPath,constants.O_WRONLY|constants.O_CREAT|constants.O_APPEND|constants.O_NOFOLLOW,0o600,handle=>Effect.gen(function*(){
 const info=yield*attempt(()=>handle.stat(),"cannot inspect service log")
 if(!info.isFile()||info.uid!==currentUid()||(info.mode&0o077)!==0)return yield*Effect.fail(runtimeError("unsafe service log"))
 const child=yield*Effect.try({try:()=>spawn(spec.executable,spec.argv,{stdio:["ignore",handle.fd,handle.fd],env:environment,detached:true,shell:false}),catch:cause=>runtimeError("cannot launch service",cause)})
 yield*Effect.async<void,ResearchFabricRuntimeError>(resume=>{child.once("error",cause=>resume(Effect.fail(runtimeError("cannot launch service",cause))));child.once("spawn",()=>resume(Effect.void))})
 const pid=child.pid
 child.unref()
 if(pid===undefined)return yield*Effect.fail(runtimeError("service has no process ID"))
 const identity=yield*processIdentity(pid)
 return identity===null?yield*Effect.fail(runtimeError("service exited before identity could be recorded")):identity
}))
const nodeRuntime:ResearchFabricRuntimeShape=Object.freeze({
 environment:Effect.sync(()=>Object.freeze({...process.env})),processIdentity,
 tcpReady:(host:string,port:number)=>Effect.async<boolean>(resume=>{const socket=connect({host,port});const done=(value:boolean):void=>{socket.removeAllListeners();socket.destroy();resume(Effect.succeed(value))};socket.setTimeout(1000);socket.once("connect",()=>done(true));socket.once("timeout",()=>done(false));socket.once("error",()=>done(false));return Effect.sync(()=>socket.destroy())}),
 httpReady:(url:string)=>Effect.async<readonly[boolean,number|null]>(resume=>{const req=request(url,{headers:{"User-Agent":"hswm-research-fabric/1"},timeout:2000},res=>{res.resume();resume(Effect.succeed([res.statusCode!==undefined&&res.statusCode>=200&&res.statusCode<400,res.statusCode??null]as const))});req.once("timeout",()=>{req.destroy();resume(Effect.succeed([false,null]as const))});req.once("error",()=>resume(Effect.succeed([false,null]as const)));req.end();return Effect.sync(()=>req.destroy())}),
 executable,readText:(path:string,max:number)=>readBounded(path,max,false),readPrivateText:(path:string,max:number)=>readBounded(path,max,true),
 writePrivateExclusive:(path:string,text:string)=>withFile(path,constants.O_WRONLY|constants.O_CREAT|constants.O_EXCL|constants.O_NOFOLLOW,0o600,handle=>attempt(()=>handle.writeFile(text,"utf8"),"cannot write fabric file").pipe(Effect.zipRight(attempt(()=>handle.sync(),"cannot sync fabric file")))),
 ensurePrivateDirectory:(path:string)=>Effect.gen(function*(){yield*attempt(()=>mkdir(path,{recursive:true,mode:0o700}),"cannot create fabric directory");const info=yield*attempt(()=>lstat(path),"cannot inspect fabric directory");if(!info.isDirectory()||currentUid()===null||info.uid!==currentUid()||(info.mode&0o077)!==0)return yield*Effect.fail(runtimeError("unsafe fabric directory"))}),
 unlinkIfPresent:(path:string)=>attempt(()=>unlink(path),"cannot remove fabric record").pipe(Effect.catchIf(error=>error.causeCode==="ENOENT",()=>Effect.void)),
 randomHex:(bytes:number)=>Effect.sync(()=>randomBytes(bytes).toString("hex")),nowUnixNs:Effect.sync(()=>BigInt(Date.now())*1000000n),monotonicMs:Effect.sync(()=>performance.now()),launch,
 signalGroup:(pid:number,signal:NodeJS.Signals)=>Effect.try({try:()=>{process.kill(-pid,signal)},catch:cause=>runtimeError("cannot signal research-fabric process group",cause)}),sleep:(milliseconds:number)=>Effect.sleep(milliseconds)
})
export const NodeResearchFabricRuntimeLive:Layer.Layer<ResearchFabricRuntime>=Layer.succeed(ResearchFabricRuntime,nodeRuntime)
