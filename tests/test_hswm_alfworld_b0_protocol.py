"""Repository-level bindings for the sealed ALFWorld B0 preregistration."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from hswm.experiments import alfworld_b0_actor as actor
from hswm.experiments import alfworld_b0_dgx as dgx
from hswm.experiments import alfworld_b0_runtime as b0_runtime
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
    assert protocol["prospective_amendments"] == [
        {
            "id": "ARM64_PDDL_ONLY_ENVIRONMENT_ADAPTER_AND_HASH_BOUND_RUNTIME_SPLIT",
            "superseded_protocol_file_sha256": "6d1f18f3ccc0e70ed8b4ba72a98462114fe647f26e7e19919fc3c1ecb072249d",
            "trigger": "A DGX package-install engineering attempt established that upstream TextWorld 1.7.0 invokes Inform7 setup and its official archive has no aarch64 compiler payload. The attempt stopped during dependency construction.",
            "change": "Preserve the historically qualified runtime bytes; move valid_unseen-opaque lookup into a B0-only source; install the exact official TextWorld 1.7.0 revision with an explicit PDDL-only build adapter that skips Inform7 setup and supplies no Inform7 capability.",
            "prospective_boundary": "NO_B0_SELECTION_NO_ALFWORLD_EPISODE_NO_MODEL_CALL_NO_OUTCOME_OBSERVED",
        },
        {
            "id": "DGX_TRUSTED_MAINTAINER_SUDO_BWRAP_NO_USERNS_ADAPTER",
            "superseded_protocol_file_sha256": "d4448317625a617e0e687bf0bd5bc108d49dc570bad44ed96b05dff5f5d054bc",
            "trigger": "Pre-B0 fixed-action engineering qualification reached the DGX sandbox launcher but stopped before its first actor frame. No B0 selection, model call, or B0 outcome occurred. Diagnostics established that the host AppArmor policy rejects the required unprivileged user namespace and that the exact privileged no-userns adapter can import ALFWorld, register the sealed game, construct the environment, and reset it.",
            "change": "Use a B0-only source-bound noninteractive sudo Bubblewrap adapter with explicit pid, ipc, uts, net, and best-effort cgroup namespaces; no user namespace; all capabilities dropped except CAP_DAC_READ_SEARCH; and a read-only /proc/controller-pid/fd/verified-fd game bind held by the controller through worker termination. Preserve the historical runtime implementation unchanged.",
            "prospective_boundary": "NO_B0_SELECTION_NO_MODEL_CALL_NO_B0_OUTCOME_OBSERVED_ENGINEERING_RESET_DIAGNOSTIC_ONLY",
        },
        {
            "id": "VLLM_METRICS_PUBLIC_PROJECTION_REPAIR_AFTER_NEUTRAL_PROBE",
            "superseded_protocol_file_sha256": "0519fc2820c3e00438958d51824c465805b22d4faeb01da636e986c83358848c",
            "trigger": "A pre-selection engineering probe issued exactly one neutral tokenize request and one tiny schema-constrained completion on a fresh service, then refused before writing either qualification receipt because its public leakage guard rejected the expected fixed ALFWorld source-path labels. Artifact packaging also rejected root-owned compile-cache bytes. No counter delta was inspected from the failed occurrence.",
            "change": "Permit the fixed committed ALFWorld source-path labels in the aggregate source binding while continuing to forbid task identities, episodes, games, selections, observations, outcomes, prompts, messages, content, and raw evidence. Place fresh container caches in the runner cache tree rather than published outputs and repeat under a new occurrence identifier.",
            "prospective_boundary": "NO_B0_SELECTION_NO_ALFWORLD_EPISODE_NO_TASK_OUTCOME_ONE_NEUTRAL_TOKENIZE_AND_ONE_NEUTRAL_COMPLETION_OCCURRED_NO_METRIC_DELTA_INSPECTED",
        },
        {
            "id": "DGX_GB10_CUDA_LAUNCH_BLOCKING_STARTUP_STABILIZATION",
            "superseded_protocol_file_sha256": "c2cda2508e968072d58256cacc7e9d4c792ce7be73c097ce1136803b873e87dd",
            "trigger": "The repaired fresh-service metrics occurrence exited during vLLM memory-profile warmup with cudaErrorNotPermitted at the native fused RMSNorm path on DGX GB10 before readiness and before either neutral probe POST. The owned container was removed and shared services were restored.",
            "change": "Add CUDA_LAUNCH_BLOCKING=1 to the exact pinned container environment, following the upstream vLLM GB10 warmup-race workaround while retaining enforce-eager and every model, image, decoding, cache, and request-budget identity. Detect an exited owned startup container immediately instead of waiting for the full readiness deadline.",
            "prospective_boundary": "NO_B0_SELECTION_NO_ALFWORLD_EPISODE_NO_TASK_OUTCOME_NO_NEUTRAL_PROBE_POST_STARTUP_ENGINEERING_FAILURE_ONLY",
        },
        {
            "id": "PRE_B0_ENGINEERING_EVIDENCE_AND_COMPLETION_COUNTER_SEMANTICS_BINDING",
            "superseded_protocol_file_sha256": "f754cb5fb6db2b97fa1b1a2055946f7dc63ce7c754909eec894e1848d07bc548",
            "trigger": "Before any B0 selection, one sealed fixed-look DGX runtime qualification and one fresh-service neutral vLLM metrics qualification were completed and committed. The neutral probe established that request_success_total increased by zero for one successful tokenize POST and by one for one successful completion POST, with running and prefix-cache counters remaining zero.",
            "change": "Bind both immutable public qualification manifests, require their committed bytes in the live start closure, and prospectively compare the final service success counter with issued completion POSTs only while continuing to account for tokenize and completion POSTs separately at the client gate.",
            "prospective_boundary": "NO_B0_SELECTION_NO_ALFWORLD_B0_EPISODE_NO_TASK_OUTCOME_ONE_NEUTRAL_TOKENIZE_AND_ONE_NEUTRAL_COMPLETION_ENGINEERING_PROBE_ONLY_NO_AGENT_OR_HSWM_EFFICACY",
        }
    ]
    assert protocol["registration_status"] == (
        "PROSPECTIVE_BEFORE_ANY_B0_SELECTION_ALFWORLD_EPISODE_OR_TASK_OUTCOME_"
        "AFTER_COMMITTED_ENGINEERING_RUNTIME_AND_NEUTRAL_METRICS_QUALIFICATIONS"
    )

    evidence = protocol["current_evidence"]
    assert isinstance(evidence, dict)
    # The historical qualification remains a separately bound record.  The DGX
    # and vLLM records are later, committed engineering evidence; none is a B0
    # selection, episode, task outcome, or efficacy result.
    assert evidence["runtime_qualification"] == {
        "path": "manifests/HSWM_ALFWORLD_TEXT_RUNTIME_QUALIFICATION_2026-08-30.json",
        "file_sha256": "1e1bb8fb0d6974dec7a17ef3ebfce9131dc2cbb4e4354ddafb5bd74d7bd46d12",
        "receipt_sha256": "3473dc2bd5e209b421fc7ccb214fa48191d44ec3625a5f037e033a6ea7def051",
        "status": "ENGINEERING_INSTRUMENT_QUALIFIED_G0_NOT_PASSED",
    }
    assert evidence["dgx_runtime_qualification"] == {
        "path": "manifests/HSWM_ALFWORLD_TEXT_RUNTIME_DGX_QUALIFICATION_2026-08-30.json",
        "file_sha256": "a641218babb759159714f02fd539cf508997991f9469731788353941fb98595d",
        "receipt_sha256": "1723986c3203add3cac0fe121b3cf110830c49e9873cccd737cef95a43b01422",
        "status": "ENGINEERING_INSTRUMENT_QUALIFIED_DGX_ARM64_G0_NOT_PASSED",
        "evidence_commit": "dd395b7cbacf7b5204453043ce67ef8b17db52d6",
    }
    assert evidence["vllm_metrics_qualification"] == {
        "path": "manifests/HSWM_ALFWORLD_B0_VLLM_METRICS_QUALIFICATION_2026-08-30.json",
        "file_sha256": "5a3e2ddfae77d37e1e858ebc42267b76a61805dc3dc4fcce92ec2fd706464b12",
        "receipt_sha256": "a1d40c17ad3b38f2d84f864821a50b91c0285c04b98af966c4effe4ceb05d4ca",
        "private_receipt_file_sha256": "94971d57e8f69410a4398f3f5f8cc622c88fabd8df9a6c40b0eb6c46a1f95a60",
        "status": "ENGINEERING_VLLM_METRICS_SEMANTICS_QUALIFIED_B0_NOT_RUN",
        "evidence_commit": "a45ef8fcc3be878deab3778f5dde935778276b2e",
        "probe_predecessor_protocol_sha256": "f754cb5fb6db2b97fa1b1a2055946f7dc63ce7c754909eec894e1848d07bc548",
    }
    bindings = (
        (evidence["pool_manifest"], "rendered_json_sha256"),
        (evidence["runtime_qualification"], "file_sha256"),
        (evidence["dgx_runtime_qualification"], "file_sha256"),
        (evidence["vllm_metrics_qualification"], "file_sha256"),
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


def test_dgx_runtime_and_arm64_pddl_only_requirements_are_exact() -> None:
    protocol = _protocol()
    assert protocol["model_runtime"] == dgx.MODEL_RUNTIME
    assert protocol["model_runtime"]["request_success_counter_semantics"] == (
        "COMPLETED_GENERATION_REQUESTS_ONLY_TOKENIZE_EXCLUDED"
    )
    assert protocol["model_runtime"]["successful_tokenize_post_counter_delta"] == 0
    assert protocol["model_runtime"]["successful_completion_post_counter_delta"] == 1
    assert protocol["model_runtime"]["final_service_attestation"] == (
        "REQUEST_SUCCESS_TOTAL_EQUALS_ISSUED_COMPLETION_POST_COUNT_"
        "TOKENIZE_ACCOUNTED_SEPARATELY"
    )

    environment = protocol["environment_runtime"]
    assert isinstance(environment, dict)
    assert environment["sandbox"] == b0_runtime.dgx_sandbox_contract()
    evidence = protocol["current_evidence"]
    assert isinstance(evidence, dict)
    assert environment["dgx_fixed_action_qualification"] == evidence[
        "dgx_runtime_qualification"
    ]
    inherited = REPOSITORY_ROOT / str(environment["inherited_requirements_path"])
    assert sha256(inherited.read_bytes()).hexdigest() == environment[
        "inherited_requirements_sha256"
    ]
    requirements = REPOSITORY_ROOT / str(
        environment["arm64_pddl_only_requirements_path"]
    )
    raw = requirements.read_bytes()
    assert sha256(raw).hexdigest() == environment["arm64_pddl_only_requirements_sha256"]
    package_lines = [
        line.strip().lower()
        for line in raw.decode("utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert all(not line.startswith(("-e", "--editable", "alfworld", "hswm")) for line in package_lines)
    assert "alfworld" not in "\n".join(package_lines)
    assert "hswm" not in "\n".join(package_lines)
    assert "textworld==1.7.0" not in package_lines
    inherited_lines = [
        line.strip().lower()
        for line in inherited.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert set(inherited_lines) - set(package_lines) == {"textworld==1.7.0"}
    assert set(package_lines) <= set(inherited_lines)

    textworld = environment["textworld"]
    assert textworld == {
        "upstream_repository": "https://github.com/microsoft/TextWorld",
        "upstream_tag": "1.7.0",
        "upstream_revision": "9fce9ee107fa042ef2656e41e0b362450a35ecd8",
        "patch_path": "_research/causal_composition/preregistrations/alfworld_b0_calibration_2026-08-30/textworld-pddl-only.v1.patch",
        "patch_sha256": "8b623fe87548694b3990896d69260ae3325c2d686cac62c7daf3963a23772c1d",
        "install_environment": {"TEXTWORLD_PDDL_ONLY": "1"},
        "capability": "PDDL_ONLY_NO_INFORM7_SETUP_OR_CAPABILITY",
    }
    patch = REPOSITORY_ROOT / str(textworld["patch_path"])
    assert sha256(patch.read_bytes()).hexdigest() == textworld["patch_sha256"]
    patch_text = patch.read_text(encoding="utf-8")
    assert "os.environ.get(\"TEXTWORLD_PDDL_ONLY\") == \"1\"" in patch_text
    assert "def _pre_install(dir):" in patch_text
    assert "if _pddl_only_install():" in patch_text
    assert environment["install_order"] == [
        "install arm64_pddl_only_requirements exactly",
        "checkout TextWorld upstream_revision exactly",
        "verify and apply textworld.patch_path",
        "install patched TextWorld with TEXTWORLD_PDDL_ONLY=1 and --no-deps",
        "install source-pinned ALFWorld with --no-deps",
        "supply HSWM from the clean execution checkout through PYTHONPATH",
    ]


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
        "_research/causal_composition/preregistrations/alfworld_b0_calibration_2026-08-30/alfworld_text_runtime.arm64_pddl_only.requirements.v1.txt",
        "_research/causal_composition/preregistrations/alfworld_b0_calibration_2026-08-30/textworld-pddl-only.v1.patch",
        "_research/causal_composition/preregistrations/alfworld_b0_calibration_2026-08-30/runtime_qualification_contract.v1.json",
        "manifests/HSWM_ALFWORLD_TEXT_CLEAN_POOL_2026-08-30.json",
        "manifests/HSWM_ALFWORLD_TEXT_RUNTIME_DGX_QUALIFICATION_2026-08-30.json",
        "manifests/HSWM_ALFWORLD_B0_VLLM_METRICS_QUALIFICATION_2026-08-30.json",
        "manifests/HSWM_ALFWORLD_B0_SELECTION_2026-08-30.json",
        "src/hswm/experiments/alfworld_b0_selection.py",
        "src/hswm/experiments/alfworld_b0_actor.py",
        "src/hswm/experiments/alfworld_b0_calibration.py",
        "src/hswm/experiments/alfworld_b0_dgx.py",
        "src/hswm/experiments/alfworld_b0_vllm_metrics.py",
        "src/hswm/experiments/alfworld_b0_live.py",
        "src/hswm/experiments/alfworld_b0_runtime.py",
        "src/hswm/experiments/alfworld_text_runtime.py",
        "src/hswm/experiments/alfworld_text_worker.py",
        "src/hswm/experiments/continual_live.py",
        "scripts/qualify_hswm_alfworld_b0_runtime.py",
        "scripts/qualify_hswm_alfworld_b0_vllm_metrics.py",
    }
    assert required_existing <= paths
    assert all((REPOSITORY_ROOT / path).is_file() for path in required_existing)
