from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from prom_search_hswm.hswm_function_network import EvidenceCandidateV1
from prom_search_hswm.hswm_typed_ports import canonical_json, canonical_sha256
from prom_search_hswm.prom9_f1_r8_power import (
    build_selection_receipts,
    evaluator_selected_entries,
    selected_entries,
)
from prom_search_hswm.prom9_f1_r8_source import (
    COMPONENT_SCHEMA,
    EVALUATOR_SEAL_SCHEMA,
    GOLD_SCHEMA,
    SOURCE_RECEIPT_SCHEMA,
    R8SourceRefusal,
    build_artifacts,
    redact_entries,
    source_entity_id,
    verify_evaluator_seal,
    verify_public_source_receipt,
)
from prom_search_hswm.test_prom9_f1_r8_power import SENTINEL, _pages, _prior


def _row(item_id: str, question: str, answer: str, paragraphs: list[tuple[str, list[str]]]):
    return {
        "row": {
            "id": item_id,
            "question": question,
            "answer": answer,
            "context": {
                "title": [title for title, _ in paragraphs],
                "sentences": [sentences for _, sentences in paragraphs],
            },
            "supporting_facts": {"title": [], "sent_id": []},
            "evidences": [],
            "type": "comparison",
        }
    }


def _viewer(answer: str = SENTINEL) -> dict[str, object]:
    return {
        "rows": [
            _row("item-a", "Question A?", answer, [("Shared", ["One."])]),
            _row(
                "item-b", "Question B?", "second",
                [("Shared", ["One."]), ("Bridge", ["Two."])],
            ),
            _row("item-c", "Question C?", "third", [("Bridge", ["Two."])]),
        ]
    }


def _full_entries(viewer: dict[str, object]) -> list[dict[str, object]]:
    return [
        {"dataset_row_index": 504 + index, "row": copy.deepcopy(wrapped["row"])}
        for index, wrapped in enumerate(viewer["rows"])
    ]


def _envelope() -> dict[str, object]:
    return {
        "per_call_input_caps": {"1": 275, "2": 1691, "3": 2359},
        "per_call_output_caps": {"1": 768, "2": 1536, "3": 768},
    }


def _artifacts(viewer: dict[str, object]) -> dict[str, dict[str, object]]:
    full = _full_entries(viewer)
    public = redact_entries(full)
    return build_artifacts(
        public,
        full,
        public_selection_receipt_sha256=canonical_sha256(
            {"schema_version": "test-public-selection/v1", "rows": public}
        ),
        gold_source_receipt_sha256=canonical_sha256(
            {"schema_version": "test-gold-source/v1", "rows": full}
        ),
        dataset="framolfese/2WikiMultihopQA",
        config="default",
        split="validation",
        run_id="f1-2wiki-sealed-r8-test",
        mode="sealed",
        model="fixed-model",
        model_revision="fixed-revision",
        token_envelope=_envelope(),
        sealed_at="2026-07-29T00:00:00Z",
        preregistration_artifact_sha256="a" * 64,
    )


def test_optional_source_identity_preserves_legacy_candidate_hash() -> None:
    legacy = EvidenceCandidateV1(
        bond_id="bond", evidence_id="evidence", content="paragraph",
        observable={"score": 1.0},
    )
    expected = canonical_sha256(
        [{
            "bond_id": "bond", "evidence_id": "evidence",
            "content_sha256": canonical_sha256({"content": "paragraph"}),
        }]
    )
    assert canonical_sha256([legacy.universe_identity()]) == expected
    entity = source_entity_id("Title", ["Sentence."])
    bound = EvidenceCandidateV1(
        bond_id="bond", evidence_id="evidence", content="paragraph",
        observable={"score": 1.0}, source_entity_id=entity,
    )
    assert bound.universe_identity()["source_entity_id"] == entity


def test_public_source_v3_and_gold_v2_have_exact_separated_shapes() -> None:
    artifacts = _artifacts(_viewer())
    assert artifacts["source_receipt"]["schema_version"] == SOURCE_RECEIPT_SCHEMA
    assert artifacts["gold"]["schema_version"] == GOLD_SCHEMA
    assert set(artifacts["gold"]) == {"schema_version", "run_id", "items"}
    assert artifacts["evaluator_receipt"]["schema_version"] == EVALUATOR_SEAL_SCHEMA
    assert verify_public_source_receipt(artifacts["source_receipt"]) == artifacts[
        "source_receipt"
    ]["source_receipt_sha256"]
    assert verify_evaluator_seal(artifacts["evaluator_receipt"]) == artifacts[
        "evaluator_receipt"
    ]["receipt_sha256"]
    public_graph = {
        "manifest": artifacts["manifest"],
        "source": artifacts["source_receipt"],
        "summary": artifacts["summary"],
    }
    assert SENTINEL not in canonical_json(public_graph)
    assert SENTINEL in canonical_json(artifacts["gold"])
    assert SENTINEL not in canonical_json(artifacts["evaluator_receipt"])
    assert all(
        set(entry["row"]) == {"id", "question", "context", "type"}
        for entry in artifacts["source_receipt"]["redacted_rows"]
    )
    assert {
        item["max_input_tokens"] for item in artifacts["manifest"]["items"]
    } == {4325}


def test_transitive_shared_paragraphs_form_one_source_component() -> None:
    artifacts = _artifacts(_viewer())
    items = artifacts["manifest"]["items"]
    component_ids = {item["component_id"] for item in items}
    entities = sorted(
        {
            candidate["source_entity_id"]
            for item in items
            for candidate in item["candidates"]
        }
    )
    assert component_ids == {
        canonical_sha256(
            {"schema_version": COMPONENT_SCHEMA, "source_entity_ids": entities}
        )
    }


def test_answer_mutation_changes_only_evaluator_side_hashes() -> None:
    first = _artifacts(_viewer("first-private-answer"))
    changed = copy.deepcopy(_viewer("first-private-answer"))
    changed["rows"][0]["row"]["answer"] = "mutated-private-answer"
    second = _artifacts(changed)
    assert first["manifest"] == second["manifest"]
    assert first["source_receipt"] == second["source_receipt"]
    assert first["summary"] == second["summary"]
    assert first["gold"] != second["gold"]
    assert first["evaluator_receipt"] != second["evaluator_receipt"]
    assert first["evaluator_receipt"]["gold_sha256"] != second[
        "evaluator_receipt"
    ]["gold_sha256"]
    assert first["evaluator_receipt"]["gold_source_receipt_sha256"] != second[
        "evaluator_receipt"
    ]["gold_source_receipt_sha256"]


def test_cli_consumes_both_receipts_and_never_prints_answers(tmp_path: Path) -> None:
    development, confirmatory = _pages(tmp_path, answer=SENTINEL)
    selection, gold_source = build_selection_receipts(
        prior_receipt=_prior(),
        development_pages=development,
        confirmatory_pages=confirmatory,
    )
    public_rows = selected_entries(selection, "development")
    assert evaluator_selected_entries(selection, gold_source, "development")
    inputs = {
        "selection": tmp_path / "selection.json",
        "gold_source": tmp_path / "gold-source.json",
        "envelope": tmp_path / "envelope.json",
    }
    for name, value in (
        ("selection", selection), ("gold_source", gold_source),
        ("envelope", _envelope()),
    ):
        inputs[name].write_text(json.dumps(value), encoding="utf-8")
        inputs[name].chmod(0o600)
    outputs = {
        name: tmp_path / f"{name}.json"
        for name in ("manifest", "gold", "source", "evaluator")
    }
    command = [
        sys.executable, "-m", "prom_search_hswm.prom9_f1_r8_source",
        "--selection-receipt", str(inputs["selection"]),
        "--gold-source-receipt", str(inputs["gold_source"]),
        "--selection-cohort", "development",
        "--length", str(len(public_rows)),
        "--run-id", "f1-2wiki-r8-development-cli-test",
        "--mode", "development",
        "--model", "fixed-model",
        "--model-revision", "fixed-revision",
        "--token-envelope", str(inputs["envelope"]),
        "--sealed-at", "2026-07-29T00:00:00Z",
        "--manifest", str(outputs["manifest"]),
        "--gold", str(outputs["gold"]),
        "--source-receipt", str(outputs["source"]),
        "--evaluator-receipt", str(outputs["evaluator"]),
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert SENTINEL not in result.stdout + result.stderr
    assert SENTINEL not in outputs["manifest"].read_text(encoding="utf-8")
    assert SENTINEL not in outputs["source"].read_text(encoding="utf-8")
    assert SENTINEL not in outputs["evaluator"].read_text(encoding="utf-8")
    assert SENTINEL in outputs["gold"].read_text(encoding="utf-8")
    assert all(os.stat(path).st_mode & 0o777 == 0o600 for path in outputs.values())


def test_sealed_artifacts_require_preregistration_and_exact_token_caps() -> None:
    full = _full_entries(_viewer())
    public = redact_entries(full)
    kwargs = {
        "public_selection_receipt_sha256": "a" * 64,
        "gold_source_receipt_sha256": "b" * 64,
        "dataset": "dataset", "config": "default", "split": "validation",
        "run_id": "f1-2wiki-sealed-r8-test", "mode": "sealed",
        "model": "model", "model_revision": "revision", "sealed_at": "time",
    }
    with pytest.raises(R8SourceRefusal, match="preregistration"):
        build_artifacts(
            public, full, token_envelope=_envelope(),
            preregistration_artifact_sha256=None, **kwargs,
        )
    bad = _envelope()
    bad["per_call_output_caps"].pop("2")
    with pytest.raises(R8SourceRefusal, match="exact call 1/2/3"):
        build_artifacts(
            public, full, token_envelope=bad,
            preregistration_artifact_sha256="c" * 64, **kwargs,
        )
