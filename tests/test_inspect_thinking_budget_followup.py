from __future__ import annotations
import importlib.util, subprocess, sys
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]; D=ROOT/'_research/inspect_comparison_v1';sys.path.insert(0,str(D))
spec=importlib.util.spec_from_file_location('thinking_budget_followup',D/'thinking_budget_followup.py');m=importlib.util.module_from_spec(spec);assert spec and spec.loader;sys.modules[spec.name]=m;spec.loader.exec_module(m)
def fixture(tmp_path):
 d=tmp_path/'f';subprocess.run(['node',str(D/'prepare_oracle_diagnostic.mts'),str(d)],cwd=ROOT,check=True,capture_output=True,text=True);return d
def test_plan_is_frozen_32_thinking_1024(tmp_path):
 p=m.plan(fixture(tmp_path));assert len(p['cases'])==32 and p['budget']==32 and p['max_tokens']==1024 and p['timeout_seconds']==60 and p['generation']['thinking'] is True
def test_rows_retains_invalid_reasoning_failure(tmp_path):
 p=m.plan(fixture(tmp_path)); samples=[]
 for i,c in enumerate(p['cases']):
  r={'valid':True,'answer':c['target'],'reasoning':'trace','error_kind':None,'request_sha256':'a'*64,'response_sha256':'b'*64,'usage':{'total_tokens':2},'latency_ms':1,'model_calls':1,'reasoning_field':'reasoning','finish_reason':'stop'}
  if i==0:r['reasoning']=''
  samples.append(SimpleNamespace(id=c['id'],output=SimpleNamespace(metadata={'thinking_followup':r})))
 rows=m.rows(SimpleNamespace(status='success',samples=samples),p); s=m.summary(rows);assert len(rows)==32 and not rows[0]['valid'] and s['invalid']==1 and s['known_model_calls']==32
def test_run_uses_decorated_inspect_task_with_fake_bridge(tmp_path,monkeypatch):
 p=m.plan(fixture(tmp_path)); calls=[]
 def fake(_relation, example, execution, **kw):
  calls.append((example.id,execution.max_tokens,execution.timeout_seconds,kw['generation']))
  return {'valid':True,'answer':example.target,'error_kind':None,'request_sha256':'a'*64,'response_sha256':'b'*64,'usage':{'total_tokens':2},'latency_ms':1,'model_calls':1,'reasoning':'' if len(calls)==1 else 'trace','reasoning_field':'reasoning','finish_reason':'stop'}
 monkeypatch.setattr(m,'evaluate_relation',fake)
 out=m.run(p,tmp_path/'out','http://127.0.0.1:1','fake')
 assert [c[0] for c in calls]==[case['id'] for case in p['cases']]
 assert all(c[1:3]==(1024,60) and c[3]==m.GEN for c in calls)
 assert out['arms'][m.ARM]['invalid']==1 and out['decision']=='REVISE_LOCAL_EXECUTION'
