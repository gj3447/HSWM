"""F0 harness tests — deterministic, LLM-free.

Validates the scorer + aggregation + verdict bands so the real vLLM run only
adds a data point, never debugs the pipeline. Run from this dir:
    python -m pytest test_f0.py -q

# KG: ATOM_Skill_longinus  (F0 falsifier)
"""

from __future__ import annotations

from f1_score import char_bigrams, score_pair, token_f1, words
from regenerate import echo_regenerate, stub_regenerate
from run_f0 import _load_pairs, run_f0, verdict


class TestScorer:
    def test_identical_is_one(self):
        assert token_f1("롱기누스 바인딩", "롱기누스 바인딩")["f1"] == 1.0

    def test_disjoint_is_zero(self):
        assert token_f1("abcdef", "지구본")["f1"] == 0.0

    def test_empty_safe(self):
        assert token_f1("", "무언가")["f1"] == 0.0
        assert token_f1("무언가", "")["f1"] == 0.0

    def test_partial_between_zero_and_one(self):
        f1 = token_f1("롱기누스 바인딩 도구", "롱기누스 검증 도구")["f1"]
        assert 0.0 < f1 < 1.0

    def test_char_bigram_tokenizer(self):
        assert char_bigrams("abc") == ["ab", "bc"]
        assert char_bigrams("a") == ["a"]
        assert char_bigrams("") == []

    def test_word_tokenizer_normalizes(self):
        assert words("Hello,  World.") == ["hello", "world"]

    def test_both_metrics_present(self):
        s = score_pair("가나다", "가나다")
        assert s["char_bigram"]["f1"] == 1.0 and s["word"]["f1"] == 1.0


class TestVerdictBands:
    def test_supported(self):
        assert verdict(0.80) == "P_SUPPORTED"
        assert verdict(0.95) == "P_SUPPORTED"

    def test_refuted(self):
        assert verdict(0.50) == "P_REFUTED"
        assert verdict(0.10) == "P_REFUTED"

    def test_inconclusive(self):
        assert verdict(0.65) == "INCONCLUSIVE"


class TestHarness:
    def test_perfect_regenerator_supports_P(self):
        pairs = _load_pairs()
        gold_by_nc = {p["node_content"]: p["doc_prose"] for p in pairs}
        result = run_f0(pairs, lambda nc: gold_by_nc[nc])  # returns exact gold
        assert result["mean_char_bigram_f1"] == 1.0
        assert result["verdict"] == "P_SUPPORTED"
        assert result["n_pairs"] == len(pairs)

    def test_garbage_regenerator_refutes_P(self):
        pairs = _load_pairs()
        result = run_f0(pairs, lambda nc: "xyzxyz")  # no overlap w/ Korean gold
        assert result["mean_char_bigram_f1"] <= 0.5
        assert result["verdict"] == "P_REFUTED"

    def test_stub_runs_over_all_pairs(self):
        pairs = _load_pairs()
        result = run_f0(pairs, stub_regenerate)
        assert result["n_pairs"] == len(pairs)
        assert len(result["per_pair"]) == len(pairs)

    def test_echo_floor_has_structural_overlap(self):
        # echo returns node_content; it shares vocabulary with doc_prose so F1 > 0
        # but < 1 (not identical) — the no-LLM structural floor.
        pairs = _load_pairs()
        result = run_f0(pairs, echo_regenerate)
        assert 0.0 < result["mean_char_bigram_f1"] < 1.0
