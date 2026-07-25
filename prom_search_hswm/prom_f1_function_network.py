#!/usr/bin/env python3
"""Run and judge the PROM-9 F1 matched-budget function-network experiment.

The ``run`` command never opens gold.  The ``judge`` command takes a separate
gold file and first revalidates every model-call and item-run receipt.  A
development run can exercise the entire pipeline but can never emit a sealed
scientific support verdict.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import random
import re
from collections.abc import Mapping, Sequence

from prom_search_hswm.hswm_call_receipt import OpenAICompatibleJSONPort
from prom_search_hswm.hswm_function_network import (
    EvidenceCandidateV1,
    F1_ARMS,
    FLAT_ARM,
    FunctionNetworkItemV1,
    REMOVAL_ARM,
    SHUFFLE_ARM,
    TYPED_ARM,
    VECTOR_ARM,
    run_item,
    verify_run,
)
from prom_search_hswm.hswm_function_registry import build_registry
from prom_search_hswm.hswm_typed_ports import canonical_sha256
from prom_search_hswm.prom9_protocol import DEFAULT_PROTOCOL


MANIFEST_SCHEMA = "hswm-prom9-f1-manifest/v1"
SUITE_SCHEMA = "hswm-prom9-f1-suite/v1"
GOLD_SCHEMA = "hswm-prom9-f1-gold/v1"
JUDGMENT_SCHEMA = "hswm-prom9-f1-judgment/v1"
_SHA = re.compile(r"^[0-9a-f]{64}$")


class F1HarnessError(RuntimeError):
    pass


def _read_json(path: Path, label: str) -> dict[str, object]:
    def pairs(values: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in values:
            if key in result:
                raise F1HarnessError(f"duplicate key in {label}: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=pairs)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise F1HarnessError(f"cannot read {label}: {error}") from error
    if not isinstance(value, dict):
        raise F1HarnessError(f"{label} must be an object")
    return value


def _write_once(path: Path, value: Mapping[str, object]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as error:
        raise F1HarnessError(f"refusing to replace output: {path}") from error
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _keys(value: Mapping[str, object], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise F1HarnessError(
            f"{label} keys drifted: missing={sorted(expected-set(value))}, "
            f"extra={sorted(set(value)-expected)}"
        )


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise F1HarnessError(f"{label} must be non-empty text")
    return value


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise F1HarnessError(f"{label} must be positive")
    return value


def _sha(value: object, label: str) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise F1HarnessError(f"{label} must be a lowercase SHA-256")
    return value


def _arm_overrides(arm_id: str) -> dict[str, str]:
    output_contract = {
        "QF_QUERY_COMPILER": (
            'Return JSON only with exactly: request_id string; objectives array of unique strings; '
            'required_evidence_types array of unique strings; constraints array of unique strings; '
            'abstain boolean. Preserve request_id exactly.'
        ),
        "BF_BOND_PROPOSER": (
            'Return JSON only with exactly: request_id string; ordered_bond_ids array of unique '
            'supplied strings; bond_potentials object exactly covering ordered_bond_ids with finite '
            'numbers <= 0; evidence_refs array of unique supplied evidence-ID strings; abstain boolean. '
            'Preserve request_id exactly.'
        ),
        "AF_ANSWER_SYNTHESIZER": (
            'Return JSON only with exactly: request_id string; answer string containing only the '
            'shortest answer span, or an empty string when abstaining; '
            'supporting_evidence_ids array of unique supplied strings; uncertainty string; '
            'abstain boolean. Preserve request_id exactly.'
        ),
    }
    guard = " Never inspect gold/outcome labels, mutate persistent state, or judge the experiment. "
    if arm_id == TYPED_ARM:
        return {}
    if arm_id == FLAT_ARM:
        return {
            "QF_QUERY_COMPILER": "Generic flat workflow planning pass. Preserve request_id." + guard + output_contract["QF_QUERY_COMPILER"],
            "BF_BOND_PROPOSER": "Generic flat-context selection pass. Use only flat_position, flat_score, and source_type. Preserve request_id." + guard + output_contract["BF_BOND_PROPOSER"],
            "AF_ANSWER_SYNTHESIZER": "Generic flat workflow answering pass. Answer only from selected_evidence. Preserve request_id." + guard + output_contract["AF_ANSWER_SYNTHESIZER"],
        }
    if arm_id == VECTOR_ARM:
        return {
            "QF_QUERY_COMPILER": "Generic vector-memory query planning pass. Preserve request_id." + guard + output_contract["QF_QUERY_COMPILER"],
            "BF_BOND_PROPOSER": "Vector-memory selection pass. Rank only by supplied vector_score and source_type. Preserve request_id." + guard + output_contract["BF_BOND_PROPOSER"],
            "AF_ANSWER_SYNTHESIZER": "Vector-memory answering pass. Answer only from selected_evidence. Preserve request_id." + guard + output_contract["AF_ANSWER_SYNTHESIZER"],
        }
    if arm_id == REMOVAL_ARM:
        return {
            "BF_BOND_PROPOSER": (
                "Schema-preserving null BF control. Make this physical call but select no bonds. "
                "Copy request_id; ordered_bond_ids=[], bond_potentials={}, evidence_refs=[], "
                "abstain=true." + guard + output_contract["BF_BOND_PROPOSER"]
            )
        }
    if arm_id == SHUFFLE_ARM:
        return {
            "QF_QUERY_COMPILER": "Use the answer-synthesizer role instruction, but this port has no evidence and must remain a QueryPlanV1. Preserve request_id." + guard + output_contract["QF_QUERY_COMPILER"],
            "BF_BOND_PROPOSER": "Use the query-compiler role instruction on the supplied candidate table while preserving the BondProposalV1 port. Preserve request_id." + guard + output_contract["BF_BOND_PROPOSER"],
            "AF_ANSWER_SYNTHESIZER": "Use the bond-proposer role instruction, but preserve the AnswerEnvelopeV1 port and cite only supplied evidence. Preserve request_id." + guard + output_contract["AF_ANSWER_SYNTHESIZER"],
        }
    raise F1HarnessError(f"unknown arm: {arm_id}")


def validate_manifest(value: Mapping[str, object]) -> dict[str, object]:
    _keys(
        value,
        {
            "schema_version", "run_id", "mode", "model", "model_revision",
            "token_tolerance", "state_capacity_bytes", "state_bytes_by_arm",
            "preregistration_receipt_sha256", "items",
        },
        "F1 manifest",
    )
    if value.get("schema_version") != MANIFEST_SCHEMA:
        raise F1HarnessError("unsupported F1 manifest schema")
    mode = value.get("mode")
    if mode not in {"development", "sealed"}:
        raise F1HarnessError("manifest mode must be development or sealed")
    prereg = value.get("preregistration_receipt_sha256")
    if mode == "sealed":
        _sha(prereg, "sealed preregistration receipt")
    elif prereg is not None:
        _sha(prereg, "development preregistration receipt")
    tolerance = value.get("token_tolerance")
    state_capacity = value.get("state_capacity_bytes")
    if isinstance(tolerance, bool) or not isinstance(tolerance, int) or tolerance < 0:
        raise F1HarnessError("token_tolerance must be non-negative")
    if isinstance(state_capacity, bool) or not isinstance(state_capacity, int) or state_capacity < 0:
        raise F1HarnessError("state_capacity_bytes must be non-negative")
    state_rows = value.get("state_bytes_by_arm")
    if not isinstance(state_rows, dict) or set(state_rows) != set(F1_ARMS):
        raise F1HarnessError("state_bytes_by_arm must exactly cover F1 arms")
    for arm, raw in state_rows.items():
        if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0 or raw > state_capacity:
            raise F1HarnessError(f"invalid or over-cap state bytes for {arm}")
    raw_items = value.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise F1HarnessError("manifest items must be non-empty")
    seen: set[str] = set()
    for index, raw in enumerate(raw_items):
        if not isinstance(raw, dict):
            raise F1HarnessError(f"item {index} must be an object")
        _keys(
            raw,
            {
                "item_id", "query_text", "allowed_evidence_types", "candidates",
                "max_evidence_items", "max_input_tokens", "max_output_tokens_per_call",
            },
            f"item {index}",
        )
        item_id = _text(raw["item_id"], f"item {index} id")
        if item_id in seen:
            raise F1HarnessError(f"duplicate item_id: {item_id}")
        seen.add(item_id)
    _text(value.get("run_id"), "run_id")
    _text(value.get("model"), "model")
    _text(value.get("model_revision"), "model_revision")
    return json.loads(json.dumps(value, ensure_ascii=False))


def _item(raw: Mapping[str, object]) -> FunctionNetworkItemV1:
    candidates = []
    for index, candidate in enumerate(raw["candidates"]):
        if not isinstance(candidate, dict):
            raise F1HarnessError(f"candidate {index} must be an object")
        _keys(candidate, {"bond_id", "evidence_id", "content", "observable"}, f"candidate {index}")
        if not isinstance(candidate["observable"], dict):
            raise F1HarnessError(f"candidate {index} observable must be an object")
        candidates.append(
            EvidenceCandidateV1(
                bond_id=_text(candidate["bond_id"], "bond_id"),
                evidence_id=_text(candidate["evidence_id"], "evidence_id"),
                content=_text(candidate["content"], "candidate content"),
                observable=dict(candidate["observable"]),
            )
        )
    evidence_types = raw["allowed_evidence_types"]
    if not isinstance(evidence_types, list) or not evidence_types:
        raise F1HarnessError("allowed_evidence_types must be non-empty")
    return FunctionNetworkItemV1(
        item_id=str(raw["item_id"]),
        query_text=_text(raw["query_text"], "query_text"),
        allowed_evidence_types=tuple(_text(item, "evidence type") for item in evidence_types),
        candidates=tuple(candidates),
        max_evidence_items=_positive_int(raw["max_evidence_items"], "max_evidence_items"),
        max_input_tokens=_positive_int(raw["max_input_tokens"], "max_input_tokens"),
        max_output_tokens_per_call=_positive_int(raw["max_output_tokens_per_call"], "max_output_tokens_per_call"),
    )


def run_suite(
    manifest: Mapping[str, object],
    *,
    protocol_path: Path,
    model_port,
    max_workers: int = 1,
) -> dict[str, object]:
    normalized = validate_manifest(manifest)
    if isinstance(max_workers, bool) or not isinstance(max_workers, int) or not 1 <= max_workers <= 8:
        raise F1HarnessError("max_workers must be in [1, 8]")
    registries = {
        arm: build_registry(
            protocol_path,
            model=str(normalized["model"]),
            model_revision=str(normalized["model_revision"]),
            prompt_overrides=_arm_overrides(arm),
        )
        for arm in F1_ARMS
    }
    jobs = [(_item(raw), arm) for raw in normalized["items"] for arm in F1_ARMS]

    def execute(job):
        item, arm = job
        return run_item(
            run_id=str(normalized["run_id"]),
            arm_id=arm,
            item=item,
            registry=registries[arm],
            model_port=model_port,
            persistent_state_bytes=int(normalized["state_bytes_by_arm"][arm]),
        ).canonical()

    if max_workers == 1:
        rows = [execute(job) for job in jobs]
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            rows = list(executor.map(execute, jobs))
    unsigned = {
        "schema_version": SUITE_SCHEMA,
        "run_id": normalized["run_id"],
        "mode": normalized["mode"],
        "manifest_sha256": canonical_sha256(normalized),
        "model": normalized["model"],
        "model_revision": normalized["model_revision"],
        "token_tolerance": normalized["token_tolerance"],
        "state_capacity_bytes": normalized["state_capacity_bytes"],
        "preregistration_receipt_sha256": normalized["preregistration_receipt_sha256"],
        "max_workers": max_workers,
        "registries": {arm: registries[arm].canonical() for arm in F1_ARMS},
        "item_runs": rows,
        "gold_opened": False,
        "scientific_verdict_emitted": False,
    }
    return {**unsigned, "suite_receipt_sha256": canonical_sha256(unsigned)}


def verify_suite(value: Mapping[str, object]) -> str:
    data = dict(value)
    if data.get("schema_version") != SUITE_SCHEMA:
        raise F1HarnessError("unsupported F1 suite schema")
    declared = data.pop("suite_receipt_sha256", None)
    if not isinstance(declared, str) or canonical_sha256(data) != declared:
        raise F1HarnessError("F1 suite self-hash drifted")
    if data.get("gold_opened") is not False or data.get("scientific_verdict_emitted") is not False:
        raise F1HarnessError("F1 run phase crossed evaluator authority")
    registries = data.get("registries")
    if not isinstance(registries, dict) or set(registries) != set(F1_ARMS):
        raise F1HarnessError("F1 suite registries must exactly cover every arm")
    registry_functions: dict[str, dict[str, Mapping[str, object]]] = {}
    for arm, raw_registry in registries.items():
        if not isinstance(raw_registry, dict):
            raise F1HarnessError(f"invalid registry for {arm}")
        unsigned_registry = dict(raw_registry)
        registry_sha = unsigned_registry.pop("registry_sha256", None)
        if not isinstance(registry_sha, str) or canonical_sha256(unsigned_registry) != registry_sha:
            raise F1HarnessError(f"registry hash drifted for {arm}")
        functions = raw_registry.get("functions")
        if not isinstance(functions, list) or len(functions) != 3:
            raise F1HarnessError(f"registry for {arm} must contain three functions")
        indexed_functions: dict[str, Mapping[str, object]] = {}
        for function in functions:
            if not isinstance(function, dict):
                raise F1HarnessError(f"invalid registry function for {arm}")
            function_id = str(function.get("function_id"))
            if function.get("prompt_sha256") != canonical_sha256({"prompt": function.get("prompt")}):
                raise F1HarnessError(f"prompt hash drifted for {arm}/{function_id}")
            indexed_functions[function_id] = function
        if set(indexed_functions) != {
            "QF_QUERY_COMPILER", "BF_BOND_PROPOSER", "AF_ANSWER_SYNTHESIZER"
        }:
            raise F1HarnessError(f"function set drifted for {arm}")
        registry_functions[arm] = indexed_functions
    rows = data.get("item_runs")
    if not isinstance(rows, list) or not rows:
        raise F1HarnessError("F1 suite has no item runs")
    for row in rows:
        if not isinstance(row, dict):
            raise F1HarnessError("invalid F1 item run")
        verify_run(row)
        arm = str(row.get("arm_id"))
        if arm not in registries or row.get("registry_sha256") != registries[arm].get("registry_sha256"):
            raise F1HarnessError("item run is not bound to its arm registry")
        for call in row["calls"]:
            function = registry_functions[arm].get(str(call.get("function_id")))
            if function is None or call.get("prompt_sha256") != function.get("prompt_sha256"):
                raise F1HarnessError("call prompt is not bound to the arm registry")
    return declared


def _normalize_answer(value: str) -> str:
    return " ".join(value.casefold().strip().split())


def _bootstrap(values: list[float], *, reps: int, seed: int) -> list[float]:
    if not values:
        raise F1HarnessError("cannot bootstrap an empty comparison")
    generator = random.Random(seed)
    means = []
    for _ in range(reps):
        means.append(sum(values[generator.randrange(len(values))] for _ in values) / len(values))
    means.sort()
    return [means[int(0.025 * (reps - 1))], means[int(0.975 * (reps - 1))]]


def judge_suite(
    suite: Mapping[str, object],
    gold: Mapping[str, object],
    *,
    bootstrap_reps: int = 10000,
    bootstrap_seed: int = 20260724,
) -> dict[str, object]:
    suite_sha = verify_suite(suite)
    _keys(gold, {"schema_version", "run_id", "evaluator_receipt_sha256", "items"}, "F1 gold")
    if gold.get("schema_version") != GOLD_SCHEMA or gold.get("run_id") != suite.get("run_id"):
        raise F1HarnessError("gold identity does not match the F1 suite")
    evaluator_sha = _sha(gold.get("evaluator_receipt_sha256"), "evaluator receipt")
    gold_rows = gold.get("items")
    if not isinstance(gold_rows, list) or not gold_rows:
        raise F1HarnessError("gold items must be non-empty")
    answers: dict[str, set[str]] = {}
    for index, raw in enumerate(gold_rows):
        if not isinstance(raw, dict):
            raise F1HarnessError(f"gold item {index} must be an object")
        _keys(raw, {"item_id", "accepted_answers"}, f"gold item {index}")
        accepted = raw["accepted_answers"]
        if not isinstance(accepted, list) or not accepted or any(not isinstance(item, str) or not item.strip() for item in accepted):
            raise F1HarnessError(f"gold item {index} accepted answers are invalid")
        item_id = _text(raw["item_id"], f"gold item {index} id")
        if item_id in answers:
            raise F1HarnessError(f"duplicate gold item: {item_id}")
        answers[item_id] = {_normalize_answer(item) for item in accepted}

    indexed: dict[str, dict[str, Mapping[str, object]]] = {}
    for row in suite["item_runs"]:
        item_id = str(row["item_id"])
        arm = str(row["arm_id"])
        indexed.setdefault(item_id, {})[arm] = row
    if set(indexed) != set(answers):
        raise F1HarnessError("suite/gold item sets differ")
    token_tolerance = int(suite["token_tolerance"])
    parity_failures: list[str] = []
    scores = {arm: [] for arm in F1_ARMS}
    item_scores: list[dict[str, object]] = []
    for item_id in sorted(indexed):
        arms = indexed[item_id]
        if set(arms) != set(F1_ARMS):
            raise F1HarnessError(f"item {item_id} does not cover every F1 arm")
        universes = {str(row["candidate_universe_sha256"]) for row in arms.values()}
        models = {
            (str(call["model"]), str(call["model_revision"]))
            for row in arms.values() for call in row["calls"]
        }
        allowed = {int(row["total_allowed_output_tokens"]) for row in arms.values()}
        totals = [int(row["total_input_tokens"]) + int(row["total_output_tokens"]) for row in arms.values()]
        if len(universes) != 1:
            parity_failures.append(f"{item_id}:candidate-universe")
        if len(models) != 1:
            parity_failures.append(f"{item_id}:model")
        if len(allowed) != 1:
            parity_failures.append(f"{item_id}:allowed-output")
        if max(totals) - min(totals) > token_tolerance:
            parity_failures.append(f"{item_id}:consumed-token-spread={max(totals)-min(totals)}")
        row_scores: dict[str, float] = {}
        for arm in F1_ARMS:
            answer = arms[arm]["answer"]
            score = float(
                not bool(answer["abstain"])
                and _normalize_answer(str(answer["answer"])) in answers[item_id]
            )
            scores[arm].append(score)
            row_scores[arm] = score
        item_scores.append({"item_id": item_id, "scores": row_scores})
    metrics = {
        arm: {"success_rate": sum(values) / len(values), "n": len(values)}
        for arm, values in scores.items()
    }
    comparisons = {}
    for arm in (FLAT_ARM, VECTOR_ARM, REMOVAL_ARM, SHUFFLE_ARM):
        diffs = [left - right for left, right in zip(scores[TYPED_ARM], scores[arm])]
        comparisons[f"typed_minus_{arm}"] = {
            "mean": sum(diffs) / len(diffs),
            "bootstrap95": _bootstrap(diffs, reps=bootstrap_reps, seed=bootstrap_seed),
        }
    typed_flat = comparisons[f"typed_minus_{FLAT_ARM}"]
    gates = {
        "exact_three_calls_each": all(len(row["calls"]) == 3 for arms in indexed.values() for row in arms.values()),
        "equal_budget": not parity_failures,
        "typed_beats_flat_lcb_gt_0": typed_flat["bootstrap95"][0] > 0.0,
        "typed_beats_vector": comparisons[f"typed_minus_{VECTOR_ARM}"]["mean"] > 0.0,
        "removal_loses_effect": comparisons[f"typed_minus_{REMOVAL_ARM}"]["mean"] > 0.0,
        "shuffle_loses_effect": comparisons[f"typed_minus_{SHUFFLE_ARM}"]["mean"] > 0.0,
    }
    statistically_supported = all(gates.values())
    if suite["mode"] == "development":
        verdict = "DEVELOPMENT_ONLY"
        allowed_claim = "No scientific efficacy claim; use this result only to debug and freeze F1."
    elif statistically_supported:
        verdict = "F1_SUPPORTED_NARROW"
        allowed_claim = "On the registered sealed scope, typed composition beat matched flat/vector controls and lost its effect under role removal/shuffle."
    else:
        verdict = "REJECTED_OR_NARROWED"
        allowed_claim = "The sealed F1 result did not satisfy the complete topology-and-budget conjunction."
    unsigned = {
        "schema_version": JUDGMENT_SCHEMA,
        "run_id": suite["run_id"],
        "suite_receipt_sha256": suite_sha,
        "evaluator_receipt_sha256": evaluator_sha,
        "mode": suite["mode"],
        "bootstrap": {"reps": bootstrap_reps, "seed": bootstrap_seed, "paired": True},
        "metrics": metrics,
        "comparisons": comparisons,
        "gates": gates,
        "parity_failures": parity_failures,
        "item_scores": item_scores,
        "verdict": verdict,
        "allowed_claim": allowed_claim,
    }
    return {**unsigned, "judgment_sha256": canonical_sha256(unsigned)}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--manifest", type=Path, required=True)
    run_parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    run_parser.add_argument("--endpoint", required=True)
    run_parser.add_argument("--api-key-env")
    run_parser.add_argument("--timeout-seconds", type=float, default=180.0)
    run_parser.add_argument("--max-workers", type=int, default=1)
    run_parser.add_argument("--output", type=Path, required=True)
    judge_parser = subparsers.add_parser("judge")
    judge_parser.add_argument("--suite", type=Path, required=True)
    judge_parser.add_argument("--gold", type=Path, required=True)
    judge_parser.add_argument("--bootstrap-reps", type=int, default=10000)
    judge_parser.add_argument("--bootstrap-seed", type=int, default=20260724)
    judge_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            manifest = _read_json(args.manifest, "F1 manifest")
            port = OpenAICompatibleJSONPort(
                args.endpoint,
                api_key_env=args.api_key_env,
                timeout_seconds=args.timeout_seconds,
            )
            result = run_suite(
                manifest,
                protocol_path=args.protocol,
                model_port=port,
                max_workers=args.max_workers,
            )
        else:
            result = judge_suite(
                _read_json(args.suite, "F1 suite"),
                _read_json(args.gold, "F1 gold"),
                bootstrap_reps=args.bootstrap_reps,
                bootstrap_seed=args.bootstrap_seed,
            )
        _write_once(args.output, result)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except Exception as error:
        print(json.dumps({"status": "REFUSED", "reason": str(error)}, ensure_ascii=False), file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "F1HarnessError",
    "GOLD_SCHEMA",
    "JUDGMENT_SCHEMA",
    "MANIFEST_SCHEMA",
    "SUITE_SCHEMA",
    "judge_suite",
    "run_suite",
    "validate_manifest",
    "verify_suite",
]
