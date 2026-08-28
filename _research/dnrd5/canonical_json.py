"""Independent Python codec for the runtime's ``hswm-canonical-json/v1``.

Python's default ``sort_keys=True`` orders Unicode code points. JavaScript
orders object keys by UTF-16 code units, which differs for supplementary-plane
characters. DNRD-5 hashes must not depend on which implementation produced a
record, so this module implements the runtime contract directly rather than
wrapping ``json.dumps(..., sort_keys=True)``.
"""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any


CONTRACT_VERSION = "hswm-canonical-json/v1"
MAX_BYTES = 1_048_576
MAX_DEPTH = 128
MAX_NODES = 100_000
MAX_SAFE_INTEGER = 9_007_199_254_740_991


class CanonicalJsonError(ValueError):
    """The value or byte string is outside canonical-json/v1."""


def _validate_string(value: str) -> None:
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise CanonicalJsonError("JSON strings cannot contain lone surrogates") from error


def _utf16_sort_key(value: str) -> bytes:
    """Return the bytewise equivalent of JavaScript UTF-16 lexical ordering."""
    _validate_string(value)
    return value.encode("utf-16-be", errors="strict")


def _validate_value(
    value: Any,
    *,
    depth: int = 0,
    node_count: list[int] | None = None,
) -> None:
    if node_count is None:
        node_count = [0]
    if depth > MAX_DEPTH:
        raise CanonicalJsonError("JSON nesting exceeds the v1 depth bound")
    node_count[0] += 1
    if node_count[0] > MAX_NODES:
        raise CanonicalJsonError("JSON value exceeds the v1 node bound")

    if value is None or type(value) is bool:
        return
    if type(value) is str:
        _validate_string(value)
        return
    if type(value) is int:
        if not -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
            raise CanonicalJsonError("JSON integer is outside the safe-integer range")
        return
    if type(value) is list:
        for item in value:
            _validate_value(item, depth=depth + 1, node_count=node_count)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise CanonicalJsonError("JSON object keys must be exact strings")
            _validate_string(key)
            _validate_value(item, depth=depth + 1, node_count=node_count)
        return
    raise CanonicalJsonError("value is not part of canonical-json/v1")


def _encode_string(value: str) -> str:
    # CPython's compact string encoding matches the v1 escape table when
    # ensure_ascii is false: non-ASCII is literal UTF-8 and controls are escaped.
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _encode_value(value: Any) -> str:
    if value is None:
        return "null"
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) is str:
        return _encode_string(value)
    if type(value) is int:
        return str(value)
    if type(value) is list:
        return "[" + ",".join(_encode_value(item) for item in value) + "]"
    if type(value) is dict:
        members = (
            f"{_encode_string(key)}:{_encode_value(value[key])}"
            for key in sorted(value, key=_utf16_sort_key)
        )
        return "{" + ",".join(members) + "}"
    # ``_validate_value`` owns the public error, so reaching this is a bug.
    raise AssertionError("validated canonical JSON value has an unknown type")


def canonical_bytes(value: Any) -> bytes:
    """Encode one value to exact, no-suffix canonical-json/v1 UTF-8 bytes."""
    _validate_value(value)
    encoded = _encode_value(value).encode("utf-8", errors="strict")
    if len(encoded) > MAX_BYTES:
        raise CanonicalJsonError("canonical JSON bytes exceed the v1 byte bound")
    return encoded


def canonical_sha256(value: Any) -> str:
    return sha256(canonical_bytes(value)).hexdigest()


def _reject_constant(value: str) -> None:
    raise CanonicalJsonError(f"forbidden JSON constant {value!r}")


def _reject_float(value: str) -> None:
    raise CanonicalJsonError(f"canonical-json/v1 excludes non-integer number {value!r}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CanonicalJsonError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def parse_canonical(raw: bytes) -> Any:
    """Parse exact canonical bytes, rejecting whitespace and transport suffixes."""
    if type(raw) is not bytes:
        raise CanonicalJsonError("canonical JSON input must be exact bytes")
    if len(raw) > MAX_BYTES:
        raise CanonicalJsonError("canonical JSON bytes exceed the v1 byte bound")
    try:
        text = raw.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
            parse_float=_reject_float,
        )
        encoded = canonical_bytes(value)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise CanonicalJsonError("input is not strict bounded UTF-8 JSON") from error
    if encoded != raw:
        raise CanonicalJsonError("input bytes are not exact canonical-json/v1")
    return value
