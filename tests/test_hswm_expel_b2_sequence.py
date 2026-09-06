from __future__ import annotations

from hashlib import sha256
import io
import json
from pathlib import Path
from typing import Any, Callable, Mapping

import pytest

from _research.dnrd5.canonical_json import canonical_bytes
from hswm.experiments.alfworld_text_runtime import LocalGameBinding, LocalSandboxSpec
from hswm.experiments.alfworld_text_worker import actor_projection, build_outcome
from hswm.experiments.continual_live import ModelCompletion, STRUCTURED_OUTPUT_MODE, TOKEN_PREFLIGHT_MODE, TokenPreflightReceipt
from hswm.experiments.expel_b2_selection import select_prospective_b2
from hswm.experiments.expel_b2_sequence import B2SequenceError, run_b2_sequence
from hswm.experiments.expel_b2_transport import ExpelB2Transport


class FakeBackend:
    def __init__(self, *, reflection: str = '{"rule":"Inspect before acting."}', usage: bool = True) -> None:
        self.reflection, self.usage = reflection, usage

    @property
    def identity(self) -> Mapping[str, Any]:
        return {"enable_thinking": False, "expected_max_model_len": 4096, "model": "fake", "response_format_mode": STRUCTURED_OUTPUT_MODE, "seed": 0, "temperature": 0.0, "token_preflight_mode": TOKEN_PREFLIGHT_MODE, "top_p": 1.0, "timeout_seconds": 10.0}

    def tokenize(self, *, raw_request: bytes, source_chat_request_sha256: str, max_output_tokens: int, request_id: str, response_observer: Callable[..., None]) -> TokenPreflightReceipt:
        raw = canonical_bytes({"count": 5, "max_model_len": 4096, "token_strs": None, "tokens": [1] * 5})
        response_observer(raw_request, raw, 200, True)
        return TokenPreflightReceipt.make(raw_request=raw_request, raw_response=raw, source_chat_request_sha256=source_chat_request_sha256, max_output_tokens=max_output_tokens, http_status=200, latency_ms=1, raw_response_complete=True)

    def complete(self, *, raw_request: bytes, request_id: str, response_observer: Callable[..., None]) -> ModelCompletion:
        schema = json.loads(raw_request)["response_format"]["json_schema"]["name"]
        text = self.reflection if schema == "hswm_expel_b2_reflection" else '{"action":"look"}'
        response = canonical_bytes({"choices": [{"finish_reason": "stop", "message": {"content": text}}], "model": "fake", "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7}})
        response_observer(raw_request, response)
        return ModelCompletion(text=text, raw_request_json=raw_request.decode(), raw_response_json=response.decode(), request_sha256=sha256(raw_request).hexdigest(), response_sha256=sha256(response).hexdigest(), model="fake", input_tokens=5 if self.usage else None, output_tokens=2 if self.usage else None, latency_ms=1, usage_reported=self.usage)


class Process:
    def __init__(self, uid: str, digest: str, *, success: bool = True, forged: bool = False, malformed: bool = False) -> None:
        action = sha256(b"look").hexdigest()
        observations = [sha256(b"room").hexdigest(), sha256(b"done").hexdigest()]
        outcome = build_outcome(episode_uid=uid, action_digests=[action], observation_digests=observations, done=True, won=success, score=int(success), source_game_sha256=digest)
        if forged:
            outcome["action_digests_sha256"] = "a" * 64
        self.stdin = io.BytesIO()
        self.stdout = io.BytesIO(canonical_bytes(actor_projection(episode_uid=uid, observation="room", step_index=0, done=False)) + b"\n" + canonical_bytes(actor_projection(episode_uid=uid, observation="done", step_index=1, done=True)) + b"\n")
        self.stderr = io.BytesIO((b"{}\n" if malformed else canonical_bytes(outcome) + b"\n"))
    def poll(self): return None
    def wait(self, timeout=None): return 0
    def terminate(self): pass


def _inputs(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    asset = tmp_path / "assets"; asset.mkdir()
    records = []
    for split, total in (("train", 9), ("valid_seen", 5), ("valid_unseen", 3)):
        for i in range(total):
            uid, rel = f"{split}:{i}", f"{split}/{i}.tw-pddl"; path = asset / rel; path.parent.mkdir(exist_ok=True); path.write_bytes(uid.encode())
            records.append({"bytes": len(uid), "file_sha256": sha256(uid.encode()).hexdigest(), "opaque_uid": uid, "relative_path": rel, "relative_path_sha256": sha256(rel.encode()).hexdigest(), "split": split, "task_group_uid": f"group:{split}:{i}"})
    counts = {s: sum(x["split"] == s for x in records) for s in ("train", "valid_seen", "valid_unseen")}; groups = counts.copy()
    commitment = {"selected_game_counts": counts, "selected_game_bytes_by_split": {s: sum(x["bytes"] for x in records if x["split"] == s) for s in counts}, "selected_task_group_counts": groups, "task_group_overlap_counts": {}, "selected_game_total": len(records)}
    locator = {"schema_version": "hswm-alfworld-text-clean-pool-local-locator/v1", "record_role": "LOCAL", "source_binding": {"repository_commit": "a" * 40, "assets": []}, "pool_commitment": commitment, "records": records}
    locator_path = tmp_path / "locator.json"; locator_path.write_bytes(json.dumps(locator, sort_keys=True).encode())
    manifest = {"schema_version": "hswm-alfworld-text-clean-pool/v2", "aggregate_commitment": {**commitment, "local_locator_rendered_json_sha256": sha256(locator_path.read_bytes()).hexdigest(), "local_locator_canonical_json_sha256": sha256(canonical_bytes(locator)).hexdigest()}, "source_binding": {"repository_commit": "a" * 40, "official_release_assets": []}}
    pool = tmp_path / "pool.json"; pool.write_bytes(json.dumps(manifest, sort_keys=True).encode())
    selection = select_prospective_b2(pool_manifest=pool.absolute(), local_locator=locator_path.absolute(), occurrence_uid="sym:Occurrence:b2", protocol_uid="sym:Study:b2", protocol_version="v1", protocol_sha256="b" * 64, expected_pool_manifest_sha256=sha256(pool.read_bytes()).hexdigest(), expected_local_locator_sha256=sha256(locator_path.read_bytes()).hexdigest())
    return selection, pool, locator_path, asset


def _spec(row, binding, game, pool_sha, locator_sha):
    # Fields used by the sequence only; no sandbox is started by this fake runtime.
    return LocalSandboxSpec(Path("/bin/true"), Path("/bin/true"), Path("/"), Path("/tmp"), Path("/tmp"), Path("/tmp"), game.parents[1], game, pool_sha, locator_sha, binding, row.opaque_uid, max_steps=20)


def _run(tmp_path: Path, backend: FakeBackend, **process_kwargs):
    selection, pool, locator, asset = _inputs(tmp_path)
    out = tmp_path / "out"; out.mkdir()
    return run_b2_sequence(selection=selection, output_root=out.absolute(), pool_manifest=pool.absolute(), local_locator=locator.absolute(), asset_root=asset.absolute(), transport_factory=lambda sink: ExpelB2Transport(backend, event_sink=sink), sandbox_spec_factory=_spec, runtime_launcher=lambda spec: Process(spec.episode_uid, spec.game_binding.file_sha256, **process_kwargs), frame_reader=lambda stream, **_: stream.readline())


def test_complete_train_reflections_freeze_and_consistent_eval_lesson(tmp_path: Path) -> None:
    private, public = _run(tmp_path, FakeBackend())
    assert private["status"].startswith("B2_SEQUENCE_COMPLETE") and len(private["episodes"]) == 12, private["episodes"][0].get("error")
    assert private["retained_rule_count"] == 1 and private["frozen_state_sha256"]
    assert public["splits"]["valid_seen"]["completed"] == 4


def test_failed_reflection_preserves_prefix_and_does_not_enter_eval(tmp_path: Path) -> None:
    private, _ = _run(tmp_path, FakeBackend(reflection='{"rule":"bad\\nrule"}'))
    assert private["status"] == "INCONCLUSIVE_MEASUREMENT_NOT_READY"
    assert len(private["episodes"]) == 1 and private["episodes"][0]["outcome"]["success"] is True
    assert private["request_counts"]["reflection_completion"] == 1 and private["frozen_state_sha256"] is None


def test_forged_trace_outcome_has_no_reflection(tmp_path: Path) -> None:
    private, _ = _run(tmp_path, FakeBackend(), forged=True)
    assert private["status"] == "INCONCLUSIVE_MEASUREMENT_NOT_READY"
    assert private["request_counts"]["reflection_tokenize"] == 0


def test_malformed_terminal_has_no_reflection(tmp_path: Path) -> None:
    private, _ = _run(tmp_path, FakeBackend(), malformed=True)
    assert private["status"] == "INCONCLUSIVE_MEASUREMENT_NOT_READY"
    assert private["request_counts"]["reflection_tokenize"] == 0


def test_root_refuses_resume_and_unknown_usage_is_not_zero(tmp_path: Path) -> None:
    selection, pool, locator, asset = _inputs(tmp_path)
    out = tmp_path / "out"; out.mkdir(); (out / "prior").write_text("x")
    with pytest.raises(B2SequenceError, match="fresh absolute"):
        run_b2_sequence(selection=selection, output_root=out.absolute(), pool_manifest=pool.absolute(), local_locator=locator.absolute(), asset_root=asset.absolute(), transport_factory=lambda sink: ExpelB2Transport(FakeBackend(), event_sink=sink), sandbox_spec_factory=_spec, runtime_launcher=lambda spec: Process(spec.episode_uid, spec.game_binding.file_sha256), frame_reader=lambda stream, **_: stream.readline())
    private, _ = _run(tmp_path / "unknown", FakeBackend(usage=False))
    assert private["usage"]["completion"]["input_tokens"]["unknown_request_count"] > 0
