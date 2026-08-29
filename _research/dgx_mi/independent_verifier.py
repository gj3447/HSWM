"""Standalone fail-closed reader for the QCASE-024 mechanism diagnostic.

This module deliberately does not import ``_research.dgx_mi.protocol`` or its
freezer/runner.  It is an evidence reducer, not a model runner.
"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import argparse
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from _research.dnrd5.canonical_json import canonical_bytes, canonical_sha256, parse_canonical
from _research.dgx_q1.github_ci_receipt import parse_github_actions_ci_receipt

PLAN = "hswm-dgx-qcase024-mi-plan/v1"
MARKER = "hswm-dgx-qcase024-mi-start-marker/v1"
FREEZE = "hswm-dgx-qcase024-mi-preregistration-freeze/v1"
LEDGER = "hswm-dgx-qcase024-mi-ledger/v1"
NAMESPACE = "DNRD5-QCASE024-MECHANISM-ISOLATION-ONLY/v1"
RUNNER = "hswm-dgx-qcase024-mi-runner/v1"
ARMS = ("ASYNC_ENABLED", "ASYNC_DISABLED")
BLOCKS = (("ASYNC_ENABLED", "B01"), ("ASYNC_DISABLED", "B01"),
          ("ASYNC_DISABLED", "B02"), ("ASYNC_ENABLED", "B02"))
COMPLETE = "LIVE_COMPLETE_DGX_QCASE024_MECHANISM_DIAGNOSTIC"
INCOMPLETE = "INCONCLUSIVE_DGX_QCASE024_MI_INCOMPLETE_LIVE_SLOTS"
UNAVAILABLE = "INCONCLUSIVE_DGX_QCASE024_MI_REQUIRED_LOGPROB_OR_ALIGNMENT_UNAVAILABLE"
VOID = "VOID_DGX_QCASE024_MI_PROTOCOL_LEDGER_HASH_ORDER_OR_BOUNDARY_BREACH"
TERMINALS = (COMPLETE, INCOMPLETE, UNAVAILABLE, VOID)
ZERO = "0" * 64
SHA = re.compile(r"^[0-9a-f]{64}$")
ATTEMPT = re.compile(r"^MI-024-(ASYNC_ENABLED|ASYNC_DISABLED)-B0[12]-R00[1-4]$")
SYSTEM = ("Act only as the bounded DNRD-5 token-native model function. Read the "
          "declared public synthetic input, follow its instruction, and return "
          "exactly one object satisfying the supplied strict JSON schema.")
REGISTRY = {"schema_version": "hswm-dgx-qcase024-mi-plan-consumption-registry/v1", "path": "/mnt/hswm/evidence/hswm-dnrd5-qcase024-mi-1-consumption-v1", "scope": "PINNED_DGX_NODE_LOCAL_DURABLE_PLAN_HASH_REGISTRY", "boundary": "NODE_LOCAL_PATH_BINDING_NOT_DISTRIBUTED_GLOBAL_CONSENSUS", "terminal": "ONE_DURABLE_BURN_PER_PLAN_HASH_AT_THE_DECLARED_PATH"}
NONCLAIMS = ("POST_RESULT_SELECTED_QCASE024_DIAGNOSTIC_NOT_CONFIRMATORY_OR_GENERALIZABLE", "NOT_A_Q1_RETRY_OR_BATCH_INVARIANCE_QUALIFICATION", "NOT_A_DNRD5_300_BLOCK_OCCURRENCE_OR_SOURCE_A_AUTHORIZATION", "NOT_CAUSAL_ATTRIBUTION_TO_SCHEDULING_GDN_FP8_OR_PROVIDER_INTERNALS", "NOT_PROOF_OF_NO_INTERFERENCE_OR_HSWM_CAUSAL_LEARNING", "NOT_PROOF_OF_CONSCIOUSNESS_SELFHOOD_OR_SCALE_INVARIANT_CAUSAL_CLOSURE")
EXPECTED_MATERIAL = {"instruction_sha256": "8e13131449ba0f31cb7305490dec680f6808006db2e5b50cc8614b172c85b907", "model_input_sha256": "5902dec004e606aaf46b8a5d80c45ab855f275d714d111b2430d86d0e1c1a273", "response_schema_sha256": "a623afd2cace659731c46b336fd4cb75c071e60f425fa583e8995abe7ff83940", "rng_sha256": "69b1f0ef2be0d6519baa19562928cc6ed3a458e382e48508a4cb47292063bd78"}
EXPECTED_SELECTION = {"q1_source_commit": "4e3238b472c88c3e51e7849472f46d8f8e368d9d", "q1_result_commit": "a6f13445375f8195a35e025810cc1628c41b5641", "q1_v3_plan_sha256": "b054396e68620c2bcc97a9da9c429edda3182c93d41a573e6eef6fe30c997c22", "q1_live_receipt_sha256": "a10d107463823218ada992945d7b72167669e0948b3019dd680607a530c30978", "q1_evidence_receipt_sha256": "cc53ba6d42ebe52d648fbd777850b9b96c9ae50e7fda99aa5cf7456a6344b51f", "q1_exact_ledger_sha256": "f3cdfff46e1ee4ff0973531296863970f7bc9fa21eff1ea60ddc4da7a6e13f00", "q1_result_projection_sha256": "17649d84046297a0ad5ecaadb5efdcc35d02f8ef58b9784ff8de65048b611d22", "selected_request_sha256": "c24c74241bbf670b3e2c640f3acd18cb449d3172659bde5fcb08262950a53a19", "q1_terminal": "LIVE_FALSIFIED_EXACT_ASSISTANT_CONTENT_UTF8_ON_FROZEN_Q1", "selected_case": "QCASE-024", "selection_status": "POST_RESULT_SELECTED_NOT_CONFIRMATORY", "selection_basis": "ONE_SEMANTIC_ASSISTANT_CONTENT_VARIANT_IN_Q1_V3"}
PINNED_MODEL = "qwen3.6-35b-a3b"
PINNED_REQUEST_SHA256 = "fec3b64ce00d750e67a34374fe9d1e5e7fa6232294b8990e0aa4f352bc52fac9"
SERVER_PREFIX = ("--model", "/model-repository/snapshots/95a723d08a9490559dae23d0cff1d9466213d989", "--served-model-name", PINNED_MODEL, "--host", "0.0.0.0", "--port", "8000", "--max-num-seqs", "1", "--no-enable-prefix-caching", "--max-model-len", "32768", "--gpu-memory-utilization", "0.500", "--generation-config", "vllm", "--seed", "0", "--enforce-eager", "--language-model-only", "--max-logprobs", "20", "--logprobs-mode", "processed_logprobs")
PINNED_IDENTITIES = {
    "ASYNC_ENABLED": {"endpoint_sha256": "d8af93d15021cde9f992a8037a9120403c241a18106a6e732d15e88ca8e42995", "model_identity_sha256": "cbb9ffc9ccc837e65396254cfc08b8831a32c87a28c9275c445593aa6fb235d1", "tls_identity_sha256": "7e1ab55efb6f198c4afb7d5d85360fad5eb398cedfedf86e0b18bc27dedc941d", "declared_isolation_contract_sha256": "ac594ec24eb2a096b0053096c8650aeca33aa290d7146bd0793abddcd64e9ba1", "model_snapshot_manifest_sha256": "2ece6b46248e818cbf93aa30299300f7dd4c60d9351960ec790cc8b420376e47", "runtime_identity_sha256": "742586b6e4790b0d6b8debd24be69f0f08a4977b39bdf91a4e0352da0a574ff1"},
    "ASYNC_DISABLED": {"endpoint_sha256": "d8af93d15021cde9f992a8037a9120403c241a18106a6e732d15e88ca8e42995", "model_identity_sha256": "cbb9ffc9ccc837e65396254cfc08b8831a32c87a28c9275c445593aa6fb235d1", "tls_identity_sha256": "7e1ab55efb6f198c4afb7d5d85360fad5eb398cedfedf86e0b18bc27dedc941d", "declared_isolation_contract_sha256": "ac594ec24eb2a096b0053096c8650aeca33aa290d7146bd0793abddcd64e9ba1", "model_snapshot_manifest_sha256": "2ece6b46248e818cbf93aa30299300f7dd4c60d9351960ec790cc8b420376e47", "runtime_identity_sha256": "7e0c29da01b637cdc1322124ae4cfc51542a8e8bed3916e94836628ebca48606"},
}


class _Number(str):
    """A JSON numeric lexeme; preserving it avoids binary-float diagnostics."""


def _bad(message: str = "breach") -> None:
    raise ValueError(message)


def _object(value: Any, keys: set[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        _bad("key set")
    return value


def _digest(value: Any) -> str:
    if type(value) is not str or SHA.fullmatch(value) is None or value == ZERO:
        _bad("digest")
    return value


def _canonical(raw: bytes) -> Any:
    return parse_canonical(raw)


def _ordinary(raw: bytes) -> Any:
    """Strict ordinary JSON, retaining floating-point lexemes as ``_Number``."""
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                _bad("duplicate JSON key")
            result[key] = value
        return result
    try:
        return json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=pairs,
                          parse_float=_Number,
                          parse_constant=lambda _: _bad("nonfinite JSON"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError("ordinary JSON") from error


def _descriptor(value: Any) -> dict[str, Any]:
    item = _object(value, {"sha256", "byte_length"})
    _digest(item["sha256"])
    if type(item["byte_length"]) is not int or not 0 <= item["byte_length"] <= 16 * 1024 * 1024:
        _bad("descriptor length")
    return item


def _blob(root: Path, descriptor: Any) -> bytes:
    item = _descriptor(descriptor)
    path = root / "content" / item["sha256"]
    if path.is_symlink() or not path.is_file():
        _bad("missing blob")
    raw = path.read_bytes()
    if len(raw) != item["byte_length"] or sha256(raw).hexdigest() != item["sha256"]:
        _bad("blob hash")
    return raw


def _decimal(value: Any) -> Decimal:
    if type(value) not in {int, _Number}:
        _bad("numeric logprob")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError("decimal") from error
    if not result.is_finite():
        _bad("nonfinite logprob")
    return result


def _decimal_text(value: Decimal) -> str:
    value = value.normalize()
    # fixed form avoids multiple canonical textual spellings of an equal gap.
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def _token(value: Any) -> tuple[bytes, Decimal, list[tuple[bytes, Decimal, int]]]:
    item = _object(value, {"token", "bytes", "logprob", "top_logprobs"})
    if type(item["token"]) is not str or not item["token"]:
        _bad("token text")
    data = item["bytes"]
    if type(data) is not list or not data or any(type(q) is not int or not 0 <= q <= 255 for q in data):
        _bad("token bytes")
    top = item["top_logprobs"]
    if type(top) is not list or len(top) != 20:
        _bad("top20 unavailable")
    alternatives: list[tuple[bytes, Decimal, int]] = []
    for index, candidate in enumerate(top):
        candidate = _object(candidate, {"token", "bytes", "logprob"})
        if type(candidate["token"]) is not str or not candidate["token"]:
            _bad("top token")
        candidate_bytes = candidate["bytes"]
        if (type(candidate_bytes) is not list or not candidate_bytes or
                any(type(q) is not int or not 0 <= q <= 255 for q in candidate_bytes)):
            _bad("top bytes")
        alternatives.append((bytes(candidate_bytes), _decimal(candidate["logprob"]), index))
    return bytes(data), _decimal(item["logprob"]), alternatives


def _tokens(envelope: dict[str, Any], content: bytes) -> list[tuple[bytes, Decimal, list[tuple[bytes, Decimal, int]]]]:
    choices = envelope.get("choices")
    if type(choices) is not list or len(choices) != 1 or type(choices[0]) is not dict:
        _bad("choice")
    choice = choices[0]
    if choice.get("finish_reason") != "stop" or type(choice.get("message")) is not dict:
        _bad("choice terminal")
    message = choice["message"]
    if type(message.get("content")) is not str or message["content"].encode("utf-8") != content:
        _bad("content join")
    logprobs = choice.get("logprobs")
    if type(logprobs) is not dict or set(logprobs) != {"content"} or type(logprobs["content"]) is not list:
        _bad("logprobs unavailable")
    result = [_token(item) for item in logprobs["content"]]
    if not result or b"".join(item[0] for item in result) != content:
        _bad("token byte alignment")
    return result


def _schema(schema: Any, value: Any = None, *, instance: bool = False) -> None:
    """Validate the closed response-schema subset without calling the runner."""
    if type(schema) is not dict or schema.get("type") not in {"object", "array", "string", "integer", "boolean", "null"}: _bad("schema")
    kind = schema["type"]
    if kind == "object":
        if set(schema) != {"type", "properties", "required", "additionalProperties"} or type(schema["properties"]) is not dict or not schema["properties"] or type(schema["required"]) is not list or set(schema["required"]) != set(schema["properties"]) or len(schema["required"]) != len(set(schema["required"])) or schema["additionalProperties"] is not False: _bad("object schema")
        for child in schema["properties"].values(): _schema(child)
        if instance:
            if type(value) is not dict or set(value) != set(schema["properties"]): _bad("object instance")
            for name, child in schema["properties"].items(): _schema(child, value[name], instance=True)
    elif kind == "string":
        if not {"type"} <= set(schema) <= {"type", "minLength", "maxLength", "pattern"} or type(schema.get("minLength", 0)) is not int or type(schema.get("maxLength", 65536)) is not int: _bad("string schema")
        if instance and (type(value) is not str or not schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", 65536) or ("pattern" in schema and re.fullmatch(schema["pattern"], value) is None)): _bad("string instance")
    elif kind == "integer":
        if not {"type"} <= set(schema) <= {"type", "minimum", "maximum"} or type(schema.get("minimum", -(2**53-1))) is not int or type(schema.get("maximum", 2**53-1)) is not int: _bad("integer schema")
        if instance and (type(value) is not int or not schema.get("minimum", -(2**53-1)) <= value <= schema.get("maximum", 2**53-1)): _bad("integer instance")
    elif kind == "array":
        if not {"type", "items"} <= set(schema) <= {"type", "items", "minItems", "maxItems"} or type(schema["items"]) is not dict: _bad("array schema")
        _schema(schema["items"])
        if instance:
            if type(value) is not list or not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", 65536): _bad("array instance")
            for child in value: _schema(schema["items"], child, instance=True)
    elif set(schema) != {"type"} or (instance and ((kind == "boolean" and type(value) is not bool) or (kind == "null" and value is not None))): _bad("scalar schema")


def _span(tokens: list[tuple[bytes, Decimal, list[tuple[bytes, Decimal, int]]]], offset: int) -> tuple[int, int, int]:
    cursor = 0
    for index, (data, _, _) in enumerate(tokens):
        end = cursor + len(data)
        if offset < end:
            return index, cursor, end
        cursor = end
    _bad("divergence span")


def _gap(selected: tuple[bytes, Decimal, list[tuple[bytes, Decimal, int]]], peer_bytes: bytes) -> dict[str, Any]:
    data, selected_score, alternatives = selected
    peer = [(score, index) for candidate, score, index in alternatives if candidate == peer_bytes]
    nonselected = [(score, candidate, index) for candidate, score, index in alternatives if candidate != data]
    if not nonselected:
        _bad("no alternative")
    best_score, _, best_index = sorted(nonselected, key=lambda q: (-q[0], q[1], q[2]))[0]
    result: dict[str, Any] = {
        "selected_logprob": _decimal_text(selected_score),
        "selected_minus_best_nonselected": _decimal_text(selected_score - best_score),
        "best_nonselected_rank": best_index,
    }
    if peer:
        peer_score, peer_index = sorted(peer, key=lambda q: (-q[0], q[1]))[0]
        result |= {"peer_status": "PEER_TOKEN_IN_TOP20", "peer_rank": peer_index,
                   "selected_minus_peer": _decimal_text(selected_score - peer_score)}
    else:
        result |= {"peer_status": "PEER_TOKEN_NOT_IN_TOP20", "peer_rank": None,
                   "selected_minus_peer": None}
    return result


def _comparison(left_id: str, left: tuple[bytes, list[Any]], right_id: str, right: tuple[bytes, list[Any]]) -> dict[str, Any] | None:
    left_bytes, left_tokens = left; right_bytes, right_tokens = right
    offset = 0
    while offset < min(len(left_bytes), len(right_bytes)) and left_bytes[offset] == right_bytes[offset]:
        offset += 1
    if offset == len(left_bytes) == len(right_bytes):
        return None
    if offset == len(left_bytes) or offset == len(right_bytes):
        # This is still a defined byte divergence; the exhausted side has no token.
        return {"left_attempt_id": left_id, "right_attempt_id": right_id,
                "first_differing_byte_offset": offset, "token_status": "ONE_CONTENT_IS_PREFIX",
                "left": None, "right": None}
    li, ls, le = _span(left_tokens, offset); ri, rs, re = _span(right_tokens, offset)
    left_token, right_token = left_tokens[li], right_tokens[ri]
    return {"left_attempt_id": left_id, "right_attempt_id": right_id,
            "first_differing_byte_offset": offset, "token_status": "ALIGNED_BY_EMITTED_BYTES",
            "left": {"token_index": li, "byte_start": ls, "byte_end": le,
                     "token_sha256": sha256(left_token[0]).hexdigest(),
                     "gap": _gap(left_token, right_token[0])},
            "right": {"token_index": ri, "byte_start": rs, "byte_end": re,
                      "token_sha256": sha256(right_token[0]).hexdigest(),
                      "gap": _gap(right_token, left_token[0])}}


def _plan(raw: bytes) -> dict[str, Any]:
    plan = _canonical(raw)
    required = {"schema_version", "namespace", "source", "runner_version", "material", "request_sha256", "attempt_ids",
                "post_result_selection", "arms", "block_order", "attempts_per_block", "budget", "zero_retry",
                "consumption_registry", "verifier", "evidence_root_genesis_sha256", "allowed_terminals", "nonclaims"}
    plan = _object(plan, required)
    if (plan["schema_version"], plan["namespace"], plan["runner_version"], plan["attempts_per_block"],
        plan["budget"], plan["zero_retry"]) != (PLAN, NAMESPACE, RUNNER, 4, 16, True):
        _bad("plan static")
    _digest(plan["request_sha256"]); _digest(plan["evidence_root_genesis_sha256"])
    if plan["request_sha256"] != PINNED_REQUEST_SHA256: _bad("pinned request")
    if plan["allowed_terminals"] != list(TERMINALS): _bad("plan terminals")
    if plan["consumption_registry"] != REGISTRY or plan["nonclaims"] != list(NONCLAIMS): _bad("plan registry/nonclaims")
    source = _object(plan["source"], {"commit", "tree", "ci_receipt_sha256", "ci_terminal"})
    verifier = _object(plan["verifier"], {"source", "build_output_sha256"})
    for item in (source, _object(verifier["source"], {"commit", "tree", "ci_receipt_sha256", "ci_terminal"})):
        if (type(item["commit"]) is not str or not re.fullmatch(r"[0-9a-f]{40}", item["commit"]) or item["commit"] == "0" * 40 or type(item["tree"]) is not str or not re.fullmatch(r"[0-9a-f]{40}", item["tree"]) or item["tree"] == "0" * 40 or item["ci_terminal"] != "FIRST_ATTEMPT_SUCCESSFUL_CI_BUILD"):
            _bad("source")
        _digest(item["ci_receipt_sha256"])
    _digest(verifier["build_output_sha256"])
    material = _object(plan["material"], {"case_id", "instruction_sha256", "model_input_sha256", "response_schema_sha256", "rng_sha256", "max_output_tokens"})
    if material.get("case_id") != "QCASE-024" or material.get("max_output_tokens") != 256 or {key: material.get(key) for key in EXPECTED_MATERIAL} != EXPECTED_MATERIAL: _bad("material")
    if plan["post_result_selection"] != EXPECTED_SELECTION: _bad("selection")
    if plan["block_order"] != [{"arm": arm, "block_id": block} for arm, block in BLOCKS] or plan["attempt_ids"] != _expected_attempts(): _bad("block order")
    if type(plan["arms"]) is not dict or set(plan["arms"]) != set(ARMS): _bad("arms")
    for arm in ARMS:
        identity = plan["arms"][arm]
        if type(identity) is not dict or set(identity) != {"endpoint_sha256", "model_identity_sha256", "runtime_identity_sha256", "tls_identity_sha256", "declared_isolation_contract_sha256", "model_snapshot_manifest_sha256"}: _bad("identity map")
        for item in identity.values(): _digest(item)
        if identity != PINNED_IDENTITIES[arm]: _bad("pinned arm identities")
    return plan


def _expected_attempts() -> list[str]:
    return [f"MI-024-{arm}-{block}-R{rep:03d}" for arm, block in BLOCKS for rep in range(1, 5)]


def _pattern(contents: dict[str, bytes]) -> tuple[str, dict[str, int], dict[str, int]]:
    block_counts: dict[str, int] = {}
    arm_counts: dict[str, int] = {}
    for arm, block in BLOCKS:
        values = [contents[f"MI-024-{arm}-{block}-R{rep:03d}"] for rep in range(1, 5)]
        block_counts[f"{arm}/{block}"] = len(set(values))
    for arm in ARMS:
        values = [contents[f"MI-024-{arm}-{block}-R{rep:03d}"] for a, block in BLOCKS if a == arm for rep in range(1, 5)]
        arm_counts[arm] = len(set(values))
    enabled, disabled = arm_counts["ASYNC_ENABLED"], arm_counts["ASYNC_DISABLED"]
    if enabled == disabled == 1: label = "ALL_ARM_BLOCKS_EXACT"
    elif enabled > 1 and disabled == 1: label = "ASYNC_ENABLED_VARIATION_ASYNC_DISABLED_EXACT"
    elif enabled == 1 and disabled > 1: label = "ASYNC_DISABLED_VARIATION_ASYNC_ENABLED_EXACT"
    else: label = "BOTH_ARMS_VARIATION"
    return label, block_counts, arm_counts


def _modal_counts(contents: dict[str, bytes]) -> tuple[dict[str, int], dict[str, int]]:
    block: dict[str, int] = {}; arm: dict[str, int] = {}
    for a, b in BLOCKS:
        values = [contents[f"MI-024-{a}-{b}-R{r:03d}"] for r in range(1, 5)]
        block[f"{a}/{b}"] = max(Counter(values).values())
    for a in ARMS:
        values = [contents[f"MI-024-{a}-{b}-R{r:03d}"] for aa, b in BLOCKS if aa == a for r in range(1, 5)]
        arm[a] = max(Counter(values).values())
    return block, arm


def _referenced_descriptors(value: Any, found: set[str]) -> None:
    if type(value) is dict:
        if set(value) == {"sha256", "byte_length"} and type(value.get("sha256")) is str:
            found.add(value["sha256"])
        for item in value.values(): _referenced_descriptors(item, found)
    elif type(value) is list:
        for item in value: _referenced_descriptors(item, found)


def _boundary(root: Path, descriptor: Any, *, arm: str, block: str, phase: str, completed: int, server: dict[str, Any]) -> None:
    value = _canonical(_blob(root, descriptor))
    keys = {"schema_version", "arm", "block_id", "phase", "completed", "async_scheduling", "server_argv", "server_argv_sha256", "server_identity", "request_success_total", "raw_metrics_sha256", "terminal"}
    value = _object(value, keys)
    if (value["schema_version"], value["arm"], value["block_id"], value["phase"], value["completed"], value["async_scheduling"], value["server_identity"], value["request_success_total"], value["terminal"]) != ("hswm-dgx-qcase024-mi-boundary/v1", arm, block, phase, completed, arm == "ASYNC_ENABLED", server["observed"], completed, "FINITE_BLOCK_BOUNDARY_NOT_NO_INTERFERENCE_PROOF"):
        _bad("boundary continuity")
    if type(value["server_argv"]) is not list or sha256("\0".join(value["server_argv"]).encode()).hexdigest() != value["server_argv_sha256"]:
        _bad("boundary argv")
    if tuple(value["server_argv"][:-1]) != SERVER_PREFIX or value["server_argv"][-1] != ("--async-scheduling" if arm == "ASYNC_ENABLED" else "--no-async-scheduling"):
        _bad("boundary async")
    _digest(value["raw_metrics_sha256"])


def verify(root: Path, *, external_registry_root: Path | None = None) -> dict[str, Any]:
    """Recompute the sealed diagnostic result, returning ``VOID`` on breach."""
    try:
        if not isinstance(root, Path) or root.is_symlink() or not root.is_dir(): _bad("root")
        names = {path.name for path in root.iterdir()}
        if names != {"content", "mi_ledger.jsonl", "dispatch.lock"}: _bad("root closure")
        content_dir = root / "content"; ledger_path = root / "mi_ledger.jsonl"
        if content_dir.is_symlink() or not content_dir.is_dir() or ledger_path.is_symlink() or not ledger_path.is_file(): _bad("root type")
        raw_ledger = ledger_path.read_bytes()
        if not raw_ledger.endswith(b"\n"): _bad("ledger framing")
        rows = [_canonical(line) for line in raw_ledger[:-1].split(b"\n")]
        previous = ZERO
        for ordinal, row in enumerate(rows, 1):
            if type(row) is not dict or row.get("ordinal") != ordinal or row.get("previous_record_sha256") != previous:
                _bad("ledger order")
            actual = canonical_sha256({key: value for key, value in row.items() if key != "record_sha256"})
            if row.get("record_sha256") != actual: _bad("ledger chain")
            previous = actual
        if not 3 <= len(rows) <= 39: _bad("ledger cardinality")
        burn, marker = rows[0], rows[1]
        if burn.get("schema_version") != LEDGER or marker.get("schema_version") != LEDGER or burn.get("record_type") != "PLAN_CONSUMPTION" or marker.get("record_type") != "MI_MARKER": _bad("prefix")
        _object(burn, {"schema_version","record_type","consumption","plan_sha256","closure_manifest_sha256","registry_path","evidence_mode","retry","terminal","ordinal","previous_record_sha256","record_sha256"})
        _object(marker, {"schema_version","record_type","plan","marker","freeze","root","material","request","identities","provenance","publication","all_request_blob_durable","retry","terminal","ordinal","previous_record_sha256","record_sha256"})
        plan_raw = _blob(root, marker["plan"]); plan = _plan(plan_raw); plan_sha = sha256(plan_raw).hexdigest()
        if burn.get("plan_sha256") != plan_sha: _bad("plan join")
        closure_raw = _blob(root, marker["freeze"]); closure = _canonical(closure_raw)
        if (burn["closure_manifest_sha256"], burn["evidence_mode"], burn["retry"], burn["terminal"]) != (sha256(closure_raw).hexdigest(), "LIVE_LEASE", "NONE", "DURABLE_PLAN_BURN_BEFORE_ANY_MI_TARGET_LAUNCH"):
            _bad("burn semantics")
        if (type(closure) is not dict or closure.get("schema_version") != FREEZE or closure.get("namespace") != NAMESPACE or
                type(closure.get("artifacts")) is not list): _bad("closure")
        declared = {item.get("path"): item for item in closure["artifacts"] if type(item) is dict}
        if len(declared) != len(closure["artifacts"]) or declared.get("plan.json", {}).get("sha256") != plan_sha: _bad("closure plan")
        # Every frozen artifact replayed into the root must remain the exact
        # descriptor declared by the checked-in closure, not merely the plan.
        def closure_join(path: str, descriptor: Any) -> None:
            item = _descriptor(descriptor); frozen = declared.get(path)
            if frozen != {"path": path, **item}: _bad("closure artifact join")
        closure_join("start_marker.json", marker["marker"])
        closure_join("root_genesis.json", marker["root"])
        closure_join("material_provenance.json", marker["material"])
        closure_join("request.json", marker["request"])
        for arm in ARMS:
            for name, descriptor in marker.get("identities", {}).get(arm, {}).items():
                closure_join(f"identities/{arm}/{name}.json", descriptor)
        start_marker = _blob(root, marker["marker"])
        expected_marker = {"schema_version": MARKER, "namespace": NAMESPACE, "plan_sha256": plan_sha,
                           "request_sha256": plan["request_sha256"], "scheduled_attempts": _expected_attempts(),
                           "terminal": "ALL_16_SERIALIZED_POSTS_AND_LOGPROB_OBSERVABILITY_BOUND_BEFORE_LIVE_START",
                           "nonclaims": plan["nonclaims"]}
        if _canonical(start_marker) != expected_marker: _bad("marker")
        if marker.get("all_request_blob_durable") is not True: _bad("request durability")
        if (marker["retry"], marker["terminal"]) != ("NONE", "ALL_16_MI_REQUEST_BLOBS_FSYNCED_BEFORE_ANY_TARGET_LAUNCH"): _bad("marker semantics")
        if sha256(_blob(root, marker["root"])).hexdigest() != plan["evidence_root_genesis_sha256"]: _bad("genesis")
        if type(marker.get("identities")) is not dict or set(marker["identities"]) != set(ARMS): _bad("identity roots")
        for arm in ARMS:
            if set(marker["identities"][arm]) != set(plan["arms"][arm]): _bad("identity keys")
            for name, expected in plan["arms"][arm].items():
                if sha256(_blob(root, marker["identities"][arm][name])).hexdigest() != expected: _bad("identity digest")
            endpoint = _canonical(_blob(root, marker["identities"][arm]["endpoint_sha256"]))
            model = _canonical(_blob(root, marker["identities"][arm]["model_identity_sha256"]))
            runtime = _canonical(_blob(root, marker["identities"][arm]["runtime_identity_sha256"]))
            tls = _canonical(_blob(root, marker["identities"][arm]["tls_identity_sha256"]))
            if (_object(endpoint, {"schema_version","endpoint","method","transport"}) != {"schema_version":"hswm-dgx-q1-endpoint-identity/v1","endpoint":"http://127.0.0.1:18080/v1/chat/completions","method":"POST","transport":"LOOPBACK_HTTP_NO_TLS"} or set(model) != {"schema_version","model","repository","revision","snapshot_manifest_sha256"} or (model.get("model"),model.get("repository"),model.get("revision")) != (PINNED_MODEL,"Qwen/Qwen3.6-35B-A3B-FP8","95a723d08a9490559dae23d0cff1d9466213d989") or tls != {"schema_version":"hswm-dgx-q1-tls-identity/v1","endpoint_scheme":"http","tls":"NOT_APPLICABLE_LOOPBACK_ONLY"}): _bad("identity semantic")
            if runtime.get("schema_version") != "hswm-dgx-qcase024-mi-runtime-identity/v1" or runtime.get("async_scheduling") != (arm == "ASYNC_ENABLED") or tuple(runtime.get("server_arguments", [])) != SERVER_PREFIX + (("--async-scheduling",) if arm == "ASYNC_ENABLED" else ("--no-async-scheduling",)) or runtime.get("served_model") != PINNED_MODEL or runtime.get("endpoint") != endpoint["endpoint"]: _bad("runtime identity")
        provenance = marker.get("provenance")
        if type(provenance) is not dict or set(provenance) != {"source_ci_receipt_sha256", "verifier_ci_receipt_sha256", "verifier_build_output_sha256"}: _bad("provenance keys")
        source_ci = _blob(root, provenance["source_ci_receipt_sha256"])
        verifier_ci = _blob(root, provenance["verifier_ci_receipt_sha256"])
        if sha256(source_ci).hexdigest() != plan["source"].get("ci_receipt_sha256"): _bad("source CI")
        if sha256(verifier_ci).hexdigest() != plan["verifier"].get("source", {}).get("ci_receipt_sha256"): _bad("verifier CI")
        parse_github_actions_ci_receipt(source_ci, repository="gj3447/HSWM", commit=plan["source"]["commit"], tree=plan["source"]["tree"])
        parse_github_actions_ci_receipt(verifier_ci, repository="gj3447/HSWM", commit=plan["verifier"]["source"]["commit"], tree=plan["verifier"]["source"]["tree"])
        build = _canonical(_blob(root, provenance["verifier_build_output_sha256"]))
        build = _object(build, {"schema_version", "source_path", "source_sha256", "source_utf8", "imports", "terminal"})
        if (build["schema_version"], build["source_path"], build["terminal"]) != ("hswm-dgx-qcase024-mi-independent-verifier-build/v1", "_research/dgx_mi/independent_verifier.py", "MI_INDEPENDENT_VERIFIER_SOURCE_AND_IMPORTS_BOUND") or sha256(build["source_utf8"].encode()).hexdigest() != build["source_sha256"] or sha256(Path(__file__).read_bytes()).hexdigest() != build["source_sha256"] or any(item in {"_research.dgx_mi.protocol", "_research.dgx_mi.preregistration", "_research.dgx_mi.runner"} for item in build["imports"]): _bad("verifier build")
        if sha256(_blob(root, provenance["verifier_build_output_sha256"])).hexdigest() != plan["verifier"].get("build_output_sha256"): _bad("verifier build digest")
        publication = _object(marker.get("publication"), {"commit", "tree", "ci_receipt"})
        if (type(publication["commit"]) is not str or not re.fullmatch(r"[0-9a-f]{40}", publication["commit"]) or publication["commit"] == "0" * 40 or type(publication["tree"]) is not str or not re.fullmatch(r"[0-9a-f]{40}", publication["tree"]) or publication["tree"] == "0" * 40): _bad("publication identity")
        receipt = _blob(root, publication["ci_receipt"])
        if sha256(receipt).hexdigest() != publication["ci_receipt"]["sha256"]: _bad("publication receipt")
        parse_github_actions_ci_receipt(receipt, repository="gj3447/HSWM", commit=publication["commit"], tree=publication["tree"])
        consumption = _blob(root, burn["consumption"])
        burn_record = _canonical(consumption)
        if _object(burn_record, {"schema_version", "plan_sha256", "closure_manifest_sha256", "evidence_root", "registry_path", "terminal"})["schema_version"] != "hswm-dgx-qcase024-mi-plan-consumption/v1" or burn_record["plan_sha256"] != plan_sha or burn_record["closure_manifest_sha256"] != sha256(closure_raw).hexdigest() or burn_record["registry_path"] != burn["registry_path"] or burn_record["terminal"] != "PLAN_BURNED_BEFORE_ANY_MI_TARGET_LAUNCH_NO_REUSE" or type(burn_record["evidence_root"]) is not str or not burn_record["evidence_root"]: _bad("consumption semantics")
        if external_registry_root is None:
            return {"terminal": INCOMPLETE}
        path = external_registry_root / (plan_sha + ".consumed")
        if path.is_symlink() or not path.is_file() or path.read_bytes() != consumption: return {"terminal": INCOMPLETE}

        # A failed slot is intentionally terminal: the runner seals rather than
        # replacing it.  It is still a hash-bound partial observation, but can
        # never be reduced as the 16-slot mechanism result.
        if len(rows) != 39:
            seal = rows[-1]
            _object(seal, {"schema_version","record_type","status","started_slots","successful_slots","failed_slots","failure_code","blocks","retry","retry_allowed","terminal","ordinal","previous_record_sha256","record_sha256"})
            if seal["schema_version"] != LEDGER or seal["record_type"] != "RUN_SEAL" or seal["status"] not in {INCOMPLETE, UNAVAILABLE} or seal["retry"] != "NONE" or seal["retry_allowed"] is not False or seal["terminal"] != "MI_ROOT_SEALED_NO_RESUME_OR_REPLACEMENT": _bad("early seal")
            if (type(seal["started_slots"]) is not int or type(seal["successful_slots"]) is not int or type(seal["failed_slots"]) is not int or not 1 <= seal["started_slots"] < 16 or not 0 <= seal["successful_slots"] <= seal["started_slots"] or seal["failed_slots"] != seal["started_slots"] - seal["successful_slots"] or type(seal["blocks"]) is not list or not 1 <= len(seal["blocks"]) <= 4): _bad("early counts")
            return {"terminal": seal["status"], "plan_sha256": plan_sha, "ledger_sha256": sha256(raw_ledger).hexdigest(), "ledger_final_record_sha256": previous}

        expected = _expected_attempts(); index = 2; contents: dict[str, bytes] = {}; token_rows: dict[str, list[Any]] = {}
        server_ids: set[tuple[str, str]] = set(); block_servers: list[dict[str, Any]] = []
        for arm, block in BLOCKS:
            block_start = rows[index]; index += 1
            if block_start.get("schema_version") != LEDGER or block_start.get("record_type") != "BLOCK_START" or block_start.get("arm") != arm or block_start.get("block_id") != block or block_start.get("block_index") != len(block_servers) + 1:
                _bad("block start")
            server = _object(block_start.get("server_identity"), {"async_scheduling", "container_name", "observed"})
            observed = _object(server["observed"], {"container_id_sha256", "container_start_sha256", "cgroup_sha256", "network_namespace_sha256", "server_argv_sha256"})
            if server["async_scheduling"] != (arm == "ASYNC_ENABLED") or type(server["container_name"]) is not str or not server["container_name"] or any(_digest(v) is None for v in observed.values()):
                _bad("server identity")
            incarnation = (observed["container_id_sha256"], observed["container_start_sha256"])
            if incarnation in server_ids: _bad("server reuse")
            server_ids.add(incarnation); block_servers.append(server)
            _boundary(root, block_start["pre_boundary_attestation"], arm=arm, block=block, phase="PRE", completed=0, server=server)
            for rep in range(1, 5):
                attempt = f"MI-024-{arm}-{block}-R{rep:03d}"
                start, terminal = rows[index], rows[index + 1]; index += 2
                if (start.get("schema_version"), start.get("record_type"), start.get("attempt_id"), start.get("arm"), start.get("block_id"), start.get("replicate")) != (LEDGER, "START", attempt, arm, block, rep): _bad("start")
                _object(start, {"schema_version","record_type","attempt_id","arm","block_id","replicate","request","response_schema","plan_sha256","pre_boundary_attestation","retry","terminal","ordinal","previous_record_sha256","record_sha256"})
                if start.get("plan_sha256") != plan_sha or start.get("retry") != "NONE": _bad("start join")
                if _blob(root, start["request"]) != _blob(root, marker["request"]): _bad("request bytes")
                if sha256(_blob(root, start["request"])).hexdigest() != plan["request_sha256"]: _bad("request hash")
                schema_raw = _blob(root, start["response_schema"])
                if sha256(schema_raw).hexdigest() != plan["material"]["response_schema_sha256"]: _bad("response schema join")
                schema = _canonical(schema_raw); _schema(schema)
                _boundary(root, start["pre_boundary_attestation"], arm=arm, block=block, phase="PRE", completed=rep - 1, server=server)
                if terminal.get("schema_version") != LEDGER or terminal.get("record_type") != "TERMINAL" or terminal.get("attempt_id") != attempt or terminal.get("start_record_sha256") != start.get("record_sha256") or terminal.get("retry") != "NONE" or terminal.get("retry_allowed") is not False: _bad("terminal")
                if terminal.get("outcome") != "SUCCEEDED": return {"terminal": INCOMPLETE}
                _boundary(root, terminal["post_boundary_attestation"], arm=arm, block=block, phase="POST", completed=rep, server=server)
                content = _blob(root, terminal["model_content_utf8"])
                raw_envelope = _blob(root, terminal["raw_envelope"]); envelope = _ordinary(raw_envelope)
                if type(envelope) is not dict: _bad("envelope")
                usage = envelope.get("usage")
                if envelope.get("model") != PINNED_MODEL or type(usage) is not dict or set(usage) != {"prompt_tokens", "completion_tokens", "total_tokens"} or any(type(usage.get(key)) is not int or usage[key] < 0 for key in usage) or usage["prompt_tokens"] + usage["completion_tokens"] != usage["total_tokens"]: _bad("envelope provenance")
                structured = _blob(root, terminal["structured_content_diagnostic"])
                parsed_content = _ordinary(content)
                if canonical_bytes(parsed_content) != structured: _bad("structured join")
                _schema(schema, parsed_content, instance=True)
                try:
                    tokens = _tokens(envelope, content)
                    trace = _blob(root, terminal["token_logprob_trace"])
                    # The producer uses ordinary ``json.loads`` for its trace;
                    # use a second ordinary parse here while keeping the
                    # lossless parse above for Decimal arithmetic.
                    trace_value = json.loads(raw_envelope.decode("utf-8", "strict"))
                    expected_trace = json.dumps(trace_value["choices"][0]["logprobs"]["content"], ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
                    if trace != expected_trace: _bad("trace projection")
                except ValueError: return {"terminal": UNAVAILABLE}
                contents[attempt] = content; token_rows[attempt] = tokens
        seal = rows[index] if index < len(rows) else None; index += 1
        if index != len(rows) or type(seal) is not dict or seal.get("schema_version") != LEDGER or seal.get("record_type") != "RUN_SEAL" or seal.get("status") != COMPLETE or (seal.get("started_slots"), seal.get("successful_slots"), seal.get("failed_slots")) != (16, 16, 0): _bad("run seal")
        if type(seal.get("blocks")) is not list or len(seal["blocks"]) != 4: _bad("run blocks")
        for summary, (arm, block), block_server in zip(seal["blocks"], BLOCKS, block_servers):
            if type(summary) is not dict or summary.get("arm") != arm or summary.get("block_id") != block or summary.get("started_slots") != 4 or summary.get("successful_slots") != 4: _bad("block summary")
            server = _object(summary.get("server_identity"), {"async_scheduling", "container_name", "observed"})
            if server != block_server: _bad("block summary server join")
            _boundary(root, summary.get("final_boundary_attestation"), arm=arm, block=block, phase="FINAL", completed=4, server=server)
        pattern, block_cardinality, arm_cardinality = _pattern(contents)
        block_modal_count, arm_modal_count = _modal_counts(contents)
        comparisons = []
        unavailable = False
        for arm in ARMS:
            blocks = [block for a, block in BLOCKS if a == arm]
            baseline = f"MI-024-{arm}-{blocks[0]}-R001"
            for block in blocks:
                for rep in range(1, 5):
                    target = f"MI-024-{arm}-{block}-R{rep:03d}"
                    if target == baseline: continue
                    row = _comparison(baseline, (contents[baseline], token_rows[baseline]), target, (contents[target], token_rows[target]))
                    if row is not None:
                        comparisons.append(row)
                        if row["token_status"] != "ALIGNED_BY_EMITTED_BYTES" or row["left"]["gap"]["peer_status"] != "PEER_TOKEN_IN_TOP20" or row["right"]["gap"]["peer_status"] != "PEER_TOKEN_IN_TOP20": unavailable = True
        descriptors = sorted({path.name for path in content_dir.iterdir() if path.is_file() and not path.is_symlink()})
        if any(SHA.fullmatch(item) is None for item in descriptors): _bad("content names")
        referenced: set[str] = set()
        for row in rows: _referenced_descriptors(row, referenced)
        if set(descriptors) != referenced: _bad("unreferenced or missing content")
        result = {"terminal": UNAVAILABLE if unavailable else COMPLETE, "observation_pattern": pattern,
                  "plan_sha256": plan_sha, "closure_manifest_sha256": sha256(closure_raw).hexdigest(),
                  "ledger_sha256": sha256(raw_ledger).hexdigest(),
                  "ledger_final_record_sha256": previous, "content_blob_count": len(descriptors),
                  "content_manifest_sha256": canonical_sha256(descriptors),
                  "block_content_cardinality": block_cardinality, "arm_content_cardinality": arm_cardinality,
                  "block_modal_content_count": block_modal_count, "arm_modal_content_count": arm_modal_count,
                  "all_content_cardinality": len(set(contents.values())), "modal_content_count": max(Counter(contents.values()).values()),
                  "first_divergence_diagnostics": comparisons}
        return result
    except Exception:
        return {"terminal": VOID}


__all__ = ["COMPLETE", "INCOMPLETE", "UNAVAILABLE", "VOID", "verify"]


def main(argv: list[str] | None = None) -> int:
    """Write a canonical independent result; only integrity VOID is nonzero."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--external-registry-root")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    result = verify(Path(args.root), external_registry_root=(Path(args.external_registry_root) if args.external_registry_root else None))
    raw = canonical_bytes(result)
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".mi-verifier-", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(raw); handle.flush(); os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            try: os.unlink(temporary)
            except FileNotFoundError: pass
    else:
        print(raw.decode("utf-8"))
    return 2 if result["terminal"] == VOID else 0


if __name__ == "__main__":
    raise SystemExit(main())
