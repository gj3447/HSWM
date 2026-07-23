"""Freeze a leakage-resistant P1v3 source-policy split.

Selection reads only public type-6 questions and the count of exact matches in
the untouched base articles.  It selects single-match cases so every derived
packet has exactly one original true record and one deterministic decoy.  Gold
answers and the authoritative source-class mapping remain in a sealed sidecar.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from collections.abc import Mapping, Sequence
from typing import Any

from hswm_weight_snapshot import canonical_sha256
from p1v2_type6_environment import retrieve_exact_attribute_documents
from p1v3_policy_environment import (
    DEFAULT_DISTRACTOR_CLASS,
    DEFAULT_TRUSTED_CLASS,
    build_policy_conflict_case,
)


PUBLIC_SCHEMA_VERSION = "hswm-p1v3-policy-public-manifest/v1"
SEALED_SCHEMA_VERSION = "hswm-p1v3-policy-sealed-sidecar/v1"
DEFAULT_SELECTION_SEED = 20260724
DEFAULT_SPLITS = {"training": 1, "calibration": 3, "heldout": 6}


class P1V3PreparationError(ValueError):
    pass


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise P1V3PreparationError(f"{label} must be non-empty text")
    return value.strip()


def select_single_match_type6_ids(
    questions: Sequence[Mapping[str, Any]],
    articles: Sequence[Mapping[str, Any]],
    *,
    selection_seed: int = DEFAULT_SELECTION_SEED,
) -> tuple[str, ...]:
    """Select using only public ID, question text, type, and match count."""

    if not isinstance(selection_seed, int) or isinstance(selection_seed, bool):
        raise P1V3PreparationError("selection_seed must be an integer")
    selected: list[str] = []
    for row in questions:
        if not isinstance(row, Mapping) or row.get("type") != 6:
            continue
        case_id = _text(row.get("id"), "question id")
        question = _text(row.get("question"), "question")
        matches = retrieve_exact_attribute_documents(
            question, articles, top_k=len(articles)
        )
        if len(matches) == 1:
            selected.append(case_id)
    if len(selected) != len(set(selected)):
        raise P1V3PreparationError("candidate question IDs must be unique")
    return tuple(sorted(selected, key=lambda case_id: canonical_sha256({
        "selection_seed": selection_seed,
        "question_type": 6,
        "public_exact_match_count": 1,
        "case_id": case_id,
    })))


def build_policy_manifests(
    questions: Sequence[Mapping[str, Any]],
    articles: Sequence[Mapping[str, Any]],
    *,
    universe: str,
    dataset_file_sha256: Mapping[str, str],
    generation_receipt_sha256: str,
    selection_seed: int = DEFAULT_SELECTION_SEED,
    split_sizes: Mapping[str, int] = DEFAULT_SPLITS,
) -> tuple[dict[str, object], dict[str, object]]:
    if set(split_sizes) != {"training", "calibration", "heldout"}:
        raise P1V3PreparationError("split_sizes must contain the P1v3 split cut")
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value <= 0
        for value in split_sizes.values()
    ):
        raise P1V3PreparationError("split sizes must be positive integers")
    universe = _text(universe, "universe")
    hashes = dict(dataset_file_sha256)
    if (
        not hashes
        or any(
            not isinstance(key, str)
            or not key
            or not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
            for key, value in hashes.items()
        )
        or not isinstance(generation_receipt_sha256, str)
        or len(generation_receipt_sha256) != 64
        or any(character not in "0123456789abcdef" for character in generation_receipt_sha256)
    ):
        raise P1V3PreparationError("dataset and generation hashes are invalid")

    selected_ids = select_single_match_type6_ids(
        questions, articles, selection_seed=selection_seed
    )
    required = sum(split_sizes.values())
    if len(selected_ids) < required:
        raise P1V3PreparationError(
            f"single-match candidate count {len(selected_ids)} is below {required}"
        )
    selected_ids = selected_ids[:required]
    rows = {
        str(row.get("id")): row
        for row in questions
        if isinstance(row, Mapping) and row.get("type") == 6
    }
    public_splits: dict[str, list[dict[str, object]]] = {}
    sealed_cases: dict[str, dict[str, object]] = {}
    cursor = 0
    for split in ("training", "calibration", "heldout"):
        public_rows: list[dict[str, object]] = []
        for case_id in selected_ids[cursor:cursor + split_sizes[split]]:
            question = _text(rows[case_id].get("question"), "question")
            case = build_policy_conflict_case(
                case_id=case_id,
                question=question,
                articles=articles,
                trusted_class=DEFAULT_TRUSTED_CLASS,
                distractor_class=DEFAULT_DISTRACTOR_CLASS,
                maximum_true_documents=1,
            )
            public_row = case.public()
            public_row["split"] = split
            public_row["public_case_sha256"] = canonical_sha256(public_row)
            public_rows.append(public_row)
            sealed_cases[case_id] = {
                **case.sealed(),
                "split": split,
            }
        public_splits[split] = public_rows
        cursor += split_sizes[split]

    sealed: dict[str, object] = {
        "schema_version": SEALED_SCHEMA_VERSION,
        "universe": universe,
        "source_policy": {
            "trusted_class": DEFAULT_TRUSTED_CLASS,
            "distractor_class": DEFAULT_DISTRACTOR_CLASS,
            "global_within_universe": True,
        },
        "cases": sealed_cases,
    }
    sealed["sealed_sidecar_sha256"] = canonical_sha256(sealed)
    public: dict[str, object] = {
        "schema_version": PUBLIC_SCHEMA_VERSION,
        "universe": universe,
        "selection": {
            "question_type": 6,
            "selection_seed": selection_seed,
            "public_exact_match_count": 1,
            "selection_fields": [
                "type", "id", "question", "public_exact_match_count"
            ],
            "gold_answer_or_cardinality_inspected": False,
            "split_sizes": dict(split_sizes),
        },
        "opaque_source_classes": sorted(
            (DEFAULT_TRUSTED_CLASS, DEFAULT_DISTRACTOR_CLASS)
        ),
        "source_policy_semantics_published": False,
        "dataset_file_sha256": dict(sorted(hashes.items())),
        "generation_receipt_sha256": generation_receipt_sha256,
        "sealed_sidecar_sha256": sealed["sealed_sidecar_sha256"],
        "splits": public_splits,
    }
    forbidden = {
        "expected_answers", "trusted_source_ids", "distractor_source_ids",
        "trusted_class", "distractor_class", "gold_answers", "answer",
        "answers", "solution_trace", "solution_traces",
    }
    if forbidden & {key.casefold() for key in _recursive_keys(public)}:
        raise P1V3PreparationError("public manifest crossed the sealed boundary")
    public["public_manifest_sha256"] = canonical_sha256(public)
    verify_policy_manifests(public, sealed)
    return public, sealed


def verify_policy_manifests(
    public: Mapping[str, object], sealed: Mapping[str, object]
) -> None:
    if public.get("schema_version") != PUBLIC_SCHEMA_VERSION:
        raise P1V3PreparationError("public manifest schema drifted")
    if sealed.get("schema_version") != SEALED_SCHEMA_VERSION:
        raise P1V3PreparationError("sealed sidecar schema drifted")
    public_unsigned = dict(public)
    public_sha = public_unsigned.pop("public_manifest_sha256", None)
    sealed_unsigned = dict(sealed)
    sealed_sha = sealed_unsigned.pop("sealed_sidecar_sha256", None)
    if not isinstance(public_sha, str) or canonical_sha256(public_unsigned) != public_sha:
        raise P1V3PreparationError("public manifest self-hash drifted")
    if not isinstance(sealed_sha, str) or canonical_sha256(sealed_unsigned) != sealed_sha:
        raise P1V3PreparationError("sealed sidecar self-hash drifted")
    if public.get("sealed_sidecar_sha256") != sealed_sha:
        raise P1V3PreparationError("public manifest does not bind the sidecar")
    public_splits = public.get("splits")
    sealed_cases = sealed.get("cases")
    if not isinstance(public_splits, Mapping) or not isinstance(sealed_cases, Mapping):
        raise P1V3PreparationError("manifest split schema drifted")
    public_ids: list[str] = []
    for split in ("training", "calibration", "heldout"):
        rows = public_splits.get(split)
        if not isinstance(rows, list):
            raise P1V3PreparationError("public split must be a list")
        for row in rows:
            if not isinstance(row, Mapping) or row.get("split") != split:
                raise P1V3PreparationError("public case split drifted")
            case_id = row.get("case_id")
            if not isinstance(case_id, str):
                raise P1V3PreparationError("public case ID drifted")
            public_ids.append(case_id)
            sealed_row = sealed_cases.get(case_id)
            if not isinstance(sealed_row, Mapping) or sealed_row.get("split") != split:
                raise P1V3PreparationError("public and sealed splits disagree")
            if sealed_row.get("derivation_sha256") != row.get("derivation_sha256"):
                raise P1V3PreparationError("public and sealed derivations disagree")
    if len(public_ids) != len(set(public_ids)) or set(public_ids) != set(sealed_cases):
        raise P1V3PreparationError("manifest case cuts disagree")
    forbidden = {
        "expected_answers", "trusted_source_ids", "distractor_source_ids",
        "trusted_class", "distractor_class", "gold_answers", "answer",
        "answers", "solution_trace", "solution_traces",
    }
    if forbidden & {key.casefold() for key in _recursive_keys(public)}:
        raise P1V3PreparationError("public manifest crossed the sealed boundary")


def load_and_build(
    universe_path: Path,
    generation_receipt_path: Path,
    *,
    selection_seed: int = DEFAULT_SELECTION_SEED,
) -> tuple[dict[str, object], dict[str, object]]:
    articles_path = universe_path / "articles.json"
    questions_path = universe_path / "questions" / "type6.json"
    if not articles_path.is_file() or not questions_path.is_file():
        raise P1V3PreparationError("universe files are missing")
    articles = json.loads(articles_path.read_text(encoding="utf-8"))
    questions = json.loads(questions_path.read_text(encoding="utf-8"))
    generation = json.loads(generation_receipt_path.read_text(encoding="utf-8"))
    if not isinstance(articles, list) or not isinstance(questions, list):
        raise P1V3PreparationError("universe JSON schema drifted")
    generation_sha = generation.get("generation_receipt_sha256")
    if not isinstance(generation_sha, str):
        raise P1V3PreparationError("generation receipt hash is missing")
    return build_policy_manifests(
        questions,
        articles,
        universe=universe_path.name,
        dataset_file_sha256={
            "articles.json": _file_sha256(articles_path),
            "questions/type6.json": _file_sha256(questions_path),
        },
        generation_receipt_sha256=generation_sha,
        selection_seed=selection_seed,
    )


def _atomic_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_path = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    temporary = Path(raw_path)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write((json.dumps(
                value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
            ) + "\n").encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _recursive_keys(value: object):
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key)
            yield from _recursive_keys(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _recursive_keys(item)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe-path", type=Path, required=True)
    parser.add_argument("--generation-receipt", type=Path, required=True)
    parser.add_argument("--public-output", type=Path, required=True)
    parser.add_argument("--sealed-output", type=Path, required=True)
    parser.add_argument("--selection-seed", type=int, default=DEFAULT_SELECTION_SEED)
    args = parser.parse_args()
    public, sealed = load_and_build(
        args.universe_path,
        args.generation_receipt,
        selection_seed=args.selection_seed,
    )
    _atomic_write(args.sealed_output, sealed)
    _atomic_write(args.public_output, public)
    verify_policy_manifests(
        json.loads(args.public_output.read_text(encoding="utf-8")),
        json.loads(args.sealed_output.read_text(encoding="utf-8")),
    )
    print(json.dumps({
        "public_manifest_sha256": public["public_manifest_sha256"],
        "sealed_sidecar_sha256": sealed["sealed_sidecar_sha256"],
        "split_sizes": {key: len(value) for key, value in public["splits"].items()},
        "public_output": str(args.public_output),
        "sealed_output": str(args.sealed_output),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "P1V3PreparationError",
    "build_policy_manifests",
    "load_and_build",
    "select_single_match_type6_ids",
    "verify_policy_manifests",
]
