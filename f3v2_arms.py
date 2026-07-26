"""F3v2 arms harness (slice 2) — prereg §3 arms over the procedural testbed.

PREREG (draft, sha-pinned in every receipt):
  /Users/lagyeongjun/CD/SYMPOSIUM/HSWM/PREREG_F3V2_HARDER_TRANSFER_2026-07-26.md §3-§5.

Slice 1 (f3v2_procedural_worlds.py) built the foundry-world testbed and the
canary gate adopted it (receipt f3v2_canary_gate_dev_1785040277.json: receiver
ZS hard 12.5% <= 30, donor 87.5% >= 70, gap 75pp).  This module implements the
prereg §3 transfer arms on top of it: a donor experiences TRAIN worlds, its
experience is distilled into typed lessons, and the frozen receiver is scored
on disjoint TEST worlds with each arm's memory context.  Scoring is the
deterministic world simulator — no LLM judge anywhere in this slice.

Split / leakage (prereg §6.2): experience comes from `train_seed` worlds,
scoring from `test_seed` worlds (same tier, default S / S+1).  Disjointness is
enforced on world_sha256 — world_id is per-seed (f3v2-<tier>-<idx>) and
collides across seeds by construction, so content sha is the identity.
make_splits fails closed on any shared sha.

Donor experience pipeline: run_experience(chat, model, worlds, ...) attempts
each world (render_prompt -> chat -> parse_model_actions -> simulate) and
returns per-world trajectory records.  `chat` is INJECTED — production passes
f2.CachedOpenAIChat (budget-capped, disk-cached); tests and the dry-run smoke
pass ScriptedChat (offline, exact-table, fail-closed on a miss).
compile_arm_lessons reuses fw.compile_lessons for the per-world ground-truth
typed lessons (fact / workflow / norm, prereg §2) and adds trajectory-derived
contrast entries: classify_failure maps a failed trajectory to a planted
failure mode (verb-batching / blast-shortcut / interleave-cooling /
drain-timeout / reheat-shatter / order-confusion / parse-failure) from its
violation kind, reason string, and action-sequence signature — a deterministic
heuristic, documented at the function.

Arms (each builds the receiver's augmented prompt for a test world):

* (a) no_memory   — bare render_prompt, nothing added.
* (b) naive_donor — donor train-world typed lessons verbatim.
* (c) abstracted  — programmatic task-agnostic rewrite: per-ore order facts
                    dropped (world-specific), world name -> "the foundry",
                    ore names -> "each ore", relic -> "the relic", numeric
                    drain windows -> "the drain window"; the workflow layer
                    collapses to the planted-strategy statement (already
                    world-agnostic); enforce/avoid semantics kept; identical
                    texts deduped with merged provenance; a fail-closed check
                    asserts no world token survives.  There is deliberately NO
                    LLM-mediated rewrite hook in the dev path: (c) must be a
                    deterministic transformation here, and a live rewrite
                    would add an unbudgeted call channel.
* (d) contrast    — (enforce; avoid) pairs kept only when supported by BOTH a
                    donor success trajectory AND an observed failure
                    trajectory on the same train world (MemCollab-style).
                    Success evidence is donor-only; failure evidence is the
                    union of donor and receiver train trajectories — the
                    disagreement gate already runs receiver ZS on train, so
                    the receiver's OWN failure modes enter the contrast at
                    zero extra call cost.
* (e) b_self      — the receiver's own lessons from its own train
                    trajectories: the typed lessons of the worlds it
                    experienced PLUS (enforce; avoid) pairs distilled from
                    its OWN observed failure modes.  With one attempt per
                    world a receiver-only success/failure contrast is
                    structurally empty, so the self-contrast success side is
                    the world's planted winnability
                    (ground_truth_trajectories — no LLM): the ceiling is the
                    perfect consolidation of the receiver's own experience.
                    Same compilation PIPELINE as (d); self pairs are framed
                    "from your own failed attempt" so (d)/(e) contexts stay
                    textually distinct.
* (f) placebo     — identical lesson FORMAT (fact/workflow/norm blocks of
                    comparable length) with unrelated-domain content
                    (household/craft tips).  Zero foundry verbs is a
                    fail-closed module invariant; content-word disjointness
                    vs the real lesson corpus is asserted in tests.
* (x) xvendor     — prereg §8 deferral: non-Qwen receiver not available;
                    build_arm_prompt raises NotImplementedError.

Retrieval (prereg §3): lessons attach to their source train worlds; for a
test world the top-k=3 lessons by embedding similarity are injected
(MemCollab non-monotonic k).  The embedder is FIXED across arms (MemDelta):
default HashEmbedder — deterministic offline token-hashed bag-of-words
(sha256(token) -> bucket) with cosine; an embedder callable is injectable for
the live path.  Query = the test world's rules text vs lesson texts.

Disagreement gate (on/off ablation; Agent KB: gate가 전이 성립 조건): the
receiver is run zero-shot on TRAIN worlds; a train world is disagreement-
flagged when the receiver failed it while the donor succeeded on it.  Gate ON
(arm variant `*_gated`) injects only flagged lessons; OFF injects all
retrieved.  no_memory / b_self / placebo are gate-invariant (a `_gated`
variant of those is an ArmsError).  For merged abstracted lessons the flag is
"any supporting world flagged" — generic lessons dedupe across worlds, so the
gate only bites (c) when NO supporting world is flagged; documented honestly.

TRR (prereg §4): per test world the arm's 0/1 score is paired across arms.
TRR = (arm - no_mem) / (b_self - no_mem) on the paired means, reported per
tier; the judgment target is min(TRR_c, TRR_d) on hard.  b_self == no_mem is
the degenerate case: TRR is reported null with degenerate=True (never a
divide-by-zero).  negative_transfer_rate (share of worlds with arm < no_mem)
rides along as the prereg's secondary metric.

Kills (prereg §5), pure functions over paired vectors + config:

* K1 env kill     — TRR_c <= 0 AND TRR_d <= 0 (hard) AND b_self acc >= 0.60.
                    "B-self ZS" is read as the arm-(e) accuracy: lessons
                    provably CAN move the receiver, so donor-transfer failure
                    indicts the environment's capability axis.
* K2 claim kill   — naive TRR < 0 AND neither contrast nor abstracted beats
                    naive by paired bootstrap 95% CI (LCB of the paired diff
                    > 0 required); reps=10000 with a pinned seed.
* K3 priming kill — TRR_placebo >= TRR_abstracted - 0.1.
* K4 (judge) / K5 (noise floor) are NOT APPLICABLE to simulator-scored F3v2:
  K4 presupposes an LLM judge panel (this testbed scores with the world
  simulator — reinstated only if a judge-scored variant is added, prereg §7
  step 2 measures it on the sealed judge track); K5 presupposes annotation
  error in gold labels (ground truth here is planted by construction,
  annotation error rate 0 — the kill cannot bind).  Both are recorded with
  one-line rationales in KILLS_NOT_APPLICABLE, never stubbed into fake
  measurements.

Receipts follow the canary-gate conventions: schema
hswm-f3v2-arms-receipt/v1, mode development, stage DEVELOPMENT_ONLY, prereg
file + sha256, script + harness-module sha256 map, config dump, worlds with
watermarks/sha256, split audit, per-arm results, TRR table, kills, llm_budget
block, wall_clock_s, and the honesty line: grounded measurement only; no
scientific claim; judgment is the gate's.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import math
from pathlib import Path
import random
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

fw = importlib.import_module("f3v2_procedural_worlds")

PREREG_PATH = Path(
    "/Users/lagyeongjun/CD/SYMPOSIUM/HSWM/PREREG_F3V2_HARDER_TRANSFER_2026-07-26.md")

TOP_K = 3                  # prereg §3: MemCollab non-monotonic top-k
BOOT_REPS = 10000          # prereg §5 K2: paired bootstrap replicates
K1_B_SELF_MIN = 0.60       # prereg §5 K1: b_self accuracy floor
K3_PLACEBO_SLACK = 0.1     # prereg §5 K3: placebo >= abstracted - 0.1

# byte-identical to f3v2_canary_gate.SYSTEM_PROMPT (receiver-freeze
# continuity with the adopted canary gate; the sha is pinned in its receipt).
SYSTEM_PROMPT = (
    "You are an agent solving synthetic foundry-world planning tasks. Read "
    "the world rules carefully, track every ore's state step by step, and "
    "reply with JSON only.")

CORE_ARM_IDS = ("a_no_memory", "b_naive_donor", "c_abstracted",
                "d_contrast", "e_b_self", "f_placebo")
GATED_ARM_IDS = ("b_naive_donor_gated", "c_abstracted_gated",
                 "d_contrast_gated")
ARM_POOLS = {"b_naive_donor": "naive", "c_abstracted": "abstracted",
             "d_contrast": "contrast", "e_b_self": "b_self",
             "f_placebo": "placebo"}
GATE_INVARIANT_ARMS = ("a_no_memory", "e_b_self", "f_placebo")


class ArmsError(RuntimeError):
    pass


class SplitError(ArmsError):
    pass


# ---------------------------------------------------------------- splits
def make_splits(n_train: int, n_test: int, tier: str,
                train_seed: int, test_seed: int) -> dict:
    """Train/test world sets, same tier, instance-disjoint by world_sha256.

    world_id is per-seed (f3v2-<tier>-<idx>) and collides across seeds by
    construction; the content sha is the split identity.  Fail-closed."""
    train = fw.generate_batch(n_train, tier, train_seed)
    test = fw.generate_batch(n_test, tier, test_seed)
    shared = sorted({fw.world_sha256(w) for w in train}
                    & {fw.world_sha256(w) for w in test})
    if shared:
        raise SplitError(
            f"train/test world overlap: {len(shared)} shared world_sha256 "
            f"(train_seed={train_seed}, test_seed={test_seed}); pick "
            "different seeds — leakage voids the run (prereg §6.2)")
    return {"train": train, "test": test}


# ---------------------------------------------------------------- experience
def run_experience(chat, model: str, worlds: list[dict], *, seed: int,
                   max_tokens: int, system: str = SYSTEM_PROMPT,
                   prompt_fn=None) -> list[dict]:
    """Attempt each world once; return per-world trajectory records.

    chat is any object with the CachedOpenAIChat.chat signature (production:
    f2.CachedOpenAIChat; offline: ScriptedChat).  prompt_fn(world) overrides
    the prompt (arm contexts); default is the bare ZS prompt."""
    rows = []
    for world in worlds:
        prompt = prompt_fn(world) if prompt_fn is not None \
            else fw.render_prompt(world)
        meta = chat.chat(model=model, system=system, user=prompt,
                         seed=seed, max_tokens=max_tokens)
        actions = fw.parse_model_actions(meta["text"])
        if actions is not None:
            sim = fw.simulate(world, actions)
            correct = bool(sim["ok"])
            violation, reason, steps = sim["violation"], sim["reason"], sim["steps"]
        else:
            correct, violation, reason, steps = (
                False, "parse_failure", "parse_failure: no JSON actions object", 0)
        rows.append({
            "world_id": world["world_id"],
            "world_seed": world["seed"],
            "watermark": world["watermark"],
            "tier": world["tier"],
            "n_items": len(world["items"]),
            "optimal_len": world["optimal_len"],
            "step_cap": world["step_cap"],
            "parse_ok": actions is not None,
            "actions": actions,
            "correct": correct,
            "violation": violation,
            "reason": reason,
            "steps": steps,
            "cached": meta["cached"],
            "usage": meta["usage"],
            "request_sha256": meta["request_sha256"],
        })
    return rows


def accuracy(rows: list[dict]):
    return round(sum(r["correct"] for r in rows) / len(rows), 4) if rows else None


# ------------------------------------------------------- failure taxonomy
_VERB_ITEM_RE = re.compile(r"(cleanse|heat|charge|inscribe|blast)\(([^)]+)\)")
_HEAT_RE = re.compile(r"heat\(([^)]+)\)")


def _batched(actions: list[str]) -> bool:
    """Verb-batching signature: the same verb applied to >=2 distinct ores in
    one consecutive run (the weak-planner policy shape — naive_batch_solver)."""
    run_verb, run_items = None, set()
    for action in actions:
        m = _VERB_ITEM_RE.match(action)
        if not m:
            run_verb, run_items = None, set()
            continue
        verb, item = m.group(1), m.group(2)
        if verb == run_verb:
            run_items.add(item)
            if len(run_items) >= 2:
                return True
        else:
            run_verb, run_items = verb, {item}
    return False


def _cooled_by_interleave(actions: list[str], fail_idx: int, item: str) -> bool:
    """The ore WAS heated, then a DIFFERENT ore was heated (one-crucible
    cooling revoked the heat), then a verb needing `heated` failed."""
    last_heat = None
    for i in range(fail_idx):
        m = _HEAT_RE.match(actions[i])
        if m and m.group(1) == item:
            last_heat = i
    if last_heat is None:
        return False
    for i in range(last_heat + 1, fail_idx):
        m = _HEAT_RE.match(actions[i])
        if m and m.group(1) != item:
            return True
    return False


def classify_failure(world: dict, traj: dict):
    """Map a failed trajectory to a planted failure mode (deterministic
    heuristic): blast-shortcut / reheat-shatter / verb-batching /
    interleave-cooling / drain-timeout / order-confusion / parse-failure.

    Priority is policy-shape first (blast usage, batching signature — those
    are the sins the lessons preach against), then violation-kind analysis;
    anything unmapped falls back to the raw simulator violation string."""
    if traj["correct"]:
        return None
    if not traj["parse_ok"]:
        return "parse-failure"
    actions = traj["actions"] or []
    violation = traj.get("violation") or ""
    reason = traj.get("reason") or ""
    if any(a.startswith("blast(") for a in actions):
        return "blast-shortcut"
    if violation == "shattered":
        return "reheat-shatter"
    if _batched(actions):
        return "verb-batching"
    if violation == "precondition" and "requires heated" in reason:
        fail_idx = traj["steps"]
        item = None
        if 0 <= fail_idx < len(actions):
            m = _VERB_ITEM_RE.match(actions[fail_idx])
            if m:
                item = m.group(2)
        if item is not None and _cooled_by_interleave(actions, fail_idx, item):
            return "interleave-cooling"
        return "order-confusion"
    if (violation == "precondition" and "requires primed" in reason
            and reason.startswith("inscribe(")):
        return "drain-timeout"
    if violation in ("precondition", "fuse_rejected", "no_fuse"):
        return "order-confusion"
    return violation or "unknown"


# ---------------------------------------------------------------- lessons
def _lesson(lesson_id: str, kind: str, *, text: str = "",
            enforce=None, avoid=None, mode=None, sources) -> dict:
    return {"lesson_id": lesson_id, "kind": kind, "text": text,
            "enforce": enforce, "avoid": avoid, "mode": mode,
            "sources": list(sources), "flagged": False}


CONTRAST_ENFORCE = (
    "enforce: run each ore's own preparation order atomically, one ore at a "
    "time, then fuse")
CONTRAST_AVOID = {
    "verb-batching": ("batching one verb across several ores (orders differ "
                      "per ore; the batch breaks each ore's own order and "
                      "trips the one-crucible cooling rule)"),
    "interleave-cooling": ("interleaving two ores' preparation (one crucible: "
                           "heating a second ore cools the first)"),
    "blast-shortcut": ("the blast shortcut (it taints the ore and the final "
                       "fuse fails)"),
    "drain-timeout": ("leaving a primed ore un-inscribed past the drain "
                      "window (it drains and must be redone)"),
    "reheat-shatter": ("re-heating a primed ore (it shatters and the world "
                       "is lost)"),
    "order-confusion": ("assuming all ores share one order (check each ore's "
                        "own listed order)"),
    "parse-failure": "free-form replies (emit only the JSON actions object)",
}


def _contrast_lesson(world: dict, mode: str, observed_reason: str, *,
                     framing: str = "observed") -> dict:
    wm = world["watermark"]
    avoid_body = CONTRAST_AVOID.get(
        mode, f"the pattern that failed in experience (violation: {mode})")
    if framing == "own":  # b_self: the receiver's OWN failed attempt
        tag = f"(from your own failed attempt: {observed_reason})"
    else:
        tag = f"(observed: {observed_reason})"
    return _lesson(
        f"{world['world_id']}-{wm[:8]}-contrast-{mode}-{framing}", "contrast",
        enforce=CONTRAST_ENFORCE,
        avoid=f"avoid: {avoid_body} {tag}",
        mode=mode, sources=[wm])


def ground_truth_trajectories(worlds: list[dict]) -> list[dict]:
    """Synthetic success trajectories (NO LLM): every world is winnable by
    construction (strategy_solver, slice-1 guarantee).  Used as the success
    side of the b_self self-contrast — with one attempt per world a
    receiver-only success/failure contrast is structurally empty, so the
    ceiling consolidates the receiver's own failures against ground truth."""
    rows = []
    for w in worlds:
        actions = fw.strategy_solver(w)
        rows.append({
            "world_id": w["world_id"], "world_seed": w["seed"],
            "watermark": w["watermark"], "tier": w["tier"],
            "parse_ok": True, "actions": actions, "correct": True,
            "violation": None, "reason": "ok", "steps": len(actions),
            "synthetic": True,
        })
    return rows


def compile_arm_lessons(worlds: list[dict], trajectories: list[dict], *,
                        failure_trajectories=None,
                        contrast_framing: str = "observed") -> dict:
    """Typed lessons (prereg §2 three layers) + trajectory-derived contrast.

    lessons: per-world ground-truth fact/workflow/norm (fw.compile_lessons).
    contrast: (enforce; avoid) pairs, kept only for worlds with BOTH a success
    in `trajectories` AND a classified failure in `failure_trajectories`
    (default: the same pool) — MemCollab-style success/failure contrast."""
    traj_by_wm: dict[str, list] = {}
    for t in trajectories:
        traj_by_wm.setdefault(t["watermark"], []).append(t)
    fail_by_wm: dict[str, list] = {}
    for t in (trajectories if failure_trajectories is None
              else failure_trajectories):
        fail_by_wm.setdefault(t["watermark"], []).append(t)
    lessons: list[dict] = []
    contrast: list[dict] = []
    for w in worlds:
        wm = w["watermark"]
        gt = w["lessons"]
        for i, fact in enumerate(gt["fact"]):
            lessons.append(_lesson(f"{w['world_id']}-{wm[:8]}-fact-{i}",
                                   "fact", text=fact["text"], sources=[wm]))
        lessons.append(_lesson(f"{w['world_id']}-{wm[:8]}-workflow",
                               "workflow", text=gt["workflow"]["text"],
                               sources=[wm]))
        lessons.append(_lesson(f"{w['world_id']}-{wm[:8]}-norm", "norm",
                               enforce=gt["norm"]["enforce"],
                               avoid=gt["norm"]["avoid"], sources=[wm]))
        if not any(t["correct"] for t in traj_by_wm.get(wm, [])):
            continue  # no success evidence -> no contrast support here
        modes: dict[str, str] = {}
        for t in fail_by_wm.get(wm, []):
            mode = classify_failure(w, t)
            if mode is not None and mode not in modes:
                modes[mode] = t["reason"]
        for mode in sorted(modes):
            contrast.append(_contrast_lesson(w, mode, modes[mode],
                                             framing=contrast_framing))
    return {"lessons": lessons, "contrast": contrast}


# ------------------------------------------------------- (c) abstraction
def _world_tokens(worlds: list[dict]) -> list[tuple[str, str]]:
    toks = []
    for w in worlds:
        toks.append((f"the {w['world_name']}", "the foundry"))
        toks.append((w["world_name"], "the foundry"))
        toks.append((f"the {w['relic']}", "the relic"))
        toks.append((w["relic"], "the relic"))
        for item in w["items"]:
            toks.append((item, "each ore"))
    toks.sort(key=lambda tr: -len(tr[0]))  # longest first (phrase before word)
    return toks


def _abstract_text(text: str, toks: list[tuple[str, str]]) -> str:
    for tok, repl in toks:
        text = re.sub(r"\b" + re.escape(tok) + r"\b", repl, text)
    # world-specific numeric mechanic parameters -> generic references
    text = re.sub(r"within the next \d+ actions", "within the drain window", text)
    text = re.sub(r"more than \d+ actions", "more than the drain window allows",
                  text)
    return text


def abstract_lessons(lessons: list[dict], worlds: list[dict]) -> list[dict]:
    """(c) abstracted: programmatic task-agnostic rewrite of donor lessons.

    Per-ore order facts are DROPPED (world-specific by construction); generic
    mechanic facts, the workflow layer (= the planted-strategy statement,
    already world-agnostic) and the norm layer are kept with world tokens
    stripped; identical texts dedupe with merged provenance.  Fail-closed: a
    surviving world token is an ArmsError."""
    toks = _world_tokens(worlds)
    by_wm = {w["watermark"]: w for w in worlds}
    all_items = {item for w in worlds for item in w["items"]}
    out: list[dict] = []
    seen: dict[tuple, dict] = {}

    def push(kind, *, text="", enforce=None, avoid=None, sources):
        key = (kind, text, enforce, avoid)
        if key in seen:
            tgt = seen[key]
            for s in sources:
                if s not in tgt["sources"]:
                    tgt["sources"].append(s)
            return
        lesson = _lesson(f"abstracted-{kind}-{len(out)}", kind, text=text,
                         enforce=enforce, avoid=avoid, sources=list(sources))
        seen[key] = lesson
        out.append(lesson)

    for lesson in lessons:
        if lesson["kind"] == "fact":
            if any(re.search(r"\b" + re.escape(i) + r"\b", lesson["text"])
                   for i in all_items):
                continue  # per-ore order facts cannot generalize
            push("fact", text=_abstract_text(lesson["text"], toks),
                 sources=lesson["sources"])
        elif lesson["kind"] == "workflow":
            for s in lesson["sources"]:
                if s in by_wm:
                    push("workflow",
                         text=by_wm[s]["planted_strategy"]["statement"],
                         sources=lesson["sources"])
        elif lesson["kind"] == "norm":
            push("norm",
                 enforce=_abstract_text(lesson["enforce"] or "", toks),
                 avoid=_abstract_text(lesson["avoid"] or "", toks),
                 sources=lesson["sources"])
    for lesson in out:  # fail-closed purity check
        blob = " ".join(p for p in (lesson["text"], lesson["enforce"],
                                    lesson["avoid"]) if p)
        for w in worlds:
            for tok in (w["world_name"], w["relic"], *w["items"]):
                if re.search(r"\b" + re.escape(tok) + r"\b", blob):
                    raise ArmsError(
                        f"abstraction leak: {tok!r} survives in "
                        f"{lesson['lesson_id']}")
    return out


# ------------------------------------------------------- (f) placebo store
# unrelated-domain content (household/craft tips), zero foundry vocabulary;
# format identical to real lessons (fact tips / workflow advice / enforce;
# avoid norms), comparable length.  Content-word disjointness vs the real
# lesson corpus is asserted in tests/test_f3v2_arms.py.
PLACEBO_FACTS = (
    "When brewing green tea, steep the leaves briefly in water under eighty "
    "degrees and discard the initial rinse to keep the flavor clear.",
    "Before repotting a fern, loosen the outer roots gently and choose a pot "
    "slightly wider than its previous home.",
    "To quiet a bicycle chain, wipe it dry after wet rides and apply a small "
    "drop of lubricant onto every link, then spin the pedals slowly.",
    "When tuning a guitar by ear, match the fifth fret of each string "
    "against the open string beneath it, except the third.",
    "For a crisp bread crust, bring the oven to temperature early and lay a "
    "shallow tray of water on the lower rack during baking.",
    "When sketching a portrait, begin with the gap between the eyes and "
    "gauge every later measurement against that single unit.",
    "To season a wooden board, rub food-safe oil along the grain, let it "
    "soak overnight, and buff away the excess.",
    "When labeling pantry jars, write the packing date on every lid and "
    "rotate older stock toward the front.",
)
PLACEBO_WORKFLOWS = (
    "Proceed patiently through one stage at a stretch: complete what lies in "
    "front of you, tidy the bench, then move along.",
    "Handle each garden bed separately: weed thoroughly, water deeply, mulch "
    "lightly, and only then attend the neighboring bed.",
)
PLACEBO_NORMS = (
    ("enforce: double-check each measurement twice against a known reference",
     "avoid: rushing the closing check; avoid: guessing a reading from "
     "recollection"),
    ("enforce: label every container the day it is packed",
     "avoid: leaving lids loose; avoid: trusting memory over a fresh tag"),
    ("enforce: sharpen blades lightly and often rather than waiting for them "
     "to dull",
     "avoid: storing tools damp; avoid: oiling over rust"),
    ("enforce: gather ingredients fully before lighting the stove",
     "avoid: salting early; avoid: crowding the pan"),
)

FOUNDRY_VERB_RE = re.compile(
    r"\b(cleanse|heat|charge|inscribe|blast|fuse|fusing|primed|tainted|"
    r"crucible)\b", re.IGNORECASE)

# function words + format markers, excluded from the content-word disjointness
# check (placebo vs real lessons).  Format markers (enforce/avoid) are shared
# BY DESIGN — the placebo arm must keep the identical lesson format.
PLACEBO_STOPWORDS = frozenset(
    "a an the and or but if then else of to in on for with without at by from "
    "up down over under after before between among into out off about above "
    "across along around during through per as so such is are was were be "
    "been being has have had do does did done can could may might must shall "
    "should will would not no never always only just also too very more most "
    "less least much many few any all each every some none one two three "
    "first second third last next same other another own it its he she they "
    "them their we our you your i me my who what which how when where why "
    "again once twice now still yet already soon later back away here "
    "there this that these those than then thus hence therefore however "
    "though although because while until unless instead rather quite even "
    "ever perhaps maybe almost nearly hardly barely simply merely enough "
    "s re ll ve don t "
    "enforce avoid lesson lessons fact workflow norm contrast".split())


def build_placebo_lessons(worlds: list[dict]) -> list[dict]:
    """(f) placebo: identical format, unrelated content, one set per train
    world (deterministic pick by world watermark).  Purity is fail-closed."""
    out: list[dict] = []
    for w in worlds:
        wm = w["watermark"]
        h = int(wm[:8], 16)
        i, j = h % len(PLACEBO_FACTS), (h // 3 + 1) % len(PLACEBO_FACTS)
        if i == j:
            j = (j + 1) % len(PLACEBO_FACTS)
        enforce, avoid = PLACEBO_NORMS[h % len(PLACEBO_NORMS)]
        pid = f"placebo-{w['world_id']}-{wm[:8]}"
        out.append(_lesson(f"{pid}-fact-0", "fact",
                           text=PLACEBO_FACTS[i], sources=[wm]))
        out.append(_lesson(f"{pid}-fact-1", "fact",
                           text=PLACEBO_FACTS[j], sources=[wm]))
        out.append(_lesson(f"{pid}-workflow", "workflow",
                           text=PLACEBO_WORKFLOWS[h % len(PLACEBO_WORKFLOWS)],
                           sources=[wm]))
        out.append(_lesson(f"{pid}-norm", "norm", enforce=enforce,
                           avoid=avoid, sources=[wm]))
    for lesson in out:
        blob = " ".join(p for p in (lesson["text"], lesson["enforce"],
                                    lesson["avoid"]) if p)
        if FOUNDRY_VERB_RE.search(blob):
            raise ArmsError(
                f"placebo purity violation: foundry verb in {lesson['lesson_id']}")
    return out


# ------------------------------------------------------- disagreement gate
def disagreement_flags(worlds: list[dict], donor_trajs: list[dict],
                       receiver_trajs: list[dict]) -> dict:
    """world flagged <=> receiver FAILED the train world while the donor
    SUCCEEDED on it (Agent KB: gate가 전이 성립 조건 — only then does donor
    knowledge transfer something the receiver demonstrably lacks)."""
    don_ok: dict[str, bool] = {}
    for t in donor_trajs:
        don_ok[t["watermark"]] = don_ok.get(t["watermark"], False) or t["correct"]
    rec_ok: dict[str, bool] = {}
    for t in receiver_trajs:
        rec_ok[t["watermark"]] = rec_ok.get(t["watermark"], False) or t["correct"]
    return {w["watermark"]: (not rec_ok.get(w["watermark"], False))
            and don_ok.get(w["watermark"], False) for w in worlds}


def build_lesson_sets(train_worlds: list[dict], donor_trajs: list[dict],
                      receiver_trajs: list[dict]) -> dict:
    """All arm pools + the disagreement map, from the two train experiences.

    b_self (ceiling) = typed lessons of the worlds the receiver experienced
    PLUS self-contrast pairs: the receiver's OWN observed failure modes
    distilled against ground-truth winnability (synthetic successes — one
    attempt per world makes a receiver-only success/failure contrast
    structurally empty; the ceiling is the perfect consolidation of the
    receiver's own experience, framed "from your own failed attempt" so the
    (d) and (e) contexts stay textually distinct)."""
    flags = disagreement_flags(train_worlds, donor_trajs, receiver_trajs)
    don = compile_arm_lessons(train_worlds, donor_trajs)
    con = compile_arm_lessons(
        train_worlds, donor_trajs,
        failure_trajectories=list(donor_trajs) + list(receiver_trajs))["contrast"]
    rec = compile_arm_lessons(train_worlds, receiver_trajs)
    self_contrast = compile_arm_lessons(
        train_worlds, ground_truth_trajectories(train_worlds),
        failure_trajectories=receiver_trajs,
        contrast_framing="own")["contrast"]
    pools = {
        "naive": don["lessons"],
        "abstracted": abstract_lessons(don["lessons"], train_worlds),
        "contrast": con,
        "b_self": rec["lessons"] + self_contrast,
        "placebo": build_placebo_lessons(train_worlds),
        "disagreement": flags,
    }
    for name, pool in pools.items():
        if name == "disagreement":
            continue
        for lesson in pool:
            lesson["flagged"] = any(flags.get(s, False)
                                    for s in lesson["sources"])
    return pools


# ---------------------------------------------------------------- embedding
_TOKEN_RE = re.compile(r"[a-z0-9]+")


class HashEmbedder:
    """Deterministic offline embedder (MemDelta: FIXED across arms):
    token-hashed bag-of-words — sha256(token) -> bucket, L2-normalized —
    scored with cosine.  No model, no network, bit-stable across runs."""

    name = "hash-bow-sha256-v1"

    def __init__(self, dim: int = 256):
        self.dim = dim

    def __call__(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for tok in _TOKEN_RE.findall(text.casefold()):
            digest = hashlib.sha256(tok.encode("utf-8")).digest()
            vec[int.from_bytes(digest[:8], "big") % self.dim] += 1.0
        norm = math.sqrt(sum(x * x for x in vec))
        if norm:
            vec = [x / norm for x in vec]
        return vec


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _lesson_embed_text(lesson: dict) -> str:
    return " ".join(p for p in (lesson["text"], lesson["enforce"],
                                lesson["avoid"]) if p)


def retrieve_lessons(query_text: str, lessons: list[dict], embedder,
                     top_k: int = TOP_K) -> list[dict]:
    """Top-k lessons by embedding similarity (score desc, lesson_id asc —
    fully deterministic under ties)."""
    if not lessons or top_k <= 0:
        return []
    q = embedder(query_text)
    scored = [(cosine(q, embedder(_lesson_embed_text(lesson))),
               lesson["lesson_id"], lesson) for lesson in lessons]
    scored.sort(key=lambda s: (-s[0], s[1]))
    return [lesson for _score, _lid, lesson in scored[:top_k]]


def _rules_text(world: dict) -> str:
    return "\n".join(r["text"] for r in world["rules"])


# ---------------------------------------------------------------- arms
def render_lesson_block(lessons: list[dict]) -> str:
    """The injected memory context.  ONE format for every arm (placebo parity
    requires byte-identical scaffolding; only the content differs)."""
    lines = ["Experience notes from prior work in other workshops (apply "
             "what transfers; the ores and orders differ here):"]
    for i, lesson in enumerate(lessons, start=1):
        if lesson["kind"] in ("norm", "contrast"):
            body = f"{lesson['enforce']} || {lesson['avoid']}"
        else:
            body = lesson["text"]
        lines.append(f"{i}. [{lesson['kind']}] {body}")
    return "\n".join(lines)


def build_arm_prompt(arm_id: str, world: dict, lesson_sets: dict, *,
                     embedder=None, top_k: int = TOP_K) -> str:
    """The receiver's augmented prompt for a test world under one arm."""
    base = fw.render_prompt(world)
    if arm_id == "a_no_memory":
        return base
    if arm_id == "x_xvendor":
        raise NotImplementedError(
            "xvendor arm deferred (prereg §8): no non-Qwen receiver is "
            "available; same-family confound stays a documented caveat")
    gated = arm_id.endswith("_gated")
    base_arm = arm_id[:-len("_gated")] if gated else arm_id
    if gated and base_arm in GATE_INVARIANT_ARMS:
        raise ArmsError(f"arm {base_arm} is gate-invariant; no _gated variant")
    pool_name = ARM_POOLS.get(base_arm)
    if pool_name is None:
        raise ArmsError(f"unknown arm {arm_id!r}")
    lessons = lesson_sets[pool_name]
    if gated:  # gate ON: only disagreement-flagged lessons transfer
        lessons = [lesson for lesson in lessons if lesson["flagged"]]
    embedder = embedder or HashEmbedder()
    retrieved = retrieve_lessons(_rules_text(world), lessons, embedder, top_k)
    if not retrieved:
        return base
    return render_lesson_block(retrieved) + "\n\n" + base


def evaluate_arms(chat, model: str, test_worlds: list[dict],
                  arm_ids, lesson_sets: dict, *, embedder=None, seed: int,
                  max_tokens: int, system: str = SYSTEM_PROMPT) -> dict:
    """Score the receiver on test worlds under each arm context (paired:
    every arm attempts the same worlds)."""
    embedder = embedder or HashEmbedder()
    out = {}
    for arm in arm_ids:
        rows = run_experience(
            chat, model, test_worlds, seed=seed, max_tokens=max_tokens,
            system=system,
            prompt_fn=lambda w, a=arm: build_arm_prompt(
                a, w, lesson_sets, embedder=embedder))
        out[arm] = {"arm_id": arm, "n": len(rows),
                    "n_correct": sum(r["correct"] for r in rows),
                    "accuracy": accuracy(rows), "rows": rows}
    return out


# ---------------------------------------------------------------- TRR
def _r4(x):
    return round(x, 4) if x is not None else None


def _trr_entry(arm: str, vec: list[int], nm: list[int], bs: list[int]) -> dict:
    n = len(vec)
    acc = sum(vec) / n if n else None
    m = sum(nm) / n if n else None
    b = sum(bs) / n if n else None
    degenerate = m is None or b is None or b == m
    trr = None if degenerate or acc is None else (acc - m) / (b - m)
    ntr = (sum(1 for x, y in zip(vec, nm) if x < y) / n) if n else None
    return {"arm": arm, "n": n, "acc": _r4(acc), "no_mem_acc": _r4(m),
            "b_self_acc": _r4(b), "trr": _r4(trr), "degenerate": degenerate,
            "negative_transfer_rate": _r4(ntr),
            "scores": {"arm": list(vec), "no_mem": list(nm),
                       "b_self": list(bs)}}


def trr_table(results: dict, *, no_mem: str = "a_no_memory",
              b_self: str = "e_b_self") -> dict:
    """TRR = (arm - no_mem) / (b_self - no_mem) per tier, paired per world.

    Degenerate case (b_self == no_mem): trr null + degenerate=True — never a
    divide-by-zero.  Pairing is fail-closed: every arm must attempt the same
    worlds in the same order."""
    for required in (no_mem, b_self):
        if required not in results:
            raise ArmsError(f"trr_table needs arm {required!r}")
    ref = [r["world_id"] for r in results[no_mem]["rows"]]
    for arm, res in results.items():
        ids = [r["world_id"] for r in res["rows"]]
        if ids != ref:
            raise ArmsError(
                f"arm {arm} worlds not paired with {no_mem} "
                f"({len(ids)} vs {len(ref)} rows)")
    tiers = sorted({r["tier"] for r in results[no_mem]["rows"]})
    out: dict[str, dict] = {}
    for tier in tiers:
        def vec(arm):
            return [int(r["correct"]) for r in results[arm]["rows"]
                    if r["tier"] == tier]
        nm, bs = vec(no_mem), vec(b_self)
        out[tier] = {arm: _trr_entry(arm, vec(arm), nm, bs)
                     for arm in results}
    return out


# ---------------------------------------------------------------- kills
def paired_bootstrap_diff(a: list, b: list, *, reps: int = BOOT_REPS,
                          seed: int = 20260726) -> dict:
    """Paired bootstrap CI of mean(a - b): resample world indices with
    replacement, percentile interval [2.5%, 97.5%], pinned seed."""
    if len(a) != len(b) or not a:
        raise ArmsError("paired_bootstrap_diff needs equal non-empty vectors")
    rng = random.Random(f"f3v2-boot:{seed}")
    n = len(a)
    diffs = [x - y for x, y in zip(a, b)]
    stats = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n
                   for _ in range(reps))
    lo = stats[int(0.025 * reps)]
    hi = stats[min(int(0.975 * reps), reps - 1)]
    return {"mean_diff": _r4(sum(diffs) / n), "ci95": [_r4(lo), _r4(hi)],
            "reps": reps, "seed": seed, "n": n}


def eval_k1_env_kill(*, trr_contrast, trr_abstracted, b_self_acc) -> dict:
    """K1 (prereg §5): TRR_c <= 0 AND TRR_d <= 0 (hard) AND b_self >= 0.60
    -> capability axis absent, testbed redesign.  'B-self ZS' is read as the
    arm-(e) accuracy: self-lessons provably move the receiver, so donor
    transfer failure indicts the environment, not the lesson format."""
    evaluable = trr_contrast is not None and trr_abstracted is not None
    fired = (evaluable and trr_contrast <= 0 and trr_abstracted <= 0
             and b_self_acc is not None and b_self_acc >= K1_B_SELF_MIN)
    return {"kill": "k1_env_kill", "fired": bool(fired),
            "evaluable": evaluable,
            "values": {"trr_contrast": trr_contrast,
                       "trr_abstracted": trr_abstracted,
                       "b_self_acc": b_self_acc,
                       "b_self_min": K1_B_SELF_MIN},
            "note": "mechanical observation only; sealed judgment is the gate's"}


def eval_k2_claim_kill(*, naive_trr, contrast_scores, naive_scores,
                       abstracted_scores, reps: int = BOOT_REPS,
                       seed: int = 20260726) -> dict:
    """K2 (prereg §5): naive TRR < 0 AND neither contrast nor abstracted beats
    naive by paired bootstrap 95% CI (LCB of the paired diff > 0 required)
    -> typed store indistinguishable from naive, claim ② shelve."""
    boot_c = paired_bootstrap_diff(contrast_scores, naive_scores,
                                   reps=reps, seed=seed)
    boot_a = paired_bootstrap_diff(abstracted_scores, naive_scores,
                                   reps=reps, seed=seed)
    c_beats = boot_c["ci95"][0] > 0
    a_beats = boot_a["ci95"][0] > 0
    evaluable = naive_trr is not None
    fired = evaluable and naive_trr < 0 and not c_beats and not a_beats
    return {"kill": "k2_claim_kill", "fired": bool(fired),
            "evaluable": evaluable,
            "values": {"naive_trr": naive_trr,
                       "contrast_minus_naive": boot_c,
                       "abstracted_minus_naive": boot_a,
                       "contrast_beats_naive": c_beats,
                       "abstracted_beats_naive": a_beats},
            "note": "mechanical observation only; sealed judgment is the gate's"}


def eval_k3_priming_kill(*, trr_placebo, trr_abstracted) -> dict:
    """K3 (prereg §5): TRR_placebo >= TRR_abstracted - 0.1 -> the lift is
    generic priming, 'transfer' naming forbidden."""
    evaluable = trr_placebo is not None and trr_abstracted is not None
    fired = (evaluable
             and trr_placebo >= trr_abstracted - K3_PLACEBO_SLACK)
    return {"kill": "k3_priming_kill", "fired": bool(fired),
            "evaluable": evaluable,
            "values": {"trr_placebo": trr_placebo,
                       "trr_abstracted": trr_abstracted,
                       "slack": K3_PLACEBO_SLACK},
            "note": "mechanical observation only; sealed judgment is the gate's"}


KILLS_NOT_APPLICABLE = {
    "k4_judge_kill": {
        "kill": "k4_judge_kill", "fired": False, "applicable": False,
        "note": ("N/A in simulator-scored F3v2: there is no LLM judge panel "
                 "whose planted-wrong-answer catch rate could be measured; "
                 "reinstated only if a judge-scored variant is added "
                 "(prereg §7 step 2 covers the sealed judge track).")},
    "k5_noise_floor_kill": {
        "kill": "k5_noise_floor_kill", "fired": False, "applicable": False,
        "note": ("N/A in simulator-scored F3v2: gold ground truth is planted "
                 "by construction (annotation error rate 0), so a "
                 "re-annotation noise floor cannot bind; documented, not "
                 "measured.")},
}


def evaluate_kills(tier_table: dict, *, reps: int = BOOT_REPS,
                   seed: int = 20260726) -> dict:
    """All kill observations over one tier's TRR table (the five core arms
    are required; gated variants are ablations, not kill inputs)."""
    required = ("a_no_memory", "b_naive_donor", "c_abstracted",
                "d_contrast", "e_b_self", "f_placebo")
    missing = [a for a in required if a not in tier_table]
    if missing:
        raise ArmsError(f"evaluate_kills: missing core arms {missing}")
    kills = {
        "k1_env_kill": eval_k1_env_kill(
            trr_contrast=tier_table["d_contrast"]["trr"],
            trr_abstracted=tier_table["c_abstracted"]["trr"],
            b_self_acc=tier_table["e_b_self"]["acc"]),
        "k2_claim_kill": eval_k2_claim_kill(
            naive_trr=tier_table["b_naive_donor"]["trr"],
            contrast_scores=tier_table["d_contrast"]["scores"]["arm"],
            naive_scores=tier_table["b_naive_donor"]["scores"]["arm"],
            abstracted_scores=tier_table["c_abstracted"]["scores"]["arm"],
            reps=reps, seed=seed),
        "k3_priming_kill": eval_k3_priming_kill(
            trr_placebo=tier_table["f_placebo"]["trr"],
            trr_abstracted=tier_table["c_abstracted"]["trr"]),
    }
    kills.update({k: dict(v) for k, v in KILLS_NOT_APPLICABLE.items()})
    return kills


# ---------------------------------------------------------------- receipt
def build_receipt(*, script_path, config: dict, train_worlds: list[dict],
                  test_worlds: list[dict], arm_results: dict, trr: dict,
                  kills: dict, budget_block: dict, wall_clock_s: float,
                  prereg_path=PREREG_PATH, extra: dict | None = None) -> dict:
    """Canary-gate-convention receipt: hswm-f3v2-arms-receipt/v1."""
    prereg_path = Path(prereg_path)
    if not prereg_path.exists():
        raise ArmsError(f"prereg file missing: {prereg_path}")
    harness = {}
    for name in ("f3v2_procedural_worlds.py", "f2_delta_w_credit.py",
                 "f3v2_arms.py"):
        path = HERE / name
        harness[name] = (hashlib.sha256(path.read_bytes()).hexdigest()
                         if path.exists() else None)
    tier = config.get("tier", "hard")
    worlds = []
    for split, batch in (("train", train_worlds), ("test", test_worlds)):
        for w in batch:
            worlds.append({"world_id": w["world_id"], "split": split,
                           "tier": w["tier"], "seed": w["seed"],
                           "n_items": len(w["items"]),
                           "optimal_len": w["optimal_len"],
                           "step_cap": w["step_cap"],
                           "watermark": w["watermark"],
                           "world_sha256": fw.world_sha256(w)})
    shared = sorted({fw.world_sha256(w) for w in train_worlds}
                    & {fw.world_sha256(w) for w in test_worlds})
    tt = trr.get(tier, {})
    cd = [tt[a]["trr"] for a in ("c_abstracted", "d_contrast") if a in tt]
    present = [v for v in cd if v is not None]
    receipt = {
        "schema_version": "hswm-f3v2-arms-receipt/v1",
        "mode": "development",
        "stage": "DEVELOPMENT_ONLY",
        "branch": "F3v2-harder-transfer",
        "preregistration_file": str(prereg_path),
        "preregistration_file_sha256": hashlib.sha256(
            prereg_path.read_bytes()).hexdigest(),
        "preregistration_status": (
            "DRAFT — user ratify pending; machine-lock to "
            "prom_search_hswm/evidence/PREREG_f3v2_*.json happens only after "
            "ratify"),
        "script_sha256": hashlib.sha256(
            Path(script_path).read_bytes()).hexdigest(),
        "harness_module_sha256": harness,
        "config": config,
        "split_audit": {
            "tier": tier,
            "train_seed": config.get("train_seed"),
            "test_seed": config.get("test_seed"),
            "n_train": len(train_worlds), "n_test": len(test_worlds),
            "shared_world_sha256": shared,
            "verdict": "DISJOINT" if not shared else "VOID",
            "note": ("world_id is per-seed and collides across splits by "
                     "construction; content sha256 is the split identity "
                     "(prereg §6.2 instance-disjoint)."),
        },
        "worlds": worlds,
        "arms": arm_results,
        "trr": trr,
        "judgment_target": {
            "name": f"min(trr_c_abstracted, trr_d_contrast) [{tier}]",
            "value": _r4(min(present)) if len(present) == 2 else None,
            "degenerate": len(present) < 2,
        },
        "kills": kills,
        "llm_budget": budget_block,
        "honesty": ("grounded measurement only; no scientific claim; judgment "
                    "is the gate's. DEVELOPMENT_ONLY: nothing sealed."),
        "wall_clock_s": wall_clock_s,
    }
    if extra:
        receipt.update(extra)
    return receipt


# ---------------------------------------------------------------- offline chat
class ScriptedChat:
    """Offline deterministic chat stand-in (tests / dev-smoke dry-run; NO
    network).  Exact-table routing: (model, system, user) -> action list.  A
    table miss is a hard error (fail-closed) so pipeline drift surfaces
    immediately instead of silently changing the scripted outcomes."""

    backend_name = "scripted-offline-v1"

    def __init__(self, table: dict | None = None):
        self.table = dict(table or {})
        self.misses = 0
        self.hits = 0
        self.last_http_status = None
        self.last_error_kind = None
        self.degraded_to_parallel = None

    def add(self, model: str, system: str, user: str, actions: list) -> None:
        self.table[(model, system, user)] = list(actions)

    def chat(self, *, model: str, system: str, user: str, seed: int,
             max_tokens: int, timeout: float = 0.0) -> dict:
        key = (model, system, user)
        if key not in self.table:
            raise ArmsError(
                f"ScriptedChat miss (model={model!r}): no scripted reply for "
                f"prompt {user[:80]!r}... — extend the table")
        self.misses += 1
        actions = self.table[key]
        return {
            "text": json.dumps({"actions": actions}),
            "finish_reason": "stop",
            "response_model": model,
            "usage": {"prompt_tokens": len(user) // 4,
                      "completion_tokens": 3 * len(actions)},
            "request_sha256": hashlib.sha256(json.dumps(
                {"backend": self.backend_name, "model": model,
                 "system": system, "user": user, "seed": seed,
                 "max_tokens": max_tokens}, sort_keys=True).encode()).hexdigest(),
            "cached": False,
        }
