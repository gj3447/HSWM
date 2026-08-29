from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

import pytest

from _research.dnrd5.canonical_json import canonical_bytes, canonical_sha256, parse_canonical
from _research.dgx_q1.independent_live_verifier import (
    INCONCLUSIVE,
    TEST_FALSIFIED,
    TEST_INCONCLUSIVE,
    TEST_REPRODUCED,
    VOID,
    _external_consumption_witness,
    verify,
)
from _research.dgx_q1.live_preregistration import (
    build_live_preregistration,
    q0_public_materials,
)
from _research.dgx_q1.live_protocol import (
    BOUNDARY_SCHEMA,
    NAMESPACE,
    LiveQ1Refusal,
    dynamic_kernel_rpc_tcp_listeners,
    listener_inventory_sha256,
    validate_boundary_attestation,
)
from _research.dgx_q1.live_runner import LiveObservation, LiveQ1Runner
from tests.test_dgx_q1_live_preregistration import preregistration_inputs


def _bundle() -> tuple[dict[str, bytes], tuple]:
    artifacts = build_live_preregistration(preregistration_inputs())
    _, materials = q0_public_materials()
    return artifacts, materials


def _identities(artifacts: dict[str, bytes]) -> dict[str, bytes]:
    return {
        path.removeprefix("identities/").removesuffix(".json"): raw
        for path, raw in artifacts.items()
        if path.startswith("identities/")
    }


def _provenance(artifacts: dict[str, bytes]) -> dict[str, bytes]:
    return {
        path.removeprefix("provenance/").removesuffix(".json"): raw
        for path, raw in artifacts.items()
        if path.startswith("provenance/")
    }


def _dynamic_registrations(
    ipv4_port: int = 40000, ipv6_port: int = 40000
) -> list[dict]:
    ipv4_high, ipv4_low = divmod(ipv4_port, 256)
    ipv6_high, ipv6_low = divmod(ipv6_port, 256)
    rows = [
        {
            "program": 100021,
            "version": version,
            "netid": netid,
            "address": (
                f"0.0.0.0.{ipv4_high}.{ipv4_low}"
                if netid in {"tcp", "udp"}
                else f"::.{ipv6_high}.{ipv6_low}"
            ),
            "service": "nlockmgr",
            "owner": "superuser",
        }
        for version in (1, 3, 4)
        for netid in ("tcp", "tcp6", "udp", "udp6")
    ]
    return sorted(rows, key=canonical_bytes)


def test_dynamic_nlockmgr_tcp_family_ports_may_differ() -> None:
    registrations = _dynamic_registrations(33965, 37197)
    assert dynamic_kernel_rpc_tcp_listeners(registrations) == (
        "0.0.0.0:33965",
        "[::]:37197",
    )


@pytest.mark.parametrize("tamper", ("duplicate_target", "userspace_dynamic"))
def test_boundary_rejects_auditable_listener_row_tampering(
    tmp_path: Path, tamper: str
) -> None:
    artifacts, _ = _bundle()
    plan_raw = artifacts["plan.json"]
    runtime = parse_canonical(_identities(artifacts)["runtime_identity_sha256"])
    receipt = parse_canonical(_attestation(plan_raw, runtime, "STARTUP", None, 0))
    rows = list(receipt["host_tcp_listener_rows"])
    if tamper == "duplicate_target":
        rows.append("LISTEN 1 1 127.0.0.1:18080 0.0.0.0:*")
    else:
        index = next(index for index, row in enumerate(rows) if "0.0.0.0:40000" in row)
        rows[index] += ' users:(("nlockmgr",pid=1,fd=3))'
    receipt["host_tcp_listener_rows"] = sorted(rows)
    receipt["host_tcp_listener_rows_sha256"] = canonical_sha256(
        receipt["host_tcp_listener_rows"]
    )
    with pytest.raises(LiveQ1Refusal):
        validate_boundary_attestation(
            canonical_bytes(receipt),
            plan_raw,
            phase="STARTUP",
            attempt_id=None,
            completed_attempts=0,
            declared_isolation_raw=_identities(artifacts)[
                "declared_isolation_contract_sha256"
            ],
            target="127.0.0.1:18080",
        )


def _attestation(
    plan_raw: bytes,
    runtime: dict,
    phase: str,
    attempt_id: str | None,
    completed: int,
) -> bytes:
    plan = parse_canonical(plan_raw)
    registrations = _dynamic_registrations()
    listeners = dynamic_kernel_rpc_tcp_listeners(registrations)
    static = [
        "127.0.0.1:22",
        "127.0.0.54%lo:53",
        "[::1]:22",
        "[fd00::1]:443",
    ]
    host_rows = sorted(
        f"LISTEN 0 4096 {endpoint} 0.0.0.0:*"
        for endpoint in [*static, *listeners, "127.0.0.1:18080"]
    )
    return canonical_bytes(
        {
            "schema_version": BOUNDARY_SCHEMA,
            "namespace": NAMESPACE,
            "q1_sha256": sha256(plan_raw).hexdigest(),
            "phase": phase,
            "attempt_id": attempt_id,
            "completed_attempts": completed,
            "endpoint_sha256": plan["identities"]["endpoint_sha256"],
            "model_identity_sha256": plan["identities"]["model_identity_sha256"],
            "runtime_identity_sha256": plan["identities"]["runtime_identity_sha256"],
            "model_snapshot_manifest_sha256": plan["identities"][
                "model_snapshot_manifest_sha256"
            ],
            "container_id_sha256": sha256(b"container").hexdigest(),
            "image_id": runtime["image_id"],
            "configured_image": runtime["container_image"],
            "container_start_sha256": sha256(b"start").hexdigest(),
            "cgroup_sha256": sha256(b"cgroup").hexdigest(),
            "argv_sha256": sha256(b"argv").hexdigest(),
            "gpu_uuid": runtime["gpu_uuid"],
            "gpu_compute_pids": [123],
            "host_listener_present": True,
            "container_init_pid": 1,
            "container_network_namespace_sha256": sha256(b"net:[1]").hexdigest(),
            "container_tcp_tables_sha256": sha256(b"tcp tables").hexdigest(),
            "internal_listener_port": 8000,
            "host_listener_inventory_sha256": listener_inventory_sha256(
                sorted([*static, *listeners, "127.0.0.1:18080"])
            ),
            "host_tcp_listener_rows": host_rows,
            "host_tcp_listener_rows_sha256": canonical_sha256(host_rows),
            "dynamic_kernel_rpc_registrations": registrations,
            "dynamic_kernel_rpc_registrations_sha256": canonical_sha256(registrations),
            "dynamic_kernel_rpc_tcp_listeners": list(listeners),
            "nlm_tcpport": 0,
            "nlm_udpport": 0,
            "unexpected_listener_count": 0,
            "requests_running": 0,
            "request_success_total": completed,
            "prefix_cache_hits": 0,
            "prefix_cache_queries": 0,
            "raw_metrics_sha256": sha256(
                canonical_bytes([phase, attempt_id, completed])
            ).hexdigest(),
            "boundary": "FINITE_OBSERVED_CONTROLS_NOT_NO_INTERFERENCE_PROOF",
            "nonclaim": (
                "NOT_DISPATCH_AUTHORIZATION_OR_SOURCE_A_PERMIT_OR_NO_INTERFERENCE_PROOF"
            ),
        }
    )


def _response(request_raw: bytes, *, answer: str = "OK") -> LiveObservation:
    request = parse_canonical(request_raw)
    schema = request["response_format"]["json_schema"]["schema"]
    rationale_minimum = schema["properties"]["rationale"]["minLength"]
    content = json.dumps(
        {"rationale": "A" * rationale_minimum, "answer": answer},
        ensure_ascii=False,
        indent=1,
    )
    envelope = canonical_bytes(
        {
            "model": request["model"],
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": content},
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }
    )
    return LiveObservation(200, envelope, "application/json", "request-fixture")


def _runner(
    root: Path,
    artifacts: dict[str, bytes],
    materials: tuple,
    transport,
    *,
    attester=None,
) -> LiveQ1Runner:
    plan_raw = artifacts["plan.json"]
    identities = _identities(artifacts)
    runtime = parse_canonical(identities["runtime_identity_sha256"])
    boundary = attester or (
        lambda phase, attempt, completed: _attestation(
            plan_raw, runtime, phase, attempt, completed
        )
    )
    registry = root.parent / "q1-consumption-registry"
    registry.mkdir(mode=0o700, exist_ok=True)
    return LiveQ1Runner(
        root,
        plan_raw,
        artifacts["start_marker.json"],
        artifacts["corpus_manifest.json"],
        materials,
        identities,
        _provenance(artifacts),
        artifacts["root_genesis.json"],
        artifacts["closure_manifest.json"],
        _attestation(plan_raw, runtime, "STARTUP", None, 0),
        boundary,
        consumption_root=registry,
        transport_for_testing=transport,
        fixture_mode=True,
    )


def test_unified_runner_yields_independently_verified_reproduction(tmp_path: Path) -> None:
    artifacts, materials = _bundle()
    calls: list[bytes] = []

    def transport(_: str, request: bytes, __: int) -> LiveObservation:
        calls.append(request)
        return _response(request)

    runner = _runner(tmp_path / "root", artifacts, materials, transport)
    rows = runner.execute_all()
    assert len(rows) == 96
    assert len(calls) == 96
    assert len(set(calls)) == 24
    assert verify(tmp_path / "root")["terminal"] == INCONCLUSIVE
    assert verify(tmp_path / "root", allow_test_fixture=True)["terminal"] == TEST_REPRODUCED
    with pytest.raises(LiveQ1Refusal, match="sealed"):
        runner.execute_all()


def test_exact_utf8_difference_falsifies_without_call_replacement(tmp_path: Path) -> None:
    artifacts, materials = _bundle()
    seen: Counter[str] = Counter()

    def transport(_: str, request: bytes, __: int) -> LiveObservation:
        digest = sha256(request).hexdigest()
        seen[digest] += 1
        return _response(request, answer="NO" if seen[digest] == 4 else "OK")

    _runner(tmp_path / "root", artifacts, materials, transport).execute_all()
    assert sum(seen.values()) == 96
    assert verify(tmp_path / "root", allow_test_fixture=True)["terminal"] == TEST_FALSIFIED


def test_invalid_envelope_consumes_once_and_is_inconclusive(tmp_path: Path) -> None:
    artifacts, materials = _bundle()
    count = 0

    def transport(_: str, request: bytes, __: int) -> LiveObservation:
        nonlocal count
        count += 1
        if count == 1:
            return LiveObservation(200, b'{"model":"wrong"}', "application/json")
        return _response(request)

    _runner(tmp_path / "root", artifacts, materials, transport).execute_all()
    assert count == 96
    assert verify(tmp_path / "root", allow_test_fixture=True)["terminal"] == TEST_INCONCLUSIVE


def test_transport_failure_halts_without_retry(tmp_path: Path) -> None:
    artifacts, materials = _bundle()
    count = 0

    def transport(_: str, request: bytes, __: int) -> LiveObservation:
        nonlocal count
        count += 1
        if count == 3:
            raise OSError("closed")
        return _response(request)

    rows = _runner(tmp_path / "root", artifacts, materials, transport).execute_all()
    assert len(rows) == 3
    assert count == 3
    assert verify(tmp_path / "root", allow_test_fixture=True)["terminal"] == TEST_INCONCLUSIVE


def test_post_boundary_failure_keeps_raw_envelope_then_halts(tmp_path: Path) -> None:
    artifacts, materials = _bundle()
    plan_raw = artifacts["plan.json"]
    runtime = parse_canonical(_identities(artifacts)["runtime_identity_sha256"])

    def attester(phase: str, attempt: str | None, completed: int) -> bytes:
        if phase == "POST" and completed == 1:
            raise RuntimeError("boundary lost")
        return _attestation(plan_raw, runtime, phase, attempt, completed)

    rows = _runner(
        tmp_path / "root", artifacts, materials, lambda _, request, __: _response(request),
        attester=attester,
    ).execute_all()
    assert len(rows) == 1
    assert rows[0]["raw_envelope"] is not None
    assert rows[0]["post_boundary_attestation"] is None
    assert verify(tmp_path / "root", allow_test_fixture=True)["terminal"] == TEST_INCONCLUSIVE


def test_runner_halts_before_post_when_dynamic_nlockmgr_pair_changes(tmp_path: Path) -> None:
    artifacts, materials = _bundle()
    plan_raw = artifacts["plan.json"]
    runtime = parse_canonical(_identities(artifacts)["runtime_identity_sha256"])
    calls = 0

    def attester(phase: str, attempt: str | None, completed: int) -> bytes:
        raw = _attestation(plan_raw, runtime, phase, attempt, completed)
        if phase != "PRE":
            return raw
        receipt = parse_canonical(raw)
        registrations = _dynamic_registrations(40000, 40001)
        listeners = dynamic_kernel_rpc_tcp_listeners(registrations)
        receipt["dynamic_kernel_rpc_registrations"] = registrations
        receipt["dynamic_kernel_rpc_registrations_sha256"] = canonical_sha256(registrations)
        receipt["dynamic_kernel_rpc_tcp_listeners"] = list(listeners)
        receipt["host_listener_inventory_sha256"] = listener_inventory_sha256(
            sorted(
                [
                    "127.0.0.1:22",
                    "127.0.0.54%lo:53",
                    "[::1]:22",
                    "[fd00::1]:443",
                    *listeners,
                    "127.0.0.1:18080",
                ]
            )
        )
        host_rows = sorted(
            f"LISTEN 0 4096 {endpoint} 0.0.0.0:*"
            for endpoint in [
                "127.0.0.1:22",
                "127.0.0.54%lo:53",
                "[::1]:22",
                "[fd00::1]:443",
                *listeners,
                "127.0.0.1:18080",
            ]
        )
        receipt["host_tcp_listener_rows"] = host_rows
        receipt["host_tcp_listener_rows_sha256"] = canonical_sha256(host_rows)
        return canonical_bytes(receipt)

    def transport(_: str, request: bytes, __: int) -> LiveObservation:
        nonlocal calls
        calls += 1
        return _response(request)

    assert _runner(tmp_path / "root", artifacts, materials, transport, attester=attester).execute_all() == ()
    assert calls == 0


def test_independent_verifier_refuses_ledger_mutation(tmp_path: Path) -> None:
    artifacts, materials = _bundle()
    root = tmp_path / "root"
    _runner(root, artifacts, materials, lambda _, request, __: _response(request)).execute_all()
    raw = (root / "q1_live_ledger.jsonl").read_bytes()
    (root / "q1_live_ledger.jsonl").write_bytes(raw.replace(b"QCASE-001", b"QCASE-999", 1))
    assert verify(root)["terminal"] == VOID


def test_external_consumption_witness_requires_exact_regular_marker(tmp_path: Path) -> None:
    registry = tmp_path / "registry"
    registry.mkdir()
    plan_sha256 = "a" * 64
    copied = canonical_bytes({"consumption": "fixture"})
    marker = registry / f"{plan_sha256}.consumed"

    assert not _external_consumption_witness(None, str(registry), plan_sha256, copied)
    marker.write_bytes(b"different")
    assert not _external_consumption_witness(registry, str(registry), plan_sha256, copied)
    marker.write_bytes(copied)
    assert _external_consumption_witness(registry, str(registry), plan_sha256, copied)
    other_registry = tmp_path / "other-registry"
    other_registry.mkdir()
    assert not _external_consumption_witness(
        other_registry, str(registry), plan_sha256, copied
    )
    marker.unlink()
    marker.symlink_to(tmp_path / "elsewhere")
    assert not _external_consumption_witness(registry, str(registry), plan_sha256, copied)


def test_plan_is_burned_before_start_and_cannot_be_reused(tmp_path: Path) -> None:
    artifacts, materials = _bundle()
    registry = tmp_path / "registry"; registry.mkdir()
    (tmp_path / "one").mkdir(); (tmp_path / "two").mkdir()
    first = _runner(tmp_path / "one" / "evidence", artifacts, materials, lambda _, request, __: _response(request))
    # Move the burn into one fixed operator registry, then demonstrate a
    # different evidence-root parent cannot make the frozen plan reusable.
    first.consumption_root = registry
    first.execute_all()
    second = _runner(tmp_path / "two" / "evidence", artifacts, materials, lambda _, request, __: _response(request))
    second.consumption_root = registry
    with pytest.raises(LiveQ1Refusal, match="already consumed"):
        second.execute_all()


def test_injected_boundary_requires_explicit_fixture_mode(tmp_path: Path) -> None:
    artifacts, materials = _bundle()
    plan = artifacts["plan.json"]
    registry = tmp_path / "registry"; registry.mkdir()
    with pytest.raises(LiveQ1Refusal, match="explicit fixture mode"):
        LiveQ1Runner(tmp_path / "root", plan, artifacts["start_marker.json"], artifacts["corpus_manifest.json"], materials, _identities(artifacts), _provenance(artifacts), artifacts["root_genesis.json"], artifacts["closure_manifest.json"], b"fake", lambda *_: b"fake", consumption_root=registry)
