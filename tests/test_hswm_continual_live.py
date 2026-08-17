from __future__ import annotations

import base64
from hashlib import sha256
import json
from pathlib import Path
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
    run_removal_restore_probes,
)
from hswm.selfmod.contracts import canonical_json_bytes


class ScriptedRelationalBackend:
    """Stateless fixture whose only input is the recorded chat request."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    @property
    def identity(self) -> Mapping[str, Any]:
        return {
            "adapter": "scripted-relational/v1",
            "enable_thinking": False,
            "model": "deterministic-fixture",
            "seed": 0,
            "temperature": 0.0,
            "top_p": 1.0,
        }

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
        active = payload["active_hswm"]
        existing = {item["memory_id"]: item for item in active["memories"]}
        new_memories: list[dict[str, Any]] = []
        for source_token in payload["public_source_tokens"]:
            content = source_token["content"]
            new_memories.append(
                {
                    "content": {
                        "relation": content["relation"],
                        "source": content["source"],
                        "target": content["target"],
                    },
                    "kind": "atomic_relation",
                    "labels": ["agent-authored"],
                    "memory_id": source_token["suggested_memory_id"],
                    "related_memory_ids": [],
                    "source_token_ids": [source_token["token_id"]],
                }
            )
        all_memories = {**existing, **{item["memory_id"]: item for item in new_memories}}
        for memory in new_memories:
            target = memory["content"]["target"]
            memory["related_memory_ids"] = sorted(
                item["memory_id"]
                for item in all_memories.values()
                if item["content"].get("source") == target
                and item["memory_id"] != memory["memory_id"]
            )
        memory_ids = sorted(all_memories)
        response = {
            "cells": [
                {
                    "capability": "nonce_graph_lookup",
                    "cell_id": "cell:lookup",
                    "executor_agent_id": None,
                    "instruction": "Traverse the absorbed atomic relations.",
                    "memory_ids": memory_ids,
                    "next_cell_ids": [],
                }
            ],
            "delete_memory_ids": [],
            "entry_cell_id": "cell:lookup",
            "rationale": "Absorb each public atomic relation into the HSWM cells.",
            "upsert_memories": new_memories,
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
        messages: Sequence[Mapping[str, str]],
        max_output_tokens: int,
        request_id: str,
        response_observer: Callable[[bytes, bytes], None],
    ) -> ModelCompletion:
        payload = json.loads(messages[-1]["content"])
        self.requests.append(
            {
                "max_output_tokens": max_output_tokens,
                "payload": payload,
                "request_id": request_id,
                "system": messages[0]["content"],
            }
        )
        operation = payload["operation"]
        if operation == "answer":
            text = self._answer(payload)
        elif operation == "author_hswm_state":
            text = self._author(payload)
        elif operation == "update_plain_memory":
            text = self._plain(payload)
        else:
            raise AssertionError(operation)
        raw_request = canonical_json_bytes(
            {
                "chat_template_kwargs": {"enable_thinking": False},
                "max_tokens": max_output_tokens,
                "messages": list(messages),
                "model": "deterministic-fixture",
                "seed": 0,
                "temperature": 0.0,
                "top_p": 1.0,
            }
        )
        input_tokens = max(1, len(raw_request) // 4)
        output_tokens = max(1, len(text.encode()) // 4)
        raw_response = canonical_json_bytes(
            {
                "choices": [{"message": {"content": text}}],
                "model": "deterministic-fixture",
                "usage": {
                    "completion_tokens": output_tokens,
                    "prompt_tokens": input_tokens,
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


def _budget() -> ArmBudget:
    return ArmBudget(
        answer_max_output_tokens=128,
        update_max_output_tokens=8192,
        max_input_bytes=2_000_000,
        max_state_bytes=1_000_000,
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
    assert json.loads(first_entry.request_payload_json)["operation"] == "author_hswm_state"
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
    with pytest.raises(ContinualLiveError, match="raw request parameters"):
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
    assert [event["event"] for event in events] == [
        "intent",
        "raw_response_received",
        "response_received",
        "rejected_response",
    ]
    raw_event = events[1]
    completion = events[2]["completion"]
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
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def read(self, _limit: int) -> bytes:
            return raw_response

    def fake_urlopen(*args: Any, **kwargs: Any) -> FakeResponse:
        return FakeResponse()

    monkeypatch.setattr(live.urlrequest, "urlopen", fake_urlopen)
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
    assert [event["event"] for event in events] == [
        "intent",
        "raw_response_received",
        "failed",
    ]
    assert base64.b64decode(events[1]["raw_response_base64"]) == raw_response
    assert events[1]["raw_response_sha256"] == sha256(raw_response).hexdigest()
    assert events[-1]["outcome"] == "received_invalid"
    assert events[-1]["retry_permitted"] is False
    assert arm.ledger == []


def test_rejects_model_authorship_that_cites_hidden_or_old_sources(tmp_path: Path) -> None:
    class BadBackend(ScriptedRelationalBackend):
        @staticmethod
        def _author(payload: Mapping[str, Any]) -> str:
            value = json.loads(ScriptedRelationalBackend._author(payload))
            value["upsert_memories"][0]["source_token_ids"] = ["hidden-gold-token"]
            return json.dumps(value)

    arm = StructuredHSWMArm(
        backend=BadBackend(),
        budget=_budget(),
        isolation_id="bad-source",
        store_path=tmp_path / "state.sqlite3",
    )
    with pytest.raises(ContinualLiveError, match="provenance"):
        arm.update(
            LearningBatch(
                episode_id="episode-bad",
                after_step=0,
                chosen=None,
                correct=False,
                learning_tokens=(PublicLearningToken("a", "r", "b"),),
            )
        )
    assert arm.state_canonical_bytes() == canonical_json_bytes(GENESIS.canonical())


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


def test_cli_binds_four_exact_seeds_retains_failure_and_forbids_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seeds = tuple(bytes([index + 1]) * 32 for index in range(4))
    commitments = tuple(sha256(seed).hexdigest() for seed in seeds)
    seed_path = tmp_path / "seeds.json"
    seed_path.write_text(json.dumps([seed.hex() for seed in seeds]), encoding="ascii")
    seed_path.chmod(0o600)
    precommit_path = tmp_path / "precommit.json"
    commitments = _write_test_precommit(precommit_path, seeds, monkeypatch)
    output = tmp_path / "output"

    def fail_call(self: Any, **kwargs: Any) -> ModelCompletion:
        raise ContinualLiveError("synthetic partial-call outcome")

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
        "--output-dir",
        str(output),
        "--source-revision",
        "c" * 40,
        "--container-digest",
        "sha256:" + "d" * 64,
        "--service-binding",
        "sha256:" + "e" * 64,
        "--removal-restore",
    ]
    with pytest.raises(ContinualLiveError, match="partial-call"):
        main(argv)

    prereg = json.loads((output / "preregistration.json").read_text())
    assert prereg["ordered_seed_commitments"] == list(commitments)
    assert prereg["selected_seed_indices"] == [0, 1]
    assert (output / "frozen_precommit.canonical.json").read_bytes() == precommit_path.read_bytes()
    reveal = json.loads((output / "seed_reveal.json").read_text())
    assert reveal["used_seeds"] == [
        {"frozen_index": 0, "seed_hex": seeds[0].hex()},
        {"frozen_index": 1, "seed_hex": seeds[1].hex()},
    ]
    assert seeds[2].hex() not in json.dumps(reveal)
    terminal = json.loads((output / "terminal_receipt.json").read_text())
    assert terminal["status"] == "failed"
    journal = output / "state" / "stream-00" / "hswm" / "calls.jsonl"
    events = [json.loads(line) for line in journal.read_text().splitlines()]
    assert [item["event"] for item in events] == ["intent", "failed"]
    assert "state/stream-00/hswm/calls.jsonl" in terminal["artifact_sha256s"]

    with pytest.raises(ContinualLiveError, match="no resume"):
        main(argv)


@pytest.mark.parametrize("seed_count", [3, 5])
def test_pilot_rejects_any_frozen_seed_count_other_than_four(
    tmp_path: Path, seed_count: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    seeds = tuple(bytes([index + 1]) * 32 for index in range(seed_count))
    seed_path = tmp_path / f"seeds-{seed_count}.json"
    seed_path.write_text(json.dumps([seed.hex() for seed in seeds]), encoding="ascii")
    seed_path.chmod(0o600)
    authority_seeds = tuple(bytes([index + 11]) * 32 for index in range(4))
    precommit_path = tmp_path / f"precommit-{seed_count}.json"
    _write_test_precommit(precommit_path, authority_seeds, monkeypatch)
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
        "--output-dir",
        str(tmp_path / f"output-{seed_count}"),
        "--source-revision",
        "c" * 40,
        "--container-digest",
        "sha256:" + "d" * 64,
        "--service-binding",
        "sha256:" + "e" * 64,
        "--removal-restore",
    ]
    with pytest.raises(ContinualLiveError, match="exactly 4"):
        main(argv)
