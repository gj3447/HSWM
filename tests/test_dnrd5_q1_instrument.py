from __future__ import annotations

import json
import shutil
from hashlib import sha256
from pathlib import Path

import pytest

from _research.dnrd5.canonical_json import canonical_bytes, canonical_sha256, parse_canonical
from _research.dnrd5.independent_q1_gateway_root import IndependentQ1Refusal, close_q1_gateway_root, verify_q1_gateway_root
from _research.dnrd5.provider_gateway import Dnrd5ProviderConfig, HttpObservation
from _research.dnrd5.q1_provider_gateway import Q1CorpusMaterial, Q1ProviderGateway, build_q1_request
from _research.dnrd5.q1_qualification import FALSIFIED, INCONCLUSIVE, Q1_NAMESPACE, Q1_SCHEMA, Q1Refusal, REPRODUCED, VOID, derive_q1_call_order, make_q1_start_marker, validate_q1_plan

MODEL = "q1-test-model"

def _observations(*, mismatch: bool = False, raw: bytes | None = None) -> tuple[HttpObservation,...]:
    observations=[]
    for index in range(96):
        if raw is not None:
            observations.append(HttpObservation(200,raw,"application/json","q1-test")); continue
        answer="B" if mismatch and index==1 else "A"
        content=' { "answer" : "'+answer+'" } '
        envelope=(f'{{ "usage" : {{"completion_tokens":1,"prompt_tokens":1,"total_tokens":2}}, "choices" : [ {{ "message" : {{ "content" : {json.dumps(content)} }}, "finish_reason":"stop" }} ], "model" : "{MODEL}" }}').encode()
        observations.append(HttpObservation(200,envelope,"application/json","q1-test"))
    return tuple(observations)

def _hash(value: bytes | str) -> str: return sha256(value if type(value) is bytes else value.encode()).hexdigest()
def _source(tag: str) -> dict[str,str]: return {"commit":_hash(tag)[:40],"tree":_hash(tag+"tree")[:40],"ci_receipt_sha256":_hash(tag+"ci"),"ci_terminal":"FIRST_ATTEMPT_SUCCESSFUL_CI_BUILD"}
def _materials() -> list[Q1CorpusMaterial]:
    rows=[]
    for i in range(24):
        kind=("PRE_OUTCOME_TRAJECTORY","REVISION_PROPOSAL","FRESH_PROBE")[i%3]
        model_input={"publicTask":{"ordinal":i},"behaviorProjection":{"kind":"q1"}} if kind=="PRE_OUTCOME_TRAJECTORY" else ({"sealedTrajectory":{"ordinal":i},"assignedFeedback":{"signal":"public"},"revisionRequest":{"kind":"q1"}} if kind=="REVISION_PROPOSAL" else {"behaviorProjection":{"kind":"q1"},"freshProbe":{"ordinal":i}})
        schema={"type":"object","properties":{"answer":{"type":"string","minLength":1}},"required":["answer"],"additionalProperties":False}
        rows.append(Q1CorpusMaterial(f"QCASE-{i+1:03d}",b"return answer",canonical_bytes(model_input),canonical_bytes(schema),bytes([i+1])*8,64))
    return rows
def _setup():
    config=Dnrd5ProviderConfig("http://127.0.0.1:9999/v1/chat/completions",MODEL); materials=_materials()
    declared=canonical_bytes({"boundary":"FINITE_DECLARED_CONTROL_CONTRACT_NOT_OBSERVED_PROOF","dedicated_process":True,"dedicated_node":True,"dedicated_gpu":True,"prefix_cache":False,"max_num_seqs":1,"other_inference_processes":0})
    identities={"endpoint_sha256":config.endpoint.encode(),"model_identity_sha256":canonical_bytes({"model":MODEL}),"runtime_identity_sha256":canonical_bytes({"runtime":"test"}),"tls_identity_sha256":canonical_bytes({"tls":"test"}),"declared_isolation_contract_sha256":declared}
    corpus=[]
    for i,material in enumerate(materials):
        request=build_q1_request(config,("PRE_OUTCOME_TRAJECTORY","REVISION_PROPOSAL","FRESH_PROBE")[i%3],material)
        corpus.append({"case_id":material.case_id,"call_class":("PRE_OUTCOME_TRAJECTORY","REVISION_PROPOSAL","FRESH_PROBE")[i%3],"request_sha256":_hash(request),"instruction_sha256":_hash(material.instruction_bytes),"model_input_sha256":_hash(material.model_input_bytes),"response_schema_sha256":_hash(material.response_schema_bytes),"rng_sha256":_hash(material.rng_bytes),"max_output_tokens":64})
    seed=bytes.fromhex("12"*32); attempts=[f"DNRD5-Q1-{case['case_id'][-3:]}-R{rep:03d}" for case in corpus for rep in range(1,5)]
    manifest=canonical_bytes({"schema_version":"hswm-dnrd5-q1-corpus-manifest/v1","corpus":corpus}); genesis=canonical_bytes({"schema_version":"q1-test-root-genesis/v1"})
    plan=canonical_bytes({"schema_version":Q1_SCHEMA,"namespace":Q1_NAMESPACE,"source":_source("gateway"),"gateway_version":"hswm-dnrd5-q1-provider-gateway/v2","corpus_manifest_sha256":_hash(manifest),"corpus":corpus,"replicates":4,"call_order":derive_q1_call_order(attempts,seed),"call_order_algorithm":"FROZEN_SHA256_FISHER_YATES_V2","call_order_seed_hex":seed.hex(),"call_order_seed_sha256":_hash(seed),"budget":96,"zero_retry":True,"identities":{key:_hash(value) for key,value in identities.items()},"verifier":{"source":_source("verifier"),"build_output_sha256":_hash("build")},"evidence_root_genesis_sha256":_hash(genesis),"comparator":"EXACT_ASSISTANT_CONTENT_UTF8_WITH_CANONICAL_STRUCTURED_DIAGNOSTIC","allowed_terminals":[REPRODUCED,FALSIFIED,INCONCLUSIVE,VOID],"nonclaims":["NOT_A_DNRD5_300_BLOCK_OCCURRENCE_CALL_OR_PILOT_EFFECT_DATA","NOT_SOURCE_A_AUTHORIZATION_OR_SOURCE_A_FREEZE","NOT_PROOF_OF_PROVIDER_INTERNAL_CACHE_SCHEDULING_OR_GLOBAL_DETERMINISM","NOT_PROOF_OF_NO_INTERFERENCE_OR_HSWM_CAUSAL_LEARNING","NOT_EXTERNAL_CI_OR_SOURCE_PROVENANCE_ATTESTATION","NOT_OBSERVED_ISOLATION_OR_AUTHORIZATION_TO_DISPATCH","NOT_A_PROVIDER_DISPATCH_OR_EXTERNAL_PROVIDER_OBSERVATION"]})
    receipt=canonical_bytes({"schema_version":"hswm-dnrd5-q1-observed-isolation-receipt/v1","receipt_kind":"OBSERVED_PRE_DISPATCH_FINITE_CONTROL","declared_isolation_contract_sha256":_hash(declared),"dedicated_process":True,"dedicated_node":True,"dedicated_gpu":True,"prefix_cache":False,"max_num_seqs":1,"other_inference_processes":0,"boundary":"FINITE_OBSERVED_CONTROLS_NOT_NO_INTERFERENCE_PROOF"})
    return config,materials,identities,manifest,genesis,plan,receipt

def _gateway(root: Path, *, observations: tuple[HttpObservation,...], receipt: bytes | None = None) -> Q1ProviderGateway:
    config,materials,identities,manifest,genesis,plan,observed=_setup()
    return Q1ProviderGateway(root,plan,make_q1_start_marker(plan),config,identity_bytes=identities,corpus_manifest_bytes=manifest,root_genesis_bytes=genesis,observed_isolation_receipt=observed if receipt is None else receipt,offline_observations=observations)

def test_source_stage_preflight_and_96_slot_opaque_envelope(tmp_path: Path):
    config,materials,identities,manifest,genesis,plan,receipt=_setup(); root=tmp_path/"q1"
    gateway=Q1ProviderGateway(root,plan,make_q1_start_marker(plan),config,identity_bytes=identities,corpus_manifest_bytes=manifest,root_genesis_bytes=genesis,observed_isolation_receipt=receipt,offline_observations=_observations())
    output=gateway.execute_all(materials)
    rows=[parse_canonical(line) for line in (root/"q1_attempts.jsonl").read_bytes().rstrip(b"\n").split(b"\n")]
    assert rows[0]["record_type"]=="Q1_MARKER" and len(rows[0]["request_sha256s"])==24 and len(output)==96
    assert all((root/"content"/digest).is_file() for digest in rows[0]["request_sha256s"])
    assert verify_q1_gateway_root(root)["terminal"] == REPRODUCED
    with pytest.raises(Q1Refusal,match="single-use"):
        gateway.execute_all(materials)
    assert len(output)==96

def test_source_stage_exact_utf8_mismatch_is_replay_falsified(tmp_path: Path):
    gateway=_gateway(tmp_path/"q1",observations=_observations(mismatch=True))
    gateway.execute_all(_materials())
    assert verify_q1_gateway_root(tmp_path/"q1")["terminal"]==FALSIFIED

def test_observed_receipt_refuses_before_root_or_dispatch(tmp_path: Path):
    _,_,_,_,_,_,receipt=_setup(); bad=parse_canonical(receipt); bad["max_num_seqs"]=2
    with pytest.raises(Q1Refusal,match="observed isolation"):
        _gateway(tmp_path/"never-created",observations=_observations(),receipt=canonical_bytes(bad))
    assert not (tmp_path/"never-created").exists()

def test_source_stage_has_no_network_callback_or_default_observations(tmp_path: Path):
    config,_,identities,manifest,genesis,plan,receipt=_setup()
    with pytest.raises(Q1Refusal,match="offline observations"):
        Q1ProviderGateway(tmp_path/"never-created",plan,make_q1_start_marker(plan),config,identity_bytes=identities,corpus_manifest_bytes=manifest,root_genesis_bytes=genesis,observed_isolation_receipt=receipt)
    assert not (tmp_path/"never-created").exists()

@pytest.mark.parametrize("tamper",[lambda p:p.__setitem__("call_order",list(reversed(p["call_order"]))),lambda p:p.__setitem__("corpus_manifest_sha256","0"*64),lambda p:p["source"].__setitem__("commit","0"*40)])
def test_schema_rejects_order_placeholder_and_uncommitted_identity(tamper):
    *_,plan,_=_setup(); value=parse_canonical(plan); tamper(value)
    with pytest.raises(Q1Refusal): validate_q1_plan(canonical_bytes(value))

def test_duplicate_key_nonfinite_and_tautological_schema_are_refused(tmp_path: Path):
    duplicate=b'{"model":"q1-test-model","model":"q1-test-model","choices":[],"usage":{}}'
    gateway=_gateway(tmp_path/"q1",observations=_observations(raw=duplicate)); gateway.execute_all(_materials())
    rows=(tmp_path/"q1"/"q1_attempts.jsonl").read_bytes()
    assert b'"outcome":"FAILED"' in rows
    assert verify_q1_gateway_root(tmp_path/"q1")["terminal"]==INCONCLUSIVE
    config,materials,*_=_setup()
    bad=Q1CorpusMaterial(materials[0].case_id,materials[0].instruction_bytes,materials[0].model_input_bytes,canonical_bytes({"type":"object"}),materials[0].rng_bytes,64)
    with pytest.raises(Q1Refusal,match="schema"): build_q1_request(config,"PRE_OUTCOME_TRAJECTORY",bad)

def _rechain(root: Path, rows: list[dict]) -> None:
    previous="0"*64
    for ordinal,row in enumerate(rows,1):
        row["ordinal"]=ordinal; row["previous_record_sha256"]=previous
        row["record_sha256"]=canonical_sha256({key:value for key,value in row.items() if key!="record_sha256"})
        previous=row["record_sha256"]
    (root/"q1_attempts.jsonl").write_bytes(b"\n".join(canonical_bytes(row) for row in rows)+b"\n")

def test_independent_closure_rejects_reorder_unknown_row_and_missing_identity_blob(tmp_path: Path):
    config,materials,identities,manifest,genesis,plan,receipt=_setup(); base=tmp_path/"base"
    Q1ProviderGateway(base,plan,make_q1_start_marker(plan),config,identity_bytes=identities,corpus_manifest_bytes=manifest,root_genesis_bytes=genesis,observed_isolation_receipt=receipt,offline_observations=_observations()).execute_all(materials)
    for name,mutate in (
        ("reordered",lambda rows: rows.__setitem__(slice(1,3),[rows[2],rows[1]])),
        ("unknown",lambda rows: rows[1].__setitem__("unknown",True)),
        ("terminal-class",lambda rows: rows[2].__setitem__("call_class","INVALID_CALL_CLASS")),
        ("replicate",lambda rows: rows[1].__setitem__("replicate",99)),
        ("schema-length",lambda rows: rows[1]["response_schema"].__setitem__("byte_length",rows[1]["response_schema"]["byte_length"]+1)),
        ("request-list",lambda rows: rows[0]["request_sha256s"].reverse()),
    ):
        root=tmp_path/name; shutil.copytree(base,root); rows=[parse_canonical(line) for line in (root/"q1_attempts.jsonl").read_bytes().rstrip(b"\n").split(b"\n")]; mutate(rows); _rechain(root,rows)
        assert close_q1_gateway_root(root)["terminal"].startswith("VOID")
    for name,mutate in (
        ("short",lambda rows: rows.pop()),
        ("long",lambda rows: rows.append(dict(rows[-1]))),
    ):
        root=tmp_path/name; shutil.copytree(base,root); rows=[parse_canonical(line) for line in (root/"q1_attempts.jsonl").read_bytes().rstrip(b"\n").split(b"\n")]; mutate(rows); _rechain(root,rows)
        assert close_q1_gateway_root(root)["terminal"].startswith("VOID")
    missing=tmp_path/"missing"; shutil.copytree(base,missing); plan_row=parse_canonical((missing/"q1_attempts.jsonl").read_bytes().split(b"\n")[0]); plan_value=parse_canonical((missing/"content"/plan_row["plan"]["sha256"]).read_bytes()); (missing/"content"/plan_value["identities"]["runtime_identity_sha256"]).unlink()
    assert close_q1_gateway_root(missing)["terminal"].startswith("VOID")

def test_manifest_mismatch_and_recursive_schema_bound_tamper_refuse_before_dispatch(tmp_path: Path):
    config,materials,identities,manifest,genesis,plan,receipt=_setup()
    wrong=canonical_bytes({"schema_version":"hswm-dnrd5-q1-corpus-manifest/v1","corpus":[]})
    with pytest.raises(Q1Refusal,match="manifest"):
        Q1ProviderGateway(tmp_path/"no-root",plan,make_q1_start_marker(plan),config,identity_bytes=identities,corpus_manifest_bytes=wrong,root_genesis_bytes=genesis,observed_isolation_receipt=receipt,offline_observations=_observations())
    nested={"type":"object","properties":{"items":{"type":"array","minItems":2,"maxItems":1,"items":{"type":"integer","minimum":3,"maximum":2}}},"required":["items"],"additionalProperties":False}
    bad=Q1CorpusMaterial(materials[0].case_id,materials[0].instruction_bytes,materials[0].model_input_bytes,canonical_bytes(nested),materials[0].rng_bytes,64)
    with pytest.raises(Q1Refusal,match="schema"): build_q1_request(config,"PRE_OUTCOME_TRAJECTORY",bad)
    unsupported={"type":"object","properties":{"answer":{"type":"string","pattern":"^A$"}},"required":["answer"],"additionalProperties":False}
    bad_keyword=Q1CorpusMaterial(materials[0].case_id,materials[0].instruction_bytes,materials[0].model_input_bytes,canonical_bytes(unsupported),materials[0].rng_bytes,64)
    with pytest.raises(Q1Refusal,match="schema"): build_q1_request(config,"PRE_OUTCOME_TRAJECTORY",bad_keyword)
    supported={"type":"object","properties":{"items":{"type":"array","minItems":1,"maxItems":2,"items":{"type":"object","properties":{"score":{"type":"integer","minimum":0,"maximum":1},"note":{"type":"null"}},"required":["score","note"],"additionalProperties":False}}},"required":["items"],"additionalProperties":False}
    nested_ok=Q1CorpusMaterial(materials[0].case_id,materials[0].instruction_bytes,materials[0].model_input_bytes,canonical_bytes(supported),materials[0].rng_bytes,64)
    assert build_q1_request(config,"PRE_OUTCOME_TRAJECTORY",nested_ok)
