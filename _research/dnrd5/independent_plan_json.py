"""Independent DNRD-5 plan JSON verifier codec.

Kept deliberately separate from ``plan_json`` so an implementation mistake in
the randomization producer cannot validate itself.
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


class IndependentPlanJsonError(ValueError):
    """A candidate fails the independently implemented plan JSON rules."""


def _utf8(text: str) -> None:
    try:
        text.encode("utf-8", "strict")
    except UnicodeEncodeError as error:
        raise IndependentPlanJsonError("surrogate code unit in JSON string") from error


def _ascii_key(text: str) -> None:
    _utf8(text)
    if not KEY_MIN_LENGTH <= len(text) <= KEY_MAX_LENGTH:
        raise IndependentPlanJsonError("key length is outside 1..128")
    for character in text:
        if ord(character) < 0x20 or ord(character) > 0x7e:
            raise IndependentPlanJsonError("key is not printable ASCII")


def _check(item: Any, level: int, tally: list[int]) -> None:
    if level > MAX_DEPTH:
        raise IndependentPlanJsonError("plan nesting is too deep")
    tally[0] += 1
    if tally[0] > MAX_NODES:
        raise IndependentPlanJsonError("plan has too many nodes")
    if item is None or type(item) is bool:
        return
    if type(item) is str:
        _utf8(item)
        return
    if type(item) is int:
        if item < -MAX_SAFE_INTEGER or item > MAX_SAFE_INTEGER:
            raise IndependentPlanJsonError("plan integer is not safe")
        return
    if type(item) is list:
        for child in item:
            _check(child, level + 1, tally)
        return
    if type(item) is dict:
        for name in item:
            if type(name) is not str:
                raise IndependentPlanJsonError("plan mapping key is not a string")
            _ascii_key(name)
            _check(item[name], level + 1, tally)
        return
    raise IndependentPlanJsonError("plan value has an unsupported runtime type")


def _json_string(text: str) -> str:
    return json.dumps(text, ensure_ascii=False, separators=(",", ":"))


def _render(item: Any) -> str:
    if item is None:
        return "null"
    if type(item) is bool:
        return "true" if item else "false"
    if type(item) is str:
        return _json_string(item)
    if type(item) is int:
        return str(item)
    if type(item) is list:
        return "[" + ",".join(_render(child) for child in item) + "]"
    if type(item) is dict:
        ordered = sorted(item.keys())
        return "{" + ",".join(
            _json_string(name) + ":" + _render(item[name]) for name in ordered
        ) + "}"
    raise AssertionError("independent codec rendered an unchecked value")


def canonical_bytes(value: Any) -> bytes:
    _check(value, 0, [0])
    output = _render(value).encode("utf-8", "strict")
    if len(output) > MAX_BYTES:
        raise IndependentPlanJsonError("encoded plan is larger than 2,000,000 bytes")
    return output


def canonical_sha256(value: Any) -> str:
    return sha256(canonical_bytes(value)).hexdigest()


def _reject_constant(token: str) -> None:
    raise IndependentPlanJsonError(f"non-JSON constant {token!r}")


def _reject_float(token: str) -> None:
    raise IndependentPlanJsonError(f"non-integral JSON number {token!r}")


def _no_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for name, item in pairs:
        if name in mapping:
            raise IndependentPlanJsonError("duplicate object member")
        mapping[name] = item
    return mapping


def parse_canonical(raw: bytes) -> Any:
    if type(raw) is not bytes:
        raise IndependentPlanJsonError("independent input must be bytes")
    if len(raw) > MAX_BYTES:
        raise IndependentPlanJsonError("independent input is too large")
    try:
        parsed = json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=_no_duplicate,
            parse_constant=_reject_constant,
            parse_float=_reject_float,
        )
        rebuilt = canonical_bytes(parsed)
    except IndependentPlanJsonError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as error:
        raise IndependentPlanJsonError("input is not strict UTF-8 JSON") from error
    if raw != rebuilt:
        raise IndependentPlanJsonError("input is not exact independent plan JSON")
    return parsed
