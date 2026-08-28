"""Cross-implementation known-answer tests for DNRD-5 plan JSON only."""

from __future__ import annotations

import ast
from hashlib import sha256
import json
from pathlib import Path

import pytest

from _research.dnrd5 import (
    independent_plan_json,
    independent_randomization,
    occurrence_preflight,
    plan_json,
    randomization,
)


KAT_PATH = Path(__file__).resolve().parents[1] / "_research/dnrd5/vectors/plan_json_v1_kat.json"
KAT_SHA256 = "012dcc2ebf71dd6b54dfceec9aeeb72673961c64830694ab7bb7c678deb6051f"


def _kat_raw() -> bytes:
    return KAT_PATH.read_bytes()


def _kat() -> dict[str, object]:
    raw = _kat_raw()
    assert len(raw) == 3_618
    assert sha256(raw).hexdigest() == KAT_SHA256
    value = json.loads(raw.decode("utf-8"))
    assert type(value) is dict
    return value


def test_fixed_kat_corpus_binds_contract_and_two_independent_codecs() -> None:
    corpus = _kat()
    assert occurrence_preflight.PLAN_JSON_KAT_SHA256 == KAT_SHA256
    assert occurrence_preflight.PLAN_JSON_KAT_BYTE_LENGTH == len(_kat_raw())
    assert occurrence_preflight.PLAN_JSON_KAT_MEDIA_TYPE == (
        "application/vnd.hswm.dnrd5.plan-json-kat-v1+json"
    )
    assert set(corpus) == {
        "schema_version",
        "contract",
        "valid",
        "invalid_raw",
        "generated_over_1mib_case",
        "full_plan_known_answers",
    }
    assert corpus["schema_version"] == "hswm-dnrd5-plan-json-kat/v1"
    assert corpus["contract"] == {
        "contract_version": plan_json.CONTRACT_VERSION,
        "key_domain": "PRINTABLE_ASCII_U0020_THROUGH_U007E",
        "key_max_length": plan_json.KEY_MAX_LENGTH,
        "key_min_length": plan_json.KEY_MIN_LENGTH,
        "max_bytes": plan_json.MAX_BYTES,
        "max_depth": plan_json.MAX_DEPTH,
        "max_nodes": plan_json.MAX_NODES,
        "value_string_domain": "UNICODE_SCALARS_NO_LONE_SURROGATES",
    }
    assert plan_json.CONTRACT_VERSION == independent_plan_json.CONTRACT_VERSION
    assert plan_json.MEDIA_TYPE == independent_plan_json.MEDIA_TYPE
    assert plan_json.MAX_BYTES == independent_plan_json.MAX_BYTES
    assert plan_json.MAX_DEPTH == independent_plan_json.MAX_DEPTH
    assert plan_json.MAX_NODES == independent_plan_json.MAX_NODES
    assert plan_json.KEY_MIN_LENGTH == independent_plan_json.KEY_MIN_LENGTH
    assert plan_json.KEY_MAX_LENGTH == independent_plan_json.KEY_MAX_LENGTH

    for row in corpus["valid"]:  # type: ignore[index]
        assert type(row) is dict
        expected = row["canonical_utf8"].encode("utf-8")
        assert sha256(expected).hexdigest() == row["sha256"]
        assert plan_json.canonical_bytes(row["value"]) == expected
        assert independent_plan_json.canonical_bytes(row["value"]) == expected
        assert plan_json.parse_canonical(expected) == row["value"]
        assert independent_plan_json.parse_canonical(expected) == row["value"]


def test_fixed_invalid_raw_kat_is_refused_by_both_codecs() -> None:
    for row in _kat()["invalid_raw"]:  # type: ignore[index]
        assert type(row) is dict
        raw = row["raw_utf8"].encode("utf-8")
        with pytest.raises(plan_json.PlanJsonError):
            plan_json.parse_canonical(raw)
        with pytest.raises(independent_plan_json.IndependentPlanJsonError):
            independent_plan_json.parse_canonical(raw)


def test_generated_over_one_mib_known_answer_and_exact_limit() -> None:
    metadata = _kat()["generated_over_1mib_case"]
    assert metadata == {
        "kind": "repeat_string_value",
        "key": "value",
        "character": "x",
        "repeat_count": 1_048_577,
        "expected_byte_length": 1_048_589,
        "expected_sha256": "4e2480fd5e328040c22c173f5c57a027ac508f3501df83251f42460a013e92ca",
    }
    value = {metadata["key"]: metadata["character"] * metadata["repeat_count"]}
    encoded = plan_json.canonical_bytes(value)
    assert encoded == independent_plan_json.canonical_bytes(value)
    assert len(encoded) == metadata["expected_byte_length"]
    assert sha256(encoded).hexdigest() == metadata["expected_sha256"]
    assert len(encoded) > 1_048_576

    exact_limit = {"value": "x" * (plan_json.MAX_BYTES - len(b'{"value":""}'))}
    assert len(plan_json.canonical_bytes(exact_limit)) == plan_json.MAX_BYTES
    assert plan_json.canonical_bytes(exact_limit) == independent_plan_json.canonical_bytes(exact_limit)
    too_large = {"value": "x" * (plan_json.MAX_BYTES - len(b'{"value":""}') + 1)}
    with pytest.raises(plan_json.PlanJsonError):
        plan_json.canonical_bytes(too_large)
    with pytest.raises(independent_plan_json.IndependentPlanJsonError):
        independent_plan_json.canonical_bytes(too_large)


def test_two_full_300_block_plan_known_answers_match_independent_rederivation() -> None:
    rows = _kat()["full_plan_known_answers"]
    assert type(rows) is list and len(rows) == 2
    for row in rows:
        assert type(row) is dict
        produced = randomization.derive_study_plan(
            future_randomness_hex=row["future_randomness_hex"],
            study_binding_sha256=row["study_binding_sha256"],
        )
        independently_rederived = independent_randomization.derive_study_plan(
            future_randomness_hex=row["future_randomness_hex"],
            study_binding_sha256=row["study_binding_sha256"],
        )
        producer_bytes = randomization.canonical_json_bytes(produced)
        independent_bytes = independent_randomization.canonical_json_bytes(
            independently_rederived
        )
        assert producer_bytes == independent_bytes
        assert len(producer_bytes) == row["expected_byte_length"]
        assert sha256(producer_bytes).hexdigest() == row["expected_sha256"]
        assert produced["study_plan_sha256"] == row["expected_study_plan_sha256"]
        assert independently_rederived["study_plan_sha256"] == row["expected_study_plan_sha256"]
        assert sum(len(block["private_call_schedule"]) for block in produced["blocks"]) == 2_700


def test_runtime_value_key_depth_and_node_boundaries_match() -> None:
    valid = {"x" * 128: {"inner": "눈😀"}}
    assert plan_json.canonical_bytes(valid) == independent_plan_json.canonical_bytes(valid)
    invalid_values: tuple[object, ...] = (
        {"x" * 129: 1},
        {"é": 1},
        {"a\n": 1},
        {"nested": {"😀": 1}},
        {"": 1},
        {1: "non-string-key"},
        {"value": "\ud800"},
        1.25,
        float("nan"),
        float("inf"),
        9_007_199_254_740_992,
        (1, 2),
        object(),
    )
    for value in invalid_values:
        with pytest.raises(plan_json.PlanJsonError):
            plan_json.canonical_bytes(value)
        with pytest.raises(independent_plan_json.IndependentPlanJsonError):
            independent_plan_json.canonical_bytes(value)

    huge_integer_raw = b'{"value":' + (b"9" * 5_000) + b"}"
    with pytest.raises(plan_json.PlanJsonError):
        plan_json.parse_canonical(huge_integer_raw)
    with pytest.raises(independent_plan_json.IndependentPlanJsonError):
        independent_plan_json.parse_canonical(huge_integer_raw)

    allowed: object = None
    for _ in range(plan_json.MAX_DEPTH):
        allowed = [allowed]
    assert plan_json.canonical_bytes(allowed) == independent_plan_json.canonical_bytes(allowed)
    too_deep = [allowed]
    with pytest.raises(plan_json.PlanJsonError):
        plan_json.canonical_bytes(too_deep)
    with pytest.raises(independent_plan_json.IndependentPlanJsonError):
        independent_plan_json.canonical_bytes(too_deep)

    maximum_nodes = [0] * (plan_json.MAX_NODES - 1)
    assert plan_json.canonical_bytes(maximum_nodes) == independent_plan_json.canonical_bytes(maximum_nodes)
    too_many_nodes = [0] * plan_json.MAX_NODES
    with pytest.raises(plan_json.PlanJsonError):
        plan_json.canonical_bytes(too_many_nodes)
    with pytest.raises(independent_plan_json.IndependentPlanJsonError):
        independent_plan_json.canonical_bytes(too_many_nodes)


def test_independent_codec_import_graph_excludes_producer_codec() -> None:
    source = Path(independent_plan_json.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )
    assert "_research.dnrd5.plan_json" not in imported
    assert "_research.dnrd5.randomization" not in imported
