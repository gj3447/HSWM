"""Constructive NumPy representation witness for the SWM-0 worlds.

The module deliberately implements only ``SWM-0R`` representation conformance.
Its order-invariant encoders know the fixture's F_3 construction, including the
fixed ``(c-a-b) mod 3`` and role-A witness channels.  Only the final balanced
ridge readout is fitted.  Consequently this is *not* a learned Theta/R/W
operator and cannot satisfy the separate ``SWM-0W`` learning gate.  It is also
not recurrent HSWM, learned topology, outcome-bound plasticity, or an LLM
function-cell loop.

Opaque node identifiers are used only to join incidences to nodes.  They never
enter the semantic features of the target or its typed-star parity arm.  The
``ID_ORDER_PROBE`` is the sole intentional identifier probe; even there, only an
order-invariant multiset of node-UID hash buckets is exposed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from hswm.experiments.swm0_worlds import (
    FIELD_ORDER,
    GROUPING_RELATION,
    ROLE_RELATION,
    WorldBlockV1,
    WorldCaseV1,
    WorldV1,
    ablate_grouping,
    ablate_roles,
    pairwise_projection,
    role_stripped_projection,
)


OPERATOR_VERSION = "hswm-swm0-operator/v1"
RIDGE_VERSION = "hswm-swm0-balanced-ridge/v1"
MECHANISM_KIND = "CONSTRUCTIVE_REPRESENTATION_WITNESS"
MILESTONE_STATUS = "SWM-0R_REPRESENTATION_CONFORMANCE_ONLY"
LEARNED_OPERATOR_STATUS = "SWM-0W_UNIMPLEMENTED_UNJUDGED"
_PROBE_BUCKETS = 16


class SWM0OperatorError(ValueError):
    """Raised when an operator input or model state violates the contract."""


class SWM0Arm(str, Enum):
    """Preregistered information arms for the SWM-0 witness."""

    ROLE_NARY_ONE_SWEEP = "ROLE_NARY_ONE_SWEEP"
    TYPED_STAR_EQUIV = "TYPED_STAR_EQUIV"
    SCALAR_HYPEREDGE = "SCALAR_HYPEREDGE"
    TYPED_CLIQUE_2SECTION = "TYPED_CLIQUE_2SECTION"
    PAIRWISE_RELATION_SUM = "PAIRWISE_RELATION_SUM"
    COSINE_OR_FLAT = "COSINE_OR_FLAT"
    ROLE_SHUFFLE = "ROLE_SHUFFLE"
    GROUPING_SHUFFLE = "GROUPING_SHUFFLE"
    ID_ORDER_PROBE = "ID_ORDER_PROBE"


ROLE_NARY_ONE_SWEEP = SWM0Arm.ROLE_NARY_ONE_SWEEP.value
TYPED_STAR_EQUIV = SWM0Arm.TYPED_STAR_EQUIV.value
SCALAR_HYPEREDGE = SWM0Arm.SCALAR_HYPEREDGE.value
TYPED_CLIQUE_2SECTION = SWM0Arm.TYPED_CLIQUE_2SECTION.value
PAIRWISE_RELATION_SUM = SWM0Arm.PAIRWISE_RELATION_SUM.value
COSINE_OR_FLAT = SWM0Arm.COSINE_OR_FLAT.value
ROLE_SHUFFLE = SWM0Arm.ROLE_SHUFFLE.value
GROUPING_SHUFFLE = SWM0Arm.GROUPING_SHUFFLE.value
ID_ORDER_PROBE = SWM0Arm.ID_ORDER_PROBE.value
ALL_ARMS: tuple[SWM0Arm, ...] = tuple(SWM0Arm)

# The enum names are preregistration compatibility identifiers.  These
# descriptions are the narrower mechanisms actually implemented here.
ENCODER_PATHS: Mapping[SWM0Arm, str] = {
    SWM0Arm.ROLE_NARY_ONE_SWEEP: "native-typed-hyperedge-constructive/v1",
    SWM0Arm.TYPED_STAR_EQUIV: "independent-typed-incidence-star-compiler/v1",
    SWM0Arm.SCALAR_HYPEREDGE: "role-stripped-exact-grouping/v1",
    SWM0Arm.TYPED_CLIQUE_2SECTION: "typed-2section-role-summary/v1",
    SWM0Arm.PAIRWISE_RELATION_SUM: "typed-2section-role-summary-duplicate/v1",
    SWM0Arm.COSINE_OR_FLAT: "flat-node-multiset-null-no-cosine/v1",
    SWM0Arm.ROLE_SHUFFLE: "deterministic-role-projection-ablation/v1",
    SWM0Arm.GROUPING_SHUFFLE: "deterministic-grouping-projection-ablation/v1",
    SWM0Arm.ID_ORDER_PROBE: "order-invariant-node-uid-bucket-probe/v1",
}
STAR_COMPILER_INDEPENDENT = True
DUPLICATE_INFORMATION_CONTROLS: tuple[tuple[SWM0Arm, ...], ...] = (
    (
        SWM0Arm.TYPED_CLIQUE_2SECTION,
        SWM0Arm.PAIRWISE_RELATION_SUM,
    ),
)
ARM_BOUNDARIES: Mapping[SWM0Arm, str] = {
    SWM0Arm.ROLE_NARY_ONE_SWEEP: (
        "constructive native typed-hyperedge F_3 decoder; not learned Theta/R/W"
    ),
    SWM0Arm.TYPED_STAR_EQUIV: (
        "independent lossless incidence-star compilation and traversal"
    ),
    SWM0Arm.SCALAR_HYPEREDGE: "exact grouping with incidence roles erased",
    SWM0Arm.TYPED_CLIQUE_2SECTION: "typed 2-section summary; grouping erased",
    SWM0Arm.PAIRWISE_RELATION_SUM: (
        "same pairwise information as typed clique; duplicate control"
    ),
    SWM0Arm.COSINE_OR_FLAT: (
        "flat node-multiset null only; enum name retained but no cosine is computed"
    ),
    SWM0Arm.ROLE_SHUFFLE: (
        "deterministic role-projection ablation, not a sampled shuffle"
    ),
    SWM0Arm.GROUPING_SHUFFLE: (
        "deterministic pairwise grouping ablation, not a sampled shuffle"
    ),
    SWM0Arm.ID_ORDER_PROBE: (
        "order-invariant node-UID bucket probe; edge UIDs are not observed"
    ),
}


def _joint_key(grouping_shift: int, role_anchor: int) -> str:
    return f"joint:grouping={grouping_shift}:role={role_anchor}"


def _scalar_key(grouping_shift: int) -> str:
    return f"scalar:grouping={grouping_shift}"


def _clique_key(role_anchor: int) -> str:
    return f"clique:role={role_anchor}"


def _pairwise_sum_key(role_anchor: int) -> str:
    return f"pairwise-sum:role={role_anchor}"


def _role_shuffle_key(grouping_shift: int) -> str:
    return f"role-shuffle:grouping={grouping_shift}"


def _grouping_shuffle_key(role_anchor: int) -> str:
    return f"grouping-shuffle:role={role_anchor}"


def _flat_key(node_sort: str, value: int | None) -> str:
    value_text = "none" if value is None else str(value)
    return f"flat:sort={node_sort}:value={value_text}"


def _probe_key(bucket: int) -> str:
    return f"probe:node-uid-bucket={bucket}"


def _make_common_vocabulary() -> tuple[str, ...]:
    keys: list[str] = []
    keys.extend(
        _joint_key(grouping_shift, role_anchor)
        for grouping_shift in range(FIELD_ORDER)
        for role_anchor in range(FIELD_ORDER)
    )
    keys.extend(_scalar_key(value) for value in range(FIELD_ORDER))
    keys.extend(_clique_key(value) for value in range(FIELD_ORDER))
    keys.extend(_pairwise_sum_key(value) for value in range(FIELD_ORDER))
    keys.extend(_role_shuffle_key(value) for value in range(FIELD_ORDER))
    keys.extend(_grouping_shuffle_key(value) for value in range(FIELD_ORDER))
    keys.extend(
        _flat_key(node_sort, value)
        for node_sort in ("X", "Y", "Z", "U")
        for value in range(FIELD_ORDER)
    )
    keys.append(_flat_key("D", None))
    keys.extend(_probe_key(bucket) for bucket in range(_PROBE_BUCKETS))
    if len(keys) != len(set(keys)):
        raise AssertionError("the SWM-0 common vocabulary contains duplicates")
    return tuple(keys)


COMMON_FEATURE_VOCABULARY = _make_common_vocabulary()
_COMMON_FEATURE_INDEX = {
    feature: index for index, feature in enumerate(COMMON_FEATURE_VOCABULARY)
}

_ARM_FEATURE_KEYS: Mapping[SWM0Arm, frozenset[str]] = {
    SWM0Arm.ROLE_NARY_ONE_SWEEP: frozenset(
        _joint_key(grouping, role)
        for grouping in range(FIELD_ORDER)
        for role in range(FIELD_ORDER)
    ),
    SWM0Arm.TYPED_STAR_EQUIV: frozenset(
        _joint_key(grouping, role)
        for grouping in range(FIELD_ORDER)
        for role in range(FIELD_ORDER)
    ),
    SWM0Arm.SCALAR_HYPEREDGE: frozenset(
        _scalar_key(value) for value in range(FIELD_ORDER)
    ),
    SWM0Arm.TYPED_CLIQUE_2SECTION: frozenset(
        _clique_key(value) for value in range(FIELD_ORDER)
    ),
    SWM0Arm.PAIRWISE_RELATION_SUM: frozenset(
        _pairwise_sum_key(value) for value in range(FIELD_ORDER)
    ),
    SWM0Arm.COSINE_OR_FLAT: frozenset(
        [
            _flat_key(node_sort, value)
            for node_sort in ("X", "Y", "Z", "U")
            for value in range(FIELD_ORDER)
        ]
        + [_flat_key("D", None)]
    ),
    SWM0Arm.ROLE_SHUFFLE: frozenset(
        _role_shuffle_key(value) for value in range(FIELD_ORDER)
    ),
    SWM0Arm.GROUPING_SHUFFLE: frozenset(
        _grouping_shuffle_key(value) for value in range(FIELD_ORDER)
    ),
    SWM0Arm.ID_ORDER_PROBE: frozenset(
        _probe_key(bucket) for bucket in range(_PROBE_BUCKETS)
    ),
}


def _coerce_arm(arm: SWM0Arm | str) -> SWM0Arm:
    if isinstance(arm, SWM0Arm):
        return arm
    try:
        return SWM0Arm(arm)
    except (TypeError, ValueError) as exc:
        raise SWM0OperatorError(f"unsupported SWM-0 arm: {arm!r}") from exc


def effective_feature_count(arm: SWM0Arm | str) -> int:
    """Maximum encoder channels for an arm, not dense readout parameters."""

    return len(_ARM_FEATURE_KEYS[_coerce_arm(arm)])


@dataclass(frozen=True, slots=True)
class EncoderOperationEstimate:
    """Structural work units, explicitly not a FLOP or latency parity claim."""

    node_visits: int = 0
    incidence_visits: int = 0
    pair_terms: int = 0
    feature_products: int = 0
    uid_hashes: int = 0

    def __post_init__(self) -> None:
        if any(
            type(value) is not int or value < 0
            for value in (
                self.node_visits,
                self.incidence_visits,
                self.pair_terms,
                self.feature_products,
                self.uid_hashes,
            )
        ):
            raise SWM0OperatorError("operation estimates require non-negative ints")

    @property
    def total_units(self) -> int:
        return (
            self.node_visits
            + self.incidence_visits
            + self.pair_terms
            + self.feature_products
            + self.uid_hashes
        )


def estimate_encoder_operations(
    world: WorldV1, arm: SWM0Arm | str
) -> EncoderOperationEstimate:
    """Return an auditable structural estimate for one encoder invocation.

    One unit means one visited record, emitted/visited pair term, feature
    product, or UID hash.  It is useful for detecting gross arm asymmetry but is
    not an instruction-level, wall-clock, or FLOP equivalence certificate.
    """

    selected = _coerce_arm(arm)
    node_count = len(world.nodes)
    incidence_count = sum(len(edge.incidences) for edge in world.edges)
    pair_count = sum(
        len(edge.incidences) * (len(edge.incidences) - 1) // 2
        for edge in world.edges
    )
    if selected is SWM0Arm.ROLE_NARY_ONE_SWEEP:
        return EncoderOperationEstimate(
            incidence_visits=incidence_count,
            feature_products=FIELD_ORDER**2,
        )
    if selected is SWM0Arm.TYPED_STAR_EQUIV:
        return EncoderOperationEstimate(
            incidence_visits=2 * incidence_count,
            feature_products=FIELD_ORDER**2,
        )
    if selected in {SWM0Arm.SCALAR_HYPEREDGE, SWM0Arm.ROLE_SHUFFLE}:
        return EncoderOperationEstimate(incidence_visits=2 * incidence_count)
    if selected in {
        SWM0Arm.TYPED_CLIQUE_2SECTION,
        SWM0Arm.PAIRWISE_RELATION_SUM,
        SWM0Arm.GROUPING_SHUFFLE,
    }:
        return EncoderOperationEstimate(
            incidence_visits=incidence_count,
            pair_terms=2 * pair_count,
        )
    if selected is SWM0Arm.COSINE_OR_FLAT:
        return EncoderOperationEstimate(node_visits=node_count)
    if selected is SWM0Arm.ID_ORDER_PROBE:
        return EncoderOperationEstimate(
            node_visits=node_count, uid_hashes=node_count
        )
    raise AssertionError(f"unhandled SWM-0 arm: {selected}")


def _node_projection_map(
    projection: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    nodes = projection.get("nodes")
    if not isinstance(nodes, list):
        raise SWM0OperatorError("projection nodes must be a list")
    result: dict[str, Mapping[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, Mapping) or not isinstance(node.get("uid"), str):
            raise SWM0OperatorError("projection contains an invalid node")
        result[node["uid"]] = node
    return result


def _roleless_grouping_histogram(
    projection: Mapping[str, Any],
) -> np.ndarray:
    """Recover only the grouping latent from an exact role-stripped projection."""

    nodes = _node_projection_map(projection)
    histogram = np.zeros(FIELD_ORDER, dtype=np.float64)
    edges = projection.get("edges")
    if not isinstance(edges, list):
        raise SWM0OperatorError("role-stripped projection edges must be a list")
    for edge in edges:
        if not isinstance(edge, Mapping) or edge.get("relation_type") != GROUPING_RELATION:
            continue
        members = edge.get("members")
        if not isinstance(members, list):
            raise SWM0OperatorError("role-stripped edge members must be a list")
        by_sort: dict[str, Mapping[str, Any]] = {}
        for uid in members:
            node = nodes.get(uid)
            if node is None:
                raise SWM0OperatorError("role-stripped edge refers to an unknown node")
            by_sort[str(node["node_sort"])] = node
        if not {"X", "Y", "Z"}.issubset(by_sort):
            raise SWM0OperatorError("grouping edge is missing an X, Y, or Z member")
        a = by_sort["X"]["value"]
        b = by_sort["Y"]["value"]
        c = by_sort["Z"]["value"]
        if not all(type(value) is int for value in (a, b, c)):
            raise SWM0OperatorError("grouping members require integer F_3 values")
        histogram[(int(c) - int(a) - int(b)) % FIELD_ORDER] += 1.0
    # A complete gadget has q^2 edges.  Dividing by the protocol constant makes
    # a removal visible instead of silently renormalising it away.
    histogram /= float(FIELD_ORDER**2)
    return histogram


def _pairwise_role_histogram(projection: Mapping[str, Any]) -> np.ndarray:
    """Recover only the role latent from a typed pairwise projection."""

    nodes = _node_projection_map(projection)
    histogram = np.zeros(FIELD_ORDER, dtype=np.float64)
    pairs = projection.get("pairs")
    if not isinstance(pairs, list):
        raise SWM0OperatorError("pairwise projection pairs must be a list")
    observations = 0.0
    for pair in pairs:
        if not isinstance(pair, Mapping) or pair.get("relation_type") != ROLE_RELATION:
            continue
        count = pair.get("count")
        if type(count) is not int or count <= 0:
            raise SWM0OperatorError("pair multiplicity must be a positive integer")
        for endpoint_name in ("left", "right"):
            endpoint = pair.get(endpoint_name)
            if not isinstance(endpoint, Mapping) or endpoint.get("role") != "A":
                continue
            uid = endpoint.get("node_uid")
            node = nodes.get(uid)
            if node is None or node.get("node_sort") != "U":
                raise SWM0OperatorError("role A must refer to a U node")
            value = node.get("value")
            if type(value) is not int or not 0 <= value < FIELD_ORDER:
                raise SWM0OperatorError("role A U node must carry an F_3 value")
            histogram[value] += float(count)
            observations += float(count)
    if observations:
        histogram /= observations
    return histogram


def _joint_feature_map(
    grouping: np.ndarray, role: np.ndarray
) -> dict[str, float]:
    """Fixed circular-task witness channels consumed by the ridge readout."""

    features: dict[str, float] = {}
    for grouping_shift in range(FIELD_ORDER):
        for role_anchor in range(FIELD_ORDER):
            value = float(grouping[grouping_shift] * role[role_anchor])
            if value:
                features[_joint_key(grouping_shift, role_anchor)] = value
    return features


def _native_typed_histograms(world: WorldV1) -> tuple[np.ndarray, np.ndarray]:
    """Traverse native typed hyperedges directly, without a projection helper."""

    node_by_uid = {node.uid: node for node in world.nodes}
    grouping = np.zeros(FIELD_ORDER, dtype=np.float64)
    role = np.zeros(FIELD_ORDER, dtype=np.float64)
    for edge in world.edges:
        by_role = {
            incidence.role: node_by_uid[incidence.node_uid]
            for incidence in edge.incidences
        }
        if edge.relation_type == GROUPING_RELATION:
            a = by_role["X"].value
            b = by_role["Y"].value
            c = by_role["Z"].value
            if not all(type(value) is int for value in (a, b, c)):
                raise SWM0OperatorError("native grouping edge lacks F_3 values")
            grouping[(int(c) - int(a) - int(b)) % FIELD_ORDER] += 1.0
        elif edge.relation_type == ROLE_RELATION:
            anchor = by_role["A"].value
            if type(anchor) is not int or not 0 <= anchor < FIELD_ORDER:
                raise SWM0OperatorError("native role-A incidence lacks an F_3 value")
            role[anchor] += 1.0
    grouping /= float(FIELD_ORDER**2)
    return grouping, role


def _native_target_feature_map(world: WorldV1) -> dict[str, float]:
    """Constructive native-hyperedge path for the SWM-0R witness."""

    grouping, role = _native_typed_histograms(world)
    return _joint_feature_map(grouping, role)


@dataclass(frozen=True, slots=True)
class CompiledTypedStarV1:
    """Semantic typed incidence star with no opaque node or edge identifier."""

    relation_type: str
    spokes: tuple[tuple[str, str, int | None], ...]

    def __post_init__(self) -> None:
        if self.relation_type not in {GROUPING_RELATION, ROLE_RELATION}:
            raise SWM0OperatorError("compiled star has an unsupported relation")
        if not isinstance(self.spokes, tuple) or len(self.spokes) != 4:
            raise SWM0OperatorError("compiled star requires four immutable spokes")
        if any(
            not isinstance(spoke, tuple)
            or len(spoke) != 3
            or not isinstance(spoke[0], str)
            or not isinstance(spoke[1], str)
            for spoke in self.spokes
        ):
            raise SWM0OperatorError("compiled star contains an invalid spoke")


def _star_sort_key(star: CompiledTypedStarV1) -> str:
    return json.dumps(
        [star.relation_type, [list(spoke) for spoke in star.spokes]],
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def compile_typed_star(world: WorldV1) -> tuple[CompiledTypedStarV1, ...]:
    """Independently compile native edges into lossless semantic star records.

    The compiler does not call the native target encoder and emits no opaque
    UID.  Multiplicity is preserved by retaining one star record per edge.
    """

    node_by_uid = {node.uid: node for node in world.nodes}
    stars: list[CompiledTypedStarV1] = []
    for edge in world.edges:
        spokes = tuple(
            sorted(
                (
                    (
                        incidence.role,
                        node_by_uid[incidence.node_uid].node_sort,
                        node_by_uid[incidence.node_uid].value,
                    )
                    for incidence in edge.incidences
                ),
                key=lambda spoke: (spoke[0], spoke[1], str(spoke[2])),
            )
        )
        stars.append(CompiledTypedStarV1(edge.relation_type, spokes))
    return tuple(sorted(stars, key=_star_sort_key))


def _traverse_typed_star(
    stars: Sequence[CompiledTypedStarV1],
) -> tuple[np.ndarray, np.ndarray]:
    """Traverse compiled stars; deliberately separate from the native path."""

    grouping = np.zeros(FIELD_ORDER, dtype=np.float64)
    role = np.zeros(FIELD_ORDER, dtype=np.float64)
    for star in stars:
        by_role = {spoke[0]: spoke for spoke in star.spokes}
        if star.relation_type == GROUPING_RELATION:
            a = by_role["X"][2]
            b = by_role["Y"][2]
            c = by_role["Z"][2]
            if not all(type(value) is int for value in (a, b, c)):
                raise SWM0OperatorError("compiled grouping star lacks F_3 values")
            grouping[(int(c) - int(a) - int(b)) % FIELD_ORDER] += 1.0
        elif star.relation_type == ROLE_RELATION:
            anchor = by_role["A"][2]
            if type(anchor) is not int or not 0 <= anchor < FIELD_ORDER:
                raise SWM0OperatorError("compiled role star lacks a role-A value")
            role[anchor] += 1.0
    grouping /= float(FIELD_ORDER**2)
    return grouping, role


def _typed_star_feature_map(world: WorldV1) -> dict[str, float]:
    grouping, role = _traverse_typed_star(compile_typed_star(world))
    return _joint_feature_map(grouping, role)


def _flat_feature_map(world: WorldV1) -> dict[str, float]:
    features: dict[str, float] = {}
    for node in world.nodes:
        key = _flat_key(node.node_sort, node.value)
        features[key] = features.get(key, 0.0) + 1.0
    return features


def _identifier_probe_feature_map(world: WorldV1) -> dict[str, float]:
    """Order-invariant opaque-node-ID probe; edge IDs remain unobserved."""

    features: dict[str, float] = {}
    for node in world.nodes:
        bucket = hashlib.sha256(node.uid.encode("ascii")).digest()[0] % _PROBE_BUCKETS
        key = _probe_key(bucket)
        features[key] = features.get(key, 0.0) + 1.0
    return features


def _histogram_feature_map(
    histogram: np.ndarray, key_function: Any
) -> dict[str, float]:
    return {
        key_function(index): float(value)
        for index, value in enumerate(histogram)
        if value
    }


def semantic_feature_map(
    world: WorldV1, arm: SWM0Arm | str
) -> dict[str, float]:
    """Return a sparse, deterministic feature map for one preregistered arm.

    Target/star features contain only relation type, incidence role, node sort,
    and F_3 value-derived channels.  Opaque UIDs are never emitted as keys or
    values.  The dictionaries are independent of node, edge, and incidence
    serialisation order.
    """

    selected = _coerce_arm(arm)
    if selected is SWM0Arm.ROLE_NARY_ONE_SWEEP:
        features = _native_target_feature_map(world)
    elif selected is SWM0Arm.TYPED_STAR_EQUIV:
        # This independent compiler/traversal must equal the native path because
        # typed incidence-star expansion is lossless.  It is not an alias call.
        features = _typed_star_feature_map(world)
    elif selected is SWM0Arm.SCALAR_HYPEREDGE:
        histogram = _roleless_grouping_histogram(role_stripped_projection(world))
        features = _histogram_feature_map(histogram, _scalar_key)
    elif selected is SWM0Arm.TYPED_CLIQUE_2SECTION:
        histogram = _pairwise_role_histogram(pairwise_projection(world))
        features = _histogram_feature_map(histogram, _clique_key)
    elif selected is SWM0Arm.PAIRWISE_RELATION_SUM:
        histogram = _pairwise_role_histogram(pairwise_projection(world))
        features = _histogram_feature_map(histogram, _pairwise_sum_key)
    elif selected is SWM0Arm.COSINE_OR_FLAT:
        features = _flat_feature_map(world)
    elif selected is SWM0Arm.ROLE_SHUFFLE:
        # Averaging over every incidence-role permutation is exactly the
        # canonical role ablation.  It retains g and erases r.
        histogram = _roleless_grouping_histogram(ablate_roles(world))
        features = _histogram_feature_map(histogram, _role_shuffle_key)
    elif selected is SWM0Arm.GROUPING_SHUFFLE:
        # Averaging over all grouping-preserving pair marginals is represented
        # by the canonical typed 2-section.  It retains r and erases g.
        histogram = _pairwise_role_histogram(ablate_grouping(world))
        features = _histogram_feature_map(histogram, _grouping_shuffle_key)
    elif selected is SWM0Arm.ID_ORDER_PROBE:
        features = _identifier_probe_feature_map(world)
    else:  # pragma: no cover - Enum exhaustiveness guard
        raise AssertionError(f"unhandled SWM-0 arm: {selected}")

    unknown = set(features).difference(_COMMON_FEATURE_INDEX)
    if unknown:
        raise SWM0OperatorError(f"feature map escaped the common vocabulary: {unknown}")
    for key, value in features.items():
        if not isinstance(key, str) or not math.isfinite(value):
            raise SWM0OperatorError("feature maps require finite numeric values")
    return dict(sorted(features.items()))


def encode_world(
    world: WorldV1,
    arm: SWM0Arm | str,
    *,
    vocabulary: Sequence[str] = COMMON_FEATURE_VOCABULARY,
) -> np.ndarray:
    """Encode a world against a deterministic shared feature vocabulary."""

    if len(vocabulary) != len(set(vocabulary)):
        raise SWM0OperatorError("feature vocabulary must not contain duplicates")
    feature_map = semantic_feature_map(world, arm)
    index = (
        _COMMON_FEATURE_INDEX
        if tuple(vocabulary) == COMMON_FEATURE_VOCABULARY
        else {feature: position for position, feature in enumerate(vocabulary)}
    )
    missing = set(feature_map).difference(index)
    if missing:
        raise SWM0OperatorError(f"vocabulary is missing encoded features: {missing}")
    vector = np.zeros(len(vocabulary), dtype=np.float64)
    for feature, value in feature_map.items():
        vector[index[feature]] = value
    vector.setflags(write=False)
    return vector


def cases_from_blocks(blocks: Iterable[WorldBlockV1]) -> tuple[WorldCaseV1, ...]:
    """Flatten split-atomic blocks without changing their within-block order."""

    return tuple(case for block in blocks for case in block.cases)


def _canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class BalancedRidgeReadout:
    """The only fitted component: a balanced ridge over constructive features."""

    arm: SWM0Arm
    vocabulary: tuple[str, ...]
    coefficients: np.ndarray
    ridge: float
    class_counts: tuple[int, int, int]

    def __post_init__(self) -> None:
        selected = _coerce_arm(self.arm)
        object.__setattr__(self, "arm", selected)
        if not isinstance(self.vocabulary, tuple) or len(self.vocabulary) != len(
            set(self.vocabulary)
        ):
            raise SWM0OperatorError("model vocabulary must be a unique tuple")
        coefficients = np.asarray(self.coefficients, dtype=np.float64).copy()
        expected_shape = (len(self.vocabulary) + 1, FIELD_ORDER)
        if coefficients.shape != expected_shape:
            raise SWM0OperatorError(
                f"coefficient shape {coefficients.shape!r} != {expected_shape!r}"
            )
        if not np.isfinite(coefficients).all():
            raise SWM0OperatorError("coefficients must be finite")
        coefficients.setflags(write=False)
        object.__setattr__(self, "coefficients", coefficients)
        if not math.isfinite(self.ridge) or self.ridge <= 0.0:
            raise SWM0OperatorError("ridge must be finite and positive")
        if (
            not isinstance(self.class_counts, tuple)
            or len(self.class_counts) != FIELD_ORDER
            or any(type(count) is not int or count <= 0 for count in self.class_counts)
        ):
            raise SWM0OperatorError("every F_3 class must occur in training")

    @classmethod
    def fit(
        cls,
        cases: Sequence[WorldCaseV1],
        arm: SWM0Arm | str,
        *,
        ridge: float = 1.0e-6,
        vocabulary: Sequence[str] = COMMON_FEATURE_VOCABULARY,
    ) -> "BalancedRidgeReadout":
        """Fit a deterministic inverse-frequency-balanced ridge classifier."""

        selected = _coerce_arm(arm)
        if not cases:
            raise SWM0OperatorError("at least one training case is required")
        if not math.isfinite(ridge) or ridge <= 0.0:
            raise SWM0OperatorError("ridge must be finite and positive")
        vocabulary_tuple = tuple(vocabulary)
        if len(vocabulary_tuple) != len(set(vocabulary_tuple)):
            raise SWM0OperatorError("feature vocabulary must not contain duplicates")

        encoded = np.vstack(
            [
                encode_world(case.world, selected, vocabulary=vocabulary_tuple)
                for case in cases
            ]
        )
        labels = np.asarray([case.target for case in cases], dtype=np.int64)
        counts_array = np.bincount(labels, minlength=FIELD_ORDER)
        if np.any(counts_array == 0):
            raise SWM0OperatorError("training cases must contain every F_3 class")

        sample_weights = np.asarray(
            [len(cases) / (FIELD_ORDER * counts_array[label]) for label in labels],
            dtype=np.float64,
        )
        design = np.column_stack((encoded, np.ones(len(cases), dtype=np.float64)))
        targets = np.eye(FIELD_ORDER, dtype=np.float64)[labels]
        root_weights = np.sqrt(sample_weights)[:, None]
        weighted_design = design * root_weights
        weighted_targets = targets * root_weights

        penalty = np.eye(design.shape[1], dtype=np.float64) * ridge
        penalty[-1, -1] = 0.0  # Do not regularise the intercept.
        gram = weighted_design.T @ weighted_design + penalty
        rhs = weighted_design.T @ weighted_targets
        try:
            coefficients = np.linalg.solve(gram, rhs)
        except np.linalg.LinAlgError:  # Defensive fallback for exotic BLAS builds.
            coefficients = np.linalg.pinv(gram, rcond=1.0e-15) @ rhs
        return cls(
            arm=selected,
            vocabulary=vocabulary_tuple,
            coefficients=coefficients,
            ridge=float(ridge),
            class_counts=tuple(int(value) for value in counts_array),
        )

    @property
    def parameter_count(self) -> int:
        """Nominal dense-readout parameters; this is not compute parity."""

        return int(self.coefficients.size)

    @property
    def effective_feature_count(self) -> int:
        """Maximum channels emitted by this arm's fixed encoder."""

        return effective_feature_count(self.arm)

    @property
    def mechanism_kind(self) -> str:
        return MECHANISM_KIND

    @property
    def milestone_status(self) -> str:
        return MILESTONE_STATUS

    def encoder_operation_estimate(
        self, world: WorldV1
    ) -> EncoderOperationEstimate:
        return estimate_encoder_operations(world, self.arm)

    @property
    def state_sha256(self) -> str:
        """Exact float-state digest for a pinned NumPy/BLAS environment.

        Hexadecimal encoding avoids locale/JSON rounding ambiguity, but a
        different linear-algebra implementation may still change fitted low
        bits and therefore the digest.
        """

        return _canonical_json_sha256(
            {
                "arm": self.arm.value,
                "class_counts": list(self.class_counts),
                "coefficients_hex": [
                    [float(value).hex() for value in row]
                    for row in self.coefficients.tolist()
                ],
                "effective_feature_count": self.effective_feature_count,
                "encoder_path": ENCODER_PATHS[self.arm],
                "learned_operator_status": LEARNED_OPERATOR_STATUS,
                "mechanism_kind": MECHANISM_KIND,
                "milestone_status": MILESTONE_STATUS,
                "ridge_hex": float(self.ridge).hex(),
                "schema_version": RIDGE_VERSION,
                "vocabulary": list(self.vocabulary),
            }
        )

    def logits(self, world: WorldV1) -> np.ndarray:
        vector = encode_world(world, self.arm, vocabulary=self.vocabulary)
        design = np.concatenate((vector, np.ones(1, dtype=np.float64)))
        result = design @ self.coefficients
        result = np.asarray(result, dtype=np.float64)
        result.setflags(write=False)
        return result

    def predict(self, world: WorldV1) -> int:
        return int(np.argmax(self.logits(world)))

    def predict_cases(self, cases: Sequence[WorldCaseV1]) -> np.ndarray:
        predictions = np.asarray(
            [self.predict(case.world) for case in cases], dtype=np.int64
        )
        predictions.setflags(write=False)
        return predictions

    def score(self, cases: Sequence[WorldCaseV1]) -> float:
        if not cases:
            raise SWM0OperatorError("at least one evaluation case is required")
        predictions = self.predict_cases(cases)
        targets = np.asarray([case.target for case in cases], dtype=np.int64)
        return float(np.mean(predictions == targets))


def fit_arm(
    cases: Sequence[WorldCaseV1],
    arm: SWM0Arm | str,
    *,
    ridge: float = 1.0e-6,
    vocabulary: Sequence[str] = COMMON_FEATURE_VOCABULARY,
) -> BalancedRidgeReadout:
    """Convenience wrapper for the public fit API."""

    return BalancedRidgeReadout.fit(
        cases, arm, ridge=ridge, vocabulary=vocabulary
    )


@dataclass(frozen=True, slots=True)
class ArmEvaluation:
    arm: SWM0Arm
    train_accuracy: float
    test_accuracy: float
    parameter_count: int
    effective_feature_count: int
    encoder_operation_units: int
    mechanism_kind: str
    milestone_status: str
    state_sha256: str


def evaluate_arms(
    train_cases: Sequence[WorldCaseV1],
    test_cases: Sequence[WorldCaseV1],
    *,
    arms: Sequence[SWM0Arm | str] = ALL_ARMS,
    ridge: float = 1.0e-6,
) -> tuple[ArmEvaluation, ...]:
    """Fit and score arms; reported structural units are not compute parity."""

    if not train_cases:
        raise SWM0OperatorError("at least one training case is required")
    results: list[ArmEvaluation] = []
    for arm in arms:
        model = fit_arm(train_cases, arm, ridge=ridge)
        results.append(
            ArmEvaluation(
                arm=model.arm,
                train_accuracy=model.score(train_cases),
                test_accuracy=model.score(test_cases),
                parameter_count=model.parameter_count,
                effective_feature_count=model.effective_feature_count,
                encoder_operation_units=model.encoder_operation_estimate(
                    train_cases[0].world
                ).total_units,
                mechanism_kind=model.mechanism_kind,
                milestone_status=model.milestone_status,
                state_sha256=model.state_sha256,
            )
        )
    return tuple(results)


__all__ = [
    "ALL_ARMS",
    "ARM_BOUNDARIES",
    "COMMON_FEATURE_VOCABULARY",
    "COSINE_OR_FLAT",
    "DUPLICATE_INFORMATION_CONTROLS",
    "ENCODER_PATHS",
    "GROUPING_SHUFFLE",
    "ID_ORDER_PROBE",
    "LEARNED_OPERATOR_STATUS",
    "MECHANISM_KIND",
    "MILESTONE_STATUS",
    "OPERATOR_VERSION",
    "PAIRWISE_RELATION_SUM",
    "RIDGE_VERSION",
    "ROLE_NARY_ONE_SWEEP",
    "ROLE_SHUFFLE",
    "SCALAR_HYPEREDGE",
    "STAR_COMPILER_INDEPENDENT",
    "SWM0Arm",
    "SWM0OperatorError",
    "TYPED_CLIQUE_2SECTION",
    "TYPED_STAR_EQUIV",
    "ArmEvaluation",
    "BalancedRidgeReadout",
    "CompiledTypedStarV1",
    "EncoderOperationEstimate",
    "cases_from_blocks",
    "compile_typed_star",
    "encode_world",
    "effective_feature_count",
    "evaluate_arms",
    "estimate_encoder_operations",
    "fit_arm",
    "semantic_feature_map",
]
