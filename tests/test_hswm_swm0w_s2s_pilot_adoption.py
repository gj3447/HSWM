from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from io import BytesIO
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import pytest

from hswm.experiments import swm0w_s2s_pilot as pilot
from hswm.experiments import swm0w_s2s_pilot_adoption as adoption
from hswm.experiments import swm0w_s2s_protocol as protocol
from hswm.experiments import swm0w_s2s_training as training
from hswm.experiments.swm0w_s2s_operator import (
    ALL_ARMS,
    S2SArm,
    architecture_receipt,
)


SOURCE_COMMIT = "a" * 40
RUN_ID = 9_876_543_210


def _sha(*parts: object) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode("ascii")).hexdigest()


def _environment() -> dict[str, object]:
    return {
        "blas": {
            "name": "fixture-blas",
            "openblas_configuration": "fixture-openblas",
            "version": "fixture-version",
        },
        "byteorder": "little",
        "cpu": {
            "flags": None,
            "machine": "x86_64",
            "model_name": "fixture-cpu",
            "vendor_id": "fixture-vendor",
        },
        "numpy_version": "fixture-numpy",
        "platform_release": "fixture-linux-release",
        "platform_system": "Linux",
        "python_implementation": "CPython",
        "python_version": pilot.WORKFLOW_PYTHON_VERSION,
        "runner_arch": "X64",
        "runner_os": "Linux",
        "simd": {"baseline": [], "found": [], "not_found": []},
        "source_commit": SOURCE_COMMIT,
        "thread_environment": dict(pilot.WORKFLOW_FIXED_ENVIRONMENT),
    }


def _stage1_cell(
    *,
    roster_index: int,
    draw_index: int,
    public_arm: str,
    learning_rate_label: str,
    task_binding: dict[str, object],
) -> dict[str, object]:
    key = pilot._cell_key(
        roster_index, draw_index, public_arm, learning_rate_label
    )
    payload = {
        "config": pilot._config_for(
            pilot.STAGE1_MAX_UPDATES, learning_rate_label
        ).canonical(),
        "draw_index": draw_index,
        "learning_rate_binary64_hex": key["learning_rate_binary64_hex"],
        "learning_rate_decimal": learning_rate_label,
        "model_state_sha256": _sha("stage1-state", roster_index),
        "operator_arm": key["operator_arm"],
        "optimization_receipt_sha256": _sha(
            "stage1-optimization", roster_index
        ),
        "parameters_sha256": _sha("stage1-parameters", roster_index),
        "public_arm": public_arm,
        "roster_index": roster_index,
        "runner_replay_observed": True,
        "schema_version": pilot.THROUGHPUT_CELL_RECEIPT_VERSION,
        "stage": pilot.STAGE1_NAME,
        "task": pilot._opaque_task_binding(task_binding),
        "telemetry_only": True,
    }
    return pilot._with_sha256(payload, "cell_receipt_sha256")


def _stage2_model(
    *, task: object, arm: S2SArm, learning_rate_label: str
) -> training.LearnedS2SOperator:
    config = pilot._config_for(
        pilot.STAGE2_MAX_UPDATES, learning_rate_label
    )
    data = training._compiled_task_data(task)
    parameters = training._training_initial_parameters(arm, config.seed)
    parameter_sha = training._parameter_sha256(arm, parameters)
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
            parameters_sha256=parameter_sha,
        ),
        *(
            training.OptimizationHistoryEntry(
                update=update,
                train_loss=train_loss,
                dev_loss=dev_loss,
                gradient_norm=0.0,
                clipped=False,
                improved=False,
                parameters_sha256=parameter_sha,
            )
            for update in range(1, pilot.PATIENCE + 1)
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
        "initial_parameters_sha256": parameter_sha,
        "best_parameters_sha256": parameter_sha,
        "best_update": 0,
        "stopped_update": pilot.PATIENCE,
        "best_train_loss": train_loss,
        "best_dev_loss": dev_loss,
        "update_count": pilot.PATIENCE,
        "clipped_update_count": 0,
        "history": history,
        "history_entry_count": len(history),
        "history_sha256": training._history_sha256(history),
        "termination_reason": training.TerminationReason.PATIENCE,
    }
    receipt = training.S2SOptimizationReceipt(
        **values,
        receipt_sha256=training.canonical_sha256(
            training._optimization_unsigned_payload(values)
        ),
    )
    return training.LearnedS2SOperator(
        arm=arm,
        config=config,
        parameters=parameters,
        optimization=receipt,
    )


def _complete_pilot_artifact() -> dict[str, object]:
    tasks = tuple(
        pilot._expected_public_task(draw_index)
        for draw_index in pilot.TASK_DRAW_INDICES
    )
    task_bindings = tuple(pilot._task_binding(task) for task in tasks)
    stage1: list[dict[str, object]] = []
    stage2: list[dict[str, object]] = []
    for roster_index, (
        draw_index,
        public_arm,
        learning_rate_label,
    ) in enumerate(pilot.fixed_roster()):
        task_binding = task_bindings[draw_index]
        stage1.append(
            _stage1_cell(
                roster_index=roster_index,
                draw_index=draw_index,
                public_arm=public_arm,
                learning_rate_label=learning_rate_label,
                task_binding=task_binding,
            )
        )
        operator_arm = S2SArm(pilot.PUBLIC_TO_OPERATOR_ARM[public_arm])
        model = _stage2_model(
            task=tasks[draw_index],
            arm=operator_arm,
            learning_rate_label=learning_rate_label,
        )
        stage2.append(
            pilot._full_cell_record(
                model,
                task_binding=task_binding,
                cell_key=pilot._cell_key(
                    roster_index,
                    draw_index,
                    public_arm,
                    learning_rate_label,
                ),
            )
        )
    selections = pilot.select_learning_rates(stage2)
    deterministic = pilot._deterministic_receipt(
        environment=_environment(),
        task_bindings=task_bindings,
        stage1_cells=stage1,
        stage2_cells=stage2,
        selections=selections,
    )
    runtime_cells = [
        pilot._runtime_cell(
            stage=stage,
            cell_key=pilot._cell_key(
                roster_index,
                draw_index,
                public_arm,
                learning_rate_label,
            ),
            fit_elapsed_ns=1,
            replay_elapsed_ns=1,
            peak_rss_kib=1,
            exit_status="COMPLETED",
        )
        for stage in (pilot.STAGE1_NAME, pilot.STAGE2_NAME)
        for roster_index, (
            draw_index,
            public_arm,
            learning_rate_label,
        ) in enumerate(pilot.fixed_roster())
    ]
    stage1_elapsed = pilot.EXPECTED_CELL_COUNT * 2
    runtime = pilot._runtime_report(
        terminal_status=pilot.TERMINAL_COMPLETE,
        reason_code="FIXED_DEVELOPMENT_ROSTER_COMPLETE",
        task_preparation=tuple(
            {
                "draw_index": draw_index,
                "elapsed_ns": 1,
                "peak_rss_kib_after": 1,
            }
            for draw_index in pilot.TASK_DRAW_INDICES
        ),
        cell_runtime=runtime_cells,
        admission={
            "admitted": True,
            "admission_limit_ns": pilot.ADMISSION_LIMIT_NS,
            "integer_projection_multiplier": pilot.PROJECTION_MULTIPLIER,
            "projected_stage2_fit_and_replay_ns": (
                stage1_elapsed * pilot.PROJECTION_MULTIPLIER
            ),
            "stage1_fit_and_replay_elapsed_ns_sum": stage1_elapsed,
        },
    )
    artifact = pilot._artifact(deterministic, runtime)
    assert pilot.validate_pilot_artifact(artifact) == artifact
    return artifact


def _zip_member(
    member: bytes,
    *,
    extra_member: bool = False,
    compression: int = ZIP_STORED,
) -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w", compression=compression) as archive:
        archive.writestr(adoption.EXPECTED_ARTIFACT_MEMBER, member)
        if extra_member:
            archive.writestr("unexpected.txt", b"unexpected")
    return stream.getvalue()


def _artifact_bytes(value: dict[str, object]) -> bytes:
    return (pilot.canonical_json(value) + "\n").encode("utf-8")


def _evidence(archive_bytes: bytes):
    run = {
        "conclusion": "success",
        "event": adoption.EXPECTED_EVENT,
        "head_branch": adoption.EXPECTED_BRANCH,
        "head_sha": SOURCE_COMMIT,
        "id": RUN_ID,
        "name": adoption.EXPECTED_WORKFLOW_NAME,
        "path": adoption.EXPECTED_WORKFLOW_PATH,
        "repository": adoption.EXPECTED_REPOSITORY,
        "run_attempt": 1,
        "status": "completed",
    }
    job = {
        "completed_at": "2026-08-21T03:00:00Z",
        "conclusion": "success",
        "head_sha": SOURCE_COMMIT,
        "id": 9_001,
        "labels": [pilot.WORKFLOW_RUNNER_IMAGE],
        "name": adoption.EXPECTED_JOB_NAME,
        "run_attempt": 1,
        "run_id": RUN_ID,
        "started_at": "2026-08-21T02:00:00Z",
        "status": "completed",
    }
    artifact = {
        "created_at": "2026-08-21T03:00:00Z",
        "digest": f"sha256:{hashlib.sha256(archive_bytes).hexdigest()}",
        "expired": False,
        "expires_at": "2026-11-19T03:00:00Z",
        "id": 8_001,
        "name": f"swm0w-s2s-train-dev-pilot-{RUN_ID}-1",
        "size_in_bytes": len(archive_bytes),
        "workflow_run": {"head_sha": SOURCE_COMMIT, "id": RUN_ID},
    }
    return run, job, artifact


@dataclass(frozen=True)
class Bundle:
    archive_bytes: bytes
    run: dict[str, object]
    job: dict[str, object]
    artifact: dict[str, object]
    receipt: adoption.PilotAdoptionReceiptV1


@pytest.fixture(scope="module")
def complete_bundle() -> Bundle:
    archive_bytes = _zip_member(_artifact_bytes(_complete_pilot_artifact()))
    run, job, artifact = _evidence(archive_bytes)
    receipt = adoption.build_pilot_adoption_receipt(
        pilot_artifact_zip_bytes=archive_bytes,
        github_run=run,
        github_job=job,
        github_artifact=artifact,
    )
    return Bundle(archive_bytes, run, job, artifact, receipt)


def _kwargs(bundle: Bundle) -> dict[str, object]:
    return {
        "pilot_artifact_zip_bytes": bundle.archive_bytes,
        "github_run": bundle.run,
        "github_job": bundle.job,
        "github_artifact": bundle.artifact,
    }


def _rehash_receipt(value: dict[str, object]) -> None:
    unsigned = dict(value)
    unsigned.pop("receipt_sha256")
    value["receipt_sha256"] = adoption.canonical_sha256(unsigned)


def test_complete_artifact_derives_three_configs_and_exact_exclusion(
    complete_bundle: Bundle,
) -> None:
    receipt = complete_bundle.receipt
    assert receipt.source_commit == SOURCE_COMMIT
    assert receipt.github_run.run_attempt == 1
    assert receipt.archive.member_name == "pilot.json"
    assert receipt.archive.member_sha256 == receipt.pilot_artifact_bytes_sha256
    assert tuple(row.operator_arm for row in receipt.selected_configs) == ALL_ARMS
    assert tuple(
        row.learning_rate_decimal for row in receipt.selected_configs
    ) == ("0.001", "0.001", "0.001")
    assert receipt.protocol_config.arm_configs == tuple(
        (row.operator_arm, row.config) for row in receipt.selected_configs
    )
    assert receipt.protocol_config.excluded_task_provenance == (
        (pilot.EXPECTED_SEED_COMMITMENT_SHA256, (0, 1, 2)),
    )
    assert pilot.EXPECTED_SEED_COMMITMENT_SHA256 != (
        pilot.EXTERNAL_SEED_SHA256_HEX
    )
    canonical = receipt.canonical()
    assert canonical["pilot"]["stage2_replay_validated_count"] == 27
    assert canonical["claim_boundary"] == adoption.CLAIM_BOUNDARY
    assert canonical["verdict"] == adoption.VERDICT
    assert canonical["github_evidence"]["assurance"] == (
        adoption.GITHUB_EVIDENCE_ASSURANCE
    )


def test_runtime_summary_is_exact_telemetry_only_projection(
    complete_bundle: Bundle,
) -> None:
    summary = complete_bundle.receipt.runtime_summary
    with ZipFile(BytesIO(complete_bundle.archive_bytes), "r") as archive:
        pilot_bytes = archive.read(adoption.EXPECTED_ARTIFACT_MEMBER)
    parsed_pilot = pilot.parse_pilot_artifact_bytes(pilot_bytes)
    assert summary.runtime_telemetry_sha256 == parsed_pilot[
        "runtime_telemetry"
    ]["runtime_telemetry_sha256"]
    assert summary.admitted is True
    assert summary.admission_limit_ns == pilot.ADMISSION_LIMIT_NS
    assert summary.projection_multiplier == pilot.PROJECTION_MULTIPLIER
    assert summary.admission_stage1_total_ns == 54
    assert summary.projected_stage2_fit_and_replay_ns == 1_620
    assert (
        summary.task_preparation_count,
        summary.task_preparation_total_ns,
        summary.task_preparation_max_ns,
    ) == (3, 3, 1)
    assert (
        summary.stage1_cell_count,
        summary.stage1_fit_ns,
        summary.stage1_replay_ns,
        summary.stage1_total_ns,
    ) == (27, 27, 27, 54)
    assert (
        summary.stage2_cell_count,
        summary.stage2_fit_ns,
        summary.stage2_replay_ns,
        summary.stage2_total_ns,
    ) == (27, 27, 27, 54)
    assert (
        summary.selected_rate_stage2_cell_count,
        summary.selected_rate_stage2_fit_ns,
        summary.selected_rate_stage2_replay_ns,
        summary.selected_rate_stage2_total_ns,
    ) == (9, 9, 9, 18)
    assert summary.max_peak_rss_kib == 1
    assert summary.github_job_elapsed_seconds == 3_600
    assert summary.archive_size_in_bytes == len(complete_bundle.archive_bytes)
    assert summary.member_size_in_bytes == len(pilot_bytes)
    canonical = summary.canonical()
    assert canonical["summary_role"] == adoption.RUNTIME_SUMMARY_ROLE
    assert canonical["prereg_resource_policy_status"] == (
        adoption.PREREG_RESOURCE_POLICY_STATUS
    )
    assert "timeout" not in adoption.canonical_json(canonical).lower()
    assert "rss_limit" not in adoption.canonical_json(canonical).lower()


def test_canonical_receipt_round_trips_only_with_exact_source_evidence(
    complete_bundle: Bundle,
) -> None:
    raw = adoption.canonical_receipt_bytes(
        complete_bundle.receipt, **_kwargs(complete_bundle)
    )
    parsed = adoption.parse_pilot_adoption_receipt_bytes(
        raw, **_kwargs(complete_bundle)
    )
    assert parsed == complete_bundle.receipt
    assert raw == (
        adoption.canonical_json(complete_bundle.receipt.canonical()) + "\n"
    ).encode("utf-8")


def test_run_not_completed_void_artifact_is_never_adoptable() -> None:
    archive_bytes = _zip_member(_artifact_bytes(pilot.initial_void_artifact()))
    run, job, artifact = _evidence(archive_bytes)
    with pytest.raises(
        adoption.SWM0WS2SPilotAdoptionError,
        match="only DEVELOPMENT_COMPLETE",
    ):
        adoption.build_pilot_adoption_receipt(
            pilot_artifact_zip_bytes=archive_bytes,
            github_run=run,
            github_job=job,
            github_artifact=artifact,
        )


@pytest.mark.parametrize(
    ("source", "field", "value", "match"),
    (
        ("run", "id", True, "exact integer"),
        ("run", "run_attempt", True, "exact integer"),
        ("run", "head_branch", "dev", "identity"),
        ("run", "path", "other.yml", "identity"),
        ("run", "event", "push", "identity"),
        ("run", "conclusion", "failure", "identity"),
        ("job", "id", True, "exact integer"),
        ("job", "run_attempt", True, "exact integer"),
        ("job", "conclusion", "failure", "identity"),
        ("artifact", "id", True, "exact integer"),
        ("artifact", "size_in_bytes", True, "exact integer"),
        ("artifact", "expired", 0, "exact bool"),
    ),
)
def test_api_evidence_rejects_bool_aliases_and_identity_drift(
    complete_bundle: Bundle,
    source: str,
    field: str,
    value: object,
    match: str,
) -> None:
    run = copy.deepcopy(complete_bundle.run)
    job = copy.deepcopy(complete_bundle.job)
    artifact = copy.deepcopy(complete_bundle.artifact)
    target = {"run": run, "job": job, "artifact": artifact}[source]
    target[field] = value
    with pytest.raises(adoption.SWM0WS2SPilotAdoptionError, match=match):
        adoption.build_pilot_adoption_receipt(
            pilot_artifact_zip_bytes=complete_bundle.archive_bytes,
            github_run=run,
            github_job=job,
            github_artifact=artifact,
        )


@pytest.mark.parametrize("source", ("run", "job", "artifact"))
def test_api_evidence_rejects_extra_keys(
    complete_bundle: Bundle, source: str
) -> None:
    run = copy.deepcopy(complete_bundle.run)
    job = copy.deepcopy(complete_bundle.job)
    artifact = copy.deepcopy(complete_bundle.artifact)
    target = {"run": run, "job": job, "artifact": artifact}[source]
    target["unexpected"] = "forbidden"
    with pytest.raises(adoption.SWM0WS2SPilotAdoptionError, match="keys drifted"):
        adoption.build_pilot_adoption_receipt(
            pilot_artifact_zip_bytes=complete_bundle.archive_bytes,
            github_run=run,
            github_job=job,
            github_artifact=artifact,
        )


def test_job_projection_rejects_self_hosted_or_extra_runner_labels(
    complete_bundle: Bundle,
) -> None:
    for labels in (
        ["self-hosted", pilot.WORKFLOW_RUNNER_IMAGE],
        [pilot.WORKFLOW_RUNNER_IMAGE, "unexpected"],
    ):
        job = copy.deepcopy(complete_bundle.job)
        job["labels"] = labels
        with pytest.raises(
            adoption.SWM0WS2SPilotAdoptionError,
            match="runner",
        ):
            adoption.build_pilot_adoption_receipt(
                pilot_artifact_zip_bytes=complete_bundle.archive_bytes,
                github_run=complete_bundle.run,
                github_job=job,
                github_artifact=complete_bundle.artifact,
            )


def test_source_commit_cross_binding_rejects_consistent_looking_api_drift(
    complete_bundle: Bundle,
) -> None:
    run = copy.deepcopy(complete_bundle.run)
    run["head_sha"] = "b" * 40
    with pytest.raises(
        adoption.SWM0WS2SPilotAdoptionError,
        match="environment drifted",
    ):
        adoption.build_pilot_adoption_receipt(
            pilot_artifact_zip_bytes=complete_bundle.archive_bytes,
            github_run=run,
            github_job=complete_bundle.job,
            github_artifact=complete_bundle.artifact,
        )


def test_zip_and_artifact_api_bind_exact_archive_and_member_bytes(
    complete_bundle: Bundle,
) -> None:
    artifact = copy.deepcopy(complete_bundle.artifact)
    artifact["digest"] = "sha256:" + "0" * 64
    with pytest.raises(adoption.SWM0WS2SPilotAdoptionError, match="exact ZIP"):
        adoption.build_pilot_adoption_receipt(
            pilot_artifact_zip_bytes=complete_bundle.archive_bytes,
            github_run=complete_bundle.run,
            github_job=complete_bundle.job,
            github_artifact=artifact,
        )

    member = _artifact_bytes(pilot.initial_void_artifact())
    extra_archive = _zip_member(member, extra_member=True)
    run, job, artifact = _evidence(extra_archive)
    with pytest.raises(adoption.SWM0WS2SPilotAdoptionError, match="exactly pilot.json"):
        adoption.build_pilot_adoption_receipt(
            pilot_artifact_zip_bytes=extra_archive,
            github_run=run,
            github_job=job,
            github_artifact=artifact,
        )

    noncanonical_archive = _zip_member(b" " + member)
    run, job, artifact = _evidence(noncanonical_archive)
    with pytest.raises(adoption.SWM0WS2SPilotAdoptionError, match="strict artifact"):
        adoption.build_pilot_adoption_receipt(
            pilot_artifact_zip_bytes=noncanonical_archive,
            github_run=run,
            github_job=job,
            github_artifact=artifact,
        )

    with ZipFile(BytesIO(complete_bundle.archive_bytes), "r") as original:
        complete_member = original.read(adoption.EXPECTED_ARTIFACT_MEMBER)
    deflated_archive = _zip_member(complete_member, compression=ZIP_DEFLATED)
    run, job, artifact = _evidence(deflated_archive)
    deflated = adoption.build_pilot_adoption_receipt(
        pilot_artifact_zip_bytes=deflated_archive,
        github_run=run,
        github_job=job,
        github_artifact=artifact,
    )
    assert deflated.archive.compression == "ZIP_DEFLATED"


def test_receipt_parser_rejects_duplicate_noncanonical_and_extra_keys(
    complete_bundle: Bundle,
) -> None:
    raw = adoption.canonical_receipt_bytes(
        complete_bundle.receipt, **_kwargs(complete_bundle)
    )
    duplicate = raw.replace(
        b'{"adoption_status":',
        b'{"adoption_status":"FORGED","adoption_status":',
        1,
    )
    with pytest.raises(adoption.SWM0WS2SPilotAdoptionError, match="duplicate key"):
        adoption.parse_pilot_adoption_receipt_bytes(
            duplicate, **_kwargs(complete_bundle)
        )
    with pytest.raises(adoption.SWM0WS2SPilotAdoptionError, match="canonical"):
        adoption.parse_pilot_adoption_receipt_bytes(
            b" " + raw, **_kwargs(complete_bundle)
        )

    extra = copy.deepcopy(complete_bundle.receipt.canonical())
    extra["unexpected"] = "forbidden"
    _rehash_receipt(extra)
    with pytest.raises(adoption.SWM0WS2SPilotAdoptionError, match="exactly replay"):
        adoption.parse_pilot_adoption_receipt_bytes(
            (adoption.canonical_json(extra) + "\n").encode("utf-8"),
            **_kwargs(complete_bundle),
        )


def test_receipt_parser_rejects_bool_alias_and_self_rehashed_seed_confusion(
    complete_bundle: Bundle,
) -> None:
    bool_alias = copy.deepcopy(complete_bundle.receipt.canonical())
    bool_alias["pilot"]["stage2_cell_count"] = True
    _rehash_receipt(bool_alias)
    with pytest.raises(adoption.SWM0WS2SPilotAdoptionError, match="exactly replay"):
        adoption.parse_pilot_adoption_receipt_bytes(
            (adoption.canonical_json(bool_alias) + "\n").encode("utf-8"),
            **_kwargs(complete_bundle),
        )

    forged = copy.deepcopy(complete_bundle.receipt.canonical())
    forged["pilot"]["task_seed_commitment_sha256"] = (
        pilot.EXTERNAL_SEED_SHA256_HEX
    )
    config = forged["protocol_config_projection"]
    config["excluded_task_provenance"][0]["seed_commitment_sha256"] = (
        pilot.EXTERNAL_SEED_SHA256_HEX
    )
    config_unsigned = dict(config)
    config_unsigned.pop("receipt_sha256")
    config["receipt_sha256"] = protocol.canonical_sha256(config_unsigned)
    _rehash_receipt(forged)
    with pytest.raises(adoption.SWM0WS2SPilotAdoptionError, match="exactly replay"):
        adoption.parse_pilot_adoption_receipt_bytes(
            (adoption.canonical_json(forged) + "\n").encode("utf-8"),
            **_kwargs(complete_bundle),
        )


@pytest.mark.parametrize(
    ("section", "field"),
    (
        ("admission", "projected_stage2_fit_and_replay_ns"),
        ("artifact_sizes", "archive_size_in_bytes"),
        ("selected_rate_stage2", "cell_count"),
        ("stage1", "fit_elapsed_ns_sum"),
        ("stage2", "replay_elapsed_ns_sum"),
        ("task_preparation", "elapsed_ns_sum"),
    ),
)
def test_runtime_summary_rejects_bool_aliases_after_self_rehash(
    complete_bundle: Bundle,
    section: str,
    field: str,
) -> None:
    forged = copy.deepcopy(complete_bundle.receipt.canonical())
    forged["runtime_telemetry_summary"][section][field] = True
    _rehash_receipt(forged)
    with pytest.raises(adoption.SWM0WS2SPilotAdoptionError, match="exactly replay"):
        adoption.parse_pilot_adoption_receipt_bytes(
            (adoption.canonical_json(forged) + "\n").encode("utf-8"),
            **_kwargs(complete_bundle),
        )


def test_runtime_summary_rejects_tamper_extra_key_and_self_rehashed_sha(
    complete_bundle: Bundle,
) -> None:
    for mutation in ("runtime_sha", "extra_key"):
        forged = copy.deepcopy(complete_bundle.receipt.canonical())
        summary = forged["runtime_telemetry_summary"]
        if mutation == "runtime_sha":
            summary["runtime_telemetry_sha256"] = "f" * 64
        else:
            summary["unexpected_resource_policy"] = "FORBIDDEN"
        _rehash_receipt(forged)
        with pytest.raises(
            adoption.SWM0WS2SPilotAdoptionError,
            match="exactly replay",
        ):
            adoption.parse_pilot_adoption_receipt_bytes(
                (adoption.canonical_json(forged) + "\n").encode("utf-8"),
                **_kwargs(complete_bundle),
            )


def test_receipt_constructor_and_dataclass_replace_cannot_bypass_evidence(
    complete_bundle: Bundle,
) -> None:
    with pytest.raises(
        adoption.SWM0WS2SPilotAdoptionError,
        match="evidence-replaying APIs",
    ):
        adoption.PilotAdoptionReceiptV1()
    with pytest.raises((TypeError, ValueError)):
        replace(
            complete_bundle.receipt,
            pilot_artifact_self_sha256="f" * 64,
            receipt_sha256="e" * 64,
        )

    mismatched_run = copy.deepcopy(complete_bundle.run)
    mismatched_run["id"] += 1
    with pytest.raises(adoption.SWM0WS2SPilotAdoptionError):
        adoption.canonical_receipt_bytes(
            complete_bundle.receipt,
            pilot_artifact_zip_bytes=complete_bundle.archive_bytes,
            github_run=mismatched_run,
            github_job=complete_bundle.job,
            github_artifact=complete_bundle.artifact,
        )


def test_adoption_surface_has_no_future_seed_network_dispatch_or_test_access() -> None:
    source = Path(adoption.__file__).read_text(encoding="utf-8")
    assert ".iter_cases(\"test\")" not in source
    assert "generate_task(" not in source
    assert "workflow_dispatch(" not in source
    assert "requests." not in source
    assert "urllib." not in source
    assert "socket." not in source
