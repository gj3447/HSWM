"""P5 FULL PREREG RUN — HSWM vs direct-LLM-rerank, matched LLM budget, strong judge.

LakatoTree: LakatosTree_HSWM_20260719 / prediction-p5-cognitive-uplift-vs-directllm
This is the *full prereg* execution (pilot = ab_p5_pilot.py, gemma3:4b, INCONCLUSIVE
with a 4B-judge-worse-than-cosine confound). Confound removal: strong judge/reader
(qwen3.6-27b on dgx vLLM, OpenAI-compatible endpoint) for ALL LLM roles.

Extends the pilot (structure inherited unchanged):
  3 arms   : cosine (diagnostic, 0 judgment calls) /
             hswm  (budget spent OFFLINE -> additive-j weight field, 0 eval calls) /
             direct (same budget spent AT INFERENCE: listwise rerank per eval query)
  frozen reader identical across arms; matched judgment-call budget counters; disk cache.
New here:
  * --chat-backend {ollama,openai}: OpenAI-compatible /chat/completions backend
    (vLLM qwen3.6-27b). Reasoning models: content is stripped; <think> blocks removed;
    thinking disabled by default via chat_template_kwargs (--think to re-enable).
  * --dataset {musique,2wiki}: MuSiQue (answerable) + 2WikiMultihopQA
    (framolfese/2WikiMultihopQA via HF datasets-server), normalized to one row schema.
  * judge-quality diagnostic vs gold supporting paragraphs (pilot confound check:
    judge labels must beat cosine-top-3 pseudo-labels; else confound persists).
  * --parallel N: thread-parallel eval loop (per-row independence; counters locked).
  * combine mode: merge per-run JSONs -> ab_p5_full_results.json with the mechanical
    prereg assessment (metric = hswm_answer_f1_minus_directllm; cognitive iff
    delta >= +0.03 on every dataset AND worst seed; |delta| < 0.03 => operational-only;
    Goodhart co-primary: nDCG up + F1 flat => REFUTED).

Run (per dataset x seed), then combine:
  .venv/bin/python ab_p5_full.py run --dataset musique --seed 7  --out ab_p5_full_musique_s7.json
  .venv/bin/python ab_p5_full.py run --dataset musique --seed 13 --out ab_p5_full_musique_s13.json
  .venv/bin/python ab_p5_full.py run --dataset 2wiki   --seed 7  --out ab_p5_full_2wiki_s7.json
  .venv/bin/python ab_p5_full.py combine --runs ab_p5_full_*.json --out ab_p5_full_results.json

NO LakatoTree submit_result from here; parent verifies and judges. New file only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import string
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np

OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
DEFAULT_CACHE = os.environ.get(
    "AB_P5_CACHE", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".ab_p5_cache")
)
LAMBDA_GRID = [0.0, 0.25, 0.5, 1.0, 2.0, 4.0]

MUSIQUE_ROWS_URL = (
    "https://datasets-server.huggingface.co/rows?dataset=dgslibisey%2FMuSiQue"
    "&config=default&split=validation&offset={off}&length=100"
)
# 2:1:1 hop mix like the pilot, doubled pool for n_train+n_eval=200 splits.
MUSIQUE_OFFSETS = (0, 100, 200, 300, 1300, 1400, 2100, 2200)

WIKI2_ROWS_URL = (
    "https://datasets-server.huggingface.co/rows?dataset=framolfese%2F2WikiMultihopQA"
    "&config=default&split=validation&offset={off}&length=100"
)
WIKI2_OFFSETS = (0, 100, 200, 300, 400)

PREREG_DELTA = 0.03  # prereg P5 threshold on hswm_answer_f1_minus_directllm


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
        except Exception as e:  # transient 500s / tunnel hiccups; bounded backoff, no storm
            last = e
            if attempt < retries:
                wait = (2, 10, 30)[min(attempt, 2)]
                print(f"[retry] {url.rsplit('/', 1)[-1]} failed ({e}); "
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
        tmp = self._path(kind, key) + f".tmp{os.getpid()}{threading.get_ident()}"
        with open(tmp, "w") as f:
            json.dump(value, f)
        os.replace(tmp, self._path(kind, key))


# ---------------------------------------------------------------- chat backends
_THINK_RE = re.compile(r"<think>.*?</think>", re.S)


class ChatBase:
    """Per-purpose call counting + disk cache. Cached hits still count as calls:
    budget parity is about *judgments consumed*, not wall time. Thread-safe."""

    def __init__(self, model: str, cache: DiskCache):
        self.model = model
        self.cache = cache
        self.calls: dict[str, int] = {}
        self.wall_s = 0.0
        self.empty_content = 0  # openai: content empty after strip (e.g. length cut)
        self._lock = threading.Lock()

    def _count(self, purpose: str) -> None:
        with self._lock:
            self.calls[purpose] = self.calls.get(purpose, 0) + 1

    def _add_wall(self, dt: float) -> None:
        with self._lock:
            self.wall_s += dt

    def chat(self, purpose: str, prompt: str, num_predict: int) -> str:
        raise NotImplementedError


class OllamaChat(ChatBase):
    def chat(self, purpose: str, prompt: str, num_predict: int) -> str:
        self._count(purpose)
        key = json.dumps([self.model, prompt, num_predict])
        hit = self.cache.get("chat", key)
        if hit is not None:
            return hit
        t0 = time.time()
        resp = _http_json(
            f"{OLLAMA}/api/chat",
            {"model": self.model, "stream": False,
             "messages": [{"role": "user", "content": prompt}],
             "options": {"temperature": 0, "num_predict": num_predict}},
        )
        self._add_wall(time.time() - t0)
        out = resp["message"]["content"]
        self.cache.put("chat", key, out)
        return out


class OpenAIChat(ChatBase):
    """OpenAI-compatible /chat/completions (vLLM). temperature 0. Reasoning models:
    vLLM routes thinking to message.reasoning; content may carry leading whitespace or
    stray <think> blocks -> stripped before use. Thinking disabled via
    chat_template_kwargs unless think=True."""

    def __init__(self, model: str, cache: DiskCache, base_url: str, think: bool):
        super().__init__(model, cache)
        self.base_url = base_url.rstrip("/")
        self.think = think

    def chat(self, purpose: str, prompt: str, num_predict: int) -> str:
        self._count(purpose)
        key = json.dumps(["openai", self.model, self.think, prompt, num_predict])
        hit = self.cache.get("chat", key)
        if hit is not None:
            return hit
        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": num_predict,
            "messages": [{"role": "user", "content": prompt}],
        }
        if not self.think:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        t0 = time.time()
        resp = _http_json(f"{self.base_url}/chat/completions", payload)
        self._add_wall(time.time() - t0)
        msg = resp["choices"][0]["message"]
        out = _THINK_RE.sub("", msg.get("content") or "").strip()
        if not out:
            with self._lock:
                self.empty_content += 1
        self.cache.put("chat", key, out)
        return out


class Embedder:
    def __init__(self, model: str, cache: DiskCache):
        self.model = model
        self.cache = cache
        self.split_fallbacks = 0  # deterministic per-text 500s (see pilot docstring)

    def _embed_one(self, text: str, depth: int = 0) -> list[float]:
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
            batch = missing[s: s + 8]
            try:
                embs = _http_json(f"{OLLAMA}/api/embed",
                                  {"model": self.model, "input": batch},
                                  retries=1)["embeddings"]
            except Exception:
                embs = [self._embed_one(t) for t in batch]
            for j, vec in enumerate(embs):
                i = missing_idx[s + j]
                out[i] = np.array(vec, dtype=np.float32)
                self.cache.put("emb", json.dumps([self.model, missing[s + j]]), vec)
        return np.stack(out)  # type: ignore[arg-type]


# ---------------------------------------------------------------- data
def load_pool_musique(cache_dir: str) -> list[dict]:
    """Normalized rows: id/hop/question/answer/answer_aliases/paragraphs."""
    path = os.path.join(cache_dir, "musique_val_pool_full.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    rows: list[dict] = []
    for off in MUSIQUE_OFFSETS:
        d = _http_json(MUSIQUE_ROWS_URL.format(off=off), timeout=120)
        for r in (x["row"] for x in d["rows"]):
            if not r.get("answerable"):
                continue
            rows.append({
                "id": r["id"],
                "hop": r["id"].split("_")[0],
                "question": r["question"],
                "answer": r["answer"],
                "answer_aliases": list(r.get("answer_aliases") or []),
                "paragraphs": [
                    {"idx": p["idx"], "title": p["title"],
                     "paragraph_text": p["paragraph_text"],
                     "is_supporting": bool(p["is_supporting"])}
                    for p in r["paragraphs"]
                ],
            })
    with open(path, "w") as f:
        json.dump(rows, f)
    return rows


def load_pool_2wiki(cache_dir: str) -> list[dict]:
    """framolfese/2WikiMultihopQA validation via HF datasets-server, normalized.
    context = {title: [...], sentences: [[...], ...]}; supporting_facts.title list."""
    path = os.path.join(cache_dir, "2wiki_val_pool.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    rows: list[dict] = []
    for off in WIKI2_OFFSETS:
        d = _http_json(WIKI2_ROWS_URL.format(off=off), timeout=120)
        for r in (x["row"] for x in d["rows"]):
            titles = r["context"]["title"]
            sents = r["context"]["sentences"]
            sup = set(r["supporting_facts"]["title"])
            paras = [
                {"idx": i, "title": t, "paragraph_text": " ".join(s),
                 "is_supporting": t in sup}
                for i, (t, s) in enumerate(zip(titles, sents))
            ]
            if not any(p["is_supporting"] for p in paras):
                continue  # unanswerable from given context; skip (counted via pool size)
            rows.append({
                "id": r["id"],
                "hop": r["type"],
                "question": r["question"],
                "answer": r["answer"],
                "answer_aliases": [],
                "paragraphs": paras,
            })
    with open(path, "w") as f:
        json.dump(rows, f)
    return rows


def load_pool(dataset: str, cache_dir: str) -> list[dict]:
    if dataset == "musique":
        return load_pool_musique(cache_dir)
    if dataset == "2wiki":
        return load_pool_2wiki(cache_dir)
    raise ValueError(dataset)


def split_pool(rows: list[dict], n_train: int, n_eval: int, seed: int):
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(rows))
    take = idx[: n_train + n_eval]
    train = [rows[i] for i in take[:n_train]]
    ev = [rows[i] for i in take[n_train:]]
    return train, ev


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


def set_prf(pred: set[int], gold: set[int]) -> tuple[float, float, float]:
    if not pred or not gold:
        return 0.0, 0.0, 0.0
    tp = len(pred & gold)
    p = tp / len(pred)
    r = tp / len(gold)
    f = 2 * p * r / (p + r) if p + r > 0 else 0.0
    return p, r, f


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
        self.P: np.ndarray | None = None
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
        _, _, vt = np.linalg.svd(Xc, full_matrices=False)
        k = min(self.proj_dim, vt.shape[0])  # rank clamp (tiny-run safety)
        self.P = vt[:k].T
        rng = np.random.default_rng(seed * 5381 + 3)
        self.M = 0.01 * rng.standard_normal((k, k))

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
        """labeled = [(row, positive_idx_list)] from the LLM judge (the only supervision
        HSWM buys with its budget). lambda selected on a val split of *labeled train
        queries* by nDCG vs those same LLM labels (grid incl 0 => cosine floor)."""
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
def hswm_offline_judgments(llm: ChatBase, rows: list[dict], budget: int,
                           parallel: int) -> tuple[list, dict]:
    target = rows[:budget]
    labeled: list = [None] * len(target)

    def _one(i: int) -> None:
        row = target[i]
        out = llm.chat("hswm_judgment",
                       JUDGE_PROMPT.format(q=row["question"], cands=cand_block(row, 260)),
                       num_predict=512)
        pos = parse_idx_list(out, {p["idx"] for p in row["paragraphs"]})
        labeled[i] = (row, pos[:5])

    with ThreadPoolExecutor(max_workers=max(1, parallel)) as ex:
        list(ex.map(_one, range(len(target))))
    parse_fail = sum(1 for _, pos in labeled if not pos)
    return labeled, {"judgment_calls": len(target), "parse_failures": parse_fail}


def judge_quality_diag(field: Field, labeled: list[tuple[dict, list[int]]]) -> dict:
    """Confound check from the pilot (judge weaker than cosine). Judge label set vs
    gold is_supporting, compared to cosine-top-3 pseudo-labels on the same rows."""
    jf, cf = [], []
    for row, pos in labeled:
        gold = {p["idx"] for p in row["paragraphs"] if p["is_supporting"]}
        if not gold:
            continue
        jf.append(set_prf(set(pos), gold)[2])
        cf.append(set_prf(set(field.order(row, lam=0.0)[:3]), gold)[2])
    return {
        "judge_label_f1_vs_gold": round(float(np.mean(jf)), 4) if jf else None,
        "cosine_top3_f1_vs_gold": round(float(np.mean(cf)), 4) if cf else None,
        "judge_beats_cosine_labels": bool(jf and cf and np.mean(jf) > np.mean(cf)),
        "n_rows": len(jf),
    }


def direct_rerank(llm: ChatBase, field: Field, row: dict,
                  calls_per_query: int) -> tuple[list[int], int]:
    """Listwise rerank with the eval query's own candidates. 2-stage if budget allows.
    Fallback fill = cosine order (reported)."""
    cos_order = field.order(row, lam=0.0)
    valid = {p["idx"] for p in row["paragraphs"]}
    top_n = min(10, len(valid))
    fails = 0

    out = llm.chat("direct_rerank",
                   RERANK_PROMPT.format(q=row["question"], cands=cand_block(row, 260),
                                        top_n=top_n),
                   num_predict=512)
    r1 = parse_idx_list(out, valid)
    if not r1:
        fails += 1
    order = r1 + [i for i in cos_order if i not in r1]

    if calls_per_query >= 2:
        top10 = order[:top_n]
        out2 = llm.chat("direct_rerank",
                        RERANK_PROMPT.format(q=row["question"],
                                             cands=cand_block(row, 500, only=top10),
                                             top_n=min(5, top_n)),
                        num_predict=512)
        r2 = parse_idx_list(out2, set(top10))
        if not r2:
            fails += 1
        order = r2 + [i for i in order if i not in r2]
    return order, fails


def read_answer(llm: ChatBase, purpose: str, row: dict, order: list[int], k: int) -> str:
    chosen = set(order[:k])
    ctx = "\n\n".join(
        f"{p['title']}: {_snip(p['paragraph_text'], 1200)}"
        for p in row["paragraphs"] if p["idx"] in chosen
    )
    return llm.chat(purpose, READER_PROMPT.format(ctx=ctx, q=row["question"]),
                    num_predict=256)


# ---------------------------------------------------------------- run
def cmd_run(args) -> None:
    if args.budget % args.n_eval != 0:
        print(f"NOTE: budget {args.budget} not divisible by n_eval {args.n_eval}; "
              f"direct arm uses floor() calls per query.", file=sys.stderr)
    calls_per_query = max(1, args.budget // args.n_eval)

    cache = DiskCache(args.cache_dir)
    if args.chat_backend == "openai":
        llm: ChatBase = OpenAIChat(args.chat_model, cache, args.openai_base_url, args.think)
    else:
        llm = OllamaChat(args.chat_model, cache)
    emb = Embedder(args.embed_model, cache)
    field = Field(emb, args.proj_dim)

    print(f"[data] loading {args.dataset} pool ...", flush=True)
    pool = load_pool(args.dataset, args.cache_dir)
    if len(pool) < args.n_train + args.n_eval:
        print(f"BLOCKER: pool={len(pool)} < n_train+n_eval={args.n_train + args.n_eval}",
              file=sys.stderr)
        sys.exit(2)
    train_rows, eval_rows = split_pool(pool, args.n_train, args.n_eval, args.seed)
    print(f"[data] pool={len(pool)} train={len(train_rows)} eval={len(eval_rows)} "
          f"hops(eval)={sorted({r['hop'] for r in eval_rows})}", flush=True)

    t_start = time.time()
    print("[embed] paragraph+query embeddings (shared substrate) ...", flush=True)
    field.fit_pca(train_rows, args.seed)
    for i, r in enumerate(eval_rows):  # warm the cache sequentially (thread-safe reads later)
        field.para_embs(r), field.query_emb(r)
        if (i + 1) % 25 == 0:
            print(f"[embed] eval warm {i+1}/{len(eval_rows)}", flush=True)

    # --- HSWM arm: offline budget -> labels -> train field; eval = 0 ranking calls
    print(f"[hswm] spending budget B={args.budget} offline on train judgments ...", flush=True)
    labeled, jinfo = hswm_offline_judgments(llm, train_rows, args.budget, args.parallel)
    jq = judge_quality_diag(field, labeled)
    print(f"[hswm] judge quality vs gold: {jq}", flush=True)
    train_diag = field.train_additive(labeled, args.seed)
    print(f"[hswm] trained: {train_diag}", flush=True)

    # --- rank + read on eval queries (row-parallel; per-row work is independent)
    per_query: list = [None] * len(eval_rows)
    fail_lock = threading.Lock()
    direct_fails = [0]
    done = [0]

    def _eval_one(qi: int) -> None:
        row = eval_rows[qi]
        gold_sup = {p["idx"] for p in row["paragraphs"] if p["is_supporting"]}
        golds = [row["answer"]] + list(row.get("answer_aliases") or [])

        orders = {
            "cosine": field.order(row, lam=0.0),
            "hswm": field.order(row),  # 0 LLM ranking calls at eval time
        }
        d_order, d_fail = direct_rerank(llm, field, row, calls_per_query)
        orders["direct"] = d_order
        with fail_lock:
            direct_fails[0] += d_fail

        rec = {"id": row["id"], "hop": row["hop"], "question": row["question"],
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
        per_query[qi] = rec
        with fail_lock:
            done[0] += 1
            n = done[0]
        if n % 5 == 0 or n == len(eval_rows):
            print(f"[eval {n}/{len(eval_rows)}] " +
                  " ".join(f"{a}:em={rec[a]['em']:.0f}" for a in orders), flush=True)

    with ThreadPoolExecutor(max_workers=max(1, args.parallel)) as ex:
        list(ex.map(_eval_one, range(len(eval_rows))))

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
        "label": "PREREG_CANDIDATE",
        "note": "full P5 run, single dataset+seed; combine across runs for the prereg "
                "judgment; parent verifies before any LakatoTree submit_result",
        "tree": "LakatosTree_HSWM_20260719",
        "prereg_ref": "prediction-p5-cognitive-uplift-vs-directllm",
        "dataset": args.dataset,
        "config": {k: getattr(args, k) for k in
                   ("n_train", "n_eval", "budget", "top_k", "proj_dim", "seed",
                    "chat_backend", "chat_model", "embed_model", "think", "parallel")},
        "data": {"pool_size": len(pool),
                 "eval_hops": {h: sum(1 for r in eval_rows if r["hop"] == h)
                               for h in sorted({r["hop"] for r in eval_rows})}},
        "llm_call_parity": {
            "hswm_judgment_calls": llm.calls.get("hswm_judgment", 0),
            "direct_rerank_calls": llm.calls.get("direct_rerank", 0),
            "reader_calls": {a: llm.calls.get(f"reader_{a}", 0) for a in arms},
            "parity_ok": llm.calls.get("hswm_judgment", 0) == llm.calls.get("direct_rerank", 0),
        },
        "hswm_training": {**jinfo, **train_diag},
        "judge_quality": jq,
        "direct_parse_fallbacks": direct_fails[0],
        "llm_empty_content": llm.empty_content,
        "embed_split_fallbacks": emb.split_fallbacks,
        "aggregate": agg,
        "delta": {
            "em_hswm_minus_direct": round(agg["hswm"]["em"] - agg["direct"]["em"], 4),
            "f1_hswm_minus_direct": round(agg["hswm"]["f1"] - agg["direct"]["f1"], 4),
            "ndcg_hswm_minus_direct": round(agg["hswm"]["ndcg10_vs_gold"]
                                            - agg["direct"]["ndcg10_vs_gold"], 4),
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
                      ("llm_call_parity", "hswm_training", "judge_quality",
                       "aggregate", "delta")},
                     indent=1, ensure_ascii=False))
    print(f"[done] results -> {args.out}", flush=True)


# ---------------------------------------------------------------- combine
def cmd_combine(args) -> None:
    runs = []
    for p in args.runs:
        with open(p) as f:
            runs.append((os.path.basename(p), json.load(f)))

    summary = []
    for name, r in runs:
        summary.append({
            "run": name,
            "dataset": r["dataset"],
            "seed": r["config"]["seed"],
            "n_eval": r["config"]["n_eval"],
            "aggregate": r["aggregate"],
            "delta_f1_hswm_minus_direct": r["delta"]["f1_hswm_minus_direct"],
            "delta_em_hswm_minus_direct": r["delta"]["em_hswm_minus_direct"],
            "delta_ndcg_hswm_minus_direct": r["delta"].get(
                "ndcg_hswm_minus_direct",
                round(r["aggregate"]["hswm"]["ndcg10_vs_gold"]
                      - r["aggregate"]["direct"]["ndcg10_vs_gold"], 4)),
            "parity_ok": r["llm_call_parity"]["parity_ok"],
            "judge_quality": r.get("judge_quality"),
        })

    deltas = [s["delta_f1_hswm_minus_direct"] for s in summary]
    datasets = sorted({s["dataset"] for s in summary})
    worst = min(deltas)
    per_dataset_ok = {
        ds: all(s["delta_f1_hswm_minus_direct"] >= PREREG_DELTA
                for s in summary if s["dataset"] == ds)
        for ds in datasets
    }
    cognitive = all(per_dataset_ok.values()) and worst >= PREREG_DELTA
    all_null = all(abs(d) < PREREG_DELTA for d in deltas)
    # Goodhart co-primary: ranking gain without answer gain refutes the cognitive claim
    goodhart = any(
        s["delta_ndcg_hswm_minus_direct"] > 0 and abs(s["delta_f1_hswm_minus_direct"]) < PREREG_DELTA
        for s in summary
    )
    if cognitive:
        assessment = "SUPPORTED_cognitive-uplift"
    elif all_null:
        assessment = "operational-only (kill criterion: all |delta| < 0.03)"
    elif all(d <= -PREREG_DELTA for d in deltas):
        assessment = "REFUTED (direct-LLM beats HSWM everywhere)"
    else:
        assessment = "INCONCLUSIVE (mixed deltas across runs)"

    out = {
        "label": "PREREG_CANDIDATE",
        "tree": "LakatosTree_HSWM_20260719",
        "prereg_ref": "prediction-p5-cognitive-uplift-vs-directllm",
        "prereg_criteria": {
            "metric": "hswm_answer_f1_minus_directllm",
            "cognitive": f"delta >= +{PREREG_DELTA} replicated on every dataset AND worst seed",
            "kill": f"|delta| < {PREREG_DELTA} => operational-only",
            "co_primary": "nDCG up while F1 flat => Goodhart REFUTED",
            "ablation": "cosine arm = j-removal ablation (built into 3-arm design)",
        },
        "runs": summary,
        "worst_seed_delta_f1": worst,
        "per_dataset_replication": per_dataset_ok,
        "goodhart_flag_ndcg_up_f1_flat": goodhart,
        "preliminary_assessment": assessment,
        "per_query_by_run": {name: r["per_query"] for name, r in runs},
    }
    with open(args.out, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(json.dumps({k: out[k] for k in
                      ("runs", "worst_seed_delta_f1", "per_dataset_replication",
                       "goodhart_flag_ndcg_up_f1_flat", "preliminary_assessment")},
                     indent=1, ensure_ascii=False, default=str))
    print(f"[done] combined -> {args.out}", flush=True)


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    rp = sub.add_parser("run", help="one dataset x seed full run")
    rp.add_argument("--dataset", choices=("musique", "2wiki"), required=True)
    rp.add_argument("--n-train", dest="n_train", type=int, default=100)
    rp.add_argument("--n-eval", dest="n_eval", type=int, default=100)
    rp.add_argument("--budget", type=int, default=100,
                    help="LLM judgment/ranking calls per arm (HSWM offline == direct online)")
    rp.add_argument("--top-k", dest="top_k", type=int, default=3)
    rp.add_argument("--proj-dim", dest="proj_dim", type=int, default=96)
    rp.add_argument("--seed", type=int, default=7)
    rp.add_argument("--chat-backend", dest="chat_backend",
                    choices=("ollama", "openai"), default="openai")
    rp.add_argument("--chat-model", dest="chat_model", default="qwen3.6-27b")
    rp.add_argument("--openai-base-url", dest="openai_base_url",
                    default="http://127.0.0.1:18001/v1")
    rp.add_argument("--think", action="store_true",
                    help="leave reasoning enabled (default: chat_template_kwargs "
                         "enable_thinking=false for deterministic parse + throughput)")
    rp.add_argument("--embed-model", dest="embed_model", default="bge-m3")
    rp.add_argument("--parallel", type=int, default=4)
    rp.add_argument("--cache-dir", dest="cache_dir", default=DEFAULT_CACHE)
    rp.add_argument("--out", required=True)
    rp.set_defaults(func=cmd_run)

    cp = sub.add_parser("combine", help="merge run JSONs + mechanical prereg assessment")
    cp.add_argument("--runs", nargs="+", required=True)
    cp.add_argument("--out", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "ab_p5_full_results.json"))
    cp.set_defaults(func=cmd_combine)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
