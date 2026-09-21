/** Post-run diagnostic audit. Never edits sealed run outputs or evaluation criteria. */
import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { split, modes, projectedInput, label, digest } from './domain.mts';
const root=process.argv[2],out=process.argv[3];if(!root||!out)throw new Error('Usage: audit.mts PRIVATE_OUTPUT_ROOT NEW_PUBLIC_AUDIT');
const read=async(p:string)=>JSON.parse(await readFile(join(root,p),'utf8'));
const rows=(await readFile(join(root,'predictions.jsonl'),'utf8')).trim().split('\n').map(s=>JSON.parse(s));
const same=(a:unknown,b:unknown)=>JSON.stringify(a)===JSON.stringify(b);
const families:any[]=[],learningCalls:any[]=[];
for(let f=0;f<4;f++){
 const t=split(f),p=`trials/${t.task.id}`,states:any={};
 for(const arm of ['frozen','learned','evidence_only','removed','restored'])states[arm]=await read(`${p}/state-${arm}-before.json`);
 const calls=(await readFile(join(root,p,'http/train-learned/calls.jsonl'),'utf8')).trim().split('\n').map(s=>JSON.parse(s));
 if(calls.length!==2)throw new Error('Unexpected learning call count');
 for(const c of calls){
  const path=`${p}/http/train-learned/${c.requestSha256}`,raw=await readFile(join(root,path+'.request.json'),'utf8'),response=await readFile(join(root,path+'.response.json'),'utf8');
  if(digest(raw)!==c.requestSha256||digest(response)!==c.responseSha256||c.status!==200)throw new Error('Learning transport integrity');
  const req=JSON.parse(raw),contract=JSON.parse(req.messages[1].content);
  const event=JSON.parse(contract.frame.event);
  if(!same(event.cases.map((x:any)=>x.id),t.task.train))throw new Error('Non-training input');
  if(contract.outcome){const o=JSON.parse(contract.outcome.observed);if(!same(o.cases.map((x:any)=>x.id),t.task.train)||o.cases.some((x:any)=>x.observed!==label(f,x.id)))throw new Error('Feedback split/label drift');}
  learningCalls.push({...c,family:f,contract:contract.contract,training_split_only:true});
 }
 const learned=await read(`${p}/train-learned.json`);
 const semanticFields=['semanticText','disposition','uncertainty','exceptionRefs'];
 families.push({family:f,name:t.task.id,committed:learned.committedDisposition,
  training_score:learned.trainingScore,
  changed_semantic_fields:semanticFields.filter(k=>!same(states.frozen.semantic[k],states.learned.semantic[k])),
  learned_equals_evidence_only_visible_input:same(projectedInput(states.learned,t.test[0]),projectedInput(states.evidence_only,t.test[0])),
  request_repeats:modes.flatMap(mode=>[['frozen','removed'],['learned','restored'],['learned','evidence_only']].map(([a,b])=>{
   const left=rows.filter(r=>r.family===f&&r.arm===a&&r.mode===mode);
   const pairs=left.map(r=>[r,rows.find(s=>s.family===f&&s.arm===b&&s.mode===mode&&s.case_id===r.case_id)]);
   return {mode,arms:[a,b],n:pairs.length,identical_requests:pairs.filter(([r,s])=>r.request_sha256===s.request_sha256).length,
    prediction_object_changes:pairs.filter(([r,s])=>!same(r.prediction,s.prediction)).length,
    validity_changes:pairs.filter(([r,s])=>r.valid!==s.valid).length,
    paired_valid_bit_changes:pairs.filter(([r,s])=>r.valid&&s.valid&&r.prediction.bit!==s.prediction.bit).length,
    test_paired_valid_bit_changes:pairs.filter(([r,s])=>r.partition==='test'&&r.valid&&s.valid&&r.prediction.bit!==s.prediction.bit).length};
  }))});
}
const modeTotals=modes.map(mode=>{const rs=rows.filter(r=>r.mode===mode);return {mode,n:rs.length,valid:rs.filter(r=>r.valid).length,
 mean_latency_ms:rs.reduce((s,r)=>s+r.latency_ms,0)/rs.length,prompt_tokens:rs.reduce((s,r)=>s+(r.usage?.prompt_tokens??0),0),completion_tokens:rs.reduce((s,r)=>s+(r.usage?.completion_tokens??0),0),
 candidate_mass:mode==='direct'?{min:Math.min(...rs.map(r=>r.prediction.candidateMass)),mean:rs.reduce((s,r)=>s+r.prediction.candidateMass,0)/rs.length}:null};});
const report={schema_version:'hswm-jevp-postrun-diagnostic-audit/v1',date:'2026-09-21',analysis_status:'POST_RUN_DESCRIPTIVE_NOT_NEW_SUCCESS_CRITERION',families,learningCalls,modeTotals,
 total_http_calls:rows.length+learningCalls.length,successful_http:rows.filter(r=>r.status===200).length+learningCalls.filter(r=>r.status===200).length,
 total_prompt_tokens:[...rows,...learningCalls].reduce((s,r)=>s+(r.usage?.prompt_tokens??0),0),total_completion_tokens:[...rows,...learningCalls].reduce((s,r)=>s+(r.usage?.completion_tokens??0),0),
 material_finding:'All four admitted revisions preserve the four visible semantic fields; learned/evidence-only inputs are identical. Semantic revision mediation is absent, so numerical differences between those arms cannot support learned-meaning efficacy.',
 interpretation:'Repeated byte-identical requests can have differing probabilities or bits despite seed 0 and temperature 0. No exact behavior-restoration or numerical determinism claim.',cr_fcl_promotion:false};
if(families.some(f=>f.changed_semantic_fields.length||!f.learned_equals_evidence_only_visible_input))throw new Error('Update diagnostic interpretation: no-op assertion false');
await writeFile(out,JSON.stringify(report,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify({out,modeTotals,total_http_calls:report.total_http_calls,total_prompt_tokens:report.total_prompt_tokens,total_completion_tokens:report.total_completion_tokens,families:families.map(f=>({family:f.family,changed:f.changed_semantic_fields}))}));
