from __future__ import annotations

import base64
from hashlib import sha256
import json
from pathlib import Path

import pytest

from hswm.infrastructure import occurrence_cli
from hswm.infrastructure.occurrence_attestation import (
    DSSE_PAYLOAD_TYPE,
    InTotoStatementV1,
)
from hswm.infrastructure.occurrence_integrity import ContentDescriptorV1


def _output(capsys: pytest.CaptureFixture[str]) -> dict:
    return json.loads(capsys.readouterr().out)


def test_describe_and_statement_bind_exact_local_bytes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    subject = tmp_path / "registration.json"
    predicate = tmp_path / "predicate.json"
    subject.write_bytes(b'{"frozen":true}\n')
    predicate.write_text('{"kind":"registration"}', encoding="utf-8")

    assert occurrence_cli.main(
        ["describe", str(subject), "--media-type", "application/json"]
    ) == 0
    descriptor = _output(capsys)
    assert descriptor == {
        "byte_length": len(subject.read_bytes()),
        "media_type": "application/json",
        "sha256": sha256(subject.read_bytes()).hexdigest(),
    }

    assert occurrence_cli.main(
        [
            "statement",
            "--subject",
            str(subject),
            "--subject-name",
            "registration.json",
            "--media-type",
            "application/json",
            "--predicate-type",
            "https://hswm.example/predicate/occurrence-registration/v1",
            "--predicate",
            str(predicate),
        ]
    ) == 0
    statement = _output(capsys)
    assert statement["_type"] == "https://in-toto.io/Statement/v1"
    assert statement["subject"] == [
        {
            "digest": {"sha256": descriptor["sha256"]},
            "name": "registration.json",
        }
    ]


def test_parse_dsse_never_claims_cryptographic_verification(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    statement = InTotoStatementV1(
        ContentDescriptorV1("application/json", "a" * 64, 1),
        "registration.json",
        "https://hswm.example/predicate/v1",
        {"frozen": True},
    ).bytes()
    envelope = {
        "payloadType": DSSE_PAYLOAD_TYPE,
        "payload": base64.b64encode(statement).decode("ascii"),
        "signatures": [
            {"keyid": "external-key", "sig": base64.b64encode(b"sig").decode("ascii")}
        ],
    }
    path = tmp_path / "envelope.json"
    path.write_text(json.dumps(envelope), encoding="utf-8")

    assert occurrence_cli.main(["parse-dsse", str(path)]) == 0
    parsed = _output(capsys)
    assert parsed["cryptographically_verified"] is False
    assert parsed["signature_keyids"] == ["external-key"]
    assert "sig" not in parsed
    assert "payload" not in parsed


def test_workflow_options_are_one_shot(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert occurrence_cli.main(["workflow-options", "occurrence-001"]) == 0
    options = _output(capsys)
    assert options["workflow_id"] == "g0-occurrence/occurrence-001"
    assert options["workflow_id_reuse_policy"] == "REJECT_DUPLICATE"
    assert options["workflow_retry_policy"] == {"maximum_attempts": 1}
    assert options["activity_retry_policy"] == {"maximum_attempts": 1}
    assert options["replacement_round_allowed"] is False


def test_raw_json_publication_command_is_not_exposed() -> None:
    """A mapping must not bypass the guarded in-process completion receipt."""

    with pytest.raises(SystemExit) as error:
        occurrence_cli.main(["publication"])
    assert error.value.code == 2


def test_bad_json_exits_fail_closed(tmp_path: Path) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("not json", encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        occurrence_cli.main(["parse-dsse", str(broken)])
    assert error.value.code == 2


def test_external_write_commands_are_emitted_but_never_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    body = tmp_path / "claim.json"
    statement = tmp_path / "statement.json"
    bundle = tmp_path / "bundle.json"
    request = tmp_path / "request.tsq"
    body.write_bytes(b'{"occurrence_uid":"occurrence-001"}\n')
    statement.write_bytes(b'{"_type":"https://in-toto.io/Statement/v1"}\n')

    assert occurrence_cli.main(
        [
            "worm-command", "--bucket", "hswm-occurrence.example",
            "--occurrence-uid", "occurrence-001", "--body", str(body),
            "--retain-until", "2027-09-03T00:00:00Z",
            "--claimant-account-id", "111111111111",
            "--admin-account-id", "222222222222",
        ]
    ) == 0
    worm = _output(capsys)
    assert worm["execution"] == "NOT_EXECUTED"
    assert worm["argv"][1:3] == ["s3api", "put-object"]

    assert occurrence_cli.main(
        [
            "cosign-attest-command", "--blob", str(body), "--statement",
            str(statement), "--bundle", str(bundle),
        ]
    ) == 0
    cosign = _output(capsys)
    assert cosign["execution"] == "NOT_EXECUTED"
    assert cosign["argv"][:2] == ["cosign", "attest-blob"]

    assert occurrence_cli.main(
        [
            "rfc3161-query-command", "--blob", str(bundle if bundle.exists() else body),
            "--request", str(request),
        ]
    ) == 0
    timestamp = _output(capsys)
    assert timestamp["execution"] == "NOT_EXECUTED"
    assert timestamp["argv"][1:3] == ["ts", "-query"]
