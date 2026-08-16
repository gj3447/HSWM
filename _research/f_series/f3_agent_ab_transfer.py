"""F3 gate (Agent A -> frozen-B knowledge transfer) development/sealed harness.

PREREG (locked, read-only input): prom_search_hswm/evidence/
PREREG_f3_agent_ab_transfer_20260725.json (in the SYMPOSIUM/HSWM checkout).

Receipts from this script are always mode="development" measurements; the
scientific judgment belongs to the HSWM_LOCAL_RECORD gate, never to this file.

Design (parent-ratified 2026-07-25):
  donor A     ollama qwen3:14b (native /api/chat, think=false).  Per train
              world A gets the verified outcome and states which SOURCE_CLASS
              was authoritative (strict JSON verdict); the lesson is compiled
              from A's OWN choice — including A's mistakes (an inverted
              donor lesson is genuine fallible knowledge, kept; an invalid
              verdict yields no lesson for that world, recorded).
  deltaW      typed edit log over A's lesson store: per world, second train
              case answered with vs without the lesson; harmful lesson
              (with < without) -> {"op": "delete"}, else {"op": "keep"}.
              B-self (vLLM qwen3.6-27b) runs the identical pipeline; B5 is
              its mirrored product, so B1 vs B5 differs ONLY in who authored.
  packet      receipts/f3_transfer_packet_<ts>.json (+ bself variant):
              canonical lessons + edit log + Merkle provenance root over
              lesson ids + donor corpus manifest hash (train case
              derivation shas) + packet sha256.
  arms        B0 none / B1 A lessons+deletes / B2 placebo lessons (schema-
              and token-comparable, unrelated domain, no deletes) / B3 A raw
              training transcripts / B4a A lessons no deletes / B4b placebo
              with A's delete pattern (deltaW-only) / B5 B-self lessons+deletes.
  G           Acc(B1) - Acc(B5), paired bootstrap CI.
  S           dist_cosine(B1 answers, A answers) - dist_cosine(B5 answers,
              A answers) over fresh cases, answers normalized (casefold,
              whitespace), "<EMPTY>" marker for empty answer sets; paired
              bootstrap CI.  Secondary: mean per-case answer-set Jaccard
              difference.  Method recorded in every receipt (prereg says
              "corr"; the implemented reading is aggregate distribution
              cosine + per-case Jaccard, no embeddings — deterministic).
  kills       f3_k1 G<=0 / f3_k2 S<=0 / f3_k3 B1<=max(B0,B2,B3)
              (+b1<=b3 sub-flag) / f3_k4 B0>=5/6.

Scoring is gold exact-set-match (no LLM judge).  Plumbing (chat backends,
disk cache, pool, leakage audit, placebo lessons) is reused from
f2_delta_w_credit.py / f4_topology_learning.py, unmodified.

Usage:
  .venv/bin/python -m _research.f_series.f3_agent_ab_transfer --smoke
  .venv/bin/python -m _research.f_series.f3_agent_ab_transfer --universes-dir _research/f2_sealed_universes
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
from pathlib import Path
import random
import time

from . import REPO_ROOT, source_path
from . import f2_delta_w_credit as f2

NULL_BATTERY_DIR = REPO_ROOT / "prom_search_hswm"

from p1v2_typed_lesson import (  # noqa: E402
    LessonCompilePolicyV1,
    compile_typed_lesson,
    render_lesson_context,
    retrieve_lessons,
)
from p1v3_policy_environment import (  # noqa: E402
    build_policy_conflict_case,
    render_policy_training_transcript,
)
from prom_search_hswm.hswm_null_battery import headroom_band_ok  # noqa: E402

PREREG_PATH = NULL_BATTERY_DIR / "evidence" / "PREREG_f3_agent_ab_transfer_20260725.json"
RECEIPT_DIR = REPO_ROOT / "receipts"
HEADROOM_BAND = (0.3, 0.7)
SATURATION_B0 = 5 / 6
SCOPE = {
    "all_terms": ["who is", "the person whose"],
    "any_terms": ["occupation", "hobby", "date of birth", "gender"],
    "excluded_terms": [],
}
WORLDS = (
    ("RHO", "TAU"), ("SIGMA", "BETA"), ("GAMMA", "DELTA"),
    ("KAPPA", "ZETA"), ("OMEGA", "PSI"), ("ALPHA", "NU"),
)


class F3Error(RuntimeError):
    pass


# ---------------------------------------------------------------- helpers
def merkle_root(hexes: list[str]) -> str:
    layer = sorted(hexes)
    if not layer:
        return hashlib.sha256(b"").hexdigest()
    while len(layer) > 1:
        layer = [
            hashlib.sha256("|".join(layer[i:i + 2]).encode()).hexdigest()
            for i in range(0, len(layer), 2)
        ]
    return layer[0]


def build_splits_f3(pool, article_cache, *, n_worlds: int, train_per_world: int,
                    n_fresh: int, max_answers: int, split_seed: int):
    order = list(pool)
    random.Random(f"f3-split-{split_seed}").shuffle(order)
    need = n_worlds * train_per_world + n_fresh
    if len(order) < need:
        raise F3Error(f"pool {len(order)} < needed {need}")
    splits = {"train": [], "fresh": []}
    skipped = {"train": [], "fresh": []}
    cursor = 0
    quotas = {"train": n_worlds * train_per_world, "fresh": n_fresh}
    for name, quota in quotas.items():
        while len(splits[name]) < quota and cursor < len(order):
            entry = order[cursor]
            cursor += 1
            world_idx = (len(splits[name]) // train_per_world) % n_worlds \
                if name == "train" else len(splits[name]) % n_worlds
            trusted, distractor = WORLDS[world_idx]
            question = entry["question"]
            try:
                case = build_policy_conflict_case(
                    case_id=f"f3-{name}-{question['id'][:12]}",
                    question=question["question"],
                    articles=article_cache.articles(entry["universe"]),
                    trusted_class=trusted, distractor_class=distractor,
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
            splits[name].append((case, world_idx, question, entry["universe"]))
        if len(splits[name]) < quota:
            raise F3Error(f"split '{name}' filled {len(splits[name])}/{quota}")
    return {"splits": splits, "skipped": skipped}


def compile_donor_lesson(case, *, teach: str, ignore: str):
    episode_id = f"policy-training:{case.case_id}"
    evidence_id = "policy-training-evidence:" + case.derivation_sha256
    instruction = (
        "When supplied records contain conflicting answer candidates, treat "
        f"SOURCE_CLASS={teach} as authoritative, ignore SOURCE_CLASS={ignore} "
        f"claims for the final answer, and cite only {teach} records."
    )
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
    lesson = compile_typed_lesson(recorded, LessonCompilePolicyV1(
        allowed_episode_ids=(episode_id,),
        allowed_evidence_ids=(evidence_id,),
    ))
    return lesson


VERDICT_SYSTEM = (
    "You identify which record class was authoritative in a verified training "
    "episode. Output only strict JSON.")


def donor_verdict(chat, model: str, case, seed: int) -> dict:
    payload = {
        "question": case.question,
        "documents": [d.canonical() for d in case.documents],
        "verified_answers": list(case.expected_answers),
        "instruction": (
            "Exactly one of the SOURCE_CLASS values shown in the documents was "
            "authoritative for the verified answers. Return strict JSON "
            '{"authoritative": "<SOURCE_CLASS value>"} with no other keys.'),
    }
    meta = chat.chat(model=model, system=VERDICT_SYSTEM,
                     user=json.dumps(payload, ensure_ascii=False, sort_keys=True),
                     seed=seed, max_tokens=64)
    try:
        if meta["finish_reason"] != "stop":
            raise ValueError("finish")
        value = json.loads(meta["text"])["authoritative"]
    except Exception:  # noqa: BLE001
        return {"valid": False, "raw": meta["text"][:200]}
    if value not in (case.trusted_class, case.distractor_class):
        return {"valid": False, "raw": str(value)[:200]}
    return {"valid": True, "choice": value,
            "ground_truth": case.trusted_class,
            "orientation": "correct" if value == case.trusted_class else "inverted"}


def eval_ctx(chat, model: str, ctx, cases, by_id: dict, parallel: int, seed: int,
             keep_answers: bool = False):
    """ctx: ('lessons', ids) | ('raw', text) | ('none',) — shared by all cases."""

    def work(item):
        case, _w, _q, _u = item
        kind = ctx[0]
        if kind == "lessons":
            ids = tuple(sorted(ctx[1]))
            memory = "" if not ids else render_lesson_context(
                retrieve_lessons(case.question, [by_id[i] for i in ids],
                                 top_k=len(ids)),
                [by_id[i] for i in ids])
        elif kind == "raw":
            memory = ctx[1]
        else:
            memory = ""
        user = f2.render_answer_prompt(case.question, case.documents, memory)
        meta = chat.chat(model=model, system=f2.P1V2_SYSTEM_PROMPT, user=user,
                         seed=seed, max_tokens=256)
        correct, parse_ok, answers = 0, True, []
        try:
            if meta["finish_reason"] != "stop":
                raise ValueError("finish_reason")
            payload = json.loads(meta["text"])
            answers = payload["answers"]
            if not isinstance(answers, list):
                raise ValueError("answers")
            correct = int(f2.normalized_set(answers)
                          == f2.normalized_set(case.expected_answers))
        except Exception:  # noqa: BLE001
            parse_ok = False
            answers = []
        row = {"case_id": case.case_id, "correct": correct, "parse_ok": parse_ok,
               "cached": meta["cached"]}
        if keep_answers:
            row["answers"] = [str(a) for a in answers]
        return row

    with ThreadPoolExecutor(max_workers=parallel) as pool:
        rows = list(pool.map(work, cases))
    n = len(rows)
    out = {
        "accuracy": sum(r["correct"] for r in rows) / n,
        "parse_failures": sum(1 for r in rows if not r["parse_ok"]),
        "correct_vector": [r["correct"] for r in rows],
    }
    if keep_answers:
        out["rows"] = rows
    return out


def donor_pipeline(chat, model: str, n_worlds: int, train_cases,
                   parallel: int, seed: int):
    """Verdict -> lessons -> deltaW edit log, for one donor model."""
    per_world: dict[int, list] = {}
    for item in train_cases:
        per_world.setdefault(item[1], []).append(item)
    lessons: dict[int, object] = {}
    verdicts: dict[int, dict] = {}
    for w in range(n_worlds):
        case1 = per_world[w][0][0]
        verdict = donor_verdict(chat, model, case1, seed)
        verdicts[w] = verdict
        if verdict["valid"]:
            other = (case1.distractor_class if verdict["choice"] == case1.trusted_class
                     else case1.trusted_class)
            lessons[w] = compile_donor_lesson(
                case1, teach=verdict["choice"], ignore=other)
    by_id = {l.lesson_id: l for l in lessons.values()}
    edits = []
    for w in sorted(lessons):
        case2 = per_world[w][1][0]
        lid = lessons[w].lesson_id
        res_with = eval_ctx(chat, model, ("lessons", (lid,)), [per_world[w][1]],
                            by_id, parallel, seed)
        res_without = eval_ctx(chat, model, ("none",), [per_world[w][1]],
                               by_id, parallel, seed)
        acc_with = res_with["correct_vector"][0]
        acc_without = res_without["correct_vector"][0]
        op = "delete" if acc_with < acc_without else "keep"
        edits.append({
            "op": op, "target": lid,
            "evidence": {"case_id": case2.case_id, "acc_with_lesson": acc_with,
                         "acc_without_lesson": acc_without},
        })
    return lessons, verdicts, edits


def seal_packet(*, donor: dict, train_cases, lessons: dict, edits: list,
                out_path: Path) -> dict:
    corpus_manifest = merkle_root([item[0].derivation_sha256 for item in train_cases])
    packet = {
        "schema_version": "hswm-f3-transfer-packet/v1",
        "donor": donor,
        "experience": {
            "train_case_ids": [item[0].case_id for item in train_cases],
            "corpus_manifest_sha256": corpus_manifest,
        },
        "lessons": [lessons[w].canonical() for w in sorted(lessons)],
        "lesson_merkle_root": merkle_root(
            [lessons[w].lesson_id for w in sorted(lessons)]),
        "delta_w": {
            "schema_version": "hswm-f3-delta-w-edit-log/v1",
            "store_manifest_sha256": merkle_root(
                [lessons[w].lesson_id for w in sorted(lessons)]),
            "edits": edits,
        },
    }
    unsigned = dict(packet)
    packet["packet_sha256"] = hashlib.sha256(json.dumps(
        unsigned, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False).encode()).hexdigest()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(packet, indent=1, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    return packet


def norm_answers(answers: list[str]) -> list[str]:
    vals = sorted({" ".join(str(a).casefold().split()) for a in answers if str(a).strip()})
    return vals if vals else ["<EMPTY>"]


def dist_cosine(rows_x, rows_a) -> float:
    cx: Counter = Counter()
    ca: Counter = Counter()
    for rx, ra in zip(rows_x, rows_a):
        for v in norm_answers(rx.get("answers", [])):
            cx[v] += 1
        for v in norm_answers(ra.get("answers", [])):
            ca[v] += 1
    keys = set(cx) | set(ca)
    num = sum(cx[k] * ca[k] for k in keys)
    den = math.sqrt(sum(v * v for v in cx.values())) \
        * math.sqrt(sum(v * v for v in ca.values()))
    return num / den if den else 0.0


def case_jaccard(rx, ra) -> float:
    sx = set(norm_answers(rx.get("answers", [])))
    sa = set(norm_answers(ra.get("answers", [])))
    return len(sx & sa) / len(sx | sa) if (sx | sa) else 1.0


def bootstrap_gap(vals_a, vals_b, *, n_boot: int, seed: int):
    """CI of mean(a - b) over paired per-case vectors (single resample index)."""
    rng = random.Random(seed)
    n = len(vals_a)
    diffs = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        diffs.append(sum(vals_a[i] for i in idx) / n
                     - sum(vals_b[i] for i in idx) / n)
    diffs.sort()
    return {"mean": sum(diffs) / n_boot,
            "ci95": [diffs[int(0.025 * n_boot)], diffs[int(0.975 * n_boot)]]}


def bootstrap_s_gap(rows_b1, rows_b5, rows_a, *, n_boot: int, seed: int):
    rng = random.Random(seed)
    n = len(rows_a)
    diffs = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        b1 = [rows_b1[i] for i in idx]
        b5 = [rows_b5[i] for i in idx]
        a = [rows_a[i] for i in idx]
        diffs.append(dist_cosine(b1, a) - dist_cosine(b5, a))
    diffs.sort()
    return {"mean": sum(diffs) / n_boot,
            "ci95": [diffs[int(0.025 * n_boot)], diffs[int(0.975 * n_boot)]]}


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-fresh", type=int, default=100)
    ap.add_argument("--train-per-world", type=int, default=2)
    ap.add_argument("--split-seed", type=int, default=20260727)
    ap.add_argument("--seed", type=int, default=20260725)
    ap.add_argument("--max-answers", type=int, default=1)
    ap.add_argument("--max-calls", type=int, default=1200)
    ap.add_argument("--parallel-b", type=int, default=16)
    ap.add_argument("--parallel-a", type=int, default=4)
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--universes-dir", type=Path,
                    default=REPO_ROOT / "_research" / "f2_sealed_universes")
    ap.add_argument("--donor-backend", choices=("ollama", "vllm"), default="ollama")
    ap.add_argument("--donor-url", default="http://127.0.0.1:11434")
    ap.add_argument("--donor-model", default="qwen3:14b")
    ap.add_argument("--receiver-url", default="http://127.0.0.1:18000/v1")
    ap.add_argument("--receiver-model", default="qwen3.6-27b")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    if args.smoke:
        args.n_fresh = 6
        args.max_calls = 120
    n_worlds = len(WORLDS)
    t0 = time.time()
    ts = int(t0)
    out_path = Path(args.out) if args.out else (
        RECEIPT_DIR / f"f3_agent_ab_transfer_{'smoke' if args.smoke else 'sealed'}_{ts}.json")
    packet_path = RECEIPT_DIR / f"f3_transfer_packet_{ts}.json"
    packet_b_path = RECEIPT_DIR / f"f3_transfer_packet_bself_{ts}.json"

    receipt = {
        "schema_version": "hswm-f3-agent-ab-transfer-receipt/v1",
        "mode": "development",
        "branch": "F3-agent-ab-transfer",
        "smoke": bool(args.smoke),
        "preregistration_file": str(PREREG_PATH),
        "preregistration_file_sha256": hashlib.sha256(
            PREREG_PATH.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "harness_module_sha256": hashlib.sha256(
            source_path("f2_delta_w_credit.py").read_bytes()).hexdigest(),
        "config": vars(args) | {"out": str(out_path),
                                "universes_dir": str(args.universes_dir)},
        "receiver_freeze": {
            "backend": "vllm", "url": args.receiver_url,
            "model": args.receiver_model,
            "system_prompt_sha256": hashlib.sha256(
                f2.P1V2_SYSTEM_PROMPT.encode()).hexdigest(),
            "prompt_shape": "hswm-p1v2-answer-input/v1 (render_answer_prompt)",
            "seed": args.seed, "temperature": 0, "max_tokens": 256,
            "note": "B is frozen: deployment/prompt/tools/readout/budget fixed "
                    "for all arms; only the memory_context varies.",
        },
        "donor_freeze": {
            "backend": args.donor_backend, "url": args.donor_url,
            "model": args.donor_model,
            "note": "donor A != receiver B (true cross-agent). B-self uses the "
                    "receiver model, so B1 vs B5 differs only in authorship.",
        },
        "honesty": "grounded measurement only; no scientific claim; judgment is the gate's",
    }
    budget = f2.Budget(args.max_calls)
    donor = f2.CachedChat(args.donor_url, budget) \
        if args.donor_backend == "ollama" \
        else f2.CachedOpenAIChat(args.donor_url, budget)
    receiver = f2.CachedOpenAIChat(args.receiver_url, budget)
    aborted = None
    try:
        pool, pool_stats = f2.load_question_pool(args.universes_dir, args.max_answers)
        receipt["question_pool"] = pool_stats
        article_cache = f2._ArticleCache(args.universes_dir)
        built = build_splits_f3(pool, article_cache, n_worlds=n_worlds,
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

        # ---- donor A + B-self pipelines ----
        lessons_a, verdicts_a, edits_a = donor_pipeline(
            donor, args.donor_model, n_worlds, train_cases,
            args.parallel_a, args.seed)
        lessons_b, verdicts_b, edits_b = donor_pipeline(
            receiver, args.receiver_model, n_worlds, train_cases,
            args.parallel_b, args.seed)
        receipt["donor_a"] = {
            "model": args.donor_model,
            "verdicts": {str(w): v for w, v in sorted(verdicts_a.items())},
            "n_lessons": len(lessons_a),
            "orientations": {str(w): verdicts_a[w].get("orientation")
                             for w in sorted(verdicts_a) if verdicts_a[w]["valid"]},
        }
        receipt["b_self"] = {
            "model": args.receiver_model,
            "n_lessons": len(lessons_b),
            "orientations": {str(w): verdicts_b[w].get("orientation")
                             for w in sorted(verdicts_b) if verdicts_b[w]["valid"]},
        }

        by_id_a = {l.lesson_id: l for l in lessons_a.values()}
        by_id_b = {l.lesson_id: l for l in lessons_b.values()}
        placebo_lessons, _placebo_map = f2.build_placebo_lessons(by_id_a, f"f3-placebo-{args.seed}")
        by_id_p = placebo_lessons

        packet = seal_packet(
            donor={"backend": args.donor_backend, "url": args.donor_url,
                   "model": args.donor_model},
            train_cases=train_cases, lessons=lessons_a, edits=edits_a,
            out_path=packet_path)
        packet_b = seal_packet(
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
        raw_log_full = "\n".join(render_policy_training_transcript(item[0])
                                 for item in train_cases)
        # token-envelope parity (prereg): B3 raw log is capped to the B1
        # lesson-context size so the typed-vs-raw contrast is not confounded
        # by a ~12x token advantage (measured 7.5k vs 0.6k tokens in smoke 1).
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
            "cap_note": "B3 raw log deterministically prefix-capped to the B1 "
                        "context size (prereg token_envelope: equal across arms).",
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
            res = eval_ctx(receiver, args.receiver_model, ctx, fresh_cases,
                           by_id, args.parallel_b, args.seed,
                           keep_answers=keep_ans)
            arms[arm_id] = res
        receipt["arms"] = {
            k: {"context_kind": arm_ctxs[k][0],
                "n_context_lessons": (len(arm_ctxs[k][1]) if arm_ctxs[k][0] == "lessons" else 0),
                "fresh_accuracy": v["accuracy"],
                "fresh_parse_failures": v["parse_failures"],
                "approx_context_tokens": (len(raw_log) // 4 if k == "B3_raw_log_only" else None)}
            for k, v in arms.items()}

        # ---- A's own response distribution on fresh (for S) ----
        a_fresh = eval_ctx(donor, args.donor_model, ("lessons", kept_a),
                           fresh_cases, by_id_a, args.parallel_a, args.seed,
                           keep_answers=True)

        # ---- G and S ----
        acc = {k: v["accuracy"] for k, v in arms.items()}
        G = acc["B1_full_packet"] - acc["B5_b_self_lessons"]
        g_ci = bootstrap_gap(arms["B1_full_packet"]["correct_vector"],
                             arms["B5_b_self_lessons"]["correct_vector"],
                             n_boot=args.n_boot, seed=args.seed)
        rows_b1 = arms["B1_full_packet"]["rows"]
        rows_b5 = arms["B5_b_self_lessons"]["rows"]
        rows_a = a_fresh["rows"]
        s_cos_b1 = dist_cosine(rows_b1, rows_a)
        s_cos_b5 = dist_cosine(rows_b5, rows_a)
        S = s_cos_b1 - s_cos_b5
        s_ci = bootstrap_s_gap(rows_b1, rows_b5, rows_a,
                               n_boot=args.n_boot, seed=args.seed)
        jac_b1 = sum(case_jaccard(rx, ra) for rx, ra in zip(rows_b1, rows_a)) / len(rows_a)
        jac_b5 = sum(case_jaccard(rx, ra) for rx, ra in zip(rows_b5, rows_a)) / len(rows_a)
        receipt["discriminators"] = {
            "G": round(G, 4), "G_ci95": [round(x, 4) for x in g_ci["ci95"]],
            "S": round(S, 4), "S_ci95": [round(x, 4) for x in s_ci["ci95"]],
            "S_components": {"dist_cosine_B1_A": round(s_cos_b1, 4),
                             "dist_cosine_B5_A": round(s_cos_b5, 4)},
            "S_secondary_jaccard": {"mean_B1_A": round(jac_b1, 4),
                                    "mean_B5_A": round(jac_b5, 4)},
            "S_method": (
                "per-case answers normalized (casefold+whitespace), empty set "
                "-> '<EMPTY>'; aggregate count-vector cosine between arm and "
                "donor answer distributions, difference with paired bootstrap "
                "CI (prereg 'corr' reading = distribution cosine; secondary "
                "metric = mean per-case answer-set Jaccard difference). "
                "Deterministic, no embeddings."),
        }

        # ---- kills ----
        receipt["headroom_band"] = list(HEADROOM_BAND)
        receipt["headroom_band_ok"] = headroom_band_ok(acc["B0_no_experience"], *HEADROOM_BAND)
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
    except (F3Error, f2.BudgetExceeded) as err:
        aborted = str(err)
    except Exception as err:  # noqa: BLE001
        aborted = f"{type(err).__name__}: {err}"

    receipt["llm_budget"] = {
        "max_calls": args.max_calls, "used": budget.used,
        "donor": {"backend": args.donor_backend, "model": args.donor_model,
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
