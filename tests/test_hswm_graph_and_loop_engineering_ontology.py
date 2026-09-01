from __future__ import annotations

import json
from pathlib import Path

from scripts import build_hswm_graph_and_loop_engineering_ontology as builder
from scripts import upsert_hswm_graph_and_loop_engineering as publisher


ROOT = Path(__file__).resolve().parents[1]


def test_graph_and_loop_engineering_projection_is_deterministic_and_current() -> None:
    data = builder.build_data()

    builder.validate_data(data)
    publisher.validate_data(data)

    path = ROOT / builder.ONTOLOGY_PATH
    assert path.read_bytes() == builder.encoded_data(data)
    assert json.loads(path.read_text(encoding="utf-8")) == data
    assert data["expected_counts"]["external_source_records"] == len(
        builder.EXTERNAL_SOURCES
    )
    assert data["expected_counts"]["gates"] == len(builder.GATES)
