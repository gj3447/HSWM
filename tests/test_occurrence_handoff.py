from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from hswm.experiments.swm0w_beacon import canonical_json
from hswm.infrastructure import occurrence_cli, occurrence_handoff
from hswm.infrastructure.occurrence_handoff import (
    EXTERNAL_BINDING_SLOTS,
    ExternalHandoffV1,
    MAX_HANDOFF_BYTES,
    OccurrenceHandoffError,
    RETURN_SLOTS,
    ROLE_SLOTS,
    STATUS,
    external_handoff_template,
    parse_external_handoff,
    validate_external_handoff,
)
from hswm.infrastructure.occurrence_integrity import ContentDescriptorV1


def _template_bytes() -> bytes:
    return external_handoff_template(occurrence_uid="g0-handoff-001").bytes()


def test_template_is_canonical_descriptor_only_and_always_blocked() -> None:
    handoff = parse_external_handoff(_template_bytes())
    value = handoff.canonical()
    report = validate_external_handoff(handoff)

    assert value["status"] == STATUS
    assert tuple(value["role_binding_descriptors"]) == ROLE_SLOTS
    assert tuple(value["external_binding_descriptors"]) == EXTERNAL_BINDING_SLOTS
    assert value["operator_return_checklist"] == list(RETURN_SLOTS)
    assert "HSWM_G0_DGX_EXECUTION_SURFACE_BINDING" in EXTERNAL_BINDING_SLOTS
    assert "HSWM_G0_PRIVATE_LINEAGE_DISJOINT_HOLDOUT_BINDING" in EXTERNAL_BINDING_SLOTS
    assert {
        "dsse_envelope", "rekor_inclusion_verification", "rfc3161_verified_token",
        "pre_pulse_actor_material_seal", "drand_pulse_verification",
        "all_run_manifest", "pending_external_audit_candidate_receipt",
        "final_terminal_receipt",
    } <= set(RETURN_SLOTS)
    assert all(item is None for item in value["role_binding_descriptors"].values())
    assert report["status"] == STATUS
    assert report["schema_structure_valid"] is True
    assert report["descriptor_graph_complete"] is False
    assert report["structural_validation_only"] is True
    assert report["external_independence_proven"] is False
    assert report["live_execution_ready"] is False
    assert report["g0_passed"] is False


def test_parse_rejects_noncanonical_duplicate_nonfinite_and_extra_fields() -> None:
    template = json.loads(_template_bytes())
    with pytest.raises(OccurrenceHandoffError, match="canonical"):
        parse_external_handoff(json.dumps(template, indent=2).encode())
    duplicate = b'{"schema_version":"x","schema_version":"x"}'
    with pytest.raises(OccurrenceHandoffError, match="duplicate"):
        parse_external_handoff(duplicate)
    with pytest.raises(OccurrenceHandoffError, match="non-finite"):
        parse_external_handoff(b'{"value":NaN}')
    template["extra"] = None
    with pytest.raises(OccurrenceHandoffError, match="keys"):
        parse_external_handoff(canonical_json(template).encode())


def test_parse_rejects_wrong_candidate_record_digest() -> None:
    value = json.loads(_template_bytes())
    value["toolchain_candidates_sha256"] = "0" * 64
    with pytest.raises(OccurrenceHandoffError, match="exact toolchain"):
        parse_external_handoff(canonical_json(value).encode())


def test_parsed_value_refuses_later_candidate_record_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handoff = parse_external_handoff(_template_bytes())
    monkeypatch.setattr(
        occurrence_handoff,
        "toolchain_candidates_sha256",
        lambda: "0" * 64,
    )

    with pytest.raises(OccurrenceHandoffError, match="exact toolchain"):
        validate_external_handoff(handoff)


def test_validation_only_reports_structural_role_descriptor_collision() -> None:
    value = json.loads(_template_bytes())
    descriptor = {"byte_length": 1, "media_type": "application/json", "sha256": "a" * 64}
    for slot in ROLE_SLOTS:
        value["role_binding_descriptors"][slot] = descriptor
    handoff = parse_external_handoff(canonical_json(value).encode())
    report = validate_external_handoff(handoff)

    assert report["declared_role_descriptor_digests_distinct"] is False
    assert report["status"] == STATUS
    assert report["external_independence_proven"] is False


def test_fully_populated_descriptor_graph_still_cannot_promote() -> None:
    value = json.loads(_template_bytes())

    def descriptor(label: str) -> dict[str, object]:
        return {
            "byte_length": len(label),
            "media_type": "application/json",
            "sha256": sha256(label.encode()).hexdigest(),
        }

    value["protocol_package_descriptor"] = descriptor("protocol-package")
    for field, slots in (
        ("role_binding_descriptors", ROLE_SLOTS),
        ("external_binding_descriptors", EXTERNAL_BINDING_SLOTS),
        ("operator_return_descriptors", RETURN_SLOTS),
    ):
        for slot in slots:
            value[field][slot] = descriptor(f"{field}:{slot}")

    report = validate_external_handoff(
        parse_external_handoff(canonical_json(value).encode())
    )

    assert report["missing_descriptor_slots"] == []
    assert report["descriptor_graph_complete"] is True
    assert report["declared_role_descriptor_digests_distinct"] is True
    assert report["status"] == STATUS
    assert report["external_independence_proven"] is False
    assert report["live_execution_ready"] is False
    assert report["g0_passed"] is False


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    (
        ("schema_version", "hswm-g0-external-qualification-handoff/v2", "schema"),
        ("status", "READY_FOR_LIVE_EXECUTION", "status"),
        ("claim_boundary", "externally qualified", "claim boundary"),
        ("operator_return_checklist", [], "return checklist"),
    ),
)
def test_parse_rejects_contract_drift_and_promotion_fields(
    field: str, replacement: object, message: str
) -> None:
    value = json.loads(_template_bytes())
    value[field] = replacement
    with pytest.raises(OccurrenceHandoffError, match=message):
        parse_external_handoff(canonical_json(value).encode())


def test_public_construction_rejects_wrong_slots_and_non_descriptors() -> None:
    with pytest.raises(OccurrenceHandoffError, match="role_binding_descriptors keys"):
        ExternalHandoffV1(
            occurrence_uid="g0-handoff-001", protocol_package_descriptor=None,
            role_binding_descriptors={},
            external_binding_descriptors={slot: None for slot in EXTERNAL_BINDING_SLOTS},
            operator_return_descriptors={slot: None for slot in RETURN_SLOTS},
        )
    with pytest.raises(OccurrenceHandoffError, match="values must be descriptors"):
        ExternalHandoffV1(
            occurrence_uid="g0-handoff-001", protocol_package_descriptor=None,
            role_binding_descriptors={
                slot: ContentDescriptorV1("application/json", "a" * 64, 1)
                for slot in ROLE_SLOTS
            },
            external_binding_descriptors={slot: None for slot in EXTERNAL_BINDING_SLOTS},
            operator_return_descriptors={slot: "not-a-descriptor" for slot in RETURN_SLOTS},
        )


def test_public_construction_copies_slot_maps_immutably() -> None:
    roles = {slot: None for slot in ROLE_SLOTS}
    external = {slot: None for slot in EXTERNAL_BINDING_SLOTS}
    returned = {slot: None for slot in RETURN_SLOTS}
    handoff = ExternalHandoffV1(
        occurrence_uid="g0-handoff-001",
        protocol_package_descriptor=None,
        role_binding_descriptors=roles,
        external_binding_descriptors=external,
        operator_return_descriptors=returned,
    )

    roles.clear()
    external.clear()
    returned.clear()

    assert tuple(handoff.role_binding_descriptors) == ROLE_SLOTS
    assert tuple(handoff.external_binding_descriptors) == EXTERNAL_BINDING_SLOTS
    assert tuple(handoff.operator_return_descriptors) == RETURN_SLOTS
    with pytest.raises(TypeError):
        handoff.role_binding_descriptors[ROLE_SLOTS[0]] = None


def test_oversized_handoff_exits_fail_closed(tmp_path: Path) -> None:
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b" " * (MAX_HANDOFF_BYTES + 1))

    with pytest.raises(SystemExit) as error:
        occurrence_cli.main(["external-handoff-validate", str(oversized)])

    assert error.value.code == 2


def test_cli_template_and_validation_do_not_promote(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert occurrence_cli.main(["external-handoff-template", "g0-handoff-001"]) == 0
    template = capsys.readouterr().out.encode()
    path = tmp_path / "handoff.json"
    path.write_bytes(template)
    assert occurrence_cli.main(["external-handoff-validate", str(path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == STATUS
    assert report["g0_passed"] is False
