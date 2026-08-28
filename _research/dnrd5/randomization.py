"""Deterministic randomization contracts for the proposed DNRD-5 study.

This module does not execute model calls or create a scientific result.  It
turns a future-randomness value and a pre-observation study binding into a
fixed 300-block allocation plan.  Fork identities and per-fork call seeds are
derived independently of arm allocation so that treatment labels cannot alter
the preassigned randomness of a clone.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

from _research.dnrd5.plan_json import (
    CONTRACT_VERSION as PLAN_JSON_CONTRACT_VERSION,
    PlanJsonError,
    canonical_bytes as _plan_canonical_bytes,
    canonical_sha256 as _plan_canonical_sha256,
    parse_canonical as _parse_plan_canonical,
)


SCHEMA_VERSION = "hswm-dnrd5-randomization/v1"
MODEL_PROJECTION_SCHEMA = "hswm-dnrd5-model-randomization-projection/v1"
EVALUATOR_PROJECTION_SCHEMA = "hswm-dnrd5-evaluator-randomization-projection/v1"
CANONICAL_JSON_ENCODING = PLAN_JSON_CONTRACT_VERSION
BLOCK_COUNT = 300
BLOCK_ID_PREFIX = "DNRD5-BLOCK-"
ARMS = (
    "ACTIVE",
    "OUTCOME_INDEPENDENT_SHAM",
    "DELAYED_NO_CREDIT",
    "EXACT_W0_ROLLBACK",
)
CALLS_PER_BLOCK = 9
TOTAL_CALLS = BLOCK_COUNT * CALLS_PER_BLOCK
SCIENTIFIC_STATUS = "RANDOMIZATION_DERIVATION_ONLY_CHRONOLOGY_NOT_ENFORCED_NOT_EXECUTION_NOT_RESULT"
COMBINED_CUSTODY_STATUS = "COMBINED_CUSTODY_FIXTURE_NOT_PRODUCTION"
MODEL_PROJECTION_STATUS = "RANDOMIZATION_METADATA_EXCLUSION_TEMPLATE_ONLY"
EVALUATOR_PROJECTION_STATUS = "RANDOMIZATION_NONE_ARM_CLONE_ORDER_FREE"
_HEX_256_LENGTH = 64

_BLOCK_PLAN_KEYS = {
    "schema_version",
    "block_id",
    "canonical_json_encoding",
    "randomization_binding",
    "sealed_fork_projection",
    "assignment_receipt",
    "private_assignment",
    "call_schedule_receipt",
    "private_call_schedule",
    "model_visible_randomization_projection",
    "scientific_status",
}


class RandomizationValidationError(ValueError):
    """Raised when randomization material violates the frozen contract."""


def canonical_json_bytes(value: Any) -> bytes:
    """Encode the narrow JSON domain used by the randomization contract."""
    try:
        return _plan_canonical_bytes(value)
    except PlanJsonError as error:
        raise RandomizationValidationError("value is not canonical JSON encodable") from error


def canonical_json_sha256(value: Any) -> str:
    try:
        return _plan_canonical_sha256(value)
    except PlanJsonError as error:
        raise RandomizationValidationError("value is not canonical JSON encodable") from error


def expected_block_ids() -> tuple[str, ...]:
    return tuple(f"{BLOCK_ID_PREFIX}{index:04d}" for index in range(1, BLOCK_COUNT + 1))


def _require_sha256(value: str, field: str) -> str:
    if not isinstance(value, str) or len(value) != _HEX_256_LENGTH:
        raise RandomizationValidationError(f"{field} must be a lowercase SHA-256 hex string")
    try:
        decoded = bytes.fromhex(value)
    except ValueError as error:
        raise RandomizationValidationError(f"{field} must be a lowercase SHA-256 hex string") from error
    if decoded.hex() != value:
        raise RandomizationValidationError(f"{field} must be a lowercase SHA-256 hex string")
    return value


def _require_block_id(block_id: str) -> str:
    if not isinstance(block_id, str) or block_id not in set(expected_block_ids()):
        raise RandomizationValidationError("block_id is outside the exact ordered DNRD-5 universe")
    return block_id


def _derive(root: bytes, purpose: str, *parts: str) -> bytes:
    if not isinstance(purpose, str) or not purpose:
        raise RandomizationValidationError("derivation purpose must be nonempty")
    digest = hashlib.sha256()
    digest.update(SCHEMA_VERSION.encode("ascii"))
    for component in (purpose, *parts):
        encoded = component.encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
    digest.update(len(root).to_bytes(4, "big"))
    digest.update(root)
    return digest.digest()


def _uniform_below(root: bytes, purpose: str, upper: int, counter: int) -> tuple[int, int]:
    """Return an unbiased integer using SHA-256 rejection sampling."""
    if upper < 1:
        raise RandomizationValidationError("uniform upper bound must be positive")
    modulus = 1 << 256
    cutoff = modulus - (modulus % upper)
    while True:
        candidate = int.from_bytes(_derive(root, purpose, str(counter)), "big")
        counter += 1
        if candidate < cutoff:
            return candidate % upper, counter


def _permutation(items: Sequence[str], root: bytes, purpose: str) -> tuple[str, ...]:
    shuffled = list(items)
    counter = 0
    for index in range(len(shuffled) - 1, 0, -1):
        selected, counter = _uniform_below(root, purpose, index + 1, counter)
        shuffled[index], shuffled[selected] = shuffled[selected], shuffled[index]
    return tuple(shuffled)


def derive_clone_material(
    *, future_randomness_hex: str, study_binding_sha256: str, block_id: str
) -> tuple[dict[str, str], ...]:
    """Derive four opaque forks and their arm-independent call seed commitments."""
    entropy_hex = _require_sha256(future_randomness_hex, "future_randomness_hex")
    study_binding = _require_sha256(study_binding_sha256, "study_binding_sha256")
    checked_block_id = _require_block_id(block_id)
    root = bytes.fromhex(entropy_hex)
    block_root = _derive(root, "block-root", study_binding, checked_block_id)
    clones: list[dict[str, str]] = []
    for index in range(4):
        fork_material = _derive(block_root, "opaque-fork", str(index))
        fork_id = f"fork-{fork_material.hex()[:32]}"
        proposal_seed = _derive(block_root, "proposal-seed", fork_id).hex()
        probe_seed = _derive(block_root, "probe-seed", fork_id).hex()
        clones.append(
            {
                "fork_id": fork_id,
                "proposal_seed_sha256": hashlib.sha256(bytes.fromhex(proposal_seed)).hexdigest(),
                "probe_seed_sha256": hashlib.sha256(bytes.fromhex(probe_seed)).hexdigest(),
            }
        )
    if len({clone["fork_id"] for clone in clones}) != 4:
        raise RandomizationValidationError("derived opaque fork identifiers collided")
    return tuple(clones)


def derive_arm_assignment(
    *,
    future_randomness_hex: str,
    study_binding_sha256: str,
    block_id: str,
) -> dict[str, str]:
    """Assign arms to the one canonical fork order derived from frozen inputs."""
    entropy_hex = _require_sha256(future_randomness_hex, "future_randomness_hex")
    study_binding = _require_sha256(study_binding_sha256, "study_binding_sha256")
    checked_block_id = _require_block_id(block_id)
    clones = derive_clone_material(
        future_randomness_hex=entropy_hex,
        study_binding_sha256=study_binding,
        block_id=checked_block_id,
    )
    fork_ids = tuple(clone["fork_id"] for clone in clones)
    root = bytes.fromhex(entropy_hex)
    assignment_root = _derive(
        root,
        "arm-assignment",
        study_binding,
        checked_block_id,
        canonical_json_sha256(list(fork_ids)),
    )
    arm_order = _permutation(ARMS, assignment_root, "arm-permutation")
    return dict(zip(fork_ids, arm_order, strict=True))


def derive_call_schedule(
    *,
    future_randomness_hex: str,
    study_binding_sha256: str,
    block_id: str,
) -> tuple[dict[str, str], ...]:
    """Derive the immutable one-plus-four-plus-four call grammar for one block."""
    entropy_hex = _require_sha256(future_randomness_hex, "future_randomness_hex")
    study_binding = _require_sha256(study_binding_sha256, "study_binding_sha256")
    checked_block_id = _require_block_id(block_id)
    root = bytes.fromhex(entropy_hex)
    block_root = _derive(root, "block-root", study_binding, checked_block_id)
    clones = derive_clone_material(
        future_randomness_hex=entropy_hex,
        study_binding_sha256=study_binding,
        block_id=checked_block_id,
    )
    fork_ids = tuple(clone["fork_id"] for clone in clones)
    clone_by_id = {clone["fork_id"]: clone for clone in clones}
    schedule_root = _derive(
        root,
        "call-schedule",
        study_binding,
        checked_block_id,
        canonical_json_sha256(list(fork_ids)),
    )
    proposal_order = _permutation(fork_ids, schedule_root, "proposal-order")
    probe_order = _permutation(fork_ids, schedule_root, "probe-order")
    rows: list[dict[str, str]] = [
        {
            "call_id": f"{checked_block_id}:TRAJECTORY:0",
            "call_class": "PRE_OUTCOME_TRAJECTORY",
            "fork_id": "SHARED_W0",
            "rng_seed_sha256": hashlib.sha256(
                _derive(block_root, "trajectory-seed")
            ).hexdigest(),
        }
    ]
    rows.extend(
        {
            "call_id": f"{checked_block_id}:PROPOSAL:{index}",
            "call_class": "REVISION_PROPOSAL",
            "fork_id": fork_id,
            "rng_seed_sha256": clone_by_id[fork_id]["proposal_seed_sha256"],
        }
        for index, fork_id in enumerate(proposal_order, start=1)
    )
    rows.extend(
        {
            "call_id": f"{checked_block_id}:PROBE:{index}",
            "call_class": "FRESH_PROBE",
            "fork_id": fork_id,
            "rng_seed_sha256": clone_by_id[fork_id]["probe_seed_sha256"],
        }
        for index, fork_id in enumerate(probe_order, start=1)
    )
    return tuple(rows)


def derive_block_plan(
    *, future_randomness_hex: str, study_binding_sha256: str, block_id: str
) -> dict[str, Any]:
    """Build one private allocation record plus its model-safe public projection."""
    clones = derive_clone_material(
        future_randomness_hex=future_randomness_hex,
        study_binding_sha256=study_binding_sha256,
        block_id=block_id,
    )
    assignment = derive_arm_assignment(
        future_randomness_hex=future_randomness_hex,
        study_binding_sha256=study_binding_sha256,
        block_id=block_id,
    )
    schedule = derive_call_schedule(
        future_randomness_hex=future_randomness_hex,
        study_binding_sha256=study_binding_sha256,
        block_id=block_id,
    )
    entropy_hex = _require_sha256(future_randomness_hex, "future_randomness_hex")
    study_binding = _require_sha256(study_binding_sha256, "study_binding_sha256")
    checked_block_id = _require_block_id(block_id)
    randomization_binding = {
        "derivation_version": SCHEMA_VERSION,
        "future_randomness_sha256": hashlib.sha256(bytes.fromhex(entropy_hex)).hexdigest(),
        "study_binding_sha256": study_binding,
    }
    sealed_fork_projection = {
        "schema_version": SCHEMA_VERSION,
        "block_id": checked_block_id,
        "forks": list(clones),
    }
    assignment_receipt = {
        "schema_version": SCHEMA_VERSION,
        "block_id": checked_block_id,
        "sealed_fork_projection_sha256": canonical_json_sha256(sealed_fork_projection),
        "assignment_commitment_sha256": canonical_json_sha256(assignment),
    }
    call_schedule_receipt = {
        "schema_version": SCHEMA_VERSION,
        "block_id": checked_block_id,
        "sealed_fork_projection_sha256": canonical_json_sha256(sealed_fork_projection),
        "call_schedule_commitment_sha256": canonical_json_sha256(list(schedule)),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "block_id": checked_block_id,
        "canonical_json_encoding": CANONICAL_JSON_ENCODING,
        "randomization_binding": randomization_binding,
        "sealed_fork_projection": sealed_fork_projection,
        "assignment_receipt": assignment_receipt,
        "private_assignment": assignment,
        "call_schedule_receipt": call_schedule_receipt,
        "private_call_schedule": list(schedule),
        "model_visible_randomization_projection": {
            "schema_version": SCHEMA_VERSION,
            "block_id": checked_block_id,
            "call_budget": CALLS_PER_BLOCK,
            "projection_status": "RANDOMIZATION_METADATA_EXCLUSION_TEMPLATE_ONLY",
        },
        "scientific_status": SCIENTIFIC_STATUS,
    }


def validate_block_plan(
    plan: Mapping[str, Any], *, future_randomness_hex: str, study_binding_sha256: str
) -> dict[str, Any]:
    """Validate one plan by rederiving it from the pinned public inputs."""
    if type(plan) is not dict or set(plan) != _BLOCK_PLAN_KEYS:
        raise RandomizationValidationError("block plan has an unexpected key set")
    if plan["schema_version"] != SCHEMA_VERSION:
        raise RandomizationValidationError("block plan schema version mismatch")
    block_id = _require_block_id(plan["block_id"])
    binding = plan["randomization_binding"]
    sealed_forks = plan["sealed_fork_projection"]
    assignment_receipt = plan["assignment_receipt"]
    schedule_receipt = plan["call_schedule_receipt"]
    assignment = plan["private_assignment"]
    schedule = plan["private_call_schedule"]
    model_input = plan["model_visible_randomization_projection"]
    if type(binding) is not dict or set(binding) != {
        "derivation_version",
        "future_randomness_sha256",
        "study_binding_sha256",
    }:
        raise RandomizationValidationError("randomization binding is malformed")
    _require_sha256(binding["future_randomness_sha256"], "future_randomness_sha256")
    _require_sha256(binding["study_binding_sha256"], "study_binding_sha256")
    if binding["derivation_version"] != SCHEMA_VERSION:
        raise RandomizationValidationError("randomization derivation version mismatch")
    if type(sealed_forks) is not dict or set(sealed_forks) != {
        "schema_version",
        "block_id",
        "forks",
    }:
        raise RandomizationValidationError("sealed fork projection is malformed")
    if sealed_forks["schema_version"] != SCHEMA_VERSION or sealed_forks["block_id"] != block_id:
        raise RandomizationValidationError("sealed fork projection identity mismatch")
    clones = sealed_forks["forks"]
    if not isinstance(clones, list) or len(clones) != 4:
        raise RandomizationValidationError("sealed projection must bind exactly four forks")
    clone_keys = {"fork_id", "proposal_seed_sha256", "probe_seed_sha256"}
    if any(type(clone) is not dict or set(clone) != clone_keys for clone in clones):
        raise RandomizationValidationError("sealed fork record is malformed")
    for clone in clones:
        if not isinstance(clone["fork_id"], str) or not clone["fork_id"].startswith("fork-"):
            raise RandomizationValidationError("sealed fork identifier is malformed")
        _require_sha256(clone["proposal_seed_sha256"], "proposal_seed_sha256")
        _require_sha256(clone["probe_seed_sha256"], "probe_seed_sha256")
    fork_ids = [clone["fork_id"] for clone in clones]
    if len(fork_ids) != 4 or len(set(fork_ids)) != 4:
        raise RandomizationValidationError("sealed projection does not contain four distinct forks")
    if not isinstance(assignment, Mapping) or set(assignment) != set(fork_ids) or set(assignment.values()) != set(ARMS):
        raise RandomizationValidationError("private assignment is not a complete four-arm permutation")
    if type(assignment_receipt) is not dict or set(assignment_receipt) != {
        "schema_version",
        "block_id",
        "sealed_fork_projection_sha256",
        "assignment_commitment_sha256",
    }:
        raise RandomizationValidationError("assignment receipt is malformed")
    if assignment_receipt["assignment_commitment_sha256"] != canonical_json_sha256(dict(assignment)):
        raise RandomizationValidationError("assignment commitment mismatch")
    if assignment_receipt["sealed_fork_projection_sha256"] != canonical_json_sha256(sealed_forks):
        raise RandomizationValidationError("assignment does not bind the sealed fork projection")
    if not isinstance(schedule, list) or len(schedule) != CALLS_PER_BLOCK:
        raise RandomizationValidationError("block must contain exactly nine scheduled calls")
    if type(schedule_receipt) is not dict or set(schedule_receipt) != {
        "schema_version",
        "block_id",
        "sealed_fork_projection_sha256",
        "call_schedule_commitment_sha256",
    }:
        raise RandomizationValidationError("call schedule receipt is malformed")
    if schedule_receipt["call_schedule_commitment_sha256"] != canonical_json_sha256(schedule):
        raise RandomizationValidationError("call schedule commitment mismatch")
    if schedule_receipt["sealed_fork_projection_sha256"] != canonical_json_sha256(sealed_forks):
        raise RandomizationValidationError("call schedule does not bind the sealed fork projection")
    if any(type(row) is not dict or set(row) != {"call_id", "call_class", "fork_id", "rng_seed_sha256"} for row in schedule):
        raise RandomizationValidationError("call schedule row is malformed")
    for row in schedule:
        _require_sha256(row["rng_seed_sha256"], "call rng_seed_sha256")
    classes = [row["call_class"] for row in schedule]
    if classes != ["PRE_OUTCOME_TRAJECTORY", *("REVISION_PROPOSAL",) * 4, *("FRESH_PROBE",) * 4]:
        raise RandomizationValidationError("call schedule violates the one-plus-four-plus-four grammar")
    if len({row["call_id"] for row in schedule}) != CALLS_PER_BLOCK:
        raise RandomizationValidationError("call schedule repeats a call ID")
    proposal_forks = [row["fork_id"] for row in schedule if row["call_class"] == "REVISION_PROPOSAL"]
    probe_forks = [row["fork_id"] for row in schedule if row["call_class"] == "FRESH_PROBE"]
    if set(proposal_forks) != set(fork_ids) or set(probe_forks) != set(fork_ids):
        raise RandomizationValidationError("each fork must receive exactly one proposal and one probe call")
    if not isinstance(model_input, Mapping) or set(model_input) != {
        "schema_version", "block_id", "call_budget", "projection_status"
    }:
        raise RandomizationValidationError("model input projection has an unexpected key set")
    if model_input != {
        "schema_version": SCHEMA_VERSION,
        "block_id": block_id,
        "call_budget": CALLS_PER_BLOCK,
        "projection_status": "RANDOMIZATION_METADATA_EXCLUSION_TEMPLATE_ONLY",
    }:
        raise RandomizationValidationError("model input projection is not canonical")
    model_bytes = canonical_json_bytes(model_input)
    if any(arm.encode("ascii") in model_bytes for arm in ARMS) or any(
        fork_id.encode("ascii") in model_bytes for fork_id in fork_ids
    ):
        raise RandomizationValidationError("model input projection leaks an arm label or fork identity")
    if plan["scientific_status"] != SCIENTIFIC_STATUS:
        raise RandomizationValidationError("randomization plan overclaims scientific status")
    expected = derive_block_plan(
        future_randomness_hex=future_randomness_hex,
        study_binding_sha256=study_binding_sha256,
        block_id=block_id,
    )
    if canonical_json_bytes(plan) != canonical_json_bytes(expected):
        raise RandomizationValidationError(
            "block plan does not independently rederive from the pinned randomness and study binding"
        )
    return _parse_plan_canonical(canonical_json_bytes(dict(plan)))


def derive_study_plan(*, future_randomness_hex: str, study_binding_sha256: str) -> dict[str, Any]:
    """Expand the exact ordered 300-block universe and its 2,700 call slots."""
    blocks = [
        derive_block_plan(
            future_randomness_hex=future_randomness_hex,
            study_binding_sha256=study_binding_sha256,
            block_id=block_id,
        )
        for block_id in expected_block_ids()
    ]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "block_ids_sha256": canonical_json_sha256(list(expected_block_ids())),
        "blocks": blocks,
        "block_count": BLOCK_COUNT,
        "total_call_slots": TOTAL_CALLS,
        "scientific_status": SCIENTIFIC_STATUS,
    }
    return {**payload, "study_plan_sha256": canonical_json_sha256(payload)}


def validate_study_plan(
    plan: Mapping[str, Any], *, future_randomness_hex: str, study_binding_sha256: str
) -> dict[str, Any]:
    """Rederive and compare the entire 300-block allocation without exclusions."""
    if type(plan) is not dict or set(plan) != {
        "schema_version",
        "block_ids_sha256",
        "blocks",
        "block_count",
        "total_call_slots",
        "scientific_status",
        "study_plan_sha256",
    }:
        raise RandomizationValidationError("study plan has an unexpected key set")
    if type(plan["blocks"]) is not list or len(plan["blocks"]) != BLOCK_COUNT:
        raise RandomizationValidationError("study plan must contain exactly 300 blocks")
    if [block.get("block_id") for block in plan["blocks"] if isinstance(block, Mapping)] != list(expected_block_ids()):
        raise RandomizationValidationError("study blocks do not equal the exact ordered universe")
    payload = {key: value for key, value in plan.items() if key != "study_plan_sha256"}
    if plan["study_plan_sha256"] != canonical_json_sha256(payload):
        raise RandomizationValidationError("study plan commitment mismatch")
    expected = derive_study_plan(
        future_randomness_hex=future_randomness_hex,
        study_binding_sha256=study_binding_sha256,
    )
    if canonical_json_bytes(plan) != canonical_json_bytes(expected):
        raise RandomizationValidationError(
            "study plan does not independently rederive from the pinned randomness and study binding"
        )
    return _parse_plan_canonical(canonical_json_bytes(dict(plan)))


def extract_private_custodian_view(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Project a structurally exact combined fixture by value for its custodian.

    This function does not rederive the plan because it intentionally receives
    no future-randomness preimage.  Callers must first use ``validate_block_plan``
    at the derivation boundary; the returned status prevents treating this
    in-process projection as a production access-control capability.
    """
    if type(plan) is not dict or set(plan) != _BLOCK_PLAN_KEYS:
        raise RandomizationValidationError("combined plan has an unexpected key set")
    required = (
        "schema_version",
        "block_id",
        "randomization_binding",
        "sealed_fork_projection",
        "assignment_receipt",
        "private_assignment",
        "call_schedule_receipt",
        "private_call_schedule",
    )
    view = {key: plan[key] for key in required}
    view["custody_status"] = COMBINED_CUSTODY_STATUS
    return _parse_plan_canonical(canonical_json_bytes(view))


def derive_model_visible_projection(study_binding_sha256: str, block_id: str) -> dict[str, Any]:
    """Allocation-free request metadata; no entropy, arm, fork, order, or seed data."""
    study_binding = _require_sha256(study_binding_sha256, "study_binding_sha256")
    checked = _require_block_id(block_id)
    return {
        "schema_version": MODEL_PROJECTION_SCHEMA,
        "study_binding_sha256": study_binding,
        "block_id": checked,
        "call_budget": CALLS_PER_BLOCK,
        "projection_status": MODEL_PROJECTION_STATUS,
    }


def validate_model_visible_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    expected = {
        "schema_version",
        "study_binding_sha256",
        "block_id",
        "call_budget",
        "projection_status",
    }
    if type(value) is not dict or set(value) != expected:
        raise RandomizationValidationError("model projection has an unexpected key set")
    if (
        value["schema_version"] != MODEL_PROJECTION_SCHEMA
        or value["study_binding_sha256"]
        != _require_sha256(value["study_binding_sha256"], "study_binding_sha256")
        or value["block_id"] != _require_block_id(value["block_id"])
        or value["call_budget"] != CALLS_PER_BLOCK
        or value["projection_status"] != MODEL_PROJECTION_STATUS
    ):
        raise RandomizationValidationError("model projection is not canonical")
    encoded = canonical_json_bytes(value)
    if (
        any(arm.encode("ascii") in encoded for arm in ARMS)
        or b"fork-" in encoded
        or b"assignment" in encoded
    ):
        raise RandomizationValidationError("model projection leaks private allocation material")
    return _parse_plan_canonical(encoded)


def derive_evaluator_visible_projection(study_binding_sha256: str, block_id: str) -> dict[str, Any]:
    return {
        "schema_version": EVALUATOR_PROJECTION_SCHEMA,
        "study_binding_sha256": _require_sha256(
            study_binding_sha256, "study_binding_sha256"
        ),
        "block_id": _require_block_id(block_id),
        "projection_status": EVALUATOR_PROJECTION_STATUS,
    }


def validate_evaluator_visible_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    expected = {
        "schema_version",
        "study_binding_sha256",
        "block_id",
        "projection_status",
    }
    if type(value) is not dict or set(value) != expected:
        raise RandomizationValidationError("evaluator projection has an unexpected key set")
    if (
        value["schema_version"] != EVALUATOR_PROJECTION_SCHEMA
        or value["study_binding_sha256"]
        != _require_sha256(value["study_binding_sha256"], "study_binding_sha256")
        or value["block_id"] != _require_block_id(value["block_id"])
        or value["projection_status"] != EVALUATOR_PROJECTION_STATUS
    ):
        raise RandomizationValidationError("evaluator projection is not canonical")
    encoded = canonical_json_bytes(value)
    if (
        any(arm.encode("ascii") in encoded for arm in ARMS)
        or b"fork-" in encoded
        or b"assignment" in encoded
    ):
        raise RandomizationValidationError("evaluator projection leaks private allocation material")
    return _parse_plan_canonical(encoded)
