"""Tests for the F3v2 arms harness slice 2 (f3v2_arms + f3v2_dev_smoke).

Fully offline: every chat is a deterministic f3v2_arms.ScriptedChat (exact
prompt table, fail-closed on a miss) — no network, no live LLM calls.  Covers
train/test split disjointness, arm-context determinism, abstraction token
stripping, contrast evidence requirements, placebo purity, the disagreement
gate, TRR math (incl. the degenerate case), the K1-K3 kill evaluators, the
receipt schema, and the dev-smoke dry-run end to end.
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

import f3v2_arms as fa  # noqa: E402
import f3v2_procedural_worlds as fw  # noqa: E402

SEED = 20260726
MODEL = "scripted-model"


# ---------------------------------------------------------------- helpers
def _splits(n_train=4, n_test=4, tier="hard"):
    return fa.make_splits(n_train, n_test, tier, SEED, SEED + 1)


def _chat_for(worlds, policy):
    chat = fa.ScriptedChat()
    for i, w in enumerate(worlds):
        chat.add(MODEL, fa.SYSTEM_PROMPT, fw.render_prompt(w), policy(w, i))
    return chat


def _donor_policy(w, _i):
    return fw.strategy_solver(w)


def _receiver_policy(w, i):
    """One success (idx%4==1), blast failure (idx%4==2), else verb-batching
    failure — exercises the gate's negative and two failure modes."""
    if i % 4 == 1:
        return fw.strategy_solver(w)
    if i % 4 == 2:
        return fw.blast_solver(w)
    return fw.naive_batch_solver(w)


def _experience(splits):
    donor_trajs = fa.run_experience(
        _chat_for(splits["train"], _donor_policy), MODEL, splits["train"],
        seed=SEED, max_tokens=64)
    recv_trajs = fa.run_experience(
        _chat_for(splits["train"], _receiver_policy), MODEL, splits["train"],
        seed=SEED, max_tokens=64)
    return donor_trajs, recv_trajs


def _lesson_sets(splits):
    donor_trajs, recv_trajs = _experience(splits)
    return fa.build_lesson_sets(splits["train"], donor_trajs, recv_trajs)


def _lesson_blob(lesson):
    return " ".join(p for p in (lesson["text"], lesson["enforce"],
                                lesson["avoid"]) if p)


def _results(arm_scores):
    out = {}
    for arm, scores in arm_scores.items():
        rows = [{"world_id": f"f3v2-hard-{i}", "tier": "hard",
                 "correct": bool(s)} for i, s in enumerate(scores)]
        out[arm] = {"arm_id": arm, "n": len(rows),
                    "n_correct": sum(r["correct"] for r in rows),
                    "accuracy": fa.accuracy(rows), "rows": rows}
    return out


CORE_SCORES = {
    "a_no_memory": [0, 0, 0, 0],
    "b_naive_donor": [0, 0, 0, 0],
    "c_abstracted": [1, 0, 1, 0],
    "d_contrast": [1, 1, 0, 0],
    "e_b_self": [1, 1, 1, 1],
    "f_placebo": [0, 1, 0, 0],
}


# ------------------------------------------------------------- splits
def test_train_test_split_disjoint_enforced():
    splits = _splits()
    train_sha = {fw.world_sha256(w) for w in splits["train"]}
    test_sha = {fw.world_sha256(w) for w in splits["test"]}
    assert train_sha.isdisjoint(test_sha)
    # identical seeds produce identical worlds -> fail closed
    with pytest.raises(fa.SplitError):
        fa.make_splits(4, 4, "hard", 1000, 1000)


# ------------------------------------------------------------- experience
def test_run_experience_records_trajectories():
    splits = _splits()
    donor_trajs, recv_trajs = _experience(splits)
    assert all(t["correct"] for t in donor_trajs)
    assert [t["correct"] for t in recv_trajs] == [False, True, False, False]
    assert recv_trajs[0]["violation"] is not None
    assert fa.accuracy(donor_trajs) == 1.0
    assert fa.accuracy(recv_trajs) == 0.25


def test_failure_mode_classification():
    splits = _splits()
    worlds = splits["train"]
    _, recv_trajs = _experience(splits)
    assert fa.classify_failure(worlds[0], recv_trajs[0]) == "verb-batching"
    assert fa.classify_failure(worlds[2], recv_trajs[2]) == "blast-shortcut"
    assert fa.classify_failure(worlds[1], recv_trajs[1]) is None  # success


# ------------------------------------------------------------- determinism
def test_arm_prompt_determinism():
    splits = _splits()
    sets = _lesson_sets(splits)
    arms = list(fa.CORE_ARM_IDS) + list(fa.GATED_ARM_IDS)
    for arm in arms:
        for w in splits["test"]:
            p1 = fa.build_arm_prompt(arm, w, sets)
            p2 = fa.build_arm_prompt(arm, w, sets,
                                     embedder=fa.HashEmbedder())
            assert p1 == p2


def test_hash_embedder_and_retrieval_determinism():
    e1, e2 = fa.HashEmbedder(), fa.HashEmbedder()
    assert e1("cooling crucible heat") == e2("cooling crucible heat")
    assert fa.cosine(e1("identical text"), e1("identical text")) == \
        pytest.approx(1.0)
    splits = _splits()
    sets = _lesson_sets(splits)
    w = splits["test"][0]
    r1 = [l["lesson_id"] for l in
          fa.retrieve_lessons(fa._rules_text(w), sets["naive"], e1)]
    r2 = [l["lesson_id"] for l in
          fa.retrieve_lessons(fa._rules_text(w), sets["naive"], e2)]
    assert r1 == r2
    assert len(r1) == fa.TOP_K


# ------------------------------------------------------------- abstracted
def test_abstracted_strips_world_tokens():
    splits = _splits()
    sets = _lesson_sets(splits)
    assert sets["abstracted"]
    for lesson in sets["abstracted"]:
        blob = _lesson_blob(lesson)
        for w in splits["train"]:
            assert not re.search(r"\b" + re.escape(w["world_name"]) + r"\b",
                                 blob)
            assert not re.search(r"\b" + re.escape(w["relic"]) + r"\b", blob)
            for item in w["items"]:
                assert not re.search(r"\b" + re.escape(item) + r"\b", blob), \
                    f"ore {item} leaked into {lesson['lesson_id']}"
    # enforce/avoid semantics survive
    norms = [l for l in sets["abstracted"] if l["kind"] == "norm"]
    assert norms and any(l["enforce"].startswith("enforce:") for l in norms)
    assert any("avoid:" in l["avoid"] for l in norms)
    # per-ore order facts are dropped; generic mechanic facts are kept
    facts = [l for l in sets["abstracted"] if l["kind"] == "fact"]
    assert facts
    assert all("Preparation order of" not in l["text"] for l in facts)
    # numeric drain windows generalized
    assert not any(re.search(r"next \d+ actions|more than \d+ actions",
                             _lesson_blob(l)) for l in sets["abstracted"])


# ------------------------------------------------------------- contrast
def test_contrast_requires_success_and_failure_evidence():
    worlds = fw.generate_batch(1, "hard", 99)
    donor_trajs = fa.run_experience(
        _chat_for(worlds, _donor_policy), MODEL, worlds, seed=1,
        max_tokens=64)
    res = fa.compile_arm_lessons(worlds, donor_trajs)  # failure pool = donor
    assert res["contrast"] == []  # no failure evidence at all

    recv_trajs = fa.run_experience(
        _chat_for(worlds, lambda w, _i: fw.naive_batch_solver(w)), MODEL,
        worlds, seed=1, max_tokens=64)
    assert not recv_trajs[0]["correct"]
    res2 = fa.compile_arm_lessons(worlds, donor_trajs,
                                  failure_trajectories=recv_trajs)
    assert [l["mode"] for l in res2["contrast"]] == ["verb-batching"]
    pair = res2["contrast"][0]
    assert pair["enforce"].startswith("enforce:")
    assert pair["avoid"].startswith("avoid:")
    assert "observed:" in pair["avoid"]

    # failure evidence without a donor success -> still no contrast
    res3 = fa.compile_arm_lessons(worlds, recv_trajs,
                                  failure_trajectories=recv_trajs)
    assert res3["contrast"] == []


# ------------------------------------------------------------- placebo
def test_placebo_has_no_foundry_verbs_and_disjoint_content():
    splits = _splits()
    sets = _lesson_sets(splits)
    assert sets["placebo"]
    for lesson in sets["placebo"]:
        blob = _lesson_blob(lesson)
        assert not fa.FOUNDRY_VERB_RE.search(blob), \
            f"foundry verb in placebo {lesson['lesson_id']}"

    def content_tokens(lessons):
        toks = set()
        for lesson in lessons:
            toks.update(
                t for t in re.findall(r"[a-z0-9]+",
                                      _lesson_blob(lesson).casefold())
                if t not in fa.PLACEBO_STOPWORDS)
        return toks

    real = sets["naive"] + sets["contrast"] + sets["b_self"]
    overlap = content_tokens(sets["placebo"]) & content_tokens(real)
    assert overlap == set(), f"placebo/real content-word overlap: {overlap}"
    # format parity: same kinds and enforce/avoid scaffolding as real lessons
    assert {l["kind"] for l in sets["placebo"]} == {"fact", "workflow", "norm"}
    pnorm = next(l for l in sets["placebo"] if l["kind"] == "norm")
    assert pnorm["enforce"].startswith("enforce:")
    assert "avoid:" in pnorm["avoid"]


# ------------------------------------------------------------- disagreement gate
def test_disagreement_gate_flagging_and_filtering():
    splits = _splits()
    sets = _lesson_sets(splits)
    flags = sets["disagreement"]
    flagged_ids = [w["world_id"] for w in splits["train"]
                   if flags[w["watermark"]]]
    # receiver succeeded only on world 1; donor succeeded everywhere
    assert flagged_ids == ["f3v2-hard-0", "f3v2-hard-2", "f3v2-hard-3"]
    assert any(not l["flagged"] for l in sets["naive"])
    assert any(l["flagged"] for l in sets["naive"])

    emb = fa.HashEmbedder()
    w = splits["test"][0]
    expected = fa.retrieve_lessons(
        fa._rules_text(w), [l for l in sets["naive"] if l["flagged"]],
        emb, fa.TOP_K)
    prompt = fa.build_arm_prompt("b_naive_donor_gated", w, sets, embedder=emb)
    assert fa.render_lesson_block(expected) in prompt
    block = prompt.split("\n\n")[0]
    flag_texts = {l["text"] for l in sets["naive"]
                  if l["flagged"] and l["kind"] in ("fact", "workflow")}
    for l in sets["naive"]:
        if (not l["flagged"] and l["kind"] in ("fact", "workflow")
                and l["text"] not in flag_texts):
            assert l["text"] not in block, "unflagged lesson leaked past gate"

    # gate-invariant arms have no _gated variant
    for arm in ("a_no_memory_gated", "e_b_self_gated", "f_placebo_gated"):
        with pytest.raises(fa.ArmsError):
            fa.build_arm_prompt(arm, w, sets)


def test_xvendor_arm_is_a_documented_stub():
    splits = _splits()
    sets = _lesson_sets(splits)
    with pytest.raises(NotImplementedError):
        fa.build_arm_prompt("x_xvendor", splits["test"][0], sets)


# ------------------------------------------------------------- TRR
def test_trr_math_hand_computed():
    table = fa.trr_table(_results(CORE_SCORES))["hard"]
    assert table["c_abstracted"]["trr"] == 0.5       # (0.5-0)/(1-0)
    assert table["d_contrast"]["trr"] == 0.5
    assert table["b_naive_donor"]["trr"] == 0.0
    assert table["f_placebo"]["trr"] == 0.25
    assert table["e_b_self"]["trr"] == 1.0
    assert table["c_abstracted"]["degenerate"] is False


def test_trr_negative_and_negative_transfer_rate():
    scores = dict(CORE_SCORES)
    scores["a_no_memory"] = [1, 0, 1, 0]
    scores["c_abstracted"] = [0, 0, 0, 0]
    table = fa.trr_table(_results(scores))["hard"]
    entry = table["c_abstracted"]
    assert entry["trr"] == -1.0                      # (0-0.5)/(1-0.5)
    assert entry["negative_transfer_rate"] == 0.5    # two worlds below no_mem


def test_trr_degenerate_when_b_self_equals_no_mem():
    scores = dict(CORE_SCORES)
    scores["a_no_memory"] = [0, 1, 0, 1]
    scores["e_b_self"] = [0, 1, 0, 1]
    table = fa.trr_table(_results(scores))["hard"]
    entry = table["c_abstracted"]
    assert entry["trr"] is None
    assert entry["degenerate"] is True


def test_trr_pairing_is_fail_closed():
    results = _results(CORE_SCORES)
    results["c_abstracted"]["rows"] = results["c_abstracted"]["rows"][::-1]
    with pytest.raises(fa.ArmsError):
        fa.trr_table(results)


# ------------------------------------------------------------- kills
def test_k1_env_kill_fires_and_not_fires():
    fired = fa.eval_k1_env_kill(trr_contrast=-0.2, trr_abstracted=0.0,
                                b_self_acc=0.75)
    assert fired["fired"] and fired["evaluable"]
    assert not fa.eval_k1_env_kill(
        trr_contrast=-0.2, trr_abstracted=0.3, b_self_acc=0.75)["fired"]
    assert not fa.eval_k1_env_kill(
        trr_contrast=-0.2, trr_abstracted=0.0, b_self_acc=0.5)["fired"]
    degen = fa.eval_k1_env_kill(trr_contrast=None, trr_abstracted=0.0,
                                b_self_acc=0.75)
    assert not degen["fired"] and not degen["evaluable"]


def test_k2_claim_kill_fires_and_not_fires():
    # naive TRR < 0 and neither arm beats naive (zero/centred CIs) -> fires
    fired = fa.eval_k2_claim_kill(
        naive_trr=-0.25,
        contrast_scores=[0, 1, 0, 1], naive_scores=[0, 1, 0, 1],
        abstracted_scores=[1, 0, 1, 0], reps=2000, seed=1)
    assert fired["fired"] and fired["evaluable"]
    assert fired["values"]["contrast_minus_naive"]["ci95"] == [0.0, 0.0]

    # contrast cleanly beats naive (constant +1 diff) -> no kill
    beaten = fa.eval_k2_claim_kill(
        naive_trr=-0.25,
        contrast_scores=[1] * 8, naive_scores=[0] * 8,
        abstracted_scores=[0] * 8, reps=2000, seed=1)
    assert not beaten["fired"]
    assert beaten["values"]["contrast_beats_naive"] is True

    # naive TRR not negative -> kill cannot fire
    assert not fa.eval_k2_claim_kill(
        naive_trr=0.1,
        contrast_scores=[0, 1, 0, 1], naive_scores=[0, 1, 0, 1],
        abstracted_scores=[0, 1, 0, 1], reps=2000, seed=1)["fired"]

    degen = fa.eval_k2_claim_kill(
        naive_trr=None,
        contrast_scores=[0], naive_scores=[0], abstracted_scores=[0],
        reps=200, seed=1)
    assert not degen["fired"] and not degen["evaluable"]


def test_k3_priming_kill_fires_and_not_fires():
    assert fa.eval_k3_priming_kill(trr_placebo=0.5, trr_abstracted=0.55)["fired"]
    assert not fa.eval_k3_priming_kill(trr_placebo=0.3,
                                       trr_abstracted=0.55)["fired"]
    degen = fa.eval_k3_priming_kill(trr_placebo=None, trr_abstracted=0.55)
    assert not degen["fired"] and not degen["evaluable"]


def test_evaluate_kills_requires_core_arms_and_marks_na_kills():
    kills = fa.evaluate_kills(fa.trr_table(_results(CORE_SCORES))["hard"],
                              reps=2000, seed=1)
    assert set(kills) == {"k1_env_kill", "k2_claim_kill", "k3_priming_kill",
                          "k4_judge_kill", "k5_noise_floor_kill"}
    assert kills["k4_judge_kill"]["applicable"] is False
    assert kills["k5_noise_floor_kill"]["applicable"] is False
    with pytest.raises(fa.ArmsError):
        fa.evaluate_kills({"a_no_memory": {}}, reps=100, seed=1)


# ------------------------------------------------------------- receipt
def test_receipt_schema_and_development_stage():
    splits = _splits()
    results = _results(CORE_SCORES)
    trr = fa.trr_table(results)
    kills = fa.evaluate_kills(trr["hard"], reps=2000, seed=1)
    receipt = fa.build_receipt(
        script_path=os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "f3v2_dev_smoke.py"),
        config={"tier": "hard", "train_seed": SEED, "test_seed": SEED + 1},
        train_worlds=splits["train"], test_worlds=splits["test"],
        arm_results=results, trr=trr, kills=kills,
        budget_block={"mode": "scripted-dry-run", "used": 0},
        wall_clock_s=0.1)
    for key in ("schema_version", "mode", "stage", "preregistration_file",
                "preregistration_file_sha256", "script_sha256",
                "harness_module_sha256", "config", "split_audit", "worlds",
                "arms", "trr", "judgment_target", "kills", "llm_budget",
                "honesty", "wall_clock_s"):
        assert key in receipt, f"missing receipt key {key}"
    assert receipt["schema_version"] == "hswm-f3v2-arms-receipt/v1"
    assert receipt["mode"] == "development"
    assert receipt["stage"] == "DEVELOPMENT_ONLY"
    assert set(receipt["harness_module_sha256"]) == {
        "f3v2_procedural_worlds.py", "f2_delta_w_credit.py", "f3v2_arms.py"}
    assert receipt["split_audit"]["verdict"] == "DISJOINT"
    assert len(receipt["worlds"]) == 8
    assert {w["split"] for w in receipt["worlds"]} == {"train", "test"}
    assert "grounded measurement" in receipt["honesty"]
    json.dumps(receipt)  # serializable


# ------------------------------------------------------------- dev smoke
def test_dev_smoke_dry_run_end_to_end(tmp_path):
    import f3v2_dev_smoke as smoke
    out = tmp_path / "receipt.json"
    rc = smoke.main(["--out", str(out), "--gated"])
    assert rc == 0
    receipt = json.loads(out.read_text())
    assert receipt["aborted"] is None
    assert receipt["stage"] == "DEVELOPMENT_ONLY"
    assert receipt["dry_run"] is True
    assert receipt["llm_budget"]["mode"] == "scripted-dry-run"
    assert receipt["split_audit"]["verdict"] == "DISJOINT"
    for arm in list(fa.CORE_ARM_IDS) + [fa.FLAT_FILE_ARM] + \
            list(fa.GATED_ARM_IDS):
        assert arm in receipt["arms"], f"arm {arm} missing from smoke receipt"
    hard = receipt["trr"]["hard"]
    assert hard["a_no_memory"]["acc"] == 0.0
    assert hard["e_b_self"]["acc"] == 1.0
    assert hard["b_naive_donor"]["trr"] == 0.25
    assert hard["g_flat_file"]["trr"] == 0.5
    assert receipt["judgment_target"]["value"] == 0.75
    assert receipt["kills"]["k1_env_kill"]["fired"] is False
    assert receipt["kills"]["k4_judge_kill"]["applicable"] is False
    # scripted budget accounting: 2*4 train + 10 contexts * 4 test = 48 lookups
    assert receipt["llm_budget"]["used"] == 48
    assert receipt["llm_budget"]["planned_calls"] == 48


def test_dev_smoke_live_refuses_overspend_before_network(tmp_path):
    import f3v2_dev_smoke as smoke
    # --live without a sealed manifest and without --dev is refused by the
    # sealed-run gate (argparse exit 2) BEFORE any endpoint is touched.
    with pytest.raises(SystemExit) as exc:
        smoke.main(["--live", "--out", str(tmp_path / "r.json")])
    assert exc.value.code == 2
