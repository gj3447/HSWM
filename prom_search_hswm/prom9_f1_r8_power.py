#!/usr/bin/env python3
"""Freeze outcome-blind F1 r8 cohorts and build the development power receipt.

Selection reads only Dataset Viewer IDs/questions/context/type.  Public
selection v2 contains only those redacted rows; exact answer-bearing page and
selected-row preimages live in a separate evaluator-only receipt.  Development components are frozen before
any model call as 12 equal blocks of four; the confirmatory cohort is selected
from complete singleton components so exactly 100 raw items are retained.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import re
import sys
from collections.abc import Mapping, Sequence

from prom_search_hswm.hswm_function_network import (
    FLAT_ARM,
    REMOVAL_ARM,
    SHUFFLE_ARM,
    TYPED_ARM,
    VECTOR_ARM,
)
from prom_search_hswm.hswm_typed_ports import canonical_json, canonical_sha256
from prom_search_hswm.prom9_f1_r8_environment import (
    R8_DEPENDENCY_NAMES,
    verify_dependency_receipt,
    verify_environment_receipt,
    verify_preimage_bundle,
)
from prom_search_hswm.prom9_f1_prior_exposure import (
    _assign_components,
    _page_projection,
    _read_private_bytes,
    _strict_object,
    verify_prior_exposure_receipt,
    write_private_once,
)


SELECTION_SCHEMA = "hswm-prom9-f1-r8-cohort-selection/v2"
GOLD_SOURCE_SCHEMA = "hswm-prom9-f1-r8-gold-source-receipt/v1"
POWER_RECEIPT_SCHEMA = "hswm-prom9-f1-r8-power-operating-characteristic/v3"
POWER_DEVELOPMENT_SCHEMA = "hswm-prom9-f1-r8-power-development-data/v2"
POWER_EVIDENCE_SCHEMA = "hswm-prom9-f1-r8-development-evidence/v1"
POWER_SIMULATOR_SCHEMA = "hswm-prom9-f1-r8-power-simulator-spec/v1"
BLOCK_ASSIGNMENT_SCHEMA = "hswm-f1-r8-power-block-assignment/v1"
SELECTION_KEY_SCHEMA = "hswm-f1-r8-component-selection/v1"
SELECTION_SEED = 20260728
DEVELOPMENT_OFFSETS = (104, 204, 304, 404)
CONFIRMATORY_POOL_OFFSETS = (504, 604, 704, 804, 904, 1004, 1104, 1204, 1304, 1404)
DEVELOPMENT_COMPONENTS = 48
SEED_BLOCKS = 12
COMPONENTS_PER_BLOCK = 4
SELECTED_CLUSTERS = 40
TRIALS = 60
BOOTSTRAP = {
    "reps": 10000,
    "seed": 20260724,
    "lower_index": 249,
    "upper_index": 9749,
    "paired": True,
    "unit": "component_cluster_macro",
    "method": "paired_cluster_percentile_bootstrap_v1",
    "minimum_clusters": 40,
    "metric": "min_of_four_paired_cluster_bootstrap_lcbs",
}
POWER_SCENARIOS = (
    "null", "effect_0_03", "mde", "effect_0_08", "coverage",
    "unequal_cluster", "heavy_tail", "seed_interaction", "carryover",
)
CONTROLS = (FLAT_ARM, VECTOR_ARM, REMOVAL_ARM, SHUFFLE_ARM)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
REQUIRED_DEPENDENCY_NAMES = R8_DEPENDENCY_NAMES


class PowerRefusal(RuntimeError):
    """The frozen selection or power evidence is inadmissible."""


def _manifest_source_entity_ids(item: Mapping[str, object]) -> list[str]:
    candidates = item.get("candidates")
    if not isinstance(candidates, list) or any(
        not isinstance(candidate, Mapping) for candidate in candidates
    ):
        raise PowerRefusal("development manifest candidates are malformed")
    return sorted(
        {str(candidate.get("source_entity_id")) for candidate in candidates}
    )


def _redact_entry(entry: Mapping[str, object]) -> dict[str, object]:
    row = entry.get("row")
    if not isinstance(row, Mapping):
        raise PowerRefusal("candidate row is malformed")
    try:
        redacted = {key: row[key] for key in ("id", "question", "context", "type")}
    except KeyError as error:
        raise PowerRefusal("candidate row lacks a public field") from error
    return {
        "dataset_row_index": entry["dataset_row_index"],
        "row": json.loads(canonical_json(redacted)),
    }


def _page_input_redacted(
    entries: Sequence[Mapping[str, object]], offset: int
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    if len(entries) != 100:
        raise PowerRefusal("public candidate page length drifted")
    normalized: list[dict[str, object]] = []
    fake_rows: list[dict[str, object]] = []
    for index, raw_entry in enumerate(entries):
        if not isinstance(raw_entry, Mapping) or set(raw_entry) != {
            "dataset_row_index", "row"
        }:
            raise PowerRefusal("public candidate entry shape drifted")
        row = raw_entry.get("row")
        if (
            raw_entry.get("dataset_row_index") != offset + index
            or not isinstance(row, Mapping)
            or set(row) != {"id", "question", "context", "type"}
        ):
            raise PowerRefusal("public candidate row allowlist drifted")
        normalized_entry = json.loads(canonical_json(dict(raw_entry)))
        normalized.append(normalized_entry)
        fake_rows.append(
            {
                "row": {
                    **dict(row),
                    "answer": "",
                    "supporting_facts": {"title": [], "sent_id": []},
                    "evidences": [],
                }
            }
        )
    projections = _page_projection(
        {"rows": fake_rows}, offset=offset, length=100
    )
    receipt = {
        "offset": offset,
        "length": 100,
        "redacted_rows": normalized,
        "redacted_rows_sha256": canonical_sha256(normalized),
        "whitelisted_projection_sha256": canonical_sha256(projections),
    }
    return receipt, projections, normalized


def _page_input_bytes(
    raw: bytes, offset: int
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    page = _strict_object(raw, "r8 candidate page")
    full_projection = _page_projection(page, offset=offset, length=100)
    wrapped = page.get("rows")
    assert isinstance(wrapped, list)
    full_entries = [
        {"dataset_row_index": offset + index, "row": dict(value["row"])}
        for index, value in enumerate(wrapped)
    ]
    public = _page_input_redacted(
        [_redact_entry(entry) for entry in full_entries], offset
    )
    if public[1] != full_projection:
        raise PowerRefusal("public page projection differs from the full preimage")
    return public


def _page_input(
    path: Path, offset: int
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    return _page_input_bytes(_read_private_bytes(path), offset)


def _component_key(component_id: str, purpose: str) -> tuple[str, str]:
    return (
        canonical_sha256(
            {
                "schema_version": SELECTION_KEY_SCHEMA,
                "seed": SELECTION_SEED,
                "purpose": purpose,
                "component_id": component_id,
            }
        ),
        component_id,
    )


def _block_key(component_id: str) -> tuple[str, str]:
    return (
        canonical_sha256(
            {
                "schema_version": BLOCK_ASSIGNMENT_SCHEMA,
                "seed": SELECTION_SEED,
                "component_id": component_id,
            }
        ),
        component_id,
    )


def _selected_rows_block(
    selected_components: Sequence[Mapping[str, object]],
    entries_by_item: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    item_ids = sorted(
        str(item_id)
        for component in selected_components
        for item_id in component["item_ids"]
    )
    entries = sorted(
        (dict(entries_by_item[item_id]) for item_id in item_ids),
        key=lambda value: int(value["dataset_row_index"]),
    )
    source_entities = sorted(
        {
            str(entity)
            for component in selected_components
            for entity in component["source_entity_ids"]
        }
    )
    component_ids = sorted(str(component["component_id"]) for component in selected_components)
    return {
        "item_ids": item_ids,
        "source_entity_ids": source_entities,
        "component_ids": component_ids,
        "selected_rows": entries,
        "selected_rows_sha256": canonical_sha256(entries),
        "item_root_sha256": canonical_sha256(item_ids),
        "source_entity_root_sha256": canonical_sha256(source_entities),
        "component_root_sha256": canonical_sha256(component_ids),
    }


def _verify_disjoint(left: Mapping[str, object], right: Mapping[str, object], label: str) -> None:
    for key in ("item_ids", "source_entity_ids", "component_ids"):
        if set(left[key]) & set(right[key]):
            raise PowerRefusal(f"{label} overlaps on {key}")


def _build_selection_receipt(
    *,
    prior_receipt: Mapping[str, object],
    development_pages: Mapping[int, object],
    confirmatory_pages: Mapping[int, object],
    page_loader,
) -> dict[str, object]:
    prior_sha = verify_prior_exposure_receipt(prior_receipt)
    if set(development_pages) != set(DEVELOPMENT_OFFSETS):
        raise PowerRefusal("development candidate pages drifted")
    if set(confirmatory_pages) != set(CONFIRMATORY_POOL_OFFSETS):
        raise PowerRefusal("confirmatory candidate pages drifted")
    aggregate = prior_receipt.get("aggregate")
    if not isinstance(aggregate, Mapping):
        raise PowerRefusal("prior exposure aggregate is missing")
    prior = {
        "item_ids": list(aggregate["prior_item_ids"]),
        "source_entity_ids": list(aggregate["prior_source_entity_ids"]),
        "component_ids": list(aggregate["prior_component_ids"]),
    }
    prior_entities = set(str(value) for value in prior["source_entity_ids"])
    prior_items = set(str(value) for value in prior["item_ids"])

    page_receipts: list[dict[str, object]] = []
    development_rows: list[dict[str, object]] = []
    development_entries: list[dict[str, object]] = []
    for offset in DEVELOPMENT_OFFSETS:
        page_receipt, projections, entries = page_loader(
            development_pages[offset], offset
        )
        page_receipts.append({"purpose": "development", **page_receipt})
        development_rows.extend(projections)
        development_entries.extend(entries)
    dev_items = [dict(row) for row in development_rows]
    dev_components = _assign_components(dev_items)
    eligible_dev = [
        component
        for component in dev_components
        if not (set(component["source_entity_ids"]) & prior_entities)
        and not (set(component["item_ids"]) & prior_items)
    ]
    if len(eligible_dev) < DEVELOPMENT_COMPONENTS:
        raise PowerRefusal("development pool has fewer than 48 prior-fresh components")
    development_selected = sorted(
        eligible_dev,
        key=lambda value: _component_key(str(value["component_id"]), "development_power"),
    )[:DEVELOPMENT_COMPONENTS]
    if not ({len(component["item_ids"]) for component in development_selected} & {1}) or not any(
        len(component["item_ids"]) > 1 for component in development_selected
    ):
        raise PowerRefusal("development selection lacks singleton/multi-item variation")
    block_order = sorted(
        development_selected,
        key=lambda value: _block_key(str(value["component_id"])),
    )
    development_schedule: list[dict[str, object]] = []
    for rank, component in enumerate(block_order):
        development_schedule.append(
            {
                "component_id": component["component_id"],
                "item_ids": sorted(component["item_ids"]),
                "source_entity_ids": sorted(component["source_entity_ids"]),
                "cluster_size": len(component["item_ids"]),
                "seed_block": rank // COMPONENTS_PER_BLOCK,
                "carryover_block": rank % COMPONENTS_PER_BLOCK,
            }
        )
    if (
        len(development_schedule) != DEVELOPMENT_COMPONENTS
        or {int(value["seed_block"]) for value in development_schedule} != set(range(SEED_BLOCKS))
        or any(
            {int(value["carryover_block"]) for value in development_schedule if value["seed_block"] == block}
            != set(range(COMPONENTS_PER_BLOCK))
            for block in range(SEED_BLOCKS)
        )
    ):
        raise PowerRefusal("development block assignment drifted")
    dev_entries_by_item = {
        str(entry["row"]["id"]): entry for entry in development_entries
    }
    development_block = _selected_rows_block(development_schedule, dev_entries_by_item)

    confirmatory_rows: list[dict[str, object]] = []
    confirmatory_entries: list[dict[str, object]] = []
    for offset in CONFIRMATORY_POOL_OFFSETS:
        page_receipt, projections, entries = page_loader(
            confirmatory_pages[offset], offset
        )
        page_receipts.append({"purpose": "confirmatory_pool", **page_receipt})
        confirmatory_rows.extend(projections)
        confirmatory_entries.extend(entries)
    confirmatory_items = [dict(row) for row in confirmatory_rows]
    confirmatory_components = _assign_components(confirmatory_items)
    dev_entities = set(development_block["source_entity_ids"])
    dev_item_ids = set(development_block["item_ids"])
    eligible_confirmatory = [
        component
        for component in confirmatory_components
        if len(component["item_ids"]) == 1
        and not (set(component["source_entity_ids"]) & (prior_entities | dev_entities))
        and not (set(component["item_ids"]) & (prior_items | dev_item_ids))
    ]
    if len(eligible_confirmatory) < 100:
        raise PowerRefusal("confirmatory pool has fewer than 100 fresh singleton components")
    confirmatory_selected = sorted(
        eligible_confirmatory,
        key=lambda value: _component_key(str(value["component_id"]), "confirmatory_r8"),
    )[:100]
    confirmatory_schedule = [
        {
            "component_id": component["component_id"],
            "item_ids": sorted(component["item_ids"]),
            "source_entity_ids": sorted(component["source_entity_ids"]),
            "cluster_size": 1,
        }
        for component in confirmatory_selected
    ]
    confirmatory_entries_by_item = {
        str(entry["row"]["id"]): entry for entry in confirmatory_entries
    }
    confirmatory_block = _selected_rows_block(
        confirmatory_schedule, confirmatory_entries_by_item
    )
    _verify_disjoint(prior, development_block, "prior/development")
    _verify_disjoint(prior, confirmatory_block, "prior/confirmatory")
    _verify_disjoint(development_block, confirmatory_block, "development/confirmatory")
    if len(confirmatory_block["item_ids"]) != 100 or len(confirmatory_schedule) != 100:
        raise PowerRefusal("confirmatory selection is not exactly 100 complete components")

    policy = {
        "selection_seed": SELECTION_SEED,
        "development_pool_offsets": list(DEVELOPMENT_OFFSETS),
        "confirmatory_pool_offsets": list(CONFIRMATORY_POOL_OFFSETS),
        "page_length": 100,
        "development_components": DEVELOPMENT_COMPONENTS,
        "seed_blocks": SEED_BLOCKS,
        "components_per_seed_block": COMPONENTS_PER_BLOCK,
        "confirmatory_items": 100,
        "confirmatory_component_size": 1,
        "selection_key_schema": SELECTION_KEY_SCHEMA,
        "block_assignment_schema": BLOCK_ASSIGNMENT_SCHEMA,
        "derived_fields": ["id", "question", "context", "type"],
        "answers_used_for_selection": False,
    }
    unsigned = {
        "schema_version": SELECTION_SCHEMA,
        "prior_exposure_receipt_sha256": prior_sha,
        "selection_policy": policy,
        "source_pages": page_receipts,
        "development": {
            **development_block,
            "component_schedule": development_schedule,
            "selection_root_sha256": canonical_sha256(
                [value["component_id"] for value in development_selected]
            ),
        },
        "confirmatory": {
            **confirmatory_block,
            "component_schedule": confirmatory_schedule,
            "selection_root_sha256": canonical_sha256(
                [value["component_id"] for value in confirmatory_selected]
            ),
        },
        "pairwise_disjoint": {
            "item_ids": True,
            "source_entity_ids": True,
            "component_ids": True,
        },
        "answers_disclosed_to_stdout": False,
    }
    return {**unsigned, "selection_receipt_sha256": canonical_sha256(unsigned)}


def build_selection_receipt(
    *,
    prior_receipt: Mapping[str, object],
    development_pages: Mapping[int, Path],
    confirmatory_pages: Mapping[int, Path],
) -> dict[str, object]:
    """Compatibility wrapper returning only the answer-redacted public receipt."""

    selection, _gold_source = build_selection_receipts(
        prior_receipt=prior_receipt,
        development_pages=development_pages,
        confirmatory_pages=confirmatory_pages,
    )
    return selection


def _full_entries_from_page(raw: bytes, offset: int) -> list[dict[str, object]]:
    page = _strict_object(raw, "r8 candidate page")
    _page_projection(page, offset=offset, length=100)
    wrapped = page.get("rows")
    assert isinstance(wrapped, list)
    return [
        {
            "dataset_row_index": offset + index,
            "row": json.loads(canonical_json(dict(value["row"]))),
        }
        for index, value in enumerate(wrapped)
    ]


def _gold_selected_block(
    item_ids: Sequence[object], entries_by_item: Mapping[str, Mapping[str, object]]
) -> dict[str, object]:
    entries = sorted(
        (dict(entries_by_item[str(item_id)]) for item_id in item_ids),
        key=lambda entry: int(entry["dataset_row_index"]),
    )
    return {
        "full_rows": entries,
        "full_rows_sha256": canonical_sha256(entries),
    }


def build_selection_receipts(
    *,
    prior_receipt: Mapping[str, object],
    development_pages: Mapping[int, Path],
    confirmatory_pages: Mapping[int, Path],
) -> tuple[dict[str, object], dict[str, object]]:
    """Build the public v2 selection and evaluator-only gold-source v1 pair."""

    if set(development_pages) != set(DEVELOPMENT_OFFSETS):
        raise PowerRefusal("development candidate pages drifted")
    if set(confirmatory_pages) != set(CONFIRMATORY_POOL_OFFSETS):
        raise PowerRefusal("confirmatory candidate pages drifted")
    development_raw = {
        offset: _read_private_bytes(Path(development_pages[offset]))
        for offset in DEVELOPMENT_OFFSETS
    }
    confirmatory_raw = {
        offset: _read_private_bytes(Path(confirmatory_pages[offset]))
        for offset in CONFIRMATORY_POOL_OFFSETS
    }
    selection = _build_selection_receipt(
        prior_receipt=prior_receipt,
        development_pages=development_raw,
        confirmatory_pages=confirmatory_raw,
        page_loader=lambda raw, offset: _page_input_bytes(bytes(raw), offset),
    )
    selection_sha = verify_selection_receipt(selection)
    page_receipts: list[dict[str, object]] = []
    all_entries: list[dict[str, object]] = []
    for purpose, pages in (
        ("development", development_raw),
        ("confirmatory_pool", confirmatory_raw),
    ):
        for offset, raw in pages.items():
            page = _strict_object(raw, "r8 candidate page")
            entries = _full_entries_from_page(raw, offset)
            all_entries.extend(entries)
            page_receipts.append(
                {
                    "purpose": purpose,
                    "offset": offset,
                    "length": 100,
                    "raw_page_base64": base64.b64encode(raw).decode("ascii"),
                    "raw_page_sha256": hashlib.sha256(raw).hexdigest(),
                    "canonical_page_sha256": canonical_sha256(page),
                }
            )
    entries_by_item = {
        str(entry["row"]["id"]): entry for entry in all_entries
    }
    if len(entries_by_item) != len(all_entries):
        raise PowerRefusal("candidate item identity repeats across source pages")
    gold_unsigned = {
        "schema_version": GOLD_SOURCE_SCHEMA,
        "selection_receipt_sha256": selection_sha,
        "source_pages": page_receipts,
        "selected_rows": {
            cohort: _gold_selected_block(
                selection[cohort]["item_ids"], entries_by_item
            )
            for cohort in ("development", "confirmatory")
        },
    }
    gold_source = {
        **gold_unsigned,
        "gold_source_receipt_sha256": canonical_sha256(gold_unsigned),
    }
    verify_gold_source_receipt(gold_source, selection)
    return selection, gold_source


def _verify_development_block_assignment(
    development: Mapping[str, object],
) -> None:
    schedule = development.get("component_schedule")
    if not isinstance(schedule, list) or len(schedule) != DEVELOPMENT_COMPONENTS:
        raise PowerRefusal("development selection must contain exactly 48 components")
    rows: dict[str, Mapping[str, object]] = {}
    for raw in schedule:
        if not isinstance(raw, Mapping):
            raise PowerRefusal("development component schedule is malformed")
        component_id = raw.get("component_id")
        if (
            not isinstance(component_id, str)
            or _SHA256.fullmatch(component_id) is None
            or component_id in rows
        ):
            raise PowerRefusal("development component schedule identity drifted")
        rows[component_id] = raw
    ordered = sorted(rows, key=_block_key)
    if [str(raw.get("component_id")) for raw in schedule] != ordered:
        raise PowerRefusal("development block order drifted")
    for rank, component_id in enumerate(ordered):
        raw = rows[component_id]
        observed = (raw.get("seed_block"), raw.get("carryover_block"))
        expected = (rank // COMPONENTS_PER_BLOCK, rank % COMPONENTS_PER_BLOCK)
        if (
            any(isinstance(value, bool) or not isinstance(value, int) for value in observed)
            or observed != expected
        ):
            raise PowerRefusal("development block assignment drifted")


def replay_selection_receipt(
    value: Mapping[str, object], *, prior_receipt: Mapping[str, object]
) -> str:
    """Replay the selector from public redacted pages only."""

    declared = verify_selection_receipt(value)
    pages = value.get("source_pages")
    if not isinstance(pages, list) or len(pages) != (
        len(DEVELOPMENT_OFFSETS) + len(CONFIRMATORY_POOL_OFFSETS)
    ):
        raise PowerRefusal("selection source-page inventory drifted")
    development: dict[int, list[dict[str, object]]] = {}
    confirmatory: dict[int, list[dict[str, object]]] = {}
    expected_fields = {
        "purpose",
        "offset",
        "length",
        "redacted_rows",
        "redacted_rows_sha256",
        "whitelisted_projection_sha256",
    }
    for raw_page in pages:
        if not isinstance(raw_page, Mapping) or set(raw_page) != expected_fields:
            raise PowerRefusal("selection source-page shape drifted")
        offset = raw_page.get("offset")
        purpose = raw_page.get("purpose")
        rows = raw_page.get("redacted_rows")
        if (
            isinstance(offset, bool)
            or not isinstance(offset, int)
            or raw_page.get("length") != 100
            or not isinstance(rows, list)
        ):
            raise PowerRefusal("selection source-page metadata drifted")
        if purpose == "development" and offset in DEVELOPMENT_OFFSETS:
            target = development
        elif purpose == "confirmatory_pool" and offset in CONFIRMATORY_POOL_OFFSETS:
            target = confirmatory
        else:
            raise PowerRefusal("selection source-page purpose or offset drifted")
        if offset in target:
            raise PowerRefusal("selection source-page offset repeats")
        target[offset] = [dict(row) for row in rows]
    rebuilt = _build_selection_receipt(
        prior_receipt=prior_receipt,
        development_pages=development,
        confirmatory_pages=confirmatory,
        page_loader=lambda rows, offset: _page_input_redacted(rows, offset),
    )
    if rebuilt != dict(value):
        raise PowerRefusal("selection receipt does not replay from sealed source pages")
    return declared


def verify_selection_receipt(value: Mapping[str, object]) -> str:
    if value.get("schema_version") != SELECTION_SCHEMA:
        raise PowerRefusal("selection receipt schema drifted")
    unsigned = dict(value)
    declared = unsigned.pop("selection_receipt_sha256", None)
    if not isinstance(declared, str) or canonical_sha256(unsigned) != declared:
        raise PowerRefusal("selection receipt self-hash drifted")
    if value.get("pairwise_disjoint") != {
        "item_ids": True,
        "source_entity_ids": True,
        "component_ids": True,
    }:
        raise PowerRefusal("selection disjointness was not proven")
    development = value.get("development")
    confirmatory = value.get("confirmatory")
    if not isinstance(development, Mapping) or not isinstance(confirmatory, Mapping):
        raise PowerRefusal("selection cohorts are absent")
    _verify_development_block_assignment(development)
    if len(confirmatory.get("item_ids", [])) != 100:
        raise PowerRefusal("confirmatory selection must contain exactly 100 items")
    for cohort, block in (("development", development), ("confirmatory", confirmatory)):
        rows = block.get("selected_rows")
        if not isinstance(rows, list) or canonical_sha256(rows) != block.get(
            "selected_rows_sha256"
        ):
            raise PowerRefusal(f"{cohort} selected-row preimage drifted")
        entries = _selected_entries_unverified(block)
        if [str(entry["row"]["id"]) for entry in entries] != sorted(
            str(item_id) for item_id in block.get("item_ids", [])
        ):
            # Selection rows are stored by dataset order, so compare as sets below.
            if {
                str(entry["row"]["id"]) for entry in entries
            } != set(str(item_id) for item_id in block.get("item_ids", [])):
                raise PowerRefusal(f"{cohort} selected-row identity drifted")
    pages = value.get("source_pages")
    if not isinstance(pages, list) or len(pages) != (
        len(DEVELOPMENT_OFFSETS) + len(CONFIRMATORY_POOL_OFFSETS)
    ):
        raise PowerRefusal("selection source-page inventory drifted")
    for raw_page in pages:
        if not isinstance(raw_page, Mapping):
            raise PowerRefusal("selection source-page entry is malformed")
        rows = raw_page.get("redacted_rows")
        if not isinstance(rows, list) or canonical_sha256(rows) != raw_page.get(
            "redacted_rows_sha256"
        ):
            raise PowerRefusal("selection redacted page hash drifted")
    return declared


def _selected_entries_unverified(block: Mapping[str, object]) -> list[dict[str, object]]:
    rows = block.get("selected_rows")
    if not isinstance(rows, list):
        raise PowerRefusal("selected cohort lacks public row preimages")
    result: list[dict[str, object]] = []
    for raw in rows:
        if not isinstance(raw, Mapping) or set(raw) != {"dataset_row_index", "row"}:
            raise PowerRefusal("selected public row shape drifted")
        row = raw.get("row")
        if not isinstance(row, Mapping) or set(row) != {
            "id", "question", "context", "type"
        }:
            raise PowerRefusal("selected public row allowlist drifted")
        result.append(json.loads(canonical_json(dict(raw))))
    return result


def selected_entries(value: Mapping[str, object], cohort: str) -> list[dict[str, object]]:
    verify_selection_receipt(value)
    block = value.get(cohort)
    if not isinstance(block, Mapping):
        raise PowerRefusal("unknown selected cohort")
    return _selected_entries_unverified(block)


def _decode_gold_selected_block(
    value: Mapping[str, object], cohort: str
) -> list[dict[str, object]]:
    selected = value.get("selected_rows")
    if not isinstance(selected, Mapping) or set(selected) != {
        "development", "confirmatory"
    }:
        raise PowerRefusal("gold-source selected-row inventory drifted")
    block = selected.get(cohort)
    if not isinstance(block, Mapping) or set(block) != {
        "full_rows", "full_rows_sha256"
    }:
        raise PowerRefusal("gold-source selected-row block drifted")
    rows = block.get("full_rows")
    if not isinstance(rows, list):
        raise PowerRefusal("gold-source selected rows are absent")
    if (
        canonical_sha256(rows) != block.get("full_rows_sha256")
    ):
        raise PowerRefusal("gold-source selected-row preimage drifted")
    return [json.loads(canonical_json(dict(row))) for row in rows]


def verify_gold_source_receipt(
    value: Mapping[str, object], selection_receipt: Mapping[str, object]
) -> str:
    selection_sha = verify_selection_receipt(selection_receipt)
    expected = {
        "schema_version", "selection_receipt_sha256", "source_pages",
        "selected_rows", "gold_source_receipt_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != expected:
        raise PowerRefusal("gold-source receipt shape drifted")
    unsigned = dict(value)
    declared = unsigned.pop("gold_source_receipt_sha256", None)
    if (
        value.get("schema_version") != GOLD_SOURCE_SCHEMA
        or value.get("selection_receipt_sha256") != selection_sha
        or not isinstance(declared, str)
        or canonical_sha256(unsigned) != declared
    ):
        raise PowerRefusal("gold-source receipt identity or self-hash drifted")
    pages = value.get("source_pages")
    public_pages = selection_receipt.get("source_pages")
    if not isinstance(pages, list) or not isinstance(public_pages, list):
        raise PowerRefusal("gold-source page inventory is absent")
    public_by_key = {
        (str(page.get("purpose")), int(page.get("offset"))): page
        for page in public_pages
        if isinstance(page, Mapping) and isinstance(page.get("offset"), int)
    }
    entries_by_item: dict[str, dict[str, object]] = {}
    seen_keys: set[tuple[str, int]] = set()
    page_fields = {
        "purpose", "offset", "length", "raw_page_base64", "raw_page_sha256",
        "canonical_page_sha256",
    }
    for page_receipt in pages:
        if not isinstance(page_receipt, Mapping) or set(page_receipt) != page_fields:
            raise PowerRefusal("gold-source page shape drifted")
        purpose = page_receipt.get("purpose")
        offset = page_receipt.get("offset")
        encoded = page_receipt.get("raw_page_base64")
        if (
            not isinstance(purpose, str)
            or isinstance(offset, bool)
            or not isinstance(offset, int)
            or page_receipt.get("length") != 100
            or not isinstance(encoded, str)
        ):
            raise PowerRefusal("gold-source page metadata drifted")
        key = (purpose, offset)
        if key in seen_keys or key not in public_by_key:
            raise PowerRefusal("gold-source page identity repeats or drifted")
        seen_keys.add(key)
        try:
            raw = base64.b64decode(encoded, validate=True)
        except ValueError as error:
            raise PowerRefusal("gold-source page bytes are invalid") from error
        page = _strict_object(raw, "gold-source candidate page")
        if (
            hashlib.sha256(raw).hexdigest() != page_receipt.get("raw_page_sha256")
            or canonical_sha256(page) != page_receipt.get("canonical_page_sha256")
        ):
            raise PowerRefusal("gold-source page preimage drifted")
        rebuilt_public, _projections, _rows = _page_input_bytes(raw, offset)
        if {"purpose": purpose, **rebuilt_public} != dict(public_by_key[key]):
            raise PowerRefusal("gold-source page differs from public redaction")
        for entry in _full_entries_from_page(raw, offset):
            item_id = str(entry["row"]["id"])
            if item_id in entries_by_item:
                raise PowerRefusal("gold-source item identity repeats")
            entries_by_item[item_id] = entry
    if seen_keys != set(public_by_key):
        raise PowerRefusal("gold-source page coverage is incomplete")
    for cohort in ("development", "confirmatory"):
        public_rows = selected_entries(selection_receipt, cohort)
        full_rows = _decode_gold_selected_block(value, cohort)
        expected_full = sorted(
            (entries_by_item[str(row["row"]["id"])] for row in public_rows),
            key=lambda row: int(row["dataset_row_index"]),
        )
        if full_rows != expected_full or [
            _redact_entry(row) for row in full_rows
        ] != public_rows:
            raise PowerRefusal("gold-source selected rows differ from public selection")
    return declared


def evaluator_selected_entries(
    selection_receipt: Mapping[str, object],
    gold_source_receipt: Mapping[str, object],
    cohort: str,
) -> list[dict[str, object]]:
    """Strict evaluator-only accessor for answer-bearing selected rows."""

    if cohort not in {"development", "confirmatory"}:
        raise PowerRefusal("unknown evaluator cohort")
    verify_gold_source_receipt(gold_source_receipt, selection_receipt)
    return _decode_gold_selected_block(gold_source_receipt, cohort)


def _self_hash(value: Mapping[str, object], field: str, label: str) -> str:
    unsigned = dict(value)
    declared = unsigned.pop(field, None)
    if not isinstance(declared, str) or canonical_sha256(unsigned) != declared:
        raise PowerRefusal(f"{label} self-hash drifted")
    return declared


def _normalize_answer(value: str) -> str:
    return " ".join(value.casefold().strip().split())


def derive_development_components(
    *,
    manifest: Mapping[str, object],
    suite: Mapping[str, object],
    gold: Mapping[str, object],
    selection_receipt: Mapping[str, object],
) -> list[dict[str, object]]:
    verify_selection_receipt(selection_receipt)
    development = selection_receipt.get("development")
    if not isinstance(development, Mapping):
        raise PowerRefusal("development selection is absent")
    schedule = development.get("component_schedule")
    manifest_items = manifest.get("items")
    item_runs = suite.get("item_runs")
    gold_rows = gold.get("items")
    if (
        not isinstance(schedule, list)
        or not isinstance(manifest_items, list)
        or not isinstance(item_runs, list)
        or not isinstance(gold_rows, list)
    ):
        raise PowerRefusal("development evidence arrays are absent")
    if (
        manifest.get("mode") != "development"
        or suite.get("mode") != "development"
        or manifest.get("run_id") != suite.get("run_id")
        or manifest.get("run_id") != gold.get("run_id")
    ):
        raise PowerRefusal("development run identity drifted")
    indexed_manifest: dict[str, Mapping[str, object]] = {}
    for raw in manifest_items:
        if not isinstance(raw, Mapping):
            raise PowerRefusal("development manifest item is malformed")
        item_id = str(raw.get("item_id"))
        if not item_id or item_id in indexed_manifest:
            raise PowerRefusal("development manifest item IDs repeat")
        indexed_manifest[item_id] = raw
    selected_item_ids = {str(value) for value in development.get("item_ids", [])}
    if set(indexed_manifest) != selected_item_ids:
        raise PowerRefusal("development manifest differs from frozen selection")

    indexed_runs: dict[str, dict[str, Mapping[str, object]]] = {}
    for raw in item_runs:
        if not isinstance(raw, Mapping):
            raise PowerRefusal("development item run is malformed")
        item_id = str(raw.get("item_id"))
        arm_id = str(raw.get("arm_id"))
        if item_id not in indexed_manifest or arm_id not in (TYPED_ARM, *CONTROLS):
            raise PowerRefusal("development item run identity drifted")
        arms = indexed_runs.setdefault(item_id, {})
        if arm_id in arms:
            raise PowerRefusal("development item-arm run repeats")
        arms[arm_id] = raw
    if set(indexed_runs) != set(indexed_manifest) or any(
        set(arms) != {TYPED_ARM, *CONTROLS} for arms in indexed_runs.values()
    ):
        raise PowerRefusal("development suite does not exactly cover five arms")

    accepted: dict[str, set[str]] = {}
    for raw in gold_rows:
        if not isinstance(raw, Mapping):
            raise PowerRefusal("development gold row is malformed")
        item_id = str(raw.get("item_id"))
        answers = raw.get("accepted_answers")
        if (
            item_id in accepted
            or not isinstance(answers, list)
            or not answers
            or any(not isinstance(value, str) or not value for value in answers)
        ):
            raise PowerRefusal("development gold identity or answers drifted")
        accepted[item_id] = {_normalize_answer(value) for value in answers}
    if set(accepted) != set(indexed_manifest):
        raise PowerRefusal("development gold and manifest identities differ")

    item_scores: dict[str, dict[str, float]] = {}
    for item_id, arms in indexed_runs.items():
        item_scores[item_id] = {}
        for arm, run in arms.items():
            answer = run.get("answer")
            if not isinstance(answer, Mapping):
                raise PowerRefusal("development answer envelope is absent")
            item_scores[item_id][arm] = float(
                answer.get("abstain") is False
                and _normalize_answer(str(answer.get("answer", ""))) in accepted[item_id]
            )

    components: list[dict[str, object]] = []
    seen_components: set[str] = set()
    seen_entities: set[str] = set()
    for raw in schedule:
        if not isinstance(raw, Mapping):
            raise PowerRefusal("development component schedule is malformed")
        component_id = str(raw.get("component_id"))
        item_ids = sorted(str(value) for value in raw.get("item_ids", []))
        source_entities = sorted(str(value) for value in raw.get("source_entity_ids", []))
        if (
            not _SHA256.fullmatch(component_id)
            or component_id in seen_components
            or not item_ids
            or not source_entities
            or len(set(item_ids)) != len(item_ids)
            or len(set(source_entities)) != len(source_entities)
            or not set(item_ids) <= set(indexed_manifest)
            or seen_entities & set(source_entities)
        ):
            raise PowerRefusal("development component identity or partition drifted")
        seen_components.add(component_id)
        seen_entities.update(source_entities)
        derived_entities = sorted(
            {
                str(candidate["source_entity_id"])
                for item_id in item_ids
                for candidate in indexed_manifest[item_id].get("candidates", [])
            }
        )
        if source_entities != derived_entities:
            raise PowerRefusal("development component source preimage drifted")
        derived_component = canonical_sha256(
            {
                "schema_version": "hswm-source-entity-connected-component/v1",
                "source_entity_ids": source_entities,
            }
        )
        if component_id != derived_component or any(
            indexed_manifest[item_id].get("component_id") != component_id
            for item_id in item_ids
        ):
            raise PowerRefusal("development component was not source-derived")
        if raw.get("cluster_size") != len(item_ids):
            raise PowerRefusal("development component cluster size drifted")
        components.append(
            {
                "component_id": component_id,
                "item_ids": item_ids,
                "source_entity_ids": source_entities,
                "cluster_size": len(item_ids),
                "seed_block": int(raw["seed_block"]),
                "carryover_block": int(raw["carryover_block"]),
                "contrasts": {
                    arm: sum(
                        item_scores[item_id][TYPED_ARM] - item_scores[item_id][arm]
                        for item_id in item_ids
                    )
                    / float(len(item_ids))
                    for arm in CONTROLS
                },
            }
        )
    if (
        len(components) != DEVELOPMENT_COMPONENTS
        or set(item_id for component in components for item_id in component["item_ids"])
        != set(indexed_manifest)
    ):
        raise PowerRefusal("development components do not exactly cover the pilot")
    return sorted(components, key=lambda value: str(value["component_id"]))


def _load_judge_core(path: Path):
    spec = importlib.util.spec_from_file_location("hswm_f1_r8_frozen_judge", path)
    if spec is None or spec.loader is None:
        raise PowerRefusal("cannot load frozen independent judge")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as error:
        raise PowerRefusal(f"cannot import frozen independent judge: {error}") from error
    for name in ("judge_core_sha256", "_recompute_power_characteristics"):
        if not callable(getattr(module, name, None)):
            raise PowerRefusal(f"frozen judge lacks {name}")
    return module


def _verify_deployment_environment_binding(
    labels: object,
    *,
    execution_lock: Mapping[str, object],
    manifest: Mapping[str, object],
) -> dict[str, object]:
    expected_fields = {
        "spool_endpoint",
        "model_upstream_endpoint",
        "model_deployment_receipt_sha256",
        "model",
        "model_revision",
        "run_id",
        "hswm_commit",
        "symposium_commit",
    }
    policy = execution_lock.get("execution_policy")
    deployment_sha = execution_lock.get("deployment_receipt_sha256")
    hswm_commit = execution_lock.get("hswm_commit")
    model_revision = manifest.get("model_revision")
    if (
        not isinstance(labels, Mapping)
        or set(labels) != expected_fields
        or not isinstance(policy, Mapping)
        or labels.get("spool_endpoint") != policy.get("endpoint")
        or labels.get("model_upstream_endpoint")
        != execution_lock.get("upstream_endpoint")
        or labels.get("model_deployment_receipt_sha256") != deployment_sha
        or labels.get("model") != manifest.get("model")
        or execution_lock.get("model") != manifest.get("model")
        or execution_lock.get("served_model") != manifest.get("model")
        or labels.get("model_revision") != model_revision
        or execution_lock.get("model_revision") != model_revision
        or not isinstance(model_revision, str)
        or _COMMIT.fullmatch(model_revision) is None
        or not isinstance(deployment_sha, str)
        or _SHA256.fullmatch(deployment_sha) is None
        or execution_lock.get("deployment_id")
        != f"hswm:model_deployment:v2:{deployment_sha}"
        or labels.get("run_id") != manifest.get("run_id")
        or labels.get("hswm_commit") != hswm_commit
        or not isinstance(hswm_commit, str)
        or _COMMIT.fullmatch(hswm_commit) is None
        or not isinstance(labels.get("symposium_commit"), str)
        or _COMMIT.fullmatch(str(labels.get("symposium_commit"))) is None
    ):
        raise PowerRefusal("environment deployment semantic binding drifted")
    return dict(labels)


def build_power_receipt(
    *,
    manifest: Mapping[str, object],
    execution_lock: Mapping[str, object],
    public_source_receipt: Mapping[str, object],
    selection_receipt: Mapping[str, object],
    gold_source_receipt: Mapping[str, object],
    prior_exposure_receipt: Mapping[str, object],
    suite: Mapping[str, object],
    evaluator_receipt: Mapping[str, object],
    gold: Mapping[str, object],
    db_genesis_receipt: Mapping[str, object],
    environment_dependency_bundle: Mapping[str, object],
    judge_core_path: Path,
) -> dict[str, object]:
    from prom_search_hswm.prom9_f1_r8_runner import verify_suite_v3_without_gold
    from prom_search_hswm.prom9_f1_r8_source import (
        EVALUATOR_SEAL_SCHEMA,
        GOLD_SCHEMA,
        SOURCE_RECEIPT_SCHEMA,
        verify_evaluator_seal,
        verify_public_source_receipt,
    )
    from prom_search_hswm.prom_f1_function_network import _verify_token_blocks

    selection_sha = verify_selection_receipt(selection_receipt)
    prior_sha = verify_prior_exposure_receipt(prior_exposure_receipt)
    if selection_receipt.get("prior_exposure_receipt_sha256") != prior_sha:
        raise PowerRefusal("selection is not bound to the supplied prior exposure receipt")
    suite_sha = verify_suite_v3_without_gold(suite)
    execution_lock_sha = _self_hash(
        execution_lock, "lock_sha256", "development execution lock"
    )
    if canonical_sha256(manifest) != suite.get("manifest_sha256"):
        raise PowerRefusal("development manifest differs from terminal suite")
    source_sha = verify_public_source_receipt(public_source_receipt)
    gold_source_sha = verify_gold_source_receipt(
        gold_source_receipt, selection_receipt
    )
    evaluator_sha = verify_evaluator_seal(evaluator_receipt)
    genesis_sha = _self_hash(db_genesis_receipt, "genesis_sha256", "DB genesis")
    compatibility_root = verify_preimage_bundle(
        environment_dependency_bundle, verify_live=True
    )
    environment = environment_dependency_bundle.get("environment_receipt")
    dependencies = environment_dependency_bundle.get("dependency_receipt")
    if not isinstance(environment, Mapping) or not isinstance(dependencies, Mapping):
        raise PowerRefusal("environment/dependency bundle entries are absent")
    environment_sha = verify_environment_receipt(environment, verify_live=True)
    dependency_sha = verify_dependency_receipt(dependencies, verify_live=True)
    bundle_sha = environment_dependency_bundle.get("bundle_sha256")
    if not isinstance(bundle_sha, str) or _SHA256.fullmatch(bundle_sha) is None:
        raise PowerRefusal("environment/dependency bundle hash is invalid")
    gold_sha = canonical_sha256(gold)
    manifest_items = manifest.get("items")
    source_rows = public_source_receipt.get("rows")
    if not isinstance(manifest_items, list) or not isinstance(source_rows, list):
        raise PowerRefusal("development manifest/source rows are absent")
    manifest_by_id = {
        str(item.get("item_id")): item
        for item in manifest_items
        if isinstance(item, Mapping)
    }
    source_by_id = {
        str(row.get("item_id")): row for row in source_rows if isinstance(row, Mapping)
    }
    if len(manifest_by_id) != len(manifest_items) or set(source_by_id) != set(manifest_by_id):
        raise PowerRefusal("development source receipt and manifest identities differ")
    for item_id, item in manifest_by_id.items():
        observed_entities = _manifest_source_entity_ids(item)
        if source_by_id[item_id].get("source_entity_ids") != observed_entities:
            raise PowerRefusal("development source-entity binding drifted")
    cohort_root = canonical_sha256(sorted(manifest_by_id))
    full_entries = evaluator_selected_entries(
        selection_receipt, gold_source_receipt, "development"
    )
    expected_gold = {
        "schema_version": GOLD_SCHEMA,
        "run_id": manifest.get("run_id"),
        "items": [
            {
                "item_id": str(entry["row"]["id"]),
                "accepted_answers": [entry["row"]["answer"]],
            }
            for entry in full_entries
        ],
    }
    labels = environment.get("labels")
    dependency_files = dependencies.get("files")
    _verify_deployment_environment_binding(
        labels, execution_lock=execution_lock, manifest=manifest
    )
    if (
        not isinstance(dependency_files, Mapping)
        or set(dependency_files) != set(REQUIRED_DEPENDENCY_NAMES)
    ):
        raise PowerRefusal("environment/dependency semantic binding drifted")
    if (
        public_source_receipt.get("schema_version") != SOURCE_RECEIPT_SCHEMA
        or gold.get("schema_version") != GOLD_SCHEMA
        or dict(gold) != expected_gold
        or evaluator_receipt.get("run_id") != manifest.get("run_id")
        or gold.get("run_id") != manifest.get("run_id")
        or suite.get("measurement_lock_sha256") != execution_lock_sha
        or execution_lock.get("manifest_sha256") != canonical_sha256(manifest)
        or execution_lock.get("selection_receipt_sha256") != selection_sha
        or execution_lock.get("prior_exposure_receipt_sha256") != prior_sha
        or execution_lock.get("public_source_receipt_sha256") != source_sha
        or execution_lock.get("gold_source_receipt_sha256") != gold_source_sha
        or execution_lock.get("gold_sha256") != gold_sha
        or execution_lock.get("evaluator_receipt_sha256") != evaluator_sha
        or execution_lock.get("db_genesis_receipt_sha256") != genesis_sha
        or execution_lock.get("environment_receipt_sha256") != environment_sha
        or execution_lock.get("dependency_receipt_sha256") != dependency_sha
        or execution_lock.get("environment_dependency_compatibility_root_sha256")
        != compatibility_root
        or execution_lock.get("environment_dependency_bundle_sha256") != bundle_sha
        or any(
            suite.get(field) != execution_lock.get(field)
            for field in (
                "upstream_endpoint",
                "deployment_receipt_sha256",
                "deployment_id",
                "served_model",
                "model_revision",
            )
        )
        or evaluator_receipt.get("cohort_root_sha256") != cohort_root
        or evaluator_receipt.get("raw_source_sha256")
        != public_source_receipt.get("raw_source_sha256")
        or evaluator_receipt.get("public_selection_receipt_sha256") != selection_sha
        or evaluator_receipt.get("public_source_receipt_sha256") != source_sha
        or evaluator_receipt.get("gold_source_receipt_sha256") != gold_source_sha
        or evaluator_receipt.get("gold_sha256") != gold_sha
        or evaluator_receipt.get("schema_version") != EVALUATOR_SEAL_SCHEMA
        or public_source_receipt.get("public_selection_receipt_sha256") != selection_sha
        or suite.get("gold_opened") is not False
        or suite.get("scientific_verdict_emitted") is not False
    ):
        raise PowerRefusal("development evidence identity drifted")
    parity = suite.get("token_parity")
    if not isinstance(parity, Mapping) or parity.get("all_within_tolerance") is not True:
        raise PowerRefusal("development token parity did not pass")
    transport = suite.get("transport_audit")
    runs = suite.get("item_runs")
    if not isinstance(transport, Mapping) or not isinstance(runs, list):
        raise PowerRefusal("development terminal transport evidence is absent")
    _verify_token_blocks(suite, runs)
    execution_policy = execution_lock.get("execution_policy")
    if not isinstance(execution_policy, Mapping):
        raise PowerRefusal("development execution policy is absent")
    if (
        transport.get("call_count") != len(runs) * 3
        or transport.get("item_run_count") != len(runs)
        or transport.get("status_counts") != {"ACCEPTED": len(runs) * 3}
        or suite.get("max_workers") != execution_policy.get("max_workers")
    ):
        raise PowerRefusal("development terminal counts or execution policy drifted")
    components = derive_development_components(
        manifest=manifest,
        suite=suite,
        gold=gold,
        selection_receipt=selection_receipt,
    )
    prior = prior_exposure_receipt.get("aggregate")
    if not isinstance(prior, Mapping):
        raise PowerRefusal("prior exposure aggregate is absent")
    if (
        {value["component_id"] for value in components}
        & set(prior.get("prior_component_ids", []))
        or {
            entity
            for component in components
            for entity in component["source_entity_ids"]
        }
        & set(prior.get("prior_source_entity_ids", []))
        or {
            item_id
            for component in components
            for item_id in component["item_ids"]
        }
        & set(prior.get("prior_item_ids", []))
    ):
        raise PowerRefusal("development evidence overlaps prior measured exposure")

    plan = {
        "schema_version": POWER_SIMULATOR_SCHEMA,
        "trials": TRIALS,
        "master_seed": SELECTION_SEED,
        "selected_cluster_count": SELECTED_CLUSTERS,
        "selection_method": "complete_seed_block_without_replacement/v1",
        "mde": 0.05,
        "target_power": 0.80,
        "scenarios": list(POWER_SCENARIOS),
    }
    analysis = {
        "schema_version": POWER_DEVELOPMENT_SCHEMA,
        "development_components": components,
        "simulation_plan": plan,
    }
    evidence = {
        "schema_version": POWER_EVIDENCE_SCHEMA,
        "manifest": dict(manifest),
        "execution_lock": dict(execution_lock),
        "public_source_receipt": dict(public_source_receipt),
        "selection_receipt": dict(selection_receipt),
        "gold_source_receipt": dict(gold_source_receipt),
        "prior_exposure_receipt": dict(prior_exposure_receipt),
        "suite": dict(suite),
        "evaluator_receipt": dict(evaluator_receipt),
        "gold": dict(gold),
        "db_genesis_receipt": dict(db_genesis_receipt),
        "environment_dependency_bundle": dict(environment_dependency_bundle),
        "artifact_receipts": {
            "selection_receipt_sha256": selection_sha,
            "prior_exposure_receipt_sha256": prior_sha,
            "execution_lock_sha256": execution_lock_sha,
            "public_source_receipt_sha256": source_sha,
            "gold_source_receipt_sha256": gold_source_sha,
            "suite_receipt_sha256": suite_sha,
            "evaluator_receipt_sha256": evaluator_sha,
            "db_genesis_receipt_sha256": genesis_sha,
            "gold_sha256": gold_sha,
            "environment_receipt_sha256": environment_sha,
            "dependency_receipt_sha256": dependency_sha,
            "environment_dependency_compatibility_root_sha256": compatibility_root,
            "environment_dependency_bundle_sha256": bundle_sha,
        },
    }
    judge_core_file_sha = hashlib.sha256(Path(judge_core_path).read_bytes()).hexdigest()
    if (
        execution_lock.get("judge_core_file_sha256") != judge_core_file_sha
        or not isinstance(dependency_files, Mapping)
        or not isinstance(dependency_files.get("judge_core"), Mapping)
        or dependency_files["judge_core"].get("sha256") != judge_core_file_sha
    ):
        raise PowerRefusal("frozen judge file differs from the development lock")
    judge = _load_judge_core(judge_core_path)
    judge_core_sha = str(judge.judge_core_sha256(judge_core_path))
    if (
        judge_core_sha != execution_lock.get("judge_core_sha256")
        or hashlib.sha256(Path(judge_core_path).read_bytes()).hexdigest()
        != judge_core_file_sha
    ):
        raise PowerRefusal("frozen judge semantics changed after development lock")
    characteristics = judge._recompute_power_characteristics(
        components, plan, bootstrap=BOOTSTRAP
    )
    unsigned = {
        "schema_version": POWER_RECEIPT_SCHEMA,
        "analysis_input": analysis,
        "development_evidence": evidence,
        "development_evidence_sha256": canonical_sha256(evidence),
        "development_data_sha256": canonical_sha256(components),
        "simulator_sha256": judge_core_sha,
        "judge_core_sha256": judge_core_sha,
        "inference_unit": "component_cluster_macro",
        "selected_method": "paired_cluster_percentile_bootstrap_v1",
        "minimum_clusters": SELECTED_CLUSTERS,
        "operating_characteristics": characteristics,
    }
    return {**unsigned, "receipt_sha256": canonical_sha256(unsigned)}


def _page_arg(value: str) -> tuple[int, Path]:
    try:
        offset, path = value.split(":", 1)
        return int(offset), Path(path)
    except (ValueError, TypeError) as error:
        raise argparse.ArgumentTypeError("page must be OFFSET:PATH") from error


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    select = subparsers.add_parser("select")
    select.add_argument("--prior-exposure-receipt", type=Path, required=True)
    select.add_argument("--development-page", action="append", type=_page_arg, required=True)
    select.add_argument("--confirmatory-page", action="append", type=_page_arg, required=True)
    select.add_argument("--output", type=Path, required=True)
    select.add_argument("--gold-source-output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command != "select":
            raise PowerRefusal("unsupported command")
        prior_raw = _read_private_bytes(args.prior_exposure_receipt)
        prior = _strict_object(prior_raw, "prior-exposure receipt")
        development = dict(args.development_page)
        confirmatory = dict(args.confirmatory_page)
        if len(development) != len(args.development_page) or len(confirmatory) != len(args.confirmatory_page):
            raise PowerRefusal("duplicate page argument")
        if args.output.resolve() == args.gold_source_output.resolve():
            raise PowerRefusal("public and gold-source outputs must be distinct")
        receipt, gold_source = build_selection_receipts(
            prior_receipt=prior,
            development_pages=development,
            confirmatory_pages=confirmatory,
        )
        verify_selection_receipt(receipt)
        verify_gold_source_receipt(gold_source, receipt)
        write_private_once(args.gold_source_output, gold_source)
        write_private_once(args.output, receipt)
        print(
            json.dumps(
                {
                    "status": "FROZEN_BEFORE_MODEL_CALLS",
                    "selection_receipt_sha256": receipt["selection_receipt_sha256"],
                    "development_components": len(receipt["development"]["component_schedule"]),
                    "development_items": len(receipt["development"]["item_ids"]),
                    "confirmatory_components": len(receipt["confirmatory"]["component_schedule"]),
                    "confirmatory_items": len(receipt["confirmatory"]["item_ids"]),
                    "pairwise_disjoint": receipt["pairwise_disjoint"],
                },
                sort_keys=True,
            )
        )
        return 0
    except Exception:
        print(json.dumps({"status": "REFUSED"}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BOOTSTRAP",
    "CONFIRMATORY_POOL_OFFSETS",
    "DEVELOPMENT_OFFSETS",
    "PowerRefusal",
    "GOLD_SOURCE_SCHEMA",
    "SELECTION_SCHEMA",
    "build_selection_receipt",
    "build_selection_receipts",
    "evaluator_selected_entries",
    "replay_selection_receipt",
    "selected_entries",
    "verify_gold_source_receipt",
    "verify_selection_receipt",
]
