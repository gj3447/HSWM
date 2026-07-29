#!/usr/bin/env python3
"""Freeze outcome-blind F1 r8 cohorts and build the development power receipt.

Selection reads only Dataset Viewer IDs/questions/context/type.  The private
page and selected-row byte preimages remain embedded, but answers are never
used by the selector or printed.  Development components are frozen before
any model call as 12 equal blocks of four; the confirmatory cohort is selected
from complete singleton components so exactly 100 raw items are retained.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import random
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
from prom_search_hswm.prom9_f1_prior_exposure import (
    _assign_components,
    _page_projection,
    _read_private_bytes,
    _strict_object,
    verify_prior_exposure_receipt,
    write_private_once,
)


SELECTION_SCHEMA = "hswm-prom9-f1-r8-cohort-selection/v1"
POWER_RECEIPT_SCHEMA = "hswm-prom9-f1-r8-power-operating-characteristic/v2"
POWER_DEVELOPMENT_SCHEMA = "hswm-prom9-f1-r8-power-development-data/v1"
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


class PowerRefusal(RuntimeError):
    """The frozen selection or power evidence is inadmissible."""


def _page_input(path: Path, offset: int) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    raw = _read_private_bytes(path)
    page = _strict_object(raw, "r8 candidate page")
    projections = _page_projection(page, offset=offset, length=100)
    wrapped = page.get("rows")
    assert isinstance(wrapped, list)
    entries = [
        {"dataset_row_index": offset + index, "row": dict(value["row"])}
        for index, value in enumerate(wrapped)
    ]
    receipt = {
        "offset": offset,
        "length": 100,
        "raw_bytes_sha256": hashlib.sha256(raw).hexdigest(),
        "canonical_viewer_response_sha256": canonical_sha256(page),
        "payload_base64": base64.b64encode(raw).decode("ascii"),
        "whitelisted_projection_sha256": canonical_sha256(projections),
    }
    return receipt, projections, entries


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
    raw = canonical_json(entries).encode("utf-8")
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
        "raw_rows_json_b64": base64.b64encode(raw).decode("ascii"),
        "raw_rows_sha256": hashlib.sha256(raw).hexdigest(),
        "item_root_sha256": canonical_sha256(item_ids),
        "source_entity_root_sha256": canonical_sha256(source_entities),
        "component_root_sha256": canonical_sha256(component_ids),
    }


def _verify_disjoint(left: Mapping[str, object], right: Mapping[str, object], label: str) -> None:
    for key in ("item_ids", "source_entity_ids", "component_ids"):
        if set(left[key]) & set(right[key]):
            raise PowerRefusal(f"{label} overlaps on {key}")


def build_selection_receipt(
    *,
    prior_receipt: Mapping[str, object],
    development_pages: Mapping[int, Path],
    confirmatory_pages: Mapping[int, Path],
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
        page_receipt, projections, entries = _page_input(development_pages[offset], offset)
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
        page_receipt, projections, entries = _page_input(confirmatory_pages[offset], offset)
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
    if len(development.get("component_schedule", [])) != 48:
        raise PowerRefusal("development selection must contain exactly 48 components")
    if len(confirmatory.get("item_ids", [])) != 100:
        raise PowerRefusal("confirmatory selection must contain exactly 100 items")
    return declared


def selected_entries(value: Mapping[str, object], cohort: str) -> list[dict[str, object]]:
    verify_selection_receipt(value)
    block = value.get(cohort)
    if not isinstance(block, Mapping):
        raise PowerRefusal("unknown selected cohort")
    encoded = block.get("raw_rows_json_b64")
    if not isinstance(encoded, str):
        raise PowerRefusal("selected cohort lacks raw-row preimage")
    try:
        raw = base64.b64decode(encoded, validate=True)
        entries = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError, json.JSONDecodeError) as error:
        raise PowerRefusal("selected cohort raw-row preimage is invalid") from error
    if hashlib.sha256(raw).hexdigest() != block.get("raw_rows_sha256"):
        raise PowerRefusal("selected cohort raw-row hash drifted")
    if not isinstance(entries, list):
        raise PowerRefusal("selected cohort raw rows must be an array")
    return entries


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
        receipt = build_selection_receipt(
            prior_receipt=prior,
            development_pages=development,
            confirmatory_pages=confirmatory,
        )
        verify_selection_receipt(receipt)
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
    "SELECTION_SCHEMA",
    "build_selection_receipt",
    "selected_entries",
    "verify_selection_receipt",
]
