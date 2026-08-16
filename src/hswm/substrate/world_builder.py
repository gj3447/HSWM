"""Corpus-level hyperedge WORLD BUILDER (T4.5) — QA rows in, one leaf HSWM out.

Consumes the ab_p5_full.py normalized row schema
    {id, hop, question, answer, paragraphs: [{idx, title, paragraph_text, is_supporting}]}
(MuSiQue / 2WikiMultihopQA via HF datasets-server; fetching stays in ab_p5_full,
this module is NETWORK-FREE) and builds ONE corpus-level `Hypergraph`:

    nodes  = ENTITIES  — every paragraph title (wiki articles are about entities)
             + capitalized phrases mentioned in ≥ MIN_ENTITY_COUNT paragraphs
    edge   = one hyperedge per (deduped) paragraph, binding the entities it
             mentions. Title membership ⇒ every edge has arity ≥ 1 ⇒ NO gold
             paragraph can be dropped (structural gold recall = 1.0, tested).
    bridge = paragraph A mentioning the title-entity of paragraph B shares that
             node with B — the sparse entity-cooccurrence structure that is the
             ONLY regime where traversal has a literature edge (add1584: dense
             para-para cosine graphs make diffusion a low-pass smoother; this
             builder deliberately does NOT build that graph).

Honest scope limits:
- Default embedder = doc_builder.hash_embed STAND-IN (lexical only). Real runs
  MUST inject a real model via embed_fn or cosine arms are strawmen.
- Entity extraction is a capitalization heuristic, not NER/coref. Alias splits
  ("US" vs "United States") fragment nodes; extraction recall bounds bridge
  coverage (a missed mention = a missing walkable edge, logged as first-class
  in stats, spec §9 ②).
- 기술통계 선행 보고 (spec §10 T4.5): stats() MUST be published before any
  result — the world's shape (density, hubs) decides the experiment, and that
  decision must be visible, not baked (expB v1 containment-artifact lesson).
- This builds ONE leaf HSWM. The user-canon multi-field weave (여러 HSWM이
  롱기누스로 엮인 맵, 2026-07-19) lives a layer ABOVE this interface; nothing
  here assumes the leaf is alone.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field as dfield

import numpy as np

from doc_builder import hash_embed
from hypergraph import Hypergraph

MIN_ENTITY_COUNT = 2      # body-mention entities must appear in ≥ this many paragraphs
DEFAULT_DIM = 256
_CAP_RE = re.compile(r"\b[A-Z][a-zA-Z0-9']*(?:\s+[A-Z][a-zA-Z0-9']*)*")
_HOP_RE = re.compile(r"(\d+)")

# single-word mention blocklist — sentence-initial capitalization turns function
# words/months into MEGA-HUB fake entities (live musique run: 'the' deg=1130,
# 'she', 'september' in top hubs → the dense low-pass regime traversal dies in).
# Multi-word phrases are never blocked ('The United States' survives via strip).
_MENTION_BLOCK = frozenset("""
the a an and or but if then else of to in on at by for with from as is are was
were be been being it its this that these those he she they them his her their
i you we me my your our us what which who whom when where why how all any both
each few more most other some such only own same so than too very can will
just should now there here after before while during january february march
april may june july august september october november december monday tuesday
wednesday thursday friday saturday sunday one two three four five six seven
eight nine ten first second third
""".split())


def _norm_ent(s: str) -> str:
    """lowercase + whitespace-collapse + leading-article strip ('The Ember Dragon'
    ≡ 'Ember Dragon' — the most common alias fragmentation; full alias/coref
    resolution stays a documented limitation)."""
    t = re.sub(r"\s+", " ", s).strip().lower()
    return re.sub(r"^(the|a|an) ", "", t)


def extract_mentions(text: str) -> list[str]:
    """Capitalized-phrase mentions. Single-word mentions in _MENTION_BLOCK are
    dropped (df gate alone does NOT stop them — they pass ≥2 docs trivially and
    become fake hubs); multi-word phrases always survive."""
    out = []
    for m in _CAP_RE.finditer(text):
        if len(m.group(0)) < 3:
            continue
        e = _norm_ent(m.group(0))
        if " " not in e and e in _MENTION_BLOCK:
            continue
        out.append(e)
    return out


_HOPWORD_RE = re.compile(r"(\d+)\s*hop")
_2WIKI_TYPE_HOPS = {"comparison": 2, "inference": 2, "compositional": 2,
                    "bridge comparison": 4, "bridge_comparison": 4}


def parse_hop(row: dict) -> int:
    """Hop label: '<N>hop' pattern in hop/id → N; 2wiki type string → mapped;
    fallback = #supporting paragraphs. (A bare digit-grab pulled hex noise out
    of 2wiki ids — hop '87154' — caught live by the stats 선행보고.)"""
    for key in ("hop", "id"):
        m = _HOPWORD_RE.search(str(row.get(key, "")).lower())
        if m:
            return int(m.group(1))
    t = str(row.get("hop", "")).strip().lower()
    if t in _2WIKI_TYPE_HOPS:
        return _2WIKI_TYPE_HOPS[t]
    return sum(1 for p in row["paragraphs"] if p.get("is_supporting"))


@dataclass
class WorldQuery:
    qid: str
    question: str
    answer: str
    hop: int
    gold: np.ndarray          # global edge ids of supporting paragraphs


@dataclass
class BuiltWorld:
    hg: Hypergraph            # nodes=entities, edges=paragraphs (unit_emb stapled)
    entities: list[str]
    unit_texts: list[str]     # "title :: text" per edge
    queries: list[WorldQuery]
    stats: dict = dfield(default_factory=dict)


def build(rows: list[dict], embed_fn=None, dim: int = DEFAULT_DIM) -> BuiltWorld:
    embed = embed_fn if embed_fn is not None else (lambda ts: hash_embed(ts, dim))

    # ---- pass 1: dedup paragraphs, collect mention document-frequency ----
    para_key_to_eid: dict[tuple, int] = {}
    titles: list[str] = []
    texts: list[str] = []
    mentions_per_para: list[list[str]] = []
    df: dict[str, int] = {}
    for row in rows:
        for p in row["paragraphs"]:
            key = (p["title"], p["paragraph_text"])
            if key in para_key_to_eid:
                continue
            para_key_to_eid[key] = len(titles)
            titles.append(_norm_ent(p["title"]))
            texts.append(f"{p['title']} :: {p['paragraph_text']}")
            ms = set(extract_mentions(p["paragraph_text"]))
            mentions_per_para.append(sorted(ms))
            for m in ms:
                df[m] = df.get(m, 0) + 1

    # ---- entity vocabulary: all titles + frequent body mentions ----
    title_set = set(titles)
    vocab = sorted(title_set | {m for m, c in df.items() if c >= MIN_ENTITY_COUNT})
    eidx = {e: i for i, e in enumerate(vocab)}

    members: list[np.ndarray] = []
    mention_misses = 0        # body mentions dropped by the df gate (coverage bound, §9 ②)
    for j, title in enumerate(titles):
        mem = {eidx[title]}   # title entity ALWAYS bound ⇒ arity ≥ 1 structurally
        for m in mentions_per_para[j]:
            if m in eidx:
                mem.add(eidx[m])
            else:
                mention_misses += 1
        members.append(np.array(sorted(mem), dtype=np.int64))

    M = len(members)
    hg = Hypergraph(node_emb=np.asarray(embed(vocab), dtype=np.float64),
                    members=members,
                    edge_freq=np.ones(M), edge_recency=np.zeros(M))
    hg.unit_emb = np.asarray(embed(texts), dtype=np.float64)  # type: ignore[attr-defined]

    # ---- queries: gold paragraph → global edge id (structural recall 1.0) ----
    queries: list[WorldQuery] = []
    for row in rows:
        gold = [para_key_to_eid[(p["title"], p["paragraph_text"])]
                for p in row["paragraphs"] if p.get("is_supporting")]
        queries.append(WorldQuery(qid=str(row.get("id", len(queries))),
                                  question=row["question"], answer=str(row.get("answer", "")),
                                  hop=parse_hop(row), gold=np.array(sorted(set(gold)), dtype=np.int64)))

    # ---- 기술통계 (publish BEFORE results — spec §10 T4.5) ----
    arity = np.array([m.size for m in members])
    deg = np.bincount(np.concatenate(members), minlength=len(vocab))
    hop_counts: dict[int, int] = {}
    for q in queries:
        hop_counts[q.hop] = hop_counts.get(q.hop, 0) + 1
    stats = {
        "n_edges": M, "n_nodes": len(vocab), "nnz": int(arity.sum()),
        "arity": {"mean": round(float(arity.mean()), 2), "p50": int(np.median(arity)),
                  "p90": int(np.percentile(arity, 90)), "max": int(arity.max())},
        "node_degree": {"mean": round(float(deg.mean()), 2),
                        "p90": int(np.percentile(deg, 90)), "max": int(deg.max())},
        "top_hubs": [vocab[i] for i in np.argsort(-deg)[:5]],
        "density_mean_deg_over_M": round(float(deg.mean()) / max(M, 1), 4),
        "queries_per_hop": dict(sorted(hop_counts.items())),
        "gold_recall_structural": 1.0,       # title-membership guarantee (tested)
        "mention_misses_df_gate": mention_misses,
        "embedder": "hash_embed STAND-IN" if embed_fn is None else "injected",
    }
    return BuiltWorld(hg=hg, entities=vocab, unit_texts=texts, queries=queries, stats=stats)
