from __future__ import annotations
import importlib.util,json,subprocess,sys
from pathlib import Path
from types import SimpleNamespace
import pytest
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'_research/inspect_comparison_v1';sys.path.insert(0,str(D))
spec=importlib.util.spec_from_file_location('budget_comparison',D/'budget_comparison.py');m=importlib.util.module_from_spec(spec);assert spec and spec.loader;sys.modules[spec.name]=m;spec.loader.exec_module(m)
def fixture(t):
 d=t/'f';subprocess.run(['node',str(D/'prepare_oracle_diagnostic.mts'),str(d)],cwd=ROOT,check=True,capture_output=True,text=True);return d
def response(answer,reasoning='r'):
 return {'valid':True,'answer':answer,'error_kind':None,'request_sha256':'a'*64,'response_sha256':'b'*64,'usage':{'total_tokens':2},'latency_ms':1,'model_calls':1,'reasoning':reasoning,'reasoning_field':'reasoning','finish_reason':'stop'}
def fake_log(cases):
 return SimpleNamespace(samples=[SimpleNamespace(id=c['id'],output=SimpleNamespace(metadata={'hswm_budget_arms':{a:response(c['target']) for a in m.ARMS}})) for c in cases],location=Path('fake.eval'))
def test_plan_is_96_and_rotates_development_cases(tmp_path):
 p=m.plan(fixture(tmp_path));assert p['planned_attempts']==96 and len(p['cases'])==32 and p['generation']['C_THINK_512']['thinking'] is True
 assert p['generation']['A_NONTHINK_32']['temperature']==.6

def test_summary_counts_all_arms_and_families(tmp_path):
 p=m.plan(fixture(tmp_path));r=m.rows(fake_log(p['cases']),p['cases']);s=m.summarize(r)
 assert all(s[a]['environment_correct']==32 and s[a]['family_correct']==[8]*4 for a in m.ARMS)

def test_run_compatibility_failure_is_counted_not_retried(tmp_path,monkeypatch):
 p=m.plan(fixture(tmp_path));log=fake_log(p['cases']);log.samples[0].output.metadata['hswm_budget_arms']['C_THINK_512']=response('0','')
 for sample in log.samples[1:]:
  sample.output.metadata['hswm_budget_arms']={a:{'valid':False,'answer':None,'error_kind':'NOT_ATTEMPTED_AFTER_COMPATIBILITY_FAILURE','request_sha256':None,'response_sha256':None,'usage':None,'latency_ms':None,'model_calls':None,'reasoning':None,'reasoning_field':None,'finish_reason':None} for a in m.ARMS}
 monkeypatch.setattr(m,'budget_task',lambda *a,**k:None);monkeypatch.setattr(m,'eval',lambda *a,**k:[log])
 with pytest.raises(RuntimeError,match='compatibility'):m.run(p,tmp_path/'out','http://127.0.0.1:1','fake')
 x=json.loads((tmp_path/'out/failed.json').read_text());assert x['attempted_calls']==3 and x['remaining_unattempted']==93

def test_actual_inspect_solver_stops_bridge_after_three_compatibility_calls(tmp_path, monkeypatch):
    p=m.plan(fixture(tmp_path)); calls=[]
    def fake_eval(relation, example, execution, **kwargs):
        calls.append((example.id, execution.max_tokens, kwargs['generation']['thinking']))
        missing = example.id == p['compatibility_case_id'] and kwargs['generation']['thinking']
        return {**response(example.target, '' if missing else 'reasoning'), 'model':execution.model}
    monkeypatch.setattr(m, 'evaluate_relation', fake_eval)
    out=tmp_path/'actual-gate'
    with pytest.raises(RuntimeError, match='compatibility'):
        m.run(p,out,'http://127.0.0.1:1','fake')
    assert len(calls)==3
    failed=json.loads((out/'failed.json').read_text())
    assert failed['attempted_calls']==3 and failed['remaining_unattempted']==93
    # Inspect did visit the remaining evaluator samples, but the solver made no calls for them.
    from inspect_ai.log import read_eval_log
    log=read_eval_log(failed['raw_inspect_log'])
    assert len(log.samples)==32
    blocked=sum(1 for s in log.samples[1:] for r in s.output.metadata['hswm_budget_arms'].values() if r['error_kind']=='NOT_ATTEMPTED_AFTER_COMPATIBILITY_FAILURE')
    assert blocked==93


def test_actual_inspect_solver_runs_96_in_predeclared_case_orders(tmp_path, monkeypatch):
    p=m.plan(fixture(tmp_path)); calls=[]
    def fake_eval(relation, example, execution, **kwargs):
        arm=next(a for a,g in m.GEN.items() if g==kwargs['generation'] and execution.max_tokens==(32 if a=='A_NONTHINK_32' else 512))
        calls.append((example.id,arm))
        answer='0' if arm=='C_THINK_512' and example.id==p['cases'][1]['id'] else example.target
        return {**response(answer,'reasoning' if arm=='C_THINK_512' else None),'model':execution.model}
    monkeypatch.setattr(m,'evaluate_relation',fake_eval)
    result=m.run(p,tmp_path/'actual-full','http://127.0.0.1:1','fake')
    assert len(calls)==96
    for pos, case in enumerate(p['cases']):
        assert [arm for identifier,arm in calls[pos*3:pos*3+3] if identifier==case['id']]==p['arm_order_by_case'][case['id']]
    assert result['arms']['C_THINK_512']['environment_correct']==31

def test_recover_partial_real_inspect_log_and_rejects_malformed(tmp_path, monkeypatch):
    from inspect_ai.log import write_eval_log, read_eval_log
    p=m.plan(fixture(tmp_path)); plan_path=tmp_path/'frozen.json'; plan_path.write_text(json.dumps(p))
    def fake_eval(relation, example, execution, **kwargs):
        generation=kwargs['generation']
        request={
            'model':execution.model,
            'seed':execution.seed,
            'max_tokens':execution.max_tokens,
            'temperature':generation['temperature'],
            'top_p':generation['top_p'],
            'top_k':generation['top_k'],
            'min_p':generation['min_p'],
            'chat_template_kwargs':{'enable_thinking':generation['thinking']},
        }
        return {**response(example.target, 'reasoning' if generation['thinking'] else None), 'model':execution.model, 'request':request}
    monkeypatch.setattr(m,'evaluate_relation',fake_eval)
    logs=m.eval([m.budget_task(p['cases'],p['oracle_relation_by_family'],p['frozen_execution'],'http://127.0.0.1:1',p['frozen_execution']['model'])],model=None,log_dir=str(tmp_path/'logs'),fail_on_error=True,max_tasks=1,max_samples=1)
    short_log=read_eval_log(logs[0].location); short_log.status='started'; first_four={case['id'] for case in p['cases'][:4]}; short_log.samples=[sample for sample in short_log.samples if sample.id in first_four]
    short_raw=tmp_path/'short.eval'; write_eval_log(short_log,short_raw)
    short_result=m.recover(plan_path,short_raw,tmp_path/'short-recovery.json',124)
    assert [row['id'] for row in short_result['arms']['A_NONTHINK_32']['rows']]==sorted(case['id'] for case in p['cases'][:4])
    log=read_eval_log(logs[0].location); log.status='started'; log.samples=log.samples[:26]
    raw=tmp_path/'partial.eval'; write_eval_log(log,raw)
    out=tmp_path/'recovery.json'; result=m.recover(plan_path,raw,out,124)
    assert result['status']=='PARTIAL_TIMEOUT' and result['retained_cases']==26
    assert result['retained_calls']==78 and result['unretained_planned_calls']==18
    assert result['attempted_calls'] is None and result['arms']['A_NONTHINK_32']['total']==26
    assert result['arms']['A_NONTHINK_32']['family_denominators']==[8,8,8,2]
    assert result['frozen_plan_file']['sha256']==m.digest(plan_path.read_bytes())
    assert result['attempted_call_bounds']=={'lower':78,'upper':96}
    bad=read_eval_log(raw); bad.samples[1].id=bad.samples[0].id; duplicate=tmp_path/'duplicate.eval'; write_eval_log(bad,duplicate)
    with pytest.raises(ValueError,match='prefix'):m.recover(plan_path,duplicate,tmp_path/'x.json',124)
    nonprefix_log=read_eval_log(raw); nonprefix_log.samples[0],nonprefix_log.samples[1]=nonprefix_log.samples[1],nonprefix_log.samples[0]
    with monkeypatch.context() as local_patch:
        local_patch.setattr(m, 'read_eval_log', lambda _path: nonprefix_log)
        with pytest.raises(ValueError,match='prefix'):m.recover(plan_path,raw,tmp_path/'order.json',124)
    duplicate_log=read_eval_log(raw); duplicate_log.samples[1].id=duplicate_log.samples[0].id
    with monkeypatch.context() as local_patch:
        local_patch.setattr(m, 'read_eval_log', lambda _path: duplicate_log)
        with pytest.raises(ValueError,match='duplicate'):m.recover(plan_path,raw,tmp_path/'direct-duplicate.json',124)
    wrong_target=read_eval_log(raw); wrong_target.samples[0].target='1' if wrong_target.samples[0].target=='0' else '0'
    with monkeypatch.context() as local_patch:
        local_patch.setattr(m, 'read_eval_log', lambda _path: wrong_target)
        with pytest.raises(ValueError,match='target'):m.recover(plan_path,raw,tmp_path/'wrong-target.json',124)
    wrong_request=read_eval_log(raw)
    wrong_request.samples[0].output.metadata['hswm_budget_arms']['A_NONTHINK_32']['request']['max_tokens']=999
    with monkeypatch.context() as local_patch:
        local_patch.setattr(m, 'read_eval_log', lambda _path: wrong_request)
        with pytest.raises(ValueError,match='token cap'):m.recover(plan_path,raw,tmp_path/'wrong-request.json',124)
    bad=read_eval_log(raw); del bad.samples[0].output.metadata['hswm_budget_arms']['B_NONTHINK_512']; missing=tmp_path/'missing.eval'; write_eval_log(bad,missing)
    with pytest.raises(ValueError,match='metadata'):m.recover(plan_path,missing,tmp_path/'y.json',124)
    complete=read_eval_log(raw); complete.status='success'; success=tmp_path/'success.eval'; write_eval_log(complete,success)
    with pytest.raises(ValueError,match='incomplete'):m.recover(plan_path,success,tmp_path/'z.json',124)
