"""Fail-closed identity and concurrency checks for bounded KG publication.

This module protects the publication transaction used by the HSWM bundle
writers.  It is not a general Neo4j administration API, a canonical-state
writer, or an HSWM learning path.  In particular, its constraints apply only
to the label implied by a bundle-owned ``sym:<kind>:...`` UID; they cannot make
unrelated legacy clients globally safe.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Any
from uuid import uuid4

from .kg_bundle_semantics import validate_bundle_semantics


REGISTRY_UID = "sym:KG_INFRA:schema-registry-v1-2026-08-03"
_UID_KIND = re.compile(r"sym:([A-Za-z_][A-Za-z0-9_]*):[^:\s][^\s]*\Z")
_LOCK_PROPERTY = "__hswm_publication_transaction_lock"
_NODE_UID_UNIQUENESS_TYPES = frozenset({"UNIQUENESS", "NODE_PROPERTY_UNIQUENESS"})


class KgPublicationIntegrityError(RuntimeError):
    """A publication identity or transaction-integrity obligation failed."""


def _owned_nodes(data: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    nodes = data.get("nodes")
    if not isinstance(nodes, Sequence) or isinstance(nodes, (str, bytes)):
        raise KgPublicationIntegrityError("bundle nodes must be a sequence")
    if not nodes:
        raise KgPublicationIntegrityError("bundle has no owned nodes")
    if any(not isinstance(row, Mapping) for row in nodes):
        raise KgPublicationIntegrityError("bundle node record is invalid")
    return nodes


def uid_kind(uid: object) -> str:
    """Return the explicit UID kind that must also be a node label."""

    if not isinstance(uid, str):
        raise KgPublicationIntegrityError("owned node UID must be text")
    match = _UID_KIND.match(uid)
    if match is None:
        raise KgPublicationIntegrityError(f"owned node lacks sym UID kind: {uid!r}")
    return match.group(1)


def validate_uid_kind_labels(data: Mapping[str, Any]) -> set[str]:
    """Require each owned node's UID kind label before any live interaction."""

    kinds: set[str] = set()
    for row in _owned_nodes(data):
        uid = row.get("uid")
        kind = uid_kind(uid)
        labels = row.get("labels")
        if not isinstance(labels, Sequence) or isinstance(labels, (str, bytes)):
            raise KgPublicationIntegrityError(f"owned node labels are invalid: {uid!r}")
        if kind not in labels:
            raise KgPublicationIntegrityError(
                f"owned node UID kind label is missing: {uid!r} requires {kind!r}"
            )
        properties = row.get("properties")
        if not isinstance(properties, Mapping):
            raise KgPublicationIntegrityError(f"owned node properties are invalid: {uid!r}")
        declared_uid = properties.get("uid")
        if declared_uid is not None and declared_uid != uid:
            raise KgPublicationIntegrityError(
                f"owned node properties.uid cannot override row UID: {uid!r}"
            )
        kinds.add(kind)
    return kinds


def validate_bundle_for_publication(data: Mapping[str, Any]) -> set[str]:
    """Run semantic and typed-identity checks even for direct ``publish`` calls."""

    try:
        validate_bundle_semantics(data)
    except ValueError as error:
        raise KgPublicationIntegrityError(str(error)) from error
    return validate_uid_kind_labels(data)


def _constraint_rows(tx: Any) -> list[Mapping[str, Any]]:
    """Read only the fields used to prove Neo4j node-UID uniqueness."""

    return tx.run(
        "SHOW CONSTRAINTS YIELD name, type, entityType, labelsOrTypes, properties "
        "RETURN name, type, entityType, labelsOrTypes, properties"
    ).data()


def _has_uid_unique_constraint(rows: Sequence[Mapping[str, Any]], kind: str) -> bool:
    for row in rows:
        if (
            row.get("type") in _NODE_UID_UNIQUENESS_TYPES
            and row.get("entityType") == "NODE"
            and list(row.get("labelsOrTypes") or ()) == [kind]
            and list(row.get("properties") or ()) == ["uid"]
        ):
            return True
    return False


def assert_uid_kind_constraints(tx: Any, data: Mapping[str, Any]) -> set[str]:
    """Fail closed unless every published UID kind has ``kind(uid) UNIQUE``."""

    kinds = validate_uid_kind_labels(data)
    rows = _constraint_rows(tx)
    required_labels = kinds | {"SchemaRegistry"}
    missing = sorted(
        label for label in required_labels if not _has_uid_unique_constraint(rows, label)
    )
    if missing:
        raise KgPublicationIntegrityError(
            "missing required Neo4j UID uniqueness constraints for labels: "
            + ", ".join(missing)
        )
    return kinds


def serialize_on_schema_registry(tx: Any) -> None:
    """Take a write lock on the pre-existing registry without changing its bytes.

    Neo4j holds a write lock for the transaction after the dummy update.  The
    temporary property is removed in the same statement, so the registry's
    final property set is unchanged.  A pre-existing reserved property is
    refused instead of overwritten.
    """

    token = str(uuid4())
    row = tx.run(
        "MATCH (r:SchemaRegistry {uid:$uid}) "
        "WHERE r." + _LOCK_PROPERTY + " IS NULL "
        "SET r." + _LOCK_PROPERTY + " = $token "
        "WITH r REMOVE r." + _LOCK_PROPERTY + " "
        "RETURN r.uid AS uid, properties(r) AS properties",
        uid=REGISTRY_UID,
        token=token,
    ).single()
    if row is None or row.get("uid") != REGISTRY_UID:
        raise KgPublicationIntegrityError(
            "schema registry is missing or reserved publication lock is occupied"
        )
    if _LOCK_PROPERTY in (row.get("properties") or {}):
        raise KgPublicationIntegrityError("schema registry lock property was not removed")
