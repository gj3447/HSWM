"""DNRD-5 plan-specific canonical JSON producer codec.

This deliberately narrow wire format is for randomization plans only.  It is
not the repository-wide canonical JSON format and it makes no occurrence or
custody claim.
"""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any


CONTRACT_VERSION = "hswm-dnrd5-plan-json/v1"
MEDIA_TYPE = "application/vnd.hswm.dnrd5.randomization-plan-v1+json"
MAX_BYTES = 2_000_000
MAX_DEPTH = 128
MAX_NODES = 100_000
MAX_SAFE_INTEGER = 9_007_199_254_740_991
KEY_MIN_LENGTH = 1
KEY_MAX_LENGTH = 128


class PlanJsonError(ValueError):
    """A value or byte string is outside the DNRD-5 plan JSON contract."""


def _string(value: str) -> None:
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise PlanJsonError("strings cannot contain lone surrogates") from error


def _key(value: str) -> None:
    _string(value)
    if not KEY_MIN_LENGTH <= len(value) <= KEY_MAX_LENGTH:
        raise PlanJsonError("object keys must have length 1 through 128")
    if any(not "\u0020" <= character <= "\u007e" for character in value):
        raise PlanJsonError("object keys must be printable ASCII")


def _validate(value: Any, depth: int, nodes: list[int]) -> None:
    if depth > MAX_DEPTH:
        raise PlanJsonError("JSON nesting exceeds the plan bound")
    nodes[0] += 1
    if nodes[0] > MAX_NODES:
        raise PlanJsonError("JSON node count exceeds the plan bound")
    if value is None or type(value) is bool:
        return
    if type(value) is str:
        _string(value)
        return
    if type(value) is int:
        if not -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
            raise PlanJsonError("integer is outside the safe range")
        return
    if type(value) is list:
        for item in value:
            _validate(item, depth + 1, nodes)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise PlanJsonError("object keys must be exact strings")
            _key(key)
            _validate(item, depth + 1, nodes)
        return
    raise PlanJsonError("value is outside the exact plan JSON domain")


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _encode(value: Any) -> str:
    if value is None:
        return "null"
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) is str:
        return _quote(value)
    if type(value) is int:
        return str(value)
    if type(value) is list:
        return "[" + ",".join(_encode(item) for item in value) + "]"
    if type(value) is dict:
        return "{" + ",".join(
            f"{_quote(key)}:{_encode(value[key])}" for key in sorted(value)
        ) + "}"
    raise AssertionError("unvalidated plan value")


def canonical_bytes(value: Any) -> bytes:
    """Return exact compact UTF-8 plan bytes, without a transport suffix."""
    _validate(value, 0, [0])
    result = _encode(value).encode("utf-8", errors="strict")
    if len(result) > MAX_BYTES:
        raise PlanJsonError("canonical plan bytes exceed the 2,000,000-byte bound")
    return result


def canonical_sha256(value: Any) -> str:
    return sha256(canonical_bytes(value)).hexdigest()


def _constant(value: str) -> None:
    raise PlanJsonError(f"forbidden JSON constant {value!r}")


def _float(value: str) -> None:
    raise PlanJsonError(f"plan JSON excludes fractional number {value!r}")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PlanJsonError(f"duplicate object key {key!r}")
        result[key] = value
    return result


def parse_canonical(raw: bytes) -> Any:
    """Parse only bytes already in the exact plan canonical representation."""
    if type(raw) is not bytes:
        raise PlanJsonError("plan JSON input must be exact bytes")
    if len(raw) > MAX_BYTES:
        raise PlanJsonError("plan JSON bytes exceed the 2,000,000-byte bound")
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_pairs,
            parse_constant=_constant,
            parse_float=_float,
        )
        encoded = canonical_bytes(value)
    except PlanJsonError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as error:
        raise PlanJsonError("input is not strict bounded UTF-8 JSON") from error
    if encoded != raw:
        raise PlanJsonError("input bytes are not exact canonical DNRD-5 plan JSON")
    return value
