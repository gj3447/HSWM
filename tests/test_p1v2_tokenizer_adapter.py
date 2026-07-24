from __future__ import annotations

import pytest

from p1v2_tokenizer_adapter import (
    FrozenTokenizerPromptPadder,
    TokenizerPaddingError,
)


def _character_encode(text):
    return tuple(ord(character) for character in text)


def test_padding_is_exact_prefix_preserving_and_deterministic():
    padder = FrozenTokenizerPromptPadder(
        encode=_character_encode,
        tokenizer_identity="fixture-character-tokenizer@sha256:1234",
        inert_fragments=(" x", " yz"),
    )
    render = lambda memory: "prefix:" + memory + ":suffix"
    target = padder.count_prompt_tokens(render("lesson")) + 6

    first = padder.pad_memory_context(
        "lesson", target_prompt_tokens=target, render_prompt=render
    )
    second = padder.pad_memory_context(
        "lesson", target_prompt_tokens=target, render_prompt=render
    )

    assert first == second
    assert first.startswith("lesson")
    assert padder.count_prompt_tokens(render(first)) == target
    assert len(padder.padding_identity) == 64


def test_padding_rejects_unreachable_target_and_invalid_tokenizer():
    padder = FrozenTokenizerPromptPadder(
        encode=lambda text: tuple(text.split()),
        tokenizer_identity="fixture-word-tokenizer:v1",
        inert_fragments=(" two tokens",),
    )
    with pytest.raises(TokenizerPaddingError, match="cannot reach"):
        padder.pad_memory_context(
            "base",
            target_prompt_tokens=2,
            render_prompt=lambda memory: memory,
        )

    broken = FrozenTokenizerPromptPadder(
        encode=lambda _text: "not-a-token-sequence",
        tokenizer_identity="broken:v1",
    )
    with pytest.raises(TokenizerPaddingError, match="token sequence"):
        broken.count_prompt_tokens("prompt")


def test_tensor_like_tokenizer_output_is_counted_without_coercion():
    class TensorLike:
        def __len__(self):
            return 7

    padder = FrozenTokenizerPromptPadder(
        encode=lambda _text: TensorLike(),
        tokenizer_identity="fixture-tensor-tokenizer:v1",
    )
    assert padder.count_prompt_tokens("prompt") == 7
