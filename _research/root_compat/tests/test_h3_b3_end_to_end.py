"""End-to-end H3/B3 teeth from paragraph evidence to typed readout.

These fixtures deliberately avoid title matches.  The only useful topology is
therefore produced by two evidence-paired, non-title claim joins.  Evaluation
labels are introduced only after compilation, when the test scores the frozen
readout; neither compiler nor typed kernel receives them.
"""
from __future__ import annotations

from dataclasses import replace
import json
import math

import numpy as np

import claim_builder as cb
import typed_composition as tc


PROMPT_SHA256 = "1" * 64
CONFIG_SHA256 = "2" * 64


def _freeze_claim(
    paragraph: cb.ParagraphInputV1,
    *,
    subject: str,
    predicate: str,
    argument: str,
    argument_role: str,
) -> cb.FrozenExtractionV1:
    """Bind one extractor-shaped claim to exact paragraph codepoint spans."""

    def span(exact: str) -> dict[str, object]:
        start = paragraph.text.index(exact)
        return {"start": start, "end": start + len(exact), "exact": exact}

    payload = {
        "schema_version": cb.EXTRACTION_SCHEMA_VERSION,
        "claims": [{
            "subject": span(subject),
            "predicate": span(predicate),
            "arguments": [{"role": argument_role, **span(argument)}],
        }],
    }
    return cb.freeze_extraction(
        paragraph.source_id,
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        producer="frozen-query-blind-fixture",
        model_revision="fixture-model@sha256:0123456789abcdef",
        prompt_sha256=PROMPT_SHA256,
        config_sha256=CONFIG_SHA256,
    )


def _paragraphs_and_extractions() -> tuple[
    tuple[cb.ParagraphInputV1, ...], tuple[cb.FrozenExtractionV1, ...]
]:
    paragraphs = (
        cb.ParagraphInputV1(
            "src:00-work", "Work Record",
            "The Clockwork Suite was composed by Ada Lovelace.",
        ),
        cb.ParagraphInputV1(
            "src:01-person", "Person Record",
            "Ada Lovelace was born in Byron City.",
        ),
        cb.ParagraphInputV1(
            "src:02-city", "City Record",
            "Byron City is located in Northland.",
        ),
        cb.ParagraphInputV1(
            "src:03-noise-a", "Noise Record Alpha",
            "Noise Alpha studies Obscure Token.",
        ),
        cb.ParagraphInputV1(
            "src:04-noise-b", "Noise Record Beta",
            "Obscure Token catalogs Noise Beta.",
        ),
    )
    extractions = (
        _freeze_claim(
            paragraphs[0], subject="The Clockwork Suite",
            predicate="was composed by", argument="Ada Lovelace",
            argument_role="composer",
        ),
        _freeze_claim(
            paragraphs[1], subject="Ada Lovelace", predicate="was born in",
            argument="Byron City", argument_role="birthplace",
        ),
        _freeze_claim(
            paragraphs[2], subject="Byron City", predicate="is located in",
            argument="Northland", argument_role="location",
        ),
        _freeze_claim(
            paragraphs[3], subject="Noise Alpha", predicate="studies",
            argument="Obscure Token", argument_role="research_topic",
        ),
        _freeze_claim(
            paragraphs[4], subject="Obscure Token", predicate="catalogs",
            argument="Noise Beta", argument_role="archive_topic",
        ),
    )
    return paragraphs, extractions


def _compiled_chain() -> tuple[
    cb.ClaimGraphBuildV1, tc.TypedCompositionGraphV1, dict[str, int]
]:
    paragraphs, extractions = _paragraphs_and_extractions()
    build = cb.compile_claim_graph(paragraphs, extractions)
    assert cb.verify_claim_graph(build) == ()
    # No paragraph title occurs in another paragraph.  B1 cannot manufacture
    # either useful edge in this fixture.
    assert build.title_anchor_fallback.directed_links == ()
    assert all(arc.origin == "verified_shared_entity" for arc in build.directed_arcs)
    graph = tc.graph_from_claim_build(build)
    ordinal = {source_id: index for index, source_id in enumerate(graph.target_ids)}
    return build, graph, ordinal


def _static_scores(graph: tc.TypedCompositionGraphV1) -> np.ndarray:
    by_id = {
        "src:00-work": 1.0,
        "src:01-person": 0.10,
        "src:02-city": -0.05,
        "src:03-noise-a": 0.25,
        "src:04-noise-b": 0.15,
    }
    return np.asarray([by_id[item] for item in graph.target_ids], dtype=np.float64)


def _policy(*, max_hops: int = 2, mu: float = 0.5, **changes: object) -> tc.TypedCompositionPolicyV1:
    policy = tc.TypedCompositionPolicyV1(
        seed_k=1, max_hops=max_hops, mu=mu, fanout_exponent=0.0,
        max_fanout=4, max_join_degree=4, min_typed_match=0.20,
    )
    return replace(policy, **changes)


def _rank(scores: np.ndarray, target: int) -> int:
    order = np.argsort(-scores, kind="stable")
    return int(np.flatnonzero(order == target)[0]) + 1


def _single_gold_ndcg(scores: np.ndarray, target: int, *, k: int = 3) -> float:
    rank = _rank(scores, target)
    return 0.0 if rank > k else 1.0 / math.log2(rank + 1.0)


def _arc_id(
    graph: tc.TypedCompositionGraphV1, source_id: str, target_id: str,
) -> str:
    matches = [
        arc.arc_id for arc in graph.arcs
        if arc.source_id == source_id and arc.target_id == target_id
    ]
    assert len(matches) == 1
    return matches[0]


QUERY = (
    "Which birthplace city was the composer who composed the Clockwork Suite "
    "born in, and where is that city located?"
)


def test_b3_non_title_two_edge_chain_first_reaches_gold_at_depth_two():
    build, graph, ordinal = _compiled_chain()
    static = _static_scores(graph)
    gold = ordinal["src:02-city"]

    k1, _, k1_receipt = tc.compose_typed_scores(
        QUERY, static, graph, _policy(max_hops=1),
    )
    k2, _, k2_receipt = tc.compose_typed_scores(
        QUERY, static, graph, _policy(max_hops=2),
    )

    assert k1[gold].tobytes() == static[gold].tobytes()
    assert k2[gold] > k1[gold]
    assert _single_gold_ndcg(k2, gold) > _single_gold_ndcg(k1, gold)
    assert k2_receipt.h3_composition_status == "PASS"
    assert k2_receipt.k1_ablation is not None
    assert gold in k2_receipt.k1_ablation.full_over_k1_promoted_targets
    assert k1_receipt.h3_composition_status == "REFUSED"

    path = next(item for item in k2_receipt.promoted_paths if item.target == gold)
    assert path.first_reached_depth == path.selected_depth == 2
    assert path.intermediate_target_ids == ("src:01-person",)
    assert len(path.steps) == 2
    assert [step.source_selector.exact for step in path.steps] == [
        "Ada Lovelace", "Byron City",
    ]
    assert [step.target_selector.exact for step in path.steps] == [
        "Ada Lovelace", "Byron City",
    ]
    # Every selector remains an exact quote in the immutable paragraph input.
    text_by_source = {item.source_id: item.text for item in build.paragraphs}
    for step in path.steps:
        for selector in (step.source_selector, step.target_selector):
            assert text_by_source[selector.source_id][selector.start:selector.end] == selector.exact


def test_second_edge_target_and_relation_role_shuffles_kill_the_h3_gain():
    _, graph, ordinal = _compiled_chain()
    static = _static_scores(graph)
    gold = ordinal["src:02-city"]
    second_edge = _arc_id(graph, "src:01-person", "src:02-city")
    decoy_edge = _arc_id(graph, "src:03-noise-a", "src:04-noise-b")

    target_null = tc.target_shuffle_null_control(
        graph, (second_edge, decoy_edge), seed=7,
    )
    target_scores, _, target_receipt = tc.compose_typed_scores(
        QUERY, static, target_null, _policy(),
    )
    assert target_scores[gold].tobytes() == static[gold].tobytes()
    assert _single_gold_ndcg(target_scores, gold) == _single_gold_ndcg(static, gold)
    assert target_receipt.h3_composition_status == "PASS"  # a decoy may compose
    assert gold not in target_receipt.k1_ablation.full_over_k1_promoted_targets

    relation_null = tc.relation_shuffle_null_control(
        graph, (second_edge, decoy_edge), seed=11,
    )
    relation_scores, _, relation_receipt = tc.compose_typed_scores(
        QUERY, static, relation_null, _policy(),
    )
    assert relation_scores[gold].tobytes() == static[gold].tobytes()
    assert gold not in relation_receipt.k1_ablation.full_over_k1_promoted_targets
    assert relation_receipt.h3_composition_status == "REFUSED"
    assert relation_receipt.h3_refusal_reason == "no positive depth-2 promotion"


def test_relation_mismatch_refuses_and_mu_zero_is_bit_identical():
    _, graph, ordinal = _compiled_chain()
    static = _static_scores(graph)
    gold = ordinal["src:02-city"]

    mismatch, _, mismatch_receipt = tc.compose_typed_scores(
        "What color is the ocean?", static, graph, _policy(),
    )
    assert mismatch.tobytes() == static.tobytes()
    assert mismatch_receipt.h3_composition_status == "REFUSED"
    assert mismatch_receipt.trip_reason == "no_query_compatible_evidence_path"

    signed = static.copy()
    signed[gold] = -0.0
    floor, contribution, floor_receipt = tc.compose_typed_scores(
        QUERY, signed, graph, _policy(mu=0.0),
    )
    assert floor.tobytes() == signed.tobytes()
    assert contribution.tobytes() == np.zeros_like(signed).tobytes()
    assert floor_receipt.h3_composition_status == "REFUSED"
    assert floor_receipt.h3_refusal_reason == "mu=0 certified floor cannot establish composition"


def test_compiler_quarantines_a_nine_document_shared_entity_hub():
    paragraphs = tuple(
        cb.ParagraphInputV1(
            f"src:hub-{index:02d}", f"Hub Record {index:02d}",
            f"Node {index:02d} references Mega Common Entity.",
        )
        for index in range(cb.SHARED_ENTITY_POLICY.max_document_frequency + 1)
    )
    extractions = tuple(
        _freeze_claim(
            paragraph, subject=f"Node {index:02d}", predicate="references",
            argument="Mega Common Entity", argument_role="related_entity",
        )
        for index, paragraph in enumerate(paragraphs)
    )

    build = cb.compile_claim_graph(paragraphs, extractions)
    assert cb.verify_claim_graph(build) == ()
    assert [item.reason for item in build.quarantined_shared_entities] == [
        "hub_document_frequency"
    ]
    assert build.quarantined_shared_entities[0].document_frequency == 9
    assert not any(
        arc.origin == "verified_shared_entity" for arc in build.directed_arcs
    )

    graph = tc.graph_from_claim_build(build)
    static = np.linspace(1.0, 0.0, graph.n_targets, dtype=np.float64)
    final, _, receipt = tc.compose_typed_scores(
        "Which node references Mega Common Entity?", static, graph, _policy(),
    )
    assert final.tobytes() == static.tobytes()
    assert receipt.h3_composition_status == "REFUSED"
    assert receipt.trip_reason == "no_query_compatible_evidence_path"
