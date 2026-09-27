"""Run a bounded GEPA training comparison and a separate held-out comparison."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict
import argparse
import importlib
import json
from hashlib import sha256
from pathlib import Path
import sys
from typing import Any

from relation_optimizer import (
    Execution,
    Example,
    ReflectionProposer,
    RelationEvaluation,
    SharedEvaluator,
    evaluate_heldout,
    optimize_relation_text,
    result_to_evaluation,
)

CHECKOUT_ROOT = Path(__file__).resolve().parents[2]


def _resource_totals(outcomes: Sequence[RelationEvaluation]) -> dict[str, int]:
    return {
        "physical_model_calls": sum(item.physical_model_calls or 0 for item in outcomes),
        "unknown_physical_model_call_records": sum(item.physical_model_calls is None for item in outcomes),
        "model_call_upper_bound": sum(item.model_call_upper_bound for item in outcomes),
        "logical_model_calls": sum(item.logical_model_calls for item in outcomes),
        "input_tokens": sum(item.input_tokens or 0 for item in outcomes),
        "output_tokens": sum(item.output_tokens or 0 for item in outcomes),
        "unknown_input_token_records": sum(item.input_tokens is None for item in outcomes),
        "unknown_output_token_records": sum(item.output_tokens is None for item in outcomes),
    }


def _bridge_resource_totals(log: object) -> dict[str, int]:
    """Read already-written Inspect sample metadata without a second execution."""
    outcomes: list[RelationEvaluation] = []
    for sample in getattr(log, "samples", []) or []:
        output = getattr(sample, "output", None)
        metadata = getattr(output, "metadata", None) or {}
        result = metadata.get("hswm_bridge") if isinstance(metadata, Mapping) else None
        if not isinstance(result, Mapping):
            continue
        outcomes.append(result_to_evaluation(result, "0", str(getattr(sample, "id", "inspect-sample"))))
    return _resource_totals(outcomes)


def run_comparison(
    *,
    seed_relation_text: str,
    examples: Sequence[Example],
    execution: Execution,
    shared_evaluator: SharedEvaluator,
    reflection_proposer: ReflectionProposer,
    max_training_calls: int = 32,
    max_reflection_calls: int = 2,
    max_heldout_calls: int = 40,
    evaluate_heldout_arms: bool = True,
) -> dict[str, Any]:
    """Optimize only `split=train`, then score seed/chosen text on `split=heldout`.

    This returns a compact receipt-like report. It is not a canonical write or a
    research-result claim.  The shared evaluator owns model transport and raw
    private request/response storage.
    """
    train = [example for example in examples if (example.get("split") if isinstance(example, Mapping) else getattr(example, "split")) == "train"]
    heldout = [example for example in examples if (example.get("split") if isinstance(example, Mapping) else getattr(example, "split")) == "heldout"]
    if not train or not heldout:
        raise ValueError("examples require non-empty train and heldout splits")
    if 2 * len(heldout) > max_heldout_calls:
        raise ValueError("two heldout arms exceed their fixed total call budget")

    training_outcomes: list[RelationEvaluation] = []
    training_attempts = 0

    def counted_training(candidate: str, example: Example, request_execution: Execution) -> Mapping[str, object]:
        nonlocal training_attempts
        if training_attempts >= max_training_calls:
            # GEPA can issue a whole batch across its metric-stop boundary. Do
            # not make a 33rd provider request just to discover that fact.
            return {
                "valid": False, "answer": None, "error_kind": "REQUEST_ATTEMPT_BUDGET_EXHAUSTED",
                "request_sha256": None, "response_sha256": None,
                "model": request_execution["model"], "usage": None, "latency_ms": None,
                "model_calls": 0, "model_calls_upper_bound": 0,
                "attempt_status": "NOT_ATTEMPTED_BUDGET_EXHAUSTED",
            }
        training_attempts += 1
        result = shared_evaluator(candidate, example, request_execution)
        target = example["target"] if isinstance(example, Mapping) else getattr(example, "target")
        identifier = example["id"] if isinstance(example, Mapping) else getattr(example, "id")
        training_outcomes.append(result_to_evaluation(result, str(target), str(identifier)))
        return result

    optimized = optimize_relation_text(
        seed_relation_text=seed_relation_text,
        training_examples=train,
        shared_evaluator=counted_training,
        execution=execution,
        max_metric_calls=max_training_calls,
        max_reflection_calls=max_reflection_calls,
        custom_candidate_proposer=reflection_proposer,
    )
    selected = optimized.best_candidate
    if not isinstance(selected, str) or not selected.strip():
        raise RuntimeError("GEPA returned no relation-text candidate")

    seed_heldout: tuple[RelationEvaluation, ...] = ()
    candidate_heldout: tuple[RelationEvaluation, ...] = ()
    if evaluate_heldout_arms:
        seed_heldout = evaluate_heldout(
            candidate_text=seed_relation_text, heldout_examples=heldout,
            shared_evaluator=shared_evaluator, execution=execution,
        )
        candidate_heldout = evaluate_heldout(
            candidate_text=selected, heldout_examples=heldout,
            shared_evaluator=shared_evaluator, execution=execution,
        )
    return {
        "claim_boundary": "GEPA_COMPARATOR_ONLY_NOT_CANONICAL_WRITE_OR_EFFICACY_PROOF",
        "candidate_text": selected,
        "training_resource_counts": _resource_totals(training_outcomes),
        "training_request_attempts": training_attempts,
        "seed_heldout": [asdict(item) for item in seed_heldout],
        "candidate_heldout": [asdict(item) for item in candidate_heldout],
        "heldout_resource_counts": _resource_totals((*seed_heldout, *candidate_heldout)),
        "configured_limits": {
            "max_training_calls": max_training_calls,
            "max_reflection_calls": max_reflection_calls,
            "max_heldout_calls_total": max_heldout_calls,
        },
    }


def main() -> None:
    """Run only against output from `prepare_fixture.mts`, never `hswm_bridge --fixture`."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture_dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    fixture_dir, output_dir = args.fixture_dir, args.output_dir
    output_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    if str(CHECKOUT_ROOT) not in sys.path:
        sys.path.insert(0, str(CHECKOUT_ROOT))
    live_eval = importlib.import_module("_research.inspect_comparison_v1.live_eval")
    train = live_eval.load_cases(fixture_dir / "train.jsonl", "train")
    heldout = live_eval.load_cases(fixture_dir / "heldout.jsonl", "heldout")
    baseline = (fixture_dir / "baseline.txt").read_text(encoding="utf-8").strip()
    raw_execution = json.loads((fixture_dir / "execution.json").read_text(encoding="utf-8"))
    execution = live_eval.Execution(**raw_execution)
    train_ids, heldout_ids = {item.id for item in train}, {item.id for item in heldout}
    if train_ids & heldout_ids:
        raise ValueError("train and heldout IDs overlap")
    train_fields = {json.dumps(item.input["fields"], sort_keys=True) for item in train}
    heldout_fields = {json.dumps(item.input["fields"], sort_keys=True) for item in heldout}
    if train_fields & heldout_fields:
        raise ValueError("train and heldout input.fields overlap")
    if any(item.input["relation"]["semanticText"] != baseline for item in [*train, *heldout]):
        raise ValueError("every fixture relation text must equal the provisional baseline")
    inputs = {
        "train_jsonl_sha256": sha256((fixture_dir / "train.jsonl").read_bytes()).hexdigest(),
        "heldout_jsonl_sha256": sha256((fixture_dir / "heldout.jsonl").read_bytes()).hexdigest(),
        "baseline_sha256": sha256(baseline.encode()).hexdigest(),
        "execution_sha256": sha256(json.dumps(raw_execution, sort_keys=True).encode()).hexdigest(),
    }
    raw_training: list[Mapping[str, object]] = []

    def shared(candidate: str, example: object, ignored_execution: object) -> Mapping[str, object]:
        result = live_eval.evaluate_relation(candidate, example, execution)
        raw_training.append(result)
        return result

    reflection = __import__("relation_optimizer").make_http_reflection_proposer(execution.as_dict())
    try:
        report = run_comparison(
            seed_relation_text=baseline, examples=[*train, *heldout], execution=execution.as_dict(),
            shared_evaluator=shared, reflection_proposer=reflection,
            evaluate_heldout_arms=False,
        )
    except Exception as error:
        (output_dir / "training-raw.jsonl").write_text("".join(json.dumps(item) + "\n" for item in raw_training), encoding="utf-8")
        (output_dir / "reflection-raw.jsonl").write_text(
            "".join(json.dumps(item) + "\n" for item in getattr(reflection, "records", [])), encoding="utf-8"
        )
        (output_dir / "comparison.json").write_text(json.dumps({
            "status": "INCOMPLETE", "error": f"{type(error).__name__}: {error}",
            "claim_boundary": "GEPA_COMPARATOR_ONLY_NOT_CANONICAL_WRITE_OR_EFFICACY_PROOF",
        }, indent=2) + "\n", encoding="utf-8")
        raise
    (output_dir / "training-raw.jsonl").write_text("".join(json.dumps(item) + "\n" for item in raw_training), encoding="utf-8")
    (output_dir / "reflection-raw.jsonl").write_text(
        "".join(json.dumps(item) + "\n" for item in getattr(reflection, "records", [])), encoding="utf-8"
    )
    candidate = str(report["candidate_text"])
    (output_dir / "candidate.txt").write_text(candidate + "\n", encoding="utf-8")
    try:
        baseline_log, candidate_log = live_eval.run_live(heldout, baseline, candidate, execution, output_dir / "inspect-logs")
    except Exception as error:
        (output_dir / "comparison.json").write_text(json.dumps({
            "status": "INCOMPLETE", "error": f"{type(error).__name__}: {error}", "inputs": inputs,
            "claim_boundary": "GEPA_COMPARATOR_ONLY_NOT_CANONICAL_WRITE_OR_EFFICACY_PROOF",
        }, indent=2) + "\n", encoding="utf-8")
        raise
    report["inspect_log_locations"] = [str(baseline_log.location), str(candidate_log.location)]
    from inspect_ai.log import read_eval_log
    baseline_eval, candidate_eval = read_eval_log(baseline_log.location), read_eval_log(candidate_log.location)
    report["heldout_inspect_accuracy"] = {
        "baseline": baseline_eval.results.scores[0].metrics["accuracy"].value,
        "candidate": candidate_eval.results.scores[0].metrics["accuracy"].value,
    }
    baseline_totals = _bridge_resource_totals(baseline_eval)
    candidate_totals = _bridge_resource_totals(candidate_eval)
    report["heldout_resource_counts"] = {
        key: baseline_totals[key] + candidate_totals[key]
        for key in baseline_totals
    }
    reflection_records = getattr(reflection, "records", [])
    report["reflection_request_attempts"] = len(reflection_records)
    def reflection_tokens(record: Mapping[str, Any], key: str) -> int | None:
        usage = record.get("usage")
        value = usage.get(key) if isinstance(usage, Mapping) else None
        return value if type(value) is int and value >= 0 else None

    report["reflection_usage"] = {
        "input_tokens": sum(reflection_tokens(item, "prompt_tokens") or 0 for item in reflection_records),
        "output_tokens": sum(reflection_tokens(item, "completion_tokens") or 0 for item in reflection_records),
        "unknown_usage_records": sum(
            reflection_tokens(item, "prompt_tokens") is None or reflection_tokens(item, "completion_tokens") is None
            for item in reflection_records
        ),
    }
    report["inputs"] = inputs
    (output_dir / "comparison.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
