from __future__ import annotations

from pathlib import Path
import json

import pytest

from _research.dnrd5 import task_family
from _research.dnrd5.canonical_json import canonical_bytes
from hswm.experiments import pre_g1_screen
from hswm.experiments.pre_g1_screen import (
    PinnedTextLessonB2, PreG1ScreenError, ScreenEpisode, WorkerEndpoint, run_pre_g1_screen,
)


class FakeBackend:
    def __init__(self, isolation_id: int = 0) -> None:
        self.hypothesis_calls = 0
        self.probe_calls = 0
        self.isolation_id = isolation_id

    def choose_hypothesis(self, public_task):
        self.hypothesis_calls += 1
        return 0

    def answer_probe(self, public_task, probe_challenge, visible):
        self.probe_calls += 1
        hypothesis = visible.get("hypothesis", 0)
        core = public_task["public_core"]
        return core["h0" if hypothesis == 0 else "h1"][probe_challenge["probe_input"]]

    def session_isolation_receipt(self):
        suffix = str(self.isolation_id)
        return {
            "schema_version": "hswm-pre-g1-backend-session-receipt/v1",
            "session_id": f"session-{suffix}",
            "context_namespace": f"context-{suffix}",
            "response_cache_namespace": f"cache-{suffix}",
            "reset_mode": "COLD_CONTEXT_NO_HISTORY",
            "model_revision": "test-model-r1",
            "attestation_scope": "ADAPTER_REPORTED_NOT_INDEPENDENTLY_VERIFIED",
        }


class FreshBackendFactory:
    def __init__(self) -> None:
        self.sessions: list[FakeBackend] = []

    def __call__(self) -> FakeBackend:
        session = FakeBackend(len(self.sessions) + 1)
        self.sessions.append(session)
        return session


class ReusedStatefulSession(FakeBackend):
    pass


class MalformedReceiptBackend(FakeBackend):
    def session_isolation_receipt(self):
        return {"session_id": "missing-required-contract"}


class SharedGlobalWrapper(FakeBackend):
    def __init__(self, isolation_id: int, shared_state: list[int]) -> None:
        super().__init__(isolation_id)
        self.shared_state = shared_state

    def answer_probe(self, public_task, probe_challenge, visible):
        self.shared_state[0] += 1
        core = public_task["public_core"]
        hypothesis = 0 if self.shared_state[0] % 3 == 0 else 1
        return core["h0" if hypothesis == 0 else "h1"][probe_challenge["probe_input"]]


def _episode(*, block_index: int = 1) -> ScreenEpisode:
    core = task_family.production_public_core(b"t" * 32, block_index)
    evaluator_private = task_family.production_evaluator_private(b"e" * 32, core)
    challenge = task_family.production_probe_challenge(b"p" * 32, core)
    hidden = task_family.production_hidden_answer(evaluator_private, challenge, core)
    placebo = task_family.production_placebo_private(b"z" * 32, core)
    public = task_family.assemble_production_public_task(
        core, task_family.commitment(evaluator_private), task_family.commitment(challenge),
        hidden["commitment"], task_family.commitment(placebo),
    )
    return ScreenEpisode(public, challenge)


def _seed(path: Path, raw: bytes) -> Path:
    path.write_bytes(raw)
    return path


def test_screen_has_matched_slots_local_h3_intervention_and_no_secret_leak(tmp_path: Path) -> None:
    backend = FreshBackendFactory()
    outcome = WorkerEndpoint("outcome", _seed(tmp_path / "outcome.seed", b"e" * 32))
    sham = WorkerEndpoint("sham", _seed(tmp_path / "sham.seed", b"z" * 32))
    score = WorkerEndpoint("score", _seed(tmp_path / "score.seed", b"e" * 32))
    bundle = run_pre_g1_screen(backend_session_factory=backend, episodes=[_episode()], outcome_feedback=outcome, sham_feedback=sham, score=score, b2=PinnedTextLessonB2())
    assert bundle["terminal"] == "PRE_G1_MEASUREMENT_SCREEN_NO_G0_G1_CLAIM"
    assert len(backend.sessions) == 16
    assert sum(item.hypothesis_calls for item in backend.sessions) == 1
    assert sum(item.probe_calls for item in backend.sessions) == 15
    row = bundle["episodes"][0]
    assert set(row["arms"]) == {"B0", "B2_SURROGATE", "H1", "H2", "H3"}
    assert {arm["observed_probe_calls"] for arm in row["arms"].values()} == {3}
    assert {arm["update_calls"] for arm in row["arms"].values()} == {0}
    assert bundle["call_accounting"] == {
        "shared_training_calls": 1,
        "observed_probe_calls": 15,
        "observed_backend_calls": 16,
        "per_arm_update_calls": 0,
        "future_comparator_parity": "NOT_EVALUATED",
        "worker_invocations": {"outcome_feedback": 1, "sham_feedback": 1, "score": 15},
        "model_calls": 16,
        "worker_calls": 17,
    }
    h3 = row["arms"]["H3"]["probes"]
    assert h3[0]["visible"] == h3[2]["visible"]
    assert h3[1]["visible"] == {"mode": "EMPTY"}
    store = row["immutable_revision_stores"]
    assert store["h3_removal"]["removed_bytes_sha256"] == store["h3_restore"]["restored_bytes_sha256"]
    assert store["h3_restore"]["removal_receipt_sha256"] == store["h3_removal"]["receipt_sha256"]
    assert store["h1_admission"]["action"] == store["h2_admission"]["action"] == "ADMIT"
    assert row["arm_evaluation_order"] == (
        "B0", "B2_SURROGATE", "H1", "H2", "H3",
    )
    assert row["b2_surrogate"]["resource_receipt"]["writes"] == (
        "TEXT_ONLY_NO_HSWM_ADMISSION"
    )
    assert row["b2_surrogate"]["kind"] == (
        "FROZEN_TEXT_LESSON_SURROGATE_NOT_EXPEL_REPRODUCTION_OR_EXTERNAL_BASELINE"
    )
    assert set(row["true_feedback"]) == set(row["sham_feedback"])
    assert len(canonical_bytes(row["true_feedback"])) == len(canonical_bytes(row["sham_feedback"]))
    public = str(bundle)
    assert "theta" not in public and "probe_answer" not in public
    assert "e" * 32 not in public and "z" * 32 not in public


def test_worker_is_fail_closed_on_wrong_role_or_cross_task(tmp_path: Path) -> None:
    endpoint = WorkerEndpoint("outcome", _seed(tmp_path / "outcome.seed", b"e" * 32))
    episode = _episode()
    with pytest.raises(PreG1ScreenError):
        endpoint.call({"schema_version": "hswm-pre-g1-outcome-worker/v1", "kind": "SHAM_FEEDBACK", "public_task": episode.public_task, "sealed_training": {}})
    wrong_seed = WorkerEndpoint("outcome", _seed(tmp_path / "wrong.seed", b"q" * 32))
    with pytest.raises(PreG1ScreenError):
        wrong_seed.call({"schema_version": "hswm-pre-g1-outcome-worker/v1", "kind": "TRAINING_OUTCOME", "public_task": episode.public_task, "sealed_training": {}})
    sealed = pre_g1_screen._seal_training(episode.public_task, 0)
    other = _episode(block_index=2)
    with pytest.raises(PreG1ScreenError):
        endpoint.call({"schema_version": "hswm-pre-g1-outcome-worker/v1", "kind": "TRAINING_OUTCOME", "public_task": other.public_task, "sealed_training": sealed})


def test_screen_rejects_reused_stateful_backend_session(tmp_path: Path) -> None:
    session = ReusedStatefulSession()
    outcome = WorkerEndpoint("outcome", _seed(tmp_path / "outcome.seed", b"e" * 32))
    sham = WorkerEndpoint("sham", _seed(tmp_path / "sham.seed", b"z" * 32))
    score = WorkerEndpoint("score", _seed(tmp_path / "score.seed", b"e" * 32))
    with pytest.raises(PreG1ScreenError, match="reused a session object"):
        run_pre_g1_screen(
            backend_session_factory=lambda: session, episodes=[_episode()],
            outcome_feedback=outcome, sham_feedback=sham, score=score, b2=PinnedTextLessonB2(),
        )


@pytest.mark.parametrize("malformation", ("extra_field", "bad_digest"))
def test_invalid_public_task_refuses_before_backend_factory(tmp_path: Path, malformation: str) -> None:
    episode = _episode()
    public = dict(episode.public_task)
    if malformation == "extra_field":
        public["unbound"] = "not-permitted"
    else:
        public["public_core_commitment"] = "0" * 64
    factory_calls = 0

    def factory() -> FakeBackend:
        nonlocal factory_calls
        factory_calls += 1
        return FakeBackend(factory_calls)

    outcome = WorkerEndpoint("outcome", _seed(tmp_path / "outcome.seed", b"e" * 32))
    sham = WorkerEndpoint("sham", _seed(tmp_path / "sham.seed", b"z" * 32))
    score = WorkerEndpoint("score", _seed(tmp_path / "score.seed", b"e" * 32))
    with pytest.raises(PreG1ScreenError, match="public task"):
        run_pre_g1_screen(
            backend_session_factory=factory,
            episodes=[ScreenEpisode(public, episode.probe_challenge)],
            outcome_feedback=outcome,
            sham_feedback=sham,
            score=score,
            b2=PinnedTextLessonB2(),
        )
    assert factory_calls == 0


def test_screen_refuses_malformed_session_receipt(tmp_path: Path) -> None:
    outcome = WorkerEndpoint("outcome", _seed(tmp_path / "outcome.seed", b"e" * 32))
    sham = WorkerEndpoint("sham", _seed(tmp_path / "sham.seed", b"z" * 32))
    score = WorkerEndpoint("score", _seed(tmp_path / "score.seed", b"e" * 32))
    with pytest.raises(PreG1ScreenError, match="canonical isolation receipt"):
        run_pre_g1_screen(
            backend_session_factory=lambda: MalformedReceiptBackend(1),
            episodes=[_episode()], outcome_feedback=outcome, sham_feedback=sham,
            score=score, b2=PinnedTextLessonB2(),
        )


def test_adapter_receipts_do_not_prove_provider_global_state_isolation(tmp_path: Path) -> None:
    shared_state = [0]
    next_id = 0

    def contaminated_factory() -> SharedGlobalWrapper:
        nonlocal next_id
        next_id += 1
        return SharedGlobalWrapper(next_id, shared_state)

    outcome = WorkerEndpoint("outcome", _seed(tmp_path / "outcome.seed", b"e" * 32))
    sham = WorkerEndpoint("sham", _seed(tmp_path / "sham.seed", b"z" * 32))
    score = WorkerEndpoint("score", _seed(tmp_path / "score.seed", b"e" * 32))
    bundle = run_pre_g1_screen(
        backend_session_factory=contaminated_factory, episodes=[_episode()],
        outcome_feedback=outcome, sham_feedback=sham, score=score, b2=PinnedTextLessonB2(),
    )
    h3 = bundle["episodes"][0]["arms"]["H3"]["probes"]
    assert h3[0]["visible"] == h3[2]["visible"]
    assert h3[0]["answer_sha256"] != h3[2]["answer_sha256"]
    assert shared_state == [15]
    assert bundle["execution_boundary"]["session_isolation"].endswith("NOT_INDEPENDENTLY_VERIFIED")
    assert "NO_CAUSAL_INTERPRETATION" in bundle["claim_boundary"]


def test_b2_requires_source_binding() -> None:
    with pytest.raises(PreG1ScreenError):
        PinnedTextLessonB2(Path("/missing/source-pin.json")).propose(hypothesis=0, feedback_bit=1)


def test_b2_refuses_arbitrary_source_pin(tmp_path: Path) -> None:
    pin = tmp_path / "pin.json"
    pin.write_text(json.dumps({"prior_uid": "sym:Prior:expel-b2-text-lesson-v1", "official_sources": {"repository": {"commit": "0" * 40}, "license": {"spdx": "Apache-2.0"}}}), encoding="utf-8")
    with pytest.raises(PreG1ScreenError):
        PinnedTextLessonB2(pin).propose(hypothesis=0, feedback_bit=1)


@pytest.mark.parametrize(
    ("hypothesis", "feedback_bit"),
    [(True, 1), (0, False), (2, 1), (0, -1)],
)
def test_b2_refuses_non_bit_inputs(hypothesis: object, feedback_bit: object) -> None:
    with pytest.raises(PreG1ScreenError):
        PinnedTextLessonB2().propose(
            hypothesis=hypothesis,  # type: ignore[arg-type]
            feedback_bit=feedback_bit,  # type: ignore[arg-type]
        )
