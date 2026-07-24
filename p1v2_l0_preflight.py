"""Build the frozen P1v2 L0 retrieval/parity budget without model calls."""
from __future__ import annotations

import argparse
from hashlib import sha256
import importlib.metadata
import json
import os
from pathlib import Path
import tempfile
from collections.abc import Mapping, Sequence
from typing import Any

from hswm_weight_snapshot import canonical_sha256
from p1v2_l0_harness import render_answer_prompt
from p1v2_l0_prepare import verify_l0_manifests
from p1v2_llm_answerer import P1V2_SYSTEM_PROMPT
from p1v2_prompt_parity import ExactPromptPadderPort, build_prompt_parity_plan
from p1v2_tokenizer_adapter import FrozenTokenizerPromptPadder
from p1v2_type6_environment import (
    build_l0_memory_contexts,
    render_training_transcript,
    retrieve_exact_attribute_documents,
    verify_type6_oracle_admission,
)
from p1v2_typed_lesson import LessonCompilePolicyV1, TypedLessonV1, compile_typed_lesson


SCHEMA_VERSION = "hswm-p1v2-l0-budget-manifest/v1"
ORACLE_INSTRUCTION = (
    "Inspect every supplied document for the exact requested attribute value, "
    "return the complete set of matching document titles, and do not stop after "
    "the first match."
)
FROZEN_MODULES = (
    "hswm_weight_snapshot.py",
    "p1_llm_answerer.py",
    "p1v2_typed_lesson.py",
    "p1v2_prompt_parity.py",
    "p1v2_tokenizer_adapter.py",
    "p1v2_l0_harness.py",
    "p1v2_llm_answerer.py",
    "p1v2_l0_prepare.py",
    "p1v2_type6_environment.py",
    "p1v2_l0_preflight.py",
)


class L0PreflightError(ValueError):
    pass


def _file_sha(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_training_oracle(
    public: Mapping[str, object],
    sealed: Mapping[str, object],
) -> tuple[TypedLessonV1, str, str]:
    verify_l0_manifests(public, sealed)
    splits = public["splits"]
    training_rows = splits["training"]
    if not isinstance(training_rows, list) or not training_rows:
        raise L0PreflightError("public manifest has no training case")
    training = training_rows[0]
    case_id = training["case_id"]
    sealed_row = sealed["cases"].get(case_id)
    if not isinstance(sealed_row, Mapping) or sealed_row.get("split") != "training":
        raise L0PreflightError("training case is not available in the sealed cut")
    gold_answers = sealed_row.get("gold_answers")
    if not isinstance(gold_answers, list) or not gold_answers:
        raise L0PreflightError("training gold evidence is unavailable")
    episode_id = f"training:{case_id}"
    evidence_id = "training-evidence:" + canonical_sha256({
        "case_id": case_id,
        "question_sha256": canonical_sha256({"question": training["question"]}),
        "verified_gold_answers": sorted(gold_answers),
        "sealed_gold_sha256": sealed["sealed_gold_sha256"],
    })
    recorded = {
        "schema_version": "hswm-p1v2-operational-verdict/v1",
        "source_episode_ids": [episode_id],
        "evidence_ids": [evidence_id],
        "verdict_type": "GENERALIZATION",
        "scope_predicate": {
            "all_terms": ["who is", "the person whose"],
            "any_terms": ["occupation", "hobby", "date of birth", "gender"],
            "excluded_terms": [],
        },
        "instruction": ORACLE_INSTRUCTION,
        "polarity": "DO",
        "confidence": 1.0,
        "supersedes": [],
    }
    heldout_ids = tuple(row["case_id"] for row in splits["heldout"])
    lesson = compile_typed_lesson(
        recorded,
        LessonCompilePolicyV1(
            allowed_episode_ids=(episode_id,),
            allowed_evidence_ids=(evidence_id,),
            forbidden_identifiers=heldout_ids,
        ),
    )
    admission_receipt = verify_type6_oracle_admission(lesson)
    transcript = render_training_transcript(
        case_id=episode_id,
        question=training["question"],
        verified_gold_answers=gold_answers,
        evidence_id=evidence_id,
    )
    return lesson, transcript, admission_receipt


def build_budget_manifest(
    *,
    public: Mapping[str, object],
    sealed: Mapping[str, object],
    articles: Sequence[Mapping[str, Any]],
    padder: ExactPromptPadderPort,
    deployment_receipt_sha256: str,
    deployment_file_sha256: str,
    generation_receipt_sha256: str,
    module_sha256: Mapping[str, str],
    model: str,
    model_revision: str,
    max_output_tokens: int = 256,
    seed: int = 9173,
    eligibility_min_documents: int = 2,
    eligibility_max_documents: int = 10,
) -> dict[str, object]:
    lesson, transcript, admission_receipt = build_training_oracle(public, sealed)
    heldout = public["splits"]["heldout"]
    case_plans: list[dict[str, object]] = []
    excluded_case_ids: list[str] = []
    for row in heldout:
        question = row["question"]
        all_documents = retrieve_exact_attribute_documents(
            question, articles, top_k=len(articles)
        )
        if not eligibility_min_documents <= len(all_documents) <= eligibility_max_documents:
            excluded_case_ids.append(row["case_id"])
            continue
        documents = all_documents
        contexts = build_l0_memory_contexts(
            question=question,
            admitted_lesson=lesson,
            raw_training_transcript=transcript,
        )
        parity = build_prompt_parity_plan(
            contexts,
            render_prompt=lambda context, question=question, documents=documents: (
                render_answer_prompt(question, documents, context)
            ),
            padder=padder,
        )
        case_plans.append({
            "case_id": row["case_id"],
            "public_case_sha256": row["case_sha256"],
            "retrieved_document_ids": [document.source_id for document in documents],
            "retrieved_document_count": len(documents),
            "target_input_tokens_per_arm": parity.target_prompt_tokens,
            "prompt_sha256": dict(parity.prompt_sha256),
            "parity_receipt_sha256": parity.parity_receipt_sha256,
        })
    if set(module_sha256) != set(FROZEN_MODULES):
        raise L0PreflightError("outcome module hash cut drifted")
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "stage": "L0_ORACLE_ACTUATION",
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
            "sealed_gold_sha256": sealed["sealed_gold_sha256"],
            "generation_receipt_sha256": generation_receipt_sha256,
            "heldout_case_count": len(case_plans),
            "excluded_public_heldout_case_count": len(excluded_case_ids),
            "excluded_public_heldout_case_ids": sorted(excluded_case_ids),
            "eligibility": {
                "source": "public_question_plus_article_exact_match_count_only",
                "minimum_retrieved_documents": eligibility_min_documents,
                "maximum_retrieved_documents": eligibility_max_documents,
                "sealed_answer_values_or_cardinality_inspected": False,
            },
            "gold_open_policy": "after_all_four_answers_for_each_case",
        },
        "oracle": {
            "lesson_id": lesson.lesson_id,
            "compiler_receipt_sha256": lesson.compiler_receipt_sha256,
            "admission_receipt_sha256": admission_receipt,
            "raw_training_transcript_sha256": canonical_sha256({"transcript": transcript}),
        },
        "parity": {
            "tokenizer_identity": padder.tokenizer_identity,
            "padding_identity": padder.padding_identity,
            "model_calls_per_case_per_arm": 1,
            "physical_model_calls_total": len(case_plans) * 4,
            "retrieval_calls_per_case_per_arm": 1,
            "case_plans": case_plans,
        },
        "module_sha256": dict(sorted(module_sha256.items())),
        "scientific_judgment_emitted": False,
    }
    if any(key.casefold() == "verdict" for key in _recursive_keys(manifest)):
        raise L0PreflightError("budget manifest must not contain scientific judgment")
    manifest["budget_manifest_sha256"] = canonical_sha256(manifest)
    return manifest


def make_qwen_chat_padder(snapshot_path: Path, *, tokenizer_identity: str):
    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise L0PreflightError("transformers is required for deployed-tokenizer parity") from error
    tokenizer = AutoTokenizer.from_pretrained(
        snapshot_path, local_files_only=True, trust_remote_code=True
    )

    def encode_user_prompt(user_prompt: str):
        encoded = tokenizer.apply_chat_template(
            [
                {"role": "system", "content": P1V2_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            tokenize=True,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        if isinstance(encoded, Mapping):
            encoded = encoded.get("input_ids")
        return encoded

    return FrozenTokenizerPromptPadder(
        encode=encode_user_prompt,
        tokenizer_identity=tokenizer_identity,
        inert_fragments=(" x", " ZXQPAD", "\nZXQPAD", " ZXQPAD.", " ZXQPAD ZXQPAD"),
    )


def _recursive_keys(value: object):
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key)
            yield from _recursive_keys(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _recursive_keys(item)


def _write_once(path: Path, value: object) -> None:
    encoded = (json.dumps(
        value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
    ) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != encoded:
            raise L0PreflightError("refusing to overwrite a different budget manifest")
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
    parser.add_argument("--public-manifest", type=Path, required=True)
    parser.add_argument("--sealed-gold", type=Path, required=True)
    parser.add_argument("--articles", type=Path, required=True)
    parser.add_argument("--deployment-receipt", type=Path, required=True)
    parser.add_argument("--generation-receipt", type=Path, required=True)
    parser.add_argument("--tokenizer-snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    public = json.loads(args.public_manifest.read_text(encoding="utf-8"))
    sealed = json.loads(args.sealed_gold.read_text(encoding="utf-8"))
    articles = json.loads(args.articles.read_text(encoding="utf-8"))
    deployment = json.loads(args.deployment_receipt.read_text(encoding="utf-8"))
    generation = json.loads(args.generation_receipt.read_text(encoding="utf-8"))
    here = Path(__file__).resolve().parent
    module_hashes = {module: _file_sha(here / module) for module in FROZEN_MODULES}
    tokenizer_identity = canonical_sha256({
        "schema_version": "hswm-p1v2-qwen-chat-tokenizer/v1",
        "model_revision": deployment["server_process"]["revision_binding"],
        "tokenizer_config_sha256": deployment["snapshot"]["tokenizer_config_sha256"],
        "chat_template_sha256": next(
            item["sha256"] for item in deployment["snapshot"]["metadata_files"]
            if item["path"] == "chat_template.jinja"
        ),
        "system_prompt_sha256": canonical_sha256({"prompt": P1V2_SYSTEM_PROMPT}),
        "transformers_version": importlib.metadata.version("transformers"),
        "thinking_enabled": False,
    })
    padder = make_qwen_chat_padder(
        args.tokenizer_snapshot, tokenizer_identity=tokenizer_identity
    )
    manifest = build_budget_manifest(
        public=public,
        sealed=sealed,
        articles=articles,
        padder=padder,
        deployment_receipt_sha256=deployment["receipt_sha256"],
        deployment_file_sha256=_file_sha(args.deployment_receipt),
        generation_receipt_sha256=generation["generation_receipt_sha256"],
        module_sha256=module_hashes,
        model=deployment["served_model"],
        model_revision=deployment["server_process"]["revision_binding"],
    )
    _write_once(args.output, manifest)
    print(json.dumps({
        "budget_manifest_sha256": manifest["budget_manifest_sha256"],
        "heldout_cases": manifest["data"]["heldout_case_count"],
        "physical_model_calls_total": manifest["parity"]["physical_model_calls_total"],
        "output": str(args.output),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["FROZEN_MODULES", "L0PreflightError", "build_budget_manifest", "build_training_oracle"]
