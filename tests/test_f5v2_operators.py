from __future__ import annotations

import json

import pytest

from f5v2_operators import (
    F5V2ContractError,
    append_only_sha256,
    build_abstractive_qfr,
    build_qfr_extractive_source,
    parse_cpl1_numeric_packet,
    render_append_only,
)


SCHEMA_SHA = "1" * 64
PROVENANCE_A_SHA = "2" * 64
PROVENANCE_B_SHA = "3" * 64


def packet(
    edge_id: str = "edge:policy:alpha",
    *,
    numeric_delta: float = 0.25,
    confidence: float = 0.9,
    provenance_sha256: str = PROVENANCE_A_SHA,
):
    return parse_cpl1_numeric_packet(
        {
            "shared_schema_sha256": SCHEMA_SHA,
            "edge_or_hyperedge_id": edge_id,
            "numeric_delta": numeric_delta,
            "confidence": confidence,
            "provenance_sha256": provenance_sha256,
        }
    )


def test_cpl1_packet_is_numeric_provenance_only_and_fail_closed() -> None:
    accepted = packet()

    assert set(accepted.canonical()) == {
        "shared_schema_sha256",
        "edge_or_hyperedge_id",
        "numeric_delta",
        "confidence",
        "provenance_sha256",
    }
    with pytest.raises(F5V2ContractError, match="unexpected fields.*query"):
        parse_cpl1_numeric_packet({**accepted.canonical(), "query": "leak"})
    with pytest.raises(F5V2ContractError, match="finite"):
        parse_cpl1_numeric_packet(
            {**accepted.canonical(), "numeric_delta": float("nan")}
        )
    with pytest.raises(F5V2ContractError, match="between 0 and 1"):
        parse_cpl1_numeric_packet({**accepted.canonical(), "confidence": 1.1})


def test_r_extracts_only_verbatim_atomic_packets_and_qfr_is_ephemeral() -> None:
    packets = (
        packet(),
        packet(
            "hyperedge:policy:beta",
            numeric_delta=-0.1,
            confidence=0.7,
            provenance_sha256=PROVENANCE_B_SHA,
        ),
    )
    before = append_only_sha256(packets)

    b0 = build_qfr_extractive_source(
        "Which policy applies?",
        packets,
        selected_packet_sha256s=(packets[1].packet_sha256,),
    )
    qfr = build_abstractive_qfr(
        "Which policy applies?",
        b0,
        content="The beta policy has the selected numeric support.",
        cited_packet_sha256s=(packets[1].packet_sha256,),
    )

    assert b0.mode == "R_EXTRACTIVE"
    assert b0.durable is False
    assert [span.packet.canonical() for span in b0.spans] == [
        packets[1].canonical()
    ]
    assert qfr.mode == "QFR"
    assert qfr.durable is False
    assert qfr.query_sha256 == b0.query_sha256
    assert qfr.cited_packet_sha256s == (packets[1].packet_sha256,)
    assert append_only_sha256(packets) == before


def test_qfr_rejects_fabricated_selection_or_citation() -> None:
    packets = (packet(),)

    with pytest.raises(F5V2ContractError, match="unknown packet"):
        build_qfr_extractive_source(
            "q",
            packets,
            selected_packet_sha256s=("f" * 64,),
        )

    b0 = build_qfr_extractive_source("q", packets)
    with pytest.raises(F5V2ContractError, match="not present in B0"):
        build_abstractive_qfr(
            "q",
            b0,
            content="fabricated",
            cited_packet_sha256s=("f" * 64,),
        )
    with pytest.raises(F5V2ContractError, match="query does not match"):
        build_abstractive_qfr(
            "different query",
            b0,
            content="mismatch",
        )


def test_append_only_render_is_stable_and_preserves_provenance() -> None:
    packets = (
        packet(),
        packet(
            "edge:policy:beta",
            provenance_sha256=PROVENANCE_B_SHA,
        ),
    )

    first = render_append_only(packets)
    second = render_append_only(tuple(reversed(tuple(reversed(packets)))))
    decoded = json.loads(first)

    assert first == second
    assert [item["provenance_sha256"] for item in decoded["packets"]] == [
        PROVENANCE_A_SHA,
        PROVENANCE_B_SHA,
    ]
