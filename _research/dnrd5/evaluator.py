"""Pure private evaluators for the DNRD-5 two-hypothesis task family."""

from __future__ import annotations

from typing import Any, Mapping

from . import task_family as task


def _sealed_training(public: Mapping[str, Any], sealed: Mapping[str, Any]) -> dict[str, Any]:
    parsed = task._exact(
        sealed,
        {"schema_version", "public_task_commitment", "response", "trajectory_commitment"},
        "sealed_training_response",
    )
    payload = {key: value for key, value in parsed.items() if key != "trajectory_commitment"}
    if parsed["schema_version"] != task.SEALED_TRAINING_RESPONSE_SCHEMA:
        raise task.TaskFamilyError("wrong sealed training schema")
    if parsed["public_task_commitment"] != task.commitment(public) or parsed["trajectory_commitment"] != task.commitment(payload):
        raise task.TaskFamilyError("sealed training commitment mismatch")
    task.validate_training_response(public, parsed["response"])
    return dict(parsed)


def evaluate_training(
    public: Mapping[str, Any], evaluator_private: Mapping[str, Any], sealed_training_response: Mapping[str, Any]
) -> dict[str, Any]:
    """Return only a minimal true correct/incorrect receipt for a sealed trajectory."""
    task._private_record(evaluator_private, task.EVALUATOR_PRIVATE_SCHEMA, public, "evaluator_private")
    if task.commitment(evaluator_private) != public["evaluator_private_commitment"]:
        raise task.TaskFamilyError("evaluator private commitment mismatch")
    sealed = _sealed_training(public, sealed_training_response)
    response = task.validate_training_response(public, sealed["response"])
    bit = int(response["hypothesis_id"] == evaluator_private["theta"])
    payload = {
        "schema_version": task.OUTCOME_RECEIPT_SCHEMA,
        "trajectory_commitment": sealed["trajectory_commitment"],
        "feedback_bit": bit,
    }
    return {**payload, "receipt_commitment": task.commitment(payload)}


def _proposal_projection(trajectory_commitment: str, feedback_bit: int) -> dict[str, Any]:
    task._sha(trajectory_commitment, "trajectory_commitment")
    task._bit(feedback_bit, "feedback_bit")
    return {
        "schema_version": task.PROPOSAL_FEEDBACK_SCHEMA,
        "trajectory_commitment": trajectory_commitment,
        "feedback_bit": feedback_bit,
    }


def genuine_proposal_projection(outcome_receipt: Mapping[str, Any]) -> dict[str, Any]:
    receipt = task._exact(
        outcome_receipt,
        {"schema_version", "trajectory_commitment", "feedback_bit", "receipt_commitment"},
        "outcome_receipt",
    )
    payload = {key: value for key, value in receipt.items() if key != "receipt_commitment"}
    if receipt["schema_version"] != task.OUTCOME_RECEIPT_SCHEMA or receipt["receipt_commitment"] != task.commitment(payload):
        raise task.TaskFamilyError("outcome receipt commitment mismatch")
    return _proposal_projection(receipt["trajectory_commitment"], receipt["feedback_bit"])


def placebo_proposal_projection(
    public: Mapping[str, Any], placebo_private: Mapping[str, Any], sealed_training_response: Mapping[str, Any]
) -> dict[str, Any]:
    task._private_record(placebo_private, task.PLACEBO_PRIVATE_SCHEMA, public, "placebo_private")
    if task.commitment(placebo_private) != public["placebo_private_commitment"]:
        raise task.TaskFamilyError("placebo private commitment mismatch")
    sealed = _sealed_training(public, sealed_training_response)
    return _proposal_projection(sealed["trajectory_commitment"], placebo_private["placebo_bit"])


def evaluate_probe(
    public: Mapping[str, Any], probe_private: Mapping[str, Any], sealed_probe_response: Mapping[str, Any]
) -> dict[str, Any]:
    """Blindly score one sealed probe token without returning theta, answer, or diagnostics."""
    task._private_record(probe_private, task.PROBE_PRIVATE_SCHEMA, public, "probe_private")
    if task.commitment(probe_private) != public["probe_private_commitment"]:
        raise task.TaskFamilyError("probe private commitment mismatch")
    response = task._exact(
        sealed_probe_response,
        {"schema_version", "public_task_commitment", "opening_commitment", "bundle_audit_receipt", "opening_status", "answer_token", "response_commitment"},
        "sealed_probe_response",
    )
    payload = {key: value for key, value in response.items() if key != "response_commitment"}
    if response["schema_version"] != task.SEALED_PROBE_RESPONSE_SCHEMA or response["response_commitment"] != task.commitment(payload):
        raise task.TaskFamilyError("sealed probe response commitment mismatch")
    if response["public_task_commitment"] != task.commitment(public):
        raise task.TaskFamilyError("sealed probe belongs to another public task")
    task._token_value(response["answer_token"], "sealed probe answer")
    if response["opening_status"] != task.PROBE_OPENING_STATUS:
        raise task.TaskFamilyError("sealed probe lacks lifecycle chronology nonclaim")
    expected_opening = task.open_probe(public, probe_private, response["bundle_audit_receipt"])
    if response["opening_commitment"] != expected_opening["opening_commitment"]:
        raise task.TaskFamilyError("sealed probe does not bind the committed probe opening")
    score = int(response["answer_token"] == probe_private["probe_answer"])
    outcome_payload = {
        "schema_version": task.PROBE_OUTCOME_SCHEMA,
        "probe_response_commitment": response["response_commitment"],
        "score": score,
    }
    return {**outcome_payload, "receipt_commitment": task.commitment(outcome_payload)}


def evaluate_probe_separated(
    public_task: Mapping[str, Any],
    probe_challenge: Mapping[str, Any],
    hidden_answer: Mapping[str, Any],
    answer_token: str,
) -> dict[str, Any]:
    """Blind score with challenge and answer custodians separated; never accepts theta."""
    expected_public_keys = {
        "schema_version",
        "public_core",
        "public_core_commitment",
        "evaluator_private_commitment",
        "probe_challenge_commitment",
        "hidden_answer_commitment",
        "placebo_private_commitment",
    }
    if type(public_task) is not dict or set(public_task) != expected_public_keys:
        raise task.TaskFamilyError("separated public task shape mismatch")
    if public_task["schema_version"] != task.SEPARATED_PUBLIC_SCHEMA:
        raise task.TaskFamilyError("separated public schema mismatch")
    core = task._validate_public_core(public_task["public_core"])
    if public_task["public_core_commitment"] != task.commitment(core):
        raise task.TaskFamilyError("separated public core mismatch")
    for field in (
        "evaluator_private_commitment",
        "probe_challenge_commitment",
        "hidden_answer_commitment",
        "placebo_private_commitment",
    ):
        task._sha(public_task[field], field)
    if task.commitment(probe_challenge) != public_task["probe_challenge_commitment"]:
        raise task.TaskFamilyError("probe challenge commitment mismatch")
    checked_challenge = task.validate_production_probe_challenge(probe_challenge, core)
    checked_answer = task.validate_production_hidden_answer(hidden_answer, core, checked_challenge)
    if checked_answer["commitment"] != public_task["hidden_answer_commitment"]:
        raise task.TaskFamilyError("hidden answer commitment mismatch")
    task._token_value(answer_token, "probe answer token")
    if answer_token not in core["outputs"]:
        raise task.TaskFamilyError("probe answer outside public output domain")
    result = {
        "schema_version": task.SEPARATED_PROBE_OUTCOME_SCHEMA,
        "probe_challenge_commitment": task.commitment(checked_challenge),
        "score": int(answer_token == checked_answer["probe_answer"]),
    }
    return {**result, "receipt_commitment": task.commitment(result)}
