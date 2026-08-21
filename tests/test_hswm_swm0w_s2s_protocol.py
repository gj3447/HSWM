from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import math

import numpy as np
import pytest

from hswm.experiments import swm0w_s2s_protocol as protocol
from hswm.experiments.swm0w_s2s_family import (
    TaskBatchV2,
    _build_task,
    generate_task,
    generate_task_batch,
)
from hswm.experiments.swm0w_s2s_operator import (
    ALL_ARMS,
    ROLE_CYCLES,
    S2SArm,
    canonical_json,
    canonical_sha256,
    construct_task_bound_q_witness_v2,
    initialize_operator,
)
from hswm.experiments.swm0w_s2s_training import (
    S2STrainingConfig,
    fit_task_operator,
    replay_optimization,
)


def _digest(*parts: object) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode("ascii")).hexdigest()


@pytest.fixture(scope="module")
def fitted_bundle():
    task = generate_task(
        external_seed=hashlib.sha256(b"synthetic-s2s-protocol-fit").digest()
    )
    arm_configs = tuple(
        (
            arm,
            S2STrainingConfig(
                seed=0,
                max_updates=0,
                learning_rate=0.001,
                patience=1,
            ),
        )
        for arm in ALL_ARMS
    )
    config = protocol.build_protocol_config(
        arm_configs,
        excluded_task_provenance=((_digest("synthetic-public-pilot"), (0, 1, 2)),),
    )
    train = tuple(task.iter_cases("train"))
    dev = tuple(task.iter_cases("dev"))
    models = tuple(
        fit_task_operator(task, train, dev, arm=arm, config=training_config)
        for arm, training_config in arm_configs
    )
    replay_models = tuple(replay_optimization(model) for model in models)
    replays = tuple(
        protocol.build_fit_replay_receipt(model, replay)
        for model, replay in zip(models, replay_models, strict=True)
    )
    evaluation = protocol.evaluate_task(task, models, replays, config)
    return task, config, models, replays, evaluation


@pytest.fixture(scope="module")
def synthetic_batch():
    return generate_task_batch(
        external_seed=hashlib.sha256(b"synthetic-s2s-protocol-reducer").digest(),
        count=protocol.TASK_COUNT,
    )


def _metric(
    task,
    config,
    *,
    q: float,
    b: float,
    r: float,
    c: float,
    valid: bool = True,
) -> protocol.TaskMetricReceipt:
    archives = tuple(_digest("archive", task.draw_index, arm.value) for arm in ALL_ARMS)
    replays = tuple(_digest("replay", task.draw_index, arm.value) for arm in ALL_ARMS)
    scores = tuple(
        _digest("score", task.draw_index, variant.value)
        for variant in protocol.ScoreVariant
    )
    values = {
        "draw_index": task.draw_index,
        "task_manifest_sha256": task.manifest_sha256,
        "structural_task_sha256": task.structural_task_sha256,
        "protocol_config_sha256": config.receipt_sha256,
        "model_archive_sha256s": archives,
        "fit_replay_sha256s": replays,
        "score_receipt_sha256s": scores,
        "learned_q_receipt_sha256": _digest("Q", task.draw_index),
        "integrity_receipt_sha256": _digest("integrity", task.draw_index),
        "integrity_valid": valid,
        "q": q,
        "b": b,
        "r": r,
        "c": c,
    }
    unsigned = {
        "b_hex": b.hex(),
        "c_hex": c.hex(),
        "draw_index": task.draw_index,
        "fit_replay_sha256s": list(replays),
        "integrity_receipt_sha256": values["integrity_receipt_sha256"],
        "integrity_valid": valid,
        "learned_q_receipt_sha256": values["learned_q_receipt_sha256"],
        "model_archive_sha256s": list(archives),
        "protocol_config_sha256": config.receipt_sha256,
        "q_hex": q.hex(),
        "r_hex": r.hex(),
        "schema_version": protocol.TASK_METRIC_VERSION,
        "score_receipt_sha256s": list(scores),
        "structural_task_sha256": task.structural_task_sha256,
        "task_manifest_sha256": task.manifest_sha256,
    }
    return protocol.TaskMetricReceipt(
        **values, receipt_sha256=canonical_sha256(unsigned)
    )


def _metrics(batch, config, *, q=0.9, b=0.2, r=0.2, c=0.0):
    return tuple(
        _metric(task, config, q=q, b=b, r=r, c=c) for task in batch.tasks
    )


def _rehash(payload: dict[str, object]) -> dict[str, object]:
    result = copy.deepcopy(payload)
    result.pop("receipt_sha256", None)
    return {**result, "receipt_sha256": canonical_sha256(result)}


def _score_with_r2(score, values):
    raw = score.canonical()
    for row, requested in zip(raw["strata"], values, strict=True):
        denominator = float(
            row["centered_sum_squares_numerator"]
            / (
                row["sample_count"]
                * 2 ** (2 * protocol.TARGET_SCALE_EXPONENT)
            )
        )
        squared_error = (1.0 - requested) * denominator
        row["squared_error_hex"] = squared_error.hex()
        row["r2_hex"] = (1.0 - squared_error / denominator).hex()
    actual_values = tuple(float.fromhex(row["r2_hex"]) for row in raw["strata"])
    worst_r2, worst_role, worst_channel = min(
        (value, index // 2, index % 2)
        for index, value in enumerate(actual_values)
    )
    raw["worst_r2_hex"] = worst_r2.hex()
    raw["worst_role"] = worst_role
    raw["worst_channel"] = worst_channel
    return protocol.parse_six_stratum_score(_rehash(raw))


def _propagate_score_rehashes(raw, scores):
    parsed_scores = tuple(
        protocol.parse_six_stratum_score(score) for score in scores
    )
    q_value, b_value, r_value, c_value = protocol._metric_values(parsed_scores)
    metrics = raw["metrics"]
    metrics["score_receipt_sha256s"] = [
        score["receipt_sha256"] for score in scores
    ]
    metrics["q_hex"] = q_value.hex()
    metrics["b_hex"] = b_value.hex()
    metrics["r_hex"] = r_value.hex()
    metrics["c_hex"] = c_value.hex()
    raw["scores"] = scores
    raw["metrics"] = _rehash(metrics)
    return _rehash(raw)


def test_strict_family_training_and_config_parsers_round_trip(fitted_bundle):
    task, config, models, _, _ = fitted_bundle
    assert protocol.parse_task_spec_v2(task.canonical()) == task
    assert protocol.parse_training_config(models[0].config.canonical()) == models[0].config
    assert (
        protocol.parse_optimization_receipt(models[0].optimization.canonical())
        == models[0].optimization
    )
    assert protocol.parse_protocol_config(config.canonical()) == config
    assert tuple(arm for arm, _ in config.arm_configs) == ALL_ARMS
    assert all(row[1].learning_rate == 0.001 for row in config.arm_configs)


def test_task_batch_envelope_retains_all_indexed_draws_and_duplicates(synthetic_batch):
    archive = protocol.serialize_task_batch(synthetic_batch)
    assert protocol.parse_task_batch(archive) == synthetic_batch
    assert tuple(task.draw_index for task in synthetic_batch.tasks) == tuple(range(20))

    base = synthetic_batch.tasks[0]
    duplicate_tasks = tuple(
        _build_task(
            seed_commitment_sha256=base.seed_commitment_sha256,
            draw_index=index,
            rank_gains=base.rank_gains,
            split_coefficients=base.split_coefficients,
            split_residues=base.split_residues,
        )
        for index in range(20)
    )
    duplicates = tuple((index, 0) for index in range(1, 20))
    payload = {
        "duplicate_structural_target_draws": [list(row) for row in duplicates],
        "duplicate_structural_task_draws": [list(row) for row in duplicates],
        "requested_count": 20,
        "schema_version": "hswm-swm0w-s2s-task-batch/v2",
        "seed_commitment_sha256": base.seed_commitment_sha256,
        "task_manifest_sha256s": [task.manifest_sha256 for task in duplicate_tasks],
    }
    duplicated = TaskBatchV2(
        seed_commitment_sha256=base.seed_commitment_sha256,
        requested_count=20,
        tasks=duplicate_tasks,
        duplicate_structural_target_draws=duplicates,
        duplicate_structural_task_draws=duplicates,
        batch_sha256=canonical_sha256(payload),
    )
    assert protocol.parse_task_batch(protocol.serialize_task_batch(duplicated)) == duplicated
    assert len(duplicated.duplicate_structural_task_draws) == 19


def test_canonical_json_loader_rejects_duplicates_nonfinite_and_aliases(fitted_bundle):
    task = fitted_bundle[0]
    encoded = canonical_json(task.canonical())
    assert protocol.loads_canonical_json(encoded) == task.canonical()
    with pytest.raises(protocol.SWM0WS2SProtocolError):
        protocol.loads_canonical_json('{"a":1,"a":2}')
    with pytest.raises(protocol.SWM0WS2SProtocolError):
        protocol.loads_canonical_json('{"a":NaN}')
    with pytest.raises(protocol.SWM0WS2SProtocolError):
        protocol.loads_canonical_json('{"a":-0.0}')
    with pytest.raises(protocol.SWM0WS2SProtocolError):
        protocol.loads_canonical_json(" " + encoded)


def test_exact_type_parsers_reject_bool_int_and_python_subclasses(fitted_bundle):
    task = fitted_bundle[0]
    raw = task.canonical()
    raw["draw_index"] = True
    with pytest.raises(protocol.SWM0WS2SProtocolError):
        protocol.parse_task_spec_v2(raw)

    class IntAlias(int):
        pass

    raw = task.canonical()
    raw["draw_index"] = IntAlias(0)
    with pytest.raises(protocol.SWM0WS2SProtocolError):
        protocol.parse_task_spec_v2(raw)

    class DictAlias(dict):
        pass

    with pytest.raises(protocol.SWM0WS2SProtocolError):
        protocol.parse_task_spec_v2(DictAlias(task.canonical()))


def test_task_and_optimization_hash_tamper_fail_closed(fitted_bundle):
    task, _, models, _, _ = fitted_bundle
    raw_task = task.canonical()
    raw_task["manifest_sha256"] = "0" * 64
    with pytest.raises(protocol.SWM0WS2SProtocolError):
        protocol.parse_task_spec_v2(raw_task)

    raw_optimization = models[0].optimization.canonical()
    raw_optimization["task_spec"] = copy.deepcopy(raw_optimization["task_spec"])
    raw_optimization["task_spec"]["draw_index"] = True
    with pytest.raises(protocol.SWM0WS2SProtocolError):
        protocol.parse_optimization_receipt(raw_optimization)


def test_learned_parameter_archive_is_exact_and_bit_sensitive(fitted_bundle):
    _, _, models, _, _ = fitted_bundle
    archive = protocol.archive_learned_model(models[0])
    parsed = protocol.parse_learned_model_archive(archive.canonical())
    assert parsed.model().state_sha256 == models[0].state_sha256
    assert parsed.model().parameters_sha256 == models[0].parameters_sha256

    reordered = archive.canonical()
    reordered["tensors"] = list(reversed(reordered["tensors"]))
    with pytest.raises(protocol.SWM0WS2SProtocolError):
        protocol.parse_learned_model_archive(reordered)

    one_ulp = archive.canonical()
    tensor = one_ulp["tensors"][0]
    value = float.fromhex(tensor["values_hex"][0])
    tensor["values_hex"][0] = math.nextafter(value, math.inf).hex()
    with pytest.raises(protocol.SWM0WS2SProtocolError):
        protocol.parse_learned_model_archive(one_ulp)

    signed_zero = archive.canonical()
    location = next(
        (tensor, index)
        for tensor in signed_zero["tensors"]
        for index, value_hex in enumerate(tensor["values_hex"])
        if value_hex == "0x0.0p+0"
    )
    location[0]["values_hex"][location[1]] = "-0x0.0p+0"
    with pytest.raises(protocol.SWM0WS2SProtocolError):
        protocol.parse_learned_model_archive(signed_zero)

    nonfinite = archive.canonical()
    nonfinite["tensors"][0]["values_hex"][0] = "nan"
    with pytest.raises(protocol.SWM0WS2SProtocolError):
        protocol.parse_learned_model_archive(nonfinite)


def test_epoch_zero_fit_replay_marker_is_valid_and_deeply_bound(fitted_bundle):
    task, _, models, replays, _ = fitted_bundle
    assert all(model.optimization.best_update == 0 for model in models)
    assert all(replay.parameter_bytes_equal for replay in replays)
    assert all(replay.optimization_canonical_equal for replay in replays)
    assert all(replay.state_equal for replay in replays)
    assert all(
        protocol.parse_fit_replay_receipt(replay.canonical()) == replay
        for replay in replays
    )
    crossed = replays[0].canonical()
    crossed["task_manifest_sha256"] = task.structural_task_sha256
    crossed = _rehash(crossed)
    parsed = protocol.parse_fit_replay_receipt(crossed)
    with pytest.raises(protocol.SWM0WS2SProtocolError):
        protocol.evaluate_task(task, models, (parsed, *replays[1:]), fitted_bundle[1])


def test_complete_evaluation_binds_all_scores_cycles_and_restoration(fitted_bundle):
    task, _, models, _, evaluation = fitted_bundle
    assert evaluation.task == task
    assert evaluation.integrity.valid
    assert evaluation.integrity.errors == ()
    assert tuple(score.variant for score in evaluation.scores) == tuple(
        protocol.ScoreVariant
    )
    assert ROLE_CYCLES == ((1, 2, 0), (2, 0, 1))
    assert all(score.world_count == 6_250 for score in evaluation.scores)
    assert all(
        row.sample_count == 12_500
        for score in evaluation.scores
        for row in score.strata
    )
    base = evaluation.scores[0]
    restored = evaluation.scores[4]
    broadcast = evaluation.scores[5]
    assert restored.prediction_tensor_sha256 == base.prediction_tensor_sha256
    assert restored.strata == base.strata
    assert broadcast.source_prediction_tensor_sha256 == base.prediction_tensor_sha256
    observed_metrics = (
        evaluation.metrics.q,
        evaluation.metrics.b,
        evaluation.metrics.r,
        evaluation.metrics.c,
    )
    assert observed_metrics == (
        0.0,
        0.0,
        0.0,
        0.0,
    )
    assert protocol.parse_task_evaluation_receipt(evaluation.canonical()) == evaluation
    raw_operator = initialize_operator(S2SArm.T16, seed=0)
    with pytest.raises(protocol.SWM0WS2SProtocolError):
        protocol.evaluate_task(
            task,
            (raw_operator, models[1], models[2]),
            fitted_bundle[3],
            fitted_bundle[1],
        )
    witness = construct_task_bound_q_witness_v2(task)
    with pytest.raises(protocol.SWM0WS2SProtocolError):
        protocol.evaluate_task(
            task,
            (witness, models[1], models[2]),
            fitted_bundle[3],
            fitted_bundle[1],
        )


def test_evaluation_parser_replays_learned_q_against_archived_t16(fitted_bundle):
    evaluation = fitted_bundle[4]
    raw = evaluation.canonical()
    learned_q = raw["learned_q_intervention"]
    learned_q["learned_parameters_sha256"] = "f" * 64
    learned_q["restored_parameters_sha256"] = "f" * 64
    learned_q = _rehash(learned_q)
    raw["learned_q_intervention"] = learned_q

    q_variants = {
        protocol.ScoreVariant.T16_Q_REMOVED.value,
        protocol.ScoreVariant.T16_RESTORED.value,
        protocol.ScoreVariant.T16_CYCLE_120.value,
        protocol.ScoreVariant.T16_CYCLE_201.value,
    }
    scores = []
    for score in raw["scores"]:
        if score["variant"] in q_variants:
            score["source_receipt_sha256"] = learned_q["receipt_sha256"]
            score = _rehash(score)
        scores.append(score)
    metrics = raw["metrics"]
    metrics["learned_q_receipt_sha256"] = learned_q["receipt_sha256"]
    metrics["score_receipt_sha256s"] = [
        score["receipt_sha256"] for score in scores
    ]
    raw["scores"] = scores
    raw["metrics"] = _rehash(metrics)

    with pytest.raises(protocol.SWM0WS2SProtocolError):
        protocol.parse_task_evaluation_receipt(_rehash(raw))


def test_evaluation_parser_recomputes_test_dataset_and_targets(fitted_bundle):
    raw = fitted_bundle[4].canonical()
    scores = []
    for score in raw["scores"]:
        score["test_dataset_sha256"] = "f" * 64
        score["target_tensor_sha256"] = "e" * 64
        scores.append(_rehash(score))

    with pytest.raises(protocol.SWM0WS2SProtocolError):
        protocol.parse_task_evaluation_receipt(
            _propagate_score_rehashes(raw, scores)
        )


@pytest.mark.parametrize("forgery", ("prediction", "strata"))
def test_evaluation_parser_recomputes_predictions_and_strata(
    fitted_bundle, forgery
):
    evaluation = fitted_bundle[4]
    raw = evaluation.canonical()
    scores = list(raw["scores"])
    if forgery == "prediction":
        scores[2]["prediction_tensor_sha256"] = "f" * 64
        scores[2] = _rehash(scores[2])
    else:
        changed = _score_with_r2(
            evaluation.scores[2],
            (-0.25, 0.0, 0.0, 0.0, 0.0, 0.0),
        )
        scores[2] = changed.canonical()

    with pytest.raises(protocol.SWM0WS2SProtocolError):
        protocol.parse_task_evaluation_receipt(
            _propagate_score_rehashes(raw, scores)
        )


@pytest.mark.parametrize("forgery", ("structural_audit", "model_symmetry"))
def test_evaluation_parser_recomputes_integrity_audit(fitted_bundle, forgery):
    raw = fitted_bundle[4].canonical()
    integrity = raw["integrity"]
    if forgery == "structural_audit":
        integrity["structural_audit_sha256"] = "f" * 64
    else:
        integrity["model_symmetry"][0]["max_abs_error_hex"] = (2.0**-20).hex()
    raw["integrity"] = _rehash(integrity)
    metrics = raw["metrics"]
    metrics["integrity_receipt_sha256"] = raw["integrity"]["receipt_sha256"]
    raw["metrics"] = _rehash(metrics)

    with pytest.raises(protocol.SWM0WS2SProtocolError):
        protocol.parse_task_evaluation_receipt(_rehash(raw))


def test_task_metric_formulas_are_paired_minima_not_global_shortcuts(fitted_bundle):
    evaluation = fitted_bundle[4]
    scores = list(evaluation.scores)
    base = (0.5, 0.75, 0.75, 0.75, 0.75, 0.75)
    scores[0] = _score_with_r2(scores[0], base)
    scores[2] = _score_with_r2(
        scores[2], (0.625, 0.25, 0.625, 0.625, 0.625, 0.625)
    )
    scores[5] = _score_with_r2(
        scores[5], (0.0, 0.625, 0.625, 0.625, 0.625, 0.625)
    )
    scores[6] = _score_with_r2(
        scores[6], (0.0, 0.625, 0.625, 0.625, 0.625, 0.625)
    )
    scores[7] = _score_with_r2(
        scores[7], (0.25, 0.5, 0.5, 0.5, 0.5, 0.5)
    )
    q_value, b_value, r_value, c_value = protocol._metric_values(tuple(scores))
    score_map = {score.variant: score for score in scores}
    actual_base = score_map[protocol.ScoreVariant.T16_BASE].strata
    actual_broadcast = score_map[protocol.ScoreVariant.T16_BROADCAST].strata
    actual_ds = score_map[protocol.ScoreVariant.DS870_BASE].strata
    actual_cycles = (
        score_map[protocol.ScoreVariant.T16_CYCLE_120].strata,
        score_map[protocol.ScoreVariant.T16_CYCLE_201].strata,
    )
    assert q_value == min(row.r2 for row in actual_base)
    assert b_value == min(
        left.r2 - right.r2
        for left, right in zip(actual_base, actual_broadcast, strict=True)
    )
    assert r_value == min(
        left.r2 - right.r2
        for cycle in actual_cycles
        for left, right in zip(actual_base, cycle, strict=True)
    )
    assert c_value == min(row.r2 for row in actual_base) - min(
        row.r2 for row in actual_ds
    )
    assert b_value == pytest.approx(0.125)
    assert r_value == pytest.approx(0.125)
    assert c_value == pytest.approx(0.25)
    assert b_value != min(row.r2 for row in actual_base) - min(
        row.r2 for row in actual_broadcast
    )
    assert c_value != min(
        left.r2 - right.r2
        for left, right in zip(
            actual_base, actual_ds, strict=True
        )
    )


def test_score_parser_and_evaluation_reject_cross_score_and_subsets(fitted_bundle):
    task, _, models, _, evaluation = fitted_bundle
    for score in evaluation.scores:
        assert protocol.parse_six_stratum_score(score.canonical()) == score
    base_prediction = models[0].forward(
        protocol._complete_test_data(task)[1]
    )
    with pytest.raises(protocol.SWM0WS2SProtocolError):
        protocol.score_complete_test_predictions(
            task,
            models[0],
            evaluated_state_sha256=models[0].as_unlabeled_operator().state_sha256,
            source_receipt_sha256=evaluation.archives[0].receipt_sha256,
            variant=protocol.ScoreVariant.T16_BASE,
            predictions=base_prediction[:-1],
        )

    scores = list(evaluation.scores)
    raw_broadcast = scores[5].canonical()
    raw_broadcast["source_prediction_tensor_sha256"] = "f" * 64
    scores[5] = protocol.parse_six_stratum_score(_rehash(raw_broadcast))
    with pytest.raises(protocol.SWM0WS2SProtocolError):
        replace(evaluation, scores=tuple(scores))


def test_q_intervention_rejects_cross_model_and_receipt_tamper(fitted_bundle):
    _, _, models, _, evaluation = fitted_bundle
    receipt = protocol.parse_learned_q_intervention(evaluation.learned_q.canonical())
    ablated, same_receipt = protocol.remove_learned_q(models[0])
    assert same_receipt == receipt
    restored = protocol.restore_learned_q(models[0], ablated, receipt)
    assert restored.parameters_sha256 == models[0].parameters_sha256
    with pytest.raises(protocol.SWM0WS2SProtocolError):
        protocol.restore_learned_q(models[1], ablated, receipt)
    raw = receipt.canonical()
    raw["learned_state_sha256"] = models[1].state_sha256
    with pytest.raises(protocol.SWM0WS2SProtocolError):
        protocol.parse_learned_q_intervention(raw)


def test_null_epsilon_is_inclusive_and_one_ulp_above_cannot_claim_valid(fitted_bundle):
    integrity = fitted_bundle[4].integrity
    raw = integrity.canonical()
    raw["pcap_max_r2_hex"] = protocol.PAIR_NULL_EPSILON.hex()
    exact = protocol.parse_integrity_receipt(_rehash(raw))
    assert exact.valid

    raw = integrity.canonical()
    raw["pcap_max_r2_hex"] = math.nextafter(
        protocol.PAIR_NULL_EPSILON, math.inf
    ).hex()
    with pytest.raises(protocol.SWM0WS2SProtocolError):
        protocol.parse_integrity_receipt(_rehash(raw))


def test_shared_bootstrap_and_candidate_pass_kill_inconclusive_void(
    fitted_bundle, synthetic_batch
):
    config = fitted_bundle[1]
    first = protocol.shared_task_bootstrap_indices()
    second = protocol.shared_task_bootstrap_indices()
    assert np.array_equal(first, second)
    assert not first.flags.writeable
    assert protocol._bootstrap_sha256(first) == (
        "1e184b1d4dfd9d4a41496646574180f86195ff4372f3b637de0d37190c143845"
    )

    exact_gate = _metrics(synthetic_batch, config, q=0.8, b=0.1, r=0.1, c=-0.02)
    passed = protocol.finalize_candidate(synthetic_batch, exact_gate, config)
    assert passed.outcome is protocol.CandidateOutcome.CANDIDATE_PASS_AWAITING_BUNDLE
    assert passed.compact_competitive_phrase_candidate
    assert protocol.parse_final_candidate_receipt(passed.canonical()) == passed

    killed = protocol.finalize_candidate(
        synthetic_batch,
        _metrics(synthetic_batch, config, q=0.799, b=0.2, r=0.2),
        config,
    )
    assert killed.outcome is protocol.CandidateOutcome.CANDIDATE_KILL_AWAITING_BUNDLE
    assert killed.reason_codes == ("Q_UCB_BELOW_GATE",)

    q_values = (0.7, 0.7) + (0.8,) * 18
    crossing = tuple(
        _metric(task, config, q=q_values[index], b=0.2, r=0.2, c=0.0)
        for index, task in enumerate(synthetic_batch.tasks)
    )
    inconclusive = protocol.finalize_candidate(synthetic_batch, crossing, config)
    assert (
        inconclusive.outcome
        is protocol.CandidateOutcome.CANDIDATE_INCONCLUSIVE_AWAITING_BUNDLE
    )
    assert dict(inconclusive.estimates)["Q"].upper == 0.8

    voided = protocol.finalize_candidate(
        synthetic_batch, exact_gate, config, integrity_errors=("TIMEOUT",)
    )
    assert voided.outcome is protocol.CandidateOutcome.VOID
    assert voided.estimates == ()
    assert voided.bootstrap_indices_sha256 is None
    partial = protocol.finalize_candidate(synthetic_batch, exact_gate[:-1], config)
    assert partial.outcome is protocol.CandidateOutcome.VOID
    assert partial.estimates == ()


def test_reducer_rejects_cross_task_order_and_exact_excluded_provenance(
    fitted_bundle, synthetic_batch
):
    config = fitted_bundle[1]
    metrics = _metrics(synthetic_batch, config)
    crossed = protocol.finalize_candidate(
        synthetic_batch, (metrics[1], metrics[0], *metrics[2:]), config
    )
    assert crossed.outcome is protocol.CandidateOutcome.VOID
    assert "TASK_00_ORDER_OR_MANIFEST_DRIFT" in crossed.reason_codes

    exclusion = protocol.build_protocol_config(
        config.arm_configs,
        excluded_task_provenance=(
            (synthetic_batch.seed_commitment_sha256, (0, 1, 2)),
        ),
    )
    rebound = tuple(
        _metric(task, exclusion, q=0.9, b=0.2, r=0.2, c=0.0)
        for task in synthetic_batch.tasks
    )
    excluded = protocol.finalize_candidate(synthetic_batch, rebound, exclusion)
    assert excluded.outcome is protocol.CandidateOutcome.VOID
    assert excluded.reason_codes == ("EXCLUDED_TASK_PROVENANCE_REUSED",)


def test_structural_collision_is_retained_not_treated_as_excluded(fitted_bundle):
    config = fitted_bundle[1]
    source = generate_task(
        external_seed=hashlib.sha256(b"synthetic-duplicate-source").digest()
    )
    tasks = tuple(
        _build_task(
            seed_commitment_sha256=source.seed_commitment_sha256,
            draw_index=index,
            rank_gains=source.rank_gains,
            split_coefficients=source.split_coefficients,
            split_residues=source.split_residues,
        )
        for index in range(20)
    )
    duplicates = tuple((index, 0) for index in range(1, 20))
    payload = {
        "duplicate_structural_target_draws": [list(row) for row in duplicates],
        "duplicate_structural_task_draws": [list(row) for row in duplicates],
        "requested_count": 20,
        "schema_version": "hswm-swm0w-s2s-task-batch/v2",
        "seed_commitment_sha256": source.seed_commitment_sha256,
        "task_manifest_sha256s": [task.manifest_sha256 for task in tasks],
    }
    batch = TaskBatchV2(
        source.seed_commitment_sha256,
        20,
        tasks,
        duplicates,
        duplicates,
        canonical_sha256(payload),
    )
    metrics = _metrics(batch, config)
    result = protocol.finalize_candidate(batch, metrics, config)
    assert result.outcome is protocol.CandidateOutcome.CANDIDATE_PASS_AWAITING_BUNDLE
    assert len(result.task_metrics) == 20
    assert len({row.structural_task_sha256 for row in result.task_metrics}) == 1


def test_task_metric_parser_rejects_negative_zero_nan_and_hash_tamper(
    fitted_bundle, synthetic_batch
):
    metric = _metrics(synthetic_batch, fitted_bundle[1])[0]
    assert protocol.parse_task_metric_receipt(metric.canonical()) == metric
    negative_zero = metric.canonical()
    negative_zero["c_hex"] = "-0x0.0p+0"
    negative_zero = _rehash(negative_zero)
    with pytest.raises(protocol.SWM0WS2SProtocolError):
        protocol.parse_task_metric_receipt(negative_zero)
    nonfinite = metric.canonical()
    nonfinite["q_hex"] = "nan"
    nonfinite = _rehash(nonfinite)
    with pytest.raises(protocol.SWM0WS2SProtocolError):
        protocol.parse_task_metric_receipt(nonfinite)
    tampered = metric.canonical()
    tampered["task_manifest_sha256"] = "0" * 64
    with pytest.raises(protocol.SWM0WS2SProtocolError):
        protocol.parse_task_metric_receipt(tampered)
