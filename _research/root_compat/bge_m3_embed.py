"""Recorded BGE-M3 embedding runner for fresh H3 confirmations.

The runner is deliberately outside the World Compiler.  It turns a frozen
JSONL preimage manifest into a stable-ID NPZ plus a JSON receipt.  Consumers
join vectors by ID; array position is never an identity contract.

Input JSONL records contain exactly ``id``, ``kind``, and ``text``.  The
command-line encoder uses the BGE-M3 CLS vector followed by L2 normalization,
matching the model's published sentence-transformers pooling configuration.

Longinus ReferenceSite: ``H3_B3_COMPOSITION_PREREG_2026-07-20.md`` frozen
BGE-M3 artifact and producer-identity contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import argparse
import json
import math
import os
from pathlib import Path
import re
import tempfile
import time
from collections.abc import Callable, Iterable, Sequence
from typing import Any, Mapping

import numpy as np


SCHEMA_VERSION = "hswm-recorded-embedding/v3"
MODEL_ATTESTATION_SCHEMA_VERSION = "hswm-local-model-attestation/v2"
ALLOWED_KEYS = frozenset({"id", "kind", "text"})
FROZEN_MODEL_ID = "BAAI/bge-m3"
FROZEN_MODEL_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
# Frozen in H3_B3_RUN_MANIFEST_2026-07-20.json before confirmatory evaluation.
FROZEN_WEIGHT_BLOB_SHA256 = (
    "b5e0ce3470abf5ef3831aa1bd5553b486803e83251590ab7ff35a117cf6aad38"
)
FROZEN_POOLING = "CLS+L2"
FROZEN_MAX_LENGTH = 8192
FROZEN_DTYPE = "bfloat16"
FROZEN_BATCH_SIZE = 32

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
_TOKENIZER_PAYLOADS = frozenset({
    "tokenizer.json", "tokenizer.model", "sentencepiece.bpe.model",
    "spiece.model", "vocab.json", "vocab.txt",
})
_MODEL_ATTESTATION_KEYS = frozenset({
    "schema_version", "resolved_model_id", "resolved_revision",
    "resolved_snapshot_path", "resolved_repository_path", "config_sha256",
    "config_identity", "tokenizer_config_sha256", "tokenizer_identity",
    "tokenizer_payloads", "weight_files", "weight_root_sha256",
    "weight_blob_sha256", "metadata_files", "metadata_root_sha256",
    "snapshot_root_sha256", "attestation_sha256", "attestation_id",
})
_EMBEDDING_RECEIPT_KEYS = frozenset({
    "schema_version", "model", "model_revision", "model_attestation",
    "pooling", "max_length", "dtype", "batch_size",
    "producer_code_sha256", "normalized", "input_sha256", "output_sha256",
    "n_records", "dimension", "elapsed_s", "id_root_sha256",
    "max_norm_error", "receipt_sha256", "receipt_id",
})


@dataclass(frozen=True)
class EmbeddingInputV1:
    id: str
    kind: str
    text: str


def canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )


def _file_sha256(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _strict_json_bytes(raw: bytes, *, label: str) -> Any:
    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"{label} contains duplicate JSON key {key!r}")
            value[key] = item
        return value

    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=object_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not strict UTF-8 JSON") from exc


def _require_sha256(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _integrity_digest(value: Mapping[str, Any], *excluded: str) -> str:
    payload = {key: item for key, item in value.items() if key not in excluded}
    return sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _exclusive_temp(parent: Path, *, prefix: str) -> tuple[int, Path]:
    descriptor, raw_path = tempfile.mkstemp(dir=parent, prefix=prefix)
    return descriptor, Path(raw_path)


def _root_digest(entries: Sequence[Mapping[str, Any]]) -> str:
    return sha256(canonical_json(tuple(entries)).encode("utf-8")).hexdigest()


def _snapshot_file_entries(snapshot: Path, repository: Path) -> tuple[dict[str, Any], ...]:
    """Enumerate a HF snapshot without following attacker-chosen directories.

    Hugging Face legitimately represents snapshot files as symlinks into the
    repository-local ``blobs`` directory.  Those links are admitted; links to
    any other location and symlinked directories fail closed.
    """

    declared_blob_root = repository / "blobs"
    if declared_blob_root.is_symlink():
        raise ValueError("HF repository blobs directory may not be a symlink")
    blob_root = declared_blob_root.resolve(strict=False)
    rows: list[dict[str, Any]] = []
    for directory, directory_names, file_names in os.walk(snapshot, followlinks=False):
        base = Path(directory)
        for name in tuple(directory_names):
            candidate = base / name
            if candidate.is_symlink():
                raise ValueError("model snapshot contains a symlinked directory")
        for name in file_names:
            candidate = base / name
            relative = candidate.relative_to(snapshot).as_posix()
            if candidate.is_symlink():
                try:
                    resolved = candidate.resolve(strict=True)
                except OSError as exc:
                    raise ValueError(f"model snapshot has dangling link {relative}") from exc
                if not resolved.is_file():
                    raise ValueError(f"model snapshot link is not a file: {relative}")
                if _is_relative_to(resolved, snapshot):
                    storage = "snapshot"
                elif _is_relative_to(resolved, blob_root):
                    storage = "hf_blob"
                else:
                    raise ValueError(
                        f"model snapshot link escapes its repository: {relative}"
                    )
                target = resolved.relative_to(repository).as_posix()
            else:
                if not candidate.is_file():
                    raise ValueError(f"model snapshot has a non-regular entry: {relative}")
                resolved = candidate.resolve(strict=True)
                if not _is_relative_to(resolved, snapshot):
                    raise ValueError(f"model snapshot file escapes snapshot: {relative}")
                storage = "snapshot"
                target = None
            digest = _file_sha256(resolved)
            if storage == "hf_blob" and _SHA256_RE.fullmatch(resolved.name):
                if resolved.name != digest:
                    raise ValueError(
                        f"HF LFS blob filename/content mismatch: {relative}"
                    )
            rows.append({
                "path": relative,
                "sha256": digest,
                "size_bytes": resolved.stat().st_size,
                "storage": storage,
                "link_target": target,
            })
    return tuple(sorted(rows, key=lambda row: str(row["path"])))


def _json_object(path: Path, *, label: str) -> Mapping[str, Any]:
    value = _strict_json_bytes(path.read_bytes(), label=label)
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a JSON object")
    return value


def attest_model_snapshot(
    model_path: str | Path,
    *,
    expected_model: str,
    expected_revision: str,
) -> dict[str, Any]:
    """Bind the actually loaded local HF snapshot to its content.

    A caller-provided model label is not evidence.  The repository ID and
    revision are derived from the resolved
    ``models--ORG--NAME/snapshots/REV`` path, while config/tokenizer metadata
    and every weight blob are content-hashed.  An arbitrary local transformer
    therefore cannot be receipted as BGE-M3 by changing CLI strings.
    """

    declared = Path(model_path).expanduser()
    if declared.is_symlink():
        raise ValueError("model path itself may not be a symlink alias")
    snapshot = declared.resolve(strict=True)
    if not snapshot.is_dir() or snapshot.parent.name != "snapshots":
        raise ValueError("model path must resolve to an exact HF snapshot directory")
    if _REVISION_RE.fullmatch(expected_revision) is None:
        raise ValueError("model revision must be an exact 40-hex commit")
    repository = snapshot.parent.parent
    expected_repository = "models--" + expected_model.replace("/", "--")
    if "/" not in expected_model or repository.name != expected_repository:
        raise ValueError("model snapshot is not under a Hugging Face cache repository")
    resolved_model = expected_model
    resolved_revision = snapshot.name
    if resolved_revision != expected_revision:
        raise ValueError(
            "resolved snapshot revision does not equal declared revision"
        )

    config = snapshot / "config.json"
    tokenizer_config = snapshot / "tokenizer_config.json"
    if not config.is_file():
        raise ValueError("model snapshot lacks config.json")
    if not tokenizer_config.is_file():
        raise ValueError("model snapshot lacks tokenizer_config.json")

    all_entries = _snapshot_file_entries(snapshot, repository)
    entries_by_path = {str(row["path"]): row for row in all_entries}
    tokenizer_payloads = tuple(sorted(
        path for path in entries_by_path
        if Path(path).name in _TOKENIZER_PAYLOADS
    ))
    if not tokenizer_payloads:
        raise ValueError("model snapshot lacks a tokenizer payload")
    weight_entries = tuple(row for row in all_entries if (
        str(row["path"]).endswith(".safetensors")
        or (
            Path(str(row["path"])).name.startswith("pytorch_model")
            and Path(str(row["path"])).suffix in {".bin", ".pt"}
        )
    ))
    if not weight_entries:
        raise ValueError("model snapshot contains no recognized weight blob")
    weight_paths = {str(row["path"]) for row in weight_entries}
    metadata_entries = tuple(
        row for row in all_entries if str(row["path"]) not in weight_paths
    )
    if not metadata_entries:
        raise ValueError("model snapshot contains no tokenizer/config metadata")

    config_value = _json_object(config, label="config.json")
    tokenizer_value = _json_object(
        tokenizer_config, label="tokenizer_config.json",
    )
    name_or_path = config_value.get("_name_or_path")
    if isinstance(name_or_path, str) and "/" in name_or_path:
        if name_or_path.rstrip("/") != expected_model:
            raise ValueError("config.json names a different upstream model")
    tokenizer_name = tokenizer_value.get("name_or_path")
    if isinstance(tokenizer_name, str) and "/" in tokenizer_name:
        if tokenizer_name.rstrip("/") != expected_model:
            raise ValueError("tokenizer_config.json names a different model")

    weight_root = _root_digest(weight_entries)
    metadata_root = _root_digest(metadata_entries)
    config_identity = {
        "model_type": config_value.get("model_type"),
        "architectures": config_value.get("architectures"),
        "torch_dtype": config_value.get("torch_dtype"),
    }
    tokenizer_identity = {
        "tokenizer_class": tokenizer_value.get("tokenizer_class"),
        "model_max_length": tokenizer_value.get("model_max_length"),
    }
    payload: dict[str, Any] = {
        "schema_version": MODEL_ATTESTATION_SCHEMA_VERSION,
        "resolved_model_id": resolved_model,
        "resolved_revision": resolved_revision,
        "resolved_snapshot_path": str(snapshot),
        "resolved_repository_path": str(repository.resolve(strict=True)),
        "config_sha256": entries_by_path["config.json"]["sha256"],
        "config_identity": config_identity,
        "tokenizer_config_sha256": entries_by_path["tokenizer_config.json"]["sha256"],
        "tokenizer_identity": tokenizer_identity,
        "tokenizer_payloads": list(tokenizer_payloads),
        "weight_files": list(weight_entries),
        "weight_root_sha256": weight_root,
        "weight_blob_sha256": (
            weight_entries[0]["sha256"] if len(weight_entries) == 1 else None
        ),
        "metadata_files": list(metadata_entries),
        "metadata_root_sha256": metadata_root,
        "snapshot_root_sha256": sha256(canonical_json({
            "model": resolved_model,
            "revision": resolved_revision,
            "weights": weight_root,
            "metadata": metadata_root,
        }).encode("utf-8")).hexdigest(),
    }
    integrity = _integrity_digest(payload)
    payload["attestation_sha256"] = integrity
    payload["attestation_id"] = f"hswm:model_snapshot:v2:{integrity}"
    validate_model_attestation(payload)
    return payload


def validate_model_attestation(
    value: Mapping[str, Any],
    *,
    expected_model: str | None = None,
    expected_revision: str | None = None,
    snapshot_path: str | Path | None = None,
    verify_files: bool = False,
) -> dict[str, Any]:
    """Validate self-integrity and optionally recompute the live snapshot."""

    if not isinstance(value, Mapping) or set(value) != _MODEL_ATTESTATION_KEYS:
        raise ValueError("model attestation keys mismatch")
    result = dict(value)
    if result.get("schema_version") != MODEL_ATTESTATION_SCHEMA_VERSION:
        raise ValueError("model attestation schema mismatch")
    model = result.get("resolved_model_id")
    revision = result.get("resolved_revision")
    if not isinstance(model, str) or "/" not in model:
        raise ValueError("model attestation has invalid model identity")
    if not isinstance(revision, str) or _REVISION_RE.fullmatch(revision) is None:
        raise ValueError("model attestation has invalid revision")
    if expected_model is not None and model != expected_model:
        raise ValueError("model attestation model mismatch")
    if expected_revision is not None and revision != expected_revision:
        raise ValueError("model attestation revision mismatch")
    for key in (
        "config_sha256", "tokenizer_config_sha256", "weight_root_sha256",
        "metadata_root_sha256", "snapshot_root_sha256", "attestation_sha256",
    ):
        _require_sha256(result.get(key), label=f"model_attestation.{key}")
    weight_blob = result.get("weight_blob_sha256")
    if weight_blob is not None:
        _require_sha256(weight_blob, label="model_attestation.weight_blob_sha256")
    file_rows: dict[str, Mapping[str, Any]] = {}
    for collection in ("weight_files", "metadata_files"):
        rows = result.get(collection)
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"model attestation {collection} must be non-empty")
        paths: list[str] = []
        for row in rows:
            if not isinstance(row, Mapping) or set(row) != {
                "path", "sha256", "size_bytes", "storage", "link_target",
            }:
                raise ValueError(f"model attestation {collection} entry mismatch")
            path = row.get("path")
            if (not isinstance(path, str) or not path
                    or Path(path).is_absolute() or ".." in Path(path).parts):
                raise ValueError("model attestation contains unsafe relative path")
            paths.append(path)
            if path in file_rows:
                raise ValueError("model attestation repeats a snapshot path")
            file_rows[path] = row
            _require_sha256(row.get("sha256"), label=f"{collection}.{path}")
            if not isinstance(row.get("size_bytes"), int) or row["size_bytes"] < 0:
                raise ValueError("model attestation contains invalid file size")
            if row.get("storage") not in {"snapshot", "hf_blob"}:
                raise ValueError("model attestation contains invalid storage class")
            if row.get("link_target") is not None and not isinstance(
                row.get("link_target"), str,
            ):
                raise ValueError("model attestation contains invalid link target")
        if paths != sorted(paths) or len(paths) != len(set(paths)):
            raise ValueError(f"model attestation {collection} paths are not canonical")
        if _root_digest(rows) != result[f"{collection[:-6]}_root_sha256"]:
            raise ValueError(f"model attestation {collection} root mismatch")
    if (file_rows.get("config.json", {}).get("sha256")
            != result["config_sha256"]):
        raise ValueError("model attestation config hash is not file-bound")
    if (file_rows.get("tokenizer_config.json", {}).get("sha256")
            != result["tokenizer_config_sha256"]):
        raise ValueError("model attestation tokenizer config is not file-bound")
    tokenizer_payloads = result.get("tokenizer_payloads")
    if not isinstance(tokenizer_payloads, list) or not tokenizer_payloads:
        raise ValueError("model attestation lacks tokenizer payload binding")
    if (tokenizer_payloads != sorted(tokenizer_payloads)
            or len(tokenizer_payloads) != len(set(tokenizer_payloads))
            or any(path not in file_rows for path in tokenizer_payloads)):
        raise ValueError("model attestation tokenizer payload binding mismatch")
    weights = result["weight_files"]
    expected_blob = weights[0]["sha256"] if len(weights) == 1 else None
    if result.get("weight_blob_sha256") != expected_blob:
        raise ValueError("model attestation single weight blob binding mismatch")
    expected_snapshot_root = sha256(canonical_json({
        "model": model,
        "revision": revision,
        "weights": result["weight_root_sha256"],
        "metadata": result["metadata_root_sha256"],
    }).encode("utf-8")).hexdigest()
    if result["snapshot_root_sha256"] != expected_snapshot_root:
        raise ValueError("model attestation snapshot root mismatch")
    if not isinstance(result.get("config_identity"), Mapping):
        raise ValueError("model attestation lacks config identity")
    if not isinstance(result.get("tokenizer_identity"), Mapping):
        raise ValueError("model attestation lacks tokenizer identity")
    expected_integrity = _integrity_digest(
        result, "attestation_sha256", "attestation_id",
    )
    if result["attestation_sha256"] != expected_integrity:
        raise ValueError("model attestation self-hash mismatch")
    if result.get("attestation_id") != f"hswm:model_snapshot:v2:{expected_integrity}":
        raise ValueError("model attestation ID mismatch")

    if verify_files or snapshot_path is not None:
        live_path = snapshot_path or result["resolved_snapshot_path"]
        recomputed = attest_model_snapshot(
            live_path, expected_model=model, expected_revision=revision,
        )
        if recomputed != result:
            raise ValueError("model snapshot no longer matches attestation")
    return result


def write_model_attestation(
    path: str | Path,
    value: Mapping[str, Any],
) -> str:
    """First-write one canonical, live-reverified model attestation.

    The standalone artifact is needed before an embedding stage can be
    authorized.  It deliberately retains the existing attestation schema and
    self-hash; the returned digest is the SHA-256 of the exact canonical JSON
    line written to disk.
    """

    attestation = validate_model_attestation(value, verify_files=True)
    output = Path(path).expanduser().absolute()
    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = (canonical_json(attestation) + "\n").encode("utf-8")
    try:
        descriptor = os.open(
            output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600,
        )
    except FileExistsError as exc:
        raise FileExistsError(
            "model attestation is first-write-wins"
        ) from exc
    published = False
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            view = memoryview(encoded)
            while view:
                written = handle.write(view)
                if written is None or written <= 0:  # pragma: no cover - IO guard
                    raise OSError("failed to write model attestation")
                view = view[written:]
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(output.parent)
        published = True
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if not published:
            output.unlink(missing_ok=True)
    return sha256(encoded).hexdigest()


def load_jsonl(path: str) -> tuple[EmbeddingInputV1, ...]:
    records: list[EmbeddingInputV1] = []
    with open(path, encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"line {line_number}: invalid JSON") from exc
            if not isinstance(raw, dict) or set(raw) != ALLOWED_KEYS:
                raise ValueError(
                    f"line {line_number}: keys must be exactly {sorted(ALLOWED_KEYS)}"
                )
            record = EmbeddingInputV1(
                id=str(raw["id"]), kind=str(raw["kind"]), text=str(raw["text"]),
            )
            if not record.id or not record.kind or not record.text:
                raise ValueError(f"line {line_number}: fields must be non-empty")
            records.append(record)
    if not records:
        raise ValueError("embedding input is empty")
    ids = [record.id for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("embedding input IDs must be unique")
    return tuple(sorted(records, key=lambda record: record.id))


def input_sha256(records: Sequence[EmbeddingInputV1]) -> str:
    payload = tuple({
        "id": record.id,
        "kind": record.kind,
        "text_sha256": sha256(record.text.encode("utf-8")).hexdigest(),
    } for record in records)
    return sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def embed_records(
    records: Sequence[EmbeddingInputV1],
    encode_batch: Callable[[Sequence[str]], np.ndarray],
    *,
    batch_size: int = FROZEN_BATCH_SIZE,
) -> np.ndarray:
    """Encode and verify a stable sequence with an injectable batch encoder."""

    if batch_size < 1 or not records:
        raise ValueError("records and positive batch_size are required")
    chunks: list[np.ndarray] = []
    dimension: int | None = None
    for start in range(0, len(records), batch_size):
        texts = [record.text for record in records[start:start + batch_size]]
        values = np.asarray(encode_batch(texts), dtype=np.float32)
        if values.ndim != 2 or values.shape[0] != len(texts):
            raise ValueError("encoder returned an invalid batch shape")
        if not np.isfinite(values).all():
            raise ValueError("encoder returned a non-finite vector")
        if dimension is None:
            dimension = values.shape[1]
        if not dimension or values.shape[1] != dimension:
            raise ValueError("encoder dimension changed between batches")
        norms = np.linalg.norm(values.astype(np.float64), axis=1)
        if np.any(norms <= 1e-12):
            raise ValueError("encoder returned a zero vector")
        values = values / norms[:, None].astype(np.float32)
        chunks.append(values)
    matrix = np.concatenate(chunks, axis=0)
    norms = np.linalg.norm(matrix.astype(np.float64), axis=1)
    if np.max(np.abs(norms - 1.0)) > 1e-5:
        raise ValueError("normalization invariant failed")
    return matrix


def write_artifact(
    output_path: str,
    receipt_path: str,
    records: Sequence[EmbeddingInputV1],
    vectors: np.ndarray,
    *,
    model_attestation: dict[str, Any],
    max_length: int,
    dtype_name: str,
    batch_size: int,
    elapsed_s: float,
) -> dict[str, Any]:
    vectors = np.asarray(vectors, dtype=np.float32)
    ids_tuple = tuple(record.id for record in records)
    if (not records or len(ids_tuple) != len(set(ids_tuple))
            or ids_tuple != tuple(sorted(ids_tuple))):
        raise ValueError("embedding records must have unique canonical IDs")
    if vectors.ndim != 2 or vectors.shape[0] != len(records) or vectors.shape[1] < 1:
        raise ValueError("vector count does not match embedding inputs")
    if not np.isfinite(vectors).all():
        raise ValueError("embedding vectors contain non-finite values")
    norm_error = float(np.max(np.abs(
        np.linalg.norm(vectors.astype(np.float64), axis=1) - 1.0
    )))
    if norm_error > 1e-5:
        raise ValueError("embedding vectors are not L2 normalized")
    if max_length != FROZEN_MAX_LENGTH or dtype_name != FROZEN_DTYPE:
        raise ValueError("confirmatory BGE-M3 max_length/dtype contract changed")
    if batch_size != FROZEN_BATCH_SIZE:
        raise ValueError(f"batch_size is frozen at {FROZEN_BATCH_SIZE}")
    if not math.isfinite(float(elapsed_s)) or float(elapsed_s) < 0:
        raise ValueError("elapsed_s must be finite and non-negative")
    attestation = validate_model_attestation(
        model_attestation, expected_model=FROZEN_MODEL_ID,
        expected_revision=FROZEN_MODEL_REVISION,
    )
    if attestation.get("weight_blob_sha256") != FROZEN_WEIGHT_BLOB_SHA256:
        raise ValueError("BGE-M3 weight blob does not match preregistered content")
    if attestation.get("config_identity", {}).get("model_type") != "xlm-roberta":
        raise ValueError("BGE-M3 config model_type mismatch")

    output = Path(output_path).expanduser().absolute()
    receipt_output = Path(receipt_path).expanduser().absolute()
    if output == receipt_output:
        raise ValueError("artifact and receipt paths must differ")
    if output.exists() or receipt_output.exists():
        raise FileExistsError("embedding artifact paths are first-write-wins")
    output.parent.mkdir(parents=True, exist_ok=True)
    receipt_output.parent.mkdir(parents=True, exist_ok=True)
    text_hashes = np.asarray([
        sha256(record.text.encode("utf-8")).hexdigest() for record in records
    ])
    ids = np.asarray(ids_tuple)
    kinds = np.asarray([record.kind for record in records])
    artifact_fd, artifact_tmp = _exclusive_temp(
        output.parent, prefix=f".{output.name}.pending-",
    )
    receipt_fd: int | None = None
    receipt_tmp: Path | None = None
    artifact_published = False
    try:
        with os.fdopen(artifact_fd, "wb") as handle:
            artifact_fd = -1
            np.savez_compressed(
                handle, ids=ids, kinds=kinds, text_sha256=text_hashes,
                vectors=vectors,
            )
            handle.flush()
            os.fsync(handle.fileno())
        output_digest = _file_sha256(artifact_tmp)
        receipt: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "model": attestation["resolved_model_id"],
            "model_revision": attestation["resolved_revision"],
            "model_attestation": attestation,
            "pooling": FROZEN_POOLING,
            "max_length": max_length,
            "dtype": dtype_name,
            "batch_size": batch_size,
            "producer_code_sha256": _file_sha256(Path(__file__)),
            "normalized": True,
            "input_sha256": input_sha256(records),
            "output_sha256": output_digest,
            "n_records": len(records),
            "dimension": int(vectors.shape[1]),
            "elapsed_s": round(float(elapsed_s), 6),
            "id_root_sha256": sha256(
                canonical_json(ids_tuple).encode("utf-8")
            ).hexdigest(),
            "max_norm_error": norm_error,
        }
        receipt_digest = _integrity_digest(receipt)
        receipt["receipt_sha256"] = receipt_digest
        receipt["receipt_id"] = f"hswm:recorded_embedding:v3:{receipt_digest}"
        validate_embedding_receipt(
            receipt, artifact_path=artifact_tmp, expected_records=records,
            expected_producer_code_sha256=receipt["producer_code_sha256"],
        )
        receipt_fd, receipt_tmp = _exclusive_temp(
            receipt_output.parent, prefix=f".{receipt_output.name}.pending-",
        )
        receipt_bytes = (canonical_json(receipt) + "\n").encode("utf-8")
        with os.fdopen(receipt_fd, "wb") as handle:
            receipt_fd = -1
            handle.write(receipt_bytes)
            handle.flush()
            os.fsync(handle.fileno())

        os.link(artifact_tmp, output)
        artifact_published = True
        _fsync_directory(output.parent)
        os.link(receipt_tmp, receipt_output)
        _fsync_directory(receipt_output.parent)
        return receipt
    except FileExistsError as exc:
        if artifact_published:
            try:
                if output.stat().st_ino == artifact_tmp.stat().st_ino:
                    output.unlink()
                    _fsync_directory(output.parent)
            except (FileNotFoundError, OSError):
                pass
        raise FileExistsError("embedding artifact paths are first-write-wins") from exc
    except Exception:
        if artifact_published:
            try:
                if output.stat().st_ino == artifact_tmp.stat().st_ino:
                    output.unlink()
                    _fsync_directory(output.parent)
            except (FileNotFoundError, OSError):
                pass
        raise
    finally:
        if artifact_fd >= 0:
            os.close(artifact_fd)
        if receipt_fd is not None and receipt_fd >= 0:
            os.close(receipt_fd)
        artifact_tmp.unlink(missing_ok=True)
        if receipt_tmp is not None:
            receipt_tmp.unlink(missing_ok=True)


def validate_embedding_receipt(
    value: Mapping[str, Any],
    *,
    artifact_path: str | Path | None = None,
    expected_records: Sequence[EmbeddingInputV1] | None = None,
    expected_producer_code_sha256: str | None = None,
    verify_snapshot: bool = False,
) -> dict[str, Any]:
    """Verify a receipt's self-hash and, when supplied, its NPZ preimage."""

    if not isinstance(value, Mapping) or set(value) != _EMBEDDING_RECEIPT_KEYS:
        raise ValueError("embedding receipt keys mismatch")
    receipt = dict(value)
    if receipt.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("embedding receipt schema mismatch")
    if (receipt.get("model") != FROZEN_MODEL_ID
            or receipt.get("model_revision") != FROZEN_MODEL_REVISION
            or receipt.get("pooling") != FROZEN_POOLING
            or receipt.get("max_length") != FROZEN_MAX_LENGTH
            or receipt.get("dtype") != FROZEN_DTYPE
            or receipt.get("batch_size") != FROZEN_BATCH_SIZE
            or receipt.get("normalized") is not True):
        raise ValueError("embedding execution contract mismatch")
    producer_digest = _require_sha256(
        receipt.get("producer_code_sha256"), label="producer_code_sha256",
    )
    if (expected_producer_code_sha256 is not None
            and producer_digest != expected_producer_code_sha256):
        raise ValueError("embedding producer code hash mismatch")
    for key in ("input_sha256", "output_sha256", "id_root_sha256", "receipt_sha256"):
        _require_sha256(receipt.get(key), label=key)
    if not isinstance(receipt.get("n_records"), int) or receipt["n_records"] < 1:
        raise ValueError("embedding receipt has invalid record count")
    if not isinstance(receipt.get("dimension"), int) or receipt["dimension"] < 1:
        raise ValueError("embedding receipt has invalid dimension")
    for key in ("elapsed_s", "max_norm_error"):
        number = receipt.get(key)
        if (not isinstance(number, (int, float)) or isinstance(number, bool)
                or not math.isfinite(float(number)) or float(number) < 0):
            raise ValueError(f"embedding receipt has invalid {key}")
    if float(receipt["max_norm_error"]) > 1e-5:
        raise ValueError("embedding receipt records an invalid norm error")
    attestation = validate_model_attestation(
        receipt.get("model_attestation"), expected_model=FROZEN_MODEL_ID,
        expected_revision=FROZEN_MODEL_REVISION,
        verify_files=verify_snapshot,
    )
    if attestation.get("weight_blob_sha256") != FROZEN_WEIGHT_BLOB_SHA256:
        raise ValueError("embedding receipt weight identity mismatch")
    expected_integrity = _integrity_digest(
        receipt, "receipt_sha256", "receipt_id",
    )
    if receipt["receipt_sha256"] != expected_integrity:
        raise ValueError("embedding receipt self-hash mismatch")
    if receipt.get("receipt_id") != f"hswm:recorded_embedding:v3:{expected_integrity}":
        raise ValueError("embedding receipt ID mismatch")

    if expected_records is not None:
        ids = tuple(record.id for record in expected_records)
        if receipt["input_sha256"] != input_sha256(expected_records):
            raise ValueError("embedding receipt input preimage mismatch")
        if receipt["n_records"] != len(expected_records):
            raise ValueError("embedding receipt record count mismatch")
        expected_id_root = sha256(canonical_json(ids).encode("utf-8")).hexdigest()
        if receipt["id_root_sha256"] != expected_id_root:
            raise ValueError("embedding receipt ID root mismatch")
    if artifact_path is not None:
        source = Path(artifact_path)
        if _file_sha256(source) != receipt["output_sha256"]:
            raise ValueError("embedding receipt output hash mismatch")
        try:
            with np.load(source, allow_pickle=False) as archive:
                if set(archive.files) != {"ids", "kinds", "text_sha256", "vectors"}:
                    raise ValueError("embedding NPZ members mismatch")
                ids = tuple(str(item) for item in archive["ids"].tolist())
                kinds = tuple(str(item) for item in archive["kinds"].tolist())
                text_hashes = tuple(str(item) for item in archive["text_sha256"].tolist())
                vectors = np.asarray(archive["vectors"], dtype=np.float32)
        except (OSError, ValueError) as exc:
            if isinstance(exc, ValueError) and str(exc).startswith("embedding NPZ"):
                raise
            raise ValueError("embedding receipt points to invalid NPZ") from exc
        if (vectors.ndim != 2 or vectors.shape != (
                receipt["n_records"], receipt["dimension"],
        ) or len(ids) != len(kinds) or len(ids) != len(text_hashes)):
            raise ValueError("embedding NPZ arrays are not aligned")
        if tuple(sorted(ids)) != ids or len(ids) != len(set(ids)):
            raise ValueError("embedding NPZ IDs are not canonical")
        if not np.isfinite(vectors).all():
            raise ValueError("embedding NPZ has non-finite vectors")
        observed_norm_error = float(np.max(np.abs(
            np.linalg.norm(vectors.astype(np.float64), axis=1) - 1.0
        )))
        if observed_norm_error > 1e-5:
            raise ValueError("embedding NPZ vectors are not normalized")
        if expected_records is not None:
            expected_rows = tuple(
                (
                    record.id, record.kind,
                    sha256(record.text.encode("utf-8")).hexdigest(),
                )
                for record in expected_records
            )
            if tuple(zip(ids, kinds, text_hashes, strict=True)) != expected_rows:
                raise ValueError("embedding NPZ preimage rows mismatch")
    return receipt


def load_embedding_receipt(
    receipt_path: str | Path,
    *,
    artifact_path: str | Path | None = None,
    expected_records: Sequence[EmbeddingInputV1] | None = None,
    expected_producer_code_sha256: str | None = None,
    verify_snapshot: bool = False,
) -> dict[str, Any]:
    try:
        raw = Path(receipt_path).read_bytes()
    except OSError as exc:
        raise ValueError("cannot read embedding receipt") from exc
    value = _strict_json_bytes(raw, label="embedding receipt")
    if not isinstance(value, Mapping):
        raise ValueError("embedding receipt must be a JSON object")
    return validate_embedding_receipt(
        value, artifact_path=artifact_path, expected_records=expected_records,
        expected_producer_code_sha256=expected_producer_code_sha256,
        verify_snapshot=verify_snapshot,
    )


def _transformers_encoder(
    model_path: str,
    *,
    max_length: int,
    dtype_name: str,
) -> Callable[[Sequence[str]], np.ndarray]:
    import torch
    from transformers import AutoModel, AutoTokenizer

    dtype = {
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
        "float32": torch.float32,
    }[dtype_name]
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    model = AutoModel.from_pretrained(
        model_path, local_files_only=True, torch_dtype=dtype,
    ).eval().to("cuda")

    def encode(texts: Sequence[str]) -> np.ndarray:
        inputs = tokenizer(
            list(texts), padding=True, truncation=True, max_length=max_length,
            return_tensors="pt",
        ).to("cuda")
        with torch.inference_mode():
            hidden = model(**inputs).last_hidden_state[:, 0]
            hidden = torch.nn.functional.normalize(hidden.float(), p=2, dim=1)
        return hidden.cpu().numpy()

    return encode


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attest-only", action="store_true")
    parser.add_argument("--attestation-out")
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-id", default=FROZEN_MODEL_ID)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--input")
    parser.add_argument("--output")
    parser.add_argument("--receipt")
    parser.add_argument("--batch-size", type=int, default=FROZEN_BATCH_SIZE)
    parser.add_argument("--max-length", type=int, default=FROZEN_MAX_LENGTH)
    parser.add_argument(
        "--dtype", choices=("float16", "bfloat16", "float32"),
        default="bfloat16",
    )
    args = parser.parse_args(tuple(argv) if argv is not None else None)
    if args.model_id != FROZEN_MODEL_ID:
        raise ValueError(f"model-id is frozen at {FROZEN_MODEL_ID}")
    if args.model_revision != FROZEN_MODEL_REVISION:
        raise ValueError(f"model-revision is frozen at {FROZEN_MODEL_REVISION}")
    if args.attest_only:
        if not args.attestation_out:
            parser.error("--attest-only requires --attestation-out")
        if any(value is not None for value in (
            args.input, args.output, args.receipt,
        )):
            parser.error(
                "--attest-only forbids --input, --output, and --receipt"
            )
        attestation = attest_model_snapshot(
            args.model, expected_model=args.model_id,
            expected_revision=args.model_revision,
        )
        file_digest = write_model_attestation(
            args.attestation_out, attestation,
        )
        print(canonical_json({
            "schema_version": MODEL_ATTESTATION_SCHEMA_VERSION,
            "attestation_id": attestation["attestation_id"],
            "attestation_sha256": attestation["attestation_sha256"],
            "file_sha256": file_digest,
            "output": str(args.attestation_out),
        }))
        return
    if args.attestation_out is not None:
        parser.error("--attestation-out requires --attest-only")
    missing = [
        option for option, value in (
            ("--input", args.input), ("--output", args.output),
            ("--receipt", args.receipt),
        ) if value is None
    ]
    if missing:
        parser.error(
            "embedding mode requires " + ", ".join(missing)
        )
    if (args.max_length != FROZEN_MAX_LENGTH or args.dtype != FROZEN_DTYPE
            or args.batch_size != FROZEN_BATCH_SIZE):
        raise ValueError(
            "max-length/dtype/batch-size are frozen at "
            f"{FROZEN_MAX_LENGTH}/{FROZEN_DTYPE}/{FROZEN_BATCH_SIZE}"
        )
    records = load_jsonl(args.input)
    started = time.monotonic()
    model_attestation = attest_model_snapshot(
        args.model, expected_model=args.model_id,
        expected_revision=args.model_revision,
    )
    validate_model_attestation(
        model_attestation, expected_model=FROZEN_MODEL_ID,
        expected_revision=FROZEN_MODEL_REVISION, verify_files=True,
    )
    resolved_model_path = model_attestation["resolved_snapshot_path"]
    encoder = _transformers_encoder(
        resolved_model_path, max_length=args.max_length, dtype_name=args.dtype,
    )
    vectors = embed_records(records, encoder, batch_size=args.batch_size)
    # Detect a snapshot/blob swap between attestation and model load.
    if attest_model_snapshot(
        resolved_model_path, expected_model=FROZEN_MODEL_ID,
        expected_revision=FROZEN_MODEL_REVISION,
    ) != model_attestation:
        raise ValueError("model snapshot changed while embedding")
    receipt = write_artifact(
        args.output, args.receipt, records, vectors,
        model_attestation=model_attestation, max_length=args.max_length,
        dtype_name=args.dtype, batch_size=args.batch_size,
        elapsed_s=time.monotonic() - started,
    )
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
