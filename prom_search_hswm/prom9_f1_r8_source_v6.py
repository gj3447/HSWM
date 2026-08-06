#!/usr/bin/env python3
"""Produce one F1 r8 c801 source quartet from the frozen v6 selection.

Generation-bound fork of the ``prom9_f1_r8_source`` CLI for the C-recontract
cohorts ratified 2026-08-05: the selection/gold inputs are v6 receipts
(cohort-selection/v6, 800/800 train cohorts) whose verification lives in
``prom9_f1_r8_selection_v6``, and the run identities are pinned to the c801
generation.  All artifact construction (manifest / gold / source receipt /
evaluator receipt) is the untouched ``build_artifacts`` machinery.

The v4 CLI stays as-is for its own generation; this module refuses anything
that is not exactly the c801 contract (fail-closed).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from prom_search_hswm.hswm_typed_ports import canonical_sha256
from prom_search_hswm.prom9_f1_prior_exposure import (
    _read_private_bytes,
    _strict_object,
)
from prom_search_hswm.prom9_f1_r8_envelope_v6 import (
    CONFIRMATORY_RUN_ID_C801,
    DATASET_C801,
    DATASET_CONFIG_C801,
    DEVELOPMENT_RUN_ID_C801,
)
from prom_search_hswm.prom9_f1_r8_power import (
    _decode_gold_selected_block,
    _selected_entries_unverified,
)
from prom_search_hswm.prom9_f1_r8_selection_v6 import (
    verify_gold_source_receipt_v6,
    verify_selection_receipt_v6,
)
from prom_search_hswm.prom9_f1_r8_source import (
    R8SourceRefusal,
    build_artifacts,
    read_json,
    write_json_once,
)

DATASET_SPLIT_C801 = "train"
COHORT_CONTRACTS_C801 = {
    "development": {
        "run_id": DEVELOPMENT_RUN_ID_C801,
        "mode": "development",
        "components": 800,
    },
    "confirmatory": {
        "run_id": CONFIRMATORY_RUN_ID_C801,
        "mode": "sealed",
        "components": 800,
        "items": 800,
    },
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection-receipt", type=Path, required=True)
    parser.add_argument("--gold-source-receipt", type=Path, required=True)
    parser.add_argument(
        "--selection-cohort", choices=("development", "confirmatory"), required=True
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--mode", choices=("development", "sealed"), required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--token-envelope", type=Path, required=True)
    parser.add_argument("--sealed-at", required=True)
    parser.add_argument("--preregistration-artifact-sha256")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--source-receipt", type=Path, required=True)
    parser.add_argument("--evaluator-receipt", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        contract = COHORT_CONTRACTS_C801[args.selection_cohort]
        if args.run_id != contract["run_id"] or args.mode != contract["mode"]:
            raise R8SourceRefusal(
                "c801 source requires the exact ratified run identity for its "
                "cohort"
            )
        if args.mode == "development" and args.preregistration_artifact_sha256:
            raise R8SourceRefusal(
                "development source must not carry a preregistration anchor"
            )
        if args.mode == "sealed" and not args.preregistration_artifact_sha256:
            raise R8SourceRefusal("sealed source requires a preregistration anchor")

        selection = _strict_object(
            _read_private_bytes(args.selection_receipt), "v6 selection receipt"
        )
        selection_sha = verify_selection_receipt_v6(selection)
        policy = selection["selection_policy"]
        if policy.get("dataset_split") != DATASET_SPLIT_C801:
            raise R8SourceRefusal("v6 selection split is not the ratified train pool")

        gold_source = _strict_object(
            _read_private_bytes(args.gold_source_receipt),
            "evaluator-only v6 gold-source receipt",
        )
        verify_gold_source_receipt_v6(gold_source, selection)
        gold_source_sha = str(gold_source["gold_source_receipt_sha256"])

        # The v4 accessors (selected_entries / evaluator_selected_entries)
        # re-verify against the v3/v4 schemas; both v6 receipts were already
        # verified above, so read the blocks with the unverified accessors.
        cohort_block = selection.get(args.selection_cohort)
        if not isinstance(cohort_block, dict):
            raise R8SourceRefusal("v6 selection cohort block is absent")
        item_ids = cohort_block.get("item_ids")
        component_ids = cohort_block.get("component_ids")
        component_schedule = cohort_block.get("component_schedule")
        if (
            not isinstance(item_ids, list)
            or not isinstance(component_ids, list)
            or not isinstance(component_schedule, list)
            or len(component_ids) != contract["components"]
            or len(component_schedule) != contract["components"]
            or (
                "items" in contract
                and len(item_ids) != contract["items"]
            )
        ):
            raise R8SourceRefusal(
                "selected cohort scale differs from the ratified c801 contract"
            )
        expected_items = len(item_ids)
        public_rows = _selected_entries_unverified(cohort_block)
        evaluator_rows = _decode_gold_selected_block(
            gold_source, args.selection_cohort
        )
        if (
            len(public_rows) != expected_items
            or len(evaluator_rows) != expected_items
        ):
            raise R8SourceRefusal(
                "selected cohort count differs from the ratified c801 contract"
            )
        token_envelope = read_json(args.token_envelope, "token envelope")
        artifacts = build_artifacts(
            public_rows,
            evaluator_rows,
            public_selection_receipt_sha256=selection_sha,
            gold_source_receipt_sha256=gold_source_sha,
            dataset=DATASET_C801,
            config=DATASET_CONFIG_C801,
            split=DATASET_SPLIT_C801,
            run_id=args.run_id,
            mode=args.mode,
            model=args.model,
            model_revision=args.model_revision,
            token_envelope=token_envelope,
            sealed_at=args.sealed_at,
            preregistration_artifact_sha256=args.preregistration_artifact_sha256,
        )
        summary = artifacts.get("summary")
        if (
            not isinstance(summary, dict)
            or summary.get("items") != expected_items
            or summary.get("components") != contract["components"]
        ):
            raise R8SourceRefusal("generated artifact scale differs from selection")
        destinations = {
            Path(args.manifest).resolve(), Path(args.gold).resolve(),
            Path(args.source_receipt).resolve(),
            Path(args.evaluator_receipt).resolve(),
        }
        if len(destinations) != 4:
            raise R8SourceRefusal("artifact output paths must be distinct")
        write_json_once(args.gold, artifacts["gold"])
        write_json_once(args.evaluator_receipt, artifacts["evaluator_receipt"])
        write_json_once(args.source_receipt, artifacts["source_receipt"])
        write_json_once(args.manifest, artifacts["manifest"])
        print(
            json.dumps(
                {
                    "status": "PREPARED_NO_ANSWERS_DISCLOSED",
                    **artifacts["summary"],
                    "manifest_sha256": canonical_sha256(artifacts["manifest"]),
                    "source_receipt_sha256": artifacts["source_receipt"][
                        "source_receipt_sha256"
                    ],
                },
                sort_keys=True,
            )
        )
        return 0
    except Exception as error:
        print(
            json.dumps({"status": "REFUSED", "reason": str(error)}, sort_keys=True),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
