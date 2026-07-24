"""L0 typed-lesson actuation harness that emits observations, never a verdict."""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Mapping, Protocol, Sequence

from hswm_weight_snapshot import canonical_sha256
from p1_llm_answerer import RetrievedDocumentV1
from p1v2_prompt_parity import ARM_IDS, PromptParityPlanV1


OBSERVATION_SCHEMA_VERSION = "hswm-p1v2-l0-observation/v1"
EVIDENCE_SCHEMA_VERSION = "lakato-evidence-record/v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


class L0HarnessError(ValueError):
    pass


@dataclass(frozen=True)
class L0AnswerReceiptV1:
    arm_id: str
    request_sha256: str
    answers: tuple[str, ...]
    user_prompt_tokens: int
    logical_call_count: int = 1


class L0AnswerPort(Protocol):
    adapter_identity: str

    def answer(
        self,
        *,
        arm_id: str,
        question: str,
        documents: Sequence[RetrievedDocumentV1],
        user_prompt: str,
        idempotency_key: str,
    ) -> L0AnswerReceiptV1: ...


def render_answer_prompt(
    question: str,
    documents: Sequence[RetrievedDocumentV1],
    memory_context: str,
) -> str:
    if not question or not documents:
        raise L0HarnessError("question and retrieved documents must be non-empty")
    payload = {
        "schema_version": "hswm-p1v2-answer-input/v1",
        "question": question,
        "documents": [document.canonical() for document in documents],
        "memory_context": memory_context,
    }
    serialized = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    lowered = serialized.casefold()
    for forbidden_key in ("gold_answer", "evaluation_label", "solution_trace"):
        if f'"{forbidden_key}"' in lowered:
            raise L0HarnessError("answer prompt crossed the sealed evaluator boundary")
    return serialized


def _answer_set(values: Sequence[str]) -> set[str]:
    normalized = {" ".join(value.casefold().split()) for value in values if value.strip()}
    if not normalized:
        raise L0HarnessError("gold answers must contain non-empty text")
    return normalized


def run_l0_observation(
    *,
    case_id: str,
    question: str,
    documents: Sequence[RetrievedDocumentV1],
    sealed_gold_answers: Sequence[str],
    parity_plan: PromptParityPlanV1,
    answerer: L0AnswerPort,
) -> dict[str, object]:
    """Run four equal-prompt-token calls, then open gold only for evaluation."""

    if not case_id or not answerer.adapter_identity:
        raise L0HarnessError("case and answer adapter identities must be non-empty")
    if set(parity_plan.rendered_prompts) != set(ARM_IDS):
        raise L0HarnessError("parity plan is missing a registered arm")
    parity_plan.verify()
    receipts: dict[str, L0AnswerReceiptV1] = {}
    for arm in ARM_IDS:
        idempotency_key = canonical_sha256({
            "schema_version": OBSERVATION_SCHEMA_VERSION,
            "case_id": case_id,
            "arm_id": arm,
            "prompt_sha256": parity_plan.prompt_sha256[arm],
            "adapter_identity": answerer.adapter_identity,
        })
        receipt = answerer.answer(
            arm_id=arm,
            question=question,
            documents=tuple(documents),
            user_prompt=parity_plan.rendered_prompts[arm],
            idempotency_key=idempotency_key,
        )
        if receipt.arm_id != arm or receipt.logical_call_count != 1:
            raise L0HarnessError("answer receipt violates arm or call-count parity")
        if receipt.user_prompt_tokens != parity_plan.target_prompt_tokens:
            raise L0HarnessError("answer receipt violates exact prompt-token parity")
        if receipt.request_sha256 != idempotency_key:
            raise L0HarnessError("answer receipt does not bind the requested intent")
        receipts[arm] = receipt

    gold = _answer_set(sealed_gold_answers)
    rows: dict[str, dict[str, object]] = {}
    for arm in ARM_IDS:
        receipt = receipts[arm]
        predicted = {" ".join(value.casefold().split()) for value in receipt.answers}
        rows[arm] = {
            "request_sha256": receipt.request_sha256,
            "answers_sha256": canonical_sha256({"answers": sorted(predicted)}),
            "set_match": int(predicted == gold),
            "user_prompt_tokens": receipt.user_prompt_tokens,
            "logical_call_count": receipt.logical_call_count,
        }
    observations = {
        "schema_version": OBSERVATION_SCHEMA_VERSION,
        "case_id": case_id,
        "question_sha256": canonical_sha256({"question": question}),
        "document_ids": [document.source_id for document in documents],
        "parity_receipt_sha256": parity_plan.parity_receipt_sha256,
        "answer_adapter_identity": answerer.adapter_identity,
        "arms": rows,
        "measurements": {
            "typed_minus_no_memory": (
                rows["T1_typed_lesson"]["set_match"]
                - rows["T3_no_memory"]["set_match"]
            ),
            "typed_minus_raw_transcript": (
                rows["T1_typed_lesson"]["set_match"]
                - rows["T2_raw_transcript"]["set_match"]
            ),
            "typed_minus_shuffled_or_removed": (
                rows["T1_typed_lesson"]["set_match"]
                - rows["T4_shuffled_or_removed"]["set_match"]
            ),
        },
        "budget": {
            "logical_model_calls": sum(row["logical_call_count"] for row in rows.values()),
            "user_prompt_tokens_per_arm": parity_plan.target_prompt_tokens,
            "token_parity": len({row["user_prompt_tokens"] for row in rows.values()}) == 1,
        },
        "gold_boundary": {
            "gold_sent_to_answer_port": False,
            "gold_opened_only_after_all_arm_answers": True,
            "gold_values_published": False,
        },
    }
    observations["observation_sha256"] = canonical_sha256(observations)
    return observations


def build_lakato_evidence_record(
    *,
    programme: str,
    branch: str,
    conjecture: str,
    preregistration_sha256: str,
    prediction_receipt_sha256: str,
    data_manifest_sha256: str,
    harness_command: Sequence[str],
    harness_cwd: str,
    git_commit: str,
    environment: Mapping[str, str],
    observations: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Package grounded measurement evidence without importing a judge."""

    if not observations:
        raise L0HarnessError("at least one observation is required")
    for value, label in (
        (preregistration_sha256, "preregistration"),
        (prediction_receipt_sha256, "prediction receipt"),
        (data_manifest_sha256, "data manifest"),
    ):
        if not _SHA256.fullmatch(value):
            raise L0HarnessError(f"{label} must be a lowercase SHA-256")
    if not _GIT_SHA.fullmatch(git_commit):
        raise L0HarnessError("git_commit must be a 40-character lowercase SHA")
    if not all((programme, branch, conjecture, harness_cwd)) or not harness_command:
        raise L0HarnessError("evidence identity, command, and cwd must be non-empty")
    record: dict[str, object] = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "programme": programme,
        "branch": branch,
        "conjecture": conjecture,
        "preregistration_sha256": preregistration_sha256,
        "prediction_receipt_sha256": prediction_receipt_sha256,
        "measurement": {
            "metric": "min(mean_paired_exact_set_match_T1_minus_T3,mean_paired_exact_set_match_T1_minus_T2)",
            "unit": "exact_set_match_rate_difference",
            "scope": "P1v2 L0/L1 typed-lesson comparison",
            "observations": [dict(item) for item in observations],
        },
        "grounded_status": "GROUNDED_MEASUREMENT_NO_SCIENTIFIC_VERDICT",
        "provenance": {
            "data_manifest_sha256": data_manifest_sha256,
            "harness_command": list(harness_command),
            "harness_cwd": harness_cwd,
            "git_commit": git_commit,
            "environment": dict(environment),
        },
        "findings": [],
    }
    if any(key == "verdict" for key in _recursive_keys(record)):
        raise L0HarnessError("measurement evidence must not contain a verdict")
    record["evidence_sha256"] = canonical_sha256(record)
    verify_lakato_evidence_record(record)
    return record


def verify_lakato_evidence_record(record: Mapping[str, object]) -> None:
    """Read back a measurement record and reject tamper or self-judgment."""

    if record.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        raise L0HarnessError("unsupported Lakato evidence schema")
    if any(key == "verdict" for key in _recursive_keys(record)):
        raise L0HarnessError("measurement evidence must not contain a verdict")
    unsigned = dict(record)
    declared = unsigned.pop("evidence_sha256", None)
    if not isinstance(declared, str) or canonical_sha256(unsigned) != declared:
        raise L0HarnessError("evidence self-hash does not bind canonical bytes")


def _recursive_keys(value: object):
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key)
            yield from _recursive_keys(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _recursive_keys(item)
