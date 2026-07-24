from __future__ import annotations

from copy import deepcopy

import pytest

from p1v2_l0_prepare import (
    P1V2PreparationError,
    build_l0_manifests,
    verify_l0_manifests,
)


def _questions(count=8):
    return [
        {
            "id": f"case-{index}",
            "question": f"Who is the person whose occupation is role-{index}?",
            "solution_traces": "sealed trace",
            "answer": [f"Person {index} A", f"Person {index} B"],
            "template": ["Who is", "the person whose", "occupation", "is", "role", "?"],
            "type": 6,
            "difficulty": 1,
            "is_aggregation_question": False,
        }
        for index in range(count)
    ]


def _has_forbidden_key(value):
    forbidden = {"answer", "answers", "gold_answers", "solution_trace", "solution_traces"}
    if isinstance(value, dict):
        return bool(forbidden & {str(key).casefold() for key in value}) or any(
            _has_forbidden_key(item) for item in value.values()
        )
    if isinstance(value, list):
        return any(_has_forbidden_key(item) for item in value)
    return False


def test_public_split_is_deterministic_and_gold_is_sealed():
    split_sizes = {"training": 2, "heldout": 3, "retention": 1}
    public, sealed = build_l0_manifests(
        _questions(),
        universe="fixture-universe",
        dataset_file_sha256={"questions/type6.json": "1" * 64},
        split_sizes=split_sizes,
    )
    repeated, repeated_sealed = build_l0_manifests(
        list(reversed(_questions())),
        universe="fixture-universe",
        dataset_file_sha256={"questions/type6.json": "1" * 64},
        split_sizes=split_sizes,
    )

    assert public == repeated
    assert sealed == repeated_sealed
    assert not _has_forbidden_key(public)
    assert len(public["splits"]["heldout"]) == 3
    assert public["sealed_gold_sha256"] == sealed["sealed_gold_sha256"]
    assert all("gold_answers" in row for row in sealed["cases"].values())


def test_selection_ids_do_not_depend_on_answers_or_solution_traces():
    original = _questions()
    mutated = deepcopy(original)
    for index, row in enumerate(mutated):
        row["answer"] = [f"Changed Gold {index}"]
        row["solution_traces"] = f"changed trace {index}"
    split_sizes = {"training": 2, "heldout": 3, "retention": 1}
    public_a, sealed_a = build_l0_manifests(
        original,
        universe="fixture",
        dataset_file_sha256={"questions/type6.json": "2" * 64},
        split_sizes=split_sizes,
    )
    public_b, sealed_b = build_l0_manifests(
        mutated,
        universe="fixture",
        dataset_file_sha256={"questions/type6.json": "2" * 64},
        split_sizes=split_sizes,
    )

    ids_a = {
        split: [row["case_id"] for row in public_a["splits"][split]]
        for split in split_sizes
    }
    ids_b = {
        split: [row["case_id"] for row in public_b["splits"][split]]
        for split in split_sizes
    }
    assert ids_a == ids_b
    assert sealed_a["sealed_gold_sha256"] != sealed_b["sealed_gold_sha256"]


def test_prepare_rejects_insufficient_or_duplicate_type6_ids():
    with pytest.raises(P1V2PreparationError, match="below required"):
        build_l0_manifests(
            _questions(2),
            universe="fixture",
            dataset_file_sha256={"questions/type6.json": "3" * 64},
            split_sizes={"training": 1, "heldout": 1, "retention": 1},
        )
    duplicated = _questions(4)
    duplicated[1]["id"] = duplicated[0]["id"]
    with pytest.raises(P1V2PreparationError, match="unique"):
        build_l0_manifests(
            duplicated,
            universe="fixture",
            dataset_file_sha256={"questions/type6.json": "3" * 64},
            split_sizes={"training": 1, "heldout": 1, "retention": 1},
        )


def test_readback_verifier_rejects_public_or_sealed_tamper():
    public, sealed = build_l0_manifests(
        _questions(),
        universe="fixture",
        dataset_file_sha256={"questions/type6.json": "4" * 64},
        split_sizes={"training": 2, "heldout": 3, "retention": 1},
    )
    public_tampered = deepcopy(public)
    public_tampered["splits"]["heldout"][0]["question"] = "tampered"
    with pytest.raises(P1V2PreparationError, match="self-hash"):
        verify_l0_manifests(public_tampered, sealed)

    sealed_tampered = deepcopy(sealed)
    first_id = next(iter(sealed_tampered["cases"]))
    sealed_tampered["cases"][first_id]["gold_answers"] = ["tampered"]
    with pytest.raises(P1V2PreparationError, match="self-hash"):
        verify_l0_manifests(public, sealed_tampered)
