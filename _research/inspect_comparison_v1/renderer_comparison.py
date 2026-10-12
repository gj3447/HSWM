"""Paired legacy-versus-ordered renderer diagnostic; development only, never efficacy."""
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from live_eval import Execution, LiveExample, run_live
from oracle_single_diagnostic import COHORT, build, digest, _json_bytes, _make_examples, _sample_rows

def write_new(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f: json.dump(value, f, indent=2, sort_keys=True); f.write('\n')

def arm(rows: list[dict[str, Any]], name: str) -> dict[str, Any]:
    tokens=[r['usage']['total_tokens'] for r in rows if isinstance(r.get('usage'),dict) and isinstance(r['usage'].get('total_tokens'),int)]
    latency=[r['latency_ms'] for r in rows if isinstance(r.get('latency_ms'),(int,float)) and not isinstance(r.get('latency_ms'),bool)]
    calls=[r['model_calls'] for r in rows if isinstance(r.get('model_calls'),int) and not isinstance(r.get('model_calls'),bool)]
    return {'name':name,'total':len(rows),'valid':sum(r['valid'] for r in rows),'invalid':sum(not r['valid'] for r in rows),
      'environment_correct':sum(r['environment_correct'] for r in rows),'frozen_rule_consistent':sum(r['frozen_rule_consistent'] for r in rows),
      'known_model_calls':sum(calls),'unknown_call_attempts':len(rows)-len(calls),'total_tokens':sum(tokens),'unknown_token_rows':len(rows)-len(tokens),
      'latency_ms':sum(latency),'unknown_latency_rows':len(rows)-len(latency),'rows':rows}

def paired(legacy: list[dict[str,Any]], ordered: list[dict[str,Any]]) -> tuple[list[dict[str,Any]],dict[str,int]]:
    by={r['id']:r for r in ordered}; out=[]; counts={'both_correct':0,'legacy_only':0,'ordered_only':0,'both_wrong':0}
    for l in legacy:
        o=by.get(l['id'])
        if not o: raise RuntimeError('ordered log omitted a legacy id')
        key='both_correct' if l['environment_correct'] and o['environment_correct'] else 'legacy_only' if l['environment_correct'] else 'ordered_only' if o['environment_correct'] else 'both_wrong'
        counts[key]+=1; out.append({'id':l['id'],'family':l['family'],'legacy_correct':l['environment_correct'],'ordered_correct':o['environment_correct'],'discordance':key})
    return out,counts

def plan(fixture_root: Path) -> dict[str,Any]:
    base=build(fixture_root)
    runner_sources = {name: digest(Path(__file__).with_name(name).read_bytes()) for name in ('renderer_comparison.py', 'live_eval.py', 'hswm_bridge.mts')}
    return {'schema':'hswm-renderer-comparison/v1','cohort':'DEVELOPMENT_EXPOSED','evidence_kind':'PLANNED_RENDERER_COMPARISON_NOT_EFFICACY','fixture_root':str(fixture_root),'source_fixture_plan_sha256':digest(_json_bytes(base)), 'source_sha256':base['families'][0]['source_sha256'],'runner_source_sha256':runner_sources, 'families':base['families'],'frozen_execution':base['frozen_execution'],'logical_cases':32,'planned_attempts':64,'noHoldoutClaim':True,'screening':{'candidateCorrectAtLeast':30,'eachFamilyCandidateCorrectAtLeast':7,'allOutputsValid':True},'arm_order_by_family':{str(f['family']): ('ORDERED_THEN_LEGACY' if f['family'] % 2 else 'LEGACY_THEN_ORDERED') for f in base['families']},'counterbalance_limitation':'Counterbalanced by family only; not a per-case randomized-order claim.','renderers':{'legacy':'bridge JSON.stringify(LocalSemanticInput) byte-equivalent default','ordered':'deterministic relation/roles/priorEvidence/fields presentation'},'old_relation_sha256':digest(''.join(x['oracle_text'] for x in base['families']).encode()),'old_relation_sha256_description':'aggregate digest of frozen oracle relation texts used by both arms; not a historical baseline answer arm'}

def run(value:dict[str,Any], out:Path, base_url:str, model:str) -> dict[str,Any]:
    if out.exists(): raise ValueError('output directory must not already exist')
    out.mkdir(mode=0o700); frozen=value['frozen_execution']; execution=Execution(base_url,model,frozen['max_tokens'],frozen['timeout_seconds'],frozen['seed'])
    psha=digest(_json_bytes(value)); write_new(out/'started.json',{'plan_sha256':psha,'started_at':datetime.now(timezone.utc).isoformat(),'actual_execution':{**execution.as_dict(),'temperature':0,'thinking':False},'planned_attempts':64})
    receipts=[]
    try:
      for family in value['families']:
        cases=family['selected']; logs=run_live(_make_examples(cases),family['oracle_text'],family['oracle_text'],execution,out/f"family-{family['family']}",dataset_sha256=family['dataset_sha256'],baseline_renderer='legacy',candidate_renderer='ordered',candidate_first=family['family'] % 2 == 1)
        legacy=_sample_rows(logs[0],cases,'legacy'); ordered=_sample_rows(logs[1],cases,'ordered')
        for rows in (legacy,ordered):
          for row in rows: row['family']=family['family']; row['pel']=next(c['pel'] for c in cases if c['id']==row['id']); row['nub']=next(c['nub'] for c in cases if c['id']==row['id'])
        pairs,counts=paired(legacy,ordered); raw_logs=[{'path':str(x.location), 'sha256': digest(Path(x.location).read_bytes()) if Path(x.location).is_file() else None} for x in logs]
        receipt={'family':family['family'],'fixture_sha256':family['fixture_sha256'],'dataset_sha256':family['dataset_sha256'],'raw_logs':raw_logs,'actual_order':value['arm_order_by_family'][str(family['family'])],'legacy':arm(legacy,'legacy'),'ordered':arm(ordered,'ordered'),'paired_rows':pairs,'paired_counts':counts}; write_new(out/f"family-{family['family']}.json",receipt); receipts.append(receipt)
    except Exception as e:
      done=len(receipts)*16; write_new(out/'failed.json',{'status':'INCOMPLETE','error':str(e),'completed_confirmed_calls':done,'current_family_attempts':'UNKNOWN_UP_TO_16','remaining_unattempted':64-done-16,'decision':'INCOMPLETE_NO_DECISION'}); raise
    legacy=[r for x in receipts for r in x['legacy']['rows']]; ordered=[r for x in receipts for r in x['ordered']['rows']]; pairs,counts=paired(legacy,ordered); s=value['screening']; passed=sum(r['environment_correct'] for r in ordered)>=s['candidateCorrectAtLeast'] and all(x['ordered']['environment_correct']>=s['eachFamilyCandidateCorrectAtLeast'] for x in receipts) and all(r['valid'] for r in legacy+ordered)
    result={'schema':'hswm-renderer-comparison/v1','status':'COMPLETE','decision':'DEVELOPMENT_SCREEN_PASSED' if passed else 'REVISE_LOCAL_EXECUTION','plan_sha256':psha,'source_fixture_plan_sha256':value['source_fixture_plan_sha256'],'source_sha256':value['source_sha256'],'runner_source_sha256':value['runner_source_sha256'],'started_at':json.loads((out/'started.json').read_text())['started_at'],'finished_at':datetime.now(timezone.utc).isoformat(),'arm_order_by_family':value['arm_order_by_family'],'counterbalance_limitation':value['counterbalance_limitation'],'actual_execution':{**execution.as_dict(),'temperature':0,'thinking':False},'cohort':'DEVELOPMENT_EXPOSED','logical_cases':32,'planned_attempts':64,'noHoldoutClaim':True,'attempted_calls':64,'old_relation_sha256':value['old_relation_sha256'],'renderers':value['renderers'],'legacy':arm(legacy,'legacy'),'ordered':arm(ordered,'ordered'),'paired_rows':pairs,'paired_counts':counts,'results':receipts,'noHoldoutClaim':True,'noEfficacyOrPopulationClaim':True}; write_new(out/'summary.json',result); return result

def main()->None:
 p=argparse.ArgumentParser(); p.add_argument('command',choices=('plan','verify','run')); p.add_argument('fixture_root',type=Path); p.add_argument('--out',type=Path,required=True); p.add_argument('--base-url'); p.add_argument('--model'); a=p.parse_args(); v=plan(a.fixture_root)
 if a.command=='run':
  if not a.base_url or not a.model: raise ValueError('run requires --base-url and --model')
  run(v,a.out,a.base_url,a.model)
 else: write_new(a.out,v)
if __name__=='__main__': main()
