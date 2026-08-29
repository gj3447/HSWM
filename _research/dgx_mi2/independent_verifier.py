"""Independent fail-closed evidence reducer for a frozen MI-2 run.

No ``_research.dgx_mi2`` module is imported: this file is safe to bind in the
frozen verifier manifest and replay without a producer implementation.
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
from hashlib import sha256
import itertools
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from _research.dnrd5.canonical_json import canonical_bytes, canonical_sha256, parse_canonical
from _research.dgx_q1.github_ci_receipt import parse_github_actions_ci_receipt
from _research.dgx_q1.live_protocol import validate_response_schema

PLAN_SCHEMA="hswm-dgx-qcase024-mi2-launch-crossed-plan/v1"
FREEZE_SCHEMA="hswm-dgx-qcase024-mi2-launch-crossed-preregistration-freeze/v1"
SEED_SCHEMA="hswm-dgx-qcase024-mi2-launch-crossed-csprng-raw-draw/v2"
LEDGER="hswm-dgx-mi2-launch-crossed-ledger/v1"
NAMESPACE="DNRD5-QCASE024-MI-2-LAUNCH-CROSSED-ONLY/v1"
REGISTRY={"schema_version":"hswm-dgx-qcase024-mi2-launch-crossed-consumption-registry/v1","path":"/mnt/hswm/evidence/hswm-dnrd5-qcase024-mi-2-launch-crossed-v1-consumption-v1","scope":"PINNED_DGX_NODE_LOCAL_DURABLE_PLAN_HASH_REGISTRY","boundary":"NODE_LOCAL_PATH_BINDING_NOT_DISTRIBUTED_GLOBAL_CONSENSUS","terminal":"ONE_DURABLE_BURN_PER_PLAN_HASH_AT_THE_DECLARED_PATH"}
NONCLAIMS=("POST_RESULT_SELECTED_CASE_FINITE_RANDOMIZED_CONTRAST_ONLY_NOT_GENERALIZABLE","NOT_A_Q1_RETRY_OR_BATCH_INVARIANCE_QUALIFICATION","NOT_A_DNRD5_300_BLOCK_OCCURRENCE_OR_SOURCE_A_AUTHORIZATION","NOT_MECHANISTIC_ATTRIBUTION_TO_PROVIDER_INTERNAL_SCHEDULER_GDN_FP8_KERNEL_OR_LAUNCH_TIME","NOT_PROOF_OF_NO_INTERFERENCE_OR_HSWM_CAUSAL_LEARNING","NOT_PROOF_OF_CONSCIOUSNESS_SELFHOOD_OR_SCALE_INVARIANT_CAUSAL_CLOSURE")
EXPECTED_MATERIAL={"instruction.txt":"8e13131449ba0f31cb7305490dec680f6808006db2e5b50cc8614b172c85b907","model_input.json":"5902dec004e606aaf46b8a5d80c45ab855f275d714d111b2430d86d0e1c1a273","response_schema.json":"a623afd2cace659731c46b336fd4cb75c071e60f425fa583e8995abe7ff83940","rng.bin":"69b1f0ef2be0d6519baa19562928cc6ed3a458e382e48508a4cb47292063bd78"}
EXPECTED_REQUEST="fec3b64ce00d750e67a34374fe9d1e5e7fa6232294b8990e0aa4f352bc52fac9"
EXPECTED_MI1={"mi1_result_commit":"4891e8560f54983461b1904e7c5f8bb9fcc4cdfe","mi1_result_tree":"c400df84f67a24805af964473c644a293ea02297","mi1_result_ci_receipt_sha256":"f2e84493a1d3f6a5794483c4ecc9de9e81fec938ff53eb5b8978d60d535d304a","mi1_evidence_sha256":"82807014e3b6bbffaa675e4c79f7c25b60a94a2afc5e2bbe7dc45bb896b34681","mi1_result_projection_sha256":"8bd6a537812344a1036e2c4206cd8129ed2294c1b40cca724c8bee4729c7ec43","mi1_ledger_sha256":"838f338946af641f69e0e234eafbe8589be9c783dbc12870e1d110128c8a160b","mi1_terminal":"LIVE_COMPLETE_DGX_QCASE024_MECHANISM_DIAGNOSTIC","mi1_observation_pattern":"BOTH_ARMS_VARIATION","selection_status":"POST_RESULT_SELECTED_CASE_FINITE_RANDOMIZED_CONTRAST_ONLY_NOT_GENERALIZABLE"}
COMPLETE="LIVE_COMPLETE_DGX_QCASE024_MI2_RANDOMIZED_LAUNCH_EXPERIMENT"
INCOMPLETE="INCONCLUSIVE_DGX_QCASE024_MI2_INCOMPLETE_LAUNCHES"
UNAVAILABLE="INCONCLUSIVE_DGX_QCASE024_MI2_REQUIRED_CONTENT_OR_TRACE"
VOID="VOID_DGX_QCASE024_MI2_PROTOCOL_LEDGER_HASH_ORDER_OR_BOUNDARY_BREACH"
ASSOCIATION="FINITE_RANDOMIZED_ARM_ASSOCIATION_DETECTED"
NO_ASSOCIATION="FINITE_RANDOMIZED_NO_ARM_ASSOCIATION_DETECTED"
ZERO="0"*64; SHA=re.compile(r"^[0-9a-f]{64}$")
FULL_TRACE="hswm-dgx-mi2-full-processed-logprob-trace/v1"
PREFIX=b'{\n  "answer": "VISTA",\n  "rationale": "The first cue'
PREFIX_SHA="073d99db9361985aa3706af40d268a21bd9bb68fd608dd00a2b51ff3857b3bdf"
ARMS=("ASYNC_ENABLED","ASYNC_DISABLED")
SERVER_PREFIX=("--model","/model-repository/snapshots/95a723d08a9490559dae23d0cff1d9466213d989","--served-model-name","qwen3.6-35b-a3b","--host","0.0.0.0","--port","8000","--max-num-seqs","1","--no-enable-prefix-caching","--max-model-len","32768","--gpu-memory-utilization","0.500","--generation-config","vllm","--seed","0","--enforce-eager","--language-model-only","--max-logprobs","20","--logprobs-mode","processed_logprobs")
REQUIRED_ENV=("HF_HOME=/cache/huggingface","HUGGINGFACE_HUB_CACHE=/cache/huggingface/hub","VLLM_CACHE_ROOT=/cache/compile/vllm","TORCHINDUCTOR_CACHE_DIR=/cache/compile/torchinductor","TRITON_CACHE_DIR=/cache/compile/triton","HF_HUB_OFFLINE=1","TRANSFORMERS_OFFLINE=1","VLLM_ENABLE_V1_MULTIPROCESSING=0","PYTHONHASHSEED=0","CUBLAS_WORKSPACE_CONFIG=:4096:8")
RANDOMIZATION={"family_alpha":"0.05","endpoint_alpha":"0.025","multiplicity":"BONFERRONI_TWO_REGISTERED_ENDPOINTS","endpoints":[{"endpoint":"CONTENT_TV","statistic":"T_content=1/2*sum_c|N_E,c-N_D,c|","primary_replicate":"R001"},{"endpoint":"FIXED_BRANCH_MARGIN","statistic":"T_margin=abs(sum_E M_i-sum_D M_i)","primary_replicate":"R001","completion_row_zero_based":20,"prefix_length":52,"prefix_sha256":PREFIX_SHA,"candidates":{"indicates":{"token":" indicates","sha256":"55fde3431b756dfca90d8b612bb85fd7d7a282438be28c060af78d5081c0470e"},"explicitly":{"token":" explicitly","sha256":"d6a745a584f5f0b57eddf076426e31a457cf068a78b2caa9d0cc3778f354d697"}}}],"schedule_domain_count":400,"schedule_selection_method":"RAW_CSPRNG_256_BIT_INTEGER_REJECTION_SAMPLING_400_THEN_EXPLICIT_ED_DE_LEXICOGRAPHIC_SCHEDULE","raw_draw_acceptance":"RAW_256_BIT_CSPRNG_INTEGER_LT_FLOOR_2POW256_DIV_400_TIMES_400_THEN_MOD_400","upper_tail":"COUNT_T_GE_OBSERVED_OVER_ALL_400_SCHEDULES","minimum_attainable_inclusive_tail":"2/400=0.005_DUE_TO_GLOBAL_ARM_COMPLEMENT_SYMMETRY","unit":"FRESH_LAUNCH_PRIMARY_R001","trace_unavailable":"INCONCLUSIVE_REQUIRED_TRACE_ENDPOINT_UNAVAILABLE_NO_POST_HOC_FALLBACK","hash_binding_boundary":"SHA256_ARTIFACT_BINDING_PROVES_RECORDED_RAW_DRAW_AND_SELECTION_CONSISTENCY_NOT_ENTROPY_OR_MANIPULATION"}
TIME=re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")

def _bad(x: str="breach")->None: raise ValueError(x)
def _obj(x:Any,keys:set[str])->dict[str,Any]:
    if type(x)is not dict or set(x)!=keys: _bad("key set")
    return x
def _digest(x:Any)->str:
    if type(x)is not str or SHA.fullmatch(x) is None or x==ZERO: _bad("digest")
    return x
def _desc(x:Any)->dict[str,Any]:
    x=_obj(x,{"sha256","byte_length"}); _digest(x["sha256"])
    if type(x["byte_length"]) is not int or not 0<=x["byte_length"]<=16*1024*1024: _bad("length")
    return x
def _blob(root:Path,x:Any)->bytes:
    x=_desc(x); path=root/"content"/x["sha256"]
    if path.is_symlink() or not path.is_file(): _bad("blob")
    raw=path.read_bytes()
    if len(raw)!=x["byte_length"] or sha256(raw).hexdigest()!=x["sha256"]: _bad("blob hash")
    return raw
def _strict(raw:bytes)->Any:
    def pairs(rows:list[tuple[str,Any]])->dict[str,Any]:
        out={}
        for key,value in rows:
            if key in out: _bad("duplicate key")
            out[key]=value
        return out
    try: return json.loads(raw.decode("utf-8","strict"),object_pairs_hook=pairs,parse_float=str,parse_constant=lambda _: _bad("nonfinite"))
    except (UnicodeDecodeError,json.JSONDecodeError,RecursionError) as e: raise ValueError("json") from e
def _decimal(x:Any)->Decimal:
    if type(x)is not str: _bad("decimal")
    try: y=Decimal(x)
    except Exception as e: raise ValueError("decimal") from e
    if not y.is_finite(): _bad("decimal")
    return y
def _meta(keys:set[str])->set[str]: return keys|{"schema_version","ordinal","previous_record_sha256","record_sha256"}
def _time(x:Any)->None:
    if type(x)is not str or TIME.fullmatch(x) is None: _bad("time")
def _source(x:Any)->dict[str,Any]:
    x=_obj(x,{"commit","tree","ci_receipt_sha256","ci_terminal"})
    if any(type(x[n])is not str or not re.fullmatch(r"[0-9a-f]{40}",x[n]) or x[n]=="0"*40 for n in ("commit","tree")) or x["ci_terminal"]!="FIRST_ATTEMPT_SUCCESSFUL_CI_BUILD": _bad("source")
    _digest(x["ci_receipt_sha256"]); return x
def _arm_identities(root:Path,marker:dict[str,Any],plan:dict[str,Any],join:Any)->dict[str,list[str]]:
    names=("endpoint_sha256","model_identity_sha256","runtime_identity_sha256","tls_identity_sha256","declared_isolation_contract_sha256","model_snapshot_manifest_sha256")
    if type(marker["identities"])is not dict or set(marker["identities"])!=set(ARMS) or type(plan["arms"])is not dict or set(plan["arms"])!=set(ARMS): _bad("arms")
    runtimes={}; common=None
    for arm in ARMS:
        rows=_obj(marker["identities"][arm],set(names)); planned=_obj(plan["arms"][arm],set(names))
        raw={name:join(f"identities/{arm}/{name}.json",rows[name]) for name in names}
        if {name:sha256(value).hexdigest() for name,value in raw.items()}!=planned: _bad("arm digest")
        endpoint=_obj(parse_canonical(raw["endpoint_sha256"]),{"schema_version","endpoint","method","transport"})
        model=_obj(parse_canonical(raw["model_identity_sha256"]),{"schema_version","model","repository","revision","snapshot_manifest_sha256"})
        tls=_obj(parse_canonical(raw["tls_identity_sha256"]),{"schema_version","endpoint_scheme","tls"})
        snapshot=_obj(parse_canonical(raw["model_snapshot_manifest_sha256"]),{"schema_version","repository","revision","file_count","total_byte_length","files","files_sha256"})
        if endpoint!={"schema_version":"hswm-dgx-q1-endpoint-identity/v1","endpoint":"http://127.0.0.1:18080/v1/chat/completions","method":"POST","transport":"LOOPBACK_HTTP_NO_TLS"} or {k:model[k] for k in ("schema_version","model","repository","revision")}!={"schema_version":"hswm-dgx-q1-model-identity/v1","model":"qwen3.6-35b-a3b","repository":"Qwen/Qwen3.6-35B-A3B-FP8","revision":"95a723d08a9490559dae23d0cff1d9466213d989"} or model["snapshot_manifest_sha256"]!=sha256(raw["model_snapshot_manifest_sha256"]).hexdigest() or tls!={"schema_version":"hswm-dgx-q1-tls-identity/v1","endpoint_scheme":"http","tls":"NOT_APPLICABLE_LOOPBACK_ONLY"} or snapshot["schema_version"]!="hswm-dgx-q1-model-snapshot-manifest/v1" or snapshot["repository"]!=model["repository"] or snapshot["revision"]!=model["revision"] or type(snapshot["file_count"])is not int or snapshot["file_count"]<=0 or type(snapshot["files"])is not list or len(snapshot["files"])!=snapshot["file_count"] or sha256(raw["declared_isolation_contract_sha256"]).hexdigest()!="ac594ec24eb2a096b0053096c8650aeca33aa290d7146bd0793abddcd64e9ba1": _bad("identity semantic")
        runtime=_obj(parse_canonical(raw["runtime_identity_sha256"]),{"schema_version","container_image","image_id","vllm_version","gpu_uuid","gpu_name","gpu_driver_version","gpu_compute_capability","endpoint","served_model","model_revision","model_snapshot_manifest_sha256","max_model_len","max_num_seqs","gpu_memory_utilization_milli","prefix_cache","enforce_eager","batch_invariant","v1_multiprocessing","model_loading_offline","generation_config","engine_seed","language_model_only","container_internal_port","container_network_mode","container_ipc_mode","host_publish_ip","async_scheduling","server_arguments","required_environment","max_logprobs","logprobs_mode"})
        fixed={"schema_version":"hswm-dgx-qcase024-mi-runtime-identity/v4","container_image":"vllm/vllm-openai@sha256:e4f88a835143cd22aee2397a26ec6bb80b3a4a6fe0c882bcbc63822904766089","image_id":"sha256:30a38a1d74a17365eca400e83ffd885b250e0c8c0d3c5b508afa8c412d2ddf95","vllm_version":"0.25.1","gpu_uuid":"GPU-ffed5bca-3452-8e9e-03fb-b2a4d8f40bc5","gpu_name":"NVIDIA GB10","gpu_driver_version":"580.126.09","gpu_compute_capability":"12.1","endpoint":"http://127.0.0.1:18080/v1/chat/completions","served_model":"qwen3.6-35b-a3b","model_revision":"95a723d08a9490559dae23d0cff1d9466213d989","model_snapshot_manifest_sha256":"2ece6b46248e818cbf93aa30299300f7dd4c60d9351960ec790cc8b420376e47","max_model_len":32768,"max_num_seqs":1,"gpu_memory_utilization_milli":500,"prefix_cache":False,"enforce_eager":True,"batch_invariant":False,"v1_multiprocessing":False,"model_loading_offline":True,"generation_config":"vllm","engine_seed":0,"language_model_only":True,"container_internal_port":8000,"container_network_mode":"bridge","container_ipc_mode":"private","host_publish_ip":"127.0.0.1","max_logprobs":20,"logprobs_mode":"processed_logprobs"}
        expected_flag="--async-scheduling" if arm=="ASYNC_ENABLED" else "--no-async-scheduling"
        if {k:runtime[k] for k in fixed}!=fixed or sha256(raw["model_snapshot_manifest_sha256"]).hexdigest()!=fixed["model_snapshot_manifest_sha256"] or runtime["async_scheduling"]!=(arm=="ASYNC_ENABLED") or runtime["server_arguments"]!=[*SERVER_PREFIX,expected_flag] or tuple(runtime["required_environment"])!=REQUIRED_ENV: _bad("runtime")
        normalized=dict(runtime); normalized["async_scheduling"]="ARM"; normalized["server_arguments"]=["ARM" if x in {"--async-scheduling","--no-async-scheduling"} else x for x in runtime["server_arguments"]]
        if common is None: common=normalized
        elif common!=normalized: _bad("arm difference")
        runtimes[arm]=runtime
    return {arm:runtimes[arm]["server_arguments"] for arm in ARMS}
def _gpu_raw(raw:bytes)->None:
    try: lines=[line for line in raw.decode("utf-8","strict").splitlines() if line.strip()]
    except UnicodeDecodeError: _bad("gpu utf8")
    if len(raw)>16*1024 or len(lines)!=1 or len(lines[0].split(","))!=5 or lines[0].split(",")[0].strip()!="GPU-ffed5bca-3452-8e9e-03fb-b2a4d8f40bc5": _bad("gpu row")
def _descriptors(value:Any,out:set[str])->None:
    """Collect every content-addressed descriptor from a ledger value."""
    if type(value)is dict:
        if set(value)=={"sha256","byte_length"}:
            out.add(_desc(value)["sha256"]); return
        if set(value)=={"path","sha256","byte_length"}:
            out.add(_desc({"sha256":value["sha256"],"byte_length":value["byte_length"]})["sha256"]); return
        for child in value.values(): _descriptors(child,out)
    elif type(value)is list:
        for child in value: _descriptors(child,out)

def _all_schedules()->tuple[tuple[str,...],...]:
    half=list(itertools.combinations(range(6),3)); out=[]
    for left,right in itertools.product(half,repeat=2):
        chosen=set(left)|{x+6 for x in right}; out.append(tuple("ED" if x in chosen else "DE" for x in range(12)))
    return tuple(out)
ALL_SCHEDULES=_all_schedules()
if len(ALL_SCHEDULES)!=400: raise AssertionError
def _schedule(seed_raw:bytes)->tuple[int,tuple[str,...]]:
    seed=_obj(parse_canonical(seed_raw),{"schema_version","raw_draw_hex","selection_domain","terminal"})
    if seed["schema_version"]!=SEED_SCHEMA or seed["selection_domain"]!="HSWM-DNRD5-MI2-LAUNCH-CROSSED-SCHEDULE/v1" or seed["terminal"]!="RAW_CSPRNG_256_BIT_DRAW_REVEALED_BEFORE_SCHEDULE_SELECTION" or type(seed["raw_draw_hex"])is not str: _bad("seed")
    try: raw=bytes.fromhex(seed["raw_draw_hex"])
    except ValueError: _bad("seed hex")
    if len(raw)!=32 or raw.hex()!=seed["raw_draw_hex"]: _bad("seed bytes")
    limit=((1<<256)//400)*400
    number=int.from_bytes(raw,"big")
    if number>=limit: _bad("seed rejected tail")
    return number%400,ALL_SCHEDULES[number%400]
def _order(schedule:tuple[str,...])->list[dict[str,Any]]:
    out=[]
    for pair,orientation in enumerate(schedule,1):
        for position,letter in enumerate(orientation,1):
            absolute=len(out)+1
            out.append({"pair_id":f"P{pair:02d}","pair_orientation":orientation,"launch_position":position,"absolute_launch_index":absolute,"absolute_launch_parity":"ODD" if absolute%2 else "EVEN","prior_arm":None if not out else out[-1]["arm"],"arm":"ASYNC_ENABLED" if letter=="E" else "ASYNC_DISABLED","arm_code":letter})
    return out

def _ledger(root:Path)->list[dict[str,Any]]:
    path=root/"mi2_ledger.jsonl"
    if path.is_symlink() or not path.is_file(): _bad("ledger")
    raw=path.read_bytes()
    if not raw.endswith(b"\n"): _bad("framing")
    rows=[parse_canonical(x) for x in raw.splitlines()]; previous=ZERO
    for n,row in enumerate(rows,1):
        if type(row)is not dict or row.get("schema_version")!=LEDGER or row.get("ordinal")!=n or row.get("previous_record_sha256")!=previous: _bad("chain order")
        actual=canonical_sha256({k:v for k,v in row.items() if k!="record_sha256"})
        if row.get("record_sha256")!=actual: _bad("chain hash")
        previous=actual
    return rows
def _service(x:Any,arm:str)->dict[str,Any]:
    x=_obj(x,{"async_scheduling","container_name","observed"})
    if x["async_scheduling"]!=(arm=="ASYNC_ENABLED") or type(x["container_name"])is not str or not x["container_name"]: _bad("service")
    observed=_obj(x["observed"],{"container_id_sha256","container_start_sha256","cgroup_sha256","network_namespace_sha256","server_argv_sha256"})
    for value in observed.values(): _digest(value)
    return x
def _boundary(root:Path,desc:Any,core:dict[str,Any],service:dict[str,Any],phase:str,completed:int,argv:list[str],baseline:int|None=None)->int:
    x=_obj(parse_canonical(_blob(root,desc)),{"schema_version","pair_id","launch_index","arm","phase","completed","async_scheduling","server_argv","server_argv_sha256","server_identity","request_success_total","raw_metrics_sha256","terminal"})
    if x["schema_version"]!="hswm-dgx-mi2-boundary/v1" or any(x[k]!=core[k] for k in ("pair_id","launch_index","arm")) or x["phase"]!=phase or x["completed"]!=completed or x["async_scheduling"]!=service["async_scheduling"] or x["server_identity"]!=service["observed"] or x["server_argv"]!=argv or x["server_argv_sha256"]!=service["observed"]["server_argv_sha256"] or sha256("\0".join(x["server_argv"]).encode()).hexdigest()!=x["server_argv_sha256"] or type(x["request_success_total"])is not int or x["request_success_total"]<0 or x["terminal"]!="FINITE_LAUNCH_BOUNDARY_NOT_NO_INTERFERENCE_PROOF" or baseline is not None and x["request_success_total"]!=baseline+completed: _bad("boundary")
    _digest(x["raw_metrics_sha256"])
    return x["request_success_total"]
def _teardown(root:Path,desc:Any,gpu:Any,core:dict[str,Any])->None:
    x=_obj(parse_canonical(_blob(root,desc)),{"schema_version","pair_id","launch_index","arm","observed_at_utc","gpu_observation","quiescence","terminal"})
    if x["schema_version"]!="hswm-dgx-mi2-launch-crossed-teardown/v1" or any(x[k]!=core[k] for k in ("pair_id","launch_index","arm")) or x["terminal"]!="FINITE_TEARDOWN_NOT_NO_INTERFERENCE_PROOF": _bad("teardown")
    _time(x["observed_at_utc"]); raw=_blob(root,gpu)
    _gpu_raw(raw); projection=_obj(x["gpu_observation"],{"sha256","byte_length","validated_projection"})
    if {"sha256":projection["sha256"],"byte_length":projection["byte_length"]}!={"sha256":sha256(raw).hexdigest(),"byte_length":len(raw)} or _obj(projection["validated_projection"],{"line_count","columns_per_line"})!={"line_count":1,"columns_per_line":5} or _obj(x["quiescence"],{"docker_containers","gpu_compute_apps","target_listener_present"})!={"docker_containers":0,"gpu_compute_apps":0,"target_listener_present":False}: _bad("quiescence")

def _trace_margin(raw:bytes,content:bytes)->Decimal:
    trace=_obj(parse_canonical(raw),{"schema_version","rows"})
    if trace["schema_version"]!=FULL_TRACE or type(trace["rows"])is not list or len(trace["rows"])<=20: _bad("trace")
    rows=trace["rows"]; emitted=bytearray()
    for n,row in enumerate(rows):
        row=_obj(row,{"token","bytes","logprob","top_logprobs"})
        if type(row["token"])is not str or type(row["bytes"])is not list or not row["bytes"] or any(type(v)is not int or not 0<=v<=255 for v in row["bytes"]) or type(row["top_logprobs"])is not list or len(row["top_logprobs"])!=20: _bad("trace row")
        score=_decimal(row["logprob"]); identities=set(); found=False
        for candidate in row["top_logprobs"]:
            candidate=_obj(candidate,{"token","bytes","logprob"})
            if type(candidate["token"])is not str or type(candidate["bytes"])is not list or not candidate["bytes"] or any(type(v)is not int or not 0<=v<=255 for v in candidate["bytes"]): _bad("candidate")
            key=(candidate["token"],bytes(candidate["bytes"]));
            if key in identities: _bad("candidate duplicate")
            identities.add(key)
            if key==(row["token"],bytes(row["bytes"])) and _decimal(candidate["logprob"])==score: found=True
        if not found: _bad("selected absent")
        if n<len(rows)-1: emitted.extend(row["bytes"])
    if rows[-1]["token"]!="<|im_end|>" or bytes(rows[-1]["bytes"])!=b"<|im_end|>" or bytes(emitted)!=content: _bad("trace alignment")
    prefix=b"".join(bytes(row["bytes"]) for row in rows[:20])
    if prefix!=PREFIX or sha256(prefix).hexdigest()!=PREFIX_SHA: _bad("fixed prefix")
    scores={}
    for candidate in rows[20]["top_logprobs"]:
        key=(candidate["token"],bytes(candidate["bytes"]))
        if key==(" indicates",b" indicates"):
            if type(candidate["logprob"])is not str: _bad("branch representation")
            scores["i"]=_decimal(candidate["logprob"])
        elif key==(" explicitly",b" explicitly"):
            if type(candidate["logprob"])is not str: _bad("branch representation")
            scores["e"]=_decimal(candidate["logprob"])
    if set(scores)!={"i","e"}: _bad("fixed candidates")
    return scores["i"]-scores["e"]
def _randomization(contents:dict[str,tuple[str,str]],margins:dict[str,tuple[Decimal,Decimal]],schedule:tuple[str,...])->dict[str,Any]:
    def stat(s:tuple[str,...])->tuple[int,Decimal]:
        enabled=Counter(); disabled=Counter(); em=Decimal(0); dm=Decimal(0)
        for i,orientation in enumerate(s,1):
            a,b=contents[f"P{i:02d}"]; ma,mb=margins[f"P{i:02d}"]
            if orientation=="ED": enabled[a]+=1; disabled[b]+=1; em+=ma; dm+=mb
            else: disabled[a]+=1; enabled[b]+=1; dm+=ma; em+=mb
        return sum(abs(enabled[x]-disabled[x]) for x in set(enabled)|set(disabled))//2,abs(em-dm)
    observed=stat(schedule); all_stats=[stat(s) for s in ALL_SCHEDULES]; cn=sum(x[0]>=observed[0] for x in all_stats); mn=sum(x[1]>=observed[1] for x in all_stats)
    label=ASSOCIATION if cn<=10 or mn<=10 else NO_ASSOCIATION
    return {"schema_version":"hswm-dgx-qcase024-mi2-launch-crossed-endpoint-family/v1","family_alpha":"0.05","endpoint_alpha":"0.025","multiplicity":"BONFERRONI_TWO_REGISTERED_ENDPOINTS","endpoints":[{"schema_version":"hswm-dgx-qcase024-mi2-launch-crossed-randomization/v1","endpoint":"CONTENT_TV","statistic":"T_content=1/2*sum_c|N_E,c-N_D,c|","observed_t":observed[0],"upper_tail_numerator":cn,"denominator":400,"p_value":f"{cn}/400","alpha":"0.025","reject_at_alpha":cn<=10,"schedule_domain_count":400,"interpretation":"FINITE_EXACT_RANDOMIZATION_ENDPOINT_NOT_MECHANISTIC_ATTRIBUTION"},{"schema_version":"hswm-dgx-qcase024-mi2-launch-crossed-randomization/v1","endpoint":"FIXED_BRANCH_MARGIN","statistic":"T_margin=abs(sum_E M_i-sum_D M_i)","observed_t":str(observed[1]),"upper_tail_numerator":mn,"denominator":400,"p_value":f"{mn}/400","alpha":"0.025","reject_at_alpha":mn<=10,"schedule_domain_count":400,"interpretation":"FINITE_EXACT_RANDOMIZATION_ENDPOINT_NOT_MECHANISTIC_ATTRIBUTION"}],"family_label":label,"missing_fixed_branch_margin":"INCONCLUSIVE_REQUIRED_TRACE_ENDPOINT_UNAVAILABLE_NO_POST_HOC_FALLBACK","claim_boundary":"FINITE_WINDOW_SHARP_NO_ARM_EFFECT_AND_NO_INTERFERENCE_NULL_ONLY"}

def _partial(root:Path,rows:list[dict[str,Any]],final:dict[str,Any],plan_sha:str,closure:dict[str,Any],order:list[dict[str,Any]],expected_argv:dict[str,list[str]],expected:list[str],marker:dict[str,Any],schema:dict[str,Any])->dict[str,Any]:
    """Replay the exact scheduled producer prefix and fail closed on drift."""
    _obj(final,_meta({"record_type","status","started_slots","successful_slots","failed_slots","failure_code","launches","retry","retry_allowed","terminal"}))
    started=final["started_slots"]; succeeded=final["successful_slots"]
    if final["record_type"]!="RUN_SEAL" or final["status"] not in {INCOMPLETE,UNAVAILABLE} or final["retry"]!="NONE" or final["retry_allowed"] is not False or final["terminal"]!="MI2_ROOT_SEALED_NO_RESUME_OR_REPLACEMENT" or type(started)is not int or type(succeeded)is not int or final["failed_slots"]!=1 or not 1<=started<=48 or succeeded!=started-1 or type(final["failure_code"])is not str or re.fullmatch(r"[A-Z][A-Z0-9_]*",final["failure_code"]) is None or type(final["launches"])is not list: _bad("partial seal")
    expected_status=UNAVAILABLE if final["failure_code"]=="MI2LOGPROBUNAVAILABLE" else INCOMPLETE
    if final["status"]!=expected_status: _bad("partial status")
    launch_count=(started+1)//2; failed_rep=1 if started%2 else 2
    cursor=3; summaries=[]; incarnations=set(); counted_started=counted_succeeded=0
    for launch_index,short in enumerate(order[:launch_count],1):
        core={"pair_id":short["pair_id"],"pair_orientation":short["pair_orientation"],"launch_position":short["launch_position"],"launch_index":short["absolute_launch_index"],"absolute_launch_parity":short["absolute_launch_parity"],"prior_arm":short["prior_arm"],"arm":short["arm"],"arm_code":short["arm_code"]}
        launch=rows[cursor]; cursor+=1
        _obj(launch,_meta({"record_type","pair_id","pair_orientation","launch_position","launch_index","absolute_launch_parity","prior_arm","arm","arm_code","service_identity","pre_boundary_attestation","observed_at_utc","retry","terminal"}))
        if launch["record_type"]!="LAUNCH_START" or any(launch[k]!=core[k] for k in core) or launch["retry"]!="NONE" or launch["terminal"]!="FRESH_SERVER_BOUND_BEFORE_R001_AND_R002": _bad("partial launch")
        service=_service(launch["service_identity"],core["arm"])
        if service["container_name"]!=f"hswm-mi2-{launch_index:02d}": _bad("partial container")
        incarnation=(service["observed"]["container_id_sha256"],service["observed"]["container_start_sha256"])
        if incarnation in incarnations: _bad("partial service reuse")
        incarnations.add(incarnation); _time(launch["observed_at_utc"])
        baseline=_boundary(root,launch["pre_boundary_attestation"],core,service,"PRE",0,expected_argv[core["arm"]],0)
        is_failed_launch=launch_index==launch_count; slots=failed_rep if is_failed_launch else 2; successful_here=0
        for rep,role in ((1,"PRIMARY"),(2,"SERIAL_DIAGNOSTIC")):
            if rep>slots: break
            start,terminal=rows[cursor],rows[cursor+1]; cursor+=2; counted_started+=1
            _obj(start,_meta({"record_type","pair_id","pair_orientation","launch_position","launch_index","absolute_launch_parity","prior_arm","arm","arm_code","attempt_id","replicate","role","request","response_schema","plan_sha256","pre_boundary_attestation","observed_at_utc","retry","terminal"}))
            if start["record_type"]!="START" or any(start[k]!=core[k] for k in core) or start["attempt_id"]!=expected[(launch_index-1)*2+rep-1] or start["replicate"]!=f"R{rep:03d}" or start["role"]!=role or start["request"]!=marker["request"] or start["response_schema"]!=marker["response_schema"] or start["plan_sha256"]!=plan_sha or start["retry"]!="NONE" or start["terminal"]!="DURABLY_VISIBLE_BEFORE_SINGLE_MI2_POST": _bad("partial start")
            _boundary(root,start["pre_boundary_attestation"],core,service,"PRE",rep-1,expected_argv[core["arm"]],baseline); _time(start["observed_at_utc"])
            _obj(terminal,_meta({"record_type","pair_id","pair_orientation","launch_position","launch_index","absolute_launch_parity","prior_arm","arm","arm_code","attempt_id","replicate","role","start_record_sha256","service_identity","observation","raw_envelope","model_content_utf8","structured_content_diagnostic","full_processed_logprob_trace","post_boundary_attestation","outcome","failure_code","observed_at_utc","duration_ns","retry","retry_allowed","terminal"}))
            common=(terminal["record_type"]=="TERMINAL" and all(terminal[k]==core[k] for k in core) and terminal["attempt_id"]==start["attempt_id"] and terminal["replicate"]==start["replicate"] and terminal["role"]==start["role"] and terminal["start_record_sha256"]==start["record_sha256"] and terminal["service_identity"]==service and terminal["retry"]=="NONE" and terminal["retry_allowed"] is False and terminal["terminal"]=="MI2_SLOT_CONSUMED_NO_RETRY_OR_REPLACEMENT" and type(terminal["duration_ns"])is int and terminal["duration_ns"]>=0)
            if not common: _bad("partial terminal")
            _time(terminal["observed_at_utc"]); is_failure=is_failed_launch and rep==failed_rep
            if is_failure:
                if terminal["outcome"]!="FAILED" or terminal["failure_code"]!=final["failure_code"] or any(terminal[k] is not None for k in ("model_content_utf8","structured_content_diagnostic","full_processed_logprob_trace")): _bad("partial failure")
                observation=terminal["observation"]
                if observation is not None:
                    observation=_obj(observation,{"status","response_content_type","provider_request_id"})
                    if type(observation["status"])is not int or observation["response_content_type"] is not None and (type(observation["response_content_type"])is not str or not observation["response_content_type"]) or observation["provider_request_id"] is not None and type(observation["provider_request_id"])is not str: _bad("partial failure observation")
                if terminal["raw_envelope"] is not None and observation is None or terminal["post_boundary_attestation"] is not None and terminal["raw_envelope"] is None: _bad("partial failure stage")
                if terminal["raw_envelope"] is not None: _blob(root,terminal["raw_envelope"])
                if terminal["post_boundary_attestation"] is not None: _boundary(root,terminal["post_boundary_attestation"],core,service,"POST",rep,expected_argv[core["arm"]],baseline)
            else:
                if terminal["outcome"]!="SUCCEEDED" or terminal["failure_code"] is not None: _bad("partial success")
                observation=_obj(terminal["observation"],{"status","response_content_type","provider_request_id"})
                if observation["status"]!=200 or observation["response_content_type"] is not None and (type(observation["response_content_type"])is not str or not observation["response_content_type"]) or observation["provider_request_id"] is not None and type(observation["provider_request_id"])is not str: _bad("partial observation")
                _boundary(root,terminal["post_boundary_attestation"],core,service,"POST",rep,expected_argv[core["arm"]],baseline)
                raw=_strict(_blob(root,terminal["raw_envelope"])); choices=raw.get("choices") if type(raw)is dict else None; usage=raw.get("usage") if type(raw)is dict else None
                if raw.get("model")!="qwen3.6-35b-a3b" or type(choices)is not list or len(choices)!=1 or type(choices[0])is not dict or choices[0].get("finish_reason")!="stop" or type(choices[0].get("message"))is not dict or type(choices[0]["message"].get("content"))is not str or type(usage)is not dict or any(type(usage.get(x))is not int or usage[x]<0 for x in ("prompt_tokens","completion_tokens","total_tokens")) or usage["prompt_tokens"]+usage["completion_tokens"]!=usage["total_tokens"]: _bad("partial response")
                content=choices[0]["message"]["content"].encode(); instance=_strict(content); validate_response_schema(schema,instance,instance=True)
                if _blob(root,terminal["model_content_utf8"])!=content or _blob(root,terminal["structured_content_diagnostic"])!=canonical_bytes(instance): _bad("partial content")
                trace=_blob(root,terminal["full_processed_logprob_trace"])
                if type(choices[0].get("logprobs"))is not dict or canonical_bytes({"schema_version":FULL_TRACE,"rows":choices[0]["logprobs"].get("content")})!=trace: _bad("partial trace")
                _trace_margin(trace,content); successful_here+=1; counted_succeeded+=1
        teardown=rows[cursor]; cursor+=1
        _obj(teardown,_meta({"record_type","pair_id","pair_orientation","launch_position","launch_index","absolute_launch_parity","prior_arm","arm","arm_code","service_identity","teardown_attestation","gpu_observation_raw","observed_at_utc","duration_ns","terminal"}))
        if teardown["record_type"]!="LAUNCH_TEARDOWN" or any(teardown[k]!=core[k] for k in core) or teardown["service_identity"]!=service or teardown["terminal"]!="FRESH_LAUNCH_QUIESCED_BEFORE_NEXT_LAUNCH" or type(teardown["duration_ns"])is not int or teardown["duration_ns"]<0: _bad("partial teardown")
        _time(teardown["observed_at_utc"]); _teardown(root,teardown["teardown_attestation"],teardown["gpu_observation_raw"],core)
        seal=rows[cursor]; cursor+=1
        _obj(seal,_meta({"record_type","pair_id","pair_orientation","launch_position","launch_index","absolute_launch_parity","prior_arm","arm","arm_code","service_identity","started_slots","successful_slots","final_boundary_attestation","launch_teardown_record_sha256","observed_at_utc","duration_ns","retry","terminal"}))
        final_boundary=None if is_failed_launch else seal["final_boundary_attestation"]
        if seal["record_type"]!="LAUNCH_SEAL" or any(seal[k]!=core[k] for k in core) or seal["service_identity"]!=service or seal["started_slots"]!=slots or seal["successful_slots"]!=successful_here or seal["final_boundary_attestation"]!=final_boundary or seal["launch_teardown_record_sha256"]!=teardown["record_sha256"] or seal["retry"]!="NONE" or seal["terminal"]!="FRESH_LAUNCH_SEALED_NO_REUSE" or type(seal["duration_ns"])is not int or seal["duration_ns"]<0: _bad("partial launch seal")
        _time(seal["observed_at_utc"])
        if final_boundary is not None: _boundary(root,final_boundary,core,service,"FINAL",2,expected_argv[core["arm"]],baseline)
        summaries.append({**core,"service_identity":service,"started_slots":slots,"successful_slots":successful_here,"final_boundary_attestation":final_boundary,"launch_teardown_record_sha256":teardown["record_sha256"]})
    if cursor!=len(rows)-1 or counted_started!=started or counted_succeeded!=succeeded or final["launches"]!=summaries: _bad("partial launches")
    receipt_path=root/"receipt.json"
    if receipt_path.is_symlink() or not receipt_path.is_file(): _bad("partial receipt")
    receipt=_obj(parse_canonical(receipt_path.read_bytes()),{"schema_version","plan_sha256","ledger","content_manifest_sha256","status","started_slots","successful_slots","failed_slots","terminal"})
    ledger=(root/"mi2_ledger.jsonl").read_bytes(); names=sorted(x.name for x in (root/"content").iterdir() if x.is_file() and not x.is_symlink()); refs:set[str]=set()
    for row in rows: _descriptors(row,refs)
    _descriptors(closure,refs)
    if set(names)!=refs or receipt["schema_version"]!="hswm-dgx-mi2-launch-crossed-content-addressed-receipt/v1" or receipt["plan_sha256"]!=plan_sha or receipt["ledger"]!={"sha256":sha256(ledger).hexdigest(),"byte_length":len(ledger)} or receipt["content_manifest_sha256"]!=canonical_sha256(names) or receipt["status"]!=final["status"] or (receipt["started_slots"],receipt["successful_slots"],receipt["failed_slots"])!=(final["started_slots"],final["successful_slots"],final["failed_slots"]) or receipt["terminal"]!="MI2_ROOT_SEALED_NO_RESUME_OR_REPLACEMENT": _bad("partial receipt")
    return {"terminal":final["status"],"plan_sha256":plan_sha}

def verify(root:Path,*,external_registry_root:Path|None=None)->dict[str,Any]:
    try:
        rows=_ledger(root); global_row,burn,marker=rows[:3]
        _obj(global_row,_meta({"record_type","attestation","gpu_observation_raw","observed_at_utc","terminal"}))
        if global_row["record_type"]!="GLOBAL_QUIESCENCE" or global_row["terminal"]!="SHARED_DGX_QUIESCENT_BEFORE_PLAN_CONSUMPTION": _bad("global quiescence")
        _time(global_row["observed_at_utc"])
        global_gpu=_blob(root,global_row["gpu_observation_raw"]); _gpu_raw(global_gpu)
        global_attestation=_obj(parse_canonical(_blob(root,global_row["attestation"])),{"schema_version","gpu_uuid","endpoint","observed_at_utc","gpu_observation","quiescence","terminal"})
        gpu_projection=_obj(global_attestation["gpu_observation"],{"sha256","byte_length","validated_projection"})
        if global_attestation["schema_version"]!="hswm-dgx-mi2-global-quiescence/v1" or global_attestation["gpu_uuid"]!="GPU-ffed5bca-3452-8e9e-03fb-b2a4d8f40bc5" or global_attestation["endpoint"]!="http://127.0.0.1:18080/v1/chat/completions" or global_attestation["terminal"]!="PRE_BURN_SHARED_DGX_QUIESCENCE_NOT_NO_INTERFERENCE_PROOF" or {"sha256":gpu_projection["sha256"],"byte_length":gpu_projection["byte_length"]}!={"sha256":sha256(global_gpu).hexdigest(),"byte_length":len(global_gpu)} or _obj(gpu_projection["validated_projection"],{"line_count","columns_per_line"})!={"line_count":1,"columns_per_line":5} or _obj(global_attestation["quiescence"],{"docker_containers","gpu_compute_apps","target_listener_present"})!={"docker_containers":0,"gpu_compute_apps":0,"target_listener_present":False}: _bad("global quiescence data")
        _time(global_attestation["observed_at_utc"])
        _obj(burn,_meta({"record_type","plan_sha256","closure_manifest_sha256","consumption","registry_path","retry","terminal"})); _obj(marker,_meta({"record_type","plan","marker","closure_manifest","schedule_seed","root_genesis","request","response_schema","identities","provenance","publication","request_bindings","all_48_request_bindings_durable","retry","terminal"}))
        if burn["record_type"]!="PLAN_CONSUMPTION" or marker["record_type"]!="MI2_MARKER" or burn["retry"]!=marker["retry"]!="NONE": _bad("root")
        plan_raw=_blob(root,marker["plan"]); plan=parse_canonical(plan_raw); plan_sha=sha256(plan_raw).hexdigest()
        if type(plan)is not dict or plan.get("schema_version")!=PLAN_SCHEMA or plan.get("namespace")!=NAMESPACE or burn["plan_sha256"]!=plan_sha: _bad("plan")
        closure_raw=_blob(root,marker["closure_manifest"]); closure=_obj(parse_canonical(closure_raw),{"schema_version","namespace","artifacts"})
        if closure["schema_version"]!=FREEZE_SCHEMA or closure["namespace"]!=NAMESPACE or burn["closure_manifest_sha256"]!=sha256(closure_raw).hexdigest(): _bad("closure")
        frozen={x.get("path"):x for x in closure["artifacts"] if type(x)is dict and set(x)=={"path","sha256","byte_length"}}
        if len(frozen)!=len(closure["artifacts"]): _bad("closure items")
        identity_names=("endpoint_sha256","model_identity_sha256","runtime_identity_sha256","tls_identity_sha256","declared_isolation_contract_sha256","model_snapshot_manifest_sha256")
        expected_closure={"plan.json","start_marker.json","schedule_seed_material.json","root_genesis.json","request.json","materials/QCASE-024/response_schema.json","materials/QCASE-024/instruction.txt","materials/QCASE-024/model_input.json","materials/QCASE-024/rng.bin","provenance/source_ci_receipt_sha256.json","provenance/verifier_ci_receipt_sha256.json","provenance/verifier_build_output_sha256.json"}|{f"identities/{arm}/{name}.json" for arm in ARMS for name in identity_names}
        if set(frozen)!=expected_closure: _bad("closure set")
        def join(path:str,desc:Any)->bytes:
            item=_desc(desc)
            if frozen.get(path)!={"path":path,**item}: _bad("closure join")
            return _blob(root,item)
        # A closure is not merely a few convenient joins: every frozen byte
        # must be present and hash-addressed in the evidence root.
        for path,item in frozen.items():
            if type(path) is not str or not path or path.startswith("/") or ".." in path.split("/"):
                _bad("closure path")
            _blob(root,{"sha256":item["sha256"],"byte_length":item["byte_length"]})
        seed_raw=join("schedule_seed_material.json",marker["schedule_seed"]); schedule_index,schedule=_schedule(seed_raw); order=_order(schedule)
        for path,desc in (("plan.json",marker["plan"]),("start_marker.json",marker["marker"]),("root_genesis.json",marker["root_genesis"]),("request.json",marker["request"]),("materials/QCASE-024/response_schema.json",marker["response_schema"])): join(path,desc)
        select=_obj(plan.get("schedule_selection"),{"method","seed_material_sha256","schedule_index","schedule","schedule_domain_count"})
        plan_keys={"schema_version","namespace","instrument_id","source","runner_version","material","request_sha256","post_result_selection","arms","schedule_selection","block_order","attempt_ids","replicates_per_launch","fresh_launches","primary_posts","budget","zero_retry","no_refill_resume_or_early_stop","consumption_registry","randomization","verifier","evidence_root_genesis_sha256","allowed_terminals","nonclaims"}
        if set(plan)!=plan_keys or select["method"]!="RAW_CSPRNG_256_BIT_INTEGER_REJECTION_SAMPLING_400_THEN_EXPLICIT_ED_DE_LEXICOGRAPHIC_SCHEDULE" or select["schedule_index"]!=schedule_index or select["schedule"]!=list(schedule) or select["schedule_domain_count"]!=400 or select["seed_material_sha256"]!=sha256(seed_raw).hexdigest() or plan.get("block_order")!=order or plan.get("budget")!=48 or plan.get("fresh_launches")!=24 or plan.get("primary_posts")!=24 or plan.get("replicates_per_launch")!=2 or plan.get("zero_retry") is not True or plan.get("no_refill_resume_or_early_stop") is not True or plan.get("consumption_registry")!=REGISTRY or plan.get("randomization")!=RANDOMIZATION or plan.get("allowed_terminals")!=[COMPLETE,INCOMPLETE,UNAVAILABLE,VOID] or plan.get("nonclaims")!=list(NONCLAIMS): _bad("schedule/plan")
        if plan["instrument_id"]!="DNRD5-QCASE024-MI-2-LAUNCH-CROSSED-V1" or plan["runner_version"]!="hswm-dgx-qcase024-mi2-launch-crossed-runner/v1" or plan["request_sha256"]!=EXPECTED_REQUEST or plan["post_result_selection"]!=EXPECTED_MI1 or plan["material"]!={"case_id":"QCASE-024","instruction_sha256":EXPECTED_MATERIAL["instruction.txt"],"model_input_sha256":EXPECTED_MATERIAL["model_input.json"],"response_schema_sha256":EXPECTED_MATERIAL["response_schema.json"],"rng_sha256":EXPECTED_MATERIAL["rng.bin"],"max_output_tokens":256}: _bad("static plan")
        source=_source(plan["source"]); verifier=_obj(plan["verifier"],{"source","build_output_sha256"}); verifier_source=_source(verifier["source"]); _digest(verifier["build_output_sha256"])
        expected_argv=_arm_identities(root,marker,plan,join)
        expected=[f"MI2-{x['pair_id']}-{x['arm_code']}-R{r:03d}" for x in order for r in (1,2)]
        if plan.get("attempt_ids")!=expected or marker["all_48_request_bindings_durable"] is not True or marker["request_bindings"]!=[{"attempt_id":x,"request":marker["request"]} for x in expected]: _bad("request bindings")
        marker_raw=join("start_marker.json",marker["marker"])
        expected_marker=canonical_bytes({"schema_version":"hswm-dgx-qcase024-mi2-launch-crossed-start-marker/v1","namespace":NAMESPACE,"plan_sha256":plan_sha,"request_sha256":plan["request_sha256"],"seed_material_sha256":sha256(seed_raw).hexdigest(),"scheduled_attempts":expected,"terminal":"ALL_48_SERIALIZED_POSTS_AND_PRIMARY_RANDOMIZATION_BOUND_BEFORE_LIVE_START","nonclaims":list(NONCLAIMS)})
        if marker_raw!=expected_marker: _bad("start marker")
        request=join("request.json",marker["request"]); schema_raw=join("materials/QCASE-024/response_schema.json",marker["response_schema"])
        if sha256(request).hexdigest()!=plan.get("request_sha256"): _bad("request")
        if sha256(join("root_genesis.json",marker["root_genesis"])).hexdigest()!=plan.get("evidence_root_genesis_sha256"):
            _bad("genesis")
        for name,digest in (("instruction.txt",plan["material"]["instruction_sha256"]),("model_input.json",plan["material"]["model_input_sha256"]),("response_schema.json",plan["material"]["response_schema_sha256"]),("rng.bin",plan["material"]["rng_sha256"])):
            descriptor = marker["response_schema"] if name=="response_schema.json" else {
                "sha256": frozen["materials/QCASE-024/"+name]["sha256"],
                "byte_length": frozen["materials/QCASE-024/"+name]["byte_length"],
            }
            if sha256(join("materials/QCASE-024/"+name, descriptor)).hexdigest()!=digest:
                _bad("material")
        schema=parse_canonical(schema_raw); validate_response_schema(schema)
        provenance=marker["provenance"]
        if type(provenance)is not dict or set(provenance)!={"source_ci_receipt_sha256","verifier_ci_receipt_sha256","verifier_build_output_sha256"}: _bad("provenance")
        for name in provenance: join("provenance/"+name+".json",provenance[name])
        for source,receipt_name in ((plan.get("source"),"source_ci_receipt_sha256"),(plan.get("verifier",{}).get("source"),"verifier_ci_receipt_sha256")):
            if type(source)is not dict: _bad("source")
            receipt_raw=_blob(root,provenance[receipt_name])
            if sha256(receipt_raw).hexdigest()!=source["ci_receipt_sha256"]: _bad("ci digest")
            parse_github_actions_ci_receipt(receipt_raw,repository="gj3447/HSWM",commit=source["commit"],tree=source["tree"])
        build=_obj(parse_canonical(_blob(root,provenance["verifier_build_output_sha256"])),{"schema_version","source_path","source_sha256","source_utf8","imports","terminal"})
        if sha256(_blob(root,provenance["verifier_build_output_sha256"])).hexdigest()!=plan["verifier"]["build_output_sha256"] or build["schema_version"]!="hswm-dgx-qcase024-mi2-launch-crossed-independent-verifier-build/v1" or build["terminal"]!="MI2_INDEPENDENT_VERIFIER_SOURCE_AND_IMPORTS_BOUND" or build["source_path"]!="_research/dgx_mi2/independent_verifier.py" or type(build["imports"])is not list or sha256(build["source_utf8"].encode()).hexdigest()!=build["source_sha256"] or sha256(Path(__file__).read_bytes()).hexdigest()!=build["source_sha256"] or any(type(x)is not str or x.startswith("_research.dgx_mi2") for x in build["imports"]): _bad("build")
        publication=_obj(marker["publication"],{"commit","tree","ci_receipt"}); parse_github_actions_ci_receipt(_blob(root,publication["ci_receipt"]),repository="gj3447/HSWM",commit=publication["commit"],tree=publication["tree"])
        consumption=_blob(root,burn["consumption"])
        consumption_value=_obj(parse_canonical(consumption),{"schema_version","plan_sha256","closure_manifest_sha256","evidence_root","registry_path","terminal"})
        if burn["registry_path"]!=REGISTRY["path"] or burn["terminal"]!="DURABLE_PLAN_BURN_BEFORE_ANY_MI2_TARGET_LAUNCH" or consumption_value!={"schema_version":"hswm-dgx-mi2-launch-crossed-plan-consumption/v1","plan_sha256":plan_sha,"closure_manifest_sha256":sha256(closure_raw).hexdigest(),"evidence_root":str(root),"registry_path":REGISTRY["path"],"terminal":"PLAN_BURNED_BEFORE_ANY_MI2_TARGET_LAUNCH_NO_REUSE"}: _bad("consumption")
        if external_registry_root is not None:
            target=external_registry_root/(plan_sha+".consumed")
            if target.is_symlink() or not target.is_file() or target.read_bytes()!=consumption: _bad("external burn")
        final=rows[-1]
        if final.get("record_type")!="RUN_SEAL": _bad("seal")
        if final.get("status") in {INCOMPLETE,UNAVAILABLE}:
            return _partial(root,rows,final,plan_sha,closure,order,expected_argv,expected,marker,schema)
        if final.get("status")!=COMPLETE: _bad("seal")
        if external_registry_root is None: _bad("complete requires external registry")
        target=external_registry_root/(plan_sha+".consumed")
        if target.is_symlink() or not target.is_file() or target.read_bytes()!=consumption: _bad("external burn")
        cursor=3; incarnations=set(); contents={}; margins={}; summaries=[]
        for launch_index,short in enumerate(order,1):
            core={"pair_id":short["pair_id"],"pair_orientation":short["pair_orientation"],"launch_position":short["launch_position"],"launch_index":short["absolute_launch_index"],"absolute_launch_parity":short["absolute_launch_parity"],"prior_arm":short["prior_arm"],"arm":short["arm"],"arm_code":short["arm_code"]}; launch=rows[cursor]; cursor+=1
            _obj(launch,_meta({"record_type","pair_id","pair_orientation","launch_position","launch_index","absolute_launch_parity","prior_arm","arm","arm_code","service_identity","pre_boundary_attestation","observed_at_utc","retry","terminal"}))
            if launch["record_type"]!="LAUNCH_START" or any(launch[k]!=core[k] for k in core) or launch["retry"]!="NONE": _bad("launch")
            service=_service(launch["service_identity"],core["arm"])
            if service["container_name"]!=f"hswm-mi2-{launch_index:02d}": _bad("container")
            incarnation=(service["observed"]["container_id_sha256"],service["observed"]["container_start_sha256"])
            if incarnation in incarnations: _bad("service reuse")
            incarnations.add(incarnation); _time(launch["observed_at_utc"]); baseline=_boundary(root,launch["pre_boundary_attestation"],core,service,"PRE",0,expected_argv[core["arm"]],0); values=[]; ms=[]
            for rep,role in ((1,"PRIMARY"),(2,"SERIAL_DIAGNOSTIC")):
                start,terminal=rows[cursor],rows[cursor+1]; cursor+=2
                _obj(start,_meta({"record_type","pair_id","pair_orientation","launch_position","launch_index","absolute_launch_parity","prior_arm","arm","arm_code","attempt_id","replicate","role","request","response_schema","plan_sha256","pre_boundary_attestation","observed_at_utc","retry","terminal"}))
                if start["record_type"]!="START" or any(start[k]!=core[k] for k in core) or start["attempt_id"]!=expected[(launch_index-1)*2+rep-1] or start["replicate"]!=f"R{rep:03d}" or start["role"]!=role or start["request"]!=marker["request"] or start["response_schema"]!=marker["response_schema"] or start["plan_sha256"]!=plan_sha or start["retry"]!="NONE": _bad("start")
                _boundary(root,start["pre_boundary_attestation"],core,service,"PRE",rep-1,expected_argv[core["arm"]],baseline); _time(start["observed_at_utc"])
                _obj(terminal,_meta({"record_type","pair_id","pair_orientation","launch_position","launch_index","absolute_launch_parity","prior_arm","arm","arm_code","attempt_id","replicate","role","start_record_sha256","service_identity","observation","raw_envelope","model_content_utf8","structured_content_diagnostic","full_processed_logprob_trace","post_boundary_attestation","outcome","failure_code","observed_at_utc","duration_ns","retry","retry_allowed","terminal"}))
                if terminal["record_type"]!="TERMINAL" or any(terminal[k]!=core[k] for k in core) or terminal["attempt_id"]!=start["attempt_id"] or terminal["replicate"]!=start["replicate"] or terminal["role"]!=start["role"] or terminal["start_record_sha256"]!=start["record_sha256"] or terminal["service_identity"]!=service or terminal["retry"]!="NONE" or terminal["retry_allowed"] is not False or terminal["outcome"]!="SUCCEEDED" or terminal["failure_code"] is not None or terminal["terminal"]!="MI2_SLOT_CONSUMED_NO_RETRY_OR_REPLACEMENT" or type(terminal["duration_ns"])is not int or terminal["duration_ns"]<0: _bad("terminal")
                _time(terminal["observed_at_utc"])
                observation=_obj(terminal["observation"],{"status","response_content_type","provider_request_id"})
                if observation["status"]!=200 or observation["response_content_type"] is not None and (type(observation["response_content_type"])is not str or not observation["response_content_type"]) or observation["provider_request_id"] is not None and type(observation["provider_request_id"])is not str: _bad("observation")
                _boundary(root,terminal["post_boundary_attestation"],core,service,"POST",rep,expected_argv[core["arm"]],baseline); raw=_blob(root,terminal["raw_envelope"]); response=_strict(raw); choices=response.get("choices") if type(response)is dict else None; usage=response.get("usage") if type(response)is dict else None
                if response.get("model")!="qwen3.6-35b-a3b" or type(choices)is not list or len(choices)!=1 or type(choices[0])is not dict or choices[0].get("finish_reason")!="stop" or type(choices[0].get("message"))is not dict or type(choices[0]["message"].get("content"))is not str or type(usage)is not dict or any(type(usage.get(x))is not int or usage[x]<0 for x in ("prompt_tokens","completion_tokens","total_tokens")) or usage["prompt_tokens"]+usage["completion_tokens"]!=usage["total_tokens"]: _bad("response")
                content=choices[0]["message"]["content"].encode(); instance=_strict(content); validate_response_schema(schema,instance,instance=True)
                if _blob(root,terminal["model_content_utf8"])!=content or _blob(root,terminal["structured_content_diagnostic"])!=canonical_bytes(instance): _bad("content")
                trace_raw=_blob(root,terminal["full_processed_logprob_trace"])
                if type(choices[0].get("logprobs")) is not dict or canonical_bytes({"schema_version":FULL_TRACE,"rows":choices[0]["logprobs"].get("content")}) != trace_raw: _bad("trace projection")
                values.append(terminal["model_content_utf8"]["sha256"]); ms.append(_trace_margin(trace_raw,content))
            teardown=rows[cursor]; cursor+=1; _obj(teardown,_meta({"record_type","pair_id","pair_orientation","launch_position","launch_index","absolute_launch_parity","prior_arm","arm","arm_code","service_identity","teardown_attestation","gpu_observation_raw","observed_at_utc","duration_ns","terminal"}))
            if teardown["record_type"]!="LAUNCH_TEARDOWN" or any(teardown[k]!=core[k] for k in core) or teardown["service_identity"]!=service or teardown["terminal"]!="FRESH_LAUNCH_QUIESCED_BEFORE_NEXT_LAUNCH" or type(teardown["duration_ns"])is not int or teardown["duration_ns"]<0: _bad("teardown")
            _time(teardown["observed_at_utc"])
            _teardown(root,teardown["teardown_attestation"],teardown["gpu_observation_raw"],core)
            seal=rows[cursor]; cursor+=1; _obj(seal,_meta({"record_type","pair_id","pair_orientation","launch_position","launch_index","absolute_launch_parity","prior_arm","arm","arm_code","service_identity","started_slots","successful_slots","final_boundary_attestation","launch_teardown_record_sha256","observed_at_utc","duration_ns","retry","terminal"}))
            if seal["record_type"]!="LAUNCH_SEAL" or any(seal[k]!=core[k] for k in core) or seal["service_identity"]!=service or (seal["started_slots"],seal["successful_slots"],seal["retry"])!=(2,2,"NONE") or seal["terminal"]!="FRESH_LAUNCH_SEALED_NO_REUSE" or seal["launch_teardown_record_sha256"]!=teardown["record_sha256"] or type(seal["duration_ns"])is not int or seal["duration_ns"]<0: _bad("launch seal")
            _time(seal["observed_at_utc"])
            _boundary(root,seal["final_boundary_attestation"],core,service,"FINAL",2,expected_argv[core["arm"]],baseline); contents.setdefault(core["pair_id"],[]).append(values[0]); margins.setdefault(core["pair_id"],[]).append(ms[0])
            summaries.append({**core,"service_identity":service,"started_slots":2,"successful_slots":2,"final_boundary_attestation":seal["final_boundary_attestation"],"launch_teardown_record_sha256":teardown["record_sha256"]})
        _obj(final,_meta({"record_type","status","started_slots","successful_slots","failed_slots","failure_code","launches","retry","retry_allowed","terminal"}))
        if cursor!=len(rows)-1 or len(incarnations)!=24 or (final.get("started_slots"),final.get("successful_slots"),final.get("failed_slots"),final.get("retry"),final.get("retry_allowed"))!=(48,48,0,"NONE",False) or final["failure_code"] is not None or final["terminal"]!="MI2_ROOT_SEALED_NO_RESUME_OR_REPLACEMENT" or final["launches"]!=summaries: _bad("final")
        receipt_path=root/"receipt.json"
        if receipt_path.is_symlink() or not receipt_path.is_file(): _bad("receipt")
        receipt=_obj(parse_canonical(receipt_path.read_bytes()),{"schema_version","plan_sha256","ledger","content_manifest_sha256","status","started_slots","successful_slots","failed_slots","terminal"})
        names=sorted(item.name for item in (root/"content").iterdir() if item.is_file() and not item.is_symlink())
        referenced:set[str]=set()
        for row in rows: _descriptors(row,referenced)
        _descriptors(closure,referenced)
        if set(names)!=referenced: _bad("content reachability")
        if receipt["schema_version"]!="hswm-dgx-mi2-launch-crossed-content-addressed-receipt/v1" or receipt["plan_sha256"]!=plan_sha or _desc(receipt["ledger"])!={"sha256":sha256((root/"mi2_ledger.jsonl").read_bytes()).hexdigest(),"byte_length":len((root/"mi2_ledger.jsonl").read_bytes())} or receipt["content_manifest_sha256"]!=canonical_sha256(names) or receipt["status"]!=COMPLETE or (receipt["started_slots"],receipt["successful_slots"],receipt["failed_slots"])!=(48,48,0) or receipt["terminal"]!="MI2_ROOT_SEALED_NO_RESUME_OR_REPLACEMENT": _bad("receipt")
        result=_randomization({k:tuple(v) for k,v in contents.items()},{k:tuple(v) for k,v in margins.items()},schedule)
        result.update({"terminal":COMPLETE,"plan_sha256":plan_sha,"ledger_sha256":sha256((root/"mi2_ledger.jsonl").read_bytes()).hexdigest(),"ledger_final_record_sha256":final["record_sha256"],"primary_unit":"R001_FRESH_LAUNCH_ONLY","serial_diagnostic":"R002_EXCLUDED_FROM_RANDOMIZATION_N"})
        return result
    except Exception: return {"terminal":VOID}

def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--root",required=True); parser.add_argument("--external-registry-root",required=True); parser.add_argument("--output"); args=parser.parse_args(argv); result=verify(Path(args.root),external_registry_root=Path(args.external_registry_root)); raw=canonical_bytes(result)
    if args.output:
        target=Path(args.output); target.parent.mkdir(parents=True,exist_ok=True); fd,tmp=tempfile.mkstemp(prefix=".mi2-verifier-",dir=target.parent)
        try:
            with os.fdopen(fd,"wb") as handle: handle.write(raw); handle.flush(); os.fsync(handle.fileno())
            os.replace(tmp,target)
        finally:
            try: os.unlink(tmp)
            except FileNotFoundError: pass
    else: print(raw.decode())
    return 2 if result["terminal"]==VOID else 0

__all__=["ASSOCIATION","COMPLETE","INCOMPLETE","NO_ASSOCIATION","UNAVAILABLE","VOID","verify"]

if __name__=="__main__":
    raise SystemExit(main())
