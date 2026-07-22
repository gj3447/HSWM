"""R2 — ML-material 위 max-product 걷기 재판 (PROM-8 R2, USER "연산>절약" 정전).

R1 판정: t1은 seed로 살았으나 min depth-2는 0 (kill#2 — 재료/판 문제).
R2는 그 재료를 진짜로 바꾼다: ReFinED QID + fastcoref 전파(claim_weave_ml)로
identity arc를 짜서 결정론 woven 그래프 위에 layering, R1 최강 설정(A4:
alias+soft+hippo seed)을 고정한 채 그래프만 A/B.

  A4_r1_full   결정론 woven (재현 통제 — R1 영수증과 일치해야 함)
  A5_ml_full   결정론 woven + ML weave (이번 판의 treatment)

측정: T0 admissible chains / t1 entrance / kernel-legal depth-2 (같은 워커).
walker·seed·alias·soft 로직은 r1_t1_retry에서 그대로 import — R2가 바꾸는 건
오직 그래프 재료다 (단일 변수).

예산: build-time 추출은 이미 완료된 receipt(r2_material/*.json)를 읽기만.
query-time LLM/network 0. gold 무소비.

Do not run before PREREG_R2_ML_WALK_2026-07-22.json records a live prediction.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import numpy as np

import claim_builder as cb
import h3_b3_falsifier as fz
import typed_composition as typed
from chain_viability import enumerate_admissible_chains
from claim_weave import apply_weave, weave_c1, weave_c2, weave_c3
from claim_weave_ml import load_material, weave_ml
from r1_predicate_alias import (
    build_predicate_alias_index, query_term_closure, _norm_words,
)
from r1_t1_retry import (
    EMBED_NPZ, JOURNAL, SEED_K, SEGMENTS,
    load_embedding_store, select_seeds, walk_depth2,
)

HERE = Path(__file__).parent
PREREG = HERE / "PREREG_R2_ML_WALK_2026-07-22.json"
EVIDENCE = HERE / "EVIDENCE_R2_ML_WALK_2026-07-22.json"
MATERIAL = {
    ds: {phase: HERE / ".ab_p5_cache" / "r2_material" / f"{ds}_{phase}.json"
         for phase in ("link", "coref")}
    for ds in ("musique", "2wiki")
}
FROZEN_MODULES = (
    "chain_viability.py", "claim_weave.py", "claim_weave_ml.py",
    "r1_predicate_alias.py", "r1_t1_retry.py", "r2_ml_walk.py",
)


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def preregistration_guard() -> dict:
    if not PREREG.exists():
        raise RuntimeError(f"missing preregistration: {PREREG}")
    locked = json.loads(PREREG.read_text(encoding="utf-8"))
    if locked.get("registered_before_measurement") is not True:
        raise RuntimeError("preregistration not confirmed before measurement")
    if not locked.get("prediction_receipt_sha256"):
        raise RuntimeError("preregistration lacks a prediction receipt")
    for module in FROZEN_MODULES:
        if locked["module_sha256"].get(module) != _sha(HERE / module):
            raise RuntimeError(f"frozen module drift: {module}")
    for ds, phases in MATERIAL.items():
        for phase, path in phases.items():
            if locked["material_sha256"][f"{ds}_{phase}"] != _sha(path):
                raise RuntimeError(f"frozen material drift: {ds}_{phase}")
    if locked["embedding_npz_sha256"] != _sha(EMBED_NPZ):
        raise RuntimeError("frozen embedding store drift")
    if locked["journal_sha256"] != _sha(JOURNAL):
        raise RuntimeError("frozen journal drift")
    return locked


def main() -> int:
    locked = preregistration_guard()
    paragraph_vecs, query_vecs = load_embedding_store()
    segments = {n: fz.load_prepared_segment(p) for n, p in SEGMENTS.items()}
    artifact = fz.load_extraction_artifact(JOURNAL, tuple(segments.values()))
    policy = typed.TypedCompositionPolicyV1(seed_k=SEED_K)
    min_match = float(policy.min_typed_match)

    prepared: dict[str, dict] = {}
    all_preds: list[str] = []
    ml_stats: dict[str, dict] = {}
    for name in sorted(segments):
        segment = segments[name]
        paragraphs = fz._paragraph_inputs(segment)
        frozen = tuple(artifact.frozen_by_source[p.source_id] for p in paragraphs)
        build = cb.compile_claim_graph(paragraphs, frozen)
        if cb.verify_claim_graph(build):
            raise RuntimeError(f"{name}: claim graph verification failed")
        base = typed.graph_from_claim_build(build)
        titles = {p.source_id: p.title for p in paragraphs}

        det = apply_weave(base, [
            weave_c1(build, titles, base),
            weave_c2(build, titles, base),
            weave_c3(build, titles, base),
        ])
        link_by, coref_by = load_material(name)
        ml, stats = weave_ml(build, base, link_by, coref_by)
        full = apply_weave(det, [ml])
        ml_stats[name] = {
            "ml_arcs": len(ml.arcs),
            "paragraphs_sha_mismatch": stats.paragraphs_sha_mismatch,
            "clusters_conflicted": stats.clusters_conflicted,
            "qids_fan_capped": stats.qids_fan_capped,
            "roles_resolved_direct": stats.roles_resolved_direct,
            "roles_resolved_coref": stats.roles_resolved_coref,
        }

        graphs = {"A4_r1_full": det, "A5_ml_full": full}
        chains = {arm: enumerate_admissible_chains(g) for arm, g in graphs.items()}
        for g in graphs.values():
            for arc in g.arcs:
                all_preds.append(arc.source_predicate.exact)
                if arc.target_predicate is not None:
                    all_preds.append(arc.target_predicate.exact)

        ordinal_vecs = np.stack([paragraph_vecs[sid] for sid in base.target_ids])
        rows = [r for r in segment.evaluation_rows if (name, r.qid) in query_vecs]
        if len(rows) != len(segment.evaluation_rows):
            raise RuntimeError(f"{name}: missing frozen query embeddings")
        rows.sort(key=lambda r: r.qid)
        prepared[name] = {
            "graphs": graphs, "chains": chains, "titles": titles,
            "ordinal_vecs": ordinal_vecs, "rows": rows,
        }

    alias_index = build_predicate_alias_index(all_preds)

    per_dataset: dict[str, dict] = {}
    for name, pack in prepared.items():
        arm_rows: dict[str, dict] = {}
        for arm_name, graph in pack["graphs"].items():
            ledger = pack["chains"][arm_name]
            entrance_set = {c.source_target for c in ledger.chains}
            t1_hits = depth2_hits = depth2_targets_sum = 0
            for row in pack["rows"]:
                scores = pack["ordinal_vecs"] @ query_vecs[(name, row.qid)]
                q_terms = query_term_closure(row.question)
                seeds = select_seeds(scores, q_terms, graph, pack["titles"],
                                     hippo=True, k=SEED_K)
                if entrance_set.intersection(seeds):
                    t1_hits += 1
                reached, n_t = walk_depth2(
                    q_terms, scores, graph, policy, seeds=seeds,
                    soft_gate=True, use_alias=True, alias_index=alias_index,
                    min_typed_match=min_match,
                )
                if reached:
                    depth2_hits += 1
                    depth2_targets_sum += n_t
            arm_rows[arm_name] = {
                "t0_admissible_chains": ledger.admissible_chain_count,
                "entrance_paragraphs": len(entrance_set),
                "queries": len(pack["rows"]),
                "t1_seed_reaches_entrance": t1_hits,
                "kernel_legal_depth2_queries": depth2_hits,
                "depth2_targets_sum": depth2_targets_sum,
            }
        per_dataset[name] = arm_rows

    def _min(arm: str, key: str) -> int:
        return min(per_dataset[d][arm][key] for d in per_dataset)

    primary = _min("A5_ml_full", "kernel_legal_depth2_queries")
    novel = sum(
        per_dataset[d]["A5_ml_full"]["kernel_legal_depth2_queries"]
        - per_dataset[d]["A4_r1_full"]["kernel_legal_depth2_queries"]
        for d in per_dataset
    )

    evidence = {
        "schema": "hswm-r2-ml-walk-evidence/v1",
        "programme": "LakatosTree_PromSearchHSWM_20260721",
        "branch": "R2-ml-material-walk",
        "preregistration": {
            "path": PREREG.name, "sha256": _sha(PREREG),
            "prediction_receipt_sha256": locked["prediction_receipt_sha256"],
        },
        "measurement": {
            "metric": "min_over_datasets_A5_kernel_legal_depth2_queries",
            "value": primary,
            "novel_metric": "sum_A5_minus_A4_kernel_legal_depth2_queries",
            "novel_value": novel,
            "per_dataset": per_dataset,
            "ml_weave_stats": ml_stats,
            "config": {"walker": "r1_t1_retry.walk_depth2 (unchanged)",
                       "arm_fixed": "alias+soft+hippo seed (R1 A4)",
                       "single_variable": "graph material only"},
        },
        "budget": {"query_time_llm": 0, "network": 0, "new_embedding": 0,
                   "build_time_models": "ReFinED wikipedia_model_with_numbers + fastcoref FCoref (attestation in r2_material receipts)"},
        "gold_labels_consumed": False,
        "limitations": [
            "Same dev substrate as R1/T1 — the C4 regime critique (dense/small pool) still applies; a full-pool trial is R3, not this.",
            "ML lane here is build-time only; HippoRAG2-style query-time LLM filter not used.",
            "No retrieval-quality claim; waterfall structural metrics only.",
        ],
    }
    EVIDENCE.write_text(json.dumps(evidence, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(json.dumps({
        "evidence": str(EVIDENCE), "evidence_sha256": _sha(EVIDENCE),
        "primary_min_A5_depth2": primary, "novel_A5_minus_A4_depth2": novel,
        "per_dataset": {d: {a: {k: v for k, v in r.items() if k != "queries"}
                            for a, r in arms.items()}
                        for d, arms in per_dataset.items()},
        "ml_stats": ml_stats,
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
