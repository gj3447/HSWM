from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from prom_search_hswm.hswm_typed_ports import canonical_sha256
from prom_search_hswm.prom9_f1_r8_power import PowerRefusal
import prom_search_hswm.prom9_f1_r8_selection_v6 as selection_v6


PRIOR_SHA = "a" * 64
SUCCESSOR_SHA = "b" * 64
PREDECESSOR_SHA = "c" * 64


def _prior() -> dict[str, object]:
    return {"prior_exposure_receipt_sha256": PRIOR_SHA}


def _successor() -> dict[str, object]:
    return {
        "aborted_attempt_exposure_receipt_sha256": SUCCESSOR_SHA,
        "c800_incident": {
            "artifact_bindings": {
                "selection_receipt": {
                    "declared_hashes": {
                        "selection_receipt_sha256": PREDECESSOR_SHA,
                    }
                }
            }
        },
    }


def _predecessor() -> dict[str, object]:
    return {
        "selection_receipt_sha256": PREDECESSOR_SHA,
        "selection_policy": {"dataset_split": "train"},
        "source_pages": [{"offset": 104}],
        "development": {
            "item_ids": ["old-dev-item"],
            "source_entity_ids": ["1" * 64],
            "component_ids": ["2" * 64],
        },
        "confirmatory": {
            "item_ids": ["old-conf-item"],
            "source_entity_ids": ["3" * 64],
            "component_ids": ["4" * 64],
        },
    }


@pytest.fixture(autouse=True)
def _authorities(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        selection_v6, "verify_prior_exposure_receipt", lambda _value: PRIOR_SHA
    )
    monkeypatch.setattr(
        selection_v6,
        "verify_f1_r8_successor_exposure_set_v2",
        lambda _value: SUCCESSOR_SHA,
    )
    monkeypatch.setattr(
        selection_v6,
        "verify_predecessor_selection_receipt",
        lambda _value: PREDECESSOR_SHA,
    )
    monkeypatch.setattr(
        selection_v6,
        "merge_c801_exposure_boundaries",
        lambda _prior, _successor: {
            "prior_exposure_receipt_sha256": PRIOR_SHA,
            "aborted_attempt_exposure_receipt_sha256": SUCCESSOR_SHA,
            "item_ids": [],
            "source_entity_ids": [],
            "component_ids": [],
        },
    )


def _row(serial: int, *, confirmatory: bool = False) -> dict[str, object]:
    prefix = "conf" if confirmatory else "dev"
    if confirmatory:
        title = f"{prefix}-single-{serial:05d}"
    elif serial % 3 in (1, 2):
        title = f"{prefix}-pair-{serial - (serial % 3) + 1:05d}"
    else:
        title = f"{prefix}-single-{serial:05d}"
    return {
        "id": f"v6-{prefix}-item-{serial:05d}",
        "question": f"Question {serial}?",
        "answer": f"PRIVATE_{serial}",
        "context": {
            "title": [title],
            "sentences": [[f"Sentence {title}."]],
        },
        "supporting_facts": {"title": [], "sent_id": []},
        "evidences": [],
        "type": "comparison",
    }


def _page(path: Path, rows: list[dict[str, object]]) -> Path:
    path.write_text(
        json.dumps({"rows": [{"row": row} for row in rows]}),
        encoding="utf-8",
    )
    path.chmod(0o600)
    return path


def _pages(tmp_path: Path) -> tuple[dict[int, Path], dict[int, Path]]:
    development = {
        1504 + page * 100: _page(
            tmp_path / f"dev-{page}.json",
            [_row(page * 100 + index) for index in range(100)],
        )
        for page in range(13)
    }
    confirmatory = {
        5004 + page * 100: _page(
            tmp_path / f"conf-{page}.json",
            [
                _row(page * 100 + index, confirmatory=True)
                for index in range(100)
            ],
        )
        for page in range(9)
    }
    return development, confirmatory


def _rehash(value: dict[str, object]) -> None:
    unsigned = dict(value)
    unsigned.pop("selection_receipt_sha256", None)
    value["selection_receipt_sha256"] = canonical_sha256(unsigned)


def test_v6_builder_and_standalone_verifier_freeze_ratified_800_by_800(
    tmp_path: Path,
) -> None:
    development, confirmatory = _pages(tmp_path)
    selection, gold = selection_v6.build_selection_receipts_v6(
        prior_receipt=_prior(),
        successor_exposure_set=_successor(),
        predecessor_selection=_predecessor(),
        development_pages=development,
        confirmatory_pages=confirmatory,
    )

    policy = selection["selection_policy"]
    assert policy["development_components"] == 800
    assert policy["seed_blocks"] == 200
    assert policy["components_per_seed_block"] == 4
    assert policy["confirmatory_items"] == 800
    assert len(selection["development"]["component_schedule"]) == 800
    assert len(selection["confirmatory"]["component_schedule"]) == 800
    assert len(selection["confirmatory"]["item_ids"]) == 800
    assert selection_v6.verify_selection_receipt_v6(selection) == selection[
        "selection_receipt_sha256"
    ]
    assert selection_v6.verify_gold_source_receipt_v6(gold, selection) == gold[
        "gold_source_receipt_sha256"
    ]

    for field, replacement in (
        ("development_components", 799),
        ("seed_blocks", 199),
        ("confirmatory_items", 799),
    ):
        drifted = copy.deepcopy(selection)
        drifted["selection_policy"][field] = replacement
        _rehash(drifted)
        with pytest.raises(PowerRefusal, match="ratified c801 contract"):
            selection_v6.verify_selection_receipt_v6(drifted)

    drifted = copy.deepcopy(selection)
    drifted["development"]["selection_root_sha256"] = "0" * 64
    _rehash(drifted)
    with pytest.raises(PowerRefusal, match="schedule binding drifted"):
        selection_v6.verify_selection_receipt_v6(drifted)

    with pytest.raises(PowerRefusal, match="ratified 800/800 contract"):
        selection_v6.build_selection_receipts_v6(
            prior_receipt=_prior(),
            successor_exposure_set=_successor(),
            predecessor_selection=_predecessor(),
            development_pages=development,
            confirmatory_pages=confirmatory,
            development_components=796,
        )


def test_v6_cli_reports_only_contract_refusal_reason(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        selection_v6,
        "_read_private_bytes",
        lambda _path: b"{}",
    )
    monkeypatch.setattr(
        selection_v6,
        "_strict_object",
        lambda _raw, _label: {},
    )
    monkeypatch.setattr(
        "prom_search_hswm.prom9_f1_r8_runner.read_stable_json",
        lambda _path, _label: ({}, "f" * 64),
    )
    monkeypatch.setattr(
        selection_v6,
        "build_selection_receipts_v6",
        lambda **_kwargs: (_ for _ in ()).throw(PowerRefusal("safe contract reason")),
    )

    exit_code = selection_v6.main(
        [
            "select",
            "--prior-exposure-receipt",
            "prior.json",
            "--successor-exposure-set",
            "successor.json",
            "--predecessor-selection",
            "predecessor.json",
            "--development-page",
            "1504:dev.json",
            "--confirmatory-page",
            "5004:conf.json",
            "--dataset-split",
            "train",
            "--output",
            "selection.json",
            "--gold-source-output",
            "gold.json",
        ]
    )

    assert exit_code == 1
    assert json.loads(capsys.readouterr().err) == {
        "reason": "safe contract reason",
        "status": "REFUSED",
    }
