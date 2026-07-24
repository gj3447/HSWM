#!/usr/bin/env python3
"""Prepare a small gold-separated 2Wiki F1 development cohort.

Rows are fetched read-only through the Hugging Face Dataset Viewer.  Retrieval
features are computed from question/context bytes only; supporting_facts,
evidences, and answer are never used in candidate scoring.  Gold is written to
a separate file for the independent F1 judge.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re
import ssl
from typing import Mapping, Sequence
from urllib.parse import urlencode
from urllib.request import urlopen

from prom_search_hswm.hswm_function_network import F1_ARMS
from prom_search_hswm.hswm_typed_ports import canonical_sha256
from prom_search_hswm.prom_f1_function_network import GOLD_SCHEMA, MANIFEST_SCHEMA


SOURCE_SCHEMA = "hswm-prom9-f1-2wiki-source-receipt/v1"
DEFAULT_DATASET = "framolfese/2WikiMultihopQA"
DEFAULT_CONFIG = "default"
DEFAULT_SPLIT = "validation"
DATASET_SERVER = "https://datasets-server.huggingface.co"
_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
_STOP = frozenset(
    "a an and are as at be both by did do does for from has have in is it of on or "
    "that the their to was were what when where which who whose with".split()
)


class Prepare2WikiError(RuntimeError):
    pass


def _tokens(value: str) -> list[str]:
    return [token for token in _TOKEN.findall(value.casefold()) if token not in _STOP]


def _tfidf_scores(query: str, documents: Sequence[str]) -> list[float]:
    if not documents:
        raise Prepare2WikiError("documents must be non-empty")
    tokenized = [_tokens(document) for document in documents]
    query_tokens = _tokens(query)
    document_frequency = Counter(
        token for document in tokenized for token in set(document)
    )
    count = len(documents)

    def vector(tokens: Sequence[str]) -> dict[str, float]:
        frequencies = Counter(tokens)
        return {
            token: frequency * (math.log((count + 1) / (document_frequency[token] + 1)) + 1.0)
            for token, frequency in frequencies.items()
        }

    query_vector = vector(query_tokens)
    query_norm = math.sqrt(sum(value * value for value in query_vector.values()))
    scores = []
    for tokens in tokenized:
        document_vector = vector(tokens)
        document_norm = math.sqrt(sum(value * value for value in document_vector.values()))
        numerator = sum(query_vector.get(token, 0.0) * value for token, value in document_vector.items())
        denominator = query_norm * document_norm
        scores.append(0.0 if denominator == 0.0 else numerator / denominator)
    return scores


def _structural_features(titles: Sequence[str], documents: Sequence[str]) -> list[dict[str, int]]:
    lowered_documents = [document.casefold() for document in documents]
    features = []
    for index, title in enumerate(titles):
        title_key = title.casefold()
        outbound = sum(
            int(other.casefold() in lowered_documents[index])
            for other_index, other in enumerate(titles)
            if other_index != index and len(other) >= 4
        )
        inbound = sum(
            int(title_key in document)
            for other_index, document in enumerate(lowered_documents)
            if other_index != index and len(title) >= 4
        )
        features.append(
            {
                "incidence_count": 1 + outbound + inbound,
                "seam_count": outbound + inbound,
            }
        )
    return features


def _paragraph(title: str, sentences: object) -> str:
    if not isinstance(sentences, list) or any(not isinstance(item, str) for item in sentences):
        raise Prepare2WikiError("context sentences must be an array of text")
    return f"{title}. " + " ".join(sentences)


def make_artifacts(
    viewer_response: Mapping[str, object],
    *,
    dataset: str,
    config: str,
    split: str,
    offset: int,
    length: int,
    run_id: str,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    raw_rows = viewer_response.get("rows")
    if not isinstance(raw_rows, list) or len(raw_rows) != length:
        raise Prepare2WikiError("Dataset Viewer returned an incomplete row page")
    items = []
    gold_items = []
    source_rows = []
    for position, wrapped in enumerate(raw_rows):
        if not isinstance(wrapped, dict) or not isinstance(wrapped.get("row"), dict):
            raise Prepare2WikiError(f"row {position} is malformed")
        row = wrapped["row"]
        required = {"id", "question", "answer", "context", "supporting_facts", "evidences", "type"}
        if set(row) != required:
            raise Prepare2WikiError(f"row {position} schema drifted")
        context = row["context"]
        if not isinstance(context, dict) or set(context) != {"title", "sentences"}:
            raise Prepare2WikiError(f"row {position} context schema drifted")
        titles = context["title"]
        sentence_groups = context["sentences"]
        if (
            not isinstance(titles, list)
            or not isinstance(sentence_groups, list)
            or not titles
            or len(titles) != len(sentence_groups)
            or any(not isinstance(title, str) or not title for title in titles)
        ):
            raise Prepare2WikiError(f"row {position} context arrays are invalid")
        paragraphs = [
            _paragraph(title, sentences)
            for title, sentences in zip(titles, sentence_groups)
        ]
        scores = _tfidf_scores(str(row["question"]), paragraphs)
        structure = _structural_features(titles, paragraphs)
        candidate_count = len(paragraphs)
        candidates = []
        for index, (title, paragraph) in enumerate(zip(titles, paragraphs)):
            flat_score = 1.0 if candidate_count == 1 else 1.0 - index / (candidate_count - 1)
            candidates.append(
                {
                    "bond_id": f"{row['id']}:bond:{index}",
                    "evidence_id": f"{row['id']}:evidence:{index}",
                    "content": paragraph,
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
        item_id = str(row["id"])
        items.append(
            {
                "item_id": item_id,
                "query_text": str(row["question"]),
                "allowed_evidence_types": ["wikipedia_paragraph"],
                "candidates": candidates,
                "max_evidence_items": min(3, candidate_count),
                "max_input_tokens": 16000,
                "max_output_tokens_per_call": 512,
            }
        )
        gold_items.append({"item_id": item_id, "accepted_answers": [str(row["answer"])]})
        source_rows.append(
            {
                "dataset_row_index": offset + position,
                "item_id": item_id,
                "question_sha256": canonical_sha256({"question": row["question"]}),
                "context_sha256": canonical_sha256({"context": context}),
                "gold_sha256": canonical_sha256({"answer": row["answer"]}),
                "question_type": row["type"],
            }
        )
    source_unsigned = {
        "schema_version": SOURCE_SCHEMA,
        "dataset": dataset,
        "config": config,
        "split": split,
        "offset": offset,
        "length": length,
        "dataset_server": DATASET_SERVER,
        "viewer_response_sha256": canonical_sha256(viewer_response),
        "rows": source_rows,
        "feature_policy": "question/context-only TF-IDF cosine plus title-incidence seam counts; answer, evidences, and supporting_facts excluded",
    }
    source = {**source_unsigned, "source_receipt_sha256": canonical_sha256(source_unsigned)}
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "run_id": run_id,
        "mode": "development",
        "model": "qwen3.6-27b",
        "model_revision": "Qwen/Qwen3.6-27B@server-process-attested-20260724",
        "token_tolerance": 512,
        "state_capacity_bytes": 4096,
        "state_bytes_by_arm": {arm: 4096 for arm in F1_ARMS},
        "preregistration_receipt_sha256": None,
        "items": items,
    }
    gold = {
        "schema_version": GOLD_SCHEMA,
        "run_id": run_id,
        "evaluator_receipt_sha256": source["source_receipt_sha256"],
        "items": gold_items,
    }
    return manifest, gold, source


def _write_once(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as error:
        raise Prepare2WikiError(f"refusing to replace output: {path}") from error
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--split", default=DEFAULT_SPLIT)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--length", type=int, default=8)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--source-receipt", type=Path, required=True)
    parser.add_argument("--ca-file", type=Path, default=Path("/etc/ssl/cert.pem"))
    args = parser.parse_args(argv)
    try:
        if args.offset < 0 or not 1 <= args.length <= 100:
            raise Prepare2WikiError("offset/length are outside Dataset Viewer bounds")
        query = urlencode(
            {
                "dataset": args.dataset,
                "config": args.config,
                "split": args.split,
                "offset": args.offset,
                "length": args.length,
            }
        )
        context = ssl.create_default_context(cafile=str(args.ca_file))
        with urlopen(f"{DATASET_SERVER}/rows?{query}", context=context, timeout=60) as response:
            raw = response.read()
        viewer_response = json.loads(raw)
        if not isinstance(viewer_response, dict):
            raise Prepare2WikiError("Dataset Viewer response must be an object")
        manifest, gold, source = make_artifacts(
            viewer_response,
            dataset=args.dataset,
            config=args.config,
            split=args.split,
            offset=args.offset,
            length=args.length,
            run_id=args.run_id,
        )
        _write_once(args.manifest, manifest)
        _write_once(args.gold, gold)
        _write_once(args.source_receipt, source)
        print(
            json.dumps(
                {
                    "status": "PREPARED_DEVELOPMENT_ONLY",
                    "items": args.length,
                    "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
                    "gold_sha256": hashlib.sha256(args.gold.read_bytes()).hexdigest(),
                    "source_receipt_sha256": source["source_receipt_sha256"],
                },
                sort_keys=True,
            )
        )
        return 0
    except Exception as error:
        print(json.dumps({"status": "REFUSED", "reason": str(error)}), file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["Prepare2WikiError", "make_artifacts"]
