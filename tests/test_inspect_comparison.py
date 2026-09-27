"""Focused coverage for the isolated Inspect saved-output adapter."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

pytest.importorskip("inspect_ai", reason="Inspect comparison runs in its isolated uv environment")
from inspect_ai.log import read_eval_log


ROOT = Path(__file__).resolve().parents[1]
RESEARCH_DIR = ROOT / "_research" / "inspect_comparison_v1"


def load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, RESEARCH_DIR / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


paired_eval = load_module("paired_eval")
semantic_locality_adapter = load_module("semantic_locality_adapter")


def write_jsonl(path: Path, records: list[dict[str, str]]) -> None:
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")


def test_load_rejects_duplicate_and_incomplete_pairs(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.jsonl"
    record = {"id": "one", "input": "p", "target": "yes", "baseline": "no", "candidate": "yes"}
    write_jsonl(path, [record, record])
    with pytest.raises(ValueError, match="duplicate id"):
        paired_eval.load_paired_jsonl(path)

    path.write_text('{"id":"two","input":"p","target":"yes","baseline":"no"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="missing=.*candidate"):
        paired_eval.load_paired_jsonl(path)

    path.write_text(
        '{"id":"two","id":"two-again","input":"p","target":"yes","baseline":"no","candidate":"yes"}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate JSON key"):
        paired_eval.load_paired_jsonl(path)

    write_jsonl(path, [{**record, "id": "   "}])
    with pytest.raises(ValueError, match="id.*non-whitespace"):
        paired_eval.load_paired_jsonl(path)

    write_jsonl(path, [{**record, "candidate": "\t"}])
    with pytest.raises(ValueError, match="candidate.*non-whitespace"):
        paired_eval.load_paired_jsonl(path)


def test_inspect_writes_logs_and_scores_both_arms(tmp_path: Path) -> None:
    path = tmp_path / "paired.jsonl"
    write_jsonl(
        path,
        [
            {"id": "one", "input": "p1", "target": "yes", "baseline": "no", "candidate": "yes"},
            {"id": "two", "input": "p2", "target": "no", "baseline": "no", "candidate": "no"},
        ],
    )
    baseline, candidate = paired_eval.run(path, tmp_path / "logs")
    baseline_log, candidate_log = read_eval_log(baseline.location), read_eval_log(candidate.location)
    assert baseline_log.results.scores[0].metrics["accuracy"].value == 0.5
    assert candidate_log.results.scores[0].metrics["accuracy"].value == 1.0


def test_inspect_error_status_fails_the_runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "paired.jsonl"
    write_jsonl(path, [{"id": "one", "input": "p", "target": "yes", "baseline": "yes", "candidate": "yes"}])
    monkeypatch.setattr(
        paired_eval,
        "eval",
        lambda *args, **kwargs: [SimpleNamespace(status="success"), SimpleNamespace(status="error")],
    )
    with pytest.raises(RuntimeError, match="error"):
        paired_eval.run(path, tmp_path / "logs")


def test_source_adapter_rejects_target_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "observations.jsonl"
    write_jsonl(
        source,
        [
            {"id": "1", "arm": "full", "expected": "yes", "decision": "yes"},
            {"id": "1", "arm": "role_swap", "expected": "no", "decision": "no"},
        ],
    )
    with pytest.raises(ValueError, match="target mismatch"):
        semantic_locality_adapter.convert(source, tmp_path / "paired.jsonl", "full", "role_swap")


def test_source_adapter_retains_invalid_decision_as_a_failure(tmp_path: Path) -> None:
    source = tmp_path / "observations.jsonl"
    output = tmp_path / "paired.jsonl"
    write_jsonl(
        source,
        [
            {"id": "1", "arm": "full", "expected": "yes", "decision": "yes", "valid": False},
            {"id": "1", "arm": "role_swap", "expected": "yes", "decision": "yes", "valid": True},
        ],
    )
    assert semantic_locality_adapter.convert(source, output, "full", "role_swap") == 1
    pair = paired_eval.load_paired_jsonl(output)[0]
    assert pair.baseline == semantic_locality_adapter.INVALID_SAVED_OUTPUT
    baseline, candidate = paired_eval.run(output, tmp_path / "logs")
    assert read_eval_log(baseline.location).results.scores[0].metrics["accuracy"].value == 0.0
    assert read_eval_log(candidate.location).results.scores[0].metrics["accuracy"].value == 1.0
