"""Tests for the F3v2 SEALED layer: g_flat_file strong null, sealed prep
(manifest + _write_once + --seal flip), and sealed-run gating.

Fully offline: no network, no live LLM calls (every chat is scripted; prep is
pure file/deterministic-world work).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

import f3v2_arms as fa  # noqa: E402
import f3v2_dev_smoke as smoke  # noqa: E402
import f3v2_procedural_worlds as fw  # noqa: E402
import f3v2_sealed_prep as prep  # noqa: E402

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


def _lesson_sets(splits):
    donor_trajs = fa.run_experience(
        _chat_for(splits["train"], lambda w, _i: fw.strategy_solver(w)),
        MODEL, splits["train"], seed=SEED, max_tokens=64)

    def _receiver(w, i):
        if i % 4 == 1:
            return fw.strategy_solver(w)
        if i % 4 == 2:
            return fw.blast_solver(w)
        return fw.naive_batch_solver(w)

    recv_trajs = fa.run_experience(
        _chat_for(splits["train"], _receiver), MODEL, splits["train"],
        seed=SEED, max_tokens=64)
    return fa.build_lesson_sets(splits["train"], donor_trajs, recv_trajs)


def _tiny_prereg():
    return {
        "schema_version": "hswm-preregistration/v1",
        "branch": "F3v2-harder-transfer-testbed",
        "environment": {"generator": "f3v2_procedural_worlds.py"},
        "cohort": {
            "train": {"hard": 2, "mid": 1, "seed": 101},
            "test": {"hard": 3, "mid": 2, "seed": 202},
            "cluster_key": "world"},
        "models": {"donor": {"id": "d"}, "receiver": {"id": "r"}},
        "metrics": {"estimation": "paired bootstrap 95% CI (reps=10000, "
                                  "seed=20260727)"},
        "budget_contract": {
            "contexts_per_test_world": 10, "per_call_max_tokens": 768,
            "hard_cap": 5400,
            "estimated_calls": {"receiver_test": 50, "receiver_train": 3,
                                "donor_train": 3, "total": 56}},
    }


def _write_tiny_prereg(tmp_path):
    path = tmp_path / "prereg.json"
    payload = json.dumps(_tiny_prereg(), sort_keys=True, indent=2) + "\n"
    path.write_text(payload, encoding="utf-8")
    return path


def _prep_tiny(tmp_path, seal=False):
    prereg_path = _write_tiny_prereg(tmp_path)
    dev = tmp_path / "manifest.dev.json"
    rc = prep.main(["--prereg", str(prereg_path), "--out", str(dev),
                    "--run-id", "tiny"])
    assert rc == 0
    if not seal:
        return prereg_path, dev
    sealed = tmp_path / "manifest.sealed.json"
    rc = prep.main(["--seal", "--in", str(dev), "--out", str(sealed)])
    assert rc == 0
    return prereg_path, sealed


# ================================================================== flat file
def test_flat_file_is_unstructured_but_same_lessons():
    splits = _splits()
    sets = _lesson_sets(splits)
    emb = fa.HashEmbedder()
    w = splits["test"][0]
    prompt = fa.build_arm_prompt("g_flat_file", w, sets, embedder=emb)
    base = fw.render_prompt(w)
    assert prompt.endswith(base)
    block = prompt[: len(prompt) - len(base) - 2]

    # same retrieval as (b) naive over the same pool
    expected = fa.retrieve_lessons(fa._rules_text(w), sets["naive"], emb,
                                   fa.TOP_K)
    assert block == fa.render_flat_file(expected)
    assert block.startswith(fa.FLAT_FILE_INSTRUCTION)

    # unstructured: no typed kind tags, no lesson ids, no block header,
    # no "||" norm separator (that is typed-block structure)
    for marker in ("[fact]", "[workflow]", "[norm]", "[contrast]",
                   "Experience notes from prior work in other workshops",
                   "||"):
        assert marker not in block
    for lesson in sets["naive"]:
        assert lesson["lesson_id"] not in block

    # content ⊆ naive pool only ("no foundry strategy text beyond naive"):
    # every paragraph after the instruction is a whitespace-normalized naive
    # lesson body
    naive_bodies = set()
    for lesson in sets["naive"]:
        if lesson["kind"] in ("norm", "contrast"):
            body = f"{lesson['enforce']} {lesson['avoid']}"
        else:
            body = lesson["text"]
        naive_bodies.add(" ".join(body.split()))
    paragraphs = block.split("\n\n")[1:]
    assert len(paragraphs) == len(expected)
    for para in paragraphs:
        assert para in naive_bodies


def test_flat_file_deterministic_and_gate_invariant():
    splits = _splits()
    sets = _lesson_sets(splits)
    w = splits["test"][0]
    assert fa.build_arm_prompt("g_flat_file", w, sets) == \
        fa.build_arm_prompt("g_flat_file", w, sets,
                            embedder=fa.HashEmbedder())
    with pytest.raises(fa.ArmsError):
        fa.build_arm_prompt("g_flat_file_gated", w, sets)
    # registry: 10 sealed contexts = 6 core + g + 3 gated
    assert len(fa.SEALED_CONTEXTS) == 10
    assert fa.SEALED_CONTEXTS == (fa.CORE_ARM_IDS + (fa.FLAT_FILE_ARM,)
                                  + fa.GATED_ARM_IDS)


def test_flat_file_scores_but_stays_out_of_judgment():
    splits = _splits()
    results = {}
    for arm, scores in {
            "a_no_memory": [0, 0, 0, 0], "b_naive_donor": [0, 0, 0, 0],
            "c_abstracted": [1, 0, 1, 0], "d_contrast": [1, 1, 0, 0],
            "e_b_self": [1, 1, 1, 1], "f_placebo": [0, 1, 0, 0],
            "g_flat_file": [1, 0, 0, 1]}.items():
        rows = [{"world_id": f"f3v2-hard-{i}", "tier": "hard",
                 "correct": bool(s)} for i, s in enumerate(scores)]
        results[arm] = {"arm_id": arm, "n": 4,
                        "n_correct": sum(r["correct"] for r in rows),
                        "accuracy": fa.accuracy(rows), "rows": rows}
    trr = fa.trr_table(results)
    assert trr["hard"]["g_flat_file"]["trr"] == 0.5  # scored alongside
    kills = fa.evaluate_kills(trr["hard"], reps=200, seed=1)
    receipt = fa.build_receipt(
        script_path=os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "f3v2_dev_smoke.py"),
        config={"tier": "hard", "train_seed": SEED, "test_seed": SEED + 1},
        train_worlds=splits["train"], test_worlds=splits["test"],
        arm_results=results, trr=trr, kills=kills,
        budget_block={"mode": "scripted-dry-run", "used": 0},
        wall_clock_s=0.1)
    # judgment target is min(c, d) — g does not enter it
    assert receipt["judgment_target"]["value"] == 0.5
    assert "g_flat_file" not in receipt["judgment_target"]["name"]


# ================================================================== prep
def test_build_manifest_deterministic_and_complete():
    prereg = _tiny_prereg()
    m1 = prep.build_manifest(prereg, prereg_path="p", prereg_sha256="s",
                             run_id="tiny")
    m2 = prep.build_manifest(prereg, prereg_path="p", prereg_sha256="s",
                             run_id="tiny")
    assert json.dumps(m1, sort_keys=True) == json.dumps(m2, sort_keys=True)
    assert m1["schema_version"] == "hswm-f3v2-sealed-manifest/v1"
    assert m1["mode"] == "development"
    assert m1["preregistration_receipt_sha256"] == "s"
    assert m1["cohort"]["train"]["n_worlds"] == 3
    assert m1["cohort"]["test"]["n_worlds"] == 5
    assert m1["cohort"]["train"]["tiers"] == {"hard": 2, "mid": 1}
    assert m1["split_audit"]["verdict"] == "DISJOINT"
    assert len(m1["arms"]) == 10
    # budget: 2*3 train + 10*5 test = 56
    assert m1["budget"]["total"] == 56
    assert m1["budget"]["receiver_test"] == 50
    assert m1["budget"]["within_cap"] is True
    assert m1["generator"]["sha256"]
    assert m1["estimation"]["bootstrap_reps"] == 10000
    assert m1["estimation"]["bootstrap_seed"] == 20260727
    # world entries carry the binding shas
    entry = m1["cohort"]["test"]["worlds"][0]
    assert len(entry["world_sha256"]) == 64 and len(entry["watermark"]) == 16


def test_build_manifest_refuses_leaking_split():
    prereg = _tiny_prereg()
    prereg["cohort"]["test"]["seed"] = 101  # same seed as train -> same worlds
    with pytest.raises(prep.PrepError):
        prep.build_manifest(prereg, prereg_path="p", prereg_sha256="s",
                            run_id="tiny")


def test_build_manifest_refuses_budget_drift():
    prereg = _tiny_prereg()
    prereg["budget_contract"]["estimated_calls"]["total"] = 999
    with pytest.raises(prep.PrepError):
        prep.build_manifest(prereg, prereg_path="p", prereg_sha256="s",
                            run_id="tiny")
    prereg = _tiny_prereg()
    prereg["budget_contract"]["contexts_per_test_world"] = 9
    with pytest.raises(prep.PrepError):
        prep.build_manifest(prereg, prereg_path="p", prereg_sha256="s",
                            run_id="tiny")


def test_write_once_and_expect_sha(tmp_path):
    prereg_path = _write_tiny_prereg(tmp_path)
    out = tmp_path / "manifest.dev.json"
    rc = prep.main(["--prereg", str(prereg_path), "--out", str(out)])
    assert rc == 0
    # _write_once: a second write to the same path is refused
    rc = prep.main(["--prereg", str(prereg_path), "--out", str(out)])
    assert rc == 1
    assert not (tmp_path / "manifest.dev.json").read_text() == ""
    # expect-sha: wrong value refused, right value accepted
    rc = prep.main(["--prereg", str(prereg_path), "--expect-prereg-sha",
                    "0" * 64, "--out", str(tmp_path / "m2.json")])
    assert rc == 1
    good = hashlib.sha256(prereg_path.read_bytes()).hexdigest()
    rc = prep.main(["--prereg", str(prereg_path), "--expect-prereg-sha", good,
                    "--out", str(tmp_path / "m2.json")])
    assert rc == 0


def test_seal_flip_and_refusals(tmp_path):
    _prereg_path, dev = _prep_tiny(tmp_path)
    sealed = tmp_path / "manifest.sealed.json"
    rc = prep.main(["--seal", "--in", str(dev), "--out", str(sealed)])
    assert rc == 0
    dev_doc = json.loads(dev.read_text())
    sealed_doc = json.loads(sealed.read_text())
    assert sealed_doc["mode"] == "sealed"
    assert dev_doc["mode"] == "development"
    # mode flip only — every other field identical
    assert {k: v for k, v in sealed_doc.items() if k != "mode"} == \
           {k: v for k, v in dev_doc.items() if k != "mode"}
    # re-seal of a sealed source refused
    rc = prep.main(["--seal", "--in", str(sealed),
                    "--out", str(tmp_path / "again.json")])
    assert rc == 1
    # sealing onto an existing path refused
    rc = prep.main(["--seal", "--in", str(dev), "--out", str(sealed)])
    assert rc == 1
    # sealing a non-manifest refused
    rc = prep.main(["--seal", "--in", str(_prereg_path),
                    "--out", str(tmp_path / "junk.json")])
    assert rc == 1


def test_real_prereg_manifest_budget():
    manifest = prep.build_manifest(
        prep._load_json(prep.DEFAULT_PREREG),
        prereg_path=str(prep.DEFAULT_PREREG),
        prereg_sha256=prep._sha256_path(prep.DEFAULT_PREREG),
        run_id="f3v2-sealed-prep-r1")
    assert manifest["cohort"]["train"]["tiers"] == {"hard": 32, "mid": 16}
    assert manifest["cohort"]["test"]["tiers"] == {"hard": 384, "mid": 128}
    budget = manifest["budget"]
    assert budget["contexts_per_test_world"] == 10
    assert budget["receiver_test"] == 512 * 10 == 5120
    assert budget["receiver_train"] == budget["donor_train"] == 48
    assert budget["total"] == 5216
    assert budget["hard_cap"] == 5400
    assert budget["within_cap"] is True
    # regeneration path verifies the sealed list bit-for-bit
    cohort = fa.cohort_from_manifest(manifest)
    assert len(cohort["train"]) == 48 and len(cohort["test"]) == 512


def test_cohort_from_manifest_fails_closed_on_drift(tmp_path):
    _prereg_path, dev = _prep_tiny(tmp_path)
    manifest = json.loads(dev.read_text())
    manifest["cohort"]["test"]["worlds"][0]["world_sha256"] = "0" * 64
    with pytest.raises(fa.ArmsError):
        fa.cohort_from_manifest(manifest)


# ================================================================== run gating
def test_live_gate_logic():
    assert smoke.live_gate(False, False, None) is None
    assert smoke.live_gate(True, False, "sealed") is None
    assert smoke.live_gate(True, True, "development") is None
    assert smoke.live_gate(True, True, None) is None
    assert smoke.live_gate(True, False, "development") is not None
    assert smoke.live_gate(True, False, None) is not None


def test_sealed_run_gating_and_receipt_modes(tmp_path):
    prereg_path, dev = _prep_tiny(tmp_path)
    # --live on a development manifest without --dev: refused before network
    with pytest.raises(SystemExit) as exc:
        smoke.main(["--manifest", str(dev), "--live",
                    "--out", str(tmp_path / "r0.json")])
    assert exc.value.code == 2

    # scripted (no --live) run on the development manifest
    out_dev = tmp_path / "r_dev.json"
    rc = smoke.main(["--manifest", str(dev), "--out", str(out_dev)])
    assert rc == 0
    receipt = json.loads(out_dev.read_text())
    assert receipt["aborted"] is None
    assert receipt["mode"] == "development"
    assert receipt["stage"] == "DEVELOPMENT_ONLY"
    assert len(receipt["arms"]) == 10
    assert receipt["llm_budget"]["planned_calls"] == 56
    assert receipt["llm_budget"]["used"] == 56
    assert receipt["split_audit"]["verdict"] == "DISJOINT"
    assert receipt["preregistration_receipt_sha256"] == hashlib.sha256(
        prereg_path.read_bytes()).hexdigest()

    # scripted run on the SEALED manifest: mode flips to sealed (config
    # binding) but stage stays DEVELOPMENT_ONLY — scripted numbers carry no
    # sealed weight
    sealed = tmp_path / "manifest.sealed.json"
    rc = prep.main(["--seal", "--in", str(dev), "--out", str(sealed)])
    assert rc == 0
    out_sealed = tmp_path / "r_sealed.json"
    rc = smoke.main(["--manifest", str(sealed), "--out", str(out_sealed)])
    assert rc == 0
    receipt = json.loads(out_sealed.read_text())
    assert receipt["aborted"] is None
    assert receipt["mode"] == "sealed"
    assert receipt["stage"] == "DEVELOPMENT_ONLY"
    assert receipt["dry_run"] is True
    assert receipt["sealed_manifest"]["mode"] == "sealed"
    assert receipt["sealed_manifest"]["sha256"] == hashlib.sha256(
        sealed.read_bytes()).hexdigest()
    assert receipt["preregistration_receipt_sha256"] == hashlib.sha256(
        prereg_path.read_bytes()).hexdigest()
    assert receipt["llm_budget"]["planned_calls"] == 56
