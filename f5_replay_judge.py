"""HSWM_LOCAL_RECORD-compatible replay judge for the F5 sealed measurement.

HSWM_LOCAL_RECORD replays a producer with exactly one positional result path and
expects ``metric=<number>`` on stdout (f2/f4_replay_judge.py pattern).  The
result path accepted here is the sealed F5 receipt
(``hswm-f5-consolidation-receipt/v1``).  The judge:

  1. binds the receipt to the harness script (script_sha256 +
     harness_module_sha256) and to the locked preregistration,
  2. rebuilds the deterministic world from the receipt config (splits,
     wake/sleep timeline, three arms, detail+gist probes, conflict
     injection) — all RNG is seeded and all shuffle inputs are sorted, so
     no string-hash-seed dependence (the F4 bug class),
  3. recomputes EVERY number in the receipt from the on-disk LLM response
     cache (.f2_cache) with transport hard-forbidden (zero network — a
     cache miss aborts the replay), and
  4. requires BIT-EQUAL agreement before printing the prereg primary
     metric: mean over lag >= 4 of (A_detail - max(B_detail, C_detail)).

The judge never accepts a client-supplied value; it derives the metric
again through the deterministic measurement path.
"""
from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

RECEIPT_SCHEMA = "hswm-f5-consolidation-receipt/v1"


class F5ReplayError(ValueError):
    """The sealed F5 receipt cannot be regenerated bit-equally."""


class _TransportForbidden(Exception):
    """Replay attempted an LLM call that is not in the disk cache."""


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_receipt(path: Path) -> dict:
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise F5ReplayError(f"receipt unreadable: {type(error).__name__}") from error
    if not isinstance(receipt, dict):
        raise F5ReplayError("receipt must be a mapping")
    if receipt.get("schema_version") != RECEIPT_SCHEMA:
        raise F5ReplayError("receipt schema drifted")
    if receipt.get("aborted") is not None:
        raise F5ReplayError(f"receipt is an aborted run: {receipt['aborted']}")
    if receipt.get("smoke"):
        raise F5ReplayError("smoke receipts are not replayable evidence")
    return receipt


def _compare(label: str, recomputed, recorded, mismatches: list) -> None:
    if recomputed != recorded:
        mismatches.append({
            "field": label, "recorded": recorded, "recomputed": recomputed})


def replay_metric(receipt_path: Path) -> float:
    receipt = _load_receipt(receipt_path)

    harness_path = HERE / "f5_consolidation.py"
    if not harness_path.is_file():
        raise F5ReplayError("f5 harness script missing beside the judge")
    if _sha256_file(harness_path) != receipt.get("script_sha256"):
        raise F5ReplayError("f5 harness script sha256 differs from the receipt")
    module_sha = receipt.get("harness_module_sha256")
    if module_sha:
        p = HERE / "f2_delta_w_credit.py"
        if not p.is_file() or _sha256_file(p) != module_sha:
            raise F5ReplayError("f2 module sha256 drifted")
    prereg_path = Path(receipt["preregistration_file"])
    if prereg_path.is_file():
        if _sha256_file(prereg_path) != receipt.get("preregistration_file_sha256"):
            raise F5ReplayError("preregistration file sha256 drifted")

    f2 = importlib.import_module("f2_delta_w_credit")
    f3r1 = importlib.import_module("f3_agent_ab_transfer")
    m = importlib.import_module("f5_consolidation")

    def _forbidden_transport(req, timeout, backend):
        raise _TransportForbidden("replay attempted a non-cached LLM call")
    f2._transport_with_backoff = _forbidden_transport

    config = receipt["config"]
    seed = int(config["seed"])
    E = int(config["episodes"])
    budget_chars = int(config["token_budget_chars"])
    parallel = 4
    universes_dir = Path(config["universes_dir"])
    if not universes_dir.is_absolute():
        universes_dir = HERE / universes_dir

    # ---- rebuild the deterministic world ----
    pool, _stats = f2.load_question_pool(universes_dir, int(config["max_answers"]))
    article_cache = f2._ArticleCache(universes_dir)
    built = m.build_splits_f5(pool, article_cache, n_episodes=E,
                              n_fresh_ep=int(config["n_fresh_ep"]),
                              max_answers=int(config["max_answers"]),
                              split_seed=int(config["split_seed"]))
    train_cases = built["splits"]["train"]
    fresh_cases = built["splits"]["fresh"]
    train_by_origin = {item[1]: item for item in train_cases}
    fresh_by_ep = {ep: [item for item in fresh_cases if item[1] == ep]
                   for ep in range(E)}

    mismatches: list = []
    leak = f2.leakage_report(train_cases, [], fresh_cases)
    _compare("leakage_binding", leak["binding_leakage"],
             receipt["leakage"]["binding_leakage"], mismatches)

    budget = f2.Budget(10 ** 9)
    if config["answer_backend"] == "vllm":
        answerer = f2.CachedOpenAIChat(config["answer_url"], budget)
    else:
        answerer = f2.CachedChat(config["answer_url"], budget)
    answer_model = config["answer_model"]

    # ---- timeline: wakes + sleeps ----
    store: list[m.StoreRec] = []
    snapshots: list[str] = []
    wake_meta = []
    for k in range(E):
        item = train_by_origin[k]
        case = item[0]
        lesson_full = m.compile_lesson(
            case, teach=case.trusted_class, ignore=case.distractor_class,
            confidence=1.0)
        by_id = {lesson_full.lesson_id: lesson_full}
        res_with = f3r1.eval_ctx(answerer, answer_model,
                                 ("lessons", (lesson_full.lesson_id,)),
                                 [item], by_id, parallel, seed)
        res_without = f3r1.eval_ctx(answerer, answer_model, ("none",),
                                    [item], by_id, parallel, seed)
        delta = res_with["correct_vector"][0] - res_without["correct_vector"][0]
        c0 = 0.5 + 0.5 * delta
        lesson = m.compile_lesson(
            case, teach=case.trusted_class, ignore=case.distractor_class,
            confidence=c0)
        store.append(m.StoreRec(lesson=lesson, origin=k, form="full",
                                confidence=c0))
        wake_meta.append({"episode": k, "acc_with": res_with["correct_vector"][0],
                          "acc_without": res_without["correct_vector"][0],
                          "c0": c0})
        if k < E - 1:
            m.sleep_pass(store, k, train_by_origin, snapshots)
    store_c = [m.StoreRec(lesson=r.lesson, origin=r.origin, form="full",
                          confidence=wake_meta[r.origin]["c0"])
               for r in store]
    _compare("wake_meta", wake_meta, receipt["timeline"]["wake"], mismatches)
    _compare("sleep_snapshot_sha256", snapshots,
             receipt["timeline"]["sleep_snapshot_sha256"], mismatches)
    _compare("final_store_A", [r.snapshot() for r in store],
             receipt["timeline"]["final_store_A"], mismatches)

    lags = [(E - 1 - ep) for ep in range(E)]

    # ---- probes ----
    from p1v3_policy_environment import render_policy_training_transcript
    transcripts = {ep: render_policy_training_transcript(train_by_origin[ep][0])
                   for ep in range(E)}
    results = {"A": {"detail": {}, "gist": {}},
               "C": {"detail": {}, "gist": {}},
               "B": {"detail": {}, "gist": {}}}
    parse_fail_total = 0
    for ep in range(E):
        items = fresh_by_ep[ep]
        q0 = items[0][0].question
        mem_a = m.render_store(store, budget_chars, q0)
        r = m.f5_eval(answerer, answer_model, items,
                      lambda item, mem=mem_a: (mem, item[0].question),
                      m.score_detail, parallel, seed)
        results["A"]["detail"][ep] = r
        parse_fail_total += r["parse_failures"]
        mem_ag = m.render_store_gist_probe(store, budget_chars)
        r = m.gist_verdict_probe(answerer, answer_model, items, mem_ag,
                                 parallel, seed)
        results["A"]["gist"][ep] = r
        parse_fail_total += r["parse_failures"]
        mem_c = m.render_store(store_c, budget_chars, q0)
        r = m.f5_eval(answerer, answer_model, items,
                      lambda item, mem=mem_c: (mem, item[0].question),
                      m.score_detail, parallel, seed)
        results["C"]["detail"][ep] = r
        parse_fail_total += r["parse_failures"]
        mem_cg = m.render_store_gist_probe(store_c, budget_chars)
        r = m.gist_verdict_probe(answerer, answer_model, items, mem_cg,
                                 parallel, seed)
        results["C"]["gist"][ep] = r
        parse_fail_total += r["parse_failures"]
        mem_b = transcripts[ep][:budget_chars]
        r = m.f5_eval(answerer, answer_model, items,
                      lambda item, mem=mem_b: (mem, item[0].question),
                      m.score_detail, parallel, seed)
        results["B"]["detail"][ep] = r
        parse_fail_total += r["parse_failures"]
        r = m.gist_verdict_probe(answerer, answer_model, items, mem_b,
                                 parallel, seed)
        results["B"]["gist"][ep] = r
        parse_fail_total += r["parse_failures"]

    immediate = {}
    base_detail = {}
    store_im: list[m.StoreRec] = []
    for k in range(E):
        item = train_by_origin[k]
        case = item[0]
        c0 = wake_meta[k]["c0"]
        lesson = m.compile_lesson(
            case, teach=case.trusted_class, ignore=case.distractor_class,
            confidence=c0)
        store_im.append(m.StoreRec(lesson=lesson, origin=k, form="full",
                                   confidence=c0))
        mem = m.render_store(store_im, budget_chars,
                             fresh_by_ep[k][0][0].question)
        r = m.f5_eval(answerer, answer_model, fresh_by_ep[k],
                      lambda item, mem=mem: (mem, item[0].question),
                      m.score_detail, parallel, seed)
        immediate[k] = r
        parse_fail_total += r["parse_failures"]
        r = m.f5_eval(answerer, answer_model, fresh_by_ep[k],
                      lambda item: ("", item[0].question),
                      m.score_detail, parallel, seed)
        base_detail[k] = r
        parse_fail_total += r["parse_failures"]

    # ---- curves ----
    def curve(arm, kind):
        return [results[arm][kind][ep]["accuracy"] for ep in range(E)]

    def vecs(arm, kind):
        return [results[arm][kind][ep]["correct_vector"] for ep in range(E)]

    R = {arm: {"detail": curve(arm, "detail"), "gist": curve(arm, "gist")}
         for arm in ("A", "B", "C")}
    _compare("lags", lags, receipt["retention_curves"]["lags"], mismatches)
    _compare("R_detail", {arm: R[arm]["detail"] for arm in R},
             receipt["retention_curves"]["R_detail"], mismatches)
    _compare("R_gist", {arm: R[arm]["gist"] for arm in R},
             receipt["retention_curves"]["R_gist"], mismatches)
    _compare("base_detail", [base_detail[ep]["accuracy"] for ep in range(E)],
             receipt["retention_curves"]["base_detail"], mismatches)
    _compare("immediate_A_detail", [immediate[ep]["accuracy"] for ep in range(E)],
             receipt["retention_curves"]["immediate_A_detail"], mismatches)

    # ---- slopes ----
    n_boot = int(config["n_boot"])
    slope_a = m.least_squares_slope(lags, R["A"]["detail"])
    slope_b = m.least_squares_slope(lags, R["B"]["detail"])
    slope_c = m.least_squares_slope(lags, R["C"]["detail"])
    sd_ac = m.bootstrap_slope_diff(vecs("A", "detail"), vecs("C", "detail"),
                                   lags, n_boot=n_boot, seed=seed)
    sd_ab = m.bootstrap_slope_diff(vecs("A", "detail"), vecs("B", "detail"),
                                   lags, n_boot=n_boot, seed=seed)
    _compare("decay_slopes", {
        "slope_A": round(slope_a, 4), "slope_B": round(slope_b, 4),
        "slope_C": round(slope_c, 4),
        "A_minus_C": {"diff": round(slope_a - slope_c, 4),
                      "ci95": [round(x, 4) for x in sd_ac["ci95"]]},
        "A_minus_B": {"diff": round(slope_a - slope_b, 4),
                      "ci95": [round(x, 4) for x in sd_ab["ci95"]]},
        "method": receipt["decay_slopes"]["method"],
    }, receipt["decay_slopes"], mismatches)

    # ---- judgment + kills ----
    gap_ab = [R["A"]["detail"][i] - R["B"]["detail"][i] for i in range(E)]
    gap_ac = [R["A"]["detail"][i] - R["C"]["detail"][i] for i in range(E)]
    lag4_idx = [i for i in range(E) if lags[i] >= 4]
    delta = float(config.get("delta", 0.10))
    cond1 = (bool(lag4_idx)
             and all(gap_ab[i] >= delta for i in lag4_idx)
             and all(gap_ac[i] >= delta for i in lag4_idx))
    cond2 = sd_ac["ci95"][0] > 0 and sd_ab["ci95"][0] > 0
    _compare("cond1", cond1,
             receipt["judgment_conditions"]["cond1_A_dominates_lag4plus_by_delta"],
             mismatches)
    _compare("cond2", cond2,
             receipt["judgment_conditions"]["cond2_A_slope_shallower_significant"],
             mismatches)
    _compare("lag4plus_indices", lag4_idx,
             receipt["judgment_conditions"]["lag4plus_indices"], mismatches)
    kills = receipt["kill_condition_observations"]
    _compare("f5_k1", min(gap_ab) <= delta,
             kills["f5_k1_B_within_delta_all_lags"], mismatches)
    _compare("f5_k2", max(gap_ac) <= delta,
             kills["f5_k2_A_minus_C_le_delta_all_lags"], mismatches)
    _compare("f5_k3", (gap_ac[-1] > delta and max(gap_ac[:-1] or [0]) <= delta),
             kills["f5_k3_advantage_only_at_lag0"], mismatches)
    _compare("gap_values", {"gap_A_minus_B": [round(x, 4) for x in gap_ab],
                            "gap_A_minus_C": [round(x, 4) for x in gap_ac]},
             kills["values"], mismatches)

    # ---- secondary endpoints ----
    gist_slope_a = m.least_squares_slope(lags, R["A"]["gist"])
    _compare("gist_detail_branch", {
        "detail_slope_A": round(slope_a, 4),
        "gist_slope_A": round(gist_slope_a, 4),
        "transformation_signature": bool(
            slope_a < -0.01 and gist_slope_a >= -0.01),
    }, receipt["gist_detail_branch"], mismatches)
    _compare("BWT_FWT", {
        "BWT_per_episode": [round(immediate[ep]["accuracy"]
                                  - R["A"]["detail"][ep], 4)
                            for ep in range(E)],
        "FWT_slope_immediate_over_episode": round(m.least_squares_slope(
            list(range(E)), [immediate[ep]["accuracy"] for ep in range(E)]), 4),
        "note": receipt["BWT_FWT"]["note"],
    }, receipt["BWT_FWT"], mismatches)

    ref_ep = 0
    conflict_acc = []
    for n_inj in (0, 1, 2):
        injected = list(store)
        for j in range(n_inj):
            src = train_by_origin[j][0]
            inv = m.compile_lesson(
                src, teach=src.distractor_class, ignore=src.trusted_class,
                confidence=1.0)
            injected.append(m.StoreRec(lesson=inv, origin=-(j + 1),
                                       form="injected", confidence=1.0))
        mem = m.render_store(injected, budget_chars,
                             fresh_by_ep[ref_ep][0][0].question)
        r = m.f5_eval(answerer, answer_model, fresh_by_ep[ref_ep],
                      lambda item, mem=mem: (mem, item[0].question),
                      m.score_detail, parallel, seed)
        conflict_acc.append(r["accuracy"])
        parse_fail_total += r["parse_failures"]
    _compare("conflict_accuracy", [round(x, 4) for x in conflict_acc],
             receipt["conflict_density"]["accuracy_A_ref_episode"], mismatches)
    _compare("parse_failures_total", parse_fail_total,
             receipt["parse_failures_total"], mismatches)

    # ---- zero-transport proof ----
    if answerer.misses:
        mismatches.append({"field": "transport_free",
                           "recorded": 0, "recomputed": answerer.misses})
    _compare("total_logical_calls", answerer.hits,
             receipt["llm_budget"]["total_logical"], mismatches)

    if mismatches:
        raise F5ReplayError(json.dumps(
            {"mismatches": mismatches[:20], "total": len(mismatches)},
            ensure_ascii=False))

    # ---- prereg primary metric: lag>=4 mean(A - max(B, C)) ----
    vals = [R["A"]["detail"][i] - max(R["B"]["detail"][i], R["C"]["detail"][i])
            for i in range(E) if lags[i] >= 4]
    return sum(vals) / len(vals)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1 or args[0].startswith("-"):
        print("replay_error=usage: f5_replay_judge.py <receipt_path>", file=sys.stderr)
        return 1
    try:
        metric = replay_metric(Path(args[0]))
    except (F5ReplayError, _TransportForbidden, ValueError, OSError) as error:
        print(f"replay_error={type(error).__name__}:{error}", file=sys.stderr)
        return 1
    print(f"metric={metric:g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
