"""Frozen 32-case C-thinking-1024 follow-up; development-only, no retries."""
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from inspect_ai import Task, eval, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.scorer import Score, Target, scorer
from inspect_ai.solver import Generate, TaskState, solver
from live_eval import Execution, LiveExample, evaluate_relation
from oracle_single_diagnostic import build, digest, _json_bytes
ARM='C_THINK_1024'; GEN={'temperature':.6,'top_p':.95,'top_k':20,'min_p':0,'thinking':True}
def write_new(p:Path,v:Any):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf8') as f: json.dump(v,f,indent=2,sort_keys=True);f.write('\n')
def plan(fixture:Path):
 b=build(fixture); cases=[{**c,'family':f['family']} for f in b['families'] for c in f['selected']]
 pins={n:digest(Path(__file__).with_name(n).read_bytes()) for n in ('thinking_budget_followup.py','live_eval.py','hswm_bridge.mts','oracle_single_diagnostic.py')}
 return {'schema':'hswm-thinking-budget-followup/v1','cohort':'DEVELOPMENT_EXPOSED','evidence_kind':'FROZEN_THINKING_CAP_FOLLOWUP_NOT_EFFICACY','fixture_plan_sha256':digest(_json_bytes(b)),'source_sha256':b['families'][0]['source_sha256'],'runner_source_sha256':pins,'cases':cases,'oracle_relation_by_family':{str(f['family']):f['oracle_text'] for f in b['families']},'generation':GEN,'max_tokens':1024,'timeout_seconds':60,'seed':0,'budget':32,'screening':{'correctAtLeast':30,'eachFamilyCorrectAtLeast':7,'allOutputsValid':True},'noHoldoutClaim':True,'noEfficacyOrPopulationClaim':True}
def execution(v,url,model): return Execution(url,model,1024,60,0)
@solver
def solver(relations,v,url,model,bridge_command=None):
 async def solve(state:TaskState,generate:Generate):
  c=dict(state.metadata['case']); kw={'renderer':'legacy','generation':GEN}
  if bridge_command is not None: kw['bridge_command']=bridge_command
  r=evaluate_relation(relations[str(c['family'])],LiveExample(c['id'],'train',c['input'],c['target']),execution(v,url,model),**kw)
  if r.get('valid') and (not isinstance(r.get('reasoning'),str) or not r['reasoning'].strip()): r={**r,'valid':False,'answer':None,'error_kind':'MISSING_REASONING_CHANNEL'}
  state.output.completion=r['answer'] if r.get('valid') else '\0INVALID';state.output.metadata={'thinking_followup':r};return state
 return solve
@scorer(metrics=[])
def score():
 async def s(state:TaskState,target:Target):
  r=(state.output.metadata or {}).get('thinking_followup',{});return Score(value=bool(r.get('valid') and r.get('answer')==target.text))
 return s
@task
def followup_task(v,url,model,bridge_command=None):
 ds=MemoryDataset([Sample(input=json.dumps(c['input'],sort_keys=True),target=c['target'],id=c['id'],metadata={'case':c}) for c in v['cases']])
 return Task(dataset=ds,solver=solver(v['oracle_relation_by_family'],v,url,model,bridge_command),scorer=score(),name='hswm_thinking_1024_followup')
def rows(log,v):
 if getattr(log,'status','success')!='success' or len(log.samples)!=32: raise RuntimeError('expected 32 frozen samples')
 by={c['id']:c for c in v['cases']}; samples={str(s.id):s for s in log.samples}
 if len(samples)!=32 or set(samples)!=set(by): raise RuntimeError('expected exactly the frozen sample IDs')
 out=[]
 for c in v['cases']:
  s=samples[c['id']];r=(getattr(getattr(s,'output',None),'metadata',{}) or {}).get('thinking_followup')
  if not c or not isinstance(r,dict):raise RuntimeError('missing followup row')
  valid=r.get('valid') is True and r.get('answer') in ('0','1') and isinstance(r.get('reasoning'),str) and bool(r['reasoning'].strip())
  out.append({'id':c['id'],'family':c['family'],'answer':r.get('answer') if valid else None,'valid':valid,'error_kind':None if valid else r.get('error_kind') or 'MISSING_REASONING_CHANNEL','environment_target':c['target'],'environment_correct':valid and r.get('answer')==c['target'],'request_sha256':r.get('request_sha256'),'response_sha256':r.get('response_sha256'),'usage':r.get('usage'),'latency_ms':r.get('latency_ms'),'model_calls':r.get('model_calls'),'reasoning':r.get('reasoning'),'reasoning_field':r.get('reasoning_field'),'finish_reason':r.get('finish_reason')})
 return out
def summary(rows):
 toks=[x['usage']['total_tokens'] for x in rows if isinstance(x['usage'],dict) and isinstance(x['usage'].get('total_tokens'),int)];lat=[x['latency_ms'] for x in rows if isinstance(x['latency_ms'],(int,float)) and not isinstance(x['latency_ms'],bool)];calls=[x['model_calls'] for x in rows if isinstance(x['model_calls'],int) and not isinstance(x['model_calls'],bool)]
 return {'total':32,'valid':sum(x['valid'] for x in rows),'invalid':sum(not x['valid'] for x in rows),'environment_correct':sum(x['environment_correct'] for x in rows),'known_model_calls':sum(calls),'unknown_call_attempts':32-len(calls),'total_tokens':sum(toks),'unknown_token_rows':32-len(toks),'latency_ms':sum(lat),'unknown_latency_rows':32-len(lat),'family_correct':[sum(x['environment_correct'] for x in rows if x['family']==f) for f in range(4)],'rows':rows}
def run(v,out:Path,url,model,bridge_command=None):
 if out.exists():raise ValueError('output directory exists')
 out.mkdir(mode=0o700);ph=digest(_json_bytes(v));write_new(out/'started.json',{'plan_sha256':ph,'started_at':datetime.now(timezone.utc).isoformat(),'planned_attempts':32})
 log=eval([followup_task(v,url,model,bridge_command)],model=None,log_dir=str(out/'inspect'),fail_on_error=True,max_tasks=1,max_samples=1)[0];r=rows(log,v);a=summary(r);sc=v['screening'];passed=a['valid']==32 and a['environment_correct']>=sc['correctAtLeast'] and all(n>=sc['eachFamilyCorrectAtLeast'] for n in a['family_correct']);p=Path(log.location)
 result={'schema':'hswm-thinking-budget-followup/v1','status':'COMPLETE','decision':'CANDIDATE_FOR_FRESH_EVALUATION' if passed else 'REVISE_LOCAL_EXECUTION','plan_sha256':ph,'fixture_plan_sha256':v['fixture_plan_sha256'],'source_sha256':v['source_sha256'],'runner_source_sha256':v['runner_source_sha256'],'started_at':json.loads((out/'started.json').read_text())['started_at'],'finished_at':datetime.now(timezone.utc).isoformat(),'cohort':'DEVELOPMENT_EXPOSED','planned_attempts':32,'attempted_calls':32,'actual_execution':{'base_url':url,'model':model,'weight_revision':'UNKNOWN','seed':0,'generation':GEN,'max_tokens':1024,'timeout_seconds':60},'arms':{ARM:a},'raw_inspect_log':{'path':str(p),'sha256':digest(p.read_bytes()) if p.is_file() else None},'noHoldoutClaim':True,'noEfficacyOrPopulationClaim':True};write_new(out/'summary.json',result);return result
def main():
 p=argparse.ArgumentParser();p.add_argument('command',choices=('plan','run'));p.add_argument('fixture',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--base-url');p.add_argument('--model');a=p.parse_args();v=plan(a.fixture)
 if a.command=='run':
  if not a.base_url or not a.model:raise ValueError('run requires --base-url --model')
  run(v,a.out,a.base_url,a.model)
 else:write_new(a.out,v)
if __name__=='__main__':main()
