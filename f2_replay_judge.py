"""LakatoTree-compatible replay judge for the F2 sealed measurement.

LakatoTree replays a producer with exactly one positional result path and
expects ``metric=<number>`` on stdout (p1v4_replay_judge.py pattern).  The
result path accepted here is the sealed F2 receipt
(``hswm-f2-delta-w-credit-receipt/v2``).  The judge:

  1. binds the receipt to the harness script it was produced by
     (``script_sha256``) and to the locked preregistration file,
  2. rebuilds the deterministic world from the receipt config (question pool,
     splits, lessons, placebo store, TMC/LOO seeds),
  3. recomputes EVERY number in the receipt from the on-disk LLM response
     cache (.f2_cache) with transport hard-forbidden (zero network — a cache
     miss aborts the replay), and
  4. requires BIT-EQUAL agreement (exact for accuracies, receipt-rounding for
     phi/LOO/rho) before printing the prereg primary metric
     ``credit_informed - random_edit`` on fresh heldout.

The judge never accepts a client-supplied value; it derives the metric again
through the deterministic measurement path.
"""
from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
import random
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

RECEIPT_SCHEMA = "hswm-f2-delta-w-credit-receipt/v2"


class F2ReplayError(ValueError):
    """The sealed F2 receipt cannot be regenerated bit-equally."""


class _TransportForbidden(Exception):
    """Replay attempted an LLM call that is not in the disk cache."""


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_receipt(path: Path) -> dict:
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise F2ReplayError(f"receipt unreadable: {type(error).__name__}") from error
    if not isinstance(receipt, dict):
        raise F2ReplayError("receipt must be a mapping")
    if receipt.get("schema_version") != RECEIPT_SCHEMA:
        raise F2ReplayError("receipt schema drifted")
    if receipt.get("aborted") is not None:
        raise F2ReplayError(f"receipt is an aborted run: {receipt['aborted']}")
    if receipt.get("smoke"):
        raise F2ReplayError("smoke receipts are not replayable evidence")
    return receipt


def _compare(label: str, recomputed, recorded, mismatches: list) -> None:
    if recomputed != recorded:
        mismatches.append({
            "field": label, "recorded": recorded, "recomputed": recomputed})


def replay_metric(receipt_path: Path) -> float:
    receipt = _load_receipt(receipt_path)

    # ---- bind harness script + preregistration ----
    harness_path = HERE / "f2_delta_w_credit.py"
    if not harness_path.is_file():
        raise F2ReplayError("harness script missing beside the judge")
    if _sha256_file(harness_path) != receipt.get("script_sha256"):
        raise F2ReplayError("harness script sha256 differs from the receipt")
    prereg_path = Path(receipt["preregistration_file"])
    if prereg_path.is_file():
        if _sha256_file(prereg_path) != receipt.get("preregistration_file_sha256"):
            raise F2ReplayError("preregistration file sha256 drifted")

    h = importlib.import_module("f2_delta_w_credit")

    # ---- hard-forbid any LLM transport (cache-only replay) ----
    def _forbidden_transport(req, timeout, backend):
        raise _TransportForbidden("replay attempted a non-cached LLM call")
    h._transport_with_backoff = _forbidden_transport

    config = receipt["config"]
    seed = int(config["seed"])
    n_lessons = int(config["lessons"])
    universes_dir = Path(config["universes_dir"])
    if not universes_dir.is_absolute():
        universes_dir = HERE / universes_dir

    # ---- rebuild the deterministic world ----
    pool, _stats = h.load_question_pool(universes_dir, int(config["max_answers"]))
    article_cache = h._ArticleCache(universes_dir)
    built = h.build_splits(pool, article_cache,
                           n_lessons=n_lessons,
                           n_dev=int(config["n_dev"]),
                           n_fresh=int(config["n_fresh"]),
                           max_answers=int(config["max_answers"]))
    train_cases = built["splits"]["train"]
    dev_cases = built["splits"]["dev"]
    fresh_cases = built["splits"]["fresh"]
    lessons, lesson_meta = h.compile_world_lessons(train_cases, n_lessons)
    lesson_ids = tuple(sorted(lessons))
    placebo_lessons, placebo_map = h.build_placebo_lessons(
        lessons, f"f2-placebo-{seed}")

    mismatches: list = []
    _compare("lesson_id_prefixes", sorted(l[:16] for l in lesson_ids),
             sorted(receipt["lessons"]), mismatches)
    _compare("placebo_id_map",
             {k[:16]: v[:16] for k, v in placebo_map.items()},
             receipt["placebo_store"]["lesson_id_map"], mismatches)

    # ---- cache-only backends ----
    budget = h.Budget(10 ** 9)
    if config["answer_backend"] == "vllm":
        answerer = h.CachedOpenAIChat(config["answer_url"], budget)
    else:
        answerer = h.CachedChat(config["answer_url"], budget)
    critic = h.CachedChat(config["critic_url"], budget)
    parallel = 4

    V_cache: dict = {}

    def V(subset_ids, cases):
        key = tuple(sorted(subset_ids))
        if key not in V_cache:
            V_cache[key] = h.evaluate_subset(
                answerer, config["answer_model"], key, cases, lessons,
                parallel, seed)
        return V_cache[key]

    # ---- base / full ----
    base_dev = V((), dev_cases)
    full_dev = V(lesson_ids, dev_cases)
    _compare("dev_base_accuracy", base_dev["accuracy"],
             receipt["dev_base_accuracy"], mismatches)
    _compare("dev_full_store_accuracy", full_dev["accuracy"],
             receipt["dev_full_store_accuracy"], mismatches)

    # ---- TMC-Shapley (same seed, same order) ----
    rng = random.Random(f"f2-tmc-{seed}")
    phi = {lid: [] for lid in lesson_ids}
    perms_run = 0
    for _ in range(int(config["m_shapley"])):
        perm = list(lesson_ids)
        rng.shuffle(perm)
        prefix: tuple = ()
        prev = V(prefix, dev_cases)["accuracy"]
        for lid in perm:
            new = V(prefix + (lid,), dev_cases)["accuracy"]
            phi[lid].append(new - prev)
            prefix = prefix + (lid,)
            prev = new
        perms_run += 1
    phi_mean = {lid: (sum(v) / len(v) if v else None) for lid, v in phi.items()}
    _compare("m_perms_run", perms_run, receipt["credit"]["m_perms_run"], mismatches)
    _compare("phi_tmc",
             {lid[:16]: (round(phi_mean[lid], 4) if phi_mean[lid] is not None else None)
              for lid in lesson_ids},
             receipt["credit"]["phi_tmc"], mismatches)

    # ---- measured LOO ----
    loo = {}
    v_full = full_dev["accuracy"]
    for lid in lesson_ids:
        rest = tuple(x for x in lesson_ids if x != lid)
        loo[lid] = v_full - V(rest, dev_cases)["accuracy"]
    _compare("loo_delta_v", {lid[:16]: round(loo[lid], 4) for lid in lesson_ids},
             receipt["credit"]["loo_delta_v"], mismatches)
    rho = h.spearman([phi_mean[lid] for lid in lesson_ids],
                     [loo[lid] for lid in lesson_ids])
    _compare("spearman_rho", (round(rho, 4) if rho is not None else None),
             receipt["credit"]["spearman_rho"], mismatches)
    _compare("spearman_pairs", len(lesson_ids),
             receipt["credit"]["spearman_pairs"], mismatches)
    _compare("distinct_subsets_evaluated", len(V_cache),
             receipt["credit"]["distinct_subsets_evaluated"], mismatches)

    # ---- arms ----
    ranked = sorted(lesson_ids, key=lambda lid: (-(phi_mean[lid] or 0.0), lid))
    delete_credit = tuple(sorted(ranked[-2:]))
    store_a = tuple(lid for lid in lesson_ids if lid not in delete_credit)
    plan_b = h.random_edit_plan(list(lesson_ids), 0, 2, 0, f"f2-random-edit-{seed}")
    delete_random = tuple(sorted(plan_b.deletes))
    store_b = tuple(lid for lid in lesson_ids if lid not in delete_random)
    _compare("arm_a_deleted", [l[:16] for l in delete_credit],
             receipt["arms"]["a_credit_informed"]["deleted"], mismatches)
    _compare("arm_b_deleted", [l[:16] for l in delete_random],
             receipt["arms"]["b_random_edit"]["deleted"], mismatches)

    accs: dict[str, float] = {}
    for arm_id, store in (("a_credit_informed", store_a), ("b_random_edit", store_b)):
        res = h.evaluate_subset(answerer, config["answer_model"], store,
                                fresh_cases, lessons, parallel, seed)
        accs[arm_id] = res["accuracy"]
        _compare(f"{arm_id}.fresh_accuracy", res["accuracy"],
                 receipt["arms"][arm_id]["fresh_accuracy"], mismatches)
        _compare(f"{arm_id}.fresh_parse_failures", res["parse_failures"],
                 receipt["arms"][arm_id]["fresh_parse_failures"], mismatches)

    delete_critic, _critic_meta = h.run_critic(
        critic, config["critic_model"], full_dev, lessons, seed)
    store_c = tuple(lid for lid in lesson_ids if lid not in delete_critic)
    res_c = h.evaluate_subset(answerer, config["answer_model"], store_c,
                              fresh_cases, lessons, parallel, seed)
    accs["c_verbal_gradient"] = res_c["accuracy"]
    _compare("arm_c_deleted", [l[:16] for l in delete_critic],
             receipt["arms"]["c_verbal_gradient"]["deleted"], mismatches)
    _compare("c_verbal_gradient.fresh_accuracy", res_c["accuracy"],
             receipt["arms"]["c_verbal_gradient"]["fresh_accuracy"], mismatches)

    delete_placebo = {placebo_map[lid] for lid in delete_credit}
    store_d = tuple(lid for lid in sorted(placebo_lessons)
                    if lid not in delete_placebo)
    res_d = h.evaluate_subset(answerer, config["answer_model"], store_d,
                              fresh_cases, placebo_lessons, parallel, seed)
    accs["d_deranged_placebo"] = res_d["accuracy"]
    _compare("d_deranged_placebo.fresh_accuracy", res_d["accuracy"],
             receipt["arms"]["d_deranged_placebo"]["fresh_accuracy"], mismatches)

    # ---- kill observations + leakage ----
    kills = receipt["kill_condition_observations"]
    _compare("f2_k1", (accs["a_credit_informed"] - accs["b_random_edit"]) <= 0,
             kills["f2_k1_credit_informed_minus_random_le_0"], mismatches)
    _compare("f2_k2", accs["d_deranged_placebo"] >= accs["a_credit_informed"],
             kills["f2_k2_placebo_ge_credit"], mismatches)
    _compare("f2_k3", base_dev["accuracy"] >= h.SATURATION_BASE,
             kills["f2_k3_saturation_base_ge_5_6"], mismatches)
    leak = h.leakage_report(train_cases, dev_cases, fresh_cases)
    _compare("leakage_binding", leak["binding_leakage"],
             receipt["leakage"]["binding_leakage"], mismatches)

    # ---- zero-transport proof: every logical call was a cache hit ----
    expected_answerer = receipt["llm_budget"]["answerer"]["misses"]
    expected_critic = receipt["llm_budget"]["critic"]["misses"]
    _compare("answerer_cache_hits_equal_original_misses", answerer.hits,
             expected_answerer, mismatches)
    _compare("critic_cache_hits_equal_original_misses", critic.hits,
             expected_critic, mismatches)
    if answerer.misses or critic.misses:
        mismatches.append({"field": "transport_free",
                           "recorded": 0,
                           "recomputed": answerer.misses + critic.misses})

    if mismatches:
        raise F2ReplayError(json.dumps(
            {"mismatches": mismatches[:20], "total": len(mismatches)},
            ensure_ascii=False))
    return accs["a_credit_informed"] - accs["b_random_edit"]


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1 or args[0].startswith("-"):
        print("replay_error=usage: f2_replay_judge.py <receipt_path>", file=sys.stderr)
        return 1
    try:
        metric = replay_metric(Path(args[0]))
    except (F2ReplayError, _TransportForbidden, ValueError, OSError) as error:
        print(f"replay_error={type(error).__name__}:{error}", file=sys.stderr)
        return 1
    print(f"metric={metric:g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
