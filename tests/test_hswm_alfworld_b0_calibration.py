from __future__ import annotations

from hashlib import sha256
import io
import json
import os
from pathlib import Path
from typing import Any

import pytest

from _research.dnrd5.canonical_json import canonical_bytes
from hswm.experiments import alfworld_b0_selection as selection_module
from hswm.experiments.alfworld_b0_actor import (
    B0_ACTION_PROTOCOL,
    B0_ACTION_RECEIPT_SCHEMA,
    B0ActionReceipt,
    _action_schema,
)
from hswm.experiments.alfworld_b0_calibration import (
    COMPLETE_STATUS,
    INCONCLUSIVE_STATUS,
    AlfworldB0CalibrationError,
    run_b0_calibration,
    verify_protocol,
)
from hswm.experiments.alfworld_text_runtime import (
    LocalSandboxSpec,
    read_one_line,
)
from hswm.experiments.alfworld_text_worker import actor_projection, build_outcome
from hswm.selfmod.contracts import canonical_json_bytes


REPOSITORY = Path(__file__).resolve().parents[1]
PROTOCOL = (
    REPOSITORY
    / "_research/causal_composition/preregistrations/alfworld_b0_calibration_2026-08-30/protocol.v1.json"
).resolve()


def _file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _fixture(
    tmp_path: Path,
) -> tuple[Path, dict[str, object], Path, Path, Path]:
    asset = tmp_path / "asset"
    asset.mkdir()
    records: list[dict[str, object]] = []
    selected: dict[str, list[dict[str, str]]] = {"train": [], "valid_seen": []}
    for split, count in (("train", 8), ("valid_seen", 4)):
        for number in range(count):
            relative = f"{split}/{number}.tw-pddl"
            game = asset / relative
            game.parent.mkdir(exist_ok=True)
            contents = f"game-{split}-{number}".encode()
            game.write_bytes(contents)
            opaque = f"opaque:{split}:{number}"
            group = f"group:{split}:{number}"
            records.append(
                {
                    "bytes": len(contents),
                    "file_sha256": sha256(contents).hexdigest(),
                    "opaque_uid": opaque,
                    "relative_path": relative,
                    "relative_path_sha256": sha256(relative.encode()).hexdigest(),
                    "split": split,
                    "task_group_uid": group,
                }
            )
            selected[split].append(
                {"split": split, "task_group_uid": group, "opaque_uid": opaque}
            )
    commitment = {
        "selected_game_counts": {"train": 8, "valid_seen": 4},
        "selected_game_bytes_by_split": {
            split: sum(int(row["bytes"]) for row in records if row["split"] == split)
            for split in ("train", "valid_seen")
        },
        "selected_task_group_counts": {"train": 8, "valid_seen": 4},
        "task_group_overlap_counts": {},
        "selected_game_total": 12,
    }
    locator = {
        "schema_version": "hswm-alfworld-text-clean-pool-local-locator/v1",
        "record_role": "LOCAL_NONREPOSITORY_GAME_LOCATOR_NOT_FOR_REDISTRIBUTION",
        "source_binding": {"repository_commit": "a" * 40, "assets": []},
        "pool_commitment": commitment,
        "records": records,
    }
    locator_raw = (
        json.dumps(locator, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()
    locator_path = tmp_path / "locator.json"
    locator_path.write_bytes(locator_raw)
    manifest = {
        "schema_version": "hswm-alfworld-text-clean-pool/v2",
        "aggregate_commitment": {
            "local_locator_rendered_json_sha256": sha256(locator_raw).hexdigest(),
            "local_locator_canonical_json_sha256": sha256(
                canonical_bytes(locator)
            ).hexdigest(),
            **commitment,
        },
        "source_binding": {
            "repository_commit": "a" * 40,
            "official_release_assets": [],
        },
    }
    pool_path = tmp_path / "pool.json"
    pool_path.write_bytes(
        (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    )
    verified = verify_protocol(PROTOCOL)
    digest = sha256(canonical_bytes(selected)).hexdigest()
    selection: dict[str, object] = {
        "schema_version": "hswm-alfworld-b0-selection-private-receipt/v1",
        "record_role": "LOCAL_NONREPOSITORY_OPAQUE_B0_SELECTION_RECEIPT_NOT_FOR_REDISTRIBUTION",
        "status": "PROSPECTIVE_SELECTION_ONLY_G0_NOT_RUN",
        "protocol": {
            "uid": verified.uid,
            "version": verified.version,
            "protocol_file_sha256": verified.binding_sha256,
        },
        "selector_source_sha256": _file_sha(Path(selection_module.__file__)),
        "input_commitments": {
            "pool_manifest_rendered_json_sha256": _file_sha(pool_path),
            "local_locator_rendered_json_sha256": _file_sha(locator_path),
        },
        "selection_digest_sha256": digest,
        "selected": selected,
        "valid_unseen_selected_group_count": 0,
        "no_claim": "Local selection receipt only; no experiment was run.",
    }
    selection["private_receipt_sha256"] = sha256(
        canonical_bytes(selection)
    ).hexdigest()
    return PROTOCOL, selection, pool_path, locator_path, asset


class _FakeActor:
    def __init__(self, *, fail_call: int | None = None) -> None:
        self._tokenize = 0
        self._completion = 0
        self._sealed = False
        self.fail_call = fail_call
        self.received: list[dict[str, Any]] = []
        self.deadline_calls: list[tuple[float | None, Any]] = []

    @property
    def request_counts(self) -> tuple[int, int]:
        return self._tokenize, self._completion

    def seal(self) -> tuple[int, int]:
        self._sealed = True
        return self.request_counts

    def act(
        self,
        *,
        episode_uid: str,
        step_index: int,
        history: tuple[dict[str, str], ...],
        observation: str,
        deadline: float | None = None,
        monotonic: Any = None,
    ) -> B0ActionReceipt:
        self.deadline_calls.append((deadline, monotonic))
        assert not self._sealed
        self._tokenize += 1
        if self.fail_call == self._tokenize:
            raise RuntimeError("scripted transport failure")
        self._completion += 1
        self.received.append(
            {
                "episode_uid": episode_uid,
                "step_index": step_index,
                "history": history,
                "observation": observation,
            }
        )
        digest = sha256(f"{episode_uid}:{step_index}".encode()).hexdigest()
        action = "look"
        unsigned: dict[str, object] = {
            "action": action,
            "action_sha256": sha256(action.encode()).hexdigest(),
            "completion_call_count": 1,
            "completion_call_index": self._completion,
            "completion_latency_ms": 7,
            "completion_request_sha256": digest,
            "completion_response_sha256": digest,
            "episode_uid": episode_uid,
            "input_tokens": 3,
            "model": "qwen3.6-35b-a3b",
            "output_tokens": 2,
            "protocol": B0_ACTION_PROTOCOL,
            "response_schema_sha256": _action_schema().schema_sha256,
            "schema": B0_ACTION_RECEIPT_SCHEMA,
            "step_index": step_index,
            "tokenize_call_count": 1,
            "tokenize_call_index": self._tokenize,
            "token_preflight_token_count": 3,
            "token_preflight_latency_ms": 3,
            "token_preflight_receipt_sha256": digest,
            "token_preflight_request_sha256": digest,
            "token_preflight_response_sha256": digest,
            "usage_reported": True,
        }
        return B0ActionReceipt(
            **unsigned,
            receipt_sha256=sha256(canonical_json_bytes(unsigned)).hexdigest(),
        )


class _Process:
    def __init__(
        self,
        *,
        uid: str,
        source_sha: str,
        action_steps: int = 1,
        malformed_outcome: bool = False,
        extra_stdout: bytes = b"",
    ) -> None:
        frames = [
            canonical_bytes(
                actor_projection(
                    episode_uid=uid,
                    observation=f"observation-{step}",
                    step_index=step,
                    done=step == action_steps,
                )
            )
            + b"\n"
            for step in range(action_steps + 1)
        ]
        self.stdin = io.BytesIO()
        self.stdout = io.BytesIO(b"".join(frames) + extra_stdout)
        actions = [sha256(b"look").hexdigest()] * action_steps
        observations = [sha256(f"observation-{step}".encode()).hexdigest() for step in range(action_steps + 1)]
        outcome = build_outcome(
            episode_uid=uid,
            action_digests=actions,
            observation_digests=observations,
            done=True,
            won=True,
            score=1,
            source_game_sha256=source_sha,
        )
        self.stderr = io.BytesIO(
            b"bad\n" if malformed_outcome else canonical_bytes(outcome) + b"\n"
        )
        self.closed = False

    def wait(self, timeout: float) -> int:
        self.closed = True
        return 0

    def poll(self) -> int | None:
        return 0 if self.closed else None

    def terminate(self) -> None:
        self.closed = True


def _reader(stream: io.BytesIO, *, timeout_seconds: float, label: str) -> bytes:
    del timeout_seconds, label
    return stream.readline()


def _factory(tmp_path: Path, *, wrong_uid: bool = False):
    def build(selection, binding, game_file, pool_sha, locator_sha, protocol):
        root = tmp_path / "python-root"
        (root / "bin").mkdir(parents=True, exist_ok=True)
        python = root / "bin" / "python"
        python.write_text("x")
        for name in ("repo", "upstream", "venv"):
            (tmp_path / name).mkdir(exist_ok=True)
        bwrap = tmp_path / "bwrap"
        bwrap.write_text("x")
        return LocalSandboxSpec(
            bwrap,
            python,
            root,
            tmp_path / "repo",
            tmp_path / "upstream",
            tmp_path / "venv",
            game_file.parents[1],
            game_file,
            pool_sha,
            locator_sha,
            binding,
            "wrong:uid" if wrong_uid else selection.opaque_uid,
            max_steps=protocol.max_steps,
        )

    return build


def test_runs_exact_order_and_projects_only_aggregates(tmp_path: Path) -> None:
    protocol, selection, pool, locator, asset = _fixture(tmp_path)
    actor = _FakeActor()
    seen: list[str] = []

    def launcher(spec):
        seen.append(spec.episode_uid)
        return _Process(
            uid=spec.episode_uid, source_sha=spec.game_binding.file_sha256
        )

    private, public = run_b0_calibration(
        protocol=protocol,
        private_selection_receipt=selection,
        pool_manifest=pool,
        local_locator=locator,
        asset_root=asset,
        sandbox_spec_factory=_factory(tmp_path),
        runtime_launcher=launcher,
        actor=actor,
        frame_reader=_reader,
    )
    assert private["status"] == COMPLETE_STATUS
    assert [row["split"] for row in private["episode_prefix"]] == ["train"] * 8 + [
        "valid_seen"
    ] * 4
    assert len(seen) == 12
    assert public["success_counts"] == {"train": 8, "valid_seen": 4}
    assert public["headroom_classification"] == "SATURATION_OR_INSUFFICIENT_HEADROOM"
    assert public["resource_totals"]["issued_http_post_count"] == 24
    assert public["confidence_intervals"]["train"] == {
        "successes": 8,
        "trials": 8,
        "lower": "0.630583352",
        "upper": "1.000000000",
        "method": "TWO_SIDED_95_PERCENT_CLOPPER_PEARSON",
    }
    encoded = canonical_bytes(public).lower()
    for forbidden in (
        b"opaque:train",
        b"group:train",
        b"observation-0",
        b'"action"',
        b"relative_path",
    ):
        assert forbidden not in encoded


def test_schema_error_seals_prefix_once_without_replacement(tmp_path: Path) -> None:
    protocol, selection, pool, locator, asset = _fixture(tmp_path)
    actor = _FakeActor()
    launches = 0

    def launcher(spec):
        nonlocal launches
        launches += 1
        return _Process(
            uid=spec.episode_uid,
            source_sha=spec.game_binding.file_sha256,
            malformed_outcome=launches == 2,
        )

    private, public = run_b0_calibration(
        protocol=protocol,
        private_selection_receipt=selection,
        pool_manifest=pool,
        local_locator=locator,
        asset_root=asset,
        sandbox_spec_factory=_factory(tmp_path),
        runtime_launcher=launcher,
        actor=actor,
        frame_reader=_reader,
    )
    assert launches == 2
    assert private["status"] == INCONCLUSIVE_STATUS
    assert len(private["episode_prefix"]) == 2
    assert public["invalid_counts"] == {"train": 1, "valid_seen": 0}
    assert (
        public["headroom_classification"]
        == "INCONCLUSIVE_MEASUREMENT_NOT_READY_WITHOUT_HEADROOM_CLASSIFICATION"
    )
    assert public["confidence_intervals"] is None


def test_selection_digest_and_pool_binding_fail_before_launch(tmp_path: Path) -> None:
    protocol, selection, pool, locator, asset = _fixture(tmp_path)
    selected = selection["selected"]
    assert isinstance(selected, dict)
    train = selected["train"]
    assert isinstance(train, list)
    train[0]["opaque_uid"] = "opaque:forged"
    selection["private_receipt_sha256"] = sha256(
        canonical_bytes(
            {key: value for key, value in selection.items() if key != "private_receipt_sha256"}
        )
    ).hexdigest()
    with pytest.raises(AlfworldB0CalibrationError, match="digest does not bind"):
        run_b0_calibration(
            protocol=protocol,
            private_selection_receipt=selection,
            pool_manifest=pool,
            local_locator=locator,
            asset_root=asset,
            sandbox_spec_factory=_factory(tmp_path),
            runtime_launcher=lambda spec: pytest.fail("must not launch"),
            actor=_FakeActor(),
            frame_reader=_reader,
        )


def test_malicious_factory_binding_is_consumed_once_without_launch(tmp_path: Path) -> None:
    protocol, selection, pool, locator, asset = _fixture(tmp_path)
    private, public = run_b0_calibration(
        protocol=protocol,
        private_selection_receipt=selection,
        pool_manifest=pool,
        local_locator=locator,
        asset_root=asset,
        sandbox_spec_factory=_factory(tmp_path, wrong_uid=True),
        runtime_launcher=lambda spec: pytest.fail("must not launch"),
        actor=_FakeActor(),
        frame_reader=_reader,
    )
    assert private["status"] == INCONCLUSIVE_STATUS
    assert len(private["episode_prefix"]) == 1
    assert public["resource_totals"]["issued_http_post_count"] == 0


def test_initial_pipe_close_preserves_only_registered_worker_phase(tmp_path: Path) -> None:
    protocol, selection, pool, locator, asset = _fixture(tmp_path)
    read_fd, write_fd = os.pipe()
    os.close(write_fd)
    closed_stdout = os.fdopen(read_fd, "rb")

    class PreframeProcess(_Process):
        def __init__(self, *, uid: str, source_sha: str) -> None:
            super().__init__(uid=uid, source_sha=source_sha)
            self.stdout = closed_stdout
            self.poll_count = 0

        def poll(self) -> int | None:
            self.poll_count += 1
            return None if self.poll_count == 1 else 44

        def wait(self, timeout: float) -> int:
            del timeout
            self.closed = True
            return 44

    try:
        private, public = run_b0_calibration(
            protocol=protocol,
            private_selection_receipt=selection,
            pool_manifest=pool,
            local_locator=locator,
            asset_root=asset,
            sandbox_spec_factory=_factory(tmp_path),
            runtime_launcher=lambda spec: PreframeProcess(
                uid=spec.episode_uid,
                source_sha=spec.game_binding.file_sha256,
            ),
            actor=_FakeActor(),
            frame_reader=read_one_line,
        )
    finally:
        closed_stdout.close()
    failure = private["episode_prefix"][0]
    assert failure["preframe_failure_phase"] == "ENVIRONMENT_RESET"
    assert failure["error"] == "runtime refused before initial actor frame"
    assert "private transport detail" not in json.dumps(private, sort_keys=True)
    assert public["resource_totals"]["actor_call_count"] == 0
    assert public["resource_totals"]["issued_http_post_count"] == 0


def test_immediate_registered_worker_exit_is_classified_before_frame_read(
    tmp_path: Path,
) -> None:
    protocol, selection, pool, locator, asset = _fixture(tmp_path)

    class ImmediatePreframeProcess(_Process):
        def poll(self) -> int:
            return 44

        def wait(self, timeout: float) -> int:
            del timeout
            self.closed = True
            return 44

    private, public = run_b0_calibration(
        protocol=protocol,
        private_selection_receipt=selection,
        pool_manifest=pool,
        local_locator=locator,
        asset_root=asset,
        sandbox_spec_factory=_factory(tmp_path),
        runtime_launcher=lambda spec: ImmediatePreframeProcess(
            uid=spec.episode_uid,
            source_sha=spec.game_binding.file_sha256,
        ),
        actor=_FakeActor(),
        frame_reader=lambda *_args, **_kwargs: pytest.fail("must not read a frame"),
    )
    failure = private["episode_prefix"][0]
    assert failure["preframe_failure_phase"] == "ENVIRONMENT_RESET"
    assert failure["error"] == "runtime refused before initial actor frame"
    assert public["resource_totals"]["actor_call_count"] == 0


def test_nonterminal_step_20_refuses_action_21(tmp_path: Path) -> None:
    protocol, selection, pool, locator, asset = _fixture(tmp_path)
    actor = _FakeActor()

    def launcher(spec):
        return _Process(
            uid=spec.episode_uid,
            source_sha=spec.game_binding.file_sha256,
            action_steps=21,
        )

    private, public = run_b0_calibration(
        protocol=protocol,
        private_selection_receipt=selection,
        pool_manifest=pool,
        local_locator=locator,
        asset_root=asset,
        sandbox_spec_factory=_factory(tmp_path),
        runtime_launcher=launcher,
        actor=actor,
        frame_reader=_reader,
    )
    assert private["status"] == INCONCLUSIVE_STATUS
    assert actor.request_counts == (20, 20)
    assert public["resource_totals"]["issued_completion_post_count"] == 20


def test_history_is_episode_local_and_never_contains_outcome(tmp_path: Path) -> None:
    protocol, selection, pool, locator, asset = _fixture(tmp_path)
    actor = _FakeActor()

    def launcher(spec):
        return _Process(
            uid=spec.episode_uid,
            source_sha=spec.game_binding.file_sha256,
            action_steps=2,
        )

    private, _ = run_b0_calibration(
        protocol=protocol,
        private_selection_receipt=selection,
        pool_manifest=pool,
        local_locator=locator,
        asset_root=asset,
        sandbox_spec_factory=_factory(tmp_path),
        runtime_launcher=launcher,
        actor=actor,
        frame_reader=_reader,
    )
    assert private["status"] == COMPLETE_STATUS
    first_calls = [row for row in actor.received if row["step_index"] == 0]
    second_calls = [row for row in actor.received if row["step_index"] == 1]
    assert len(first_calls) == len(second_calls) == 12
    assert all(row["history"] == () for row in first_calls)
    assert all(
        row["history"]
        == ({"observation": "observation-0", "action": "look"},)
        for row in second_calls
    )
    assert all(
        "outcome" not in json.dumps(row, sort_keys=True).lower()
        for row in actor.received
    )


def test_actor_transport_failure_records_issued_prefix(tmp_path: Path) -> None:
    protocol, selection, pool, locator, asset = _fixture(tmp_path)
    actor = _FakeActor(fail_call=2)
    private, public = run_b0_calibration(
        protocol=protocol,
        private_selection_receipt=selection,
        pool_manifest=pool,
        local_locator=locator,
        asset_root=asset,
        sandbox_spec_factory=_factory(tmp_path),
        runtime_launcher=lambda spec: _Process(
            uid=spec.episode_uid, source_sha=spec.game_binding.file_sha256
        ),
        actor=actor,
        frame_reader=_reader,
    )
    assert private["status"] == INCONCLUSIVE_STATUS
    assert public["resource_totals"]["issued_tokenize_post_count"] == 2
    assert public["resource_totals"]["issued_completion_post_count"] == 1
    assert private["episode_prefix"][-1]["failed_actor_attempt"] is not None


def test_calibration_forwards_one_absolute_deadline_to_every_actor_call(
    tmp_path: Path,
) -> None:
    protocol, selection, pool, locator, asset = _fixture(tmp_path)
    actor = _FakeActor()

    class Clock:
        def __call__(self) -> float:
            return 50.0

    clock = Clock()
    private, _ = run_b0_calibration(
        protocol=protocol,
        private_selection_receipt=selection,
        pool_manifest=pool,
        local_locator=locator,
        asset_root=asset,
        sandbox_spec_factory=_factory(tmp_path),
        runtime_launcher=lambda spec: _Process(
            uid=spec.episode_uid, source_sha=spec.game_binding.file_sha256
        ),
        actor=actor,
        frame_reader=_reader,
        monotonic=clock,
    )
    assert private["status"] == COMPLETE_STATUS
    assert actor.deadline_calls
    assert all(deadline == 36_050.0 for deadline, _ in actor.deadline_calls)
    assert all(observed_monotonic is clock for _, observed_monotonic in actor.deadline_calls)


def test_protocol_runtime_drift_is_rejected() -> None:
    protocol = json.loads(PROTOCOL.read_bytes())
    protocol["model_runtime"]["byte_exactness_required"] = True
    with pytest.raises(AlfworldB0CalibrationError, match="executable contract"):
        verify_protocol(protocol)
