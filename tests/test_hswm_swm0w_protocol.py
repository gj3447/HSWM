from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from hswm.experiments import swm0w_protocol as protocol
from hswm.experiments import swm0w_operator as operator
from hswm.experiments import swm0w_task_family as tasks
from hswm.experiments import swm0w_worlds as worlds


ZERO = "0" * 64
ONE = "1" * 64


def _digest(*parts: object) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode("ascii")).hexdigest()


def _seed(index: int) -> bytes:
    return (index + 1).to_bytes(32, "big")


def _admission() -> protocol.ConfirmatoryAdmissionV1:
    unsigned = {
        "admission_status": "GITHUB_OPERATIONAL_CHRONOLOGY_OBSERVED",
        "commitment_sha256": "2" * 64,
        "experiment_id": "HSWM-SWM0W-CONFIRMATORY-1",
        "future_round": 123,
        "github_chronology_receipt_sha256": "3" * 64,
        "preregistration_sha256": "4" * 64,
        "prereg_file_sha256": "5" * 64,
        "protocol_contract_sha256": operator.canonical_sha256(
            protocol.protocol_contract()
        ),
        "registration_commit_b": "b" * 40,
        "registration_core_sha256": "6" * 64,
        "schema_version": protocol.ADMISSION_RECEIPT_SCHEMA,
        "source_commit_a": "a" * 40,
        "task_seed_binding_sha256": protocol.ordered_task_seed_binding_sha256(
            tuple(_seed(index) for index in range(20))
        ),
        "validated": True,
        "workflow_sha256": "8" * 64,
    }
    return protocol.validate_admission_receipt(
        {**unsigned, "receipt_sha256": operator.canonical_sha256(unsigned)}
    )


def _variance() -> protocol.ExactTestVariance:
    # 2,500 integer targets at +2 and 2,500 at -2 with dyadic scale 2^-1.
    # Population variance = (5000*20000)/(5000^2) * 2^-2 = 1 exactly.
    return protocol.ExactTestVariance(5_000, 0, 20_000, 1)


def _arm_result(
    spec: protocol.ArmSpec,
    task_uid: str,
    requested_r2: float,
    marker: int,
    optimizer: protocol.OptimizerTemplate,
) -> protocol.ArmResult:
    variance = _variance()
    mse = float(1.0 - requested_r2)
    actual_r2 = protocol.r_squared_from_mse(mse, variance)
    state_sha = _digest("arm-state", task_uid, spec.spec_id, marker)
    return protocol.ArmResult(
        spec_id=spec.spec_id,
        optimizer_seed=protocol.optimizer_seed_from_task_uid(task_uid),
        training_config_sha256=operator.canonical_sha256(
            optimizer.config(spec, task_uid).canonical()
        ),
        model_state_sha256=state_sha,
        optimization_receipt_sha256=_digest(
            "arm-optimization", task_uid, spec.spec_id, marker
        ),
        score_receipt_sha256=_digest("arm-score", task_uid, spec.spec_id, marker),
        predictions_sha256=_digest(
            "arm-predictions", task_uid, spec.spec_id, marker
        ),
        mean_squared_error=mse,
        test_r2=actual_r2,
    )


def _task_receipt(
    index: int,
    *,
    q: float = 0.95,
    l: float = 0.20,
    c: float = 0.00,
    h: float = 0.20,
    s: float = 0.10,
    r: float = 0.20,
    k: float = 0.20,
    optimizer: protocol.OptimizerTemplate = protocol.CONFIRMATORY_OPTIMIZER,
) -> protocol.TaskReceipt:
    task_uid = f"swm0wt_{index + 1:024x}"
    requested = {
        "T16": q,
        "P16": q - l,
        "A16": q - l - 0.01,
        "R16": q - l - 0.02,
        "F16": q - c,
        "D16": q - c - 0.01,
        "P17-cap": q - k,
        "A21-cap": q - k - 0.01,
        "R64-cap": q - k - 0.02,
    }
    arms = tuple(
        _arm_result(
            spec,
            task_uid,
            requested[spec.spec_id],
            index + position + 1,
            optimizer,
        )
        for position, spec in enumerate(protocol.ARM_SPECS)
    )
    base_r2 = arms[0].test_r2
    nontriple_damage = h - s
    heads = []
    for position, head in enumerate(protocol.HEAD_SPECS):
        requested_damage = h if head.roles == worlds.ROLES else nontriple_damage
        mse = float(1.0 - (base_r2 - requested_damage))
        ablated_r2 = protocol.r_squared_from_mse(mse, _variance())
        damage = base_r2 - ablated_r2
        removal_sha = _digest("head-removal", task_uid, position)
        ablated_sha = _digest("head-state", task_uid, position)
        score_sha = _digest("head-score", task_uid, position)
        predictions_sha = _digest("head-predictions", task_uid, position)
        heads.append(
            protocol.HeadResult(
                head=head,
                removal_receipt_sha256=removal_sha,
                ablated_state_sha256=ablated_sha,
                restored_state_sha256=arms[0].model_state_sha256,
                restored_score_receipt_sha256=arms[0].score_receipt_sha256,
                restored_predictions_sha256=arms[0].predictions_sha256,
                score_receipt_sha256=score_sha,
                predictions_sha256=predictions_sha,
                ablated_mse=mse,
                ablated_r2=ablated_r2,
                damage=damage,
            )
        )
    cycle_mse = float(1.0 - (base_r2 - r))
    cycle_r2 = protocol.r_squared_from_mse(cycle_mse, _variance())
    metrics = protocol.metric_vector_from_measurements(
        {row.spec_id: row for row in arms}, cycle_r2, heads
    )
    template_sha = operator.canonical_sha256(optimizer.canonical())
    task_sha = _digest("task", index)
    task_seed_sha = hashlib.sha256(_seed(index)).hexdigest()
    parity_sha = _digest("parity", index)
    cycle_score_sha = _digest("cycle-score", index)
    cycle_predictions_sha = _digest("cycle-predictions", index)
    unsigned = {
        "arm_results": [row.canonical() for row in arms],
        "exact_test_variance": _variance().canonical(),
        "head_results": [row.canonical() for row in heads],
        "metrics": metrics.canonical(),
        "native_star_parity": {
            "exact": True,
            "receipt_sha256": parity_sha,
            "world_count": 15_625,
        },
        "optimizer_template": optimizer.canonical(),
        "optimizer_template_sha256": template_sha,
        "role_cycle": {
            "mean_squared_error_hex": cycle_mse.hex(),
            "predictions_sha256": cycle_predictions_sha,
            "r2_hex": cycle_r2.hex(),
            "rule": protocol.ROLE_CYCLE_RULE,
            "score_receipt_sha256": cycle_score_sha,
        },
        "schema_version": protocol.TASK_RECEIPT_SCHEMA,
        "task_index": index,
        "task_sha256": task_sha,
        "task_seed_sha256": task_seed_sha,
        "task_uid": task_uid,
    }
    return protocol.TaskReceipt(
        task_index=index,
        task_uid=task_uid,
        task_sha256=task_sha,
        task_seed_sha256=task_seed_sha,
        optimizer_template=optimizer,
        optimizer_template_sha256=template_sha,
        exact_variance=_variance(),
        arm_results=arms,
        native_star_world_count=15_625,
        native_star_parity_sha256=parity_sha,
        role_cycle_score_receipt_sha256=cycle_score_sha,
        role_cycle_predictions_sha256=cycle_predictions_sha,
        role_cycle_mse=cycle_mse,
        role_cycle_r2=cycle_r2,
        head_results=tuple(heads),
        metrics=metrics,
        receipt_sha256=operator.canonical_sha256(unsigned),
    )


def test_contract_is_occam_bounded_and_exactly_registered() -> None:
    assert [(row.spec_id, row.arm.value, row.width) for row in protocol.ARM_SPECS] == [
        ("T16", "ROLE_TRIPLE", 16),
        ("P16", "LOWER_ORDER_PAIR", 16),
        ("A16", "ADDITIVE", 16),
        ("R16", "ROLELESS", 16),
        ("F16", "FLAT_MLP", 16),
        ("D16", "ROLE_AWARE_DEEPSETS", 16),
        ("P17-cap", "LOWER_ORDER_PAIR", 17),
        ("A21-cap", "ADDITIVE", 21),
        ("R64-cap", "ROLELESS", 64),
    ]
    assert tuple(head.roles for head in protocol.HEAD_SPECS) == (
        ("r0",), ("r1",), ("r2",),
        ("r0", "r1"), ("r0", "r2"), ("r1", "r2"),
        ("r0", "r1", "r2"),
    )
    contract = protocol.protocol_contract()
    assert contract["task_count"] == 20
    assert contract["test_case_count"] == 5_000
    assert contract["confirmatory_optimizer"]["epochs"] == 300
    assert contract["thresholds"]["q"] == 0.80.hex()
    assert contract["bootstrap"]["sample_shape"] == [10_000, 20]
    assert contract["bootstrap"]["quantiles"] == [0.05, 0.95]
    assert contract["scope"]["standalone_authoritative_verdict"] is False
    assert contract["scope"]["external_admission_is_structural_not_authenticating"]
    assert "TYPED_STAR_TRIPLE" not in {row["arm"] for row in contract["arm_specs"]}


def test_optimizer_seed_is_exact_task_uid_hex_and_shared_by_arms() -> None:
    uid = "swm0wt_0123456789abcdef01234567"
    expected = int.from_bytes(
        hashlib.sha256(
            b"hswm-swm0w-optimizer-seed/v1\x00" + uid.encode("ascii")
        ).digest()[:8],
        "big",
    )
    assert protocol.optimizer_seed_from_task_uid(uid) == expected
    configs = [spec for spec in protocol.ARM_SPECS]
    assert {
        protocol.CONFIRMATORY_OPTIMIZER.config(spec, uid).seed for spec in configs
    } == {expected}
    with pytest.raises(protocol.SWM0WProtocolError, match="exact task uid"):
        protocol.optimizer_seed_from_task_uid("swm0wt_bad")


def test_ordered_seed_binding_is_exact_ordered_and_fail_closed() -> None:
    seeds = tuple(_seed(index) for index in range(20))
    first = protocol.ordered_task_seed_binding_sha256(seeds)
    assert first == protocol.ordered_task_seed_binding_sha256(tuple(seeds))
    assert first != protocol.ordered_task_seed_binding_sha256(tuple(reversed(seeds)))
    with pytest.raises(protocol.SWM0WProtocolError, match="exactly 20"):
        protocol.ordered_task_seed_binding_sha256(seeds[:-1])
    with pytest.raises(protocol.SWM0WProtocolError, match="unique"):
        protocol.ordered_task_seed_binding_sha256((seeds[0],) * 20)


def test_exact_variance_and_r_squared_do_not_estimate_test_variance() -> None:
    variance = _variance()
    assert variance.centered_numerator == 100_000_000
    assert variance.population_variance == 1.0
    assert protocol.r_squared_from_mse(0.25, variance) == 0.75
    payload = variance.canonical()
    assert payload["target_integer_sum"] == 0
    assert payload["target_integer_sum_of_squares"] == 20_000
    assert payload["population_variance_hex"] == 1.0.hex()


def test_fixed_role_cycle_changes_roles_without_adding_evaluator_fields() -> None:
    world = worlds.ModelWorldV1(
        tuple(
            worlds.RoleInputV1(role, features)
            for role, features in zip(
                worlds.ROLES,
                ((-1.0, -0.5), (0.0, 0.5), (1.0, -1.0)),
            )
        )
    )
    cycled = protocol.cycle_role_inputs(world)
    assert cycled.feature_matrix() == (
        (0.0, 0.5), (1.0, -1.0), (-1.0, -0.5)
    )
    encoded = operator.canonical_json(cycled.canonical())
    assert all(word not in encoded for word in ("target", "split", "task_uid", "label"))


def test_task_receipt_recomputes_all_metrics_and_is_content_addressed() -> None:
    receipt = _task_receipt(0)
    assert receipt.metrics.q == receipt.arm_results[0].test_r2
    assert receipt.metrics.l > 0.19
    assert receipt.metrics.c == 0.0
    assert receipt.metrics.h > 0.19
    assert receipt.metrics.s > 0.09
    assert receipt.metrics.r > 0.19
    assert receipt.metrics.k > 0.19
    assert receipt.receipt_sha256 == operator.canonical_sha256(receipt.unsigned())
    assert protocol.validate_task_receipt(receipt.canonical()) == receipt
    with pytest.raises(protocol.SWM0WProtocolError, match="task metrics"):
        replace(receipt, metrics=replace(receipt.metrics, q=0.0))
    with pytest.raises(protocol.SWM0WProtocolError, match="receipt hash"):
        replace(receipt, receipt_sha256=ZERO)
    with pytest.raises(protocol.SWM0WProtocolError, match="5,000 test cases"):
        replace(receipt, exact_variance=protocol.ExactTestVariance(2, 0, 8, 1))


def test_task_receipt_binds_each_arm_config_and_real_head_state_change() -> None:
    receipt = _task_receipt(0)

    wrong_config = receipt.canonical()
    wrong_config["arm_results"][0]["training_config_sha256"] = ZERO
    wrong_config["receipt_sha256"] = operator.canonical_sha256(
        {key: value for key, value in wrong_config.items() if key != "receipt_sha256"}
    )
    with pytest.raises(protocol.SWM0WProtocolError, match="arm training config"):
        protocol.validate_task_receipt(wrong_config)

    unchanged_head = receipt.canonical()
    unchanged_head["head_results"][0]["ablated_state_sha256"] = (
        unchanged_head["arm_results"][0]["model_state_sha256"]
    )
    unchanged_head["receipt_sha256"] = operator.canonical_sha256(
        {key: value for key, value in unchanged_head.items() if key != "receipt_sha256"}
    )
    with pytest.raises(protocol.SWM0WProtocolError, match="did not change"):
        protocol.validate_task_receipt(unchanged_head)

    repeated_states = receipt.canonical()
    repeated = repeated_states["head_results"][0]["ablated_state_sha256"]
    for row in repeated_states["head_results"]:
        row["ablated_state_sha256"] = repeated
    repeated_states["receipt_sha256"] = operator.canonical_sha256(
        {key: value for key, value in repeated_states.items() if key != "receipt_sha256"}
    )
    with pytest.raises(protocol.SWM0WProtocolError, match="unique ablated"):
        protocol.validate_task_receipt(repeated_states)

    false_unchanged_predictions = receipt.canonical()
    false_unchanged_predictions["head_results"][0]["predictions_sha256"] = (
        false_unchanged_predictions["arm_results"][0]["predictions_sha256"]
    )
    false_unchanged_predictions["receipt_sha256"] = operator.canonical_sha256(
        {
            key: value
            for key, value in false_unchanged_predictions.items()
            if key != "receipt_sha256"
        }
    )
    with pytest.raises(protocol.SWM0WProtocolError, match="zero damage"):
        protocol.validate_task_receipt(false_unchanged_predictions)

    repeated_arm_predictions = receipt.canonical()
    repeated_arm_predictions["arm_results"][1]["predictions_sha256"] = (
        repeated_arm_predictions["arm_results"][0]["predictions_sha256"]
    )
    repeated_arm_predictions["receipt_sha256"] = operator.canonical_sha256(
        {
            key: value
            for key, value in repeated_arm_predictions.items()
            if key != "receipt_sha256"
        }
    )
    with pytest.raises(protocol.SWM0WProtocolError, match="equal prediction"):
        protocol.validate_task_receipt(repeated_arm_predictions)

    repeated_cycle_score = receipt.canonical()
    repeated_cycle_score["role_cycle"]["score_receipt_sha256"] = (
        repeated_cycle_score["arm_results"][0]["score_receipt_sha256"]
    )
    repeated_cycle_score["receipt_sha256"] = operator.canonical_sha256(
        {
            key: value
            for key, value in repeated_cycle_score.items()
            if key != "receipt_sha256"
        }
    )
    with pytest.raises(protocol.SWM0WProtocolError, match="equal score"):
        protocol.validate_task_receipt(repeated_cycle_score)


def test_receipt_parsers_reject_json_bool_integer_aliases() -> None:
    task_payload = _task_receipt(0).canonical()
    task_payload["head_results"][0]["head"]["order"] = True
    with pytest.raises(protocol.SWM0WProtocolError, match="selector"):
        protocol.validate_task_receipt(task_payload)

    final_payload = protocol.finalize_protocol(
        tuple(_task_receipt(index) for index in range(20)),
        mode="CONFIRMATORY",
        admission=_admission(),
    ).canonical()
    final_payload["bootstrap"]["shared_across_metrics"] = 1
    with pytest.raises(protocol.SWM0WProtocolError, match="primitive type"):
        protocol.validate_final_receipt(final_payload)


def test_shared_bootstrap_is_exact_deterministic_and_reused() -> None:
    first = protocol.shared_task_bootstrap_indices()
    second = protocol.shared_task_bootstrap_indices()
    assert first.shape == (10_000, 20)
    assert first.dtype == np.int64
    assert np.array_equal(first, second)
    assert first.flags.writeable is False
    receipts = tuple(_task_receipt(index, q=0.91 + index / 1000) for index in range(20))
    estimates = dict(protocol.summarize_metrics(receipts))
    q_values = np.asarray([row.metrics.q for row in receipts])
    expected = q_values[first].mean(axis=1)
    lower, upper = np.quantile(expected, [0.05, 0.95], method="linear")
    assert estimates["Q"].lower == float(lower)
    assert estimates["Q"].upper == float(upper)


def test_reducer_emits_pass_kill_inconclusive_and_void() -> None:
    admitted = _admission()
    passing = tuple(_task_receipt(index) for index in range(20))
    passed = protocol.finalize_protocol(
        passing,
        mode=protocol.RunMode.CONFIRMATORY,
        admission=admitted,
    )
    assert passed.outcome is protocol.ProtocolOutcome.CANDIDATE_PASS_AWAITING_BUNDLE
    assert passed.capacity_independent_phrase_candidate
    assert "verdict" not in passed.canonical()
    assert "capacity_independent_phrase_allowed" not in passed.canonical()
    assert passed.receipt_sha256 == operator.canonical_sha256(passed.unsigned())
    assert protocol.validate_final_receipt(passed.canonical()) == passed
    forged = passed.canonical()
    forged["outcome"] = "CANDIDATE_KILL_AWAITING_BUNDLE"
    forged["capacity_independent_phrase_candidate"] = False
    forged["receipt_sha256"] = operator.canonical_sha256(
        {key: value for key, value in forged.items() if key != "receipt_sha256"}
    )
    with pytest.raises(protocol.SWM0WProtocolError, match="recompute"):
        protocol.validate_final_receipt(forged)

    killed = protocol.finalize_protocol(
        tuple(_task_receipt(index, q=0.50) for index in range(20)),
        mode="CONFIRMATORY",
        admission=admitted,
    )
    assert killed.outcome is protocol.ProtocolOutcome.CANDIDATE_KILL_AWAITING_BUNDLE
    assert "Q_UCB_BELOW_GATE" in killed.reason_codes

    crossing = tuple(
        _task_receipt(index, q=0.70 if index < 10 else 0.90)
        for index in range(20)
    )
    inconclusive = protocol.finalize_protocol(
        crossing,
        mode="CONFIRMATORY",
        admission=admitted,
    )
    assert inconclusive.outcome is (
        protocol.ProtocolOutcome.CANDIDATE_INCONCLUSIVE_AWAITING_BUNDLE
    )

    void = protocol.finalize_protocol(passing, mode="CONFIRMATORY")
    assert void.outcome is protocol.ProtocolOutcome.VOID
    assert "MISSING_OR_MISMATCHED_OPERATIONAL_ADMISSION" in void.reason_codes


def test_diagnostic_mode_is_explicit_and_never_makes_a_gate_decision() -> None:
    tiny = protocol.OptimizerTemplate(epochs=1, batch_size=8192, patience=1)
    receipt = _task_receipt(0, optimizer=tiny)
    final = protocol.finalize_protocol(
        (receipt,), mode=protocol.RunMode.DIAGNOSTIC, optimizer=tiny
    )
    assert final.outcome is protocol.ProtocolOutcome.DIAGNOSTIC_ONLY
    assert final.reason_codes == ("DIAGNOSTIC_ONLY",)
    assert final.bootstrap_indices_sha256 is None
    assert all(estimate.lower is None for _, estimate in final.metric_estimates)
    void = protocol.finalize_protocol(
        (receipt,),
        mode=protocol.RunMode.DIAGNOSTIC,
        optimizer=tiny,
        integrity_errors=("HASH_MISMATCH",),
    )
    assert void.outcome is protocol.ProtocolOutcome.VOID
    assert void.reason_codes == ("HASH_MISMATCH",)


def test_receipts_reject_ducks_and_finalize_rechecks_frozen_nested_state() -> None:
    receipt = _task_receipt(0)

    class MetricDuck:
        q = receipt.metrics.q
        l = receipt.metrics.l
        c = receipt.metrics.c
        h = receipt.metrics.h
        s = receipt.metrics.s
        r = receipt.metrics.r
        k = receipt.metrics.k

        def canonical(self):
            return receipt.metrics.canonical()

    with pytest.raises(protocol.SWM0WProtocolError, match="exact MetricVector"):
        replace(receipt, metrics=MetricDuck())
    with pytest.raises(protocol.SWM0WProtocolError, match="all nine arms"):
        replace(receipt, arm_results=list(receipt.arm_results))

    object.__setattr__(receipt.metrics, "q", 123.0)
    with pytest.raises(protocol.SWM0WProtocolError, match="changed after"):
        protocol.finalize_protocol((receipt,), mode="DIAGNOSTIC")


def test_optimizer_template_rejects_bool_and_integer_float_drift() -> None:
    with pytest.raises(protocol.SWM0WProtocolError, match="exact integers"):
        protocol.OptimizerTemplate(epochs=True)
    with pytest.raises(protocol.SWM0WProtocolError, match="exact floats"):
        protocol.OptimizerTemplate(gradient_clip=5)


def test_confirmatory_contract_rejects_count_optimizer_and_order_drift() -> None:
    one = _task_receipt(0)
    partial = protocol.finalize_protocol(
        (one,), mode="CONFIRMATORY", admission=_admission()
    )
    assert partial.outcome is protocol.ProtocolOutcome.VOID
    assert "CONFIRMATORY_TASK_COUNT_DRIFT" in partial.reason_codes
    with pytest.raises(protocol.SWM0WProtocolError, match="seed order"):
        protocol.finalize_protocol((_task_receipt(1),), mode="DIAGNOSTIC")
    with pytest.raises(protocol.SWM0WProtocolError, match="exactly 20"):
        protocol.run_protocol(
            (b"x" * 32,), mode="CONFIRMATORY", admission=_admission()
        )
    drifted = protocol.Thresholds(q=0.79)
    drifted_result = protocol.finalize_protocol(
        tuple(_task_receipt(index) for index in range(20)),
        mode="CONFIRMATORY",
        admission=_admission(),
        thresholds=drifted,
    )
    assert drifted_result.outcome is protocol.ProtocolOutcome.VOID
    assert "CONFIRMATORY_THRESHOLD_DRIFT" in drifted_result.reason_codes


def test_confirmatory_seed_mismatch_is_rejected_before_training(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seeds = list(_seed(index) for index in range(20))
    seeds[-1] = b"z" * 32
    called = False

    def forbidden(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("training must not start")

    monkeypatch.setattr(protocol, "execute_task", forbidden)
    with pytest.raises(protocol.SWM0WProtocolError, match="different ordered"):
        protocol.run_protocol(
            tuple(seeds), mode="CONFIRMATORY", admission=_admission()
        )
    assert called is False


def test_one_tiny_diagnostic_executes_label_free_and_restores_all_heads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed = []
    original = operator.LearnedSWM0WOperator.predict

    def guarded(self, world):
        assert type(world) is worlds.ModelWorldV1
        observed.append(world)
        return original(self, world)

    monkeypatch.setattr(operator.LearnedSWM0WOperator, "predict", guarded)
    # The protocol imports the class, so the patched method also guards its
    # label-free test and role-cycle crossings.
    tiny = protocol.OptimizerTemplate(epochs=1, batch_size=8192, patience=1)
    receipt = protocol.execute_task(
        b"swm0w-protocol-diagnostic-seed!" + b"x" * 16,
        0,
        mode="DIAGNOSTIC",
        optimizer=tiny,
    )
    assert observed
    assert len(receipt.arm_results) == 9
    assert len(receipt.head_results) == 7
    assert all(
        row.restored_state_sha256 == receipt.arm_results[0].model_state_sha256
        for row in receipt.head_results
    )
    assert receipt.native_star_world_count == 15_625
    assert receipt.receipt_sha256 == operator.canonical_sha256(receipt.unsigned())


def test_cli_contract_and_source_boundaries(capsys: pytest.CaptureFixture[str]) -> None:
    assert protocol.main(["contract"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["protocol_version"] == protocol.PROTOCOL_VERSION
    source = Path(protocol.__file__).read_text(encoding="utf-8")
    test_source = Path(__file__).read_text(encoding="utf-8")
    assert len(test_source.splitlines()) < 700
    assert "scipy" not in source.lower()
    assert "._" not in "\n".join(
        line for line in source.splitlines() if line.lstrip().startswith("from hswm")
    )
    assert "swm0w_beacon" not in source
    assert "requests." not in source.lower()
    assert "np.linalg" not in source
    assert "subprocess" not in source
    assert "socket" not in source
