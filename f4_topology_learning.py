"""F4 gate (learned topology rewiring) development/sealed harness.

PREREG (locked, read-only input): prom_search_hswm/evidence/
PREREG_f4_topology_learning_20260725.json (in the SYMPOSIUM/HSWM checkout).

Receipts from this script are always mode="development" measurements; the
scientific judgment belongs to the HSWM_LOCAL_RECORD gate, never to this file.

Design (WANN-style W-freeze):
  store       L typed source-policy lessons (frozen content, compiled once
              from train cases).  L/5 worlds per group share one trusted
              class C_g with per-world distractors Q01..; the LAST world of
              each group is a PLANTED INVERTED lesson (teach distractor,
              ignore C_g) so group-mates partition into helpful (trust C_g)
              vs harmful (ignore C_g) neighbours.  This is what gives
              topology a causal channel through retrieval: a question of
              world w seeds its own lesson, and the (k-1) neighbours are
              chosen by the edge set ONLY — weights, budget, seed and render
              are identical across arms, only the topology differs.
  learner     Hebbian co-firing on the training trajectory: per train case
              of world w, eval {w} then {w, l} per same-group mate l;
              edge {w,l} gains (acc_with - acc_without); edges with W>0 are
              kept (E_learned).  Simple on purpose — the claim is "learned
              structure beats null structures", not "the learner is optimal".
  arms        A E_learned / B degree-preserving shuffle (null battery) /
              C clique completion / D |E|-matched random sparse.
  curve       top-k removal by edge importance (LOO-measured for the top-M
              edges, learned-weight beyond) vs seeded random removal;
              AUC gap = mean(rand_acc - top_acc) with paired bootstrap CI.
  rho         Spearman(topology edit distance between learning checkpoints,
              |delta fresh accuracy|) with bootstrap CI.
  kills       f4_k1 any control >= A (point, CI reported) / f4_k2 AUC gap CI
              includes 0 / f4_k3 rho CI includes 0.

Answerer/critic plumbing, question pool, disk cache and receipt shape are
reused from f2_delta_w_credit.py (imported as a module, unmodified).
--smoke runs the full path at L=12/g=4x3, n-fresh 6, within ~96 calls.

Usage:
  .venv/bin/python f4_topology_learning.py --smoke
  .venv/bin/python f4_topology_learning.py --universes-dir _research/f2_sealed_universes
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
NULL_BATTERY_DIR = Path("/Users/lagyeongjun/CD/SYMPOSIUM/HSWM/prom_search_hswm")
sys.path.insert(0, str(NULL_BATTERY_DIR))

f2 = importlib.import_module("f2_delta_w_credit")

from p1v2_typed_lesson import LessonCompilePolicyV1, compile_typed_lesson  # noqa: E402
from p1v3_policy_environment import (  # noqa: E402
    build_policy_conflict_case,
    render_policy_training_transcript,
    verify_policy_oracle_admission,
)
from hswm_null_battery import degree_preserving_shuffle, headroom_band_ok  # noqa: E402

PREREG_PATH = NULL_BATTERY_DIR / "evidence" / "PREREG_f4_topology_learning_20260725.json"
RECEIPT_DIR = HERE / "receipts"
GROUP_TRUSTED = ("RHO", "SIGMA", "GAMMA", "KAPPA", "OMEGA", "ALPHA")
HEADROOM_BAND = (0.3, 0.7)
SCOPE = {
    "all_terms": ["who is", "the person whose"],
    "any_terms": ["occupation", "hobby", "date of birth", "gender"],
    "excluded_terms": [],
}


class F4Error(RuntimeError):
    pass


# ---------------------------------------------------------------- worlds
def make_worlds(n_lessons: int, n_groups: int) -> list[dict]:
    """L worlds in G groups; last world of each group is planted inverted."""
    if n_lessons % n_groups:
        raise F4Error("--lessons must be a multiple of --groups")
    size = n_lessons // n_groups
    worlds = []
    for idx in range(n_lessons):
        g, j = divmod(idx, size)
        worlds.append({
            "world_idx": idx,
            "group": g,
            "trusted": GROUP_TRUSTED[g],
            "distractor": f"Q{idx + 1:02d}",
            "orientation": "planted_inverted" if j == size - 1 else "correct",
        })
    return worlds


# ---------------------------------------------------------------- splits
def build_splits(pool, article_cache, *, worlds, n_fresh: int,
                 max_answers: int, split_seed: int):
    """Seeded shuffle of the deduped pool, then train |W| + fresh n slices."""
    order = list(pool)
    random.Random(f"f4-split-{split_seed}").shuffle(order)
    quotas = {"train": len(worlds), "fresh": n_fresh}
    splits: dict[str, list] = {name: [] for name in quotas}
    skipped: dict[str, list] = {name: [] for name in quotas}
    cursor = 0
    for name, quota in quotas.items():
        while len(splits[name]) < quota and cursor < len(order):
            entry = order[cursor]
            cursor += 1
            world = worlds[len(splits[name]) % len(worlds)]
            question = entry["question"]
            try:
                case = build_policy_conflict_case(
                    case_id=f"f4-{name}-{question['id'][:12]}",
                    question=question["question"],
                    articles=article_cache.articles(entry["universe"]),
                    trusted_class=world["trusted"],
                    distractor_class=world["distractor"],
                    maximum_true_documents=max_answers,
                )
            except Exception as err:  # noqa: BLE001 - record and skip, never fudge
                skipped[name].append({
                    "question_id": question.get("id"), "universe": entry["universe"],
                    "error": type(err).__name__})
                continue
            if list(case.expected_answers) != sorted(question["answer"]):
                skipped[name].append({
                    "question_id": question.get("id"), "universe": entry["universe"],
                    "error": "gold_mismatch"})
                continue
            splits[name].append((case, world["world_idx"], question, entry["universe"]))
        if len(splits[name]) < quota:
            raise F4Error(
                f"split '{name}' filled {len(splits[name])}/{quota} from "
                f"{len(order)} unique texts; widen --max-answers or add universes")
    return {"splits": splits, "skipped": skipped}


# ---------------------------------------------------------------- lessons
def compile_lessons(train_cases, worlds) -> tuple[dict, dict]:
    lessons: dict[str, object] = {}
    meta: dict[str, dict] = {}
    for world in worlds:
        case, w, question, universe = train_cases[world["world_idx"]]
        assert w == world["world_idx"]
        episode_id = f"policy-training:{case.case_id}"
        transcript = render_policy_training_transcript(case)
        evidence_id = "policy-training-evidence:" + case.derivation_sha256
        if world["orientation"] == "correct":
            teach, ignore = world["trusted"], world["distractor"]
        else:
            teach, ignore = world["distractor"], world["trusted"]
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
        admission = "skipped_planted_inverted"
        if world["orientation"] == "correct":
            verify_policy_oracle_admission(
                lesson, trusted_class=world["trusted"],
                distractor_class=world["distractor"])
            admission = "oracle_admission_passed"
        lessons[world["world_idx"]] = lesson
        meta[world["world_idx"]] = {
            "lesson_id": lesson.lesson_id, "group": world["group"],
            "trusted_class": world["trusted"],
            "distractor_class": world["distractor"],
            "orientation": world["orientation"], "admission": admission,
            "training_case_id": case.case_id, "training_universe": universe,
            "training_transcript_sha256": f2.canonical_sha256({"t": transcript}),
        }
    return lessons, meta


# ---------------------------------------------------------------- topology
def mates_of(world_idx: int, n_lessons: int, group_size: int) -> list[int]:
    g = world_idx // group_size
    return [g * group_size + j for j in range(group_size)
            if g * group_size + j != world_idx]


def learn_topology(answerer, answer_model: str, train_cases, worlds, lessons,
                   n_lessons: int, group_size: int, parallel: int, seed: int,
                   checkpoint_at: set[int]):
    """Hebbian co-firing; returns edge weights, kept edge set, checkpoints."""
    weights: dict[tuple[int, int], int] = {}
    checkpoints: list[dict] = []
    by_id = lessons_by_id(lessons)

    def kept_edges():
        return {pair for pair, w in weights.items() if w > 0}

    for case_idx, item in enumerate(train_cases):
        _case, w, _q, _u = item
        mates = sorted(mates_of(w, n_lessons, group_size))
        ctxs = [(w,)] + [(w, l) for l in mates]
        units = [(
            tuple(sorted(lessons[l].lesson_id for l in ctx)), item)
            for ctx in ctxs]
        rows = eval_units(answerer, answer_model, units, by_id, parallel, seed)
        results = {ctx: row["correct"] for ctx, row in zip(ctxs, rows)}
        base = results[(w,)]
        for l in mates:
            pair = tuple(sorted((w, l)))
            weights[pair] = weights.get(pair, 0) + (results[(w, l)] - base)
        if case_idx + 1 in checkpoint_at:
            checkpoints.append({
                "after_case": case_idx + 1,
                "edges": sorted(tuple(sorted(e)) for e in kept_edges()),
            })
    return weights, kept_edges(), checkpoints


def lessons_by_id(lessons: dict) -> dict:
    return {lesson.lesson_id: lesson for lesson in lessons.values()}


# --------------------------------------------------------------- batched eval
def eval_units(answerer, answer_model: str, units, by_id: dict,
               parallel: int, seed: int):
    """Evaluate (subset_ids, case_item) units in one worker pool.

    Each unit has its own lesson subset (topology-dependent), so the shared
    f2.evaluate_subset (one subset for all cases) cannot be used; the render,
    parse and scoring path below mirrors it exactly (same prompt, same cache
    keys, same set-match)."""
    from concurrent.futures import ThreadPoolExecutor

    def work(unit):
        subset_ids, item = unit
        case, _w, _q, _u = item
        ctx = f2.memory_context(case.question, tuple(sorted(subset_ids)), by_id)
        user = f2.render_answer_prompt(case.question, case.documents, ctx)
        meta = answerer.chat(model=answer_model, system=f2.P1V2_SYSTEM_PROMPT,
                             user=user, seed=seed, max_tokens=256)
        correct = 0
        parse_ok = True
        try:
            if meta["finish_reason"] != "stop":
                raise ValueError("finish_reason")
            payload = json.loads(meta["text"])
            answers = payload["answers"]
            if not isinstance(answers, list):
                raise ValueError("answers")
            correct = int(f2.normalized_set(answers)
                          == f2.normalized_set(case.expected_answers))
        except Exception:  # noqa: BLE001 - dev harness counts, never repairs
            parse_ok = False
        return {"case_id": case.case_id, "correct": correct,
                "parse_ok": parse_ok, "cached": meta["cached"]}

    with ThreadPoolExecutor(max_workers=parallel) as pool:
        return list(pool.map(work, units))


def neighbors(edge_set, w: int, n_lessons: int) -> list[int]:
    return sorted(l for l in range(n_lessons)
                  if l != w and tuple(sorted((w, l))) in edge_set)


def context_subset(edge_set, w: int, lessons: dict, k_context: int) -> tuple:
    ids = [lessons[w].lesson_id]
    for l in neighbors(edge_set, w, len(lessons)):
        if len(ids) >= k_context:
            break
        ids.append(lessons[l].lesson_id)
    return tuple(sorted(ids))


def eval_topology(answerer, answer_model: str, edge_set, cases, lessons,
                  k_context: int, parallel: int, seed: int):
    """Accuracy of a topology: per case, seed lesson + (k-1) neighbours."""
    by_id = lessons_by_id(lessons)
    units = [(context_subset(edge_set, w, lessons, k_context), item)
            for item in cases
            for case, w, _q, _u in [item]]
    rows = eval_units(answerer, answer_model, units, by_id, parallel, seed)
    n = len(rows)
    return {
        "accuracy": sum(r["correct"] for r in rows) / n,
        "parse_failures": sum(1 for r in rows if not r["parse_ok"]),
        "correct_vector": [r["correct"] for r in rows],
    }


def clique_edges(n_lessons: int):
    return {tuple(sorted((i, j))) for i in range(n_lessons)
            for j in range(i + 1, n_lessons)}


def random_sparse_edges(n_lessons: int, count: int, seed: str):
    rng = random.Random(seed)
    all_pairs = sorted(clique_edges(n_lessons))
    return set(rng.sample(all_pairs, min(count, len(all_pairs))))


def shuffle_edges(edge_set, seed: str):
    shuffled = degree_preserving_shuffle(
        [list(e) for e in sorted(edge_set)], seed)
    return {tuple(e) for e in shuffled}


# ---------------------------------------------------------------- stats
def paired_bootstrap_gap(vecs_a, vecs_b, *, n_boot: int, seed: int):
    """CI of mean(a - b) over paired per-case vectors."""
    rng = random.Random(seed)
    n = len(vecs_a)
    diffs = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        diffs.append(sum(vecs_a[i] for i in idx) / n
                     - sum(vecs_b[i] for i in idx) / n)
    diffs.sort()
    return {
        "mean": sum(diffs) / n_boot,
        "ci95": [diffs[int(0.025 * n_boot)], diffs[int(0.975 * n_boot)]],
    }


def bootstrap_spearman_ci(points, *, n_boot: int, seed: int):
    rng = random.Random(seed)
    rhos = []
    for _ in range(n_boot):
        sample = [points[rng.randrange(len(points))] for _ in points]
        rho = f2.spearman([p[0] for p in sample], [p[1] for p in sample])
        if rho is not None:
            rhos.append(rho)
    if not rhos:
        return {"rho": None, "ci95": [None, None]}
    rhos.sort()
    return {"ci95": [rhos[int(0.025 * len(rhos))],
                     rhos[int(0.975 * len(rhos))]]}


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lessons", type=int, default=30)
    ap.add_argument("--groups", type=int, default=6)
    ap.add_argument("--n-fresh", type=int, default=50)
    ap.add_argument("--k-context", type=int, default=4,
                    help="lessons per context: seed + (k-1) neighbours")
    ap.add_argument("--loo-m", type=int, default=10,
                    help="top edges by learned weight that get LOO-measured importance")
    ap.add_argument("--curve-k", type=int, default=10,
                    help="cumulative removal steps for the ablation curve")
    ap.add_argument("--checkpoints", type=int, default=4,
                    help="learning checkpoints before the final topology")
    ap.add_argument("--split-seed", type=int, default=20260726)
    ap.add_argument("--seed", type=int, default=20260725)
    ap.add_argument("--max-answers", type=int, default=1)
    ap.add_argument("--max-calls", type=int, default=4000)
    ap.add_argument("--parallel", type=int, default=16)
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--universes-dir", type=Path,
                    default=HERE / "_research" / "f2_sealed_universes")
    ap.add_argument("--answer-backend", choices=("ollama", "vllm"), default="vllm")
    ap.add_argument("--answer-url", default="http://127.0.0.1:18000/v1")
    ap.add_argument("--answer-model", default="qwen3.6-27b")
    ap.add_argument("--skip-base", action="store_true",
                    help="skip the no-memory base eval (smoke budget)")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    if args.smoke:
        args.lessons = 12
        args.groups = 4
        args.n_fresh = 6
        args.k_context = 2
        args.loo_m = 2
        args.curve_k = 1
        args.checkpoints = 2
        args.max_calls = 100
        args.skip_base = True
    t0 = time.time()
    ts = int(t0)
    out_path = Path(args.out) if args.out else (
        RECEIPT_DIR / f"f4_topology_learning_{'smoke' if args.smoke else 'sealed'}_{ts}.json")

    group_size = args.lessons // args.groups
    receipt = {
        "schema_version": "hswm-f4-topology-learning-receipt/v1",
        "mode": "development",
        "branch": "F4-topology-learning",
        "smoke": bool(args.smoke),
        "preregistration_file": str(PREREG_PATH),
        "preregistration_file_sha256": hashlib.sha256(
            PREREG_PATH.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "harness_module_sha256": hashlib.sha256(
            (HERE / "f2_delta_w_credit.py").read_bytes()).hexdigest(),
        "config": vars(args) | {"out": str(out_path),
                                "universes_dir": str(args.universes_dir)},
        "answerer_freeze": {
            "backend": args.answer_backend, "url": args.answer_url,
            "model": args.answer_model,
            "note": "same freeze as the F2 sealed run (vLLM qwen3.6-27b, "
                    "thinking off via chat_template_kwargs; p1v4 lineage "
                    "Qwen3.6-35B-A3B-FP8 not served on this host)",
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
        worlds = make_worlds(args.lessons, args.groups)
        pool, pool_stats = f2.load_question_pool(args.universes_dir, args.max_answers)
        receipt["question_pool"] = pool_stats
        article_cache = f2._ArticleCache(args.universes_dir)
        built = build_splits(pool, article_cache, worlds=worlds,
                             n_fresh=args.n_fresh,
                             max_answers=args.max_answers,
                             split_seed=args.split_seed)
        train_cases = built["splits"]["train"]
        fresh_cases = built["splits"]["fresh"]
        receipt["splits"] = {
            "n_train": len(train_cases), "n_fresh": len(fresh_cases),
            "skipped": built["skipped"],
            "split_seed": args.split_seed,
            "fresh_case_worlds": [w for _c, w, _q, _u in fresh_cases],
        }
        receipt["leakage"] = f2.leakage_report(train_cases, [], fresh_cases)
        lessons, lesson_meta = compile_lessons(train_cases, worlds)
        receipt["lessons"] = {str(w): {k: v for k, v in lesson_meta[w].items()
                                       if k != "training_transcript_sha256"}
                              for w in sorted(lesson_meta)}

        # ---- base (headroom) ----
        if not args.skip_base:
            base = f2.evaluate_subset(answerer, args.answer_model, (), fresh_cases,
                                      lessons_by_id(lessons), args.parallel, args.seed)
            receipt["fresh_base_accuracy"] = base["accuracy"]
            receipt["headroom_band"] = list(HEADROOM_BAND)
            receipt["headroom_band_ok"] = headroom_band_ok(
                base["accuracy"], *HEADROOM_BAND)
        else:
            receipt["fresh_base_accuracy"] = None
            receipt["headroom_note"] = "base eval skipped (--skip-base)"

        # ---- learn topology ----
        n_cases = len(train_cases)
        checkpoint_at = {
            max(1, round(n_cases * (i + 1) / (args.checkpoints + 1)))
            for i in range(args.checkpoints)}
        weights, e_learned, checkpoints = learn_topology(
            answerer, args.answer_model, train_cases, worlds, lessons,
            args.lessons, group_size, args.parallel, args.seed, checkpoint_at)
        receipt["learning"] = {
            "edges_tested": len(weights),
            "edges_kept": len(e_learned),
            "edge_weights": {f"{a}-{b}": w for (a, b), w in sorted(weights.items())},
            "checkpoints": checkpoints,
            "group_size": group_size,
            "inverted_worlds": [w["world_idx"] for w in worlds
                                if w["orientation"] == "planted_inverted"],
        }

        # ---- arms ----
        edge_sets = {
            "A_learned": e_learned,
            "B_shuffled": shuffle_edges(e_learned, f"f4-shuffle-{args.seed}"),
            "C_clique": clique_edges(args.lessons),
            "D_random_sparse": random_sparse_edges(
                args.lessons, len(e_learned), f"f4-randsparse-{args.seed}"),
        }
        arms = {}
        for arm_id, edges in edge_sets.items():
            res = eval_topology(answerer, args.answer_model, edges, fresh_cases,
                                lessons, args.k_context, args.parallel, args.seed)
            arms[arm_id] = {
                "n_edges": len(edges),
                "fresh_accuracy": res["accuracy"],
                "fresh_parse_failures": res["parse_failures"],
                "correct_vector": res["correct_vector"],
            }
        receipt["arms"] = {
            k: {kk: vv for kk, vv in v.items() if kk != "correct_vector"}
            for k, v in arms.items()}

        # ---- edge ablation causal curve ----
        acc_a = arms["A_learned"]["fresh_accuracy"]
        ranked_edges = sorted(e_learned, key=lambda e: (-weights[e], e))
        loo_edges = ranked_edges[:args.loo_m]
        importance = {}
        for e in loo_edges:
            res = eval_topology(answerer, args.answer_model, e_learned - {e},
                                fresh_cases, lessons, args.k_context,
                                args.parallel, args.seed)
            importance[e] = acc_a - res["accuracy"]
        removal_order = loo_edges + [e for e in ranked_edges if e not in loo_edges]
        rng = random.Random(f"f4-curve-{args.seed}")
        random_order = list(e_learned)
        rng.shuffle(random_order)
        k_steps = min(args.curve_k, len(removal_order))
        curve_top, curve_rand = [], []
        for k in range(1, k_steps + 1):
            res_t = eval_topology(answerer, args.answer_model,
                                  e_learned - set(removal_order[:k]), fresh_cases,
                                  lessons, args.k_context, args.parallel, args.seed)
            res_r = eval_topology(answerer, args.answer_model,
                                  e_learned - set(random_order[:k]), fresh_cases,
                                  lessons, args.k_context, args.parallel, args.seed)
            curve_top.append(res_t)
            curve_rand.append(res_r)
        if k_steps >= 1:
            gap_per_k = [r["accuracy"] - t["accuracy"]
                         for r, t in zip(curve_rand, curve_top)]
            auc_gap = sum(gap_per_k) / len(gap_per_k)
            # paired one-sample CI: per-case (rand - top) correctness gaps vs 0
            per_case_gaps = []
            for t, r in zip(curve_top, curve_rand):
                per_case_gaps.append([r_ - t_ for t_, r_ in zip(
                    t["correct_vector"], r["correct_vector"])])
            flat_gaps = [g for per_k in per_case_gaps for g in per_k]
            gap_ci = paired_bootstrap_gap(
                flat_gaps, [0] * len(flat_gaps),
                n_boot=args.n_boot, seed=args.seed + 1)
        else:
            auc_gap, gap_ci = None, {"mean": None, "ci95": [None, None]}
        receipt["causal_curve"] = {
            "k_steps": k_steps,
            "loo_measured_edges": {f"{a}-{b}": round(importance[e], 4)
                                   for (a, b), e in
                                   ((e, e) for e in loo_edges)} if loo_edges else {},
            "curve_top_acc": [round(r["accuracy"], 4) for r in curve_top],
            "curve_rand_acc": [round(r["accuracy"], 4) for r in curve_rand],
            "auc_gap": (round(auc_gap, 4) if auc_gap is not None else None),
            "auc_gap_ci95": gap_ci["ci95"],
            "importance_note": (
                "LOO importance measured on fresh for the top-M edges by learned "
                "weight; deeper edges ranked by learned weight (documented "
                "deviation from full-LOO prereg reading — full LOO on |E| edges "
                "is |E|*n_fresh calls)"),
        }

        # ---- structure-performance correlation ----
        topo_points = [{"tag": f"ckpt_{c['after_case']}", "edges": set(map(tuple, c["edges"]))}
                       for c in checkpoints]
        topo_points.append({"tag": "final", "edges": set(map(tuple, e_learned))})
        topo_accs = {}
        for tp in topo_points:
            if tp["tag"] == "final":
                topo_accs[tp["tag"]] = acc_a
            else:
                res = eval_topology(answerer, args.answer_model, tp["edges"],
                                    fresh_cases, lessons, args.k_context,
                                    args.parallel, args.seed)
                topo_accs[tp["tag"]] = res["accuracy"]
        corr_points = []
        for i in range(len(topo_points)):
            for j in range(i + 1, len(topo_points)):
                ei, ej = topo_points[i]["edges"], topo_points[j]["edges"]
                edit = len(ei ^ ej)
                delta = abs(topo_accs[topo_points[i]["tag"]]
                            - topo_accs[topo_points[j]["tag"]])
                corr_points.append((edit, delta))
        rho = f2.spearman([p[0] for p in corr_points],
                          [p[1] for p in corr_points]) if len(corr_points) >= 2 else None
        rho_boot = bootstrap_spearman_ci(corr_points, n_boot=args.n_boot,
                                         seed=args.seed) if corr_points else {
                                             "ci95": [None, None]}
        receipt["structure_performance"] = {
            "checkpoint_accuracies": topo_accs,
            "points": corr_points,
            "spearman_rho": (round(rho, 4) if rho is not None else None),
            "rho_ci95": rho_boot["ci95"],
        }

        # ---- kill observations ----
        controls = {k: v for k, v in arms.items() if k != "A_learned"}
        best_control = max(controls, key=lambda k: controls[k]["fresh_accuracy"])
        control_gaps = {}
        for name, arm in controls.items():
            gap = paired_bootstrap_gap(arms["A_learned"]["correct_vector"],
                                       arm["correct_vector"],
                                       n_boot=args.n_boot, seed=args.seed)
            control_gaps[name] = {"a_minus_x": round(
                arms["A_learned"]["fresh_accuracy"] - arm["fresh_accuracy"], 4),
                "ci95": [round(x, 4) for x in gap["ci95"]]}
        k1 = any(arm["fresh_accuracy"] >= acc_a for arm in controls.values())
        k2 = (gap_ci["ci95"][0] is not None and gap_ci["ci95"][1] is not None
              and gap_ci["ci95"][0] <= 0 <= gap_ci["ci95"][1])
        k3 = (rho_boot["ci95"][0] is not None and rho_boot["ci95"][1] is not None
              and rho_boot["ci95"][0] <= 0 <= rho_boot["ci95"][1])
        receipt["kill_condition_observations"] = {
            "f4_k1_any_control_catches_a": k1,
            "f4_k2_auc_gap_ci_includes_0": k2,
            "f4_k3_rho_ci_includes_0": k3,
            "values": {
                "learned_minus_best_control": round(
                    acc_a - controls[best_control]["fresh_accuracy"], 4),
                "best_control": best_control,
                "control_gaps": control_gaps,
                "auc_gap": receipt["causal_curve"]["auc_gap"],
                "rho": receipt["structure_performance"]["spearman_rho"],
            },
            "note": "mechanical observation only; sealed judgment belongs to the gate",
        }
    except (F4Error, f2.BudgetExceeded) as err:
        aborted = str(err)
    except Exception as err:  # noqa: BLE001 - record failure honestly
        aborted = f"{type(err).__name__}: {err}"

    receipt["llm_budget"] = {
        "max_calls": args.max_calls, "used": budget.used,
        "answerer": {"backend": args.answer_backend, "url": args.answer_url,
                     "model": args.answer_model,
                     "misses": answerer.misses, "hits": answerer.hits,
                     "degraded_to_parallel": answerer.degraded_to_parallel},
        "total_logical": answerer.misses + answerer.hits,
    }
    receipt["aborted"] = aborted
    receipt["wall_clock_s"] = round(time.time() - t0, 1)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=1, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    summary = {
        "receipt": str(out_path), "aborted": aborted,
        "calls": receipt["llm_budget"], "wall_clock_s": receipt["wall_clock_s"],
        "leakage_binding": receipt.get("leakage", {}).get("binding_leakage"),
        "arms": {k: {kk: vv for kk, vv in v.items()
                     if kk in ("fresh_accuracy", "n_edges", "fresh_parse_failures")}
                 for k, v in receipt.get("arms", {}).items()},
        "causal_curve": receipt.get("causal_curve", {}).get("auc_gap"),
        "rho": receipt.get("structure_performance", {}).get("spearman_rho"),
        "kill": receipt.get("kill_condition_observations"),
    }
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    return 0 if aborted is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
