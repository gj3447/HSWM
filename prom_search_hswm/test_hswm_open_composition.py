#!/usr/bin/env python3
"""Executable contract for fixed-depth-free OpenHSWM composition.

Pure engineering properties only.  Passing this suite is not a retrieval-quality
or Lakatos progressive result.
"""
from __future__ import annotations

import json

import pytest

import hswm_open_composition as open_kernel
from hswm_field_algebra import Field, SeamArc, field_id, merge
from hswm_hypergraph import build_hypergraph
from hswm_open_composition import (
    Connector,
    ConnectorEndpoint,
    MaterializedField,
    OpenHSWM,
    Port,
    SemanticWeight,
    UnsupportedMaterialization,
    compose,
    materialize,
)


LEX = ["lacan", "zizek", "badiou", "cohen", "hallward"]


def mk_field(findings, sources, ledger=()):
    hg = build_hypergraph(
        findings,
        extractor=lambda text: {item for item in LEX if item in text.lower()},
    )
    provenance = {edge_id: tuple(sorted(sources[edge_id])) for edge_id in hg.edges}
    return Field(
        hg=hg,
        provenance=provenance,
        ledger=frozenset(ledger),
        seam=(),
    )


@pytest.fixture
def fields():
    a = mk_field(
        [
            {"rf": "a1", "text": "lacan on the real", "clusters": ["psycho"]},
            {"rf": "sh", "text": "cohen forcing shared", "clusters": ["set"]},
        ],
        {"a1": {"srcA"}, "sh": {"srcA", "srcB"}},
        ledger={"ev-a1"},
    )
    b = mk_field(
        [
            {
                "rf": "b1",
                "text": "zizek reads hallward",
                "clusters": ["politics"],
            },
            {"rf": "sh", "text": "cohen forcing shared", "clusters": ["set"]},
        ],
        {"b1": {"srcB"}, "sh": {"srcA", "srcB"}},
        ledger={"ev-b1"},
    )
    c = mk_field(
        [{"rf": "c1", "text": "badiou event axiom", "clusters": ["ontology"]}],
        {"c1": {"srcC"}},
    )
    return a, b, c


@pytest.fixture
def open_fields(fields):
    a, b, c = fields
    oa = OpenHSWM.from_field(
        a,
        mount_id="mount:a",
        ports=(
            Port(
                "port:a:lacan", "entity:lacan", "person", "claimant", "out"
            ),
            Port("port:a:cohen", "entity:cohen", "person", "bridge", "bi"),
        ),
        weights=(SemanticWeight("a1", -0.2), SemanticWeight("sh", -0.1)),
    )
    ob = OpenHSWM.from_field(
        b,
        mount_id="mount:b",
        ports=(
            Port("port:b:zizek", "entity:zizek", "person", "reader", "in"),
            Port("port:b:cohen", "entity:cohen", "person", "bridge", "bi"),
        ),
        weights=(SemanticWeight("b1", -0.3), SemanticWeight("sh", -0.1)),
    )
    oc = OpenHSWM.from_field(
        c,
        mount_id="mount:c",
        ports=(
            Port("port:c:badiou", "entity:badiou", "person", "theorist", "bi"),
        ),
        weights=(SemanticWeight("c1", -0.4),),
    )
    return oa, ob, oc


def connector_ab(oa, ob, *, evidence="fixture identity"):
    return Connector(
        connector_id="connector:ab",
        endpoints=(
            oa.endpoint("port:a:lacan", "left"),
            ob.endpoint("port:b:zizek", "right"),
        ),
        relation_type="canonical_identity",
        evidence=evidence,
        event_id="event:ab",
    )


def connector_bc(ob, oc):
    return Connector(
        connector_id="connector:bc",
        endpoints=(
            ob.endpoint("port:b:cohen", "source"),
            oc.endpoint("port:c:badiou", "target"),
        ),
        relation_type="semantic_bridge",
        evidence="fixture semantic bridge",
        event_id="event:bc",
    )


def test_closure_composite_can_compose_again(open_fields):
    oa, ob, oc = open_fields
    ab = compose((oa, ob), connectors=(connector_ab(oa, ob),))
    abc = compose((ab, oc), connectors=(connector_bc(ob, oc),))
    assert isinstance(ab, OpenHSWM)
    assert isinstance(abc, OpenHSWM)
    assert len(abc.mounts) == 3
    assert len(abc.connectors) == 2


def test_regrouping_normalizes_to_one_digest(open_fields):
    oa, ob, oc = open_fields
    ab = connector_ab(oa, ob)
    bc = connector_bc(ob, oc)
    left = compose((compose((oa, ob), connectors=(ab,)), oc), connectors=(bc,))
    right = compose((oa, compose((ob, oc), connectors=(bc,))), connectors=(ab,))
    assert left.semantic_digest() == right.semantic_digest()


def test_empty_identity(open_fields):
    oa, _, _ = open_fields
    assert compose((OpenHSWM.empty(), oa)).semantic_digest() == oa.semantic_digest()
    assert compose((oa, OpenHSWM.empty())).semantic_digest() == oa.semantic_digest()


def test_canonical_state_has_no_fixed_layer_or_recursive_children(open_fields):
    oa, ob, _ = open_fields
    aggregate = compose((oa, ob), connectors=(connector_ab(oa, ob),))
    canonical = aggregate.canonical()
    encoded = json.dumps(canonical, sort_keys=True)
    assert not any(token in encoded for token in ('"layer"', '"level"', '"depth"'))
    assert "children" not in canonical and "parts" not in canonical
    assert all(set(mount) == {"mount_id", "field_id", "ports", "weights"}
               for mount in canonical["mounts"])


def test_same_field_may_have_two_distinct_mounts(fields, open_fields):
    a, _, _ = fields
    oa, _, _ = open_fields
    second = OpenHSWM.from_field(
        a,
        mount_id="mount:a:second-role",
        ports=(
            Port(
                "port:a2:lacan", "entity:lacan", "person", "critic", "in"
            ),
        ),
        weights=(SemanticWeight("a1", -0.2), SemanticWeight("sh", -0.1)),
    )
    aggregate = compose((oa, second))
    assert len(aggregate.mounts) == 2
    assert aggregate.mounts[0].field_digest == aggregate.mounts[1].field_digest
    with pytest.raises(UnsupportedMaterialization, match="mount multiplicity"):
        materialize(aggregate)


def test_same_mount_same_intent_is_idempotent(open_fields):
    oa, _, _ = open_fields
    assert compose((oa, oa)).semantic_digest() == oa.semantic_digest()


def test_same_mount_different_payload_fails_closed(fields, open_fields):
    _, b, _ = fields
    oa, _, _ = open_fields
    impostor = OpenHSWM.from_field(
        b,
        mount_id="mount:a",
        ports=(
            Port("port:impostor", "entity:zizek", "person", "reader", "bi"),
        ),
    )
    with pytest.raises(ValueError, match="mount conflict"):
        compose((oa, impostor))


def test_connector_must_use_an_operand_export(fields, open_fields):
    _, b, _ = fields
    oa, _, _ = open_fields
    private = OpenHSWM.from_field(
        b,
        mount_id="mount:private",
        ports=(
            Port(
                "port:private:zizek",
                "entity:zizek",
                "person",
                "hidden-reader",
                "in",
                "private",
            ),
        ),
    )
    illegal = Connector(
        connector_id="connector:illegal",
        endpoints=(
            oa.endpoint("port:a:lacan", "source"),
            ConnectorEndpoint(
                "mount:private", "port:private:zizek", "target"
            ),
        ),
        relation_type="semantic_bridge",
        evidence="negative oracle",
        event_id="event:illegal",
    )
    with pytest.raises(ValueError, match="not exposed"):
        compose((oa, private), connectors=(illegal,))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), 0.1])
def test_semantic_weight_domain_rejects_noncanonical_values(value):
    with pytest.raises(ValueError, match="finite and <= 0"):
        SemanticWeight("edge", value)


def test_weights_and_provenance_survive_composition_and_materialization(open_fields):
    oa, ob, _ = open_fields
    aggregate = compose((oa, ob), connectors=(connector_ab(oa, ob),))
    assert {
        (mount.mount_id, weight.edge_id, weight.log_salience)
        for mount in aggregate.mounts
        for weight in mount.weights
    } == {
        ("mount:a", "a1", -0.2),
        ("mount:a", "sh", -0.1),
        ("mount:b", "b1", -0.3),
        ("mount:b", "sh", -0.1),
    }
    materialized = materialize(aggregate)
    assert isinstance(materialized, MaterializedField)
    assert materialized.field.provenance["sh"] == ("srcA", "srcB")
    assert {w.edge_id for w in materialized.weights} == {"a1", "b1", "sh"}


def test_specialization_is_non_mutating_and_still_composable(open_fields):
    oa, ob, oc = open_fields
    aggregate = compose((oa, ob), connectors=(connector_ab(oa, ob),))
    before = aggregate.semantic_digest()
    specialized = aggregate.specialize(
        ("mount:a",), interface_ids=("port:a:cohen",)
    )
    assert aggregate.semantic_digest() == before
    assert isinstance(specialized, OpenHSWM)
    assert [mount.mount_id for mount in specialized.mounts] == ["mount:a"]
    assert [port.interface_id for port in specialized.interfaces] == ["port:a:cohen"]
    assert not specialized.connectors
    assert isinstance(compose((specialized, oc)), OpenHSWM)


def test_separation_recomposition_is_digest_exact(open_fields):
    oa, ob, _ = open_fields
    source = compose((oa, ob), connectors=(connector_ab(oa, ob),))
    result = source.separate(("connector:ab",))
    assert len(result.parts) == 2
    assert [c.connector_id for c in result.cut_connectors] == ["connector:ab"]
    assert result.recompose().semantic_digest() == source.semantic_digest()


def test_nary_connector_is_valid_open_state_but_not_silently_materialized(open_fields):
    oa, ob, oc = open_fields
    ternary = Connector(
        connector_id="connector:abc",
        endpoints=(
            oa.endpoint("port:a:cohen", "premise"),
            ob.endpoint("port:b:cohen", "witness"),
            oc.endpoint("port:c:badiou", "conclusion"),
        ),
        relation_type="nary_argument",
        evidence="three-role fixture",
        event_id="event:abc",
    )
    aggregate = compose((oa, ob, oc), connectors=(ternary,))
    assert len(aggregate.connectors[0].endpoints) == 3
    with pytest.raises(UnsupportedMaterialization, match="relation type"):
        materialize(aggregate)


def test_supported_identity_materialization_matches_legacy_quotient(fields, open_fields):
    a, b, _ = fields
    oa, ob, _ = open_fields
    connector = connector_ab(oa, ob)
    aggregate = compose((oa, ob), connectors=(connector,))
    materialized = materialize(aggregate)
    expected = merge(
        a,
        b,
        new_seam=(
            SeamArc(
                arc_id="connector:ab",
                left_vid="entity:lacan",
                right_vid="entity:zizek",
                evidence="fixture identity",
                event_id="event:ab",
            ),
        ),
    )
    assert field_id(materialized.field) == field_id(expected)


def test_compose_never_materializes(monkeypatch, open_fields):
    oa, ob, _ = open_fields

    def forbidden(*_args, **_kwargs):
        raise AssertionError("compose called legacy materializer")

    monkeypatch.setattr(open_kernel, "merge_all", forbidden)
    result = compose((oa, ob), connectors=(connector_ab(oa, ob),))
    assert isinstance(result, OpenHSWM)
    assert not isinstance(result, Field)


def test_conflicting_connector_intent_fails_closed(open_fields):
    oa, ob, _ = open_fields
    original = connector_ab(oa, ob)
    connected = compose((oa, ob), connectors=(original,))
    conflict = connector_ab(oa, ob, evidence="different evidence")
    with pytest.raises(ValueError, match="connector conflict"):
        compose((connected,), connectors=(conflict,))


def test_mounted_field_drift_is_detected(fields):
    a, _, _ = fields
    wrapped = OpenHSWM.from_field(
        a,
        mount_id="mount:drift",
        ports=(Port("port:drift", "entity:lacan", "person", "subject"),),
    )
    a.ledger = frozenset({"mutated-after-mount"})
    with pytest.raises(UnsupportedMaterialization, match="mounted field drift"):
        materialize(wrapped)


def test_legacy_empty_identity_gap_fails_explicitly():
    with pytest.raises(UnsupportedMaterialization, match="no empty identity"):
        materialize(OpenHSWM.empty())

