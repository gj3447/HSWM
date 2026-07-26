"""F3v2 arms harness (slice 2) — 6-arm transfer experiment driver, dev smoke.

PREREG (draft, sha-pinned in the receipt):
  /Users/lagyeongjun/CD/SYMPOSIUM/HSWM/PREREG_F3V2_HARDER_TRANSFER_2026-07-26.md §3-5.

Arms (prereg §3):
  (a) a_no_memory    receiver alone (floor)
  (b) b_naive_donor  donor raw typed lessons as-is (null reproduction expected)
  (c) c_abstracted   Insight-style task-agnostic rewrite of (b) via the donor
  (d) d_contrast     (enforce; avoid) distilled by the donor from its own
                     success/failure trajectory pair (MemCollab style)
  (e) e_b_self       receiver's own lessons from mid-tier experience (ceiling)
  (f) f_placebo      same-format content-free generic tips (must tie (a))

Flow: donor re-solves the canary train worlds (hard tier, seed 20260726 —
identical request bodies to the canary gate, so these are disk-cache hits);
its typed lesson store is compiled from the worlds it SOLVED (its slip world
feeds the contrast pair).  Arms (c)/(d) are rewrites of (b) via the donor
model itself (temp 0, pinned prompts).  Heldout test worlds use a different
seed (instance-disjoint, sha-audited).  Eval = receiver on test worlds with
the arm's lesson context, simulator-scored.  Retrieval is top-k=3
deterministic token-Jaccard; the disagreement gate (Agent KB style) discards
retrieved lessons whose per-ore order claims contradict the test world's
STATED orders — on/off ablation flag, default ON for arms b/c/d.

Metric (prereg §4): TRR = (arm - no-mem) / (B-self - no-mem) on hard tier;
negative-transfer rate per task with Track-style tags; per-lesson-type TRR
behind --include-per-type.  Kill conditions (prereg §5) are a pure function
(evaluate_kill_conditions) the sealed judge can call; here they are only a
mechanical observation.  Prereg-reading note: K1's "B-self ZS >= 60%" is read
as the receiver no-memory accuracy (the a4 recipe uses "B-self ZS" for the
receiver zero-shot bar).

Slice-2 smoke deviations (recorded in every receipt):
* donor lesson store = deterministic typed-lesson compile from donor-SOLVED
  train worlds (not donor free-written text) — wiring simplification.
* retrieval = deterministic token-Jaccard, not the pinned BGE embedder
  (MemDelta fixed-embedding rule bites at sealed prep, not dev smoke).
* gate ablation is wired (--no-gate) but the smoke runs gate ON only.
* per-type TRR arms exist (--include-per-type) but stay off in the smoke
  budget (<=20 new live calls: 12 eval + 2 donor rewrites + 2 B-self).

Everything here is a DEVELOPMENT_ONLY measurement: no scientific claim;
judgment belongs to the LakatosTree gate, never to this file.

Usage (once the vLLM box is back):
  .venv/bin/python f3v2_arms.py --dry-run            # offline plan, no calls
  ./f3v2_smoke_preflight.sh                          # endpoint checks + smoke
  .venv/bin/python f3v2_arms.py --smoke \
      --endpoint http://192.168.219.102:8000 --donor-model qwen3.6-27b \
      --receiver-endpoint http://192.168.219.102:8001 \
      --receiver-model qwen3-4b-real
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
from pathlib import Path
import random
import re
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

f2 = importlib.import_module("f2_delta_w_credit")
fw = importlib.import_module("f3v2_procedural_worlds")
# identical system prompt to the canary gate: donor train re-solves below hit
# the canary's disk cache byte-for-byte (same endpoint/model/body/seed)
canary = importlib.import_module("f3v2_canary_gate")

PREREG_PATH = Path(
    "/Users/lagyeongjun/CD/SYMPOSIUM/HSWM/PREREG_F3V2_HARDER_TRANSFER_2026-07-26.md")
RECEIPT_DIR = HERE / "receipts"

SYSTEM_PROMPT = canary.SYSTEM_PROMPT
WRITER_SYSTEM = (
    "You are distilling agent experience into reusable field notes. Reply "
    "with JSON only.")

ARMS = ("a_no_memory", "b_naive_donor", "c_abstracted", "d_contrast",
        "e_b_self", "f_placebo")
GATE_ARMS = ("b_naive_donor", "c_abstracted", "d_contrast")
TOP_K = 3  # prereg §3: top-k=3 (MemCollab non-monotonic)

K1_RECEIVER_ZS_SATURATION = 0.60  # prereg §5 K1: "B-self ZS >= 60%"
K3_PRIMING_MARGIN = 0.1           # prereg §5 K3

PLACEBO_TIPS = (
    "Read every instruction twice before starting any procedure.",
    "Keep the workshop tidy and put every tool back where it belongs.",
    "Write down what you did so that you can repeat it later.",
    "If something goes wrong, stop and check each step in order.",
    "Measure twice, cut once: confirm the requirements before acting.",
    "Work steadily and do not rush the final step.",
    "Label your materials so that nothing gets mixed up.",
    "Take notes on failures; they will be useful next time.",
    "A clear plan before the first action saves rework afterwards.",
    "Check off each requirement as you complete it.",
    "Good lighting and a clean bench prevent most mistakes.",
    "When two steps seem equal, do the simpler one first.",
    "Keep a checklist and mark items as you finish them.",
    "Ask whether each action is reversible before you take it.",
    "Slow is smooth, and smooth is fast.",
    "Store leftover materials properly for the next job.",
)

ABSTRACT_PROMPT = """You are distilling field notes for transfer.

Below are raw typed field notes from an experienced agent's foundry worlds.
Rewrite them as task-agnostic insights that apply to ANY ritual-foundry
world: remove ALL ore names, world names, and world-specific preparation
orders, but keep the procedure (how to schedule work) and the norms (what to
enforce, what to avoid). 3-6 bullets.

RAW NOTES:
{raw}

Reply with JSON only: {{"lessons": ["...", "..."]}}."""

CONTRAST_PROMPT = """You are distilling a success/failure contrast into norms.

An experienced agent solved ritual-foundry worlds. One trajectory SUCCEEDED,
one FAILED on a rule violation. Distill the behavioral difference into
(enforce; avoid) norm pairs: task-agnostic, no ore names, no world names.
2-4 enforce rules and 2-4 avoid rules.

WORLD RULES (shared by both trajectories):
{rules}

SUCCESSFUL trajectory ({n_ok} actions, fuse succeeded):
{ok_actions}

FAILED trajectory (violation: {fail_reason}):
{fail_actions}

Reply with JSON only: {{"enforce": ["..."], "avoid": ["..."]}}."""

BSELF_WRITE_PROMPT = """You just solved a ritual-foundry task:

{task}

Your solution (accepted): {actions}

Write field notes that would help you solve NEW foundry worlds with
different ores and different preparation orders: what you learned about how
foundries work, the procedure you used, and mistakes to avoid. 3-6 bullets.

Reply with JSON only: {{"lessons": ["...", "..."]}}."""


class ArmsError(RuntimeError):
    pass


# ---------------------------------------------------------------- pure pieces
def build_donor_lesson_store(train_worlds: list[dict],
                             donor_rows: list[dict]) -> list[dict]:
    """Typed lessons of the train worlds the donor SOLVED (flattened)."""
    ok_worlds = {r["world_id"] for r in donor_rows if r.get("correct")}
    store: list[dict] = []
    for world in train_worlds:
        if world["world_id"] not in ok_worlds:
            continue
        lessons = world["lessons"]
        for entry in lessons["fact"]:
            store.append({"lesson_id": entry["lesson_id"], "type": "fact",
                          "world_id": world["world_id"], "text": entry["text"]})
        for key in ("workflow", "norm"):
            entry = lessons[key]
            text = entry["text"] if key == "workflow" else (
                f"{entry['enforce']}. {entry['avoid']}")
            store.append({"lesson_id": entry["lesson_id"], "type": key,
                          "world_id": world["world_id"], "text": text})
    return store


def _tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", text.casefold()) if len(t) > 2}


def retrieve_topk(query_text: str, store: list[dict], k: int = TOP_K) -> list[dict]:
    """Deterministic token-Jaccard retrieval (dev smoke embedder stand-in)."""
    q = _tokens(query_text)
    scored = []
    for entry in store:
        toks = _tokens(entry["text"])
        union = len(q | toks) or 1
        scored.append((len(q & toks) / union, entry["lesson_id"], entry))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [e for _s, _i, e in scored[:k]]


_ORDER_CLAIM_RE = re.compile(
    r"preparation order of ([a-z]+)\s*:\s*((?:[a-z]+\s*->\s*)+[a-z]+)", re.I)


def disagreement_gate(lessons: list[dict], world: dict) -> tuple[list[dict], list[dict]]:
    """Drop lessons whose per-ore order claims contradict the world's STATED
    orders (Agent KB disagreement gate). Returns (kept, dropped-with-reason)."""
    kept, dropped = [], []
    for entry in lessons:
        reason = None
        for m in _ORDER_CLAIM_RE.finditer(entry["text"]):
            ore = m.group(1).casefold()
            claimed = tuple(" ".join(m.group(2).casefold().split()).split(" -> "))
            if ore in world["items"]:
                actual = tuple(world["ladders"][ore])
                if claimed != actual:
                    reason = (f"claims order of {ore} as {' -> '.join(claimed)} "
                              f"but the world states {' -> '.join(actual)}")
                    break
        if reason is None:
            kept.append(entry)
        else:
            dropped.append({"lesson_id": entry["lesson_id"], "reason": reason})
    return kept, dropped


def render_lesson_block(lessons_texts: list[str]) -> str:
    return ("Field notes from prior foundry work:\n"
            + "\n".join(f"- {t}" for t in lessons_texts))


def build_placebo(reference_block: str, seed_tag: str,
                  band: tuple[float, float] = (0.85, 1.15)) -> str:
    """Content-free generic tips, format-matched to the reference lesson block
    (same notes-block shape) and inside its token-length band (placebo format
    parity, prereg §3 arm f).  Bullet count is NOT matched — the priming
    control needs length parity, not structural identity; tips may repeat if
    the reference is longer than the whole pool."""
    rng = random.Random(f"f3v2-placebo:{seed_tag}")
    tips = list(PLACEBO_TIPS)
    rng.shuffle(tips)
    target = len(reference_block)
    chosen: list[str] = []
    i = 0
    while len(render_lesson_block(chosen)) < band[0] * target:
        chosen.append(tips[i % len(tips)])
        i += 1
        if i > 3 * len(tips):  # pool exhausted without reaching the band
            break
    if len(render_lesson_block(chosen)) > band[1] * target and len(chosen) > 1:
        chosen.pop()
    return render_lesson_block(chosen)


def compute_trr(acc_arm: float | None, acc_a: float | None,
                acc_e: float | None) -> float | None:
    """TRR = (arm - no-mem) / (B-self - no-mem); None when the ceiling gap
    collapses (B-self == no-mem) or any input is missing."""
    if acc_arm is None or acc_a is None or acc_e is None:
        return None
    denom = acc_e - acc_a
    if denom <= 0:
        return None
    return (acc_arm - acc_a) / denom


def negative_transfer_rate(vec_arm: list[int], vec_a: list[int]) -> float | None:
    """Fraction of tasks where the arm scored WORSE than no-mem (binary)."""
    if not vec_arm or len(vec_arm) != len(vec_a):
        return None
    return sum(1 for x, a in zip(vec_arm, vec_a) if x < a) / len(vec_arm)


def bootstrap_paired_ci(vec_x: list[int], vec_y: list[int], *,
                        n_boot: int = 2000, seed: int = 0) -> dict | None:
    """CI of mean(x - y) over paired per-task vectors (single resample index)."""
    if not vec_x or len(vec_x) != len(vec_y):
        return None
    rng = random.Random(seed)
    n = len(vec_x)
    diffs = sorted(
        sum(vec_x[i] for i in idx) / n - sum(vec_y[i] for i in idx) / n
        for idx in ([rng.randrange(n) for _ in range(n)] for _ in range(n_boot)))
    return {"mean": sum(diffs) / n_boot,
            "ci95": [diffs[int(0.025 * n_boot)], diffs[int(0.975 * n_boot)]]}


def evaluate_kill_conditions(acc: dict, vectors: dict, *,
                             n_boot: int = 2000, seed: int = 0) -> dict:
    """Prereg §5 K1-K3 as a pure function (the sealed judge calls this).

    K1 environment: TRR_c <= 0 AND TRR_d <= 0 AND receiver no-mem >= 60%.
    K2 claim:       TRR_naive < 0 AND neither contrast nor abstracted beats
                    naive with a paired bootstrap CI (lower bound > 0).
    K3 priming:     TRR_placebo >= TRR_abstracted - 0.1.
    fired=None means indeterminate (missing/degenerate inputs), never a pass.
    """
    acc_a, acc_e = acc.get("a_no_memory"), acc.get("e_b_self")
    trr = {arm: compute_trr(acc.get(arm), acc_a, acc_e)
           for arm in ("b_naive_donor", "c_abstracted", "d_contrast", "f_placebo")}

    if trr["c_abstracted"] is None or trr["d_contrast"] is None or acc_a is None:
        k1 = {"fired": None, "reason": "TRR indeterminate (ceiling gap collapsed)"}
    else:
        k1 = {"fired": bool(trr["c_abstracted"] <= 0
                            and trr["d_contrast"] <= 0
                            and acc_a >= K1_RECEIVER_ZS_SATURATION),
              "reason": (f"TRR_c={_r2(trr['c_abstracted'])}, "
                         f"TRR_d={_r2(trr['d_contrast'])}, "
                         f"receiver_zs={_r2(acc_a)} (bar {K1_RECEIVER_ZS_SATURATION})")}

    if trr["b_naive_donor"] is None:
        k2 = {"fired": None, "reason": "naive TRR indeterminate"}
    elif not trr["b_naive_donor"] < 0:
        k2 = {"fired": False, "reason": f"naive TRR {_r2(trr['b_naive_donor'])} >= 0"}
    else:
        sig = {}
        for arm, key in (("c_abstracted", "sig_c_beats_naive"),
                         ("d_contrast", "sig_d_beats_naive")):
            ci = bootstrap_paired_ci(vectors.get(arm) or [],
                                     vectors.get("b_naive_donor") or [],
                                     n_boot=n_boot, seed=seed)
            sig[key] = None if ci is None else bool(ci["ci95"][0] > 0)
        if any(v is None for v in sig.values()):
            k2 = {"fired": None, "reason": "missing paired vectors for bootstrap"}
        else:
            k2 = {"fired": bool(not sig["sig_c_beats_naive"]
                                and not sig["sig_d_beats_naive"]),
                  "reason": (f"naive TRR {_r2(trr['b_naive_donor'])} < 0 and "
                             f"c beats naive: {sig['sig_c_beats_naive']}, "
                             f"d beats naive: {sig['sig_d_beats_naive']}")}

    if trr["f_placebo"] is None or trr["c_abstracted"] is None:
        k3 = {"fired": None, "reason": "placebo/abstracted TRR indeterminate"}
    else:
        k3 = {"fired": bool(trr["f_placebo"]
                            >= trr["c_abstracted"] - K3_PRIMING_MARGIN),
              "reason": (f"TRR_placebo={_r2(trr['f_placebo'])} vs "
                         f"TRR_abstracted={_r2(trr['c_abstracted'])} "
                         f"(margin {K3_PRIMING_MARGIN})")}

    return {"trr": {k: _r2(v) for k, v in trr.items()},
            "k1_environment_kill": k1, "k2_claim_kill": k2,
            "k3_priming_kill": k3,
            "note": "mechanical observation only; sealed judgment belongs to the gate"}


def _r2(x):
    return None if x is None else round(x, 4)


# ---------------------------------------------------------------- llm pieces
def solve(chat, model: str, world: dict, lesson_block: str | None,
          seed: int, max_tokens: int) -> dict:
    user = ((lesson_block + "\n\n") if lesson_block else "") + fw.render_prompt(world)
    meta = chat.chat(model=model, system=SYSTEM_PROMPT, user=user,
                     seed=seed, max_tokens=max_tokens)
    actions = fw.parse_model_actions(meta["text"])
    ok, reason = (fw.verify_solution(world, actions) if actions is not None
                  else (False, "parse_failure: no JSON actions object"))
    return {"world_id": world["world_id"], "parse_ok": actions is not None,
            "actions": actions, "correct": bool(ok), "reason": reason,
            "cached": meta["cached"], "usage": meta["usage"],
            "request_sha256": meta["request_sha256"]}


def _json_field(meta: dict, key: str) -> list[str]:
    try:
        obj = json.loads(meta["text"])
        vals = obj.get(key)
        return [str(v) for v in vals] if isinstance(vals, list) else []
    except (ValueError, TypeError):
        return []


def abstract_lessons(chat, model: str, raw_block: str, seed: int,
                     max_tokens: int) -> dict:
    meta = chat.chat(model=model, system=WRITER_SYSTEM,
                     user=ABSTRACT_PROMPT.format(raw=raw_block),
                     seed=seed, max_tokens=max_tokens)
    return {"lessons": _json_field(meta, "lessons"), "cached": meta["cached"],
            "request_sha256": meta["request_sha256"]}


def contrast_lessons(chat, model: str, world: dict, ok_row: dict,
                     fail_row: dict, fail_reason: str, seed: int,
                     max_tokens: int) -> dict:
    rules_txt = "\n".join(r["text"] for r in world["rules"])
    meta = chat.chat(model=model, system=WRITER_SYSTEM,
                     user=CONTRAST_PROMPT.format(
                         rules=rules_txt, n_ok=len(ok_row["actions"] or []),
                         ok_actions=json.dumps(ok_row["actions"]),
                         fail_reason=fail_reason,
                         fail_actions=json.dumps(fail_row["actions"])),
                     seed=seed, max_tokens=max_tokens)
    lessons = ([f"enforce: {t}" for t in _json_field(meta, "enforce")]
               + [f"avoid: {t}" for t in _json_field(meta, "avoid")])
    return {"lessons": lessons, "cached": meta["cached"],
            "request_sha256": meta["request_sha256"]}


def bself_lessons(chat, model: str, mid_world: dict, seed: int,
                  max_tokens: int) -> dict:
    solve_row = solve(chat, model, mid_world, None, seed, max_tokens)
    write = chat.chat(model=model, system=WRITER_SYSTEM,
                      user=BSELF_WRITE_PROMPT.format(
                          task=fw.render_prompt(mid_world),
                          actions=json.dumps(solve_row["actions"])),
                      seed=seed, max_tokens=max_tokens)
    return {"solve_row": solve_row, "lessons": _json_field(write, "lessons"),
            "write_cached": write["cached"],
            "write_request_sha256": write["request_sha256"]}


def _track_tag(row: dict, context_lessons: list[dict]) -> str | None:
    """Track-style negative-transfer tag (heuristic, dev smoke)."""
    if row["correct"]:
        return None
    reason = row["reason"]
    ore_match = re.search(r"\(([a-z]+)\)", reason)
    if "requires" in reason and ore_match:
        ore = ore_match.group(1)
        if any(ore in les["text"] for les in context_lessons):
            return "mismatched_anchoring"
        return "misapplied_practice"
    if "fuse" in reason:
        return "false_validation"
    return "misapplied_practice"


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--endpoint", default="http://192.168.219.102:8000")
    ap.add_argument("--receiver-endpoint", default="")
    ap.add_argument("--donor-model", default="qwen3.6-27b")
    ap.add_argument("--receiver-model", default="qwen3-4b-real")
    ap.add_argument("--seed", type=int, default=20260726)
    ap.add_argument("--train-seed", type=int, default=20260726)
    ap.add_argument("--train-worlds", type=int, default=8)
    ap.add_argument("--test-seed", type=int, default=20260727)
    ap.add_argument("--n-test", type=int, default=2)
    ap.add_argument("--bself-seed", type=int, default=20260728)
    ap.add_argument("--max-tokens", type=int, default=768)
    ap.add_argument("--max-live-calls", type=int, default=20)
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--gate", dest="gate", action="store_true", default=True)
    ap.add_argument("--no-gate", dest="gate", action="store_false")
    ap.add_argument("--include-per-type", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--dry-run", action="store_true",
                    help="build the plan without any chat call and exit")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    if args.smoke:
        args.n_test = min(args.n_test, 2)

    t0 = time.time()
    ts = int(t0)
    endpoint_v1 = args.endpoint.rstrip("/")
    if not endpoint_v1.endswith("/v1"):
        endpoint_v1 += "/v1"
    receiver_endpoint_v1 = (args.receiver_endpoint or args.endpoint).rstrip("/")
    if not receiver_endpoint_v1.endswith("/v1"):
        receiver_endpoint_v1 += "/v1"
    out_path = Path(args.out) if args.out else (
        RECEIPT_DIR / f"f3v2_arms_smoke_{ts}.json")

    train_worlds = fw.generate_batch(args.train_worlds, "hard", args.train_seed)
    test_worlds = fw.generate_batch(args.n_test, "hard", args.test_seed)
    mid_world = fw.generate_world(seed=args.bself_seed, tier="mid", world_idx=0)
    train_shas = {fw.world_sha256(w) for w in train_worlds}
    test_shas = {fw.world_sha256(w) for w in test_worlds}
    leakage = {"train_seed": args.train_seed, "test_seed": args.test_seed,
               "world_sha_overlap": sorted(train_shas & test_shas),
               "binding_verdict": "CLEAN" if not (train_shas & test_shas) else "LEAK"}
    if leakage["binding_verdict"] == "LEAK":
        raise ArmsError(f"train/test world overlap: {leakage['world_sha_overlap']}")

    planned_calls = {
        "donor_train_resolves_cache_hits": args.train_worlds,
        "abstracted_rewrite": 1, "contrast_distill": 1, "bself_mid_solve": 1,
        "bself_lesson_write": 1, "receiver_eval": len(ARMS) * args.n_test,
    }
    planned_calls["total_new_live"] = sum(
        v for k, v in planned_calls.items() if "cache" not in k)

    if args.dry_run:
        print(json.dumps({
            "dry_run": True, "leakage": leakage,
            "train_worlds": [(w["world_id"], len(w["items"])) for w in train_worlds],
            "test_worlds": [(w["world_id"], len(w["items"]),
                             fw.world_sha256(w)[:12]) for w in test_worlds],
            "bself_mid_world": mid_world["world_id"],
            "arms": ARMS, "gate_on_for": list(GATE_ARMS) if args.gate else [],
            "planned_calls": planned_calls,
            "budget_ok": planned_calls["total_new_live"] <= args.max_live_calls,
        }, indent=1, ensure_ascii=False))
        return 0 if planned_calls["total_new_live"] <= args.max_live_calls else 1

    receipt = {
        "schema_version": "hswm-f3v2-arms-receipt/v1",
        "mode": "development",
        "stage": "DEVELOPMENT_ONLY",
        "branch": "F3v2-harder-transfer",
        "smoke": bool(args.smoke),
        "preregistration_file": str(PREREG_PATH),
        "preregistration_file_sha256": hashlib.sha256(
            PREREG_PATH.read_bytes()).hexdigest(),
        "preregistration_status": ("DRAFT — user ratify pending; machine-lock "
                                   "to prom_search_hswm/evidence/PREREG_f3v2_*.json "
                                   "happens only after ratify"),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "harness_module_sha256": {
            "f3v2_procedural_worlds.py": hashlib.sha256(
                (HERE / "f3v2_procedural_worlds.py").read_bytes()).hexdigest(),
            "f3v2_canary_gate.py": hashlib.sha256(
                (HERE / "f3v2_canary_gate.py").read_bytes()).hexdigest(),
            "f2_delta_w_credit.py": hashlib.sha256(
                (HERE / "f2_delta_w_credit.py").read_bytes()).hexdigest(),
        },
        "config": vars(args) | {"endpoint_v1": endpoint_v1,
                                "receiver_endpoint_v1": receiver_endpoint_v1,
                                "out": str(out_path)},
        "donor_freeze": {"backend": "vllm-openai-compat", "url": endpoint_v1,
                         "model": args.donor_model,
                         "thinking_off": "chat_template_kwargs enable_thinking=false"},
        "receiver_freeze": {
            "backend": "vllm-openai-compat", "url": receiver_endpoint_v1,
            "model": args.receiver_model,
            "thinking_off": "chat_template_kwargs enable_thinking=false",
            "system_prompt_sha256": hashlib.sha256(
                SYSTEM_PROMPT.encode()).hexdigest(),
            "seed": args.seed, "temperature": 0, "max_tokens": args.max_tokens,
            "note": ("DEV STAND-IN for the sealed qwen3:14b receiver; frozen, "
                     "input channel only; only the lesson block varies across "
                     "arms. Real Qwen3-4B on its own container (root "
                     "Qwen/Qwen3-4B per /v1/models)."),
        },
        "honesty": ("grounded measurement only; no scientific claim; judgment "
                    "is the gate's. DEVELOPMENT_ONLY: nothing sealed. n=2 test "
                    "tasks is a WIRING test, not a measurement."),
        "deviations": [
            "donor lesson store = deterministic typed-lesson compile from "
            "donor-SOLVED train worlds (not donor free-written text).",
            "retrieval = deterministic token-Jaccard (BGE fixed embedder is "
            "deferred to sealed prep, MemDelta rule).",
            "gate ablation wired (--no-gate) but smoke runs gate ON only.",
            "per-type TRR arms behind --include-per-type, off in smoke budget.",
            "B-self experience = 1 mid-tier world (parent directive).",
            "K1 'B-self ZS >= 60%' read as receiver no-memory accuracy.",
        ],
        "leakage": leakage,
        "train_worlds": [{"world_id": w["world_id"], "n_items": len(w["items"]),
                          "world_sha256": fw.world_sha256(w)} for w in train_worlds],
        "test_worlds": [{"world_id": w["world_id"], "n_items": len(w["items"]),
                         "world_sha256": fw.world_sha256(w)} for w in test_worlds],
        "disagreement_gate": {"default_on_for": list(GATE_ARMS),
                              "active": bool(args.gate), "top_k": TOP_K},
        "planned_calls": planned_calls,
    }

    budget = f2.Budget(args.max_live_calls)
    donor = f2.CachedOpenAIChat(endpoint_v1, budget)
    receiver = f2.CachedOpenAIChat(receiver_endpoint_v1, budget)
    aborted = None
    try:
        # donor re-solves train worlds (canary-identical bodies: cache hits)
        donor_rows = [solve(donor, args.donor_model, w, None,
                            args.seed, args.max_tokens) for w in train_worlds]
        store = build_donor_lesson_store(train_worlds, donor_rows)
        raw_block = render_lesson_block([e["text"] for e in store])
        receipt["donor_train"] = {
            "n_worlds": len(train_worlds),
            "n_solved": sum(r["correct"] for r in donor_rows),
            "solved_worlds": [r["world_id"] for r in donor_rows if r["correct"]],
            "failed_worlds": [r["world_id"] for r in donor_rows
                              if not r["correct"]],
            "lesson_store_size": len(store),
        }

        abs_res = abstract_lessons(donor, args.donor_model, raw_block,
                                   args.seed, args.max_tokens)
        ok_row = next((r for r in donor_rows if r["correct"]), None)
        fail_row = next((r for r in donor_rows if not r["correct"]), None)
        if ok_row is None:
            raise ArmsError("donor solved no train world — no lesson store")
        if fail_row is not None:
            fail_world = train_worlds[[w["world_id"] for w in train_worlds]
                                      .index(fail_row["world_id"])]
            con_res = contrast_lessons(donor, args.donor_model, fail_world,
                                       ok_row, fail_row, fail_row["reason"],
                                       args.seed, args.max_tokens)
            receipt["contrast_pair"] = {"success": ok_row["world_id"],
                                        "failure": fail_row["world_id"],
                                        "synthetic_failure": False}
        else:  # no donor failure: synthetic batching trajectory as the pair
            fail_world = train_worlds[0]
            synth_actions = fw.naive_batch_solver(fail_world)
            _ok, synth_reason = fw.verify_solution(fail_world, synth_actions)
            con_res = contrast_lessons(
                donor, args.donor_model, fail_world, ok_row,
                {"actions": synth_actions}, synth_reason,
                args.seed, args.max_tokens)
            receipt["contrast_pair"] = {"success": ok_row["world_id"],
                                        "failure": "synthetic_naive_batch",
                                        "synthetic_failure": True}

        bself = bself_lessons(receiver, args.receiver_model, mid_world,
                              args.seed, args.max_tokens)
        bself_block = render_lesson_block(bself["lessons"]) if bself["lessons"] \
            else ""
        receipt["b_self"] = {"mid_world": mid_world["world_id"],
                             "mid_solve_correct": bself["solve_row"]["correct"],
                             "n_lessons": len(bself["lessons"])}

        arm_blocks: dict[str, str | None] = {
            "a_no_memory": None,
            "c_abstracted": render_lesson_block(abs_res["lessons"]),
            "d_contrast": render_lesson_block(con_res["lessons"]),
            "e_b_self": bself_block,
        }
        # placebo parity reference = the (b) block on the first test world
        ref_lessons = retrieve_topk(fw.render_prompt(test_worlds[0]), store)
        b_ref_block = render_lesson_block([e["text"] for e in ref_lessons])
        arm_blocks["f_placebo"] = build_placebo(b_ref_block, f"{args.seed}")
        receipt["placebo"] = {
            "reference_block_chars": len(b_ref_block),
            "placebo_block_chars": len(arm_blocks["f_placebo"]),
            "band": [0.85, 1.15],
        }

        arms_out: dict[str, dict] = {}
        for arm in ARMS:
            rows = []
            for world in test_worlds:
                if arm == "b_naive_donor":
                    lessons = retrieve_topk(fw.render_prompt(world), store)
                elif arm == "c_abstracted":
                    lessons = [{"lesson_id": "abstracted-0",
                                "text": t} for t in abs_res["lessons"]]
                elif arm == "d_contrast":
                    lessons = [{"lesson_id": "contrast-0",
                                "text": t} for t in con_res["lessons"]]
                elif arm == "e_b_self":
                    lessons = [{"lesson_id": f"bself-{i}", "text": t}
                               for i, t in enumerate(bself["lessons"])]
                else:
                    lessons = []
                dropped: list[dict] = []
                if arm in GATE_ARMS and args.gate and lessons:
                    lessons, dropped = disagreement_gate(lessons, world)
                if arm in ("a_no_memory",):
                    block = None
                elif arm == "f_placebo":
                    block = arm_blocks["f_placebo"]
                elif arm in ("b_naive_donor", "c_abstracted",
                             "d_contrast", "e_b_self"):
                    block = render_lesson_block([e["text"] for e in lessons]) \
                        if lessons else None
                row = solve(receiver, args.receiver_model, world, block,
                            args.seed, args.max_tokens)
                row["n_context_lessons"] = len(lessons)
                row["gate_dropped"] = dropped
                row["track_tag"] = _track_tag(row, lessons)
                rows.append(row)
            vec = [r["correct"] for r in rows]
            arms_out[arm] = {
                "rows": rows, "correct_vector": [int(v) for v in vec],
                "accuracy": round(sum(vec) / len(vec), 4) if rows else None,
                "block_chars": len(arm_blocks.get(arm) or ""),
            }

        acc = {arm: v["accuracy"] for arm, v in arms_out.items()}
        vectors = {arm: v["correct_vector"] for arm, v in arms_out.items()}
        receipt["arms"] = arms_out
        receipt["metrics"] = {
            "accuracies": acc,
            "trr": {arm: _r2(compute_trr(acc[arm], acc["a_no_memory"],
                                         acc["e_b_self"]))
                    for arm in ("b_naive_donor", "c_abstracted", "d_contrast",
                                "f_placebo")},
            "negative_transfer_rate": {
                arm: _r2(negative_transfer_rate(vectors[arm],
                                                vectors["a_no_memory"]))
                for arm in ARMS if arm != "a_no_memory"},
            "placebo_minus_no_mem": _r2(acc["f_placebo"] - acc["a_no_memory"]),
            "note": "n=2 wiring smoke — values are not a measurement.",
        }
        receipt["kill_condition_observations"] = evaluate_kill_conditions(
            acc, vectors, n_boot=args.n_boot, seed=args.seed)
    except (ArmsError, f2.BudgetExceeded) as err:
        aborted = str(err)
    except Exception as err:  # noqa: BLE001
        aborted = f"{type(err).__name__}: {err}"

    receipt["llm_budget"] = {
        "max_calls": args.max_live_calls, "used": budget.used,
        "donor": {"model": args.donor_model, "url": endpoint_v1,
                  "misses": donor.misses, "hits": donor.hits},
        "receiver": {"model": args.receiver_model, "url": receiver_endpoint_v1,
                     "misses": receiver.misses, "hits": receiver.hits},
    }
    receipt["aborted"] = aborted
    receipt["wall_clock_s"] = round(time.time() - t0, 1)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=1, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(json.dumps({
        "receipt": str(out_path), "aborted": aborted,
        "leakage": receipt["leakage"]["binding_verdict"],
        "donor_train": receipt.get("donor_train"),
        "accuracies": receipt.get("metrics", {}).get("accuracies"),
        "trr": receipt.get("metrics", {}).get("trr"),
        "kills": {k: v.get("fired") for k, v in
                  receipt.get("kill_condition_observations", {}).items()
                  if k.startswith("k")},
        "calls": receipt["llm_budget"], "wall_clock_s": receipt["wall_clock_s"],
    }, indent=1, ensure_ascii=False))
    return 0 if aborted is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
