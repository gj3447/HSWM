"""Freeze the P1v3 development-only real-model calibration budget.

This boundary accepts the public manifest and the development sidecar only.  A
heldout sidecar path is deliberately not part of either the Python API or CLI.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import importlib.metadata
import json
import os
from pathlib import Path
import tempfile
from collections.abc import Mapping

from hswm_weight_snapshot import canonical_sha256
from p1_llm_answerer import RetrievedDocumentV1
from p1v2_l0_harness import render_answer_prompt
from p1v2_l0_preflight import make_qwen_chat_padder
from p1v2_llm_answerer import P1V2_SYSTEM_PROMPT
from p1v2_prompt_parity import ExactPromptPadderPort, build_prompt_parity_plan
from p1v3_policy_environment import (
    PolicyConflictCaseV1,
    build_policy_memory_contexts,
    compile_policy_oracle_lesson,
    render_policy_training_transcript,
)
from p1v3_prepare import DEVELOPMENT_SCHEMA_VERSION, PUBLIC_SCHEMA_VERSION


SCHEMA_VERSION = "hswm-p1v3-policy-calibration-budget/v1"
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
    "p1v3_calibration_measure.py",
)


class P1V3CalibrationPreflightError(ValueError):
    pass


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_self_hash(value: Mapping[str, object], key: str, label: str) -> str:
    unsigned = dict(value)
    declared = unsigned.pop(key, None)
    if not isinstance(declared, str) or canonical_sha256(unsigned) != declared:
        raise P1V3CalibrationPreflightError(f"{label} self-hash drifted")
    return declared


def verify_development_boundary(
    public: Mapping[str, object], development: Mapping[str, object]
) -> str:
    """Verify development without accepting or opening the heldout sidecar."""

    if public.get("schema_version") != PUBLIC_SCHEMA_VERSION:
        raise P1V3CalibrationPreflightError("public manifest schema drifted")
    if development.get("schema_version") != DEVELOPMENT_SCHEMA_VERSION:
        raise P1V3CalibrationPreflightError("development sidecar schema drifted")
    public_sha = _verify_self_hash(
        public, "public_manifest_sha256", "public manifest"
    )
    development_sha = _verify_self_hash(
        development, "development_sidecar_sha256", "development sidecar"
    )
    if public.get("development_sidecar_sha256") != development_sha:
        raise P1V3CalibrationPreflightError(
            "public manifest does not bind the development sidecar"
        )
    heldout_sha = public.get("heldout_sidecar_sha256")
    if not isinstance(heldout_sha, str) or len(heldout_sha) != 64:
        raise P1V3CalibrationPreflightError("public heldout binding is missing")
    if public.get("universe") != development.get("universe"):
        raise P1V3CalibrationPreflightError("public and development universes differ")
    if development.get("allowed_splits") != ["training", "calibration"]:
        raise P1V3CalibrationPreflightError(
            "development sidecar is authorized for a non-development split"
        )
    splits = public.get("splits")
    cases = development.get("cases")
    if not isinstance(splits, Mapping) or not isinstance(cases, Mapping):
        raise P1V3CalibrationPreflightError("development split schema drifted")
    expected_ids = {
        row["case_id"]
        for split in ("training", "calibration")
        for row in splits.get(split, [])
        if isinstance(row, Mapping) and isinstance(row.get("case_id"), str)
    }
    heldout_ids = {
        row["case_id"]
        for row in splits.get("heldout", [])
        if isinstance(row, Mapping) and isinstance(row.get("case_id"), str)
    }
    if not expected_ids or set(cases) != expected_ids:
        raise P1V3CalibrationPreflightError(
            "development sidecar case cut differs from public development IDs"
        )
    if set(cases) & heldout_ids:
        raise P1V3CalibrationPreflightError(
            "heldout outcome entered the development sidecar"
        )
    for case_id, row in cases.items():
        if not isinstance(row, Mapping) or row.get("split") not in {
            "training", "calibration"
        }:
            raise P1V3CalibrationPreflightError(
                f"development case {case_id} crossed the split boundary"
            )
    return canonical_sha256({
        "schema_version": "hswm-p1v3-development-boundary-receipt/v1",
        "public_manifest_sha256": public_sha,
        "development_sidecar_sha256": development_sha,
        "heldout_sidecar_sha256": heldout_sha,
        "development_case_ids": sorted(expected_ids),
        "future_heldout_case_ids_sha256": canonical_sha256({
            "case_ids": sorted(heldout_ids)
        }),
        "heldout_sidecar_loaded": False,
    })


def policy_case_from_manifests(
    public_row: Mapping[str, object], sealed_row: Mapping[str, object]
) -> PolicyConflictCaseV1:
    public_unsigned = dict(public_row)
    public_case_sha = public_unsigned.pop("public_case_sha256", None)
    if not isinstance(public_case_sha, str) or canonical_sha256(public_unsigned) != public_case_sha:
        raise P1V3CalibrationPreflightError("public case self-hash drifted")
    if public_row.get("case_id") != sealed_row.get("case_id"):
        raise P1V3CalibrationPreflightError("public and development case IDs differ")
    if public_row.get("split") != sealed_row.get("split"):
        raise P1V3CalibrationPreflightError("public and development case splits differ")
    if public_row.get("derivation_sha256") != sealed_row.get("derivation_sha256"):
        raise P1V3CalibrationPreflightError("public and development derivations differ")
    documents = public_row.get("documents")
    if not isinstance(documents, list):
        raise P1V3CalibrationPreflightError("public case documents are unavailable")
    try:
        return PolicyConflictCaseV1(
            case_id=str(public_row["case_id"]),
            question=str(public_row["question"]),
            documents=tuple(RetrievedDocumentV1(**dict(row)) for row in documents),
            expected_answers=tuple(sealed_row["expected_answers"]),
            trusted_source_ids=tuple(sealed_row["trusted_source_ids"]),
            distractor_source_ids=tuple(sealed_row["distractor_source_ids"]),
            trusted_class=str(sealed_row["trusted_class"]),
            distractor_class=str(sealed_row["distractor_class"]),
            derivation_sha256=str(sealed_row["derivation_sha256"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise P1V3CalibrationPreflightError(
            "policy case reconstruction failed"
        ) from error


def build_policy_training_oracle(
    public: Mapping[str, object], development: Mapping[str, object]
):
    boundary_receipt = verify_development_boundary(public, development)
    training_rows = public["splits"]["training"]
    if not isinstance(training_rows, list) or len(training_rows) != 1:
        raise P1V3CalibrationPreflightError("exactly one training case is required")
    public_row = training_rows[0]
    sealed_row = development["cases"].get(public_row["case_id"])
    if not isinstance(sealed_row, Mapping) or sealed_row.get("split") != "training":
        raise P1V3CalibrationPreflightError("training outcome is unavailable")
    case = policy_case_from_manifests(public_row, sealed_row)
    heldout_ids = tuple(row["case_id"] for row in public["splits"]["heldout"])
    lesson = compile_policy_oracle_lesson(
        case, forbidden_identifiers=heldout_ids
    )
    transcript = render_policy_training_transcript(case)
    return case, lesson, transcript, boundary_receipt


def build_calibration_budget(
    *,
    public: Mapping[str, object],
    development: Mapping[str, object],
    padder: ExactPromptPadderPort,
    public_file_sha256: str,
    development_file_sha256: str,
    deployment_receipt_sha256: str,
    deployment_file_sha256: str,
    module_sha256: Mapping[str, str],
    model: str,
    model_revision: str,
    max_output_tokens: int = 512,
    seed: int = 9173,
) -> dict[str, object]:
    _training, lesson, transcript, boundary_receipt = build_policy_training_oracle(
        public, development
    )
    if set(module_sha256) != set(FROZEN_MODULES):
        raise P1V3CalibrationPreflightError("outcome module hash cut drifted")
    calibration_rows = public["splits"]["calibration"]
    if not isinstance(calibration_rows, list) or len(calibration_rows) < 3:
        raise P1V3CalibrationPreflightError("at least three calibration cases are required")
    plans: list[dict[str, object]] = []
    for row in calibration_rows:
        sealed_row = development["cases"].get(row["case_id"])
        if not isinstance(sealed_row, Mapping) or sealed_row.get("split") != "calibration":
            raise P1V3CalibrationPreflightError("calibration outcome is unavailable")
        case = policy_case_from_manifests(row, sealed_row)
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
        plans.append({
            "case_id": case.case_id,
            "public_case_sha256": row["public_case_sha256"],
            "document_ids": [document.source_id for document in case.documents],
            "document_cut_sha256": canonical_sha256({
                "documents": [document.canonical() for document in case.documents]
            }),
            "target_input_tokens_per_arm": parity.target_prompt_tokens,
            "prompt_sha256": dict(parity.prompt_sha256),
            "parity_receipt_sha256": parity.parity_receipt_sha256,
        })
    heldout_ids = tuple(row["case_id"] for row in public["splits"]["heldout"])
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "stage": "P1V3_DEVELOPMENT_CALIBRATION",
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
            "heldout_sidecar_loaded": False,
            "heldout_outcomes_inspected": False,
            "development_boundary_receipt_sha256": boundary_receipt,
            "calibration_case_count": len(plans),
            "future_heldout_case_count": len(heldout_ids),
            "future_heldout_case_ids_sha256": canonical_sha256({
                "case_ids": sorted(heldout_ids)
            }),
            "gold_open_policy": "after_all_four_answers_for_each_calibration_case",
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
        "module_sha256": dict(sorted(module_sha256.items())),
        "scientific_judgment_emitted": False,
    }
    if any(key.casefold() == "verdict" for key in _recursive_keys(manifest)):
        raise P1V3CalibrationPreflightError(
            "calibration budget must not contain scientific judgment"
        )
    manifest["budget_manifest_sha256"] = canonical_sha256(manifest)
    return manifest


def tokenizer_identity_from_deployment(deployment: Mapping[str, object]) -> str:
    metadata = deployment["snapshot"]["metadata_files"]
    return canonical_sha256({
        "schema_version": "hswm-p1v3-qwen-chat-tokenizer/v1",
        "model_revision": deployment["server_process"]["revision_binding"],
        "tokenizer_config_sha256": deployment["snapshot"]["tokenizer_config_sha256"],
        "chat_template_sha256": next(
            item["sha256"] for item in metadata
            if item["path"] == "chat_template.jinja"
        ),
        "system_prompt_sha256": canonical_sha256({"prompt": P1V2_SYSTEM_PROMPT}),
        "transformers_version": importlib.metadata.version("transformers"),
        "thinking_enabled": False,
    })


def _recursive_keys(value: object):
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key)
            yield from _recursive_keys(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _recursive_keys(item)


def write_once(path: Path, value: object) -> None:
    encoded = (json.dumps(
        value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
    ) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != encoded:
            raise P1V3CalibrationPreflightError(
                "refusing to overwrite a different calibration artifact"
            )
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_path = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    temporary = Path(raw_path)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-manifest", type=Path, required=True)
    parser.add_argument("--development-sidecar", type=Path, required=True)
    parser.add_argument("--deployment-receipt", type=Path, required=True)
    parser.add_argument("--tokenizer-snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    public = json.loads(args.public_manifest.read_text(encoding="utf-8"))
    development = json.loads(args.development_sidecar.read_text(encoding="utf-8"))
    deployment = json.loads(args.deployment_receipt.read_text(encoding="utf-8"))
    here = Path(__file__).resolve().parent
    padder = make_qwen_chat_padder(
        args.tokenizer_snapshot,
        tokenizer_identity=tokenizer_identity_from_deployment(deployment),
    )
    manifest = build_calibration_budget(
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
    )
    write_once(args.output, manifest)
    print(json.dumps({
        "budget_manifest_sha256": manifest["budget_manifest_sha256"],
        "calibration_cases": manifest["data"]["calibration_case_count"],
        "physical_model_calls_total": manifest["parity"][
            "physical_model_calls_total"
        ],
        "heldout_sidecar_loaded": False,
        "output": str(args.output),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "FROZEN_MODULES",
    "P1V3CalibrationPreflightError",
    "build_calibration_budget",
    "build_policy_training_oracle",
    "file_sha256",
    "policy_case_from_manifests",
    "tokenizer_identity_from_deployment",
    "verify_development_boundary",
    "write_once",
]
