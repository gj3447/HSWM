"""Exact local token meter for the Qwen2/Qwen3 tokenizer family (stdlib only).

The PROM-9 F1 equal-budget gate compares consumed input+output tokens across
arms, so the harness needs a deterministic, offline way to count the prompt
tokens that the served model will report.  This module re-implements the
Qwen2 byte-level BPE tokenizer (``Qwen2Tokenizer``) and the Qwen3 chat
template in pure Python.  It loads the unmodified upstream ``vocab.json``,
``merges.txt``, and ``tokenizer_config.json`` files; every file hash is
recorded so a manifest can bind the exact tokenizer identity.

The implementation is validated against the served model itself: the F1
development r4 suite records the server's ``prompt_tokens`` for 60 calls, and
``prom9_validate_token_meter.py`` requires an exact match on all of them
before the meter may be referenced by a manifest.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
import unicodedata
from collections.abc import Mapping
from typing import Protocol


METER_KIND = "qwen2-bpe-local-files/v1"
CHAT_TEMPLATE_ID = "qwen3-im-start-system-user-think-disabled/v1"


class TokenMeterError(RuntimeError):
    """The meter files, the meter itself, or a count is not trustworthy."""


class TokenMeter(Protocol):
    """Counting port used by the F1 harness; tests inject deterministic fakes."""

    def count_text(self, text: str) -> int: ...

    def count_chat_prompt(self, system_prompt: str, user_text: str) -> int: ...

    def identity(self) -> dict[str, object]: ...


def _read_stable_bytes(path: Path, label: str) -> bytes:
    """Read one bounded regular file once through a stable no-follow FD."""

    target = Path(path)
    try:
        before = target.lstat()
    except OSError as error:
        raise TokenMeterError(f"cannot stat meter {label} file: {error}") from error
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise TokenMeterError(
            f"meter {label} file must be a regular non-symlink file"
        )
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(target, flags)
    except OSError as error:
        raise TokenMeterError(f"cannot open meter {label} file: {error}") from error
    payload = bytearray()
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_dev != before.st_dev
            or opened.st_ino != before.st_ino
        ):
            raise TokenMeterError(f"meter {label} file changed before reading")
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            payload.extend(block)
            if len(payload) > 64 * 1024 * 1024:
                raise TokenMeterError(f"meter {label} file exceeds 64 MiB")
        after_fd = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        after_path = target.lstat()
    except OSError as error:
        raise TokenMeterError(f"cannot restat meter {label} file: {error}") from error
    identity = lambda value: (  # noqa: E731 - immutable stat projection
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )
    if (
        identity(before) != identity(after_fd)
        or identity(before) != identity(after_path)
        or len(payload) != before.st_size
    ):
        raise TokenMeterError(f"meter {label} file changed while reading")
    return bytes(payload)


def _bytes_to_unicode() -> dict[int, str]:
    """Return the GPT-2 byte-to-printable-unicode mapping."""

    printable = (
        list(range(ord("!"), ord("~") + 1))
        + list(range(ord("¡"), ord("¬") + 1))
        + list(range(ord("®"), ord("ÿ") + 1))
    )
    mapping: dict[int, str] = {}
    extra = 0
    for value in range(256):
        if value in printable:
            mapping[value] = chr(value)
        else:
            mapping[value] = chr(256 + extra)
            extra += 1
    return mapping


_BYTE_TO_CHAR = _bytes_to_unicode()


def _is_letter(char: str) -> bool:
    return unicodedata.category(char).startswith("L")


def _is_number(char: str) -> bool:
    return unicodedata.category(char).startswith("N")


def _is_space(char: str) -> bool:
    return char.isspace()


def _is_punct_class(char: str) -> bool:
    return not _is_space(char) and not _is_letter(char) and not _is_number(char)


def _pre_tokenize(text: str) -> list[str]:
    """Split ``text`` exactly like the Qwen2 pre-tokenizer pattern.

    Reproduces, with ordered-alternative regex semantics, the pattern::

        '(?i:[sdmt]|ll|ve|re)|[^\\r\\n\\p{L}\\p{N}]?\\p{L}+|\\p{N}{1,3}|
         ?[^\\s\\p{L}\\p{N}]+[\\r\\n]*|\\s*[\\r\\n]+|\\s+(?!\\S)|\\s+
    """

    words: list[str] = []
    length = len(text)
    position = 0
    while position < length:
        end = _match_word(text, position)
        if end is None or end <= position:
            raise TokenMeterError(f"pre-tokenizer stalled at offset {position}")
        words.append(text[position:end])
        position = end
    return words


def _match_word(text: str, start: int) -> int | None:
    length = len(text)
    char = text[start]
    # Alternative 1: '(?i:[sdmt]|ll|ve|re)
    if char == "'":
        tail = text[start + 1 : start + 3].casefold()
        if tail[:1] in {"s", "d", "m", "t"}:
            return start + 2
        if tail in {"ll", "ve", "re"}:
            return start + 3
    # Alternative 2: [^\r\n\p{L}\p{N}]?\p{L}+
    cursor = start
    if not _is_letter(char):
        if char in "\r\n" or _is_number(char):
            cursor = start  # optional prefix cannot be consumed here
        else:
            cursor = start + 1
    if cursor < length and _is_letter(text[cursor]):
        end = cursor + 1
        while end < length and _is_letter(text[end]):
            end += 1
        return end
    # Alternative 3: \p{N}{1,3}
    if _is_number(char):
        end = start
        while end < length and end - start < 3 and _is_number(text[end]):
            end += 1
        return end
    # Alternative 4:  ?[^\s\p{L}\p{N}]+[\r\n]*
    cursor = start
    if char == " ":
        cursor = start + 1
    if cursor < length and _is_punct_class(text[cursor]):
        end = cursor
        while end < length and _is_punct_class(text[end]):
            end += 1
        while end < length and text[end] in "\r\n":
            end += 1
        return end
    # Alternative 5: \s*[\r\n]+
    if _is_space(char):
        run_end = start
        while run_end < length and _is_space(text[run_end]):
            run_end += 1
        back = run_end
        while back > start and text[back - 1] not in "\r\n":
            back -= 1
        if back > start:
            newline_end = back
            while newline_end < length and text[newline_end] in "\r\n":
                newline_end += 1
            return newline_end
        # Alternative 6: \s+(?!\S)
        back = run_end
        while back > start:
            if back == length or _is_space(text[back]):
                return back
            back -= 1
        # Alternative 7: \s+
        return run_end
    return None


class QwenBpeMeter:
    """Offline Qwen2-family BPE meter bound to hashed upstream files."""

    def __init__(
        self,
        vocab_path: Path,
        merges_path: Path,
        config_path: Path,
        *,
        expected_sha256: Mapping[str, str] | None = None,
        source: str = "https://huggingface.co/Qwen/Qwen3.6-27B (vocab.json, merges.txt, tokenizer_config.json)",
    ) -> None:
        self._source = source
        self._paths = {
            "vocab": Path(vocab_path),
            "merges": Path(merges_path),
            "config": Path(config_path),
        }
        raw_files = {
            name: _read_stable_bytes(path, name)
            for name, path in self._paths.items()
        }
        hashes = {
            f"{name}_sha256": hashlib.sha256(raw).hexdigest()
            for name, raw in raw_files.items()
        }
        if expected_sha256 is not None:
            for key, expected in expected_sha256.items():
                if hashes.get(key) != expected:
                    raise TokenMeterError(f"meter file hash drifted: {key}")
        self._files_sha256 = hashes
        try:
            vocab = json.loads(raw_files["vocab"].decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise TokenMeterError(f"cannot parse meter vocab: {error}") from error
        if not isinstance(vocab, dict) or not vocab:
            raise TokenMeterError("meter vocab must be a non-empty object")
        self._vocab: dict[str, int] = {str(token): int(index) for token, index in vocab.items()}
        merges: dict[tuple[str, str], int] = {}
        try:
            lines = raw_files["merges"].decode("utf-8").splitlines()
        except UnicodeError as error:
            raise TokenMeterError(f"cannot parse meter merges: {error}") from error
        rank = 0
        for line in lines:
            if not line or line.startswith("#"):
                continue
            left, separator, right = line.partition(" ")
            if not separator or not left or not right:
                raise TokenMeterError(f"malformed merge line {rank}")
            merges[(left, right)] = rank
            rank += 1
        if not merges:
            raise TokenMeterError("meter merges must be non-empty")
        self._merges = merges
        try:
            config = json.loads(raw_files["config"].decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise TokenMeterError(f"cannot parse meter config: {error}") from error
        added = config.get("added_tokens_decoder")
        specials: dict[str, int] = {}
        if isinstance(added, dict):
            for index, body in added.items():
                if isinstance(body, dict) and isinstance(body.get("content"), str):
                    specials[body["content"]] = int(index)
        if not {"<|im_start|>", "<|im_end|>"}.issubset(specials):
            raise TokenMeterError("meter config lacks the Qwen chat special tokens")
        self._specials = specials
        self._word_cache: dict[str, int] = {}

    def files_sha256(self) -> dict[str, str]:
        return dict(self._files_sha256)

    def identity(self) -> dict[str, object]:
        return {
            "kind": METER_KIND,
            "chat_template_id": CHAT_TEMPLATE_ID,
            "source": self._source,
            **self._files_sha256,
        }

    def _encode_word(self, word: str) -> int:
        cached = self._word_cache.get(word)
        if cached is not None:
            return cached
        symbols = [_BYTE_TO_CHAR[byte] for byte in word.encode("utf-8")]
        while len(symbols) > 1:
            best_rank: int | None = None
            best_index = 0
            for index in range(len(symbols) - 1):
                rank = self._merges.get((symbols[index], symbols[index + 1]))
                if rank is not None and (best_rank is None or rank < best_rank):
                    best_rank = rank
                    best_index = index
            if best_rank is None:
                break
            symbols[best_index : best_index + 2] = [
                symbols[best_index] + symbols[best_index + 1]
            ]
        for symbol in symbols:
            if symbol not in self._vocab:
                raise TokenMeterError(f"BPE produced a symbol outside the vocab: {symbol!r}")
        total = len(symbols)
        self._word_cache[word] = total
        return total

    def count_text(self, text: str) -> int:
        """Count tokens of raw text, honoring special tokens as atomic."""

        if not isinstance(text, str):
            raise TokenMeterError("count_text requires a string")
        total = 0
        cursor = 0
        length = len(text)
        ordered = sorted(self._specials, key=len, reverse=True)
        while cursor < length:
            matched = None
            for special in ordered:
                if text.startswith(special, cursor):
                    matched = special
                    break
            if matched is not None:
                total += 1
                cursor += len(matched)
                continue
            next_special = length
            for special in ordered:
                found = text.find(special, cursor)
                if found != -1 and found < next_special:
                    next_special = found
            segment = text[cursor:next_special]
            for word in _pre_tokenize(segment):
                total += self._encode_word(word)
            cursor = next_special
        return total

    def count_chat_prompt(self, system_prompt: str, user_text: str) -> int:
        """Count the served prompt tokens for one system+user exchange.

        Reconstructs the Qwen3 chat template exactly as vLLM renders it for
        ``add_generation_prompt=True`` with ``enable_thinking=False``::

            <|im_start|>system\n{system}<|im_end|>\n
            <|im_start|>user\n{user}<|im_end|>\n
            <|im_start|>assistant\n<think>\n\n</think>\n\n
        """

        return self.count_text(render_chat_prompt(system_prompt, user_text))


def render_chat_prompt(system_prompt: str, user_text: str) -> str:
    if not isinstance(system_prompt, str) or not isinstance(user_text, str):
        raise TokenMeterError("chat prompt parts must be strings")
    return (
        "<|im_start|>system\n"
        + system_prompt
        + "<|im_end|>\n<|im_start|>user\n"
        + user_text
        + "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
    )


def fit_parity_filler(
    *,
    meter: TokenMeter,
    system_prompt: str,
    payload: Mapping[str, object],
    filler_field: str,
    cap: int,
    unit: str,
    max_chars: int,
) -> dict[str, object]:
    """Return ``payload`` with the inert filler field sized to hit ``cap``.

    The returned payload's chat-prompt token count under ``meter`` equals the
    registered per-call input cap exactly.  The filler is a repetition of the
    manifest-declared unit string; it carries no information and is recorded,
    hashed, and replayable as part of the call receipt.  The search is
    fail-closed: a natural prompt already above the cap, or the absence of an
    exact fit within the declared character ceiling, raises instead of
    silently shipping a non-conforming envelope.
    """

    from prom_search_hswm.hswm_typed_ports import canonical_json

    if isinstance(cap, bool) or not isinstance(cap, int) or cap < 1:
        raise TokenMeterError("envelope cap must be a positive integer")
    if not unit:
        raise TokenMeterError("filler unit must be non-empty")
    if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars < 0:
        raise TokenMeterError("max filler chars must be a non-negative integer")
    base = dict(payload)
    base[filler_field] = ""

    def count_with(chars: int) -> int:
        candidate = dict(base)
        candidate[filler_field] = unit * chars
        return meter.count_chat_prompt(system_prompt, canonical_json(candidate))

    natural = count_with(0)
    if natural > cap:
        raise TokenMeterError(
            f"natural prompt of {natural} tokens exceeds the registered envelope cap {cap}"
        )
    if natural == cap:
        return base
    needed = cap - natural
    unit_tokens = meter.count_text(unit)
    chars_per_token = max(1, round(len(unit) / max(1, unit_tokens)))
    estimate = min(max_chars, needed * chars_per_token)
    below: tuple[int, int] | None = None
    above: tuple[int, int] | None = None
    current = estimate
    for _ in range(8):
        total = count_with(current)
        if total == cap:
            result = dict(base)
            result[filler_field] = unit * current
            return result
        if total < cap:
            below = (current, total)
            current += max(1, (cap - total) * chars_per_token)
            if current > max_chars:
                break
        else:
            above = (current, total)
            current -= max(1, (total - cap) * chars_per_token)
            if current < 0:
                break
        if below is not None and above is not None:
            break
    low = below[0] if below is not None else 0
    high = above[0] if above is not None else max_chars
    for candidate_chars in range(low, high + 1):
        if count_with(candidate_chars) == cap:
            result = dict(base)
            result[filler_field] = unit * candidate_chars
            return result
    raise TokenMeterError(
        "no exact parity-filler fit within the declared character ceiling"
    )


@dataclass(frozen=True)
class FakeMeter:
    """Deterministic test meter: one token per four characters, plus wrapper.

    The chat wrapper overhead is a fixed constant so tests can reason about
    exact envelope arithmetic without the upstream tokenizer files.
    """

    chars_per_token: int = 4
    chat_overhead_tokens: int = 11

    def count_text(self, text: str) -> int:
        if not isinstance(text, str):
            raise TokenMeterError("count_text requires a string")
        return max(1, -(-len(text) // self.chars_per_token))

    def count_chat_prompt(self, system_prompt: str, user_text: str) -> int:
        return self.chat_overhead_tokens + self.count_text(system_prompt) + self.count_text(user_text)

    def identity(self) -> dict[str, object]:
        return {
            "kind": "fake-meter-for-tests/v1",
            "chat_template_id": "fake-chat-template/v1",
            "chars_per_token": self.chars_per_token,
            "chat_overhead_tokens": self.chat_overhead_tokens,
        }


__all__ = [
    "CHAT_TEMPLATE_ID",
    "FakeMeter",
    "METER_KIND",
    "QwenBpeMeter",
    "TokenMeter",
    "TokenMeterError",
    "fit_parity_filler",
    "render_chat_prompt",
]
