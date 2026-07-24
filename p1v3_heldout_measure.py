"""Execute the server-preregistered P1v3 heldout measurement without judging it."""
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
from p1v3_calibration_preflight import (
    build_policy_training_oracle,
    file_sha256,
    policy_case_from_manifests,
    write_once,
)
from p1v3_heldout_preflight import FROZEN_MODULES, build_heldout_budget
from p1v3_policy_environment import build_policy_memory_contexts
from p1v3_prepare import verify_policy_manifests


EVIDENCE_SCHEMA_VERSION = "hswm-p1v3-policy-heldout-evidence/v1"
PREREG_SCHEMA_VERSION = "hswm-p1v3-preregistration/v1"


class P1V3HeldoutMeasurementError(RuntimeError):
    pass


def _verify_self_hash(value: Mapping[str, object], key: str, label: str) -> None:
    unsigned = dict(value)
    declared = unsigned.pop(key, None)
    if not isinstance(declared, str) or canonical_sha256(unsigned) != declared:
        raise P1V3HeldoutMeasurementError(f"{label} self-hash drifted")


def preregistration_guard(
    prereg: Mapping[str, object],
    *,
    here: Path,
    public: Mapping[str, object],
    development: Mapping[str, object],
    heldout: Mapping[str, object],
    calibration: Mapping[str, object],
    budget: Mapping[str, object],
    deployment_file_sha256: str,
    prediction_receipt_file_sha256: str,
) -> None:
    if prereg.get("schema_version") != PREREG_SCHEMA_VERSION:
        raise P1V3HeldoutMeasurementError("preregistration schema drifted")
    if (
        prereg.get("registration_state") != "SERVER_REGISTERED_FROZEN_UNRUN"
        or prereg.get("registered_before_measurement") is not True
    ):
        raise P1V3HeldoutMeasurementError("heldout measurement lacks prior registration")
    _verify_self_hash(prereg, "preregistration_sha256", "preregistration")
    expected_modules = prereg.get("module_sha256")
    if not isinstance(expected_modules, Mapping) or set(expected_modules) != set(
        FROZEN_MODULES
    ):
        raise P1V3HeldoutMeasurementError("preregistered module cut drifted")
    for module in FROZEN_MODULES:
        current = file_sha256(here / module)
        if expected_modules[module] != current or budget["module_sha256"][module] != current:
            raise P1V3HeldoutMeasurementError(f"frozen outcome module drift: {module}")
    locks = prereg.get("locks")
    if not isinstance(locks, Mapping):
        raise P1V3HeldoutMeasurementError("preregistration locks are missing")
    expected_locks = {
        "public_manifest_sha256": public["public_manifest_sha256"],
        "development_sidecar_sha256": development["development_sidecar_sha256"],
        "heldout_sidecar_sha256": heldout["heldout_sidecar_sha256"],
        "calibration_evidence_sha256": calibration["evidence_sha256"],
        "budget_manifest_sha256": budget["budget_manifest_sha256"],
        "deployment_file_sha256": deployment_file_sha256,
        "prediction_receipt_file_sha256": prediction_receipt_file_sha256,
    }
    for key, value in expected_locks.items():
        if locks.get(key) != value:
            raise P1V3HeldoutMeasurementError(f"preregistration lock drift: {key}")
    frozen_commit = locks.get("git_commit")
    if (
        not isinstance(frozen_commit, str)
        or subprocess.run(
            ["git", "merge-base", "--is-ancestor", frozen_commit, "HEAD"],
            cwd=here,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode != 0
    ):
        raise P1V3HeldoutMeasurementError("frozen source commit is not an ancestor")


def build_heldout_evidence(
    *,
    preregistration_sha256: str,
    prediction_receipt_sha256: str,
    budget: Mapping[str, object],
    observations: Sequence[Mapping[str, object]],
    command: Sequence[str],
    cwd: str,
    runtime_commit: str,
    environment: Mapping[str, str],
) -> dict[str, object]:
    if not observations or not command or not cwd or len(runtime_commit) != 40:
        raise P1V3HeldoutMeasurementError("heldout evidence identity is incomplete")
    evidence: dict[str, object] = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "programme": "LakatosTree_HSWM_20260719",
        "branch": "p1v3-nonredundant-policy-actuation",
        "conjecture": (
            "A training-derived typed source policy changes and improves frozen-model "
            "heldout answers versus no memory on the fresh seed-3 conflict cut."
        ),
        "preregistration_sha256": preregistration_sha256,
        "prediction_receipt_sha256": prediction_receipt_sha256,
        "budget_manifest_sha256": budget["budget_manifest_sha256"],
        "data_manifest_sha256": budget["data"]["public_manifest_sha256"],
        "observations": [dict(observation) for observation in observations],
        "measurement_contract": dict(budget["score_contract"]),
        "grounded_status": "GROUNDED_MEASUREMENT_NO_SCIENTIFIC_JUDGMENT",
        "provenance": {
            "command": list(command),
            "cwd": cwd,
            "runtime_commit": runtime_commit,
            "environment": dict(environment),
        },
        "scientific_judgment_emitted": False,
    }
    if any(key.casefold() == "verdict" for key in _recursive_keys(evidence)):
        raise P1V3HeldoutMeasurementError("measurement evidence attempted self-judgment")
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
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--prediction-receipt", type=Path, required=True)
    parser.add_argument("--public-manifest", type=Path, required=True)
    parser.add_argument("--development-sidecar", type=Path, required=True)
    parser.add_argument("--heldout-sidecar", type=Path, required=True)
    parser.add_argument("--sidecar-separation-receipt", type=Path, required=True)
    parser.add_argument("--calibration-evidence", type=Path, required=True)
    parser.add_argument("--deployment-receipt", type=Path, required=True)
    parser.add_argument("--budget-manifest", type=Path, required=True)
    parser.add_argument("--tokenizer-snapshot", type=Path, required=True)
    parser.add_argument("--answer-db", type=Path, required=True)
    parser.add_argument("--evidence-output", type=Path, required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    prereg = json.loads(args.preregistration.read_text(encoding="utf-8"))
    prediction = json.loads(args.prediction_receipt.read_text(encoding="utf-8"))
    public = json.loads(args.public_manifest.read_text(encoding="utf-8"))
    development = json.loads(args.development_sidecar.read_text(encoding="utf-8"))
    heldout = json.loads(args.heldout_sidecar.read_text(encoding="utf-8"))
    separation = json.loads(
        args.sidecar_separation_receipt.read_text(encoding="utf-8")
    )
    calibration = json.loads(args.calibration_evidence.read_text(encoding="utf-8"))
    deployment = json.loads(args.deployment_receipt.read_text(encoding="utf-8"))
    budget = json.loads(args.budget_manifest.read_text(encoding="utf-8"))
    verify_policy_manifests(public, development, heldout)
    _verify_self_hash(budget, "budget_manifest_sha256", "heldout budget")
    preregistration_guard(
        prereg,
        here=here,
        public=public,
        development=development,
        heldout=heldout,
        calibration=calibration,
        budget=budget,
        deployment_file_sha256=file_sha256(args.deployment_receipt),
        prediction_receipt_file_sha256=file_sha256(args.prediction_receipt),
    )
    for expected, observed, label in (
        (budget["data"]["public_file_sha256"], file_sha256(args.public_manifest), "public"),
        (
            budget["data"]["development_file_sha256"],
            file_sha256(args.development_sidecar),
            "development",
        ),
        (budget["data"]["heldout_file_sha256"], file_sha256(args.heldout_sidecar), "heldout"),
        (
            budget["data"]["sidecar_separation_receipt_file_sha256"],
            file_sha256(args.sidecar_separation_receipt),
            "sidecar separation receipt",
        ),
        (
            budget["data"]["calibration_evidence_file_sha256"],
            file_sha256(args.calibration_evidence),
            "calibration evidence",
        ),
    ):
        if expected != observed:
            raise P1V3HeldoutMeasurementError(f"{label} file hash drifted")

    padder = make_qwen_chat_padder(
        args.tokenizer_snapshot,
        tokenizer_identity=budget["parity"]["tokenizer_identity"],
    )
    rebuilt = build_heldout_budget(
        public=public,
        development=development,
        calibration_evidence=calibration,
        sidecar_separation=separation,
        padder=padder,
        public_file_sha256=file_sha256(args.public_manifest),
        development_file_sha256=file_sha256(args.development_sidecar),
        heldout_file_sha256=file_sha256(args.heldout_sidecar),
        sidecar_separation_receipt_file_sha256=file_sha256(
            args.sidecar_separation_receipt
        ),
        calibration_evidence_file_sha256=file_sha256(args.calibration_evidence),
        deployment_receipt_sha256=deployment["receipt_sha256"],
        deployment_file_sha256=file_sha256(args.deployment_receipt),
        module_sha256={module: file_sha256(here / module) for module in FROZEN_MODULES},
        model=deployment["served_model"],
        model_revision=deployment["server_process"]["revision_binding"],
        max_output_tokens=budget["model"]["max_output_tokens"],
        seed=budget["model"]["seed"],
        minimum_typed_improvements=budget["score_contract"][
            "minimum_typed_improvements_for_pass"
        ],
    )
    if rebuilt != budget:
        raise P1V3HeldoutMeasurementError("runtime inputs do not reproduce heldout budget")

    _training, lesson, transcript, _boundary = build_policy_training_oracle(
        public, development
    )
    public_rows = {row["case_id"]: row for row in public["splits"]["heldout"]}
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
            row = public_rows[case_id]
            sealed_row = heldout["cases"].get(case_id)
            if not isinstance(sealed_row, Mapping):
                raise P1V3HeldoutMeasurementError("heldout gold is unavailable")
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
            plan = plans[case_id]
            if (
                parity.parity_receipt_sha256 != plan["parity_receipt_sha256"]
                or parity.target_prompt_tokens != plan["target_input_tokens_per_arm"]
                or dict(parity.prompt_sha256) != plan["prompt_sha256"]
            ):
                raise P1V3HeldoutMeasurementError("heldout prompt plan drifted")
            observations.append(run_l0_observation(
                case_id=case.case_id,
                question=case.question,
                documents=case.documents,
                sealed_gold_answers=case.expected_answers,
                parity_plan=parity,
                answerer=answerer,
            ))

    prediction_sha = prediction.get("prediction_receipt_sha256")
    if not isinstance(prediction_sha, str):
        raise P1V3HeldoutMeasurementError("prediction receipt inner hash is missing")
    runtime_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=here, text=True
    ).strip()
    evidence = build_heldout_evidence(
        preregistration_sha256=prereg["preregistration_sha256"],
        prediction_receipt_sha256=prediction_sha,
        budget=budget,
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
    write_once(args.evidence_output, evidence)
    print(json.dumps({
        "evidence_output": str(args.evidence_output),
        "evidence_sha256": evidence["evidence_sha256"],
        "observation_count": len(observations),
        "scientific_judgment_emitted": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "P1V3HeldoutMeasurementError",
    "build_heldout_evidence",
    "preregistration_guard",
]
