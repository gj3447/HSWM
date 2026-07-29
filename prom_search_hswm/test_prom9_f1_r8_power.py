from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from prom_search_hswm.hswm_function_network import F1_ARMS, TYPED_ARM, VECTOR_ARM
from prom_search_hswm.hswm_typed_ports import canonical_json, canonical_sha256
from prom_search_hswm.prom9_f1_prior_exposure import SCHEMA as PRIOR_SCHEMA
from prom_search_hswm.prom9_f1_r8_power import (
    CONFIRMATORY_POOL_OFFSETS,
    DEVELOPMENT_OFFSETS,
    GOLD_SOURCE_SCHEMA,
    SELECTION_SCHEMA,
    PowerRefusal,
    build_selection_receipts,
    derive_development_components,
    evaluator_selected_entries,
    replay_selection_receipt,
    _manifest_source_entity_ids,
    selected_entries,
    verify_gold_source_receipt,
    verify_selection_receipt,
)
from prom_search_hswm.prom9_f1_r8_source import build_artifacts


SENTINEL = "PRIVATE_SENTINEL_ANSWER"


def _prior() -> dict[str, object]:
    items = [f"prior-item-{index:03d}" for index in range(104)]
    entities = [canonical_sha256({"prior-entity": index}) for index in range(104)]
    components = [canonical_sha256({"prior-component": index}) for index in range(104)]
    unsigned = {
        "schema_version": PRIOR_SCHEMA,
        "aggregate": {
            "prior_item_ids": items,
            "prior_source_entity_ids": entities,
            "prior_component_ids": components,
            "item_root_sha256": canonical_sha256(items),
            "source_entity_root_sha256": canonical_sha256(entities),
            "component_root_sha256": canonical_sha256(components),
        },
        "complete": True,
    }
    return {**unsigned, "prior_exposure_receipt_sha256": canonical_sha256(unsigned)}


def _row(
    index: int, *, development: bool, answer: str | None = None
) -> dict[str, object]:
    if development and index < 200:
        title = f"development-pair-{index // 2:03d}"
    else:
        title = f"{'development' if development else 'confirmatory'}-{index:04d}"
    return {
        "id": f"{'dev' if development else 'r8'}-item-{index:04d}",
        "question": f"Question {index}?",
        "answer": answer if answer is not None else f"PRIVATE_{index}",
        "context": {"title": [title], "sentences": [[f"Sentence {title}."]]},
        "supporting_facts": {"title": [], "sent_id": []},
        "evidences": [],
        "type": "comparison",
    }


def _pages(tmp_path: Path, *, answer: str | None = None):
    development: dict[int, Path] = {}
    for page_index, offset in enumerate(DEVELOPMENT_OFFSETS):
        rows = [
            _row(page_index * 100 + index, development=True, answer=answer)
            for index in range(100)
        ]
        path = tmp_path / f"dev-{offset}.json"
        path.write_text(json.dumps({"rows": [{"row": row} for row in rows]}), encoding="utf-8")
        path.chmod(0o600)
        development[offset] = path
    confirmatory: dict[int, Path] = {}
    for page_index, offset in enumerate(CONFIRMATORY_POOL_OFFSETS):
        rows = [
            _row(page_index * 100 + index, development=False, answer=answer)
            for index in range(100)
        ]
        path = tmp_path / f"r8-{offset}.json"
        path.write_text(json.dumps({"rows": [{"row": row} for row in rows]}), encoding="utf-8")
        path.chmod(0o600)
        confirmatory[offset] = path
    return development, confirmatory


def _envelope() -> dict[str, object]:
    return {
        "per_call_input_caps": {"1": 280, "2": 1713, "3": 2152},
        "per_call_output_caps": {"1": 768, "2": 1536, "3": 768},
    }


def test_public_selection_v2_and_private_gold_source_are_physically_separate(
    tmp_path: Path,
) -> None:
    development, confirmatory = _pages(tmp_path, answer=SENTINEL)
    selection, gold_source = build_selection_receipts(
        prior_receipt=_prior(),
        development_pages=development,
        confirmatory_pages=confirmatory,
    )
    assert selection["schema_version"] == SELECTION_SCHEMA
    assert gold_source["schema_version"] == GOLD_SOURCE_SCHEMA
    assert verify_selection_receipt(selection) == selection["selection_receipt_sha256"]
    assert replay_selection_receipt(selection, prior_receipt=_prior()) == selection[
        "selection_receipt_sha256"
    ]
    assert verify_gold_source_receipt(gold_source, selection) == gold_source[
        "gold_source_receipt_sha256"
    ]
    assert SENTINEL not in canonical_json(selection)
    assert SENTINEL in canonical_json(gold_source)
    public_rows = selected_entries(selection, "development")
    full_rows = evaluator_selected_entries(selection, gold_source, "development")
    assert all(set(entry) == {"dataset_row_index", "row"} for entry in public_rows)
    assert all(set(entry["row"]) == {"id", "question", "context", "type"} for entry in public_rows)
    assert all("answer" in entry["row"] for entry in full_rows)
    assert len(selection["development"]["component_schedule"]) == 48
    assert len(selection["confirmatory"]["item_ids"]) == 100


def test_answer_only_mutation_leaves_public_selection_byte_identical(
    tmp_path: Path,
) -> None:
    development, confirmatory = _pages(tmp_path, answer="FIRST_PRIVATE")
    first_selection, first_gold_source = build_selection_receipts(
        prior_receipt=_prior(),
        development_pages=development,
        confirmatory_pages=confirmatory,
    )
    for path in development.values():
        page = json.loads(path.read_text(encoding="utf-8"))
        for wrapped in page["rows"]:
            wrapped["row"]["answer"] = "MUTATED_PRIVATE"
        path.write_text(json.dumps(page), encoding="utf-8")
        path.chmod(0o600)
    second_selection, second_gold_source = build_selection_receipts(
        prior_receipt=_prior(),
        development_pages=development,
        confirmatory_pages=confirmatory,
    )
    assert first_selection == second_selection
    assert first_gold_source != second_gold_source
    assert first_gold_source["gold_source_receipt_sha256"] != second_gold_source[
        "gold_source_receipt_sha256"
    ]


def test_select_cli_requires_distinct_public_and_gold_source_outputs(tmp_path: Path) -> None:
    development, confirmatory = _pages(tmp_path, answer=SENTINEL)
    prior_path = tmp_path / "prior.json"
    prior_path.write_text(json.dumps(_prior()), encoding="utf-8")
    prior_path.chmod(0o600)
    public_path = tmp_path / "selection.json"
    gold_source_path = tmp_path / "gold-source.json"
    command = [
        sys.executable, "-m", "prom_search_hswm.prom9_f1_r8_power", "select",
        "--prior-exposure-receipt", str(prior_path),
    ]
    for offset, path in development.items():
        command.extend(["--development-page", f"{offset}:{path}"])
    for offset, path in confirmatory.items():
        command.extend(["--confirmatory-page", f"{offset}:{path}"])
    command.extend(
        ["--output", str(public_path), "--gold-source-output", str(gold_source_path)]
    )
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert SENTINEL not in result.stdout + result.stderr
    assert SENTINEL not in public_path.read_text(encoding="utf-8")
    assert SENTINEL in gold_source_path.read_text(encoding="utf-8")
    assert os.stat(public_path).st_mode & 0o777 == 0o600
    assert os.stat(gold_source_path).st_mode & 0o777 == 0o600


def test_rehashed_block_swap_is_refused_by_public_selector_replay(tmp_path: Path) -> None:
    development, confirmatory = _pages(tmp_path)
    selection, _gold_source = build_selection_receipts(
        prior_receipt=_prior(),
        development_pages=development,
        confirmatory_pages=confirmatory,
    )
    tampered = copy.deepcopy(selection)
    schedule = tampered["development"]["component_schedule"]
    schedule[0]["seed_block"], schedule[5]["seed_block"] = (
        schedule[5]["seed_block"], schedule[0]["seed_block"]
    )
    unsigned = dict(tampered)
    unsigned.pop("selection_receipt_sha256")
    tampered["selection_receipt_sha256"] = canonical_sha256(unsigned)
    with pytest.raises(PowerRefusal, match="block assignment"):
        replay_selection_receipt(tampered, prior_receipt=_prior())


def test_terminal_components_use_evaluator_only_gold_after_the_run(tmp_path: Path) -> None:
    development, confirmatory = _pages(tmp_path)
    selection, gold_source = build_selection_receipts(
        prior_receipt=_prior(),
        development_pages=development,
        confirmatory_pages=confirmatory,
    )
    public_rows = selected_entries(selection, "development")
    full_rows = evaluator_selected_entries(selection, gold_source, "development")
    artifacts = build_artifacts(
        public_rows,
        full_rows,
        public_selection_receipt_sha256=selection["selection_receipt_sha256"],
        gold_source_receipt_sha256=gold_source["gold_source_receipt_sha256"],
        dataset="dataset",
        config="default",
        split="validation",
        run_id="f1-2wiki-r8-development-test",
        mode="development",
        model="model",
        model_revision="revision",
        token_envelope=_envelope(),
        sealed_at="2026-07-29T00:00:00Z",
        preregistration_artifact_sha256=None,
    )
    accepted = {
        row["item_id"]: row["accepted_answers"][0]
        for row in artifacts["gold"]["items"]
    }
    item_runs = []
    for index, item in enumerate(artifacts["manifest"]["items"]):
        for arm in F1_ARMS:
            correct = arm == TYPED_ARM or (arm == VECTOR_ARM and index % 3 == 0)
            item_runs.append(
                {
                    "item_id": item["item_id"],
                    "arm_id": arm,
                    "answer": {
                        "answer": accepted[item["item_id"]] if correct else "incorrect",
                        "abstain": False,
                    },
                }
            )
    components = derive_development_components(
        manifest=artifacts["manifest"],
        suite={
            "mode": "development",
            "run_id": artifacts["manifest"]["run_id"],
            "item_runs": item_runs,
        },
        gold=artifacts["gold"],
        selection_receipt=selection,
    )
    assert len(components) == 48
    assert {component["seed_block"] for component in components} == set(range(12))
    assert any(component["contrasts"][VECTOR_ARM] < 1.0 for component in components)


def test_manifest_source_entities_follow_source_receipt_set_semantics() -> None:
    entity = "e" * 64
    assert _manifest_source_entity_ids(
        {
            "candidates": [
                {"source_entity_id": entity},
                {"source_entity_id": entity},
            ]
        }
    ) == [entity]
