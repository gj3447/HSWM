"""Deterministic first-write PRE_RUN manifest builder for H3-B3.

This module is deliberately outside the frozen evaluator set.  It derives
every input digest, stage preimage count/hash, and implementation hash from the
files that exist at freeze time.  It then writes a temporary canonical
manifest in the repository root, requires :func:`h3_b3_falsifier.load_run_manifest`
to accept it, and only then publishes the exact inode with no-replace
semantics.

No producer output hash appears in PRE_RUN.  Development/fresh OPEN and CLOSE
paths, phase receipts, and future Qwen27 adjudication paths are commitments to
currently nonexistent artifacts.

Longinus ReferenceSite: ``H3_B3_COMPOSITION_PREREG_2026-07-20.md``,
``H3_B3_V5_RESTART_PREREG_2026-07-20.md``, and
``h3_b3_falsifier.load_run_manifest``.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from hashlib import sha256
import argparse
import json
import os
from pathlib import Path
import tempfile
from collections.abc import Mapping, Sequence
from typing import Any

import bge_m3_embed as bge
import h3_arc_adjudicator as arca
import h3_b3_falsifier as h3
import h3_b3_prepare as prep
import h3_fresh_manifest as fresh
import model_deployment_receipt as deployment
import recorded_llm_extractor as rex
import relation_eval as reval
from world_ir import canonical_json


REPO_ROOT = Path(__file__).resolve().parent
FROZEN_BGE_DIMENSION = 1024
MANIFEST_BUILDER_SCHEMA_VERSION = "hswm-h3-b3-manifest-builder/v3"
FROZEN_V5_MANIFEST_PATH = "H3_B3_RUN_MANIFEST_V5_2026-07-20.json"

# V5 is a single preregistered confirmatory run, not a parameterized manifest
# template.  These bindings are intentionally independent of the supplied
# files so a caller cannot alter an input and merely recompute a self-consistent
# manifest around it.
FROZEN_V5_PROTOCOL_BINDING = {
    "path": "H3_B3_V5_RESTART_PREREG_2026-07-20.md",
    "sha256": "253ffd9e2550b30f6aa3c2d3144d4524a6f6c18ed9849f795553218e03e7eebb",
}
FROZEN_V5_PARENT_EVIDENCE = (
    {
        "path": "H3_B3_COMPOSITION_PREREG_2026-07-20.md",
        "sha256": "338a8859a7e2eebbea9c804d75f6b8e0db09d7ddf6b91db939cb30bae9f59a31",
    },
    {
        "path": "H3_B3_V3_REFUSAL_2026-07-20.md",
        "sha256": "da68371a21a54b1789779453581e2aee6fc5cc1f237b43d5dde24e78cd92f4a9",
    },
    {
        "path": "H3_B3_V4_RESTART_PREREG_2026-07-20.md",
        "sha256": "01f130c683d016a2f235500acae9fb3b4242e40dbe0afa2376310d938d5db9f4",
    },
    {
        "path": "H3_B3_V4_PREOUTPUT_REFUSAL_2026-07-20.md",
        "sha256": "9cf599b18e49d9342576f5a201a7d3312465c6a71a0ed6946b155ea9294042d7",
    },
)
FROZEN_V5_OUTPUT_PREFIX = (
    ".ab_p5_cache/h3_b3/runs/qwen35-r3-schema-v4-20260720"
)
FROZEN_V5_PREFLIGHT_PATH = (
    ".ab_p5_cache/h3_b3/H3_B3_PREFLIGHT_RECEIPT_V5_2026-07-20.json"
)
FROZEN_V5_QWEN35_DEPLOYMENT = {
    "path": ".ab_p5_cache/h3_b3/QWEN35_DEPLOYMENT_RECEIPT_V2_2026-07-20_RETRY1.json",
    "sha256": "15d3880b211c5e21a4087caa55f008d4474323a3d220e05bb47343bcd1f1c0a6",
}
FROZEN_V5_GATE_SOURCE_CODE_ROOT_SHA256 = (
    "2218428e2767689ebd538d99aad54031c8dcefdfc2913b43ed5e843f3513ddf5"
)
FROZEN_V5_EXTRACTOR_SCHEMA_VERSION = "hswm-recorded-llm-extractor/v4"
FROZEN_V5_ATTEMPT_JOURNAL_SCHEMA_VERSION = (
    "hswm-recorded-llm-attempt-journal/v1"
)
FROZEN_V5_ATTEMPT_JOURNAL_EVENTS = ("START", "FINALIZE")
FROZEN_V5_EXTRACTOR_PROMPT_SHA256 = (
    "bebcbaf01be3d0a05c7edc4284ec18e244da951f243a124bd558b39aba34fc0c"
)
FROZEN_V5_EXTRACTOR_CONFIG_SHA256 = (
    "185a15214301633f3353b80636438a4e5e1744633392753201256bf37267d2c0"
)
FROZEN_V5_STAGE_SEGMENTS = {
    "development": {
        "musique": {
            "path": ".ab_p5_cache/h3_b3/musique_development_v4_segment.json",
            "sha256": "de481a3307d8e04f17895b6c125f06a2299a821fc9254b67066058476b0b94e2",
        },
        "2wiki": {
            "path": ".ab_p5_cache/h3_b3/2wiki_development_v4_segment.json",
            "sha256": "10439ba55f0741fb2a092ce1dfb1fd0643cf1d0c5f42ff81dc001519608fd9fa",
        },
    },
    "fresh": {
        "musique": {
            "path": ".ab_p5_cache/h3_b3/musique_fresh_v4_segment.json",
            "sha256": "214d5594e6b7437f3f7a95b1bd86656f2052c0badfe2815ccff222c3eaa545c8",
        },
        "2wiki": {
            "path": ".ab_p5_cache/h3_b3/2wiki_fresh_v4_segment.json",
            "sha256": "0b6b7f58abcce938ee4ed8e0e437d23af8b7d65399b8c8ff7075279206a01b97",
        },
    },
}
FROZEN_V5_STAGE_PREIMAGES = {
    "development": {
        "extraction_records": 3_599,
        "extraction_jsonl_sha256": "53d827704e530d91a7847a193735718ea9df36f8fe421feaaa61393f3193d114",
        "embedding_records": 3_999,
        "embedding_jsonl_sha256": "99e44c8fd5b7d3935ab4299e0510d620643dd82a4e0ee47a389d078d739b44f4",
    },
    "fresh": {
        "extraction_records": 5_449,
        "extraction_jsonl_sha256": "9bccc338c1d1c8738ab1ea78f6283a462a278516c96b7b9d6832902041892942",
        "embedding_records": 5_999,
        "embedding_jsonl_sha256": "4b744d61a571d5cee122ad031a27535c529ab4c40703bfebda9b8c5a446a23bd",
    },
}
FROZEN_V5_DEVELOPMENT_SIDECARS = {
    "musique": {
        "path": ".ab_p5_cache/h3_relation_raw_musique.json",
        "file_sha256": "c44453d2534cd326000f65dfa7d3f02b879f4390cd0fbc067617ad84e0a6bd9e",
    },
    "2wiki": {
        "path": ".ab_p5_cache/h3_relation_raw_2wiki.json",
        "file_sha256": "212c43c5116d114e73d0b02e5fcd28580043ae306d3303fea0d76276715047ed",
    },
}
FROZEN_V5_FRESH_HOLDOUT = {
    "musique": {
        "path": ".ab_p5_cache/h3_b3/musique_fresh_manifest_v2.json",
        "manifest_file_sha256": "12bffedbce50be64019727f3a39309af0676e76ce3ef30e74bcb38932bea991c",
        "selected_manifest_id": "8aafec838c80d136ebea0dc8f084b7a3a088027f3876fa5ffab63ff1f7851537",
    },
    "2wiki": {
        "path": ".ab_p5_cache/h3_b3/2wiki_fresh_manifest_v2.json",
        "manifest_file_sha256": "2c1bed2236b0127209cae5f009dacfe41c03a2b38c401f993cb8f3aab1edc343",
        "selected_manifest_id": "4b0f41685aabb62cabf67497baf0a31776c3c9bd5195bef801dc9ae047998b47",
    },
}


class ManifestBuildError(ValueError):
    """A PRE_RUN input, path commitment, or publication invariant failed."""


@dataclass(frozen=True)
class ExtractorExecutionV1:
    endpoint: str
    model: str
    model_revision: str
    max_concurrency: int = 2
    timeout_seconds: float = 180.0
    max_tokens: int = 1024
    max_attempts: int = 2


FROZEN_V5_EXTRACTOR_EXECUTION = ExtractorExecutionV1(
    endpoint="http://127.0.0.1:18002/v1",
    model="Qwen/Qwen3.6-35B-A3B-FP8",
    model_revision="95a723d08a9490559dae23d0cff1d9466213d989",
    max_concurrency=2,
    timeout_seconds=180.0,
    max_tokens=1024,
    max_attempts=2,
)


@dataclass(frozen=True)
class ArcExecutionV1:
    endpoint: str
    max_concurrency: int = 2
    timeout_seconds: float = 180.0
    max_tokens: int = 96


def file_sha256(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_frozen_v5(actual: Any, expected: Any, *, label: str) -> None:
    """Reject a self-consistent value that differs from the V5 prereg."""

    if actual != expected:
        raise ManifestBuildError(f"{label} differs from frozen V5 preregistration")


def _validate_parent_evidence() -> None:
    """Require the exact parent protocols and refusals named by V5."""

    for binding in FROZEN_V5_PARENT_EVIDENCE:
        evidence_file, relative = _existing_root_file(
            REPO_ROOT / binding["path"], label="V5 parent evidence",
        )
        _require_frozen_v5(
            {"path": relative, "sha256": file_sha256(evidence_file)},
            binding,
            label=f"V5 parent evidence {binding['path']}",
        )


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _strict_json_file(path: Path, *, label: str) -> dict[str, Any]:
    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ManifestBuildError(
                    f"{label} contains duplicate JSON key {key!r}"
                )
            result[key] = value
        return result

    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=object_pairs)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestBuildError(f"cannot read {label} as strict JSON") from exc
    if not isinstance(value, dict):
        raise ManifestBuildError(f"{label} must be a JSON object")
    return value


def _existing_root_file(path: str | Path, *, label: str) -> tuple[Path, str]:
    declared = Path(path).expanduser()
    if declared.is_symlink():
        raise ManifestBuildError(f"{label} may not be a symlink")
    try:
        resolved = declared.resolve(strict=True)
        relative = resolved.relative_to(REPO_ROOT.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise ManifestBuildError(
            f"{label} must be an existing file under repository root"
        ) from exc
    if not resolved.is_file():
        raise ManifestBuildError(f"{label} must be a regular file")
    relative_text = relative.as_posix()
    if not relative_text or ".." in relative.parts:
        raise ManifestBuildError(f"{label} has a non-canonical relative path")
    return resolved, relative_text


def _future_root_path(value: str | Path, *, label: str) -> tuple[Path, str]:
    relative = Path(value)
    if (relative.is_absolute() or not relative.parts or ".." in relative.parts
            or relative.as_posix() != str(value)):
        raise ManifestBuildError(
            f"{label} must be a canonical repository-root-relative path"
        )
    root = REPO_ROOT.resolve(strict=True)
    candidate = root / relative
    try:
        candidate.relative_to(root)
    except ValueError as exc:  # pragma: no cover - lexical guards above
        raise ManifestBuildError(f"{label} escapes repository root") from exc
    cursor = candidate.parent
    while cursor != root:
        if cursor.is_symlink():
            raise ManifestBuildError(f"{label} has a symlinked parent")
        if cursor.exists():
            try:
                cursor.resolve(strict=True).relative_to(root)
            except (OSError, ValueError) as exc:
                raise ManifestBuildError(f"{label} parent escapes repository") from exc
        cursor = cursor.parent
    return candidate, relative.as_posix()


def _output_manifest_path(path: str | Path) -> Path:
    declared = Path(path).expanduser()
    absolute = declared if declared.is_absolute() else REPO_ROOT / declared
    if absolute.name in {"", ".", ".."}:
        raise ManifestBuildError("manifest output must name a root file")
    try:
        parent = absolute.parent.resolve(strict=True)
    except OSError as exc:
        raise ManifestBuildError("manifest output parent does not exist") from exc
    if parent != REPO_ROOT.resolve(strict=True):
        raise ManifestBuildError("PRE_RUN manifest must be written at repository root")
    if absolute.name != FROZEN_V5_MANIFEST_PATH:
        raise ManifestBuildError(
            "PRE_RUN manifest filename differs from frozen V5 preregistration"
        )
    return parent / absolute.name


def _keyed_paths(values: Sequence[str], *, label: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ManifestBuildError(f"{label} expects DATASET=PATH")
        key, path = value.split("=", 1)
        if key not in h3.DATASETS or not path or key in result:
            raise ManifestBuildError(f"invalid or duplicate {label}: {value!r}")
        result[key] = path
    if set(result) != set(h3.DATASETS):
        raise ManifestBuildError(
            f"{label} requires exactly {', '.join(h3.DATASETS)}"
        )
    return result


def _load_segments(
    paths: Mapping[str, str | Path], *, stage: str,
) -> tuple[dict[str, prep.PreparedSegmentV1], dict[str, dict[str, str]]]:
    if set(paths) != set(h3.DATASETS):
        raise ManifestBuildError(f"{stage} segments require both datasets")
    segments: dict[str, prep.PreparedSegmentV1] = {}
    bindings: dict[str, dict[str, str]] = {}
    for dataset in h3.DATASETS:
        source, relative = _existing_root_file(
            paths[dataset], label=f"{stage} segment {dataset}",
        )
        try:
            segment = h3.load_prepared_segment(source)
        except (OSError, ValueError, h3.ArtifactIntegrityError) as exc:
            raise ManifestBuildError(
                f"invalid {stage} segment for {dataset}: {exc}"
            ) from exc
        if segment.dataset != dataset or segment.split != stage:
            raise ManifestBuildError(
                f"{stage} segment dataset/split mismatch for {dataset}"
            )
        segments[dataset] = segment
        bindings[dataset] = {
            "path": relative, "sha256": file_sha256(source),
        }
    return segments, bindings


def _validate_fresh_manifest(
    path: Path,
    *,
    dataset: str,
    segment: prep.PreparedSegmentV1,
) -> tuple[dict[str, Any], str]:
    value = _strict_json_file(path, label=f"fresh manifest {dataset}")
    expected_keys = {field.name for field in fields(fresh.FreshHoldoutManifestV1)}
    if set(value) != expected_keys:
        raise ManifestBuildError(f"fresh manifest {dataset} root keys mismatch")
    if value.get("schema_version") != fresh.SCHEMA_VERSION:
        raise ManifestBuildError(f"fresh manifest {dataset} schema mismatch")
    if value.get("dataset") != dataset:
        raise ManifestBuildError(f"fresh manifest {dataset} dataset mismatch")
    selected_id = value.get("selected_manifest_sha256")
    hash_payload = {
        key: item for key, item in value.items()
        if key != "selected_manifest_sha256"
    }
    expected_id = sha256(
        canonical_json(hash_payload).encode("utf-8")
    ).hexdigest()
    if selected_id != expected_id:
        raise ManifestBuildError(f"fresh manifest {dataset} self-hash mismatch")
    audit = value.get("audit")
    counts = value.get("counts")
    if (not isinstance(audit, Mapping) or audit.get("all_disjoint") is not True
            or not isinstance(counts, Mapping)
            or counts.get("selected_rows") != len(segment.evaluation_rows)):
        raise ManifestBuildError(
            f"fresh manifest {dataset} disjoint/count gate failed"
        )
    if value.get("selected_qids") != [
        row.qid for row in segment.evaluation_rows
    ]:
        raise ManifestBuildError(f"fresh manifest {dataset} qid order mismatch")
    expected_paragraphs = [asdict(item) for item in segment.paragraphs]
    if value.get("compiler_paragraphs") != expected_paragraphs:
        raise ManifestBuildError(
            f"fresh manifest {dataset} compiler paragraphs mismatch"
        )
    compiler_payload = {
        "rows": value.get("compiler_rows"),
        "paragraphs": value.get("compiler_paragraphs"),
    }
    try:
        reval.assert_compiler_payload_clean(compiler_payload)
    except reval.RelationEvaluationError as exc:
        raise ManifestBuildError(
            f"fresh manifest {dataset} compiler payload leaks labels"
        ) from exc
    sidecar = value.get("evaluator_sidecar")
    if not isinstance(sidecar, list) or len(sidecar) != len(segment.evaluation_rows):
        raise ManifestBuildError(
            f"fresh manifest {dataset} evaluator sidecar count mismatch"
        )
    for binding, row in zip(sidecar, segment.evaluation_rows, strict=True):
        example = binding.get("example") if isinstance(binding, Mapping) else None
        if (not isinstance(binding, Mapping) or not isinstance(example, Mapping)
                or example.get("qid") != row.qid
                or example.get("question") != row.question
                or int(binding.get("benchmark_hop", -1)) != row.hop
                or binding.get("paragraph_source_ids")
                != list(row.paragraph_source_ids)
                or binding.get("gold_source_ids") != list(row.gold_source_ids)):
            raise ManifestBuildError(
                f"fresh manifest {dataset} evaluator binding mismatch: {row.qid}"
            )
    return value, str(selected_id)


def _stage_output_paths(prefix: str, stage: str) -> dict[str, str]:
    base = f"{prefix}/{stage}"
    embedding = f"{base}/embedding"
    return {
        "extraction_jsonl": f"{base}/extractions.jsonl",
        "extraction_open_receipt": f"{base}/extractions.open.json",
        "extraction_close_receipt": f"{base}/extractions.close.json",
        "embedding_run_directory": embedding,
        "embedding_npz": f"{embedding}/embeddings.npz",
        "embedding_receipt": f"{embedding}/embedding.receipt.json",
        "embedding_open_receipt": f"{base}/embedding.open.json",
        "embedding_close_receipt": f"{base}/embedding.close.json",
    }


def _arc_paths(prefix: str, dataset: str) -> dict[str, str]:
    base = f"{prefix}/fresh/arc/{dataset}"
    return {
        "packet": f"{base}.packet.json",
        "packet_seal": f"{base}.packet-seal.json",
        "ledger": f"{base}.ledger.jsonl",
        "adjudication": f"{base}.adjudication.json",
        "adjudication_close": f"{base}.adjudication-close.json",
    }


def _assert_future_outputs_clear(paths: Sequence[str]) -> None:
    for relative in paths:
        absolute, canonical = _future_root_path(
            relative, label="committed output path",
        )
        if canonical != relative:
            raise ManifestBuildError("committed output path is not canonical")
        if absolute.exists() or absolute.is_symlink():
            raise ManifestBuildError(
                f"PRE_RUN output already exists: {relative}"
            )


def build_manifest(
    *,
    protocol_path: str | Path,
    preflight_path: str | Path,
    bge_attestation_path: str | Path,
    qwen35_deployment_path: str | Path,
    development_segments: Mapping[str, str | Path],
    fresh_segments: Mapping[str, str | Path],
    development_sidecars: Mapping[str, str | Path],
    fresh_manifests: Mapping[str, str | Path],
    output_prefix: str,
    extractor: ExtractorExecutionV1,
    qwen27_deployment_path: str,
    arc: ArcExecutionV1,
) -> dict[str, Any]:
    """Derive an exact schema-v2 manifest without publishing it."""

    for label, mapping in (
        ("development sidecars", development_sidecars),
        ("fresh manifests", fresh_manifests),
    ):
        if set(mapping) != set(h3.DATASETS):
            raise ManifestBuildError(f"{label} require both datasets")

    protocol_file, protocol_relative = _existing_root_file(
        protocol_path, label="protocol",
    )
    _require_frozen_v5(
        {"path": protocol_relative, "sha256": file_sha256(protocol_file)},
        FROZEN_V5_PROTOCOL_BINDING,
        label="protocol binding",
    )
    _validate_parent_evidence()
    preflight_file, preflight_relative = _existing_root_file(
        preflight_path, label="preflight receipt",
    )
    _require_frozen_v5(
        preflight_relative, FROZEN_V5_PREFLIGHT_PATH,
        label="preflight receipt path",
    )
    bge_file, bge_relative = _existing_root_file(
        bge_attestation_path, label="BGE model attestation",
    )
    qwen35_file, qwen35_relative = _existing_root_file(
        qwen35_deployment_path, label="Qwen35 deployment receipt",
    )
    _require_frozen_v5(
        {"path": qwen35_relative, "sha256": file_sha256(qwen35_file)},
        FROZEN_V5_QWEN35_DEPLOYMENT,
        label="Qwen35 deployment receipt",
    )

    prefix_path = Path(output_prefix)
    if (prefix_path.is_absolute() or not prefix_path.parts
            or ".." in prefix_path.parts
            or prefix_path.as_posix() != output_prefix):
        raise ManifestBuildError(
            "output prefix must be canonical repository-root-relative"
        )
    prefix = prefix_path.as_posix().rstrip("/")
    _require_frozen_v5(
        prefix, FROZEN_V5_OUTPUT_PREFIX, label="output prefix",
    )
    qwen27_absolute, qwen27_relative = _future_root_path(
        qwen27_deployment_path, label="future Qwen27 deployment receipt",
    )
    prefix_absolute = REPO_ROOT.resolve(strict=True) / prefix_path
    try:
        qwen27_absolute.relative_to(prefix_absolute)
    except ValueError as exc:
        raise ManifestBuildError(
            "future Qwen27 receipt must be below output prefix"
        ) from exc

    development, development_bindings = _load_segments(
        development_segments, stage="development",
    )
    fresh_segments_loaded, fresh_bindings = _load_segments(
        fresh_segments, stage="fresh",
    )
    development_preimages = h3._preimage_receipt(tuple(
        development[dataset] for dataset in h3.DATASETS
    ))
    fresh_preimages = h3._preimage_receipt(tuple(
        fresh_segments_loaded[dataset] for dataset in h3.DATASETS
    ))
    _require_frozen_v5(
        development_bindings,
        FROZEN_V5_STAGE_SEGMENTS["development"],
        label="development segment bindings",
    )
    _require_frozen_v5(
        fresh_bindings,
        FROZEN_V5_STAGE_SEGMENTS["fresh"],
        label="fresh segment bindings",
    )
    _require_frozen_v5(
        development_preimages,
        FROZEN_V5_STAGE_PREIMAGES["development"],
        label="development preimages",
    )
    _require_frozen_v5(
        fresh_preimages,
        FROZEN_V5_STAGE_PREIMAGES["fresh"],
        label="fresh preimages",
    )

    sidecar_bindings: dict[str, dict[str, str]] = {}
    holdout_bindings: dict[str, dict[str, str]] = {}
    for dataset in h3.DATASETS:
        sidecar_file, sidecar_relative = _existing_root_file(
            development_sidecars[dataset],
            label=f"development sidecar {dataset}",
        )
        sidecar_bindings[dataset] = {
            "path": sidecar_relative,
            "file_sha256": file_sha256(sidecar_file),
        }
        manifest_file, manifest_relative = _existing_root_file(
            fresh_manifests[dataset], label=f"fresh manifest {dataset}",
        )
        _manifest, selected_id = _validate_fresh_manifest(
            manifest_file, dataset=dataset,
            segment=fresh_segments_loaded[dataset],
        )
        holdout_bindings[dataset] = {
            "path": manifest_relative,
            "manifest_file_sha256": file_sha256(manifest_file),
            "selected_manifest_id": selected_id,
        }
    _require_frozen_v5(
        sidecar_bindings,
        FROZEN_V5_DEVELOPMENT_SIDECARS,
        label="development sidecar bindings",
    )
    _require_frozen_v5(
        holdout_bindings,
        FROZEN_V5_FRESH_HOLDOUT,
        label="fresh holdout bindings",
    )

    try:
        preflight_receipt = h3.preflight.load_preflight_receipt(preflight_file)
    except (OSError, ValueError) as exc:
        raise ManifestBuildError(f"preflight receipt is invalid: {exc}") from exc
    code_sha256 = {
        relative: file_sha256(path)
        for relative, path in h3.FROZEN_CODE_MODULE_PATHS.items()
    }
    preflight_code = {
        item.path: item.sha256
        for item in preflight_receipt.implementation_modules
    }
    if preflight_code != code_sha256:
        raise ManifestBuildError(
            "preflight implementation snapshot differs from current code"
        )
    _require_frozen_v5(
        getattr(preflight_receipt, "gate_source_code_root_sha256", None),
        FROZEN_V5_GATE_SOURCE_CODE_ROOT_SHA256,
        label="preflight gate-source code root",
    )

    bge_raw = bge_file.read_bytes()
    bge_value = _strict_json_file(bge_file, label="BGE model attestation")
    if bge_raw != (canonical_json(bge_value) + "\n").encode("utf-8"):
        raise ManifestBuildError("BGE model attestation is not canonical JSONL")
    try:
        bge_attestation = bge.validate_model_attestation(
            bge_value, expected_model=bge.FROZEN_MODEL_ID,
            expected_revision=bge.FROZEN_MODEL_REVISION,
        )
    except (TypeError, ValueError) as exc:
        raise ManifestBuildError(f"BGE model attestation is invalid: {exc}") from exc
    if bge_attestation.get("weight_blob_sha256") != bge.FROZEN_WEIGHT_BLOB_SHA256:
        raise ManifestBuildError("BGE model attestation weight is not frozen BGE-M3")

    try:
        qwen35 = deployment.load_deployment_receipt(qwen35_file)
    except (OSError, ValueError, deployment.DeploymentAttestationError) as exc:
        raise ManifestBuildError(f"Qwen35 deployment receipt is invalid: {exc}") from exc
    if (qwen35.get("endpoint") != extractor.endpoint
            or qwen35.get("served_model") != extractor.model
            or qwen35.get("snapshot", {}).get("resolved_revision")
            != extractor.model_revision):
        raise ManifestBuildError(
            "extractor config differs from Qwen35 deployment receipt"
        )
    try:
        _require_frozen_v5(
            extractor,
            FROZEN_V5_EXTRACTOR_EXECUTION,
            label="extractor execution",
        )
        _require_frozen_v5(
            rex.SCHEMA_VERSION,
            FROZEN_V5_EXTRACTOR_SCHEMA_VERSION,
            label="extractor schema",
        )
        _require_frozen_v5(
            getattr(rex, "JOURNAL_SCHEMA_VERSION", None),
            FROZEN_V5_ATTEMPT_JOURNAL_SCHEMA_VERSION,
            label="attempt journal schema",
        )
        _require_frozen_v5(
            (getattr(rex, "START_EVENT", None), getattr(rex, "FINALIZE_EVENT", None)),
            FROZEN_V5_ATTEMPT_JOURNAL_EVENTS,
            label="attempt journal event types",
        )
        extractor_config = rex.ExtractorConfigV1(
            endpoint=extractor.endpoint, model=extractor.model,
            model_revision=extractor.model_revision,
            max_concurrency=extractor.max_concurrency,
            timeout_seconds=extractor.timeout_seconds,
            max_tokens=extractor.max_tokens,
            max_attempts=extractor.max_attempts,
            batch_size=1,
        )
    except (TypeError, ValueError) as exc:
        raise ManifestBuildError(f"extractor config is invalid: {exc}") from exc
    _require_frozen_v5(
        rex.prompt_sha256(),
        FROZEN_V5_EXTRACTOR_PROMPT_SHA256,
        label="extractor prompt SHA-256",
    )
    _require_frozen_v5(
        rex.config_sha256(extractor_config),
        FROZEN_V5_EXTRACTOR_CONFIG_SHA256,
        label="extractor config SHA-256",
    )

    embedding_execution = {
        "model": bge.FROZEN_MODEL_ID,
        "snapshot": bge.FROZEN_MODEL_REVISION,
        "dimension": FROZEN_BGE_DIMENSION,
        "pooling": bge.FROZEN_POOLING,
        "max_length": bge.FROZEN_MAX_LENGTH,
        "dtype": bge.FROZEN_DTYPE,
        "batch_size": bge.FROZEN_BATCH_SIZE,
        "producer_code_sha256": code_sha256["bge_m3_embed.py"],
    }
    embedding = {
        **embedding_execution,
        "model_attestation": bge_attestation,
        "model_attestation_receipt": {
            "path": bge_relative, "sha256": file_sha256(bge_file),
        },
        "config_sha256": sha256(
            canonical_json(embedding_execution).encode("utf-8")
        ).hexdigest(),
    }

    development_outputs = _stage_output_paths(prefix, "development")
    fresh_outputs = _stage_output_paths(prefix, "fresh")
    arc_paths = {
        dataset: _arc_paths(prefix, dataset) for dataset in h3.DATASETS
    }
    phase_paths = {
        "development_report": f"{prefix}/phases/development-report.json",
        "certificate_transition": f"{prefix}/phases/certificate-transition.json",
        "fresh_artifact_seal": f"{prefix}/phases/fresh-artifact-seal.json",
        "final_report": f"{prefix}/phases/final-report.json",
    }
    future_paths = [
        *development_outputs.values(), *fresh_outputs.values(),
        *phase_paths.values(), qwen27_relative,
        *(path for dataset_paths in arc_paths.values()
          for path in dataset_paths.values()),
    ]
    if len(future_paths) != len(set(future_paths)):
        raise ManifestBuildError("committed output paths are not globally unique")
    _assert_future_outputs_clear(future_paths)

    try:
        arc_config = arca.ArcAdjudicatorConfigV1(
            endpoint=arc.endpoint,
            deployment_attestation_sha256="0" * 64,
            model=arca.FROZEN_MODEL,
            model_revision=arca.FROZEN_MODEL_REVISION,
            max_concurrency=arc.max_concurrency,
            timeout_seconds=arc.timeout_seconds,
            max_tokens=arc.max_tokens,
        )
    except (TypeError, ValueError) as exc:
        raise ManifestBuildError(f"arc adjudicator config is invalid: {exc}") from exc
    arc_commitment = asdict(arc_config)
    arc_commitment.pop("deployment_attestation_sha256")
    arc_manifest = {
        "endpoint": arc_config.endpoint,
        "model": arc_config.model,
        "model_revision": arc_config.model_revision,
        "max_concurrency": arc_config.max_concurrency,
        "timeout_seconds": arc_config.timeout_seconds,
        "max_tokens": arc_config.max_tokens,
        "config_sha256": sha256(
            canonical_json(arc_commitment).encode("utf-8")
        ).hexdigest(),
    }

    extraction_deployment = {
        "path": qwen35_relative, "sha256": file_sha256(qwen35_file),
    }
    return {
        "schema_version": h3.MANIFEST_SCHEMA_VERSION,
        "status_at_freeze": "PRE_RUN_FROZEN",
        "protocol": {
            "path": protocol_relative, "sha256": file_sha256(protocol_file),
        },
        "code_sha256": code_sha256,
        "preflight": {
            "path": preflight_relative,
            "sha256": file_sha256(preflight_file),
            "receipt_id": preflight_receipt.receipt_id,
        },
        "evaluation_config": dict(h3.FROZEN_EVALUATION_CONFIG),
        "extractor": {
            "endpoint": extractor_config.endpoint,
            "model": extractor_config.model,
            "model_revision": extractor_config.model_revision,
            "max_concurrency": extractor_config.max_concurrency,
            "timeout_seconds": extractor_config.timeout_seconds,
            "max_tokens": extractor_config.max_tokens,
            "max_attempts": extractor_config.max_attempts,
            "prompt_sha256": rex.prompt_sha256(),
            "config_sha256": rex.config_sha256(extractor_config),
            "batch_size": 1,
        },
        "embedding": embedding,
        "stage_artifacts": {
            "development": {
                "segments": development_bindings,
                "preimages": development_preimages,
                "output_paths": development_outputs,
                "extraction_deployment_receipt": extraction_deployment,
            },
            "fresh": {
                "segments": fresh_bindings,
                "preimages": fresh_preimages,
                "output_paths": fresh_outputs,
                "extraction_deployment_receipt": extraction_deployment,
                "arc_deployment_receipt": {
                    "path": qwen27_relative,
                    "endpoint": arc.endpoint,
                    "model": arca.FROZEN_MODEL,
                    "model_revision": arca.FROZEN_MODEL_REVISION,
                },
                "arc_paths": arc_paths,
            },
        },
        "development_sidecars": sidecar_bindings,
        "fresh_holdout": holdout_bindings,
        "phase_paths": phase_paths,
        "arc_adjudicator": arc_manifest,
    }


def publish_manifest(path: str | Path, manifest: Mapping[str, Any]) -> str:
    """Validate a temporary canonical file, then publish that inode once."""

    output = _output_manifest_path(path)
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"PRE_RUN manifest is first-write-wins: {output}")
    encoded = (canonical_json(dict(manifest)) + "\n").encode("utf-8")
    descriptor, raw_temporary = tempfile.mkstemp(
        dir=REPO_ROOT, prefix=".h3-b3-manifest-validate-",
    )
    temporary = Path(raw_temporary)
    temporary_inode: int | None = None
    published = False
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        temporary_inode = temporary.stat().st_ino
        _fsync_directory(REPO_ROOT)
        try:
            loaded = h3.load_run_manifest(
                temporary, _allow_unpublished_candidate=True,
            )
        except (OSError, ValueError, h3.ArtifactIntegrityError) as exc:
            raise ManifestBuildError(
                f"candidate manifest failed frozen loader validation: {exc}"
            ) from exc
        if canonical_json(loaded) != canonical_json(dict(manifest)):
            raise ManifestBuildError("candidate manifest changed during validation")
        try:
            os.link(temporary, output)
        except FileExistsError as exc:
            raise FileExistsError(
                f"PRE_RUN manifest is first-write-wins: {output}"
            ) from exc
        _fsync_directory(REPO_ROOT)
        published = True
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if not published and output.exists() and temporary_inode is not None:
            # Remove only our inode if publication happened but the directory
            # durability step failed.
            try:
                if output.stat().st_ino == temporary_inode:
                    output.unlink()
            except (FileNotFoundError, OSError):
                pass
        temporary.unlink(missing_ok=True)
    return sha256(encoded).hexdigest()


def create_manifest(
    *, output_path: str | Path, **kwargs: Any,
) -> tuple[dict[str, Any], str]:
    manifest = build_manifest(**kwargs)
    digest = publish_manifest(output_path, manifest)
    return manifest, digest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--output-prefix", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--preflight", required=True)
    parser.add_argument("--bge-attestation", required=True)
    parser.add_argument("--qwen35-deployment", required=True)
    parser.add_argument("--development-segment", action="append", required=True)
    parser.add_argument("--fresh-segment", action="append", required=True)
    parser.add_argument("--development-sidecar", action="append", required=True)
    parser.add_argument("--fresh-manifest", action="append", required=True)
    parser.add_argument("--extractor-endpoint", required=True)
    parser.add_argument("--extractor-model", required=True)
    parser.add_argument("--extractor-model-revision", required=True)
    parser.add_argument("--extractor-max-concurrency", type=int, default=2)
    parser.add_argument("--extractor-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--extractor-max-tokens", type=int, default=1024)
    parser.add_argument("--extractor-max-attempts", type=int, default=2)
    parser.add_argument("--qwen27-deployment-path", required=True)
    parser.add_argument("--qwen27-endpoint", required=True)
    parser.add_argument("--arc-max-concurrency", type=int, default=2)
    parser.add_argument("--arc-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--arc-max-tokens", type=int, default=96)
    args = parser.parse_args(argv)

    manifest, digest = create_manifest(
        output_path=args.output,
        protocol_path=args.protocol,
        preflight_path=args.preflight,
        bge_attestation_path=args.bge_attestation,
        qwen35_deployment_path=args.qwen35_deployment,
        development_segments=_keyed_paths(
            args.development_segment, label="development segment",
        ),
        fresh_segments=_keyed_paths(
            args.fresh_segment, label="fresh segment",
        ),
        development_sidecars=_keyed_paths(
            args.development_sidecar, label="development sidecar",
        ),
        fresh_manifests=_keyed_paths(
            args.fresh_manifest, label="fresh manifest",
        ),
        output_prefix=args.output_prefix,
        extractor=ExtractorExecutionV1(
            endpoint=args.extractor_endpoint,
            model=args.extractor_model,
            model_revision=args.extractor_model_revision,
            max_concurrency=args.extractor_max_concurrency,
            timeout_seconds=args.extractor_timeout_seconds,
            max_tokens=args.extractor_max_tokens,
            max_attempts=args.extractor_max_attempts,
        ),
        qwen27_deployment_path=args.qwen27_deployment_path,
        arc=ArcExecutionV1(
            endpoint=args.qwen27_endpoint,
            max_concurrency=args.arc_max_concurrency,
            timeout_seconds=args.arc_timeout_seconds,
            max_tokens=args.arc_max_tokens,
        ),
    )
    print(canonical_json({
        "schema_version": MANIFEST_BUILDER_SCHEMA_VERSION,
        "manifest_schema_version": manifest["schema_version"],
        "manifest_sha256": digest,
        "output": str(_output_manifest_path(args.output)),
        "development_preimages": manifest["stage_artifacts"]["development"][
            "preimages"
        ],
        "fresh_preimages": manifest["stage_artifacts"]["fresh"]["preimages"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
