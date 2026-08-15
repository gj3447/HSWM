"""F0 semantic measurement — does the regeneration recover the SPECIFIC node's
meaning, controlling for topical inflation?

Consumes cached regenerations (RESULTS_vllm_*.json) so no re-generation. For each
pair computes an independent semantic score against (a) its OWN gold [matched] and
(b) a cyclically shifted gold [mismatched, deterministic null control]. The
signal for premise P is the GAP = mean_matched - mean_mismatched: a positive gap
means the regeneration is specifically closer to its own node's doc prose than to
another node's — i.e. meaning is *specifically* derivable, not just topical.

This produces a local_record-evidence-record/v1-shaped measurement with NO verdict —
HSWM_LOCAL_RECORD's deterministic judge derives the verdict (see PREREG.md, LOCAL_RECORD_*).

Usage:
    python run_f0_semantic.py --scorer mock                       # harness smoke
    python run_f0_semantic.py --scorer embedding --regen RESULTS_vllm_2026-07-21.json --out EVIDENCE_...json
    python run_f0_semantic.py --scorer llmjudge  --regen ...

# KG: ATOM_Skill_longinus  (F0 semantic metric, HSWM lens-duality design §9)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from semantic_score import embedding_cosines, llm_judge_scores, mock_cosines

HERE = Path(__file__).parent


def _shift(xs: list, k: int = 1) -> list:
    """Deterministic cyclic shift for the mismatched null control."""
    n = len(xs)
    return [xs[(i + k) % n] for i in range(n)]


def run_semantic(pairs: list[dict], regen: dict[str, str], scorer) -> dict:
    fids = [p["field_id"] for p in pairs]
    golds = [p["doc_prose"] for p in pairs]
    preds = [regen[f] for f in fids]
    mismatched_golds = _shift(golds, 1)

    matched = scorer(preds, golds)
    mismatched = scorer(preds, mismatched_golds)

    n = len(fids) or 1
    mean_matched = round(sum(matched) / n, 4)
    mean_mismatched = round(sum(mismatched) / n, 4)
    gap = round(mean_matched - mean_mismatched, 4)
    return {
        "n_pairs": len(fids),
        "mean_matched": mean_matched,
        "mean_mismatched": mean_mismatched,
        "gap": gap,
        "per_pair": [
            {"field_id": fids[i], "matched": matched[i], "mismatched": mismatched[i]}
            for i in range(len(fids))
        ],
    }


def _load_pairs() -> list[dict]:
    return json.loads((HERE / "toy_pairs.json").read_text())["pairs"]


def _load_regen(path: str) -> dict[str, str]:
    data = json.loads(Path(path).read_text())
    return {r["field_id"]: r["regenerated"] for r in data["per_pair"]}


_SCORERS = {"embedding": embedding_cosines, "llmjudge": llm_judge_scores, "mock": mock_cosines}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scorer", default="mock", choices=list(_SCORERS))
    ap.add_argument("--regen", default="RESULTS_vllm_2026-07-21.json")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    pairs = _load_pairs()
    if args.scorer == "mock":
        regen = {p["field_id"]: p["node_content"] for p in pairs}  # stand-in, tests only
    else:
        regen = _load_regen(str(HERE / args.regen))

    result = run_semantic(pairs, regen, _SCORERS[args.scorer])
    result["scorer"] = args.scorer
    result["evidence_kind"] = "local_record-evidence-record/v1-measurement"
    result["note"] = "NO verdict here — HSWM_LOCAL_RECORD deterministic judge derives it from the locked prediction."
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.out:
        Path(str(HERE / args.out)).write_text(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
