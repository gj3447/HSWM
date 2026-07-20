"""Frozen, leakage-safe confirmatory holdout manifests for HSWM H3/B3.

This module performs no network access.  It consumes an already-frozen
MuSiQue JSON snapshot or 2Wiki row mappings/parquet file, removes every row
that overlaps the prior B1 experiment by query id, relation template, or exact
gold evidence identity, and chooses the confirmatory cohort with a declared
hash order.

The output has two deliberately separate surfaces:

* ``compiler_payload`` contains only opaque ids and paragraph title/text.
* ``evaluator_payload`` contains the normalized :mod:`relation_eval` labels.

Thus the n-ary compiler never needs to accept a raw QA row merely so the
evaluator can recover a relation chain.  The manifest binds both surfaces,
the raw snapshot, the prior B1 qids, the selection quotas, and a disjointness
audit with SHA-256.

Longinus ReferenceSite:
``HSWM/PROM_16_WORLD_COMPILER_CERTIFIED_READOUT_ENVELOPE_2026-07-20.md``
sections 14-18 (fresh confirmatory builder falsifier).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import argparse
import json
from pathlib import Path
from collections.abc import Mapping, Sequence
from typing import Any

import relation_eval as reval
from world_ir import canonical_json, content_id


SCHEMA_VERSION = "hswm-h3-fresh-manifest/v2"
SELECTION_SEED = "HSWM-H3-B3-CONFIRM-2026-07-20-v1"
DEFAULT_QUOTAS: dict[str, tuple[tuple[int, int], ...]] = {
    "musique": ((2, 160), (3, 80), (4, 60)),
    "2wiki": ((2, 150), (4, 100)),
}


class FreshManifestError(ValueError):
    """The source, prior-B1 boundary, or requested cohort is invalid."""


@dataclass(frozen=True)
class CompilerParagraphV1:
    """Complete paragraph input visible to B1/B3 compilers."""

    source_id: str
    title: str
    text: str


@dataclass(frozen=True)
class CompilerRowV1:
    """Opaque candidate-set envelope; it carries no query or gold label."""

    row_id: str
    paragraph_source_ids: tuple[str, ...]


@dataclass(frozen=True)
class EvaluatorBindingV1:
    """Raw-label-derived evaluation binding kept outside compiler input.

    ``paragraph_source_ids`` and ``gold_source_ids`` are independently
    reconstructed from the raw benchmark row.  ``binding_id`` commits those
    sets together with the opaque compiler ``row_id``, raw row digest, hop,
    and normalized occurrence; it is not copied from a compiled segment.
    """

    binding_id: str
    row_id: str
    raw_row_sha256: str
    paragraph_source_ids: tuple[str, ...]
    gold_source_ids: tuple[str, ...]
    benchmark_hop: int
    example: reval.RelationExampleV1


@dataclass(frozen=True)
class HoldoutCountsV1:
    raw_rows: int
    prior_rows: int
    eligible_rows: int
    selected_rows: int
    excluded_rows_total: int
    excluded_prior_qid: int
    excluded_prior_template: int
    excluded_prior_evidence: int
    eligible_by_hop: tuple[tuple[int, int], ...]
    selected_by_hop: tuple[tuple[int, int], ...]
    compiler_paragraphs: int


@dataclass(frozen=True)
class DisjointAuditV1:
    prior_relation_template_count: int
    prior_evidence_content_id_count: int
    selected_prior_qid_overlap_count: int
    selected_prior_template_overlap_count: int
    selected_prior_evidence_overlap_count: int
    selected_duplicate_qid_count: int
    qid_disjoint: bool
    relation_template_disjoint: bool
    exact_evidence_disjoint: bool
    all_disjoint: bool


@dataclass(frozen=True)
class FreshHoldoutManifestV1:
    schema_version: str
    dataset: str
    selection_seed: str
    quotas: tuple[tuple[int, int], ...]
    raw_source_sha256: str
    source_file_sha256: str | None
    prior_qid_sha256: str
    selected_manifest_sha256: str
    prior_qids: tuple[str, ...]
    selected_qids: tuple[str, ...]
    counts: HoldoutCountsV1
    audit: DisjointAuditV1
    compiler_rows: tuple[CompilerRowV1, ...]
    compiler_paragraphs: tuple[CompilerParagraphV1, ...]
    evaluator_sidecar: tuple[EvaluatorBindingV1, ...]


def _sha256_file(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _row_qid(row: Mapping[str, Any], *, path: str = "row") -> str:
    value = row.get("id", row.get("_id", ""))
    qid = str(value).strip()
    if not qid:
        raise FreshManifestError(f"{path}.id or {path}._id is required")
    return qid


def _record_list(value: Any, path: str) -> list[dict[str, Any]]:
    """Convert record lists or HF struct-of-lists without rewriting text."""

    if isinstance(value, Mapping):
        columns = {str(key): column for key, column in value.items()}
        if not columns:
            return []
        if any(
            not isinstance(column, Sequence) or isinstance(column, (str, bytes))
            for column in columns.values()
        ):
            raise FreshManifestError(f"{path} columns must be sequences")
        lengths = {len(column) for column in columns.values()}
        if len(lengths) != 1:
            raise FreshManifestError(f"{path} columns must have equal lengths")
        length = next(iter(lengths))
        return [
            {key: column[index] for key, column in columns.items()}
            for index in range(length)
        ]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        out: list[dict[str, Any]] = []
        for index, item in enumerate(value):
            if not isinstance(item, Mapping):
                raise FreshManifestError(f"{path}[{index}] must be a mapping")
            out.append(dict(item))
        return out
    raise FreshManifestError(f"{path} must be records or a struct-of-lists")


def _require_raw_text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FreshManifestError(f"{path} must be non-empty text")
    return value


def _paragraph_source_id(dataset: str, title: str, text: str) -> str:
    return content_id("h3_compiler_paragraph", {
        "dataset": dataset,
        "title": title,
        "text": text,
    })


def _compiler_paragraph_records(
    dataset: str, row: Mapping[str, Any], *, path: str,
) -> tuple[CompilerParagraphV1, ...]:
    records: list[tuple[str, str]] = []
    if dataset == "musique":
        for index, paragraph in enumerate(_record_list(row.get("paragraphs"),
                                                       f"{path}.paragraphs")):
            title = _require_raw_text(paragraph.get("title"),
                                      f"{path}.paragraphs[{index}].title")
            text_key = "paragraph_text" if "paragraph_text" in paragraph else "text"
            text = _require_raw_text(paragraph.get(text_key),
                                     f"{path}.paragraphs[{index}].{text_key}")
            records.append((title, text))
    elif dataset == "2wiki":
        context = row.get("context")
        if isinstance(context, Mapping):
            titles, sentences = context.get("title"), context.get("sentences")
            if (
                not isinstance(titles, Sequence) or isinstance(titles, (str, bytes))
                or not isinstance(sentences, Sequence) or isinstance(sentences, (str, bytes))
                or len(titles) != len(sentences)
            ):
                raise FreshManifestError(f"{path}.context title/sentences must align")
            candidates = list(zip(titles, sentences, strict=True))
        elif isinstance(context, Sequence) and not isinstance(context, (str, bytes)):
            candidates = list(context)
        else:
            raise FreshManifestError(f"{path}.context must be pairs or struct-of-lists")
        for index, candidate in enumerate(candidates):
            if (
                not isinstance(candidate, Sequence) or isinstance(candidate, (str, bytes))
                or len(candidate) != 2
            ):
                raise FreshManifestError(f"{path}.context[{index}] must be [title, sentences]")
            title = _require_raw_text(candidate[0], f"{path}.context[{index}].title")
            sentences = candidate[1]
            if (
                not isinstance(sentences, Sequence) or isinstance(sentences, (str, bytes))
                or not sentences
            ):
                raise FreshManifestError(f"{path}.context[{index}].sentences must be non-empty")
            checked = tuple(
                _require_raw_text(sentence, f"{path}.context[{index}].sentences[{ordinal}]")
                for ordinal, sentence in enumerate(sentences)
            )
            records.append((title, " ".join(checked)))
    else:
        raise FreshManifestError(f"unsupported dataset {dataset!r}")

    paragraphs: list[CompilerParagraphV1] = []
    seen: set[str] = set()
    for title, text in records:
        source_id = _paragraph_source_id(dataset, title, text)
        if source_id in seen:
            continue
        seen.add(source_id)
        paragraphs.append(CompilerParagraphV1(source_id, title, text))
    if not paragraphs:
        raise FreshManifestError(f"{path} has no compiler paragraphs")
    return tuple(paragraphs)


def _musique_gold_source_ids(
    row: Mapping[str, Any],
    paragraphs: tuple[CompilerParagraphV1, ...],
    *,
    path: str,
) -> tuple[str, ...]:
    """Derive paragraph gold solely from native MuSiQue support labels."""

    raw_paragraphs = _record_list(row.get("paragraphs"), f"{path}.paragraphs")
    by_idx: dict[int, str] = {}
    flag_gold: set[str] = set()
    support_flag_count = 0
    for ordinal, raw in enumerate(raw_paragraphs):
        title = _require_raw_text(
            raw.get("title"), f"{path}.paragraphs[{ordinal}].title",
        )
        text_key = "paragraph_text" if "paragraph_text" in raw else "text"
        text = _require_raw_text(
            raw.get(text_key), f"{path}.paragraphs[{ordinal}].{text_key}",
        )
        try:
            if isinstance(raw.get("idx", ordinal), bool):
                raise ValueError
            paragraph_idx = int(raw.get("idx", ordinal))
        except (TypeError, ValueError) as exc:
            raise FreshManifestError(
                f"{path}.paragraphs[{ordinal}].idx must be an integer"
            ) from exc
        if paragraph_idx in by_idx:
            raise FreshManifestError(f"{path}.paragraphs has duplicate idx {paragraph_idx}")
        source_id = _paragraph_source_id("musique", title, text)
        by_idx[paragraph_idx] = source_id
        if "is_supporting" in raw:
            support_flag_count += 1
            if not isinstance(raw["is_supporting"], bool):
                raise FreshManifestError(
                    f"{path}.paragraphs[{ordinal}].is_supporting must be boolean"
                )
            if raw["is_supporting"]:
                flag_gold.add(source_id)

    decomposition_gold: set[str] = set()
    steps = _record_list(
        row.get("question_decomposition"), f"{path}.question_decomposition",
    )
    for ordinal, step in enumerate(steps):
        step_path = f"{path}.question_decomposition[{ordinal}]"
        support = step.get("support_paragraph")
        if isinstance(support, Mapping):
            title = _require_raw_text(
                support.get("title"), f"{step_path}.support_paragraph.title",
            )
            text_key = "paragraph_text" if "paragraph_text" in support else "text"
            text = _require_raw_text(
                support.get(text_key), f"{step_path}.support_paragraph.{text_key}",
            )
            source_id = _paragraph_source_id("musique", title, text)
            if source_id not in by_idx.values():
                raise FreshManifestError(
                    f"{step_path}.support_paragraph is absent from raw candidates"
                )
        else:
            if "paragraph_support_idx" not in step:
                raise FreshManifestError(
                    f"{step_path} lacks a raw paragraph support label"
                )
            try:
                if isinstance(step["paragraph_support_idx"], bool):
                    raise ValueError
                support_idx = int(step["paragraph_support_idx"])
            except (TypeError, ValueError) as exc:
                raise FreshManifestError(
                    f"{step_path}.paragraph_support_idx must be an integer"
                ) from exc
            if support_idx not in by_idx:
                raise FreshManifestError(
                    f"{step_path}.paragraph_support_idx={support_idx} has no candidate"
                )
            source_id = by_idx[support_idx]
        decomposition_gold.add(source_id)

    if not decomposition_gold:
        raise FreshManifestError(f"{path} has no raw MuSiQue support labels")
    if support_flag_count:
        if support_flag_count != len(raw_paragraphs):
            raise FreshManifestError(
                f"{path}.paragraphs mixes present and missing is_supporting labels"
            )
        if flag_gold != decomposition_gold:
            raise FreshManifestError(
                f"{path} MuSiQue support labels disagree between paragraphs and decomposition"
            )
    candidate_ids = tuple(item.source_id for item in paragraphs)
    if not decomposition_gold.issubset(candidate_ids):
        raise FreshManifestError(f"{path} gold support is outside candidate paragraphs")
    return tuple(source_id for source_id in candidate_ids if source_id in decomposition_gold)


def _wiki_gold_source_ids(
    row: Mapping[str, Any],
    paragraphs: tuple[CompilerParagraphV1, ...],
    *,
    path: str,
) -> tuple[str, ...]:
    """Derive paragraph gold solely from 2Wiki supporting_facts + context."""

    context = row.get("context")
    if isinstance(context, Mapping):
        titles, sentences = context.get("title"), context.get("sentences")
        if (
            not isinstance(titles, Sequence) or isinstance(titles, (str, bytes))
            or not isinstance(sentences, Sequence) or isinstance(sentences, (str, bytes))
            or len(titles) != len(sentences)
        ):
            raise FreshManifestError(f"{path}.context title/sentences must align")
        candidates = list(zip(titles, sentences, strict=True))
    elif isinstance(context, Sequence) and not isinstance(context, (str, bytes)):
        candidates = list(context)
    else:
        raise FreshManifestError(f"{path}.context must be pairs or struct-of-lists")

    by_title: dict[str, tuple[str, int]] = {}
    for ordinal, candidate in enumerate(candidates):
        if (
            not isinstance(candidate, Sequence) or isinstance(candidate, (str, bytes))
            or len(candidate) != 2
        ):
            raise FreshManifestError(f"{path}.context[{ordinal}] must be [title, sentences]")
        title = _require_raw_text(candidate[0], f"{path}.context[{ordinal}].title")
        raw_sentences = candidate[1]
        if (
            not isinstance(raw_sentences, Sequence)
            or isinstance(raw_sentences, (str, bytes)) or not raw_sentences
        ):
            raise FreshManifestError(f"{path}.context[{ordinal}].sentences must be non-empty")
        checked = tuple(
            _require_raw_text(
                sentence, f"{path}.context[{ordinal}].sentences[{index}]",
            )
            for index, sentence in enumerate(raw_sentences)
        )
        source_id = _paragraph_source_id("2wiki", title, " ".join(checked))
        previous = by_title.get(title)
        if previous is not None and previous[0] != source_id:
            raise FreshManifestError(
                f"{path}.context title {title!r} is ambiguous across paragraphs"
            )
        by_title[title] = (source_id, len(checked))

    support_value = row.get("supporting_facts")
    if isinstance(support_value, Mapping):
        titles = support_value.get("title")
        indices = support_value.get(
            "sent_id", support_value.get("sentence_id", support_value.get("idx")),
        )
        if (
            not isinstance(titles, Sequence) or isinstance(titles, (str, bytes))
            or not isinstance(indices, Sequence) or isinstance(indices, (str, bytes))
            or len(titles) != len(indices)
        ):
            raise FreshManifestError(
                f"{path}.supporting_facts title/sentence-index columns must align"
            )
        supports = list(zip(titles, indices, strict=True))
    elif isinstance(support_value, Sequence) and not isinstance(
        support_value, (str, bytes)
    ):
        supports = list(support_value)
    else:
        raise FreshManifestError(f"{path}.supporting_facts must contain raw labels")

    gold: set[str] = set()
    for ordinal, support in enumerate(supports):
        if (
            not isinstance(support, Sequence) or isinstance(support, (str, bytes))
            or len(support) < 2
        ):
            raise FreshManifestError(
                f"{path}.supporting_facts[{ordinal}] must be [title, sentence_idx]"
            )
        title = _require_raw_text(
            support[0], f"{path}.supporting_facts[{ordinal}].title",
        )
        try:
            if isinstance(support[1], bool):
                raise ValueError
            sentence_idx = int(support[1])
        except (TypeError, ValueError) as exc:
            raise FreshManifestError(
                f"{path}.supporting_facts[{ordinal}].sentence_idx must be an integer"
            ) from exc
        if title not in by_title:
            raise FreshManifestError(
                f"{path}.supporting_facts title {title!r} is absent from context"
            )
        source_id, sentence_count = by_title[title]
        if not 0 <= sentence_idx < sentence_count:
            raise FreshManifestError(
                f"{path}.supporting_facts[{ordinal}] sentence index is out of range"
            )
        gold.add(source_id)
    if not gold:
        raise FreshManifestError(f"{path} has no raw 2Wiki support labels")
    candidate_ids = tuple(item.source_id for item in paragraphs)
    if not gold.issubset(candidate_ids):
        raise FreshManifestError(f"{path} gold support is outside candidate paragraphs")
    return tuple(source_id for source_id in candidate_ids if source_id in gold)


def _gold_source_ids(
    dataset: str,
    row: Mapping[str, Any],
    paragraphs: tuple[CompilerParagraphV1, ...],
    *,
    path: str,
) -> tuple[str, ...]:
    if dataset == "musique":
        return _musique_gold_source_ids(row, paragraphs, path=path)
    if dataset == "2wiki":
        return _wiki_gold_source_ids(row, paragraphs, path=path)
    raise FreshManifestError(f"unsupported dataset {dataset!r}")


def _normalizer(dataset: str):
    if dataset == "musique":
        return reval.normalize_musique_row
    if dataset == "2wiki":
        return reval.normalize_2wiki_row
    raise FreshManifestError(
        f"unsupported dataset {dataset!r}; expected one of {sorted(DEFAULT_QUOTAS)}"
    )


def _benchmark_hop(
    dataset: str, row: Mapping[str, Any], example: reval.RelationExampleV1,
) -> int:
    """Return the benchmark's declared logic-depth stratum.

    MuSiQue's decomposition length is the hop label.  In 2Wiki, however, the
    ordered ``evidences`` list may contain 3-7 triples while the benchmark's
    task taxonomy declares ordinary rows as 2-hop and bridge-comparison rows
    as 4-hop.  H3 quotas follow that benchmark/world-builder definition; exact
    template/evidence exclusions still use the full normalized relation steps.
    """

    if dataset == "musique":
        return example.hop
    type_hops = {
        "comparison": 2,
        "inference": 2,
        "compositional": 2,
        "bridge comparison": 4,
        "bridge_comparison": 4,
    }
    qtype = str(row.get("type", "")).strip().casefold()
    if qtype not in type_hops:
        raise FreshManifestError(f"2wiki row {example.qid!r} has unknown type {qtype!r}")
    return type_hops[qtype]


def _validate_quotas(
    dataset: str, quotas: Mapping[int, int] | Sequence[tuple[int, int]] | None,
) -> tuple[tuple[int, int], ...]:
    raw = DEFAULT_QUOTAS[dataset] if quotas is None else (
        tuple(quotas.items()) if isinstance(quotas, Mapping) else tuple(quotas)
    )
    normalized: dict[int, int] = {}
    for hop, count in raw:
        if isinstance(hop, bool) or not isinstance(hop, int) or hop <= 0:
            raise FreshManifestError("quota hop values must be positive integers")
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise FreshManifestError("quota counts must be positive integers")
        if hop in normalized:
            raise FreshManifestError(f"duplicate quota for hop {hop}")
        normalized[hop] = count
    if not normalized:
        raise FreshManifestError("at least one quota is required")
    return tuple(sorted(normalized.items()))


def _selection_key(dataset: str, qid: str, seed: str) -> tuple[str, str]:
    digest = sha256(f"{seed}|{dataset}|{qid}".encode("utf-8")).hexdigest()
    return digest, qid


def _compiler_row_id(dataset: str, qid: str, raw_row_sha256: str) -> str:
    return content_id("h3_compiler_row", {
        "dataset": dataset,
        "qid_sha256": sha256(qid.encode("utf-8")).hexdigest(),
        "raw_row_sha256": raw_row_sha256,
    })


def _evaluator_binding_id(
    *,
    dataset: str,
    row_id: str,
    raw_row_sha256: str,
    paragraph_source_ids: tuple[str, ...],
    gold_source_ids: tuple[str, ...],
    benchmark_hop: int,
    occurrence_id: str,
) -> str:
    return content_id("h3_evaluator_binding", {
        "dataset": dataset,
        "row_id": row_id,
        "raw_row_sha256": raw_row_sha256,
        "paragraph_source_ids": paragraph_source_ids,
        "gold_source_ids": gold_source_ids,
        "benchmark_hop": benchmark_hop,
        "occurrence_id": occurrence_id,
    })


def derive_row_label_provenance(
    dataset: str,
    row: Mapping[str, Any],
    *,
    path: str = "row",
) -> tuple[CompilerRowV1, tuple[CompilerParagraphV1, ...], EvaluatorBindingV1]:
    """Recompute one compiler/evaluator join directly from a raw benchmark row.

    This is the loader-facing contract: callers that still possess the frozen
    raw snapshot can regenerate the candidate set, support-derived gold set,
    benchmark hop, row id, and binding id without consulting a compiler
    segment or trusting serialized evaluator labels.
    """

    if not isinstance(row, Mapping):
        raise FreshManifestError(f"{path} must be a mapping")
    qid = _row_qid(row, path=path)
    try:
        example = _normalizer(dataset)(row)
    except reval.RelationEvaluationError as exc:
        raise FreshManifestError(f"{path}: {exc}") from exc
    if example.qid != qid:
        raise FreshManifestError(
            f"{path} qid changed during normalization: {qid!r} -> {example.qid!r}"
        )
    raw_row_sha256 = sha256(canonical_json(row).encode("utf-8")).hexdigest()
    if example.raw_row_sha256 != raw_row_sha256:
        raise FreshManifestError(f"{path} normalized example lost raw-row identity")
    paragraphs = _compiler_paragraph_records(dataset, row, path=path)
    paragraph_source_ids = tuple(item.source_id for item in paragraphs)
    gold_source_ids = _gold_source_ids(dataset, row, paragraphs, path=path)
    benchmark_hop = _benchmark_hop(dataset, row, example)
    row_id = _compiler_row_id(dataset, qid, raw_row_sha256)
    compiler_row = CompilerRowV1(
        row_id=row_id, paragraph_source_ids=paragraph_source_ids,
    )
    binding = EvaluatorBindingV1(
        binding_id=_evaluator_binding_id(
            dataset=dataset, row_id=row_id,
            raw_row_sha256=raw_row_sha256,
            paragraph_source_ids=paragraph_source_ids,
            gold_source_ids=gold_source_ids,
            benchmark_hop=benchmark_hop,
            occurrence_id=example.occurrence_id,
        ),
        row_id=row_id,
        raw_row_sha256=raw_row_sha256,
        paragraph_source_ids=paragraph_source_ids,
        gold_source_ids=gold_source_ids,
        benchmark_hop=benchmark_hop,
        example=example,
    )
    return compiler_row, paragraphs, binding


def compiler_payload(manifest: FreshHoldoutManifestV1) -> dict[str, Any]:
    """Return the only payload that may cross into B1/B3 compilation."""

    payload = {
        "schema_version": "hswm-h3-compiler-input/v1",
        "rows": tuple(asdict(row) for row in manifest.compiler_rows),
        "paragraphs": tuple(asdict(paragraph) for paragraph in manifest.compiler_paragraphs),
    }
    reval.assert_compiler_payload_clean(payload)
    return payload


def evaluator_payload(manifest: FreshHoldoutManifestV1) -> dict[str, Any]:
    """Return the QA/relation sidecar; never pass this object to a compiler."""

    return {
        "schema_version": "hswm-h3-evaluator-sidecar/v2",
        "dataset": manifest.dataset,
        "raw_source_sha256": manifest.raw_source_sha256,
        "selected_manifest_sha256": manifest.selected_manifest_sha256,
        "bindings": tuple(asdict(binding) for binding in manifest.evaluator_sidecar),
    }


def _manifest_hash_payload(
    *, dataset: str, selection_seed: str, quotas: tuple[tuple[int, int], ...],
    raw_source_sha256: str, source_file_sha256: str | None,
    prior_qid_sha256: str, prior_qids: tuple[str, ...],
    selected_qids: tuple[str, ...], counts: HoldoutCountsV1,
    audit: DisjointAuditV1, compiler_rows: tuple[CompilerRowV1, ...],
    compiler_paragraphs: tuple[CompilerParagraphV1, ...],
    evaluator_sidecar: tuple[EvaluatorBindingV1, ...],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset": dataset,
        "selection_seed": selection_seed,
        "quotas": quotas,
        "raw_source_sha256": raw_source_sha256,
        "source_file_sha256": source_file_sha256,
        "prior_qid_sha256": prior_qid_sha256,
        "prior_qids": prior_qids,
        "selected_qids": selected_qids,
        "counts": counts,
        "audit": audit,
        "compiler_rows": compiler_rows,
        "compiler_paragraphs": compiler_paragraphs,
        "evaluator_sidecar": evaluator_sidecar,
    }


def build_fresh_holdout_manifest(
    dataset: str,
    raw_rows: Sequence[Mapping[str, Any]],
    prior_b1_qids: Sequence[str],
    *,
    quotas: Mapping[int, int] | Sequence[tuple[int, int]] | None = None,
    selection_seed: str = SELECTION_SEED,
    source_file_sha256: str | None = None,
) -> FreshHoldoutManifestV1:
    """Select and bind a relation/evidence-disjoint confirmatory holdout.

    ``raw_rows`` must include every qid in ``prior_b1_qids`` so the exact B1
    relation templates and evidence identities can be recovered rather than
    guessed from qids alone.  Candidate row order affects the raw snapshot
    digest but never the hash-based selection order.
    """

    normalizer = _normalizer(dataset)
    quota_tuple = _validate_quotas(dataset, quotas)
    if not isinstance(selection_seed, str) or not selection_seed:
        raise FreshManifestError("selection_seed must be non-empty text")
    rows = tuple(raw_rows)
    if not rows:
        raise FreshManifestError("raw_rows must not be empty")
    if any(not isinstance(row, Mapping) for row in rows):
        raise FreshManifestError("raw_rows must contain mappings")

    by_qid: dict[str, Mapping[str, Any]] = {}
    examples: dict[str, reval.RelationExampleV1] = {}
    benchmark_hops: dict[str, int] = {}
    for index, row in enumerate(rows):
        qid = _row_qid(row, path=f"raw_rows[{index}]")
        if qid in by_qid:
            raise FreshManifestError(f"duplicate raw qid {qid!r}")
        try:
            example = normalizer(row)
        except reval.RelationEvaluationError as exc:
            raise FreshManifestError(f"raw_rows[{index}]: {exc}") from exc
        if example.qid != qid:
            raise FreshManifestError(
                f"raw_rows[{index}] qid changed during normalization: {qid!r} -> {example.qid!r}"
            )
        by_qid[qid] = row
        examples[qid] = example
        benchmark_hops[qid] = _benchmark_hop(dataset, row, example)

    prior_qids = tuple(sorted({str(qid).strip() for qid in prior_b1_qids if str(qid).strip()}))
    if not prior_qids:
        raise FreshManifestError("prior_b1_qids must not be empty")
    missing_prior = tuple(qid for qid in prior_qids if qid not in by_qid)
    if missing_prior:
        preview = ", ".join(repr(item) for item in missing_prior[:5])
        raise FreshManifestError(
            f"raw source is missing {len(missing_prior)} prior B1 qids: {preview}"
        )
    prior_qid_set = set(prior_qids)
    prior_examples = tuple(examples[qid] for qid in prior_qids)
    prior_templates = {example.relation_template_id for example in prior_examples}
    prior_evidence = {
        evidence_id
        for example in prior_examples
        for evidence_id in example.evidence_content_ids
    }

    eligible_by_hop: dict[int, list[reval.RelationExampleV1]] = {}
    excluded_qid = excluded_template = excluded_evidence = excluded_total = 0
    for qid, example in examples.items():
        qid_hit = qid in prior_qid_set
        template_hit = example.relation_template_id in prior_templates
        evidence_hit = not set(example.evidence_content_ids).isdisjoint(prior_evidence)
        excluded_qid += int(qid_hit)
        excluded_template += int(template_hit)
        excluded_evidence += int(evidence_hit)
        if qid_hit or template_hit or evidence_hit:
            excluded_total += 1
            continue
        eligible_by_hop.setdefault(benchmark_hops[qid], []).append(example)

    selected: list[reval.RelationExampleV1] = []
    available_counts = {hop: len(items) for hop, items in eligible_by_hop.items()}
    for hop, requested in quota_tuple:
        candidates = sorted(
            eligible_by_hop.get(hop, ()),
            key=lambda item: _selection_key(dataset, item.qid, selection_seed),
        )
        if len(candidates) < requested:
            raise FreshManifestError(
                f"{dataset} hop {hop}: quota {requested} unavailable after disjointness "
                f"filters; eligible={len(candidates)}"
            )
        selected.extend(candidates[:requested])

    selected_qids = tuple(example.qid for example in selected)
    selected_qid_set = set(selected_qids)
    selected_templates = {example.relation_template_id for example in selected}
    selected_evidence = {
        evidence_id for example in selected for evidence_id in example.evidence_content_ids
    }
    duplicate_qids = len(selected_qids) - len(selected_qid_set)
    qid_overlap = len(selected_qid_set & prior_qid_set)
    template_overlap = len(selected_templates & prior_templates)
    evidence_overlap = len(selected_evidence & prior_evidence)
    audit = DisjointAuditV1(
        prior_relation_template_count=len(prior_templates),
        prior_evidence_content_id_count=len(prior_evidence),
        selected_prior_qid_overlap_count=qid_overlap,
        selected_prior_template_overlap_count=template_overlap,
        selected_prior_evidence_overlap_count=evidence_overlap,
        selected_duplicate_qid_count=duplicate_qids,
        qid_disjoint=qid_overlap == 0,
        relation_template_disjoint=template_overlap == 0,
        exact_evidence_disjoint=evidence_overlap == 0,
        all_disjoint=(qid_overlap == template_overlap == evidence_overlap == duplicate_qids == 0),
    )
    if not audit.all_disjoint:
        raise FreshManifestError(f"internal disjointness failure: {audit}")

    compiler_rows: list[CompilerRowV1] = []
    evaluator_sidecar: list[EvaluatorBindingV1] = []
    paragraph_by_id: dict[str, CompilerParagraphV1] = {}
    for example in selected:
        row = by_qid[example.qid]
        compiler_row, paragraphs, evaluator_binding = derive_row_label_provenance(
            dataset, row, path=f"selected[{example.qid}]",
        )
        if evaluator_binding.example != example:
            raise FreshManifestError(
                f"selected[{example.qid}] label provenance changed after selection"
            )
        for paragraph in paragraphs:
            previous = paragraph_by_id.get(paragraph.source_id)
            if previous is not None and previous != paragraph:
                raise FreshManifestError(
                    f"paragraph content-id collision at {paragraph.source_id}"
                )
            paragraph_by_id[paragraph.source_id] = paragraph
        compiler_rows.append(compiler_row)
        evaluator_sidecar.append(evaluator_binding)

    compiler_row_tuple = tuple(compiler_rows)
    compiler_paragraph_tuple = tuple(
        paragraph_by_id[source_id] for source_id in sorted(paragraph_by_id)
    )
    evaluator_tuple = tuple(evaluator_sidecar)
    selected_counts = tuple(
        (hop, sum(benchmark_hops[example.qid] == hop for example in selected))
        for hop, _ in quota_tuple
    )
    counts = HoldoutCountsV1(
        raw_rows=len(rows),
        prior_rows=len(prior_qids),
        eligible_rows=sum(available_counts.values()),
        selected_rows=len(selected),
        excluded_rows_total=excluded_total,
        excluded_prior_qid=excluded_qid,
        excluded_prior_template=excluded_template,
        excluded_prior_evidence=excluded_evidence,
        eligible_by_hop=tuple(sorted(available_counts.items())),
        selected_by_hop=selected_counts,
        compiler_paragraphs=len(compiler_paragraph_tuple),
    )
    raw_source_sha256 = sha256(canonical_json(rows).encode("utf-8")).hexdigest()
    prior_qid_sha256 = sha256(canonical_json(prior_qids).encode("utf-8")).hexdigest()
    hash_payload = _manifest_hash_payload(
        dataset=dataset,
        selection_seed=selection_seed,
        quotas=quota_tuple,
        raw_source_sha256=raw_source_sha256,
        source_file_sha256=source_file_sha256,
        prior_qid_sha256=prior_qid_sha256,
        prior_qids=prior_qids,
        selected_qids=selected_qids,
        counts=counts,
        audit=audit,
        compiler_rows=compiler_row_tuple,
        compiler_paragraphs=compiler_paragraph_tuple,
        evaluator_sidecar=evaluator_tuple,
    )
    selected_manifest_sha256 = sha256(
        canonical_json(hash_payload).encode("utf-8")
    ).hexdigest()
    manifest = FreshHoldoutManifestV1(
        schema_version=SCHEMA_VERSION,
        dataset=dataset,
        selection_seed=selection_seed,
        quotas=quota_tuple,
        raw_source_sha256=raw_source_sha256,
        source_file_sha256=source_file_sha256,
        prior_qid_sha256=prior_qid_sha256,
        selected_manifest_sha256=selected_manifest_sha256,
        prior_qids=prior_qids,
        selected_qids=selected_qids,
        counts=counts,
        audit=audit,
        compiler_rows=compiler_row_tuple,
        compiler_paragraphs=compiler_paragraph_tuple,
        evaluator_sidecar=evaluator_tuple,
    )
    compiler_payload(manifest)  # final fail-closed QA-label boundary check
    return manifest


def derive_prior_b1_qids(
    normalized_pool_rows: Sequence[Mapping[str, Any]], *, n_rows: int = 200,
) -> tuple[str, ...]:
    """Reproduce B1's hop-round-robin sample from its normalized pool cache."""

    if isinstance(n_rows, bool) or not isinstance(n_rows, int) or n_rows <= 0:
        raise FreshManifestError("n_rows must be a positive integer")

    # Kept local so this manifest module does not import the experiment's
    # numpy/hypergraph builder merely to recover the frozen sampling rule.
    type_hops = {
        "comparison": 2,
        "inference": 2,
        "compositional": 2,
        "bridge comparison": 4,
        "bridge_comparison": 4,
    }

    def parse_hop(row: Mapping[str, Any]) -> int:
        import re

        for key in ("hop", "id"):
            match = re.search(r"(\d+)\s*hop", str(row.get(key, "")).casefold())
            if match:
                return int(match.group(1))
        label = str(row.get("hop", "")).strip().casefold()
        if label in type_hops:
            return type_hops[label]
        paragraphs = row.get("paragraphs")
        if not isinstance(paragraphs, Sequence) or isinstance(paragraphs, (str, bytes)):
            raise FreshManifestError("normalized pool row needs a recognized hop or paragraphs")
        return sum(
            bool(paragraph.get("is_supporting"))
            for paragraph in paragraphs
            if isinstance(paragraph, Mapping)
        )

    buckets: dict[int, list[str]] = {}
    seen: set[str] = set()
    for index, row in enumerate(normalized_pool_rows):
        if not isinstance(row, Mapping):
            raise FreshManifestError(f"normalized_pool_rows[{index}] must be a mapping")
        qid = _row_qid(row, path=f"normalized_pool_rows[{index}]")
        if qid in seen:
            raise FreshManifestError(f"duplicate normalized-pool qid {qid!r}")
        seen.add(qid)
        buckets.setdefault(parse_hop(row), []).append(qid)

    selected: list[str] = []
    cursor = 0
    while len(selected) < n_rows and any(cursor < len(items) for items in buckets.values()):
        for hop in sorted(buckets):
            if cursor < len(buckets[hop]) and len(selected) < n_rows:
                selected.append(buckets[hop][cursor])
        cursor += 1
    if len(selected) != n_rows:
        raise FreshManifestError(
            f"prior B1 sample requested {n_rows} rows but pool supplied {len(selected)}"
        )
    return tuple(selected)


def load_json_rows(path: str | Path) -> tuple[tuple[dict[str, Any], ...], str]:
    """Load a frozen JSON row list/wrapper and verify any declared row digest."""

    source_path = Path(path)
    with source_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, Mapping):
        rows = payload.get("rows")
        declared = payload.get("rows_sha256")
    else:
        rows, declared = payload, None
    if not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows):
        raise FreshManifestError(f"{source_path} must contain a row list or {{rows: [...]}}")
    row_tuple = tuple(dict(row) for row in rows)
    actual = sha256(canonical_json(row_tuple).encode("utf-8")).hexdigest()
    if declared is not None and declared != actual:
        raise FreshManifestError(
            f"declared rows_sha256 mismatch for {source_path}: {declared} != {actual}"
        )
    return row_tuple, _sha256_file(source_path)


def load_2wiki_parquet(path: str | Path) -> tuple[tuple[dict[str, Any], ...], str]:
    """Load local 2Wiki parquet with an optional, clearly-declared dependency."""

    try:
        import pyarrow.parquet as parquet  # type: ignore[import-not-found]
    except ImportError as exc:
        raise FreshManifestError(
            "2Wiki parquet loading requires optional dependency pyarrow; "
            "install it in the runner or pass already-decoded row mappings"
        ) from exc
    source_path = Path(path)
    try:
        rows = parquet.read_table(source_path).to_pylist()
    except Exception as exc:  # pyarrow exposes format/IO-specific exception types
        raise FreshManifestError(f"failed to read 2Wiki parquet {source_path}: {exc}") from exc
    if not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows):
        raise FreshManifestError(f"2Wiki parquet {source_path} did not decode to row mappings")
    return tuple(dict(row) for row in rows), _sha256_file(source_path)


def manifest_as_dict(manifest: FreshHoldoutManifestV1) -> dict[str, Any]:
    return asdict(manifest)


def write_manifest(manifest: FreshHoldoutManifestV1, path: str | Path) -> None:
    """Write canonical JSON; the bytes are reproducible across invocations."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(canonical_json(manifest) + "\n", encoding="utf-8")


def _load_prior_pool(path: str | Path) -> tuple[dict[str, Any], ...]:
    rows, _digest = load_json_rows(path)
    return rows


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=sorted(DEFAULT_QUOTAS), required=True)
    parser.add_argument("--raw", required=True, help="frozen raw JSON or 2Wiki parquet")
    parser.add_argument("--prior-pool", required=True,
                        help="normalized B1 pool JSON used by the 200-row sampler")
    parser.add_argument("--prior-n", type=int, default=200)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    if args.dataset == "2wiki" and str(args.raw).casefold().endswith(".parquet"):
        raw_rows, source_file_sha = load_2wiki_parquet(args.raw)
    else:
        raw_rows, source_file_sha = load_json_rows(args.raw)
    prior_pool = _load_prior_pool(args.prior_pool)
    prior_qids = derive_prior_b1_qids(prior_pool, n_rows=args.prior_n)
    manifest = build_fresh_holdout_manifest(
        args.dataset,
        raw_rows,
        prior_qids,
        source_file_sha256=source_file_sha,
    )
    write_manifest(manifest, args.output)
    print(json.dumps({
        "dataset": manifest.dataset,
        "selected_manifest_sha256": manifest.selected_manifest_sha256,
        "raw_source_sha256": manifest.raw_source_sha256,
        "prior_qid_sha256": manifest.prior_qid_sha256,
        "selected_rows": manifest.counts.selected_rows,
        "eligible_by_hop": dict(manifest.counts.eligible_by_hop),
        "selected_by_hop": dict(manifest.counts.selected_by_hop),
        "all_disjoint": manifest.audit.all_disjoint,
        "output": str(args.output),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
