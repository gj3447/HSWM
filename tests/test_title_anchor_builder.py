"""B1 exact-title-anchor builder teeth (offline, evaluation-blind).

Longinus ReferenceSite:
``HSWM/PROM_16_WORLD_COMPILER_CERTIFIED_READOUT_ENVELOPE_2026-07-20.md``
sections 14-18.
"""
from dataclasses import fields, replace
import inspect

import numpy as np
import pytest

import title_anchor_builder as tab


def _paragraphs() -> tuple[tab.ParagraphInputV1, ...]:
    return (
        tab.ParagraphInputV1(
            "src:castle",
            "Stormhold Castle",
            "The castle was built by Harlan Vex. Harlan Vex sealed its gates.",
        ),
        tab.ParagraphInputV1(
            "src:harlan",
            "Harlan Vex",
            "Harlan Vex feared the Ember—Dragon.",
        ),
        tab.ParagraphInputV1(
            "src:dragon",
            "Ember Dragon",
            "The Ember Dragon slept beneath a mountain.",
        ),
        tab.ParagraphInputV1(
            "src:noise",
            "Willow Market",
            "Fish and lamp oil were sold here.",
        ),
    )


def _pairs(build: tab.TitleAnchorBuildV1) -> set[tuple[str, str]]:
    return {
        (link.subject_source_id, link.object_source_id)
        for link in build.directed_links
    }


def test_narrow_compiler_input_excludes_all_evaluation_fields():
    assert [field.name for field in fields(tab.ParagraphInputV1)] == [
        "source_id", "title", "text",
    ]
    assert list(inspect.signature(tab.build_title_anchor_graph).parameters) == ["paragraphs"]
    with pytest.raises(TypeError, match="raw QA rows are forbidden"):
        tab.build_title_anchor_graph([{
            "source_id": "src:x",
            "title": "X",
            "text": "Y",
            "question": "leak",
            "answer": "leak",
            "is_supporting": True,
            "hop": 9,
        }])


def test_role_aware_chain_and_exact_evidence_receipts():
    build = tab.build_title_anchor_graph(_paragraphs())
    assert ("src:castle", "src:harlan") in _pairs(build)
    assert ("src:harlan", "src:dragon") in _pairs(build)
    assert ("src:castle", "src:dragon") not in _pairs(build)

    link = next(
        item for item in build.directed_links
        if item.subject_source_id == "src:harlan" and item.object_source_id == "src:dragon"
    )
    assert link.subject_role == tab.SUBJECT_ROLE == "paragraph_title_subject"
    assert link.object_role == tab.OBJECT_ROLE == "body_title_alias_object"
    receipt = next(item for item in build.evidence_spans if item.receipt_id in link.evidence_receipt_ids)
    paragraph = next(item for item in build.paragraphs if item.source_id == receipt.source_id)
    assert paragraph.text[receipt.body_start:receipt.body_end] == receipt.exact_quote
    assert receipt.exact_quote == "Ember—Dragon"
    assert receipt.normalized_alias == "ember dragon"
    assert receipt.offset_unit == tab.OFFSET_UNIT
    assert tab.verify_title_anchor_build(build) == ()


def test_unicode_punctuation_normalizer_is_exact_not_fuzzy():
    assert tab.normalize_title_alias("  Ｎｅｗ—YORK!!! ") == "new york"
    paragraphs = (
        tab.ParagraphInputV1("src:guide", "Guide", "Ｎｅｗ—YORK borders Yorkshire."),
        tab.ParagraphInputV1("src:ny", "New York", "A city."),
        tab.ParagraphInputV1("src:york", "York", "Another city."),
        tab.ParagraphInputV1("src:yorkshire", "Yorkshire", "A county."),
    )
    build = tab.build_title_anchor_graph(paragraphs)
    assert _pairs(build) == {
        ("src:guide", "src:ny"),
        ("src:guide", "src:yorkshire"),
    }
    assert ("src:guide", "src:york") not in _pairs(build)  # no York-in-Yorkshire fuzzy hit
    receipt = next(
        item for item in build.evidence_spans
        if item.disposition == "linked" and item.object_source_id == "src:ny"
    )
    assert receipt.exact_quote == "Ｎｅｗ—YORK"


def test_leftmost_longest_suppresses_nested_title_alias():
    paragraphs = (
        tab.ParagraphInputV1("src:guide", "Guide", "New York is larger."),
        tab.ParagraphInputV1("src:new-york", "New York", "A city."),
        tab.ParagraphInputV1("src:york", "York", "Another city."),
    )
    build = tab.build_title_anchor_graph(paragraphs)
    assert _pairs(build) == {("src:guide", "src:new-york")}
    linked = [item for item in build.evidence_spans if item.source_id == "src:guide"]
    assert [(item.exact_quote, item.object_source_id) for item in linked] == [
        ("New York", "src:new-york")
    ]


def test_ambiguous_short_alias_is_quarantined_but_qualified_alias_can_link():
    paragraphs = (
        tab.ParagraphInputV1(
            "src:guide", "Guide", "Mercury was known early. Mercury (planet) has an orbit."
        ),
        tab.ParagraphInputV1("src:planet", "Mercury (planet)", "A world."),
        tab.ParagraphInputV1("src:element", "Mercury (element)", "A metal."),
    )
    build = tab.build_title_anchor_graph(paragraphs)
    assert _pairs(build) == {("src:guide", "src:planet")}
    assert len(build.quarantined_spans) == 1
    quarantine = build.quarantined_spans[0]
    assert quarantine.exact_quote == "Mercury"
    assert quarantine.candidate_source_ids == ("src:planet", "src:element")
    assert quarantine.reason == "ambiguous_alias"
    assert build.stats["alias_ambiguity"] == {
        "ambiguous_alias_keys": 1,
        "ambiguous_alias_bindings": 2,
        "quarantined_spans": 1,
        "quarantined_characters": len("Mercury"),
    }


def test_target_and_unit_text_order_are_cache_compatible():
    paragraphs = _paragraphs()
    build = tab.build_title_anchor_graph(paragraphs)
    assert build.paragraph_graph.target_source_ids == tuple(item.source_id for item in paragraphs)
    assert build.paragraph_graph.unit_texts == tuple(
        f"{item.title} :: {item.text}" for item in paragraphs
    )
    assert [item.ordinal for item in build.paragraphs] == list(range(len(paragraphs)))

    expected = np.zeros((len(paragraphs), len(paragraphs)))
    expected[0, 1] = 1.0
    expected[1, 2] = 1.0
    assert np.array_equal(build.paragraph_graph.adjacency(), expected)


def test_descriptive_stats_cover_spans_outdegree_hubs_and_ambiguity():
    build = tab.build_title_anchor_graph(_paragraphs())
    assert build.stats["n_paragraphs"] == 4
    assert build.stats["n_directed_links"] == 2
    coverage = build.stats["span_coverage"]
    assert coverage["selected_spans"] >= coverage["linked_spans"] == 3
    # Two occurrences of Harlan Vex collapse to one directed edge but retain
    # two evidence receipts; one title self-reference remains audit-only.
    assert coverage["self_reference_spans"] >= 1
    assert 0.0 < coverage["linked_char_fraction"] < 1.0
    assert build.stats["outdegree"]["max"] == 1
    assert build.stats["hubs"]["indegree"]["max"] == 1
    assert build.stats["hubs"]["top"][0]["source_id"] == "src:harlan"
    assert "alias_ambiguity" in build.stats


def test_deterministic_and_integrity_verifier_detects_tampered_quote():
    first = tab.build_title_anchor_graph(_paragraphs())
    second = tab.build_title_anchor_graph(_paragraphs())
    assert first == second
    assert first.build_id == second.build_id
    assert np.array_equal(
        first.paragraph_graph.adjacency(), second.paragraph_graph.adjacency()
    )

    bad_receipt = replace(first.evidence_spans[0], exact_quote="tampered")
    tampered = replace(first, evidence_spans=(bad_receipt, *first.evidence_spans[1:]))
    assert any(
        issue.startswith("receipt_quote_mismatch:")
        for issue in tab.verify_title_anchor_build(tampered)
    )


def test_duplicate_or_unstable_source_identity_fails_closed():
    with pytest.raises(ValueError, match="duplicate stable source_id"):
        tab.build_title_anchor_graph((
            tab.ParagraphInputV1("src:same", "Alpha", "Text."),
            tab.ParagraphInputV1("src:same", "Beta", "Text."),
        ))
    with pytest.raises(ValueError, match="source_id must be non-empty"):
        tab.build_title_anchor_graph((tab.ParagraphInputV1("", "Alpha", "Text."),))
