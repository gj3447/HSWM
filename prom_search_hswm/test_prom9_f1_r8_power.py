from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from prom_search_hswm.hswm_function_network import F1_ARMS, TYPED_ARM, VECTOR_ARM
from prom_search_hswm.hswm_typed_ports import canonical_json, canonical_sha256
from prom_search_hswm.prom9_f1_prior_exposure import SCHEMA as PRIOR_SCHEMA
from prom_search_hswm.prom9_f1_r8_environment import R8_DEPENDENCY_NAMES
from prom_search_hswm.prom9_f1_r8_power import (
    CONFIRMATORY_POOL_OFFSETS,
    DEVELOPMENT_OFFSETS,
    GOLD_SOURCE_SCHEMA,
    SELECTION_SCHEMA,
    PowerRefusal,
    _load_judge_core,
    build_power_receipt,
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
        "per_call_input_caps": {"1": 275, "2": 1691, "3": 2359},
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


def test_power_builder_success_rederives_full_embedded_development_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import prom_search_hswm.prom9_f1_r8_power as power
    import prom_search_hswm.prom9_f1_r8_runner as runner
    import prom_search_hswm.prom_f1_function_network as function_network

    development, confirmatory = _pages(tmp_path)
    prior = _prior()
    selection, gold_source = build_selection_receipts(
        prior_receipt=prior,
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
        run_id="f1-2wiki-r8-development-builder-test",
        mode="development",
        model="measured-model",
        model_revision="f" * 40,
        token_envelope=_envelope(),
        sealed_at="2026-07-29T00:00:00Z",
        preregistration_artifact_sha256=None,
    )
    manifest = artifacts["manifest"]
    gold = artifacts["gold"]
    source = artifacts["source_receipt"]
    evaluator = artifacts["evaluator_receipt"]
    accepted = {
        row["item_id"]: row["accepted_answers"][0] for row in gold["items"]
    }
    item_runs = [
        {
            "item_id": item["item_id"],
            "arm_id": arm,
            "answer": {
                "answer": accepted[item["item_id"]]
                if arm == TYPED_ARM
                else "incorrect",
                "abstain": False,
            },
        }
        for item in manifest["items"]
        for arm in F1_ARMS
    ]

    judge_path = (
        Path(__file__).resolve().parents[3]
        / "FINDINGS"
        / "hswm-f1-r8-try3-2026-07-28"
        / "f1_r8_lakatotree_judge.py"
    )
    judge_file_sha = hashlib.sha256(judge_path.read_bytes()).hexdigest()
    judge_semantic_sha = str(_load_judge_core(judge_path).judge_core_sha256(judge_path))
    environment_sha = "a" * 64
    dependency_sha = "b" * 64
    compatibility_root = "c" * 64
    bundle_sha = "d" * 64
    genesis_unsigned = {"schema_version": "test-genesis/v1"}
    genesis = {
        **genesis_unsigned,
        "genesis_sha256": canonical_sha256(genesis_unsigned),
    }
    deployment_sha = "e" * 64
    dependency_files = {
        name: {"sha256": canonical_sha256({"dependency": name})}
        for name in R8_DEPENDENCY_NAMES
    }
    dependency_files["judge_core"] = {"sha256": judge_file_sha}
    environment = {
        "labels": {
            "spool_endpoint": "https://spool.invalid",
            "model_upstream_endpoint": (
                "https://inference.invalid/v1/chat/completions"
            ),
            "model_deployment_receipt_sha256": deployment_sha,
            "model": manifest["model"],
            "model_revision": manifest["model_revision"],
            "run_id": manifest["run_id"],
            "hswm_commit": "1" * 40,
            "symposium_commit": "2" * 40,
        }
    }
    dependencies = {"files": dependency_files}
    environment_bundle = {
        "environment_receipt": environment,
        "dependency_receipt": dependencies,
        "bundle_sha256": bundle_sha,
    }
    lock_unsigned = {
        "manifest_sha256": canonical_sha256(manifest),
        "selection_receipt_sha256": selection["selection_receipt_sha256"],
        "prior_exposure_receipt_sha256": prior[
            "prior_exposure_receipt_sha256"
        ],
        "public_source_receipt_sha256": source["source_receipt_sha256"],
        "gold_source_receipt_sha256": gold_source[
            "gold_source_receipt_sha256"
        ],
        "gold_sha256": canonical_sha256(gold),
        "evaluator_receipt_sha256": evaluator["receipt_sha256"],
        "db_genesis_receipt_sha256": genesis["genesis_sha256"],
        "environment_receipt_sha256": environment_sha,
        "dependency_receipt_sha256": dependency_sha,
        "environment_dependency_compatibility_root_sha256": compatibility_root,
        "environment_dependency_bundle_sha256": bundle_sha,
        "judge_core_sha256": judge_semantic_sha,
        "judge_core_file_sha256": judge_file_sha,
        "hswm_commit": "1" * 40,
        "model": manifest["model"],
        "model_revision": manifest["model_revision"],
        "upstream_endpoint": environment["labels"]["model_upstream_endpoint"],
        "deployment_receipt_sha256": deployment_sha,
        "deployment_id": f"hswm:model_deployment:v2:{deployment_sha}",
        "served_model": manifest["model"],
        "execution_policy": {"endpoint": "https://spool.invalid", "max_workers": 1},
    }
    execution_lock = {
        **lock_unsigned,
        "lock_sha256": canonical_sha256(lock_unsigned),
    }
    suite = {
        "mode": "development",
        "run_id": manifest["run_id"],
        "manifest_sha256": canonical_sha256(manifest),
        "measurement_lock_sha256": execution_lock["lock_sha256"],
        "item_runs": item_runs,
        "token_parity": {"all_within_tolerance": True},
        "transport_audit": {
            "call_count": len(item_runs) * 3,
            "item_run_count": len(item_runs),
            "status_counts": {"ACCEPTED": len(item_runs) * 3},
        },
        "max_workers": 1,
        "gold_opened": False,
        "scientific_verdict_emitted": False,
        "upstream_endpoint": lock_unsigned["upstream_endpoint"],
        "deployment_receipt_sha256": deployment_sha,
        "deployment_id": lock_unsigned["deployment_id"],
        "served_model": manifest["model"],
        "model_revision": manifest["model_revision"],
    }

    monkeypatch.setattr(
        runner,
        "verify_suite_v3_without_gold",
        lambda _suite: canonical_sha256({"terminal-suite": True}),
    )
    monkeypatch.setattr(function_network, "_verify_token_blocks", lambda *_args: None)
    monkeypatch.setattr(power, "verify_preimage_bundle", lambda *_args, **_kwargs: compatibility_root)
    monkeypatch.setattr(power, "verify_environment_receipt", lambda *_args, **_kwargs: environment_sha)
    monkeypatch.setattr(power, "verify_dependency_receipt", lambda *_args, **_kwargs: dependency_sha)

    receipt = build_power_receipt(
        manifest=manifest,
        execution_lock=execution_lock,
        public_source_receipt=source,
        selection_receipt=selection,
        gold_source_receipt=gold_source,
        prior_exposure_receipt=prior,
        suite=suite,
        evaluator_receipt=evaluator,
        gold=gold,
        db_genesis_receipt=genesis,
        environment_dependency_bundle=environment_bundle,
        judge_core_path=judge_path,
    )
    expected_components = derive_development_components(
        manifest=manifest,
        suite=suite,
        gold=gold,
        selection_receipt=selection,
    )
    assert receipt["analysis_input"]["development_components"] == expected_components
    assert set(receipt["development_evidence"]["artifact_receipts"]) == {
        "selection_receipt_sha256",
        "prior_exposure_receipt_sha256",
        "execution_lock_sha256",
        "public_source_receipt_sha256",
        "gold_source_receipt_sha256",
        "suite_receipt_sha256",
        "evaluator_receipt_sha256",
        "db_genesis_receipt_sha256",
        "gold_sha256",
        "environment_receipt_sha256",
        "dependency_receipt_sha256",
        "environment_dependency_compatibility_root_sha256",
        "environment_dependency_bundle_sha256",
    }


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
