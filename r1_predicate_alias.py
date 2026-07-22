"""Offline predicate / role alias-closure for PROM-8 R1 (no network).

Build-time style map: Wikidata-ish property families + morphology clusters
over the exact predicate strings that already exist in the frozen woven graph.
Does not download Wikidata; CC0-style *local* alias families only.
"""
from __future__ import annotations

from collections import defaultdict
import re
import unicodedata

_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)
_STOP = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "did", "do", "does",
    "for", "from", "how", "in", "is", "it", "of", "on", "or", "that", "the",
    "this", "to", "was", "were", "what", "when", "where", "which", "who",
    "whom", "whose", "why", "with", "both", "such", "american", "film",
    "dutch", "drama", "comedy",
})

# Hand families ≈ Wikidata property alias groups (local, no fetch).
# Each family is a set of surface stems that should expand into each other.
_FAMILY_STEMS: tuple[frozenset[str], ...] = (
    frozenset({"direct", "director", "directed", "directing"}),
    frozenset({"star", "starring", "stars", "actor", "actress", "cast"}),
    frozenset({"write", "written", "writer", "author", "screenplay"}),
    frozenset({"produc", "producer", "produced"}),
    frozenset({"born", "birth", "birthplace", "nativ"}),
    frozenset({"die", "died", "death", "deceased"}),
    frozenset({"son", "daughter", "child", "father", "mother", "parent",
               "sister", "brother", "twin", "wife", "husband", "spouse",
               "married", "marriage", "consort"}),
    frozenset({"found", "founder", "founded", "founding", "establish"}),
    frozenset({"releas", "release", "published", "publication"}),
    frozenset({"border", "borders", "adjacent", "located", "location",
               "headquarter", "capital"}),
    frozenset({"collabor", "work", "worked", "partner"}),
)


def _norm_words(text: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    out: list[str] = []
    for raw in _WORD_RE.findall(normalized):
        if raw in _STOP or len(raw) < 2:
            continue
        word = raw
        for suffix in ("ingly", "edly", "ation", "ions", "ment", "ers",
                       "ing", "ed", "er", "es", "s"):
            if len(word) - len(suffix) >= 4 and word.endswith(suffix):
                word = word[:-len(suffix)]
                break
        if word and word not in _STOP:
            out.append(word)
    return tuple(sorted(set(out)))


def _family_for(stem: str) -> frozenset[str] | None:
    for fam in _FAMILY_STEMS:
        for member in fam:
            if stem == member or stem.startswith(member) or member.startswith(stem):
                if min(len(stem), len(member)) >= 4 or stem == member:
                    return fam
    return None


def expand_terms(terms: tuple[str, ...] | set[str]) -> frozenset[str]:
    """Expand a bag of normalized stems with family aliases."""
    out: set[str] = set(terms)
    for t in list(terms):
        fam = _family_for(t)
        if fam is not None:
            out.update(fam)
        # light morphology reopen
        for s in ("e", "er", "or", "ed", "ing"):
            out.add(t + s)
    return frozenset(out)


def build_predicate_alias_index(predicate_strings: list[str]) -> dict[str, frozenset[str]]:
    """Map each exact predicate string -> expanded stem set for matching."""
    index: dict[str, frozenset[str]] = {}
    # inverted: stem -> predicates sharing family
    stem_to_preds: dict[str, set[str]] = defaultdict(set)
    base_terms: dict[str, tuple[str, ...]] = {}
    for pred in predicate_strings:
        terms = _norm_words(pred)
        base_terms[pred] = terms
        for t in terms:
            stem_to_preds[t].add(pred)
            fam = _family_for(t)
            if fam:
                for m in fam:
                    stem_to_preds[m].add(pred)
    for pred, terms in base_terms.items():
        expanded = set(expand_terms(terms))
        # co-cluster: any other predicate sharing a content stem (≥5 chars)
        for t in terms:
            if len(t) >= 5:
                for other in stem_to_preds.get(t, ()):
                    expanded.update(base_terms.get(other, ()))
        index[pred] = frozenset(expanded)
    return index


def query_term_closure(query_text: str) -> frozenset[str]:
    return expand_terms(_norm_words(query_text))
