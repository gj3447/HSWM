/** Durable atomic output for the offline P1 diagnostic. */
import { randomUUID } from "node:crypto"
import { dirname, join } from "node:path"
import { open, rename, unlink } from "node:fs/promises"
import { Data, Effect } from "effect"

export class NativeP1OutputError extends Data.TaggedError("NativeP1OutputError")<{readonly detail:string}>{}
const failure=(detail:string)=>new NativeP1OutputError({detail})
const attempt=<Value>(thunk:()=>Promise<Value>,detail:string):Effect.Effect<Value,NativeP1OutputError>=>Effect.tryPromise({try:thunk,catch:error=>failure(error instanceof Error?`${detail}: ${error.message}`:detail)})
export const writeNativeP1OutputAtomic=(path:string,bytes:Uint8Array):Effect.Effect<void,NativeP1OutputError>=>Effect.gen(function*(){
 const directory=dirname(path),temporary=join(directory,`.native-p1-${randomUUID()}.tmp`)
 yield* Effect.acquireUseRelease(
 attempt(()=>open(temporary,"wx",0o600),"cannot create temporary P1 output"),
  handle=>Effect.gen(function*(){yield* attempt(()=>handle.writeFile(bytes),"cannot write temporary P1 output");yield* attempt(()=>handle.sync(),"cannot fsync temporary P1 output");yield* attempt(()=>handle.close(),"cannot close temporary P1 output");yield* attempt(()=>rename(temporary,path),"cannot publish P1 output");const parent=yield* attempt(()=>open(directory,"r"),"cannot open P1 output directory");yield* Effect.acquireUseRelease(Effect.succeed(parent),directoryHandle=>attempt(()=>directoryHandle.sync(),"cannot fsync P1 output directory"),directoryHandle=>attempt(()=>directoryHandle.close(),"cannot close P1 output directory").pipe(Effect.ignore))}),
  handle=>attempt(()=>handle.close(),"cannot close temporary P1 output").pipe(Effect.ignore,Effect.andThen(attempt(()=>unlink(temporary),"cannot clean P1 output").pipe(Effect.ignore)))
 )
})
