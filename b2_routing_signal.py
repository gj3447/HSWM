#!/usr/bin/env python3
"""B-2 routing signal existence — measurement only, no learning.

Preregistered (LakatoTree): does a per-query routing signal exist in our query
distribution at all? Computed from EXISTING per-query result JSONs.

Metrics per dataset:
  - oracle_gap_pp : mean_q(max_arm score_q) - max_arm(mean score), in percentage
                    points. Upper bound on what any per-query router could gain
                    over the best fixed strategy.
  - tie_rate_pct  : % of queries where (top1 - top2) <= EPSILON.
  - margin stats  : per-query (top1 - top2) distribution (mean/median/p90).
  - bootstrap 95% CI for oracle gap (paired, N_BOOT resamples, fixed seed).

Kill conditions (prereg): oracle_gap < 2.0pp  OR  tie_rate > 80%.
"""

import hashlib
import json
import statistics
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent
EPSILON = 0.01
SEED = 20260723
N_BOOT = 10000

OUT_JSON = REPO / "EVIDENCE_B2_ROUTING_SIGNAL_2026-07-23.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def load_substrate_bench():
    """substrate_bench_results.json: 5 substrates x {sup_recall_at_3, ndcg10, hit_at_3, mrr}."""
    d = json.loads((REPO / "substrate_bench_results.json").read_text())
    arms = ["cosine", "bm25", "ppr", "rrf", "hswm"]
    rows = []  # (group, {arm: {metric: float}})
    for e in d["per_query"]:
        rows.append((e["run"], {a: e[a] for a in arms}))
    return rows, arms, ["sup_recall_at_3", "ndcg10"]


def load_traversal_bench():
    """traversal_bench_results.json: 5 arms x {sup_recall_at_3, ndcg10}; test split only."""
    d = json.loads((REPO / "traversal_bench_results.json").read_text())
    arms = list(d["arms"])
    rows = []
    n_val_skipped = 0
    for e in d["per_query"]:
        if e.get("split") != "test":
            n_val_skipped += 1
            continue
        rows.append((e["dataset"], {a: e[a] for a in arms}))
    return rows, arms, ["sup_recall_at_3", "ndcg10"], n_val_skipped


def load_ab_p5():
    """ab_p5_full_results.json: per_query_by_run, arms cosine/direct/hswm, metric f1/em."""
    d = json.loads((REPO / "ab_p5_full_results.json").read_text())
    arms = ["cosine", "direct", "hswm"]
    rows = []
    for run, entries in d["per_query_by_run"].items():
        tag = run.replace("ab_p5_full_", "").replace(".json", "")
        for e in entries:
            rows.append((tag, {a: e[a] for a in arms}))
    return rows, arms, ["f1", "em"]


def analyze(rows, arms, metric):
    """rows: [(group, {arm: {metric: float}})]. Returns stats for one metric."""
    n = len(rows)
    per_q = []
    for _, armvals in rows:
        scores = sorted((armvals[a][metric] for a in arms), reverse=True)
        per_q.append((scores[0], scores[1] if len(scores) > 1 else 0.0, armvals))

    means = {a: statistics.fmean(av[a][metric] for _, _, av in per_q) for a in arms}
    best_fixed = max(means, key=means.get)

    # per-query gap vs the best fixed strategy (identified on full data)
    gaps = np.array([top1 - av[best_fixed][metric] for top1, _, av in per_q])
    oracle_gap = float(gaps.mean())

    margins = sorted(top1 - top2 for top1, top2, _ in per_q)
    tie_rate = sum(1 for m in margins if m <= EPSILON) / n

    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, n, size=(N_BOOT, n))
    boot = gaps[idx].mean(axis=1)
    ci_lo, ci_hi = np.percentile(boot, [2.5, 97.5])

    return {
        "metric": metric,
        "n_queries": n,
        "arms": arms,
        "arm_means": {a: round(means[a], 6) for a in arms},
        "best_fixed_arm": best_fixed,
        "best_fixed_mean": round(means[best_fixed], 6),
        "oracle_mean_score": round(float(np.array([t for t, _, _ in per_q]).mean()), 6),
        "oracle_gap": round(oracle_gap, 6),
        "oracle_gap_pp": round(oracle_gap * 100, 4),
        "oracle_gap_pp_ci95": [round(float(ci_lo) * 100, 4), round(float(ci_hi) * 100, 4)],
        "tie_rate_pct": round(tie_rate * 100, 2),
        "epsilon": EPSILON,
        "margin_pp": {
            "mean": round(statistics.fmean(margins) * 100, 4),
            "median": round(statistics.median(margins) * 100, 4),
            "p90": round(float(np.percentile(margins, 90)) * 100, 4),
        },
    }


def group_rows(rows):
    groups = {}
    for g, av in rows:
        groups.setdefault(g, []).append((g, av))
    return groups


def main():
    report = {
        "experiment": "B-2 routing signal existence (measurement-only, no learning)",
        "date": "2026-07-23",
        "epsilon": EPSILON,
        "bootstrap": {"n_resamples": N_BOOT, "seed": SEED, "paired": True},
        "kill_conditions": {"oracle_gap_pp_lt": 2.0, "tie_rate_pct_gt": 80.0},
        "inputs": {},
        "datasets": {},
        "files_without_per_query": {
            "qkv_routing_result.json": "aggregate counts/rates only; no per-query scores",
            "qkv_b1_development_result.json": "arms carry only aggregate metrics + score_matrix_sha256; raw score matrix not stored",
        },
    }

    # --- substrate bench ---
    p = REPO / "substrate_bench_results.json"
    report["inputs"][p.name] = sha256(p)
    rows, arms, metrics = load_substrate_bench()
    for name, sub in [("pooled", rows)] + sorted(group_rows(rows).items()):
        ds = report["datasets"][f"substrate_bench/{name}"] = {"source": p.name, "arms": arms}
        for m in metrics:
            ds[m] = analyze(sub, arms, m)

    # --- traversal bench (test split only) ---
    p = REPO / "traversal_bench_results.json"
    report["inputs"][p.name] = sha256(p)
    rows, arms, metrics, n_val = load_traversal_bench()
    for name, sub in [("pooled_test", rows)] + sorted(group_rows(rows).items()):
        ds = report["datasets"][f"traversal_bench/{name}"] = {
            "source": p.name, "arms": arms, "val_rows_excluded": n_val}
        for m in metrics:
            ds[m] = analyze(sub, arms, m)

    # --- ab_p5 full ---
    p = REPO / "ab_p5_full_results.json"
    report["inputs"][p.name] = sha256(p)
    rows, arms, metrics = load_ab_p5()
    for name, sub in [("pooled", rows)] + sorted(group_rows(rows).items()):
        ds = report["datasets"][f"ab_p5/{name}"] = {"source": p.name, "arms": arms}
        for m in metrics:
            ds[m] = analyze(sub, arms, m)

    # --- primary verdict inputs: primary metric per dataset ---
    primary_metric = {
        "substrate_bench": "sup_recall_at_3",
        "traversal_bench": "sup_recall_at_3",
        "ab_p5": "f1",
    }
    primaries = []
    for dsname, ds in report["datasets"].items():
        bench = dsname.split("/")[0]
        m = primary_metric[bench]
        r = ds[m]
        primaries.append({
            "dataset": dsname, "metric": m,
            "oracle_gap_pp": r["oracle_gap_pp"],
            "oracle_gap_pp_ci95": r["oracle_gap_pp_ci95"],
            "tie_rate_pct": r["tie_rate_pct"],
            "n_queries": r["n_queries"],
        })
    best = max(primaries, key=lambda x: x["oracle_gap_pp"])
    report["primary_summary"] = {
        "per_dataset": primaries,
        "max_oracle_gap_pp": {"dataset": best["dataset"], "metric": best["metric"],
                              "oracle_gap_pp": best["oracle_gap_pp"],
                              "ci95": best["oracle_gap_pp_ci95"],
                              "tie_rate_pct": best["tie_rate_pct"]},
        "kill_rule": "kill if oracle_gap_pp < 2.0 OR tie_rate_pct > 80 on the most routing-favorable dataset",
    }

    OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")

    # console summary
    print(f"epsilon={EPSILON}  boot={N_BOOT}  seed={SEED}")
    print(f"{'dataset':38s} {'metric':16s} {'n':>4s} {'oracle_gap_pp':>13s} {'CI95':>18s} {'tie%':>7s} {'marg_med_pp':>11s}")
    for dsname, ds in report["datasets"].items():
        for m in (k for k in ds if k not in ("source", "arms", "val_rows_excluded")):
            r = ds[m]
            ci = r["oracle_gap_pp_ci95"]
            print(f"{dsname:38s} {m:16s} {r['n_queries']:>4d} {r['oracle_gap_pp']:>13.3f} "
                  f"[{ci[0]:>7.3f},{ci[1]:>7.3f}] {r['tie_rate_pct']:>6.2f}% {r['margin_pp']['median']:>11.3f}")
    b = report["primary_summary"]["max_oracle_gap_pp"]
    print(f"\nMAX oracle gap (most routing-favorable): {b['dataset']} {b['metric']} "
          f"= {b['oracle_gap_pp']:.3f}pp CI95={b['ci95']} tie={b['tie_rate_pct']:.2f}%")


if __name__ == "__main__":
    main()
