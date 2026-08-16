"""Tests for the F3v2 harder-transfer testbed slice 1 (procedural worlds).

Covers prereg §2 invariants: deterministic seed-pinned generation, planted
strategy solvability (100% by construction), and hard/mid tier separation
(the planted strategy is necessary on hard tier — verb-batching and the
blast shortcut must fail there while passing on mid).
"""
from __future__ import annotations

from _research.f_series import f3v2_procedural_worlds as fw

SEEDS = (1, 7, 20260726, 424242)


def _worlds(tier, seeds=SEEDS, per_seed=3):
    return [w for s in seeds for w in fw.generate_batch(per_seed, tier, s)]


# ------------------------------------------------------------- determinism
def test_same_seed_same_worlds():
    a = fw.generate_batch(4, "hard", 123)
    b = fw.generate_batch(4, "hard", 123)
    assert [fw.canonical_world_json(w) for w in a] == \
           [fw.canonical_world_json(w) for w in b]
    assert [fw.world_sha256(w) for w in a] == [fw.world_sha256(w) for w in b]


def test_different_seed_different_worlds():
    a = fw.generate_batch(4, "hard", 123)
    b = fw.generate_batch(4, "hard", 124)
    assert [fw.canonical_world_json(w) for w in a] != \
           [fw.canonical_world_json(w) for w in b]


def test_world_is_json_serializable_and_watermarked():
    for w in _worlds("hard") + _worlds("mid"):
        assert fw.canonical_world_json(w)  # json.dumps round-trip
        assert len(w["watermark"]) == 16
        assert w["schema"] == "hswm-f3v2-procedural-world/v1"


# ------------------------------------------- planted-strategy solvability
def test_strategy_solver_achieves_100pct_by_construction():
    for w in _worlds("hard") + _worlds("mid"):
        ok, reason = fw.verify_solution(w, fw.strategy_solver(w))
        assert ok, f"{w['world_id']}: planted strategy failed: {reason}"


def test_strategy_solver_is_optimal_length_and_within_cap():
    for w in _worlds("hard") + _worlds("mid"):
        actions = fw.strategy_solver(w)
        assert len(actions) == w["optimal_len"]
        assert len(actions) <= w["step_cap"]


# --------------------------------------------------------- tier separation
def test_tier_shapes():
    for w in _worlds("mid"):
        assert len(w["items"]) == 2
        assert w["ladder"] == ["cleanse", "heat", "charge"]
        assert all(order == w["ladder"] for order in w["ladders"].values())
        assert w["constraints"]["cooling"] is False
        assert w["constraints"]["blast_enabled"] is False
        assert w["constraints"]["decay_k"] is None
        assert w["constraints"]["per_ore_orders"] is False
    for w in _worlds("hard"):
        assert len(w["items"]) in (4, 5)  # retuned 3-4 -> 4-5, 2026-07-26
        assert w["ladder"] == ["cleanse", "heat", "charge", "inscribe"]
        assert w["constraints"]["cooling"] is True
        assert w["constraints"]["blast_enabled"] is True
        assert w["constraints"]["reheat_ruin"] is True
        assert w["constraints"]["decay_k"] in (3, 4)
        assert w["constraints"]["per_ore_orders"] is True
        assert w["optimal_len"] > 16  # meaningfully deeper than mid (7)
        # mechanism lever 2026-07-26 (b): per-ore non-uniform orders
        orders = list(w["ladders"].values())
        assert len(orders) == len(w["items"])
        for order in orders:
            assert sorted(order) == sorted(w["ladder"])  # a permutation
            assert order.index("heat") < order.index("charge")  # no suicide
        assert len({tuple(o) for o in orders}) >= 2  # never one shared order


def test_verb_batching_passes_mid_but_fails_hard():
    for w in _worlds("mid"):
        ok, reason = fw.verify_solution(w, fw.naive_batch_solver(w))
        assert ok, f"mid batching should pass: {reason}"
    for w in _worlds("hard"):
        ok, reason = fw.verify_solution(w, fw.naive_batch_solver(w))
        assert not ok, f"{w['world_id']}: hard must punish verb batching"
        # cooling is the planted reason batching dies on hard tier
        assert "heated" in reason or "requires" in reason


def test_blast_shortcut_fails_on_hard():
    for w in _worlds("hard"):
        ok, reason = fw.verify_solution(w, fw.blast_solver(w))
        assert not ok
        assert "tainted" in reason or "fuse" in reason


def test_rule_violations_are_caught():
    w = fw.generate_world(seed=1, tier="hard", world_idx=0)
    item = w["items"][0]
    # applying the SECOND step of an ore's own order directly violates its
    # precondition (the first step's flag is missing)
    second = w["ladders"][item][1]
    ok, reason = fw.verify_solution(w, [f"{second}({item})"])
    assert not ok and "requires" in reason
    # unknown ore is rejected
    ok, reason = fw.verify_solution(w, ["cleanse(zzz)"])
    assert not ok and "unknown" in reason
    # exceeding the step cap fails before any simulation
    ok, reason = fw.verify_solution(w, ["cleanse(%s)" % item] * (w["step_cap"] + 1))
    assert not ok and "cap" in reason
    # no fuse at the end fails
    ladder_actions = fw.strategy_solver(w)[:-1]
    ok, reason = fw.verify_solution(w, ladder_actions)
    assert not ok and "fuse" in reason


def test_drain_window_binding():
    # deterministic search: a hard world with an ore whose own order has
    # charge immediately before inscribe (so inscribe's precondition is the
    # primed flag that drain clears)
    target = None
    for w in _worlds("hard"):
        for ore, order in w["ladders"].items():
            if order.index("inscribe") == order.index("charge") + 1:
                other = next(i for i in w["items"] if i != ore)
                target = (w, ore, other)
                break
        if target:
            break
    assert target, "no charge->inscribe ore in the deterministic world set"
    w, a, b = target
    k = w["constraints"]["decay_k"]
    order_a = w["ladders"][a]
    prime_steps = [f"{v}({a})" for v in order_a[: order_a.index("charge") + 1]]
    stall_verb = w["ladders"][b][0]  # first step of b's order: always legal
    actions = prime_steps + [f"{stall_verb}({b})"] * (k + 1) + [f"inscribe({a})"]
    ok, reason = fw.verify_solution(w, actions)
    assert not ok
    assert "requires primed" in reason  # drained before the inscribe


# ------------------------------------------------------------- lessons
def test_lessons_three_typed_layers():
    for w in _worlds("hard") + _worlds("mid"):
        lessons = w["lessons"]
        assert lessons["fact"] and all(l["type"] == "fact" for l in lessons["fact"])
        assert lessons["workflow"]["type"] == "workflow"
        norm = lessons["norm"]
        assert norm["type"] == "norm"
        assert norm["enforce"].startswith("enforce:")
        assert "avoid:" in norm["avoid"]
        # workflow lesson must carry the planted strategy statement
        assert "atomically" in lessons["workflow"]["text"] or \
               "back-to-back" in lessons["workflow"]["text"]
    # hard tier norm must name every interaction trap
    for w in _worlds("hard"):
        assert "blast" in w["lessons"]["norm"]["avoid"]
        assert "re-heating" in w["lessons"]["norm"]["avoid"]
        assert "drain" in w["lessons"]["norm"]["avoid"] or "drains" in \
               w["lessons"]["norm"]["avoid"]


# ------------------------------------------------------------- prompting
def test_zs_prompt_states_facts_but_never_strategy_or_norms():
    for w in _worlds("hard") + _worlds("mid"):
        prompt = fw.render_prompt(w)
        # facts are present
        for rule in w["rules"]:
            assert rule["text"] in prompt
        for item in w["items"]:
            assert item in prompt
        # the workflow strategy / norm phrasing must NOT leak into ZS prompt
        for banned in ("atomically", "back-to-back", "Never batch",
                       "never interleave", "enforce:", "avoid:"):
            assert banned not in prompt
        assert str(w["step_cap"]) in prompt


def test_parse_model_actions_roundtrip():
    w = fw.generate_world(seed=7, tier="hard", world_idx=0)
    actions = fw.strategy_solver(w)
    import json
    text = json.dumps({"actions": actions})
    parsed = fw.parse_model_actions(text)
    assert parsed == [a.casefold() for a in actions]
    ok, _ = fw.verify_solution(w, parsed)
    assert ok
    # prose around the JSON is tolerated
    parsed2 = fw.parse_model_actions("Here is my plan:\n" + text + "\nDone.")
    assert parsed2 == parsed
    # garbage is a parse failure, not a crash
    assert fw.parse_model_actions("no json here") is None
    assert fw.parse_model_actions('{"wrong_key": []}') is None
