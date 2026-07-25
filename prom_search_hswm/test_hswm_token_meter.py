from __future__ import annotations

import json
from pathlib import Path

import pytest

from prom_search_hswm.hswm_token_meter import (
    CHAT_TEMPLATE_ID,
    METER_KIND,
    FakeMeter,
    QwenBpeMeter,
    TokenMeterError,
    _pre_tokenize,
    fit_parity_filler,
    render_chat_prompt,
)
from prom_search_hswm.prom9_validate_token_meter import validate_meter_against_suite


REPO_ROOT = Path(__file__).resolve().parents[1]
TOKENIZER_DIR = REPO_ROOT / "prom_search_hswm" / "data" / "qwen36_tokenizer"
R4_SUITE = REPO_ROOT / "_research" / "prom9_runs" / "f1-2wiki-dev-r4" / "suite.json"
REAL_FILES_PRESENT = (
    (TOKENIZER_DIR / "vocab.json").exists()
    and (TOKENIZER_DIR / "merges.txt").exists()
    and (TOKENIZER_DIR / "tokenizer_config.json").exists()
    and R4_SUITE.exists()
)


def _mini_tokenizer(tmp_path: Path) -> QwenBpeMeter:
    """Smallest lawful meter: byte-level symbols, two merges, chat specials."""

    vocab = {
        "a": 0,
        "b": 1,
        "c": 2,
        "ab": 3,
        "Ġ": 4,
        "Ġa": 5,
        "Ġb": 6,
        "Ġc": 7,
        "<|im_start|>": 8,
        "<|im_end|>": 9,
    }
    (tmp_path / "vocab.json").write_text(json.dumps(vocab), encoding="utf-8")
    (tmp_path / "merges.txt").write_text("#version: 0.2\na b\nĠ b\n", encoding="utf-8")
    config = {
        "tokenizer_class": "Qwen2Tokenizer",
        "added_tokens_decoder": {
            "8": {"content": "<|im_start|>", "special": True},
            "9": {"content": "<|im_end|>", "special": True},
        },
    }
    (tmp_path / "tokenizer_config.json").write_text(json.dumps(config), encoding="utf-8")
    return QwenBpeMeter(
        tmp_path / "vocab.json",
        tmp_path / "merges.txt",
        tmp_path / "tokenizer_config.json",
    )


def test_pre_tokenizer_matches_documented_cases() -> None:
    assert _pre_tokenize("don't") == ["don", "'t"]
    assert _pre_tokenize("they'll've") == ["they", "'ll", "'ve"]
    assert _pre_tokenize("abc1234") == ["abc", "123", "4"]
    assert _pre_tokenize(" hello world") == [" hello", " world"]
    assert _pre_tokenize("a  b") == ["a", " ", " b"]
    assert _pre_tokenize("x\n\ny") == ["x", "\n\n", "y"]
    assert _pre_tokenize("李杨") == ["李杨"]
    assert _pre_tokenize("a--b") == ["a", "--", "b"]
    assert _pre_tokenize("") == []


def test_meter_counts_bpe_and_specials_atomically(tmp_path: Path) -> None:
    meter = _mini_tokenizer(tmp_path)
    assert meter.count_text("ab") == 1  # the single merged token
    assert meter.count_text("abc") == 2
    assert meter.count_text("a b") == 2
    assert meter.count_text("<|im_start|>ab<|im_end|>") == 3
    assert meter.identity()["kind"] == METER_KIND
    assert set(meter.files_sha256()) == {"vocab_sha256", "merges_sha256", "config_sha256"}


def test_meter_is_deterministic_across_loads(tmp_path: Path) -> None:
    first = _mini_tokenizer(tmp_path)
    second = _mini_tokenizer(tmp_path)
    text = "ab cab<|im_start|> a b"
    assert first.count_text(text) == second.count_text(text)
    assert first.identity() == second.identity()


def test_meter_refuses_missing_files_and_hash_drift(tmp_path: Path) -> None:
    with pytest.raises(TokenMeterError, match="cannot read"):
        QwenBpeMeter(
            tmp_path / "none.json", tmp_path / "none.txt", tmp_path / "none.json"
        )
    meter = _mini_tokenizer(tmp_path)
    good = meter.files_sha256()
    QwenBpeMeter(
        tmp_path / "vocab.json",
        tmp_path / "merges.txt",
        tmp_path / "tokenizer_config.json",
        expected_sha256=good,
    )
    with pytest.raises(TokenMeterError, match="hash drifted"):
        QwenBpeMeter(
            tmp_path / "vocab.json",
            tmp_path / "merges.txt",
            tmp_path / "tokenizer_config.json",
            expected_sha256={**good, "vocab_sha256": "0" * 64},
        )


def test_render_chat_prompt_matches_the_frozen_template() -> None:
    rendered = render_chat_prompt("SYS", "USER")
    assert rendered == (
        "<|im_start|>system\nSYS<|im_end|>\n"
        "<|im_start|>user\nUSER<|im_end|>\n"
        "<|im_start|>assistant\n<think>\n\n</think>\n\n"
    )


def test_fit_parity_filler_hits_the_cap_exactly() -> None:
    meter = FakeMeter()
    payload = {"request_id": "req-x", "query_text": "capital?"}
    fitted = fit_parity_filler(
        meter=meter,
        system_prompt="You are a compiler.",
        payload=payload,
        filler_field="parity_filler",
        cap=40,
        unit="0",
        max_chars=1000,
    )
    assert (
        meter.count_chat_prompt("You are a compiler.", json.dumps(fitted, sort_keys=True, separators=(",", ":")))
        == 40
    )
    same = fit_parity_filler(
        meter=meter,
        system_prompt="You are a compiler.",
        payload=payload,
        filler_field="parity_filler",
        cap=40,
        unit="0",
        max_chars=1000,
    )
    assert fitted == same
    with pytest.raises(TokenMeterError, match="exceeds the registered envelope cap"):
        fit_parity_filler(
            meter=meter,
            system_prompt="You are a compiler.",
            payload=payload,
            filler_field="parity_filler",
            cap=1,
            unit="0",
            max_chars=1000,
        )


@pytest.mark.skipif(not REAL_FILES_PRESENT, reason="Qwen3.6 tokenizer files or r4 suite not present")
def test_real_meter_reproduces_all_r4_server_prompt_counts() -> None:
    meter = QwenBpeMeter(
        TOKENIZER_DIR / "vocab.json",
        TOKENIZER_DIR / "merges.txt",
        TOKENIZER_DIR / "tokenizer_config.json",
    )
    suite = json.loads(R4_SUITE.read_text(encoding="utf-8"))
    receipt = validate_meter_against_suite(meter=meter, suite=suite)
    assert receipt["calls_checked"] == 60
    assert receipt["mismatches"] == 0
    assert receipt["result"] == "EXACT_MATCH_60_OF_60"
    assert receipt["meter"]["chat_template_id"] == CHAT_TEMPLATE_ID


@pytest.mark.skipif(not REAL_FILES_PRESENT, reason="Qwen3.6 tokenizer files or r4 suite not present")
def test_real_meter_digit_filler_tokenizes_linearly() -> None:
    meter = QwenBpeMeter(
        TOKENIZER_DIR / "vocab.json",
        TOKENIZER_DIR / "merges.txt",
        TOKENIZER_DIR / "tokenizer_config.json",
    )
    # The manifest declares the digit filler unit because Qwen3.6 tokenizes a
    # digit run one token per character with no merge surprises, so an exact
    # envelope fit always exists.
    counts = [meter.count_text("0" * k) for k in range(1, 13)]
    assert counts == list(range(1, 13))
