"""F3-r3 gate (Agent A -> frozen-B transfer) — gold-blind derivation, strong->weak.

PREREG (locked, read-only input): prom_search_hswm/evidence/
PREREG_f3_agent_ab_transfer_20260725.json (in the SYMPOSIUM/HSWM checkout).

r3 rationale (parent decision 2026-07-26): r1 (2-class) and r2 (4-class)
both died structurally — with the verified outcome REVEALED, every donor
(qwen3:14b, qwen3:8b, qwen3.6-27b) aced the verdict, so A lessons were
byte-identical to B-self lessons and G == 0.  r3 removes the reveal:
derivation is GOLD-BLIND and symmetric for donor and B-self — each model
first SOLVES the train case with no lesson and no gold, then believes the
class whose documents support its OWN answer, and the lesson is compiled
from that belief.  A weak model falls for forged decoy claims and derives
inverted lessons, so authorship drives lesson quality and G can live.
(prereg reading deviation, recorded in every receipt: oracle/verified
-outcome admission -> gold-blind self-verdict derivation; B5's "same
experience, self-generated" definition is preserved — the experience is
the same cases, the derivation is B's own.)

Roles (parent decision): donor A = vLLM qwen3.6-27b (STRONG); receiver B
(frozen) = ollama qwen3:8b (WEAK, native /api/chat think=false).  B-self
runs the identical blind pipeline on the receiver model, so B1 vs B5
differs ONLY in who authored the lessons.  G = Acc(B1) - Acc(B5);
S = dist_cosine(B1 answers, A answers) - dist_cosine(B5 answers, A
answers) with paired bootstrap CI (dark-knowledge signature).  Scoring is
gold exact-set-match — gold is hidden only at LESSON-DERIVATION time,
never at evaluation time.

Belief extraction is deterministic (no extra LLM call): support(class) =
number of the model's normalized answer strings that appear in that
class's documents; belief = argmax (ties -> class code asc); all-zero
support -> no lesson for that world (recorded invalid).

Everything else mirrors r2: multi-class cases (1 trusted + 3 distractors,
p1v3_multi_environment.py), deltaW typed edit log (harmful on the two
remaining train cases -> delete), sealed packets (sha256 + Merkle +
corpus manifest), arms B0/B1/B2/B3(token-capped)/B4a/B4b/B5, kills
f3_k1..k4.  Receipts are always mode="development" measurements.

Usage:
  .venv/bin/python f3_agent_ab_transfer_r3.py --smoke
  .venv/bin/python f3_agent_ab_transfer_r3.py --universes-dir _research/f2_sealed_universes
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
from pathlib import Path
import random
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
NULL_BATTERY_DIR = Path("/Users/lagyeongjun/CD/SYMPOSIUM/HSWM/prom_search_hswm")
sys.path.insert(0, str(NULL_BATTERY_DIR))

f2 = importlib.import_module("f2_delta_w_credit")
f3r1 = importlib.import_module("f3_agent_ab_transfer")
f3r2 = importlib.import_module("f3_agent_ab_transfer_r2")

from hswm_null_battery import headroom_band_ok  # noqa: E402

PREREG_PATH = NULL_BATTERY_DIR / "evidence" / "PREREG_f3_agent_ab_transfer_20260725.json"
RECEIPT_DIR = HERE / "receipts"
HEADROOM_BAND = (0.3, 0.7)
SATURATION_B0 = 5 / 6


class F3R3Error(RuntimeError):
    pass


def infer_belief(case, answers: list[str]) -> tuple[str | None, dict]:
    """Which class's documents SUPPORT the model's own answer (deterministic).

    Support is claim-level, not name-level: PhantomWiki articles mention
    related people by name, so a name substring match ties across docs.
    The discriminating line is "the {attribute} of {answer} is {value}." —
    it exists in exactly one document (the true article for a true answer,
    the forged decoy for a decoy answer)."""
    from p1v2_type6_environment import parse_type6_question
    query = parse_type6_question(case.question)
    vals = [" ".join(str(a).casefold().split()) for a in answers if str(a).strip()]
    support = {}
    for klass in case.candidate_classes:
        text = " ".join(
            " ".join(d.text.casefold().split()) for d in case.documents
            if d.text.startswith(f"[SOURCE_CLASS={klass}]"))
        support[klass] = sum(
            1 for v in vals
            if v and f"the {query.attribute} of {v} is {query.value}." in text)
    top = max(support.values()) if support else 0
    if top == 0:
        return None, support
    winners = sorted(k for k, v in support.items() if v == top)
    return winners[0], support


def blind_pipeline(chat, model: str, worlds, train_cases, parallel: int,
                   seed: int):
    """Gold-blind solve -> belief -> lesson; then deltaW edit log."""
    per_world: dict[int, list] = {}
    for item in train_cases:
        per_world.setdefault(item[1], []).append(item)
    lessons: dict[int, object] = {}
    derivations: dict[int, dict] = {}
    for world in worlds:
        w = world["world_idx"]
        item1 = per_world[w][0]
        case1 = item1[0]
        res = f3r1.eval_ctx(chat, model, ("none",), [item1], {}, parallel,
                            seed, keep_answers=True)
        row = res["rows"][0]
        belief, support = infer_belief(case1, row["answers"])
        gold = set(f2.normalized_set(case1.expected_answers))
        solve_correct = int(f2.normalized_set(row["answers"]) == gold)
        derivations[w] = {
            "model_answers": row["answers"], "parse_ok": row["parse_ok"],
            "solve_correct": solve_correct,
            "belief": belief, "support": support,
            "ground_truth": case1.trusted_class,
            "orientation": (("correct" if belief == case1.trusted_class else "inverted")
                            if belief else None),
        }
        if belief is not None:
            lessons[w] = f3r2.compile_multi_lesson(case1, teach=belief)
    by_id = {l.lesson_id: l for l in lessons.values()}
    edits = []
    for w in sorted(lessons):
        lid = lessons[w].lesson_id
        acc_with = acc_without = 0
        for item in per_world[w][1:]:
            res_with = f3r1.eval_ctx(chat, model, ("lessons", (lid,)), [item],
                                     by_id, parallel, seed)
            res_without = f3r1.eval_ctx(chat, model, ("none",), [item],
                                        by_id, parallel, seed)
            acc_with += res_with["correct_vector"][0]
            acc_without += res_without["correct_vector"][0]
        op = "delete" if acc_with < acc_without else "keep"
        edits.append({
            "op": op, "target": lid,
            "evidence": {"n_cases": len(per_world[w]) - 1,
                         "acc_with_lesson": acc_with,
                         "acc_without_lesson": acc_without},
        })
    return lessons, derivations, edits


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-fresh", type=int, default=100)
    ap.add_argument("--train-per-world", type=int, default=3)
    ap.add_argument("--split-seed", type=int, default=20260728)
    ap.add_argument("--seed", type=int, default=20260725)
    ap.add_argument("--max-answers", type=int, default=1)
    ap.add_argument("--max-calls", type=int, default=1500)
    ap.add_argument("--parallel-b", type=int, default=4)
    ap.add_argument("--parallel-a", type=int, default=16)
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--universes-dir", type=Path,
                    default=HERE / "_research" / "f2_sealed_universes")
    ap.add_argument("--donor-url", default="http://127.0.0.1:18000/v1")
    ap.add_argument("--donor-model", default="qwen3.6-27b")
    ap.add_argument("--receiver-url", default="http://127.0.0.1:11434")
    ap.add_argument("--receiver-model", default="qwen3:8b")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    if args.smoke:
        args.n_fresh = 6
        args.max_calls = 150
    worlds = f3r2.make_worlds(6)
    t0 = time.time()
    ts = int(t0)
    out_path = Path(args.out) if args.out else (
        RECEIPT_DIR / f"f3r3_agent_ab_transfer_{'smoke' if args.smoke else 'sealed'}_{ts}.json")
    packet_path = RECEIPT_DIR / f"f3r3_transfer_packet_{ts}.json"
    packet_b_path = RECEIPT_DIR / f"f3r3_transfer_packet_bself_{ts}.json"

    receipt = {
        "schema_version": "hswm-f3-agent-ab-transfer-r3-receipt/v1",
        "mode": "development",
        "branch": "F3-agent-ab-transfer",
        "smoke": bool(args.smoke),
        "preregistration_file": str(PREREG_PATH),
        "preregistration_file_sha256": hashlib.sha256(
            PREREG_PATH.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "harness_module_sha256": {
            "f2_delta_w_credit.py": hashlib.sha256(
                (HERE / "f2_delta_w_credit.py").read_bytes()).hexdigest(),
            "f3_agent_ab_transfer.py": hashlib.sha256(
                (HERE / "f3_agent_ab_transfer.py").read_bytes()).hexdigest(),
            "f3_agent_ab_transfer_r2.py": hashlib.sha256(
                (HERE / "f3_agent_ab_transfer_r2.py").read_bytes()).hexdigest(),
            "p1v3_multi_environment.py": hashlib.sha256(
                (HERE / "p1v3_multi_environment.py").read_bytes()).hexdigest(),
        },
        "prereg_reading_deviation": (
            "r3 (parent decision 2026-07-26): lesson derivation is GOLD-BLIND "
            "(no verified-outcome reveal) — each model solves the train case "
            "and believes the class supporting its own answer (deterministic "
            "support scoring); r1/r2 used verified-outcome-revealed verdicts "
            "which every model aced, killing G structurally.  Roles: donor "
            "A = vLLM qwen3.6-27b (strong), receiver B = ollama qwen3:8b "
            "(weak, frozen).  B5 keeps the prereg 'same experience, "
            "self-generated' definition.  Gold is hidden only at derivation; "
            "evaluation scoring is gold exact-set-match as preregistered."),
        "config": vars(args) | {"out": str(out_path),
                                "universes_dir": str(args.universes_dir)},
        "donor_freeze": {"backend": "vllm", "url": args.donor_url,
                         "model": args.donor_model,
                         "thinking_off": "chat_template_kwargs enable_thinking=false"},
        "receiver_freeze": {
            "backend": "ollama", "url": args.receiver_url,
            "model": args.receiver_model,
            "thinking_off": "native /api/chat think=false",
            "system_prompt_sha256": hashlib.sha256(
                f2.P1V2_SYSTEM_PROMPT.encode()).hexdigest(),
            "seed": args.seed, "temperature": 0, "max_tokens": 256,
            "note": "B frozen; only memory_context varies across arms.",
        },
        "honesty": "grounded measurement only; no scientific claim; judgment is the gate's",
    }
    budget = f2.Budget(args.max_calls)
    donor = f2.CachedOpenAIChat(args.donor_url, budget)
    receiver = f2.CachedChat(args.receiver_url, budget)
    aborted = None
    try:
        pool, pool_stats = f2.load_question_pool(args.universes_dir, args.max_answers)
        receipt["question_pool"] = pool_stats
        article_cache = f2._ArticleCache(args.universes_dir)
        built = f3r2.build_splits_r2(pool, article_cache, worlds=worlds,
                                     train_per_world=args.train_per_world,
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

        lessons_a, deriv_a, edits_a = blind_pipeline(
            donor, args.donor_model, worlds, train_cases,
            args.parallel_a, args.seed)
        lessons_b, deriv_b, edits_b = blind_pipeline(
            receiver, args.receiver_model, worlds, train_cases,
            args.parallel_b, args.seed)
        receipt["donor_a"] = {
            "model": args.donor_model, "n_lessons": len(lessons_a),
            "solve_accuracy": sum(d["solve_correct"] for d in deriv_a.values()) / len(deriv_a),
            "orientations": {str(w): deriv_a[w]["orientation"] for w in sorted(deriv_a)},
            "n_invalid_beliefs": sum(1 for d in deriv_a.values() if d["belief"] is None),
        }
        receipt["b_self"] = {
            "model": args.receiver_model, "n_lessons": len(lessons_b),
            "solve_accuracy": sum(d["solve_correct"] for d in deriv_b.values()) / len(deriv_b),
            "orientations": {str(w): deriv_b[w]["orientation"] for w in sorted(deriv_b)},
            "n_invalid_beliefs": sum(1 for d in deriv_b.values() if d["belief"] is None),
        }
        bself_wrong = [
            {"world": w, "belief": deriv_b[w]["belief"],
             "ground_truth": deriv_b[w]["ground_truth"],
             "model_answers": deriv_b[w]["model_answers"],
             "support": deriv_b[w]["support"]}
            for w in sorted(deriv_b)
            if deriv_b[w]["orientation"] in ("inverted", None)]
        receipt["derivation_survival_check"] = {
            "b_self_wrong_beliefs": len(bself_wrong),
            "cases": bself_wrong,
            "note": "r3 survival check: G can live only if B-self (8b) derives "
                    "at least one wrong/inverted lesson.  If zero, A==B-self "
                    "again and G is structurally 0 — report and stop.",
        }

        by_id_a = {l.lesson_id: l for l in lessons_a.values()}
        by_id_b = {l.lesson_id: l for l in lessons_b.values()}
        placebo_lessons, _placebo_map = f2.build_placebo_lessons(
            by_id_a, f"f3r3-placebo-{args.seed}")
        by_id_p = placebo_lessons

        packet = f3r1.seal_packet(
            donor={"backend": "vllm", "url": args.donor_url,
                   "model": args.donor_model},
            train_cases=train_cases, lessons=lessons_a, edits=edits_a,
            out_path=packet_path)
        packet_b = f3r1.seal_packet(
            donor={"backend": "ollama", "url": args.receiver_url,
                   "model": args.receiver_model, "role": "b_self"},
            train_cases=train_cases, lessons=lessons_b, edits=edits_b,
            out_path=packet_b_path)
        receipt["packets"] = {
            "donor_a": {"path": str(packet_path),
                        "file_sha256": hashlib.sha256(packet_path.read_bytes()).hexdigest(),
                        "packet_sha256": packet["packet_sha256"],
                        "lesson_merkle_root": packet["lesson_merkle_root"],
                        "corpus_manifest_sha256": packet["experience"]["corpus_manifest_sha256"],
                        "n_lessons": len(packet["lessons"]),
                        "n_deletes": sum(1 for e in edits_a if e["op"] == "delete")},
            "b_self": {"path": str(packet_b_path),
                       "file_sha256": hashlib.sha256(packet_b_path.read_bytes()).hexdigest(),
                       "packet_sha256": packet_b["packet_sha256"],
                       "n_lessons": len(packet_b["lessons"]),
                       "n_deletes": sum(1 for e in edits_b if e["op"] == "delete")},
        }

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
        receipt["token_envelope"] = {
            "b1_context_chars": len(b1_ref_ctx),
            "b3_raw_log_chars_full": len(raw_log_full),
            "b3_raw_log_chars_capped": len(raw_log),
        }

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
                receiver, args.receiver_model, ctx, fresh_cases,
                by_id, args.parallel_b, args.seed, keep_answers=keep_ans)
        receipt["arms"] = {
            k: {"context_kind": arm_ctxs[k][0],
                "n_context_lessons": (len(arm_ctxs[k][1]) if arm_ctxs[k][0] == "lessons" else 0),
                "fresh_accuracy": v["accuracy"],
                "fresh_parse_failures": v["parse_failures"]}
            for k, v in arms.items()}

        a_fresh = f3r1.eval_ctx(donor, args.donor_model, ("lessons", kept_a),
                                fresh_cases, by_id_a, args.parallel_a, args.seed,
                                keep_answers=True)

        acc = {k: v["accuracy"] for k, v in arms.items()}
        G = acc["B1_full_packet"] - acc["B5_b_self_lessons"]
        g_ci = f3r1.bootstrap_gap(arms["B1_full_packet"]["correct_vector"],
                                  arms["B5_b_self_lessons"]["correct_vector"],
                                  n_boot=args.n_boot, seed=args.seed)
        rows_b1 = arms["B1_full_packet"]["rows"]
        rows_b5 = arms["B5_b_self_lessons"]["rows"]
        rows_a = a_fresh["rows"]
        s_cos_b1 = f3r1.dist_cosine(rows_b1, rows_a)
        s_cos_b5 = f3r1.dist_cosine(rows_b5, rows_a)
        S = s_cos_b1 - s_cos_b5
        s_ci = f3r1.bootstrap_s_gap(rows_b1, rows_b5, rows_a,
                                    n_boot=args.n_boot, seed=args.seed)
        jac_b1 = sum(f3r1.case_jaccard(rx, ra)
                     for rx, ra in zip(rows_b1, rows_a)) / len(rows_a)
        jac_b5 = sum(f3r1.case_jaccard(rx, ra)
                     for rx, ra in zip(rows_b5, rows_a)) / len(rows_a)
        receipt["discriminators"] = {
            "G": round(G, 4), "G_ci95": [round(x, 4) for x in g_ci["ci95"]],
            "S": round(S, 4), "S_ci95": [round(x, 4) for x in s_ci["ci95"]],
            "S_components": {"dist_cosine_B1_A": round(s_cos_b1, 4),
                             "dist_cosine_B5_A": round(s_cos_b5, 4)},
            "S_secondary_jaccard": {"mean_B1_A": round(jac_b1, 4),
                                    "mean_B5_A": round(jac_b5, 4)},
            "S_method": "as r1 (normalized answer-set distribution cosine + "
                        "paired bootstrap CI; secondary per-case Jaccard).",
        }
        receipt["headroom_band"] = list(HEADROOM_BAND)
        receipt["headroom_band_ok"] = headroom_band_ok(
            acc["B0_no_experience"], *HEADROOM_BAND)
        receipt["kill_condition_observations"] = {
            "f3_k1_G_le_0": G <= 0,
            "f3_k2_S_le_0": S <= 0,
            "f3_k3_B1_le_max_B0_B2_B3": acc["B1_full_packet"] <= max(
                acc["B0_no_experience"], acc["B2_placebo_lessons"],
                acc["B3_raw_log_only"]),
            "f3_k3_sub_B1_le_B3": acc["B1_full_packet"] <= acc["B3_raw_log_only"],
            "f3_k4_saturation_B0_ge_5_6": acc["B0_no_experience"] >= SATURATION_B0,
            "values": {k: round(v, 4) for k, v in acc.items()},
            "note": "mechanical observation only; sealed judgment belongs to the gate",
        }
    except (F3R3Error, f2.BudgetExceeded) as err:
        aborted = str(err)
    except Exception as err:  # noqa: BLE001
        aborted = f"{type(err).__name__}: {err}"

    receipt["llm_budget"] = {
        "max_calls": args.max_calls, "used": budget.used,
        "donor": {"model": args.donor_model,
                  "misses": donor.misses, "hits": donor.hits},
        "receiver": {"model": args.receiver_model,
                     "misses": receiver.misses, "hits": receiver.hits},
        "total_logical": donor.misses + donor.hits + receiver.misses + receiver.hits,
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
        "survival": receipt.get("derivation_survival_check"),
        "donor_a": receipt.get("donor_a"), "b_self": receipt.get("b_self"),
        "arms": {k: v.get("fresh_accuracy") for k, v in receipt.get("arms", {}).items()},
        "discriminators": receipt.get("discriminators"),
        "kill": {k: v for k, v in receipt.get("kill_condition_observations", {}).items()
                 if k.startswith("f3")},
    }, indent=1, ensure_ascii=False))
    return 0 if aborted is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
