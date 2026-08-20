from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile

import pytest

from hswm.experiments import swm0w_beacon as beacon
from hswm.experiments import swm0w_confirmatory as confirmatory
from hswm.experiments import swm0w_protocol as protocol
from hswm.experiments import swm0w_task_family as task_family
from hswm.experiments import swm0w_worlds as worlds


requires_drand_verifier = pytest.mark.skipif(
    not beacon.verifier_dependency_available(),
    reason="requires the byte-pinned installed drand-client verifier",
)


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    )
    return completed.stdout.strip()


def _rfc3339(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        for name in sorted(files):
            archive.writestr(name, files[name])
    return stream.getvalue()


def _synthetic_task_receipt(
    index: int,
    seed: bytes,
    *,
    task_material_seed: bytes | None = None,
    variance_override: protocol.ExactTestVariance | None = None,
) -> protocol.TaskReceipt:
    """A content-valid reducer fixture; it performs no model fitting."""

    task = task_family.build_task_from_external_seed(
        seed if task_material_seed is None else task_material_seed
    )
    task_uid = task.task_uid
    variance = (
        protocol.exact_test_variance(task)
        if variance_override is None
        else variance_override
    )
    requested = {
        "T16": 0.95,
        "P16": 0.75,
        "A16": 0.74,
        "R16": 0.73,
        "F16": 0.95,
        "D16": 0.94,
        "P17-cap": 0.75,
        "A21-cap": 0.74,
        "R64-cap": 0.73,
    }

    def digest(label: str, position: int) -> str:
        return sha256(f"{index}:{label}:{position}".encode()).hexdigest()

    arms: list[protocol.ArmResult] = []
    for position, spec in enumerate(protocol.ARM_SPECS):
        row_digest = digest("arm", position)
        mse = float((1.0 - requested[spec.spec_id]) * variance.population_variance)
        arms.append(
            protocol.ArmResult(
                spec_id=spec.spec_id,
                optimizer_seed=protocol.optimizer_seed_from_task_uid(task_uid),
                training_config_sha256=protocol.canonical_sha256(
                    protocol.CONFIRMATORY_OPTIMIZER.config(spec, task_uid).canonical()
                ),
                model_state_sha256=row_digest,
                optimization_receipt_sha256=row_digest,
                score_receipt_sha256=row_digest,
                predictions_sha256=row_digest,
                mean_squared_error=mse,
                test_r2=protocol.r_squared_from_mse(mse, variance),
            )
        )
    base_r2 = arms[0].test_r2
    heads: list[protocol.HeadResult] = []
    for position, head in enumerate(protocol.HEAD_SPECS):
        requested_damage = 0.20 if head.roles == worlds.ROLES else 0.10
        mse = float((1.0 - (base_r2 - requested_damage)) * variance.population_variance)
        r2 = protocol.r_squared_from_mse(mse, variance)
        row_digest = digest("head", position)
        heads.append(
            protocol.HeadResult(
                head=head,
                removal_receipt_sha256=row_digest,
                ablated_state_sha256=row_digest,
                restored_state_sha256=arms[0].model_state_sha256,
                restored_score_receipt_sha256=arms[0].score_receipt_sha256,
                restored_predictions_sha256=arms[0].predictions_sha256,
                score_receipt_sha256=row_digest,
                predictions_sha256=row_digest,
                ablated_mse=mse,
                ablated_r2=r2,
                damage=base_r2 - r2,
            )
        )
    cycle_mse = float((1.0 - (base_r2 - 0.20)) * variance.population_variance)
    cycle_r2 = protocol.r_squared_from_mse(cycle_mse, variance)
    metrics = protocol.metric_vector_from_measurements(
        {row.spec_id: row for row in arms}, cycle_r2, heads
    )
    task_sha = task.task_sha256
    parity_sha = digest("parity", 0)
    cycle_sha = digest("cycle", 0)
    optimizer_sha = protocol.canonical_sha256(
        protocol.CONFIRMATORY_OPTIMIZER.canonical()
    )
    unsigned = {
        "arm_results": [row.canonical() for row in arms],
        "exact_test_variance": variance.canonical(),
        "head_results": [row.canonical() for row in heads],
        "metrics": metrics.canonical(),
        "native_star_parity": {
            "exact": True,
            "receipt_sha256": parity_sha,
            "world_count": 15_625,
        },
        "optimizer_template": protocol.CONFIRMATORY_OPTIMIZER.canonical(),
        "optimizer_template_sha256": optimizer_sha,
        "role_cycle": {
            "mean_squared_error_hex": cycle_mse.hex(),
            "predictions_sha256": cycle_sha,
            "r2_hex": cycle_r2.hex(),
            "rule": protocol.ROLE_CYCLE_RULE,
            "score_receipt_sha256": cycle_sha,
        },
        "schema_version": protocol.TASK_RECEIPT_SCHEMA,
        "task_index": index,
        "task_sha256": task_sha,
        "task_seed_sha256": sha256(seed).hexdigest(),
        "task_uid": task_uid,
    }
    return protocol.TaskReceipt(
        task_index=index,
        task_uid=task_uid,
        task_sha256=task_sha,
        task_seed_sha256=sha256(seed).hexdigest(),
        optimizer_template=protocol.CONFIRMATORY_OPTIMIZER,
        optimizer_template_sha256=optimizer_sha,
        exact_variance=variance,
        arm_results=tuple(arms),
        native_star_world_count=15_625,
        native_star_parity_sha256=parity_sha,
        role_cycle_score_receipt_sha256=cycle_sha,
        role_cycle_predictions_sha256=cycle_sha,
        role_cycle_mse=cycle_mse,
        role_cycle_r2=cycle_r2,
        head_results=tuple(heads),
        metrics=metrics,
        receipt_sha256=protocol.canonical_sha256(unsigned),
    )


@dataclass(frozen=True)
class RegistrationFixture:
    root: Path
    prereg_bytes: bytes
    prereg: confirmatory.ValidatedPreregistrationV1
    carrier: confirmatory.RegistrationCarrierV1
    run: dict[str, object]
    workflow_runs: dict[str, object]
    jobs: dict[str, object]
    artifact: dict[str, object]
    archive: bytes
    archive_digest: str
    commit_a: str
    commit_b: str


@pytest.fixture()
def registration(tmp_path: Path) -> RegistrationFixture:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "fixture@example.invalid")
    _git(root, "config", "user.name", "Fixture")
    for relative in confirmatory.REQUIRED_SOURCE_PATHS:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((f"fixture:{relative}\n").encode())
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "source freeze A")
    commit_a = _git(root, "rev-parse", "HEAD")
    manifest = confirmatory.tracked_bytes_manifest(root, commit_a)
    paths = manifest.path_sha256()
    experiment_id = "SWM0W-TEST-CHRONOLOGY"
    core = {
        "schema_version": confirmatory.REGISTRATION_CORE_SCHEMA,
        "experiment_id": experiment_id,
        "claim_scope": confirmatory.CLAIM_SCOPE,
        "repository_binding": {
            "repository": confirmatory.EXPECTED_REPOSITORY,
            "ref": confirmatory.EXPECTED_REF,
            "source_commit_a": commit_a,
            "source_tree_oid": manifest.tree_oid,
            "tracked_bytes_manifest_sha256": manifest.manifest_sha256,
            "tracked_file_count": len(manifest.rows),
            "required_file_sha256": {
                path: paths[path] for path in confirmatory.REQUIRED_SOURCE_PATHS
            },
            "registration_commit_rule": confirmatory.REGISTRATION_COMMIT_RULE,
            "preregistration_path": confirmatory.PREREGISTRATION_PATH,
        },
        "workflow_binding": {
            "path": confirmatory.WORKFLOW_PATH,
            "sha256": paths[confirmatory.WORKFLOW_PATH],
            "trigger_event": confirmatory.EXPECTED_EVENT,
            "trigger_ref": confirmatory.EXPECTED_REF,
            "jobs": ["register", "confirm", "adjudicate"],
        },
        "protocol_contract": protocol.protocol_contract(),
        "execution_policy": {
            "task_count": beacon.TASK_COUNT,
            "task_indices": list(range(beacon.TASK_COUNT)),
            "single_process": True,
            "run_attempt": 1,
            "rerun_allowed": False,
            "reroll_allowed": False,
            "post_pulse_resume_allowed": False,
        },
        "chronology_policy": {
            "provider": confirmatory.CHRONOLOGY_PROVIDER,
            "minimum_declared_lead_seconds": confirmatory.MINIMUM_DECLARED_LEAD_SECONDS,
            "minimum_registration_artifact_lead_seconds": confirmatory.MINIMUM_ARTIFACT_LEAD_SECONDS,
            "maximum_declared_to_run_created_seconds": confirmatory.MAX_DECLARED_TO_RUN_CREATED_SECONDS,
            "claim": confirmatory.CHRONOLOGY_STATUS,
        },
        "runtime_binding": {
            "runner": confirmatory.RUNNER_LABEL,
            "runner_os": confirmatory.RUNNER_OS,
            "runner_arch": confirmatory.RUNNER_ARCH,
            "node_version": confirmatory.NODE_VERSION,
            "node_archive_sha256": confirmatory.NODE_ARCHIVE_SHA256,
            "node_executable_sha256": confirmatory.NODE_EXECUTABLE_SHA256,
            "runtime_trust_status": confirmatory.RUNTIME_TRUST_STATUS,
        },
    }
    core_sha = confirmatory.canonical_sha256(core)
    round_number = 1_000
    round_time = beacon.quicknet_round_time(round_number)
    commitment = beacon.make_future_round_commitment(
        experiment_id=experiment_id,
        registration_evidence_sha256=core_sha,
        registered_at_unix=round_time - 1_200,
        round_number=round_number,
    )
    unsigned = {
        "schema_version": confirmatory.PREREGISTRATION_SCHEMA,
        "registration_core": core,
        "registration_core_sha256": core_sha,
        "future_round_commitment": commitment.canonical(),
    }
    prereg_payload = {
        **unsigned,
        "preregistration_sha256": confirmatory.canonical_sha256(unsigned),
    }
    prereg_bytes = (confirmatory.canonical_json(prereg_payload) + "\n").encode()
    prereg_path = root / confirmatory.PREREGISTRATION_PATH
    prereg_path.parent.mkdir(parents=True)
    prereg_path.write_bytes(prereg_bytes)
    _git(root, "add", confirmatory.PREREGISTRATION_PATH)
    _git(root, "commit", "-q", "-m", "registration B")
    commit_b = _git(root, "rev-parse", "HEAD")
    prereg = confirmatory.validate_preregistration_bytes(prereg_bytes, repo_root=root)

    run_id = 1234
    run_created = commitment.registered_at_unix + 30
    run: dict[str, object] = {
        "id": run_id,
        "run_attempt": 1,
        "repository": {"full_name": confirmatory.EXPECTED_REPOSITORY},
        "head_repository": {"full_name": confirmatory.EXPECTED_REPOSITORY},
        "event": confirmatory.EXPECTED_EVENT,
        "head_branch": "main",
        "head_sha": commit_b,
        "path": confirmatory.WORKFLOW_PATH,
        "created_at": _rfc3339(run_created),
    }
    workflow_runs: dict[str, object] = {
        "total_count": 1,
        "workflow_runs": [json.loads(json.dumps(run))],
    }
    carrier = confirmatory.build_registration_carrier(
        prereg,
        repo_root=root,
        registration_commit_b=commit_b,
        github_run=run,
        github_workflow_runs=workflow_runs,
        expected_run_id=run_id,
    )
    archive = _zip_bytes(
        {
            "github_run.json": json.dumps(run).encode(),
            "github_workflow_runs.json": json.dumps(workflow_runs).encode(),
            "registration_carrier.json": (
                confirmatory.canonical_json(carrier.canonical()) + "\n"
            ).encode(),
        }
    )
    archive_digest = sha256(archive).hexdigest()
    artifact_id = 5678
    artifact: dict[str, object] = {
        "id": artifact_id,
        "name": confirmatory.registration_artifact_name(carrier),
        "digest": f"sha256:{archive_digest}",
        "expired": False,
        "size_in_bytes": len(archive),
        "created_at": _rfc3339(run_created + 20),
        "workflow_run": {"id": run_id, "head_sha": commit_b},
    }
    jobs: dict[str, object] = {
        "jobs": [
            {
                "id": 222,
                "name": "register",
                "run_id": run_id,
                "run_attempt": 1,
                "head_sha": commit_b,
                "status": "completed",
                "conclusion": "success",
                "started_at": _rfc3339(run_created + 1),
                "completed_at": _rfc3339(run_created + 25),
            }
        ]
    }
    return RegistrationFixture(
        root,
        prereg_bytes,
        prereg,
        carrier,
        run,
        workflow_runs,
        jobs,
        artifact,
        archive,
        archive_digest,
        commit_a,
        commit_b,
    )


def test_noncyclic_preregistration_and_exact_commit_pair(
    registration: RegistrationFixture,
) -> None:
    item = registration.prereg
    assert item.commitment.registration_evidence_sha256 == item.registration_core_sha256
    assert item.preregistration_sha256 != item.registration_core_sha256
    assert (
        confirmatory.validate_registration_commit_pair(
            item,
            repo_root=registration.root,
            registration_commit_b=registration.commit_b,
        )
        == registration.commit_b
    )
    with pytest.raises(TypeError):
        item.repository_binding["repository"] = "attacker/repo"  # type: ignore[index]
    indices = item.registration_core["execution_policy"]["task_indices"]
    assert type(indices) is tuple
    with pytest.raises(AttributeError):
        indices.append(20)  # type: ignore[attr-defined]


def test_exact_json_primitive_types_cannot_alias_bool_int_or_float(
    registration: RegistrationFixture,
) -> None:
    payload = json.loads(confirmatory.canonical_json(registration.prereg.payload))
    core = payload["registration_core"]
    core["execution_policy"]["run_attempt"] = True
    core_sha = confirmatory.canonical_sha256(core)
    old_commitment = registration.prereg.commitment
    commitment = beacon.make_future_round_commitment(
        experiment_id=registration.prereg.experiment_id,
        registration_evidence_sha256=core_sha,
        registered_at_unix=old_commitment.registered_at_unix,
        round_number=old_commitment.round,
    )
    unsigned = {
        "schema_version": confirmatory.PREREGISTRATION_SCHEMA,
        "registration_core": core,
        "registration_core_sha256": core_sha,
        "future_round_commitment": commitment.canonical(),
    }
    drifted = {
        **unsigned,
        "preregistration_sha256": confirmatory.canonical_sha256(unsigned),
    }
    with pytest.raises(confirmatory.SWM0WConfirmatoryError, match="exact JSON"):
        confirmatory.validate_preregistration_bytes(
            (confirmatory.canonical_json(drifted) + "\n").encode(),
            repo_root=registration.root,
        )

    carrier = registration.carrier.canonical()
    carrier["run_attempt"] = True
    carrier_unsigned = dict(carrier)
    del carrier_unsigned["carrier_sha256"]
    carrier["carrier_sha256"] = confirmatory.canonical_sha256(carrier_unsigned)
    with pytest.raises(confirmatory.SWM0WConfirmatoryError, match="integer"):
        confirmatory.parse_registration_carrier(carrier)

    run = json.loads(json.dumps(registration.run))
    run["run_attempt"] = True
    with pytest.raises(confirmatory.SWM0WConfirmatoryError, match="integer"):
        confirmatory.build_github_chronology_receipt(
            registration.prereg,
            registration.carrier,
            github_run=run,
            github_workflow_runs=registration.workflow_runs,
            github_jobs=registration.jobs,
            artifact=registration.artifact,
            downloaded_archive_bytes=registration.archive,
            expected_artifact_id=registration.artifact["id"],
            expected_artifact_digest=registration.archive_digest,
        )


def test_commit_b_rejects_any_post_registration_change(
    registration: RegistrationFixture,
) -> None:
    extra = registration.root / "extra.txt"
    extra.write_text("not preregistration\n")
    _git(registration.root, "add", "extra.txt")
    _git(registration.root, "commit", "-q", "-m", "not B")
    wrong_b = _git(registration.root, "rev-parse", "HEAD")
    with pytest.raises(confirmatory.SWM0WConfirmatoryError, match="direct child"):
        confirmatory.validate_registration_commit_pair(
            registration.prereg,
            repo_root=registration.root,
            registration_commit_b=wrong_b,
        )


def test_duplicate_json_keys_are_rejected_before_canonicalization(
    registration: RegistrationFixture,
) -> None:
    duplicate = b'{"schema_version":"a","schema_version":"b"}\n'
    with pytest.raises(confirmatory.SWM0WConfirmatoryError, match="duplicate JSON"):
        confirmatory.validate_preregistration_bytes(
            duplicate, repo_root=registration.root
        )


def test_registration_zip_and_live_operational_chronology(
    registration: RegistrationFixture,
) -> None:
    carrier, archived_run, archived_workflow_runs = (
        confirmatory.parse_registration_archive(
            registration.archive, expected_digest=registration.archive_digest
        )
    )
    assert carrier == registration.carrier
    assert archived_run["id"] == registration.run["id"]
    assert archived_workflow_runs["total_count"] == 1
    chronology = confirmatory.build_github_chronology_receipt(
        registration.prereg,
        carrier,
        github_run=registration.run,
        github_workflow_runs=registration.workflow_runs,
        github_jobs=registration.jobs,
        artifact=registration.artifact,
        downloaded_archive_bytes=registration.archive,
        expected_artifact_id=registration.artifact["id"],
        expected_artifact_digest=registration.archive_digest,
    )
    assert chronology.chronology_status == confirmatory.CHRONOLOGY_STATUS
    assert chronology.run_attempt == 1

    mutated_jobs = json.loads(json.dumps(registration.jobs))
    mutated_jobs["jobs"][0]["run_attempt"] = 2
    with pytest.raises(
        confirmatory.SWM0WConfirmatoryError, match="identity/conclusion"
    ):
        confirmatory.build_github_chronology_receipt(
            registration.prereg,
            carrier,
            github_run=registration.run,
            github_workflow_runs=registration.workflow_runs,
            github_jobs=mutated_jobs,
            artifact=registration.artifact,
            downloaded_archive_bytes=registration.archive,
            expected_artifact_id=registration.artifact["id"],
            expected_artifact_digest=registration.archive_digest,
        )

    duplicate_runs = json.loads(json.dumps(registration.workflow_runs))
    second = json.loads(json.dumps(registration.run))
    second["id"] = registration.run["id"] + 1
    duplicate_runs["total_count"] = 2
    duplicate_runs["workflow_runs"].append(second)
    with pytest.raises(confirmatory.SWM0WConfirmatoryError, match="sole surviving"):
        confirmatory.build_github_chronology_receipt(
            registration.prereg,
            carrier,
            github_run=registration.run,
            github_workflow_runs=duplicate_runs,
            github_jobs=registration.jobs,
            artifact=registration.artifact,
            downloaded_archive_bytes=registration.archive,
            expected_artifact_id=registration.artifact["id"],
            expected_artifact_digest=registration.archive_digest,
        )


def test_archive_rejects_digest_drift_duplicates_and_traversal() -> None:
    good = _zip_bytes({"candidate_bundle.json": b"{}\n"})
    with pytest.raises(confirmatory.SWM0WConfirmatoryError, match="digest mismatch"):
        confirmatory.validate_artifact_archive(
            good,
            expected_digest="0" * 64,
            expected_members=confirmatory.CANDIDATE_ARCHIVE_MEMBERS,
            maximum_bytes=1_024,
        )
    stream = BytesIO()
    with pytest.warns(UserWarning, match="Duplicate name"):
        with ZipFile(stream, "w") as archive:
            archive.writestr("candidate_bundle.json", b"one")
            archive.writestr("candidate_bundle.json", b"two")
    duplicate = stream.getvalue()
    with pytest.raises(confirmatory.SWM0WConfirmatoryError, match="member set/order"):
        confirmatory.validate_artifact_archive(
            duplicate,
            expected_digest=sha256(duplicate).hexdigest(),
            expected_members=confirmatory.CANDIDATE_ARCHIVE_MEMBERS,
            maximum_bytes=1_024,
        )
    traversal = _zip_bytes({"../candidate_bundle.json": b"{}"})
    with pytest.raises(confirmatory.SWM0WConfirmatoryError):
        confirmatory.validate_artifact_archive(
            traversal,
            expected_digest=sha256(traversal).hexdigest(),
            expected_members=("../candidate_bundle.json",),
            maximum_bytes=1_024,
        )


def test_wait_is_bounded_and_network_refusal_precedes_verifier(
    registration: RegistrationFixture,
) -> None:
    times = iter(
        [
            registration.prereg.commitment.round_time_unix - 20,
            registration.prereg.commitment.round_time_unix - 5,
            registration.prereg.commitment.round_time_unix,
        ]
    )
    sleeps: list[float] = []
    confirmatory.wait_for_committed_round(
        registration.prereg.commitment,
        clock=lambda: next(times),
        sleeper=sleeps.append,
    )
    assert sleeps == [15.0, 5.0]

    called = False

    def verifier(_: beacon.FutureRoundCommitmentV1):
        nonlocal called
        called = True
        raise AssertionError("must not run")

    with pytest.raises(confirmatory.SWM0WConfirmatoryError, match="explicit opt-in"):
        confirmatory._verify_committed_pulse_with_fixed_retries(  # type: ignore[attr-defined]
            registration.prereg.commitment,
            allow_network=False,
            verifier=verifier,
        )
    assert called is False


@requires_drand_verifier
def test_offline_quicknet_vector_binds_exact_order_but_cannot_admit(
    registration: RegistrationFixture,
) -> None:
    receipt, binding = beacon.verify_and_bind_offline(registration.prereg.commitment)
    beacon.validate_task_seed_bundle_links(
        registration.prereg.commitment, receipt, binding
    )
    seeds = binding.task_seed_bytes()
    assert len(seeds) == protocol.TASK_COUNT
    assert protocol.ordered_task_seed_binding_sha256(seeds) != (
        protocol.ordered_task_seed_binding_sha256(tuple(reversed(seeds)))
    )
    chronology = confirmatory.build_github_chronology_receipt(
        registration.prereg,
        registration.carrier,
        github_run=registration.run,
        github_workflow_runs=registration.workflow_runs,
        github_jobs=registration.jobs,
        artifact=registration.artifact,
        downloaded_archive_bytes=registration.archive,
        expected_artifact_id=registration.artifact["id"],
        expected_artifact_digest=registration.archive_digest,
    )
    with pytest.raises(confirmatory.SWM0WConfirmatoryError, match="online mode"):
        confirmatory.admit_verified_seed_bundle(
            registration.prereg,
            registration.carrier,
            chronology,
            verifier_receipt=receipt,
            task_seed_binding=binding,
        )


@requires_drand_verifier
def test_candidate_only_becomes_pass_after_server_bound_no_training_replay(
    registration: RegistrationFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_builder = task_family.build_task_from_external_seed
    task_cache: dict[bytes, task_family.StreamedTaskV1] = {}

    def cached_builder(seed: bytes) -> task_family.StreamedTaskV1:
        if seed not in task_cache:
            task_cache[seed] = real_builder(seed)
        return task_cache[seed]

    monkeypatch.setattr(task_family, "build_task_from_external_seed", cached_builder)
    verifier_receipt, binding = beacon.verify_and_bind_offline(
        registration.prereg.commitment
    )
    chronology = confirmatory.build_github_chronology_receipt(
        registration.prereg,
        registration.carrier,
        github_run=registration.run,
        github_workflow_runs=registration.workflow_runs,
        github_jobs=registration.jobs,
        artifact=registration.artifact,
        downloaded_archive_bytes=registration.archive,
        expected_artifact_id=registration.artifact["id"],
        expected_artifact_digest=registration.archive_digest,
    )
    # Offline fixture execution exercises all deterministic links without
    # pretending to be production.  Only this one online-mode guard is mocked.
    monkeypatch.setattr(confirmatory, "_validate_pinned_node_receipt", lambda _: None)
    admission = confirmatory.admit_verified_seed_bundle(
        registration.prereg,
        registration.carrier,
        chronology,
        verifier_receipt=verifier_receipt,
        task_seed_binding=binding,
    )
    tasks = tuple(
        _synthetic_task_receipt(index, seed)
        for index, seed in enumerate(binding.task_seed_bytes())
    )
    final = protocol.finalize_protocol(
        tasks,
        mode=protocol.RunMode.CONFIRMATORY,
        optimizer=protocol.CONFIRMATORY_OPTIMIZER,
        admission=admission,
        thresholds=protocol.CONFIRMATORY_THRESHOLDS,
    )
    assert final.outcome is protocol.ProtocolOutcome.CANDIDATE_PASS_AWAITING_BUNDLE
    candidate = confirmatory.build_candidate_bundle(
        registration.prereg,
        registration.carrier,
        chronology,
        github_run=registration.run,
        github_workflow_runs=registration.workflow_runs,
        github_jobs=registration.jobs,
        artifact=registration.artifact,
        verifier_receipt=verifier_receipt,
        task_seed_binding=binding,
        admission=admission,
        task_receipts=tasks,
        final_receipt=final,
    )
    assert "evidence_verdict" not in candidate
    assert len(candidate["task_receipts_in_seed_order"]) == 20

    round_time = registration.prereg.commitment.round_time_unix
    jobs = json.loads(json.dumps(registration.jobs))
    jobs["jobs"].append(
        {
            "id": 333,
            "name": "confirm",
            "run_id": registration.run["id"],
            "run_attempt": 1,
            "head_sha": registration.commit_b,
            "status": "completed",
            "conclusion": "success",
            "started_at": _rfc3339(round_time + 1),
            "completed_at": _rfc3339(round_time + 120),
            "labels": [confirmatory.RUNNER_LABEL],
            "runner_name": "GitHub Actions 1",
            "runner_group_name": "GitHub Actions",
        }
    )
    candidate_bytes = (confirmatory.canonical_json(candidate) + "\n").encode()
    candidate_archive = _zip_bytes({"candidate_bundle.json": candidate_bytes})
    candidate_digest = sha256(candidate_archive).hexdigest()
    candidate_artifact = {
        "id": 9999,
        "name": confirmatory.candidate_artifact_name(registration.carrier),
        "digest": f"sha256:{candidate_digest}",
        "expired": False,
        "size_in_bytes": len(candidate_archive),
        "created_at": _rfc3339(round_time + 100),
        "workflow_run": {
            "id": registration.run["id"],
            "head_sha": registration.commit_b,
        },
    }
    pre_pulse_jobs = json.loads(json.dumps(jobs))
    pre_pulse_confirm = pre_pulse_jobs["jobs"][-1]
    pre_pulse_confirm["started_at"] = _rfc3339(round_time - 50)
    pre_pulse_confirm["completed_at"] = _rfc3339(round_time - 10)
    pre_pulse_artifact = dict(candidate_artifact)
    pre_pulse_artifact["created_at"] = _rfc3339(round_time - 20)
    with pytest.raises(confirmatory.SWM0WConfirmatoryError, match="post-pulse"):
        confirmatory.adjudicate_candidate_archive(
            registration.prereg,
            registration.carrier,
            repo_root=registration.root,
            github_run=registration.run,
            github_workflow_runs=registration.workflow_runs,
            github_jobs=pre_pulse_jobs,
            registration_artifact=registration.artifact,
            registration_archive_bytes=registration.archive,
            registration_artifact_id=registration.artifact["id"],
            registration_artifact_digest=registration.archive_digest,
            candidate_artifact=pre_pulse_artifact,
            candidate_archive_bytes=candidate_archive,
            candidate_artifact_id=pre_pulse_artifact["id"],
            candidate_artifact_digest=candidate_digest,
        )
    adjudication = confirmatory.adjudicate_candidate_archive(
        registration.prereg,
        registration.carrier,
        repo_root=registration.root,
        github_run=registration.run,
        github_workflow_runs=registration.workflow_runs,
        github_jobs=jobs,
        registration_artifact=registration.artifact,
        registration_archive_bytes=registration.archive,
        registration_artifact_id=registration.artifact["id"],
        registration_artifact_digest=registration.archive_digest,
        candidate_artifact=candidate_artifact,
        candidate_archive_bytes=candidate_archive,
        candidate_artifact_id=candidate_artifact["id"],
        candidate_artifact_digest=candidate_digest,
    )
    assert adjudication.evidence_verdict == "PASS"
    assert adjudication.capacity_independent_phrase_allowed is True
    assert (
        adjudication.bls_replay_ordered_task_seed_binding_sha256
        == adjudication.task_seed_binding_sha256
    )
    assert adjudication.bls_replay_fixture_sha256
    assert adjudication.bls_replay_stable_projection_sha256

    replay_inputs = {
        "repo_root": registration.root,
        "github_run": registration.run,
        "github_workflow_runs": registration.workflow_runs,
        "github_jobs": jobs,
        "registration_artifact": registration.artifact,
        "registration_archive_bytes": registration.archive,
        "registration_artifact_id": registration.artifact["id"],
        "registration_artifact_digest": registration.archive_digest,
        "candidate_artifact": candidate_artifact,
        "candidate_archive_bytes": candidate_archive,
        "candidate_artifact_id": candidate_artifact["id"],
        "candidate_artifact_digest": candidate_digest,
    }
    tampered_replay = adjudication.canonical()
    tampered_replay["bls_replay_stable_projection_sha256"] = "f" * 64
    tampered_unsigned = dict(tampered_replay)
    del tampered_unsigned["receipt_sha256"]
    tampered_replay["receipt_sha256"] = confirmatory.canonical_sha256(tampered_unsigned)
    with pytest.raises(confirmatory.SWM0WConfirmatoryError, match="does not replay"):
        confirmatory.validate_evidence_adjudication(
            tampered_replay,
            registration.prereg,
            registration.carrier,
            **replay_inputs,
        )

    real_replay = confirmatory._replay_committed_pulse_bls  # type: ignore[attr-defined]

    def reject_bls(*_: object) -> object:
        raise confirmatory.SWM0WConfirmatoryError("independent BLS replay rejected")

    monkeypatch.setattr(confirmatory, "_replay_committed_pulse_bls", reject_bls)
    with pytest.raises(confirmatory.SWM0WConfirmatoryError, match="BLS replay"):
        confirmatory.adjudicate_candidate_archive(
            registration.prereg,
            registration.carrier,
            repo_root=registration.root,
            github_run=registration.run,
            github_workflow_runs=registration.workflow_runs,
            github_jobs=jobs,
            registration_artifact=registration.artifact,
            registration_archive_bytes=registration.archive,
            registration_artifact_id=registration.artifact["id"],
            registration_artifact_digest=registration.archive_digest,
            candidate_artifact=candidate_artifact,
            candidate_archive_bytes=candidate_archive,
            candidate_artifact_id=candidate_artifact["id"],
            candidate_artifact_digest=candidate_digest,
        )
    monkeypatch.setattr(confirmatory, "_replay_committed_pulse_bls", real_replay)

    wrong_first = _synthetic_task_receipt(
        0,
        binding.task_seed_bytes()[0],
        task_material_seed=b"fabricated-task-material".ljust(32, b"\0"),
        variance_override=protocol.ExactTestVariance(5_000, 0, 40_000, 1),
    )
    seed_digest_only_tasks = (wrong_first, *tasks[1:])
    # The protocol's structural seed binding accepts this: every declared seed
    # digest is right, but task 0's UID/SHA/variance came from another seed.
    seed_digest_only_final = protocol.finalize_protocol(
        seed_digest_only_tasks,
        mode=protocol.RunMode.CONFIRMATORY,
        optimizer=protocol.CONFIRMATORY_OPTIMIZER,
        admission=admission,
        thresholds=protocol.CONFIRMATORY_THRESHOLDS,
    )
    assert seed_digest_only_final.outcome is (
        protocol.ProtocolOutcome.CANDIDATE_PASS_AWAITING_BUNDLE
    )
    identity_forged = json.loads(json.dumps(candidate))
    identity_forged["task_receipts_in_seed_order"] = [
        row.canonical() for row in seed_digest_only_tasks
    ]
    identity_forged["protocol_final_receipt"] = seed_digest_only_final.canonical()
    identity_forged["protocol_candidate_outcome"] = seed_digest_only_final.outcome.value
    unsigned = dict(identity_forged)
    del unsigned["bundle_sha256"]
    identity_forged["bundle_sha256"] = confirmatory.canonical_sha256(unsigned)
    identity_bytes = (confirmatory.canonical_json(identity_forged) + "\n").encode()
    identity_archive = _zip_bytes({"candidate_bundle.json": identity_bytes})
    identity_digest = sha256(identity_archive).hexdigest()
    identity_artifact = dict(candidate_artifact)
    identity_artifact["digest"] = f"sha256:{identity_digest}"
    identity_artifact["size_in_bytes"] = len(identity_archive)
    with pytest.raises(confirmatory.SWM0WConfirmatoryError, match="identity/variance"):
        confirmatory.adjudicate_candidate_archive(
            registration.prereg,
            registration.carrier,
            repo_root=registration.root,
            github_run=registration.run,
            github_workflow_runs=registration.workflow_runs,
            github_jobs=jobs,
            registration_artifact=registration.artifact,
            registration_archive_bytes=registration.archive,
            registration_artifact_id=registration.artifact["id"],
            registration_artifact_digest=registration.archive_digest,
            candidate_artifact=identity_artifact,
            candidate_archive_bytes=identity_archive,
            candidate_artifact_id=identity_artifact["id"],
            candidate_artifact_digest=identity_digest,
        )

    forged = json.loads(json.dumps(candidate))
    forged["protocol_candidate_outcome"] = (
        protocol.ProtocolOutcome.CANDIDATE_KILL_AWAITING_BUNDLE.value
    )
    unsigned = dict(forged)
    del unsigned["bundle_sha256"]
    forged["bundle_sha256"] = confirmatory.canonical_sha256(unsigned)
    forged_bytes = (confirmatory.canonical_json(forged) + "\n").encode()
    forged_archive = _zip_bytes({"candidate_bundle.json": forged_bytes})
    forged_digest = sha256(forged_archive).hexdigest()
    forged_artifact = dict(candidate_artifact)
    forged_artifact["digest"] = f"sha256:{forged_digest}"
    forged_artifact["size_in_bytes"] = len(forged_archive)
    with pytest.raises(
        confirmatory.SWM0WConfirmatoryError, match="differs from reducer"
    ):
        confirmatory.adjudicate_candidate_archive(
            registration.prereg,
            registration.carrier,
            repo_root=registration.root,
            github_run=registration.run,
            github_workflow_runs=registration.workflow_runs,
            github_jobs=jobs,
            registration_artifact=registration.artifact,
            registration_archive_bytes=registration.archive,
            registration_artifact_id=registration.artifact["id"],
            registration_artifact_digest=registration.archive_digest,
            candidate_artifact=forged_artifact,
            candidate_archive_bytes=forged_archive,
            candidate_artifact_id=forged_artifact["id"],
            candidate_artifact_digest=forged_digest,
        )


def test_atomic_output_never_overwrites(tmp_path: Path) -> None:
    output = tmp_path / "receipt.json"
    digest = confirmatory.atomic_write_canonical_json(output, {"x": 1})
    assert digest == sha256(b'{"x":1}\n').hexdigest()
    with pytest.raises(confirmatory.SWM0WConfirmatoryError, match="overwrite"):
        confirmatory.atomic_write_canonical_json(output, {"x": 2})


def test_operational_failure_can_only_record_void(
    registration: RegistrationFixture,
) -> None:
    receipt = confirmatory.build_operational_void_receipt(
        registration.prereg,
        registration_commit_b=registration.commit_b,
        run_id=registration.run["id"],
        confirm_needs_result="failure",
        reason_code="CONFIRM_JOB_DID_NOT_COMPLETE_SUCCESSFULLY",
        github_run=registration.run,
        github_workflow_runs=registration.workflow_runs,
        github_jobs=registration.jobs,
    )
    assert (
        confirmatory.validate_operational_void_receipt(receipt)["evidence_verdict"]
        == "VOID"
    )
    forged = dict(receipt)
    forged["evidence_verdict"] = "PASS"
    with pytest.raises(confirmatory.SWM0WConfirmatoryError, match="fixed fields"):
        confirmatory.validate_operational_void_receipt(forged)


def test_workflow_is_three_job_attempt_one_and_has_no_rerun_surface() -> None:
    workflow_path = (
        Path(__file__).parents[1] / ".github/workflows/swm0w-confirmatory.yml"
    )
    if not workflow_path.is_file():
        pytest.skip(
            "repository-only workflow is not shipped in the source distribution"
        )
    workflow = workflow_path.read_text(encoding="utf-8")
    assert "workflow_dispatch:" not in workflow
    assert "schedule:" not in workflow
    assert "matrix:" not in workflow
    assert "download-artifact" not in workflow
    assert "cache: true" not in workflow
    assert "register:\n" in workflow
    assert "  confirm:\n" in workflow
    assert "  adjudicate:\n" in workflow
    assert "always()" in workflow
    assert workflow.count("github.run_attempt == 1") == 3
    assert workflow.count("actions/workflows/swm0w-confirmatory.yml/runs?") == 4
    assert workflow.count("--workflow-runs-json") == 6
    assert workflow.count("npm ci --ignore-scripts --no-audit --no-fund") == 2
    assert (
        workflow.count("actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020")
        == 2
    )
    for step_id in (
        "id: fail_closed_marker",
        "id: node_setup",
        "id: replay_preflight",
        "id: control_plane",
        "id: strong_adjudication",
    ):
        assert step_id in workflow
    assert workflow.count("continue-on-error: true") >= 4
    for outcome in (
        "steps.fail_closed_marker.outcome",
        "steps.node_setup.outcome",
        "steps.replay_preflight.outcome",
        "steps.control_plane.outcome",
        "steps.strong_adjudication.outcome",
    ):
        assert outcome in workflow
    assert "steps.upload.outcome == 'success'" in workflow
    assert "if: ${{ always() }}\n        uses: actions/upload-artifact@" in workflow
    assert "missing/unreadable adjudication artifact is VOID/no evidence" in (
        confirmatory.__doc__ or ""
    )
    lines = workflow.splitlines()
    step_starts = [
        index for index, line in enumerate(lines) if line.startswith("      - name:")
    ]
    assert step_starts
    for position, start in enumerate(step_starts):
        end = (
            step_starts[position + 1] if position + 1 < len(step_starts) else len(lines)
        )
        block = lines[start:end]
        executors = [
            line
            for line in block
            if line.startswith("        run:") or line.startswith("        uses:")
        ]
        assert len(executors) == 1, f"workflow step lacks one executor: {block[0]}"
    assert "REPOSITORY_OWNER_HAS_NOT_DELETED_MATCHING_RUNS" in (
        confirmatory.EVIDENCE_TRUST_BOUNDARY
    )
    for pin in (
        "11bd71901bbe5b1630ceea73d27597364c9af683",
        "1e862dfacbd1d6d858c55d9b792c756523627244",
        "49933ea5288caeca8642d1e84afbd3f7d6820020",
        "ea165f8d65b6e75b540449e92b4886f43607fa02",
    ):
        assert pin in workflow
    for stale_or_wrong_pin in (
        "3d3c42e5aac5ba805825da76410c181273ba90b1",
        "c771a70e6277c0a99b617c7a806ffedaca235ff9",
        "249970729cb0ef3589644e2896645e5dc5ba9c38",
    ):
        assert stale_or_wrong_pin not in workflow


def test_admission_object_alone_has_no_evidence_promotion_api() -> None:
    # The protocol type is intentionally structural.  The chronology module's
    # only candidate->verdict mapping is reached through exact GitHub artifact
    # adjudication, never from this type alone.
    assert "admission" not in confirmatory._OUTCOME_TO_EVIDENCE  # type: ignore[attr-defined]
    assert (
        protocol.protocol_contract()["scope"]["standalone_authoritative_verdict"]
        is False
    )
    assert not hasattr(confirmatory, "adjudicate_admission")
