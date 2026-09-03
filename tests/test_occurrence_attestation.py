from __future__ import annotations

import base64
from hashlib import sha256
from pathlib import Path

import pytest

from hswm.infrastructure.occurrence_attestation import (
    DSSE_PAYLOAD_TYPE, HSWM_STRICT_ATTESTATION_PROFILE_V1, DsseEnvelopeV1, InTotoStatementV1, OccurrenceAttestationError,
    cosign_attest_blob_argv, cosign_verify_blob_attestation_argv,
    cosign_verify_blob_attestation_artifact_argv, cosign_verify_blob_argv,
    rfc3161_query_argv, rfc3161_submit_argv, rfc3161_verify_argv,
    rfc3161_verify_query_argv, verify_with_pinned_binary,
)
from hswm.infrastructure.occurrence_integrity import ContentDescriptorV1


def statement_bytes() -> bytes:
    return InTotoStatementV1(ContentDescriptorV1("application/json", "a" * 64, 7), "registration.json", "https://example.test/predicate/v1", {"x": "y"}).bytes()


def envelope() -> dict:
    return {"payloadType": DSSE_PAYLOAD_TYPE, "payload": base64.b64encode(statement_bytes()).decode(),
            "signatures": [{"keyid": "key-1", "sig": base64.b64encode(b"sig").decode()}]}


def test_intoto_round_trip_and_dsse_is_unverified() -> None:
    parsed = InTotoStatementV1.from_bytes(statement_bytes())
    assert parsed.subject.sha256 == "a" * 64
    assert parsed.subject_name == "registration.json"
    envelope_value = DsseEnvelopeV1.from_mapping(envelope())
    assert envelope_value.statement.predicate == {"x": "y"}
    assert envelope_value.cryptographically_verified is False
    assert "exactly one" in HSWM_STRICT_ATTESTATION_PROFILE_V1


def test_attestation_json_rejects_duplicate_keys_and_nonfinite_numbers() -> None:
    with pytest.raises(OccurrenceAttestationError, match="duplicate key"):
        InTotoStatementV1.from_bytes(b'{"_type":"a","_type":"b"}')
    with pytest.raises(OccurrenceAttestationError, match="non-finite"):
        InTotoStatementV1.from_bytes(b'{"value":NaN}')


@pytest.mark.parametrize("mutate", [
    lambda value: value.update(payloadType="application/json"),
    lambda value: value.update(payload="%%%"),
    lambda value: value.update(signatures=[]),
    lambda value: value.update(signatures=[{"keyid": "x", "sig": "c2ln"}, {"keyid": "x", "sig": "c2ln"}]),
])
def test_dsse_rejects_mutation(mutate) -> None:
    value = envelope()
    mutate(value)
    with pytest.raises(OccurrenceAttestationError):
        DsseEnvelopeV1.from_mapping(value)


def test_direct_argv_builders(tmp_path: Path) -> None:
    blob = tmp_path / "blob"; bundle = tmp_path / "bundle"; response = tmp_path / "response"; ca = tmp_path / "ca"; trusted_root = tmp_path / "trusted-root.json"
    for path in (blob, response, ca, trusted_root): path.write_bytes(b"x")
    attest = cosign_attest_blob_argv(cosign="cosign", blob=blob, statement=response, bundle=bundle)
    assert attest == ("cosign", "attest-blob", "--statement", str(response.resolve()), "--bundle", str(bundle.resolve()), "--yes", str(blob.resolve()))
    assert not any("token" in item.lower() or "password" in item.lower() for item in attest)
    bundle.write_bytes(b"x")
    cosign = cosign_verify_blob_argv(cosign="cosign", blob=blob, bundle=bundle, trusted_root=trusted_root, identity="id", issuer="issuer")
    assert cosign == ("cosign", "verify-blob", "--bundle", str(bundle.resolve()), "--trusted-root", str(trusted_root.resolve()), "--certificate-identity", "id", "--certificate-oidc-issuer", "issuer", str(blob.resolve()))
    statement_output = tmp_path / "verified-statement.json"
    verify_attestation = cosign_verify_blob_attestation_argv(
        cosign="cosign", bundle=bundle, statement_output=statement_output,
        trusted_root=trusted_root, identity="id", issuer="issuer"
    )
    assert verify_attestation == (
        "cosign", "verify-blob-attestation", "--statement-only", "--bundle", str(bundle.resolve()),
        "--trusted-root", str(trusted_root.resolve()),
        "--certificate-identity", "id", "--certificate-oidc-issuer", "issuer",
        "--output-file", str(statement_output.resolve()),
    )
    assert str(blob.resolve()) not in verify_attestation
    artifact_verify = cosign_verify_blob_attestation_artifact_argv(
        cosign="cosign", blob=blob, bundle=bundle, trusted_root=trusted_root,
        identity="id", issuer="issuer"
    )
    assert artifact_verify[-1] == str(blob.resolve())
    assert "--trusted-root" in artifact_verify
    assert rfc3161_verify_argv(openssl="openssl", blob=blob, response=response, ca_file=ca)[1:4] == ("ts", "-verify", "-data")

    with pytest.raises(OccurrenceAttestationError, match="must not already exist"):
        cosign_attest_blob_argv(cosign="cosign", blob=blob, statement=response, bundle=bundle)


def test_pinned_binary_mismatch_refuses_before_execution(tmp_path: Path) -> None:
    executable = tmp_path / "verifier"
    executable.write_text("not executable")
    with pytest.raises(OccurrenceAttestationError, match="SHA-256 mismatch"):
        verify_with_pinned_binary(argv=(str(executable), "verify"), executable=executable,
                                  executable_sha256="0" * 64, expected_version_text="x")


def test_pinned_verifier_executes_only_exact_open_input_bytes(tmp_path: Path) -> None:
    executable = tmp_path / "verifier"
    executable.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = version ]; then printf 'verifier-v1\\n'; exit 0; fi\n"
        "[ \"$(cat \"$2\")\" = 'bound-input' ]\n",
        encoding="utf-8",
    )
    executable.chmod(0o700)
    payload = tmp_path / "payload"
    payload.write_bytes(b"bound-input")
    executable_sha256 = sha256(executable.read_bytes()).hexdigest()
    payload_sha256 = sha256(payload.read_bytes()).hexdigest()

    result = verify_with_pinned_binary(
        argv=(str(executable.resolve()), "verify", str(payload.resolve())),
        executable=executable,
        executable_sha256=executable_sha256,
        expected_version_text="verifier-v1\n",
        pinned_inputs={payload: payload_sha256},
    )
    assert result.verified is True

    with pytest.raises(OccurrenceAttestationError, match="input SHA-256 mismatch"):
        verify_with_pinned_binary(
            argv=(str(executable.resolve()), "verify", str(payload.resolve())),
            executable=executable,
            executable_sha256=executable_sha256,
            expected_version_text="verifier-v1\n",
            pinned_inputs={payload: "0" * 64},
        )


def test_rfc3161_live_path_binds_nonce_and_refuses_implicit_network(tmp_path: Path) -> None:
    blob = tmp_path / "blob"
    request = tmp_path / "request.tsq"
    response = tmp_path / "response.tsr"
    ca = tmp_path / "tsa-ca.pem"
    blob.write_bytes(b"exact signed envelope")
    ca.write_bytes(b"trust root")

    query = rfc3161_query_argv(openssl="openssl", blob=blob, request=request)
    assert query[1:5] == ("ts", "-query", "-data", str(blob.resolve()))
    assert "-sha256" in query and "-cert" in query
    request.write_bytes(b"nonce-bearing request")

    with pytest.raises(OccurrenceAttestationError, match="allow_network"):
        rfc3161_submit_argv(
            curl="curl", request=request, response=response,
            tsa_url="https://tsa.example.test/timestamp",
        )
    submit = rfc3161_submit_argv(
        curl="curl", request=request, response=response,
        tsa_url="https://tsa.example.test/timestamp", allow_network=True,
    )
    assert "Content-Type: application/timestamp-query" in submit
    assert str(response.resolve()) in submit
    response.write_bytes(b"timestamp response")
    verify = rfc3161_verify_query_argv(
        openssl="openssl", request=request, response=response, ca_file=ca
    )
    assert verify[1:4] == ("ts", "-verify", "-queryfile")

    with pytest.raises(OccurrenceAttestationError, match="credential-free"):
        rfc3161_submit_argv(
            curl="curl", request=request, response=tmp_path / "other.tsr",
            tsa_url="https://token@tsa.example.test/timestamp", allow_network=True,
        )
