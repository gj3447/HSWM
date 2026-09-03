"""No-secret, no-network readiness check for a prospective G0 occurrence.

This module observes only whether required bindings are present.  It never
returns environment values, endpoint URLs, tokens, command output, or artifact
digests.  A matching executable version is merely an engineering candidate;
artifact digest/source/license qualification remains a separate requirement.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import os
import re
import shutil
import subprocess


PREFLIGHT_SCHEMA = "hswm-g0-occurrence-live-preflight/v1"
COSIGN_CANDIDATE_VERSION = "3.1.3"
TEMPORAL_CLI_CANDIDATE_VERSION = "1.8.3"
AWS_CLI_CANDIDATE_VERSION = "2.36.36"
OPENSSL_CANDIDATE_VERSION = "3.5.6"
READY_STATUS = "READY_FOR_EXTERNAL_QUALIFICATION_NOT_LIVE_EXECUTION"
BLOCKED_EXTERNAL_STATUS = "BLOCKED_EXTERNAL"
BLOCKED_LOCAL_STATUS = "BLOCKED_LOCAL_ENGINEERING"
CLAIM_BOUNDARY = (
    "presence-only qualification-input check; version strings are not artifact "
    "qualification and declared role identifiers are not an external "
    "independence proof; not registration, "
    "artifact integrity verification, live execution readiness or authorization, outcome truth, Permit, "
    "causal credit, canonical admission, learning, or efficacy evidence"
)

# Names intentionally describe the required external boundary without exposing
# the endpoint, credential, registration, or artifact values themselves.
REQUIRED_EXTERNAL_BINDINGS = (
    "HSWM_G0_OSF_REGISTRATION_BINDING",
    "HSWM_G0_WORM_ENDPOINT",
    "HSWM_G0_WORM_POLICY_AUDIT_BINDING",
    "HSWM_G0_SIGSTORE_REKOR_ENDPOINT",
    "HSWM_G0_RFC3161_TSA_ENDPOINT",
    "HSWM_G0_PRODUCTION_TEMPORAL_ENDPOINT",
    "HSWM_G0_TEMPORAL_SIGNAL_AUTHORIZATION_BINDING",
    "HSWM_G0_TOOLCHAIN_QUALIFICATION_BINDING",
    "HSWM_G0_COMPLETION_AUDIT_QUALIFICATION_BINDING",
    "HSWM_G0_DRAND_VERIFIER_BINDING",
    "HSWM_G0_CUSTODIAN_ENDPOINT",
    "HSWM_G0_EVALUATOR_A_ENDPOINT",
    "HSWM_G0_EVALUATOR_B_ENDPOINT",
)
ROLE_IDENTITY_BINDINGS = (
    ("actor", "HSWM_G0_ACTOR_ROLE_ID"),
    ("revision_proposer", "HSWM_G0_REVISION_PROPOSER_ROLE_ID"),
    ("occurrence_claimant", "HSWM_G0_OCCURRENCE_CLAIMANT_ROLE_ID"),
    ("worm_administrator", "HSWM_G0_WORM_ADMINISTRATOR_ROLE_ID"),
    ("custodian", "HSWM_G0_CUSTODIAN_ROLE_ID"),
    ("drand_verifier", "HSWM_G0_DRAND_VERIFIER_ROLE_ID"),
    ("evaluator_a", "HSWM_G0_EVALUATOR_A_ROLE_ID"),
    ("evaluator_b", "HSWM_G0_EVALUATOR_B_ROLE_ID"),
    ("external_auditor", "HSWM_G0_EXTERNAL_AUDITOR_ROLE_ID"),
)
_VERSION_ARGUMENTS = {
    "cosign": ("version",),
    "temporal": ("version",),
    "aws": ("--version",),
    "openssl": ("version",),
}


@dataclass(frozen=True, slots=True)
class BindingPresence:
    name: str
    present: bool


@dataclass(frozen=True, slots=True)
class BinaryPresence:
    name: str
    candidate_version: str
    present: bool
    candidate_version_observed: bool
    artifact_integrity_verified: bool = False


@dataclass(frozen=True, slots=True)
class OccurrencePreflightReport:
    schema_version: str
    status: str
    claim_boundary: str
    local_engineering_ready: bool
    artifact_qualification_proven: bool
    live_execution_ready: bool
    external_bindings_declared: bool
    external_independence_proven: bool
    bindings: tuple[BindingPresence, ...]
    binaries: tuple[BinaryPresence, ...]
    declared_role_identities_distinct: bool
    missing_external_bindings: tuple[str, ...]
    same_role_identities: tuple[str, ...]


def run_occurrence_preflight(
    *,
    environ: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] = shutil.which,
    version: Callable[[str], str | None] | None = None,
) -> OccurrencePreflightReport:
    """Return a presence-only readiness result without contacting any service."""

    source = os.environ if environ is None else environ
    version_lookup = _local_version if version is None else version
    bindings = tuple(
        BindingPresence(name=name, present=_present(source, name))
        for name in REQUIRED_EXTERNAL_BINDINGS
    )
    role_values = {
        role: source.get(name, "").strip() for role, name in ROLE_IDENTITY_BINDINGS
    }
    role_presence = tuple(
        BindingPresence(name=name, present=bool(role_values[role]))
        for role, name in ROLE_IDENTITY_BINDINGS
    )
    binaries = tuple(
        _binary_presence(
            name,
            candidate,
            which=which,
            version=(
                version_lookup
                if version is not None
                else lambda executable, arguments=_VERSION_ARGUMENTS[name]: _local_version(
                    executable, arguments
                )
            ),
        )
        for name, candidate in (
            ("cosign", COSIGN_CANDIDATE_VERSION),
            ("temporal", TEMPORAL_CLI_CANDIDATE_VERSION),
            ("aws", AWS_CLI_CANDIDATE_VERSION),
            ("openssl", OPENSSL_CANDIDATE_VERSION),
        )
    )
    same_roles = _same_role_identities(role_values)
    missing = tuple(
        item.name for item in (*bindings, *role_presence) if not item.present
    )
    bindings_declared = not missing and not same_roles
    local_ready = all(
        item.present and item.candidate_version_observed for item in binaries
    )
    if not bindings_declared:
        status = BLOCKED_EXTERNAL_STATUS
    elif not local_ready:
        status = BLOCKED_LOCAL_STATUS
    else:
        status = READY_STATUS
    return OccurrencePreflightReport(
        schema_version=PREFLIGHT_SCHEMA,
        status=status,
        claim_boundary=CLAIM_BOUNDARY,
        local_engineering_ready=local_ready,
        artifact_qualification_proven=False,
        live_execution_ready=False,
        external_bindings_declared=bindings_declared,
        external_independence_proven=False,
        bindings=(*bindings, *role_presence),
        binaries=binaries,
        declared_role_identities_distinct=not same_roles and not any(
            not item.present for item in role_presence
        ),
        missing_external_bindings=missing,
        same_role_identities=same_roles,
    )


def _present(environ: Mapping[str, str], name: str) -> bool:
    value = environ.get(name)
    return isinstance(value, str) and bool(value.strip())


def _binary_presence(
    name: str,
    candidate_version: str,
    *,
    which: Callable[[str], str | None],
    version: Callable[[str], str | None],
) -> BinaryPresence:
    executable = which(name)
    if not executable:
        return BinaryPresence(
            name=name,
            candidate_version=candidate_version,
            present=False,
            candidate_version_observed=False,
        )
    observed = version(executable)
    return BinaryPresence(
        name=name,
        candidate_version=candidate_version,
        present=True,
        candidate_version_observed=_contains_exact_version(observed, candidate_version),
    )


def _contains_exact_version(output: str | None, candidate: str) -> bool:
    return isinstance(output, str) and re.search(
        rf"(?<![0-9.]){re.escape(candidate)}(?![0-9.])", output
    ) is not None


def _same_role_identities(identities: Mapping[str, str]) -> tuple[str, ...]:
    roles = tuple(role for role, value in identities.items() if value)
    return tuple(
        f"{left}={right}"
        for index, left in enumerate(roles)
        for right in roles[index + 1 :]
        if identities[left] == identities[right]
    )


def _local_version(executable: str, arguments: tuple[str, ...] = ("version",)) -> str | None:
    """Read bounded local version output only; it is never included in the report."""

    try:
        completed = subprocess.run(
            (executable, *arguments),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return (completed.stdout + completed.stderr) if completed.returncode == 0 else None


__all__ = [
    "BLOCKED_EXTERNAL_STATUS",
    "BLOCKED_LOCAL_STATUS",
    "AWS_CLI_CANDIDATE_VERSION",
    "CLAIM_BOUNDARY",
    "COSIGN_CANDIDATE_VERSION",
    "OPENSSL_CANDIDATE_VERSION",
    "OccurrencePreflightReport",
    "PREFLIGHT_SCHEMA",
    "READY_STATUS",
    "REQUIRED_EXTERNAL_BINDINGS",
    "TEMPORAL_CLI_CANDIDATE_VERSION",
    "run_occurrence_preflight",
]
