"""Pure DNRD-5 two-hypothesis task construction.

This module creates commitments and validates byte-shaped task objects only.  It
does not call a model, evaluate an occurrence, admit state, or claim learning.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping


BLOCK_COUNT = 300
SEED_BYTES = 32
DOMAIN = b"HSWM-DNRD-5-TWO-HYPOTHESIS-TASK-V1"
PUBLIC_SCHEMA = "hswm-dnrd5-public-task/v1"
PUBLIC_CORE_SCHEMA = "hswm-dnrd5-public-task-core/v1"
EVALUATOR_PRIVATE_SCHEMA = "hswm-dnrd5-evaluator-private/v1"
PROBE_PRIVATE_SCHEMA = "hswm-dnrd5-probe-private/v1"
PLACEBO_PRIVATE_SCHEMA = "hswm-dnrd5-placebo-private/v1"
TRAINING_RESPONSE_SCHEMA = "hswm-dnrd5-training-response/v1"
SEALED_TRAINING_RESPONSE_SCHEMA = "hswm-dnrd5-sealed-training-response/v1"
OUTCOME_RECEIPT_SCHEMA = "hswm-dnrd5-outcome-receipt/v1"
PROPOSAL_FEEDBACK_SCHEMA = "hswm-dnrd5-proposal-feedback-projection/v1"
PROBE_OPENING_SCHEMA = "hswm-dnrd5-probe-opening/v1"
SEALED_PROBE_RESPONSE_SCHEMA = "hswm-dnrd5-sealed-probe-response/v1"
PROBE_OUTCOME_SCHEMA = "hswm-dnrd5-probe-outcome/v1"
BUNDLE_AUDIT_RECEIPT_SCHEMA = "hswm-dnrd5-bundle-audit-receipt/v1"
SEPARATED_PUBLIC_SCHEMA = "hswm-dnrd5-public-task-separated/v1"
SEPARATED_EVALUATOR_PRIVATE_SCHEMA = "hswm-dnrd5-evaluator-private-separated/v1"
SEPARATED_PROBE_CHALLENGE_SCHEMA = "hswm-dnrd5-probe-challenge-separated/v1"
SEPARATED_HIDDEN_ANSWER_SCHEMA = "hswm-dnrd5-hidden-answer-separated/v1"
SEPARATED_PLACEBO_PRIVATE_SCHEMA = "hswm-dnrd5-placebo-private-separated/v1"
SEPARATED_PROBE_OUTCOME_SCHEMA = "hswm-dnrd5-probe-outcome-separated/v1"
EVALUATOR_DERIVATION_DOMAIN = "evaluator-theta/v1"
PROBE_DERIVATION_DOMAIN = "probe-challenge/v1"
PLACEBO_DERIVATION_DOMAIN = "placebo/v1"
PROBE_OPENING_STATUS = "COMMITMENT_ONLY_REQUIRES_LIFECYCLE_CHRONOLOGY_GATE"
BUNDLE_AUDIT_STATUS = (
    "CROSS_PRIVATE_CONSISTENCY_CHECKED_CONTENT_HASH_ONLY_"
    "REQUIRES_CANONICAL_CUSTODY_NOT_AUTHORIZATION"
)
THETA_PLACEBO_STATUS = "DOMAIN_SEPARATED_SHA256_PRF_COMPUTATIONAL_CONCEALMENT_NOT_CONDITIONAL_INDEPENDENCE_PROOF"
MECHANISM_UNIQUENESS_STATUS = "TWO_HYPOTHESIS_TASK_NOT_EVIDENCE_OF_UNIQUE_MACROPLASTICITY_MECHANISM"
COMBINED_FIXTURE_STATUS = "COMBINED_FIXTURE_NOT_PRODUCTION_CUSTODY_OR_INDEPENDENCE_EVIDENCE"
TOKEN_RE = re.compile(r"^nonce-[0-9a-f]{16}$", re.ASCII)
BLOCK_ID_RE = re.compile(r"^DNRD5-BLOCK-(?:0(?:00[1-9]|0[1-9][0-9]|[12][0-9]{2})|0300)$", re.ASCII)


class TaskFamilyError(ValueError):
    """Raised when a DNRD-5 task or receipt violates its pure contract."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def commitment(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _derive(seed: bytes, block_index: int, label: str) -> bytes:
    if type(seed) is not bytes or len(seed) != SEED_BYTES:
        raise TaskFamilyError(f"seed must be exactly {SEED_BYTES} bytes")
    if type(block_index) is not int or not 0 <= block_index < BLOCK_COUNT:
        raise TaskFamilyError(f"block_index must lie in [0, {BLOCK_COUNT})")
    return hashlib.sha256(
        DOMAIN + b"\0" + seed + b"\0" + f"block:{block_index:03d}:{label}".encode("ascii")
    ).digest()


def _token(seed: bytes, block_index: int, label: str) -> str:
    return "nonce-" + _derive(seed, block_index, label).hex()[:16]


def _uniform_below(seed: bytes, block_index: int, label: str, upper: int) -> int:
    """Domain-separated SHA-256 rejection sampling, with no modulo bias."""
    if type(upper) is not int or upper < 1:
        raise TaskFamilyError("uniform upper bound must be a positive integer")
    cutoff = 256 - (256 % upper)
    counter = 0
    while True:
        value = _derive(seed, block_index, f"{label}:rejection:{counter}")[0]
        counter += 1
        if value < cutoff:
            return value % upper


def _exact(value: object, expected: set[str], label: str) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != expected:
        raise TaskFamilyError(f"{label} has unexpected or missing fields")
    return value


def _string(value: object, label: str) -> str:
    if type(value) is not str or not value:
        raise TaskFamilyError(f"{label} must be a nonempty string")
    return value


def _bit(value: object, label: str) -> int:
    if type(value) is not int or value not in (0, 1):
        raise TaskFamilyError(f"{label} must be integer 0 or 1")
    return value


def _sha(value: object, label: str) -> str:
    result = _string(value, label)
    if len(result) != 64 or any(char not in "0123456789abcdef" for char in result):
        raise TaskFamilyError(f"{label} must be lowercase SHA-256")
    return result


def _token_value(value: object, label: str) -> str:
    result = _string(value, label)
    if TOKEN_RE.fullmatch(result) is None:
        raise TaskFamilyError(f"{label} must be a fixed-width nonce token")
    return result


def _block_id(index: int) -> str:
    return f"DNRD5-BLOCK-{index + 1:04d}"


def _mapping(value: object, inputs: list[str], outputs: list[str], label: str) -> dict[str, str]:
    if type(value) is not dict or set(value) != set(inputs):
        raise TaskFamilyError(f"{label} must map exactly the public inputs")
    parsed = {key: _token_value(child, f"{label}[{key}]") for key, child in value.items()}
    if set(parsed.values()) != set(outputs) or len(set(parsed.values())) != len(outputs):
        raise TaskFamilyError(f"{label} must be a permutation of public outputs")
    return parsed


def _validate_public_core(value: object) -> dict[str, Any]:
    core = _exact(
        value,
        {"schema_version", "block_id", "seed_commitment", "inputs", "outputs", "h0", "h1", "train_input"},
        "public_core",
    )
    if core["schema_version"] != PUBLIC_CORE_SCHEMA:
        raise TaskFamilyError("wrong public core schema")
    block_id = _string(core["block_id"], "public_core.block_id")
    if BLOCK_ID_RE.fullmatch(block_id) is None:
        raise TaskFamilyError("public_core.block_id must use DNRD5-BLOCK-0001 through DNRD5-BLOCK-0300")
    _sha(core["seed_commitment"], "public_core.seed_commitment")
    if type(core["inputs"]) is not list or type(core["outputs"]) is not list:
        raise TaskFamilyError("public core inputs and outputs must be lists")
    inputs = [_token_value(item, "public_core.input") for item in core["inputs"]]
    outputs = [_token_value(item, "public_core.output") for item in core["outputs"]]
    if len(inputs) != 4 or len(outputs) != 4 or len(set(inputs)) != 4 or len(set(outputs)) != 4:
        raise TaskFamilyError("public core needs four distinct fixed-width inputs and outputs")
    if inputs != sorted(inputs) or outputs != sorted(outputs):
        raise TaskFamilyError("public core token arrays must be canonically sorted")
    h0 = _mapping(core["h0"], inputs, outputs, "public_core.h0")
    h1 = _mapping(core["h1"], inputs, outputs, "public_core.h1")
    if any(h0[input_token] == h1[input_token] for input_token in inputs):
        raise TaskFamilyError("h0 and h1 must differ pointwise")
    train_input = _token_value(core["train_input"], "public_core.train_input")
    if train_input not in inputs:
        raise TaskFamilyError("train_input must be public input")
    return {
        "schema_version": PUBLIC_CORE_SCHEMA,
        "block_id": block_id,
        "seed_commitment": core["seed_commitment"],
        "inputs": inputs,
        "outputs": outputs,
        "h0": h0,
        "h1": h1,
        "train_input": train_input,
    }


def public_core(public_task: Mapping[str, Any]) -> dict[str, Any]:
    public = _exact(
        public_task,
        {
            "schema_version", "block_id", "seed_commitment", "public_core", "public_core_commitment",
            "evaluator_private_commitment", "probe_private_commitment", "placebo_private_commitment",
        },
        "public_task",
    )
    if public["schema_version"] != PUBLIC_SCHEMA:
        raise TaskFamilyError("wrong public task schema")
    core = _validate_public_core(public["public_core"])
    if public["block_id"] != core["block_id"] or public["seed_commitment"] != core["seed_commitment"]:
        raise TaskFamilyError("public task/core identity mismatch")
    if public["public_core_commitment"] != commitment(core):
        raise TaskFamilyError("public core commitment mismatch")
    for field in ("evaluator_private_commitment", "probe_private_commitment", "placebo_private_commitment"):
        _sha(public[field], field)
    return core


def _private_record(value: object, expected_schema: str, public: Mapping[str, Any], label: str) -> Mapping[str, Any]:
    core = public_core(public)
    expected = {"schema_version", "block_id", "public_core_commitment", "private_canary"}
    if expected_schema == EVALUATOR_PRIVATE_SCHEMA:
        expected |= {"theta"}
    elif expected_schema == PROBE_PRIVATE_SCHEMA:
        expected |= {"probe_input", "probe_answer", "probe_identity"}
    elif expected_schema == PLACEBO_PRIVATE_SCHEMA:
        expected |= {"placebo_bit"}
    record = _exact(value, expected, label)
    if record["schema_version"] != expected_schema or record["block_id"] != core["block_id"]:
        raise TaskFamilyError(f"{label} schema or block mismatch")
    if record["public_core_commitment"] != commitment(core):
        raise TaskFamilyError(f"{label} public core commitment mismatch")
    _token_value(record["private_canary"], f"{label}.private_canary")
    if expected_schema == EVALUATOR_PRIVATE_SCHEMA:
        _bit(record["theta"], f"{label}.theta")
    elif expected_schema == PROBE_PRIVATE_SCHEMA:
        _token_value(record["probe_input"], f"{label}.probe_input")
        _token_value(record["probe_answer"], f"{label}.probe_answer")
        _token_value(record["probe_identity"], f"{label}.probe_identity")
        if record["probe_input"] not in core["inputs"] or record["probe_input"] == core["train_input"]:
            raise TaskFamilyError(f"{label}.probe_input must be a held-out public-domain input")
        if record["probe_answer"] not in core["outputs"]:
            raise TaskFamilyError(f"{label}.probe_answer must be a public-domain output token")
    else:
        _bit(record["placebo_bit"], f"{label}.placebo_bit")
    return record


def audit_bundle(
    public: Mapping[str, Any], evaluator_private: Mapping[str, Any], probe_private: Mapping[str, Any], placebo_private: Mapping[str, Any]
) -> dict[str, Any]:
    core = public_core(public)
    evaluator = _private_record(evaluator_private, EVALUATOR_PRIVATE_SCHEMA, public, "evaluator_private")
    probe = _private_record(probe_private, PROBE_PRIVATE_SCHEMA, public, "probe_private")
    placebo = _private_record(placebo_private, PLACEBO_PRIVATE_SCHEMA, public, "placebo_private")
    if commitment(evaluator) != public["evaluator_private_commitment"]:
        raise TaskFamilyError("evaluator private commitment mismatch")
    if commitment(probe) != public["probe_private_commitment"]:
        raise TaskFamilyError("probe private commitment mismatch")
    if commitment(placebo) != public["placebo_private_commitment"]:
        raise TaskFamilyError("placebo private commitment mismatch")
    theta = _bit(evaluator["theta"], "evaluator_private.theta")
    _bit(placebo["placebo_bit"], "placebo_private.placebo_bit")
    probe_input = _token_value(probe["probe_input"], "probe_private.probe_input")
    probe_answer = _token_value(probe["probe_answer"], "probe_private.probe_answer")
    probe_identity = _token_value(probe["probe_identity"], "probe_private.probe_identity")
    if probe_input not in core["inputs"] or probe_input == core["train_input"]:
        raise TaskFamilyError("probe input must be a distinct hidden public-domain input")
    expected_probe_answer = core["h0" if theta == 0 else "h1"][probe_input]
    if probe_answer != expected_probe_answer:
        raise TaskFamilyError("probe private answer does not match hidden theta")
    public_bytes = canonical_json(public)
    for forbidden in (
        evaluator["private_canary"],
        probe["private_canary"],
        placebo["private_canary"],
        probe_identity,
    ):
        if forbidden.encode("utf-8") in public_bytes:
            raise TaskFamilyError("public task leaks private material")
    payload = {
        "schema_version": BUNDLE_AUDIT_RECEIPT_SCHEMA,
        "public_task_commitment": commitment(public),
        "evaluator_private_commitment": commitment(evaluator),
        "probe_private_commitment": commitment(probe),
        "placebo_private_commitment": commitment(placebo),
        "status": BUNDLE_AUDIT_STATUS,
    }
    return {**payload, "audit_commitment": commitment(payload)}


def _bundle_audit_receipt(
    public: Mapping[str, Any], probe_private_commitment: str, receipt: Mapping[str, Any]
) -> dict[str, Any]:
    parsed = _exact(
        receipt,
        {
            "schema_version", "public_task_commitment", "evaluator_private_commitment",
            "probe_private_commitment", "placebo_private_commitment", "status", "audit_commitment",
        },
        "bundle_audit_receipt",
    )
    payload = {key: value for key, value in parsed.items() if key != "audit_commitment"}
    if parsed["schema_version"] != BUNDLE_AUDIT_RECEIPT_SCHEMA or parsed["status"] != BUNDLE_AUDIT_STATUS:
        raise TaskFamilyError("bundle audit receipt schema or status mismatch")
    if parsed["audit_commitment"] != commitment(payload):
        raise TaskFamilyError("bundle audit receipt commitment mismatch")
    if parsed["public_task_commitment"] != commitment(public) or parsed["probe_private_commitment"] != probe_private_commitment:
        raise TaskFamilyError("bundle audit receipt does not bind public task and probe private")
    for key in ("evaluator_private_commitment", "placebo_private_commitment"):
        _sha(parsed[key], f"bundle audit receipt.{key}")
    return dict(parsed)


def task_family_status() -> dict[str, str]:
    """Hard nonclaims that the production lifecycle must retain verbatim."""
    return {
        "bundle_audit_status": BUNDLE_AUDIT_STATUS,
        "theta_placebo_status": THETA_PLACEBO_STATUS,
        "mechanism_uniqueness_status": MECHANISM_UNIQUENESS_STATUS,
        "probe_opening_status": PROBE_OPENING_STATUS,
        "combined_fixture_status": COMBINED_FIXTURE_STATUS,
    }


def generate_block(seed: bytes, block_index: int) -> dict[str, dict[str, Any]]:
    """Generate one domain-separated block and audit all public/private commitments."""
    if type(seed) is not bytes or len(seed) != SEED_BYTES:
        raise TaskFamilyError(f"seed must be exactly {SEED_BYTES} bytes")
    if type(block_index) is not int or not 0 <= block_index < BLOCK_COUNT:
        raise TaskFamilyError(f"block_index must lie in [0, {BLOCK_COUNT})")
    block_id = _block_id(block_index)
    seed_commitment = hashlib.sha256(seed).hexdigest()
    inputs = sorted(_token(seed, block_index, f"input:{index}") for index in range(4))
    outputs = sorted(_token(seed, block_index, f"output:{index}") for index in range(4))
    if len(set(inputs)) != 4 or len(set(outputs)) != 4 or set(inputs) & set(outputs):
        raise TaskFamilyError("derived nonce token collision")
    h0 = {input_token: outputs[index] for index, input_token in enumerate(inputs)}
    h1 = {input_token: outputs[(index + 1) % 4] for index, input_token in enumerate(inputs)}
    train_index = _uniform_below(seed, block_index, "train-index", 4)
    probe_offset = _uniform_below(seed, block_index, "probe-offset", 3)
    probe_index = (train_index + 1 + probe_offset) % 4
    core = {
        "schema_version": PUBLIC_CORE_SCHEMA,
        "block_id": block_id,
        "seed_commitment": seed_commitment,
        "inputs": inputs,
        "outputs": outputs,
        "h0": h0,
        "h1": h1,
        "train_input": inputs[train_index],
    }
    core_commitment = commitment(core)
    theta = _derive(seed, block_index, "theta")[0] & 1
    placebo_bit = _derive(seed, block_index, "placebo-bit")[0] & 1
    evaluator_private = {
        "schema_version": EVALUATOR_PRIVATE_SCHEMA,
        "block_id": block_id,
        "public_core_commitment": core_commitment,
        "theta": theta,
        "private_canary": _token(seed, block_index, "evaluator-canary"),
    }
    probe_private = {
        "schema_version": PROBE_PRIVATE_SCHEMA,
        "block_id": block_id,
        "public_core_commitment": core_commitment,
        "probe_input": inputs[probe_index],
        "probe_answer": (h0 if theta == 0 else h1)[inputs[probe_index]],
        "probe_identity": _token(seed, block_index, "probe-identity"),
        "private_canary": _token(seed, block_index, "probe-canary"),
    }
    placebo_private = {
        "schema_version": PLACEBO_PRIVATE_SCHEMA,
        "block_id": block_id,
        "public_core_commitment": core_commitment,
        "placebo_bit": placebo_bit,
        "private_canary": _token(seed, block_index, "placebo-canary"),
    }
    all_tokens = inputs + outputs + [
        evaluator_private["private_canary"],
        probe_private["probe_identity"],
        probe_private["private_canary"],
        placebo_private["private_canary"],
    ]
    if len(set(all_tokens)) != len(all_tokens):
        raise TaskFamilyError("domain-derived token collision")
    public = {
        "schema_version": PUBLIC_SCHEMA,
        "block_id": block_id,
        "seed_commitment": seed_commitment,
        "public_core": core,
        "public_core_commitment": core_commitment,
        "evaluator_private_commitment": commitment(evaluator_private),
        "probe_private_commitment": commitment(probe_private),
        "placebo_private_commitment": commitment(placebo_private),
    }
    audit_receipt = audit_bundle(public, evaluator_private, probe_private, placebo_private)
    return {
        "public_task": public,
        "evaluator_private": evaluator_private,
        "probe_private": probe_private,
        "placebo_private": placebo_private,
        "bundle_audit_receipt": audit_receipt,
        "status": COMBINED_FIXTURE_STATUS,
    }


def generate_study(seed: bytes) -> list[dict[str, dict[str, Any]]]:
    return [generate_block(seed, block_index) for block_index in range(BLOCK_COUNT)]


# Production-facing custody-separated constructors.  No constructor below takes
# more than one seed; assembly receives commitments/records, never seed bytes.
def production_public_core(task_seed: bytes, block_index: int) -> dict[str, Any]:
    if type(task_seed) is not bytes or len(task_seed) != SEED_BYTES:
        raise TaskFamilyError("task seed must be exactly 32 bytes")
    if type(block_index) is not int or not 0 <= block_index < BLOCK_COUNT:
        raise TaskFamilyError("task block index is outside frozen universe")
    inputs = sorted(_token(task_seed, block_index, f"input:{index}") for index in range(4))
    outputs = sorted(_token(task_seed, block_index, f"output:{index}") for index in range(4))
    if len(set(inputs)) != 4 or len(set(outputs)) != 4 or set(inputs) & set(outputs):
        raise TaskFamilyError("task token collision")
    h0 = {item: outputs[index] for index, item in enumerate(inputs)}
    h1 = {item: outputs[(index + 1) % 4] for index, item in enumerate(inputs)}
    return _validate_public_core(
        {
            "schema_version": PUBLIC_CORE_SCHEMA,
            "block_id": _block_id(block_index),
            "seed_commitment": hashlib.sha256(task_seed).hexdigest(),
            "inputs": inputs,
            "outputs": outputs,
            "h0": h0,
            "h1": h1,
            "train_input": inputs[
                _uniform_below(task_seed, block_index, "train-index", 4)
            ],
        }
    )


def _source(seed: bytes, domain: str) -> dict[str, str]:
    if type(seed) is not bytes or len(seed) != SEED_BYTES:
        raise TaskFamilyError("production source seed must be exactly 32 bytes")
    return {"source_randomness_commitment": hashlib.sha256(seed).hexdigest(), "derivation_domain": domain}


def production_evaluator_private(evaluator_seed: bytes, core: Mapping[str, Any]) -> dict[str, Any]:
    parsed = _validate_public_core(core)
    index = int(parsed["block_id"][-4:]) - 1
    return {
        "schema_version": SEPARATED_EVALUATOR_PRIVATE_SCHEMA,
        "block_id": parsed["block_id"],
        "public_core_commitment": commitment(parsed),
        "theta": _derive(evaluator_seed, index, "separated-theta")[0] & 1,
        **_source(evaluator_seed, EVALUATOR_DERIVATION_DOMAIN),
    }


def validate_production_evaluator_private(value: Mapping[str, Any], core: Mapping[str, Any]) -> dict[str, Any]:
    parsed = _validate_public_core(core)
    record = _exact(
        value,
        {
            "schema_version",
            "block_id",
            "public_core_commitment",
            "theta",
            "source_randomness_commitment",
            "derivation_domain",
        },
        "separated evaluator",
    )
    if (
        record["schema_version"] != SEPARATED_EVALUATOR_PRIVATE_SCHEMA
        or record["block_id"] != parsed["block_id"]
        or record["public_core_commitment"] != commitment(parsed)
        or record["derivation_domain"] != EVALUATOR_DERIVATION_DOMAIN
    ):
        raise TaskFamilyError("separated evaluator binding mismatch")
    _bit(record["theta"], "separated evaluator theta")
    _sha(record["source_randomness_commitment"], "separated evaluator source")
    return dict(record)


def production_probe_challenge(probe_seed: bytes, core: Mapping[str, Any]) -> dict[str, Any]:
    parsed = _validate_public_core(core)
    index = int(parsed["block_id"][-4:]) - 1
    candidates = [item for item in parsed["inputs"] if item != parsed["train_input"]]
    return {
        "schema_version": SEPARATED_PROBE_CHALLENGE_SCHEMA,
        "block_id": parsed["block_id"],
        "public_core_commitment": commitment(parsed),
        "probe_input": candidates[
            _uniform_below(probe_seed, index, "separated-probe", 3)
        ],
        "probe_identity": _token(probe_seed, index, "separated-probe-identity"),
        **_source(probe_seed, PROBE_DERIVATION_DOMAIN),
    }


def validate_production_probe_challenge(value: Mapping[str, Any], core: Mapping[str, Any]) -> dict[str, Any]:
    parsed = _validate_public_core(core)
    record = _exact(
        value,
        {
            "schema_version",
            "block_id",
            "public_core_commitment",
            "probe_input",
            "probe_identity",
            "source_randomness_commitment",
            "derivation_domain",
        },
        "separated challenge",
    )
    if (
        record["schema_version"] != SEPARATED_PROBE_CHALLENGE_SCHEMA
        or record["block_id"] != parsed["block_id"]
        or record["public_core_commitment"] != commitment(parsed)
        or record["derivation_domain"] != PROBE_DERIVATION_DOMAIN
    ):
        raise TaskFamilyError("separated challenge binding mismatch")
    _sha(record["source_randomness_commitment"], "separated challenge source")
    _token_value(record["probe_input"], "separated challenge input")
    _token_value(record["probe_identity"], "separated challenge identity")
    if (
        record["probe_input"] not in parsed["inputs"]
        or record["probe_input"] == parsed["train_input"]
    ):
        raise TaskFamilyError("separated challenge must be held out")
    return dict(record)


def production_hidden_answer(evaluator_private: Mapping[str, Any], probe_challenge: Mapping[str, Any], core: Mapping[str, Any]) -> dict[str, Any]:
    parsed = _validate_public_core(core)
    evaluator = validate_production_evaluator_private(evaluator_private, parsed)
    challenge = validate_production_probe_challenge(probe_challenge, parsed)
    answer = parsed["h0" if evaluator["theta"] == 0 else "h1"][challenge["probe_input"]]
    payload = {
        "schema_version": SEPARATED_HIDDEN_ANSWER_SCHEMA,
        "block_id": parsed["block_id"],
        "public_core_commitment": commitment(parsed),
        "probe_challenge_commitment": commitment(challenge),
        "probe_answer": answer,
        "theta_source_commitment": evaluator["source_randomness_commitment"],
    }
    return {**payload, "commitment": commitment(payload)}


def production_placebo_private(placebo_seed: bytes, core: Mapping[str, Any]) -> dict[str, Any]:
    parsed = _validate_public_core(core)
    index = int(parsed["block_id"][-4:]) - 1
    return {
        "schema_version": SEPARATED_PLACEBO_PRIVATE_SCHEMA,
        "block_id": parsed["block_id"],
        "public_core_commitment": commitment(parsed),
        "placebo_bit": _derive(placebo_seed, index, "separated-placebo")[0] & 1,
        **_source(placebo_seed, PLACEBO_DERIVATION_DOMAIN),
    }


def validate_production_placebo_private(value: Mapping[str, Any], core: Mapping[str, Any]) -> dict[str, Any]:
    parsed = _validate_public_core(core)
    record = _exact(
        value,
        {
            "schema_version",
            "block_id",
            "public_core_commitment",
            "placebo_bit",
            "source_randomness_commitment",
            "derivation_domain",
        },
        "separated placebo",
    )
    if (
        record["schema_version"] != SEPARATED_PLACEBO_PRIVATE_SCHEMA
        or record["block_id"] != parsed["block_id"]
        or record["public_core_commitment"] != commitment(parsed)
        or record["derivation_domain"] != PLACEBO_DERIVATION_DOMAIN
    ):
        raise TaskFamilyError("separated placebo binding mismatch")
    _bit(record["placebo_bit"], "separated placebo bit")
    _sha(record["source_randomness_commitment"], "separated placebo source")
    return dict(record)


def validate_production_hidden_answer(value: Mapping[str, Any], core: Mapping[str, Any], challenge: Mapping[str, Any]) -> dict[str, Any]:
    parsed = _validate_public_core(core)
    checked = validate_production_probe_challenge(challenge, parsed)
    record = _exact(
        value,
        {
            "schema_version",
            "block_id",
            "public_core_commitment",
            "probe_challenge_commitment",
            "probe_answer",
            "theta_source_commitment",
            "commitment",
        },
        "separated hidden answer",
    )
    payload = {key: item for key, item in record.items() if key != "commitment"}
    if (
        record["schema_version"] != SEPARATED_HIDDEN_ANSWER_SCHEMA
        or record["block_id"] != parsed["block_id"]
        or record["public_core_commitment"] != commitment(parsed)
        or record["probe_challenge_commitment"] != commitment(checked)
        or record["commitment"] != commitment(payload)
    ):
        raise TaskFamilyError("separated hidden answer binding mismatch")
    _token_value(record["probe_answer"], "separated hidden answer")
    _sha(record["theta_source_commitment"], "separated answer source")
    if record["probe_answer"] not in parsed["outputs"]:
        raise TaskFamilyError("separated hidden answer outside output domain")
    return dict(record)


def assemble_production_public_task(core: Mapping[str, Any], evaluator_commitment: str, probe_challenge_commitment: str, hidden_answer_commitment: str, placebo_commitment: str) -> dict[str, Any]:
    parsed = _validate_public_core(core)
    for value in (
        evaluator_commitment,
        probe_challenge_commitment,
        hidden_answer_commitment,
        placebo_commitment,
    ):
        _sha(value, "separated commitment")
    return {
        "schema_version": SEPARATED_PUBLIC_SCHEMA,
        "public_core": parsed,
        "public_core_commitment": commitment(parsed),
        "evaluator_private_commitment": evaluator_commitment,
        "probe_challenge_commitment": probe_challenge_commitment,
        "hidden_answer_commitment": hidden_answer_commitment,
        "placebo_private_commitment": placebo_commitment,
    }


def validate_training_response(public: Mapping[str, Any], response: Mapping[str, Any]) -> dict[str, Any]:
    core = public_core(public)
    parsed = _exact(response, {"schema_version", "block_id", "hypothesis_id", "answer_token"}, "training_response")
    if parsed["schema_version"] != TRAINING_RESPONSE_SCHEMA or parsed["block_id"] != core["block_id"]:
        raise TaskFamilyError("training response schema or block mismatch")
    hypothesis_id = _bit(parsed["hypothesis_id"], "training_response.hypothesis_id")
    answer = _token_value(parsed["answer_token"], "training_response.answer_token")
    expected = core["h0" if hypothesis_id == 0 else "h1"][core["train_input"]]
    if answer != expected:
        raise TaskFamilyError("training response answer is inconsistent with selected hypothesis")
    return dict(parsed)


def seal_training_response(public: Mapping[str, Any], response: Mapping[str, Any]) -> dict[str, Any]:
    parsed = validate_training_response(public, response)
    payload = {
        "schema_version": SEALED_TRAINING_RESPONSE_SCHEMA,
        "public_task_commitment": commitment(public),
        "response": parsed,
    }
    return {**payload, "trajectory_commitment": commitment(payload)}


def open_probe(
    public: Mapping[str, Any], probe_private: Mapping[str, Any], bundle_audit_receipt: Mapping[str, Any]
) -> dict[str, Any]:
    _private_record(probe_private, PROBE_PRIVATE_SCHEMA, public, "probe_private")
    if commitment(probe_private) != public["probe_private_commitment"]:
        raise TaskFamilyError("probe private commitment mismatch")
    audit_receipt = _bundle_audit_receipt(public, commitment(probe_private), bundle_audit_receipt)
    payload = {
        "schema_version": PROBE_OPENING_SCHEMA,
        "public_task_commitment": commitment(public),
        "probe_private_commitment": commitment(probe_private),
        "probe_input": probe_private["probe_input"],
        "probe_identity": probe_private["probe_identity"],
        "bundle_audit_receipt": audit_receipt,
        "opening_status": PROBE_OPENING_STATUS,
    }
    return {**payload, "opening_commitment": commitment(payload)}


def seal_probe_response(public: Mapping[str, Any], opening: Mapping[str, Any], answer_token: str) -> dict[str, Any]:
    core = public_core(public)
    parsed = _exact(
        opening,
        {
            "schema_version", "public_task_commitment", "probe_private_commitment", "probe_input",
            "probe_identity", "bundle_audit_receipt", "opening_status", "opening_commitment",
        },
        "probe_opening",
    )
    payload = {key: value for key, value in parsed.items() if key != "opening_commitment"}
    if parsed["schema_version"] != PROBE_OPENING_SCHEMA or parsed["opening_commitment"] != commitment(payload):
        raise TaskFamilyError("probe opening commitment mismatch")
    if parsed["public_task_commitment"] != commitment(public) or parsed["probe_private_commitment"] != public["probe_private_commitment"]:
        raise TaskFamilyError("probe opening/public commitment mismatch")
    if parsed["opening_status"] != PROBE_OPENING_STATUS:
        raise TaskFamilyError("probe opening lacks lifecycle chronology nonclaim")
    _bundle_audit_receipt(public, parsed["probe_private_commitment"], parsed["bundle_audit_receipt"])
    if parsed["probe_input"] not in core["inputs"] or parsed["probe_input"] == core["train_input"]:
        raise TaskFamilyError("probe opening input must be a held-out public-domain input")
    _token_value(parsed["probe_identity"], "probe opening identity")
    answer = _token_value(answer_token, "probe answer token")
    if answer not in core["outputs"]:
        raise TaskFamilyError("probe answer token is outside public output domain")
    response_payload = {
        "schema_version": SEALED_PROBE_RESPONSE_SCHEMA,
        "public_task_commitment": commitment(public),
        "opening_commitment": parsed["opening_commitment"],
        "bundle_audit_receipt": parsed["bundle_audit_receipt"],
        "opening_status": parsed["opening_status"],
        "answer_token": answer,
    }
    return {**response_payload, "response_commitment": commitment(response_payload)}
