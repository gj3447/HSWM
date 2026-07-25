"""F5 gate (long-term consolidation) development/sealed harness.

PREREG (locked, read-only input): prom_search_hswm/evidence/
PREREG_f5_consolidation_20260725.json (in the SYMPOSIUM/HSWM checkout).

Receipts from this script are always mode="development" measurements; the
scientific judgment belongs to the LakatosTree gate, never to this file.

Design (parent-ratified 2026-07-26):
  episodes    E PhantomWiki source-class worlds, experienced in sequence
              (E1..E8 sealed / E1..E4 smoke).  Simulated lag: retention of
              episode i is probed at the final state, so lag(i) = (E-1)-i
              episodes of interference (prereg reading deviation, recorded:
              wall-clock weeks -> simulated episode-interference lag).
  wake        per episode: typed actuation lesson derived from the training
              case (correct policy lesson), initial confidence = Hebbian
              contribution c0 = 0.5 + 0.5*(acc_with - acc_without) measured
              on the episode's training case (2 calls, shared by arms A/C).
  sleep       consolidation operator (DETERMINISTIC, definition recorded in
              the receipt per foundation semantic-weight-metric-contract):
              after episode k<E-1, every lesson with origin<k has its
              confidence downscaled by alpha; a full-form lesson whose
              confidence falls below theta is COMPRESSED to a short gist
              instruction (supersedes chain) pinned at gist_floor and never
              evicted.  Edge-weight meaning = Hebbian delta-s (c0) plus
              downscale alpha per sleep.
  arms        A full HSWM (wake+sleep) / B raw-log append-only (episode
              transcripts preserved, same char budget retrieval) / C
              consolidation-off (same lessons, sleep no-op).
  probes      detail (standard exact-set-match per episode) and gist
              ("which SOURCE_CLASS is authoritative?" meta-question, answer
              set must equal {trusted_class}); immediate A-probe after each
              wake for GEM-format BWT/FWT; conflict-density injection;
              token cost per correct answer.
  retention   R_detail(t), R_gist(t) per arm; least-squares decay slope
              with paired bootstrap CIs (prereg's hierarchical model read
              as bootstrap slope CI, method recorded).  Judgment:
              (1) A dominates B and C by >= delta at every lag >= 4
              (2) LCB of (slope_A - slope_C) and (slope_A - slope_B) > 0.
  kills       f5_k1 B within delta of A at all lags / f5_k2 A-C <= delta at
              all lags / f5_k3 A>C only at lag 0.

Plumbing (chat backends, disk cache, pool, leakage audit, typed lesson
compiler) is reused from f2_delta_w_credit.py / f3_agent_ab_transfer.py,
unmodified.  Answerer: vLLM qwen3.6-27b (ollama qwen3:8b is actuation-
incapable per F3-r3 smoke and is not used).

Usage:
  .venv/bin/python f5_consolidation.py --smoke
  .venv/bin/python f5_consolidation.py --universes-dir _research/f2_sealed_universes
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
from hswm_null_battery import headroom_band_ok  # noqa: E402

PREREG_PATH = NULL_BATTERY_DIR / "evidence" / "PREREG_f5_consolidation_20260725.json"
RECEIPT_DIR = HERE / "receipts"
HEADROOM_BAND = (0.3, 0.7)
DELTA = 0.10
SCOPE = {
    "all_terms": ["who is", "the person whose"],
    "any_terms": ["occupation", "hobby", "date of birth", "gender"],
    "excluded_terms": [],
}
WORLDS = (
    ("RHO", "TAU"), ("SIGMA", "BETA"), ("GAMMA", "DELTA"), ("KAPPA", "ZETA"),
    ("OMEGA", "PSI"), ("ALPHA", "NU"), ("ETA", "THETA"), ("IOTA", "LAMBDA"),
)
# consolidation operator constants (definition pinned for the receipt)
ALPHA = 0.8          # confidence downscale per sleep
THETA = 0.5          # below this, a full-form lesson is compressed
GIST_FLOOR = 0.5     # gist lessons are pinned here (typed-lesson admission floor) and never evicted
GIST_TEMPLATE = "Treat SOURCE_CLASS={klass} as authoritative when records conflict."


class F5Error(RuntimeError):
    pass


class StoreRec:
    def __init__(self, lesson, origin: int, form: str, confidence: float):
        self.lesson = lesson
        self.origin = origin
        self.form = form
        self.confidence = confidence

    def snapshot(self) -> dict:
        return {"lesson_id": self.lesson.lesson_id[:16], "origin": self.origin,
                "form": self.form, "confidence": round(self.confidence, 4)}


# ---------------------------------------------------------------- lessons
def compile_lesson(case, *, teach: str, ignore: str, confidence: float,
                   supersedes: tuple[str, ...] = (), gist: bool = False,
                   known_ids: tuple[str, ...] = ()):
    episode_id = f"policy-training:{case.case_id}"
    evidence_id = "policy-training-evidence:" + case.derivation_sha256
    instruction = (GIST_TEMPLATE.format(klass=teach) if gist else (
        "When supplied records contain conflicting answer candidates, treat "
        f"SOURCE_CLASS={teach} as authoritative, ignore SOURCE_CLASS={ignore} "
        f"claims for the final answer, and cite only {teach} records."))
    recorded = {
        "schema_version": "hswm-p1v2-operational-verdict/v1",
        "source_episode_ids": [episode_id],
        "evidence_ids": [evidence_id],
        "verdict_type": "GENERALIZATION",
        "scope_predicate": SCOPE,
        "instruction": instruction,
        "polarity": "DO",
        "confidence": confidence,
        "supersedes": list(supersedes),
    }
    return compile_typed_lesson(recorded, LessonCompilePolicyV1(
        allowed_episode_ids=(episode_id,),
        allowed_evidence_ids=(evidence_id,),
        known_lesson_ids=known_ids,
    ))


# ---------------------------------------------------------------- eval
def f5_eval(chat, model: str, items, ctx_fn, score_fn, parallel: int, seed: int):
    """items: (case, world_idx, question, universe); ctx_fn(item)->(memory, question);
    score_fn(answers, item)->0/1.  Mirrors f3r1.eval_ctx exactly (same cache keys)."""
    from concurrent.futures import ThreadPoolExecutor

    def work(item):
        case, _w, _q, _u = item
        memory, question = ctx_fn(item)
        user = f2.render_answer_prompt(question, case.documents, memory)
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
            correct = int(bool(score_fn(answers, item)))
        except Exception:  # noqa: BLE001
            parse_ok = False
        return {"case_id": case.case_id, "correct": correct, "parse_ok": parse_ok,
                "cached": meta["cached"]}

    with ThreadPoolExecutor(max_workers=parallel) as pool:
        rows = list(pool.map(work, items))
    n = len(rows)
    return {
        "accuracy": sum(r["correct"] for r in rows) / n,
        "parse_failures": sum(1 for r in rows if not r["parse_ok"]),
        "correct_vector": [r["correct"] for r in rows],
    }


def detail_ctx(question: str):
    return lambda memory: (memory, question)


def score_detail(answers, item) -> bool:
    case = item[0]
    return f2.normalized_set(answers) == f2.normalized_set(case.expected_answers)


GIST_SYSTEM = (
    "You answer which record class a memory store treats as authoritative. "
    "Output only strict JSON.")


def gist_verdict_probe(chat, model: str, items, memory: str, parallel: int,
                       seed: int):
    """Forced-choice gist probe (parent decision 2026-07-26): the free-form
    meta-question scored 0 everywhere in smoke 1784997083 — the answerer
    shape elicits entity names, not class codes.  Same donor-verdict form
    as F3: candidates listed, strict JSON {"authoritative": ...}, memory
    only (no case documents)."""
    from concurrent.futures import ThreadPoolExecutor

    def work(item):
        case = item[0]
        candidates = sorted({case.trusted_class, case.distractor_class})
        payload = {
            "memory_context": memory,
            "candidate_classes": candidates,
            "instruction": (
                "Using only the memory_context, decide which candidate class "
                "is treated as authoritative when records conflict. Return "
                "strict JSON {\"authoritative\": \"<one of candidate_classes>\"} "
                "with no other keys."),
        }
        meta = chat.chat(model=model, system=GIST_SYSTEM,
                         user=json.dumps(payload, ensure_ascii=False,
                                         sort_keys=True),
                         seed=seed, max_tokens=64)
        correct, parse_ok = 0, True
        try:
            if meta["finish_reason"] != "stop":
                raise ValueError("finish_reason")
            value = json.loads(meta["text"])["authoritative"]
            if value not in candidates:
                raise ValueError("out_of_candidates")
            correct = int(value == case.trusted_class)
        except Exception:  # noqa: BLE001
            parse_ok = False
        return {"case_id": case.case_id, "correct": correct,
                "parse_ok": parse_ok, "cached": meta["cached"]}

    with ThreadPoolExecutor(max_workers=parallel) as pool:
        rows = list(pool.map(work, items))
    n = len(rows)
    return {
        "accuracy": sum(r["correct"] for r in rows) / n,
        "parse_failures": sum(1 for r in rows if not r["parse_ok"]),
        "correct_vector": [r["correct"] for r in rows],
    }


# ---------------------------------------------------------------- store
def rank_store(store: list[StoreRec]):
    return sorted(store, key=lambda r: (-r.confidence, r.lesson.lesson_id))


def pack_lessons(ranked, budget_chars: int):
    packed, used = [], 40
    for rec in ranked:
        cost = len(rec.lesson.instruction) + 120
        if packed and used + cost > budget_chars:
            break
        packed.append(rec)
        used += cost
    return packed, used


def render_store(store, budget_chars: int, question: str) -> str:
    packed, _used = pack_lessons(rank_store(store), budget_chars)
    if not packed:
        return ""
    lessons = [r.lesson for r in packed]
    selection = retrieve_lessons(question, lessons, top_k=len(lessons))
    return render_lesson_context(selection, lessons)


def render_store_gist_probe(store, budget_chars: int) -> str:
    packed, _used = pack_lessons(rank_store(store), budget_chars)
    if not packed:
        return ""
    payload = {
        "schema_version": "hswm-p1v2-lesson-context/v1",
        "lessons": [{
            "lesson_id": r.lesson.lesson_id,
            "scope_predicate": r.lesson.scope_predicate.canonical(),
            "instruction": r.lesson.instruction,
            "polarity": r.lesson.polarity,
            "confidence": r.confidence,
        } for r in packed],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def store_snapshot(store) -> str:
    return hashlib.sha256(json.dumps(
        [r.snapshot() for r in store], sort_keys=True).encode()).hexdigest()


def sleep_pass(store: list[StoreRec], current_episode: int, train_cases_by_origin: dict,
               snapshots: list) -> None:
    """Deterministic consolidation: downscale full-form, compress-to-gist at theta."""
    for rec in store:
        if rec.origin >= current_episode or rec.form == "gist":
            continue  # newest episode untouched; gist lessons are pinned
        rec.confidence *= ALPHA
        if rec.confidence < THETA:
            case = train_cases_by_origin[rec.origin][0]
            gist_lesson = compile_lesson(
                case, teach=case.trusted_class, ignore=case.distractor_class,
                confidence=GIST_FLOOR,
                supersedes=(rec.lesson.lesson_id,),
                gist=True, known_ids=(rec.lesson.lesson_id,))
            rec.lesson = gist_lesson
            rec.form = "gist"
            rec.confidence = GIST_FLOOR
    snapshots.append(store_snapshot(store))


# ---------------------------------------------------------------- splits
def build_splits_f5(pool, article_cache, *, n_episodes: int, n_fresh_ep: int,
                    max_answers: int, split_seed: int):
    order = list(pool)
    random.Random(f"f5-split-{split_seed}").shuffle(order)
    quotas = {"train": n_episodes, "fresh": n_episodes * n_fresh_ep}
    splits: dict[str, list] = {name: [] for name in quotas}
    skipped: dict[str, list] = {name: [] for name in quotas}
    cursor = 0
    for name, quota in quotas.items():
        while len(splits[name]) < quota and cursor < len(order):
            entry = order[cursor]
            cursor += 1
            if name == "train":
                ep = len(splits[name])
            else:
                ep = len(splits[name]) // n_fresh_ep
            trusted, distractor = WORLDS[ep]
            question = entry["question"]
            try:
                case = build_policy_conflict_case(
                    case_id=f"f5-{name}-e{ep}-{question['id'][:8]}",
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
            splits[name].append((case, ep, question, entry["universe"]))
        if len(splits[name]) < quota:
            raise F5Error(f"split '{name}' filled {len(splits[name])}/{quota}")
    return {"splits": splits, "skipped": skipped}


# ---------------------------------------------------------------- stats
def least_squares_slope(xs, ys) -> float:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom if denom else 0.0


def bootstrap_slope_diff(vecs_a, vecs_b, lags, *, n_boot: int, seed: int):
    """vecs_*: per-lag correctness vectors; paired resample within lags."""
    rng = random.Random(seed)
    diffs = []
    for _ in range(n_boot):
        def means(vecs):
            return [sum(v[i] for i in [rng.randrange(len(v)) for _ in v]) / len(v)
                    for v in vecs]
        ma, mb = means(vecs_a), means(vecs_b)
        diffs.append(least_squares_slope(lags, ma) - least_squares_slope(lags, mb))
    diffs.sort()
    return {"mean": sum(diffs) / n_boot,
            "ci95": [diffs[int(0.025 * n_boot)], diffs[int(0.975 * n_boot)]]}


def paired_gap(vals_a, vals_b, *, n_boot: int, seed: int):
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


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--episodes", type=int, default=8)
    ap.add_argument("--n-fresh-ep", type=int, default=12)
    ap.add_argument("--token-budget-chars", type=int, default=1600)
    ap.add_argument("--split-seed", type=int, default=20260730)
    ap.add_argument("--seed", type=int, default=20260725)
    ap.add_argument("--max-answers", type=int, default=1)
    ap.add_argument("--max-calls", type=int, default=1000)
    ap.add_argument("--parallel", type=int, default=16)
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--universes-dir", type=Path,
                    default=HERE / "_research" / "f2_sealed_universes")
    ap.add_argument("--answer-backend", choices=("ollama", "vllm"), default="vllm")
    ap.add_argument("--answer-url", default="http://127.0.0.1:18000/v1")
    ap.add_argument("--answer-model", default="qwen3.6-27b")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    if args.smoke:
        args.episodes = 4
        args.n_fresh_ep = 4
        args.token_budget_chars = 800
        args.max_calls = 120
    E = args.episodes
    t0 = time.time()
    ts = int(t0)
    out_path = Path(args.out) if args.out else (
        RECEIPT_DIR / f"f5_consolidation_{'smoke' if args.smoke else 'sealed'}_{ts}.json")

    receipt = {
        "schema_version": "hswm-f5-consolidation-receipt/v1",
        "mode": "development",
        "branch": "F5-consolidation",
        "smoke": bool(args.smoke),
        "preregistration_file": str(PREREG_PATH),
        "preregistration_file_sha256": hashlib.sha256(
            PREREG_PATH.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "harness_module_sha256": hashlib.sha256(
            (HERE / "f2_delta_w_credit.py").read_bytes()).hexdigest(),
        "config": vars(args) | {"out": str(out_path),
                                "universes_dir": str(args.universes_dir),
                                "delta": DELTA, "alpha": ALPHA,
                                "theta": THETA, "gist_floor": GIST_FLOOR},
        "consolidation_operator_definition": {
            "wake": "correct typed lesson per episode; initial confidence "
                    "c0 = 0.5 + 0.5*(acc_with_lesson - acc_without) on the "
                    "episode's training case (Hebbian contribution).",
            "sleep": f"after episode k<E-1: for every lesson with origin<k, "
                     f"confidence *= alpha ({ALPHA}); a full-form lesson with "
                     f"confidence < theta ({THETA}) is COMPRESSED to the gist "
                     f"form {GIST_TEMPLATE!r} (supersedes chain) pinned at "
                     f"gist_floor ({GIST_FLOOR} = the typed-lesson admission "
                     f"floor); gist lessons are never evicted.",
            "edge_weight_meaning": "edge weight = Hebbian delta-s (c0) + "
                     "downscale alpha per sleep (foundation "
                     "semantic-weight-metric-contract self-fulfillment note).",
            "retrieval": "rank by (confidence desc, lesson_id), pack into the "
                     "shared char budget (per-lesson cost = instruction chars + 120).",
        },
        "prereg_reading_deviations": [
            "simulated-lag: wall-clock weeks replaced by episode-interference "
            "lag — retention of episode i is probed at the final state, "
            "lag(i) = (E-1)-i subsequent episodes.",
            "decay model: hierarchical function-form comparison (Murre&Dros) "
            "read as least-squares slope with paired bootstrap CI.",
            "gist probe form: forced-choice verdict (parent decision "
            "2026-07-26) — candidate classes listed, strict JSON "
            '{"authoritative": ...}, memory_context only, no case documents; '
            "the free-form meta-question scored 0 for all arms in smoke "
            "1784997083 (answerer shape elicits entity names, not class codes).",
            "schema-generalization probe read as gist accuracy on episodes "
            "whose lessons were compressed (gist form generalizes) vs "
            "uncompressed (CLS-prediction composition out of scope here).",
        ],
        "answerer_freeze": {
            "backend": args.answer_backend, "url": args.answer_url,
            "model": args.answer_model,
            "note": "qwen3.6-27b (ollama qwen3:8b is actuation-incapable per "
                    "F3-r3 smoke and is not used anywhere).",
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
        pool, pool_stats = f2.load_question_pool(args.universes_dir, args.max_answers)
        receipt["question_pool"] = pool_stats
        article_cache = f2._ArticleCache(args.universes_dir)
        built = build_splits_f5(pool, article_cache, n_episodes=E,
                                n_fresh_ep=args.n_fresh_ep,
                                max_answers=args.max_answers,
                                split_seed=args.split_seed)
        train_cases = built["splits"]["train"]
        fresh_cases = built["splits"]["fresh"]
        receipt["splits"] = {
            "n_train": len(train_cases), "n_fresh": len(fresh_cases),
            "skipped": built["skipped"], "split_seed": args.split_seed,
            "fresh_episode_sizes": {ep: sum(1 for _c, w, _q, _u in fresh_cases if w == ep)
                                    for ep in range(E)},
        }
        receipt["leakage"] = f2.leakage_report(train_cases, [], fresh_cases)
        train_by_origin = {item[1]: item for item in train_cases}
        fresh_by_ep = {ep: [item for item in fresh_cases if item[1] == ep]
                   for ep in range(E)}

        # ---- timeline: wakes (shared) + sleeps (arm A) ----
        store: list[StoreRec] = []
        snapshots: list[str] = []
        wake_meta = []
        for k in range(E):
            item = train_by_origin[k]
            case = item[0]
            lesson_full = compile_lesson(
                case, teach=case.trusted_class, ignore=case.distractor_class,
                confidence=1.0)
            by_id = {lesson_full.lesson_id: lesson_full}
            res_with = f3r1.eval_ctx(answerer, args.answer_model,
                                     ("lessons", (lesson_full.lesson_id,)),
                                     [item], by_id, args.parallel, args.seed)
            res_without = f3r1.eval_ctx(answerer, args.answer_model, ("none",),
                                        [item], by_id, args.parallel, args.seed)
            delta = res_with["correct_vector"][0] - res_without["correct_vector"][0]
            c0 = 0.5 + 0.5 * delta
            lesson = compile_lesson(
                case, teach=case.trusted_class, ignore=case.distractor_class,
                confidence=c0)
            store.append(StoreRec(lesson=lesson, origin=k, form="full",
                                  confidence=c0))
            wake_meta.append({"episode": k, "acc_with": res_with["correct_vector"][0],
                              "acc_without": res_without["correct_vector"][0],
                              "c0": c0})
            if k < E - 1:
                sleep_pass(store, k, train_by_origin, snapshots)
        store_c = [StoreRec(lesson=r.lesson, origin=r.origin, form="full",
                            confidence=wake_meta[r.origin]["c0"])
                   for r in store]  # C: same lessons, never slept, full form
        receipt["timeline"] = {
            "wake": wake_meta,
            "sleep_snapshot_sha256": snapshots,
            "final_store_A": [r.snapshot() for r in store],
        }

        lags = [(E - 1 - ep) for ep in range(E)]

        # ---- probes ----
        transcripts = {ep: render_policy_training_transcript(train_by_origin[ep][0])
                       for ep in range(E)}

        def arm_b_ctx(ep):
            return lambda item: (
                transcripts[ep][:args.token_budget_chars], item[0].question)

        results = {"A": {"detail": {}, "gist": {}},
                   "C": {"detail": {}, "gist": {}},
                   "B": {"detail": {}, "gist": {}}}
        parse_fail_total = 0
        for ep in range(E):
            items = fresh_by_ep[ep]
            q0 = items[0][0].question
            # arm A
            mem_a = render_store(store, args.token_budget_chars, q0)
            r = f5_eval(answerer, args.answer_model, items,
                        lambda item, mem=mem_a: (mem, item[0].question),
                        score_detail, args.parallel, args.seed)
            results["A"]["detail"][ep] = r
            parse_fail_total += r["parse_failures"]
            mem_ag = render_store_gist_probe(store, args.token_budget_chars)
            r = gist_verdict_probe(answerer, args.answer_model, items, mem_ag,
                                   args.parallel, args.seed)
            results["A"]["gist"][ep] = r
            parse_fail_total += r["parse_failures"]
            # arm C
            mem_c = render_store(store_c, args.token_budget_chars, q0)
            r = f5_eval(answerer, args.answer_model, items,
                        lambda item, mem=mem_c: (mem, item[0].question),
                        score_detail, args.parallel, args.seed)
            results["C"]["detail"][ep] = r
            parse_fail_total += r["parse_failures"]
            mem_cg = render_store_gist_probe(store_c, args.token_budget_chars)
            r = gist_verdict_probe(answerer, args.answer_model, items, mem_cg,
                                   args.parallel, args.seed)
            results["C"]["gist"][ep] = r
            parse_fail_total += r["parse_failures"]
            # arm B
            mem_b = transcripts[ep][:args.token_budget_chars]
            r = f5_eval(answerer, args.answer_model, items,
                        lambda item, mem=mem_b: (mem, item[0].question),
                        score_detail, args.parallel, args.seed)
            results["B"]["detail"][ep] = r
            parse_fail_total += r["parse_failures"]
            r = gist_verdict_probe(answerer, args.answer_model, items, mem_b,
                                   args.parallel, args.seed)
            results["B"]["gist"][ep] = r
            parse_fail_total += r["parse_failures"]

        # ---- immediate A probes (BWT) + base ----
        immediate = {}
        base_detail = {}
        store_im: list[StoreRec] = []
        for k in range(E):
            item = train_by_origin[k]
            case = item[0]
            c0 = wake_meta[k]["c0"]
            lesson = compile_lesson(
                case, teach=case.trusted_class, ignore=case.distractor_class,
                confidence=c0)
            store_im.append(StoreRec(lesson=lesson, origin=k, form="full",
                                     confidence=c0))
            mem = render_store(store_im, args.token_budget_chars,
                               fresh_by_ep[k][0][0].question)
            r = f5_eval(answerer, args.answer_model, fresh_by_ep[k],
                        lambda item, mem=mem: (mem, item[0].question),
                        score_detail, args.parallel, args.seed)
            immediate[k] = r
            parse_fail_total += r["parse_failures"]
            r = f5_eval(answerer, args.answer_model, fresh_by_ep[k],
                        lambda item: ("", item[0].question),
                        score_detail, args.parallel, args.seed)
            base_detail[k] = r
            parse_fail_total += r["parse_failures"]

        # ---- curves ----
        def curve(arm, kind):
            return [results[arm][kind][ep]["accuracy"] for ep in range(E)]

        def vecs(arm, kind):
            return [results[arm][kind][ep]["correct_vector"] for ep in range(E)]

        R = {arm: {"detail": curve(arm, "detail"), "gist": curve(arm, "gist")}
             for arm in ("A", "B", "C")}
        receipt["retention_curves"] = {
            "lags": lags,
            "R_detail": {arm: R[arm]["detail"] for arm in R},
            "R_gist": {arm: R[arm]["gist"] for arm in R},
            "base_detail": [base_detail[ep]["accuracy"] for ep in range(E)],
            "immediate_A_detail": [immediate[ep]["accuracy"] for ep in range(E)],
        }
        receipt["headroom_band"] = list(HEADROOM_BAND)
        receipt["headroom_band_ok"] = headroom_band_ok(
            sum(base_detail[ep]["accuracy"] for ep in range(E)) / E, *HEADROOM_BAND)

        slope_a = least_squares_slope(lags, R["A"]["detail"])
        slope_b = least_squares_slope(lags, R["B"]["detail"])
        slope_c = least_squares_slope(lags, R["C"]["detail"])
        sd_ac = bootstrap_slope_diff(vecs("A", "detail"), vecs("C", "detail"),
                                     lags, n_boot=args.n_boot, seed=args.seed)
        sd_ab = bootstrap_slope_diff(vecs("A", "detail"), vecs("B", "detail"),
                                     lags, n_boot=args.n_boot, seed=args.seed)
        receipt["decay_slopes"] = {
            "slope_A": round(slope_a, 4), "slope_B": round(slope_b, 4),
            "slope_C": round(slope_c, 4),
            "A_minus_C": {"diff": round(slope_a - slope_c, 4),
                          "ci95": [round(x, 4) for x in sd_ac["ci95"]]},
            "A_minus_B": {"diff": round(slope_a - slope_b, 4),
                          "ci95": [round(x, 4) for x in sd_ab["ci95"]]},
            "method": "least-squares slope of R_detail(t) vs lag; paired "
                      "bootstrap over per-lag case vectors (prereg hierarchical "
                      "fit read as bootstrap slope CI).",
        }

        # ---- judgment conditions + kills ----
        gap_ab = [R["A"]["detail"][i] - R["B"]["detail"][i] for i in range(E)]
        gap_ac = [R["A"]["detail"][i] - R["C"]["detail"][i] for i in range(E)]
        lag4_idx = [i for i in range(E) if lags[i] >= 4]
        cond1 = (bool(lag4_idx)
                 and all(gap_ab[i] >= DELTA for i in lag4_idx)
                 and all(gap_ac[i] >= DELTA for i in lag4_idx))
        cond2 = sd_ac["ci95"][0] > 0 and sd_ab["ci95"][0] > 0
        receipt["judgment_conditions"] = {
            "cond1_A_dominates_lag4plus_by_delta": cond1,
            "cond2_A_slope_shallower_significant": cond2,
            "lag4plus_indices": lag4_idx,
            "note": ("smoke has max lag 3 -> cond1 not evaluable"
                     if not lag4_idx else "evaluated at lags "
                     + str([lags[i] for i in lag4_idx])),
        }
        receipt["kill_condition_observations"] = {
            "f5_k1_B_within_delta_all_lags": min(gap_ab) <= DELTA,
            "f5_k2_A_minus_C_le_delta_all_lags": max(gap_ac) <= DELTA,
            "f5_k3_advantage_only_at_lag0": (
                gap_ac[-1] > DELTA and max(gap_ac[:-1] or [0]) <= DELTA),
            "values": {"gap_A_minus_B": [round(x, 4) for x in gap_ab],
                       "gap_A_minus_C": [round(x, 4) for x in gap_ac]},
            "note": "mechanical observation only; sealed judgment belongs to the gate",
        }

        # ---- secondary endpoints ----
        gist_slope_a = least_squares_slope(lags, R["A"]["gist"])
        receipt["gist_detail_branch"] = {
            "detail_slope_A": round(slope_a, 4),
            "gist_slope_A": round(gist_slope_a, 4),
            "transformation_signature": bool(
                slope_a < -0.01 and gist_slope_a >= -0.01),
        }
        receipt["BWT_FWT"] = {
            "BWT_per_episode": [round(immediate[ep]["accuracy"]
                                      - R["A"]["detail"][ep], 4)
                                for ep in range(E)],
            "FWT_slope_immediate_over_episode": round(least_squares_slope(
                list(range(E)), [immediate[ep]["accuracy"] for ep in range(E)]), 4),
            "note": "GEM format: BWT = immediate minus final-lag retention per "
                    "episode; FWT = slope of wake-time actuation over episodes.",
        }
        # conflict density: inject 0/1/2 contradictory lessons into A's render
        ref_ep = 0
        ref_case = train_by_origin[ref_ep][0]
        conflict_acc = []
        for n_inj in (0, 1, 2):
            injected = list(store)
            for j in range(n_inj):
                src = train_by_origin[j][0]
                inv = compile_lesson(
                    src, teach=src.distractor_class, ignore=src.trusted_class,
                    confidence=1.0)
                injected.append(StoreRec(lesson=inv, origin=-(j + 1),
                                         form="injected", confidence=1.0))
            mem = render_store(injected, args.token_budget_chars,
                               fresh_by_ep[ref_ep][0][0].question)
            r = f5_eval(answerer, args.answer_model, fresh_by_ep[ref_ep],
                        lambda item, mem=mem: (mem, item[0].question),
                        score_detail, args.parallel, args.seed)
            conflict_acc.append(r["accuracy"])
            parse_fail_total += r["parse_failures"]
        receipt["conflict_density"] = {
            "injected_counts": [0, 1, 2],
            "accuracy_A_ref_episode": [round(x, 4) for x in conflict_acc],
            "note": "contradictory (inverted) lesson injection into arm A's "
                    "render; resolution read as accuracy retention.",
        }
        receipt["cost_metric"] = {
            "mean_context_chars": {
                "A": sum(len(render_store(store, args.token_budget_chars,
                                          fresh_by_ep[ep][0][0].question))
                         for ep in range(E)) / E,
                "B": sum(len(transcripts[ep][:args.token_budget_chars])
                         for ep in range(E)) / E,
                "C": sum(len(render_store(store_c, args.token_budget_chars,
                                          fresh_by_ep[ep][0][0].question))
                         for ep in range(E)) / E,
            },
            "chars_per_correct_answer": {
                arm: round(
                    (sum(len(render_store(store if arm == "A" else store_c,
                                          args.token_budget_chars,
                                          fresh_by_ep[ep][0][0].question))
                         for ep in range(E)) / E)
                    / max(sum(R[arm]["detail"]) / E, 1e-9), 1)
                for arm in ("A", "C")
            } | {"B": round(
                (sum(len(transcripts[ep][:args.token_budget_chars])
                     for ep in range(E)) / E)
                / max(sum(R["B"]["detail"]) / E, 1e-9), 1)},
        }
        receipt["parse_failures_total"] = parse_fail_total
    except (F5Error, f2.BudgetExceeded) as err:
        aborted = str(err)
    except Exception as err:  # noqa: BLE001
        aborted = f"{type(err).__name__}: {err}"

    receipt["llm_budget"] = {
        "max_calls": args.max_calls, "used": budget.used,
        "answerer": {"backend": args.answer_backend, "url": args.answer_url,
                     "model": args.answer_model,
                     "misses": answerer.misses, "hits": answerer.hits},
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
        "retention_curves": receipt.get("retention_curves"),
        "decay_slopes": receipt.get("decay_slopes"),
        "judgment_conditions": receipt.get("judgment_conditions"),
        "kill": {k: v for k, v in receipt.get("kill_condition_observations", {}).items()
                 if k.startswith("f5")},
        "gist_detail_branch": receipt.get("gist_detail_branch"),
        "final_store_A": receipt.get("timeline", {}).get("final_store_A"),
        "parse_failures_total": receipt.get("parse_failures_total"),
    }, indent=1, ensure_ascii=False))
    return 0 if aborted is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
