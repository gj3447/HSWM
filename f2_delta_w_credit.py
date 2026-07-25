"""F2 gate (result -> credit assignment -> deltaW learning) development harness.

PREREG (locked, read-only input): prom_search_hswm/evidence/
PREREG_f2_delta_w_credit_20260725.json (in the SYMPOSIUM/HSWM checkout).

DEVELOPMENT MODE ONLY. This script runs a small, unsealed harness-validation
measurement: n_dev=8, m=8 TMC permutations, L=6 lessons, n_fresh=12.  It emits
numbers, never a scientific claim.  Every receipt field is marked
mode="development".

Design (dev-scale instantiation of the prereg arms):
  environment   p1v3 policy-conflict cases (PhantomWiki, single-answer type6).
  worlds        6 source-class pairs; one typed policy lesson per world.
                worlds 0-3 lessons are correct; worlds 4-5 lessons are PLANTED
                INVERTED (anti-credit ground truth, prereg secondary
                discriminator "planted_ground_truth_testbed").
  V(S)          frozen answerer accuracy with lesson subset S rendered into
                memory_context (p1v2 prompt shape, exact-set-match scoring).
  credit        budget-capped TMC-Shapley phi_i over m seeded permutations.
  gate          Spearman rho(phi_i, measured LOO delta-V_i), prereg >= 0.2.
  arms          (a) credit-informed keep top-2 / delete bottom-2
                (b) same-size random edit (hswm_null_battery.random_edit_plan)
                (c) verbal-gradient LLM critic proposed deletes
                each measured on a fresh heldout cut disjoint from train/dev.

Splits (disjoint universes, p1v3 lineage): train=sparse_t200_fk1 (6 q),
dev=large_t200_fk3 (8 q), fresh=mid_t20_fk3 (12 q).  Single-answer type6
questions only (maximum_true_documents=1, same cut as p1v3_prepare).

Answerer freeze note: the sealed p1v4 answerer (Qwen3.6-35B-A3B-FP8 on the
dell vLLM host, receipts/p1v2_qwen35_deployment_20260724.json) is NOT served
on this machine.  Per task instruction this dev run freezes the local ollama
answerer (default qwen3:14b, http://127.0.0.1:11434/v1) instead; the deviation
is recorded in the receipt.  All LLM responses are disk-cached (.f2_cache/) so
reruns with identical config are cache hits.

Usage: .venv/bin/python f2_delta_w_credit.py [--smoke] [--n-dev 8] [--m-perms 8]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
# null battery lives in the sibling SYMPOSIUM/HSWM checkout (read-only import)
NULL_BATTERY_DIR = Path("/Users/lagyeongjun/CD/SYMPOSIUM/HSWM/prom_search_hswm")
sys.path.insert(0, str(NULL_BATTERY_DIR))

from hswm_weight_snapshot import canonical_sha256  # noqa: E402
from p1v2_l0_harness import render_answer_prompt  # noqa: E402
from p1v2_llm_answerer import P1V2_SYSTEM_PROMPT  # noqa: E402
from p1v2_typed_lesson import (  # noqa: E402
    LessonCompilePolicyV1,
    compile_typed_lesson,
    render_lesson_context,
    retrieve_lessons,
)
from p1v3_policy_environment import (  # noqa: E402
    build_policy_conflict_case,
    render_policy_training_transcript,
    verify_policy_oracle_admission,
)
from hswm_null_battery import (  # noqa: E402
    disjoint_audit,
    headroom_band_ok,
    random_edit_plan,
)

PREREG_PATH = NULL_BATTERY_DIR / "evidence" / "PREREG_f2_delta_w_credit_20260725.json"
UNIVERSE_ROOT = HERE / "_research" / "r3_replay" / "universes"
CACHE_DIR = HERE / ".f2_cache"
RECEIPT_PATH = HERE / "receipts" / "f2_delta_w_credit_dev_20260725.json"

# worlds: (trusted_class, distractor_class, lesson_orientation)
WORLDS = (
    ("RHO", "TAU", "correct"),
    ("SIGMA", "BETA", "correct"),
    ("GAMMA", "DELTA", "correct"),
    ("KAPPA", "ZETA", "correct"),
    ("OMEGA", "PSI", "planted_inverted"),
    ("ALPHA", "NU", "planted_inverted"),
)
SPLIT_UNIVERSES = {"train": "sparse_t200_fk1", "dev": "large_t200_fk3", "fresh": "mid_t20_fk3"}
TMC_SEED = "f2-tmc-20260725"
RANDOM_EDIT_SEED = "f2-random-edit-20260725"
SCOPE = {
    "all_terms": ["who is", "the person whose"],
    "any_terms": ["occupation", "hobby", "date of birth", "gender"],
    "excluded_terms": [],
}
HEADROOM_BAND = (0.3, 0.7)  # prereg common_chassis.headroom_band


class BudgetExceeded(RuntimeError):
    pass


class CriticParseError(RuntimeError):
    pass


# ---------------------------------------------------------------- cached LLM
class CachedChat:
    """Disk-cached native-ollama /api/chat caller; misses count against budget.

    Harness bug found in smoke run 1 (2026-07-25): the ollama 0.17.7
    OpenAI-compat /v1/chat/completions silently ignores every thinking-off
    switch (chat_template_kwargs.enable_thinking, "think": false, /no_think);
    qwen3 reasoning then consumed the whole num_predict budget, yielding
    finish_reason=length with empty content (all parse failures, acc 0.0).
    The native /api/chat endpoint honours "think": false, so this caller uses
    it exclusively.  Cached smoke-run entries are keyed on the old body shape
    and are never reused.
    """

    def __init__(self, endpoint: str, max_calls: int):
        self.endpoint = endpoint.rstrip("/")
        self.max_calls = max_calls
        self.misses = 0
        self.hits = 0
        CACHE_DIR.mkdir(exist_ok=True)

    def _cache_path(self, key: str) -> Path:
        return CACHE_DIR / f"{key}.json"

    def chat(self, *, model: str, system: str, user: str, seed: int,
             max_tokens: int, timeout: float = 240.0) -> dict:
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "think": False,
            "format": "json",
            "options": {
                "temperature": 0,
                "top_p": 1.0,
                "seed": seed,
                "num_predict": max_tokens,
            },
        }
        key = hashlib.sha256(json.dumps(
            {"api": "ollama-native-v1", "endpoint": self.endpoint, "body": body},
            sort_keys=True,
        ).encode()).hexdigest()
        path = self._cache_path(key)
        if path.exists():
            self.hits += 1
            return json.loads(path.read_text(encoding="utf-8"))["response_meta"] | {
                "cached": True}
        if self.misses >= self.max_calls:
            raise BudgetExceeded(f"LLM call budget {self.max_calls} exhausted")
        self.misses += 1
        req = urllib.request.Request(
            self.endpoint + "/api/chat",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        last_err = None
        for attempt in (1, 2):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    raw = json.loads(resp.read().decode("utf-8"))
                break
            except Exception as err:  # noqa: BLE001 - dev harness records class only
                last_err = err
                time.sleep(2 * attempt)
        else:
            raise RuntimeError(f"chat transport failed twice: {type(last_err).__name__}")
        meta = {
            "text": raw["message"]["content"],
            "finish_reason": raw.get("done_reason"),
            "response_model": raw.get("model"),
            "usage": {
                "prompt_tokens": raw.get("prompt_eval_count", 0),
                "completion_tokens": raw.get("eval_count", 0),
            },
            "request_sha256": key,
        }
        path.write_text(json.dumps({"response_meta": meta}, ensure_ascii=False),
                        encoding="utf-8")
        return meta | {"cached": False}


# ---------------------------------------------------------------- data cut
def load_single_answer_questions(universe: str) -> tuple[list[dict], list[dict]]:
    base = UNIVERSE_ROOT / universe
    articles = json.loads((base / "articles.json").read_text(encoding="utf-8"))
    questions = json.loads((base / "questions" / "type6.json").read_text(encoding="utf-8"))
    singles = [q for q in questions if len(q.get("answer", [])) == 1]
    return articles, singles


def build_case(question: dict, articles: list[dict], world_idx: int, split: str):
    trusted, distractor, _orientation = WORLDS[world_idx]
    case = build_policy_conflict_case(
        case_id=f"f2dev-{split}-{question['id'][:12]}",
        question=question["question"],
        articles=articles,
        trusted_class=trusted,
        distractor_class=distractor,
        maximum_true_documents=1,
    )
    if list(case.expected_answers) != sorted(question["answer"]):
        # environment gold must match the sealed type6 gold; skip otherwise
        return None
    return case


def build_split(split: str, quota: int) -> list:
    universe = SPLIT_UNIVERSES[split]
    articles, singles = load_single_answer_questions(universe)
    cases = []
    skipped = []
    for idx, question in enumerate(singles):
        if len(cases) >= quota:
            break
        world_idx = idx % len(WORLDS)
        try:
            case = build_case(question, articles, world_idx, split)
        except Exception as err:  # noqa: BLE001 - record and skip, never fudge
            skipped.append({"question_id": question["id"], "error": type(err).__name__})
            continue
        if case is None:
            skipped.append({"question_id": question["id"], "error": "gold_mismatch"})
            continue
        cases.append((case, world_idx, question))
    if len(cases) < quota:
        raise RuntimeError(f"{split}: only {len(cases)} usable cases (need {quota})")
    return cases, skipped, universe


# ---------------------------------------------------------------- lessons
def compile_world_lessons(train_cases) -> dict:
    """One typed policy lesson per world; worlds 4-5 are planted inverted."""
    lessons = {}
    meta = {}
    for world_idx, (trusted, distractor, orientation) in enumerate(WORLDS):
        case, _w, question = train_cases[world_idx]
        assert _w == world_idx
        episode_id = f"policy-training:{case.case_id}"
        transcript = render_policy_training_transcript(case)
        evidence_id = "policy-training-evidence:" + case.derivation_sha256
        if orientation == "correct":
            teach, ignore = trusted, distractor
        else:
            teach, ignore = distractor, trusted  # planted anti-credit
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
        if orientation == "correct":
            verify_policy_oracle_admission(
                lesson, trusted_class=trusted, distractor_class=distractor)
            admission = "oracle_admission_passed"
        lessons[lesson.lesson_id] = lesson
        meta[lesson.lesson_id] = {
            "world_idx": world_idx, "trusted_class": trusted,
            "distractor_class": distractor, "orientation": orientation,
            "admission": admission, "training_case_id": case.case_id,
            "training_transcript_sha256": canonical_sha256({"t": transcript}),
        }
    return lessons, meta


# ---------------------------------------------------------------- V(subset)
def memory_context(question: str, subset_ids: tuple[str, ...], lessons: dict) -> str:
    if not subset_ids:
        return ""
    subset = [lessons[i] for i in subset_ids]
    selection = retrieve_lessons(question, subset, top_k=len(subset))
    return render_lesson_context(selection, subset)


def normalized_set(values) -> set:
    return {" ".join(v.casefold().split()) for v in values if v.strip()}


def evaluate_subset(llm: CachedChat, model: str, subset_ids: tuple[str, ...],
                    cases, lessons: dict, parallel: int, seed: int) -> dict:
    """V(S): mean exact-set-match of the frozen answerer over `cases`."""
    def work(item):
        case, _world_idx, _q = item
        ctx = memory_context(case.question, subset_ids, lessons)
        user = render_answer_prompt(case.question, case.documents, ctx)
        meta = llm.chat(model=model, system=P1V2_SYSTEM_PROMPT, user=user,
                        seed=seed, max_tokens=256)
        correct = 0
        parse_ok = True
        try:
            if meta["finish_reason"] != "stop":
                raise ValueError("finish_reason")
            payload = json.loads(meta["text"])
            answers = payload["answers"]
            if not isinstance(answers, list):
                raise ValueError("answers")
            correct = int(normalized_set(answers) == normalized_set(case.expected_answers))
        except Exception:  # noqa: BLE001 - dev harness counts, never repairs
            parse_ok = False
        return {"case_id": case.case_id, "correct": correct, "parse_ok": parse_ok,
                "cached": meta["cached"]}

    with ThreadPoolExecutor(max_workers=parallel) as pool:
        rows = list(pool.map(work, cases))
    n = len(rows)
    return {
        "subset": sorted(subset_ids),
        "n_cases": n,
        "accuracy": sum(r["correct"] for r in rows) / n,
        "parse_failures": sum(1 for r in rows if not r["parse_ok"]),
        "rows": rows,
    }


# ---------------------------------------------------------------- stats
def _ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        mean_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = mean_rank
        i = j + 1
    return ranks


def spearman(a: list[float], b: list[float]):
    if len(a) != len(b) or len(a) < 2:
        return None
    if len(set(a)) < 2 or len(set(b)) < 2:
        return None
    ra, rb = _ranks(a), _ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra)
    vb = sum((y - mb) ** 2 for y in rb)
    if va == 0 or vb == 0:
        return None
    return cov / (va * vb) ** 0.5


# ---------------------------------------------------------------- arms
def run_critic(llm: CachedChat, critic_model: str, dev_eval_full, lessons: dict,
               lesson_meta: dict, seed: int) -> list[str]:
    """Verbal-gradient arm: one batched LLM critic call proposes 2 deletes."""
    lesson_lines = []
    for lid in sorted(lessons):
        lesson_lines.append(f"- {lid[:16]}: {lessons[lid].instruction}")
    case_lines = []
    for row in dev_eval_full["rows"]:
        case_lines.append(
            f"- case {row['case_id']}: correct={row['correct']} parse_ok={row['parse_ok']}")
    user = (
        "A frozen answerer answered policy-conflict questions with ALL of the typed "
        "memory lessons below in context. Per-case outcomes follow. Some lessons may "
        "help, some may harm. Choose exactly 2 lessons to DELETE to improve future "
        "accuracy on similar questions. Return strict JSON with keys \"delete\" "
        "(array of exactly 2 lesson id prefixes as shown) and \"rationale\" (short).\n\n"
        "LESSONS:\n" + "\n".join(lesson_lines) + "\n\nDEV OUTCOMES (full store):\n"
        + "\n".join(case_lines)
    )
    system = "You are a memory-store critic. Output only strict JSON."
    meta = llm.chat(model=critic_model, system=system, user=user,
                    seed=seed, max_tokens=1024, timeout=300.0)
    try:
        payload = json.loads(meta["text"])
        proposed = payload["delete"]
        if not isinstance(proposed, list) or len(proposed) != 2:
            raise CriticParseError("critic did not propose exactly 2 deletes")
        resolved = []
        for prefix in proposed:
            matches = [lid for lid in lessons if lid.startswith(str(prefix))]
            if len(matches) != 1:
                raise CriticParseError(f"critic prefix {prefix!r} matches {len(matches)}")
            resolved.append(matches[0])
        return resolved, {"critic_raw": payload, "critic_cached": meta["cached"]}
    except (json.JSONDecodeError, KeyError, CriticParseError) as err:
        raise CriticParseError(f"arm-c critic output unusable: {err}") from err


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-dev", type=int, default=8)
    ap.add_argument("--m-perms", type=int, default=8)
    ap.add_argument("--n-fresh", type=int, default=12)
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--max-subsets", type=int, default=44)
    ap.add_argument("--max-calls", type=int, default=400)
    ap.add_argument("--model", default="qwen3:14b")
    ap.add_argument("--critic-model", default="qwen3:14b")
    ap.add_argument("--endpoint", default="http://127.0.0.1:11434")
    ap.add_argument("--seed", type=int, default=20260725)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--out", default=str(RECEIPT_PATH))
    args = ap.parse_args()
    if args.smoke:
        args.n_dev, args.m_perms, args.n_fresh = 2, 1, 2

    t0 = time.time()
    receipt = {
        "schema_version": "hswm-f2-delta-w-credit-dev-receipt/v1",
        "mode": "development",
        "branch": "F2-delta-w-credit",
        "preregistration_file": str(PREREG_PATH),
        "preregistration_file_sha256": hashlib.sha256(
            PREREG_PATH.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "config": vars(args) | {"out": args.out},
        "answerer_freeze_note": (
            "Sealed p1v4 answerer (Qwen3.6-35B-A3B-FP8, dell vLLM 127.0.0.1:18002) "
            "is not served on this host; dev run freezes the local ollama model "
            f"{args.model} at {args.endpoint} per task instruction. Not comparable "
            "to sealed p1v4 numbers."),
        "honesty": "development harness validation; no scientific claim; n << 100",
    }
    llm = CachedChat(args.endpoint, args.max_calls)
    aborted = None
    try:
        # ---- splits ----
        train_cases, skipped_train, u_train = build_split("train", len(WORLDS))
        dev_cases, skipped_dev, u_dev = build_split("dev", args.n_dev)
        fresh_cases, skipped_fresh, u_fresh = build_split("fresh", args.n_fresh)
        receipt["splits"] = {
            "universes": {"train": u_train, "dev": u_dev, "fresh": u_fresh},
            "n_train": len(train_cases), "n_dev": len(dev_cases),
            "n_fresh": len(fresh_cases),
            "skipped": {"train": skipped_train, "dev": skipped_dev,
                        "fresh": skipped_fresh},
            "dev_case_worlds": [w for _c, w, _q in dev_cases],
            "fresh_case_worlds": [w for _c, w, _q in fresh_cases],
        }
        receipt["disjoint_audit"] = disjoint_audit(
            [q["question"] for _c, _w, q in train_cases],
            [q["question"] for _c, _w, q in dev_cases + fresh_cases])

        # ---- lessons ----
        lessons, lesson_meta = compile_world_lessons(train_cases)
        lesson_ids = tuple(sorted(lessons))
        receipt["lessons"] = {lid[:16]: lesson_meta[lid] for lid in lesson_ids}

        V_cache: dict[tuple[str, ...], dict] = {}

        def V(subset_ids, cases):
            key = tuple(sorted(subset_ids))
            if key not in V_cache:
                V_cache[key] = evaluate_subset(
                    llm, args.model, key, cases, lessons, args.parallel, args.seed)
                if len(V_cache) > args.max_subsets:
                    raise BudgetExceeded(
                        f"distinct subset cap {args.max_subsets} exceeded")
            return V_cache[key]

        # ---- base / headroom ----
        base_dev = V((), dev_cases)
        full_dev = V(lesson_ids, dev_cases)
        receipt["dev_base_accuracy"] = base_dev["accuracy"]
        receipt["dev_full_store_accuracy"] = full_dev["accuracy"]
        receipt["headroom_band"] = list(HEADROOM_BAND)
        receipt["headroom_band_ok"] = headroom_band_ok(
            base_dev["accuracy"], *HEADROOM_BAND)

        # ---- TMC-Shapley ----
        rng = random.Random(TMC_SEED)
        phi = {lid: [] for lid in lesson_ids}
        perms_run = 0
        for _ in range(args.m_perms):
            perm = list(lesson_ids)
            rng.shuffle(perm)
            prefix: tuple[str, ...] = ()
            prev = V(prefix, dev_cases)["accuracy"]
            for lid in perm:
                new = V(prefix + (lid,), dev_cases)["accuracy"]
                phi[lid].append(new - prev)
                prefix = prefix + (lid,)
                prev = new
            perms_run += 1
        phi_mean = {lid: sum(v) / len(v) for lid, v in phi.items()}

        # ---- LOO ----
        loo = {}
        v_full = full_dev["accuracy"]
        for lid in lesson_ids:
            rest = tuple(x for x in lesson_ids if x != lid)
            loo[lid] = v_full - V(rest, dev_cases)["accuracy"]

        rho = spearman([phi_mean[lid] for lid in lesson_ids],
                       [loo[lid] for lid in lesson_ids])
        receipt["credit"] = {
            "m_perms_run": perms_run,
            "distinct_subsets_evaluated": len(V_cache),
            "phi_tmc": {lid[:16]: round(phi_mean[lid], 4) for lid in lesson_ids},
            "loo_delta_v": {lid[:16]: round(loo[lid], 4) for lid in lesson_ids},
            "spearman_rho": (round(rho, 4) if rho is not None else None),
            "spearman_note": None if rho is not None else "undefined (constant vector)",
            "prereg_gate_rho_ge_0.2": (rho >= 0.2) if rho is not None else None,
        }

        # ---- arms on fresh ----
        ranked = sorted(lesson_ids, key=lambda lid: (-phi_mean[lid], lid))
        keep_top2 = tuple(ranked[:2])
        delete_credit = tuple(sorted(ranked[-2:]))
        store_a = tuple(lid for lid in lesson_ids if lid not in delete_credit)

        plan_b = random_edit_plan(list(lesson_ids), 0, 2, 0, RANDOM_EDIT_SEED)
        delete_random = tuple(sorted(plan_b.deletes))
        store_b = tuple(lid for lid in lesson_ids if lid not in delete_random)

        arms = {}
        for arm_id, store in (("a_credit_informed", store_a),
                              ("b_random_edit", store_b)):
            res = evaluate_subset(llm, args.model, store, fresh_cases, lessons,
                                  args.parallel, args.seed)
            arms[arm_id] = {"kept_lessons": [l[:16] for l in store],
                            "fresh_accuracy": res["accuracy"],
                            "fresh_parse_failures": res["parse_failures"]}
        arms["a_credit_informed"]["deleted"] = [l[:16] for l in delete_credit]
        arms["a_credit_informed"]["kept_top2"] = [l[:16] for l in keep_top2]
        arms["b_random_edit"]["deleted"] = [l[:16] for l in delete_random]

        try:
            delete_critic, critic_meta = run_critic(
                llm, args.critic_model, full_dev, lessons, lesson_meta, args.seed)
            store_c = tuple(lid for lid in lesson_ids if lid not in delete_critic)
            res = evaluate_subset(llm, args.model, store_c, fresh_cases, lessons,
                                  args.parallel, args.seed)
            arms["c_verbal_gradient"] = {
                "kept_lessons": [l[:16] for l in store_c],
                "deleted": [l[:16] for l in delete_critic],
                "fresh_accuracy": res["accuracy"],
                "fresh_parse_failures": res["parse_failures"],
                "critic": critic_meta,
            }
        except CriticParseError as err:
            arms["c_verbal_gradient"] = {"error": str(err)}

        receipt["arms"] = arms
        if "fresh_accuracy" in arms.get("a_credit_informed", {}) and \
                "fresh_accuracy" in arms.get("b_random_edit", {}):
            receipt["dev_measurements"] = {
                "credit_informed_minus_random":
                    arms["a_credit_informed"]["fresh_accuracy"]
                    - arms["b_random_edit"]["fresh_accuracy"],
                "note": "development-scale point estimate only; no CI, no claim",
            }
    except BudgetExceeded as err:
        aborted = str(err)
    except Exception as err:  # noqa: BLE001 - record failure honestly
        aborted = f"{type(err).__name__}: {err}"

    receipt["llm_budget"] = {
        "max_calls": args.max_calls, "misses": llm.misses, "hits": llm.hits,
        "total_logical": llm.misses + llm.hits,
    }
    receipt["aborted"] = aborted
    receipt["wall_clock_s"] = round(time.time() - t0, 1)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out = out.with_name(out.stem + f"_{int(t0)}" + out.suffix)
    out.write_text(json.dumps(receipt, indent=1, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(json.dumps({
        "receipt": str(out), "aborted": aborted,
        "calls": receipt["llm_budget"], "wall_clock_s": receipt["wall_clock_s"],
        "dev_base_accuracy": receipt.get("dev_base_accuracy"),
        "headroom_band_ok": receipt.get("headroom_band_ok"),
        "credit": receipt.get("credit"),
        "arms": {k: {kk: vv for kk, vv in v.items()
                     if kk in ("fresh_accuracy", "error", "deleted")}
                 for k, v in receipt.get("arms", {}).items()},
    }, indent=1, ensure_ascii=False))
    return 0 if aborted is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
