from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest

import prom_search_hswm.prom9_f1_prior_exposure as prior_exposure
from prom_search_hswm.hswm_typed_ports import canonical_sha256
from prom_search_hswm.prom9_f1_prior_exposure import (
    ABORTED_ATTEMPT_EXPOSURE_SCHEMA,
    ABORTED_ATTEMPT_STATUS,
    EXPECTED_PAGE_SPECS,
    PriorExposureRefusal,
    SCHEMA,
    build_prior_exposure_receipt,
    inventory_stable_tree,
    merge_exposure_boundaries,
    verify_aborted_attempt_exposure_receipt,
    verify_prior_exposure_receipt,
    write_private_once,
)
from prom_search_hswm.prom9_f1_r8_runner import (
    R8RunnerRefusal,
    read_stable_json,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
INCIDENT_RECEIPT_PATH = (
    REPO_ROOT / "receipts" / "hswm_f1_r8_v8_aborted_exposure.v1.json"
)
INCIDENT_RECEIPT_SHA256 = (
    "6d3f2f8978a8502c0f01135ad7b998841dbb4bd61462934927f735e3932bad7d"
)


def _row(index: int) -> dict[str, object]:
    return {
        "id": f"item-{index:03d}",
        "question": f"Question {index}?",
        "answer": f"PRIVATE_ANSWER_{index}",
        "context": {
            "title": [f"Title {index}"],
            "sentences": [[f"Sentence {index}."]],
        },
        "supporting_facts": {"title": [], "sent_id": []},
        "evidences": [],
        "type": "comparison",
    }


def _private_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(0o600)


def _fixture(tmp_path: Path):
    rows = [_row(index) for index in range(104)]
    pages: dict[tuple[int, int], tuple[Path, str]] = {}
    for offset, length in EXPECTED_PAGE_SPECS:
        value = {"rows": [{"row": row} for row in rows[offset : offset + length]]}
        path = tmp_path / f"page-{offset}-{length}.json"
        _private_json(path, value)
        pages[(offset, length)] = (path, canonical_sha256(value))

    root = tmp_path / "artifacts"
    run = root / "f1-2wiki-sealed-r1"
    run.mkdir(parents=True)
    item_ids = [f"item-{index:03d}" for index in range(4, 104)]
    _private_json(
        run / "manifest.v2.json",
        {"run_id": "f1-2wiki-sealed-r1", "items": [{"item_id": value} for value in item_ids]},
    )
    _private_json(
        run / "suite.json",
        {
            "run_id": "f1-2wiki-sealed-r1",
            "item_runs": [{"item_id": value} for value in item_ids],
        },
    )
    source_unsigned = {
        "schema_version": "hswm-prom9-f1-2wiki-source-receipt/v1",
        "run_id": "f1-2wiki-sealed-r1",
        "offset": 4,
        "length": 100,
        "viewer_response_sha256": pages[(4, 100)][1],
        "rows": [{"item_id": value} for value in item_ids],
    }
    _private_json(
        run / "source.receipt.json",
        {**source_unsigned, "source_receipt_sha256": canonical_sha256(source_unsigned)},
    )
    opaque = run / "gold.separate.json"
    opaque.write_bytes(b"PRIVATE_ANSWER_SENTINEL not-json by design")
    opaque.chmod(0o600)
    return pages, root


def _receipt(tmp_path: Path):
    pages, root = _fixture(tmp_path)
    return build_prior_exposure_receipt(
        page_files=pages,
        artifact_roots={"fixture": root},
        dataset="framolfese/2WikiMultihopQA",
        config="default",
        split="validation",
        expected_run_dirs=1,
        expected_legacy_source_receipts=1,
        expected_manifests=1,
        expected_suites=1,
    )


def _incident_receipt() -> dict[str, object]:
    value, _raw_file_sha256 = read_stable_json(
        INCIDENT_RECEIPT_PATH, "aborted-attempt exposure receipt"
    )
    return value


def _resign_incident(value: dict[str, object]) -> None:
    unsigned = copy.deepcopy(value)
    unsigned.pop("aborted_attempt_exposure_receipt_sha256", None)
    value["aborted_attempt_exposure_receipt_sha256"] = canonical_sha256(unsigned)


def _minimal_prior(
    *, item_ids: list[str], source_entity_ids: list[str], component_ids: list[str]
) -> dict[str, object]:
    aggregate = {
        "prior_item_ids": item_ids,
        "prior_source_entity_ids": source_entity_ids,
        "prior_component_ids": component_ids,
        "item_root_sha256": canonical_sha256(item_ids),
        "source_entity_root_sha256": canonical_sha256(source_entity_ids),
        "component_root_sha256": canonical_sha256(component_ids),
    }
    unsigned = {
        "schema_version": SCHEMA,
        "aggregate": aggregate,
        "complete": True,
    }
    return {
        **unsigned,
        "prior_exposure_receipt_sha256": canonical_sha256(unsigned),
    }


def test_complete_receipt_has_exact_104_item_union_and_opaque_gold(tmp_path: Path) -> None:
    receipt = _receipt(tmp_path)
    assert receipt["complete"] is True
    assert receipt["counts"]["items"] == 104
    assert receipt["counts"]["pages"] == 4
    assert receipt["counts"]["legacy_source_receipts"] == 1
    assert verify_prior_exposure_receipt(receipt) == receipt[
        "prior_exposure_receipt_sha256"
    ]
    gold = next(
        row for row in receipt["artifact_inventory"] if row["path"].endswith("gold.separate.json")
    )
    assert gold["size_bytes"] == len(b"PRIVATE_ANSWER_SENTINEL not-json by design")


def test_missing_or_hash_drifted_legacy_page_is_refused(tmp_path: Path) -> None:
    pages, root = _fixture(tmp_path)
    missing = dict(pages)
    missing.pop((0, 1))
    with pytest.raises(PriorExposureRefusal, match="four legacy pages"):
        build_prior_exposure_receipt(
            page_files=missing,
            artifact_roots={"fixture": root},
            dataset="dataset",
            config="default",
            split="validation",
            expected_run_dirs=1,
            expected_legacy_source_receipts=1,
            expected_manifests=1,
            expected_suites=1,
        )
    drifted = dict(pages)
    drifted[(0, 1)] = (pages[(0, 1)][0], "0" * 64)
    with pytest.raises(PriorExposureRefusal, match="page hash drifted"):
        build_prior_exposure_receipt(
            page_files=drifted,
            artifact_roots={"fixture": root},
            dataset="dataset",
            config="default",
            split="validation",
            expected_run_dirs=1,
            expected_legacy_source_receipts=1,
            expected_manifests=1,
            expected_suites=1,
        )


def test_prior_receipt_self_hash_tamper_is_refused(tmp_path: Path) -> None:
    receipt = _receipt(tmp_path)
    tampered = copy.deepcopy(receipt)
    tampered["aggregate"]["prior_item_ids"].pop()
    with pytest.raises(PriorExposureRefusal, match="self-hash"):
        verify_prior_exposure_receipt(tampered)


def test_artifact_tree_refuses_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    root.mkdir()
    target = root / "target"
    target.write_bytes(b"value")
    (root / "link").symlink_to(target)
    with pytest.raises(PriorExposureRefusal, match="symlink"):
        inventory_stable_tree("fixture", root)


def test_private_reader_refuses_lstat_to_open_identity_swap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "private.json"
    replacement = tmp_path / "replacement.json"
    _private_json(target, {"identity": "before"})
    _private_json(replacement, {"identity": "after"})
    original_open = os.open
    swapped = False

    def swapping_open(path, flags, *args):
        nonlocal swapped
        if not swapped and Path(path) == target:
            os.replace(replacement, target)
            swapped = True
        return original_open(path, flags, *args)

    monkeypatch.setattr(prior_exposure.os, "open", swapping_open)
    with pytest.raises(PriorExposureRefusal, match="changed before"):
        prior_exposure._read_private_bytes(target)


def test_private_write_is_0600_and_write_once(tmp_path: Path) -> None:
    output = tmp_path / "receipt.json"
    write_private_once(output, {"value": 1})
    assert os.stat(output).st_mode & 0o777 == 0o600
    with pytest.raises(PriorExposureRefusal, match="replace"):
        write_private_once(output, {"value": 2})


def test_aborted_attempt_receipt_is_exact_complete_public_metadata() -> None:
    receipt = _incident_receipt()
    assert receipt["schema_version"] == ABORTED_ATTEMPT_EXPOSURE_SCHEMA
    assert receipt["status"] == ABORTED_ATTEMPT_STATUS
    assert receipt["complete"] is True
    assert set(receipt["run_identity"]) == {
        "carrier_commit",
        "ended_at",
        "host",
        "implementation_commit",
        "job_name",
        "model",
        "model_revision",
        "run_id",
        "stage_path",
        "started_at",
    }
    assert receipt["run_identity"]["job_name"] == (
        "hswm-f1-r8-v8-development-825"
    )
    assert receipt["run_identity"]["stage_path"] == (
        "/data/kjra/PROJECT/PI/hswm_f1_r8_try3_v8_20260729"
    )
    assert receipt["run_identity"]["host"] == (
        "airobotics-Precision-7960-Tower"
    )
    assert receipt["run_identity"]["started_at"] == (
        "2026-07-29T23:15:22+09:00"
    )
    assert receipt["run_identity"]["ended_at"] == (
        "2026-07-29T23:15:34+09:00"
    )
    assert (
        verify_aborted_attempt_exposure_receipt(receipt)
        == INCIDENT_RECEIPT_SHA256
        == receipt["aborted_attempt_exposure_receipt_sha256"]
    )
    accepted = receipt["accepted_upstream_calls"]
    assert isinstance(accepted, list) and len(accepted) == 1
    assert accepted[0]["physical_call_id"] == (
        "3c9261a5e38c986c54e6c0bde7321baa4d9f7d2ef2052d407e864b4ee61a1f04"
    )
    assert accepted[0]["arm_id"] == "typed_hswm_three_function_network"
    assert accepted[0]["function_id"] == "QF_QUERY_COMPILER"
    assert accepted[0]["dataset_row_index"] == 124
    assert len(accepted[0]["source_entity_ids"]) == 10
    local_only = receipt["local_only_calls"]
    assert isinstance(local_only, list) and local_only[0]["state"] == (
        "SENT_NOT_UPSTREAM"
    )
    assert local_only[0]["arm_id"] == "typed_hswm_three_function_network"
    assert local_only[0]["function_id"] == "BF_BOND_PROPOSER"


def test_aborted_attempt_file_gate_refuses_duplicate_keys(tmp_path: Path) -> None:
    original = INCIDENT_RECEIPT_PATH.read_text(encoding="utf-8")
    duplicated = original.replace(
        '  "status": "ABORTED_QUARANTINED",',
        '  "status": "ABORTED",\n  "status": "ABORTED_QUARANTINED",',
        1,
    )
    assert duplicated != original
    path = tmp_path / "duplicate-key-incident.json"
    path.write_text(duplicated, encoding="utf-8")
    with pytest.raises(R8RunnerRefusal, match="duplicate JSON key"):
        read_stable_json(path, "aborted-attempt exposure receipt")


@pytest.mark.parametrize(
    ("section", "field", "replacement"),
    [
        ("non_exposure_boundary", "runner_gold_opened", True),
        ("non_exposure_boundary", "runner_gold_opened", 0),
        ("counts", "accepted_development_upstream_calls", 2),
        ("counts", "accepted_development_upstream_calls", True),
        ("termination", "exit_code", 135.0),
        ("accepted_upstream_calls", 0, None),
        (None, "status", "ABORTED"),
    ],
)
def test_aborted_attempt_tamper_and_resign_is_refused(
    section: str | None, field: str | int, replacement: object
) -> None:
    receipt = _incident_receipt()
    target = receipt if section is None else receipt[section]
    if section == "accepted_upstream_calls":
        assert isinstance(target, list) and field == 0
        accepted = target[0]
        assert isinstance(accepted, dict)
        accepted["dataset_row_index"] = 124.0
    else:
        assert isinstance(target, dict) and isinstance(field, str)
        target[field] = replacement
    _resign_incident(receipt)
    with pytest.raises(PriorExposureRefusal):
        verify_aborted_attempt_exposure_receipt(receipt)


def test_aborted_attempt_aggregate_root_mismatch_is_refused_after_resign() -> None:
    receipt = _incident_receipt()
    aggregate = receipt["aggregate"]
    assert isinstance(aggregate, dict)
    aggregate["source_entity_root_sha256"] = "0" * 64
    _resign_incident(receipt)
    with pytest.raises(PriorExposureRefusal, match="aggregate root"):
        verify_aborted_attempt_exposure_receipt(receipt)


def test_merge_exposure_boundaries_returns_sorted_canonical_union() -> None:
    incident = _incident_receipt()
    incident_aggregate = incident["aggregate"]
    assert isinstance(incident_aggregate, dict)
    incident_items = incident_aggregate["prior_item_ids"]
    incident_sources = incident_aggregate["prior_source_entity_ids"]
    incident_components = incident_aggregate["prior_component_ids"]
    assert isinstance(incident_items, list)
    assert isinstance(incident_sources, list)
    assert isinstance(incident_components, list)
    prior = _minimal_prior(
        item_ids=sorted(["000-prior-item", incident_items[0]]),
        source_entity_ids=sorted(["0" * 64, incident_sources[0]]),
        component_ids=sorted(["0" * 64, incident_components[0]]),
    )

    merged = merge_exposure_boundaries(prior, incident)
    expected_items = sorted({"000-prior-item", *incident_items})
    expected_sources = sorted({"0" * 64, *incident_sources})
    expected_components = sorted({"0" * 64, *incident_components})
    assert merged == {
        "prior_exposure_receipt_sha256": prior[
            "prior_exposure_receipt_sha256"
        ],
        "aborted_attempt_exposure_receipt_sha256": INCIDENT_RECEIPT_SHA256,
        "item_ids": expected_items,
        "source_entity_ids": expected_sources,
        "component_ids": expected_components,
        "item_root_sha256": canonical_sha256(expected_items),
        "source_entity_root_sha256": canonical_sha256(expected_sources),
        "component_root_sha256": canonical_sha256(expected_components),
    }
