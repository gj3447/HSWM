"""Offline teeth for the F5v2 B-prime ordered-gate machine lock."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import f5v2_sealed_prep as prep
from f5v2_judge import build_dev_smoke_receipt
from f5v2_operators import parse_cpl1_numeric_packet


ROOT = Path(__file__).resolve().parents[1]
PREREG_PATH = (
    ROOT
    / "prom_search_hswm"
    / "evidence"
    / "PREREG_F5V2_BPRIME_DURABLE_CACHE_20260726.draft.json"
)
ORDERED_PATH = ROOT / "receipts" / "HSWM_ORDERED_GATE_STATUS_20260724.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: dict) -> Path:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def _ratified_prereg() -> dict:
    value = _read(PREREG_PATH)
    value["status"] = "USER_RATIFIED_READY_FOR_MACHINE_LOCK"
    return value


def _p4_status() -> dict:
    value = _read(ORDERED_PATH)
    by_id = {gate["id"]: gate for gate in value["gates"]}
    for gate_id in prep.ORDERED_SEQUENCE[:-1]:
        by_id[gate_id]["state"] = "SATISFIED"
        by_id[gate_id]["missing_dependencies"] = []
        by_id[gate_id]["evidence"] = by_id[gate_id].get("evidence") or {
            "receipt_sha256": "1" * 64
        }
    p4 = by_id[prep.P4_GATE]
    p4["state"] = "ACTION_REQUIRED"
    p4["missing_dependencies"] = []
    value["active_gate"] = {
        "id": prep.P4_GATE,
        "lane": p4["lane"],
        "priority": p4["priority"],
        "state": p4["state"],
        "action": p4["action"],
    }
    value["next_actions"] = [value["active_gate"]]
    value["ordered_remaining"] = [prep.P4_GATE]
    value["p1v5_packet_supplied"] = True
    value["p2_packet_supplied"] = True
    value["scientific_verdict_emitted"] = False
    value["plan_sha256"] = prep.sha256_path(prep.DEFAULT_ORDERED_PLAN)
    value["harness_sha256"] = prep.sha256_path(
        ROOT / "hswm_next_research_harness.py"
    )
    return prep.add_self_hash(value, "status_receipt_sha256")


def _cpl1_unlock() -> dict:
    payload = {
        "shared_schema_sha256": "2" * 64,
        "edge_or_hyperedge_id": "edge:fixture:alpha",
        "numeric_delta": 0.25,
        "confidence": 0.9,
        "provenance_sha256": "3" * 64,
    }
    unsigned = {
        "schema_version": prep.CPL1_UNLOCK_SCHEMA,
        "status": "PASS_F5V2_UNLOCK",
        "numeric_packet": {
            "packet_sha256": parse_cpl1_numeric_packet(payload).packet_sha256,
            "payload": payload,
            "pre_outcome_receipt_sha256": "4" * 64,
        },
        "causal_gates": {
            "numeric_W_gain_positive": True,
            "W_removal_erases_gain": True,
            "G_match_lcb_positive": True,
            "DSI_lcb_positive": True,
            "prompt_forbidden_overlap_count_zero": True,
        },
    }
    return prep.add_self_hash(unsigned, "receipt_sha256")


def _smoke(manifest_path: Path) -> dict:
    packet_sha = _cpl1_unlock()["numeric_packet"]["packet_sha256"]
    return build_dev_smoke_receipt(
        manifest_sha256=prep.sha256_path(manifest_path),
        citation_rows=[{"cited_packet_sha256s": [packet_sha]}],
        allowed_packet_sha256s=[packet_sha],
        canary_cases=[{"should_reject": True, "rejected": True}],
        drm_cases=[
            {
                "case_id": "supported-only",
                "supported_claims": ["claim:a"],
                "proposed_claims": ["claim:a"],
            }
        ],
        legacy_downscale_negative_reproduced=True,
        bitemporal_fired=True,
        query_leakage_count=0,
    )


def _development_chain(tmp_path: Path) -> dict[str, object]:
    prereg_path = _write(tmp_path / "prereg.json", _ratified_prereg())
    status_path = _write(tmp_path / "ordered.json", _p4_status())
    unlock_path = _write(tmp_path / "unlock.json", _cpl1_unlock())
    manifest = prep.build_manifest(
        _read(prereg_path),
        _read(status_path),
        _read(unlock_path),
        prereg_path=prereg_path,
        ordered_status_path=status_path,
        cpl1_unlock_path=unlock_path,
        run_id="fixture-r1",
    )
    manifest_path = _write(tmp_path / "manifest.dev.json", manifest)
    prep_receipt = prep.build_prep_receipt(
        manifest, dev_manifest_path=manifest_path
    )
    prep_receipt_path = _write(tmp_path / "prep-receipt.json", prep_receipt)
    smoke = _smoke(manifest_path)
    smoke_path = _write(tmp_path / "smoke.json", smoke)
    return {
        "prereg_path": prereg_path,
        "status_path": status_path,
        "unlock_path": unlock_path,
        "manifest": manifest,
        "manifest_path": manifest_path,
        "prep_receipt": prep_receipt,
        "prep_receipt_path": prep_receipt_path,
        "smoke": smoke,
        "smoke_path": smoke_path,
    }


def _seal(chain: dict[str, object]) -> dict:
    return prep.seal_manifest(
        _read(chain["manifest_path"]),  # type: ignore[arg-type]
        _read(chain["smoke_path"]),  # type: ignore[arg-type]
        _read(chain["prep_receipt_path"]),  # type: ignore[arg-type]
        dev_manifest_path=chain["manifest_path"],  # type: ignore[arg-type]
        smoke_path=chain["smoke_path"],  # type: ignore[arg-type]
        prep_receipt_path=chain["prep_receipt_path"],  # type: ignore[arg-type]
    )


def test_repository_prereg_is_explicitly_draft_and_refuses_machine_lock():
    with pytest.raises(prep.PrepError, match="does not declare user-ratified"):
        prep.validate_prereg(_read(PREREG_PATH))


def test_repository_ordered_status_refuses_out_of_order_f5v2():
    with pytest.raises(prep.PrepError, match="out-of-order"):
        prep.validate_ordered_status(_read(ORDERED_PATH))


def test_forged_ordered_status_is_refused_by_official_self_hash():
    value = _p4_status()
    value["ordered_remaining"] = []
    with pytest.raises(prep.PrepError, match="self-hash"):
        prep.validate_ordered_status(value)


def test_p4_status_must_bind_current_harness_and_plan():
    value = _p4_status()
    value["harness_sha256"] = "f" * 64
    value = prep.add_self_hash(value, "status_receipt_sha256")
    with pytest.raises(prep.PrepError, match="current harness"):
        prep.validate_ordered_status(value)


def test_forged_unlock_and_failed_causal_gate_are_refused():
    forged = _cpl1_unlock()
    forged["causal_gates"]["W_removal_erases_gain"] = False
    with pytest.raises(prep.PrepError, match="self-hash"):
        prep.validate_cpl1_unlock(forged)

    honestly_failed = prep.add_self_hash(forged, "receipt_sha256")
    with pytest.raises(prep.PrepError, match="W_removal_erases_gain"):
        prep.validate_cpl1_unlock(honestly_failed)

    payload_tamper = _cpl1_unlock()
    payload_tamper["numeric_packet"]["payload"]["numeric_delta"] = 0.75
    payload_tamper = prep.add_self_hash(payload_tamper, "receipt_sha256")
    with pytest.raises(prep.PrepError, match="canonical packet_sha256 mismatch"):
        prep.validate_cpl1_unlock(payload_tamper)


def test_build_manifest_is_deterministic_and_self_hashes_all_inputs(tmp_path):
    chain = _development_chain(tmp_path)
    manifest = chain["manifest"]
    assert isinstance(manifest, dict)
    prep.verify_self_hash(manifest, "manifest_self_sha256", "manifest")
    assert manifest["mode"] == "development"
    assert manifest["ordered_active_gate"] == prep.P4_GATE
    assert manifest["preregistration"]["sha256"] == prep.sha256_path(
        chain["prereg_path"]  # type: ignore[arg-type]
    )
    assert manifest["cpl1_unlock"]["receipt_sha256"] == _cpl1_unlock()[
        "receipt_sha256"
    ]
    assert set(manifest["legacy_immutable_sha256"]) == set(prep.LEGACY_IMMUTABLE)
    assert all(len(value) == 64 for value in manifest["implementation_sha256"].values())


def test_synthetic_integrity_chain_can_only_offline_seal(tmp_path):
    sealed = _seal(_development_chain(tmp_path))
    assert sealed["mode"] == "offline-sealed"
    assert sealed["measurement_authorized"] is False
    assert sealed["authority_state"] == "BLOCKED_EXTERNAL_AUTHORITIES_AND_RUNTIME_MISSING"
    assert "external_user_ratification_receipt" in sealed["missing_authorities"]
    prep.verify_self_hash(sealed, "manifest_self_sha256", "sealed manifest")


def test_forged_manifest_refused_after_outer_receipts_are_rebound(tmp_path):
    chain = _development_chain(tmp_path)
    manifest = _read(chain["manifest_path"])  # type: ignore[arg-type]
    manifest["implementation_sha256"]["f5v2_operators.py"] = "f" * 64
    manifest = prep.add_self_hash(manifest, "manifest_self_sha256")
    _write(chain["manifest_path"], manifest)  # type: ignore[arg-type]

    prep_receipt = prep.build_prep_receipt(
        manifest, dev_manifest_path=chain["manifest_path"]  # type: ignore[arg-type]
    )
    _write(chain["prep_receipt_path"], prep_receipt)  # type: ignore[arg-type]
    _write(chain["smoke_path"], _smoke(chain["manifest_path"]))  # type: ignore[arg-type]

    with pytest.raises(prep.PrepError, match="does not reproduce"):
        _seal(chain)


def test_forged_prep_receipt_is_refused_even_with_valid_self_hash(tmp_path):
    chain = _development_chain(tmp_path)
    receipt = _read(chain["prep_receipt_path"])  # type: ignore[arg-type]
    receipt["manifest_sha256"] = "f" * 64
    receipt = prep.add_self_hash(receipt, "receipt_sha256")
    _write(chain["prep_receipt_path"], receipt)  # type: ignore[arg-type]
    with pytest.raises(prep.PrepError, match="not bound"):
        _seal(chain)


def test_hand_forged_pass_smoke_without_judge_self_hash_is_refused(tmp_path):
    chain = _development_chain(tmp_path)
    forged = {
        "schema_version": prep.DEV_SMOKE_SCHEMA,
        "status": "PASS",
        "manifest_sha256": prep.sha256_path(chain["manifest_path"]),  # type: ignore[arg-type]
        "gates": {
            "legacy_downscale_negative_reproduced": True,
            "bitemporal_fired": True,
            "provenance_passed": True,
            "canary_passed": True,
            "drm_lure_passed": True,
            "query_leakage_zero": True,
        },
    }
    _write(chain["smoke_path"], forged)  # type: ignore[arg-type]
    with pytest.raises(prep.PrepError, match="smoke verification"):
        _seal(chain)


def test_query_field_leakage_in_ratified_prereg_is_refused():
    prereg = _ratified_prereg()
    prereg["input_contract"]["denylist"].remove("query_sha256")
    with pytest.raises(prep.PrepError, match="query_sha256"):
        prep.validate_prereg(prereg)


def test_write_once_never_replaces_existing_artifact(tmp_path):
    path = tmp_path / "manifest.json"
    prep.write_once(path, {"v": 1})
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(prep.PrepError, match="refusing to replace"):
        prep.write_once(path, {"v": 2})
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_seal_cli_requires_prep_receipt(tmp_path, capsys):
    chain = _development_chain(tmp_path)
    out = tmp_path / "sealed.json"
    rc = prep.main(
        [
            "--seal",
            "--in",
            str(chain["manifest_path"]),
            "--dev-smoke",
            str(chain["smoke_path"]),
            "--out",
            str(out),
        ]
    )
    assert rc == 1
    assert not out.exists()
    assert "--prep-receipt" in capsys.readouterr().err


def test_cli_records_current_refusal_without_creating_manifest(tmp_path):
    out = tmp_path / "should-not-exist.json"
    refusal = tmp_path / "refusal.json"
    rc = prep.main(
        [
            "--prereg",
            str(PREREG_PATH),
            "--ordered-status",
            str(ORDERED_PATH),
            "--out",
            str(out),
            "--refusal-receipt",
            str(refusal),
        ]
    )
    assert rc == 1
    assert not out.exists()
    value = _read(refusal)
    assert value["status"] == "REFUSED"
    assert "does not declare user-ratified" in value["reason"]
