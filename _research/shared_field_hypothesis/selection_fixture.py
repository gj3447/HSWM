"""Independent cost/risk action fixture for the G2 selection task.

The gold label here is intentionally not a retrieval argmax.  Relevance is
recorded only as a negative-control readout; admission and utility use frozen
outcome, reward, cost, and risk labels.  A valid fixture must contain at least
one separation case where the unique top-relevance action is either infeasible
or has worse constrained utility than the gold action.

All arithmetic is integer arithmetic.  This avoids platform-dependent float
ties and makes regret byte-replayable.  Infeasible actions have ``regret=null``
and an explicit refusal reason; inventing a numeric reward for an unsafe action
would silently turn a hard constraint into a soft retrieval score.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping


SOURCE_SCHEMA = "hswm-cost-risk-selection-source/v1"
COMPILED_SCHEMA = "hswm-cost-risk-selection-fixture/v1"
COMMITMENT_SENTINEL = "<COMMITMENT_SHA256>"
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_TOP_KEYS = frozenset(
    {"schema", "fixture_id", "evidence_state", "actions", "constraints", "commitment_sha256"}
)
_EVIDENCE_KEYS = frozenset({"evidence_id", "payload"})
_ACTION_KEYS = frozenset(
    {"action_id", "outcome", "reward", "cost", "risk", "relevance", "evidence_ids"}
)
_OUTCOME_KEYS = frozenset({"outcome_id", "acceptable", "payload"})
_CONSTRAINT_KEYS = frozenset(
    {"max_cost", "max_risk", "min_reward", "cost_weight", "risk_weight"}
)


class SelectionFixtureError(ValueError):
    """The source cannot define an independent deterministic action label."""


class CanonicalSelectionError(SelectionFixtureError):
    """The input is not the single canonical JSON encoding."""


class SelectionTamperError(SelectionFixtureError):
    """The source bytes disagree with their semantic commitment."""


class SelectionDuplicateIDError(SelectionFixtureError):
    """A stable ID was reused with different payload bytes."""


class SelectionOracleError(SelectionFixtureError):
    """No unique constrained gold action or relevance separation exists."""


def canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CanonicalSelectionError(f"value is not canonical JSON data: {exc}") from exc


def _sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _duplicate_rejector(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CanonicalSelectionError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise CanonicalSelectionError(f"non-finite JSON number: {value}")


def load_canonical_source(source: bytes) -> dict[str, Any]:
    if not isinstance(source, bytes):
        raise CanonicalSelectionError("source must be bytes")
    if source.startswith(b"\xef\xbb\xbf"):
        raise CanonicalSelectionError("UTF-8 BOM is not canonical")
    try:
        value = json.loads(
            source.decode("utf-8", errors="strict"),
            object_pairs_hook=_duplicate_rejector,
            parse_constant=_reject_constant,
        )
    except CanonicalSelectionError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CanonicalSelectionError(f"invalid UTF-8 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise CanonicalSelectionError("source must contain one JSON object")
    if canonical_json_bytes(value) != source:
        raise CanonicalSelectionError("source is valid JSON but not canonical")
    return value


def _exact_keys(value: Any, expected: frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SelectionFixtureError(f"{label} must be an object")
    actual = frozenset(value)
    if actual != expected:
        raise SelectionFixtureError(
            f"{label} fields differ: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )
    return value


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
        raise SelectionFixtureError(f"{label} must match {_ID_RE.pattern}")
    return value


def _integer(value: Any, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise SelectionFixtureError(f"{label} must be an integer >= {minimum}")
    return value


def selection_source_commitment(document: Mapping[str, Any]) -> str:
    """Digest all source semantics while normalizing only the self-binding."""
    normalized = copy.deepcopy(dict(document))
    normalized["commitment_sha256"] = COMMITMENT_SENTINEL
    return _sha256(normalized)


def seal_selection_source(document: Mapping[str, Any]) -> bytes:
    """Create committed canonical bytes for fixture construction/tests."""
    sealed = copy.deepcopy(dict(document))
    sealed["commitment_sha256"] = selection_source_commitment(sealed)
    return canonical_json_bytes(sealed)


@dataclass(frozen=True)
class CompiledSelectionFixture:
    canonical_bytes: bytes
    source_sha256: str
    evidence_state_sha256: str
    oracle_sha256: str

    @property
    def compiled_sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes).hexdigest()

    @property
    def document(self) -> dict[str, Any]:
        return json.loads(self.canonical_bytes.decode("utf-8"))

    @property
    def gold_action_id(self) -> str:
        return self.document["gold_action_id"]

    def action(self, action_id: str) -> Mapping[str, Any]:
        for action in self.document["action_oracle"]:
            if action["action_id"] == action_id:
                return action
        raise KeyError(action_id)


def _parse_source(source: bytes) -> dict[str, Any]:
    document = load_canonical_source(source)
    _exact_keys(document, _TOP_KEYS, "source")
    if document["schema"] != SOURCE_SCHEMA:
        raise SelectionFixtureError(f"schema must be {SOURCE_SCHEMA}")
    _identifier(document["fixture_id"], "fixture_id")
    commitment = document["commitment_sha256"]
    if not isinstance(commitment, str) or not re.fullmatch(r"[0-9a-f]{64}", commitment):
        raise SelectionTamperError("commitment_sha256 must be a lowercase SHA-256")
    actual_commitment = selection_source_commitment(document)
    if commitment != actual_commitment:
        raise SelectionTamperError(
            f"source commitment mismatch: expected {commitment}, derived {actual_commitment}"
        )
    return document


def compile_selection_fixture(source: bytes) -> CompiledSelectionFixture:
    """Compile a committed source into a deterministic constrained action oracle."""
    document = _parse_source(source)

    evidence_state = document["evidence_state"]
    if not isinstance(evidence_state, list) or not evidence_state:
        raise SelectionFixtureError("evidence_state must be a non-empty array")
    evidence_registry: dict[str, bytes] = {}
    compiled_evidence: list[dict[str, str]] = []
    evidence_order: list[str] = []
    for index, raw in enumerate(evidence_state):
        evidence = _exact_keys(raw, _EVIDENCE_KEYS, f"evidence_state[{index}]")
        evidence_id = _identifier(evidence["evidence_id"], f"evidence_state[{index}].evidence_id")
        encoded = canonical_json_bytes(evidence["payload"])
        prior = evidence_registry.get(evidence_id)
        if prior is not None:
            if prior != encoded:
                raise SelectionDuplicateIDError(
                    f"evidence_id {evidence_id!r} has differing payloads"
                )
            raise CanonicalSelectionError(f"evidence_id {evidence_id!r} is duplicated")
        evidence_registry[evidence_id] = encoded
        evidence_order.append(evidence_id)
        compiled_evidence.append(
            {
                "evidence_id": evidence_id,
                "evidence_sha256": _sha256(
                    {"evidence_id": evidence_id, "payload": evidence["payload"]}
                ),
            }
        )
    if evidence_order != sorted(evidence_order):
        raise CanonicalSelectionError("evidence_state must be evidence_id-sorted")

    constraints = _exact_keys(document["constraints"], _CONSTRAINT_KEYS, "constraints")
    parsed_constraints = {
        key: _integer(value, f"constraints.{key}") for key, value in constraints.items()
    }
    if parsed_constraints["cost_weight"] == 0 or parsed_constraints["risk_weight"] == 0:
        raise SelectionOracleError("cost_weight and risk_weight must both be positive")

    raw_actions = document["actions"]
    if not isinstance(raw_actions, list) or len(raw_actions) < 2:
        raise SelectionFixtureError("actions must contain at least two actions")
    action_order: list[str] = []
    action_registry: dict[str, bytes] = {}
    outcome_registry: dict[str, bytes] = {}
    parsed_actions: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_actions):
        action = _exact_keys(raw, _ACTION_KEYS, f"actions[{index}]")
        action_id = _identifier(action["action_id"], f"actions[{index}].action_id")
        action_bytes = canonical_json_bytes(action)
        prior_action = action_registry.get(action_id)
        if prior_action is not None:
            if prior_action != action_bytes:
                raise SelectionDuplicateIDError(
                    f"action_id {action_id!r} has differing payloads"
                )
            raise CanonicalSelectionError(f"action_id {action_id!r} is duplicated")
        action_registry[action_id] = action_bytes
        action_order.append(action_id)

        outcome = _exact_keys(action["outcome"], _OUTCOME_KEYS, f"action {action_id}.outcome")
        outcome_id = _identifier(outcome["outcome_id"], f"action {action_id}.outcome_id")
        if not isinstance(outcome["acceptable"], bool):
            raise SelectionFixtureError(f"action {action_id}: outcome.acceptable must be boolean")
        outcome_bytes = canonical_json_bytes(outcome)
        prior_outcome = outcome_registry.get(outcome_id)
        if prior_outcome is not None and prior_outcome != outcome_bytes:
            raise SelectionDuplicateIDError(
                f"outcome_id {outcome_id!r} has differing payloads"
            )
        outcome_registry[outcome_id] = outcome_bytes

        evidence_ids = action["evidence_ids"]
        if not isinstance(evidence_ids, list) or not evidence_ids:
            raise SelectionFixtureError(f"action {action_id}: evidence_ids must be non-empty")
        normalized_evidence_ids = [
            _identifier(value, f"action {action_id}.evidence_ids[]") for value in evidence_ids
        ]
        if normalized_evidence_ids != sorted(normalized_evidence_ids) or len(
            set(normalized_evidence_ids)
        ) != len(normalized_evidence_ids):
            raise CanonicalSelectionError(
                f"action {action_id}: evidence_ids must be strictly sorted and unique"
            )
        unknown = set(normalized_evidence_ids) - set(evidence_registry)
        if unknown:
            raise SelectionFixtureError(
                f"action {action_id}: unknown evidence IDs {sorted(unknown)}"
            )

        reward = _integer(action["reward"], f"action {action_id}.reward")
        cost = _integer(action["cost"], f"action {action_id}.cost")
        risk = _integer(action["risk"], f"action {action_id}.risk")
        relevance = _integer(action["relevance"], f"action {action_id}.relevance")
        refusal_reasons: list[str] = []
        if not outcome["acceptable"]:
            refusal_reasons.append("UNACCEPTABLE_OUTCOME")
        if reward < parsed_constraints["min_reward"]:
            refusal_reasons.append("MIN_REWARD_NOT_MET")
        if cost > parsed_constraints["max_cost"]:
            refusal_reasons.append("COST_CAP_EXCEEDED")
        if risk > parsed_constraints["max_risk"]:
            refusal_reasons.append("RISK_CAP_EXCEEDED")
        utility = (
            reward
            - parsed_constraints["cost_weight"] * cost
            - parsed_constraints["risk_weight"] * risk
        )
        parsed_actions.append(
            {
                "action_id": action_id,
                "action_sha256": _sha256(action),
                "outcome_id": outcome_id,
                "outcome_sha256": _sha256(outcome),
                "reward": reward,
                "cost": cost,
                "risk": risk,
                "relevance": relevance,
                "utility": utility,
                "feasible": not refusal_reasons,
                "refusal_reasons": refusal_reasons,
                "evidence_ids": normalized_evidence_ids,
            }
        )
    if action_order != sorted(action_order):
        raise CanonicalSelectionError("actions must be action_id-sorted")

    feasible = [action for action in parsed_actions if action["feasible"]]
    if not feasible:
        raise SelectionOracleError("no action satisfies the outcome/cost/risk constraints")
    best_utility = max(action["utility"] for action in feasible)
    winners = [action for action in feasible if action["utility"] == best_utility]
    if len(winners) != 1:
        raise SelectionOracleError(
            f"gold action is ambiguous at utility {best_utility}: "
            f"{sorted(action['action_id'] for action in winners)}"
        )
    gold = winners[0]

    best_relevance = max(action["relevance"] for action in parsed_actions)
    relevance_winners = [
        action for action in parsed_actions if action["relevance"] == best_relevance
    ]
    if len(relevance_winners) != 1:
        raise SelectionOracleError("top relevance must be unique for the negative control")
    relevance_top = relevance_winners[0]
    if relevance_top["action_id"] == gold["action_id"]:
        raise SelectionOracleError(
            "fixture lacks separation: retrieval relevance argmax equals constrained gold"
        )
    if relevance_top["feasible"]:
        separation_kind = "TOP_RELEVANCE_COST_SUBOPTIMAL"
        if relevance_top["utility"] >= gold["utility"]:
            raise SelectionOracleError("purported cost-suboptimal action is not suboptimal")
    else:
        separation_kind = "TOP_RELEVANCE_UNSAFE_OR_CONSTRAINT_INVALID"

    action_oracle: list[dict[str, Any]] = []
    for action in parsed_actions:
        oracle = dict(action)
        oracle["selected"] = action["action_id"] == gold["action_id"]
        oracle["regret"] = (
            best_utility - action["utility"] if action["feasible"] else None
        )
        oracle["decision"] = "ELIGIBLE" if action["feasible"] else "REFUSED"
        action_oracle.append(oracle)

    evidence_state_sha256 = _sha256(document["evidence_state"])
    oracle_payload = {
        "gold_action_id": gold["action_id"],
        "gold_utility": best_utility,
        "top_relevance_action_id": relevance_top["action_id"],
        "separation_kind": separation_kind,
        "actions": action_oracle,
    }
    oracle_sha256 = _sha256(oracle_payload)
    output = {
        "schema": COMPILED_SCHEMA,
        "fixture_id": document["fixture_id"],
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "source_commitment_sha256": document["commitment_sha256"],
        "evidence_state_sha256": evidence_state_sha256,
        "evidence_bindings": compiled_evidence,
        "constraints": parsed_constraints,
        "gold_action_id": gold["action_id"],
        "gold_utility": best_utility,
        "top_relevance_action_id": relevance_top["action_id"],
        "separation_kind": separation_kind,
        "action_oracle": action_oracle,
        "oracle_sha256": oracle_sha256,
        "gold_oracle_basis": "frozen outcome/reward/cost/risk constraints; relevance excluded",
        "claim_boundary": {
            "model_arm_implemented": False,
            "result_claimed": False,
            "efficacy_claimed": False,
        },
    }
    return CompiledSelectionFixture(
        canonical_bytes=canonical_json_bytes(output),
        source_sha256=output["source_sha256"],
        evidence_state_sha256=evidence_state_sha256,
        oracle_sha256=oracle_sha256,
    )


def verify_compiled_selection_fixture(
    source: bytes, compiled_bytes: bytes
) -> CompiledSelectionFixture:
    """Recompile the committed source and reject any stored-byte drift."""
    expected = compile_selection_fixture(source)
    if not isinstance(compiled_bytes, bytes) or compiled_bytes != expected.canonical_bytes:
        raise SelectionTamperError(
            "compiled selection fixture tamper/drift: bytes do not match deterministic replay"
        )
    return expected


compile_source_block = compile_selection_fixture


__all__ = [
    "COMMITMENT_SENTINEL",
    "COMPILED_SCHEMA",
    "CompiledSelectionFixture",
    "CanonicalSelectionError",
    "SOURCE_SCHEMA",
    "SelectionDuplicateIDError",
    "SelectionFixtureError",
    "SelectionOracleError",
    "SelectionTamperError",
    "canonical_json_bytes",
    "compile_selection_fixture",
    "compile_source_block",
    "load_canonical_source",
    "seal_selection_source",
    "selection_source_commitment",
    "verify_compiled_selection_fixture",
]
