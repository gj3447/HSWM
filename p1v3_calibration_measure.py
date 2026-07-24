"""Run the P1v3 development-only calibration and emit no scientific verdict."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
from collections.abc import Mapping, Sequence

from hswm_weight_snapshot import canonical_sha256
from p1_llm_answerer import P1AnswererConfigV1
from p1v2_l0_harness import render_answer_prompt, run_l0_observation
from p1v2_l0_preflight import make_qwen_chat_padder
from p1v2_llm_answerer import RecordedP1V2Answerer
from p1v2_prompt_parity import build_prompt_parity_plan
from p1v3_calibration_gate import evaluate_policy_calibration
from p1v3_calibration_preflight import (
    FROZEN_MODULES,
    P1V3CalibrationPreflightError,
    build_calibration_budget,
    build_policy_training_oracle,
    file_sha256,
    policy_case_from_manifests,
    write_once,
)
from p1v3_policy_environment import build_policy_memory_contexts


EVIDENCE_SCHEMA_VERSION = "hswm-p1v3-policy-calibration-evidence/v1"


class P1V3CalibrationMeasurementError(RuntimeError):
    pass


def _verify_self_hash(value: Mapping[str, object], key: str, label: str) -> None:
    unsigned = dict(value)
    declared = unsigned.pop(key, None)
    if not isinstance(declared, str) or canonical_sha256(unsigned) != declared:
        raise P1V3CalibrationMeasurementError(f"{label} self-hash drifted")


def build_calibration_evidence(
    *,
    budget: Mapping[str, object],
    gate_receipt: Mapping[str, object],
    observations: Sequence[Mapping[str, object]],
    command: Sequence[str],
    cwd: str,
    runtime_commit: str,
    environment: Mapping[str, str],
) -> dict[str, object]:
    if not observations or not command or not cwd or len(runtime_commit) != 40:
        raise P1V3CalibrationMeasurementError("calibration evidence identity is incomplete")
    _verify_self_hash(
        gate_receipt, "calibration_receipt_sha256", "calibration gate receipt"
    )
    evidence: dict[str, object] = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "stage": "DEVELOPMENT_ONLY_BEFORE_HELDOUT_FREEZE",
        "budget_manifest_sha256": budget["budget_manifest_sha256"],
        "data_boundary": {
            "public_manifest_sha256": budget["data"]["public_manifest_sha256"],
            "development_sidecar_sha256": budget["data"][
                "development_sidecar_sha256"
            ],
            "heldout_sidecar_sha256": budget["data"]["heldout_sidecar_sha256"],
            "heldout_sidecar_loaded": False,
            "heldout_outcomes_inspected": False,
        },
        "observations": [dict(observation) for observation in observations],
        "calibration_gate": dict(gate_receipt),
        "provenance": {
            "command": list(command),
            "cwd": cwd,
            "runtime_commit": runtime_commit,
            "environment": dict(environment),
        },
        "scientific_judgment_emitted": False,
    }
    if any(key.casefold() == "verdict" for key in _recursive_keys(evidence)):
        raise P1V3CalibrationMeasurementError(
            "calibration evidence must not contain scientific judgment"
        )
    evidence["evidence_sha256"] = canonical_sha256(evidence)
    return evidence


def _recursive_keys(value: object):
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key)
            yield from _recursive_keys(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _recursive_keys(item)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-manifest", type=Path, required=True)
    parser.add_argument("--development-sidecar", type=Path, required=True)
    parser.add_argument("--deployment-receipt", type=Path, required=True)
    parser.add_argument("--budget-manifest", type=Path, required=True)
    parser.add_argument("--tokenizer-snapshot", type=Path, required=True)
    parser.add_argument("--answer-db", type=Path, required=True)
    parser.add_argument("--evidence-output", type=Path, required=True)
    args = parser.parse_args()

    here = Path(__file__).resolve().parent
    public = json.loads(args.public_manifest.read_text(encoding="utf-8"))
    development = json.loads(args.development_sidecar.read_text(encoding="utf-8"))
    deployment = json.loads(args.deployment_receipt.read_text(encoding="utf-8"))
    budget = json.loads(args.budget_manifest.read_text(encoding="utf-8"))
    _verify_self_hash(budget, "budget_manifest_sha256", "calibration budget")
    if set(budget.get("module_sha256", {})) != set(FROZEN_MODULES):
        raise P1V3CalibrationMeasurementError("frozen outcome module cut drifted")
    for module in FROZEN_MODULES:
        if budget["module_sha256"][module] != file_sha256(here / module):
            raise P1V3CalibrationMeasurementError(
                f"frozen outcome module drift: {module}"
            )
    for expected, observed, label in (
        (budget["data"]["public_file_sha256"], file_sha256(args.public_manifest), "public"),
        (
            budget["data"]["development_file_sha256"],
            file_sha256(args.development_sidecar),
            "development",
        ),
        (
            budget["model"]["deployment_file_sha256"],
            file_sha256(args.deployment_receipt),
            "deployment",
        ),
    ):
        if expected != observed:
            raise P1V3CalibrationMeasurementError(f"{label} file hash drifted")
    if budget["data"].get("heldout_sidecar_loaded") is not False:
        raise P1V3CalibrationMeasurementError("budget crossed heldout boundary")

    padder = make_qwen_chat_padder(
        args.tokenizer_snapshot,
        tokenizer_identity=budget["parity"]["tokenizer_identity"],
    )
    rebuilt = build_calibration_budget(
        public=public,
        development=development,
        padder=padder,
        public_file_sha256=file_sha256(args.public_manifest),
        development_file_sha256=file_sha256(args.development_sidecar),
        deployment_receipt_sha256=deployment["receipt_sha256"],
        deployment_file_sha256=file_sha256(args.deployment_receipt),
        module_sha256={module: file_sha256(here / module) for module in FROZEN_MODULES},
        model=deployment["served_model"],
        model_revision=deployment["server_process"]["revision_binding"],
        max_output_tokens=budget["model"]["max_output_tokens"],
        seed=budget["model"]["seed"],
    )
    if rebuilt != budget:
        raise P1V3CalibrationMeasurementError(
            "runtime inputs do not reproduce the frozen calibration budget"
        )

    _training, lesson, transcript, _boundary = build_policy_training_oracle(
        public, development
    )
    public_rows = {
        row["case_id"]: row for row in public["splits"]["calibration"]
    }
    plans = {plan["case_id"]: plan for plan in budget["parity"]["case_plans"]}
    answer_config = P1AnswererConfigV1(
        endpoint=deployment["endpoint"],
        model=deployment["served_model"],
        model_revision=deployment["server_process"]["revision_binding"],
        deployment_receipt_sha256=deployment["receipt_sha256"],
        max_tokens=budget["model"]["max_output_tokens"],
        seed=budget["model"]["seed"],
    )
    observations: list[dict[str, object]] = []
    with RecordedP1V2Answerer(
        args.answer_db,
        config=answer_config,
        count_user_prompt_tokens=padder.count_prompt_tokens,
        tokenizer_identity=padder.tokenizer_identity,
    ) as answerer:
        for case_id in sorted(plans):
            public_row = public_rows[case_id]
            sealed_row = development["cases"].get(case_id)
            if not isinstance(sealed_row, Mapping):
                raise P1V3CalibrationMeasurementError(
                    "calibration outcome is unavailable"
                )
            case = policy_case_from_manifests(public_row, sealed_row)
            contexts = build_policy_memory_contexts(
                question=case.question,
                admitted_lesson=lesson,
                raw_training_transcript=transcript,
            )
            parity = build_prompt_parity_plan(
                contexts,
                render_prompt=lambda context, case=case: render_answer_prompt(
                    case.question, case.documents, context
                ),
                padder=padder,
            )
            plan = plans[case_id]
            if (
                parity.parity_receipt_sha256 != plan["parity_receipt_sha256"]
                or parity.target_prompt_tokens != plan["target_input_tokens_per_arm"]
                or dict(parity.prompt_sha256) != plan["prompt_sha256"]
            ):
                raise P1V3CalibrationMeasurementError(
                    "runtime prompt plan differs from frozen budget"
                )
            observations.append(run_l0_observation(
                case_id=case.case_id,
                question=case.question,
                documents=case.documents,
                sealed_gold_answers=case.expected_answers,
                parity_plan=parity,
                answerer=answerer,
            ))

    calibration_ids = tuple(row["case_id"] for row in public["splits"]["calibration"])
    heldout_ids = tuple(row["case_id"] for row in public["splits"]["heldout"])
    gate = evaluate_policy_calibration(
        observations,
        calibration_case_ids=calibration_ids,
        future_heldout_case_ids=heldout_ids,
        environment_sha256=public["public_manifest_sha256"],
    )
    runtime_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=here, text=True
    ).strip()
    evidence = build_calibration_evidence(
        budget=budget,
        gate_receipt=gate,
        observations=observations,
        command=tuple(sys.argv),
        cwd=str(Path.cwd()),
        runtime_commit=runtime_commit,
        environment={
            "python": sys.version.split()[0],
            "transformers": importlib.metadata.version("transformers"),
            "host": deployment["host"],
            "served_model": deployment["served_model"],
        },
    )
    try:
        write_once(args.evidence_output, evidence)
    except P1V3CalibrationPreflightError as error:
        raise P1V3CalibrationMeasurementError(str(error)) from error
    print(json.dumps({
        "evidence_output": str(args.evidence_output),
        "evidence_sha256": evidence["evidence_sha256"],
        "observation_count": len(observations),
        "gate_status": gate["gate_status"],
        "heldout_freeze_authorized": gate["heldout_freeze_authorized"],
        "heldout_sidecar_loaded": False,
        "scientific_judgment_emitted": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "P1V3CalibrationMeasurementError",
    "build_calibration_evidence",
]
