"""Run an Inspect task over paired, pre-recorded outputs without a model call."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from inspect_ai import Task, eval, task
from inspect_ai.dataset import Dataset, MemoryDataset, Sample
from inspect_ai.scorer import Score, Target, accuracy, scorer
from inspect_ai.solver import Generate, TaskState, solver

Arm = Literal["baseline", "candidate"]
CHECKOUT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class PairedRecord:
    """A single fixed target with one saved output per comparison arm."""

    id: str
    input: str
    target: str
    baseline: str
    candidate: str


def _text(value: Any, field: str, line: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"line {line}: {field!r} must be a non-whitespace string")
    return value


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def load_paired_jsonl(path: Path) -> list[PairedRecord]:
    """Load strict JSONL records and reject incomplete or duplicate pairs."""
    records: list[PairedRecord] = []
    seen_ids: set[str] = set()
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            raise ValueError(f"line {line_number}: blank lines are not allowed")
        try:
            item = json.loads(raw, object_pairs_hook=_object_without_duplicate_keys)
        except json.JSONDecodeError as error:
            raise ValueError(f"line {line_number}: invalid JSON") from error
        except ValueError as error:
            raise ValueError(f"line {line_number}: {error}") from error
        if not isinstance(item, dict):
            raise ValueError(f"line {line_number}: record must be an object")
        allowed = {"id", "input", "target", "baseline", "candidate"}
        unknown = set(item) - allowed
        missing = allowed - set(item)
        if unknown or missing:
            raise ValueError(
                f"line {line_number}: fields must be exactly {sorted(allowed)}; "
                f"missing={sorted(missing)}, unknown={sorted(unknown)}"
            )
        record = PairedRecord(**{field: _text(item[field], field, line_number) for field in allowed})
        if record.id in seen_ids:
            raise ValueError(f"line {line_number}: duplicate id {record.id!r}")
        seen_ids.add(record.id)
        records.append(record)
    if not records:
        raise ValueError("input must contain at least one record")
    return records


def dataset_for(records: Iterable[PairedRecord]) -> Dataset:
    return MemoryDataset(
        [Sample(
            input=record.input,
            target=record.target,
            id=record.id,
            metadata={"baseline": record.baseline, "candidate": record.candidate},
        ) for record in records]
    )


@solver
def saved_output(arm: Arm):
    """Place one saved arm into Inspect's output; deliberately never calls a model."""
    if arm not in ("baseline", "candidate"):
        raise ValueError(f"unknown arm {arm!r}")

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        state.output.completion = str(state.metadata[arm])
        return state

    return solve


@scorer(metrics=[accuracy()])
def exact_saved_output():
    """Score a pre-recorded completion against the per-record target."""

    async def score(state: TaskState, target: Target) -> Score:
        return Score(value=state.output.completion == target.text)

    return score


@task
def paired_saved_outputs(path: str, arm: Arm = "baseline") -> Task:
    """An Inspect task for a selected arm of a strict paired JSONL file."""
    return Task(
        dataset=dataset_for(load_paired_jsonl(Path(path))),
        solver=saved_output(arm),
        scorer=exact_saved_output(),
        name=f"paired_saved_outputs_{arm}",
    )


def run(path: Path, log_dir: Path) -> tuple[Any, Any]:
    """Run both saved-output arms and write ordinary Inspect eval logs to log_dir."""
    log_dir.mkdir(parents=True, exist_ok=True)
    logs = eval(
        [paired_saved_outputs(str(path), "baseline"), paired_saved_outputs(str(path), "candidate")],
        model="mockllm/model",
        log_dir=str(log_dir),
        fail_on_error=True,
    )
    failed = [str(log.status) for log in logs if log.status != "success"]
    if failed:
        raise RuntimeError(f"Inspect evaluation did not succeed: {', '.join(failed)}")
    baseline, candidate = logs
    return baseline, candidate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="strict paired JSONL input")
    parser.add_argument(
        "--log-dir", type=Path, default=CHECKOUT_ROOT / ".hswm-local/inspect-comparison",
        help="ignored directory for Inspect .eval logs",
    )
    args = parser.parse_args()
    logs = run(args.input, args.log_dir)
    print("\n".join(str(log.location) for log in logs))


if __name__ == "__main__":
    main()
