from __future__ import annotations

from p1v2_l0_preflight import FROZEN_MODULES, build_budget_manifest
from p1v2_l0_prepare import build_l0_manifests


class CharacterPadder:
    tokenizer_identity = "fixture-chat-character-tokenizer:v1"
    padding_identity = "fixture-character-padding:v1"

    def count_prompt_tokens(self, prompt):
        return len(prompt)

    def pad_memory_context(self, memory_context, *, target_prompt_tokens, render_prompt):
        padded = memory_context
        while self.count_prompt_tokens(render_prompt(padded)) < target_prompt_tokens:
            padded += "x"
        return padded


def _questions():
    attributes = [
        ("occupation", "baker"),
        ("occupation", "trader"),
        ("hobby", "chess"),
    ]
    return [
        {
            "id": f"case-{index}",
            "question": f"Who is the person whose {attribute} is {value}?",
            "answer": [f"Person {index}"],
            "solution_traces": "sealed",
            "template": ["Who", "attribute", "value"],
            "type": 6,
            "difficulty": 1,
        }
        for index, (attribute, value) in enumerate(attributes)
    ]


def _articles():
    return [
        {"title": "Person 0", "article": "The occupation of Person 0 is baker."},
        {"title": "Person 1", "article": "The occupation of Person 1 is trader."},
        {"title": "Person 2", "article": "The hobby of Person 2 is chess."},
    ]


def test_preflight_freezes_all_case_parity_without_a_scientific_judgment():
    public, sealed = build_l0_manifests(
        _questions(),
        universe="fixture",
        dataset_file_sha256={"articles.json": "1" * 64},
        split_sizes={"training": 1, "heldout": 1, "retention": 1},
    )
    manifest = build_budget_manifest(
        public=public,
        sealed=sealed,
        articles=_articles(),
        padder=CharacterPadder(),
        deployment_receipt_sha256="2" * 64,
        deployment_file_sha256="3" * 64,
        generation_receipt_sha256="4" * 64,
        module_sha256={module: "5" * 64 for module in FROZEN_MODULES},
        model="fixed-model",
        model_revision="revision-1",
        eligibility_min_documents=1,
    )

    assert manifest["measurement_state"] == "FROZEN_UNRUN"
    assert manifest["data"]["heldout_case_count"] == 1
    assert manifest["parity"]["physical_model_calls_total"] == 4
    assert manifest["scientific_judgment_emitted"] is False
    assert "verdict" not in str(manifest).casefold()
    plan = manifest["parity"]["case_plans"][0]
    assert len(set(plan["prompt_sha256"].values())) == 3
    assert (
        plan["prompt_sha256"]["T3_no_memory"]
        == plan["prompt_sha256"]["T4_shuffled_or_removed"]
    )
    assert len(manifest["budget_manifest_sha256"]) == 64
