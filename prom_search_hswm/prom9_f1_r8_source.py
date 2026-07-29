#!/usr/bin/env python3
"""Prepare answer-blind HSWM F1 r8 source, manifest, and evaluator artifacts.

The Dataset Viewer response is supplied as an explicit offline file.  Public
cohort and candidate identities are derived only from row IDs, questions, and
context paragraphs.  Answers are copied only into private sealed artifacts;
they are never used for selection, feature construction, or terminal output.
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
SOURCE_RECEIPT_SCHEMA = "hswm-prom9-f1-r8-source-receipt/v2"
SOURCE_BUNDLE_SCHEMA = "hswm-prom9-f1-r8-source-bundle/v2"
EVALUATOR_SEAL_SCHEMA = "hswm-prom9-f1-r8-evaluator-seal/v1"
GOLD_SCHEMA = "hswm-prom9-f1-gold/v1"
SOURCE_ENTITY_SCHEMA = "hswm-2wiki-paragraph-source/v1"
COMPONENT_SCHEMA = "hswm-source-entity-connected-component/v1"
COMPONENT_POLICY = "raw_2wiki_paragraph_connected_components/v2"
GENERATION_POLICY = {
    "temperature": 0,
    "enable_thinking": False,
    "structured_output_backend": "json_schema",
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ROW_KEYS = {
    "id", "question", "answer", "context", "supporting_facts",
    "evidences", "type",
}


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
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    except FileExistsError as error:
        raise R8SourceRefusal(f"refusing to replace output: {destination}") from error
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


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


def _validated_selected_entries(
    raw_entries: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    positions: set[int] = set()
    item_ids: set[str] = set()
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, Mapping) or set(raw_entry) != {
            "dataset_row_index", "row"
        }:
            raise R8SourceRefusal("selected raw-row entry schema drifted")
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
            raise R8SourceRefusal("selected raw-row identity is invalid or duplicate")
        item_id = row.get("id")
        if not isinstance(item_id, str) or not item_id or item_id in item_ids:
            raise R8SourceRefusal("selected item identity is invalid or duplicate")
        positions.add(position)
        item_ids.add(item_id)
        # Canonical round-trip detaches the frozen selected preimage from any
        # mutable caller-owned page object without inspecting gold fields.
        entries.append(
            json.loads(
                canonical_json(
                    {"dataset_row_index": position, "row": dict(row)}
                )
            )
        )
    return entries


def derive_public_rows(
    entries: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    """Return manifest items, source projections, and private gold rows."""

    manifest_items: list[dict[str, object]] = []
    projections: list[dict[str, object]] = []
    gold_rows: list[dict[str, object]] = []
    for entry in entries:
        position = entry.get("dataset_row_index")
        row = entry.get("row")
        if isinstance(position, bool) or not isinstance(position, int) or position < 0:
            raise R8SourceRefusal("dataset row index must be non-negative")
        if not isinstance(row, dict) or set(row) != _ROW_KEYS:
            raise R8SourceRefusal("raw row schema drifted")
        item_id = str(row["id"])
        question = row["question"]
        answer = row["answer"]
        if not isinstance(question, str) or not question:
            raise R8SourceRefusal("question must be non-empty text")
        if not isinstance(answer, str):
            raise R8SourceRefusal("answer must be text")
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
                "max_input_tokens": 4145,
                "max_output_tokens_per_call": 768,
            }
        )
        projections.append(
            {
                "dataset_row_index": position,
                "item_id": item_id,
                "query_text": question,
                "raw_row_sha256": canonical_sha256(row),
                "candidates": source_candidates,
            }
        )
        gold_rows.append({"item_id": item_id, "accepted_answers": [answer]})
    _assign_components(manifest_items)
    return manifest_items, projections, gold_rows


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


def build_artifacts(
    viewer_response: Mapping[str, object],
    *,
    dataset: str,
    config: str,
    split: str,
    offset: int,
    length: int,
    run_id: str,
    mode: str,
    model: str,
    model_revision: str,
    token_envelope: Mapping[str, object],
    sealed_at: str,
    preregistration_artifact_sha256: str | None,
    selected_entries: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, dict[str, object]]:
    if offset < 0 or length < 1:
        raise R8SourceRefusal("offset and length must be positive Dataset Viewer bounds")
    if mode not in {"development", "sealed"}:
        raise R8SourceRefusal("mode must be development or sealed")
    if mode == "sealed" and not (
        isinstance(preregistration_artifact_sha256, str)
        and _SHA256.fullmatch(preregistration_artifact_sha256)
    ):
        raise R8SourceRefusal("sealed manifest requires a preregistration artifact SHA-256")
    if mode == "development" and preregistration_artifact_sha256 is not None:
        raise R8SourceRefusal("development manifest cannot claim preregistration")
    if not run_id or not model or not model_revision or not sealed_at:
        raise R8SourceRefusal("run/model/revision/sealed_at must be non-empty")
    entries = (
        _validated_entries(viewer_response, offset=offset, length=length)
        if selected_entries is None
        else _validated_selected_entries(selected_entries)
    )
    if len(entries) != length:
        raise R8SourceRefusal("selected entry count differs from frozen length")
    items, projections, gold_rows = derive_public_rows(entries)
    raw_rows_bytes = canonical_json(entries).encode("utf-8")
    raw_source_sha = hashlib.sha256(raw_rows_bytes).hexdigest()
    source_bundle_sha = canonical_sha256(
        {
            "schema_version": SOURCE_BUNDLE_SCHEMA,
            "dataset": dataset,
            "config": config,
            "split": split,
            "rows": projections,
        }
    )
    source_unsigned = {
        "schema_version": SOURCE_RECEIPT_SCHEMA,
        "dataset": dataset,
        "config": config,
        "split": split,
        "raw_rows_json_b64": base64.b64encode(raw_rows_bytes).decode("ascii"),
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
                "raw_row_sha256": projection["raw_row_sha256"],
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
    cohort_root = canonical_sha256(sorted(str(item["item_id"]) for item in items))
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
    gold_payload = {
        "schema_version": GOLD_SCHEMA,
        "run_id": run_id,
        "items": gold_rows,
    }
    evaluator_unsigned = {
        "schema_version": EVALUATOR_SEAL_SCHEMA,
        "run_id": run_id,
        "cohort_root_sha256": cohort_root,
        "raw_source_sha256": raw_source_sha,
        "source_receipt_sha256": source_receipt["source_receipt_sha256"],
        "gold_payload_sha256": canonical_sha256(gold_payload),
        "answers_inspected_by_operator": False,
        "sealed_at": sealed_at,
    }
    evaluator = {
        **evaluator_unsigned,
        "receipt_sha256": canonical_sha256(evaluator_unsigned),
    }
    gold = {
        "schema_version": GOLD_SCHEMA,
        "run_id": run_id,
        "evaluator_receipt_sha256": evaluator["receipt_sha256"],
        "items": gold_rows,
    }
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
        "gold": gold,
        "source_receipt": source_receipt,
        "evaluator_receipt": evaluator,
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
            "cohort_root_sha256": cohort_root,
            "candidate_universe_root_sha256": candidate_root,
            "raw_source_sha256": raw_source_sha,
            "source_bundle_sha256": source_bundle_sha,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--viewer-response-file", type=Path, required=True)
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--split", default=DEFAULT_SPLIT)
    parser.add_argument("--offset", type=int, required=True)
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
        viewer_response = read_json(args.viewer_response_file, "Dataset Viewer page")
        token_envelope = read_json(args.token_envelope, "token envelope")
        artifacts = build_artifacts(
            viewer_response,
            dataset=args.dataset,
            config=args.config,
            split=args.split,
            offset=args.offset,
            length=args.length,
            run_id=args.run_id,
            mode=args.mode,
            model=args.model,
            model_revision=args.model_revision,
            token_envelope=token_envelope,
            sealed_at=args.sealed_at,
            preregistration_artifact_sha256=args.preregistration_artifact_sha256,
        )
        write_json_once(args.manifest, artifacts["manifest"])
        write_json_once(args.gold, artifacts["gold"])
        write_json_once(args.source_receipt, artifacts["source_receipt"])
        write_json_once(args.evaluator_receipt, artifacts["evaluator_receipt"])
        print(
            json.dumps(
                {
                    "status": "PREPARED_NO_ANSWERS_DISCLOSED",
                    **artifacts["summary"],
                    "manifest_sha256": canonical_sha256(artifacts["manifest"]),
                    "gold_sha256": canonical_sha256(artifacts["gold"]),
                    "source_receipt_sha256": artifacts["source_receipt"][
                        "source_receipt_sha256"
                    ],
                    "evaluator_receipt_sha256": artifacts["evaluator_receipt"][
                        "receipt_sha256"
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
    "candidate_universe_sha256",
    "derive_public_rows",
    "read_json",
    "source_entity_id",
    "write_json_once",
]
