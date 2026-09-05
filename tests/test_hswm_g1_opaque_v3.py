"""The v3 G0-local instrument: separate evaluator, balanced positions, sham arm, Permit path."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Callable, Mapping

import pytest

from hswm.experiments import atom_v2_permit_bridge as bridge
from hswm.experiments import continual_live as live
from hswm.experiments import g1_micro, g1_opaque_v3
from hswm.experiments import g1_opaque_evaluator_process as evaluator_process
from hswm.selfmod.contracts import canonical_json_bytes, canonical_sha256

from tests.test_hswm_g1_micro import _OPAQUE_SUCCESSOR_PROTOCOL, _OpaquePilotBackend


ROOT = Path(__file__).resolve().parents[1]
SEED = bytes(range(32)) * 2


def _process() -> bridge.LocalPermitCommitProcess:
    process = bridge.default_process(ROOT)
    if process is None:
        pytest.skip("Atom v2 local Permit commit process is not built (cd src/hswm/effect-runtime && npm run build)")
    return process


def _generate(tmp_path: Path) -> tuple[dict, str, dict, Path, Path]:
    source = json.loads(_OPAQUE_SUCCESSOR_PROTOCOL.read_text(encoding="utf-8"))
    registry = tmp_path / "durable" / "v3-once"
    registry.parent.mkdir(parents=True)
    protocol, reveal = g1_opaque_v3.generate_v3(
        seed=SEED, study_date="2026-09-15", live_binding=source["live_binding"],
        tokenizer_model={key: source["tokenizer_binding"][key] for key in (
            "container_image", "container_image_id", "model_repository", "model_revision", "snapshot_manifest_sha256",
        )},
        consumption_registry_path=str(registry),
    )
    reveal_path = tmp_path / "private" / "reveal.json"
    reveal_path.parent.mkdir()
    reveal_path.write_bytes(canonical_json_bytes(reveal))
    return protocol, canonical_sha256(protocol), reveal, reveal_path, registry


class _StatelessBackend(_OpaquePilotBackend):
    """Ignores compiled state entirely: every probe picks the wrong code."""

    def complete(self, *, raw_request: bytes, request_id: str, response_observer: Callable[[bytes, bytes], None]) -> live.ModelCompletion:
        from hashlib import sha256

        request = json.loads(raw_request)
        payload = json.loads(request["messages"][-1]["content"])
        if "compiled_disposition" not in payload:
            return super().complete(raw_request=raw_request, request_id=request_id, response_observer=response_observer)
        codes = list(payload["action_codes"])
        correct = self.correct_by_cue[payload["cue"]]
        choice = next(code for code in codes if code != correct)
        text = json.dumps({"action_code": choice}, separators=(",", ":"))
        self.complete_calls += 1
        input_tokens = self._preflight_counts[sha256(raw_request).hexdigest()]
        raw_response = canonical_json_bytes({
            "choices": [{"finish_reason": "stop", "message": {"content": text}}],
            "id": f"stateless-fixture-{self.complete_calls}",
            "model": self.model,
            "usage": {"completion_tokens": 1, "prompt_tokens": input_tokens, "total_tokens": input_tokens + 1},
        })
        response_observer(raw_request, raw_response)
        response_sha = sha256(raw_response).hexdigest()
        self.response_sha256s.append(response_sha)
        return live.ModelCompletion(
            text=text, raw_request_json=raw_request.decode("utf-8"), raw_response_json=raw_response.decode("utf-8"),
            request_sha256=sha256(raw_request).hexdigest(), response_sha256=response_sha, model=self.model,
            input_tokens=input_tokens, output_tokens=1, latency_ms=0, usage_reported=True,
        )


def test_generation_is_deterministic_balanced_and_secret_bound(tmp_path: Path) -> None:
    protocol, sha, reveal, _, _ = _generate(tmp_path)
    source = json.loads(_OPAQUE_SUCCESSOR_PROTOCOL.read_text(encoding="utf-8"))
    again, reveal_again = g1_opaque_v3.generate_v3(
        seed=SEED, study_date="2026-09-15", live_binding=source["live_binding"],
        tokenizer_model={key: source["tokenizer_binding"][key] for key in (
            "container_image", "container_image_id", "model_repository", "model_revision", "snapshot_manifest_sha256",
        )},
        consumption_registry_path=protocol["consumption_registry"]["path"],
    )
    assert canonical_sha256(again) == sha and reveal_again == reveal
    assert protocol["generation"]["correct_position_balance"] == [16, 16]
    assert sum(e["sham_feedback_correct"] for e in protocol["episodes"]) == 16
    public_text = json.dumps(protocol)
    assert all(entry["salt"] not in public_text and entry["leakage_canary"] not in public_text for entry in reveal["episodes"])
    assert all(not {"salt", "correct_action_code", "leakage_canary"} & set(episode) for episode in protocol["episodes"])
    assert reveal["protocol_canonical_sha256"] == sha
    positions = [e["stateful_probe_action_order"].index(r["correct_action_code"]) for e, r in zip(protocol["episodes"], reveal["episodes"], strict=True)]
    assert positions.count(0) == 16
    g1_opaque_v3.validate_v3_protocol(protocol)
    broken = deepcopy(protocol)
    broken["episodes"][0]["sham_feedback_correct"] = not broken["episodes"][0]["sham_feedback_correct"]
    with pytest.raises(g1_micro.G1MicroError, match="balanced"):
        g1_opaque_v3.validate_v3_protocol(broken)
    broken = deepcopy(protocol)
    broken["atom_v2_permit_commit"]["required"] = False
    with pytest.raises(g1_micro.G1MicroError, match="Atom v2"):
        g1_opaque_v3.validate_v3_protocol(broken)


def _run(tmp_path: Path, backend_factory: Callable[[Mapping[str, str]], Any]) -> tuple[dict, dict, Path]:
    protocol, sha, reveal, reveal_path, registry = _generate(tmp_path)
    process = _process()
    correct_by_cue = {e["cue"]: r["correct_action_code"] for e, r in zip(protocol["episodes"], reveal["episodes"], strict=True)}
    endpoint = evaluator_process.default_endpoint(reveal_path, tmp_path / "evaluator" / "ledger.jsonl")
    output = tmp_path / "v3-output"
    bundle = g1_opaque_v3.run_v3_with_backend(
        backend=backend_factory(correct_by_cue), protocol=protocol, protocol_sha256=sha, output_dir=output,
        execution_registry_path=registry, evaluator=endpoint, permit_commit=process,
        reveal_path_after_seal=reveal_path, allow_pending_tokenizer_binding=True,
    )
    return protocol, bundle, output


def test_state_mediated_backend_reaches_the_g0_local_observed_terminal(tmp_path: Path) -> None:
    protocol, bundle, output = _run(tmp_path, _OpaquePilotBackend)
    metrics = bundle["metrics"]
    assert bundle["terminal"] == "V3_COMPLETE_G0_LOCAL_IDENTIFIABILITY_OBSERVED_NO_EFFICACY_INFERENCE"
    assert bundle["claim_ceiling"] == g1_opaque_v3.CLAIM_CEILING_IF_OBSERVED
    assert metrics["branch_correct"]["ACTIVE"] == 32 and metrics["branch_correct"]["RESTORE"] == 32
    assert metrics["branch_correct"]["FORCED_OPPOSITE_FEEDBACK"] == 0
    assert metrics["branch_correct"]["NO_UPDATE"] == 0 and metrics["branch_correct"]["REMOVE"] == 0
    assert metrics["branch_correct"]["OUTCOME_INDEPENDENT_SHAM"] == 16
    assert metrics["atom_v2_permit_commits"] == 96 and metrics["evaluator_feedback_verified"] == 32
    assert metrics["correct_position_balance_stateful"] == [16, 16]
    assert metrics["evaluator_separate_os_user_episodes"] == 0  # same user in tests
    assert bundle["reveal_attached_after_seal"]["behavior_calls_sealed_before_reveal_read"] == 320
    ledger_rows = (tmp_path / "evaluator" / "ledger.jsonl").read_bytes().splitlines()
    assert len(ledger_rows) == 32
    assert g1_micro.verify_bundle_file(output / "result.json")["verification"] == "VALID_LOCAL_STRUCTURAL_G0_LOCAL_RECONSTRUCTION"
    assert g1_opaque_v3.verify_v3_bundle(bundle, base_dir=output, protocol=protocol)["terminal"] == bundle["terminal"]
    registry = json.loads(Path(protocol["consumption_registry"]["path"]).read_bytes())
    assert registry["payload"]["status"] == "COMPLETED_NO_RERUN"

    def rewrite(mutate: Callable[[dict], None]) -> dict:
        mutated = json.loads((output / "result.json").read_bytes())
        mutate(mutated)
        unsigned = dict(mutated)
        unsigned.pop("bundle_sha256")
        mutated["bundle_sha256"] = canonical_sha256(unsigned)
        return mutated

    def flip_feedback(b: dict) -> None:
        feedback = b["episodes"][0]["outcome"]["payload"]["evaluator_feedback"]
        feedback["choice_was_correct"] = not feedback["choice_was_correct"]
        unsigned = dict(feedback)
        unsigned.pop("receipt_sha256")
        feedback["receipt_sha256"] = canonical_sha256(unsigned)
        outcome = b["episodes"][0]["outcome"]
        unsigned_outcome = dict(outcome)
        unsigned_outcome.pop("record_sha256")
        outcome["record_sha256"] = canonical_sha256(unsigned_outcome)

    with pytest.raises(evaluator_process.EvaluatorRefusal, match="MAC"):
        g1_opaque_v3.verify_v3_bundle(rewrite(flip_feedback), base_dir=output, protocol=protocol)

    def promote(b: dict) -> None:
        b["metrics"]["branch_correct"]["NO_UPDATE"] = 5

    with pytest.raises(g1_micro.G1MicroError, match="metrics or terminal"):
        g1_opaque_v3.verify_v3_bundle(rewrite(promote), base_dir=output, protocol=protocol)


def test_stateless_backend_reaches_the_no_separation_terminal(tmp_path: Path) -> None:
    protocol, bundle, output = _run(tmp_path, _StatelessBackend)
    assert bundle["terminal"] == "V3_COMPLETE_NO_SEPARATION_NO_EFFICACY_INFERENCE"
    assert bundle["claim_ceiling"] == "INSTRUMENT_VALIDATION_ONLY"
    assert bundle["metrics"]["branch_correct"]["ACTIVE"] == 0
    assert g1_opaque_v3.verify_v3_bundle(bundle, base_dir=output, protocol=protocol)["claim_ceiling"] == "INSTRUMENT_VALIDATION_ONLY"


def test_live_occurrence_refuses_a_pending_tokenizer_binding_and_a_second_claim(tmp_path: Path) -> None:
    protocol, sha, _, reveal_path, registry = _generate(tmp_path)
    process = _process()
    endpoint = evaluator_process.default_endpoint(reveal_path, tmp_path / "ledger.jsonl")
    with pytest.raises(g1_micro.G1MicroError, match="measured tokenizer binding"):
        g1_opaque_v3.run_v3_with_backend(
            backend=_OpaquePilotBackend({}), protocol=protocol, protocol_sha256=sha, output_dir=tmp_path / "out",
            execution_registry_path=registry, evaluator=endpoint, permit_commit=process, reveal_path_after_seal=reveal_path,
        )
    registry.write_bytes(b"{}")
    with pytest.raises(g1_micro.G1MicroError, match="one-shot registry"):
        g1_opaque_v3.run_v3_with_backend(
            backend=_OpaquePilotBackend({}), protocol=protocol, protocol_sha256=sha, output_dir=tmp_path / "out",
            execution_registry_path=registry, evaluator=endpoint, permit_commit=process, reveal_path_after_seal=reveal_path,
            allow_pending_tokenizer_binding=True,
        )


def test_preflight_reports_custody_freeze_and_measurement_blockers(tmp_path: Path) -> None:
    protocol, _, _, reveal_path, registry = _generate(tmp_path)
    protocol_path = tmp_path / "protocol.v1.json"
    protocol_path.write_bytes(canonical_json_bytes(protocol))
    endpoint = evaluator_process.default_endpoint(reveal_path, tmp_path / "ledger.jsonl")
    report = g1_opaque_v3.preflight_v3(
        protocol_path=protocol_path, output_dir=tmp_path / "out", execution_registry_path=registry,
        evaluator=endpoint, permit_commit=None, reveal_path_after_seal=reveal_path,
    )
    assert report["status"] == "PREFLIGHT_BLOCKED_ZERO_POST"
    assert set(report["problems"]) == {
        "PROTOCOL_NOT_FROZEN", "TOKENIZER_BINDING_NOT_MEASURED",
        "ATOM_V2_PERMIT_COMMIT_PROCESS_ABSENT", "REVEAL_READABLE_BY_ACTOR_BEFORE_RUN",
    }
    assert report["reveal_custody"] == "ACTOR_CAN_READ_REVEAL_BEFORE_RUN"
    unreadable = tmp_path / "missing-reveal.json"
    report = g1_opaque_v3.preflight_v3(
        protocol_path=protocol_path, output_dir=tmp_path / "out", execution_registry_path=registry,
        evaluator=endpoint, permit_commit=None, reveal_path_after_seal=unreadable, allow_same_user=True,
    )
    assert "REVEAL_READABLE_BY_ACTOR_BEFORE_RUN" not in report["problems"]
    assert report["reveal_custody"] == "ACTOR_CANNOT_READ_REVEAL_BEFORE_RUN"
