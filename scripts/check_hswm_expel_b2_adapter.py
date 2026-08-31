"""Offline engineering check for the pinned ExpeL B2 two-channel adapter."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hswm.experiments.expel_b2_adapter import (
    ExpelDirectConfig,
    SuccessfulTrajectory,
    audit_expel_direct_wrapper_parity,
    build_expel_b2_wrapper_projection,
    semantic_reference_from_wrapper,
    verify_pinned_expel_source,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_root", type=Path)
    args = parser.parse_args()

    source = verify_pinned_expel_source(args.source_root)
    config = ExpelDirectConfig(
        rule_cap=10,
        rule_cap_resolution="PAPER_ALFWORLD_COMMAND_EXPLICIT_10_RULE_CAP",
        max_fewshot_tokens=128,
        tokenizer_revision="ENGINEERING_FIXTURE_TOKEN_COUNTS_ONLY",
        embedding_model_revision=(
            "sentence-transformers/all-mpnet-base-v2:UNRESOLVED_REVISION"
        ),
        retriever_revision="langchain-0.0.181:FAISS_TASK_SIMILARITY",
    )
    wrapper = build_expel_b2_wrapper_projection(
        source,
        rules=("inspect the environment before acting", "complete prerequisites first"),
        successful_trajectories=(
            SuccessfulTrajectory(
                "clean apple___1", "pick_clean_then_place", "fixture trajectory A", 4, 0
            ),
            SuccessfulTrajectory(
                "clean mug___2", "pick_clean_then_place", "fixture trajectory B", 4, 1
            ),
        ),
        ranked_task_ids=("clean mug___2", "clean apple___1"),
        current_task="clean bowl___3",
        current_env_name="pick_clean_then_place",
        config=config,
    )
    reference = semantic_reference_from_wrapper(wrapper)
    parity = audit_expel_direct_wrapper_parity(reference, wrapper)
    output = {
        "source_binding": source.source_binding,
        "observed_defaults": source.observed_defaults,
        "engineering_parity": parity,
        "next_required_boundary": (
            "PIN_TRANSITIVE_DEPENDENCIES_AND_CAPTURE_EXECUTED_B2_EXPEL_DIRECT_"
            "BEFORE_CREDITING_DIRECT_WRAPPER_PARITY"
        ),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
