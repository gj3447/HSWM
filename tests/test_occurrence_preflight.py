from __future__ import annotations

from types import SimpleNamespace

from hswm.infrastructure import occurrence_preflight
from hswm.infrastructure.occurrence_preflight import (
    BLOCKED_EXTERNAL_STATUS,
    READY_STATUS,
    REQUIRED_EXTERNAL_BINDINGS,
    run_occurrence_preflight,
)


def binaries(*, cosign: str = "3.1.3", temporal: str = "1.8.3"):
    paths = {
        "cosign": "/candidate/cosign",
        "temporal": "/candidate/temporal",
        "aws": "/candidate/aws",
        "openssl": "/candidate/openssl",
    }
    outputs = {
        paths["cosign"]: f"cosign version {cosign}",
        paths["temporal"]: f"temporal version {temporal}",
        paths["aws"]: "aws-cli/2.36.36",
        paths["openssl"]: "OpenSSL 3.5.6 7 Apr 2026",
    }
    return lambda name: paths.get(name), lambda path: outputs.get(path)


def complete_environ() -> dict[str, str]:
    return {
        **{name: f"secret-or-endpoint-{index}" for index, name in enumerate(REQUIRED_EXTERNAL_BINDINGS)},
        "HSWM_G0_ACTOR_ROLE_ID": "operator-a.example",
        "HSWM_G0_REVISION_PROPOSER_ROLE_ID": "proposer-b.example",
        "HSWM_G0_OCCURRENCE_CLAIMANT_ROLE_ID": "claimant-c.example",
        "HSWM_G0_WORM_ADMINISTRATOR_ROLE_ID": "admin-d.example",
        "HSWM_G0_CUSTODIAN_ROLE_ID": "custodian-e.example",
        "HSWM_G0_DRAND_VERIFIER_ROLE_ID": "drand-verifier-f.example",
        "HSWM_G0_EVALUATOR_A_ROLE_ID": "evaluator-g.example",
        "HSWM_G0_EVALUATOR_B_ROLE_ID": "evaluator-h.example",
        "HSWM_G0_EXTERNAL_AUDITOR_ROLE_ID": "auditor-i.example",
    }


def test_current_missing_style_is_blocked_external() -> None:
    which, version = binaries()
    report = run_occurrence_preflight(environ={}, which=which, version=version)

    assert report.status == BLOCKED_EXTERNAL_STATUS
    assert report.local_engineering_ready is True
    assert report.external_bindings_declared is False
    assert report.external_independence_proven is False
    assert report.artifact_qualification_proven is False
    assert report.live_execution_ready is False
    assert set(report.missing_external_bindings) == {
        *REQUIRED_EXTERNAL_BINDINGS,
        "HSWM_G0_ACTOR_ROLE_ID",
        "HSWM_G0_REVISION_PROPOSER_ROLE_ID",
        "HSWM_G0_OCCURRENCE_CLAIMANT_ROLE_ID",
        "HSWM_G0_WORM_ADMINISTRATOR_ROLE_ID",
        "HSWM_G0_CUSTODIAN_ROLE_ID",
        "HSWM_G0_DRAND_VERIFIER_ROLE_ID",
        "HSWM_G0_EVALUATOR_A_ROLE_ID",
        "HSWM_G0_EVALUATOR_B_ROLE_ID",
        "HSWM_G0_EXTERNAL_AUDITOR_ROLE_ID",
    }


def test_report_never_leaks_binding_values_or_version_output() -> None:
    which, version = binaries()
    secret = "https://token:do-not-print@example.invalid/sensitive"
    report = run_occurrence_preflight(
        environ={**complete_environ(), "HSWM_G0_WORM_ENDPOINT": secret},
        which=which,
        version=lambda path: f"candidate {version(path)} {secret}",
    )

    rendered = repr(report)
    assert secret not in rendered
    assert "candidate cosign version" not in rendered
    assert report.status == READY_STATUS


def test_same_control_domain_refuses_external_independence() -> None:
    which, version = binaries()
    report = run_occurrence_preflight(
        environ={
            **complete_environ(),
            "HSWM_G0_ACTOR_ROLE_ID": "same.example",
            "HSWM_G0_CUSTODIAN_ROLE_ID": "same.example",
        },
        which=which,
        version=version,
    )

    assert report.status == BLOCKED_EXTERNAL_STATUS
    assert report.external_bindings_declared is False
    assert report.external_independence_proven is False
    assert report.declared_role_identities_distinct is False
    assert report.same_role_identities == ("actor=custodian",)


def test_all_required_bindings_and_distinct_domains_are_ready_not_execution() -> None:
    which, version = binaries()
    report = run_occurrence_preflight(
        environ=complete_environ(), which=which, version=version
    )

    assert report.status == READY_STATUS
    assert report.local_engineering_ready is True
    assert report.external_bindings_declared is True
    assert report.external_independence_proven is False
    assert report.artifact_qualification_proven is False
    assert report.live_execution_ready is False
    assert report.declared_role_identities_distinct is True
    assert all(item.artifact_integrity_verified is False for item in report.binaries)


def test_local_version_uses_tool_specific_argv_and_combines_nonsecret_output(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run(argv, **_kwargs):  # type: ignore[no-untyped-def]
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout="", stderr="aws-cli/2.36.36")

    monkeypatch.setattr(occurrence_preflight.subprocess, "run", fake_run)
    assert occurrence_preflight._local_version("/candidate/aws", ("--version",)) == "aws-cli/2.36.36"
    assert calls == [("/candidate/aws", "--version")]
