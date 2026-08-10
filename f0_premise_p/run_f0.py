"""F0 harness — measure whether harness-doc prose is regenerable from HSWM node
content (premise P). See PREREG.md for the locked prediction and bands.

Usage:
    python run_f0.py --backend stub          # LLM-free harness smoke
    python run_f0.py --backend vllm          # real dgx vLLM run (needs F0_LLM_*)
    python run_f0.py --backend echo          # structural floor

Verdict bands (locked, PREREG): mean char-bigram F1
    >= 0.80  P_SUPPORTED   (asymmetric lens sufficient)
    <= 0.50  P_REFUTED     (symmetric-lens candidate for this axis)
    else     INCONCLUSIVE  (toy insufficient -> real data)

# KG: ATOM_Skill_longinus  (F0 falsifier, HSWM lens-duality design §9)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from f1_score import score_pair
from regenerate import get_regenerator

HERE = Path(__file__).parent

# Locked bands (PREREG) — do not tune to results.
P_SUPPORTED_AT = 0.80
P_REFUTED_AT = 0.50


def verdict(mean_char_f1: float) -> str:
    if mean_char_f1 >= P_SUPPORTED_AT:
        return "P_SUPPORTED"
    if mean_char_f1 <= P_REFUTED_AT:
        return "P_REFUTED"
    return "INCONCLUSIVE"


def run_f0(pairs: list[dict], regenerate) -> dict:
    """Run the regenerator over pairs, score, aggregate, judge."""
    rows = []
    for p in pairs:
        pred = regenerate(p["node_content"])
        sc = score_pair(pred, p["doc_prose"])
        rows.append(
            {
                "field_id": p["field_id"],
                "regenerated": pred,
                "char_bigram_f1": sc["char_bigram"]["f1"],
                "word_f1": sc["word"]["f1"],
            }
        )
    n = len(rows) or 1
    mean_char = round(sum(r["char_bigram_f1"] for r in rows) / n, 4)
    mean_word = round(sum(r["word_f1"] for r in rows) / n, 4)
    return {
        "n_pairs": len(rows),
        "mean_char_bigram_f1": mean_char,
        "mean_word_f1": mean_word,
        "verdict": verdict(mean_char),
        "bands": {"P_SUPPORTED_at": P_SUPPORTED_AT, "P_REFUTED_at": P_REFUTED_AT},
        "per_pair": rows,
    }


def _load_pairs() -> list[dict]:
    return json.loads((HERE / "toy_pairs.json").read_text())["pairs"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="stub", choices=["stub", "echo", "vllm"])
    ap.add_argument("--out", default=None, help="write result JSON to this path")
    args = ap.parse_args()

    result = run_f0(_load_pairs(), get_regenerator(args.backend))
    result["backend"] = args.backend
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
