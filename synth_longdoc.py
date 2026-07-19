"""Length × hop-depth ORTHOGONAL synthetic world — Experiment B substrate (v2).

Owner's untested intuition (HSWM/내가 주는 말.txt): HSWM beats cosine
*specifically on long units* (paragraph → book) because structural weights
survive where the mean-pooled embedding dilutes. Competing SR-lineage
explanation (PROM_PRIOR_ART_TRIBUNAL §6): the win/loss pattern is about
*multi-hop propagation absence*, not span length. This world CROSSES the two
axes so Experiment B can attribute the delta.

v2 — rebuilt after adversarial review wf_a931ba07-21a (14 confirmed findings).
v1 used a CONTAINMENT relevance premise ("unit contains topic = relevant") with
gold truncated to 3; at chapter length (k=16 of T=60 topics) containment
saturates, so the judge ceiling collapsed with length BY CONSTRUCTION and the
"length trend refuted" verdict was an artifact (flips with n_topics). Without
truncation the premise degenerates the other way (pool ≈ all-gold at chapter).
Containment is therefore the WRONG formalization of the owner's claim, which is
about a unit being ABOUT a topic, not merely mentioning it.

v2 premise — ABOUTNESS latent:
- Each length level has `gold_units_per_topic` DESIGNED units per topic whose
  owner latent = that topic ("a chapter about X"); fill units have owner = -1
  ("chapters that merely mention things"). Gold = designed units of the
  (hop-resolved) target. Base rate is CONSTANT across length levels — no
  saturation ceiling, the length axis is free to move either way.
- Unit embedding = mean of member-topic embeddings (+noise): the owner topic's
  share of the mean shrinks as k grows → embedding DILUTION with length (the
  documented single-vector failure mode; LIMIT / Lost-in-a-Single-Vector).
- HOP chains: bridge_next links t0→t1→…→th; a query written about t0 has gold
  = units ABOUT t_h. Static fields cannot propagate; a spreading arm can.
- Same query topics reused across every length stratum → per-query deltas are
  PAIRED across strata (stats_protocol.paired_trend_p applies).

What a synthetic world can and cannot say (honesty): it demonstrates MECHANISM
SUFFICIENCY — *if* an aboutness signal survives length while embeddings dilute,
what does each arm do — it cannot decide whether real long documents satisfy
that premise. The real-data slot (NoCha / NarrativeQA / QASPER) decides that.

Honest regimes (harness must be able to say NO_GAIN — synth.py pattern):
  "aboutness" — premise as above; judge/structure signal exists beyond cosine.
  "null"      — unit embeddings pure noise AND gold assigned via a hidden
      permutation of owners: neither cosine nor the exposed owner latent
      carries signal; no arm should beat any other. Teeth check.

Determinism: explicit integer seeds; no global RNG; no hash() (review: PYTHONHASHSEED).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from hypergraph import Hypergraph

LENGTH_LEVELS: dict[str, int] = {"sentence": 1, "paragraph": 3, "section": 8, "chapter": 16}
LENGTH_ORDER = ["sentence", "paragraph", "section", "chapter"]
LEVEL_INDEX = {lv: i for i, lv in enumerate(LENGTH_ORDER)}  # deterministic pool seeding


def _unit(x: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(x, axis=-1, keepdims=True)
    return x / np.clip(n, 1e-12, None)


@dataclass
class LongDocWorld:
    """One (regime, seed) world holding every length stratum over shared topics."""
    regime: str
    topic_emb: np.ndarray                     # (T, d)
    bridge_next: np.ndarray                   # (T,) chain: topic i → bridge_next[i]
    strata: dict[str, Hypergraph]             # level → hypergraph of units
    unit_topics: dict[str, list[np.ndarray]]  # level → exposed members per unit
    unit_owner: dict[str, np.ndarray]         # level → owner topic per unit (-1 = none)
    query_topic: np.ndarray                   # (Q,) surface topic t0
    query_hop: np.ndarray                     # (Q,) hop depth
    query_emb: np.ndarray                     # (Q, d) noisy embedding of t0
    gold: dict[str, list[np.ndarray]]         # level → gold[q] = units ABOUT t_h

    @property
    def Q(self) -> int:
        return self.query_emb.shape[0]


def _chain_target(t0: int, hop: int, bridge_next: np.ndarray) -> int:
    t = int(t0)
    for _ in range(hop):
        t = int(bridge_next[t])
    return t


def generate(regime: str, seed: int, n_topics: int = 60, dim: int = 24,
             units_per_level: int = 260, n_queries: int = 120,
             max_hop: int = 2, gold_units_per_topic: int = 3,
             emb_noise: float = 0.35) -> LongDocWorld:
    """Build one world. Topics, queries, and chains are shared across strata.

    n_topics / gold_units_per_topic are part of the experimental premise (review
    finding: v1's verdict was sensitive to n_topics). In v2 the gold base rate
    is n_topics-independent by construction (owner latent), but both stay
    reported alongside results.
    """
    if regime not in ("aboutness", "null"):
        raise ValueError(f"unknown regime {regime!r}")
    rng = np.random.default_rng(seed)

    topic_emb = _unit(rng.standard_normal((n_topics, dim)))
    bridge_next = rng.permutation(n_topics)

    query_topic = rng.integers(0, n_topics, size=n_queries)
    query_hop = np.arange(n_queries) % (max_hop + 1)
    query_emb = _unit(topic_emb[query_topic] + emb_noise * rng.standard_normal((n_queries, dim)))

    strata: dict[str, Hypergraph] = {}
    unit_topics: dict[str, list[np.ndarray]] = {}
    unit_owner: dict[str, np.ndarray] = {}
    gold: dict[str, list[np.ndarray]] = {}

    for level in LENGTH_ORDER:
        k = LENGTH_LEVELS[level]
        members: list[np.ndarray] = []
        owners: list[int] = []
        # designed units: owner topic guaranteed member, others drawn from the REST
        # (review fix: no collision shrink — exactly k members, owner always present)
        for t in range(n_topics):
            rest = np.setdiff1d(np.arange(n_topics), [t])
            for _ in range(gold_units_per_topic):
                others = rng.choice(rest, size=k - 1, replace=False) if k > 1 else np.empty(0, dtype=np.int64)
                members.append(np.sort(np.concatenate([[t], others])).astype(np.int64))
                owners.append(t)
        while len(members) < units_per_level:
            members.append(np.sort(rng.choice(n_topics, size=min(k, n_topics), replace=False)).astype(np.int64))
            owners.append(-1)

        m_arr = len(members)
        owner_arr = np.array(owners, dtype=np.int64)
        pooled = np.stack([topic_emb[m].mean(axis=0) for m in members])
        node_emb = _unit(pooled + emb_noise * rng.standard_normal((m_arr, dim)))
        if regime == "null":
            node_emb = _unit(rng.standard_normal((m_arr, dim)))

        hg = Hypergraph(
            node_emb=topic_emb,
            members=members,
            edge_freq=rng.integers(1, 30, size=m_arr).astype(np.float64),
            edge_recency=rng.random(m_arr),
        )
        hg.unit_emb = node_emb  # type: ignore[attr-defined]  # per-unit (edge-level) view

        gold_owner = owner_arr
        if regime == "null":
            # hidden permutation of owner labels: gold is real but the EXPOSED
            # owner latent (what the judge reads) is uninformative for it
            gold_owner = owner_arr[rng.permutation(m_arr)]

        g: list[np.ndarray] = []
        for q in range(n_queries):
            th = _chain_target(int(query_topic[q]), int(query_hop[q]), bridge_next)
            g.append(np.flatnonzero(gold_owner == th).astype(np.int64))

        strata[level] = hg
        unit_topics[level] = members
        unit_owner[level] = owner_arr
        gold[level] = g

    return LongDocWorld(regime=regime, topic_emb=topic_emb, bridge_next=bridge_next,
                        strata=strata, unit_topics=unit_topics, unit_owner=unit_owner,
                        query_topic=query_topic, query_hop=query_hop,
                        query_emb=query_emb, gold=gold)


def candidate_pool(world: LongDocWorld, level: str, q: int, pool_size: int,
                   seed: int) -> np.ndarray:
    """Fixed rerank pool: random units ∪ gold (falsifier §2.2 rerank isolation).

    Seeded with LEVEL_INDEX (review fix: hash(level) was PYTHONHASHSEED-dependent,
    breaking the preregistered determinism claim).
    """
    rng = np.random.default_rng(seed * 99991 + q * 31 + LEVEL_INDEX[level] * 7717)
    m = world.strata[level].M
    base = rng.choice(m, size=min(pool_size, m), replace=False)
    pool = np.unique(np.concatenate([base, world.gold[level][q]]))
    if pool.size > pool_size:
        goldset = set(world.gold[level][q].tolist())
        extras = [e for e in pool.tolist() if e not in goldset]
        keep = list(goldset) + extras[: pool_size - len(goldset)]
        pool = np.array(sorted(keep), dtype=np.int64)
    return pool
