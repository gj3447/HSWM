"""Fail-closed future-public-randomness binding for future SWM-0W tasks.

This repository-checkout module is a narrow experimental provenance boundary,
primarily in ``Pi``:
it binds a proposed experiment to one exact future Quicknet round and derives
twenty domain-separated task seeds only after a pinned Node verifier has made
the official ``drand-client`` cryptographically accept that pulse.

It creates no preregistration, chooses no live future round, and reports no
confirmatory result.  In particular, a same-party timestamp/commit/reveal is
not chronology evidence.  Independent external registration is still needed.

Official references:

* https://docs.drand.love/blog/2023/10/16/quicknet-is-live/
* https://docs.drand.love/docs/cryptography/
* https://github.com/drand/drand-client/tree/v1.4.2
* https://csrc.nist.gov/pubs/ir/8213/ipd
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Mapping, Sequence


COMMITMENT_SCHEMA = "hswm-swm0w-drand-future-round-commitment/v1"
VERIFIER_RECEIPT_SCHEMA = "hswm-swm0w-drand-verification-receipt/v1"
BINDING_SCHEMA = "hswm-swm0w-drand-task-seed-binding/v1"
HELPER_VERSION = "hswm-swm0w-drand-node-verifier/v1"
VERIFIER_DISTRIBUTION_SCOPE = "REPOSITORY_OR_SOURCE_CHECKOUT_ONLY"
RUNTIME_TRUST_STATUS = "TRUSTED_LOCAL_OS_AND_NODE_RUNTIME_REQUIRED"

QUICKNET_CHAIN_HASH = "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971"
QUICKNET_PUBLIC_KEY = (
    "83cf0f2896adee7eb8b5f01fcad3912212c437e0073e911fb90022d3e760183c"
    "8c4b450b6a0a6c3ac6a5776a2d1064510d1fec758c921cc22b0e17e63aaf4bcb"
    "5ed66304de9cf809bd274ca73bab4af5a6e9c76a4bc09e76eae8991ef5ece45a"
)
QUICKNET_GROUP_HASH = "f477d5c89f21a17c863a7f937c6a6d15859414d2be09cd448d4279af331c5d3e"
QUICKNET_GENESIS_TIME = 1_692_803_367
QUICKNET_PERIOD_SECONDS = 3
QUICKNET_SCHEME_ID = "bls-unchained-g1-rfc9380"
QUICKNET_BEACON_ID = "quicknet"
QUICKNET_BASE_URL = f"https://api.drand.sh/{QUICKNET_CHAIN_HASH}"

DRAND_CLIENT_PACKAGE = "drand-client"
DRAND_CLIENT_VERSION = "1.4.2"
DRAND_CLIENT_GIT_COMMIT = "ef8c9260294f8699b5e8c27a6b764f8f0d768bea"
DRAND_CLIENT_GIT_TAG_URL = "https://github.com/drand/drand-client/tree/v1.4.2"
DRAND_CLIENT_TARBALL = (
    "https://registry.npmjs.org/drand-client/-/drand-client-1.4.2.tgz"
)
DRAND_CLIENT_NPM_INTEGRITY = (
    "sha512-jeNJmrVplfgIA/GVndxxJ5mo8y63BS2pEdNhk1siU4pQ+z/"
    "BnxsqRnxjH9ag1ip887s12SEgo0MTZPbQNz27NA=="
)
DRAND_CLIENT_NPM_SHASUM = "f9108eef6881e62c0c0f154f30f7bd0a818ea809"

NIST_FUTURE_PUBLIC_RANDOMNESS_URL = "https://csrc.nist.gov/pubs/ir/8213/ipd"
DRAND_QUICKNET_DOC_URL = "https://docs.drand.love/blog/2023/10/16/quicknet-is-live/"
DRAND_CRYPTOGRAPHY_DOC_URL = "https://docs.drand.love/docs/cryptography/"

TASK_COUNT = 20
TASK_SEED_DOMAIN = "HSWM-SWM0W-TASK-SEED-V1"
MAX_SAFE_INTEGER = 9_007_199_254_740_991
MAX_QUICKNET_ROUND = (
    (MAX_SAFE_INTEGER - QUICKNET_GENESIS_TIME) // QUICKNET_PERIOD_SECONDS
) + 1
MAX_OFFLINE_FIXTURE_BYTES = 65_536
CHRONOLOGY_STATUS = (
    "CRYPTOGRAPHIC_PULSE_VERIFIED_CHRONOLOGY_REQUIRES_INDEPENDENT_EXTERNAL_"
    "REGISTRATION_EVIDENCE"
)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_TOOL_ROOT = _REPOSITORY_ROOT / "tools" / "swm0w_drand"
DEFAULT_NODE_HELPER = _TOOL_ROOT / "verify-beacon.mjs"
DEFAULT_PACKAGE_LOCK = _TOOL_ROOT / "package-lock.json"
DEFAULT_OFFLINE_FIXTURE = _TOOL_ROOT / "fixtures" / "quicknet-round-1000.json"
_INSTALLED_PACKAGE_JSON = _TOOL_ROOT / "node_modules" / "drand-client" / "package.json"
_INSTALLED_RUNTIME_BUNDLE = (
    _TOOL_ROOT / "node_modules" / "drand-client" / "build" / "esm" / "index.mjs"
)

# Filled from the generated npm v3 lock and the exact helper/client bytes.  They
# deliberately make verifier changes fail closed until this module is reviewed.
VERIFIER_PACKAGE_LOCK_SHA256 = (
    "ca0acb4a88ab7e1ade131e9e2f2fecc7d716b8cfb788922c172f4dbcd9eb4be6"
)
VERIFIER_HELPER_SHA256 = (
    "0f0643c67cb18ec0e760c087d0b6a95d5f5b3fcc063686fec42e0a03d6390fc6"
)
DRAND_CLIENT_PACKAGE_JSON_SHA256 = (
    "71271cae1994991202a8e717923560d62db0c615e19e31e9a60f40b92d8ee9f7"
)
DRAND_CLIENT_RUNTIME_BUNDLE_SHA256 = (
    "c5f6eff0d5692efd8f2e19953a49713d17554739016f9d0f3235380aab9ea904"
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_HEX_RE = re.compile(r"^[0-9a-f]+$")
_EXPERIMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")


class SWM0WBeaconError(ValueError):
    """Raised when a commitment, verifier, pulse, or seed binding fails."""


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise SWM0WBeaconError("canonical JSON object keys must be strings")
        return {
            key: _jsonable(item)
            for key, item in sorted(value.items(), key=lambda pair: pair[0])
        }
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SWM0WBeaconError("canonical JSON rejects non-finite floats")
        return value
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if hasattr(value, "canonical"):
        return _jsonable(value.canonical())
    raise SWM0WBeaconError(f"unsupported canonical value: {type(value)!r}")


def canonical_json(value: Any) -> str:
    return json.dumps(
        _jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_sha256(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    try:
        return sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise SWM0WBeaconError(f"required verifier file is unavailable: {path}") from exc


def _require_int(
    value: Any,
    name: str,
    *,
    minimum: int = 0,
    maximum: int = MAX_SAFE_INTEGER,
) -> int:
    if type(value) is not int or value < minimum or value > maximum:
        raise SWM0WBeaconError(
            f"{name} must be an integer in [{minimum}, {maximum}]"
        )
    return value


def _require_sha256(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise SWM0WBeaconError(f"{name} must be lowercase SHA-256")
    return value


def _require_hex(value: Any, byte_count: int, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != byte_count * 2
        or not _HEX_RE.fullmatch(value)
    ):
        raise SWM0WBeaconError(f"{name} must be {byte_count} lowercase hex bytes")
    return value


def _require_exact_keys(
    value: Any, expected: Sequence[str], name: str
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != set(expected):
        raise SWM0WBeaconError(f"{name} keys do not match the frozen schema")
    return value


def quicknet_round_time(round_number: int) -> int:
    selected = _require_int(
        round_number,
        "round",
        minimum=1,
        maximum=MAX_QUICKNET_ROUND,
    )
    return QUICKNET_GENESIS_TIME + (selected - 1) * QUICKNET_PERIOD_SECONDS


def first_quicknet_round_strictly_after(timestamp_unix: int) -> int:
    timestamp = _require_int(timestamp_unix, "timestamp_unix", minimum=0)
    if timestamp < QUICKNET_GENESIS_TIME:
        return 1
    return ((timestamp - QUICKNET_GENESIS_TIME) // QUICKNET_PERIOD_SECONDS) + 2


@dataclass(frozen=True, slots=True)
class FutureRoundCommitmentV1:
    experiment_id: str
    registration_evidence_sha256: str
    registered_at_unix: int
    chain_hash: str
    round: int
    round_time_unix: int
    task_count: int
    seed_domain: str
    chronology_claim_allowed: bool
    commitment_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.experiment_id, str) or not _EXPERIMENT_RE.fullmatch(
            self.experiment_id
        ):
            raise SWM0WBeaconError("experiment_id has an invalid form")
        _require_sha256(
            self.registration_evidence_sha256, "registration_evidence_sha256"
        )
        registered = _require_int(
            self.registered_at_unix,
            "registered_at_unix",
            minimum=QUICKNET_GENESIS_TIME,
        )
        selected_round = _require_int(
            self.round,
            "round",
            minimum=1,
            maximum=MAX_QUICKNET_ROUND,
        )
        if self.chain_hash != QUICKNET_CHAIN_HASH:
            raise SWM0WBeaconError("commitment must use the pinned Quicknet chain")
        if self.round_time_unix != quicknet_round_time(selected_round):
            raise SWM0WBeaconError("commitment round/time mismatch")
        if self.round_time_unix <= registered:
            raise SWM0WBeaconError("committed pulse must be strictly after registration time")
        if self.task_count != TASK_COUNT or self.seed_domain != TASK_SEED_DOMAIN:
            raise SWM0WBeaconError("commitment task count/domain mismatch")
        if self.chronology_claim_allowed is not False:
            raise SWM0WBeaconError("same-party commitment cannot claim chronology")
        _require_sha256(self.commitment_sha256, "commitment_sha256")
        if self.commitment_sha256 != canonical_sha256(self.unsigned()):
            raise SWM0WBeaconError("commitment self-hash mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "chain_hash": self.chain_hash,
            "chronology_claim_allowed": self.chronology_claim_allowed,
            "experiment_id": self.experiment_id,
            "registered_at_unix": self.registered_at_unix,
            "registration_evidence_sha256": self.registration_evidence_sha256,
            "round": self.round,
            "round_time_unix": self.round_time_unix,
            "schema_version": COMMITMENT_SCHEMA,
            "seed_domain": self.seed_domain,
            "task_count": self.task_count,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "commitment_sha256": self.commitment_sha256}


def make_future_round_commitment(
    *,
    experiment_id: str,
    registration_evidence_sha256: str,
    registered_at_unix: int,
    round_number: int,
) -> FutureRoundCommitmentV1:
    unsigned = {
        "chain_hash": QUICKNET_CHAIN_HASH,
        "chronology_claim_allowed": False,
        "experiment_id": experiment_id,
        "registered_at_unix": registered_at_unix,
        "registration_evidence_sha256": registration_evidence_sha256,
        "round": round_number,
        "round_time_unix": quicknet_round_time(round_number),
        "schema_version": COMMITMENT_SCHEMA,
        "seed_domain": TASK_SEED_DOMAIN,
        "task_count": TASK_COUNT,
    }
    return FutureRoundCommitmentV1(
        experiment_id=experiment_id,
        registration_evidence_sha256=registration_evidence_sha256,
        registered_at_unix=registered_at_unix,
        chain_hash=QUICKNET_CHAIN_HASH,
        round=round_number,
        round_time_unix=unsigned["round_time_unix"],
        task_count=TASK_COUNT,
        seed_domain=TASK_SEED_DOMAIN,
        chronology_claim_allowed=False,
        commitment_sha256=canonical_sha256(unsigned),
    )


def parse_future_round_commitment(
    value: Mapping[str, Any],
) -> FutureRoundCommitmentV1:
    data = _require_exact_keys(
        value,
        (
            "chain_hash",
            "chronology_claim_allowed",
            "commitment_sha256",
            "experiment_id",
            "registered_at_unix",
            "registration_evidence_sha256",
            "round",
            "round_time_unix",
            "schema_version",
            "seed_domain",
            "task_count",
        ),
        "commitment",
    )
    if data["schema_version"] != COMMITMENT_SCHEMA:
        raise SWM0WBeaconError("unsupported commitment schema")
    return FutureRoundCommitmentV1(
        experiment_id=data["experiment_id"],
        registration_evidence_sha256=data["registration_evidence_sha256"],
        registered_at_unix=data["registered_at_unix"],
        chain_hash=data["chain_hash"],
        round=data["round"],
        round_time_unix=data["round_time_unix"],
        task_count=data["task_count"],
        seed_domain=data["seed_domain"],
        chronology_claim_allowed=data["chronology_claim_allowed"],
        commitment_sha256=data["commitment_sha256"],
    )


@dataclass(frozen=True, slots=True)
class VerifiedPulseV1:
    mode: str
    round: int
    round_time_unix: int
    randomness: str
    signature: str
    verified_at_unix: int
    verifier_receipt_sha256: str


def _expected_chain() -> dict[str, Any]:
    return {
        "beacon_id": QUICKNET_BEACON_ID,
        "genesis_time": QUICKNET_GENESIS_TIME,
        "group_hash": QUICKNET_GROUP_HASH,
        "hash": QUICKNET_CHAIN_HASH,
        "period": QUICKNET_PERIOD_SECONDS,
        "public_key": QUICKNET_PUBLIC_KEY,
        "scheme_id": QUICKNET_SCHEME_ID,
    }


def _validate_verifier_provenance(value: Any) -> None:
    data = _require_exact_keys(
        value,
        (
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
        ),
        "verifier",
    )
    fixed_expected = {
        "git_commit": DRAND_CLIENT_GIT_COMMIT,
        "git_tag_url": DRAND_CLIENT_GIT_TAG_URL,
        "helper_sha256": VERIFIER_HELPER_SHA256,
        "npm_integrity": DRAND_CLIENT_NPM_INTEGRITY,
        "npm_shasum": DRAND_CLIENT_NPM_SHASUM,
        "package": DRAND_CLIENT_PACKAGE,
        "package_json_sha256": DRAND_CLIENT_PACKAGE_JSON_SHA256,
        "package_lock_sha256": VERIFIER_PACKAGE_LOCK_SHA256,
        "runtime_bundle_sha256": DRAND_CLIENT_RUNTIME_BUNDLE_SHA256,
        "runtime_engine": "Node.js",
        "runtime_trust_status": RUNTIME_TRUST_STATUS,
        "source_tarball": DRAND_CLIENT_TARBALL,
        "version": DRAND_CLIENT_VERSION,
    }
    fixed_actual = dict(data)
    _require_sha256(fixed_actual.pop("runtime_exec_sha256", None), "runtime_exec_sha256")
    runtime_version = fixed_actual.pop("runtime_version", None)
    if fixed_actual != fixed_expected:
        raise SWM0WBeaconError("verifier source/version/integrity mismatch")
    match = re.fullmatch(r"v([0-9]+)\.([0-9]+)\.([0-9]+)", runtime_version or "")
    if match is None or int(match.group(1)) < 18:
        raise SWM0WBeaconError("verifier requires a recorded Node.js >=18 runtime")


def validate_verifier_receipt(
    value: Mapping[str, Any], commitment: FutureRoundCommitmentV1
) -> VerifiedPulseV1:
    """Validate a helper receipt exactly; this alone does not rerun BLS.

    Seed production is intentionally exposed only through ``verify_and_bind_*``,
    which executes the pinned Node cryptographic verifier first.
    """

    if not isinstance(commitment, FutureRoundCommitmentV1):
        raise SWM0WBeaconError("commitment must be a validated commitment object")
    data = _require_exact_keys(
        value,
        (
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
        ),
        "verifier receipt",
    )
    if data["schema_version"] != VERIFIER_RECEIPT_SCHEMA:
        raise SWM0WBeaconError("unsupported verifier receipt schema")
    if data["helper_version"] != HELPER_VERSION:
        raise SWM0WBeaconError("unexpected Node helper version")
    if data["chronology_claim_allowed"] is not False:
        raise SWM0WBeaconError("verifier receipt cannot claim chronology")
    if data["mode"] not in {"offline", "online"}:
        raise SWM0WBeaconError("unsupported verifier mode")
    if dict(_require_exact_keys(data["chain"], _expected_chain(), "chain")) != _expected_chain():
        raise SWM0WBeaconError("verifier receipt Quicknet chain mismatch")
    pulse = _require_exact_keys(
        data["pulse"],
        ("randomness", "round", "round_time_unix", "signature"),
        "pulse",
    )
    if pulse["round"] != commitment.round:
        raise SWM0WBeaconError("verified pulse round does not match commitment")
    if pulse["round_time_unix"] != commitment.round_time_unix:
        raise SWM0WBeaconError("verified pulse time does not match commitment")
    randomness = _require_hex(pulse["randomness"], 32, "pulse.randomness")
    signature = _require_hex(pulse["signature"], 48, "pulse.signature")
    if sha256(bytes.fromhex(signature)).hexdigest() != randomness:
        raise SWM0WBeaconError("randomness is not SHA256(signature bytes)")
    expected_url = f"{QUICKNET_BASE_URL}/public/{commitment.round}"
    if data["pulse_source_url"] != expected_url:
        raise SWM0WBeaconError("pulse source URL does not bind exact chain/round")
    if data["mode"] == "offline":
        _require_sha256(data["input_fixture_sha256"], "input_fixture_sha256")
        expected_network_policy = "OFFLINE_INJECTED_CLIENT_FETCH_GUARD"
    else:
        if data["input_fixture_sha256"] is not None:
            raise SWM0WBeaconError("online verifier cannot claim an offline fixture")
        expected_network_policy = "ONLINE_EXPLICIT"
    verification = _require_exact_keys(
        data["verification"],
        (
            "accepted_beacon_sha256",
            "accepted_by",
            "network_policy",
            "randomness_derivation",
            "signature_scheme",
        ),
        "verification",
    )
    client_beacon = {
        "randomness": randomness,
        "round": commitment.round,
        "signature": signature,
    }
    expected_verification = {
        "accepted_beacon_sha256": canonical_sha256(client_beacon),
        "accepted_by": "drand-client.fetchBeacon",
        "network_policy": expected_network_policy,
        "randomness_derivation": "SHA256(raw_signature_bytes)",
        "signature_scheme": QUICKNET_SCHEME_ID,
    }
    if dict(verification) != expected_verification:
        raise SWM0WBeaconError("receipt lacks the exact cryptographic verifier evidence")
    _validate_verifier_provenance(data["verifier"])
    verified_at = _require_int(data["verified_at_unix"], "verified_at_unix")
    if verified_at < commitment.round_time_unix:
        raise SWM0WBeaconError("verifier timestamp predates the selected pulse")
    receipt_sha = _require_sha256(data["receipt_sha256"], "receipt_sha256")
    unsigned = dict(data)
    del unsigned["receipt_sha256"]
    if canonical_sha256(unsigned) != receipt_sha:
        raise SWM0WBeaconError("verifier receipt self-hash mismatch")
    return VerifiedPulseV1(
        mode=data["mode"],
        round=commitment.round,
        round_time_unix=commitment.round_time_unix,
        randomness=randomness,
        signature=signature,
        verified_at_unix=verified_at,
        verifier_receipt_sha256=receipt_sha,
    )


def verifier_dependency_available() -> bool:
    return (
        shutil.which("node") is not None
        and DEFAULT_NODE_HELPER.is_file()
        and DEFAULT_PACKAGE_LOCK.is_file()
        and _INSTALLED_PACKAGE_JSON.is_file()
        and _INSTALLED_RUNTIME_BUNDLE.is_file()
    )


def _verify_local_dependency_bytes() -> None:
    expected = (
        (DEFAULT_NODE_HELPER, VERIFIER_HELPER_SHA256),
        (DEFAULT_PACKAGE_LOCK, VERIFIER_PACKAGE_LOCK_SHA256),
        (_INSTALLED_PACKAGE_JSON, DRAND_CLIENT_PACKAGE_JSON_SHA256),
        (_INSTALLED_RUNTIME_BUNDLE, DRAND_CLIENT_RUNTIME_BUNDLE_SHA256),
    )
    for path, digest in expected:
        _require_sha256(digest, f"pinned digest for {path.name}")
        if file_sha256(path) != digest:
            raise SWM0WBeaconError(f"local verifier dependency digest mismatch: {path}")


def invoke_node_verifier(
    commitment: FutureRoundCommitmentV1,
    *,
    mode: str = "offline",
    pulse_file: Path | None = None,
    allow_network: bool = False,
    timeout_seconds: float = 30.0,
) -> Mapping[str, Any]:
    """Run the pinned cryptographic verifier; online access requires opt-in."""

    if not isinstance(commitment, FutureRoundCommitmentV1):
        raise SWM0WBeaconError("commitment must be a validated commitment object")
    if mode not in {"offline", "online"}:
        raise SWM0WBeaconError("mode must be offline or online")
    if mode == "online" and not allow_network:
        raise SWM0WBeaconError("online drand verification requires allow_network=True")
    if mode == "offline" and allow_network:
        raise SWM0WBeaconError("offline verification cannot enable network access")
    if (
        type(timeout_seconds) not in {int, float}
        or not math.isfinite(timeout_seconds)
        or timeout_seconds <= 0
    ):
        raise SWM0WBeaconError("timeout_seconds must be finite and positive")
    _verify_local_dependency_bytes()
    binary = shutil.which("node")
    if binary is None:
        raise SWM0WBeaconError("Node.js verifier runtime is unavailable")
    runtime_exec_sha256 = file_sha256(Path(binary).resolve())
    command = [
        binary,
        str(DEFAULT_NODE_HELPER),
        mode,
        "--expected-round",
        str(commitment.round),
    ]
    selected_fixture: Path | None = None
    if mode == "offline":
        selected_fixture = DEFAULT_OFFLINE_FIXTURE if pulse_file is None else Path(pulse_file)
        try:
            fixture_stat = selected_fixture.stat()
        except OSError as exc:
            raise SWM0WBeaconError("offline pulse fixture is unavailable") from exc
        if not selected_fixture.is_file() or fixture_stat.st_size > MAX_OFFLINE_FIXTURE_BYTES:
            raise SWM0WBeaconError(
                "offline pulse fixture must be a bounded regular file"
            )
        command.extend(("--pulse-file", str(selected_fixture)))
    elif pulse_file is not None:
        raise SWM0WBeaconError("online mode cannot accept a pulse fixture")
    try:
        verifier_environment = os.environ.copy()
        verifier_environment.pop("NODE_OPTIONS", None)
        verifier_environment.pop("NODE_PATH", None)
        completed = subprocess.run(
            command,
            cwd=_TOOL_ROOT,
            check=False,
            capture_output=True,
            env=verifier_environment,
            text=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SWM0WBeaconError("Node cryptographic verifier did not complete") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip()[-500:]
        raise SWM0WBeaconError(f"Node cryptographic verifier rejected pulse: {detail}")
    if completed.stderr.strip():
        raise SWM0WBeaconError("Node verifier emitted unexpected stderr")
    try:
        receipt = json.loads(completed.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        raise SWM0WBeaconError("Node verifier did not return one JSON receipt") from exc
    if not isinstance(receipt, Mapping):
        raise SWM0WBeaconError("Node verifier receipt must be an object")
    verifier = receipt.get("verifier")
    if not isinstance(verifier, Mapping) or verifier.get(
        "runtime_exec_sha256"
    ) != runtime_exec_sha256:
        raise SWM0WBeaconError("Node receipt does not bind the executed runtime")
    if selected_fixture is not None and receipt.get("input_fixture_sha256") != file_sha256(
        selected_fixture
    ):
        raise SWM0WBeaconError("Node receipt does not bind the supplied fixture bytes")
    validate_verifier_receipt(receipt, commitment)
    return receipt


@dataclass(frozen=True, slots=True)
class TaskSeedBindingV1:
    """Deterministic seed material, not standalone evidence of BLS execution."""

    commitment_sha256: str
    verifier_receipt_sha256: str
    chain_hash: str
    round: int
    randomness: str
    seed_domain: str
    task_seed_hex: tuple[str, ...]
    chronology_status: str
    chronology_claim_allowed: bool
    binding_sha256: str

    def __post_init__(self) -> None:
        _require_sha256(self.commitment_sha256, "commitment_sha256")
        _require_sha256(self.verifier_receipt_sha256, "verifier_receipt_sha256")
        if self.chain_hash != QUICKNET_CHAIN_HASH:
            raise SWM0WBeaconError("seed binding chain mismatch")
        _require_int(
            self.round,
            "round",
            minimum=1,
            maximum=MAX_QUICKNET_ROUND,
        )
        _require_hex(self.randomness, 32, "randomness")
        if self.seed_domain != TASK_SEED_DOMAIN:
            raise SWM0WBeaconError("seed binding domain mismatch")
        if len(self.task_seed_hex) != TASK_COUNT:
            raise SWM0WBeaconError("seed binding must contain exactly 20 task seeds")
        for index, value in enumerate(self.task_seed_hex):
            _require_hex(value, 32, f"task_seed_hex[{index}]")
        if len(set(self.task_seed_hex)) != TASK_COUNT:
            raise SWM0WBeaconError("task seeds must be unique")
        expected_seeds = tuple(
            _derive_task_seed(
                commitment_sha256=self.commitment_sha256,
                randomness=self.randomness,
                round_number=self.round,
                index=index,
            ).hex()
            for index in range(TASK_COUNT)
        )
        if self.task_seed_hex != expected_seeds:
            raise SWM0WBeaconError("task seeds do not match the frozen derivation")
        if self.chronology_status != CHRONOLOGY_STATUS:
            raise SWM0WBeaconError("seed binding chronology status mismatch")
        if self.chronology_claim_allowed is not False:
            raise SWM0WBeaconError("seed binding cannot claim chronology")
        _require_sha256(self.binding_sha256, "binding_sha256")
        if self.binding_sha256 != canonical_sha256(self.unsigned()):
            raise SWM0WBeaconError("seed binding self-hash mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "chain_hash": self.chain_hash,
            "chronology_claim_allowed": self.chronology_claim_allowed,
            "chronology_status": self.chronology_status,
            "commitment_sha256": self.commitment_sha256,
            "randomness": self.randomness,
            "round": self.round,
            "schema_version": BINDING_SCHEMA,
            "seed_domain": self.seed_domain,
            "task_seed_hex": list(self.task_seed_hex),
            "verifier_receipt_sha256": self.verifier_receipt_sha256,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "binding_sha256": self.binding_sha256}

    def task_seed_bytes(self) -> tuple[bytes, ...]:
        return tuple(bytes.fromhex(value) for value in self.task_seed_hex)


def validate_task_seed_bundle_links(
    commitment: FutureRoundCommitmentV1,
    verifier_receipt: Mapping[str, Any],
    binding: TaskSeedBindingV1,
) -> TaskSeedBindingV1:
    """Cross-check all bundle links without claiming to rerun BLS verification.

    Evidence admission must still originate in ``verify_and_bind_*`` or rerun
    the pinned helper independently. A binding object by itself is not proof.
    """

    if not isinstance(binding, TaskSeedBindingV1):
        raise SWM0WBeaconError("binding must be a validated task-seed binding")
    pulse = validate_verifier_receipt(verifier_receipt, commitment)
    expected = (
        (binding.commitment_sha256, commitment.commitment_sha256),
        (binding.verifier_receipt_sha256, pulse.verifier_receipt_sha256),
        (binding.chain_hash, commitment.chain_hash),
        (binding.round, pulse.round),
        (binding.randomness, pulse.randomness),
    )
    if any(actual != wanted for actual, wanted in expected):
        raise SWM0WBeaconError("commitment, verifier receipt, and seed binding diverge")
    return binding


def _derive_task_seed(
    *, commitment_sha256: str, randomness: str, round_number: int, index: int
) -> bytes:
    material = b"\x00".join(
        (
            TASK_SEED_DOMAIN.encode("ascii"),
            bytes.fromhex(QUICKNET_CHAIN_HASH),
            round_number.to_bytes(8, "big"),
            bytes.fromhex(randomness),
            bytes.fromhex(commitment_sha256),
            index.to_bytes(4, "big"),
        )
    )
    return sha256(material).digest()


def _bind_task_seeds_from_verified_execution(
    commitment: FutureRoundCommitmentV1,
    verifier_receipt: Mapping[str, Any],
) -> TaskSeedBindingV1:
    """Build seeds after ``invoke_node_verifier``; never a public receipt-only API."""

    pulse = validate_verifier_receipt(verifier_receipt, commitment)
    seeds = tuple(
        _derive_task_seed(
            commitment_sha256=commitment.commitment_sha256,
            randomness=pulse.randomness,
            round_number=pulse.round,
            index=index,
        ).hex()
        for index in range(TASK_COUNT)
    )
    unsigned = {
        "chain_hash": QUICKNET_CHAIN_HASH,
        "chronology_claim_allowed": False,
        "chronology_status": CHRONOLOGY_STATUS,
        "commitment_sha256": commitment.commitment_sha256,
        "randomness": pulse.randomness,
        "round": pulse.round,
        "schema_version": BINDING_SCHEMA,
        "seed_domain": TASK_SEED_DOMAIN,
        "task_seed_hex": list(seeds),
        "verifier_receipt_sha256": pulse.verifier_receipt_sha256,
    }
    return TaskSeedBindingV1(
        commitment_sha256=commitment.commitment_sha256,
        verifier_receipt_sha256=pulse.verifier_receipt_sha256,
        chain_hash=QUICKNET_CHAIN_HASH,
        round=pulse.round,
        randomness=pulse.randomness,
        seed_domain=TASK_SEED_DOMAIN,
        task_seed_hex=seeds,
        chronology_status=CHRONOLOGY_STATUS,
        chronology_claim_allowed=False,
        binding_sha256=canonical_sha256(unsigned),
    )


def verify_and_bind_offline(
    commitment: FutureRoundCommitmentV1,
    *,
    pulse_file: Path | None = None,
) -> tuple[Mapping[str, Any], TaskSeedBindingV1]:
    receipt = invoke_node_verifier(
        commitment,
        mode="offline",
        pulse_file=pulse_file,
    )
    return receipt, _bind_task_seeds_from_verified_execution(commitment, receipt)


def verify_and_bind_online(
    commitment: FutureRoundCommitmentV1,
    *,
    allow_network: bool = False,
) -> tuple[Mapping[str, Any], TaskSeedBindingV1]:
    """Explicitly fetch, cryptographically verify, and bind one committed round."""

    receipt = invoke_node_verifier(
        commitment,
        mode="online",
        allow_network=allow_network,
    )
    return receipt, _bind_task_seeds_from_verified_execution(commitment, receipt)


__all__ = [
    "BINDING_SCHEMA",
    "CHRONOLOGY_STATUS",
    "COMMITMENT_SCHEMA",
    "DEFAULT_NODE_HELPER",
    "DEFAULT_OFFLINE_FIXTURE",
    "DRAND_CLIENT_GIT_COMMIT",
    "DRAND_CLIENT_GIT_TAG_URL",
    "DRAND_CLIENT_NPM_INTEGRITY",
    "DRAND_CLIENT_NPM_SHASUM",
    "DRAND_CLIENT_PACKAGE",
    "DRAND_CLIENT_TARBALL",
    "DRAND_CLIENT_VERSION",
    "DRAND_CRYPTOGRAPHY_DOC_URL",
    "DRAND_QUICKNET_DOC_URL",
    "FutureRoundCommitmentV1",
    "NIST_FUTURE_PUBLIC_RANDOMNESS_URL",
    "QUICKNET_BEACON_ID",
    "QUICKNET_CHAIN_HASH",
    "QUICKNET_GENESIS_TIME",
    "QUICKNET_GROUP_HASH",
    "QUICKNET_PERIOD_SECONDS",
    "QUICKNET_PUBLIC_KEY",
    "QUICKNET_SCHEME_ID",
    "RUNTIME_TRUST_STATUS",
    "SWM0WBeaconError",
    "TASK_COUNT",
    "TASK_SEED_DOMAIN",
    "TaskSeedBindingV1",
    "VerifiedPulseV1",
    "VERIFIER_DISTRIBUTION_SCOPE",
    "canonical_json",
    "canonical_sha256",
    "first_quicknet_round_strictly_after",
    "invoke_node_verifier",
    "make_future_round_commitment",
    "parse_future_round_commitment",
    "quicknet_round_time",
    "validate_task_seed_bundle_links",
    "validate_verifier_receipt",
    "verifier_dependency_available",
    "verify_and_bind_offline",
    "verify_and_bind_online",
]
