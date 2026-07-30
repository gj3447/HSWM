"""ooptdd v2.9 — ed25519 signatures for audit records (G1 closure).

The audit chain binds WHAT was judged (record_hash over canonical JSON) but
until now not WHO judged it: auditor_id was a bare string (2026-07-28 OSS
coverage gap G1). This module signs the record_hash with ed25519 so an audit
record carries non-repudiable identity:

  record["signature"] = {
      "scheme":  "ed25519-rfc8032",
      "payload": "record_hash",          # what is signed, explicitly
      "pubkey":  "<64 hex>",
      "sig":     "<128 hex>",
  }

record_hash() excludes BOTH "hash" and "signature" (backward compatible:
legacy records have no signature key, so their hashes are unchanged).

Identity policy (enforced in audit_policy, progressive like R1/R3):
  verified   — sig checks out AND pubkey == registry pubkey for auditor_id
  untrusted  — sig checks out but auditor has no registry pubkey yet
  absent     — no signature (legacy / key not available); flagged, chained
  REFUSED    — sig invalid, or key's pubkey contradicts the registry
               (impersonation-shaped; fail-closed like the chain itself)

Implementation: pure-Python ed25519 per RFC 8032 (stdlib only — the venv has
neither cryptography nor PyNaCl, checked 2026-07-28). Correctness is pinned
by the RFC's own test vectors in tests/test_signing.py. Performance is not
the constraint (one signature per audit record); auditability is.

Keys: OOPTDD_KEY_DIR or ~/.config/ooptdd/keys/<auditor_id>.key (hex, 0600).
Private keys NEVER live in the repo; only pubkeys enter auditors.json.
"""
from __future__ import annotations

import hashlib
import json
import os

# --- RFC 8032 ed25519, pow()-accelerated reference form ----------------------

_b = 256
_q = 2**255 - 19
_l = 2**252 + 27742317777372353535851937790883648493


def _H(m: bytes) -> bytes:
    return hashlib.sha512(m).digest()


def _inv(x: int) -> int:
    return pow(x, _q - 2, _q)


_d = (-121665 * _inv(121666)) % _q
_I = pow(2, (_q - 1) // 4, _q)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * _inv(_d * y * y + 1)
    x = pow(xx, (_q + 3) // 8, _q)
    if (x * x - xx) % _q != 0:
        x = (x * _I) % _q
    if x % 2 != 0:
        x = _q - x
    return x


_By = 4 * _inv(5)
_Bx = _xrecover(_By)
_B = (_Bx % _q, _By % _q)
_IDENTITY = (0, 1)


def _edwards(P: tuple[int, int], Q: tuple[int, int]) -> tuple[int, int]:
    x1, y1 = P
    x2, y2 = Q
    denom = _d * x1 * x2 * y1 * y2
    x3 = (x1 * y2 + x2 * y1) * _inv(1 + denom)
    y3 = (y1 * y2 + x1 * x2) * _inv(1 - denom)
    return (x3 % _q, y3 % _q)


def _scalarmult(P: tuple[int, int], e: int) -> tuple[int, int]:
    Q = _IDENTITY
    while e > 0:
        if e & 1:
            Q = _edwards(Q, P)
        P = _edwards(P, P)
        e >>= 1
    return Q


def _encodeint(y: int) -> bytes:
    return y.to_bytes(_b // 8, "little")


def _encodepoint(P: tuple[int, int]) -> bytes:
    x, y = P
    return (y | ((x & 1) << (_b - 1))).to_bytes(_b // 8, "little")


def _decodeint(s: bytes) -> int:
    return int.from_bytes(s, "little")


def _isoncurve(P: tuple[int, int]) -> bool:
    x, y = P
    return (-x * x + y * y - 1 - _d * x * x * y * y) % _q == 0


def _decodepoint(s: bytes) -> tuple[int, int]:
    if len(s) != _b // 8:
        raise ValueError("point encoding length is wrong")
    y = int.from_bytes(s, "little") & ((1 << (_b - 1)) - 1)
    x = _xrecover(y)
    if x & 1 != (s[-1] >> 7):
        x = _q - x
    P = (x, y)
    if not _isoncurve(P):
        raise ValueError("decoding point that is not on curve")
    return P


def _clamped_scalar(h: bytes) -> int:
    a = bytearray(h[:32])
    a[0] &= 248
    a[31] &= 63
    a[31] |= 64
    return int.from_bytes(a, "little")


def publickey(sk: bytes) -> bytes:
    if len(sk) != 32:
        raise ValueError("ed25519 secret key must be 32 bytes")
    return _encodepoint(_scalarmult(_B, _clamped_scalar(_H(sk))))


def sign(m: bytes, sk: bytes) -> bytes:
    h = _H(sk)
    a = _clamped_scalar(h)
    pk = _encodepoint(_scalarmult(_B, a))
    r = int.from_bytes(_H(h[32:] + m), "little") % _l
    R = _encodepoint(_scalarmult(_B, r))
    S = (r + int.from_bytes(_H(R + pk + m), "little") * a) % _l
    return R + _encodeint(S)


def verify_signature(sig: bytes, m: bytes, pk: bytes) -> bool:
    """RFC 8032 verification; returns False (never raises) on any invalid input."""
    try:
        if len(sig) != 64 or len(pk) != 32:
            return False
        R = _decodepoint(sig[:32])
        A = _decodepoint(pk)
        S = _decodeint(sig[32:])
        if S >= _l:
            return False
        h = int.from_bytes(_H(sig[:32] + pk + m), "little") % _l
        return _scalarmult(_B, S) == _edwards(R, _scalarmult(A, h))
    except (ValueError, IndexError):
        return False


# --- key files + record-level helpers ---------------------------------------

SCHEME = "ed25519-rfc8032"
DEFAULT_KEY_DIR = os.path.expanduser("~/.config/ooptdd/keys")


def key_dir() -> str:
    return os.environ.get("OOPTDD_KEY_DIR", DEFAULT_KEY_DIR)


def key_path(auditor_id: str, directory: str | None = None) -> str:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in auditor_id)
    return os.path.join(directory or key_dir(), f"{safe}.key")


def generate_keypair() -> tuple[bytes, bytes]:
    sk = os.urandom(32)
    return sk, publickey(sk)


def genkey(auditor_id: str, directory: str | None = None) -> dict:
    """Create a keypair, write the private key 0600, return the pubkey info.

    Refuses to overwrite an existing key (rotation must be deliberate)."""
    path = key_path(auditor_id, directory)
    if os.path.exists(path):
        raise ValueError(f"key already exists for {auditor_id}: {path} (delete it deliberately to rotate)")
    sk, pk = generate_keypair()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(sk.hex() + "\n")
    return {"auditor_id": auditor_id, "pubkey": pk.hex(), "key_path": path}


def load_secret(auditor_id: str, directory: str | None = None) -> bytes | None:
    path = key_path(auditor_id, directory)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return bytes.fromhex(f.read().strip())


def sign_record(record_hash_hex: str, sk: bytes) -> dict:
    """Sign a chained-record hash; the block goes into record['signature']."""
    pk = publickey(sk)
    sig = sign(record_hash_hex.encode("ascii"), sk)
    return {"scheme": SCHEME, "payload": "record_hash", "pubkey": pk.hex(), "sig": sig.hex()}


def verify_record_signature(record: dict) -> bool:
    """Verify a record's signature block against its own recomputed hash."""
    from ooptdd.receipt_log import record_hash

    block = record.get("signature")
    if not isinstance(block, dict):
        return False
    if block.get("scheme") != SCHEME or block.get("payload") != "record_hash":
        return False
    try:
        pk = bytes.fromhex(block["pubkey"])
        sig = bytes.fromhex(block["sig"])
    except (KeyError, ValueError):
        return False
    return verify_signature(sig, record_hash(record).encode("ascii"), pk)
