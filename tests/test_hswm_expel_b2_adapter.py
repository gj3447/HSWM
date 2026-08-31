from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from hswm.experiments.expel_b2_adapter import (
    CLAIM_BOUNDARY,
    DIRECT_ARM,
    EXPEL_LICENSE_SHA256,
    PINNED_FILE_SHA256,
    ExpelB2AdapterError,
    ExpelDirectConfig,
    PinnedExpelSource,
    SuccessfulTrajectory,
    audit_expel_direct_wrapper_parity,
    bind_expel_runtime_source,
    build_expel_b2_wrapper_projection,
    semantic_reference_from_wrapper,
    verify_expel_runtime_pin,
    verify_pinned_expel_source,
)
from hswm.selfmod.contracts import canonical_sha256


def _source() -> PinnedExpelSource:
    source_binding = {
        "prior_uid": "sym:Prior:expel-b2-text-lesson-v1",
        "repository_commit": "e41ec9a24823e7b560c561ab191441b56d9bcefc",
        "repository_tree": "8ba77f84284693ebbe12ba9a93bd32fd101a6922",
        "license_id": "Apache-2.0",
        "license_sha256": EXPEL_LICENSE_SHA256,
        "source_pin_sha256": "17f5c77e30b91ee23edff3cbf74e40d2c3d87048788bfe6a67c562cd66e40886",
        "pinned_file_sha256": PINNED_FILE_SHA256,
        "executable_dependency_closure": "NOT_PINNED",
    }
    source_binding["source_binding_sha256"] = canonical_sha256(source_binding)
    return PinnedExpelSource(
        source_binding=source_binding,
        system_template="You are {ai_name}. {instruction}",
        system_instruction="Follow the syntax of the examples closely when taking actions.",
        human_instruction_template=(
            "{instruction}You may take maximum of {max_steps} steps.\nHere are two examples:"
        ),
        instruction_fewshots_template="{instruction}\n\n{fewshots}\n\n(END OF EXAMPLES)\n",
        rule_template="RULES:\n{rules}\n",
        task_template="Now it's your turn!\n{task}",
        observed_defaults={
            "max_num_rules": 20,
            "fewshot_strategy": "task_similarity",
            "embedder_path": "all-mpnet-base-v2",
            "retriever_type": "knn",
            "buffer_retrieve_ratio": 4,
            "reranker": "none",
            "max_fewshot_tokens": "auto",
            "max_steps": 20,
            "num_fewshots": 2,
            "split": "eval_out_of_distribution",
        },
    )


def _config() -> ExpelDirectConfig:
    return ExpelDirectConfig(
        rule_cap=10,
        rule_cap_resolution="PAPER_ALFWORLD_COMMAND_EXPLICIT_10_RULE_CAP",
        max_fewshot_tokens=100,
        tokenizer_revision="tiktoken-0.4.0:gpt-3.5-turbo",
        embedding_model_revision="sentence-transformers/all-mpnet-base-v2:UNRESOLVED_REVISION",
        retriever_revision="langchain-0.0.181:FAISS_TASK_SIMILARITY",
    )


def _trajectories() -> tuple[SuccessfulTrajectory, ...]:
    return (
        SuccessfulTrajectory("clean apple___1", "pick_clean_then_place", "longer trajectory", 3, 0),
        SuccessfulTrajectory("clean apple___1", "pick_clean_then_place", "short", 2, 1),
        SuccessfulTrajectory("clean mug___2", "pick_clean_then_place", "mug trajectory", 3, 2),
        SuccessfulTrajectory("clean plate___3", "pick_clean_then_place", "too many tokens", 101, 3),
        SuccessfulTrajectory("clean bowl___4", "pick_clean_then_place", "bowl trajectory", 3, 4),
    )


def _projection():
    return build_expel_b2_wrapper_projection(
        _source(),
        rules=("inspect before acting", "clean before placing"),
        successful_trajectories=_trajectories(),
        ranked_task_ids=(
            "clean plate___3",
            "clean apple___1",
            "clean apple___1",
            "clean mug___2",
            "clean bowl___4",
        ),
        current_task="clean bowl___9",
        current_env_name="pick_clean_then_place",
        config=_config(),
    )


def test_two_channel_wrapper_preserves_numbered_rules_retrieved_fewshots_and_prompt() -> None:
    projection = _projection()
    assert projection["global_rules"]["utf8"] == (
        "1. inspect before acting\n2. clean before placing"
    )
    selected = projection["successful_trajectory_fewshots"]["selected"]
    assert [item["task_id"] for item in selected] == [
        "clean apple___1",
        "clean mug___2",
    ]
    assert [item["utf8"] for item in selected] == [
        "clean apple\nshort",
        "clean mug\nmug trajectory",
    ]
    prompt = projection["model_visible_prompt"]["messages"][0]
    assert prompt["role"] == "human"
    assert "You are alfred." in prompt["content_utf8"]
    assert "clean apple\nshort" in prompt["content_utf8"]
    assert "1. inspect before acting" in prompt["content_utf8"]
    assert prompt["content_utf8"].endswith("Now it's your turn!\nclean bowl")
    assert projection["resource_accounting"] == {
        "model_calls": 0,
        "retrieval_queries": 1,
        "token_counter_calls": 4,
        "logical_vector_documents": 4,
        "selected_fewshots": 2,
        "ranking_execution": "PINNED_EXPEL_FAISS_TASK_SIMILARITY",
    }
    assert CLAIM_BOUNDARY in projection["claim_boundary"]


def test_semantic_reference_parity_is_exact_but_does_not_claim_direct_runtime() -> None:
    wrapper = _projection()
    reference = semantic_reference_from_wrapper(wrapper)
    receipt = audit_expel_direct_wrapper_parity(reference, wrapper)
    assert receipt["exact"] is True
    assert receipt["direct_runtime_executed"] is False
    assert receipt["status"] == "PINNED_SOURCE_SEMANTIC_REFERENCE_EXACT_PARITY_ONLY"
    assert "NO_DIRECT_RUNTIME" in receipt["claim_boundary"]
    assert all(receipt["comparisons"].values())


def test_parity_fails_closed_on_one_model_visible_byte() -> None:
    wrapper = _projection()
    reference = semantic_reference_from_wrapper(wrapper)
    reference["model_visible_prompt"]["messages"][0]["content_utf8"] += " "
    reference_without_digest = dict(reference)
    reference_without_digest.pop("projection_sha256")
    reference["projection_sha256"] = canonical_sha256(reference_without_digest)
    with pytest.raises(ExpelB2AdapterError, match="model_visible_prompt_bytes"):
        audit_expel_direct_wrapper_parity(reference, wrapper)


def test_parity_refuses_direct_runtime_label_while_dependency_closure_is_open() -> None:
    wrapper = _projection()
    direct = semantic_reference_from_wrapper(wrapper)
    direct.pop("projection_sha256")
    direct["arm_id"] = DIRECT_ARM
    direct["projection_sha256"] = canonical_sha256(direct)
    with pytest.raises(ExpelB2AdapterError, match="dependency closure remains unpinned"):
        audit_expel_direct_wrapper_parity(direct, wrapper)


def test_executed_direct_capture_has_exact_wrapper_projection_parity() -> None:
    source = bind_expel_runtime_source(_source())
    wrapper = build_expel_b2_wrapper_projection(
        source,
        rules=("inspect before acting", "clean before placing"),
        successful_trajectories=_trajectories(),
        ranked_task_ids=(
            "clean plate___3",
            "clean apple___1",
            "clean apple___1",
            "clean mug___2",
            "clean bowl___4",
        ),
        current_task="clean bowl___9",
        current_env_name="pick_clean_then_place",
        config=_config(),
    )
    direct = deepcopy(wrapper)
    direct.pop("projection_sha256")
    direct["arm_id"] = DIRECT_ARM
    runtime_pin_sha256 = verify_expel_runtime_pin()["runtime_pin_sha256"]
    direct["runtime_capture"] = {
        "schema_version": "hswm-expel-b2-upstream-runtime-capture/v1",
        "runtime_pin_sha256": runtime_pin_sha256,
        "fixture_sha256": "f" * 64,
        "upstream_execution": True,
        "network_connect_attempts": [],
        "llm_calls": 0,
        "simulator_steps": 0,
        "physical_vector_index_builds": 2,
        "physical_document_embedding_batches": 2,
        "physical_query_embedding_calls": 1,
        "trajectory_token_counts": {"fixture": 1},
        "embedding_trace_sha256": "a" * 64,
        "faiss_index_sha256": "b" * 64,
        "installed_distributions_sha256": "c" * 64,
    }
    direct["projection_sha256"] = canonical_sha256(direct)
    receipt = audit_expel_direct_wrapper_parity(direct, wrapper)
    assert receipt["exact"] is True
    assert receipt["direct_runtime_executed"] is True
    assert receipt["status"] == (
        "DIRECT_UPSTREAM_EXECUTED_WRAPPER_PROJECTION_EXACT_PARITY"
    )
    assert "NOT_INDEPENDENT_WRAPPER_VECTOR_EXECUTION" in receipt["claim_boundary"]

    forged_direct = deepcopy(direct)
    forged_direct.pop("projection_sha256")
    forged_binding = forged_direct["source_binding"]
    forged_binding.pop("source_binding_sha256")
    forged_binding["executable_dependency_closure"] = (
        "PINNED_DIRECT_CAPTURE_SLICE:" + "e" * 64
    )
    forged_binding["source_binding_sha256"] = canonical_sha256(forged_binding)
    forged_direct["runtime_capture"]["runtime_pin_sha256"] = "e" * 64
    forged_direct["projection_sha256"] = canonical_sha256(forged_direct)
    with pytest.raises(ExpelB2AdapterError, match="runtime capture boundary"):
        audit_expel_direct_wrapper_parity(forged_direct, wrapper)

    wrapper_with_vector = deepcopy(wrapper)
    wrapper_with_vector.pop("projection_sha256")
    wrapper_capture = {
        "schema_version": "hswm-expel-b2-wrapper-vector-capture/v1",
        "runtime_pin_sha256": runtime_pin_sha256,
        "fixture_sha256": "f" * 64,
        "ranked_task_ids": direct["successful_trajectory_fewshots"][
            "ranked_task_ids"
        ],
        "trajectory_token_counts": {"fixture": 1},
        "vector_documents_sha256": direct["state_writes"][
            "task_vector_document_set_sha256"
        ],
        "embedding_trace_sha256": "a" * 64,
        "faiss_index_sha256": "b" * 64,
        "installed_distributions_sha256": "c" * 64,
        "physical_vector_index_builds": 2,
        "physical_document_embedding_batches": 2,
        "physical_query_embedding_calls": 1,
        "network_connect_attempts": [],
        "llm_calls": 0,
        "simulator_steps": 0,
        "upstream_agent_imported": False,
    }
    wrapper_capture["capture_sha256"] = canonical_sha256(wrapper_capture)
    wrapper_with_vector["wrapper_runtime_capture"] = wrapper_capture
    wrapper_with_vector["projection_sha256"] = canonical_sha256(wrapper_with_vector)
    full_receipt = audit_expel_direct_wrapper_parity(direct, wrapper_with_vector)
    assert full_receipt["status"] == (
        "DIRECT_AND_INDEPENDENT_WRAPPER_VECTOR_EXECUTED_EXACT_PARITY"
    )
    assert full_receipt["comparisons"]["independent_wrapper_vector_execution"] is True

    drifted_wrapper = deepcopy(wrapper_with_vector)
    drifted_wrapper.pop("projection_sha256")
    drifted_capture = drifted_wrapper["wrapper_runtime_capture"]
    drifted_capture["faiss_index_sha256"] = "d" * 64
    drifted_capture.pop("capture_sha256")
    drifted_capture["capture_sha256"] = canonical_sha256(drifted_capture)
    drifted_wrapper["projection_sha256"] = canonical_sha256(drifted_wrapper)
    with pytest.raises(
        ExpelB2AdapterError, match="independent_wrapper_vector_execution"
    ):
        audit_expel_direct_wrapper_parity(direct, drifted_wrapper)


def test_wrapper_requires_explicit_rule_cap_and_environment_filtered_ranking() -> None:
    with pytest.raises(ExpelB2AdapterError, match="rule list exceeds"):
        build_expel_b2_wrapper_projection(
            _source(), rules=tuple(f"rule-{index}" for index in range(11)),
            successful_trajectories=_trajectories(), ranked_task_ids=("clean mug___2",),
            current_task="clean bowl___9", current_env_name="pick_clean_then_place",
            config=_config(),
        )
    crossed = list(_trajectories())
    crossed[2] = replace(crossed[2], env_name="pick_heat_then_place")
    with pytest.raises(ExpelB2AdapterError, match="environment filter"):
        build_expel_b2_wrapper_projection(
            _source(), rules=("rule",), successful_trajectories=crossed,
            ranked_task_ids=("clean mug___2",), current_task="clean bowl___9",
            current_env_name="pick_clean_then_place", config=_config(),
        )


def test_source_verifier_refuses_missing_or_unpinned_source(tmp_path: Path) -> None:
    with pytest.raises(ExpelB2AdapterError):
        verify_pinned_expel_source(tmp_path / "missing")
    root = tmp_path / "source"
    root.mkdir()
    with pytest.raises(ExpelB2AdapterError, match="pinned file"):
        verify_pinned_expel_source(root)


def test_wrapper_refuses_forged_source_binding() -> None:
    source = _source()
    forged_binding = dict(source.source_binding)
    forged_binding["license_sha256"] = "0" * 64
    forged_binding.pop("source_binding_sha256")
    forged_binding["source_binding_sha256"] = canonical_sha256(forged_binding)
    with pytest.raises(ExpelB2AdapterError, match="source object identity"):
        build_expel_b2_wrapper_projection(
            replace(source, source_binding=forged_binding),
            rules=("rule",),
            successful_trajectories=_trajectories(),
            ranked_task_ids=("clean mug___2",),
            current_task="clean bowl___9",
            current_env_name="pick_clean_then_place",
            config=_config(),
        )
