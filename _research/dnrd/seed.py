"""DNRD-local future Quicknet seed binding.

This is deliberately a small, standard-library-only projection.  It accepts a
*previously cryptographically verified* Quicknet projection but does not fetch
or verify a beacon itself, select a retry, orchestrate a run, or import any
SWM0W/S2S machinery.

The public Quicknet chain identity, genesis timestamp, period, and round-time
formula below are copied with attribution from
``src/hswm/effect-runtime/src/s2s-quicknet.ts``.  No S2S type, seed format, or
workflow contract is reused.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any, Mapping


# Public Quicknet constants/formula attributed to s2s-quicknet.ts, as noted
# above.  They are frozen independently for the DNRD protocol.
QUICKNET_CHAIN_HASH = "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971"
QUICKNET_GENESIS_TIME_UNIX = 1_692_803_367
QUICKNET_PERIOD_SECONDS = 3
QUICKNET_BEACON_ID = "quicknet"
QUICKNET_GROUP_HASH = "f477d5c89f21a17c863a7f937c6a6d15859414d2be09cd448d4279af331c5d3e"
QUICKNET_PUBLIC_KEY = (
    "83cf0f2896adee7eb8b5f01fcad3912212c437e0073e911fb90022d3e760183c8"
    "c4b450b6a0a6c3ac6a5776a2d1064510d1fec758c921cc22b0e17e63aaf4bcb5"
    "ed66304de9cf809bd274ca73bab4af5a6e9c76a4bc09e76eae8991ef5ece45a"
)
QUICKNET_SIGNATURE_SCHEME = "bls-unchained-g1-rfc9380"
MAX_SAFE_INTEGER = (1 << 53) - 1
MAX_QUICKNET_ROUND = (
    (MAX_SAFE_INTEGER - QUICKNET_GENESIS_TIME_UNIX) // QUICKNET_PERIOD_SECONDS
) + 1

EXPERIMENT_ID = "HSWM-DNRD-2"
SEED_DOMAIN = "HSWM-DNRD-FUTURE-SEED-V2"
SEED_MATERIAL_SCHEMA = "hswm-dnrd-future-seed-material/v2"
PULSE_BINDING_SCHEMA = "hswm-dnrd-pulse-binding/v2"
VERIFIER_RECEIPT_SCHEMA = "hswm-swm0w-drand-verification-receipt/v1"
VERIFIER_HELPER_VERSION = "hswm-swm0w-drand-node-verifier/v1"
VERIFIER_ACCEPTED_BY = "drand-client.fetchBeacon"
VERIFIER_RANDOMNESS_DERIVATION = "SHA256(raw_signature_bytes)"
MINIMUM_LEAD_SECONDS = 900
_HEX = frozenset("0123456789abcdef")
_PARSER_ATTESTATION = object()


class DNRDSeedBindingError(ValueError):
    """A supplied chronology, projection, or binding is not DNRD-valid."""


def _nonempty_string(value: object, field: str) -> str:
    if type(value) is not str or not value:
        raise DNRDSeedBindingError(f"{field} must be a nonempty string")
    return value


def _hex(value: object, field: str, *, length: int) -> str:
    result = _nonempty_string(value, field)
    if len(result) != length or any(char not in _HEX for char in result):
        raise DNRDSeedBindingError(f"{field} must be exactly {length} lowercase hex characters")
    return result


def _unix_second(value: object, field: str) -> int:
    if type(value) is not int or not 0 <= value <= MAX_SAFE_INTEGER:
        raise DNRDSeedBindingError(f"{field} must be a safe nonnegative integer Unix second")
    return value


def _positive_round(value: object, field: str) -> int:
    if type(value) is not int or not 1 <= value <= MAX_QUICKNET_ROUND:
        raise DNRDSeedBindingError(f"{field} must be a valid positive Quicknet round")
    return value


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _exact_keys(value: object, expected: set[str], field: str) -> Mapping[str, Any]:
    if type(value) is not dict:
        raise DNRDSeedBindingError(f"{field} must be an object")
    actual = set(value)
    if actual != expected:
        raise DNRDSeedBindingError(
            f"{field} keys differ: missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )
    return value


def _strict_verifier_json_object(receipt_bytes: bytes) -> dict[str, Any]:
    if type(receipt_bytes) is not bytes:
        raise DNRDSeedBindingError("verifier receipt must be exact bytes")
    try:
        text = receipt_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise DNRDSeedBindingError("verifier receipt is not exact UTF-8") from error
    # verify-beacon.mjs emits canonical JSON followed by exactly one LF.
    if not text.endswith("\n") or text[:-1].endswith("\n"):
        raise DNRDSeedBindingError("verifier receipt must have exactly one terminal LF")
    encoded = text[:-1]

    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise DNRDSeedBindingError(f"verifier receipt repeats JSON key {key!r}")
            result[key] = value
        return result

    def no_nonfinite(value: str) -> None:
        raise DNRDSeedBindingError(f"verifier receipt contains forbidden JSON constant {value!r}")

    try:
        value = json.loads(
            encoded,
            object_pairs_hook=no_duplicates,
            parse_constant=no_nonfinite,
        )
    except (json.JSONDecodeError, DNRDSeedBindingError) as error:
        if isinstance(error, DNRDSeedBindingError):
            raise
        raise DNRDSeedBindingError("verifier receipt is not valid JSON") from error
    if type(value) is not dict:
        raise DNRDSeedBindingError("verifier receipt root must be an object")
    # This rejects a syntactically-valid but hand-formatted JSON carrier: the
    # actual helper emits exactly this canonical form (plus its terminal LF).
    if _canonical_bytes(value).decode("utf-8") != encoded:
        raise DNRDSeedBindingError("verifier receipt bytes are not the helper's canonical JSON form")
    return value


def quicknet_round_time_unix(round_number: int) -> int:
    """Return the exact Quicknet Unix second for a valid frozen round."""

    round_value = _positive_round(round_number, "round_number")
    return QUICKNET_GENESIS_TIME_UNIX + (round_value - 1) * QUICKNET_PERIOD_SECONDS


def first_eligible_quicknet_round(
    *, source_freeze_unix: int, user_ratification_unix: int
) -> int:
    """First round at least 900 seconds after both frozen chronology events."""

    source_time = _unix_second(source_freeze_unix, "source_freeze_unix")
    ratification_time = _unix_second(user_ratification_unix, "user_ratification_unix")
    threshold = max(source_time, ratification_time) + MINIMUM_LEAD_SECONDS
    if threshold > MAX_SAFE_INTEGER:
        raise DNRDSeedBindingError("eligible-round threshold exceeds safe integer range")
    if threshold <= QUICKNET_GENESIS_TIME_UNIX:
        return 1
    offset = threshold - QUICKNET_GENESIS_TIME_UNIX
    round_number = ((offset + QUICKNET_PERIOD_SECONDS - 1) // QUICKNET_PERIOD_SECONDS) + 1
    return _positive_round(round_number, "first_eligible_round")


@dataclass(frozen=True, slots=True)
class VerifiedQuicknetProjection:
    """A caller-supplied projection whose cryptographic verification already occurred."""

    chain_hash: str
    round: int
    round_time_unix: int
    randomness_hex: str
    verification_succeeded: bool
    verification_receipt_sha256: str
    _parser_attestation: object | None = field(default=None, repr=False, compare=False)

    def validate(self) -> None:
        if self._parser_attestation is not _PARSER_ATTESTATION:
            raise DNRDSeedBindingError(
                "Quicknet projection must be created by projection_from_verifier_receipt_bytes"
            )
        if self.chain_hash != QUICKNET_CHAIN_HASH:
            raise DNRDSeedBindingError("Quicknet chain hash does not match the frozen DNRD chain")
        round_number = _positive_round(self.round, "projection.round")
        if _unix_second(self.round_time_unix, "projection.round_time_unix") != quicknet_round_time_unix(round_number):
            raise DNRDSeedBindingError("projection.round_time_unix does not match the frozen Quicknet formula")
        _hex(self.randomness_hex, "projection.randomness_hex", length=64)
        if self.verification_succeeded is not True:
            raise DNRDSeedBindingError("projection.verification_succeeded must be true")
        _hex(
            self.verification_receipt_sha256,
            "projection.verification_receipt_sha256",
            length=64,
        )

    def canonical(self) -> dict[str, object]:
        self.validate()
        return {
            "chain_hash": self.chain_hash,
            "round": self.round,
            "round_time_unix": self.round_time_unix,
            "randomness_hex": self.randomness_hex,
            "verification_receipt_sha256": self.verification_receipt_sha256,
            "verification_succeeded": self.verification_succeeded,
        }


def _expected_quicknet_chain() -> dict[str, object]:
    return {
        "beacon_id": QUICKNET_BEACON_ID,
        "genesis_time": QUICKNET_GENESIS_TIME_UNIX,
        "group_hash": QUICKNET_GROUP_HASH,
        "hash": QUICKNET_CHAIN_HASH,
        "period": QUICKNET_PERIOD_SECONDS,
        "public_key": QUICKNET_PUBLIC_KEY,
        "scheme_id": QUICKNET_SIGNATURE_SCHEME,
    }


def projection_from_verifier_receipt_bytes(
    receipt_bytes: bytes,
    *,
    expected_helper_sha256: str,
    expected_package_lock_sha256: str,
    expected_runtime_bundle_sha256: str,
    expected_runtime_exec_sha256: str,
    expected_runtime_version: str,
) -> VerifiedQuicknetProjection:
    """Parse one pinned ``verify-beacon.mjs`` stdout receipt into a projection.

    The caller supplies the expected helper, package-lock, runtime-bundle, and
    Node executable identities.  This parser validates their occurrence in the
    receipt but does not itself perform BLS verification or network I/O; that
    happened in the verifier process which emitted these exact bytes.
    """

    for name, value in (
        ("expected_helper_sha256", expected_helper_sha256),
        ("expected_package_lock_sha256", expected_package_lock_sha256),
        ("expected_runtime_bundle_sha256", expected_runtime_bundle_sha256),
        ("expected_runtime_exec_sha256", expected_runtime_exec_sha256),
    ):
        _hex(value, name, length=64)
    _nonempty_string(expected_runtime_version, "expected_runtime_version")
    receipt = _strict_verifier_json_object(receipt_bytes)
    top = _exact_keys(
        receipt,
        {
            "chain",
            "chronology_claim_allowed",
            "helper_version",
            "input_fixture_sha256",
            "mode",
            "pulse",
            "pulse_source_url",
            "receipt_sha256",
            "schema_version",
            "verification",
            "verified_at_unix",
            "verifier",
        },
        "verifier receipt",
    )
    if top["schema_version"] != VERIFIER_RECEIPT_SCHEMA:
        raise DNRDSeedBindingError("verifier receipt schema version mismatch")
    if top["helper_version"] != VERIFIER_HELPER_VERSION:
        raise DNRDSeedBindingError("verifier helper version mismatch")
    if top["chronology_claim_allowed"] is not False:
        raise DNRDSeedBindingError("verifier receipt must not authorize chronology claims")

    chain = _exact_keys(
        top["chain"],
        set(_expected_quicknet_chain()),
        "verifier receipt.chain",
    )
    if dict(chain) != _expected_quicknet_chain():
        raise DNRDSeedBindingError("verifier receipt chain does not match frozen Quicknet constants")

    pulse = _exact_keys(
        top["pulse"],
        {"randomness", "round", "round_time_unix", "signature"},
        "verifier receipt.pulse",
    )
    round_number = _positive_round(pulse["round"], "verifier receipt.pulse.round")
    round_time = _unix_second(pulse["round_time_unix"], "verifier receipt.pulse.round_time_unix")
    if round_time != quicknet_round_time_unix(round_number):
        raise DNRDSeedBindingError("verifier receipt pulse round/time mismatch")
    randomness = _hex(pulse["randomness"], "verifier receipt.pulse.randomness", length=64)
    signature = _hex(pulse["signature"], "verifier receipt.pulse.signature", length=96)
    if sha256(bytes.fromhex(signature)).hexdigest() != randomness:
        raise DNRDSeedBindingError("verifier receipt randomness is not SHA256(signature bytes)")

    verification = _exact_keys(
        top["verification"],
        {
            "accepted_beacon_sha256",
            "accepted_by",
            "network_policy",
            "randomness_derivation",
            "signature_scheme",
        },
        "verifier receipt.verification",
    )
    accepted_beacon = {
        "randomness": randomness,
        "round": round_number,
        "signature": signature,
    }
    if _hex(
        verification["accepted_beacon_sha256"],
        "verifier receipt.verification.accepted_beacon_sha256",
        length=64,
    ) != sha256(_canonical_bytes(accepted_beacon)).hexdigest():
        raise DNRDSeedBindingError("verifier receipt accepted beacon digest mismatch")
    if verification["accepted_by"] != VERIFIER_ACCEPTED_BY:
        raise DNRDSeedBindingError("verifier receipt accepted_by mismatch")
    if verification["randomness_derivation"] != VERIFIER_RANDOMNESS_DERIVATION:
        raise DNRDSeedBindingError("verifier receipt randomness derivation mismatch")
    if verification["signature_scheme"] != QUICKNET_SIGNATURE_SCHEME:
        raise DNRDSeedBindingError("verifier receipt signature scheme mismatch")

    mode = top["mode"]
    if mode not in {"offline", "online"}:
        raise DNRDSeedBindingError("verifier receipt mode must be offline or online")
    expected_policy = (
        "OFFLINE_INJECTED_CLIENT_FETCH_GUARD" if mode == "offline" else "ONLINE_EXPLICIT"
    )
    if verification["network_policy"] != expected_policy:
        raise DNRDSeedBindingError("verifier receipt network policy does not match mode")
    fixture_sha = top["input_fixture_sha256"]
    if mode == "online":
        if fixture_sha is not None:
            raise DNRDSeedBindingError("online verifier receipt must have null input fixture digest")
    else:
        _hex(fixture_sha, "verifier receipt.input_fixture_sha256", length=64)
    expected_url = f"https://api.drand.sh/{QUICKNET_CHAIN_HASH}/public/{round_number}"
    if top["pulse_source_url"] != expected_url:
        raise DNRDSeedBindingError("verifier receipt pulse source URL mismatch")
    verified_at = _unix_second(top["verified_at_unix"], "verifier receipt.verified_at_unix")
    if verified_at < round_time:
        raise DNRDSeedBindingError("verifier receipt predates its pulse round")

    verifier = _exact_keys(
        top["verifier"],
        {
            "git_commit",
            "git_tag_url",
            "helper_sha256",
            "npm_integrity",
            "npm_shasum",
            "package",
            "package_json_sha256",
            "package_lock_sha256",
            "runtime_bundle_sha256",
            "runtime_engine",
            "runtime_exec_sha256",
            "runtime_trust_status",
            "runtime_version",
            "source_tarball",
            "version",
        },
        "verifier receipt.verifier",
    )
    _hex(verifier["git_commit"], "verifier receipt.verifier.git_commit", length=40)
    for field_name in (
        "helper_sha256",
        "package_json_sha256",
        "package_lock_sha256",
        "runtime_bundle_sha256",
        "runtime_exec_sha256",
    ):
        _hex(verifier[field_name], f"verifier receipt.verifier.{field_name}", length=64)
    if verifier["helper_sha256"] != expected_helper_sha256:
        raise DNRDSeedBindingError("verifier helper SHA pin mismatch")
    if verifier["package_lock_sha256"] != expected_package_lock_sha256:
        raise DNRDSeedBindingError("verifier package-lock SHA pin mismatch")
    if verifier["runtime_bundle_sha256"] != expected_runtime_bundle_sha256:
        raise DNRDSeedBindingError("verifier runtime-bundle SHA pin mismatch")
    if verifier["runtime_exec_sha256"] != expected_runtime_exec_sha256:
        raise DNRDSeedBindingError("verifier Node executable SHA pin mismatch")
    if verifier["runtime_version"] != expected_runtime_version:
        raise DNRDSeedBindingError("verifier Node version pin mismatch")
    if (
        verifier["package"] != "drand-client"
        or verifier["version"] != "1.4.2"
        or verifier["runtime_engine"] != "Node.js"
        or verifier["runtime_trust_status"] != "TRUSTED_LOCAL_OS_AND_NODE_RUNTIME_REQUIRED"
    ):
        raise DNRDSeedBindingError("verifier receipt provenance identity mismatch")
    for field_name in (
        "git_tag_url",
        "npm_integrity",
        "npm_shasum",
        "runtime_version",
        "source_tarball",
    ):
        _nonempty_string(verifier[field_name], f"verifier receipt.verifier.{field_name}")

    unsigned = dict(top)
    receipt_self_hash = unsigned.pop("receipt_sha256")
    if _hex(receipt_self_hash, "verifier receipt.receipt_sha256", length=64) != sha256(
        _canonical_bytes(unsigned)
    ).hexdigest():
        raise DNRDSeedBindingError("verifier receipt self-hash mismatch")
    return VerifiedQuicknetProjection(
        chain_hash=QUICKNET_CHAIN_HASH,
        round=round_number,
        round_time_unix=round_time,
        randomness_hex=randomness,
        verification_succeeded=True,
        verification_receipt_sha256=sha256(receipt_bytes).hexdigest(),
        _parser_attestation=_PARSER_ATTESTATION,
    )


@dataclass(frozen=True, slots=True)
class SourceFreezeBinding:
    """Exact source and preregistration identities included in seed material."""

    source_commit: str
    source_tree_oid: str
    source_manifest_sha256: str
    preregistration_commit: str
    preregistration_blob_sha256: str
    ratification_statement_sha256: str
    experiment_id: str = EXPERIMENT_ID

    def validate(self) -> None:
        _hex(self.source_commit, "source_commit", length=40)
        _hex(self.source_tree_oid, "source_tree_oid", length=40)
        _hex(self.source_manifest_sha256, "source_manifest_sha256", length=64)
        _hex(self.preregistration_commit, "preregistration_commit", length=40)
        _hex(self.preregistration_blob_sha256, "preregistration_blob_sha256", length=64)
        _hex(
            self.ratification_statement_sha256,
            "ratification_statement_sha256",
            length=64,
        )
        if self.experiment_id != EXPERIMENT_ID:
            raise DNRDSeedBindingError(f"experiment_id must be {EXPERIMENT_ID!r}")

    def canonical(self) -> dict[str, str]:
        self.validate()
        return {
            "experiment_id": self.experiment_id,
            "preregistration_blob_sha256": self.preregistration_blob_sha256,
            "preregistration_commit": self.preregistration_commit,
            "ratification_statement_sha256": self.ratification_statement_sha256,
            "source_commit": self.source_commit,
            "source_manifest_sha256": self.source_manifest_sha256,
            "source_tree_oid": self.source_tree_oid,
        }


def seed_material(
    *, projection: VerifiedQuicknetProjection, source_binding: SourceFreezeBinding
) -> dict[str, object]:
    """Return the one explicit, domain-separated canonical seed payload."""

    projection.validate()
    source_binding.validate()
    return {
        "domain": SEED_DOMAIN,
        "experiment_id": source_binding.experiment_id,
        "preregistration_blob_sha256": source_binding.preregistration_blob_sha256,
        "preregistration_commit": source_binding.preregistration_commit,
        "ratification_statement_sha256": source_binding.ratification_statement_sha256,
        "quicknet_chain_hash": projection.chain_hash,
        "quicknet_randomness_hex": projection.randomness_hex,
        "quicknet_round": projection.round,
        "quicknet_round_time_unix": projection.round_time_unix,
        "source_commit": source_binding.source_commit,
        "source_manifest_sha256": source_binding.source_manifest_sha256,
        "source_tree_oid": source_binding.source_tree_oid,
        "verification_receipt_sha256": projection.verification_receipt_sha256,
        "schema_version": SEED_MATERIAL_SCHEMA,
    }


def derive_seed_hex(
    *, projection: VerifiedQuicknetProjection, source_binding: SourceFreezeBinding
) -> str:
    """Derive exactly one 32-byte seed from the frozen canonical material."""

    return sha256(_canonical_bytes(seed_material(projection=projection, source_binding=source_binding))).hexdigest()


@dataclass(frozen=True, slots=True)
class DNRDPulseBindingReceipt:
    """Content-addressed proof of one exact, already-verified future pulse binding."""

    source_freeze_unix: int
    user_ratification_unix: int
    minimum_eligible_time_unix: int
    projection: VerifiedQuicknetProjection
    source_binding: SourceFreezeBinding
    seed_hex: str
    receipt_sha256: str
    schema_version: str = PULSE_BINDING_SCHEMA

    def canonical_without_receipt_sha256(self) -> dict[str, object]:
        if self.schema_version != PULSE_BINDING_SCHEMA:
            raise DNRDSeedBindingError("pulse binding schema version is invalid")
        source_time = _unix_second(self.source_freeze_unix, "source_freeze_unix")
        ratification_time = _unix_second(self.user_ratification_unix, "user_ratification_unix")
        expected_minimum = max(source_time, ratification_time) + MINIMUM_LEAD_SECONDS
        if self.minimum_eligible_time_unix != expected_minimum:
            raise DNRDSeedBindingError("minimum eligible time does not match frozen chronology")
        self.projection.validate()
        self.source_binding.validate()
        expected_round = first_eligible_quicknet_round(
            source_freeze_unix=source_time,
            user_ratification_unix=ratification_time,
        )
        if self.projection.round != expected_round:
            raise DNRDSeedBindingError("projection round is not the first eligible frozen Quicknet round")
        if self.projection.round_time_unix < expected_minimum:
            raise DNRDSeedBindingError("projection round is too early for frozen chronology")
        expected_seed = derive_seed_hex(projection=self.projection, source_binding=self.source_binding)
        if self.seed_hex != expected_seed:
            raise DNRDSeedBindingError("pulse binding seed does not match canonical seed material")
        _hex(self.seed_hex, "seed_hex", length=64)
        return {
            "minimum_eligible_time_unix": self.minimum_eligible_time_unix,
            "projection": self.projection.canonical(),
            "schema_version": self.schema_version,
            "seed_hex": self.seed_hex,
            "source_binding": self.source_binding.canonical(),
            "source_freeze_unix": self.source_freeze_unix,
            "user_ratification_unix": self.user_ratification_unix,
        }

    def validate(self) -> None:
        expected = sha256(_canonical_bytes(self.canonical_without_receipt_sha256())).hexdigest()
        if self.receipt_sha256 != expected:
            raise DNRDSeedBindingError("pulse binding receipt SHA-256 does not match canonical receipt bytes")
        _hex(self.receipt_sha256, "receipt_sha256", length=64)

    def canonical(self) -> dict[str, object]:
        self.validate()
        result = self.canonical_without_receipt_sha256()
        result["receipt_sha256"] = self.receipt_sha256
        return result


def bind_future_pulse(
    *,
    source_freeze_unix: int,
    user_ratification_unix: int,
    projection: VerifiedQuicknetProjection,
    source_binding: SourceFreezeBinding,
) -> DNRDPulseBindingReceipt:
    """Validate one exact eligible pulse and emit its self-addressed receipt."""

    source_time = _unix_second(source_freeze_unix, "source_freeze_unix")
    ratification_time = _unix_second(user_ratification_unix, "user_ratification_unix")
    minimum_time = max(source_time, ratification_time) + MINIMUM_LEAD_SECONDS
    projection.validate()
    source_binding.validate()
    expected_round = first_eligible_quicknet_round(
        source_freeze_unix=source_time,
        user_ratification_unix=ratification_time,
    )
    if projection.round != expected_round:
        raise DNRDSeedBindingError("supplied Quicknet round is early or not the first eligible round")
    if projection.round_time_unix < minimum_time:
        raise DNRDSeedBindingError("supplied Quicknet round time is too early")
    seed_hex = derive_seed_hex(projection=projection, source_binding=source_binding)
    unsigned = {
        "minimum_eligible_time_unix": minimum_time,
        "projection": projection.canonical(),
        "schema_version": PULSE_BINDING_SCHEMA,
        "seed_hex": seed_hex,
        "source_binding": source_binding.canonical(),
        "source_freeze_unix": source_time,
        "user_ratification_unix": ratification_time,
    }
    receipt = DNRDPulseBindingReceipt(
        source_freeze_unix=source_time,
        user_ratification_unix=ratification_time,
        minimum_eligible_time_unix=minimum_time,
        projection=projection,
        source_binding=source_binding,
        seed_hex=seed_hex,
        receipt_sha256=sha256(_canonical_bytes(unsigned)).hexdigest(),
    )
    receipt.validate()
    return receipt


__all__ = [
    "DNRDPulseBindingReceipt",
    "DNRDSeedBindingError",
    "EXPERIMENT_ID",
    "MAX_QUICKNET_ROUND",
    "MINIMUM_LEAD_SECONDS",
    "PULSE_BINDING_SCHEMA",
    "QUICKNET_BEACON_ID",
    "QUICKNET_CHAIN_HASH",
    "QUICKNET_GENESIS_TIME_UNIX",
    "QUICKNET_GROUP_HASH",
    "QUICKNET_PERIOD_SECONDS",
    "QUICKNET_PUBLIC_KEY",
    "QUICKNET_SIGNATURE_SCHEME",
    "SEED_DOMAIN",
    "SourceFreezeBinding",
    "VerifiedQuicknetProjection",
    "bind_future_pulse",
    "derive_seed_hex",
    "first_eligible_quicknet_round",
    "projection_from_verifier_receipt_bytes",
    "quicknet_round_time_unix",
    "seed_material",
]
