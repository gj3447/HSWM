"""T1 rung — do frozen dev-query seeds reach the woven T0 chain entrances?

H3-C0 waterfall published (frozen V5, n=200 per dataset): "legal
claim-continuous second hop" = 0 for MuSiQue and 2Wiki, and the T0 frontier
was empty.  B1 unlocked T0 (MuSiQue 6 / 2Wiki 25 admissible chains, metric
progressive).  This rung asks the next waterfall question with everything
else frozen:

  T1        one of the top-3 frozen cosine seeds is a chain-entrance
            paragraph of an admissible C3 chain;
  T1+T2+T3' the unmodified typed kernel (``compose_typed_scores``, typed
            mode, seed_k=3) reaches a legal depth-two target on the woven
            graph — the exact quantity that was 0/200 on the frozen graph.

Budget discipline: embeddings are read from the frozen V5 development store
(``embeddings.npz``); no model, network, or new embedding call is made.
Gold labels are never consumed — only qid (embedding lookup) and raw
question text (kernel input, as the kernel itself mandates).

Do not run before PREREG_T1_ENTRANCE_REACH_2026-07-22.json records a live
LakatoTree prediction and freezes the hashes this guard checks.
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

HERE = Path(__file__).parent
CACHE = HERE / ".ab_p5_cache" / "h3_b3"
RUN = CACHE / "runs" / "qwen35-r3-schema-v4-20260720" / "development"
JOURNAL = RUN / "extractions.jsonl"
EMBED_NPZ = RUN / "embedding" / "embeddings.npz"
SEGMENTS = {
    "musique": CACHE / "musique_development_v4_segment.json",
    "2wiki": CACHE / "2wiki_development_v4_segment.json",
}
PREREG = HERE / "PREREG_T1_ENTRANCE_REACH_2026-07-22.json"
EVIDENCE = HERE / "EVIDENCE_T1_ENTRANCE_REACH_2026-07-22.json"

FROZEN_MODULES = (
    "chain_viability.py", "claim_weave.py", "t1_entrance_reach.py",
)
SEED_K = 3


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def preregistration_guard() -> dict:
    if not PREREG.exists():
        raise RuntimeError(f"missing preregistration: {PREREG}")
    locked = json.loads(PREREG.read_text(encoding="utf-8"))
    if locked.get("registered_before_measurement") is not True:
        raise RuntimeError("preregistration is not confirmed before measurement")
    if not locked.get("prediction_receipt_sha256"):
        raise RuntimeError("preregistration lacks a prediction receipt")
    for module in FROZEN_MODULES:
        if locked["module_sha256"].get(module) != _sha256_file(HERE / module):
            raise RuntimeError(f"frozen module drift: {module}")
    if locked["embedding_npz_sha256"] != _sha256_file(EMBED_NPZ):
        raise RuntimeError("frozen embedding store drift")
    if locked["journal_sha256"] != _sha256_file(JOURNAL):
        raise RuntimeError("frozen journal drift")
    return locked


def load_embedding_store() -> tuple[dict[str, np.ndarray], dict[tuple[str, str], np.ndarray]]:
    store = np.load(EMBED_NPZ, allow_pickle=True)
    ids = [str(x) for x in store["ids"]]
    kinds = [str(x) for x in store["kinds"]]
    vectors = np.asarray(store["vectors"], dtype=np.float64)
    paragraph_vecs: dict[str, np.ndarray] = {}
    query_vecs: dict[tuple[str, str], np.ndarray] = {}
    for row_id, kind, vec in zip(ids, kinds, vectors):
        if kind == "paragraph":
            # id format: "paragraph:<source_id>"
            paragraph_vecs[row_id.split(":", 1)[1]] = vec
        elif kind == "query":
            # id format: "query:<dataset>:<qid>"
            _, dataset, qid = row_id.split(":", 2)
            query_vecs[(dataset, qid)] = vec
    return paragraph_vecs, query_vecs


def main() -> int:
    locked = preregistration_guard()
    paragraph_vecs, query_vecs = load_embedding_store()

    segments = {name: fz.load_prepared_segment(path)
                for name, path in SEGMENTS.items()}
    artifact = fz.load_extraction_artifact(JOURNAL, tuple(segments.values()))
    frozen_by_source = artifact.frozen_by_source

    policy = typed.TypedCompositionPolicyV1(seed_k=SEED_K)
    measurement: dict[str, dict] = {}
    for name in sorted(segments):
        segment = segments[name]
        paragraphs = fz._paragraph_inputs(segment)
        frozen = tuple(frozen_by_source[p.source_id] for p in paragraphs)
        build = cb.compile_claim_graph(paragraphs, frozen)
        if cb.verify_claim_graph(build):
            raise RuntimeError(f"{name}: claim graph verification failed")
        base = typed.graph_from_claim_build(build)
        titles = {p.source_id: p.title for p in paragraphs}
        woven = apply_weave(base, [
            weave_c1(build, titles, base),
            weave_c2(build, titles, base),
            weave_c3(build, titles, base),
        ])

        arms = {"C0": typed.make_typed_graph(
                    base.target_ids,
                    tuple(sorted(base.arcs, key=lambda a: a.arc_id))),
                "C3": woven}
        entrances = {
            arm: sorted({c.source_target
                         for c in enumerate_admissible_chains(g).chains})
            for arm, g in arms.items()
        }

        ordinal_vecs = np.stack([paragraph_vecs[sid] for sid in base.target_ids])
        rows = [r for r in segment.evaluation_rows
                if (name, r.qid) in query_vecs]
        if len(rows) != len(segment.evaluation_rows):
            raise RuntimeError(f"{name}: missing frozen query embeddings")
        rows.sort(key=lambda r: r.qid)

        arm_rows: dict[str, dict] = {}
        for arm, graph in arms.items():
            entrance_set = set(entrances[arm])
            t1_hits = 0
            kernel_depth2 = 0
            for row in rows:
                scores = ordinal_vecs @ query_vecs[(name, row.qid)]
                top = np.argsort(-scores, kind="stable")[:SEED_K]
                if entrance_set.intersection(int(i) for i in top):
                    t1_hits += 1
                _, _, receipt = typed.compose_typed_scores(
                    row.question, scores, graph, policy, mode="typed")
                if receipt.first_reachable_at_depth_2 > 0:
                    kernel_depth2 += 1
            arm_rows[arm] = {
                "entrance_paragraphs": len(entrance_set),
                "queries": len(rows),
                "t1_seed_reaches_entrance": t1_hits,
                "kernel_legal_depth2_queries": kernel_depth2,
            }
        measurement[name] = arm_rows

    t1_min = min(m["C3"]["t1_seed_reaches_entrance"] for m in measurement.values())
    depth2_min = min(m["C3"]["kernel_legal_depth2_queries"]
                     for m in measurement.values())

    evidence = {
        "schema": "hswm-t1-entrance-reach-evidence/v1",
        "programme": "LakatosTree_PromSearchHSWM_20260721",
        "branch": "T1-entrance-reach-c3",
        "preregistration": {
            "path": PREREG.name,
            "sha256": _sha256_file(PREREG),
            "prediction_receipt_sha256": locked["prediction_receipt_sha256"],
        },
        "measurement": {
            "metric": "min_over_datasets_c3_t1_seed_reaches_entrance",
            "value": t1_min,
            "novel_metric": "min_over_datasets_c3_kernel_legal_depth2_queries",
            "novel_value": depth2_min,
            "published_frozen_baseline": {
                "kernel_legal_second_hop": {"musique": 0, "2wiki": 0},
                "source": "H3_C0_CHAIN_VIABILITY_DIAGNOSIS_2026-07-20.md gate waterfall (n=200)",
            },
            "per_dataset": measurement,
            "policy": {"seed_k": SEED_K, "mode": "typed",
                       "kernel": "compose_typed_scores (unmodified)"},
        },
        "budget": {"llm_calls": 0, "network_calls": 0,
                   "new_embedding_calls": 0,
                   "note": "frozen V5 development embedding store reused"},
        "gold_labels_consumed": False,
        "limitations": [
            "Development split, frozen top-3 cosine seeds; certificate halves untouched.",
            "kernel_legal_depth2 conflates T1+T2+structural T3 reachability; the K2-vs-K1 score-digest change and second-edge null (full T3) remain a separate rung.",
            "No retrieval-quality claim: reaching a legal second hop says nothing yet about answering queries better.",
        ],
    }
    EVIDENCE.write_text(json.dumps(evidence, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(json.dumps({
        "evidence": str(EVIDENCE),
        "evidence_sha256": _sha256_file(EVIDENCE),
        "t1_min": t1_min,
        "kernel_depth2_min": depth2_min,
        "per_dataset": {
            name: {arm: row for arm, row in arms.items()}
            for name, arms in measurement.items()
        },
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
