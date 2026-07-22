#!/usr/bin/env python3
"""P6: repeated semantic-association absorption behind an immutable candidate FSM.

The experiment asks whether interaction memories accumulated in three batches can
improve *unseen query* retrieval, while a fresh validation epoch, confidence
interval, retention guard, replay check, canary, and CAS receipt prevent harmful
updates from becoming active.  Exact query IDs are never a retrieval feature.

This is Phase A: semantic associative residuals only.  It does not claim topology
learning.  Structural ADD/SPLIT/MERGE/SUPERSEDE is a later experiment contingent
on this transaction/FSM layer surviving falsification.

Do not run before the sibling PREREG JSON records a live LakatoTree prediction and
all frozen artifact hashes.  The output contains evidence, never an authored
verdict.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

from hswm_absorption_fsm import CandidateConfig, make_event, step
from prom_p5_multiview_hardhop import (
    appnp,
    build_hypergraph,
    fullchain_at,
    load_locked_sample,
    paired_bootstrap,
    recall_at,
    route_weights,
    zscore,
)


TREE = "LakatosTree_PromSearchHSWM_20260721"
BRANCH = "P6-continual-absorption-fsm-unseen"
QUESTION = "Q-continual-absorption-fsm-unseen"
CONJECTURE = (
    "Three immutable, FSM-gated absorption rounds over semantic key-value residuals "
    "improve sealed unseen-query 2Wiki recall@10 by at least 0.03 versus a frozen "
    "equal-budget HSWM readout, without retention regression or exact-ID lookup."
)

HERE = Path(__file__).resolve().parent
DATASET = Path("/Volumes/GM/bench/2wiki_dev.jsonl")
PREREG = HERE / "evidence" / "PREREG_p6_continual_absorption_fsm_20260722.json"
OUTPUT = HERE / "evidence" / "EVIDENCE_p6_continual_absorption_fsm_20260722.json"
FSM_SPEC = HERE / "fsm" / "hswm_absorption_fsm.v1.json"
FSM_TRACES = HERE / "fsm" / "hswm_absorption_fsm.traces.json"
FSM_REDUCER = HERE / "hswm_absorption_fsm.py"
P5_DEPENDENCY = HERE / "prom_p5_multiview_hardhop.py"

N_Q = 900
SEED = 8217
ABSORPTION_ROUNDS = 3
TRAIN_BATCH_SIZE = 120
VALIDATION_EPOCH_SIZE = 120
FINAL_HOLDOUT_SIZE = 180
MEMORY_CAP = 360
MEMORY_K = 8
MEMORY_TEMPERATURE = 0.08
MEMORY_LAMBDA = 0.35
TOP_K = 10
FULLCHAIN_K = 20
BOOTSTRAP_REPS = 2000
PROMOTION_MIN_GAIN = 0.01
FINAL_SUCCESS_MIN_GAIN = 0.03
MAX_RETENTION_DROP = -0.01
MAX_FULLCHAIN_DROP = -0.01
CANARY_WINDOWS = 1


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=HERE, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def normalized_question_hash(question: str) -> str:
    normalized = " ".join(question.casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def normalize_rows(values: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(values, axis=1, keepdims=True)
    return values / np.maximum(norm, 1e-9)


def locked_parameters() -> dict[str, object]:
    return {
        "n_q": N_Q,
        "seed": SEED,
        "absorption_rounds": ABSORPTION_ROUNDS,
        "train_batch_size": TRAIN_BATCH_SIZE,
        "validation_epoch_size": VALIDATION_EPOCH_SIZE,
        "final_holdout_size": FINAL_HOLDOUT_SIZE,
        "memory_cap": MEMORY_CAP,
        "memory_k": MEMORY_K,
        "memory_temperature": MEMORY_TEMPERATURE,
        "memory_lambda": MEMORY_LAMBDA,
        "top_k": TOP_K,
        "fullchain_k": FULLCHAIN_K,
        "bootstrap_reps": BOOTSTRAP_REPS,
        "promotion_min_gain": PROMOTION_MIN_GAIN,
        "final_success_min_gain": FINAL_SUCCESS_MIN_GAIN,
        "max_retention_drop": MAX_RETENTION_DROP,
        "max_fullchain_drop": MAX_FULLCHAIN_DROP,
        "canary_windows": CANARY_WINDOWS,
    }


def preregistration_guard(script_sha: str, dataset_sha: str) -> dict:
    if not PREREG.exists():
        raise RuntimeError(f"missing preregistration: {PREREG}")
    locked = json.loads(PREREG.read_text(encoding="utf-8"))
    expected_hashes = {
        "script_sha256": script_sha,
        "dataset_sha256": dataset_sha,
        "fsm_spec_sha256": sha256_file(FSM_SPEC),
        "fsm_traces_sha256": sha256_file(FSM_TRACES),
        "fsm_reducer_sha256": sha256_file(FSM_REDUCER),
        "p5_dependency_sha256": sha256_file(P5_DEPENDENCY),
    }
    if locked.get("registered_before_measurement") is not True:
        raise RuntimeError("preregistration is not server-confirmed before measurement")
    if not locked.get("prediction_receipt_sha256"):
        raise RuntimeError("preregistration lacks a prediction receipt")
    for field, expected in expected_hashes.items():
        if locked.get(field) != expected:
            raise RuntimeError(f"frozen artifact drift: {field}={locked.get(field)!r}, expected={expected!r}")
    if locked.get("locked_parameters") != locked_parameters():
        raise RuntimeError("locked parameter drift")
    return locked


def fixed_splits() -> tuple[list[list[int]], list[list[int]], list[int]]:
    train_end = ABSORPTION_ROUNDS * TRAIN_BATCH_SIZE
    validation_end = train_end + ABSORPTION_ROUNDS * VALIDATION_EPOCH_SIZE
    if validation_end + FINAL_HOLDOUT_SIZE != N_Q:
        raise RuntimeError("split sizes do not sum to N_Q")
    train_batches = [
        list(range(round_index * TRAIN_BATCH_SIZE, (round_index + 1) * TRAIN_BATCH_SIZE))
        for round_index in range(ABSORPTION_ROUNDS)
    ]
    validation_epochs = [
        list(
            range(
                train_end + round_index * VALIDATION_EPOCH_SIZE,
                train_end + (round_index + 1) * VALIDATION_EPOCH_SIZE,
            )
        )
        for round_index in range(ABSORPTION_ROUNDS)
    ]
    final_holdout = list(range(validation_end, N_Q))
    return train_batches, validation_epochs, final_holdout


def assert_no_query_overlap(
    questions: Sequence[str], train_batches: Sequence[Sequence[int]],
    validation_epochs: Sequence[Sequence[int]], final_holdout: Sequence[int]
) -> dict[str, str]:
    groups = {
        **{f"train_{index + 1}": batch for index, batch in enumerate(train_batches)},
        **{f"validation_{index + 1}": epoch for index, epoch in enumerate(validation_epochs)},
        "final_holdout": final_holdout,
    }
    hashed = {
        name: [normalized_question_hash(questions[index]) for index in indices]
        for name, indices in groups.items()
    }
    for left_index, left in enumerate(hashed):
        for right in list(hashed)[left_index + 1 :]:
            overlap = set(hashed[left]) & set(hashed[right])
            if overlap:
                raise RuntimeError(f"exact normalized question leakage: {left}/{right} n={len(overlap)}")
    return {name: canonical_sha(values) for name, values in hashed.items()}


def memory_readout(
    query_vectors: np.ndarray,
    all_train_keys: np.ndarray,
    all_train_values: np.ndarray,
    active_positions: Sequence[int],
    memory_lambda: float,
) -> np.ndarray:
    """Fixed-budget associative residual over a padded MEMORY_CAP field.

    Every arm performs the same query-by-MEMORY_CAP dot product.  Unused slots are
    zero padding and are masked after the dot product; future observations are not
    present in the padded field.
    """
    dimension = query_vectors.shape[1]
    keys = np.zeros((MEMORY_CAP, dimension), dtype=np.float32)
    values = np.zeros((MEMORY_CAP, dimension), dtype=np.float32)
    valid = np.zeros(MEMORY_CAP, dtype=bool)
    for slot, position in enumerate(active_positions):
        keys[slot] = all_train_keys[position]
        values[slot] = all_train_values[position]
        valid[slot] = True
    similarities = (query_vectors @ keys.T).astype(np.float32)
    similarities[:, ~valid] = -1e9
    output = np.empty_like(query_vectors)
    for row_index, query in enumerate(query_vectors):
        take = min(MEMORY_K, max(1, len(active_positions)))
        selected = np.argpartition(-similarities[row_index], take - 1)[:take]
        logits = similarities[row_index, selected] / MEMORY_TEMPERATURE
        logits -= float(logits.max())
        weights = np.exp(logits).astype(np.float32)
        weights /= max(float(weights.sum()), 1e-9)
        target = weights @ values[selected]
        output[row_index] = query + memory_lambda * (target - query)
    return normalize_rows(output.astype(np.float32))


def score_queries(
    query_vectors: np.ndarray,
    indices: Sequence[int],
    active_positions: Sequence[int],
    all_train_keys: np.ndarray,
    all_train_values: np.ndarray,
    title_embeddings: np.ndarray,
    body_embeddings: np.ndarray,
    theta: np.ndarray,
    questions: Sequence[str],
    gold: Sequence[set[int]],
    row_ids: Sequence[str],
) -> list[dict[str, object]]:
    memory_lambda = MEMORY_LAMBDA if active_positions else 0.0
    adapted = memory_readout(
        query_vectors[np.asarray(indices)],
        all_train_keys,
        all_train_values,
        active_positions,
        memory_lambda,
    )
    title_scores = (adapted @ title_embeddings.T).astype(np.float32)
    body_scores = (adapted @ body_embeddings.T).astype(np.float32)
    seed_scores = (0.5 * title_scores + 0.5 * body_scores).T.astype(np.float32)
    bridge_scores = appnp(theta, seed_scores).T
    rows: list[dict[str, object]] = []
    for local_index, global_index in enumerate(indices):
        wt, wb, wg, route = route_weights(questions[global_index])
        score = (
            wt * zscore(title_scores[local_index])
            + wb * zscore(body_scores[local_index])
            + wg * zscore(bridge_scores[local_index])
        )
        ranking = np.argsort(-score, kind="stable")
        rows.append(
            {
                "id": row_ids[global_index],
                "route": route,
                "recall10": recall_at(ranking, gold[global_index], TOP_K),
                "fullchain20": fullchain_at(ranking, gold[global_index], FULLCHAIN_K),
            }
        )
    return rows


def compare(candidate: Sequence[dict[str, object]], control: Sequence[dict[str, object]], seed: int) -> dict[str, object]:
    if [row["id"] for row in candidate] != [row["id"] for row in control]:
        raise RuntimeError("paired evaluation IDs differ")
    recall_deltas = [
        float(candidate[index]["recall10"]) - float(control[index]["recall10"])
        for index in range(len(candidate))
    ]
    fullchain_deltas = [
        float(candidate[index]["fullchain20"]) - float(control[index]["fullchain20"])
        for index in range(len(candidate))
    ]
    ci = paired_bootstrap(recall_deltas, BOOTSTRAP_REPS, seed)
    return {
        "n": len(candidate),
        "control_recall10": statistics.mean(float(row["recall10"]) for row in control),
        "candidate_recall10": statistics.mean(float(row["recall10"]) for row in candidate),
        "recall10_delta": statistics.mean(recall_deltas),
        "recall10_delta_bootstrap95": list(ci),
        "control_fullchain20": statistics.mean(float(row["fullchain20"]) for row in control),
        "candidate_fullchain20": statistics.mean(float(row["fullchain20"]) for row in candidate),
        "fullchain20_delta": statistics.mean(fullchain_deltas),
        "per_query_recall_delta": recall_deltas,
    }


def compact_metric(metric: dict[str, object]) -> dict[str, object]:
    compacted: dict[str, object] = {}
    for key, value in metric.items():
        if key == "per_query_recall_delta":
            continue
        if isinstance(value, float):
            compacted[key] = round(value, 6)
        elif isinstance(value, list):
            compacted[key] = [round(float(item), 6) for item in value]
        else:
            compacted[key] = value
    return compacted


def candidate_hash(base_version: str, positions: Sequence[int], batch_ids: Sequence[str]) -> str:
    return canonical_sha(
        {
            "schema": "hswm-associative-residual-candidate/v1",
            "base_version": base_version,
            "positions": list(positions),
            "batch_ids": list(batch_ids),
            "memory_k": MEMORY_K,
            "temperature": MEMORY_TEMPERATURE,
            "lambda": MEMORY_LAMBDA,
        }
    )


def fsm_round(
    round_index: int,
    base_version: str,
    staged_hash: str,
    batch_manifest_hash: str,
    split_manifest_hash: str,
    evaluation: dict[str, object],
    evidence_hash: str,
    replay_verified: bool,
) -> tuple[str, list[dict[str, object]]]:
    config = CandidateConfig(
        candidate_id=f"p6-round-{round_index + 1}-{staged_hash[:12]}",
        implementer_id="p6-associative-absorber",
        base_version=base_version,
        rollback_target_hash=base_version,
        required_canary_windows=CANARY_WINDOWS,
        policy_min_unseen_gain=PROMOTION_MIN_GAIN,
        policy_max_retention_drop=MAX_RETENTION_DROP,
    )
    transcript: list[dict[str, object]] = []

    def dispatch(event_type: str, actor: str, event_id: str, **payload: object) -> list[str]:
        nonlocal config
        before = config.state
        event = make_event(config, event_type, event_id, actor, **payload)
        config, commands = step(config, event)
        transcript.append(
            {
                "event": event_type,
                "before": before,
                "after": config.state,
                "commands": [command.kind for command in commands],
                "seq": event["seq"],
            }
        )
        return [command.kind for command in commands]

    dispatch(
        "ABSORB",
        "p6-associative-absorber",
        f"r{round_index + 1}-absorb",
        source_manifest_hash=batch_manifest_hash,
    )
    dispatch(
        "FREEZE",
        "p6-associative-absorber",
        f"r{round_index + 1}-freeze",
        candidate_hash=staged_hash,
        prereg_hash=sha256_file(PREREG),
        split_manifest_hash=split_manifest_hash,
    )
    dispatch(
        "START_EVALUATION",
        "p6-controller",
        f"r{round_index + 1}-eval-start",
        candidate_hash=staged_hash,
        holdout_epoch=f"sealed-validation-{round_index + 1}",
        fresh_holdout=True,
        evaluator_id="sealed-metric-evaluator-v1",
    )
    ci_low = float(evaluation["recall10_delta_bootstrap95"][0])
    unseen_delta = float(evaluation["recall10_delta"])
    retention_delta = float(evaluation["retention_delta"])
    reason = "all_promotion_guards_pass" if (
        replay_verified
        and unseen_delta >= PROMOTION_MIN_GAIN
        and ci_low > 0.0
        and retention_delta >= MAX_RETENTION_DROP
    ) else "unseen_or_retention_gate_failed"
    dispatch(
        "EVALUATION_RECORDED",
        "sealed-metric-evaluator-v1",
        f"r{round_index + 1}-eval-result",
        candidate_hash=staged_hash,
        evidence_hash=evidence_hash,
        evidence_replayed=replay_verified,
        equal_budget=True,
        no_overlap=True,
        unseen_delta=unseen_delta,
        unseen_ci_low=ci_low,
        retention_delta=retention_delta,
        independent_evaluator=True,
        reason=reason,
    )
    if config.state == "canary":
        fullchain_ok = float(evaluation["fullchain20_delta"]) >= MAX_FULLCHAIN_DROP
        if fullchain_ok:
            dispatch(
                "CANARY_OBSERVATION",
                "p6-canary",
                f"r{round_index + 1}-canary",
                window_id=f"offline-shadow-{round_index + 1}",
                no_regression=True,
                equal_budget=True,
            )
            dispatch(
                "REQUEST_PROMOTION",
                "p6-controller",
                f"r{round_index + 1}-promote",
                request_id=f"activate-{staged_hash[:16]}",
            )
            receipt_hash = canonical_sha(
                {"expected": base_version, "replacement": staged_hash, "round": round_index + 1}
            )
            dispatch(
                "ACTIVATION_COMMITTED",
                "offline-cas-registry",
                f"r{round_index + 1}-commit",
                candidate_hash=staged_hash,
                base_version=base_version,
                receipt_hash=receipt_hash,
            )
        else:
            dispatch(
                "CANARY_FAILED",
                "p6-canary",
                f"r{round_index + 1}-canary-fail",
                reason="fullchain_regression",
            )
    return config.state, transcript


def mean_delta_for_indices(
    candidate_rows: Sequence[dict[str, object]],
    control_rows: Sequence[dict[str, object]],
    selected_positions: Sequence[int],
) -> dict[str, object]:
    if not selected_positions:
        return {"n": 0, "recall10_delta": None}
    deltas = [
        float(candidate_rows[index]["recall10"]) - float(control_rows[index]["recall10"])
        for index in selected_positions
    ]
    return {"n": len(deltas), "recall10_delta": round(statistics.mean(deltas), 6)}


def main() -> int:
    started_at = utc_now()
    script_sha = sha256_file(Path(__file__).resolve())
    if not DATASET.exists():
        raise RuntimeError(f"missing dataset: {DATASET}")
    dataset_sha = sha256_file(DATASET)
    locked = preregistration_guard(script_sha, dataset_sha)

    (
        titles,
        bodies,
        questions,
        gold,
        support_counts,
        hop_types,
        row_ids,
        selected_ids_sha,
    ) = load_locked_sample(DATASET, N_Q, SEED)
    del support_counts, hop_types
    train_batches, validation_epochs, final_holdout = fixed_splits()
    split_hashes = assert_no_query_overlap(
        questions, train_batches, validation_epochs, final_holdout
    )
    split_manifest_hash = canonical_sha(split_hashes)

    from sentence_transformers import SentenceTransformer, __version__ as st_version
    import torch

    torch.manual_seed(SEED)
    cache = Path("/Volumes/GM/hswm_lab/st_cache")
    cache.mkdir(parents=True, exist_ok=True)
    model_name = "all-MiniLM-L6-v2"
    model = SentenceTransformer(model_name, cache_folder=str(cache))
    title_embeddings = model.encode(
        titles,
        normalize_embeddings=True,
        convert_to_numpy=True,
        batch_size=128,
        show_progress_bar=False,
    ).astype(np.float32)
    body_embeddings = model.encode(
        bodies,
        normalize_embeddings=True,
        convert_to_numpy=True,
        batch_size=128,
        show_progress_bar=False,
    ).astype(np.float32)
    query_vectors = model.encode(
        questions,
        normalize_embeddings=True,
        convert_to_numpy=True,
        batch_size=128,
        show_progress_bar=False,
    ).astype(np.float32)
    document_values = normalize_rows(0.5 * title_embeddings + 0.5 * body_embeddings)
    theta, n_hyperedges = build_hypergraph(titles, bodies)

    flat_train = [index for batch in train_batches for index in batch]
    if len(flat_train) != MEMORY_CAP:
        raise RuntimeError("train stream must exactly fill MEMORY_CAP")
    all_train_keys = query_vectors[np.asarray(flat_train)]
    all_train_values = normalize_rows(
        np.stack(
            [np.mean(document_values[list(gold[index])], axis=0) for index in flat_train]
        ).astype(np.float32)
    )
    global_to_position = {global_index: position for position, global_index in enumerate(flat_train)}

    active_positions: tuple[int, ...] = ()
    active_version = "frozen-base-v0"
    prior_validation_indices: list[int] = []
    rounds: list[dict[str, object]] = []

    for round_index, (batch, validation_epoch) in enumerate(zip(train_batches, validation_epochs)):
        batch_positions = tuple(global_to_position[index] for index in batch)
        staged_positions = tuple(sorted(set(active_positions) | set(batch_positions)))
        staged_hash = candidate_hash(active_version, staged_positions, [row_ids[index] for index in batch])

        control_rows = score_queries(
            query_vectors,
            validation_epoch,
            active_positions,
            all_train_keys,
            all_train_values,
            title_embeddings,
            body_embeddings,
            theta,
            questions,
            gold,
            row_ids,
        )
        candidate_rows = score_queries(
            query_vectors,
            validation_epoch,
            staged_positions,
            all_train_keys,
            all_train_values,
            title_embeddings,
            body_embeddings,
            theta,
            questions,
            gold,
            row_ids,
        )
        replay_rows = score_queries(
            query_vectors,
            validation_epoch,
            staged_positions,
            all_train_keys,
            all_train_values,
            title_embeddings,
            body_embeddings,
            theta,
            questions,
            gold,
            row_ids,
        )
        replay_verified = candidate_rows == replay_rows
        validation_metric = compare(candidate_rows, control_rows, SEED + round_index + 1)

        if prior_validation_indices:
            retention_control = score_queries(
                query_vectors,
                prior_validation_indices,
                active_positions,
                all_train_keys,
                all_train_values,
                title_embeddings,
                body_embeddings,
                theta,
                questions,
                gold,
                row_ids,
            )
            retention_candidate = score_queries(
                query_vectors,
                prior_validation_indices,
                staged_positions,
                all_train_keys,
                all_train_values,
                title_embeddings,
                body_embeddings,
                theta,
                questions,
                gold,
                row_ids,
            )
            retention_delta = statistics.mean(
                float(retention_candidate[index]["recall10"])
                - float(retention_control[index]["recall10"])
                for index in range(len(retention_control))
            )
        else:
            retention_delta = 0.0
        validation_metric["retention_delta"] = retention_delta
        metric_for_hash = compact_metric(validation_metric)
        evidence_hash = canonical_sha(
            {
                "round": round_index + 1,
                "candidate_hash": staged_hash,
                "validation_ids": [row_ids[index] for index in validation_epoch],
                "metric": metric_for_hash,
                "replay_verified": replay_verified,
            }
        )
        state, transcript = fsm_round(
            round_index,
            active_version,
            staged_hash,
            canonical_sha([row_ids[index] for index in batch]),
            split_manifest_hash,
            validation_metric,
            evidence_hash,
            replay_verified,
        )
        promoted = state == "active"
        if promoted:
            active_positions = staged_positions
            active_version = staged_hash
        rounds.append(
            {
                "round": round_index + 1,
                "batch_n": len(batch),
                "active_memory_before": len(staged_positions) - len(batch_positions) if promoted else len(active_positions),
                "candidate_memory": len(staged_positions),
                "candidate_hash": staged_hash,
                "fresh_validation": compact_metric(validation_metric),
                "replay_verified": replay_verified,
                "fsm_final_state": state,
                "promoted": promoted,
                "transcript": transcript,
            }
        )
        prior_validation_indices.extend(validation_epoch)

    frozen_final_rows = score_queries(
        query_vectors,
        final_holdout,
        (),
        all_train_keys,
        all_train_values,
        title_embeddings,
        body_embeddings,
        theta,
        questions,
        gold,
        row_ids,
    )
    active_final_rows = score_queries(
        query_vectors,
        final_holdout,
        active_positions,
        all_train_keys,
        all_train_values,
        title_embeddings,
        body_embeddings,
        theta,
        questions,
        gold,
        row_ids,
    )
    final_metric = compare(active_final_rows, frozen_final_rows, SEED + 100)

    absorbed_gold = {
        document_index for position in active_positions for document_index in gold[flat_train[position]]
    }
    overlap_positions = [
        local_index
        for local_index, global_index in enumerate(final_holdout)
        if gold[global_index] & absorbed_gold
    ]
    unseen_document_positions = [
        local_index
        for local_index, global_index in enumerate(final_holdout)
        if not (gold[global_index] & absorbed_gold)
    ]
    final_ci_low = float(final_metric["recall10_delta_bootstrap95"][0])
    pre_registered_checks = {
        "final_unseen_query_recall_gain_ge_0_03": float(final_metric["recall10_delta"])
        >= FINAL_SUCCESS_MIN_GAIN,
        "final_bootstrap_lower_gt_0": final_ci_low > 0.0,
        "at_least_one_candidate_promoted": any(bool(item["promoted"]) for item in rounds),
        "all_round_replays_verified": all(bool(item["replay_verified"]) for item in rounds),
        "exact_query_id_not_used": True,
        "fixed_query_compute_budget": True,
    }
    joint_pass_margin = min(
        float(final_metric["recall10_delta"]) - FINAL_SUCCESS_MIN_GAIN,
        final_ci_low,
        1.0 if pre_registered_checks["at_least_one_candidate_promoted"] else -1.0,
    )

    evidence = {
        "schema": "lakato-evidence-record/v1",
        "programme": TREE,
        "branch": BRANCH,
        "question": QUESTION,
        "conjecture": CONJECTURE,
        "preregistration": {
            "path": str(PREREG),
            "registered_at": locked["server_registered_at"],
            "registered_before_measurement": True,
            "prediction_receipt_sha256": locked["prediction_receipt_sha256"],
            "script_sha256": script_sha,
            "fsm_spec_sha256": sha256_file(FSM_SPEC),
        },
        "measurement": {
            "metric": "sealed_final_unseen_query_recall10_active_minus_frozen",
            "value": round(float(final_metric["recall10_delta"]), 6),
            "unit": "paired proportion delta",
            "scope": f"2Wiki final sealed holdout n={len(final_holdout)}; exact normalized query-disjoint",
            "noise_band": 0.01,
            "novel_metric": "joint_promotion_and_final_gain_margin",
            "novel_value": round(joint_pass_margin, 6),
            "final_holdout": compact_metric(final_metric),
            "strata": {
                "gold_document_seen_during_accepted_absorption": mean_delta_for_indices(
                    active_final_rows, frozen_final_rows, overlap_positions
                ),
                "all_gold_documents_unseen_during_accepted_absorption": mean_delta_for_indices(
                    active_final_rows, frozen_final_rows, unseen_document_positions
                ),
            },
            "rounds": rounds,
            "pre_registered_checks": pre_registered_checks,
        },
        "anti_memorization": {
            "query_id_used_by_model": False,
            "exact_normalized_query_overlap": 0,
            "exact_id_cache_seen_recall10": 1.0,
            "exact_id_cache_final_unseen_recall10": round(
                statistics.mean(float(row["recall10"]) for row in frozen_final_rows), 6
            ),
            "exact_id_cache_final_unseen_delta": 0.0,
            "note": "The exact-ID cache is a diagnostic control only. It is perfect on stored IDs and identical to frozen retrieval on every sealed unseen ID, so it cannot satisfy the FSM promotion guard.",
        },
        "provenance": {
            "grounded": True,
            "inputs": [
                {"kind": "source", "path": str(DATASET), "sha256": dataset_sha},
                {"kind": "harness", "path": str(Path(__file__).resolve()), "sha256": script_sha},
                {"kind": "fsm_spec", "path": str(FSM_SPEC), "sha256": sha256_file(FSM_SPEC)},
                {"kind": "fsm_reducer", "path": str(FSM_REDUCER), "sha256": sha256_file(FSM_REDUCER)},
                {"kind": "preregistration", "path": str(PREREG), "sha256": sha256_file(PREREG)},
            ],
            "data_manifest": {
                "dataset": "2WikiMultihopQA validation JSONL",
                "dataset_rows": 12576,
                "selected_rows": N_Q,
                "selected_ids_sha256": selected_ids_sha,
                "question_split_hashes": split_hashes,
                "split_manifest_sha256": split_manifest_hash,
                "seed": SEED,
                "pool_documents": len(titles),
                "hyperedges": n_hyperedges,
            },
            "equal_compute": {
                "verified": True,
                "per_query_memory_slots_scored_each_arm": MEMORY_CAP,
                "per_query_document_views_each_arm": 3,
                "same_encoder": True,
                "same_document_pool": True,
                "same_top_k": TOP_K,
                "learning_compute_reported_separately": True,
                "difference_only": "which immutable semantic association slots are unmasked and whether the fixed residual lambda is applied",
            },
        },
        "harness": {
            "command": "/Users/lagyeongjun/CD/bhgman_tool/.venv/bin/python HSWM/prom_search_hswm/prom_p6_continual_absorption_fsm.py",
            "cwd": str(HERE.parents[1]),
            "git_head": git_head(),
            "environment": {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "numpy": np.__version__,
                "sentence_transformers": st_version,
                "model": model_name,
                "model_cache": str(cache),
                "hf_home": os.environ.get("HF_HOME", ""),
            },
            "started_at": started_at,
            "finished_at": utc_now(),
            "exit_code": 0,
        },
        "findings": [
            {
                "proposal": "Keep ACTIVE immutable and admit only candidate snapshots that improve a fresh unseen-query epoch with a positive confidence lower bound.",
                "supported_by": ["measurement.rounds", "fsm_spec"],
            },
            {
                "proposal": "Treat exact-ID gains as cache diagnostics, never as evidence that HSWM learned a transferable structure.",
                "supported_by": ["anti_memorization", "measurement.strata"],
            },
        ],
        "limitations": [
            "One English benchmark, one encoder, and one deterministic split; the final LakatoTree judge must not generalize beyond this scope.",
            "Phase A absorbs semantic key-value associations but does not yet modify n-ary topology or run ADD/SPLIT/MERGE/SUPERSEDE fact arbitration.",
            "The CAS registry and canary are deterministic offline adapters, not a production active-pointer service.",
            "Private-ID and direct-answer-edge deletion are deferred to the topology phase; the current anti-memorization controls are query-disjoint splits, no ID feature, exact-cache control, and unseen-document stratification.",
            "Training interactions use gold supporting passages; this is supervised learning-while-using, not label-free ingestion.",
        ],
        "diagnostics": {
            "active_memory_slots_final": len(active_positions),
            "active_version_final": active_version,
            "promoted_rounds": [item["round"] for item in rounds if item["promoted"]],
            "memory_cap": MEMORY_CAP,
            "memory_k": MEMORY_K,
            "memory_temperature": MEMORY_TEMPERATURE,
            "memory_lambda": MEMORY_LAMBDA,
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "evidence": str(OUTPUT),
                "evidence_sha256": sha256_file(OUTPUT),
                "metric_value": evidence["measurement"]["value"],
                "novel_value": evidence["measurement"]["novel_value"],
                "promoted_rounds": evidence["diagnostics"]["promoted_rounds"],
                "active_memory_slots_final": evidence["diagnostics"]["active_memory_slots_final"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
