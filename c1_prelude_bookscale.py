"""C-1 PRELUDE book-scale — HSWM vs dense vs clique-reduction ablation.

Prereg: prom_search_hswm/evidence/PREREG_c1_prelude_bookscale_20260723.json
(first BOOK-SCALE measurement; current state SUBSTRATE_VALID, not BOOK_SCALE_PROVEN).

Arms (IDENTICAL judge prompt + identical chunking + identical cosine seed):
  dense  — bge-m3 cosine top-20, no structural walk.
  hswm   — repo traversal.py star-expansion walk over the chunk-term hypergraph
           (Hypergraph/WeightField/traverse reused verbatim), mu=0.4, K=2, gamma=0.5.
  clique — same hypergraph reduced to pairwise chunk-chunk clique graph
           (weight = sum idf of shared terms), same walk shape + combine.

Data: PRELUDE public split (262 instances, 4 public-domain books), texts in
data/prelude/ (sha256 locked in prereg). Judge: qwen3.6-27b on dgx vLLM
(ssh forward 127.0.0.1:18000), temp 0, thinking off. Embeddings: bge-m3 on
dgx ollama (127.0.0.1:11434). LLM/embedding responses are disk-cached
(data/prelude/cache/) so reruns are deterministic and free.

Usage:  .venv/bin/python c1_prelude_bookscale.py [--limit N] [--parallel 8] [--judge/--no-judge]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import string
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from hypergraph import Hypergraph          # repo
from weight_field import WeightField       # repo
import traversal                           # repo (build_index, traverse, _softmax_topm)

# ---------------- prereg constants (LOCKED — see PREREG json) ----------------
BOOKS = {
    "The Count of Monte Cristo": {"file": "montecristo.txt", "lang": "en",
        "sha256": "64f8d5cfa51fcecb904abf7312d395d512a71817e7359b91288beb50517c3836"},
    "In Search of the Castaways": {"file": "castaways.txt", "lang": "en",
        "sha256": "df5da6648b41f3e2498e6b048a8aa051932d73b70a9d76596177e5a9eec3e8c1"},
    "封神演义": {"file": "fengshen.txt", "lang": "zh",
        "sha256": "182c62503fcf9912a899078198b52f4e7545d352d1ff17b10955e241e6424c93"},
    "三国演义": {"file": "sanguo.txt", "lang": "zh",
        "sha256": "6299a0d16533c23cde92462c92aab8720e109dbb48425c3642eb484ffdbd3e07"},
}
CHUNK_WORDS_EN = 500
CHUNK_CHARS_ZH = 750
TOP_TERMS = 8
MIN_DF = 3
TOP_K = 20                # judge context: dgx vLLM max_model_len = 24576
MU = 0.4
K_HOPS = 2
GAMMA = 0.5
KAPPA = 1
BOOT = 10000
SEED = 20260723

DATA = os.path.join(HERE, "data", "prelude")
CACHE_DIR = os.path.join(DATA, "cache")
OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
JUDGE_URL = os.environ.get("JUDGE_URL", "http://127.0.0.1:18000/v1")
JUDGE_MODEL = "qwen3.6-27b"
EMBED_MODEL = "bge-m3"

_STOP = set(
    "a an the of to in on at for and or but is are was were be been being as by with "
    "from into that this these those it its he she they them his her their who whom "
    "which what when where why how do does did has have had not no s t o m re ve ll d "
    "than then also whose about over under between during after before said says one "
    "two would could should will shall may might must upon out up down off again once".split()
)


# ---------------- small utils ----------------
def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _post(url: str, payload: dict, timeout: int = 300) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------- cached embedding (bge-m3 via ollama) ----------------
class Embedder:
    def __init__(self):
        os.makedirs(CACHE_DIR, exist_ok=True)
        self.calls = 0

    def _cache_path(self, text: str) -> str:
        return os.path.join(CACHE_DIR, f"emb_{sha256_text(EMBED_MODEL + '|' + text)}.npy")

    def embed_many(self, texts: list[str], parallel: int = 16) -> np.ndarray:
        out: list[np.ndarray | None] = [None] * len(texts)
        todo = []
        for i, t in enumerate(texts):
            p = self._cache_path(t)
            if os.path.exists(p):
                out[i] = np.load(p)
            else:
                todo.append(i)

        def work(i: int):
            r = _post(f"{OLLAMA}/api/embeddings", {"model": EMBED_MODEL, "prompt": texts[i]})
            v = np.asarray(r["embedding"], dtype=np.float64)
            v = v / max(np.linalg.norm(v), 1e-12)
            np.save(self._cache_path(texts[i]), v)
            return i, v

        if todo:
            with ThreadPoolExecutor(max_workers=parallel) as ex:
                for i, v in ex.map(work, todo):
                    out[i] = v
            self.calls += len(todo)
        return np.stack(out)  # type: ignore[arg-type]


# ---------------- cached judge (qwen3.6-27b via vLLM) ----------------
class Judge:
    def __init__(self):
        os.makedirs(CACHE_DIR, exist_ok=True)
        self.calls = 0
        self.prompt_tokens = 0

    def _cache_path(self, prompt: str) -> str:
        return os.path.join(CACHE_DIR, f"judge_{sha256_text(JUDGE_MODEL + '|' + prompt)}.json")

    def ask(self, prompt: str) -> tuple[str, dict]:
        p = self._cache_path(prompt)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            return d["text"], {"cached": True, "prompt_tokens": d.get("prompt_tokens", 0)}
        payload = {
            "model": JUDGE_MODEL, "temperature": 0.0, "max_tokens": 16,
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [{"role": "user", "content": prompt}],
        }
        r = _post(f"{JUDGE_URL}/chat/completions", payload)
        text = r["choices"][0]["message"]["content"]
        ptok = r.get("usage", {}).get("prompt_tokens", 0)
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"text": text, "prompt_tokens": ptok}, f, ensure_ascii=False)
        self.calls += 1
        self.prompt_tokens += ptok
        return text, {"cached": False, "prompt_tokens": ptok}


# ---------------- book loading + chunking ----------------
def load_book_text(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        t = f.read()
    # strip Gutenberg boilerplate if present
    m = re.search(r"\*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG EBOOK[^\n]*\n", t)
    if m:
        t = t[m.end():]
    m = re.search(r"\*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG EBOOK", t)
    if m:
        t = t[:m.start()]
    return t.strip()


def chunk_book(text: str, lang: str) -> list[str]:
    if lang == "en":
        words = text.split()
        return [" ".join(words[i:i + CHUNK_WORDS_EN])
                for i in range(0, len(words), CHUNK_WORDS_EN)]
    flat = re.sub(r"\s+", "", text)
    return [flat[i:i + CHUNK_CHARS_ZH] for i in range(0, len(flat), CHUNK_CHARS_ZH)]


# ---------------- salient terms ----------------
_WORD_RE = re.compile(r"[a-z][a-z'\-]{2,}")
_ZH_PUNCT = "，。！？；：、“”‘’（）《》〈〉【】…—·0123456789abcdefghijklmnopqrstuvwxyz"


def zh_terms(text: str) -> list[str]:
    """jieba posseg nouns/names len>=2; fallback char bigrams if jieba missing."""
    try:
        import jieba.posseg as pseg
        return [w for w, flag in pseg.cut(text)
                if len(w) >= 2 and flag[:1] in ("n",) and w.strip(_ZH_PUNCT) == w]
    except Exception:
        return [text[i:i + 2] for i in range(len(text) - 1)
                if text[i] not in _ZH_PUNCT and text[i + 1] not in _ZH_PUNCT]


def en_terms(text: str) -> list[str]:
    return [w for w in _WORD_RE.findall(text.lower()) if w not in _STOP]


def build_term_index(chunks: list[str], lang: str):
    """df-filtered term vocab, idf, per-chunk top-TOP_TERMS tf.idf terms."""
    tf = [__import__("collections").Counter(
        zh_terms(c) if lang == "zh" else en_terms(c)) for c in chunks]
    df: dict[str, int] = {}
    for c in tf:
        for t in c:
            df[t] = df.get(t, 0) + 1
    M = len(chunks)
    vocab = {t for t, d in df.items() if MIN_DF <= d <= 0.5 * M}
    idf = {t: math.log((1 + M) / (1 + df[t])) + 1.0 for t in vocab}
    members: list[list[str]] = []
    for c in tf:
        scored = sorted(((t, n * idf[t]) for t, n in c.items() if t in vocab),
                        key=lambda x: -x[1])
        members.append([t for t, _ in scored[:TOP_TERMS]])
    return vocab, idf, members


# ---------------- HSWM world (repo Hypergraph) ----------------
def build_hswm(chunks: list[str], chunk_emb: np.ndarray, members: list[list[str]]):
    terms = sorted({t for m in members for t in m})
    t2i = {t: i for i, t in enumerate(terms)}
    node_emb = np.zeros((len(terms), 2))  # nodes carry no semantics here; field reads edges
    edges = [np.array([t2i[t] for t in m], dtype=np.int64) if m
             else np.array([0], dtype=np.int64) for m in members]
    hg = Hypergraph(node_emb=node_emb, members=edges,
                    edge_freq=np.ones(len(chunks)), edge_recency=np.ones(len(chunks)))
    field = WeightField(hg, M=None, lam=0.0, target_emb=chunk_emb)
    return hg, field


# ---------------- clique reduction walk ----------------
def clique_walk(w_dense: np.ndarray, members: list[list[str]], idf: dict[str, float],
                k: int) -> np.ndarray:
    """Pairwise clique expansion of the SAME hypergraph; same walk shape as
    traversal.traverse (seed softmax -> K damped hops -> support-restricted z combine)."""
    M = len(members)
    inv: dict[str, list[int]] = {}
    for i, m in enumerate(members):
        for t in m:
            inv.setdefault(t, []).append(i)
    # sparse pairwise weights W[i][j] = sum idf(shared terms)
    Ws: list[dict[int, float]] = [dict() for _ in range(M)]
    for t, chunks_of_t in inv.items():
        w = idf[t]
        for i in chunks_of_t:
            for j in chunks_of_t:
                if i != j:
                    Ws[i][j] = Ws[i].get(j, 0.0) + w
    s = traversal._softmax_topm(w_dense, traversal.SEED_M)
    a = s.copy()
    for _ in range(K_HOPS):
        at = np.zeros(M)
        for i, nbrs in enumerate(Ws):
            if a[i] <= 0 or not nbrs:
                continue
            tot = sum(nbrs.values())
            for j, w in nbrs.items():
                at[j] += a[i] * w / tot
        at = at / max(at.sum(), 1e-12)
        a = (1.0 - GAMMA) * s + GAMMA * at
    # support-restricted z-norm combine (identical formula to traversal.py)
    S = np.flatnonzero((a != 0) | (s != 0))
    d = a[S] - s[S]
    R = np.zeros_like(w_dense)
    std = float(d.std(ddof=0))
    if std > 0:
        R[S] = (d > 0) * np.maximum((d - d.mean()) / std, 0.0)
    w_final = w_dense + MU * R
    order = np.argsort(-w_final, kind="stable")[:k]
    return order


# ---------------- judge prompt (FIXED across arms) ----------------
JUDGE_TEMPLATE = """You are judging whether a proposed PREQUEL (a character's backstory) is consistent with the canonical narrative of the original book.

Book: {book}
Character: {char}
PREQUEL: {prequel}

Retrieved excerpts from the book (evidence, possibly scattered across the narrative):
---
{evidence}
---

Judge primarily from the excerpts. Answer "contradict" if the prequel conflicts with facts, timeline, character traits, relationships or the spirit of the canonical narrative. Answer "consistent" if it is compatible, even if it adds non-conflicting new details.
Answer with exactly one word: consistent or contradict."""


def parse_verdict(text: str) -> str:
    t = text.strip().lower()
    if "contradict" in t:
        return "contradict"
    if "consistent" in t:
        return "consistent"
    return "unparsed"


# ---------------- F1 + bootstrap ----------------
def macro_f1(golds: list[str], preds: list[str]) -> dict:
    per = {}
    for cls in ("consistent", "contradict"):
        tp = sum(1 for g, p in zip(golds, preds) if g == cls and p == cls)
        fp = sum(1 for g, p in zip(golds, preds) if g != cls and p == cls)
        fn = sum(1 for g, p in zip(golds, preds) if g == cls and p != cls)
        f1 = 2 * tp / max(2 * tp + fp + fn, 1e-12)
        per[cls] = {"f1": f1, "tp": tp, "fp": fp, "fn": fn}
    return {"macro_f1": (per["consistent"]["f1"] + per["contradict"]["f1"]) / 2,
            "per_class": per}


def boot_ci(golds: list[str], pa: list[str], pb: list[str],
            n_boot: int = BOOT, seed: int = SEED) -> dict:
    """Paired bootstrap CI of macroF1(a) - macroF1(b)."""
    rng = np.random.default_rng(seed)
    n = len(golds)
    g = np.array(golds)
    a = np.array(pa)
    b = np.array(pb)
    diffs = np.empty(n_boot)
    for r in range(n_boot):
        idx = rng.integers(0, n, n)
        diffs[r] = (macro_f1(list(g[idx]), list(a[idx]))["macro_f1"]
                    - macro_f1(list(g[idx]), list(b[idx]))["macro_f1"])
    return {"mean_diff": float(diffs.mean()),
            "ci95": [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))],
            "p_a_le_b": float((diffs <= 0).mean())}


# ---------------- main ----------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="cap instances (pilot)")
    ap.add_argument("--books", default="", help="comma-separated subset of book names")
    ap.add_argument("--parallel", type=int, default=8)
    ap.add_argument("--no-judge", action="store_true", help="retrieval only, no LLM calls")
    ap.add_argument("--out", default=os.path.join(HERE, "EVIDENCE_C1_PRELUDE_BOOKSCALE_2026-07-23.json"))
    args = ap.parse_args()

    import pandas as pd
    t0 = time.time()
    df = pd.read_parquet(os.path.join(DATA, "public.parquet"))
    if args.books:
        keep = set(args.books.split(","))
        df = df[df.book_name.isin(keep)]
    df = df.reset_index(drop=True)
    if args.limit:
        # stratified pilot: round-robin across books keeps book mix
        df = (df.groupby("book_name", group_keys=False)
                .apply(lambda g: g.head(math.ceil(args.limit / 4)))
                .reset_index(drop=True))
        df = df.head(args.limit).reset_index(drop=True)
    print(f"[c1] instances: {len(df)} over {df.book_name.nunique()} books", flush=True)

    # ---- ingest books ----
    emb = Embedder()
    worlds: dict[str, dict] = {}
    for book, spec in BOOKS.items():
        if book not in set(df.book_name):
            continue
        path = os.path.join(DATA, spec["file"])
        actual = sha256_file(path)
        if actual != spec["sha256"]:
            raise SystemExit(f"sha mismatch {book}: {actual} != prereg {spec['sha256']}")
        tb = time.time()
        text = load_book_text(path)
        chunks = chunk_book(text, spec["lang"])
        chunk_emb = emb.embed_many(chunks, parallel=16)
        vocab, idf, members = build_term_index(chunks, spec["lang"])
        hg, field = build_hswm(chunks, chunk_emb, members)
        idx = traversal.build_index(hg)
        worlds[book] = {"chunks": chunks, "emb": chunk_emb, "field": field,
                        "idx": idx, "members": members, "idf": idf,
                        "n_vocab": len(vocab),
                        "ingest_s": round(time.time() - tb, 1)}
        print(f"[ingest] {book}: {len(chunks)} chunks, {len(vocab)} terms, "
              f"{worlds[book]['ingest_s']}s", flush=True)

    # ---- queries ----
    q_emb = emb.embed_many(list(df["content"]), parallel=16)
    golds = list(df["label"])

    judge = Judge()
    preds: dict[str, list[str]] = {a: ["unparsed"] * len(df) for a in ("dense", "hswm", "clique")}
    orders: dict[str, list] = {a: [None] * len(df) for a in ("dense", "hswm", "clique")}
    abstain = {"hswm": 0}

    def work(i: int):
        row = df.iloc[i]
        w = worlds[row["book_name"]]
        W = w["field"].value(q_emb[i])          # cosine seed — shared by all arms
        o_dense = np.argsort(-W, kind="stable")[:TOP_K]
        o_hswm, _, rc = traversal.traverse(
            w["field"], q_emb[i], k=TOP_K, mu=MU, K=K_HOPS, kappa=KAPPA,
            gamma=GAMMA, index=w["idx"])
        if rc.abstained:
            abstain["hswm"] += 1
        o_clique = clique_walk(W, w["members"], w["idf"], TOP_K)
        out = {"dense": list(map(int, o_dense)), "hswm": list(map(int, o_hswm)),
               "clique": list(map(int, o_clique))}
        if args.no_judge:
            return i, out, {}
        verdicts = {}
        for arm, order in out.items():
            ev = "\n...\n".join(w["chunks"][j] for j in order)
            prompt = JUDGE_TEMPLATE.format(
                book=row["book_name"], char=row["char"],
                prequel=row["content"], evidence=ev)
            text, meta = judge.ask(prompt)
            verdicts[arm] = parse_verdict(text)
        return i, out, verdicts

    with ThreadPoolExecutor(max_workers=args.parallel) as ex:
        for i, out, verdicts in ex.map(work, range(len(df))):
            for arm in out:
                orders[arm].append(None)  # placeholder, filled below
            for arm in ("dense", "hswm", "clique"):
                if len(orders[arm]) <= i:
                    orders[arm].extend([None] * (i + 1 - len(orders[arm])))
                orders[arm][i] = out[arm]
                if verdicts:
                    preds[arm][i] = verdicts[arm]
            if (i + 1) % 25 == 0:
                print(f"[run] {i + 1}/{len(df)} judged", flush=True)

    # ---- metrics ----
    result = {
        "label": "C1_PRELUDE_BOOKSCALE",
        "prereg": "prom_search_hswm/evidence/PREREG_c1_prelude_bookscale_20260723.json",
        "n_instances": len(df),
        "pilot": bool(args.limit),
        "no_judge": bool(args.no_judge),
        "books": {b: {"chunks": len(w["chunks"]), "terms": w["n_vocab"],
                      "ingest_s": w["ingest_s"],
                      "n_instances": int((df.book_name == b).sum())}
                  for b, w in worlds.items()},
        "cost": {"embedding_calls": emb.calls, "judge_calls": judge.calls,
                 "judge_prompt_tokens": judge.prompt_tokens},
        "hswm_abstain_count": abstain["hswm"],
    }
    if not args.no_judge:
        f1 = {arm: macro_f1(golds, preds[arm]) for arm in preds}
        unparsed = {arm: preds[arm].count("unparsed") for arm in preds}
        deltas = {
            "hswm_minus_dense": boot_ci(golds, preds["hswm"], preds["dense"]),
            "hswm_minus_clique": boot_ci(golds, preds["hswm"], preds["clique"]),
        }
        per_book = {}
        for b in sorted(set(df.book_name)):
            idx = [i for i in range(len(df)) if df.iloc[i]["book_name"] == b]
            per_book[b] = {arm: round(macro_f1(
                [golds[i] for i in idx], [preds[arm][i] for i in idx])["macro_f1"], 4)
                for arm in preds}
        kill = (deltas["hswm_minus_dense"]["mean_diff"] < 0.02
                or deltas["hswm_minus_clique"]["mean_diff"] <= 0.0)
        result.update({
            "macro_f1": {a: round(f1[a]["macro_f1"], 4) for a in f1},
            "per_class": {a: f1[a]["per_class"] for a in f1},
            "unparsed": unparsed,
            "per_book_macro_f1": per_book,
            "deltas_pp": {k: {"mean": round(100 * v["mean_diff"], 2),
                              "ci95": [round(100 * x, 2) for x in v["ci95"]],
                              "p_le_0": round(v["p_a_le_b"], 4)}
                          for k, v in deltas.items()},
            "prereg_verdict": {
                "hswm_minus_dense_ge_3pp": deltas["hswm_minus_dense"]["mean_diff"] >= 0.03,
                "hswm_gt_clique": deltas["hswm_minus_clique"]["mean_diff"] > 0.0,
                "kill_condition_hit": kill,
                "low_power_note": "n=262 -> CI ~+/-6pt; if CI straddles threshold, verdict is low_power",
            },
        })
    result["wall_clock_s"] = round(time.time() - t0, 1)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, ensure_ascii=False)
    print(json.dumps({k: v for k, v in result.items() if k in
                      ("macro_f1", "deltas_pp", "prereg_verdict", "cost", "wall_clock_s")},
                     indent=1, ensure_ascii=False), flush=True)
    print(f"[done] -> {args.out}", flush=True)


if __name__ == "__main__":
    main()
