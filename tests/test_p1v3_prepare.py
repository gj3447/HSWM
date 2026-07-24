from __future__ import annotations

from copy import deepcopy
import json

import pytest

from p1v3_prepare import (
    P1V3PreparationError,
    build_policy_manifests,
    verify_policy_manifests,
)


def _fixture():
    articles = []
    questions = []
    for index in range(12):
        title = f"Person{index}"
        value = f"job{index}"
        articles.append({
            "title": title,
            "article": f"The occupation of {title} is {value}.",
        })
        questions.append({
            "id": f"case:{index}",
            "type": 6,
            "question": f"Who is the person whose occupation is {value}?",
        })
    return questions, articles


def _build():
    questions, articles = _fixture()
    return build_policy_manifests(
        questions,
        articles,
        universe="fixture-seed3",
        dataset_file_sha256={"articles.json": "1" * 64, "questions/type6.json": "2" * 64},
        generation_receipt_sha256="3" * 64,
    )


def test_policy_manifests_are_deterministic_disjoint_and_public_blind():
    public, development, heldout = _build()
    questions, articles = _fixture()
    reversed_public, reversed_development, reversed_heldout = build_policy_manifests(
        list(reversed(questions)),
        list(reversed(articles)),
        universe="fixture-seed3",
        dataset_file_sha256={"articles.json": "1" * 64, "questions/type6.json": "2" * 64},
        generation_receipt_sha256="3" * 64,
    )

    assert public == reversed_public
    assert development == reversed_development
    assert heldout == reversed_heldout
    assert set(development["cases"]).isdisjoint(heldout["cases"])
    assert {row["split"] for row in development["cases"].values()} == {
        "training", "calibration"
    }
    assert {row["split"] for row in heldout["cases"].values()} == {"heldout"}
    assert {key: len(rows) for key, rows in public["splits"].items()} == {
        "training": 1,
        "calibration": 3,
        "heldout": 6,
    }
    all_ids = [row["case_id"] for rows in public["splits"].values() for row in rows]
    assert len(all_ids) == len(set(all_ids)) == 10
    encoded = json.dumps(public, sort_keys=True)
    for private in (
        "expected_answers", "trusted_source_ids", "distractor_source_ids",
        "trusted_class", "distractor_class", "gold_answers",
    ):
        assert private not in encoded
    assert public["selection"]["gold_answer_or_cardinality_inspected"] is False


def test_manifest_verifier_rejects_public_private_key_or_hash_tamper():
    public, development, heldout = _build()
    leaked = deepcopy(public)
    leaked["splits"]["heldout"][0]["expected_answers"] = ["Person0"]
    with pytest.raises(P1V3PreparationError, match="self-hash|sealed boundary"):
        verify_policy_manifests(leaked, development, heldout)

    tampered = deepcopy(development)
    tampered["cases"][next(iter(tampered["cases"]))]["expected_answers"] = ["wrong"]
    with pytest.raises(P1V3PreparationError, match="self-hash"):
        verify_policy_manifests(public, tampered, heldout)


def test_prepare_refuses_insufficient_single_match_candidates():
    questions, articles = _fixture()
    with pytest.raises(P1V3PreparationError, match="below"):
        build_policy_manifests(
            questions[:9],
            articles,
            universe="fixture-seed3",
            dataset_file_sha256={"articles.json": "1" * 64},
            generation_receipt_sha256="3" * 64,
        )
