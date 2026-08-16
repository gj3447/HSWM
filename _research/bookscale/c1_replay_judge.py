"""C1 PRELUDE replay judge — 서버 재현명령('python <script> <result_path>')용 순수 numpy 재채점기.

두 모드:
  (기본, 컨테이너) data/prelude/c1_replay_records.json 만 읽어 macro-F1·paired bootstrap 델타를
    재계산하고 stdout 에 `metric=<hswm_minus_dense pp>` 한 줄만 출력 (부가정보는 stderr).
    pandas/ollama/vLLM/네트워크 없음 — numpy 만 있으면 된다.
  (--collect, Mac 전용) 캐시된 임베딩(.npy)과 judge 응답(.json)만으로 파이프라인을 오프라인 재구성해
    records 아티팩트를 만든다. 캐시 미스 = 즉시 실패(네트워크 0 보증).

판정 장부 수리 패턴(R3와 동일): producer(c1_prelude_bookscale.py, dgx 임베딩/judge 캐시 적재)
→ 아티팩트(records json, sync 루트 안) → judge(본 파일, 컨테이너 재실행 가능).

현재 진입점: python _research/bookscale/c1_replay_judge.py [--collect]
"""
from __future__ import annotations

import json
import math
import os
import sys
from hashlib import sha256
from pathlib import Path

import numpy as np


def _discover_repository_root(anchor: str | Path = __file__) -> Path:
    """Find the checkout root that owns the replay records and source tree."""
    resolved = Path(anchor).resolve(strict=True)
    start = resolved.parent if resolved.is_file() else resolved
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise RuntimeError(f"cannot locate HSWM repository root from {resolved}")


REPO_ROOT = _discover_repository_root()
for _import_root in (REPO_ROOT, REPO_ROOT / "src"):
    if str(_import_root) not in sys.path:
        sys.path.insert(0, str(_import_root))

RECORDS = REPO_ROOT / "data" / "prelude" / "c1_replay_records.json"

BOOT = 10000
SEED = 20260723


# ---------------- c1_prelude_bookscale.py 와 동일 공식 (복사, 임포트 아님 — 컨테이너 자급) ----------------
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


def boot_ci(golds, pa, pb, n_boot=BOOT, seed=SEED):
    rng = np.random.default_rng(seed)
    n = len(golds)
    g, a, b = np.array(golds), np.array(pa), np.array(pb)
    diffs = np.empty(n_boot)
    for r in range(n_boot):
        idx = rng.integers(0, n, n)
        diffs[r] = (macro_f1(list(g[idx]), list(a[idx]))["macro_f1"]
                    - macro_f1(list(g[idx]), list(b[idx]))["macro_f1"])
    return {"mean_diff": float(diffs.mean()),
            "ci95": [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))],
            "p_a_le_b": float((diffs <= 0).mean())}


# ---------------- score 모드 (컨테이너) ----------------
def score() -> int:
    rec = json.loads(RECORDS.read_text(encoding="utf-8"))
    golds = rec["golds"]
    preds = rec["preds"]
    f1 = {arm: macro_f1(golds, preds[arm])["macro_f1"] for arm in preds}
    d_hd = boot_ci(golds, preds["hswm"], preds["dense"])
    d_hc = boot_ci(golds, preds["hswm"], preds["clique"])
    primary = round(100 * d_hd["mean_diff"], 6)
    novel = round(100 * d_hc["mean_diff"], 6)
    print(f"metric={primary}", flush=True)  # stdout 순수 — 서버 metric 파서 계약
    print(json.dumps({
        "primary_hswm_minus_dense_pp": primary,
        "novel_hswm_minus_clique_pp": novel,
        "macro_f1": {a: round(v, 6) for a, v in f1.items()},
        "ci95_hswm_minus_dense_pp": [round(100 * x, 4) for x in d_hd["ci95"]],
        "p_le_0": round(d_hd["p_a_le_b"], 4),
        "kill_hit": bool(d_hd["mean_diff"] < 0.02 or d_hc["mean_diff"] <= 0.0),
    }, ensure_ascii=False), file=sys.stderr)
    return 0


# ---------------- collect 모드 (Mac, 캐시 전용 오프라인) ----------------
def _collect_dependencies():
    from _research.bookscale import c1_prelude_bookscale as c1
    import traversal

    return c1, traversal


def collect() -> int:
    import pandas as pd

    c1, traversal = _collect_dependencies()

    def emb_cache_path(text: str) -> Path:
        return Path(c1.CACHE_DIR) / f"emb_{sha256((c1.EMBED_MODEL + '|' + text).encode('utf-8')).hexdigest()}.npy"

    def judge_cache_path(prompt: str) -> Path:
        return Path(c1.CACHE_DIR) / f"judge_{sha256((c1.JUDGE_MODEL + '|' + prompt).encode('utf-8')).hexdigest()}.json"

    def embed_cached(texts: list[str]) -> np.ndarray:
        vecs = []
        for t in texts:
            p = emb_cache_path(t)
            if not p.exists():
                raise SystemExit(f"embedding cache miss (네트워크 0 계약 위반 방지): {t[:60]!r}")
            vecs.append(np.load(p))
        return np.stack(vecs)

    df = pd.read_parquet(os.path.join(c1.DATA, "public.parquet")).reset_index(drop=True)

    worlds: dict[str, dict] = {}
    for book, spec in c1.BOOKS.items():
        path = os.path.join(c1.DATA, spec["file"])
        if c1.sha256_file(path) != spec["sha256"]:
            raise SystemExit(f"sha mismatch: {book}")
        text = c1.load_book_text(path)
        chunks = c1.chunk_book(text, spec["lang"])
        chunk_emb = embed_cached(chunks)
        vocab, idf, members = c1.build_term_index(chunks, spec["lang"])
        hg, field = c1.build_hswm(chunks, chunk_emb, members)
        idx = traversal.build_index(hg)
        worlds[book] = {"chunks": chunks, "field": field, "idx": idx,
                        "members": members, "idf": idf}

    q_vecs = embed_cached(list(df["content"]))
    golds = list(df["label"])
    preds: dict[str, list[str]] = {a: [] for a in ("dense", "hswm", "clique")}

    for i in range(len(df)):
        row = df.iloc[i]
        w = worlds[row["book_name"]]
        W = w["field"].value(q_vecs[i])
        o_dense = np.argsort(-W, kind="stable")[: c1.TOP_K]
        o_hswm, _, _ = traversal.traverse(
            w["field"], q_vecs[i], k=c1.TOP_K, mu=c1.MU, K=c1.K_HOPS,
            kappa=c1.KAPPA, gamma=c1.GAMMA, index=w["idx"])
        o_clique = c1.clique_walk(W, w["members"], w["idf"], c1.TOP_K)
        orders = {"dense": o_dense, "hswm": o_hswm, "clique": o_clique}
        for arm, order in orders.items():
            ev = "\n...\n".join(w["chunks"][int(j)] for j in order)
            prompt = c1.JUDGE_TEMPLATE.format(
                book=row["book_name"], char=row["char"],
                prequel=row["content"], evidence=ev)
            p = judge_cache_path(prompt)
            if not p.exists():
                raise SystemExit(f"judge cache miss at instance {i} arm {arm}")
            d = json.loads(p.read_text(encoding="utf-8"))
            preds[arm].append(c1.parse_verdict(d["text"]))
        if (i + 1) % 50 == 0:
            print(f"[collect] {i + 1}/{len(df)}", flush=True)

    rec = {
        "schema": "c1-replay-records/v1",
        "source_run": "c1_prelude_bookscale.py full run (cache 재구성, 네트워크 0)",
        "n_instances": len(df),
        "book_names": list(df["book_name"]),
        "golds": golds,
        "preds": preds,
        "manifest": {
            "parquet_sha256": c1.sha256_file(os.path.join(c1.DATA, "public.parquet")),
            "books_sha256": {b: s["sha256"] for b, s in c1.BOOKS.items()},
            "params": {"TOP_K": c1.TOP_K, "MU": c1.MU, "K_HOPS": c1.K_HOPS,
                       "KAPPA": c1.KAPPA, "GAMMA": c1.GAMMA,
                       "BOOT": BOOT, "SEED": SEED},
        },
    }
    RECORDS.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    print(f"[collect] records -> {RECORDS} (n={len(df)})", flush=True)
    return 0


def main() -> int:
    if "--collect" in sys.argv:
        return collect()
    return score()


if __name__ == "__main__":
    raise SystemExit(main())
