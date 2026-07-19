"""T3 + T5 — certified μ selection, null-shuffle teeth, real-data certification.

T3 (offline):
  select_mu()        certified μ from MU_GRID: the best-mean arm must beat μ=0 on
                     PAIRED validation nDCG by SELECT_Z_ADJ × SE (multiplicity-
                     corrected, spec §5 F2). Ported quirk (INTENDED conservatism,
                     expB_longdoc lineage): only the best-MEAN arm is certified —
                     if it fails, return 0 even if a smaller arm would pass.
  shuffle_world()    EXACT degree-preserving membership shuffle (configuration-
                     model pairwise swaps with within-edge-duplicate rejection:
                     per-node degree and per-edge arity preserved bit-exactly).
  null_gate()        H-T2 (v2): gate is on CERTIFICATION, not raw residuals —
                     shuffled worlds still have structure so a_K ≠ a_0 is
                     generic; the requirement is that no seed certifies μ>0.
                     Any certified μ>0 on a null world ⇒ HARNESS_BROKEN.

T5 first pass (network + dgx bge-m3; 0-LLM FIELD — honest scope):
  λ_j = 0 and b ≡ 1: the field is cosine-only, so this pass answers exactly ONE
  question — "does entity-world traversal beat pointwise cosine at matched
  0-inference budget?" — and does NOT exercise judgment or supersession arms
  (those are T4/H-T3). Stats are published BEFORE deltas (T4.5 discipline).
  Deployment default stays μ=0 unless certification passes per corpus.

Run:  uv run python traversal_cert.py teeth
      OLLAMA_URL=http://127.0.0.1:11434 uv run python traversal_cert.py real --dataset musique
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

import numpy as np

import metrics
import traversal as tv
import world_builder as wb
from weight_field import WeightField

SELECT_Z_ADJ = 2.5          # spec §5 F2 (max-t/Bonferroni over 4 non-zero arms)
MU_GRID = tv.MU_GRID
SEEDS = (0, 1, 2, 3, 4)
K_EVAL = 10
VAL_FRAC = 0.5
OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
EMBED_MODEL = "bge-m3"


# ---------- field/eval plumbing ----------

def make_field(world: wb.BuiltWorld) -> WeightField:
    """Cosine-only field over the PARAGRAPH view (unit_emb), b ≡ 1 (0-LLM pass)."""
    f = WeightField(world.hg, M=None)
    f._pooled = world.hg.unit_emb        # score units, not member-mean (test_world_builder 관습)
    return f


def _full_wtrav(field: WeightField, q_emb: np.ndarray, mu: float,
                index: tv.TraversalIndex) -> np.ndarray:
    M = field.hg.M
    ids, scores, _rc = tv.traverse(field, q_emb, k=M, mu=mu, index=index)
    out = np.empty(M)
    out[ids] = scores
    return out


def eval_queries(field: WeightField, world: wb.BuiltWorld, q_ids: list[int],
                 q_embs: np.ndarray, mu: float, index: tv.TraversalIndex,
                 seed: int = 0, trips: dict | None = None) -> np.ndarray:
    """Per-query nDCG@K_EVAL over the full edge pool (paired across arms by query).

    trips (optional dict) accumulates abstain reasons — spec §5 mandates
    publishing the trip 발화율 (a guard firing on 40% of queries must be
    visible, not silently eating the treatment)."""
    edges = np.arange(world.hg.M)
    out = np.empty(len(q_ids))
    for i, qi in enumerate(q_ids):
        M = field.hg.M
        ids, scores, rc = tv.traverse(field, q_embs[qi], k=M, mu=mu, index=index)
        w = np.empty(M)
        w[ids] = scores
        if trips is not None and mu > 0:
            key = rc.abstain_reason or "no_abstain"
            trips[key] = trips.get(key, 0) + 1
        out[i] = metrics.ndcg_at_k(w, world.queries[qi].gold, edges, k=K_EVAL, seed=seed)
    return out


def select_mu(field: WeightField, world: wb.BuiltWorld, val_ids: list[int],
              q_embs: np.ndarray, index: tv.TraversalIndex, seed: int = 0) -> tuple[float, dict]:
    """Certified μ (0 admissible). Best-mean arm only; SELECT_Z_ADJ × SE paired gate."""
    base = eval_queries(field, world, val_ids, q_embs, 0.0, index, seed)
    best_mu, best_mean, certified = 0.0, float(base.mean()), False
    diag = {"val_mean_mu0": round(float(base.mean()), 4)}
    for mu in MU_GRID[1:]:
        v = eval_queries(field, world, val_ids, q_embs, mu, index, seed)
        m = float(v.mean())
        diag[f"val_mean_mu{mu}"] = round(m, 4)
        if m > best_mean:
            d = v - base
            se = float(d.std(ddof=1)) / max(np.sqrt(d.size), 1.0)
            best_mu, best_mean = mu, m
            certified = bool(float(d.mean()) >= SELECT_Z_ADJ * se)
    chosen = best_mu if certified else 0.0
    diag.update({"best_mu": best_mu, "certified": certified, "chosen_mu": chosen})
    return chosen, diag


# ---------- T3: null-shuffle teeth ----------

def shuffle_world(world: wb.BuiltWorld, seed: int) -> wb.BuiltWorld:
    """EXACT degree-preserving membership shuffle (configuration-model swaps).

    Random pairwise swaps on the incidence COO, rejecting any swap that would
    duplicate a node within an edge — per-node degree AND per-edge arity are
    preserved bit-exactly while co-membership semantics is destroyed. (A naive
    global permutation + unique shrinks incidence ~12% and broke the
    degree-preservation contract — caught by test, replaced.)"""
    rng = np.random.default_rng(seed * 60013 + 7)
    hg = world.hg
    arity = np.array([m.size for m in hg.members])
    node_idx = np.concatenate(hg.members).copy()
    edge_of = np.repeat(np.arange(hg.M), arity)
    edge_sets = [set(m.tolist()) for m in hg.members]
    nnz = node_idx.size
    for i, j in rng.integers(0, nnz, size=(20 * nnz, 2)):
        u, v = int(node_idx[i]), int(node_idx[j])
        ei, ej = int(edge_of[i]), int(edge_of[j])
        if ei == ej or u == v or u in edge_sets[ej] or v in edge_sets[ei]:
            continue
        node_idx[i], node_idx[j] = v, u
        edge_sets[ei].discard(u); edge_sets[ei].add(v)
        edge_sets[ej].discard(v); edge_sets[ej].add(u)
    members, pos = [], 0
    for a in arity:
        members.append(np.sort(node_idx[pos:pos + a]))
        pos += a
    from hypergraph import Hypergraph
    hg2 = Hypergraph(node_emb=hg.node_emb, members=members,
                     edge_freq=hg.edge_freq.copy(), edge_recency=hg.edge_recency.copy())
    hg2.unit_emb = hg.unit_emb            # type: ignore[attr-defined]  # embeddings untouched
    return wb.BuiltWorld(hg=hg2, entities=world.entities, unit_texts=world.unit_texts,
                         queries=world.queries, stats=dict(world.stats, shuffled=True))


def null_gate(world: wb.BuiltWorld, q_embs: np.ndarray, seeds=SEEDS) -> dict:
    """H-T2: every seed must certify μ=0 on the shuffled world, else HARNESS_BROKEN."""
    chosen = []
    for s in seeds:
        w2 = shuffle_world(world, s)
        field = make_field(w2)
        index = tv.build_index(w2.hg)
        rng = np.random.default_rng(s * 977 + 3)
        val = list(rng.permutation(len(w2.queries))[: max(2, int(len(w2.queries) * VAL_FRAC))])
        mu, _ = select_mu(field, w2, val, q_embs, index, seed=s)
        chosen.append(mu)
    ok = all(m == 0.0 for m in chosen)
    return {"verdict": "NO_GAIN" if ok else "HARNESS_BROKEN", "chosen_mu_per_seed": chosen}


# ---------- T5: real-data first pass ----------

EMBED_FALLBACKS: list[str] = []   # items that needed hash fallback (reported in stats)


def _embed_call(inputs: list[str]) -> list[list[float]]:
    payload = json.dumps({"model": EMBED_MODEL, "input": inputs}).encode()
    req = urllib.request.Request(f"{OLLAMA}/api/embed", data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        embs = json.loads(r.read().decode())["embeddings"]
    if not np.isfinite(np.asarray(embs)).all():
        raise RuntimeError("non-finite embedding returned")
    return embs


def _embed_batch(texts: list[str], batch: int = 32) -> np.ndarray:
    """Resilient embedding: sanitize + bounded retries + per-item fallback.

    ollama returns 500 on some inputs/blips (observed live at 3136/6007);
    ab_p5_full's embedder had retry/fallback — ported. No retry storms: 3
    attempts with fixed backoff, then per-item isolation; a persistently
    failing ITEM raises loudly with its preview (no silent fabrication)."""
    import time
    out: list[list[float]] = []
    clean = [(t.strip()[:4000] or "-") for t in texts]
    for i in range(0, len(clean), batch):
        chunk = clean[i:i + batch]
        for attempt in range(3):
            try:
                out.extend(_embed_call(chunk))
                break
            except Exception:
                if attempt < 2:
                    time.sleep(2 + 3 * attempt)
                    continue
                for item in chunk:          # isolate the poison item
                    emb = None
                    # observed live: bge-m3 emits NaN for certain plain inputs
                    # (ollama log: 'json: unsupported value: NaN') — perturb
                    # tokenization first, hash fallback last (counted, loud).
                    for variant in (item, item + ".", "passage: " + item):
                        try:
                            emb = _embed_call([variant])
                            break
                        except Exception:
                            continue
                    if emb is None:
                        print(f"  !! hash-fallback embed for {item[:60]!r}", flush=True)
                        EMBED_FALLBACKS.append(item[:80])
                        emb = [wb.hash_embed([item], 1024)[0].tolist()]
                    out.extend(emb)
        if (i // batch) % 10 == 0 or i + batch >= len(clean):
            print(f"  embedded {min(i + batch, len(clean))}/{len(clean)}", flush=True)
    return np.asarray(out, dtype=np.float64)


def run_real(dataset: str, cache_dir: str = ".ab_p5_cache", n_rows: int | None = 200) -> dict:
    import hashlib

    import ab_p5_full as ab
    os.makedirs(cache_dir, exist_ok=True)
    all_rows = ab.load_pool(dataset, cache_dir)
    # hop-STRATIFIED round-robin sampling — head-truncation destroyed the hop
    # mix live (musique first 200 rows were ALL 2-hop; offsets are hop-ordered)
    by_hop: dict[int, list[dict]] = {}
    for r in all_rows:
        by_hop.setdefault(wb.parse_hop(r), []).append(r)
    rows: list[dict] = []
    i = 0
    while (n_rows is None or len(rows) < n_rows) and any(i < len(v) for v in by_hop.values()):
        for h in sorted(by_hop):
            if i < len(by_hop[h]) and (n_rows is None or len(rows) < n_rows):
                rows.append(by_hop[h][i])
        i += 1
    print(f"[{dataset}] rows={len(rows)} (stratified from {len(all_rows)})")

    world = wb.build(rows, embed_fn=lambda ts: np.zeros((len(ts), 8)))  # shape-only pass for texts
    vocab_sha = hashlib.sha256(("\n".join(world.entities) + f"|u{len(world.unit_texts)}"
                                ).encode()).hexdigest()[:12]
    embed_cache = os.path.join(cache_dir, f"cert_embed_{dataset}_{vocab_sha}.npz")
    ent_texts, unit_texts = world.entities, world.unit_texts
    q_texts = [q.question for q in world.queries]
    if os.path.exists(embed_cache):
        z = np.load(embed_cache)
        ent_e, unit_e, q_e = z["ent"], z["unit"], z["q"]
        print("  embeddings from cache")
    else:
        print(f"  embedding {len(ent_texts)} entities + {len(unit_texts)} units + {len(q_texts)} queries via {EMBED_MODEL}")
        ent_e, unit_e, q_e = _embed_batch(ent_texts), _embed_batch(unit_texts), _embed_batch(q_texts)
        np.savez_compressed(embed_cache, ent=ent_e, unit=unit_e, q=q_e)

    # rebuild with real embeddings injected (order-stable: same rows ⇒ same vocab order)
    calls = iter([ent_e, unit_e])
    world = wb.build(rows, embed_fn=lambda ts: next(calls))
    world.stats["embedder"] = f"{EMBED_MODEL} (dgx ollama)"
    print("STATS(선행 보고):", json.dumps(world.stats, ensure_ascii=False))

    field = make_field(world)
    index = tv.build_index(world.hg)
    rng = np.random.default_rng(42)
    perm = rng.permutation(len(world.queries))
    n_val = int(len(perm) * VAL_FRAC)
    val_ids, test_ids = list(perm[:n_val]), list(perm[n_val:])

    mu, diag = select_mu(field, world, val_ids, q_e, index, seed=0)
    print("CERT:", json.dumps(diag))

    # trip 발화율은 항상 측정 (μ=0로 인증돼도 순회 arm이 왜 죽었는지 보여야 함)
    trips: dict[str, int] = {}
    base = eval_queries(field, world, test_ids, q_e, 0.0, index, seed=1)
    probe_mu = mu if mu > 0 else 0.4
    dep_probe = eval_queries(field, world, test_ids, q_e, probe_mu, index, seed=1, trips=trips)
    dep = dep_probe if mu > 0 else base
    trip_rate = {k: round(v / max(len(test_ids), 1), 3) for k, v in sorted(trips.items())}
    per_hop: dict[int, list[float]] = {}
    probe_hop: dict[int, list[float]] = {}
    for j, qi in enumerate(test_ids):
        per_hop.setdefault(world.queries[qi].hop, []).append(float(dep[j] - base[j]))
        probe_hop.setdefault(world.queries[qi].hop, []).append(float(dep_probe[j] - base[j]))
    report = {
        "dataset": dataset, "n_rows": len(rows), "chosen_mu": mu, "cert_diag": diag,
        "test_mean_ndcg_pointwise": round(float(base.mean()), 4),
        "test_mean_ndcg_deployed": round(float(dep.mean()), 4),
        "delta_by_hop": {h: {"n": len(v), "mean": round(float(np.mean(v)), 4)}
                         for h, v in sorted(per_hop.items())},
        "probe_delta_by_hop_EXPLORATORY": {h: {"n": len(v), "mean": round(float(np.mean(v)), 4)}
                                           for h, v in sorted(probe_hop.items())},
        "verdict": "TRAVERSAL_CERTIFIED" if mu > 0 else "TRAVERSAL_OFF (certified floor)",
        "scope": "0-LLM field (lambda_j=0, b==1) — judgment/supersession arms NOT exercised (T4)",
        "trip_rate_probe_arm": {"probe_mu": probe_mu, **trip_rate},
        "embed_hash_fallbacks": list(EMBED_FALLBACKS),
        "stats": world.stats,
    }
    out = f"cert_{dataset}_result.json"
    with open(out, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(f"VERDICT: {report['verdict']}  ->  {out}")
    return report


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "teeth"
    if mode == "teeth":
        from tests.test_traversal_cert import _corpus_rows
        rows = _corpus_rows(seed=0)
        world = wb.build(rows)
        q_e = wb.hash_embed([q.question for q in world.queries], wb.DEFAULT_DIM)
        print(json.dumps(null_gate(world, q_e), indent=1))
    elif mode == "real":
        ds = sys.argv[sys.argv.index("--dataset") + 1] if "--dataset" in sys.argv else "musique"
        run_real(ds)
    else:
        raise SystemExit(f"unknown mode {mode!r}")
