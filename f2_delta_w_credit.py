"""F2 gate (result -> credit assignment -> deltaW learning) harness, sealed-scale edition.

PREREG (locked, read-only input): prom_search_hswm/evidence/
PREREG_f2_delta_w_credit_20260725.json (in the SYMPOSIUM/HSWM checkout).

Receipts from this script are always mode="development" measurements; the
scientific judgment belongs to the HSWM_LOCAL_RECORD gate, never to this file.

Changes vs the 2026-07-25 dev edition (receipt ..._1784953230.json):

1. SPLIT DEDUP (lesson-phantomwiki-split-dedup-question-text-20260725):
   splits are built from a GLOBAL question pool deduplicated by normalized
   question text (attribute+value), so train/dev/fresh exact-text overlap is
   structurally 0 and then audited.  Root cause found on 2026-07-25: the three
   t200 universe dirs (sparse/large/dense, friendship_k 1/3/9) share identical
   articles and identical type6 question texts + answers (titles_sha equal) —
   they are ONE universe for this environment; only mid_t20_fk3 and
   small_t2_fk3 add new question texts.  The unique single-answer text pool is
   therefore 52, and a sealed n_dev=100 + n_fresh=100 cut CANNOT be filled
   from it: the run fails closed at preflight with pool stats (widen the pool
   with --max-answers, or generate fresh PhantomWiki universes with new base
   seeds via .venv_phantom + swipl and pass --universes-dir).

2. PLACEBO ARM (prereg f2_k2): hswm_null_battery.deranged_placebo_store maps
   every lesson instruction to an unrelated-domain text of comparable length
   (PLACEBO_POOL, no source-class content); the placebo store gets the same
   delete positions as arm (a).  kill observation: placebo_acc >= credit_acc.

3. Scale flags: --n-dev/--n-fresh/--m-shapley/--lessons/--seed/--parallel
   (sealed defaults 100/100/16/6/20260725/auto, parallel auto = 16 for vllm /
   8 for ollama, halving ladder to min 4 on 429/5xx/timeout), --max-answers,
   --universes-dir, --max-tmc-subsets, --loo-budget.  --smoke runs the full
   path at n6/m4/L6 within ~80 calls.

Environment: p1v3 policy-conflict cases (PhantomWiki type6).  Worlds: 6
source-class pairs, one typed policy lesson per world; worlds 0-3 correct,
worlds 4-5 PLANTED INVERTED (anti-credit ground truth).  V(S) = frozen
answerer exact-set-match accuracy with lesson subset S in memory_context
(p1v2 prompt shape).  Credit = budget-capped TMC-Shapley over seeded
permutations; gate = Spearman(phi, measured LOO delta-V) vs prereg 0.2.

Answerer backends (--answer-backend): "vllm" (default, user directive
2026-07-25) = OpenAI-compat /chat/completions at --answer-url (default dgx
vLLM 127.0.0.1:18000/v1) with chat_template_kwargs enable_thinking=false,
which this vLLM honours; "ollama" = native /api/chat (ollama's own /v1
compat path ignores every thinking-off switch on 0.17.7 — see dev receipt
f2_delta_w_credit_dev_20260725.json).  The verbal-gradient critic always
stays on ollama (--critic-url/--critic-model, default qwen3:14b) for
heterogeneous separation; scoring is gold exact-match, so no judge
circularity.  All responses are disk-cached in .f2_cache/ with
backend+endpoint+model in the key; identical config reruns are cache hits.
Sealed p1v4's answerer (Qwen3.6-35B-A3B-FP8, dell vLLM) is not served on
this host; qwen3.6-27b is the closest available Qwen3.6-family model.

Usage:
  .venv/bin/python f2_delta_w_credit.py --smoke
  .venv/bin/python f2_delta_w_credit.py --universes-dir _research/f2_sealed_universes
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
import urllib.error
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
from p1v2_type6_environment import parse_type6_question  # noqa: E402
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
    deranged_placebo_store,
    disjoint_audit,
    headroom_band_ok,
    random_edit_plan,
)

PREREG_PATH = NULL_BATTERY_DIR / "evidence" / "PREREG_f2_delta_w_credit_20260725.json"
DEFAULT_UNIVERSES_DIR = HERE / "_research" / "r3_replay" / "universes"
CACHE_DIR = HERE / ".f2_cache"
RECEIPT_DIR = HERE / "receipts"

# worlds: (trusted_class, distractor_class, lesson_orientation)
WORLDS = (
    ("RHO", "TAU", "correct"),
    ("SIGMA", "BETA", "correct"),
    ("GAMMA", "DELTA", "correct"),
    ("KAPPA", "ZETA", "correct"),
    ("OMEGA", "PSI", "planted_inverted"),
    ("ALPHA", "NU", "planted_inverted"),
)
SCOPE = {
    "all_terms": ["who is", "the person whose"],
    "any_terms": ["occupation", "hobby", "date of birth", "gender"],
    "excluded_terms": [],
}
HEADROOM_BAND = (0.3, 0.7)  # prereg common_chassis.headroom_band
SATURATION_BASE = 5 / 6     # prereg kill f2_k3

# placebo content pool: unrelated domain, instruction-shaped, comparable
# length to the real policy instructions, no source-class or QA vocabulary.
PLACEBO_POOL = (
    "When brewing green tea, steep the leaves for two minutes in water below "
    "eighty degrees and discard the first rinse to keep the flavor clear.",
    "Before repotting a fern, loosen the outer roots gently and choose a pot "
    "only slightly wider than the one it grew in before.",
    "To keep a bicycle chain quiet, wipe it dry after wet rides and apply one "
    "small drop of lubricant to each link, then spin the pedals slowly.",
    "When tuning a guitar by ear, match the fifth fret of each string to the "
    "open string below it, except for the third string which uses the fourth.",
    "For a crisp bread crust, preheat the oven completely and place a shallow "
    "tray of water on the lower rack during the first half of baking.",
    "When sketching a portrait, begin with the distance between the eyes and "
    "compare every other measurement against that single unit repeatedly.",
)


class BudgetExceeded(RuntimeError):
    pass


class PoolShortfall(RuntimeError):
    pass


class CriticParseError(RuntimeError):
    pass


# ---------------------------------------------------------------- cached LLM
class Budget:
    """Shared LLM miss budget across all backends (answerer + critic)."""

    def __init__(self, max_calls: int):
        self.max_calls = max_calls
        self.used = 0

    def take(self) -> None:
        if self.used >= self.max_calls:
            raise BudgetExceeded(f"LLM call budget {self.max_calls} exhausted")
        self.used += 1


def _cache_read(path: Path) -> dict | None:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["response_meta"] | {
            "cached": True}
    return None


def _cache_write(path: Path, meta: dict) -> None:
    path.write_text(json.dumps({"response_meta": meta}, ensure_ascii=False),
                    encoding="utf-8")


class CachedChat:
    """Disk-cached native-ollama /api/chat caller (used for the critic).

    ollama 0.17.7's OpenAI-compat /v1/chat/completions silently ignores every
    thinking-off switch (chat_template_kwargs.enable_thinking, "think": false,
    /no_think); qwen3 reasoning then consumed the whole num_predict budget
    (finish=length, empty content).  Native /api/chat honours "think": false.
    """

    backend_name = "ollama-native-v1"

    def __init__(self, endpoint: str, budget: Budget):
        self.endpoint = endpoint.rstrip("/")
        self.budget = budget
        self.misses = 0
        self.hits = 0
        self.last_http_status: int | None = None
        self.last_error_kind: str | None = None
        self.degraded_to_parallel: int | None = None
        CACHE_DIR.mkdir(exist_ok=True)

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
            {"backend": self.backend_name, "endpoint": self.endpoint,
             "model": model, "body": body},
            sort_keys=True,
        ).encode()).hexdigest()
        path = CACHE_DIR / f"{key}.json"
        cached = _cache_read(path)
        if cached is not None:
            self.hits += 1
            return cached
        self.budget.take()
        self.misses += 1
        req = urllib.request.Request(
            self.endpoint + "/api/chat",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        raw = _transport_with_backoff(req, timeout, self)
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
        _cache_write(path, meta)
        return meta | {"cached": False}


class CachedOpenAIChat:
    """Disk-cached OpenAI-compat /chat/completions caller (vLLM answerer).

    vLLM honours chat_template_kwargs {"enable_thinking": false} (verified
    2026-07-25: content returned, reasoning_content empty, finish=stop) —
    unlike ollama's /v1 path, which ignores every thinking-off switch.
    Retries 429/5xx/timeouts with exponential backoff and records the last
    status for the parallel auto-degrade ladder."""

    backend_name = "openai-compat-v1"

    def __init__(self, endpoint: str, budget: Budget):
        self.endpoint = endpoint.rstrip("/")
        self.budget = budget
        self.misses = 0
        self.hits = 0
        self.last_http_status: int | None = None
        self.last_error_kind: str | None = None
        self.degraded_to_parallel: int | None = None
        CACHE_DIR.mkdir(exist_ok=True)

    def chat(self, *, model: str, system: str, user: str, seed: int,
             max_tokens: int, timeout: float = 240.0) -> dict:
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "top_p": 1.0,
            "seed": seed,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "chat_template_kwargs": {"enable_thinking": False},
        }
        key = hashlib.sha256(json.dumps(
            {"backend": self.backend_name, "endpoint": self.endpoint,
             "model": model, "body": body},
            sort_keys=True,
        ).encode()).hexdigest()
        path = CACHE_DIR / f"{key}.json"
        cached = _cache_read(path)
        if cached is not None:
            self.hits += 1
            return cached
        self.budget.take()
        self.misses += 1
        req = urllib.request.Request(
            self.endpoint + "/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        raw = _transport_with_backoff(req, timeout, self)
        try:
            choice = raw["choices"][0]
            text = choice["message"]["content"]
            finish_reason = choice.get("finish_reason")
            response_model = raw.get("model")
            usage = raw.get("usage") or {}
        except (KeyError, IndexError, TypeError, AttributeError) as error:
            raise RuntimeError("OpenAI response schema mismatch") from error
        meta = {
            "text": text,
            "finish_reason": finish_reason,
            "response_model": response_model,
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
            },
            "request_sha256": key,
        }
        _cache_write(path, meta)
        return meta | {"cached": False}


def _transport_with_backoff(req, timeout: float, backend) -> dict:
    """POST with exponential backoff on 429/5xx and transient errors."""
    last_err = None
    for attempt in (1, 2, 3, 4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            backend.last_http_status = err.code
            backend.last_error_kind = "http"
            last_err = err
            time.sleep(min(2 ** attempt, 16))
        except (TimeoutError, ConnectionError, OSError) as err:
            backend.last_error_kind = "timeout"
            last_err = err
            time.sleep(min(2 ** attempt, 16))
        except Exception as err:  # noqa: BLE001 - record class only
            backend.last_error_kind = type(err).__name__
            last_err = err
            time.sleep(min(2 ** attempt, 16))
    raise RuntimeError(f"chat transport failed 4x: {type(last_err).__name__}")


# ------------------------------------------------- question pool and splits
def _norm_text(text: str) -> str:
    return " ".join(text.casefold().split())


def load_question_pool(universes_dir: Path, max_answers: int) -> tuple[list[dict], dict]:
    """All type6 questions with 1..max_answers answers, deduped by normalized
    question text (first occurrence wins), canonically ordered by text sha."""
    pool: dict[str, dict] = {}
    per_universe_raw: dict[str, int] = {}
    for udir in sorted(p for p in universes_dir.iterdir() if p.is_dir()):
        qpath = udir / "questions" / "type6.json"
        apath = udir / "articles.json"
        if not qpath.exists() or not apath.exists():
            continue
        questions = json.loads(qpath.read_text(encoding="utf-8"))
        kept = 0
        for question in questions:
            n_answers = len(question.get("answer", []))
            if not (1 <= n_answers <= max_answers):
                continue
            kept += 1
            key = _norm_text(question["question"])
            if key not in pool:
                pool[key] = {"question": question, "universe": udir.name}
        per_universe_raw[udir.name] = kept
    ordered = sorted(pool.items(), key=lambda kv: hashlib.sha256(
        kv[0].encode("utf-8")).hexdigest())
    stats = {
        "universes_dir": str(universes_dir),
        "max_answers": max_answers,
        "unique_question_texts": len(pool),
        "per_universe_raw_counts": per_universe_raw,
        "dedup_note": (
            "t200 dirs (sparse/large/dense) share identical articles and type6 "
            "texts+answers (verified 2026-07-25, titles_sha equal); dedup by "
            "normalized question text collapses them to one contributor."),
    }
    return [item for _key, item in ordered], stats


class _ArticleCache:
    def __init__(self, universes_dir: Path):
        self.universes_dir = universes_dir
        self._cache: dict[str, list[dict]] = {}

    def articles(self, universe: str) -> list[dict]:
        if universe not in self._cache:
            self._cache[universe] = json.loads(
                (self.universes_dir / universe / "articles.json").read_text(
                    encoding="utf-8"))
        return self._cache[universe]


def build_splits(pool: list[dict], article_cache: _ArticleCache, *,
                 n_lessons: int, n_dev: int, n_fresh: int,
                 max_answers: int) -> dict:
    """Fill train/dev/fresh from the deduped pool, skipping unbuildable texts.

    Global text dedup upstream makes cross-split exact overlap structurally 0;
    the receipt still audits it.  Fail-closed (PoolShortfall) with stats when
    the pool cannot fill the quotas.
    """
    quotas = {"train": n_lessons, "dev": n_dev, "fresh": n_fresh}
    splits: dict[str, list] = {name: [] for name in quotas}
    skipped: dict[str, list] = {name: [] for name in quotas}
    cursor = 0
    for name, quota in quotas.items():
        while len(splits[name]) < quota and cursor < len(pool):
            entry = pool[cursor]
            cursor += 1
            world_idx = len(splits[name]) % n_lessons
            trusted, distractor, _orientation = WORLDS[world_idx]
            question = entry["question"]
            try:
                case = build_policy_conflict_case(
                    case_id=f"f2seal-{name}-{question['id'][:12]}",
                    question=question["question"],
                    articles=article_cache.articles(entry["universe"]),
                    trusted_class=trusted,
                    distractor_class=distractor,
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
            splits[name].append((case, world_idx, question, entry["universe"]))
        if len(splits[name]) < quota:
            raise PoolShortfall(
                f"split '{name}' filled {len(splits[name])}/{quota} from "
                f"{len(pool)} unique texts (max_answers={max_answers}); widen "
                "--max-answers or add universes via --universes-dir")
    return {"splits": splits, "skipped": skipped}


# ---------------------------------------------------------------- lessons
def compile_world_lessons(train_cases, n_lessons: int) -> tuple[dict, dict]:
    """One typed policy lesson per world; worlds 4-5 are planted inverted."""
    lessons: dict[str, object] = {}
    meta: dict[str, dict] = {}
    for world_idx in range(n_lessons):
        trusted, distractor, orientation = WORLDS[world_idx]
        case, w, question, universe = train_cases[world_idx]
        assert w == world_idx
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
            "training_universe": universe,
            "training_transcript_sha256": canonical_sha256({"t": transcript}),
        }
    return lessons, meta


def build_placebo_lessons(lessons: dict, seed: str) -> tuple[dict, dict]:
    """Deranged placebo store (prereg f2_k2): same lesson schema/token shape,
    unrelated-domain content, one placebo per real lesson, no reuse."""
    store = {lid: lessons[lid].instruction for lid in lessons}
    deranged = deranged_placebo_store(store, list(PLACEBO_POOL), seed)
    placebo: dict[str, object] = {}
    mapping: dict[str, str] = {}
    for lid, text in deranged.items():
        orig = lessons[lid]
        recorded = {
            "schema_version": "hswm-p1v2-operational-verdict/v1",
            "source_episode_ids": list(orig.source_episode_ids),
            "evidence_ids": list(orig.evidence_ids),
            "verdict_type": orig.verdict_type,
            "scope_predicate": orig.scope_predicate.canonical(),
            "instruction": text,
            "polarity": orig.polarity,
            "confidence": orig.confidence,
            "supersedes": [],
        }
        placebo_lesson = compile_typed_lesson(recorded, LessonCompilePolicyV1(
            allowed_episode_ids=tuple(orig.source_episode_ids),
            allowed_evidence_ids=tuple(orig.evidence_ids),
        ))
        placebo[placebo_lesson.lesson_id] = placebo_lesson
        mapping[lid] = placebo_lesson.lesson_id
    return placebo, mapping


# ---------------------------------------------------------------- V(subset)
def memory_context(question: str, subset_ids: tuple[str, ...], lessons: dict) -> str:
    if not subset_ids:
        return ""
    subset = [lessons[i] for i in subset_ids]
    selection = retrieve_lessons(question, subset, top_k=len(subset))
    return render_lesson_context(selection, subset)


def normalized_set(values) -> set:
    return {" ".join(v.casefold().split()) for v in values if v.strip()}


def evaluate_subset(llm, model: str, subset_ids: tuple[str, ...],
                    cases, lessons: dict, parallel: int, seed: int) -> dict:
    """V(S): mean exact-set-match of the frozen answerer over `cases`.

    Auto-degrade ladder: on transport failure with 429/5xx/timeout, halve the
    worker count (min 4) and retry the whole subset once (completed calls are
    cache hits); the degraded value sticks for later subsets."""

    def work(item):
        case, _world_idx, _q, _universe = item
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

    if llm.degraded_to_parallel is not None:
        parallel = min(parallel, llm.degraded_to_parallel)
    try:
        with ThreadPoolExecutor(max_workers=parallel) as pool:
            rows = list(pool.map(work, cases))
        effective_parallel = parallel
    except RuntimeError:
        retryable = (llm.last_error_kind == "timeout"
                     or (llm.last_http_status or 0) == 429
                     or (llm.last_http_status or 0) >= 500)
        if parallel > 4 and retryable:
            degraded = max(4, parallel // 2)
            llm.degraded_to_parallel = degraded
            with ThreadPoolExecutor(max_workers=degraded) as pool:
                rows = list(pool.map(work, cases))
            effective_parallel = degraded
        else:
            raise
    n = len(rows)
    return {
        "subset": sorted(subset_ids),
        "n_cases": n,
        "accuracy": sum(r["correct"] for r in rows) / n,
        "parse_failures": sum(1 for r in rows if not r["parse_ok"]),
        "parallel_effective": effective_parallel,
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
               seed: int) -> tuple[list[str], dict]:
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


def leakage_report(train_cases, dev_cases, fresh_cases) -> dict:
    """Binding check = exact question text + attribute-value overlap (must be
    0, structurally guaranteed by the deduped pool).  The raw-text Jaccard
    audit is recorded too, annotated as a type6-template artifact source."""
    def texts(cases):
        return [q["question"] for _c, _w, q, _u in cases]

    def values(cases):
        out = []
        for _c, _w, q, _u in cases:
            try:
                parsed = parse_type6_question(q["question"])
                out.append(f"{parsed.attribute}|{parsed.value}")
            except Exception:  # noqa: BLE001
                out.append(q["question"])
        return out

    t, d, f = texts(train_cases), texts(dev_cases), texts(fresh_cases)
    exact = {
        "train_dev": sorted(set(t) & set(d)),
        "train_fresh": sorted(set(t) & set(f)),
        "dev_fresh": sorted(set(d) & set(f)),
    }
    tv, dv, fv = values(train_cases), values(dev_cases), values(fresh_cases)
    exact_values = {
        "train_dev": sorted(set(tv) & set(dv)),
        "train_fresh": sorted(set(tv) & set(fv)),
        "dev_fresh": sorted(set(dv) & set(fv)),
    }
    binding = (
        sum(len(v) for v in exact.values())
        + sum(len(v) for v in exact_values.values()))
    raw_audit = disjoint_audit(t, d + f)
    value_audit = disjoint_audit(tv, dv + fv)
    return {
        "exact_question_text_overlap": exact,
        "exact_attribute_value_overlap": exact_values,
        "binding_leakage": binding,
        "binding_verdict": "CLEAN" if binding == 0 else "VOID",
        "audit_on_raw_question_texts": raw_audit,
        "audit_on_attribute_values": value_audit,
        "template_artifact_note": (
            "type6 questions share the 'Who is the person whose <attr> is' "
            "template (7/9 tokens), so raw-text token-Jaccard near-dups are "
            "expected artifacts; the binding criterion is exact question text "
            "and attribute-value overlap, both structurally 0 after pool dedup."),
    }


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-dev", type=int, default=100)
    ap.add_argument("--n-fresh", type=int, default=100)
    ap.add_argument("--m-shapley", "--m-perms", dest="m_shapley", type=int, default=16)
    ap.add_argument("--lessons", type=int, default=6)
    ap.add_argument("--seed", type=int, default=20260725)
    ap.add_argument("--parallel", type=int, default=0,
                    help="worker count; 0 = auto (16 for vllm, 8 for ollama)")
    ap.add_argument("--max-answers", type=int, default=1)
    ap.add_argument("--max-calls", type=int, default=8000)
    ap.add_argument("--max-subsets", type=int, default=0,
                    help="safety cap on distinct V-subsets (0 = unlimited)")
    ap.add_argument("--max-tmc-subsets", type=int, default=0,
                    help="truncate TMC after this many distinct subsets (0 = unlimited)")
    ap.add_argument("--loo-budget", type=int, default=0,
                    help="max uncached LOO subsets (0 = unlimited)")
    ap.add_argument("--universes-dir", type=Path, default=DEFAULT_UNIVERSES_DIR)
    ap.add_argument("--answer-backend", choices=("ollama", "vllm"), default="vllm")
    ap.add_argument("--answer-url", default="http://127.0.0.1:18000/v1")
    ap.add_argument("--answer-model", default="qwen3.6-27b")
    ap.add_argument("--critic-url", default="http://127.0.0.1:11434")
    ap.add_argument("--critic-model", default="qwen3:14b")
    ap.add_argument("--smoke", action="store_true",
                    help="path-validation preset: n6/f6/m4/L6 within ~80 calls")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    if args.smoke:
        args.n_dev = 6
        args.n_fresh = 6
        args.m_shapley = 4
        args.lessons = 6
        args.max_tmc_subsets = 5
        args.loo_budget = 2
        args.max_calls = 80
    if not (2 <= args.lessons <= len(WORLDS)):
        raise SystemExit(f"--lessons must be in [2, {len(WORLDS)}]")
    if args.parallel <= 0:
        args.parallel = 16 if args.answer_backend == "vllm" else 8
    t0 = time.time()
    ts = int(t0)
    if args.out:
        out_path = Path(args.out)
    else:
        tag = "smoke" if args.smoke else "sealed"
        out_path = RECEIPT_DIR / f"f2_delta_w_credit_{tag}_{ts}.json"

    budget = Budget(args.max_calls)
    if args.answer_backend == "vllm":
        answerer = CachedOpenAIChat(args.answer_url, budget)
        thinking_note = (
            'vLLM OpenAI-compat chat_template_kwargs {"enable_thinking": false} '
            "(verified honoured on this endpoint 2026-07-25: content returned, "
            "reasoning_content empty, finish=stop).")
    else:
        answerer = CachedChat(args.answer_url, budget)
        thinking_note = (
            "ollama native /api/chat think=false (ollama's /v1 compat path "
            "ignores every thinking-off switch on 0.17.7).")
    critic = CachedChat(args.critic_url, budget)
    receipt = {
        "schema_version": "hswm-f2-delta-w-credit-receipt/v2",
        "mode": "development",
        "branch": "F2-delta-w-credit",
        "smoke": bool(args.smoke),
        "preregistration_file": str(PREREG_PATH),
        "preregistration_file_sha256": hashlib.sha256(
            PREREG_PATH.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "config": vars(args) | {"out": str(out_path),
                                "universes_dir": str(args.universes_dir)},
        "answerer_freeze": {
            "backend": args.answer_backend,
            "url": args.answer_url,
            "model": args.answer_model,
            "lineage_note": (
                "Sealed p1v4 answerer was Qwen/Qwen3.6-35B-A3B-FP8 (dell vLLM "
                "127.0.0.1:18002, receipts/p1v2_qwen35_deployment_20260724.json), "
                "not served on this host; the frozen answerer here is the closest "
                "available model in the same Qwen3.6 family on the dgx vLLM "
                "endpoint. User directive 2026-07-25: vLLM is the intended "
                "answerer backend."),
            "thinking_off": thinking_note,
            "judge_role_separation": (
                "Scoring is gold exact-set-match (no LLM judge), so sharing the "
                "vLLM endpoint introduces no judging circularity. The "
                "verbal-gradient critic is kept on a separate backend/model: "
                f"ollama {args.critic_model} at {args.critic_url}."),
        },
        "honesty": "grounded measurement only; no scientific claim; judgment is the gate's",
    }
    aborted = None
    try:
        # ---- deduped question pool -> splits ----
        pool, pool_stats = load_question_pool(args.universes_dir, args.max_answers)
        receipt["question_pool"] = pool_stats
        article_cache = _ArticleCache(args.universes_dir)
        built = build_splits(pool, article_cache,
                             n_lessons=args.lessons, n_dev=args.n_dev,
                             n_fresh=args.n_fresh, max_answers=args.max_answers)
        train_cases = built["splits"]["train"]
        dev_cases = built["splits"]["dev"]
        fresh_cases = built["splits"]["fresh"]
        receipt["splits"] = {
            "n_train": len(train_cases), "n_dev": len(dev_cases),
            "n_fresh": len(fresh_cases),
            "skipped": built["skipped"],
            "split_universes": {
                name: sorted({u for _c, _w, _q, u in built["splits"][name]})
                for name in ("train", "dev", "fresh")},
            "dev_case_worlds": [w for _c, w, _q, _u in dev_cases],
            "fresh_case_worlds": [w for _c, w, _q, _u in fresh_cases],
        }
        receipt["leakage"] = leakage_report(train_cases, dev_cases, fresh_cases)

        # ---- lessons + placebo store ----
        lessons, lesson_meta = compile_world_lessons(train_cases, args.lessons)
        lesson_ids = tuple(sorted(lessons))
        receipt["lessons"] = {lid[:16]: lesson_meta[lid] for lid in lesson_ids}
        placebo_seed = f"f2-placebo-{args.seed}"
        placebo_lessons, placebo_map = build_placebo_lessons(lessons, placebo_seed)
        receipt["placebo_store"] = {
            "seed": placebo_seed,
            "content_pool": list(PLACEBO_POOL),
            "content_pool_sha256": canonical_sha256({"pool": list(PLACEBO_POOL)}),
            "lesson_id_map": {k[:16]: v[:16] for k, v in placebo_map.items()},
        }

        V_cache: dict[tuple[str, ...], dict] = {}

        def V(subset_ids, cases):
            key = tuple(sorted(subset_ids))
            if key not in V_cache:
                if args.max_subsets and len(V_cache) >= args.max_subsets:
                    raise BudgetExceeded(
                        f"distinct subset cap {args.max_subsets} exceeded")
                V_cache[key] = evaluate_subset(
                    answerer, args.answer_model, key, cases, lessons,
                    args.parallel, args.seed)
            return V_cache[key]

        # ---- base / headroom ----
        base_dev = V((), dev_cases)
        full_dev = V(lesson_ids, dev_cases)
        receipt["dev_base_accuracy"] = base_dev["accuracy"]
        receipt["dev_full_store_accuracy"] = full_dev["accuracy"]
        receipt["headroom_band"] = list(HEADROOM_BAND)
        receipt["headroom_band_ok"] = headroom_band_ok(
            base_dev["accuracy"], *HEADROOM_BAND)

        # ---- budget-capped TMC-Shapley ----
        tmc_seed = f"f2-tmc-{args.seed}"
        rng = random.Random(tmc_seed)
        phi = {lid: [] for lid in lesson_ids}
        perms_run = 0
        tmc_truncated = False
        tmc_subsets_at_start = len(V_cache)
        for _ in range(args.m_shapley):
            if (args.max_tmc_subsets
                    and len(V_cache) - tmc_subsets_at_start + 2 >= args.max_tmc_subsets):
                tmc_truncated = True
                break
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
        phi_mean = {lid: (sum(v) / len(v) if v else None) for lid, v in phi.items()}

        # ---- measured LOO delta-V (budget-capped) ----
        loo: dict[str, float | None] = {}
        loo_extras_used = 0
        v_full = full_dev["accuracy"]
        for lid in lesson_ids:
            rest = tuple(x for x in lesson_ids if x != lid)
            if rest in V_cache:
                loo[lid] = v_full - V_cache[rest]["accuracy"]
            elif args.loo_budget == 0 or loo_extras_used < args.loo_budget:
                loo_extras_used += 1
                loo[lid] = v_full - V(rest, dev_cases)["accuracy"]
            else:
                loo[lid] = None
        paired = [lid for lid in lesson_ids
                  if phi_mean[lid] is not None and loo[lid] is not None]
        rho = spearman([phi_mean[lid] for lid in paired],
                       [loo[lid] for lid in paired])
        receipt["credit"] = {
            "tmc_seed": tmc_seed,
            "m_perms_run": perms_run,
            "tmc_truncated": tmc_truncated,
            "distinct_subsets_evaluated": len(V_cache),
            "phi_tmc": {lid[:16]: (round(phi_mean[lid], 4)
                                  if phi_mean[lid] is not None else None)
                        for lid in lesson_ids},
            "loo_delta_v": {lid[:16]: (round(loo[lid], 4)
                                      if loo[lid] is not None else None)
                            for lid in lesson_ids},
            "loo_budget": args.loo_budget,
            "spearman_pairs": len(paired),
            "spearman_rho": (round(rho, 4) if rho is not None else None),
            "spearman_note": None if rho is not None else "undefined (constant/insufficient pairs)",
            "prereg_gate_rho_ge_0.2": (rho >= 0.2) if rho is not None else None,
        }

        # ---- arms on fresh ----
        ranked = sorted(lesson_ids,
                        key=lambda lid: (-(phi_mean[lid] or 0.0), lid))
        keep_top2 = tuple(ranked[:2])
        delete_credit = tuple(sorted(ranked[-2:]))
        store_a = tuple(lid for lid in lesson_ids if lid not in delete_credit)

        plan_b = random_edit_plan(list(lesson_ids), 0, 2, 0,
                                  f"f2-random-edit-{args.seed}")
        delete_random = tuple(sorted(plan_b.deletes))
        store_b = tuple(lid for lid in lesson_ids if lid not in delete_random)

        arms: dict[str, dict] = {}
        for arm_id, store in (("a_credit_informed", store_a),
                              ("b_random_edit", store_b)):
            res = evaluate_subset(answerer, args.answer_model, store, fresh_cases,
                                  lessons, args.parallel, args.seed)
            arms[arm_id] = {"kept_lessons": [l[:16] for l in store],
                            "fresh_accuracy": res["accuracy"],
                            "fresh_parse_failures": res["parse_failures"]}
        arms["a_credit_informed"]["deleted"] = [l[:16] for l in delete_credit]
        arms["a_credit_informed"]["kept_top2"] = [l[:16] for l in keep_top2]
        arms["b_random_edit"]["deleted"] = [l[:16] for l in delete_random]

        try:
            delete_critic, critic_meta = run_critic(
                critic, args.critic_model, full_dev, lessons, args.seed)
            store_c = tuple(lid for lid in lesson_ids if lid not in delete_critic)
            res = evaluate_subset(answerer, args.answer_model, store_c, fresh_cases,
                                  lessons, args.parallel, args.seed)
            arms["c_verbal_gradient"] = {
                "kept_lessons": [l[:16] for l in store_c],
                "deleted": [l[:16] for l in delete_critic],
                "fresh_accuracy": res["accuracy"],
                "fresh_parse_failures": res["parse_failures"],
                "critic": critic_meta,
            }
        except CriticParseError as err:
            arms["c_verbal_gradient"] = {"error": str(err)}

        # arm (d): deranged placebo store, same delete positions as arm (a)
        delete_placebo = {placebo_map[lid] for lid in delete_credit}
        store_d = tuple(lid for lid in sorted(placebo_lessons)
                        if lid not in delete_placebo)
        res_d = evaluate_subset(answerer, args.answer_model, store_d, fresh_cases,
                                placebo_lessons, args.parallel, args.seed)
        arms["d_deranged_placebo"] = {
            "kept_lessons": [l[:16] for l in store_d],
            "deleted": sorted(l[:16] for l in delete_placebo),
            "fresh_accuracy": res_d["accuracy"],
            "fresh_parse_failures": res_d["parse_failures"],
            "note": "same schema/token shape as arm (a), unrelated content; "
                    "fresh accuracy >= arm (a) triggers prereg kill f2_k2",
        }
        receipt["arms"] = arms

        acc_a = arms["a_credit_informed"]["fresh_accuracy"]
        acc_b = arms["b_random_edit"]["fresh_accuracy"]
        acc_d = arms["d_deranged_placebo"]["fresh_accuracy"]
        receipt["kill_condition_observations"] = {
            "f2_k1_credit_informed_minus_random_le_0": (acc_a - acc_b) <= 0,
            "f2_k2_placebo_ge_credit": acc_d >= acc_a,
            "f2_k3_saturation_base_ge_5_6": base_dev["accuracy"] >= SATURATION_BASE,
            "values": {
                "credit_informed": acc_a, "random_edit": acc_b,
                "verbal_gradient": arms["c_verbal_gradient"].get("fresh_accuracy"),
                "deranged_placebo": acc_d, "dev_base": base_dev["accuracy"],
            },
            "note": "mechanical observation only; sealed judgment belongs to the gate",
        }
    except (BudgetExceeded, PoolShortfall) as err:
        aborted = str(err)
    except Exception as err:  # noqa: BLE001 - record failure honestly
        aborted = f"{type(err).__name__}: {err}"

    receipt["llm_budget"] = {
        "max_calls": args.max_calls,
        "used": budget.used,
        "answerer": {
            "backend": args.answer_backend, "url": args.answer_url,
            "model": args.answer_model,
            "misses": answerer.misses, "hits": answerer.hits,
            "last_http_status": answerer.last_http_status,
            "last_error_kind": answerer.last_error_kind,
            "degraded_to_parallel": answerer.degraded_to_parallel,
        },
        "critic": {
            "backend": "ollama", "url": args.critic_url, "model": args.critic_model,
            "misses": critic.misses, "hits": critic.hits,
        },
        "total_logical": answerer.misses + answerer.hits + critic.misses + critic.hits,
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
        "dev_base_accuracy": receipt.get("dev_base_accuracy"),
        "headroom_band_ok": receipt.get("headroom_band_ok"),
        "credit": receipt.get("credit"),
        "kill": receipt.get("kill_condition_observations"),
        "arms": {k: {kk: vv for kk, vv in v.items()
                     if kk in ("fresh_accuracy", "error", "deleted")}
                 for k, v in receipt.get("arms", {}).items()},
    }, indent=1, ensure_ascii=False))
    return 0 if aborted is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
