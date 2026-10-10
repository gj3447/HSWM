"""Bounded, development-exposed single-E1 oracle diagnostic.

It reuses live_eval's one-request bridge. It neither changes W nor establishes
efficacy. Plan/verify perform only local fixture validation; run first freezes
all four fixture families, then permits at most 64 model-call attempts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

from live_eval import Execution, LiveExample, load_live_jsonl, run_live

CHECKOUT_ROOT = Path(__file__).resolve().parents[2]
FAMILIES = range(4)
COHORT = "DEVELOPMENT_EXPOSED_HISTORICAL_FAMILY_NOT_FINAL_HOLDOUT"
SOURCE_PATHS = frozenset({
    "_research/dgx_semantic_learning_v1/domain.mts",
    "src/hswm/effect-runtime/src/local-semantic-execution-domain.ts",
    "_research/inspect_comparison_v1/prepare_oracle_diagnostic.mts",
})
FIXTURE_FILES = ("train.jsonl", "baseline.txt", "oracle.txt", "execution.json")
SCREEN_KEYS = frozenset({
    "oracleCorrectAtLeast", "frozenRuleConsistencyAtLeast",
    "eachFamilyOracleCorrectAtLeast", "allOutputsValid",
    "mandatoryExceptionCasesRecorded", "decisionPass", "decisionFail",
    "noEfficacyOrPopulationClaim",
})
ID_PATTERN = re.compile(r"^local-semantic-f([0-3])-i(\d{2})$")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _read(path: Path) -> bytes:
    return path.read_bytes()


class _FrozenTextPath:
    """Minimal read-only adapter so live_eval parses the already hashed bytes."""

    def __init__(self, label: Path, contents: bytes) -> None:
        self._label = label
        self._contents = contents

    def read_text(self, encoding: str = "utf-8") -> str:
        return self._contents.decode(encoding)

    def __str__(self) -> str:
        return str(self._label)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(_read(path))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid JSON fixture: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"fixture must be an object: {path}")
    return value


def _write_new(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _bit(value: Any, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value not in (0, 1):
        raise ValueError(f"{name} must be a bit")
    return value


def _nonblank(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonblank string")
    return value


def _fixture_digest(files: dict[str, bytes]) -> str:
    # This matches the TypeScript generator's ordered NUL-delimited aggregate.
    return digest(b"".join(name.encode() + b"\0" + files[name] for name in FIXTURE_FILES))


def _screen(value: Any) -> dict[str, Any]:
    expected = {
        "oracleCorrectAtLeast": 30,
        "frozenRuleConsistencyAtLeast": 30,
        "eachFamilyOracleCorrectAtLeast": 7,
        "allOutputsValid": True,
        "mandatoryExceptionCasesRecorded": True,
        "decisionPass": "DEVELOPMENT_SCREEN_PASSED",
        "decisionFail": "REVISE_LOCAL_EXECUTION",
        "noEfficacyOrPopulationClaim": True,
    }
    if not isinstance(value, dict) or set(value) != SCREEN_KEYS or value != expected:
        raise ValueError("unexpected screening contract")
    return expected


def _validate_source_pins(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != SOURCE_PATHS:
        raise ValueError("source pins must exactly name the approved local sources")
    result: dict[str, str] = {}
    for relative, claimed in value.items():
        if not isinstance(claimed, str) or not re.fullmatch(r"[0-9a-f]{64}", claimed):
            raise ValueError(f"invalid source hash for {relative}")
        source = CHECKOUT_ROOT / relative
        if not source.is_file() or digest(_read(source)) != claimed:
            raise ValueError(f"source byte hash mismatch: {relative}")
        result[relative] = claimed
    return result


def _original_id(case_id: str, family: int) -> int:
    match = ID_PATTERN.fullmatch(case_id)
    if not match or int(match.group(1)) != family:
        raise ValueError(f"unexpected selected case id: {case_id}")
    original_id = int(match.group(2))
    if not 0 <= original_id < 32:
        raise ValueError(f"selected case ID out of range: {case_id}")
    return original_id


def _selected_manifest(value: Any) -> dict[int, dict[str, Any]]:
    if not isinstance(value, list) or len(value) != 8:
        raise ValueError("selected manifest must declare exactly eight cases")
    selected: dict[int, dict[str, Any]] = {}
    expected_keys = {"originalId", "expected", "pel", "nub", "frozenRuleExpected", "evaluatorOnly"}
    for row in value:
        if not isinstance(row, dict) or set(row) != expected_keys:
            raise ValueError("selected manifest has an invalid field set")
        original_id = row["originalId"]
        if not isinstance(original_id, int) or isinstance(original_id, bool) or not 0 <= original_id < 32:
            raise ValueError("selected originalId is invalid")
        expected, pel, nub = (_bit(row[key], key) for key in ("expected", "pel", "nub"))
        frozen = _bit(row["frozenRuleExpected"], "frozenRuleExpected")
        if frozen != expected ^ pel or row["evaluatorOnly"] != {
            "groundTruth": expected, "frozenRuleExpected": frozen
        }:
            raise ValueError("selected evaluator-only values disagree with supplied rule")
        if original_id in selected:
            raise ValueError("duplicate selected originalId")
        selected[original_id] = dict(row)
    if {(row["expected"], row["pel"], row["nub"]) for row in selected.values()} != {
        (target, pel, nub) for target in (0, 1) for pel in (0, 1) for nub in (0, 1)
    }:
        raise ValueError("selected cases do not cover all target/context/exception strata")
    return selected


def _execution(value: Any) -> dict[str, Any]:
    keys = {"base_url", "model", "max_tokens", "timeout_seconds", "seed"}
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError("execution configuration has an invalid field set")
    for key in ("max_tokens", "timeout_seconds", "seed"):
        if not isinstance(value[key], int) or isinstance(value[key], bool):
            raise ValueError("execution numeric values must be integers")
    _nonblank(value["base_url"], "execution.base_url")
    _nonblank(value["model"], "execution.model")
    return dict(value)


def _case_record(example: LiveExample, family: int, selected: dict[int, dict[str, Any]], baseline: str) -> dict[str, Any]:
    original_id = _original_id(example.id, family)
    declared = selected.get(original_id)
    if declared is None:
        raise ValueError(f"case not declared by fixture manifest: {example.id}")
    fields = example.input["fields"]
    expected = _bit(declared["expected"], "expected")
    if (
        example.target != str(expected)
        or fields["context"]["pel"] != declared["pel"]
        or fields["exception"]["nub"] != declared["nub"]
        or example.input["relation"]["semanticText"] != baseline.rstrip("\n")
    ):
        raise ValueError(f"train row disagrees with its frozen manifest relation: {example.id}")
    return {
        "id": example.id, "original_id": original_id, "target": example.target,
        "pel": declared["pel"], "nub": declared["nub"],
        "frozen_rule_expected": str(declared["frozenRuleExpected"]),
        "input": example.input, "input_sha256": digest(_json_bytes(example.input)),
    }


def family_plan(fixture_root: Path, family: int) -> dict[str, Any]:
    directory = fixture_root / f"family-{family}"
    manifest = _load_json(directory / "fixture.json")
    if manifest.get("schema") != "hswm-inspect-oracle-single-diagnostic/v1" or manifest.get("family") != family:
        raise ValueError("family fixture schema or number mismatch")
    if (
        manifest.get("developmentExposure") != COHORT
        or manifest.get("originalHistoricalMembership") != "NOT_CLAIMED_AS_HELDOUT"
        or manifest.get("fixedArms") != ["FROZEN_SINGLE_E1", "ORACLE_SINGLE_E1"]
        or manifest.get("maxModelCallsForThisFamily") != 16
    ):
        raise ValueError("family cohort or call-bound contract mismatch")
    screening = _screen(manifest.get("screening"))
    source_pins = _validate_source_pins(manifest.get("sourceSha256"))
    file_hashes = manifest.get("files")
    if not isinstance(file_hashes, dict) or set(file_hashes) != set(FIXTURE_FILES):
        raise ValueError("fixture must hash exactly its four executable files")
    files = {name: _read(directory / name) for name in FIXTURE_FILES}
    for name, contents in files.items():
        if file_hashes[name] != digest(contents):
            raise ValueError(f"fixture file hash mismatch: family-{family}/{name}")
    fixture_sha = _fixture_digest(files)
    if manifest.get("fixtureSha256") != fixture_sha:
        raise ValueError("fixture aggregate hash mismatch")
    try:
        execution = _execution(json.loads(files["execution.json"]))
    except json.JSONDecodeError as error:
        raise ValueError("invalid execution JSON") from error
    selected = _selected_manifest(manifest.get("selected"))
    # Do not let the shared loader reread a filesystem path after it was hashed.
    examples = load_live_jsonl(_FrozenTextPath(directory / "train.jsonl", files["train.jsonl"]), "train")
    if len(examples) != 8 or len({example.id for example in examples}) != 8:
        raise ValueError("family fixture must contain exactly eight distinct train examples")
    baseline, oracle = files["baseline.txt"].decode(), files["oracle.txt"].decode()
    _nonblank(baseline, "baseline relation")
    _nonblank(oracle, "oracle relation")
    cases = [_case_record(example, family, selected, baseline) for example in examples]
    if set(item["original_id"] for item in cases) != set(selected):
        raise ValueError("train rows and selected manifest differ")
    dataset_rows = [{"id": x["id"], "split": "train", "input": x["input"], "target": x["target"]} for x in cases]
    return {
        "family": family, "fixture_sha256": fixture_sha,
        "execution_sha256": digest(files["execution.json"]), "execution": execution,
        "baseline_text": baseline, "oracle_text": oracle,
        "baseline_sha256": digest(files["baseline.txt"]), "oracle_sha256": digest(files["oracle.txt"]),
        "selected": cases, "selected_ids": [item["original_id"] for item in cases],
        "dataset_sha256": digest(_json_bytes(dataset_rows)),
        "source_sha256": source_pins, "screening": screening,
    }


def _validate_root(fixture_root: Path, families: list[dict[str, Any]]) -> None:
    root = _load_json(fixture_root / "fixture.json")
    pins, screening = families[0]["source_sha256"], families[0]["screening"]
    expected_families = [
        {"family": item["family"], "fixtureSha256": item["fixture_sha256"], "selectedIds": item["selected_ids"]}
        for item in families
    ]
    if (
        root.get("schema") != "hswm-inspect-oracle-diagnostic-root/v1"
        or root.get("sourceSha256") != pins
        or _screen(root.get("screening")) != screening
        or root.get("families") != expected_families
        or root.get("totalLogicalCases") != 32
        or root.get("totalModelCallMaximum") != 64
        or root.get("arms") != ["FROZEN_SINGLE_E1", "ORACLE_SINGLE_E1"]
        or root.get("modelCallsPerformed") is not False
    ):
        raise ValueError("root fixture contract mismatch")


def build(fixture_root: Path) -> dict[str, Any]:
    """Verify all source and fixture bytes before an execution can be attempted."""
    families = [family_plan(fixture_root, family) for family in FAMILIES]
    if any(item["execution"] != families[0]["execution"] for item in families):
        raise ValueError("execution configuration differs across families")
    if any(
        item["source_sha256"] != families[0]["source_sha256"] or item["screening"] != families[0]["screening"]
        for item in families
    ):
        raise ValueError("family evidence contracts differ")
    _validate_root(fixture_root, families)
    return {
        "schema": "hswm-oracle-single-diagnostic/v1", "cohort": COHORT,
        "evidence_kind": "PLANNED_SINGLE_E1_DIAGNOSTIC_NOT_EFFICACY",
        "families": families, "frozen_execution": families[0]["execution"],
        "planned_attempts": 64, "screening": families[0]["screening"],
    }


def _sample_rows(log: Any, cases: list[dict[str, Any]], arm: str) -> list[dict[str, Any]]:
    samples = getattr(log, "samples", None)
    expected_ids = {case["id"] for case in cases}
    if not isinstance(samples, list) or len(samples) != len(cases):
        raise RuntimeError(f"{arm}: Inspect log has missing or extra samples")
    by_id = {case["id"]: case for case in cases}
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for sample in samples:
        identifier = str(getattr(sample, "id", ""))
        if identifier not in expected_ids or identifier in seen:
            raise RuntimeError(f"{arm}: Inspect log has foreign or duplicate sample ID")
        seen.add(identifier)
        metadata = getattr(getattr(sample, "output", None), "metadata", None)
        bridge = metadata.get("hswm_bridge") if isinstance(metadata, dict) else None
        if not isinstance(bridge, dict) or not isinstance(bridge.get("valid"), bool):
            raise RuntimeError(f"{arm}: Inspect log lacks a bridge result")
        answer = bridge.get("answer")
        if bridge["valid"] and answer not in ("0", "1"):
            raise RuntimeError(f"{arm}: valid bridge result has no binary answer")
        if not bridge["valid"] and answer is not None:
            raise RuntimeError(f"{arm}: invalid bridge result carries an answer")
        case = by_id[identifier]
        rows.append({
            "id": identifier, "arm": arm, "answer": answer, "valid": bridge["valid"],
            "error_kind": bridge.get("error_kind"), "environment_target": case["target"],
            "frozen_rule_expected": case["frozen_rule_expected"],
            "environment_correct": bool(bridge["valid"] and answer == case["target"]),
            "frozen_rule_consistent": bool(bridge["valid"] and answer == case["frozen_rule_expected"]),
            "request_sha256": bridge.get("request_sha256"), "response_sha256": bridge.get("response_sha256"),
            "usage": bridge.get("usage"), "latency_ms": bridge.get("latency_ms"),
            "model_calls": bridge.get("model_calls"), "model_calls_upper_bound": bridge.get("model_calls_upper_bound", 1),
        })
    if seen != expected_ids:
        raise RuntimeError(f"{arm}: Inspect log omitted selected IDs")
    return rows


def _arm_summary(rows: list[dict[str, Any]], metric: str) -> dict[str, Any]:
    known_calls = [x["model_calls"] for x in rows if isinstance(x["model_calls"], int) and not isinstance(x["model_calls"], bool)]
    latencies = [x["latency_ms"] for x in rows if isinstance(x["latency_ms"], (int, float)) and not isinstance(x["latency_ms"], bool)]
    tokens = [
        x["usage"]["total_tokens"] for x in rows
        if isinstance(x["usage"], dict) and isinstance(x["usage"].get("total_tokens"), int)
        and not isinstance(x["usage"]["total_tokens"], bool)
    ]
    return {
        "correct": sum(row[metric] for row in rows), "total": len(rows),
        "valid": sum(row["valid"] for row in rows), "invalid": sum(not row["valid"] for row in rows),
        "known_model_calls": sum(known_calls), "unknown_call_attempts": len(rows) - len(known_calls),
        "model_call_upper_bound": sum(x["model_calls_upper_bound"] if isinstance(x["model_calls_upper_bound"], int) else 1 for x in rows),
        "known_total_tokens": sum(tokens), "unknown_token_rows": len(rows) - len(tokens),
        "known_latency_ms": sum(latencies), "unknown_latency_rows": len(rows) - len(latencies), "rows": rows,
    }


def summarize(baseline_log: Any, oracle_log: Any, cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "baseline": _arm_summary(_sample_rows(baseline_log, cases, "FROZEN_SINGLE_E1"), "frozen_rule_consistent"),
        "oracle": _arm_summary(_sample_rows(oracle_log, cases, "ORACLE_SINGLE_E1"), "environment_correct"),
    }


def _make_examples(cases: Iterable[dict[str, Any]]) -> list[LiveExample]:
    return [LiveExample(case["id"], "train", case["input"], case["target"]) for case in cases]


def run(plan: dict[str, Any], output: Path, base_url: str, model: str) -> dict[str, Any]:
    """Run only in-memory verified plan data; fixture paths are never reread."""
    if output.exists():
        raise ValueError("output directory must not already exist")
    _nonblank(base_url, "base_url")
    _nonblank(model, "model")
    output.mkdir(mode=0o700)
    frozen = plan["frozen_execution"]
    actual = Execution(base_url, model, frozen["max_tokens"], frozen["timeout_seconds"], frozen["seed"])
    _write_new(output / "started.json", {
        "plan_sha256": digest(_json_bytes(plan)), "cohort": COHORT, "planned_attempts": 64,
        "actual_execution": actual.as_dict(), "evidence_kind": plan["evidence_kind"],
    })
    completed: list[dict[str, Any]] = []
    for item in plan["families"]:
        family = item["family"]
        try:
            baseline_log, oracle_log = run_live(
                _make_examples(item["selected"]), item["baseline_text"], item["oracle_text"], actual,
                output / f"family-{family}", dataset_sha256=item["dataset_sha256"],
            )
            receipt = {"family": family, **summarize(baseline_log, oracle_log, item["selected"]),
                       "fixture_sha256": item["fixture_sha256"]}
            _write_new(output / f"family-{family}.json", receipt)
            completed.append(receipt)
        except Exception as error:
            attempted = len(completed) * 16
            _write_new(output / "failed.json", {
                "status": "INCOMPLETE", "family": family, "error": str(error), "planned_attempts": 64,
                "completed_family_attempts": attempted, "current_family_attempts": "UNKNOWN_UP_TO_16",
                "remaining_unattempted": 64 - attempted - 16,
                "completed_families": [item["family"] for item in completed],
                "decision": "INCOMPLETE_NO_SCREEN_DECISION",
            })
            raise
    baseline_rows = [row for receipt in completed for row in receipt["baseline"]["rows"]]
    oracle_rows = [row for receipt in completed for row in receipt["oracle"]["rows"]]
    all_rows = baseline_rows + oracle_rows
    screen = plan["screening"]
    passed = (
        sum(row["environment_correct"] for row in oracle_rows) >= screen["oracleCorrectAtLeast"]
        and sum(row["frozen_rule_consistent"] for row in baseline_rows) >= screen["frozenRuleConsistencyAtLeast"]
        and all(receipt["oracle"]["correct"] >= screen["eachFamilyOracleCorrectAtLeast"] for receipt in completed)
        and all(row["valid"] for row in all_rows)
    )
    summary = {
        "status": "COMPLETE", "results": completed, "planned_attempts": 64, "all_valid": sum(row["valid"] for row in all_rows),
        "oracle_environment_correct": sum(row["environment_correct"] for row in oracle_rows),
        "baseline_frozen_rule_consistent": sum(row["frozen_rule_consistent"] for row in baseline_rows),
        "baseline_environment_correct": sum(row["environment_correct"] for row in baseline_rows),
        "screen_passed": passed, "decision": screen["decisionPass"] if passed else screen["decisionFail"],
        "no_efficacy_or_population_claim": True,
    }
    _write_new(output / "summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "verify", "run"))
    parser.add_argument("fixture_root", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--base-url")
    parser.add_argument("--model")
    args = parser.parse_args()
    plan = build(args.fixture_root)
    if args.command in ("plan", "verify"):
        _write_new(args.out, plan)
    else:
        if not args.base_url or not args.model:
            raise ValueError("run requires --base-url and --model")
        run(plan, args.out, args.base_url, args.model)


if __name__ == "__main__":
    main()
