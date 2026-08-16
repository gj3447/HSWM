"""HSWM_LOCAL_RECORD-compatible replay judge for the F4-r2 sealed measurement.

HSWM_LOCAL_RECORD replays a producer with exactly one positional result path and
expects ``metric=<number>`` on stdout (f2_replay_judge.py pattern).  The
result path accepted here is the sealed F4-r2 receipt
(``hswm-f4-topology-learning-r2-receipt/v1``).  The judge:

  1. binds the receipt to the harness scripts it was produced by
     (script_sha256 + harness module shas) and to the locked preregistration,
  2. rebuilds the deterministic world from the receipt config (question pool,
     splits, lessons, Hebbian anchor-edge learning, four arm topologies),
  3. recomputes EVERY number in the receipt from the on-disk LLM response
     cache (.f2_cache) with transport hard-forbidden (zero network — a cache
     miss aborts the replay), and
  4. requires BIT-EQUAL agreement (exact for counts/accuracies/weights,
     receipt-rounding for curve/rho values) before printing the prereg
     primary metric ``A_learned - best_control`` on fresh heldout.

The judge never accepts a client-supplied value; it derives the metric again
through the deterministic measurement path.
"""
from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
import sys


def _discover_repository_root(anchor: str | Path = __file__) -> Path:
    resolved = Path(anchor).resolve(strict=True)
    start = resolved.parent if resolved.is_file() else resolved
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise RuntimeError(f"cannot locate HSWM repository root from {resolved}")


REPO_ROOT = _discover_repository_root()
F_SERIES_ROOT = REPO_ROOT / "_research" / "f_series"
for _import_root in (REPO_ROOT, REPO_ROOT / "src"):
    if str(_import_root) not in sys.path:
        sys.path.insert(0, str(_import_root))


def _harness_module_path(relative_name: str) -> Path:
    if relative_name in {"f2_delta_w_credit.py", "f4_topology_learning.py"}:
        return F_SERIES_ROOT / relative_name
    if relative_name == "hswm_null_battery.py":
        return REPO_ROOT / "prom_search_hswm" / relative_name
    return REPO_ROOT / relative_name

RECEIPT_SCHEMA = "hswm-f4-topology-learning-r2-receipt/v1"


class F4ReplayError(ValueError):
    """The sealed F4 receipt cannot be regenerated bit-equally."""


class _TransportForbidden(Exception):
    """Replay attempted an LLM call that is not in the disk cache."""


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_receipt(path: Path) -> dict:
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise F4ReplayError(f"receipt unreadable: {type(error).__name__}") from error
    if not isinstance(receipt, dict):
        raise F4ReplayError("receipt must be a mapping")
    if receipt.get("schema_version") != RECEIPT_SCHEMA:
        raise F4ReplayError("receipt schema drifted")
    if receipt.get("aborted") is not None:
        raise F4ReplayError(f"receipt is an aborted run: {receipt['aborted']}")
    if receipt.get("smoke"):
        raise F4ReplayError("smoke receipts are not replayable evidence")
    return receipt


def _compare(label: str, recomputed, recorded, mismatches: list) -> None:
    if recomputed != recorded:
        mismatches.append({
            "field": label, "recorded": recorded, "recomputed": recomputed})


def replay_metric(receipt_path: Path) -> float:
    receipt = _load_receipt(receipt_path)

    # ---- bind harness scripts + preregistration ----
    r2_path = F_SERIES_ROOT / "f4_topology_learning_r2.py"
    if not r2_path.is_file():
        raise F4ReplayError("canonical r2 harness script missing")
    if _sha256_file(r2_path) != receipt.get("script_sha256"):
        raise F4ReplayError("r2 harness script sha256 differs from the receipt")
    module_shas = receipt.get("harness_module_sha256", {})
    for rel, sha in module_shas.items():
        p = _harness_module_path(rel)
        if not p.is_file() or _sha256_file(p) != sha:
            raise F4ReplayError(f"harness module drifted: {rel}")
    prereg_path = Path(receipt["preregistration_file"])
    if prereg_path.is_file():
        if _sha256_file(prereg_path) != receipt.get("preregistration_file_sha256"):
            raise F4ReplayError("preregistration file sha256 drifted")

    f2 = importlib.import_module("_research.f_series.f2_delta_w_credit")
    f4r1 = importlib.import_module("_research.f_series.f4_topology_learning")
    m = importlib.import_module("_research.f_series.f4_topology_learning_r2")
    from prom_search_hswm.hswm_null_battery import (  # noqa: E402
        bipartite_degree_preserving_shuffle,
        headroom_band_ok,
    )

    # ---- hard-forbid any LLM transport (cache-only replay) ----
    def _forbidden_transport(req, timeout, backend):
        raise _TransportForbidden("replay attempted a non-cached LLM call")
    f2._transport_with_backoff = _forbidden_transport

    config = receipt["config"]
    seed = int(config["seed"])
    n_lessons = int(config["lessons"])
    n_fresh = int(config["n_fresh"])
    k_context = int(config["k_context"])
    parallel = 4
    universes_dir = Path(config["universes_dir"])
    if not universes_dir.is_absolute():
        universes_dir = REPO_ROOT / universes_dir

    # ---- rebuild the deterministic world ----
    worlds = m.make_worlds(n_lessons)
    pool, _stats = f2.load_question_pool(universes_dir, int(config["max_answers"]))
    article_cache = f2._ArticleCache(universes_dir)
    built = f4r1.build_splits(pool, article_cache, worlds=worlds,
                              n_fresh=n_fresh,
                              max_answers=int(config["max_answers"]),
                              split_seed=int(config["split_seed"]))
    train_cases = built["splits"]["train"]
    fresh_cases = built["splits"]["fresh"]
    lessons, lesson_meta = f4r1.compile_lessons(train_cases, worlds)
    by_id = f4r1.lessons_by_id(lessons)
    lesson_ids = sorted(by_id)
    anchors = sorted({w["trusted"] for w in worlds}
                     | {w["distractor"] for w in worlds})

    mismatches: list = []
    _compare("fresh_case_worlds", [w for _c, w, _q, _u in fresh_cases],
             receipt["splits"]["fresh_case_worlds"], mismatches)
    leak = f2.leakage_report(train_cases, [], fresh_cases)
    _compare("leakage_binding", leak["binding_leakage"],
             receipt["leakage"]["binding_leakage"], mismatches)

    budget = f2.Budget(10 ** 9)
    if config["answer_backend"] == "vllm":
        answerer = f2.CachedOpenAIChat(config["answer_url"], budget)
    else:
        answerer = f2.CachedChat(config["answer_url"], budget)
    answer_model = config["answer_model"]

    # ---- base ----
    if receipt.get("fresh_base_accuracy") is not None:
        base = f2.evaluate_subset(answerer, answer_model, (), fresh_cases,
                                  by_id, parallel, seed)
        _compare("fresh_base_accuracy", base["accuracy"],
                 receipt["fresh_base_accuracy"], mismatches)

    # ---- learn anchor edges ----
    n_cases = len(train_cases)
    n_checkpoints = int(config["checkpoints"])
    checkpoint_at = {
        max(1, round(n_cases * (i + 1) / (n_checkpoints + 1)))
        for i in range(n_checkpoints)}
    weights, e_learned, checkpoints = m.learn_anchor_edges(
        answerer, answer_model, train_cases, lessons,
        parallel, seed, checkpoint_at)
    worlds_with_edge = sorted({idx for idx in range(n_lessons)
                               if any(l == lessons[idx].lesson_id
                                      for _a, l in e_learned)})
    _compare("edges_kept", len(e_learned), receipt["learning"]["edges_kept"],
             mismatches)
    _compare("worlds_with_valid_edge", worlds_with_edge,
             receipt["learning"]["worlds_with_valid_edge"], mismatches)
    _compare("edge_weights",
             {f"{a}->{l[:12]}": w for (a, l), w in sorted(weights.items())},
             receipt["learning"]["edge_weights"], mismatches)
    _compare("checkpoint_edge_counts",
             [{"after_case": c["after_case"], "n_edges": len(c["edges"])}
              for c in checkpoints],
             receipt["learning"]["checkpoints"], mismatches)

    # ---- arms ----
    edge_sets = {
        "A_learned": set(e_learned),
        "B_shuffled": set(bipartite_degree_preserving_shuffle(
            sorted(e_learned), lesson_ids, f"f4r2-shuffle-{seed}")),
        "C_clique": m.clique_bipartite(anchors, lesson_ids),
        "D_random_sparse": m.random_sparse_bipartite(
            anchors, lesson_ids, len(e_learned), f"f4r2-randsparse-{seed}"),
    }
    arms = {}
    for arm_id, edges in edge_sets.items():
        res = m.eval_topology(answerer, answer_model, edges, fresh_cases,
                              k_context, parallel, seed, by_id)
        arms[arm_id] = res
        rec_arm = receipt["arms"][arm_id]
        _compare(f"{arm_id}.n_edges", len(edges), rec_arm["n_edges"], mismatches)
        _compare(f"{arm_id}.fresh_accuracy", res["accuracy"],
                 rec_arm["fresh_accuracy"], mismatches)
        _compare(f"{arm_id}.fresh_parse_failures", res["parse_failures"],
                 rec_arm["fresh_parse_failures"], mismatches)
        _compare(f"{arm_id}.empty_contexts", res["empty_contexts"],
                 rec_arm["empty_contexts"], mismatches)

    # ---- topology divergence ----
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
    _compare("topology_divergence", divergence,
             receipt["topology_divergence"], mismatches)

    # ---- causal curve (anchor-pair units) ----
    acc_a = arms["A_learned"]["accuracy"]
    units_by_lesson: dict[str, set] = {}
    for _a, _l in e_learned:
        units_by_lesson.setdefault(_l, set()).add((_a, _l))
    lid2world = {lessons[w].lesson_id: w for w in lessons}
    fresh_world_set = {w for _c, w, _q, _u in fresh_cases}
    candidates = sorted(
        (l for l in units_by_lesson if lid2world[l] in fresh_world_set),
        key=lambda l: (-sum(weights[e] for e in units_by_lesson[l]), l))
    loo_units = candidates[:int(config["loo_m"])]
    importance = {}
    for l in loo_units:
        res = m.eval_topology(answerer, answer_model,
                              e_learned - units_by_lesson[l], fresh_cases,
                              k_context, parallel, seed, by_id)
        importance[l] = acc_a - res["accuracy"]
    removal_order = (
        sorted(loo_units, key=lambda l: (-importance[l], l))
        + [l for l in candidates if l not in loo_units]
        + sorted((l for l in units_by_lesson if l not in candidates),
                 key=lambda l: (-sum(weights[e] for e in units_by_lesson[l]), l)))
    import random as _random
    rng = _random.Random(f"f4r2-curve-{seed}")
    random_order = sorted(units_by_lesson)  # hash-order-independent (replay determinism)
    rng.shuffle(random_order)
    k_steps = min(int(config["curve_k"]), len(removal_order))
    curve_top, curve_rand = [], []
    for k in range(1, k_steps + 1):
        drop_t = set().union(*(units_by_lesson[l] for l in removal_order[:k]))
        drop_r = set().union(*(units_by_lesson[l] for l in random_order[:k]))
        curve_top.append(m.eval_topology(
            answerer, answer_model, e_learned - drop_t,
            fresh_cases, k_context, parallel, seed, by_id))
        curve_rand.append(m.eval_topology(
            answerer, answer_model, e_learned - drop_r,
            fresh_cases, k_context, parallel, seed, by_id))
    gap_per_k = [r["accuracy"] - t["accuracy"]
                 for r, t in zip(curve_rand, curve_top)]
    auc_gap = sum(gap_per_k) / len(gap_per_k) if gap_per_k else None
    per_case_gaps = []
    for t, r in zip(curve_top, curve_rand):
        per_case_gaps.append([r_ - t_ for t_, r_ in zip(
            t["correct_vector"], r["correct_vector"])])
    flat_gaps = [g for per_k in per_case_gaps for g in per_k]
    gap_ci = f4r1.paired_bootstrap_gap(
        flat_gaps, [0] * len(flat_gaps),
        n_boot=int(config["n_boot"]), seed=seed + 1)
    _compare("k_steps", k_steps, receipt["causal_curve"]["k_steps"], mismatches)
    _compare("loo_candidate_units", len(candidates),
             receipt["causal_curve"]["loo_candidate_units"], mismatches)
    _compare("loo_measured_units",
             {l[:12]: round(importance[l], 4) for l in loo_units},
             receipt["causal_curve"]["loo_measured_units"], mismatches)
    _compare("curve_top_acc", [round(r["accuracy"], 4) for r in curve_top],
             receipt["causal_curve"]["curve_top_acc"], mismatches)
    _compare("curve_rand_acc", [round(r["accuracy"], 4) for r in curve_rand],
             receipt["causal_curve"]["curve_rand_acc"], mismatches)
    _compare("auc_gap", (round(auc_gap, 4) if auc_gap is not None else None),
             receipt["causal_curve"]["auc_gap"], mismatches)
    _compare("auc_gap_ci95", gap_ci["ci95"],
             receipt["causal_curve"]["auc_gap_ci95"], mismatches)

    # ---- structure-performance correlation ----
    topo_points = [{"tag": f"ckpt_{c['after_case']}", "edges": set(c["edges"])}
                   for c in checkpoints]
    topo_points.append({"tag": "final", "edges": set(e_learned)})
    topo_accs = {}
    for tp in topo_points:
        if tp["tag"] == "final":
            topo_accs[tp["tag"]] = acc_a
        else:
            topo_accs[tp["tag"]] = m.eval_topology(
                answerer, answer_model, tp["edges"], fresh_cases,
                k_context, parallel, seed, by_id)["accuracy"]
    _compare("checkpoint_accuracies", topo_accs,
             receipt["structure_performance"]["checkpoint_accuracies"], mismatches)
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
        corr_points, n_boot=int(config["n_boot"]), seed=seed) if corr_points else {
            "ci95": [None, None]}
    _compare("corr_points", corr_points,
             [tuple(p) for p in receipt["structure_performance"]["points"]],
             mismatches)
    _compare("spearman_rho", (round(rho, 4) if rho is not None else None),
             receipt["structure_performance"]["spearman_rho"], mismatches)
    _compare("rho_ci95", rho_boot["ci95"],
             receipt["structure_performance"]["rho_ci95"], mismatches)

    # ---- kill observations ----
    controls = {k: v for k, v in arms.items() if k != "A_learned"}
    best_control = max(controls, key=lambda k: controls[k]["accuracy"])
    control_gaps = {}
    for name, arm in controls.items():
        gap = f4r1.paired_bootstrap_gap(arms["A_learned"]["correct_vector"],
                                        arm["correct_vector"],
                                        n_boot=int(config["n_boot"]), seed=seed)
        control_gaps[name] = {"a_minus_x": round(
            arms["A_learned"]["accuracy"] - arm["accuracy"], 4),
            "ci95": [round(x, 4) for x in gap["ci95"]]}
    kills = receipt["kill_condition_observations"]
    _compare("f4_k1", any(arm["accuracy"] >= acc_a for arm in controls.values()),
             kills["f4_k1_any_control_catches_a"], mismatches)
    _compare("f4_k2", (gap_ci["ci95"][0] is not None
                       and gap_ci["ci95"][1] is not None
                       and gap_ci["ci95"][0] <= 0 <= gap_ci["ci95"][1]),
             kills["f4_k2_auc_gap_ci_includes_0"], mismatches)
    _compare("f4_k3", (rho_boot["ci95"][0] is not None
                       and rho_boot["ci95"][1] is not None
                       and rho_boot["ci95"][0] <= 0 <= rho_boot["ci95"][1]),
             kills["f4_k3_rho_ci_includes_0"], mismatches)
    _compare("best_control", best_control,
             kills["values"]["best_control"], mismatches)
    _compare("control_gaps", control_gaps, kills["values"]["control_gaps"],
             mismatches)

    # ---- zero-transport proof ----
    if answerer.misses:
        mismatches.append({"field": "transport_free",
                           "recorded": 0, "recomputed": answerer.misses})
    _compare("total_logical_calls", answerer.hits,
             receipt["llm_budget"]["total_logical"], mismatches)

    if mismatches:
        raise F4ReplayError(json.dumps(
            {"mismatches": mismatches[:20], "total": len(mismatches)},
            ensure_ascii=False))
    return acc_a - controls[best_control]["accuracy"]


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1 or args[0].startswith("-"):
        print(
            "replay_error=usage: python -m _research.replay_judges.f4_replay_judge <receipt_path>",
            file=sys.stderr,
        )
        return 1
    try:
        metric = replay_metric(Path(args[0]))
    except (F4ReplayError, _TransportForbidden, ValueError, OSError) as error:
        print(f"replay_error={type(error).__name__}:{error}", file=sys.stderr)
        return 1
    print(f"metric={metric:g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
