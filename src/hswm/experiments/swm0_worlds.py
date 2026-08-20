"""Deterministic counterfactual worlds for the SWM-0 mechanism test.

The construction is intentionally small.  Every block contains the Cartesian
product of two hidden F_3 latents.  ``g`` is encoded only by exact hyperedge
grouping, while ``r`` is encoded only by incidence roles.  The evaluator target
is ``(g + r) % 3``; evaluator metadata never appears in a model-visible world.

This module is a fixture/protocol generator, not a learned model.  Its digest
functions define the information retained by each planned SWM-0 ablation.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Sequence

import numpy as np


FIELD_ORDER = 3
PROTOCOL_VERSION = "hswm-swm0-worlds/v1"
WORLD_SCHEMA = "hswm-swm0-world/v1"
BLOCK_SCHEMA = "hswm-swm0-block/v1"
REMOVAL_SCHEMA = "hswm-swm0-edge-removal/v1"

GROUPING_RELATION = "grouping"
ROLE_RELATION = "role"
GROUPING_ROLES = frozenset(("X", "Y", "Z", "O"))
ROLE_ROLES = frozenset(("A", "B", "C", "O"))
SPLITS = frozenset(("train", "dev", "test"))

_UID_RE = re.compile(r"^(?:n|e|case|block)_[0-9a-f]{24}$")


class SWM0WorldError(ValueError):
    """Raised when an SWM-0 artifact violates its protocol invariants."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    """Return a lowercase SHA-256 over canonical JSON."""

    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _check_uid(uid: str, prefix: str) -> None:
    if not isinstance(uid, str) or not _UID_RE.fullmatch(uid):
        raise SWM0WorldError(f"invalid opaque uid: {uid!r}")
    if not uid.startswith(f"{prefix}_"):
        raise SWM0WorldError(f"uid {uid!r} must use prefix {prefix!r}")


def _check_sha256(value: str, field: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise SWM0WorldError(f"{field} must be a lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class NodeV1:
    """A node with static, label-independent model features."""

    uid: str
    gadget_type: str
    value: int | None
    node_sort: str

    def __post_init__(self) -> None:
        _check_uid(self.uid, "n")
        expected: dict[str, tuple[str, bool]] = {
            "X": ("grouping", True),
            "Y": ("grouping", True),
            "Z": ("grouping", True),
            "U": ("role", True),
            "D": ("decision", False),
        }
        if self.node_sort not in expected:
            raise SWM0WorldError(f"unsupported node sort: {self.node_sort!r}")
        expected_gadget, has_value = expected[self.node_sort]
        if self.gadget_type != expected_gadget:
            raise SWM0WorldError(
                f"{self.node_sort} nodes require gadget_type={expected_gadget!r}"
            )
        if has_value:
            if type(self.value) is not int or not 0 <= self.value < FIELD_ORDER:
                raise SWM0WorldError("valued nodes require an integer in F_3")
        elif self.value is not None:
            raise SWM0WorldError("the decision node has no field value")

    def canonical(self) -> dict[str, Any]:
        return {
            "gadget_type": self.gadget_type,
            "node_sort": self.node_sort,
            "uid": self.uid,
            "value": self.value,
        }


@dataclass(frozen=True, slots=True)
class IncidenceV1:
    """An immutable first-class node--hyperedge incidence."""

    node_uid: str
    role: str

    def __post_init__(self) -> None:
        _check_uid(self.node_uid, "n")
        if not isinstance(self.role, str) or not self.role:
            raise SWM0WorldError("incidence role must be a non-empty string")

    def canonical(self) -> dict[str, str]:
        return {"node_uid": self.node_uid, "role": self.role}


@dataclass(frozen=True, slots=True)
class HyperedgeV1:
    """A typed four-way hyperedge with role-bearing incidences."""

    uid: str
    relation_type: str
    incidences: tuple[IncidenceV1, ...]

    def __post_init__(self) -> None:
        _check_uid(self.uid, "e")
        if not isinstance(self.incidences, tuple):
            raise SWM0WorldError("incidences must be an immutable tuple")
        if len(self.incidences) != 4:
            raise SWM0WorldError("SWM-0 hyperedges have exactly four incidences")
        node_uids = [inc.node_uid for inc in self.incidences]
        if len(set(node_uids)) != len(node_uids):
            raise SWM0WorldError("a hyperedge cannot repeat a node incidence")
        roles = frozenset(inc.role for inc in self.incidences)
        expected_roles = {
            GROUPING_RELATION: GROUPING_ROLES,
            ROLE_RELATION: ROLE_ROLES,
        }.get(self.relation_type)
        if expected_roles is None:
            raise SWM0WorldError(
                f"unsupported relation type: {self.relation_type!r}"
            )
        if roles != expected_roles:
            raise SWM0WorldError(
                f"{self.relation_type} edge requires roles "
                f"{sorted(expected_roles)!r}"
            )

    def canonical(self, *, include_uid: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "incidences": sorted(
                (inc.canonical() for inc in self.incidences),
                key=lambda item: (item["role"], item["node_uid"]),
            ),
            "relation_type": self.relation_type,
        }
        if include_uid:
            result["uid"] = self.uid
        return result


def _edge_sort_key(edge: HyperedgeV1) -> bytes:
    return _canonical_bytes(edge.canonical(include_uid=True))


@dataclass(frozen=True, slots=True)
class WorldV1:
    """A model-visible world; it deliberately contains no evaluator labels."""

    nodes: tuple[NodeV1, ...]
    edges: tuple[HyperedgeV1, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.nodes, tuple) or not isinstance(self.edges, tuple):
            raise SWM0WorldError("nodes and edges must be immutable tuples")
        node_by_uid = {node.uid: node for node in self.nodes}
        if len(node_by_uid) != len(self.nodes):
            raise SWM0WorldError("node uids must be unique")
        edge_uids = [edge.uid for edge in self.edges]
        if len(set(edge_uids)) != len(edge_uids):
            raise SWM0WorldError("edge uids must be unique")

        expected_nodes = Counter(
            [(sort, value) for sort in ("X", "Y", "Z", "U") for value in range(3)]
            + [("D", None)]
        )
        actual_nodes = Counter((node.node_sort, node.value) for node in self.nodes)
        if actual_nodes != expected_nodes:
            raise SWM0WorldError(
                "a world requires X/Y/Z/U nodes for every F_3 value and one D node"
            )

        expected_sort_by_role = {
            GROUPING_RELATION: {"X": "X", "Y": "Y", "Z": "Z", "O": "D"},
            ROLE_RELATION: {"A": "U", "B": "U", "C": "U", "O": "D"},
        }
        for edge in self.edges:
            for incidence in edge.incidences:
                node = node_by_uid.get(incidence.node_uid)
                if node is None:
                    raise SWM0WorldError(
                        f"edge {edge.uid!r} refers to an unknown node"
                    )
                expected_sort = expected_sort_by_role[edge.relation_type][
                    incidence.role
                ]
                if node.node_sort != expected_sort:
                    raise SWM0WorldError(
                        f"role {incidence.role!r} requires node sort "
                        f"{expected_sort!r}"
                    )
        if sum(edge.relation_type == ROLE_RELATION for edge in self.edges) > 1:
            raise SWM0WorldError("a world has at most one role-gadget edge")

    def canonical(self) -> dict[str, Any]:
        """Identity-bearing artifact form, used by remove/restore receipts."""

        return {
            "edges": [
                edge.canonical(include_uid=True)
                for edge in sorted(self.edges, key=_edge_sort_key)
            ],
            "nodes": [
                node.canonical()
                for node in sorted(self.nodes, key=lambda item: item.uid)
            ],
            "schema_version": WORLD_SCHEMA,
        }

    def model_visible(self) -> dict[str, Any]:
        """Canonical full semantic form, excluding incidental edge identifiers."""

        return full_projection(self)

    @property
    def artifact_sha256(self) -> str:
        return canonical_sha256(self.canonical())

    @property
    def full_sha256(self) -> str:
        return full_sha256(self)

    @property
    def pairwise_sha256(self) -> str:
        return pairwise_sha256(self)

    @property
    def role_stripped_sha256(self) -> str:
        return role_stripped_sha256(self)

    @property
    def flat_sha256(self) -> str:
        return flat_sha256(self)


def _canonical_nodes(world: WorldV1) -> list[dict[str, Any]]:
    return [
        node.canonical() for node in sorted(world.nodes, key=lambda item: item.uid)
    ]


def full_projection(world: WorldV1) -> dict[str, Any]:
    """Retain exact hyperedge grouping and every incidence role."""

    edges = [edge.canonical(include_uid=False) for edge in world.edges]
    edges.sort(key=_canonical_bytes)
    return {
        "edges": edges,
        "nodes": _canonical_nodes(world),
        "schema_version": "hswm-swm0-full-projection/v1",
    }


def pairwise_projection(world: WorldV1) -> dict[str, Any]:
    """Typed, role-aware 2-section with multiplicities and no edge identity.

    This projection retains the role latent but provably erases the grouping
    latent in the balanced F_3 construction.
    """

    counts: Counter[tuple[str, str, str, str, str]] = Counter()
    for edge in world.edges:
        incidences = sorted(
            ((inc.role, inc.node_uid) for inc in edge.incidences),
            key=lambda item: (item[0], item[1]),
        )
        for left_index, left in enumerate(incidences):
            for right in incidences[left_index + 1 :]:
                counts[(edge.relation_type, left[0], left[1], right[0], right[1])] += 1
    pairs = [
        {
            "count": count,
            "left": {"node_uid": left_node, "role": left_role},
            "relation_type": relation_type,
            "right": {"node_uid": right_node, "role": right_role},
        }
        for (
            relation_type,
            left_role,
            left_node,
            right_role,
            right_node,
        ), count in sorted(counts.items())
    ]
    return {
        "nodes": _canonical_nodes(world),
        "pairs": pairs,
        "schema_version": "hswm-swm0-pairwise-projection/v1",
    }


def role_stripped_projection(world: WorldV1) -> dict[str, Any]:
    """Retain exact membership/grouping but erase incidence roles."""

    edges = [
        {
            "members": sorted(inc.node_uid for inc in edge.incidences),
            "relation_type": edge.relation_type,
        }
        for edge in world.edges
    ]
    edges.sort(key=_canonical_bytes)
    return {
        "edges": edges,
        "nodes": _canonical_nodes(world),
        "schema_version": "hswm-swm0-role-stripped-projection/v1",
    }


def flat_projection(world: WorldV1) -> dict[str, Any]:
    """Retain only the shared node multiset and its static features."""

    return {
        "nodes": _canonical_nodes(world),
        "schema_version": "hswm-swm0-flat-projection/v1",
    }


def full_sha256(world: WorldV1) -> str:
    return canonical_sha256(full_projection(world))


def pairwise_sha256(world: WorldV1) -> str:
    return canonical_sha256(pairwise_projection(world))


def role_stripped_sha256(world: WorldV1) -> str:
    return canonical_sha256(role_stripped_projection(world))


def flat_sha256(world: WorldV1) -> str:
    return canonical_sha256(flat_projection(world))


def ablate_roles(world: WorldV1) -> dict[str, Any]:
    """The canonical role ablation: exact sets, no incidence roles."""

    return role_stripped_projection(world)


def ablate_grouping(world: WorldV1) -> dict[str, Any]:
    """The canonical grouping ablation: a typed role-aware 2-section."""

    return pairwise_projection(world)


def _nodes_by_sort_and_value(world: WorldV1) -> dict[tuple[str, int | None], NodeV1]:
    return {(node.node_sort, node.value): node for node in world.nodes}


def decode_grouping_latent(world: WorldV1) -> int:
    """Constructively recover ``g`` from exact grouping hyperedges."""

    nodes = {node.uid: node for node in world.nodes}
    grouping_edges = [
        edge for edge in world.edges if edge.relation_type == GROUPING_RELATION
    ]
    if len(grouping_edges) != 9:
        raise SWM0WorldError("a complete grouping gadget requires nine edges")
    observed_pairs: set[tuple[int, int]] = set()
    candidates: set[int] = set()
    for edge in grouping_edges:
        by_role = {inc.role: nodes[inc.node_uid] for inc in edge.incidences}
        a = by_role["X"].value
        b = by_role["Y"].value
        c = by_role["Z"].value
        assert a is not None and b is not None and c is not None
        observed_pairs.add((a, b))
        candidates.add((c - a - b) % FIELD_ORDER)
    if observed_pairs != {
        (a, b) for a in range(FIELD_ORDER) for b in range(FIELD_ORDER)
    } or len(candidates) != 1:
        raise SWM0WorldError("grouping gadget is not a complete F_3 Latin trade")
    return next(iter(candidates))


def decode_role_latent(world: WorldV1) -> int:
    """Constructively recover ``r`` from the cyclic incidence-role gadget."""

    nodes = {node.uid: node for node in world.nodes}
    role_edges = [edge for edge in world.edges if edge.relation_type == ROLE_RELATION]
    if len(role_edges) != 1:
        raise SWM0WorldError("a complete role gadget requires exactly one edge")
    by_role = {inc.role: nodes[inc.node_uid] for inc in role_edges[0].incidences}
    values = tuple(by_role[role].value for role in ("A", "B", "C"))
    if any(value is None for value in values):
        raise SWM0WorldError("role gadget incidences must select U nodes")
    a, b, c = values
    assert a is not None and b is not None and c is not None
    if (b, c) != ((a + 1) % FIELD_ORDER, (a + 2) % FIELD_ORDER):
        raise SWM0WorldError("role gadget is not a cyclic F_3 assignment")
    return a


def constructive_target(world: WorldV1) -> int:
    """Evaluator oracle for the mechanism-defined label."""

    return (decode_grouping_latent(world) + decode_role_latent(world)) % FIELD_ORDER


def rotate_role_gadget(world: WorldV1, *, step: int = 1) -> WorldV1:
    """Counterfactually rotate ``r`` while keeping memberships and ``g`` fixed."""

    if type(step) is not int:
        raise SWM0WorldError("step must be an integer")
    r_new = (decode_role_latent(world) + step) % FIELD_ORDER
    nodes = _nodes_by_sort_and_value(world)
    decision = nodes[("D", None)]
    replaced: list[HyperedgeV1] = []
    for edge in world.edges:
        if edge.relation_type != ROLE_RELATION:
            replaced.append(edge)
            continue
        replaced.append(
            HyperedgeV1(
                uid=edge.uid,
                relation_type=ROLE_RELATION,
                incidences=(
                    IncidenceV1(nodes[("U", r_new)].uid, "A"),
                    IncidenceV1(nodes[("U", (r_new + 1) % 3)].uid, "B"),
                    IncidenceV1(nodes[("U", (r_new + 2) % 3)].uid, "C"),
                    IncidenceV1(decision.uid, "O"),
                ),
            )
        )
    return WorldV1(nodes=world.nodes, edges=tuple(replaced))


def shift_grouping_gadget(world: WorldV1, *, step: int = 1) -> WorldV1:
    """Counterfactually shift ``g`` while keeping pairwise counts and ``r`` fixed."""

    if type(step) is not int:
        raise SWM0WorldError("step must be an integer")
    shift = step % FIELD_ORDER
    nodes = {node.uid: node for node in world.nodes}
    by_sort_value = _nodes_by_sort_and_value(world)
    replaced: list[HyperedgeV1] = []
    for edge in world.edges:
        if edge.relation_type != GROUPING_RELATION:
            replaced.append(edge)
            continue
        incidences: list[IncidenceV1] = []
        for incidence in edge.incidences:
            if incidence.role != "Z":
                incidences.append(incidence)
                continue
            old_z = nodes[incidence.node_uid]
            assert old_z.value is not None
            new_z = by_sort_value[("Z", (old_z.value + shift) % FIELD_ORDER)]
            incidences.append(IncidenceV1(new_z.uid, "Z"))
        replaced.append(
            HyperedgeV1(
                uid=edge.uid,
                relation_type=edge.relation_type,
                incidences=tuple(incidences),
            )
        )
    return WorldV1(nodes=world.nodes, edges=tuple(replaced))


def _validate_complete_world(world: WorldV1) -> None:
    if len(world.edges) != 10:
        raise SWM0WorldError("a complete world has nine grouping and one role edge")
    decode_grouping_latent(world)
    decode_role_latent(world)


@dataclass(frozen=True, slots=True)
class WorldCaseV1:
    """Evaluator-only envelope around one model-visible world."""

    case_uid: str
    g: int
    r: int
    target: int
    world: WorldV1

    def __post_init__(self) -> None:
        _check_uid(self.case_uid, "case")
        for name, value in (("g", self.g), ("r", self.r), ("target", self.target)):
            if type(value) is not int or not 0 <= value < FIELD_ORDER:
                raise SWM0WorldError(f"{name} must be an integer in F_3")
        if self.target != (self.g + self.r) % FIELD_ORDER:
            raise SWM0WorldError("target must equal (g + r) mod 3")
        _validate_complete_world(self.world)
        if decode_grouping_latent(self.world) != self.g:
            raise SWM0WorldError("evaluator g does not match the world")
        if decode_role_latent(self.world) != self.r:
            raise SWM0WorldError("evaluator r does not match the world")

    def canonical(self) -> dict[str, Any]:
        """Evaluator artifact; do not pass this envelope to a model."""

        return {
            "case_uid": self.case_uid,
            "g": self.g,
            "r": self.r,
            "target": self.target,
            "world": self.world.canonical(),
        }

    def model_visible(self) -> dict[str, Any]:
        return self.world.model_visible()


@dataclass(frozen=True, slots=True)
class WorldBlockV1:
    """A split-atomic block containing all nine sibling counterfactuals."""

    block_uid: str
    split: str
    seed_sha256: str
    cases: tuple[WorldCaseV1, ...]
    block_sha256: str

    def __post_init__(self) -> None:
        _check_uid(self.block_uid, "block")
        if self.split not in SPLITS:
            raise SWM0WorldError(f"split must be one of {sorted(SPLITS)!r}")
        _check_sha256(self.seed_sha256, "seed_sha256")
        _check_sha256(self.block_sha256, "block_sha256")
        if not isinstance(self.cases, tuple) or len(self.cases) != 9:
            raise SWM0WorldError("a block must contain exactly nine cases")
        if len({case.case_uid for case in self.cases}) != 9:
            raise SWM0WorldError("case uids must be unique")
        if {(case.g, case.r) for case in self.cases} != {
            (g, r) for g in range(3) for r in range(3)
        }:
            raise SWM0WorldError("a block must contain every (g, r) pair once")
        if Counter(case.target for case in self.cases) != Counter({0: 3, 1: 3, 2: 3}):
            raise SWM0WorldError("each target class must occur three times")
        node_forms = {
            _canonical_bytes(_canonical_nodes(case.world)) for case in self.cases
        }
        if len(node_forms) != 1:
            raise SWM0WorldError("sibling worlds must share one node/feature surface")
        if self.block_sha256 != canonical_sha256(self.unsigned_canonical()):
            raise SWM0WorldError("block_sha256 does not authenticate the block")

    def unsigned_canonical(self) -> dict[str, Any]:
        return {
            "block_uid": self.block_uid,
            "cases": [case.canonical() for case in self.cases],
            "schema_version": BLOCK_SCHEMA,
            "seed_sha256": self.seed_sha256,
            "split": self.split,
        }

    def canonical(self) -> dict[str, Any]:
        result = self.unsigned_canonical()
        result["block_sha256"] = self.block_sha256
        return result


def _opaque_uid(
    seed_preimage: bytes,
    *,
    split: str,
    block_index: int,
    domain: str,
    index: int,
    prefix: str,
) -> str:
    payload = b"\x00".join(
        (
            PROTOCOL_VERSION.encode("utf-8"),
            seed_preimage,
            split.encode("ascii"),
            str(block_index).encode("ascii"),
            domain.encode("ascii"),
            str(index).encode("ascii"),
        )
    )
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:24]}"


def _rng_seed(
    seed_preimage: bytes, *, split: str, block_index: int, domain: str
) -> int:
    payload = b"\x00".join(
        (
            PROTOCOL_VERSION.encode("utf-8"),
            seed_preimage,
            split.encode("ascii"),
            str(block_index).encode("ascii"),
            domain.encode("ascii"),
        )
    )
    return int.from_bytes(hashlib.sha256(payload).digest()[:16], "big")


def _permuted_tuple(values: Sequence[Any], rng: np.random.Generator) -> tuple[Any, ...]:
    order = rng.permutation(len(values))
    return tuple(values[int(index)] for index in order)


def generate_block(
    *, split: str, block_index: int, seed_preimage: bytes
) -> WorldBlockV1:
    """Generate one deterministic, split-atomic q=3 counterfactual block.

    ``seed_preimage`` is deliberately not serialized.  Supply at least 128 bits
    and keep it evaluator-side; all exposed identifiers are domain-separated,
    fixed-width hashes.
    """

    if split not in SPLITS:
        raise SWM0WorldError(f"split must be one of {sorted(SPLITS)!r}")
    if type(block_index) is not int or block_index < 0:
        raise SWM0WorldError("block_index must be a non-negative integer")
    if not isinstance(seed_preimage, bytes) or len(seed_preimage) < 16:
        raise SWM0WorldError("seed_preimage must contain at least 128 bits")

    def uid(domain: str, index: int, prefix: str) -> str:
        return _opaque_uid(
            seed_preimage,
            split=split,
            block_index=block_index,
            domain=domain,
            index=index,
            prefix=prefix,
        )

    nodes_unshuffled = [
        NodeV1(uid(f"node-{sort}", value, "n"), "grouping", value, sort)
        for sort in ("X", "Y", "Z")
        for value in range(3)
    ]
    nodes_unshuffled.extend(
        NodeV1(uid("node-U", value, "n"), "role", value, "U")
        for value in range(3)
    )
    nodes_unshuffled.append(NodeV1(uid("node-D", 0, "n"), "decision", None, "D"))
    node_rng = np.random.Generator(
        np.random.PCG64(
            _rng_seed(
                seed_preimage,
                split=split,
                block_index=block_index,
                domain="node-order",
            )
        )
    )
    nodes = _permuted_tuple(nodes_unshuffled, node_rng)
    by_sort_value = {(node.node_sort, node.value): node for node in nodes}
    decision = by_sort_value[("D", None)]

    latent_pairs = [(g, r) for g in range(3) for r in range(3)]
    case_order_rng = np.random.Generator(
        np.random.PCG64(
            _rng_seed(
                seed_preimage,
                split=split,
                block_index=block_index,
                domain="case-order",
            )
        )
    )
    latent_pairs = list(_permuted_tuple(latent_pairs, case_order_rng))

    cases: list[WorldCaseV1] = []
    for g, r in latent_pairs:
        latent_ordinal = g * FIELD_ORDER + r
        edge_rng = np.random.Generator(
            np.random.PCG64(
                _rng_seed(
                    seed_preimage,
                    split=split,
                    block_index=block_index,
                    domain=f"edge-order-{latent_ordinal}",
                )
            )
        )
        edges: list[HyperedgeV1] = []
        for a in range(3):
            for b in range(3):
                edge_ordinal = a * FIELD_ORDER + b
                incidences = (
                    IncidenceV1(by_sort_value[("X", a)].uid, "X"),
                    IncidenceV1(by_sort_value[("Y", b)].uid, "Y"),
                    IncidenceV1(by_sort_value[("Z", (a + b + g) % 3)].uid, "Z"),
                    IncidenceV1(decision.uid, "O"),
                )
                incidences = _permuted_tuple(incidences, edge_rng)
                edges.append(
                    HyperedgeV1(
                        uid(
                            f"edge-{latent_ordinal}-grouping",
                            edge_ordinal,
                            "e",
                        ),
                        GROUPING_RELATION,
                        incidences,
                    )
                )
        role_incidences = (
            IncidenceV1(by_sort_value[("U", r)].uid, "A"),
            IncidenceV1(by_sort_value[("U", (r + 1) % 3)].uid, "B"),
            IncidenceV1(by_sort_value[("U", (r + 2) % 3)].uid, "C"),
            IncidenceV1(decision.uid, "O"),
        )
        edges.append(
            HyperedgeV1(
                uid(f"edge-{latent_ordinal}-role", 0, "e"),
                ROLE_RELATION,
                _permuted_tuple(role_incidences, edge_rng),
            )
        )
        world = WorldV1(nodes=nodes, edges=_permuted_tuple(edges, edge_rng))
        cases.append(
            WorldCaseV1(
                case_uid=uid("case", latent_ordinal, "case"),
                g=g,
                r=r,
                target=(g + r) % FIELD_ORDER,
                world=world,
            )
        )

    seed_sha256 = hashlib.sha256(seed_preimage).hexdigest()
    block_uid = uid("block", 0, "block")
    unsigned = {
        "block_uid": block_uid,
        "cases": [case.canonical() for case in cases],
        "schema_version": BLOCK_SCHEMA,
        "seed_sha256": seed_sha256,
        "split": split,
    }
    return WorldBlockV1(
        block_uid=block_uid,
        split=split,
        seed_sha256=seed_sha256,
        cases=tuple(cases),
        block_sha256=canonical_sha256(unsigned),
    )


@dataclass(frozen=True, slots=True)
class EdgeRemovalV1:
    """Authenticated receipt for one reversible edge removal."""

    base_artifact_sha256: str
    removed_artifact_sha256: str
    edge: HyperedgeV1
    receipt_sha256: str

    def __post_init__(self) -> None:
        _check_sha256(self.base_artifact_sha256, "base_artifact_sha256")
        _check_sha256(self.removed_artifact_sha256, "removed_artifact_sha256")
        _check_sha256(self.receipt_sha256, "receipt_sha256")
        if self.receipt_sha256 != canonical_sha256(self.unsigned_canonical()):
            raise SWM0WorldError("receipt_sha256 does not authenticate the removal")

    def unsigned_canonical(self) -> dict[str, Any]:
        return {
            "base_artifact_sha256": self.base_artifact_sha256,
            "edge": self.edge.canonical(include_uid=True),
            "removed_artifact_sha256": self.removed_artifact_sha256,
            "schema_version": REMOVAL_SCHEMA,
        }

    def canonical(self) -> dict[str, Any]:
        result = self.unsigned_canonical()
        result["receipt_sha256"] = self.receipt_sha256
        return result


def remove_edge(world: WorldV1, edge_uid: str) -> tuple[WorldV1, EdgeRemovalV1]:
    """Return a new world and an authenticated exact-restore receipt."""

    _check_uid(edge_uid, "e")
    matching = [edge for edge in world.edges if edge.uid == edge_uid]
    if len(matching) != 1:
        raise SWM0WorldError(f"edge {edge_uid!r} is not present exactly once")
    removed_world = WorldV1(
        nodes=world.nodes,
        edges=tuple(edge for edge in world.edges if edge.uid != edge_uid),
    )
    unsigned = {
        "base_artifact_sha256": world.artifact_sha256,
        "edge": matching[0].canonical(include_uid=True),
        "removed_artifact_sha256": removed_world.artifact_sha256,
        "schema_version": REMOVAL_SCHEMA,
    }
    receipt = EdgeRemovalV1(
        base_artifact_sha256=world.artifact_sha256,
        removed_artifact_sha256=removed_world.artifact_sha256,
        edge=matching[0],
        receipt_sha256=canonical_sha256(unsigned),
    )
    return removed_world, receipt


def restore_edge(world: WorldV1, receipt: EdgeRemovalV1) -> WorldV1:
    """Restore exactly one removed edge, failing closed on mismatch/tampering."""

    if world.artifact_sha256 != receipt.removed_artifact_sha256:
        raise SWM0WorldError("receipt does not apply to this removed world")
    if any(edge.uid == receipt.edge.uid for edge in world.edges):
        raise SWM0WorldError("the removed edge is already present")
    restored = WorldV1(nodes=world.nodes, edges=world.edges + (receipt.edge,))
    if restored.artifact_sha256 != receipt.base_artifact_sha256:
        raise SWM0WorldError("restoration does not reproduce the authenticated base")
    return restored


__all__ = [
    "BLOCK_SCHEMA",
    "EdgeRemovalV1",
    "FIELD_ORDER",
    "GROUPING_RELATION",
    "HyperedgeV1",
    "IncidenceV1",
    "NodeV1",
    "PROTOCOL_VERSION",
    "REMOVAL_SCHEMA",
    "ROLE_RELATION",
    "SPLITS",
    "SWM0WorldError",
    "WORLD_SCHEMA",
    "WorldBlockV1",
    "WorldCaseV1",
    "WorldV1",
    "ablate_grouping",
    "ablate_roles",
    "canonical_sha256",
    "constructive_target",
    "decode_grouping_latent",
    "decode_role_latent",
    "flat_projection",
    "flat_sha256",
    "full_projection",
    "full_sha256",
    "generate_block",
    "pairwise_projection",
    "pairwise_sha256",
    "remove_edge",
    "restore_edge",
    "role_stripped_projection",
    "role_stripped_sha256",
    "rotate_role_gadget",
    "shift_grouping_gadget",
]
