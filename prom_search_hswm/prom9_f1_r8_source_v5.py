#!/usr/bin/env python3
"""Produce one F1 r8 c800 source quartet from the frozen v5 selection.

Generation-bound fork of the ``prom9_f1_r8_source`` CLI for the C-recontract
cohorts ratified 2026-08-05: the selection/gold inputs are v5 receipts
(cohort-selection/v5, 800/800 train cohorts) whose verification lives in
``prom9_f1_r8_selection_v5``, and the run identities are pinned to the c800
generation.  All artifact construction (manifest / gold / source receipt /
evaluator receipt) is the untouched ``build_artifacts`` machinery.

The v4 CLI stays as-is for its own generation; this module refuses anything
that is not exactly the c800 contract (fail-closed).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from prom_search_hswm.prom9_f1_prior_exposure import (
    _read_private_bytes,
    _strict_object,
)
from prom_search_hswm.prom9_f1_r8_envelope_v5 import (
    CONFIRMATORY_RUN_ID_C800,
    DATASET_C800,
    DATASET_CONFIG_C800,
    DEVELOPMENT_RUN_ID_C800,
)
from prom_search_hswm.prom9_f1_r8_power import (
    evaluator_selected_entries,
    selected_entries,
)
from prom_search_hswm.prom9_f1_r8_selection_v5 import (
    verify_gold_source_receipt_v5,
    verify_selection_receipt_v5,
)
from prom_search_hswm.prom9_f1_r8_source import (
    R8SourceRefusal,
    build_artifacts,
    read_json,
    write_json_once,
)

DATASET_SPLIT_C800 = "train"
COHORT_CONTRACTS_C800 = {
    "development": {
        "run_id": DEVELOPMENT_RUN_ID_C800,
        "mode": "development",
        "length": 959,
    },
    "confirmatory": {
        "run_id": CONFIRMATORY_RUN_ID_C800,
        "mode": "sealed",
        "length": 800,
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
        contract = COHORT_CONTRACTS_C800[args.selection_cohort]
        if args.run_id != contract["run_id"] or args.mode != contract["mode"]:
            raise R8SourceRefusal(
                "c800 source requires the exact ratified run identity for its "
                "cohort"
            )
        if args.mode == "development" and args.preregistration_artifact_sha256:
            raise R8SourceRefusal(
                "development source must not carry a preregistration anchor"
            )
        if args.mode == "sealed" and not args.preregistration_artifact_sha256:
            raise R8SourceRefusal("sealed source requires a preregistration anchor")

        selection = _strict_object(
            _read_private_bytes(args.selection_receipt), "v5 selection receipt"
        )
        selection_sha = verify_selection_receipt_v5(selection)
        policy = selection["selection_policy"]
        if policy.get("dataset_split") != DATASET_SPLIT_C800:
            raise R8SourceRefusal("v5 selection split is not the ratified train pool")

        gold_source = _strict_object(
            _read_private_bytes(args.gold_source_receipt),
            "evaluator-only v5 gold-source receipt",
        )
        verify_gold_source_receipt_v5(gold_source, selection)
        gold_source_sha = str(gold_source["gold_source_receipt_sha256"])

        public_rows = selected_entries(selection, args.selection_cohort)
        evaluator_rows = evaluator_selected_entries(
            selection, gold_source, args.selection_cohort
        )
        if (
            len(public_rows) != contract["length"]
            or len(evaluator_rows) != contract["length"]
        ):
            raise R8SourceRefusal(
                "selected cohort count differs from the ratified c800 contract"
            )
        token_envelope = read_json(args.token_envelope, "token envelope")
        artifacts = build_artifacts(
            public_rows,
            evaluator_rows,
            public_selection_receipt_sha256=selection_sha,
            gold_source_receipt_sha256=gold_source_sha,
            dataset=DATASET_C800,
            config=DATASET_CONFIG_C800,
            split=DATASET_SPLIT_C800,
            run_id=args.run_id,
            mode=args.mode,
            model=args.model,
            model_revision=args.model_revision,
            token_envelope=token_envelope,
            sealed_at=args.sealed_at,
            preregistration_artifact_sha256=args.preregistration_artifact_sha256,
        )
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
        from prom_search_hswm.hswm_typed_ports import canonical_sha256

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
