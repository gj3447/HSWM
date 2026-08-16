from __future__ import annotations

import hashlib
import json

import pytest

from hswm.experiments.f5v2.operators import (
    F5V2ContractError,
    append_only_sha256,
    build_qfr_extractive_source,
    canonical_source_cut_sha256,
    parse_cpl1_numeric_packet,
    render_append_only,
)
from hswm.experiments.f5v2.topic_cache import (
    B0_ARM_ID,
    BPRIME_ARM_ID,
    TopicCacheIntegrityError,
    build_b0_extractive_cache,
    build_bprime_candidate_cache,
    load_b0_extractive_cache,
    load_bprime_candidate_cache,
    select_bprime_candidate_blocks,
    verify_b0_extractive_cache,
    verify_bprime_candidate_cache,
)


SCHEMA_SHA = "a" * 64


def packet(edge_id: str, delta: float, provenance: str):
    return parse_cpl1_numeric_packet(
        {
            "shared_schema_sha256": SCHEMA_SHA,
            "edge_or_hyperedge_id": edge_id,
            "numeric_delta": delta,
            "confidence": 0.8,
            "provenance_sha256": provenance,
        }
    )


def packets():
    return (
        packet("edge:alpha", 0.25, "1" * 64),
        packet("edge:alpha", -0.05, "2" * 64),
        packet("hyperedge:beta", 0.1, "3" * 64),
    )


def test_cache_build_is_query_agnostic_and_content_addressed(tmp_path) -> None:
    source = packets()
    first_query = build_qfr_extractive_source("alpha question", source)
    second_query = build_qfr_extractive_source("unrelated question", source)

    manifest_a = build_bprime_candidate_cache(tmp_path / "a", source)
    manifest_b = build_bprime_candidate_cache(tmp_path / "b", source)
    loaded = load_bprime_candidate_cache(tmp_path / "a")

    assert first_query.query_sha256 != second_query.query_sha256
    assert manifest_a == manifest_b
    assert manifest_a.manifest_id == loaded.manifest.manifest_id
    assert manifest_a.source_cut_sha256 == canonical_source_cut_sha256(source)
    assert manifest_a.arm_id == BPRIME_ARM_ID
    assert len(loaded.blocks) == 2
    for value in [manifest_a.canonical(), *[b.canonical() for b in loaded.blocks]]:
        encoded = json.dumps(value, sort_keys=True).lower()
        assert '"query' not in encoded
        assert '"prompt' not in encoded


def test_cache_reopens_bit_identically_and_reuses_across_queries(tmp_path) -> None:
    source = packets()
    cache_dir = tmp_path / "cache"
    manifest = build_bprime_candidate_cache(cache_dir, source)
    manifest_bytes = (cache_dir / "manifest.json").read_bytes()

    assert build_bprime_candidate_cache(cache_dir, source) == manifest
    assert (cache_dir / "manifest.json").read_bytes() == manifest_bytes

    alpha = select_bprime_candidate_blocks(
        cache_dir, edge_or_hyperedge_ids=("edge:alpha",)
    )
    beta = select_bprime_candidate_blocks(
        cache_dir, edge_or_hyperedge_ids=("hyperedge:beta",)
    )
    assert [block.topic_key for block in alpha] == ["edge:alpha"]
    assert [block.topic_key for block in beta] == ["hyperedge:beta"]
    assert (cache_dir / "manifest.json").read_bytes() == manifest_bytes


def test_cache_is_canonical_under_reversed_packet_iteration(tmp_path) -> None:
    source = packets()
    forward_dir = tmp_path / "forward"
    reverse_dir = tmp_path / "reverse"

    forward = build_bprime_candidate_cache(forward_dir, source)
    reverse = build_bprime_candidate_cache(reverse_dir, tuple(reversed(source)))

    assert append_only_sha256(source) != append_only_sha256(tuple(reversed(source)))
    assert forward == reverse
    assert (forward_dir / "manifest.json").read_bytes() == (
        reverse_dir / "manifest.json"
    ).read_bytes()
    assert load_bprime_candidate_cache(forward_dir).blocks == load_bprime_candidate_cache(reverse_dir).blocks


def test_b0_is_durable_query_agnostic_and_has_no_derived_state(tmp_path) -> None:
    source = packets()
    first_dir = tmp_path / "b0-first"
    second_dir = tmp_path / "b0-reversed"

    first = build_b0_extractive_cache(first_dir, source)
    second = build_b0_extractive_cache(second_dir, tuple(reversed(source)))
    loaded = load_b0_extractive_cache(first_dir)

    assert first == second
    assert first.arm_id == B0_ARM_ID
    assert (first_dir / "manifest.json").read_bytes() == (
        second_dir / "manifest.json"
    ).read_bytes()
    for value in [first.canonical(), *[block.canonical() for block in loaded.blocks]]:
        encoded = json.dumps(value, sort_keys=True).lower()
        assert '"query' not in encoded
        assert '"slow_w' not in encoded
        assert '"slow_h' not in encoded
        assert '"rule' not in encoded
        assert '"derived' not in encoded


def test_b0_rejects_injected_derived_field_even_after_rewrite(tmp_path) -> None:
    cache_dir = tmp_path / "b0"
    manifest = build_b0_extractive_cache(cache_dir, packets())
    block_path = cache_dir / "blocks" / f"{manifest.block_ids[0]}.json"
    block = json.loads(block_path.read_text(encoding="utf-8"))
    block["slow_w_rule"] = 0.5
    block_path.write_text(
        json.dumps(block, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    with pytest.raises(TopicCacheIntegrityError, match="unexpected fields.*slow_w_rule"):
        verify_b0_extractive_cache(cache_dir)


def test_cache_rejects_query_leakage_in_packet_or_manifest(tmp_path) -> None:
    source = packets()
    cache_dir = tmp_path / "cache"
    build_bprime_candidate_cache(cache_dir, source)

    with pytest.raises(F5V2ContractError, match="unexpected fields.*query"):
        parse_cpl1_numeric_packet({**source[0].canonical(), "query_hash": "f" * 64})

    manifest_path = cache_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["query_sha256"] = "f" * 64
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    with pytest.raises(TopicCacheIntegrityError, match="unexpected fields.*query"):
        verify_bprime_candidate_cache(cache_dir)


def test_cache_rejects_tampered_source_or_block_digest(tmp_path) -> None:
    source = packets()
    cache_dir = tmp_path / "cache"
    manifest = build_bprime_candidate_cache(cache_dir, source)

    with pytest.raises(TopicCacheIntegrityError, match="source cut"):
        verify_bprime_candidate_cache(cache_dir, expected_source_cut_sha256="f" * 64)

    block_path = cache_dir / "blocks" / f"{manifest.block_ids[0]}.json"
    block = json.loads(block_path.read_text(encoding="utf-8"))
    block["slow_w_updates"][0]["numeric_delta"] = 999
    block_path.write_text(
        json.dumps(block, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    with pytest.raises(TopicCacheIntegrityError, match="digest"):
        verify_bprime_candidate_cache(cache_dir)


def test_cache_build_does_not_mutate_raw_append_or_provenance(tmp_path) -> None:
    source = packets()
    raw_path = tmp_path / "raw-append.json"
    raw_path.write_text(render_append_only(source), encoding="utf-8")
    raw_before = raw_path.read_bytes()
    raw_sha_before = hashlib.sha256(raw_before).hexdigest()
    provenance_before = tuple(packet.provenance_sha256 for packet in source)

    build_bprime_candidate_cache(
        tmp_path / "cache",
        source,
        expected_source_cut_sha256=canonical_source_cut_sha256(source),
    )

    assert raw_path.read_bytes() == raw_before
    assert hashlib.sha256(raw_path.read_bytes()).hexdigest() == raw_sha_before
    assert tuple(packet.provenance_sha256 for packet in source) == provenance_before
