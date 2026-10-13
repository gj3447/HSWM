"""Development-only 3-arm token-cap/thinking diagnostic (at most 96 calls)."""
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from inspect_ai import Task, eval, task
from inspect_ai.log import read_eval_log
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.scorer import Score, Target, scorer
from inspect_ai.solver import Generate, TaskState, solver
from live_eval import Execution, LiveExample, evaluate_relation
from oracle_single_diagnostic import build, digest, _json_bytes
ARMS=('A_NONTHINK_32','B_NONTHINK_512','C_THINK_512')
GEN={'A_NONTHINK_32':{'temperature':.6,'top_p':.95,'top_k':20,'min_p':0,'thinking':False},'B_NONTHINK_512':{'temperature':.6,'top_p':.95,'top_k':20,'min_p':0,'thinking':False},'C_THINK_512':{'temperature':.6,'top_p':.95,'top_k':20,'min_p':0,'thinking':True}}
def write_new(p:Path,v:Any)->None:
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf8') as f: json.dump(v,f,indent=2,sort_keys=True);f.write('\n')
def execution(base:dict[str,Any], arm:str, url:str, model:str)->Execution:
 return Execution(url,model,32 if arm=='A_NONTHINK_32' else 512,base['timeout_seconds'],base['seed'])
def plan(fixture:Path)->dict[str,Any]:
 b=build(fixture); cases=[{**c,'family':f['family']} for f in b['families'] for c in f['selected']]
 for position, case in enumerate(cases): case['case_position']=position
 sources={name:digest(Path(__file__).with_name(name).read_bytes()) for name in ('budget_comparison.py','live_eval.py','hswm_bridge.mts','oracle_single_diagnostic.py')}
 orders={case['id']:[ARMS[(case['case_position']+i)%3] for i in range(3)] for case in cases}
 return {'schema':'hswm-budget-comparison/v1','cohort':'DEVELOPMENT_EXPOSED','evidence_kind':'PLANNED_TOKEN_MODE_DIAGNOSTIC_NOT_EFFICACY','fixture_root':str(fixture),'fixture_plan_sha256':digest(_json_bytes(b)),'source_sha256':b['families'][0]['source_sha256'],'runner_source_sha256':sources,'cases':cases,'arm_order_by_case':orders,'compatibility_case_id':cases[0]['id'],'stop_rule':'After exactly three compatibility attempts, stop further bridge calls if any arm is invalid or C lacks a nonempty reasoning channel.','oracle_relation_by_family':{str(f['family']):f['oracle_text'] for f in b['families']},'frozen_execution':b['frozen_execution'],'arms':list(ARMS),'generation':GEN,'planned_attempts':96,'screening':{'correctAtLeast':30,'eachFamilyCorrectAtLeast':7,'allOutputsValid':True},'noHoldoutClaim':True,'noEfficacyOrPopulationClaim':True}
def dataset(cases:list[dict[str,Any]])->MemoryDataset:
 return MemoryDataset([Sample(input=json.dumps(c['input'],sort_keys=True),target=c['target'],id=c['id'],metadata={'budget_case':c}) for c in cases])
@solver
def budget_solver(relations:dict[str,str], base:dict[str,Any], url:str, model:str, bridge_command=None, compatibility_id:str|None=None):
 gate={'blocked':False}
 async def solve(state:TaskState,generate:Generate)->TaskState:
  c=dict(state.metadata['budget_case']); order=[ARMS[(c['case_position']+i)%3] for i in range(3)]; rows={}
  if gate['blocked']:
   rows={a:{'valid':False,'answer':None,'error_kind':'NOT_ATTEMPTED_AFTER_COMPATIBILITY_FAILURE','request_sha256':None,'response_sha256':None,'usage':None,'latency_ms':None,'model_calls':None,'reasoning':None,'reasoning_field':None,'finish_reason':None} for a in ARMS}
   state.output.completion='\0INVALID'; state.output.metadata={'hswm_budget_arms':rows,'arm_order':order}; return state
  for arm in order:
   e=execution(base,arm,url,model); x=LiveExample(c['id'],'train',c['input'],c['target'])
   kw={'renderer':'legacy','generation':GEN[arm]}
   if bridge_command is not None: kw['bridge_command']=bridge_command
   result=evaluate_relation(relations[str(c['family'])],x,e,**kw)
   if arm=='C_THINK_512' and result.get('valid') and (not isinstance(result.get('reasoning'),str) or not result['reasoning'].strip()):
    result={**result,'valid':False,'answer':None,'error_kind':'MISSING_REASONING_CHANNEL'}
   rows[arm]=result
  if c['id']==compatibility_id and any(not rows[a].get('valid') for a in ARMS): gate['blocked']=True
  state.output.completion=next((r['answer'] for r in rows.values() if r.get('valid')),'\0INVALID')
  state.output.metadata={'hswm_budget_arms':rows,'arm_order':order}; return state
 return solve
@scorer(metrics=[])
def budget_score():
 async def score(state:TaskState,target:Target)->Score:
  arms=(state.output.metadata or {}).get('hswm_budget_arms',{})
  c=arms.get('C_THINK_512',{}) if isinstance(arms,dict) else {}
  return Score(value=bool(c.get('valid') and c.get('answer')==target.text))
 return score
@task
def budget_task(cases,relations,base,url,model,bridge_command=None):
 return Task(dataset=dataset(cases),solver=budget_solver(relations,base,url,model,bridge_command,cases[0]['id']),scorer=budget_score(),name='hswm_budget_mode_development')
def rows(log:Any,cases:list[dict[str,Any]])->dict[str,list[dict[str,Any]]]:
 by={c['id']:c for c in cases}; out={a:[] for a in ARMS}
 if getattr(log,'status','success') != 'success': raise RuntimeError('Inspect log did not succeed')
 if len(log.samples)!=32 or len({str(s.id) for s in log.samples})!=32: raise RuntimeError('Inspect log must have 32 unique samples')
 for s in log.samples:
  c=by.get(str(s.id)); meta=getattr(getattr(s,'output',None),'metadata',{}) or {}; arms=meta.get('hswm_budget_arms') if isinstance(meta,dict) else None
  if c is None or not isinstance(arms,dict) or set(arms)!=set(ARMS):raise RuntimeError('missing budget arm metadata')
  for a,r in arms.items():
   valid=r.get('valid') is True and (a!='C_THINK_512' or isinstance(r.get('reasoning'),str) and bool(r.get('reasoning').strip()))
   error=r.get('error_kind') if not valid else None
   if not valid and a=='C_THINK_512' and r.get('valid') is True and not error: error='MISSING_REASONING_CHANNEL'
   out[a].append({'id':c['id'],'family':c['family'],'answer':r.get('answer') if valid else None,'valid':valid,'error_kind':error,'environment_target':c['target'],'environment_correct':valid and r.get('answer')==c['target'],'request_sha256':r.get('request_sha256'),'response_sha256':r.get('response_sha256'),'usage':r.get('usage'),'latency_ms':r.get('latency_ms'),'model_calls':r.get('model_calls'),'reasoning':r.get('reasoning'),'reasoning_field':r.get('reasoning_field'),'finish_reason':r.get('finish_reason')})
 return out
def summarize(r:dict[str,list[dict[str,Any]]])->dict[str,Any]:
 out={}
 for a,x in r.items():
  toks=[z['usage']['total_tokens'] for z in x if isinstance(z['usage'],dict) and isinstance(z['usage'].get('total_tokens'),int)]; lat=[z['latency_ms'] for z in x if isinstance(z['latency_ms'],(int,float))]; calls=[z['model_calls'] for z in x if isinstance(z['model_calls'],int)]
  out[a]={'total':32,'valid':sum(z['valid'] for z in x),'invalid':sum(not z['valid'] for z in x),'environment_correct':sum(z['environment_correct'] for z in x),'known_model_calls':sum(calls),'not_attempted':sum(z['error_kind']=='NOT_ATTEMPTED_AFTER_COMPATIBILITY_FAILURE' for z in x),'unknown_call_attempts':sum(z['model_calls'] is None and z['error_kind']!='NOT_ATTEMPTED_AFTER_COMPATIBILITY_FAILURE' for z in x),'total_tokens':sum(toks),'unknown_token_rows':32-len(toks),'latency_ms':sum(lat),'unknown_latency_rows':32-len(lat),'family_correct':[sum(z['environment_correct'] for z in x if z['family']==f) for f in range(4)],'rows':x}
 return out
def run(v:dict[str,Any],out:Path,url:str,model:str,bridge_command=None)->dict[str,Any]:
 if out.exists():raise ValueError('output directory must not already exist')
 out.mkdir(mode=0o700); psha=digest(_json_bytes(v)); write_new(out/'started.json',{'plan_sha256':psha,'fixture_plan_sha256':v['fixture_plan_sha256'],'source_sha256':v['source_sha256'],'runner_source_sha256':v['runner_source_sha256'],'arm_order_by_case':v['arm_order_by_case'],'stop_rule':v['stop_rule'],'started_at':datetime.now(timezone.utc).isoformat(),'planned_attempts':96,'actual_execution':{'base_url':url,'model':model,'seed':v['frozen_execution']['seed'],'generation':GEN}})
 log=eval([budget_task(v['cases'],v['oracle_relation_by_family'],v['frozen_execution'],url,model,bridge_command)],model=None,log_dir=str(out/'inspect'),fail_on_error=True,max_tasks=1,max_samples=1)[0]
 r=rows(log,v['cases']); arms=summarize(r); first={a:r[a][0] for a in ARMS}
 if any(not z['valid'] for z in first.values()):
  observed=sum(x['known_model_calls'] for x in arms.values())
  if observed != 3: raise RuntimeError(f'compatibility gate accounting mismatch: expected 3 calls, observed {observed}')
  write_new(out/'failed.json',{'status':'NOT_READY','decision':'INCOMPLETE_NO_SCIENTIFIC_DECISION','attempted_calls':3,'remaining_unattempted':93,'compatibility_rows':first,'raw_inspect_log':str(log.location)}); raise RuntimeError('compatibility preflight failed')
 screen=v['screening']; per_arm_screen={a:(x['environment_correct']>=screen['correctAtLeast'] and all(n>=screen['eachFamilyCorrectAtLeast'] for n in x['family_correct']) and x['valid']==32) for a,x in arms.items()}
 baseline=arms['A_NONTHINK_32']['environment_correct']; candidates={a:(a!='A_NONTHINK_32' and per_arm_screen[a] and arms[a]['environment_correct']>baseline) for a in ARMS}
 pairs={f'{left}_VS_{right}':{'both_correct':sum(x['environment_correct'] and y['environment_correct'] for x,y in zip(r[left],r[right])),'left_only':sum(x['environment_correct'] and not y['environment_correct'] for x,y in zip(r[left],r[right])),'right_only':sum(not x['environment_correct'] and y['environment_correct'] for x,y in zip(r[left],r[right])),'both_wrong':sum(not x['environment_correct'] and not y['environment_correct'] for x,y in zip(r[left],r[right]))} for left,right in [('A_NONTHINK_32','B_NONTHINK_512'),('B_NONTHINK_512','C_THINK_512')]}
 raw_path=Path(log.location); raw_sha=digest(raw_path.read_bytes()) if raw_path.is_file() else None
 result={'schema':'hswm-budget-comparison/v1','status':'COMPLETE','decision':'CANDIDATE_FOR_FRESH_EVALUATION' if any(candidates.values()) else 'REVISE_LOCAL_EXECUTION','plan_sha256':psha,'fixture_plan_sha256':v['fixture_plan_sha256'],'source_sha256':v['source_sha256'],'runner_source_sha256':v['runner_source_sha256'],'arm_order_by_case':v['arm_order_by_case'],'stop_rule':v['stop_rule'],'started_at':json.loads((out/'started.json').read_text())['started_at'],'finished_at':datetime.now(timezone.utc).isoformat(),'cohort':'DEVELOPMENT_EXPOSED','planned_attempts':96,'attempted_calls':96,'actual_execution':{'base_url':url,'model':model,'seed':v['frozen_execution']['seed'],'generation':GEN},'arms':arms,'per_arm_screen':per_arm_screen,'candidate_for_fresh_evaluation':candidates,'paired_counts':pairs,'raw_inspect_log':{'path':str(log.location),'sha256':raw_sha},'noHoldoutClaim':True,'noEfficacyOrPopulationClaim':True};write_new(out/'summary.json',result);return result
def _validate_recovery_request(value: dict[str, Any], arm: str, plan_value: dict[str, Any]) -> None:
    """Confirm the retained bridge request used the frozen mode and model."""
    request = value.get("request")
    if not isinstance(request, dict):
        raise ValueError("missing retained request")
    execution = plan_value["frozen_execution"]
    generation = plan_value["generation"][arm]
    expected_max_tokens = 32 if arm == "A_NONTHINK_32" else 512
    if request.get("model") != execution["model"]:
        raise ValueError("request model differs from frozen plan")
    if request.get("seed") != execution["seed"]:
        raise ValueError("request seed differs from frozen plan")
    if request.get("max_tokens") != expected_max_tokens:
        raise ValueError("request token cap differs from frozen plan")
    for name in ("temperature", "top_p", "top_k", "min_p"):
        if request.get(name) != generation[name]:
            raise ValueError("request generation differs from frozen plan")
    template = request.get("chat_template_kwargs")
    if not isinstance(template, dict) or template.get("enable_thinking") != generation["thinking"]:
        raise ValueError("request thinking mode differs from frozen plan")


def recover(frozen_plan: Path, raw_log: Path, out: Path, outer_exit_code: int) -> dict[str, Any]:
    """Summarize a timeout-retained Inspect prefix without inventing missing calls."""
    if outer_exit_code != 124:
        raise ValueError("recovery requires outer exit code 124")
    if out.exists():
        raise ValueError("output must not already exist")
    plan_value = json.loads(frozen_plan.read_text(encoding="utf8"))
    if plan_value.get("schema") != "hswm-budget-comparison/v1":
        raise ValueError("unsupported frozen plan")
    cases = plan_value.get("cases")
    if not isinstance(cases, list) or len(cases) != 32 or plan_value.get("planned_attempts") != 96:
        raise ValueError("invalid frozen plan")
    log = read_eval_log(str(raw_log))
    if str(getattr(log, "status", "")) not in ("started", "cancelled"):
        raise ValueError("recovery accepts only incomplete Inspect logs")
    samples = list(log.samples or [])
    known = {str(case["id"]): case for case in cases}
    identifiers = [str(sample.id) for sample in samples]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("duplicate sample id")
    if any(identifier not in known for identifier in identifiers):
        raise ValueError("unknown sample id")
    scheduled_prefix = sorted(str(case["id"]) for case in cases[:len(samples)])
    if identifiers != scheduled_prefix:
        raise ValueError("samples are not a sorted frozen-dataset prefix")
    if not samples or len(samples) > 32:
        raise ValueError("invalid retained sample count")
    retained: list[dict[str, Any]] = []
    for sample, identifier in zip(samples, identifiers, strict=True):
        case = known[identifier]
        if getattr(sample, "target", None) != case["target"]:
            raise ValueError("sample target differs from frozen plan")
        sample_meta = getattr(sample, "metadata", {}) or {}
        if not isinstance(sample_meta, dict) or sample_meta.get("budget_case") != case:
            raise ValueError("sample case metadata differs from frozen plan")
        meta = getattr(getattr(sample, "output", None), "metadata", {}) or {}
        arms = meta.get("hswm_budget_arms") if isinstance(meta, dict) else None
        if not isinstance(arms, dict) or set(arms) != set(ARMS) or meta.get("arm_order") != plan_value["arm_order_by_case"].get(identifier):
            raise ValueError("invalid arm metadata or order")
        for arm, value in arms.items():
            if not isinstance(value, dict):
                raise ValueError("invalid arm result")
            valid = value.get("valid") is True
            if valid and value.get("answer") not in ("0", "1"):
                raise ValueError("valid answer is not binary")
            calls = value.get("model_calls")
            if calls not in (None, 0, 1) or isinstance(calls, bool):
                raise ValueError("invalid model call accounting")
            _validate_recovery_request(value, arm, plan_value)
            if arm == "C_THINK_512" and valid and (not isinstance(value.get("reasoning"), str) or not value["reasoning"].strip()):
                raise ValueError("C lacks reasoning channel")
            retained.append({"id":identifier,"family":case["family"],"answer":value.get("answer") if valid else None,"valid":valid,"error_kind":value.get("error_kind"),"environment_target":case["target"],"environment_correct":valid and value.get("answer")==case["target"],"request_sha256":value.get("request_sha256"),"response_sha256":value.get("response_sha256"),"usage":value.get("usage"),"latency_ms":value.get("latency_ms"),"model_calls":calls,"reasoning":value.get("reasoning"),"reasoning_field":value.get("reasoning_field"),"finish_reason":value.get("finish_reason"),"arm":arm})
    n=len(samples); grouped={arm:[row for row in retained if row["arm"]==arm] for arm in ARMS}; arm_summary={}
    for arm, arm_rows in grouped.items():
        tokens=[row["usage"]["total_tokens"] for row in arm_rows if isinstance(row["usage"],dict) and isinstance(row["usage"].get("total_tokens"),int) and not isinstance(row["usage"].get("total_tokens"),bool)]
        latency=[row["latency_ms"] for row in arm_rows if isinstance(row["latency_ms"],(int,float)) and not isinstance(row["latency_ms"],bool)]
        calls=[row["model_calls"] for row in arm_rows if isinstance(row["model_calls"],int) and not isinstance(row["model_calls"],bool)]
        arm_summary[arm]={"total":n,"family_denominators":[sum(row["family"]==family for row in arm_rows) for family in range(4)],"valid":sum(row["valid"] for row in arm_rows),"invalid":sum(not row["valid"] for row in arm_rows),"environment_correct":sum(row["environment_correct"] for row in arm_rows),"known_model_calls":sum(calls),"unknown_call_attempts":n-len(calls),"total_tokens":sum(tokens),"unknown_token_rows":n-len(tokens),"latency_ms":sum(latency),"unknown_latency_rows":n-len(latency),"family_correct":[sum(row["environment_correct"] and row["family"]==family for row in arm_rows) for family in range(4)],"rows":arm_rows}
    lower=sum(summary["known_model_calls"] for summary in arm_summary.values())
    result={"schema":"hswm-budget-recovery/v1","status":"PARTIAL_TIMEOUT","decision":"INCOMPLETE_NO_SCIENTIFIC_DECISION","cohort":"DEVELOPMENT_EXPOSED","planned_attempts":96,"attempted_calls":None,"retained_cases":n,"retained_calls":3*n,"unretained_planned_calls":96-3*n,"attempted_call_bounds":{"lower":lower,"upper":96},"frozen_plan_file":{"path":str(frozen_plan),"sha256":digest(frozen_plan.read_bytes())},"raw_inspect_log":{"path":str(raw_log),"sha256":digest(raw_log.read_bytes())},"actual_execution":{"model":plan_value["frozen_execution"]["model"],"seed":plan_value["frozen_execution"]["seed"],"generation":plan_value["generation"]},"started_at":getattr(log.eval,"created",None),"finished_at":None,"arms":arm_summary,"noHoldoutClaim":True,"noEfficacyOrPopulationClaim":True}
    write_new(out,result)
    return result

def main():
 p=argparse.ArgumentParser();p.add_argument('command',choices=('plan','run','recover'));p.add_argument('fixture',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--base-url');p.add_argument('--model');p.add_argument('--log',type=Path);p.add_argument('--outer-exit-code',type=int);a=p.parse_args()
 if a.command=='recover':
  if not a.log or a.outer_exit_code is None: raise ValueError('recover requires --log and --outer-exit-code')
  recover(a.fixture,a.log,a.out,a.outer_exit_code); return
 v=plan(a.fixture)
 if a.command=='run':
  if not a.base_url or not a.model:raise ValueError('run requires --base-url and --model')
  run(v,a.out,a.base_url,a.model)
 else:write_new(a.out,v)
if __name__=='__main__':main()
