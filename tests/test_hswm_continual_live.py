from __future__ import annotations

import base64
from dataclasses import replace
from hashlib import sha256
import io
import json
from pathlib import Path
import tarfile
from typing import Any, Callable, Mapping, Sequence

import pytest

from hswm.experiments import continual_live as live

from hswm.experiments.continual import (
    LearningBatch,
    PublicLearningToken,
    PublicProbe,
    deterministic_test_seed,
    generate_stream,
)
from hswm.experiments.continual_live import (
    ArmBudget,
    ContinualLiveError,
    GENESIS,
    ModelCompletion,
    OpenAICompatibleBackend,
    StructuredHSWMArm,
    audit_parity,
    build_four_arms,
    main,
    make_sealed_probe_pack,
    run_four_arm_stream,
    run_public_schema_gate,
    run_removal_restore_probes,
    schema_gate_main,
)
from hswm.selfmod.contracts import canonical_json_bytes


TOKEN_PREFLIGHT_SUCCESS_EVENTS = [
    "intent",
    "tokenize_intent",
    "tokenize_raw_response_received",
    "tokenize_accepted",
    "generation_dispatch_intent",
]


class ScriptedRelationalBackend:
    """Stateless fixture whose only input is the recorded chat request."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.tokenize_requests: list[dict[str, Any]] = []
        self._preflight_counts: dict[str, int] = {}

    @property
    def identity(self) -> Mapping[str, Any]:
        return {
            "adapter": "scripted-relational/v1",
            "enable_thinking": False,
            "expected_max_model_len": 32768,
            "model": "deterministic-fixture",
            "response_format_mode": live.STRUCTURED_OUTPUT_MODE,
            "seed": 0,
            "temperature": 0.0,
            "token_preflight_mode": live.TOKEN_PREFLIGHT_MODE,
            "token_preflight_transport_trust": "scripted-test-double",
            "top_p": 1.0,
        }

    def tokenize(
        self,
        *,
        raw_request: bytes,
        source_chat_request_sha256: str,
        max_output_tokens: int,
        request_id: str,
        response_observer: Callable[[bytes, bytes, int | None, bool], None],
    ) -> live.TokenPreflightReceipt:
        request_value = json.loads(raw_request)
        count = max(1, len(raw_request) // 64)
        max_model_len = live.PUBLIC_SCHEMA_GATE_CONTEXT_WINDOW_TOKENS
        raw_response = canonical_json_bytes(
            {
                "count": count,
                "max_model_len": max_model_len,
                "token_strs": None,
                "tokens": list(range(count)),
            }
        )
        self.tokenize_requests.append(
            {
                "max_output_tokens": max_output_tokens,
                "request": request_value,
                "request_id": request_id,
                "source_chat_request_sha256": source_chat_request_sha256,
            }
        )
        self._preflight_counts[source_chat_request_sha256] = count
        response_observer(raw_request, raw_response, 200, True)
        return live.TokenPreflightReceipt.make(
            raw_request=raw_request,
            raw_response=raw_response,
            source_chat_request_sha256=source_chat_request_sha256,
            max_output_tokens=max_output_tokens,
            http_status=200,
            latency_ms=0,
            raw_response_complete=True,
        )

    @staticmethod
    def _edges_from_hswm(state: Mapping[str, Any]) -> dict[tuple[str, str], str]:
        result: dict[tuple[str, str], str] = {}
        for memory in state["memories"]:
            content = memory["content"]
            if memory["kind"] == "atomic_relation":
                result[(content["source"], content["relation"])] = content["target"]
        return result

    @staticmethod
    def _edges_from_plain(memory: str) -> dict[tuple[str, str], str]:
        result: dict[tuple[str, str], str] = {}
        for line in memory.splitlines():
            parts = line.split(" ")
            if len(parts) == 3:
                result[(parts[0], parts[1])] = parts[2]
        return result

    @staticmethod
    def _answer(payload: Mapping[str, Any]) -> str:
        probe = payload["probe"]
        if payload["state_kind"] == "bounded_plain_text":
            edges = ScriptedRelationalBackend._edges_from_plain(payload["state"])
        else:
            edges = ScriptedRelationalBackend._edges_from_hswm(payload["state"])
        node = probe["source"]
        for relation in probe["relations"]:
            target = edges.get((node, relation))
            if target is None:
                node = probe["choices"][0]
                break
            node = target
        if node not in probe["choices"]:
            node = probe["choices"][0]
        return json.dumps({"choice": node}, separators=(",", ":"))

    @staticmethod
    def _author(payload: Mapping[str, Any]) -> str:
        active = payload["current_hswm_indexed_read_only"]
        existing = list(active["memories"])
        source_tokens = payload["public_source_tokens"]
        new_relations: list[dict[str, Any]] = []
        for source_token in payload["public_source_tokens"]:
            content = source_token["content"]
            related_existing = [
                item["memory_id"]
                for item in existing
                if item["content"].get("source") == content["target"]
            ]
            related_new = sorted(
                other["suggested_memory_id"]
                for other in source_tokens
                if other["content"].get("source") == content["target"]
                and other["suggested_memory_id"]
                != source_token["suggested_memory_id"]
            )
            new_relations.append(
                {
                    "related_memory_ids": related_existing + related_new,
                }
            )
        cell_width = live.MAX_CELL_MEMORY_REFERENCES
        existing_cell_indices = [
            index // cell_width for index in range(len(existing))
        ]
        new_cell_indices = [
            (len(existing) + index) // cell_width
            for index in range(len(source_tokens))
        ]
        cell_count = max(
            1, (len(existing) + len(source_tokens) + cell_width - 1) // cell_width
        )
        cell_ids = [f"cell:lookup:{index}" for index in range(cell_count)]
        cells = []
        for index in range(cell_count):
            cells.append(
                {
                    "capability": "nonce_graph_lookup",
                    "cell_id": cell_ids[index],
                    "executor_agent_id": None,
                    "instruction": "Traverse the absorbed atomic relations.",
                    "next_cell_indices": (
                        [index + 1] if index + 1 < cell_count else []
                    ),
                }
            )
        response = {
            "cells": cells,
            "entry_cell_index": 0,
            "existing_memory_cell_indices": existing_cell_indices,
            "new_memory_cell_indices": new_cell_indices,
            "new_memory_relations": new_relations,
            "rationale": "Absorb each public atomic relation into the HSWM cells.",
        }
        return json.dumps(response, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _plain(payload: Mapping[str, Any]) -> str:
        lines = {
            line
            for line in payload["current_memory"].splitlines()
            if line.strip()
        }
        for token in payload["public_learning_tokens"]:
            lines.add(f"{token['source']} {token['relation']} {token['target']}")
        return json.dumps(
            {"memory": "\n".join(sorted(lines))},
            sort_keys=True,
            separators=(",", ":"),
        )

    def complete(
        self,
        *,
        raw_request: bytes,
        request_id: str,
        response_observer: Callable[[bytes, bytes], None],
    ) -> ModelCompletion:
        request_value = json.loads(raw_request)
        messages = request_value["messages"]
        max_output_tokens = request_value["max_tokens"]
        response_format = request_value["response_format"]
        response_schema = live.JSONSchemaContract.make(
            response_format["json_schema"]["name"],
            response_format["json_schema"]["schema"],
        )
        assert response_format == response_schema.response_format()
        payload = json.loads(messages[-1]["content"])
        self.requests.append(
            {
                "max_output_tokens": max_output_tokens,
                "payload": payload,
                "request_id": request_id,
                "response_schema": response_schema.canonical(),
                "system": messages[0]["content"],
            }
        )
        operation = payload["operation"]
        if operation == "answer":
            text = self._answer(payload)
        elif operation == "author_hswm_compact_patch":
            text = self._author(payload)
        elif operation == "update_plain_memory":
            text = self._plain(payload)
        else:
            raise AssertionError(operation)
        input_tokens = self._preflight_counts[sha256(raw_request).hexdigest()]
        output_tokens = max(1, len(text.encode()) // 4)
        raw_response = canonical_json_bytes(
            {
                "choices": [
                    {"finish_reason": "stop", "message": {"content": text}}
                ],
                "model": "deterministic-fixture",
                "usage": {
                    "completion_tokens": output_tokens,
                    "prompt_tokens": input_tokens,
                    "total_tokens": input_tokens + output_tokens,
                },
            }
        )
        response_observer(raw_request, raw_response)
        return ModelCompletion(
            text=text,
            raw_request_json=raw_request.decode("utf-8"),
            raw_response_json=raw_response.decode("utf-8"),
            request_sha256=sha256(raw_request).hexdigest(),
            response_sha256=sha256(raw_response).hexdigest(),
            model="deterministic-fixture",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=0,
            usage_reported=True,
        )


class FirstResponseGateViolationBackend(ScriptedRelationalBackend):
    """Return a valid compact body with one frozen gate-envelope violation."""

    def __init__(self, violation: str) -> None:
        super().__init__()
        self.violation = violation

    def complete(
        self,
        *,
        raw_request: bytes,
        request_id: str,
        response_observer: Callable[[bytes, bytes], None],
    ) -> ModelCompletion:
        observed: list[tuple[bytes, bytes]] = []
        completion = super().complete(
            raw_request=raw_request,
            request_id=request_id,
            response_observer=lambda request, response: observed.append(
                (request, response)
            ),
        )
        raw_request, raw_response = observed[0]
        envelope = json.loads(raw_response)
        if self.violation == "length":
            envelope["choices"][0]["finish_reason"] = "length"
            output_tokens = completion.output_tokens
        elif self.violation == "headroom":
            output_tokens = 7000
            envelope["usage"]["completion_tokens"] = output_tokens
            envelope["usage"]["total_tokens"] = (
                completion.input_tokens + output_tokens
            )
        else:  # pragma: no cover - test construction guard
            raise AssertionError(self.violation)
        changed_response = canonical_json_bytes(envelope)
        response_observer(raw_request, changed_response)
        return ModelCompletion(
            text=completion.text,
            raw_request_json=raw_request.decode("utf-8"),
            raw_response_json=changed_response.decode("utf-8"),
            request_sha256=sha256(raw_request).hexdigest(),
            response_sha256=sha256(changed_response).hexdigest(),
            model=completion.model,
            input_tokens=completion.input_tokens,
            output_tokens=output_tokens,
            latency_ms=completion.latency_ms,
            usage_reported=True,
        )


def _budget() -> ArmBudget:
    return ArmBudget(
        answer_max_output_tokens=128,
        update_max_output_tokens=8192,
        max_input_bytes=2_000_000,
        max_state_bytes=1_000_000,
    )


def _one_token_batch() -> LearningBatch:
    return LearningBatch(
        episode_id="episode-one-token",
        after_step=0,
        chosen=None,
        correct=False,
        learning_tokens=(PublicLearningToken("node-a", "rel-x", "node-b"),),
    )


def _small_stream():
    return generate_stream(
        0,
        seed_preimage=deterministic_test_seed(991),
        horizon=4,
        delay=1,
        choice_count=4,
        entity_count=24,
        relation_count=3,
        warmup_edges=24,
        reveal_batch=4,
    )


def _write_test_precommit(
    path: Path,
    seeds: Sequence[bytes],
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[str, ...]:
    commitments = tuple(sha256(seed).hexdigest() for seed in seeds)
    commitment_document = {
        "commitments": list(commitments),
        "protocol": "nonce-graph-prequential/v1",
        "purpose": "engineering-pilot-only-never-confirmatory",
        "schema": "hswm-continual-pilot-seed-commitments/v1",
    }
    assignment_document = {
        "primary": list(commitments[:2]),
        "protocol": "nonce-graph-prequential/v1",
        "purpose": "engineering-pilot-only-never-confirmatory",
        "reserve": list(commitments[2:]),
        "reserve_rule": "mechanical infrastructure invalidity only; never outcome-conditioned",
        "resume_rule": "no retry or resume with a revealed preimage",
        "schema": "hswm-continual-pilot-seed-assignment/v1",
    }
    value: dict[str, Any] = {
        "assignment_document": assignment_document,
        "assignment_sha256": live.canonical_sha256(assignment_document),
        "commitment_document": commitment_document,
        "commitment_set_sha256": live.canonical_sha256(commitment_document),
        "confirmatory_denylist": list(commitments),
        "confirmatory_eligible": False,
        "engineering_only": True,
        "frozen_before_pilot_completion_calls": True,
        "intended_provider": {
            "enable_thinking": False,
            "endpoint": "http://model.invalid",
            "model_revision": "a" * 40,
            "model_root": "fixture/root",
            "served_model": "fixture-model",
            "temperature": 0.0,
            "vllm_version": "test",
        },
        "preimages_revealed": False,
        "primary_execution": {
            "answer_max_tokens": 128,
            "arms": ["hswm", "reset", "no_write", "plain"],
            "base_endpoint_calls_per_stream": 164,
            "choice_count": 8,
            "delay": 4,
            "endpoint_call_budget_total": 358,
            "endpoint_calls_per_stream": 179,
            "horizon": 20,
            "max_input_bytes": 2_000_000,
            "max_state_bytes": 1_000_000,
            "per_call_timeout_seconds": 120.0,
            "removal_restore": True,
            "removal_restore_extra_calls_per_stream": 15,
            "removal_restore_probes_per_stream": 5,
            "resume_allowed": False,
            "retry_limit": 0,
            "streams": 2,
            "update_max_tokens": 8192,
        },
        "primary_seed_indices": [0, 1],
        "protocol": "nonce-graph-prequential/v1",
        "reserve_seed_indices": [2, 3],
        "schema": "hswm-continual-pilot-precommit/v2",
        "seed_preimage_encoding": "32 raw bytes; commitment=sha256(raw bytes)",
        "supersedes_canonical_artifact_sha256": "b" * 64,
        "supersession_reason": "fixture exceeded 4096; freeze 8192 before calls",
    }
    value["precommit_sha256"] = live.canonical_sha256(value)
    raw = canonical_json_bytes(value)
    path.write_bytes(raw)
    monkeypatch.setattr(
        live, "FROZEN_PILOT_PRECOMMIT_ARTIFACT_SHA256", sha256(raw).hexdigest()
    )
    monkeypatch.setattr(
        live, "FROZEN_PILOT_PRECOMMIT_SHA256", value["precommit_sha256"]
    )
    return commitments


def _json_artifact(value: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def _write_failed_primary_fixture(
    tmp_path: Path,
    *,
    seeds: Sequence[bytes],
    v2_precommit_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, Path, dict[str, Any]]:
    commitments = [sha256(seed).hexdigest() for seed in seeds]
    v2_raw = v2_precommit_path.read_bytes()
    prereg: dict[str, Any] = {
        "precommit_artifact_sha256": sha256(v2_raw).hexdigest(),
        "selected_seed_indices": [0, 1],
    }
    prereg["prereg_sha256"] = live.canonical_sha256(prereg)
    reveal: dict[str, Any] = {
        "ordered_seed_commitments": commitments,
        "selected_seed_indices": [0, 1],
        "used_seeds": [
            {"frozen_index": index, "seed_hex": seeds[index].hex()}
            for index in (0, 1)
        ],
    }
    reveal["reveal_sha256"] = live.canonical_sha256(reveal)
    post_reveal: dict[str, Any] = {"valid": False}
    post_reveal["validation_sha256"] = live.canonical_sha256(post_reveal)
    timeout_error = (
        "ContinualLiveError: model call outcome unknown; no retry: timed out"
    )
    status = {
        "completed_streams": 0,
        "error": timeout_error,
        "status": "failed",
    }
    request_id = "cl-first-timeout"
    journal = b"".join(
        _json_artifact(event)
        for event in (
            {
                "arm": "hswm",
                "backend": {"timeout_seconds": 120.0},
                "event": "intent",
                "max_output_tokens": 8192,
                "operation": "update",
                "ordinal": 0,
                "request_id": request_id,
            },
            {
                "arm": "hswm",
                "error": timeout_error,
                "event": "failed",
                "operation": "update",
                "ordinal": 0,
                "outcome": "unknown",
                "request_id": request_id,
                "retry_permitted": False,
            },
        )
    )
    pilot_files = {
        "frozen_precommit.canonical.json": v2_raw,
        "post_reveal_validation.json": _json_artifact(post_reveal),
        "preregistration.json": _json_artifact(prereg),
        "seed_reveal.json": _json_artifact(reveal),
        "state/stream-00/hswm/calls.jsonl": journal,
        "status.json": _json_artifact(status),
    }
    terminal: dict[str, Any] = {
        "artifact_sha256s": {
            name: sha256(raw).hexdigest() for name, raw in pilot_files.items()
        },
        "completed_streams": 0,
        "engineering_only": True,
        "error": timeout_error,
        "removal_mediation_gate_passed": None,
        "protocol": live.LIVE_PROTOCOL,
        "status": "failed",
    }
    terminal["receipt_sha256"] = live.canonical_sha256(terminal)
    terminal_raw = _json_artifact(terminal)
    pilot_files["terminal_receipt.json"] = terminal_raw

    identity = {"endpoint": "http://model.invalid", "model": "fixture-model"}
    identity_sha256 = live.canonical_sha256(identity)
    before = {
        "identity": identity,
        "identity_sha256": identity_sha256,
        "phase": "before",
    }
    after = {**before, "phase": "after"}
    before_raw = canonical_json_bytes(before)
    after_raw = canonical_json_bytes(after)
    monkeypatch.setattr(
        live, "FAILED_SERVICE_BEFORE_ARTIFACT_SHA256", sha256(before_raw).hexdigest()
    )
    monkeypatch.setattr(
        live, "FAILED_SERVICE_AFTER_ARTIFACT_SHA256", sha256(after_raw).hexdigest()
    )
    wrapper = {
        "after_capture_exit_code": 0,
        "after_identity_sha256": identity_sha256,
        "before_identity_sha256": identity_sha256,
        "identity_unchanged": True,
        "pilot_exit_code": 1,
        "schema": "hswm-continual-live-ops-wrapper/v1",
    }
    wrapper_raw = canonical_json_bytes(wrapper)

    archive_path = tmp_path / "failed-artifacts.tar"
    all_files = {
        **{f"outputs/pilot/{name}": raw for name, raw in pilot_files.items()},
        "outputs/ops/service.before.canonical.json": before_raw,
        "outputs/ops/service.after.canonical.json": after_raw,
        "outputs/ops/wrapper_terminal.canonical.json": wrapper_raw,
    }
    with tarfile.open(archive_path, "w") as archive:
        for name, raw in sorted(all_files.items()):
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            info.mtime = 0
            archive.addfile(info, io.BytesIO(raw))

    tar_sha256 = sha256(archive_path.read_bytes()).hexdigest()
    outer_receipt = {
        "artifact": {
            "bytes": archive_path.stat().st_size,
            "name": "artifacts.tar",
            "sha256": tar_sha256,
        },
        "command_sha256": "f" * 64,
        "durable_tier": "data01-4tb-nfs",
        "execution_tier": "dgx-nvme",
        "exit_code": 1,
        "finished_at": "2026-08-17T16:16:14Z",
        "run_id": "fixture-r2-timeout",
        "schema": "bhgman-hswm-run/v1",
        "source_commit": "c" * 40,
        "source_root": "/fixture/source",
        "started_at": "2026-08-17T16:14:13Z",
        "status": "failed",
    }
    receipt_path = tmp_path / "failed-receipt.json"
    receipt_raw = _json_artifact(outer_receipt)
    receipt_path.write_bytes(receipt_raw)
    binding = {
        "artifacts_tar_sha256": tar_sha256,
        "completed_model_responses": 0,
        "completed_streams": 0,
        "endpoint_calls_observed": 1,
        "failed_call_journal_sha256": sha256(journal).hexdigest(),
        "failed_run_id": "fixture-r2-timeout",
        "failed_source_revision": "c" * 40,
        "failure_class": "mechanical_timeout_before_response",
        "frozen_v2_precommit_artifact_sha256": sha256(v2_raw).hexdigest(),
        "outer_receipt_sha256": sha256(receipt_raw).hexdigest(),
        "output_terminal_file_sha256": sha256(terminal_raw).hexdigest(),
        "post_reveal_file_sha256": sha256(pilot_files["post_reveal_validation.json"]).hexdigest(),
        "post_reveal_validation_sha256": post_reveal["validation_sha256"],
        "preregistration_file_sha256": sha256(pilot_files["preregistration.json"]).hexdigest(),
        "preregistration_sha256": prereg["prereg_sha256"],
        "retry_permitted": False,
        "score_artifacts_written": False,
        "seed_reveal_file_sha256": sha256(pilot_files["seed_reveal.json"]).hexdigest(),
        "service_identity_sha256": identity_sha256,
        "status_file_sha256": sha256(pilot_files["status.json"]).hexdigest(),
        "terminal_receipt_sha256": terminal["receipt_sha256"],
        "usable_model_responses": 0,
        "wrapper_terminal_file_sha256": sha256(wrapper_raw).hexdigest(),
    }
    return archive_path, receipt_path, binding


def _write_test_recovery_precommit(
    path: Path,
    *,
    seeds: Sequence[bytes],
    binding: Mapping[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    selected_seed_indices: Sequence[int] = (2, 3),
) -> tuple[str, ...]:
    fixture = (
        Path(__file__).parent
        / "fixtures"
        / "pilot_recovery_precommit_v3.canonical.json"
    )
    value = json.loads(fixture.read_bytes())
    commitments = tuple(sha256(seed).hexdigest() for seed in seeds)
    value["commitment_document"]["commitments"] = list(commitments)
    value["commitment_set_sha256"] = live.canonical_sha256(
        value["commitment_document"]
    )
    value["assignment_document"]["primary"] = list(commitments[:2])
    value["assignment_document"]["reserve"] = list(commitments[2:])
    value["assignment_sha256"] = live.canonical_sha256(value["assignment_document"])
    value["confirmatory_denylist"] = list(commitments)
    value["primary_seed_commitment_denylist"] = list(commitments[:2])
    value["selected_seed_indices"] = list(selected_seed_indices)
    value["failed_primary_binding"] = dict(binding)
    value["supersedes_canonical_artifact_sha256"] = binding[
        "frozen_v2_precommit_artifact_sha256"
    ]
    value["intended_provider"] = {
        "enable_thinking": False,
        "endpoint": "http://model.invalid",
        "model_revision": "a" * 40,
        "model_root": "fixture/root",
        "served_model": "fixture-model",
        "temperature": 0.0,
        "vllm_version": "test",
    }
    value.pop("precommit_sha256")
    value["precommit_sha256"] = live.canonical_sha256(value)
    raw = canonical_json_bytes(value)
    path.write_bytes(raw)
    monkeypatch.setattr(
        live, "FROZEN_RECOVERY_PRECOMMIT_ARTIFACT_SHA256", sha256(raw).hexdigest()
    )
    monkeypatch.setattr(
        live, "FROZEN_RECOVERY_PRECOMMIT_SHA256", value["precommit_sha256"]
    )
    return commitments


def _all_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            child
            for item in value.values()
            for child in _all_keys(item)
        }
    if isinstance(value, list):
        return {child for item in value for child in _all_keys(item)}
    return set()


def test_four_arms_use_isolated_states_and_public_only_requests(tmp_path: Path) -> None:
    backends: list[ScriptedRelationalBackend] = []

    def factory() -> ScriptedRelationalBackend:
        backend = ScriptedRelationalBackend()
        backends.append(backend)
        return backend

    manifest = _small_stream()
    run, audit, arms = run_four_arm_stream(
        manifest,
        backend_factory=factory,
        budget=_budget(),
        state_dir=tmp_path / "states",
    )

    assert run.arm_names == ("hswm", "reset", "no_write", "plain")
    assert audit.call_parity and audit.usage_complete and audit.config_parity
    assert audit.valid and not audit.exact_input_token_parity
    assert [len(arm.ledger) for arm in arms] == [9, 9, 9, 9]
    assert arms[0].state_canonical_bytes() != canonical_json_bytes(GENESIS.canonical())
    assert arms[1].state_canonical_bytes() == canonical_json_bytes(GENESIS.canonical())
    assert arms[2].state_canonical_bytes() == canonical_json_bytes(GENESIS.canonical())
    assert arms[3].state_canonical_bytes() != canonical_json_bytes(
        {"memory": "", "schema": "linear-plain-memory/v1"}
    )
    assert len({arm.store_path for arm in arms[:3]}) == 3

    for backend in backends:
        for request in backend.requests:
            keys = _all_keys(request["payload"])
            assert "answer" not in keys
            assert "support_edge_ids" not in keys
            assert "support_reveal_steps" not in keys

    first_entry = arms[0].ledger[0]
    assert (
        json.loads(first_entry.request_payload_json)["operation"]
        == "author_hswm_compact_patch"
    )
    assert first_entry.canonical()["completion"]["text"] == first_entry.completion.text


def test_prequential_answers_are_read_only_and_sqlite_cas_advances(tmp_path: Path) -> None:
    backend = ScriptedRelationalBackend()
    arm = StructuredHSWMArm(
        backend=backend,
        budget=_budget(),
        isolation_id="read-only",
        store_path=tmp_path / "state.sqlite3",
    )
    batch = LearningBatch(
        episode_id="episode-x",
        after_step=0,
        chosen=None,
        correct=False,
        learning_tokens=(PublicLearningToken("n_a", "r_x", "n_b"),),
    )
    arm.update(batch)
    before = arm.state_canonical_bytes()
    answer = arm.answer(
        PublicProbe(step=1, source="n_a", relations=("r_x",), choices=("n_c", "n_b"))
    )
    assert json.loads(answer.response_text) == {"choice": "n_b"}
    assert arm.state_canonical_bytes() == before
    active = arm.store.active_snapshot()
    assert active.generation == 1
    assert arm.store.activation_count() == 1
    assert active.snapshot.memories[0].source_token_ids[0].startswith("learn-")
    assert active.snapshot.cells[0].memory_ids == (active.snapshot.memories[0].memory_id,)


def test_removal_restart_restore_is_bitwise_and_behaviorally_exact(tmp_path: Path) -> None:
    manifest = _small_stream()
    run, _audit, arms = run_four_arm_stream(
        manifest,
        backend_factory=ScriptedRelationalBackend,
        budget=_budget(),
        state_dir=tmp_path / "states",
    )
    arm = arms[0]
    probes = make_sealed_probe_pack(manifest)
    result = run_removal_restore_probes(
        arm,
        probes,
        primary_run=run,
    )
    assert result.exact_state_restore and result.exact_choice_restore
    assert result.state_dependence_observed
    assert result.removal_mediation_gate_passed
    assert all(result.active_correct) and all(result.restored_correct)
    assert result.active_score > result.deleted_score
    assert result.active_state_sha256 == result.restored_state_sha256
    assert result.primary_run_sha256 == run.run_sha256
    assert result.deleted_state_sha256 == sha256(
        canonical_json_bytes(GENESIS.canonical())
    ).hexdigest()
    assert arm.store.activation_count() == 7


def test_negative_removal_effect_is_persistable_not_an_infrastructure_error(
    tmp_path: Path,
) -> None:
    manifest = _small_stream()
    run, _audit, arms = run_four_arm_stream(
        manifest,
        backend_factory=ScriptedRelationalBackend,
        budget=_budget(),
        state_dir=tmp_path / "states",
    )
    arm = arms[0]
    learned_memories = arm.store.active_snapshot().snapshot.memories[:5]
    probes = tuple(
        (
            PublicProbe(
                step=index + 1,
                source=memory.content["source"],
                relations=(memory.content["relation"],),
                choices=(memory.content["target"], f"wrong-{index}"),
            ),
            memory.content["target"],
        )
        for index, memory in enumerate(learned_memories)
    )
    result = run_removal_restore_probes(
        arm,
        probes,
        primary_run=run,
    )
    assert result.active_score == result.deleted_score == result.restored_score == 5
    assert not result.state_dependence_observed
    assert not result.removal_mediation_gate_passed
    assert result.exact_state_restore and result.exact_choice_restore


def test_confirmatory_rejects_nonexact_observed_input_tokens(tmp_path: Path) -> None:
    arms = build_four_arms(
        backend_factory=ScriptedRelationalBackend,
        budget=_budget(),
        state_dir=tmp_path / "states",
        isolation_prefix="confirmatory",
    )
    batch = LearningBatch(
        episode_id="episode-confirmatory",
        after_step=0,
        chosen=None,
        correct=False,
        learning_tokens=(PublicLearningToken("a", "r", "b"),),
    )
    for arm in arms:
        arm.update(batch)
    audit = audit_parity(arms, confirmatory=True)
    assert audit.call_parity and audit.usage_complete and audit.config_parity
    assert not audit.exact_input_token_parity
    assert not audit.valid


def test_parity_rejects_returned_model_drift(tmp_path: Path) -> None:
    arms = build_four_arms(
        backend_factory=ScriptedRelationalBackend,
        budget=_budget(),
        state_dir=tmp_path / "states",
        isolation_prefix="model-drift",
    )
    batch = LearningBatch(
        episode_id="episode-model-drift",
        after_step=0,
        chosen=None,
        correct=False,
        learning_tokens=(PublicLearningToken("a", "r", "b"),),
    )
    for arm in arms:
        arm.update(batch)
    last = arms[-1].ledger[0]
    object.__setattr__(last.completion, "model", "different-model")
    audit = audit_parity(arms, confirmatory=False)
    assert not audit.model_parity
    assert not audit.valid


def test_post_response_ledger_rejection_retains_full_response(
    tmp_path: Path,
) -> None:
    class DriftBackend(ScriptedRelationalBackend):
        @property
        def identity(self) -> Mapping[str, Any]:
            return {**super().identity, "model": "different-frozen-model"}

    journal = tmp_path / "calls.jsonl"
    arm = StructuredHSWMArm(
        backend=DriftBackend(),
        budget=_budget(),
        isolation_id="rejected-response",
        store_path=tmp_path / "state.sqlite3",
        journal_path=journal,
    )
    with pytest.raises(ContinualLiveError, match="token preflight differs"):
        arm.update(
            LearningBatch(
                episode_id="episode-rejected-response",
                after_step=0,
                chosen=None,
                correct=False,
                learning_tokens=(PublicLearningToken("a", "r", "b"),),
            )
        )

    events = [json.loads(line) for line in journal.read_text().splitlines()]
    assert [event["event"] for event in events] == TOKEN_PREFLIGHT_SUCCESS_EVENTS + [
        "raw_response_received",
        "response_received",
        "rejected_response",
    ]
    raw_event = events[-3]
    completion = events[-2]["completion"]
    assert base64.b64decode(raw_event["raw_response_base64"]) == completion[
        "raw_response_json"
    ].encode("utf-8")
    assert raw_event["raw_response_sha256"] == completion["response_sha256"]
    assert events[-1]["outcome"] == "received_invalid"
    assert events[-1]["retry_permitted"] is False
    assert arm.ledger == []


def test_invalid_provider_json_is_retained_before_parsing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_response = b"not-json-from-provider"

    class FakeResponse:
        def __init__(self, body: bytes) -> None:
            self.body = body
            self.status = 200

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def read(self, _limit: int) -> bytes:
            return self.body

    def fake_urlopen(request: Any, **kwargs: Any) -> FakeResponse:
        del kwargs
        if request.full_url.endswith("/tokenize"):
            return FakeResponse(
                canonical_json_bytes(
                    {
                        "count": 3,
                        "max_model_len": 32768,
                        "token_strs": None,
                        "tokens": [1, 2, 3],
                    }
                )
            )
        return FakeResponse(raw_response)

    monkeypatch.setattr(live, "_urlopen_no_redirect", fake_urlopen)
    journal = tmp_path / "invalid-json.calls.jsonl"
    arm = StructuredHSWMArm(
        backend=OpenAICompatibleBackend(
            live.OpenAIBackendConfig(
                endpoint="http://model.invalid",
                model="fixture-model",
            )
        ),
        budget=_budget(),
        isolation_id="invalid-provider-json",
        store_path=tmp_path / "invalid-json.sqlite3",
        journal_path=journal,
    )
    with pytest.raises(ContinualLiveError, match="invalid chat-completions envelope"):
        arm.update(
            LearningBatch(
                episode_id="episode-invalid-json",
                after_step=0,
                chosen=None,
                correct=False,
                learning_tokens=(PublicLearningToken("a", "r", "b"),),
            )
        )

    events = [json.loads(line) for line in journal.read_text().splitlines()]
    assert [event["event"] for event in events] == TOKEN_PREFLIGHT_SUCCESS_EVENTS + [
        "raw_response_received",
        "failed",
    ]
    assert base64.b64decode(events[-2]["raw_response_base64"]) == raw_response
    assert events[-2]["raw_response_sha256"] == sha256(raw_response).hexdigest()
    assert events[-1]["outcome"] == "received_invalid"
    assert events[-1]["retry_permitted"] is False
    assert arm.ledger == []


def test_rejects_model_authorship_that_cites_hidden_or_old_sources(tmp_path: Path) -> None:
    class BadBackend(ScriptedRelationalBackend):
        @staticmethod
        def _author(payload: Mapping[str, Any]) -> str:
            value = json.loads(ScriptedRelationalBackend._author(payload))
            value["new_memory_relations"][0]["related_memory_ids"] = [
                "memory:hidden-not-public"
            ]
            return json.dumps(value)

    arm = StructuredHSWMArm(
        backend=BadBackend(),
        budget=_budget(),
        isolation_id="bad-source",
        store_path=tmp_path / "state.sqlite3",
    )
    with pytest.raises(ContinualLiveError, match="schema enum"):
        arm.update(
            LearningBatch(
                episode_id="episode-bad",
                after_step=0,
                chosen=None,
                correct=False,
                learning_tokens=(
                    PublicLearningToken("a", "r", "b"),
                    PublicLearningToken("b", "r", "c"),
                ),
            )
        )
    assert arm.state_canonical_bytes() == canonical_json_bytes(GENESIS.canonical())


@pytest.mark.parametrize(
    ("mutation", "error_match"),
    [
        (
            lambda value: value["new_memory_relations"].pop(),
            "array bound",
        ),
        (
            lambda value: value["new_memory_cell_indices"].pop(),
            "array bound",
        ),
        (
            lambda value: value["cells"].append(
                {
                    "capability": "nonce_graph_lookup",
                    "cell_id": "cell:unreachable",
                    "executor_agent_id": None,
                    "instruction": "A deliberately unreachable cell.",
                    "next_cell_indices": [],
                }
            ),
            "reachable from entry",
        ),
        (
            lambda value: value["new_memory_relations"][0].update(
                {"related_memory_ids": [0]}
            ),
            "schema enum",
        ),
        (
            lambda value: value.update({"entry_cell_index": 1}),
            "entry_cell_index cites an unknown cell",
        ),
        (
            lambda value: value["new_memory_cell_indices"].__setitem__(0, 1),
            "new_memory_cell_indices cites an unknown cell",
        ),
        (
            lambda value: value["new_memory_cell_indices"].__setitem__(0, True),
            "integer bound",
        ),
        (
            lambda value: value["new_memory_cell_indices"].__setitem__(0, -1),
            "integer bound",
        ),
        (
            lambda value: value["new_memory_cell_indices"].__setitem__(
                0, live.MAX_AUTHORED_CELLS
            ),
            "integer bound",
        ),
        (
            lambda value: value["cells"][0].update({"next_cell_indices": [1]}),
            "cell next_cell_indices contains duplicate or unknown indexes",
        ),
        (
            lambda value: value["cells"].append(
                {
                    "capability": "nonce_graph_lookup",
                    "cell_id": value["cells"][0]["cell_id"],
                    "executor_agent_id": None,
                    "instruction": "Duplicate cell ids must fail.",
                    "next_cell_indices": [],
                }
            ),
            "compact cell ids must be unique",
        ),
        (
            lambda value: value.update({"delete_memory_ids": []}),
            "object schema",
        ),
        (
            lambda value: value["cells"][0].update(
                {"instruction": "x" * (live.MAX_CELL_INSTRUCTION_CHARS + 1)}
            ),
            "string bound",
        ),
    ],
)
def test_compact_patch_fails_closed_on_coverage_references_and_reachability(
    tmp_path: Path,
    mutation: Callable[[dict[str, Any]], Any],
    error_match: str,
) -> None:
    class InvalidCompactBackend(ScriptedRelationalBackend):
        @staticmethod
        def _author(payload: Mapping[str, Any]) -> str:
            value = json.loads(ScriptedRelationalBackend._author(payload))
            mutation(value)
            return json.dumps(value)

    arm = StructuredHSWMArm(
        backend=InvalidCompactBackend(),
        budget=_budget(),
        isolation_id=f"invalid-compact-{error_match}",
        store_path=tmp_path / "state.sqlite3",
    )
    with pytest.raises(ContinualLiveError, match=error_match):
        arm.update(
            LearningBatch(
                episode_id="episode-invalid-compact",
                after_step=0,
                chosen=None,
                correct=False,
                learning_tokens=(
                    PublicLearningToken("a", "r", "b"),
                    PublicLearningToken("b", "r", "c"),
                ),
            )
        )
    assert arm.state_canonical_bytes() == canonical_json_bytes(GENESIS.canonical())


def test_compact_patch_rejects_assignment_vector_cell_capacity(
    tmp_path: Path,
) -> None:
    class OverloadedCellBackend(ScriptedRelationalBackend):
        @staticmethod
        def _author(payload: Mapping[str, Any]) -> str:
            value = json.loads(ScriptedRelationalBackend._author(payload))
            value["cells"] = [
                {
                    "capability": "nonce_graph_lookup",
                    "cell_id": "cell:overloaded",
                    "executor_agent_id": None,
                    "instruction": "This cell is intentionally over capacity.",
                    "next_cell_indices": [],
                }
            ]
            value["new_memory_cell_indices"] = [0] * len(
                value["new_memory_cell_indices"]
            )
            return json.dumps(value, sort_keys=True, separators=(",", ":"))

    arm = StructuredHSWMArm(
        backend=OverloadedCellBackend(),
        budget=_budget(),
        isolation_id="overloaded-assignment-vector",
        store_path=tmp_path / "state.sqlite3",
    )
    batch = LearningBatch(
        episode_id="episode-overloaded-assignment-vector",
        after_step=0,
        chosen=None,
        correct=False,
        learning_tokens=tuple(
            PublicLearningToken(f"node-{index}", "rel", f"target-{index}")
            for index in range(live.MAX_CELL_MEMORY_REFERENCES + 1)
        ),
    )
    with pytest.raises(ContinualLiveError, match="memory assignment bound"):
        arm.update(batch)
    assert arm.state_canonical_bytes() == canonical_json_bytes(GENESIS.canonical())


def _projection_test_snapshot() -> Any:
    memories = (
        live.MemoryRecord(
            memory_id="memory:a",
            kind="atomic_relation",
            content={
                "kind": "atomic_relation",
                "relation": "rel",
                "source": "node-a",
                "target": "node-b",
            },
            source_token_ids=("token:a",),
            related_memory_ids=("memory:b",),
            labels=("agent-organized",),
        ),
        live.MemoryRecord(
            memory_id="memory:b",
            kind="atomic_relation",
            content={
                "kind": "atomic_relation",
                "relation": "rel",
                "source": "node-b",
                "target": "node-c",
            },
            source_token_ids=("token:b",),
            labels=("agent-organized",),
        ),
    )
    cells = (
        live.CellRecord(
            cell_id="cell:a",
            capability=live.CAPABILITY,
            instruction="Route from the first memory.",
            memory_ids=("memory:a",),
            next_cell_ids=("cell:b",),
            executor_agent_id=None,
        ),
        live.CellRecord(
            cell_id="cell:b",
            capability=live.CAPABILITY,
            instruction="Route from the second memory.",
            memory_ids=("memory:b",),
            executor_agent_id=None,
        ),
    )
    return live.make_snapshot(memories, cells=cells, entry_cell_id="cell:a")


def test_indexed_authoring_projection_roundtrips_exact_state_and_order() -> None:
    active = _projection_test_snapshot()
    projection = live._indexed_authoring_projection(active, generation=7)
    assert projection["active_generation"] == 7
    assert projection["snapshot_id"] == active.snapshot_id
    assert [item["memory_id"] for item in projection["memories"]] == [
        memory.memory_id for memory in active.memories
    ]
    assert [item["cell_id"] for item in projection["cells"]] == [
        cell.cell_id for cell in active.cells
    ]
    assert projection["memories"][0]["related_memory_indices"] == [1]
    assert projection["cells"][0]["memory_indices"] == [0]
    assert projection["cells"][0]["next_cell_indices"] == [1]
    assert projection["entry_cell_index"] == 0
    assert live._expand_indexed_authoring_projection(projection) == active.canonical()
    live._validate_indexed_authoring_projection(
        projection,
        active=active,
        generation=7,
    )


@pytest.mark.parametrize("invalid_index", [True, -1, 2])
def test_indexed_projection_rejects_bool_negative_and_oob_refs(
    invalid_index: object,
) -> None:
    active = _projection_test_snapshot()
    projection = live._indexed_authoring_projection(active, generation=3)
    projection["memories"][0]["related_memory_indices"] = [invalid_index]
    body = {
        key: value for key, value in projection.items() if key != "projection_sha256"
    }
    projection["projection_sha256"] = live.canonical_sha256(body)
    with pytest.raises(ContinualLiveError, match="bool, negative, or unknown index"):
        live._expand_indexed_authoring_projection(projection)


def test_indexed_projection_preserves_raw_reference_duplicates_and_order() -> None:
    active = _projection_test_snapshot()
    projection = live._indexed_authoring_projection(active, generation=3)
    projection["memories"][0]["related_memory_indices"] = [1, 1]
    projection["cells"][0]["memory_indices"] = [0, 0]
    expanded = active.canonical()
    expanded["memories"][0]["related_memory_ids"] = ["memory:b", "memory:b"]
    expanded["cells"][0]["memory_ids"] = ["memory:a", "memory:a"]
    projection["source_snapshot_sha256"] = sha256(
        canonical_json_bytes(expanded)
    ).hexdigest()
    body = {
        key: value for key, value in projection.items() if key != "projection_sha256"
    }
    projection["projection_sha256"] = live.canonical_sha256(body)
    assert live._expand_indexed_authoring_projection(projection) == expanded


def test_indexed_projection_rejects_rehashed_tamper_against_active() -> None:
    active = _projection_test_snapshot()
    projection = live._indexed_authoring_projection(active, generation=3)
    projection["cells"][0]["instruction"] = "Tampered but self-consistent."
    expanded = active.canonical()
    expanded["cells"][0]["instruction"] = "Tampered but self-consistent."
    projection["source_snapshot_sha256"] = sha256(
        canonical_json_bytes(expanded)
    ).hexdigest()
    body = {
        key: value for key, value in projection.items() if key != "projection_sha256"
    }
    projection["projection_sha256"] = live.canonical_sha256(body)
    with pytest.raises(ContinualLiveError, match="different HSWM state"):
        live._validate_indexed_authoring_projection(
            projection,
            active=active,
            generation=3,
        )


@pytest.mark.parametrize(
    ("violation", "message"),
    [
        ("zero", "exactly one reachable cell"),
        ("multiple", "exactly one reachable cell"),
        ("capability", "capability is unsupported"),
        ("executor", "cannot preserve delegated executors"),
    ],
)
def test_compact_subset_rejects_unrepresentable_active_state_before_intent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    violation: str,
    message: str,
) -> None:
    memory = live.MemoryRecord(
        memory_id="memory:active",
        kind="atomic_relation",
        content={
            "kind": "atomic_relation",
            "relation": "rel",
            "source": "node-a",
            "target": "node-b",
        },
        source_token_ids=("token:active",),
    )
    if violation == "multiple":
        cells = (
            live.CellRecord(
                cell_id="cell:a",
                capability=live.CAPABILITY,
                instruction="First duplicate assignment.",
                memory_ids=(memory.memory_id,),
                next_cell_ids=("cell:b",),
            ),
            live.CellRecord(
                cell_id="cell:b",
                capability=live.CAPABILITY,
                instruction="Second duplicate assignment.",
                memory_ids=(memory.memory_id,),
            ),
        )
    else:
        cells = (
            live.CellRecord(
                cell_id="cell:a",
                capability=("unsupported" if violation == "capability" else live.CAPABILITY),
                instruction="An intentionally unrepresentable active cell.",
                memory_ids=() if violation == "zero" else (memory.memory_id,),
                executor_agent_id="agent:delegate" if violation == "executor" else None,
            ),
        )
    invalid = live.make_snapshot(
        (memory,),
        cells=cells,
        entry_cell_id="cell:a",
    )
    backend = ScriptedRelationalBackend()
    journal = tmp_path / "calls.jsonl"
    arm = StructuredHSWMArm(
        backend=backend,
        budget=_budget(),
        isolation_id=f"unrepresentable-{violation}",
        store_path=tmp_path / "state.sqlite3",
        journal_path=journal,
    )
    active_type = type(arm.store.active_snapshot())
    monkeypatch.setattr(
        arm.store,
        "active_snapshot",
        lambda: active_type(snapshot=invalid, generation=1, policy=arm.policy),
    )
    with pytest.raises(ContinualLiveError, match=message):
        arm.update(_one_token_batch())
    assert backend.requests == []
    assert arm.ledger == []
    assert not journal.exists()


def test_compact_patch_materializes_public_content_without_echoing_records(
    tmp_path: Path,
) -> None:
    backend = ScriptedRelationalBackend()
    arm = StructuredHSWMArm(
        backend=backend,
        budget=_budget(),
        isolation_id="compact-materialization",
        store_path=tmp_path / "state.sqlite3",
    )
    arm.update(
        LearningBatch(
            episode_id="episode-compact-materialization",
            after_step=0,
            chosen=None,
            correct=False,
            learning_tokens=(
                PublicLearningToken("node-a", "rel-x", "node-b"),
                PublicLearningToken("node-b", "rel-y", "node-c"),
            ),
        )
    )
    snapshot = arm.store.active_snapshot().snapshot
    by_source = {memory.content["source"]: memory for memory in snapshot.memories}
    assert by_source["node-a"].content == {
        "kind": "atomic_relation",
        "relation": "rel-x",
        "source": "node-a",
        "target": "node-b",
    }
    assert by_source["node-a"].labels == ("agent-organized",)
    assert by_source["node-a"].related_memory_ids == (
        by_source["node-b"].memory_id,
    )
    completion_value = json.loads(arm.ledger[0].completion.text)
    assert "upsert_memories" not in completion_value
    assert "memories" not in completion_value
    assert "node-a" not in arm.ledger[0].completion.text
    assert completion_value["new_memory_relations"][0] == {
        "related_memory_ids": [by_source["node-b"].memory_id]
    }
    assert all(
        set(relation) == {"related_memory_ids"}
        and all(
            isinstance(memory_id, str)
            for memory_id in relation["related_memory_ids"]
        )
        for relation in completion_value["new_memory_relations"]
    )
    assert set(snapshot.cells[0].memory_ids) == {
        memory.memory_id for memory in snapshot.memories
    }


def test_direct_memory_relations_reject_duplicate_and_cell_index_namespaces(
    tmp_path: Path,
) -> None:
    class InvalidDirectRelationBackend(ScriptedRelationalBackend):
        def __init__(self, violation: str) -> None:
            super().__init__()
            self.violation = violation

        def _author(self, payload: Mapping[str, Any]) -> str:
            value = json.loads(ScriptedRelationalBackend._author(payload))
            relation = value["new_memory_relations"][0]
            if self.violation == "duplicate":
                target = relation["related_memory_ids"][0]
                relation["related_memory_ids"] = [target, target]
            else:
                relation["related_memory_ids"] = [
                    value["new_memory_cell_indices"][1]
                ]
            return json.dumps(value, sort_keys=True, separators=(",", ":"))

    batch = LearningBatch(
        episode_id="direct-relation-namespace",
        after_step=0,
        chosen=None,
        correct=False,
        learning_tokens=(
            PublicLearningToken("node-a", "rel", "node-b"),
            PublicLearningToken("node-b", "rel", "node-c"),
            PublicLearningToken("node-c", "rel", "node-d"),
        ),
    )
    for violation, message in (
        ("duplicate", "duplicate or unknown memory ids"),
        ("cell-index", "schema enum"),
    ):
        arm = StructuredHSWMArm(
            backend=InvalidDirectRelationBackend(violation),
            budget=_budget(),
            isolation_id=f"direct-relation-{violation}",
            store_path=tmp_path / violation / "state.sqlite3",
        )
        with pytest.raises(ContinualLiveError, match=message):
            arm.update(batch)
        assert arm.store.active_snapshot().generation == 0
        assert arm.state_canonical_bytes() == canonical_json_bytes(
            GENESIS.canonical()
        )


def test_existing_assignment_minus_one_is_the_only_delete_encoding(
    tmp_path: Path,
) -> None:
    class DeleteUnreferencedSourceBackend(ScriptedRelationalBackend):
        def __init__(self) -> None:
            super().__init__()
            self.author_calls = 0

        def _author(self, payload: Mapping[str, Any]) -> str:
            value = json.loads(ScriptedRelationalBackend._author(payload))
            self.author_calls += 1
            if self.author_calls == 2:
                memories = payload["current_hswm_indexed_read_only"]["memories"]
                delete_index = next(
                    index
                    for index, memory in enumerate(memories)
                    if memory["content"]["source"] == "node-a"
                )
                value["existing_memory_cell_indices"][delete_index] = -1
            return json.dumps(value, sort_keys=True, separators=(",", ":"))

    arm = StructuredHSWMArm(
        backend=DeleteUnreferencedSourceBackend(),
        budget=_budget(),
        isolation_id="valid-vector-delete",
        store_path=tmp_path / "state.sqlite3",
    )
    arm.update(
        LearningBatch(
            episode_id="valid-vector-delete",
            after_step=0,
            chosen=None,
            correct=False,
            learning_tokens=(
                PublicLearningToken("node-a", "rel", "node-b"),
                PublicLearningToken("node-b", "rel", "node-c"),
            ),
        )
    )
    arm.update(
        LearningBatch(
            episode_id="valid-vector-delete",
            after_step=1,
            chosen=None,
            correct=False,
            learning_tokens=(PublicLearningToken("node-c", "rel", "node-d"),),
        )
    )
    snapshot = arm.store.active_snapshot().snapshot
    assert {memory.content["source"] for memory in snapshot.memories} == {
        "node-b",
        "node-c",
    }
    assigned_ids = [memory_id for cell in snapshot.cells for memory_id in cell.memory_ids]
    assert sorted(assigned_ids) == sorted(
        memory.memory_id for memory in snapshot.memories
    )
    second_value = json.loads(arm.ledger[1].completion.text)
    assert second_value["existing_memory_cell_indices"].count(-1) == 1
    assert "delete_memory_ids" not in second_value


def test_relation_to_minus_one_deleted_existing_memory_is_rejected_precommit(
    tmp_path: Path,
) -> None:
    class DeleteRelationTargetBackend(ScriptedRelationalBackend):
        def __init__(self) -> None:
            super().__init__()
            self.author_calls = 0

        def _author(self, payload: Mapping[str, Any]) -> str:
            value = json.loads(ScriptedRelationalBackend._author(payload))
            self.author_calls += 1
            if self.author_calls == 2:
                memories = payload["current_hswm_indexed_read_only"]["memories"]
                delete_index = next(
                    index
                    for index, memory in enumerate(memories)
                    if memory["content"]["source"] == "node-a"
                )
                assert value["new_memory_relations"][0]["related_memory_ids"] == [
                    memories[delete_index]["memory_id"]
                ]
                value["existing_memory_cell_indices"][delete_index] = -1
            return json.dumps(value, sort_keys=True, separators=(",", ":"))

    arm = StructuredHSWMArm(
        backend=DeleteRelationTargetBackend(),
        budget=_budget(),
        isolation_id="invalid-vector-delete-target",
        store_path=tmp_path / "state.sqlite3",
    )
    arm.update(
        LearningBatch(
            episode_id="invalid-vector-delete-target",
            after_step=0,
            chosen=None,
            correct=False,
            learning_tokens=(
                PublicLearningToken("node-a", "rel", "node-b"),
                PublicLearningToken("node-b", "rel", "node-c"),
            ),
        )
    )
    before = arm.store.active_snapshot()
    with pytest.raises(
        ContinualLiveError, match="new relation targets a deleted existing memory"
    ):
        arm.update(
            LearningBatch(
                episode_id="invalid-vector-delete-target",
                after_step=1,
                chosen=None,
                correct=False,
                learning_tokens=(
                    PublicLearningToken("node-x", "rel", "node-a"),
                ),
            )
        )
    after = arm.store.active_snapshot()
    assert after.generation == before.generation == 1
    assert after.snapshot.canonical() == before.snapshot.canonical()
    assert arm.store.token_count() == 2


def test_deletion_referenced_by_surviving_memory_is_rejected_precommit(
    tmp_path: Path,
) -> None:
    class DeleteReferencedExistingBackend(ScriptedRelationalBackend):
        def __init__(self) -> None:
            super().__init__()
            self.author_calls = 0

        def _author(self, payload: Mapping[str, Any]) -> str:
            value = json.loads(ScriptedRelationalBackend._author(payload))
            self.author_calls += 1
            if self.author_calls == 2:
                memories = payload["current_hswm_indexed_read_only"]["memories"]
                delete_index = next(
                    index
                    for index, memory in enumerate(memories)
                    if memory["content"]["source"] == "node-b"
                )
                value["existing_memory_cell_indices"][delete_index] = -1
            return json.dumps(value, sort_keys=True, separators=(",", ":"))

    arm = StructuredHSWMArm(
        backend=DeleteReferencedExistingBackend(),
        budget=_budget(),
        isolation_id="invalid-surviving-reference-delete",
        store_path=tmp_path / "state.sqlite3",
    )
    arm.update(
        LearningBatch(
            episode_id="invalid-surviving-reference-delete",
            after_step=0,
            chosen=None,
            correct=False,
            learning_tokens=(
                PublicLearningToken("node-a", "rel", "node-b"),
                PublicLearningToken("node-b", "rel", "node-c"),
            ),
        )
    )
    before = arm.store.active_snapshot()
    with pytest.raises(
        ContinualLiveError,
        match="cannot delete an existing memory still referenced by surviving state",
    ):
        arm.update(
            LearningBatch(
                episode_id="invalid-surviving-reference-delete",
                after_step=1,
                chosen=None,
                correct=False,
                learning_tokens=(
                    PublicLearningToken("node-c", "rel", "node-d"),
                ),
            )
        )
    after = arm.store.active_snapshot()
    assert after.generation == before.generation == 1
    assert after.snapshot.canonical() == before.snapshot.canonical()
    assert arm.store.token_count() == 2


def test_public_schema_gate_is_exactly_four_public_calls(tmp_path: Path) -> None:
    result = run_public_schema_gate(
        backend_factory=ScriptedRelationalBackend,
        state_dir=tmp_path / "gate-state",
    )
    assert result["valid"] is True
    assert result["adapter_schema"] == "hswm-compact-structure-patch/v4"
    assert result["protocol"] == "hswm-public-schema-gate/v5"
    assert result["indexed_authoring_view_schema"] == (
        "hswm-indexed-authoring-view/v1"
    )
    assert result["mutation_expressivity"] == "compact-adapter-subset"
    assert result["provider_context_window_tokens"] == 32768
    assert result["input_token_ceiling"] == 26624
    fixture = live.public_schema_gate_fixture()
    assert fixture["protocol"] == "hswm-public-schema-gate/v3"
    assert fixture["compact_patch_schema"] == "hswm-compact-structure-patch/v3"
    assert fixture["fixture_sha256"] == (
        "2a798b518c712551792400477411f89767755062b926a569dcec6afb9cda3bd6"
    )
    assert result["model_generation_calls_observed"] == 4
    assert result["token_preflight_calls_observed"] == 4
    assert result["outbound_http_requests_observed"] == 8
    assert [item["operation"] for item in result["calls"]] == [
        "update",
        "update",
        "update",
        "answer",
    ]
    assert all(item["finish_reason"] == "stop" for item in result["calls"])
    assert max(
        item["output_tokens"]
        for item in result["calls"]
        if item["operation"] == "update"
    ) <= 6144
    assert result["final_memory_count"] == 144
    assert result["probe_choice"] == live.public_schema_gate_fixture()["probe_answer"]
    assert result["before_probe_state_sha256"] == result["after_probe_state_sha256"]
    assert result["denylisted_from_evaluation"] is True
    assert result["provider_structured_output_backend_attested"] is False
    assert result["probe_mechanism_attribution"] == "not-attested-by-this-public-gate"
    assert [
        item["expected_relation_count"]
        for item in result["agent_relation_checks"]
    ] == [63, 3]
    assert [
        item["expected_existing_relation_count"]
        for item in result["agent_relation_checks"]
    ] == [0, 1]
    assert [
        item["expected_new_relation_count"]
        for item in result["agent_relation_checks"]
    ] == [63, 2]
    assert all(
        item["exact_match"]
        and item["expected_relation_count"] == item["observed_relation_count"]
        and item["expected_relations_sha256"]
        == item["observed_relations_sha256"]
        and item["expected_existing_relation_count"]
        == item["observed_existing_relation_count"]
        and item["expected_existing_relations_sha256"]
        == item["observed_existing_relations_sha256"]
        and item["expected_new_relation_count"]
        == item["observed_new_relation_count"]
        and item["expected_new_relations_sha256"]
        == item["observed_new_relations_sha256"]
        for item in result["agent_relation_checks"]
    )
    assert result["extension"]["relation_author"] == (
        "evaluator:public-schema-gate-fixture"
    )
    assert result["extension"]["evaluator_authored_memory_count"] == 76
    assert result["extension"]["evaluator_authored_relation_count"] == 75
    structured_events = [
        json.loads(line)
        for line in (
            tmp_path / "gate-state" / "structured" / "calls.jsonl"
        ).read_text().splitlines()
    ]
    plain_events = [
        json.loads(line)
        for line in (
            tmp_path / "gate-state" / "plain" / "calls.jsonl"
        ).read_text().splitlines()
    ]
    accepted_call_events = TOKEN_PREFLIGHT_SUCCESS_EVENTS + [
        "raw_response_received",
        "response_received",
        "completed",
    ]
    assert [item["event"] for item in structured_events] == accepted_call_events * 3
    assert [item["event"] for item in plain_events] == accepted_call_events
    for events in (structured_events, plain_events):
        intents = [item for item in events if item["event"] == "intent"]
        completed = [item for item in events if item["event"] == "completed"]
        for intent, completion_event in zip(intents, completed, strict=True):
            contract = live.JSONSchemaContract(
                name=intent["response_schema_name"],
                schema_json=intent["response_schema_json"],
                schema_sha256=intent["response_schema_sha256"],
            )
            raw_request = json.loads(intent["raw_request_json"])
            assert set(raw_request) == {
                "chat_template_kwargs",
                "max_tokens",
                "messages",
                "model",
                "response_format",
                "seed",
                "temperature",
                "top_p",
            }
            expected_max_tokens = (
                128
                if intent["operation"] == "answer"
                else live.PUBLIC_SCHEMA_GATE_OUTPUT_TOKEN_CEILING
            )
            assert intent["max_output_tokens"] == expected_max_tokens
            assert raw_request["max_tokens"] == expected_max_tokens
            assert raw_request["response_format"] == contract.response_format()
            assert raw_request["response_format"]["json_schema"]["strict"] is True
            assert "structured_outputs" not in raw_request
            assert "guided_json" not in raw_request
            assert intent["raw_request_sha256"] == sha256(
                intent["raw_request_json"].encode()
            ).hexdigest()
            assert intent["raw_request_bytes"] == len(
                intent["raw_request_json"].encode()
            )
            contract.validate_instance(
                json.loads(completion_event["completion"]["text"])
            )
    assert [
        item["response_schema_name"]
        for item in structured_events
        if item["event"] == "intent"
    ] == ["hswm_compact_patch_v4", "hswm_compact_patch_v4", "hswm_choice_v1"]
    assert [
        item["response_schema_name"]
        for item in plain_events
        if item["event"] == "intent"
    ] == ["hswm_plain_memory_v1"]
    structured_intents = [
        item for item in structured_events if item["event"] == "intent"
    ]
    assert [item["max_output_tokens"] for item in structured_intents] == [
        6144,
        6144,
        128,
    ]
    assert live.PUBLIC_SCHEMA_GATE_MAX_UPDATE_INPUT_TOKENS == (
        live.PUBLIC_SCHEMA_GATE_CONTEXT_WINDOW_TOKENS
        - live.PUBLIC_SCHEMA_GATE_OUTPUT_TOKEN_CEILING
    )
    first_schema = json.loads(structured_intents[0]["response_schema_json"])
    cell_properties = first_schema["properties"]["cells"]["items"]["properties"]
    relation_properties = first_schema["properties"]["new_memory_relations"]["items"][
        "properties"
    ]
    assert first_schema["properties"]["cells"]["maxItems"] == 16
    assert cell_properties["next_cell_indices"]["maxItems"] == live.MAX_CELL_EDGES
    assert cell_properties["instruction"]["maxLength"] == 256
    assert first_schema["properties"]["existing_memory_cell_indices"][
        "minItems"
    ] == 0
    assert first_schema["properties"]["existing_memory_cell_indices"][
        "maxItems"
    ] == 0
    assert first_schema["properties"]["new_memory_cell_indices"]["minItems"] == 64
    assert first_schema["properties"]["new_memory_cell_indices"]["maxItems"] == 64
    assert first_schema["properties"]["new_memory_relations"]["minItems"] == 64
    assert first_schema["properties"]["new_memory_relations"]["maxItems"] == 64
    assert set(relation_properties) == {"related_memory_ids"}
    first_relation_ids = relation_properties["related_memory_ids"]
    assert first_relation_ids["maxItems"] == live.MAX_RELATED_MEMORY_IDS
    assert first_relation_ids["items"]["type"] == "string"
    assert len(first_relation_ids["items"]["enum"]) == 64
    assert all(
        isinstance(memory_id, str)
        for memory_id in first_relation_ids["items"]["enum"]
    )
    assert "new_memory_links" not in first_schema["properties"]
    assert "delete_memory_ids" not in first_schema["properties"]
    assert first_schema["properties"]["rationale"]["maxLength"] == 512
    second_schema = json.loads(structured_intents[1]["response_schema_json"])
    assert second_schema["properties"]["existing_memory_cell_indices"][
        "minItems"
    ] == 140
    assert second_schema["properties"]["existing_memory_cell_indices"][
        "maxItems"
    ] == 140
    assert second_schema["properties"]["new_memory_cell_indices"]["minItems"] == 4
    assert second_schema["properties"]["new_memory_cell_indices"]["maxItems"] == 4
    assert second_schema["properties"]["new_memory_relations"]["minItems"] == 4
    assert second_schema["properties"]["new_memory_relations"]["maxItems"] == 4
    second_relation_ids = second_schema["properties"]["new_memory_relations"][
        "items"
    ]["properties"]["related_memory_ids"]
    assert len(second_relation_ids["items"]["enum"]) == 144
    for completion_event in (
        item for item in structured_events if item["event"] == "completed"
    ):
        if completion_event["operation"] != "update":
            continue
        completion_value = json.loads(completion_event["completion"]["text"])
        assert set(completion_value) == {
            "cells",
            "entry_cell_index",
            "existing_memory_cell_indices",
            "new_memory_cell_indices",
            "new_memory_relations",
            "rationale",
        }
        assert not {
            "delete_memory_ids",
            "new_memory_links",
            "token_index",
        } & set(completion_value)
        assert all(
            set(relation) == {"related_memory_ids"}
            for relation in completion_value["new_memory_relations"]
        )
    first_intent = structured_intents[0]
    first_payload = json.loads(first_intent["request_payload_json"])
    assert first_payload["mutation_expressivity"] == "compact-adapter-subset"
    assert "current_hswm_read_only" not in first_payload
    first_projection = first_payload["current_hswm_indexed_read_only"]
    assert first_projection["schema"] == "hswm-indexed-authoring-view/v1"
    assert live._expand_indexed_authoring_projection(first_projection) == (
        GENESIS.canonical()
    )
    first_contract = first_payload["response_contract"]
    assert first_contract["existing_memory_cell_indices"]["exact_length"] == 0
    assert first_contract["new_memory_cell_indices"]["exact_length"] == 64
    assert first_contract["new_memory_relations"]["exact_length"] == 64
    assert first_contract["new_memory_relations"]["item_fields"] == [
        "related_memory_ids"
    ]
    assert "memory_assignments_max_per_cell_field" not in first_payload[
        "output_bounds"
    ]
    second_payload = json.loads(structured_intents[1]["request_payload_json"])
    second_projection = second_payload["current_hswm_indexed_read_only"]
    expanded_second = live._expand_indexed_authoring_projection(second_projection)
    second_update_completion = json.loads(
        [
            item["completion"]["text"]
            for item in structured_events
            if item["event"] == "completed" and item["operation"] == "update"
        ][1]
    )
    authored_target_ids = [
        memory_id
        for relation in second_update_completion["new_memory_relations"]
        for memory_id in relation["related_memory_ids"]
    ]
    existing_target_ids = {
        memory["memory_id"] for memory in expanded_second["memories"]
    }
    new_target_ids = {
        token["suggested_memory_id"]
        for token in second_payload["public_source_tokens"]
    }
    assert sum(item in existing_target_ids for item in authored_target_ids) == 1
    assert sum(item in new_target_ids for item in authored_target_ids) == 2
    assert all(isinstance(item, str) for item in authored_target_ids)
    assert len(expanded_second["memories"]) == 140
    assert len(expanded_second["cells"]) >= 1
    assert second_projection["active_generation"] == 2
    assert second_projection["source_snapshot_sha256"] == sha256(
        canonical_json_bytes(expanded_second)
    ).hexdigest()
    projection_body = {
        key: value
        for key, value in second_projection.items()
        if key != "projection_sha256"
    }
    assert second_projection["projection_sha256"] == live.canonical_sha256(
        projection_body
    )
    assert set(second_projection["memories"][0]) == {
        "content",
        "kind",
        "labels",
        "memory_id",
        "related_memory_indices",
        "source_token_ids",
    }
    assert set(second_projection["cells"][0]) == {
        "capability",
        "cell_id",
        "executor_agent_id",
        "instruction",
        "memory_indices",
        "next_cell_indices",
    }

    def nested_keys(value: Any) -> set[str]:
        if isinstance(value, Mapping):
            return set(value) | {
                key
                for item in value.values()
                for key in nested_keys(item)
            }
        if isinstance(value, list):
            return {key for item in value for key in nested_keys(item)}
        return set()

    assert not {
        "entry_cell_id",
        "memory_ids",
        "next_cell_ids",
        "related_memory_ids",
    } & nested_keys(second_projection)
    bindings = result["authoring_projection_bindings"]
    assert [item["active_generation"] for item in bindings] == [0, 2]
    assert [item["request_sha256"] for item in bindings] == [
        structured_intents[0]["raw_request_sha256"],
        structured_intents[1]["raw_request_sha256"],
    ]
    assert all(
        item["projection_schema"] == "hswm-indexed-authoring-view/v1"
        and item["mutation_expressivity"] == "compact-adapter-subset"
        for item in bindings
    )
    second_contract = second_payload["response_contract"]
    assert second_contract["existing_memory_cell_indices"]["exact_length"] == 140
    assert second_contract["new_memory_cell_indices"]["exact_length"] == 4
    assert second_contract["new_memory_relations"]["exact_length"] == 4
    assert first_contract["top_level_fields"] == [
        "cells",
        "entry_cell_index",
        "existing_memory_cell_indices",
        "new_memory_cell_indices",
        "new_memory_relations",
        "rationale",
    ]
    combined_instruction = (
        first_intent["system_message"] + " " + first_payload["instruction"]
    )
    assert "direct target MemoryRecord IDs" in combined_instruction
    assert "Cell-assignment vectors do not define memory relations" in (
        combined_instruction
    )
    assert "never cell or token indices" in combined_instruction
    assert "never infer relations from index, adjacency, or order" in (
        combined_instruction
    )
    assert "i+1" not in combined_instruction
    assert "seed" not in live.public_schema_gate_fixture()


@pytest.mark.parametrize(
    ("violation", "message"),
    [
        ("self", "cannot contain the source memory id"),
        ("wrong-other", "new relation is not content-composable"),
    ],
)
def test_public_gate_relation_failure_stops_before_commit_at_genesis(
    tmp_path: Path, violation: str, message: str
) -> None:
    class InvalidRelationBackend(ScriptedRelationalBackend):
        @staticmethod
        def _author(payload: Mapping[str, Any]) -> str:
            value = json.loads(ScriptedRelationalBackend._author(payload))
            source_tokens = payload["public_source_tokens"]
            value["new_memory_relations"][0]["related_memory_ids"] = [
                source_tokens[0 if violation == "self" else 2][
                    "suggested_memory_id"
                ]
            ]
            return json.dumps(value, sort_keys=True, separators=(",", ":"))

    backends: list[InvalidRelationBackend] = []

    def backend_factory() -> InvalidRelationBackend:
        backend = InvalidRelationBackend()
        backends.append(backend)
        return backend

    state_dir = tmp_path / f"relation-{violation}"
    with pytest.raises(ContinualLiveError, match=message):
        run_public_schema_gate(
            backend_factory=backend_factory,
            state_dir=state_dir,
        )
    assert sum(len(backend.requests) for backend in backends) == 1
    store = live.SQLiteSelfModelStore(
        state_dir / "structured" / "state.sqlite3",
        policy=live._proposal_policy(_budget()),
    )
    try:
        active = store.active_snapshot()
        assert active.snapshot.canonical() == GENESIS.canonical()
        assert active.generation == 0
        assert store.token_count() == 0
        assert store.activation_count() == 0
        assert store.snapshot_count() == 1
    finally:
        store.close()


def test_public_gate_rejects_incremental_delete_before_mutating_active_140(
    tmp_path: Path,
) -> None:
    class IncrementalDeleteBackend(ScriptedRelationalBackend):
        def __init__(self) -> None:
            super().__init__()
            self.author_calls = 0
            self.pre_incremental_state: dict[str, Any] | None = None

        def _author(self, payload: Mapping[str, Any]) -> str:
            value = json.loads(ScriptedRelationalBackend._author(payload))
            self.author_calls += 1
            if self.author_calls == 2:
                active = payload["current_hswm_indexed_read_only"]
                self.pre_incremental_state = live._expand_indexed_authoring_projection(
                    active
                )
                referenced = {
                    related_index
                    for memory in active["memories"]
                    for related_index in memory["related_memory_indices"]
                }
                delete_index = next(
                    index
                    for index in range(len(active["memories"]))
                    if index not in referenced
                )
                value["existing_memory_cell_indices"][delete_index] = -1
            return json.dumps(value, sort_keys=True, separators=(",", ":"))

    backends: list[IncrementalDeleteBackend] = []

    def backend_factory() -> IncrementalDeleteBackend:
        backend = IncrementalDeleteBackend()
        backends.append(backend)
        return backend

    state_dir = tmp_path / "incremental-delete"
    with pytest.raises(
        ContinualLiveError,
        match="public gate compact patch cannot delete existing fixture memories",
    ):
        run_public_schema_gate(
            backend_factory=backend_factory,
            state_dir=state_dir,
        )
    structured_backend = backends[0]
    assert structured_backend.author_calls == 2
    assert structured_backend.pre_incremental_state is not None
    store = live.SQLiteSelfModelStore(
        state_dir / "structured" / "state.sqlite3",
        policy=live._proposal_policy(_budget()),
    )
    try:
        active = store.active_snapshot()
        assert active.generation == 2
        assert active.snapshot.canonical() == structured_backend.pre_incremental_state
        assert len(active.snapshot.memories) == 140
        assert store.token_count() == 140
        assert store.activation_count() == 2
    finally:
        store.close()


def test_public_gate_rejects_wrong_existing_index_before_mutating_active_140(
    tmp_path: Path,
) -> None:
    class WrongExistingIndexBackend(ScriptedRelationalBackend):
        def __init__(self) -> None:
            super().__init__()
            self.author_calls = 0
            self.pre_incremental_state: dict[str, Any] | None = None

        def _author(self, payload: Mapping[str, Any]) -> str:
            value = json.loads(ScriptedRelationalBackend._author(payload))
            self.author_calls += 1
            if self.author_calls == 2:
                active = payload["current_hswm_indexed_read_only"]
                self.pre_incremental_state = live._expand_indexed_authoring_projection(
                    active
                )
                relation_index = next(
                    index
                    for index, relation in enumerate(value["new_memory_relations"])
                    if any(
                        memory_id
                        in {memory["memory_id"] for memory in active["memories"]}
                        for memory_id in relation["related_memory_ids"]
                    )
                )
                correct_id = value["new_memory_relations"][relation_index][
                    "related_memory_ids"
                ][0]
                wrong_id = next(
                    memory["memory_id"]
                    for memory in active["memories"]
                    if memory["memory_id"] != correct_id
                )
                value["new_memory_relations"][relation_index]["related_memory_ids"] = [
                    wrong_id
                ]
            return json.dumps(value, sort_keys=True, separators=(",", ":"))

    backends: list[WrongExistingIndexBackend] = []

    def backend_factory() -> WrongExistingIndexBackend:
        backend = WrongExistingIndexBackend()
        backends.append(backend)
        return backend

    state_dir = tmp_path / "wrong-existing-index"
    with pytest.raises(
        ContinualLiveError,
        match="new relation is not content-composable",
    ):
        run_public_schema_gate(
            backend_factory=backend_factory,
            state_dir=state_dir,
        )
    structured_backend = backends[0]
    assert structured_backend.author_calls == 2
    assert structured_backend.pre_incremental_state is not None
    store = live.SQLiteSelfModelStore(
        state_dir / "structured" / "state.sqlite3",
        policy=live._proposal_policy(_budget()),
    )
    try:
        active = store.active_snapshot()
        assert active.generation == 2
        assert active.snapshot.canonical() == structured_backend.pre_incremental_state
        assert len(active.snapshot.memories) == 140
        assert store.token_count() == 140
        assert store.activation_count() == 2
    finally:
        store.close()


def test_public_relation_validator_uses_content_not_shuffled_index_order(
    tmp_path: Path,
) -> None:
    summaries: list[dict[str, Any]] = []

    def validate(
        proposal: Any,
        source_tokens: Sequence[Mapping[str, Any]],
        active: Any,
    ) -> None:
        summaries.append(
            live._validate_public_gate_agent_relations(
                proposal, source_tokens, active
            )
        )

    arm = StructuredHSWMArm(
        backend=ScriptedRelationalBackend(),
        budget=_budget(),
        isolation_id="shuffled-content-relations",
        store_path=tmp_path / "state.sqlite3",
        proposal_validator=validate,
    )
    arm.update(
        LearningBatch(
            episode_id="shuffled-content-relations",
            after_step=0,
            chosen=None,
            correct=False,
            learning_tokens=(
                PublicLearningToken("node-b", "rel", "node-c"),
                PublicLearningToken("node-x", "rel", "node-a"),
                PublicLearningToken("node-a", "rel", "node-b"),
            ),
        )
    )
    assert len(summaries) == 1
    assert summaries[0]["expected_relation_count"] == 2
    assert summaries[0]["observed_relation_count"] == 2
    snapshot = arm.store.active_snapshot().snapshot
    by_source = {memory.content["source"]: memory for memory in snapshot.memories}
    assert by_source["node-x"].related_memory_ids == (
        by_source["node-a"].memory_id,
    )
    assert by_source["node-a"].related_memory_ids == (
        by_source["node-b"].memory_id,
    )
    assert by_source["node-b"].related_memory_ids == ()


@pytest.mark.parametrize(
    ("violation", "message"),
    [
        ("length", "finish_reason"),
        ("headroom", "provider output usage exceeds the request budget"),
    ],
)
def test_public_schema_gate_rejects_first_invalid_completion_before_state_change(
    tmp_path: Path, violation: str, message: str
) -> None:
    backends: list[FirstResponseGateViolationBackend] = []

    def backend_factory() -> FirstResponseGateViolationBackend:
        backend = FirstResponseGateViolationBackend(violation)
        backends.append(backend)
        return backend

    state_dir = tmp_path / f"gate-{violation}"
    with pytest.raises(ContinualLiveError, match=message):
        run_public_schema_gate(
            backend_factory=backend_factory,
            state_dir=state_dir,
        )
    assert sum(len(backend.requests) for backend in backends) == 1
    events = [
        json.loads(line)
        for line in (state_dir / "structured" / "calls.jsonl").read_text().splitlines()
    ]
    expected_tail = (
        ["raw_response_received", "failed"]
        if violation == "length"
        else ["raw_response_received", "response_received", "rejected_response"]
    )
    assert [event["event"] for event in events] == (
        TOKEN_PREFLIGHT_SUCCESS_EVENTS + expected_tail
    )
    assert sum(event["event"] == "intent" for event in events) == 1
    assert not (state_dir / "plain" / "calls.jsonl").exists()
    store = live.SQLiteSelfModelStore(
        state_dir / "structured" / "state.sqlite3",
        policy=live._proposal_policy(_budget()),
    )
    try:
        assert store.active_snapshot().snapshot.canonical() == GENESIS.canonical()
        assert store.active_snapshot().generation == 0
    finally:
        store.close()


@pytest.mark.parametrize("outcome", ["timeout", "http400"])
def test_exact_raw_request_is_fsynced_before_transport_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
) -> None:
    observed_requests: list[bytes] = []

    class TokenizeResponse:
        status = 200

        def __enter__(self) -> TokenizeResponse:
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def read(self, _limit: int) -> bytes:
            return canonical_json_bytes(
                {
                    "count": 3,
                    "max_model_len": 32768,
                    "token_strs": None,
                    "tokens": [1, 2, 3],
                }
            )

    def fail_transport(request: Any, *, timeout: float) -> Any:
        del timeout
        observed_requests.append(request.data)
        if request.full_url.endswith("/tokenize"):
            return TokenizeResponse()
        if outcome == "timeout":
            raise TimeoutError("fixture timeout before response")
        raise live.urlerror.HTTPError(
            request.full_url,
            400,
            "bad request",
            {},
            io.BytesIO(b'{"error":"fixture bad request"}'),
        )

    monkeypatch.setattr(live, "_urlopen_no_redirect", fail_transport)
    config = live.OpenAIBackendConfig(
        endpoint="http://model.invalid",
        model="fixture-model",
    )
    arm = StructuredHSWMArm(
        backend=OpenAICompatibleBackend(config),
        budget=_budget(),
        isolation_id=f"prepared-request-{outcome}",
        store_path=tmp_path / "state.sqlite3",
    )
    with pytest.raises(ContinualLiveError, match="no retry"):
        arm.update(_one_token_batch())
    assert len(observed_requests) == 2
    events = [
        json.loads(line)
        for line in arm.journal_path.read_text().splitlines()
    ]
    intent = events[0]
    assert intent["event"] == "intent"
    assert intent["raw_request_json"].encode() == observed_requests[1]
    assert intent["raw_request_sha256"] == sha256(observed_requests[1]).hexdigest()
    assert intent["raw_request_bytes"] == len(observed_requests[1])
    tokenize_intent = events[1]
    assert tokenize_intent["event"] == "tokenize_intent"
    assert tokenize_intent["raw_request_json"].encode() == observed_requests[0]
    response_format = json.loads(intent["raw_request_json"])["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    assert sum(item["event"] == "intent" for item in events) == 1
    assert events[-1]["event"] == "failed"
    assert not any(item["event"] == "completed" for item in events)
    if outcome == "timeout":
        assert [item["event"] for item in events] == TOKEN_PREFLIGHT_SUCCESS_EVENTS + [
            "failed"
        ]
    else:
        assert [item["event"] for item in events] == TOKEN_PREFLIGHT_SUCCESS_EVENTS + [
            "raw_response_received",
            "failed",
        ]
        assert events[-2]["prepared_request_match"] is True
    assert arm.store.active_snapshot().snapshot.canonical() == GENESIS.canonical()


def test_token_preflight_exactly_binds_the_prepared_chat_request(
    tmp_path: Path,
) -> None:
    backend = ScriptedRelationalBackend()
    arm = StructuredHSWMArm(
        backend=backend,
        budget=_budget(),
        isolation_id="exact-token-preflight",
        store_path=tmp_path / "state.sqlite3",
    )
    arm.update(_one_token_batch())
    entry = arm.ledger[0]
    expected = live._prepare_tokenize_request(
        backend_identity=backend.identity,
        raw_chat_request=entry.completion.raw_request_json.encode("utf-8"),
    )
    receipt = entry.token_preflight
    assert receipt.raw_request_json.encode("utf-8") == expected
    assert receipt.source_chat_request_sha256 == entry.completion.request_sha256
    assert receipt.count == entry.completion.input_tokens
    assert receipt.max_output_tokens == entry.max_output_tokens
    assert receipt.max_model_len == backend.identity["expected_max_model_len"]
    request = json.loads(receipt.raw_request_json)
    assert request["continue_final_message"] is False
    assert request["add_generation_prompt"] is True
    assert request["add_special_tokens"] is False
    assert request["chat_template_kwargs"] == {"enable_thinking": False}
    events = [json.loads(line) for line in arm.journal_path.read_text().splitlines()]
    assert [item["event"] for item in events] == TOKEN_PREFLIGHT_SUCCESS_EVENTS + [
        "raw_response_received",
        "response_received",
        "completed",
    ]
    assert events.index(
        next(item for item in events if item["event"] == "tokenize_accepted")
    ) < events.index(
        next(item for item in events if item["event"] == "generation_dispatch_intent")
    )


@pytest.mark.parametrize(
    "violation",
    [
        "extra-field",
        "bool-count",
        "negative-maxlen",
        "float-maxlen",
        "huge-count",
        "huge-token-id",
        "count-list-mismatch",
        "duplicate-count",
        "duplicate-maxlen",
        "nan-count",
        "invalid-json",
    ],
)
def test_invalid_token_preflight_envelopes_never_dispatch_generation(
    tmp_path: Path,
    violation: str,
) -> None:
    class InvalidTokenizeBackend(ScriptedRelationalBackend):
        def tokenize(self, **kwargs: Any) -> live.TokenPreflightReceipt:
            observer = kwargs.pop("response_observer")
            captured: list[tuple[bytes, bytes, int | None, bool]] = []
            receipt = super().tokenize(
                **kwargs,
                response_observer=lambda *items: captured.append(items),
            )
            raw_request, raw_response, status, complete = captured[0]
            if violation == "invalid-json":
                changed = b"not-json"
            else:
                value = json.loads(raw_response)
                if violation in {"duplicate-count", "duplicate-maxlen"}:
                    field = (
                        "count" if violation == "duplicate-count" else "max_model_len"
                    )
                    duplicate = canonical_json_bytes({field: value[field]})[1:-1]
                    changed = b"{" + duplicate + b"," + raw_response[1:]
                elif violation == "nan-count":
                    changed = raw_response.replace(
                        canonical_json_bytes(value["count"]), b"NaN", 1
                    )
                elif violation == "extra-field":
                    value["extra"] = 1
                elif violation == "bool-count":
                    value["count"] = True
                elif violation == "negative-maxlen":
                    value["max_model_len"] = -1
                elif violation == "float-maxlen":
                    value["max_model_len"] = 32768.0
                elif violation == "huge-count":
                    value["count"] = live.MAX_TOKEN_PREFLIGHT_TOKENS + 1
                elif violation == "huge-token-id":
                    value["tokens"][0] = live.MAX_TOKEN_PREFLIGHT_TOKEN_ID + 1
                elif violation == "count-list-mismatch":
                    value["count"] += 1
                else:  # pragma: no cover - parametrization guard
                    raise AssertionError(violation)
                if violation not in {
                    "duplicate-count",
                    "duplicate-maxlen",
                    "nan-count",
                }:
                    changed = canonical_json_bytes(value)
            observer(raw_request, changed, status, complete)
            return live.TokenPreflightReceipt.make(
                raw_request=raw_request,
                raw_response=changed,
                source_chat_request_sha256=kwargs["source_chat_request_sha256"],
                max_output_tokens=kwargs["max_output_tokens"],
                http_status=200,
                latency_ms=0,
                raw_response_complete=True,
            )

    backend = InvalidTokenizeBackend()
    arm = StructuredHSWMArm(
        backend=backend,
        budget=_budget(),
        isolation_id=f"invalid-tokenize-{violation}",
        store_path=tmp_path / "state.sqlite3",
    )
    with pytest.raises(ContinualLiveError, match="token preflight"):
        arm.update(_one_token_batch())
    events = [json.loads(line) for line in arm.journal_path.read_text().splitlines()]
    assert events[-1]["event"] == "tokenize_failed"
    assert events[-1]["generation_dispatched"] is False
    assert not any(item["event"] == "generation_dispatch_intent" for item in events)
    assert backend.requests == []
    assert arm.store.active_snapshot().snapshot.canonical() == GENESIS.canonical()


@pytest.mark.parametrize("observer_mode", ["silent", "duplicate", "request", "response"])
def test_token_preflight_observer_is_exactly_once_and_exact(
    tmp_path: Path,
    observer_mode: str,
) -> None:
    class ObserverViolationBackend(ScriptedRelationalBackend):
        def tokenize(self, **kwargs: Any) -> live.TokenPreflightReceipt:
            observer = kwargs.pop("response_observer")
            captured: list[tuple[bytes, bytes, int | None, bool]] = []
            receipt = super().tokenize(
                **kwargs,
                response_observer=lambda *items: captured.append(items),
            )
            raw_request, raw_response, status, complete = captured[0]
            if observer_mode == "duplicate":
                observer(raw_request, raw_response, status, complete)
                observer(raw_request, raw_response, status, complete)
            elif observer_mode == "request":
                observer(b"{}", raw_response, status, complete)
            elif observer_mode == "response":
                observer(raw_request, b"{}", status, complete)
            return receipt

    backend = ObserverViolationBackend()
    arm = StructuredHSWMArm(
        backend=backend,
        budget=_budget(),
        isolation_id=f"tokenize-observer-{observer_mode}",
        store_path=tmp_path / "state.sqlite3",
    )
    with pytest.raises(ContinualLiveError, match="tokenize|preflight"):
        arm.update(_one_token_batch())
    events = [json.loads(line) for line in arm.journal_path.read_text().splitlines()]
    assert events[-1]["event"] == "tokenize_failed"
    assert not any(item["event"] == "generation_dispatch_intent" for item in events)
    assert backend.requests == []
    assert arm.store.active_snapshot().snapshot.canonical() == GENESIS.canonical()


@pytest.mark.parametrize("failure", ["timeout", "http-oversize", "invalid-json", "no-status"])
def test_token_preflight_transport_failure_is_audited_without_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    max_bytes = 32
    error_body = b"x" * 100

    class FakeResponse:
        def __init__(self, body: bytes, *, with_status: bool = True) -> None:
            self.body = body
            if with_status:
                self.status = 200

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def read(self, limit: int) -> bytes:
            return self.body[:limit]

    def fake_urlopen(request: Any, *, timeout: float) -> FakeResponse:
        del timeout
        assert request.full_url.endswith("/tokenize")
        if failure == "timeout":
            raise TimeoutError("tokenizer timeout")
        if failure == "http-oversize":
            raise live.urlerror.HTTPError(
                request.full_url,
                400,
                "bad tokenize request",
                {},
                io.BytesIO(error_body),
            )
        if failure == "invalid-json":
            return FakeResponse(b"not-json")
        return FakeResponse(b"{}", with_status=False)

    monkeypatch.setattr(live, "_urlopen_no_redirect", fake_urlopen)
    backend = OpenAICompatibleBackend(
        live.OpenAIBackendConfig(
            endpoint="http://model.invalid",
            model="fixture-model",
            max_response_bytes=max_bytes,
        )
    )
    arm = StructuredHSWMArm(
        backend=backend,
        budget=_budget(),
        isolation_id=f"tokenize-transport-{failure}",
        store_path=tmp_path / "state.sqlite3",
    )
    with pytest.raises(ContinualLiveError, match="token preflight"):
        arm.update(_one_token_batch())
    events = [json.loads(line) for line in arm.journal_path.read_text().splitlines()]
    assert events[-1]["event"] == "tokenize_failed"
    assert events[-1]["generation_dispatched"] is False
    assert not any(item["event"] == "generation_dispatch_intent" for item in events)
    raw_events = [
        item for item in events if item["event"] == "tokenize_raw_response_received"
    ]
    if failure == "timeout":
        assert raw_events == []
    else:
        assert len(raw_events) == 1
    if failure == "http-oversize":
        assert raw_events[0]["http_status"] == 400
        assert raw_events[0]["response_complete"] is False
        assert raw_events[0]["response_truncated"] is True
        assert base64.b64decode(raw_events[0]["raw_response_base64"]) == error_body[
            : max_bytes + 1
        ]
    assert arm.store.active_snapshot().snapshot.canonical() == GENESIS.canonical()


def test_token_preflight_redirect_is_not_followed_or_generated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    open_calls = 0

    class RedirectingOpener:
        def open(self, request: Any, *, timeout: float) -> Any:
            nonlocal open_calls
            del timeout
            open_calls += 1
            raise live.urlerror.HTTPError(
                request.full_url,
                302,
                "redirect forbidden",
                {"Location": "http://elsewhere.invalid/tokenize"},
                io.BytesIO(b'{"error":"redirect forbidden"}'),
            )

    def fake_build_opener(*handlers: Any) -> RedirectingOpener:
        assert len(handlers) == 2
        assert isinstance(handlers[0], live.urlrequest.ProxyHandler)
        assert handlers[0].proxies == {}
        assert isinstance(handlers[1], live._NoRedirectHandler)
        assert handlers[1].redirect_request(None) is None
        return RedirectingOpener()

    monkeypatch.setattr(live.urlrequest, "build_opener", fake_build_opener)
    arm = StructuredHSWMArm(
        backend=OpenAICompatibleBackend(
            live.OpenAIBackendConfig(
                endpoint="http://model.invalid",
                model="fixture-model",
            )
        ),
        budget=_budget(),
        isolation_id="tokenize-no-redirect",
        store_path=tmp_path / "state.sqlite3",
    )
    with pytest.raises(ContinualLiveError, match="HTTP outcome 302"):
        arm.update(_one_token_batch())
    assert open_calls == 1
    events = [json.loads(line) for line in arm.journal_path.read_text().splitlines()]
    assert events[-1]["event"] == "tokenize_failed"
    assert events[-1]["generation_dispatched"] is False
    assert not any(item["event"] == "generation_dispatch_intent" for item in events)
    assert arm.store.active_snapshot().snapshot.canonical() == GENESIS.canonical()


def test_token_preflight_context_rejection_never_calls_generation(
    tmp_path: Path,
) -> None:
    class ContextRejectBackend(ScriptedRelationalBackend):
        @property
        def identity(self) -> Mapping[str, Any]:
            return {**super().identity, "expected_max_model_len": 100}

        def tokenize(self, **kwargs: Any) -> live.TokenPreflightReceipt:
            raw_request = kwargs["raw_request"]
            raw_response = canonical_json_bytes(
                {
                    "count": 90,
                    "max_model_len": 100,
                    "token_strs": None,
                    "tokens": list(range(90)),
                }
            )
            kwargs["response_observer"](raw_request, raw_response, 200, True)
            return live.TokenPreflightReceipt.make(
                raw_request=raw_request,
                raw_response=raw_response,
                source_chat_request_sha256=kwargs["source_chat_request_sha256"],
                max_output_tokens=kwargs["max_output_tokens"],
                http_status=200,
                latency_ms=0,
                raw_response_complete=True,
            )

    backend = ContextRejectBackend()
    arm = StructuredHSWMArm(
        backend=backend,
        budget=_budget(),
        isolation_id="tokenize-context-reject",
        store_path=tmp_path / "state.sqlite3",
    )
    with pytest.raises(ContinualLiveError, match="insufficient model context"):
        arm.update(_one_token_batch())
    events = [json.loads(line) for line in arm.journal_path.read_text().splitlines()]
    assert events[-1]["event"] == "tokenize_rejected"
    assert events[-1]["generation_dispatched"] is False
    assert backend.requests == []
    assert arm.store.active_snapshot().snapshot.canonical() == GENESIS.canonical()


def test_token_preflight_rejects_frozen_max_model_length_drift(
    tmp_path: Path,
) -> None:
    class MaxlenDriftBackend(ScriptedRelationalBackend):
        def tokenize(self, **kwargs: Any) -> live.TokenPreflightReceipt:
            observer = kwargs.pop("response_observer")
            captured: list[tuple[bytes, bytes, int | None, bool]] = []
            super().tokenize(
                **kwargs,
                response_observer=lambda *items: captured.append(items),
            )
            raw_request, raw_response, status, complete = captured[0]
            value = json.loads(raw_response)
            value["max_model_len"] = 65_536
            changed = canonical_json_bytes(value)
            observer(raw_request, changed, status, complete)
            return live.TokenPreflightReceipt.make(
                raw_request=raw_request,
                raw_response=changed,
                source_chat_request_sha256=kwargs["source_chat_request_sha256"],
                max_output_tokens=kwargs["max_output_tokens"],
                http_status=200,
                latency_ms=0,
                raw_response_complete=True,
            )

    backend = MaxlenDriftBackend()
    arm = StructuredHSWMArm(
        backend=backend,
        budget=_budget(),
        isolation_id="tokenize-maxlen-drift",
        store_path=tmp_path / "state.sqlite3",
    )
    with pytest.raises(ContinualLiveError, match="frozen backend identity"):
        arm.update(_one_token_batch())
    events = [json.loads(line) for line in arm.journal_path.read_text().splitlines()]
    assert events[-1]["event"] == "tokenize_rejected"
    assert events[-1]["generation_dispatched"] is False
    assert backend.requests == []


def test_missing_token_preflight_method_never_dispatches_generation(
    tmp_path: Path,
) -> None:
    class MissingPreflightBackend(ScriptedRelationalBackend):
        tokenize = None

    backend = MissingPreflightBackend()
    arm = StructuredHSWMArm(
        backend=backend,
        budget=_budget(),
        isolation_id="missing-token-preflight",
        store_path=tmp_path / "state.sqlite3",
    )
    with pytest.raises(TypeError, match="not callable"):
        arm.update(_one_token_batch())
    events = [json.loads(line) for line in arm.journal_path.read_text().splitlines()]
    assert [item["event"] for item in events] == [
        "intent",
        "tokenize_intent",
        "tokenize_failed",
    ]
    assert events[-1]["generation_dispatched"] is False
    assert backend.requests == []


def test_completion_prompt_usage_must_equal_token_preflight_count(
    tmp_path: Path,
) -> None:
    class UsageMismatchBackend(ScriptedRelationalBackend):
        def complete(self, **kwargs: Any) -> ModelCompletion:
            observer = kwargs.pop("response_observer")
            captured: list[tuple[bytes, bytes]] = []
            completion = super().complete(
                **kwargs,
                response_observer=lambda *items: captured.append(items),
            )
            raw_request, raw_response = captured[0]
            value = json.loads(raw_response)
            value["usage"]["prompt_tokens"] = completion.input_tokens + 1
            value["usage"]["total_tokens"] = (
                completion.input_tokens + 1 + completion.output_tokens
            )
            changed = canonical_json_bytes(value)
            observer(raw_request, changed)
            return replace(
                completion,
                raw_response_json=changed.decode("utf-8"),
                response_sha256=sha256(changed).hexdigest(),
                input_tokens=completion.input_tokens + 1,
            )

    arm = StructuredHSWMArm(
        backend=UsageMismatchBackend(),
        budget=_budget(),
        isolation_id="preflight-usage-mismatch",
        store_path=tmp_path / "state.sqlite3",
    )
    with pytest.raises(ContinualLiveError, match="token preflight differs"):
        arm.update(_one_token_batch())
    events = [json.loads(line) for line in arm.journal_path.read_text().splitlines()]
    assert events[-1]["event"] == "rejected_response"
    assert arm.ledger == []
    assert arm.store.active_snapshot().snapshot.canonical() == GENESIS.canonical()


@pytest.mark.parametrize("usage_value", [True, 1.0])
def test_completion_usage_rejects_bool_and_float_preimages(
    usage_value: object,
) -> None:
    raw_request = canonical_json_bytes({"request": "fixture"})
    text = '{"choice":"x"}'
    raw_response = canonical_json_bytes(
        {
            "choices": [
                {"finish_reason": "stop", "message": {"content": text}}
            ],
            "model": "fixture",
            "usage": {
                "completion_tokens": 1,
                "prompt_tokens": usage_value,
                "total_tokens": 2,
            },
        }
    )
    with pytest.raises(ContinualLiveError, match="raw response usage"):
        ModelCompletion(
            text=text,
            raw_request_json=raw_request.decode("utf-8"),
            raw_response_json=raw_response.decode("utf-8"),
            request_sha256=sha256(raw_request).hexdigest(),
            response_sha256=sha256(raw_response).hexdigest(),
            model="fixture",
            input_tokens=1,
            output_tokens=1,
            latency_ms=0,
            usage_reported=True,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("input_tokens", 1.0),
        ("output_tokens", 1.0),
        ("latency_ms", 0.0),
        ("usage_reported", 1),
    ],
)
def test_model_completion_persisted_telemetry_requires_exact_types(
    field: str,
    value: object,
) -> None:
    raw_request = canonical_json_bytes({"request": "fixture"})
    text = '{"choice":"x"}'
    raw_response = canonical_json_bytes(
        {
            "choices": [
                {"finish_reason": "stop", "message": {"content": text}}
            ],
            "model": "fixture",
            "usage": {
                "completion_tokens": 1,
                "prompt_tokens": 1,
                "total_tokens": 2,
            },
        }
    )
    values: dict[str, Any] = {
        "text": text,
        "raw_request_json": raw_request.decode("utf-8"),
        "raw_response_json": raw_response.decode("utf-8"),
        "request_sha256": sha256(raw_request).hexdigest(),
        "response_sha256": sha256(raw_response).hexdigest(),
        "model": "fixture",
        "input_tokens": 1,
        "output_tokens": 1,
        "latency_ms": 0,
        "usage_reported": True,
    }
    values[field] = value
    with pytest.raises(ContinualLiveError):
        ModelCompletion(**values)


def test_model_completion_rejects_wrong_total_tokens() -> None:
    raw_request = canonical_json_bytes({"request": "fixture"})
    text = '{"choice":"x"}'
    raw_response = canonical_json_bytes(
        {
            "choices": [
                {"finish_reason": "stop", "message": {"content": text}}
            ],
            "model": "fixture",
            "usage": {
                "completion_tokens": 1,
                "prompt_tokens": 1,
                "total_tokens": 3,
            },
        }
    )
    with pytest.raises(ContinualLiveError, match="raw response usage"):
        ModelCompletion(
            text=text,
            raw_request_json=raw_request.decode("utf-8"),
            raw_response_json=raw_response.decode("utf-8"),
            request_sha256=sha256(raw_request).hexdigest(),
            response_sha256=sha256(raw_response).hexdigest(),
            model="fixture",
            input_tokens=1,
            output_tokens=1,
            latency_ms=0,
            usage_reported=True,
        )


def test_dynamic_second_public_preflight_rejection_preserves_generation_two(
    tmp_path: Path,
) -> None:
    backends: list[ScriptedRelationalBackend] = []

    class DynamicLimitBackend(ScriptedRelationalBackend):
        def __init__(self) -> None:
            super().__init__()
            self.preflight_calls = 0

        def tokenize(self, **kwargs: Any) -> live.TokenPreflightReceipt:
            self.preflight_calls += 1
            if self.preflight_calls != 2:
                return super().tokenize(**kwargs)
            count = live.PUBLIC_SCHEMA_GATE_MAX_UPDATE_INPUT_TOKENS + 1
            raw_request = kwargs["raw_request"]
            raw_response = canonical_json_bytes(
                {
                    "count": count,
                    "max_model_len": 32768,
                    "token_strs": None,
                    "tokens": list(range(count)),
                }
            )
            kwargs["response_observer"](raw_request, raw_response, 200, True)
            return live.TokenPreflightReceipt.make(
                raw_request=raw_request,
                raw_response=raw_response,
                source_chat_request_sha256=kwargs["source_chat_request_sha256"],
                max_output_tokens=kwargs["max_output_tokens"],
                http_status=200,
                latency_ms=0,
                raw_response_complete=True,
            )

    def backend_factory() -> ScriptedRelationalBackend:
        backend = DynamicLimitBackend()
        backends.append(backend)
        return backend

    state_dir = tmp_path / "dynamic-public-limit"
    with pytest.raises(ContinualLiveError, match="frozen update input ceiling"):
        run_public_schema_gate(
            backend_factory=backend_factory,
            state_dir=state_dir,
        )
    structured_backend = backends[0]
    assert isinstance(structured_backend, DynamicLimitBackend)
    assert structured_backend.preflight_calls == 2
    assert len(structured_backend.requests) == 1
    events = [
        json.loads(line)
        for line in (state_dir / "structured" / "calls.jsonl").read_text().splitlines()
    ]
    assert sum(item["event"] == "generation_dispatch_intent" for item in events) == 1
    assert events[-1]["event"] == "tokenize_rejected"
    assert events[-1]["generation_dispatched"] is False
    store = live.SQLiteSelfModelStore(
        state_dir / "structured" / "state.sqlite3",
        policy=live._proposal_policy(
            ArmBudget(
                answer_max_output_tokens=128,
                update_max_output_tokens=6144,
                max_input_bytes=2_000_000,
                max_state_bytes=1_000_000,
            )
        ),
    )
    try:
        active = store.active_snapshot()
        assert active.generation == 2
        assert len(active.snapshot.memories) == 140
    finally:
        store.close()


def test_persisted_token_preflight_revalidation_rejects_rehashed_maxlen_tamper(
    tmp_path: Path,
) -> None:
    arm = StructuredHSWMArm(
        backend=ScriptedRelationalBackend(),
        budget=_budget(),
        isolation_id="persisted-token-preflight",
        store_path=tmp_path / "state.sqlite3",
    )
    arm.update(_one_token_batch())
    persisted = arm.ledger[0].canonical()
    assert live._revalidate_token_preflight_ledger_entry(persisted).count == (
        arm.ledger[0].completion.input_tokens
    )
    tampered = json.loads(canonical_json_bytes(persisted))
    receipt = tampered["token_preflight"]
    raw_response = json.loads(receipt["raw_response_json"])
    raw_response["max_model_len"] = 65_536
    changed = canonical_json_bytes(raw_response)
    receipt["max_model_len"] = 65_536
    receipt["raw_response_json"] = changed.decode("utf-8")
    receipt["raw_response_bytes"] = len(changed)
    receipt["response_sha256"] = sha256(changed).hexdigest()
    unsigned = dict(receipt)
    unsigned.pop("receipt_sha256")
    receipt["receipt_sha256"] = live.canonical_sha256(unsigned)
    with pytest.raises(ContinualLiveError, match="differs from its chat ledger"):
        live._revalidate_token_preflight_ledger_entry(tampered)


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [("count", True), ("max_model_len", 32768.0)],
)
def test_token_receipt_rejects_equal_noninteger_raw_response_fields(
    tmp_path: Path,
    field: str,
    bad_value: object,
) -> None:
    arm = StructuredHSWMArm(
        backend=ScriptedRelationalBackend(),
        budget=_budget(),
        isolation_id=f"raw-token-type-{field}",
        store_path=tmp_path / "state.sqlite3",
    )
    arm.update(_one_token_batch())
    receipt = arm.ledger[0].token_preflight.canonical()
    raw_response = json.loads(receipt["raw_response_json"])
    if field == "count":
        raw_response["count"] = bad_value
        receipt["count"] = 1
        raw_response["tokens"] = [0]
    else:
        raw_response["max_model_len"] = bad_value
    changed = canonical_json_bytes(raw_response)
    receipt["raw_response_json"] = changed.decode("utf-8")
    receipt["raw_response_bytes"] = len(changed)
    receipt["response_sha256"] = sha256(changed).hexdigest()
    unsigned = dict(receipt)
    unsigned.pop("receipt_sha256")
    receipt["receipt_sha256"] = live.canonical_sha256(unsigned)
    with pytest.raises(ContinualLiveError, match="response content"):
        live.TokenPreflightReceipt.from_mapping(receipt)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("reasoning", "hidden reasoning"),
        ("reasoning_content", "hidden reasoning"),
        ("refusal", "hidden refusal"),
        ("tool_calls", [{"id": "hidden-tool"}]),
    ],
)
def test_response_side_channels_fail_before_state_change(
    tmp_path: Path, field: str, value: Any
) -> None:
    class SideChannelBackend(ScriptedRelationalBackend):
        def complete(self, **kwargs: Any) -> ModelCompletion:
            observer = kwargs.pop("response_observer")
            observed: list[tuple[bytes, bytes]] = []
            completion = super().complete(
                **kwargs,
                response_observer=lambda request, response: observed.append(
                    (request, response)
                ),
            )
            raw_request, raw_response = observed[0]
            envelope = json.loads(raw_response)
            envelope["choices"][0]["message"][field] = value
            changed = canonical_json_bytes(envelope)
            observer(raw_request, changed)
            return replace(
                completion,
                raw_response_json=changed.decode(),
                response_sha256=sha256(changed).hexdigest(),
            )

    arm = StructuredHSWMArm(
        backend=SideChannelBackend(),
        budget=_budget(),
        isolation_id=f"side-channel-{field}",
        store_path=tmp_path / "state.sqlite3",
    )
    with pytest.raises(ContinualLiveError, match="non-content side channel"):
        arm.update(_one_token_batch())
    events = [json.loads(line) for line in arm.journal_path.read_text().splitlines()]
    assert [item["event"] for item in events] == TOKEN_PREFLIGHT_SUCCESS_EVENTS + [
        "raw_response_received",
        "failed",
    ]
    assert events[-1]["outcome"] == "received_invalid"
    assert arm.store.active_snapshot().snapshot.canonical() == GENESIS.canonical()


@pytest.mark.parametrize("finish_reason", ["length", "tool_calls", "content_filter"])
def test_nonstop_finish_reason_is_rejected_before_state_change(
    tmp_path: Path,
    finish_reason: str,
) -> None:
    class FinishReasonBackend(ScriptedRelationalBackend):
        def complete(self, **kwargs: Any) -> ModelCompletion:
            observer = kwargs.pop("response_observer")
            captured: list[tuple[bytes, bytes]] = []
            completion = super().complete(
                **kwargs,
                response_observer=lambda *items: captured.append(items),
            )
            raw_request, raw_response = captured[0]
            value = json.loads(raw_response)
            value["choices"][0]["finish_reason"] = finish_reason
            changed = canonical_json_bytes(value)
            observer(raw_request, changed)
            return replace(
                completion,
                raw_response_json=changed.decode("utf-8"),
                response_sha256=sha256(changed).hexdigest(),
            )

    arm = StructuredHSWMArm(
        backend=FinishReasonBackend(),
        budget=_budget(),
        isolation_id=f"finish-{finish_reason}",
        store_path=tmp_path / "state.sqlite3",
    )
    with pytest.raises(ContinualLiveError, match="finish_reason"):
        arm.update(_one_token_batch())
    events = [json.loads(line) for line in arm.journal_path.read_text().splitlines()]
    assert events[-1]["event"] == "failed"
    assert events[-1]["generation_dispatched"] is True
    assert any(item["event"] == "raw_response_received" for item in events)
    assert arm.ledger == []
    assert arm.store.active_snapshot().snapshot.canonical() == GENESIS.canonical()


@pytest.mark.parametrize(
    ("field", "needle"),
    [
        ("choice", '"finish_reason":"stop"'),
        ("usage", '"prompt_tokens":'),
        ("nonfinite", ""),
    ],
)
def test_non_strict_completion_envelopes_are_rejected_before_state_change(
    tmp_path: Path,
    field: str,
    needle: str,
) -> None:
    class DuplicateEnvelopeBackend(ScriptedRelationalBackend):
        def complete(self, **kwargs: Any) -> ModelCompletion:
            observer = kwargs.pop("response_observer")
            captured: list[tuple[bytes, bytes]] = []
            completion = super().complete(
                **kwargs,
                response_observer=lambda *items: captured.append(items),
            )
            raw_request, raw_response = captured[0]
            text = raw_response.decode("utf-8")
            if field == "nonfinite":
                changed_text = '{"nonfinite":NaN,' + text[1:]
            elif field == "choice":
                changed_text = text.replace(needle, f"{needle},{needle}", 1)
            else:
                start = text.index(needle) + len(needle)
                end = text.index(",", start)
                original = f"{needle}{text[start:end]}"
                changed_text = text.replace(original, f"{original},{original}", 1)
            changed = changed_text.encode("utf-8")
            observer(raw_request, changed)
            return replace(
                completion,
                raw_response_json=changed_text,
                response_sha256=sha256(changed).hexdigest(),
            )

    arm = StructuredHSWMArm(
        backend=DuplicateEnvelopeBackend(),
        budget=_budget(),
        isolation_id=f"duplicate-completion-{field}",
        store_path=tmp_path / "state.sqlite3",
    )
    with pytest.raises(ContinualLiveError, match="strict JSON"):
        arm.update(_one_token_batch())
    events = [json.loads(line) for line in arm.journal_path.read_text().splitlines()]
    assert events[-1]["event"] == "failed"
    assert events[-1]["generation_dispatched"] is True
    assert not any(item["event"] == "completed" for item in events)
    assert arm.ledger == []
    assert arm.store.active_snapshot().snapshot.canonical() == GENESIS.canonical()


def test_schema_invalid_completion_is_rejected_before_completed_or_commit(
    tmp_path: Path,
) -> None:
    class InvalidSchemaBodyBackend(ScriptedRelationalBackend):
        def complete(self, **kwargs: Any) -> ModelCompletion:
            observer = kwargs.pop("response_observer")
            observed: list[tuple[bytes, bytes]] = []
            completion = super().complete(
                **kwargs,
                response_observer=lambda request, response: observed.append(
                    (request, response)
                ),
            )
            raw_request, raw_response = observed[0]
            envelope = json.loads(raw_response)
            text = '{"bad":1}'
            envelope["choices"][0]["message"]["content"] = text
            envelope["usage"]["completion_tokens"] = 3
            envelope["usage"]["total_tokens"] = completion.input_tokens + 3
            changed = canonical_json_bytes(envelope)
            observer(raw_request, changed)
            return replace(
                completion,
                text=text,
                raw_response_json=changed.decode(),
                response_sha256=sha256(changed).hexdigest(),
                output_tokens=3,
            )

    arm = StructuredHSWMArm(
        backend=InvalidSchemaBodyBackend(),
        budget=_budget(),
        isolation_id="invalid-schema-body",
        store_path=tmp_path / "state.sqlite3",
    )
    with pytest.raises(ContinualLiveError, match="object schema"):
        arm.update(_one_token_batch())
    events = [json.loads(line) for line in arm.journal_path.read_text().splitlines()]
    assert [item["event"] for item in events] == TOKEN_PREFLIGHT_SUCCESS_EVENTS + [
        "raw_response_received",
        "response_received",
        "rejected_response",
    ]
    assert arm.ledger == []
    assert arm.store.active_snapshot().snapshot.canonical() == GENESIS.canonical()


@pytest.mark.parametrize("observer_mode", ["silent", "mismatch", "duplicate"])
def test_response_observer_is_exactly_once_and_matches_completion(
    tmp_path: Path, observer_mode: str
) -> None:
    class ObserverViolationBackend(ScriptedRelationalBackend):
        def complete(self, **kwargs: Any) -> ModelCompletion:
            observer = kwargs.pop("response_observer")
            observed: list[tuple[bytes, bytes]] = []
            completion = super().complete(
                **kwargs,
                response_observer=lambda request, response: observed.append(
                    (request, response)
                ),
            )
            raw_request, raw_response = observed[0]
            if observer_mode == "mismatch":
                observer(raw_request, b'{"different":"raw response"}')
            elif observer_mode == "duplicate":
                observer(raw_request, raw_response)
                observer(raw_request, raw_response)
            return completion

    arm = StructuredHSWMArm(
        backend=ObserverViolationBackend(),
        budget=_budget(),
        isolation_id=f"observer-{observer_mode}",
        store_path=tmp_path / "state.sqlite3",
    )
    with pytest.raises(ContinualLiveError, match="raw response|exactly one"):
        arm.update(_one_token_batch())
    events = [json.loads(line) for line in arm.journal_path.read_text().splitlines()]
    assert sum(item["event"] == "intent" for item in events) == 1
    assert events[-1]["event"] == "rejected_response"
    assert not any(item["event"] == "completed" for item in events)
    assert arm.ledger == []
    assert arm.store.active_snapshot().snapshot.canonical() == GENESIS.canonical()


def test_thinking_must_be_explicitly_disabled_before_any_call(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="enable_thinking=false"):
        live.OpenAIBackendConfig(
            endpoint="http://model.invalid",
            model="fixture-model",
            enable_thinking=True,
        )

    class MissingThinkingIdentityBackend(ScriptedRelationalBackend):
        @property
        def identity(self) -> Mapping[str, Any]:
            return {
                key: value
                for key, value in super().identity.items()
                if key != "enable_thinking"
            }

    backend = MissingThinkingIdentityBackend()
    arm = StructuredHSWMArm(
        backend=backend,
        budget=_budget(),
        isolation_id="missing-thinking-identity",
        store_path=tmp_path / "state.sqlite3",
    )
    with pytest.raises(ContinualLiveError, match="explicitly disable thinking"):
        arm.update(_one_token_batch())
    assert backend.requests == []
    assert not arm.journal_path.exists()
    assert arm.store.active_snapshot().snapshot.canonical() == GENESIS.canonical()


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("endpoint", None),
        ("endpoint", "http://user:secret@127.0.0.1:8000"),
        ("endpoint", "http://127.0.0.1:8000/v1"),
        ("endpoint", "http://127.0.0.1:8000?query=1"),
        ("endpoint", "http://127.0.0.1:8000#fragment"),
        ("model", None),
        ("model", ""),
        ("api_key", False),
        ("api_key", ""),
        ("timeout_seconds", True),
        ("timeout_seconds", float("nan")),
        ("timeout_seconds", float("inf")),
        ("timeout_seconds", 0),
        ("timeout_seconds", 86_401),
        ("temperature", False),
        ("temperature", 0),
        ("temperature", -0.0),
        ("temperature", float("nan")),
        ("temperature", float("inf")),
        ("top_p", True),
        ("top_p", 1),
        ("top_p", float("nan")),
        ("top_p", float("inf")),
        ("seed", False),
        ("seed", 0.0),
        ("max_response_bytes", True),
        ("max_response_bytes", 1.5),
        ("max_response_bytes", 0),
        ("max_response_bytes", live.MAX_RAW_REQUEST_BYTES * 2 + 1),
        ("expected_max_model_len", True),
        ("expected_max_model_len", 32768.0),
    ],
)
def test_backend_config_rejects_ambiguous_or_unbounded_values(
    field: str,
    bad_value: object,
) -> None:
    values: dict[str, Any] = {
        "endpoint": "http://127.0.0.1:8000",
        "model": "fixture-model",
    }
    values[field] = bad_value
    with pytest.raises(ValueError):
        live.OpenAIBackendConfig(**values)


def test_reported_answer_usage_cannot_exceed_request_budget(tmp_path: Path) -> None:
    class OverBudgetAnswerBackend(ScriptedRelationalBackend):
        def complete(self, **kwargs: Any) -> ModelCompletion:
            observer = kwargs.pop("response_observer")
            observed: list[tuple[bytes, bytes]] = []
            completion = super().complete(
                **kwargs,
                response_observer=lambda request, response: observed.append(
                    (request, response)
                ),
            )
            raw_request, raw_response = observed[0]
            envelope = json.loads(raw_response)
            envelope["usage"]["completion_tokens"] = 129
            envelope["usage"]["total_tokens"] = completion.input_tokens + 129
            changed = canonical_json_bytes(envelope)
            observer(raw_request, changed)
            return replace(
                completion,
                raw_response_json=changed.decode(),
                response_sha256=sha256(changed).hexdigest(),
                output_tokens=129,
            )

    arm = StructuredHSWMArm(
        backend=OverBudgetAnswerBackend(),
        budget=_budget(),
        isolation_id="over-budget-answer",
        store_path=tmp_path / "state.sqlite3",
    )
    probe = PublicProbe(
        step=0,
        source="node-a",
        relations=("rel-x",),
        choices=("node-b", "node-c"),
    )
    with pytest.raises(ContinualLiveError, match="exceeds the request budget"):
        arm.answer(probe)
    events = [json.loads(line) for line in arm.journal_path.read_text().splitlines()]
    assert events[-1]["event"] == "rejected_response"
    assert not any(item["event"] == "completed" for item in events)
    assert arm.ledger == []


@pytest.mark.parametrize(
    "unsupported",
    [
        "uniqueItems",
        "contains",
        "minContains",
        "maxContains",
        "multipleOf",
        "patternProperties",
        "propertyNames",
        "format",
    ],
)
def test_unsupported_json_schema_keyword_fails_before_call(
    unsupported: str,
) -> None:
    backend = ScriptedRelationalBackend()
    schema = live._strict_json_object(
        {"value": {"maxLength": 8, "type": "string"}}
    )
    schema[unsupported] = True
    with pytest.raises(ContinualLiveError, match="unsupported keywords"):
        live.JSONSchemaContract.make("unsupported_schema", schema)
    assert backend.requests == []


def test_schema_and_raw_envelope_tampering_are_rejected(tmp_path: Path) -> None:
    arm = StructuredHSWMArm(
        backend=ScriptedRelationalBackend(),
        budget=_budget(),
        isolation_id="schema-tamper",
        store_path=tmp_path / "state.sqlite3",
    )
    arm.update(_one_token_batch())
    entry = arm.ledger[0]
    with pytest.raises(ContinualLiveError, match="schema digest mismatch"):
        replace(entry, response_schema_sha256="0" * 64)

    request_value = json.loads(entry.completion.raw_request_json)
    request_value["response_format"]["json_schema"]["strict"] = False
    changed_request = canonical_json_bytes(request_value)
    changed_completion = replace(
        entry.completion,
        raw_request_json=changed_request.decode(),
        request_sha256=sha256(changed_request).hexdigest(),
    )
    with pytest.raises(ContinualLiveError, match="token preflight differs"):
        replace(
            entry,
            completion=changed_completion,
            raw_request_bytes=len(changed_request),
        )


def test_schema_and_completion_text_hard_byte_caps() -> None:
    oversized_schema = live._strict_json_object(
        {"value": {"enum": ["x" * live.MAX_RESPONSE_SCHEMA_BYTES], "type": "string"}}
    )
    with pytest.raises(ContinualLiveError, match="schema exceeds"):
        live.JSONSchemaContract.make("oversized_schema", oversized_schema)
    with pytest.raises(ContinualLiveError, match="completion text exceeds"):
        ModelCompletion(
            text="x" * (live.MAX_COMPLETION_TEXT_BYTES + 1),
            raw_request_json="{}",
            raw_response_json="{}",
            request_sha256="0" * 64,
            response_sha256="0" * 64,
            model="fixture",
            input_tokens=0,
            output_tokens=0,
            latency_ms=0,
            usage_reported=False,
        )
    with pytest.raises(ContinualLiveError, match="string bound"):
        live._plain_memory_response_schema().validate_instance(
            {"memory": "x" * (live.MAX_PLAIN_MEMORY_CHARS + 1)}
        )
    with pytest.raises(ContinualLiveError, match="schema enum"):
        live._choice_response_schema(("left", "right")).validate_instance(
            {"choice": "outside"}
        )


def test_public_schema_gate_cli_has_no_seed_path_and_binds_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted = ScriptedRelationalBackend()

    def scripted_complete(self: Any, **kwargs: Any) -> ModelCompletion:
        return scripted.complete(**kwargs)

    def scripted_tokenize(self: Any, **kwargs: Any) -> live.TokenPreflightReceipt:
        return scripted.tokenize(**kwargs)

    monkeypatch.setattr(OpenAICompatibleBackend, "complete", scripted_complete)
    monkeypatch.setattr(OpenAICompatibleBackend, "tokenize", scripted_tokenize)
    output = tmp_path / "gate-output"
    argv = [
        "--endpoint",
        "http://127.0.0.1:8000",
        "--model",
        "deterministic-fixture",
        "--output-dir",
        str(output),
        "--timeout",
        "600",
        "--source-revision",
        "c" * 40,
        "--container-digest",
        "sha256:" + "d" * 64,
        "--service-binding",
        "sha256:" + "e" * 64,
    ]
    assert schema_gate_main(argv) == 0
    result = json.loads((output / "gate_result.json").read_text())
    assert result["valid"] is True
    assert result["model_generation_calls_observed"] == 4
    assert result["token_preflight_calls_observed"] == 4
    assert result["outbound_http_requests_observed"] == 8
    prereg = json.loads((output / "gate_preregistration.json").read_text())
    assert prereg["no_precommit_or_seed_path"] is True
    assert prereg["protocol"] == "hswm-public-schema-gate/v5"
    assert prereg["indexed_authoring_view_schema"] == (
        "hswm-indexed-authoring-view/v1"
    )
    assert prereg["mutation_expressivity"] == "compact-adapter-subset"
    assert prereg["provider_context_window_tokens"] == 32768
    assert prereg["max_update_input_tokens"] == 26624
    assert prereg["update_max_tokens"] == 6144
    assert prereg["update_max_tokens"] == prereg["output_token_ceiling"]
    assert prereg["generation_call_budget"] == 4
    assert prereg["token_preflight_call_budget"] == 4
    assert prereg["outbound_http_request_budget"] == 8
    terminal = json.loads((output / "terminal_receipt.json").read_text())
    assert terminal["schema_gate_passed"] is True
    assert terminal["status"] == "success"
    assert terminal["generation_calls_expected"] == 4
    assert terminal["token_preflight_calls_expected"] == 4
    assert terminal["outbound_http_requests_expected"] == 8
    assert "gate_result.json" in terminal["artifact_sha256s"]
    assert "state/structured/calls.jsonl" in terminal["artifact_sha256s"]
    assert all("seed" not in path for path in terminal["artifact_sha256s"])
    persistent_files = {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
    }
    assert set(terminal["artifact_sha256s"]) == persistent_files - {
        "terminal_receipt.json"
    }
    assert all(
        terminal["artifact_sha256s"][relative]
        == sha256((output / relative).read_bytes()).hexdigest()
        for relative in terminal["artifact_sha256s"]
    )
    assert terminal["checkpointed_sqlite_artifacts"] == [
        "state/structured/state.sqlite3"
    ]
    assert not list(output.rglob("*-wal"))
    assert not list(output.rglob("*-shm"))
    assert not list(output.rglob("*-journal"))
    reopened = live.SQLiteSelfModelStore(
        output / "state" / "structured" / "state.sqlite3",
        policy=live._proposal_policy(_budget()),
    )
    try:
        active = reopened.active_snapshot()
        assert len(active.snapshot.memories) == 144
        assert active.generation == 3
    finally:
        reopened.close()
    with pytest.raises(ContinualLiveError, match="no resume"):
        schema_gate_main(argv)
    with pytest.raises(SystemExit):
        schema_gate_main([*argv, "--seed-file", str(tmp_path / "forbidden")])


def test_sealed_probe_pack_is_deterministic_and_unused() -> None:
    manifest = _small_stream()
    left = make_sealed_probe_pack(manifest)
    right = make_sealed_probe_pack(manifest)
    assert left == right
    assert len(left) == 5
    used = {(query.source, query.relations) for query in manifest.queries}
    for probe, answer in left:
        assert (probe.source, probe.relations) not in used
        assert answer in probe.choices
        assert probe.step > manifest.horizon


def test_exact_frozen_recovery_precommit_fixture() -> None:
    path = (
        Path(__file__).parent
        / "fixtures"
        / "pilot_recovery_precommit_v3.canonical.json"
    )
    raw = path.read_bytes()
    assert len(raw) == 4934
    assert raw[-1:] == b"}"
    assert sha256(raw).hexdigest() == live.FROZEN_RECOVERY_PRECOMMIT_ARTIFACT_SHA256
    value, observed = live._read_pilot_precommit(path)
    assert observed == raw
    unsigned = {key: item for key, item in value.items() if key != "precommit_sha256"}
    assert live.canonical_sha256(unsigned) == live.FROZEN_RECOVERY_PRECOMMIT_SHA256
    assert value["selected_seed_indices"] == [2, 3]
    assert value["recovery_execution"]["per_call_timeout_seconds"] == 600.0


def test_cli_rejects_consumed_v3_even_with_exact_failure_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seeds = tuple(bytes([index + 1]) * 32 for index in range(4))
    seed_path = tmp_path / "seeds.json"
    seed_path.write_text(json.dumps([seed.hex() for seed in seeds]), encoding="ascii")
    seed_path.chmod(0o600)
    v2_path = tmp_path / "v2-precommit.json"
    _write_test_precommit(v2_path, seeds, monkeypatch)
    archive_path, receipt_path, binding = _write_failed_primary_fixture(
        tmp_path,
        seeds=seeds,
        v2_precommit_path=v2_path,
        monkeypatch=monkeypatch,
    )
    precommit_path = tmp_path / "v3-precommit.json"
    _write_test_recovery_precommit(
        precommit_path,
        seeds=seeds,
        binding=binding,
        monkeypatch=monkeypatch,
    )
    output = tmp_path / "output"

    calls = 0

    def fail_call(self: Any, **kwargs: Any) -> ModelCompletion:
        nonlocal calls
        calls += 1
        raise AssertionError("consumed v3 must fail before any model call")

    monkeypatch.setattr(OpenAICompatibleBackend, "complete", fail_call)
    argv = [
        "--endpoint",
        "http://model.invalid",
        "--model",
        "fixture-model",
        "--streams",
        "2",
        "--seed-file",
        str(seed_path),
        "--precommit-file",
        str(precommit_path),
        "--failed-run-artifacts-tar",
        str(archive_path),
        "--failed-run-receipt",
        str(receipt_path),
        "--output-dir",
        str(output),
        "--source-revision",
        "c" * 40,
        "--container-digest",
        "sha256:" + "d" * 64,
        "--service-binding",
        "sha256:" + "e" * 64,
        "--timeout",
        "600",
        "--removal-restore",
    ]
    with pytest.raises(ContinualLiveError, match="permanently prohibited"):
        main(argv)
    assert calls == 0
    assert not any(output.iterdir())


def test_recovery_rejects_tampered_failed_run_tar_and_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seeds = tuple(bytes([index + 21]) * 32 for index in range(4))
    v2_path = tmp_path / "v2.json"
    _write_test_precommit(v2_path, seeds, monkeypatch)
    archive_path, receipt_path, binding = _write_failed_primary_fixture(
        tmp_path,
        seeds=seeds,
        v2_precommit_path=v2_path,
        monkeypatch=monkeypatch,
    )
    v3_path = tmp_path / "v3.json"
    _write_test_recovery_precommit(
        v3_path,
        seeds=seeds,
        binding=binding,
        monkeypatch=monkeypatch,
    )
    precommit, _ = live._read_pilot_precommit(v3_path)
    for target, match in (
        (archive_path, "artifacts.tar"),
        (receipt_path, "outer receipt"),
    ):
        original = target.read_bytes()
        target.write_bytes(original + b"tamper")
        with pytest.raises(ContinualLiveError, match=match):
            live._validate_failed_primary_artifacts(
                archive_path,
                receipt_path,
                precommit=precommit,
            )
        target.write_bytes(original)


def test_cli_rejects_consumed_v2_primary_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seeds = tuple(bytes([index + 31]) * 32 for index in range(4))
    seed_path = tmp_path / "primary-seeds.json"
    seed_path.write_text(json.dumps([seed.hex() for seed in seeds]), encoding="ascii")
    seed_path.chmod(0o600)
    precommit_path = tmp_path / "consumed-v2.json"
    _write_test_precommit(precommit_path, seeds, monkeypatch)
    with pytest.raises(ContinualLiveError, match="permanently prohibited"):
        main(
            [
                "--endpoint",
                "http://model.invalid",
                "--model",
                "fixture-model",
                "--seed-file",
                str(seed_path),
                "--precommit-file",
                str(precommit_path),
                "--output-dir",
                str(tmp_path / "primary-reuse"),
                "--source-revision",
                "c" * 40,
                "--container-digest",
                "sha256:" + "d" * 64,
                "--service-binding",
                "sha256:" + "e" * 64,
            ]
        )


def test_recovery_precommit_rejects_primary_indices(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = (
        Path(__file__).parent
        / "fixtures"
        / "pilot_recovery_precommit_v3.canonical.json"
    )
    value = json.loads(fixture.read_bytes())
    value["selected_seed_indices"] = [0, 1]
    value.pop("precommit_sha256")
    value["precommit_sha256"] = live.canonical_sha256(value)
    raw = canonical_json_bytes(value)
    path = tmp_path / "primary-as-recovery.json"
    path.write_bytes(raw)
    monkeypatch.setattr(
        live, "FROZEN_RECOVERY_PRECOMMIT_ARTIFACT_SHA256", sha256(raw).hexdigest()
    )
    monkeypatch.setattr(
        live, "FROZEN_RECOVERY_PRECOMMIT_SHA256", value["precommit_sha256"]
    )
    with pytest.raises(ContinualLiveError, match=r"reserve \[2, 3\]"):
        live._read_pilot_precommit(path)


def test_consumed_v3_is_rejected_before_old_failure_inputs(tmp_path: Path) -> None:
    seed_path = tmp_path / "seeds.json"
    seed_path.write_text(json.dumps([("01" * 32)] * 4), encoding="ascii")
    seed_path.chmod(0o600)
    fixture = (
        Path(__file__).parent
        / "fixtures"
        / "pilot_recovery_precommit_v3.canonical.json"
    )
    with pytest.raises(ContinualLiveError, match="permanently prohibited"):
        main(
            [
                "--endpoint",
                "http://127.0.0.1:8000",
                "--model",
                "qwen3.6-35b-a3b",
                "--seed-file",
                str(seed_path),
                "--precommit-file",
                str(fixture),
                "--output-dir",
                str(tmp_path / "missing-binding"),
                "--source-revision",
                "c" * 40,
                "--container-digest",
                "sha256:" + "d" * 64,
                "--service-binding",
                "sha256:" + "e" * 64,
                "--timeout",
                "600",
                "--removal-restore",
            ]
        )


@pytest.mark.parametrize("seed_count", [3, 5])
def test_consumed_v3_is_rejected_before_reading_any_old_seed_count(
    tmp_path: Path, seed_count: int
) -> None:
    seeds = tuple(bytes([index + 1]) * 32 for index in range(seed_count))
    seed_path = tmp_path / f"seeds-{seed_count}.json"
    seed_path.write_text(json.dumps([seed.hex() for seed in seeds]), encoding="ascii")
    seed_path.chmod(0o600)
    precommit_path = (
        Path(__file__).parent
        / "fixtures"
        / "pilot_recovery_precommit_v3.canonical.json"
    )
    argv = [
        "--endpoint",
        "http://model.invalid",
        "--model",
        "fixture-model",
        "--streams",
        "2",
        "--seed-file",
        str(seed_path),
        "--precommit-file",
        str(precommit_path),
        "--failed-run-artifacts-tar",
        str(tmp_path / "not-read.tar"),
        "--failed-run-receipt",
        str(tmp_path / "not-read.json"),
        "--output-dir",
        str(tmp_path / f"output-{seed_count}"),
        "--source-revision",
        "c" * 40,
        "--container-digest",
        "sha256:" + "d" * 64,
        "--service-binding",
        "sha256:" + "e" * 64,
        "--timeout",
        "600",
        "--removal-restore",
    ]
    with pytest.raises(ContinualLiveError, match="permanently prohibited"):
        main(argv)
