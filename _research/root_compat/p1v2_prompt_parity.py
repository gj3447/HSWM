"""Exact prompt-token parity planning behind an injected tokenizer/padder port."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Protocol

from hswm_weight_snapshot import canonical_sha256


ARM_IDS = (
    "T1_typed_lesson",
    "T2_raw_transcript",
    "T3_no_memory",
    "T4_shuffled_or_removed",
)
SCHEMA_VERSION = "hswm-p1v2-prompt-parity/v1"


class PromptParityError(ValueError):
    pass


class ExactPromptPadderPort(Protocol):
    tokenizer_identity: str
    padding_identity: str

    def count_prompt_tokens(self, prompt: str) -> int: ...

    def pad_memory_context(
        self,
        memory_context: str,
        *,
        target_prompt_tokens: int,
        render_prompt: Callable[[str], str],
    ) -> str: ...


@dataclass(frozen=True)
class PromptParityPlanV1:
    target_prompt_tokens: int
    padded_memory_contexts: Mapping[str, str]
    rendered_prompts: Mapping[str, str]
    prompt_sha256: Mapping[str, str]
    tokenizer_identity: str
    padding_identity: str
    parity_receipt_sha256: str
    schema_version: str = SCHEMA_VERSION

    def canonical(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "target_prompt_tokens": self.target_prompt_tokens,
            "prompt_sha256": dict(self.prompt_sha256),
            "tokenizer_identity": self.tokenizer_identity,
            "padding_identity": self.padding_identity,
            "parity_receipt_sha256": self.parity_receipt_sha256,
        }

    def verify(self) -> None:
        for value in (
            self.padded_memory_contexts,
            self.rendered_prompts,
            self.prompt_sha256,
        ):
            if set(value) != set(ARM_IDS):
                raise PromptParityError("parity plan arm set drifted")
        observed_hashes = {
            arm: canonical_sha256({"prompt": self.rendered_prompts[arm]})
            for arm in ARM_IDS
        }
        if observed_hashes != dict(self.prompt_sha256):
            raise PromptParityError("prompt hashes do not bind rendered prompts")
        expected = canonical_sha256({
            "schema_version": self.schema_version,
            "target_prompt_tokens": self.target_prompt_tokens,
            "prompt_sha256": dict(self.prompt_sha256),
            "tokenizer_identity": self.tokenizer_identity,
            "padding_identity": self.padding_identity,
        })
        if expected != self.parity_receipt_sha256:
            raise PromptParityError("parity receipt does not bind the prompt plan")


def build_prompt_parity_plan(
    memory_contexts: Mapping[str, str],
    *,
    render_prompt: Callable[[str], str],
    padder: ExactPromptPadderPort,
) -> PromptParityPlanV1:
    if set(memory_contexts) != set(ARM_IDS):
        raise PromptParityError("all and only the four registered arms are required")
    if not padder.tokenizer_identity or not padder.padding_identity:
        raise PromptParityError("tokenizer and padding identities must be recorded")
    original = {arm: str(memory_contexts[arm]) for arm in ARM_IDS}
    initial_prompts = {arm: render_prompt(original[arm]) for arm in ARM_IDS}
    initial_counts = {
        arm: padder.count_prompt_tokens(initial_prompts[arm]) for arm in ARM_IDS
    }
    if any(count <= 0 for count in initial_counts.values()):
        raise PromptParityError("prompt token counts must be positive")
    target = max(initial_counts.values())
    contexts: dict[str, str] = {}
    prompts: dict[str, str] = {}
    hashes: dict[str, str] = {}
    for arm in ARM_IDS:
        context = padder.pad_memory_context(
            original[arm], target_prompt_tokens=target, render_prompt=render_prompt
        )
        if not context.startswith(original[arm]):
            raise PromptParityError("padding must preserve the semantic context prefix")
        prompt = render_prompt(context)
        observed = padder.count_prompt_tokens(prompt)
        if observed != target:
            raise PromptParityError(
                f"arm {arm} has {observed} prompt tokens instead of {target}"
            )
        contexts[arm] = context
        prompts[arm] = prompt
        hashes[arm] = canonical_sha256({"prompt": prompt})
    receipt = canonical_sha256({
        "schema_version": SCHEMA_VERSION,
        "target_prompt_tokens": target,
        "prompt_sha256": hashes,
        "tokenizer_identity": padder.tokenizer_identity,
        "padding_identity": padder.padding_identity,
    })
    plan = PromptParityPlanV1(
        target_prompt_tokens=target,
        padded_memory_contexts=contexts,
        rendered_prompts=prompts,
        prompt_sha256=hashes,
        tokenizer_identity=padder.tokenizer_identity,
        padding_identity=padder.padding_identity,
        parity_receipt_sha256=receipt,
    )
    plan.verify()
    return plan
