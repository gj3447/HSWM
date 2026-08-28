from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

import pytest

from _research.dnrd.runner import (
    ARMS,
    BRIDGE_MOUNT_CLOSURE_PLAN_SCHEMA,
    BRIDGE_STATE_EVIDENCE_SCHEMA,
    BridgeMountClosureExport,
    ControlMaterialization,
    InitializationObservation,
    MAX_OUTPUT_TOKENS,
    MeasurementMetadata,
    ModelReply,
    ModelRequest,
    MOUNT_ROLES,
    PreDispatchAnswererError,
    RecoveryObservation,
    RoutingState,
    RunnerRefusal,
    SubprocessJsonBridge,
    SubprocessOutcomeScorer,
    TRACE_STATUS,
    _derive_overlap_observation,
    _validate_metadata,
    _validate_model_event_ledger,
    _validate_reply,
    model_request_commitment,
    run_diagnostic,
)
from _research.dnrd.scorer import score_response
from _research.dnrd.task_family import (
    canonical_json,
    commitment,
    generate_manifests,
    training_provenance_canaries,
)


SEED = bytes(range(32))
SCORER_PATH = Path("_research/dnrd/scorer.py")
SCORER_SHA256 = hashlib.sha256(SCORER_PATH.read_bytes()).hexdigest()


def _sha(value: object) -> str:
    return commitment(value)


def _deployment() -> dict:
    bodies = {
        "model_list": canonical_json({"data": [{"id": "model-fixture"}]}).decode(),
        "version": canonical_json({"version": "fixture"}).decode(),
        "tokenizer": canonical_json({"count": 1, "tokens": [1]}).decode(),
    }
    unsigned = {
        "schema_version": "hswm-dnrd-live-preflight-receipt/v1",
        "endpoint": "http://model.fixture",
        "model": "model-fixture",
        "model_root": "fixture-root",
        "model_max_model_len": 1024,
        "vllm_version": "fixture",
        "chat_config": {"max_tokens": MAX_OUTPUT_TOKENS},
        "model_list_request_sha256": _sha("models-request"),
        "model_list_response_sha256": hashlib.sha256(bodies["model_list"].encode()).hexdigest(),
        "model_list_response_utf8": bodies["model_list"],
        "version_request_sha256": _sha("version-request"),
        "version_response_sha256": hashlib.sha256(bodies["version"].encode()).hexdigest(),
        "version_response_utf8": bodies["version"],
        "tokenizer_request_sha256": _sha("tokenizer-request"),
        "tokenizer_response_sha256": hashlib.sha256(bodies["tokenizer"].encode()).hexdigest(),
        "tokenizer_response_utf8": bodies["tokenizer"],
        "tokenizer_count": 1,
        "provider_cache_independence": "NOT_OBSERVABLE_BY_CLIENT",
        "generation_calls": 0,
        "non_generation_http_calls": 3,
        "preflight_call_order": ["GET /v1/models", "GET /version", "POST /tokenize"],
    }
    return {**unsigned, "receipt_sha256": commitment(unsigned)}


def _metadata() -> MeasurementMetadata:
    deployment = _deployment()
    return MeasurementMetadata(
        bindings={
            "source_manifest_sha256": _sha("source"),
            "preregistration_sha256": _sha("prereg"),
            "preregistration_ci_receipt_sha256": _sha("prereg-ci"),
            "pulse_receipt_sha256": _sha("pulse"),
            "split_manifest_sha256": _sha("split"),
            "model_deployment_sha256": commitment(deployment),
            "scorer_sha256": SCORER_SHA256,
            "runtime_receipt_sha256": _sha("runtime"),
            "git_chronology_evidence_sha256": _sha("git-chronology"),
        },
        chronology={
            "source_commit": "a" * 40,
            "preregistration_commit": "b" * 40,
            "source_tree_oid": "c" * 40,
            "preregistration_tree_oid": "d" * 40,
            "source_frozen_at_unix": 1,
            "source_ci_completed_at_unix": 1,
            "preregistration_committed_at_unix": 1,
            "preregistration_ci_completed_at_unix": 2,
            "pulse_round": 1,
            "pulse_chain_hash": _sha("chain"),
            "pulse_at_unix": 1000,
        },
        overlap={
            "normalizer_sha256": _sha("normalizer"),
            "training_heldout_exact_overlap": 0,
            "training_heldout_normalized_overlap": 0,
            "prior_item_overlap": 0,
            "leak_detected": False,
            "watermark_detected": False,
        },
        deployment_receipt=deployment,
        scorer_source_identity=SCORER_SHA256,
        scorer_address="_research/dnrd/scorer.py",
        active_state_byte_ceiling=16_384,
    )


def _structured_chat_config(request: ModelRequest) -> dict:
    """Independent fixture copy of DNRD-4S1's frozen per-call wire contract."""
    schema = {
        "type": "object",
        "properties": {
            "response_token": {
                "type": "string",
                "enum": list(request.candidate_response_tokens),
                "pattern": r"^token-[0-9a-f]{20}$",
                "minLength": 26,
                "maxLength": 26,
            }
        },
        "required": ["response_token"],
        "additionalProperties": False,
    }
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "hswm_dnrd_response_token",
            "strict": True,
            "schema": schema,
        },
    }
    return {
        "chat_template_kwargs": {"enable_thinking": False},
        "logprobs": False,
        "n": 1,
        "stream": False,
        "temperature": 0,
        "top_p": 1,
        "max_tokens": request.max_output_tokens,
        "response_format": response_format,
        "response_format_schema_sha256": commitment(schema),
    }


class EvidenceAnswerer:
    """Public-evidence answerer with a raw live-boundary event ledger."""

    def __init__(
        self,
        *,
        fail_on: int | None = None,
        output_tokens: int = 1,
        pretty_response: bool = False,
        model: str = "model-fixture",
        endpoint: str = "http://model.fixture",
    ) -> None:
        self.requests: list[ModelRequest] = []
        self.events: list[dict] = []
        self.fail_on = fail_on
        self.output_tokens = output_tokens
        self.pretty_response = pretty_response
        self.model = model
        self.endpoint = endpoint.rstrip("/")

    def answer(self, request: ModelRequest) -> ModelReply:
        self.requests.append(request)
        if self.fail_on == len(self.requests):
            raise PreDispatchAnswererError("injected pre-dispatch answerer failure")
        assert request.max_output_tokens == MAX_OUTPUT_TOKENS
        token = request.prompt.rsplit("nonce=", 1)[1]
        reply = ModelReply(token, input_tokens=1, output_tokens=self.output_tokens)
        content = (
            '{\n  "response_token" : "' + token + '"\n}'
            if self.pretty_response else canonical_json({"response_token": token}).decode()
        )
        raw = canonical_json(
            {
                "model": self.model,
                "choices": [{"finish_reason": "stop", "message": {"content": content}}],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": self.output_tokens,
                    "total_tokens": 1 + self.output_tokens,
                },
            }
        ).decode()
        request_digest = model_request_commitment(request)
        response = {
            "response_token": token,
            "input_tokens": 1,
            "output_tokens": self.output_tokens,
            "client_cache_hit": False,
            "server_usage": {},
        }
        common = {
            "schema_version": "hswm-dnrd-live-model-event/v3",
            "ordinal": request.ordinal,
            "phase": request.phase,
            "arm": request.arm,
            "dnrd_request_sha256": request_digest,
            "endpoint": f"{self.endpoint}/v1/chat/completions",
            "model": self.model,
            "request_sha256": _sha({"provider_request": request_digest}),
            "raw_response_sha256": hashlib.sha256(raw.encode()).hexdigest(),
            "chat_config": _structured_chat_config(request),
            "elapsed_nanoseconds": 1,
            "provider_cache_independence": "NOT_OBSERVABLE_BY_CLIENT",
        }
        self.events.extend(
            [
                {**common, "event": "CHAT_COMPLETION_OBSERVED", "http_status": 200},
                {
                    **common,
                    "event": "CHAT_COMPLETION_ACCEPTED",
                    "raw_response_utf8": raw,
                    "dnrd_response_sha256": commitment(response),
                    "usage": {
                        "prompt_tokens": 1,
                        "completion_tokens": self.output_tokens,
                    },
                },
            ]
        )
        return reply


class RecordingBridge:
    def __init__(self, timeline: list[str] | None = None) -> None:
        self.events: list[str] = []
        self.sealed_episodes: list[dict] = []
        self.timeline = timeline if timeline is not None else []
        self.streams: dict[str, dict] = {}
        self.known_mounts: set[str] = set()
        self.materialized: list[tuple[str, str]] = []
        self._mount_counter = 0
        self._recover_counter = 0
        self._journal_counter = 0

    def _mount(self, label: str) -> str:
        self._mount_counter += 1
        value = f"mount:{label}:{self._mount_counter}"
        self.known_mounts.add(value)
        return value

    @staticmethod
    def _payload(scores: dict[str, dict[str, int]]) -> bytes:
        return canonical_json({"scores": scores})

    def _state(
        self,
        scores: dict[str, dict[str, int]],
        *,
        revision: str,
        lineage: str,
        mount: str,
        role: str,
    ) -> RoutingState:
        payload = self._payload(scores)
        return RoutingState(
            hashlib.sha256(payload).hexdigest(),
            revision,
            lineage,
            "owner:dnrd:routing",
            mount,
            role,
            scores,
        )

    def initialize(self, stream: dict) -> InitializationObservation:
        self.events.append("init")
        self.streams[stream["stream_id"]] = stream
        scores = {context: {route: 0 for route in stream["route_ids"]} for context in stream["context_keys"]}
        lineage = f"lineage:{stream['stream_id']}"
        w0 = self._state(scores, revision=f"w0:{stream['stream_id']}", lineage=lineage, mount=self._mount("w0"), role=MOUNT_ROLES["NO_MEMORY_ROLLBACK"])
        w1 = self._state(scores, revision=f"w1:{stream['stream_id']}", lineage=lineage, mount=self._mount("w1"), role=MOUNT_ROLES["FULL"])
        return InitializationObservation(w0, w1, _sha({"init": stream["stream_id"]}), _sha({"prefix": stream["stream_id"]}), True)

    def materialize_control(self, state: RoutingState, stream_id: str, arm: str, training_update_records: list[dict], matched_derangement: dict[str, str]) -> ControlMaterialization:
        self.events.append("materialize")
        self.materialized.append((stream_id, arm))
        assert state.mount_id in self.known_mounts
        stream = self.streams[stream_id]
        scores = {context: dict(routes) for context, routes in state.scores.items()}
        if arm == "BINDING_DERANGED_NUMERIC_PLACEBO":
            assert state.mount_role == MOUNT_ROLES["FULL"]
            assert matched_derangement == stream["matched_derangement"]
            scores = {receiver: dict(state.scores[donor]) for receiver, donor in matched_derangement.items()}
        elif arm == "RAW_EQUAL_BUDGET":
            assert state.mount_role == MOUNT_ROLES["NO_MEMORY_ROLLBACK"]
            assert len(training_update_records) == 8
            for record in training_update_records:
                scores[record["context_key"]][record["selected_route_id"]] += record["reward"] * 100_000 // 1_000_000
        else:
            raise AssertionError("unexpected control arm")
        control = self._state(scores, revision=f"{arm}:{_sha(scores)[:12]}", lineage=state.lineage_id, mount=self._mount(arm), role=MOUNT_ROLES[arm])
        return ControlMaterialization(control, _sha({"arm": arm, "state": control.state_sha256}))

    def seal_trace(self, state: RoutingState, episode: dict, selected_route_id: str, request_sha256: str, response_sha256: str) -> dict:
        self.events.append("seal")
        self.timeline.append("seal")
        self.sealed_episodes.append(dict(episode))
        assert state.mount_id in self.known_mounts
        self._journal_counter += 1
        return {
            "trace_id": _sha({"state": state.state_sha256, "episode": episode["episode_id"], "route": selected_route_id, "request": request_sha256, "response": response_sha256}),
            "episode_id": episode["episode_id"],
            "context_key": episode["context_key"],
            "context_sha256": hashlib.sha256(episode["context_key"].encode()).hexdigest(),
            "stratum": "stratum:" + hashlib.sha256(episode["stream_id"].encode()).hexdigest(),
            "selected_route_id": selected_route_id,
            "pre_outcome_score_micros": state.scores[episode["context_key"]][selected_route_id],
            "routing_payload_sha256": state.state_sha256,
            "request_sha256": request_sha256,
            "response_sha256": response_sha256,
            "status": TRACE_STATUS,
        }

    def apply_outcome(self, state: RoutingState, trace: dict, outcome: dict) -> tuple[RoutingState, dict]:
        self.events.append("apply")
        self.timeline.append("apply")
        assert state.mount_role == MOUNT_ROLES["FULL"]
        scores = {context: dict(routes) for context, routes in state.scores.items()}
        scores[trace["context_key"]][trace["selected_route_id"]] = max(
            -100_000,
            min(100_000, scores[trace["context_key"]][trace["selected_route_id"]] + outcome["reward"] * 100_000 // 1_000_000),
        )
        updated = self._state(scores, revision=f"revision:{_sha({'trace': trace, 'outcome': outcome})[:12]}", lineage=state.lineage_id, mount=state.mount_id, role=state.mount_role)
        return updated, {"receipt": _sha({"trace": trace, "outcome": outcome, "after": updated.state_sha256})}

    def recover(self, state: RoutingState) -> RecoveryObservation:
        self.events.append("recover")
        assert state.mount_id in self.known_mounts
        self._recover_counter += 1
        scores = {context: dict(routes) for context, routes in state.scores.items()}
        payload = self._payload(scores)
        recovered = self._state(scores, revision=state.revision_id, lineage=state.lineage_id, mount=state.mount_id, role=state.mount_role)
        process_instance_id = (
            f"00000000-0000-4000-8000-{self._recover_counter:012x}"
        )
        return RecoveryObservation(recovered, _sha({"journal": state.mount_id, "ordinal": self._journal_counter}), True, True, process_instance_id, payload.decode(), hashlib.sha256(payload).hexdigest(), len(payload))


class RecordingScorer:
    def __init__(self, timeline: list[str] | None = None) -> None:
        # Test scorer owns its private material at construction.  The runner
        # receives only the matching commitment.
        self.private_manifest = generate_manifests(SEED)[1]
        self.seen_sealed: list[dict] = []
        self.timeline = timeline if timeline is not None else []

    def score(self, sealed_response: dict) -> dict:
        self.timeline.append("score")
        self.seen_sealed.append(sealed_response)
        return score_response(sealed_response, self.private_manifest)


class RecordingClosureExporter:
    """Test-only closure seam; production export is owned by execute.py."""

    def __init__(
        self,
        timeline: list[str] | None = None,
        *,
        watermark_detected: bool = False,
    ) -> None:
        self.plans: list[dict] = []
        self.timeline = timeline if timeline is not None else []
        self.watermark_detected = watermark_detected
        self.forbidden_markers: frozenset[str] | None = None

    def export(
        self,
        plan: dict,
        *,
        forbidden_markers: frozenset[str],
    ) -> BridgeMountClosureExport:
        self.timeline.append("closure")
        frozen = json.loads(canonical_json(plan))
        self.plans.append(frozen)
        self.forbidden_markers = forbidden_markers
        return BridgeMountClosureExport(
            artifact_sha256=commitment(frozen),
            watermark_detected=self.watermark_detected,
        )


class FailingScorer(RecordingScorer):
    def score(self, sealed_response: dict) -> dict:
        super().score(sealed_response)
        raise RuntimeError("injected scorer failure after sealed response")


class NonReproducibleReplayBridge(RecordingBridge):
    def recover(self, state: RoutingState) -> RecoveryObservation:
        result = super().recover(state)
        if state.mount_role == MOUNT_ROLES["RAW_EQUAL_BUDGET"]:
            scores = {context: dict(routes) for context, routes in state.scores.items()}
            context = next(iter(scores))
            route = next(iter(scores[context]))
            scores[context][route] += 1
            mutated = self._state(scores, revision="bad-replay", lineage=state.lineage_id, mount=state.mount_id, role=state.mount_role)
            payload = self._payload(scores)
            return RecoveryObservation(
                mutated, result.journal_sha256, result.recovered,
                result.fresh_process, result.process_instance_id, payload.decode(),
                hashlib.sha256(payload).hexdigest(), len(payload),
            )
        return result


class MutatingEvaluationBridge(RecordingBridge):
    def __init__(self) -> None:
        super().__init__()
        self._heldout_calls = 0

    def seal_trace(self, state: RoutingState, episode: dict, selected_route_id: str, request_sha256: str, response_sha256: str) -> dict:
        trace = super().seal_trace(state, episode, selected_route_id, request_sha256, response_sha256)
        if episode["phase"] == "heldout":
            self._heldout_calls += 1
            # Alter only the final heldout trace.  No next model call can
            # expose it; the post-evaluation recovery audit must do so.
            if self._heldout_calls == 96:
                state.scores[episode["context_key"]][selected_route_id] += 1
        return trace


def _run(
    answerer: EvidenceAnswerer,
    bridge: RecordingBridge,
    scorer: RecordingScorer,
    closure_exporter: RecordingClosureExporter | None = None,
    runner_rows: list[dict] | None = None,
):
    public, private = generate_manifests(SEED)
    return run_diagnostic(
        public,
        private_manifest_commitment=commitment(private),
        answerer=answerer,
        bridge=bridge,
        scorer=scorer,
        metadata=_metadata(),
        event_sink=(lambda row: runner_rows.append(dict(row))) if runner_rows is not None else None,
        model_event_ledger_provider=lambda: tuple(answerer.events),
        closure_exporter=closure_exporter or RecordingClosureExporter(),
    )


def test_runner_call_shape_ledger_and_no_verdict() -> None:
    timeline: list[str] = []
    answerer, bridge, scorer = EvidenceAnswerer(), RecordingBridge(timeline), RecordingScorer(timeline)
    closure_exporter = RecordingClosureExporter(timeline)
    runner_rows: list[dict] = []
    result = _run(answerer, bridge, scorer, closure_exporter, runner_rows)
    assert result.inconclusive_occurrence is None
    assert len(answerer.requests) == len(scorer.seen_sealed) == 128
    assert len(answerer.events) == 256
    assert len(runner_rows) == 256
    assert [row["event"] for row in runner_rows[::2]] == ["PRE_DISPATCH_READOUT"] * 128
    assert [row["event"] for row in runner_rows[1::2]] == ["COMPLETED_CALL"] * 128
    for pre, completed in zip(runner_rows[::2], runner_rows[1::2], strict=True):
        assert completed["pre_dispatch_receipt_sha256"] == _sha(pre)
        assert completed["request"]["pre_dispatch_receipt_sha256"] == _sha(pre)
    assert bridge.events.count("seal") == 128
    assert bridge.events.count("apply") == 32
    assert [request.phase for request in answerer.requests[:32]] == ["training"] * 32
    assert [request.phase for request in answerer.requests[32:]] == ["heldout"] * 96
    assert all(
        request.candidate_response_tokens
        == tuple(sorted(request.candidate_response_tokens))
        and len(request.candidate_response_tokens) == 2
        for request in answerer.requests
    )
    assert all(timeline[index:index + 3] == ["seal", "score", "apply"] for index in range(0, 96, 3))
    assert all(
        timeline[index:index + 2] == ["seal", "score"]
        for index in range(96, 96 + 96 * 2, 2)
    )
    candidate = result.candidate
    assert candidate is not None
    assert set(candidate) == {"schema_version", "experiment_id", "bindings", "chronology", "overlap", "parity", "call_ledger", "streams"}
    assert candidate["schema_version"] == "hswm-dnrd-candidate/v3"
    assert candidate["experiment_id"] == "HSWM-DNRD-4S1"
    assert candidate["bindings"]["preregistration_ci_receipt_sha256"] == _sha("prereg-ci")
    assert candidate["bindings"]["git_chronology_evidence_sha256"] == _sha("git-chronology")
    assert set(candidate["chronology"]) == {
        "source_commit", "preregistration_commit", "source_tree_oid",
        "preregistration_tree_oid", "source_frozen_at_unix",
        "preregistration_committed_at_unix", "preregistration_ci_completed_at_unix",
        "pulse_round", "pulse_chain_hash", "pulse_at_unix",
    }
    assert "source_ci_completed_at_unix" not in candidate["chronology"]
    assert "verdict" not in json.dumps(candidate).casefold()
    assert candidate["call_ledger"]["client_dispatched_generation_requests"] == 128


    assert candidate["parity"]["fresh_process_recovery_observed"] is False
    assert candidate["parity"]["evaluation_read_only_wrt_routing_observed"] is True
    assert candidate["parity"]["equal_generation_limits_input_token_parity_not_claimed"] is True
    assert candidate["overlap"]["watermark_detected"] is False
    assert result.bridge_state_evidence is not None
    assert result.bridge_state_evidence["schema_version"] == BRIDGE_STATE_EVIDENCE_SCHEMA
    for stream in result.bridge_state_evidence["streams"]:
        assert set(stream) == {"stream_id", "pre_evaluation", "post_evaluation", "fixed_rule_replay"}
        assert stream["pre_evaluation"]["arms"] == stream["post_evaluation"]["arms"]
    assert all("private_manifest" not in request.prompt for request in answerer.requests)
    assert all("context_correct_route" not in canonical_json(episode).decode() for episode in bridge.sealed_episodes)
    assert len(closure_exporter.plans) == 1
    plan = closure_exporter.plans[0]
    assert plan["schema_version"] == BRIDGE_MOUNT_CLOSURE_PLAN_SCHEMA
    assert [stream["stream_id"] for stream in plan["streams"]] == [
        "stream-0",
        "stream-1",
        "stream-2",
        "stream-3",
    ]
    assert all(set(stream["arms"]) == set(ARMS) and "fixed_rule_replay" in stream for stream in plan["streams"])
    assert result.bridge_mount_closure_sha256 == commitment(plan)
    assert candidate["bindings"]["bridge_mount_closure_sha256"] == commitment(plan)
    assert timeline[-1] == "closure"
    for stream in candidate["streams"]:
        replay = stream["fixed_rule_replay"]
        assert replay["rule"] == "signed_reward_times_100000_div_1000000/v1"
        assert len(replay["heldout_readouts"]) == 8
        assert replay["w1_routing_payload_sha256"] == replay["replay_routing_payload_sha256"]
        assert replay["w1_routing_payload_bytes"] == replay["replay_routing_payload_bytes"]


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        (
            {
                "source_frozen_at_unix": 2,
                "source_ci_completed_at_unix": 1,
                "preregistration_committed_at_unix": 2,
                "preregistration_ci_completed_at_unix": 3,
                "pulse_at_unix": 903,
            },
            "source-A CI completion precedes source freeze",
        ),
        (
            {
                "source_ci_completed_at_unix": 2,
                "preregistration_committed_at_unix": 1,
                "preregistration_ci_completed_at_unix": 2,
                "pulse_at_unix": 902,
            },
            "B commit precedes source-A CI completion",
        ),
        (
            {
                "preregistration_committed_at_unix": 3,
                "preregistration_ci_completed_at_unix": 2,
                "pulse_at_unix": 902,
            },
            "B-CI completion precedes B commit",
        ),
        ({"pulse_at_unix": 901}, "future pulse is earlier"),
    ],
)
def test_runner_metadata_refuses_invalid_dnrd4s1_chronology_order(
    updates: dict[str, int], message: str
) -> None:
    metadata = _metadata()
    chronology = {**metadata.chronology, **updates}
    with pytest.raises(RunnerRefusal, match=message):
        _validate_metadata(replace(metadata, chronology=chronology))


@pytest.mark.parametrize(
    "bindings",
    [
        lambda value: {key: item for key, item in value.items() if key != "git_chronology_evidence_sha256"},
        lambda value: {**value, "ratification_statement_sha256": _sha("obsolete-ratification")},
    ],
)
def test_runner_metadata_requires_exact_dnrd4s1_binding_set(bindings) -> None:
    metadata = _metadata()
    with pytest.raises(RunnerRefusal, match="metadata binding key set drifted"):
        _validate_metadata(replace(metadata, bindings=bindings(dict(metadata.bindings))))


def test_runner_refuses_invalid_chronology_before_any_model_call() -> None:
    public, private = generate_manifests(SEED)
    answerer = EvidenceAnswerer()
    metadata = _metadata()
    invalid = replace(
        metadata,
        chronology={
            **metadata.chronology,
            "preregistration_ci_completed_at_unix": 2,
            "pulse_at_unix": 901,
        },
    )
    with pytest.raises(RunnerRefusal, match="DNRD-4S1 future pulse"):
        run_diagnostic(
            public,
            private_manifest_commitment=commitment(private),
            answerer=answerer,
            bridge=RecordingBridge(),
            scorer=RecordingScorer(),
            metadata=invalid,
            model_event_ledger_provider=lambda: tuple(answerer.events),
            closure_exporter=RecordingClosureExporter(),
        )
    assert answerer.requests == []


def test_runner_accepts_pretty_semantic_structured_response_and_retains_raw_hash() -> None:
    answerer = EvidenceAnswerer(pretty_response=True)
    result = _run(answerer, RecordingBridge(), RecordingScorer())
    assert result.candidate is not None
    accepted = [event for event in answerer.events if event["event"] == "CHAT_COMPLETION_ACCEPTED"]
    assert len(accepted) == 128
    assert all(
        '\n  "response_token" :' in json.loads(event["raw_response_utf8"])["choices"][0]["message"]["content"]
        for event in accepted
    )
    assert all(hashlib.sha256(event["raw_response_utf8"].encode()).hexdigest() == event["raw_response_sha256"] for event in accepted)


@pytest.mark.parametrize("content", [
    '{"response_token":"token-aaaaaaaaaaaaaaaaaaaa","response_token":"token-bbbbbbbbbbbbbbbbbbbb"}',
    '{"response_token":"token-aaaaaaaaaaaaaaaaaaaa","extra":"x"}',
    '{"response_token":"token-cccccccccccccccccccc"}',
])
def test_runner_durable_ledger_rejects_semantic_structured_response_negatives(content: str) -> None:
    answerer, rows = EvidenceAnswerer(), []
    _run(answerer, RecordingBridge(), RecordingScorer(), runner_rows=rows)
    events = json.loads(json.dumps(answerer.events))
    accepted = next(event for event in events if event["event"] == "CHAT_COMPLETION_ACCEPTED")
    raw = json.loads(accepted["raw_response_utf8"])
    raw["choices"][0]["message"]["content"] = content
    accepted["raw_response_utf8"] = canonical_json(raw).decode()
    accepted["raw_response_sha256"] = hashlib.sha256(accepted["raw_response_utf8"].encode()).hexdigest()
    with pytest.raises(RuntimeError):
        _validate_model_event_ledger(events, rows, _deployment())


def test_training_canary_leakage_bit_is_derived_from_heldout_observation() -> None:
    answerer, bridge, scorer = EvidenceAnswerer(), RecordingBridge(), RecordingScorer()
    result = _run(answerer, bridge, scorer)
    assert result.bridge_state_evidence is not None
    public, _ = generate_manifests(SEED)
    # Reuse the runner's observed shape, changing only a heldout sealed answer
    # to a public training canary.  This is an injected-negative check of the
    # observation-derived bit, not a re-run with hidden fixture material.
    observed = []
    for request in answerer.requests:
        phase = request.phase
        observed.append({
            "phase": phase,
            "request": {"prompt": request.prompt},
            "sealed_response": {"answer": "safe"},
        })
    canary = next(iter(training_provenance_canaries(public)))
    next(event for event in observed if event["phase"] == "heldout")["sealed_response"]["answer"] = canary
    overlap = _derive_overlap_observation(
        public,
        observed,
        (),
        result.bridge_state_evidence,
        _metadata().overlap,
        raw_closure_canary_seen=False,
    )
    assert overlap["watermark_detected"] is True
    assert overlap["leak_detected"] is True


@pytest.mark.parametrize("carrier", ["sealed", "accepted_raw"])
def test_training_response_canary_is_observed_as_leakage(carrier: str) -> None:
    public, _ = generate_manifests(SEED)
    canary = next(iter(training_provenance_canaries(public)))
    runner_event = {
        "phase": "training",
        "request": {"prompt": "training input intentionally contains its marker"},
        "sealed_response": {"answer": canary if carrier == "sealed" else "clean"},
    }
    model_events = (
        {
            "event": "CHAT_COMPLETION_ACCEPTED",
            "raw_response_utf8": canary if carrier == "accepted_raw" else "clean",
        },
    )
    overlap = _derive_overlap_observation(
        public,
        (runner_event,),
        model_events,
        {"routing_payload": "clean"},
        _metadata().overlap,
        raw_closure_canary_seen=False,
    )
    assert overlap["watermark_detected"] is True
    assert overlap["leak_detected"] is True


def test_raw_closure_canary_observation_propagates_to_candidate() -> None:
    public, private = generate_manifests(SEED)
    answerer = EvidenceAnswerer()
    exporter = RecordingClosureExporter(watermark_detected=True)
    result = run_diagnostic(
        public,
        private_manifest_commitment=commitment(private),
        answerer=answerer,
        bridge=RecordingBridge(),
        scorer=RecordingScorer(),
        metadata=_metadata(),
        model_event_ledger_provider=lambda: tuple(answerer.events),
        closure_exporter=exporter,
    )
    assert result.candidate is not None
    assert result.candidate["overlap"]["watermark_detected"] is True
    assert result.candidate["overlap"]["leak_detected"] is True
    assert exporter.forbidden_markers == training_provenance_canaries(public)


def test_fixed_rule_replay_derangement_and_post_eval_payload_evidence() -> None:
    result = _run(EvidenceAnswerer(), RecordingBridge(), RecordingScorer())
    assert result.candidate is not None and result.bridge_state_evidence is not None
    for stream in result.bridge_state_evidence["streams"]:
        arms = stream["pre_evaluation"]["arms"]
        assert arms["FULL"]["routing_payload_bytes"] == arms["BINDING_DERANGED_NUMERIC_PLACEBO"]["routing_payload_bytes"]
        assert arms["FULL"]["routing_payload_utf8"] != arms["BINDING_DERANGED_NUMERIC_PLACEBO"]["routing_payload_utf8"]
        assert set(arms["FULL"]) == {"mount_id", "mount_role", "state_sha256", "routing_payload_utf8", "routing_payload_sha256", "routing_payload_bytes", "score_projection_utf8", "score_projection_sha256", "score_projection_bytes"}


def test_post_eval_routing_mutation_is_inconclusive_after_all_calls() -> None:
    result = _run(EvidenceAnswerer(), MutatingEvaluationBridge(), RecordingScorer())
    assert result.candidate is None
    assert result.inconclusive_occurrence is not None
    assert result.inconclusive_occurrence["calls_completed"] == 128


def test_post_call_failure_emits_one_inconclusive_occurrence_without_retry(tmp_path: Path) -> None:
    public, private = generate_manifests(SEED)
    path = tmp_path / "inconclusive.json"
    answerer = EvidenceAnswerer(fail_on=2)
    runner_rows: list[dict] = []
    result = run_diagnostic(public, private_manifest_commitment=commitment(private), answerer=answerer, bridge=RecordingBridge(), scorer=RecordingScorer(), metadata=_metadata(), inconclusive_path=path, event_sink=lambda row: runner_rows.append(dict(row)), model_event_ledger_provider=lambda: tuple(answerer.events), closure_exporter=RecordingClosureExporter())
    assert result.candidate is None
    assert result.inconclusive_occurrence is not None
    assert result.inconclusive_occurrence["calls_completed"] == 1
    assert len(answerer.requests) == 2
    assert json.loads(path.read_text()) == result.inconclusive_occurrence
    assert [row["event"] for row in runner_rows] == [
        "PRE_DISPATCH_READOUT", "COMPLETED_CALL", "PRE_DISPATCH_READOUT"
    ]
    final_pre = runner_rows[-1]
    assert final_pre["request"]["pre_dispatch_receipt_sha256"] is None
    assert _sha(final_pre) not in {
        row.get("pre_dispatch_receipt_sha256") for row in runner_rows
    }


def test_pre_dispatch_row_is_emitted_before_answerer_and_committed_into_request() -> None:
    public, private = generate_manifests(SEED)
    rows: list[dict] = []

    class OrderingAnswerer(EvidenceAnswerer):
        def answer(self, request: ModelRequest) -> ModelReply:
            assert rows and rows[-1]["event"] == "PRE_DISPATCH_READOUT"
            assert request.pre_dispatch_receipt_sha256 == _sha(rows[-1])
            return super().answer(request)

    answerer = OrderingAnswerer(fail_on=2)
    result = run_diagnostic(
        public, private_manifest_commitment=commitment(private), answerer=answerer,
        bridge=RecordingBridge(), scorer=RecordingScorer(), metadata=_metadata(),
        event_sink=lambda row: rows.append(dict(row)),
        model_event_ledger_provider=lambda: tuple(answerer.events),
        closure_exporter=RecordingClosureExporter(),
    )
    assert result.inconclusive_occurrence is not None
    assert [row["event"] for row in rows[:3]] == [
        "PRE_DISPATCH_READOUT", "COMPLETED_CALL", "PRE_DISPATCH_READOUT"
    ]


def test_scorer_failure_and_reply_limit_are_counted() -> None:
    failed = _run(EvidenceAnswerer(), RecordingBridge(), FailingScorer())
    assert failed.inconclusive_occurrence is not None
    assert failed.inconclusive_occurrence["calls_completed"] == 1
    over_limit = _run(EvidenceAnswerer(output_tokens=MAX_OUTPUT_TOKENS + 1), RecordingBridge(), RecordingScorer())
    assert over_limit.inconclusive_occurrence is not None
    assert over_limit.inconclusive_occurrence["calls_completed"] == 1


def test_runner_refuses_malformed_response_token() -> None:
    with pytest.raises(RuntimeError, match="exact DNRD-4S1 form"):
        _validate_reply(ModelReply("not-a-dnrd-token", input_tokens=1, output_tokens=1))


def test_fixed_rule_replay_must_reproduce_payload_and_readouts_before_evaluation() -> None:
    result = _run(EvidenceAnswerer(), NonReproducibleReplayBridge(), RecordingScorer())
    assert result.candidate is None
    assert result.inconclusive_occurrence is not None
    assert result.inconclusive_occurrence["calls_completed"] == 32


def test_pre_first_error_refuses_without_occurrence() -> None:
    public, private = generate_manifests(SEED)
    answerer = EvidenceAnswerer(fail_on=1)
    with pytest.raises(RunnerRefusal, match="pre-first-call"):
        run_diagnostic(public, private_manifest_commitment=commitment(private), answerer=answerer, bridge=RecordingBridge(), scorer=RecordingScorer(), metadata=_metadata(), model_event_ledger_provider=lambda: tuple(answerer.events), closure_exporter=RecordingClosureExporter())


def test_missing_raw_closure_exporter_refuses_before_any_model_call() -> None:
    public, private = generate_manifests(SEED)
    answerer = EvidenceAnswerer()
    with pytest.raises(RunnerRefusal, match="mount-closure exporter"):
        run_diagnostic(
            public,
            private_manifest_commitment=commitment(private),
            answerer=answerer,
            bridge=RecordingBridge(),
            scorer=RecordingScorer(),
            metadata=_metadata(),
            model_event_ledger_provider=lambda: tuple(answerer.events),
        )
    assert answerer.requests == []


def test_hash_bound_subprocess_bridge_requires_canonical_single_line(tmp_path: Path) -> None:
    script = tmp_path / "fake_v2_bridge.py"
    script.write_text(
        """import json, sys
req = json.load(sys.stdin)
payload = req['payload']
if req['operation'] == 'INIT_STREAM':
    stream = payload['stream']
    scores = {context: {route: 0 for route in stream['route_ids']} for context in stream['context_keys']}
    base = {'state_sha256': 'a'*64, 'revision_id': 'genesis', 'lineage_id': 'lineage:' + stream['stream_id'], 'owner_id': 'owner:dnrd:routing', 'immutable': True, 'scores': scores}
    result = {'w0': {**base, 'mount_id': 'mount:w0', 'mount_role': 'W0_ROLLBACK'}, 'w1': {**base, 'mount_id': 'mount:w1', 'mount_role': 'FULL_TRAINABLE'}, 'initialization_receipt_sha256': 'b'*64, 'common_prefix_sha256': 'c'*64, 'equal_genesis_content': True}
elif req['operation'] == 'MATERIALIZE_CONTROL':
    state = dict(payload['state']); state['mount_id'] = 'mount:' + payload['arm']; state['revision_id'] = payload['arm']; state['mount_role'] = 'DERANGED_CONTROL'
    result = {'state': state, 'receipt_sha256': 'd'*64}
else:
    raise SystemExit(2)
sys.stdout.write(json.dumps(result, sort_keys=True, separators=(',', ':')) + '\\n')
""",
        encoding="utf-8",
    )
    digest = hashlib.sha256(script.read_bytes()).hexdigest()
    public, _ = generate_manifests(SEED)
    bridge = SubprocessJsonBridge([sys.executable, str(script)], implementation_path=script, implementation_sha256=digest, config={"fixture": "v1"})
    initial = bridge.initialize(public["streams"][0])
    assert initial.w0.mount_role == "W0_ROLLBACK"
    control = bridge.materialize_control(initial.w1, "stream-0", "BINDING_DERANGED_NUMERIC_PLACEBO", [], public["streams"][0]["matched_derangement"])
    assert control.state.mount_role == "DERANGED_CONTROL"
    script.write_text(script.read_text(encoding="utf-8") + "# drift\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="bytes drifted before invocation"):
        bridge.initialize(public["streams"][0])


def test_subprocess_recovery_rejects_truthy_wire_scalars_without_coercion() -> None:
    """A process response must not turn a string into an observed boolean."""
    payload = canonical_json({"scores": {"context:test": {"route:test": 0}}})
    state = {
        "state_sha256": hashlib.sha256(payload).hexdigest(),
        "revision_id": "revision:test",
        "lineage_id": "lineage:test",
        "owner_id": "owner:test",
        "mount_id": "mount:test",
        "mount_role": "W0_ROLLBACK",
        "immutable": True,
        "scores": {"context:test": {"route:test": 0}},
    }
    result = {
        "state": state,
        "journal_sha256": "a" * 64,
        "recovered": "true",
        "fresh_process": True,
        "process_instance_id": "00000000-0000-4000-8000-000000000001",
        "mount_role": "W0_ROLLBACK",
        "routing_payload_utf8": payload.decode("utf-8"),
        "routing_payload_sha256": hashlib.sha256(payload).hexdigest(),
        "routing_payload_bytes": len(payload),
    }
    bridge = object.__new__(SubprocessJsonBridge)
    bridge._call = lambda _operation, _payload: result  # type: ignore[method-assign]
    input_state = RoutingState(**state)
    with pytest.raises(RuntimeError, match="recovery flags must be exact booleans"):
        bridge.recover(input_state)
    result["recovered"] = True
    result["process_instance_id"] = "a" * 64
    with pytest.raises(RunnerRefusal, match="lowercase UUID"):
        bridge.recover(input_state)


def test_hash_bound_subprocess_scorer_rehashes_before_every_invocation(
    tmp_path: Path,
) -> None:
    script = tmp_path / "fake_scorer.py"
    script.write_text(
        """import json, sys
result = {
    'episode_id': 'episode:fixture',
    'selected_route_id': 'route:fixture',
    'reward': 0,
    'outcome_digest': 'a' * 64,
    'scorer_source_identity': 'b' * 64,
    'scorer_address': '_research/dnrd/scorer.py',
    'role_separation': 'DECLARED_ROLE_SEPARATION_NOT_PROVEN',
}
sys.stdout.write(json.dumps(result, sort_keys=True, separators=(',', ':')) + '\\n')
""",
        encoding="utf-8",
    )
    private = tmp_path / "private.json"
    private.write_bytes(b"{}")
    digest = hashlib.sha256(script.read_bytes()).hexdigest()
    scorer = SubprocessOutcomeScorer(
        [sys.executable, str(script)],
        implementation_path=script,
        implementation_sha256=digest,
        private_manifest_path=private,
    )
    assert scorer.score({"sealed": "fixture"})["reward"] == 0
    script.write_text(script.read_text(encoding="utf-8") + "# drift\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="bytes drifted before invocation"):
        scorer.score({"sealed": "fixture"})
