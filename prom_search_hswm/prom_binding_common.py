#!/usr/bin/env python3
"""
prom_binding_common — P1(binding density) / P4(equal-compute) 공용 하니스 (W1-T1).

LakatoTree: LakatosTree_PromSearchHSWM_20260721 — P1-binding-density / P4-equal-compute-control
공용 부품 모듈. **이 모듈은 측정하지 않는다** — frozen gold 로드, τ MC-null 캘리브레이션,
검증된 부품 재사용, evidence JSON 헬퍼만 제공. 사전등록 metric 정의는 각 judge
스크립트(prom_p1_binding_density.py / prom_p4_equalcompute_ab.py)가 소유한다.

재사용 provenance (전부 이 repo의 검증된 부품 — 함수 옆에 원 위치 명기):
- load_gold:          prom_consensus_real.py L27-32 패턴
- embed / cosine:     prom_consensus_real.py L50-56 (paraphrase-multilingual-MiniLM-L12-v2,
                      torch.manual_seed(SEED), normalize_embeddings=True)
- toks / lexical_rank: prom_legend_recall.py L63-76 (라틴/한글/한자 토크나이저 + Jaccard)
- norm (정규화 CONTAINS): prom_consensus_real.py L25 (현 PROM Step 2.5/3.3 lexical 재현)
- mc_null_z:          prom_consensus_real.py L83-92 패턴 일반화 (NULL_PERMS=2000, SEED=333)
- rrf_fuse:           hswm_fusion.py fuse(strategy='blind') 래핑 (RRF_K=60)
- evidence 헬퍼:      prom_consensus_bench.py L156-184 스키마
                      (experiment/tree/node/a_priori/prereg/_facts; _facts=부울·수치만, 자기채점 금지)

τ 규율 (P1 frontier_rule 'MC-null 캘리브레이션 τ' 강제, coverage_backlog
'tau-MC-null-calibration' 해소): τ = calibration split의 mismatched-pair(finding×비gold
candidate) cosine null 분포에서 null_mean + 3·null_std. gold(matched pair)로 τ 튜닝 금지.
완전 결정론 (RNG 불사용 — 전체 mismatched pair 사용).

gold = data/binding_gold_p1.json (frozen, W1-T1에서 홈canon Neo4j read-only pull로 동결).
split = SEED=333 결정론 calibration/eval 반반 (split_assignment) — JSON에 동결된 값과
재계산 값이 항상 일치해야 한다 (verify_split).

실행 환경: 임베딩 스모크는 ./run_on_gm.sh prom_binding_common.py (GM 마운트 필수,
모델캐시→GM). venv = ~/CD/bhgman_tool/.venv/bin/python (sentence-transformers 5.5.1).
"""
from __future__ import annotations

import json
import random
import re
import statistics
from pathlib import Path

SEED = 333
NULL_PERMS = 2000
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
RRF_K = 60
TAU_K_SIGMA = 3.0
N_DISTRACTORS_PER_FINDING = 20
TREE = "LakatosTree_PromSearchHSWM_20260721"
HERE = Path(__file__).parent
GOLD_PATH = HERE / "data" / "binding_gold_p1.json"


# ---------------------------------------------------------------- gold
def load_gold(path: Path = GOLD_PATH) -> dict:
    """frozen gold 로드 — prom_consensus_real.py L27-32 패턴."""
    return json.loads(Path(path).read_text())


def split_assignment(finding_ids, seed: int = SEED) -> dict:
    """SEED 결정론 calibration/eval 반반 split.

    sorted(finding_ids)를 random.Random(seed)로 셔플, 앞 절반 = calibration,
    나머지 = eval. 입력 순서 무관·플랫폼 무관 결정론.
    """
    ids = sorted(finding_ids)
    rng = random.Random(seed)
    rng.shuffle(ids)
    half = len(ids) // 2
    calib = set(ids[:half])
    return {fid: ("calibration" if fid in calib else "eval") for fid in finding_ids}


def verify_split(gold: dict) -> bool:
    """gold JSON에 동결된 split 필드 == split_assignment 재계산. 불일치면 ValueError."""
    frozen = {f["finding_id"]: f["split"] for f in gold["findings"]}
    recomputed = split_assignment(list(frozen), seed=gold["seed"])
    bad = {k for k in frozen if frozen[k] != recomputed[k]}
    if bad:
        raise ValueError(f"split drift vs SEED={gold['seed']} recomputation: {sorted(bad)[:5]} ...")
    return True


def sample_distractors(finding_id: str, pool_names, n: int = N_DISTRACTORS_PER_FINDING,
                       seed: int = SEED) -> list:
    """per-finding 결정론 distractor 샘플 — random.Random(f'{seed}:{finding_id}')."""
    rng = random.Random(f"{seed}:{finding_id}")
    pool = sorted(pool_names)
    return sorted(rng.sample(pool, min(n, len(pool))))


# ---------------------------------------------------------------- embedding
def embed(texts, seed: int = SEED, model_name: str = MODEL_NAME, batch_size: int = 64):
    """임베딩 — prom_consensus_real.py L50-56 패턴 (normalize → 내적=cosine)."""
    from sentence_transformers import SentenceTransformer
    import torch

    torch.manual_seed(seed)
    m = SentenceTransformer(model_name)
    return m.encode(list(texts), normalize_embeddings=True, convert_to_numpy=True,
                    batch_size=batch_size)


def cosine_matrix(a_emb, b_emb=None):
    """정규화 임베딩의 내적 = cosine. b_emb 생략 시 자기 자신."""
    if b_emb is None:
        b_emb = a_emb
    return a_emb @ b_emb.T


# ---------------------------------------------------------------- lexical
_TOK = re.compile(r"[a-z0-9]+|[가-힣]+|[一-鿿]")


def toks(s: str) -> set:
    """라틴/한글/한자 토크나이저 — prom_legend_recall.py L63-65."""
    return set(_TOK.findall(s.lower()))


def lexical_rank(q: str, cands) -> list:
    """Jaccard lexical 랭킹 — prom_legend_recall.py L67-76.

    cands: list[(cand_id, text)]. return [(jaccard, cand_id)] 내림차순 (동점 시 id 오름차순).
    """
    qt = toks(q)
    scored = []
    for cid, txt in cands:
        ct = toks(txt)
        inter = len(qt & ct)
        jac = inter / (len(qt | ct) or 1)
        scored.append((jac, cid))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored


def norm(s: str) -> str:
    """정규화 — prom_consensus_real.py L25."""
    return " ".join(s.lower().split())


def norm_contains(a: str, b: str) -> bool:
    """정규화 CONTAINS (현 PROM Step 2.5/3.3 lexical 판정 재현): 한쪽이 다른 쪽을 포함."""
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return False
    return na in nb or nb in na


# ---------------------------------------------------------------- MC-null
def mc_null_z(observed: float, stat_under_null, n_perms: int = NULL_PERMS,
              seed: int = SEED):
    """MC permutation null — prom_consensus_real.py L83-92 패턴 일반화.

    stat_under_null(rng) -> float : 호출자가 gold를 rng로 섞어 통계 재계산.
    return (z, null_mean, null_std).
    """
    rng = random.Random(seed)
    nulls = [stat_under_null(rng) for _ in range(n_perms)]
    nmean = statistics.mean(nulls)
    nstd = statistics.pstdev(nulls) or 1e-9
    return (observed - nmean) / nstd, nmean, nstd


# ---------------------------------------------------------------- tau
def calibrate_tau(fin_emb, cand_emb, gold_mask, k_sigma: float = TAU_K_SIGMA):
    """τ = mismatched-pair cosine null 분포의 mean + k_sigma·std (기본 3σ).

    fin_emb: (n_fin, d) calibration finding 임베딩 / cand_emb: (n_cand, d) 후보 임베딩.
    gold_mask: (n_fin, n_cand) bool — True=matched(gold) pair. matched pair는 null에서
    제외될 뿐, τ 계산에 사용되지 않는다 (gold 튜닝 금지). RNG 불사용 = 완전 결정론.
    return (tau, null_mean, null_std, n_null_pairs).
    """
    import numpy as np

    mask = np.asarray(gold_mask, dtype=bool)
    cos = np.asarray(fin_emb) @ np.asarray(cand_emb).T
    null_vals = cos[~mask]
    if null_vals.size == 0:
        raise ValueError("no mismatched pairs — cannot calibrate tau")
    m = float(null_vals.mean())
    s = float(null_vals.std())
    return m + k_sigma * s, m, s, int(null_vals.size)


def build_candidate_pool(gold: dict):
    """전역 후보 풀 = target_pool ∪ distractor_pool (id 정렬, 결정론).

    return (cand_ids: list[str], cand_texts: list[str], is_target: list[bool]).
    """
    items = [(f"T::{tid}", txt, True) for tid, txt in sorted(gold["target_pool"].items())]
    items += [(f"D::{did}", txt, False) for did, txt in sorted(gold["distractor_pool"].items())]
    ids = [i for i, _, _ in items]
    texts = [t for _, t, _ in items]
    is_t = [b for _, _, b in items]
    return ids, texts, is_t


def gold_mask_for(findings, cand_ids):
    """gold_mask[i][j] = cand_ids[j]가 findings[i]의 gold target인가 (T:: prefix 규약)."""
    import numpy as np

    mask = np.zeros((len(findings), len(cand_ids)), dtype=bool)
    idx = {cid: j for j, cid in enumerate(cand_ids)}
    for i, f in enumerate(findings):
        for tid in f["gold_target_ids"]:
            j = idx.get(f"T::{tid}")
            if j is not None:
                mask[i][j] = True
    return mask


def tau_from_gold(gold: dict, subset: str = "calibration", k_sigma: float = TAU_K_SIGMA):
    """gold의 calibration split에서 τ 산출 — P1/P4가 공유하는 유일한 τ 절차.

    후보 풀 = 전역(target_pool ∪ distractor_pool). null = calibration finding ×
    비gold 후보 전체 쌍의 cosine. return dict(tau/null_mean/null_std/n_null_pairs/
    n_findings/n_candidates/k_sigma/model/seed).
    """
    fins = [f for f in gold["findings"] if f["split"] == subset]
    if not fins:
        raise ValueError(f"no findings in split={subset!r}")
    cand_ids, cand_texts, _ = build_candidate_pool(gold)
    fin_emb = embed([f["finding_text"] for f in fins])
    cand_emb = embed(cand_texts)
    mask = gold_mask_for(fins, cand_ids)
    tau, m, s, n_null = calibrate_tau(fin_emb, cand_emb, mask, k_sigma=k_sigma)
    return {
        "tau": tau, "null_mean": m, "null_std": s, "n_null_pairs": n_null,
        "n_findings": len(fins), "n_candidates": len(cand_ids),
        "k_sigma": k_sigma, "model": MODEL_NAME, "seed": SEED, "subset": subset,
    }


# ---------------------------------------------------------------- fusion
def rrf_fuse(rankings: dict, k: int = RRF_K):
    """blind RRF 융합 — hswm_fusion.py fuse(strategy='blind') 래핑.

    rankings: dict[arm_name -> list[float] score per candidate].
    return fused score list. (P4 equalcompute arm의 rank-union 전용 —
    場-게이트가 필요한 자리는 gated_agreement를 직접 쓸 것.)
    """
    from hswm_fusion import fuse

    fused, _weights, _dropped = fuse(rankings, strategy="blind", k=k)
    return fused


# ---------------------------------------------------------------- evidence
def check_facts(facts: dict) -> dict:
    """_facts 규율 강제: 부울/수치만 (자기채점 문자열 금지). 위반 시 ValueError."""
    for key, v in facts.items():
        if isinstance(v, bool) or isinstance(v, (int, float)):
            continue
        raise ValueError(f"_facts[{key!r}] must be bool/number (자기채점 금지), got {type(v).__name__}")
    return facts


def evidence_skeleton(experiment: str, node: str, a_priori: dict, prereg: dict,
                      tree: str = TREE) -> dict:
    """evidence JSON 뼈대 — prom_consensus_bench.py L156-184 스키마."""
    return {
        "experiment": experiment,
        "tree": tree,
        "node": node,
        "a_priori": dict(a_priori),
        "prereg": dict(prereg),
    }


def write_evidence(ev: dict, out_path) -> Path:
    """evidence 기록 — _facts 규율 체크 후 indent=2 ensure_ascii=False 로 저장."""
    if "_facts" in ev:
        check_facts(ev["_facts"])
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ev, ensure_ascii=False, indent=2))
    return out


# ---------------------------------------------------------------- smoke
def _smoke():  # pragma: no cover — 수동 스모크 (기본 파라미터, 소형 입력)
    import hashlib
    import sys

    out = {}

    # (1) gold 로드 + split 재현성
    gold = load_gold()
    verify_split(gold)
    splits = [f["split"] for f in gold["findings"]]
    out["n_findings"] = len(gold["findings"])
    out["n_calibration"] = splits.count("calibration")
    out["n_eval"] = splits.count("eval")
    out["n_targets"] = len(gold["target_pool"])
    out["n_distractors"] = len(gold["distractor_pool"])
    out["split_sha256"] = hashlib.sha256(
        json.dumps({f["finding_id"]: f["split"] for f in gold["findings"]},
                   sort_keys=True).encode()
    ).hexdigest()

    # (2) per-finding distractor 샘플 결정론 + frozen 일치
    f0 = gold["findings"][0]
    s1 = sample_distractors(f0["finding_id"], gold["distractor_pool"])
    s2 = sample_distractors(f0["finding_id"], gold["distractor_pool"])
    assert s1 == s2, "sample_distractors nondeterministic"
    assert s1 == sorted(f0["distractor_target_texts"]), "frozen distractor sample drift"

    # (3) lexical 부품
    assert toks("GFS 마스터 元 harness") == {"gfs", "마스터", "元", "harness"}
    r = lexical_rank("chunk replication", [("a", "chunk replication topology"), ("b", "김치찌개 조리법")])
    assert r[0][1] == "a" and r[0][0] > r[1][0]
    assert norm_contains("Single  Master", "single master superseded")
    assert not norm_contains("erasure coding", "김치찌개")

    # (4) mc_null_z (소형 합성)
    z, nm, ns = mc_null_z(1.0, lambda rng: rng.random() * 0.1)
    out["mc_null_smoke_z_pos"] = bool(z > 3.0)

    # (5) rrf_fuse
    fused = rrf_fuse({"arm1": [0.9, 0.1, 0.5], "arm2": [0.8, 0.2, 0.4]})
    assert max(range(3), key=lambda i: fused[i]) == 0

    # (6) calibrate_tau 합성 결정론
    import numpy as np
    rng = np.random.default_rng(SEED)
    fe = rng.normal(size=(4, 8)); fe /= np.linalg.norm(fe, axis=1, keepdims=True)
    ce = rng.normal(size=(6, 8)); ce /= np.linalg.norm(ce, axis=1, keepdims=True)
    mask = np.zeros((4, 6), dtype=bool); mask[0, 0] = True
    t1 = calibrate_tau(fe, ce, mask)
    t2 = calibrate_tau(fe, ce, mask)
    assert t1 == t2, "calibrate_tau nondeterministic on identical input"
    out["tau_synthetic"] = t1[0]

    # (7) 실제 τ (calibration split, 실제 임베딩 — 모델 필요; run_on_gm.sh 경유)
    tau_info = tau_from_gold(gold)
    out["tau"] = tau_info["tau"]
    out["tau_null_mean"] = tau_info["null_mean"]
    out["tau_null_std"] = tau_info["null_std"]
    out["tau_n_null_pairs"] = tau_info["n_null_pairs"]

    # (8) evidence 헬퍼 + _facts 규율
    ev = evidence_skeleton("smoke", "none", {"seed": SEED}, {"metric": "none"})
    ev["_facts"] = {"ok": True}
    check_facts(ev["_facts"])
    try:
        check_facts({"verdict": "PASS"})
        raise AssertionError("check_facts must reject strings")
    except ValueError:
        pass

    digest = hashlib.sha256(
        json.dumps(out, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"SMOKE OK determinism_digest={digest}", file=sys.stderr)


if __name__ == "__main__":
    _smoke()
