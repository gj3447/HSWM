from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json

import pytest

from hswm.cells.runtime import InvokeCellEffect, canonical_json_bytes, make_packet
from hswm.cells.openai import SafeBeforeSendError
from hswm.selfmod import (
    AgentBinding,
    AgentIdentity,
    ExecutionBudget,
    ExecutionIntentConflict,
    ExecutorAuthority,
    HarnessMode,
    HarnessNode,
    JsonMultiAgentCellPort,
    JournalStepStatus,
    MultiAgentHSWM,
    MultiAgentRuntimeError,
    ScopedToken,
    SelfModelPolicy,
    SelfModifyingHSWM,
    SQLiteSelfModelStore,
    SQLiteMultiAgentJournal,
    TokenVisibility,
    make_harness,
    make_mutation,
    make_token,
    multiagent_receipt_from_mapping,
)
from hswm.selfmod.contracts import canonical_sha256
from hswm.selfmod.multiagent import (
    MULTIAGENT_JSON_REQUEST_TYPE,
    MULTIAGENT_STEP_REQUEST_TYPE,
    MULTIAGENT_STEP_RESPONSE_TYPE,
)


OBSERVE = "capability:observe"
BRANCH = "capability:branch"
JOIN = "capability:join"
ARCHITECT = "agent:architect"
AGENT_A = "agent:a"
AGENT_B = "agent:b"


def _policy() -> SelfModelPolicy:
    return SelfModelPolicy(
        allowed_capabilities=frozenset({OBSERVE, BRANCH, JOIN})
    )


def _harness():
    return make_harness(
        purpose="Fan out private observations and join agent-authored work.",
        entry_node_id="node:root",
        nodes=(
            HarnessNode(
                node_id="node:root",
                executor_agent_id=AGENT_A,
                capability=OBSERVE,
                instruction="Read A's observation and open two declared branches.",
                next_node_ids=("node:left", "node:right"),
            ),
            HarnessNode(
                node_id="node:left",
                executor_agent_id=AGENT_A,
                capability=BRANCH,
                instruction="Develop the left branch.",
                next_node_ids=("node:join",),
            ),
            HarnessNode(
                node_id="node:right",
                executor_agent_id=AGENT_B,
                capability=BRANCH,
                instruction="Combine B's private observation with the handoff.",
                next_node_ids=("node:join",),
            ),
            HarnessNode(
                node_id="node:join",
                executor_agent_id=AGENT_B,
                capability=JOIN,
                instruction="Join the two predecessor messages.",
            ),
        ),
    )


class HarnessAuthor:
    agent_id = ARCHITECT

    def __init__(self, harness) -> None:
        self.harness = harness

    def decide(self, request):
        raise AssertionError("absorb must not ask the author to execute")

    def author(self, request):
        return make_mutation(
            base_snapshot_id=request.active.snapshot.snapshot_id,
            expected_generation=request.active.generation,
            author_id=self.agent_id,
            source_token_ids=tuple(token.token_id for token in request.tokens),
            harness_mode=HarnessMode.REPLACE,
            harness=self.harness,
            rationale="Author the executable multi-agent topology from this token.",
        )


class ScriptedPort:
    """Deterministic port that exposes exactly what the runtime delivered."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.calls = []

    def invoke(self, effect):
        payload = effect.input.payload
        assert payload["agent"]["agent_id"] == self.agent_id
        assert all(
            message["recipient_agent_id"] == self.agent_id
            for message in payload["inbound_messages"]
        )
        observed = {
            "agent_id": self.agent_id,
            "node_id": payload["node"]["node_id"],
            "visible_token_ids": [
                token["token_id"] for token in payload["visible_tokens"]
            ],
            "inbound": [
                {
                    "source_node_id": message["source_node_id"],
                    "sender_agent_id": message["sender_agent_id"],
                    "recipient_agent_id": message["recipient_agent_id"],
                }
                for message in payload["inbound_messages"]
            ],
        }
        self.calls.append(deepcopy(payload))
        return make_packet(
            packet_id=f"response:{effect.activation_id}",
            packet_type=effect.expected_output_type,
            payload={"output": observed},
            provenance={"agent_id": self.agent_id, "node_id": observed["node_id"]},
        )


class OpenAIShapedPort:
    """The exact packet shape returned by OpenAICompatibleCellPort."""

    def __init__(
        self,
        response_text: str,
        *,
        model: str = "fixture-open-weight-model",
        usage=None,
        wrong_packet_type: bool = False,
        bad_payload_digest: bool = False,
    ) -> None:
        self.response_text = response_text
        self.model = model
        self.usage = (
            {"prompt_tokens": 20, "completion_tokens": 5}
            if usage is None
            else usage
        )
        self.wrong_packet_type = wrong_packet_type
        self.bad_payload_digest = bad_payload_digest
        self.calls = []

    def invoke(self, effect):
        self.calls.append(effect)
        packet = make_packet(
            packet_id=f"openai-shape:{effect.activation_id}",
            packet_type=(
                "hswm-multiagent-wrong-response/v1"
                if self.wrong_packet_type
                else effect.expected_output_type
            ),
            payload={
                "text": self.response_text,
                "model": self.model,
                "usage": self.usage,
                "response_sha256": "a" * 64,
            },
            provenance={
                "adapter": "openai-compatible/v1",
                "activation_id": effect.activation_id,
            },
        )
        if self.bad_payload_digest:
            packet = replace(packet, payload_sha256="0" * 64)
        return packet


class FailingAfterDispatchPort:
    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, effect):
        self.calls += 1
        raise RuntimeError("simulated failure after external dispatch")


class SafeOncePort(ScriptedPort):
    def __init__(self, agent_id: str) -> None:
        super().__init__(agent_id)
        self.attempts = 0

    def invoke(self, effect):
        self.attempts += 1
        if self.attempts == 1:
            raise SafeBeforeSendError("fixture proves no bytes were sent")
        return super().invoke(effect)


class MutateThenFailPort:
    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, effect):
        self.calls += 1
        effect.input.payload["visible_tokens"][0]["content"]["question"] = "poison"
        raise RuntimeError("mutated adapter request")


class RedigestMutatingPort:
    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, effect):
        self.calls += 1
        effect.input.payload["visible_tokens"][0]["content"] = {"poison": True}
        object.__setattr__(
            effect.input,
            "payload_sha256",
            canonical_sha256(effect.input.payload),
        )
        object.__setattr__(effect.input, "packet_id", "request:poisoned")
        return make_packet(
            packet_id="response:redigest-mutator",
            packet_type=effect.expected_output_type,
            payload={"output": {"accepted": True}},
            provenance={"source": "redigest-mutator"},
        )


class RedigestOpenAIPort(OpenAIShapedPort):
    def invoke(self, effect):
        effect.input.payload["messages"][1]["content"] = '{"poison":true}'
        object.__setattr__(
            effect.input,
            "payload_sha256",
            canonical_sha256(effect.input.payload),
        )
        object.__setattr__(effect.input, "packet_id", "request:bridge-poisoned")
        return super().invoke(effect)


class MalformedProvenancePort(ScriptedPort):
    def invoke(self, effect):
        packet = super().invoke(effect)
        return replace(packet, provenance_sha256="not-a-sha")


class DuplicatePacketIdPort(ScriptedPort):
    def invoke(self, effect):
        packet = super().invoke(effect)
        return replace(packet, packet_id="response:duplicate")


class LargeOutputPort:
    def __init__(self, size: int) -> None:
        self.size = size
        self.calls = 0

    def invoke(self, effect):
        self.calls += 1
        return make_packet(
            packet_id=f"large-response:{effect.activation_id}",
            packet_type=effect.expected_output_type,
            payload={
                "output": {
                    "node_id": effect.input.payload["node"]["node_id"],
                    "value": "x" * self.size,
                }
            },
            provenance={"source": "large-output-fixture"},
        )


class CrashAfterClaimJournal(SQLiteMultiAgentJournal):
    def __init__(self, path) -> None:
        super().__init__(path)
        self.crashed = False

    def claim_step(self, **kwargs):
        record = super().claim_step(**kwargs)
        if not self.crashed:
            self.crashed = True
            raise RuntimeError("simulated process loss after durable claim")
        return record


def _json_bridge_effect(payload=None):
    value = (
        {
            "episode_id": "episode:json-bridge",
            "node": {"node_id": "node:json"},
            "visible_tokens": [],
            "inbound_messages": [],
        }
        if payload is None
        else payload
    )
    return InvokeCellEffect(
        activation_id="activation:json-bridge",
        cell_id=AGENT_A,
        input=make_packet(
            packet_id="request:json-bridge",
            packet_type=MULTIAGENT_STEP_REQUEST_TYPE,
            payload=value,
            provenance={"source": "json-bridge-test"},
        ),
        expected_output_type=MULTIAGENT_STEP_RESPONSE_TYPE,
    )


def _rehash_step(step):
    unsigned = {key: value for key, value in step.items() if key != "receipt_id"}
    step["receipt_id"] = canonical_sha256(unsigned)


def _rehash_message(message):
    message["payload_sha256"] = canonical_sha256(message["payload"])
    unsigned = {key: value for key, value in message.items() if key != "message_id"}
    message["message_id"] = canonical_sha256(unsigned)


def _rehash_episode(receipt):
    unsigned = {key: value for key, value in receipt.items() if key != "receipt_id"}
    receipt["receipt_id"] = canonical_sha256(unsigned)


def _author_harness(store: SQLiteSelfModelStore, harness=None) -> None:
    harness = _harness() if harness is None else harness
    token = make_token(
        token_id="token:authored-harness",
        episode_id="episode:author-harness",
        position=0,
        role="observation",
        content={"instruction": "create a multi-agent execution harness"},
        provenance={"source": "scripted-author-fixture"},
    )
    activation = SelfModifyingHSWM(store).absorb(
        (token,),
        agent=HarnessAuthor(harness),
        agent_registry=(
            ExecutorAuthority(AGENT_A, (OBSERVE, BRANCH)),
            ExecutorAuthority(AGENT_B, (BRANCH, JOIN)),
        ),
    )
    assert activation is not None
    assert store.active_snapshot().snapshot.harness == harness


def _episode_inputs(episode_id: str):
    public = make_token(
        token_id=f"token:{episode_id}:public",
        episode_id=episode_id,
        position=0,
        role="user",
        content={"question": "combine the distributed evidence"},
        provenance={"scope": "public"},
    )
    private_a = make_token(
        token_id=f"token:{episode_id}:private-a",
        episode_id=episode_id,
        position=1,
        role="observation",
        content={"secret": "A"},
        provenance={"scope": "private", "owner": AGENT_A},
    )
    private_b = make_token(
        token_id=f"token:{episode_id}:private-b",
        episode_id=episode_id,
        position=2,
        role="observation",
        content={"secret": "B"},
        provenance={"scope": "private", "owner": AGENT_B},
    )
    return (
        ScopedToken(public),
        ScopedToken(
            private_a,
            visibility=TokenVisibility.DIRECT_ONLY,
            owner_agent_id=AGENT_A,
        ),
        ScopedToken(
            private_b,
            visibility=TokenVisibility.DIRECT_ONLY,
            owner_agent_id=AGENT_B,
        ),
    )


def _runtime(
    store,
    port_a,
    port_b,
    *,
    caps_a=None,
    caps_b=None,
    revision_a="a" * 64,
    revision_b="b" * 64,
    journal=None,
):
    return MultiAgentHSWM(
        store,
        agents=(
            AgentBinding(
                AgentIdentity(
                    AGENT_A,
                    frozenset({OBSERVE, BRANCH} if caps_a is None else caps_a),
                ),
                port_a,
                deployment_id="fixture-deployment:a",
                model_revision_sha256=revision_a,
            ),
            AgentBinding(
                AgentIdentity(
                    AGENT_B,
                    frozenset({BRANCH, JOIN} if caps_b is None else caps_b),
                ),
                port_b,
                deployment_id="fixture-deployment:b",
                model_revision_sha256=revision_b,
            ),
        ),
        journal=journal,
    )


def test_agent_authored_dag_invokes_two_ports_with_fan_out_fan_in_and_scopes(
    tmp_path,
) -> None:
    with SQLiteSelfModelStore(tmp_path / "multiagent.sqlite3", policy=_policy()) as store:
        _author_harness(store)
        active = store.active_snapshot()
        port_a = ScriptedPort(AGENT_A)
        port_b = ScriptedPort(AGENT_B)
        episode_id = "episode:distributed"
        inputs = _episode_inputs(episode_id)

        receipt = _runtime(store, port_a, port_b).run_episode(
            episode_id=episode_id,
            inputs=inputs,
            budget=ExecutionBudget(step_budget=4),
        )

        assert receipt.used_snapshot_id == active.snapshot.snapshot_id
        assert receipt.used_generation == active.generation
        assert receipt.harness_id == active.snapshot.harness.harness_id
        assert receipt.route_node_ids == (
            "node:root",
            "node:left",
            "node:right",
            "node:join",
        )
        assert receipt.leaf_node_ids == ("node:join",)
        assert receipt.executed_agent_ids == (AGENT_A, AGENT_B)
        assert receipt.budget.step_budget == receipt.usage.steps == 4
        assert len(port_a.calls) == len(port_b.calls) == 2

        public_id, private_a_id, private_b_id = receipt.input_token_ids
        for call in port_a.calls:
            visible_ids = {
                token["token_id"] for token in call["visible_tokens"]
            }
            assert visible_ids == {public_id, private_a_id}
            assert private_b_id not in visible_ids
        for call in port_b.calls:
            visible_ids = {
                token["token_id"] for token in call["visible_tokens"]
            }
            assert visible_ids == {public_id, private_b_id}
            assert private_a_id not in visible_ids

        assert len(receipt.messages) == 4
        message_edges = {
            (
                message.source_node_id,
                message.target_node_id,
                message.sender_agent_id,
                message.recipient_agent_id,
            )
            for message in receipt.messages
        }
        assert message_edges == {
            ("node:root", "node:left", AGENT_A, AGENT_A),
            ("node:root", "node:right", AGENT_A, AGENT_B),
            ("node:left", "node:join", AGENT_A, AGENT_B),
            ("node:right", "node:join", AGENT_B, AGENT_B),
        }
        # DIRECT_ONLY is a raw-input audience, not a secrecy label.  A's port
        # may deliberately communicate derived content to B over a typed edge.
        a_to_b = next(
            message
            for message in receipt.messages
            if message.source_node_id == "node:left"
        )
        assert private_a_id in a_to_b.payload["visible_token_ids"]
        join_call = next(
            call for call in port_b.calls if call["node"]["node_id"] == "node:join"
        )
        assert [
            message["source_node_id"]
            for message in join_call["inbound_messages"]
        ] == ["node:left", "node:right"]
        assert store.active_snapshot() == active


def test_json_cell_port_runs_openai_shaped_ports_through_the_full_harness(
    tmp_path,
) -> None:
    with SQLiteSelfModelStore(
        tmp_path / "multiagent-json.sqlite3", policy=_policy()
    ) as store:
        _author_harness(store)
        raw_a = OpenAIShapedPort(
            '{"output":{"agent":"a","status":"ok"}}'
        )
        raw_b = OpenAIShapedPort(
            '{"output":{"agent":"b","status":"ok"}}'
        )
        port_a = JsonMultiAgentCellPort(raw_a)
        port_b = JsonMultiAgentCellPort(raw_b)
        episode_id = "episode:openai-shaped"

        receipt = _runtime(store, port_a, port_b).run_episode(
            episode_id=episode_id,
            inputs=_episode_inputs(episode_id),
            budget=ExecutionBudget(step_budget=4),
        )

        assert receipt.executed_agent_ids == (AGENT_A, AGENT_B)
        assert receipt.usage.steps == 4
        assert port_a.calls == port_b.calls == 2
        assert len(raw_a.calls) == len(raw_b.calls) == 2
        for call in (*raw_a.calls, *raw_b.calls):
            assert call.input.packet_type == MULTIAGENT_JSON_REQUEST_TYPE
            messages = call.input.payload["messages"]
            assert [message["role"] for message in messages] == ["system", "user"]
            assert "Do not use markdown" in messages[0]["content"]
            request_value = json.loads(messages[1]["content"])
            assert (
                messages[1]["content"].encode("utf-8")
                == canonical_json_bytes(request_value)
            )
            assert request_value["episode_id"] == episode_id
        assert receipt.output_token.content["leaf_outputs"] == [
            {
                "node_id": "node:join",
                "agent_id": AGENT_B,
                "output": {"agent": "b", "status": "ok"},
            }
        ]


def test_json_cell_port_binds_model_usage_and_transport_digests_to_provenance(
) -> None:
    effect = _json_bridge_effect()
    first = JsonMultiAgentCellPort(
        OpenAIShapedPort(
            '{"output":{"answer":4}}',
            model="model:a",
            usage={"prompt_tokens": 3, "completion_tokens": 1},
        )
    ).invoke(effect)
    second = JsonMultiAgentCellPort(
        OpenAIShapedPort(
            '{"output":{"answer":4}}',
            model="model:b",
            usage={"prompt_tokens": 4, "completion_tokens": 1},
        )
    ).invoke(effect)

    assert first.packet_type == effect.expected_output_type
    assert first.payload == second.payload == {"output": {"answer": 4}}
    assert first.provenance_sha256 != second.provenance_sha256
    assert first.packet_id != second.packet_id


@pytest.mark.parametrize(
    "response_text",
    (
        '```json\n{"output":4}\n```',
        '{"output":4,"explanation":"extra"}',
    ),
    ids=("markdown", "extra-field"),
)
def test_json_cell_port_rejects_non_exact_model_output(response_text) -> None:
    adapter = JsonMultiAgentCellPort(OpenAIShapedPort(response_text))
    with pytest.raises(MultiAgentRuntimeError, match="invalid JSON|only output"):
        adapter.invoke(_json_bridge_effect())


@pytest.mark.parametrize(
    "port,match",
    (
        (
            OpenAIShapedPort('{"output":4}', wrong_packet_type=True),
            "wrong packet type",
        ),
        (
            OpenAIShapedPort('{"output":4}', bad_payload_digest=True),
            "payload digest mismatch",
        ),
    ),
    ids=("wrong-packet", "bad-digest"),
)
def test_json_cell_port_rejects_invalid_underlying_packet(port, match) -> None:
    with pytest.raises(MultiAgentRuntimeError, match=match):
        JsonMultiAgentCellPort(port).invoke(_json_bridge_effect())


def test_json_cell_port_rejects_oversize_model_response() -> None:
    port = OpenAIShapedPort(
        json.dumps({"output": "x" * 500}, separators=(",", ":"))
    )
    with pytest.raises(MultiAgentRuntimeError, match="byte budget"):
        JsonMultiAgentCellPort(port, max_response_bytes=256).invoke(
            _json_bridge_effect()
        )


def test_json_cell_port_rejects_payload_redigest_request_mutation() -> None:
    port = RedigestOpenAIPort('{"output":{"accepted":true}}')
    with pytest.raises(MultiAgentRuntimeError, match="mutated its frozen request"):
        JsonMultiAgentCellPort(port).invoke(_json_bridge_effect())


def test_aggregate_budget_rejects_the_whole_route_before_any_port_call(
    tmp_path,
) -> None:
    with SQLiteSelfModelStore(tmp_path / "budget.sqlite3", policy=_policy()) as store:
        _author_harness(store)
        before_tokens = store.token_count()
        port_a = ScriptedPort(AGENT_A)
        port_b = ScriptedPort(AGENT_B)
        with pytest.raises(MultiAgentRuntimeError, match="aggregate step budget"):
            _runtime(store, port_a, port_b).run_episode(
                episode_id="episode:too-small",
                inputs=_episode_inputs("episode:too-small"),
                budget=ExecutionBudget(step_budget=3),
            )
        assert port_a.calls == port_b.calls == []
        assert store.token_count() == before_tokens


def test_unauthorized_executor_node_fails_closed_before_dispatch(tmp_path) -> None:
    with SQLiteSelfModelStore(
        tmp_path / "unauthorized.sqlite3", policy=_policy()
    ) as store:
        _author_harness(store)
        port_a = ScriptedPort(AGENT_A)
        port_b = ScriptedPort(AGENT_B)
        with pytest.raises(MultiAgentRuntimeError, match="unauthorized"):
            _runtime(
                store,
                port_a,
                port_b,
                caps_a=frozenset({OBSERVE}),
            ).run_episode(
                episode_id="episode:unauthorized",
                inputs=_episode_inputs("episode:unauthorized"),
                budget=ExecutionBudget(step_budget=4),
            )
        assert port_a.calls == port_b.calls == []


def test_exact_execution_and_content_addressed_receipt_are_replay_deterministic(
    tmp_path,
) -> None:
    with SQLiteSelfModelStore(tmp_path / "replay.sqlite3", policy=_policy()) as store:
        genesis = store.active_snapshot()
        _author_harness(store)
        port_a = ScriptedPort(AGENT_A)
        port_b = ScriptedPort(AGENT_B)
        runtime = _runtime(store, port_a, port_b)
        episode_id = "episode:replay"
        inputs = _episode_inputs(episode_id)

        first = runtime.run_episode(
            episode_id=episode_id,
            inputs=inputs,
            budget=ExecutionBudget(step_budget=4),
        )
        calls_after_first = (len(port_a.calls), len(port_b.calls))
        store.activate_snapshot(
            genesis.snapshot.snapshot_id,
            expected_generation=1,
            author_id="evaluator:evolve-after-execution",
            source_token_ids=("token:authored-harness",),
            reason="exercise-pinned-execution-replay",
        )
        replayed = runtime.run_episode(
            episode_id=episode_id,
            inputs=inputs,
            budget=ExecutionBudget(step_budget=4),
        )

        assert replayed == first
        assert (len(port_a.calls), len(port_b.calls)) == calls_after_first
        assert replayed.receipt_id == first.receipt_id
        assert multiagent_receipt_from_mapping(first.canonical()) == first

        tampered = deepcopy(first.canonical())
        tampered["messages"][0]["sender_agent_id"] = AGENT_B
        with pytest.raises(MultiAgentRuntimeError, match="message.*digest"):
            multiagent_receipt_from_mapping(tampered)


def test_mid_run_unknown_outcome_is_durable_and_never_blindly_retried(
    tmp_path,
) -> None:
    with SQLiteSelfModelStore(tmp_path / "unknown.sqlite3", policy=_policy()) as store:
        _author_harness(store)
        port_a = ScriptedPort(AGENT_A)
        port_b = FailingAfterDispatchPort()
        runtime = _runtime(store, port_a, port_b)
        episode_id = "episode:unknown-outcome"
        inputs = _episode_inputs(episode_id)

        with pytest.raises(MultiAgentRuntimeError, match="reconciliation"):
            runtime.run_episode(
                episode_id=episode_id,
                inputs=inputs,
                budget=ExecutionBudget(step_budget=4),
            )
        assert len(port_a.calls) == 2
        assert port_b.calls == 1
        assert runtime.journal.step_record(
            episode_id=episode_id, sequence=1
        ).status is JournalStepStatus.SUCCEEDED
        assert runtime.journal.step_record(
            episode_id=episode_id, sequence=3
        ).status is JournalStepStatus.UNKNOWN_OUTCOME

        with pytest.raises(MultiAgentRuntimeError, match="reconciliation"):
            runtime.run_episode(
                episode_id=episode_id,
                inputs=inputs,
                budget=ExecutionBudget(step_budget=4),
            )
        assert len(port_a.calls) == 2
        assert port_b.calls == 1


def test_safe_before_send_resumes_without_repeating_completed_steps(tmp_path) -> None:
    with SQLiteSelfModelStore(tmp_path / "safe-retry.sqlite3", policy=_policy()) as store:
        _author_harness(store)
        port_a = ScriptedPort(AGENT_A)
        port_b = SafeOncePort(AGENT_B)
        runtime = _runtime(store, port_a, port_b)
        episode_id = "episode:safe-retry"
        inputs = _episode_inputs(episode_id)

        with pytest.raises(MultiAgentRuntimeError):
            runtime.run_episode(
                episode_id=episode_id,
                inputs=inputs,
                budget=ExecutionBudget(step_budget=4),
            )
        assert len(port_a.calls) == 2
        assert port_b.attempts == 1
        receipt = runtime.run_episode(
            episode_id=episode_id,
            inputs=inputs,
            budget=ExecutionBudget(step_budget=4),
        )
        assert receipt.usage.steps == 4
        assert len(port_a.calls) == 2
        assert port_b.attempts == 3  # right retry plus the later join step


def test_inflight_crash_state_blocks_redispatch_until_reconciliation(tmp_path) -> None:
    journal_path = tmp_path / "crash-journal.sqlite3"
    crashing = CrashAfterClaimJournal(journal_path)
    with SQLiteSelfModelStore(tmp_path / "crash.sqlite3", policy=_policy()) as store:
        _author_harness(store)
        port_a = ScriptedPort(AGENT_A)
        port_b = ScriptedPort(AGENT_B)
        episode_id = "episode:crash-after-claim"
        inputs = _episode_inputs(episode_id)
        with pytest.raises(RuntimeError, match="process loss"):
            _runtime(store, port_a, port_b, journal=crashing).run_episode(
                episode_id=episode_id,
                inputs=inputs,
                budget=ExecutionBudget(step_budget=4),
            )
        assert port_a.calls == port_b.calls == []

        recovered = _runtime(
            store,
            port_a,
            port_b,
            journal=SQLiteMultiAgentJournal(journal_path),
        )
        with pytest.raises(MultiAgentRuntimeError, match="IN_FLIGHT"):
            recovered.run_episode(
                episode_id=episode_id,
                inputs=inputs,
                budget=ExecutionBudget(step_budget=4),
            )
        assert port_a.calls == port_b.calls == []


@pytest.mark.parametrize(
    "budget,expected_calls",
    (
        (ExecutionBudget(step_budget=4, context_byte_budget=1), 0),
        (ExecutionBudget(step_budget=4, response_byte_budget=1), 1),
        (ExecutionBudget(step_budget=4, message_byte_budget=1), 1),
    ),
    ids=("context", "response", "message"),
)
def test_aggregate_byte_budgets_fail_permanently_without_redispatch(
    tmp_path, budget, expected_calls
) -> None:
    with SQLiteSelfModelStore(
        tmp_path / f"bytes-{expected_calls}-{budget.context_byte_budget}.sqlite3",
        policy=_policy(),
    ) as store:
        _author_harness(store)
        port_a = ScriptedPort(AGENT_A)
        port_b = ScriptedPort(AGENT_B)
        runtime = _runtime(store, port_a, port_b)
        episode_id = f"episode:bytes:{budget.context_byte_budget}:{budget.response_byte_budget}:{budget.message_byte_budget}"
        inputs = _episode_inputs(episode_id)
        with pytest.raises(MultiAgentRuntimeError, match="aggregate .* byte budget"):
            runtime.run_episode(
                episode_id=episode_id,
                inputs=inputs,
                budget=budget,
            )
        assert len(port_a.calls) + len(port_b.calls) == expected_calls
        with pytest.raises(MultiAgentRuntimeError, match="FAILED_PERMANENT"):
            runtime.run_episode(
                episode_id=episode_id,
                inputs=inputs,
                budget=budget,
            )
        assert len(port_a.calls) + len(port_b.calls) == expected_calls


def test_aggregate_leaf_token_store_limit_fails_permanently_without_redispatch(
    tmp_path,
) -> None:
    two_leaves = make_harness(
        purpose="Produce two individually bounded leaf outputs.",
        entry_node_id="node:root",
        nodes=(
            HarnessNode(
                node_id="node:root",
                executor_agent_id=AGENT_A,
                capability=OBSERVE,
                instruction="Fan out.",
                next_node_ids=("node:left", "node:right"),
            ),
            HarnessNode(
                node_id="node:left",
                executor_agent_id=AGENT_A,
                capability=BRANCH,
                instruction="Return the left leaf.",
            ),
            HarnessNode(
                node_id="node:right",
                executor_agent_id=AGENT_B,
                capability=BRANCH,
                instruction="Return the right leaf.",
            ),
        ),
    )
    policy = replace(_policy(), max_token_bytes=5_000)
    with SQLiteSelfModelStore(
        tmp_path / "aggregate-token-limit.sqlite3", policy=policy
    ) as store:
        _author_harness(store, two_leaves)
        port_a = LargeOutputPort(2_800)
        port_b = LargeOutputPort(2_800)
        runtime = _runtime(store, port_a, port_b)
        episode_id = "episode:aggregate-token-limit"
        inputs = _episode_inputs(episode_id)

        with pytest.raises(MultiAgentRuntimeError, match="aggregate output token"):
            runtime.run_episode(
                episode_id=episode_id,
                inputs=inputs,
                budget=ExecutionBudget(step_budget=3),
            )
        calls = port_a.calls + port_b.calls
        assert calls == 3

        with pytest.raises(MultiAgentRuntimeError, match="FAILED_PERMANENT"):
            runtime.run_episode(
                episode_id=episode_id,
                inputs=inputs,
                budget=ExecutionBudget(step_budget=3),
            )
        assert port_a.calls + port_b.calls == calls


def test_input_persistence_failure_is_permanent_before_any_dispatch(tmp_path) -> None:
    policy = replace(_policy(), max_token_bytes=1_200)
    with SQLiteSelfModelStore(
        tmp_path / "input-token-limit.sqlite3", policy=policy
    ) as store:
        _author_harness(store)
        port_a = ScriptedPort(AGENT_A)
        port_b = ScriptedPort(AGENT_B)
        runtime = _runtime(store, port_a, port_b)
        episode_id = "episode:input-token-limit"
        oversized = ScopedToken(
            make_token(
                token_id="token:input-token-limit",
                episode_id=episode_id,
                position=0,
                role="user",
                content={"value": "x" * 2_000},
                provenance={"source": "oversize-input-fixture"},
            )
        )

        with pytest.raises(MultiAgentRuntimeError, match="input token persistence"):
            runtime.run_episode(
                episode_id=episode_id,
                inputs=(oversized,),
                budget=ExecutionBudget(step_budget=4),
            )
        assert port_a.calls == port_b.calls == []

        with pytest.raises(MultiAgentRuntimeError, match="FAILED_PERMANENT"):
            runtime.run_episode(
                episode_id=episode_id,
                inputs=(oversized,),
                budget=ExecutionBudget(step_budget=4),
            )
        assert port_a.calls == port_b.calls == []


def test_port_cannot_mutate_caller_token_even_when_it_raises(tmp_path) -> None:
    with SQLiteSelfModelStore(tmp_path / "mutation.sqlite3", policy=_policy()) as store:
        _author_harness(store)
        episode_id = "episode:mutation"
        inputs = _episode_inputs(episode_id)
        before = tuple(scoped.token.canonical() for scoped in inputs)
        runtime = _runtime(store, MutateThenFailPort(), ScriptedPort(AGENT_B))
        with pytest.raises(MultiAgentRuntimeError, match="mutated"):
            runtime.run_episode(
                episode_id=episode_id,
                inputs=inputs,
                budget=ExecutionBudget(step_budget=4),
            )
        assert tuple(scoped.token.canonical() for scoped in inputs) == before
        assert store.load_token(inputs[0].token.token_id).canonical() == before[0]


def test_port_cannot_redigest_a_mutated_detached_request(tmp_path) -> None:
    with SQLiteSelfModelStore(
        tmp_path / "redigest-mutation.sqlite3", policy=_policy()
    ) as store:
        _author_harness(store)
        episode_id = "episode:redigest-mutation"
        inputs = _episode_inputs(episode_id)
        before = tuple(scoped.token.canonical() for scoped in inputs)
        mutator = RedigestMutatingPort()
        runtime = _runtime(store, mutator, ScriptedPort(AGENT_B))

        with pytest.raises(MultiAgentRuntimeError, match="mutated its frozen request"):
            runtime.run_episode(
                episode_id=episode_id,
                inputs=inputs,
                budget=ExecutionBudget(step_budget=4),
            )

        assert mutator.calls == 1
        assert tuple(scoped.token.canonical() for scoped in inputs) == before
        assert store.load_token(inputs[0].token.token_id).canonical() == before[0]
        assert (
            runtime.journal.execution_record(episode_id=episode_id).status.value
            == "UNKNOWN_OUTCOME"
        )


def test_malformed_output_provenance_fails_closed(tmp_path) -> None:
    with SQLiteSelfModelStore(
        tmp_path / "malformed-provenance.sqlite3", policy=_policy()
    ) as store:
        _author_harness(store)
        runtime = _runtime(
            store,
            MalformedProvenancePort(AGENT_A),
            ScriptedPort(AGENT_B),
        )
        episode_id = "episode:malformed-provenance"
        with pytest.raises(MultiAgentRuntimeError, match="canonical sha256"):
            runtime.run_episode(
                episode_id=episode_id,
                inputs=_episode_inputs(episode_id),
                budget=ExecutionBudget(step_budget=4),
            )


def test_duplicate_output_packet_id_fails_permanently_without_redispatch(
    tmp_path,
) -> None:
    with SQLiteSelfModelStore(
        tmp_path / "duplicate-output-id.sqlite3", policy=_policy()
    ) as store:
        _author_harness(store)
        port_a = DuplicatePacketIdPort(AGENT_A)
        port_b = DuplicatePacketIdPort(AGENT_B)
        runtime = _runtime(store, port_a, port_b)
        episode_id = "episode:duplicate-output-id"
        inputs = _episode_inputs(episode_id)

        with pytest.raises(MultiAgentRuntimeError, match="reused an output packet"):
            runtime.run_episode(
                episode_id=episode_id,
                inputs=inputs,
                budget=ExecutionBudget(step_budget=4),
            )
        assert len(port_a.calls) == 2
        assert port_b.calls == []

        with pytest.raises(MultiAgentRuntimeError, match="FAILED_PERMANENT"):
            runtime.run_episode(
                episode_id=episode_id,
                inputs=inputs,
                budget=ExecutionBudget(step_budget=4),
            )
        assert len(port_a.calls) == 2
        assert port_b.calls == []


def test_deployment_revision_is_part_of_execution_identity(tmp_path) -> None:
    with SQLiteSelfModelStore(tmp_path / "deployment.sqlite3", policy=_policy()) as store:
        _author_harness(store)
        episode_id = "episode:deployment"
        inputs = _episode_inputs(episode_id)
        first_a = ScriptedPort(AGENT_A)
        first_b = ScriptedPort(AGENT_B)
        _runtime(store, first_a, first_b).run_episode(
            episode_id=episode_id,
            inputs=inputs,
            budget=ExecutionBudget(step_budget=4),
        )
        replacement_a = ScriptedPort(AGENT_A)
        replacement_b = ScriptedPort(AGENT_B)
        with pytest.raises(ExecutionIntentConflict):
            _runtime(
                store,
                replacement_a,
                replacement_b,
                revision_a="c" * 64,
            ).run_episode(
                episode_id=episode_id,
                inputs=inputs,
                budget=ExecutionBudget(step_budget=4),
            )
        assert replacement_a.calls == replacement_b.calls == []


def test_receipt_parser_rejects_backward_edges_scope_leaks_and_fake_output(
    tmp_path,
) -> None:
    with SQLiteSelfModelStore(tmp_path / "receipt-teeth.sqlite3", policy=_policy()) as store:
        _author_harness(store)
        episode_id = "episode:receipt-teeth"
        receipt = _runtime(
            store, ScriptedPort(AGENT_A), ScriptedPort(AGENT_B)
        ).run_episode(
            episode_id=episode_id,
            inputs=_episode_inputs(episode_id),
            budget=ExecutionBudget(step_budget=4),
        )

    backward = deepcopy(receipt.canonical())
    steps = {step["node_id"]: step for step in backward["step_receipts"]}
    message = next(
        item
        for item in backward["messages"]
        if item["source_node_id"] == "node:root"
        and item["target_node_id"] == "node:left"
    )
    old_id = message["message_id"]
    message["source_node_id"] = "node:right"
    message["sender_agent_id"] = AGENT_B
    message["payload"] = deepcopy(steps["node:right"]["output"])
    _rehash_message(message)
    new_id = message["message_id"]
    steps["node:root"]["outbound_message_ids"].remove(old_id)
    steps["node:right"]["outbound_message_ids"].append(new_id)
    steps["node:left"]["inbound_message_ids"] = [new_id]
    message_by_id = {item["message_id"]: item for item in backward["messages"]}
    for step in steps.values():
        step["message_bytes"] = sum(
            len(canonical_json_bytes(message_by_id[message_id]))
            for message_id in step["outbound_message_ids"]
        )
        _rehash_step(step)
    backward["usage"]["message_bytes"] = sum(
        step["message_bytes"] for step in steps.values()
    )
    _rehash_episode(backward)
    with pytest.raises(MultiAgentRuntimeError, match="forward"):
        multiagent_receipt_from_mapping(backward)

    scope_leak = deepcopy(receipt.canonical())
    root = scope_leak["step_receipts"][0]
    root["visible_token_ids"].append(scope_leak["input_token_ids"][2])
    _rehash_step(root)
    _rehash_episode(scope_leak)
    with pytest.raises(MultiAgentRuntimeError, match="visibility"):
        multiagent_receipt_from_mapping(scope_leak)

    fake_output = deepcopy(receipt.canonical())
    fake_output["output_token"]["content"]["leaf_outputs"][0]["output"] = {
        "fabricated": True
    }
    fake_output["output_token"]["content_sha256"] = canonical_sha256(
        fake_output["output_token"]["content"]
    )
    _rehash_episode(fake_output)
    with pytest.raises(MultiAgentRuntimeError, match="linked to leaf"):
        multiagent_receipt_from_mapping(fake_output)

    usage_tamper = deepcopy(receipt.canonical())
    usage_tamper["usage"].update(
        {"context_bytes": 0, "response_bytes": 0, "message_bytes": 0}
    )
    _rehash_episode(usage_tamper)
    with pytest.raises(MultiAgentRuntimeError, match="budget accounting"):
        multiagent_receipt_from_mapping(usage_tamper)

    per_step_message_tamper = deepcopy(receipt.canonical())
    first = per_step_message_tamper["step_receipts"][0]
    removed = first["message_bytes"]
    first["message_bytes"] = 0
    per_step_message_tamper["usage"]["message_bytes"] -= removed
    _rehash_step(first)
    _rehash_episode(per_step_message_tamper)
    with pytest.raises(MultiAgentRuntimeError, match="budget accounting|message byte"):
        multiagent_receipt_from_mapping(per_step_message_tamper)

    malformed_sha = deepcopy(receipt.canonical())
    malformed_sha["step_receipts"][0]["input_payload_sha256"] = "not-a-sha"
    _rehash_step(malformed_sha["step_receipts"][0])
    _rehash_episode(malformed_sha)
    with pytest.raises(MultiAgentRuntimeError, match="canonical sha256"):
        multiagent_receipt_from_mapping(malformed_sha)


def test_multiagent_execution_rejects_a_reachable_cycle_before_dispatch(
    tmp_path,
) -> None:
    recurrent = make_harness(
        purpose="The single-agent engine may bound this; the DAG engine cannot.",
        entry_node_id="node:a",
        nodes=(
            HarnessNode(
                node_id="node:a",
                executor_agent_id=AGENT_A,
                capability=OBSERVE,
                instruction="Go to B.",
                next_node_ids=("node:b",),
            ),
            HarnessNode(
                node_id="node:b",
                executor_agent_id=AGENT_B,
                capability=BRANCH,
                instruction="Return to A.",
                next_node_ids=("node:a",),
            ),
        ),
    )
    with SQLiteSelfModelStore(tmp_path / "cycle.sqlite3", policy=_policy()) as store:
        _author_harness(store, recurrent)
        port_a = ScriptedPort(AGENT_A)
        port_b = ScriptedPort(AGENT_B)
        with pytest.raises(MultiAgentRuntimeError, match="acyclic"):
            _runtime(store, port_a, port_b).run_episode(
                episode_id="episode:cycle",
                inputs=_episode_inputs("episode:cycle"),
                budget=ExecutionBudget(step_budget=4),
            )
        assert port_a.calls == port_b.calls == []
