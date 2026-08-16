"""Load a REAL hypergraph from the SYMPOSIUM Neo4j KG into an npz cache.

Substrate (probed 2026-07-19): 93k nodes, 28.5k with embeddings. We use the
coherent 768-dim ResearchFinding embedding space + the reified :Hyperedge nodes
that bind those findings (PARTICIPATES_IN / CONTAINS / AGGREGATES / DISPATCHED).

Embeddings are pulled server-side straight into numpy and cached to .npz — they
NEVER enter an agent context. Re-runs read the cache offline.

Honesty (DB_AND_FALSIFIER_DECISION §2.8): the project KG is a SECONDARY /
confirmatory substrate, NOT a valid PRIMARY falsifier (recency-gold entanglement,
no clean query->gold labels). The link-prediction task built here is exploratory;
leakage is controlled by a context/query split (query findings are removed from
every hyperedge's member pool so a query never sees itself).

Usage:
    NEO4J_URI=... NEO4J_USER=... NEO4J_PW=... NEO4J_DATABASE=neo4j \
      uv run --extra kg python -m hswm.prototypes.neo4j_loader
"""
from __future__ import annotations

import os

import numpy as np

CACHE = "data/real_kg_hypergraph.npz"
DIM = 768
REL_TYPES = "PARTICIPATES_IN|CONTAINS|AGGREGATES|DISPATCHED"


def _creds():
    names = ("NEO4J_URI", "NEO4J_USER", "NEO4J_PW", "NEO4J_DATABASE")
    values = {name: os.environ.get(name) for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError(
            "explicit read-only Neo4j configuration required; missing "
            + ", ".join(missing)
        )
    return (
        values["NEO4J_URI"],
        values["NEO4J_USER"],
        values["NEO4J_PW"],
        values["NEO4J_DATABASE"],
    )


def load_and_cache(max_hyperedges: int = 1500, min_arity: int = 3, path: str = CACHE) -> dict:
    from neo4j import GraphDatabase, READ_ACCESS  # optional dep (extra 'kg')

    uri, user, pw, database = _creds()
    driver = GraphDatabase.driver(uri, auth=(user, pw))
    try:
        with driver.session(database=database, default_access_mode=READ_ACCESS) as s:
            rows = s.run(
                f"""
                MATCH (h:Hyperedge)-[:{REL_TYPES}]-(m:ResearchFinding)
                WHERE m.embedding IS NOT NULL AND size(m.embedding) = {DIM}
                WITH h, collect(DISTINCT elementId(m)) AS members
                WHERE size(members) >= {min_arity}
                RETURN elementId(h) AS hid, members
                LIMIT {max_hyperedges}
                """
            ).data()
            member_id_set = sorted({mid for r in rows for mid in r["members"]})
            # Pull embeddings in the dedicated batch-read exception. Values never
            # enter an agent/MCP context.
            emb_rows = s.run(
                "MATCH (m:ResearchFinding) WHERE elementId(m) IN $ids "
                "RETURN elementId(m) AS mid, m.embedding AS emb",
                ids=member_id_set,
            ).data()
    finally:
        driver.close()

    id2local = {}
    embs = []
    for r in emb_rows:
        id2local[r["mid"]] = len(embs)
        embs.append(np.asarray(r["emb"], dtype=np.float64))
    node_emb = np.vstack(embs)

    members_local = []
    for r in rows:
        loc = [id2local[m] for m in r["members"] if m in id2local]
        if len(loc) >= 2:
            members_local.append(np.array(sorted(set(loc)), dtype=np.int64))

    flat = np.concatenate(members_local)
    offsets = np.cumsum([0] + [len(m) for m in members_local])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    np.savez_compressed(path, node_emb=node_emb, members_flat=flat, members_offsets=offsets)
    print(f"cached {node_emb.shape[0]} nodes (dim {node_emb.shape[1]}), "
          f"{len(members_local)} hyperedges -> {path}")
    return {"n_nodes": node_emb.shape[0], "n_edges": len(members_local)}


def load_members(path: str = CACHE):
    """Return (node_emb (N,d), members list[np.ndarray]) from cache."""
    z = np.load(path)
    node_emb = z["node_emb"]
    flat, off = z["members_flat"], z["members_offsets"]
    members = [flat[off[j]:off[j + 1]] for j in range(len(off) - 1)]
    return node_emb, members


def main():
    load_and_cache()


if __name__ == "__main__":
    main()
