"""Token-F1 scorer for F0 (regenerated doc prose vs actual).

Pure, dependency-free, deterministic. Primary tokenizer = char-bigrams (robust
for the Korean/English mix of the harness docs; whitespace word-splitting is
unfair to agglutinative Korean). Secondary = word tokens. ROUGE-style multiset
overlap: precision = |pred ∩ gold| / |pred|, recall = |pred ∩ gold| / |gold|.

# KG: ATOM_Skill_longinus  (F0 falsifier, HSWM lens-duality design §9)
"""

from __future__ import annotations

import re
from collections import Counter


def _norm(s: str) -> str:
    """Lowercase + collapse whitespace + strip ASCII punctuation.

    Korean is untouched (no casing); ASCII punctuation removed so `.`/`,` don't
    create spurious bigrams. Deterministic.
    """
    s = s.strip().lower()
    s = re.sub(r"[^\w\s]", "", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s)
    return s


def char_bigrams(s: str) -> list[str]:
    """Whitespace-stripped character bigrams — language-agnostic (ko/en)."""
    t = _norm(s).replace(" ", "")
    if len(t) < 2:
        return [t] if t else []
    return [t[i : i + 2] for i in range(len(t) - 1)]


def words(s: str) -> list[str]:
    """Whitespace word tokens (secondary metric)."""
    n = _norm(s)
    return n.split() if n else []


def token_f1(pred: str, gold: str, tokenizer=char_bigrams) -> dict:
    """ROUGE-style multiset precision/recall/F1. Empty-safe, deterministic."""
    p = Counter(tokenizer(pred))
    g = Counter(tokenizer(gold))
    p_n, g_n = sum(p.values()), sum(g.values())
    overlap = sum((p & g).values())
    if p_n == 0 or g_n == 0 or overlap == 0:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    prec = overlap / p_n
    rec = overlap / g_n
    f1 = 2 * prec * rec / (prec + rec)
    return {"precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4)}


def score_pair(pred: str, gold: str) -> dict:
    """Both metrics for one pair."""
    return {
        "char_bigram": token_f1(pred, gold, char_bigrams),
        "word": token_f1(pred, gold, words),
    }
