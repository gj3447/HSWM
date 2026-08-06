#!/usr/bin/env python3
"""Freeze the outcome-blind F1 r8 C-recontract cohorts (selection v6).

C801 generation: development 800 components (200 equal seed blocks of four)
and confirmatory 800 complete singleton components, selected from fresh train
Dataset Viewer pages whose split+offset keys are disjoint from all v3/v4 pages
and the quarantined c800 v5 selection.  The exposure boundary is the verified
c801 successor-v2 set merged with the prior-exposure receipt and extended with
the exact c800 incident selection's development and confirmatory 3-axis blocks.

Selection reads only Dataset Viewer IDs/questions/context/type.  The public
v6 receipt contains only redacted rows; answer-bearing preimages live in the
evaluator-only gold-source receipt, as in prior receipt generations.
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
    verify_prior_exposure_receipt,
    write_private_once,
)
from prom_search_hswm.prom9_f1_r8_c801_exposure import (
    merge_c801_exposure_boundaries,
    verify_f1_r8_successor_exposure_set_v2,
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
)
from prom_search_hswm.prom9_f1_r8_selection_v5 import (
    verify_selection_receipt_v5 as verify_predecessor_selection_receipt,
)


SELECTION_SCHEMA_V6 = "hswm-prom9-f1-r8-cohort-selection/v6"
DEVELOPMENT_COMPONENTS_V6 = 800
SEED_BLOCKS_V6 = 200
COMPONENTS_PER_BLOCK_V6 = 4
CONFIRMATORY_ITEMS_V6 = 800
DEV_PURPOSE_V6 = "development_power_c801"
CONF_PURPOSE_V6 = "confirmatory_c801"
DATASET_SPLITS_V6 = ("train",)
HISTORICAL_POOL_PAGE_KEYS = frozenset(
    f"validation:{offset}"
    for offset in (
        104, 204, 304, 404, 504, 604, 704,
        804, 904, 1004, 1104, 1204, 1304, 1404,
    )
)


def _verify_offset_grid(
    development_offsets: Sequence[int],
    confirmatory_offsets: Sequence[int],
    *,
    dataset_split: str = "train",
    predecessor_page_keys: Sequence[str] = (),
) -> None:
    if dataset_split not in DATASET_SPLITS_V6:
        raise PowerRefusal("v6 dataset split is not a recognized pool split")
    predecessor_keys = frozenset(predecessor_page_keys)
    dev = list(development_offsets)
    conf = list(confirmatory_offsets)
    for label, offsets in (("development", dev), ("confirmatory", conf)):
        if not offsets or len(set(offsets)) != len(offsets):
            raise PowerRefusal(f"v6 {label} offsets are empty or repeat")
        for offset in offsets:
            if isinstance(offset, bool) or not isinstance(offset, int):
                raise PowerRefusal(f"v6 {label} offset is not an integer")
            if offset % 100 != 4:
                raise PowerRefusal(
                    f"v6 {label} offset breaks the Dataset Viewer page grid"
                )
            page_key = f"{dataset_split}:{offset}"
            if page_key in HISTORICAL_POOL_PAGE_KEYS:
                raise PowerRefusal(
                    f"v6 {label} page key reuses a historical v3/v4 pool page"
                )
            if page_key in predecessor_keys:
                raise PowerRefusal(
                    f"v6 {label} page key reuses a predecessor v5 pool page"
                )
    if set(dev) & set(conf):
        raise PowerRefusal("v6 development and confirmatory pool pages overlap")


def _valid_page_key(value: str) -> bool:
    split, separator, offset_text = value.partition(":")
    return (
        separator == ":"
        and split in ("validation", "train")
        and offset_text.isdigit()
        and int(offset_text) % 100 == 4
    )


def _predecessor_boundary(
    predecessor: Mapping[str, object],
    successor_exposure_set: Mapping[str, object],
) -> tuple[str, dict[str, set[str]], list[str]]:
    """Verify the predecessor selection receipt and lift its 3-axis blocks.

    Both cohorts are lifted: predecessor development gold was opened by the
    completed t2/t3b development runs, and predecessor confirmatory gold was
    staged on disk during the sealed-v2 stage-1 attempt.  All of it is
    therefore forbidden for every v6 cohort.
    """

    predecessor_sha = verify_predecessor_selection_receipt(predecessor)
    incident = successor_exposure_set.get("c800_incident")
    artifacts = incident.get("artifact_bindings") if isinstance(incident, Mapping) else None
    selection_binding = (
        artifacts.get("selection_receipt") if isinstance(artifacts, Mapping) else None
    )
    declared_hashes = (
        selection_binding.get("declared_hashes")
        if isinstance(selection_binding, Mapping)
        else None
    )
    if (
        not isinstance(declared_hashes, Mapping)
        or declared_hashes.get("selection_receipt_sha256") != predecessor_sha
    ):
        raise PowerRefusal(
            "predecessor v5 selection is not the quarantined c800 selection"
        )
    policy = predecessor.get("selection_policy")
    pages = predecessor.get("source_pages")
    if not isinstance(policy, Mapping) or not isinstance(pages, list):
        raise PowerRefusal("predecessor v5 page-key preimage is absent")
    predecessor_split = policy.get("dataset_split")
    if predecessor_split not in ("validation", "train"):
        raise PowerRefusal("predecessor v5 dataset split drifted")
    page_keys: list[str] = []
    for raw_page in pages:
        if not isinstance(raw_page, Mapping):
            raise PowerRefusal("predecessor v5 source-page entry is malformed")
        offset = raw_page.get("offset")
        if isinstance(offset, bool) or not isinstance(offset, int):
            raise PowerRefusal("predecessor v5 source-page offset is malformed")
        page_key = f"{predecessor_split}:{offset}"
        if not _valid_page_key(page_key):
            raise PowerRefusal("predecessor v5 source-page key is malformed")
        page_keys.append(page_key)
    page_keys = sorted(set(page_keys))
    if not page_keys:
        raise PowerRefusal("predecessor v5 page-key boundary is empty")
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
    return predecessor_sha, boundary, page_keys


def _build_selection_receipt_v6(
    *,
    prior_receipt: Mapping[str, object],
    successor_exposure_set: Mapping[str, object],
    predecessor_selection: Mapping[str, object],
    development_pages: Mapping[int, object],
    confirmatory_pages: Mapping[int, object],
    page_loader,
    development_components: int = DEVELOPMENT_COMPONENTS_V6,
    confirmatory_items: int = CONFIRMATORY_ITEMS_V6,
    dataset_split: str = "train",
) -> dict[str, object]:
    if (
        development_components != DEVELOPMENT_COMPONENTS_V6
        or confirmatory_items != CONFIRMATORY_ITEMS_V6
    ):
        raise PowerRefusal("v6 selection scale is not the ratified 800/800 contract")
    if development_components % COMPONENTS_PER_BLOCK_V6:
        raise PowerRefusal("v6 development components do not form equal seed blocks")
    seed_blocks = development_components // COMPONENTS_PER_BLOCK_V6

    prior_sha = verify_prior_exposure_receipt(prior_receipt)
    aborted_sha = verify_f1_r8_successor_exposure_set_v2(successor_exposure_set)
    exposure_boundary = merge_c801_exposure_boundaries(
        prior_receipt, successor_exposure_set
    )
    if (
        exposure_boundary.get("prior_exposure_receipt_sha256") != prior_sha
        or exposure_boundary.get("aborted_attempt_exposure_receipt_sha256")
        != aborted_sha
    ):
        raise PowerRefusal("merged exposure boundary identity drifted")
    predecessor_sha, predecessor_boundary, predecessor_page_keys = _predecessor_boundary(
        predecessor_selection, successor_exposure_set
    )

    development_offsets = sorted(int(value) for value in development_pages)
    confirmatory_offsets = sorted(int(value) for value in confirmatory_pages)
    _verify_offset_grid(
        development_offsets,
        confirmatory_offsets,
        dataset_split=dataset_split,
        predecessor_page_keys=predecessor_page_keys,
    )

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
            "v6 development pool has fewer prior-fresh components than the "
            "ratified cohort"
        )
    development_selected = sorted(
        eligible_dev,
        key=lambda value: _component_key(str(value["component_id"]), DEV_PURPOSE_V6),
    )[:development_components]
    if not (
        {len(component["item_ids"]) for component in development_selected} & {1}
    ) or not any(
        len(component["item_ids"]) > 1 for component in development_selected
    ):
        raise PowerRefusal("v6 development selection lacks singleton/multi variation")
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
                "seed_block": rank // COMPONENTS_PER_BLOCK_V6,
                "carryover_block": rank % COMPONENTS_PER_BLOCK_V6,
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
            != set(range(COMPONENTS_PER_BLOCK_V6))
            for block in range(seed_blocks)
        )
    ):
        raise PowerRefusal("v6 development block assignment drifted")
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
            "v6 confirmatory pool has fewer fresh singleton components than the "
            "ratified cohort"
        )
    confirmatory_selected = sorted(
        eligible_confirmatory,
        key=lambda value: _component_key(str(value["component_id"]), CONF_PURPOSE_V6),
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
            "v6 confirmatory selection is not exactly the ratified complete cohort"
        )

    policy = {
        "selection_seed": 20260806,
        "dataset_split": dataset_split,
        "development_pool_offsets": development_offsets,
        "confirmatory_pool_offsets": confirmatory_offsets,
        "page_length": 100,
        "development_components": development_components,
        "seed_blocks": seed_blocks,
        "components_per_seed_block": COMPONENTS_PER_BLOCK_V6,
        "confirmatory_items": confirmatory_items,
        "confirmatory_component_size": 1,
        "selection_key_schema": "hswm-f1-r8-component-selection/v1",
        "block_assignment_schema": "hswm-f1-r8-power-block-assignment/v1",
        "selection_purposes": {
            "development": DEV_PURPOSE_V6,
            "confirmatory": CONF_PURPOSE_V6,
        },
        "pool_freshness": (
            "split_offset_keys_disjoint_from_v3_v4_and_predecessor_v5"
        ),
        "predecessor_pool_page_keys": predecessor_page_keys,
        "predecessor_pool_page_key_root_sha256": canonical_sha256(
            predecessor_page_keys
        ),
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
        "schema_version": SELECTION_SCHEMA_V6,
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


def _verify_development_block_assignment_v6(
    development: Mapping[str, object], *, development_components: int
) -> None:
    schedule = development.get("component_schedule")
    if not isinstance(schedule, list) or len(schedule) != development_components:
        raise PowerRefusal(
            "v6 development selection component count differs from its policy"
        )
    rows: dict[str, Mapping[str, object]] = {}
    expected_fields = {
        "component_id",
        "item_ids",
        "source_entity_ids",
        "cluster_size",
        "seed_block",
        "carryover_block",
    }
    for raw in schedule:
        if not isinstance(raw, Mapping) or set(raw) != expected_fields:
            raise PowerRefusal("v6 development component schedule is malformed")
        component_id = raw.get("component_id")
        item_ids = raw.get("item_ids")
        source_entity_ids = raw.get("source_entity_ids")
        if (
            not isinstance(component_id, str)
            or _SHA256.fullmatch(component_id) is None
            or component_id in rows
            or not isinstance(item_ids, list)
            or not item_ids
            or item_ids != sorted(set(str(value) for value in item_ids))
            or not isinstance(source_entity_ids, list)
            or not source_entity_ids
            or source_entity_ids
            != sorted(set(str(value) for value in source_entity_ids))
            or raw.get("cluster_size") != len(item_ids)
        ):
            raise PowerRefusal("v6 development component schedule identity drifted")
        rows[component_id] = raw
    ordered = sorted(rows, key=_block_key)
    if [str(raw.get("component_id")) for raw in schedule] != ordered:
        raise PowerRefusal("v6 development block order drifted")
    for rank, component_id in enumerate(ordered):
        raw = rows[component_id]
        observed = (raw.get("seed_block"), raw.get("carryover_block"))
        expected = (
            rank // COMPONENTS_PER_BLOCK_V6,
            rank % COMPONENTS_PER_BLOCK_V6,
        )
        if (
            any(
                isinstance(value, bool) or not isinstance(value, int)
                for value in observed
            )
            or observed != expected
        ):
            raise PowerRefusal("v6 development block assignment drifted")

    schedule_component_ids = list(rows)
    expected_selection_order = sorted(
        schedule_component_ids,
        key=lambda component_id: _component_key(component_id, DEV_PURPOSE_V6),
    )
    if (
        development.get("component_ids") != sorted(schedule_component_ids)
        or development.get("item_ids")
        != sorted(
            str(item_id)
            for raw in schedule
            for item_id in raw["item_ids"]
        )
        or development.get("source_entity_ids")
        != sorted(
            {
                str(source_id)
                for raw in schedule
                for source_id in raw["source_entity_ids"]
            }
        )
        or development.get("selection_root_sha256")
        != canonical_sha256(expected_selection_order)
    ):
        raise PowerRefusal("v6 development component schedule binding drifted")


def _verify_cohort_roots_v6(
    cohort: str, block: Mapping[str, object]
) -> None:
    for axis, root_field in (
        ("item_ids", "item_root_sha256"),
        ("source_entity_ids", "source_entity_root_sha256"),
        ("component_ids", "component_root_sha256"),
    ):
        values = block.get(axis)
        if (
            not isinstance(values, list)
            or values != sorted(set(str(value) for value in values))
            or canonical_sha256(values) != block.get(root_field)
        ):
            raise PowerRefusal(f"v6 {cohort} {axis} root binding drifted")


def verify_selection_receipt_v6(value: Mapping[str, object]) -> str:
    expected_fields = {
        "schema_version",
        "prior_exposure_receipt_sha256",
        "aborted_attempt_exposure_receipt_sha256",
        "predecessor_selection_receipt_sha256",
        "selection_policy",
        "source_pages",
        "development",
        "confirmatory",
        "pairwise_disjoint",
        "answers_disclosed_to_stdout",
        "selection_receipt_sha256",
    }
    if set(value) != expected_fields or value.get("schema_version") != SELECTION_SCHEMA_V6:
        raise PowerRefusal("v6 selection receipt schema drifted")
    unsigned = dict(value)
    declared = unsigned.pop("selection_receipt_sha256", None)
    if not isinstance(declared, str) or canonical_sha256(unsigned) != declared:
        raise PowerRefusal("v6 selection receipt self-hash drifted")
    if any(
        not isinstance(value.get(field), str)
        or _SHA256.fullmatch(str(value.get(field))) is None
        for field in (
            "prior_exposure_receipt_sha256",
            "aborted_attempt_exposure_receipt_sha256",
            "predecessor_selection_receipt_sha256",
        )
    ):
        raise PowerRefusal("v6 selection exposure/predecessor binding drifted")
    if value.get("pairwise_disjoint") != {
        "item_ids": True,
        "source_entity_ids": True,
        "component_ids": True,
    } or value.get("answers_disclosed_to_stdout") is not False:
        raise PowerRefusal("v6 selection disjointness was not proven")
    policy = value.get("selection_policy")
    expected_policy_fields = {
        "selection_seed",
        "dataset_split",
        "development_pool_offsets",
        "confirmatory_pool_offsets",
        "page_length",
        "development_components",
        "seed_blocks",
        "components_per_seed_block",
        "confirmatory_items",
        "confirmatory_component_size",
        "selection_key_schema",
        "block_assignment_schema",
        "selection_purposes",
        "pool_freshness",
        "predecessor_pool_page_keys",
        "predecessor_pool_page_key_root_sha256",
        "predecessor_exclusion_cohorts",
        "exclusion_dimensions",
        "derived_fields",
        "answers_used_for_selection",
    }
    if not isinstance(policy, Mapping) or set(policy) != expected_policy_fields:
        raise PowerRefusal("v6 selection policy is absent")
    development_components = policy.get("development_components")
    confirmatory_items = policy.get("confirmatory_items")
    if (
        isinstance(development_components, bool)
        or not isinstance(development_components, int)
        or isinstance(confirmatory_items, bool)
        or not isinstance(confirmatory_items, int)
    ):
        raise PowerRefusal("v6 selection policy scale is malformed")
    if (
        development_components != DEVELOPMENT_COMPONENTS_V6
        or confirmatory_items != CONFIRMATORY_ITEMS_V6
        or policy.get("selection_seed") != 20260806
        or policy.get("seed_blocks") != SEED_BLOCKS_V6
        or policy.get("components_per_seed_block") != COMPONENTS_PER_BLOCK_V6
        or policy.get("confirmatory_component_size") != 1
        or policy.get("page_length") != 100
        or policy.get("selection_key_schema")
        != "hswm-f1-r8-component-selection/v1"
        or policy.get("block_assignment_schema")
        != "hswm-f1-r8-power-block-assignment/v1"
        or policy.get("selection_purposes")
        != {"development": DEV_PURPOSE_V6, "confirmatory": CONF_PURPOSE_V6}
        or policy.get("pool_freshness")
        != "split_offset_keys_disjoint_from_v3_v4_and_predecessor_v5"
        or policy.get("predecessor_exclusion_cohorts")
        != ["development", "confirmatory"]
        or policy.get("exclusion_dimensions")
        != ["item_ids", "source_entity_ids", "component_ids"]
        or policy.get("derived_fields") != ["id", "question", "context", "type"]
        or policy.get("answers_used_for_selection") is not False
    ):
        raise PowerRefusal("v6 selection policy differs from the ratified c801 contract")
    dev_offsets = policy.get("development_pool_offsets")
    conf_offsets = policy.get("confirmatory_pool_offsets")
    if not isinstance(dev_offsets, list) or not isinstance(conf_offsets, list):
        raise PowerRefusal("v6 selection policy offsets are absent")
    dataset_split = policy.get("dataset_split")
    if dataset_split not in DATASET_SPLITS_V6:
        raise PowerRefusal("v6 selection policy split drifted")
    predecessor_page_keys = policy.get("predecessor_pool_page_keys")
    predecessor_page_key_root = policy.get(
        "predecessor_pool_page_key_root_sha256"
    )
    if (
        not isinstance(predecessor_page_keys, list)
        or not predecessor_page_keys
        or any(
            not isinstance(key, str) or not _valid_page_key(key)
            for key in predecessor_page_keys
        )
        or predecessor_page_keys != sorted(set(predecessor_page_keys))
        or not isinstance(predecessor_page_key_root, str)
        or canonical_sha256(predecessor_page_keys) != predecessor_page_key_root
    ):
        raise PowerRefusal("v6 predecessor pool page-key boundary drifted")
    _verify_offset_grid(
        dev_offsets,
        conf_offsets,
        dataset_split=dataset_split,
        predecessor_page_keys=predecessor_page_keys,
    )
    development = value.get("development")
    confirmatory = value.get("confirmatory")
    if not isinstance(development, Mapping) or not isinstance(confirmatory, Mapping):
        raise PowerRefusal("v6 selection cohorts are absent")
    _verify_development_block_assignment_v6(
        development, development_components=development_components
    )
    _verify_cohort_roots_v6("development", development)
    _verify_cohort_roots_v6("confirmatory", confirmatory)
    if len(confirmatory.get("item_ids", [])) != confirmatory_items:
        raise PowerRefusal(
            "v6 confirmatory selection differs from its policy item count"
        )
    confirmatory_schedule = confirmatory.get("component_schedule")
    confirmatory_component_ids = confirmatory.get("component_ids")
    confirmatory_schedule_fields = {
        "component_id", "item_ids", "source_entity_ids", "cluster_size",
    }
    if (
        not isinstance(confirmatory_schedule, list)
        or len(confirmatory_schedule) != CONFIRMATORY_ITEMS_V6
        or not isinstance(confirmatory_component_ids, list)
        or len(confirmatory_component_ids) != CONFIRMATORY_ITEMS_V6
        or len(set(str(value) for value in confirmatory_component_ids))
        != CONFIRMATORY_ITEMS_V6
        or any(
            not isinstance(raw, Mapping)
            or set(raw) != confirmatory_schedule_fields
            or not isinstance(raw.get("component_id"), str)
            or _SHA256.fullmatch(str(raw.get("component_id"))) is None
            or raw.get("cluster_size") != 1
            or not isinstance(raw.get("item_ids"), list)
            or len(raw["item_ids"]) != 1
            or not isinstance(raw.get("source_entity_ids"), list)
            or not raw["source_entity_ids"]
            or raw["source_entity_ids"]
            != sorted(set(str(value) for value in raw["source_entity_ids"]))
            for raw in confirmatory_schedule
        )
    ):
        raise PowerRefusal("v6 confirmatory selection is not 800 singleton components")
    confirmatory_schedule_component_ids = [
        str(raw["component_id"]) for raw in confirmatory_schedule
    ]
    if (
        len(set(confirmatory_schedule_component_ids)) != CONFIRMATORY_ITEMS_V6
        or sorted(confirmatory_schedule_component_ids) != confirmatory_component_ids
        or sorted(str(raw["item_ids"][0]) for raw in confirmatory_schedule)
        != confirmatory.get("item_ids")
        or sorted(
            {
                str(source_id)
                for raw in confirmatory_schedule
                for source_id in raw["source_entity_ids"]
            }
        )
        != confirmatory.get("source_entity_ids")
        or confirmatory.get("selection_root_sha256")
        != canonical_sha256(confirmatory_schedule_component_ids)
    ):
        raise PowerRefusal("v6 confirmatory component schedule binding drifted")
    _verify_disjoint(development, confirmatory, "development/confirmatory")
    for cohort, block in (("development", development), ("confirmatory", confirmatory)):
        rows = block.get("selected_rows")
        if not isinstance(rows, list) or canonical_sha256(rows) != block.get(
            "selected_rows_sha256"
        ):
            raise PowerRefusal(f"v6 {cohort} selected-row preimage drifted")
        entries = _selected_entries_unverified(block)
        if {str(entry["row"]["id"]) for entry in entries} != set(
            str(item_id) for item_id in block.get("item_ids", [])
        ):
            raise PowerRefusal(f"v6 {cohort} selected-row identity drifted")
    pages = value.get("source_pages")
    if not isinstance(pages, list) or len(pages) != (
        len(dev_offsets) + len(conf_offsets)
    ):
        raise PowerRefusal("v6 selection source-page inventory drifted")
    seen_pages: set[tuple[str, int]] = set()
    page_fields = {
        "purpose",
        "offset",
        "length",
        "redacted_rows",
        "redacted_rows_sha256",
        "whitelisted_projection_sha256",
    }
    for raw_page in pages:
        if not isinstance(raw_page, Mapping) or set(raw_page) != page_fields:
            raise PowerRefusal("v6 selection source-page entry is malformed")
        purpose = raw_page.get("purpose")
        offset = raw_page.get("offset")
        if purpose == "development":
            expected_offsets = dev_offsets
        elif purpose == "confirmatory_pool":
            expected_offsets = conf_offsets
        else:
            raise PowerRefusal("v6 selection source-page purpose drifted")
        if (
            isinstance(offset, bool)
            or offset not in expected_offsets
            or raw_page.get("length") != 100
            or not isinstance(raw_page.get("whitelisted_projection_sha256"), str)
            or _SHA256.fullmatch(
                str(raw_page.get("whitelisted_projection_sha256"))
            ) is None
        ):
            raise PowerRefusal("v6 selection source-page offset drifted")
        key = (str(purpose), int(offset))
        if key in seen_pages:
            raise PowerRefusal("v6 selection source-page offset repeats")
        seen_pages.add(key)
        rows = raw_page.get("redacted_rows")
        if not isinstance(rows, list) or canonical_sha256(rows) != raw_page.get(
            "redacted_rows_sha256"
        ):
            raise PowerRefusal("v6 selection redacted page hash drifted")
    return declared


def replay_selection_receipt_v6(
    value: Mapping[str, object],
    *,
    prior_receipt: Mapping[str, object],
    successor_exposure_set: Mapping[str, object],
    predecessor_selection: Mapping[str, object],
) -> str:
    """Replay the v6 selector from public redacted pages only."""

    declared = verify_selection_receipt_v6(value)
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
    rebuilt = _build_selection_receipt_v6(
        prior_receipt=prior_receipt,
        successor_exposure_set=successor_exposure_set,
        predecessor_selection=predecessor_selection,
        development_pages=development,
        confirmatory_pages=confirmatory,
        page_loader=lambda rows, offset: _page_input_redacted(rows, offset),
        development_components=int(policy["development_components"]),
        confirmatory_items=int(policy["confirmatory_items"]),
        dataset_split=str(policy["dataset_split"]),
    )
    if rebuilt != dict(value):
        raise PowerRefusal("v6 selection receipt does not replay from source pages")
    return declared


def verify_gold_source_receipt_v6(
    value: Mapping[str, object], selection_receipt: Mapping[str, object]
) -> str:
    selection_sha = verify_selection_receipt_v6(selection_receipt)
    expected = {
        "schema_version", "selection_receipt_sha256", "source_pages",
        "selected_rows", "gold_source_receipt_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != expected:
        raise PowerRefusal("v6 gold-source receipt shape drifted")
    unsigned = dict(value)
    declared = unsigned.pop("gold_source_receipt_sha256", None)
    if (
        value.get("schema_version") != GOLD_SOURCE_SCHEMA
        or value.get("selection_receipt_sha256") != selection_sha
        or not isinstance(declared, str)
        or canonical_sha256(unsigned) != declared
    ):
        raise PowerRefusal("v6 gold-source receipt identity or self-hash drifted")
    pages = value.get("source_pages")
    public_pages = selection_receipt.get("source_pages")
    if not isinstance(pages, list) or not isinstance(public_pages, list):
        raise PowerRefusal("v6 gold-source page inventory is absent")
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
            raise PowerRefusal("v6 gold-source page shape drifted")
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
            raise PowerRefusal("v6 gold-source page metadata drifted")
        key = (purpose, offset)
        if key in seen_keys or key not in public_by_key:
            raise PowerRefusal("v6 gold-source page identity repeats or drifted")
        seen_keys.add(key)
        try:
            raw = base64.b64decode(encoded, validate=True)
        except ValueError as error:
            raise PowerRefusal("v6 gold-source page bytes are invalid") from error
        page = _strict_object(raw, "v6 gold-source candidate page")
        if (
            hashlib.sha256(raw).hexdigest() != page_receipt.get("raw_page_sha256")
            or canonical_sha256(page) != page_receipt.get("canonical_page_sha256")
        ):
            raise PowerRefusal("v6 gold-source page preimage drifted")
        rebuilt_public, _projections, _rows = _page_input_bytes(raw, offset)
        if {"purpose": purpose, **rebuilt_public} != dict(public_by_key[key]):
            raise PowerRefusal("v6 gold-source page differs from public redaction")
        for entry in _full_entries_from_page(raw, offset):
            item_id = str(entry["row"]["id"])
            if item_id in entries_by_item:
                raise PowerRefusal("v6 gold-source item identity repeats")
            entries_by_item[item_id] = entry
    if seen_keys != set(public_by_key):
        raise PowerRefusal("v6 gold-source page coverage is incomplete")
    for cohort in ("development", "confirmatory"):
        block = selection_receipt[cohort]
        public_rows = sorted(
            (dict(row) for row in block["selected_rows"]),
            key=lambda row: int(row["dataset_row_index"]),
        )
        gold_block = value["selected_rows"]
        if not isinstance(gold_block, Mapping):
            raise PowerRefusal("v6 gold-source selected rows are absent")
        cohort_block = gold_block.get(cohort)
        if not isinstance(cohort_block, Mapping) or set(cohort_block) != {
            "full_rows", "full_rows_sha256",
        }:
            raise PowerRefusal("v6 gold-source selected block shape drifted")
        full_rows = cohort_block.get("full_rows")
        if not isinstance(full_rows, list) or canonical_sha256(
            full_rows
        ) != cohort_block.get("full_rows_sha256"):
            raise PowerRefusal("v6 gold-source selected block preimage drifted")
        expected_full = sorted(
            (entries_by_item[str(row["row"]["id"])] for row in public_rows),
            key=lambda row: int(row["dataset_row_index"]),
        )
        if full_rows != expected_full or [
            _redact_entry(row) for row in full_rows
        ] != public_rows:
            raise PowerRefusal(
                "v6 gold-source selected rows differ from public selection"
            )
    return declared


def build_selection_receipts_v6(
    *,
    prior_receipt: Mapping[str, object],
    successor_exposure_set: Mapping[str, object],
    predecessor_selection: Mapping[str, object],
    development_pages: Mapping[int, Path],
    confirmatory_pages: Mapping[int, Path],
    development_components: int = DEVELOPMENT_COMPONENTS_V6,
    confirmatory_items: int = CONFIRMATORY_ITEMS_V6,
    dataset_split: str = "train",
) -> tuple[dict[str, object], dict[str, object]]:
    development_raw = {
        int(offset): _read_private_bytes(Path(development_pages[offset]))
        for offset in development_pages
    }
    confirmatory_raw = {
        int(offset): _read_private_bytes(Path(confirmatory_pages[offset]))
        for offset in confirmatory_pages
    }
    selection = _build_selection_receipt_v6(
        prior_receipt=prior_receipt,
        successor_exposure_set=successor_exposure_set,
        predecessor_selection=predecessor_selection,
        development_pages=development_raw,
        confirmatory_pages=confirmatory_raw,
        page_loader=lambda raw, offset: _page_input_bytes(bytes(raw), offset),
        development_components=development_components,
        confirmatory_items=confirmatory_items,
        dataset_split=dataset_split,
    )
    selection_sha = verify_selection_receipt_v6(selection)
    page_receipts: list[dict[str, object]] = []
    all_entries: list[dict[str, object]] = []
    for purpose, pages in (
        ("development", development_raw),
        ("confirmatory_pool", confirmatory_raw),
    ):
        for offset in sorted(pages):
            raw = pages[offset]
            page = _strict_object(raw, "v6 candidate page")
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
        raise PowerRefusal("v6 candidate item identity repeats across source pages")
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
    verify_gold_source_receipt_v6(gold_source, selection)
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
    select.add_argument(
        "--dataset-split", choices=DATASET_SPLITS_V6, required=True
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
        predecessor = _strict_object(
            _read_private_bytes(args.predecessor_selection),
            "predecessor selection receipt",
        )
        development = dict(args.development_page)
        confirmatory = dict(args.confirmatory_page)
        if len(development) != len(args.development_page) or len(confirmatory) != len(
            args.confirmatory_page
        ):
            raise PowerRefusal("duplicate page argument")
        if args.output.resolve() == args.gold_source_output.resolve():
            raise PowerRefusal("public and gold-source outputs must be distinct")
        receipt, gold_source = build_selection_receipts_v6(
            prior_receipt=prior,
            successor_exposure_set=successor_set,
            predecessor_selection=predecessor,
            development_pages=development,
            confirmatory_pages=confirmatory,
            dataset_split=args.dataset_split,
        )
        verify_selection_receipt_v6(receipt)
        verify_gold_source_receipt_v6(gold_source, receipt)
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
