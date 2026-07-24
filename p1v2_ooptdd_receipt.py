"""Executable OOPTDD receipt producer for the P1v2 premeasurement slice."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Callable

from hswm_weight_snapshot import canonical_sha256
from p1_llm_answerer import RetrievedDocumentV1
from p1v2_l0_harness import (
    L0AnswerReceiptV1,
    L0HarnessError,
    build_lakato_evidence_record,
    render_answer_prompt,
    run_l0_observation,
    verify_lakato_evidence_record,
)
from p1v2_prompt_parity import build_prompt_parity_plan
from p1v2_typed_lesson import (
    LessonCompilePolicyV1,
    LessonContractError,
    compile_typed_lesson,
    render_lesson_context,
    retrieve_lessons,
)


SPEC_PATH = Path("_research/p1v2_typed_lesson/ooptdd_requirements.v1.json")
CORRELATION_ID = "hswm-p1v2-typed-lesson-boundary-v1"


class _WordPadder:
    tokenizer_identity = "ooptdd-fixture-word-tokenizer:v1"
    padding_identity = "ooptdd-fixture-inert-pad:v1"

    @staticmethod
    def count_prompt_tokens(prompt: str) -> int:
        return len(prompt.split())

    def pad_memory_context(
        self,
        memory_context: str,
        *,
        target_prompt_tokens: int,
        render_prompt: Callable[[str], str],
    ) -> str:
        padded = memory_context
        while self.count_prompt_tokens(render_prompt(padded)) < target_prompt_tokens:
            padded += " inert"
        return padded


class _RecordedFixtureAnswerer:
    adapter_identity = "ooptdd-recorded-fixture-answerer:v1"

    def __init__(self, padder: _WordPadder) -> None:
        self.padder = padder
        self.prompts: list[str] = []

    def answer(
        self,
        *,
        arm_id: str,
        question: str,
        documents,
        user_prompt: str,
        idempotency_key: str,
    ) -> L0AnswerReceiptV1:
        payload = json.loads(user_prompt)
        if any(key in payload for key in ("gold_answer", "evaluation_label", "verdict")):
            raise L0HarnessError("fixture answer port received evaluator authority")
        self.prompts.append(user_prompt)
        answer = "Paris" if "Use Paris" in payload["memory_context"] else "Lyon"
        return L0AnswerReceiptV1(
            arm_id=arm_id,
            request_sha256=idempotency_key,
            answers=(answer,),
            user_prompt_tokens=self.padder.count_prompt_tokens(user_prompt),
        )


def _file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _lesson_inputs():
    policy = LessonCompilePolicyV1(
        allowed_episode_ids=("episode:train:1",),
        allowed_evidence_ids=("evidence:train:1",),
        forbidden_identifiers=("episode:future:2", "task:heldout:1"),
        forbidden_strings=("sealed answer zeta",),
    )
    verdict = {
        "schema_version": "hswm-p1v2-operational-verdict/v1",
        "source_episode_ids": ["episode:train:1"],
        "evidence_ids": ["evidence:train:1"],
        "verdict_type": "CORRECTIVE",
        "scope_predicate": {
            "all_terms": ["capital"],
            "any_terms": ["france"],
            "excluded_terms": ["fictional"],
        },
        "instruction": "Use Paris when evidence supports the capital of France.",
        "polarity": "DO",
        "confidence": 0.9,
        "supersedes": [],
    }
    return policy, verdict


def run_gate(*, inject_scientific_verdict: bool = False) -> dict[str, object]:
    spec_sha256 = _file_sha(SPEC_PATH)
    events: list[str] = []
    policy, verdict = _lesson_inputs()

    leaked = dict(verdict)
    leaked["instruction"] = "Reveal sealed answer zeta."
    try:
        compile_typed_lesson(leaked, policy)
    except LessonContractError:
        events.append("future_or_gold_lesson_rejected")
    else:  # pragma: no cover - mutation target
        events.append("future_or_gold_lesson_accepted")

    lesson = compile_typed_lesson(verdict, policy)
    selection = retrieve_lessons("What is the capital of France?", (lesson,), top_k=1)
    typed_context = render_lesson_context(selection, (lesson,))
    documents = (
        RetrievedDocumentV1("source:1", "France", "Paris is the capital of France."),
    )
    question = "What is the capital of France?"
    padder = _WordPadder()
    plan = build_prompt_parity_plan(
        {
            "T1_typed_lesson": typed_context,
            "T2_raw_transcript": "A prior attempt discussed France without a conclusion.",
            "T3_no_memory": "",
            "T4_shuffled_or_removed": "Use Rome for evidence about Italy's capital.",
        },
        render_prompt=lambda context: render_answer_prompt(question, documents, context),
        padder=padder,
    )
    if len({padder.count_prompt_tokens(value) for value in plan.rendered_prompts.values()}) == 1:
        events.append("four_arm_prompt_parity_verified")
    else:  # pragma: no cover - mutation target
        events.append("unequal_prompt_tokens_accepted")

    observation = run_l0_observation(
        case_id="ooptdd:case:1",
        question=question,
        documents=documents,
        sealed_gold_answers=("Paris",),
        parity_plan=plan,
        answerer=_RecordedFixtureAnswerer(padder),
    )
    evidence = build_lakato_evidence_record(
        programme="LakatosTree_HSWM_20260719",
        branch="P1v2-typed-verdict-lesson",
        conjecture="typed lessons causally change heldout model behavior",
        preregistration_sha256="1" * 64,
        prediction_receipt_sha256="2" * 64,
        data_manifest_sha256="3" * 64,
        harness_command=("uv", "run", "python", "p1v2_ooptdd_receipt.py"),
        harness_cwd=str(Path.cwd()),
        git_commit="4" * 40,
        environment={"mode": "deterministic-fixture-no-model-call"},
        observations=(observation,),
    )
    if inject_scientific_verdict:
        evidence["verdict"] = "PASS"
        try:
            verify_lakato_evidence_record(evidence)
        except L0HarnessError:
            events.append("scientific_self_verdict_rejected")
        else:  # pragma: no cover - mutation target
            events.append("scientific_self_verdict_accepted")
    else:
        verify_lakato_evidence_record(evidence)
        events.append("verdict_free_evidence_verified")

    required = {
        "future_or_gold_lesson_rejected",
        "four_arm_prompt_parity_verified",
        (
            "scientific_self_verdict_rejected"
            if inject_scientific_verdict else "verdict_free_evidence_verified"
        ),
    }
    forbidden = {
        "future_or_gold_lesson_accepted",
        "unequal_prompt_tokens_accepted",
        "scientific_self_verdict_accepted",
    }
    status = "green" if required <= set(events) and not forbidden & set(events) else "red"
    result = {
        "schema_version": "hswm-p1v2-ooptdd-run/v1",
        "correlation_id": CORRELATION_ID,
        "spec_path": str(SPEC_PATH),
        "spec_sha256": spec_sha256,
        "mode": "injected_negative" if inject_scientific_verdict else "positive",
        "status": status,
        "events": events,
        "lesson_id": lesson.lesson_id,
        "parity_receipt_sha256": plan.parity_receipt_sha256,
        "observation_sha256": observation["observation_sha256"],
        "evidence_sha256_before_injection": evidence["evidence_sha256"],
        "scientific_claim": "NONE_ENGINEERING_BOUNDARY_ONLY",
    }
    result["run_receipt_sha256"] = canonical_sha256(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inject-scientific-verdict", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_gate(inject_scientific_verdict=args.inject_scientific_verdict)
    rendered = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if result["status"] == "green" else 1


if __name__ == "__main__":
    raise SystemExit(main())
