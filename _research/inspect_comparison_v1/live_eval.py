"""Inspect evaluation of W1 E1 relation text through the isolated TypeScript bridge.

The bridge receives only the LocalSemanticInput, replacement relation text, and
execution configuration. Targets, split labels, case IDs, and arm labels remain
in evaluator custody.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from urllib.parse import urlsplit
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from inspect_ai import Task, eval, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.scorer import Score, Target, accuracy, scorer
from inspect_ai.solver import Generate, TaskState, solver

CHECKOUT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BRIDGE = ("node", str(Path(__file__).with_name("hswm_bridge.mts")))
INVALID_COMPLETION = "\u0000HSWM_LIVE_EVAL_INVALID_OUTPUT"
MAX_MODEL_CALLS = 128


@dataclass(frozen=True)
class Execution:
    base_url: str
    model: str
    max_tokens: int
    timeout_seconds: int
    seed: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "timeout_seconds": self.timeout_seconds,
            "seed": self.seed,
        }


@dataclass(frozen=True)
class LiveExample:
    id: str
    split: str
    input: dict[str, Any]
    target: str


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _nonblank(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-whitespace string")
    return value


def _exact_object(value: Any, keys: set[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{name} fields must be exactly {sorted(keys)}")
    return value


def _bit(value: Any, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value not in (0, 1):
        raise ValueError(f"{name} must be 0 or 1")


def validate_local_semantic_input(value: Any) -> dict[str, Any]:
    """Validate the W1 E1 input shape before the bridge can contact a model."""
    data = _exact_object(value, {"relation", "roles", "priorEvidence", "fields"}, "input")
    relation = _exact_object(data["relation"], {"semanticText", "disposition", "uncertainty", "exceptionRefs"}, "input.relation")
    for key in ("semanticText", "disposition", "uncertainty"):
        _nonblank(relation[key], f"input.relation.{key}")
    if not isinstance(relation["exceptionRefs"], list) or not all(isinstance(item, str) and item.strip() for item in relation["exceptionRefs"]):
        raise ValueError("input.relation.exceptionRefs must be string references")
    expected_roles = (("subject", 0), ("context", 1), ("exception", 2))
    if not isinstance(data["roles"], list) or len(data["roles"]) != len(expected_roles) or data["priorEvidence"] != []:
        raise ValueError("input must retain W1 ordered roles and empty priorEvidence")
    for index, (role, ordinal) in enumerate(expected_roles):
        observed = _exact_object(data["roles"][index], {"role", "ordinal", "referenceType"}, f"input.roles[{index}]")
        if observed["role"] != role or not isinstance(observed["ordinal"], int) or isinstance(observed["ordinal"], bool) or observed["ordinal"] != ordinal or observed["referenceType"] != "LOCAL_SEMANTIC_INPUT":
            raise ValueError("input must retain W1 ordered roles and empty priorEvidence")
    fields = _exact_object(data["fields"], {"subject", "context", "exception"}, "input.fields")
    for group, names in (("subject", {"dax", "wug", "zif"}), ("context", {"pel"}), ("exception", {"nub"})):
        role_fields = _exact_object(fields[group], names, f"input.fields.{group}")
        for name, bit in role_fields.items():
            _bit(bit, f"input.fields.{group}.{name}")
    return data


def load_live_jsonl(path: Path, split: str) -> list[LiveExample]:
    if split not in ("train", "heldout"):
        raise ValueError("split must be 'train' or 'heldout'")
    records: list[LiveExample] = []
    seen: set[str] = set()
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            raise ValueError(f"line {line_number}: blank lines are not allowed")
        try:
            value = json.loads(raw, object_pairs_hook=_object_without_duplicate_keys)
        except json.JSONDecodeError as error:
            raise ValueError(f"line {line_number}: invalid JSON") from error
        except ValueError as error:
            raise ValueError(f"line {line_number}: {error}") from error
        item = _exact_object(value, {"id", "split", "input", "target"}, f"line {line_number}")
        identifier = _nonblank(item["id"], f"line {line_number}.id")
        if identifier in seen:
            raise ValueError(f"line {line_number}: duplicate id {identifier!r}")
        seen.add(identifier)
        if item["split"] not in ("train", "heldout"):
            raise ValueError(f"line {line_number}.split must be train or heldout")
        if item["target"] not in ("0", "1"):
            raise ValueError(f"line {line_number}.target must be '0' or '1'")
        input_value = validate_local_semantic_input(item["input"])
        if item["split"] == split:
            records.append(LiveExample(identifier, split, input_value, item["target"]))
    if not records:
        raise ValueError(f"dataset has no {split!r} records")
    return records


def load_cases(path: Path, split: str = "heldout") -> list[LiveExample]:
    """Public shared loader for Inspect and GEPA; targets remain evaluator-only."""
    return load_live_jsonl(path, split)


def _validate_execution(execution: Execution) -> None:
    _nonblank(execution.base_url, "execution.base_url")
    _nonblank(execution.model, "execution.model")
    for name, value, low, high in (("max_tokens", execution.max_tokens, 1, 2048), ("timeout_seconds", execution.timeout_seconds, 1, 120), ("seed", execution.seed, 0, 2_147_483_647)):
        if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
            raise ValueError("execution max_tokens, timeout_seconds, or seed is out of bridge range")
    try:
        url = urlsplit(execution.base_url)
    except ValueError as error:
        raise ValueError("execution.base_url is invalid") from error
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ("", "/", "/v1", "/v1/"):
        raise ValueError("execution.base_url must be an HTTP model base URL without credentials")


def _invalid_result(error_kind: str, execution: Execution) -> dict[str, Any]:
    return {
        "valid": False, "answer": None, "error_kind": error_kind,
        "request_sha256": None, "response_sha256": None, "model": execution.model,
        "usage": None, "latency_ms": None, "model_calls": None,
        "model_calls_upper_bound": 1, "attempt_status": "UNKNOWN_AFTER_BRIDGE_TIMEOUT",
    }


def _validate_bridge_result(value: Any, execution: Execution) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("bridge returned non-object JSON")
    required = {"valid", "answer", "error_kind", "request_sha256", "response_sha256", "model", "usage", "latency_ms", "model_calls"}
    missing = required - set(value)
    if missing:
        raise RuntimeError(f"bridge response missing fields {sorted(missing)}")
    if not isinstance(value["valid"], bool) or value["model"] != execution.model or value["model_calls"] != 1:
        raise RuntimeError("bridge response has invalid validity, model, or call count")
    if value["valid"]:
        if value["answer"] not in ("0", "1") or value["error_kind"] is not None:
            raise RuntimeError("valid bridge response must carry a binary answer only")
    elif value["answer"] is not None or not isinstance(value["error_kind"], str) or not value["error_kind"].strip():
        raise RuntimeError("invalid bridge response must carry an error kind")
    for key in ("request_sha256", "response_sha256"):
        if value[key] is not None and (not isinstance(value[key], str) or len(value[key]) != 64):
            raise RuntimeError(f"bridge response has invalid {key}")
    return value


def evaluate_relation(
    candidate_text: str,
    example: LiveExample,
    execution: Execution,
    bridge_command: Sequence[str] = DEFAULT_BRIDGE,
) -> dict[str, Any]:
    """Execute one candidate relation through the bridge; targets never enter its stdin."""
    _nonblank(candidate_text, "candidate_text")
    _validate_execution(execution)
    payload = {"input": example.input, "relation_text": candidate_text, "execution": execution.as_dict()}
    payload_text = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    try:
        completed = subprocess.run(
            list(bridge_command), input=payload_text, text=True, capture_output=True,
            timeout=execution.timeout_seconds + 5, check=False,
        )
    except subprocess.TimeoutExpired:
        return _invalid_result("BRIDGE_TIMEOUT", execution)
    if completed.returncode != 0:
        raise RuntimeError(f"bridge configuration failure: {completed.stderr.strip() or completed.returncode}")
    try:
        result = json.loads(completed.stdout, object_pairs_hook=_object_without_duplicate_keys)
    except (json.JSONDecodeError, ValueError) as error:
        raise RuntimeError("bridge returned malformed JSON") from error
    return _validate_bridge_result(result, execution)


def dataset_for(examples: Iterable[LiveExample]) -> MemoryDataset:
    return MemoryDataset([
        Sample(input=json.dumps(example.input, sort_keys=True), target=example.target, id=example.id, metadata={"live_input": example.input})
        for example in examples
    ])


@solver
def live_relation_solver(relation_text: str, execution: Execution, bridge_command: Sequence[str] = DEFAULT_BRIDGE):
    """Use the bridge result as output while retaining malformed model responses as failures."""
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        example = LiveExample(str(state.sample_id), "heldout", dict(state.metadata["live_input"]), state.target.text)
        result = evaluate_relation(relation_text, example, execution, bridge_command)
        state.output.completion = result["answer"] if result["valid"] else INVALID_COMPLETION
        state.output.metadata = {"hswm_bridge": result}
        return state
    return solve


@scorer(metrics=[accuracy()])
def live_exact_answer():
    async def score(state: TaskState, target: Target) -> Score:
        bridge_result = (state.output.metadata or {}).get("hswm_bridge")
        return Score(value=bool(bridge_result and bridge_result["valid"] and bridge_result["answer"] == target.text))
    return score


def relation_task(examples: list[LiveExample], relation_text: str, execution: Execution, bridge_command: Sequence[str], name: str) -> Task:
    return Task(dataset=dataset_for(examples), solver=live_relation_solver(relation_text, execution, bridge_command), scorer=live_exact_answer(), name=name)


def run_live(
    examples: list[LiveExample], baseline_text: str, candidate_text: str, execution: Execution,
    log_dir: Path, bridge_command: Sequence[str] = DEFAULT_BRIDGE, dataset_sha256: str | None = None,
) -> tuple[Any, Any]:
    """Evaluate two relation texts on the same frozen examples and require successful Inspect logs."""
    _nonblank(baseline_text, "baseline_text")
    _nonblank(candidate_text, "candidate_text")
    if 2 * len(examples) > MAX_MODEL_CALLS:
        raise ValueError(f"comparison would exceed the {MAX_MODEL_CALLS} model-call attempt budget")
    log_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        {"id": example.id, "split": example.split, "input": example.input, "target": example.target}
        for example in examples
    ]
    source_digest = dataset_sha256 or hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    metadata = {
        "dataset_rows_sha256": source_digest,
        "baseline_relation_sha256": hashlib.sha256(baseline_text.encode()).hexdigest(),
        "candidate_relation_sha256": hashlib.sha256(candidate_text.encode()).hexdigest(),
        "execution": execution.as_dict(),
        "evidence_kind": "LOCAL_RELATION_TEXT_EXECUTION_NOT_CANONICAL_REVISION",
        "max_model_call_attempts": 2 * len(examples),
    }
    logs = eval(
        [
            relation_task(examples, baseline_text, execution, bridge_command, f"w1_e1_baseline_{source_digest[:12]}"),
            relation_task(examples, candidate_text, execution, bridge_command, f"w1_e1_candidate_{source_digest[:12]}"),
        ],
        model=None, log_dir=str(log_dir), fail_on_error=True,
        metadata=metadata, max_tasks=1,
    )
    failed = [str(log.status) for log in logs if log.status != "success"]
    if failed:
        raise RuntimeError(f"Inspect evaluation did not succeed: {', '.join(failed)}")
    baseline, candidate = logs
    return baseline, candidate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--baseline-relation", type=Path, required=True)
    parser.add_argument("--candidate-relation", type=Path, required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--max-tokens", type=int, default=32)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--split", choices=("train", "heldout"), default="heldout")
    parser.add_argument("--limit", type=int, default=4, help="bounded smoke limit; raise deliberately for a fuller run")
    parser.add_argument("--log-dir", type=Path, default=CHECKOUT_ROOT / ".hswm-local/inspect-live-eval")
    args = parser.parse_args()
    all_examples = load_live_jsonl(args.dataset, args.split)
    dataset_sha256 = hashlib.sha256(json.dumps([
        {"id": example.id, "split": example.split, "input": example.input, "target": example.target}
        for example in all_examples
    ], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if not 1 <= args.limit <= len(all_examples):
        raise ValueError("limit must be between 1 and the selected split size")
    execution = Execution(args.base_url, args.model, args.max_tokens, args.timeout_seconds, args.seed)
    logs = run_live(all_examples[:args.limit], args.baseline_relation.read_text(encoding="utf-8"), args.candidate_relation.read_text(encoding="utf-8"), execution, args.log_dir, dataset_sha256=dataset_sha256)
    print("\n".join(str(log.location) for log in logs))


if __name__ == "__main__":
    main()
