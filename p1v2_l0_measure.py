"""Execute the server-registered P1v2 L0 measurement and emit no verdict."""
from __future__ import annotations

import argparse
from hashlib import sha256
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from collections.abc import Mapping

from p1_llm_answerer import P1AnswererConfigV1
from p1v2_l0_harness import (
    build_lakato_evidence_record,
    render_answer_prompt,
    run_l0_observation,
)
from p1v2_l0_preflight import (
    FROZEN_MODULES as PREFLIGHT_MODULES,
    build_budget_manifest,
    build_training_oracle,
    make_qwen_chat_padder,
)
from p1v2_l0_prepare import verify_l0_manifests
from p1v2_llm_answerer import RecordedP1V2Answerer
from p1v2_prompt_parity import build_prompt_parity_plan
from p1v2_type6_environment import (
    build_l0_memory_contexts,
    retrieve_exact_attribute_documents,
)


FROZEN_OUTCOME_MODULES = tuple(sorted(set(PREFLIGHT_MODULES) | {
    "p1v2_l0_measure.py",
}))
PREREG_SCHEMA = "hswm-preregistration/v1"


class L0MeasurementError(RuntimeError):
    pass


def _file_sha(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_self_hash(value: Mapping[str, object], key: str) -> None:
    unsigned = dict(value)
    declared = unsigned.pop(key, None)
    from hswm_weight_snapshot import canonical_sha256
    if not isinstance(declared, str) or canonical_sha256(unsigned) != declared:
        raise L0MeasurementError(f"{key} does not bind canonical bytes")


def preregistration_guard(
    prereg: Mapping[str, object],
    *,
    here: Path,
    public: Mapping[str, object],
    budget: Mapping[str, object],
    deployment_file_sha256: str,
    prediction_receipt_file_sha256: str,
) -> None:
    if prereg.get("schema") != PREREG_SCHEMA:
        raise L0MeasurementError("preregistration schema drifted")
    if prereg.get("registration_state") != "SERVER_REGISTERED_FROZEN_UNRUN":
        raise L0MeasurementError("measurement is forbidden before server registration")
    if prereg.get("registered_before_measurement") is not True:
        raise L0MeasurementError("preregistration does not precede measurement")
    expected_modules = prereg.get("module_sha256")
    if not isinstance(expected_modules, Mapping) or set(expected_modules) != set(
        FROZEN_OUTCOME_MODULES
    ):
        raise L0MeasurementError("outcome module hash cut drifted")
    for module in FROZEN_OUTCOME_MODULES:
        if expected_modules[module] != _file_sha(here / module):
            raise L0MeasurementError(f"frozen outcome module drift: {module}")
    locks = prereg.get("frozen_l0_locks")
    if not isinstance(locks, Mapping):
        raise L0MeasurementError("frozen L0 locks are missing")
    expected = {
        "public_manifest_sha256": public["public_manifest_sha256"],
        "budget_manifest_sha256": budget["budget_manifest_sha256"],
        "deployment_file_sha256": deployment_file_sha256,
        "prediction_receipt_file_sha256": prediction_receipt_file_sha256,
    }
    for key, value in expected.items():
        if locks.get(key) != value:
            raise L0MeasurementError(f"frozen L0 lock drift: {key}")
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
        raise L0MeasurementError("frozen outcome commit is not an ancestor of HEAD")


def _write_once(path: Path, value: object) -> None:
    encoded = (json.dumps(
        value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
    ) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != encoded:
            raise L0MeasurementError("refusing to overwrite different measurement evidence")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_path = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    temp_path = Path(raw_path)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--prediction-receipt", type=Path, required=True)
    parser.add_argument("--public-manifest", type=Path, required=True)
    parser.add_argument("--sealed-gold", type=Path, required=True)
    parser.add_argument("--articles", type=Path, required=True)
    parser.add_argument("--deployment-receipt", type=Path, required=True)
    parser.add_argument("--generation-receipt", type=Path, required=True)
    parser.add_argument("--budget-manifest", type=Path, required=True)
    parser.add_argument("--tokenizer-snapshot", type=Path, required=True)
    parser.add_argument("--answer-db", type=Path, required=True)
    parser.add_argument("--evidence-output", type=Path, required=True)
    args = parser.parse_args()

    here = Path(__file__).resolve().parent
    prereg = json.loads(args.preregistration.read_text(encoding="utf-8"))
    prediction = json.loads(args.prediction_receipt.read_text(encoding="utf-8"))
    public = json.loads(args.public_manifest.read_text(encoding="utf-8"))
    sealed = json.loads(args.sealed_gold.read_text(encoding="utf-8"))
    articles = json.loads(args.articles.read_text(encoding="utf-8"))
    deployment = json.loads(args.deployment_receipt.read_text(encoding="utf-8"))
    generation = json.loads(args.generation_receipt.read_text(encoding="utf-8"))
    budget = json.loads(args.budget_manifest.read_text(encoding="utf-8"))
    verify_l0_manifests(public, sealed)
    _verify_self_hash(budget, "budget_manifest_sha256")
    preregistration_guard(
        prereg,
        here=here,
        public=public,
        budget=budget,
        deployment_file_sha256=_file_sha(args.deployment_receipt),
        prediction_receipt_file_sha256=_file_sha(args.prediction_receipt),
    )

    padder = make_qwen_chat_padder(
        args.tokenizer_snapshot,
        tokenizer_identity=budget["parity"]["tokenizer_identity"],
    )
    rebuilt = build_budget_manifest(
        public=public,
        sealed=sealed,
        articles=articles,
        padder=padder,
        deployment_receipt_sha256=deployment["receipt_sha256"],
        deployment_file_sha256=_file_sha(args.deployment_receipt),
        generation_receipt_sha256=generation["generation_receipt_sha256"],
        module_sha256={
            module: _file_sha(here / module) for module in PREFLIGHT_MODULES
        },
        model=deployment["served_model"],
        model_revision=deployment["server_process"]["revision_binding"],
        max_output_tokens=budget["model"]["max_output_tokens"],
        seed=budget["model"]["seed"],
    )
    if rebuilt != budget:
        raise L0MeasurementError("runtime inputs do not reproduce the frozen budget")

    lesson, transcript, _admission = build_training_oracle(public, sealed)
    public_rows = {
        row["case_id"]: row for row in public["splits"]["heldout"]
    }
    plan_by_case = {
        plan["case_id"]: plan for plan in budget["parity"]["case_plans"]
    }
    answer_config = P1AnswererConfigV1(
        endpoint=deployment["endpoint"],
        model=deployment["served_model"],
        model_revision=deployment["server_process"]["revision_binding"],
        deployment_receipt_sha256=deployment["receipt_sha256"],
        max_tokens=budget["model"]["max_output_tokens"],
        seed=budget["model"]["seed"],
    )
    observations = []
    with RecordedP1V2Answerer(
        args.answer_db,
        config=answer_config,
        count_user_prompt_tokens=padder.count_prompt_tokens,
        tokenizer_identity=padder.tokenizer_identity,
    ) as answerer:
        for case_id in sorted(plan_by_case):
            row = public_rows[case_id]
            documents = retrieve_exact_attribute_documents(
                row["question"], articles, top_k=10
            )
            contexts = build_l0_memory_contexts(
                question=row["question"],
                admitted_lesson=lesson,
                raw_training_transcript=transcript,
            )
            parity = build_prompt_parity_plan(
                contexts,
                render_prompt=lambda context, row=row, documents=documents: (
                    render_answer_prompt(row["question"], documents, context)
                ),
                padder=padder,
            )
            plan = plan_by_case[case_id]
            if (
                parity.parity_receipt_sha256 != plan["parity_receipt_sha256"]
                or parity.target_prompt_tokens != plan["target_input_tokens_per_arm"]
                or dict(parity.prompt_sha256) != plan["prompt_sha256"]
            ):
                raise L0MeasurementError("case prompt plan differs from frozen budget")
            sealed_row = sealed["cases"].get(case_id)
            if not isinstance(sealed_row, Mapping) or sealed_row.get("split") != "heldout":
                raise L0MeasurementError("heldout gold cut is unavailable")
            observations.append(run_l0_observation(
                case_id=case_id,
                question=row["question"],
                documents=documents,
                sealed_gold_answers=sealed_row["gold_answers"],
                parity_plan=parity,
                answerer=answerer,
            ))

    locks = prereg["frozen_l0_locks"]
    prediction_sha = prediction.get("prediction_receipt_sha256")
    if not isinstance(prediction_sha, str):
        prediction_sha = _file_sha(args.prediction_receipt)
    evidence = build_lakato_evidence_record(
        programme=prereg["programme"],
        branch=prereg["branch"],
        conjecture=prereg["conjecture"],
        preregistration_sha256=_file_sha(args.preregistration),
        prediction_receipt_sha256=prediction_sha,
        data_manifest_sha256=public["public_manifest_sha256"],
        harness_command=tuple(sys.argv),
        harness_cwd=str(Path.cwd()),
        git_commit=locks["git_commit"],
        environment={
            "python": sys.version.split()[0],
            "transformers": importlib.metadata.version("transformers"),
            "host": deployment["host"],
            "served_model": deployment["served_model"],
        },
        observations=tuple(observations),
    )
    _write_once(args.evidence_output, evidence)
    print(json.dumps({
        "evidence_output": str(args.evidence_output),
        "evidence_sha256": evidence["evidence_sha256"],
        "observation_count": len(observations),
        "scientific_judgment_emitted": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
