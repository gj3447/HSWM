#!/usr/bin/env python3
"""B2: cross-field merge payoff — merge(A,B)가 cross-field 질의에서 best-single을 이기나.

Programme: LakatosTree_PromSearchHSWM_20260721
Branch:    B2-crossfield-merge-payoff  (질문: Q-federated-hswm-merge-crossfield)
Spec:      ../DESIGN_PHASE_B_FEDERATED_HSWM_2026-07-22.md §3(L5 no-harm)·§6(F-B2a/b/c)

설계 (전부 결정론):
  - 2Wiki 문맥 문단을 sha256(title) 짝홀로 두 provenance field A/B에 분할.
  - field = build_hypergraph(문단=하이퍼엣지, entity 정점은 field-접두 네임스페이스)
    + Field(provenance={eid: (label,)}) — B0 대수(hswm_field_algebra) 그대로 재사용.
  - seam = 두 field에서 정규화 entity 이름이 같은 정점 쌍마다 SeamArc 1개.
  - arm 3종: merged(=merge(A,B,seam)) / best_single(질의별 max(recall_A, recall_B)) /
    merged_no_seam(=compose([A,B]), seam 0개 — F-B2c ablation).
  - readout: V∪E cosine + seam-class 1-hop 엣지 bridge 채널. seam이 없으면
    cross-field bridge가 구조적으로 불가능 — ablation이 진짜 seam을 재는 이유.
  - 질의 계층: gold 문단 title들의 짝홀이 양쪽이면 cross_field, 한쪽이면 in_field.
    gold는 계층화·평가에만 쓰고 구성에는 절대 안 씀.

정직 경계: 이 하니스는 구조만 짓는다; 주장은 prereg 뒤에서만. main()은 PREREG JSON의
  server-confirmed receipt + frozen sha 일치 없이는 한 발도 안 나간다. 이 파일의 존재는
  F-B2a/b/c 어느 쪽의 증거도 아니다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import re
import statistics
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from hswm_hypergraph import build_hypergraph  # noqa: E402
from hswm_hypergraph_readout import readout  # noqa: E402
from hswm_field_algebra import Field, SeamArc, compose, field_id, merge  # noqa: E402

TREE = "LakatosTree_PromSearchHSWM_20260721"
BRANCH = "B2-crossfield-merge-payoff"
QUESTION = "Q-federated-hswm-merge-crossfield"
CONJECTURE = (
    "On 2Wiki, merging two provenance fields with seam identity arcs beats the best "
    "single field on cross-field queries (F-B2a) without harming in-field queries "
    "beyond the noise band (F-B2b, L5), and the gain vanishes without seams (F-B2c)."
)

PREREG = HERE / "evidence" / "PREREG_b2_crossfield_merge_20260722.json"
OUTPUT = HERE / "evidence" / "EVIDENCE_b2_crossfield_merge_20260722.json"
FROZEN_MODULES = ("hswm_field_algebra.py", "hswm_hypergraph.py", "hswm_hypergraph_readout.py")

N_Q = 400
SEED = 7332
TOP_K = 10
BOOTSTRAP_REPS = 2000
LAM_V = 0.10      # V(정점) cosine 채널 가중
LAM_B = 0.30      # seam-class 1-hop 엣지 bridge 채널 가중
NOISE_BAND = 0.02  # F-B2b no-harm 허용 회귀
MODEL_NAME = "all-MiniLM-L6-v2"  # prom_p5/p6과 동일 (실측 arm 전용; 테스트는 hash embedder)

STOP = {
    "The", "A", "An", "In", "On", "At", "He", "She", "It", "They", "This",
    "That", "His", "Her", "When", "After", "Before", "There", "Their", "These",
    "Those", "As", "Of", "For", "And", "But", "Also", "However", "Its", "Who",
    "Which", "What", "Where", "Was", "Were", "Is", "Are", "Did", "Does",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=HERE, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


# ---------- 분할 / 문단 / 계층화 ----------

def base_entities(text: str) -> set[str]:
    """대문자 고유명 추출 (p5와 동일 규칙). 정규화 = lower."""
    return {
        m.lower()
        for m in re.findall(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\b", text)
        if m not in STOP and len(m) > 2
    }


def title_parity(title: str) -> str:
    """sha256(title) 짝홀 → 'A'(짝) / 'B'(홀). 문단의 field 소속을 결정."""
    return "A" if int(hashlib.sha256(title.encode("utf-8")).hexdigest(), 16) % 2 == 0 else "B"


def finding_text(title: str, body: str) -> str:
    return f"{title} :: {body}"


def _row_paragraphs(row: dict) -> list[tuple[str, str, str]]:
    ctx = row["context"]
    out = []
    for title, sents in zip(ctx["title"], ctx["sentences"]):
        body = " ".join(s.strip() for s in sents).strip()
        pid = "p" + hashlib.sha256(f"{title}\0{body}".encode("utf-8")).hexdigest()[:16]
        out.append((pid, title, body))
    return out


def paragraphs_from_rows(rows: list[dict]) -> dict[str, dict]:
    """전 row 문단 dedup pool. pid → {title, body, field}. 결정론(pid 정렬)."""
    pool: dict[str, dict] = {}
    for row in rows:
        for pid, title, body in _row_paragraphs(row):
            pool.setdefault(pid, {"title": title, "body": body, "field": title_parity(title)})
    return {pid: pool[pid] for pid in sorted(pool)}


def resolve_gold(row: dict) -> tuple[set[str], set[str]] | None:
    """supporting_facts title → 이 row 문맥의 gold pid들 + field 짝홀 집합.
    해석 불가 title이 하나라도 있으면 None (row 자체를 표본에서 제외)."""
    by_title: dict[str, str] = {}
    by_fold: dict[str, str] = {}
    title_of: dict[str, str] = {}
    for pid, title, _ in _row_paragraphs(row):
        by_title.setdefault(title, pid)
        by_fold.setdefault(title.casefold(), pid)
        title_of.setdefault(pid, title)
    gold: set[str] = set()
    parities: set[str] = set()
    titles = row.get("supporting_facts", {}).get("title", [])
    if not titles:
        return None
    for st in titles:
        pid = by_title.get(st) or by_fold.get(st.casefold())
        if pid is None:
            return None
        gold.add(pid)
        parities.add(title_parity(title_of[pid]))
    return gold, parities


def stratify(row: dict) -> tuple[str, set[str]] | None:
    """('cross_field'|'in_field', gold_pids). gold는 여기(계층)와 recall(평가)에만 쓴다."""
    resolved = resolve_gold(row)
    if resolved is None:
        return None
    gold, parities = resolved
    return ("cross_field" if parities == {"A", "B"} else "in_field"), gold


# ---------- field 구성 / seam ----------

def build_field(pool: dict[str, dict], label: str) -> Field:
    findings = [
        {"rf": pid, "text": finding_text(rec["title"], rec["body"]), "clusters": []}
        for pid, rec in pool.items() if rec["field"] == label
    ]
    if not findings:
        raise RuntimeError(f"field {label}: 문단 0개 — 표본이 분할을 못 채움")
    hg = build_hypergraph(
        findings,
        extractor=lambda t, _l=label: {f"{_l}/{n}" for n in base_entities(t)},
        topic_vertices=False,
    )
    return Field(hg=hg, provenance={eid: (label,) for eid in hg.edges},
                 ledger=frozenset(), seam=())


def clean_vertex_text(v) -> str:
    """field-접두를 벗긴 정규화 entity 이름 (임베딩 키; 접두 오염 방지)."""
    if v.kind == "entity" and "/" in v.name:
        return v.name.split("/", 1)[1]
    return v.embed_text


def seam_arcs_between(a: Field, b: Field) -> tuple[SeamArc, ...]:
    """정규화 이름이 같은 (A정점, B정점) 쌍마다 SeamArc 1개. 결정론(이름 정렬)."""
    names_a = {clean_vertex_text(v): vid for vid, v in sorted(a.hg.vertices.items())
               if v.kind == "entity"}
    names_b = {clean_vertex_text(v): vid for vid, v in sorted(b.hg.vertices.items())
               if v.kind == "entity"}
    arcs = []
    for name in sorted(set(names_a) & set(names_b)):
        key = hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]
        arcs.append(SeamArc(arc_id=f"seam-{key}", left_vid=names_a[name],
                            right_vid=names_b[name],
                            evidence=f"equal-normalized-entity:{name}",
                            event_id=f"ev-seam-{key}"))
    return tuple(arcs)


def collect_texts(fields: list[Field], questions: list[str]) -> list[str]:
    texts: set[str] = set(questions)
    for f in fields:
        texts.update(clean_vertex_text(v) for v in f.hg.vertices.values())
        texts.update(e.value for e in f.hg.edges.values())
    return sorted(texts)


def attach_embeddings(f: Field, table: dict) -> None:
    for v in f.hg.vertices.values():
        v.embedding = table[clean_vertex_text(v)]
    for e in f.hg.edges.values():
        e.embedding = table[e.value]


# ---------- readout arm (V∪E + seam-class bridge) ----------

def _seam_classes(f: Field) -> dict[str, str]:
    parent = {vid: vid for vid in f.hg.vertices}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for arc in f.seam:
        ra, rb = find(arc.left_vid), find(arc.right_vid)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    return {vid: find(vid) for vid in parent}


def rank_paragraphs(f: Field, query_vec, *, top_k: int = TOP_K,
                    lam_v: float = LAM_V, lam_b: float = LAM_B) -> list[tuple[str, float]]:
    """문단(하이퍼엣지) 랭킹 = 직접 cosine + V채널 + seam-class 1-hop bridge.
    seam이 없으면 bridge는 field 내부에 갇힌다 — F-B2c의 기계적 근거."""
    hg = f.hg
    scored = readout(hg, query_vec, mode="v_union_e",
                     top_k=len(hg.vertices) + len(hg.edges))
    vert_cos = {uid: s for kind, uid, s in scored if kind == "V"}
    edge_cos = {uid: s for kind, uid, s in scored if kind == "E"}
    root_of = _seam_classes(f)
    class_edges: defaultdict[str, set[str]] = defaultdict(set)
    for vid, root in root_of.items():
        class_edges[root].update(hg.vertices[vid].incident_edges)
    out = []
    for eid in sorted(hg.edges):
        members = hg.edges[eid].members
        v_chan = max((vert_cos[v] for v in members), default=0.0)
        bridge = 0.0
        for v in members:
            for e2 in class_edges[root_of[v]]:
                if e2 != eid and edge_cos[e2] > bridge:
                    bridge = edge_cos[e2]
        out.append((eid, edge_cos[eid] + lam_v * v_chan + lam_b * bridge))
    out.sort(key=lambda r: (-r[1], r[0]))
    return out[:top_k]


def recall_at(ranked_ids: list[str], gold: set[str], k: int) -> float:
    if not gold:
        return 0.0
    return len(set(ranked_ids[:k]) & gold) / len(gold)


def paired_bootstrap(values: list[float], reps: int, seed: int) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(reps))
    return means[int(0.025 * reps)], means[int(0.975 * reps)]


# ---------- 실험 본체 (embed_fn 주입 — 테스트는 hash embedder) ----------

def run_experiment(rows: list[dict], embed_fn, *, n_q: int | None = None,
                   seed: int = SEED, top_k: int = TOP_K,
                   bootstrap_reps: int = BOOTSTRAP_REPS, lam_v: float = LAM_V,
                   lam_b: float = LAM_B, noise_band: float = NOISE_BAND) -> dict:
    usable = []
    for row in rows:
        strat = stratify(row)
        if strat is not None:
            usable.append((row, *strat))
    order = list(range(len(usable)))
    random.Random(seed).shuffle(order)
    usable = [usable[i] for i in order]
    if n_q is not None:
        if len(usable) < n_q:
            raise RuntimeError(f"usable rows {len(usable)} < n_q {n_q}")
        usable = usable[:n_q]

    pool = paragraphs_from_rows([row for row, _, _ in usable])
    f_a, f_b = build_field(pool, "A"), build_field(pool, "B")
    arcs = seam_arcs_between(f_a, f_b)
    f_merged = merge(f_a, f_b, new_seam=arcs)
    f_no_seam = compose([f_a, f_b])

    questions = [row["question"] for row, _, _ in usable]
    texts = collect_texts([f_a, f_b, f_merged, f_no_seam], questions)
    table = dict(zip(texts, embed_fn(texts)))
    for f in (f_a, f_b, f_merged, f_no_seam):
        attach_embeddings(f, table)

    per_query = []
    for row, klass, gold in usable:
        qv = table[row["question"]]
        arm = {name: [eid for eid, _ in rank_paragraphs(f, qv, top_k=top_k,
                                                        lam_v=lam_v, lam_b=lam_b)]
               for name, f in (("a", f_a), ("b", f_b),
                               ("merged", f_merged), ("no_seam", f_no_seam))}
        r = {name: recall_at(ids, gold, top_k) for name, ids in arm.items()}
        per_query.append({
            "id": str(row.get("id", "")), "class": klass,
            "merged": r["merged"], "best_single": max(r["a"], r["b"]),
            "no_seam": r["no_seam"],
        })

    cross = [q for q in per_query if q["class"] == "cross_field"]
    infield = [q for q in per_query if q["class"] == "in_field"]
    if not cross or not infield:
        raise RuntimeError("both cross_field and in_field strata are required")

    def mean(rows_, key):
        return float(statistics.mean(q[key] for q in rows_))

    d_a = [q["merged"] - q["best_single"] for q in cross]
    d_b = [q["merged"] - q["best_single"] for q in infield]
    d_c = [q["merged"] - q["no_seam"] for q in cross]
    ci_a = paired_bootstrap(d_a, bootstrap_reps, seed + 1)
    ci_b = paired_bootstrap(d_b, bootstrap_reps, seed + 2)
    ci_c = paired_bootstrap(d_c, bootstrap_reps, seed + 3)

    def cls_block(rows_):
        return {"n": len(rows_), "merged_recall10": round(mean(rows_, "merged"), 6),
                "best_single_recall10": round(mean(rows_, "best_single"), 6),
                "merged_no_seam_recall10": round(mean(rows_, "no_seam"), 6)}

    row_ids_sha = hashlib.sha256(
        "\n".join(q["id"] for q in per_query).encode("utf-8")).hexdigest()
    return {
        "measurement": {
            "metric": "crossfield_merged_minus_best_single_recall10",
            "value": round(float(statistics.mean(d_a)), 6),
            "per_class": {"cross_field": cls_block(cross), "in_field": cls_block(infield)},
            "f_b2a": {"description": "cross-field: merged - best_single",
                      "delta": round(float(statistics.mean(d_a)), 6),
                      "bootstrap95": [round(x, 6) for x in ci_a],
                      "check_lower_gt_0": ci_a[0] > 0.0},
            "f_b2b": {"description": "in-field no-harm (L5): merged - best_single",
                      "delta": round(float(statistics.mean(d_b)), 6),
                      "bootstrap95": [round(x, 6) for x in ci_b],
                      "noise_band": noise_band,
                      "check_no_harm": float(statistics.mean(d_b)) >= -noise_band},
            "f_b2c": {"description": "cross-field seam ablation: merged - merged_no_seam",
                      "delta": round(float(statistics.mean(d_c)), 6),
                      "bootstrap95": [round(x, 6) for x in ci_c],
                      "check_lower_gt_0": ci_c[0] > 0.0},
        },
        "fields": {"field_id_a": field_id(f_a), "field_id_b": field_id(f_b),
                   "field_id_merged": field_id(f_merged),
                   "field_id_merged_no_seam": field_id(f_no_seam),
                   "n_seam_arcs": len(arcs)},
        "sample": {"seed": seed, "n_rows_used": len(per_query),
                   "n_paragraphs": len(pool), "row_ids_sha256": row_ids_sha,
                   "class_counts": {"cross_field": len(cross), "in_field": len(infield)}},
    }


# ---------- prereg guard + main (parent 세션만 실행; 지금은 실행 금지) ----------

def locked_parameters() -> dict:
    return {"n_q": N_Q, "seed": SEED, "top_k": TOP_K, "bootstrap_reps": BOOTSTRAP_REPS,
            "lam_v": LAM_V, "lam_b": LAM_B, "noise_band": NOISE_BAND, "model": MODEL_NAME}


def preregistration_guard(script_sha: str, dataset_sha: str) -> dict:
    if not PREREG.exists():
        raise RuntimeError(f"missing preregistration: {PREREG}")
    locked = json.loads(PREREG.read_text(encoding="utf-8"))
    if locked.get("registered_before_measurement") is not True:
        raise RuntimeError("preregistration is not server-confirmed before measurement")
    if not locked.get("prediction_receipt_sha256"):
        raise RuntimeError("preregistration lacks a prediction receipt")
    expected = {"script_sha256": script_sha, "dataset_sha256": dataset_sha}
    for name in FROZEN_MODULES:
        expected[f"{name}_sha256"] = sha256_file(HERE / name)
    for key, value in expected.items():
        if locked.get(key) != value:
            raise RuntimeError(f"frozen artifact drift: {key}={locked.get(key)!r} != {value!r}")
    if locked.get("locked_parameters") != locked_parameters():
        raise RuntimeError("locked parameter drift")
    return locked


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, help="2Wiki rows JSON (list 또는 {'rows': [...]})")
    args = parser.parse_args()
    started_at = utc_now()
    data_path = Path(args.data)
    script_sha = sha256_file(Path(__file__).resolve())
    dataset_sha = sha256_file(data_path)
    locked = preregistration_guard(script_sha, dataset_sha)

    raw = json.loads(data_path.read_text(encoding="utf-8"))
    rows = raw["rows"] if isinstance(raw, dict) else raw

    from sentence_transformers import SentenceTransformer, __version__ as st_version
    import torch
    torch.manual_seed(SEED)
    cache = Path("/Volumes/GM/hswm_lab/st_cache")
    model = SentenceTransformer(MODEL_NAME, cache_folder=str(cache))

    def embed_fn(texts: list[str]):
        return model.encode(texts, normalize_embeddings=True, convert_to_numpy=True,
                            batch_size=128, show_progress_bar=False).tolist()

    core = run_experiment(rows, embed_fn, n_q=N_Q, seed=SEED)
    evidence = {
        "schema": "lakato-evidence-record/v1",
        "programme": TREE, "branch": BRANCH, "question": QUESTION,
        "conjecture": CONJECTURE,
        "preregistration": {
            "path": str(PREREG),
            "registered_at": locked.get("server_registered_at"),
            "registered_before_measurement": True,
            "prediction_receipt_sha256": locked["prediction_receipt_sha256"],
            "script_sha256": script_sha,
        },
        **core,
        "provenance": {
            "grounded": True,
            "inputs": [
                {"kind": "source", "path": str(data_path), "sha256": dataset_sha},
                {"kind": "harness", "path": str(Path(__file__).resolve()), "sha256": script_sha},
                {"kind": "preregistration", "path": str(PREREG), "sha256": sha256_file(PREREG)},
            ] + [{"kind": "frozen_module", "path": str(HERE / n), "sha256": sha256_file(HERE / n)}
                 for n in FROZEN_MODULES],
        },
        "harness": {
            "command": ("/Users/lagyeongjun/CD/bhgman_tool/.venv/bin/python "
                        f"HSWM/prom_search_hswm/prom_b2_crossfield_merge.py --data {data_path}"),
            "git_head": git_head(),
            "environment": {"python": sys.version.split()[0], "platform": platform.platform(),
                            "sentence_transformers": st_version, "model": MODEL_NAME},
            "started_at": started_at, "finished_at": utc_now(), "exit_code": 0,
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence": str(OUTPUT), "evidence_sha256": sha256_file(OUTPUT),
                      "f_b2a": evidence["measurement"]["f_b2a"],
                      "f_b2b": evidence["measurement"]["f_b2b"],
                      "f_b2c": evidence["measurement"]["f_b2c"]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
