"""Exact-token prompt padding behind an injected frozen tokenizer.

The adapter owns no model or evaluator state.  Callers inject the deployed
tokenizer's ``encode`` function and record its immutable identity.  Padding is
deterministic, prefix-preserving, and fails closed when the supplied inert
fragment alphabet cannot reach the requested token count exactly.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from hswm_weight_snapshot import canonical_sha256


class TokenizerPaddingError(ValueError):
    pass


class FrozenTokenizerPromptPadder:
    def __init__(
        self,
        *,
        encode: Callable[[str], Sequence[int]],
        tokenizer_identity: str,
        inert_fragments: Sequence[str] = (" ZXQPAD", "\nZXQPAD", " ZXQPAD."),
        max_steps: int = 4096,
    ) -> None:
        if not callable(encode):
            raise TokenizerPaddingError("encode must be callable")
        if not isinstance(tokenizer_identity, str) or not tokenizer_identity.strip():
            raise TokenizerPaddingError("tokenizer identity must be non-empty")
        fragments = tuple(inert_fragments)
        if (
            not fragments
            or any(not isinstance(item, str) or not item for item in fragments)
            or len(set(fragments)) != len(fragments)
        ):
            raise TokenizerPaddingError("inert fragments must be unique non-empty text")
        if not isinstance(max_steps, int) or isinstance(max_steps, bool) or max_steps <= 0:
            raise TokenizerPaddingError("max_steps must be a positive integer")
        self._encode = encode
        self.tokenizer_identity = tokenizer_identity.strip()
        self._fragments = tuple(sorted(fragments))
        self._max_steps = max_steps
        self.padding_identity = canonical_sha256({
            "schema_version": "hswm-p1v2-token-padding/v1",
            "tokenizer_identity": self.tokenizer_identity,
            "inert_fragments": list(self._fragments),
            "algorithm": "deterministic-smallest-nonovershooting-increment/v1",
            "max_steps": self._max_steps,
        })

    def count_prompt_tokens(self, prompt: str) -> int:
        if not isinstance(prompt, str):
            raise TokenizerPaddingError("prompt must be text")
        encoded = self._encode(prompt)
        if (
            isinstance(encoded, (str, bytes, Mapping))
            or not hasattr(encoded, "__len__")
        ):
            raise TokenizerPaddingError("tokenizer encode must return a token sequence")
        count = len(encoded)
        if prompt and count <= 0:
            raise TokenizerPaddingError("non-empty prompt encoded to no tokens")
        return count

    def pad_memory_context(
        self,
        memory_context: str,
        *,
        target_prompt_tokens: int,
        render_prompt: Callable[[str], str],
    ) -> str:
        if not isinstance(memory_context, str) or not callable(render_prompt):
            raise TokenizerPaddingError("memory context and renderer are required")
        if (
            not isinstance(target_prompt_tokens, int)
            or isinstance(target_prompt_tokens, bool)
            or target_prompt_tokens <= 0
        ):
            raise TokenizerPaddingError("target token count must be positive")
        padded = memory_context
        observed = self.count_prompt_tokens(render_prompt(padded))
        if observed > target_prompt_tokens:
            raise TokenizerPaddingError("target is below the unpadded prompt count")
        for _ in range(self._max_steps):
            if observed == target_prompt_tokens:
                return padded
            candidates: list[tuple[int, str, str]] = []
            for fragment in self._fragments:
                proposed = padded + fragment
                count = self.count_prompt_tokens(render_prompt(proposed))
                if observed < count <= target_prompt_tokens:
                    candidates.append((count, fragment, proposed))
            if not candidates:
                raise TokenizerPaddingError(
                    "inert fragment alphabet cannot reach exact target token count"
                )
            # Smallest safe increment avoids a final one-token gap under BPE
            # boundary merges; fragment text is the deterministic tie breaker.
            observed, _fragment, padded = min(
                candidates, key=lambda item: (item[0], item[1])
            )
        raise TokenizerPaddingError("exact padding exceeded the frozen step budget")


__all__ = ["FrozenTokenizerPromptPadder", "TokenizerPaddingError"]
