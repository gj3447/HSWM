#!/usr/bin/env python3
"""Replay one fixed HSWM Permit test vector with an independent crypto consumer.

This is deliberately not a general Permit-envelope schema verifier, a trust
authority, an issuer, an admission checker, or a learning/effectiveness
verifier.  It only checks the checked-in vector's exact bytes, its restricted
canonical-JSON encoding, and its Ed25519 signature using OpenSSL.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VECTOR = (
    ROOT
    / "src/hswm/effect-runtime/test/fixtures"
    / "canonical-permit-envelope-v1.vector.json"
)
SAFE_INTEGER_MAX = 9_007_199_254_740_991
BASE64URL = re.compile(r"^[A-Za-z0-9_-]+$")
PINNED_PUBLIC_KEY_SPKI_DER_BASE64URL = (
    "MCowBQYDK2VwAyEA11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo"
)
PINNED_SIGNING_DOCUMENT_SHA256 = (
    "985d0156c0687de5d3e2a908c93c9aa098932afda9673925e5478dde4ff59c80"
)
PINNED_ENVELOPE_SHA256 = (
    "66af55c2437da2394450bc985f2979176cf44c6b6443a1886c8ed142bc83ed9a"
)
PINNED_CALLER_CONTEXT_VERIFICATION_STATUS = (
    "CALLER_RELATIVE_BINDINGS_TRUST_AND_TIME_ENVELOPE_VERIFIED_NOT_"
    "AUTHORITATIVE_PERMIT_NOT_ATOMIC_ADMISSION_NOT_LEARNING"
)


def fail(message: str) -> None:
    raise SystemExit(f"canonical Permit vector verification failed: {message}")


def no_duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            fail(f"duplicate JSON key {key!r}")
        value[key] = item
    return value


def has_lone_surrogate(value: str) -> bool:
    """Match JavaScript's canonical-json/v1 lone-surrogate rejection."""
    return any(0xD800 <= ord(character) <= 0xDFFF for character in value)


def reject_lone_surrogates(value: Any) -> None:
    if isinstance(value, str):
        if has_lone_surrogate(value):
            fail("JSON string contains a lone surrogate")
        return
    if isinstance(value, list):
        for item in value:
            reject_lone_surrogates(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if has_lone_surrogate(key):
                fail("JSON object key contains a lone surrogate")
            reject_lone_surrogates(item)


def utf16_code_unit_sort_key(value: str) -> bytes:
    """Sort strings as JS `<` does: lexicographic UTF-16 code units.

    Python orders Unicode scalar values, which differs around non-BMP text.
    UTF-16BE byte order has the same lexicographic order as unsigned 16-bit
    code units and is independent of host byte order.
    """
    if has_lone_surrogate(value):
        fail("canonical JSON cannot order a lone-surrogate string")
    return value.encode("utf-16-be", errors="strict")


def safe_integer(text: str) -> int:
    if text == "-0":
        fail("negative zero is outside hswm-canonical-json/v1")
    value = int(text)
    if abs(value) > SAFE_INTEGER_MAX:
        fail("JSON integer exceeds the safe-integer bound")
    return value


def reject_float(text: str) -> float:
    fail(f"non-integer JSON number {text!r}")


def decode_json_exact(raw: bytes) -> Any:
    try:
        text = raw.decode("utf-8", errors="strict")
        decoded = json.loads(
            text,
            object_pairs_hook=no_duplicate_object,
            parse_int=safe_integer,
            parse_float=reject_float,
            parse_constant=reject_float,
        )
        reject_lone_surrogates(decoded)
        return decoded
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        fail(str(error))


def canonical_json_bytes(value: Any) -> bytes:
    """Encode the repository's restricted JSON profile, not RFC 8785 JCS.

    In particular object members are sorted by UTF-16 code units, as in the
    TypeScript implementation, rather than Python's Unicode-code-point order.
    """
    try:
        def encode(item: Any) -> str:
            if item is None:
                return "null"
            if item is True:
                return "true"
            if item is False:
                return "false"
            if isinstance(item, int):
                if abs(item) > SAFE_INTEGER_MAX:
                    fail("JSON integer exceeds the safe-integer bound")
                return str(item)
            if isinstance(item, str):
                if has_lone_surrogate(item):
                    fail("canonical JSON string contains a lone surrogate")
                return json.dumps(item, ensure_ascii=False, allow_nan=False)
            if isinstance(item, list):
                return "[" + ",".join(encode(child) for child in item) + "]"
            if isinstance(item, dict):
                keys = list(item.keys())
                if not all(isinstance(key, str) for key in keys):
                    fail("canonical JSON object key is not a string")
                ordered_keys = sorted(keys, key=utf16_code_unit_sort_key)
                return "{" + ",".join(
                    f"{encode(key)}:{encode(item[key])}" for key in ordered_keys
                ) + "}"
            fail(f"unsupported JSON value type {type(item).__name__}")

        return encode(value).encode("utf-8", errors="strict")
    except (TypeError, ValueError) as error:
        fail(str(error))


def assert_canonical_json_contract() -> None:
    """Fail if this replay's ordering/rejection semantics drift from TypeScript."""
    non_bmp = "\U00010000"
    bmp_after_surrogate_range = "\uE000"
    if utf16_code_unit_sort_key(non_bmp) >= utf16_code_unit_sort_key(
        bmp_after_surrogate_range
    ):
        fail("UTF-16 non-BMP ordering self-check failed")
    expected = ('{"' + non_bmp + '":1,"' + bmp_after_surrogate_range + '":0}').encode(
        "utf-8"
    )
    if canonical_json_bytes({bmp_after_surrogate_range: 0, non_bmp: 1}) != expected:
        fail("UTF-16 canonical object ordering self-check failed")
    for malformed in ("\ud800", "\udc00", "prefix\ud800suffix"):
        try:
            canonical_json_bytes({"key": malformed})
        except SystemExit:
            continue
        fail("lone-surrogate rejection self-check failed")


def decode_base64url(value: Any, field: str) -> bytes:
    if not isinstance(value, str) or BASE64URL.fullmatch(value) is None:
        fail(f"{field} is not unpadded base64url")
    try:
        decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, binascii.Error) as error:
        fail(f"{field}: {error}")
    if base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii") != value:
        fail(f"{field} is not minimally encoded")
    return decoded


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def replay_fixed_vector(vector_path: Path) -> dict[str, Any]:
    assert_canonical_json_contract()
    vector = decode_json_exact(vector_path.read_bytes())
    if not isinstance(vector, dict):
        fail("vector root is not an object")
    if vector.get("schema") != "hswm-canonical-permit-envelope-test-vector/v1":
        fail("unexpected vector schema")
    if (
        vector.get("publicKeySpkiDerBase64Url")
        != PINNED_PUBLIC_KEY_SPKI_DER_BASE64URL
    ):
        fail("vector public key differs from the pinned RFC 8032 test key")
    if vector.get("signingDocumentSha256") != PINNED_SIGNING_DOCUMENT_SHA256:
        fail("vector signing-document digest differs from the pinned vector")
    if vector.get("envelopeSha256") != PINNED_ENVELOPE_SHA256:
        fail("vector envelope digest differs from the pinned vector")
    if (
        vector.get("expectedVerificationStatus")
        != PINNED_CALLER_CONTEXT_VERIFICATION_STATUS
    ):
        fail("vector verification status differs from the pinned nonclaim")

    signing_bytes = decode_base64url(
        vector.get("signingDocumentCanonicalBase64Url"),
        "signingDocumentCanonicalBase64Url",
    )
    envelope_bytes = decode_base64url(
        vector.get("envelopeCanonicalBase64Url"),
        "envelopeCanonicalBase64Url",
    )
    if sha256(signing_bytes) != vector.get("signingDocumentSha256"):
        fail("signing-document SHA-256 mismatch")
    if sha256(envelope_bytes) != vector.get("envelopeSha256"):
        fail("envelope SHA-256 mismatch")

    signing_document = decode_json_exact(signing_bytes)
    envelope = decode_json_exact(envelope_bytes)
    if canonical_json_bytes(signing_document) != signing_bytes:
        fail("signing document is not independently canonical")
    if canonical_json_bytes(envelope) != envelope_bytes:
        fail("envelope is not independently canonical")
    if not isinstance(envelope, dict):
        fail("envelope root is not an object")

    reconstructed = dict(envelope)
    signature = decode_base64url(reconstructed.pop("signature", None), "signature")
    if len(signature) != 64:
        fail("Ed25519 signature is not 64 bytes")
    if canonical_json_bytes(reconstructed) != signing_bytes:
        fail("envelope does not reconstruct the pinned signing document")

    public_key = decode_base64url(
        vector.get("publicKeySpkiDerBase64Url"),
        "publicKeySpkiDerBase64Url",
    )
    with tempfile.TemporaryDirectory(prefix="hswm-permit-vector-") as directory:
        temporary = Path(directory)
        public_path = temporary / "public.der"
        message_path = temporary / "message.bin"
        signature_path = temporary / "signature.bin"
        public_path.write_bytes(public_key)
        message_path.write_bytes(signing_bytes)
        signature_path.write_bytes(signature)
        completed = subprocess.run(
            [
                "openssl",
                "pkeyutl",
                "-verify",
                "-pubin",
                "-inkey",
                str(public_path),
                "-keyform",
                "DER",
                "-rawin",
                "-in",
                str(message_path),
                "-sigfile",
                str(signature_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    if completed.returncode != 0:
        fail(completed.stderr.strip() or completed.stdout.strip() or "OpenSSL rejected")

    return {
        "schema": "hswm-canonical-permit-envelope-fixed-vector-replay/v1",
        "scope": "FIXED_VECTOR_BYTES_SIGNATURE_AND_RESTRICTED_CANONICAL_JSON_ONLY",
        "signingDocumentSha256": sha256(signing_bytes),
        "envelopeSha256": sha256(envelope_bytes),
        "signatureAlgorithm": "Ed25519",
        "cryptoConsumer": "openssl-pkeyutl",
        "status": "FIXED_VECTOR_REPLAY_PASSED_NOT_GENERAL_SCHEMA_PERMIT_ADMISSION_OR_LEARNING_VERIFIER",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("vector", nargs="?", type=Path, default=DEFAULT_VECTOR)
    args = parser.parse_args()
    print(canonical_json_bytes(replay_fixed_vector(args.vector)).decode("utf-8"))


if __name__ == "__main__":
    main()
