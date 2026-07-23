from __future__ import annotations

from dataclasses import replace

import pytest

from feedback_ports import (
    CapabilityAuthority,
    CapabilityError,
    CapabilityRole,
    JudgmentReceipt,
)
from feedback_runtime import (
    EventKind,
    FeedbackCommand,
    FeedbackRuntime,
    IdempotencyConflict,
    InvalidTransition,
    StaleCutError,
)
from feedback_store import SQLiteFeedbackStore


STREAM = "feedback-stream-1"
CUT = "source-cut-1"
SECRET = b"feedback-test-secret-32-bytes!!"


def make_runtime(path, *, stream_id: str = STREAM):
    authority = CapabilityAuthority(authority_id="test-authority", secret=SECRET)
    store = SQLiteFeedbackStore(path, initial_cut_id=CUT)
    runtime = FeedbackRuntime(
        store=store,
        authority=authority,
        stream_id=stream_id,
        initial_cut_id=CUT,
    )
    caps = {
        role: authority.mint(
            stream_id=stream_id,
            principal_id=f"principal-{role.value}",
            role=role,
        )
        for role in CapabilityRole
    }
    return runtime, authority, store, caps


def advance_to_observed(runtime: FeedbackRuntime, caps):
    attach = runtime.submit(
        runtime.command(
            EventKind.ATTACH,
            request_id="req-attach",
            capability=caps[CapabilityRole.PROPOSER],
            payload={"attachment_id": "attachment-1", "actor": "untrusted-judge"},
        )
    )
    proposal = runtime.submit(
        runtime.command(
            EventKind.PROPOSE,
            request_id="req-propose",
            capability=caps[CapabilityRole.PROPOSER],
            payload={"proposal_id": "proposal-1", "action": "candidate-change"},
        )
    )
    observed = runtime.submit(
        runtime.command(
            EventKind.OBSERVE,
            request_id="req-observe",
            capability=caps[CapabilityRole.EXECUTOR],
            payload={
                "receipt_id": "observation-1",
                "proposal_event_sha256": proposal.event_sha256,
                "observation": {"score": 7},
                "adapter_identity": "executor:test-v1",
            },
        )
    )
    return attach, proposal, observed


def finish(runtime: FeedbackRuntime, caps, verdict: str):
    _attach, proposal, observed = advance_to_observed(runtime, caps)
    judgment = runtime.submit(
        runtime.command(
            EventKind.JUDGE,
            request_id="req-judge",
            capability=caps[CapabilityRole.JUDGE],
            payload={
                "judgment_receipt_id": "judgment-1",
                "proposal_event_sha256": proposal.event_sha256,
                "observation_event_sha256": observed.event_sha256,
                "verdict": verdict,
                "adapter_identity": "judge:test-v1",
                "evidence": {"rule": "fixture"},
            },
        )
    )
    commit = runtime.submit(
        runtime.commit_command(
            request_id="req-commit", capability=caps[CapabilityRole.COMMITTER]
        )
    )
    dispatch = runtime.submit(
        runtime.dispatch_command(
            request_id="req-dispatch", capability=caps[CapabilityRole.DISPATCHER]
        )
    )
    return judgment, commit, dispatch


def test_accept_reject_first_diverge_at_judge_and_route_by_verdict(tmp_path):
    accept, _, accept_store, accept_caps = make_runtime(tmp_path / "accept.db")
    reject, _, reject_store, reject_caps = make_runtime(tmp_path / "reject.db")
    try:
        finish(accept, accept_caps, "ACCEPT")
        finish(reject, reject_caps, "REJECT")
        accept_state = accept.state()
        reject_state = reject.state()
        assert [e.event_sha256 for e in accept_state.events[:3]] == [
            e.event_sha256 for e in reject_state.events[:3]
        ]
        assert accept_state.events[3].kind == reject_state.events[3].kind == EventKind.JUDGE
        assert accept_state.events[3].event_sha256 != reject_state.events[3].event_sha256
        assert accept_state.final_cut_id != reject_state.final_cut_id
        assert accept_state.next_dispatch_id != reject_state.next_dispatch_id
        assert (accept_state.route, reject_state.route) == ("integrate", "revise")
    finally:
        accept_store.close()
        reject_store.close()


def test_payload_actor_cannot_grant_authority_and_capability_is_stream_scoped(tmp_path):
    runtime, authority, store, caps = make_runtime(tmp_path / "scope.db")
    try:
        event = runtime.submit(
            runtime.command(
                EventKind.ATTACH,
                request_id="attach",
                capability=caps[CapabilityRole.PROPOSER],
                payload={"attachment_id": "a", "actor": "pretend-admin"},
            )
        )
        assert event.principal_id == "principal-proposer"
        wrong_stream = authority.mint(
            stream_id="another-stream",
            principal_id="principal-proposer",
            role=CapabilityRole.PROPOSER,
        )
        command = runtime.command(
            EventKind.PROPOSE,
            request_id="propose",
            capability=wrong_stream,
            payload={"proposal_id": "p", "action": "x"},
        )
        with pytest.raises(CapabilityError):
            runtime.submit(command)
    finally:
        store.close()

def test_forged_capability_and_cross_role_principal_are_rejected(tmp_path):
    runtime, authority, store, caps = make_runtime(tmp_path / "roles.db")
    try:
        forged = replace(caps[CapabilityRole.PROPOSER], signature="0" * 64)
        with pytest.raises(CapabilityError):
            runtime.submit(
                runtime.command(
                    EventKind.ATTACH,
                    request_id="forged",
                    capability=forged,
                    payload={"attachment_id": "a"},
                )
            )
        _attach, proposal, observed = advance_to_observed(runtime, caps)
        same_principal_judge = authority.mint(
            stream_id=STREAM,
            principal_id="principal-proposer",
            role=CapabilityRole.JUDGE,
        )
        with pytest.raises(InvalidTransition, match="multiple stream roles"):
            runtime.submit(
                runtime.command(
                    EventKind.JUDGE,
                    request_id="bad-judge",
                    capability=same_principal_judge,
                    payload={
                        "judgment_receipt_id": "j",
                        "proposal_event_sha256": proposal.event_sha256,
                        "observation_event_sha256": observed.event_sha256,
                        "verdict": "ACCEPT",
                        "adapter_identity": "judge:test",
                    },
                )
            )
    finally:
        store.close()


def test_missing_phase_stale_cut_and_wrong_parents_fail_closed(tmp_path):
    runtime, _, store, caps = make_runtime(tmp_path / "guards.db")
    try:
        judge_early = FeedbackCommand(
            stream_id=STREAM,
            request_id="early-judge",
            kind=EventKind.JUDGE,
            capability=caps[CapabilityRole.JUDGE],
            input_cut_id=CUT,
            causal_parent_ids=(),
            payload={},
        )
        with pytest.raises(InvalidTransition, match="forbidden"):
            runtime.submit(judge_early)
        runtime.submit(
            runtime.command(
                EventKind.ATTACH,
                request_id="attach",
                capability=caps[CapabilityRole.PROPOSER],
                payload={"attachment_id": "a"},
            )
        )
        stale = runtime.command(
            EventKind.PROPOSE,
            request_id="stale",
            capability=caps[CapabilityRole.PROPOSER],
            input_cut_id="stale-cut",
            payload={"proposal_id": "p", "action": "x"},
        )
        with pytest.raises(StaleCutError):
            runtime.submit(stale)
        wrong_parent = runtime.command(
            EventKind.PROPOSE,
            request_id="wrong-parent",
            capability=caps[CapabilityRole.PROPOSER],
            causal_parent_ids=("0" * 64,),
            payload={"proposal_id": "p", "action": "x"},
        )
        with pytest.raises(InvalidTransition, match="parent"):
            runtime.submit(wrong_parent)
        assert runtime.state().phase == "attached"
        assert runtime.state().sequence == 1
    finally:
        store.close()


def test_first_write_wins_retry_and_conflict(tmp_path):
    runtime, _, store, caps = make_runtime(tmp_path / "retry.db")
    try:
        command = runtime.command(
            EventKind.ATTACH,
            request_id="same-request",
            capability=caps[CapabilityRole.PROPOSER],
            payload={"attachment_id": "a"},
        )
        first = runtime.submit(command)
        assert runtime.submit(command) == first
        conflict = replace(command, payload={"attachment_id": "different"})
        with pytest.raises(IdempotencyConflict):
            runtime.submit(conflict)
        assert runtime.state().sequence == 1
    finally:
        store.close()


def test_judgment_port_receives_pinned_cut_and_adapter_idempotency_key(tmp_path):
    runtime, _, store, caps = make_runtime(tmp_path / "port.db")
    try:
        _attach, proposal, observed = advance_to_observed(runtime, caps)

        class Port:
            adapter_identity = "judge:port-v1"
            received = None

            def judge(
                self,
                proposal_payload,
                observation,
                *,
                input_cut_id,
                pinned_cut,
                idempotency_key,
            ):
                self.received = (input_cut_id, pinned_cut, idempotency_key)
                return JudgmentReceipt(
                    receipt_id="port-j",
                    proposal_event_sha256=proposal.event_sha256,
                    observation_event_sha256=observed.event_sha256,
                    verdict="ACCEPT",
                    adapter_identity=self.adapter_identity,
                    evidence={"source": "port"},
                )

        port = Port()
        event = runtime.judge_with_port(
            port,
            request_id="port-request",
            capability=caps[CapabilityRole.JUDGE],
        )
        assert event.kind == EventKind.JUDGE
        assert port.received == (CUT, CUT, "port-request")
    finally:
        store.close()
