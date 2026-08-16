"""doc→hypergraph builder HARNESS — raw text in, Experiment-B-shaped strata out.

The P0 blocker for real-data Experiment B (INDEX §3 / KQV PROM E1): HSWM could
only ingest Neo4j KGs or synthetic worlds; real books are plain text. This
module is the minimal deterministic harness that closes the SHAPE gap:

    text ──split──▶ units per length level (sentence/paragraph/section/chapter)
         ──concepts──▶ nodes = frequent content words (doc-local vocabulary)
         ──incidence──▶ hyperedge per unit = the concept set it mentions
         ──embed──▶ node/unit embeddings

HARNESS ONLY — honest scope limits (do not oversell):
- The default embedder is deterministic FEATURE HASHING (bag-of-words hashed
  ± into d buckets, L2-normalized). It is a stand-in so the pipeline runs
  end-to-end with zero deps; real runs MUST inject a real model via
  `embed_fn` (e.g. bge-m3), or cosine is a strawman (tool-fitness prefilter).
- Concept extraction is frequency + stopword filtering, not NER/coref. A
  "concept" here is a surface word; upgrading to entities is future work.
- No queries/gold here: those come from the QA dataset (NoCha/QASPER) loader,
  which is the NEXT piece, not this one.

Output mirrors what expB arms consume: per level a `Hypergraph` (nodes =
concepts, members = per-unit concept sets) with `unit_emb` stapled on, same as
synth_longdoc. Units that mention no vocabulary concept are dropped (reported).

Determinism: md5-based hashing (never Python hash()); no global RNG.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

import numpy as np

from hypergraph import Hypergraph

LENGTH_ORDER = ["sentence", "paragraph", "section", "chapter"]
SECTION_PARAS = 4      # paragraphs per section
CHAPTER_SECTIONS = 4   # sections per chapter
MIN_CONCEPT_COUNT = 3  # a word must occur this often to become a node
MIN_WORD_LEN = 3
DEFAULT_DIM = 256

_STOPWORDS = frozenset("""
the a an and or but if then else of to in on at by for with from as is are was
were be been being have has had do does did not no yes it its this that these
those he she they them his her their i you we me my your our us what which who
whom when where why how all any both each few more most other some such only
own same so than too very can will just should now said says say went came
come one two also into over under again out up down about after before while
there here
""".split())

_TOKEN_RE = re.compile(r"[a-zA-Z가-힣][a-zA-Z가-힣']*")
_SENT_RE = re.compile(r"(?<=[.!?…。])\s+")


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)
            if len(t) >= MIN_WORD_LEN and t.lower() not in _STOPWORDS]


def _stable_hash(token: str) -> int:
    return int.from_bytes(hashlib.md5(token.encode("utf-8")).digest()[:8], "little")


def hash_embed(texts: list[str], dim: int = DEFAULT_DIM) -> np.ndarray:
    """Deterministic feature-hashing embedder (STAND-IN; inject a real model for runs).

    token → bucket = h(token) mod dim, sign = parity of h — the classic hashing
    trick. L2-normalized so cosine works. Shared tokens ⇒ similar vectors; no
    semantics beyond lexical overlap (documented limitation).
    """
    out = np.zeros((len(texts), dim), dtype=np.float64)
    for i, text in enumerate(texts):
        for tok in _tokens(text):
            h = _stable_hash(tok)
            out[i, h % dim] += 1.0 if (h >> 63) & 1 == 0 else -1.0
    n = np.linalg.norm(out, axis=1, keepdims=True)
    return out / np.clip(n, 1e-12, None)


def split_units(text: str) -> dict[str, list[str]]:
    """Deterministic unit split at every length level (plain-text robust)."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    sentences = [s.strip() for p in paragraphs for s in _SENT_RE.split(p) if s.strip()]
    sections = ["\n\n".join(paragraphs[i:i + SECTION_PARAS])
                for i in range(0, len(paragraphs), SECTION_PARAS)]
    chapters = ["\n\n".join(sections[i:i + CHAPTER_SECTIONS])
                for i in range(0, len(sections), CHAPTER_SECTIONS)]
    return {"sentence": sentences, "paragraph": paragraphs,
            "section": sections, "chapter": chapters}


def extract_concepts(text: str) -> list[str]:
    """Doc-local vocabulary: content words occurring ≥ MIN_CONCEPT_COUNT times."""
    counts: dict[str, int] = {}
    for tok in _tokens(text):
        counts[tok] = counts.get(tok, 0) + 1
    return sorted(w for w, c in counts.items() if c >= MIN_CONCEPT_COUNT)


@dataclass
class BuiltDoc:
    """One document's Experiment-B-shaped strata (queries/gold NOT included)."""
    concepts: list[str]
    strata: dict[str, Hypergraph]            # level → hypergraph (unit_emb stapled)
    unit_texts: dict[str, list[str]]         # level → kept unit texts
    dropped: dict[str, int] = field(default_factory=dict)  # level → conceptless units


def build(text: str, embed_fn=None, dim: int = DEFAULT_DIM) -> BuiltDoc:
    """text → per-level hypergraphs. embed_fn(texts)->(n,d) overrides hash_embed."""
    embed = embed_fn if embed_fn is not None else (lambda ts: hash_embed(ts, dim))
    concepts = extract_concepts(text)
    if not concepts:
        raise ValueError("no concepts survived extraction — text too short/sparse")
    cidx = {c: i for i, c in enumerate(concepts)}
    node_emb = np.asarray(embed(concepts), dtype=np.float64)

    strata: dict[str, Hypergraph] = {}
    unit_texts: dict[str, list[str]] = {}
    dropped: dict[str, int] = {}
    all_units = split_units(text)

    for level in LENGTH_ORDER:
        members, kept = [], []
        n_drop = 0
        for u in all_units[level]:
            mem = np.array(sorted({cidx[t] for t in _tokens(u) if t in cidx}), dtype=np.int64)
            if mem.size == 0:
                n_drop += 1
                continue
            members.append(mem)
            kept.append(u)
        if not members:
            raise ValueError(f"level {level!r}: every unit dropped (no concept mentions)")
        m = len(members)
        hg = Hypergraph(node_emb=node_emb, members=members,
                        edge_freq=np.ones(m), edge_recency=np.zeros(m))
        hg.unit_emb = np.asarray(embed(kept), dtype=np.float64)  # type: ignore[attr-defined]
        strata[level] = hg
        unit_texts[level] = kept
        dropped[level] = n_drop

    return BuiltDoc(concepts=concepts, strata=strata, unit_texts=unit_texts, dropped=dropped)
