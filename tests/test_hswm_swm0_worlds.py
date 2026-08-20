from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import FrozenInstanceError, replace
import json
import re

import pytest

from hswm.experiments.swm0_worlds import (
    GROUPING_RELATION,
    ROLE_RELATION,
    HyperedgeV1,
    IncidenceV1,
    SWM0WorldError,
    WorldCaseV1,
    WorldV1,
    ablate_grouping,
    ablate_roles,
    constructive_target,
    decode_grouping_latent,
    decode_role_latent,
    generate_block,
    pairwise_projection,
    remove_edge,
    restore_edge,
    role_stripped_projection,
    rotate_role_gadget,
    shift_grouping_gadget,
)


SEED = b"swm0-world-tests-v1-secret-seed"


@pytest.fixture(scope="module")
def block():
    return generate_block(split="train", block_index=7, seed_preimage=SEED)


def _case(block, g: int, r: int):
    return next(case for case in block.cases if (case.g, case.r) == (g, r))


def test_block_is_the_complete_balanced_dual_latent_design(block) -> None:
    assert len(block.cases) == 9
    assert {(case.g, case.r) for case in block.cases} == {
        (g, r) for g in range(3) for r in range(3)
    }
    assert Counter(case.target for case in block.cases) == {0: 3, 1: 3, 2: 3}

    for case in block.cases:
        assert case.target == (case.g + case.r) % 3
        assert decode_grouping_latent(case.world) == case.g
        assert decode_role_latent(case.world) == case.r
        assert constructive_target(case.world) == case.target
        assert sum(
            edge.relation_type == GROUPING_RELATION for edge in case.world.edges
        ) == 9
        assert sum(edge.relation_type == ROLE_RELATION for edge in case.world.edges) == 1


def test_grouping_gadget_has_balanced_pairwise_marginals(block) -> None:
    decision_multiplicities: list[int] = []
    for g in range(3):
        world = _case(block, g, 0).world
        nodes = {node.uid: node for node in world.nodes}
        grouping = [
            edge for edge in world.edges if edge.relation_type == GROUPING_RELATION
        ]
        observed_by_pair = {"XY": Counter(), "XZ": Counter(), "YZ": Counter()}
        for edge in grouping:
            by_role = {inc.role: nodes[inc.node_uid] for inc in edge.incidences}
            values = {role: by_role[role].value for role in ("X", "Y", "Z")}
            observed_by_pair["XY"][(values["X"], values["Y"])] += 1
            observed_by_pair["XZ"][(values["X"], values["Z"])] += 1
            observed_by_pair["YZ"][(values["Y"], values["Z"])] += 1
        complete = Counter({(left, right): 1 for left in range(3) for right in range(3)})
        assert all(counts == complete for counts in observed_by_pair.values())
        decision_uid = next(node.uid for node in world.nodes if node.node_sort == "D")
        decision_multiplicities.append(
            sum(
                incidence.node_uid == decision_uid
                for edge in grouping
                for incidence in edge.incidences
            )
        )
    assert decision_multiplicities == [9, 9, 9]


def test_projection_digests_have_exact_information_boundaries(block) -> None:
    assert len({case.world.full_sha256 for case in block.cases}) == 9
    assert len({case.world.flat_sha256 for case in block.cases}) == 1

    for r in range(3):
        assert len(
            {_case(block, g, r).world.pairwise_sha256 for g in range(3)}
        ) == 1
    assert len({case.world.pairwise_sha256 for case in block.cases}) == 3

    for g in range(3):
        assert len(
            {_case(block, g, r).world.role_stripped_sha256 for r in range(3)}
        ) == 1
    assert len({case.world.role_stripped_sha256 for case in block.cases}) == 3

    pairwise_buckets: defaultdict[str, list[int]] = defaultdict(list)
    role_stripped_buckets: defaultdict[str, list[int]] = defaultdict(list)
    flat_buckets: defaultdict[str, list[int]] = defaultdict(list)
    for case in block.cases:
        pairwise_buckets[case.world.pairwise_sha256].append(case.target)
        role_stripped_buckets[case.world.role_stripped_sha256].append(case.target)
        flat_buckets[case.world.flat_sha256].append(case.target)
    assert all(sorted(labels) == [0, 1, 2] for labels in pairwise_buckets.values())
    assert all(
        sorted(labels) == [0, 1, 2] for labels in role_stripped_buckets.values()
    )
    assert [sorted(labels) for labels in flat_buckets.values()] == [
        [0, 0, 0, 1, 1, 1, 2, 2, 2]
    ]


def test_model_visible_payload_excludes_evaluator_metadata_and_edge_ids(block) -> None:
    forbidden_keys = {
        "block_index",
        "block_uid",
        "case_uid",
        "g",
        "r",
        "seed",
        "seed_sha256",
        "split",
        "target",
        "y",
    }

    def walk(value):
        if isinstance(value, dict):
            assert forbidden_keys.isdisjoint(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    for case in block.cases:
        payload = case.model_visible()
        walk(payload)
        assert all("uid" not in edge for edge in payload["edges"])
        encoded = json.dumps(payload, sort_keys=True)
        assert case.case_uid not in encoded
        assert block.block_uid not in encoded


def test_replay_is_deterministic_and_opaque_ids_are_split_disjoint(block) -> None:
    replay = generate_block(split="train", block_index=7, seed_preimage=SEED)
    assert replay == block
    assert replay.canonical() == block.canonical()

    dev = generate_block(split="dev", block_index=7, seed_preimage=SEED)
    test = generate_block(split="test", block_index=7, seed_preimage=SEED)
    blocks = (block, dev, test)

    node_sets = [
        {node.uid for case in item.cases for node in case.world.nodes}
        for item in blocks
    ]
    edge_sets = [
        {edge.uid for case in item.cases for edge in case.world.edges}
        for item in blocks
    ]
    case_sets = [{case.case_uid for case in item.cases} for item in blocks]
    for collection in (node_sets, edge_sets, case_sets):
        assert collection[0].isdisjoint(collection[1])
        assert collection[0].isdisjoint(collection[2])
        assert collection[1].isdisjoint(collection[2])

    exposed_uids = (
        {item.block_uid for item in blocks}
        | set().union(*node_sets)
        | set().union(*edge_sets)
        | set().union(*case_sets)
    )
    assert all(re.fullmatch(r"(?:n|e|case|block)_[0-9a-f]{24}", uid) for uid in exposed_uids)
    assert all(not any(split in uid for split in ("train", "dev", "test")) for uid in exposed_uids)


def test_canonical_projections_ignore_container_and_incidence_order(block) -> None:
    original = block.cases[0].world
    reversed_edges = tuple(
        replace(edge, incidences=tuple(reversed(edge.incidences)))
        for edge in reversed(original.edges)
    )
    reordered = WorldV1(nodes=tuple(reversed(original.nodes)), edges=reversed_edges)
    assert reordered.canonical() == original.canonical()
    assert reordered.full_sha256 == original.full_sha256
    assert reordered.pairwise_sha256 == original.pairwise_sha256
    assert reordered.role_stripped_sha256 == original.role_stripped_sha256
    assert reordered.flat_sha256 == original.flat_sha256


def test_role_and_grouping_ablations_and_counterfactual_interventions(block) -> None:
    for case in block.cases:
        world = case.world
        assert ablate_roles(world) == role_stripped_projection(world)
        assert ablate_grouping(world) == pairwise_projection(world)

        rotated = rotate_role_gadget(world, step=1)
        assert decode_grouping_latent(rotated) == case.g
        assert decode_role_latent(rotated) == (case.r + 1) % 3
        assert constructive_target(rotated) == (case.target + 1) % 3
        assert rotated.role_stripped_sha256 == world.role_stripped_sha256
        assert rotated.pairwise_sha256 != world.pairwise_sha256
        assert rotated.full_sha256 != world.full_sha256

        shifted = shift_grouping_gadget(world, step=1)
        assert decode_grouping_latent(shifted) == (case.g + 1) % 3
        assert decode_role_latent(shifted) == case.r
        assert constructive_target(shifted) == (case.target + 1) % 3
        assert shifted.pairwise_sha256 == world.pairwise_sha256
        assert shifted.role_stripped_sha256 != world.role_stripped_sha256
        assert shifted.full_sha256 != world.full_sha256


@pytest.mark.parametrize("relation_type", [GROUPING_RELATION, ROLE_RELATION])
def test_remove_restore_is_exact_immutable_and_fail_closed(block, relation_type) -> None:
    original = block.cases[0].world
    edge = next(edge for edge in original.edges if edge.relation_type == relation_type)
    removed, receipt = remove_edge(original, edge.uid)
    assert len(original.edges) == 10
    assert len(removed.edges) == 9
    assert removed.artifact_sha256 != original.artifact_sha256
    assert removed.full_sha256 != original.full_sha256

    restored = restore_edge(removed, receipt)
    assert restored.canonical() == original.canonical()
    assert restored.artifact_sha256 == original.artifact_sha256
    assert restored.full_sha256 == original.full_sha256

    with pytest.raises(SWM0WorldError, match="does not apply"):
        restore_edge(original, receipt)
    other_edge = next(candidate for candidate in original.edges if candidate.uid != edge.uid)
    other_removed, _ = remove_edge(original, other_edge.uid)
    with pytest.raises(SWM0WorldError, match="does not apply"):
        restore_edge(other_removed, receipt)
    with pytest.raises(SWM0WorldError, match="not present"):
        remove_edge(original, "e_000000000000000000000000")


def test_artifacts_are_frozen_and_validation_rejects_corruption(block) -> None:
    case = block.cases[0]
    with pytest.raises(FrozenInstanceError):
        case.world.nodes[0].value = 2

    grouping = next(
        edge for edge in case.world.edges if edge.relation_type == GROUPING_RELATION
    )
    with pytest.raises(SWM0WorldError, match="requires roles"):
        HyperedgeV1(
            uid=grouping.uid,
            relation_type=GROUPING_RELATION,
            incidences=(
                IncidenceV1(grouping.incidences[0].node_uid, "X"),
                IncidenceV1(grouping.incidences[1].node_uid, "Y"),
                IncidenceV1(grouping.incidences[2].node_uid, "Z"),
                IncidenceV1(grouping.incidences[3].node_uid, "Z2"),
            ),
        )

    with pytest.raises(SWM0WorldError, match="target must equal"):
        WorldCaseV1(
            case_uid=case.case_uid,
            g=case.g,
            r=case.r,
            target=(case.target + 1) % 3,
            world=case.world,
        )

    unknown = IncidenceV1("n_000000000000000000000000", "X")
    corrupt_edge = replace(
        grouping,
        incidences=tuple(
            unknown if incidence.role == "X" else incidence
            for incidence in grouping.incidences
        ),
    )
    with pytest.raises(SWM0WorldError, match="unknown node"):
        WorldV1(nodes=case.world.nodes, edges=(corrupt_edge,) + case.world.edges[1:])
