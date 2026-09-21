import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { createRequire } from 'node:module';
import { protocol, arms, modes, split, label, projectedInput, digest } from './domain.mts';
import { binaryLogprobReadout, generatedProbabilityReadout, probabilityMetrics, fitTemperature, temperatureProbability } from '../../src/hswm/effect-runtime/dist/semantic-decision-domain.js';
const { Either } = createRequire(new URL('../../src/hswm/effect-runtime/package.json',import.meta.url))('effect');
const root=process.argv[2],output=process.argv[3];if(!root||!output)throw new Error('Usage: analyze.mts OUTPUT_ROOT PUBLIC_OBSERVATIONS');
const read=(p:string)=>readFile(join(root,p),'utf8').then(JSON.parse);
const rows=(await readFile(join(root,'predictions.jsonl'),'utf8')).trim().split('\n').map(JSON.parse);
const metrics=(rs:any[])=>rs.length?Either.getOrThrow(probabilityMetrics(rs.map(r=>({p1:r.prediction.p1,label:r.label})))):null;
const summaries:any[]=[],comparisons:any[]=[],controls:any[]=[];let audited=0;
const generatedDecisions=new Map<string,number>();
for(const r of rows){
 const t=split(r.family),state=await read(`trials/${t.task.id}/state-${r.arm}-before.json`);
 if(r.label!==label(r.family,r.case_id)||r.partition!==(t.calibration.includes(r.case_id)?'calibration':'test')||(!t.calibration.includes(r.case_id)&&!t.test.includes(r.case_id)))throw new Error('Split or label drift');
 const raw=await readFile(join(root,'http',r.request_id+'.request.json'),'utf8');if(digest(raw)!==r.request_sha256)throw new Error('Request hash drift');
 const request=JSON.parse(raw),content=request.messages[1].content,expected=JSON.stringify(projectedInput(state,r.case_id));
 if(!content.startsWith(expected+'\nReturn '))throw new Error('Input frame mismatch');
 if(state.canonicalSha256!==r.canonical_sha256)throw new Error('Canonical mismatch');
 if(r.response_sha256){const rawResponse=await readFile(join(root,'http',r.request_id+'.response.json'),'utf8');if(digest(rawResponse)!==r.response_sha256)throw new Error('Response drift');const response=JSON.parse(rawResponse),choice=response.choices?.[0];if(r.valid){const reparsed=Either.getOrThrow(r.mode==='direct'?binaryLogprobReadout(choice.logprobs.content[0].top_logprobs):generatedProbabilityReadout(choice.message.content));if(JSON.stringify(reparsed)!==JSON.stringify(r.prediction))throw new Error('Prediction interpretation drift')}if(r.mode==='generated'){try{const v=JSON.parse(choice?.message?.content??'');if(v.prediction===0||v.prediction===1)generatedDecisions.set(r.request_id,v.prediction)}catch{}}}
 audited++;
}
for(const arm of arms)for(const mode of modes){
 const all=rows.filter(r=>r.arm===arm&&r.mode===mode),test=all.filter(r=>r.partition==='test'),valid=test.filter(r=>r.valid),cal=all.filter(r=>r.partition==='calibration'&&r.valid);
 const fit=cal.length?Either.getOrThrow(fitTemperature(cal.map(r=>({p1:r.prediction.p1,label:r.label})))):null;
 const calibrated=fit?valid.map(r=>({...r,prediction:{...r.prediction,p1:Either.getOrThrow(temperatureProbability(r.prediction.p1,fit.temperature))}})):[];
 const sum=(k:string)=>all.reduce((s,r)=>s+(r.usage?.[k]??0),0);
 summaries.push({arm,mode,planned_test:48,attempted_test:test.length,valid_test:valid.length,correct_including_refusals:valid.filter(r=>r.prediction.bit===r.label).length,
  raw:metrics(valid),temperature:fit,calibrated_test:metrics(calibrated),
  decision_only_auxiliary:mode==='generated'?{status:'SECONDARY_DESCRIPTIVE_NOT_PRIMARY_PROTOCOL_REPAIR',n:test.filter(r=>generatedDecisions.has(r.request_id)).length,correct:test.filter(r=>generatedDecisions.get(r.request_id)===r.label).length}:null,
  family_test:[0,1,2,3].map(f=>({family:f,attempted:test.filter(r=>r.family===f).length,valid:valid.filter(r=>r.family===f).length,metrics:metrics(valid.filter(r=>r.family===f))})),
  attempted_calls:all.length,mean_latency_ms:all.reduce((s,r)=>s+r.latency_ms,0)/all.length,prompt_tokens:sum('prompt_tokens'),completion_tokens:sum('completion_tokens'),
  selective_accuracy:[.6,.8,.9].map(threshold=>{const selected=valid.filter(r=>Math.max(r.prediction.p1,1-r.prediction.p1)>=threshold);return {threshold,n:selected.length,correct:selected.filter(r=>r.prediction.bit===r.label).length}}),
  refusal_reasons:Object.fromEntries([...new Set(all.filter(r=>!r.valid).map(r=>r.refusal?.reason??r.error??'HTTP_ERROR'))].map(reason=>[reason,all.filter(r=>(r.refusal?.reason??r.error??'HTTP_ERROR')===reason&&!r.valid).length]))});
}
for(const arm of arms){const test=rows.filter(r=>r.arm===arm&&r.partition==='test');const paired=test.filter(r=>r.mode==='direct'&&r.valid&&test.some(s=>s.mode==='generated'&&s.valid&&s.family===r.family&&s.case_id===r.case_id));const generated=paired.map(r=>test.find(s=>s.mode==='generated'&&s.family===r.family&&s.case_id===r.case_id));comparisons.push({arm,paired_valid:paired.length,direct:metrics(paired),generated:metrics(generated),direct_wins:paired.filter((r,i)=>r.prediction.bit===r.label&&generated[i].prediction.bit!==r.label).length,generated_wins:paired.filter((r,i)=>r.prediction.bit!==r.label&&generated[i].prediction.bit===r.label).length});}
for(let f=0;f<4;f++){
 const t=split(f),states:any={};for(const arm of arms){states[arm]=await read(`trials/${t.task.id}/state-${arm}-before.json`);const after=await read(`trials/${t.task.id}/state-${arm}-after.json`);if(after.canonicalSha256!==states[arm].canonicalSha256)throw new Error('Canonical changed during evaluation')}
 controls.push({family:f,removal_exact:states.frozen.canonicalSha256===states.removed.canonicalSha256,restoration_exact:states.learned.canonicalSha256===states.restored.canonicalSha256,evidence_equal:JSON.stringify(states.learned.priorEvidence)===JSON.stringify(states.evidence_only.priorEvidence),learned_relation_revision:states.learned.relationRevision,
  repeated_predictions:modes.map(mode=>({mode,...Object.fromEntries([['frozen','removed'],['learned','restored']].map(([a,b])=>[a+'_'+b,rows.filter(r=>r.family===f&&r.arm===a&&r.mode===mode).filter(r=>{const s=rows.find(s=>s.family===f&&s.arm===b&&s.mode===mode&&s.case_id===r.case_id);return JSON.stringify(r.prediction)!==JSON.stringify(s?.prediction)}).length]))}))});
}
if(controls.some(c=>!c.removal_exact||!c.restoration_exact||!c.evidence_equal))throw new Error('Control integrity failure');
const completion=await read('completion.json'),gpuText=await readFile(join(root,'gpu.csv'),'utf8');const gpu=gpuText.trim().split('\n').slice(1).map(line=>Number.parseFloat(line.split(',')[1])).filter(Number.isFinite);
const report={schema_version:'hswm-jev-principle-observations/v1',date:'2026-09-21',completion,protocol_sha256:digest(await readFile(join(root,'protocol.json'))),summaries,comparisons,controls,request_audit:audited,unique_queries:new Set(rows.map(r=>[r.family,r.arm,r.mode,r.case_id].join(':'))).size,
 gpu:{samples:gpu.length,mean_utilization_percent:gpu.reduce((s,v)=>s+v,0)/gpu.length,peak_utilization_percent:Math.max(...gpu),boundary:'Device-wide, not job-exclusive energy'},
 uninformative_baseline:{p1:.5,brier:.25,nll:Math.log(2),balanced_test_accuracy:.5},
 limitations:['Four authored binary task families, one partition each; no population generalization or independent-world-outcome claim.','Direct conditions reuse pretrained LM logits; no learned neural head, shared-trunk parallel sampler or RLCD implementation.','Conditional candidate probabilities are not prior full-vocabulary probabilities; generated and direct instructions/output contracts differ.','Temperature fits calibration partition only, cannot change argmax accuracy; 32 cases per fit is small.','Fresh native stores preserve reference authorization and mechanical admission, not full canonical Permit or causal credit.','Generated decision-only accuracy is a secondary diagnostic retaining inconsistent outputs; it does not alter the preregistered refusal rule.'],claim_ceiling:protocol.claim_ceiling};
await writeFile(output,JSON.stringify(report,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify({output,request_audit:audited,summaries:summaries.map(s=>({arm:s.arm,mode:s.mode,correct:s.correct_including_refusals,n:s.attempted_test,valid:s.valid_test,nll:s.raw?.nll,calibrated:s.calibrated_test?.nll,temperature:s.temperature?.temperature,ms:s.mean_latency_ms}))}));
