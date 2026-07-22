#!/usr/bin/env python3
"""Fixed-depth-free HSWM composition kernel.

This module does one thing the B0 field algebra intentionally does not do:
``compose`` preserves mount, port, connector, weight, and interface identity in a
flat canonical manifest.  ``materialize`` is an explicit, lossy-capability
boundary into the legacy eager ``Field`` quotient.

The public semantic type is always :class:`OpenHSWM`.  A wrapped atomic field and
an aggregate of aggregates therefore use the same API.  Nested object trees are
never part of canonical state; composition eagerly normalizes manifests, not
hypergraph contents.

This is a pure stdlib-only module, not an agent engine.  Retry, persistence,
learned routing, budgets, and event-log concurrency belong to a later engine
boundary.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field as dc_field
from typing import Iterable

from hswm_field_algebra import Field, SeamArc, field_id, merge, merge_all


SCHEMA = "hswm-open-manifest/v1"


class UnsupportedMaterialization(ValueError):
    """The open manifest contains semantics the legacy Field cannot represent."""


def _require_text(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")


def _normalize_by_id(items, *, key, canonical, label: str):
    """Canonical set union: same id+payload is a no-op; conflict fails closed."""
    by_id = {}
    for item in items:
        item_id = key(item)
        if item_id in by_id:
            if canonical(by_id[item_id]) != canonical(item):
                raise ValueError(
                    f"{label} conflict {item_id}: same id, different payload"
                )
        else:
            by_id[item_id] = item
    return tuple(by_id[k] for k in sorted(by_id))


@dataclass(frozen=True, order=True)
class SemanticWeight:
    """Slow edge potential in normalized log-salience space."""

    edge_id: str
    log_salience: float

    def __post_init__(self) -> None:
        _require_text(self.edge_id, "edge_id")
        if isinstance(self.log_salience, bool) or not isinstance(
            self.log_salience, (int, float)
        ):
            raise ValueError("log_salience must be numeric")
        value = float(self.log_salience)
        if not math.isfinite(value) or value > 0.0:
            raise ValueError("log_salience must be finite and <= 0")
        # Avoid two JSON spellings for the neutral element.
        object.__setattr__(self, "log_salience", 0.0 if value == 0.0 else value)

    def canonical(self) -> dict:
        return {"edge_id": self.edge_id, "log_salience": self.log_salience}


@dataclass(frozen=True, order=True)
class Port:
    port_id: str
    vertex_id: str
    semantic_type: str
    role: str
    polarity: str = "bi"
    visibility: str = "public"

    def __post_init__(self) -> None:
        for label, value in (
            ("port_id", self.port_id),
            ("vertex_id", self.vertex_id),
            ("semantic_type", self.semantic_type),
            ("role", self.role),
        ):
            _require_text(value, label)
        if self.polarity not in {"in", "out", "bi"}:
            raise ValueError("polarity must be one of: in, out, bi")
        if self.visibility not in {"public", "private"}:
            raise ValueError("visibility must be one of: public, private")

    def canonical(self) -> dict:
        return {
            "port_id": self.port_id,
            "vertex_id": self.vertex_id,
            "semantic_type": self.semantic_type,
            "role": self.role,
            "polarity": self.polarity,
            "visibility": self.visibility,
        }


@dataclass(frozen=True)
class Mount:
    """One instance of an atomic legacy Field inside the open manifest."""

    mount_id: str
    field: Field = dc_field(repr=False, compare=False)
    ports: tuple[Port, ...] = ()
    weights: tuple[SemanticWeight, ...] = ()
    field_digest: str = dc_field(init=False)

    def __post_init__(self) -> None:
        _require_text(self.mount_id, "mount_id")
        ports = _normalize_by_id(
            self.ports,
            key=lambda p: p.port_id,
            canonical=lambda p: p.canonical(),
            label="port",
        )
        weights = _normalize_by_id(
            self.weights,
            key=lambda w: w.edge_id,
            canonical=lambda w: w.canonical(),
            label="weight",
        )
        for port in ports:
            if port.vertex_id not in self.field.hg.vertices:
                raise ValueError(
                    f"port {port.port_id} addresses missing vertex {port.vertex_id}"
                )
        expected = set(self.field.hg.edges)
        actual = {weight.edge_id for weight in weights}
        if expected != actual:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            raise ValueError(
                f"semantic weights must cover every field edge exactly; "
                f"missing={missing}, extra={extra}"
            )
        object.__setattr__(self, "ports", ports)
        object.__setattr__(self, "weights", weights)
        object.__setattr__(self, "field_digest", field_id(self.field))

    def canonical(self) -> dict:
        return {
            "mount_id": self.mount_id,
            "field_id": self.field_digest,
            "ports": [port.canonical() for port in self.ports],
            "weights": [weight.canonical() for weight in self.weights],
        }


@dataclass(frozen=True, order=True)
class PortAddress:
    mount_id: str
    port_id: str

    def __post_init__(self) -> None:
        _require_text(self.mount_id, "mount_id")
        _require_text(self.port_id, "port_id")

    def canonical(self) -> dict:
        return {"mount_id": self.mount_id, "port_id": self.port_id}


@dataclass(frozen=True, order=True)
class InterfacePort:
    interface_id: str
    address: PortAddress

    def __post_init__(self) -> None:
        _require_text(self.interface_id, "interface_id")

    def canonical(self) -> dict:
        return {
            "interface_id": self.interface_id,
            "address": self.address.canonical(),
        }


@dataclass(frozen=True, order=True)
class ConnectorEndpoint:
    mount_id: str
    port_id: str
    relation_role: str

    def __post_init__(self) -> None:
        _require_text(self.mount_id, "mount_id")
        _require_text(self.port_id, "port_id")
        _require_text(self.relation_role, "relation_role")

    @property
    def address(self) -> PortAddress:
        return PortAddress(self.mount_id, self.port_id)

    def canonical(self) -> dict:
        return {
            "mount_id": self.mount_id,
            "port_id": self.port_id,
            "relation_role": self.relation_role,
        }


@dataclass(frozen=True)
class Connector:
    """Evidence-bearing typed n-ary seam between exposed ports."""

    connector_id: str
    endpoints: tuple[ConnectorEndpoint, ...]
    relation_type: str
    evidence: str
    event_id: str

    def __post_init__(self) -> None:
        for label, value in (
            ("connector_id", self.connector_id),
            ("relation_type", self.relation_type),
            ("evidence", self.evidence),
            ("event_id", self.event_id),
        ):
            _require_text(value, label)
        endpoints = tuple(sorted(self.endpoints))
        if len(endpoints) < 2:
            raise ValueError("connector needs at least two endpoints")
        addresses = [endpoint.address for endpoint in endpoints]
        if len(addresses) != len(set(addresses)):
            raise ValueError("connector endpoints must address distinct ports")
        object.__setattr__(self, "endpoints", endpoints)

    def canonical(self) -> dict:
        return {
            "connector_id": self.connector_id,
            "endpoints": [endpoint.canonical() for endpoint in self.endpoints],
            "relation_type": self.relation_type,
            "evidence": self.evidence,
            "event_id": self.event_id,
        }


@dataclass(frozen=True)
class OpenHSWM:
    """The one public HSWM type for both atomic and aggregate values."""

    mounts: tuple[Mount, ...] = ()
    connectors: tuple[Connector, ...] = ()
    interfaces: tuple[InterfacePort, ...] = ()
    schema: str = dc_field(default=SCHEMA, init=False)

    def __post_init__(self) -> None:
        mounts = _normalize_by_id(
            self.mounts,
            key=lambda m: m.mount_id,
            canonical=lambda m: m.canonical(),
            label="mount",
        )
        connectors = _normalize_by_id(
            self.connectors,
            key=lambda c: c.connector_id,
            canonical=lambda c: c.canonical(),
            label="connector",
        )
        interfaces = _normalize_by_id(
            self.interfaces,
            key=lambda p: p.interface_id,
            canonical=lambda p: p.canonical(),
            label="interface",
        )

        port_lookup = {
            (mount.mount_id, port.port_id): port
            for mount in mounts
            for port in mount.ports
        }
        event_ids = {}
        for connector in connectors:
            prior = event_ids.get(connector.event_id)
            if prior is not None and prior != connector.connector_id:
                raise ValueError(
                    f"event conflict {connector.event_id}: used by {prior} and "
                    f"{connector.connector_id}"
                )
            event_ids[connector.event_id] = connector.connector_id
            for endpoint in connector.endpoints:
                port = port_lookup.get((endpoint.mount_id, endpoint.port_id))
                if port is None:
                    raise ValueError(
                        f"connector {connector.connector_id} has dangling endpoint "
                        f"{endpoint.mount_id}/{endpoint.port_id}"
                    )
                if port.visibility != "public":
                    raise ValueError(
                        f"connector {connector.connector_id} addresses private port "
                        f"{endpoint.mount_id}/{endpoint.port_id}"
                    )
        for interface in interfaces:
            address = (interface.address.mount_id, interface.address.port_id)
            port = port_lookup.get(address)
            if port is None:
                raise ValueError(
                    f"interface {interface.interface_id} has dangling address "
                    f"{interface.address.mount_id}/{interface.address.port_id}"
                )
            if port.visibility != "public":
                raise ValueError(
                    f"interface {interface.interface_id} exposes private port"
                )

        object.__setattr__(self, "mounts", mounts)
        object.__setattr__(self, "connectors", connectors)
        object.__setattr__(self, "interfaces", interfaces)

    @classmethod
    def empty(cls) -> "OpenHSWM":
        return cls()

    @classmethod
    def from_field(
        cls,
        field: Field,
        *,
        mount_id: str,
        ports: Iterable[Port] = (),
        weights: Iterable[SemanticWeight] | None = None,
    ) -> "OpenHSWM":
        port_tuple = tuple(ports)
        if weights is None:
            weight_tuple = tuple(
                SemanticWeight(edge_id=edge_id, log_salience=0.0)
                for edge_id in sorted(field.hg.edges)
            )
        else:
            weight_tuple = tuple(weights)
        mount = Mount(
            mount_id=mount_id,
            field=field,
            ports=port_tuple,
            weights=weight_tuple,
        )
        interfaces = tuple(
            InterfacePort(
                interface_id=port.port_id,
                address=PortAddress(mount_id=mount_id, port_id=port.port_id),
            )
            for port in mount.ports
            if port.visibility == "public"
        )
        return cls(mounts=(mount,), interfaces=interfaces)

    def canonical(self) -> dict:
        return {
            "schema": self.schema,
            "mounts": [mount.canonical() for mount in self.mounts],
            "connectors": [connector.canonical() for connector in self.connectors],
            "interfaces": [interface.canonical() for interface in self.interfaces],
        }

    def semantic_digest(self) -> str:
        blob = json.dumps(
            self.canonical(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()

    def resolve_port(self, interface_id: str) -> PortAddress:
        for interface in self.interfaces:
            if interface.interface_id == interface_id:
                return interface.address
        raise KeyError(f"unknown interface port: {interface_id}")

    def endpoint(self, interface_id: str, relation_role: str) -> ConnectorEndpoint:
        address = self.resolve_port(interface_id)
        return ConnectorEndpoint(
            mount_id=address.mount_id,
            port_id=address.port_id,
            relation_role=relation_role,
        )

    def specialize(
        self,
        mount_ids: Iterable[str],
        *,
        interface_ids: Iterable[str] | None = None,
    ) -> "OpenHSWM":
        """Immutable induced open-subgraph view over selected mounts."""
        selected = set(mount_ids)
        known_mounts = {mount.mount_id for mount in self.mounts}
        unknown = sorted(selected - known_mounts)
        if unknown:
            raise ValueError(f"unknown specialization mounts: {unknown}")
        mounts = tuple(mount for mount in self.mounts if mount.mount_id in selected)
        connectors = tuple(
            connector
            for connector in self.connectors
            if all(endpoint.mount_id in selected for endpoint in connector.endpoints)
        )
        available_interfaces = tuple(
            interface
            for interface in self.interfaces
            if interface.address.mount_id in selected
        )
        if interface_ids is None:
            interfaces = available_interfaces
        else:
            requested = set(interface_ids)
            known_interfaces = {
                interface.interface_id for interface in available_interfaces
            }
            unknown_interfaces = sorted(requested - known_interfaces)
            if unknown_interfaces:
                raise ValueError(
                    f"unknown specialization interfaces: {unknown_interfaces}"
                )
            interfaces = tuple(
                interface
                for interface in available_interfaces
                if interface.interface_id in requested
            )
        return OpenHSWM(
            mounts=mounts, connectors=connectors, interfaces=interfaces
        )

    def separate(self, connector_ids: Iterable[str]) -> "SeparationResult":
        """Cut connectors and return explicit connected parts plus cut-set receipt."""
        cut_ids = set(connector_ids)
        cut = tuple(
            connector
            for connector in self.connectors
            if connector.connector_id in cut_ids
        )
        remaining = tuple(
            connector
            for connector in self.connectors
            if connector.connector_id not in cut_ids
        )
        mount_ids = [mount.mount_id for mount in self.mounts]
        adjacency = {mount_id: set() for mount_id in mount_ids}
        for connector in remaining:
            incident = sorted({e.mount_id for e in connector.endpoints})
            for left in incident:
                adjacency[left].update(right for right in incident if right != left)

        components = []
        unseen = set(mount_ids)
        while unseen:
            seed = min(unseen)
            stack = [seed]
            component = set()
            while stack:
                current = stack.pop()
                if current in component:
                    continue
                component.add(current)
                unseen.discard(current)
                stack.extend(sorted(adjacency[current] - component, reverse=True))
            components.append(component)

        parts = []
        for component in sorted(components, key=lambda c: tuple(sorted(c))):
            part_mounts = tuple(
                mount for mount in self.mounts if mount.mount_id in component
            )
            part_connectors = tuple(
                connector
                for connector in remaining
                if all(e.mount_id in component for e in connector.endpoints)
            )
            part_interfaces = [
                interface
                for interface in self.interfaces
                if interface.address.mount_id in component
            ]
            # A cut exposes its former boundary explicitly so the receipt can
            # recompose through the same public API even if the source projected
            # that interface away.
            for connector in cut:
                for endpoint in connector.endpoints:
                    if endpoint.mount_id in component:
                        boundary_id = (
                            f"__cut__:{connector.connector_id}:"
                            f"{endpoint.mount_id}:{endpoint.port_id}"
                        )
                        part_interfaces.append(
                            InterfacePort(
                                interface_id=boundary_id,
                                address=endpoint.address,
                            )
                        )
            parts.append(
                OpenHSWM(
                    mounts=part_mounts,
                    connectors=part_connectors,
                    interfaces=tuple(part_interfaces),
                )
            )
        return SeparationResult(
            parts=tuple(parts),
            cut_connectors=cut,
            source_interfaces=self.interfaces,
            source_digest=self.semantic_digest(),
        )


@dataclass(frozen=True)
class SeparationResult:
    parts: tuple[OpenHSWM, ...]
    cut_connectors: tuple[Connector, ...]
    source_interfaces: tuple[InterfacePort, ...]
    source_digest: str

    def recompose(self) -> OpenHSWM:
        staged = compose(self.parts, connectors=self.cut_connectors)
        restored = OpenHSWM(
            mounts=staged.mounts,
            connectors=staged.connectors,
            interfaces=self.source_interfaces,
        )
        if restored.semantic_digest() != self.source_digest:
            raise ValueError("separation receipt failed to restore source digest")
        return restored


@dataclass(frozen=True)
class MaterializedField:
    """Legacy flat cache plus the semantic state legacy Field cannot carry."""

    field: Field = dc_field(repr=False, compare=False)
    weights: tuple[SemanticWeight, ...]
    source_manifest_digest: str
    field_digest: str = dc_field(init=False)

    def __post_init__(self) -> None:
        weights = _normalize_by_id(
            self.weights,
            key=lambda w: w.edge_id,
            canonical=lambda w: w.canonical(),
            label="materialized weight",
        )
        expected = set(self.field.hg.edges)
        actual = {weight.edge_id for weight in weights}
        if expected != actual:
            raise ValueError("materialized weights do not cover the flat field")
        object.__setattr__(self, "weights", weights)
        object.__setattr__(self, "field_digest", field_id(self.field))


def compose(
    parts: Iterable[OpenHSWM],
    *,
    connectors: Iterable[Connector] = (),
    expose: Iterable[InterfacePort] = (),
    hide: Iterable[str] = (),
) -> OpenHSWM:
    """Normalize any finite collection of HSWMs into the same HSWM type.

    New connectors may address only ports exported by an operand.  Existing
    connectors are already internal canonical state and are simply unioned.
    No legacy Field merge occurs here.
    """
    part_tuple = tuple(parts)
    if any(not isinstance(part, OpenHSWM) for part in part_tuple):
        raise TypeError("compose accepts only OpenHSWM operands")
    allowed_addresses = {
        interface.address
        for part in part_tuple
        for interface in part.interfaces
    }
    new_connectors = tuple(connectors)
    for connector in new_connectors:
        for endpoint in connector.endpoints:
            if endpoint.address not in allowed_addresses:
                raise ValueError(
                    f"connector {connector.connector_id} addresses a port not "
                    f"exposed by an operand: {endpoint.mount_id}/{endpoint.port_id}"
                )

    mounts = tuple(mount for part in part_tuple for mount in part.mounts)
    all_connectors = tuple(
        connector for part in part_tuple for connector in part.connectors
    ) + new_connectors
    interfaces = tuple(
        interface for part in part_tuple for interface in part.interfaces
    ) + tuple(expose)
    hidden = set(hide)
    known_interface_ids = {interface.interface_id for interface in interfaces}
    unknown_hidden = sorted(hidden - known_interface_ids)
    if unknown_hidden:
        raise ValueError(f"cannot hide unknown interfaces: {unknown_hidden}")
    interfaces = tuple(
        interface for interface in interfaces if interface.interface_id not in hidden
    )
    return OpenHSWM(
        mounts=mounts,
        connectors=all_connectors,
        interfaces=interfaces,
    )


def materialize(hswm: OpenHSWM) -> MaterializedField:
    """Explicitly lower a representable OpenHSWM into the legacy eager Field.

    The legacy format supports only binary canonical-identity seams and has no
    mount-instance namespace.  Unsupported semantics fail closed instead of
    being silently flattened.
    """
    if not hswm.mounts:
        raise UnsupportedMaterialization(
            "the legacy Field algebra has no empty identity value"
        )
    seen_field_digests = {}
    for mount in hswm.mounts:
        current_digest = field_id(mount.field)
        if current_digest != mount.field_digest:
            raise UnsupportedMaterialization(
                f"mounted field drift at {mount.mount_id}: "
                f"{mount.field_digest} != {current_digest}"
            )
        if mount.field_digest in seen_field_digests:
            prior = seen_field_digests[mount.field_digest]
            raise UnsupportedMaterialization(
                "legacy Field would collapse mount multiplicity: "
                f"{prior}, {mount.mount_id}"
            )
        seen_field_digests[mount.field_digest] = mount.mount_id

    seams = []
    for connector in hswm.connectors:
        if connector.relation_type != "canonical_identity":
            raise UnsupportedMaterialization(
                f"legacy Field cannot encode relation type {connector.relation_type}"
            )
        if len(connector.endpoints) != 2:
            raise UnsupportedMaterialization(
                f"legacy SeamArc cannot encode {len(connector.endpoints)}-ary "
                f"connector {connector.connector_id}"
            )
        left, right = connector.endpoints
        mount_lookup = {mount.mount_id: mount for mount in hswm.mounts}
        left_mount = mount_lookup[left.mount_id]
        right_mount = mount_lookup[right.mount_id]
        port_lookup = {
            (mount.mount_id, port.port_id): port
            for mount in hswm.mounts
            for port in mount.ports
        }
        left_port = port_lookup[(left.mount_id, left.port_id)]
        right_port = port_lookup[(right.mount_id, right.port_id)]
        # Accessing mount fields above is deliberate: it keeps this boundary
        # explicit and makes future namespaced materializers local to this code.
        _ = left_mount, right_mount
        seams.append(
            SeamArc(
                arc_id=connector.connector_id,
                left_vid=left_port.vertex_id,
                right_vid=right_port.vertex_id,
                evidence=connector.evidence,
                event_id=connector.event_id,
            )
        )

    flat = merge_all([mount.field for mount in hswm.mounts])
    if seams:
        flat = merge(flat, flat, new_seam=tuple(seams))

    weights_by_edge = {}
    for mount in hswm.mounts:
        for weight in mount.weights:
            prior = weights_by_edge.get(weight.edge_id)
            if prior is not None and prior != weight:
                raise UnsupportedMaterialization(
                    f"legacy edge {weight.edge_id} has conflicting mount weights"
                )
            weights_by_edge[weight.edge_id] = weight
    return MaterializedField(
        field=flat,
        weights=tuple(weights_by_edge.values()),
        source_manifest_digest=hswm.semantic_digest(),
    )


__all__ = [
    "Connector",
    "ConnectorEndpoint",
    "InterfacePort",
    "MaterializedField",
    "Mount",
    "OpenHSWM",
    "Port",
    "PortAddress",
    "SemanticWeight",
    "SeparationResult",
    "UnsupportedMaterialization",
    "compose",
    "materialize",
]

