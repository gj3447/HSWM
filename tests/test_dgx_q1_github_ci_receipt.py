from __future__ import annotations
import json
from pathlib import Path
import pytest
from _research.dnrd5.canonical_json import canonical_bytes
from _research.dgx_q1.github_ci_receipt import *
import _research.dgx_q1.github_ci_receipt as module
COMMIT,TREE="a"*40,"b"*40
def raw():
 r={"id":1,"workflow_id":2,"run_number":3,"name":"CI","path":".github/workflows/ci.yml","event":"push","head_branch":"main","head_sha":COMMIT,"run_attempt":1,"status":"completed","conclusion":"success","created_at":"2026-08-29T00:00:00Z","run_started_at":"2026-08-29T00:00:01Z","updated_at":"2026-08-29T00:00:02Z","pull_requests":[],"repository":{"id":1,"full_name":"gj3447/HSWM"},"head_repository":{"id":1,"full_name":"gj3447/HSWM"},"head_commit":{"id":COMMIT,"tree_id":TREE}}
 l={"query":{"workflow_path":".github/workflows/ci.yml","event":"push","branch":"main","head_sha":COMMIT,"per_page":100,"page":1},"total_count":1,"workflow_runs":[r]};j={"query":{"run_id":1,"per_page":100,"page":1},"total_count":1,"jobs":[{"name":"test","status":"completed","conclusion":"success"}]}
 return tuple(json.dumps(x).encode()for x in(r,l,j))
def build():return build_github_actions_ci_receipt(*raw(),repository="gj3447/HSWM",commit=COMMIT,tree=TREE)
def test_unique_tree_joined_projection():assert parse_github_actions_ci_receipt(build(),repository="gj3447/HSWM",commit=COMMIT,tree=TREE)["boundary"]==BOUNDARY
@pytest.mark.parametrize("where,key,value",[(0,"run_attempt",2),(0,"head_branch","dev"),(0,"updated_at","2026-08-28T00:00:00Z"),(1,"total_count",2),(2,"total_count",2)])
def test_refuses_run_list_and_jobs_drift(where,key,value):
 x=list(map(json.loads,raw()));x[where][key]=value
 with pytest.raises(GitHubCiReceiptRefusal):build_github_actions_ci_receipt(*(json.dumps(y).encode()for y in x),repository="gj3447/HSWM",commit=COMMIT,tree=TREE)
def test_refuses_tree_and_list_row_mismatch():
 x=list(map(json.loads,raw()));x[0]["head_commit"]["tree_id"]="c"*40
 with pytest.raises(GitHubCiReceiptRefusal):build_github_actions_ci_receipt(*(json.dumps(y).encode()for y in x),repository="gj3447/HSWM",commit=COMMIT,tree=TREE)
 x=list(map(json.loads,raw()));x[1]["workflow_runs"][0]["id"]=7
 with pytest.raises(GitHubCiReceiptRefusal):build_github_actions_ci_receipt(*(json.dumps(y).encode()for y in x),repository="gj3447/HSWM",commit=COMMIT,tree=TREE)
def test_cli_writes_once(tmp_path:Path):
 paths=[]
 for n,b in zip(("run","list","jobs"),raw()):p=tmp_path/n;p.write_bytes(b);paths.append(p)
 out=tmp_path/"receipt";a=["--run",str(paths[0]),"--runs-list",str(paths[1]),"--jobs",str(paths[2]),"--repository","gj3447/HSWM","--commit",COMMIT,"--tree",TREE,"--output",str(out)]
 assert module.main(a)==0 and out.is_file() and module.main(a)==2
def test_parser_refuses_tamper():
 with pytest.raises(GitHubCiReceiptRefusal):parse_github_actions_ci_receipt(build()+b"\n",repository="gj3447/HSWM",commit=COMMIT,tree=TREE)
 x=json.loads(build());x["terminal"]="x"
 with pytest.raises(GitHubCiReceiptRefusal):parse_github_actions_ci_receipt(canonical_bytes(x),repository="gj3447/HSWM",commit=COMMIT,tree=TREE)
def test_saved_input_bytes_and_handcrafted_semantics_cannot_substitute():
    run,listing,jobs=raw();saved={"run_json":run,"runs_list_json":listing,"jobs_json":jobs}
    receipt_bytes=build()
    assert parse_github_actions_ci_receipt(receipt_bytes,repository="gj3447/HSWM",commit=COMMIT,tree=TREE,saved_inputs=saved)["commit"]==COMMIT
    altered=dict(saved);altered["jobs_json"]=jobs+b" "
    with pytest.raises(GitHubCiReceiptRefusal):parse_github_actions_ci_receipt(receipt_bytes,repository="gj3447/HSWM",commit=COMMIT,tree=TREE,saved_inputs=altered)
    handcrafted=json.loads(receipt_bytes);handcrafted["evidence_inputs"]["jobs_json"]["sha256"]="0"*64
    with pytest.raises(GitHubCiReceiptRefusal):parse_github_actions_ci_receipt(canonical_bytes(handcrafted),repository="gj3447/HSWM",commit=COMMIT,tree=TREE,saved_inputs=saved)
def test_embedded_raw_evidence_is_self_contained_and_canonical_base64():
    receipt_bytes=build()
    assert parse_github_actions_ci_receipt(receipt_bytes,repository="gj3447/HSWM",commit=COMMIT,tree=TREE)["tree"]==TREE
    value=json.loads(receipt_bytes);value["evidence_inputs"]["run_json"]["base64"]+="\n"
    with pytest.raises(GitHubCiReceiptRefusal):parse_github_actions_ci_receipt(canonical_bytes(value),repository="gj3447/HSWM",commit=COMMIT,tree=TREE)
