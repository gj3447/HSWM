"""Deterministic F5v2 provenance, canary, and DRM-lure gates.

This is an offline contract layer.  It does not ask an LLM to judge another
LLM and it emits no scientific verdict.  A future live runner can feed its raw
rows here before a development-smoke receipt is eligible for sealing.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Iterable, Mapping, Sequence


DEV_SMOKE_SCHEMA = "hswm-f5v2-dev-smoke-receipt/v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class JudgeContractError(ValueError):
    """A deterministic F5v2 judge input violates its locked schema."""


def _sha256(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise JudgeContractError(f"{label} must be a lowercase SHA-256")
    return value


def verify_packet_citations(
    rows: Sequence[Mapping[str, Any]],
    allowed_packet_sha256s: Iterable[str],
) -> dict[str, Any]:
    """Require every derived row to cite only frozen source packets."""
    allowed = {_require_sha(value, "allowed packet") for value in allowed_packet_sha256s}
    if not allowed:
        raise JudgeContractError("allowed packet set must not be empty")
    cited: set[str] = set()
    for index, row in enumerate(rows):
        values = row.get("cited_packet_sha256s")
        if not isinstance(values, list) or not values:
            raise JudgeContractError(f"row {index} has no packet citations")
        for value in values:
            digest = _require_sha(value, f"row {index} citation")
            if digest not in allowed:
                raise JudgeContractError(f"row {index} cites an unknown packet {digest}")
            cited.add(digest)
    return {
        "status": "PASS",
        "row_count": len(rows),
        "allowed_packet_count": len(allowed),
        "cited_packet_count": len(cited),
    }


def adversarial_canary_catch_rate(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Score preregistered wrong-answer/citation canaries.

    Every input row is an adversarial case and therefore must carry
    ``should_reject=true``.  ``rejected`` is the observed deterministic gate
    decision.  This shape prevents ordinary accuracy rows being silently mixed
    into the canary denominator.
    """
    if not cases:
        raise JudgeContractError("at least one adversarial canary is required")
    caught = 0
    for index, row in enumerate(cases):
        if row.get("should_reject") is not True:
            raise JudgeContractError(f"canary {index} is not marked should_reject")
        if not isinstance(row.get("rejected"), bool):
            raise JudgeContractError(f"canary {index} lacks boolean rejected")
        caught += int(row["rejected"])
    rate = caught / len(cases)
    return {
        "caught": caught,
        "total": len(cases),
        "catch_rate": rate,
        "threshold": 0.9,
        "passed": rate >= 0.9,
    }


def score_drm_lures(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Count related-but-unstated claims accepted by an output.

    ``supported_claims`` and ``proposed_claims`` are frozen string IDs rather
    than free text.  A proposed ID outside the support set is a DRM-style lure.
    """
    if not cases:
        raise JudgeContractError("at least one DRM lure case is required")
    lure_count = 0
    proposed_count = 0
    rows = []
    for index, row in enumerate(cases):
        supported = row.get("supported_claims")
        proposed = row.get("proposed_claims")
        if not isinstance(supported, list) or not all(isinstance(v, str) for v in supported):
            raise JudgeContractError(f"DRM case {index} has invalid supported_claims")
        if not isinstance(proposed, list) or not all(isinstance(v, str) for v in proposed):
            raise JudgeContractError(f"DRM case {index} has invalid proposed_claims")
        lures = sorted(set(proposed) - set(supported))
        lure_count += len(lures)
        proposed_count += len(proposed)
        rows.append({"case_id": row.get("case_id", str(index)), "lures": lures})
    rate = lure_count / proposed_count if proposed_count else 0.0
    return {
        "lure_count": lure_count,
        "proposed_count": proposed_count,
        "lure_rate": rate,
        "passed": lure_count == 0,
        "rows": rows,
    }


def build_dev_smoke_receipt(
    *,
    manifest_sha256: str,
    citation_rows: Sequence[Mapping[str, Any]],
    allowed_packet_sha256s: Iterable[str],
    canary_cases: Sequence[Mapping[str, Any]],
    drm_cases: Sequence[Mapping[str, Any]],
    legacy_downscale_negative_reproduced: bool,
    bitemporal_fired: bool,
    query_leakage_count: int,
) -> dict[str, Any]:
    """Assemble the exact deterministic gates consumed by sealed prep."""
    manifest_sha256 = _require_sha(manifest_sha256, "manifest_sha256")
    if isinstance(query_leakage_count, bool) or not isinstance(query_leakage_count, int):
        raise JudgeContractError("query_leakage_count must be an integer")
    if query_leakage_count < 0:
        raise JudgeContractError("query_leakage_count must be non-negative")
    citations = verify_packet_citations(citation_rows, allowed_packet_sha256s)
    canary = adversarial_canary_catch_rate(canary_cases)
    drm = score_drm_lures(drm_cases)
    gates = {
        "legacy_downscale_negative_reproduced": legacy_downscale_negative_reproduced is True,
        "bitemporal_fired": bitemporal_fired is True,
        "provenance_passed": citations["status"] == "PASS",
        "canary_passed": canary["passed"],
        "drm_lure_passed": drm["passed"],
        "query_leakage_zero": query_leakage_count == 0,
    }
    receipt = {
        "schema_version": DEV_SMOKE_SCHEMA,
        "status": "PASS_OFFLINE_INTEGRITY" if all(gates.values()) else "FAIL",
        "manifest_sha256": manifest_sha256,
        "gates": gates,
        "citation_audit": citations,
        "adversarial_canary": canary,
        "drm_lure": drm,
        "query_leakage_count": query_leakage_count,
        "claim_boundary": (
            "offline development-smoke integrity only; caller booleans and "
            "self-hashes are not external authority, live measurement, or a "
            "scientific verdict"
        ),
    }
    receipt["receipt_sha256"] = _sha256(receipt)
    return receipt


def verify_dev_smoke_receipt(receipt: Mapping[str, Any]) -> None:
    """Recompute the self-hash and reject NaN or hand-edited gate receipts."""
    if receipt.get("schema_version") != DEV_SMOKE_SCHEMA:
        raise JudgeContractError(f"receipt schema must be {DEV_SMOKE_SCHEMA}")
    expected = receipt.get("receipt_sha256")
    _require_sha(expected, "receipt_sha256")
    unsigned = dict(receipt)
    unsigned.pop("receipt_sha256", None)
    if _sha256(unsigned) != expected:
        raise JudgeContractError("development-smoke receipt digest mismatch")
    for key, value in (receipt.get("gates") or {}).items():
        if not isinstance(value, bool):
            raise JudgeContractError(f"gate {key} is not boolean")
    rate = (receipt.get("adversarial_canary") or {}).get("catch_rate")
    if not isinstance(rate, (int, float)) or isinstance(rate, bool) or not math.isfinite(rate):
        raise JudgeContractError("canary catch_rate must be finite")
