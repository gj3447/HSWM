/** Bounded I/O shell for source-pinned graph-standard tooling. */
import { createHash } from "node:crypto"
import { basename, dirname, isAbsolute, join, relative, resolve, sep } from "node:path"
import { tmpdir } from "node:os"
import { Effect, Either } from "effect"
import { BoundedSubprocess } from "./effect-bounded-subprocess.js"
import { PosixFileSystem, type PosixFileSystemShape } from "./effect-posix-filesystem.js"
import { decodeNativeTaskJson, renderNativeTaskJson, taskJsonRecord, type TaskJson } from "./native-task-json-domain.js"
import { NativeGraphStandardsError, verifyNativeGraphStandardsLock } from "./native-graph-standards-domain.js"

const failure=(detail:string)=>new NativeGraphStandardsError({detail})
const digest=(value:Uint8Array)=>createHash("sha256").update(value).digest("hex")
const decode=(value:Uint8Array)=>new TextDecoder("utf-8",{fatal:true}).decode(value)
const resolveBounded=(root:string,path:string):Either.Either<string,NativeGraphStandardsError>=>{
 if(isAbsolute(path)||path.split(/[\\/]/).includes(".."))return Either.left(failure("repository-relative path escapes checkout"))
 const target=resolve(root,path),inside=relative(root,target)
 return inside===""||inside.startsWith(`..${sep}`)||isAbsolute(inside)?Either.left(failure("repository-relative path escapes checkout")):Either.right(target)
}
const read=(fs:PosixFileSystemShape,root:string,path:string,label:string):Effect.Effect<Uint8Array,NativeGraphStandardsError>=>{
 const target=resolveBounded(root,path)
 return Either.isLeft(target)?Effect.fail(target.left):fs.readRegularBounded(target.right,{maximumBytes:64*1024*1024,minimumBytes:1,operation:label}).pipe(Effect.map(x=>x.bytes),Effect.mapError(e=>failure(`${label} is unavailable: ${e.detail}`)))
}
const execute=(argv:readonly string[],cwd:string,environment:Readonly<Record<string,string>>={GIT_ASKPASS:"/bin/false",GIT_CONFIG_GLOBAL:"/dev/null",GIT_CONFIG_NOSYSTEM:"1",GIT_TERMINAL_PROMPT:"0",LANG:"C.UTF-8",LC_ALL:"C.UTF-8",PATH:globalThis.process.env["PATH"]??""},timeoutMs=30_000):Effect.Effect<Uint8Array,NativeGraphStandardsError,BoundedSubprocess>=>Effect.gen(function*(){
 const subprocess=yield* BoundedSubprocess
 const observed=yield* subprocess.observe({argv,cwd,environment,timeoutMs,maximumOutputBytes:8*1024*1024,killProcessGroup:true}).pipe(Effect.mapError(e=>failure(e.detail)))
 if(observed.timedOut)return yield* Effect.fail(failure("subprocess timed out"))
 if(observed.outputTruncated)return yield* Effect.fail(failure("subprocess output exceeded bounds"))
 if(observed.launchError!==null)return yield* Effect.fail(failure("subprocess launch failed"))
 if(observed.signal!==null)return yield* Effect.fail(failure(`subprocess terminated by ${observed.signal}`))
 if(observed.exitCode!==0)return yield* Effect.fail(failure(`subprocess failed${observed.exitCode===null?"":` with exit ${observed.exitCode}`}`))
 return observed.stdout
})
const values=(value:TaskJson,keys:ReadonlyArray<string>,out:string[]=[]):readonly string[]=>{if(Array.isArray(value))for(const item of value)values(item,keys,out);else if(taskJsonRecord(value))for(const [key,item] of Object.entries(value)){if(keys.includes(key)&&typeof item==="string")out.push(item);values(item,keys,out)}return out}
const fileKeys=Object.freeze(["package_manifest","package_lock","project_manifest","uv_lock","lockfile","runner","path"])
export const verifyNativeGraphStandardsCheckout=(root:string,manifestPath:string):Effect.Effect<TaskJson,NativeGraphStandardsError,PosixFileSystem>=>Effect.gen(function*(){
 const fs=yield* PosixFileSystem,manifestRelative=isAbsolute(manifestPath)?relative(root,manifestPath):manifestPath,bytes=yield* read(fs,root,manifestRelative,"graph standards lock"),parsed=decodeNativeTaskJson(bytes)
 if(Either.isLeft(parsed))return yield* Effect.fail(failure("cannot read graph standards lock"))
 const entries=yield* Effect.forEach([...new Set(values(parsed.right,fileKeys))].sort(),path=>read(fs,root,path,`graph standards inventory ${path}`).pipe(Effect.map(bytes=>[path,bytes] as const)))
 const checked=verifyNativeGraphStandardsLock(parsed.right,Object.freeze(Object.fromEntries(entries)))
 if(Either.isLeft(checked))return yield* Effect.fail(checked.left)
 return {schema_version:"hswm-graph-standards-acceptance/v1",status:"PASS",suite_sources:Object.keys(checked.right.sources).length,runnable_profiles:Object.values(checked.right.profiles).filter(x=>typeof x["status"]==="string"&&x["status"].startsWith("RUNNABLE_")).length}
})
export const verifyNativeGraphStandardsSourceCheckout=(source:TaskJson,checkout:string):Effect.Effect<TaskJson,NativeGraphStandardsError,PosixFileSystem|BoundedSubprocess>=>Effect.gen(function*(){
 if(!taskJsonRecord(source)||typeof source["commit"]!=="string"||typeof source["selected_path"]!=="string")return yield* Effect.fail(failure("invalid pinned suite source"))
 const fs=yield* PosixFileSystem,root=yield* fs.realpath(checkout,"source checkout").pipe(Effect.mapError(()=>failure(`not a git checkout: ${checkout}`)))
 const git=yield* fs.identity(join(root,".git"),"source checkout git metadata").pipe(Effect.either);if(Either.isLeft(git))return yield* Effect.fail(failure(`not a git checkout: ${root}`))
 const commit=decode(yield* execute(["git","-C",root,"rev-parse","HEAD"],root)).trim();if(commit!==source["commit"])return yield* Effect.fail(failure("source checkout commit drift"))
 const selected=source["selected_path"],tree=decode(yield* execute(["git","-C",root,"rev-parse",`HEAD:${selected}`],root)).trim();if(tree!==source["git_tree_sha1"])return yield* Effect.fail(failure("source checkout selected tree drift"))
 const archive=yield* execute(["git","-C",root,"archive","--format=tar",commit,"--",selected],root);if(digest(archive)!==source["git_archive_sha256"])return yield* Effect.fail(failure("source checkout archive digest drift"))
 const dirty=decode(yield* execute(["git","-C",root,"status","--porcelain=v1","--untracked-files=all","--",selected],root));if(dirty!=="")return yield* Effect.fail(failure("source checkout selected tree is dirty"))
 const found:Record<string,string>={};for(const name of ["manifest","license"]){const path=source[`${name}_path`];if(typeof path!=="string")return yield* Effect.fail(failure(`source ${name} path drift`));const bytes=yield* read(fs,root,path,`source ${name}`);if(digest(bytes)!==source[`${name}_sha256`])return yield* Effect.fail(failure(`source ${name} digest drift`));found[name]=digest(bytes)}
 return {archive_sha256:digest(archive),commit,license_sha256:found["license"]!,manifest_sha256:found["manifest"]!,tree_sha1:tree}
})
export const fetchNativeGraphStandardSource=(source:TaskJson,destination:string,repositoryRoot:string):Effect.Effect<TaskJson,NativeGraphStandardsError,PosixFileSystem|BoundedSubprocess>=>Effect.gen(function*(){
 if(!taskJsonRecord(source)||typeof source["repository"]!=="string"||!/^https:\/\/[^@/]+\/.+\.git$/.test(source["repository"])||typeof source["commit"]!=="string"||!/^[0-9a-f]{40}$/.test(source["commit"]))return yield* Effect.fail(failure("invalid pinned suite source"))
 const fs=yield* PosixFileSystem,exists=yield* fs.identity(destination,"graph standards destination").pipe(Effect.either);if(Either.isRight(exists))return yield* Effect.fail(failure("materialization destination must not exist"));if(exists.left.code!=="ENOENT")return yield* Effect.fail(failure(exists.left.detail))
 const parent=yield* fs.realpath(dirname(destination),"graph standards destination parent").pipe(Effect.mapError(e=>failure(e.detail))),root=yield* fs.realpath(repositoryRoot,"graph standards repository root").pipe(Effect.mapError(e=>failure(e.detail)))
 if(parent===root||parent.startsWith(`${root}${sep}`))return yield* Effect.fail(failure("official suites must be materialized outside the repository"))
 yield* execute(["git","init","--quiet",destination],parent);yield* execute(["git","-C",destination,"remote","add","origin",source["repository"]],destination);yield* execute(["git","-C",destination,"fetch","--quiet","--depth=1","origin",source["commit"]],destination);yield* execute(["git","-C",destination,"checkout","--quiet","--detach","FETCH_HEAD"],destination)
 return yield* verifyNativeGraphStandardsSourceCheckout(source,destination)
})
const runtimeEnvironment=(overrides:Readonly<Record<string,string>>):Readonly<Record<string,string>>=>Object.freeze({LANG:"C.UTF-8",LC_ALL:"C.UTF-8",PATH:globalThis.process.env["PATH"]??"",TMPDIR:globalThis.process.env["TMPDIR"]??"/tmp",...overrides})
const version=(argv:readonly string[],cwd:string,expected:string,label:string):Effect.Effect<void,NativeGraphStandardsError,BoundedSubprocess>=>execute(argv,cwd).pipe(Effect.flatMap(bytes=>decode(bytes).trim()===expected?Effect.void:Effect.fail(failure(`${label} version drift`))))
const adapterReceipt=(adapter:Record<string,TaskJson>):TaskJson=>adapter["ecosystem"]==="npm"?{authority_class:adapter["authority_class"]!,ecosystem:"npm",package:adapter["package"]!,source_commit:adapter["source_commit"]!,version:adapter["version"]!,npm_integrity:adapter["npm_integrity"]!}:{authority_class:adapter["authority_class"]!,ecosystem:"pypi",package:adapter["package"]!,source_commit:adapter["source_commit"]!,version:adapter["version"]!,sdist_sha256:adapter["sdist_sha256"]!,wheel_sha256:adapter["wheel_sha256"]!}
export const qualifyNativeGraphStandardsProfile=(lock:TaskJson,profileId:string,sourceRoot:string,repositoryRoot:string,output?:string):Effect.Effect<TaskJson,NativeGraphStandardsError,PosixFileSystem|BoundedSubprocess>=>Effect.gen(function*(){
 const fs=yield* PosixFileSystem
 if(!taskJsonRecord(lock))return yield* Effect.fail(failure("graph standards lock must be an object"))
 const entries=yield* Effect.forEach([...new Set(values(lock,fileKeys))].sort(),path=>read(fs,repositoryRoot,path,`graph standards inventory ${path}`).pipe(Effect.map(bytes=>[path,bytes] as const)))
 const checked=verifyNativeGraphStandardsLock(lock,Object.freeze(Object.fromEntries(entries)),false);if(Either.isLeft(checked))return yield* Effect.fail(checked.left)
 const profile=checked.right.profiles[profileId];if(profile===undefined)return yield* Effect.fail(failure(`unknown qualification profile: ${profileId}`))
 if(profile["status"]!=="RUNNABLE_REQUIRES_PINNED_SUITE"&&profile["status"]!=="RUNNABLE_NON_PROMOTING_DRAFT_DIAGNOSTIC")return yield* Effect.fail(failure(`profile is not runnable: ${profileId}`))
 const source=checked.right.sources[String(profile["suite_source_id"])],adapter=checked.right.adapters[String(profile["adapter_id"])];if(source===undefined||adapter===undefined)return yield* Effect.fail(failure("qualification profile lock linkage drift"))
 const observed=yield* verifyNativeGraphStandardsSourceCheckout(source,sourceRoot)
 const runnerPath=String(profile["runner"]),runner=yield* read(fs,repositoryRoot,runnerPath,`profile ${profileId} runner`);if(digest(runner)!==profile["runner_sha256"])return yield* Effect.fail(failure(`profile ${profileId} runner digest drift`))
 const scope=profile["runner_suite_scope"]==="checkout_root"?sourceRoot:join(sourceRoot,String(source["selected_path"])),suiteArgument=String(profile["runner_suite_argument"]??"--suite-root"),runtime=String(profile["runner_runtime"]??"node")
 const rootRecord=lock
 const runtimeCandidate=rootRecord["runtime_lock"],pythonCandidate=rootRecord["python_runtime_lock"]
 const runtimeLock=runtimeCandidate!==undefined&&taskJsonRecord(runtimeCandidate)?runtimeCandidate:undefined,pythonLock=pythonCandidate!==undefined&&taskJsonRecord(pythonCandidate)?pythonCandidate:undefined
 let stdout:Uint8Array;let receiptRuntime:TaskJson
 if(runtime==="node"){
   if(runtimeLock===undefined)return yield* Effect.fail(failure("runtime_lock must be an object"))
   yield* version(["node","--version"],repositoryRoot,`v${runtimeLock["node"]}`,"Node.js");yield* version(["npm","--version"],repositoryRoot,String(runtimeLock["npm"]),"npm")
   const manifest=yield* read(fs,repositoryRoot,String(runtimeLock["package_manifest"]),"runtime package manifest"),packageLock=yield* read(fs,repositoryRoot,String(runtimeLock["package_lock"]),"runtime package lock")
   stdout=yield* Effect.acquireUseRelease(
     execute(["mktemp","-d","-t","hswm-graph-standard-npm-XXXXXX"],repositoryRoot).pipe(Effect.flatMap(bytes=>{const temporary=decode(bytes).trim(),temporaryParent=resolve(tmpdir());return isAbsolute(temporary)&&dirname(temporary)===temporaryParent&&basename(temporary).startsWith("hswm-graph-standard-npm-")?Effect.succeed(temporary):Effect.fail(failure(`temporary runtime path drift: ${temporary}`))})),
     temporary=>Effect.gen(function*(){yield* fs.writeExclusive(join(temporary,"package.json"),manifest,{mode:0o644,sync:true,operation:"temporary package manifest"}).pipe(Effect.mapError(e=>failure(e.detail)));yield* fs.writeExclusive(join(temporary,"package-lock.json"),packageLock,{mode:0o644,sync:true,operation:"temporary package lock"}).pipe(Effect.mapError(e=>failure(e.detail)));const env=runtimeEnvironment({HOME:join(temporary,"home"),npm_config_audit:"false",npm_config_fund:"false",npm_config_ignore_scripts:"true",npm_config_registry:"https://registry.npmjs.org/"});yield* execute(["npm","ci","--ignore-scripts","--no-audit","--no-fund"],temporary,env,180_000);return yield* execute(["node",resolve(repositoryRoot,runnerPath),"--module-root",temporary,"--profile",profileId,suiteArgument,scope],repositoryRoot,env,180_000)}),
     temporary=>execute(["rm","-rf","--",temporary],repositoryRoot).pipe(Effect.ignore)
   )
   receiptRuntime={installation:"CLEAN_TEMPORARY_NPM_CI_IGNORE_SCRIPTS",kind:"node-npm",node:`v${runtimeLock["node"]}`,npm:runtimeLock["npm"]!,package_lock_sha256:runtimeLock["package_lock_sha256"]!}
 }else if(runtime==="python"){
   if(pythonLock===undefined)return yield* Effect.fail(failure("python_runtime_lock must be an object"))
   const uvVersion=decode(yield* execute(["uv","--version"],repositoryRoot)).trim().split(/\s+/)[1];if(uvVersion!==pythonLock["uv"])return yield* Effect.fail(failure("uv version drift"))
   const project=resolve(repositoryRoot,String(pythonLock["project_manifest"]));stdout=yield* execute(["uv","run","--project",dirname(project),"--isolated","--locked","--no-python-downloads","--python",String(pythonLock["python"]),"--extra",String(pythonLock["extra"]),"python","-I",resolve(repositoryRoot,runnerPath),"--profile",profileId,suiteArgument,scope],repositoryRoot,runtimeEnvironment({UV_DEFAULT_INDEX:"https://pypi.org/simple",UV_NO_CONFIG:"1",UV_NO_PYTHON_DOWNLOADS:"1",UV_PROJECT:dirname(project)}),240_000)
   receiptRuntime={extra:pythonLock["extra"]!,installation:"CLEAN_ISOLATED_UV_RUN_LOCKED",kind:"python-uv",project_manifest_sha256:pythonLock["project_manifest_sha256"]!,python:pythonLock["python"]!,uv:pythonLock["uv"]!,uv_lock_sha256:pythonLock["uv_lock_sha256"]!}
 }else return yield* Effect.fail(failure("unsupported qualification runner runtime"))
 const parsed=decodeNativeTaskJson(stdout);if(Either.isLeft(parsed)||!taskJsonRecord(parsed.right))return yield* Effect.fail(failure("qualification runner returned non-JSON"));const result=parsed.right
 if(result["status"]!=="PASS"||result["profile"]!==profileId)return yield* Effect.fail(failure(`qualification failed for ${profileId}`))
 const manifest=yield* read(fs,sourceRoot,String(profile["qualification_manifest_path"]),"qualification manifest"),manifestSha=digest(manifest)
 if(manifestSha!==profile["qualification_manifest_sha256"]||result["manifest_sha256"]!==manifestSha)return yield* Effect.fail(failure("qualification manifest binding drift"))
 const rawCounts=result["counts"],rawExpected=profile["expected"];const counts=rawCounts!==undefined&&taskJsonRecord(rawCounts)?rawCounts:undefined,expected=rawExpected!==undefined&&taskJsonRecord(rawExpected)?rawExpected:undefined;if(counts===undefined||expected===undefined||Object.entries(expected).some(([key,value])=>counts[key]!==value)||counts["failed"]!==0||counts["passed"]!==counts[String(profile["pass_count_field"]??"total")])return yield* Effect.fail(failure("qualification count or pass denominator drift"))
 const rawAdapter=result["adapter"],observedAdapter=rawAdapter!==undefined&&taskJsonRecord(rawAdapter)?rawAdapter:undefined;if(observedAdapter===undefined||observedAdapter["package"]!==adapter["package"]||observedAdapter["version"]!==adapter["version"])return yield* Effect.fail(failure("qualification adapter drift"))
 const rawRuntime=result["runtime"],runnerRuntime=rawRuntime!==undefined&&taskJsonRecord(rawRuntime)?rawRuntime:undefined;if(runtime==="python"&&(runnerRuntime===undefined||runnerRuntime["implementation"]!=="CPython"||runnerRuntime["python"]!==(receiptRuntime as Record<string,TaskJson>)["python"]))return yield* Effect.fail(failure("qualification Python runtime drift"))
 const observedSource=taskJsonRecord(observed)?observed:undefined;if(observedSource===undefined)return yield* Effect.fail(failure("source checkout receipt drift"))
 const unsigned:Record<string,TaskJson>={adapter:adapterReceipt(adapter),claim_ceiling:profile["claim_ceiling"]!,lane:profile["lane"]!,nonclaims:["NOT_HSWM_COGNITION","NOT_CANONICAL_ADMISSION_OR_PERMIT","NOT_OUTCOME_TRUTH_OR_CAUSAL_CREDIT","NOT_CONTINUOUS_LEARNING_OR_LLM_EFFICACY","TEST_SUITE_PASS_DOES_NOT_IMPLY_UNIVERSAL_SPECIFICATION_CONFORMANCE"],profile_id:profileId,result:{counts,status:"PASS"},runner:{path:runnerPath,sha256:profile["runner_sha256"]!},runtime:receiptRuntime,schema_version:"hswm-graph-standard-qualification-receipt/v1",source:{archive_sha256:observedSource["archive_sha256"]!,commit:observedSource["commit"]!,license_sha256:observedSource["license_sha256"]!,qualification_manifest_path:profile["qualification_manifest_path"]!,qualification_manifest_sha256:manifestSha,repository:source["repository"]!,selected_path:source["selected_path"]!,source_manifest_sha256:observedSource["manifest_sha256"]!,tree_sha1:observedSource["tree_sha1"]!},standards:profile["standard_ids"]!}
 const receipt:TaskJson={...unsigned,receipt_sha256:createHash("sha256").update(renderNativeTaskJson(unsigned)).digest("hex")}
 if(output!==undefined){const payload=new TextEncoder().encode(`${renderNativeTaskJson(receipt,"pretty")}\\n`),current=yield* fs.identity(output,"qualification receipt").pipe(Effect.either);if(Either.isRight(current)){const bytes=yield* fs.readRegularBounded(output,{maximumBytes:8*1024*1024,minimumBytes:1,operation:"qualification receipt"}).pipe(Effect.map(x=>x.bytes),Effect.mapError(e=>failure(e.detail)));if(decode(bytes)!==decode(payload))return yield* Effect.fail(failure(`refusing to overwrite different receipt: ${output}`))}else if(current.left.code==="ENOENT")yield* fs.writeExclusive(output,payload,{mode:0o644,sync:true,operation:"qualification receipt"}).pipe(Effect.mapError(e=>failure(e.detail)));else return yield* Effect.fail(failure(current.left.detail))}
 return receipt
})
