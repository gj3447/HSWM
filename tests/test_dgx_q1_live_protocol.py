from pathlib import Path
from hashlib import sha256

import pytest

from _research.dnrd5.canonical_json import canonical_bytes
from _research.dgx_q1.independent_live_verifier import VOID, verify
from _research.dgx_q1.live_protocol import (
    LiveQ1Refusal,
    loopback_q1_target,
    validate_declared_isolation_contract,
)


def test_independent_verifier_closes_missing_or_malformed_roots_to_void(tmp_path: Path) -> None:
    assert verify(tmp_path / "missing")["terminal"] == VOID
    root = tmp_path / "malformed"
    root.mkdir()
    (root / "content").mkdir()
    (root / "q1_live_ledger.jsonl").write_bytes(b"not-json\n")
    assert verify(root)["terminal"] == VOID


def test_declared_isolation_v2_freezes_a_validated_listener_baseline() -> None:
    allowlist = ["127.0.0.54%lo:53", "[::1]:22", "[fd00::1]:443"]
    raw = canonical_bytes(
        {
            "schema_version": "hswm-dgx-q1-declared-isolation/v2",
            "batch_invariant": True,
            "boundary": "FINITE_DECLARED_CONTROL_CONTRACT_NOT_OBSERVED_PROOF",
            "dedicated_gpu": True,
            "dedicated_node": True,
            "dedicated_process": True,
            "max_num_seqs": 1,
            "network_scope": "LOOPBACK_INGRESS_ONLY_OUTBOUND_NOT_ATTESTED",
            "other_inference_processes": 0,
            "prefix_cache": False,
            "v1_multiprocessing": False,
            "host_listener_allowlist": allowlist,
            "host_listener_allowlist_sha256": sha256("\n".join(allowlist).encode()).hexdigest(),
            "host_listener_policy": (
                "EXACT_FROZEN_STATIC_PLUS_RPCBOUND_DYNAMIC_NLOCKMGR_PLUS_ONE_Q1_TARGET"
            ),
            "dynamic_kernel_rpc_listener_policy": {
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
            },
        }
    )
    assert validate_declared_isolation_contract(
        raw, target="127.0.0.1:18080"
    )["host_listener_allowlist"] == allowlist

    invalid = raw.replace(b"[::1]:22", b"127.0.0.1:11434")
    with pytest.raises(LiveQ1Refusal):
        validate_declared_isolation_contract(invalid, target="127.0.0.1:18080")


@pytest.mark.parametrize(
    "endpoint",
    (
        "http://127.0.0.1:018080/v1/chat/completions",
        "http://127.0.0.1:18080/v1/chat/completions/",
        "http://127.0.0.1:65536/v1/chat/completions",
    ),
)
def test_loopback_target_requires_one_canonical_url_spelling(endpoint: str) -> None:
    with pytest.raises(LiveQ1Refusal):
        loopback_q1_target(endpoint)
