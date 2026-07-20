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
