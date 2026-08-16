"""F3v2 canary adoption gate (prereg §2) — DEVELOPMENT_ONLY measurement.

PREREG (draft, sha-pinned in the receipt):
  prereg/PREREG_F3V2_HARDER_TRANSFER_2026-07-26.md

Adoption gate (prereg §2, runs BEFORE any F3v2 arm experiment): the (2)(3)
knowledge layers (workflow / norm) must not be derivable by the receiver
without donor experience.  On hard-tier worlds, zero-shot:

  * receiver accuracy  <= 30%
  * donor accuracy     >= 70%
  * donor - receiver baseline gap >= 15pp

All three must hold for gate PASS; otherwise difficulty retune (prereg:
"미달 시 난이도 재조정"), sealed runs stay forbidden.  Scoring is the
deterministic world simulator (no judge, no gold reveal at run time — the
rules are in the prompt, the optimal sequence is what the simulator checks).

Backend: live OpenAI-compatible endpoints (shared vLLM boxes — this script is
strictly sequential, <=2 concurrent, and hard-capped at 2*n live chat calls,
default 16, max 20).  Donor and receiver may live on different endpoints
(--receiver-endpoint, default = --endpoint).  Receiver default qwen3-4b is a
DEV STAND-IN: the real sealed receiver is qwen3:14b, pending the dgx window.
2026-07-26 confound resolved: the first receiver stand-in (qwen3-4b on :8000)
turned out to be a vLLM alias of the donor weights (shared root
Qwen/Qwen3.6-27B; 8/8 identical action sequences, receipt ..._1785037859);
the real Qwen3-4B is now served as qwen3-4b-real on :8001 (root Qwen/Qwen3-4B,
verified via /v1/models).  Both endpoints' /v1/models listings are recorded
verbatim in the receipt for served-model identity honesty.

Receipts are always mode="development" measurements, DEVELOPMENT_ONLY stage;
the scientific judgment belongs to the HSWM_LOCAL_RECORD gate, never to this file.

Usage:
  .venv/bin/python -m _research.f_series.f3v2_canary_gate                      # n=8, 16 calls
  .venv/bin/python -m _research.f_series.f3v2_canary_gate --smoke              # n=4, 8 calls
  .venv/bin/python -m _research.f_series.f3v2_canary_gate --n 10 --seed 20260726
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.request

from . import REPO_ROOT, source_path
from . import f2_delta_w_credit as f2
from . import f3v2_procedural_worlds as fw

PREREG_PATH = REPO_ROOT / "prereg/PREREG_F3V2_HARDER_TRANSFER_2026-07-26.md"
RECEIPT_DIR = REPO_ROOT / "receipts"

RECEIVER_ZS_MAX = 0.30   # prereg §2: receiver zero-shot hard-tier ceiling
DONOR_ZS_MIN = 0.70      # prereg §2: donor accuracy floor
GAP_MIN_PP = 15.0        # prereg §2: donor-receiver baseline gap floor (pp)
MAX_LIVE_CALLS = 20      # shared-box budget: <=20 live calls total

SYSTEM_PROMPT = (
    "You are an agent solving synthetic foundry-world planning tasks. Read "
    "the world rules carefully, track every ore's state step by step, and "
    "reply with JSON only.")


class GateAbort(RuntimeError):
    pass


def _normalize_endpoint(endpoint: str) -> str:
    ep = endpoint.rstrip("/")
    return ep if ep.endswith("/v1") else ep + "/v1"


def _list_models(endpoint_v1: str, timeout: float = 10.0) -> dict:
    req = urllib.request.Request(endpoint_v1 + "/models", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as err:  # noqa: BLE001 — recorded, not fatal
        return {"error": f"{type(err).__name__}: {err}"}


def _eval_model(chat, model: str, worlds: list[dict], seed: int,
                max_tokens: int) -> dict:
    rows = []
    for world in worlds:
        prompt = fw.render_prompt(world)
        meta = chat.chat(model=model, system=SYSTEM_PROMPT, user=prompt,
                         seed=seed, max_tokens=max_tokens)
        actions = fw.parse_model_actions(meta["text"])
        ok, reason = (fw.verify_solution(world, actions) if actions is not None
                      else (False, "parse_failure: no JSON actions object"))
        rows.append({
            "world_id": world["world_id"],
            "n_items": len(world["items"]),
            "optimal_len": world["optimal_len"],
            "step_cap": world["step_cap"],
            "parse_ok": actions is not None,
            "actions": actions,
            "correct": bool(ok),
            "reason": reason,
            "cached": meta["cached"],
            "usage": meta["usage"],
            "request_sha256": meta["request_sha256"],
        })
    correct = sum(r["correct"] for r in rows)
    return {"model": model, "n": len(rows), "n_correct": correct,
            "accuracy": round(correct / len(rows), 4) if rows else None,
            "rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--endpoint", default="http://192.168.0.23:8000",
                    help="donor endpoint (dgx; LAN reverted to .0/24 on 2026-07-26, "
                         "the .219.102 default from the router-swap window is dead)")
    ap.add_argument("--receiver-endpoint", default="",
                    help="receiver endpoint; default = --endpoint value")
    ap.add_argument("--donor-model", default="qwen3.6-27b")
    ap.add_argument("--receiver-model", default="qwen3-4b")
    ap.add_argument("--seed", type=int, default=20260726)
    ap.add_argument("--n", type=int, default=8,
                    help="hard-tier tasks per model; live calls = 2n <= 20")
    ap.add_argument("--max-tokens", type=int, default=768)
    ap.add_argument("--smoke", action="store_true", help="n=4 (8 live calls)")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    if args.smoke:
        args.n = 4
    if not 1 <= args.n <= MAX_LIVE_CALLS // 2:
        ap.error(f"--n must keep 2n <= {MAX_LIVE_CALLS} live calls")

    t0 = time.time()
    ts = int(t0)
    endpoint_v1 = _normalize_endpoint(args.endpoint)
    receiver_endpoint_v1 = _normalize_endpoint(
        args.receiver_endpoint or args.endpoint)
    out_path = Path(args.out) if args.out else (
        RECEIPT_DIR / f"f3v2_canary_gate_dev_{ts}.json")

    worlds = fw.generate_batch(args.n, "hard", args.seed)
    receipt = {
        "schema_version": "hswm-f3v2-canary-gate-receipt/v1",
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
                source_path("f3v2_procedural_worlds.py").read_bytes()).hexdigest(),
            "f2_delta_w_credit.py": hashlib.sha256(
                source_path("f2_delta_w_credit.py").read_bytes()).hexdigest(),
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
            "note": ("DEV STAND-IN for the sealed qwen3:14b receiver (pending "
                     "dgx window); both models frozen, input channel only, "
                     "identical prompts, simulator-scored. 2026-07-26 alias "
                     "confound resolved: real Qwen3-4B served as "
                     "qwen3-4b-real on its own container (root Qwen/Qwen3-4B "
                     "per /v1/models), replacing the :8000 alias that shared "
                     "donor weights."),
        },
        "honesty": ("grounded measurement only; no scientific claim; judgment "
                    "is the gate's. DEVELOPMENT_ONLY: nothing sealed."),
        "thresholds": {"receiver_zs_hard_max": RECEIVER_ZS_MAX,
                       "donor_zs_hard_min": DONOR_ZS_MIN,
                       "baseline_gap_min_pp": GAP_MIN_PP},
        "worlds": [{"world_id": w["world_id"], "seed": w["seed"],
                    "n_items": len(w["items"]), "items": w["items"],
                    "optimal_len": w["optimal_len"], "step_cap": w["step_cap"],
                    "constraints": w["constraints"],
                    "watermark": w["watermark"],
                    "world_sha256": fw.world_sha256(w)} for w in worlds],
        "models_served": {
            "donor_endpoint": endpoint_v1,
            "donor": _list_models(endpoint_v1),
            "receiver_endpoint": receiver_endpoint_v1,
            "receiver": _list_models(receiver_endpoint_v1),
        },
    }

    budget = f2.Budget(2 * args.n)
    donor = f2.CachedOpenAIChat(endpoint_v1, budget)
    receiver = f2.CachedOpenAIChat(receiver_endpoint_v1, budget)
    aborted = None
    try:
        rec = _eval_model(receiver, args.receiver_model, worlds, args.seed,
                          args.max_tokens)
        don = _eval_model(donor, args.donor_model, worlds, args.seed,
                          args.max_tokens)
        gap_pp = round((don["accuracy"] - rec["accuracy"]) * 100, 2)
        criteria = {
            "receiver_zs_hard_le_30pct": rec["accuracy"] <= RECEIVER_ZS_MAX,
            "donor_zs_hard_ge_70pct": don["accuracy"] >= DONOR_ZS_MIN,
            "baseline_gap_ge_15pp": gap_pp >= GAP_MIN_PP,
        }
        receipt["measurements"] = {
            "receiver_zs_hard_accuracy": rec["accuracy"],
            "donor_zs_hard_accuracy": don["accuracy"],
            "baseline_gap_pp": gap_pp,
            "receiver": rec, "donor": don,
        }
        receipt["gate"] = {
            "criteria": criteria,
            "verdict": "PASS" if all(criteria.values()) else "FAIL",
            "note": ("adoption gate, prereg §2: (2)(3) knowledge must be "
                     "underivable by the receiver without donor experience. "
                     "FAIL -> retune difficulty knobs (n_items, ladder, "
                     "decay_k, cap); sealed runs remain forbidden."),
        }
    except (GateAbort, f2.BudgetExceeded) as err:
        aborted = str(err)
    except Exception as err:  # noqa: BLE001
        aborted = f"{type(err).__name__}: {err}"

    receipt["llm_budget"] = {
        "max_calls": 2 * args.n, "used": budget.used,
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
    summary = {
        "receipt": str(out_path), "aborted": aborted,
        "gate": receipt.get("gate", {}).get("verdict"),
        "criteria": receipt.get("gate", {}).get("criteria"),
        "measurements": {k: receipt.get("measurements", {}).get(k) for k in
                         ("receiver_zs_hard_accuracy",
                          "donor_zs_hard_accuracy", "baseline_gap_pp")},
        "calls": receipt["llm_budget"],
        "wall_clock_s": receipt["wall_clock_s"],
    }
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    return 0 if aborted is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
