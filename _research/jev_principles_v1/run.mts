import { createRequire } from 'node:module';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { mkdir, readFile, writeFile, appendFile } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { join, resolve } from 'node:path';
import { protocol, arms, modes, split, label, digest, projectedInput, system } from './domain.mts';
import { copyTree } from './support/io.mts';
const base = resolve(fileURLToPath(new URL('../../', import.meta.url)));
const dist = process.env.HSWM_RESEARCH_RUNTIME_DIST ?? join(base, 'src/hswm/effect-runtime/dist');
const { Either } = createRequire(join(dist, 'index.js'))('effect');
const decision = await import(pathToFileURL(join(dist, 'semantic-decision-domain.js')).href);
const out = process.env.HSWM_OUTPUT_ROOT;
if (!out || process.env.HSWM_EXECUTION_TIER !== 'dgx-nvme') throw new Error('Use DGX hswm-run');
const save = async (p: string, v: unknown) => writeFile(p, JSON.stringify(v, null, 2)+'\n', {flag:'wx'});
const child = (script: string, args: string[]) => new Promise<void>((ok, fail) => {
  const p = spawn(process.execPath, [join(base, script), ...args], {env:process.env,stdio:['ignore','pipe','pipe']});
  let text=''; p.stdout.on('data',b=>text+=b); p.stderr.on('data',b=>text+=b);
  const timer=setTimeout(()=>p.kill('SIGTERM'),300000);
  p.on('error',e=>{clearTimeout(timer);fail(e)});p.on('exit',code=>{clearTimeout(timer);code===0?ok():fail(new Error(text.slice(-4000)))});
});
await mkdir(out,{recursive:true}); await mkdir(join(out,'http'),{recursive:true});
await save(join(out,'protocol.json'),protocol);
const started=Date.now();const results:any[]=[];let callCount=0;
const request = async (mode:string,input:any,meta:any) => {
  if(++callCount>protocol.execution_cap.model_calls || Date.now()-started>protocol.execution_cap.wall_seconds*1000) throw new Error('Execution cap reached');
  const common={model:protocol.model,temperature:0,seed:0,chat_template_kwargs:{enable_thinking:false},
    messages:[{role:'system',content:system},{role:'user',content:JSON.stringify(input)+(mode==='direct'?'\nReturn only the bit: 0 or 1.':'\nReturn JSON with prediction (0 or 1) and p1 (probability output is 1). Choose 1 iff p1 > 0.5; ties choose 0.')}]};
  const body=mode==='direct'?{...common,max_tokens:1,allowed_token_ids:[15,16],logprobs:true,top_logprobs:20}:{...common,max_tokens:96,response_format:{type:'json_schema',json_schema:{name:'binary',strict:true,schema:{type:'object',properties:{prediction:{type:'integer',enum:[0,1]},p1:{type:'number',minimum:0,maximum:1}},required:['prediction','p1'],additionalProperties:false}}}};
  const bytes=JSON.stringify(body),key=String(callCount).padStart(4,'0'),ts=performance.now();
  await writeFile(join(out,'http',key+'.request.json'),bytes,{flag:'wx'});
  let result:any;
  try{
    const response=await fetch(`http://127.0.0.1:${protocol.port}/v1/chat/completions`,{method:'POST',headers:{'content-type':'application/json'},body:bytes,signal:AbortSignal.timeout(protocol.execution_cap.request_seconds*1000)});
    const raw=await response.text();await writeFile(join(out,'http',key+'.response.json'),raw,{flag:'wx'});
    const data=JSON.parse(raw),choice=data.choices?.[0];
    const parsed= mode==='direct'?decision.binaryLogprobReadout(choice?.logprobs?.content?.[0]?.top_logprobs??[]):decision.generatedProbabilityReadout(choice?.message?.content??'');
    result={...meta,mode,request_id:key,status:response.status,latency_ms:performance.now()-ts,usage:data.usage??null,model:data.model,fingerprint:data.system_fingerprint,finish_reason:choice?.finish_reason,
      request_sha256:digest(bytes),response_sha256:digest(raw),valid:response.ok&&Either.isRight(parsed),...(Either.isRight(parsed)?{prediction:parsed.right}:{refusal:parsed.left})};
  }catch(e){result={...meta,mode,request_id:key,valid:false,error:String(e),latency_ms:performance.now()-ts};}
  results.push(result);await appendFile(join(out,'predictions.jsonl'),JSON.stringify(result)+'\n');
};
for(let family=0;family<4;family++){
 const t=split(family),root=join(out,'trials',t.task.id);await mkdir(root,{recursive:true});
 const config=join(root,'config.json');await save(config,{family,seed:0,root,model:{id:protocol.model,port:protocol.port}});
 try{
  await child('_research/jev_principles_v1/support/run.mts',['worker','train',config,'learned']);
  for(const [src,dst] of [['learned','restored'],['learned','evidence_only'],['frozen','removed']]) await copyTree(join(root,src),join(root,dst));
  await child('_research/jev_principles_v1/support/run.mts',['worker','control',config,'evidence_only']);
  await child('_research/jev_principles_v1/store.mts',['oracle',config,'oracle',join(root,'state-oracle-before.json')]);
  for(let ai=0;ai<arms.length;ai++){
   const arm=arms[ai],path=join(root,`state-${arm}-before.json`);
   if(arm!=='oracle')await child('_research/jev_principles_v1/store.mts',['read',config,arm,path]);
   const state=JSON.parse(await readFile(path,'utf8'));
   const order=[...t.calibration,...t.test];
   for(let i=0;i<order.length;i++){
    const id=order[i],modeOrder=(i+ai+family)%2?modes:[...modes].reverse();
    for(const mode of modeOrder)await request(mode,projectedInput(state,id),{family,arm,case_id:id,partition:t.calibration.includes(id)?'calibration':'test',label:label(family,id),canonical_sha256:state.canonicalSha256});
   }
   const after=join(root,`state-${arm}-after.json`);await child('_research/jev_principles_v1/store.mts',['read',config,arm,after]);
   const a=JSON.parse(await readFile(after,'utf8'));if(a.canonicalSha256!==state.canonicalSha256)throw new Error('Prediction changed canonical state');
   console.log(JSON.stringify({family,arm,complete_calls:callCount,valid:results.filter(r=>r.family===family&&r.arm===arm&&r.valid).length}));
  }
 }catch(e){await save(join(root,'failure.json'),{error:String(e)});console.log(JSON.stringify({family,error:String(e)}));}
}
await save(join(out,'completion.json'),{started:new Date(started).toISOString(),finished:new Date().toISOString(),callCount,planned:960,valid:results.filter(r=>r.valid).length,protocol_sha256:digest(JSON.stringify(protocol,null,2)+'\n')});
if(callCount!==960)process.exitCode=1;
