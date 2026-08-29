"""Independent raw-byte closure for executable Q roots; no producer imports."""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from typing import Any

from _research.dnrd5.canonical_json import (
    CanonicalJsonError,
    canonical_bytes,
    canonical_sha256,
    parse_canonical,
)

Q0_SCHEMA = "hswm-dnrd5-q0-response-reproducibility/v1"
MARKER_SCHEMA = "hswm-dnrd5-q-start-marker/v1"
LEDGER_SCHEMA = "hswm-dnrd5-q-executable-attempt-ledger/v1"
NAMESPACE = "DNRD5-Q-QUALIFICATION-ONLY/v1"
ZERO = "0" * 64
REPRODUCED = "REPRODUCED_ON_FROZEN_QUALIFICATION_CORPUS_UNDER_DECLARED_BOUNDARY"
FALSIFIED = "FALSIFIED_RESPONSE_REPRODUCIBILITY_ON_FROZEN_QUALIFICATION_CORPUS"
INCONCLUSIVE = "INCONCLUSIVE_QUALIFICATION_EVIDENCE"
SYSTEM_MESSAGE = "Act only as the bounded DNRD-5 token-native model function. Read the declared input, follow its instruction, and return exactly one object satisfying the supplied strict JSON schema."
_SHA = re.compile(r"^[0-9a-f]{64}$")


class IndependentQGatewayRootRefusal(ValueError):
    pass


def _fail(s: str) -> None:
    raise IndependentQGatewayRootRefusal(s)


def _sha(v: Any, l: str) -> str:
    if type(v) is not str or _SHA.fullmatch(v) is None:
        _fail(f"{l} is not SHA-256")
    return v


def _obj(v: Any, k: set[str], l: str) -> Mapping[str, Any]:
    if type(v) is not dict or set(v) != k:
        _fail(f"{l} key set drifted")
    return v


def _canon(raw: bytes, l: str) -> Mapping[str, Any]:
    try:
        v = parse_canonical(raw)
    except (CanonicalJsonError, TypeError) as e:
        _fail(f"{l} is not canonical JSON: {e}")
    if type(v) is not dict:
        _fail(f"{l} is not object")
    return v


def _blob(root: Path, d: Any, l: str) -> bytes:
    d = _sha(d, l)
    p = root / "content" / d
    if not p.is_file():
        _fail(f"{l} blob missing")
    raw = p.read_bytes()
    if sha256(raw).hexdigest() != d:
        _fail(f"{l} blob hash drifted")
    return raw


def _desc(root: Path, v: Any, l: str) -> bytes:
    x = _obj(v, {"sha256", "byte_length"}, l)
    raw = _blob(root, x["sha256"], l)
    if type(x["byte_length"]) is not int or x["byte_length"] != len(raw):
        _fail(f"{l} length drifted")
    return raw


def _order(a: list[str], seed: bytes) -> list[str]:
    out = list(a)
    n = 0
    for i in range(len(out) - 1, 0, -1):
        stream = b""
        while len(stream) < 8:
            stream += sha256(
                b"HSWM-DNRD5-Q0-CALL-ORDER-V1\0" + seed + n.to_bytes(8, "big")
            ).digest()
            n += 1
        j = int.from_bytes(stream[:8], "big") % (i + 1)
        out[i], out[j] = out[j], out[i]
    return out


def _strict(raw: bytes, l: str) -> Any:
    def unique(pairs: Any) -> dict[str, Any]:
        d = {}
        for k, v in pairs:
            if k in d:
                _fail(f"duplicate key in {l}")
            d[k] = v
        return d

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique,
            parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)),
        )
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as e:
        _fail(f"{l} not strict JSON: {e}")


def _valid(v: Any, s: Any, path: str = "$ ") -> None:
    if type(s) is not dict or s.get("type") not in {
        "object",
        "array",
        "string",
        "integer",
        "boolean",
        "null",
    }:
        _fail(f"unsupported response schema {path}")
    if "const" in s and (type(v) is not type(s["const"]) or v != s["const"]):
        _fail(f"const drift {path}")
    if "enum" in s and not any(type(v) is type(x) and v == x for x in s["enum"]):
        _fail(f"enum drift {path}")
    t = s["type"]
    if t == "object":
        p = s.get("properties")
        r = s.get("required")
        if (
            type(v) is not dict
            or type(p) is not dict
            or type(r) is not list
            or set(v) != set(p)
            or set(r) != set(p)
            or s.get("additionalProperties") is not False
        ):
            _fail(f"object drift {path}")
        for k, c in p.items():
            _valid(v[k], c, path + "." + k)
    elif t == "array":
        if (
            type(v) is not list
            or "items" not in s
            or not s.get("minItems", 0) <= len(v) <= s.get("maxItems", 10_000)
        ):
            _fail(f"array drift {path}")
        for x in v:
            _valid(x, s["items"], path + "[]")
    elif t == "string":
        if (
            type(v) is not str
            or not s.get("minLength", 0) <= len(v) <= s.get("maxLength", 65_536)
            or (
                "pattern" in s
                and (
                    type(s["pattern"]) is not str
                    or re.fullmatch(s["pattern"], v, re.ASCII) is None
                )
            )
        ):
            _fail(f"string drift {path}")
    elif t == "integer" and (
        type(v) is not int
        or not s.get("minimum", -(2**53 - 1)) <= v <= s.get("maximum", 2**53 - 1)
    ):
        _fail(f"integer drift {path}")
    elif t == "boolean" and type(v) is not bool:
        _fail(f"boolean drift {path}")
    elif t == "null" and v is not None:
        _fail(f"null drift {path}")


def _request(c: Mapping[str, Any], root: Path, model: str) -> bytes:
    ins = _blob(root, c["instruction_sha256"], "instruction").decode("utf-8")
    mi = parse_canonical(_blob(root, c["model_input_sha256"], "model input"))
    sc = parse_canonical(_blob(root, c["response_schema_sha256"], "response schema"))
    rng = _blob(root, c["rng_sha256"], "rng")
    if type(mi) is not dict or type(sc) is not dict or not ins:
        _fail("invalid corpus raw request material")
    seed = int.from_bytes(sha256(rng).digest()[:6], "big")
    return canonical_bytes(
        {
            "chat_template_kwargs": {"enable_thinking": False},
            "logprobs": False,
            "max_tokens": c["max_output_tokens"],
            "messages": [
                {"content": SYSTEM_MESSAGE, "role": "system"},
                {
                    "content": canonical_bytes(
                        {
                            "contractVersion": "hswm-dnrd5-q-model-input/v1",
                            "callClass": c["call_class"],
                            "instruction": ins,
                            "input": mi,
                        }
                    ).decode(),
                    "role": "user",
                },
            ],
            "model": model,
            "n": 1,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "hswm_dnrd5_q_" + c["call_class"].lower(),
                    "schema": sc,
                    "strict": True,
                },
            },
            "seed": seed,
            "stream": False,
            "temperature": 0,
            "top_p": 1,
        }
    )


def verify_q_gateway_root(root: Path) -> dict[str, Any]:
    ledger = root / "q_attempts.jsonl"
    if not root.is_dir() or not (root / "content").is_dir() or not ledger.is_file():
        _fail("incomplete Q root")
    raw = ledger.read_bytes()
    if not raw.endswith(b"\n") or not raw[:-1]:
        _fail("invalid Q ledger framing")
    rows = [_canon(x, "ledger row") for x in raw[:-1].split(b"\n")]
    prev = ZERO
    for i, row in enumerate(rows, 1):
        if (
            row.get("schema_version") != LEDGER_SCHEMA
            or row.get("namespace") != NAMESPACE
            or row.get("ordinal") != i
            or row.get("previous_record_sha256") != prev
        ):
            _fail("ledger chronology drifted")
        core = {k: v for k, v in row.items() if k != "record_sha256"}
        if row.get("record_sha256") != canonical_sha256(core):
            _fail("ledger self-hash drifted")
        prev = row["record_sha256"]
    m = rows[0]
    mk = {
        "schema_version",
        "namespace",
        "record_type",
        "q0",
        "marker",
        "root_genesis",
        "corpus_manifest",
        "ci_receipt",
        "verifier_build",
        "verifier_source",
        "source",
        "terminal",
        "ordinal",
        "previous_record_sha256",
        "record_sha256",
    }
    if (
        set(m) != mk
        or m.get("record_type") != "Q_START_MARKER"
        or m.get("terminal") != "Q_START_MARKER_PERSISTED_BEFORE_ANY_Q_GATEWAY_START"
    ):
        _fail("marker-first invariant drifted")
    qraw = _desc(root, m["q0"], "Q0")
    smraw = _desc(root, m["marker"], "Q marker")
    q = _canon(qraw, "Q0")
    sm = _canon(smraw, "Q marker")
    qkeys = {
        "schema_version",
        "namespace",
        "source",
        "gateway_version",
        "corpus_manifest_sha256",
        "corpus",
        "replicates",
        "comparator",
        "call_order",
        "call_order_algorithm",
        "call_order_seed_hex",
        "call_order_seed_sha256",
        "budget",
        "zero_retry",
        "identities",
        "verifier",
        "evidence_root_genesis_sha256",
        "allowed_terminals",
        "nonclaims",
    }
    if (
        set(q) != qkeys
        or q.get("schema_version") != Q0_SCHEMA
        or q.get("namespace") != NAMESPACE
        or q.get("gateway_version") != "hswm-dnrd5-q-provider-gateway/v1"
        or q.get("zero_retry") is not True
    ):
        _fail("Q0 boundary drifted")
    if (
        q.get("comparator")
        != "EXACT_REQUEST_RUNTIME_RNG_AND_MODEL_CONTENT_UTF8_STRUCTURED_EQUALITY"
        or q.get("allowed_terminals") != [REPRODUCED, FALSIFIED, INCONCLUSIVE]
        or q.get("nonclaims")
        != [
            "NOT_A_DNRD5_300_BLOCK_OCCURRENCE_CALL_OR_PILOT_EFFECT_DATA",
            "NOT_PROOF_OF_PROVIDER_KERNEL_CACHE_SCHEDULING_OR_GLOBAL_DETERMINISM",
            "NOT_PROOF_OF_NO_INTERFERENCE_OR_HSWM_CAUSAL_LEARNING",
            "NOT_FULL_RAW_ENVELOPE_USAGE_HEADER_OR_TIMING_REPRODUCIBILITY",
            "NOT_DEMONSTRATED_PRODUCTION_SHAPE_OR_SOURCE_A_QUALIFICATION",
        ]
    ):
        _fail("Q0 comparator/terminal/nonclaim drifted")
    if (
        type(q.get("source")) is not dict
        or type(q.get("verifier")) is not dict
        or set(q["source"]) != {"commit", "tree", "ci_receipt_sha256", "ci_terminal"}
        or set(q["verifier"]) != {"source", "build_output_sha256"}
        or q["verifier"]["source"] != q["source"]
        or q["source"].get("ci_terminal") != "FIRST_ATTEMPT_SUCCESSFUL_CI_BUILD"
    ):
        _fail("Q0 source/verifier v1 boundary drifted")
    ci_raw = _desc(root, m["ci_receipt"], "source CI receipt")
    build_raw = _desc(root, m["verifier_build"], "verifier build")
    verifier_source = _desc(root, m["verifier_source"], "verifier source")
    if (
        sha256(ci_raw).hexdigest() != q["source"].get("ci_receipt_sha256")
        or sha256(build_raw).hexdigest() != q["verifier"].get("build_output_sha256")
        or m.get("source") != q["source"]
    ):
        _fail("marker CI/build/source binding drifted")
    ci = _canon(ci_raw, "source CI receipt")
    build = _canon(build_raw, "verifier build")
    ci_keys = {
        "schema_version",
        "repository",
        "workflow",
        "head_sha",
        "run_attempt",
        "conclusion",
        "terminal",
    }
    if (
        set(ci) != ci_keys
        or ci.get("schema_version") != "hswm-dnrd5-q0-ci-receipt/v1"
        or ci.get("repository") != "gj3447/HSWM"
        or ci.get("workflow") != "CI"
        or ci.get("head_sha") != q["source"]["commit"]
        or ci.get("run_attempt") != 1
        or ci.get("conclusion") != "success"
        or ci.get("terminal") != "FIRST_ATTEMPT_SUCCESSFUL_CI_BUILD"
    ):
        _fail("source CI receipt content drifted")
    build_keys = {
        "schema_version",
        "source",
        "file_sha256",
        "forbidden_producer_imports_absent",
        "terminal",
    }
    if (
        set(build) != build_keys
        or build.get("schema_version") != "hswm-dnrd5-q0-independent-verifier-build/v1"
        or build.get("source") != q["verifier"]["source"]
        or type(build.get("file_sha256")) is not str
        or _SHA.fullmatch(build["file_sha256"]) is None
        or build.get("forbidden_producer_imports_absent") is not True
        or build.get("terminal") != "INDEPENDENT_RAW_BYTE_VERIFIER_BUILD_BOUND"
    ):
        _fail("verifier build content drifted")
    named_source = root / "q0.verifier-source.py"
    if (
        not named_source.is_file()
        or named_source.read_bytes() != verifier_source
        or sha256(verifier_source).hexdigest() != build["file_sha256"]
    ):
        _fail("verifier source descriptor/named file/SHA drifted")
    try:
        tree = ast.parse(verifier_source.decode("utf-8"))
    except (UnicodeDecodeError, SyntaxError) as error:
        _fail(f"verifier source AST invalid: {error}")
    forbidden = {
        "_research.dnrd5.q_provider_gateway",
        "_research.dnrd5.q0_freeze",
        "_research.dnrd5.q0_qualification",
    }
    forbidden_leaves = {name.rsplit(".", 1)[-1] for name in forbidden}
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [module, *(f"{module}.{alias.name}" for alias in node.names)]
            names.extend(alias.name for alias in node.names)
        if any(
            name in forbidden_leaves
            or any(name == item or name.startswith(item + ".") for item in forbidden)
            for name in names
        ):
            _fail("verifier source imports forbidden producer module")
    if (
        set(sm)
        != {
            "schema_version",
            "namespace",
            "q0_sha256",
            "evidence_root_genesis_sha256",
            "terminal",
            "nonclaims",
        }
        or sm.get("schema_version") != MARKER_SCHEMA
        or sm.get("namespace") != NAMESPACE
        or sm.get("q0_sha256") != sha256(qraw).hexdigest()
        or sm.get("evidence_root_genesis_sha256")
        != q.get("evidence_root_genesis_sha256")
    ):
        _fail("Q marker/Q0 binding drifted")
    genesis = _desc(root, m["root_genesis"], "root genesis")
    manifest = _desc(root, m["corpus_manifest"], "corpus manifest")
    if (
        sha256(genesis).hexdigest() != q.get("evidence_root_genesis_sha256")
        or sha256(manifest).hexdigest() != q.get("corpus_manifest_sha256")
        or not (root / "root-genesis.json").is_file()
        or (root / "root-genesis.json").read_bytes() != genesis
    ):
        _fail("root genesis/manifest drifted")
    corpus = q.get("corpus")
    mani = parse_canonical(manifest)
    if (
        type(corpus) is not list
        or not 3 <= len(corpus) <= 256
        or type(mani) is not dict
        or set(mani) != {"schema_version", "classification", "cases"}
        or mani.get("schema_version") != "hswm-dnrd5-q0-public-synthetic-corpus/v1"
        or mani.get("classification")
        != "PUBLIC_SYNTHETIC_QUALIFICATION_ONLY_NO_CORRECTNESS_EVALUATOR"
        or type(mani.get("cases")) is not list
    ):
        _fail("corpus/manifest invalid")
    cases = {}
    classes = set()
    for c in corpus:
        keys = {
            "case_id",
            "call_class",
            "request_sha256",
            "instruction_sha256",
            "model_input_sha256",
            "response_schema_sha256",
            "rng_sha256",
            "max_output_tokens",
        }
        if (
            type(c) is not dict
            or set(c) != keys
            or type(c.get("case_id")) is not str
            or c["case_id"] in cases
            or c.get("call_class")
            not in {"PRE_OUTCOME_TRAJECTORY", "REVISION_PROPOSAL", "FRESH_PROBE"}
            or c.get("max_output_tokens") not in {64, 128, 256}
        ):
            _fail("corpus case invalid")
        for x in (
            "request_sha256",
            "instruction_sha256",
            "model_input_sha256",
            "response_schema_sha256",
            "rng_sha256",
        ):
            _blob(root, c[x], "corpus " + x)
        cases[c["case_id"]] = c
        classes.add(c["call_class"])
    manifest_cases = {}
    for x in mani["cases"]:
        required = {
            "case_id",
            "call_class",
            "instruction",
            "max_output_tokens",
            "model_input",
            "response_schema",
            "rng_hex",
            "size_class",
        }
        if (
            type(x) is not dict
            or set(x) != required
            or type(x.get("case_id")) is not str
            or x["case_id"] in manifest_cases
            or type(x.get("instruction")) is not str
            or type(x.get("rng_hex")) is not str
            or len(x["rng_hex"]) % 2
            or any(ch not in "0123456789abcdef" for ch in x["rng_hex"])
        ):
            _fail("manifest raw case invalid")
        manifest_cases[x["case_id"]] = x
    if classes != {"PRE_OUTCOME_TRAJECTORY", "REVISION_PROPOSAL", "FRESH_PROBE"} or set(
        manifest_cases
    ) != set(cases):
        _fail("manifest does not exactly cover corpus")
    for cid, c in cases.items():
        x = manifest_cases[cid]
        if (
            x["call_class"] != c["call_class"]
            or x["max_output_tokens"] != c["max_output_tokens"]
            or sha256(x["instruction"].encode()).hexdigest() != c["instruction_sha256"]
            or sha256(canonical_bytes(x["model_input"])).hexdigest()
            != c["model_input_sha256"]
            or sha256(canonical_bytes(x["response_schema"])).hexdigest()
            != c["response_schema_sha256"]
            or sha256(bytes.fromhex(x["rng_hex"])).hexdigest() != c["rng_sha256"]
        ):
            _fail("manifest raw material does not bind Q0 corpus")
    reps = q.get("replicates")
    attempts = [
        f"DNRD5-Q-{cid[-3:]}-R{r:03d}" for cid in cases for r in range(1, reps + 1)
    ]
    sx = q.get("call_order_seed_hex")
    if (
        type(reps) is not int
        or not 2 <= reps <= 32
        or type(sx) is not str
        or _SHA.fullmatch(sx) is None
        or sha256(bytes.fromhex(sx)).hexdigest() != q.get("call_order_seed_sha256")
        or q.get("call_order_algorithm") != "FROZEN_SHA256_FISHER_YATES_V1"
        or q.get("call_order") != _order(attempts, bytes.fromhex(sx))
        or q.get("budget") != len(attempts)
    ):
        _fail("seeded permutation drifted")
    ids = q.get("identities")
    if type(ids) is not dict or set(ids) != {
        "endpoint_sha256",
        "model_identity_sha256",
        "runtime_identity_sha256",
        "tls_identity_sha256",
        "isolation_identity_sha256",
    }:
        _fail("identity shape drifted")
    for k, v in ids.items():
        _blob(root, v, "identity " + k)
    mid = parse_canonical(_blob(root, ids["model_identity_sha256"], "model identity"))
    if (
        type(mid) is not dict
        or not {"served_model_id", "model_root", "vllm_version"} <= set(mid)
        or any(
            type(mid[k]) is not str or not mid[k]
            for k in ("served_model_id", "model_root", "vllm_version")
        )
    ):
        _fail("unreconstructible model identity")
    if len(rows) != 1 + 2 * len(attempts):
        return {
            "terminal": INCONCLUSIVE,
            "reason": "MISSING_OR_EXTRA_ATTEMPT_RECORDS",
            "q0_sha256": sha256(qraw).hexdigest(),
        }
    obs = {}
    failed = False
    for i, aid in enumerate(q["call_order"]):
        s, t = rows[1 + 2 * i], rows[2 + 2 * i]
        cid = "QCASE-" + aid[8:11]
        rep = int(aid[-3:])
        c = cases.get(cid)
        if (
            c is None
            or s.get("record_type") != "START"
            or t.get("record_type") != "TERMINAL"
            or any(
                x.get("attempt_id") != aid
                or x.get("case_id") != cid
                or x.get("replicate") != rep
                or x.get("call_class") != c["call_class"]
                or x.get("retry") != "NONE"
                for x in (s, t)
            )
            or t.get("retry_allowed") is not False
            or t.get("start_record_sha256") != s.get("record_sha256")
        ):
            _fail("START/terminal pairing/order/retry drifted")
        sk = {
            "schema_version",
            "namespace",
            "record_type",
            "attempt_id",
            "case_id",
            "replicate",
            "call_class",
            "request",
            "response_schema",
            "identities",
            "retry",
            "terminal",
            "ordinal",
            "previous_record_sha256",
            "record_sha256",
        }
        if (
            set(s) != sk
            or s.get("terminal") != "DURABLY_VISIBLE_BEFORE_SINGLE_DISPATCH"
            or s.get("identities") != ids
        ):
            _fail("START identity/shape drifted")
        req = _desc(root, s["request"], "START request")
        schema = _desc(root, s["response_schema"], "START schema")
        if (
            sha256(req).hexdigest() != c["request_sha256"]
            or schema != _blob(root, c["response_schema_sha256"], "corpus schema")
            or req != _request(c, root, mid["served_model_id"])
        ):
            _fail("raw request reconstruction drifted")
        if t.get("terminal") != "CALL_ID_CONSUMED_NO_RETRY_RESUME_OR_REPLACEMENT":
            _fail("terminal invariant drifted")
        if t.get("outcome") == "FAILED":
            fk = {
                "schema_version",
                "namespace",
                "record_type",
                "attempt_id",
                "case_id",
                "replicate",
                "call_class",
                "start_record_sha256",
                "raw_envelope",
                "model_content_utf8",
                "structured_content",
                "http_status",
                "response_content_type",
                "provider_request_id",
                "outcome",
                "failure_code",
                "retry",
                "retry_allowed",
                "terminal",
                "ordinal",
                "previous_record_sha256",
                "record_sha256",
            }
            if (
                set(t) != fk
                or t.get("model_content_utf8") is not None
                or t.get("structured_content") is not None
                or type(t.get("failure_code")) is not str
            ):
                _fail("failed evidence shape drifted")
            if t.get("raw_envelope") is None:
                if any(
                    t.get(k) is not None
                    for k in (
                        "http_status",
                        "response_content_type",
                        "provider_request_id",
                    )
                ):
                    _fail("unobserved failure transport fields drifted")
            else:
                _desc(root, t["raw_envelope"], "failed raw envelope")
                if (
                    type(t.get("http_status")) is not int
                    or t["http_status"] < 0
                    or (
                        t.get("response_content_type") is not None
                        and type(t["response_content_type"]) is not str
                    )
                    or (
                        t.get("provider_request_id") is not None
                        and type(t["provider_request_id"]) is not str
                    )
                ):
                    _fail("observed failure transport fields drifted")
            failed = True
            continue
        tk = {
            "schema_version",
            "namespace",
            "record_type",
            "attempt_id",
            "case_id",
            "replicate",
            "call_class",
            "start_record_sha256",
            "raw_envelope",
            "model_content_utf8",
            "structured_content",
            "outcome",
            "retry",
            "retry_allowed",
            "terminal",
            "ordinal",
            "previous_record_sha256",
            "record_sha256",
        }
        if set(t) != tk or t.get("outcome") != "SUCCEEDED":
            _fail("success terminal shape drifted")
        env = _strict(_desc(root, t["raw_envelope"], "raw envelope"), "raw envelope")
        content = _desc(root, t["model_content_utf8"], "model content")
        structured = _desc(root, t["structured_content"], "structured content")
        usage = env.get("usage") if type(env) is dict else None
        if (
            type(env) is not dict
            or env.get("model") != mid["served_model_id"]
            or type(env.get("choices")) is not list
            or len(env["choices"]) != 1
            or type(env["choices"][0]) is not dict
            or env["choices"][0].get("finish_reason") != "stop"
            or type(env["choices"][0].get("message")) is not dict
            or type(env["choices"][0]["message"].get("content")) is not str
            or content != env["choices"][0]["message"]["content"].encode()
            or type(usage) is not dict
            or any(
                type(usage.get(k)) is not int or usage[k] < 0
                for k in ("prompt_tokens", "completion_tokens", "total_tokens")
            )
            or usage["prompt_tokens"] + usage["completion_tokens"]
            != usage["total_tokens"]
        ):
            _fail("raw response/model content/usage drifted")
        try:
            val = parse_canonical(content)
        except (CanonicalJsonError, TypeError) as error:
            _fail(f"model content is not canonical JSON: {error}")
        if structured != canonical_bytes(val):
            _fail("structured extraction drifted")
        _valid(val, parse_canonical(schema))
        obs[aid] = (
            sha256(req).hexdigest(),
            ids["runtime_identity_sha256"],
            ids["model_identity_sha256"],
            sha256(content).hexdigest(),
            sha256(structured).hexdigest(),
        )
    if failed:
        return {
            "terminal": INCONCLUSIVE,
            "reason": "FAILED_ATTEMPT",
            "q0_sha256": sha256(qraw).hexdigest(),
        }
    for cid in cases:
        group = [obs[f"DNRD5-Q-{cid[-3:]}-R{r:03d}"] for r in range(1, reps + 1)]
        if any(x != group[0] for x in group[1:]):
            return {
                "terminal": FALSIFIED,
                "reason": "EXACT_RESPONSE_OR_IDENTITY_MISMATCH",
                "q0_sha256": sha256(qraw).hexdigest(),
            }
    return {
        "terminal": REPRODUCED,
        "reason": "FINITE_CLIENT_OBSERVED_DECLARED_COMPARATOR_BOUNDARY_ONLY",
        "q0_sha256": sha256(qraw).hexdigest(),
    }


def _closure(root: Path) -> dict[str, Any]:
    """Add verifier-owned root metadata to one already validated terminal."""
    result = verify_q_gateway_root(root)
    ledger = (root / "q_attempts.jsonl").read_bytes()
    rows = [_canon(line, "ledger row") for line in ledger[:-1].split(b"\n")]
    result.update(
        {
            "ledger_sha256": sha256(ledger).hexdigest(),
            "final_record_sha256": rows[-1]["record_sha256"],
            "attempt_counts": {
                "started": sum(row.get("record_type") == "START" for row in rows),
                "terminal": sum(row.get("record_type") == "TERMINAL" for row in rows),
            },
            "source_a_authorized": False,
            "nonclaims": [
                "QUALIFICATION_ONLY_NOT_DNRD5_OCCURRENCE_OR_PILOT_EFFECT_DATA",
                "FINITE_CLIENT_OBSERVED_REPLAY_DOES_NOT_PROVE_PROVIDER_OR_GLOBAL_DETERMINISM",
                "COMPARATOR_EXCLUDES_FULL_ENVELOPE_USAGE_HEADERS_AND_TIMING",
                "PUBLIC_SYNTHETIC_CORPUS_IS_NOT_DEMONSTRATED_PRODUCTION_SHAPE",
                "SOURCE_A_REMAINS_UNAUTHORIZED",
            ],
        }
    )
    return result


def _verify_repository(root: Path, repository: Path) -> None:
    """Verify the frozen source tree and the exact published verifier source."""
    ledger = (root / "q_attempts.jsonl").read_bytes()
    marker = _canon(ledger.split(b"\n", 1)[0], "marker")
    q0 = _canon(_desc(root, marker["q0"], "Q0"), "Q0")
    build = _canon(
        _desc(root, marker["verifier_build"], "verifier build"), "verifier build"
    )
    try:
        tree = subprocess.check_output(
            [
                "git",
                "-C",
                str(repository),
                "rev-parse",
                f"{q0['source']['commit']}^{{tree}}",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as error:
        _fail(f"repository cannot resolve frozen source commit/tree: {error}")
    if tree != q0["source"]["tree"]:
        _fail("repository source tree differs from frozen Q0 source")
    source_blob = root / "q0.verifier-source.py"
    if not source_blob.is_file():
        _fail(
            "published q0.verifier-source.py blob is absent; source closure is unqualified"
        )
    if sha256(source_blob.read_bytes()).hexdigest() != build["file_sha256"]:
        _fail("published verifier source SHA differs from verifier build")
    try:
        committed_source = subprocess.check_output(
            [
                "git",
                "-C",
                str(repository),
                "show",
                f"{q0['source']['commit']}:_research/dnrd5/independent_q_gateway_root.py",
            ],
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        _fail(f"repository cannot open frozen verifier source blob: {error}")
    if committed_source != source_blob.read_bytes():
        _fail("published verifier source differs from frozen Git blob")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Independent read-only DNRD-5 Q-root closure verifier"
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        closure = _closure(args.root)
        _verify_repository(args.root, args.repository)
        if args.output.exists() or not args.output.parent.is_dir():
            _fail("closure output must be a new child of an existing directory")
        raw = canonical_bytes(closure)
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except (IndependentQGatewayRootRefusal, OSError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
