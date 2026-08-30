"""Focused integration coverage for the bounded G1 micro live slice."""

from __future__ import annotations

import base64
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Any, Callable, Mapping

import pytest

from hswm.experiments import continual_live as live
from hswm.experiments import g1_micro
from hswm.experiments.g1_micro_dgx import make_runtime_binding_record
from hswm.selfmod.contracts import canonical_json_bytes, canonical_sha256


_PROTOCOL = (
    Path(__file__).parents[1]
    / "_research/causal_composition/preregistrations/g1_micro_exploratory_2026-08-30"
    / "protocol.v1.json"
)
_OPAQUE_PROTOCOL = (
    Path(__file__).parents[1]
    / "_research/causal_composition/preregistrations/"
    "g1_opaque_identifiability_pilot_2026-08-30/protocol.v1.json"
)
_OPAQUE_REVEAL = Path("/tmp/hswm-g1-opaque-evaluator-reveal-v1.json")
_SNAPSHOT_MANIFEST = (
    Path(__file__).parents[1]
    / "_research/dgx_mi2/preregistrations/"
    "hswm-dnrd5-qcase024-mi-2-launch-crossed-v1-2026-08-29/"
    "identities/ASYNC_DISABLED/model_snapshot_manifest_sha256.json"
)


class _VaryingMicroBackend:
    """A stateless semantic double whose OpenAI envelopes vary per call."""

    def __init__(
        self, *, live_identity: bool = False, force_no_credit_for_active: bool = False
    ) -> None:
        self._preflight_counts: dict[str, int] = {}
        self.response_sha256s: list[str] = []
        self.complete_calls = 0
        self.tokenize_calls = 0
        self.live_identity = live_identity
        self.force_no_credit_for_active = force_no_credit_for_active
        self.model = "qwen3.6-35b-a3b" if live_identity else "g1-micro-fixture"

    @property
    def identity(self) -> Mapping[str, Any]:
        identity = {
            "adapter": "g1-micro-scripted/v1",
            "enable_thinking": False,
            "expected_max_model_len": 32_768,
            "model": self.model,
            "response_format_mode": live.STRUCTURED_OUTPUT_MODE,
            "seed": 0,
            "temperature": 0.0,
            "token_preflight_mode": live.TOKEN_PREFLIGHT_MODE,
            "token_preflight_transport_trust": "scripted-test-double",
            "top_p": 1.0,
        }
        if self.live_identity:
            identity.update(
                {
                    "adapter": "openai-compatible-stateless/v1",
                    "endpoint": "http://127.0.0.1:18080",
                    "max_response_bytes": 4_000_000,
                    "retry_count": 0,
                    "timeout_seconds": 120.0,
                    "token_preflight_transport_trust": (
                        "loopback-without-api-key-middleware"
                    ),
                }
            )
        return identity

    def tokenize(
        self,
        *,
        raw_request: bytes,
        source_chat_request_sha256: str,
        max_output_tokens: int,
        request_id: str,
        response_observer: Callable[[bytes, bytes, int | None, bool], None],
    ) -> live.TokenPreflightReceipt:
        del request_id
        self.tokenize_calls += 1
        count = max(1, len(raw_request) // 64)
        raw_response = canonical_json_bytes(
            {
                "count": count,
                "max_model_len": 32_768,
                "token_strs": None,
                "tokens": list(range(count)),
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
    def _choice(payload: Mapping[str, Any], operator: str) -> str:
        value = int(payload.get("input", payload.get("fresh_input")))
        operand = int(payload["operand"])
        result = value + operand if operator == "ADD_THREE" else value * operand
        return f"v_{result:04d}"

    def complete(
        self,
        *,
        raw_request: bytes,
        request_id: str,
        response_observer: Callable[[bytes, bytes], None],
    ) -> live.ModelCompletion:
        del request_id
        request = json.loads(raw_request)
        payload = json.loads(request["messages"][-1]["content"])
        if "sealed_trajectory" in payload:
            operation = "propose_revision"
        elif "compiled_disposition" in payload:
            operation = "fresh_behavior_probe"
        elif "input" in payload:
            operation = "pre_outcome_trajectory"
        else:  # pragma: no cover - test double guards the public protocol
            raise AssertionError("unrecognized micro payload")
        if operation == "pre_outcome_trajectory":
            # The frozen protocol has ADD_THREE hidden, so this yields false feedback.
            text = json.dumps(
                {"choice": self._choice(payload, "MULTIPLY_THREE")},
                separators=(",", ":"),
            )
        elif operation == "propose_revision":
            # Correctness feedback identifies the other operator from the trajectory.
            operator = "MULTIPLY_THREE" if (
                self.force_no_credit_for_active
                or payload["feedback"]["choice_was_correct"]
            ) else "ADD_THREE"
            text = json.dumps(
                {"operation": operator, "rationale": "binary feedback selects the operator"},
                separators=(",", ":"),
            )
        elif operation == "fresh_behavior_probe":
            rule = payload["compiled_disposition"]["rule"]
            # Empty readsets deliberately default to MULTIPLY; only admitted state wins.
            operator = "MULTIPLY_THREE" if rule is None else rule["operator"]
            text = json.dumps(
                {"choice": self._choice(payload, operator)}, separators=(",", ":")
            )
        else:  # pragma: no cover - test double guards the public protocol
            raise AssertionError(operation)

        self.complete_calls += 1
        input_tokens = self._preflight_counts[sha256(raw_request).hexdigest()]
        output_tokens = max(1, len(text.encode("utf-8")) // 4)
        # `id` has no semantic role but makes each retained raw response byte-distinct.
        raw_response = canonical_json_bytes(
            {
                "choices": [{"finish_reason": "stop", "message": {"content": text}}],
                "id": f"fixture-call-{self.complete_calls}",
                "model": self.model,
                "usage": {
                    "completion_tokens": output_tokens,
                    "prompt_tokens": input_tokens,
                    "total_tokens": input_tokens + output_tokens,
                },
            }
        )
        response_observer(raw_request, raw_response)
        response_sha = sha256(raw_response).hexdigest()
        self.response_sha256s.append(response_sha)
        return live.ModelCompletion(
            text=text,
            raw_request_json=raw_request.decode("utf-8"),
            raw_response_json=raw_response.decode("utf-8"),
            request_sha256=sha256(raw_request).hexdigest(),
            response_sha256=response_sha,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=0,
            usage_reported=True,
        )


class _FailSecondCompletionBackend(_VaryingMicroBackend):
    def complete(self, **kwargs: Any) -> live.ModelCompletion:
        if self.complete_calls == 1:
            raise RuntimeError("intentional second-call failure")
        return super().complete(**kwargs)


class _OpaquePilotBackend(_VaryingMicroBackend):
    """Semantic double for the opaque pilot: state, not candidate position, wins."""

    def __init__(self, correct_by_cue: Mapping[str, str]) -> None:
        super().__init__()
        self.correct_by_cue = dict(correct_by_cue)

    def complete(
        self,
        *,
        raw_request: bytes,
        request_id: str,
        response_observer: Callable[[bytes, bytes], None],
    ) -> live.ModelCompletion:
        del request_id
        request = json.loads(raw_request)
        payload = json.loads(request["messages"][-1]["content"])
        codes = list(payload["action_codes"])
        correct = self.correct_by_cue[payload["cue"]]
        if "feedback_correct" in payload:
            trajectory = payload["trajectory_action_code"]
            choice = trajectory if payload["feedback_correct"] else next(
                code for code in codes if code != trajectory
            )
        elif "compiled_disposition" in payload:
            rule = payload["compiled_disposition"]["rule"]
            choice = None if rule is None else rule["action_code"]
            if choice is None:
                choice = next(code for code in codes if code != correct)
        else:
            # The pre-outcome trajectory is deliberately wrong; outcome feedback
            # is the only route by which ACTIVE can learn the correct code.
            choice = next(code for code in codes if code != correct)
        text = json.dumps({"action_code": choice}, separators=(",", ":"))
        self.complete_calls += 1
        input_tokens = self._preflight_counts[sha256(raw_request).hexdigest()]
        raw_response = canonical_json_bytes(
            {
                "choices": [{"finish_reason": "stop", "message": {"content": text}}],
                "id": f"opaque-fixture-{self.complete_calls}",
                "model": self.model,
                "usage": {
                    "completion_tokens": 1,
                    "prompt_tokens": input_tokens,
                    "total_tokens": input_tokens + 1,
                },
            }
        )
        response_observer(raw_request, raw_response)
        response_sha = sha256(raw_response).hexdigest()
        self.response_sha256s.append(response_sha)
        return live.ModelCompletion(
            text=text,
            raw_request_json=raw_request.decode("utf-8"),
            raw_response_json=raw_response.decode("utf-8"),
            request_sha256=sha256(raw_request).hexdigest(),
            response_sha256=response_sha,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=1,
            latency_ms=0,
            usage_reported=True,
        )


class _NonadherentOpaquePilotBackend(_OpaquePilotBackend):
    """Returns schema-valid but credit-rule-invalid proposals; the pilot must finish."""

    def complete(
        self,
        *,
        raw_request: bytes,
        request_id: str,
        response_observer: Callable[[bytes, bytes], None],
    ) -> live.ModelCompletion:
        request = json.loads(raw_request)
        payload = json.loads(request["messages"][-1]["content"])
        if "feedback_correct" not in payload:
            return super().complete(
                raw_request=raw_request,
                request_id=request_id,
                response_observer=response_observer,
            )
        # Deliberately invert the precommitted binary rule for both proposal
        # calls while keeping the response schema valid.
        trajectory = payload["trajectory_action_code"]
        choice = (
            next(code for code in payload["action_codes"] if code != trajectory)
            if payload["feedback_correct"]
            else trajectory
        )
        text = json.dumps({"action_code": choice}, separators=(",", ":"))
        self.complete_calls += 1
        input_tokens = self._preflight_counts[sha256(raw_request).hexdigest()]
        raw_response = canonical_json_bytes(
            {
                "choices": [{"finish_reason": "stop", "message": {"content": text}}],
                "id": f"opaque-nonadherent-{self.complete_calls}",
                "model": self.model,
                "usage": {
                    "completion_tokens": 1,
                    "prompt_tokens": input_tokens,
                    "total_tokens": input_tokens + 1,
                },
            }
        )
        response_observer(raw_request, raw_response)
        response_sha = sha256(raw_response).hexdigest()
        self.response_sha256s.append(response_sha)
        return live.ModelCompletion(
            text=text,
            raw_request_json=raw_request.decode("utf-8"),
            raw_response_json=raw_response.decode("utf-8"),
            request_sha256=sha256(raw_request).hexdigest(),
            response_sha256=response_sha,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=1,
            latency_ms=0,
            usage_reported=True,
        )


def _protocol(tmp_path: Path) -> tuple[dict[str, Any], str, Path]:
    frozen, _ = g1_micro.load_protocol(_PROTOCOL)
    protocol = deepcopy(frozen)
    registry = tmp_path / "durable" / "consumption.json"
    registry.parent.mkdir()
    protocol["consumption_registry"]["path"] = str(registry)
    return protocol, canonical_sha256(protocol), registry


def _opaque_protocol(
    tmp_path: Path,
) -> tuple[dict[str, Any], str, Path, Path, dict[str, Any]]:
    protocol, _ = g1_micro.load_protocol(_OPAQUE_PROTOCOL)
    protocol = deepcopy(protocol)
    registry = tmp_path / "durable" / "opaque-once"
    registry.parent.mkdir(parents=True)
    protocol["consumption_registry"]["path"] = str(registry)
    protocol_sha = canonical_sha256(protocol)
    reveal = json.loads(_OPAQUE_REVEAL.read_bytes())
    reveal["protocol_canonical_sha256"] = protocol_sha
    reveal["reveal_commitment_root"] = protocol["evaluator_reveal_contract"][
        "reveal_commitment_root"
    ]
    reveal_path = tmp_path / "evaluator-reveal.json"
    reveal_path.write_bytes(canonical_json_bytes(reveal))
    return protocol, protocol_sha, registry, reveal_path, reveal


def _opaque_tokenizer_receipt(protocol: Mapping[str, Any]) -> dict[str, Any]:
    """Exact public projection of the pre-freeze tokenizer measurement."""
    binding = protocol["tokenizer_binding"]
    receipt: dict[str, Any] = {
        "schema_version": "hswm-g1-opaque-offline-tokenizer-receipt/v1",
        "container_image": binding["container_image"],
        "container_image_id": binding["container_image_id"],
        "model_repository": binding["model_repository"],
        "model_revision": binding["model_revision"],
        "snapshot_manifest_sha256": binding["snapshot_manifest_sha256"],
        "encoding": deepcopy(binding["encoding"]),
        "tokenizers_version": binding["tokenizers_version"],
        "transformers_version": binding["transformers_version"],
        "episodes": [
            {
                "episode_uid": episode["episode_uid"],
                "action_codes": deepcopy(episode["action_codes"]),
                "token_ids": deepcopy(episode["token_ids"]),
                "token_counts": deepcopy(episode["token_counts"]),
            }
            for episode in binding["episodes"]
        ],
    }
    receipt["receipt_sha256"] = sha256(canonical_json_bytes(receipt)).hexdigest()
    return receipt


def _runtime_binding(protocol: Mapping[str, Any], protocol_sha: str) -> dict[str, Any]:
    binding = protocol["live_binding"]
    server_argv = g1_micro.expected_dgx_server_argv(protocol)
    container_id = "1" * 64
    started_at = "2026-08-30T00:00:00Z"
    image_raw = canonical_json_bytes(
        [{"Id": binding["container_image_id"], "RepoDigests": [binding["container_image"]]}]
    )
    container_raw = canonical_json_bytes(
        [
            {
                "Config": {"Cmd": server_argv, "Image": binding["container_image"]},
                "HostConfig": {
                    "IpcMode": "private",
                    "NetworkMode": "bridge",
                    "PortBindings": {
                        "8000/tcp": [{"HostIp": "127.0.0.1", "HostPort": "18080"}]
                    },
                },
                "Id": container_id,
                "Image": binding["container_image_id"],
                "State": {"StartedAt": started_at},
            }
        ]
    )
    metrics = (
        b"vllm:num_requests_running 0\n"
        b"vllm:request_success_total 0\n"
        b"vllm:prefix_cache_hits_total 0\n"
        b"vllm:prefix_cache_queries_total 0\n"
    )
    root = Path(__file__).parents[1]
    tracked = {
        path: sha256((root / path).read_bytes()).hexdigest()
        for path in g1_micro.dgx_tracked_source_paths(protocol)
    }
    protocol_raw = canonical_json_bytes(protocol)
    protocol_source_path = (
        "_research/causal_composition/preregistrations/"
        "g1_opaque_identifiability_pilot_2026-08-30/protocol.v1.json"
        if protocol["schema_version"] == g1_micro.OPAQUE_PILOT_PROTOCOL
        else "_research/causal_composition/preregistrations/"
        "g1_micro_exploratory_2026-08-30/protocol.v1.json"
    )
    tracked[protocol_source_path] = sha256(protocol_raw).hexdigest()
    return make_runtime_binding_record(
        protocol=protocol,
        protocol_sha256=protocol_sha,
        source_commit="5" * 40,
        source_tree="6" * 40,
        source_manifest=g1_micro._source_manifest(),
        tracked_source_sha256=tracked,
        protocol_file_sha256=sha256(protocol_raw).hexdigest(),
        container_id_sha256=sha256(container_id.encode()).hexdigest(),
        container_start_sha256=sha256(started_at.encode()).hexdigest(),
        container_inspect_raw=container_raw,
        image_inspect_raw=image_raw,
        gpu_observation_raw=f"{binding['gpu_uuid']}, {binding['gpu_name']}\n".encode(),
        snapshot_manifest_raw=_SNAPSHOT_MANIFEST.read_bytes(),
        startup_metrics_raw=metrics,
        startup_models_raw=canonical_json_bytes(
            {"data": [{"id": binding["served_model"]}]}
        ),
        startup_version_raw=canonical_json_bytes({"version": binding["vllm_version"]}),
    )


def test_eight_live_calls_are_semantic_not_byte_exact_and_verify(tmp_path: Path) -> None:
    protocol, protocol_sha, registry = _protocol(tmp_path)
    backend = _VaryingMicroBackend()
    output = tmp_path / "g1-micro"

    bundle = g1_micro._run_exploratory_slice_with_backend(
        backend=backend,
        protocol=protocol,
        protocol_sha256=protocol_sha,
        output_dir=output,
        execution_registry_path=registry,
    )

    assert backend.complete_calls == 8
    assert backend.tokenize_calls == 8
    assert len(set(backend.response_sha256s)) == 8
    assert bundle["completion_call_count"] == 8
    assert bundle["tokenize_post_count"] == 8
    assert bundle["total_http_post_count"] == 16
    assert bundle["terminal"] == (
        "EXPLORATORY_OBSERVATION_RECORDED_NO_EFFICACY_INFERENCE"
    )
    assert bundle["descriptive_five_branch_pattern_observed"] is True
    assert bundle["sham_feedback_contrast"] == (
        "INFORMATIVE_DIFFERENT_FEEDBACK_SINGLE_CASE_ONLY"
    )
    registry_seal = json.loads(registry.read_bytes())
    assert registry_seal["payload"]["status"] == "COMPLETED_NO_RERUN"
    assert bundle["byte_exact_model_response_required"] is False
    assert bundle["probes"]["ACTIVE"]["payload"]["correct"] is True
    assert bundle["probes"]["OUTCOME_INDEPENDENT_SHAM"]["payload"]["correct"] is False
    assert bundle["probes"]["NO_UPDATE"]["payload"]["correct"] is False
    assert bundle["probes"]["REMOVE"]["payload"]["correct"] is False
    assert bundle["probes"]["RESTORE"]["payload"]["correct"] is True
    assert (
        bundle["probes"]["ACTIVE"]["payload"]["state_sha256"]
        == bundle["probes"]["RESTORE"]["payload"]["state_sha256"]
    )
    assert g1_micro.verify_bundle_file(output / "result.json") == {
        "bundle_sha256": bundle["bundle_sha256"],
        "exact_state_restore": True,
        "provider_response_byte_stability_required": False,
        "terminal": "EXPLORATORY_OBSERVATION_RECORDED_NO_EFFICACY_INFERENCE",
        "verification": "VALID_LOCAL_STRUCTURAL_CONSISTENCY",
    }

    tampered = deepcopy(bundle)
    tampered["probes"]["REMOVE"]["payload"]["choice"] = tampered["probes"]["ACTIVE"][
        "payload"
    ]["choice"]
    unsigned = dict(tampered)
    unsigned.pop("bundle_sha256")
    tampered["bundle_sha256"] = canonical_sha256(unsigned)
    with pytest.raises(g1_micro.G1MicroError, match="local record digest mismatch"):
        g1_micro.verify_exploratory_bundle(tampered, base_dir=output)


def test_consumed_local_permit_cannot_be_replayed(tmp_path: Path) -> None:
    protocol, protocol_sha, registry = _protocol(tmp_path)
    output = tmp_path / "g1-micro"
    bundle = g1_micro._run_exploratory_slice_with_backend(
        backend=_VaryingMicroBackend(),
        protocol=protocol,
        protocol_sha256=protocol_sha,
        output_dir=output,
        execution_registry_path=registry,
    )
    admission = bundle["local_admissions"]["ACTIVE"]
    assert admission is not None
    store = g1_micro.G1MicroStore(output / "active.sqlite3")

    with pytest.raises(g1_micro.G1MicroError, match="already consumed"):
        store.admit(
            permit=admission["permit"],
            proposal=bundle["proposals"]["ACTIVE"],
            feedback=bundle["outcome"],
            credit=bundle["credit"]["ACTIVE"],
            successor_state=admission["successor_state"],
        )


def test_partial_live_failure_is_sealed_and_cannot_be_refilled(tmp_path: Path) -> None:
    protocol, protocol_sha, registry = _protocol(tmp_path)
    output = tmp_path / "failed-g1-micro"

    with pytest.raises(RuntimeError, match="intentional second-call failure"):
        g1_micro._run_exploratory_slice_with_backend(
            backend=_FailSecondCompletionBackend(),
            protocol=protocol,
            protocol_sha256=protocol_sha,
            output_dir=output,
            execution_registry_path=registry,
        )

    abort = json.loads((output / "abort.json").read_bytes())
    assert abort["payload"]["terminal"] == "INCONCLUSIVE_MEASUREMENT_NOT_READY"
    assert abort["payload"]["retry_or_refill_permitted"] is False
    assert abort["payload"]["journal"]["completed_calls"] == 1
    assert abort["payload"]["journal"]["tokenize_posts"] == 2
    seal = json.loads(registry.read_bytes())
    assert seal["payload"]["status"] == "ABORTED_NO_RERUN"

    with pytest.raises(g1_micro.G1MicroError, match="refusing to overwrite"):
        g1_micro._run_exploratory_slice_with_backend(
            backend=_VaryingMicroBackend(),
            protocol=protocol,
            protocol_sha256=protocol_sha,
            output_dir=tmp_path / "refill-attempt",
            execution_registry_path=registry,
        )


def test_no_credit_aborts_before_probes_and_seals_no_refill(tmp_path: Path) -> None:
    protocol, protocol_sha, registry = _protocol(tmp_path)
    backend = _VaryingMicroBackend(force_no_credit_for_active=True)
    output = tmp_path / "no-credit"

    with pytest.raises(g1_micro.G1MicroError, match="precommitted credit rule"):
        g1_micro._run_exploratory_slice_with_backend(
            backend=backend,
            protocol=protocol,
            protocol_sha256=protocol_sha,
            output_dir=output,
            execution_registry_path=registry,
        )

    assert backend.complete_calls == 3
    assert backend.tokenize_calls == 3
    assert json.loads(registry.read_bytes())["payload"]["status"] == "ABORTED_NO_RERUN"
    assert json.loads((output / "abort.json").read_bytes())["payload"][
        "retry_or_refill_permitted"
    ] is False

def test_cli_preflight_is_zero_post_and_creates_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    protocol, _, registry = _protocol(tmp_path)
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_bytes(canonical_json_bytes(protocol))
    output_root = tmp_path / "wrapper-output"
    output_root.mkdir()
    output = output_root / "fresh-run"
    monkeypatch.setenv("HSWM_OUTPUT_ROOT", str(output_root))

    assert g1_micro.main(
        [
            "--protocol",
            str(protocol_path),
            "--endpoint",
            "http://127.0.0.1:18080",
            "--model",
            "qwen3.6-35b-a3b",
            "--output-dir",
            str(output),
            "--execution-registry",
            str(registry),
            "--preflight-only",
        ]
    ) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["network_calls"] == 0
    assert receipt["completion_post_cap"] == 8
    assert receipt["tokenize_post_cap"] == 8
    assert receipt["total_http_post_cap"] == 16
    assert not output.exists()
    assert not registry.exists()


def test_backend_injected_producer_refuses_protocol_drift_before_claim(
    tmp_path: Path,
) -> None:
    protocol, _, registry = _protocol(tmp_path)
    protocol["provider_call_cap"] = 9
    backend = _VaryingMicroBackend()

    with pytest.raises(g1_micro.G1MicroError, match="eight-call ceiling"):
        g1_micro._run_exploratory_slice_with_backend(
            backend=backend,
            protocol=protocol,
            protocol_sha256=canonical_sha256(protocol),
            output_dir=tmp_path / "protocol-drift",
            execution_registry_path=registry,
        )

    assert backend.complete_calls == 0
    assert backend.tokenize_calls == 0
    assert not registry.exists()


def test_retained_store_semantics_are_checked_not_only_file_hashes(
    tmp_path: Path,
) -> None:
    protocol, protocol_sha, registry = _protocol(tmp_path)
    output = tmp_path / "g1-micro"
    bundle = g1_micro._run_exploratory_slice_with_backend(
        backend=_VaryingMicroBackend(),
        protocol=protocol,
        protocol_sha256=protocol_sha,
        output_dir=output,
        execution_registry_path=registry,
    )
    with sqlite3.connect(output / "active.sqlite3") as connection:
        connection.execute("UPDATE g1_active SET generation=99 WHERE singleton=1")
    tampered = deepcopy(bundle)
    tampered["state_store_artifacts"] = g1_micro._file_manifest(
        (output / "active.sqlite3", output / "sham.sqlite3")
    )
    unsigned = dict(tampered)
    unsigned.pop("bundle_sha256")
    tampered["bundle_sha256"] = canonical_sha256(unsigned)

    with pytest.raises(g1_micro.G1MicroError, match="retained state stores differ"):
        g1_micro.verify_exploratory_bundle(tampered, base_dir=output)


def test_local_replay_does_not_depend_on_future_checkout_source_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    protocol, protocol_sha, registry = _protocol(tmp_path)
    output = tmp_path / "g1-micro"
    bundle = g1_micro._run_exploratory_slice_with_backend(
        backend=_VaryingMicroBackend(),
        protocol=protocol,
        protocol_sha256=protocol_sha,
        output_dir=output,
        execution_registry_path=registry,
    )
    monkeypatch.setattr(
        g1_micro,
        "_source_manifest",
        lambda: {name: "f" * 64 for name in bundle["source_manifest"]},
    )

    assert g1_micro.verify_bundle_file(output / "result.json")["bundle_sha256"] == (
        bundle["bundle_sha256"]
    )


def test_official_entrypoint_binds_protocol_registry_and_loopback_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    protocol, protocol_sha, registry = _protocol(tmp_path)
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_bytes(canonical_json_bytes(protocol))
    output_root = tmp_path / "wrapper-output"
    output_root.mkdir()
    output = output_root / "live-shaped-run"
    backend = _VaryingMicroBackend(live_identity=True)
    runtime_binding_path = tmp_path / "runtime-binding.json"
    runtime_binding_path.write_bytes(
        canonical_json_bytes(_runtime_binding(protocol, protocol_sha))
    )
    monkeypatch.setenv("HSWM_OUTPUT_ROOT", str(output_root))
    monkeypatch.setattr(g1_micro, "OpenAICompatibleBackend", lambda config: backend)

    bundle = g1_micro.run_exploratory_slice(
        protocol_path=protocol_path,
        endpoint="http://127.0.0.1:18080",
        model="qwen3.6-35b-a3b",
        expected_max_model_len=32_768,
        output_dir=output,
        execution_registry_path=registry,
        runtime_binding_path=runtime_binding_path,
    )
    verified = g1_micro.verify_frozen_execution_files(
        bundle_path=output / "result.json",
        protocol_path=protocol_path,
        execution_registry_path=registry,
    )

    assert verified["bundle_sha256"] == bundle["bundle_sha256"]
    assert verified["verification"] == "VALID_LOCAL_PROTOCOL_REGISTRY_BACKEND_BINDING"
    assert verified["runtime_image_identity_verified"] is True


def test_opaque_official_entrypoint_carries_runtime_binding_to_frozen_verifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    protocol, protocol_sha, registry, reveal_path, reveal = _opaque_protocol(tmp_path)
    protocol_path = _write_opaque_protocol(tmp_path, protocol)
    output_root = tmp_path / "wrapper-output"
    output_root.mkdir()
    output = output_root / "opaque-live-run"
    runtime = _runtime_binding(protocol, protocol_sha)
    runtime_path = tmp_path / "runtime-binding.json"
    runtime_path.write_bytes(canonical_json_bytes(runtime))
    backend = _OpaquePilotBackend(
        {
            episode["cue"]: secret["correct_action_code"]
            for episode, secret in zip(protocol["episodes"], reveal["episodes"], strict=True)
        }
    )
    monkeypatch.setenv("HSWM_OUTPUT_ROOT", str(output_root))
    monkeypatch.setattr(g1_micro, "OpenAICompatibleBackend", lambda config: backend)

    bundle = g1_micro.run_exploratory_slice(
        protocol_path=protocol_path,
        endpoint="http://127.0.0.1:18080",
        model="qwen3.6-35b-a3b",
        expected_max_model_len=32_768,
        output_dir=output,
        execution_registry_path=registry,
        runtime_binding_path=runtime_path,
        evaluator_reveal_path=reveal_path,
        tokenizer_receipt=_opaque_tokenizer_receipt(protocol),
    )
    verified = g1_micro.verify_frozen_execution_files(
        bundle_path=output / "result.json",
        protocol_path=protocol_path,
        execution_registry_path=registry,
    )

    assert bundle["runtime_binding"] == runtime
    assert verified["runtime_image_identity_verified"] is True


def test_completed_journal_rejects_an_unattributed_extra_row(tmp_path: Path) -> None:
    protocol, protocol_sha, registry = _protocol(tmp_path)
    output = tmp_path / "g1-micro"
    bundle = g1_micro._run_exploratory_slice_with_backend(
        backend=_VaryingMicroBackend(),
        protocol=protocol,
        protocol_sha256=protocol_sha,
        output_dir=output,
        execution_registry_path=registry,
    )
    ledger = output / "attempt_ledger.jsonl"
    with ledger.open("ab") as handle:
        handle.write(canonical_json_bytes({"event": "unattributed"}) + b"\n")
    tampered = deepcopy(bundle)
    tampered["journal"] = g1_micro._journal_manifest(ledger)
    unsigned = dict(tampered)
    unsigned.pop("bundle_sha256")
    tampered["bundle_sha256"] = canonical_sha256(unsigned)

    assert tampered["journal"]["all_rows_accounted"] is False
    with pytest.raises(g1_micro.G1MicroError, match="eight-call chronology"):
        g1_micro.verify_exploratory_bundle(tampered, base_dir=output)


def test_completed_journal_reconstructs_token_receipt_digest(tmp_path: Path) -> None:
    protocol, protocol_sha, registry = _protocol(tmp_path)
    output = tmp_path / "g1-micro"
    bundle = g1_micro._run_exploratory_slice_with_backend(
        backend=_VaryingMicroBackend(),
        protocol=protocol,
        protocol_sha256=protocol_sha,
        output_dir=output,
        execution_registry_path=registry,
    )
    ledger = output / "attempt_ledger.jsonl"
    rows = [json.loads(line) for line in ledger.read_bytes().splitlines()]
    accepted = next(row for row in rows if row["event"] == "tokenize_accepted")
    accepted["token_preflight"]["receipt_sha256"] = "0" * 64
    ledger.write_bytes(b"\n".join(canonical_json_bytes(row) for row in rows) + b"\n")
    tampered = deepcopy(bundle)
    tampered["journal"] = g1_micro._journal_manifest(ledger)
    unsigned = dict(tampered)
    unsigned.pop("bundle_sha256")
    tampered["bundle_sha256"] = canonical_sha256(unsigned)

    assert tampered["journal"]["raw_preimages_valid"] is False
    with pytest.raises(g1_micro.G1MicroError, match="eight-call chronology"):
        g1_micro.verify_exploratory_bundle(tampered, base_dir=output)


def test_opaque_protocol_rejects_threshold_and_public_commitment_drift(
    tmp_path: Path,
) -> None:
    protocol, _, _, _, _ = _opaque_protocol(tmp_path)
    protocol["analysis"]["identifiability_observed_rule"]["delta_state_min"] = 0.0
    path = tmp_path / "threshold-drift.json"
    path.write_bytes(canonical_json_bytes(protocol))
    with pytest.raises(g1_micro.G1MicroError, match="opaque pilot"):
        g1_micro.load_protocol(path)

    protocol, _, _, _, _ = _opaque_protocol(tmp_path / "second")
    protocol["episodes"][0]["evaluator_commitment_sha256"] = "0" * 64
    path = tmp_path / "commitment-drift.json"
    path.write_bytes(canonical_json_bytes(protocol))
    with pytest.raises(g1_micro.G1MicroError, match="opaque pilot"):
        g1_micro.load_protocol(path)


def test_opaque_pilot_closes_sixty_four_calls_and_exact_reveal_start_seal(
    tmp_path: Path,
) -> None:
    protocol, protocol_sha, registry, reveal_path, reveal = _opaque_protocol(tmp_path)
    backend = _OpaquePilotBackend(
        {
            episode["cue"]: secret["correct_action_code"]
            for episode, secret in zip(protocol["episodes"], reveal["episodes"], strict=True)
        }
    )
    output = tmp_path / "opaque-output"
    bundle = g1_micro.run_opaque_identifiability_pilot_with_backend(
        backend=backend,
        protocol=protocol,
        protocol_sha256=protocol_sha,
        output_dir=output,
        execution_registry_path=registry,
        evaluator_reveal_path=reveal_path,
        tokenizer_receipt=_opaque_tokenizer_receipt(protocol),
    )

    assert backend.complete_calls == 64
    assert backend.tokenize_calls == 64
    assert bundle["total_completion_posts"] == 64
    assert bundle["total_tokenize_posts"] == 64
    assert bundle["total_http_posts"] == 128
    assert bundle["metrics"]["branch_correct_counts"] == {
        "ACTIVE": 8,
        "FORCED_OPPOSITE_FEEDBACK": 0,
        "NO_UPDATE": 0,
        "REMOVE": 0,
        "RESTORE": 8,
    }
    assert all(
        episode["dispositions"][branch]["credit"]["payload"]["decision"]
        == "CREDIT"
        and episode["dispositions"][branch]["admission"] is not None
        for episode in bundle["episodes"]
        for branch in ("ACTIVE", "FORCED_OPPOSITE_FEEDBACK")
    )
    assert sum(
        episode["state_interventions"]["REMOVE"] is not None
        and episode["state_interventions"]["RESTORE"] is not None
        for episode in bundle["episodes"]
    ) == 8
    assert bundle["terminal"] == "PILOT_COMPLETE_IDENTIFIABILITY_OBSERVED_NO_EFFICACY_INFERENCE"
    first_interventions = bundle["episodes"][0]["state_interventions"]
    assert first_interventions["REMOVE"]["payload"]["operation"] == "REMOVE_TO_GENESIS"
    assert first_interventions["RESTORE"]["payload"]["operation"] == "RESTORE_ACTIVE_SNAPSHOT"
    assert first_interventions["REMOVE"]["payload"]["resulting_state_sha256"] == (
        first_interventions["RESTORE"]["payload"]["base_state_sha256"]
    )
    assert first_interventions["RESTORE"]["payload"]["resulting_state_sha256"] == (
        first_interventions["REMOVE"]["payload"]["base_state_sha256"]
    )
    seal = json.loads(registry.read_bytes())
    assert seal["payload"]["status"] == "COMPLETED_NO_RERUN"
    start = seal["payload"]["start"]
    assert start["payload"]["evaluator_reveal_sha256"] == sha256(
        reveal_path.read_bytes()
    ).hexdigest()
    assert bundle["evaluator_reveal"]["sha256"] == start["payload"][
        "evaluator_reveal_sha256"
    ]
    verified = g1_micro.verify_frozen_execution_files(
        bundle_path=output / "result.json",
        protocol_path=_write_opaque_protocol(tmp_path, protocol),
        execution_registry_path=registry,
    )
    assert verified["verification"] == "VALID_LOCAL_OPAQUE_PROTOCOL_REVEAL_REGISTRY_BINDING"


def test_opaque_pilot_rejects_tampered_tokenizer_receipt_before_start(
    tmp_path: Path,
) -> None:
    protocol, protocol_sha, registry, reveal_path, reveal = _opaque_protocol(tmp_path)
    backend = _OpaquePilotBackend(
        {
            episode["cue"]: secret["correct_action_code"]
            for episode, secret in zip(protocol["episodes"], reveal["episodes"], strict=True)
        }
    )
    receipt = _opaque_tokenizer_receipt(protocol)
    receipt["receipt_sha256"] = "0" * 64
    with pytest.raises(g1_micro.G1MicroError, match="tokenizer receipt"):
        g1_micro.run_opaque_identifiability_pilot_with_backend(
            backend=backend,
            protocol=protocol,
            protocol_sha256=protocol_sha,
            output_dir=tmp_path / "opaque-output",
            execution_registry_path=registry,
            evaluator_reveal_path=reveal_path,
            tokenizer_receipt=receipt,
        )
    assert backend.complete_calls == 0
    assert not registry.exists()


def test_opaque_pilot_rejects_tokenizer_pin_or_episode_binding_drift_before_start(
    tmp_path: Path,
) -> None:
    protocol, protocol_sha, registry, reveal_path, reveal = _opaque_protocol(tmp_path)
    backend = _OpaquePilotBackend(
        {
            episode["cue"]: secret["correct_action_code"]
            for episode, secret in zip(protocol["episodes"], reveal["episodes"], strict=True)
        }
    )
    receipt = _opaque_tokenizer_receipt(protocol)
    receipt["container_image_id"] = "sha256:" + "0" * 64
    unsigned = dict(receipt)
    unsigned.pop("receipt_sha256")
    receipt["receipt_sha256"] = sha256(canonical_json_bytes(unsigned)).hexdigest()
    with pytest.raises(g1_micro.G1MicroError, match="tokenizer receipt"):
        g1_micro.run_opaque_identifiability_pilot_with_backend(
            backend=backend,
            protocol=protocol,
            protocol_sha256=protocol_sha,
            output_dir=tmp_path / "opaque-output",
            execution_registry_path=registry,
            evaluator_reveal_path=reveal_path,
            tokenizer_receipt=receipt,
        )
    assert backend.complete_calls == 0
    assert not registry.exists()


def test_opaque_pilot_records_nonadherent_proposals_without_selective_abort(
    tmp_path: Path,
) -> None:
    protocol, protocol_sha, registry, reveal_path, reveal = _opaque_protocol(tmp_path)
    backend = _NonadherentOpaquePilotBackend(
        {
            episode["cue"]: secret["correct_action_code"]
            for episode, secret in zip(protocol["episodes"], reveal["episodes"], strict=True)
        }
    )
    bundle = g1_micro.run_opaque_identifiability_pilot_with_backend(
        backend=backend,
        protocol=protocol,
        protocol_sha256=protocol_sha,
        output_dir=tmp_path / "opaque-output",
        execution_registry_path=registry,
        evaluator_reveal_path=reveal_path,
        tokenizer_receipt=_opaque_tokenizer_receipt(protocol),
    )
    assert backend.complete_calls == 64
    assert bundle["terminal"] == "PILOT_COMPLETE_NO_BEHAVIORAL_SEPARATION_NO_EFFICACY_INFERENCE"
    assert all(
        episode["dispositions"][branch]["credit"]["payload"]["decision"] == "NO_CREDIT"
        and episode["dispositions"][branch]["admission"] is None
        for episode in bundle["episodes"]
        for branch in ("ACTIVE", "FORCED_OPPOSITE_FEEDBACK")
    )


def _write_opaque_protocol(tmp_path: Path, protocol: Mapping[str, Any]) -> Path:
    path = tmp_path / "opaque-protocol.json"
    path.write_bytes(canonical_json_bytes(protocol))
    return path


def test_opaque_frozen_verifier_rejects_copied_registry_reveal_and_ledger_tamper(
    tmp_path: Path,
) -> None:
    protocol, protocol_sha, registry, reveal_path, reveal = _opaque_protocol(tmp_path)
    backend = _OpaquePilotBackend(
        {
            episode["cue"]: secret["correct_action_code"]
            for episode, secret in zip(protocol["episodes"], reveal["episodes"], strict=True)
        }
    )
    output = tmp_path / "opaque-output"
    g1_micro.run_opaque_identifiability_pilot_with_backend(
        backend=backend,
        protocol=protocol,
        protocol_sha256=protocol_sha,
        output_dir=output,
        execution_registry_path=registry,
        evaluator_reveal_path=reveal_path,
        tokenizer_receipt=_opaque_tokenizer_receipt(protocol),
    )
    protocol_path = _write_opaque_protocol(tmp_path, protocol)
    copied_registry = tmp_path / "copied-registry.json"
    copied_registry.write_bytes(registry.read_bytes())
    with pytest.raises(g1_micro.G1MicroError, match="registry"):
        g1_micro.verify_frozen_execution_files(
            bundle_path=output / "result.json",
            protocol_path=protocol_path,
            execution_registry_path=copied_registry,
        )

    reveal_file = output / "evaluator_reveal.json"
    reveal_file.write_bytes(reveal_file.read_bytes().replace(b"canary_", b"canaryX", 1))
    with pytest.raises(g1_micro.G1MicroError, match="reveal"):
        g1_micro.verify_bundle_file(output / "result.json")

    # Restore the exact reveal then mutate a raw model request.  A structural
    # verifier must replay retained preimages, not trust aggregate metrics.
    reveal_file.write_bytes(reveal_path.read_bytes())
    ledger = output / "episodes" / "01" / "attempt_ledger.jsonl"
    rows = [json.loads(line) for line in ledger.read_bytes().splitlines()]
    intent = next(row for row in rows if row["event"] == "intent")
    intent["raw_request_json"] = intent["raw_request_json"].replace(
        "opaque action code", "ADD_THREE"
    )
    ledger.write_bytes(b"\n".join(canonical_json_bytes(row) for row in rows) + b"\n")
    with pytest.raises(g1_micro.G1MicroError, match="(ledger|request|leak|journal)"):
        g1_micro.verify_bundle_file(output / "result.json")


def _run_opaque_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    protocol, protocol_sha, registry, reveal_path, reveal = _opaque_protocol(tmp_path)
    backend = _OpaquePilotBackend(
        {
            episode["cue"]: secret["correct_action_code"]
            for episode, secret in zip(protocol["episodes"], reveal["episodes"], strict=True)
        }
    )
    output = tmp_path / "opaque-output"
    g1_micro.run_opaque_identifiability_pilot_with_backend(
        backend=backend,
        protocol=protocol,
        protocol_sha256=protocol_sha,
        output_dir=output,
        execution_registry_path=registry,
        evaluator_reveal_path=reveal_path,
        tokenizer_receipt=_opaque_tokenizer_receipt(protocol),
    )
    return output, _write_opaque_protocol(tmp_path, protocol), registry


def _rewrite_opaque_bundle(output: Path, mutate: Callable[[dict[str, Any]], None]) -> None:
    bundle = json.loads((output / "result.json").read_bytes())
    mutate(bundle)
    unsigned = dict(bundle)
    unsigned.pop("bundle_sha256")
    bundle["bundle_sha256"] = canonical_sha256(unsigned)
    (output / "result.json").write_bytes(canonical_json_bytes(bundle))


def test_opaque_verifier_rejects_rehashed_response_and_evidence_mutations(
    tmp_path: Path,
) -> None:
    output, _, _ = _run_opaque_fixture(tmp_path)
    ledger = output / "episodes" / "01" / "attempt_ledger.jsonl"
    rows = [json.loads(line) for line in ledger.read_bytes().splitlines()]
    # Change ACTIVE's response and consistently rehash every retained response
    # preimage plus the bundle call evidence.  The remaining mismatch is
    # semantic: the response no longer agrees with the recorded probe choice.
    ordinal = 3
    raw_response = next(
        row
        for row in rows
        if row["event"] == "raw_response_received" and row["ordinal"] == ordinal
    )
    raw = json.loads(base64.b64decode(raw_response["raw_response_base64"]))
    result = json.loads((output / "result.json").read_bytes())
    probe = result["episodes"][0]["probes"]["ACTIVE"]
    original_choice = probe["payload"]["choice"]
    replacement_choice = next(
        item for item in probe["payload"]["candidate_order"] if item != original_choice
    )
    response_text = json.dumps({"action_code": replacement_choice}, separators=(",", ":"))
    raw["choices"][0]["message"]["content"] = response_text
    changed = canonical_json_bytes(raw)
    raw_response["raw_response_base64"] = base64.b64encode(changed).decode()
    raw_response["raw_response_sha256"] = sha256(changed).hexdigest()
    raw_response["response_bytes"] = len(changed)
    for row in rows:
        if row["ordinal"] == ordinal and row["event"] in {
            "response_received",
            "completed",
        }:
            completion = row["completion"]
            completion["raw_response_json"] = changed.decode()
            completion["response_sha256"] = sha256(changed).hexdigest()
            completion["text"] = response_text
    ledger.write_bytes(b"\n".join(canonical_json_bytes(row) for row in rows) + b"\n")
    probe_payload = dict(probe["payload"])
    evidence = dict(probe_payload["call_evidence"])
    evidence["completion_response_sha256"] = sha256(changed).hexdigest()
    probe_payload["call_evidence"] = evidence
    result["episodes"][0]["probes"]["ACTIVE"] = g1_micro.make_record(
        "OpaqueFreshBehaviorObservation",
        owner_uid=probe["owner_uid"],
        payload=probe_payload,
        refs=probe["refs"],
    )
    result["episodes"][0]["journal"] = g1_micro._journal_manifest(ledger)
    result["metrics"] = g1_micro._opaque_metrics(result["episodes"])
    result["terminal"] = result["metrics"]["terminal"]
    unsigned = dict(result)
    unsigned.pop("bundle_sha256")
    result["bundle_sha256"] = canonical_sha256(unsigned)
    (output / "result.json").write_bytes(canonical_json_bytes(result))
    with pytest.raises(g1_micro.G1MicroError, match="(probe response|score|semantic)"):
        g1_micro.verify_bundle_file(output / "result.json")

    # A freshly content-addressed proposal still must join the raw call.
    output, _, _ = _run_opaque_fixture(tmp_path / "proposal")
    result = json.loads((output / "result.json").read_bytes())
    proposal = result["episodes"][0]["dispositions"]["ACTIVE"]["proposal"]
    proposal_payload = deepcopy(proposal["payload"])
    proposal_payload["call_evidence"]["completion_response_sha256"] = "0" * 64
    result["episodes"][0]["dispositions"]["ACTIVE"]["proposal"] = (
        g1_micro.make_record(
            "RevisionProposal",
            owner_uid=proposal["owner_uid"],
            payload=proposal_payload,
            refs=proposal["refs"],
        )
    )
    unsigned = dict(result)
    unsigned.pop("bundle_sha256")
    result["bundle_sha256"] = canonical_sha256(unsigned)
    (output / "result.json").write_bytes(canonical_json_bytes(result))
    with pytest.raises(g1_micro.G1MicroError, match="(evidence|journal|raw)"):
        g1_micro.verify_bundle_file(output / "result.json")


def test_opaque_verifier_rejects_rehashed_compiled_state_and_store_mutations(
    tmp_path: Path,
) -> None:
    output, protocol_path, registry = _run_opaque_fixture(tmp_path)
    bundle = json.loads((output / "result.json").read_bytes())
    probe = bundle["episodes"][0]["probes"]["ACTIVE"]
    payload = deepcopy(probe["payload"])
    payload["compiled_disposition"]["state_sha256"] = "0" * 64
    bundle["episodes"][0]["probes"]["ACTIVE"] = g1_micro.make_record(
        "OpaqueFreshBehaviorObservation",
        owner_uid=probe["owner_uid"],
        payload=payload,
        refs=probe["refs"],
    )
    unsigned = dict(bundle)
    unsigned.pop("bundle_sha256")
    bundle["bundle_sha256"] = canonical_sha256(unsigned)
    (output / "result.json").write_bytes(canonical_json_bytes(bundle))
    with pytest.raises(g1_micro.G1MicroError, match="(state|probe|compiled)"):
        g1_micro.verify_frozen_execution_files(
            bundle_path=output / "result.json",
            protocol_path=protocol_path,
            execution_registry_path=registry,
        )

    output, _, _ = _run_opaque_fixture(tmp_path / "store")
    store = output / "episodes" / "01" / "active.sqlite3"
    store.write_bytes(store.read_bytes() + b"adversarial trailing bytes")
    with pytest.raises(g1_micro.G1MicroError, match="(state|artifact|receipt|database)"):
        g1_micro.verify_bundle_file(output / "result.json")


def test_opaque_frozen_verifier_rejects_start_and_seal_shape_mutations(
    tmp_path: Path,
) -> None:
    output, protocol_path, registry = _run_opaque_fixture(tmp_path)
    seal = json.loads(registry.read_bytes())
    start = seal["payload"]["start"]
    start_payload = dict(start["payload"])
    start_payload["output_directory"] = "/tmp/adversarial-output"
    forged_start = g1_micro.make_record(
        "OpaquePilotExecutionStart",
        owner_uid=start["owner_uid"],
        payload=start_payload,
        refs=start["refs"],
    )
    forged_seal = g1_micro.make_record(
        "OpaquePilotExecutionSeal",
        owner_uid=seal["owner_uid"],
        payload={**seal["payload"], "start": forged_start},
        refs=(g1_micro._ref("execution_start", forged_start),),
    )
    registry.write_bytes(canonical_json_bytes(forged_seal))
    with pytest.raises(g1_micro.G1MicroError, match="start"):
        g1_micro.verify_frozen_execution_files(
            bundle_path=output / "result.json",
            protocol_path=protocol_path,
            execution_registry_path=registry,
        )

    output, protocol_path, registry = _run_opaque_fixture(tmp_path / "seal")
    seal = json.loads(registry.read_bytes())
    forged_seal = g1_micro.make_record(
        "OpaquePilotExecutionSeal",
        owner_uid=seal["owner_uid"],
        payload={**seal["payload"], "abort_sha256": "0" * 64, "unexpected": True},
        refs=seal["refs"],
    )
    registry.write_bytes(canonical_json_bytes(forged_seal))
    with pytest.raises(g1_micro.G1MicroError, match="(registry|start|seal)"):
        g1_micro.verify_frozen_execution_files(
            bundle_path=output / "result.json",
            protocol_path=protocol_path,
            execution_registry_path=registry,
        )
