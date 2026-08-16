"""Freeze a leakage-resistant PhantomWiki type-6 split for P1v2 L0.

Selection uses only ``type`` and ``id``.  Gold answers remain in a separate
sealed sidecar; the public manifest binds that sidecar by SHA-256 but never
contains answer values or solution traces.
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


PUBLIC_SCHEMA_VERSION = "hswm-p1v2-l0-public-manifest/v1"
SEALED_SCHEMA_VERSION = "hswm-p1v2-l0-sealed-gold/v1"
DEFAULT_SELECTION_SEED = 20260724
DEFAULT_SPLITS = {"training": 5, "heldout": 20, "retention": 5}


class P1V2PreparationError(ValueError):
    pass


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _nonempty_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise P1V2PreparationError(f"{label} must be non-empty text")
    return value.strip()


def select_type6_question_ids(
    questions: Sequence[Mapping[str, Any]],
    *,
    selection_seed: int = DEFAULT_SELECTION_SEED,
) -> tuple[str, ...]:
    """Select by registered type and content-addressed ID only."""

    if not isinstance(selection_seed, int) or isinstance(selection_seed, bool):
        raise P1V2PreparationError("selection seed must be an integer")
    ids: list[str] = []
    for question in questions:
        if not isinstance(question, Mapping):
            raise P1V2PreparationError("question rows must be mappings")
        if question.get("type") != 6:
            continue
        ids.append(_nonempty_text(question.get("id"), "question id"))
    if len(ids) != len(set(ids)):
        raise P1V2PreparationError("type-6 question IDs must be unique")
    return tuple(sorted(ids, key=lambda question_id: canonical_sha256({
        "selection_seed": selection_seed,
        "question_type": 6,
        "question_id": question_id,
    })))


def build_l0_manifests(
    questions: Sequence[Mapping[str, Any]],
    *,
    universe: str,
    dataset_file_sha256: Mapping[str, str],
    selection_seed: int = DEFAULT_SELECTION_SEED,
    split_sizes: Mapping[str, int] = DEFAULT_SPLITS,
) -> tuple[dict[str, object], dict[str, object]]:
    if set(split_sizes) != {"training", "heldout", "retention"}:
        raise P1V2PreparationError("split sizes must contain exactly the registered splits")
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value <= 0
        for value in split_sizes.values()
    ):
        raise P1V2PreparationError("split sizes must be positive integers")
    universe = _nonempty_text(universe, "universe")
    if not dataset_file_sha256 or any(
        not isinstance(key, str)
        or not key
        or not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
        for key, value in dataset_file_sha256.items()
    ):
        raise P1V2PreparationError("dataset files require lowercase SHA-256 values")

    selected_ids = select_type6_question_ids(
        questions, selection_seed=selection_seed
    )
    required = sum(split_sizes.values())
    if len(selected_ids) < required:
        raise P1V2PreparationError(
            f"type-6 question count {len(selected_ids)} is below required {required}"
        )
    selected_ids = selected_ids[:required]
    rows_by_id = {str(row.get("id")): row for row in questions if row.get("type") == 6}
    cursor = 0
    public_splits: dict[str, list[dict[str, object]]] = {}
    sealed_cases: dict[str, dict[str, object]] = {}
    for split in ("training", "heldout", "retention"):
        split_rows: list[dict[str, object]] = []
        for question_id in selected_ids[cursor:cursor + split_sizes[split]]:
            row = rows_by_id[question_id]
            template = row.get("template")
            if (
                not isinstance(template, list)
                or any(not isinstance(item, str) or not item for item in template)
            ):
                raise P1V2PreparationError("question template must be a list of text")
            difficulty = row.get("difficulty")
            if not isinstance(difficulty, int) or isinstance(difficulty, bool):
                raise P1V2PreparationError("question difficulty must be an integer")
            answers = row.get("answer")
            if (
                not isinstance(answers, list)
                or not answers
                or any(not isinstance(item, str) or not item for item in answers)
                or len(set(answers)) != len(answers)
            ):
                raise P1V2PreparationError("sealed answers must be unique non-empty text")
            public_row = {
                "case_id": question_id,
                "question": _nonempty_text(row.get("question"), "question"),
                "question_type": 6,
                "difficulty": difficulty,
                "template": list(template),
            }
            public_row["case_sha256"] = canonical_sha256(public_row)
            split_rows.append(public_row)
            sealed_cases[question_id] = {
                "split": split,
                "gold_answers": sorted(answers),
            }
        public_splits[split] = split_rows
        cursor += split_sizes[split]

    sealed: dict[str, object] = {
        "schema_version": SEALED_SCHEMA_VERSION,
        "universe": universe,
        "cases": sealed_cases,
    }
    sealed["sealed_gold_sha256"] = canonical_sha256(sealed)
    public: dict[str, object] = {
        "schema_version": PUBLIC_SCHEMA_VERSION,
        "universe": universe,
        "selection": {
            "question_type": 6,
            "selection_seed": selection_seed,
            "ordering": "sha256(selection_seed,question_type,question_id)",
            "selection_fields": ["type", "id"],
            "answer_cardinality_inspected_for_selection": False,
            "split_sizes": dict(split_sizes),
        },
        "dataset_file_sha256": dict(sorted(dataset_file_sha256.items())),
        "sealed_gold_sha256": sealed["sealed_gold_sha256"],
        "splits": public_splits,
    }
    forbidden = {"answer", "answers", "gold_answers", "solution_trace", "solution_traces"}
    if forbidden & {key.casefold() for key in _recursive_keys(public)}:
        raise P1V2PreparationError("public manifest crossed the sealed-gold boundary")
    public["public_manifest_sha256"] = canonical_sha256(public)
    verify_l0_manifests(public, sealed)
    return public, sealed


def verify_l0_manifests(
    public: Mapping[str, object], sealed: Mapping[str, object]
) -> None:
    if public.get("schema_version") != PUBLIC_SCHEMA_VERSION:
        raise P1V2PreparationError("unsupported public manifest schema")
    if sealed.get("schema_version") != SEALED_SCHEMA_VERSION:
        raise P1V2PreparationError("unsupported sealed-gold schema")
    public_unsigned = dict(public)
    public_digest = public_unsigned.pop("public_manifest_sha256", None)
    if not isinstance(public_digest, str) or canonical_sha256(public_unsigned) != public_digest:
        raise P1V2PreparationError("public manifest self-hash drifted")
    sealed_unsigned = dict(sealed)
    sealed_digest = sealed_unsigned.pop("sealed_gold_sha256", None)
    if not isinstance(sealed_digest, str) or canonical_sha256(sealed_unsigned) != sealed_digest:
        raise P1V2PreparationError("sealed-gold self-hash drifted")
    if public.get("sealed_gold_sha256") != sealed_digest:
        raise P1V2PreparationError("public manifest does not bind the sealed sidecar")
    public_splits = public.get("splits")
    sealed_cases = sealed.get("cases")
    if not isinstance(public_splits, Mapping) or not isinstance(sealed_cases, Mapping):
        raise P1V2PreparationError("manifest split/case schema mismatch")
    public_ids: list[str] = []
    for split in ("training", "heldout", "retention"):
        rows = public_splits.get(split)
        if not isinstance(rows, list):
            raise P1V2PreparationError("public split must be a list")
        for row in rows:
            if not isinstance(row, Mapping) or not isinstance(row.get("case_id"), str):
                raise P1V2PreparationError("public case schema mismatch")
            public_ids.append(row["case_id"])
            sealed_row = sealed_cases.get(row["case_id"])
            if not isinstance(sealed_row, Mapping) or sealed_row.get("split") != split:
                raise P1V2PreparationError("public and sealed splits disagree")
    if len(public_ids) != len(set(public_ids)) or set(public_ids) != set(sealed_cases):
        raise P1V2PreparationError("public and sealed case cuts disagree")
    forbidden = {"answer", "answers", "gold_answers", "solution_trace", "solution_traces"}
    if forbidden & {key.casefold() for key in _recursive_keys(public)}:
        raise P1V2PreparationError("public manifest crossed the sealed-gold boundary")


def load_and_build(
    universe_path: Path,
    *,
    selection_seed: int = DEFAULT_SELECTION_SEED,
) -> tuple[dict[str, object], dict[str, object]]:
    question_path = universe_path / "questions" / "type6.json"
    article_path = universe_path / "articles.json"
    if not question_path.is_file() or not article_path.is_file():
        raise P1V2PreparationError("universe must contain articles.json and questions/type6.json")
    try:
        questions = json.loads(question_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise P1V2PreparationError("type6 question file is invalid JSON") from error
    if not isinstance(questions, list):
        raise P1V2PreparationError("type6 question file must contain a list")
    return build_l0_manifests(
        questions,
        universe=universe_path.name,
        dataset_file_sha256={
            "articles.json": _file_sha256(article_path),
            "questions/type6.json": _file_sha256(question_path),
        },
        selection_seed=selection_seed,
    )


def _atomic_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_path = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    temp_path = Path(raw_path)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(json.dumps(
                value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
            ).encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


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
    parser.add_argument("--public-output", type=Path, required=True)
    parser.add_argument("--sealed-output", type=Path, required=True)
    parser.add_argument("--selection-seed", type=int, default=DEFAULT_SELECTION_SEED)
    args = parser.parse_args()
    public, sealed = load_and_build(
        args.universe_path, selection_seed=args.selection_seed
    )
    _atomic_write(args.sealed_output, sealed)
    _atomic_write(args.public_output, public)
    written_sealed = json.loads(args.sealed_output.read_text(encoding="utf-8"))
    written_public = json.loads(args.public_output.read_text(encoding="utf-8"))
    verify_l0_manifests(written_public, written_sealed)
    print(json.dumps({
        "public_output": str(args.public_output),
        "sealed_output": str(args.sealed_output),
        "public_manifest_sha256": public["public_manifest_sha256"],
        "sealed_gold_sha256": sealed["sealed_gold_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "P1V2PreparationError",
    "build_l0_manifests",
    "load_and_build",
    "select_type6_question_ids",
    "verify_l0_manifests",
]
