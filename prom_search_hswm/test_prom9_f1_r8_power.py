from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from prom_search_hswm.hswm_typed_ports import canonical_sha256
from prom_search_hswm.prom9_f1_r8_power import (
    CONFIRMATORY_POOL_OFFSETS,
    DEVELOPMENT_OFFSETS,
    PowerRefusal,
    build_selection_receipt,
    selected_entries,
    verify_selection_receipt,
)
from prom_search_hswm.prom9_f1_prior_exposure import SCHEMA as PRIOR_SCHEMA


def _prior() -> dict[str, object]:
    items = [f"prior-item-{index:03d}" for index in range(104)]
    entities = [canonical_sha256({"prior-entity": index}) for index in range(104)]
    components = [canonical_sha256({"prior-component": index}) for index in range(104)]
    unsigned = {
        "schema_version": PRIOR_SCHEMA,
        "aggregate": {
            "prior_item_ids": items,
            "prior_source_entity_ids": entities,
            "prior_component_ids": components,
            "item_root_sha256": canonical_sha256(items),
            "source_entity_root_sha256": canonical_sha256(entities),
            "component_root_sha256": canonical_sha256(components),
        },
        "complete": True,
    }
    return {**unsigned, "prior_exposure_receipt_sha256": canonical_sha256(unsigned)}


def _row(index: int, *, development: bool, answer: str | None = None) -> dict[str, object]:
    if development and index < 200:
        title = f"development-pair-{index // 2:03d}"
    else:
        title = f"{'development' if development else 'confirmatory'}-{index:04d}"
    return {
        "id": f"{'dev' if development else 'r8'}-item-{index:04d}",
        "question": f"Question {index}?",
        "answer": answer if answer is not None else f"PRIVATE_{index}",
        "context": {"title": [title], "sentences": [[f"Sentence {title}."]]},
        "supporting_facts": {"title": [], "sent_id": []},
        "evidences": [],
        "type": "comparison",
    }


def _pages(tmp_path: Path):
    development: dict[int, Path] = {}
    for page_index, offset in enumerate(DEVELOPMENT_OFFSETS):
        rows = [
            _row(page_index * 100 + index, development=True)
            for index in range(100)
        ]
        path = tmp_path / f"dev-{offset}.json"
        path.write_text(json.dumps({"rows": [{"row": row} for row in rows]}), encoding="utf-8")
        path.chmod(0o600)
        development[offset] = path
    confirmatory: dict[int, Path] = {}
    for page_index, offset in enumerate(CONFIRMATORY_POOL_OFFSETS):
        rows = [
            _row(page_index * 100 + index, development=False)
            for index in range(100)
        ]
        path = tmp_path / f"r8-{offset}.json"
        path.write_text(json.dumps({"rows": [{"row": row} for row in rows]}), encoding="utf-8")
        path.chmod(0o600)
        confirmatory[offset] = path
    return development, confirmatory


def test_selection_freezes_48_components_in_12x4_and_100_fresh_items(tmp_path: Path) -> None:
    development, confirmatory = _pages(tmp_path)
    receipt = build_selection_receipt(
        prior_receipt=_prior(),
        development_pages=development,
        confirmatory_pages=confirmatory,
    )
    assert verify_selection_receipt(receipt) == receipt["selection_receipt_sha256"]
    schedule = receipt["development"]["component_schedule"]
    assert len(schedule) == 48
    assert {row["seed_block"] for row in schedule} == set(range(12))
    for block in range(12):
        assert {
            row["carryover_block"] for row in schedule if row["seed_block"] == block
        } == {0, 1, 2, 3}
    assert {row["cluster_size"] for row in schedule} >= {1, 2}
    assert len(receipt["confirmatory"]["component_schedule"]) == 100
    assert len(selected_entries(receipt, "confirmatory")) == 100
    assert receipt["pairwise_disjoint"] == {
        "item_ids": True,
        "source_entity_ids": True,
        "component_ids": True,
    }


def test_answer_mutation_changes_page_receipt_not_outcome_blind_selection(tmp_path: Path) -> None:
    development, confirmatory = _pages(tmp_path)
    first = build_selection_receipt(
        prior_receipt=_prior(),
        development_pages=development,
        confirmatory_pages=confirmatory,
    )
    page = development[104]
    value = json.loads(page.read_text(encoding="utf-8"))
    value["rows"][0]["row"]["answer"] = "MUTATED_PRIVATE_ANSWER"
    page.write_text(json.dumps(value), encoding="utf-8")
    page.chmod(0o600)
    second = build_selection_receipt(
        prior_receipt=_prior(),
        development_pages=development,
        confirmatory_pages=confirmatory,
    )
    assert first["development"]["item_ids"] == second["development"]["item_ids"]
    assert first["development"]["component_schedule"] == second["development"][
        "component_schedule"
    ]
    first_page = next(row for row in first["source_pages"] if row["offset"] == 104)
    second_page = next(row for row in second["source_pages"] if row["offset"] == 104)
    assert first_page["raw_bytes_sha256"] != second_page["raw_bytes_sha256"]


def test_selection_receipt_hash_tamper_is_refused(tmp_path: Path) -> None:
    development, confirmatory = _pages(tmp_path)
    receipt = build_selection_receipt(
        prior_receipt=_prior(),
        development_pages=development,
        confirmatory_pages=confirmatory,
    )
    tampered = copy.deepcopy(receipt)
    tampered["confirmatory"]["item_ids"].pop()
    with pytest.raises(PowerRefusal, match="self-hash"):
        verify_selection_receipt(tampered)
