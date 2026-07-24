"""R3 replay 아티팩트 덤프 — 측정주권 분리 (producer=Mac/torch → artifact → judge=순수numpy).

판정 장부 수리(2026-07-24): 서버 replay('python <script> <result_path>')가 torch 없는
컨테이너에서도 재실행 가능하도록 측정을 둘로 분리한다.

  ① 본 스크립트(producer, Mac 전용): MiniLM 임베딩을 실행하고, 재채점에 필요한 입력만 저장
     - static_<uni>.npy   : (n_queries, n_docs) float64 점수행렬 (BLAS는 Mac에서만, judge는 적재만)
     - rows_<uni>.json     : 질의 메타(id/hop/question/gold source-id 집합)
     - universes/<uni>/    : PhantomWiki 원문(articles.json+questions/) 사본 + sha 매니페스트
  ② r3_replay_judge.py(judge, 순수 numpy): ①만으로 primary/novel metric을 재생성.

①의 임베딩 재계산은 같은 머신/라이브러리에서 결정론 — 그래도 judge 출력이
EVIDENCE_R3_WALK_REGIME_2026-07-23.json 의 값과 다르다면 **judge 값이 정본**(아티팩트-재현 가능한 쪽).
"""
from __future__ import annotations

import json
import os
import shutil
from hashlib import sha256
from pathlib import Path

import numpy as np

import typed_composition as typed  # noqa: F401  (dump가 judge와 동일 모듈 버전 공유 확인용)
from r3_phantom_ingest import build_graph, load_universe, source_id_for
from r3_walk_regime import (
    MODEL, UNIVERSES, locked_parameters,
)

HERE = Path(__file__).parent
ROOT = Path(os.environ.get("R3_ROOT", str(Path.home() / "hswm_lab/phantomwiki_r3")))
ST_CACHE = os.environ.get("R3_ST_CACHE", str(Path.home() / "hswm_lab/st_cache"))
OUT = HERE / "_research" / "r3_replay"
UNI_OUT = OUT / "universes"

# r3_walk_regime.trace_golds 와 동일 규칙으로 gold source-id 집합을 만든다.
from r3_walk_regime import trace_golds  # noqa: E402


def main() -> int:
    from sentence_transformers import SentenceTransformer
    import torch

    from r3_walk_regime import BOOT_SEED
    torch.manual_seed(BOOT_SEED)
    torch.set_num_threads(2)
    model = SentenceTransformer(MODEL, cache_folder=ST_CACHE)

    def embed(texts: list[str]) -> np.ndarray:
        return model.encode(texts, normalize_embeddings=True,
                            convert_to_numpy=True, batch_size=64,
                            show_progress_bar=False).astype(np.float64)

    OUT.mkdir(parents=True, exist_ok=True)
    UNI_OUT.mkdir(parents=True, exist_ok=True)
    manifest = {"model": MODEL, "params": locked_parameters(), "universes": {}}

    for uni in sorted(UNIVERSES):
        src_dir, dst_dir = ROOT / uni, UNI_OUT / uni
        if dst_dir.exists():
            shutil.rmtree(dst_dir)
        shutil.copytree(src_dir, dst_dir)
        articles_sha = sha256((dst_dir / "articles.json").read_bytes()).hexdigest()

        articles, questions = load_universe(dst_dir)
        titles = {a["title"] for a in articles}
        doc_texts = [a["article"] for a in sorted(articles, key=lambda x: x["title"])]
        doc_vecs = embed(doc_texts)

        rows = []
        for q in questions:
            if q.get("is_aggregation_question"):
                continue
            golds = trace_golds(q, titles)
            if golds:
                rows.append((q, golds))
        rows.sort(key=lambda r: r[0]["id"])
        q_vecs = embed([q["question"] for q, _ in rows])

        static_all = (doc_vecs @ q_vecs.T).T.astype(np.float64)  # (n_queries, n_docs)
        rows_meta = [{
            "id": q["id"], "hop": int(q.get("difficulty", 0)),
            "question": q["question"],
            "golds": [sorted(g) for g in golds],
        } for q, golds in rows]

        np.save(OUT / f"static_{uni}.npy", static_all)
        (OUT / f"rows_{uni}.json").write_text(
            json.dumps(rows_meta, ensure_ascii=False), encoding="utf-8")
        manifest["universes"][uni] = {
            "articles_sha256": articles_sha,
            "n_rows": len(rows), "static_shape": list(static_all.shape),
        }
        print(f"{uni}: rows={len(rows)} static={static_all.shape}", flush=True)

    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("dump done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
