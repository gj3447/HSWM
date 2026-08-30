"""Repository-level bindings for the sealed ALFWorld B0 preregistration."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from hswm.experiments import alfworld_b0_actor as actor
from hswm.experiments import alfworld_b0_dgx as dgx
from hswm.experiments.alfworld_b0_calibration import (
    COMPLETE_STATUS,
    INCONCLUSIVE_STATUS,
    VOID_STATUS,
    verify_protocol,
)
from hswm.experiments.alfworld_b0_selection import (
    B0Selection,
    OpaqueGameSelection,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION = (
    REPOSITORY_ROOT
    / "_research/causal_composition/preregistrations/alfworld_b0_calibration_2026-08-30"
)
PROTOCOL_PATH = PREREGISTRATION / "protocol.v1.json"


def _protocol() -> dict[str, object]:
    value = json.loads(PROTOCOL_PATH.read_bytes())
    assert isinstance(value, dict)
    return value


def test_checked_in_protocol_is_executable_and_hash_binds_existing_evidence() -> None:
    verified = verify_protocol(PROTOCOL_PATH)
    protocol = _protocol()
    assert verified.binding_sha256 == sha256(PROTOCOL_PATH.read_bytes()).hexdigest()

    evidence = protocol["current_evidence"]
    assert isinstance(evidence, dict)
    bindings = (
        (evidence["pool_manifest"], "rendered_json_sha256"),
        (evidence["runtime_qualification"], "file_sha256"),
        (evidence["source_audit"], "sha256"),
        (evidence["local_use_authorization"], "sha256"),
    )
    for record, hash_key in bindings:
        assert isinstance(record, dict)
        path, expected = record["path"], record[hash_key]
        assert isinstance(path, str) and isinstance(expected, str)
        assert sha256((REPOSITORY_ROOT / path).read_bytes()).hexdigest() == expected


def test_actor_prompt_schema_limits_and_gate_are_exactly_preregistered() -> None:
    protocol = _protocol()
    contract = protocol["actor_contract"]
    assert isinstance(contract, dict)
    assert contract["system_prompt_utf8"] == actor.B0_ACTION_SYSTEM_MESSAGE
    assert contract["system_prompt_sha256"] == sha256(
        actor.B0_ACTION_SYSTEM_MESSAGE.encode("utf-8")
    ).hexdigest()
    assert contract["response_schema_canonical_json"] == actor._action_schema().schema_json
    assert contract["response_schema_sha256"] == sha256(
        actor._action_schema().schema_json.encode("utf-8")
    ).hexdigest()
    assert contract["max_output_tokens_per_action"] == actor.B0_ACTION_MAX_OUTPUT_TOKENS
    assert contract["max_observation_utf8_bytes"] == actor.B0_ACTION_MAX_OBSERVATION_BYTES
    assert contract["max_canonical_user_payload_bytes"] == actor.B0_ACTION_MAX_INPUT_BYTES
    assert contract["max_prepared_chat_request_bytes"] == actor.B0_ACTION_MAX_REQUEST_BYTES
    assert actor.B0_MAX_TOKENIZE_CALLS == actor.B0_MAX_COMPLETION_CALLS == 240
    assert "including failed attempts" in str(contract["issued_post_gate"])
    assert "241st request" in str(contract["issued_post_gate"])


def test_dgx_runtime_and_requirements_are_exact_and_do_not_install_project_packages() -> None:
    protocol = _protocol()
    assert protocol["model_runtime"] == dgx.MODEL_RUNTIME

    environment = protocol["environment_runtime"]
    assert isinstance(environment, dict)
    requirements = REPOSITORY_ROOT / str(environment["requirements_path"])
    raw = requirements.read_bytes()
    assert sha256(raw).hexdigest() == environment["requirements_sha256"]
    package_lines = [
        line.strip().lower()
        for line in raw.decode("utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert all(not line.startswith(("-e", "--editable", "alfworld", "hswm")) for line in package_lines)
    assert "alfworld" not in "\n".join(package_lines)
    assert "hswm" not in "\n".join(package_lines)


def test_unseen_is_zero_touch_and_the_study_cannot_claim_g0_or_g1() -> None:
    protocol = _protocol()
    selection = protocol["prospective_selection"]
    assert isinstance(selection, dict)
    allocation = selection["allocation"]
    assert isinstance(allocation, dict)
    assert allocation["valid_unseen"] == {
        "groups_selected": 0,
        "games_selected": 0,
        "role": "UNTOUCHED_LINEAGE_DISJOINT_FINAL_HOLDOUT_CANDIDATE",
    }
    assert len(selection["valid_unseen_zero_touch"]) >= 1
    assert protocol["research_order"] == {"G0": "NOT_PASSED", "G1_THROUGH_G6": "LOCKED_BY_THIS_STUDY"}
    assert protocol["scientific_status"] == "EXPLORATORY_G0_CALIBRATION_ONLY_NOT_G0_PASS_NOT_G1_EFFICACY"
    assert protocol["allowed_terminals"] == [COMPLETE_STATUS, INCONCLUSIVE_STATUS, VOID_STATUS]

    selected = B0Selection(
        protocol_uid="study:fixture", protocol_version="v1", protocol_sha256="a" * 64,
        selector_source_sha256="b" * 64, pool_manifest_sha256="c" * 64,
        local_locator_sha256="d" * 64,
        train=(OpaqueGameSelection("train", "group:train", "game:train"),),
        valid_seen=(OpaqueGameSelection("valid_seen", "group:seen", "game:seen"),),
        selection_digest="e" * 64,
    ).public_projection()
    assert selected["status"] == "PROSPECTIVE_SELECTION_ONLY_G0_NOT_RUN"
    assert selected["selection"]["valid_unseen_selected_group_count"] == 0
    rendered = json.dumps(selected, sort_keys=True)
    assert "game:train" not in rendered and "game:seen" not in rendered


def test_execution_start_hashes_cover_live_code_and_name_future_receipts() -> None:
    protocol = _protocol()
    execution = protocol["execution_source_binding"]
    assert isinstance(execution, dict)
    paths = set(execution["start_marker_must_hash_paths"])
    required_existing = {
        "_research/causal_composition/preregistrations/alfworld_b0_calibration_2026-08-30/protocol.v1.json",
        "_research/causal_composition/preregistrations/alfworld_b0_calibration_2026-08-30/alfworld_text_runtime.requirements.v1.txt",
        "manifests/HSWM_ALFWORLD_TEXT_CLEAN_POOL_2026-08-30.json",
        "src/hswm/experiments/alfworld_b0_selection.py",
        "src/hswm/experiments/alfworld_b0_actor.py",
        "src/hswm/experiments/alfworld_b0_calibration.py",
        "src/hswm/experiments/alfworld_b0_dgx.py",
        "src/hswm/experiments/alfworld_b0_live.py",
        "src/hswm/experiments/alfworld_text_runtime.py",
        "src/hswm/experiments/alfworld_text_worker.py",
        "src/hswm/experiments/continual_live.py",
    }
    assert required_existing <= paths
    assert all((REPOSITORY_ROOT / path).is_file() for path in required_existing)
    # These are deliberately named in the preregistration before generation;
    # their absence means no qualification/selection receipt can be mistaken
    # for already committed execution input.
    planned = {
        "manifests/HSWM_ALFWORLD_TEXT_RUNTIME_DGX_QUALIFICATION_2026-08-30.json",
        "manifests/HSWM_ALFWORLD_B0_SELECTION_2026-08-30.json",
    }
    assert planned <= paths
    assert all(not (REPOSITORY_ROOT / path).exists() for path in planned)
