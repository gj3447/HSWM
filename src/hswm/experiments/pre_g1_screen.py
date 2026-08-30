"""Source-checkout-only PRE_G1 screen; not a G0/G1 result or admission system."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable, Mapping, Protocol, Sequence

from _research.dnrd5 import task_family
from _research.dnrd5.canonical_json import canonical_bytes, parse_canonical
from hswm.selfmod.contracts import canonical_sha256

from . import pre_g1_outcome_worker as worker


TERMINAL = "PRE_G1_MEASUREMENT_SCREEN_NO_G0_G1_CLAIM"
SCREEN_SCHEMA = "hswm-pre-g1-screen/v1"
ARMS = ("B0", "B2_SURROGATE", "H1", "H2", "H3")
EXPEL_PRIOR_UID = "sym:Prior:expel-b2-text-lesson-v1"
EXPEL_COMMIT = "e41ec9a24823e7b560c561ab191441b56d9bcefc"
EXPEL_LICENSE = "Apache-2.0"
EXPEL_PIN_FILE_SHA256 = (
    "17f5c77e30b91ee23edff3cbf74e40d2c3d87048788bfe6a67c562cd66e40886"
)
EXPEL_SURROGATE_STATUS = (
    "FROZEN_TEXT_LESSON_SURROGATE_NOT_EXPEL_REPRODUCTION_OR_EXTERNAL_BASELINE"
)
SESSION_RECEIPT_SCHEMA = "hswm-pre-g1-backend-session-receipt/v1"
SESSION_RECEIPT_FIELDS = {
    "schema_version", "session_id", "context_namespace", "response_cache_namespace",
    "reset_mode", "model_revision", "attestation_scope",
}
_DEFAULT_EXPEL_PIN = (
    Path(__file__).resolve().parents[3]
    / "_research/causal_composition/priors/expel_b2_text_lesson_v1/source_pin.v1.json"
)


class PreG1ScreenError(RuntimeError):
    pass


class ChoiceBackend(Protocol):
    """One isolated model session; it must not be reused by the screen."""

    def choose_hypothesis(self, public_task: Mapping[str, Any]) -> int: ...

    def answer_probe(
        self, public_task: Mapping[str, Any], probe_challenge: Mapping[str, Any], visible: Mapping[str, Any]
    ) -> str: ...

    def session_isolation_receipt(self) -> Mapping[str, Any]: ...


@dataclass(slots=True)
class WorkerEndpoint:
    role: str
    seed_file: Path
    invocation_count: int = field(default=0, init=False)

    def call(self, request: Mapping[str, Any]) -> dict[str, Any]:
        completed = subprocess.run(
            [sys.executable, "-m", "hswm.experiments.pre_g1_outcome_worker", "--role", self.role, "--seed-file", str(self.seed_file)],
            input=canonical_bytes(dict(request)), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=10,
        )
        if completed.returncode != 0:
            raise PreG1ScreenError("private worker refused request")
        try:
            response = parse_canonical(completed.stdout)
        except ValueError as error:
            raise PreG1ScreenError("private worker output is not canonical") from error
        if not isinstance(response, dict):
            raise PreG1ScreenError("private worker output is not an object")
        self.invocation_count += 1
        return response


@dataclass(frozen=True, slots=True)
class PinnedTextLessonB2:
    """A source-pinned surrogate; it is not an ExpeL implementation or baseline."""

    source_pin_path: Path = _DEFAULT_EXPEL_PIN

    def _pin(self) -> Mapping[str, Any]:
        try:
            raw = self.source_pin_path.read_bytes()
            value = json.loads(raw.decode("utf-8"))
            repository = value["official_sources"]["repository"]
            license_value = value["official_sources"]["license"]
        except (OSError, UnicodeDecodeError, KeyError, TypeError, json.JSONDecodeError) as error:
            raise PreG1ScreenError("B2 source pin is unavailable") from error
        if (
            sha256(raw).hexdigest() != EXPEL_PIN_FILE_SHA256
            or value.get("schema_version")
            != "hswm-causal-composition-prior-source-pin/v1"
            or value.get("prior_uid") != EXPEL_PRIOR_UID
            or repository.get("commit") != EXPEL_COMMIT
            or license_value.get("spdx") != EXPEL_LICENSE
        ):
            raise PreG1ScreenError("B2 source pin is not the exact permitted ExpeL prior")
        return value

    def propose(self, *, hypothesis: int, feedback_bit: int) -> dict[str, Any]:
        if type(hypothesis) is not int or hypothesis not in (0, 1):
            raise PreG1ScreenError("B2 hypothesis must be integer 0 or 1")
        if type(feedback_bit) is not int or feedback_bit not in (0, 1):
            raise PreG1ScreenError("B2 feedback must be integer 0 or 1")
        self._pin()
        inferred = hypothesis if feedback_bit else 1 - hypothesis
        lesson = {
            "kind": EXPEL_SURROGATE_STATUS,
            "hypothesis": inferred,
            "prior_uid": EXPEL_PRIOR_UID,
            "source_revision": EXPEL_COMMIT,
            "license_id": EXPEL_LICENSE,
        }
        return {
            **lesson,
            "external_state_digest": canonical_sha256(lesson),
            "resource_receipt": {"model_calls": 0, "writes": "TEXT_ONLY_NO_HSWM_ADMISSION"},
        }


@dataclass(frozen=True, slots=True)
class ScreenEpisode:
    public_task: Mapping[str, Any]
    probe_challenge: Mapping[str, Any]


def _legacy_public_for_training_seal(public: Mapping[str, Any]) -> dict[str, Any]:
    """Adapter only for DNRD5's existing training-seal constructor."""
    core = task_family._validate_public_core(public["public_core"])
    return {
        "schema_version": task_family.PUBLIC_SCHEMA,
        "block_id": core["block_id"],
        "seed_commitment": core["seed_commitment"],
        "public_core": core,
        "public_core_commitment": task_family.commitment(core),
        "evaluator_private_commitment": public["evaluator_private_commitment"],
        "probe_private_commitment": public["probe_challenge_commitment"],
        "placebo_private_commitment": public["placebo_private_commitment"],
    }


def _seal_training(public: Mapping[str, Any], hypothesis: int) -> dict[str, Any]:
    core = task_family._validate_public_core(public["public_core"])
    response = {
        "schema_version": task_family.TRAINING_RESPONSE_SCHEMA,
        "block_id": core["block_id"],
        "hypothesis_id": hypothesis,
        "answer_token": core["h0" if hypothesis == 0 else "h1"][core["train_input"]],
    }
    return task_family.seal_training_response(_legacy_public_for_training_seal(public), response)


def _feedback(endpoint: WorkerEndpoint, public: Mapping[str, Any], sealed_training: Mapping[str, Any]) -> dict[str, Any]:
    response = endpoint.call({"schema_version": worker.WORKER_SCHEMA, "kind": "TRAINING_OUTCOME" if endpoint.role == "outcome" else "SHAM_FEEDBACK", "public_task": dict(public), "sealed_training": dict(sealed_training)})
    trajectory_sha = sealed_training["trajectory_commitment"]
    if set(response) != {"schema_version", "trajectory_sha256", "feedback_bit", "receipt_sha256"} or response["schema_version"] != worker.FEEDBACK_SCHEMA or response["trajectory_sha256"] != trajectory_sha or type(response["feedback_bit"]) is not int or response["feedback_bit"] not in (0, 1):
        raise PreG1ScreenError("feedback worker response drifted")
    unsigned = dict(response); digest = unsigned.pop("receipt_sha256")
    if digest != sha256(canonical_bytes(unsigned)).hexdigest():
        raise PreG1ScreenError("feedback receipt digest drifted")
    return response


def _score(endpoint: WorkerEndpoint, public: Mapping[str, Any], challenge: Mapping[str, Any], answer: str) -> dict[str, Any]:
    response = endpoint.call({"schema_version": worker.WORKER_SCHEMA, "kind": "PROBE_SCORE", "public_task": dict(public), "probe_challenge": dict(challenge), "answer_token": answer})
    if set(response) != {"schema_version", "probe_challenge_commitment", "score", "receipt_sha256"} or response["schema_version"] != worker.SCORE_SCHEMA or response["probe_challenge_commitment"] != task_family.commitment(challenge) or type(response["score"]) is not int or response["score"] not in (0, 1):
        raise PreG1ScreenError("score worker response drifted")
    unsigned = dict(response); digest = unsigned.pop("receipt_sha256")
    if digest != sha256(canonical_bytes(unsigned)).hexdigest():
        raise PreG1ScreenError("score receipt digest drifted")
    return response


def _revision(hypothesis: int, feedback: Mapping[str, Any]) -> dict[str, Any]:
    inferred = hypothesis if feedback["feedback_bit"] else 1 - hypothesis
    value = {"schema_version": "hswm-pre-g1-local-revision/v1", "revision_kind": "INFERRED_HYPOTHESIS", "hypothesis": inferred, "feedback_receipt_sha256": feedback["receipt_sha256"]}
    return {**value, "revision_sha256": canonical_sha256(value)}


def _visible(*, revision: Mapping[str, Any] | None = None, lesson: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if (revision is None) == (lesson is None):
        return {"mode": "EMPTY"}
    if revision is not None:
        return {"mode": "LOCAL_REVISION", "hypothesis": revision["hypothesis"], "readset": [revision["revision_sha256"]]}
    return {"mode": "TEXT_LESSON", "hypothesis": lesson["hypothesis"], "lesson_digest": lesson["external_state_digest"]}


class ImmutableRevisionStore:
    """Narrow local store that proves H3 restores the exact removed bytes."""

    def __init__(self) -> None:
        self._records: dict[str, bytes] = {}
        self._active: set[str] = set()

    @staticmethod
    def _receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
        value = dict(payload)
        return {**value, "receipt_sha256": sha256(canonical_bytes(value)).hexdigest()}

    def admit(self, revision: Mapping[str, Any]) -> dict[str, Any]:
        payload = dict(revision)
        revision_sha = payload.pop("revision_sha256", None)
        if not isinstance(revision_sha, str) or revision_sha != canonical_sha256(payload):
            raise PreG1ScreenError("revision is not byte-exact")
        revision_bytes = canonical_bytes(dict(revision))
        if revision_sha in self._records:
            raise PreG1ScreenError("revision identity already exists in immutable store")
        self._records[revision_sha] = revision_bytes
        self._active.add(revision_sha)
        return self._receipt({
            "schema_version": "hswm-pre-g1-immutable-revision-store/v1",
            "action": "ADMIT",
            "revision_sha256": revision_sha,
            "stored_bytes_sha256": sha256(revision_bytes).hexdigest(),
            "stored_bytes_length": len(revision_bytes),
        })

    def remove(self, revision_sha: str) -> dict[str, Any]:
        if revision_sha not in self._active:
            raise PreG1ScreenError("only an active immutable revision can be removed")
        revision_bytes = self._records[revision_sha]
        self._active.remove(revision_sha)
        return self._receipt({
            "schema_version": "hswm-pre-g1-immutable-revision-store/v1",
            "action": "REMOVE",
            "revision_sha256": revision_sha,
            "removed_bytes_sha256": sha256(revision_bytes).hexdigest(),
            "removed_bytes_length": len(revision_bytes),
        })

    def restore(self, removal: Mapping[str, Any]) -> dict[str, Any]:
        expected = {
            "schema_version", "action", "revision_sha256", "removed_bytes_sha256",
            "removed_bytes_length", "receipt_sha256",
        }
        if set(removal) != expected or removal.get("schema_version") != "hswm-pre-g1-immutable-revision-store/v1" or removal.get("action") != "REMOVE":
            raise PreG1ScreenError("restore requires an exact removal receipt")
        unsigned = {key: value for key, value in removal.items() if key != "receipt_sha256"}
        if removal["receipt_sha256"] != sha256(canonical_bytes(unsigned)).hexdigest():
            raise PreG1ScreenError("removal receipt digest drifted")
        revision_sha = removal["revision_sha256"]
        if not isinstance(revision_sha, str) or revision_sha not in self._records or revision_sha in self._active:
            raise PreG1ScreenError("removal is not restorable")
        revision_bytes = self._records[revision_sha]
        if removal["removed_bytes_sha256"] != sha256(revision_bytes).hexdigest() or removal["removed_bytes_length"] != len(revision_bytes):
            raise PreG1ScreenError("immutable bytes no longer match removal receipt")
        self._active.add(revision_sha)
        return self._receipt({
            "schema_version": "hswm-pre-g1-immutable-revision-store/v1",
            "action": "RESTORE",
            "revision_sha256": revision_sha,
            "restored_bytes_sha256": sha256(revision_bytes).hexdigest(),
            "restored_bytes_length": len(revision_bytes),
            "removal_receipt_sha256": removal["receipt_sha256"],
        })

    def visible(self, revision_sha: str) -> dict[str, Any]:
        if revision_sha not in self._active:
            return _visible()
        revision_bytes = self._records[revision_sha]
        revision = parse_canonical(revision_bytes)
        if not isinstance(revision, dict) or canonical_bytes(revision) != revision_bytes:
            raise PreG1ScreenError("immutable revision bytes cannot be reconstituted")
        return _visible(revision=revision)


def _new_session(
    factory: Callable[[], ChoiceBackend], seen_sessions: list[ChoiceBackend], seen_session_ids: set[str],
    seen_context_namespaces: set[str], seen_cache_namespaces: set[str], location: str,
) -> tuple[ChoiceBackend, dict[str, Any]]:
    session = factory()
    if any(session is prior for prior in seen_sessions):
        raise PreG1ScreenError("backend session factory reused a session object")
    seen_sessions.append(session)
    try:
        receipt = dict(session.session_isolation_receipt())
        if set(receipt) != SESSION_RECEIPT_FIELDS:
            raise ValueError("receipt field set drifted")
        for field in SESSION_RECEIPT_FIELDS:
            if not isinstance(receipt[field], str) or not receipt[field]:
                raise ValueError(f"receipt {field} is not a nonempty string")
        if receipt["schema_version"] != SESSION_RECEIPT_SCHEMA:
            raise ValueError("receipt schema drifted")
        if receipt["reset_mode"] != "COLD_CONTEXT_NO_HISTORY":
            raise ValueError("receipt does not require cold context")
        if receipt["attestation_scope"] != "ADAPTER_REPORTED_NOT_INDEPENDENTLY_VERIFIED":
            raise ValueError("receipt attestation scope drifted")
        receipt_bytes = canonical_bytes(receipt)
    except (AttributeError, TypeError, ValueError) as error:
        raise PreG1ScreenError("backend session lacks a canonical isolation receipt") from error
    digest = sha256(receipt_bytes).hexdigest()
    if receipt["session_id"] in seen_session_ids:
        raise PreG1ScreenError("backend session factory reused a session identifier")
    if receipt["context_namespace"] in seen_context_namespaces:
        raise PreG1ScreenError("backend session factory reused a context namespace")
    if receipt["response_cache_namespace"] in seen_cache_namespaces:
        raise PreG1ScreenError("backend session factory reused a response-cache namespace")
    seen_session_ids.add(receipt["session_id"])
    seen_context_namespaces.add(receipt["context_namespace"])
    seen_cache_namespaces.add(receipt["response_cache_namespace"])
    return session, {"location": location, "receipt": receipt, "receipt_sha256": digest}


def _validate_episode(episode: ScreenEpisode) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    public = episode.public_task
    try:
        checked_public = worker.validate_separated_public(public)
        core = task_family._validate_public_core(checked_public["public_core"])
        task_family.validate_production_probe_challenge(episode.probe_challenge, core)
        if task_family.commitment(episode.probe_challenge) != checked_public["probe_challenge_commitment"]:
            raise PreG1ScreenError("screen probe challenge commitment drifted")
    except (worker.WorkerRefusal, KeyError, TypeError, task_family.TaskFamilyError) as error:
        raise PreG1ScreenError("screen public task is invalid") from error
    return checked_public, episode.probe_challenge


def run_pre_g1_screen(
    *, backend_session_factory: Callable[[], ChoiceBackend], episodes: Sequence[ScreenEpisode],
    outcome_feedback: WorkerEndpoint, sham_feedback: WorkerEndpoint,
    score: WorkerEndpoint, b2: PinnedTextLessonB2,
) -> dict[str, Any]:
    """Run local mechanics with fresh backend sessions for every action.

    Process endpoints remain local custody, not independent evaluator ownership.
    """

    if (outcome_feedback.role, sham_feedback.role, score.role) != ("outcome", "sham", "score") or not episodes:
        raise PreG1ScreenError("screen workers or episode set are invalid")
    initial_worker_counts = {
        "outcome_feedback": outcome_feedback.invocation_count,
        "sham_feedback": sham_feedback.invocation_count,
        "score": score.invocation_count,
    }
    seen_sessions: list[ChoiceBackend] = []
    seen_session_ids: set[str] = set()
    seen_context_namespaces: set[str] = set()
    seen_cache_namespaces: set[str] = set()
    results: list[dict[str, Any]] = []
    for ordinal, episode in enumerate(episodes):
        public, challenge = _validate_episode(episode)
        chooser, chooser_receipt = _new_session(backend_session_factory, seen_sessions, seen_session_ids, seen_context_namespaces, seen_cache_namespaces, f"episode:{ordinal}:training")
        choice = chooser.choose_hypothesis(public)
        if type(choice) is not int or choice not in (0, 1):
            raise PreG1ScreenError("backend hypothesis is invalid")
        sealed_training = _seal_training(public, choice)
        true_feedback = _feedback(outcome_feedback, public, sealed_training)
        sham_result = _feedback(sham_feedback, public, sealed_training)
        h1 = _revision(choice, true_feedback)
        h2 = _revision(choice, sham_result)
        lesson = b2.propose(hypothesis=choice, feedback_bit=true_feedback["feedback_bit"])
        h1_store = ImmutableRevisionStore()
        h1_admission = h1_store.admit(h1)
        h2_store = ImmutableRevisionStore()
        h2_admission = h2_store.admit(h2)
        h3_store = ImmutableRevisionStore()
        h3_admission = h3_store.admit(h1)
        arm_states = {
            "B0": (_visible(), _visible(), _visible()),
            "B2_SURROGATE": (_visible(lesson=lesson),) * 3,
            "H1": (h1_store.visible(h1["revision_sha256"]),) * 3,
            "H2": (h2_store.visible(h2["revision_sha256"]),) * 3,
        }
        h3_removal: dict[str, Any] | None = None
        h3_restore: dict[str, Any] | None = None
        arms: dict[str, Any] = {}
        arm_order = ARMS[ordinal % len(ARMS):] + ARMS[:ordinal % len(ARMS)]
        for arm in arm_order:
            probes = []
            for slot in range(3):
                if arm == "H3":
                    visible = h3_store.visible(h1["revision_sha256"])
                else:
                    visible = arm_states[arm][slot]
                session, session_receipt = _new_session(backend_session_factory, seen_sessions, seen_session_ids, seen_context_namespaces, seen_cache_namespaces, f"episode:{ordinal}:arm:{arm}:slot:{slot}")
                answer = session.answer_probe(public, challenge, visible)
                scored = _score(score, public, challenge, answer)
                probes.append({"slot": slot, "visible": visible, "answer_sha256": sha256(answer.encode()).hexdigest(), "score": scored["score"], "score_receipt_sha256": scored["receipt_sha256"], "session_isolation": session_receipt})
                if arm == "H3" and slot == 0:
                    h3_removal = h3_store.remove(h1["revision_sha256"])
                elif arm == "H3" and slot == 1:
                    if h3_removal is None:
                        raise PreG1ScreenError("H3 removal did not occur before empty slot")
                    h3_restore = h3_store.restore(h3_removal)
            arms[arm] = {"observed_probe_calls": len(probes), "update_calls": 0, "probes": probes}
        if h3_removal is None or h3_restore is None:
            raise PreG1ScreenError("H3 did not complete interleaved remove and restore")
        results.append({
            "episode": ordinal,
            "sealed_training": sealed_training,
            "true_feedback": true_feedback,
            "sham_feedback": sham_result,
            "h1_revision": h1,
            "h2_revision": h2,
            "b2_surrogate": lesson,
            "arm_evaluation_order": arm_order,
            "training_session_isolation": chooser_receipt,
            "immutable_revision_stores": {
                "h1_admission": h1_admission,
                "h2_admission": h2_admission,
                "h3_admission": h3_admission,
                "h3_removal": h3_removal,
                "h3_restore": h3_restore,
            },
            "arms": arms,
        })
    bundle = {
        "schema_version": SCREEN_SCHEMA,
        "terminal": TERMINAL,
        "episodes": results,
        "call_accounting": {
            "shared_training_calls": len(episodes),
            "observed_probe_calls": len(episodes) * len(ARMS) * 3,
            "observed_backend_calls": len(episodes) * (1 + len(ARMS) * 3),
            "per_arm_update_calls": 0,
            "future_comparator_parity": "NOT_EVALUATED",
            "worker_invocations": {
                "outcome_feedback": outcome_feedback.invocation_count - initial_worker_counts["outcome_feedback"],
                "sham_feedback": sham_feedback.invocation_count - initial_worker_counts["sham_feedback"],
                "score": score.invocation_count - initial_worker_counts["score"],
            },
            "model_calls": len(episodes) * (1 + len(ARMS) * 3),
            "worker_calls": len(episodes) * (2 + len(ARMS) * 3),
        },
        "execution_boundary": {
            "deployment": "SOURCE_CHECKOUT_ONLY_REUSES_RESEARCH_DNRD5_NOT_A_WHEEL_API",
            "cache_policy": "REQUIRED_BUT_NOT_PLATFORM_VERIFIED_NO_SHARED_RESPONSE_CACHE_NAMESPACE",
            "network_policy": "REQUIRED_BUT_NOT_PLATFORM_VERIFIED_BACKEND_NETWORK_POLICY",
            "session_isolation": "FRESH_FACTORY_SESSION_UNIQUE_NAMESPACES_ADAPTER_REPORTED_NOT_INDEPENDENTLY_VERIFIED",
            "custody": "LOCAL_PROCESS_BOUNDARY_NOT_INDEPENDENT_EVALUATOR_OWNERSHIP",
            "h3_empty_score_interpretation": "H3_BEHAVIORAL_EMPTY_SCORE_IS_NOT_REMOVAL_EVIDENCE_WITHOUT_EXTERNAL_PLATFORM_ISOLATION",
        },
        "claim_boundary": "LOCAL_PROCESS_SEPARATED_MEASUREMENT_SCREEN_NOT_G0_G1_OR_CANONICAL_ADMISSION_NO_CAUSAL_INTERPRETATION_WITHOUT_EXTERNAL_PLATFORM_ISOLATION",
    }
    return {**bundle, "bundle_sha256": canonical_sha256(bundle)}
