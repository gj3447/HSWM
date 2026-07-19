"""P5 PILOT (EXPLORATORY, NOT the prereg run) — HSWM vs direct-LLM-rerank, matched LLM budget.

LakatoTree: LakatosTree_HSWM_20260719 / prediction-p5-cognitive-uplift-vs-directllm
  (this pilot does NOT judge the prereg node; results are exploratory only).

QUESTION
  HSWM  = LLM relevance judgments spent OFFLINE on train queries, baked into a weight
          field (frozen cosine + sign-constrained bilinear residual, additive-j design
          from learned_v3_additive.py re-implemented for text candidates);
          eval-time ranking uses 0 LLM calls.
  direct = the SAME LLM judgment budget spent AT INFERENCE: listwise rerank of each
          eval query's own candidates (2-stage when budget/query >= 2).
  Both feed an identical frozen reader (same LLM, same prompt, temperature 0).
  Honest prior: operational-not-cognitive (HSWM <= direct, data-processing inequality).
  Kill criterion (prereg P5): |delta| < 0.03 => operational-only.

DATA: MuSiQue (answerable) validation subset via HF datasets-server
  (each row: question, answer(+aliases), 20 paragraphs with is_supporting flags).
  Ranking task = order the row's own 20 paragraphs; top-k go to the reader.

BUDGET PARITY (LLM judgment/ranking calls):
  HSWM arm : B calls, all offline on train queries (1 listwise judgment per train query).
  direct   : B calls on eval queries (B / n_eval per query, 2-stage rerank).
  Reader   : n_eval calls per arm (identical).
  cosine   : diagnostic 3rd arm, 0 judgment calls (embedding-only ranking + reader).
  All LLM calls are counted per arm and reported; embeddings (bge-m3) are shared
  substrate, identical across arms.

Run:  uv run python ab_p5_pilot.py --n-train 60 --n-eval 30 --budget 60
Every LLM/embed call is disk-cached (resumable). New file only; touches nothing else.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import string
import sys
import time
import urllib.request

import numpy as np

OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
DEFAULT_CACHE = os.environ.get(
    "AB_P5_CACHE", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".ab_p5_cache")
)
LAMBDA_GRID = [0.0, 0.25, 0.5, 1.0, 2.0, 4.0]

HF_ROWS_URL = (
    "https://datasets-server.huggingface.co/rows?dataset=dgslibisey%2FMuSiQue"
    "&config=default&split=validation&offset={off}&length=100"
)
POOL_OFFSETS = (0, 100, 1300, 2100)  # 2hop + 3hop + 4hop pages of the ordered val split


# ---------------------------------------------------------------- io helpers
def _http_json(url: str, payload=None, timeout: int = 600, retries: int = 3):
    data = None if payload is None else json.dumps(payload).encode()
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, data=data,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception as e:  # transient ollama 500s under memory pressure
            last = e
            if attempt < retries:
                wait = (2, 10, 30)[min(attempt, 2)]
                print(f"[retry] {url.rsplit('/',1)[-1]} failed ({e}); "
                      f"retry {attempt+1}/{retries} in {wait}s", file=sys.stderr, flush=True)
                time.sleep(wait)
    raise last  # type: ignore[misc]


class DiskCache:
    def __init__(self, root: str):
        self.root = root
        os.makedirs(root, exist_ok=True)

    def _path(self, kind: str, key: str) -> str:
        h = hashlib.sha1(key.encode()).hexdigest()
        return os.path.join(self.root, f"{kind}_{h}.json")

    def get(self, kind: str, key: str):
        p = self._path(kind, key)
        if os.path.exists(p):
            with open(p) as f:
                return json.load(f)
        return None

    def put(self, kind: str, key: str, value) -> None:
        with open(self._path(kind, key), "w") as f:
            json.dump(value, f)


# ---------------------------------------------------------------- ollama
class LLM:
    """Chat wrapper with per-purpose call counting + disk cache (cached hits still
    count as calls: budget parity is about *judgments consumed*, not wall time)."""

    def __init__(self, model: str, cache: DiskCache):
        self.model = model
        self.cache = cache
        self.calls: dict[str, int] = {}
        self.wall_s = 0.0

    def chat(self, purpose: str, prompt: str, num_predict: int = 256) -> str:
        self.calls[purpose] = self.calls.get(purpose, 0) + 1
        key = json.dumps([self.model, prompt, num_predict])
        hit = self.cache.get("chat", key)
        if hit is not None:
            return hit
        t0 = time.time()
        resp = _http_json(
            f"{OLLAMA}/api/chat",
            {
                "model": self.model,
                "stream": False,
                "messages": [{"role": "user", "content": prompt}],
                "options": {"temperature": 0, "num_predict": num_predict},
            },
        )
        self.wall_s += time.time() - t0
        out = resp["message"]["content"]
        self.cache.put("chat", key, out)
        return out


class Embedder:
    def __init__(self, model: str, cache: DiskCache):
        self.model = model
        self.cache = cache
        self.split_fallbacks = 0  # texts the server 500s on deterministically

    def _embed_one(self, text: str, depth: int = 0) -> list[float]:
        """Single-text embed. The serving stack 500s deterministically on a few benign
        texts (observed: exact sentence fails, each half embeds fine — llama.cpp-style
        token-sequence bug). Fallback: split in half, embed halves, average+renormalize.
        Counted in split_fallbacks and reported in results."""
        try:
            return _http_json(f"{OLLAMA}/api/embed",
                              {"model": self.model, "input": [text]},
                              retries=1)["embeddings"][0]
        except Exception:
            if depth >= 3 or len(text) < 8:
                raise
            self.split_fallbacks += 1
            mid = len(text) // 2
            a = np.array(self._embed_one(text[:mid], depth + 1))
            b = np.array(self._embed_one(text[mid:], depth + 1))
            v = a / max(np.linalg.norm(a), 1e-12) + b / max(np.linalg.norm(b), 1e-12)
            return (v / max(np.linalg.norm(v), 1e-12)).tolist()

    def embed(self, texts: list[str]) -> np.ndarray:
        out: list[np.ndarray | None] = [None] * len(texts)
        missing, missing_idx = [], []
        for i, t in enumerate(texts):
            hit = self.cache.get("emb", json.dumps([self.model, t]))
            if hit is not None:
                out[i] = np.array(hit, dtype=np.float32)
            else:
                missing.append(t)
                missing_idx.append(i)
        for s in range(0, len(missing), 8):
            batch = missing[s : s + 8]
            try:
                embs = _http_json(f"{OLLAMA}/api/embed",
                                  {"model": self.model, "input": batch},
                                  retries=1)["embeddings"]
            except Exception:  # degrade to per-item so one bad batch can't kill the run
                embs = [self._embed_one(t) for t in batch]
            for j, vec in enumerate(embs):
                i = missing_idx[s + j]
                out[i] = np.array(vec, dtype=np.float32)
                self.cache.put("emb", json.dumps([self.model, missing[s + j]]), vec)
        return np.stack(out)  # type: ignore[arg-type]


# ---------------------------------------------------------------- data
def load_pool(cache_dir: str) -> list[dict]:
    path = os.path.join(cache_dir, "musique_val_pool.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    rows: list[dict] = []
    for off in POOL_OFFSETS:
        d = _http_json(HF_ROWS_URL.format(off=off), timeout=120)
        rows += [r["row"] for r in d["rows"]]
    rows = [r for r in rows if r.get("answerable")]
    with open(path, "w") as f:
        json.dump(rows, f)
    return rows


def split_pool(rows: list[dict], n_train: int, n_eval: int, seed: int):
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(rows))
    take = idx[: n_train + n_eval]
    train = [rows[i] for i in take[:n_train]]
    ev = [rows[i] for i in take[n_train:]]
    return train, ev


def hop_of(row: dict) -> str:
    return row["id"].split("_")[0]


# ---------------------------------------------------------------- prompts + parsing
def _snip(text: str, n: int) -> str:
    return " ".join(text.split())[:n]


def cand_block(row: dict, chars: int, only: list[int] | None = None) -> str:
    lines = []
    for p in row["paragraphs"]:
        if only is not None and p["idx"] not in only:
            continue
        lines.append(f"[{p['idx']}] {p['title']}: {_snip(p['paragraph_text'], chars)}")
    return "\n".join(lines)


def parse_idx_list(text: str, valid: set[int]) -> list[int]:
    """First line containing integers wins; dedupe, keep order, filter to valid."""
    m = re.search(r"(?:RANKING|RELEVANT)\s*[:=]?\s*([0-9,\s\[\]>-]+)", text, re.I)
    blob = m.group(1) if m else text
    seen, out = set(), []
    for tok in re.findall(r"\d+", blob):
        v = int(tok)
        if v in valid and v not in seen:
            seen.add(v)
            out.append(v)
    return out


JUDGE_PROMPT = """You label evidence paragraphs for a multi-hop question.

Question: {q}

Paragraphs:
{cands}

Which paragraphs contain information NEEDED to answer the question (usually 2-4 of them)?
Reply with ONLY one line in this exact format:
RELEVANT: <comma-separated paragraph numbers>"""

RERANK_PROMPT = """You rank evidence paragraphs for a multi-hop question.

Question: {q}

Paragraphs:
{cands}

Rank the {top_n} paragraphs most useful for answering, best first.
Reply with ONLY one line in this exact format:
RANKING: <comma-separated paragraph numbers, best first>"""

READER_PROMPT = """Answer the question using ONLY the context below.

Context:
{ctx}

Question: {q}

Give ONLY the shortest exact answer (a name, date, number, or short phrase). No explanation.
Answer:"""


# ---------------------------------------------------------------- metrics
def _norm(s: str) -> str:
    s = s.lower()
    s = "".join(ch for ch in s if ch not in string.punctuation)
    s = re.sub(r"\b(a|an|the)\b", " ", s)
    return " ".join(s.split())


def answer_em(pred: str, golds: list[str]) -> float:
    p = _norm(pred)
    if not p:
        return 0.0
    for g in golds:
        gn = _norm(g)
        if gn and (gn in p or p == gn):
            return 1.0
    return 0.0


def answer_f1(pred: str, golds: list[str]) -> float:
    pt = _norm(pred).split()
    best = 0.0
    for g in golds:
        gt = _norm(g).split()
        if not pt or not gt:
            continue
        common: dict[str, int] = {}
        for t in pt:
            common[t] = common.get(t, 0) + 1
        overlap = sum(min(c, gt.count(t)) for t, c in common.items())
        if overlap == 0:
            continue
        prec, rec = overlap / len(pt), overlap / len(gt)
        best = max(best, 2 * prec * rec / (prec + rec))
    return best


def ndcg_at_k(order: list[int], gold: set[int], k: int = 10) -> float:
    rel = [1.0 if i in gold else 0.0 for i in order[:k]]
    dcg = sum(r / np.log2(j + 2) for j, r in enumerate(rel))
    ideal = sorted([1.0] * min(len(gold), k) + [0.0] * max(0, k - len(gold)), reverse=True)
    idcg = sum(r / np.log2(j + 2) for j, r in enumerate(ideal))
    return float(dcg / idcg) if idcg > 0 else 0.0


def paired_bootstrap_p(a: list[float], b: list[float], n_boot: int = 10000, seed: int = 0) -> float:
    """P(mean(a-b) <= 0) under paired bootstrap. Small => a reliably > b."""
    d = np.asarray(a) - np.asarray(b)
    if d.size == 0:
        return 1.0
    rng = np.random.default_rng(seed)
    means = np.array([d[rng.integers(0, d.size, d.size)].mean() for _ in range(n_boot)])
    return float((means <= 0).mean())


# ---------------------------------------------------------------- embedding substrate
class Field:
    """Shared cosine substrate + HSWM additive-j residual (text re-implementation of
    learned_v3_additive: W = cosine + lambda * ReLU(pe' M q'), residual in PCA space)."""

    def __init__(self, emb: Embedder, proj_dim: int):
        self.emb = emb
        self.proj_dim = proj_dim
        self.mean: np.ndarray | None = None
        self.P: np.ndarray | None = None  # (d_full, proj_dim)
        self.M: np.ndarray | None = None
        self.lam: float = 0.0

    @staticmethod
    def _unit(x: np.ndarray) -> np.ndarray:
        return x / np.maximum(np.linalg.norm(x, axis=-1, keepdims=True), 1e-12)

    def para_embs(self, row: dict) -> np.ndarray:
        texts = [f"{p['title']}\n{_snip(p['paragraph_text'], 1500)}" for p in row["paragraphs"]]
        return self._unit(self.emb.embed(texts))

    def query_emb(self, row: dict) -> np.ndarray:
        return self._unit(self.emb.embed([row["question"]]))[0]

    def fit_pca(self, train_rows: list[dict], seed: int) -> None:
        X = np.concatenate([self.para_embs(r) for r in train_rows])
        self.mean = X.mean(0)
        Xc = X - self.mean
        # top-k right singular vectors
        _, _, vt = np.linalg.svd(Xc, full_matrices=False)
        self.P = vt[: self.proj_dim].T
        rng = np.random.default_rng(seed * 5381 + 3)
        self.M = 0.01 * rng.standard_normal((self.proj_dim, self.proj_dim))

    def _proj(self, x: np.ndarray) -> np.ndarray:
        return (x - self.mean) @ self.P

    def scores(self, row: dict, lam: float | None = None) -> np.ndarray:
        pe = self.para_embs(row)
        q = self.query_emb(row)
        cos = pe @ q
        lam = self.lam if lam is None else lam
        if lam == 0.0 or self.M is None:
            return cos
        resid = (self._proj(pe) @ self.M) @ self._proj(q)
        return cos + lam * np.maximum(0.0, resid)

    def order(self, row: dict, lam: float | None = None) -> list[int]:
        sc = self.scores(row, lam)
        idxs = [p["idx"] for p in row["paragraphs"]]
        return [idxs[i] for i in np.argsort(-sc, kind="stable")]

    def train_additive(self, labeled: list[tuple[dict, list[int]]], seed: int,
                       epochs: int = 120, lr: float = 0.4, lam_train: float = 1.0,
                       val_frac: float = 0.3) -> dict:
        """labeled = [(row, positive_idx_list)]; labels come from the LLM judge (the
        only supervision HSWM buys with its budget). lambda selected on a val split
        of *labeled train queries* by nDCG vs those same LLM labels (grid incl 0 =>
        cosine floor)."""
        rng = np.random.default_rng(seed * 977 + 11)
        perm = rng.permutation(len(labeled))
        nval = max(1, int(len(labeled) * val_frac))
        val = [labeled[i] for i in perm[:nval]]
        tr = [labeled[i] for i in perm[nval:]]

        items = []
        for row, pos in tr:
            if not pos:
                continue
            pe = self.para_embs(row)
            q = self.query_emb(row)
            idxs = [p["idx"] for p in row["paragraphs"]]
            goldpos = [idxs.index(i) for i in pos if i in idxs]
            items.append((pe, q, np.array(goldpos)))

        M = self.M.copy()
        for _ in range(epochs):
            grad = np.zeros_like(M)
            for pe, q, goldpos in items:
                peP, qP = self._proj(pe), self._proj(q)
                resid = (peP @ M) @ qP
                sc = pe @ q + lam_train * np.maximum(0.0, resid)
                z = sc - sc.max()
                p = np.exp(z) / np.exp(z).sum()
                y = np.zeros_like(p)
                y[goldpos] = 1.0 / goldpos.size
                gate = (resid > 0).astype(float) * lam_train
                grad += np.outer(peP.T @ ((p - y) * gate), qP)
            if items:
                M -= lr * grad / len(items)
        self.M = M

        val_ndcg = {}
        for lam in LAMBDA_GRID:
            vals = [ndcg_at_k(self.order(row, lam), set(pos)) for row, pos in val if pos]
            val_ndcg[lam] = float(np.mean(vals)) if vals else 0.0
        self.lam = max(val_ndcg, key=val_ndcg.get)
        return {"val_ndcg_by_lambda": {str(k): round(v, 4) for k, v in val_ndcg.items()},
                "selected_lambda": self.lam,
                "n_train_labeled_used": len(items), "n_val": len(val)}


# ---------------------------------------------------------------- arms
def hswm_offline_judgments(llm: LLM, rows: list[dict], budget: int) -> tuple[list, dict]:
    labeled, parse_fail = [], 0
    for row in rows[:budget]:
        out = llm.chat("hswm_judgment",
                       JUDGE_PROMPT.format(q=row["question"], cands=cand_block(row, 260)),
                       num_predict=64)
        pos = parse_idx_list(out, {p["idx"] for p in row["paragraphs"]})
        if not pos:
            parse_fail += 1
        labeled.append((row, pos[:5]))
    return labeled, {"judgment_calls": min(budget, len(rows)), "parse_failures": parse_fail}


def direct_rerank(llm: LLM, field: Field, row: dict, calls_per_query: int) -> tuple[list[int], int]:
    """Listwise rerank with the eval query's own candidates. 2-stage if budget allows.
    Fallback fill = cosine order (reported)."""
    cos_order = field.order(row, lam=0.0)
    valid = {p["idx"] for p in row["paragraphs"]}
    fails = 0

    out = llm.chat("direct_rerank",
                   RERANK_PROMPT.format(q=row["question"], cands=cand_block(row, 260), top_n=10),
                   num_predict=96)
    r1 = parse_idx_list(out, valid)
    if not r1:
        fails += 1
    order = r1 + [i for i in cos_order if i not in r1]

    if calls_per_query >= 2:
        top10 = order[:10]
        out2 = llm.chat("direct_rerank",
                        RERANK_PROMPT.format(q=row["question"],
                                             cands=cand_block(row, 500, only=top10), top_n=5),
                        num_predict=64)
        r2 = parse_idx_list(out2, set(top10))
        if not r2:
            fails += 1
        order = r2 + [i for i in order if i not in r2]
    return order, fails


def read_answer(llm: LLM, purpose: str, row: dict, order: list[int], k: int) -> str:
    chosen = set(order[:k])
    ctx = "\n\n".join(
        f"{p['title']}: {_snip(p['paragraph_text'], 1200)}"
        for p in row["paragraphs"] if p["idx"] in chosen
    )
    return llm.chat(purpose, READER_PROMPT.format(ctx=ctx, q=row["question"]), num_predict=48)


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n-train", type=int, default=60)
    ap.add_argument("--n-eval", type=int, default=30)
    ap.add_argument("--budget", type=int, default=60,
                    help="LLM judgment/ranking calls per arm (HSWM offline == direct online)")
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--proj-dim", type=int, default=96)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--chat-model", default="gemma3:4b")
    ap.add_argument("--embed-model", default="bge-m3")
    ap.add_argument("--cache-dir", default=DEFAULT_CACHE)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                  "ab_p5_pilot_results.json"))
    args = ap.parse_args()

    if args.budget % args.n_eval != 0:
        print(f"NOTE: budget {args.budget} not divisible by n_eval {args.n_eval}; "
              f"direct arm uses floor() calls per query.", file=sys.stderr)
    calls_per_query = max(1, args.budget // args.n_eval)

    cache = DiskCache(args.cache_dir)
    llm = LLM(args.chat_model, cache)
    emb = Embedder(args.embed_model, cache)
    field = Field(emb, args.proj_dim)

    print(f"[data] loading MuSiQue pool ...", flush=True)
    pool = load_pool(args.cache_dir)
    train_rows, eval_rows = split_pool(pool, args.n_train, args.n_eval, args.seed)
    print(f"[data] pool={len(pool)} train={len(train_rows)} eval={len(eval_rows)} "
          f"hops(eval)={sorted(hop_of(r) for r in eval_rows)}", flush=True)

    t_start = time.time()
    print("[embed] paragraph+query embeddings (shared substrate) ...", flush=True)
    field.fit_pca(train_rows, args.seed)
    for r in eval_rows:  # warm the cache
        field.para_embs(r), field.query_emb(r)

    # --- HSWM arm: offline budget -> labels -> train field; eval = 0 ranking calls
    print(f"[hswm] spending budget B={args.budget} offline on train judgments ...", flush=True)
    labeled, jinfo = hswm_offline_judgments(llm, train_rows, args.budget)
    train_diag = field.train_additive(labeled, args.seed)
    print(f"[hswm] trained: {train_diag}", flush=True)

    # --- rank + read on eval queries
    per_query = []
    direct_fails = 0
    for qi, row in enumerate(eval_rows):
        gold_sup = {p["idx"] for p in row["paragraphs"] if p["is_supporting"]}
        golds = [row["answer"]] + list(row.get("answer_aliases") or [])

        orders = {
            "cosine": field.order(row, lam=0.0),
            "hswm": field.order(row),  # 0 LLM ranking calls at eval time
        }
        d_order, d_fail = direct_rerank(llm, field, row, calls_per_query)
        orders["direct"] = d_order
        direct_fails += d_fail

        rec = {"id": row["id"], "hop": hop_of(row), "question": row["question"],
               "answer": row["answer"]}
        for arm, order in orders.items():
            pred = read_answer(llm, f"reader_{arm}", row, order, args.top_k)
            rec[arm] = {
                "pred": pred.strip()[:200],
                "em": answer_em(pred, golds),
                "f1": round(answer_f1(pred, golds), 4),
                "hit_at_k": 1.0 if set(order[: args.top_k]) & gold_sup else 0.0,
                "sup_recall_at_k": round(len(set(order[: args.top_k]) & gold_sup)
                                         / max(1, len(gold_sup)), 4),
                "ndcg10_vs_gold": round(ndcg_at_k(order, gold_sup), 4),
            }
        per_query.append(rec)
        print(f"[eval {qi+1}/{len(eval_rows)}] " +
              " ".join(f"{a}:em={rec[a]['em']:.0f}" for a in orders), flush=True)

    # --- aggregate
    arms = ["cosine", "hswm", "direct"]
    agg = {}
    for arm in arms:
        agg[arm] = {m: round(float(np.mean([q[arm][m] for q in per_query])), 4)
                    for m in ("em", "f1", "hit_at_k", "sup_recall_at_k", "ndcg10_vs_gold")}

    em_h = [q["hswm"]["em"] for q in per_query]
    em_d = [q["direct"]["em"] for q in per_query]
    f1_h = [q["hswm"]["f1"] for q in per_query]
    f1_d = [q["direct"]["f1"] for q in per_query]

    result = {
        "label": "EXPLORATORY_PILOT — not the prereg P5 run; do not judge "
                 "prediction-p5-cognitive-uplift-vs-directllm with this",
        "tree": "LakatosTree_HSWM_20260719",
        "prereg_ref": "prediction-p5-cognitive-uplift-vs-directllm",
        "config": {k: getattr(args, k.replace("-", "_")) for k in
                   ("n_train", "n_eval", "budget", "top_k", "proj_dim", "seed",
                    "chat_model", "embed_model")},
        "data": {"dataset": "MuSiQue (answerable) validation subset via HF datasets-server",
                 "pool_size": len(pool),
                 "eval_hops": {h: sum(1 for r in eval_rows if hop_of(r) == h)
                               for h in sorted({hop_of(r) for r in eval_rows})}},
        "llm_call_parity": {
            "hswm_judgment_calls": llm.calls.get("hswm_judgment", 0),
            "direct_rerank_calls": llm.calls.get("direct_rerank", 0),
            "reader_calls": {a: llm.calls.get(f"reader_{a}", 0) for a in arms},
            "parity_ok": llm.calls.get("hswm_judgment", 0) == llm.calls.get("direct_rerank", 0),
        },
        "hswm_training": {**jinfo, **train_diag},
        "direct_parse_fallbacks": direct_fails,
        "embed_split_fallbacks": emb.split_fallbacks,
        "aggregate": agg,
        "delta": {
            "em_hswm_minus_direct": round(agg["hswm"]["em"] - agg["direct"]["em"], 4),
            "f1_hswm_minus_direct": round(agg["hswm"]["f1"] - agg["direct"]["f1"], 4),
            "p_hswm_gt_direct_em": round(paired_bootstrap_p(em_h, em_d, seed=args.seed), 4),
            "p_direct_gt_hswm_em": round(paired_bootstrap_p(em_d, em_h, seed=args.seed), 4),
            "p_hswm_gt_direct_f1": round(paired_bootstrap_p(f1_h, f1_d, seed=args.seed), 4),
            "p_direct_gt_hswm_f1": round(paired_bootstrap_p(f1_d, f1_h, seed=args.seed), 4),
        },
        "wall_clock_s": round(time.time() - t_start, 1),
        "llm_wall_s": round(llm.wall_s, 1),
        "per_query": per_query,
    }
    with open(args.out, "w") as f:
        json.dump(result, f, indent=1, ensure_ascii=False)
    print(json.dumps({k: result[k] for k in
                      ("llm_call_parity", "hswm_training", "aggregate", "delta")},
                     indent=1, ensure_ascii=False))
    print(f"[done] results -> {args.out}", flush=True)


if __name__ == "__main__":
    main()
