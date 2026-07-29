from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest

from prom_search_hswm.hswm_typed_ports import canonical_sha256
from prom_search_hswm.prom9_f1_prior_exposure import (
    EXPECTED_PAGE_SPECS,
    PriorExposureRefusal,
    build_prior_exposure_receipt,
    inventory_stable_tree,
    verify_prior_exposure_receipt,
    write_private_once,
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


def test_private_write_is_0600_and_write_once(tmp_path: Path) -> None:
    output = tmp_path / "receipt.json"
    write_private_once(output, {"value": 1})
    assert os.stat(output).st_mode & 0o777 == 0o600
    with pytest.raises(PriorExposureRefusal, match="replace"):
        write_private_once(output, {"value": 2})
