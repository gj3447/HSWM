"""LakatoTree-compatible replay judge for the F3-r3 sealed measurement.

LakatoTree replays a producer with exactly one positional result path and
expects ``metric=<number>`` on stdout (f2/f4/f5_replay_judge.py pattern).
The result path accepted here is the sealed F3-r3 receipt
(``hswm-f3-agent-ab-transfer-r3-receipt/v1``).  The judge:

  1. binds the receipt to the harness scripts (script_sha256 +
     harness_module_sha256) and to the locked preregistration,
  2. rebuilds the deterministic world from the receipt config (splits,
     gold-blind donor and B-self derivation, deltaW edit logs, placebo
     store, token-capped raw log),
  3. re-seals BOTH transfer packets and requires packet_sha256 +
     lesson_merkle_root + corpus_manifest_sha256 + file_sha256 equality,
  4. recomputes EVERY number in the receipt from the on-disk LLM response
     cache (.f2_cache) with transport hard-forbidden (zero network), and
  5. requires BIT-EQUAL agreement before printing the prereg primary
     metric ``B1 - max(B0, B2, B3)``.

All RNG is seeded and all shuffle inputs are sorted — no string-hash-seed
dependence (the F4 bug class).  The judge never accepts a client-supplied
value; it derives the metric again through the deterministic path.
"""
from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

RECEIPT_SCHEMA = "hswm-f3-agent-ab-transfer-r3-receipt/v1"


class F3ReplayError(ValueError):
    """The sealed F3 receipt cannot be regenerated bit-equally."""


class _TransportForbidden(Exception):
    """Replay attempted an LLM call that is not in the disk cache."""


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_receipt(path: Path) -> dict:
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise F3ReplayError(f"receipt unreadable: {type(error).__name__}") from error
    if not isinstance(receipt, dict):
        raise F3ReplayError("receipt must be a mapping")
    if receipt.get("schema_version") != RECEIPT_SCHEMA:
        raise F3ReplayError("receipt schema drifted")
    if receipt.get("aborted") is not None:
        raise F3ReplayError(f"receipt is an aborted run: {receipt['aborted']}")
    if receipt.get("smoke"):
        raise F3ReplayError("smoke receipts are not replayable evidence")
    return receipt


def _compare(label: str, recomputed, recorded, mismatches: list) -> None:
    if recomputed != recorded:
        mismatches.append({
            "field": label, "recorded": recorded, "recomputed": recomputed})


def replay_metric(receipt_path: Path) -> float:
    receipt = _load_receipt(receipt_path)

    harness_path = HERE / "f3_agent_ab_transfer_r3.py"
    if not harness_path.is_file():
        raise F3ReplayError("f3-r3 harness script missing beside the judge")
    if _sha256_file(harness_path) != receipt.get("script_sha256"):
        raise F3ReplayError("f3-r3 harness script sha256 differs from the receipt")
    for rel, sha in receipt.get("harness_module_sha256", {}).items():
        p = HERE / rel
        if not p.is_file() or _sha256_file(p) != sha:
            raise F3ReplayError(f"harness module drifted: {rel}")
    prereg_path = Path(receipt["preregistration_file"])
    if prereg_path.is_file():
        if _sha256_file(prereg_path) != receipt.get("preregistration_file_sha256"):
            raise F3ReplayError("preregistration file sha256 drifted")

    f2 = importlib.import_module("f2_delta_w_credit")
    f3r1 = importlib.import_module("f3_agent_ab_transfer")
    f3r2 = importlib.import_module("f3_agent_ab_transfer_r2")
    m = importlib.import_module("f3_agent_ab_transfer_r3")

    def _forbidden_transport(req, timeout, backend):
        raise _TransportForbidden("replay attempted a non-cached LLM call")
    f2._transport_with_backoff = _forbidden_transport

    config = receipt["config"]
    seed = int(config["seed"])
    n_fresh = int(config["n_fresh"])
    train_per_world = int(config["train_per_world"])
    universes_dir = Path(config["universes_dir"])
    if not universes_dir.is_absolute():
        universes_dir = HERE / universes_dir

    # ---- rebuild the deterministic world ----
    worlds = f3r2.make_worlds(6)
    pool, _stats = f2.load_question_pool(universes_dir, int(config["max_answers"]))
    article_cache = f2._ArticleCache(universes_dir)
    built = f3r2.build_splits_r2(pool, article_cache, worlds=worlds,
                                 train_per_world=train_per_world,
                                 n_fresh=n_fresh,
                                 max_answers=int(config["max_answers"]),
                                 split_seed=int(config["split_seed"]))
    train_cases = built["splits"]["train"]
    fresh_cases = built["splits"]["fresh"]

    mismatches: list = []
    _compare("fresh_case_worlds", [w for _c, w, _q, _u in fresh_cases],
             receipt["splits"]["fresh_case_worlds"], mismatches)
    leak = f2.leakage_report(train_cases, [], fresh_cases)
    _compare("leakage_binding", leak["binding_leakage"],
             receipt["leakage"]["binding_leakage"], mismatches)

    budget = f2.Budget(10 ** 9)
    donor = f2.CachedOpenAIChat(config["donor_url"], budget)
    receiver = f2.CachedChat(config["receiver_url"], budget)

    # ---- gold-blind derivation (A and B-self, symmetric) ----
    lessons_a, deriv_a, edits_a = m.blind_pipeline(
        donor, config["donor_model"], worlds, train_cases,
        4, seed)
    lessons_b, deriv_b, edits_b = m.blind_pipeline(
        receiver, config["receiver_model"], worlds, train_cases,
        4, seed)
    _compare("donor_a_block", {
        "model": config["donor_model"], "n_lessons": len(lessons_a),
        "solve_accuracy": sum(d["solve_correct"] for d in deriv_a.values()) / len(deriv_a),
        "orientations": {str(w): deriv_a[w]["orientation"] for w in sorted(deriv_a)},
        "n_invalid_beliefs": sum(1 for d in deriv_a.values() if d["belief"] is None),
    }, receipt["donor_a"], mismatches)
    _compare("b_self_block", {
        "model": config["receiver_model"], "n_lessons": len(lessons_b),
        "solve_accuracy": sum(d["solve_correct"] for d in deriv_b.values()) / len(deriv_b),
        "orientations": {str(w): deriv_b[w]["orientation"] for w in sorted(deriv_b)},
        "n_invalid_beliefs": sum(1 for d in deriv_b.values() if d["belief"] is None),
    }, receipt["b_self"], mismatches)
    bself_wrong = [
        {"world": w, "belief": deriv_b[w]["belief"],
         "ground_truth": deriv_b[w]["ground_truth"],
         "model_answers": deriv_b[w]["model_answers"],
         "support": deriv_b[w]["support"]}
        for w in sorted(deriv_b)
        if deriv_b[w]["orientation"] in ("inverted", None)]
    _compare("survival_b_self_wrong_beliefs", len(bself_wrong),
             receipt["derivation_survival_check"]["b_self_wrong_beliefs"], mismatches)
    _compare("survival_cases", bself_wrong,
             receipt["derivation_survival_check"]["cases"], mismatches)

    by_id_a = {l.lesson_id: l for l in lessons_a.values()}
    by_id_b = {l.lesson_id: l for l in lessons_b.values()}
    placebo_lessons, _placebo_map = f2.build_placebo_lessons(
        by_id_a, f"f3r3-placebo-{seed}")
    by_id_p = placebo_lessons

    # ---- re-seal both packets (temp files; full sha equality) ----
    with tempfile.TemporaryDirectory(prefix="f3-replay-") as tmp:
        pa = Path(tmp) / "pa.json"
        pb = Path(tmp) / "pb.json"
        packet = f3r1.seal_packet(
            donor={"backend": "vllm", "url": config["donor_url"],
                   "model": config["donor_model"]},
            train_cases=train_cases, lessons=lessons_a, edits=edits_a,
            out_path=pa)
        packet_b = f3r1.seal_packet(
            donor={"backend": "ollama", "url": config["receiver_url"],
                   "model": config["receiver_model"], "role": "b_self"},
            train_cases=train_cases, lessons=lessons_b, edits=edits_b,
            out_path=pb)
        rec_pa = receipt["packets"]["donor_a"]
        rec_pb = receipt["packets"]["b_self"]
        _compare("packet_a_sha256", packet["packet_sha256"],
                 rec_pa["packet_sha256"], mismatches)
        _compare("packet_a_merkle", packet["lesson_merkle_root"],
                 rec_pa["lesson_merkle_root"], mismatches)
        _compare("packet_a_corpus_manifest",
                 packet["experience"]["corpus_manifest_sha256"],
                 rec_pa["corpus_manifest_sha256"], mismatches)
        _compare("packet_a_file_sha256", _sha256_file(pa),
                 rec_pa["file_sha256"], mismatches)
        _compare("packet_a_counts",
                 {"n_lessons": len(packet["lessons"]),
                  "n_deletes": sum(1 for e in edits_a if e["op"] == "delete")},
                 {"n_lessons": rec_pa["n_lessons"],
                  "n_deletes": rec_pa["n_deletes"]}, mismatches)
        _compare("packet_b_sha256", packet_b["packet_sha256"],
                 rec_pb["packet_sha256"], mismatches)
        _compare("packet_b_file_sha256", _sha256_file(pb),
                 rec_pb["file_sha256"], mismatches)
        _compare("packet_b_counts",
                 {"n_lessons": len(packet_b["lessons"]),
                  "n_deletes": sum(1 for e in edits_b if e["op"] == "delete")},
                 {"n_lessons": rec_pb["n_lessons"],
                  "n_deletes": rec_pb["n_deletes"]}, mismatches)

    # ---- arms ----
    kept_a = tuple(sorted(e["target"] for e in edits_a if e["op"] == "keep"))
    kept_b = tuple(sorted(e["target"] for e in edits_b if e["op"] == "keep"))
    placebo_ids = tuple(sorted(by_id_p))
    kept_placebo = tuple(sorted(_placebo_map[t] for t in kept_a))
    from p1v3_policy_environment import render_policy_training_transcript
    from p1v2_typed_lesson import render_lesson_context, retrieve_lessons
    raw_log_full = "\n".join(render_policy_training_transcript(item[0])
                             for item in train_cases)
    if kept_a:
        ref_q = fresh_cases[0][0].question
        ref_lessons = [by_id_a[i] for i in kept_a]
        b1_ref_ctx = render_lesson_context(
            retrieve_lessons(ref_q, ref_lessons, top_k=len(ref_lessons)),
            ref_lessons)
    else:
        b1_ref_ctx = ""
    raw_log = raw_log_full[:max(len(b1_ref_ctx), 200)]
    _compare("token_envelope", {
        "b1_context_chars": len(b1_ref_ctx),
        "b3_raw_log_chars_full": len(raw_log_full),
        "b3_raw_log_chars_capped": len(raw_log),
    }, receipt["token_envelope"], mismatches)

    arm_ctxs = {
        "B0_no_experience": ("none",),
        "B1_full_packet": ("lessons", kept_a),
        "B2_placebo_lessons": ("lessons", placebo_ids),
        "B3_raw_log_only": ("raw", raw_log),
        "B4a_lessons_only": ("lessons", tuple(sorted(by_id_a))),
        "B4b_deltaW_only": ("lessons", kept_placebo),
        "B5_b_self_lessons": ("lessons", kept_b),
    }
    arms = {}
    for arm_id, ctx in arm_ctxs.items():
        by_id = by_id_p if arm_id in ("B2_placebo_lessons", "B4b_deltaW_only") \
            else (by_id_b if arm_id == "B5_b_self_lessons" else by_id_a)
        keep_ans = arm_id in ("B1_full_packet", "B5_b_self_lessons")
        arms[arm_id] = f3r1.eval_ctx(
            receiver, config["receiver_model"], ctx, fresh_cases,
            by_id, 4, seed, keep_answers=keep_ans)
        rec_arm = receipt["arms"][arm_id]
        _compare(f"{arm_id}.fresh_accuracy", arms[arm_id]["accuracy"],
                 rec_arm["fresh_accuracy"], mismatches)
        _compare(f"{arm_id}.fresh_parse_failures",
                 arms[arm_id]["parse_failures"],
                 rec_arm["fresh_parse_failures"], mismatches)
        n_ctx = len(ctx[1]) if ctx[0] == "lessons" else 0
        _compare(f"{arm_id}.n_context_lessons", n_ctx,
                 rec_arm["n_context_lessons"], mismatches)

    a_fresh = f3r1.eval_ctx(donor, config["donor_model"], ("lessons", kept_a),
                            fresh_cases, by_id_a, 4, seed, keep_answers=True)

    # ---- G and S ----
    n_boot = int(config["n_boot"])
    acc = {k: v["accuracy"] for k, v in arms.items()}
    G = acc["B1_full_packet"] - acc["B5_b_self_lessons"]
    g_ci = f3r1.bootstrap_gap(arms["B1_full_packet"]["correct_vector"],
                              arms["B5_b_self_lessons"]["correct_vector"],
                              n_boot=n_boot, seed=seed)
    rows_b1 = arms["B1_full_packet"]["rows"]
    rows_b5 = arms["B5_b_self_lessons"]["rows"]
    rows_a = a_fresh["rows"]
    s_cos_b1 = f3r1.dist_cosine(rows_b1, rows_a)
    s_cos_b5 = f3r1.dist_cosine(rows_b5, rows_a)
    S = s_cos_b1 - s_cos_b5
    s_ci = f3r1.bootstrap_s_gap(rows_b1, rows_b5, rows_a,
                                n_boot=n_boot, seed=seed)
    jac_b1 = sum(f3r1.case_jaccard(rx, ra)
                 for rx, ra in zip(rows_b1, rows_a)) / len(rows_a)
    jac_b5 = sum(f3r1.case_jaccard(rx, ra)
                 for rx, ra in zip(rows_b5, rows_a)) / len(rows_a)
    _compare("discriminators", {
        "G": round(G, 4), "G_ci95": [round(x, 4) for x in g_ci["ci95"]],
        "S": round(S, 4), "S_ci95": [round(x, 4) for x in s_ci["ci95"]],
        "S_components": {"dist_cosine_B1_A": round(s_cos_b1, 4),
                         "dist_cosine_B5_A": round(s_cos_b5, 4)},
        "S_secondary_jaccard": {"mean_B1_A": round(jac_b1, 4),
                                "mean_B5_A": round(jac_b5, 4)},
        "S_method": receipt["discriminators"]["S_method"],
    }, receipt["discriminators"], mismatches)

    # ---- kills ----
    kills = receipt["kill_condition_observations"]
    _compare("f3_k1", G <= 0, kills["f3_k1_G_le_0"], mismatches)
    _compare("f3_k2", S <= 0, kills["f3_k2_S_le_0"], mismatches)
    _compare("f3_k3", acc["B1_full_packet"] <= max(
        acc["B0_no_experience"], acc["B2_placebo_lessons"],
        acc["B3_raw_log_only"]), kills["f3_k3_B1_le_max_B0_B2_B3"], mismatches)
    _compare("f3_k3_sub", acc["B1_full_packet"] <= acc["B3_raw_log_only"],
             kills["f3_k3_sub_B1_le_B3"], mismatches)
    _compare("f3_k4", acc["B0_no_experience"] >= (5 / 6),
             kills["f3_k4_saturation_B0_ge_5_6"], mismatches)
    _compare("kill_values", {k: round(v, 4) for k, v in acc.items()},
             kills["values"], mismatches)

    # ---- zero-transport proof ----
    if donor.misses or receiver.misses:
        mismatches.append({"field": "transport_free",
                           "recorded": 0,
                           "recomputed": donor.misses + receiver.misses})
    _compare("donor_calls", donor.hits,
             receipt["llm_budget"]["donor"]["misses"]
             + receipt["llm_budget"]["donor"]["hits"], mismatches)
    _compare("receiver_calls", receiver.hits,
             receipt["llm_budget"]["receiver"]["misses"]
             + receipt["llm_budget"]["receiver"]["hits"], mismatches)
    _compare("total_logical_calls", donor.hits + receiver.hits,
             receipt["llm_budget"]["total_logical"], mismatches)

    if mismatches:
        raise F3ReplayError(json.dumps(
            {"mismatches": mismatches[:20], "total": len(mismatches)},
            ensure_ascii=False))

    return acc["B1_full_packet"] - max(
        acc["B0_no_experience"], acc["B2_placebo_lessons"],
        acc["B3_raw_log_only"])


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1 or args[0].startswith("-"):
        print("replay_error=usage: f3_replay_judge.py <receipt_path>", file=sys.stderr)
        return 1
    try:
        metric = replay_metric(Path(args[0]))
    except (F3ReplayError, _TransportForbidden, ValueError, OSError) as error:
        print(f"replay_error={type(error).__name__}:{error}", file=sys.stderr)
        return 1
    print(f"metric={metric:g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
