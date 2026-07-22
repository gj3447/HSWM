#!/usr/bin/env python3
"""v2 counterexample contract for the canonical fixed-depth-free HSWM kernel."""
from __future__ import annotations

import typing

import pytest

import hswm_open_kernel as kernel
from hswm_field_algebra import Field, SeamArc, field_id, merge
from hswm_hypergraph import Hyperedge, Hypergraph, Vertex, build_hypergraph
from hswm_open_kernel import (
    Connector,
    ConnectorEndpoint,
    OpenHSWM,
    Port,
    SemanticWeight,
    SeparationResult,
    UnsupportedMaterialization,
    compose,
    materialize,
    qualified_interface_id,
)


LEX = ["lacan", "zizek", "badiou", "cohen"]


def mk_field(findings, sources, ledger=()):
    hg = build_hypergraph(
        findings,
        extractor=lambda text: {item for item in LEX if item in text.lower()},
    )
    provenance = {edge_id: tuple(sorted(sources[edge_id])) for edge_id in hg.edges}
    return Field(hg, provenance, frozenset(ledger), ())


def manual_field(*, vertices, edges, provenance, ledger=()):
    vertex_map = {
        vid: Vertex(vid=vid, name=name, kind=kind, incident_edges=[])
        for vid, name, kind in vertices
    }
    edge_map = {}
    for eid, value, members in edges:
        edge_map[eid] = Hyperedge(eid=eid, value=value, members=list(members), clusters=[])
        for vid in members:
            vertex_map[vid].incident_edges.append(eid)
    for vertex in vertex_map.values():
        vertex.incident_edges.sort()
    return Field(
        Hypergraph(vertex_map, edge_map),
        {eid: tuple(sorted(srcs)) for eid, srcs in provenance.items()},
        frozenset(ledger),
        (),
    )


@pytest.fixture
def fields():
    a = mk_field(
        [{"rf": "a1", "text": "lacan and cohen", "clusters": ["left"]}],
        {"a1": {"srcA"}},
        ledger={"event:a"},
    )
    b = mk_field(
        [{"rf": "b1", "text": "zizek reads cohen", "clusters": ["right"]}],
        {"b1": {"srcB"}},
        ledger={"event:b"},
    )
    c = mk_field(
        [{"rf": "c1", "text": "badiou event", "clusters": ["third"]}],
        {"c1": {"srcC"}},
    )
    return a, b, c


@pytest.fixture
def open_fields(fields):
    a, b, c = fields
    oa = OpenHSWM.from_field(
        a,
        mount_id="A",
        ports=(Port("entry", "entity:lacan", "person", "source", "out"),),
        weights=(SemanticWeight("a1", -0.2),),
    )
    ob = OpenHSWM.from_field(
        b,
        mount_id="B",
        ports=(Port("entry", "entity:zizek", "person", "target", "in"),),
        weights=(SemanticWeight("b1", -0.3),),
    )
    oc = OpenHSWM.from_field(
        c,
        mount_id="C",
        ports=(Port("entry", "entity:badiou", "person", "bridge", "bi"),),
        weights=(SemanticWeight("c1", -0.4),),
    )
    return oa, ob, oc


def identity_connector(oa, ob, connector_id="identity:A:B"):
    return Connector(
        connector_id=connector_id,
        endpoints=(
            oa.endpoint(qualified_interface_id("A", "entry"), "left"),
            ob.endpoint(qualified_interface_id("B", "entry"), "right"),
        ),
        relation_type="canonical_identity",
        evidence="v2 fixture",
        event_id=f"event:{connector_id}",
    )


def test_same_local_port_name_is_closed_under_composition(open_fields):
    oa, ob, _ = open_fields
    aggregate = compose((oa, ob), connectors=(identity_connector(oa, ob),))
    assert isinstance(aggregate, OpenHSWM)
    assert {port.interface_id for port in aggregate.interfaces} == {
        qualified_interface_id("A", "entry"),
        qualified_interface_id("B", "entry"),
    }


def test_interface_encoding_is_injective_for_delimiter_heavy_ids():
    assert qualified_interface_id("a:b", "c") != qualified_interface_id("a", "b:c")
    assert qualified_interface_id("::", ":") != qualified_interface_id(":", "::")


def test_composite_can_compose_again_and_regroup(open_fields):
    oa, ob, oc = open_fields
    ab = identity_connector(oa, ob)
    bc = Connector(
        "bridge:B:C",
        (
            ob.endpoint(qualified_interface_id("B", "entry"), "source"),
            oc.endpoint(qualified_interface_id("C", "entry"), "target"),
        ),
        "semantic_bridge",
        "v2 fixture bridge",
        "event:bridge:B:C",
    )
    left = compose((compose((oa, ob), connectors=(ab,)), oc), connectors=(bc,))
    right = compose((oa, compose((ob, oc), connectors=(bc,))), connectors=(ab,))
    assert left.semantic_digest() == right.semantic_digest()
    assert len(left.mounts) == 3


def test_raw_open_hswm_constructor_is_sealed():
    with pytest.raises(TypeError, match="factory"):
        OpenHSWM(mounts=(), connectors=(), interfaces=())


def test_raw_separation_receipt_constructor_is_sealed():
    with pytest.raises(TypeError, match="factory"):
        SeparationResult(parts=(), cut_connectors=(), source_interfaces=(), source_digest="x")


def test_non_exposed_public_port_cannot_admit_connector(open_fields):
    oa, ob, _ = open_fields
    hidden_a = compose((oa,), hide=(qualified_interface_id("A", "entry"),))
    hidden_b = compose((ob,), hide=(qualified_interface_id("B", "entry"),))
    connector = Connector(
        "illegal",
        (
            ConnectorEndpoint("A", "entry", "source"),
            ConnectorEndpoint("B", "entry", "target"),
        ),
        "semantic_bridge",
        "negative oracle",
        "event:illegal",
    )
    with pytest.raises(ValueError, match="not exposed"):
        compose((hidden_a, hidden_b), connectors=(connector,))


def test_caller_field_mutation_cannot_change_snapshot(fields):
    a, _, _ = fields
    wrapped = OpenHSWM.from_field(
        a,
        mount_id="snapshot",
        ports=(Port("p", "entity:lacan", "person", "subject"),),
    )
    before_digest = wrapped.semantic_digest()
    before_field_id = field_id(materialize(wrapped).field)
    a.ledger = frozenset({"mutated"})
    a.hg.edges["a1"].value = "mutated payload"
    assert wrapped.semantic_digest() == before_digest
    assert field_id(materialize(wrapped).field) == before_field_id
    assert wrapped.mounts[0].thaw_field().ledger == frozenset({"event:a"})


def test_snapshot_rejects_mutable_nested_seam_payload(fields):
    a, _, _ = fields
    a.seam = (
        SeamArc(
            "mutable-seam",
            "entity:lacan",
            "entity:cohen",
            ["before"],
            "event:mutable-seam",
        ),
    )
    with pytest.raises(ValueError, match="seam evidence"):
        OpenHSWM.from_field(a, mount_id="mutable-seam")


def test_snapshot_rejects_mutable_nested_edge_cluster(fields):
    a, _, _ = fields
    cluster = ["before"]
    a.hg.edges["a1"].clusters = [cluster]
    with pytest.raises(ValueError, match="edge cluster"):
        OpenHSWM.from_field(a, mount_id="mutable-edge-cluster")


def test_snapshot_defensively_copies_valid_seam_records(fields):
    a, _, _ = fields
    source_arc = SeamArc(
        "stable-seam",
        "entity:lacan",
        "entity:cohen",
        "stable evidence",
        "event:stable-seam",
    )
    a.seam = (source_arc,)
    wrapped = OpenHSWM.from_field(a, mount_id="stable-seam")
    frozen_arc = wrapped.mounts[0].snapshot.seams[0]
    assert frozen_arc == source_arc
    assert frozen_arc is not source_arc
    materialized_arc = materialize(wrapped).field.seam[0]
    assert materialized_arc == frozen_arc
    assert materialized_arc is not frozen_arc


def test_public_api_type_hints_resolve_on_python39():
    for api in (OpenHSWM.from_field, OpenHSWM.specialize):
        hints = typing.get_type_hints(api)
        assert hints["return"] is OpenHSWM


def test_operand_order_never_selects_a_live_mutable_alias(fields):
    a, _, _ = fields
    twin = OpenHSWM.from_field(a, mount_id="twin")
    original = OpenHSWM.from_field(a, mount_id="original")
    a.ledger = frozenset({"late mutation"})
    left = compose((twin, original))
    right = compose((original, twin))
    assert left.semantic_digest() == right.semantic_digest()
    assert [mount.field_digest for mount in left.mounts] == [
        mount.field_digest for mount in right.mounts
    ]
    assert [field_id(mount.thaw_field()) for mount in left.mounts] == [
        field_id(mount.thaw_field()) for mount in right.mounts
    ]
    for aggregate in (left, right):
        with pytest.raises(UnsupportedMaterialization, match="mount multiplicity"):
            materialize(aggregate)


def test_separation_uses_structured_receipt_not_synthetic_boundary_ids(fields):
    a, b, _ = fields
    oa = OpenHSWM.from_field(
        a,
        mount_id="m",
        ports=(Port("p", "entity:lacan", "person", "source"),),
    )
    ob = OpenHSWM.from_field(
        b,
        mount_id="y:m",
        ports=(Port("p", "entity:zizek", "person", "target"),),
    )
    connector = Connector(
        "x:y",
        (
            oa.endpoint(qualified_interface_id("m", "p"), "left"),
            ob.endpoint(qualified_interface_id("y:m", "p"), "right"),
        ),
        "semantic_bridge",
        "delimiter counterexample",
        "event:x:y",
    )
    source = compose((oa, ob), connectors=(connector,))
    receipt = source.separate(("x:y",))
    assert len(receipt.parts) == 2
    assert all("__cut__" not in p.interface_id
               for part in receipt.parts for p in part.interfaces)
    assert receipt.recompose().semantic_digest() == source.semantic_digest()


def test_materializer_preserves_isolated_vertices():
    field = manual_field(
        vertices=(("used", "used", "entity"), ("isolated", "kept", "entity")),
        edges=(("e", "payload", ("used",)),),
        provenance={"e": {"source"}},
    )
    wrapped = OpenHSWM.from_field(field, mount_id="isolated-mount")
    flat = materialize(wrapped).field
    assert set(flat.hg.vertices) == {"used", "isolated"}
    assert flat.hg.vertices["isolated"].incident_edges == []


def test_vertex_conflict_is_grouping_and_order_independent():
    left_field = manual_field(
        vertices=(("v", "left-name", "entity"),),
        edges=(),
        provenance={},
    )
    right_field = manual_field(
        vertices=(("v", "right-name", "entity"),),
        edges=(),
        provenance={},
    )
    middle_field = manual_field(
        vertices=(("m", "middle", "entity"),),
        edges=(),
        provenance={},
    )
    left = OpenHSWM.from_field(left_field, mount_id="left")
    middle = OpenHSWM.from_field(middle_field, mount_id="middle")
    right = OpenHSWM.from_field(right_field, mount_id="right")
    grouping_a = compose((compose((left, middle)), right))
    grouping_b = compose((left, compose((middle, right))))
    assert grouping_a.semantic_digest() == grouping_b.semantic_digest()
    for aggregate in (grouping_a, grouping_b, compose((right, middle, left))):
        with pytest.raises(UnsupportedMaterialization, match="vertex conflict"):
            materialize(aggregate)


def test_empty_edge_provenance_is_rejected_at_capture():
    field = manual_field(
        vertices=(("v", "v", "entity"),),
        edges=(("e", "payload", ("v",)),),
        provenance={"e": set()},
    )
    with pytest.raises(ValueError, match="non-empty provenance"):
        OpenHSWM.from_field(field, mount_id="bad-provenance")


def shared_edge_fields(weight_b=-0.1):
    a = manual_field(
        vertices=(("v", "shared", "entity"),),
        edges=(("same", "same payload", ("v",)),),
        provenance={"same": {"srcA"}},
    )
    b = manual_field(
        vertices=(("v", "shared", "entity"),),
        edges=(("same", "same payload", ("v",)),),
        provenance={"same": {"srcB"}},
    )
    oa = OpenHSWM.from_field(
        a, mount_id="shared-A", weights=(SemanticWeight("same", -0.1),)
    )
    ob = OpenHSWM.from_field(
        b, mount_id="shared-B", weights=(SemanticWeight("same", weight_b),)
    )
    return oa, ob


def test_edge_overlap_requires_explicit_shared_capability():
    oa, ob = shared_edge_fields()
    aggregate = compose((oa, ob))
    with pytest.raises(UnsupportedMaterialization, match="shared_edge_ids"):
        materialize(aggregate)
    flat = materialize(aggregate, shared_edge_ids={"same"})
    assert flat.field.provenance["same"] == ("srcA", "srcB")
    assert [(w.edge_id, w.log_salience) for w in flat.weights] == [("same", -0.1)]


def test_declared_shared_edge_requires_equal_weight():
    oa, ob = shared_edge_fields(weight_b=-0.2)
    with pytest.raises(UnsupportedMaterialization, match="weight conflict"):
        materialize(compose((oa, ob)), shared_edge_ids={"same"})


def test_declared_shared_edge_requires_equal_payload():
    oa, _ = shared_edge_fields()
    bad = manual_field(
        vertices=(("v", "shared", "entity"),),
        edges=(("same", "different payload", ("v",)),),
        provenance={"same": {"srcB"}},
    )
    ob = OpenHSWM.from_field(
        bad, mount_id="shared-B", weights=(SemanticWeight("same", -0.1),)
    )
    with pytest.raises(UnsupportedMaterialization, match="edge conflict"):
        materialize(compose((oa, ob)), shared_edge_ids={"same"})


def test_supported_identity_materialization_matches_legacy(fields, open_fields):
    a, b, _ = fields
    oa, ob, _ = open_fields
    connector = identity_connector(oa, ob)
    flat = materialize(compose((oa, ob), connectors=(connector,))).field
    expected = merge(
        a,
        b,
        new_seam=(
            SeamArc(
                "identity:A:B",
                "entity:lacan",
                "entity:zizek",
                "v2 fixture",
                "event:identity:A:B",
            ),
        ),
    )
    assert field_id(flat) == field_id(expected)


def test_identity_materialization_rejects_unadapted_endpoint_roles(open_fields):
    oa, ob, _ = open_fields
    connector = Connector(
        "identity:unsupported-roles",
        (
            oa.endpoint(qualified_interface_id("A", "entry"), "subject"),
            ob.endpoint(qualified_interface_id("B", "entry"), "object"),
        ),
        "canonical_identity",
        "role erasure counterexample",
        "event:identity:unsupported-roles",
    )
    with pytest.raises(UnsupportedMaterialization, match="exactly left and right"):
        materialize(compose((oa, ob), connectors=(connector,)))


def test_identity_materialization_maps_vertices_by_endpoint_role(open_fields):
    oa, ob, _ = open_fields
    forward = identity_connector(oa, ob, "identity:role-sensitive")
    reverse = Connector(
        "identity:role-sensitive",
        (
            oa.endpoint(qualified_interface_id("A", "entry"), "right"),
            ob.endpoint(qualified_interface_id("B", "entry"), "left"),
        ),
        "canonical_identity",
        "v2 fixture",
        "event:identity:role-sensitive",
    )
    forward_hswm = compose((oa, ob), connectors=(forward,))
    reverse_hswm = compose((oa, ob), connectors=(reverse,))
    assert forward_hswm.semantic_digest() != reverse_hswm.semantic_digest()
    forward_field = materialize(forward_hswm).field
    reverse_field = materialize(reverse_hswm).field
    assert field_id(forward_field) != field_id(reverse_field)
    assert (forward_field.seam[0].left_vid, forward_field.seam[0].right_vid) == (
        "entity:lacan",
        "entity:zizek",
    )
    assert (reverse_field.seam[0].left_vid, reverse_field.seam[0].right_vid) == (
        "entity:zizek",
        "entity:lacan",
    )


def test_nary_connector_never_silently_binary_materializes(open_fields):
    oa, ob, oc = open_fields
    connector = Connector(
        "nary",
        (
            oa.endpoint(qualified_interface_id("A", "entry"), "one"),
            ob.endpoint(qualified_interface_id("B", "entry"), "two"),
            oc.endpoint(qualified_interface_id("C", "entry"), "three"),
        ),
        "nary_relation",
        "v2 nary fixture",
        "event:nary",
    )
    aggregate = compose((oa, ob, oc), connectors=(connector,))
    with pytest.raises(UnsupportedMaterialization, match="relation type"):
        materialize(aggregate)


def test_mount_multiplicity_is_preserved_but_legacy_quotient_rejects(fields):
    a, _, _ = fields
    one = OpenHSWM.from_field(a, mount_id="role:one")
    two = OpenHSWM.from_field(a, mount_id="role:two")
    aggregate = compose((one, two))
    assert len(aggregate.mounts) == 2
    with pytest.raises(UnsupportedMaterialization, match="mount multiplicity"):
        materialize(aggregate)


def test_specialization_is_immutable_and_recomposable(open_fields):
    oa, ob, _ = open_fields
    source = compose((oa, ob), connectors=(identity_connector(oa, ob),))
    digest = source.semantic_digest()
    specialized = source.specialize(("A",))
    assert source.semantic_digest() == digest
    assert [mount.mount_id for mount in specialized.mounts] == ["A"]
    assert isinstance(compose((specialized,)), OpenHSWM)


def test_compose_does_not_call_any_materializer(monkeypatch, open_fields):
    oa, ob, _ = open_fields

    def forbidden(*_args, **_kwargs):
        raise AssertionError("compose crossed materialization boundary")

    monkeypatch.setattr(kernel, "materialize", forbidden)
    monkeypatch.setattr(kernel, "_materialize_snapshots", forbidden)
    assert isinstance(compose((oa, ob), connectors=(identity_connector(oa, ob),)), OpenHSWM)


def test_empty_is_identity_but_has_no_legacy_materialization(open_fields):
    oa, _, _ = open_fields
    assert compose((OpenHSWM.empty(), oa)).semantic_digest() == oa.semantic_digest()
    with pytest.raises(UnsupportedMaterialization, match="no empty identity"):
        materialize(OpenHSWM.empty())


def test_identity_materialization_rejects_distinct_ports_on_same_vertex():
    field = manual_field(
        vertices=(("v", "shared vertex", "entity"),),
        edges=(("e", "payload", ("v",)),),
        provenance={"e": {"source"}},
    )
    wrapped = OpenHSWM.from_field(
        field,
        mount_id="M",
        ports=(
            Port("p1", "v", "entity", "first"),
            Port("p2", "v", "entity", "second"),
        ),
    )
    forward = Connector(
        "identity:same-vertex",
        (
            wrapped.endpoint(qualified_interface_id("M", "p1"), "left"),
            wrapped.endpoint(qualified_interface_id("M", "p2"), "right"),
        ),
        "canonical_identity",
        "same-vertex role counterexample",
        "event:identity:same-vertex",
    )
    reverse = Connector(
        "identity:same-vertex",
        (
            wrapped.endpoint(qualified_interface_id("M", "p1"), "right"),
            wrapped.endpoint(qualified_interface_id("M", "p2"), "left"),
        ),
        "canonical_identity",
        "same-vertex role counterexample",
        "event:identity:same-vertex",
    )
    aggregates = tuple(
        compose((wrapped,), connectors=(connector,))
        for connector in (forward, reverse)
    )
    assert aggregates[0].semantic_digest() != aggregates[1].semantic_digest()
    for aggregate in aggregates:
        with pytest.raises(
            UnsupportedMaterialization,
            match="distinct legacy vertices",
        ):
            materialize(aggregate)
