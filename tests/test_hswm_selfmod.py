from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import textwrap

import pytest

from hswm.cells.runtime import make_packet
from hswm.selfmod.contracts import (
    HarnessMode,
    HarnessNode,
    MemoryRecord,
    SelfModelContractError,
    SelfModelPolicy,
    canonical_json_bytes,
    make_snapshot,
    make_harness,
    make_mutation,
    make_token,
    memory_from_mapping,
    mutation_from_mapping,
    snapshot_from_mapping,
)
from hswm.selfmod.runtime import (
    AgentDecision,
    AuthoringRequest,
    ExecutionRequest,
    JsonSelfModifyingAgent,
    SelfModRuntimeError,
    SelfModifyingHSWM,
)
from hswm.selfmod.store import (
    MissingSourceTokenError,
    SQLiteSelfModelStore,
    StaleGenerationError,
    StoreIntegrityError,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
LEFT = "capability:left"
RIGHT = "capability:right"
AGENT_ID = "agent:self-authoring-fixture"
PROBE_CONTENT = {"task": "choose one authorized route"}


def _policy() -> SelfModelPolicy:
    return SelfModelPolicy(allowed_capabilities=frozenset({LEFT, RIGHT}))


def _input_token(episode_id: str):
    return make_token(
        token_id=f"input:{episode_id}",
        episode_id=episode_id,
        position=0,
        role="user",
        content=PROBE_CONTENT,
        provenance={"source": "selfmod-causal-test"},
    )


def _right_route_proposal(request: AuthoringRequest):
    source_ids = tuple(token.token_id for token in request.tokens)
    memory = MemoryRecord(
        memory_id="memory:route-right",
        kind="procedure",
        content={"preferred_capability": RIGHT},
        source_token_ids=source_ids,
        labels=("agent-authored", "routing"),
    )
    harness = make_harness(
        purpose="Use the route induced by the preceding episode.",
        entry_node_id="node:route-right",
        nodes=(
            HarnessNode(
                node_id="node:route-right",
                capability=RIGHT,
                instruction="Select the right capability for this cue.",
                memory_ids=(memory.memory_id,),
            ),
        ),
    )
    return make_mutation(
        base_snapshot_id=request.active.snapshot.snapshot_id,
        expected_generation=request.active.generation,
        author_id=AGENT_ID,
        source_token_ids=source_ids,
        upsert_memories=(memory,),
        harness_mode=HarnessMode.REPLACE,
        harness=harness,
        rationale="The agent authored a future route from its own sealed episode.",
    )


class HarnessFollowingAgent:
    """Stateless fixture: all behavioral variation comes from the active snapshot."""

    agent_id = AGENT_ID

    def __init__(self, *, author_harness: bool = False) -> None:
        self.author_harness = author_harness

    def decide(self, request: ExecutionRequest) -> AgentDecision:
        harness = request.active.snapshot.harness
        if harness is None:
            return AgentDecision(
                selected_capability=LEFT,
                output={"selected": LEFT},
            )
        node_by_id = {node.node_id: node for node in harness.nodes}
        node = node_by_id[harness.entry_node_id]
        return AgentDecision(
            selected_capability=node.capability,
            output={"selected": node.capability},
            used_memory_ids=node.memory_ids,
            followed_node_ids=(node.node_id,),
        )

    def author(self, request: AuthoringRequest):
        if not self.author_harness or request.active.snapshot.harness is not None:
            return None
        return _right_route_proposal(request)


class JsonBridgePort:
    """Minimal real CellPort bridge with agent-authored JSON responses."""

    def __init__(
        self,
        *,
        source_token_id: str,
        bad_execute_packet_type: bool = False,
        bad_execute_payload_digest: bool = False,
    ):
        self.source_token_id = source_token_id
        self.bad_execute_packet_type = bad_execute_packet_type
        self.bad_execute_payload_digest = bad_execute_payload_digest
        self.calls: list[str] = []

    def invoke(self, effect):
        operation = (
            "author"
            if effect.expected_output_type == "hswm-selfmod-author-response/v1"
            else "execute"
        )
        self.calls.append(operation)
        if operation == "author":
            response = {
                "noop": False,
                "rationale": "Author a durable route directly from absorbed tokens.",
                "upsert_memories": [
                    {
                        "memory_id": "memory:json-bridge",
                        "kind": "procedure",
                        "content": {"preferred_capability": RIGHT},
                        "source_token_ids": [self.source_token_id],
                        "related_memory_ids": [],
                        "labels": ["agent-authored", "json-bridge"],
                    }
                ],
                "delete_memory_ids": [],
                "harness_mode": "REPLACE",
                "harness": {
                    "purpose": "Execute the route authored through the CellPort.",
                    "entry_node_id": "node:json-bridge",
                    "nodes": [
                        {
                            "node_id": "node:json-bridge",
                            "capability": RIGHT,
                            "instruction": "Use the absorbed self-authored route.",
                            "memory_ids": ["memory:json-bridge"],
                            "next_node_ids": [],
                        }
                    ],
                },
            }
        else:
            response = {
                "selected_capability": RIGHT,
                "output": {"selected": RIGHT},
                "used_memory_ids": ["memory:json-bridge"],
                "followed_node_ids": ["node:json-bridge"],
            }
        packet_type = effect.expected_output_type
        if operation == "execute" and self.bad_execute_packet_type:
            packet_type = "hswm-selfmod-wrong-response/v1"
        packet = make_packet(
            packet_id=f"response:{len(self.calls)}",
            packet_type=packet_type,
            payload={"text": json.dumps(response, sort_keys=True)},
            provenance={"source": "json-selfmod-test-port"},
        )
        if operation == "execute" and self.bad_execute_payload_digest:
            return replace(packet, payload_sha256="0" * 64)
        return packet


def _run(
    runtime: SelfModifyingHSWM,
    episode_id: str,
    *,
    author_harness: bool = False,
    learn_after: bool = False,
):
    return runtime.run_episode(
        episode_id=episode_id,
        tokens=(_input_token(episode_id),),
        agent=HarnessFollowingAgent(author_harness=author_harness),
        capabilities=(LEFT, RIGHT),
        budget=1,
        learn_after=learn_after,
    )


def test_fresh_store_is_empty_and_does_not_preload_legacy_material(
    tmp_path, monkeypatch
) -> None:
    poison = tmp_path / "poison-cwd"
    (poison / "_research" / "root_compat").mkdir(parents=True)
    marker = "LEGACY_PRELOAD_SENTINEL_MUST_NOT_ENTER_HSWM"
    (poison / "AGENTS.md").write_text(marker, encoding="utf-8")
    (poison / "_research" / "root_compat" / "old-memory.json").write_text(
        json.dumps({"memory": marker}), encoding="utf-8"
    )
    monkeypatch.chdir(poison)

    with SQLiteSelfModelStore(tmp_path / "state-a.sqlite3", policy=_policy()) as first:
        active_a = first.active_snapshot()
    with SQLiteSelfModelStore(tmp_path / "state-b.sqlite3", policy=_policy()) as second:
        active_b = second.active_snapshot()

    assert active_a.generation == active_b.generation == 0
    assert active_a.snapshot.snapshot_id == active_b.snapshot.snapshot_id
    assert active_a.snapshot.memories == ()
    assert active_a.snapshot.harness is None
    assert marker.encode() not in canonical_json_bytes(active_a.snapshot.canonical())

    # This package must remain executable without the historical compatibility
    # tree; those files are replay material, never an implicit learner corpus.
    for source in sorted((REPO_ROOT / "src" / "hswm" / "selfmod").glob("*.py")):
        text = source.read_text(encoding="utf-8")
        assert "_research.root_compat" not in text
        assert "hswm.substrate.legacy_adapter" not in text
        assert "hswm.infrastructure.legacy_replay" not in text


def test_agent_authored_harness_only_changes_the_next_episode(tmp_path) -> None:
    path = tmp_path / "selfmod.sqlite3"
    with SQLiteSelfModelStore(path, policy=_policy()) as store:
        runtime = SelfModifyingHSWM(store)
        genesis = store.active_snapshot()
        first = _run(runtime, "episode:1", author_harness=True, learn_after=True)
        learned = store.active_snapshot()

        assert first.selected_capability == LEFT
        assert first.used_snapshot_id == genesis.snapshot.snapshot_id
        assert first.used_generation == 0
        assert first.harness_id is None
        assert first.activation is not None
        assert first.activation.active_snapshot_id == learned.snapshot.snapshot_id
        assert learned.generation == 1
        assert learned.snapshot.harness is not None
        assert learned.snapshot.memories[0].content == {"preferred_capability": RIGHT}

        # A fresh, stateless agent sees the same external task.  Only committed
        # HSWM state differs, and the actual selected capability changes.
        second = _run(runtime, "episode:2")
        assert second.selected_capability == RIGHT
        assert second.used_snapshot_id == learned.snapshot.snapshot_id
        assert second.used_generation == 1
        assert second.harness_id == learned.snapshot.harness.harness_id
        assert second.followed_node_ids == ("node:route-right",)
        assert second.used_memory_ids == ("memory:route-right",)
        assert second.input_content_sha256 == first.input_content_sha256
        assert second.capability_set_sha256 == first.capability_set_sha256
        assert second.budget == first.budget
        assert second.activation is None
        assert store.activation_count() == 1


def test_absorb_alone_can_author_state_that_changes_a_later_read_only_episode(
    tmp_path,
) -> None:
    path = tmp_path / "absorb-selfmod.sqlite3"

    class AbsorbOnlyAuthor(HarnessFollowingAgent):
        def decide(self, request: ExecutionRequest) -> AgentDecision:
            raise AssertionError("absorb must not execute an episode decision")

    with SQLiteSelfModelStore(path, policy=_policy()) as store:
        runtime = SelfModifyingHSWM(store)
        genesis = store.active_snapshot()
        absorbed = _input_token("episode:absorbed-observation")
        activation = runtime.absorb(
            (absorbed,), agent=AbsorbOnlyAuthor(author_harness=True)
        )

        assert activation is not None
        assert activation.base_snapshot_id == genesis.snapshot.snapshot_id
        assert activation.active_generation == 1
        assert store.token_count() == 1
        authored = store.active_snapshot()
        assert authored.snapshot.harness is not None
        assert authored.snapshot.memories[0].source_token_ids == (absorbed.token_id,)

        later = _run(runtime, "episode:after-absorb", learn_after=False)
        assert later.selected_capability == RIGHT
        assert later.used_snapshot_id == authored.snapshot.snapshot_id
        assert later.used_generation == authored.generation
        assert later.activation is None
        assert store.activation_count() == 1


def test_json_cell_port_bridge_authors_and_executes_state_and_checks_packet_type(
    tmp_path,
) -> None:
    path = tmp_path / "json-bridge-selfmod.sqlite3"
    absorbed = _input_token("episode:json-absorb")
    port = JsonBridgePort(source_token_id=absorbed.token_id)
    agent = JsonSelfModifyingAgent(agent_id=AGENT_ID, port=port)

    with SQLiteSelfModelStore(path, policy=_policy()) as store:
        runtime = SelfModifyingHSWM(store)
        activation = runtime.absorb((absorbed,), agent=agent)
        assert activation is not None
        assert port.calls == ["author"]
        active = store.active_snapshot()
        assert active.snapshot.memories[0].memory_id == "memory:json-bridge"
        assert active.snapshot.harness is not None
        assert active.snapshot.harness.entry_node_id == "node:json-bridge"

        episode_id = "episode:json-execute"
        executed = runtime.run_episode(
            episode_id=episode_id,
            tokens=(_input_token(episode_id),),
            agent=agent,
            capabilities=(LEFT, RIGHT),
            budget=1,
            learn_after=False,
        )
        assert port.calls == ["author", "execute"]
        assert executed.selected_capability == RIGHT
        assert executed.used_snapshot_id == active.snapshot.snapshot_id
        assert executed.used_memory_ids == ("memory:json-bridge",)
        assert executed.followed_node_ids == ("node:json-bridge",)

        bad_port = JsonBridgePort(
            source_token_id=absorbed.token_id, bad_execute_packet_type=True
        )
        bad_agent = JsonSelfModifyingAgent(agent_id=AGENT_ID, port=bad_port)
        bad_episode_id = "episode:json-wrong-packet"
        with pytest.raises(SelfModRuntimeError, match="packet type"):
            runtime.run_episode(
                episode_id=bad_episode_id,
                tokens=(_input_token(bad_episode_id),),
                agent=bad_agent,
                capabilities=(LEFT, RIGHT),
                budget=1,
                learn_after=False,
            )

        stale_digest_port = JsonBridgePort(
            source_token_id=absorbed.token_id, bad_execute_payload_digest=True
        )
        stale_digest_agent = JsonSelfModifyingAgent(
            agent_id=AGENT_ID, port=stale_digest_port
        )
        stale_digest_episode_id = "episode:json-stale-payload-digest"
        with pytest.raises(SelfModRuntimeError, match="payload digest"):
            runtime.run_episode(
                episode_id=stale_digest_episode_id,
                tokens=(_input_token(stale_digest_episode_id),),
                agent=stale_digest_agent,
                capabilities=(LEFT, RIGHT),
                budget=1,
                learn_after=False,
            )
        assert store.active_snapshot() == active
        assert store.activation_count() == 1


def test_process_restart_removal_and_exact_restore_prove_state_mediation(
    tmp_path,
) -> None:
    path = tmp_path / "durable-selfmod.sqlite3"
    with SQLiteSelfModelStore(path, policy=_policy()) as store:
        runtime = SelfModifyingHSWM(store)
        genesis = store.active_snapshot()
        first = _run(runtime, "episode:learn", author_harness=True, learn_after=True)
        learned = store.active_snapshot()
        assert first.activation is not None

    poison_cwd = tmp_path / "restart-cwd"
    poison_cwd.mkdir()
    (poison_cwd / "AGENTS.md").write_text(
        "A legacy-looking rule that must not be loaded.", encoding="utf-8"
    )
    child_program = textwrap.dedent(
        f"""
        import json
        import sys
        from hswm.selfmod.contracts import SelfModelPolicy, make_token
        from hswm.selfmod.runtime import AgentDecision, SelfModifyingHSWM
        from hswm.selfmod.store import SQLiteSelfModelStore

        LEFT = {LEFT!r}
        RIGHT = {RIGHT!r}

        class FreshProbeAgent:
            agent_id = {AGENT_ID!r}

            def decide(self, request):
                harness = request.active.snapshot.harness
                if harness is None:
                    return AgentDecision(LEFT, {{"selected": LEFT}})
                nodes = {{node.node_id: node for node in harness.nodes}}
                node = nodes[harness.entry_node_id]
                return AgentDecision(
                    node.capability,
                    {{"selected": node.capability}},
                    used_memory_ids=node.memory_ids,
                    followed_node_ids=(node.node_id,),
                )

            def author(self, request):
                return None

        policy = SelfModelPolicy(allowed_capabilities=frozenset({{LEFT, RIGHT}}))
        with SQLiteSelfModelStore(sys.argv[1], policy=policy) as store:
            before = store.active_snapshot()
            episode_id = "episode:restart-probe"
            token = make_token(
                token_id="input:restart-probe",
                episode_id=episode_id,
                position=0,
                role="user",
                content={PROBE_CONTENT!r},
                provenance={{"source": "fresh-child"}},
            )
            receipt = SelfModifyingHSWM(store).run_episode(
                episode_id=episode_id,
                tokens=(token,),
                agent=FreshProbeAgent(),
                capabilities=(LEFT, RIGHT),
                budget=1,
                learn_after=False,
            )
            after = store.active_snapshot()
            print(json.dumps({{
                "before_snapshot_id": before.snapshot.snapshot_id,
                "before_generation": before.generation,
                "after_snapshot_id": after.snapshot.snapshot_id,
                "after_generation": after.generation,
                "selected_capability": receipt.selected_capability,
                "input_content_sha256": receipt.input_content_sha256,
                "capability_set_sha256": receipt.capability_set_sha256,
                "budget": receipt.budget,
            }}, sort_keys=True))
        """
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(REPO_ROOT / "src")
    child = subprocess.run(
        [sys.executable, "-c", child_program, str(path)],
        cwd=poison_cwd,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert child.returncode == 0, child.stdout + child.stderr
    restarted = json.loads(child.stdout)
    assert restarted["before_snapshot_id"] == learned.snapshot.snapshot_id
    assert restarted["after_snapshot_id"] == learned.snapshot.snapshot_id
    assert restarted["before_generation"] == restarted["after_generation"] == 1
    assert restarted["selected_capability"] == RIGHT

    with SQLiteSelfModelStore(path, policy=_policy()) as store:
        runtime = SelfModifyingHSWM(store)
        before_removal_count = store.activation_count()
        removal = store.activate_snapshot(
            genesis.snapshot.snapshot_id,
            expected_generation=1,
            author_id="evaluator:causal-removal",
            source_token_ids=("input:episode:learn",),
            reason="causal-removal",
        )
        assert removal.active_snapshot_id == genesis.snapshot.snapshot_id
        removed = _run(runtime, "episode:removed-probe")
        assert removed.selected_capability == LEFT
        assert removed.used_snapshot_id == genesis.snapshot.snapshot_id
        assert removed.input_content_sha256 == restarted["input_content_sha256"]
        assert removed.capability_set_sha256 == restarted["capability_set_sha256"]
        assert removed.budget == restarted["budget"]

        restoration = store.activate_snapshot(
            learned.snapshot.snapshot_id,
            expected_generation=removal.active_generation,
            author_id="evaluator:exact-restore",
            source_token_ids=("input:episode:learn",),
            reason="exact-restore",
        )
        assert restoration.active_snapshot_id == learned.snapshot.snapshot_id
        restored = _run(runtime, "episode:restored-probe")
        assert restored.selected_capability == RIGHT
        assert restored.used_snapshot_id == learned.snapshot.snapshot_id
        assert restored.input_content_sha256 == removed.input_content_sha256
        assert restored.capability_set_sha256 == removed.capability_set_sha256
        assert restored.budget == removed.budget
        assert store.active_snapshot().snapshot.snapshot_id == learned.snapshot.snapshot_id
        assert store.activation_count() == before_removal_count + 2


def test_failed_mutation_and_stale_writers_leave_the_active_pointer_atomic(
    tmp_path,
) -> None:
    path = tmp_path / "cas-selfmod.sqlite3"
    first = SQLiteSelfModelStore(path, policy=_policy())
    second = SQLiteSelfModelStore(path, policy=_policy())
    try:
        token = _input_token("episode:cas")
        first.append_tokens((token,))
        base = first.active_snapshot()

        unauthorized_harness = make_harness(
            purpose="This proposal must fail closed.",
            entry_node_id="node:forbidden",
            nodes=(
                HarnessNode(
                    node_id="node:forbidden",
                    capability="capability:not-authorized",
                    instruction="Attempt an unauthorized route.",
                ),
            ),
        )
        unauthorized = make_mutation(
            base_snapshot_id=base.snapshot.snapshot_id,
            expected_generation=base.generation,
            author_id=AGENT_ID,
            source_token_ids=(token.token_id,),
            harness_mode=HarnessMode.REPLACE,
            harness=unauthorized_harness,
            rationale="Exercise the fixed authority boundary.",
        )
        with pytest.raises(SelfModelContractError, match="unauthorized"):
            first.commit(unauthorized)
        assert first.active_snapshot() == base
        assert first.activation_count() == 0

        request = AuthoringRequest(active=base, tokens=(token,))
        winning = _right_route_proposal(request)
        winner = first.commit(winning)
        active_after_winner = first.active_snapshot()
        assert winner.active_snapshot_id == active_after_winner.snapshot.snapshot_id

        losing_harness = make_harness(
            purpose="Competing stale route.",
            entry_node_id="node:route-left",
            nodes=(
                HarnessNode(
                    node_id="node:route-left",
                    capability=LEFT,
                    instruction="A stale writer tries to select left.",
                ),
            ),
        )
        losing = make_mutation(
            base_snapshot_id=base.snapshot.snapshot_id,
            expected_generation=base.generation,
            author_id="agent:competing-writer",
            source_token_ids=(token.token_id,),
            harness_mode=HarnessMode.REPLACE,
            harness=losing_harness,
            rationale="Lose the active-generation CAS.",
        )
        with pytest.raises(StaleGenerationError, match="active-state CAS"):
            second.commit(losing)

        assert second.active_snapshot() == active_after_winner
        assert second.activation_count() == 1
    finally:
        first.close()
        second.close()


@pytest.mark.parametrize("corruption", ["malformed", "noncanonical"])
def test_stored_snapshot_json_must_be_well_formed_and_canonical(
    tmp_path, corruption: str
) -> None:
    path = tmp_path / f"tampered-{corruption}.sqlite3"
    with SQLiteSelfModelStore(path, policy=_policy()) as store:
        token = _input_token(f"episode:tamper:{corruption}")
        store.append_tokens((token,))
        proposal = _right_route_proposal(
            AuthoringRequest(active=store.active_snapshot(), tokens=(token,))
        )
        store.commit(proposal)
        snapshot = store.active_snapshot().snapshot

    if corruption == "malformed":
        raw = b'{"schema_version":'
        expected = "invalid stored snapshot JSON"
    else:
        raw = json.dumps(snapshot.canonical(), indent=2).encode("utf-8")
        expected = "not canonical"
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "UPDATE self_model_snapshots SET snapshot_json=? WHERE snapshot_id=?",
            (raw, snapshot.snapshot_id),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(StoreIntegrityError, match=expected):
        SQLiteSelfModelStore(path, policy=_policy())


def test_reopen_rejects_a_different_constitutional_policy(tmp_path) -> None:
    path = tmp_path / "policy-bound.sqlite3"
    with SQLiteSelfModelStore(path, policy=_policy()):
        pass

    narrowed = SelfModelPolicy(allowed_capabilities=frozenset({LEFT}))
    with pytest.raises(StoreIntegrityError, match="authority differs"):
        SQLiteSelfModelStore(path, policy=narrowed)


def test_exact_commit_and_snapshot_activation_retries_are_idempotent(
    tmp_path,
) -> None:
    path = tmp_path / "idempotent-selfmod.sqlite3"
    with SQLiteSelfModelStore(path, policy=_policy()) as store:
        token = _input_token("episode:idempotency")
        store.append_tokens((token,))
        genesis = store.active_snapshot()
        proposal = _right_route_proposal(
            AuthoringRequest(active=genesis, tokens=(token,))
        )

        first_commit = store.commit(proposal)
        retry_commit = store.commit(proposal)
        assert retry_commit == first_commit
        assert store.activation_count() == 1

        removal_arguments = {
            "expected_generation": first_commit.active_generation,
            "author_id": "evaluator:idempotency",
            "source_token_ids": (token.token_id,),
            "reason": "idempotent-removal",
        }
        first_removal = store.activate_snapshot(
            genesis.snapshot.snapshot_id, **removal_arguments
        )
        retry_removal = store.activate_snapshot(
            genesis.snapshot.snapshot_id, **removal_arguments
        )
        assert retry_removal == first_removal
        assert store.activation_count() == 2
        assert store.active_snapshot().generation == first_removal.active_generation
        assert store.active_snapshot().snapshot.snapshot_id == genesis.snapshot.snapshot_id


def test_mutation_requires_every_cited_source_token_to_exist(tmp_path) -> None:
    path = tmp_path / "missing-source.sqlite3"
    with SQLiteSelfModelStore(path, policy=_policy()) as store:
        base = store.active_snapshot()
        missing = "token:not-in-the-store"
        memory = MemoryRecord(
            memory_id="memory:unsupported",
            kind="claim",
            content={"unsupported": True},
            source_token_ids=(missing,),
        )
        proposal = make_mutation(
            base_snapshot_id=base.snapshot.snapshot_id,
            expected_generation=base.generation,
            author_id=AGENT_ID,
            source_token_ids=(missing,),
            upsert_memories=(memory,),
            rationale="This proposal has no durable source token.",
        )

        with pytest.raises(MissingSourceTokenError, match="not stored"):
            store.commit(proposal)
        assert store.active_snapshot() == base
        assert store.activation_count() == 0
        assert store.snapshot_count() == 1


def test_harness_rejects_missing_references_but_permits_recurrent_cycles(
    tmp_path,
) -> None:
    with pytest.raises(SelfModelContractError, match="unknown node"):
        make_harness(
            purpose="Dangling topology must fail.",
            entry_node_id="node:only",
            nodes=(
                HarnessNode(
                    node_id="node:only",
                    capability=LEFT,
                    instruction="Attempt to leave the known graph.",
                    next_node_ids=("node:missing",),
                ),
            ),
        )

    path = tmp_path / "recurrent-harness.sqlite3"
    with SQLiteSelfModelStore(path, policy=_policy()) as store:
        token = _input_token("episode:recurrent")
        store.append_tokens((token,))
        base = store.active_snapshot()
        missing_memory_harness = make_harness(
            purpose="A missing memory reference must fail.",
            entry_node_id="node:missing-memory",
            nodes=(
                HarnessNode(
                    node_id="node:missing-memory",
                    capability=LEFT,
                    instruction="Try to use state that does not exist.",
                    memory_ids=("memory:missing",),
                ),
            ),
        )
        missing_memory = make_mutation(
            base_snapshot_id=base.snapshot.snapshot_id,
            expected_generation=base.generation,
            author_id=AGENT_ID,
            source_token_ids=(token.token_id,),
            harness_mode=HarnessMode.REPLACE,
            harness=missing_memory_harness,
            rationale="Exercise referential integrity.",
        )
        with pytest.raises(SelfModelContractError, match="missing memory"):
            store.commit(missing_memory)
        assert store.active_snapshot() == base

        recurrent = make_harness(
            purpose="Permit a bounded execution trace through a recurrent graph.",
            entry_node_id="node:a",
            nodes=(
                HarnessNode(
                    node_id="node:a",
                    capability=LEFT,
                    instruction="Move from A to B.",
                    next_node_ids=("node:b",),
                ),
                HarnessNode(
                    node_id="node:b",
                    capability=RIGHT,
                    instruction="The learned circuit may return from B to A.",
                    next_node_ids=("node:a",),
                ),
            ),
        )
        recurrent_proposal = make_mutation(
            base_snapshot_id=base.snapshot.snapshot_id,
            expected_generation=base.generation,
            author_id=AGENT_ID,
            source_token_ids=(token.token_id,),
            harness_mode=HarnessMode.REPLACE,
            harness=recurrent,
            rationale="Install a recurrent, rather than dangling, circuit.",
        )
        receipt = store.commit(recurrent_proposal)
        active = store.active_snapshot()
        assert receipt.active_snapshot_id == active.snapshot.snapshot_id
        assert active.snapshot.harness == recurrent
        assert active.snapshot.harness.nodes[0].next_node_ids == ("node:b",)
        assert active.snapshot.harness.nodes[1].next_node_ids == ("node:a",)


def test_noop_mutation_is_rejected_without_creating_state(tmp_path) -> None:
    path = tmp_path / "noop-selfmod.sqlite3"
    with SQLiteSelfModelStore(path, policy=_policy()) as store:
        token = _input_token("episode:noop")
        store.append_tokens((token,))
        base = store.active_snapshot()
        no_op = make_mutation(
            base_snapshot_id=base.snapshot.snapshot_id,
            expected_generation=base.generation,
            author_id=AGENT_ID,
            source_token_ids=(token.token_id,),
            rationale="Do not manufacture an activation for unchanged state.",
        )

        with pytest.raises(SelfModelContractError, match="no-op"):
            store.commit(no_op)
        assert store.active_snapshot() == base
        assert store.activation_count() == 0
        assert store.snapshot_count() == 1


def test_agent_authored_delete_and_harness_clear_return_to_empty_content(
    tmp_path,
) -> None:
    path = tmp_path / "delete-and-clear.sqlite3"
    with SQLiteSelfModelStore(path, policy=_policy()) as store:
        learned_source = _input_token("episode:learn-before-clear")
        store.append_tokens((learned_source,))
        genesis = store.active_snapshot()
        learned_proposal = _right_route_proposal(
            AuthoringRequest(active=genesis, tokens=(learned_source,))
        )
        store.commit(learned_proposal)
        learned = store.active_snapshot()
        assert learned.snapshot.snapshot_id != genesis.snapshot.snapshot_id
        assert learned.snapshot.memories
        assert learned.snapshot.harness is not None

        clear_source = _input_token("episode:agent-clear")
        store.append_tokens((clear_source,))
        clear = make_mutation(
            base_snapshot_id=learned.snapshot.snapshot_id,
            expected_generation=learned.generation,
            author_id=AGENT_ID,
            source_token_ids=(clear_source.token_id,),
            delete_memory_ids=tuple(
                memory.memory_id for memory in learned.snapshot.memories
            ),
            harness_mode=HarnessMode.CLEAR,
            rationale="The agent deletes its memory and clears its future harness.",
        )
        receipt = store.commit(clear)
        emptied = store.active_snapshot()

        assert receipt.reason == "SELF_AUTHORED_MUTATION"
        assert receipt.active_snapshot_id == genesis.snapshot.snapshot_id
        assert emptied.snapshot == genesis.snapshot
        assert emptied.generation == 2
        assert store.snapshot_count() == 2
        assert store.activation_count() == 2


def test_mutated_token_and_proposal_payloads_are_rejected_before_persistence(
    tmp_path,
) -> None:
    path = tmp_path / "mutable-inputs.sqlite3"
    with SQLiteSelfModelStore(path, policy=_policy()) as store:
        token_content = {"stable": True}
        token = make_token(
            token_id="token:mutable",
            episode_id="episode:mutable",
            position=0,
            role="observation",
            content=token_content,
            provenance={"source": "mutable-input-test"},
        )
        token_content["stable"] = False
        with pytest.raises(SelfModelContractError, match="content digest"):
            store.append_tokens((token,))
        assert store.token_count() == 0

        source = _input_token("episode:mutable-proposal")
        store.append_tokens((source,))
        base = store.active_snapshot()
        memory_content = {"route": RIGHT}
        memory = MemoryRecord(
            memory_id="memory:mutable",
            kind="procedure",
            content=memory_content,
            source_token_ids=(source.token_id,),
        )
        proposal = make_mutation(
            base_snapshot_id=base.snapshot.snapshot_id,
            expected_generation=base.generation,
            author_id=AGENT_ID,
            source_token_ids=(source.token_id,),
            upsert_memories=(memory,),
            rationale="Reject mutation after its content-addressed payload changes.",
        )
        memory_content["route"] = LEFT
        with pytest.raises(
            (SelfModelContractError, StoreIntegrityError), match="digest|mutation id"
        ):
            store.commit(proposal)
        assert store.active_snapshot() == base
        assert store.activation_count() == 0
        assert store.snapshot_count() == 1


def test_mapping_parsers_reject_wrong_union_and_list_shapes() -> None:
    empty = make_snapshot()
    bad_snapshot = empty.canonical()
    bad_snapshot["harness"] = "silently-droppable-string"
    with pytest.raises(SelfModelContractError, match="harness"):
        snapshot_from_mapping(bad_snapshot)

    mutation = make_mutation(
        base_snapshot_id=empty.snapshot_id,
        expected_generation=0,
        author_id=AGENT_ID,
        source_token_ids=("token:source",),
        rationale="Parser shape fixture.",
    )
    bad_mutation = mutation.canonical()
    bad_mutation["harness"] = "silently-droppable-string"
    with pytest.raises(SelfModelContractError, match="harness"):
        mutation_from_mapping(bad_mutation)

    memory = MemoryRecord(
        memory_id="memory:shape",
        kind="fact",
        content={"value": 1},
        source_token_ids=("token:source",),
    )
    bad_memory = memory.canonical()
    bad_memory["source_token_ids"] = "abc"
    with pytest.raises(SelfModelContractError, match="list|array"):
        memory_from_mapping(bad_memory)


@pytest.mark.parametrize("foreign_reference", ["proposal", "memory"])
def test_runtime_rejects_sources_outside_the_authoring_request(
    tmp_path, foreign_reference: str
) -> None:
    path = tmp_path / f"foreign-source-{foreign_reference}.sqlite3"
    old = _input_token("episode:old-source")
    current = _input_token(f"episode:current-source:{foreign_reference}")

    class ForeignSourceAuthor:
        agent_id = AGENT_ID

        def decide(self, request: ExecutionRequest) -> AgentDecision:
            raise AssertionError("absorb must not call decide")

        def author(self, request: AuthoringRequest):
            proposal_sources = (current.token_id,)
            memory_sources = (current.token_id,)
            if foreign_reference == "proposal":
                proposal_sources = (current.token_id, old.token_id)
            else:
                memory_sources = (old.token_id,)
            memory = MemoryRecord(
                memory_id=f"memory:foreign:{foreign_reference}",
                kind="claim",
                content={"foreign_reference": foreign_reference},
                source_token_ids=memory_sources,
            )
            return make_mutation(
                base_snapshot_id=request.active.snapshot.snapshot_id,
                expected_generation=request.active.generation,
                author_id=self.agent_id,
                source_token_ids=proposal_sources,
                upsert_memories=(memory,),
                rationale="Attempt to cite stored state outside this authoring request.",
            )

    with SQLiteSelfModelStore(path, policy=_policy()) as store:
        store.append_tokens((old,))
        base = store.active_snapshot()
        with pytest.raises(
            SelfModRuntimeError,
            match="outside.*authoring request|provenance.*source scope|subset",
        ):
            SelfModifyingHSWM(store).absorb(
                (current,), agent=ForeignSourceAuthor()
            )
        assert store.active_snapshot() == base
        assert store.activation_count() == 0


def test_activation_retry_detects_request_hash_tampering(tmp_path) -> None:
    path = tmp_path / "activation-request-tamper.sqlite3"
    with SQLiteSelfModelStore(path, policy=_policy()) as store:
        token = _input_token("episode:activation-tamper")
        store.append_tokens((token,))
        genesis = store.active_snapshot()
        proposal = _right_route_proposal(
            AuthoringRequest(active=genesis, tokens=(token,))
        )
        learned = store.commit(proposal)
        arguments = {
            "expected_generation": learned.active_generation,
            "author_id": "evaluator:tamper-test",
            "source_token_ids": (token.token_id,),
            "reason": "tamper-test-removal",
        }
        removal = store.activate_snapshot(
            genesis.snapshot.snapshot_id, **arguments
        )
        assert store.activation_count() == 2

    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "UPDATE activation_requests SET request_sha256=?",
            ("0" * 64,),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(
        StoreIntegrityError, match="activation request.*disagree|request.*digest"
    ):
        SQLiteSelfModelStore(path, policy=_policy())
