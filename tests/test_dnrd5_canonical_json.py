"""Known-answer and adversarial checks for the independent DNRD-5 codec."""

from __future__ import annotations

import pytest

from _research.dnrd5.canonical_json import (
    MAX_BYTES,
    MAX_DEPTH,
    MAX_NODES,
    CanonicalJsonError,
    canonical_bytes,
    canonical_sha256,
    parse_canonical,
)


def test_utf16_key_order_known_answer_matches_typescript_runtime() -> None:
    # U+1F600 sorts before U+FFFF by UTF-16 code units, but after it by Python
    # code point. This case detects accidental reversion to sort_keys=True.
    value = {"😀": 1, "\uffff": 2}
    expected = b'{"\xf0\x9f\x98\x80":1,"\xef\xbf\xbf":2}'
    assert canonical_bytes(value) == expected
    assert canonical_sha256(value) == (
        "c6b1b96b618d8be475f379fe69c6646b44d7a5d3c01630c43509562f09d1024b"
    )
    assert parse_canonical(expected) == value


def test_string_escaping_and_nested_value_known_answer() -> None:
    value = {"z": "line\nquote\"", "a": 1, "😀": True, "\uffff": None}
    assert canonical_bytes(value) == (
        '{"a":1,"z":"line\\nquote\\\"","😀":true,"\uffff":null}'.encode()
    )


@pytest.mark.parametrize(
    "raw",
    [
        b'{ "a":1}',
        b'{"a":1}\n',
        b'{"a":1,"a":2}',
        b'{"a":1,"\\u0061":2}',
        b'{"a":1.0}',
        b'{"a":-0}',
        b'{"a":9007199254740992}',
        b'{"a":"\\u0062"}',
        b"\xff",
    ],
)
def test_parser_rejects_alternate_or_invalid_bytes(raw: bytes) -> None:
    with pytest.raises(CanonicalJsonError):
        parse_canonical(raw)


@pytest.mark.parametrize(
    "value",
    [
        1.0,
        float("nan"),
        9_007_199_254_740_992,
        -9_007_199_254_740_992,
        {"x": "\ud800"},
        {1: "non-string-key"},
        (1, 2),
        object(),
    ],
)
def test_encoder_rejects_noncanonical_values(value: object) -> None:
    with pytest.raises(CanonicalJsonError):
        canonical_bytes(value)


def test_encoder_enforces_byte_depth_node_and_exact_container_bounds() -> None:
    with pytest.raises(CanonicalJsonError):
        canonical_bytes("x" * MAX_BYTES)

    allowed: object = None
    for _ in range(MAX_DEPTH):
        allowed = [allowed]
    canonical_bytes(allowed)
    too_deep = [allowed]
    with pytest.raises(CanonicalJsonError):
        canonical_bytes(too_deep)

    with pytest.raises(CanonicalJsonError):
        canonical_bytes([0] * MAX_NODES)

    class ListSubclass(list[object]):
        pass

    class DictSubclass(dict[str, object]):
        pass

    for value in (ListSubclass(), DictSubclass()):
        with pytest.raises(CanonicalJsonError):
            canonical_bytes(value)
