#!/usr/bin/env python3
"""Prepare physically separated public and evaluator-only F1 r8 artifacts.

The public builder accepts only answer-redacted selected rows.  A separate
evaluator-only row preimage supplies gold after its exact alignment with the
public selection has been verified.  No public artifact or terminal output is
derived from answer-bearing bytes.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from collections.abc import Mapping, Sequence

from prom_search_hswm.hswm_function_network import F1_ARMS
from prom_search_hswm.hswm_typed_ports import canonical_json, canonical_sha256
from prom_search_hswm.prom9_prepare_2wiki_f1 import (
    DATASET_SERVER,
    DEFAULT_CONFIG,
    DEFAULT_DATASET,
    DEFAULT_SPLIT,
    _paragraph,
    _structural_features,
    _tfidf_scores,
)


MANIFEST_SCHEMA = "hswm-prom9-f1-manifest/v3"
SOURCE_RECEIPT_SCHEMA = "hswm-prom9-f1-r8-source-receipt/v3"
SOURCE_BUNDLE_SCHEMA = "hswm-prom9-f1-r8-source-bundle/v3"
EVALUATOR_SEAL_SCHEMA = "hswm-prom9-f1-r8-evaluator-seal/v2"
GOLD_SCHEMA = "hswm-prom9-f1-gold/v2"
SOURCE_ENTITY_SCHEMA = "hswm-2wiki-paragraph-source/v1"
COMPONENT_SCHEMA = "hswm-source-entity-connected-component/v1"
COMPONENT_POLICY = "raw_2wiki_paragraph_connected_components/v2"
GENERATION_POLICY = {
    "temperature": 0,
    "enable_thinking": False,
    "structured_output_backend": "json_schema",
}
R8_TIGHT_COMMON_INPUT_BUDGET = 4325
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ROW_KEYS = {
    "id", "question", "answer", "context", "supporting_facts",
    "evidences", "type",
}
_PUBLIC_ROW_KEYS = {"id", "question", "context", "type"}


class R8SourceRefusal(RuntimeError):
    """The source or requested output is not safe to freeze."""


def _pairs(values: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in values:
        if key in result:
            raise R8SourceRefusal(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(
                R8SourceRefusal(f"non-finite JSON number in {label}: {value}")
            ),
        )
    except R8SourceRefusal:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise R8SourceRefusal(f"cannot read {label}: {error}") from error
    if not isinstance(value, dict):
        raise R8SourceRefusal(f"{label} must be an object")
    return value


def write_json_once(path: Path, value: Mapping[str, object], *, mode: int = 0o600) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    temporary = destination.with_name(f".{destination.name}.partial-{os.getpid()}")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError as error:
            raise R8SourceRefusal(f"refusing to replace output: {destination}") from error
        directory = os.open(str(destination.parent), os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _execution_budgets(token_envelope: Mapping[str, object]) -> tuple[int, int]:
    input_caps = token_envelope.get("per_call_input_caps")
    output_caps = token_envelope.get("per_call_output_caps")
    expected = {"1", "2", "3"}
    if (
        not isinstance(input_caps, Mapping)
        or not isinstance(output_caps, Mapping)
        or set(input_caps) != expected
        or set(output_caps) != expected
    ):
        raise R8SourceRefusal("token envelope must declare exact call 1/2/3 caps")
    values: list[int] = []
    for label, caps in (("input", input_caps), ("output", output_caps)):
        for call_index in sorted(expected):
            value = caps[call_index]
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise R8SourceRefusal(
                    f"token envelope {label} cap {call_index} must be a positive integer"
                )
            values.append(value)
    return sum(int(input_caps[key]) for key in sorted(expected)), max(
        int(output_caps[key]) for key in sorted(expected)
    )


def source_entity_id(title: str, sentences: Sequence[str]) -> str:
    if not title or not isinstance(title, str):
        raise R8SourceRefusal("source title must be non-empty text")
    normalized = list(sentences)
    if any(not isinstance(sentence, str) for sentence in normalized):
        raise R8SourceRefusal("source sentences must be text")
    return canonical_sha256(
        {
            "schema_version": SOURCE_ENTITY_SCHEMA,
            "title": title,
            "sentences": normalized,
        }
    )


def candidate_universe_sha256(candidates: Sequence[Mapping[str, object]]) -> str:
    identities: list[dict[str, str]] = []
    for candidate in candidates:
        identity = {
            "bond_id": str(candidate["bond_id"]),
            "evidence_id": str(candidate["evidence_id"]),
            "content_sha256": canonical_sha256({"content": candidate["content"]}),
            "source_entity_id": str(candidate["source_entity_id"]),
        }
        identities.append(identity)
    return canonical_sha256(identities)


def _validated_entries(
    viewer_response: Mapping[str, object], *, offset: int, length: int
) -> list[dict[str, object]]:
    raw_rows = viewer_response.get("rows")
    if not isinstance(raw_rows, list) or len(raw_rows) != length:
        raise R8SourceRefusal("Dataset Viewer page length drifted")
    entries: list[dict[str, object]] = []
    item_ids: set[str] = set()
    for position, wrapped in enumerate(raw_rows):
        if not isinstance(wrapped, dict) or not isinstance(wrapped.get("row"), dict):
            raise R8SourceRefusal(f"Dataset Viewer row {position} is malformed")
        row = dict(wrapped["row"])
        if set(row) != _ROW_KEYS:
            raise R8SourceRefusal(f"Dataset Viewer row {position} schema drifted")
        item_id = row.get("id")
        if not isinstance(item_id, str) or not item_id or item_id in item_ids:
            raise R8SourceRefusal("Dataset Viewer item identity is empty or duplicate")
        item_ids.add(item_id)
        entries.append({"dataset_row_index": offset + position, "row": row})
    return entries


def _validated_full_selected_entries(
    raw_entries: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    positions: set[int] = set()
    item_ids: set[str] = set()
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, Mapping) or set(raw_entry) != {
            "dataset_row_index", "row"
        }:
            raise R8SourceRefusal("evaluator selected-row entry schema drifted")
        position = raw_entry.get("dataset_row_index")
        row = raw_entry.get("row")
        if (
            isinstance(position, bool)
            or not isinstance(position, int)
            or position < 0
            or position in positions
            or not isinstance(row, Mapping)
            or set(row) != _ROW_KEYS
        ):
            raise R8SourceRefusal(
                "evaluator selected-row identity is invalid or duplicate"
            )
        item_id = row.get("id")
        if not isinstance(item_id, str) or not item_id or item_id in item_ids:
            raise R8SourceRefusal("evaluator item identity is invalid or duplicate")
        positions.add(position)
        item_ids.add(item_id)
        entries.append(
            json.loads(
                canonical_json(
                    {"dataset_row_index": position, "row": dict(row)}
                )
            )
        )
    return entries


def _validated_public_entries(
    raw_entries: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    positions: set[int] = set()
    item_ids: set[str] = set()
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, Mapping) or set(raw_entry) != {
            "dataset_row_index", "row"
        }:
            raise R8SourceRefusal("public selected-row entry schema drifted")
        position = raw_entry.get("dataset_row_index")
        row = raw_entry.get("row")
        if (
            isinstance(position, bool)
            or not isinstance(position, int)
            or position < 0
            or position in positions
            or not isinstance(row, Mapping)
            or set(row) != _PUBLIC_ROW_KEYS
        ):
            raise R8SourceRefusal("public selected-row identity is invalid or duplicate")
        item_id = row.get("id")
        question = row.get("question")
        question_type = row.get("type")
        context = row.get("context")
        if (
            not isinstance(item_id, str)
            or not item_id
            or item_id in item_ids
            or not isinstance(question, str)
            or not question
            or not isinstance(question_type, str)
            or not isinstance(context, Mapping)
            or set(context) != {"title", "sentences"}
        ):
            raise R8SourceRefusal("public selected-row allowlist drifted")
        titles = context.get("title")
        groups = context.get("sentences")
        if (
            not isinstance(titles, list)
            or not isinstance(groups, list)
            or not titles
            or len(titles) != len(groups)
            or any(not isinstance(title, str) or not title for title in titles)
            or any(
                not isinstance(group, list)
                or any(not isinstance(sentence, str) for sentence in group)
                for group in groups
            )
        ):
            raise R8SourceRefusal("public selected-row context drifted")
        positions.add(position)
        item_ids.add(item_id)
        entries.append(
            json.loads(
                canonical_json(
                    {"dataset_row_index": position, "row": dict(row)}
                )
            )
        )
    return entries


def redact_entries(
    full_entries: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Return the only row shape admissible in public r8 artifacts."""

    validated = _validated_full_selected_entries(full_entries)
    return [
        {
            "dataset_row_index": entry["dataset_row_index"],
            "row": {
                key: entry["row"][key]
                for key in ("id", "question", "context", "type")
            },
        }
        for entry in validated
    ]


def verify_exact_entry_alignment(
    public_entries: Sequence[Mapping[str, object]],
    full_entries: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Validate closed-world public/full alignment without exposing gold."""

    public = _validated_public_entries(public_entries)
    full = _validated_full_selected_entries(full_entries)
    if redact_entries(full) != public:
        raise R8SourceRefusal("public and evaluator selected rows are not exactly aligned")
    return public, full


def derive_public_rows(
    entries: Sequence[Mapping[str, object]],
    *,
    max_input_tokens: int = R8_TIGHT_COMMON_INPUT_BUDGET,
    max_output_tokens_per_call: int = 1536,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Return manifest items and source projections from redacted rows only."""

    manifest_items: list[dict[str, object]] = []
    projections: list[dict[str, object]] = []
    for entry in _validated_public_entries(entries):
        position = entry.get("dataset_row_index")
        row = entry.get("row")
        if isinstance(position, bool) or not isinstance(position, int) or position < 0:
            raise R8SourceRefusal("dataset row index must be non-negative")
        if not isinstance(row, dict) or set(row) != _PUBLIC_ROW_KEYS:
            raise R8SourceRefusal("public row schema drifted")
        item_id = str(row["id"])
        question = row["question"]
        if not isinstance(question, str) or not question:
            raise R8SourceRefusal("question must be non-empty text")
        context = row["context"]
        if not isinstance(context, dict) or set(context) != {"title", "sentences"}:
            raise R8SourceRefusal("2Wiki context schema drifted")
        titles = context["title"]
        groups = context["sentences"]
        if (
            not isinstance(titles, list)
            or not isinstance(groups, list)
            or not titles
            or len(titles) != len(groups)
            or any(not isinstance(title, str) or not title for title in titles)
        ):
            raise R8SourceRefusal("2Wiki context arrays drifted")
        paragraphs = [
            _paragraph(str(title), sentences)
            for title, sentences in zip(titles, groups)
        ]
        scores = _tfidf_scores(question, paragraphs)
        structure = _structural_features([str(title) for title in titles], paragraphs)
        candidate_count = len(paragraphs)
        candidates: list[dict[str, object]] = []
        source_candidates: list[dict[str, object]] = []
        for index, (title, raw_sentences, paragraph) in enumerate(
            zip(titles, groups, paragraphs)
        ):
            if not isinstance(raw_sentences, list) or any(
                not isinstance(sentence, str) for sentence in raw_sentences
            ):
                raise R8SourceRefusal("2Wiki paragraph sentences must be text")
            entity_id = source_entity_id(str(title), raw_sentences)
            flat_score = (
                1.0
                if candidate_count == 1
                else 1.0 - index / (candidate_count - 1)
            )
            identity = {
                "bond_id": f"{item_id}:bond:{index}",
                "evidence_id": f"{item_id}:evidence:{index}",
                "source_entity_id": entity_id,
                "content": paragraph,
            }
            source_candidates.append(identity)
            candidates.append(
                {
                    **identity,
                    "observable": {
                        "base_score": round(scores[index], 8),
                        "flat_position": index,
                        "flat_score": round(flat_score, 8),
                        **structure[index],
                        "source_type": "wikipedia_context",
                        "vector_score": round(scores[index], 8),
                    },
                }
            )
        manifest_items.append(
            {
                "item_id": item_id,
                "query_text": question,
                "allowed_evidence_types": ["wikipedia_paragraph"],
                "candidates": candidates,
                "component_id": None,
                "max_evidence_items": min(3, candidate_count),
                "max_input_tokens": max_input_tokens,
                "max_output_tokens_per_call": max_output_tokens_per_call,
            }
        )
        projections.append(
            {
                "dataset_row_index": position,
                "item_id": item_id,
                "query_text": question,
                "public_row_sha256": canonical_sha256(row),
                "candidates": source_candidates,
            }
        )
    _assign_components(manifest_items)
    return manifest_items, projections


def _derive_gold_rows(
    public_entries: Sequence[Mapping[str, object]],
    full_entries: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    public, full = verify_exact_entry_alignment(public_entries, full_entries)
    result: list[dict[str, object]] = []
    for public_entry, full_entry in zip(public, full):
        public_row = public_entry["row"]
        full_row = full_entry["row"]
        assert isinstance(public_row, Mapping) and isinstance(full_row, Mapping)
        answer = full_row.get("answer")
        if not isinstance(answer, str):
            raise R8SourceRefusal("evaluator answer must be text")
        result.append(
            {"item_id": str(public_row["id"]), "accepted_answers": [answer]}
        )
    return result


def _assign_components(items: list[dict[str, object]]) -> dict[str, list[str]]:
    parent = {str(item["item_id"]): str(item["item_id"]) for item in items}

    def find(item_id: str) -> str:
        while parent[item_id] != item_id:
            parent[item_id] = parent[parent[item_id]]
            item_id = parent[item_id]
        return item_id

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    owner: dict[str, str] = {}
    entities_by_item: dict[str, set[str]] = {}
    for item in items:
        item_id = str(item["item_id"])
        candidates = item.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise R8SourceRefusal("manifest item has no candidates")
        entities = {str(candidate["source_entity_id"]) for candidate in candidates}
        entities_by_item[item_id] = entities
        for entity in entities:
            if not _SHA256.fullmatch(entity):
                raise R8SourceRefusal("source entity identity drifted")
            prior = owner.setdefault(entity, item_id)
            union(item_id, prior)
    entities_by_root: dict[str, set[str]] = {}
    for item_id, entities in entities_by_item.items():
        entities_by_root.setdefault(find(item_id), set()).update(entities)
    component_by_root = {
        root: canonical_sha256(
            {
                "schema_version": COMPONENT_SCHEMA,
                "source_entity_ids": sorted(entities),
            }
        )
        for root, entities in entities_by_root.items()
    }
    result: dict[str, list[str]] = {}
    for item in items:
        item_id = str(item["item_id"])
        component_id = component_by_root[find(item_id)]
        item["component_id"] = component_id
        result.setdefault(component_id, []).append(item_id)
    return result


def _validate_build_identity(
    *,
    run_id: str,
    mode: str,
    model: str,
    model_revision: str,
    preregistration_artifact_sha256: str | None,
) -> None:
    if mode not in {"development", "sealed"}:
        raise R8SourceRefusal("mode must be development or sealed")
    if mode == "sealed" and not (
        isinstance(preregistration_artifact_sha256, str)
        and _SHA256.fullmatch(preregistration_artifact_sha256)
    ):
        raise R8SourceRefusal("sealed manifest requires a preregistration artifact SHA-256")
    if mode == "development" and preregistration_artifact_sha256 is not None:
        raise R8SourceRefusal("development manifest cannot claim preregistration")
    if not run_id or not model or not model_revision:
        raise R8SourceRefusal("run/model/revision must be non-empty")


def build_public_artifacts(
    public_entries: Sequence[Mapping[str, object]],
    *,
    public_selection_receipt_sha256: str,
    dataset: str,
    config: str,
    split: str,
    run_id: str,
    mode: str,
    model: str,
    model_revision: str,
    token_envelope: Mapping[str, object],
    preregistration_artifact_sha256: str | None,
) -> dict[str, dict[str, object]]:
    _validate_build_identity(
        run_id=run_id,
        mode=mode,
        model=model,
        model_revision=model_revision,
        preregistration_artifact_sha256=preregistration_artifact_sha256,
    )
    if (
        not isinstance(public_selection_receipt_sha256, str)
        or _SHA256.fullmatch(public_selection_receipt_sha256) is None
    ):
        raise R8SourceRefusal("public selection receipt hash is required")
    entries = _validated_public_entries(public_entries)
    if not entries:
        raise R8SourceRefusal("public selection must contain at least one row")
    max_input_tokens, max_output_tokens_per_call = _execution_budgets(token_envelope)
    items, projections = derive_public_rows(
        entries,
        max_input_tokens=max_input_tokens,
        max_output_tokens_per_call=max_output_tokens_per_call,
    )
    raw_source_sha = hashlib.sha256(canonical_json(entries).encode("utf-8")).hexdigest()
    source_bundle_sha = canonical_sha256(
        {
            "schema_version": SOURCE_BUNDLE_SCHEMA,
            "dataset": dataset,
            "config": config,
            "split": split,
            "public_selection_receipt_sha256": public_selection_receipt_sha256,
            "redacted_rows": entries,
            "rows": projections,
        }
    )
    source_unsigned = {
        "schema_version": SOURCE_RECEIPT_SCHEMA,
        "dataset": dataset,
        "config": config,
        "split": split,
        "public_selection_receipt_sha256": public_selection_receipt_sha256,
        "redacted_rows": entries,
        "raw_source_sha256": raw_source_sha,
        "source_bundle_sha256": source_bundle_sha,
        "component_policy": COMPONENT_POLICY,
        "rows": [
            {
                "dataset_row_index": projection["dataset_row_index"],
                "item_id": projection["item_id"],
                "question_sha256": canonical_sha256(
                    {"question": projection["query_text"]}
                ),
                "public_row_sha256": projection["public_row_sha256"],
                "candidate_universe_sha256": candidate_universe_sha256(
                    next(
                        item["candidates"]
                        for item in items
                        if item["item_id"] == projection["item_id"]
                    )
                ),
                "source_entity_ids": sorted(
                    {
                        str(candidate["source_entity_id"])
                        for candidate in projection["candidates"]
                    }
                ),
            }
            for projection in projections
        ],
    }
    source_receipt = {
        **source_unsigned,
        "source_receipt_sha256": canonical_sha256(source_unsigned),
    }
    candidate_root = canonical_sha256(
        [
            {
                "item_id": str(item["item_id"]),
                "candidate_universe_sha256": candidate_universe_sha256(
                    item["candidates"]
                ),
            }
            for item in sorted(items, key=lambda value: str(value["item_id"]))
        ]
    )
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "run_id": run_id,
        "mode": mode,
        "model": model,
        "model_revision": model_revision,
        "token_tolerance": 512,
        "state_capacity_bytes": 4096,
        "state_bytes_by_arm": {arm: 4096 for arm in F1_ARMS},
        "preregistration_artifact_sha256": preregistration_artifact_sha256,
        "generation_policy": dict(GENERATION_POLICY),
        "token_envelope": dict(token_envelope),
        "items": items,
    }
    return {
        "manifest": manifest,
        "source_receipt": source_receipt,
        "summary": {
            "items": len(items),
            "components": len({str(item["component_id"]) for item in items}),
            "source_entities": len(
                {
                    str(candidate["source_entity_id"])
                    for item in items
                    for candidate in item["candidates"]
                }
            ),
            "cohort_root_sha256": canonical_sha256(
                sorted(str(item["item_id"]) for item in items)
            ),
            "candidate_universe_root_sha256": candidate_root,
            "raw_source_sha256": raw_source_sha,
            "source_bundle_sha256": source_bundle_sha,
        },
    }


def verify_public_source_receipt(value: Mapping[str, object]) -> str:
    expected = {
        "schema_version", "dataset", "config", "split",
        "public_selection_receipt_sha256", "redacted_rows",
        "raw_source_sha256", "source_bundle_sha256", "component_policy", "rows",
        "source_receipt_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != expected:
        raise R8SourceRefusal("public source receipt shape drifted")
    unsigned = dict(value)
    declared = unsigned.pop("source_receipt_sha256", None)
    if (
        value.get("schema_version") != SOURCE_RECEIPT_SCHEMA
        or value.get("component_policy") != COMPONENT_POLICY
        or not isinstance(value.get("public_selection_receipt_sha256"), str)
        or _SHA256.fullmatch(str(value.get("public_selection_receipt_sha256"))) is None
        or not isinstance(declared, str)
        or _SHA256.fullmatch(declared) is None
        or canonical_sha256(unsigned) != declared
    ):
        raise R8SourceRefusal("public source receipt identity or self-hash drifted")
    redacted = value.get("redacted_rows")
    if not isinstance(redacted, list):
        raise R8SourceRefusal("public source redacted rows are absent")
    entries = _validated_public_entries(redacted)
    if hashlib.sha256(canonical_json(entries).encode("utf-8")).hexdigest() != value.get(
        "raw_source_sha256"
    ):
        raise R8SourceRefusal("public source row hash drifted")
    items, projections = derive_public_rows(entries)
    source_rows = [
        {
            "dataset_row_index": projection["dataset_row_index"],
            "item_id": projection["item_id"],
            "question_sha256": canonical_sha256(
                {"question": projection["query_text"]}
            ),
            "public_row_sha256": projection["public_row_sha256"],
            "candidate_universe_sha256": candidate_universe_sha256(
                next(
                    item["candidates"]
                    for item in items
                    if item["item_id"] == projection["item_id"]
                )
            ),
            "source_entity_ids": sorted(
                {
                    str(candidate["source_entity_id"])
                    for candidate in projection["candidates"]
                }
            ),
        }
        for projection in projections
    ]
    if source_rows != value.get("rows"):
        raise R8SourceRefusal("public source projections drifted")
    expected_bundle = canonical_sha256(
        {
            "schema_version": SOURCE_BUNDLE_SCHEMA,
            "dataset": value.get("dataset"),
            "config": value.get("config"),
            "split": value.get("split"),
            "public_selection_receipt_sha256": value.get(
                "public_selection_receipt_sha256"
            ),
            "redacted_rows": entries,
            "rows": projections,
        }
    )
    if expected_bundle != value.get("source_bundle_sha256"):
        raise R8SourceRefusal("public source bundle hash drifted")
    return declared


def verify_evaluator_seal(value: Mapping[str, object]) -> str:
    expected = {
        "schema_version", "run_id", "public_selection_receipt_sha256",
        "public_source_receipt_sha256", "gold_source_receipt_sha256",
        "gold_sha256", "cohort_root_sha256", "raw_source_sha256",
        "answers_inspected_by_operator", "sealed_at", "receipt_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != expected:
        raise R8SourceRefusal("evaluator seal shape drifted")
    unsigned = dict(value)
    declared = unsigned.pop("receipt_sha256", None)
    hashes = (
        "public_selection_receipt_sha256", "public_source_receipt_sha256",
        "gold_source_receipt_sha256", "gold_sha256", "cohort_root_sha256",
        "raw_source_sha256",
    )
    if (
        value.get("schema_version") != EVALUATOR_SEAL_SCHEMA
        or not isinstance(value.get("run_id"), str)
        or not value.get("run_id")
        or not isinstance(value.get("sealed_at"), str)
        or not value.get("sealed_at")
        or value.get("answers_inspected_by_operator") is not False
        or any(
            not isinstance(value.get(field), str)
            or _SHA256.fullmatch(str(value.get(field))) is None
            for field in hashes
        )
        or not isinstance(declared, str)
        or canonical_sha256(unsigned) != declared
    ):
        raise R8SourceRefusal("evaluator seal identity or self-hash drifted")
    return declared


def build_artifacts(
    public_entries: Sequence[Mapping[str, object]],
    evaluator_entries: Sequence[Mapping[str, object]],
    *,
    public_selection_receipt_sha256: str,
    gold_source_receipt_sha256: str,
    dataset: str,
    config: str,
    split: str,
    run_id: str,
    mode: str,
    model: str,
    model_revision: str,
    token_envelope: Mapping[str, object],
    sealed_at: str,
    preregistration_artifact_sha256: str | None,
) -> dict[str, dict[str, object]]:
    """Build public artifacts and evaluator-only gold from separated inputs."""

    if (
        not isinstance(public_selection_receipt_sha256, str)
        or _SHA256.fullmatch(public_selection_receipt_sha256) is None
        or not isinstance(gold_source_receipt_sha256, str)
        or _SHA256.fullmatch(gold_source_receipt_sha256) is None
        or not sealed_at
    ):
        raise R8SourceRefusal("selection/gold-source hashes and sealed_at are required")
    public, full = verify_exact_entry_alignment(public_entries, evaluator_entries)
    built = build_public_artifacts(
        public,
        public_selection_receipt_sha256=public_selection_receipt_sha256,
        dataset=dataset,
        config=config,
        split=split,
        run_id=run_id,
        mode=mode,
        model=model,
        model_revision=model_revision,
        token_envelope=token_envelope,
        preregistration_artifact_sha256=preregistration_artifact_sha256,
    )
    gold = {
        "schema_version": GOLD_SCHEMA,
        "run_id": run_id,
        "items": _derive_gold_rows(public, full),
    }
    source = built["source_receipt"]
    manifest = built["manifest"]
    summary = built["summary"]
    gold_sha = canonical_sha256(gold)
    evaluator_unsigned = {
        "schema_version": EVALUATOR_SEAL_SCHEMA,
        "run_id": run_id,
        "public_selection_receipt_sha256": public_selection_receipt_sha256,
        "public_source_receipt_sha256": source["source_receipt_sha256"],
        "gold_source_receipt_sha256": gold_source_receipt_sha256,
        "gold_sha256": gold_sha,
        "cohort_root_sha256": summary["cohort_root_sha256"],
        "raw_source_sha256": source["raw_source_sha256"],
        "answers_inspected_by_operator": False,
        "sealed_at": sealed_at,
    }
    evaluator = {
        **evaluator_unsigned,
        "receipt_sha256": canonical_sha256(evaluator_unsigned),
    }
    verify_evaluator_seal(evaluator)
    return {
        "manifest": manifest,
        "gold": gold,
        "source_receipt": source,
        "evaluator_receipt": evaluator,
        "summary": summary,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection-receipt", type=Path, required=True)
    parser.add_argument("--gold-source-receipt", type=Path, required=True)
    parser.add_argument(
        "--selection-cohort", choices=("development", "confirmatory"), required=True
    )
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--split", default=DEFAULT_SPLIT)
    parser.add_argument("--length", type=int, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--mode", choices=("development", "sealed"), required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--token-envelope", type=Path, required=True)
    parser.add_argument("--sealed-at", required=True)
    parser.add_argument("--preregistration-artifact-sha256")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--source-receipt", type=Path, required=True)
    parser.add_argument("--evaluator-receipt", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        from prom_search_hswm.prom9_f1_prior_exposure import (
            _read_private_bytes,
            _strict_object,
        )
        from prom_search_hswm.prom9_f1_r8_power import (
            evaluator_selected_entries,
            selected_entries,
            verify_selection_receipt,
        )

        selection = read_json(args.selection_receipt, "public cohort selection receipt")
        selection_sha = verify_selection_receipt(selection)
        gold_source = _strict_object(
            _read_private_bytes(args.gold_source_receipt),
            "evaluator-only gold-source receipt",
        )
        public_rows = selected_entries(selection, args.selection_cohort)
        evaluator_rows = evaluator_selected_entries(
            selection, gold_source, args.selection_cohort
        )
        gold_source_sha = str(gold_source["gold_source_receipt_sha256"])
        if len(public_rows) != args.length or len(evaluator_rows) != args.length:
            raise R8SourceRefusal("selected cohort count differs from --length")
        token_envelope = read_json(args.token_envelope, "token envelope")
        artifacts = build_artifacts(
            public_rows,
            evaluator_rows,
            public_selection_receipt_sha256=selection_sha,
            gold_source_receipt_sha256=gold_source_sha,
            dataset=args.dataset,
            config=args.config,
            split=args.split,
            run_id=args.run_id,
            mode=args.mode,
            model=args.model,
            model_revision=args.model_revision,
            token_envelope=token_envelope,
            sealed_at=args.sealed_at,
            preregistration_artifact_sha256=args.preregistration_artifact_sha256,
        )
        destinations = {
            Path(args.manifest).resolve(), Path(args.gold).resolve(),
            Path(args.source_receipt).resolve(), Path(args.evaluator_receipt).resolve(),
        }
        if len(destinations) != 4:
            raise R8SourceRefusal("artifact output paths must be distinct")
        write_json_once(args.gold, artifacts["gold"])
        write_json_once(args.evaluator_receipt, artifacts["evaluator_receipt"])
        write_json_once(args.source_receipt, artifacts["source_receipt"])
        write_json_once(args.manifest, artifacts["manifest"])
        print(
            json.dumps(
                {
                    "status": "PREPARED_NO_ANSWERS_DISCLOSED",
                    **artifacts["summary"],
                    "manifest_sha256": canonical_sha256(artifacts["manifest"]),
                    "source_receipt_sha256": artifacts["source_receipt"][
                        "source_receipt_sha256"
                    ],
                },
                sort_keys=True,
            )
        )
        return 0
    except Exception as error:
        print(
            json.dumps({"status": "REFUSED", "reason": str(error)}, sort_keys=True),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "COMPONENT_POLICY",
    "COMPONENT_SCHEMA",
    "EVALUATOR_SEAL_SCHEMA",
    "GENERATION_POLICY",
    "GOLD_SCHEMA",
    "MANIFEST_SCHEMA",
    "R8SourceRefusal",
    "SOURCE_BUNDLE_SCHEMA",
    "SOURCE_ENTITY_SCHEMA",
    "SOURCE_RECEIPT_SCHEMA",
    "build_artifacts",
    "build_public_artifacts",
    "candidate_universe_sha256",
    "derive_public_rows",
    "read_json",
    "redact_entries",
    "source_entity_id",
    "verify_evaluator_seal",
    "verify_exact_entry_alignment",
    "verify_public_source_receipt",
    "write_json_once",
]
