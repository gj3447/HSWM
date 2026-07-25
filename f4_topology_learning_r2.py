"""F4-r2 gate (learned topology rewiring) — anchor-adjacency redesign.

PREREG (locked, read-only input): prom_search_hswm/evidence/
PREREG_f4_topology_learning_20260725.json (in the SYMPOSIUM/HSWM checkout).
This file supersedes the r1 frame (f4_topology_learning.py, smoke receipt
f4_topology_learning_smoke_1784986779.json): r1 showed lesson-to-lesson
topology changes contexts but the answerer is insensitive to neighbour
identity (all 4 arms bit-identical on fresh).  The r2 redesign is recorded
as a prereg-reading deviation in every receipt.

r2 design (parent-ratified 2026-07-25):
  edges       bipartite (class-tag anchor ↔ lesson) adjacency.  A fresh
              case's documents carry [SOURCE_CLASS=X] tags; those anchors
              activate the adjacent lessons.  Topology therefore governs
              whether the valid lesson is REACHED at all — in null
              topologies it is usually unreachable, which is the F2-proven
              deletion channel (no valid lesson in context => ~base
              accuracy).  W stays frozen: lesson content is compiled once
              and never edited; only the edge set varies across arms.
  learner     Hebbian, deliberately simple: per train case of world w,
              acc({lesson w}) - acc(none) > 0  =>  +1 to both anchor edges
              (trusted↔w, distractor↔w).  Keep edges with W>0.
  retrieval   activation[l] = #edges from the case's active anchors;
              context = top-k activated lessons (ties by lesson_id),
              possibly empty.  Weights/budget/seed/render identical across
              arms; ONLY the edge set differs.
  arms        A learned / B bipartite degree-preserving shuffle
              (hswm_null_battery.bipartite_degree_preserving_shuffle —
              anchors fixed, lesson side bijected) / C clique bipartite /
              D |E|-matched random sparse bipartite.
  curve/rho   ablation unit = anchor-pair (both anchor edges of a lesson,
              parent decision (a) 2026-07-25 — per-edge LOO is flat under
              dual-anchor redundancy): LOO importance for top-M units,
              top-k removal curve vs random removal (AUC gap, paired
              bootstrap CI), checkpoint edit-distance vs |delta acc|
              Spearman rho (bootstrap CI).  kills f4_k1/k2/k3 unchanged.

Smoke MUST answer: do fresh correctness vectors actually differ across
topologies (the r1 death condition)?  The receipt carries a
topology_divergence section with per-arm-pair differing-case counts.

Usage:
  .venv/bin/python f4_topology_learning_r2.py --smoke
  .venv/bin/python f4_topology_learning_r2.py --universes-dir _research/f2_sealed_universes
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

f2 = importlib.import_module("f2_delta_w_credit")
f4r1 = importlib.import_module("f4_topology_learning")

NULL_BATTERY_DIR = Path("/Users/lagyeongjun/CD/SYMPOSIUM/HSWM/prom_search_hswm")
sys.path.insert(0, str(NULL_BATTERY_DIR))
from hswm_null_battery import (  # noqa: E402
    bipartite_degree_preserving_shuffle,
    headroom_band_ok,
)

PREREG_PATH = NULL_BATTERY_DIR / "evidence" / "PREREG_f4_topology_learning_20260725.json"
RECEIPT_DIR = HERE / "receipts"
HEADROOM_BAND = (0.3, 0.7)


class F4R2Error(RuntimeError):
    pass


# ---------------------------------------------------------------- worlds
def make_worlds(n_lessons: int) -> list[dict]:
    return [{
        "world_idx": i, "group": 0,
        "trusted": f"C{i + 1:02d}", "distractor": f"Q{i + 1:02d}",
        "orientation": "correct",
    } for i in range(n_lessons)]


# ---------------------------------------------------------------- learning
def learn_anchor_edges(answerer, answer_model: str, train_cases, lessons,
                       parallel: int, seed: int, checkpoint_at: set[int]):
    """Hebbian anchor↔lesson edges from the training trajectory."""
    weights: dict[tuple[str, str], int] = {}
    checkpoints: list[dict] = []
    by_id = f4r1.lessons_by_id(lessons)

    def kept():
        return {pair for pair, w in weights.items() if w > 0}

    for case_idx, item in enumerate(train_cases):
        case, w, _q, _u = item
        lid = lessons[w].lesson_id
        units = [((lid,), item), ((), item)]
        rows = f4r1.eval_units(answerer, answer_model, units, by_id,
                               parallel, seed)
        acc_with, acc_without = rows[0]["correct"], rows[1]["correct"]
        if acc_with - acc_without > 0:
            for anchor in (case.trusted_class, case.distractor_class):
                weights[(anchor, lid)] = weights.get((anchor, lid), 0) + 1
        if case_idx + 1 in checkpoint_at:
            checkpoints.append({
                "after_case": case_idx + 1,
                "edges": sorted(kept()),
            })
    return weights, kept(), checkpoints


# ---------------------------------------------------------------- retrieval
def context_for(case, edges: set, k_context: int) -> tuple:
    """Anchor-activation retrieval: the case's class tags activate lessons."""
    active = {case.trusted_class, case.distractor_class}
    activation: dict[str, int] = {}
    for anchor, lid in edges:
        if anchor in active:
            activation[lid] = activation.get(lid, 0) + 1
    ranked = sorted(activation, key=lambda lid: (-activation[lid], lid))
    return tuple(sorted(ranked[:k_context]))


def eval_topology(answerer, answer_model: str, edges, cases, k_context: int,
                  parallel: int, seed: int, by_id: dict):
    units = [(context_for(item[0], edges, k_context), item) for item in cases]
    rows = f4r1.eval_units(answerer, answer_model, units, by_id, parallel, seed)
    n = len(rows)
    return {
        "accuracy": sum(r["correct"] for r in rows) / n,
        "parse_failures": sum(1 for r in rows if not r["parse_ok"]),
        "correct_vector": [r["correct"] for r in rows],
        "empty_contexts": sum(1 for u, _i in units if not u),
    }


def clique_bipartite(anchors: list[str], lesson_ids: list[str]) -> set:
    return {(a, l) for a in anchors for l in lesson_ids}


def random_sparse_bipartite(anchors: list[str], lesson_ids: list[str],
                            count: int, seed: str) -> set:
    rng = random.Random(seed)
    universe = sorted(clique_bipartite(anchors, lesson_ids))
    return set(rng.sample(universe, min(count, len(universe))))


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lessons", type=int, default=30)
    ap.add_argument("--n-fresh", type=int, default=50)
    ap.add_argument("--k-context", type=int, default=4)
    ap.add_argument("--loo-m", type=int, default=30,
                    help="max fresh-covering units that get LOO-measured importance")
    ap.add_argument("--curve-k", type=int, default=10)
    ap.add_argument("--checkpoints", type=int, default=4)
    ap.add_argument("--split-seed", type=int, default=20260726)
    ap.add_argument("--seed", type=int, default=20260725)
    ap.add_argument("--max-answers", type=int, default=1)
    ap.add_argument("--max-calls", type=int, default=4000)
    ap.add_argument("--parallel", type=int, default=16)
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--universes-dir", type=Path,
                    default=HERE / "_research" / "f2_sealed_universes")
    ap.add_argument("--answer-backend", choices=("ollama", "vllm"), default="vllm")
    ap.add_argument("--answer-url", default="http://127.0.0.1:18000/v1")
    ap.add_argument("--answer-model", default="qwen3.6-27b")
    ap.add_argument("--skip-base", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    if args.smoke:
        args.lessons = 12
        args.n_fresh = 6
        args.k_context = 2
        args.loo_m = 6
        args.curve_k = 1
        args.checkpoints = 1
        args.max_calls = 100
        args.skip_base = True
    t0 = time.time()
    ts = int(t0)
    out_path = Path(args.out) if args.out else (
        RECEIPT_DIR / f"f4_topology_learning_r2_{'smoke' if args.smoke else 'sealed'}_{ts}.json")

    receipt = {
        "schema_version": "hswm-f4-topology-learning-r2-receipt/v1",
        "mode": "development",
        "branch": "F4-topology-learning",
        "smoke": bool(args.smoke),
        "preregistration_file": str(PREREG_PATH),
        "preregistration_file_sha256": hashlib.sha256(
            PREREG_PATH.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "harness_module_sha256": {
            "f2_delta_w_credit.py": hashlib.sha256(
                (HERE / "f2_delta_w_credit.py").read_bytes()).hexdigest(),
            "f4_topology_learning.py": hashlib.sha256(
                (HERE / "f4_topology_learning.py").read_bytes()).hexdigest(),
            "hswm_null_battery.py": hashlib.sha256(
                (NULL_BATTERY_DIR / "hswm_null_battery.py").read_bytes()).hexdigest(),
        },
        "prereg_reading_deviation": (
            "r2 redesign (parent-ratified 2026-07-25): edges are bipartite "
            "class-tag-anchor↔lesson adjacency instead of lesson↔lesson "
            "hyperedges (r1 smoke f4_topology_learning_smoke_1784986779.json: "
            "contexts changed, answers never did).  Amendment (parent decision "
            "2026-07-25, option (a)): the ablation/LOO unit is the ANCHOR-PAIR "
            "of a lesson, not a single edge (per-edge LOO is structurally flat "
            "under dual-anchor redundancy).  Arms/metrics/kills are unchanged "
            "from the prereg."),
        "config": vars(args) | {"out": str(out_path),
                                "universes_dir": str(args.universes_dir)},
        "answerer_freeze": {
            "backend": args.answer_backend, "url": args.answer_url,
            "model": args.answer_model,
            "note": "same freeze as the F2 sealed run (vLLM qwen3.6-27b, "
                    "thinking off; p1v4 lineage model not served on this host)",
        },
        "honesty": "grounded measurement only; no scientific claim; judgment is the gate's",
    }
    budget = f2.Budget(args.max_calls)
    if args.answer_backend == "vllm":
        answerer = f2.CachedOpenAIChat(args.answer_url, budget)
    else:
        answerer = f2.CachedChat(args.answer_url, budget)
    aborted = None
    try:
        worlds = make_worlds(args.lessons)
        pool, pool_stats = f2.load_question_pool(args.universes_dir, args.max_answers)
        receipt["question_pool"] = pool_stats
        article_cache = f2._ArticleCache(args.universes_dir)
        built = f4r1.build_splits(pool, article_cache, worlds=worlds,
                                  n_fresh=args.n_fresh,
                                  max_answers=args.max_answers,
                                  split_seed=args.split_seed)
        train_cases = built["splits"]["train"]
        fresh_cases = built["splits"]["fresh"]
        receipt["splits"] = {
            "n_train": len(train_cases), "n_fresh": len(fresh_cases),
            "skipped": built["skipped"], "split_seed": args.split_seed,
            "fresh_case_worlds": [w for _c, w, _q, _u in fresh_cases],
        }
        receipt["leakage"] = f2.leakage_report(train_cases, [], fresh_cases)
        lessons, lesson_meta = f4r1.compile_lessons(train_cases, worlds)
        by_id = f4r1.lessons_by_id(lessons)
        lesson_ids = sorted(by_id)
        anchors = sorted({w["trusted"] for w in worlds}
                         | {w["distractor"] for w in worlds})
        receipt["lessons"] = {str(w): {k: v for k, v in lesson_meta[w].items()
                                       if k != "training_transcript_sha256"}
                              for w in sorted(lesson_meta)}

        # ---- base (headroom) ----
        if not args.skip_base:
            base = f2.evaluate_subset(answerer, args.answer_model, (), fresh_cases,
                                      by_id, args.parallel, args.seed)
            receipt["fresh_base_accuracy"] = base["accuracy"]
            receipt["headroom_band"] = list(HEADROOM_BAND)
            receipt["headroom_band_ok"] = headroom_band_ok(
                base["accuracy"], *HEADROOM_BAND)
            receipt["headroom_assessment"] = (
                "floor (not saturation), parent decision 2026-07-25: F4's "
                "operative contrast is the null topologies (B/C/D), not the "
                "no-memory base; base << A is the deletion channel's "
                "precondition.  A band violation here records a floor, it "
                "does not void the arm comparison.")
        else:
            receipt["fresh_base_accuracy"] = None
            receipt["headroom_note"] = (
                "base eval skipped (--skip-base); the identical fresh split "
                "was measured at 0.0 in receipts "
                "f4_topology_learning_r2_smoke_1784988076.json and "
                "f4_topology_learning_r2_smoke_1784988931.json "
                "(floor, not saturation — see headroom_assessment there).")

        # ---- learn anchor edges ----
        n_cases = len(train_cases)
        checkpoint_at = {
            max(1, round(n_cases * (i + 1) / (args.checkpoints + 1)))
            for i in range(args.checkpoints)}
        weights, e_learned, checkpoints = learn_anchor_edges(
            answerer, args.answer_model, train_cases, lessons,
            args.parallel, args.seed, checkpoint_at)
        worlds_with_edge = sorted({lessons_idx for lessons_idx in range(args.lessons)
                                   if any(l == lessons[lessons_idx].lesson_id
                                          for _a, l in e_learned)})
        receipt["learning"] = {
            "edges_tested_note": "2 anchors per contributing train case",
            "edges_kept": len(e_learned),
            "worlds_with_valid_edge": worlds_with_edge,
            "edge_weights": {f"{a}->{l[:12]}": w for (a, l), w in sorted(weights.items())},
            "checkpoints": [{"after_case": c["after_case"],
                             "n_edges": len(c["edges"])} for c in checkpoints],
        }

        # ---- arms ----
        edge_sets = {
            "A_learned": set(e_learned),
            "B_shuffled": set(bipartite_degree_preserving_shuffle(
                sorted(e_learned), lesson_ids, f"f4r2-shuffle-{args.seed}")),
            "C_clique": clique_bipartite(anchors, lesson_ids),
            "D_random_sparse": random_sparse_bipartite(
                anchors, lesson_ids, len(e_learned), f"f4r2-randsparse-{args.seed}"),
        }
        arms = {}
        for arm_id, edges in edge_sets.items():
            res = eval_topology(answerer, args.answer_model, edges, fresh_cases,
                                args.k_context, args.parallel, args.seed, by_id)
            arms[arm_id] = {
                "n_edges": len(edges),
                "fresh_accuracy": res["accuracy"],
                "fresh_parse_failures": res["parse_failures"],
                "empty_contexts": res["empty_contexts"],
                "correct_vector": res["correct_vector"],
            }
        receipt["arms"] = {
            k: {kk: vv for kk, vv in v.items() if kk != "correct_vector"}
            for k, v in arms.items()}

        # ---- topology divergence (r2 smoke survival check) ----
        names = list(arms)
        divergence = {}
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                va = arms[names[i]]["correct_vector"]
                vb = arms[names[j]]["correct_vector"]
                diff = [idx for idx in range(len(va)) if va[idx] != vb[idx]]
                divergence[f"{names[i]}_vs_{names[j]}"] = {
                    "n_differing_cases": len(diff),
                    "differing_fresh_worlds": [fresh_cases[idx][1] for idx in diff][:10],
                }
        receipt["topology_divergence"] = divergence

        # ---- edge ablation causal curve (anchor-pair units, parent decision (a)) ----
        acc_a = arms["A_learned"]["fresh_accuracy"]
        units_by_lesson: dict[str, set] = {}
        for _a, _l in e_learned:
            units_by_lesson.setdefault(_l, set()).add((_a, _l))
        lid2world = {lessons[w].lesson_id: w for w in lessons}
        fresh_world_set = {w for _c, w, _q, _u in fresh_cases}
        # Units whose lesson cannot fire on any fresh case (anchor-gated
        # retrieval) have provably-zero fresh impact; LOO is measured only on
        # fresh-covering units (exact, not a shortcut), ranked by learned weight.
        candidates = sorted(
            (l for l in units_by_lesson if lid2world[l] in fresh_world_set),
            key=lambda l: (-sum(weights[e] for e in units_by_lesson[l]), l))
        loo_units = candidates[:args.loo_m]
        importance = {}
        for l in loo_units:
            res = eval_topology(answerer, args.answer_model,
                                e_learned - units_by_lesson[l], fresh_cases,
                                args.k_context, args.parallel, args.seed, by_id)
            importance[l] = acc_a - res["accuracy"]
        removal_order = (
            sorted(loo_units, key=lambda l: (-importance[l], l))
            + [l for l in candidates if l not in loo_units]
            + sorted((l for l in units_by_lesson if l not in candidates),
                     key=lambda l: (-sum(weights[e] for e in units_by_lesson[l]), l)))
        rng = random.Random(f"f4r2-curve-{args.seed}")
        random_order = sorted(units_by_lesson)  # hash-order-independent (replay determinism)
        rng.shuffle(random_order)
        k_steps = min(args.curve_k, len(removal_order))
        curve_top, curve_rand = [], []
        for k in range(1, k_steps + 1):
            drop_t = set().union(*(units_by_lesson[l] for l in removal_order[:k]))
            drop_r = set().union(*(units_by_lesson[l] for l in random_order[:k]))
            curve_top.append(eval_topology(
                answerer, args.answer_model, e_learned - drop_t,
                fresh_cases, args.k_context, args.parallel, args.seed, by_id))
            curve_rand.append(eval_topology(
                answerer, args.answer_model, e_learned - drop_r,
                fresh_cases, args.k_context, args.parallel, args.seed, by_id))
        if k_steps >= 1:
            gap_per_k = [r["accuracy"] - t["accuracy"]
                         for r, t in zip(curve_rand, curve_top)]
            auc_gap = sum(gap_per_k) / len(gap_per_k)
            per_case_gaps = []
            for t, r in zip(curve_top, curve_rand):
                per_case_gaps.append([r_ - t_ for t_, r_ in zip(
                    t["correct_vector"], r["correct_vector"])])
            flat_gaps = [g for per_k in per_case_gaps for g in per_k]
            gap_ci = f4r1.paired_bootstrap_gap(
                flat_gaps, [0] * len(flat_gaps),
                n_boot=args.n_boot, seed=args.seed + 1)
        else:
            auc_gap, gap_ci = None, {"mean": None, "ci95": [None, None]}
        receipt["causal_curve"] = {
            "removal_unit": "anchor_pair",
            "unit_deviation_note": (
                "prereg reading deviation #2 (parent decision 2026-07-25, option "
                "(a)): LOO importance and the removal curve are computed per "
                "ANCHOR-PAIR unit (both anchor edges of a lesson removed "
                "together), not per single edge.  Per-edge LOO is structurally "
                "flat because the two anchors are redundant reachability paths "
                "(r2 smoke: per-edge LOO = 0.0 on all top edges).  Learner "
                "unchanged; only the ablation unit moved."),
            "k_steps": k_steps,
            "loo_candidate_units": len(candidates),
            "loo_measured_units": {l[:12]: round(importance[l], 4) for l in loo_units},
            "curve_top_acc": [round(r["accuracy"], 4) for r in curve_top],
            "curve_rand_acc": [round(r["accuracy"], 4) for r in curve_rand],
            "auc_gap": (round(auc_gap, 4) if auc_gap is not None else None),
            "auc_gap_ci95": gap_ci["ci95"],
        }

        # ---- structure-performance correlation ----
        topo_points = [{"tag": f"ckpt_{c['after_case']}", "edges": set(c["edges"])}
                       for c in checkpoints]
        topo_points.append({"tag": "final", "edges": set(e_learned)})
        topo_accs = {}
        for tp in topo_points:
            if tp["tag"] == "final":
                topo_accs[tp["tag"]] = acc_a
            else:
                topo_accs[tp["tag"]] = eval_topology(
                    answerer, args.answer_model, tp["edges"], fresh_cases,
                    args.k_context, args.parallel, args.seed, by_id)["accuracy"]
        corr_points = []
        for i in range(len(topo_points)):
            for j in range(i + 1, len(topo_points)):
                edit = len(topo_points[i]["edges"] ^ topo_points[j]["edges"])
                delta = abs(topo_accs[topo_points[i]["tag"]]
                            - topo_accs[topo_points[j]["tag"]])
                corr_points.append((edit, delta))
        rho = f2.spearman([p[0] for p in corr_points],
                          [p[1] for p in corr_points]) if len(corr_points) >= 2 else None
        rho_boot = f4r1.bootstrap_spearman_ci(
            corr_points, n_boot=args.n_boot, seed=args.seed) if corr_points else {
                "ci95": [None, None]}
        receipt["structure_performance"] = {
            "checkpoint_accuracies": topo_accs,
            "points": corr_points,
            "spearman_rho": (round(rho, 4) if rho is not None else None),
            "rho_ci95": rho_boot["ci95"],
        }

        # ---- kill observations ----
        controls = {k: v for k, v in arms.items() if k != "A_learned"}
        best_control = max(controls, key=lambda k: controls[k]["fresh_accuracy"])
        control_gaps = {}
        for name, arm in controls.items():
            gap = f4r1.paired_bootstrap_gap(arms["A_learned"]["correct_vector"],
                                            arm["correct_vector"],
                                            n_boot=args.n_boot, seed=args.seed)
            control_gaps[name] = {"a_minus_x": round(
                arms["A_learned"]["fresh_accuracy"] - arm["fresh_accuracy"], 4),
                "ci95": [round(x, 4) for x in gap["ci95"]]}
        k1 = any(arm["fresh_accuracy"] >= acc_a for arm in controls.values())
        k2 = (gap_ci["ci95"][0] is not None and gap_ci["ci95"][1] is not None
              and gap_ci["ci95"][0] <= 0 <= gap_ci["ci95"][1])
        k3 = (rho_boot["ci95"][0] is not None and rho_boot["ci95"][1] is not None
              and rho_boot["ci95"][0] <= 0 <= rho_boot["ci95"][1])
        receipt["kill_condition_observations"] = {
            "f4_k1_any_control_catches_a": k1,
            "f4_k2_auc_gap_ci_includes_0": k2,
            "f4_k3_rho_ci_includes_0": k3,
            "values": {
                "learned_minus_best_control": round(
                    acc_a - controls[best_control]["fresh_accuracy"], 4),
                "best_control": best_control,
                "control_gaps": control_gaps,
                "auc_gap": receipt["causal_curve"]["auc_gap"],
                "rho": receipt["structure_performance"]["spearman_rho"],
            },
            "note": "mechanical observation only; sealed judgment belongs to the gate",
        }
    except (F4R2Error, f2.BudgetExceeded) as err:
        aborted = str(err)
    except Exception as err:  # noqa: BLE001 - record failure honestly
        aborted = f"{type(err).__name__}: {err}"

    receipt["llm_budget"] = {
        "max_calls": args.max_calls, "used": budget.used,
        "answerer": {"backend": args.answer_backend, "url": args.answer_url,
                     "model": args.answer_model,
                     "misses": answerer.misses, "hits": answerer.hits,
                     "degraded_to_parallel": answerer.degraded_to_parallel},
        "total_logical": answerer.misses + answerer.hits,
    }
    receipt["aborted"] = aborted
    receipt["wall_clock_s"] = round(time.time() - t0, 1)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=1, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(json.dumps({
        "receipt": str(out_path), "aborted": aborted,
        "calls": receipt["llm_budget"], "wall_clock_s": receipt["wall_clock_s"],
        "leakage_binding": receipt.get("leakage", {}).get("binding_leakage"),
        "arms": {k: {kk: vv for kk, vv in v.items()
                     if kk in ("fresh_accuracy", "n_edges", "empty_contexts",
                               "fresh_parse_failures")}
                 for k, v in receipt.get("arms", {}).items()},
        "divergence": receipt.get("topology_divergence"),
        "auc_gap": receipt.get("causal_curve", {}).get("auc_gap"),
        "rho": receipt.get("structure_performance", {}).get("spearman_rho"),
        "kill": receipt.get("kill_condition_observations"),
    }, indent=1, ensure_ascii=False))
    return 0 if aborted is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
