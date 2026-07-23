import json

from oss_extraction_compare import compare


def test_compare_aligns_exact_material_and_separates_coverage_from_evidence(tmp_path):
    hipporag_path = tmp_path / "hippo.json"
    journal_path = tmp_path / "v5.jsonl"
    hipporag_path.write_text(
        json.dumps(
            {
                "docs": [
                    {
                        "title": "Ada Lovelace",
                        "text": "Ada wrote Notes with Charles Babbage.",
                        "extracted_entities": ["Ada Lovelace", "Ada", "Lord Byron"],
                        "extracted_triples": [
                            ["Ada", "collaborated with", "Charles Babbage"]
                        ],
                    },
                    {
                        "title": "Unmatched",
                        "text": "This document must not enter the comparison.",
                        "extracted_entities": ["Unmatched"],
                        "extracted_triples": [],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    source_text = "Ada wrote Notes with Charles Babbage."
    claim = {
        "subject": {"start": 0, "end": 3, "exact": "Ada"},
        "predicate": {"start": 4, "end": 9, "exact": "wrote"},
        "arguments": [
            {"role": "object", "start": 10, "end": 15, "exact": "Notes"},
            {
                "role": "collaborator",
                "start": 21,
                "end": 36,
                "exact": "Charles Babbage",
            },
        ],
    }
    record = {
        "source_id": "source:1",
        "attempt_ordinal": 1,
        "record_id": "record:1",
        "status": "success",
        "source_input_json": json.dumps(
            {"title": "Ada Lovelace", "text": source_text}
        ),
        "frozen_extraction": {"payload_json": json.dumps({"claims": [claim]})},
        "quarantines": [],
    }
    journal_path.write_text(
        json.dumps({"event_type": "FINALIZE", "records": [record]}) + "\n",
        encoding="utf-8",
    )

    result = compare(hipporag_path, journal_path)

    assert result["aligned_docs"] == 1
    assert result["aligned_counts"]["hippo_entities"] == 3
    assert result["aligned_rates_pct"]["hippo_entity_title_plus_body_exact"] == 66.6667
    assert result["aligned_rates_pct"]["hippo_predicate_body_exact"] == 0.0
    assert result["aligned_counts"]["v5_role_spans"] == 4
    assert result["aligned_rates_pct"]["v5_offset_exact"] == 100.0
    assert result["aligned_counts"]["v5_nary_2plus_args"] == 1
    assert result["raw_surface_connectivity_not_h3_legal_chain"]["hipporag"][
        "directed_edges"
    ] == 1
