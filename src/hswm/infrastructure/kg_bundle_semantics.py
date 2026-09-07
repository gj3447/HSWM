"""Small, fail-closed semantic checks for selected KG bundle profiles.

This module deliberately complements the generic RDF projection validator.  It
does not interpret an ontology as canonical HSWM state and has no publication,
Permit, revision, or learning capability.  A profile is opt-in: historic and
mixed-authority bundles are not required to acquire a new common field set.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


class KgBundleSemanticError(ValueError):
    """A selected bundle profile violated its declared semantic contract."""


@dataclass(frozen=True)
class DomainRoleInventory:
    """Role inventory bound to one source schema revision, not a global schema."""

    source_revision: str
    role_counts: Mapping[str, int]


HYPERGRAPH_LEARNING_PLAN_INVENTORY = DomainRoleInventory(
    source_revision="hswm-hypergraph-learning-plan/v1",
    role_counts={
        "DESIGN_INTUITION": 4,
        "EVIDENCE_BOUNDARY": 1,
        "LEARNING_ASSERTION": 4,
        "LEARNING_CONCEPT": 20,
        "LEARNING_PLAN_BUNDLE": 1,
        "LEARNING_PLAN_STEP": 6,
        "PLAN_SOURCE": 1,
        "ROLE_PARTICIPATION": 25,
        "USER_DIRECT_REQUEST": 1,
    },
)

WORKSHOP_C1_C3_INVENTORY = DomainRoleInventory(
    source_revision="hswm-workshop-c1-c3-concept-projection/v1",
    role_counts={
        "AUTHORED_SCENE": 4,
        "ILLUSTRATIVE_HYPOTHESIS": 3,
        "ILLUSTRATIVE_PROBE": 3,
        "OPEN_MECHANISM_PROBLEM": 2,
        "WORKED_COMPOSITION_QUESTION": 1,
        "WORKED_DESIGN_INSIGHT": 4,
        "WORKED_REVISION_CANDIDATE": 3,
        "WORKED_SCOPE_GUARD": 4,
        "WORKED_SPEC_BUNDLE": 1,
        "WORKED_SPEC_SECTION": 3,
        "WORKED_SPEC_SOURCE": 1,
    },
)

_INVENTORIES = {
    HYPERGRAPH_LEARNING_PLAN_INVENTORY.source_revision: HYPERGRAPH_LEARNING_PLAN_INVENTORY,
    WORKSHOP_C1_C3_INVENTORY.source_revision: WORKSHOP_C1_C3_INVENTORY,
}


def inventory_for(data: Mapping[str, Any]) -> DomainRoleInventory | None:
    """Return a contract only for a known, explicitly versioned domain profile."""

    revision = data.get("schema_version")
    return _INVENTORIES.get(revision) if isinstance(revision, str) else None


def _fail(message: str) -> None:
    raise KgBundleSemanticError(message)


def _nodes_by_uid(data: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = data.get("nodes")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        _fail("nodes must be a sequence")
    found: dict[str, Mapping[str, Any]] = {}
    for node in rows:
        if not isinstance(node, Mapping) or not isinstance(node.get("uid"), str):
            _fail("node uid is invalid")
        if node["uid"] in found:
            _fail(f"duplicate node uid: {node['uid']}")
        properties = node.get("properties")
        if not isinstance(properties, Mapping):
            _fail(f"node properties are invalid: {node['uid']}")
        found[node["uid"]] = node
    return found


def _role(node: Mapping[str, Any]) -> str | None:
    value = node["properties"].get("standard_graph_role")
    return value if isinstance(value, str) else None


def _validate_inventory(nodes: Mapping[str, Mapping[str, Any]], inventory: DomainRoleInventory) -> None:
    actual = Counter(_role(node) for node in nodes.values())
    if None in actual:
        _fail(f"{inventory.source_revision}: every owned node must declare standard_graph_role")
    if "UNCLASSIFIED" in actual:
        _fail(f"{inventory.source_revision}: UNCLASSIFIED is not an allowed domain role")
    expected = Counter(inventory.role_counts)
    if actual != expected:
        _fail(
            f"{inventory.source_revision}: source-revision domain role inventory drift "
            f"(expected {dict(expected)}, got {dict(actual)})"
        )


def _validate_authority(nodes: Mapping[str, Mapping[str, Any]]) -> None:
    for uid, node in nodes.items():
        properties = node["properties"]
        raw = properties.get("authority_class")
        discovery = properties.get("ontology_authority_class_v1")
        if discovery is not None and (not isinstance(discovery, str) or discovery != raw):
            _fail(f"{uid}: ontology_authority_class_v1 conflicts with authority_class")


def _validate_current_decisions(
    nodes: Mapping[str, Mapping[str, Any]], relations: list[Mapping[str, Any]]
) -> None:
    for uid, node in nodes.items():
        properties = node["properties"]
        decision_uid = properties.get("current_decision_uid")
        if decision_uid is None:
            continue
        if not isinstance(decision_uid, str) or decision_uid not in nodes:
            _fail(f"{uid}: current_decision_uid does not identify an owned decision")
        if _role(node) != "CLAIM":
            _fail(f"{uid}: current_decision_uid is only valid on CLAIM")
        decision = nodes[decision_uid]
        if _role(decision) not in {"DECISION", "USER_PRIMARY_DECISION"}:
            _fail(f"{uid}: current_decision_uid does not identify a decision role")
        if decision["properties"].get("assesses_claim_uid") != uid:
            _fail(f"{uid}: decision does not assess the claim named by current_decision_uid")
        if not any(
            relation.get("from_uid") == uid
            and relation.get("to_uid") == decision_uid
            and relation.get("type") == "HAS_CONCEPT"
            for relation in relations
        ):
            _fail(f"{uid}: current_decision_uid lacks a HAS_CONCEPT claim-to-decision relation")


def _validate_authored_scenes(nodes: Mapping[str, Mapping[str, Any]]) -> None:
    for uid, node in nodes.items():
        if _role(node) != "AUTHORED_SCENE":
            continue
        if node["properties"].get("status") != "AUTHORED_ILLUSTRATION_NOT_OBSERVATION":
            _fail(f"{uid}: AUTHORED_SCENE cannot be promoted to an observed result")


def _validate_participation_ordinals(
    nodes: Mapping[str, Mapping[str, Any]], relations: list[Mapping[str, Any]]
) -> None:
    by_assertion: dict[str, list[str]] = defaultdict(list)
    for relation in relations:
        if relation.get("type") == "HAS_PARTICIPATION" and isinstance(relation.get("from_uid"), str) and isinstance(relation.get("to_uid"), str):
            by_assertion[relation["from_uid"]].append(relation["to_uid"])
    for assertion_uid, participants in by_assertion.items():
        assertion = nodes.get(assertion_uid)
        if assertion is None or _role(assertion) != "LEARNING_ASSERTION":
            continue
        ordinals: list[int] = []
        for participant_uid in participants:
            participant = nodes.get(participant_uid)
            if participant is None or _role(participant) != "ROLE_PARTICIPATION":
                _fail(f"{assertion_uid}: HAS_PARTICIPATION must name ROLE_PARTICIPATION")
            ordinal = participant["properties"].get("ordinal")
            if type(ordinal) is not int or ordinal < 0:
                _fail(f"{participant_uid}: participation ordinal must be a non-negative integer")
            ordinals.append(ordinal)
        if len(ordinals) != len(set(ordinals)):
            _fail(f"{assertion_uid}: participation ordinal must be unique within one assertion")


def validate_bundle_semantics(
    data: Mapping[str, Any], *, inventory: DomainRoleInventory | None = None
) -> None:
    """Validate selected semantic links without making an ontology-wide claim.

    If no inventory is supplied, a known profile is selected from its exact
    schema version.  Unknown bundle revisions receive only the conditional
    checks that their own populated fields make meaningful.
    """

    nodes = _nodes_by_uid(data)
    relations = data.get("relations")
    if not isinstance(relations, Sequence) or isinstance(relations, (str, bytes)) or any(not isinstance(row, Mapping) for row in relations):
        _fail("relations must be a sequence of objects")
    selected = inventory if inventory is not None else inventory_for(data)
    if selected is not None:
        _validate_inventory(nodes, selected)
    typed_relations = list(relations)
    _validate_authority(nodes)
    _validate_current_decisions(nodes, typed_relations)
    _validate_authored_scenes(nodes)
    _validate_participation_ordinals(nodes, typed_relations)
