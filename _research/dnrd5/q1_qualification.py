"""Q1 source-stage response-exactness contract; Q0 remains historical evidence."""
from __future__ import annotations

import re
from collections.abc import Sequence
from hashlib import sha256
from typing import Any

from _research.dnrd5.canonical_json import CanonicalJsonError, canonical_bytes, parse_canonical

Q1_SCHEMA = "hswm-dnrd5-q1-response-exactness/v2"
Q1_MARKER_SCHEMA = "hswm-dnrd5-q1-start-marker/v2"
Q1_NAMESPACE = "DNRD5-Q1-SOURCE-STAGE-ONLY/v2"
REPRODUCED = "REPLAY_REPRODUCED_ON_FROZEN_Q1_SOURCE_STAGE_CORPUS"
FALSIFIED = "REPLAY_FALSIFIED_ON_FROZEN_Q1_SOURCE_STAGE_CORPUS"
INCONCLUSIVE = "INCONCLUSIVE_Q1_SOURCE_STAGE_REPLAY_EVIDENCE"
VOID = "VOID_Q1_SOURCE_STAGE_PROTOCOL_LEDGER_HASH_ORDER_OR_RECEIPT_BREACH"
NONCLAIMS = (
    "NOT_A_DNRD5_300_BLOCK_OCCURRENCE_CALL_OR_PILOT_EFFECT_DATA",
    "NOT_SOURCE_A_AUTHORIZATION_OR_SOURCE_A_FREEZE",
    "NOT_PROOF_OF_PROVIDER_INTERNAL_CACHE_SCHEDULING_OR_GLOBAL_DETERMINISM",
    "NOT_PROOF_OF_NO_INTERFERENCE_OR_HSWM_CAUSAL_LEARNING",
    "NOT_EXTERNAL_CI_OR_SOURCE_PROVENANCE_ATTESTATION",
    "NOT_OBSERVED_ISOLATION_OR_AUTHORIZATION_TO_DISPATCH",
    "NOT_A_PROVIDER_DISPATCH_OR_EXTERNAL_PROVIDER_OBSERVATION",
)
CALL_CLASSES = ("PRE_OUTCOME_TRAJECTORY", "REVISION_PROPOSAL", "FRESH_PROBE")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_GIT = re.compile(r"^[0-9a-f]{40}$")
_CASE = re.compile(r"^QCASE-[0-9]{3}$")


class Q1Refusal(ValueError): pass


def _obj(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys: raise Q1Refusal(f"{label} key set drifted")
    return value


def _sha(value: Any, label: str, *, nonzero: bool = True) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None or (nonzero and value == "0" * 64):
        raise Q1Refusal(f"{label} must be a non-placeholder SHA-256")
    return value


def _source(value: Any, label: str) -> dict[str, Any]:
    source = _obj(value, {"commit", "tree", "ci_receipt_sha256", "ci_terminal"}, label)
    if type(source["commit"]) is not str or _GIT.fullmatch(source["commit"]) is None or source["commit"] == "0" * 40: raise Q1Refusal(f"{label}.commit drifted")
    if type(source["tree"]) is not str or _GIT.fullmatch(source["tree"]) is None or source["tree"] == "0" * 40: raise Q1Refusal(f"{label}.tree drifted")
    _sha(source["ci_receipt_sha256"], f"{label}.ci receipt")
    if source["ci_terminal"] != "FIRST_ATTEMPT_SUCCESSFUL_CI_BUILD": raise Q1Refusal(f"{label}.ci terminal drifted")
    return source


def _canon(raw: bytes, label: str) -> dict[str, Any]:
    try: value = parse_canonical(raw)
    except (CanonicalJsonError, TypeError) as error: raise Q1Refusal(f"{label} is not canonical JSON") from error
    if type(value) is not dict: raise Q1Refusal(f"{label} is not object")
    return value


def derive_q1_call_order(attempts: Sequence[str], seed: bytes) -> list[str]:
    """Frozen SHA-256 Fisher--Yates; duplicated by the independent verifier."""
    ordered, counter = list(attempts), 0
    for index in range(len(ordered) - 1, 0, -1):
        stream = b""
        while len(stream) < 8:
            stream += sha256(b"HSWM-DNRD5-Q1-CALL-ORDER-V2\0" + seed + counter.to_bytes(8, "big")).digest()
            counter += 1
        swap = int.from_bytes(stream[:8], "big") % (index + 1)
        ordered[index], ordered[swap] = ordered[swap], ordered[index]
    return ordered


def validate_q1_plan(raw: bytes) -> dict[str, Any]:
    plan = _canon(raw, "Q1 plan")
    keys = {"schema_version","namespace","source","gateway_version","corpus_manifest_sha256","corpus","replicates","call_order","call_order_algorithm","call_order_seed_hex","call_order_seed_sha256","budget","zero_retry","identities","verifier","evidence_root_genesis_sha256","comparator","allowed_terminals","nonclaims"}
    plan = _obj(plan, keys, "Q1 plan")
    if plan["schema_version"] != Q1_SCHEMA or plan["namespace"] != Q1_NAMESPACE: raise Q1Refusal("Q1 source-stage schema/namespace drifted")
    _source(plan["source"], "Q1 source")
    if plan["gateway_version"] != "hswm-dnrd5-q1-provider-gateway/v2": raise Q1Refusal("gateway version drifted")
    _sha(plan["corpus_manifest_sha256"], "corpus manifest")
    corpus = plan["corpus"]
    if type(corpus) is not list or len(corpus) != 24: raise Q1Refusal("Q1 requires exactly 24 cases")
    ids, classes = [], set()
    case_keys = {"case_id","call_class","request_sha256","instruction_sha256","model_input_sha256","response_schema_sha256","rng_sha256","max_output_tokens"}
    for case in corpus:
        case = _obj(case, case_keys, "Q1 case")
        if type(case["case_id"]) is not str or _CASE.fullmatch(case["case_id"]) is None: raise Q1Refusal("case id drifted")
        if case["call_class"] not in CALL_CLASSES or type(case["max_output_tokens"]) is not int or case["max_output_tokens"] not in {64,128,256}: raise Q1Refusal("case class/token drifted")
        for name in case_keys - {"case_id","call_class","max_output_tokens"}: _sha(case[name], name)
        ids.append(case["case_id"]); classes.add(case["call_class"])
    if len(set(ids)) != 24 or classes != set(CALL_CLASSES): raise Q1Refusal("corpus identity/class coverage drifted")
    if plan["replicates"] != 4 or plan["budget"] != 96 or plan["zero_retry"] is not True: raise Q1Refusal("Q1 must be 24 x 4 with zero retries")
    attempts = [f"DNRD5-Q1-{cid[-3:]}-R{rep:03d}" for cid in ids for rep in range(1,5)]
    if plan["call_order_algorithm"] != "FROZEN_SHA256_FISHER_YATES_V2" or type(plan["call_order_seed_hex"]) is not str or len(plan["call_order_seed_hex"]) != 64 or any(c not in "0123456789abcdef" for c in plan["call_order_seed_hex"]): raise Q1Refusal("call-order algorithm/seed drifted")
    seed = bytes.fromhex(plan["call_order_seed_hex"]); _sha(plan["call_order_seed_sha256"], "call-order seed")
    if sha256(seed).hexdigest() != plan["call_order_seed_sha256"] or plan["call_order"] != derive_q1_call_order(attempts, seed): raise Q1Refusal("call order is not independently derived Fisher-Yates order")
    identities = _obj(plan["identities"], {"endpoint_sha256","model_identity_sha256","runtime_identity_sha256","tls_identity_sha256","declared_isolation_contract_sha256"}, "identities")
    for name, digest in identities.items(): _sha(digest, name)
    verifier = _obj(plan["verifier"], {"source","build_output_sha256"}, "verifier")
    _source(verifier["source"], "verifier source"); _sha(verifier["build_output_sha256"], "verifier build")
    _sha(plan["evidence_root_genesis_sha256"], "root genesis")
    if plan["comparator"] != "EXACT_ASSISTANT_CONTENT_UTF8_WITH_CANONICAL_STRUCTURED_DIAGNOSTIC": raise Q1Refusal("comparator drifted")
    if plan["allowed_terminals"] != [REPRODUCED,FALSIFIED,INCONCLUSIVE,VOID] or tuple(plan["nonclaims"]) != NONCLAIMS: raise Q1Refusal("terminal/nonclaim boundary drifted")
    return plan


def make_q1_start_marker(plan_raw: bytes) -> bytes:
    validate_q1_plan(plan_raw)
    return canonical_bytes({"schema_version":Q1_MARKER_SCHEMA,"namespace":Q1_NAMESPACE,"q1_sha256":sha256(plan_raw).hexdigest(),"terminal":"Q1_MARKER_BOUND_AFTER_ALL_24_REQUEST_BLOBS_DURABLE_BEFORE_FIRST_START","nonclaims":list(NONCLAIMS)})


def validate_q1_start_marker(marker_raw: bytes, plan_raw: bytes) -> dict[str, Any]:
    validate_q1_plan(plan_raw); marker = _canon(marker_raw, "Q1 marker")
    marker = _obj(marker, {"schema_version","namespace","q1_sha256","terminal","nonclaims"}, "Q1 marker")
    if marker["schema_version"] != Q1_MARKER_SCHEMA or marker["namespace"] != Q1_NAMESPACE or marker["q1_sha256"] != sha256(plan_raw).hexdigest() or marker["terminal"] != "Q1_MARKER_BOUND_AFTER_ALL_24_REQUEST_BLOBS_DURABLE_BEFORE_FIRST_START" or tuple(marker["nonclaims"]) != NONCLAIMS: raise Q1Refusal("Q1 marker drifted")
    return marker
