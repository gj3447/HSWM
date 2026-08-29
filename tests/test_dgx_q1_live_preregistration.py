from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from _research.dnrd5.canonical_json import canonical_bytes, canonical_sha256, parse_canonical
from _research.dgx_q1.live_preregistration import (
    CALL_CLASSES,
    IDENTITY_NAMES,
    LiveQ1FreezeRefusal,
    LiveQ1PreregistrationInputs,
    build_live_preregistration,
    build_verifier_source_manifest,
    freeze_live_preregistration,
)
from _research.dgx_q1.github_ci_receipt import build_github_actions_ci_receipt
from _research.dgx_q1.live_protocol import (
    validate_live_q1_plan,
    validate_live_q1_start_marker,
)


SOURCE_COMMIT = "a" * 40
SOURCE_TREE = "b" * 40
VERIFIER_COMMIT = "c" * 40
VERIFIER_TREE = "d" * 40
REVISION = "e" * 40
SERVED_MODEL = "qwen-test-q1"
ENDPOINT = "http://127.0.0.1:18080/v1/chat/completions"


def _dynamic_kernel_policy() -> dict:
    return {
        "schema_version": "hswm-dgx-q1-dynamic-kernel-rpc-listener-policy/v1",
        "program": 100021,
        "service": "nlockmgr",
        "owner": "superuser",
        "versions": [1, 3, 4],
        "netids": ["tcp", "tcp6", "udp", "udp6"],
        "tcp_wildcard_hosts": ["0.0.0.0", "[::]"],
        "nlm_tcpport": 0,
        "nlm_udpport": 0,
        "required_tcp_listener_count": 2,
        "observation": "RPCINFO_LOCAL_REGISTRATION_JOINED_TO_PRIVILEGED_HOST_TCP_LISTENER_ROWS",
    }


def ci_receipt(commit: str, tree: str, run_id: int = 1) -> bytes:
    run = {
        "id": run_id,
        "workflow_id": 2,
        "run_number": 3,
        "name": "CI",
        "path": ".github/workflows/ci.yml",
        "event": "push",
        "head_branch": "main",
        "head_sha": commit,
        "run_attempt": 1,
        "status": "completed",
        "conclusion": "success",
        "created_at": "2026-08-29T00:00:00Z",
        "run_started_at": "2026-08-29T00:00:01Z",
        "updated_at": "2026-08-29T00:00:02Z",
        "pull_requests": [],
        "repository": {"id": 1, "full_name": "gj3447/HSWM"},
        "head_repository": {"id": 1, "full_name": "gj3447/HSWM"},
        "head_commit": {"id": commit, "tree_id": tree},
    }
    query = {
        "workflow_path": ".github/workflows/ci.yml",
        "event": "push",
        "branch": "main",
        "head_sha": commit,
        "per_page": 100,
        "page": 1,
    }
    listing = {"query": query, "total_count": 1, "workflow_runs": [run]}
    jobs = {
        "query": {"run_id": run_id, "per_page": 100, "page": 1},
        "total_count": 1,
        "jobs": [{"name": "test", "status": "completed", "conclusion": "success"}],
    }
    return build_github_actions_ci_receipt(
        json.dumps(run).encode(),
        json.dumps(listing).encode(),
        json.dumps(jobs).encode(),
        repository="gj3447/HSWM",
        commit=commit,
        tree=tree,
    )


def identity_blobs() -> dict[str, bytes]:
    file_rows = [
        {
            "path": "config.json",
            "blob": sha256(b"model").hexdigest(),
            "byte_length": 5,
            "sha256": sha256(b"model").hexdigest(),
        }
    ]
    snapshot = canonical_bytes(
        {
            "schema_version": "hswm-dgx-q1-model-snapshot-manifest/v1",
            "repository": "Qwen/Qwen-Test",
            "revision": REVISION,
            "file_count": 1,
            "total_byte_length": 5,
            "files": file_rows,
            "files_sha256": canonical_sha256(file_rows),
        }
    )
    snapshot_sha = sha256(snapshot).hexdigest()
    model = canonical_bytes(
        {
            "schema_version": "hswm-dgx-q1-model-identity/v1",
            "model": SERVED_MODEL,
            "repository": "Qwen/Qwen-Test",
            "revision": REVISION,
            "snapshot_manifest_sha256": snapshot_sha,
        }
    )
    runtime = canonical_bytes(
        {
            "schema_version": "hswm-dgx-q1-runtime-identity/v1",
            "container_image": "example/vllm@sha256:" + "1" * 64,
            "image_id": "sha256:" + "2" * 64,
            "vllm_version": "0.25.1",
            "gpu_uuid": "GPU-01234567-89ab-cdef-0123-456789abcdef",
            "gpu_name": "NVIDIA Test GPU",
            "gpu_driver_version": "580.1",
            "gpu_compute_capability": "12.1",
            "endpoint": ENDPOINT,
            "served_model": SERVED_MODEL,
            "model_revision": REVISION,
            "model_snapshot_manifest_sha256": snapshot_sha,
            "max_model_len": 32768,
            "max_num_seqs": 1,
            "gpu_memory_utilization_milli": 800,
            "prefix_cache": False,
            "enforce_eager": True,
            "batch_invariant": False,
            "v1_multiprocessing": False,
            "model_loading_offline": True,
            "generation_config": "vllm",
            "engine_seed": 0,
            "language_model_only": True,
            "container_internal_port": 8000,
            "container_network_mode": "bridge",
            "container_ipc_mode": "private",
            "host_publish_ip": "127.0.0.1",
        }
    )
    return {
        "endpoint_sha256": canonical_bytes(
            {
                "schema_version": "hswm-dgx-q1-endpoint-identity/v1",
                "endpoint": ENDPOINT,
                "method": "POST",
                "transport": "LOOPBACK_HTTP_NO_TLS",
            }
        ),
        "model_identity_sha256": model,
        "runtime_identity_sha256": runtime,
        "tls_identity_sha256": canonical_bytes(
            {
                "schema_version": "hswm-dgx-q1-tls-identity/v1",
                "endpoint_scheme": "http",
                "tls": "NOT_APPLICABLE_LOOPBACK_ONLY",
            }
        ),
        "declared_isolation_contract_sha256": canonical_bytes(
            {
                "schema_version": "hswm-dgx-q1-declared-isolation/v3",
                "batch_invariant": False,
                "boundary": (
                    "FINITE_DECLARED_SERIALIZED_CONTROL_CONTRACT_WITHOUT_BATCH_INVARIANCE"
                ),
                "dedicated_gpu": True,
                "dedicated_node": True,
                "dedicated_process": True,
                "max_num_seqs": 1,
                "network_scope": "LOOPBACK_INGRESS_ONLY_OUTBOUND_NOT_ATTESTED",
                "other_inference_processes": 0,
                "prefix_cache": False,
                "v1_multiprocessing": False,
                "host_listener_allowlist": [
                    "127.0.0.1:22",
                    "127.0.0.54%lo:53",
                    "[::1]:22",
                    "[fd00::1]:443",
                ],
                "host_listener_allowlist_sha256": sha256(
                    b"127.0.0.1:22\n127.0.0.54%lo:53\n[::1]:22\n[fd00::1]:443"
                ).hexdigest(),
                "host_listener_policy": (
                    "EXACT_FROZEN_STATIC_PLUS_RPCBOUND_DYNAMIC_NLOCKMGR_PLUS_ONE_Q1_TARGET"
                ),
                "dynamic_kernel_rpc_listener_policy": _dynamic_kernel_policy(),
            }
        ),
        "model_snapshot_manifest_sha256": snapshot,
    }


def preregistration_inputs() -> LiveQ1PreregistrationInputs:
    verifier_source = Path(
        "_research/dgx_q1/independent_live_verifier.py"
    ).read_bytes()
    return LiveQ1PreregistrationInputs(
        source_commit=SOURCE_COMMIT,
        source_tree=SOURCE_TREE,
        source_ci_receipt=ci_receipt(SOURCE_COMMIT, SOURCE_TREE),
        verifier_commit=VERIFIER_COMMIT,
        verifier_tree=VERIFIER_TREE,
        verifier_ci_receipt=ci_receipt(VERIFIER_COMMIT, VERIFIER_TREE, 2),
        verifier_build=build_verifier_source_manifest(verifier_source),
        identities=identity_blobs(),
        call_order_seed=b"s" * 32,
        root_genesis=canonical_bytes(
            {
                "schema_version": "hswm-dgx-q1-evidence-root-genesis/v1",
                "nonce_hex": "3" * 64,
                "purpose": "FRESH_SINGLE_USE_LIVE_Q1_EVIDENCE_ROOT",
                "terminal": "GENESIS_BOUND_BEFORE_ANY_LIVE_START",
            }
        ),
    )


def test_builds_bound_q0_public_24_case_live_plan() -> None:
    artifacts = build_live_preregistration(preregistration_inputs())
    plan = validate_live_q1_plan(artifacts["plan.json"])
    validate_live_q1_start_marker(
        artifacts["start_marker.json"], artifacts["plan.json"]
    )
    assert len(plan["corpus"]) == 24 and plan["budget"] == 96
    assert {row["call_class"] for row in plan["corpus"]} == set(CALL_CLASSES)
    assert set(plan["identities"]) == set(IDENTITY_NAMES)
    assert len(parse_canonical(artifacts["closure_manifest.json"])["artifacts"]) == len(
        artifacts
    ) - 1


def test_freezer_refuses_dynamic_nlockmgr_policy_or_static_listener_drift() -> None:
    item = preregistration_inputs()
    identities = dict(item.identities)
    declared = parse_canonical(identities["declared_isolation_contract_sha256"])
    declared["host_listener_allowlist"] = ["127.0.0.1:11434"]
    declared["host_listener_allowlist_sha256"] = sha256(
        b"127.0.0.1:11434"
    ).hexdigest()
    identities["declared_isolation_contract_sha256"] = canonical_bytes(declared)
    values = {name: getattr(item, name) for name in item.__dataclass_fields__}
    values["identities"] = identities
    with pytest.raises(LiveQ1FreezeRefusal, match="declared isolation"):
        build_live_preregistration(LiveQ1PreregistrationInputs(**values))


@pytest.mark.parametrize("change", ["source", "ci", "seed", "identity", "build"])
def test_refuses_adversarial_binding_drift(change: str) -> None:
    item = preregistration_inputs()
    values = {name: getattr(item, name) for name in item.__dataclass_fields__}
    if change == "source":
        values["source_commit"] = "f" * 40
    elif change == "ci":
        values["source_ci_receipt"] = b"not canonical"
    elif change == "seed":
        values["call_order_seed"] = b"x"
    elif change == "identity":
        values["identities"] = {"endpoint_sha256": b"x"}
    else:
        values["verifier_build"] = canonical_bytes({"build": "unbound"})
    with pytest.raises(LiveQ1FreezeRefusal):
        build_live_preregistration(LiveQ1PreregistrationInputs(**values))


def test_freezer_requires_fresh_output_and_writes_typed_files(tmp_path: Path) -> None:
    output = tmp_path / "freeze"
    freeze_live_preregistration(output, preregistration_inputs())
    assert (output / "plan.json").is_file()
    assert (output / "materials/QCASE-001/model_input.json").is_file()
    with pytest.raises(LiveQ1FreezeRefusal):
        freeze_live_preregistration(output, preregistration_inputs())
