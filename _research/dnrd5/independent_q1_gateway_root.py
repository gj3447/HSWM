"""Read-only Q1 closure; deliberately imports no Q1 producer or gateway module."""
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

from _research.dnrd5.canonical_json import canonical_bytes, canonical_sha256, parse_canonical

NAMESPACE="DNRD5-Q1-SOURCE-STAGE-ONLY/v2"; LEDGER_SCHEMA="hswm-dnrd5-q1-attempt-ledger/v2"; ZERO="0"*64
REPRODUCED="REPLAY_REPRODUCED_ON_FROZEN_Q1_SOURCE_STAGE_CORPUS"; FALSIFIED="REPLAY_FALSIFIED_ON_FROZEN_Q1_SOURCE_STAGE_CORPUS"; INCONCLUSIVE="INCONCLUSIVE_Q1_SOURCE_STAGE_REPLAY_EVIDENCE"; VOID="VOID_Q1_SOURCE_STAGE_PROTOCOL_LEDGER_HASH_ORDER_OR_RECEIPT_BREACH"
SYSTEM_MESSAGE="Act only as the bounded DNRD-5 token-native model function. Read the declared input, follow its instruction, and return exactly one object satisfying the supplied strict JSON schema."
class IndependentQ1Refusal(ValueError): pass
def _fail(detail: str) -> None: raise IndependentQ1Refusal(detail)
def _hex(value: Any, length: int) -> bool:
    return type(value) is str and len(value)==length and value!="0"*length and all(character in "0123456789abcdef" for character in value)
def _strict(raw: bytes) -> Any:
    def unique(pairs: Any) -> dict[str,Any]:
        answer={}
        for key,value in pairs:
            if key in answer: _fail("duplicate JSON key")
            answer[key]=value
        return answer
    try: return json.loads(raw.decode("utf-8"),object_pairs_hook=unique,parse_constant=lambda text: (_ for _ in ()).throw(ValueError(text)))
    except (UnicodeDecodeError,ValueError,json.JSONDecodeError) as error: _fail(f"not strict ordinary JSON: {error}")
def _blob(root: Path, digest: Any) -> bytes:
    if not _hex(digest,64): _fail("invalid blob digest")
    path=root/"content"/digest
    if not path.is_file(): _fail("required content blob missing")
    raw=path.read_bytes()
    if sha256(raw).hexdigest()!=digest: _fail("content blob hash drifted")
    return raw
def _desc(root: Path, descriptor: Any) -> bytes:
    if type(descriptor) is not dict or set(descriptor)!={"sha256","byte_length"}: _fail("descriptor shape drifted")
    raw=_blob(root,descriptor["sha256"])
    if type(descriptor["byte_length"]) is not int or descriptor["byte_length"]!=len(raw): _fail("descriptor length drifted")
    return raw
def _order(items: list[str], seed: bytes) -> list[str]:
    answer=list(items); counter=0
    for index in range(len(answer)-1,0,-1):
        stream=b""
        while len(stream)<8:
            stream+=sha256(b"HSWM-DNRD5-Q1-CALL-ORDER-V2\0"+seed+counter.to_bytes(8,"big")).digest(); counter+=1
        swap=int.from_bytes(stream[:8],"big")%(index+1); answer[index],answer[swap]=answer[swap],answer[index]
    return answer
def _schema(schema: Any, value: Any | None = None, *, instance: bool = True) -> None:
    if type(schema) is not dict or schema.get("type") not in {"object","array","string","integer","boolean","null"}: _fail("response schema is unsupported or tautological")
    kind=schema["type"]
    if kind=="object":
        required=schema.get("required")
        if set(schema)!={"type","properties","required","additionalProperties"} or type(schema.get("properties")) is not dict or not schema["properties"] or type(required) is not list or len(required)!=len(set(required)) or set(required)!=set(schema["properties"]) or schema.get("additionalProperties") is not False: _fail("response object schema drifted")
        for child in schema["properties"].values(): _schema(child,instance=False)
    elif kind=="array":
        if not {"type","items"}<=set(schema)<={"type","items","minItems","maxItems"} or type(schema.get("items")) is not dict or type(schema.get("minItems",0)) is not int or type(schema.get("maxItems",65536)) is not int or schema.get("minItems",0)<0 or schema.get("maxItems",65536)<schema.get("minItems",0): _fail("response array schema drifted")
        _schema(schema["items"],instance=False)
    elif kind=="string" and (not {"type"}<=set(schema)<={"type","minLength","maxLength"} or type(schema.get("minLength",0)) is not int or type(schema.get("maxLength",65536)) is not int or schema.get("minLength",0)<0 or schema.get("maxLength",65536)<schema.get("minLength",0)): _fail("response string bounds drifted")
    elif kind=="integer" and (not {"type"}<=set(schema)<={"type","minimum","maximum"} or type(schema.get("minimum",-(2**53-1))) is not int or type(schema.get("maximum",2**53-1)) is not int or schema.get("minimum",-(2**53-1))>schema.get("maximum",2**53-1)): _fail("response integer bounds drifted")
    elif kind in {"boolean","null"} and set(schema)!={"type"}: _fail("response scalar schema drifted")
    if not instance: return
    if kind=="object":
        if type(value) is not dict or set(value)!=set(schema["properties"]): _fail("response object instance drifted")
        for key,child in schema["properties"].items(): _schema(child,value[key])
    elif kind=="array":
        if type(value) is not list or not schema.get("minItems",0)<=len(value)<=schema.get("maxItems",65536): _fail("response array instance drifted")
        for item in value: _schema(schema["items"],item)
    elif kind=="string" and (type(value) is not str or not schema.get("minLength",0)<=len(value)<=schema.get("maxLength",65536)): _fail("response string instance drifted")
    elif kind=="integer" and (type(value) is not int or not schema.get("minimum",-(2**53-1))<=value<=schema.get("maximum",2**53-1)): _fail("response integer instance drifted")
    elif kind=="boolean" and type(value) is not bool: _fail("response boolean instance drifted")
    elif kind=="null" and value is not None: _fail("response null instance drifted")
def _request(root: Path, case: dict[str,Any], model: str) -> bytes:
    try: instruction=_blob(root,case["instruction_sha256"]).decode("utf-8"); model_input=parse_canonical(_blob(root,case["model_input_sha256"])); schema=parse_canonical(_blob(root,case["response_schema_sha256"])); rng=_blob(root,case["rng_sha256"])
    except Exception as error: _fail(f"raw request material drifted: {error}")
    required={"PRE_OUTCOME_TRAJECTORY":{"publicTask","behaviorProjection"},"REVISION_PROPOSAL":{"sealedTrajectory","assignedFeedback","revisionRequest"},"FRESH_PROBE":{"behaviorProjection","freshProbe"}}
    if case.get("call_class") not in required or type(model_input) is not dict or set(model_input)!=required[case["call_class"]] or not instruction or type(schema) is not dict: _fail("raw request semantic shape drifted")
    return canonical_bytes({"chat_template_kwargs":{"enable_thinking":False},"logprobs":False,"max_tokens":case["max_output_tokens"],"messages":[{"content":SYSTEM_MESSAGE,"role":"system"},{"content":canonical_bytes({"contractVersion":"hswm-dnrd5-q1-model-input/v2","callClass":case["call_class"],"instruction":instruction,"input":model_input}).decode(),"role":"user"}],"model":model,"n":1,"response_format":{"type":"json_schema","json_schema":{"name":"hswm_dnrd5_q1_"+case["call_class"].lower(),"schema":schema,"strict":True}},"seed":int.from_bytes(sha256(rng).digest()[:6],"big"),"stream":False,"temperature":0,"top_p":1})

def verify_q1_gateway_root(root: Path) -> dict[str,Any]:
    ledger=root/"q1_attempts.jsonl"
    if not root.is_dir() or not (root/"content").is_dir() or not ledger.is_file(): _fail("incomplete root")
    raw=ledger.read_bytes()
    if not raw.endswith(b"\n") or not raw[:-1]: _fail("ledger framing drifted")
    try: rows=[parse_canonical(line) for line in raw[:-1].split(b"\n")]
    except Exception as error: _fail(f"ledger canonical bytes malformed: {error}")
    if len(rows) != 193: _fail("Q1 closure requires marker plus exactly 96 START/TERMINAL pairs")
    previous=ZERO
    for ordinal,row in enumerate(rows,1):
        body={key:value for key,value in row.items() if key!="record_sha256"}
        if type(row) is not dict or row.get("schema_version")!=LEDGER_SCHEMA or row.get("namespace")!=NAMESPACE or row.get("ordinal")!=ordinal or row.get("previous_record_sha256")!=previous or row.get("record_sha256")!=canonical_sha256(body): _fail("ledger hash/order breach")
        previous=row["record_sha256"]
    marker=rows[0]
    needed={"schema_version","namespace","record_type","plan","marker","corpus_manifest","root_genesis","observed_isolation_receipt","all_request_blobs_durable","request_sha256s","terminal","ordinal","previous_record_sha256","record_sha256"}
    if set(marker)!=needed or marker.get("record_type")!="Q1_MARKER" or marker.get("all_request_blobs_durable") is not True or marker.get("terminal")!="ALL_24_EXACT_CONSTRUCTED_REQUEST_BLOBS_FSYNCED_BEFORE_FIRST_START": _fail("marker-first/durable-request breach")
    try: plan=parse_canonical(_desc(root,marker["plan"])); marker_bytes=_desc(root,marker["marker"])
    except Exception as error: _fail(f"plan/marker canonical bytes malformed: {error}")
    if type(plan) is not dict or plan.get("schema_version")!="hswm-dnrd5-q1-response-exactness/v2" or plan.get("namespace")!=NAMESPACE or plan.get("gateway_version")!="hswm-dnrd5-q1-provider-gateway/v2" or type(plan.get("corpus")) is not list or len(plan["corpus"])!=24 or plan.get("replicates")!=4 or plan.get("budget")!=96 or plan.get("zero_retry") is not True: _fail("plan boundary drifted")
    plan_keys={"schema_version","namespace","source","gateway_version","corpus_manifest_sha256","corpus","replicates","call_order","call_order_algorithm","call_order_seed_hex","call_order_seed_sha256","budget","zero_retry","identities","verifier","evidence_root_genesis_sha256","comparator","allowed_terminals","nonclaims"}
    if set(plan)!=plan_keys or plan.get("comparator")!="EXACT_ASSISTANT_CONTENT_UTF8_WITH_CANONICAL_STRUCTURED_DIAGNOSTIC" or plan.get("allowed_terminals")!=[REPRODUCED,FALSIFIED,INCONCLUSIVE,VOID] or plan.get("nonclaims") != ["NOT_A_DNRD5_300_BLOCK_OCCURRENCE_CALL_OR_PILOT_EFFECT_DATA","NOT_SOURCE_A_AUTHORIZATION_OR_SOURCE_A_FREEZE","NOT_PROOF_OF_PROVIDER_INTERNAL_CACHE_SCHEDULING_OR_GLOBAL_DETERMINISM","NOT_PROOF_OF_NO_INTERFERENCE_OR_HSWM_CAUSAL_LEARNING","NOT_EXTERNAL_CI_OR_SOURCE_PROVENANCE_ATTESTATION","NOT_OBSERVED_ISOLATION_OR_AUTHORIZATION_TO_DISPATCH","NOT_A_PROVIDER_DISPATCH_OR_EXTERNAL_PROVIDER_OBSERVATION"]: _fail("plan terminal/nonclaim/comparator drifted")
    case_keys={"case_id","call_class","request_sha256","instruction_sha256","model_input_sha256","response_schema_sha256","rng_sha256","max_output_tokens"}; valid_classes={"PRE_OUTCOME_TRAJECTORY","REVISION_PROPOSAL","FRESH_PROBE"}
    for case in plan["corpus"]:
        case_id=case.get("case_id") if type(case) is dict else None
        if type(case) is not dict or set(case)!=case_keys or type(case_id) is not str or not case_id.startswith("QCASE-") or len(case_id)!=9 or not case_id[-3:].isdigit() or case["call_class"] not in valid_classes or type(case["max_output_tokens"]) is not int or case["max_output_tokens"] not in {64,128,256} or any(not _hex(case[name],64) for name in case_keys-{"case_id","call_class","max_output_tokens"}): _fail("plan corpus case/hash/token drifted")
    if len({case["case_id"] for case in plan["corpus"]})!=24 or {case["call_class"] for case in plan["corpus"]}!=valid_classes: _fail("plan corpus identity/class drifted")
    def source_ok(source: Any) -> bool:
        return type(source) is dict and set(source)=={"commit","tree","ci_receipt_sha256","ci_terminal"} and _hex(source.get("commit"),40) and _hex(source.get("tree"),40) and _hex(source.get("ci_receipt_sha256"),64) and source.get("ci_terminal")=="FIRST_ATTEMPT_SUCCESSFUL_CI_BUILD"
    if not source_ok(plan.get("source")) or type(plan.get("verifier")) is not dict or set(plan["verifier"])!={"source","build_output_sha256"} or not source_ok(plan["verifier"].get("source")) or not _hex(plan["verifier"].get("build_output_sha256"),64): _fail("source/verifier build identity drifted")
    manifest_raw=_desc(root,marker["corpus_manifest"]); genesis_raw=_desc(root,marker["root_genesis"])
    if sha256(manifest_raw).hexdigest()!=plan.get("corpus_manifest_sha256") or sha256(genesis_raw).hexdigest()!=plan.get("evidence_root_genesis_sha256"): _fail("corpus manifest/root genesis drifted")
    try: manifest=parse_canonical(manifest_raw)
    except Exception as error: _fail(f"manifest canonical bytes malformed: {error}")
    if type(manifest) is not dict or set(manifest)!={"schema_version","corpus"} or manifest.get("schema_version")!="hswm-dnrd5-q1-corpus-manifest/v1" or manifest.get("corpus")!=plan["corpus"]: _fail("manifest/corpus semantic binding breach")
    if canonical_bytes({"schema_version":"hswm-dnrd5-q1-start-marker/v2","namespace":NAMESPACE,"q1_sha256":sha256(_desc(root,marker["plan"])).hexdigest(),"terminal":"Q1_MARKER_BOUND_AFTER_ALL_24_REQUEST_BLOBS_DURABLE_BEFORE_FIRST_START","nonclaims":plan.get("nonclaims")})!=marker_bytes: _fail("start marker binding drifted")
    identities=plan.get("identities")
    if type(identities) is not dict or set(identities)!={"endpoint_sha256","model_identity_sha256","runtime_identity_sha256","tls_identity_sha256","declared_isolation_contract_sha256"}: _fail("identity shape drifted")
    for digest in identities.values(): _blob(root,digest)
    try:
        declared=parse_canonical(_blob(root,identities["declared_isolation_contract_sha256"])); receipt=parse_canonical(_desc(root,marker["observed_isolation_receipt"])); model_identity=parse_canonical(_blob(root,identities["model_identity_sha256"]))
    except Exception as error: _fail(f"identity/receipt canonical bytes malformed: {error}")
    receipt_keys={"schema_version","receipt_kind","declared_isolation_contract_sha256","dedicated_process","dedicated_node","dedicated_gpu","prefix_cache","max_num_seqs","other_inference_processes","boundary"}
    if declared != {"boundary":"FINITE_DECLARED_CONTROL_CONTRACT_NOT_OBSERVED_PROOF","dedicated_process":True,"dedicated_node":True,"dedicated_gpu":True,"prefix_cache":False,"max_num_seqs":1,"other_inference_processes":0} or type(model_identity) is not dict or type(model_identity.get("model")) is not str or not model_identity["model"] or type(receipt) is not dict or set(receipt)!=receipt_keys or receipt.get("schema_version")!="hswm-dnrd5-q1-observed-isolation-receipt/v1" or receipt.get("receipt_kind")!="OBSERVED_PRE_DISPATCH_FINITE_CONTROL" or receipt.get("declared_isolation_contract_sha256")!=identities["declared_isolation_contract_sha256"] or any(receipt.get(key)!=value for key,value in {"dedicated_process":True,"dedicated_node":True,"dedicated_gpu":True,"prefix_cache":False,"max_num_seqs":1,"other_inference_processes":0,"boundary":"FINITE_OBSERVED_CONTROLS_NOT_NO_INTERFERENCE_PROOF"}.items()): _fail("observed isolation receipt breach")
    cases={case.get("case_id"):case for case in plan["corpus"]}
    expected=[f"DNRD5-Q1-{case_id[-3:]}-R{rep:03d}" for case_id in cases for rep in range(1,5)]
    if not _hex(plan.get("call_order_seed_hex"),64): _fail("order seed drifted")
    try: seed=bytes.fromhex(plan["call_order_seed_hex"])
    except Exception: _fail("order seed drifted")
    if sha256(seed).hexdigest()!=plan.get("call_order_seed_sha256") or plan.get("call_order_algorithm")!="FROZEN_SHA256_FISHER_YATES_V2" or plan.get("call_order")!=_order(expected,seed): _fail("order derivation breach")
    request_hashes=marker.get("request_sha256s")
    if type(request_hashes) is not list or request_hashes!=[case.get("request_sha256") for case in plan["corpus"]]: _fail("24 request manifest breach")
    for digest in request_hashes: _blob(root,digest)
    start_keys={"schema_version","namespace","record_type","attempt_id","case_id","replicate","call_class","request","response_schema","plan_schema","identities","observed_isolation_receipt_sha256","retry","terminal","ordinal","previous_record_sha256","record_sha256"}
    terminal_common={"schema_version","namespace","record_type","attempt_id","case_id","replicate","call_class","start_record_sha256","offline_observation","raw_envelope","outcome","retry","retry_allowed","terminal","ordinal","previous_record_sha256","record_sha256"}
    starts=[]; terminals=[]
    for index in range(96):
        start,terminal=rows[1+2*index],rows[2+2*index]
        if start.get("record_type")!="START" or terminal.get("record_type")!="TERMINAL" or set(start)!=start_keys: _fail("exact alternating START/TERMINAL grammar breach")
        if terminal.get("outcome")=="SUCCEEDED":
            if set(terminal)!=terminal_common|{"model_content_utf8","structured_content"}: _fail("successful TERMINAL key grammar breach")
        elif terminal.get("outcome")=="FAILED":
            if set(terminal)!=terminal_common|{"failure_code"}: _fail("failed TERMINAL key grammar breach")
        else: _fail("unknown terminal outcome")
        starts.append(start); terminals.append(terminal)
    seen={}; failed=False
    for index,(start,terminal) in enumerate(zip(starts,terminals)):
        attempt=plan["call_order"][index]; case_id="QCASE-"+attempt[9:12]; case=cases.get(case_id)
        if case is None or start.get("attempt_id")!=attempt or terminal.get("attempt_id")!=attempt or start.get("case_id")!=case_id or terminal.get("case_id")!=case_id or start.get("replicate")!=int(attempt[-3:]) or terminal.get("replicate")!=int(attempt[-3:]) or start.get("call_class")!=case["call_class"] or terminal.get("call_class")!=case["call_class"] or start.get("plan_schema")!=plan["schema_version"] or start.get("identities")!=identities or start.get("observed_isolation_receipt_sha256")!=sha256(_desc(root,marker["observed_isolation_receipt"])).hexdigest() or start.get("retry")!="NONE" or start.get("terminal")!="DURABLY_VISIBLE_BEFORE_SINGLE_OFFLINE_OBSERVATION_CONSUMPTION" or terminal.get("retry")!="NONE" or terminal.get("retry_allowed") is not False or terminal.get("start_record_sha256")!=start.get("record_sha256") or terminal.get("terminal")!="OFFLINE_OBSERVATION_SLOT_CONSUMED_NO_REPLAY_OR_REPLACEMENT": _fail("start identity/schema/order/retry breach")
        request=_request(root,case,model_identity["model"])
        if _desc(root,start.get("request"))!=request or _desc(root,start.get("response_schema"))!=_blob(root,case["response_schema_sha256"]) or sha256(request).hexdigest()!=case.get("request_sha256"): _fail("independent reconstructed request breach")
        if terminal.get("outcome")!="SUCCEEDED":
            observation=terminal.get("offline_observation")
            if type(terminal.get("failure_code")) is not str or not terminal["failure_code"] or terminal.get("raw_envelope") is not None and not isinstance(terminal.get("raw_envelope"),dict) or observation is not None and (type(observation) is not dict or set(observation)!={"status","response_content_type","provider_request_id"} or type(observation["status"]) is not int): _fail("failed terminal metadata/type breach")
            if terminal.get("raw_envelope") is not None: _desc(root,terminal["raw_envelope"])
            failed=True; continue
        observation=terminal.get("offline_observation")
        if type(observation) is not dict or set(observation)!={"status","response_content_type","provider_request_id"} or observation["status"]!=200 or observation["response_content_type"] is not None and type(observation["response_content_type"]) is not str or observation["provider_request_id"] is not None and type(observation["provider_request_id"]) is not str: _fail("offline observation metadata breach")
        envelope=_strict(_desc(root,terminal.get("raw_envelope"))); content=_desc(root,terminal.get("model_content_utf8")); structured=_desc(root,terminal.get("structured_content"))
        usage=envelope.get("usage") if type(envelope) is dict else None; choices=envelope.get("choices") if type(envelope) is dict else None
        if type(envelope) is not dict or envelope.get("model")!=model_identity["model"] or type(choices) is not list or len(choices)!=1 or type(choices[0]) is not dict or choices[0].get("finish_reason")!="stop" or type(choices[0].get("message")) is not dict or choices[0]["message"].get("content")!=content.decode("utf-8") or type(usage) is not dict or any(type(usage.get(name)) is not int or usage[name]<0 for name in ("prompt_tokens","completion_tokens","total_tokens")) or usage["prompt_tokens"]+usage["completion_tokens"]!=usage["total_tokens"] or structured!=canonical_bytes(_strict(content)): _fail("envelope/status/model/choice/finish/usage/content binding breach")
        _schema(parse_canonical(_blob(root,case["response_schema_sha256"])),_strict(content)); seen.setdefault(case_id,[]).append(sha256(content).hexdigest())
    q1=sha256(_desc(root,marker["plan"])).hexdigest()
    if len(starts)!=96 or failed: return {"terminal":INCONCLUSIVE,"reason":"MISSING_OR_FAILED_CONSUMED_SLOT","q1_sha256":q1}
    if any(len(values)!=4 or len(set(values))!=1 for values in seen.values()): return {"terminal":FALSIFIED,"reason":"ASSISTANT_CONTENT_UTF8_MISMATCH","q1_sha256":q1}
    return {"terminal":REPRODUCED,"reason":"SOURCE_STAGE_OFFLINE_FIXTURE_CONTENT_IDENTITY_ONLY","q1_sha256":q1}
def close_q1_gateway_root(root: Path) -> dict[str,Any]:
    try: return verify_q1_gateway_root(root)
    except Exception as error: return {"terminal":VOID,"reason":f"{type(error).__name__}: {error}"}
