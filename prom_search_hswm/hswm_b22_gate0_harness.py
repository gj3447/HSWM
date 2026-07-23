#!/usr/bin/env python3
"""B2.2 Gate 0: full-candidate component pack and exact neutral replay.

The existing B2.1 compiler computes every score component but persists only the
top 20 candidates.  This module preserves the complete query-by-edge matrices,
hash-binds their identity, and independently checks both the frozen B2 scorer
and the neutral ``rank_bonds`` boundary.  It is an engineering harness only: it
does not learn, promote, activate, mutate topology, or claim retrieval gain.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping, Sequence

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from hswm_bond_readout import (  # noqa: E402
    FORMULA_VERSION as BOND_FORMULA_VERSION,
    QueryBondWeight,
    normalize_query_logits,
    rank_bonds,
)
from hswm_open_composition import SemanticWeight  # noqa: E402
from prom_b2_crossfield_merge import (  # noqa: E402
    LAM_B,
    LAM_V,
    MODEL_NAME,
    SEED as B2_SEED,
    base_entities,
    finding_text,
)
from prom_b21_learned_router import (  # noqa: E402
    FROZEN_MODULES as B21_FROZEN_MODULES,
    PARTITION_SALTS,
    Paragraph,
    Query,
    directory_manifest,
    field_label,
    frozen_b2_reference,
    normalize_rows,
    opaque_entity,
    privatize_text,
    read_scorepack,
    sha256_file,
    stable_pid,
)


SCHEMA = "hswm-b22-full-candidate-pack/v1"
RECEIPT_SCHEMA = "hswm-b22-gate0-receipt/v1"
LOCK_SCHEMA = "hswm-b22-gate0-acceptance-lock/v1"
ACCEPTANCE_SCHEMA = "hswm-b22-gate0-acceptance-receipt/v1"
FEATURE_SCHEMA = "hswm-b22-feature-view/v1"
SUPERVISION_SCHEMA = "hswm-b22-supervision-sidecar/v1"
CACHE_HISTORY_SCHEMA = "hswm-b21-shared-cache-history/v1"
CACHE_HISTORY_PROFILE = "b21-r1-exact-prefix-through-target"
CACHE_HISTORY_SCOPE = "prefix_through_role_target"
ACCEPTANCE_CLAIM_BOUNDARY = (
    "mechanical full-candidate replay only; no retrieval-gain claim"
)
AXIS_ORDER = "query,edge"
DTYPE = "<f8"
COMPONENT_TOLERANCE = 1e-12
REPLAY_TOLERANCE = 1e-9

ACCEPTANCE_ROLES = {
    "b2_reproduction400": {"dataset": "2wiki", "cohort": "b2_reproduction400",
                            "requires_frozen_b2": True, "queries": 400, "edges": 2753},
    "2wiki_full_closed_corpus": {"dataset": "2wiki", "cohort": "full_closed_corpus",
                                  "requires_frozen_b2": False, "queries": 500, "edges": 3452},
    "musique_full_closed_corpus": {"dataset": "musique", "cohort": "full_closed_corpus",
                                    "requires_frozen_b2": False, "queries": 800, "edges": 8893},
}

EXPECTED_B21_CACHE_HISTORY = {
    "b2_reproduction400": (),
    "2wiki_full_closed_corpus": (
        "2wiki/b2_reproduction400/base/legacy",
        "2wiki/b2_reproduction400/frozen_reference",
    ),
    "musique_full_closed_corpus": (
        "2wiki/b2_reproduction400/base/legacy",
        "2wiki/b2_reproduction400/frozen_reference",
        "2wiki/full_closed_corpus/base/legacy",
        "2wiki/full_closed_corpus/base/b21-field-v1",
        "2wiki/full_closed_corpus/base/b21-field-v2",
        "2wiki/full_closed_corpus/private_entity/legacy",
    ),
}

ARRAY_FILES = {
    "edge_cosine": "edge_cosine.npy",
    "vertex_channel": "vertex_channel.npy",
    "bridge_no_seam": "bridge_no_seam.npy",
    "bridge_merged": "bridge_merged.npy",
    "base_no_seam": "base_no_seam.npy",
    "base_merged": "base_merged.npy",
}
SIDE_FILES = {
    "edges": "edges.json",
    "queries": "queries.json",
    "supervision": "supervision.json",
}
MANIFEST_FILE = "manifest.json"


class Gate0Error(RuntimeError):
    """Base class for typed, fail-closed Gate 0 failures."""


class PackIntegrityError(Gate0Error):
    """Pack identity, schema, hash, dtype, shape, or value failure."""


class ReplayMismatch(Gate0Error):
    """Component, neutral, B2.1, or frozen-B2 replay failure."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def _json_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _array_sha256(value: np.ndarray) -> str:
    array = np.ascontiguousarray(value)
    digest = hashlib.sha256()
    digest.update(_canonical_bytes({"dtype": array.dtype.str, "shape": list(array.shape)}))
    digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def _is_sha256(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(ch in "0123456789abcdef" for ch in value))


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    out: dict[str, object] = {}
    for key, value in pairs:
        if key in out:
            raise PackIntegrityError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"),
                          object_pairs_hook=_reject_duplicate_keys)
    except PackIntegrityError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PackIntegrityError(f"invalid JSON {path.name}: {exc}") from exc


def _read_pinned_payload(path: Path, entry: Mapping[str, object]) -> bytes:
    """Read exactly the bytes named by a manifest entry.

    Verification and parsing share this immutable byte snapshot.  This avoids a
    path being hashed once and reopened later after replacement or mutation.
    """
    expected_sha = entry.get("sha256")
    expected_bytes = entry.get("bytes")
    if not _is_sha256(expected_sha):
        raise PackIntegrityError(f"invalid payload hash: {path.name}")
    if (isinstance(expected_bytes, bool)
            or not isinstance(expected_bytes, int) or expected_bytes < 0):
        raise PackIntegrityError(f"invalid payload byte count: {path.name}")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise PackIntegrityError(f"cannot read payload {path.name}: {exc}") from exc
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise PackIntegrityError(f"payload is not a regular file: {path.name}")
        with os.fdopen(fd, "rb") as handle:
            fd = -1
            payload = handle.read()
    finally:
        if fd >= 0:
            os.close(fd)
    if len(payload) != expected_bytes:
        raise PackIntegrityError(f"payload byte count mismatch: {path.name}")
    if hashlib.sha256(payload).hexdigest() != expected_sha:
        raise PackIntegrityError(f"payload hash mismatch: {path.name}")
    return payload


def _read_pinned_json(path: Path, entry: Mapping[str, object]) -> object:
    payload = _read_pinned_payload(path, entry)
    try:
        return json.loads(payload.decode("utf-8"),
                          object_pairs_hook=_reject_duplicate_keys)
    except PackIntegrityError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PackIntegrityError(f"invalid JSON {path.name}: {exc}") from exc


def _strict_model_manifest(path: Path) -> dict:
    """Hash a model snapshot only when its complete tree is symlink-free."""
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise PackIntegrityError("model snapshot must be a real directory")
    root = path.resolve()
    for current, directories, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in [*directories, *filenames]:
            candidate = current_path / name
            if candidate.is_symlink():
                raise PackIntegrityError(
                    f"model snapshot contains symlink: {candidate.relative_to(root)}"
                )
    try:
        return directory_manifest(root)
    except (OSError, RuntimeError) as exc:
        raise PackIntegrityError(f"invalid model snapshot: {exc}") from exc


def _paths_overlap(left: Path, right: Path) -> bool:
    left = Path(left).absolute().resolve()
    right = Path(right).absolute().resolve()
    return left == right or left in right.parents or right in left.parents


def _path_is_inside(path: Path, directory: Path) -> bool:
    path = Path(path).absolute().resolve()
    directory = Path(directory).absolute().resolve()
    return path == directory or directory in path.parents


def _reject_artifact_overlap(named_paths: Mapping[str, Path]) -> None:
    items = [(name, Path(path).absolute()) for name, path in named_paths.items()]
    for index, (left_name, left) in enumerate(items):
        for right_name, right in items[index + 1:]:
            if _paths_overlap(left, right):
                raise PackIntegrityError(
                    f"artifact paths overlap: {left_name}={left} / {right_name}={right}"
                )


def _reject_output_inside_packs(output: Path,
                                named_packs: Mapping[str, Path]) -> Path:
    output = Path(output).absolute()
    if output.is_symlink():
        raise PackIntegrityError(f"refusing symlinked receipt output: {output}")
    for name, pack in named_packs.items():
        if _path_is_inside(output, Path(pack)):
            raise PackIntegrityError(
                f"receipt output is inside pack {name}: {output}"
            )
    return output


def _require_utc_timestamp(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise PackIntegrityError(f"{label} must be a UTC ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise PackIntegrityError(f"{label} is not ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise PackIntegrityError(f"{label} must carry UTC offset")
    return value


def _require_path(value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise PackIntegrityError(f"{label} must be a non-empty path string")
    return Path(value)


def _write_json(path: Path, value: object) -> None:
    path.write_bytes(_canonical_bytes(value))


def _strict_keys(value: Mapping[str, object], expected: set[str], label: str) -> None:
    observed = set(value)
    if observed != expected:
        raise PackIntegrityError(
            f"{label} keys mismatch: missing={sorted(expected-observed)}, "
            f"extra={sorted(observed-expected)}"
        )


def _require_nonempty_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise PackIntegrityError(f"{label} must be a non-empty string")
    return value


def _normalize_matrix(values: object, expected_rows: int) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 2 or array.shape[0] != expected_rows or array.shape[1] == 0:
        raise PackIntegrityError(
            f"embedder returned shape {array.shape}; expected ({expected_rows}, D)"
        )
    if not np.isfinite(array).all():
        raise PackIntegrityError("embedder returned NaN or infinity")
    norms = np.linalg.norm(array, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return array / norms


def _bridge_scores(groups: Mapping[object, Sequence[int]],
                   edge_cosine: np.ndarray) -> np.ndarray:
    """Independent query-major implementation of frozen B2 max-other bridge."""
    bridge = np.zeros_like(edge_cosine, dtype=np.float64)
    qrows = np.arange(edge_cosine.shape[0])
    for indices0 in groups.values():
        indices = np.asarray(sorted(set(indices0)), dtype=np.int64)
        if len(indices) < 2:
            continue
        values = edge_cosine[:, indices]
        top = np.max(values, axis=1)
        arg = np.argmax(values, axis=1)
        second = np.partition(values, len(indices) - 2, axis=1)[:, len(indices) - 2]
        candidates = np.broadcast_to(top[:, None], values.shape).copy()
        candidates[qrows, arg] = second
        candidates = np.maximum(candidates, 0.0)
        bridge[:, indices] = np.maximum(bridge[:, indices], candidates)
    return bridge


def _little_f8(array: np.ndarray) -> np.ndarray:
    out = np.ascontiguousarray(array, dtype=np.dtype(DTYPE))
    if out.dtype.str != DTYPE or not out.flags.c_contiguous:
        raise PackIntegrityError("failed to canonicalize array as C-contiguous <f8")
    if not np.isfinite(out).all():
        raise PackIntegrityError("component array contains NaN or infinity")
    return out


def _candidate_digest(dataset: str, salt: str, condition: str,
                      edges: Sequence[dict]) -> str:
    return _json_sha256({"dataset": dataset, "salt": salt,
                         "condition": condition, "edges": list(edges)})


def _query_digest(dataset: str, cohort: str, queries: Sequence[dict]) -> str:
    return _json_sha256({"dataset": dataset, "cohort": cohort,
                         "queries": list(queries)})


def _stable_order(edge_ids: Sequence[str], scores: np.ndarray,
                  indices: Sequence[int] | None = None) -> list[int]:
    selected = list(range(len(edge_ids))) if indices is None else list(indices)
    return sorted(selected, key=lambda i: (-float(scores[i]), edge_ids[i]))


def _ranking_sha256(edge_ids: Sequence[str], scores: np.ndarray,
                    indices: Sequence[int] | None = None) -> str:
    order = _stable_order(edge_ids, scores, indices)
    rows = [{"edge_id": edge_ids[i], "score": float(scores[i])} for i in order]
    return _json_sha256(rows)


def _validate_provenance(provenance: Mapping[str, object]) -> dict:
    required = {"dataset_sha256", "model_snapshot_sha256", "producer_sha256"}
    _strict_keys(provenance, required, "provenance")
    dataset_sha = provenance["dataset_sha256"]
    model_sha = provenance["model_snapshot_sha256"]
    producers = provenance["producer_sha256"]
    if not _is_sha256(dataset_sha) or not _is_sha256(model_sha):
        raise PackIntegrityError("dataset/model provenance must be lowercase SHA-256")
    if not isinstance(producers, Mapping) or not producers:
        raise PackIntegrityError("producer_sha256 must be a non-empty mapping")
    for name, digest in producers.items():
        _require_nonempty_text(name, "producer name")
        if not _is_sha256(digest):
            raise PackIntegrityError(f"invalid producer SHA-256 for {name}")
    return {"dataset_sha256": dataset_sha, "model_snapshot_sha256": model_sha,
            "producer_sha256": dict(sorted(producers.items()))}


@dataclass(frozen=True)
class CompiledGate0Pack:
    manifest_seed: dict
    edges: tuple[dict, ...]
    queries: tuple[dict, ...]
    supervision: tuple[dict, ...]
    arrays: Mapping[str, np.ndarray]


def _compiled_semantic_sha256(compiled: CompiledGate0Pack) -> str:
    return _json_sha256({
        "manifest_seed": compiled.manifest_seed,
        "edges": list(compiled.edges),
        "queries": list(compiled.queries),
        "supervision": list(compiled.supervision),
        "arrays": {name: _array_sha256(array)
                   for name, array in sorted(compiled.arrays.items())},
    })


def compile_full_candidate_pack(
    queries: Sequence[Query],
    pool: Mapping[str, Paragraph],
    embed_fn: Callable[[list[str]], Sequence[Sequence[float]]],
    *,
    dataset: str,
    salt: str = "legacy",
    cohort: str = "full_closed_corpus",
    condition: str = "base",
    model_id: str = MODEL_NAME,
    provenance: Mapping[str, object],
) -> CompiledGate0Pack:
    """Compile complete B2 score components without top-k truncation."""
    if salt not in PARTITION_SALTS:
        raise PackIntegrityError(f"unregistered salt: {salt}")
    if condition != "base":
        raise PackIntegrityError("Gate 0 v1 supports condition=base only")
    _require_nonempty_text(dataset, "dataset")
    _require_nonempty_text(cohort, "cohort")
    _require_nonempty_text(model_id, "model_id")
    provenance1 = _validate_provenance(provenance)
    if not queries or not pool:
        raise PackIntegrityError("queries and candidate pool must be non-empty")

    edge_ids = sorted(pool)
    if len(edge_ids) != len(set(edge_ids)):
        raise PackIntegrityError("duplicate candidate edge ID")
    edge_pos = {edge_id: i for i, edge_id in enumerate(edge_ids)}
    labels = [field_label(pool[edge_id].title, salt) for edge_id in edge_ids]
    if set(labels) != {"A", "B"}:
        raise PackIntegrityError("candidate pool must contain both A and B fields")

    vertex_keys: list[tuple[int, str]] = []
    vertex_pos: dict[tuple[int, str], int] = {}
    members: list[list[int]] = []
    member_names: list[tuple[str, ...]] = []
    groups_field: dict[tuple[int, str], list[int]] = {}
    groups_merged: dict[str, list[int]] = {}
    for edge_i, edge_id in enumerate(edge_ids):
        paragraph = pool[edge_id]
        if paragraph.pid != edge_id:
            raise PackIntegrityError(f"paragraph identity mismatch: {edge_id}")
        if stable_pid(paragraph.title, paragraph.body) != edge_id:
            raise PackIntegrityError(f"unstable/colliding paragraph identity: {edge_id}")
        field_i = 0 if labels[edge_i] == "A" else 1
        row: list[int] = []
        names = tuple(sorted(set(paragraph.entities)))
        for entity in names:
            key = (field_i, entity)
            if key not in vertex_pos:
                vertex_pos[key] = len(vertex_keys)
                vertex_keys.append(key)
            row.append(vertex_pos[key])
            groups_field.setdefault(key, []).append(edge_i)
            groups_merged.setdefault(entity, []).append(edge_i)
        members.append(row)
        member_names.append(names)

    edge_texts = [finding_text(pool[edge_id].title, pool[edge_id].body)
                  for edge_id in edge_ids]
    vertex_texts = [entity for _, entity in vertex_keys]
    query_texts = [query.question for query in queries]
    texts = sorted(set(edge_texts) | set(vertex_texts) | set(query_texts))
    embedded = _normalize_matrix(embed_fn(texts), len(texts))
    table = {text: embedded[i] for i, text in enumerate(texts)}
    edge_matrix = np.vstack([table[text] for text in edge_texts])
    query_matrix = np.vstack([table[text] for text in query_texts])
    vertex_matrix = (np.vstack([table[text] for text in vertex_texts])
                     if vertex_texts else np.empty((0, edge_matrix.shape[1])))

    edge_cosine = query_matrix @ edge_matrix.T
    vertex_cosine = (query_matrix @ vertex_matrix.T
                     if len(vertex_matrix) else np.empty((len(queries), 0)))
    vertex_channel = np.zeros_like(edge_cosine)
    for edge_i, indices in enumerate(members):
        if indices:
            vertex_channel[:, edge_i] = np.max(vertex_cosine[:, indices], axis=1)
    bridge_no_seam = _bridge_scores(groups_field, edge_cosine)
    bridge_merged = _bridge_scores(groups_merged, edge_cosine)
    base_no_seam = edge_cosine + LAM_V * vertex_channel + LAM_B * bridge_no_seam
    base_merged = edge_cosine + LAM_V * vertex_channel + LAM_B * bridge_merged
    arrays = {
        "edge_cosine": _little_f8(edge_cosine),
        "vertex_channel": _little_f8(vertex_channel),
        "bridge_no_seam": _little_f8(bridge_no_seam),
        "bridge_merged": _little_f8(bridge_merged),
        "base_no_seam": _little_f8(base_no_seam),
        "base_merged": _little_f8(base_merged),
    }

    edge_records: list[dict] = []
    for edge_i, edge_id in enumerate(edge_ids):
        names = member_names[edge_i]
        field_i = 0 if labels[edge_i] == "A" else 1
        field_sizes = [len(groups_field[(field_i, name)]) for name in names]
        merged_sizes = [len(groups_merged[name]) for name in names]
        text_digest = hashlib.sha256(edge_texts[edge_i].encode("utf-8")).hexdigest()
        member_digests = [hashlib.sha256(name.casefold().encode("utf-8")).hexdigest()
                          for name in names]
        edge_records.append({
            "edge_index": edge_i,
            "edge_id": edge_id,
            "field_label": labels[edge_i],
            "edge_text_sha256": text_digest,
            "member_set_sha256": _json_sha256(member_digests),
            "arity": len(names),
            "max_field_class_size": max(field_sizes, default=1),
            "max_merged_class_size": max(merged_sizes, default=1),
        })

    query_records: list[dict] = []
    supervision: list[dict] = []
    seen_qids: set[str] = set()
    candidate_set = set(edge_ids)
    for query_i, query in enumerate(queries):
        qid_sha = hashlib.sha256(query.qid.encode("utf-8")).hexdigest()
        if qid_sha in seen_qids:
            raise PackIntegrityError(f"duplicate query identity at index {query_i}")
        seen_qids.add(qid_sha)
        question_sha = hashlib.sha256(query.question.encode("utf-8")).hexdigest()
        query_records.append({
            "query_index": query_i,
            "qid_sha256": qid_sha,
            "question_sha256": question_sha,
            "query_token_count": len(query.question.split()),
            "query_entity_count": len(base_entities(query.question)),
        })
        gold = sorted(set(query.gold))
        if not gold or not set(gold) <= candidate_set:
            raise PackIntegrityError(f"query {query_i} has invalid gold candidate coverage")
        gold_fields = {labels[edge_pos[edge_id]] for edge_id in gold}
        supervision.append({
            "query_index": query_i,
            "qid_sha256": qid_sha,
            "gold_edge_ids": gold,
            "class": "cross_field" if gold_fields == {"A", "B"} else "in_field",
        })

    candidate_sha = _candidate_digest(dataset, salt, condition, edge_records)
    query_sha = _query_digest(dataset, cohort, query_records)
    topology_sha = _json_sha256({
        "candidate_set_sha256": candidate_sha,
        "member_set_sha256": [record["member_set_sha256"] for record in edge_records],
        "field_labels": labels,
    })
    manifest_seed = {
        "schema": SCHEMA,
        "status": "DEVELOPMENT_ONLY",
        "engineering_gate_only": True,
        "scientific_claim_allowed": False,
        "identity": {
            "dataset": dataset,
            "cohort": cohort,
            "condition": condition,
            "salt": salt,
            "model_id": model_id,
        },
        "counts": {
            "queries": len(query_records),
            "edges": len(edge_records),
            "vertices": len(vertex_keys),
            "merged_entity_classes": len(groups_merged),
        },
        "array_contract": {"axis_order": AXIS_ORDER, "dtype": DTYPE,
                           "c_contiguous": True},
        "formula": {
            "version": "hswm-b22-gate0-components/v1",
            "bond_formula_version": BOND_FORMULA_VERSION,
            "lam_v": LAM_V,
            "lam_b": LAM_B,
            "sort": "score_desc_edge_id_asc",
        },
        "candidate_set_sha256": candidate_sha,
        "query_set_sha256": query_sha,
        "topology_sha256": topology_sha,
        "text_table_sha256": _json_sha256([
            hashlib.sha256(text.encode("utf-8")).hexdigest() for text in texts
        ]),
        "embedding_table_sha256": _array_sha256(embedded),
        "provenance": provenance1,
    }
    return CompiledGate0Pack(
        manifest_seed=manifest_seed,
        edges=tuple(edge_records),
        queries=tuple(query_records),
        supervision=tuple(supervision),
        arrays=arrays,
    )


def _file_entry(path: Path, *, array: np.ndarray | None = None) -> dict:
    entry = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
    if array is not None:
        entry.update({"dtype": array.dtype.str, "shape": list(array.shape),
                      "c_contiguous": bool(array.flags.c_contiguous)})
    return entry


def _seal_manifest(manifest_core: dict) -> dict:
    sealed = dict(manifest_core)
    sealed["pack_root_sha256"] = _json_sha256(manifest_core)
    return sealed


def _unsealed_manifest(manifest: Mapping[str, object]) -> dict:
    return {key: value for key, value in manifest.items() if key != "pack_root_sha256"}


def write_pack(
    output_dir: Path,
    compiled: CompiledGate0Pack,
    *,
    frozen_b2: dict | None = None,
    b21_scorepack: dict | None = None,
) -> dict:
    """Write, verify, and atomically publish a new pack; replacement is forbidden."""
    output_dir = Path(output_dir)
    if output_dir.is_symlink():
        raise PackIntegrityError(f"refusing symlinked pack output: {output_dir}")
    output_dir = output_dir.resolve()
    if output_dir.exists() or output_dir.is_symlink():
        raise PackIntegrityError(f"refusing to replace existing pack: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.tmp-",
                                    dir=output_dir.parent))
    try:
        edges_doc = {"schema": FEATURE_SCHEMA, "records": list(compiled.edges)}
        queries_doc = {"schema": FEATURE_SCHEMA, "records": list(compiled.queries)}
        supervision_doc = {"schema": SUPERVISION_SCHEMA,
                           "records": list(compiled.supervision)}
        _write_json(staging / SIDE_FILES["edges"], edges_doc)
        _write_json(staging / SIDE_FILES["queries"], queries_doc)
        _write_json(staging / SIDE_FILES["supervision"], supervision_doc)
        files = {
            SIDE_FILES["edges"]: _file_entry(staging / SIDE_FILES["edges"]),
            SIDE_FILES["queries"]: _file_entry(staging / SIDE_FILES["queries"]),
            SIDE_FILES["supervision"]: _file_entry(staging / SIDE_FILES["supervision"]),
        }
        for name, filename in ARRAY_FILES.items():
            array = compiled.arrays[name]
            with (staging / filename).open("wb") as handle:
                np.save(handle, array, allow_pickle=False)
            files[filename] = _file_entry(staging / filename, array=array)
        manifest = _seal_manifest({**compiled.manifest_seed,
                                   "files": dict(sorted(files.items()))})
        _write_json(staging / MANIFEST_FILE, manifest)
        receipt = verify_pack(staging, expected_root=manifest["pack_root_sha256"])
        if frozen_b2 is not None:
            receipt["frozen_b2_replay"] = compare_frozen_b2(
                staging, frozen_b2, verify_first=False)
        if b21_scorepack is not None:
            receipt["b21_topk_continuity"] = compare_b21_scorepack(
                staging, b21_scorepack, verify_first=False)
        if not receipt.get("pass"):
            raise ReplayMismatch("staging verification did not pass")
        os.replace(staging, output_dir)
        receipt["pack_path"] = str(output_dir)
        return receipt
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def _load_manifest(pack_dir: Path, expected_root: str | None = None) -> dict:
    if pack_dir.is_symlink() or not pack_dir.is_dir():
        raise PackIntegrityError("pack path must be a real directory")
    manifest_path = pack_dir / MANIFEST_FILE
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise PackIntegrityError("missing or symlinked manifest.json")
    manifest = _read_json(manifest_path)
    if not isinstance(manifest, dict):
        raise PackIntegrityError("manifest must be an object")
    expected_keys = {
        "schema", "status", "engineering_gate_only", "scientific_claim_allowed",
        "identity", "counts", "array_contract", "formula",
        "candidate_set_sha256", "query_set_sha256", "topology_sha256",
        "text_table_sha256", "embedding_table_sha256", "provenance", "files",
        "pack_root_sha256",
    }
    _strict_keys(manifest, expected_keys, "manifest")
    if manifest["schema"] != SCHEMA or manifest["status"] != "DEVELOPMENT_ONLY":
        raise PackIntegrityError("wrong pack schema or status")
    if manifest["engineering_gate_only"] is not True:
        raise PackIntegrityError("engineering gate boundary missing")
    if manifest["scientific_claim_allowed"] is not False:
        raise PackIntegrityError("scientific claim boundary violated")
    if not _is_sha256(manifest["embedding_table_sha256"]):
        raise PackIntegrityError("invalid embedding-table digest")
    identity = manifest["identity"]
    counts = manifest["counts"]
    if not isinstance(identity, dict) or not isinstance(counts, dict):
        raise PackIntegrityError("manifest identity/counts must be objects")
    _strict_keys(identity, {"dataset", "cohort", "condition", "salt", "model_id"},
                 "manifest identity")
    _strict_keys(counts, {"queries", "edges", "vertices", "merged_entity_classes"},
                 "manifest counts")
    for key, value in counts.items():
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise PackIntegrityError(f"invalid manifest count: {key}")
    if identity["salt"] not in PARTITION_SALTS or identity["condition"] != "base":
        raise PackIntegrityError("unsupported manifest salt/condition")
    root = manifest["pack_root_sha256"]
    if not _is_sha256(root) or _json_sha256(_unsealed_manifest(manifest)) != root:
        raise PackIntegrityError("manifest pack root mismatch")
    if expected_root is not None and root != expected_root:
        raise PackIntegrityError("pack root differs from out-of-band expected root")
    return manifest


def _validate_file_set(pack_dir: Path, manifest: Mapping[str, object]) -> None:
    files = manifest["files"]
    if not isinstance(files, dict):
        raise PackIntegrityError("manifest files must be an object")
    required_payloads = set(SIDE_FILES.values()) | set(ARRAY_FILES.values())
    if set(files) != required_payloads:
        raise PackIntegrityError(
            f"manifest payload set mismatch: missing={sorted(required_payloads-set(files))}, "
            f"extra={sorted(set(files)-required_payloads)}"
        )
    expected = {MANIFEST_FILE, *files}
    observed = {path.name for path in pack_dir.iterdir()}
    if observed != expected:
        raise PackIntegrityError(
            f"pack file set mismatch: missing={sorted(expected-observed)}, "
            f"extra={sorted(observed-expected)}"
        )
    for name, entry in files.items():
        path = pack_dir / name
        if Path(name).name != name or path.is_symlink() or not path.is_file():
            raise PackIntegrityError(f"invalid/symlinked payload: {name}")
        if not isinstance(entry, dict):
            raise PackIntegrityError(f"file entry must be an object: {name}")
        if not name.endswith(".npy"):
            _strict_keys(entry, {"sha256", "bytes"}, f"file manifest {name}")
        if not _is_sha256(entry.get("sha256")):
            raise PackIntegrityError(f"invalid payload hash: {name}")
        if path.stat().st_size != entry.get("bytes"):
            raise PackIntegrityError(f"payload byte count mismatch: {name}")


def _load_sidecars(pack_dir: Path, manifest: Mapping[str, object]) -> tuple[list[dict], list[dict], list[dict]]:
    files = manifest["files"]
    edges_doc = _read_pinned_json(
        pack_dir / SIDE_FILES["edges"], files[SIDE_FILES["edges"]])
    queries_doc = _read_pinned_json(
        pack_dir / SIDE_FILES["queries"], files[SIDE_FILES["queries"]])
    supervision_doc = _read_pinned_json(
        pack_dir / SIDE_FILES["supervision"], files[SIDE_FILES["supervision"]])
    for doc, schema, label in (
        (edges_doc, FEATURE_SCHEMA, "edges"),
        (queries_doc, FEATURE_SCHEMA, "queries"),
        (supervision_doc, SUPERVISION_SCHEMA, "supervision"),
    ):
        if not isinstance(doc, dict):
            raise PackIntegrityError(f"{label} sidecar must be an object")
        _strict_keys(doc, {"schema", "records"}, f"{label} sidecar")
        if doc["schema"] != schema or not isinstance(doc["records"], list):
            raise PackIntegrityError(f"invalid {label} sidecar schema")
    edges = edges_doc["records"]
    queries = queries_doc["records"]
    supervision = supervision_doc["records"]
    counts = manifest["counts"]
    if len(edges) != counts.get("edges") or len(queries) != counts.get("queries"):
        raise PackIntegrityError("sidecar count mismatch")
    if len(supervision) != len(queries):
        raise PackIntegrityError("supervision count mismatch")
    return edges, queries, supervision


def _validate_identities(manifest: Mapping[str, object], edges: Sequence[dict],
                         queries: Sequence[dict], supervision: Sequence[dict]) -> tuple[list[str], list[str]]:
    edge_keys = {"edge_index", "edge_id", "field_label", "edge_text_sha256",
                 "member_set_sha256", "arity", "max_field_class_size",
                 "max_merged_class_size"}
    query_keys = {"query_index", "qid_sha256", "question_sha256",
                  "query_token_count", "query_entity_count"}
    supervision_keys = {"query_index", "qid_sha256", "gold_edge_ids", "class"}
    edge_ids: list[str] = []
    labels: list[str] = []
    for index, record in enumerate(edges):
        if not isinstance(record, dict):
            raise PackIntegrityError("edge record must be an object")
        _strict_keys(record, edge_keys, f"edge record {index}")
        if record["edge_index"] != index:
            raise PackIntegrityError("edge indices are not canonical")
        edge_ids.append(_require_nonempty_text(record["edge_id"], "edge_id"))
        labels.append(record["field_label"])
        if record["field_label"] not in ("A", "B"):
            raise PackIntegrityError("invalid field label")
        if not _is_sha256(record["edge_text_sha256"]) or not _is_sha256(record["member_set_sha256"]):
            raise PackIntegrityError("invalid edge identity digest")
        for name in ("arity", "max_field_class_size", "max_merged_class_size"):
            if isinstance(record[name], bool) or not isinstance(record[name], int) or record[name] < 0:
                raise PackIntegrityError(f"invalid structural count: {name}")
    if edge_ids != sorted(edge_ids) or len(edge_ids) != len(set(edge_ids)):
        raise PackIntegrityError("edge IDs must be unique and lexically sorted")
    if set(labels) != {"A", "B"}:
        raise PackIntegrityError("both field labels are required")

    qids: list[str] = []
    for index, (record, target) in enumerate(zip(queries, supervision)):
        if not isinstance(record, dict) or not isinstance(target, dict):
            raise PackIntegrityError("query/supervision record must be an object")
        _strict_keys(record, query_keys, f"query record {index}")
        _strict_keys(target, supervision_keys, f"supervision record {index}")
        if record["query_index"] != index or target["query_index"] != index:
            raise PackIntegrityError("query indices are not canonical")
        qid = record["qid_sha256"]
        if not _is_sha256(qid) or not _is_sha256(record["question_sha256"]):
            raise PackIntegrityError("invalid query identity digest")
        if target["qid_sha256"] != qid:
            raise PackIntegrityError("supervision/query identity mismatch")
        if target["class"] not in ("cross_field", "in_field"):
            raise PackIntegrityError("invalid supervision class")
        gold = target["gold_edge_ids"]
        if (not isinstance(gold, list) or not gold or gold != sorted(set(gold))
                or not set(gold) <= set(edge_ids)):
            raise PackIntegrityError("invalid supervision gold coverage")
        qids.append(qid)
    if len(qids) != len(set(qids)):
        raise PackIntegrityError("duplicate query identity")
    identity = manifest["identity"]
    candidate_sha = _candidate_digest(identity["dataset"], identity["salt"],
                                      identity["condition"], edges)
    query_sha = _query_digest(identity["dataset"], identity["cohort"], queries)
    if candidate_sha != manifest["candidate_set_sha256"]:
        raise PackIntegrityError("candidate-set digest mismatch")
    if query_sha != manifest["query_set_sha256"]:
        raise PackIntegrityError("query-set digest mismatch")
    topology_sha = _json_sha256({
        "candidate_set_sha256": candidate_sha,
        "member_set_sha256": [record["member_set_sha256"] for record in edges],
        "field_labels": labels,
    })
    if topology_sha != manifest["topology_sha256"]:
        raise PackIntegrityError("topology digest mismatch")
    return edge_ids, labels


def _load_arrays(pack_dir: Path, manifest: Mapping[str, object]) -> dict[str, np.ndarray]:
    counts = manifest["counts"]
    expected_shape = (counts["queries"], counts["edges"])
    arrays: dict[str, np.ndarray] = {}
    for name, filename in ARRAY_FILES.items():
        entry = manifest["files"].get(filename)
        if not isinstance(entry, dict):
            raise PackIntegrityError(f"missing array manifest entry: {filename}")
        _strict_keys(entry, {"sha256", "bytes", "dtype", "shape", "c_contiguous"},
                     f"array manifest {filename}")
        try:
            payload = _read_pinned_payload(pack_dir / filename, entry)
            loaded = np.load(io.BytesIO(payload), allow_pickle=False)
            array = np.array(loaded, dtype=loaded.dtype, order="C", copy=True)
            array.setflags(write=False)
        except Exception as exc:
            if isinstance(exc, PackIntegrityError):
                raise
            raise PackIntegrityError(f"cannot load array {filename}: {exc}") from exc
        if array.dtype.str != DTYPE or entry["dtype"] != DTYPE:
            raise PackIntegrityError(f"array dtype mismatch: {filename}")
        if array.shape != expected_shape or entry["shape"] != list(expected_shape):
            raise PackIntegrityError(f"array shape mismatch: {filename}")
        if not array.flags.c_contiguous or entry["c_contiguous"] is not True:
            raise PackIntegrityError(f"array contiguity mismatch: {filename}")
        if not np.isfinite(array).all():
            raise PackIntegrityError(f"array contains NaN or infinity: {filename}")
        arrays[name] = array
    return arrays


def _component_error(arrays: Mapping[str, np.ndarray]) -> tuple[float, float]:
    q_count = arrays["edge_cosine"].shape[0]
    max_no_seam = 0.0
    max_merged = 0.0
    for start in range(0, q_count, 32):
        sl = slice(start, min(q_count, start + 32))
        common = (arrays["edge_cosine"][sl]
                  + LAM_V * arrays["vertex_channel"][sl])
        expected_no = common + LAM_B * arrays["bridge_no_seam"][sl]
        expected_merged = common + LAM_B * arrays["bridge_merged"][sl]
        max_no_seam = max(max_no_seam, float(np.max(np.abs(
            arrays["base_no_seam"][sl] - expected_no))))
        max_merged = max(max_merged, float(np.max(np.abs(
            arrays["base_merged"][sl] - expected_merged))))
    return max_no_seam, max_merged


def _neutral_replay(edge_ids: Sequence[str], base_merged: np.ndarray) -> dict:
    neutral_slow = tuple(SemanticWeight(edge_id, 0.0) for edge_id in edge_ids)
    arbitrary_slow = tuple(SemanticWeight(edge_id, -0.01 * (i % 7))
                           for i, edge_id in enumerate(edge_ids))
    constant_query = normalize_query_logits({edge_id: 17.0 for edge_id in edge_ids})
    arbitrary_query = tuple(QueryBondWeight(edge_id, -0.02 * (i % 5))
                            for i, edge_id in enumerate(edge_ids))
    max_error = 0.0
    mismatch_count = 0
    digest = hashlib.sha256()
    for query_i in range(base_merged.shape[0]):
        row = np.asarray(base_merged[query_i], dtype=np.float64)
        base = {edge_id: float(row[i]) for i, edge_id in enumerate(edge_ids)}
        expected_order = _stable_order(edge_ids, row)
        variants = (
            rank_bonds(base, neutral_slow),
            rank_bonds(base, neutral_slow, query_weights=constant_query),
            rank_bonds(base, arbitrary_slow, query_weights=arbitrary_query,
                       slow_scale=0.0, query_scale=0.0),
        )
        for variant in variants:
            observed_ids = [item.edge_id for item in variant]
            expected_ids = [edge_ids[i] for i in expected_order]
            if observed_ids != expected_ids:
                mismatch_count += 1
            observed_scores = np.asarray([item.score for item in variant])
            expected_scores = row[expected_order]
            if len(observed_scores):
                max_error = max(max_error, float(np.max(np.abs(
                    observed_scores - expected_scores))))
        digest.update(_ranking_sha256(edge_ids, row).encode("ascii"))
    passed = mismatch_count == 0 and max_error <= REPLAY_TOLERANCE
    if not passed:
        raise ReplayMismatch(
            f"neutral replay mismatch: rankings={mismatch_count}, max_error={max_error}"
        )
    return {
        "variants": ["zero_slow_omitted_query", "constant_query_logits",
                     "zero_scales_arbitrary_nonpositive"],
        "queries": int(base_merged.shape[0]),
        "candidates": int(base_merged.shape[1]),
        "ranking_mismatches": mismatch_count,
        "max_abs_score_error": max_error,
        "ranking_sha256": digest.hexdigest(),
        "pass": True,
    }


def verify_pack(pack_dir: Path, *, expected_root: str | None = None) -> dict:
    """Verify hashes, schema, identities, components, and neutral replay."""
    pack_dir = Path(pack_dir)
    if pack_dir.is_symlink():
        raise PackIntegrityError("pack path must not be a symlink")
    pack_dir = pack_dir.absolute()
    manifest = _load_manifest(pack_dir, expected_root)
    _validate_file_set(pack_dir, manifest)
    edges, queries, supervision = _load_sidecars(pack_dir, manifest)
    edge_ids, _ = _validate_identities(manifest, edges, queries, supervision)
    _validate_provenance(manifest["provenance"])
    contract = manifest["array_contract"]
    if contract != {"axis_order": AXIS_ORDER, "dtype": DTYPE, "c_contiguous": True}:
        raise PackIntegrityError("array contract drift")
    formula = manifest["formula"]
    expected_formula = {
        "version": "hswm-b22-gate0-components/v1",
        "bond_formula_version": BOND_FORMULA_VERSION,
        "lam_v": LAM_V,
        "lam_b": LAM_B,
        "sort": "score_desc_edge_id_asc",
    }
    if formula != expected_formula:
        raise PackIntegrityError("formula contract drift")
    arrays = _load_arrays(pack_dir, manifest)
    no_error, merged_error = _component_error(arrays)
    if max(no_error, merged_error) > COMPONENT_TOLERANCE:
        raise ReplayMismatch(
            f"component algebra mismatch: no_seam={no_error}, merged={merged_error}"
        )
    neutral = _neutral_replay(edge_ids, arrays["base_merged"])
    return {
        "schema": RECEIPT_SCHEMA,
        "status": "PACK_SELF_CHECK_PASS",
        "pass": True,
        "engineering_gate_only": True,
        "scientific_claim_allowed": False,
        # A single pack can prove only intrinsic integrity.  Gate-0 acceptance
        # requires the separately locked three-pack bundle below.
        "learner_allowed": False,
        "pack_root_sha256": manifest["pack_root_sha256"],
        "candidate_set_sha256": manifest["candidate_set_sha256"],
        "query_set_sha256": manifest["query_set_sha256"],
        "counts": manifest["counts"],
        "component_replay": {
            "tolerance": COMPONENT_TOLERANCE,
            "max_abs_no_seam_error": no_error,
            "max_abs_merged_error": merged_error,
            "pass": True,
        },
        "neutral_replay": neutral,
    }


def _public_manifest_projection(manifest: Mapping[str, object]) -> dict:
    """Return only learner-relevant, path-free metadata from a verified pack."""
    return {
        "schema": manifest["schema"],
        "identity": dict(manifest["identity"]),
        "counts": dict(manifest["counts"]),
        "array_contract": dict(manifest["array_contract"]),
        "formula": dict(manifest["formula"]),
        "candidate_set_sha256": manifest["candidate_set_sha256"],
        "query_set_sha256": manifest["query_set_sha256"],
        "embedding_table_sha256": manifest["embedding_table_sha256"],
        "pack_root_sha256": manifest["pack_root_sha256"],
    }


def _load_unaccepted_feature_view(pack_dir: Path, *, expected_root: str) -> dict:
    """Build a detached learner view after trusted internal verification."""
    pack_dir = Path(pack_dir)
    if pack_dir.is_symlink():
        raise PackIntegrityError("pack path must not be a symlink")
    pack_dir = pack_dir.resolve()
    verify_pack(pack_dir, expected_root=expected_root)
    manifest = _load_manifest(pack_dir, expected_root)
    _validate_file_set(pack_dir, manifest)
    edges, queries, supervision = _load_sidecars(pack_dir, manifest)
    _validate_identities(manifest, edges, queries, supervision)
    arrays = _load_arrays(pack_dir, manifest)
    return {"schema": FEATURE_SCHEMA,
            "manifest": _public_manifest_projection(manifest),
            "edges": edges, "queries": queries, "arrays": arrays}


def _rank_arms(edge_ids: Sequence[str], labels: Sequence[str],
               base_no_seam: np.ndarray, base_merged: np.ndarray,
               query_i: int) -> dict[str, tuple[list[str], list[float]]]:
    idx_a = [i for i, label in enumerate(labels) if label == "A"]
    idx_b = [i for i, label in enumerate(labels) if label == "B"]
    arms = {}
    for name, row, indices in (
        ("a", base_no_seam[query_i], idx_a),
        ("b", base_no_seam[query_i], idx_b),
        ("merged", base_merged[query_i], None),
        ("no_seam", base_no_seam[query_i], None),
    ):
        order = _stable_order(edge_ids, row, indices)
        arms[name] = ([edge_ids[i] for i in order], [float(row[i]) for i in order])
    return arms


def _comparison_context(pack_dir: Path, verify_first: bool) -> tuple[dict, list[dict], list[dict], list[str], list[str], dict[str, np.ndarray]]:
    if verify_first:
        verify_pack(pack_dir)
    manifest = _load_manifest(pack_dir)
    edges, queries, supervision = _load_sidecars(pack_dir, manifest)
    edge_ids, labels = _validate_identities(manifest, edges, queries, supervision)
    arrays = _load_arrays(pack_dir, manifest)
    return manifest, edges, queries, edge_ids, labels, arrays


def compare_frozen_b2(pack_dir: Path, reference: dict, *,
                      tolerance: float = REPLAY_TOLERANCE,
                      verify_first: bool = True) -> dict:
    """Compare complete A/B/MERGED/NO_SEAM rankings with frozen row-wise B2."""
    _, _, queries, edge_ids, labels, arrays = _comparison_context(pack_dir, verify_first)
    records = reference.get("records") if isinstance(reference, dict) else None
    if not isinstance(records, list) or len(records) != len(queries):
        raise ReplayMismatch("frozen B2 row count mismatch")
    id_mismatches = 0
    qid_mismatches = 0
    max_error = 0.0
    comparisons = 0
    for query_i, (query, record) in enumerate(zip(queries, records)):
        if hashlib.sha256(str(record.get("qid", "")).encode("utf-8")).hexdigest() != query["qid_sha256"]:
            qid_mismatches += 1
        observed = _rank_arms(edge_ids, labels, arrays["base_no_seam"],
                              arrays["base_merged"], query_i)
        for arm in ("a", "b", "merged", "no_seam"):
            ref_arm = record.get("arms", {}).get(arm, {})
            ref_ids = ref_arm.get("ids")
            ref_scores = ref_arm.get("scores")
            ids, scores = observed[arm]
            if ref_ids != ids:
                id_mismatches += 1
            if not isinstance(ref_scores, list) or len(ref_scores) != len(scores):
                id_mismatches += 1
                continue
            if scores:
                reference_scores = np.asarray(ref_scores, dtype=np.float64)
                if not np.isfinite(reference_scores).all():
                    raise ReplayMismatch(f"frozen B2 contains non-finite scores: {arm}")
                max_error = max(max_error, float(np.max(np.abs(
                    np.asarray(scores) - reference_scores))))
                comparisons += len(scores)
    passed = id_mismatches == 0 and qid_mismatches == 0 and max_error <= tolerance
    if not passed:
        raise ReplayMismatch(
            f"frozen B2 mismatch: qids={qid_mismatches}, ids={id_mismatches}, error={max_error}"
        )
    return {"pass": True, "queries": len(queries), "arms": len(queries) * 4,
            "score_comparisons": comparisons, "qid_mismatches": qid_mismatches,
            "ranked_id_mismatches": id_mismatches,
            "max_abs_score_error": max_error, "tolerance": tolerance}


def compare_b21_scorepack(pack_dir: Path, scorepack: dict, *,
                          tolerance: float = REPLAY_TOLERANCE,
                          verify_first: bool = True) -> dict:
    """Compare the complete pack's prefixes with a pinned B2.1 top-k scorepack."""
    manifest, _, queries, edge_ids, labels, arrays = _comparison_context(pack_dir, verify_first)
    identity = manifest["identity"]
    for key, expected in (("schema", "hswm-b21-scorepack/v1"),
                          ("dataset", identity["dataset"]),
                          ("cohort", identity["cohort"]),
                          ("salt", identity["salt"]),
                          ("condition", identity["condition"]),
                          ("model", identity["model_id"]),
                          ("lam_v", LAM_V), ("lam_b", LAM_B),
                          ("n_queries", manifest["counts"]["queries"]),
                          ("n_paragraphs", manifest["counts"]["edges"])):
        if scorepack.get(key) != expected:
            raise ReplayMismatch(f"B2.1 scorepack identity mismatch: {key}")
    expected_edge_digest = hashlib.sha256(
        "\n".join(edge_ids).encode("utf-8")).hexdigest()
    if scorepack.get("edge_ids_sha256") != expected_edge_digest:
        raise ReplayMismatch("B2.1 scorepack edge-axis mismatch")
    scorepack_provenance = scorepack.get("provenance")
    if not isinstance(scorepack_provenance, dict):
        raise ReplayMismatch("B2.1 scorepack provenance missing")
    for key in ("dataset_sha256", "model_snapshot_sha256"):
        if scorepack_provenance.get(key) != manifest["provenance"][key]:
            raise ReplayMismatch(f"B2.1 scorepack provenance mismatch: {key}")
    producer_sha256 = manifest["provenance"]["producer_sha256"]
    expected_script_sha256 = producer_sha256.get("prom_b21_learned_router.py")
    if not _is_sha256(expected_script_sha256):
        raise ReplayMismatch(
            "B2.1 pack producer lineage lacks prom_b21_learned_router.py"
        )
    if scorepack_provenance.get("script_sha256") != expected_script_sha256:
        raise ReplayMismatch("B2.1 scorepack provenance mismatch: script_sha256")
    expected_frozen_modules: dict[str, str] = {}
    for name in B21_FROZEN_MODULES:
        digest = producer_sha256.get(name)
        if not _is_sha256(digest):
            raise ReplayMismatch(f"B2.1 pack producer lineage lacks frozen module: {name}")
        expected_frozen_modules[name] = digest
    if scorepack_provenance.get("frozen_modules_sha256") != expected_frozen_modules:
        raise ReplayMismatch(
            "B2.1 scorepack provenance mismatch: frozen_modules_sha256"
        )
    records = scorepack.get("records")
    if not isinstance(records, list) or len(records) != len(queries):
        raise ReplayMismatch("B2.1 scorepack row count mismatch")
    top_k = scorepack.get("top_k")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k != 20:
        raise ReplayMismatch("B2.1 continuity requires the pinned top_k=20")
    id_mismatches = 0
    qid_mismatches = 0
    max_error = 0.0
    comparisons = 0
    for query_i, (query, record) in enumerate(zip(queries, records)):
        if record.get("qid_sha256") != query["qid_sha256"]:
            qid_mismatches += 1
        if record.get("question_sha256") != query["question_sha256"]:
            qid_mismatches += 1
        observed = _rank_arms(edge_ids, labels, arrays["base_no_seam"],
                              arrays["base_merged"], query_i)
        for arm in ("a", "b", "merged", "no_seam"):
            ref = record.get("arms", {}).get(arm, {})
            ids, scores = observed[arm]
            if ref.get("ids") != ids[:top_k]:
                id_mismatches += 1
            ref_scores = ref.get("scores")
            if not isinstance(ref_scores, list) or len(ref_scores) != min(top_k, len(scores)):
                id_mismatches += 1
                continue
            if ref_scores:
                reference_scores = np.asarray(ref_scores, dtype=np.float64)
                if not np.isfinite(reference_scores).all():
                    raise ReplayMismatch(f"B2.1 scorepack contains non-finite scores: {arm}")
                max_error = max(max_error, float(np.max(np.abs(
                    np.asarray(scores[:top_k]) - reference_scores))))
                comparisons += len(ref_scores)
    passed = id_mismatches == 0 and qid_mismatches == 0 and max_error <= tolerance
    if not passed:
        raise ReplayMismatch(
            f"B2.1 continuity mismatch: qids={qid_mismatches}, ids={id_mismatches}, error={max_error}"
        )
    return {"pass": True, "queries": len(queries), "top_k": top_k,
            "score_comparisons": comparisons, "qid_mismatches": qid_mismatches,
            "ranked_id_mismatches": id_mismatches,
            "max_abs_score_error": max_error, "tolerance": tolerance}


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=HERE,
                                       text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


class SentenceEmbedder:
    """Runtime-only cached sentence-transformer adapter."""

    def __init__(self, model_path: str, *, device: str, batch_size: int) -> None:
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_path, device=device)
        self.batch_size = batch_size
        self.cache: dict[str, np.ndarray] = {}

    def __call__(self, texts: list[str]) -> np.ndarray:
        missing = [text for text in texts if text not in self.cache]
        if missing:
            vectors = self.model.encode(
                missing, normalize_embeddings=True, convert_to_numpy=True,
                batch_size=self.batch_size, show_progress_bar=False,
            )
            for text, vector in zip(missing, vectors):
                self.cache[text] = np.asarray(vector, dtype=np.float64)
        return np.vstack([self.cache[text] for text in texts])


def _select_cohort(raw: object, dataset: str, cohort: str) -> tuple[list[dict], Sequence[Query], Mapping[str, Paragraph]]:
    rows = raw.get("rows") if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        raise PackIntegrityError("dataset must be a row list or {'rows': [...]} object")
    if cohort == "b2_reproduction400":
        if dataset != "2wiki":
            raise PackIntegrityError("b2_reproduction400 is defined only for 2wiki")
        from prom_b2_crossfield_merge import stratify
        usable_rows = [row for row in rows if stratify(row) is not None]
        order = list(range(len(usable_rows)))
        import random
        random.Random(B2_SEED).shuffle(order)
        if len(order) < 400:
            raise PackIntegrityError("fewer than 400 usable B2 rows")
        selected = [usable_rows[index] for index in order[:400]]
        queries, pool = normalize_rows(selected, dataset)
        return selected, queries, pool
    if cohort == "full_closed_corpus":
        queries, pool = normalize_rows(raw, dataset)
        return rows, queries, pool
    raise PackIntegrityError(f"unknown cohort: {cohort}")


def _raw_rows(raw: object, label: str) -> list[dict]:
    rows = raw.get("rows") if isinstance(raw, dict) else raw
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise PackIntegrityError(f"{label} must contain a row-object list")
    return rows


def _b21_reproduction_view(
    raw_2wiki: object,
    *,
    query_count: int | None = None,
) -> tuple[Sequence[Query], Mapping[str, Paragraph]]:
    """Reconstruct the exact B2.1 r1 reproduction request, including row order."""
    import random

    all_queries, _ = normalize_rows(raw_2wiki, "2wiki")
    source_rows = _raw_rows(raw_2wiki, "B2.1 history 2Wiki source")
    count = (ACCEPTANCE_ROLES["b2_reproduction400"]["queries"]
             if query_count is None else query_count)
    order = list(range(len(all_queries)))
    random.Random(B2_SEED).shuffle(order)
    if len(order) < count:
        raise PackIntegrityError(
            f"B2.1 history source has fewer than {count} usable 2Wiki queries"
        )
    selected = [source_rows[index] for index in order[:count]]
    return normalize_rows(selected, "2wiki")


def _b21_requested_texts(
    queries: Sequence[Query],
    pool: Mapping[str, Paragraph],
    *,
    private_entities: bool,
) -> tuple[str, ...]:
    """Mirror B2.1's sorted unique encoder request without computing scores."""
    edge_ids = sorted(pool)
    if private_entities:
        edge_texts = [
            privatize_text(
                finding_text(pool[edge_id].title, pool[edge_id].body),
                pool[edge_id].entities,
            )
            for edge_id in edge_ids
        ]
        vertex_texts = [
            opaque_entity(entity)
            for entity in sorted({entity for edge_id in edge_ids
                                  for entity in pool[edge_id].entities})
        ]
        query_texts = [
            privatize_text(query.question, base_entities(query.question))
            for query in queries
        ]
    else:
        edge_texts = [
            finding_text(pool[edge_id].title, pool[edge_id].body)
            for edge_id in edge_ids
        ]
        vertex_texts = sorted({entity for edge_id in edge_ids
                               for entity in pool[edge_id].entities})
        query_texts = [query.question for query in queries]
    return tuple(sorted(set(edge_texts) | set(vertex_texts) | set(query_texts)))


def _embedding_cache_plan(
    role: str,
    *,
    target_raw: object,
    two_wiki_raw: object,
    reproduction_queries: int | None = None,
) -> dict:
    if role not in EXPECTED_B21_CACHE_HISTORY:
        raise PackIntegrityError(f"unknown B2.1 cache-history role: {role}")
    repro_queries, repro_pool = _b21_reproduction_view(
        two_wiki_raw, query_count=reproduction_queries)
    full_queries, full_pool = normalize_rows(two_wiki_raw, "2wiki")
    repro_base = _b21_requested_texts(
        repro_queries, repro_pool, private_entities=False)
    full_base = _b21_requested_texts(
        full_queries, full_pool, private_entities=False)
    full_private = _b21_requested_texts(
        full_queries, full_pool, private_entities=True)
    steps = {
        "2wiki/b2_reproduction400/base/legacy": repro_base,
        "2wiki/b2_reproduction400/frozen_reference": repro_base,
        "2wiki/full_closed_corpus/base/legacy": full_base,
        "2wiki/full_closed_corpus/base/b21-field-v1": full_base,
        "2wiki/full_closed_corpus/base/b21-field-v2": full_base,
        "2wiki/full_closed_corpus/private_entity/legacy": full_private,
    }
    if role == "b2_reproduction400":
        target_name = "2wiki/b2_reproduction400/base/legacy"
        target_texts = repro_base
    elif role == "2wiki_full_closed_corpus":
        target_name = "2wiki/full_closed_corpus/base/legacy"
        target_texts = full_base
    else:
        target_queries, target_pool = normalize_rows(target_raw, "musique")
        target_name = "musique/full_closed_corpus/base/legacy"
        target_texts = _b21_requested_texts(
            target_queries, target_pool, private_entities=False)
    return {
        "prewarm": tuple(
            (name, steps[name]) for name in EXPECTED_B21_CACHE_HISTORY[role]
        ),
        "target": (target_name, target_texts),
    }


def _text_sequence_sha256(texts: Sequence[str]) -> str:
    return _json_sha256([
        hashlib.sha256(text.encode("utf-8")).hexdigest() for text in texts
    ])


def _trace_cache_step(name: str, texts: Sequence[str], cache: set[str]) -> dict:
    requested = tuple(texts)
    missing = tuple(text for text in requested if text not in cache)
    cache.update(missing)
    return {
        "name": name,
        "requested_count": len(requested),
        "requested_sha256": _text_sequence_sha256(requested),
        "missing_count": len(missing),
        "missing_sha256": _text_sequence_sha256(missing),
        "cache_after_count": len(cache),
        "cache_after_sha256": _text_sequence_sha256(tuple(sorted(cache))),
    }


class _ObservedEmbeddingSchedule:
    """Record only calls that actually execute in the sealed B2.1 prefix."""

    def __init__(self, embedder: Callable[[list[str]], Sequence[Sequence[float]]]) -> None:
        self._embedder = embedder
        self._logical_cache: set[str] = set()
        self._steps: list[dict] = []

    def encode(self, name: str, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        next_cache = set(self._logical_cache)
        step = _trace_cache_step(name, texts, next_cache)
        values = self._embedder(list(texts))
        self._logical_cache = next_cache
        self._steps.append(step)
        return values

    @property
    def steps(self) -> tuple[dict, ...]:
        return tuple(dict(step) for step in self._steps)


def _make_embedding_cache_history(
    role: str,
    *,
    target_raw: object,
    two_wiki_raw: object,
    two_wiki_path: Path,
    two_wiki_sha256: str,
    model_snapshot_sha256: str,
    target_embedding_table_sha256: str,
    device: str,
    batch_size: int,
    reproduction_queries: int | None = None,
    observed_steps: Sequence[Mapping[str, object]] | None = None,
) -> dict:
    plan = _embedding_cache_plan(
        role, target_raw=target_raw, two_wiki_raw=two_wiki_raw,
        reproduction_queries=reproduction_queries)
    logical_cache: set[str] = set()
    prewarm_steps = [
        _trace_cache_step(name, texts, logical_cache)
        for name, texts in plan["prewarm"]
    ]
    target_name, target_texts = plan["target"]
    target_step = _trace_cache_step(target_name, target_texts, logical_cache)
    expected_steps = [*prewarm_steps, target_step]
    if observed_steps is not None and list(observed_steps) != expected_steps:
        raise ReplayMismatch(
            "observed embedding calls differ from the exact B2.1 prefix")
    core = {
        "schema": CACHE_HISTORY_SCHEMA,
        "profile": CACHE_HISTORY_PROFILE,
        "scope": CACHE_HISTORY_SCOPE,
        "role": role,
        "encoder": {
            "batch_size": batch_size,
            "device": device,
            "normalize_embeddings": True,
            "model_snapshot_sha256": model_snapshot_sha256,
        },
        "two_wiki_source": {
            "path": str(Path(two_wiki_path).absolute()),
            "sha256": two_wiki_sha256,
        },
        "prewarm_steps": prewarm_steps,
        "target_step": target_step,
        "target_embedding_binding": {
            "sha256": target_embedding_table_sha256,
            "scope": "producer_attested_manifest_binding",
            "model_free_rederived": False,
        },
    }
    return {**core, "history_sha256": _json_sha256(core)}


def _execute_embedding_cache_prewarm(
    embedder: Callable[[list[str]], Sequence[Sequence[float]]],
    plan: Mapping[str, object],
) -> _ObservedEmbeddingSchedule:
    observed = _ObservedEmbeddingSchedule(embedder)
    for name, texts in plan["prewarm"]:
        observed.encode(name, texts)
    return observed


def _producer_hashes() -> dict[str, str]:
    names = (
        "hswm_b22_gate0_harness.py", "prom_b2_crossfield_merge.py",
        "prom_b21_learned_router.py", "hswm_bond_readout.py",
        "hswm_open_composition.py", "hswm_field_algebra.py",
        "hswm_hypergraph.py", "hswm_hypergraph_readout.py",
    )
    return {name: sha256_file(HERE / name) for name in names}


def _write_receipt(path: Path, receipt: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical_bytes(receipt)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as exc:
        raise PackIntegrityError(f"refusing to replace receipt: {path}") from exc
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def _gzip_payload_sha256(path: Path) -> str:
    try:
        with gzip.open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except (OSError, EOFError) as exc:
        raise PackIntegrityError(f"cannot read B2.1 gzip payload: {path}") from exc


def _write_frozen_reference(path: Path, value: dict) -> dict:
    """Write a deterministic, exclusive gzip containing the full frozen-B2 replay."""
    path = Path(path).absolute()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical_bytes(value)
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", fileobj=buffer, mode="wb", mtime=0) as handle:
        handle.write(payload)
    compressed = buffer.getvalue()
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as exc:
        raise PackIntegrityError(f"refusing to replace frozen B2 reference: {path}") from exc
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(compressed)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise
    return {"path": str(path), "sha256": hashlib.sha256(compressed).hexdigest(),
            "payload_sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(compressed)}


def _read_frozen_reference(path: Path) -> tuple[dict, str]:
    path = Path(path)
    try:
        with gzip.open(path, "rb") as handle:
            payload = handle.read()
        value = json.loads(payload.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except PackIntegrityError:
        raise
    except (OSError, EOFError, UnicodeError, json.JSONDecodeError) as exc:
        raise PackIntegrityError(f"invalid frozen B2 reference: {path}") from exc
    if not isinstance(value, dict):
        raise PackIntegrityError("frozen B2 reference must be an object")
    return value, hashlib.sha256(payload).hexdigest()


def _validate_replay_block(value: object, label: str, *, expected_queries: int,
                           expected_comparisons: int,
                           expected_arms: int | None = None) -> dict:
    if not isinstance(value, dict) or value.get("pass") is not True:
        raise ReplayMismatch(f"{label} is absent or did not pass")
    for key in ("qid_mismatches", "ranked_id_mismatches"):
        if value.get(key) != 0:
            raise ReplayMismatch(f"{label} reports {key}")
    error = value.get("max_abs_score_error")
    if isinstance(error, bool) or not isinstance(error, (int, float)):
        raise ReplayMismatch(f"{label} has invalid score error")
    if not np.isfinite(float(error)) or float(error) > REPLAY_TOLERANCE:
        raise ReplayMismatch(f"{label} score error exceeds tolerance")
    if value.get("queries") != expected_queries:
        raise ReplayMismatch(f"{label} query count mismatch")
    if value.get("score_comparisons") != expected_comparisons:
        raise ReplayMismatch(f"{label} comparison count mismatch")
    if expected_arms is not None and value.get("arms") != expected_arms:
        raise ReplayMismatch(f"{label} arm count mismatch")
    return value


def _read_compile_receipt(path: Path) -> dict:
    value = _read_json(path)
    if not isinstance(value, dict):
        raise PackIntegrityError("compile receipt must be an object")
    return value


def _pack_semantic_sha256(pack_path: Path, manifest: dict) -> str:
    edges, queries, supervision = _load_sidecars(pack_path, manifest)
    arrays = _load_arrays(pack_path, manifest)
    seed = {key: value for key, value in manifest.items()
            if key not in {"files", "pack_root_sha256"}}
    compiled = CompiledGate0Pack(
        manifest_seed=seed, edges=tuple(edges), queries=tuple(queries),
        supervision=tuple(supervision), arrays=arrays)
    return _compiled_semantic_sha256(compiled)


def _validate_embedding_cache_history(
    receipt: Mapping[str, object],
    manifest: Mapping[str, object],
    role: str,
    inputs: Mapping[str, object],
) -> dict:
    history = receipt.get("embedding_cache_history")
    if not isinstance(history, dict):
        raise PackIntegrityError("compile receipt lacks embedding cache history")
    _strict_keys(history, {
        "schema", "profile", "scope", "role", "encoder", "two_wiki_source",
        "prewarm_steps", "target_step", "target_embedding_binding",
        "history_sha256",
    }, "embedding cache history")
    if (history["schema"] != CACHE_HISTORY_SCHEMA
            or history["profile"] != CACHE_HISTORY_PROFILE
            or history["scope"] != CACHE_HISTORY_SCOPE
            or history["role"] != role):
        raise PackIntegrityError("embedding cache history profile/role mismatch")
    encoder = history["encoder"]
    if not isinstance(encoder, dict):
        raise PackIntegrityError("embedding cache history encoder is missing")
    _strict_keys(encoder, {
        "batch_size", "device", "normalize_embeddings",
        "model_snapshot_sha256",
    }, "embedding cache history encoder")
    if encoder != {
        "batch_size": 128,
        "device": "cuda",
        "normalize_embeddings": True,
        "model_snapshot_sha256": manifest["provenance"]["model_snapshot_sha256"],
    }:
        raise PackIntegrityError("embedding cache history encoder contract mismatch")
    source = history["two_wiki_source"]
    if not isinstance(source, dict):
        raise PackIntegrityError("embedding cache history 2Wiki source is missing")
    _strict_keys(source, {"path", "sha256"}, "embedding cache history 2Wiki source")
    source_path = _require_path(source["path"], "embedding cache history 2Wiki path")
    if not source_path.is_absolute() or not _is_sha256(source["sha256"]):
        raise PackIntegrityError("embedding cache history 2Wiki source is not pinned")
    if not source_path.is_file() or sha256_file(source_path) != source["sha256"]:
        raise PackIntegrityError("embedding cache history 2Wiki source bytes differ")
    if (role in {"b2_reproduction400", "2wiki_full_closed_corpus"}
            and source["sha256"] != inputs["data_sha256"]):
        raise PackIntegrityError("2Wiki target/history source hashes differ")
    target_binding = history["target_embedding_binding"]
    if not isinstance(target_binding, dict):
        raise PackIntegrityError("target embedding binding is missing")
    _strict_keys(target_binding, {
        "sha256", "scope", "model_free_rederived",
    }, "target embedding binding")
    if target_binding != {
        "sha256": manifest["embedding_table_sha256"],
        "scope": "producer_attested_manifest_binding",
        "model_free_rederived": False,
    }:
        raise PackIntegrityError("target embedding binding contract mismatch")
    target_path = _require_path(inputs["data"], "compile receipt dataset path")
    expected = _make_embedding_cache_history(
        role,
        target_raw=_read_json(target_path),
        two_wiki_raw=_read_json(source_path),
        two_wiki_path=source_path,
        two_wiki_sha256=source["sha256"],
        model_snapshot_sha256=manifest["provenance"]["model_snapshot_sha256"],
        target_embedding_table_sha256=manifest["embedding_table_sha256"],
        device="cuda",
        batch_size=128,
    )
    if history != expected:
        raise PackIntegrityError("embedding cache history differs from reconstructed plan")
    return history


def _cache_history_lock_summary(history: Mapping[str, object]) -> dict:
    return {
        "profile": history["profile"],
        "scope": history["scope"],
        "history_sha256": history["history_sha256"],
        "two_wiki_source_sha256": history["two_wiki_source"]["sha256"],
        "prewarm_step_names": [step["name"] for step in history["prewarm_steps"]],
        "target_step_name": history["target_step"]["name"],
        "target_embedding_binding": history["target_embedding_binding"],
    }


def _validate_compile_receipt(receipt: dict, manifest: dict, role: str,
                              pack_path: Path) -> tuple[dict, dict]:
    if (receipt.get("schema") != RECEIPT_SCHEMA
            or receipt.get("status") != "PACK_SELF_CHECK_PASS"
            or receipt.get("pass") is not True
            or receipt.get("learner_allowed") is not False
            or receipt.get("scientific_claim_allowed") is not False):
        raise PackIntegrityError("compile receipt is not a bounded self-check PASS")
    for key in ("pack_root_sha256", "candidate_set_sha256", "query_set_sha256",
                "counts"):
        expected = (manifest["pack_root_sha256"] if key == "pack_root_sha256"
                    else manifest[key])
        if receipt.get(key) != expected:
            raise PackIntegrityError(f"compile receipt mismatch: {key}")
    neutral = receipt.get("neutral_replay")
    component = receipt.get("component_replay")
    if (not isinstance(neutral, dict) or neutral.get("pass") is not True
            or neutral.get("ranking_mismatches") != 0):
        raise ReplayMismatch("compile receipt neutral replay is incomplete")
    neutral_error = neutral.get("max_abs_score_error")
    if (isinstance(neutral_error, bool)
            or not isinstance(neutral_error, (int, float))
            or not np.isfinite(float(neutral_error))
            or float(neutral_error) > REPLAY_TOLERANCE):
        raise ReplayMismatch("compile receipt neutral replay error is invalid")
    if not isinstance(component, dict) or component.get("pass") is not True:
        raise ReplayMismatch("compile receipt component replay is incomplete")
    for key in ("max_abs_no_seam_error", "max_abs_merged_error"):
        error = component.get(key)
        if (isinstance(error, bool) or not isinstance(error, (int, float))
                or not np.isfinite(float(error))
                or float(error) > COMPONENT_TOLERANCE):
            raise ReplayMismatch(f"compile receipt component error is invalid: {key}")
    determinism = receipt.get("determinism_replay")
    if (not isinstance(determinism, dict) or determinism.get("pass") is not True
            or determinism.get("same_embedding_table") is not True
            or not _is_sha256(determinism.get("primary_semantic_sha256"))
            or determinism.get("primary_semantic_sha256")
            != determinism.get("repeated_semantic_sha256")
            or determinism.get("primary_semantic_sha256")
            != _pack_semantic_sha256(pack_path, manifest)):
        raise ReplayMismatch("same-embedding-table determinism replay is invalid")
    inputs = receipt.get("inputs")
    expected_input_keys = {
        "data", "data_sha256", "model", "model_snapshot_sha256",
        "producer_sha256", "b21_scorepack", "b21_scorepack_sha256",
        "b21_payload_sha256", "frozen_b2_reference",
        "frozen_b2_reference_sha256", "frozen_b2_payload_sha256",
    }
    if not isinstance(inputs, dict):
        raise PackIntegrityError("compile receipt inputs are missing")
    _strict_keys(inputs, expected_input_keys, "compile receipt inputs")
    provenance = manifest["provenance"]
    if (inputs["data_sha256"] != provenance["dataset_sha256"]
            or inputs["model_snapshot_sha256"] != provenance["model_snapshot_sha256"]
            or inputs["producer_sha256"] != provenance["producer_sha256"]):
        raise PackIntegrityError("compile receipt provenance differs from pack")
    for key in ("b21_scorepack_sha256", "b21_payload_sha256"):
        if not _is_sha256(inputs.get(key)):
            raise PackIntegrityError(f"compile receipt lacks pinned {key}")
    data_path = _require_path(inputs["data"], "compile receipt dataset path")
    model_path = _require_path(inputs["model"], "compile receipt model path")
    b21_path = _require_path(
        inputs["b21_scorepack"], "compile receipt B2.1 path")
    if (not data_path.is_file() or sha256_file(data_path) != inputs["data_sha256"]):
        raise PackIntegrityError("dataset bytes differ from compile receipt")
    if (_strict_model_manifest(model_path)["sha256"]
            != inputs["model_snapshot_sha256"]):
        raise PackIntegrityError("model snapshot differs from compile receipt")
    if (not b21_path.is_file()
            or sha256_file(b21_path) != inputs["b21_scorepack_sha256"]
            or _gzip_payload_sha256(b21_path) != inputs["b21_payload_sha256"]):
        raise PackIntegrityError("B2.1 reference bytes differ from compile receipt")
    if inputs["producer_sha256"] != _producer_hashes():
        raise PackIntegrityError("producer source differs from compile receipt")
    cache_history = _validate_embedding_cache_history(
        receipt, manifest, role, inputs)
    edges, _, _ = _load_sidecars(pack_path, manifest)
    field_a = sum(record["field_label"] == "A" for record in edges)
    field_b = len(edges) - field_a
    queries_count = manifest["counts"]["queries"]
    edges_count = manifest["counts"]["edges"]
    b21_comparisons = queries_count * (
        min(20, field_a) + min(20, field_b) + 2 * min(20, edges_count))
    observed_b21 = compare_b21_scorepack(
        pack_path, read_scorepack(b21_path), verify_first=False)
    _validate_replay_block(
        observed_b21, "B2.1 continuity", expected_queries=queries_count,
        expected_comparisons=b21_comparisons)
    if receipt.get("b21_topk_continuity") != observed_b21:
        raise ReplayMismatch("compile receipt B2.1 summary differs from direct replay")
    if ACCEPTANCE_ROLES[role]["requires_frozen_b2"]:
        for key in ("frozen_b2_reference_sha256", "frozen_b2_payload_sha256"):
            if not _is_sha256(inputs.get(key)):
                raise PackIntegrityError(f"compile receipt lacks pinned {key}")
        reference_path = _require_path(
            inputs["frozen_b2_reference"],
            "compile receipt frozen B2 reference path",
        )
        if (not reference_path.is_file()
                or sha256_file(reference_path) != inputs["frozen_b2_reference_sha256"]):
            raise PackIntegrityError("frozen B2 reference bytes differ from compile receipt")
        reference, payload_sha = _read_frozen_reference(reference_path)
        if payload_sha != inputs["frozen_b2_payload_sha256"]:
            raise PackIntegrityError("frozen B2 reference payload differs from compile receipt")
        observed_frozen = compare_frozen_b2(pack_path, reference, verify_first=False)
        _validate_replay_block(
            observed_frozen, "frozen B2 replay", expected_queries=queries_count,
            expected_comparisons=queries_count * 3 * edges_count,
            expected_arms=queries_count * 4)
        if receipt.get("frozen_b2_replay") != observed_frozen:
            raise ReplayMismatch("compile receipt frozen-B2 summary differs from direct replay")
    elif any(inputs.get(key) is not None for key in (
            "frozen_b2_reference", "frozen_b2_reference_sha256",
            "frozen_b2_payload_sha256")):
        raise PackIntegrityError("full-corpus role unexpectedly carries frozen-B2 reference")
    return inputs, cache_history


def _build_lock_entry(role: str, pack_path: Path, receipt_path: Path) -> dict:
    if role not in ACCEPTANCE_ROLES:
        raise PackIntegrityError(f"unknown acceptance role: {role}")
    pack_path = Path(pack_path).absolute()
    receipt_path = Path(receipt_path).absolute()
    receipt = _read_compile_receipt(receipt_path)
    root = receipt.get("pack_root_sha256")
    if not _is_sha256(root):
        raise PackIntegrityError("compile receipt lacks a valid pack root")
    verify_pack(pack_path, expected_root=root)
    manifest = _load_manifest(pack_path, expected_root=root)
    expected_identity = ACCEPTANCE_ROLES[role]
    for key in ("dataset", "cohort"):
        if manifest["identity"].get(key) != expected_identity[key]:
            raise PackIntegrityError(f"acceptance role identity mismatch: {role}/{key}")
    if manifest["identity"].get("condition") != "base" or manifest["identity"].get("salt") != "legacy":
        raise PackIntegrityError("Gate-0 acceptance requires base/legacy")
    for key in ("queries", "edges"):
        if manifest["counts"].get(key) != expected_identity[key]:
            raise PackIntegrityError(f"acceptance role count mismatch: {role}/{key}")
    inputs, cache_history = _validate_compile_receipt(
        receipt, manifest, role, pack_path)
    return {
        "role": role,
        "pack_path": str(pack_path),
        "compile_receipt_path": str(receipt_path),
        "compile_receipt_sha256": sha256_file(receipt_path),
        "pack_root_sha256": root,
        "identity": manifest["identity"],
        "counts": manifest["counts"],
        "candidate_set_sha256": manifest["candidate_set_sha256"],
        "query_set_sha256": manifest["query_set_sha256"],
        "provenance": manifest["provenance"],
        "embedding_cache_history": _cache_history_lock_summary(cache_history),
        "b21_reference": {
            "gzip_sha256": inputs["b21_scorepack_sha256"],
            "payload_sha256": inputs["b21_payload_sha256"],
        },
        "frozen_b2_reference": ({
            "gzip_sha256": inputs["frozen_b2_reference_sha256"],
            "payload_sha256": inputs["frozen_b2_payload_sha256"],
        } if ACCEPTANCE_ROLES[role]["requires_frozen_b2"] else None),
    }


def create_acceptance_lock(role_paths: Mapping[str, tuple[Path, Path]], output: Path) -> dict:
    """Freeze three already self-checked packs before the acceptance pass."""
    if set(role_paths) != set(ACCEPTANCE_ROLES):
        raise PackIntegrityError("acceptance lock requires all three Gate-0 roles")
    pack_paths: dict[str, Path] = {}
    for role, paths in role_paths.items():
        if not isinstance(paths, (tuple, list)) or len(paths) != 2:
            raise PackIntegrityError(f"acceptance role paths are invalid: {role}")
        try:
            pack_paths[role] = Path(paths[0]).absolute()
        except TypeError as exc:
            raise PackIntegrityError(
                f"acceptance pack path is invalid: {role}"
            ) from exc
    output = _reject_output_inside_packs(output, pack_paths)
    entries = {role: _build_lock_entry(role, *role_paths[role])
               for role in sorted(role_paths)}
    _validate_cross_role_entries(entries)
    lock = {
        "schema": LOCK_SCHEMA,
        "status": "FROZEN_FOR_ACCEPTANCE",
        "created_at": _utc_now(),
        "entries": entries,
        "claim_boundary": {
            "engineering_gate_only": True,
            "scientific_claim_allowed": False,
            "learner_allowed": False,
        },
    }
    _write_receipt(output, lock)
    return lock


def _validate_cross_role_entries(entries: Mapping[str, dict]) -> None:
    """Reject a bundle assembled from mutually stale datasets/models/producers."""
    if set(entries) != set(ACCEPTANCE_ROLES):
        raise PackIntegrityError("cross-role validation requires all Gate-0 roles")
    reproduction = entries["b2_reproduction400"]
    two_wiki = entries["2wiki_full_closed_corpus"]
    musique = entries["musique_full_closed_corpus"]
    if (reproduction["provenance"]["dataset_sha256"]
            != two_wiki["provenance"]["dataset_sha256"]):
        raise PackIntegrityError("2Wiki reproduction/full dataset hashes differ")
    model_hashes = {entry["provenance"]["model_snapshot_sha256"]
                    for entry in entries.values()}
    model_ids = {entry["identity"]["model_id"] for entry in entries.values()}
    producer_sets = {_json_sha256(entry["provenance"]["producer_sha256"])
                     for entry in entries.values()}
    if len(model_hashes) != 1 or len(model_ids) != 1:
        raise PackIntegrityError("Gate-0 roles do not share one frozen model")
    if len(producer_sets) != 1:
        raise PackIntegrityError("Gate-0 roles do not share one producer set")
    histories = [entry["embedding_cache_history"] for entry in entries.values()]
    if {history["profile"] for history in histories} != {CACHE_HISTORY_PROFILE}:
        raise PackIntegrityError("Gate-0 roles do not share the exact B2.1 cache profile")
    if {history["scope"] for history in histories} != {CACHE_HISTORY_SCOPE}:
        raise PackIntegrityError("Gate-0 roles do not share one cache-prefix scope")
    history_sources = {history["two_wiki_source_sha256"] for history in histories}
    if history_sources != {reproduction["provenance"]["dataset_sha256"]}:
        raise PackIntegrityError("Gate-0 cache histories do not share the pinned 2Wiki source")


def _validate_acceptance_lock(
    path: Path,
    *,
    prospective_output: Path | None = None,
) -> tuple[dict, dict[str, dict]]:
    path = Path(path).absolute()
    lock = _read_json(path)
    if not isinstance(lock, dict):
        raise PackIntegrityError("acceptance lock must be an object")
    _strict_keys(lock, {"schema", "status", "created_at", "entries", "claim_boundary"},
                 "acceptance lock")
    if lock["schema"] != LOCK_SCHEMA or lock["status"] != "FROZEN_FOR_ACCEPTANCE":
        raise PackIntegrityError("wrong acceptance lock schema/status")
    _require_utc_timestamp(lock["created_at"], "acceptance lock created_at")
    if lock["claim_boundary"] != {
        "engineering_gate_only": True,
        "scientific_claim_allowed": False,
        "learner_allowed": False,
    }:
        raise PackIntegrityError("acceptance lock claim boundary drift")
    entries = lock["entries"]
    if not isinstance(entries, dict) or set(entries) != set(ACCEPTANCE_ROLES):
        raise PackIntegrityError("acceptance lock role set mismatch")
    if prospective_output is not None:
        preview_paths: dict[str, Path] = {}
        for role, entry in entries.items():
            if not isinstance(entry, dict):
                raise PackIntegrityError(
                    f"acceptance lock entry is invalid: {role}")
            preview_paths[role] = _require_path(
                entry.get("pack_path"), f"acceptance lock pack path {role}"
            ).absolute()
        _reject_output_inside_packs(prospective_output, preview_paths)
    current: dict[str, dict] = {}
    for role in sorted(entries):
        entry = entries[role]
        if not isinstance(entry, dict):
            raise PackIntegrityError(f"acceptance lock entry is invalid: {role}")
        expected_keys = {
            "role", "pack_path", "compile_receipt_path", "compile_receipt_sha256",
            "pack_root_sha256", "identity", "counts", "candidate_set_sha256",
            "query_set_sha256", "provenance", "b21_reference",
            "frozen_b2_reference", "embedding_cache_history",
        }
        _strict_keys(entry, expected_keys, f"acceptance lock entry {role}")
        if (not _is_sha256(entry["compile_receipt_sha256"])
                or sha256_file(Path(entry["compile_receipt_path"]))
                != entry["compile_receipt_sha256"]):
            raise PackIntegrityError(f"compile receipt changed after lock: {role}")
        observed = _build_lock_entry(
            role, Path(entry["pack_path"]), Path(entry["compile_receipt_path"]))
        if observed != entry:
            raise PackIntegrityError(f"pack/receipt differs from acceptance lock: {role}")
        current[role] = observed
    _validate_cross_role_entries(current)
    return lock, current


def _accepted_entries(entries: Mapping[str, dict]) -> dict[str, dict]:
    accepted: dict[str, dict] = {}
    for role, entry in sorted(entries.items()):
        compile_receipt = _read_compile_receipt(Path(entry["compile_receipt_path"]))
        accepted[role] = {
            "pack_root_sha256": entry["pack_root_sha256"],
            "identity": entry["identity"],
            "counts": entry["counts"],
            "candidate_set_sha256": entry["candidate_set_sha256"],
            "query_set_sha256": entry["query_set_sha256"],
            "embedding_cache_history": entry["embedding_cache_history"],
            "determinism_replay": compile_receipt["determinism_replay"],
            "b21_topk_continuity": compile_receipt["b21_topk_continuity"],
            "frozen_b2_replay": compile_receipt.get("frozen_b2_replay"),
        }
    return accepted


def accept_gate0_bundle(lock_path: Path, output: Path) -> dict:
    """Accept the locked three-pack bundle; this is the sole learner unlock."""
    lock_path = Path(lock_path).absolute()
    output = Path(output).absolute()
    _, entries = _validate_acceptance_lock(
        lock_path, prospective_output=output)
    accepted_entries = _accepted_entries(entries)
    receipt = {
        "schema": ACCEPTANCE_SCHEMA,
        "status": "GATE0_ACCEPTED",
        "pass": True,
        "engineering_gate_only": True,
        "scientific_claim_allowed": False,
        "learner_allowed": True,
        "accepted_at": _utc_now(),
        "lock_path": str(lock_path),
        "lock_sha256": sha256_file(lock_path),
        "entries": accepted_entries,
        "claim_boundary": ACCEPTANCE_CLAIM_BOUNDARY,
    }
    _write_receipt(output, receipt)
    return receipt


def _load_acceptance_receipt(path: Path) -> dict:
    path = Path(path).absolute()
    value = _read_json(path)
    if not isinstance(value, dict):
        raise PackIntegrityError("acceptance receipt must be an object")
    expected = {
        "schema", "status", "pass", "engineering_gate_only",
        "scientific_claim_allowed", "learner_allowed", "accepted_at", "lock_path",
        "lock_sha256", "entries", "claim_boundary",
    }
    _strict_keys(value, expected, "acceptance receipt")
    if (value["schema"] != ACCEPTANCE_SCHEMA or value["status"] != "GATE0_ACCEPTED"
            or value["pass"] is not True or value["engineering_gate_only"] is not True
            or value["scientific_claim_allowed"] is not False
            or value["learner_allowed"] is not True
            or not _is_sha256(value["lock_sha256"])):
        raise PackIntegrityError("acceptance receipt does not authorize learner access")
    _require_utc_timestamp(value["accepted_at"], "acceptance receipt accepted_at")
    if value["claim_boundary"] != ACCEPTANCE_CLAIM_BOUNDARY:
        raise PackIntegrityError("acceptance receipt claim boundary drift")
    if not isinstance(value["entries"], dict) or set(value["entries"]) != set(ACCEPTANCE_ROLES):
        raise PackIntegrityError("acceptance receipt role set mismatch")
    lock_path = Path(value["lock_path"]).absolute()
    if (not lock_path.is_file() or sha256_file(lock_path) != value["lock_sha256"]):
        raise PackIntegrityError("acceptance lock is missing or changed")
    _, locked_entries = _validate_acceptance_lock(lock_path)
    if value["entries"] != _accepted_entries(locked_entries):
        raise PackIntegrityError("acceptance receipt differs from reconstructed lock")
    return value


def load_feature_view(pack_dir: Path, *, acceptance_receipt: Path, role: str) -> dict:
    """Load a learner view only from a root pinned by a Gate-0 acceptance receipt."""
    if role not in ACCEPTANCE_ROLES:
        raise PackIntegrityError(f"unknown accepted feature role: {role}")
    acceptance = _load_acceptance_receipt(acceptance_receipt)
    entry = acceptance["entries"].get(role)
    if not isinstance(entry, dict) or not _is_sha256(entry.get("pack_root_sha256")):
        raise PackIntegrityError(f"acceptance receipt lacks role root: {role}")
    root = entry["pack_root_sha256"]
    view = _load_unaccepted_feature_view(pack_dir, expected_root=root)
    manifest = view["manifest"]
    for key in ("identity", "counts", "candidate_set_sha256", "query_set_sha256"):
        if manifest[key] != entry.get(key):
            raise PackIntegrityError(f"accepted feature identity mismatch: {role}/{key}")
    view["acceptance"] = {
        "role": role,
        "receipt_sha256": sha256_file(Path(acceptance_receipt)),
        "pack_root_sha256": root,
    }
    return view


def _compile_role(dataset: str, cohort: str) -> str:
    matches = [
        role for role, contract in ACCEPTANCE_ROLES.items()
        if contract["dataset"] == dataset and contract["cohort"] == cohort
    ]
    if len(matches) != 1:
        raise PackIntegrityError(
            f"dataset/cohort is not a Gate-0 acceptance role: {dataset}/{cohort}")
    return matches[0]


def _compile_cli(args: argparse.Namespace) -> int:
    started_at = _utc_now()
    data_path = Path(args.data).resolve()
    role = _compile_role(args.dataset, args.cohort)
    if args.salt != "legacy":
        raise PackIntegrityError("Gate-0 acceptance compilation requires salt=legacy")
    if args.device != "cuda" or args.batch_size != 128:
        raise PackIntegrityError(
            "Gate-0 exact B2.1 cache replay requires device=cuda and batch-size=128")
    history_argument = getattr(args, "b21_history_2wiki_data", None)
    if role == "musique_full_closed_corpus":
        if not history_argument:
            raise PackIntegrityError(
                "MuSiQue Gate-0 compilation requires --b21-history-2wiki-data")
        two_wiki_path = Path(history_argument).resolve()
    else:
        two_wiki_path = data_path
        if history_argument and Path(history_argument).resolve() != data_path:
            raise PackIntegrityError(
                "2Wiki Gate-0 history source must be the target --data bytes")
    model_input = Path(args.model_path).absolute()
    model_manifest = _strict_model_manifest(model_input)
    model_path = model_input.resolve()
    output = Path(args.output).absolute()
    receipt_path = Path(args.receipt).absolute()
    frozen_reference_path = (
        Path(args.frozen_b2_reference).absolute()
        if args.frozen_b2_reference else None
    )
    if output.is_symlink():
        raise PackIntegrityError(f"refusing symlinked pack output: {output}")
    if output.exists():
        raise PackIntegrityError(f"refusing to replace existing pack: {output}")
    output_paths = {"pack": output, "compile_receipt": receipt_path,
                    "model_snapshot": model_path}
    if frozen_reference_path is not None:
        output_paths["frozen_b2_reference"] = frozen_reference_path
    _reject_artifact_overlap(output_paths)
    raw = _read_json(data_path)
    two_wiki_raw = raw if two_wiki_path == data_path else _read_json(two_wiki_path)
    selected_rows, queries, pool = _select_cohort(raw, args.dataset, args.cohort)
    producer_hashes = _producer_hashes()
    data_sha256 = sha256_file(data_path)
    two_wiki_sha256 = sha256_file(two_wiki_path)
    provenance = {
        "dataset_sha256": data_sha256,
        "model_snapshot_sha256": model_manifest["sha256"],
        "producer_sha256": producer_hashes,
    }
    embedder = SentenceEmbedder(str(model_path), device=args.device,
                                batch_size=args.batch_size)
    cache_plan = _embedding_cache_plan(
        role, target_raw=raw, two_wiki_raw=two_wiki_raw)
    observed_schedule = _execute_embedding_cache_prewarm(embedder, cache_plan)
    target_name, target_texts = cache_plan["target"]

    def encode_target(texts: list[str]) -> Sequence[Sequence[float]]:
        if tuple(texts) != tuple(target_texts):
            raise ReplayMismatch(
                f"compiled target request differs from B2.1 prefix: {target_name}")
        return observed_schedule.encode(target_name, texts)

    compiled = compile_full_candidate_pack(
        queries, pool, encode_target, dataset=args.dataset, salt=args.salt,
        cohort=args.cohort, model_id=args.model_id, provenance=provenance,
    )
    if (compiled.manifest_seed["text_table_sha256"]
            != _text_sequence_sha256(target_texts)):
        raise ReplayMismatch(f"cache-history target text table drift: {target_name}")
    cache_history = _make_embedding_cache_history(
        role,
        target_raw=raw,
        two_wiki_raw=two_wiki_raw,
        two_wiki_path=two_wiki_path,
        two_wiki_sha256=two_wiki_sha256,
        model_snapshot_sha256=model_manifest["sha256"],
        target_embedding_table_sha256=compiled.manifest_seed[
            "embedding_table_sha256"],
        device=args.device,
        batch_size=args.batch_size,
        observed_steps=observed_schedule.steps,
    )
    repeated = compile_full_candidate_pack(
        queries, pool, embedder, dataset=args.dataset, salt=args.salt,
        cohort=args.cohort, model_id=args.model_id, provenance=provenance,
    )
    primary_digest = _compiled_semantic_sha256(compiled)
    repeated_digest = _compiled_semantic_sha256(repeated)
    if primary_digest != repeated_digest:
        raise ReplayMismatch("same-embedding-table compilation is nondeterministic")
    reference = None
    reference_info = None
    if args.cohort == "b2_reproduction400":
        if not args.frozen_b2_reference:
            raise PackIntegrityError(
                "b2_reproduction400 requires --frozen-b2-reference")
        reference = frozen_b2_reference(selected_rows, embedder, top_k=len(pool))
        reference_info = _write_frozen_reference(
            frozen_reference_path, reference)
    elif args.frozen_b2_reference:
        raise PackIntegrityError(
            "--frozen-b2-reference is valid only for b2_reproduction400")
    b21_path = Path(args.b21_scorepack).resolve() if args.b21_scorepack else None
    b21 = read_scorepack(b21_path) if b21_path else None
    if _strict_model_manifest(model_path) != model_manifest:
        raise PackIntegrityError("model snapshot changed during compilation")
    if (sha256_file(data_path) != data_sha256
            or sha256_file(two_wiki_path) != two_wiki_sha256):
        raise PackIntegrityError("dataset/cache-history source changed during compilation")
    receipt = write_pack(output, compiled, frozen_b2=reference, b21_scorepack=b21)
    receipt.update({
        "embedding_cache_history": cache_history,
        "determinism_replay": {
            "pass": True,
            "same_embedding_table": True,
            "primary_semantic_sha256": primary_digest,
            "repeated_semantic_sha256": repeated_digest,
        },
        "started_at": started_at,
        "finished_at": _utc_now(),
        "git_head": _git_head(),
        "environment": {"host": platform.node(), "python": sys.version.split()[0],
                        "numpy": np.__version__, "device": args.device,
                        "batch_size": args.batch_size},
        "inputs": {
            "data": str(data_path), "data_sha256": data_sha256,
            "model": str(model_path),
            "model_snapshot_sha256": model_manifest["sha256"],
            "producer_sha256": producer_hashes,
            "b21_scorepack": str(b21_path) if b21_path else None,
            "b21_scorepack_sha256": sha256_file(b21_path) if b21_path else None,
            "b21_payload_sha256": _gzip_payload_sha256(b21_path) if b21_path else None,
            "frozen_b2_reference": reference_info["path"] if reference_info else None,
            "frozen_b2_reference_sha256": reference_info["sha256"] if reference_info else None,
            "frozen_b2_payload_sha256": reference_info["payload_sha256"] if reference_info else None,
        },
    })
    _write_receipt(receipt_path, receipt)
    print(json.dumps({"pack": str(output), "receipt": str(receipt_path),
                      "pack_root_sha256": receipt["pack_root_sha256"],
                      "status": receipt["status"]}, indent=2, sort_keys=True))
    return 0


def _verify_cli(args: argparse.Namespace) -> int:
    receipt = verify_pack(Path(args.pack), expected_root=args.expected_root)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


def _lock_cli(args: argparse.Namespace) -> int:
    role_paths = {
        "b2_reproduction400": (Path(args.reproduction_pack), Path(args.reproduction_receipt)),
        "2wiki_full_closed_corpus": (Path(args.two_wiki_pack), Path(args.two_wiki_receipt)),
        "musique_full_closed_corpus": (Path(args.musique_pack), Path(args.musique_receipt)),
    }
    lock = create_acceptance_lock(role_paths, Path(args.output))
    print(json.dumps({"lock": str(Path(args.output).absolute()),
                      "lock_sha256": sha256_file(Path(args.output).absolute()),
                      "status": lock["status"]}, indent=2, sort_keys=True))
    return 0


def _accept_cli(args: argparse.Namespace) -> int:
    receipt = accept_gate0_bundle(Path(args.lock), Path(args.output))
    print(json.dumps({"receipt": str(Path(args.output).absolute()),
                      "receipt_sha256": sha256_file(Path(args.output).absolute()),
                      "status": receipt["status"],
                      "learner_allowed": receipt["learner_allowed"]},
                     indent=2, sort_keys=True))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    compile_parser = sub.add_parser("compile", help="build and atomically publish a Gate 0 pack")
    compile_parser.add_argument("--data", required=True)
    compile_parser.add_argument("--dataset", choices=("2wiki", "musique"), required=True)
    compile_parser.add_argument("--cohort", choices=("b2_reproduction400", "full_closed_corpus"),
                                default="full_closed_corpus")
    compile_parser.add_argument("--salt", choices=PARTITION_SALTS, default="legacy")
    compile_parser.add_argument("--model-path", required=True)
    compile_parser.add_argument("--model-id", default=MODEL_NAME)
    compile_parser.add_argument("--device", default="cuda")
    compile_parser.add_argument("--batch-size", type=int, default=128)
    compile_parser.add_argument("--b21-scorepack")
    compile_parser.add_argument(
        "--b21-history-2wiki-data",
        help="pinned 2Wiki source needed to reconstruct B2.1 shared-cache history",
    )
    compile_parser.add_argument("--frozen-b2-reference")
    compile_parser.add_argument("--output", required=True)
    compile_parser.add_argument("--receipt", required=True)
    verify_parser = sub.add_parser("verify", help="model-free verification of an existing pack")
    verify_parser.add_argument("--pack", required=True)
    verify_parser.add_argument("--expected-root", required=True)
    lock_parser = sub.add_parser("lock", help="freeze the complete three-pack Gate-0 bundle")
    lock_parser.add_argument("--reproduction-pack", required=True)
    lock_parser.add_argument("--reproduction-receipt", required=True)
    lock_parser.add_argument("--two-wiki-pack", required=True)
    lock_parser.add_argument("--two-wiki-receipt", required=True)
    lock_parser.add_argument("--musique-pack", required=True)
    lock_parser.add_argument("--musique-receipt", required=True)
    lock_parser.add_argument("--output", required=True)
    accept_parser = sub.add_parser("accept", help="verify a frozen bundle and emit learner unlock")
    accept_parser.add_argument("--lock", required=True)
    accept_parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "compile":
            if args.batch_size <= 0:
                raise PackIntegrityError("batch size must be positive")
            return _compile_cli(args)
        if args.command == "verify":
            return _verify_cli(args)
        if args.command == "lock":
            return _lock_cli(args)
        return _accept_cli(args)
    except PackIntegrityError as exc:
        print(json.dumps({"status": "ENGINEERING_REPLAY_FAIL",
                          "category": "integrity", "message": str(exc)}), file=sys.stderr)
        return 4
    except ReplayMismatch as exc:
        print(json.dumps({"status": "ENGINEERING_REPLAY_FAIL",
                          "category": "replay", "message": str(exc)}), file=sys.stderr)
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
