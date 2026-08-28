"""Independent DNRD-5 v1 randomization consumer.

This deliberately does not import the randomization producer: it rederives
the frozen allocation bytes from pinned inputs.  Validation is allocation
integrity only--it is not chronology, isolation, execution, or scientific
evidence.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

from _research.dnrd5.independent_plan_json import (
    CONTRACT_VERSION as PLAN_JSON_CONTRACT_VERSION,
    IndependentPlanJsonError,
    canonical_bytes as _independent_plan_bytes,
    canonical_sha256 as _independent_plan_sha256,
    parse_canonical as _parse_independent_plan,
)


SCHEMA_VERSION = "hswm-dnrd5-randomization/v1"
CANONICAL_JSON_ENCODING = PLAN_JSON_CONTRACT_VERSION
BLOCK_COUNT = 300
BLOCK_ID_PREFIX = "DNRD5-BLOCK-"
ARMS = ("ACTIVE", "OUTCOME_INDEPENDENT_SHAM", "DELAYED_NO_CREDIT", "EXACT_W0_ROLLBACK")
CALLS_PER_BLOCK = 9
TOTAL_CALLS = 2700
TERMINAL_MARKER = "INDEPENDENT_RANDOMIZATION_CONSUMER_ONLY_NOT_CHRONOLOGY_NOT_ISOLATION_NOT_EXECUTION_NOT_SCIENTIFIC_RESULT"


class IndependentRandomizationRefusal(ValueError):
    """Pinned allocation material does not exactly rederive."""


def canonical_json_bytes(value: Any) -> bytes:
    try:
        return _independent_plan_bytes(value)
    except IndependentPlanJsonError as error:
        raise IndependentRandomizationRefusal("value is not canonical JSON") from error


def canonical_json_sha256(value: Any) -> str:
    try:
        return _independent_plan_sha256(value)
    except IndependentPlanJsonError as error:
        raise IndependentRandomizationRefusal("value is not canonical JSON") from error


def expected_block_ids() -> tuple[str, ...]:
    return tuple(f"{BLOCK_ID_PREFIX}{n:04d}" for n in range(1, BLOCK_COUNT + 1))


def _sha(value: Any, label: str) -> str:
    if type(value) is not str or len(value) != 64:
        raise IndependentRandomizationRefusal(f"{label} must be lowercase SHA-256 hex")
    try:
        raw = bytes.fromhex(value)
    except ValueError as error:
        raise IndependentRandomizationRefusal(f"{label} must be lowercase SHA-256 hex") from error
    if raw.hex() != value:
        raise IndependentRandomizationRefusal(f"{label} must be lowercase SHA-256 hex")
    return value


def _block(value: Any) -> str:
    if type(value) is not str or value not in expected_block_ids():
        raise IndependentRandomizationRefusal("block_id is outside exact ordered universe")
    return value


def _derive(root: bytes, purpose: str, *parts: str) -> bytes:
    h = hashlib.sha256()
    h.update(SCHEMA_VERSION.encode("ascii"))
    for part in (purpose, *parts):
        if type(part) is not str or not part:
            raise IndependentRandomizationRefusal("derivation domain is malformed")
        encoded = part.encode("utf-8")
        h.update(len(encoded).to_bytes(4, "big")); h.update(encoded)
    h.update(len(root).to_bytes(4, "big")); h.update(root)
    return h.digest()


def _below(root: bytes, purpose: str, upper: int, counter: int) -> tuple[int, int]:
    if type(upper) is not int or upper < 1:
        raise IndependentRandomizationRefusal("invalid permutation bound")
    cutoff = (1 << 256) - ((1 << 256) % upper)
    while True:
        candidate = int.from_bytes(_derive(root, purpose, str(counter)), "big")
        counter += 1
        if candidate < cutoff:
            return candidate % upper, counter


def _permute(items: Sequence[str], root: bytes, purpose: str) -> tuple[str, ...]:
    output = list(items); counter = 0
    for pos in range(len(output) - 1, 0, -1):
        chosen, counter = _below(root, purpose, pos + 1, counter)
        output[pos], output[chosen] = output[chosen], output[pos]
    return tuple(output)


def _inputs(future_randomness_hex: str, study_binding_sha256: str, block_id: str) -> tuple[bytes, str, str]:
    return bytes.fromhex(_sha(future_randomness_hex, "future_randomness_hex")), _sha(study_binding_sha256, "study_binding_sha256"), _block(block_id)


def derive_block_plan(*, future_randomness_hex: str, study_binding_sha256: str, block_id: str) -> dict[str, Any]:
    """Reconstruct one v1 plan without accepting caller-selected fork order."""
    root, binding, block = _inputs(future_randomness_hex, study_binding_sha256, block_id)
    block_root = _derive(root, "block-root", binding, block)
    clones = []
    for index in range(4):
        fork = f"fork-{_derive(block_root, 'opaque-fork', str(index)).hex()[:32]}"
        proposal = _derive(block_root, "proposal-seed", fork)
        probe = _derive(block_root, "probe-seed", fork)
        clones.append({"fork_id": fork, "proposal_seed_sha256": hashlib.sha256(proposal).hexdigest(), "probe_seed_sha256": hashlib.sha256(probe).hexdigest()})
    fork_ids = tuple(row["fork_id"] for row in clones)
    if len(set(fork_ids)) != 4:
        raise IndependentRandomizationRefusal("fork collision")
    forks = {"schema_version": SCHEMA_VERSION, "block_id": block, "forks": clones}
    fork_digest = canonical_json_sha256(forks)
    assignment_root = _derive(root, "arm-assignment", binding, block, canonical_json_sha256(list(fork_ids)))
    assignment = dict(zip(fork_ids, _permute(ARMS, assignment_root, "arm-permutation"), strict=True))
    schedule_root = _derive(root, "call-schedule", binding, block, canonical_json_sha256(list(fork_ids)))
    by_fork = {item["fork_id"]: item for item in clones}
    schedule = [{"call_id": f"{block}:TRAJECTORY:0", "call_class": "PRE_OUTCOME_TRAJECTORY", "fork_id": "SHARED_W0", "rng_seed_sha256": hashlib.sha256(_derive(block_root, "trajectory-seed")).hexdigest()}]
    schedule += [{"call_id": f"{block}:PROPOSAL:{i}", "call_class": "REVISION_PROPOSAL", "fork_id": fork, "rng_seed_sha256": by_fork[fork]["proposal_seed_sha256"]} for i, fork in enumerate(_permute(fork_ids, schedule_root, "proposal-order"), 1)]
    schedule += [{"call_id": f"{block}:PROBE:{i}", "call_class": "FRESH_PROBE", "fork_id": fork, "rng_seed_sha256": by_fork[fork]["probe_seed_sha256"]} for i, fork in enumerate(_permute(fork_ids, schedule_root, "probe-order"), 1)]
    binding_record = {"derivation_version": SCHEMA_VERSION, "future_randomness_sha256": hashlib.sha256(root).hexdigest(), "study_binding_sha256": binding}
    return {"schema_version": SCHEMA_VERSION, "block_id": block, "canonical_json_encoding": CANONICAL_JSON_ENCODING, "randomization_binding": binding_record, "sealed_fork_projection": forks, "assignment_receipt": {"schema_version": SCHEMA_VERSION, "block_id": block, "sealed_fork_projection_sha256": fork_digest, "assignment_commitment_sha256": canonical_json_sha256(assignment)}, "private_assignment": assignment, "call_schedule_receipt": {"schema_version": SCHEMA_VERSION, "block_id": block, "sealed_fork_projection_sha256": fork_digest, "call_schedule_commitment_sha256": canonical_json_sha256(schedule)}, "private_call_schedule": schedule, "model_visible_randomization_projection": {"schema_version": SCHEMA_VERSION, "block_id": block, "call_budget": CALLS_PER_BLOCK, "projection_status": "RANDOMIZATION_METADATA_EXCLUSION_TEMPLATE_ONLY"}, "scientific_status": "RANDOMIZATION_DERIVATION_ONLY_CHRONOLOGY_NOT_ENFORCED_NOT_EXECUTION_NOT_RESULT"}


def derive_study_plan(*, future_randomness_hex: str, study_binding_sha256: str) -> dict[str, Any]:
    """Reconstruct all exact blocks and their 2,700 preassigned call slots."""
    blocks = [derive_block_plan(future_randomness_hex=future_randomness_hex, study_binding_sha256=study_binding_sha256, block_id=block) for block in expected_block_ids()]
    payload = {"schema_version": SCHEMA_VERSION, "block_ids_sha256": canonical_json_sha256(list(expected_block_ids())), "blocks": blocks, "block_count": BLOCK_COUNT, "total_call_slots": TOTAL_CALLS, "scientific_status": "RANDOMIZATION_DERIVATION_ONLY_CHRONOLOGY_NOT_ENFORCED_NOT_EXECUTION_NOT_RESULT"}
    return {**payload, "study_plan_sha256": canonical_json_sha256(payload)}


def validate_study_plan(plan: Mapping[str, Any], *, future_randomness_hex: str, study_binding_sha256: str) -> dict[str, Any]:
    """Fail closed on any reordering, reassignment, schedule, or seed mutation."""
    required = {"schema_version", "block_ids_sha256", "blocks", "block_count", "total_call_slots", "scientific_status", "study_plan_sha256"}
    if type(plan) is not dict or set(plan) != required:
        raise IndependentRandomizationRefusal("study plan key set drifted")
    if plan.get("scientific_status") != "RANDOMIZATION_DERIVATION_ONLY_CHRONOLOGY_NOT_ENFORCED_NOT_EXECUTION_NOT_RESULT":
        raise IndependentRandomizationRefusal("scientific status overclaim")
    expected = derive_study_plan(future_randomness_hex=future_randomness_hex, study_binding_sha256=study_binding_sha256)
    if canonical_json_bytes(plan) != canonical_json_bytes(expected):
        raise IndependentRandomizationRefusal("study plan does not exactly rederive from pinned inputs")
    return _parse_independent_plan(canonical_json_bytes(plan))
