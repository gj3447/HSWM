"""Independent, fail-closed reader for the DGX Q1 attempt ledger.

It deliberately imports neither the Q1 producer nor the runner.
"""
from __future__ import annotations
from collections import Counter
from hashlib import sha256
from datetime import datetime, timezone
import ast, base64, json, re
from pathlib import Path
from typing import Any
from _research.dnrd5.canonical_json import canonical_bytes, canonical_sha256, parse_canonical

PLAN="hswm-dgx-q1-live-response-exactness/v1"; MARKER="hswm-dgx-q1-live-start-marker/v1"
LEDGER="hswm-dgx-q1-live-attempt-ledger/v1"; BOUNDARY="hswm-dgx-q1-live-boundary-attestation/v1"
NS="DNRD5-Q1-LIVE-QUALIFICATION-ONLY/v1"; RUNNER="hswm-dgx-q1-live-runner/v1"
REPRODUCED="LIVE_REPRODUCED_EXACT_ASSISTANT_CONTENT_UTF8_ON_FROZEN_Q1"; FALSIFIED="LIVE_FALSIFIED_EXACT_ASSISTANT_CONTENT_UTF8_ON_FROZEN_Q1"
INCONCLUSIVE="INCONCLUSIVE_LIVE_Q1_EVIDENCE"; VOID="VOID_LIVE_Q1_PROTOCOL_LEDGER_HASH_ORDER_OR_BOUNDARY_BREACH"
TEST_REPRODUCED="TEST_ONLY_REPRODUCED_EXACT_ASSISTANT_CONTENT_UTF8_ON_FIXTURE_Q1"; TEST_FALSIFIED="TEST_ONLY_FALSIFIED_EXACT_ASSISTANT_CONTENT_UTF8_ON_FIXTURE_Q1"; TEST_INCONCLUSIVE="TEST_ONLY_INCONCLUSIVE_Q1_FIXTURE_EVIDENCE"
TERMINALS=(REPRODUCED,FALSIFIED,INCONCLUSIVE,VOID)
NONCLAIMS=("NOT_A_DNRD5_300_BLOCK_OCCURRENCE_CALL_OR_PILOT_EFFECT_DATA","NOT_SOURCE_A_AUTHORIZATION_OR_SOURCE_A_FREEZE","NOT_PROOF_OF_PROVIDER_INTERNAL_CACHE_SCHEDULING_OR_GLOBAL_DETERMINISM","NOT_PROOF_OF_NO_INTERFERENCE_OR_HSWM_CAUSAL_LEARNING","NOT_PROOF_OF_CONSCIOUSNESS_SELFHOOD_OR_SCALE_INVARIANT_CAUSAL_CLOSURE")
CLASSES=("PRE_OUTCOME_TRAJECTORY","REVISION_PROPOSAL","FRESH_PROBE")
SYSTEM="Act only as the bounded DNRD-5 token-native model function. Read the declared public synthetic input, follow its instruction, and return exactly one object satisfying the supplied strict JSON schema."
REGISTRY={"schema_version":"hswm-dgx-q1-plan-consumption-registry/v1","path":"/mnt/hswm/evidence/hswm-dnrd5-q1-live-consumption-v1","scope":"PINNED_DGX_NODE_LOCAL_DURABLE_PLAN_HASH_REGISTRY","boundary":"NODE_LOCAL_PATH_BINDING_NOT_DISTRIBUTED_GLOBAL_CONSENSUS","terminal":"ONE_DURABLE_BURN_PER_PLAN_HASH_AT_THE_DECLARED_PATH"}
Z="0"*64; SHA=re.compile(r"^[0-9a-f]{64}$"); GIT=re.compile(r"^[0-9a-f]{40}$"); CASE=re.compile(r"^QCASE-[0-9]{3}$"); ATT=re.compile(r"^DNRD5-Q1L-([0-9]{3})-R(00[1-4])$")
def bad(x="breach"): raise ValueError(x)
def obj(x,k):
 if type(x)is not dict or set(x)!=k: bad("keyset")
 return x
def digest(x):
 if type(x)is not str or SHA.fullmatch(x)is None or x==Z: bad("digest")
 return x
def can(b):
 try:return parse_canonical(b)
 except Exception as e: raise ValueError("canonical") from e
def strict(b):
 def pairs(xs):
  d={}
  for k,v in xs:
   if k in d: bad("duplicate")
   d[k]=v
  return d
 try:return json.loads(b.decode("utf8","strict"),object_pairs_hook=pairs,parse_constant=lambda _:bad("nonfinite"))
 except (UnicodeDecodeError,json.JSONDecodeError,RecursionError) as e:raise ValueError("json") from e
def blob(r,d):
 d=obj(d,{"sha256","byte_length"}); h=digest(d["sha256"])
 if type(d["byte_length"])is not int or not 0<=d["byte_length"]<=16*1024*1024:bad("length")
 p=r/"content"/h
 if p.is_symlink() or not p.is_file():bad("nonregular blob")
 b=p.read_bytes()
 if len(b)!=d["byte_length"] or sha256(b).hexdigest()!=h:bad("blob")
 return b
def source(x):
 x=obj(x,{"commit","tree","ci_receipt_sha256","ci_terminal"})
 if any(type(x[k])is not str or GIT.fullmatch(x[k])is None or x[k]=="0"*40 for k in ("commit","tree")) or x["ci_terminal"]!="FIRST_ATTEMPT_SUCCESSFUL_CI_BUILD":bad("source")
 digest(x["ci_receipt_sha256"])
def _ci_input(d):
 d=obj(d,{"sha256","byte_length","base64"});digest(d["sha256"])
 if type(d["byte_length"])is not int or d["byte_length"]<1 or type(d["base64"])is not str:bad("ci input")
 try:b=base64.b64decode(d["base64"],validate=True)
 except Exception:bad("ci base64")
 if base64.b64encode(b).decode("ascii")!=d["base64"]or len(b)!=d["byte_length"]or sha256(b).hexdigest()!=d["sha256"]:bad("ci input bytes")
 return b
def _ci_time(v):
 if type(v)is not str:bad("ci time")
 try:return int(datetime.strptime(v,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp())
 except ValueError:bad("ci time")
def _ci_run(x,s):
 if type(x)is not dict:bad("ci run")
 r=x.get("repository");h=x.get("head_repository");c=x.get("head_commit")
 if type(r)is not dict or type(h)is not dict or type(c)is not dict:bad("ci run nested")
 fields=("id","workflow_id","run_number","name","path","event","head_branch","head_sha","run_attempt","status","conclusion","created_at","run_started_at","updated_at","pull_requests")
 y={k:x.get(k)for k in fields};y|={"repository":{"id":r.get("id"),"full_name":r.get("full_name")},"head_repository":{"id":h.get("id"),"full_name":h.get("full_name")},"head_commit":{"id":c.get("id"),"tree_id":c.get("tree_id")}}
 if type(y["id"])is not int or y["id"]<=0 or type(y["workflow_id"])is not int or y["workflow_id"]<=0 or type(y["run_number"])is not int or y["run_number"]<=0 or y["name"]!="CI"or y["path"]!=".github/workflows/ci.yml"or(y["event"],y["head_branch"],y["head_sha"],y["run_attempt"],y["status"],y["conclusion"],y["pull_requests"])!=("push","main",s["commit"],1,"completed","success",[])or y["repository"]!=y["head_repository"]or y["repository"].get("full_name")!="gj3447/HSWM"or type(y["repository"].get("id"))is not int or y["repository"]["id"]<=0 or y["head_commit"]!={"id":s["commit"],"tree_id":s["tree"]}:bad("ci run semantics")
 a,b,c=(_ci_time(y[k])for k in("created_at","run_started_at","updated_at"))
 if not a<=b<=c:bad("ci chronology")
 return y
def _ci_jobs(x,run_id):
 if type(x)is not dict or x.get("query")!={"run_id":run_id,"per_page":100,"page":1}or type(x.get("jobs"))is not list or not x["jobs"]or x.get("total_count")!=len(x["jobs"])or len(x["jobs"])>100:bad("ci jobs")
 jobs=[]
 for j in x["jobs"]:
  if type(j)is not dict or type(j.get("name"))is not str or not j["name"]or j.get("status")!="completed"or j.get("conclusion")!="success":bad("ci job")
  jobs.append({"name":j["name"],"conclusion":"success"})
 jobs.sort(key=lambda q:q["name"])
 if len({q["name"]for q in jobs})!=len(jobs):bad("ci jobs unique")
 return jobs
def ci(raw,s):
 keys={"schema_version","provider","repository","commit","tree","workflow_run_id","run_attempt","event","head_branch","conclusion","jobs","jobs_sha256","evidence_inputs","query_contract","terminal","boundary"}
 x=obj(can(raw),keys);inputs=obj(x["evidence_inputs"],{"run_json","runs_list_json","jobs_json","workflow_metadata_json"})
 embedded={k:_ci_input(inputs[k])for k in("run_json","runs_list_json","jobs_json")}
 if inputs["workflow_metadata_json"]is not None:
  embedded["workflow_metadata_json"]=_ci_input(inputs["workflow_metadata_json"]);strict(embedded["workflow_metadata_json"])
 run_raw=strict(embedded["run_json"]);listing=strict(embedded["runs_list_json"]);jobs_raw=strict(embedded["jobs_json"])
 selected=_ci_run(run_raw,s)
 query={"workflow_path":".github/workflows/ci.yml","event":"push","branch":"main","head_sha":s["commit"],"per_page":100,"page":1}
 if type(listing)is not dict or listing.get("query")!=query or listing.get("total_count")!=1 or type(listing.get("workflow_runs"))is not list or len(listing["workflow_runs"])!=1 or _ci_run(listing["workflow_runs"][0],s)!=selected:bad("ci list")
 jobs=_ci_jobs(jobs_raw,selected["id"])
 qcontract={"workflow_runs":query,"jobs":{"run_id":selected["id"],"per_page":100,"page":1}}
 expected={"schema_version":"hswm-github-actions-first-success-ci-receipt/v1","provider":"github-actions","repository":"gj3447/HSWM","commit":s["commit"],"tree":s["tree"],"workflow_run_id":selected["id"],"run_attempt":1,"event":"push","head_branch":"main","conclusion":"success","jobs":jobs,"jobs_sha256":canonical_sha256(jobs),"evidence_inputs":inputs,"query_contract":qcontract,"terminal":"FIRST_ATTEMPT_SUCCESSFUL_CI_BUILD","boundary":"RAW_GITHUB_API_PROJECTION_NOT_CRYPTOGRAPHIC_PROVIDER_ATTESTATION"}
 if x!=expected or raw!=canonical_bytes(expected):bad("ci")
 return x
def verifier_build(raw):
 x=obj(can(raw),{"schema_version","source_path","source_sha256","source_utf8","imports","terminal"})
 if x["schema_version"]!="hswm-dgx-q1-independent-verifier-build/v1"or x["source_path"]!="_research/dgx_q1/independent_live_verifier.py"or type(x["source_utf8"])is not str or sha256(x["source_utf8"].encode()).hexdigest()!=x["source_sha256"]or type(x["imports"])is not list or x["imports"]!=sorted(set(x["imports"]))or x["terminal"]!="INDEPENDENT_VERIFIER_SOURCE_AND_IMPORTS_BOUND":bad("verifier build")
 try:tree=ast.parse(x["source_utf8"])
 except SyntaxError:bad("verifier syntax")
 imports=set()
 for node in ast.walk(tree):
  if isinstance(node,ast.Import):imports.update(a.name for a in node.names)
  elif isinstance(node,ast.ImportFrom)and node.module:imports.add(node.module)
 if sorted(imports)!=x["imports"]or imports&{"_research.dgx_q1.live_protocol","_research.dgx_q1.live_runner","_research.dgx_q1.live_launcher","_research.dgx_q1.live_preregistration"}:bad("verifier imports")
 if sha256(Path(__file__).read_bytes()).hexdigest()!=x["source_sha256"]:bad("verifier runtime source")
def schema(s,v=None,instance=False):
 if type(s)is not dict or s.get("type") not in {"object","array","string","integer","boolean","null"}:bad("schema")
 t=s["type"]
 if t=="object":
  if set(s)!={"type","properties","required","additionalProperties"} or type(s["properties"])is not dict or not s["properties"] or type(s["required"])is not list or set(s["required"])!=set(s["properties"]) or len(s["required"])!=len(set(s["required"])) or s["additionalProperties"] is not False:bad("object")
  for q in s["properties"].values():schema(q)
  if instance:
   if type(v)is not dict or set(v)!=set(s["properties"]):bad("object value")
   for k,q in s["properties"].items():schema(q,v[k],True)
 elif t=="array":
  if not {"type","items"}<=set(s)<={"type","items","minItems","maxItems"} or type(s["items"])is not dict or type(s.get("minItems",0))is not int or type(s.get("maxItems",65536))is not int or not 0<=s.get("minItems",0)<=s.get("maxItems",65536):bad("array")
  schema(s["items"])
  if instance:
   if type(v)is not list or not s.get("minItems",0)<=len(v)<=s.get("maxItems",65536):bad("array value")
   for q in v:schema(s["items"],q,True)
 elif t=="string":
  if not {"type"}<=set(s)<={"type","minLength","maxLength","pattern"} or type(s.get("minLength",0))is not int or type(s.get("maxLength",65536))is not int or not 0<=s.get("minLength",0)<=s.get("maxLength",65536) or ("pattern"in s and type(s["pattern"])is not str):bad("string")
  if instance and (type(v)is not str or not s.get("minLength",0)<=len(v)<=s.get("maxLength",65536) or ("pattern"in s and re.fullmatch(s["pattern"],v)is None)):bad("string value")
 elif t=="integer":
  if not {"type"}<=set(s)<={"type","minimum","maximum"} or type(s.get("minimum",-9007199254740991))is not int or type(s.get("maximum",9007199254740991))is not int:bad("int")
  if instance and (type(v)is not int or not s.get("minimum",-9007199254740991)<=v<=s.get("maximum",9007199254740991)):bad("int value")
 elif set(s)!={"type"} or (t=="boolean" and instance and type(v)is not bool) or (t=="null" and instance and v is not None):bad("scalar")
def order(a,seed):
 if len(a)!=96 or len(set(a))!=96 or len(seed)!=32 or any(ATT.fullmatch(x)is None for x in a):bad("order")
 a=list(a)
 for c,i in enumerate(range(95,0,-1)):
  h=sha256(b"HSWM-DGX-Q1-LIVE-CALL-ORDER-V1\0"+seed+c.to_bytes(8,"big")).digest();j=int.from_bytes(h[:8],"big")%(i+1);a[i],a[j]=a[j],a[i]
 return a
def plan(raw):
 p=obj(can(raw),{"schema_version","namespace","source","runner_version","corpus_manifest_sha256","corpus","replicates","call_order","call_order_algorithm","call_order_seed_hex","call_order_seed_sha256","budget","zero_retry","consumption_registry","identities","verifier","evidence_root_genesis_sha256","comparator","allowed_terminals","nonclaims"})
 if p["schema_version"]!=PLAN or p["namespace"]!=NS or p["runner_version"]!=RUNNER or (p["replicates"],p["budget"],p["zero_retry"])!=(4,96,True) or p["consumption_registry"]!=REGISTRY or p["call_order_algorithm"]!="FROZEN_SHA256_FISHER_YATES_V1" or p["comparator"]!="EXACT_ASSISTANT_CONTENT_UTF8_WITH_CANONICAL_STRUCTURED_DIAGNOSTIC" or p["allowed_terminals"]!=list(TERMINALS) or p["nonclaims"]!=list(NONCLAIMS):bad("plan")
 source(p["source"]);[digest(p[x]) for x in ("corpus_manifest_sha256","call_order_seed_sha256","evidence_root_genesis_sha256")]
 if type(p["call_order_seed_hex"])is not str or SHA.fullmatch(p["call_order_seed_hex"])is None:bad("seed")
 seed=bytes.fromhex(p["call_order_seed_hex"])
 if sha256(seed).hexdigest()!=p["call_order_seed_sha256"] or type(p["corpus"])is not list or len(p["corpus"])!=24:bad("corpus")
 ck={"case_id","call_class","request_sha256","instruction_sha256","model_input_sha256","response_schema_sha256","rng_sha256","max_output_tokens"};ids=[];cs=Counter()
 for q in p["corpus"]:
  q=obj(q,ck)
  if type(q["case_id"])is not str or CASE.fullmatch(q["case_id"])is None or q["call_class"]not in CLASSES or type(q["max_output_tokens"])is not int or q["max_output_tokens"]not in {64,128,256}:bad("case")
  for x in ck-{"case_id","call_class","max_output_tokens"}:digest(q[x])
  ids.append(q["case_id"]);cs[q["call_class"]]+=1
 if len(set(ids))!=24 or cs!=Counter({x:8 for x in CLASSES}) or p["call_order"]!=order([f"DNRD5-Q1L-{x[-3:]}-R{n:03d}"for x in ids for n in range(1,5)],seed):bad("coverage/order")
 ii=obj(p["identities"],{"endpoint_sha256","model_identity_sha256","runtime_identity_sha256","tls_identity_sha256","declared_isolation_contract_sha256","model_snapshot_manifest_sha256"});[digest(x)for x in ii.values()]
 v=obj(p["verifier"],{"source","build_output_sha256"});source(v["source"]);digest(v["build_output_sha256"]);return p
def request(model,c,ib,mb,sb,rb):
 ins=ib.decode("utf8","strict");mi=can(mb);sc=can(sb);need={"PRE_OUTCOME_TRAJECTORY":{"publicTask","behaviorProjection"},"REVISION_PROPOSAL":{"sealedTrajectory","assignedFeedback","revisionRequest"},"FRESH_PROBE":{"behaviorProjection","freshProbe"}}[c["call_class"]]
 if not ins or type(mi)is not dict or set(mi)!=need:bad("material")
 schema(sc)
 return canonical_bytes({"chat_template_kwargs":{"enable_thinking":False},"logprobs":False,"max_tokens":c["max_output_tokens"],"messages":[{"content":SYSTEM,"role":"system"},{"content":canonical_bytes({"contractVersion":"hswm-dgx-q1-live-model-input/v1","callClass":c["call_class"],"instruction":ins,"input":mi}).decode(),"role":"user"}],"model":model,"n":1,"response_format":{"type":"json_schema","json_schema":{"name":"hswm_dgx_q1_live_"+c["call_class"].lower(),"schema":sc,"strict":True}},"seed":int.from_bytes(sha256(rb).digest()[:6],"big"),"stream":False,"temperature":0,"top_p":1})
def att(r,d,pr,p,phase,aid,n,stable):
 x=obj(can(blob(r,d)),{"schema_version","namespace","q1_sha256","phase","attempt_id","completed_attempts","endpoint_sha256","model_identity_sha256","runtime_identity_sha256","model_snapshot_manifest_sha256","container_id_sha256","image_id","configured_image","container_start_sha256","cgroup_sha256","argv_sha256","gpu_uuid","gpu_compute_pids","host_listener_present","container_init_pid","container_network_namespace_sha256","container_tcp_tables_sha256","internal_listener_port","host_listener_inventory_sha256","unexpected_listener_count","requests_running","request_success_total","prefix_cache_hits","prefix_cache_queries","raw_metrics_sha256","boundary","nonclaim"})
 if x["schema_version"]!=BOUNDARY or x["namespace"]!=NS or x["q1_sha256"]!=sha256(pr).hexdigest() or (x["phase"],x["attempt_id"],x["completed_attempts"])!=(phase,aid,n) or any(x[k]!=p["identities"][k]for k in ("endpoint_sha256","model_identity_sha256","runtime_identity_sha256","model_snapshot_manifest_sha256")) or x["boundary"]!="FINITE_OBSERVED_CONTROLS_NOT_NO_INTERFERENCE_PROOF" or x["nonclaim"]!="NOT_DISPATCH_AUTHORIZATION_OR_SOURCE_A_PERMIT_OR_NO_INTERFERENCE_PROOF" or x["requests_running"]!=0 or type(x["request_success_total"])is not int or x["request_success_total"]!=n or type(x["prefix_cache_hits"])is not int or type(x["prefix_cache_queries"])is not int or x["prefix_cache_hits"]!=0 or x["prefix_cache_queries"]!=0 or type(x["unexpected_listener_count"])is not int or x["unexpected_listener_count"]!=0:bad("att")
 for k in ("container_id_sha256","container_start_sha256","cgroup_sha256","argv_sha256","container_network_namespace_sha256","container_tcp_tables_sha256","host_listener_inventory_sha256","raw_metrics_sha256"):digest(x[k])
 if type(x["image_id"])is not str or re.fullmatch(r"sha256:[0-9a-f]{64}",x["image_id"])is None or type(x["configured_image"])is not str or not x["configured_image"] or type(x["gpu_uuid"])is not str or re.fullmatch(r"GPU-[0-9a-f-]{8,80}",x["gpu_uuid"])is None:bad("att id")
 if x["host_listener_present"]is not True or type(x["container_init_pid"])is not int or x["container_init_pid"]<=0 or x["internal_listener_port"]!=8000:bad("listener")
 for k in ("gpu_compute_pids",):
  if type(x[k])is not list or not x[k] or x[k]!=sorted(x[k]) or len(set(x[k]))!=len(x[k]) or any(type(q)is not int or q<=0 for q in x[k]):bad("pids")
 now=tuple(x[k]for k in ("container_id_sha256","image_id","configured_image","container_start_sha256","cgroup_sha256","argv_sha256","gpu_uuid","container_init_pid","container_network_namespace_sha256"))
 if stable is not None and now!=stable:bad("continuity")
 return now
def _result(mode,terminal,allow):
 if mode=="LIVE_LEASE":return {"terminal":terminal,"evidence_mode":mode}
 if not allow:return {"terminal":INCONCLUSIVE,"evidence_mode":mode}
 mapped={REPRODUCED:TEST_REPRODUCED,FALSIFIED:TEST_FALSIFIED,INCONCLUSIVE:TEST_INCONCLUSIVE}
 return {"terminal":mapped.get(terminal,VOID),"evidence_mode":mode}
def _external_consumption_witness(
 external_registry_root:Path|None,registry_path:str,plan_sha256:str,copied_consumption:bytes
)->bool:
 """Check the node-local burn record independently of the copied evidence.

 The evidence root contains a copied, hash-bound consumption record.  A live
 verdict additionally requires the durable record at the frozen registry path
 to still be present as the same ordinary file.  This is deliberately a
 node-local witness, not a distributed-consensus claim.
 """
 try:
  if not isinstance(external_registry_root,Path)or type(registry_path)is not str or SHA.fullmatch(plan_sha256)is None: return False
  declared=Path(registry_path)
  if not declared.is_absolute()or external_registry_root!=declared or external_registry_root.is_symlink()or not external_registry_root.is_dir():return False
  marker=external_registry_root/(plan_sha256+".consumed")
  if marker.is_symlink()or not marker.is_file():return False
  return marker.read_bytes()==copied_consumption
 except (OSError,ValueError):return False
def verify(root:Path,*,external_registry_root:Path|None=None,allow_test_fixture:bool=False)->dict[str,str]:
 try:
  if type(allow_test_fixture)is not bool or(external_registry_root is not None and not isinstance(external_registry_root,Path)):bad("verifier options")
  if not isinstance(root,Path)or root.is_symlink()or not root.is_dir()or (root/"content").is_symlink()or not (root/"content").is_dir()or (root/"q1_live_ledger.jsonl").is_symlink()or not (root/"q1_live_ledger.jsonl").is_file()or(root/"dispatch.lock").is_symlink()or not(root/"dispatch.lock").is_file():bad("root type")
  if {p.name for p in root.iterdir()}!={"content","q1_live_ledger.jsonl","dispatch.lock"}or any(p.is_symlink()or not p.is_file()or SHA.fullmatch(p.name)is None for p in(root/"content").iterdir()):bad("root closure")
  raw=(root/"q1_live_ledger.jsonl").read_bytes()
  if not raw.endswith(b"\n"):bad()
  rows=[can(x)for x in raw[:-1].split(b"\n")];prev=Z
  for i,x in enumerate(rows,1):
   if type(x)is not dict or x.get("ordinal")!=i or x.get("previous_record_sha256")!=prev or x.get("record_sha256")!=canonical_sha256({k:v for k,v in x.items()if k!="record_sha256"}):bad("chain")
   prev=x["record_sha256"]
  if len(rows)<3:bad("ledger cardinality")
  burn=obj(rows[0],{"schema_version","namespace","record_type","consumption","plan_sha256","closure_manifest_sha256","registry_path","evidence_mode","retry","terminal","ordinal","previous_record_sha256","record_sha256"})
  mk=obj(rows[1],{"schema_version","namespace","record_type","evidence_mode","plan","marker","corpus_manifest","root_genesis","freeze_closure","identities","provenance","startup_boundary_attestation","all_request_blobs_durable","request_sha256s","retry","terminal","ordinal","previous_record_sha256","record_sha256"})
  if burn["schema_version"]!=LEDGER or burn["namespace"]!=NS or burn["record_type"]!="PLAN_CONSUMPTION"or burn["retry"]!="NONE"or burn["terminal"]!="DURABLE_PLAN_BURN_BEFORE_ANY_PRE_OR_START":bad("consumption ledger")
  if mk["schema_version"]!=LEDGER or mk["namespace"]!=NS or mk["record_type"]!="LIVE_MARKER" or mk["evidence_mode"]not in{"LIVE_LEASE","TEST_FIXTURE_INJECTED"}or burn["evidence_mode"]!=mk["evidence_mode"]or mk["all_request_blobs_durable"]is not True or mk["retry"]!="NONE" or mk["terminal"]!="ALL_24_EXACT_REQUEST_BLOBS_FSYNCED_BEFORE_FIRST_LIVE_START":bad("marker")
  pr=blob(root,mk["plan"]);p=plan(pr);mark=obj(can(blob(root,mk["marker"])),{"schema_version","namespace","q1_sha256","request_sha256s","terminal","nonclaims"})
  if mark!={"schema_version":MARKER,"namespace":NS,"q1_sha256":sha256(pr).hexdigest(),"request_sha256s":[x["request_sha256"]for x in p["corpus"]],"terminal":"PLAN_AND_ALL_24_REQUEST_HASHES_BOUND_BEFORE_ANY_LIVE_START","nonclaims":list(NONCLAIMS)}or mk["request_sha256s"]!=mark["request_sha256s"]:bad("marker bind")
  closure_raw=blob(root,mk["freeze_closure"]);closure=obj(can(closure_raw),{"schema_version","namespace","artifacts"})
  if closure["schema_version"]!="hswm-dgx-q1-live-preregistration-freeze/v1"or closure["namespace"]!=NS or type(closure["artifacts"])is not list or not closure["artifacts"]:bad("freeze closure")
  closure_entries={x.get("path"):x for x in closure["artifacts"]if type(x)is dict and set(x)=={"path","sha256","byte_length"}}
  plan_entry=closure_entries.get("plan.json")
  if len(closure_entries)!=len(closure["artifacts"])or type(plan_entry)is not dict or {k:plan_entry[k]for k in("sha256","byte_length")}!=mk["plan"]:bad("freeze plan closure")
  consumption=obj(can(blob(root,burn["consumption"])),{"schema_version","plan_sha256","closure_manifest_sha256","evidence_root","registry_path","evidence_mode","launch_identity_sha256","terminal"})
  if burn["plan_sha256"]!=sha256(pr).hexdigest()or burn["closure_manifest_sha256"]!=sha256(closure_raw).hexdigest()or consumption!={"schema_version":"hswm-dgx-q1-plan-consumption/v1","plan_sha256":burn["plan_sha256"],"closure_manifest_sha256":burn["closure_manifest_sha256"],"evidence_root":str(root),"registry_path":burn["registry_path"],"evidence_mode":mk["evidence_mode"],"launch_identity_sha256":mk["startup_boundary_attestation"]["sha256"],"terminal":"PLAN_BURNED_BEFORE_FIRST_LIVE_START_NO_REUSE"}:bad("consumption binding")
  if type(burn["registry_path"])is not str or not Path(burn["registry_path"]).is_absolute()or(mk["evidence_mode"]=="LIVE_LEASE"and burn["registry_path"]!=p["consumption_registry"]["path"]):bad("registry binding")
  registry_witness=_external_consumption_witness(external_registry_root,burn["registry_path"],burn["plan_sha256"],canonical_bytes(consumption)) if mk["evidence_mode"]=="LIVE_LEASE" else True
  cm=blob(root,mk["corpus_manifest"]);g=blob(root,mk["root_genesis"]);cmv=can(cm);gv=can(g)
  if sha256(cm).hexdigest()!=p["corpus_manifest_sha256"]or type(cmv)is not dict or set(cmv)!={"schema_version","namespace","q0_public_synthetic_manifest","corpus"}or cmv["schema_version"]!="hswm-dgx-q1-live-public-synthetic-corpus/v1"or cmv["namespace"]!=NS or type(cmv["q0_public_synthetic_manifest"])is not dict or cmv["q0_public_synthetic_manifest"].get("classification")!="PUBLIC_SYNTHETIC_QUALIFICATION_ONLY_NO_CORRECTNESS_EVALUATOR"or cmv["corpus"]!=p["corpus"]or sha256(g).hexdigest()!=p["evidence_root_genesis_sha256"]or gv!={"schema_version":"hswm-dgx-q1-evidence-root-genesis/v1","nonce_hex":gv.get("nonce_hex")if type(gv)is dict else None,"purpose":"FRESH_SINGLE_USE_LIVE_Q1_EVIDENCE_ROOT","terminal":"GENESIS_BOUND_BEFORE_ANY_LIVE_START"}or type(gv.get("nonce_hex"))is not str or SHA.fullmatch(gv["nonce_hex"])is None:bad("root")
  ids=obj(mk["identities"],set(p["identities"]));ibs={k:blob(root,v)for k,v in ids.items()}
  if any(sha256(ibs[k]).hexdigest()!=p["identities"][k]for k in ids):bad("ids")
  ep=can(ibs["endpoint_sha256"]);model=can(ibs["model_identity_sha256"]);tls=can(ibs["tls_identity_sha256"]);iso=can(ibs["declared_isolation_contract_sha256"]);snap=can(ibs["model_snapshot_manifest_sha256"]);runtime=can(ibs["runtime_identity_sha256"])
  rk={"schema_version","container_image","image_id","vllm_version","gpu_uuid","gpu_name","gpu_driver_version","gpu_compute_capability","endpoint","served_model","model_revision","model_snapshot_manifest_sha256","max_model_len","max_num_seqs","gpu_memory_utilization_milli","prefix_cache","enforce_eager","batch_invariant","v1_multiprocessing","model_loading_offline","generation_config","engine_seed","language_model_only","container_internal_port","container_network_mode","container_ipc_mode","host_publish_ip"}
  files=snap.get("files")if type(snap)is dict else None
  if type(ep)is not dict or set(ep)!={"schema_version","endpoint","method","transport"}or ep.get("schema_version")!="hswm-dgx-q1-endpoint-identity/v1"or ep.get("method")!="POST"or ep.get("transport")!="LOOPBACK_HTTP_NO_TLS"or type(ep.get("endpoint"))is not str or re.fullmatch(r"http://127\.0\.0\.1:[1-9][0-9]{0,4}/v1/chat/completions",ep["endpoint"])is None or type(model)is not dict or set(model)!={"schema_version","model","repository","revision","snapshot_manifest_sha256"}or model.get("schema_version")!="hswm-dgx-q1-model-identity/v1"or not all(type(model.get(k))is str and model[k]for k in ("model","repository","revision"))or GIT.fullmatch(model["revision"])is None or model.get("snapshot_manifest_sha256")!=p["identities"]["model_snapshot_manifest_sha256"]or tls!={"schema_version":"hswm-dgx-q1-tls-identity/v1","endpoint_scheme":"http","tls":"NOT_APPLICABLE_LOOPBACK_ONLY"}or type(snap)is not dict or set(snap)!={"schema_version","repository","revision","file_count","total_byte_length","files","files_sha256"}or snap.get("schema_version")!="hswm-dgx-q1-model-snapshot-manifest/v1"or snap.get("repository")!=model["repository"]or snap.get("revision")!=model["revision"]or type(snap.get("file_count"))is not int or snap["file_count"]<=0 or type(files)is not list or len(files)!=snap["file_count"]or snap.get("files_sha256")!=canonical_sha256(files)or type(snap.get("total_byte_length"))is not int or snap["total_byte_length"]!=sum(x.get("byte_length",-1)for x in files if type(x)is dict)or any(type(x)is not dict or set(x)!={"path","blob","byte_length","sha256"}or type(x["path"])is not str or not x["path"]or type(x["blob"])is not str or not x["blob"]or type(x["byte_length"])is not int or x["byte_length"]<0 or type(x["sha256"])is not str or SHA.fullmatch(x["sha256"])is None for x in files)or type(runtime)is not dict or set(runtime)!=rk or runtime.get("schema_version")!="hswm-dgx-q1-runtime-identity/v1"or runtime.get("served_model")!=model["model"]or runtime.get("endpoint")!=ep["endpoint"]or runtime.get("model_revision")!=model["revision"]or runtime.get("model_snapshot_manifest_sha256")!=p["identities"]["model_snapshot_manifest_sha256"]or type(runtime.get("container_image"))is not str or re.fullmatch(r"[^@\s]+@sha256:[0-9a-f]{64}",runtime["container_image"])is None or type(runtime.get("image_id"))is not str or re.fullmatch(r"sha256:[0-9a-f]{64}",runtime["image_id"])is None or type(runtime.get("gpu_uuid"))is not str or re.fullmatch(r"GPU-[0-9a-f-]{8,80}",runtime["gpu_uuid"])is None or runtime.get("max_num_seqs")!=1 or runtime.get("prefix_cache")is not False or runtime.get("enforce_eager")is not True or runtime.get("batch_invariant")is not True or runtime.get("v1_multiprocessing")is not False or runtime.get("model_loading_offline")is not True or runtime.get("generation_config")!="vllm"or runtime.get("engine_seed")!=0 or runtime.get("language_model_only") is not True:bad("semantic ids")
  if runtime.get("language_model_only")is not True or runtime.get("container_internal_port")!=8000 or runtime.get("container_network_mode")!="bridge"or runtime.get("container_ipc_mode")!="private"or runtime.get("host_publish_ip")!="127.0.0.1":bad("semantic ids")
  expectediso={"schema_version":"hswm-dgx-q1-declared-isolation/v1","batch_invariant":True,"boundary":"FINITE_DECLARED_CONTROL_CONTRACT_NOT_OBSERVED_PROOF","dedicated_gpu":True,"dedicated_node":True,"dedicated_process":True,"max_num_seqs":1,"network_scope":"LOOPBACK_INGRESS_ONLY_OUTBOUND_NOT_ATTESTED","other_inference_processes":0,"prefix_cache":False,"v1_multiprocessing":False}
  if iso!=expectediso:bad("isolation")
  pv=obj(mk["provenance"],{"source_ci_receipt_sha256","verifier_ci_receipt_sha256","verifier_build_output_sha256"});ex={"source_ci_receipt_sha256":p["source"]["ci_receipt_sha256"],"verifier_ci_receipt_sha256":p["verifier"]["source"]["ci_receipt_sha256"],"verifier_build_output_sha256":p["verifier"]["build_output_sha256"]};pvb={k:blob(root,pv[k])for k in ex}
  if any(sha256(pvb[k]).hexdigest()!=ex[k]for k in ex):bad("provenance")
  ci(pvb["source_ci_receipt_sha256"],p["source"]);ci(pvb["verifier_ci_receipt_sha256"],p["verifier"]["source"]);verifier_build(pvb["verifier_build_output_sha256"])
  stable=att(root,mk["startup_boundary_attestation"],pr,p,"STARTUP",None,0,None)
  if stable[1]!=runtime["image_id"]or stable[2]!=runtime["container_image"]or stable[6]!=runtime["gpu_uuid"]:bad("att runtime join")
  cases={x["case_id"]:x for x in p["corpus"]};req={};schemas={}
  for cid,c in cases.items():
   get=lambda n:blob(root,{"sha256":c[n],"byte_length":len((root/"content"/c[n]).read_bytes())})
   req[cid]=request(model["model"],c,get("instruction_sha256"),get("model_input_sha256"),get("response_schema_sha256"),get("rng_sha256"));schemas[cid]=get("response_schema_sha256")
   if sha256(req[cid]).hexdigest()!=c["request_sha256"]:bad("request")
  i=2;started=ok=0;out={};halt=False
  while i<len(rows)and rows[i].get("record_type")=="START":
   s=obj(rows[i],{"schema_version","namespace","record_type","attempt_id","case_id","replicate","call_class","request","response_schema","plan_sha256","pre_boundary_attestation","retry","terminal","ordinal","previous_record_sha256","record_sha256"});i+=1;m=ATT.fullmatch(s["attempt_id"])
   if s["schema_version"]!=LEDGER or s["namespace"]!=NS or m is None or s["attempt_id"]!=p["call_order"][started]or s["case_id"]!="QCASE-"+m.group(1)or s["replicate"]!=int(m.group(2))or s["call_class"]!=cases[s["case_id"]]["call_class"]or s["plan_sha256"]!=sha256(pr).hexdigest()or s["retry"]!="NONE"or s["terminal"]!="DURABLY_VISIBLE_BEFORE_SINGLE_LIVE_POST"or blob(root,s["request"])!=req[s["case_id"]]or blob(root,s["response_schema"])!=schemas[s["case_id"]]:bad("start")
   stable=att(root,s["pre_boundary_attestation"],pr,p,"PRE",s["attempt_id"],started,stable);started+=1
   t=obj(rows[i],{"schema_version","namespace","record_type","attempt_id","case_id","replicate","call_class","start_record_sha256","observation","raw_envelope","post_boundary_attestation","model_content_utf8","structured_content_diagnostic","outcome","failure_code","retry","retry_allowed","terminal","ordinal","previous_record_sha256","record_sha256"});i+=1
   if t["schema_version"]!=LEDGER or t["namespace"]!=NS or any(t[k]!=s[k]for k in ("attempt_id","case_id","replicate","call_class"))or t["start_record_sha256"]!=s["record_sha256"]or t["retry"]!="NONE"or t["retry_allowed"]is not False or t["terminal"]!="LIVE_SLOT_CONSUMED_NO_RETRY_OR_REPLACEMENT"or t["outcome"]not in {"SUCCEEDED","FAILED"}:bad("terminal")
   if t["outcome"]=="SUCCEEDED":
    o=obj(t["observation"],{"status","response_content_type","provider_request_id"})
    if type(o["status"])is not int or (o["response_content_type"]is not None and type(o["response_content_type"])is not str)or(o["provider_request_id"]is not None and type(o["provider_request_id"])is not str)or t["failure_code"]is not None:bad("obs")
    stable=att(root,t["post_boundary_attestation"],pr,p,"POST",s["attempt_id"],started,stable);e=strict(blob(root,t["raw_envelope"]));content=blob(root,t["model_content_utf8"]);structured=blob(root,t["structured_content_diagnostic"])
    if o["status"]!=200 or type(e)is not dict or e.get("model")!=model["model"]or type(e.get("choices"))is not list or len(e["choices"])!=1 or type(e["choices"][0])is not dict or e["choices"][0].get("finish_reason")!="stop"or type(e["choices"][0].get("message"))is not dict or e["choices"][0]["message"].get("content").encode()!=content:bad("envelope")
    u=e.get("usage")
    if type(u)is not dict or any(type(u.get(k))is not int or u[k]<0 for k in ("prompt_tokens","completion_tokens","total_tokens"))or u["prompt_tokens"]+u["completion_tokens"]!=u["total_tokens"]:bad("usage")
    q=strict(content);schema(can(schemas[s["case_id"]]),q,True)
    if structured!=canonical_bytes(q):bad("diagnostic")
    out.setdefault(s["case_id"],[]).append(content);ok+=1
   else:
    if type(t["failure_code"])is not str or t["model_content_utf8"]is not None or t["structured_content_diagnostic"]is not None:bad("failed")
    if t["raw_envelope"]is not None:blob(root,t["raw_envelope"])
    if t["post_boundary_attestation"]is not None:stable=att(root,t["post_boundary_attestation"],pr,p,"POST",s["attempt_id"],started,stable)
  seal=obj(rows[i],{"schema_version","namespace","record_type","status","started_slots","successful_slots","failed_slots","failure_code","final_boundary_attestation","retry","retry_allowed","terminal","ordinal","previous_record_sha256","record_sha256"});i+=1
  if i!=len(rows)or seal["schema_version"]!=LEDGER or seal["namespace"]!=NS or seal["record_type"]!="RUN_SEAL"or(seal["started_slots"],seal["successful_slots"],seal["failed_slots"])!=(started,ok,started-ok)or seal["retry"]!="NONE"or seal["retry_allowed"]is not False or seal["terminal"]!="LIVE_Q1_ROOT_SEALED_NO_RESUME_OR_REPLACEMENT":bad("seal")
  if seal["status"]=="COMPLETE_96_LIVE_POSTS":
   if started!=96 or seal["failure_code"]is not None or seal["final_boundary_attestation"]is None:bad("complete")
   att(root,seal["final_boundary_attestation"],pr,p,"FINAL",None,96,stable)
   if ok!=96 or len(out)!=24 or any(len(v)!=4 for v in out.values()):return _result(mk["evidence_mode"],INCONCLUSIVE,allow_test_fixture)
   terminal=REPRODUCED if all(len(set(v))==1 for v in out.values())else FALSIFIED
   if not registry_witness:terminal=INCONCLUSIVE
   return _result(mk["evidence_mode"],terminal,allow_test_fixture)
  if seal["status"]not in {"HALTED_BEFORE_LIVE_POST","HALTED_AFTER_TRANSPORT_FAILURE","HALTED_AFTER_POST_BOUNDARY_FAILURE","HALTED_AFTER_FINAL_BOUNDARY_FAILURE"}or type(seal["failure_code"])is not str:bad("halt")
  if seal["status"]=="HALTED_AFTER_FINAL_BOUNDARY_FAILURE":
   if started!=96 or seal["final_boundary_attestation"]is not None:bad("final")
  elif seal["final_boundary_attestation"]is not None:bad("early")
  return _result(mk["evidence_mode"],INCONCLUSIVE,allow_test_fixture)
 except Exception:return {"terminal":VOID}

__all__=["REPRODUCED","FALSIFIED","INCONCLUSIVE","VOID","TEST_REPRODUCED","TEST_FALSIFIED","TEST_INCONCLUSIVE","verify"]
