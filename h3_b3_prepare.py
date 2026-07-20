"""Prepare query-blind B3 extraction and stable-ID embedding preimages.

This is artifact plumbing, not a compiler.  It joins the frozen development
sample and fresh holdout manifests into deduplicated JSONL inputs while keeping
all evaluator fields out of the extraction surface.  Every output record has a
stable content-derived ID, so later NPZ artifacts are joined by identity rather
than array position.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import argparse
import json
from pathlib import Path
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import h3_fresh_manifest as fresh
import world_builder as wb
from world_ir import canonical_json, content_id


SCHEMA_VERSION = "hswm-h3-b3-preimages/v1"


@dataclass(frozen=True)
class EvaluationRowV1:
    dataset: str
    split: str
    qid: str
    question: str
    paragraph_source_ids: tuple[str, ...]
    gold_source_ids: tuple[str, ...]
    hop: int


@dataclass(frozen=True)
class PreparedSegmentV1:
    dataset: str
    split: str
    paragraphs: tuple[fresh.CompilerParagraphV1, ...]
    evaluation_rows: tuple[EvaluationRowV1, ...]


def paragraph_source_id(dataset: str, title: str, text: str) -> str:
    return content_id("h3_compiler_paragraph", {
        "dataset": dataset, "title": title, "text": text,
    })


def _normalized_paragraphs(
    dataset: str, row: Mapping[str, Any],
) -> tuple[fresh.CompilerParagraphV1, ...]:
    out: list[fresh.CompilerParagraphV1] = []
    seen: set[str] = set()
    for index, raw in enumerate(row.get("paragraphs", ())):
        if not isinstance(raw, Mapping):
            raise ValueError(f"paragraphs[{index}] must be a mapping")
        title = raw.get("title")
        text = raw.get("paragraph_text", raw.get("text"))
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"paragraphs[{index}].title must be non-empty")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"paragraphs[{index}].text must be non-empty")
        source_id = paragraph_source_id(dataset, title, text)
        if source_id in seen:
            continue
        seen.add(source_id)
        out.append(fresh.CompilerParagraphV1(source_id, title, text))
    if not out:
        raise ValueError("row has no paragraphs")
    return tuple(out)


def prepare_development_segment(
    dataset: str,
    normalized_pool: Sequence[Mapping[str, Any]],
    *,
    n_rows: int = 200,
) -> PreparedSegmentV1:
    """Reproduce B1's 200-row sample without exposing QA to the extractor."""

    qids = fresh.derive_prior_b1_qids(normalized_pool, n_rows=n_rows)
    by_qid = {str(row.get("id", row.get("_id", ""))): row for row in normalized_pool}
    if len(by_qid) != len(normalized_pool):
        raise ValueError("development pool qids must be unique and non-empty")
    paragraphs: dict[str, fresh.CompilerParagraphV1] = {}
    evaluation: list[EvaluationRowV1] = []
    for qid in qids:
        row = by_qid[qid]
        row_paragraphs = _normalized_paragraphs(dataset, row)
        for paragraph in row_paragraphs:
            existing = paragraphs.get(paragraph.source_id)
            if existing is not None and existing != paragraph:
                raise ValueError("stable paragraph ID collision")
            paragraphs[paragraph.source_id] = paragraph
        gold_ids = []
        paragraph_ids = []
        seen_paragraph_ids: set[str] = set()
        raw_paragraphs = tuple(row["paragraphs"])
        for raw in raw_paragraphs:
            title = str(raw["title"])
            text = str(raw.get("paragraph_text", raw.get("text", "")))
            source_id = paragraph_source_id(dataset, title, text)
            if source_id not in paragraphs:
                raise ValueError("row paragraph was lost during canonicalization")
            if source_id not in seen_paragraph_ids:
                seen_paragraph_ids.add(source_id)
                paragraph_ids.append(source_id)
            if bool(raw.get("is_supporting")):
                gold_ids.append(source_id)
        question = row.get("question")
        if not isinstance(question, str) or not question.strip() or not gold_ids:
            raise ValueError(f"development row {qid} lacks question or gold evidence")
        evaluation.append(EvaluationRowV1(
            dataset=dataset, split="development", qid=qid, question=question,
            paragraph_source_ids=tuple(paragraph_ids),
            gold_source_ids=tuple(sorted(set(gold_ids))), hop=wb.parse_hop(dict(row)),
        ))
    return PreparedSegmentV1(
        dataset=dataset, split="development",
        paragraphs=tuple(sorted(paragraphs.values(), key=lambda item: item.source_id)),
        evaluation_rows=tuple(evaluation),
    )


def prepare_fresh_segment(
    manifest: Mapping[str, Any],
    raw_rows: Sequence[Mapping[str, Any]],
) -> PreparedSegmentV1:
    """Bind a fresh compiler manifest to evaluator-only query/gold records."""

    dataset = str(manifest.get("dataset", ""))
    selected_qids = tuple(str(value) for value in manifest.get("selected_qids", ()))
    compiler_paragraphs = tuple(
        fresh.CompilerParagraphV1(**value)
        for value in manifest.get("compiler_paragraphs", ())
    )
    paragraph_by_id = {item.source_id: item for item in compiler_paragraphs}
    by_qid = {
        str(row.get("id", row.get("_id", ""))): row for row in raw_rows
    }
    evaluation: list[EvaluationRowV1] = []
    for qid in selected_qids:
        row = by_qid.get(qid)
        if row is None:
            raise ValueError(f"fresh raw row missing qid {qid}")
        if dataset == "musique":
            raw_paragraphs = tuple(row["paragraphs"])
            pairs = [
                (str(item["title"]), str(item.get("paragraph_text", item.get("text", ""))),
                 bool(item.get("is_supporting")))
                for item in raw_paragraphs
            ]
        elif dataset == "2wiki":
            context = row["context"]
            if isinstance(context, Mapping):
                titles, sentence_rows = context["title"], context["sentences"]
            else:
                titles, sentence_rows = zip(*context, strict=True)
            support = row["supporting_facts"]
            support_titles = set(
                support["title"] if isinstance(support, Mapping)
                else (item[0] for item in support)
            )
            pairs = [
                (str(title), " ".join(str(sentence) for sentence in sentences),
                 str(title) in support_titles)
                for title, sentences in zip(titles, sentence_rows, strict=True)
            ]
        else:
            raise ValueError(f"unsupported dataset {dataset!r}")
        paragraph_ids_list: list[str] = []
        seen_paragraph_ids: set[str] = set()
        gold_id_set: set[str] = set()
        for title, text, supporting in pairs:
            source_id = paragraph_source_id(dataset, title, text)
            if source_id not in seen_paragraph_ids:
                seen_paragraph_ids.add(source_id)
                paragraph_ids_list.append(source_id)
            if supporting:
                gold_id_set.add(source_id)
        paragraph_ids = tuple(paragraph_ids_list)
        if any(source_id not in paragraph_by_id for source_id in paragraph_ids):
            raise ValueError(f"manifest/raw paragraph identity mismatch for {qid}")
        gold_ids = tuple(sorted(gold_id_set))
        question = row.get("question")
        if not isinstance(question, str) or not question.strip() or not gold_ids:
            raise ValueError(f"fresh row {qid} lacks question or gold evidence")
        evaluation.append(EvaluationRowV1(
            dataset=dataset, split="fresh", qid=qid, question=question,
            paragraph_source_ids=paragraph_ids, gold_source_ids=gold_ids,
            hop=(
                len(row.get("question_decomposition", ()))
                if dataset == "musique"
                else (4 if str(row.get("type", "")).casefold().replace("_", " ")
                      == "bridge comparison" else 2)
            ),
        ))
    return PreparedSegmentV1(
        dataset=dataset, split="fresh", paragraphs=compiler_paragraphs,
        evaluation_rows=tuple(evaluation),
    )


def extraction_records(
    segments: Iterable[PreparedSegmentV1],
) -> tuple[dict[str, str], ...]:
    paragraphs: dict[str, fresh.CompilerParagraphV1] = {}
    for segment in segments:
        for paragraph in segment.paragraphs:
            old = paragraphs.get(paragraph.source_id)
            if old is not None and old != paragraph:
                raise ValueError("stable paragraph ID collision across segments")
            paragraphs[paragraph.source_id] = paragraph
    return tuple({
        "source_id": item.source_id, "title": item.title, "text": item.text,
    } for item in sorted(paragraphs.values(), key=lambda item: item.source_id))


def embedding_records(
    segments: Iterable[PreparedSegmentV1],
) -> tuple[dict[str, str], ...]:
    segments = tuple(segments)
    rows = list({
        "id": f"paragraph:{record['source_id']}", "kind": "paragraph",
        "text": f"{record['title']} :: {record['text']}",
    } for record in extraction_records(segments))
    seen_query_ids: set[str] = set()
    for segment in segments:
        for row in segment.evaluation_rows:
            query_id = f"query:{row.dataset}:{row.qid}"
            if query_id in seen_query_ids:
                raise ValueError("duplicate query ID across segments")
            seen_query_ids.add(query_id)
            rows.append({"id": query_id, "kind": "query", "text": row.question})
    return tuple(sorted(rows, key=lambda item: item["id"]))


def write_jsonl(records: Sequence[Mapping[str, Any]], path: str | Path) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(canonical_json(record) + "\n" for record in records)
    target.write_text(body, encoding="utf-8")
    return sha256(body.encode("utf-8")).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--segment-json", action="append", required=True)
    parser.add_argument("--extraction-output", required=True)
    parser.add_argument("--embedding-output", required=True)
    args = parser.parse_args(argv)
    segments = []
    for path in args.segment_json:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        segments.append(PreparedSegmentV1(
            dataset=value["dataset"], split=value["split"],
            paragraphs=tuple(fresh.CompilerParagraphV1(**item)
                             for item in value["paragraphs"]),
            evaluation_rows=tuple(EvaluationRowV1(**item)
                                  for item in value["evaluation_rows"]),
        ))
    extraction = extraction_records(segments)
    embeddings = embedding_records(segments)
    result = {
        "schema_version": SCHEMA_VERSION,
        "extraction_records": len(extraction),
        "embedding_records": len(embeddings),
        "extraction_sha256": write_jsonl(extraction, args.extraction_output),
        "embedding_sha256": write_jsonl(embeddings, args.embedding_output),
    }
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
