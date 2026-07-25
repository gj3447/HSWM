"""F3-r2 gate (Agent A -> frozen-B transfer) — harder-verdict redesign.

PREREG (locked, read-only input): prom_search_hswm/evidence/
PREREG_f3_agent_ab_transfer_20260725.json (in the SYMPOSIUM/HSWM checkout).

r2 rationale (parent decision 2026-07-25, option (a)): in r1
(f3_agent_ab_transfer_smoke_1784991668.json) both donors aced the 2-class
verdict (6/6 each), so A lessons were byte-identical to B-self lessons and
G == 0 structurally.  r2 makes the verdict genuinely hard: each train case
carries ONE trusted class plus THREE distractor classes
(p1v3_multi_environment.py, ADD-only module), so the donor must pick the
authoritative class from 4 candidates.  Donor = ollama qwen3:8b (weaker
than receiver qwen3.6-27b by design — the G discriminator needs a donor/
receiver quality gap; qwen3:14b was ceiling-perfect at 2-class, so the
smoke stresses the gap with a weaker donor; recorded in the receipt).
train_per_world raised to 3 for deltaW signal diversity (parent decision).

Everything else is the r1 design: donor verdict -> typed lesson (donor's
own choice, fallible), deltaW typed edit log (harmful lesson on the two
remaining train cases -> delete), sealed packets (sha256 + Merkle +
corpus manifest), arms B0/B1/B2/B3(token-capped)/B4a/B4b/B5, G = Acc(B1)
- Acc(B5), S = dist_cosine difference with paired bootstrap CI, kills
f3_k1..k4, scoring = gold exact-set-match.  Receipts are always
mode="development" measurements.

Usage:
  .venv/bin/python f3_agent_ab_transfer_r2.py --smoke
  .venv/bin/python f3_agent_ab_transfer_r2.py --universes-dir _research/f2_sealed_universes
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

from p1v3_multi_environment import build_policy_conflict_case_multi  # noqa: E402
from hswm_null_battery import headroom_band_ok  # noqa: E402

PREREG_PATH = NULL_BATTERY_DIR / "evidence" / "PREREG_f3_agent_ab_transfer_20260725.json"
RECEIPT_DIR = HERE / "receipts"
HEADROOM_BAND = (0.3, 0.7)
SATURATION_B0 = 5 / 6
SCOPE = {
    "all_terms": ["who is", "the person whose"],
    "any_terms": ["occupation", "hobby", "date of birth", "gender"],
    "excluded_terms": [],
}
GROUP_TRUSTED = ("RHO", "SIGMA", "GAMMA", "KAPPA", "OMEGA", "ALPHA")


class F3R2Error(RuntimeError):
    pass


def make_worlds(n_worlds: int, n_distractors: int = 3) -> list[dict]:
    return [{
        "world_idx": i,
        "trusted": GROUP_TRUSTED[i],
        "distractors": tuple(f"Q{i}{ch}" for ch in "ABCDEFGH"[:n_distractors]),
    } for i in range(n_worlds)]


def build_splits_r2(pool, article_cache, *, worlds, train_per_world: int,
                    n_fresh: int, max_answers: int, split_seed: int):
    order = list(pool)
    random.Random(f"f3r2-split-{split_seed}").shuffle(order)
    quotas = {"train": len(worlds) * train_per_world, "fresh": n_fresh}
    splits: dict[str, list] = {name: [] for name in quotas}
    skipped: dict[str, list] = {name: [] for name in quotas}
    cursor = 0
    for name, quota in quotas.items():
        while len(splits[name]) < quota and cursor < len(order):
            entry = order[cursor]
            cursor += 1
            idx = len(splits[name])
            world = worlds[(idx // train_per_world) % len(worlds)] \
                if name == "train" else worlds[idx % len(worlds)]
            question = entry["question"]
            try:
                case = build_policy_conflict_case_multi(
                    case_id=f"f3r2-{name}-{question['id'][:12]}",
                    question=question["question"],
                    articles=article_cache.articles(entry["universe"]),
                    trusted_class=world["trusted"],
                    distractor_classes=world["distractors"],
                    maximum_true_documents=max_answers,
                )
            except Exception as err:  # noqa: BLE001
                skipped[name].append({"question_id": question.get("id"),
                                      "error": type(err).__name__})
                continue
            if list(case.expected_answers) != sorted(question["answer"]):
                skipped[name].append({"question_id": question.get("id"),
                                      "error": "gold_mismatch"})
                continue
            splits[name].append((case, world["world_idx"], question, entry["universe"]))
        if len(splits[name]) < quota:
            raise F3R2Error(f"split '{name}' filled {len(splits[name])}/{quota}")
    return {"splits": splits, "skipped": skipped}


def donor_verdict_multi(chat, model: str, case, seed: int) -> dict:
    payload = {
        "question": case.question,
        "documents": [d.canonical() for d in case.documents],
        "verified_answers": list(case.expected_answers),
        "candidate_classes": list(case.candidate_classes),
        "instruction": (
            "Exactly one of the candidate_classes was authoritative for the "
            "verified answers. Return strict JSON "
            '{"authoritative": "<one of candidate_classes>"} with no other keys.'),
    }
    meta = chat.chat(model=model, system=f3r1.VERDICT_SYSTEM,
                     user=json.dumps(payload, ensure_ascii=False, sort_keys=True),
                     seed=seed, max_tokens=64)
    try:
        if meta["finish_reason"] != "stop":
            raise ValueError("finish")
        value = json.loads(meta["text"])["authoritative"]
    except Exception:  # noqa: BLE001
        return {"valid": False, "raw": meta["text"][:200]}
    if value not in case.candidate_classes:
        return {"valid": False, "raw": str(value)[:200]}
    return {"valid": True, "choice": value,
            "ground_truth": case.trusted_class,
            "orientation": "correct" if value == case.trusted_class else "inverted"}


def compile_multi_lesson(case, *, teach: str):
    others = [c for c in case.candidate_classes if c != teach]
    ignore_str = ", ".join(f"SOURCE_CLASS={c}" for c in others)
    episode_id = f"policy-training:{case.case_id}"
    evidence_id = "policy-training-evidence:" + case.derivation_sha256
    instruction = (
        "When supplied records contain conflicting answer candidates, treat "
        f"SOURCE_CLASS={teach} as authoritative, ignore {ignore_str} claims "
        f"for the final answer, and cite only {teach} records."
    )
    from p1v2_typed_lesson import LessonCompilePolicyV1, compile_typed_lesson
    recorded = {
        "schema_version": "hswm-p1v2-operational-verdict/v1",
        "source_episode_ids": [episode_id],
        "evidence_ids": [evidence_id],
        "verdict_type": "GENERALIZATION",
        "scope_predicate": SCOPE,
        "instruction": instruction,
        "polarity": "DO",
        "confidence": 1.0,
        "supersedes": [],
    }
    return compile_typed_lesson(recorded, LessonCompilePolicyV1(
        allowed_episode_ids=(episode_id,),
        allowed_evidence_ids=(evidence_id,),
    ))


def donor_pipeline_r2(chat, model: str, worlds, train_cases, parallel: int,
                      seed: int):
    per_world: dict[int, list] = {}
    for item in train_cases:
        per_world.setdefault(item[1], []).append(item)
    lessons: dict[int, object] = {}
    verdicts: dict[int, dict] = {}
    for world in worlds:
        w = world["world_idx"]
        case1 = per_world[w][0][0]
        verdict = donor_verdict_multi(chat, model, case1, seed)
        verdicts[w] = verdict
        if verdict["valid"]:
            lessons[w] = compile_multi_lesson(case1, teach=verdict["choice"])
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
    return lessons, verdicts, edits


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-fresh", type=int, default=100)
    ap.add_argument("--train-per-world", type=int, default=3)
    ap.add_argument("--split-seed", type=int, default=20260728)
    ap.add_argument("--seed", type=int, default=20260725)
    ap.add_argument("--max-answers", type=int, default=1)
    ap.add_argument("--max-calls", type=int, default=1500)
    ap.add_argument("--parallel-b", type=int, default=16)
    ap.add_argument("--parallel-a", type=int, default=4)
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--universes-dir", type=Path,
                    default=HERE / "_research" / "f2_sealed_universes")
    ap.add_argument("--donor-url", default="http://127.0.0.1:11434")
    ap.add_argument("--donor-model", default="qwen3:8b")
    ap.add_argument("--receiver-url", default="http://127.0.0.1:18000/v1")
    ap.add_argument("--receiver-model", default="qwen3.6-27b")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    if args.smoke:
        args.n_fresh = 6
        args.max_calls = 150
    worlds = make_worlds(len(GROUP_TRUSTED))
    t0 = time.time()
    ts = int(t0)
    out_path = Path(args.out) if args.out else (
        RECEIPT_DIR / f"f3r2_agent_ab_transfer_{'smoke' if args.smoke else 'sealed'}_{ts}.json")
    packet_path = RECEIPT_DIR / f"f3r2_transfer_packet_{ts}.json"
    packet_b_path = RECEIPT_DIR / f"f3r2_transfer_packet_bself_{ts}.json"

    receipt = {
        "schema_version": "hswm-f3-agent-ab-transfer-r2-receipt/v1",
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
            "p1v3_multi_environment.py": hashlib.sha256(
                (HERE / "p1v3_multi_environment.py").read_bytes()).hexdigest(),
        },
        "prereg_reading_deviation": (
            "r2 (parent decision 2026-07-25, option (a)): verdict task is "
            "4-class (1 trusted + 3 distractors, p1v3_multi_environment "
            "ADD-only module) because 2-class was ceiling-easy for both "
            "models in r1 (G==0 structurally).  Donor weakened to "
            "qwen3:8b so the donor/receiver quality gap can exist "
            "(qwen3:14b aced 2-class; if 8b still aces 4-class the next "
            "step is a weaker donor).  train_per_world=3 for deltaW "
            "diversity.  Arms/metrics/kills unchanged from the prereg."),
        "config": vars(args) | {"out": str(out_path),
                                "universes_dir": str(args.universes_dir)},
        "donor_freeze": {
            "backend": "ollama", "url": args.donor_url, "model": args.donor_model,
            "rationale": "donor must be weaker than receiver for G to be "
                         "measurable; qwen3:14b was ceiling-perfect at 2-class "
                         "in r1, so r2 uses qwen3:8b.",
        },
        "receiver_freeze": {
            "backend": "vllm", "url": args.receiver_url, "model": args.receiver_model,
            "system_prompt_sha256": hashlib.sha256(
                f2.P1V2_SYSTEM_PROMPT.encode()).hexdigest(),
            "seed": args.seed, "temperature": 0, "max_tokens": 256,
            "note": "B frozen; only memory_context varies across arms.",
        },
        "honesty": "grounded measurement only; no scientific claim; judgment is the gate's",
    }
    budget = f2.Budget(args.max_calls)
    donor = f2.CachedChat(args.donor_url, budget)
    receiver = f2.CachedOpenAIChat(args.receiver_url, budget)
    aborted = None
    try:
        pool, pool_stats = f2.load_question_pool(args.universes_dir, args.max_answers)
        receipt["question_pool"] = pool_stats
        article_cache = f2._ArticleCache(args.universes_dir)
        built = build_splits_r2(pool, article_cache, worlds=worlds,
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

        lessons_a, verdicts_a, edits_a = donor_pipeline_r2(
            donor, args.donor_model, worlds, train_cases,
            args.parallel_a, args.seed)
        lessons_b, verdicts_b, edits_b = donor_pipeline_r2(
            receiver, args.receiver_model, worlds, train_cases,
            args.parallel_b, args.seed)
        receipt["donor_a"] = {
            "model": args.donor_model,
            "n_lessons": len(lessons_a),
            "orientations": {str(w): verdicts_a[w].get("orientation")
                             for w in sorted(verdicts_a) if verdicts_a[w]["valid"]},
            "n_invalid_verdicts": sum(1 for v in verdicts_a.values()
                                      if not v["valid"]),
        }
        receipt["b_self"] = {
            "model": args.receiver_model,
            "n_lessons": len(lessons_b),
            "orientations": {str(w): verdicts_b[w].get("orientation")
                             for w in sorted(verdicts_b) if verdicts_b[w]["valid"]},
            "n_invalid_verdicts": sum(1 for v in verdicts_b.values()
                                      if not v["valid"]),
        }
        # r2 survival evidence: where donor and b-self verdicts diverge
        divergent = []
        for w in sorted(verdicts_a):
            va, vb = verdicts_a[w], verdicts_b[w]
            ca = va.get("choice") if va["valid"] else None
            cb = vb.get("choice") if vb["valid"] else None
            if ca != cb:
                divergent.append({"world": w, "donor_choice": ca,
                                  "bself_choice": cb,
                                  "ground_truth": worlds[w]["trusted"]})
        receipt["verdict_divergence"] = {
            "n_divergent_worlds": len(divergent), "cases": divergent,
            "note": "r2 survival check: G is measurable only if donor and "
                    "b-self verdicts diverge on at least one world.",
        }

        by_id_a = {l.lesson_id: l for l in lessons_a.values()}
        by_id_b = {l.lesson_id: l for l in lessons_b.values()}
        placebo_lessons, _placebo_map = f2.build_placebo_lessons(
            by_id_a, f"f3r2-placebo-{args.seed}")
        by_id_p = placebo_lessons

        packet = f3r1.seal_packet(
            donor={"backend": "ollama", "url": args.donor_url,
                   "model": args.donor_model},
            train_cases=train_cases, lessons=lessons_a, edits=edits_a,
            out_path=packet_path)
        packet_b = f3r1.seal_packet(
            donor={"backend": "vllm", "url": args.receiver_url,
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
        raw_log_full = "\n".join(f3r1.render_policy_training_transcript(item[0])
                                 for item in train_cases) \
            if hasattr(f3r1, "render_policy_training_transcript") else ""
        if not raw_log_full:
            from p1v3_policy_environment import render_policy_training_transcript
            raw_log_full = "\n".join(render_policy_training_transcript(item[0])
                                     for item in train_cases)
        from p1v2_typed_lesson import render_lesson_context, retrieve_lessons
        if kept_a:
            ref_q = fresh_cases[0][0].question
            ref_lessons = [by_id_a[i] for i in kept_a]
            b1_ref_ctx = render_lesson_context(
                retrieve_lessons(ref_q, ref_lessons, top_k=len(ref_lessons)),
                ref_lessons)
        else:
            b1_ref_ctx = ""
        raw_cap = max(len(b1_ref_ctx), 200)
        raw_log = raw_log_full[:raw_cap]
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
    except (F3R2Error, f2.BudgetExceeded) as err:
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
        "verdict_divergence": receipt.get("verdict_divergence"),
        "donor_a": receipt.get("donor_a"), "b_self": receipt.get("b_self"),
        "packets": {k: v.get("packet_sha256", "")[:16]
                    for k, v in receipt.get("packets", {}).items()},
        "arms": {k: v.get("fresh_accuracy") for k, v in receipt.get("arms", {}).items()},
        "discriminators": receipt.get("discriminators"),
        "kill": {k: v for k, v in receipt.get("kill_condition_observations", {}).items()
                 if k.startswith("f3")},
    }, indent=1, ensure_ascii=False))
    return 0 if aborted is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
