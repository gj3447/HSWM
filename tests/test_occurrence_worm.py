from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from hswm.infrastructure.occurrence_worm import (
    WormClaimTerminal,
    build_s3_worm_claim_command,
    build_s3_worm_claim_readback_commands,
    classify_s3_worm_claim_result,
)


def command(tmp_path: Path):
    body = tmp_path / "claim.json"
    body.write_bytes(b'{"occurrence":"g0-001"}\n')
    digest = sha256(body.read_bytes()).hexdigest()
    return build_s3_worm_claim_command(
        bucket="hswm-g0-worm.example",
        occurrence_uid="g0-001",
        body_file=body,
        expected_body_sha256=digest,
        retain_until="2027-01-01T00:00:00Z",
        claimant_account_id="111111111111",
        admin_account_id="222222222222",
    )


def put_metadata() -> dict[str, str]:
    return {
        "VersionId": "version-001",
        "ETag": '"etag-001"',
        "ChecksumSHA256": "placeholder",
    }


def head_metadata(value) -> dict[str, str]:
    return {
        "VersionId": "version-001",
        "ETag": '"etag-001"',
        "ChecksumSHA256": value.checksum_sha256_base64,
    }


def retention_metadata(value) -> dict[str, dict[str, str]]:
    return {"Retention": {"Mode": "COMPLIANCE", "RetainUntilDate": value.retain_until}}


def test_command_is_exact_conditional_compliance_write(tmp_path: Path) -> None:
    value = command(tmp_path)

    assert value.key == "occurrences/g0-001/claim.json"
    assert value.claimant_account_id != value.admin_account_id
    assert value.argv == (
        "aws", "s3api", "put-object", "--bucket", "hswm-g0-worm.example",
        "--key", "occurrences/g0-001/claim.json", "--body", str(value.body_file),
        "--if-none-match", "*", "--checksum-algorithm", "SHA256",
        "--checksum-sha256", value.checksum_sha256_base64, "--object-lock-mode",
        "COMPLIANCE", "--object-lock-retain-until-date", "2027-01-01T00:00:00Z",
        "--expected-bucket-owner", "222222222222", "--no-cli-pager",
    )


def test_success_needs_version_pinned_readback(tmp_path: Path) -> None:
    value = command(tmp_path)
    put = {**put_metadata(), "ChecksumSHA256": value.checksum_sha256_base64}
    readbacks = build_s3_worm_claim_readback_commands(value, version_id="version-001")
    assert "head-object" in readbacks.head_object_argv
    assert "get-object-retention" in readbacks.get_retention_argv
    assert "version-001" in readbacks.head_object_argv
    assert readbacks.head_object_argv[-2:] == ("--checksum-mode", "ENABLED")
    result = classify_s3_worm_claim_result(
        value, http_status=200, put_response_metadata=put,
        head_object_metadata=head_metadata(value), retention_metadata=retention_metadata(value),
    )

    assert result.terminal is WormClaimTerminal.CANDIDATE_CLAIMED
    assert result.retry_permitted is False

    normalized_retention = classify_s3_worm_claim_result(
        value, http_status=200, put_response_metadata=put,
        head_object_metadata=head_metadata(value),
        retention_metadata={
            "Retention": {
                "Mode": "COMPLIANCE",
                "RetainUntilDate": "2027-01-01T00:00:00+00:00",
            }
        },
    )
    assert normalized_retention.terminal is WormClaimTerminal.CANDIDATE_CLAIMED

    no_readback = classify_s3_worm_claim_result(
        value, http_status=200, put_response_metadata=put
    )
    assert no_readback.terminal is WormClaimTerminal.INCONCLUSIVE
    assert no_readback.retry_permitted is False

    invalid = classify_s3_worm_claim_result(
        value, http_status=200, put_response_metadata=put,
        head_object_metadata=head_metadata(value),
        retention_metadata={"Retention": {"Mode": "GOVERNANCE", "RetainUntilDate": value.retain_until}},
    )
    assert invalid.terminal is WormClaimTerminal.INCONCLUSIVE
    assert invalid.retry_permitted is False


@pytest.mark.parametrize("status", (409, 412))
def test_duplicate_statuses_are_terminal_void(tmp_path: Path, status: int) -> None:
    result = classify_s3_worm_claim_result(
        command(tmp_path), http_status=status, put_response_metadata={}
    )

    assert result.terminal is WormClaimTerminal.VOID_DUPLICATE
    assert result.retry_permitted is False


def test_other_failures_are_inconclusive_without_retry(tmp_path: Path) -> None:
    result = classify_s3_worm_claim_result(
        command(tmp_path), http_status=503, put_response_metadata={"ETag": '"partial"'}
    )

    assert result.terminal is WormClaimTerminal.INCONCLUSIVE
    assert result.retry_permitted is False


def test_body_drift_and_same_account_are_refused_before_command(tmp_path: Path) -> None:
    body = tmp_path / "claim.json"
    body.write_text("bytes", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        build_s3_worm_claim_command(
            bucket="hswm-g0-worm.example", occurrence_uid="g0-001", body_file=body,
            expected_body_sha256="0" * 64, retain_until="2027-01-01T00:00:00Z",
            claimant_account_id="111111111111", admin_account_id="222222222222",
        )
    with pytest.raises(ValueError, match="distinct"):
        build_s3_worm_claim_command(
            bucket="hswm-g0-worm.example", occurrence_uid="g0-001", body_file=body,
            expected_body_sha256=sha256(body.read_bytes()).hexdigest(),
            retain_until="2027-01-01T00:00:00Z", claimant_account_id="111111111111",
            admin_account_id="111111111111",
        )
    with pytest.raises(ValueError, match="RFC3339"):
        build_s3_worm_claim_command(
            bucket="hswm-g0-worm.example", occurrence_uid="g0-001", body_file=body,
            expected_body_sha256=sha256(body.read_bytes()).hexdigest(),
            retain_until="not-a-timeZ", claimant_account_id="111111111111",
            admin_account_id="222222222222",
        )


def test_readback_rejects_option_like_version_id(tmp_path: Path) -> None:
    value = command(tmp_path)
    with pytest.raises(ValueError, match="non-option"):
        build_s3_worm_claim_readback_commands(value, version_id="--unexpected-option")
