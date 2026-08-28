from __future__ import annotations

import base64
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path

import pytest

from _research.dnrd.execute import PREREG_CLAIM_BOUNDARY
from _research.dnrd.task_family import canonical_json, commitment, generate_manifests


REPO_ROOT = Path(__file__).resolve().parents[1]
JUDGE_PATH = REPO_ROOT / "_research" / "dnrd" / "judge.py"
_SPEC = importlib.util.spec_from_file_location("hswm_dnrd_judge", JUDGE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
judge = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(judge)


def _sha(label: str) -> str:
    return (label.encode("ascii").hex() + "0" * 64)[:64]


def _chat_config() -> dict[str, object]:
    candidates = ["token-0123456789abcdef0123", "token-ffffffffffffffffffff"]
    schema = {
        "type": "object",
        "properties": {"response_token": {
            "type": "string", "enum": candidates,
            "pattern": "^token-[0-9a-f]{20}$", "minLength": 26, "maxLength": 26,
        }},
        "required": ["response_token"],
        "additionalProperties": False,
    }
    response_format = {
        "type": "json_schema",
        "json_schema": {"name": "hswm_dnrd_response_token", "strict": True, "schema": schema},
    }
    return {
        "chat_template_kwargs": {"enable_thinking": False}, "logprobs": False,
        "n": 1, "stream": False, "temperature": 0, "top_p": 1,
        "max_tokens": judge.MAX_OUTPUT_TOKENS,
        "response_format": response_format,
        "response_format_schema_sha256": commitment(schema),
    }


def _qualification_summary() -> dict[str, object]:
    calls: list[dict[str, object]] = []
    pairs = (
        ("token-00000000000000000001", "token-00000000000000000002"),
        ("token-00000000000000000003", "token-00000000000000000004"),
        ("token-00000000000000000005", "token-00000000000000000006"),
    )
    for ordinal, pair in enumerate(pairs, start=1):
        requested = pair[1] if ordinal == 2 else pair[0]
        schema = {
            "type": "object",
            "properties": {"response_token": {
                "type": "string", "enum": list(pair),
                "pattern": "^token-[0-9a-f]{20}$", "minLength": 26,
                "maxLength": 26,
            }},
            "required": ["response_token"],
            "additionalProperties": False,
        }
        calls.append({
            "candidate_response_tokens": list(pair),
            "completion_tokens": 1,
            "dnrd_request_sha256": _sha(f"request-{ordinal}"),
            "dnrd_response_sha256": _sha(f"response-{ordinal}"),
            "finish_reason": "stop",
            "http_request_sha256": _sha(f"http-{ordinal}"),
            "http_status": 200,
            "ordinal": ordinal,
            "prompt_tokens": 1,
            "raw_response_sha256": _sha(f"raw-{ordinal}"),
            "requested_token": requested,
            "response_format_schema_sha256": commitment(schema),
            "returned_token": requested,
        })
    return {
        "schema_version": "hswm-dnrd4s1-structured-output-qualification-summary/v1",
        "domain": "HSWM-DNRD4S1-STRUCTURED-OUTPUT-QUALIFICATION-v1",
        "event_schema": "hswm-dnrd-live-model-event/v3",
        "experiment_occurrence": False,
        "future_seed_material_used": False,
        "record_role": (
            "CONTENT_ADDRESSED_OPERATOR_SUMMARY_OF_DISJOINT_NONSCIENTIFIC_LIVE_"
            "QUALIFICATION_NOT_SCIENTIFIC_EVIDENCE"
        ),
        "raw_full_stdout_record_persisted": False,
        "retry_count": 0,
        "max_output_tokens": judge.MAX_OUTPUT_TOKENS,
        "model_endpoint": "http://127.0.0.1:18000",
        "served_model_id": "qwen3.6-35b-a3b",
        "vllm_version": "0.25.1",
        "provider_cache_independence": judge.PROVIDER_CACHE_UNOBSERVABLE,
        "calls": calls,
        "started_at_unix_ns": 1,
        "ended_at_unix_ns": 2,
        "source_files": [
            {"path": "_research/dnrd/live.py", "sha256": "a" * 64},
            {"path": "_research/dnrd/qualify.py", "sha256": "b" * 64},
            {"path": "_research/dnrd/runner.py", "sha256": "c" * 64},
            {"path": "_research/dnrd/task_family.py", "sha256": "d" * 64},
        ],
        "python_executable_sha256": judge.OFFICIAL_PYTHON_EXECUTABLE_SHA256,
        "python_version": judge.OFFICIAL_PYTHON_VERSION,
        "unicode_data_version": judge.OFFICIAL_UNICODE_DATA_VERSION,
    }


def test_structured_output_qualification_independently_rejects_semantic_drift() -> None:
    config = {
        "model_endpoint": "http://127.0.0.1:18000",
        "python_executable_sha256": judge.OFFICIAL_PYTHON_EXECUTABLE_SHA256,
        "python_version": judge.OFFICIAL_PYTHON_VERSION,
        "unicode_data_version": judge.OFFICIAL_UNICODE_DATA_VERSION,
    }
    base = _qualification_summary()
    source = {"files": deepcopy(base["source_files"])}
    preregistration = {
        "runtime_bindings": {
            "python_executable_sha256": judge.OFFICIAL_PYTHON_EXECUTABLE_SHA256,
            "python_version": judge.OFFICIAL_PYTHON_VERSION,
            "unicode_data_version": judge.OFFICIAL_UNICODE_DATA_VERSION,
        }
    }
    raw = canonical_json(base) + b"\n"
    judge._structured_output_qualification(
        raw,
        config=config,
        public={},
        private={},
        source=source,
        preregistration=preregistration,
    )

    altered = deepcopy(base)
    altered["calls"][0]["response_format_schema_sha256"] = "0" * 64
    with pytest.raises(judge.BundleRefusal, match="response schema digest"):
        judge._structured_output_qualification(
            canonical_json(altered) + b"\n",
            config=config,
            public={},
            private={},
            source=source,
            preregistration=preregistration,
        )

    altered = deepcopy(base)
    altered["calls"][0]["ordinal"] = True
    with pytest.raises(judge.BundleRefusal, match="fixed successful contract"):
        judge._structured_output_qualification(
            canonical_json(altered) + b"\n",
            config=config,
            public={},
            private={},
            source=source,
            preregistration=preregistration,
        )

    altered = deepcopy(base)
    altered["source_files"][2]["sha256"] = "e" * 64
    with pytest.raises(judge.BundleRefusal, match="source identities"):
        judge._structured_output_qualification(
            canonical_json(altered) + b"\n",
            config=config,
            public={},
            private={},
            source=source,
            preregistration=preregistration,
        )

    altered = deepcopy(base)
    altered["source_files"].reverse()
    with pytest.raises(judge.BundleRefusal, match="source-file order"):
        judge._structured_output_qualification(
            canonical_json(altered) + b"\n",
            config=config,
            public={},
            private={},
            source=source,
            preregistration=preregistration,
        )

    altered = deepcopy(base)
    altered["unicode_data_version"] = "0.0.0"
    with pytest.raises(judge.BundleRefusal, match="Python/Unicode runtime identities"):
        judge._structured_output_qualification(
            canonical_json(altered) + b"\n",
            config=config,
            public={},
            private={},
            source=source,
            preregistration=preregistration,
        )


def _claim_bound_preregistration() -> dict[str, object]:
    boundary = deepcopy(PREREG_CLAIM_BOUNDARY)
    return {
        "created_at": "2026-08-27",
        **{
            key: boundary[key]
            for key in (
                "canonical_role", "predecessor_bindings", "forbidden_rescues",
                "scientific_question", "hypotheses", "learning_boundary", "arms",
                "interventions", "diagnostic_readouts", "void_conditions",
                "single_attempt_policy", "required_before_measurement",
                "result_promotion", "measurement_gate",
            )
        },
        "testbed": {
            "family": "REPEATED_CONTEXT_TABULAR_ROUTING_MECHANICS_V2",
            **boundary["testbed_claims"],
            "development_streams": 4,
            "training_calls_per_stream_maximum": 8,
            "paired_heldout_probes_per_stream": 8,
            "evaluation_arms": 3,
            "evaluation_calls": 96,
            "shared_learning_or_compiler_calls_maximum": 32,
            "client_dispatched_generation_request_ceiling": 128,
            "model": {
                "served_model_id": "qwen3.6-35b-a3b",
                "substitution_allowed": False,
                "temperature": 0,
                "thinking": False,
                "max_output_tokens": judge.MAX_OUTPUT_TOKENS,
                "deployment_readback_required": True,
                "exact_weight_revision_attested": False,
                "exact_weight_identity_claimed": False,
            },
        },
        "parity_and_leakage": {
            "same_served_model_id_and_chat_endpoint": True,
            "equal_client_dispatched_and_logical_requests": True,
            "equal_generation_limits_input_token_parity_not_claimed": True,
            "equal_candidate_evidence_universe": True,
            "all_active_payloads_within_byte_ceiling": True,
            "active_state_byte_ceiling": 16_384,
            "full_fixed_rule_replay_numeric_payload_bytes_equal": True,
            "full_deranged_numeric_payload_byte_count_equal": True,
            "arm_labels_hidden_from_model": True,
            "fresh_process_recovery_observed": True,
            "distinct_arm_mount_ids": True,
            "evaluation_read_only_wrt_routing_observed": True,
            "cache_hits_required": 0,
            "private_route_binding_open_only_after_response_seal": True,
            "pre_dispatch_readout_bound_before_model_response": True,
            "scorer_outcome_response_independent": True,
            **boundary["parity_claims"],
        },
    }


def _self_addressed_receipt(unsigned: dict[str, object]) -> dict[str, object]:
    return {**unsigned, "receipt_sha256": commitment(unsigned)}


def _preregistration_ci_fixture() -> dict[str, object]:
    """One self-consistent DNRD-4S1 source/prereg/CI fixture for negative joins."""
    scorer_sha256 = _sha("fixture-scorer")
    source = {
        "schema_version": "hswm-dnrd-source-freeze-manifest/v1",
        "experiment_id": judge.EXPERIMENT_ID,
        "source_commit_tree_bound_externally": (
            "SOURCE_COMMIT_TREE_BOUND_EXTERNALLY_NO_SELF_CYCLE"
        ),
        "files": [
            {
                "path": path,
                "sha256": scorer_sha256 if path == "_research/dnrd/scorer.py" else _sha("fixture-source"),
            }
            for path in sorted(judge.FROZEN_DNRD_SOURCE_CLOSURE)
        ],
    }
    source_bytes = canonical_json(source)
    source_commit = "a" * 40
    preregistration_commit = "b" * 40
    source_tree_oid = "e" * 40
    preregistration_tree_oid = "c" * 40
    preregistration_blob_oid = "d" * 40
    source_ci_completed_at_utc = "2026-08-27T23:00:00Z"
    def ci_api(run_id: int, commit: str, tree: str, updated: str) -> dict[str, object]:
        return {"id": run_id, "workflow_id": 3, "run_number": 4, "name": "CI", "path": ".github/workflows/ci.yml", "event": "push", "head_branch": "main", "head_sha": commit, "run_attempt": 1, "status": "completed", "conclusion": "success", "created_at": "2026-08-27T22:00:00Z", "run_started_at": "2026-08-27T22:00:01Z", "updated_at": updated, "pull_requests": [], "head_commit": {"id": commit, "tree_id": tree}, "repository": {"id": 1, "full_name": "gj3447/HSWM"}, "head_repository": {"id": 1, "full_name": "gj3447/HSWM"}}
    def ci_projection(api: dict[str, object]) -> dict[str, object]:
        keys = ("id", "workflow_id", "run_number", "name", "path", "event", "head_branch", "head_sha", "run_attempt", "status", "conclusion", "created_at", "run_started_at", "updated_at", "pull_requests")
        return {**{key: api[key] for key in keys}, "head_commit": api["head_commit"], "repository": api["repository"], "head_repository": api["head_repository"]}
    source_api = ci_api(101, source_commit, source_tree_oid, source_ci_completed_at_utc)
    source_ci_raw = canonical_json(source_api).decode("utf-8")
    source_ci = _self_addressed_receipt({
        "schema_version": "hswm-dnrd-source-ci-receipt/v2",
        "provider": "GITHUB_ACTIONS",
        "run_id": 101,
        "head_sha": source_commit,
        "conclusion": "success",
        "raw_response_sha256": sha256(source_ci_raw.encode("utf-8")).hexdigest(),
        "raw_response_utf8": source_ci_raw,
        "discovery_query": {"request_path": f"/repos/gj3447/HSWM/actions/workflows/ci.yml/runs?event=push&branch=main&head_sha={source_commit}&per_page=100&page=1", "workflow_path": ".github/workflows/ci.yml", "event": "push", "branch": "main", "head_sha": source_commit, "per_page": 100, "page": 1},
        "critical_projection": ci_projection(source_api),
        "raw_list_response_sha256": sha256(canonical_json({"total_count": 1, "workflow_runs": [source_api]})).hexdigest(),
        "raw_list_response_utf8": canonical_json({"total_count": 1, "workflow_runs": [source_api]}).decode(),
    })
    preregistration = _claim_bound_preregistration()
    preregistration.update({
        "schema_version": judge.PREREGISTRATION_SCHEMA,
        "experiment_id": judge.EXPERIMENT_ID,
        "protocol_version": "v4s1",
        "status": "FROZEN_AWAITING_SUCCESSFUL_PREREGISTRATION_B_CI_AND_FUTURE_PULSE",
        "authority": {
            "broad_research_continuation_requested": True,
            "measurement_authorized_by_user_broad_continuation": True,
            "authorization_is_scientific_evidence": False,
            "measurement_requires_external_exact_hash_ratification_receipt": False,
            "measurement_requires_successful_preregistration_b_ci_receipt": True,
            "scientific_judgment_emitted": False,
            "external_governance_required": False,
        },
        "preregistration_b_ci_gate": {
            "receipt_schema": "hswm-dnrd-preregistration-b-ci-receipt/v2",
            "provider": "GITHUB_ACTIONS",
            "status": "completed",
            "conclusion": "success",
            "minimum_lead_seconds": 900,
            "selection_rule": "EXACT_UNFILTERED_PUSH_MAIN_HEAD_SHA_WORKFLOW_LIST_TOTAL_COUNT_ONE_FIRST_ATTEMPT",
        },
        "source_a_ci": {
            "receipt_sha256": sha256(canonical_json(source_ci)).hexdigest(),
            "run_id": 101,
            "head_sha": source_commit,
            "conclusion": "success",
        },
        "runtime_bindings": {},
    })
    preregistration_bytes = canonical_json(preregistration)
    completed_at_utc = "2026-08-28T00:00:00Z"
    completed_at_unix = judge._strict_utc_unix(completed_at_utc, "fixture B-CI completion")
    preregistration_api = ci_api(202, preregistration_commit, preregistration_tree_oid, completed_at_utc)
    preregistration_ci_raw = canonical_json(preregistration_api).decode("utf-8")
    preregistration_ci = _self_addressed_receipt({
        "schema_version": "hswm-dnrd-preregistration-b-ci-receipt/v2",
        "provider": "GITHUB_ACTIONS",
        "run_id": 202,
        "head_sha": preregistration_commit,
        "head_tree_oid": preregistration_tree_oid,
        "preregistration_path": "_research/dnrd/preregistration.json",
        "preregistration_git_blob_oid": preregistration_blob_oid,
        "preregistration_sha256": sha256(preregistration_bytes).hexdigest(),
        "status": "completed",
        "conclusion": "success",
        "completed_at_utc": completed_at_utc,
        "completed_at_unix": completed_at_unix,
        "raw_response_sha256": sha256(preregistration_ci_raw.encode("utf-8")).hexdigest(),
        "raw_response_utf8": preregistration_ci_raw,
        "discovery_query": {"request_path": f"/repos/gj3447/HSWM/actions/workflows/ci.yml/runs?event=push&branch=main&head_sha={preregistration_commit}&per_page=100&page=1", "workflow_path": ".github/workflows/ci.yml", "event": "push", "branch": "main", "head_sha": preregistration_commit, "per_page": 100, "page": 1},
        "critical_projection": ci_projection(preregistration_api),
        "raw_list_response_sha256": sha256(canonical_json({"total_count": 1, "workflow_runs": [preregistration_api]})).hexdigest(),
        "raw_list_response_utf8": canonical_json({"total_count": 1, "workflow_runs": [preregistration_api]}).decode(),
    })
    preregistration_ci_bytes = canonical_json(preregistration_ci)
    candidate_value = {
        "bindings": {
            "source_manifest_sha256": sha256(source_bytes).hexdigest(),
            "preregistration_sha256": sha256(preregistration_bytes).hexdigest(),
            "preregistration_ci_receipt_sha256": sha256(preregistration_ci_bytes).hexdigest(),
            "scorer_sha256": scorer_sha256,
        },
        "chronology": {
            "source_commit": source_commit,
            "preregistration_commit": preregistration_commit,
            "source_tree_oid": source_tree_oid,
            "preregistration_tree_oid": preregistration_tree_oid,
            "source_frozen_at_unix": judge._strict_utc_unix(
                source_ci_completed_at_utc, "fixture source-CI completion"
            ) - 1,
            "preregistration_committed_at_unix": completed_at_unix - 1,
            "preregistration_ci_completed_at_unix": completed_at_unix,
        },
    }
    return {
        "source": source,
        "source_bytes": source_bytes,
        "source_ci": source_ci,
        "preregistration": preregistration,
        "preregistration_bytes": preregistration_bytes,
        "preregistration_ci": preregistration_ci,
        "preregistration_ci_bytes": preregistration_ci_bytes,
        "candidate": candidate_value,
        "preregistration_blob_oid": preregistration_blob_oid,
    }


def _validate_preregistration_ci_fixture(fixture: dict[str, object]) -> None:
    judge._validate_source_and_preregistration(
        source=fixture["source"],
        preregistration=fixture["preregistration"],
        source_ci=fixture["source_ci"],
        preregistration_ci=fixture["preregistration_ci"],
        candidate=fixture["candidate"],
        source_bytes=fixture["source_bytes"],
        preregistration_bytes=fixture["preregistration_bytes"],
        preregistration_ci_bytes=fixture["preregistration_ci_bytes"],
    )


def _reserialize_preregistration_ci(fixture: dict[str, object]) -> None:
    receipt = fixture["preregistration_ci"]
    assert isinstance(receipt, dict)
    unsigned = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    receipt["receipt_sha256"] = commitment(unsigned)
    raw = canonical_json(receipt)
    fixture["preregistration_ci_bytes"] = raw
    candidate_value = fixture["candidate"]
    assert isinstance(candidate_value, dict)
    bindings = candidate_value["bindings"]
    assert isinstance(bindings, dict)
    bindings["preregistration_ci_receipt_sha256"] = sha256(raw).hexdigest()


def test_preregistration_b_ci_receipt_refuses_self_consistent_completion_time_drift() -> None:
    fixture = _preregistration_ci_fixture()
    _validate_preregistration_ci_fixture(fixture)

    altered = deepcopy(fixture)
    receipt = altered["preregistration_ci"]
    assert isinstance(receipt, dict)
    receipt["completed_at_unix"] = receipt["completed_at_unix"] + 1
    _reserialize_preregistration_ci(altered)
    with pytest.raises(judge.BundleRefusal, match="UTC completion time drifted"):
        _validate_preregistration_ci_fixture(altered)


def test_source_ci_receipt_refuses_completion_before_source_freeze() -> None:
    fixture = _preregistration_ci_fixture()
    altered = deepcopy(fixture)
    candidate = altered["candidate"]
    assert isinstance(candidate, dict)
    chronology = candidate["chronology"]
    assert isinstance(chronology, dict)
    source_ci = altered["source_ci"]
    assert isinstance(source_ci, dict)
    raw = json.loads(source_ci["raw_response_utf8"])
    completed_at = judge._strict_utc_unix(raw["updated_at"], "fixture source-CI completion")
    chronology["source_frozen_at_unix"] = completed_at + 1
    with pytest.raises(judge.BundleRefusal, match="source-A tree/freeze/precedence"):
        _validate_preregistration_ci_fixture(altered)


def test_preregistration_b_ci_receipt_refuses_self_consistent_raw_provider_drift() -> None:
    fixture = _preregistration_ci_fixture()
    altered = deepcopy(fixture)
    receipt = altered["preregistration_ci"]
    assert isinstance(receipt, dict)
    raw = json.loads(receipt["raw_response_utf8"])
    raw["head_commit"]["tree_id"] = "f" * 40
    receipt["raw_response_utf8"] = canonical_json(raw).decode("utf-8")
    receipt["raw_response_sha256"] = sha256(receipt["raw_response_utf8"].encode("utf-8")).hexdigest()
    _reserialize_preregistration_ci(altered)
    with pytest.raises(judge.BundleRefusal, match="raw response does not attest"):
        _validate_preregistration_ci_fixture(altered)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("head_tree_oid", "f" * 40),
        ("preregistration_git_blob_oid", "f" * 40),
    ],
)
def test_preregistration_b_ci_receipt_refuses_raw_git_tree_or_blob_drift(
    field: str, value: str
) -> None:
    fixture = _preregistration_ci_fixture()
    receipt = deepcopy(fixture["preregistration_ci"])
    assert isinstance(receipt, dict)
    receipt[field] = value
    candidate_value = fixture["candidate"]
    assert isinstance(candidate_value, dict)
    with pytest.raises(judge.BundleRefusal, match="raw A-to-B Git tree/blob/chronology"):
        judge._validate_preregistration_ci_git_binding(
            preregistration_ci=receipt,
            candidate=candidate_value,
            preregistration_commit="b" * 40,
            preregistration_tree_oid="c" * 40,
            preregistration_path="_research/dnrd/preregistration.json",
            preregistration_git_blob_oid=fixture["preregistration_blob_oid"],
            preregistration_sha256=candidate_value["bindings"]["preregistration_sha256"],
            preregistration_committed_at_unix=candidate_value["chronology"]["preregistration_committed_at_unix"],
        )


def test_preregistration_b_ci_receipt_refuses_completion_before_b_commit() -> None:
    fixture = _preregistration_ci_fixture()
    receipt = deepcopy(fixture["preregistration_ci"])
    candidate_value = deepcopy(fixture["candidate"])
    assert isinstance(receipt, dict) and isinstance(candidate_value, dict)
    receipt["completed_at_unix"] = candidate_value["chronology"]["preregistration_committed_at_unix"] - 1
    candidate_value["chronology"]["preregistration_ci_completed_at_unix"] = receipt["completed_at_unix"]
    with pytest.raises(judge.BundleRefusal, match="raw A-to-B Git tree/blob/chronology"):
        judge._validate_preregistration_ci_git_binding(
            preregistration_ci=receipt,
            candidate=candidate_value,
            preregistration_commit="b" * 40,
            preregistration_tree_oid="c" * 40,
            preregistration_path="_research/dnrd/preregistration.json",
            preregistration_git_blob_oid=fixture["preregistration_blob_oid"],
            preregistration_sha256=candidate_value["bindings"]["preregistration_sha256"],
            preregistration_committed_at_unix=candidate_value["chronology"]["preregistration_committed_at_unix"],
        )


def test_dnr_d4_bundle_rejects_obsolete_ratification_artifact(tmp_path: Path) -> None:
    (tmp_path / "ratification_receipt.json").write_text("{}", encoding="utf-8")
    with pytest.raises(judge.BundleRefusal, match="must not retain obsolete ratification_receipt"):
        judge.judge_bundle(tmp_path)


@pytest.mark.parametrize(
    "field_path",
    [
        ("canonical_role",), ("predecessor_bindings",), ("forbidden_rescues",),
        ("scientific_question",), ("hypotheses",),
        ("testbed", "relationship_to_prior_p1"), ("testbed", "analysis_unit"),
        ("testbed", "freshness"), ("learning_boundary",),
        ("arms", "FULL"), ("interventions",),
        ("parity_and_leakage", "compiler_input_audit"),
        ("parity_and_leakage", "canary"), ("diagnostic_readouts",),
        ("void_conditions",), ("single_attempt_policy",),
        ("required_before_measurement",), ("result_promotion",),
        ("measurement_gate",),
    ],
)
def test_independent_judge_refuses_any_broadened_preregistration_claim(
    field_path: tuple[str, ...],
) -> None:
    prereg = _claim_bound_preregistration()
    assert commitment(PREREG_CLAIM_BOUNDARY) == judge.PREREG_CLAIM_BOUNDARY_SHA256
    judge._validate_preregistration_claim_boundary(prereg)
    target = prereg
    for key in field_path[:-1]:
        target = target[key]
    target[field_path[-1]] = "CLAIM_LLM_LEARNING_EFFICACY_AND_UNSEEN_GENERALIZATION"
    with pytest.raises(judge.BundleRefusal, match="claim boundary"):
        judge._validate_preregistration_claim_boundary(prereg)


def test_preregistration_names_exact_terminals_and_does_not_claim_record_signatures() -> None:
    promotion = PREREG_CLAIM_BOUNDARY["result_promotion"]
    assert promotion["non_go_terminals"] == [
        "DIAGNOSTIC_NO_GO",
        "VOID_PROTOCOL",
        "INCONCLUSIVE_OCCURRENCE",
    ]
    full_description = PREREG_CLAIM_BOUNDARY["arms"]["FULL"]
    raw_description = PREREG_CLAIM_BOUNDARY["interventions"]["fixed_rule_replay_gate"]
    assert full_description.startswith("For each stream, apply exactly eight")
    assert raw_description.startswith("NO_MODEL_DISPATCH")


def test_dnrd3_and_dnrd4_predecessor_identities_are_hard_bound() -> None:
    predecessors = PREREG_CLAIM_BOUNDARY["predecessor_bindings"]
    assert predecessors[-9:-5] == [
        "DNRD3_STRUCTURAL_VOID_POST_128_CALLS_NO_MECHANICS_RESULT_NO_RETRY",
        "DNRD3_PREREGISTRATION_SHA256="
        "2bcbe110cac8b69b3889761c05635a8af62b09a443e2a10a2a4a62aad0791226",
        "DNRD3_RESULT_COMMIT=43c1b9885352ed99e6845884b0adec0445f1be4b",
        "DNRD3_CHECKED_EVIDENCE_RECEIPT_SELF_SHA256="
        "55c9de56932b3b28ab049e056e93051312442ca84c29c90182ffc485d996e829",
    ]
    assert predecessors[-5:] == [
        "DNRD4_FROZEN_UNEXECUTED_PREMARKER_STATIC_INSTRUMENT_REFUSAL_NO_QUICKNET_NO_MARKER_NO_GENERATION_NO_OCCURRENCE_NO_JUDGMENT",
        "DNRD4_SOURCE_A_COMMIT=276fc42354169cb5f0f0bc6cbaf34052047cd630",
        "DNRD4_PREREGISTRATION_B_COMMIT=b1dc53d8efdaee24d1ffad10cc558a48321bc6ac",
        "DNRD4_PREREGISTRATION_SHA256=87cdf810e3c4c88a8b755f5b31bd3b98dad6bff9d5c320e58eaeb7b2659a3762",
        "DNRD4_INVALID_RUNTIME_MANIFEST_SHA256=fbca6ec3d59fc575f7a9effc4f7add15da8d56e280b5434981f84355f9cdd737",
    ]
    assert commitment(PREREG_CLAIM_BOUNDARY) == judge.PREREG_CLAIM_BOUNDARY_SHA256


def test_independent_judge_refuses_claim_text_hidden_in_preregistration_created_at() -> None:
    prereg = _claim_bound_preregistration()
    prereg["created_at"] = (
        "2026-08-27; CLAIM_LLM_LEARNING_EFFICACY_AND_UNSEEN_GENERALIZATION"
    )
    with pytest.raises(judge.BundleRefusal, match="exact ISO-8601 date"):
        judge._validate_preregistration_claim_boundary(prereg)


def _runtime_binding_fixture() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    runtime = {
        "bridge_implementation_sha256": _sha("bridge"),
        "bridge_runtime_tree_manifest_sha256": _sha("tree"),
        "bridge_config": {"schemaVersion": "fixture"},
        "scorer_implementation_sha256": _sha("scorer"),
        "node_executable_sha256": judge.OFFICIAL_NODE_EXECUTABLE_SHA256,
        "node_version": judge.OFFICIAL_NODE_VERSION,
        "python_executable_sha256": judge.OFFICIAL_PYTHON_EXECUTABLE_SHA256,
        "python_version": judge.OFFICIAL_PYTHON_VERSION,
        "unicode_data_version": judge.OFFICIAL_UNICODE_DATA_VERSION,
        "subprocess_environment": dict(judge.PINNED_SUBPROCESS_ENVIRONMENT),
    }
    config = {
        "model_endpoint": "http://127.0.0.1:8000",
        "verifier_helper_sha256": _sha("helper"),
        "verifier_package_lock_sha256": _sha("lock"),
        "verifier_runtime_bundle_sha256": (
            judge.OFFICIAL_DRAND_CLIENT_RUNTIME_BUNDLE_SHA256
        ),
        "structured_output_qualification_sha256": _sha("qualification"),
    }
    binding = {
        "model_endpoint": config["model_endpoint"],
        "bridge_implementation_sha256": runtime["bridge_implementation_sha256"],
        "bridge_runtime_tree_manifest_sha256": runtime["bridge_runtime_tree_manifest_sha256"],
        "bridge_config_sha256": commitment(runtime["bridge_config"]),
        "scorer_implementation_sha256": runtime["scorer_implementation_sha256"],
        "node_executable_sha256": runtime["node_executable_sha256"],
        "node_version": runtime["node_version"],
        "python_executable_sha256": runtime["python_executable_sha256"],
        "python_version": runtime["python_version"],
        "unicode_data_version": runtime["unicode_data_version"],
        "verifier_helper_sha256": config["verifier_helper_sha256"],
        "verifier_package_lock_sha256": config["verifier_package_lock_sha256"],
        "verifier_runtime_bundle_sha256": config["verifier_runtime_bundle_sha256"],
        "structured_output_qualification_sha256": config[
            "structured_output_qualification_sha256"
        ],
        "subprocess_environment": runtime["subprocess_environment"],
    }
    return {"runtime_bindings": binding}, runtime, config


@pytest.mark.parametrize(
    "field",
    [
        "model_endpoint", "bridge_implementation_sha256",
        "bridge_runtime_tree_manifest_sha256", "bridge_config_sha256",
        "scorer_implementation_sha256", "node_executable_sha256", "node_version",
        "python_executable_sha256", "python_version", "unicode_data_version",
        "verifier_helper_sha256", "verifier_package_lock_sha256",
        "verifier_runtime_bundle_sha256", "structured_output_qualification_sha256",
        "subprocess_environment",
    ],
)
def test_independent_judge_refuses_every_drifted_preregistration_runtime_binding(
    field: str,
) -> None:
    prereg, runtime, config = _runtime_binding_fixture()
    judge._validate_preregistration_runtime_binding(prereg, runtime, config)
    binding = prereg["runtime_bindings"]
    assert isinstance(binding, dict)
    binding[field] = "CLAIM_LLM_LEARNING_EFFICACY_AND_UNSEEN_GENERALIZATION"
    with pytest.raises(judge.BundleRefusal, match="preregistration"):
        judge._validate_preregistration_runtime_binding(prereg, runtime, config)


@pytest.mark.parametrize(
    ("field", "forged"),
    [
        ("node_executable_sha256", _sha("forged-node")),
        ("node_version", "v24.13.0-forged"),
        ("python_executable_sha256", _sha("forged-python")),
        ("python_version", "3.12.13-forged"),
        ("unicode_data_version", "15.0.0-forged"),
        ("verifier_runtime_bundle_sha256", _sha("forged-bundle")),
    ],
)
def test_independent_judge_refuses_self_consistent_nonofficial_runtime_identity(
    field: str, forged: str
) -> None:
    prereg, runtime, config = _runtime_binding_fixture()
    binding = prereg["runtime_bindings"]
    assert isinstance(binding, dict)
    binding[field] = forged
    if field in runtime:
        runtime[field] = forged
    if field in config:
        config[field] = forged
    with pytest.raises(judge.BundleRefusal, match="Source-A protocol constants"):
        judge._validate_preregistration_runtime_binding(prereg, runtime, config)


def test_independent_judge_refuses_self_consistent_nonfixed_subprocess_environment() -> None:
    prereg, runtime, config = _runtime_binding_fixture()
    forged = {**judge.PINNED_SUBPROCESS_ENVIRONMENT, "NODE_OPTIONS": "--import=attacker"}
    prereg["runtime_bindings"]["subprocess_environment"] = forged
    runtime["subprocess_environment"] = forged
    with pytest.raises(judge.BundleRefusal, match="subprocess environment"):
        judge._validate_preregistration_runtime_binding(prereg, runtime, config)


@pytest.mark.parametrize(
    ("path", "field"),
    [
        ("_research/dnrd/verify-beacon.mjs", "verifier_helper_sha256"),
        ("tools/swm0w_drand/package-lock.json", "verifier_package_lock_sha256"),
    ],
)
def test_independent_judge_joins_verifier_source_bytes_to_preregistration_pins(
    path: str, field: str
) -> None:
    prereg, _, config = _runtime_binding_fixture()
    source = {
        "files": [
            {
                "path": "_research/dnrd/verify-beacon.mjs",
                "sha256": config["verifier_helper_sha256"],
            },
            {
                "path": "tools/swm0w_drand/package-lock.json",
                "sha256": config["verifier_package_lock_sha256"],
            },
        ]
    }
    judge._validate_verifier_source_binding(source, prereg, config)
    target = next(row for row in source["files"] if row["path"] == path)
    target["sha256"] = _sha(f"forged-{field}")
    with pytest.raises(judge.BundleRefusal, match="Source-A bytes"):
        judge._validate_verifier_source_binding(source, prereg, config)


def _retained_bundle_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raw: bytes
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    digest = sha256(raw).hexdigest()
    monkeypatch.setattr(
        judge, "OFFICIAL_DRAND_CLIENT_RUNTIME_BUNDLE_SHA256", digest
    )
    target = tmp_path / judge.VERIFIER_RUNTIME_BUNDLE_EVIDENCE_PATH
    target.write_bytes(raw)
    target.chmod(0o400)
    preregistration = {
        "runtime_bindings": {"verifier_runtime_bundle_sha256": digest}
    }
    config = {"verifier_runtime_bundle_sha256": digest}
    runtime = {
        "verifier_runtime_bundle_sha256": digest,
        "verifier_runtime_bundle_evidence_path": (
            judge.VERIFIER_RUNTIME_BUNDLE_EVIDENCE_PATH
        ),
        "verifier_runtime_bundle_dependency_policy": (
            judge.VERIFIER_RUNTIME_BUNDLE_DEPENDENCY_POLICY
        ),
    }
    return preregistration, config, runtime


def test_independent_judge_rehashes_exact_retained_verifier_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = b"var pinnedVerifierFixture = true;\n"
    preregistration, config, runtime = _retained_bundle_fixture(
        tmp_path, monkeypatch, raw
    )
    judge._validate_verifier_runtime_bundle_evidence(
        tmp_path, raw, preregistration, config, runtime
    )
    config["verifier_runtime_bundle_sha256"] = _sha("substituted-bundle")
    with pytest.raises(judge.BundleRefusal, match="official Source-A/B/runtime"):
        judge._validate_verifier_runtime_bundle_evidence(
            tmp_path, raw, preregistration, config, runtime
        )


@pytest.mark.parametrize(
    "raw",
    [
        b'import { forged } from "./mutable.mjs";\n',
        b'export { forged } from "./mutable.mjs";\n',
        b'const forged = await import("./mutable.mjs");\n',
    ],
)
def test_independent_judge_refuses_retained_bundle_external_esm_dependencies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raw: bytes
) -> None:
    preregistration, config, runtime = _retained_bundle_fixture(
        tmp_path, monkeypatch, raw
    )
    with pytest.raises(judge.BundleRefusal, match="external ESM dependency"):
        judge._validate_verifier_runtime_bundle_evidence(
            tmp_path, raw, preregistration, config, runtime
        )


def _route(label: str) -> dict[str, str]:
    return {"selected_route_id": f"route:{label}", "route_digest_sha256": _sha(label)}


def _process_id(index: int) -> str:
    return f"00000000-0000-4000-8000-{index:012x}"


def _state_evidence_entry(*, arm: str, mount_role: str) -> tuple[dict[str, object], dict[str, object]]:
    stream = {"stream_id": "stream-0", "context_keys": ["context-0"], "route_ids": ["route-0", "route-1"]}
    stratum = f"stratum:{sha256(b'stream-0').hexdigest()}"
    context_sha = sha256(b"context-0").hexdigest()
    payload = {
        "schemaVersion": "hswm-dnrd-routing-payload/v1",
        "contexts": [{
            "contextSha256": context_sha,
            "stratum": stratum,
            "routes": [{"routeId": "route-0", "scoreMicros": 0}, {"routeId": "route-1", "scoreMicros": 0}],
        }],
        "structuralStatus": "LOCAL_EXPERIMENTAL_ROUTING_PAYLOAD_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING",
    }
    durable = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    projection = json.dumps(
        {"scores": {"context-0": {"route-0": 0, "route-1": 0}}},
        ensure_ascii=True, sort_keys=True, separators=(",", ":"),
    )
    durable_hash = sha256(durable.encode()).hexdigest()
    return stream, {
        "mount_id": "mount-0",
        "mount_role": mount_role,
        "state_sha256": durable_hash,
        "routing_payload_utf8": durable,
        "routing_payload_sha256": durable_hash,
        "routing_payload_bytes": len(durable.encode()),
        "score_projection_utf8": projection,
        "score_projection_sha256": sha256(projection.encode()).hexdigest(),
        "score_projection_bytes": len(projection.encode()),
    }


def _observation(label: str, route_reward_micros: int) -> dict[str, object]:
    return {**_route(label), "route_reward_micros": route_reward_micros}


def _probe(stream: int, probe: int) -> dict[str, object]:
    w0_label = f"w0-{stream}-{probe}"
    full_label = w0_label if probe < 4 else f"full-{stream}-{probe}"
    deranged_label = f"deranged-{stream}-{probe}"
    w0_reward = 1_000_000 if probe < 4 else -1_000_000
    return {
        "probe_id": f"probe:{stream}:{probe}",
        "arms": {
            "FULL": _observation(full_label, 1_000_000),
            "NO_MEMORY_ROLLBACK": _observation(w0_label, w0_reward),
            "BINDING_DERANGED_NUMERIC_PLACEBO": _observation(deranged_label, -1_000_000),
        },
        "rollback": _route(w0_label),
        "restore": _route(full_label),
    }


def _stream(index: int) -> dict[str, object]:
    owner = f"owner:{index}"
    return {
        "stream_id": f"stream:{index}",
        "w0": {
            "state_sha256": _sha(f"w0-state-{index}"),
            "revision_id": f"w0-revision:{index}",
            "lineage_id": f"lineage:{index}",
            "immutable": True,
        },
        "w1": {
            "state_sha256": _sha(f"w1-state-{index}"),
            "revision_id": f"w1-revision:{index}",
            "lineage_id": f"lineage:{index}",
            "immutable": True,
            "owner_id": owner,
        },
        "clean_process_recovery": {
            "recovered": True,
            "journal_sha256": _sha(f"journal-{index}"),
            "recovered_state_sha256": _sha(f"w1-state-{index}"),
            "fresh_process": True,
            "process_instance_id": _process_id(index),
        },
        "fixed_rule_replay": {
            "schema_version": "hswm-dnrd-fixed-rule-replay-observation/v1",
            "rule": "signed_reward_times_100000_div_1000000/v1",
            "w1_state_sha256": _sha(f"w1-state-{index}"),
            "w1_journal_sha256": _sha(f"journal-{index}"),
            "w1_routing_payload_sha256": _sha(f"payload-{index}"),
            "w1_routing_payload_bytes": 1,
            "replay_state_sha256": _sha(f"w1-state-{index}"),
            "replay_journal_sha256": _sha(f"journal-{index}"),
            "replay_routing_payload_sha256": _sha(f"payload-{index}"),
            "replay_routing_payload_bytes": 1,
            "replay_process_instance_id": _process_id(index + 100),
            "heldout_readouts": [],
        },
        "local_v2_linkage": {
            "experimental_schema_id": "hswm:dnrd:v1",
            "owner_id": owner,
            "outcome_ledger_sha256": _sha(f"outcome-{index}"),
            "credit_ledger_sha256": _sha(f"credit-{index}"),
            "local_structural_receipt_sha256": _sha(f"admission-{index}"),
            "transition_evidence_sha256": _sha(f"evidence-{index}"),
            "local_only": True,
            "schema_owner_matches": True,
            "outcome_present": True,
            "reference_grant_matched_not_canonical_permit": True,
        },
        "derangement": {
            "algorithm": "within-stratum-no-fixed-point/v1",
            "seed_sha256": _sha(f"derangement-{index}"),
            "fixed_point_count": 0,
            "preserves_update_multiset": True,
            "preserves_precision": True,
            "preserves_l1_l2_norms": True,
            "preserves_routing_payload_byte_count": True,
            "routing_payload_content_differs": True,
        },
        "w0_replay_mismatch_probe_ids": [],
        "probes": [_probe(index, probe) for probe in range(8)],
    }


def candidate() -> dict[str, object]:
    return {
        "schema_version": judge.CANDIDATE_SCHEMA,
        "experiment_id": judge.EXPERIMENT_ID,
        "bindings": {
            "source_manifest_sha256": _sha("source-manifest"),
            "preregistration_sha256": _sha("preregistration"),
            "preregistration_ci_receipt_sha256": _sha("preregistration-ci-receipt"),
            "pulse_receipt_sha256": _sha("pulse-receipt"),
            "split_manifest_sha256": _sha("split-manifest"),
            "model_deployment_sha256": _sha("deployment"),
            "scorer_sha256": _sha("scorer"),
            "runtime_receipt_sha256": _sha("runtime-receipt"),
            "event_ledger_sha256": _sha("events"),
            "model_event_ledger_sha256": _sha("model-events"),
            "bridge_state_evidence_sha256": _sha("bridge-state"),
            "git_chronology_evidence_sha256": _sha("git-chronology"),
            "bridge_mount_closure_sha256": _sha("bridge-mount-closure"),
        },
        "chronology": {
            "source_commit": "a" * 40,
            "preregistration_commit": "b" * 40,
            "source_tree_oid": "c" * 40,
            "preregistration_tree_oid": "d" * 40,
            "source_frozen_at_unix": 1_000,
            "preregistration_committed_at_unix": 1_050,
            "preregistration_ci_completed_at_unix": 1_100,
            "pulse_round": 7,
            "pulse_chain_hash": _sha("quicknet-chain"),
            "pulse_at_unix": 2_000,
        },
        "overlap": {
            "normalizer_sha256": _sha("normalizer"),
            "training_heldout_exact_overlap": 0,
            "training_heldout_normalized_overlap": 0,
            "prior_item_overlap": 0,
            "leak_detected": False,
            "watermark_detected": False,
        },
        "parity": {
            "same_served_model_id_and_chat_endpoint": True,
            "equal_client_dispatched_and_logical_requests": True,
            "equal_generation_limits_input_token_parity_not_claimed": True,
            "equal_candidate_evidence_universe": True,
            "all_active_payloads_within_byte_ceiling": True,
            "full_fixed_rule_replay_numeric_payload_bytes_equal": True,
            "full_deranged_numeric_payload_byte_count_equal": True,
            "arm_labels_hidden_from_model": True,
            "pre_dispatch_readout_bound_before_model_response": True,
            "scorer_outcome_response_independent": True,
            "fresh_process_recovery_observed": True,
            "distinct_arm_mount_ids": True,
            "evaluation_read_only_wrt_routing_observed": True,
        },
        "call_ledger": {
            "common_training_model_calls": 32,
            "evaluation_model_calls": 96,
            "client_dispatched_generation_requests": 128,
            "logical_model_calls": 128,
            "route_only_model_calls": 0,
            "scorer_model_calls": 0,
            "retries": 0,
            "client_cache_hits": 0,
            "post_first_call_operational_failure": False,
        },
        "streams": [_stream(index) for index in range(4)],
    }


def _public_canary_fixture(seed: bytes) -> dict[str, object]:
    """Minimal public support sufficient for the judge's seed/canary audit."""
    streams: list[dict[str, object]] = []
    for stream_index in range(4):
        context = f"context-{stream_index}"
        training: list[dict[str, object]] = []
        for ordinal in range(8):
            canary = judge._expected_training_canary(seed, stream_index, ordinal)
            training.append(
                {
                    "episode_id": f"training:{stream_index}:{ordinal}",
                    "context_key": context,
                    "candidate_route_ids": ["route-a", "route-b"],
                    "prompt": (
                        f"training prompt {stream_index}/{ordinal}"
                        f"\nTraining provenance marker: {canary}"
                    ),
                    "provenance_canary": canary,
                }
            )
        heldout = [
            {
                "episode_id": f"heldout:{stream_index}:{ordinal}",
                "context_key": context,
                "candidate_route_ids": ["route-a", "route-b"],
                "prompt": f"heldout prompt {stream_index}/{ordinal}",
            }
            for ordinal in range(8)
        ]
        streams.append(
            {
                "context_keys": [context],
                "route_ids": ["route-a", "route-b"],
                "matched_derangement": {context: context},
                "training": training,
                "heldout": heldout,
            }
        )
    return {"streams": streams}


def test_positive_candidate_is_integrity_go_without_utility_claim() -> None:
    judgment = judge.judge(candidate())
    assert judgment["schema_version"] == "hswm-dnrd-judgment/v3"
    assert judgment["terminal"] == "DIAGNOSTIC_INTEGRITY_GO_NO_UTILITY_CLAIM"
    assert judgment["scientific_status"] == "UNJUDGED"
    assert judgment["efficacy_claim"] == "NOT_EVALUATED"
    assert judgment["canonical_permit"] == "NOT_ESTABLISHED"
    assert judgment["learning_claim"] == "NOT_ESTABLISHED"
    assert "engineering-conformance diagnostic" in judgment["claim_boundary"]
    assert "not scientific effect evidence" in judgment["claim_boundary"]
    assert "DECLARED_ROLE_SEPARATION_NOT_PROVEN" in judgment["claim_boundary"]
    assert "Model-serving identity/determinism is not proven" in judgment["claim_boundary"]
    linkage = candidate()["streams"][0]["local_v2_linkage"]
    assert set(linkage) >= {
        "outcome_ledger_sha256",
        "credit_ledger_sha256",
        "local_structural_receipt_sha256",
        "schema_owner_matches",
        "reference_grant_matched_not_canonical_permit",
    }


def test_training_provenance_canaries_are_rederived_from_seed_and_prompt_confined() -> None:
    seed = b"\x42" * 32
    public = _public_canary_fixture(seed)
    expected = frozenset(
        judge._expected_training_canary(seed, stream_index, ordinal)
        for stream_index in range(4)
        for ordinal in range(8)
    )
    assert judge._validate_training_provenance_canaries(public, seed) == expected

    public["streams"][0]["training"][0]["provenance_canary"] = (
        judge._expected_training_canary(seed, 0, 1)
    )
    with pytest.raises(judge.BundleRefusal, match="deterministically rederive"):
        judge._validate_training_provenance_canaries(public, seed)


def test_training_provenance_canary_is_rejected_from_public_heldout_material() -> None:
    seed = b"\x43" * 32
    public = _public_canary_fixture(seed)
    canary = judge._expected_training_canary(seed, 0, 0)
    public["streams"][3]["heldout"][4]["prompt"] += f" leaked {canary}"
    with pytest.raises(judge.BundleRefusal, match="heldout public episode"):
        judge._validate_training_provenance_canaries(public, seed)


def test_canary_leakage_recomputation_covers_state_request_seal_and_raw_response() -> None:
    canary = "dnrd-training-provenance:" + "a" * 32
    canaries = frozenset({canary})
    clean_event = {"request": {"prompt": "heldout"}, "sealed_response": {"answer": "clean"}}
    clean_accepted = {"raw_response_utf8": json.dumps({"choice": "clean"})}
    assert not judge._recompute_training_canary_leakage(
        canaries=canaries,
        state_evidence={"routing_payload": "clean"},
        call_evidence=[({**clean_event, "phase": "heldout"}, clean_accepted)],
    )

    for state, event, accepted in (
        ({"routing_payload": canary}, clean_event, clean_accepted),
        ({"routing_payload": "clean"}, {"request": {"prompt": canary}, "sealed_response": {"answer": "clean"}}, clean_accepted),
        ({"routing_payload": "clean"}, {"request": {"prompt": "heldout"}, "sealed_response": {"answer": canary}}, clean_accepted),
        ({"routing_payload": "clean"}, clean_event, {"raw_response_utf8": json.dumps({"choice": canary})}),
    ):
        assert judge._recompute_training_canary_leakage(
            canaries=canaries,
            state_evidence=state,
            call_evidence=[({**event, "phase": "heldout"}, accepted)],
        )


@pytest.mark.parametrize("carrier", ["sealed_response", "raw_response_utf8"])
def test_training_output_canary_is_rejected_while_training_request_is_allowed(
    carrier: str,
) -> None:
    canary = "dnrd-training-provenance:" + "c" * 32
    event = {
        "phase": "training",
        "request": {"prompt": canary},
        "sealed_response": {"answer": canary if carrier == "sealed_response" else "clean"},
    }
    accepted = {
        "raw_response_utf8": json.dumps(
            {"choice": canary if carrier == "raw_response_utf8" else "clean"}
        )
    }
    assert judge._recompute_training_canary_leakage(
        canaries=frozenset({canary}),
        state_evidence={"routing_payload": "clean"},
        call_evidence=[(event, accepted)],
    )


def test_candidate_overlap_bits_cannot_hide_or_assert_a_canary_leak() -> None:
    overlap = candidate()["overlap"]
    with pytest.raises(judge.BundleRefusal, match="leak/watermark projection"):
        judge._validate_recomputed_canary_overlap(overlap, True)

    asserted = deepcopy(overlap)
    asserted["leak_detected"] = True
    asserted["watermark_detected"] = True
    with pytest.raises(judge.BundleRefusal, match="training provenance canary leaked"):
        judge._validate_recomputed_canary_overlap(asserted, True)
    with pytest.raises(judge.BundleRefusal, match="leak/watermark projection"):
        judge._validate_recomputed_canary_overlap(asserted, False)



@pytest.mark.parametrize(
    ("mutate", "terminal"),
    [
        (lambda value: value["overlap"].__setitem__("leak_detected", True), "VOID_PROTOCOL"),
        (lambda value: value["call_ledger"].__setitem__("client_dispatched_generation_requests", 159), "VOID_PROTOCOL"),
        (lambda value: value["streams"][0]["derangement"].__setitem__("fixed_point_count", 1), "VOID_PROTOCOL"),
        (
            lambda value: value["streams"][0]["probes"][0]["rollback"].__setitem__(
                "route_digest_sha256", _sha("not-w0")
            ),
            "DIAGNOSTIC_NO_GO",
        ),
        (
            lambda value: value["streams"][0]["probes"][0]["restore"].__setitem__(
                "route_digest_sha256", _sha("not-full")
            ),
            "DIAGNOSTIC_NO_GO",
        ),
        (
            lambda value: value["streams"][0]["local_v2_linkage"].__setitem__(
                "owner_id", "owner:wrong"
            ),
            "VOID_PROTOCOL",
        ),
        (
            lambda value: value["streams"][0]["clean_process_recovery"].__setitem__(
                "fresh_process", False
            ),
            "DIAGNOSTIC_NO_GO",
        ),
        (
            lambda value: value["streams"][0]["local_v2_linkage"].__setitem__(
                "outcome_present", False
            ),
            "VOID_PROTOCOL",
        ),
    ],
)
def test_injected_negative_candidates_receive_the_predeclared_terminal(mutate, terminal: str) -> None:
    value = deepcopy(candidate())
    mutate(value)
    assert judge.judge(value)["terminal"] == terminal


def test_measurement_provided_verdict_is_strictly_refused() -> None:
    value = candidate()
    value["verdict"] = "PASS"
    with pytest.raises(judge.JudgeRefusal, match="forbidden"):
        judge.judge(value)


def test_valid_but_inert_route_mechanics_is_no_go() -> None:
    value = candidate()
    for stream in value["streams"]:
        stream["probes"][4]["arms"]["FULL"] = deepcopy(
            stream["probes"][4]["arms"]["NO_MEMORY_ROLLBACK"]
        )
        stream["probes"][4]["restore"] = deepcopy(stream["probes"][4]["rollback"])
    assert judge.judge(value)["terminal"] == "DIAGNOSTIC_NO_GO"


def test_digest_only_perturbation_is_no_go() -> None:
    value = candidate()
    for stream in value["streams"]:
        probe = stream["probes"][4]
        w0 = probe["arms"]["NO_MEMORY_ROLLBACK"]
        probe["arms"]["FULL"]["selected_route_id"] = w0["selected_route_id"]
        probe["restore"]["selected_route_id"] = w0["selected_route_id"]
    assert judge.judge(value)["terminal"] == "DIAGNOSTIC_NO_GO"


def test_completed_candidate_cannot_embed_partial_operational_failure() -> None:
    value = candidate()
    value["call_ledger"].update(
        {
            "common_training_model_calls": 8,
            "evaluation_model_calls": 16,
            "client_dispatched_generation_requests": 24,
            "logical_model_calls": 24,
            "post_first_call_operational_failure": True,
        }
    )
    assert judge.judge(value)["terminal"] == "VOID_PROTOCOL"


def test_process_recovery_identifier_is_raw_canonical_uuid_not_a_synthetic_hash() -> None:
    value = candidate()
    value["streams"][0]["clean_process_recovery"]["process_instance_id"] = _sha("synthetic-process")
    with pytest.raises(judge.JudgeRefusal, match="canonical lowercase UUID"):
        judge.judge(value)


def test_bridge_state_evidence_binds_the_expected_mount_role_for_each_arm() -> None:
    stream, entry = _state_evidence_entry(arm="FULL", mount_role="RAW_CONTROL")
    with pytest.raises(judge.BundleRefusal, match="mount_role"):
        judge._scores_from_state_entry(entry, stream, "FULL", "state")


def test_episode_replay_rejects_noncanonical_retained_response_token() -> None:
    stream = {
        "stream_id": "stream-0",
        "context_keys": ["context-0"],
        "route_ids": ["route-a", "route-b"],
    }
    episode = {
        "episode_id": "heldout:0:0",
        "stream_id": "stream-0",
        "phase": "heldout",
        "context_key": "context-0",
        "candidate_route_ids": ["route-a", "route-b"],
        "entity": "entity-0",
        "aliases": ["alias-0"],
        "surface_template": "template-0",
        "prompt": "return a JSON object whose only field is response_token from selected evidence.",
        "route_evidence": [
            {
                "route_id": "route-a",
                "evidence_text": "route-a gives token-00000000000000000000",
                "response_token": "token-00000000000000000000",
            },
            {
                "route_id": "route-b",
                "evidence_text": "route-b gives token-gggggggggggggggggggg",
                "response_token": "token-gggggggggggggggggggg",
            },
        ],
        "arm_order": list(judge.ARMS),
    }

    with pytest.raises(judge.BundleRefusal, match="exact DNRD-4S1 form"):
        judge._check_episode(episode, stream, "heldout", "episode")


def test_generated_dnrd4s1_manifest_pair_replays_under_the_judge() -> None:
    public, private = generate_manifests(bytes(range(32)))

    episodes, stream_by_episode, bindings = judge._public_manifest_index(public, private)

    assert len(episodes) == 64
    assert set(stream_by_episode) == set(episodes)
    assert set(bindings) == {"stream-0", "stream-1", "stream-2", "stream-3"}


def test_deranged_positive_route_reward_excess_is_no_go() -> None:
    value = candidate()
    for probe in value["streams"][0]["probes"]:
        probe["arms"]["BINDING_DERANGED_NUMERIC_PLACEBO"]["route_reward_micros"] = 1_000_000
    assert judge.judge(value)["terminal"] == "DIAGNOSTIC_NO_GO"


def test_valid_negative_cli_result_exits_zero(tmp_path: Path) -> None:
    value = candidate()
    for stream in value["streams"]:
        stream["probes"][0]["arms"]["FULL"] = deepcopy(
            stream["probes"][0]["arms"]["NO_MEMORY_ROLLBACK"]
        )
        stream["probes"][0]["restore"] = deepcopy(stream["probes"][0]["rollback"])
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    assert judge.main([str(path)]) == 0


def test_missing_both_terminal_artifacts_is_machine_void_not_refusal(tmp_path: Path) -> None:
    """An executor crash before terminal projection still gets a sealed negative."""
    result = judge.judge_bundle(tmp_path)

    assert result["terminal"] == "VOID_PROTOCOL"
    assert result["authority"] == "TERMINAL_ARTIFACT_ABSENCE_NOT_A_SCIENTIFIC_OCCURRENCE"
    assert result["scientific_status"] == "UNJUDGED"
    assert result["terminalization_check"] == "CANDIDATE_AND_INCONCLUSIVE_ARTIFACTS_ABSENT"
    assert len(result["bundle_verification_receipt_sha256"]) == 64


def test_missing_both_terminal_artifacts_cli_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert judge.main([str(tmp_path)]) == 0
    rendered = json.loads(capsys.readouterr().out)
    assert rendered["terminal"] == "VOID_PROTOCOL"
    assert rendered["terminalization_check"] == "CANDIDATE_AND_INCONCLUSIVE_ARTIFACTS_ABSENT"


def test_candidate_only_bundle_can_never_upgrade_to_go(tmp_path: Path) -> None:
    """Self-reported candidate hashes are not an evidence bundle."""
    path = tmp_path / "candidate.json"
    path.write_text(
        json.dumps(candidate(), ensure_ascii=True, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    result = judge.judge_bundle(tmp_path)
    assert result["terminal"] == "VOID_PROTOCOL"
    assert result["authority"] == "INCOMPLETE_OR_INVALID_EVIDENCE_BUNDLE_NOT_VERIFIED"
    assert len(result["bundle_verification_receipt_sha256"]) == 64


def _write_indexed_inconclusive_bundle(root: Path) -> None:
    """Build the minimal structurally closed aborted-occurrence bundle."""
    raw = canonical_json({
        "model": "qwen3.6-35b-a3b",
        "choices": [{"finish_reason": "length", "message": {"content": "x"}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    })
    failure_message = "chat completion choice must finish with exact reason 'stop'"
    occurrence = {
        "schema_version": judge.INCONCLUSIVE_SCHEMA,
        "experiment_id": judge.EXPERIMENT_ID,
        "post_first_call": True,
        "calls_completed": 1,
        "client_cache_hits": 0,
        "failure_type": "LiveBoundaryError",
        "failure_digest": commitment({"type": "LiveBoundaryError", "message": failure_message}),
    }
    (root / "inconclusive.json").write_bytes(canonical_json(occurrence))
    for relative in judge.BUNDLE_COMMON_REQUIRED_FILES - {"bundle_index.json"}:
        path = root / relative
        if path.name == "inconclusive.json":
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"{}\n" if path.name.endswith(".jsonl") else b"x")
    event_common = {
        "schema_version": judge.LIVE_EVENT_SCHEMA,
        "ordinal": 1,
        "phase": "training",
        "arm": None,
        "dnrd_request_sha256": _sha("request"),
        "endpoint": "http://example.invalid/v1/chat/completions",
        "model": "qwen3.6-35b-a3b",
        "request_sha256": _sha("body"),
        "raw_response_sha256": sha256(raw).hexdigest(),
        "http_status": 200,
        "chat_config": _chat_config(),
        "elapsed_nanoseconds": 1,
        "provider_cache_independence": judge.PROVIDER_CACHE_UNOBSERVABLE,
    }
    observed = {"event": "CHAT_COMPLETION_OBSERVED", **event_common}
    rejected = {
        "event": "CHAT_COMPLETION_REJECTED", **event_common,
        "raw_response_encoding": "base64",
        "raw_response_base64": base64.b64encode(raw).decode("ascii"),
        "raw_response_bytes": len(raw),
        "failure_stage_code": "FINISH_REASON_NOT_STOP",
        "failure_message": failure_message,
        "failure_message_sha256": sha256(failure_message.encode()).hexdigest(),
    }
    terminal_request = {
        "episode_id": "training:0:0",
        "selected_route_id": "route-a",
        "prompt": "fixture terminal prompt",
        "max_output_tokens": judge.MAX_OUTPUT_TOKENS,
        "ordinal": 1,
        "phase": "training",
        "arm": None,
        "candidate_response_tokens": ["token-0123456789abcdef0123", "token-ffffffffffffffffffff"],
        "pre_dispatch_receipt_sha256": None,
    }
    terminal_pre = {
        "schema_version": judge.RUNNER_EVENT_SCHEMA,
        "event": "PRE_DISPATCH_READOUT",
        "ordinal": 1,
        "phase": "training",
        "arm": None,
        "request": terminal_request,
        "pre_dispatch_readout": {
            "selected_route_id": "route-a", "route_digest_sha256": _sha("terminal-route"),
            "pre_outcome_score_micros": 0,
            "recovery": {"recovered": True, "fresh_process": True, "journal_sha256": _sha("terminal-journal"), "process_instance_id": _process_id(98)},
            "routing_payload_sha256": _sha("terminal-payload"),
        },
    }
    terminal_bound_request = {**terminal_request, "pre_dispatch_receipt_sha256": commitment(terminal_pre)}
    for event in (observed, rejected):
        event["dnrd_request_sha256"] = commitment(terminal_bound_request)
    (root / "model_events.jsonl").write_bytes(canonical_json(observed) + b"\n" + canonical_json(rejected) + b"\n")
    (root / "runner_events.jsonl").write_bytes(canonical_json(terminal_pre) + b"\n")
    _refresh_bundle_index(root)


def _prepend_accepted_call_to_inconclusive_bundle(root: Path) -> None:
    """Make the minimal bundle contain one accepted call before its rejection."""
    request = {
        "episode_id": "training:0:0",
        "selected_route_id": "route-a",
        "prompt": "fixture accepted prompt",
        "max_output_tokens": judge.MAX_OUTPUT_TOKENS,
        "ordinal": 1,
        "phase": "training",
        "arm": None,
        "candidate_response_tokens": ["token-0123456789abcdef0123", "token-ffffffffffffffffffff"],
        "pre_dispatch_receipt_sha256": _sha("pre-dispatch"),
    }
    provider_body = {
        "chat_template_kwargs": {"enable_thinking": False},
        "max_tokens": judge.MAX_OUTPUT_TOKENS,
        "messages": [{"content": request["prompt"], "role": "user"}],
        "model": "qwen3.6-35b-a3b",
        "n": 1,
        "stream": False,
        "temperature": 0,
        "top_p": 1,
        "logprobs": False,
        "response_format": _chat_config()["response_format"],
    }
    raw = canonical_json({
        "model": "qwen3.6-35b-a3b",
        "choices": [{
            "finish_reason": "stop",
            "message": {"content": '{"response_token":"token-0123456789abcdef0123"}'},
        }],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    })
    common = {
        "schema_version": judge.LIVE_EVENT_SCHEMA,
        "ordinal": 1,
        "phase": "training",
        "arm": None,
        "dnrd_request_sha256": commitment(request),
        "endpoint": "http://example.invalid/v1/chat/completions",
        "model": "qwen3.6-35b-a3b",
        "request_sha256": sha256(canonical_json(provider_body)).hexdigest(),
        "raw_response_sha256": sha256(raw).hexdigest(),
        "chat_config": _chat_config(),
        "elapsed_nanoseconds": 1,
        "provider_cache_independence": judge.PROVIDER_CACHE_UNOBSERVABLE,
    }
    observed = {"event": "CHAT_COMPLETION_OBSERVED", **common, "http_status": 200}
    accepted = {
        "event": "CHAT_COMPLETION_ACCEPTED",
        **common,
        "raw_response_utf8": raw.decode("utf-8"),
        "dnrd_response_sha256": commitment({
            "response_token": "token-0123456789abcdef0123",
            "input_tokens": 1,
            "output_tokens": 1,
            "client_cache_hit": False,
            "server_usage": {},
        }),
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }
    terminal = [
        json.loads(line)
        for line in (root / "model_events.jsonl").read_text().splitlines()
    ]
    for event in terminal:
        event["ordinal"] = 2
    (root / "model_events.jsonl").write_bytes(
        b"".join(
            canonical_json(event) + b"\n"
            for event in (observed, accepted, *terminal)
        )
    )
    readout = {
        "selected_route_id": "route-a",
        "route_digest_sha256": _sha("route"),
        "pre_outcome_score_micros": 0,
        "recovery": {
            "recovered": True, "fresh_process": True,
            "journal_sha256": _sha("journal"), "process_instance_id": _process_id(99),
        },
        "routing_payload_sha256": _sha("payload"),
    }
    pre_request = {**request, "pre_dispatch_receipt_sha256": None}
    pre = {
        "schema_version": judge.RUNNER_EVENT_SCHEMA,
        "event": "PRE_DISPATCH_READOUT",
        "ordinal": 1,
        "phase": "training",
        "arm": None,
        "request": pre_request,
        "pre_dispatch_readout": readout,
    }
    receipt = commitment(pre)
    runner = {
        "schema_version": judge.RUNNER_EVENT_SCHEMA,
        "event": "COMPLETED_CALL",
        "ordinal": 1,
        "phase": "training",
        "arm": None,
        "request": {**request, "pre_dispatch_receipt_sha256": receipt},
        "sealed_response": {},
        "trace": {},
        "scorer_outcome": {},
        "credit_receipt": {},
        "route_digest_sha256": _sha("route"),
        "pre_dispatch_receipt_sha256": receipt,
        "route_replay": None,
    }
    request_id = commitment(runner["request"])
    events = [observed, accepted, *terminal]
    for event in events[:2]:
        event["dnrd_request_sha256"] = request_id
    (root / "model_events.jsonl").write_bytes(
        b"".join(canonical_json(event) + b"\n" for event in events)
    )
    terminal_request = {
        "episode_id": "training:0:1", "selected_route_id": "route-a", "prompt": "fixture terminal prompt",
        "max_output_tokens": judge.MAX_OUTPUT_TOKENS, "ordinal": 2, "phase": "training", "arm": None,
        "candidate_response_tokens": ["token-0123456789abcdef0123", "token-ffffffffffffffffffff"],
        "pre_dispatch_receipt_sha256": None,
    }
    terminal_pre = {
        "schema_version": judge.RUNNER_EVENT_SCHEMA, "event": "PRE_DISPATCH_READOUT",
        "ordinal": 2, "phase": "training", "arm": None, "request": terminal_request,
        "pre_dispatch_readout": readout,
    }
    terminal_bound_request = {**terminal_request, "pre_dispatch_receipt_sha256": commitment(terminal_pre)}
    for event in terminal:
        event["dnrd_request_sha256"] = commitment(terminal_bound_request)
    (root / "model_events.jsonl").write_bytes(
        b"".join(canonical_json(event) + b"\n" for event in (observed, accepted, *terminal))
    )
    (root / "runner_events.jsonl").write_bytes(
        canonical_json(pre) + b"\n" + canonical_json(runner) + b"\n" + canonical_json(terminal_pre) + b"\n"
    )
    occurrence = json.loads((root / "inconclusive.json").read_text())
    occurrence["calls_completed"] = 2
    (root / "inconclusive.json").write_bytes(canonical_json(occurrence))
    _refresh_bundle_index(root)


def _refresh_bundle_index(root: Path, *, reverse_prefix_collision: bool = False) -> None:
    """Rebind test mutations so the adjudicator reaches ledger replay."""
    index_path = root / "bundle_index.json"
    if index_path.exists():
        index_path.unlink()
    rows = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if path.is_file():
            body = path.read_bytes()
            rows.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": sha256(body).hexdigest(),
                    "bytes": len(body),
                }
            )
    if reverse_prefix_collision:
        first = next(index for index, row in enumerate(rows) if row["path"].endswith("assert.d.ts"))
        second = next(index for index, row in enumerate(rows) if row["path"].endswith("assert/strict.d.ts"))
        rows[first], rows[second] = rows[second], rows[first]
    unsigned = {"schema_version": "hswm-dnrd-evidence-bundle-index/v1", "artifacts": rows}
    index = {**unsigned, "receipt_sha256": commitment(unsigned)}
    (root / "bundle_index.json").write_bytes(canonical_json(index))


def test_missing_bundle_index_void_is_not_claimed_as_verified_or_indexed(tmp_path: Path) -> None:
    occurrence = {
        "schema_version": judge.INCONCLUSIVE_SCHEMA,
        "experiment_id": judge.EXPERIMENT_ID,
        "post_first_call": True,
        "calls_completed": 1,
        "client_cache_hits": 0,
        "failure_type": "LiveBoundaryError",
        "failure_digest": _sha("inconclusive-failure"),
    }
    (tmp_path / "inconclusive.json").write_bytes(canonical_json(occurrence))

    result = judge.judge_bundle(tmp_path)

    assert result["terminal"] == "VOID_PROTOCOL"
    assert result["authority"] == "INCOMPLETE_OR_INVALID_EVIDENCE_BUNDLE_NOT_VERIFIED"
    assert "indexed" not in result["claim_boundary"].casefold()
    assert "failed structural verification" in result["claim_boundary"]


def test_indexed_inconclusive_is_verified_only_as_a_partial_occurrence(tmp_path: Path) -> None:
    _write_indexed_inconclusive_bundle(tmp_path)

    result = judge.judge_bundle(tmp_path)

    assert result["terminal"] == "INCONCLUSIVE_OCCURRENCE"
    assert result["authority"] == "INDEXED_INCONCLUSIVE_MODEL_BOUNDARY_AND_RUNNER_IDENTITY_LEDGER_VERIFIED"
    assert result["claim_boundary"] == (
        "The indexed model-boundary ledger and accepted-call-to-runner-row identity coverage "
        "were verified. Runner-row semantic contents, the terminal request preimage, and retained "
        "common context were not replayed as a completed candidate. This partial occurrence cannot "
        "establish efficacy, general intelligence, canonical Permit, admission, or learning."
    )


@pytest.mark.parametrize("mutation", ["base64", "identity", "order"])
def test_inconclusive_rejected_ledger_tampering_is_void(tmp_path: Path, mutation: str) -> None:
    _write_indexed_inconclusive_bundle(tmp_path)
    events = [json.loads(line) for line in (tmp_path / "model_events.jsonl").read_text().splitlines()]
    if mutation == "base64":
        events[1]["raw_response_base64"] = "eA=="
    elif mutation == "identity":
        events[1]["request_sha256"] = _sha("tampered-body")
    else:
        events.reverse()
    (tmp_path / "model_events.jsonl").write_bytes(b"".join(canonical_json(event) + b"\n" for event in events))
    _refresh_bundle_index(tmp_path)

    assert judge.judge_bundle(tmp_path)["terminal"] == "VOID_PROTOCOL"


def test_inconclusive_calls_completed_requires_at_least_one_model_event(tmp_path: Path) -> None:
    _write_indexed_inconclusive_bundle(tmp_path)
    (tmp_path / "model_events.jsonl").write_bytes(b"")
    _refresh_bundle_index(tmp_path)

    result = judge.judge_bundle(tmp_path)

    assert result["terminal"] == "VOID_PROTOCOL"
    assert "must retain model boundary events" in result["failure_reason"]


def test_inconclusive_runner_identities_exactly_cover_accepted_prior_calls(
    tmp_path: Path,
) -> None:
    _write_indexed_inconclusive_bundle(tmp_path)
    _prepend_accepted_call_to_inconclusive_bundle(tmp_path)
    assert judge.judge_bundle(tmp_path)["terminal"] == "INCONCLUSIVE_OCCURRENCE"

    (tmp_path / "runner_events.jsonl").write_bytes(b"")
    _refresh_bundle_index(tmp_path)
    result = judge.judge_bundle(tmp_path)

    assert result["terminal"] == "VOID_PROTOCOL"
    assert "exactly cover accepted prior model calls" in result["failure_reason"]


def test_inconclusive_malformed_runner_request_is_void_not_an_adjudicator_error(
    tmp_path: Path,
) -> None:
    _write_indexed_inconclusive_bundle(tmp_path)
    _prepend_accepted_call_to_inconclusive_bundle(tmp_path)
    rows = [json.loads(line) for line in (tmp_path / "runner_events.jsonl").read_text().splitlines()]
    del rows[1]["request"]["phase"]
    (tmp_path / "runner_events.jsonl").write_bytes(
        b"".join(canonical_json(row) + b"\n" for row in rows)
    )
    _refresh_bundle_index(tmp_path)

    result = judge.judge_bundle(tmp_path)

    assert result["terminal"] == "VOID_PROTOCOL"
    assert "pre-dispatch receipt" in result["failure_reason"]


def test_inconclusive_terminal_call_cannot_replay_a_prior_dnrd_request_identity(
    tmp_path: Path,
) -> None:
    _write_indexed_inconclusive_bundle(tmp_path)
    _prepend_accepted_call_to_inconclusive_bundle(tmp_path)
    events = [
        json.loads(line)
        for line in (tmp_path / "model_events.jsonl").read_text().splitlines()
    ]
    for event in events[2:]:
        event["dnrd_request_sha256"] = events[0]["dnrd_request_sha256"]
    (tmp_path / "model_events.jsonl").write_bytes(
        b"".join(canonical_json(event) + b"\n" for event in events)
    )
    _refresh_bundle_index(tmp_path)

    result = judge.judge_bundle(tmp_path)

    assert result["terminal"] == "VOID_PROTOCOL"
    assert "repeats a request identity across ordinals" in result["failure_reason"]


@pytest.mark.parametrize("mutation", ["stage", "message"])
def test_inconclusive_rejected_stage_must_derive_from_exact_message(
    tmp_path: Path, mutation: str
) -> None:
    _write_indexed_inconclusive_bundle(tmp_path)
    events = [json.loads(line) for line in (tmp_path / "model_events.jsonl").read_text().splitlines()]
    rejected = events[1]
    if mutation == "stage":
        rejected["failure_stage_code"] = "USAGE_NOT_OBJECT"
    else:
        rejected["failure_message"] = "chat completion must contain object usage"
        rejected["failure_message_sha256"] = sha256(rejected["failure_message"].encode()).hexdigest()
    (tmp_path / "model_events.jsonl").write_bytes(
        b"".join(canonical_json(event) + b"\n" for event in events)
    )
    _refresh_bundle_index(tmp_path)

    result = judge.judge_bundle(tmp_path)

    assert result["terminal"] == "VOID_PROTOCOL"
    assert result["authority"] == "INCOMPLETE_OR_INVALID_EVIDENCE_BUNDLE_NOT_VERIFIED"
    assert "message does not derive" in result["failure_reason"]


def _write_oversize_single_rejected_occurrence(tmp_path: Path) -> None:
    _write_indexed_inconclusive_bundle(tmp_path)
    raw = b"x" * 1_048_577
    message = "chat completion response exceeds frozen 1 MiB byte limit"
    events = [json.loads(line) for line in (tmp_path / "model_events.jsonl").read_text().splitlines()]
    rejected = events[1]
    del rejected["raw_response_sha256"]
    del rejected["raw_response_bytes"]
    rejected["retained_response_prefix_encoding"] = "base64"
    rejected["retained_response_prefix_base64"] = base64.b64encode(raw).decode("ascii")
    rejected["retained_response_prefix_sha256"] = sha256(raw).hexdigest()
    rejected["retained_response_prefix_bytes"] = len(raw)
    rejected["response_body_bytes_lower_bound"] = len(raw)
    rejected["failure_stage_code"] = "RESPONSE_BODY_EXCEEDS_1_MIB"
    rejected["failure_message"] = message
    rejected["failure_message_sha256"] = sha256(message.encode()).hexdigest()
    del rejected["raw_response_encoding"]
    del rejected["raw_response_base64"]
    (tmp_path / "model_events.jsonl").write_bytes(canonical_json(rejected) + b"\n")
    occurrence = json.loads((tmp_path / "inconclusive.json").read_text())
    occurrence["failure_digest"] = commitment({"type": "LiveBoundaryError", "message": message})
    (tmp_path / "inconclusive.json").write_bytes(canonical_json(occurrence))
    _refresh_bundle_index(tmp_path)


def test_inconclusive_oversize_single_rejected_event_is_a_valid_partial_occurrence(
    tmp_path: Path,
) -> None:
    _write_oversize_single_rejected_occurrence(tmp_path)

    result = judge.judge_bundle(tmp_path)

    assert result["terminal"] == "INCONCLUSIVE_OCCURRENCE"
    assert result["authority"] == "INDEXED_INCONCLUSIVE_MODEL_BOUNDARY_AND_RUNNER_IDENTITY_LEDGER_VERIFIED"


@pytest.mark.parametrize(
    "field, replacement",
    [
        ("retained_response_prefix_base64", "eA=="),
        ("retained_response_prefix_sha256", _sha("forged-prefix")),
        ("retained_response_prefix_bytes", 1_048_576),
        ("response_body_bytes_lower_bound", 1_048_576),
    ],
)
def test_inconclusive_oversize_prefix_evidence_tampering_is_void(
    tmp_path: Path, field: str, replacement: str | int
) -> None:
    _write_oversize_single_rejected_occurrence(tmp_path)
    event = json.loads((tmp_path / "model_events.jsonl").read_text())
    event[field] = replacement
    (tmp_path / "model_events.jsonl").write_bytes(canonical_json(event) + b"\n")
    _refresh_bundle_index(tmp_path)

    result = judge.judge_bundle(tmp_path)

    assert result["terminal"] == "VOID_PROTOCOL"
    assert "retained prefix" in result["failure_reason"]


def test_bundle_index_rejects_native_path_sort_prefix_collision(tmp_path: Path) -> None:
    _write_indexed_inconclusive_bundle(tmp_path)
    (tmp_path / "node_modules" / "@types" / "node" / "assert").mkdir(parents=True)
    (tmp_path / "node_modules" / "@types" / "node" / "assert.d.ts").write_text("a", encoding="ascii")
    (tmp_path / "node_modules" / "@types" / "node" / "assert" / "strict.d.ts").write_text("b", encoding="ascii")
    _refresh_bundle_index(tmp_path, reverse_prefix_collision=True)

    result = judge.judge_bundle(tmp_path)

    assert result["terminal"] == "VOID_PROTOCOL"
    assert "paths must be sorted" in result["failure_reason"]


def test_malformed_bundle_candidate_is_refused(tmp_path: Path) -> None:
    (tmp_path / "candidate.json").write_text('{"schema_version":"x","schema_version":"y"}', encoding="utf-8")
    with pytest.raises(judge.BundleRefusal, match="repeats JSON key"):
        judge.judge_bundle(tmp_path)


def _v2_bytes(value: object) -> bytes:
    return judge._v2_canonical_bytes(value, "test raw V2 value")


def _v2_descriptor(raw: bytes, media_type: str) -> dict[str, object]:
    return {"mediaType": media_type, "byteLength": len(raw), "sha256": sha256(raw).hexdigest()}


def _minimal_raw_v2_mount() -> tuple[dict[str, bytes], dict[str, object], dict[str, object]]:
    """A byte-addressed bootstrap mount used to exercise the stdlib replay."""
    mount_id = "dnrd-mount-v1-00000000-0000-4000-8000-000000000001"
    context_key = "context-0"
    context_sha = sha256(context_key.encode()).hexdigest()
    stratum = "stratum:" + sha256(b"stream-0").hexdigest()
    registry = {
        "mount_id": mount_id,
        "route_ids": ["route-0", "route-1"],
        "contexts": [{"context_key": context_key, "context_sha256": context_sha, "stratum": stratum}],
        "matched_derangement": {},
        "episodes": [],
        "training": [],
    }
    payload = {
        "schemaVersion": "hswm-dnrd-routing-payload/v1",
        "contexts": [{
            "contextSha256": context_sha,
            "stratum": stratum,
            "routes": [{"routeId": "route-0", "scoreMicros": 0}, {"routeId": "route-1", "scoreMicros": 0}],
        }],
        "structuralStatus": "LOCAL_EXPERIMENTAL_ROUTING_PAYLOAD_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING",
    }
    payload_raw = _v2_bytes(payload)
    payload_descriptor = _v2_descriptor(payload_raw, judge.V2_DNRD_CONTENT_MEDIA_TYPE)
    routing_key = {
        "schemaVersion": judge.V2_SCHEMA_VERSION,
        "lineageId": judge.V2_LINEAGE,
        "atomUid": "dnrd:routing",
        "revisionId": 0,
    }
    atom = {
        "_tag": "CanonicalAtomV2",
        "contractVersion": "hswm-canonical-atom/v2",
        "key": routing_key,
        "kind": "dnrd:routing-disposition",
        "responsibilityOwner": judge.V2_ROUTING_OWNER,
        "content": payload_descriptor,
        "provenance": {"mode": "BOOTSTRAP", "evidenceSha256": payload_descriptor["sha256"], "sourceRef": None},
        "lifecycle": "ADMITTED",
        "references": [],
    }
    atom_raw = _v2_bytes(atom)
    atom_descriptor = _v2_descriptor(atom_raw, judge.V2_ATOM_ENVELOPE_MEDIA_TYPE)
    decided_at = "2026-08-27T00:00:00.000Z"
    provenance = {
        "contract_version": "hswm-dnrd-local-transition-provenance/v1",
        "clock_trust": "UNATTESTED_OS_CLOCK_ORDER_ESTABLISHED_BY_STATE_REVISION_ONLY",
        "decided_at": decided_at,
        "expected_state_revision": 0,
        "read_set": [],
        "trace_ref": None,
        "writes": [{
            "key": routing_key,
            "kind": atom["kind"],
            "responsibility_owner": atom["responsibilityOwner"],
            "content": payload_descriptor,
            "atom_provenance": atom["provenance"],
            "lifecycle": "ADMITTED",
            "references": [],
        }],
    }
    provenance_raw = _v2_bytes(provenance)
    provenance_sha = sha256(provenance_raw).hexdigest()
    transition_id = "dnrd:transition:0:dnrd:routing"
    receipt = {
        "_tag": "CanonicalAtomV2EffectReceipt",
        "contractVersion": "hswm-canonical-effect-receipt/v2",
        "transitionId": transition_id,
        "schemaVersion": judge.V2_SCHEMA_VERSION,
        "previousStateRevision": 0,
        "nextStateRevision": 1,
        "readSet": [],
        "writeSet": [routing_key],
        "traceRef": None,
        "guard": {
            "schema": "PASSED", "ownerTotality": "PASSED", "references": "PASSED", "revision": "PASSED",
            "permission": "REFERENCE_GRANT_MATCHED_NOT_CANONICAL_PERMIT",
        },
        "actorClaim": judge.V2_ACTOR,
        "authorizationRef": judge.V2_AUTHORIZATION,
        "scope": judge.V2_SCOPE,
        "decidedAt": decided_at,
        "decision": "ACCEPTED",
        "provenanceSha256": provenance_sha,
    }
    schema_descriptor, schema_raw = judge._v2_expected_schema_descriptor()
    schema_binding = {"schemaVersion": judge.V2_SCHEMA_VERSION, "content": schema_descriptor}
    initial_state = {
        "schemaVersion": judge.V2_SCHEMA_VERSION,
        "revision": 0,
        "bootstrapClosed": False,
        "atoms": [],
        "acceptedTransitionIds": [],
    }
    genesis = {
        "_tag": "CanonicalAtomV2StateJournalGenesis",
        "contractVersion": judge.V2_JOURNAL_CONTRACT,
        "encoding": judge.V2_JSON_SCHEMA,
        "journalLineageId": judge.V2_LINEAGE,
        "schema": schema_binding,
        "stateRevision": 0,
        "bootstrapClosed": False,
        "predecessor": None,
        "resultingStateSha256": sha256(_v2_bytes(initial_state)).hexdigest(),
    }
    genesis_raw = _v2_bytes(genesis)
    genesis_descriptor = _v2_descriptor(genesis_raw, judge.V2_JOURNAL_MEDIA_TYPE)
    final_state = {
        "schemaVersion": judge.V2_SCHEMA_VERSION,
        "revision": 1,
        "bootstrapClosed": True,
        "atoms": [atom],
        "acceptedTransitionIds": [transition_id],
    }
    commit = {
        "_tag": "CanonicalAtomV2StateJournalCommit",
        "contractVersion": judge.V2_JOURNAL_CONTRACT,
        "encoding": judge.V2_JSON_SCHEMA,
        "journalLineageId": judge.V2_LINEAGE,
        "schema": schema_binding,
        "stateRevision": 1,
        "predecessor": genesis_descriptor,
        "receipt": receipt,
        "writeBindings": [{"key": routing_key, "payload": payload_descriptor, "envelope": atom_descriptor}],
        "previousStateSha256": genesis["resultingStateSha256"],
        "resultingStateSha256": sha256(_v2_bytes(final_state)).hexdigest(),
        "durability": "LOCAL_PREDECESSOR_BOUND_JOURNAL_V1_NOT_CANONICAL_PERMIT_NOT_LEARNING",
    }
    commit_raw = _v2_bytes(commit)
    files: dict[str, bytes] = {}
    prefix = f"mounts/{mount_id}/"
    binding_name = sha256(_v2_bytes({"schemaVersion": judge.V2_SCHEMA_VERSION})).hexdigest()
    files[prefix + "schema-bindings/" + binding_name] = _v2_bytes(schema_binding)
    for raw in (schema_raw, payload_raw, atom_raw, provenance_raw):
        files[prefix + "objects/" + sha256(raw).hexdigest()] = raw
    for raw, revision in ((genesis_raw, 0), (commit_raw, 1)):
        digest = sha256(raw).hexdigest()
        files[prefix + "journal-objects/" + digest] = raw
        files[prefix + "journal-slots/" + judge._v2_slot_name(judge.V2_LINEAGE, schema_descriptor["sha256"], revision)] = raw
    return files, {"mount_id": mount_id}, registry


def test_raw_v2_mount_replay_rehashes_schema_content_journal_and_provenance() -> None:
    files, mount, registry = _minimal_raw_v2_mount()
    replay = judge._replay_v2_mount(files, mount=mount, registry=registry, scorer_sha256=_sha("scorer"))
    assert replay["final_revision"] == 1
    assert replay["routing_atoms"][-1]["key"]["atomUid"] == "dnrd:routing"


def test_raw_v2_mount_replay_refuses_rehashed_journal_state_predecessor_tamper() -> None:
    files, mount, registry = _minimal_raw_v2_mount()
    prefix = f"mounts/{mount['mount_id']}/"
    slot = next(path for path in files if path.startswith(prefix + "journal-slots/") and path != prefix + "journal-slots/" + judge._v2_slot_name(judge.V2_LINEAGE, judge._v2_expected_schema_descriptor()[0]["sha256"], 0))
    original = judge._v2_object_bytes(files[slot], "test commit")
    tampered = {**original, "previousStateSha256": "0" * 64}
    raw = _v2_bytes(tampered)
    old_digest = sha256(files[slot]).hexdigest()
    del files[prefix + "journal-objects/" + old_digest]
    files[prefix + "journal-objects/" + sha256(raw).hexdigest()] = raw
    files[slot] = raw
    with pytest.raises(judge.BundleRefusal, match="predecessor/schema/state binding"):
        judge._replay_v2_mount(files, mount=mount, registry=registry, scorer_sha256=_sha("scorer"))


def test_raw_v2_mount_replay_refuses_content_object_byte_tamper() -> None:
    files, mount, registry = _minimal_raw_v2_mount()
    prefix = f"mounts/{mount['mount_id']}/objects/"
    payload_path = next(path for path, raw in files.items() if path.startswith(prefix) and b"hswm-dnrd-routing-payload/v1" in raw)
    files[payload_path] = files[payload_path] + b" "
    with pytest.raises(judge.BundleRefusal, match="filename/hash"):
        judge._replay_v2_mount(files, mount=mount, registry=registry, scorer_sha256=_sha("scorer"))


def test_raw_v2_mount_ids_require_the_exact_process_uuid_shape() -> None:
    assert judge.V2_MOUNT_ID.fullmatch(
        "dnrd-mount-v1-00000000-0000-4000-8000-000000000001"
    )
    assert judge.V2_MOUNT_ID.fullmatch("dnrd-mount-v1-" + "a" * 36) is None


def test_raw_v2_w0_full_prefix_requires_exact_genesis_and_bootstrap_records() -> None:
    files, w0_mount, registry = _minimal_raw_v2_mount()
    full_id = "dnrd-mount-v1-00000000-0000-4000-8000-000000000002"
    w0_prefix = f"mounts/{w0_mount['mount_id']}/"
    full_files = {
        path.replace(w0_prefix, f"mounts/{full_id}/", 1): raw
        for path, raw in files.items()
    }
    w0_replay = judge._replay_v2_mount(
        files, mount=w0_mount, registry=registry, scorer_sha256=_sha("scorer")
    )
    full_replay = judge._replay_v2_mount(
        full_files,
        mount={"mount_id": full_id},
        registry={**registry, "mount_id": full_id},
        scorer_sha256=_sha("scorer"),
    )
    judge._require_full_w0_bootstrap_prefix(
        w0_replay, full_replay, stream_id="stream-0"
    )
    forged = deepcopy(full_replay)
    forged["record_digests"][1] = "0" * 64
    with pytest.raises(judge.BundleRefusal, match="shared genesis/bootstrap"):
        judge._require_full_w0_bootstrap_prefix(w0_replay, forged, stream_id="stream-0")


def test_raw_mount_closure_refuses_exporter_file_bound_violation(tmp_path: Path) -> None:
    closure = tmp_path / "bridge_mount_closure"
    closure.mkdir(mode=0o700)
    path = closure / "root-config.json"
    path.write_bytes(b"x")
    path.chmod(0o400)
    manifest = {
        "files": [{
            "path": "root-config.json",
            "sha256": sha256(b"x").hexdigest(),
            "bytes": judge.MOUNT_CLOSURE_MAX_FILE_BYTES + 1,
            "mode": 0o400,
        }]
    }
    with pytest.raises(judge.BundleRefusal, match="1048576"):
        judge._closure_files(tmp_path, manifest)


@pytest.mark.parametrize("domain", ["objects", "journal-objects"])
def test_raw_mount_closure_scans_unreferenced_retained_bytes_for_training_canary(
    domain: str,
) -> None:
    files, mount, _ = _minimal_raw_v2_mount()
    canary = "dnrd-training-provenance:" + "b" * 32
    # This object is content-addressed and could be included in an otherwise
    # valid exported closure without appearing in the semantic V2 trajectory.
    # The canary scan intentionally runs before the later unreferenced-object
    # refusal, so it covers every retained raw byte.
    raw = _v2_bytes({"unreferenced_trace_or_journal": canary})
    digest = sha256(raw).hexdigest()
    files[f"mounts/{mount['mount_id']}/{domain}/{digest}"] = raw
    with pytest.raises(judge.BundleRefusal, match="training provenance canary"):
        judge._reject_training_canary_in_raw_closure(files, frozenset({canary}))


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _validate_source_closure_for_test(paths: set[str] | frozenset[str]) -> None:
    """Reach the source-closure gate before unrelated preregistration checks."""
    source_bytes = b"fixture source manifest bytes"
    preregistration_bytes = b"fixture preregistration bytes"
    scorer_path = "_research/dnrd/scorer.py"
    scorer_sha256 = _sha("fixture-scorer")
    judge._validate_source_and_preregistration(
        source={
            "schema_version": "hswm-dnrd-source-freeze-manifest/v1",
            "experiment_id": judge.EXPERIMENT_ID,
            "source_commit_tree_bound_externally": (
                "SOURCE_COMMIT_TREE_BOUND_EXTERNALLY_NO_SELF_CYCLE"
            ),
            "files": [
                {
                    "path": path,
                    "sha256": scorer_sha256 if path == scorer_path else _sha("fixture-source"),
                }
                for path in sorted(paths)
            ],
        },
        preregistration={},
        source_ci={},
        preregistration_ci={},
        candidate={
            "bindings": {
                "source_manifest_sha256": sha256(source_bytes).hexdigest(),
                "preregistration_sha256": sha256(preregistration_bytes).hexdigest(),
                "scorer_sha256": scorer_sha256,
            }
        },
        source_bytes=source_bytes,
        preregistration_bytes=preregistration_bytes,
        preregistration_ci_bytes=b"fixture preregistration CI receipt bytes",
    )


def test_source_manifest_refuses_a_missing_frozen_closure_path() -> None:
    paths = set(judge.FROZEN_DNRD_SOURCE_CLOSURE)
    paths.remove("_research/dnrd/__init__.py")
    with pytest.raises(judge.BundleRefusal, match="exact frozen DNRD source closure"):
        _validate_source_closure_for_test(paths)


def test_source_manifest_refuses_an_extra_closure_path() -> None:
    paths = set(judge.FROZEN_DNRD_SOURCE_CLOSURE)
    paths.add("_research/dnrd/unbound-extra.py")
    with pytest.raises(judge.BundleRefusal, match="exact frozen DNRD source closure"):
        _validate_source_closure_for_test(paths)


def _write_runtime_closure_file(root: Path, relative: str, body: bytes) -> str:
    path = root / "bridge_runtime_closure" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return sha256(body).hexdigest()


def _write_source_closure_file(root: Path, relative: str, body: bytes) -> str:
    path = root / "source_closure" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return sha256(body).hexdigest()


def _seal_fixture_closure(path: Path) -> None:
    directories = [path, *(item for item in path.rglob("*") if item.is_dir())]
    for item in path.rglob("*"):
        if item.is_file():
            item.chmod(0o400)
    for directory in sorted(directories, key=lambda item: len(item.parts), reverse=True):
        directory.chmod(0o500)


@pytest.mark.parametrize(
    "closure_name, validator",
    [
        (
            "source_closure",
            lambda root, digest: judge._validate_source_closure(
                root, {"files": [{"path": "member.txt", "sha256": digest}]}
            ),
        ),
        (
            "bridge_runtime_closure",
            lambda root, _digest: judge._runtime_closure_files(root),
        ),
    ],
)
def test_independent_judge_refuses_writable_execution_closure_member(
    tmp_path: Path, closure_name: str, validator: object
) -> None:
    closure = tmp_path / closure_name
    closure.mkdir(mode=0o700)
    member = closure / "member.txt"
    member.write_bytes(b"immutable-source-or-runtime-byte")
    member.chmod(0o600)
    closure.chmod(0o500)
    digest = sha256(member.read_bytes()).hexdigest()
    with pytest.raises(judge.BundleRefusal, match="not sealed 0400"):
        validator(tmp_path, digest)
    closure.chmod(0o700)


def _runtime_v3_closure_fixture(
    tmp_path: Path, *, include_extra_package: bool = False
) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    """Minimal v3 source/build fixture with its exact recursive package closure."""
    package_graph: dict[str, tuple[str, dict[str, str]]] = {
        "@standard-schema/spec": ("1.1.0", {}),
        "@types/node": ("24.13.3", {"undici-types": "7.18.2"}),
        "effect": ("3.22.1", {"@standard-schema/spec": "1.1.0", "fast-check": "3.23.2"}),
        "fast-check": ("3.23.2", {"pure-rand": "6.1.0"}),
        "pure-rand": ("6.1.0", {}),
        "typescript": ("5.9.3", {}),
        "undici-types": ("7.18.2", {}),
    }
    if include_extra_package:
        package_graph["unrelated"] = ("0.1.0", {})

    source_package = {
        "name": "@hswm/effect-runtime",
        "version": "fixture",
        "dependencies": {"effect": "3.22.1"},
        "devDependencies": {"@types/node": "24.13.3", "typescript": "5.9.3"},
    }
    source_lock = {
        "name": "@hswm/effect-runtime",
        "version": "fixture",
        "lockfileVersion": 3,
        "packages": {
            "": source_package,
            **{
                f"node_modules/{name}": {"version": version, "dependencies": dependencies}
                for name, (version, dependencies) in package_graph.items()
            },
        },
    }
    source_bodies = {
        "src/hswm/effect-runtime/.npmrc": b"fund=false\n",
        "src/hswm/effect-runtime/package.json": _canonical_json_bytes(source_package),
        "src/hswm/effect-runtime/package-lock.json": _canonical_json_bytes(source_lock),
        "src/hswm/effect-runtime/tsconfig.json": b'{"compilerOptions":{}}\n',
        "src/hswm/effect-runtime/tsconfig.build.json": b'{"extends":"./tsconfig.json"}\n',
        "src/hswm/effect-runtime/tsconfig.dnrd.json": b'{"extends":"./tsconfig.json"}\n',
    }
    source_rows = [
        {"path": relative, "sha256": _write_source_closure_file(tmp_path, relative, body)}
        for relative, body in sorted(source_bodies.items())
    ]

    bridge_sha = _write_runtime_closure_file(
        tmp_path, "bridge.js", b'import "effect";\nexport const bridge = true;\n'
    )
    external_packages: list[dict[str, object]] = []
    compiler: dict[str, str] | None = None
    for name, (version, dependencies) in sorted(package_graph.items()):
        package_root = f"node_modules/{name}"
        package_json_path = f"{package_root}/package.json"
        written: dict[str, str] = {
            package_json_path: _write_runtime_closure_file(
                tmp_path,
                package_json_path,
                _canonical_json_bytes(
                    {"dependencies": dependencies, "name": name, "version": version}
                ),
            )
        }
        if name == "typescript":
            written[f"{package_root}/bin/tsc"] = _write_runtime_closure_file(
                tmp_path, f"{package_root}/bin/tsc", b"#!/usr/bin/env node\n"
            )
            written[f"{package_root}/lib/tsc.js"] = _write_runtime_closure_file(
                tmp_path, f"{package_root}/lib/tsc.js", b"export {};\n"
            )
            written[f"{package_root}/lib/typescript.js"] = _write_runtime_closure_file(
                tmp_path, f"{package_root}/lib/typescript.js", b"export {};\n"
            )
            entrypoint_path = f"{package_root}/lib/tsc.js"
            compiler = {
                "package_json_path": package_json_path,
                "package_json_sha256": written[package_json_path],
                "bin_tsc_path": f"{package_root}/bin/tsc",
                "bin_tsc_sha256": written[f"{package_root}/bin/tsc"],
                "lib_tsc_path": entrypoint_path,
                "lib_tsc_sha256": written[entrypoint_path],
                "lib_typescript_path": f"{package_root}/lib/typescript.js",
                "lib_typescript_sha256": written[f"{package_root}/lib/typescript.js"],
            }
        else:
            entrypoint_path = f"{package_root}/index.js"
            written[entrypoint_path] = _write_runtime_closure_file(
                tmp_path, entrypoint_path, f"export const packageName = {name!r};\n".encode()
            )
        external_packages.append(
            {
                "name": name,
                "version": version,
                "package_root": package_root,
                "package_json_path": package_json_path,
                "package_json_sha256": written[package_json_path],
                "resolved_entrypoint_path": entrypoint_path,
                "resolved_entrypoint_sha256": written[entrypoint_path],
                "files": [
                    {"path": path, "sha256": digest, "bytes": len((tmp_path / "bridge_runtime_closure" / path).read_bytes())}
                    for path, digest in sorted(written.items())
                ],
            }
        )
    assert compiler is not None

    source_manifest_sha = sha256(b"source-manifest").hexdigest()
    manifest = {
        "schema_version": judge.RUNTIME_TREE_MANIFEST_SCHEMA,
        "root_path": "/fixture/runtime-root",
        "entrypoint": "bridge.js",
        "files": [{"path": "bridge.js", "sha256": bridge_sha, "bytes": len((tmp_path / "bridge_runtime_closure" / "bridge.js").read_bytes())}],
        "external_packages": external_packages,
        "build_provenance": {
            "source_a_commit": "a" * 40,
            "source_a_tree": "b" * 40,
            "source_manifest_path": "source_manifest.json",
            "source_manifest_sha256": source_manifest_sha,
            "node_executable_sha256": sha256(b"node").hexdigest(),
            "node_version": "vfixture",
            "dependency_materialization_command": list(judge.RUNTIME_DEPENDENCY_MATERIALIZATION_COMMAND),
            "compilation_command": list(judge.RUNTIME_COMPILATION_COMMAND),
            "claim_boundary": judge.RUNTIME_BUILD_CLAIM_BOUNDARY,
            "source_inputs": source_rows,
            "package_roots": list(judge.RUNTIME_PACKAGE_ROOTS),
            "typescript": compiler,
        },
    }
    manifest_bytes = _canonical_json_bytes(manifest)
    (tmp_path / "bridge_runtime_tree_manifest.json").write_bytes(manifest_bytes)
    runtime = {
        "bridge_runtime_tree_manifest_sha256": sha256(manifest_bytes).hexdigest(),
        "bridge_runtime_root": "/fixture/runtime-root",
        "bridge_implementation_sha256": bridge_sha,
        "node_executable_sha256": sha256(b"node").hexdigest(),
        "node_version": "vfixture",
    }
    candidate_value = {
        "chronology": {"source_commit": "a" * 40, "source_tree_oid": "b" * 40},
        "bindings": {"source_manifest_sha256": source_manifest_sha},
    }
    chronology = {"source": {
        "commit_oid": "a" * 40,
        "commit_raw_utf8": "fixture",
        "tree_oid": "b" * 40,
        "commit_time_unix": 1,
        "source_manifest_path": "source_manifest.json",
        "source_manifest_blob_sha256": source_manifest_sha,
        "file_blobs": [],
    }}
    return manifest, runtime, candidate_value, {"files": source_rows, "chronology": chronology}


def _rewrite_runtime_v3_manifest(tmp_path: Path, manifest: dict[str, object], runtime: dict[str, object]) -> None:
    raw = _canonical_json_bytes(manifest)
    (tmp_path / "bridge_runtime_tree_manifest.json").write_bytes(raw)
    runtime["bridge_runtime_tree_manifest_sha256"] = sha256(raw).hexdigest()


def _replace_source_input(
    tmp_path: Path,
    manifest: dict[str, object],
    support: dict[str, object],
    relative: str,
    body: bytes,
) -> None:
    path = tmp_path / "source_closure" / relative
    path.write_bytes(body)
    digest = sha256(body).hexdigest()
    for rows in (support["files"], manifest["build_provenance"]["source_inputs"]):
        next(row for row in rows if row["path"] == relative)["sha256"] = digest


def _validate_runtime_v3_fixture(
    tmp_path: Path,
    runtime: dict[str, object],
    candidate_value: dict[str, object],
    support: dict[str, object],
) -> None:
    _seal_fixture_closure(tmp_path / "source_closure")
    _seal_fixture_closure(tmp_path / "bridge_runtime_closure")
    judge._validate_runtime_closure(
        tmp_path,
        runtime,
        source={"files": support["files"]},
        candidate=candidate_value,
        chronology=support["chronology"],
    )


def test_runtime_v3_closure_rehashes_selected_recursive_package_tree_and_build_provenance(tmp_path: Path) -> None:
    _, runtime, candidate_value, support = _runtime_v3_closure_fixture(tmp_path)
    _validate_runtime_v3_fixture(tmp_path, runtime, candidate_value, support)


def test_runtime_v4_closure_allows_only_manifest_addressed_zero_byte_regular_file(tmp_path: Path) -> None:
    manifest, runtime, candidate_value, support = _runtime_v3_closure_fixture(tmp_path)
    package = next(item for item in manifest["external_packages"] if item["name"] == "effect")
    relative = "node_modules/effect/dist/intentional-empty.js"
    digest = _write_runtime_closure_file(tmp_path, relative, b"")
    package["files"].append({"path": relative, "sha256": digest, "bytes": 0})
    package["files"].sort(key=lambda row: row["path"])
    _rewrite_runtime_v3_manifest(tmp_path, manifest, runtime)
    _validate_runtime_v3_fixture(tmp_path, runtime, candidate_value, support)

    # A zero-byte file outside the exact selected closure is still refused.
    extra_root = tmp_path / "extra-zero"
    extra_root.mkdir()
    _, runtime, candidate_value, support = _runtime_v3_closure_fixture(extra_root)
    _write_runtime_closure_file(extra_root, "node_modules/effect/dist/unlisted-empty.js", b"")
    with pytest.raises(judge.BundleRefusal, match="file closure is not exact"):
        _validate_runtime_v3_fixture(extra_root, runtime, candidate_value, support)

    mismatch_root = tmp_path / "size-mismatch"
    mismatch_root.mkdir()
    manifest, runtime, candidate_value, support = _runtime_v3_closure_fixture(mismatch_root)
    package = next(item for item in manifest["external_packages"] if item["name"] == "effect")
    relative = "node_modules/effect/dist/intentional-empty.js"
    digest = _write_runtime_closure_file(mismatch_root, relative, b"")
    package["files"].append({"path": relative, "sha256": digest, "bytes": 1})
    package["files"].sort(key=lambda row: row["path"])
    _rewrite_runtime_v3_manifest(mismatch_root, manifest, runtime)
    with pytest.raises(judge.BundleRefusal, match="copy hash mismatch"):
        _validate_runtime_v3_fixture(mismatch_root, runtime, candidate_value, support)


def test_runtime_v3_closure_refuses_omitted_or_extra_deep_package_bytes(tmp_path: Path) -> None:
    _, runtime, candidate_value, support = _runtime_v3_closure_fixture(tmp_path)
    (tmp_path / "bridge_runtime_closure" / "node_modules/typescript/lib/typescript.js").unlink()
    with pytest.raises(judge.BundleRefusal, match="copy hash mismatch"):
        _validate_runtime_v3_fixture(tmp_path, runtime, candidate_value, support)

    tmp_path_2 = tmp_path / "fresh"
    tmp_path_2.mkdir()
    _, runtime, candidate_value, support = _runtime_v3_closure_fixture(tmp_path_2)
    _write_runtime_closure_file(
        tmp_path_2, "node_modules/typescript/lib/deep/unlisted.js", b"export {};\n"
    )
    with pytest.raises(judge.BundleRefusal, match="package file closure is not exact"):
        _validate_runtime_v3_fixture(tmp_path_2, runtime, candidate_value, support)


@pytest.mark.parametrize(
    "field, replacement",
    [
        ("dependency_materialization_command", ["npm", "install"]),
        ("compilation_command", ["node", "tsc"]),
        ("claim_boundary", "BUILD_REEXECUTED"),
        ("source_inputs", []),
    ],
)
def test_runtime_v3_closure_refuses_tampered_build_commands_or_boundary(
    tmp_path: Path, field: str, replacement: object
) -> None:
    manifest, runtime, candidate_value, support = _runtime_v3_closure_fixture(tmp_path)
    manifest["build_provenance"][field] = replacement
    _rewrite_runtime_v3_manifest(tmp_path, manifest, runtime)
    with pytest.raises(judge.BundleRefusal, match="build provenance|source inputs"):
        _validate_runtime_v3_fixture(tmp_path, runtime, candidate_value, support)


def test_runtime_v3_closure_refuses_missing_transitive_or_extra_selected_package(tmp_path: Path) -> None:
    manifest, runtime, candidate_value, support = _runtime_v3_closure_fixture(tmp_path)
    manifest["external_packages"] = [
        row for row in manifest["external_packages"] if row["name"] != "pure-rand"
    ]
    _rewrite_runtime_v3_manifest(tmp_path, manifest, runtime)
    with pytest.raises(judge.BundleRefusal, match="omits a required root or transitive dependency"):
        _validate_runtime_v3_fixture(tmp_path, runtime, candidate_value, support)

    extra_root = tmp_path / "extra"
    extra_root.mkdir()
    _, runtime, candidate_value, support = _runtime_v3_closure_fixture(
        extra_root, include_extra_package=True
    )
    with pytest.raises(judge.BundleRefusal, match="exact recursive selected dependency closure"):
        _validate_runtime_v3_fixture(extra_root, runtime, candidate_value, support)


def test_runtime_v3_closure_refuses_source_lock_package_version_mismatch(tmp_path: Path) -> None:
    manifest, runtime, candidate_value, support = _runtime_v3_closure_fixture(tmp_path)
    lock_path = "src/hswm/effect-runtime/package-lock.json"
    lock = json.loads((tmp_path / "source_closure" / lock_path).read_text(encoding="utf-8"))
    lock["packages"]["node_modules/effect"]["version"] = "9.9.9"
    _replace_source_input(tmp_path, manifest, support, lock_path, _canonical_json_bytes(lock))
    _rewrite_runtime_v3_manifest(tmp_path, manifest, runtime)
    with pytest.raises(judge.BundleRefusal, match="package-lock pin"):
        _validate_runtime_v3_fixture(tmp_path, runtime, candidate_value, support)


def test_runtime_v3_closure_refuses_compiler_pin_tamper(tmp_path: Path) -> None:
    manifest, runtime, candidate_value, support = _runtime_v3_closure_fixture(tmp_path)
    manifest["build_provenance"]["typescript"]["lib_tsc_sha256"] = "0" * 64
    _rewrite_runtime_v3_manifest(tmp_path, manifest, runtime)
    with pytest.raises(judge.BundleRefusal, match="TypeScript compiler bytes"):
        _validate_runtime_v3_fixture(tmp_path, runtime, candidate_value, support)
