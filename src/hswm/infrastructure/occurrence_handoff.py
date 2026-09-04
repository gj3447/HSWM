"""Fail-closed, descriptor-only handoff for a prospective external G0 run.

This is an exchange contract for an external operator, not an external-service
client.  It deliberately records no raw credentials, endpoint values, private
payloads, receipt bytes, or claims of independence.  Structural validation
cannot establish that a role, account, service, or auditor is independent or
live.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path
import re
import sysconfig
from types import MappingProxyType
from typing import Any, Mapping

from hswm.experiments.swm0w_beacon import canonical_json
from hswm.infrastructure.occurrence_integrity import ContentDescriptorV1
from hswm.infrastructure.occurrence_preflight import (
    REQUIRED_EXTERNAL_BINDINGS,
    ROLE_IDENTITY_BINDINGS,
)


SCHEMA = "hswm-g0-external-qualification-handoff/v1"
STATUS = "BLOCKED_EXTERNAL"
MAX_HANDOFF_BYTES = 64 * 1024
CLAIM_BOUNDARY = (
    "descriptor-only external-operator handoff and structural validation only; "
    "not external independence, artifact qualification, live readiness, "
    "registration, execution, outcome truth, G0, Permit, canonical admission, "
    "causal credit, or learning evidence"
)
_UID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,159}$")
_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_INSTALLED_DATA_ROOT = Path(sysconfig.get_path("data")) / "share/hswm/g0_occurrence"
_CANDIDATES_NAME = "HSWM_G0_OCCURRENCE_TOOLCHAIN_CANDIDATES.v1.json"

ROLE_SLOTS = tuple(role for role, _ in ROLE_IDENTITY_BINDINGS)
EXTERNAL_BINDING_SLOTS = REQUIRED_EXTERNAL_BINDINGS + (
    "HSWM_G0_DGX_EXECUTION_SURFACE_BINDING",
    "HSWM_G0_PRIVATE_LINEAGE_DISJOINT_HOLDOUT_BINDING",
)
RETURN_SLOTS = (
    "osf_immutable_registration_readback",
    "dsse_envelope",
    "rekor_inclusion_verification",
    "rfc3161_verified_token",
    "toolchain_qualification_receipt",
    "worm_claim_and_policy_audit",
    "pre_pulse_actor_material_seal",
    "drand_pulse_verification",
    "temporal_history_export",
    "temporal_terminal_audit_receipt",
    "all_run_manifest",
    "custodian_reveal_receipt",
    "evaluator_a_receipt",
    "evaluator_b_receipt",
    "pending_external_audit_candidate_receipt",
    "external_audit_manifest",
    "external_audit_cosign_bundle",
    "final_terminal_receipt",
)
_FIELDS = {
    "claim_boundary",
    "external_binding_descriptors",
    "occurrence_uid",
    "operator_return_checklist",
    "operator_return_descriptors",
    "protocol_package_descriptor",
    "role_binding_descriptors",
    "schema_version",
    "status",
    "toolchain_candidates_sha256",
}


class OccurrenceHandoffError(ValueError):
    """The untrusted handoff is malformed or exceeds the frozen contract."""


def _fixed_candidates_path() -> Path:
    repository_path = _REPOSITORY_ROOT / "_research/g0_occurrence" / _CANDIDATES_NAME
    return (
        repository_path
        if repository_path.is_file()
        else _INSTALLED_DATA_ROOT / _CANDIDATES_NAME
    )


def toolchain_candidates_sha256() -> str:
    try:
        return sha256(_fixed_candidates_path().read_bytes()).hexdigest()
    except OSError as exc:
        raise OccurrenceHandoffError("fixed toolchain candidate record is unavailable") from exc


def _uid(value: object) -> str:
    if not isinstance(value, str) or _UID.fullmatch(value) is None:
        raise OccurrenceHandoffError("occurrence_uid must be a bounded ASCII identifier")
    return value


def _strict_json(raw: bytes) -> Mapping[str, Any]:
    if len(raw) > MAX_HANDOFF_BYTES:
        raise OccurrenceHandoffError("handoff exceeds byte limit")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise OccurrenceHandoffError(f"handoff contains duplicate key {key!r}")
            result[key] = value
        return result

    def reject_nonfinite(value: str) -> None:
        raise OccurrenceHandoffError(f"handoff contains non-finite JSON number {value}")

    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=unique_object,
            parse_constant=reject_nonfinite,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise OccurrenceHandoffError("handoff must be strict UTF-8 JSON") from exc
    if not isinstance(value, Mapping) or set(value) != _FIELDS:
        raise OccurrenceHandoffError("handoff keys do not match frozen schema")
    if canonical_json(value).encode("utf-8") != raw:
        raise OccurrenceHandoffError("handoff must use canonical JSON bytes")
    return value


def _descriptor_or_none(value: object, field: str) -> ContentDescriptorV1 | None:
    if value is None:
        return None
    try:
        return ContentDescriptorV1.from_mapping(value)
    except ValueError as exc:
        raise OccurrenceHandoffError(f"{field} must be a descriptor or null") from exc


def _descriptor_slots(
    value: object, slots: tuple[str, ...], field: str
) -> dict[str, ContentDescriptorV1 | None]:
    if not isinstance(value, Mapping) or set(value) != set(slots):
        raise OccurrenceHandoffError(f"{field} keys do not match frozen slots")
    return {slot: _descriptor_or_none(value[slot], f"{field}.{slot}") for slot in slots}


@dataclass(frozen=True, slots=True)
class ExternalHandoffV1:
    occurrence_uid: str
    protocol_package_descriptor: ContentDescriptorV1 | None
    role_binding_descriptors: Mapping[str, ContentDescriptorV1 | None]
    external_binding_descriptors: Mapping[str, ContentDescriptorV1 | None]
    operator_return_descriptors: Mapping[str, ContentDescriptorV1 | None]
    toolchain_candidates_digest: str = field(
        default_factory=toolchain_candidates_sha256,
        repr=False,
    )

    def __post_init__(self) -> None:
        _uid(self.occurrence_uid)
        self._assert_current_toolchain_binding()
        if self.protocol_package_descriptor is not None and not isinstance(
            self.protocol_package_descriptor, ContentDescriptorV1
        ):
            raise OccurrenceHandoffError(
                "protocol_package_descriptor must be a descriptor or null"
            )
        for field, value, slots in (
            ("role_binding_descriptors", self.role_binding_descriptors, ROLE_SLOTS),
            (
                "external_binding_descriptors",
                self.external_binding_descriptors,
                EXTERNAL_BINDING_SLOTS,
            ),
            ("operator_return_descriptors", self.operator_return_descriptors, RETURN_SLOTS),
        ):
            if not isinstance(value, Mapping) or set(value) != set(slots):
                raise OccurrenceHandoffError(f"{field} keys do not match frozen slots")
            if any(
                item is not None and not isinstance(item, ContentDescriptorV1)
                for item in value.values()
            ):
                raise OccurrenceHandoffError(
                    f"{field} values must be descriptors or null"
                )
            object.__setattr__(
                self,
                field,
                MappingProxyType({slot: value[slot] for slot in slots}),
            )

    def _assert_current_toolchain_binding(self) -> None:
        if self.toolchain_candidates_digest != toolchain_candidates_sha256():
            raise OccurrenceHandoffError(
                "handoff does not bind exact toolchain candidate bytes"
            )

    def canonical(self) -> dict[str, Any]:
        self._assert_current_toolchain_binding()

        def render(value: ContentDescriptorV1 | None) -> dict[str, Any] | None:
            return None if value is None else value.canonical()

        return {
            "claim_boundary": CLAIM_BOUNDARY,
            "external_binding_descriptors": {
                slot: render(self.external_binding_descriptors[slot])
                for slot in EXTERNAL_BINDING_SLOTS
            },
            "occurrence_uid": self.occurrence_uid,
            "operator_return_checklist": list(RETURN_SLOTS),
            "operator_return_descriptors": {
                slot: render(self.operator_return_descriptors[slot]) for slot in RETURN_SLOTS
            },
            "protocol_package_descriptor": render(self.protocol_package_descriptor),
            "role_binding_descriptors": {
                slot: render(self.role_binding_descriptors[slot]) for slot in ROLE_SLOTS
            },
            "schema_version": SCHEMA,
            "status": STATUS,
            "toolchain_candidates_sha256": self.toolchain_candidates_digest,
        }

    def bytes(self) -> bytes:
        return canonical_json(self.canonical()).encode("utf-8")


def external_handoff_template(*, occurrence_uid: str) -> ExternalHandoffV1:
    """Create a non-promoting template with no asserted external evidence."""
    return ExternalHandoffV1(
        occurrence_uid=_uid(occurrence_uid),
        protocol_package_descriptor=None,
        role_binding_descriptors={slot: None for slot in ROLE_SLOTS},
        external_binding_descriptors={slot: None for slot in EXTERNAL_BINDING_SLOTS},
        operator_return_descriptors={slot: None for slot in RETURN_SLOTS},
    )


def parse_external_handoff(raw: bytes) -> ExternalHandoffV1:
    """Strictly parse an untrusted canonical handoff without external checks."""
    value = _strict_json(raw)
    if value["schema_version"] != SCHEMA or value["status"] != STATUS:
        raise OccurrenceHandoffError("handoff schema version or status is invalid")
    if value["claim_boundary"] != CLAIM_BOUNDARY:
        raise OccurrenceHandoffError("handoff claim boundary is invalid")
    if value["toolchain_candidates_sha256"] != toolchain_candidates_sha256():
        raise OccurrenceHandoffError("handoff does not bind exact toolchain candidate bytes")
    if value["operator_return_checklist"] != list(RETURN_SLOTS):
        raise OccurrenceHandoffError("operator return checklist is invalid")
    return ExternalHandoffV1(
        occurrence_uid=_uid(value["occurrence_uid"]),
        protocol_package_descriptor=_descriptor_or_none(
            value["protocol_package_descriptor"], "protocol_package_descriptor"
        ),
        role_binding_descriptors=_descriptor_slots(
            value["role_binding_descriptors"], ROLE_SLOTS, "role_binding_descriptors"
        ),
        external_binding_descriptors=_descriptor_slots(
            value["external_binding_descriptors"], EXTERNAL_BINDING_SLOTS,
            "external_binding_descriptors",
        ),
        operator_return_descriptors=_descriptor_slots(
            value["operator_return_descriptors"], RETURN_SLOTS,
            "operator_return_descriptors",
        ),
        toolchain_candidates_digest=value["toolchain_candidates_sha256"],
    )


def validate_external_handoff(handoff: ExternalHandoffV1) -> dict[str, Any]:
    """Return a structural report whose status can never promote a live run."""
    if not isinstance(handoff, ExternalHandoffV1):
        raise OccurrenceHandoffError("external handoff value is required")
    handoff._assert_current_toolchain_binding()
    role_values = tuple(handoff.role_binding_descriptors[slot] for slot in ROLE_SLOTS)
    all_roles_present = all(value is not None for value in role_values)
    role_digests = [value.sha256 for value in role_values if value is not None]
    missing = (
        (
            []
            if handoff.protocol_package_descriptor is not None
            else ["protocol_package_descriptor"]
        )
        + [
            f"role_binding_descriptors.{slot}"
            for slot in ROLE_SLOTS
            if handoff.role_binding_descriptors[slot] is None
        ]
        + [
            f"external_binding_descriptors.{slot}"
            for slot in EXTERNAL_BINDING_SLOTS
            if handoff.external_binding_descriptors[slot] is None
        ]
        + [
            f"operator_return_descriptors.{slot}"
            for slot in RETURN_SLOTS
            if handoff.operator_return_descriptors[slot] is None
        ]
    )
    return {
        "claim_boundary": CLAIM_BOUNDARY,
        "declared_role_descriptor_digests_distinct": (
            all_roles_present and len(role_digests) == len(set(role_digests))
        ),
        "external_independence_proven": False,
        "g0_passed": False,
        "live_execution_ready": False,
        "missing_descriptor_slots": missing,
        "occurrence_uid": handoff.occurrence_uid,
        "schema_version": SCHEMA,
        "status": STATUS,
        "descriptor_graph_complete": not missing,
        "schema_structure_valid": True,
        "structural_validation_only": True,
        "toolchain_candidates_sha256": handoff.toolchain_candidates_digest,
    }


def load_external_handoff(path: Path) -> ExternalHandoffV1:
    if not isinstance(path, Path):
        raise OccurrenceHandoffError("handoff path is required")
    try:
        resolved = path.resolve(strict=True)
        if not resolved.is_file():
            raise OccurrenceHandoffError("handoff must be a regular file")
        with resolved.open("rb") as stream:
            raw = stream.read(MAX_HANDOFF_BYTES + 1)
        return parse_external_handoff(raw)
    except OSError as exc:
        raise OccurrenceHandoffError("cannot read handoff") from exc


__all__ = [
    "CLAIM_BOUNDARY",
    "EXTERNAL_BINDING_SLOTS",
    "ExternalHandoffV1",
    "MAX_HANDOFF_BYTES",
    "OccurrenceHandoffError",
    "RETURN_SLOTS",
    "ROLE_SLOTS",
    "SCHEMA",
    "STATUS",
    "external_handoff_template",
    "load_external_handoff",
    "parse_external_handoff",
    "toolchain_candidates_sha256",
    "validate_external_handoff",
]
