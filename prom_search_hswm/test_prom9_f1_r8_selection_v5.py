from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from prom_search_hswm.hswm_typed_ports import canonical_sha256
import prom_search_hswm.prom9_f1_prior_exposure as prior_exposure
import prom_search_hswm.prom9_f1_r8_selection_v5 as selection_v5
from prom_search_hswm.prom9_f1_r8_selection_v5 import (
    DEVELOPMENT_COMPONENTS_V5,
    CONFIRMATORY_ITEMS_V5,
    SEED_BLOCKS_V5,
    SELECTION_SCHEMA_V5,
    build_selection_receipts_v5,
    replay_selection_receipt_v5,
    verify_gold_source_receipt_v5,
    verify_selection_receipt_v5,
)
from prom_search_hswm.prom9_f1_r8_power import PowerRefusal
from prom_search_hswm.prom9_f1_r8_source import source_entity_id


PRIOR_SHA = "a" * 64
SET_SHA = "b" * 64
PREDECESSOR_SHA = "c" * 64

# A dedicated entity whose component the predecessor is declared to have used.
PREDECESSOR_TITLE = "predecessor-shared-entity"
PREDECESSOR_SENTENCES = [f"Sentence {PREDECESSOR_TITLE}."]


def _prior() -> dict[str, object]:
    items = sorted(f"prior-item-{index:03d}" for index in range(10))
    entities = sorted(canonical_sha256({"prior-entity": i}) for i in range(10))
    components = sorted(canonical_sha256({"prior-component": i}) for i in range(10))
    return {
        "schema_version": "hswm-prom9-f1-prior-exposure/v1",
        "aggregate": {
            "prior_item_ids": items,
            "prior_source_entity_ids": entities,
            "prior_component_ids": components,
        },
        "complete": True,
        "prior_exposure_receipt_sha256": PRIOR_SHA,
    }


def _successor_set() -> dict[str, object]:
    items = sorted(f"aborted-item-{index:03d}" for index in range(3))
    entities = sorted(canonical_sha256({"aborted-entity": i}) for i in range(3))
    components = sorted(canonical_sha256({"aborted-component": i}) for i in range(3))
    return {
        "schema_version": "hswm-prom9-f1-successor-exposure-set/v1",
        "aggregate": {
            "prior_item_ids": items,
            "prior_source_entity_ids": entities,
            "prior_component_ids": components,
        },
        "complete": True,
        "aborted_attempt_exposure_receipt_sha256": SET_SHA,
    }


def _predecessor() -> dict[str, object]:
    entity = source_entity_id(PREDECESSOR_TITLE, PREDECESSOR_SENTENCES)
    component = canonical_sha256(
        {
            "schema_version": "hswm-source-entity-connected-component/v1",
            "source_entity_ids": [entity],
        }
    )
    return {
        "schema_version": "hswm-prom9-f1-r8-cohort-selection/v4",
        "development": {
            "item_ids": ["predecessor-dev-item"],
            "source_entity_ids": [entity],
            "component_ids": [component],
        },
        "confirmatory": {
            "item_ids": ["predecessor-conf-item"],
            "source_entity_ids": [
                canonical_sha256({"predecessor-conf-entity": 0})
            ],
            "component_ids": [
                canonical_sha256({"predecessor-conf-component": 0})
            ],
        },
        "selection_receipt_sha256": PREDECESSOR_SHA,
    }


@pytest.fixture(autouse=True)
def _patched_exposure_verifiers(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify_prior(value: Mapping[str, object]) -> str:
        return str(value["prior_exposure_receipt_sha256"])

    def verify_set(value: Mapping[str, object]) -> str:
        return str(value["aborted_attempt_exposure_receipt_sha256"])

    def aggregate(value: Mapping[str, object]) -> Mapping[str, object]:
        return value["aggregate"]

    def verify_predecessor(value: Mapping[str, object]) -> str:
        if value.get("schema_version") != "hswm-prom9-f1-r8-cohort-selection/v4":
            raise PowerRefusal("predecessor schema drifted")
        return str(value["selection_receipt_sha256"])

    monkeypatch.setattr(selection_v5, "verify_prior_exposure_receipt", verify_prior)
    monkeypatch.setattr(
        selection_v5, "verify_f1_r8_successor_exposure_set", verify_set
    )
    monkeypatch.setattr(
        selection_v5, "verify_predecessor_selection_receipt", verify_predecessor
    )
    monkeypatch.setattr(
        prior_exposure, "verify_prior_exposure_receipt", verify_prior
    )
    monkeypatch.setattr(
        prior_exposure, "verify_aborted_attempt_exposure_receipt", verify_set
    )
    monkeypatch.setattr(
        prior_exposure, "verified_aborted_attempt_aggregate", aggregate
    )


def _dev_row(page_index: int, index: int) -> dict[str, object]:
    serial = page_index * 100 + index
    if serial % 3 == 2:
        # Every third row pairs with its predecessor row to form a
        # two-item component.
        titles = [f"dev-pair-{serial - 1:05d}"]
    elif serial % 3 == 1:
        titles = [f"dev-pair-{serial:05d}"]
    elif serial == 0:
        # One development row rides the predecessor-forbidden entity.
        titles = [PREDECESSOR_TITLE]
    else:
        titles = [f"dev-single-{serial:05d}"]
    return {
        "id": f"v5-dev-item-{serial:05d}",
        "question": f"Question {serial}?",
        "answer": f"PRIVATE_{serial}",
        "context": {
            "title": titles,
            "sentences": [[f"Sentence {title}."] for title in titles],
        },
        "supporting_facts": {"title": [], "sent_id": []},
        "evidences": [],
        "type": "comparison",
    }


def _conf_row(page_index: int, index: int) -> dict[str, object]:
    serial = page_index * 100 + index
    return {
        "id": f"v5-conf-item-{serial:05d}",
        "question": f"Confirmatory question {serial}?",
        "answer": f"PRIVATE_CONF_{serial}",
        "context": {
            "title": [f"conf-single-{serial:05d}"],
            "sentences": [[f"Sentence conf-single-{serial:05d}."]],
        },
        "supporting_facts": {"title": [], "sent_id": []},
        "evidences": [],
        "type": "comparison",
    }


def _write_page(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        json.dumps({"rows": [{"row": row} for row in rows]}), encoding="utf-8"
    )
    path.chmod(0o600)


def _pages(
    tmp_path: Path, *, dev_pages: int = 1, conf_pages: int = 1
) -> tuple[dict[int, Path], dict[int, Path]]:
    development: dict[int, Path] = {}
    for page_index in range(dev_pages):
        offset = 1504 + page_index * 100
        path = tmp_path / f"dev-{offset}.json"
        _write_page(
            path, [_dev_row(page_index, index) for index in range(100)]
        )
        development[offset] = path
    confirmatory: dict[int, Path] = {}
    for page_index in range(conf_pages):
        offset = 5004 + page_index * 100
        path = tmp_path / f"conf-{offset}.json"
        _write_page(
            path, [_conf_row(page_index, index) for index in range(100)]
        )
        confirmatory[offset] = path
    return development, confirmatory


def _build_small(tmp_path: Path, **overrides):
    development, confirmatory = _pages(tmp_path)
    kwargs = {
        "prior_receipt": _prior(),
        "successor_exposure_set": _successor_set(),
        "predecessor_selection": _predecessor(),
        "development_pages": development,
        "confirmatory_pages": confirmatory,
        "development_components": 8,
        "confirmatory_items": 10,
    }
    kwargs.update(overrides)
    return build_selection_receipts_v5(**kwargs)


def test_v5_small_build_verify_and_replay(tmp_path: Path) -> None:
    selection, gold_source = _build_small(tmp_path)
    assert selection["schema_version"] == SELECTION_SCHEMA_V5
    assert selection["predecessor_selection_receipt_sha256"] == PREDECESSOR_SHA
    policy = selection["selection_policy"]
    assert policy["development_components"] == 8
    assert policy["seed_blocks"] == 2
    assert policy["confirmatory_items"] == 10
    assert policy["predecessor_exclusion_cohorts"] == [
        "development", "confirmatory",
    ]
    assert len(selection["development"]["component_schedule"]) == 8
    assert len(selection["confirmatory"]["component_schedule"]) == 10
    assert selection["pairwise_disjoint"] == {
        "item_ids": True,
        "source_entity_ids": True,
        "component_ids": True,
    }
    assert verify_selection_receipt_v5(selection)
    assert verify_gold_source_receipt_v5(gold_source, selection)
    assert replay_selection_receipt_v5(
        selection,
        prior_receipt=_prior(),
        successor_exposure_set=_successor_set(),
        predecessor_selection=_predecessor(),
    ) == selection["selection_receipt_sha256"]


def test_v5_predecessor_entity_is_excluded_from_both_cohorts(
    tmp_path: Path,
) -> None:
    selection, _gold = _build_small(tmp_path)
    forbidden_entity = source_entity_id(
        PREDECESSOR_TITLE, PREDECESSOR_SENTENCES
    )
    for cohort in ("development", "confirmatory"):
        block = selection[cohort]
        assert forbidden_entity not in set(block["source_entity_ids"])
        assert "predecessor-dev-item" not in set(block["item_ids"])
        # The row riding the predecessor entity is a live candidate row, so
        # its exclusion is the predecessor boundary doing real work.
        assert "v5-dev-item-00000" not in set(block["item_ids"])


def test_v5_variation_gate_requires_singleton_and_multi(tmp_path: Path) -> None:
    selected = _build_small(tmp_path)[0]["development"]["component_schedule"]
    sizes = {int(component["cluster_size"]) for component in selected}
    assert 1 in sizes and any(size > 1 for size in sizes)


def test_v5_historical_offset_is_refused(tmp_path: Path) -> None:
    development, confirmatory = _pages(tmp_path)
    stale = tmp_path / "dev-104.json"
    _write_page(stale, [_dev_row(9, index) for index in range(100)])
    development = {104: stale, **{k: v for k, v in development.items() if k != 1504}}
    with pytest.raises(PowerRefusal):
        build_selection_receipts_v5(
            prior_receipt=_prior(),
            successor_exposure_set=_successor_set(),
            predecessor_selection=_predecessor(),
            development_pages=development,
            confirmatory_pages=confirmatory,
            development_components=8,
            confirmatory_items=10,
        )


def test_v5_overlapping_pool_offsets_are_refused(tmp_path: Path) -> None:
    development, confirmatory = _pages(tmp_path)
    clash = tmp_path / "conf-clash.json"
    _write_page(clash, [_conf_row(9, index) for index in range(100)])
    confirmatory = {1504: clash}
    with pytest.raises(PowerRefusal):
        build_selection_receipts_v5(
            prior_receipt=_prior(),
            successor_exposure_set=_successor_set(),
            predecessor_selection=_predecessor(),
            development_pages=development,
            confirmatory_pages=confirmatory,
            development_components=8,
            confirmatory_items=10,
        )


def test_v5_insufficient_pool_is_refused(tmp_path: Path) -> None:
    with pytest.raises(PowerRefusal):
        _build_small(tmp_path, development_components=200)


def test_v5_tampered_receipt_and_replay_are_refused(tmp_path: Path) -> None:
    selection, _gold = _build_small(tmp_path)
    tampered = copy.deepcopy(selection)
    tampered["development"] = dict(tampered["development"])
    tampered["development"]["item_ids"] = list(
        tampered["development"]["item_ids"]
    )[:-1]
    with pytest.raises(PowerRefusal):
        verify_selection_receipt_v5(tampered)
    resigned = copy.deepcopy(selection)
    resigned["predecessor_selection_receipt_sha256"] = "d" * 64
    unsigned = dict(resigned)
    unsigned.pop("selection_receipt_sha256")
    resigned["selection_receipt_sha256"] = canonical_sha256(unsigned)
    assert verify_selection_receipt_v5(resigned)
    with pytest.raises(PowerRefusal):
        replay_selection_receipt_v5(
            resigned,
            prior_receipt=_prior(),
            successor_exposure_set=_successor_set(),
            predecessor_selection=_predecessor(),
        )


def test_v5_answer_only_mutation_keeps_public_receipt_identical(
    tmp_path: Path,
) -> None:
    development, confirmatory = _pages(tmp_path)
    first = build_selection_receipts_v5(
        prior_receipt=_prior(),
        successor_exposure_set=_successor_set(),
        predecessor_selection=_predecessor(),
        development_pages=development,
        confirmatory_pages=confirmatory,
        development_components=8,
        confirmatory_items=10,
    )
    mutated_dir = tmp_path / "mutated"
    mutated_dir.mkdir()
    for pages in (development, confirmatory):
        for offset, path in list(pages.items()):
            page = json.loads(path.read_text(encoding="utf-8"))
            for wrapped in page["rows"]:
                wrapped["row"]["answer"] = "MUTATED_" + str(offset)
            mutated = mutated_dir / path.name
            mutated.write_text(json.dumps(page), encoding="utf-8")
            mutated.chmod(0o600)
            pages[offset] = mutated
    second = build_selection_receipts_v5(
        prior_receipt=_prior(),
        successor_exposure_set=_successor_set(),
        predecessor_selection=_predecessor(),
        development_pages=development,
        confirmatory_pages=confirmatory,
        development_components=8,
        confirmatory_items=10,
    )
    assert first[0] == second[0]
    assert first[1] != second[1]


def test_v5_ratified_scale_800_by_800(tmp_path: Path) -> None:
    scale_dir = tmp_path / "scale"
    scale_dir.mkdir()
    development, confirmatory = {}, {}
    for page_index in range(13):
        offset = 1504 + page_index * 100
        path = scale_dir / f"dev-{offset}.json"
        _write_page(
            path, [_dev_row(page_index, index) for index in range(100)]
        )
        development[offset] = path
    for page_index in range(9):
        offset = 5004 + page_index * 100
        path = scale_dir / f"conf-{offset}.json"
        _write_page(
            path, [_conf_row(page_index, index) for index in range(100)]
        )
        confirmatory[offset] = path
    selection, gold_source = build_selection_receipts_v5(
        prior_receipt=_prior(),
        successor_exposure_set=_successor_set(),
        predecessor_selection=_predecessor(),
        development_pages=development,
        confirmatory_pages=confirmatory,
        development_components=DEVELOPMENT_COMPONENTS_V5,
        confirmatory_items=CONFIRMATORY_ITEMS_V5,
    )
    policy = selection["selection_policy"]
    assert policy["development_components"] == 800
    assert policy["seed_blocks"] == SEED_BLOCKS_V5 == 200
    schedule = selection["development"]["component_schedule"]
    assert len(schedule) == 800
    assert {int(value["seed_block"]) for value in schedule} == set(range(200))
    assert len(selection["confirmatory"]["component_schedule"]) == 800
    assert verify_selection_receipt_v5(selection)
    assert verify_gold_source_receipt_v5(gold_source, selection)
