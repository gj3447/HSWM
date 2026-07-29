from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from prom_search_hswm.hswm_function_network import EvidenceCandidateV1
from prom_search_hswm.hswm_typed_ports import canonical_sha256
from prom_search_hswm.prom9_f1_r8_source import (
    COMPONENT_SCHEMA,
    R8SourceRefusal,
    build_artifacts,
    source_entity_id,
)


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


def _viewer(answer: str = "PRIVATE_SENTINEL_ANSWER") -> dict[str, object]:
    return {
        "rows": [
            _row("item-a", "Question A?", answer, [("Shared", ["One."])]),
            _row(
                "item-b",
                "Question B?",
                "second",
                [("Shared", ["One."]), ("Bridge", ["Two."])],
            ),
            _row("item-c", "Question C?", "third", [("Bridge", ["Two."])]),
        ]
    }


def _artifacts(viewer: dict[str, object]) -> dict[str, dict[str, object]]:
    return build_artifacts(
        viewer,
        dataset="framolfese/2WikiMultihopQA",
        config="default",
        split="validation",
        offset=504,
        length=3,
        run_id="f1-2wiki-sealed-r8-test",
        mode="sealed",
        model="fixed-model",
        model_revision="fixed-revision",
        token_envelope={"fixture": True},
        sealed_at="2026-07-29T00:00:00Z",
        preregistration_artifact_sha256="a" * 64,
    )


def test_optional_source_identity_preserves_legacy_candidate_hash() -> None:
    legacy = EvidenceCandidateV1(
        bond_id="bond",
        evidence_id="evidence",
        content="paragraph",
        observable={"score": 1.0},
    )
    expected = canonical_sha256(
        [
            {
                "bond_id": "bond",
                "evidence_id": "evidence",
                "content_sha256": canonical_sha256({"content": "paragraph"}),
            }
        ]
    )
    assert canonical_sha256([legacy.universe_identity()]) == expected

    entity = source_entity_id("Title", ["Sentence."])
    bound = EvidenceCandidateV1(
        bond_id="bond",
        evidence_id="evidence",
        content="paragraph",
        observable={"score": 1.0},
        source_entity_id=entity,
    )
    assert bound.universe_identity()["source_entity_id"] == entity
    assert canonical_sha256([bound.universe_identity()]) != expected


def test_transitive_shared_paragraphs_form_one_source_component() -> None:
    artifacts = _artifacts(_viewer())
    items = artifacts["manifest"]["items"]
    component_ids = {item["component_id"] for item in items}
    assert len(component_ids) == 1
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


def test_answer_mutation_cannot_change_public_manifest_or_source_entities() -> None:
    first = _artifacts(_viewer("first-private-answer"))
    changed_viewer = copy.deepcopy(_viewer("first-private-answer"))
    changed_viewer["rows"][0]["row"]["answer"] = "mutated-private-answer"
    second = _artifacts(changed_viewer)
    assert first["manifest"] == second["manifest"]
    first_rows = first["source_receipt"]["rows"]
    second_rows = second["source_receipt"]["rows"]
    assert [row["source_entity_ids"] for row in first_rows] == [
        row["source_entity_ids"] for row in second_rows
    ]
    assert first["source_receipt"]["raw_source_sha256"] != second["source_receipt"][
        "raw_source_sha256"
    ]


def test_cli_never_prints_answers_and_seals_outputs_0600(tmp_path: Path) -> None:
    viewer = tmp_path / "viewer.json"
    envelope = tmp_path / "envelope.json"
    viewer.write_text(json.dumps(_viewer()), encoding="utf-8")
    envelope.write_text(json.dumps({"fixture": True}), encoding="utf-8")
    outputs = {
        name: tmp_path / f"{name}.json"
        for name in ("manifest", "gold", "source", "evaluator")
    }
    command = [
        sys.executable,
        "-m",
        "prom_search_hswm.prom9_f1_r8_source",
        "--viewer-response-file",
        str(viewer),
        "--offset",
        "504",
        "--length",
        "3",
        "--run-id",
        "f1-2wiki-sealed-r8-test",
        "--mode",
        "sealed",
        "--model",
        "fixed-model",
        "--model-revision",
        "fixed-revision",
        "--token-envelope",
        str(envelope),
        "--sealed-at",
        "2026-07-29T00:00:00Z",
        "--preregistration-artifact-sha256",
        "a" * 64,
        "--manifest",
        str(outputs["manifest"]),
        "--gold",
        str(outputs["gold"]),
        "--source-receipt",
        str(outputs["source"]),
        "--evaluator-receipt",
        str(outputs["evaluator"]),
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "PRIVATE_SENTINEL_ANSWER" not in result.stdout
    assert "PRIVATE_SENTINEL_ANSWER" not in result.stderr
    assert all(os.stat(path).st_mode & 0o777 == 0o600 for path in outputs.values())


def test_sealed_artifacts_require_a_real_preregistration_hash() -> None:
    with pytest.raises(R8SourceRefusal, match="preregistration"):
        build_artifacts(
            _viewer(),
            dataset="dataset",
            config="default",
            split="validation",
            offset=0,
            length=3,
            run_id="f1-2wiki-sealed-r8-test",
            mode="sealed",
            model="model",
            model_revision="revision",
            token_envelope={},
            sealed_at="time",
            preregistration_artifact_sha256=None,
        )
