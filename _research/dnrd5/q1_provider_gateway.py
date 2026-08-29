"""Q1 source-stage offline observation replay with no network callback or resume."""
from __future__ import annotations

import fcntl
import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from _research.dnrd5.canonical_json import canonical_bytes, canonical_sha256, parse_canonical
from _research.dnrd5.provider_gateway import Dnrd5ProviderConfig, HttpObservation
from _research.dnrd5.q1_qualification import CALL_CLASSES, Q1_NAMESPACE, Q1Refusal, make_q1_start_marker, validate_q1_plan, validate_q1_start_marker

LEDGER_SCHEMA = "hswm-dnrd5-q1-attempt-ledger/v2"
ZERO = "0" * 64
SYSTEM_MESSAGE = "Act only as the bounded DNRD-5 token-native model function. Read the declared input, follow its instruction, and return exactly one object satisfying the supplied strict JSON schema."

@dataclass(frozen=True, slots=True)
class Q1CorpusMaterial:
    case_id: str; instruction_bytes: bytes; model_input_bytes: bytes; response_schema_bytes: bytes; rng_bytes: bytes; max_output_tokens: int

def _desc(raw: bytes) -> dict[str, Any]: return {"sha256":sha256(raw).hexdigest(),"byte_length":len(raw)}
def _sync_dir(path: Path) -> None:
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)
def _put(root: Path, raw: bytes) -> None:
    target=root/"content"/sha256(raw).hexdigest()
    if target.exists():
        if target.read_bytes()!=raw: raise Q1Refusal("content-address collision")
        return
    fd,tmp=tempfile.mkstemp(dir=root/"content",prefix=".q1-")
    try:
        with os.fdopen(fd,"wb") as handle: handle.write(raw); handle.flush(); os.fsync(handle.fileno())
        try: os.link(tmp,target)
        except FileExistsError:
            if target.read_bytes()!=raw: raise Q1Refusal("content-address collision")
    finally:
        try: os.unlink(tmp)
        except FileNotFoundError: pass
    _sync_dir(root/"content")
def _append(root: Path, core: dict[str,Any]) -> dict[str,Any]:
    ledger=root/"q1_attempts.jsonl"; fd=os.open(ledger,os.O_RDWR)
    with os.fdopen(fd,"r+b") as handle:
        fcntl.flock(handle.fileno(),fcntl.LOCK_EX); raw=handle.read(); previous=ZERO; ordinal=1
        if raw:
            if not raw.endswith(b"\n"): raise Q1Refusal("ledger framing drift")
            for line in raw[:-1].split(b"\n"):
                row=parse_canonical(line); body={k:v for k,v in row.items() if k!="record_sha256"}
                if type(row) is not dict or row.get("ordinal")!=ordinal or row.get("previous_record_sha256")!=previous or row.get("record_sha256")!=canonical_sha256(body): raise Q1Refusal("ledger chain drift")
                previous=row["record_sha256"]; ordinal+=1
        row={**core,"ordinal":ordinal,"previous_record_sha256":previous}; row["record_sha256"]=canonical_sha256(row)
        handle.seek(0,2); handle.write(canonical_bytes(row)+b"\n"); handle.flush(); os.fsync(handle.fileno()); fcntl.flock(handle.fileno(),fcntl.LOCK_UN)
    _sync_dir(root); return row
def _strict(raw: bytes) -> Any:
    def unique(pairs: Any) -> dict[str,Any]:
        result={}
        for key,value in pairs:
            if key in result: raise ValueError("duplicate JSON key")
            result[key]=value
        return result
    return json.loads(raw.decode("utf-8"),object_pairs_hook=unique,parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
def _schema(schema: Any, value: Any | None = None, *, instance: bool = False) -> None:
    if type(schema) is not dict or schema.get("type") not in {"object","array","string","integer","boolean","null"}: raise Q1Refusal("unsupported/tautological response schema")
    kind=schema["type"]
    if kind == "object":
        required=schema.get("required")
        if set(schema)!={"type","properties","required","additionalProperties"} or type(schema.get("properties")) is not dict or not schema["properties"] or type(required) is not list or len(required)!=len(set(required)) or set(required) != set(schema["properties"]) or schema.get("additionalProperties") is not False: raise Q1Refusal("unsupported/tautological response schema")
        for child in schema["properties"].values(): _schema(child)
    elif kind == "array":
        if not {"type","items"}<=set(schema)<={"type","items","minItems","maxItems"} or type(schema["items"]) is not dict or type(schema.get("minItems",0)) is not int or type(schema.get("maxItems",65536)) is not int or schema.get("minItems",0)<0 or schema.get("maxItems",65536)<schema.get("minItems",0): raise Q1Refusal("unsupported/tautological response schema")
        _schema(schema["items"])
    elif kind == "string" and (not {"type"}<=set(schema)<={"type","minLength","maxLength"} or type(schema.get("minLength",0)) is not int or type(schema.get("maxLength",65536)) is not int or schema.get("minLength",0)<0 or schema.get("maxLength",65536)<schema.get("minLength",0)): raise Q1Refusal("unsupported/tautological response schema")
    elif kind == "integer" and (not {"type"}<=set(schema)<={"type","minimum","maximum"} or type(schema.get("minimum",-(2**53-1))) is not int or type(schema.get("maximum",2**53-1)) is not int or schema.get("minimum",-(2**53-1))>schema.get("maximum",2**53-1)): raise Q1Refusal("unsupported/tautological response schema")
    elif kind in {"boolean","null"} and set(schema)!={"type"}: raise Q1Refusal("unsupported/tautological response schema")
    if not instance: return
    if kind=="object":
        props=schema.get("properties"); required=schema.get("required")
        if type(value) is not dict or type(props) is not dict or not props or type(required) is not list or set(required)!=set(props) or schema.get("additionalProperties") is not False or set(value)!=set(props): raise Q1Refusal("response object schema mismatch")
        for key,child in props.items(): _schema(child,value[key],instance=True)
    elif kind=="string":
        if type(value) is not str or not schema.get("minLength",0) <= len(value) <= schema.get("maxLength",65536): raise Q1Refusal("response string schema mismatch")
    elif kind=="integer" and (type(value) is not int or not schema.get("minimum",-(2**53-1)) <= value <= schema.get("maximum",2**53-1)): raise Q1Refusal("response integer schema mismatch")
    elif kind=="boolean" and type(value) is not bool: raise Q1Refusal("response boolean schema mismatch")
    elif kind=="null" and value is not None: raise Q1Refusal("response null schema mismatch")
    elif kind=="array":
        if type(value) is not list or not schema.get("minItems",0)<=len(value)<=schema.get("maxItems",65536): raise Q1Refusal("response array schema mismatch")
        for item in value: _schema(schema["items"],item,instance=True)

def _manifest(raw: bytes, corpus: list[dict[str, Any]]) -> None:
    try: manifest=parse_canonical(raw)
    except Exception as error: raise Q1Refusal("corpus manifest must be canonical JSON") from error
    if type(manifest) is not dict or set(manifest)!={"schema_version","corpus"} or manifest.get("schema_version")!="hswm-dnrd5-q1-corpus-manifest/v1" or manifest.get("corpus") != corpus:
        raise Q1Refusal("corpus manifest does not bind the exact Q1 corpus")
def _model_input(call_class: str, value: Any) -> None:
    if call_class not in CALL_CLASSES or type(value) is not dict or not value: raise Q1Refusal("model input class/shape drift")
    needed={"PRE_OUTCOME_TRAJECTORY":{"publicTask","behaviorProjection"},"REVISION_PROPOSAL":{"sealedTrajectory","assignedFeedback","revisionRequest"},"FRESH_PROBE":{"behaviorProjection","freshProbe"}}[call_class]
    if set(value)!=needed: raise Q1Refusal("model input is not the bounded Q1 call-class shape")
def build_q1_request(config: Dnrd5ProviderConfig, call_class: str, material: Q1CorpusMaterial) -> bytes:
    try:
        model_input=parse_canonical(material.model_input_bytes); response_schema=parse_canonical(material.response_schema_bytes); instruction=material.instruction_bytes.decode("utf-8")
    except Exception as error: raise Q1Refusal("Q1 material must be canonical JSON/UTF-8") from error
    _model_input(call_class,model_input); _schema(response_schema)
    if not instruction or not material.rng_bytes or material.max_output_tokens not in {64,128,256}: raise Q1Refusal("Q1 material bounds drifted")
    seed=int.from_bytes(sha256(material.rng_bytes).digest()[:6],"big")
    return canonical_bytes({"chat_template_kwargs":{"enable_thinking":False},"logprobs":False,"max_tokens":material.max_output_tokens,"messages":[{"content":SYSTEM_MESSAGE,"role":"system"},{"content":canonical_bytes({"contractVersion":"hswm-dnrd5-q1-model-input/v2","callClass":call_class,"instruction":instruction,"input":model_input}).decode(),"role":"user"}],"model":config.expected_model,"n":1,"response_format":{"type":"json_schema","json_schema":{"name":"hswm_dnrd5_q1_"+call_class.lower(),"schema":response_schema,"strict":True}},"seed":seed,"stream":False,"temperature":0,"top_p":1})
def _validate_envelope(raw: bytes, status: int, model: str, schema_raw: bytes) -> tuple[bytes,bytes]:
    if status!=200: raise Q1Refusal("provider status is not 200")
    try: envelope=_strict(raw); schema=parse_canonical(schema_raw)
    except Exception as error: raise Q1Refusal("provider envelope/schema is not strict JSON") from error
    if type(envelope) is not dict or envelope.get("model")!=model: raise Q1Refusal("provider model identity drift")
    choices=envelope.get("choices"); usage=envelope.get("usage")
    if type(choices) is not list or len(choices)!=1 or type(choices[0]) is not dict or choices[0].get("finish_reason")!="stop" or type(choices[0].get("message")) is not dict or type(choices[0]["message"].get("content")) is not str: raise Q1Refusal("provider choice/finish/content drift")
    if type(usage) is not dict or any(type(usage.get(key)) is not int or usage[key]<0 for key in ("prompt_tokens","completion_tokens","total_tokens")) or usage["prompt_tokens"]+usage["completion_tokens"]!=usage["total_tokens"]: raise Q1Refusal("provider usage drift")
    content=choices[0]["message"]["content"].encode("utf-8",errors="strict")
    try: parsed=_strict(content); _schema(schema,parsed,instance=True)
    except Exception as error: raise Q1Refusal("assistant structured content/schema drift") from error
    return content,canonical_bytes(parsed)
def _observed_receipt(raw: bytes, declared_digest: str) -> dict[str,Any]:
    try: receipt=parse_canonical(raw)
    except Exception as error: raise Q1Refusal("observed isolation receipt must be canonical JSON") from error
    required={"schema_version","receipt_kind","declared_isolation_contract_sha256","dedicated_process","dedicated_node","dedicated_gpu","prefix_cache","max_num_seqs","other_inference_processes","boundary"}
    if type(receipt) is not dict or set(receipt)!=required or receipt.get("schema_version")!="hswm-dnrd5-q1-observed-isolation-receipt/v1" or receipt.get("receipt_kind")!="OBSERVED_PRE_DISPATCH_FINITE_CONTROL" or receipt.get("declared_isolation_contract_sha256")!=declared_digest or receipt.get("dedicated_process") is not True or receipt.get("dedicated_node") is not True or receipt.get("dedicated_gpu") is not True or receipt.get("prefix_cache") is not False or receipt.get("max_num_seqs")!=1 or receipt.get("other_inference_processes")!=0 or receipt.get("boundary")!="FINITE_OBSERVED_CONTROLS_NOT_NO_INTERFERENCE_PROOF": raise Q1Refusal("observed isolation receipt does not satisfy strict finite control fields")
    return receipt

class Q1ProviderGateway:
    def __init__(self, root: Path, plan_raw: bytes, marker_raw: bytes, config: Dnrd5ProviderConfig, *, identity_bytes: Mapping[str,bytes], corpus_manifest_bytes: bytes, root_genesis_bytes: bytes, observed_isolation_receipt: bytes, offline_observations: Sequence[HttpObservation]|None=None) -> None:
        self.plan=validate_q1_plan(plan_raw); validate_q1_start_marker(marker_raw,plan_raw)
        expected={"endpoint_sha256","model_identity_sha256","runtime_identity_sha256","tls_identity_sha256","declared_isolation_contract_sha256"}
        if set(identity_bytes)!=expected or any(sha256(identity_bytes[name]).hexdigest()!=self.plan["identities"][name] for name in expected) or sha256(config.endpoint.encode()).hexdigest()!=self.plan["identities"]["endpoint_sha256"]: raise Q1Refusal("runtime identity binding drift")
        try: model_identity=parse_canonical(identity_bytes["model_identity_sha256"])
        except Exception as error: raise Q1Refusal("model identity must be canonical JSON") from error
        if type(model_identity) is not dict or model_identity.get("model")!=config.expected_model: raise Q1Refusal("model identity does not bind the configured model")
        if sha256(corpus_manifest_bytes).hexdigest()!=self.plan["corpus_manifest_sha256"] or sha256(root_genesis_bytes).hexdigest()!=self.plan["evidence_root_genesis_sha256"]: raise Q1Refusal("corpus manifest/root genesis binding drift")
        _manifest(corpus_manifest_bytes,self.plan["corpus"])
        declared=identity_bytes["declared_isolation_contract_sha256"]
        try: declared_value=parse_canonical(declared)
        except Exception as error: raise Q1Refusal("declared isolation contract must be canonical JSON") from error
        if type(declared_value) is not dict or declared_value != {"boundary":"FINITE_DECLARED_CONTROL_CONTRACT_NOT_OBSERVED_PROOF","dedicated_process":True,"dedicated_node":True,"dedicated_gpu":True,"prefix_cache":False,"max_num_seqs":1,"other_inference_processes":0}: raise Q1Refusal("declared isolation contract drifted")
        _observed_receipt(observed_isolation_receipt,sha256(declared).hexdigest())
        if type(offline_observations) not in {tuple,list} or len(offline_observations)!=96: raise Q1Refusal("source-stage Q1 requires exactly 96 offline observations and has no network callback")
        for observation in offline_observations:
            if type(observation) is not HttpObservation or type(observation.status) is not int or type(observation.body) is not bytes or len(observation.body)>config.max_response_bytes or observation.response_content_type is not None and type(observation.response_content_type) is not str or observation.provider_request_id is not None and type(observation.provider_request_id) is not str: raise Q1Refusal("offline observation fixture shape drifted")
        if root.exists() or not root.parent.is_dir(): raise Q1Refusal("Q1 root must be fresh")
        root.mkdir(mode=0o700); (root/"content").mkdir(mode=0o700); (root/"q1_attempts.jsonl").touch(mode=0o600); (root/"dispatch.lock").touch(mode=0o600); _sync_dir(root/"content"); _sync_dir(root)
        self.root,self.plan_raw,self.config,self.offline_observations=root,plan_raw,config,tuple(offline_observations); self.ids={name:sha256(raw).hexdigest() for name,raw in identity_bytes.items()}; self.receipt=observed_isolation_receipt
        for raw in (plan_raw,marker_raw,corpus_manifest_bytes,root_genesis_bytes,observed_isolation_receipt,*identity_bytes.values()): _put(root,raw)
    def _request(self, case: Mapping[str,Any], material: Q1CorpusMaterial) -> bytes:
        request=build_q1_request(self.config,case["call_class"],material)
        expected={"instruction_sha256":sha256(material.instruction_bytes).hexdigest(),"model_input_sha256":sha256(material.model_input_bytes).hexdigest(),"response_schema_sha256":sha256(material.response_schema_bytes).hexdigest(),"rng_sha256":sha256(material.rng_bytes).hexdigest(),"request_sha256":sha256(request).hexdigest()}
        if any(case[name]!=digest for name,digest in expected.items()) or case["max_output_tokens"]!=material.max_output_tokens: raise Q1Refusal("raw-material/request binding drift")
        return request
    def execute_all(self, corpus: Sequence[Q1CorpusMaterial]) -> tuple[dict[str,Any],...]:
        if (self.root/"q1_attempts.jsonl").read_bytes(): raise Q1Refusal("Q1 source-stage root is single-use and cannot resume")
        if len(corpus)!=24 or len({m.case_id for m in corpus})!=24: raise Q1Refusal("Q1 requires exactly 24 unique raw cases")
        cases={case["case_id"]:case for case in self.plan["corpus"]}; materials={m.case_id:m for m in corpus}
        if set(cases)!=set(materials): raise Q1Refusal("corpus case set drift")
        requests={}
        for case_id,material in materials.items():
            request=self._request(cases[case_id],material); requests[case_id]=request
            for raw in (material.instruction_bytes,material.model_input_bytes,material.response_schema_bytes,material.rng_bytes,request): _put(self.root,raw)
        _append(self.root,{"schema_version":LEDGER_SCHEMA,"namespace":Q1_NAMESPACE,"record_type":"Q1_MARKER","plan":_desc(self.plan_raw),"marker":_desc(make_q1_start_marker(self.plan_raw)),"corpus_manifest":_desc((self.root/"content"/self.plan["corpus_manifest_sha256"]).read_bytes()),"root_genesis":_desc((self.root/"content"/self.plan["evidence_root_genesis_sha256"]).read_bytes()),"observed_isolation_receipt":_desc(self.receipt),"all_request_blobs_durable":True,"request_sha256s":[sha256(requests[case["case_id"]]).hexdigest() for case in self.plan["corpus"]],"terminal":"ALL_24_EXACT_CONSTRUCTED_REQUEST_BLOBS_FSYNCED_BEFORE_FIRST_START"})
        output=[]
        for attempt_id in self.plan["call_order"]:
            case_id="QCASE-"+attempt_id[9:12]
            output.append(self._one(attempt_id,cases[case_id],materials[case_id],requests[case_id]))
        return tuple(output)
    def _one(self, attempt_id: str, case: Mapping[str,Any], material: Q1CorpusMaterial, request: bytes) -> dict[str,Any]:
        fd=os.open(self.root/"dispatch.lock",os.O_RDWR)
        with os.fdopen(fd,"r+b") as lock:
            fcntl.flock(lock.fileno(),fcntl.LOCK_EX); rows=[parse_canonical(line) for line in (self.root/"q1_attempts.jsonl").read_bytes().rstrip(b"\n").split(b"\n")]; starts=[row for row in rows if row.get("record_type")=="START"]
            if len(starts)>=96 or attempt_id!=self.plan["call_order"][len(starts)]: raise Q1Refusal("order/resume/replacement breach")
            case_id="QCASE-"+attempt_id[9:12]; start=_append(self.root,{"schema_version":LEDGER_SCHEMA,"namespace":Q1_NAMESPACE,"record_type":"START","attempt_id":attempt_id,"case_id":case_id,"replicate":int(attempt_id[-3:]),"call_class":case["call_class"],"request":_desc(request),"response_schema":_desc(material.response_schema_bytes),"plan_schema":self.plan["schema_version"],"identities":self.ids,"observed_isolation_receipt_sha256":sha256(self.receipt).hexdigest(),"retry":"NONE","terminal":"DURABLY_VISIBLE_BEFORE_SINGLE_OFFLINE_OBSERVATION_CONSUMPTION"})
            observed=None
            try:
                observed=self.offline_observations[len(starts)]
                content,structured=_validate_envelope(observed.body,observed.status,self.config.expected_model,material.response_schema_bytes)
                for raw in (observed.body,content,structured): _put(self.root,raw)
                return _append(self.root,{"schema_version":LEDGER_SCHEMA,"namespace":Q1_NAMESPACE,"record_type":"TERMINAL","attempt_id":attempt_id,"case_id":case_id,"replicate":int(attempt_id[-3:]),"call_class":case["call_class"],"start_record_sha256":start["record_sha256"],"offline_observation":{"status":observed.status,"response_content_type":observed.response_content_type,"provider_request_id":observed.provider_request_id},"raw_envelope":_desc(observed.body),"model_content_utf8":_desc(content),"structured_content":_desc(structured),"outcome":"SUCCEEDED","retry":"NONE","retry_allowed":False,"terminal":"OFFLINE_OBSERVATION_SLOT_CONSUMED_NO_REPLAY_OR_REPLACEMENT"})
            except Exception as error:
                if observed is not None: _put(self.root,observed.body)
                return _append(self.root,{"schema_version":LEDGER_SCHEMA,"namespace":Q1_NAMESPACE,"record_type":"TERMINAL","attempt_id":attempt_id,"case_id":case_id,"replicate":int(attempt_id[-3:]),"call_class":case["call_class"],"start_record_sha256":start["record_sha256"],"offline_observation":None if observed is None else {"status":observed.status,"response_content_type":observed.response_content_type,"provider_request_id":observed.provider_request_id},"raw_envelope":None if observed is None else _desc(observed.body),"outcome":"FAILED","failure_code":type(error).__name__.upper(),"retry":"NONE","retry_allowed":False,"terminal":"OFFLINE_OBSERVATION_SLOT_CONSUMED_NO_REPLAY_OR_REPLACEMENT"})
