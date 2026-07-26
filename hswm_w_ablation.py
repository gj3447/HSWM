"""Deterministic scalar-W interventions for the HSWM causal shadow experiment.

The implemented runtime currently stores durable scalar slow weights.  This
module therefore makes no claim about the proposed operator-valued semantic
synapse.  It constructs content-addressed FULL, REMOVED, SHUFFLED, and RESTORED
states while keeping topology fixed and preserving the learned delta multiset
inside preregistered strata.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from hswm_weight_snapshot import (
    SlowWeightV1,
    WeightSnapshotV1,
    canonical_sha256,
)


class WAblationError(ValueError):
    """A requested intervention violates the frozen W-ablation contract."""


@dataclass(frozen=True)
class WAblationBundleV1:
    """The four causal states, with RESTORED bit-identical to FULL."""

    base: WeightSnapshotV1
    full: WeightSnapshotV1
    removed: WeightSnapshotV1
    shuffled: WeightSnapshotV1
    restored: WeightSnapshotV1
    strata_by_edge: tuple[tuple[str, str], ...]
    seed: int

    def canonical(self) -> dict[str, object]:
        return {
            "schema_version": "hswm-w-ablation-bundle/v1",
            "scope": "scalar_slow_efficacy_v1",
            "base_snapshot_sha256": self.base.snapshot_id,
            "full_snapshot_sha256": self.full.snapshot_id,
            "removed_snapshot_sha256": self.removed.snapshot_id,
            "shuffled_snapshot_sha256": self.shuffled.snapshot_id,
            "restored_snapshot_sha256": self.restored.snapshot_id,
            "strata_by_edge": [
                {"edge_id": edge_id, "stratum": stratum}
                for edge_id, stratum in self.strata_by_edge
            ],
            "seed": self.seed,
        }


def _validate_pair(base: WeightSnapshotV1, full: WeightSnapshotV1) -> None:
    if base.topology_sha256 != full.topology_sha256:
        raise WAblationError("base and full snapshots must share one topology")
    if set(base.weight_map()) != set(full.weight_map()):
        raise WAblationError("base and full snapshots must cover identical edge ids")
    if base.snapshot_id == full.snapshot_id:
        raise WAblationError("full snapshot must contain at least one learned change")


def _normalized_strata(
    edge_ids: Sequence[str], strata_by_edge: Mapping[str, str]
) -> tuple[tuple[str, str], ...]:
    if set(edge_ids) != set(strata_by_edge):
        missing = sorted(set(edge_ids) - set(strata_by_edge))
        extra = sorted(set(strata_by_edge) - set(edge_ids))
        raise WAblationError(f"strata must exactly cover edges; missing={missing} extra={extra}")
    normalized: list[tuple[str, str]] = []
    for edge_id in sorted(edge_ids):
        stratum = strata_by_edge[edge_id]
        if not isinstance(stratum, str) or not stratum:
            raise WAblationError(f"empty stratum for edge {edge_id}")
        normalized.append((edge_id, stratum))
    return tuple(normalized)


def _intervention_snapshot(
    *,
    base: WeightSnapshotV1,
    full: WeightSnapshotV1,
    weights: Mapping[str, float],
    intervention: str,
    seed: int,
) -> WeightSnapshotV1:
    normalized_weights = tuple(
        SlowWeightV1(edge_id=edge_id, log_salience=weights[edge_id])
        for edge_id in sorted(weights)
    )
    provenance = canonical_sha256(
        {
            "schema_version": "hswm-w-intervention-provenance/v1",
            "scope": "scalar_slow_efficacy_v1",
            "intervention": intervention,
            "base_snapshot_sha256": base.snapshot_id,
            "full_snapshot_sha256": full.snapshot_id,
            "seed": seed,
        }
    )
    unsigned = {
        "schema_version": full.schema_version,
        "epoch": full.epoch,
        "parent_snapshot_id": base.snapshot_id,
        "topology_sha256": base.topology_sha256,
        "weights": [weight.canonical() for weight in normalized_weights],
        "provenance_root_sha256": provenance,
    }
    return WeightSnapshotV1(
        snapshot_id=canonical_sha256(unsigned),
        epoch=full.epoch,
        parent_snapshot_id=base.snapshot_id,
        topology_sha256=base.topology_sha256,
        weights=normalized_weights,
        provenance_root_sha256=provenance,
    )


def _deranged_deltas(
    base: WeightSnapshotV1,
    full: WeightSnapshotV1,
    strata: tuple[tuple[str, str], ...],
    *,
    seed: int,
) -> dict[str, float]:
    base_map = base.weight_map()
    full_map = full.weight_map()
    deltas = {edge_id: full_map[edge_id] - base_map[edge_id] for edge_id in base_map}
    changed = {edge_id for edge_id, delta in deltas.items() if delta != 0.0}
    if not changed:
        raise WAblationError("full snapshot has no non-zero learned deltas")

    edges_by_stratum: dict[str, list[str]] = {}
    for edge_id, stratum in strata:
        if edge_id in changed:
            edges_by_stratum.setdefault(stratum, []).append(edge_id)

    assignment: dict[str, float] = {edge_id: 0.0 for edge_id in base_map}
    for stratum, edge_ids in sorted(edges_by_stratum.items()):
        edge_ids.sort()
        if len(edge_ids) < 2:
            raise WAblationError(
                f"changed stratum {stratum!r} needs at least two edges for derangement"
            )
        values = [deltas[edge_id] for edge_id in edge_ids]
        if len(set(values)) < 2:
            raise WAblationError(
                f"changed stratum {stratum!r} has no distinguishable delta assignment"
            )

        candidate_offsets = list(range(1, len(edge_ids)))
        start = seed % len(candidate_offsets)
        candidate_offsets = candidate_offsets[start:] + candidate_offsets[:start]
        selected: dict[str, float] | None = None
        for offset in candidate_offsets:
            proposed = {
                edge_id: values[(index + offset) % len(values)]
                for index, edge_id in enumerate(edge_ids)
            }
            if any(proposed[edge_id] == deltas[edge_id] for edge_id in edge_ids):
                continue
            if any(base_map[edge_id] + proposed[edge_id] > 0.0 for edge_id in edge_ids):
                continue
            selected = proposed
            break
        if selected is None:
            raise WAblationError(
                f"stratum {stratum!r} has no valid max-zero delta derangement"
            )
        assignment.update(selected)
    return assignment


def build_w_ablation_bundle(
    base: WeightSnapshotV1,
    full: WeightSnapshotV1,
    *,
    strata_by_edge: Mapping[str, str],
    seed: int,
) -> WAblationBundleV1:
    """Build and verify the four frozen scalar-W intervention states.

    REMOVED is the exact base snapshot, never an all-zero synthetic field.
    RESTORED is the exact FULL object, never a relearned approximation.
    """

    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise WAblationError("seed must be a non-negative integer")
    _validate_pair(base, full)
    strata = _normalized_strata(tuple(base.weight_map()), strata_by_edge)
    shuffled_deltas = _deranged_deltas(base, full, strata, seed=seed)
    base_map = base.weight_map()
    shuffled_values = {
        edge_id: base_map[edge_id] + shuffled_deltas[edge_id]
        for edge_id in base_map
    }
    shuffled = _intervention_snapshot(
        base=base,
        full=full,
        weights=shuffled_values,
        intervention="W_SHUFFLED_WITHIN_STRATUM",
        seed=seed,
    )
    bundle = WAblationBundleV1(
        base=base,
        full=full,
        removed=base,
        shuffled=shuffled,
        restored=full,
        strata_by_edge=strata,
        seed=seed,
    )
    verify_w_ablation_bundle(bundle)
    return bundle


def verify_w_ablation_bundle(bundle: WAblationBundleV1) -> None:
    _validate_pair(bundle.base, bundle.full)
    if bundle.removed.snapshot_id != bundle.base.snapshot_id:
        raise WAblationError("W_REMOVED must be the exact base snapshot")
    if bundle.restored.snapshot_id != bundle.full.snapshot_id:
        raise WAblationError("W_RESTORED must be bit-identical to W_FULL")
    snapshots = (bundle.base, bundle.full, bundle.shuffled)
    if len({snapshot.topology_sha256 for snapshot in snapshots}) != 1:
        raise WAblationError("W intervention changed topology")
    if bundle.shuffled.snapshot_id in {bundle.base.snapshot_id, bundle.full.snapshot_id}:
        raise WAblationError("W_SHUFFLED must differ from base and full snapshots")

    base_map = bundle.base.weight_map()
    full_map = bundle.full.weight_map()
    shuffled_map = bundle.shuffled.weight_map()
    if set(base_map) != set(full_map) or set(base_map) != set(shuffled_map):
        raise WAblationError("W intervention changed edge support")
    strata = dict(bundle.strata_by_edge)
    for stratum in sorted(set(strata.values())):
        edges = [edge_id for edge_id in sorted(base_map) if strata[edge_id] == stratum]
        full_deltas = sorted(full_map[edge_id] - base_map[edge_id] for edge_id in edges)
        shuffled_deltas = sorted(
            shuffled_map[edge_id] - base_map[edge_id] for edge_id in edges
        )
        if full_deltas != shuffled_deltas:
            raise WAblationError(f"shuffle changed delta multiset in stratum {stratum!r}")


__all__ = [
    "WAblationBundleV1",
    "WAblationError",
    "build_w_ablation_bundle",
    "verify_w_ablation_bundle",
]
