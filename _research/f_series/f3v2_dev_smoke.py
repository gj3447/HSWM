"""F3v2 arms runner — dev smoke + manifest-driven sealed run (DEVELOPMENT_ONLY unless sealed).

PREREG (machine-locked, binding spec):
  prom_search_hswm/evidence/PREREG_F3V2_harder_transfer_20260726.json

Pipeline (all logic lives in f3v2_arms; this script is CLI wiring + chat
construction): donor experiences TRAIN worlds -> typed lessons (+ trajectory
contrast) -> frozen receiver attempts disjoint TEST worlds under each arm
context -> simulator scores -> TRR table + kill observations -> receipt.

Modes:
* LEGACY dev smoke (no --manifest): single tier, --n-train/--n-test worlds
  from --seed/--seed+1; arm list = 6 core + g_flat_file (7; --gated adds the
  3 *_gated variants -> the 10 prereg contexts).
* MANIFEST mode (--manifest <hswm-f3v2-sealed-manifest/v1>): the cohort is
  AUTHORITATIVE — worlds are regenerated from the locked seeds/sizes/tiers
  and every world_sha256 is verified against the manifest (drift = run void);
  arms, budget hard_cap, and the bootstrap estimation block come from the
  manifest.  --tier only selects the judgment/kills tier (default hard).

Live-call gate (sealed discipline): --live is REFUSED unless the manifest
mode is "sealed" or --dev is explicitly passed (live_gate, pure).  Without
--live the runner is offline/scripted (dry-run).  Receipt mode: "sealed"
iff the manifest is sealed and --dev is not passed; stage is SEALED only
for a LIVE sealed run — a scripted dry-run of a sealed manifest keeps
mode="sealed" (config binding) but stage DEVELOPMENT_ONLY, because scripted
numbers never carry sealed weight.  preregistration_receipt_sha256 is bound
into the receipt from the manifest.

Live-call budget (hard cap via f2.Budget):
  calls = n_train (donor experience)
        + n_train (receiver train ZS — feeds b_self lessons AND the
                   disagreement gate)
        + n_contexts * n_test.
  Legacy dev-4 (4+4, 7 arms) = 4+4+28 = 36; --gated (10 contexts) = 48.
  Default cap without a manifest is 30 (shared-box discipline), so a legacy
  default LIVE plan is REFUSED at preflight: pass --max-calls deliberately
  or trim --n-test.  With --manifest the cap defaults to the manifest
  budget hard_cap (locked prereg: 2*48 + 10*512 = 5216 <= 5400).

DRY-RUN scripted chats (offline, exact-table, fail-closed on a miss):
  * donor train       = strategy_solver on every train world (all correct);
  * receiver train ZS = idx%4==1 -> strategy_solver (one success so the
    disagreement gate has a negative), idx%4==2 -> blast_solver, otherwise
    naive_batch_solver (both fail on hard tier by construction);
  * receiver test     = DRY_OUTCOMES per arm (1 -> strategy_solver, 0 ->
    naive_batch_solver).  Calibrated for hard tier (on mid tier the batch
    solver PASSES, so scripted "failures" only bite on hard).
The dry run validates the full pipeline including the receipt write; its
numbers are scripted, never measurements.

Endpoints: default http://192.168.0.23:8000 (dgx .0/24 LAN; the canary's
192.168.219.102 default is dead).  --receiver-endpoint defaults to
--endpoint (the canary used :8001 for qwen3-4b-real).  Sequential, <=2
concurrent like the canary gate.

Usage:
  python3 -m _research.f_series.f3v2_dev_smoke                          # offline dry-run (legacy)
  python3 -m _research.f_series.f3v2_dev_smoke --gated                  # 10 contexts
  python3 -m _research.f_series.f3v2_dev_smoke --manifest <sealed.json> # sealed rehearsal (scripted)
  python3 -m _research.f_series.f3v2_dev_smoke --manifest <sealed.json> --live   # SEALED RUN
  python3 -m _research.f_series.f3v2_dev_smoke --manifest <dev.json> --live --dev # dev-weight live
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

from . import REPO_ROOT
from . import f3v2_arms as arms
from . import f3v2_procedural_worlds as fw

RECEIPT_DIR = REPO_ROOT / "receipts"
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
    "g_flat_file": (0, 1, 0, 1),     # strong null: content of (b), flat
    "b_naive_donor_gated": (0, 0, 0, 0),
    "c_abstracted_gated": (1, 1, 0, 1),
    "d_contrast_gated": (1, 0, 1, 0),
}


def live_gate(live: bool, dev: bool, manifest_mode: str | None) -> str | None:
    """Sealed-run gating (pure): --live needs a sealed manifest or --dev."""
    if not live:
        return None
    if manifest_mode == "sealed" or dev:
        return None
    return ("--live refused: manifest mode is "
            f"{manifest_mode or 'absent (legacy dev smoke)'} (not sealed); "
            "pass --dev to confirm a development-weight live run, or seal "
            "the manifest first (f3v2_sealed_prep.py --seal)")


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
                    help="chat seed; legacy world seeds default to seed / seed+1")
    ap.add_argument("--train-seed", type=int, default=0)
    ap.add_argument("--test-seed", type=int, default=0)
    ap.add_argument("--n-train", type=int, default=4)
    ap.add_argument("--n-test", type=int, default=4)
    ap.add_argument("--tier", default="hard", choices=fw.TIERS,
                    help="world tier (legacy mode) / judgment+kills tier")
    ap.add_argument("--max-tokens", type=int, default=768)
    ap.add_argument("--max-calls", type=int, default=0,
                    help="hard live-call cap; 0 = manifest hard_cap when "
                         "--manifest is given, else 30 (shared-box discipline)")
    ap.add_argument("--gated", action="store_true",
                    help="legacy mode: add the 3 gate-on arm variants "
                         "(manifest mode: the manifest arm list is authoritative)")
    ap.add_argument("--boot-reps", type=int, default=0,
                    help="paired bootstrap replicates; 0 = manifest estimation "
                         "block when --manifest, else 10000")
    ap.add_argument("--manifest", default="",
                    help="hswm-f3v2-sealed-manifest/v1 path: cohort/arms/"
                         "budget/estimation become manifest-authoritative")
    ap.add_argument("--dev", action="store_true",
                    help="explicitly run a development-weight pass even with "
                         "a manifest (required for --live on a dev manifest; "
                         "demotes a sealed manifest to development weight)")
    ap.add_argument("--live", action="store_true",
                    help="REQUIRED for any network call; refused without a "
                         "sealed manifest or --dev")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)

    manifest = None
    manifest_sha = None
    if args.manifest:
        manifest_path = Path(args.manifest)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        if manifest.get("schema_version") != arms.MANIFEST_SCHEMA:
            ap.error(f"manifest schema is not {arms.MANIFEST_SCHEMA}")
    gate_err = live_gate(args.live, args.dev,
                         manifest.get("mode") if manifest else None)
    if gate_err:
        ap.error(gate_err)

    if manifest:
        cohort = arms.cohort_from_manifest(manifest)  # regenerates + verifies
        arm_ids = list(manifest["arms"])
        max_calls = args.max_calls or int(manifest["budget"]["hard_cap"])
        estimation = manifest.get("estimation") or {}
        boot_reps = args.boot_reps or int(
            estimation.get("bootstrap_reps", arms.BOOT_REPS))
        boot_seed = int(estimation.get("bootstrap_seed", args.seed))
        train_seed = manifest["cohort"]["train"]["seed"]
        test_seed = manifest["cohort"]["test"]["seed"]
    else:
        train_seed = args.train_seed or args.seed
        test_seed = args.test_seed or args.seed + 1
        cohort = arms.make_splits(args.n_train, args.n_test, args.tier,
                                  train_seed, test_seed)
        arm_ids = list(arms.CORE_ARM_IDS) + [arms.FLAT_FILE_ARM]
        if args.gated:
            arm_ids += list(arms.GATED_ARM_IDS)
        max_calls = args.max_calls or 30
        boot_reps = args.boot_reps or arms.BOOT_REPS
        boot_seed = args.seed
    plan_calls = 2 * len(cohort["train"]) + len(arm_ids) * len(cohort["test"])

    t0 = time.time()
    ts = int(t0)
    out_path = Path(args.out) if args.out else (
        RECEIPT_DIR / f"f3v2_arms_smoke_{'live' if args.live else 'dry'}_{ts}.json")

    budget = None
    endpoint_v1 = receiver_endpoint_v1 = "scripted-offline"
    if args.live:
        if plan_calls > max_calls:
            ap.error(f"live plan needs {plan_calls} calls > cap {max_calls} "
                     f"(2*n_train + n_contexts*n_test); raise --max-calls "
                     "deliberately or trim the panel")
        # lazy imports: the dry-run path (and the offline test suite) never
        # touches the f2/hswm dependency chain or any socket.
        from . import f2_delta_w_credit as f2
        from . import f3v2_canary_gate as gate
        budget = f2.Budget(max_calls)
        endpoint_v1 = gate._normalize_endpoint(args.endpoint)
        receiver_endpoint_v1 = gate._normalize_endpoint(
            args.receiver_endpoint or args.endpoint)
        donor_chat = f2.CachedOpenAIChat(endpoint_v1, budget)
        receiver_chat = f2.CachedOpenAIChat(receiver_endpoint_v1, budget)
    else:
        donor_chat = arms.ScriptedChat()
        receiver_chat = arms.ScriptedChat()
        _fill_train_table(donor_chat, args.donor_model, cohort["train"],
                          "donor")
        _fill_train_table(receiver_chat, args.receiver_model,
                          cohort["train"], "receiver")

    aborted = None
    receipt = {}
    receiver_arm_chats: list = []
    try:
        donor_trajs = arms.run_experience(
            donor_chat, args.donor_model, cohort["train"], seed=args.seed,
            max_tokens=args.max_tokens)
        recv_train_trajs = arms.run_experience(
            receiver_chat, args.receiver_model, cohort["train"],
            seed=args.seed, max_tokens=args.max_tokens)
        lesson_sets = arms.build_lesson_sets(cohort["train"], donor_trajs,
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
                _fill_arm_table(chat, args.receiver_model, cohort["test"],
                                [arm], lesson_sets, embedder)
                receiver_arm_chats.append(chat)
            results.update(arms.evaluate_arms(
                chat, args.receiver_model, cohort["test"], [arm], lesson_sets,
                embedder=embedder, seed=args.seed,
                max_tokens=args.max_tokens))
        trr = arms.trr_table(results)
        kills = arms.evaluate_kills(trr[args.tier], reps=boot_reps,
                                    seed=boot_seed)
        config = vars(args) | {
            "train_seed": train_seed, "test_seed": test_seed,
            "arm_ids": arm_ids, "plan_calls": plan_calls,
            "max_calls_effective": max_calls,
            "boot_reps_effective": boot_reps, "boot_seed_effective": boot_seed,
            "manifest_mode": manifest.get("mode") if manifest else None,
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
            "max_calls": max_calls if args.live else 0,
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
                    for w in cohort["train"]},
                "n_lessons": {name: len(lesson_sets[name]) for name in
                              ("naive", "abstracted", "contrast", "b_self",
                               "placebo")},
                "gate_note": ("flag = receiver failed the train world while "
                              "the donor succeeded on it; *_gated arms inject "
                              "only flagged lessons (Agent KB: gate가 전이 "
                              "성립 조건)."),
            },
        }
        if manifest:
            extra["sealed_manifest"] = {
                "file": args.manifest, "sha256": manifest_sha,
                "mode": manifest.get("mode"),
                "run_id": manifest.get("run_id")}
        if args.live:
            from . import f3v2_canary_gate as gate
            extra["models_served"] = {
                "donor_endpoint": endpoint_v1,
                "donor": gate._list_models(endpoint_v1),
                "receiver_endpoint": receiver_endpoint_v1,
                "receiver": gate._list_models(receiver_endpoint_v1),
            }
        sealed_weight = bool(manifest and manifest.get("mode") == "sealed"
                             and not args.dev)
        receipt = arms.build_receipt(
            script_path=Path(__file__), config=config,
            train_worlds=cohort["train"], test_worlds=cohort["test"],
            arm_results=results, trr=trr, kills=kills,
            budget_block=budget_block,
            wall_clock_s=round(time.time() - t0, 1),
            mode="sealed" if sealed_weight else "development",
            stage="SEALED" if (sealed_weight and args.live)
                  else "DEVELOPMENT_ONLY",
            preregistration_receipt_sha256=(
                manifest.get("preregistration_receipt_sha256")
                if manifest else None),
            extra=extra)
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
