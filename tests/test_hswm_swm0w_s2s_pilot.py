from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from hswm.experiments import swm0w_s2s_pilot as pilot


def _sha(*values: object) -> str:
    return hashlib.sha256(repr(values).encode("utf-8")).hexdigest()


class FakeTask:
    def __init__(self, draw_index: int, split_calls: list[tuple[int, str]]) -> None:
        self.draw_index = draw_index
        self.family_certificate_sha256 = "c" * 64
        self.family_definition_sha256 = "d" * 64
        self.manifest_sha256 = pilot.EXPECTED_TASK_MANIFEST_SHA256S[draw_index]
        self.seed_commitment_sha256 = pilot.EXPECTED_SEED_COMMITMENT_SHA256
        self.structural_target_sha256 = (
            pilot.EXPECTED_STRUCTURAL_TARGET_SHA256S[draw_index]
        )
        self.structural_task_sha256 = (
            pilot.EXPECTED_STRUCTURAL_TASK_SHA256S[draw_index]
        )
        self._split_calls = split_calls

    def iter_cases(self, split: str):
        self._split_calls.append((self.draw_index, split))
        if split not in {"train", "dev"}:
            raise AssertionError(f"forbidden split: {split}")
        yield (self.draw_index, split)

    def canonical(self) -> dict[str, object]:
        return {
            "draw_index": self.draw_index,
            "family_certificate_sha256": self.family_certificate_sha256,
            "family_definition_sha256": self.family_definition_sha256,
            "manifest_sha256": self.manifest_sha256,
            "seed_commitment_sha256": self.seed_commitment_sha256,
            "structural_target_sha256": self.structural_target_sha256,
            "structural_task_sha256": self.structural_task_sha256,
        }


@dataclass(frozen=True)
class FakeHistory:
    dev_loss: float


class FakeOptimization:
    def __init__(
        self,
        *,
        key: tuple[object, ...],
        config: object,
        initial_dev_loss: float,
        best_dev_loss: float,
    ) -> None:
        self.config = config
        self.stopped_update = config.max_updates
        self.best_update = config.max_updates
        self.best_train_loss = best_dev_loss * 0.9
        self.best_dev_loss = best_dev_loss
        self.clipped_update_count = config.max_updates // 2
        self.termination_reason = "MAX_UPDATES"
        self.history = (FakeHistory(initial_dev_loss),)
        self.initial_parameters_sha256 = _sha("initial", key[1])
        self.receipt_sha256 = _sha("receipt", key, config.max_updates)

    def canonical(self) -> dict[str, object]:
        return {
            "best_dev_loss_hex": self.best_dev_loss.hex(),
            "best_train_loss_hex": self.best_train_loss.hex(),
            "best_update": self.best_update,
            "clipped_update_count": self.clipped_update_count,
            "history": [{"dev_loss_hex": self.history[0].dev_loss.hex()}],
            "initial_parameters_sha256": self.initial_parameters_sha256,
            "receipt_sha256": self.receipt_sha256,
            "stopped_update": self.stopped_update,
            "termination_reason": self.termination_reason,
        }


class FakeModel:
    def __init__(
        self,
        *,
        arm: object,
        config: object,
        optimization: FakeOptimization,
        parameter_value: float,
    ) -> None:
        self.arm = arm
        self.config = config
        self.optimization = optimization
        self.fitted = True
        self.learned = optimization.best_update > 0
        self.parameters = {
            "w": np.asarray([parameter_value], dtype=np.float64)
        }
        self.parameters_sha256 = hashlib.sha256(
            self.parameters["w"].tobytes(order="C")
        ).hexdigest()
        self.state_sha256 = _sha(
            "state", optimization.receipt_sha256, self.parameters_sha256
        )

    def replay_copy(self, *, mutate_parameter: bool = False) -> "FakeModel":
        replayed = FakeModel(
            arm=self.arm,
            config=self.config,
            optimization=self.optimization,
            parameter_value=float(self.parameters["w"][0]),
        )
        if mutate_parameter:
            replayed.parameters["w"][0] += 1.0
            # Deliberately retain the original hashes: byte comparison is a
            # separate replay requirement.
            replayed.parameters_sha256 = self.parameters_sha256
            replayed.state_sha256 = self.state_sha256
        return replayed


class StepClock:
    def __init__(self, step_ns: int = 1_000_000) -> None:
        self.value = 0
        self.step_ns = step_ns

    def __call__(self) -> int:
        self.value += self.step_ns
        return self.value


def _environment() -> dict[str, object]:
    return {
        "fixture": "unit-test-numeric-environment",
        "thread_environment": {"OPENBLAS_NUM_THREADS": "1"},
    }


def _dependencies(
    *,
    step_ns: int = 1_000_000,
    baseline_mismatch: tuple[int, str, str] | None = None,
    replay_mismatch_at: int | None = None,
):
    split_calls: list[tuple[int, str]] = []
    fit_calls: list[tuple[int, int, str, str]] = []
    replay_calls: list[FakeModel] = []

    def generate_task(*, external_seed: bytes, draw_index: int) -> FakeTask:
        assert external_seed == pilot.EXTERNAL_SEED
        return FakeTask(draw_index, split_calls)

    selected_ratio = {
        "T16": {"0.001": 0.5, "0.003": 0.25, "0.01": 0.75},
        "P_CAP18": {"0.001": 0.125, "0.003": 0.5, "0.01": 0.75},
        "DS870": {"0.001": 0.75, "0.003": 0.5, "0.01": 0.125},
    }

    def fit(task, train, dev, *, arm, config):
        assert train == ((task.draw_index, "train"),)
        assert dev == ((task.draw_index, "dev"),)
        label = next(
            label
            for label, binary64 in pilot.LEARNING_RATE_HEX.items()
            if binary64 == config.learning_rate.hex()
        )
        fit_calls.append((config.max_updates, task.draw_index, arm.value, label))
        initial = float(2**task.draw_index)
        public_arm = (
            "DEEPSETS_870" if arm.value == "DS870" else arm.value
        )
        if baseline_mismatch == (task.draw_index, public_arm, label) and (
            config.max_updates == pilot.STAGE2_MAX_UPDATES
        ):
            initial *= 2.0
        ratio = (
            0.99
            if config.max_updates == pilot.STAGE1_MAX_UPDATES
            else selected_ratio[arm.value][label]
        )
        key = (task.draw_index, arm.value, label, config.max_updates)
        optimization = FakeOptimization(
            key=key,
            config=config,
            initial_dev_loss=initial,
            best_dev_loss=initial * ratio,
        )
        value = float(
            1
            + task.draw_index * 100
            + tuple(pilot.PUBLIC_TO_OPERATOR_ARM.values()).index(arm.value) * 10
            + pilot.LEARNING_RATE_LABELS.index(label)
            + config.max_updates
        )
        return FakeModel(
            arm=arm,
            config=config,
            optimization=optimization,
            parameter_value=value,
        )

    def replay(model: FakeModel) -> FakeModel:
        replay_calls.append(model)
        return model.replay_copy(
            mutate_parameter=(
                replay_mismatch_at is not None
                and len(replay_calls) == replay_mismatch_at
            )
        )

    return {
        "task_generator": generate_task,
        "fitter": fit,
        "replayer": replay,
        "clock_ns": StepClock(step_ns),
        "peak_rss_kib": lambda: 12_345,
        "environment": _environment(),
        "selector": pilot._select_validated_learning_rates,
    }, split_calls, fit_calls, replay_calls


def _rehash_cell(cell: dict[str, object]) -> None:
    unsigned = dict(cell)
    unsigned.pop("cell_receipt_sha256")
    cell["cell_receipt_sha256"] = pilot.canonical_sha256(unsigned)


def _build_strict_cell(stage: str) -> dict[str, object]:
    """Build a valid receipt without executing optimizer updates."""

    from hswm.experiments.swm0w_s2s_operator import S2SArm, architecture_receipt
    from hswm.experiments import swm0w_s2s_training as training

    task = pilot._expected_public_task(0)
    if stage == pilot.STAGE1_NAME:
        max_updates = update_count = pilot.STAGE1_MAX_UPDATES
        termination = training.TerminationReason.MAX_UPDATES
    elif stage == pilot.STAGE2_NAME:
        max_updates = pilot.STAGE2_MAX_UPDATES
        update_count = pilot.PATIENCE
        termination = training.TerminationReason.PATIENCE
    else:
        raise AssertionError(stage)
    config = pilot._config_for(max_updates, "0.001")
    arm = S2SArm.T16
    data = training._compiled_task_data(task)
    parameters = training._training_initial_parameters(arm, config.seed)
    initial_sha = training._parameter_sha256(arm, parameters)
    train_loss = training._loss_for_parameters(
        arm, parameters, data.train_x, data.train_targets, data.weights
    )
    dev_loss = training._loss_for_parameters(
        arm, parameters, data.dev_x, data.dev_targets, data.weights
    )
    history = (
        training.OptimizationHistoryEntry(
            update=0,
            train_loss=train_loss,
            dev_loss=dev_loss,
            gradient_norm=None,
            clipped=False,
            improved=True,
            parameters_sha256=initial_sha,
        ),
        *(
            training.OptimizationHistoryEntry(
                update=update,
                train_loss=train_loss,
                dev_loss=dev_loss,
                gradient_norm=0.0,
                clipped=False,
                improved=False,
                parameters_sha256=initial_sha,
            )
            for update in range(1, update_count + 1)
        ),
    )
    values = {
        "arm": arm,
        "config": config,
        "task": task,
        "family_definition_sha256": task.family_definition_sha256,
        "family_certificate_sha256": task.family_certificate_sha256,
        "structural_target_sha256": task.structural_target_sha256,
        "structural_task_sha256": task.structural_task_sha256,
        "task_manifest_sha256": task.manifest_sha256,
        "train_dataset_sha256": data.train_dataset_sha256,
        "dev_dataset_sha256": data.dev_dataset_sha256,
        "dataset_schema_sha256": training.DATASET_SCHEMA_SHA256,
        "train_case_count": len(tuple(task.iter_cases("train"))),
        "dev_case_count": len(tuple(task.iter_cases("dev"))),
        "stratum_loss_receipts": data.strata,
        "loss_definition_sha256": training._loss_definition_sha256(data.strata),
        "operator_architecture_receipt_sha256": architecture_receipt(
            arm
        ).receipt_sha256,
        "initial_parameters_sha256": initial_sha,
        "best_parameters_sha256": initial_sha,
        "best_update": 0,
        "stopped_update": update_count,
        "best_train_loss": train_loss,
        "best_dev_loss": dev_loss,
        "update_count": update_count,
        "clipped_update_count": 0,
        "history": history,
        "history_entry_count": len(history),
        "history_sha256": training._history_sha256(history),
        "termination_reason": termination,
    }
    receipt = training.S2SOptimizationReceipt(
        **values,
        receipt_sha256=training.canonical_sha256(
            training._optimization_unsigned_payload(values)
        ),
    )
    model = training.LearnedS2SOperator(
        arm=arm,
        config=config,
        parameters=parameters,
        optimization=receipt,
    )
    record = (
        pilot._throughput_cell_record
        if stage == pilot.STAGE1_NAME
        else pilot._full_cell_record
    )
    cell = record(
        model,
        task_binding=pilot._task_binding(task),
        cell_key=pilot._cell_key(0, 0, "T16", "0.001"),
    )
    pilot._validate_cell_prefix([cell], stage=stage)
    return cell


@pytest.fixture(scope="module")
def strict_stage1_cell() -> dict[str, object]:
    return _build_strict_cell(pilot.STAGE1_NAME)


@pytest.fixture(scope="module")
def strict_stage2_cell() -> dict[str, object]:
    return _build_strict_cell(pilot.STAGE2_NAME)


def _rehash_optimization_and_cell(cell: dict[str, object]) -> None:
    from hswm.experiments import swm0w_s2s_training as training

    optimization = cell["optimization_receipt"]
    unsigned = dict(optimization)
    unsigned.pop("receipt_sha256")
    optimization["receipt_sha256"] = training.canonical_sha256(unsigned)
    cell["optimization_receipt_sha256"] = optimization["receipt_sha256"]
    _rehash_cell(cell)


def _rehash_runtime_and_artifact(artifact: dict[str, object]) -> None:
    runtime = artifact["runtime_telemetry"]
    assert type(runtime) is dict
    unsigned_runtime = dict(runtime)
    unsigned_runtime.pop("runtime_telemetry_sha256")
    runtime["runtime_telemetry_sha256"] = pilot.canonical_sha256(
        unsigned_runtime
    )
    unsigned_artifact = dict(artifact)
    unsigned_artifact.pop("artifact_sha256")
    artifact["artifact_sha256"] = pilot.canonical_sha256(unsigned_artifact)


def _forbidden_stage1_paths(value: object, path: str = "$") -> list[str]:
    forbidden = (
        "best_update",
        "clipped",
        "clipping",
        "dev",
        "history",
        "loss",
        "train",
    )
    findings: list[str] = []
    if type(value) is dict:
        for key, item in value.items():
            lowered = key.lower()
            if any(token in lowered for token in forbidden):
                findings.append(f"{path}.{key}")
            findings.extend(_forbidden_stage1_paths(item, f"{path}.{key}"))
    elif type(value) is list:
        for index, item in enumerate(value):
            findings.extend(_forbidden_stage1_paths(item, f"{path}[{index}]"))
    elif type(value) is str:
        lowered = value.lower()
        if any(token in lowered for token in forbidden):
            findings.append(path)
    return findings


def test_contract_freezes_seed_roster_optimizer_and_manifest_goldens() -> None:
    from hswm.experiments.swm0w_s2s_family import generate_task_batch

    assert pilot.EXTERNAL_SEED == hashlib.sha256(
        b"HSWM-SWM0W-S2S-TRAIN-DEV-PILOT-v1"
    ).digest()
    assert pilot.EXTERNAL_SEED_SHA256_HEX == (
        "4d87b662169765730c5317052c27b824a3f3013ca88bec909467c56f00502b6c"
    )
    assert pilot.EXPECTED_TASK_BATCH_SHA256 == (
        "301b6c6fedd5094487036e0aafe3fbadd239a8593cbb9549132422a148904595"
    )
    assert pilot.EXPECTED_TASK_MANIFEST_SHA256S == (
        "0f926fcc84432a2b47c11405238a325a474539f9cbc69ff160246fa1be1cebe0",
        "eb229a225b8b3410a9ae98b3c960a70aedbacc50406a51b49fa1e11400d3d6bc",
        "2909e23547e2c870d1361156a9130ede96d94b2fa441420619ee049a4093980b",
    )
    assert len(pilot.fixed_roster()) == 27
    assert pilot.fixed_roster() == tuple(
        (draw, arm, rate)
        for draw in (0, 1, 2)
        for arm in ("T16", "P_CAP18", "DEEPSETS_870")
        for rate in ("0.001", "0.003", "0.01")
    )
    contract = pilot.pilot_contract_payload()
    public_batch = generate_task_batch(external_seed=pilot.EXTERNAL_SEED, count=3)
    public_bindings = [pilot._task_binding(task) for task in public_batch.tasks]
    assert public_batch.batch_sha256 == pilot.EXPECTED_TASK_BATCH_SHA256
    assert pilot._task_batch_sha256(public_bindings) == public_batch.batch_sha256
    assert contract["stage1"]["max_updates"] == 10
    assert contract["stage2"]["max_updates"] == 300
    assert contract["patience"] == 50
    assert contract["initializer_seed"] == 0
    assert contract["selection"]["stage1_losses_used"] is False
    boundary = contract["future_confirmatory_boundary"]
    assert boundary["pilot_seed_and_draw_provenance_are_excluded"] is True
    assert boundary["semantic_collisions_from_future_with_replacement_draws"] == (
        "RETAIN_AND_DISCLOSE_NEVER_FILTER_OR_REROLL"
    )
    assert pilot.canonical_sha256(contract) == pilot.PILOT_CONTRACT_SHA256


def test_admitted_run_uses_only_train_dev_and_exact_nonadaptive_double_roster() -> None:
    dependencies, split_calls, fit_calls, replay_calls = _dependencies()
    artifact = pilot.run_pilot(**dependencies)

    assert artifact["terminal_status"] == pilot.TERMINAL_COMPLETE
    assert artifact["verdict"] == pilot.NO_EFFICACY_VERDICT
    assert split_calls == [
        (draw, split) for draw in (0, 1, 2) for split in ("train", "dev")
    ]
    expected_stage1 = [
        (10, draw, pilot.PUBLIC_TO_OPERATOR_ARM[arm], rate)
        for draw, arm, rate in pilot.fixed_roster()
    ]
    expected_stage2 = [
        (300, draw, pilot.PUBLIC_TO_OPERATOR_ARM[arm], rate)
        for draw, arm, rate in pilot.fixed_roster()
    ]
    assert fit_calls == expected_stage1 + expected_stage2
    assert len(replay_calls) == 54

    deterministic = artifact["deterministic_receipt"]
    assert len(deterministic["ordered_stage1_cell_receipts"]) == 27
    assert len(deterministic["ordered_stage2_cell_receipts"]) == 27
    assert all(
        "best_dev_loss_hex" not in cell
        and cell["telemetry_only"] is True
        and cell["runner_replay_observed"] is True
        and "replay_validated" not in cell
        for cell in deterministic["ordered_stage1_cell_receipts"]
    )
    assert all(
        _forbidden_stage1_paths(cell) == []
        for cell in deterministic["ordered_stage1_cell_receipts"]
    )
    assert all(
        cell["replay_validated"] is True
        and cell["budget_status"] == "CAP_LIMITED"
        for cell in deterministic["ordered_stage2_cell_receipts"]
    )
    assert [
        selection["selected_learning_rate_decimal"]
        for selection in deterministic["selections"]
    ] == ["0.003", "0.001", "0.01"]
    assert deterministic["future_confirmatory_exclusion"]["required"] is True

    runtime = artifact["runtime_telemetry"]
    assert len(runtime["cell_runtime"]) == 54
    assert runtime["admission"]["admitted"] is True
    assert runtime["admission"]["projected_stage2_fit_and_replay_ns"] == (
        27 * 2_000_000 * 30
    )
    assert all(
        set(cell).issuperset(
            {
                "fit_elapsed_ns",
                "replay_elapsed_ns",
                "fit_and_replay_elapsed_ns",
                "peak_rss_kib_after",
                "exit_status",
            }
        )
        for cell in runtime["cell_runtime"]
    )


def test_runtime_nonadmission_stops_after_stage1_without_selection_or_rerun() -> None:
    dependencies, split_calls, fit_calls, replay_calls = _dependencies(
        step_ns=10_000_000_000
    )
    artifact = pilot.run_pilot(**dependencies)

    assert artifact["terminal_status"] == pilot.TERMINAL_VOID
    assert artifact["runtime_telemetry"]["reason_code"] == (
        "STAGE2_RUNTIME_ADMISSION_REJECTED"
    )
    assert artifact["runtime_telemetry"]["admission"]["admitted"] is False
    assert len(fit_calls) == len(replay_calls) == 27
    assert all(call[0] == 10 for call in fit_calls)
    assert artifact["deterministic_receipt"]["selections"] == []
    assert artifact["deterministic_receipt"]["selection_status"] == (
        pilot.NO_SELECTION
    )
    assert split_calls == [
        (draw, split) for draw in (0, 1, 2) for split in ("train", "dev")
    ]


def test_replay_byte_mismatch_fails_once_without_retry_or_selection() -> None:
    dependencies, _, fit_calls, replay_calls = _dependencies(replay_mismatch_at=1)
    artifact = pilot.run_pilot(**dependencies)

    assert artifact["terminal_status"] == pilot.TERMINAL_VOID
    assert len(fit_calls) == len(replay_calls) == 1
    assert artifact["deterministic_receipt"]["selections"] == []
    failure = artifact["runtime_telemetry"]["cell_runtime"][-1]
    assert failure["exit_status"] == "ERROR"
    assert failure["error_message"] == "replay parameter bytes mismatch"


def test_task_telemetry_failure_preserves_last_valid_artifact_prefix() -> None:
    def fail_peak_rss() -> int:
        raise RuntimeError("task RSS unavailable")

    artifact = pilot.run_pilot(
        clock_ns=StepClock(),
        peak_rss_kib=fail_peak_rss,
        environment=pilot.numeric_environment_payload(),
    )

    assert artifact["terminal_status"] == pilot.TERMINAL_VOID
    assert artifact["deterministic_receipt"]["ordered_task_bindings"] == []
    assert artifact["runtime_telemetry"]["task_preparation_runtime"] == []
    assert artifact["runtime_telemetry"]["error"]["message"] == (
        "task RSS unavailable"
    )
    assert pilot.validate_pilot_artifact(artifact) == artifact


def test_cell_telemetry_failure_does_not_publish_unpaired_cell() -> None:
    calls = 0

    def fail_on_cell_peak_rss() -> int:
        nonlocal calls
        calls += 1
        if calls <= len(pilot.TASK_DRAW_INDICES):
            return 12_345
        raise RuntimeError("cell RSS unavailable")

    def fit(task, train, dev, *, arm, config):
        assert train and dev
        optimization = FakeOptimization(
            key=(task.draw_index, arm.value, config.learning_rate.hex()),
            config=config,
            initial_dev_loss=1.0,
            best_dev_loss=0.9,
        )
        return FakeModel(
            arm=arm,
            config=config,
            optimization=optimization,
            parameter_value=1.0,
        )

    artifact = pilot.run_pilot(
        fitter=fit,
        replayer=lambda model: model.replay_copy(),
        clock_ns=StepClock(),
        peak_rss_kib=fail_on_cell_peak_rss,
        environment=pilot.numeric_environment_payload(),
    )

    deterministic = artifact["deterministic_receipt"]
    runtime = artifact["runtime_telemetry"]
    assert deterministic["ordered_stage1_cell_receipts"] == []
    assert runtime["cell_runtime"] == []
    assert runtime["error"]["message"] == "cell RSS unavailable"
    assert pilot.validate_pilot_artifact(artifact) == artifact


def test_baseline_drift_voids_only_after_complete_fresh_grid() -> None:
    dependencies, _, fit_calls, replay_calls = _dependencies(
        baseline_mismatch=(0, "P_CAP18", "0.003")
    )
    artifact = pilot.run_pilot(**dependencies)

    assert len(fit_calls) == len(replay_calls) == 54
    assert artifact["terminal_status"] == pilot.TERMINAL_VOID
    assert artifact["runtime_telemetry"]["error"]["message"] == (
        "epoch-zero dev loss drifted within a task"
    )
    assert artifact["deterministic_receipt"]["selections"] == []


def test_exact_selector_uses_mean_then_max_then_numeric_rate_only() -> None:
    dependencies, _, _, _ = _dependencies()
    artifact = pilot.run_pilot(**dependencies)
    cells = [
        dict(cell)
        for cell in artifact["deterministic_receipt"][
            "ordered_stage2_cell_receipts"
        ]
    ]
    ratios = {
        "0.001": (0.0, 0.5, 1.0),
        "0.003": (0.5, 0.5, 0.5),
        "0.01": (0.5, 0.5, 0.5),
    }
    for cell in cells:
        draw = cell["draw_index"]
        ratio = ratios[cell["learning_rate_decimal"]][draw]
        baseline = float.fromhex(cell["epoch_zero_dev_loss_hex"])
        best = baseline * ratio
        cell["best_dev_loss_hex"] = best.hex()
        cell["z_exact"] = pilot._fraction_payload(
            pilot.Fraction.from_float(best) / pilot.Fraction.from_float(baseline)
        )
        cell["optimization_receipt"] = dict(cell["optimization_receipt"])
        cell["optimization_receipt"]["best_dev_loss_hex"] = best.hex()
        _rehash_cell(cell)

    selections = pilot._select_validated_learning_rates(cells)
    assert [item["selected_learning_rate_decimal"] for item in selections] == [
        "0.003",
        "0.003",
        "0.003",
    ]


def test_cell_parser_rejects_aliases_and_noncanonical_binary64(
    strict_stage1_cell: dict[str, object],
) -> None:
    for field, value, match in (
        ("draw_index", False, "roster identity"),
        ("roster_index", False, "roster identity"),
        ("learning_rate_binary64_hex", "0x1p-10", "roster identity"),
    ):
        forged = copy.deepcopy(strict_stage1_cell)
        forged[field] = value
        _rehash_cell(forged)
        with pytest.raises(pilot.SWM0WS2SPilotError, match=match):
            pilot._validate_cell_prefix([forged], stage=pilot.STAGE1_NAME)

    with pytest.raises(
        pilot.SWM0WS2SPilotError, match="exact string mapping keys"
    ):
        pilot.canonical_json({1: "collision", "1": "other"})


def test_cell_parser_accepts_sanitized_stage1_and_reconstructs_stage2_receipt(
    strict_stage1_cell: dict[str, object],
    strict_stage2_cell: dict[str, object],
) -> None:
    pilot._validate_cell_prefix([strict_stage1_cell], stage=pilot.STAGE1_NAME)
    pilot._validate_cell_prefix([strict_stage2_cell], stage=pilot.STAGE2_NAME)


@pytest.mark.parametrize(
    ("mutation", "match"),
    (
        ("nested_receipt_sha", "optimization receipt is invalid"),
        ("best_train_nan", "best train loss"),
        ("best_train_negative_zero", "best train loss"),
        ("config_patience", "training config drifted"),
        ("task_manifest_and_rank_gains", "task spec drifted"),
        ("fitted_integer_alias", "cell fields drifted"),
        ("learned_integer_alias", "cell fields drifted"),
        ("best_update", "optimization receipt is invalid"),
        ("fake_termination", "optimization receipt is invalid"),
    ),
)
def test_deep_parser_rejects_self_rehashed_semantic_forgery(
    strict_stage2_cell: dict[str, object],
    mutation: str,
    match: str,
) -> None:
    forged = copy.deepcopy(strict_stage2_cell)
    optimization = forged["optimization_receipt"]
    assert type(optimization) is dict

    if mutation == "nested_receipt_sha":
        optimization["receipt_sha256"] = "f" * 64
        forged["optimization_receipt_sha256"] = "f" * 64
        _rehash_cell(forged)
    elif mutation == "best_train_nan":
        optimization["best_train_loss_hex"] = "nan"
        _rehash_optimization_and_cell(forged)
    elif mutation == "best_train_negative_zero":
        optimization["best_train_loss_hex"] = "-0x0.0p+0"
        _rehash_optimization_and_cell(forged)
    elif mutation == "config_patience":
        nested_config = optimization["config"]
        assert type(nested_config) is dict
        nested_config["patience"] = 999
        mirrored_config = forged["config"]
        assert type(mirrored_config) is dict
        mirrored_config["patience"] = 999
        _rehash_optimization_and_cell(forged)
    elif mutation == "task_manifest_and_rank_gains":
        nested_task = optimization["task_spec"]
        assert type(nested_task) is dict
        nested_task["manifest_sha256"] = "e" * 64
        rank_gains = nested_task["rank_gains"]
        assert type(rank_gains) is list
        assert type(rank_gains[0]) is dict
        rank_gains[0]["gain"] += 1
        optimization["task_manifest_sha256"] = "e" * 64
        mirrored_task = forged["task"]
        assert type(mirrored_task) is dict
        mirrored_task["manifest_sha256"] = "e" * 64
        mirrored_spec = mirrored_task["task_spec"]
        assert type(mirrored_spec) is dict
        mirrored_spec["manifest_sha256"] = "e" * 64
        mirrored_rank_gains = mirrored_spec["rank_gains"]
        assert type(mirrored_rank_gains) is list
        assert type(mirrored_rank_gains[0]) is dict
        mirrored_rank_gains[0]["gain"] += 1
        _rehash_optimization_and_cell(forged)
    elif mutation == "fitted_integer_alias":
        forged["fitted"] = 1
        _rehash_cell(forged)
    elif mutation == "learned_integer_alias":
        forged["learned"] = 0
        _rehash_cell(forged)
    elif mutation == "best_update":
        optimization["best_update"] = 1
        _rehash_optimization_and_cell(forged)
    elif mutation == "fake_termination":
        optimization["termination_reason"] = "MAX_UPDATES"
        forged["termination_reason"] = "MAX_UPDATES"
        forged["budget_status"] = "CAP_LIMITED"
        _rehash_optimization_and_cell(forged)
    else:  # pragma: no cover - the parameter roster above is closed.
        raise AssertionError(mutation)

    with pytest.raises(pilot.SWM0WS2SPilotError, match=match):
        pilot._validate_cell_prefix([forged], stage=pilot.STAGE2_NAME)


@pytest.mark.parametrize(
    "forged_fraction",
    (
        {"denominator": 1, "numerator": True},
        {"denominator": True, "numerator": 1},
        {"denominator": 0, "numerator": 1},
        {"denominator": 2, "numerator": 2},
    ),
)
def test_stage2_z_rejects_bool_alias_and_noncanonical_fraction(
    strict_stage2_cell: dict[str, object],
    forged_fraction: dict[str, object],
) -> None:
    forged = copy.deepcopy(strict_stage2_cell)
    forged["z_exact"] = forged_fraction
    _rehash_cell(forged)
    with pytest.raises(pilot.SWM0WS2SPilotError, match="fraction"):
        pilot._validate_cell_prefix([forged], stage=pilot.STAGE2_NAME)


def test_task_binding_parser_rejects_self_consistent_rank_gain_forgery(
    strict_stage2_cell: dict[str, object],
) -> None:
    binding = copy.deepcopy(strict_stage2_cell["task"])
    assert type(binding) is dict
    task_spec = binding["task_spec"]
    assert type(task_spec) is dict
    rank_gains = task_spec["rank_gains"]
    assert type(rank_gains) is list
    assert type(rank_gains[0]) is dict
    rank_gains[0]["gain"] += 1
    with pytest.raises(
        pilot.SWM0WS2SPilotError,
        match="differs from regenerated public task",
    ):
        pilot._validate_task_binding_list([binding])


def test_cli_requires_explicit_output_and_initializes_canonical_void(
    tmp_path: Path,
) -> None:
    with pytest.raises(SystemExit):
        pilot.main([])
    assert tuple(tmp_path.iterdir()) == ()

    output = tmp_path / "pilot.json"
    assert pilot.main(["--initialize-void", "--output", str(output)]) == 0
    raw = output.read_bytes()
    assert raw.endswith(b"\n")
    parsed = json.loads(raw)
    assert raw == (pilot.canonical_json(parsed) + "\n").encode("utf-8")
    assert pilot.parse_pilot_artifact_bytes(raw) == parsed
    assert parsed["terminal_status"] == pilot.TERMINAL_VOID
    assert parsed["deterministic_receipt"]["selections"] == []


def test_strict_parser_rejects_tamper_and_duplicate_keys() -> None:
    artifact = pilot.initial_void_artifact()
    assert pilot.validate_pilot_artifact(artifact) == artifact
    raw = (pilot.canonical_json(artifact) + "\n").encode("utf-8")
    assert pilot.parse_pilot_artifact_bytes(raw) == artifact

    forged = json.loads(raw)
    forged["deterministic_receipt"]["selection_status"] = "FORGED"
    with pytest.raises(pilot.SWM0WS2SPilotError, match="self-hash mismatch"):
        pilot.validate_pilot_artifact(forged)
    with pytest.raises(pilot.SWM0WS2SPilotError, match="duplicate key"):
        pilot.parse_pilot_artifact_bytes(b'{"x":1,"x":1}\n')


def test_runtime_parser_rejects_self_rehashed_reason_and_error_forgery() -> None:
    forged_reason = copy.deepcopy(pilot.initial_void_artifact())
    reason_runtime = forged_reason["runtime_telemetry"]
    assert type(reason_runtime) is dict
    reason_runtime["reason_code"] = "FORGED_REASON"
    _rehash_runtime_and_artifact(forged_reason)
    with pytest.raises(pilot.SWM0WS2SPilotError, match="identity drifted"):
        pilot.validate_pilot_artifact(forged_reason)

    forged_error = copy.deepcopy(pilot.initial_void_artifact())
    error_runtime = forged_error["runtime_telemetry"]
    assert type(error_runtime) is dict
    error_runtime["error"] = {"class": "Forged", "message": "forged"}
    _rehash_runtime_and_artifact(forged_error)
    with pytest.raises(
        pilot.SWM0WS2SPilotError,
        match="runtime reason and terminal error disagree",
    ):
        pilot.validate_pilot_artifact(forged_error)


@pytest.mark.parametrize(
    "reason_code",
    (
        "ENVIRONMENT_BOUND_RUN_IN_PROGRESS",
        "TASK_PREPARATION_IN_PROGRESS",
        f"{pilot.STAGE1_NAME}_IN_PROGRESS",
        "RUNTIME_ADMISSION_EVALUATED",
        f"{pilot.STAGE2_NAME}_IN_PROGRESS",
        "STAGE2_RUNTIME_ADMISSION_REJECTED",
        "FIXED_DEVELOPMENT_ROSTER_COMPLETE",
    ),
)
def test_runtime_parser_binds_every_reason_to_reachable_state(
    reason_code: str,
) -> None:
    forged = copy.deepcopy(pilot.initial_void_artifact())
    runtime = forged["runtime_telemetry"]
    assert type(runtime) is dict
    runtime["reason_code"] = reason_code
    _rehash_runtime_and_artifact(forged)
    with pytest.raises(
        pilot.SWM0WS2SPilotError,
        match="runtime reason does not match pilot state",
    ):
        pilot.validate_pilot_artifact(forged)


def test_runner_source_has_no_test_split_access() -> None:
    source = Path(pilot.__file__).read_text(encoding="utf-8")
    assert '.iter_cases("test")' not in source


def test_repository_manual_workflow_is_fixed_and_dispatch_only() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    workflow_path = (
        repository_root
        / ".github"
        / "workflows"
        / "swm0w-s2s-train-dev-pilot.yml"
    )
    if not workflow_path.is_file():
        pytest.skip("repository-only workflow is absent from the source distribution")
    workflow = workflow_path.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "push:" not in workflow
    assert "pull_request:" not in workflow
    assert "timeout-minutes: 180" in workflow
    assert 'PYTHON_VERSION: "3.11.15"' in workflow
    assert "Materialize the exact pilot Python" in workflow
    assert 'uv python install --managed-python "$PYTHON_VERSION"' in workflow
    assert workflow.index(
        'uv python install --managed-python "$PYTHON_VERSION"'
    ) < workflow.index(
        'pilot_python="$(uv python find --managed-python "$PYTHON_VERSION")"'
    )
    assert "Reject duplicate dispatches for this commit" in workflow
    assert "head_sha=$GITHUB_SHA" in workflow
    assert 'uv sync --locked --managed-python --python "$PYTHON_VERSION"' in workflow
    assert (
        'uv run --locked --managed-python --python "$PYTHON_VERSION"'
        in workflow
    )
    assert "python -m hswm.experiments.swm0w_s2s_pilot" in workflow
    assert "if: ${{ always() }}" in workflow
    assert "test" not in workflow.lower()
