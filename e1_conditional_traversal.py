#!/usr/bin/env python3
"""E1 query-type conditional traversal measurement.

Prereg (LakatoTree, 2026-07-23):
  - bridge subset (gold hop >= 3):  mean(best traversal arm - static) >= +2.0pp
    would trigger a 'conditional OFF' revision proposal.
  - factoid subset (gold hop <= 2): mean(best traversal arm - static) < 0pp
    (traversal hurts factoid queries).

Fixed split rule: bridge = gold hop >= 3, factoid = gold hop <= 2.
Gold hop count = per-query n_gold (number of gold evidence docs), which is
consistent with the file's own test_per_hop stratification
(musique hop labels 2hop/3hop*/4hop* map 1:1 onto n_gold; 2wiki uses n_gold).

Primary metric: sup_recall_at_3 (present in the input file).
Static arm: hswm_static. Traversal arms: hswm_traversal, ppr_pure,
traversal_wseed. 'cosine' is a non-HSWM baseline, reported but not part of
the delta. 'best traversal arm' = traversal arm with the highest subset mean.

Paired bootstrap 95% CI, 10000 resamples, seed=20260723.
stdlib + numpy only. Measurement only -- no code improvement.
"""

import hashlib
import json
import sys

import numpy as np

INPUT = "/Users/lagyeongjun/CD/SYMPOSIUM/GIT/HSWM/traversal_bench_results.json"
OUT_JSON = "/Users/lagyeongjun/CD/SYMPOSIUM/GIT/HSWM/EVIDENCE_E1_CONDITIONAL_TRAVERSAL_2026-07-23.json"

METRIC = "sup_recall_at_3"
STATIC_ARM = "hswm_static"
TRAVERSAL_ARMS = ["hswm_traversal", "ppr_pure", "traversal_wseed"]
BASELINE_ARMS = ["cosine"]
SEED = 20260723
N_BOOT = 10000
BRIDGE_MIN_HOP = 3
PREREG_DELTA_PP = 2.0


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def paired_boot_ci(diff, rng, n_boot=N_BOOT):
    """Percentile 95% CI of the mean of a paired difference vector."""
    diff = np.asarray(diff, dtype=float)
    n = len(diff)
    idx = rng.integers(0, n, size=(n_boot, n))
    means = diff[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def main():
    with open(INPUT) as f:
        data = json.load(f)

    arms_all = list(data["arms"])
    per_query = data["per_query"]

    # --- join coverage: hop label source -------------------------------------
    test = [q for q in per_query if q["split"] == "test"]
    with_hop = [q for q in test if isinstance(q.get("n_gold"), int)]
    coverage = {
        "hop_label_source": "per-query n_gold field inside traversal_bench_results.json "
        "(gold evidence doc count; consistent with file's own test_per_hop strata)",
        "n_test_total": len(test),
        "n_test_with_hop": len(with_hop),
        "coverage": len(with_hop) / len(test) if test else 0.0,
        "n_excluded_no_hop": len(test) - len(with_hop),
    }

    subsets = {
        "bridge": [q for q in with_hop if q["n_gold"] >= BRIDGE_MIN_HOP],
        "factoid": [q for q in with_hop if q["n_gold"] <= 2],
    }

    rng = np.random.default_rng(SEED)
    results = {}
    for name, qs in subsets.items():
        arm_scores = {
            a: np.array([q[a][METRIC] for q in qs], dtype=float) for a in arms_all
        }
        arm_means = {a: float(v.mean()) for a, v in arm_scores.items()}
        best_trav = max(TRAVERSAL_ARMS, key=lambda a: arm_means[a])
        diff = (arm_scores[best_trav] - arm_scores[STATIC_ARM]) * 100.0  # pp
        delta_pp = float(diff.mean())
        lo, hi = paired_boot_ci(diff, rng)
        # per-arm deltas vs static (evidence table)
        per_arm_delta = {}
        for a in TRAVERSAL_ARMS + BASELINE_ARMS:
            d_a = (arm_scores[a] - arm_scores[STATIC_ARM]) * 100.0
            lo_a, hi_a = paired_boot_ci(d_a, rng)
            per_arm_delta[a] = {
                "delta_pp": float(d_a.mean()),
                "ci95_pp": [lo_a, hi_a],
            }
        results[name] = {
            "n": len(qs),
            "split_rule": f"n_gold >= {BRIDGE_MIN_HOP}"
            if name == "bridge"
            else "n_gold <= 2",
            "arm_means": arm_means,
            "best_traversal_arm": best_trav,
            "delta_best_trav_minus_static_pp": delta_pp,
            "ci95_pp": [lo, hi],
            "per_arm_delta_vs_static_pp": per_arm_delta,
        }

    # --- prereg verdict --------------------------------------------------------
    b = results["bridge"]
    fct = results["factoid"]
    verdict = {
        "bridge_prediction": f"delta >= +{PREREG_DELTA_PP}pp (prior expectation: low)",
        "bridge_observed_pp": b["delta_best_trav_minus_static_pp"],
        "bridge_ci95_pp": b["ci95_pp"],
        "bridge_prediction_confirmed": bool(
            b["delta_best_trav_minus_static_pp"] >= PREREG_DELTA_PP
            and b["ci95_pp"][0] > 0
        ),
        "novel_factoid_prediction": "delta < 0pp (traversal hurts factoid)",
        "novel_factoid_observed_pp": fct["delta_best_trav_minus_static_pp"],
        "novel_factoid_ci95_pp": fct["ci95_pp"],
        "novel_factoid_prediction_confirmed": bool(
            fct["delta_best_trav_minus_static_pp"] < 0
        ),
    }
    verdict["prereg_call"] = (
        "conditional-OFF revision proposal"
        if verdict["bridge_prediction_confirmed"]
        else "full TRAVERSAL_OFF verdict stands"
    )

    out = {
        "label": "E1_CONDITIONAL_TRAVERSAL",
        "date": "2026-07-23",
        "input_file": INPUT,
        "input_sha256": sha256_of(INPUT),
        "metric": METRIC,
        "static_arm": STATIC_ARM,
        "traversal_arms": TRAVERSAL_ARMS,
        "baseline_arms_reported_only": BASELINE_ARMS,
        "split_rule": {
            "bridge": f"gold hop (n_gold) >= {BRIDGE_MIN_HOP}",
            "factoid": "gold hop (n_gold) <= 2",
        },
        "join_coverage": coverage,
        "bootstrap": {
            "type": "paired percentile",
            "n_resamples": N_BOOT,
            "seed": SEED,
        },
        "results": results,
        "prereg_verdict": verdict,
    }
    with open(OUT_JSON, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    # console summary
    print(f"input sha256: {out['input_sha256']}")
    print(f"metric: {METRIC} | test queries with hop: {coverage['n_test_with_hop']}/{coverage['n_test_total']}")
    for name in ("bridge", "factoid"):
        r = results[name]
        print(f"\n[{name}] n={r['n']}")
        for a in arms_all:
            print(f"  {a:16s} mean={r['arm_means'][a]:.4f}")
        print(
            f"  best traversal = {r['best_traversal_arm']}: "
            f"delta vs static = {r['delta_best_trav_minus_static_pp']:+.2f}pp "
            f"CI95 [{r['ci95_pp'][0]:+.2f}, {r['ci95_pp'][1]:+.2f}]"
        )
    print(f"\nprereg call: {verdict['prereg_call']}")
    print(f"wrote {OUT_JSON}")


if __name__ == "__main__":
    sys.exit(main())
