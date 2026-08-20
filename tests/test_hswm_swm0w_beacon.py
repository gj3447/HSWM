from __future__ import annotations

from copy import deepcopy
import ast
from hashlib import sha256
import json
from pathlib import Path

import pytest

from hswm.experiments import swm0w_beacon as beacon


ROUND = 1000
ROUND_TIME = 1_692_806_364
REGISTRATION_SHA256 = "1" * 64
EXPECTED_RANDOMNESS = (
    "fe290beca10872ef2fb164d2aa4442de4566183ec51c56ff3cd603d930e54fdd"
)
EXPECTED_SIGNATURE = (
    "b44679b9a59af2ec876b1a6b1ad52ea9b1615fc3982b19576350f93447cb1125"
    "e342b73a8dd2bacbe47e4b6b63ed5e39"
)


def commitment(*, experiment_id: str = "swm0w-offline-vector-test"):
    return beacon.make_future_round_commitment(
        experiment_id=experiment_id,
        registration_evidence_sha256=REGISTRATION_SHA256,
        registered_at_unix=ROUND_TIME - 1,
        round_number=ROUND,
    )


@pytest.fixture(scope="module")
def verified_bundle():
    if not beacon.verifier_dependency_available():
        pytest.skip(
            "offline BLS integration requires `npm ci --ignore-scripts` in "
            "tools/swm0w_drand"
        )
    selected = commitment()
    receipt, binding = beacon.verify_and_bind_offline(selected)
    return selected, receipt, binding


def _rehash_receipt(value: dict) -> dict:
    unsigned = {key: item for key, item in value.items() if key != "receipt_sha256"}
    value["receipt_sha256"] = beacon.canonical_sha256(unsigned)
    return value


def _rehash_commitment(value: dict) -> dict:
    unsigned = {
        key: item for key, item in value.items() if key != "commitment_sha256"
    }
    value["commitment_sha256"] = beacon.canonical_sha256(unsigned)
    return value


def test_quicknet_constants_and_round_time_are_exact() -> None:
    assert beacon.QUICKNET_CHAIN_HASH == (
        "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971"
    )
    assert beacon.QUICKNET_GENESIS_TIME == 1_692_803_367
    assert beacon.QUICKNET_PERIOD_SECONDS == 3
    assert beacon.QUICKNET_SCHEME_ID == "bls-unchained-g1-rfc9380"
    assert len(bytes.fromhex(beacon.QUICKNET_PUBLIC_KEY)) == 96
    assert beacon.quicknet_round_time(1) == beacon.QUICKNET_GENESIS_TIME
    assert beacon.quicknet_round_time(ROUND) == ROUND_TIME
    assert beacon.first_quicknet_round_strictly_after(ROUND_TIME) == ROUND + 1
    assert beacon.first_quicknet_round_strictly_after(ROUND_TIME - 1) == ROUND
    with pytest.raises(beacon.SWM0WBeaconError, match="must be an integer"):
        beacon.quicknet_round_time(beacon.MAX_QUICKNET_ROUND + 1)


def test_canonical_json_rejects_ambiguous_non_string_object_keys() -> None:
    with pytest.raises(beacon.SWM0WBeaconError, match="keys must be strings"):
        beacon.canonical_json({1: "integer key"})


def test_commitment_requires_a_strict_future_round_and_denies_chronology_claim() -> None:
    selected = commitment()
    assert selected.round_time_unix > selected.registered_at_unix
    assert selected.chronology_claim_allowed is False
    assert selected.commitment_sha256 == beacon.canonical_sha256(selected.unsigned())
    assert beacon.parse_future_round_commitment(selected.canonical()) == selected

    with pytest.raises(beacon.SWM0WBeaconError, match="strictly after"):
        beacon.make_future_round_commitment(
            experiment_id="not-future",
            registration_evidence_sha256=REGISTRATION_SHA256,
            registered_at_unix=ROUND_TIME,
            round_number=ROUND,
        )


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    (
        ("round_time_unix", ROUND_TIME + 1, "round/time"),
        ("chain_hash", "2" * 64, "pinned Quicknet"),
        ("chronology_claim_allowed", True, "cannot claim chronology"),
    ),
)
def test_commitment_rejects_semantic_tampering(
    field: str, replacement, message: str
) -> None:
    value = commitment().canonical()
    value[field] = replacement
    _rehash_commitment(value)
    with pytest.raises(beacon.SWM0WBeaconError, match=message):
        beacon.parse_future_round_commitment(value)


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    (
        ("registered_at_unix", float(ROUND_TIME - 1), "must be an integer"),
        ("round", float(ROUND), "must be an integer"),
        ("round_time_unix", float(ROUND_TIME), "must be an integer"),
        ("task_count", float(beacon.TASK_COUNT), "must be an integer"),
        ("chronology_claim_allowed", 0, "cannot claim chronology"),
    ),
)
def test_commitment_rejects_rehashed_json_type_aliases(
    field: str, replacement, message: str
) -> None:
    value = commitment().canonical()
    value[field] = replacement
    _rehash_commitment(value)
    with pytest.raises(beacon.SWM0WBeaconError, match=message):
        beacon.parse_future_round_commitment(value)


def test_official_round_1000_fixture_is_frozen_and_self_consistent() -> None:
    fixture = json.loads(beacon.DEFAULT_OFFLINE_FIXTURE.read_text(encoding="utf-8"))
    assert fixture["chain_hash"] == beacon.QUICKNET_CHAIN_HASH
    assert fixture["source_url"] == f"{beacon.QUICKNET_BASE_URL}/public/{ROUND}"
    assert fixture["pulse"] == {
        "randomness": EXPECTED_RANDOMNESS,
        "round": ROUND,
        "signature": EXPECTED_SIGNATURE,
    }
    assert sha256(bytes.fromhex(EXPECTED_SIGNATURE)).hexdigest() == EXPECTED_RANDOMNESS


def test_package_lock_and_helper_pin_official_client_source_and_integrity() -> None:
    package_json = json.loads(
        (beacon._TOOL_ROOT / "package.json").read_text(encoding="utf-8")
    )
    lock = json.loads(beacon.DEFAULT_PACKAGE_LOCK.read_text(encoding="utf-8"))
    locked = lock["packages"]["node_modules/drand-client"]
    assert package_json["dependencies"] == {"drand-client": "1.4.2"}
    assert lock["lockfileVersion"] == 3
    assert locked == {
        **locked,
        "version": beacon.DRAND_CLIENT_VERSION,
        "resolved": beacon.DRAND_CLIENT_TARBALL,
        "integrity": beacon.DRAND_CLIENT_NPM_INTEGRITY,
    }
    assert beacon.file_sha256(beacon.DEFAULT_PACKAGE_LOCK) == (
        beacon.VERIFIER_PACKAGE_LOCK_SHA256
    )
    assert beacon.file_sha256(beacon.DEFAULT_NODE_HELPER) == (
        beacon.VERIFIER_HELPER_SHA256
    )
    assert beacon.DRAND_CLIENT_GIT_COMMIT == (
        "ef8c9260294f8699b5e8c27a6b764f8f0d768bea"
    )
    if beacon._INSTALLED_RUNTIME_BUNDLE.is_file():
        runtime = beacon._INSTALLED_RUNTIME_BUNDLE.read_text(encoding="utf-8")
        assert not runtime.startswith("import ")
        assert "\nimport " not in runtime
    assert beacon.VERIFIER_DISTRIBUTION_SCOPE == (
        "REPOSITORY_OR_SOURCE_CHECKOUT_ONLY"
    )


def test_helper_uses_public_cryptographic_client_path_and_offline_guard() -> None:
    source = beacon.DEFAULT_NODE_HELPER.read_text(encoding="utf-8")
    assert 'import { fetchBeacon, quicknetClient } from "drand-client"' in source
    assert "await fetchBeacon(offlineClient(fixture.pulse), expectedRound)" in source
    assert "offline verification forbids fetch" in source
    assert "disableBeaconVerification: false" in source
    assert "verifyBeacon" not in source.replace("verify-beacon", "")


def test_offline_official_vector_is_bls_verified_and_yields_twenty_seeds(
    verified_bundle,
) -> None:
    selected, receipt, binding = verified_bundle
    pulse = beacon.validate_verifier_receipt(receipt, selected)
    assert pulse.randomness == EXPECTED_RANDOMNESS
    assert pulse.signature == EXPECTED_SIGNATURE
    assert receipt["verification"]["accepted_by"] == "drand-client.fetchBeacon"
    assert receipt["verification"]["network_policy"] == (
        "OFFLINE_INJECTED_CLIENT_FETCH_GUARD"
    )
    assert receipt["chronology_claim_allowed"] is False
    assert receipt["verifier"]["runtime_engine"] == "Node.js"
    assert receipt["verifier"]["runtime_version"].startswith("v")
    assert receipt["verifier"]["runtime_trust_status"] == (
        beacon.RUNTIME_TRUST_STATUS
    )
    assert receipt["verifier"]["runtime_exec_sha256"] == beacon.file_sha256(
        Path(beacon.shutil.which("node")).resolve()
    )
    assert binding.chronology_claim_allowed is False
    assert binding.chronology_status == beacon.CHRONOLOGY_STATUS
    assert len(binding.task_seed_bytes()) == beacon.TASK_COUNT == 20
    assert all(len(value) == 32 for value in binding.task_seed_bytes())
    assert len(set(binding.task_seed_bytes())) == 20
    assert binding.task_seed_hex[0] == (
        "e4ad98e590af2360507e38d3740245ba8302aebaf71838f014cc888ac9370f65"
    )
    _, replay = beacon.verify_and_bind_offline(selected)
    assert replay.task_seed_hex == binding.task_seed_hex


def test_seed_derivation_is_domain_separated_by_commitment(verified_bundle) -> None:
    _, _, original = verified_bundle
    other_commitment = commitment(experiment_id="swm0w-other-task-family")
    _, other = beacon.verify_and_bind_offline(other_commitment)
    assert original.task_seed_hex != other.task_seed_hex
    assert original.randomness == other.randomness


def test_seed_binding_constructor_rejects_arbitrary_seed_material(
    verified_bundle,
) -> None:
    _, _, binding = verified_bundle
    with pytest.raises(beacon.SWM0WBeaconError, match="frozen derivation"):
        beacon.TaskSeedBindingV1(
            commitment_sha256=binding.commitment_sha256,
            verifier_receipt_sha256=binding.verifier_receipt_sha256,
            chain_hash=binding.chain_hash,
            round=binding.round,
            randomness=binding.randomness,
            seed_domain=binding.seed_domain,
            task_seed_hex=("0" * 64, *binding.task_seed_hex[1:]),
            chronology_status=binding.chronology_status,
            chronology_claim_allowed=False,
            binding_sha256=binding.binding_sha256,
        )


def test_seed_binding_is_not_accepted_without_exact_bundle_links(
    verified_bundle,
) -> None:
    selected, receipt, binding = verified_bundle
    assert (
        beacon.validate_task_seed_bundle_links(selected, receipt, binding) is binding
    )
    unsigned = binding.unsigned()
    unsigned["verifier_receipt_sha256"] = "2" * 64
    forged = beacon.TaskSeedBindingV1(
        commitment_sha256=binding.commitment_sha256,
        verifier_receipt_sha256=unsigned["verifier_receipt_sha256"],
        chain_hash=binding.chain_hash,
        round=binding.round,
        randomness=binding.randomness,
        seed_domain=binding.seed_domain,
        task_seed_hex=binding.task_seed_hex,
        chronology_status=binding.chronology_status,
        chronology_claim_allowed=False,
        binding_sha256=beacon.canonical_sha256(unsigned),
    )
    with pytest.raises(beacon.SWM0WBeaconError, match="seed binding diverge"):
        beacon.validate_task_seed_bundle_links(selected, receipt, forged)


def test_simple_boolean_or_http_receipt_is_not_cryptographic_proof() -> None:
    with pytest.raises(beacon.SWM0WBeaconError, match="frozen schema"):
        beacon.validate_verifier_receipt(
            {"http_ok": True, "signature_verified": True}, commitment()
        )


def test_receipt_rejects_rehashed_verifier_or_acceptance_forgery(
    verified_bundle,
) -> None:
    selected, receipt, _ = verified_bundle
    changed_version = deepcopy(receipt)
    changed_version["verifier"]["version"] = "1.4.3"
    _rehash_receipt(changed_version)
    with pytest.raises(beacon.SWM0WBeaconError, match="source/version/integrity"):
        beacon.validate_verifier_receipt(changed_version, selected)

    boolean_substitute = deepcopy(receipt)
    boolean_substitute["verification"] = {
        "accepted_beacon_sha256": receipt["verification"]["accepted_beacon_sha256"],
        "accepted_by": "HTTP 200 plus boolean",
        "network_policy": "OFFLINE_INJECTED_CLIENT_FETCH_GUARD",
        "randomness_derivation": "SHA256(raw_signature_bytes)",
        "signature_scheme": beacon.QUICKNET_SCHEME_ID,
    }
    _rehash_receipt(boolean_substitute)
    with pytest.raises(beacon.SWM0WBeaconError, match="cryptographic verifier"):
        beacon.validate_verifier_receipt(boolean_substitute, selected)


@pytest.mark.parametrize(
    ("path", "replacement", "message"),
    (
        (("pulse", "round"), float(ROUND), "pulse.round must be an integer"),
        (
            ("pulse", "round_time_unix"),
            float(ROUND_TIME),
            "pulse.round_time_unix must be an integer",
        ),
        (
            ("chain", "genesis_time"),
            float(beacon.QUICKNET_GENESIS_TIME),
            "Quicknet chain mismatch",
        ),
        (
            ("chain", "period"),
            float(beacon.QUICKNET_PERIOD_SECONDS),
            "Quicknet chain mismatch",
        ),
        (("chronology_claim_allowed",), 0, "cannot claim chronology"),
    ),
)
def test_verifier_receipt_rejects_rehashed_json_type_aliases(
    verified_bundle,
    path: tuple[str, ...],
    replacement,
    message: str,
) -> None:
    selected, receipt, _ = verified_bundle
    changed = deepcopy(receipt)
    target = changed
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement
    _rehash_receipt(changed)
    with pytest.raises(beacon.SWM0WBeaconError, match=message):
        beacon.validate_verifier_receipt(changed, selected)


def test_verifier_receipt_rejects_non_string_runtime_version_cleanly(
    verified_bundle,
) -> None:
    selected, receipt, _ = verified_bundle
    changed = deepcopy(receipt)
    changed["verifier"]["runtime_version"] = True
    _rehash_receipt(changed)
    with pytest.raises(beacon.SWM0WBeaconError, match="version must be a string"):
        beacon.validate_verifier_receipt(changed, selected)


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    (
        ("round", float(ROUND), "must be an integer"),
        ("chronology_claim_allowed", 0, "cannot claim chronology"),
    ),
)
def test_task_seed_binding_rejects_json_type_aliases(
    verified_bundle,
    field: str,
    replacement,
    message: str,
) -> None:
    _, _, binding = verified_bundle
    values = {
        "commitment_sha256": binding.commitment_sha256,
        "verifier_receipt_sha256": binding.verifier_receipt_sha256,
        "chain_hash": binding.chain_hash,
        "round": binding.round,
        "randomness": binding.randomness,
        "seed_domain": binding.seed_domain,
        "task_seed_hex": binding.task_seed_hex,
        "chronology_status": binding.chronology_status,
        "chronology_claim_allowed": binding.chronology_claim_allowed,
    }
    values[field] = replacement
    unsigned = {
        "chain_hash": values["chain_hash"],
        "chronology_claim_allowed": values["chronology_claim_allowed"],
        "chronology_status": values["chronology_status"],
        "commitment_sha256": values["commitment_sha256"],
        "randomness": values["randomness"],
        "round": values["round"],
        "schema_version": beacon.BINDING_SCHEMA,
        "seed_domain": values["seed_domain"],
        "task_seed_hex": list(values["task_seed_hex"]),
        "verifier_receipt_sha256": values["verifier_receipt_sha256"],
    }
    with pytest.raises(beacon.SWM0WBeaconError, match=message):
        beacon.TaskSeedBindingV1(
            **values,
            binding_sha256=beacon.canonical_sha256(unsigned),
        )


def test_task_seed_binding_requires_exact_seed_count(verified_bundle) -> None:
    _, _, binding = verified_bundle
    with pytest.raises(beacon.SWM0WBeaconError, match="exactly 20 task seeds"):
        beacon.TaskSeedBindingV1(
            commitment_sha256=binding.commitment_sha256,
            verifier_receipt_sha256=binding.verifier_receipt_sha256,
            chain_hash=binding.chain_hash,
            round=binding.round,
            randomness=binding.randomness,
            seed_domain=binding.seed_domain,
            task_seed_hex=binding.task_seed_hex[:-1],
            chronology_status=binding.chronology_status,
            chronology_claim_allowed=False,
            binding_sha256=binding.binding_sha256,
        )


def test_offline_client_rejects_bls_invalid_signature_even_with_matching_randomness(
    tmp_path: Path,
) -> None:
    if not beacon.verifier_dependency_available():
        pytest.skip("offline BLS integration requires the locked Node dependencies")
    fixture = json.loads(beacon.DEFAULT_OFFLINE_FIXTURE.read_text(encoding="utf-8"))
    signature = bytearray.fromhex(fixture["pulse"]["signature"])
    signature[-1] ^= 1
    fixture["pulse"]["signature"] = bytes(signature).hex()
    fixture["pulse"]["randomness"] = sha256(signature).hexdigest()
    path = tmp_path / "bls-invalid-pulse.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")
    with pytest.raises(beacon.SWM0WBeaconError, match="rejected pulse"):
        beacon.invoke_node_verifier(
            commitment(), mode="offline", pulse_file=path
        )


def test_exact_committed_round_is_required_by_node_verifier() -> None:
    if not beacon.verifier_dependency_available():
        pytest.skip("offline BLS integration requires the locked Node dependencies")
    next_time = beacon.quicknet_round_time(ROUND + 1)
    next_commitment = beacon.make_future_round_commitment(
        experiment_id="wrong-round-vector",
        registration_evidence_sha256=REGISTRATION_SHA256,
        registered_at_unix=next_time - 1,
        round_number=ROUND + 1,
    )
    with pytest.raises(beacon.SWM0WBeaconError, match="rejected pulse"):
        beacon.invoke_node_verifier(next_commitment, mode="offline")


def test_online_network_is_never_enabled_by_default() -> None:
    with pytest.raises(beacon.SWM0WBeaconError, match="allow_network=True"):
        beacon.invoke_node_verifier(commitment(), mode="online")
    with pytest.raises(beacon.SWM0WBeaconError, match="cannot enable network"):
        beacon.invoke_node_verifier(
            commitment(), mode="offline", allow_network=True
        )


@pytest.mark.parametrize("timeout", (True, "30", float("nan"), 0, -1))
def test_invalid_timeout_is_rejected_before_subprocess(timeout) -> None:
    with pytest.raises(beacon.SWM0WBeaconError, match="finite and positive"):
        beacon.invoke_node_verifier(commitment(), timeout_seconds=timeout)


def test_offline_fixture_must_be_a_bounded_regular_file(tmp_path: Path) -> None:
    with pytest.raises(beacon.SWM0WBeaconError, match="bounded regular file"):
        beacon.invoke_node_verifier(commitment(), pulse_file=tmp_path)
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b" " * (beacon.MAX_OFFLINE_FIXTURE_BYTES + 1))
    with pytest.raises(beacon.SWM0WBeaconError, match="bounded regular file"):
        beacon.invoke_node_verifier(commitment(), pulse_file=oversized)


def test_beacon_python_source_has_no_duplicate_literal_dict_keys() -> None:
    tree = ast.parse(Path(beacon.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys = [
            key.value
            for key in node.keys
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        ]
        assert len(keys) == len(set(keys)), f"duplicate dict key at line {node.lineno}"


def test_missing_node_runtime_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    if not beacon.verifier_dependency_available():
        pytest.skip("local dependency byte check requires the locked Node install")
    monkeypatch.setattr(beacon.shutil, "which", lambda _: None)
    with pytest.raises(beacon.SWM0WBeaconError, match="runtime is unavailable"):
        beacon.invoke_node_verifier(commitment(), mode="offline")
