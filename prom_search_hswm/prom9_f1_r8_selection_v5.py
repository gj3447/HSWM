#!/usr/bin/env python3
"""Freeze the outcome-blind F1 r8 C-recontract cohorts (selection v5).

Cohort-expansion generation ratified 2026-08-05: development 800 components
(200 equal seed blocks of four) and confirmatory 800 complete singleton
components, selected from FRESH Dataset Viewer pages only (offsets disjoint
from every v3/v4 pool page).  The exposure boundary is the v4 boundary
(prior-exposure receipt + successor exposure set) EXTENDED with the
predecessor selection receipt's development AND confirmatory 3-axis blocks,
because the predecessor development gold was opened by completed t2/t3b runs
and the predecessor confirmatory gold was staged on disk.

Selection reads only Dataset Viewer IDs/questions/context/type.  The public
v5 receipt contains only redacted rows; answer-bearing preimages live in the
evaluator-only gold-source receipt, exactly as in v4.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from prom_search_hswm.hswm_typed_ports import canonical_sha256
from prom_search_hswm.prom9_f1_prior_exposure import (
    _assign_components,
    _read_private_bytes,
    _strict_object,
    merge_exposure_boundaries,
    verify_f1_r8_successor_exposure_set,
    verify_prior_exposure_receipt,
    write_private_once,
)
from prom_search_hswm.prom9_f1_r8_power import (
    GOLD_SOURCE_SCHEMA,
    PowerRefusal,
    _SHA256,
    _block_key,
    _component_key,
    _component_overlaps_boundary,
    _full_entries_from_page,
    _gold_selected_block,
    _page_input_bytes,
    _page_input_redacted,
    _redact_entry,
    _selected_entries_unverified,
    _selected_rows_block,
    _verify_disjoint,
    verify_selection_receipt as verify_predecessor_selection_receipt,
)


SELECTION_SCHEMA_V5 = "hswm-prom9-f1-r8-cohort-selection/v5"
DEVELOPMENT_COMPONENTS_V5 = 800
SEED_BLOCKS_V5 = 200
COMPONENTS_PER_BLOCK_V5 = 4
CONFIRMATORY_ITEMS_V5 = 800
DEV_PURPOSE_V5 = "development_power_c800"
CONF_PURPOSE_V5 = "confirmatory_c800"
# Every page offset ever used by the v3/v4 pools; v5 pools must be fresh.
HISTORICAL_POOL_OFFSETS = frozenset(
    {104, 204, 304, 404, 504, 604, 704, 804, 904, 1004, 1104, 1204, 1304, 1404}
)


def _verify_offset_grid(
    development_offsets: Sequence[int], confirmatory_offsets: Sequence[int]
) -> None:
    dev = list(development_offsets)
    conf = list(confirmatory_offsets)
    for label, offsets in (("development", dev), ("confirmatory", conf)):
        if not offsets or len(set(offsets)) != len(offsets):
            raise PowerRefusal(f"v5 {label} offsets are empty or repeat")
        for offset in offsets:
            if isinstance(offset, bool) or not isinstance(offset, int):
                raise PowerRefusal(f"v5 {label} offset is not an integer")
            if offset % 100 != 4:
                raise PowerRefusal(
                    f"v5 {label} offset breaks the Dataset Viewer page grid"
                )
            if offset in HISTORICAL_POOL_OFFSETS:
                raise PowerRefusal(
                    f"v5 {label} offset reuses a historical v3/v4 pool page"
                )
    if set(dev) & set(conf):
        raise PowerRefusal("v5 development and confirmatory pool pages overlap")


def _predecessor_boundary(
    predecessor: Mapping[str, object],
) -> tuple[str, dict[str, set[str]]]:
    """Verify the predecessor selection receipt and lift its 3-axis blocks.

    Both cohorts are lifted: predecessor development gold was opened by the
    completed t2/t3b development runs, and predecessor confirmatory gold was
    staged on disk during the sealed-v2 stage-1 attempt.  All of it is
    therefore forbidden for every v5 cohort.
    """

    predecessor_sha = verify_predecessor_selection_receipt(predecessor)
    boundary: dict[str, set[str]] = {
        "item_ids": set(),
        "source_entity_ids": set(),
        "component_ids": set(),
    }
    for cohort in ("development", "confirmatory"):
        block = predecessor.get(cohort)
        if not isinstance(block, Mapping):
            raise PowerRefusal("predecessor selection cohort is absent")
        for axis in ("item_ids", "source_entity_ids", "component_ids"):
            values = block.get(axis)
            if not isinstance(values, list) or not values:
                raise PowerRefusal("predecessor selection axis is malformed")
            boundary[axis].update(str(value) for value in values)
    return predecessor_sha, boundary


def _build_selection_receipt_v5(
    *,
    prior_receipt: Mapping[str, object],
    successor_exposure_set: Mapping[str, object],
    predecessor_selection: Mapping[str, object],
    development_pages: Mapping[int, object],
    confirmatory_pages: Mapping[int, object],
    page_loader,
    development_components: int = DEVELOPMENT_COMPONENTS_V5,
    confirmatory_items: int = CONFIRMATORY_ITEMS_V5,
) -> dict[str, object]:
    if development_components % COMPONENTS_PER_BLOCK_V5:
        raise PowerRefusal("v5 development components do not form equal seed blocks")
    seed_blocks = development_components // COMPONENTS_PER_BLOCK_V5

    prior_sha = verify_prior_exposure_receipt(prior_receipt)
    aborted_sha = verify_f1_r8_successor_exposure_set(successor_exposure_set)
    exposure_boundary = merge_exposure_boundaries(
        prior_receipt, successor_exposure_set
    )
    if (
        exposure_boundary.get("prior_exposure_receipt_sha256") != prior_sha
        or exposure_boundary.get("aborted_attempt_exposure_receipt_sha256")
        != aborted_sha
    ):
        raise PowerRefusal("merged exposure boundary identity drifted")
    predecessor_sha, predecessor_boundary = _predecessor_boundary(
        predecessor_selection
    )

    development_offsets = sorted(int(value) for value in development_pages)
    confirmatory_offsets = sorted(int(value) for value in confirmatory_pages)
    _verify_offset_grid(development_offsets, confirmatory_offsets)

    exposed = {
        "item_ids": sorted(
            {str(v) for v in exposure_boundary["item_ids"]}
            | predecessor_boundary["item_ids"]
        ),
        "source_entity_ids": sorted(
            {str(v) for v in exposure_boundary["source_entity_ids"]}
            | predecessor_boundary["source_entity_ids"]
        ),
        "component_ids": sorted(
            {str(v) for v in exposure_boundary["component_ids"]}
            | predecessor_boundary["component_ids"]
        ),
    }

    page_receipts: list[dict[str, object]] = []
    development_rows: list[dict[str, object]] = []
    development_entries: list[dict[str, object]] = []
    for offset in development_offsets:
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
        if not _component_overlaps_boundary(component, exposed)
    ]
    if len(eligible_dev) < development_components:
        raise PowerRefusal(
            "v5 development pool has fewer prior-fresh components than the "
            "ratified cohort"
        )
    development_selected = sorted(
        eligible_dev,
        key=lambda value: _component_key(str(value["component_id"]), DEV_PURPOSE_V5),
    )[:development_components]
    if not (
        {len(component["item_ids"]) for component in development_selected} & {1}
    ) or not any(
        len(component["item_ids"]) > 1 for component in development_selected
    ):
        raise PowerRefusal("v5 development selection lacks singleton/multi variation")
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
                "seed_block": rank // COMPONENTS_PER_BLOCK_V5,
                "carryover_block": rank % COMPONENTS_PER_BLOCK_V5,
            }
        )
    if (
        len(development_schedule) != development_components
        or {int(value["seed_block"]) for value in development_schedule}
        != set(range(seed_blocks))
        or any(
            {
                int(value["carryover_block"])
                for value in development_schedule
                if value["seed_block"] == block
            }
            != set(range(COMPONENTS_PER_BLOCK_V5))
            for block in range(seed_blocks)
        )
    ):
        raise PowerRefusal("v5 development block assignment drifted")
    dev_entries_by_item = {
        str(entry["row"]["id"]): entry for entry in development_entries
    }
    development_block = _selected_rows_block(
        development_schedule, dev_entries_by_item
    )

    confirmatory_rows: list[dict[str, object]] = []
    confirmatory_entries: list[dict[str, object]] = []
    for offset in confirmatory_offsets:
        page_receipt, projections, entries = page_loader(
            confirmatory_pages[offset], offset
        )
        page_receipts.append({"purpose": "confirmatory_pool", **page_receipt})
        confirmatory_rows.extend(projections)
        confirmatory_entries.extend(entries)
    confirmatory_items_pool = [dict(row) for row in confirmatory_rows]
    confirmatory_components = _assign_components(confirmatory_items_pool)
    confirmatory_forbidden = {
        "item_ids": set(exposed["item_ids"]) | set(development_block["item_ids"]),
        "source_entity_ids": set(exposed["source_entity_ids"])
        | set(development_block["source_entity_ids"]),
        "component_ids": set(exposed["component_ids"])
        | set(development_block["component_ids"]),
    }
    eligible_confirmatory = [
        component
        for component in confirmatory_components
        if len(component["item_ids"]) == 1
        and not _component_overlaps_boundary(component, confirmatory_forbidden)
    ]
    if len(eligible_confirmatory) < confirmatory_items:
        raise PowerRefusal(
            "v5 confirmatory pool has fewer fresh singleton components than the "
            "ratified cohort"
        )
    confirmatory_selected = sorted(
        eligible_confirmatory,
        key=lambda value: _component_key(str(value["component_id"]), CONF_PURPOSE_V5),
    )[:confirmatory_items]
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
    exposed_lists = {axis: sorted(values) for axis, values in exposed.items()}
    _verify_disjoint(exposed_lists, development_block, "exposure/development")
    _verify_disjoint(exposed_lists, confirmatory_block, "exposure/confirmatory")
    _verify_disjoint(development_block, confirmatory_block, "development/confirmatory")
    if (
        len(confirmatory_block["item_ids"]) != confirmatory_items
        or len(confirmatory_schedule) != confirmatory_items
    ):
        raise PowerRefusal(
            "v5 confirmatory selection is not exactly the ratified complete cohort"
        )

    policy = {
        "selection_seed": 20260728,
        "development_pool_offsets": development_offsets,
        "confirmatory_pool_offsets": confirmatory_offsets,
        "page_length": 100,
        "development_components": development_components,
        "seed_blocks": seed_blocks,
        "components_per_seed_block": COMPONENTS_PER_BLOCK_V5,
        "confirmatory_items": confirmatory_items,
        "confirmatory_component_size": 1,
        "selection_key_schema": "hswm-f1-r8-component-selection/v1",
        "block_assignment_schema": "hswm-f1-r8-power-block-assignment/v1",
        "selection_purposes": {
            "development": DEV_PURPOSE_V5,
            "confirmatory": CONF_PURPOSE_V5,
        },
        "pool_freshness": "offsets_disjoint_from_all_v3_v4_pool_pages",
        "predecessor_exclusion_cohorts": ["development", "confirmatory"],
        "exclusion_dimensions": [
            "item_ids",
            "source_entity_ids",
            "component_ids",
        ],
        "derived_fields": ["id", "question", "context", "type"],
        "answers_used_for_selection": False,
    }
    unsigned = {
        "schema_version": SELECTION_SCHEMA_V5,
        "prior_exposure_receipt_sha256": prior_sha,
        "aborted_attempt_exposure_receipt_sha256": aborted_sha,
        "predecessor_selection_receipt_sha256": predecessor_sha,
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


def _verify_development_block_assignment_v5(
    development: Mapping[str, object], *, development_components: int
) -> None:
    schedule = development.get("component_schedule")
    if not isinstance(schedule, list) or len(schedule) != development_components:
        raise PowerRefusal(
            "v5 development selection component count differs from its policy"
        )
    rows: dict[str, Mapping[str, object]] = {}
    for raw in schedule:
        if not isinstance(raw, Mapping):
            raise PowerRefusal("v5 development component schedule is malformed")
        component_id = raw.get("component_id")
        if (
            not isinstance(component_id, str)
            or _SHA256.fullmatch(component_id) is None
            or component_id in rows
        ):
            raise PowerRefusal("v5 development component schedule identity drifted")
        rows[component_id] = raw
    ordered = sorted(rows, key=_block_key)
    if [str(raw.get("component_id")) for raw in schedule] != ordered:
        raise PowerRefusal("v5 development block order drifted")
    for rank, component_id in enumerate(ordered):
        raw = rows[component_id]
        observed = (raw.get("seed_block"), raw.get("carryover_block"))
        expected = (
            rank // COMPONENTS_PER_BLOCK_V5,
            rank % COMPONENTS_PER_BLOCK_V5,
        )
        if (
            any(
                isinstance(value, bool) or not isinstance(value, int)
                for value in observed
            )
            or observed != expected
        ):
            raise PowerRefusal("v5 development block assignment drifted")


def verify_selection_receipt_v5(value: Mapping[str, object]) -> str:
    if value.get("schema_version") != SELECTION_SCHEMA_V5:
        raise PowerRefusal("v5 selection receipt schema drifted")
    unsigned = dict(value)
    declared = unsigned.pop("selection_receipt_sha256", None)
    if not isinstance(declared, str) or canonical_sha256(unsigned) != declared:
        raise PowerRefusal("v5 selection receipt self-hash drifted")
    if any(
        not isinstance(value.get(field), str)
        or _SHA256.fullmatch(str(value.get(field))) is None
        for field in (
            "prior_exposure_receipt_sha256",
            "aborted_attempt_exposure_receipt_sha256",
            "predecessor_selection_receipt_sha256",
        )
    ):
        raise PowerRefusal("v5 selection exposure/predecessor binding drifted")
    if value.get("pairwise_disjoint") != {
        "item_ids": True,
        "source_entity_ids": True,
        "component_ids": True,
    }:
        raise PowerRefusal("v5 selection disjointness was not proven")
    policy = value.get("selection_policy")
    if not isinstance(policy, Mapping):
        raise PowerRefusal("v5 selection policy is absent")
    development_components = policy.get("development_components")
    confirmatory_items = policy.get("confirmatory_items")
    if (
        isinstance(development_components, bool)
        or not isinstance(development_components, int)
        or isinstance(confirmatory_items, bool)
        or not isinstance(confirmatory_items, int)
    ):
        raise PowerRefusal("v5 selection policy scale is malformed")
    dev_offsets = policy.get("development_pool_offsets")
    conf_offsets = policy.get("confirmatory_pool_offsets")
    if not isinstance(dev_offsets, list) or not isinstance(conf_offsets, list):
        raise PowerRefusal("v5 selection policy offsets are absent")
    _verify_offset_grid(dev_offsets, conf_offsets)
    development = value.get("development")
    confirmatory = value.get("confirmatory")
    if not isinstance(development, Mapping) or not isinstance(confirmatory, Mapping):
        raise PowerRefusal("v5 selection cohorts are absent")
    _verify_development_block_assignment_v5(
        development, development_components=development_components
    )
    if len(confirmatory.get("item_ids", [])) != confirmatory_items:
        raise PowerRefusal(
            "v5 confirmatory selection differs from its policy item count"
        )
    for cohort, block in (("development", development), ("confirmatory", confirmatory)):
        rows = block.get("selected_rows")
        if not isinstance(rows, list) or canonical_sha256(rows) != block.get(
            "selected_rows_sha256"
        ):
            raise PowerRefusal(f"v5 {cohort} selected-row preimage drifted")
        entries = _selected_entries_unverified(block)
        if {str(entry["row"]["id"]) for entry in entries} != set(
            str(item_id) for item_id in block.get("item_ids", [])
        ):
            raise PowerRefusal(f"v5 {cohort} selected-row identity drifted")
    pages = value.get("source_pages")
    if not isinstance(pages, list) or len(pages) != (
        len(dev_offsets) + len(conf_offsets)
    ):
        raise PowerRefusal("v5 selection source-page inventory drifted")
    seen_pages: set[tuple[str, int]] = set()
    for raw_page in pages:
        if not isinstance(raw_page, Mapping):
            raise PowerRefusal("v5 selection source-page entry is malformed")
        purpose = raw_page.get("purpose")
        offset = raw_page.get("offset")
        if purpose == "development":
            expected_offsets = dev_offsets
        elif purpose == "confirmatory_pool":
            expected_offsets = conf_offsets
        else:
            raise PowerRefusal("v5 selection source-page purpose drifted")
        if isinstance(offset, bool) or offset not in expected_offsets:
            raise PowerRefusal("v5 selection source-page offset drifted")
        key = (str(purpose), int(offset))
        if key in seen_pages:
            raise PowerRefusal("v5 selection source-page offset repeats")
        seen_pages.add(key)
        rows = raw_page.get("redacted_rows")
        if not isinstance(rows, list) or canonical_sha256(rows) != raw_page.get(
            "redacted_rows_sha256"
        ):
            raise PowerRefusal("v5 selection redacted page hash drifted")
    return declared


def replay_selection_receipt_v5(
    value: Mapping[str, object],
    *,
    prior_receipt: Mapping[str, object],
    successor_exposure_set: Mapping[str, object],
    predecessor_selection: Mapping[str, object],
) -> str:
    """Replay the v5 selector from public redacted pages only."""

    declared = verify_selection_receipt_v5(value)
    policy = value["selection_policy"]
    development: dict[int, list[dict[str, object]]] = {}
    confirmatory: dict[int, list[dict[str, object]]] = {}
    for raw_page in value["source_pages"]:
        offset = int(raw_page["offset"])
        rows = [dict(row) for row in raw_page["redacted_rows"]]
        if raw_page["purpose"] == "development":
            development[offset] = rows
        else:
            confirmatory[offset] = rows
    rebuilt = _build_selection_receipt_v5(
        prior_receipt=prior_receipt,
        successor_exposure_set=successor_exposure_set,
        predecessor_selection=predecessor_selection,
        development_pages=development,
        confirmatory_pages=confirmatory,
        page_loader=lambda rows, offset: _page_input_redacted(rows, offset),
        development_components=int(policy["development_components"]),
        confirmatory_items=int(policy["confirmatory_items"]),
    )
    if rebuilt != dict(value):
        raise PowerRefusal("v5 selection receipt does not replay from source pages")
    return declared


def verify_gold_source_receipt_v5(
    value: Mapping[str, object], selection_receipt: Mapping[str, object]
) -> str:
    selection_sha = verify_selection_receipt_v5(selection_receipt)
    expected = {
        "schema_version", "selection_receipt_sha256", "source_pages",
        "selected_rows", "gold_source_receipt_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != expected:
        raise PowerRefusal("v5 gold-source receipt shape drifted")
    unsigned = dict(value)
    declared = unsigned.pop("gold_source_receipt_sha256", None)
    if (
        value.get("schema_version") != GOLD_SOURCE_SCHEMA
        or value.get("selection_receipt_sha256") != selection_sha
        or not isinstance(declared, str)
        or canonical_sha256(unsigned) != declared
    ):
        raise PowerRefusal("v5 gold-source receipt identity or self-hash drifted")
    pages = value.get("source_pages")
    public_pages = selection_receipt.get("source_pages")
    if not isinstance(pages, list) or not isinstance(public_pages, list):
        raise PowerRefusal("v5 gold-source page inventory is absent")
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
            raise PowerRefusal("v5 gold-source page shape drifted")
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
            raise PowerRefusal("v5 gold-source page metadata drifted")
        key = (purpose, offset)
        if key in seen_keys or key not in public_by_key:
            raise PowerRefusal("v5 gold-source page identity repeats or drifted")
        seen_keys.add(key)
        try:
            raw = base64.b64decode(encoded, validate=True)
        except ValueError as error:
            raise PowerRefusal("v5 gold-source page bytes are invalid") from error
        page = _strict_object(raw, "v5 gold-source candidate page")
        if (
            hashlib.sha256(raw).hexdigest() != page_receipt.get("raw_page_sha256")
            or canonical_sha256(page) != page_receipt.get("canonical_page_sha256")
        ):
            raise PowerRefusal("v5 gold-source page preimage drifted")
        rebuilt_public, _projections, _rows = _page_input_bytes(raw, offset)
        if {"purpose": purpose, **rebuilt_public} != dict(public_by_key[key]):
            raise PowerRefusal("v5 gold-source page differs from public redaction")
        for entry in _full_entries_from_page(raw, offset):
            item_id = str(entry["row"]["id"])
            if item_id in entries_by_item:
                raise PowerRefusal("v5 gold-source item identity repeats")
            entries_by_item[item_id] = entry
    if seen_keys != set(public_by_key):
        raise PowerRefusal("v5 gold-source page coverage is incomplete")
    for cohort in ("development", "confirmatory"):
        block = selection_receipt[cohort]
        public_rows = sorted(
            (dict(row) for row in block["selected_rows"]),
            key=lambda row: int(row["dataset_row_index"]),
        )
        gold_block = value["selected_rows"]
        if not isinstance(gold_block, Mapping):
            raise PowerRefusal("v5 gold-source selected rows are absent")
        cohort_block = gold_block.get(cohort)
        if not isinstance(cohort_block, Mapping) or set(cohort_block) != {
            "full_rows", "full_rows_sha256",
        }:
            raise PowerRefusal("v5 gold-source selected block shape drifted")
        full_rows = cohort_block.get("full_rows")
        if not isinstance(full_rows, list) or canonical_sha256(
            full_rows
        ) != cohort_block.get("full_rows_sha256"):
            raise PowerRefusal("v5 gold-source selected block preimage drifted")
        expected_full = sorted(
            (entries_by_item[str(row["row"]["id"])] for row in public_rows),
            key=lambda row: int(row["dataset_row_index"]),
        )
        if full_rows != expected_full or [
            _redact_entry(row) for row in full_rows
        ] != public_rows:
            raise PowerRefusal(
                "v5 gold-source selected rows differ from public selection"
            )
    return declared


def build_selection_receipts_v5(
    *,
    prior_receipt: Mapping[str, object],
    successor_exposure_set: Mapping[str, object],
    predecessor_selection: Mapping[str, object],
    development_pages: Mapping[int, Path],
    confirmatory_pages: Mapping[int, Path],
    development_components: int = DEVELOPMENT_COMPONENTS_V5,
    confirmatory_items: int = CONFIRMATORY_ITEMS_V5,
) -> tuple[dict[str, object], dict[str, object]]:
    development_raw = {
        int(offset): _read_private_bytes(Path(development_pages[offset]))
        for offset in development_pages
    }
    confirmatory_raw = {
        int(offset): _read_private_bytes(Path(confirmatory_pages[offset]))
        for offset in confirmatory_pages
    }
    selection = _build_selection_receipt_v5(
        prior_receipt=prior_receipt,
        successor_exposure_set=successor_exposure_set,
        predecessor_selection=predecessor_selection,
        development_pages=development_raw,
        confirmatory_pages=confirmatory_raw,
        page_loader=lambda raw, offset: _page_input_bytes(bytes(raw), offset),
        development_components=development_components,
        confirmatory_items=confirmatory_items,
    )
    selection_sha = verify_selection_receipt_v5(selection)
    page_receipts: list[dict[str, object]] = []
    all_entries: list[dict[str, object]] = []
    for purpose, pages in (
        ("development", development_raw),
        ("confirmatory_pool", confirmatory_raw),
    ):
        for offset in sorted(pages):
            raw = pages[offset]
            page = _strict_object(raw, "v5 candidate page")
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
    entries_by_item = {str(entry["row"]["id"]): entry for entry in all_entries}
    if len(entries_by_item) != len(all_entries):
        raise PowerRefusal("v5 candidate item identity repeats across source pages")
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
    verify_gold_source_receipt_v5(gold_source, selection)
    return selection, gold_source


def _page_arg(value: str) -> tuple[int, Path]:
    offset_text, _, path_text = value.partition(":")
    if not path_text:
        raise argparse.ArgumentTypeError("expected OFFSET:PATH")
    return int(offset_text), Path(path_text)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    select = subparsers.add_parser("select")
    select.add_argument("--prior-exposure-receipt", type=Path, required=True)
    select.add_argument("--successor-exposure-set", type=Path, required=True)
    select.add_argument("--predecessor-selection", type=Path, required=True)
    select.add_argument(
        "--development-page", action="append", type=_page_arg, required=True
    )
    select.add_argument(
        "--confirmatory-page", action="append", type=_page_arg, required=True
    )
    select.add_argument("--output", type=Path, required=True)
    select.add_argument("--gold-source-output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command != "select":
            raise PowerRefusal("unsupported command")
        prior_raw = _read_private_bytes(args.prior_exposure_receipt)
        prior = _strict_object(prior_raw, "prior-exposure receipt")
        from prom_search_hswm.prom9_f1_r8_runner import read_stable_json

        successor_set, _set_file_sha = read_stable_json(
            args.successor_exposure_set, "successor exposure set"
        )
        predecessor, _predecessor_file_sha = read_stable_json(
            args.predecessor_selection, "predecessor selection receipt"
        )
        development = dict(args.development_page)
        confirmatory = dict(args.confirmatory_page)
        if len(development) != len(args.development_page) or len(confirmatory) != len(
            args.confirmatory_page
        ):
            raise PowerRefusal("duplicate page argument")
        if args.output.resolve() == args.gold_source_output.resolve():
            raise PowerRefusal("public and gold-source outputs must be distinct")
        receipt, gold_source = build_selection_receipts_v5(
            prior_receipt=prior,
            successor_exposure_set=successor_set,
            predecessor_selection=predecessor,
            development_pages=development,
            confirmatory_pages=confirmatory,
        )
        verify_selection_receipt_v5(receipt)
        verify_gold_source_receipt_v5(gold_source, receipt)
        write_private_once(args.gold_source_output, gold_source)
        write_private_once(args.output, receipt)
        print(
            json.dumps(
                {
                    "status": "FROZEN_BEFORE_MODEL_CALLS",
                    "selection_receipt_sha256": receipt["selection_receipt_sha256"],
                    "development_components": len(
                        receipt["development"]["component_schedule"]
                    ),
                    "development_items": len(receipt["development"]["item_ids"]),
                    "confirmatory_components": len(
                        receipt["confirmatory"]["component_schedule"]
                    ),
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
