"""F3v2 procedural-world generator — harder transfer testbed (slice 1).

PREREG (draft, sha-pinned by the canary gate):
  /Users/lagyeongjun/CD/SYMPOSIUM/HSWM/PREREG_F3V2_HARDER_TRANSFER_2026-07-26.md §2.

Design (PROM16 a2/a4 rationale, 2026-07-26): the F3 r1-r3 PhantomWiki testbed
died structurally (environment-determined semantic knowledge, G=0/S=0) because
fact-composition knowledge does not separate model capability.  The capability
axis lives in PROCEDURAL knowledge (Dynamic Cheatsheet Game-of-24: weak models
never find the solver pattern, so their memory fills with defective strategies;
In-Context Distillation: hard tier keeps the teacher/student gap).  This module
therefore generates "ritual foundry" worlds:

* hidden environment rules — "action X requires state Y first" multi-step
  procedural constraints (per-item verb ladder cleanse -> heat -> charge ->
  inscribe), PLUS hard-tier interaction rules (one-crucible cooling, primed
  drain window, reheat shatter, tainting blast shortcut);
* a planted optimal strategy per world (Game-of-24/DC-style discoverable
  solver pattern): "run each ore's full ladder ATOMICALLY, one ore at a time,
  then fuse" — robust against every interaction rule, and the strategy solver
  below achieves 100% by construction;
* typed lessons (prereg §2 three layers): (1) fact = environment rule facts,
  (2) workflow = the atomic-ladder procedure order, (3) norm = contrast rule
  "enforce atomic ladders; avoid blast / reheat / drain".

Tiers: mid (2 ores, 3-step ladder, no interaction rules — weak models should
mostly pass) and hard (4-5 ores, 4-step ladder, all interaction rules on —
designed so a weak model fails zero-shot but succeeds with the right lessons).
The ZS prompt states the bare rule FACTS only; it never states the workflow
strategy or the norms (those are exactly the (2)(3) lessons a donor must
supply).  Determinism: everything derives from random.Random(f-string seeds);
canonical JSON (sort_keys) is stable across runs.

Prereg-sanctioned difficulty retunes (prereg §2 "미달 시 난이도 재조정"):
* 2026-07-26: hard-tier ore count 3-4 -> 4-5.  Reason: canary adoption-gate
  criterion-1 miss vs the real Qwen3-4B receiver — receiver ZS hard = 50%
  (bar <= 30%), donor 100%, gap 50pp (receipt
  receipts/f3v2_canary_gate_dev_1785038688.json).  All 4 receiver failures
  were the planted cooling trap via verb-batching, so the knob that adds
  heat/charge windows (ore count) moves; drain K / cap / ladder unchanged
  (their failure modes were not observed).  Donor headroom was 100% vs the
  >= 70% floor, so modest added difficulty is safe for criterion 2.

Everything here is a DEVELOPMENT_ONLY harness component: measurements are
grounded measurements, never scientific claims; judgment belongs to the gate.
"""
from __future__ import annotations

import hashlib
import json
import random
import re

TIERS = ("mid", "hard")

LADDER_MID = ("cleanse", "heat", "charge")
LADDER_HARD = ("cleanse", "heat", "charge", "inscribe")

# precondition flag per verb (total order along the ladder)
_PRECOND = {"cleanse": None, "heat": "cleansed", "charge": "heated",
            "inscribe": "primed"}
_VERBS = ("cleanse", "heat", "charge", "inscribe", "blast")

_NAME_HEADS = ("vel", "nar", "qua", "ost", "zel", "mor", "thu", "bren", "ilo",
               "dra", "syl", "fer", "glim", "tor", "ash", "kel", "vorn", "mi")
_NAME_TAILS = ("ium", "ite", "ox", "ar", "eth", "on", "yx", "il", "um", "ane",
               "os", "ek")
_WORLD_ADJ = ("Ash", "Hollow", "Glimmer", "Pale", "Ember", "Silent", "Verdant",
              "Broken", "Lucent", "Iron")
_WORLD_NOUN = ("Crucible", "Foundry", "Forge", "Kiln", "Anvil")
_RELICS = ("Dawn Sigil", "Star Ingot", "Deep Alloy", "Sun Lattice",
           "Oath Metal", "First Coil")

_ACTION_RE = re.compile(
    r"^(?P<verb>cleanse|heat|charge|inscribe|blast)\s*\(\s*(?P<item>[a-z]+)\s*\)"
    r"$|^fuse\s*(\(\s*\))?$")

SLACK_MID = 2
SLACK_HARD = 4


class WorldError(ValueError):
    pass


# ---------------------------------------------------------------- generation
def _rng(seed: int, tier: str, world_idx: int, salt: str = "") -> random.Random:
    return random.Random(f"f3v2:{seed}:{tier}:{world_idx}:{salt}")


def _item_names(rng: random.Random, n: int) -> list[str]:
    names: set[str] = set()
    while len(names) < n:
        names.add(rng.choice(_NAME_HEADS) + rng.choice(_NAME_TAILS))
    return sorted(names)


def generate_world(*, seed: int, tier: str, world_idx: int) -> dict:
    """One deterministic foundry world (plain JSON-able dict)."""
    if tier not in TIERS:
        raise WorldError(f"unknown tier {tier!r}")
    rng = _rng(seed, tier, world_idx)
    ladder = list(LADDER_MID if tier == "mid" else LADDER_HARD)
    n_items = 2 if tier == "mid" else rng.choice((4, 5))
    items = _item_names(rng, n_items)
    constraints = {
        # heating one ore instantly cools every other heated ore (one crucible)
        "cooling": tier == "hard",
        # heating a primed ore shatters it
        "reheat_ruin": tier == "hard",
        # primed-but-not-inscribed ore drains unless inscribed within K actions
        "decay_k": None if tier == "mid" else rng.choice((3, 4)),
        # blast shortcut: instant prime but taints (fuse then fails)
        "blast_enabled": tier == "hard",
    }
    optimal_len = len(ladder) * n_items + 1  # full ladder per ore + fuse
    step_cap = optimal_len + (SLACK_MID if tier == "mid" else SLACK_HARD)
    world_name = f"{rng.choice(_WORLD_ADJ)} {rng.choice(_WORLD_NOUN)}"
    relic = rng.choice(_RELICS)

    rules = _render_rules(ladder, constraints)
    strategy = (
        "Run each ore's full ladder atomically, one ore at a time: "
        f"{' -> '.join(ladder)} on a single ore with no other ore's steps in "
        "between, then the next ore, and fuse at the very end.")
    world = {
        "schema": "hswm-f3v2-procedural-world/v1",
        "world_id": f"f3v2-{tier}-{world_idx}",
        "tier": tier,
        "seed": seed,
        "world_name": world_name,
        "relic": relic,
        "items": items,
        "ladder": ladder,
        "constraints": constraints,
        "rules": rules,
        "goal": (f"Fuse all ores into the {relic}: fuse succeeds only if "
                 f"every ore is primed"
                 + (" and inscribed" if "inscribe" in ladder else "")
                 + ", and no ore is tainted or shattered."),
        "optimal_len": optimal_len,
        "step_cap": step_cap,
        "planted_strategy": {
            "id": "atomic_item_ladders",
            "statement": strategy,
            "rationale": ("Game-of-24/Dynamic-Cheatsheet-style robust solver "
                          "pattern: any interleaving risks cooling/drain/"
                          "shatter interactions; the atomic per-ore ladder is "
                          "the discoverable policy that is always safe."),
        },
    }
    world["lessons"] = compile_lessons(world)
    world["watermark"] = hashlib.sha256(
        canonical_world_json(world).encode()).hexdigest()[:16]
    return world


def _render_rules(ladder: list[str], constraints: dict) -> list[dict]:
    rules = [
        {"id": "r_cleanse", "kind": "fact",
         "text": "cleanse(X) is always possible and makes X cleansed."},
        {"id": "r_heat", "kind": "fact",
         "text": "heat(X) is only possible if X is cleansed; it makes X heated."},
        {"id": "r_charge", "kind": "fact",
         "text": ("charge(X) is only possible if X is heated right now; it "
                  "makes X primed and consumes the heat (X is no longer heated).")},
    ]
    if "inscribe" in ladder:
        rules.append({"id": "r_inscribe", "kind": "fact",
                      "text": ("inscribe(X) is only possible if X is primed; "
                               "inscription locks the charge — X stays primed "
                               "and inscribed and can no longer drain.")})
    if constraints["cooling"]:
        rules.append({"id": "r_cooling", "kind": "fact",
                      "text": ("Heating one ore instantly cools every other ore "
                               "(all other ores stop being heated): the crucible "
                               "holds heat for one ore at a time.")})
    if constraints["decay_k"] is not None:
        rules.append({"id": "r_drain", "kind": "fact",
                      "text": (f"A primed ore that is not inscribed within the "
                               f"next {constraints['decay_k']} actions drains: "
                               "it loses primed and heated and must be heated "
                               "and charged again.")})
    if constraints["reheat_ruin"]:
        rules.append({"id": "r_shatter", "kind": "fact",
                      "text": ("Heating a primed ore shatters it; a shattered "
                               "ore can never be used again.")})
    if constraints["blast_enabled"]:
        rules.append({"id": "r_blast", "kind": "fact",
                      "text": ("blast(X) instantly makes X primed without "
                               "cleansing or heating, but X becomes tainted.")})
    return rules


def generate_batch(n_worlds: int, tier: str, seed: int) -> list[dict]:
    return [generate_world(seed=seed, tier=tier, world_idx=i)
            for i in range(n_worlds)]


def canonical_world_json(world: dict) -> str:
    return json.dumps(world, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def world_sha256(world: dict) -> str:
    return hashlib.sha256(canonical_world_json(world).encode()).hexdigest()


# ---------------------------------------------------------------- lessons
def compile_lessons(world: dict) -> dict:
    """Typed lessons, prereg §2 three layers: fact / workflow / norm."""
    lid = f"f3v2-{world['tier']}-{world['world_id'].rsplit('-', 1)[-1]}"
    facts = [f"In the {world['world_name']}, {r['text'][0].lower() + r['text'][1:]}"
             for r in world["rules"]]
    ladder_txt = " -> ".join(world["ladder"])
    workflow = (
        f"Optimal procedure for the {world['world_name']}: prime each ore "
        f"completely before touching the next one. For one ore run "
        f"{ladder_txt} back-to-back with no other ore's steps in between; "
        f"then do the same for the next ore; call fuse only at the very end. "
        f"Never batch one verb across ores and never interleave two ores' "
        f"ladders.")
    enforce = (f"enforce: finish one ore's full ladder ({ladder_txt}) "
               "atomically before starting the next ore")
    avoid = []
    if world["constraints"]["blast_enabled"]:
        avoid.append("blast-fusing (it taints the ore and the final fuse then "
                     "fails no matter how many steps it saves)")
    if world["constraints"]["reheat_ruin"]:
        avoid.append("re-heating a primed ore (it shatters and the world "
                     "becomes unwinnable)")
    if world["constraints"]["decay_k"] is not None:
        avoid.append(f"letting a primed ore sit more than "
                     f"{world['constraints']['decay_k']} actions before "
                     "inscribing (it drains and the work must be redone)")
    if not avoid:
        avoid.append("nothing beyond respecting the precondition order")
    return {
        "fact": [{"lesson_id": f"{lid}-fact-{i}", "type": "fact", "text": t}
                 for i, t in enumerate(facts)],
        "workflow": {"lesson_id": f"{lid}-workflow", "type": "workflow",
                     "text": workflow},
        "norm": {"lesson_id": f"{lid}-norm", "type": "norm",
                 "enforce": enforce, "avoid": "; ".join("avoid: " + a for a in avoid)},
    }


# ---------------------------------------------------------------- simulation
def _initial_state(world: dict) -> dict:
    return {item: {"cleansed": False, "heated": False, "primed": False,
                   "inscribed": False, "tainted": False, "ruined": False,
                   "primed_age": None}
            for item in world["items"]}


def simulate(world: dict, actions: list[str]) -> dict:
    """Run an action sequence; return {ok, fused, violation, reason, steps}.

    First rule breach stops the run (strict scoring).  fuse is terminal:
    success requires a valid fuse as the last meaningful action.
    """
    items = _initial_state(world)
    constraints = world["constraints"]
    ladder = world["ladder"]
    if not actions:
        return _fail(0, "empty", "no actions given")
    if len(actions) > world["step_cap"]:
        return _fail(0, "cap",
                     f"{len(actions)} actions exceeds step cap {world['step_cap']}")
    fused = False
    for step, raw in enumerate(actions):
        # drain tick at the START of the step (ore must be inscribed within
        # decay_k actions *after* the one that primed it)
        k = constraints["decay_k"]
        if k is not None:
            for name, st in items.items():
                if st["primed"] and not st["inscribed"]:
                    st["primed_age"] = (st["primed_age"] or 0) + 1
                    if st["primed_age"] > k:
                        st["primed"] = False
                        st["heated"] = False
                        st["primed_age"] = None  # drained; re-heatable
        action = " ".join(str(raw).strip().casefold().split())
        m = _ACTION_RE.match(action)
        if not m:
            return _fail(step, "malformed", f"cannot parse action {raw!r}")
        if fused:
            return _fail(step, "after_fuse", "actions continue after fuse")
        if m.group("verb") is None:  # fuse
            bad = [n for n, st in items.items()
                   if not (st["primed"]
                           and (st["inscribed"] or "inscribe" not in ladder)
                           and not st["tainted"] and not st["ruined"])]
            if bad:
                return _fail(step, "fuse_rejected",
                             f"fuse fails: ores not ready or tainted/shattered: {bad}")
            fused = True
            continue
        verb, item = m.group("verb"), m.group("item")
        if item not in items:
            return _fail(step, "unknown_item", f"unknown ore {item!r}")
        st = items[item]
        if st["ruined"]:
            return _fail(step, "ruined", f"{item} is shattered")
        if verb == "blast":
            if not constraints["blast_enabled"]:
                return _fail(step, "unavailable", "blast is not available in this world")
            st["primed"] = True
            st["tainted"] = True
            st["primed_age"] = 0
        else:
            if verb not in ladder:
                return _fail(step, "unavailable", f"{verb} is not used in this world")
            req = _PRECOND[verb]
            if req is not None and not st[req]:
                return _fail(step, "precondition",
                             f"{verb}({item}) requires {req}")
            if verb == "heat" and st["primed"] and constraints["reheat_ruin"]:
                return _fail(step, "shattered",
                             f"heating primed {item} shatters it")
            if verb == "cleanse":
                st["cleansed"] = True
            elif verb == "heat":
                st["heated"] = True
                if constraints["cooling"]:
                    for other, ost in items.items():
                        if other != item:
                            ost["heated"] = False
            elif verb == "charge":
                st["primed"] = True
                st["heated"] = False
                st["primed_age"] = 0
            elif verb == "inscribe":
                st["inscribed"] = True
                st["primed_age"] = None
    if not fused:
        return _fail(len(actions), "no_fuse", "sequence ends without a successful fuse")
    return {"ok": True, "fused": True, "violation": None, "reason": "ok",
            "steps": len(actions)}


def _fail(step: int, violation: str, reason: str) -> dict:
    return {"ok": False, "fused": False, "violation": violation,
            "reason": reason, "steps": step}


def verify_solution(world: dict, actions: list[str]) -> tuple[bool, str]:
    sim = simulate(world, actions)
    return sim["ok"], sim["reason"]


# ---------------------------------------------------------------- solvers
def strategy_solver(world: dict) -> list[str]:
    """The planted optimal strategy: atomic per-ore ladders, then fuse.

    Always valid by construction (preconditions hold sequentially; cooling is
    irrelevant because each ore is charged immediately after its own heating;
    inscription happens inside the drain window; blast/reheat never used).
    """
    actions = [f"{verb}({item})" for item in sorted(world["items"])
               for verb in world["ladder"]]
    return actions + ["fuse"]


def naive_batch_solver(world: dict) -> list[str]:
    """Verb-batching baseline (group by verb): what a weak planner emits."""
    actions = [f"{verb}({item})" for verb in world["ladder"]
               for item in sorted(world["items"])]
    return actions + ["fuse"]


def blast_solver(world: dict) -> list[str]:
    """Shortcut-taking baseline: blast every ore, then fuse (taints -> fail)."""
    return [f"blast({item})" for item in sorted(world["items"])] + ["fuse"]


# ---------------------------------------------------------------- prompting
def render_prompt(world: dict) -> str:
    """Zero-shot task prompt: bare rule FACTS only — never the strategy/norms."""
    verbs = ", ".join(f"{v}(ore)" for v in world["ladder"])
    if world["constraints"]["blast_enabled"]:
        verbs += ", blast(ore)"
    verbs += ", fuse"
    rules_txt = "\n".join(f"{i}. {r['text']}" for i, r in
                          enumerate(world["rules"], start=1))
    return (
        f"You are operating a ritual foundry in the {world['world_name']}.\n\n"
        f"Ores: {', '.join(world['items'])}.\n"
        f"Goal: {world['goal']}\n\n"
        f"World rules:\n{rules_txt}\n\n"
        f"Available actions: {verbs}.\n"
        f"Write actions as verb(ore), for example cleanse({world['items'][0]}); "
        f"fuse takes no argument and must be the final action.\n"
        f"You have at most {world['step_cap']} actions.\n\n"
        f"Reply with JSON only: {{\"actions\": [\"...\", ..., \"fuse\"]}}.")


def parse_model_actions(text: str) -> list[str] | None:
    """Extract the actions list from a model reply (JSON object expected)."""
    if not text:
        return None
    obj = None
    try:
        obj = json.loads(text)
    except (ValueError, TypeError):
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                obj = json.loads(m.group(0))
            except (ValueError, TypeError):
                obj = None
    if not isinstance(obj, dict):
        return None
    actions = obj.get("actions")
    if not isinstance(actions, list) or not all(isinstance(a, str) for a in actions):
        return None
    return [a.strip().casefold() for a in actions]
