"""H3 B3 preimage preparation keeps compiler and evaluator surfaces apart."""
from __future__ import annotations

import h3_b3_prepare as prep


def _row(qid: str, hop: str = "2hop"):
    return {
        "id": f"{hop}__{qid}", "hop": hop, "question": f"Where is {qid}?",
        "answer": "Hidden", "paragraphs": [
            {"title": f"Title {qid}", "paragraph_text": f"{qid} cites Bridge Person.",
             "is_supporting": True},
            {"title": "Noise", "paragraph_text": f"Noise {qid}.",
             "is_supporting": False},
        ],
    }


def test_development_extraction_surface_is_query_blind_and_stable():
    rows = [_row("a"), _row("b")]
    segment = prep.prepare_development_segment("musique", rows, n_rows=2)
    extracted = prep.extraction_records((segment,))
    assert len(extracted) == 4
    assert all(set(item) == {"source_id", "title", "text"} for item in extracted)
    assert all("question" not in item and "answer" not in item for item in extracted)
    assert segment.evaluation_rows[0].gold_source_ids
    assert prep.extraction_records((segment,)) == extracted


def test_embedding_preimage_uses_stable_id_not_array_position():
    segment = prep.prepare_development_segment(
        "musique", [_row("a"), _row("b")], n_rows=2,
    )
    records = prep.embedding_records((segment,))
    assert tuple(item["id"] for item in records) == tuple(sorted(
        item["id"] for item in records
    ))
    assert sum(item["kind"] == "query" for item in records) == 2
    assert sum(item["kind"] == "paragraph" for item in records) == 4


def test_duplicate_query_or_paragraph_collision_fails_closed():
    segment = prep.prepare_development_segment("musique", [_row("a")], n_rows=1)
    try:
        prep.embedding_records((segment, segment))
    except ValueError as exc:
        assert "duplicate query ID" in str(exc)
    else:
        raise AssertionError("duplicate segment should fail")


def test_duplicate_paragraph_occurrence_keeps_gold_binding_after_dedup():
    row = _row("dup")
    row["paragraphs"].append(dict(row["paragraphs"][0]))
    segment = prep.prepare_development_segment("musique", [row], n_rows=1)
    assert len(segment.paragraphs) == 2
    assert len(segment.evaluation_rows[0].paragraph_source_ids) == 2
    assert len(set(segment.evaluation_rows[0].paragraph_source_ids)) == 2
    assert len(segment.evaluation_rows[0].gold_source_ids) == 1


def test_development_gold_preserves_candidate_order_not_content_hash_order():
    supporting = [
        {"title": title, "paragraph_text": f"Evidence {title}.",
         "is_supporting": True}
        for title in ("Alpha", "Beta", "Gamma")
    ]
    supporting.sort(
        key=lambda item: prep.paragraph_source_id(
            "musique", item["title"], item["paragraph_text"],
        ),
        reverse=True,
    )
    row = _row("ordered")
    row["paragraphs"] = supporting

    segment = prep.prepare_development_segment("musique", [row], n_rows=1)
    evaluation = segment.evaluation_rows[0]

    assert evaluation.gold_source_ids == evaluation.paragraph_source_ids
    assert evaluation.gold_source_ids != tuple(sorted(evaluation.gold_source_ids))


def test_development_question_matches_normalized_provenance_text():
    row = _row("whitespace")
    row["question"] = "  Which   evidence\ncomes first?  "

    segment = prep.prepare_development_segment("musique", [row], n_rows=1)

    assert segment.evaluation_rows[0].question == "Which evidence comes first?"


def test_fresh_gold_preserves_candidate_order_not_content_hash_order():
    supporting = [
        {"title": title, "text": f"Evidence {title}."}
        for title in ("Delta", "Epsilon", "Zeta")
    ]
    supporting.sort(
        key=lambda item: prep.paragraph_source_id(
            "2wiki", item["title"], item["text"],
        ),
        reverse=True,
    )
    paragraphs = [
        {
            "source_id": prep.paragraph_source_id("2wiki", item["title"], item["text"]),
            "title": item["title"],
            "text": item["text"],
        }
        for item in supporting
    ]
    raw_row = {
        "id": "fresh-ordered",
        "question": "What follows the evidence chain?",
        "type": "compositional",
        "context": [
            [item["title"], [item["text"]]] for item in supporting
        ],
        "supporting_facts": [
            [item["title"], 0] for item in supporting
        ],
    }
    segment = prep.prepare_fresh_segment(
        {
            "dataset": "2wiki",
            "selected_qids": ["fresh-ordered"],
            "compiler_paragraphs": paragraphs,
        },
        [raw_row],
    )
    evaluation = segment.evaluation_rows[0]

    assert evaluation.gold_source_ids == evaluation.paragraph_source_ids
    assert evaluation.gold_source_ids != tuple(sorted(evaluation.gold_source_ids))
