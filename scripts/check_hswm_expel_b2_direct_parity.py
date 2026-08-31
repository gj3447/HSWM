"""Run pinned upstream ExpeL and compare its capture with the HSWM adapter."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hswm.experiments.expel_b2_adapter import (
    ExpelB2AdapterError,
    ExpelDirectConfig,
    SuccessfulTrajectory,
    audit_expel_direct_wrapper_parity,
    bind_expel_runtime_source,
    build_expel_b2_wrapper_projection,
    verify_expel_runtime_pin,
    verify_pinned_expel_source,
)
from hswm.selfmod.contracts import canonical_sha256


PRIOR_ROOT = (
    ROOT / "_research/causal_composition/priors/expel_b2_text_lesson_v1"
)
SOURCE_PIN = PRIOR_ROOT / "source_pin.v1.json"
RUNTIME_PIN = PRIOR_ROOT / "runtime/runtime_pin.v1.json"
FIXTURE = PRIOR_ROOT / "runtime/direct_capture_fixture.v1.json"
UPSTREAM_CAPTURE = ROOT / "scripts/capture_hswm_expel_b2_upstream.py"
WRAPPER_VECTOR_CAPTURE = ROOT / "scripts/capture_hswm_expel_b2_wrapper_vector.py"


def _read_fixture(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ExpelB2AdapterError("direct capture fixture is unavailable") from error
    if not isinstance(value, dict):
        raise ExpelB2AdapterError("direct capture fixture must be an object")
    digest = value.get("fixture_sha256")
    unsigned = dict(value)
    unsigned.pop("fixture_sha256", None)
    if not isinstance(digest, str) or digest != canonical_sha256(unsigned):
        raise ExpelB2AdapterError("direct capture fixture identity drifted")
    return value


def _sealed_environment(tiktoken_cache: Path) -> dict[str, str]:
    environment = dict(os.environ)
    for name in (
        "OPENAI_API_KEY",
        "HF_TOKEN",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        environment.pop(name, None)
    environment.update(
        {
            "PYTHONHASHSEED": "0",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "TOKENIZERS_PARALLELISM": "false",
            "TIKTOKEN_CACHE_DIR": str(tiktoken_cache),
        }
    )
    return environment


def _run_capture(
    command: list[str], *, tiktoken_cache: Path, label: str
) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=_sealed_environment(tiktoken_cache),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        detail = result.stderr.strip().splitlines()[-1:] or ["unknown capture error"]
        raise ExpelB2AdapterError(f"{label} failed: " + detail[0])
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ExpelB2AdapterError(f"{label} returned invalid JSON") from error
    if not isinstance(value, dict):
        raise ExpelB2AdapterError(f"{label} must be an object")
    return value


def _capture_direct(
    *,
    pinned_python: Path,
    source_root: Path,
    model_root: Path,
    tiktoken_cache: Path,
) -> dict[str, Any]:
    command = [
        str(pinned_python),
        str(UPSTREAM_CAPTURE),
        "--source-root",
        str(source_root),
        "--source-pin",
        str(SOURCE_PIN),
        "--runtime-pin",
        str(RUNTIME_PIN),
        "--fixture",
        str(FIXTURE),
        "--model-root",
        str(model_root),
        "--tiktoken-cache",
        str(tiktoken_cache),
    ]
    return _run_capture(
        command,
        tiktoken_cache=tiktoken_cache,
        label="upstream direct capture",
    )


def _capture_wrapper_vector(
    *,
    pinned_python: Path,
    model_root: Path,
    tiktoken_cache: Path,
) -> dict[str, Any]:
    command = [
        str(pinned_python),
        str(WRAPPER_VECTOR_CAPTURE),
        "--runtime-pin",
        str(RUNTIME_PIN),
        "--fixture",
        str(FIXTURE),
        "--model-root",
        str(model_root),
        "--tiktoken-cache",
        str(tiktoken_cache),
    ]
    return _run_capture(
        command,
        tiktoken_cache=tiktoken_cache,
        label="independent wrapper vector capture",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pinned-python", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--tiktoken-cache", required=True, type=Path)
    args = parser.parse_args()

    runtime_pin = verify_expel_runtime_pin(RUNTIME_PIN)
    fixture = _read_fixture(FIXTURE)
    source = bind_expel_runtime_source(
        verify_pinned_expel_source(args.source_root, source_pin_path=SOURCE_PIN),
        RUNTIME_PIN,
    )
    direct = _capture_direct(
        pinned_python=args.pinned_python,
        source_root=args.source_root,
        model_root=args.model_root,
        tiktoken_cache=args.tiktoken_cache,
    )
    wrapper_capture = _capture_wrapper_vector(
        pinned_python=args.pinned_python,
        model_root=args.model_root,
        tiktoken_cache=args.tiktoken_cache,
    )
    capture = direct.get("runtime_capture")
    if not isinstance(capture, dict):
        raise ExpelB2AdapterError("direct runtime capture metadata is unavailable")
    counts = wrapper_capture.get("trajectory_token_counts")
    ranked = wrapper_capture.get("ranked_task_ids")
    if not isinstance(counts, dict) or not isinstance(ranked, list):
        raise ExpelB2AdapterError("wrapper vector measurements are unavailable")

    trajectories = tuple(
        SuccessfulTrajectory(
            task_id=row["task_id"],
            env_name=row["env_name"],
            trajectory=row["trajectory"],
            token_count=counts[row["task_id"]],
            write_ordinal=row["write_ordinal"],
        )
        for row in fixture["successful_trajectories"]
    )
    wrapper = build_expel_b2_wrapper_projection(
        source,
        rules=fixture["rules"],
        successful_trajectories=trajectories,
        ranked_task_ids=ranked,
        current_task=fixture["current_task"],
        current_env_name=fixture["current_env_name"],
        config=ExpelDirectConfig(**fixture["config"]),
        ai_name=fixture["ai_name"],
    )
    wrapper["wrapper_runtime_capture"] = wrapper_capture
    wrapper.pop("projection_sha256")
    wrapper["projection_sha256"] = canonical_sha256(wrapper)
    parity = audit_expel_direct_wrapper_parity(direct, wrapper)
    output = {
        "schema_version": "hswm-expel-b2-executed-direct-parity-check/v1",
        "status": parity["status"],
        "runtime_pin_sha256": runtime_pin["runtime_pin_sha256"],
        "fixture_sha256": fixture["fixture_sha256"],
        "direct_projection_sha256": direct["projection_sha256"],
        "wrapper_projection_sha256": wrapper["projection_sha256"],
        "parity": parity,
        "direct_runtime_measurements": {
            "embedding_trace_sha256": capture["embedding_trace_sha256"],
            "faiss_index_sha256": capture["faiss_index_sha256"],
            "physical_vector_index_builds": capture["physical_vector_index_builds"],
            "physical_document_embedding_batches": capture[
                "physical_document_embedding_batches"
            ],
            "physical_query_embedding_calls": capture[
                "physical_query_embedding_calls"
            ],
            "network_connect_attempts": capture["network_connect_attempts"],
            "llm_calls": capture["llm_calls"],
            "simulator_steps": capture["simulator_steps"],
        },
        "independent_wrapper_vector_measurements": {
            "capture_sha256": wrapper_capture["capture_sha256"],
            "embedding_trace_sha256": wrapper_capture["embedding_trace_sha256"],
            "faiss_index_sha256": wrapper_capture["faiss_index_sha256"],
            "physical_vector_index_builds": wrapper_capture[
                "physical_vector_index_builds"
            ],
            "physical_document_embedding_batches": wrapper_capture[
                "physical_document_embedding_batches"
            ],
            "physical_query_embedding_calls": wrapper_capture[
                "physical_query_embedding_calls"
            ],
            "network_connect_attempts": wrapper_capture[
                "network_connect_attempts"
            ],
            "llm_calls": wrapper_capture["llm_calls"],
            "simulator_steps": wrapper_capture["simulator_steps"],
            "upstream_agent_imported": wrapper_capture["upstream_agent_imported"],
        },
        "claim_boundary": parity["claim_boundary"],
        "next_required_boundary": (
            "QUALIFY_AN_INDEPENDENTLY_OWNED_OUTCOME_AND_EVALUATION_BOUNDARY_"
            "BEFORE_ANY_EFFICACY_OCCURRENCE"
        ),
    }
    output["check_sha256"] = canonical_sha256(output)
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
