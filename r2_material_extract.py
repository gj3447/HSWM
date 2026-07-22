"""R2 ML-material extraction — ReFinED(QID linking) + fastcoref(coreference).

PROM-8 C3 채택 실행 (USER 2026-07-22 "연산 많이 해도 똑똑해지면 된다" — 값싼
결정론 weave의 T1 RED 이후, 진짜 재료로 걷기를 재시험하는 R2의 1단계).

frozen V5 development 문단(2,094 + 1,505 = 3,599개)의 body text 위에서
build-time 추출만 수행한다. query·gold·질문 텍스트는 일절 읽지 않는다.

- 모든 span은 `text[start:end] == exact`를 즉석 검증, 불일치는 드롭·카운트(날조 0).
- 모델·revision·config를 receipt에 attestation으로 박제 (재현 계약).
- CPU 고정 (A1 조사: GPU tie-break 비결정론 회피).
- 출력: .ab_p5_cache/r2_material/{dataset}_{phase}.json (sha는 요약에 별도 기록).

실행 (venv 분리 — 의존성 충돌 격리):
  .venv_coref/bin/python  r2_material_extract.py --phase coref
  .venv_refined/bin/python r2_material_extract.py --phase link
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

HERE = Path(__file__).parent
CACHE = HERE / ".ab_p5_cache" / "h3_b3"
OUT_DIR = HERE / ".ab_p5_cache" / "r2_material"
SEGMENTS = {
    "musique": CACHE / "musique_development_v4_segment.json",
    "2wiki": CACHE / "2wiki_development_v4_segment.json",
}
GM_LAB = Path("/Volumes/GM/hswm_lab")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_paragraphs(dataset: str) -> list[dict]:
    seg = json.loads(SEGMENTS[dataset].read_text(encoding="utf-8"))
    return [{"source_id": p["source_id"], "text": p["text"]}
            for p in seg["paragraphs"]]


def run_coref(paragraphs: list[dict]) -> tuple[list[dict], dict]:
    from fastcoref import FCoref
    model = FCoref(device="cpu")
    texts = [p["text"] for p in paragraphs]
    preds = model.predict(texts=texts)
    records, dropped = [], 0
    for p, pred in zip(paragraphs, preds):
        clusters_out = []
        spans = pred.get_clusters(as_strings=False)
        strings = pred.get_clusters(as_strings=True)
        for cluster, cluster_strs in zip(spans, strings):
            mentions = []
            for (start, end), s in zip(cluster, cluster_strs):
                exact = p["text"][start:end]
                if exact != s:
                    dropped += 1
                    continue
                mentions.append({"start": start, "end": end, "exact": exact})
            if len(mentions) >= 2:
                clusters_out.append(mentions)
        records.append({
            "source_id": p["source_id"],
            "source_text_sha256": sha256_text(p["text"]),
            "clusters": clusters_out,
        })
    attestation = {
        "tool": "fastcoref.FCoref", "device": "cpu",
        "package": _pkg_version("fastcoref"),
    }
    return records, attestation


def run_link(paragraphs: list[dict], checkpoint: Path | None = None, max_new: int = 0) -> tuple[list[dict], dict]:
    import torch
    torch.set_num_threads(2)  # Mac RAM/CPU 압박 완화 (jetsam kill 회피)
    from refined.inference.processor import Refined
    data_dir = GM_LAB / "refined_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    model = Refined.from_pretrained(
        model_name="wikipedia_model_with_numbers",
        entity_set="wikipedia",
        data_dir=str(data_dir),
        device="cpu",
    )
    records, dropped = [], 0
    done_ids: set[str] = set()
    if checkpoint and checkpoint.exists():
        records = json.loads(checkpoint.read_text(encoding="utf-8"))
        done_ids = {r["source_id"] for r in records}
        print(f"[resume] {len(done_ids)} paragraphs from checkpoint", flush=True)
    since_save = 0
    paragraphs = [p for p in paragraphs if p["source_id"] not in done_ids]
    if max_new:
        paragraphs = paragraphs[:max_new]
    for p in paragraphs:
        spans_out = []
        for span in model.process_text(p["text"]):
            start = span.start
            exact = p["text"][start:start + span.ln]
            if exact != span.text:
                dropped += 1
                continue
            qid = (span.predicted_entity.wikidata_entity_id
                   if span.predicted_entity else None)
            candidates = [
                {"qid": c[0].wikidata_entity_id if hasattr(c[0], "wikidata_entity_id") else str(c[0]),
                 "score": float(c[1])}
                for c in (span.candidate_entities or [])[:5]
            ]
            spans_out.append({
                "start": start, "end": start + span.ln, "exact": exact,
                "qid": qid,
                "coarse_type": getattr(span, "coarse_type", None),
                "candidates": candidates,
            })
        records.append({
            "source_id": p["source_id"],
            "source_text_sha256": sha256_text(p["text"]),
            "spans": spans_out,
        })
        since_save += 1
        if checkpoint and since_save >= 200:
            checkpoint.write_text(json.dumps(records, ensure_ascii=False),
                                  encoding="utf-8")
            since_save = 0
            print(f"[checkpoint] {len(records)} paragraphs", flush=True)
    if checkpoint:
        checkpoint.write_text(json.dumps(records, ensure_ascii=False),
                              encoding="utf-8")
    attestation = {
        "tool": "ReFinED", "model_name": "wikipedia_model_with_numbers",
        "entity_set": "wikipedia", "device": "cpu",
        "package": _pkg_version("refined") or _pkg_version("ReFinED"),
    }
    return records, attestation


def _pkg_version(name: str):
    try:
        from importlib.metadata import version
        return version(name)
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["coref", "link"], required=True)
    parser.add_argument("--datasets", default="musique,2wiki")
    parser.add_argument("--max-new", type=int, default=0,
                        help="이번 프로세스에서 처리할 신규 문단 상한 (0=무제한). "
                             "라운드제 실행용 — 스왑 누적 없이 깨끗이 종료 후 재시작.")
    args = parser.parse_args()
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    summary = {}
    for dataset in args.datasets.split(","):
        started = time.time()
        paragraphs = load_paragraphs(dataset)
        if args.phase == "coref":
            records, attestation = run_coref(paragraphs)
            n_units = sum(len(r["clusters"]) for r in records)
        else:
            ckpt = OUT_DIR / f"{dataset}_link.partial.json"
            records, attestation = run_link(paragraphs, checkpoint=ckpt, max_new=args.max_new)
            n_units = sum(len(r["spans"]) for r in records)
            if len(records) < len(paragraphs):
                print(json.dumps({dataset: {"round_progress": len(records),
                                            "total": len(paragraphs)}}))
                continue  # 미완 라운드: 최종 파일 쓰지 않고 체크포인트 유지
            ckpt.unlink(missing_ok=True)
        payload = {
            "schema": f"hswm-r2-material-{args.phase}/v1",
            "dataset": dataset,
            "n_paragraphs": len(paragraphs),
            "n_units": n_units,
            "attestation": attestation,
            "records": records,
        }
        out = OUT_DIR / f"{dataset}_{args.phase}.json"
        blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        out.write_text(blob, encoding="utf-8")
        summary[dataset] = {
            "path": str(out), "sha256": hashlib.sha256(blob.encode()).hexdigest(),
            "n_paragraphs": len(paragraphs), "n_units": n_units,
            "elapsed_s": round(time.time() - started, 1),
        }
        print(json.dumps({dataset: summary[dataset]}, ensure_ascii=False))
    print(json.dumps({"phase": args.phase, "summary": summary}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
