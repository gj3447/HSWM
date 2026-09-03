from __future__ import annotations

from dataclasses import replace

import pytest

from hswm.infrastructure import occurrence_registration as registration


PACKAGE = registration.ContentDescriptor("protocol/package.json", "a" * 64, 21)
REGISTRATION = {
    "data": {
        "id": "abc12",
        "type": "registrations",
        "attributes": {"date_registered": "2026-09-03T00:00:00Z", "withdrawn": False},
        "links": {"self": "https://api.osf.io/v2/registrations/abc12/"},
    }
}
FILE = {
    "data": {
        "id": "file123",
        "type": "files",
        "attributes": {"name": "protocol/package.json", "size": 21, "extra": {"hashes": {"sha256": "a" * 64}}},
        "links": {
            "self": "https://api.osf.io/v2/files/file123/",
            "download": "https://files.osf.io/v1/resources/abc12/providers/osfstorage/file123",
        },
    }
}


def test_matching_pre_pulse_osf_readback_is_only_audit_candidate() -> None:
    result = registration.parse_osf_registration_readback(
        REGISTRATION, FILE, expected_package=PACKAGE, read_back_bytes=PACKAGE,
        read_back_download_url="https://files.osf.io/v1/resources/abc12/providers/osfstorage/file123", pulse_timestamp="2026-09-03T00:00:03Z"
    )
    assert result.status == registration.AUDIT_CANDIDATE
    assert result.reason is None
    assert "not preregistration success" in result.claim_boundary
    assert result.registration_id == "abc12"
    assert result.file_metadata_url == "https://api.osf.io/v2/files/file123/"
    assert result.file_download_url == "https://files.osf.io/v1/resources/abc12/providers/osfstorage/file123"


def test_withdrawal_byte_mismatch_and_late_registration_are_void() -> None:
    withdrawn = {"data": {**REGISTRATION["data"], "attributes": {"date_registered": "2026-09-03T00:00:00Z", "withdrawn": True}}}
    assert registration.parse_osf_registration_readback(withdrawn, FILE, expected_package=PACKAGE, read_back_bytes=PACKAGE, read_back_download_url="https://files.osf.io/v1/resources/abc12/providers/osfstorage/file123", pulse_timestamp="2026-09-03T00:00:03Z").status == registration.VOID
    mismatch = replace(PACKAGE, sha256="b" * 64)
    assert registration.parse_osf_registration_readback(REGISTRATION, FILE, expected_package=PACKAGE, read_back_bytes=mismatch, read_back_download_url="https://files.osf.io/v1/resources/abc12/providers/osfstorage/file123", pulse_timestamp="2026-09-03T00:00:03Z").status == registration.VOID
    late = registration.parse_osf_registration_readback(REGISTRATION, FILE, expected_package=PACKAGE, read_back_bytes=PACKAGE, read_back_download_url="https://files.osf.io/v1/resources/abc12/providers/osfstorage/file123", pulse_timestamp="2026-09-03T00:00:00Z")
    assert late.status == registration.VOID
    assert late.reason == "REGISTRATION_NOT_STRICTLY_BEFORE_PULSE"


def test_official_urls_and_opt_in_unauthenticated_curl_only() -> None:
    argv = registration.build_osf_readback_get_argv("https://api.osf.io/v2/registrations/abc12/", allow_network=True)
    assert argv[-1] == "https://api.osf.io/v2/registrations/abc12/"
    assert ("--proto", "=https", "--proto-redir", "=https") == argv[5:9]
    assert not any("token" in value.lower() or "authorization" in value.lower() for value in argv)
    with pytest.raises(registration.OccurrenceRegistrationError, match="allow_network"):
        registration.build_osf_readback_get_argv(argv[-1])
    bad = {"data": {**REGISTRATION["data"], "links": {"self": "http://evil.example/abc12/"}}}
    with pytest.raises(registration.OccurrenceRegistrationError, match="canonical OSF"):
        registration.parse_osf_registration_readback(bad, FILE, expected_package=PACKAGE, read_back_bytes=PACKAGE, read_back_download_url="https://files.osf.io/v1/resources/abc12/providers/osfstorage/file123", pulse_timestamp="2026-09-03T00:00:03Z")


def test_raw_bytes_must_be_provenanced_to_links_download() -> None:
    with pytest.raises(registration.OccurrenceRegistrationError, match="exactly match"):
        registration.parse_osf_registration_readback(
            REGISTRATION, FILE, expected_package=PACKAGE, read_back_bytes=PACKAGE,
            read_back_download_url="https://files.osf.io/v1/resources/other1/providers/osfstorage/file123", pulse_timestamp="2026-09-03T00:00:03Z",
        )


def test_official_swagger_url_shapes_are_enforced() -> None:
    bad_self = {
        "data": {
            **FILE["data"],
            "links": {
                **FILE["data"]["links"],
                "self": "https://api.osf.io/v2/files/osfstorage/file123/",
            },
        }
    }
    with pytest.raises(registration.OccurrenceRegistrationError, match="API v2 file URL"):
        registration.parse_osf_registration_readback(
            REGISTRATION,
            bad_self,
            expected_package=PACKAGE,
            read_back_bytes=PACKAGE,
            read_back_download_url=FILE["data"]["links"]["download"],
            pulse_timestamp="2026-09-03T00:00:03Z",
        )
