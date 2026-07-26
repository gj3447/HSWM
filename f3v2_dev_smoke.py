"""F3v2 arms dev smoke (prereg §7 step 2) — DEVELOPMENT_ONLY path validation.

PREREG (draft, sha-pinned in the receipt):
  /Users/lagyeongjun/CD/SYMPOSIUM/HSWM/PREREG_F3V2_HARDER_TRANSFER_2026-07-26.md

Pipeline (all logic lives in f3v2_arms; this script is CLI wiring + chat
construction): donor experiences TRAIN worlds -> typed lessons (+ trajectory
contrast) -> frozen receiver attempts disjoint TEST worlds under each arm
context -> simulator scores -> TRR table + kill observations -> receipt.

Live-call budget (hard cap via f2.Budget):
  calls = n_train (donor experience)
        + n_train (receiver train ZS — feeds b_self lessons AND the
                   disagreement gate)
        + n_arms * n_test (6 core arms; --gated adds the 3 *_gated variants).
  dev-4 default (4 train + 4 test, 6 core arms) = 4 + 4 + 24 = 32 calls.
  The default cap is 30 (shared-box discipline — the sealed experiment owns
  the vLLM window today), so the default LIVE plan is REFUSED at preflight:
  pass --max-calls 32 for the deliberate dev-4 sweep, or --n-test 3 for 26
  calls.  --gated at n_test 4 adds 12 more (44 total).

DRY-RUN (the default; NO network — the shared box is sealed today): --live is
REQUIRED for any network call.  Without it the script wires deterministic
ScriptedChats (offline, exact-table, fail-closed on a miss):
  * donor train       = strategy_solver on every train world (all correct);
  * receiver train ZS = scripted policy: idx%4==1 -> strategy_solver (one
    success so the disagreement gate has a negative), idx%4==2 ->
    blast_solver (blast-shortcut failure mode), otherwise naive_batch_solver
    (verb-batching failure mode) — both fail on hard tier by construction;
  * receiver test     = DRY_OUTCOMES per arm (1 -> strategy_solver, 0 ->
    naive_batch_solver).  Calibrated for hard tier (on mid tier the batch
    solver PASSES, so scripted "failures" only bite on hard).
The dry run validates the full pipeline including the receipt write; its
numbers are scripted, never measurements.

Endpoints: default http://192.168.0.23:8000 (dgx is back on the .0/24 LAN;
the canary gate's 192.168.219.102 default is dead).  --receiver-endpoint
defaults to --endpoint (the canary used :8001 for qwen3-4b-real).
Sequential, <=2 concurrent like the canary gate.  Receipts are always
mode="development", stage DEVELOPMENT_ONLY.

Usage:
  python3 f3v2_dev_smoke.py                          # offline dry-run
  python3 f3v2_dev_smoke.py --gated                  # + gate-on variants
  python3 f3v2_dev_smoke.py --live --max-calls 32    # deliberate dev-4 sweep
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

fw = importlib.import_module("f3v2_procedural_worlds")
arms = importlib.import_module("f3v2_arms")

RECEIPT_DIR = HERE / "receipts"
DEFAULT_ENDPOINT = "http://192.168.0.23:8000"

# scripted dry-run receiver outcomes on TEST worlds, per arm (cycled by world
# idx): 1 -> strategy_solver (correct), 0 -> naive_batch_solver (fails hard).
DRY_OUTCOMES = {
    "a_no_memory": (0, 0, 0, 0),
    "b_naive_donor": (0, 1, 0, 0),   # naive transfers ~nothing (null-ish)
    "c_abstracted": (1, 1, 0, 1),
    "d_contrast": (1, 0, 1, 1),
    "e_b_self": (1, 1, 1, 1),        # ceiling
    "f_placebo": (0, 0, 0, 1),       # ≈ no_memory
    "b_naive_donor_gated": (0, 0, 0, 0),
    "c_abstracted_gated": (1, 1, 0, 1),
    "d_contrast_gated": (1, 0, 1, 0),
}


def _dry_train_actions(policy: str, world: dict, idx: int) -> list:
    if policy == "donor" or idx % 4 == 1:
        return fw.strategy_solver(world)
    if idx % 4 == 2:
        return fw.blast_solver(world)
    return fw.naive_batch_solver(world)


def _fill_train_table(chat: arms.ScriptedChat, model: str,
                      worlds: list[dict], policy: str) -> None:
    for i, w in enumerate(worlds):
        chat.add(model, arms.SYSTEM_PROMPT, fw.render_prompt(w),
                 _dry_train_actions(policy, w, i))


def _fill_arm_table(chat: arms.ScriptedChat, model: str,
                    worlds: list[dict], arm_ids, lesson_sets: dict,
                    embedder) -> None:
    for arm in arm_ids:
        pattern = DRY_OUTCOMES[arm]
        for i, w in enumerate(worlds):
            prompt = arms.build_arm_prompt(arm, w, lesson_sets,
                                           embedder=embedder)
            actions = (fw.strategy_solver(w) if pattern[i % len(pattern)]
                       else fw.naive_batch_solver(w))
            chat.add(model, arms.SYSTEM_PROMPT, prompt, actions)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT,
                    help="donor endpoint (dgx .0/24 LAN)")
    ap.add_argument("--receiver-endpoint", default="",
                    help="receiver endpoint; default = --endpoint value")
    ap.add_argument("--donor-model", default="qwen3.6-27b")
    ap.add_argument("--receiver-model", default="qwen3-4b-real")
    ap.add_argument("--seed", type=int, default=20260726,
                    help="chat seed; world seeds default to seed / seed+1")
    ap.add_argument("--train-seed", type=int, default=0)
    ap.add_argument("--test-seed", type=int, default=0)
    ap.add_argument("--n-train", type=int, default=4)
    ap.add_argument("--n-test", type=int, default=4)
    ap.add_argument("--tier", default="hard", choices=fw.TIERS)
    ap.add_argument("--max-tokens", type=int, default=768)
    ap.add_argument("--max-calls", type=int, default=30,
                    help="hard live-call cap (f2.Budget); default 30 keeps "
                         "the shared box disciplined — see docstring budget math")
    ap.add_argument("--gated", action="store_true",
                    help="add the 3 disagreement-gate-on arm variants")
    ap.add_argument("--boot-reps", type=int, default=arms.BOOT_REPS)
    ap.add_argument("--live", action="store_true",
                    help="REQUIRED for any network call; default is the "
                         "offline scripted dry-run")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)

    train_seed = args.train_seed or args.seed
    test_seed = args.test_seed or args.seed + 1
    arm_ids = list(arms.CORE_ARM_IDS)
    if args.gated:
        arm_ids += list(arms.GATED_ARM_IDS)
    plan_calls = 2 * args.n_train + len(arm_ids) * args.n_test

    t0 = time.time()
    ts = int(t0)
    out_path = Path(args.out) if args.out else (
        RECEIPT_DIR / f"f3v2_arms_smoke_{'live' if args.live else 'dry'}_{ts}.json")

    splits = arms.make_splits(args.n_train, args.n_test, args.tier,
                              train_seed, test_seed)
    budget = None
    endpoint_v1 = receiver_endpoint_v1 = "scripted-offline"
    if args.live:
        # lazy imports: the dry-run path (and the offline test suite) never
        # touches the f2/hswm dependency chain or any socket.
        f2 = importlib.import_module("f2_delta_w_credit")
        gate = importlib.import_module("f3v2_canary_gate")
        if plan_calls > args.max_calls:
            ap.error(f"live plan needs {plan_calls} calls > --max-calls "
                     f"{args.max_calls} (2*n_train + n_arms*n_test); raise "
                     "--max-calls deliberately or trim --n-test/--arms")
        budget = f2.Budget(args.max_calls)
        endpoint_v1 = gate._normalize_endpoint(args.endpoint)
        receiver_endpoint_v1 = gate._normalize_endpoint(
            args.receiver_endpoint or args.endpoint)
        donor_chat = f2.CachedOpenAIChat(endpoint_v1, budget)
        receiver_chat = f2.CachedOpenAIChat(receiver_endpoint_v1, budget)
    else:
        donor_chat = arms.ScriptedChat()
        receiver_chat = arms.ScriptedChat()
        _fill_train_table(donor_chat, args.donor_model, splits["train"],
                          "donor")
        _fill_train_table(receiver_chat, args.receiver_model,
                          splits["train"], "receiver")

    aborted = None
    receipt = {}
    receiver_arm_chats: list = []
    try:
        donor_trajs = arms.run_experience(
            donor_chat, args.donor_model, splits["train"], seed=args.seed,
            max_tokens=args.max_tokens)
        recv_train_trajs = arms.run_experience(
            receiver_chat, args.receiver_model, splits["train"],
            seed=args.seed, max_tokens=args.max_tokens)
        lesson_sets = arms.build_lesson_sets(splits["train"], donor_trajs,
                                             recv_train_trajs)
        embedder = arms.HashEmbedder()
        results = {}
        for arm in arm_ids:
            if args.live:
                chat = receiver_chat
            else:
                # one scripted chat per arm: two arms may legitimately build
                # identical contexts (same retrieval on overlapping pools),
                # and a shared exact-match table would let the later arm's
                # scripted outcomes clobber the earlier one's.
                chat = arms.ScriptedChat()
                _fill_arm_table(chat, args.receiver_model, splits["test"],
                                [arm], lesson_sets, embedder)
                receiver_arm_chats.append(chat)
            results.update(arms.evaluate_arms(
                chat, args.receiver_model, splits["test"], [arm], lesson_sets,
                embedder=embedder, seed=args.seed,
                max_tokens=args.max_tokens))
        trr = arms.trr_table(results)
        kills = arms.evaluate_kills(trr[args.tier], reps=args.boot_reps,
                                    seed=args.seed)
        config = vars(args) | {
            "train_seed": train_seed, "test_seed": test_seed,
            "arm_ids": arm_ids, "plan_calls": plan_calls,
            "endpoint_v1": endpoint_v1,
            "receiver_endpoint_v1": receiver_endpoint_v1,
            "embedder": f"{embedder.name} (dim={embedder.dim}, fixed across "
                        "arms per MemDelta)",
            "top_k": arms.TOP_K, "out": str(out_path)}
        recv_misses = receiver_chat.misses + sum(
            c.misses for c in receiver_arm_chats)
        recv_hits = receiver_chat.hits + sum(c.hits for c in receiver_arm_chats)
        used = budget.used if budget is not None else (
            donor_chat.misses + recv_misses)
        budget_block = {
            "mode": "live" if args.live else "scripted-dry-run",
            "max_calls": args.max_calls if args.live else 0,
            "planned_calls": plan_calls, "used": used,
            "donor": {"model": args.donor_model, "url": endpoint_v1,
                      "misses": donor_chat.misses, "hits": donor_chat.hits},
            "receiver": {"model": args.receiver_model,
                         "url": receiver_endpoint_v1,
                         "misses": recv_misses,
                         "hits": recv_hits},
        }
        extra = {
            "dry_run": not args.live,
            "memory": {
                "disagreement_flags": {
                    w["world_id"]: lesson_sets["disagreement"][w["watermark"]]
                    for w in splits["train"]},
                "n_lessons": {name: len(lesson_sets[name]) for name in
                              ("naive", "abstracted", "contrast", "b_self",
                               "placebo")},
                "gate_note": ("flag = receiver failed the train world while "
                              "the donor succeeded on it; *_gated arms inject "
                              "only flagged lessons (Agent KB: gate가 전이 "
                              "성립 조건)."),
            },
        }
        if args.live:
            gate = importlib.import_module("f3v2_canary_gate")
            extra["models_served"] = {
                "donor_endpoint": endpoint_v1,
                "donor": gate._list_models(endpoint_v1),
                "receiver_endpoint": receiver_endpoint_v1,
                "receiver": gate._list_models(receiver_endpoint_v1),
            }
        receipt = arms.build_receipt(
            script_path=Path(__file__), config=config,
            train_worlds=splits["train"], test_worlds=splits["test"],
            arm_results=results, trr=trr, kills=kills,
            budget_block=budget_block,
            wall_clock_s=round(time.time() - t0, 1), extra=extra)
    except arms.ArmsError as err:
        aborted = str(err)
    except Exception as err:  # noqa: BLE001 — recorded, never hidden
        aborted = f"{type(err).__name__}: {err}"

    receipt.setdefault("schema_version", "hswm-f3v2-arms-receipt/v1")
    receipt.setdefault("mode", "development")
    receipt.setdefault("stage", "DEVELOPMENT_ONLY")
    receipt["aborted"] = aborted
    receipt["wall_clock_s"] = round(time.time() - t0, 1)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=1, ensure_ascii=False,
                                   default=str) + "\n", encoding="utf-8")
    summary = {
        "receipt": str(out_path), "aborted": aborted,
        "dry_run": not args.live,
        "judgment_target": receipt.get("judgment_target"),
        "kills_fired": [k for k, v in receipt.get("kills", {}).items()
                        if v.get("fired")],
        "arms": {k: v.get("accuracy")
                 for k, v in receipt.get("arms", {}).items()},
        "calls": receipt.get("llm_budget"),
        "wall_clock_s": receipt["wall_clock_s"],
    }
    print(json.dumps(summary, indent=1, ensure_ascii=False, default=str))
    return 0 if aborted is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
