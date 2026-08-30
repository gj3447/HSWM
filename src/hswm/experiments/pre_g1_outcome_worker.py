"""One-request local custody worker for the PRE_G1 measurement screen.

The worker is deliberately a process boundary, not an independently owned
scientific evaluator.  It owns exactly one private seed file and returns only
the allow-listed feedback or score projection needed by the parent screen.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
import sys
from typing import Any, Mapping

from _research.dnrd5 import evaluator, task_family
from _research.dnrd5.canonical_json import canonical_bytes, parse_canonical


WORKER_SCHEMA = "hswm-pre-g1-outcome-worker/v1"
FEEDBACK_SCHEMA = "hswm-pre-g1-feedback/v1"
SCORE_SCHEMA = "hswm-pre-g1-score/v1"


class WorkerRefusal(ValueError):
    """A request or private boundary does not satisfy the narrow worker API."""


def _exact(value: object, fields: set[str]) -> Mapping[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise WorkerRefusal("worker request field set drifted")
    return value


def _sha(value: object) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise WorkerRefusal("worker digest is invalid")
    return value


def _seed(path: Path) -> bytes:
    raw = path.read_bytes()
    if len(raw) != task_family.SEED_BYTES:
        raise WorkerRefusal("private seed file has the wrong length")
    return raw


def validate_separated_public(value: object) -> Mapping[str, Any]:
    """Validate the entire public separated-task contract before private work."""
    expected = {
        "schema_version", "public_core", "public_core_commitment",
        "evaluator_private_commitment", "probe_challenge_commitment",
        "hidden_answer_commitment", "placebo_private_commitment",
    }
    public = _exact(value, expected)
    if public["schema_version"] != task_family.SEPARATED_PUBLIC_SCHEMA:
        raise WorkerRefusal("public task schema is invalid")
    core = task_family._validate_public_core(public["public_core"])
    if public["public_core_commitment"] != task_family.commitment(core):
        raise WorkerRefusal("public core commitment does not match public task")
    for field in (
        "evaluator_private_commitment", "probe_challenge_commitment",
        "hidden_answer_commitment", "placebo_private_commitment",
    ):
        task_family._sha(public[field], field)
    return public


def _legacy_public_for_training_seal(public: Mapping[str, Any]) -> dict[str, Any]:
    core = task_family._validate_public_core(public["public_core"])
    return {
        "schema_version": task_family.PUBLIC_SCHEMA,
        "block_id": core["block_id"], "seed_commitment": core["seed_commitment"],
        "public_core": core, "public_core_commitment": task_family.commitment(core),
        "evaluator_private_commitment": public["evaluator_private_commitment"],
        "probe_private_commitment": public["probe_challenge_commitment"],
        "placebo_private_commitment": public["placebo_private_commitment"],
    }


def _sealed_training(public: Mapping[str, Any], value: object) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise WorkerRefusal("sealed training is invalid")
    try:
        response = value["response"]
        expected = task_family.seal_training_response(_legacy_public_for_training_seal(public), response)
    except (KeyError, TypeError, task_family.TaskFamilyError) as error:
        raise WorkerRefusal("sealed training does not validate") from error
    if value != expected:
        raise WorkerRefusal("sealed training commitment drifted")
    return value


def _reply(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result["receipt_sha256"] = sha256(canonical_bytes(result)).hexdigest()
    return result


def handle_request(*, role: str, seed: bytes, request: object) -> dict[str, Any]:
    """Handle one canonical request without returning a seed, theta, or answer."""

    if role == "outcome":
        value = _exact(request, {"schema_version", "kind", "public_task", "sealed_training"})
        if value["schema_version"] != WORKER_SCHEMA or value["kind"] != "TRAINING_OUTCOME":
            raise WorkerRefusal("outcome request kind is invalid")
        public = validate_separated_public(value["public_task"])
        core = task_family._validate_public_core(public["public_core"])
        sealed = _sealed_training(public, value["sealed_training"])
        hypothesis = sealed["response"]["hypothesis_id"]
        if type(hypothesis) is not int or hypothesis not in (0, 1):
            raise WorkerRefusal("hypothesis is invalid")
        private = task_family.production_evaluator_private(seed, core)
        if task_family.commitment(private) != public["evaluator_private_commitment"]:
            raise WorkerRefusal("evaluator private commitment does not match public task")
        return _reply({
            "schema_version": FEEDBACK_SCHEMA,
            "trajectory_sha256": _sha(sealed["trajectory_commitment"]),
            "feedback_bit": int(hypothesis == private["theta"]),
        })
    if role == "sham":
        value = _exact(request, {"schema_version", "kind", "public_task", "sealed_training"})
        if value["schema_version"] != WORKER_SCHEMA or value["kind"] != "SHAM_FEEDBACK":
            raise WorkerRefusal("sham request kind is invalid")
        public = validate_separated_public(value["public_task"])
        core = task_family._validate_public_core(public["public_core"])
        sealed = _sealed_training(public, value["sealed_training"])
        hypothesis = sealed["response"]["hypothesis_id"]
        if type(hypothesis) is not int or hypothesis not in (0, 1):
            raise WorkerRefusal("hypothesis is invalid")
        private = task_family.production_placebo_private(seed, core)
        if task_family.commitment(private) != public["placebo_private_commitment"]:
            raise WorkerRefusal("placebo private commitment does not match public task")
        return _reply({
            "schema_version": FEEDBACK_SCHEMA,
            "trajectory_sha256": _sha(sealed["trajectory_commitment"]),
            "feedback_bit": int(private["placebo_bit"]),
        })
    if role == "score":
        value = _exact(request, {"schema_version", "kind", "public_task", "probe_challenge", "answer_token"})
        if value["schema_version"] != WORKER_SCHEMA or value["kind"] != "PROBE_SCORE":
            raise WorkerRefusal("score request kind is invalid")
        public = validate_separated_public(value["public_task"])
        core = task_family._validate_public_core(public["public_core"])
        private = task_family.production_evaluator_private(seed, core)
        if task_family.commitment(private) != public["evaluator_private_commitment"]:
            raise WorkerRefusal("evaluator private commitment does not match public task")
        hidden = task_family.production_hidden_answer(private, value["probe_challenge"], core)
        scored = evaluator.evaluate_probe_separated(
            public, value["probe_challenge"], hidden, value["answer_token"]
        )
        return _reply({
            "schema_version": SCORE_SCHEMA,
            "probe_challenge_commitment": scored["probe_challenge_commitment"],
            "score": scored["score"],
        })
    raise WorkerRefusal("worker role is invalid")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", choices=("outcome", "sham", "score"), required=True)
    parser.add_argument("--seed-file", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        raw = sys.stdin.buffer.read()
        request = parse_canonical(raw)
        result = handle_request(role=args.role, seed=_seed(args.seed_file), request=request)
        sys.stdout.buffer.write(canonical_bytes(result))
    except (OSError, ValueError, task_family.TaskFamilyError) as error:
        sys.stderr.write(f"PRE_G1_WORKER_REFUSAL:{type(error).__name__}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
