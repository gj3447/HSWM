#!/usr/bin/env python3
"""Canonical v2 kernel for fixed-depth-free, self-similar HSWM composition.

The kernel is deliberately smaller than an agent runtime.  It owns immutable
field snapshots, mount-qualified interfaces, connector admission, flat normal
form, reversible separation receipts, and explicit safe materialization.

The frozen v1 prototype remains in ``hswm_open_composition.py`` with its partial
LakatoTree receipt.  This module closes the counterexamples documented in
``AMENDMENT_OPEN_HSWM_KERNEL_V2_2026-07-22.md`` without rewriting that history.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field as dc_field
from typing import Iterable, Mapping, Optional

from hswm_field_algebra import Field, SeamArc, field_id
from hswm_hypergraph import Hyperedge, Hypergraph, Vertex
from hswm_open_composition import (
    Connector,
    ConnectorEndpoint,
    InterfacePort,
    Port,
    PortAddress,
    SemanticWeight,
    UnsupportedMaterialization,
)


SCHEMA = "hswm-open-kernel/v2"


def _require_text(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")


def _normalize_by_id(items, *, key, canonical, label: str):
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
    return tuple(by_id[item_id] for item_id in sorted(by_id))


def qualified_interface_id(mount_id: str, port_id: str) -> str:
    """Injective readable encoding of a mount-qualified local port name."""
    _require_text(mount_id, "mount_id")
    _require_text(port_id, "port_id")
    return f"q{len(mount_id)}:{mount_id}{len(port_id)}:{port_id}"


@dataclass(frozen=True, order=True)
class FrozenVertex:
    vid: str
    name: str
    kind: str

    def __post_init__(self) -> None:
        _require_text(self.vid, "vertex id")
        _require_text(self.name, "vertex name")
        _require_text(self.kind, "vertex kind")

    def canonical(self) -> dict:
        return {"vid": self.vid, "name": self.name, "kind": self.kind}


@dataclass(frozen=True, order=True)
class FrozenEdge:
    eid: str
    value: str
    members: tuple[str, ...]
    clusters: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_text(self.eid, "edge id")
        if not isinstance(self.value, str):
            raise ValueError("edge value must be a string")
        for member in self.members:
            _require_text(member, f"edge {self.eid} member")
        for cluster in self.clusters:
            _require_text(cluster, f"edge cluster for {self.eid}")
        members = tuple(sorted(self.members))
        if len(members) != len(set(members)):
            raise ValueError(f"edge {self.eid} contains duplicate members")
        object.__setattr__(self, "members", members)
        object.__setattr__(self, "clusters", tuple(self.clusters))

    def canonical(self) -> dict:
        return {
            "eid": self.eid,
            "value": self.value,
            "members": list(self.members),
            "clusters": list(self.clusters),
        }


def _seam_canonical(seam: SeamArc) -> dict:
    return seam.canonical()


def _freeze_seam(seam: SeamArc) -> SeamArc:
    """Validate and copy a legacy seam into string-only immutable state."""
    if not isinstance(seam, SeamArc):
        raise ValueError("snapshot seam must be a SeamArc")
    for label, value in (
        ("seam arc_id", seam.arc_id),
        ("seam left_vid", seam.left_vid),
        ("seam right_vid", seam.right_vid),
        ("seam evidence", seam.evidence),
        ("seam event_id", seam.event_id),
    ):
        _require_text(value, label)
    return SeamArc(
        arc_id=seam.arc_id,
        left_vid=seam.left_vid,
        right_vid=seam.right_vid,
        evidence=seam.evidence,
        event_id=seam.event_id,
    )


@dataclass(frozen=True)
class FrozenFieldSnapshot:
    """Immutable canonical subset of legacy Field state.

    Embeddings are intentionally excluded because legacy ``field_id`` defines
    them as derived state.  Every semantic/provenance record used by the legacy
    algebra is frozen and can be defensively thawed.
    """

    vertices: tuple[FrozenVertex, ...]
    edges: tuple[FrozenEdge, ...]
    provenance: tuple[tuple[str, tuple[str, ...]], ...]
    ledger: tuple[str, ...]
    seams: tuple[SeamArc, ...]
    legacy_digest: str = dc_field(init=False)

    def __post_init__(self) -> None:
        vertices = _normalize_by_id(
            self.vertices,
            key=lambda vertex: vertex.vid,
            canonical=lambda vertex: vertex.canonical(),
            label="snapshot vertex",
        )
        edges = _normalize_by_id(
            self.edges,
            key=lambda edge: edge.eid,
            canonical=lambda edge: edge.canonical(),
            label="snapshot edge",
        )
        vertex_ids = {vertex.vid for vertex in vertices}
        for edge in edges:
            missing = sorted(set(edge.members) - vertex_ids)
            if missing:
                raise ValueError(f"edge {edge.eid} references missing vertices {missing}")

        provenance_by_edge = {}
        for edge_id, sources in self.provenance:
            _require_text(edge_id, "provenance edge id")
            canonical_sources = tuple(sorted(set(sources)))
            if not canonical_sources:
                raise ValueError(
                    f"edge {edge_id} must have non-empty provenance"
                )
            for source in canonical_sources:
                _require_text(source, f"provenance source for {edge_id}")
            if edge_id in provenance_by_edge:
                if provenance_by_edge[edge_id] != canonical_sources:
                    raise ValueError(f"provenance conflict for edge {edge_id}")
            else:
                provenance_by_edge[edge_id] = canonical_sources
        edge_ids = {edge.eid for edge in edges}
        if set(provenance_by_edge) != edge_ids:
            missing = sorted(edge_ids - set(provenance_by_edge))
            extra = sorted(set(provenance_by_edge) - edge_ids)
            raise ValueError(
                f"provenance must exactly cover snapshot edges; "
                f"missing={missing}, extra={extra}"
            )

        seams = _normalize_by_id(
            tuple(_freeze_seam(seam) for seam in self.seams),
            key=lambda seam: seam.arc_id,
            canonical=_seam_canonical,
            label="snapshot seam",
        )
        for seam in seams:
            for vertex_id in (seam.left_vid, seam.right_vid):
                if vertex_id not in vertex_ids:
                    raise ValueError(
                        f"seam {seam.arc_id} references missing vertex {vertex_id}"
                    )
        ledger = tuple(sorted(set(self.ledger)))
        for event_id in ledger:
            _require_text(event_id, "ledger event id")

        object.__setattr__(self, "vertices", vertices)
        object.__setattr__(self, "edges", edges)
        object.__setattr__(
            self,
            "provenance",
            tuple((edge_id, provenance_by_edge[edge_id]) for edge_id in sorted(edge_ids)),
        )
        object.__setattr__(self, "ledger", ledger)
        object.__setattr__(self, "seams", seams)
        object.__setattr__(self, "legacy_digest", field_id(self.thaw()))

    @classmethod
    def capture(cls, field: Field) -> "FrozenFieldSnapshot":
        field.hg.check_incidence()
        return cls(
            vertices=tuple(
                FrozenVertex(vertex.vid, vertex.name, vertex.kind)
                for _, vertex in sorted(field.hg.vertices.items())
            ),
            edges=tuple(
                FrozenEdge(
                    edge.eid,
                    edge.value,
                    tuple(edge.members),
                    tuple(edge.clusters),
                )
                for _, edge in sorted(field.hg.edges.items())
            ),
            provenance=tuple(
                (edge_id, tuple(sources))
                for edge_id, sources in sorted(field.provenance.items())
            ),
            ledger=tuple(field.ledger),
            seams=tuple(field.seam),
        )

    def thaw(self) -> Field:
        """Return a fresh mutable legacy value; never expose snapshot internals."""
        vertices = {
            vertex.vid: Vertex(
                vid=vertex.vid,
                name=vertex.name,
                kind=vertex.kind,
                incident_edges=[],
            )
            for vertex in self.vertices
        }
        edges = {
            edge.eid: Hyperedge(
                eid=edge.eid,
                value=edge.value,
                members=list(edge.members),
                clusters=list(edge.clusters),
            )
            for edge in self.edges
        }
        for edge in edges.values():
            for vertex_id in edge.members:
                vertices[vertex_id].incident_edges.append(edge.eid)
        for vertex in vertices.values():
            vertex.incident_edges.sort()
        return Field(
            hg=Hypergraph(vertices=vertices, edges=edges),
            provenance={edge_id: sources for edge_id, sources in self.provenance},
            ledger=frozenset(self.ledger),
            seam=tuple(_freeze_seam(seam) for seam in self.seams),
        )


@dataclass(frozen=True)
class Mount:
    mount_id: str
    snapshot: FrozenFieldSnapshot
    ports: tuple[Port, ...] = ()
    weights: tuple[SemanticWeight, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.mount_id, "mount_id")
        ports = _normalize_by_id(
            self.ports,
            key=lambda port: port.port_id,
            canonical=lambda port: port.canonical(),
            label="port",
        )
        weights = _normalize_by_id(
            self.weights,
            key=lambda weight: weight.edge_id,
            canonical=lambda weight: weight.canonical(),
            label="weight",
        )
        vertex_ids = {vertex.vid for vertex in self.snapshot.vertices}
        for port in ports:
            if port.vertex_id not in vertex_ids:
                raise ValueError(
                    f"port {port.port_id} addresses missing vertex {port.vertex_id}"
                )
        edge_ids = {edge.eid for edge in self.snapshot.edges}
        weight_ids = {weight.edge_id for weight in weights}
        if edge_ids != weight_ids:
            raise ValueError(
                "semantic weights must cover every snapshot edge exactly; "
                f"missing={sorted(edge_ids - weight_ids)}, "
                f"extra={sorted(weight_ids - edge_ids)}"
            )
        object.__setattr__(self, "ports", ports)
        object.__setattr__(self, "weights", weights)

    @property
    def field_digest(self) -> str:
        return self.snapshot.legacy_digest

    def thaw_field(self) -> Field:
        return self.snapshot.thaw()

    def canonical(self) -> dict:
        return {
            "mount_id": self.mount_id,
            "field_id": self.field_digest,
            "ports": [port.canonical() for port in self.ports],
            "weights": [weight.canonical() for weight in self.weights],
        }


class OpenHSWM:
    """Factory-sealed immutable value for both atomic and aggregate HSWMs."""

    __slots__ = ("_mounts", "_connectors", "_interfaces", "_digest")

    def __init__(self, *_args, **_kwargs):
        raise TypeError("OpenHSWM is factory-sealed; use empty/from_field/compose")

    def __setattr__(self, _name, _value):
        raise AttributeError("OpenHSWM is immutable")

    @classmethod
    def _from_state(
        cls,
        *,
        mounts: Iterable[Mount],
        connectors: Iterable[Connector],
        interfaces: Iterable[InterfacePort],
    ) -> "OpenHSWM":
        mounts = _normalize_by_id(
            tuple(mounts),
            key=lambda mount: mount.mount_id,
            canonical=lambda mount: mount.canonical(),
            label="mount",
        )
        connectors = _normalize_by_id(
            tuple(connectors),
            key=lambda connector: connector.connector_id,
            canonical=lambda connector: connector.canonical(),
            label="connector",
        )
        interfaces = _normalize_by_id(
            tuple(interfaces),
            key=lambda interface: interface.interface_id,
            canonical=lambda interface: interface.canonical(),
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
                    f"event conflict {connector.event_id}: {prior} vs "
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
                        f"connector {connector.connector_id} addresses private port"
                    )
        for interface in interfaces:
            port = port_lookup.get(
                (interface.address.mount_id, interface.address.port_id)
            )
            if port is None:
                raise ValueError(
                    f"interface {interface.interface_id} has dangling address"
                )
            if port.visibility != "public":
                raise ValueError(
                    f"interface {interface.interface_id} exposes private port"
                )

        canonical = {
            "schema": SCHEMA,
            "mounts": [mount.canonical() for mount in mounts],
            "connectors": [connector.canonical() for connector in connectors],
            "interfaces": [interface.canonical() for interface in interfaces],
        }
        blob = json.dumps(
            canonical,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        instance = object.__new__(cls)
        object.__setattr__(instance, "_mounts", mounts)
        object.__setattr__(instance, "_connectors", connectors)
        object.__setattr__(instance, "_interfaces", interfaces)
        object.__setattr__(instance, "_digest", hashlib.sha256(blob).hexdigest())
        return instance

    @classmethod
    def empty(cls) -> "OpenHSWM":
        return cls._from_state(mounts=(), connectors=(), interfaces=())

    @classmethod
    def from_field(
        cls,
        field: Field,
        *,
        mount_id: str,
        ports: Iterable[Port] = (),
        weights: Optional[Iterable[SemanticWeight]] = None,
        interface_aliases: Optional[Mapping[str, str]] = None,
    ) -> "OpenHSWM":
        snapshot = FrozenFieldSnapshot.capture(field)
        ports = tuple(ports)
        if weights is None:
            weights = tuple(
                SemanticWeight(edge.eid, 0.0) for edge in snapshot.edges
            )
        else:
            weights = tuple(weights)
        mount = Mount(mount_id, snapshot, ports, weights)
        aliases = dict(interface_aliases or {})
        public_port_ids = {
            port.port_id for port in mount.ports if port.visibility == "public"
        }
        unknown_aliases = sorted(set(aliases) - public_port_ids)
        if unknown_aliases:
            raise ValueError(
                f"interface aliases reference non-public ports: {unknown_aliases}"
            )
        interfaces = tuple(
            InterfacePort(
                aliases.get(
                    port.port_id,
                    qualified_interface_id(mount.mount_id, port.port_id),
                ),
                PortAddress(mount.mount_id, port.port_id),
            )
            for port in mount.ports
            if port.visibility == "public"
        )
        return cls._from_state(
            mounts=(mount,), connectors=(), interfaces=interfaces
        )

    @property
    def mounts(self) -> tuple[Mount, ...]:
        return self._mounts

    @property
    def connectors(self) -> tuple[Connector, ...]:
        return self._connectors

    @property
    def interfaces(self) -> tuple[InterfacePort, ...]:
        return self._interfaces

    def canonical(self) -> dict:
        return {
            "schema": SCHEMA,
            "mounts": [mount.canonical() for mount in self._mounts],
            "connectors": [connector.canonical() for connector in self._connectors],
            "interfaces": [interface.canonical() for interface in self._interfaces],
        }

    def semantic_digest(self) -> str:
        return self._digest

    def resolve_port(self, interface_id: str) -> PortAddress:
        for interface in self._interfaces:
            if interface.interface_id == interface_id:
                return interface.address
        raise KeyError(f"unknown interface port: {interface_id}")

    def endpoint(self, interface_id: str, relation_role: str) -> ConnectorEndpoint:
        address = self.resolve_port(interface_id)
        return ConnectorEndpoint(address.mount_id, address.port_id, relation_role)

    def specialize(
        self,
        mount_ids: Iterable[str],
        *,
        interface_ids: Optional[Iterable[str]] = None,
    ) -> "OpenHSWM":
        selected = set(mount_ids)
        known = {mount.mount_id for mount in self._mounts}
        unknown = sorted(selected - known)
        if unknown:
            raise ValueError(f"unknown specialization mounts: {unknown}")
        mounts = tuple(
            mount for mount in self._mounts if mount.mount_id in selected
        )
        connectors = tuple(
            connector
            for connector in self._connectors
            if all(endpoint.mount_id in selected for endpoint in connector.endpoints)
        )
        available = tuple(
            interface
            for interface in self._interfaces
            if interface.address.mount_id in selected
        )
        if interface_ids is None:
            interfaces = available
        else:
            requested = set(interface_ids)
            available_ids = {interface.interface_id for interface in available}
            unknown_interfaces = sorted(requested - available_ids)
            if unknown_interfaces:
                raise ValueError(
                    f"unknown specialization interfaces: {unknown_interfaces}"
                )
            interfaces = tuple(
                interface
                for interface in available
                if interface.interface_id in requested
            )
        return OpenHSWM._from_state(
            mounts=mounts, connectors=connectors, interfaces=interfaces
        )

    def separate(self, connector_ids: Iterable[str]) -> "SeparationResult":
        cut_ids = set(connector_ids)
        cut = tuple(
            connector
            for connector in self._connectors
            if connector.connector_id in cut_ids
        )
        remaining = tuple(
            connector
            for connector in self._connectors
            if connector.connector_id not in cut_ids
        )
        mount_ids = [mount.mount_id for mount in self._mounts]
        adjacency = {mount_id: set() for mount_id in mount_ids}
        for connector in remaining:
            incident = sorted({endpoint.mount_id for endpoint in connector.endpoints})
            for left in incident:
                adjacency[left].update(
                    right for right in incident if right != left
                )
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
        for component in sorted(components, key=lambda item: tuple(sorted(item))):
            parts.append(
                OpenHSWM._from_state(
                    mounts=tuple(
                        mount
                        for mount in self._mounts
                        if mount.mount_id in component
                    ),
                    connectors=tuple(
                        connector
                        for connector in remaining
                        if all(
                            endpoint.mount_id in component
                            for endpoint in connector.endpoints
                        )
                    ),
                    interfaces=tuple(
                        interface
                        for interface in self._interfaces
                        if interface.address.mount_id in component
                    ),
                )
            )
        return SeparationResult._from_source(
            parts=tuple(parts),
            cut_connectors=cut,
            source_interfaces=self._interfaces,
            source_digest=self._digest,
        )


class SeparationResult:
    """Factory-sealed structured cut receipt; no synthetic boundary IDs."""

    __slots__ = (
        "_parts",
        "_cut_connectors",
        "_source_interfaces",
        "_source_digest",
    )

    def __init__(self, *_args, **_kwargs):
        raise TypeError("SeparationResult is factory-sealed; use OpenHSWM.separate")

    def __setattr__(self, _name, _value):
        raise AttributeError("SeparationResult is immutable")

    @classmethod
    def _from_source(
        cls,
        *,
        parts: tuple[OpenHSWM, ...],
        cut_connectors: tuple[Connector, ...],
        source_interfaces: tuple[InterfacePort, ...],
        source_digest: str,
    ) -> "SeparationResult":
        instance = object.__new__(cls)
        object.__setattr__(instance, "_parts", parts)
        object.__setattr__(instance, "_cut_connectors", cut_connectors)
        object.__setattr__(instance, "_source_interfaces", source_interfaces)
        object.__setattr__(instance, "_source_digest", source_digest)
        return instance

    @property
    def parts(self) -> tuple[OpenHSWM, ...]:
        return self._parts

    @property
    def cut_connectors(self) -> tuple[Connector, ...]:
        return self._cut_connectors

    def recompose(self) -> OpenHSWM:
        restored = OpenHSWM._from_state(
            mounts=tuple(mount for part in self._parts for mount in part.mounts),
            connectors=tuple(
                connector
                for part in self._parts
                for connector in part.connectors
            )
            + self._cut_connectors,
            interfaces=self._source_interfaces,
        )
        if restored.semantic_digest() != self._source_digest:
            raise ValueError("separation receipt failed to restore source digest")
        return restored


@dataclass(frozen=True)
class MaterializedField:
    field: Field = dc_field(repr=False, compare=False)
    weights: tuple[SemanticWeight, ...]
    source_manifest_digest: str
    shared_edge_ids: tuple[str, ...]
    field_digest: str = dc_field(init=False)

    def __post_init__(self) -> None:
        weights = _normalize_by_id(
            self.weights,
            key=lambda weight: weight.edge_id,
            canonical=lambda weight: weight.canonical(),
            label="materialized weight",
        )
        if {weight.edge_id for weight in weights} != set(self.field.hg.edges):
            raise ValueError("materialized weights do not exactly cover flat edges")
        object.__setattr__(self, "weights", weights)
        object.__setattr__(self, "shared_edge_ids", tuple(sorted(self.shared_edge_ids)))
        object.__setattr__(self, "field_digest", field_id(self.field))


def compose(
    parts: Iterable[OpenHSWM],
    *,
    connectors: Iterable[Connector] = (),
    expose: Iterable[InterfacePort] = (),
    hide: Iterable[str] = (),
) -> OpenHSWM:
    part_tuple = tuple(parts)
    if any(not isinstance(part, OpenHSWM) for part in part_tuple):
        raise TypeError("compose accepts only canonical OpenHSWM operands")
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
    known_interfaces = {interface.interface_id for interface in interfaces}
    unknown_hidden = sorted(hidden - known_interfaces)
    if unknown_hidden:
        raise ValueError(f"cannot hide unknown interfaces: {unknown_hidden}")
    interfaces = tuple(
        interface
        for interface in interfaces
        if interface.interface_id not in hidden
    )
    return OpenHSWM._from_state(
        mounts=mounts,
        connectors=all_connectors,
        interfaces=interfaces,
    )


def _materialize_snapshots(
    hswm: OpenHSWM,
    *,
    shared_edge_ids: set[str],
) -> MaterializedField:
    if not hswm.mounts:
        raise UnsupportedMaterialization(
            "the legacy Field representation has no empty identity"
        )

    field_digest_owner = {}
    for mount in hswm.mounts:
        prior = field_digest_owner.get(mount.field_digest)
        if prior is not None:
            raise UnsupportedMaterialization(
                f"materialization would collapse mount multiplicity: "
                f"{prior}, {mount.mount_id}"
            )
        field_digest_owner[mount.field_digest] = mount.mount_id

    vertices = {}
    edges = {}
    provenance = {}
    weights = {}
    edge_owners = {}
    overlap_ids = set()
    ledger = set()
    seams = {}

    for mount in hswm.mounts:
        ledger.update(mount.snapshot.ledger)
        mount_weights = {weight.edge_id: weight for weight in mount.weights}
        for vertex in mount.snapshot.vertices:
            prior = vertices.get(vertex.vid)
            if prior is not None and prior != vertex:
                raise UnsupportedMaterialization(
                    f"vertex conflict {vertex.vid}: same id, different payload"
                )
            vertices[vertex.vid] = vertex
        snapshot_provenance = dict(mount.snapshot.provenance)
        for edge in mount.snapshot.edges:
            prior = edges.get(edge.eid)
            if prior is not None:
                overlap_ids.add(edge.eid)
                if edge.eid not in shared_edge_ids:
                    raise UnsupportedMaterialization(
                        f"overlapping edge {edge.eid} requires shared_edge_ids capability"
                    )
                if prior != edge:
                    raise UnsupportedMaterialization(
                        f"edge conflict {edge.eid}: declared shared payload differs"
                    )
                if weights[edge.eid] != mount_weights[edge.eid]:
                    raise UnsupportedMaterialization(
                        f"shared edge weight conflict {edge.eid}"
                    )
                provenance[edge.eid] = tuple(
                    sorted(
                        set(provenance[edge.eid])
                        | set(snapshot_provenance[edge.eid])
                    )
                )
                edge_owners[edge.eid].add(mount.mount_id)
            else:
                edges[edge.eid] = edge
                provenance[edge.eid] = snapshot_provenance[edge.eid]
                weights[edge.eid] = mount_weights[edge.eid]
                edge_owners[edge.eid] = {mount.mount_id}
        for source_seam in mount.snapshot.seams:
            seam = _freeze_seam(source_seam)
            prior = seams.get(seam.arc_id)
            if prior is not None and prior != seam:
                raise UnsupportedMaterialization(
                    f"seam conflict {seam.arc_id}: same id, different payload"
                )
            seams[seam.arc_id] = seam

    unused_capabilities = sorted(shared_edge_ids - overlap_ids)
    if unused_capabilities:
        raise UnsupportedMaterialization(
            f"unused shared_edge_ids capabilities: {unused_capabilities}"
        )

    port_lookup = {
        (mount.mount_id, port.port_id): port
        for mount in hswm.mounts
        for port in mount.ports
    }
    for connector in hswm.connectors:
        if connector.relation_type != "canonical_identity":
            raise UnsupportedMaterialization(
                f"materialized Field cannot encode relation type "
                f"{connector.relation_type}"
            )
        if len(connector.endpoints) != 2:
            raise UnsupportedMaterialization(
                f"binary SeamArc cannot encode {len(connector.endpoints)}-ary "
                f"connector {connector.connector_id}"
            )
        endpoints_by_role = {
            endpoint.relation_role: endpoint for endpoint in connector.endpoints
        }
        if (
            set(endpoints_by_role) != {"left", "right"}
            or len(endpoints_by_role) != len(connector.endpoints)
        ):
            raise UnsupportedMaterialization(
                f"canonical_identity connector {connector.connector_id} requires "
                "exactly left and right endpoint roles"
            )
        left = endpoints_by_role["left"]
        right = endpoints_by_role["right"]
        left_vertex_id = port_lookup[(left.mount_id, left.port_id)].vertex_id
        right_vertex_id = port_lookup[(right.mount_id, right.port_id)].vertex_id
        if left_vertex_id == right_vertex_id:
            raise UnsupportedMaterialization(
                f"canonical_identity connector {connector.connector_id} requires "
                "distinct legacy vertices to preserve endpoint roles"
            )
        seam = SeamArc(
            connector.connector_id,
            left_vertex_id,
            right_vertex_id,
            connector.evidence,
            connector.event_id,
        )
        prior = seams.get(seam.arc_id)
        if prior is not None and prior != seam:
            raise UnsupportedMaterialization(
                f"seam conflict {seam.arc_id}: connector lowering differs"
            )
        seams[seam.arc_id] = seam

    mutable_vertices = {
        vertex.vid: Vertex(
            vid=vertex.vid,
            name=vertex.name,
            kind=vertex.kind,
            incident_edges=[],
        )
        for vertex in vertices.values()
    }
    mutable_edges = {
        edge.eid: Hyperedge(
            eid=edge.eid,
            value=edge.value,
            members=list(edge.members),
            clusters=list(edge.clusters),
        )
        for edge in edges.values()
    }
    for edge in mutable_edges.values():
        for vertex_id in edge.members:
            mutable_vertices[vertex_id].incident_edges.append(edge.eid)
    for vertex in mutable_vertices.values():
        vertex.incident_edges.sort()
    flat = Field(
        hg=Hypergraph(vertices=mutable_vertices, edges=mutable_edges),
        provenance={edge_id: provenance[edge_id] for edge_id in sorted(provenance)},
        ledger=frozenset(ledger),
        seam=tuple(seams[seam_id] for seam_id in sorted(seams)),
    )
    return MaterializedField(
        field=flat,
        weights=tuple(weights[edge_id] for edge_id in sorted(weights)),
        source_manifest_digest=hswm.semantic_digest(),
        shared_edge_ids=tuple(sorted(shared_edge_ids)),
    )


def materialize(
    hswm: OpenHSWM,
    *,
    shared_edge_ids: Iterable[str] = (),
) -> MaterializedField:
    shared = set(shared_edge_ids)
    for edge_id in shared:
        _require_text(edge_id, "shared edge id")
    return _materialize_snapshots(hswm, shared_edge_ids=shared)


__all__ = [
    "Connector",
    "ConnectorEndpoint",
    "FrozenEdge",
    "FrozenFieldSnapshot",
    "FrozenVertex",
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
    "qualified_interface_id",
]
