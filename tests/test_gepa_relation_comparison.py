"""Actual GEPA integration coverage for the isolated relation-text adapter."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest

pytest.importorskip("gepa", reason="GEPA comparison runs in its isolated uv environment")

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "_research" / "gepa_relation_comparison_v1" / "relation_optimizer.py"


def _load():
    spec = importlib.util.spec_from_file_location("gepa_relation_optimizer", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


relation_optimizer = _load()
sys.modules["relation_optimizer"] = relation_optimizer


def _load_runner():
    spec = importlib.util.spec_from_file_location("gepa_relation_runner", MODULE_PATH.with_name("runner.py"))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


relation_runner = _load_runner()

EXECUTION = {
    "base_url": "http://127.0.0.1:8001/v1",
    "model": "qwen3-4b-real",
    "max_tokens": 128,
    "timeout_seconds": 5.0,
    "seed": 0,
}


def test_actual_gepa_evaluator_adapter_returns_score_and_reflection_side_info() -> None:
    def shared(candidate: str, example: dict[str, object], execution: dict[str, object]):
        assert execution["model"] == "qwen3-4b-real"
        return {"id": example["id"], "valid": True, "answer": "1" if candidate == "revised" else "0",
                "error_kind": None, "request_sha256": "a", "response_sha256": "b", "model": execution["model"],
                "usage": {"input_tokens": 12, "output_tokens": 3, "total_tokens": 15}, "latency_ms": 1, "model_calls": 1}

    training_input = {"relation": {"semanticText": "baseline"}, "fields": {"subject": {"dax": 1}}}
    score, side_info = relation_optimizer.make_gepa_evaluator(shared, EXECUTION)("seed", {"id": "train-1", "target": "1", "input": training_input})
    assert score == 0.0
    assert side_info["feedback"] == "training execution returned answer='0', error_kind=None"
    assert side_info["resource_counts"]["input_tokens"] == 12
    assert side_info["training_input"]["fields"] == training_input["fields"]
    assert side_info["training_input"]["relation"]["semanticText"] == "seed"
    assert training_input["relation"]["semanticText"] == "baseline"
    assert side_info["observed_answer"] == "0"
    assert side_info["expected_answer"] == "1"


def test_heldout_is_never_sent_to_gepa_and_is_evaluated_separately() -> None:
    calls: list[str] = []

    def shared(candidate: str, example: dict[str, object], execution: dict[str, object]):
        calls.append(str(example["id"]))
        return {"id": example["id"], "valid": True, "answer": "1", "error_kind": None,
                "request_sha256": "a", "response_sha256": "b", "model": execution["model"],
                "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}, "latency_ms": 1, "model_calls": 1}

    outcomes = relation_optimizer.evaluate_heldout(
        candidate_text="candidate", heldout_examples=[{"id": "hidden-1", "target": "1", "label": "secret"}],
        shared_evaluator=shared, execution=EXECUTION
    )
    assert outcomes[0].case_id == "hidden-1"
    assert calls == ["hidden-1"]


def test_real_gepa_accepts_the_custom_proposer_configuration() -> None:
    """Use the pinned library's own optimizer; proposer avoids a reflection model call."""
    def shared(candidate: str, example: dict[str, object], execution: dict[str, object]):
        return {"id": example["id"], "valid": True, "answer": "1" if candidate == "revised" else "0",
                "error_kind": None, "request_sha256": "a", "response_sha256": "b", "model": execution["model"],
                "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}, "latency_ms": 1, "model_calls": 1}

    def proposer(candidate, reflective_dataset, components_to_update):
        return {component: "revised" for component in components_to_update}

    result = relation_optimizer.optimize_relation_text(
        seed_relation_text="seed", training_examples=[{"id": "train-1", "target": "1"}], shared_evaluator=shared,
        execution=EXECUTION, max_metric_calls=2, max_reflection_calls=1, custom_candidate_proposer=proposer,
    )
    assert result is not None


def test_runner_keeps_heldout_out_of_gepa_training_and_reports_both_arms() -> None:
    calls: list[tuple[str, str]] = []
    reflection_context: list[object] = []

    def shared(candidate: str, example: dict[str, object], execution: dict[str, object]):
        calls.append((str(example["id"]), candidate))
        expected = "revised"
        return {"valid": True, "answer": "1" if candidate == expected else "0", "error_kind": None,
                "request_sha256": "a", "response_sha256": "b", "model": execution["model"],
                "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}, "latency_ms": 1, "model_calls": 1}

    def proposer(candidate, reflective_dataset, components_to_update):
        reflection_context.append(reflective_dataset)
        return {component: "revised" for component in components_to_update}

    report = relation_runner.run_comparison(
        seed_relation_text="seed",
        examples=[
            {"id": "train-1", "split": "train", "target": "1"},
            {"id": "heldout-1", "split": "heldout", "target": "1"},
        ],
        execution=EXECUTION,
        shared_evaluator=shared,
        reflection_proposer=proposer,
        max_training_calls=32,
        max_reflection_calls=1,
        max_heldout_calls=2,
    )
    assert report["claim_boundary"].startswith("GEPA_COMPARATOR_ONLY")
    assert report["candidate_text"] == "revised"
    assert report["heldout_resource_counts"]["physical_model_calls"] == 2
    assert calls[-2:] == [("heldout-1", "seed"), ("heldout-1", "revised")]
    assert reflection_context
    assert "heldout-1" not in repr(reflection_context)
