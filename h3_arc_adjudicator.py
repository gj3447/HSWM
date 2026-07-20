"""Frozen, query-label-blind identity adjudicator for H3-B3 shared joins.

The H3-B3 compiler can propose a directed relation continuation only when two
claim-role spans share a conservatively admitted surface.  Surface equality is
not entity identity, so this module applies the preregistered independent
safety gate: one Qwen3.6-27B request per sampled emitted join/source pair,
containing only the two local evidence contexts frozen by
:func:`build_arc_precision_audit_packet`.

Every attempt is a first-write-wins receipt.  Invalid JSON, a missing decision,
model mismatch, HTTP failure, or transport failure is durably recorded as
``UNCLEAR`` and therefore ``correct=false``.  The cache validates retained
preimages, repairs only an incomplete final line, and never retries a completed
request.  This prevents selective re-adjudication after seeing an unfavorable
identity decision.

Longinus ReferenceSite: ``H3_B3_COMPOSITION_PREREG_2026-07-20.md`` section 5
(query-label-blind shared-join audit and Wilson precision gate).
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, fields, replace
from enum import StrEnum
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
from typing import Any

import recorded_llm_extractor as rex
import relation_eval as reval
import model_deployment_receipt as mdr
from world_ir import canonical_json, content_id, sha256_text


PACKET_SCHEMA_VERSION = "hswm-h3-b3-arc-audit-packet/v1"
PACKET_SEAL_SCHEMA_VERSION = "hswm-h3-b3-arc-packet-seal/v1"
SCHEMA_VERSION = "hswm-h3-b3-arc-adjudication/v2"
RECEIPT_SCHEMA_VERSION = "hswm-h3-b3-arc-adjudication-receipt/v2"
ADJUDICATION_CLOSE_SCHEMA_VERSION = (
    "hswm-h3-b3-arc-adjudication-close/v1"
)
PRODUCER = "hswm-query-label-blind-qwen36-27b-arc-adjudicator/v2"
# The live DGX OpenAI-compatible endpoint advertises this served model ID;
# ``root`` is Qwen/Qwen3.6-27B.  Receipts bind the served ID because that is
# what the response envelope can verify without inference.
FROZEN_MODEL = "qwen3.6-27b"
FROZEN_MODEL_ID = "Qwen/Qwen3.6-27B"
FROZEN_MODEL_REVISION = "6a9e13bd6fc8f0983b9b99948120bc37f49c13e9"
FROZEN_PACKET_SEED = "HSWM-H3-B3-ARC-AUDIT-2026-07-20-v1"
DURABLE_OUTCOME_CLAIM = "one durable outcome per audit item"
EMPTY_FILE_SHA256 = hashlib.sha256(b"").hexdigest()

SYSTEM_PROMPT = """You are a query-label-blind entity-identity auditor.
Decide whether the highlighted mention in LEFT and RIGHT denotes the same
real-world entity using ONLY the two supplied titles and local excerpts. Do
not use outside knowledge, background memory, search, or unstated assumptions. The
same spelling alone is not evidence of identity. Choose SAME only when the
local contexts support one identity, DIFFERENT only when they support distinct
identities, and UNCLEAR whenever the local evidence is insufficient or
conflicting. Return exactly one JSON object and no prose or markdown. Its only
key is \"decision\" and its value is exactly \"SAME\", \"DIFFERENT\", or
\"UNCLEAR\"."""
USER_PROMPT_TEMPLATE = "PAIR_JSON={pair_json}"

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_PACKET_KEYS = frozenset({
    "schema_version", "seed", "dataset", "sampling_unit",
    "max_audit_units", "n_available_audit_units", "n_sampled",
    "evaluation_labels_included", "items", "packet_sha256",
})
_ITEM_KEYS = frozenset({
    "audit_item_id", "dataset", "join_entity_id", "normalized_surface",
    "source_claim_id", "target_claim_id", "source_predicate_exact",
    "target_predicate_exact", "source_role", "target_role", "left_context",
    "right_context",
})
_CONTEXT_KEYS = frozenset({
    "source_id", "title", "context_start", "context_end", "context_exact",
    "selector_start", "selector_end", "selector_exact",
    "selector_start_in_context", "selector_end_in_context",
    "source_text_sha256",
})
_PAIR_KEYS = frozenset({"left", "right"})
_PAIR_SIDE_KEYS = frozenset({
    "title", "excerpt", "mention_start", "mention_end", "mention_exact",
})
_ADJUDICATION_KEYS = frozenset({
    "schema_version", "packet_sha256", "adjudicator", "prompt_sha256",
    "config_sha256", "deployment_attestation_sha256", "judgments",
    "adjudication_sha256",
})
_JUDGMENT_KEYS = frozenset({
    "audit_item_id", "correct", "decision", "adjudicator", "receipt",
})
_PACKET_SEAL_KEYS = frozenset({
    "schema_version", "stage_run_id", "run_manifest_sha256",
    "certificate_transition_sha256", "fresh_artifact_seal_sha256",
    "packet_path", "packet_file_sha256", "packet_sha256", "n_items",
    "adjudication_config_sha256", "deployment_attestation_path",
    "deployment_attestation_file_sha256", "ledger_path", "output_path",
    "close_path", "ledger_device", "ledger_inode",
    "ledger_initial_sha256", "durable_outcome_claim", "packet_seal_sha256",
})
_ADJUDICATION_CLOSE_KEYS = frozenset({
    "schema_version", "stage_run_id", "packet_seal_sha256",
    "final_ledger_sha256", "adjudication_output_sha256",
    "adjudication_sha256", "n_items", "n_outcomes", "endpoint_calls",
    "cache_hits", "completed_request_ids", "ledger_device", "ledger_inode",
    "same_ledger_inode", "durable_outcome_claim",
    "adjudication_close_sha256",
})


class ArcDecision(StrEnum):
    SAME = "SAME"
    DIFFERENT = "DIFFERENT"
    UNCLEAR = "UNCLEAR"


class PacketIntegrityError(ValueError):
    """An audit packet is malformed, label-bearing, or not self-authenticating."""


class CacheCorruptionError(ValueError):
    """A complete cached receipt does not match its retained preimages."""


class AdjudicationIntegrityError(ValueError):
    """A completed adjudication does not bind its packet and receipts."""


class PacketSealIntegrityError(ValueError):
    """The committed packet, paths, ledger identity, or predecessors drifted."""


class AdjudicationCloseIntegrityError(ValueError):
    """A close receipt does not prove a complete sealed adjudication."""


@dataclass(frozen=True)
class ArcAdjudicatorConfigV1:
    endpoint: str
    deployment_attestation_sha256: str
    model: str = FROZEN_MODEL
    model_revision: str = FROZEN_MODEL_REVISION
    max_concurrency: int = 2
    timeout_seconds: float = 180.0
    max_tokens: int = 96
    temperature: int = 0
    top_p: float = 1.0
    seed: int = 0
    disable_thinking: bool = True
    response_format: str = "json_object"
    items_per_request: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.endpoint, str) or not self.endpoint.strip():
            raise ValueError("endpoint must be non-empty")
        if (
            not isinstance(self.deployment_attestation_sha256, str)
            or _SHA256_RE.fullmatch(self.deployment_attestation_sha256) is None
        ):
            raise ValueError(
                "deployment_attestation_sha256 must be a lower-case SHA-256"
            )
        if self.model != FROZEN_MODEL:
            raise ValueError(f"model is frozen at {FROZEN_MODEL}")
        if self.model_revision != FROZEN_MODEL_REVISION:
            raise ValueError("model_revision is not the preregistered revision")
        if not 1 <= self.max_concurrency <= 16:
            raise ValueError("max_concurrency must be in [1, 16]")
        if self.timeout_seconds <= 0 or self.max_tokens <= 0:
            raise ValueError("timeout_seconds and max_tokens must be positive")
        if self.temperature != 0 or self.seed != 0:
            raise ValueError("temperature and seed are frozen at zero")
        if self.top_p != 1.0:
            raise ValueError("top_p is frozen at 1.0")
        if not self.disable_thinking:
            raise ValueError("enable_thinking must remain false")
        if self.response_format != "json_object":
            raise ValueError("response_format must remain json_object")
        if self.items_per_request != 1:
            raise ValueError("exactly one audit item per request is required")


@dataclass(frozen=True)
class ArcAdjudicationReceiptV1:
    schema_version: str
    record_id: str
    packet_sha256: str
    audit_item_id: str
    producer: str
    producer_sha256: str
    adjudicator: str
    model: str
    model_revision: str
    deployment_attestation_sha256: str
    response_model: str
    finish_reason: str
    prompt_sha256: str
    config_json: str
    config_sha256: str
    request_id: str
    request_json: str
    request_sha256: str
    http_status: int | None
    raw_response: str
    raw_response_sha256: str
    response_content: str
    response_content_sha256: str
    output_json: str
    output_sha256: str
    usage_json: str
    latency_ms: int
    decision: ArcDecision
    error_json: str


@dataclass(frozen=True)
class ArcAdjudicationRunV1:
    adjudication: dict[str, Any]
    cache_hits: int
    endpoint_calls: int


Transport = Callable[
    [rex.OpenAIRequestV1],
    rex.TransportResponseV1 | str | Mapping[str, Any],
]


class _DuplicateJSONKey(ValueError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJSONKey(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _strict_json(text: str) -> Any:
    return json.loads(text, object_pairs_hook=_strict_object)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise PacketIntegrityError(f"{label} must be a lower-case SHA-256")
    return value


def _validate_context(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or frozenset(value) != _CONTEXT_KEYS:
        raise PacketIntegrityError(f"{label} has unexpected context keys")
    text_fields = (
        "source_id", "title", "context_exact", "selector_exact",
        "source_text_sha256",
    )
    if any(not isinstance(value[key], str) or not value[key] for key in text_fields):
        raise PacketIntegrityError(f"{label} context text fields must be non-empty")
    _require_sha256(value["source_text_sha256"], f"{label}.source_text_sha256")
    integer_fields = (
        "context_start", "context_end", "selector_start", "selector_end",
        "selector_start_in_context", "selector_end_in_context",
    )
    if any(not _is_int(value[key]) for key in integer_fields):
        raise PacketIntegrityError(f"{label} offsets must be integers")
    cs, ce = value["context_start"], value["context_end"]
    ss, se = value["selector_start"], value["selector_end"]
    rs, re_ = value["selector_start_in_context"], value["selector_end_in_context"]
    excerpt = value["context_exact"]
    if not (0 <= cs <= ss < se <= ce and ce - cs == len(excerpt)):
        raise PacketIntegrityError(f"{label} absolute offsets are inconsistent")
    if (rs, re_) != (ss - cs, se - cs):
        raise PacketIntegrityError(f"{label} relative offsets are inconsistent")
    if not (0 <= rs < re_ <= len(excerpt)):
        raise PacketIntegrityError(f"{label} selector is outside its excerpt")
    if excerpt[rs:re_] != value["selector_exact"]:
        raise PacketIntegrityError(f"{label} selector quote mismatch")
    return value


def validate_audit_packet(value: Any) -> dict[str, Any]:
    """Validate the exact packet schema, self-hash, and label-free contract."""

    if not isinstance(value, dict) or frozenset(value) != _PACKET_KEYS:
        raise PacketIntegrityError("audit packet root keys do not match v1")
    if value["schema_version"] != PACKET_SCHEMA_VERSION:
        raise PacketIntegrityError("unsupported audit packet schema")
    if value["seed"] != FROZEN_PACKET_SEED:
        raise PacketIntegrityError("audit packet seed is not preregistered")
    if value["dataset"] not in {"musique", "2wiki"}:
        raise PacketIntegrityError("audit packet dataset is unsupported")
    if value["sampling_unit"] != "unique emitted shared-join source pair":
        raise PacketIntegrityError("audit packet sampling unit changed")
    if value["evaluation_labels_included"] is not False:
        raise PacketIntegrityError("audit packet declares evaluation labels")
    for key in ("max_audit_units", "n_available_audit_units", "n_sampled"):
        if not _is_int(value[key]) or value[key] < 0:
            raise PacketIntegrityError(f"{key} must be a non-negative integer")
    if not 1 <= value["max_audit_units"] <= 100:
        raise PacketIntegrityError("max_audit_units must be in [1, 100]")
    if not isinstance(value["items"], list):
        raise PacketIntegrityError("items must be an array")
    if value["n_sampled"] != len(value["items"]):
        raise PacketIntegrityError("n_sampled does not match items")
    if value["n_sampled"] > min(
        value["n_available_audit_units"], value["max_audit_units"]
    ):
        raise PacketIntegrityError("sample count exceeds the declared population")

    item_ids: set[str] = set()
    audit_units: set[tuple[str, str, str]] = set()
    for index, item in enumerate(value["items"]):
        label = f"items[{index}]"
        if not isinstance(item, dict) or frozenset(item) != _ITEM_KEYS:
            raise PacketIntegrityError(f"{label} keys do not match v1")
        for key in _ITEM_KEYS - {"left_context", "right_context"}:
            if not isinstance(item[key], str) or not item[key]:
                raise PacketIntegrityError(f"{label}.{key} must be non-empty text")
        if item["dataset"] != value["dataset"]:
            raise PacketIntegrityError(f"{label} dataset mismatch")
        left = _validate_context(item["left_context"], f"{label}.left_context")
        right = _validate_context(item["right_context"], f"{label}.right_context")
        if left["source_id"] == right["source_id"]:
            raise PacketIntegrityError(f"{label} does not join two sources")
        item_payload = {key: item[key] for key in item if key != "audit_item_id"}
        expected_item_id = sha256_text(canonical_json(item_payload))
        if item["audit_item_id"] != expected_item_id:
            raise PacketIntegrityError(f"{label} audit_item_id mismatch")
        pair = tuple(sorted((left["source_id"], right["source_id"])))
        audit_unit = (item["join_entity_id"], pair[0], pair[1])
        if item["audit_item_id"] in item_ids or audit_unit in audit_units:
            raise PacketIntegrityError(
                "duplicate audit item or emitted shared-join source pair"
            )
        item_ids.add(item["audit_item_id"])
        audit_units.add(audit_unit)

    # This is a second, independently maintained fail-closed key scan.  Exact
    # schema checks above prevent an attacker from hiding labels under aliases.
    try:
        reval.assert_compiler_payload_clean(value)
    except reval.EvaluationLabelLeakageError as exc:
        raise PacketIntegrityError(str(exc)) from exc
    _require_sha256(value["packet_sha256"], "packet_sha256")
    body = {key: value[key] for key in value if key != "packet_sha256"}
    if value["packet_sha256"] != sha256_text(canonical_json(body)):
        raise PacketIntegrityError("audit packet self-hash mismatch")
    return value


def load_audit_packet(path: str | Path) -> dict[str, Any]:
    try:
        value = _strict_json(Path(path).read_text(encoding="utf-8"))
    except (_DuplicateJSONKey, json.JSONDecodeError, OSError) as exc:
        raise PacketIntegrityError(f"cannot read audit packet: {exc}") from exc
    return validate_audit_packet(value)


def prompt_sha256() -> str:
    return sha256_text(SYSTEM_PROMPT + "\n" + USER_PROMPT_TEMPLATE)


def _config_payload(config: ArcAdjudicatorConfigV1) -> dict[str, Any]:
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "endpoint": config.endpoint.rstrip("/"),
        "deployment_attestation_sha256": (
            config.deployment_attestation_sha256
        ),
        "model": config.model,
        "model_revision": config.model_revision,
        "max_concurrency": config.max_concurrency,
        "timeout_seconds": config.timeout_seconds,
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "top_p": config.top_p,
        "seed": config.seed,
        "disable_thinking": config.disable_thinking,
        "response_format": config.response_format,
        "items_per_request": config.items_per_request,
    }


def config_sha256(config: ArcAdjudicatorConfigV1) -> str:
    return sha256_text(canonical_json(_config_payload(config)))


def file_sha256(path: str | Path) -> str:
    """Hash the exact bytes of a regular file without canonicalizing JSON."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_deployment_attestation(
    path: str | Path,
    *,
    config: ArcAdjudicatorConfigV1 | None = None,
) -> dict[str, Any]:
    """Validate the receipt semantically, then bind it to runtime config."""

    try:
        receipt = mdr.load_deployment_receipt(path)
    except mdr.DeploymentAttestationError as exc:
        raise PacketSealIntegrityError(
            "deployment attestation is not a valid self-bound receipt"
        ) from exc
    snapshot = receipt["snapshot"]
    if (
        receipt["served_model"] != FROZEN_MODEL
        or snapshot["resolved_model_id"] != FROZEN_MODEL_ID
        or snapshot["resolved_revision"] != FROZEN_MODEL_REVISION
    ):
        raise PacketSealIntegrityError(
            "deployment attestation is not the frozen arc model/revision"
        )
    if config is not None and (
        receipt["endpoint"] != config.endpoint.rstrip("/")
        or receipt["served_model"] != config.model
        or snapshot["resolved_revision"] != config.model_revision
    ):
        raise PacketSealIntegrityError(
            "deployment attestation does not bind the runtime endpoint/model"
        )
    return receipt


def _existing_regular_path(
    path: str | Path,
    label: str,
    error_type: type[ValueError],
) -> Path:
    try:
        resolved = Path(path).resolve(strict=True)
        info = resolved.stat()
    except OSError as exc:
        raise error_type(f"{label} is not an existing file: {exc}") from exc
    if not stat.S_ISREG(info.st_mode):
        raise error_type(f"{label} is not a regular file")
    return resolved


def _planned_canonical_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _seal_self_hash(value: Mapping[str, Any], hash_key: str) -> str:
    return sha256_text(canonical_json({
        key: value[key] for key in value if key != hash_key
    }))


def validate_packet_seal(value: Any) -> dict[str, Any]:
    """Validate a packet seal and every file/path commitment it carries.

    The ledger may be non-empty after adjudication starts, but it must still be
    the same filesystem object that was exclusively created empty at seal time.
    """

    if not isinstance(value, dict) or frozenset(value) != _PACKET_SEAL_KEYS:
        raise PacketSealIntegrityError("packet seal root keys do not match v1")
    if value["schema_version"] != PACKET_SEAL_SCHEMA_VERSION:
        raise PacketSealIntegrityError("packet seal schema mismatch")
    if (
        not isinstance(value["stage_run_id"], str)
        or not value["stage_run_id"].strip()
        or value["stage_run_id"] != value["stage_run_id"].strip()
    ):
        raise PacketSealIntegrityError("stage_run_id must be non-empty canonical text")
    for key in (
        "run_manifest_sha256", "certificate_transition_sha256",
        "fresh_artifact_seal_sha256", "packet_file_sha256", "packet_sha256",
        "adjudication_config_sha256",
        "deployment_attestation_file_sha256", "ledger_initial_sha256",
        "packet_seal_sha256",
    ):
        if not isinstance(value[key], str) or _SHA256_RE.fullmatch(value[key]) is None:
            raise PacketSealIntegrityError(f"{key} must be a lower-case SHA-256")
    if value["ledger_initial_sha256"] != EMPTY_FILE_SHA256:
        raise PacketSealIntegrityError("ledger was not committed as an empty file")
    if value["durable_outcome_claim"] != DURABLE_OUTCOME_CLAIM:
        raise PacketSealIntegrityError("durable outcome claim changed")
    if value["packet_seal_sha256"] != _seal_self_hash(
        value, "packet_seal_sha256",
    ):
        raise PacketSealIntegrityError("packet seal self-hash mismatch")
    if not _is_int(value["n_items"]) or value["n_items"] < 0:
        raise PacketSealIntegrityError("n_items must be a non-negative integer")
    for key in ("ledger_device", "ledger_inode"):
        if not _is_int(value[key]) or value[key] < 0:
            raise PacketSealIntegrityError(f"{key} must be a non-negative integer")

    packet_path = _existing_regular_path(
        value["packet_path"], "sealed packet", PacketSealIntegrityError,
    )
    attestation_path = _existing_regular_path(
        value["deployment_attestation_path"], "deployment attestation",
        PacketSealIntegrityError,
    )
    ledger_path = _existing_regular_path(
        value["ledger_path"], "adjudication ledger", PacketSealIntegrityError,
    )
    output_path = _planned_canonical_path(value["output_path"])
    close_path = _planned_canonical_path(value["close_path"])
    canonical_paths = {
        "packet_path": packet_path,
        "deployment_attestation_path": attestation_path,
        "ledger_path": ledger_path,
        "output_path": output_path,
        "close_path": close_path,
    }
    for key, resolved in canonical_paths.items():
        if value[key] != str(resolved):
            raise PacketSealIntegrityError(f"{key} is not its canonical exact path")
    if len({str(path) for path in canonical_paths.values()}) != len(canonical_paths):
        raise PacketSealIntegrityError("sealed artifact paths must be distinct")
    if file_sha256(packet_path) != value["packet_file_sha256"]:
        raise PacketSealIntegrityError("sealed packet file hash mismatch")
    if file_sha256(attestation_path) != value[
        "deployment_attestation_file_sha256"
    ]:
        raise PacketSealIntegrityError("deployment attestation file hash mismatch")
    _validate_deployment_attestation(attestation_path)
    try:
        packet = load_audit_packet(packet_path)
    except PacketIntegrityError as exc:
        raise PacketSealIntegrityError("sealed packet is invalid") from exc
    if (
        packet["packet_sha256"] != value["packet_sha256"]
        or len(packet["items"]) != value["n_items"]
    ):
        raise PacketSealIntegrityError("packet identity/count differs from seal")
    ledger_info = ledger_path.stat()
    if (
        ledger_info.st_dev != value["ledger_device"]
        or ledger_info.st_ino != value["ledger_inode"]
    ):
        raise PacketSealIntegrityError("adjudication ledger inode changed")
    return value


def load_packet_seal(path: str | Path) -> dict[str, Any]:
    """Strictly load and validate a committed packet seal."""

    try:
        value = _strict_json(Path(path).read_text(encoding="utf-8"))
    except (_DuplicateJSONKey, json.JSONDecodeError, OSError) as exc:
        raise PacketSealIntegrityError(f"cannot read packet seal: {exc}") from exc
    return validate_packet_seal(value)


def create_packet_seal(
    *,
    seal_path: str | Path,
    stage_run_id: str,
    run_manifest_sha256: str,
    certificate_transition_sha256: str,
    fresh_artifact_seal_sha256: str,
    packet_path: str | Path,
    config: ArcAdjudicatorConfigV1,
    deployment_attestation_path: str | Path,
    ledger_path: str | Path,
    output_path: str | Path,
    close_path: str | Path,
) -> dict[str, Any]:
    """Commit one query-blind packet and an exclusively empty audit ledger.

    The caller must supply paths before any model call.  If seal publication
    fails after the empty ledger is created, the orphan ledger is deliberately
    left in place so a later run cannot silently reuse that path.
    """

    if not isinstance(stage_run_id, str) or not stage_run_id.strip():
        raise ValueError("stage_run_id must be non-empty")
    stage_run_id = stage_run_id.strip()
    for label, value in (
        ("run_manifest_sha256", run_manifest_sha256),
        ("certificate_transition_sha256", certificate_transition_sha256),
        ("fresh_artifact_seal_sha256", fresh_artifact_seal_sha256),
    ):
        if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
            raise ValueError(f"{label} must be a lower-case SHA-256")

    packet_file = _existing_regular_path(
        packet_path, "packet", PacketSealIntegrityError,
    )
    attestation_file = _existing_regular_path(
        deployment_attestation_path, "deployment attestation",
        PacketSealIntegrityError,
    )
    packet = load_audit_packet(packet_file)
    _validate_deployment_attestation(attestation_file, config=config)
    attestation_sha = file_sha256(attestation_file)
    if attestation_sha != config.deployment_attestation_sha256:
        raise PacketSealIntegrityError(
            "config does not bind the supplied deployment attestation file"
        )

    seal_file = _planned_canonical_path(seal_path)
    ledger_file = _planned_canonical_path(ledger_path)
    output_file = _planned_canonical_path(output_path)
    close_file = _planned_canonical_path(close_path)
    for path in (seal_file, ledger_file, output_file, close_file):
        path.parent.mkdir(parents=True, exist_ok=True)
    committed_paths = (
        seal_file, packet_file, attestation_file, ledger_file, output_file,
        close_file,
    )
    if len({str(path) for path in committed_paths}) != len(committed_paths):
        raise PacketSealIntegrityError("packet-seal artifact paths must be distinct")
    for label, path in (
        ("packet seal", seal_file), ("ledger", ledger_file),
        ("adjudication output", output_file), ("close receipt", close_file),
    ):
        if path.exists():
            raise FileExistsError(f"{label} path already exists: {path}")

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(ledger_file, flags, 0o600)
    try:
        os.fsync(fd)
        ledger_info = os.fstat(fd)
    finally:
        os.close(fd)
    if not stat.S_ISREG(ledger_info.st_mode):  # pragma: no cover - OS guard
        raise PacketSealIntegrityError("exclusive ledger is not a regular file")
    _fsync_parent(ledger_file)
    # Recheck the two future artifacts immediately before publishing the seal;
    # neither may be selected from a prior or concurrent adjudication.
    for label, path in (
        ("adjudication output", output_file), ("close receipt", close_file),
    ):
        if path.exists():
            raise FileExistsError(f"{label} path appeared before sealing: {path}")
    current_ledger_info = ledger_file.stat()
    if (
        file_sha256(ledger_file) != EMPTY_FILE_SHA256
        or current_ledger_info.st_dev != ledger_info.st_dev
        or current_ledger_info.st_ino != ledger_info.st_ino
    ):
        raise PacketSealIntegrityError(
            "exclusive ledger changed before packet seal publication"
        )

    body = {
        "schema_version": PACKET_SEAL_SCHEMA_VERSION,
        "stage_run_id": stage_run_id,
        "run_manifest_sha256": run_manifest_sha256,
        "certificate_transition_sha256": certificate_transition_sha256,
        "fresh_artifact_seal_sha256": fresh_artifact_seal_sha256,
        "packet_path": str(packet_file),
        "packet_file_sha256": file_sha256(packet_file),
        "packet_sha256": packet["packet_sha256"],
        "n_items": len(packet["items"]),
        "adjudication_config_sha256": config_sha256(config),
        "deployment_attestation_path": str(attestation_file),
        "deployment_attestation_file_sha256": attestation_sha,
        "ledger_path": str(ledger_file),
        "output_path": str(output_file),
        "close_path": str(close_file),
        "ledger_device": ledger_info.st_dev,
        "ledger_inode": ledger_info.st_ino,
        "ledger_initial_sha256": EMPTY_FILE_SHA256,
        "durable_outcome_claim": DURABLE_OUTCOME_CLAIM,
    }
    seal = {
        **body,
        "packet_seal_sha256": sha256_text(canonical_json(body)),
    }
    _write_exclusive(seal_file, seal)
    loaded = load_packet_seal(seal_file)
    if loaded != seal:  # pragma: no cover - canonical writer invariant
        raise PacketSealIntegrityError("published packet seal changed")
    return loaded


def _local_pair(item: Mapping[str, Any]) -> dict[str, Any]:
    def side(context: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "title": context["title"],
            "excerpt": context["context_exact"],
            "mention_start": context["selector_start_in_context"],
            "mention_end": context["selector_end_in_context"],
            "mention_exact": context["selector_exact"],
        }

    pair = {"left": side(item["left_context"]), "right": side(item["right_context"])}
    reval.assert_compiler_payload_clean(pair)
    return pair


def _validate_local_pair(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or frozenset(value) != _PAIR_KEYS:
        raise CacheCorruptionError("request pair root is not local-context v1")
    for side_name in ("left", "right"):
        side = value[side_name]
        if not isinstance(side, dict) or frozenset(side) != _PAIR_SIDE_KEYS:
            raise CacheCorruptionError("request pair side has unexpected keys")
        if any(not isinstance(side[key], str) or not side[key]
               for key in ("title", "excerpt", "mention_exact")):
            raise CacheCorruptionError("request pair text fields must be non-empty")
        start, end = side["mention_start"], side["mention_end"]
        if not _is_int(start) or not _is_int(end):
            raise CacheCorruptionError("request pair offsets must be integers")
        if not 0 <= start < end <= len(side["excerpt"]):
            raise CacheCorruptionError("request pair selector is outside excerpt")
        if side["excerpt"][start:end] != side["mention_exact"]:
            raise CacheCorruptionError("request pair selector quote mismatch")
    try:
        reval.assert_compiler_payload_clean(value)
    except reval.EvaluationLabelLeakageError as exc:
        raise CacheCorruptionError(str(exc)) from exc
    return value


def make_openai_request(
    item: Mapping[str, Any],
    *,
    packet_sha256: str,
    config: ArcAdjudicatorConfigV1,
) -> rex.OpenAIRequestV1:
    """Build exactly one frozen request from local contexts only."""

    pair_json = canonical_json(_local_pair(item))
    body: dict[str, Any] = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_PROMPT_TEMPLATE.format(pair_json=pair_json),
            },
        ],
        "temperature": 0,
        "top_p": 1.0,
        "seed": 0,
        "max_tokens": config.max_tokens,
        "response_format": {"type": "json_object"},
        "chat_template_kwargs": {"enable_thinking": False},
    }
    request_sha = sha256_text(canonical_json(body))
    request_id = content_id("h3_b3_arc_adjudication_request", {
        "packet_sha256": packet_sha256,
        "audit_item_id": item["audit_item_id"],
        "prompt_sha256": prompt_sha256(),
        "config_sha256": config_sha256(config),
        "request_sha256": request_sha,
    })
    return rex.OpenAIRequestV1(
        request_id=request_id,
        endpoint=config.endpoint,
        body=body,
        timeout_seconds=config.timeout_seconds,
    )


def _coerce_transport_response(
    value: rex.TransportResponseV1 | str | Mapping[str, Any],
) -> rex.TransportResponseV1:
    if isinstance(value, rex.TransportResponseV1):
        return value
    if isinstance(value, str):
        return rex.TransportResponseV1(raw_response=value)
    if isinstance(value, Mapping):
        return rex.TransportResponseV1(raw_response=canonical_json(dict(value)))
    raise TypeError("transport must return a response, string, or mapping")


def _extract_envelope(
    raw_response: str,
) -> tuple[str, str, str, str, str | None]:
    """Replay one OpenAI envelope and admit only a completed generation.

    ``finish_reason`` is retained even on refusal so the receipt proves why a
    syntactically valid but truncated/content-filtered answer counted as
    ``UNCLEAR``.  Only exact ``stop`` can reach the decision parser.
    """

    try:
        envelope = _strict_json(raw_response)
    except (_DuplicateJSONKey, json.JSONDecodeError, TypeError, ValueError) as exc:
        return (
            "", "", "", canonical_json({}),
            f"{type(exc).__name__}: invalid envelope",
        )
    if not isinstance(envelope, dict):
        return (
            "", "", "", canonical_json({}),
            "TypeError: envelope is not an object",
        )
    usage = envelope.get("usage", {})
    try:
        usage_json = canonical_json(usage)
    except (TypeError, ValueError):
        usage_json = canonical_json({})
    choices = envelope.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        return "", "", "", usage_json, "ValueError: expected exactly one choice"
    choice = choices[0]
    message = choice.get("message") if isinstance(choice, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    raw_finish_reason = (
        choice.get("finish_reason") if isinstance(choice, dict) else None
    )
    finish_reason = (
        raw_finish_reason if isinstance(raw_finish_reason, str) else ""
    )
    if not isinstance(content, str):
        return (
            "", "", finish_reason, usage_json,
            "TypeError: choice.message.content is not text",
        )
    response_model = envelope.get("model", "")
    if not isinstance(response_model, str):
        response_model = ""
    if raw_finish_reason != "stop":
        return (
            content, response_model, finish_reason, usage_json,
            "ValueError: choice.finish_reason must be exact 'stop'",
        )
    return content, response_model, finish_reason, usage_json, None


def _parse_decision(content: str) -> tuple[ArcDecision, str | None]:
    try:
        payload = _strict_json(content)
    except (_DuplicateJSONKey, json.JSONDecodeError, TypeError, ValueError) as exc:
        return ArcDecision.UNCLEAR, f"{type(exc).__name__}: invalid decision JSON"
    if not isinstance(payload, dict) or frozenset(payload) != {"decision"}:
        return ArcDecision.UNCLEAR, "ValueError: decision object must have one key"
    try:
        return ArcDecision(payload["decision"]), None
    except (TypeError, ValueError):
        return ArcDecision.UNCLEAR, "ValueError: decision is outside frozen enum"


def _error_json(error_type: str | None, detail: str | None = None) -> str:
    if error_type is None:
        return canonical_json({})
    return canonical_json({
        "type": error_type,
        "detail": detail or "adjudication failed closed",
    })


def _adjudicator(config: ArcAdjudicatorConfigV1) -> str:
    return f"{config.model}@{config.model_revision}"


def _record_id(record: ArcAdjudicationReceiptV1) -> str:
    return content_id("h3_b3_arc_adjudication_receipt", {
        "packet_sha256": record.packet_sha256,
        "audit_item_id": record.audit_item_id,
        "producer_sha256": record.producer_sha256,
        "adjudicator": record.adjudicator,
        "model": record.model,
        "model_revision": record.model_revision,
        "deployment_attestation_sha256": (
            record.deployment_attestation_sha256
        ),
        "response_model": record.response_model,
        "finish_reason": record.finish_reason,
        "prompt_sha256": record.prompt_sha256,
        "config_sha256": record.config_sha256,
        "request_id": record.request_id,
        "request_sha256": record.request_sha256,
        "http_status": record.http_status,
        "raw_response_sha256": record.raw_response_sha256,
        "response_content_sha256": record.response_content_sha256,
        "output_sha256": record.output_sha256,
        "usage_sha256": sha256_text(record.usage_json),
        "latency_ms": record.latency_ms,
        "decision": record.decision.value,
        "error_sha256": sha256_text(record.error_json),
    })


def _make_receipt(
    item: Mapping[str, Any],
    packet_sha256: str,
    config: ArcAdjudicatorConfigV1,
    request: rex.OpenAIRequestV1,
    *,
    http_status: int | None,
    raw_response: str,
    response_content: str,
    response_model: str,
    finish_reason: str,
    usage_json: str,
    latency_ms: int,
    decision: ArcDecision,
    error_json: str,
) -> ArcAdjudicationReceiptV1:
    output_json = canonical_json({"decision": decision.value})
    config_json = canonical_json(_config_payload(config))
    request_json = canonical_json(request.body)
    provisional = ArcAdjudicationReceiptV1(
        schema_version=RECEIPT_SCHEMA_VERSION,
        record_id="",
        packet_sha256=packet_sha256,
        audit_item_id=str(item["audit_item_id"]),
        producer=PRODUCER,
        producer_sha256=sha256_text(PRODUCER),
        adjudicator=_adjudicator(config),
        model=config.model,
        model_revision=config.model_revision,
        deployment_attestation_sha256=(
            config.deployment_attestation_sha256
        ),
        response_model=response_model,
        finish_reason=finish_reason,
        prompt_sha256=prompt_sha256(),
        config_json=config_json,
        config_sha256=sha256_text(config_json),
        request_id=request.request_id,
        request_json=request_json,
        request_sha256=sha256_text(request_json),
        http_status=http_status,
        raw_response=raw_response,
        raw_response_sha256=sha256_text(raw_response),
        response_content=response_content,
        response_content_sha256=sha256_text(response_content),
        output_json=output_json,
        output_sha256=sha256_text(output_json),
        usage_json=usage_json,
        latency_ms=max(0, int(latency_ms)),
        decision=decision,
        error_json=error_json,
    )
    return replace(provisional, record_id=_record_id(provisional))


def adjudicate_item(
    item: Mapping[str, Any],
    *,
    packet_sha256: str,
    config: ArcAdjudicatorConfigV1,
    transport: Transport,
) -> ArcAdjudicationReceiptV1:
    """Perform one attempt; all boundary failures become durable UNCLEAR."""

    request = make_openai_request(
        item, packet_sha256=packet_sha256, config=config,
    )
    started = time.perf_counter_ns()
    try:
        response = _coerce_transport_response(transport(request))
    except Exception as exc:
        latency_ms = (time.perf_counter_ns() - started) // 1_000_000
        return _make_receipt(
            item, packet_sha256, config, request, http_status=None,
            raw_response="", response_content="", response_model="",
            finish_reason="",
            usage_json=canonical_json({}), latency_ms=latency_ms,
            decision=ArcDecision.UNCLEAR,
            error_json=_error_json(type(exc).__name__, "transport call failed"),
        )

    latency_ms = (time.perf_counter_ns() - started) // 1_000_000
    raw_response = response.raw_response
    if not 200 <= response.http_status < 300:
        return _make_receipt(
            item, packet_sha256, config, request,
            http_status=response.http_status, raw_response=raw_response,
            response_content="", response_model="", finish_reason="",
            usage_json=canonical_json({}),
            latency_ms=latency_ms, decision=ArcDecision.UNCLEAR,
            error_json=_error_json(
                "HTTPStatusError", f"non-success HTTP status {response.http_status}",
            ),
        )

    content, response_model, finish_reason, usage_json, envelope_error = (
        _extract_envelope(raw_response)
    )
    if envelope_error is not None:
        return _make_receipt(
            item, packet_sha256, config, request,
            http_status=response.http_status, raw_response=raw_response,
            response_content=content, response_model=response_model,
            finish_reason=finish_reason,
            usage_json=usage_json, latency_ms=latency_ms,
            decision=ArcDecision.UNCLEAR,
            error_json=_error_json("InvalidOpenAIResponse", envelope_error),
        )
    if response_model != config.model:
        return _make_receipt(
            item, packet_sha256, config, request,
            http_status=response.http_status, raw_response=raw_response,
            response_content=content, response_model=response_model,
            finish_reason=finish_reason,
            usage_json=usage_json, latency_ms=latency_ms,
            decision=ArcDecision.UNCLEAR,
            error_json=_error_json("ModelMismatch", "response model changed"),
        )
    decision, decision_error = _parse_decision(content)
    return _make_receipt(
        item, packet_sha256, config, request,
        http_status=response.http_status, raw_response=raw_response,
        response_content=content, response_model=response_model,
        finish_reason=finish_reason,
        usage_json=usage_json, latency_ms=latency_ms, decision=decision,
        error_json=(
            _error_json("InvalidDecision", decision_error)
            if decision_error is not None else _error_json(None)
        ),
    )


def _validate_config_preimage(record: ArcAdjudicationReceiptV1) -> dict[str, Any]:
    try:
        value = _strict_json(record.config_json)
    except (_DuplicateJSONKey, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise CacheCorruptionError("receipt config_json is invalid") from exc
    if canonical_json(value) != record.config_json:
        raise CacheCorruptionError("receipt config_json is not canonical")
    if sha256_text(record.config_json) != record.config_sha256:
        raise CacheCorruptionError("receipt config hash mismatch")
    expected_keys = frozenset(_config_payload(ArcAdjudicatorConfigV1(
        endpoint="fixture.invalid", deployment_attestation_sha256="0" * 64,
    )))
    if not isinstance(value, dict) or frozenset(value) != expected_keys:
        raise CacheCorruptionError("receipt config keys do not match v1")
    try:
        reconstructed = ArcAdjudicatorConfigV1(
            endpoint=value["endpoint"],
            deployment_attestation_sha256=value[
                "deployment_attestation_sha256"
            ],
            model=value["model"],
            model_revision=value["model_revision"],
            max_concurrency=value["max_concurrency"],
            timeout_seconds=value["timeout_seconds"],
            max_tokens=value["max_tokens"], temperature=value["temperature"],
            top_p=value["top_p"], seed=value["seed"],
            disable_thinking=value["disable_thinking"],
            response_format=value["response_format"],
            items_per_request=value["items_per_request"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CacheCorruptionError("receipt config violates frozen policy") from exc
    if value != _config_payload(reconstructed):
        raise CacheCorruptionError("receipt config preimage changed")
    if (
        record.model != reconstructed.model
        or record.model_revision != reconstructed.model_revision
        or record.deployment_attestation_sha256
        != reconstructed.deployment_attestation_sha256
    ):
        raise CacheCorruptionError(
            "receipt model/deployment attestation does not match config"
        )
    return value


def _validate_request_preimage(
    record: ArcAdjudicationReceiptV1, config_value: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        body = _strict_json(record.request_json)
    except (_DuplicateJSONKey, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise CacheCorruptionError("receipt request_json is invalid") from exc
    if canonical_json(body) != record.request_json:
        raise CacheCorruptionError("receipt request_json is not canonical")
    if sha256_text(record.request_json) != record.request_sha256:
        raise CacheCorruptionError("receipt request hash mismatch")
    expected_keys = {
        "model", "messages", "temperature", "top_p", "seed", "max_tokens",
        "response_format", "chat_template_kwargs",
    }
    if not isinstance(body, dict) or set(body) != expected_keys:
        raise CacheCorruptionError("receipt request body keys changed")
    if (
        body["model"] != config_value["model"]
        or body["temperature"] != 0
        or body["top_p"] != 1.0
        or body["seed"] != 0
        or body["max_tokens"] != config_value["max_tokens"]
        or body["response_format"] != {"type": "json_object"}
        or body["chat_template_kwargs"] != {"enable_thinking": False}
    ):
        raise CacheCorruptionError("receipt request decoding policy changed")
    messages = body["messages"]
    if not isinstance(messages, list) or len(messages) != 2:
        raise CacheCorruptionError("receipt request must contain two messages")
    if messages[0] != {"role": "system", "content": SYSTEM_PROMPT}:
        raise CacheCorruptionError("receipt system prompt changed")
    user = messages[1]
    prefix = "PAIR_JSON="
    if (
        not isinstance(user, dict) or set(user) != {"role", "content"}
        or user.get("role") != "user"
        or not isinstance(user.get("content"), str)
        or not user["content"].startswith(prefix)
    ):
        raise CacheCorruptionError("receipt user prompt changed")
    try:
        pair = _strict_json(user["content"][len(prefix):])
    except (_DuplicateJSONKey, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise CacheCorruptionError("receipt local pair JSON is invalid") from exc
    _validate_local_pair(pair)
    if user["content"] != USER_PROMPT_TEMPLATE.format(pair_json=canonical_json(pair)):
        raise CacheCorruptionError("receipt local pair JSON is not canonical")
    expected_request_id = content_id("h3_b3_arc_adjudication_request", {
        "packet_sha256": record.packet_sha256,
        "audit_item_id": record.audit_item_id,
        "prompt_sha256": record.prompt_sha256,
        "config_sha256": record.config_sha256,
        "request_sha256": record.request_sha256,
    })
    if record.request_id != expected_request_id:
        raise CacheCorruptionError("receipt request identity mismatch")
    return body


def _validate_receipt_preimages(record: ArcAdjudicationReceiptV1) -> None:
    if record.schema_version != RECEIPT_SCHEMA_VERSION:
        raise CacheCorruptionError("receipt schema mismatch")
    if not _SHA256_RE.fullmatch(record.packet_sha256):
        raise CacheCorruptionError("receipt packet hash is invalid")
    if record.producer != PRODUCER or record.producer_sha256 != sha256_text(PRODUCER):
        raise CacheCorruptionError("receipt producer mismatch")
    if record.prompt_sha256 != prompt_sha256():
        raise CacheCorruptionError("receipt prompt hash mismatch")
    if record.adjudicator != f"{record.model}@{record.model_revision}":
        raise CacheCorruptionError("receipt adjudicator identity mismatch")
    if _SHA256_RE.fullmatch(record.deployment_attestation_sha256) is None:
        raise CacheCorruptionError("receipt deployment attestation hash is invalid")
    config_value = _validate_config_preimage(record)
    _validate_request_preimage(record, config_value)
    if record.latency_ms < 0:
        raise CacheCorruptionError("receipt latency must be non-negative")
    if record.http_status is not None and not _is_int(record.http_status):
        raise CacheCorruptionError("receipt HTTP status must be integer or null")
    if record.raw_response_sha256 != sha256_text(record.raw_response):
        raise CacheCorruptionError("receipt raw response hash mismatch")
    if record.response_content_sha256 != sha256_text(record.response_content):
        raise CacheCorruptionError("receipt response content hash mismatch")
    if record.output_sha256 != sha256_text(record.output_json):
        raise CacheCorruptionError("receipt output hash mismatch")
    try:
        output = _strict_json(record.output_json)
        usage = _strict_json(record.usage_json)
        error = _strict_json(record.error_json)
    except (_DuplicateJSONKey, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise CacheCorruptionError("receipt output/usage/error JSON is invalid") from exc
    if canonical_json(output) != record.output_json or output != {"decision": record.decision.value}:
        raise CacheCorruptionError("receipt output preimage mismatch")
    if canonical_json(usage) != record.usage_json:
        raise CacheCorruptionError("receipt usage_json is not canonical")
    if canonical_json(error) != record.error_json:
        raise CacheCorruptionError("receipt error_json is not canonical")
    if error and (not isinstance(error, dict) or set(error) != {"type", "detail"}):
        raise CacheCorruptionError("receipt error schema mismatch")

    if record.http_status is None:
        if (
            record.raw_response or record.response_content
            or record.response_model or record.finish_reason or usage != {}
        ):
            raise CacheCorruptionError("transport-failure receipt retained impossible response data")
        if record.decision != ArcDecision.UNCLEAR or not error:
            raise CacheCorruptionError("transport failure must fail closed")
    elif not 200 <= record.http_status < 300:
        if (
            record.response_content or record.response_model
            or record.finish_reason or usage != {}
        ):
            raise CacheCorruptionError("HTTP-failure receipt retained parsed response data")
        if record.decision != ArcDecision.UNCLEAR or not error:
            raise CacheCorruptionError("HTTP failure must fail closed")
    else:
        (
            content, response_model, finish_reason, envelope_usage,
            envelope_error,
        ) = _extract_envelope(record.raw_response)
        if (
            content != record.response_content
            or response_model != record.response_model
            or finish_reason != record.finish_reason
            or envelope_usage != record.usage_json
        ):
            raise CacheCorruptionError("receipt response envelope preimage mismatch")
        if envelope_error is not None:
            if record.decision != ArcDecision.UNCLEAR or not error:
                raise CacheCorruptionError("invalid envelope must fail closed")
        elif response_model != record.model:
            if record.decision != ArcDecision.UNCLEAR or not error:
                raise CacheCorruptionError("model mismatch must fail closed")
        else:
            parsed_decision, decision_error = _parse_decision(content)
            if parsed_decision != record.decision:
                raise CacheCorruptionError("receipt decision differs from raw response")
            if decision_error is None and error:
                raise CacheCorruptionError("valid response has a spurious error")
            if decision_error is not None and (
                record.decision != ArcDecision.UNCLEAR or not error
            ):
                raise CacheCorruptionError("invalid decision must fail closed")
    if record.record_id != _record_id(record):
        raise CacheCorruptionError("receipt identity mismatch")


def _receipt_from_dict(value: Any) -> ArcAdjudicationReceiptV1:
    if not isinstance(value, dict):
        raise CacheCorruptionError("receipt must be an object")
    expected = {field.name for field in fields(ArcAdjudicationReceiptV1)}
    if set(value) != expected:
        raise CacheCorruptionError("receipt keys do not match v1")
    try:
        record = ArcAdjudicationReceiptV1(
            **{**value, "decision": ArcDecision(value["decision"])}
        )
    except (TypeError, ValueError) as exc:
        raise CacheCorruptionError("receipt fields are invalid") from exc
    _validate_receipt_preimages(record)
    return record


class JSONLArcAdjudicationCache:
    """Append-safe, first-write-wins cache keyed by deterministic request ID."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _open_locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        return handle

    @staticmethod
    def _repair_tail(handle) -> bytes:
        handle.seek(0)
        data = handle.read()
        if data and not data.endswith(b"\n"):
            last_newline = data.rfind(b"\n")
            valid_length = last_newline + 1 if last_newline >= 0 else 0
            handle.seek(valid_length)
            handle.truncate()
            handle.flush()
            os.fsync(handle.fileno())
            data = data[:valid_length]
        return data

    @staticmethod
    def _decode(data: bytes) -> tuple[ArcAdjudicationReceiptV1, ...]:
        records: list[ArcAdjudicationReceiptV1] = []
        by_request: dict[str, str] = {}
        by_packet_item: dict[tuple[str, str], str] = {}
        for line_number, line in enumerate(data.splitlines(), 1):
            if not line:
                continue
            try:
                value = _strict_json(line.decode("utf-8"))
                record = _receipt_from_dict(value)
            except (UnicodeDecodeError, _DuplicateJSONKey, json.JSONDecodeError,
                    CacheCorruptionError) as exc:
                raise CacheCorruptionError(
                    f"invalid complete JSONL line {line_number}: {exc}"
                ) from exc
            old = by_request.get(record.request_id)
            if old is not None and old != record.record_id:
                raise CacheCorruptionError("multiple outcomes for one request")
            if old is not None:
                raise CacheCorruptionError("duplicate completed request in cache")
            by_request[record.request_id] = record.record_id
            packet_item = (record.packet_sha256, record.audit_item_id)
            old_item = by_packet_item.get(packet_item)
            if old_item is not None and old_item != record.record_id:
                raise CacheCorruptionError("multiple outcomes for one audit item")
            if old_item is not None:
                raise CacheCorruptionError("duplicate completed audit item in cache")
            by_packet_item[packet_item] = record.record_id
            records.append(record)
        return tuple(records)

    def records(self) -> tuple[ArcAdjudicationReceiptV1, ...]:
        handle = self._open_locked()
        try:
            return self._decode(self._repair_tail(handle))
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()

    def append(self, record: ArcAdjudicationReceiptV1) -> bool:
        _validate_receipt_preimages(record)
        handle = self._open_locked()
        try:
            existing = self._decode(self._repair_tail(handle))
            if any(
                item.request_id == record.request_id
                or (
                    item.packet_sha256 == record.packet_sha256
                    and item.audit_item_id == record.audit_item_id
                )
                for item in existing
            ):
                return False
            handle.seek(0, os.SEEK_END)
            handle.write((canonical_json(record) + "\n").encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
            return True
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()


def _validate_cached_request(
    record: ArcAdjudicationReceiptV1,
    item: Mapping[str, Any],
    packet_sha256: str,
    config: ArcAdjudicatorConfigV1,
) -> None:
    request = make_openai_request(
        item, packet_sha256=packet_sha256, config=config,
    )
    if (
        record.packet_sha256 != packet_sha256
        or record.audit_item_id != item["audit_item_id"]
        or record.request_id != request.request_id
        or record.request_json != canonical_json(request.body)
    ):
        raise CacheCorruptionError("cached receipt does not bind requested audit item")


def _build_adjudication(
    packet: Mapping[str, Any],
    config: ArcAdjudicatorConfigV1,
    receipts: Sequence[ArcAdjudicationReceiptV1],
) -> dict[str, Any]:
    judgments = [
        {
            "audit_item_id": record.audit_item_id,
            "correct": record.decision == ArcDecision.SAME,
            "decision": record.decision.value,
            "adjudicator": record.adjudicator,
            "receipt": asdict(record),
        }
        for record in receipts
    ]
    body = {
        "schema_version": SCHEMA_VERSION,
        "packet_sha256": packet["packet_sha256"],
        "adjudicator": _adjudicator(config),
        "prompt_sha256": prompt_sha256(),
        "config_sha256": config_sha256(config),
        "deployment_attestation_sha256": (
            config.deployment_attestation_sha256
        ),
        "judgments": judgments,
    }
    return {
        **body,
        "adjudication_sha256": sha256_text(canonical_json(body)),
    }


def validate_adjudication(value: Any, packet: Mapping[str, Any]) -> dict[str, Any]:
    """Verify an output artifact and every embedded receipt preimage."""

    packet = validate_audit_packet(dict(packet))
    if not isinstance(value, dict) or frozenset(value) != _ADJUDICATION_KEYS:
        raise AdjudicationIntegrityError("adjudication root keys do not match v1")
    if value["schema_version"] != SCHEMA_VERSION:
        raise AdjudicationIntegrityError("adjudication schema mismatch")
    if value["packet_sha256"] != packet["packet_sha256"]:
        raise AdjudicationIntegrityError("adjudication packet binding mismatch")
    if _SHA256_RE.fullmatch(value["deployment_attestation_sha256"]) is None:
        raise AdjudicationIntegrityError(
            "adjudication deployment attestation hash is invalid"
        )
    body = {key: value[key] for key in value if key != "adjudication_sha256"}
    if value["adjudication_sha256"] != sha256_text(canonical_json(body)):
        raise AdjudicationIntegrityError("adjudication self-hash mismatch")
    judgments = value["judgments"]
    if not isinstance(judgments, list) or len(judgments) != len(packet["items"]):
        raise AdjudicationIntegrityError("adjudication judgment count mismatch")
    expected_ids = [item["audit_item_id"] for item in packet["items"]]
    observed_ids: list[str] = []
    for judgment in judgments:
        if not isinstance(judgment, dict) or frozenset(judgment) != _JUDGMENT_KEYS:
            raise AdjudicationIntegrityError("judgment keys do not match v1")
        try:
            receipt = _receipt_from_dict(judgment["receipt"])
            decision = ArcDecision(judgment["decision"])
        except (CacheCorruptionError, TypeError, ValueError) as exc:
            raise AdjudicationIntegrityError("invalid embedded receipt") from exc
        if (
            judgment["audit_item_id"] != receipt.audit_item_id
            or judgment["adjudicator"] != receipt.adjudicator
            or judgment["adjudicator"] != value["adjudicator"]
            or decision != receipt.decision
            or judgment["correct"] is not (decision == ArcDecision.SAME)
            or receipt.packet_sha256 != packet["packet_sha256"]
            or receipt.prompt_sha256 != value["prompt_sha256"]
            or receipt.config_sha256 != value["config_sha256"]
            or receipt.deployment_attestation_sha256
            != value["deployment_attestation_sha256"]
        ):
            raise AdjudicationIntegrityError("judgment and receipt disagree")
        observed_ids.append(receipt.audit_item_id)
    if observed_ids != expected_ids:
        raise AdjudicationIntegrityError("judgments do not preserve packet order")
    return value


def run_arc_adjudication(
    packet: Mapping[str, Any],
    config: ArcAdjudicatorConfigV1,
    *,
    cache_path: str | Path,
    transport: Transport | None = None,
) -> ArcAdjudicationRunV1:
    """Produce one durable terminal outcome for each still-missing item.

    This is a durable-ledger guarantee, not a claim of network exactly-once
    delivery: a transport failure is itself one terminal ``UNCLEAR`` outcome.
    """

    packet = validate_audit_packet(dict(packet))
    sender = transport or rex.openai_compatible_transport()
    cache = JSONLArcAdjudicationCache(cache_path)
    cached = {
        (record.packet_sha256, record.audit_item_id): record
        for record in cache.records()
    }
    receipts_by_item: dict[str, ArcAdjudicationReceiptV1] = {}
    pending: list[Mapping[str, Any]] = []
    cache_hits = 0
    for item in packet["items"]:
        record = cached.get((packet["packet_sha256"], item["audit_item_id"]))
        if record is None:
            pending.append(item)
        else:
            _validate_cached_request(
                record, item, packet["packet_sha256"], config,
            )
            receipts_by_item[item["audit_item_id"]] = record
            cache_hits += 1

    with ThreadPoolExecutor(max_workers=config.max_concurrency) as executor:
        futures = {
            executor.submit(
                adjudicate_item, item,
                packet_sha256=packet["packet_sha256"], config=config,
                transport=sender,
            ): item
            for item in pending
        }
        for future in as_completed(futures):
            record = future.result()
            if not cache.append(record):
                raise CacheCorruptionError("request was completed concurrently")
            receipts_by_item[record.audit_item_id] = record

    ordered = tuple(
        receipts_by_item[item["audit_item_id"]] for item in packet["items"]
    )
    artifact = _build_adjudication(packet, config, ordered)
    validate_adjudication(artifact, packet)
    return ArcAdjudicationRunV1(
        adjudication=artifact,
        cache_hits=cache_hits,
        endpoint_calls=len(pending),
    )


def _config_from_receipt(
    record: ArcAdjudicationReceiptV1,
) -> ArcAdjudicatorConfigV1:
    value = _validate_config_preimage(record)
    return ArcAdjudicatorConfigV1(
        endpoint=value["endpoint"],
        deployment_attestation_sha256=value[
            "deployment_attestation_sha256"
        ],
        model=value["model"], model_revision=value["model_revision"],
        max_concurrency=value["max_concurrency"],
        timeout_seconds=value["timeout_seconds"],
        max_tokens=value["max_tokens"], temperature=value["temperature"],
        top_p=value["top_p"], seed=value["seed"],
        disable_thinking=value["disable_thinking"],
        response_format=value["response_format"],
        items_per_request=value["items_per_request"],
    )


def _read_complete_ledger(path: str | Path) -> tuple[ArcAdjudicationReceiptV1, ...]:
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise AdjudicationCloseIntegrityError(
            f"cannot read adjudication ledger: {exc}"
        ) from exc
    if data and not data.endswith(b"\n"):
        raise AdjudicationCloseIntegrityError(
            "closed adjudication ledger has an incomplete final line"
        )
    try:
        return JSONLArcAdjudicationCache._decode(data)
    except CacheCorruptionError as exc:
        raise AdjudicationCloseIntegrityError(
            "closed adjudication ledger is corrupt"
        ) from exc


def _validate_sealed_records(
    records: Sequence[ArcAdjudicationReceiptV1],
    seal: Mapping[str, Any],
    packet: Mapping[str, Any],
    *,
    config: ArcAdjudicatorConfigV1 | None,
    require_complete: bool,
) -> dict[str, ArcAdjudicationReceiptV1]:
    items = {item["audit_item_id"]: item for item in packet["items"]}
    by_item: dict[str, ArcAdjudicationReceiptV1] = {}
    for record in records:
        if record.packet_sha256 != seal["packet_sha256"]:
            raise AdjudicationCloseIntegrityError(
                "sealed ledger contains a foreign packet"
            )
        item = items.get(record.audit_item_id)
        if item is None:
            raise AdjudicationCloseIntegrityError(
                "sealed ledger contains a foreign audit item"
            )
        if record.audit_item_id in by_item:
            raise AdjudicationCloseIntegrityError(
                "sealed ledger contains duplicate audit outcomes"
            )
        record_config = config or _config_from_receipt(record)
        if (
            record.config_sha256 != seal["adjudication_config_sha256"]
            or config_sha256(record_config)
            != seal["adjudication_config_sha256"]
            or record.deployment_attestation_sha256
            != seal["deployment_attestation_file_sha256"]
        ):
            raise AdjudicationCloseIntegrityError(
                "sealed receipt config/deployment binding changed"
            )
        try:
            _validate_cached_request(
                record, item, packet["packet_sha256"], record_config,
            )
        except CacheCorruptionError as exc:
            raise AdjudicationCloseIntegrityError(
                "sealed receipt does not bind its audit item"
            ) from exc
        by_item[record.audit_item_id] = record
    if require_complete and set(by_item) != set(items):
        raise AdjudicationCloseIntegrityError(
            "sealed ledger does not contain one outcome per audit item"
        )
    return by_item


def _load_json_artifact(
    path: str | Path,
    label: str,
    error_type: type[ValueError],
) -> dict[str, Any]:
    try:
        value = _strict_json(Path(path).read_text(encoding="utf-8"))
    except (_DuplicateJSONKey, json.JSONDecodeError, OSError) as exc:
        raise error_type(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise error_type(f"{label} must be a JSON object")
    return value


def _validate_output_against_ledger(
    artifact: Mapping[str, Any],
    packet: Mapping[str, Any],
    seal: Mapping[str, Any],
    records_by_item: Mapping[str, ArcAdjudicationReceiptV1],
) -> None:
    try:
        validate_adjudication(dict(artifact), packet)
    except (AdjudicationIntegrityError, PacketIntegrityError) as exc:
        raise AdjudicationCloseIntegrityError(
            "adjudication output is invalid"
        ) from exc
    if (
        artifact["config_sha256"] != seal["adjudication_config_sha256"]
        or artifact["deployment_attestation_sha256"]
        != seal["deployment_attestation_file_sha256"]
    ):
        raise AdjudicationCloseIntegrityError(
            "adjudication output differs from sealed config/deployment"
        )
    for judgment in artifact["judgments"]:
        record = records_by_item.get(judgment["audit_item_id"])
        if record is None or judgment["receipt"] != asdict(record):
            raise AdjudicationCloseIntegrityError(
                "adjudication output is not the committed ledger outcome"
            )


def _build_adjudication_close(
    seal: Mapping[str, Any],
    packet: Mapping[str, Any],
    artifact: Mapping[str, Any],
    records_by_item: Mapping[str, ArcAdjudicationReceiptV1],
) -> dict[str, Any]:
    ledger_path = Path(seal["ledger_path"])
    output_path = Path(seal["output_path"])
    ledger_info = ledger_path.stat()
    completed_request_ids = [
        records_by_item[item["audit_item_id"]].request_id
        for item in packet["items"]
    ]
    body = {
        "schema_version": ADJUDICATION_CLOSE_SCHEMA_VERSION,
        "stage_run_id": seal["stage_run_id"],
        "packet_seal_sha256": seal["packet_seal_sha256"],
        "final_ledger_sha256": file_sha256(ledger_path),
        "adjudication_output_sha256": file_sha256(output_path),
        "adjudication_sha256": artifact["adjudication_sha256"],
        "n_items": seal["n_items"],
        "n_outcomes": len(records_by_item),
        # These are cumulative sealed-run facts.  A resumed invocation can
        # reuse already durable outcomes, but the ledger started empty and
        # contains one endpoint-attempt outcome for every item.
        "endpoint_calls": seal["n_items"],
        "cache_hits": 0,
        "completed_request_ids": completed_request_ids,
        "ledger_device": ledger_info.st_dev,
        "ledger_inode": ledger_info.st_ino,
        "same_ledger_inode": (
            ledger_info.st_dev == seal["ledger_device"]
            and ledger_info.st_ino == seal["ledger_inode"]
        ),
        "durable_outcome_claim": DURABLE_OUTCOME_CLAIM,
    }
    return {
        **body,
        "adjudication_close_sha256": sha256_text(canonical_json(body)),
    }


def validate_adjudication_close(packet_seal_path: str | Path) -> dict[str, Any]:
    """Validate the full seal -> ledger -> output -> close evidence chain.

    A caller must require this function to succeed before using any identity
    precision metric derived from the adjudication output.
    """

    seal = load_packet_seal(packet_seal_path)
    packet = load_audit_packet(seal["packet_path"])
    records = _read_complete_ledger(seal["ledger_path"])
    records_by_item = _validate_sealed_records(
        records, seal, packet, config=None, require_complete=True,
    )
    if records:
        try:
            _validate_deployment_attestation(
                seal["deployment_attestation_path"],
                config=_config_from_receipt(records[0]),
            )
        except PacketSealIntegrityError as exc:
            raise AdjudicationCloseIntegrityError(
                "closed ledger config is not bound to deployment attestation"
            ) from exc
    artifact = _load_json_artifact(
        seal["output_path"], "adjudication output",
        AdjudicationCloseIntegrityError,
    )
    _validate_output_against_ledger(artifact, packet, seal, records_by_item)
    close = _load_json_artifact(
        seal["close_path"], "adjudication close receipt",
        AdjudicationCloseIntegrityError,
    )
    if frozenset(close) != _ADJUDICATION_CLOSE_KEYS:
        raise AdjudicationCloseIntegrityError(
            "adjudication close root keys do not match v1"
        )
    if close["schema_version"] != ADJUDICATION_CLOSE_SCHEMA_VERSION:
        raise AdjudicationCloseIntegrityError("adjudication close schema mismatch")
    for key in (
        "packet_seal_sha256", "final_ledger_sha256",
        "adjudication_output_sha256", "adjudication_sha256",
        "adjudication_close_sha256",
    ):
        if not isinstance(close[key], str) or _SHA256_RE.fullmatch(close[key]) is None:
            raise AdjudicationCloseIntegrityError(
                f"close {key} must be a lower-case SHA-256"
            )
    if close["adjudication_close_sha256"] != _seal_self_hash(
        close, "adjudication_close_sha256",
    ):
        raise AdjudicationCloseIntegrityError("adjudication close self-hash mismatch")
    expected_ids = [
        records_by_item[item["audit_item_id"]].request_id
        for item in packet["items"]
    ]
    ledger_info = Path(seal["ledger_path"]).stat()
    scalar_expectations = {
        "stage_run_id": seal["stage_run_id"],
        "packet_seal_sha256": seal["packet_seal_sha256"],
        "final_ledger_sha256": file_sha256(seal["ledger_path"]),
        "adjudication_output_sha256": file_sha256(seal["output_path"]),
        "adjudication_sha256": artifact["adjudication_sha256"],
        "n_items": seal["n_items"],
        "n_outcomes": seal["n_items"],
        "endpoint_calls": seal["n_items"],
        "cache_hits": 0,
        "completed_request_ids": expected_ids,
        "ledger_device": seal["ledger_device"],
        "ledger_inode": seal["ledger_inode"],
        "same_ledger_inode": True,
        "durable_outcome_claim": DURABLE_OUTCOME_CLAIM,
    }
    for key, expected in scalar_expectations.items():
        if close[key] != expected:
            raise AdjudicationCloseIntegrityError(
                f"adjudication close {key} does not match sealed evidence"
            )
    if (
        ledger_info.st_dev != close["ledger_device"]
        or ledger_info.st_ino != close["ledger_inode"]
        or len(expected_ids) != len(set(expected_ids))
    ):
        raise AdjudicationCloseIntegrityError(
            "closed ledger inode/request identities are not unique and stable"
        )
    return close


def _validate_seal_for_run(
    seal: Mapping[str, Any],
    config: ArcAdjudicatorConfigV1,
    deployment_attestation_path: str | Path,
) -> None:
    attestation = _existing_regular_path(
        deployment_attestation_path, "deployment attestation",
        PacketSealIntegrityError,
    )
    if str(attestation) != seal["deployment_attestation_path"]:
        raise PacketSealIntegrityError(
            "runtime deployment attestation path differs from packet seal"
        )
    if (
        file_sha256(attestation) != seal["deployment_attestation_file_sha256"]
        or config.deployment_attestation_sha256
        != seal["deployment_attestation_file_sha256"]
        or config_sha256(config) != seal["adjudication_config_sha256"]
    ):
        raise PacketSealIntegrityError(
            "runtime config/deployment attestation differs from packet seal"
        )
    _validate_deployment_attestation(attestation, config=config)


def run_sealed_arc_adjudication(
    packet_seal_path: str | Path,
    config: ArcAdjudicatorConfigV1,
    *,
    deployment_attestation_path: str | Path,
    transport: Transport | None = None,
) -> ArcAdjudicationRunV1:
    """Run only the paths committed by a valid packet seal, then close them.

    Crash recovery consults the same committed ledger and calls the endpoint
    only for missing items.  A successful close proves one durable outcome per
    audit item; it deliberately makes no network exactly-once claim.
    """

    seal = load_packet_seal(packet_seal_path)
    _validate_seal_for_run(seal, config, deployment_attestation_path)
    packet = load_audit_packet(seal["packet_path"])
    close_path = Path(seal["close_path"])
    output_path = Path(seal["output_path"])

    if close_path.exists():
        validate_adjudication_close(packet_seal_path)
        artifact = _load_json_artifact(
            output_path, "adjudication output", AdjudicationCloseIntegrityError,
        )
        return ArcAdjudicationRunV1(
            adjudication=artifact, cache_hits=seal["n_items"], endpoint_calls=0,
        )

    cache = JSONLArcAdjudicationCache(seal["ledger_path"])
    records = cache.records()  # repairs only an interrupted final line
    records_by_item = _validate_sealed_records(
        records, seal, packet, config=config, require_complete=False,
    )
    if output_path.exists():
        if len(records_by_item) != seal["n_items"]:
            raise AdjudicationCloseIntegrityError(
                "adjudication output exists before the sealed ledger is complete"
            )
        artifact = _load_json_artifact(
            output_path, "adjudication output", AdjudicationCloseIntegrityError,
        )
        _validate_output_against_ledger(
            artifact, packet, seal, records_by_item,
        )
        close = _build_adjudication_close(
            seal, packet, artifact, records_by_item,
        )
        _write_exclusive(close_path, close)
        validate_adjudication_close(packet_seal_path)
        return ArcAdjudicationRunV1(
            adjudication=artifact, cache_hits=seal["n_items"], endpoint_calls=0,
        )

    result = run_arc_adjudication(
        packet, config, cache_path=seal["ledger_path"], transport=transport,
    )
    final_records = _read_complete_ledger(seal["ledger_path"])
    records_by_item = _validate_sealed_records(
        final_records, seal, packet, config=config, require_complete=True,
    )
    _validate_output_against_ledger(
        result.adjudication, packet, seal, records_by_item,
    )
    _write_exclusive(output_path, result.adjudication)
    close = _build_adjudication_close(
        seal, packet, result.adjudication, records_by_item,
    )
    _write_exclusive(close_path, close)
    validate_adjudication_close(packet_seal_path)
    return result


def _fsync_parent(path: Path) -> None:
    try:
        fd = os.open(path.parent, os.O_RDONLY)
    except OSError:  # pragma: no cover - platform/filesystem dependent
        return
    try:
        os.fsync(fd)
    except OSError:  # pragma: no cover - platform/filesystem dependent
        pass
    finally:
        os.close(fd)


def _write_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    """Atomically publish canonical JSON without replacing any existing path."""

    encoded = (canonical_json(value) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        # A hard-link publication has O_EXCL semantics at the final path and
        # cannot overwrite another process's evidence artifact.
        os.link(temporary, path)
        _fsync_parent(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _write_once(path: Path, value: Mapping[str, Any]) -> None:
    encoded = (canonical_json(value) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() == encoded:
            return
        raise FileExistsError(f"refusing to replace existing artifact: {path}")
    try:
        _write_exclusive(path, value)
    except FileExistsError:
        # Idempotent crash recovery may observe a concurrently published byte-
        # identical artifact, but a differing preimage is never replaced.
        if path.read_bytes() != encoded:
            raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet-seal-json", required=True, type=Path)
    parser.add_argument("--deployment-attestation", required=True, type=Path)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model", default=FROZEN_MODEL)
    parser.add_argument("--model-revision", default=FROZEN_MODEL_REVISION)
    parser.add_argument("--max-concurrency", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--max-tokens", type=int, default=96)
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    args = parser.parse_args(argv)

    deployment_attestation_sha256 = file_sha256(
        _existing_regular_path(
            args.deployment_attestation, "deployment attestation",
            PacketSealIntegrityError,
        )
    )
    config = ArcAdjudicatorConfigV1(
        endpoint=args.endpoint,
        deployment_attestation_sha256=deployment_attestation_sha256,
        model=args.model,
        model_revision=args.model_revision,
        max_concurrency=args.max_concurrency,
        timeout_seconds=args.timeout_seconds, max_tokens=args.max_tokens,
    )
    api_key = os.environ.get(args.api_key_env)
    result = run_sealed_arc_adjudication(
        args.packet_seal_json, config,
        deployment_attestation_path=args.deployment_attestation,
        transport=rex.openai_compatible_transport(api_key=api_key),
    )
    seal = load_packet_seal(args.packet_seal_json)
    close = validate_adjudication_close(args.packet_seal_json)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "stage_run_id": seal["stage_run_id"],
        "packet_seal_sha256": seal["packet_seal_sha256"],
        "packet_sha256": seal["packet_sha256"],
        "adjudication_sha256": result.adjudication["adjudication_sha256"],
        "adjudication_close_sha256": close["adjudication_close_sha256"],
        "deployment_attestation_sha256": (
            result.adjudication["deployment_attestation_sha256"]
        ),
        "judgments": len(result.adjudication["judgments"]),
        "cache_hits": result.cache_hits,
        "endpoint_calls": result.endpoint_calls,
        "decision_counts": {
            decision.value: sum(
                item["decision"] == decision.value
                for item in result.adjudication["judgments"]
            )
            for decision in ArcDecision
        },
    }
    print(canonical_json(summary))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through main()
    raise SystemExit(main())
