"""Executable OOPTDD producer for the P1v3 policy-actuation boundary."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from hswm_weight_snapshot import canonical_sha256
from p1v2_prompt_parity import ARM_IDS
from p1v2_typed_lesson import LessonCompilePolicyV1, compile_typed_lesson
from p1v3_calibration_gate import evaluate_policy_calibration
from p1v3_policy_environment import (
    PolicyEnvironmentError,
    build_policy_conflict_case,
    compile_policy_oracle_lesson,
    verify_policy_oracle_admission,
)


SPEC_PATH = Path("_research/p1v3_policy_actuation/ooptdd_requirements.v1.json")
CORRELATION_ID = "hswm-p1v3-nonredundant-policy-actuation-v1"
_ARTICLES = (
    {"title": "Alice", "article": "The occupation of Alice is baker."},
    {"title": "Bob", "article": "The occupation of Bob is carpenter."},
    {"title": "Carol", "article": "The occupation of Carol is singer."},
)
_QUESTION = "Who is the person whose occupation is baker?"


def _file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _observation(case_id: str, *, typed: int, no_memory: int) -> dict[str, object]:
    arms: dict[str, dict[str, object]] = {}
    for arm in ARM_IDS:
        match = typed if arm == "T1_typed_lesson" else no_memory
        answer = "right" if match else "wrong"
        arms[arm] = {
            "answers_sha256": canonical_sha256({"case": case_id, "answer": answer}),
            "set_match": match,
            "logical_call_count": 1,
        }
    return {
        "case_id": case_id,
        "arms": arms,
        "budget": {"logical_model_calls": 4, "token_parity": True},
        "gold_boundary": {
            "gold_sent_to_answer_port": False,
            "gold_opened_only_after_all_arm_answers": True,
            "gold_values_published": False,
        },
    }


def _compile_inverted(case):
    episode_id = "policy-training:" + case.case_id
    evidence_id = "policy-training-evidence:" + case.derivation_sha256
    return compile_typed_lesson(
        {
            "schema_version": "hswm-p1v2-operational-verdict/v1",
            "source_episode_ids": [episode_id],
            "evidence_ids": [evidence_id],
            "verdict_type": "GENERALIZATION",
            "scope_predicate": {
                "all_terms": ["who is", "the person whose"],
                "any_terms": ["occupation"],
                "excluded_terms": [],
            },
            "instruction": (
                "When records conflict, treat SOURCE_CLASS=TAU as authoritative, "
                "ignore SOURCE_CLASS=RHO, and cite only TAU records."
            ),
            "polarity": "DO",
            "confidence": 1.0,
            "supersedes": [],
        },
        LessonCompilePolicyV1(
            allowed_episode_ids=(episode_id,),
            allowed_evidence_ids=(evidence_id,),
        ),
    )


def run_gate(*, inject_ceiling_environment: bool = False) -> dict[str, object]:
    events: list[str] = []
    case = build_policy_conflict_case(
        case_id="policy-training:fixture",
        question=_QUESTION,
        articles=_ARTICLES,
    )
    public = case.public()
    encoded_public = json.dumps(public, sort_keys=True)
    if not any(
        private in encoded_public
        for private in ("expected_answers", "trusted_class", "distractor_class")
    ):
        events.append("public_packet_hides_gold_and_trust_semantics")
    else:  # pragma: no cover - mutation target
        events.append("public_packet_leaked_gold_or_trust_semantics")
    if (
        len(case.trusted_source_ids) == len(case.distractor_source_ids) > 0
        and len(case.documents)
        == len(case.trusted_source_ids) + len(case.distractor_source_ids)
    ):
        events.append("balanced_content_addressed_conflict_packet_verified")
    else:  # pragma: no cover - mutation target
        events.append("unbalanced_conflict_packet_accepted")

    admitted = compile_policy_oracle_lesson(case)
    try:
        verify_policy_oracle_admission(
            _compile_inverted(case), trusted_class="RHO", distractor_class="TAU"
        )
    except PolicyEnvironmentError:
        events.append("inverted_policy_lesson_rejected")
    else:  # pragma: no cover - mutation target
        events.append("inverted_policy_lesson_accepted")

    calibration_ids = ("cal:1", "cal:2", "cal:3")
    if inject_ceiling_environment:
        observations = tuple(
            _observation(case_id, typed=1, no_memory=1)
            for case_id in calibration_ids
        )
    else:
        observations = (
            _observation("cal:1", typed=1, no_memory=0),
            _observation("cal:2", typed=1, no_memory=1),
            _observation("cal:3", typed=1, no_memory=1),
        )
    calibration = evaluate_policy_calibration(
        observations,
        calibration_case_ids=calibration_ids,
        future_heldout_case_ids=("heldout:1", "heldout:2"),
        environment_sha256=case.derivation_sha256,
    )
    if inject_ceiling_environment:
        if (
            calibration["gate_status"] == "CALIBRATION_REJECT"
            and calibration["heldout_freeze_authorized"] is False
        ):
            events.append("ceiling_environment_rejected")
        else:  # pragma: no cover - mutation target
            events.append("ceiling_environment_authorized")
    elif (
        calibration["gate_status"] == "CALIBRATION_PASS"
        and calibration["heldout_freeze_authorized"] is True
    ):
        events.append("development_headroom_gate_passed")

    base_required = {
        "public_packet_hides_gold_and_trust_semantics",
        "balanced_content_addressed_conflict_packet_verified",
        "inverted_policy_lesson_rejected",
    }
    mode_event = (
        "ceiling_environment_rejected"
        if inject_ceiling_environment
        else "development_headroom_gate_passed"
    )
    forbidden = {
        "public_packet_leaked_gold_or_trust_semantics",
        "unbalanced_conflict_packet_accepted",
        "inverted_policy_lesson_accepted",
        "ceiling_environment_authorized",
    }
    status = (
        "green"
        if base_required | {mode_event} <= set(events)
        and not forbidden & set(events)
        else "red"
    )
    result: dict[str, object] = {
        "schema_version": "hswm-p1v3-ooptdd-run/v1",
        "correlation_id": CORRELATION_ID,
        "spec_path": str(SPEC_PATH),
        "spec_sha256": _file_sha(SPEC_PATH),
        "mode": "injected_ceiling" if inject_ceiling_environment else "positive",
        "status": status,
        "events": events,
        "case_derivation_sha256": case.derivation_sha256,
        "lesson_id": admitted.lesson_id,
        "calibration_receipt_sha256": calibration["calibration_receipt_sha256"],
        "scientific_claim": "NONE_ENVIRONMENT_ADMISSION_ONLY",
    }
    result["run_receipt_sha256"] = canonical_sha256(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inject-ceiling-environment", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_gate(inject_ceiling_environment=args.inject_ceiling_environment)
    rendered = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if result["status"] == "green" else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["run_gate"]
