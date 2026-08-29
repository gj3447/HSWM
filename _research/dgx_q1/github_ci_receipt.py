"""Strict offline GitHub Actions CI receipt projector; never contacts GitHub."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import base64, json, os, re, tempfile
from pathlib import Path
from typing import Any
from _research.dnrd5.canonical_json import canonical_bytes, canonical_sha256, parse_canonical

SCHEMA="hswm-github-actions-first-success-ci-receipt/v1"
BOUNDARY="RAW_GITHUB_API_PROJECTION_NOT_CRYPTOGRAPHIC_PROVIDER_ATTESTATION"
TERMINAL="FIRST_ATTEMPT_SUCCESSFUL_CI_BUILD"; WORKFLOW_PATH=".github/workflows/ci.yml"; _GIT=re.compile(r"^[0-9a-f]{40}$")
class GitHubCiReceiptRefusal(ValueError): pass
def _json(raw:bytes,label:str)->dict[str,Any]:
 if type(raw)is not bytes or not raw or len(raw)>4*1024*1024:raise GitHubCiReceiptRefusal(f"{label} bytes")
 def pairs(xs):
  d={}
  for k,v in xs:
   if k in d:raise GitHubCiReceiptRefusal(f"{label} duplicate")
   d[k]=v
  return d
 try:v=json.loads(raw.decode("utf8","strict"),object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
 except (UnicodeDecodeError,json.JSONDecodeError,ValueError)as e:raise GitHubCiReceiptRefusal(f"{label} JSON")from e
 if type(v)is not dict:raise GitHubCiReceiptRefusal(f"{label} object")
 return v
def _id(repo:str,commit:str,tree:str)->None:
 if repo!="gj3447/HSWM"or any(type(x)is not str or _GIT.fullmatch(x)is None or x=="0"*40 for x in(commit,tree)):raise GitHubCiReceiptRefusal("identity")
def _time(v:object,label:str)->int:
 if type(v)is not str:raise GitHubCiReceiptRefusal(label)
 try:return int(datetime.strptime(v,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp())
 except ValueError as e:raise GitHubCiReceiptRefusal(label)from e
def _run(x:dict[str,Any],repo:str,commit:str,tree:str,label:str)->dict[str,Any]:
 r,h,c=x.get("repository"),x.get("head_repository"),x.get("head_commit")
 fields=("id","workflow_id","run_number","name","path","event","head_branch","head_sha","run_attempt","status","conclusion","created_at","run_started_at","updated_at","pull_requests")
 if type(r)is not dict or type(h)is not dict or type(c)is not dict:raise GitHubCiReceiptRefusal(label)
 y={k:x.get(k)for k in fields};y|={"repository":{"id":r.get("id"),"full_name":r.get("full_name")},"head_repository":{"id":h.get("id"),"full_name":h.get("full_name")},"head_commit":{"id":c.get("id"),"tree_id":c.get("tree_id")}}
 if(type(y["id"])is not int or y["id"]<=0 or type(y["workflow_id"])is not int or y["workflow_id"]<=0 or type(y["run_number"])is not int or y["run_number"]<=0 or y["name"]!="CI"or y["path"]!=WORKFLOW_PATH or(y["event"],y["head_branch"],y["head_sha"],y["run_attempt"],y["status"],y["conclusion"],y["pull_requests"])!=("push","main",commit,1,"completed","success",[])or y["repository"]!=y["head_repository"]or y["repository"].get("full_name")!=repo or type(y["repository"].get("id"))is not int or y["repository"]["id"]<=0 or y["head_commit"]!={"id":commit,"tree_id":tree}):raise GitHubCiReceiptRefusal(label)
 a,b,d=(_time(y[k],f"{label}.{k}")for k in("created_at","run_started_at","updated_at"))
 if not a<=b<=d:raise GitHubCiReceiptRefusal(label)
 return y
def _jobs(x:dict[str,Any],run_id:int)->list[dict[str,str]]:
 if x.get("query")!={"run_id":run_id,"per_page":100,"page":1}or type(x.get("jobs"))is not list or not x["jobs"]or x.get("total_count")!=len(x["jobs"])or len(x["jobs"])>100:raise GitHubCiReceiptRefusal("jobs pagination")
 v=[]
 for j in x["jobs"]:
  if type(j)is not dict or type(j.get("name"))is not str or not j["name"]or j.get("status")!="completed"or j.get("conclusion")!="success":raise GitHubCiReceiptRefusal("job")
  v.append({"name":j["name"],"conclusion":"success"})
 v.sort(key=lambda z:z["name"])
 if len({z["name"]for z in v})!=len(v):raise GitHubCiReceiptRefusal("job names")
 return v
def _desc(raw:bytes)->dict[str,Any]:return {"sha256":__import__("hashlib").sha256(raw).hexdigest(),"byte_length":len(raw),"base64":base64.b64encode(raw).decode("ascii")}
def _metadata(raw:bytes|None)->dict[str,Any]|None:
 if raw is None:return None
 # The optional saved workflow endpoint is retained byte-for-byte; it is not
 # substituted for the selected run/list evidence.
 _json(raw,"workflow metadata")
 return _desc(raw)
def _inputs(run:bytes,listing:bytes,jobs:bytes,workflow:bytes|None)->dict[str,Any]:
 return {"run_json":_desc(run),"runs_list_json":_desc(listing),"jobs_json":_desc(jobs),"workflow_metadata_json":_metadata(workflow)}
def build_github_actions_ci_receipt(run_json:bytes,runs_list_json:bytes,jobs_json:bytes,*,repository:str,commit:str,tree:str,workflow_metadata_json:bytes|None=None)->bytes:
 _id(repository,commit,tree);selected=_run(_json(run_json,"run"),repository,commit,tree,"run"); listing=_json(runs_list_json,"runs list")
 q={"workflow_path":WORKFLOW_PATH,"event":"push","branch":"main","head_sha":commit,"per_page":100,"page":1}
 if listing.get("query")!=q or listing.get("total_count")!=1 or type(listing.get("workflow_runs"))is not list or len(listing["workflow_runs"])!=1 or type(listing["workflow_runs"][0])is not dict or _run(listing["workflow_runs"][0],repository,commit,tree,"runs list row")!=selected:raise GitHubCiReceiptRefusal("unique workflow selection")
 jobs_page=_json(jobs_json,"jobs");jobs=_jobs(jobs_page,selected["id"])
 query={"workflow_runs":q,"jobs":jobs_page["query"]}
 return canonical_bytes({"schema_version":SCHEMA,"provider":"github-actions","repository":repository,"commit":commit,"tree":tree,"workflow_run_id":selected["id"],"run_attempt":1,"event":"push","head_branch":"main","conclusion":"success","jobs":jobs,"jobs_sha256":canonical_sha256(jobs),"evidence_inputs":_inputs(run_json,runs_list_json,jobs_json,workflow_metadata_json),"query_contract":query,"terminal":TERMINAL,"boundary":BOUNDARY})
def _check_inputs(value:object,provided:dict[str,bytes]|None)->dict[str,bytes]:
 names={"run_json","runs_list_json","jobs_json","workflow_metadata_json"}
 if type(value)is not dict or set(value)!=names:raise GitHubCiReceiptRefusal("input evidence descriptors")
 decoded:dict[str,bytes]={}
 for name in names:
  descriptor=value[name]
  if name=="workflow_metadata_json"and descriptor is None:
   if provided is not None and name in provided:raise GitHubCiReceiptRefusal("unexpected workflow metadata")
   continue
  if type(descriptor)is not dict or set(descriptor)!={"sha256","byte_length","base64"}or type(descriptor["sha256"])is not str or re.fullmatch(r"[0-9a-f]{64}",descriptor["sha256"]) is None or type(descriptor["byte_length"])is not int or descriptor["byte_length"]<1 or type(descriptor["base64"])is not str:raise GitHubCiReceiptRefusal("input evidence descriptor")
  try:raw=base64.b64decode(descriptor["base64"],validate=True)
  except Exception as error:raise GitHubCiReceiptRefusal("input evidence base64")from error
  if base64.b64encode(raw).decode("ascii")!=descriptor["base64"]or _desc(raw)!=descriptor:raise GitHubCiReceiptRefusal("input evidence byte/hash mismatch")
  decoded[name]=raw
  if provided is not None:
   if name not in provided or type(provided[name])is not bytes or _desc(provided[name])!=descriptor:raise GitHubCiReceiptRefusal("saved input evidence drift")
 if provided is not None and set(provided)-names:raise GitHubCiReceiptRefusal("unexpected saved input")
 return decoded
def parse_github_actions_ci_receipt(raw:bytes,*,repository:str,commit:str,tree:str,saved_inputs:dict[str,bytes]|None=None)->dict[str,Any]:
 _id(repository,commit,tree)
 try:x=parse_canonical(raw)
 except Exception as e:raise GitHubCiReceiptRefusal("canonical receipt")from e
 k={"schema_version","provider","repository","commit","tree","workflow_run_id","run_attempt","event","head_branch","conclusion","jobs","jobs_sha256","evidence_inputs","query_contract","terminal","boundary"};jobs=x.get("jobs")if type(x)is dict else None
 if(type(x)is not dict or set(x)!=k or x.get("schema_version")!=SCHEMA or x.get("provider")!="github-actions"or(x.get("repository"),x.get("commit"),x.get("tree"),x.get("run_attempt"),x.get("event"),x.get("head_branch"),x.get("conclusion"),x.get("terminal"),x.get("boundary"))!=(repository,commit,tree,1,"push","main","success",TERMINAL,BOUNDARY)or type(x.get("workflow_run_id"))is not int or x["workflow_run_id"]<=0 or type(jobs)is not list or not jobs or jobs!=sorted(jobs,key=lambda z:z.get("name","")if type(z)is dict else "")or any(type(z)is not dict or set(z)!={"name","conclusion"}or type(z["name"])is not str or not z["name"]or z["conclusion"]!="success"for z in jobs)or len({z["name"]for z in jobs})!=len(jobs)or x.get("jobs_sha256")!=canonical_sha256(jobs)):raise GitHubCiReceiptRefusal("receipt")
 embedded=_check_inputs(x["evidence_inputs"],saved_inputs)
 if x["query_contract"]!={"workflow_runs":{"workflow_path":WORKFLOW_PATH,"event":"push","branch":"main","head_sha":commit,"per_page":100,"page":1},"jobs":{"run_id":x["workflow_run_id"],"per_page":100,"page":1}}:raise GitHubCiReceiptRefusal("query contract")
 rebuilt=build_github_actions_ci_receipt(embedded["run_json"],embedded["runs_list_json"],embedded["jobs_json"],repository=repository,commit=commit,tree=tree,workflow_metadata_json=embedded.get("workflow_metadata_json"))
 if rebuilt!=raw:raise GitHubCiReceiptRefusal("handcrafted semantic receipt substitution")
 return x
def _write(path:Path,raw:bytes)->None:
 if path.exists()or path.is_symlink()or not path.parent.is_dir():raise GitHubCiReceiptRefusal("fresh output")
 fd,tmp=tempfile.mkstemp(prefix=".q1-ci-",dir=path.parent)
 try:
  with os.fdopen(fd,"wb")as f:f.write(raw);f.flush();os.fsync(f.fileno())
  os.link(tmp,path)
 finally:
  try:os.unlink(tmp)
  except FileNotFoundError:pass
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
def main(argv:list[str]|None=None)->int:
 p=argparse.ArgumentParser(description="offline Q1 CI receipt projector; no network")
 for n in("run","runs-list","jobs","repository","commit","tree","output"):p.add_argument("--"+n,required=True)
 p.add_argument("--workflow-metadata")
 a=p.parse_args(argv)
 try:_write(Path(a.output),build_github_actions_ci_receipt(Path(a.run).read_bytes(),Path(a.runs_list).read_bytes(),Path(a.jobs).read_bytes(),repository=a.repository,commit=a.commit,tree=a.tree,workflow_metadata_json=None if a.workflow_metadata is None else Path(a.workflow_metadata).read_bytes()))
 except (OSError,ValueError,GitHubCiReceiptRefusal):return 2
 return 0
if __name__=="__main__":raise SystemExit(main())
__all__=["BOUNDARY","GitHubCiReceiptRefusal","SCHEMA","TERMINAL","build_github_actions_ci_receipt","parse_github_actions_ci_receipt"]
