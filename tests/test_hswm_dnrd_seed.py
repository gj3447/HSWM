from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = REPO_ROOT / "_research" / "dnrd" / "seed.py"
_SPEC = importlib.util.spec_from_file_location("hswm_dnrd_seed", SEED_PATH)
assert _SPEC is not None and _SPEC.loader is not None
seed = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = seed
_SPEC.loader.exec_module(seed)


SOURCE_FREEZE = 1_700_000_000
PREREGISTRATION_CI_COMPLETED = 1_700_000_001
HELPER_PIN = "3" * 64
LOCK_PIN = "4" * 64
BUNDLE_PIN = "5" * 64
NODE_PIN = "9" * 64
NODE_VERSION = "v24.test"


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def _source_binding() -> object:
    return seed.SourceFreezeBinding(
        source_commit="a" * 40,
        source_tree_oid="b" * 40,
        source_manifest_sha256="c" * 64,
        preregistration_commit="d" * 40,
        preregistration_tree_oid="e" * 40,
        preregistration_blob_sha256="e" * 64,
        preregistration_ci_completed_unix=PREREGISTRATION_CI_COMPLETED,
        preregistration_ci_receipt_sha256="f" * 64,
    )


def _verifier_receipt_value(*, round_number: int | None = None) -> dict[str, object]:
    selected_round = round_number or seed.first_eligible_quicknet_round(
        source_freeze_unix=SOURCE_FREEZE,
        preregistration_ci_completed_unix=PREREGISTRATION_CI_COMPLETED,
    )
    signature = "ab" * 48
    randomness = sha256(bytes.fromhex(signature)).hexdigest()
    pulse = {
        "randomness": randomness,
        "round": selected_round,
        "round_time_unix": seed.quicknet_round_time_unix(selected_round),
        "signature": signature,
    }
    unsigned: dict[str, object] = {
        "chain": {
            "beacon_id": "quicknet",
            "genesis_time": seed.QUICKNET_GENESIS_TIME_UNIX,
            "group_hash": seed.QUICKNET_GROUP_HASH,
            "hash": seed.QUICKNET_CHAIN_HASH,
            "period": seed.QUICKNET_PERIOD_SECONDS,
            "public_key": seed.QUICKNET_PUBLIC_KEY,
            "scheme_id": seed.QUICKNET_SIGNATURE_SCHEME,
        },
        "chronology_claim_allowed": False,
        "helper_version": "hswm-swm0w-drand-node-verifier/v1",
        "input_fixture_sha256": None,
        "mode": "online",
        "pulse": pulse,
        "pulse_source_url": f"https://api.drand.sh/{seed.QUICKNET_CHAIN_HASH}/public/{selected_round}",
        "schema_version": "hswm-swm0w-drand-verification-receipt/v1",
        "verification": {
            "accepted_beacon_sha256": sha256(
                _canonical({key: pulse[key] for key in ("randomness", "round", "signature")})
            ).hexdigest(),
            "accepted_by": "drand-client.fetchBeacon",
            "network_policy": "ONLINE_EXPLICIT",
            "randomness_derivation": "SHA256(raw_signature_bytes)",
            "signature_scheme": "bls-unchained-g1-rfc9380",
        },
        "verified_at_unix": pulse["round_time_unix"],
        "verifier": {
            "git_commit": "6" * 40,
            "git_tag_url": "https://example.invalid/drand-client",
            "helper_sha256": HELPER_PIN,
            "npm_integrity": "sha512-test",
            "npm_shasum": "7" * 40,
            "package": "drand-client",
            "package_json_sha256": "8" * 64,
            "package_lock_sha256": LOCK_PIN,
            "runtime_bundle_sha256": BUNDLE_PIN,
            "runtime_engine": "Node.js",
            "runtime_exec_sha256": NODE_PIN,
            "runtime_trust_status": "TRUSTED_LOCAL_OS_AND_NODE_RUNTIME_REQUIRED",
            "runtime_version": NODE_VERSION,
            "source_tarball": "https://example.invalid/drand-client.tgz",
            "version": "1.4.2",
        },
    }
    return {**unsigned, "receipt_sha256": sha256(_canonical(unsigned)).hexdigest()}


def _verifier_receipt_bytes(*, round_number: int | None = None) -> bytes:
    return _canonical(_verifier_receipt_value(round_number=round_number)) + b"\n"


def _resigned_verifier_receipt(mutator) -> bytes:
    value = deepcopy(_verifier_receipt_value())
    mutator(value)
    unsigned = {key: item for key, item in value.items() if key != "receipt_sha256"}
    value["receipt_sha256"] = sha256(_canonical(unsigned)).hexdigest()
    return _canonical(value) + b"\n"


def _parse_verifier(receipt_bytes: bytes) -> object:
    return seed.projection_from_verifier_receipt_bytes(
        receipt_bytes,
        expected_helper_sha256=HELPER_PIN,
        expected_package_lock_sha256=LOCK_PIN,
        expected_runtime_bundle_sha256=BUNDLE_PIN,
        expected_runtime_exec_sha256=NODE_PIN,
        expected_runtime_version=NODE_VERSION,
    )


def _projection(*, round_number: int | None = None) -> object:
    return _parse_verifier(_verifier_receipt_bytes(round_number=round_number))


def _receipt() -> object:
    return seed.bind_future_pulse(
        source_freeze_unix=SOURCE_FREEZE,
        preregistration_ci_completed_unix=PREREGISTRATION_CI_COMPLETED,
        projection=_projection(),
        source_binding=_source_binding(),
    )


def test_first_eligible_round_is_minimal_and_has_exact_lead() -> None:
    round_number = seed.first_eligible_quicknet_round(
        source_freeze_unix=SOURCE_FREEZE,
        preregistration_ci_completed_unix=PREREGISTRATION_CI_COMPLETED,
    )
    threshold = max(SOURCE_FREEZE, PREREGISTRATION_CI_COMPLETED) + 900
    assert seed.quicknet_round_time_unix(round_number) >= threshold
    if round_number > 1:
        assert seed.quicknet_round_time_unix(round_number - 1) < threshold


def test_binding_is_deterministic_content_addressed_and_32_bytes() -> None:
    first = _receipt()
    second = _receipt()
    assert first == second
    assert len(first.seed_hex) == 64
    assert len(bytes.fromhex(first.seed_hex)) == 32
    assert first.seed_hex == seed.derive_seed_hex(
        projection=_projection(), source_binding=_source_binding()
    )
    canonical = first.canonical()
    assert canonical["receipt_sha256"] == first.receipt_sha256
    material = seed.seed_material(projection=_projection(), source_binding=_source_binding())
    assert material["domain"] == "HSWM-DNRD-4S1-FUTURE-SEED-V1"
    assert material["experiment_id"] == "HSWM-DNRD-4S1"
    assert material["schema_version"] == "hswm-dnrd4s1-future-seed-material/v1"
    assert first.schema_version == "hswm-dnrd4s1-pulse-binding/v1"
    assert set(material) == {"domain", "experiment_id", "schema_version", "source_commit", "preregistration_commit", "quicknet_chain_hash", "quicknet_round", "quicknet_randomness_hex"}
    assert set(canonical) == {
        "minimum_eligible_time_unix",
        "preregistration_ci_completed_unix",
        "projection",
        "receipt_sha256",
        "schema_version",
        "seed_hex",
        "source_binding",
        "source_freeze_unix",
    }
    assert set(canonical["source_binding"]) == {
        "experiment_id",
        "preregistration_blob_sha256",
        "preregistration_ci_completed_unix",
        "preregistration_ci_receipt_sha256",
        "preregistration_commit",
        "preregistration_tree_oid",
        "source_commit",
        "source_manifest_sha256",
        "source_tree_oid",
    }
    assert "ratification" not in json.dumps(canonical).casefold()


@pytest.mark.parametrize(
    "projection",
    [
        lambda: replace(_projection(), chain_hash="0" * 64),
        lambda: replace(_projection(), randomness_hex="A" * 64),
        lambda: replace(_projection(), randomness_hex="1" * 62),
        lambda: replace(_projection(), verification_succeeded=False),
        lambda: replace(_projection(), verification_receipt_sha256="z" * 64),
        lambda: replace(_projection(), round_time_unix=_projection().round_time_unix + 1),
    ],
)
def test_tampered_verified_projection_is_rejected(projection) -> None:
    with pytest.raises(seed.DNRDSeedBindingError):
        seed.bind_future_pulse(
            source_freeze_unix=SOURCE_FREEZE,
            preregistration_ci_completed_unix=PREREGISTRATION_CI_COMPLETED,
            projection=projection(),
            source_binding=_source_binding(),
        )


def test_early_or_nonfirst_round_is_rejected() -> None:
    expected = _projection().round
    with pytest.raises(seed.DNRDSeedBindingError, match="early or not the first eligible"):
        seed.bind_future_pulse(
            source_freeze_unix=SOURCE_FREEZE,
            preregistration_ci_completed_unix=PREREGISTRATION_CI_COMPLETED,
            projection=_projection(round_number=expected - 1),
            source_binding=_source_binding(),
        )
    with pytest.raises(seed.DNRDSeedBindingError, match="early or not the first eligible"):
        seed.bind_future_pulse(
            source_freeze_unix=SOURCE_FREEZE,
            preregistration_ci_completed_unix=PREREGISTRATION_CI_COMPLETED,
            projection=_projection(round_number=expected + 1),
            source_binding=_source_binding(),
        )


def test_chronology_tamper_rejects_precomputed_round() -> None:
    with pytest.raises(seed.DNRDSeedBindingError, match="early or not the first eligible"):
        seed.bind_future_pulse(
            source_freeze_unix=SOURCE_FREEZE + 3_000,
            preregistration_ci_completed_unix=PREREGISTRATION_CI_COMPLETED,
            projection=_projection(),
            source_binding=_source_binding(),
        )


def test_source_or_preregistration_binding_tamper_is_rejected() -> None:
    with pytest.raises(seed.DNRDSeedBindingError):
        seed.derive_seed_hex(
            projection=_projection(),
            source_binding=replace(_source_binding(), source_commit="A" * 40),
        )
    with pytest.raises(seed.DNRDSeedBindingError):
        seed.derive_seed_hex(
            projection=_projection(),
            source_binding=replace(_source_binding(), preregistration_blob_sha256="f" * 63),
        )
    with pytest.raises(seed.DNRDSeedBindingError):
        seed.derive_seed_hex(
            projection=_projection(),
            source_binding=replace(_source_binding(), experiment_id="HSWM-DNRD-4"),
        )
    with pytest.raises(seed.DNRDSeedBindingError):
        seed.derive_seed_hex(
            projection=_projection(),
            source_binding=replace(
                _source_binding(), preregistration_ci_completed_unix=True
            ),
        )
    assert seed.derive_seed_hex(
        projection=_projection(), source_binding=_source_binding()
    ) == seed.derive_seed_hex(
        projection=_projection(),
        source_binding=replace(
            _source_binding(), preregistration_tree_oid="0" * 40
        ),
    )
    assert seed.derive_seed_hex(
        projection=_projection(), source_binding=_source_binding()
    ) == seed.derive_seed_hex(
        projection=_projection(),
        source_binding=replace(
            _source_binding(), preregistration_ci_receipt_sha256="0" * 64
        ),
    )
    assert seed.derive_seed_hex(
        projection=_projection(), source_binding=_source_binding()
    ) == seed.derive_seed_hex(
        projection=_projection(),
        source_binding=replace(
            _source_binding(),
            preregistration_ci_completed_unix=PREREGISTRATION_CI_COMPLETED + 1,
        ),
    )


def test_seed_v5_excludes_raw_carriers_but_changes_for_immutable_preimage() -> None:
    baseline = seed.derive_seed_hex(projection=_projection(), source_binding=_source_binding())
    assert baseline == seed.derive_seed_hex(
        projection=replace(_projection(), verification_receipt_sha256="0" * 64),
        source_binding=_source_binding(),
    )
    assert baseline == seed.derive_seed_hex(
        projection=_projection(),
        source_binding=replace(_source_binding(), preregistration_ci_receipt_sha256="0" * 64),
    )
    assert baseline != seed.derive_seed_hex(projection=_projection(), source_binding=replace(_source_binding(), source_commit="0" * 40))
    assert baseline != seed.derive_seed_hex(projection=_projection(), source_binding=replace(_source_binding(), preregistration_commit="0" * 40))
    assert baseline != seed.derive_seed_hex(projection=replace(_projection(), randomness_hex="0" * 64), source_binding=_source_binding())


def test_content_addressed_receipt_rejects_tamper() -> None:
    receipt = _receipt()
    with pytest.raises(seed.DNRDSeedBindingError, match="seed does not match"):
        replace(receipt, seed_hex="3" * 64).validate()
    with pytest.raises(seed.DNRDSeedBindingError, match="receipt SHA-256"):
        replace(receipt, receipt_sha256="4" * 64).validate()


def test_bool_is_not_a_valid_chronology_integer() -> None:
    with pytest.raises(seed.DNRDSeedBindingError):
        seed.first_eligible_quicknet_round(
            source_freeze_unix=True,
            preregistration_ci_completed_unix=PREREGISTRATION_CI_COMPLETED,
        )


def test_ci_completion_must_be_positive_and_match_the_source_binding() -> None:
    with pytest.raises(seed.DNRDSeedBindingError, match="must be positive"):
        seed.first_eligible_quicknet_round(
            source_freeze_unix=SOURCE_FREEZE,
            preregistration_ci_completed_unix=0,
        )
    with pytest.raises(seed.DNRDSeedBindingError, match="CI completion time differs"):
        seed.bind_future_pulse(
            source_freeze_unix=SOURCE_FREEZE,
            preregistration_ci_completed_unix=PREREGISTRATION_CI_COMPLETED + 1,
            projection=_projection(),
            source_binding=_source_binding(),
        )


def test_only_the_strict_verifier_parser_can_create_a_usable_projection() -> None:
    receipt_bytes = _verifier_receipt_bytes()
    projection = _parse_verifier(receipt_bytes)
    assert projection.verification_receipt_sha256 == sha256(receipt_bytes).hexdigest()
    with pytest.raises(seed.DNRDSeedBindingError, match="must be created"):
        seed.VerifiedQuicknetProjection(
            chain_hash=seed.QUICKNET_CHAIN_HASH,
            round=projection.round,
            round_time_unix=projection.round_time_unix,
            randomness_hex=projection.randomness_hex,
            verification_succeeded=True,
            verification_receipt_sha256=projection.verification_receipt_sha256,
        ).validate()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["chain"].__setitem__("beacon_id", "other"),
        lambda value: value["chain"].__setitem__("genesis_time", 0),
        lambda value: value["chain"].__setitem__("period", 4),
        lambda value: value["chain"].__setitem__("hash", "0" * 64),
        lambda value: value["chain"].__setitem__("group_hash", "0" * 64),
        lambda value: value["chain"].__setitem__("public_key", "0" * 192),
        lambda value: value["chain"].__setitem__("scheme_id", "other-scheme"),
        lambda value: value["pulse"].__setitem__("round_time_unix", 0),
        lambda value: value["pulse"].__setitem__("randomness", "0" * 64),
        lambda value: value["pulse"].__setitem__("signature", "cd" * 48),
        lambda value: value["verification"].__setitem__("accepted_beacon_sha256", "0" * 64),
        lambda value: value["verification"].__setitem__("accepted_by", "self"),
        lambda value: value["verification"].__setitem__("randomness_derivation", "other"),
        lambda value: value["verification"].__setitem__("signature_scheme", "other"),
        lambda value: value["verification"].__setitem__("network_policy", "OFFLINE_INJECTED_CLIENT_FETCH_GUARD"),
        lambda value: value.__setitem__("mode", "offline"),
        lambda value: value["verifier"].__setitem__("helper_sha256", "0" * 64),
        lambda value: value["verifier"].__setitem__("package_lock_sha256", "0" * 64),
        lambda value: value["verifier"].__setitem__("runtime_bundle_sha256", "0" * 64),
        lambda value: value["verifier"].__setitem__("runtime_exec_sha256", "0" * 64),
        lambda value: value["verifier"].__setitem__("runtime_version", "v0.attacker"),
        lambda value: value["verifier"].__setitem__("runtime_engine", "Python"),
        lambda value: value.__setitem__("chronology_claim_allowed", True),
        lambda value: value.__setitem__("pulse_source_url", "https://wrong.invalid"),
    ],
)
def test_critical_verifier_receipt_tampering_is_rejected_even_if_self_rehashed(mutate) -> None:
    with pytest.raises(seed.DNRDSeedBindingError):
        _parse_verifier(_resigned_verifier_receipt(mutate))


def test_verifier_receipt_self_hash_duplicate_nonfinite_and_utf8_tampering_are_rejected() -> None:
    unsigned = _verifier_receipt_value()
    unsigned["receipt_sha256"] = "0" * 64
    with pytest.raises(seed.DNRDSeedBindingError, match="self-hash"):
        _parse_verifier(_canonical(unsigned) + b"\n")
    with pytest.raises(seed.DNRDSeedBindingError, match="repeats JSON key"):
        _parse_verifier(b'{"chain":{},"chain":{}}\n')
    with pytest.raises(seed.DNRDSeedBindingError, match="forbidden JSON constant"):
        _parse_verifier(b"NaN\n")
    with pytest.raises(seed.DNRDSeedBindingError, match="UTF-8"):
        _parse_verifier(b"\xff\n")


def test_caller_supplied_verifier_pins_are_required() -> None:
    receipt = _verifier_receipt_bytes()
    with pytest.raises(seed.DNRDSeedBindingError, match="helper SHA pin"):
        seed.projection_from_verifier_receipt_bytes(
            receipt,
            expected_helper_sha256="0" * 64,
            expected_package_lock_sha256=LOCK_PIN,
            expected_runtime_bundle_sha256=BUNDLE_PIN,
            expected_runtime_exec_sha256=NODE_PIN,
            expected_runtime_version=NODE_VERSION,
        )
    with pytest.raises(seed.DNRDSeedBindingError, match="package-lock SHA pin"):
        seed.projection_from_verifier_receipt_bytes(
            receipt,
            expected_helper_sha256=HELPER_PIN,
            expected_package_lock_sha256="0" * 64,
            expected_runtime_bundle_sha256=BUNDLE_PIN,
            expected_runtime_exec_sha256=NODE_PIN,
            expected_runtime_version=NODE_VERSION,
        )
    with pytest.raises(seed.DNRDSeedBindingError, match="runtime-bundle SHA pin"):
        seed.projection_from_verifier_receipt_bytes(
            receipt,
            expected_helper_sha256=HELPER_PIN,
            expected_package_lock_sha256=LOCK_PIN,
            expected_runtime_bundle_sha256="0" * 64,
            expected_runtime_exec_sha256=NODE_PIN,
            expected_runtime_version=NODE_VERSION,
        )
    with pytest.raises(seed.DNRDSeedBindingError, match="Node executable SHA pin"):
        seed.projection_from_verifier_receipt_bytes(
            receipt,
            expected_helper_sha256=HELPER_PIN,
            expected_package_lock_sha256=LOCK_PIN,
            expected_runtime_bundle_sha256=BUNDLE_PIN,
            expected_runtime_exec_sha256="0" * 64,
            expected_runtime_version=NODE_VERSION,
        )
    with pytest.raises(seed.DNRDSeedBindingError, match="Node version pin"):
        seed.projection_from_verifier_receipt_bytes(
            receipt,
            expected_helper_sha256=HELPER_PIN,
            expected_package_lock_sha256=LOCK_PIN,
            expected_runtime_bundle_sha256=BUNDLE_PIN,
            expected_runtime_exec_sha256=NODE_PIN,
            expected_runtime_version="v0.wrong",
        )
