"""Generate positive and injected-negative receipts for the real L0 judge."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from hswm_weight_snapshot import canonical_sha256
from p1v2_l0_harness import build_lakato_evidence_record
from p1v2_l0_judge import judge_l0, make_contradiction_receipt
from p1v2_prompt_parity import ARM_IDS
from p1v2_type6_environment import Type6EnvironmentError, verify_type6_oracle_admission
from p1v2_typed_lesson import LessonCompilePolicyV1, compile_typed_lesson


def _file_sha(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fixture_observation() -> dict[str, object]:
    arms = {}
    for arm in ARM_IDS:
        typed = arm == "T1_typed_lesson"
        arms[arm] = {
            "request_sha256": canonical_sha256({"fixture_arm": arm}),
            "answers_sha256": canonical_sha256({"fixture_answer": "right" if typed else "wrong"}),
            "set_match": int(typed),
            "user_prompt_tokens": 100,
            "logical_call_count": 1,
        }
    observation: dict[str, object] = {
        "schema_version": "hswm-p1v2-l0-observation/v1",
        "case_id": "fixture:case:1",
        "question_sha256": "1" * 64,
        "document_ids": ["fixture:source:1"],
        "parity_receipt_sha256": "2" * 64,
        "answer_adapter_identity": "fixture-recorded-answerer:v1",
        "arms": arms,
        "measurements": {
            "typed_minus_no_memory": 1,
            "typed_minus_raw_transcript": 1,
            "typed_minus_shuffled_or_removed": 1,
        },
        "budget": {
            "logical_model_calls": 4,
            "user_prompt_tokens_per_arm": 100,
            "token_parity": True,
        },
        "gold_boundary": {
            "gold_sent_to_answer_port": False,
            "gold_opened_only_after_all_arm_answers": True,
            "gold_values_published": False,
        },
    }
    observation["observation_sha256"] = canonical_sha256(observation)
    return observation


def _fixture_evidence() -> dict[str, object]:
    return build_lakato_evidence_record(
        programme="LakatosTree_HSWM_20260719",
        branch="P1v2-typed-verdict-lesson",
        conjecture="fixture typed lesson actuates heldout behavior",
        preregistration_sha256="3" * 64,
        prediction_receipt_sha256="4" * 64,
        data_manifest_sha256="5" * 64,
        harness_command=("python", "fixture"),
        harness_cwd="/fixture",
        git_commit="6" * 40,
        environment={"fixture": "true"},
        observations=(_fixture_observation(),),
    )


def _fixture_budget() -> dict[str, object]:
    budget: dict[str, object] = {
        "schema_version": "hswm-p1v2-l0-budget-manifest/v1",
        "measurement_state": "FROZEN_UNRUN",
        "parity": {"case_plans": [{
            "case_id": "fixture:case:1",
            "parity_receipt_sha256": "2" * 64,
            "target_input_tokens_per_arm": 100,
        }]},
        "scientific_judgment_emitted": False,
    }
    budget["budget_manifest_sha256"] = canonical_sha256(budget)
    return budget


def _real_contradiction_refusal() -> dict[str, object]:
    candidate = compile_typed_lesson(
        {
            "schema_version": "hswm-p1v2-operational-verdict/v1",
            "source_episode_ids": ["fixture:training"],
            "evidence_ids": ["fixture:evidence"],
            "verdict_type": "GENERALIZATION",
            "scope_predicate": {
                "all_terms": ["who is", "the person whose"],
                "any_terms": ["occupation"],
                "excluded_terms": [],
            },
            "instruction": "Inspect every supplied document but return only the first match.",
            "polarity": "DO",
            "confidence": 1.0,
            "supersedes": [],
        },
        LessonCompilePolicyV1(
            allowed_episode_ids=("fixture:training",),
            allowed_evidence_ids=("fixture:evidence",),
        ),
    )
    guard_sha = _file_sha(Path(__file__).with_name("p1v2_type6_environment.py"))
    try:
        verify_type6_oracle_admission(candidate)
    except Type6EnvironmentError as error:
        return make_contradiction_receipt(
            candidate_lesson_sha256=candidate.lesson_id,
            admission_guard_sha256=guard_sha,
            rejected=True,
            error_class=type(error).__name__,
        )
    return make_contradiction_receipt(
        candidate_lesson_sha256=candidate.lesson_id,
        admission_guard_sha256=guard_sha,
        rejected=False,
        error_class=None,
    )


def run_fixtures(output_directory: Path) -> dict[str, object]:
    output_directory.mkdir(parents=True, exist_ok=True)
    evidence = _fixture_evidence()
    budget = _fixture_budget()
    contradiction = _real_contradiction_refusal()
    positive = judge_l0(evidence, budget, contradiction)
    injected = make_contradiction_receipt(
        candidate_lesson_sha256=contradiction["candidate_lesson_sha256"],
        admission_guard_sha256=contradiction["admission_guard_sha256"],
        rejected=False,
        error_class=None,
    )
    negative = judge_l0(evidence, budget, injected)
    if positive["verdict"] != "PASS" or negative["verdict"] != "KILL":
        raise RuntimeError("real L0 judge did not separate positive and injected-negative fixtures")
    artifacts = {
        "contradiction_refusal": contradiction,
        "positive_judge_receipt": positive,
        "injected_negative_judge_receipt": negative,
    }
    paths: dict[str, dict[str, str]] = {}
    for name, value in artifacts.items():
        path = output_directory / f"p1v2_l0_{name}_20260724.json"
        path.write_text(
            json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        paths[name] = {"path": str(path), "file_sha256": _file_sha(path)}
    manifest: dict[str, object] = {
        "schema_version": "hswm-p1v2-l0-judge-fixture-manifest/v1",
        "judge_script_sha256": _file_sha(Path(__file__).with_name("p1v2_l0_judge.py")),
        "fixture_runner_sha256": _file_sha(Path(__file__)),
        "positive_expected": "PASS",
        "injected_negative_expected": "KILL",
        "artifacts": paths,
    }
    manifest["fixture_manifest_sha256"] = canonical_sha256(manifest)
    manifest_path = output_directory / "p1v2_l0_judge_fixture_manifest_20260724.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    manifest = run_fixtures(args.output_directory)
    print(json.dumps({
        "fixture_manifest_sha256": manifest["fixture_manifest_sha256"],
        "positive_expected": manifest["positive_expected"],
        "injected_negative_expected": manifest["injected_negative_expected"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
