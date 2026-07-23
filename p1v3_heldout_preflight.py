"""Freeze the P1v3 heldout policy-actuation budget after calibration passes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from collections.abc import Mapping

from hswm_weight_snapshot import canonical_sha256
from p1_llm_answerer import RetrievedDocumentV1
from p1v2_l0_harness import render_answer_prompt
from p1v2_l0_preflight import make_qwen_chat_padder
from p1v2_prompt_parity import ExactPromptPadderPort, build_prompt_parity_plan
from p1v3_calibration_preflight import (
    build_policy_training_oracle,
    file_sha256,
    tokenizer_identity_from_deployment,
    write_once,
)
from p1v3_policy_environment import build_policy_memory_contexts


SCHEMA_VERSION = "hswm-p1v3-policy-heldout-budget/v1"
FROZEN_MODULES = (
    "hswm_weight_snapshot.py",
    "p1_llm_answerer.py",
    "p1v2_typed_lesson.py",
    "p1v2_prompt_parity.py",
    "p1v2_tokenizer_adapter.py",
    "p1v2_l0_harness.py",
    "p1v2_llm_answerer.py",
    "p1v2_l0_preflight.py",
    "p1v3_policy_environment.py",
    "p1v3_calibration_gate.py",
    "p1v3_prepare.py",
    "p1v3_calibration_preflight.py",
    "p1v3_heldout_preflight.py",
    "p1v3_heldout_measure.py",
    "p1v3_heldout_judge.py",
)


class P1V3HeldoutPreflightError(ValueError):
    pass


def _verify_self_hash(value: Mapping[str, object], key: str, label: str) -> None:
    unsigned = dict(value)
    declared = unsigned.pop(key, None)
    if not isinstance(declared, str) or canonical_sha256(unsigned) != declared:
        raise P1V3HeldoutPreflightError(f"{label} self-hash drifted")


def verify_calibration_authorization(
    calibration: Mapping[str, object], *, public: Mapping[str, object]
) -> str:
    _verify_self_hash(calibration, "evidence_sha256", "calibration evidence")
    gate = calibration.get("calibration_gate")
    boundary = calibration.get("data_boundary")
    if not isinstance(gate, Mapping) or not isinstance(boundary, Mapping):
        raise P1V3HeldoutPreflightError("calibration evidence schema drifted")
    _verify_self_hash(gate, "calibration_receipt_sha256", "calibration gate")
    if (
        gate.get("gate_status") != "CALIBRATION_PASS"
        or gate.get("heldout_freeze_authorized") is not True
        or gate.get("heldout_outcomes_inspected") is not False
        or boundary.get("heldout_sidecar_loaded") is not False
        or boundary.get("heldout_outcomes_inspected") is not False
    ):
        raise P1V3HeldoutPreflightError("development calibration did not authorize heldout")
    if (
        boundary.get("public_manifest_sha256") != public.get("public_manifest_sha256")
        or boundary.get("development_sidecar_sha256")
        != public.get("development_sidecar_sha256")
        or boundary.get("heldout_sidecar_sha256")
        != public.get("heldout_sidecar_sha256")
    ):
        raise P1V3HeldoutPreflightError("calibration evidence binds a different split")
    return str(gate["calibration_receipt_sha256"])


def build_heldout_budget(
    *,
    public: Mapping[str, object],
    development: Mapping[str, object],
    calibration_evidence: Mapping[str, object],
    sidecar_separation: Mapping[str, object],
    padder: ExactPromptPadderPort,
    public_file_sha256: str,
    development_file_sha256: str,
    heldout_file_sha256: str,
    sidecar_separation_receipt_file_sha256: str,
    calibration_evidence_file_sha256: str,
    deployment_receipt_sha256: str,
    deployment_file_sha256: str,
    module_sha256: Mapping[str, str],
    model: str,
    model_revision: str,
    max_output_tokens: int = 512,
    seed: int = 9173,
    minimum_typed_improvements: int = 3,
) -> dict[str, object]:
    calibration_receipt_sha = verify_calibration_authorization(
        calibration_evidence, public=public
    )
    _training, lesson, transcript, boundary_receipt = build_policy_training_oracle(
        public, development
    )
    if set(module_sha256) != set(FROZEN_MODULES):
        raise P1V3HeldoutPreflightError("outcome module hash cut drifted")
    separation_public = sidecar_separation.get("public")
    separation_development = sidecar_separation.get("development")
    separation_heldout = sidecar_separation.get("heldout")
    if not all(
        isinstance(value, Mapping)
        for value in (separation_public, separation_development, separation_heldout)
    ):
        raise P1V3HeldoutPreflightError("sidecar separation receipt schema drifted")
    if (
        separation_public.get("manifest_sha256") != public["public_manifest_sha256"]
        or separation_development.get("sidecar_sha256")
        != development["development_sidecar_sha256"]
        or separation_heldout.get("sidecar_sha256") != public["heldout_sidecar_sha256"]
        or separation_heldout.get("file_sha256") != heldout_file_sha256
    ):
        raise P1V3HeldoutPreflightError("sidecar separation receipt binds another split")
    rows = public["splits"]["heldout"]
    if not isinstance(rows, list) or len(rows) != 6:
        raise P1V3HeldoutPreflightError("frozen heldout cut must contain six cases")
    if not isinstance(minimum_typed_improvements, int) or not (
        1 <= minimum_typed_improvements <= len(rows)
    ):
        raise P1V3HeldoutPreflightError("heldout improvement threshold is invalid")
    plans: list[dict[str, object]] = []
    for row in rows:
        documents_raw = row.get("documents")
        if not isinstance(documents_raw, list):
            raise P1V3HeldoutPreflightError("public heldout documents are unavailable")
        try:
            documents = tuple(
                RetrievedDocumentV1(**dict(document)) for document in documents_raw
            )
            case_id = str(row["case_id"])
            question = str(row["question"])
        except (KeyError, TypeError, ValueError) as error:
            raise P1V3HeldoutPreflightError("public heldout case is invalid") from error
        contexts = build_policy_memory_contexts(
            question=question,
            admitted_lesson=lesson,
            raw_training_transcript=transcript,
        )
        parity = build_prompt_parity_plan(
            contexts,
            render_prompt=lambda context, question=question, documents=documents: render_answer_prompt(
                question, documents, context
            ),
            padder=padder,
        )
        plans.append({
            "case_id": case_id,
            "public_case_sha256": row["public_case_sha256"],
            "document_ids": [document.source_id for document in documents],
            "document_cut_sha256": canonical_sha256({
                "documents": [document.canonical() for document in documents]
            }),
            "target_input_tokens_per_arm": parity.target_prompt_tokens,
            "prompt_sha256": dict(parity.prompt_sha256),
            "parity_receipt_sha256": parity.parity_receipt_sha256,
        })
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "stage": "P1V3_HELDOUT_POLICY_ACTUATION",
        "measurement_state": "FROZEN_UNRUN",
        "model": {
            "served_model": model,
            "model_revision": model_revision,
            "deployment_receipt_sha256": deployment_receipt_sha256,
            "deployment_file_sha256": deployment_file_sha256,
            "temperature": 0,
            "seed": seed,
            "max_output_tokens": max_output_tokens,
            "thinking_enabled": False,
        },
        "data": {
            "public_manifest_sha256": public["public_manifest_sha256"],
            "public_file_sha256": public_file_sha256,
            "development_sidecar_sha256": development[
                "development_sidecar_sha256"
            ],
            "development_file_sha256": development_file_sha256,
            "heldout_sidecar_sha256": public["heldout_sidecar_sha256"],
            "heldout_file_sha256": heldout_file_sha256,
            "sidecar_separation_receipt_file_sha256": sidecar_separation_receipt_file_sha256,
            "calibration_evidence_sha256": calibration_evidence["evidence_sha256"],
            "calibration_evidence_file_sha256": calibration_evidence_file_sha256,
            "calibration_receipt_sha256": calibration_receipt_sha,
            "development_boundary_receipt_sha256": boundary_receipt,
            "heldout_case_count": len(plans),
            "heldout_gold_values_or_cardinality_inspected_for_planning": False,
            "gold_open_policy": "after_all_four_answers_for_each_heldout_case",
        },
        "oracle": {
            "lesson_id": lesson.lesson_id,
            "compiler_receipt_sha256": lesson.compiler_receipt_sha256,
            "raw_training_transcript_sha256": canonical_sha256({
                "transcript": transcript
            }),
        },
        "parity": {
            "tokenizer_identity": padder.tokenizer_identity,
            "padding_identity": padder.padding_identity,
            "model_calls_per_case_per_arm": 1,
            "physical_model_calls_total": len(plans) * 4,
            "case_plans": plans,
        },
        "score_contract": {
            "primary_metric": "typed_improvement_count_vs_no_memory",
            "baseline": 0,
            "direction": "higher",
            "minimum_typed_improvements_for_pass": minimum_typed_improvements,
            "required_valid_case_count": len(plans),
            "raw_transcript_is_reported_not_a_pass_gate": True,
        },
        "module_sha256": dict(sorted(module_sha256.items())),
        "scientific_judgment_emitted": False,
    }
    if any(key.casefold() == "verdict" for key in _recursive_keys(manifest)):
        raise P1V3HeldoutPreflightError("heldout budget contains scientific judgment")
    manifest["budget_manifest_sha256"] = canonical_sha256(manifest)
    return manifest


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
    parser.add_argument("--sidecar-separation-receipt", type=Path, required=True)
    parser.add_argument("--calibration-evidence", type=Path, required=True)
    parser.add_argument("--deployment-receipt", type=Path, required=True)
    parser.add_argument("--tokenizer-snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    public = json.loads(args.public_manifest.read_text(encoding="utf-8"))
    development = json.loads(args.development_sidecar.read_text(encoding="utf-8"))
    separation = json.loads(
        args.sidecar_separation_receipt.read_text(encoding="utf-8")
    )
    calibration = json.loads(args.calibration_evidence.read_text(encoding="utf-8"))
    deployment = json.loads(args.deployment_receipt.read_text(encoding="utf-8"))
    here = Path(__file__).resolve().parent
    padder = make_qwen_chat_padder(
        args.tokenizer_snapshot,
        tokenizer_identity=tokenizer_identity_from_deployment(deployment),
    )
    manifest = build_heldout_budget(
        public=public,
        development=development,
        calibration_evidence=calibration,
        sidecar_separation=separation,
        padder=padder,
        public_file_sha256=file_sha256(args.public_manifest),
        development_file_sha256=file_sha256(args.development_sidecar),
        heldout_file_sha256=separation["heldout"]["file_sha256"],
        sidecar_separation_receipt_file_sha256=file_sha256(
            args.sidecar_separation_receipt
        ),
        calibration_evidence_file_sha256=file_sha256(args.calibration_evidence),
        deployment_receipt_sha256=deployment["receipt_sha256"],
        deployment_file_sha256=file_sha256(args.deployment_receipt),
        module_sha256={module: file_sha256(here / module) for module in FROZEN_MODULES},
        model=deployment["served_model"],
        model_revision=deployment["server_process"]["revision_binding"],
    )
    write_once(args.output, manifest)
    print(json.dumps({
        "budget_manifest_sha256": manifest["budget_manifest_sha256"],
        "heldout_cases": manifest["data"]["heldout_case_count"],
        "physical_model_calls_total": manifest["parity"]["physical_model_calls_total"],
        "minimum_typed_improvements_for_pass": manifest["score_contract"][
            "minimum_typed_improvements_for_pass"
        ],
        "output": str(args.output),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "FROZEN_MODULES",
    "P1V3HeldoutPreflightError",
    "build_heldout_budget",
    "verify_calibration_authorization",
]
