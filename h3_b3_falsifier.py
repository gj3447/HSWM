"""Confirmatory H3-B3 evidence-bound composition falsifier.

The runner consumes four frozen :class:`h3_b3_prepare.PreparedSegmentV1`
artifacts, a completed recorded-extraction JSONL, and a stable-ID BGE-M3 NPZ.
It deliberately keeps compiler and evaluator inputs separate: only
``(source_id, title, text)`` and already-recorded extractions reach B1/B3;
questions and gold evidence are joined afterwards by stable identity.

The development relation/evidence-disjoint ``val`` half selects one K=2
policy.  The development ``test`` half is a certificate gate.  The selected
policy is then frozen for the untouched fresh segment.  K=2 is always compared
with a matched K=1 run over the same B3 graph and budget, B1 K=2, and the
validation-selected strongest static baseline.  Topology, relation/role, and
second-edge controls are evaluated without re-selection.

This is a research falsifier, not a deployment certificate.  Even PASS permits
only the narrow phrase "evidence-bound relational composition retrieval
intelligence"; it does not establish answer reasoning or a general reasoner.

Longinus ReferenceSite: ``H3_B3_COMPOSITION_PREREG_2026-07-20.md``,
``H3_B3_V5_RESTART_PREREG_2026-07-20.md``, and the current first-write run
manifest.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import argparse
import json
import math
import os
from pathlib import Path
import re
from typing import Any

import numpy as np

import bge_m3_embed as bge
import claim_builder as cb
import composition as b1comp
import h3_arc_adjudicator as arca
import h3_artifact_lifecycle as lifecycle
import h3_b3_preflight as preflight
import h3_b3_prepare as prep
import h3_fresh_manifest as fresh_manifest
import metrics
import model_deployment_receipt as deployment_receipt
import recorded_llm_extractor as rex
import relation_eval as reval
import title_anchor_builder as tab
import typed_composition as typed
import world_ir
from world_ir import canonical_json


SCHEMA_VERSION = "hswm-h3-b3-falsifier/v1"
MANIFEST_SCHEMA_VERSION = "hswm-h3-b3-run-manifest/v3"
DEVELOPMENT_REPORT_SCHEMA_VERSION = "hswm-h3-b3-development-report/v1"
CERTIFICATE_TRANSITION_SCHEMA_VERSION = "hswm-h3-b3-certificate-transition/v1"
FRESH_ARTIFACT_SEAL_SCHEMA_VERSION = "hswm-h3-b3-fresh-artifact-seal/v1"
K_METRIC = 10
STAGES = ("development", "fresh")
DATASETS = ("musique", "2wiki")
PREIMAGE_RECEIPT_KEYS = {
    "extraction_records", "extraction_jsonl_sha256",
    "embedding_records", "embedding_jsonl_sha256",
}
HASHED_PATH_KEYS = {"path", "sha256"}
ARC_DEPLOYMENT_COMMITMENT_KEYS = {
    "path", "endpoint", "model", "model_revision",
}
STAGE_OUTPUT_PATH_KEYS = {
    "extraction_jsonl", "extraction_open_receipt", "extraction_close_receipt",
    "embedding_run_directory", "embedding_npz", "embedding_receipt",
    "embedding_open_receipt", "embedding_close_receipt",
}
DEVELOPMENT_STAGE_RECEIPT_KEYS = {
    "segments", "preimages", "output_paths",
    "extraction_deployment_receipt",
}
FRESH_STAGE_COMMITMENT_KEYS = {
    "segments", "preimages", "output_paths",
    "extraction_deployment_receipt", "arc_deployment_receipt", "arc_paths",
}
ARC_PATH_KEYS = {
    "packet", "packet_seal", "ledger", "adjudication", "adjudication_close",
}
PHASE_PATH_KEYS = {
    "development_report", "certificate_transition", "fresh_artifact_seal",
    "final_report",
}
ARC_ADJUDICATOR_MANIFEST_KEYS = {
    "endpoint", "model", "model_revision", "max_concurrency",
    "timeout_seconds", "max_tokens", "config_sha256",
}
MANIFEST_ROOT_KEYS = {
    "schema_version", "status_at_freeze", "protocol", "code_sha256",
    "preflight", "evaluation_config", "extractor", "embedding",
    "stage_artifacts", "development_sidecars", "fresh_holdout",
    "phase_paths", "arc_adjudicator",
}
FROZEN_CODE_MODULE_PATHS = {
    "h3_b3_falsifier.py": Path(__file__).resolve(),
    "h3_arc_adjudicator.py": Path(arca.__file__).resolve(),
    "h3_artifact_lifecycle.py": Path(lifecycle.__file__).resolve(),
    "h3_b3_preflight.py": Path(preflight.__file__).resolve(),
    "model_deployment_receipt.py": Path(deployment_receipt.__file__).resolve(),
    "bge_m3_embed.py": Path(bge.__file__).resolve(),
    "recorded_llm_extractor.py": Path(rex.__file__).resolve(),
    "h3_fresh_manifest.py": Path(fresh_manifest.__file__).resolve(),
    "h3_b3_prepare.py": Path(prep.__file__).resolve(),
    "claim_builder.py": Path(cb.__file__).resolve(),
    "typed_composition.py": Path(typed.__file__).resolve(),
    "title_anchor_builder.py": Path(tab.__file__).resolve(),
    "composition.py": Path(b1comp.__file__).resolve(),
    "relation_eval.py": Path(reval.__file__).resolve(),
    "metrics.py": Path(metrics.__file__).resolve(),
    "world_ir.py": Path(world_ir.__file__).resolve(),
}
POLICY_GRID = tuple(
    typed.TypedCompositionPolicyV1(
        seed_k=seed_k, max_hops=2, mu=mu, fanout_exponent=0.5,
        max_fanout=16, max_join_degree=8, min_typed_match=0.20,
    )
    for seed_k in (3, 10)
    for mu in (0.025, 0.05, 0.1)
)
NULL_SEEDS = (0, 1, 2, 3, 4)
PRIMARY_THRESHOLDS = {"ndcg10": 0.02, "asr10": 0.03}
MAX_ATTEMPT_CAP_TERMINAL_RATE = 0.005
MAX_ATTEMPT_CAP_TERMINAL_RATE_BY_DATASET = 0.01
ARC_AUDIT_SEED = "HSWM-H3-B3-ARC-AUDIT-2026-07-20-v1"
ARC_AUDIT_MODEL_REVISION = arca.FROZEN_MODEL_REVISION
RESAMPLING_SEED = 20_260_720
FROZEN_EVALUATION_CONFIG = {
    "split_seed": 42,
    "n_bootstrap": 10_000,
    "n_signflips": 100_000,
    "null_seeds": list(NULL_SEEDS),
    "resampling_seed": RESAMPLING_SEED,
}
FROZEN_BGE_DIMENSION = 1024
EMBEDDING_MANIFEST_KEYS = {
    "model", "snapshot", "dimension", "pooling", "max_length", "dtype",
    "batch_size", "producer_code_sha256", "model_attestation",
    "model_attestation_receipt", "config_sha256",
}
EXTRACTOR_MANIFEST_KEYS = {
    "endpoint", "model", "model_revision", "max_concurrency",
    "timeout_seconds", "max_tokens", "max_attempts", "prompt_sha256",
    "config_sha256", "batch_size",
}
FROZEN_V5_PROTOCOL_BINDING = {
    "path": "H3_B3_V5_RESTART_PREREG_2026-07-20.md",
    "sha256": "253ffd9e2550b30f6aa3c2d3144d4524a6f6c18ed9849f795553218e03e7eebb",
}
FROZEN_V5_MANIFEST_PATH = "H3_B3_RUN_MANIFEST_V5_2026-07-20.json"
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
FROZEN_V5_PREFLIGHT_PATH = (
    ".ab_p5_cache/h3_b3/H3_B3_PREFLIGHT_RECEIPT_V5_2026-07-20.json"
)
FROZEN_V5_GATE_SOURCE_CODE_ROOT_SHA256 = (
    "2218428e2767689ebd538d99aad54031c8dcefdfc2913b43ed5e843f3513ddf5"
)
FROZEN_V5_OUTPUT_PREFIX = (
    ".ab_p5_cache/h3_b3/runs/qwen35-r3-schema-v4-20260720"
)
FROZEN_V5_QWEN35_DEPLOYMENT = {
    "path": ".ab_p5_cache/h3_b3/QWEN35_DEPLOYMENT_RECEIPT_V2_2026-07-20_RETRY1.json",
    "sha256": "15d3880b211c5e21a4087caa55f008d4474323a3d220e05bb47343bcd1f1c0a6",
}
FROZEN_V5_BGE_RECEIPT = {
    "path": ".ab_p5_cache/h3_b3/BGE_M3_ATTESTATION_V2_2026-07-20.json",
    "sha256": "430ea4606b734d97ee8e07fe7a079ce8fcd18e77f6457a9f4cb95c3340824212",
}
FROZEN_V5_EXTRACTOR = {
    "endpoint": "http://127.0.0.1:18002/v1",
    "model": "Qwen/Qwen3.6-35B-A3B-FP8",
    "model_revision": "95a723d08a9490559dae23d0cff1d9466213d989",
    "max_concurrency": 2,
    "timeout_seconds": 180.0,
    "max_tokens": 1024,
    "max_attempts": 2,
    "prompt_sha256": "bebcbaf01be3d0a05c7edc4284ec18e244da951f243a124bd558b39aba34fc0c",
    "config_sha256": "185a15214301633f3353b80636438a4e5e1744633392753201256bf37267d2c0",
    "batch_size": 1,
}
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
TOKEN_RE = re.compile(r"(?u)\b\w\w+\b")


class ArtifactIntegrityError(RuntimeError):
    """A frozen input cannot be joined or reproduced exactly."""


class HarnessInvariantError(RuntimeError):
    """The evaluator or a causal control cannot express its declared test."""


class _DuplicateJSONKey(ValueError):
    """A JSON object repeated a key and therefore has ambiguous meaning."""


def _strict_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            raise _DuplicateJSONKey(f"duplicate JSON key: {key}")
        value[key] = child
    return value


def _strict_json_loads(raw: str, *, label: str) -> Any:
    try:
        return json.loads(raw, object_pairs_hook=_strict_json_object)
    except (json.JSONDecodeError, _DuplicateJSONKey) as exc:
        raise ArtifactIntegrityError(f"invalid {label}: {exc}") from exc


@dataclass(frozen=True)
class EvaluationConfigV1:
    split_seed: int = 42
    n_bootstrap: int = 10_000
    n_signflips: int = 100_000
    null_seeds: tuple[int, ...] = NULL_SEEDS
    resampling_seed: int = RESAMPLING_SEED

    def __post_init__(self) -> None:
        if self.n_bootstrap < 100 or self.n_signflips < 100:
            raise ValueError("bootstrap and sign-flip budgets must be >=100")
        if not self.null_seeds or any(seed < 0 for seed in self.null_seeds):
            raise ValueError("at least one non-negative null seed is required")
        if self.resampling_seed != RESAMPLING_SEED:
            raise ValueError(f"resampling_seed is frozen at {RESAMPLING_SEED}")


def _evaluation_config_receipt(config: EvaluationConfigV1) -> dict[str, Any]:
    """Return the JSON-shaped confirmatory configuration preimage."""

    value = asdict(config)
    value["null_seeds"] = list(value["null_seeds"])
    return value


def _require_frozen_evaluation_config(value: Mapping[str, Any]) -> None:
    if canonical_json(dict(value)) != canonical_json(FROZEN_EVALUATION_CONFIG):
        raise ArtifactIntegrityError(
            "confirmatory evaluation config differs from preregistration"
        )


@dataclass(frozen=True)
class EmbeddingArtifactV1:
    path: str
    file_sha256: str
    ids: tuple[str, ...]
    kinds: tuple[str, ...]
    text_sha256: tuple[str, ...]
    vectors: np.ndarray
    vector_by_id: Mapping[str, np.ndarray]
    receipt: Mapping[str, Any] | None


@dataclass(frozen=True)
class ExtractionArtifactV1:
    path: str
    file_sha256: str
    journal: rex.AttemptJournalV1
    records: tuple[rex.RecordedExtractionV1, ...]
    frozen_by_source: Mapping[str, cb.FrozenExtractionV1]
    accounting: Mapping[str, Any]


@dataclass(frozen=True)
class CompiledSegmentV1:
    segment: prep.PreparedSegmentV1
    target_ids: tuple[str, ...]
    ordinal_by_source: Mapping[str, int]
    b1_build: tab.TitleAnchorBuildV1
    b1_graph: b1comp.CompositionGraphV1
    b3_build: cb.ClaimGraphBuildV1
    b3_graph: typed.TypedCompositionGraphV1
    cosine: np.ndarray
    bm25: np.ndarray
    rrf: np.ndarray
    gold_ordinals: tuple[np.ndarray, ...]


def _audit_context(
    paragraph: tab.ParagraphInputV1,
    span: cb.ArcEvidenceSpanV1,
    *,
    radius: int = 96,
) -> dict[str, Any]:
    if span.text_scope != "body" or span.source_id != paragraph.source_id:
        raise HarnessInvariantError("shared-join audit selector is not body-bound")
    if paragraph.text[span.start:span.end] != span.exact:
        raise HarnessInvariantError("shared-join audit selector quote mismatch")
    start = max(0, span.start - radius)
    end = min(len(paragraph.text), span.end + radius)
    return {
        "source_id": paragraph.source_id,
        "title": paragraph.title,
        "context_start": start,
        "context_end": end,
        "context_exact": paragraph.text[start:end],
        "selector_start": span.start,
        "selector_end": span.end,
        "selector_exact": span.exact,
        "selector_start_in_context": span.start - start,
        "selector_end_in_context": span.end - start,
        "source_text_sha256": span.source_text_sha256,
    }


def build_arc_precision_audit_packet(
    build: cb.ClaimGraphBuildV1,
    *,
    dataset: str,
    max_audit_units: int = 100,
) -> dict[str, Any]:
    """Freeze query-label-free shared-join identity audit units.

    Only exact directed reverse duplicates collapse.  Every distinct emitted
    paragraph-pair/claim-role edge remains in the sampling frame, so a
    homonymous join spanning three documents cannot hide two bad pairs behind
    one favorable representative.
    """

    if dataset not in {"musique", "2wiki"} or not 1 <= max_audit_units <= 100:
        raise ValueError("dataset and max_audit_units<=100 are required")
    issues = cb.verify_claim_graph(build)
    if issues:
        raise HarnessInvariantError(f"cannot audit invalid claim graph: {issues[:3]}")
    paragraphs = {item.source_id: item for item in build.paragraphs}
    claims = {item.claim_id: item for item in build.nary_claims}
    audit_units: dict[tuple[Any, ...], cb.ParagraphRoleArcV1] = {}
    for arc in build.directed_arcs:
        if arc.origin != "verified_shared_entity":
            continue
        source_claim = claims.get(arc.claim_id or "")
        target_claim = claims.get(arc.target_claim_id or "")
        if source_claim is None or target_claim is None:
            raise HarnessInvariantError("shared join lacks both claim identities")
        source_side = (
            arc.subject_source_id, source_claim.claim_id,
            source_claim.predicate.exact, arc.source_evidence_span.role,
            arc.source_evidence_span.start, arc.source_evidence_span.end,
            arc.source_evidence_span.exact,
        )
        target_side = (
            arc.object_source_id, target_claim.claim_id,
            target_claim.predicate.exact, arc.target_evidence_span.role,
            arc.target_evidence_span.start, arc.target_evidence_span.end,
            arc.target_evidence_span.exact,
        )
        unit_key = (arc.join_entity_id, *sorted((source_side, target_side)))
        old = audit_units.get(unit_key)
        if old is None or arc.arc_id < old.arc_id:
            audit_units[unit_key] = arc
    ordered_units = sorted(
        audit_units,
        key=lambda unit: (
            sha256(
                f"{ARC_AUDIT_SEED}|{dataset}|{canonical_json(unit)}".encode()
            ).hexdigest(),
            canonical_json(unit),
        ),
    )[:max_audit_units]
    items: list[dict[str, Any]] = []
    for unit_key in ordered_units:
        representative = audit_units[unit_key]
        join_id = representative.join_entity_id
        source_claim = claims.get(representative.claim_id or "")
        target_claim = claims.get(representative.target_claim_id or "")
        if source_claim is None or target_claim is None:
            raise HarnessInvariantError("shared join lacks both claim identities")
        left = _audit_context(
            paragraphs[representative.subject_source_id],
            representative.source_evidence_span,
        )
        right = _audit_context(
            paragraphs[representative.object_source_id],
            representative.target_evidence_span,
        )
        item_payload = {
            "dataset": dataset,
            "join_entity_id": join_id,
            "normalized_surface": representative.source_evidence_span.normalized_surface,
            "source_claim_id": source_claim.claim_id,
            "target_claim_id": target_claim.claim_id,
            "source_predicate_exact": source_claim.predicate.exact,
            "target_predicate_exact": target_claim.predicate.exact,
            "source_role": representative.source_evidence_span.role,
            "target_role": representative.target_evidence_span.role,
            "left_context": left,
            "right_context": right,
        }
        item_id = sha256(canonical_json(item_payload).encode("utf-8")).hexdigest()
        items.append({"audit_item_id": item_id, **item_payload})
    body = {
        "schema_version": "hswm-h3-b3-arc-audit-packet/v1",
        "seed": ARC_AUDIT_SEED,
        "dataset": dataset,
        "sampling_unit": "unique emitted shared-join source pair",
        "max_audit_units": max_audit_units,
        "n_available_audit_units": len(audit_units),
        "n_sampled": len(items),
        "evaluation_labels_included": False,
        "items": items,
    }
    reval.assert_compiler_payload_clean(body)
    return {**body, "packet_sha256": sha256(
        canonical_json(body).encode("utf-8")
    ).hexdigest()}


def score_arc_precision_audit(
    packet: Mapping[str, Any],
    adjudication: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Score independent query-label-blind adjudication with a Wilson95 gate."""

    item_ids = tuple(str(item["audit_item_id"]) for item in packet.get("items", ()))
    if not item_ids:
        return {
            "admitted": False, "reason": "no shared joins available to audit",
            "n": 0, "correct": 0, "precision": None, "wilson95": None,
        }
    if adjudication is None:
        return {
            "admitted": False, "reason": "adjudication absent",
            "n": len(item_ids), "correct": None, "precision": None,
            "wilson95": None,
        }
    try:
        validated = arca.validate_adjudication(dict(adjudication), dict(packet))
    except (arca.AdjudicationIntegrityError, arca.PacketIntegrityError) as exc:
        raise ArtifactIntegrityError(
            f"arc adjudication does not bind audit packet: {exc}"
        ) from exc
    judgments = validated["judgments"]
    by_id = {str(value["audit_item_id"]): value for value in judgments}
    n = len(item_ids)
    correct = sum(by_id[item_id]["correct"] is True for item_id in item_ids)
    unclear = sum(by_id[item_id]["decision"] == "UNCLEAR" for item_id in item_ids)
    point = correct / n
    z = 1.959963984540054
    denominator = 1.0 + z * z / n
    centre = point + z * z / (2.0 * n)
    margin = z * math.sqrt(point * (1.0 - point) / n + z * z / (4.0 * n * n))
    lower = (centre - margin) / denominator
    upper = (centre + margin) / denominator
    admitted = point >= 0.95 and lower >= 0.90
    return {
        "admitted": admitted,
        "reason": None if admitted else "precision gate failed",
        "n": n, "correct": correct, "precision": round(point, 6),
        "unclear_counted_incorrect": unclear,
        "wilson95": [round(lower, 6), round(upper, 6)],
        "required": {"precision": 0.95, "wilson95_lower": 0.90},
        "adjudication_receipt": {
            "adjudicator": validated["adjudicator"],
            "model_revision": ARC_AUDIT_MODEL_REVISION,
            "prompt_sha256": validated["prompt_sha256"],
            "config_sha256": validated["config_sha256"],
            "adjudication_sha256": validated["adjudication_sha256"],
            "raw_response_sha256": [
                value["receipt"]["raw_response_sha256"] for value in judgments
            ],
        },
    }


def _file_sha256(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _array_sha256(value: np.ndarray) -> str:
    array = np.ascontiguousarray(np.asarray(value, dtype="<f8"))
    return sha256(array.tobytes(order="C")).hexdigest()


def _strict_root(value: Any, keys: set[str], *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ArtifactIntegrityError(
            f"{label} keys must be exactly {sorted(keys)}"
        )
    return value


def _require_sha256(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ArtifactIntegrityError(f"{label} must be a lowercase SHA-256")
    return value


def _validate_preimage_receipt_schema(
    value: Any,
    *,
    label: str,
) -> Mapping[str, Any]:
    receipt = _strict_root(value, PREIMAGE_RECEIPT_KEYS, label=label)
    for key in ("extraction_records", "embedding_records"):
        if type(receipt[key]) is not int or receipt[key] <= 0:
            raise ArtifactIntegrityError(f"{label}.{key} must be a positive int")
    if receipt["embedding_records"] < receipt["extraction_records"]:
        raise ArtifactIntegrityError(
            f"{label}.embedding_records cannot be smaller than extraction_records"
        )
    _require_sha256(
        receipt["extraction_jsonl_sha256"],
        label=f"{label}.extraction_jsonl_sha256",
    )
    _require_sha256(
        receipt["embedding_jsonl_sha256"],
        label=f"{label}.embedding_jsonl_sha256",
    )
    return receipt


def _validate_hashed_path_receipt(
    value: Any,
    *,
    label: str,
) -> Mapping[str, Any]:
    receipt = _strict_root(value, HASHED_PATH_KEYS, label=label)
    path = receipt["path"]
    if (not isinstance(path, str) or not path
            or Path(path).is_absolute() or ".." in Path(path).parts
            or Path(path).as_posix() != path):
        raise ArtifactIntegrityError(
            f"{label}.path must be canonical root-relative"
        )
    _require_sha256(receipt["sha256"], label=f"{label}.sha256")
    return receipt


def _validate_committed_path(value: Any, *, label: str) -> str:
    if (not isinstance(value, str) or not value
            or Path(value).is_absolute() or ".." in Path(value).parts
            or Path(value).as_posix() != value):
        raise ArtifactIntegrityError(
            f"{label} must be a canonical root-relative path"
        )
    return value


def _validate_stage_artifact_receipts(value: Any) -> Mapping[str, Any]:
    """Validate PRE_RUN commitments without circular output hashes.

    OPEN/CLOSE/output paths are frozen, but their receipts and outputs do not
    exist yet.  Their hashes enter the certificate transition (development)
    or fresh artifact seal (fresh) only after the committed producer closes.
    """

    stages = _strict_root(value, set(STAGES), label="stage_artifacts")
    for stage, keys in (
        ("development", DEVELOPMENT_STAGE_RECEIPT_KEYS),
        ("fresh", FRESH_STAGE_COMMITMENT_KEYS),
    ):
        receipt = _strict_root(stages[stage], keys, label=f"stage_artifacts.{stage}")
        segments = _strict_root(
            receipt["segments"], set(DATASETS),
            label=f"stage_artifacts.{stage}.segments",
        )
        for dataset in DATASETS:
            _validate_hashed_path_receipt(
                segments[dataset],
                label=f"stage_artifacts.{stage}.segments.{dataset}",
            )
        _validate_preimage_receipt_schema(
            receipt["preimages"],
            label=f"stage_artifacts.{stage}.preimages",
        )
        output_paths = _strict_root(
            receipt["output_paths"], STAGE_OUTPUT_PATH_KEYS,
            label=f"stage_artifacts.{stage}.output_paths",
        )
        for key, path in output_paths.items():
            _validate_committed_path(
                path, label=f"stage_artifacts.{stage}.output_paths.{key}",
            )
        _validate_hashed_path_receipt(
            receipt["extraction_deployment_receipt"],
            label=f"stage_artifacts.{stage}.extraction_deployment_receipt",
        )
    fresh = stages["fresh"]
    arc_deployment = _strict_root(
        fresh["arc_deployment_receipt"], ARC_DEPLOYMENT_COMMITMENT_KEYS,
        label="stage_artifacts.fresh.arc_deployment_receipt",
    )
    _validate_committed_path(
        arc_deployment["path"],
        label="stage_artifacts.fresh.arc_deployment_receipt.path",
    )
    if (arc_deployment["model"] != arca.FROZEN_MODEL
            or arc_deployment["model_revision"] != arca.FROZEN_MODEL_REVISION
            or not isinstance(arc_deployment["endpoint"], str)
            or not arc_deployment["endpoint"]):
        raise ArtifactIntegrityError("fresh arc deployment commitment mismatch")
    arc_paths = _strict_root(
        fresh["arc_paths"], set(DATASETS),
        label="stage_artifacts.fresh.arc_paths",
    )
    for dataset in DATASETS:
        paths = _strict_root(
            arc_paths[dataset], ARC_PATH_KEYS,
            label=f"stage_artifacts.fresh.arc_paths.{dataset}",
        )
        for key, path in paths.items():
            _validate_committed_path(
                path, label=f"stage_artifacts.fresh.arc_paths.{dataset}.{key}",
            )
    return stages


def _resolve_hashed_path(
    manifest_path: Path,
    value: Any,
    *,
    label: str,
) -> Path:
    receipt = _validate_hashed_path_receipt(value, label=label)
    path = (manifest_path.parent / receipt["path"]).resolve()
    if not path.is_file() or _file_sha256(path) != receipt["sha256"]:
        raise ArtifactIntegrityError(f"{label} file hash mismatch")
    return path


def _validate_model_attestation(
    value: Any,
    *,
    label: str,
    expected_model: str | None = None,
    expected_revision: str | None = None,
) -> Mapping[str, Any]:
    try:
        return bge.validate_model_attestation(
            value, expected_model=expected_model,
            expected_revision=expected_revision,
        )
    except (TypeError, ValueError) as exc:
        raise ArtifactIntegrityError(f"{label} failed validation: {exc}") from exc


def _validate_deployment_attestation(
    path: Path,
    *,
    expected_model: str,
    expected_revision: str,
    label: str,
) -> Mapping[str, Any]:
    try:
        receipt = deployment_receipt.load_deployment_receipt(path)
    except (OSError, ValueError, deployment_receipt.DeploymentAttestationError) as exc:
        raise ArtifactIntegrityError(f"{label} failed validation: {exc}") from exc
    snapshot = receipt["snapshot"]
    if (receipt["served_model"] != expected_model
            or snapshot["resolved_revision"] != expected_revision
            or receipt["advertised_models"].count(expected_model) != 1):
        raise ArtifactIntegrityError(f"{label} model/revision mismatch")
    return receipt


def _validate_embedding_manifest(
    manifest_path: Path,
    value: Any,
) -> Mapping[str, Any]:
    embedding = _strict_root(value, EMBEDDING_MANIFEST_KEYS, label="embedding")
    if (embedding["model"] != bge.FROZEN_MODEL_ID
            or embedding["snapshot"] != bge.FROZEN_MODEL_REVISION
            or embedding["pooling"] != bge.FROZEN_POOLING
            or embedding["max_length"] != bge.FROZEN_MAX_LENGTH
            or embedding["dtype"] != bge.FROZEN_DTYPE
            or embedding["batch_size"] != bge.FROZEN_BATCH_SIZE
            or type(embedding["dimension"]) is not int
            or embedding["dimension"] != FROZEN_BGE_DIMENSION):
        raise ArtifactIntegrityError("embedding frozen execution contract mismatch")
    if embedding["producer_code_sha256"] != _file_sha256(Path(bge.__file__)):
        raise ArtifactIntegrityError("embedding producer code hash mismatch")
    execution_config = {
        key: embedding[key] for key in (
            "model", "snapshot", "dimension", "pooling", "max_length", "dtype",
            "batch_size", "producer_code_sha256",
        )
    }
    if embedding["config_sha256"] != sha256(
        canonical_json(execution_config).encode("utf-8")
    ).hexdigest():
        raise ArtifactIntegrityError("embedding config SHA commitment mismatch")
    attestation_path = _resolve_hashed_path(
        manifest_path, embedding["model_attestation_receipt"],
        label="embedding.model_attestation_receipt",
    )
    try:
        attestation_file = json.loads(attestation_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactIntegrityError(f"invalid embedding model attestation: {exc}") from exc
    attestation = _validate_model_attestation(
        embedding["model_attestation"], label="embedding.model_attestation",
        expected_model=bge.FROZEN_MODEL_ID,
        expected_revision=bge.FROZEN_MODEL_REVISION,
    )
    if (canonical_json(attestation_file) != canonical_json(attestation)
            or attestation["resolved_model_id"] != embedding["model"]
            or attestation["resolved_revision"] != embedding["snapshot"]):
        raise ArtifactIntegrityError("embedding model attestation commitment mismatch")
    return embedding


def _v5_stage_output_paths(stage: str) -> dict[str, str]:
    base = f"{FROZEN_V5_OUTPUT_PREFIX}/{stage}"
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


def _v5_arc_paths(dataset: str) -> dict[str, str]:
    base = f"{FROZEN_V5_OUTPUT_PREFIX}/fresh/arc/{dataset}"
    return {
        "packet": f"{base}.packet.json",
        "packet_seal": f"{base}.packet-seal.json",
        "ledger": f"{base}.ledger.jsonl",
        "adjudication": f"{base}.adjudication.json",
        "adjudication_close": f"{base}.adjudication-close.json",
    }


def _require_frozen_v5_manifest_contract(
    *,
    manifest_path: Path,
    allow_unpublished_candidate: bool,
    protocol: Mapping[str, Any],
    preflight_binding: Mapping[str, Any],
    preflight_receipt: preflight.PreflightReceiptV1,
    extractor: Mapping[str, Any],
    embedding: Mapping[str, Any],
    stages: Mapping[str, Any],
    phase_paths: Mapping[str, Any],
    sidecars: Mapping[str, Any],
    holdouts: Mapping[str, Any],
    arc_config: Mapping[str, Any],
) -> None:
    """Reject self-consistent PRE_RUN drift from the exact V5 amendment."""

    repository_root = Path(__file__).resolve().parent
    try:
        parent = manifest_path.parent.resolve(strict=True)
    except OSError as exc:
        raise ArtifactIntegrityError("V5 manifest parent cannot be resolved") from exc
    if parent != repository_root:
        raise ArtifactIntegrityError("V5 manifest must be at repository root")
    if allow_unpublished_candidate:
        if not manifest_path.name.startswith(".h3-b3-manifest-validate-"):
            raise ArtifactIntegrityError("invalid unpublished V5 manifest candidate")
    elif manifest_path.name != FROZEN_V5_MANIFEST_PATH:
        raise ArtifactIntegrityError("V5 manifest path differs from preregistration")
    for binding in FROZEN_V5_PARENT_EVIDENCE:
        evidence_path = repository_root / binding["path"]
        if (not evidence_path.is_file()
                or _file_sha256(evidence_path) != binding["sha256"]):
            raise ArtifactIntegrityError(
                f"V5 parent evidence hash mismatch: {binding['path']}"
            )

    expected_phase_paths = {
        "development_report": (
            f"{FROZEN_V5_OUTPUT_PREFIX}/phases/development-report.json"
        ),
        "certificate_transition": (
            f"{FROZEN_V5_OUTPUT_PREFIX}/phases/certificate-transition.json"
        ),
        "fresh_artifact_seal": (
            f"{FROZEN_V5_OUTPUT_PREFIX}/phases/fresh-artifact-seal.json"
        ),
        "final_report": f"{FROZEN_V5_OUTPUT_PREFIX}/phases/final-report.json",
    }
    expected_arc = {
        "endpoint": "http://127.0.0.1:18001/v1",
        "model": arca.FROZEN_MODEL,
        "model_revision": arca.FROZEN_MODEL_REVISION,
        "max_concurrency": 2,
        "timeout_seconds": 180.0,
        "max_tokens": 96,
        "config_sha256": (
            "b771d2a8e90502344454b55a8f7076d4b16dbf57dab33c8af3e109522598153d"
        ),
    }
    if dict(protocol) != FROZEN_V5_PROTOCOL_BINDING:
        raise ArtifactIntegrityError("protocol differs from frozen V5 amendment")
    if preflight_binding["path"] != FROZEN_V5_PREFLIGHT_PATH:
        raise ArtifactIntegrityError("preflight path differs from frozen V5 amendment")
    if (preflight_receipt.gate_source_code_root_sha256
            != FROZEN_V5_GATE_SOURCE_CODE_ROOT_SHA256):
        raise ArtifactIntegrityError("preflight gate source root differs from V5")
    if (rex.SCHEMA_VERSION != "hswm-recorded-llm-extractor/v4"
            or rex.JOURNAL_SCHEMA_VERSION
            != "hswm-recorded-llm-attempt-journal/v1"
            or (rex.START_EVENT, rex.FINALIZE_EVENT) != ("START", "FINALIZE")):
        raise ArtifactIntegrityError("extractor/journal schema differs from V5")
    if dict(extractor) != FROZEN_V5_EXTRACTOR:
        raise ArtifactIntegrityError("extractor differs from frozen V5 amendment")
    if (embedding["model_attestation_receipt"] != FROZEN_V5_BGE_RECEIPT):
        raise ArtifactIntegrityError("BGE attestation receipt differs from V5")
    for stage in STAGES:
        if (stages[stage]["segments"] != FROZEN_V5_STAGE_SEGMENTS[stage]
                or stages[stage]["preimages"] != FROZEN_V5_STAGE_PREIMAGES[stage]
                or stages[stage]["output_paths"] != _v5_stage_output_paths(stage)
                or stages[stage]["extraction_deployment_receipt"]
                != FROZEN_V5_QWEN35_DEPLOYMENT):
            raise ArtifactIntegrityError(
                f"{stage} artifacts differ from frozen V5 amendment"
            )
    fresh_arc_deployment = stages["fresh"]["arc_deployment_receipt"]
    if fresh_arc_deployment != {
        "path": f"{FROZEN_V5_OUTPUT_PREFIX}/fresh/qwen27-deployment-v2.json",
        "endpoint": "http://127.0.0.1:18001/v1",
        "model": arca.FROZEN_MODEL,
        "model_revision": arca.FROZEN_MODEL_REVISION,
    }:
        raise ArtifactIntegrityError("fresh ARC deployment differs from V5")
    if stages["fresh"]["arc_paths"] != {
        dataset: _v5_arc_paths(dataset) for dataset in DATASETS
    }:
        raise ArtifactIntegrityError("fresh ARC paths differ from V5")
    if dict(phase_paths) != expected_phase_paths:
        raise ArtifactIntegrityError("phase paths differ from frozen V5 amendment")
    if dict(sidecars) != FROZEN_V5_DEVELOPMENT_SIDECARS:
        raise ArtifactIntegrityError("development sidecars differ from V5")
    if dict(holdouts) != FROZEN_V5_FRESH_HOLDOUT:
        raise ArtifactIntegrityError("fresh holdouts differ from V5")
    if dict(arc_config) != expected_arc:
        raise ArtifactIntegrityError("ARC execution differs from frozen V5 amendment")


def load_run_manifest(
    path: str | Path, *, _allow_unpublished_candidate: bool = False,
) -> dict[str, Any]:
    manifest_path = Path(path)
    try:
        value = _strict_json_loads(
            manifest_path.read_text(encoding="utf-8"), label="run manifest",
        )
    except OSError as exc:
        raise ArtifactIntegrityError(f"invalid run manifest: {exc}") from exc
    _strict_root(value, MANIFEST_ROOT_KEYS, label="run manifest")
    if value.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ArtifactIntegrityError("run manifest schema mismatch")
    if value.get("status_at_freeze") != "PRE_RUN_FROZEN":
        raise ArtifactIntegrityError("run manifest was not frozen before the run")
    protocol = value.get("protocol")
    if not isinstance(protocol, Mapping):
        raise ArtifactIntegrityError("run manifest lacks protocol receipt")
    _strict_root(protocol, HASHED_PATH_KEYS, label="protocol")
    _validate_committed_path(protocol.get("path"), label="protocol.path")
    protocol_path = manifest_path.parent / str(protocol.get("path", ""))
    if not protocol_path.is_file() or _file_sha256(protocol_path) != protocol.get("sha256"):
        raise ArtifactIntegrityError("preregistered protocol hash mismatch")
    code_hashes = value.get("code_sha256")
    if (not isinstance(code_hashes, Mapping)
            or set(code_hashes) != set(FROZEN_CODE_MODULE_PATHS)):
        raise ArtifactIntegrityError(
            "run manifest code_sha256 keys must exactly bind imported modules"
        )
    repository_root = Path(__file__).resolve().parent
    for relative, imported_path in FROZEN_CODE_MODULE_PATHS.items():
        key_path = Path(relative)
        if (key_path.is_absolute() or ".." in key_path.parts
                or key_path.as_posix() != relative):
            raise ArtifactIntegrityError(
                f"frozen code path is not canonical root-relative: {relative}"
            )
        source = (repository_root / key_path).resolve()
        if source != imported_path:
            raise ArtifactIntegrityError(
                f"frozen code path does not resolve to imported module: {relative}"
            )
        expected = _require_sha256(
            code_hashes[relative], label=f"code_sha256.{relative}",
        )
        if not source.is_file() or _file_sha256(source) != expected:
            raise ArtifactIntegrityError(f"frozen code hash mismatch: {relative}")

    preflight_binding = _strict_root(
        value.get("preflight"), {"path", "sha256", "receipt_id"},
        label="preflight",
    )
    preflight_path = _resolve_hashed_path(
        manifest_path,
        {"path": preflight_binding["path"], "sha256": preflight_binding["sha256"]},
        label="preflight",
    )
    try:
        preflight_receipt = preflight.load_preflight_receipt(preflight_path)
    except (OSError, ValueError) as exc:
        raise ArtifactIntegrityError(f"preflight receipt failed validation: {exc}") from exc
    if preflight_receipt.receipt_id != preflight_binding["receipt_id"]:
        raise ArtifactIntegrityError("preflight receipt id mismatch")
    preflight_modules = {
        item.path: item.sha256 for item in preflight_receipt.implementation_modules
    }
    manifest_code_root = lifecycle.authorization_code_root(code_hashes)
    if (preflight_modules != dict(code_hashes)
            or preflight_receipt.implementation_code_root_sha256
            != manifest_code_root):
        raise ArtifactIntegrityError(
            "preflight implementation code root differs from run manifest"
        )

    extractor = _strict_root(
        value.get("extractor"), EXTRACTOR_MANIFEST_KEYS, label="extractor",
    )
    if int(extractor.get("batch_size", -1)) != 1:
        raise ArtifactIntegrityError("confirmatory extractor batch_size must be exactly 1")
    if (not isinstance(extractor["model"], str) or not extractor["model"]
            or not isinstance(extractor["model_revision"], str)
            or not extractor["model_revision"]):
        raise ArtifactIntegrityError("extractor model/revision are required")
    for key in ("prompt_sha256", "config_sha256"):
        _require_sha256(extractor[key], label=f"extractor.{key}")
    try:
        extractor_config = rex.ExtractorConfigV1(
            endpoint=extractor["endpoint"],
            model=extractor["model"],
            model_revision=extractor["model_revision"],
            max_concurrency=extractor["max_concurrency"],
            timeout_seconds=extractor["timeout_seconds"],
            max_tokens=extractor["max_tokens"],
            max_attempts=extractor["max_attempts"],
            batch_size=extractor["batch_size"],
        )
    except (TypeError, ValueError) as exc:
        raise ArtifactIntegrityError(f"extractor config invalid: {exc}") from exc
    if (extractor["prompt_sha256"] != rex.prompt_sha256()
            or extractor["config_sha256"] != rex.config_sha256(extractor_config)):
        raise ArtifactIntegrityError("extractor execution commitment mismatch")
    embedding = _validate_embedding_manifest(manifest_path, value.get("embedding"))
    stages = _validate_stage_artifact_receipts(value.get("stage_artifacts"))
    for stage in STAGES:
        deployment_path = _resolve_hashed_path(
            manifest_path, stages[stage]["extraction_deployment_receipt"],
            label=f"stage_artifacts.{stage}.extraction_deployment_receipt",
        )
        deployment = _validate_deployment_attestation(
            deployment_path, expected_model=extractor["model"],
            expected_revision=extractor["model_revision"],
            label=f"{stage} extraction deployment attestation",
        )
        if deployment.get("endpoint") != extractor["endpoint"]:
            raise ArtifactIntegrityError(
                f"{stage} extraction deployment endpoint mismatch"
            )
    if "preimages" in value:
        raise ArtifactIntegrityError(
            "flat preimages are forbidden; use exact stage_artifacts receipts"
        )
    evaluation_config = value.get("evaluation_config")
    if not isinstance(evaluation_config, Mapping):
        raise ArtifactIntegrityError(
            "run manifest must freeze the confirmatory evaluation config"
        )
    _require_frozen_evaluation_config(evaluation_config)
    phase_paths = _strict_root(
        value.get("phase_paths"), PHASE_PATH_KEYS, label="phase_paths",
    )
    for key, committed in phase_paths.items():
        _validate_committed_path(committed, label=f"phase_paths.{key}")

    sidecars = _strict_root(
        value.get("development_sidecars"), set(DATASETS),
        label="development_sidecars",
    )
    for dataset in DATASETS:
        _resolve_hashed_path(
            manifest_path,
            {
                "path": _strict_root(
                    sidecars[dataset], {"path", "file_sha256"},
                    label=f"development_sidecars.{dataset}",
                )["path"],
                "sha256": sidecars[dataset]["file_sha256"],
            },
            label=f"development_sidecars.{dataset}",
        )
    holdouts = _strict_root(
        value.get("fresh_holdout"), set(DATASETS), label="fresh_holdout",
    )
    for dataset in DATASETS:
        holdout = _strict_root(
            holdouts[dataset],
            {"path", "manifest_file_sha256", "selected_manifest_id"},
            label=f"fresh_holdout.{dataset}",
        )
        _resolve_hashed_path(
            manifest_path,
            {"path": holdout["path"], "sha256": holdout["manifest_file_sha256"]},
            label=f"fresh_holdout.{dataset}",
        )
        _require_sha256(
            holdout["selected_manifest_id"],
            label=f"fresh_holdout.{dataset}.selected_manifest_id",
        )

    arc_config = _strict_root(
        value.get("arc_adjudicator"), ARC_ADJUDICATOR_MANIFEST_KEYS,
        label="arc_adjudicator",
    )
    try:
        frozen_arc_config = arca.ArcAdjudicatorConfigV1(
            endpoint=arc_config["endpoint"],
            deployment_attestation_sha256="0" * 64,
            model=arc_config["model"],
            model_revision=arc_config["model_revision"],
            max_concurrency=arc_config["max_concurrency"],
            timeout_seconds=arc_config["timeout_seconds"],
            max_tokens=arc_config["max_tokens"],
        )
    except (TypeError, ValueError) as exc:
        raise ArtifactIntegrityError(f"arc adjudicator config invalid: {exc}") from exc
    frozen_config_commitment = asdict(frozen_arc_config)
    frozen_config_commitment.pop("deployment_attestation_sha256")
    if (arc_config["model"] != arca.FROZEN_MODEL
            or arc_config["model_revision"] != arca.FROZEN_MODEL_REVISION
            or arc_config["endpoint"]
            != stages["fresh"]["arc_deployment_receipt"]["endpoint"]
            or arc_config["config_sha256"]
            != sha256(canonical_json(frozen_config_commitment).encode("utf-8")).hexdigest()):
        raise ArtifactIntegrityError("arc adjudicator config commitment mismatch")

    _require_frozen_v5_manifest_contract(
        manifest_path=manifest_path,
        allow_unpublished_candidate=_allow_unpublished_candidate,
        protocol=protocol,
        preflight_binding=preflight_binding,
        preflight_receipt=preflight_receipt,
        extractor=extractor,
        embedding=embedding,
        stages=stages,
        phase_paths=phase_paths,
        sidecars=sidecars,
        holdouts=holdouts,
        arc_config=arc_config,
    )

    committed_paths = list(phase_paths.values())
    for stage in STAGES:
        committed_paths.extend(stages[stage]["output_paths"].values())
    for paths in stages["fresh"]["arc_paths"].values():
        committed_paths.extend(paths.values())
    committed_paths.append(stages["fresh"]["arc_deployment_receipt"]["path"])
    if len(committed_paths) != len(set(committed_paths)):
        raise ArtifactIntegrityError("committed output paths must be globally unique")
    return value


def load_prepared_segment(
    path: str | Path,
    *,
    expected_sha256: str | None = None,
) -> prep.PreparedSegmentV1:
    source = Path(path)
    if expected_sha256 is not None and _file_sha256(source) != expected_sha256:
        raise ArtifactIntegrityError(f"segment file hash mismatch: {source}")
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactIntegrityError(f"invalid segment {source}: {exc}") from exc
    _strict_root(
        raw, {"dataset", "split", "paragraphs", "evaluation_rows"},
        label="PreparedSegment",
    )
    try:
        paragraphs = tuple(
            prep.fresh.CompilerParagraphV1(**item) for item in raw["paragraphs"]
        )
        evaluation_rows = []
        evaluation_keys = {
            "dataset", "split", "qid", "question", "paragraph_source_ids",
            "gold_source_ids", "hop",
        }
        for item in raw["evaluation_rows"]:
            _strict_root(item, evaluation_keys, label="EvaluationRow")
            evaluation_rows.append(prep.EvaluationRowV1(
                dataset=item["dataset"], split=item["split"], qid=item["qid"],
                question=item["question"],
                paragraph_source_ids=tuple(item["paragraph_source_ids"]),
                gold_source_ids=tuple(item["gold_source_ids"]), hop=int(item["hop"]),
            ))
        evaluation = tuple(evaluation_rows)
    except (TypeError, KeyError, ValueError) as exc:
        raise ArtifactIntegrityError(f"malformed PreparedSegment: {exc}") from exc
    segment = prep.PreparedSegmentV1(
        dataset=str(raw["dataset"]), split=str(raw["split"]),
        paragraphs=paragraphs, evaluation_rows=evaluation,
    )
    if segment.dataset not in {"musique", "2wiki"}:
        raise ArtifactIntegrityError(f"unsupported segment dataset {segment.dataset!r}")
    if segment.split not in {"development", "fresh"}:
        raise ArtifactIntegrityError(f"unsupported segment split {segment.split!r}")
    source_ids = [item.source_id for item in segment.paragraphs]
    if not source_ids or len(source_ids) != len(set(source_ids)):
        raise ArtifactIntegrityError("segment paragraph IDs must be non-empty and unique")
    if tuple(sorted(source_ids)) != tuple(source_ids):
        raise ArtifactIntegrityError("segment paragraphs are not in canonical ID order")
    for item in segment.paragraphs:
        expected_source_id = prep.paragraph_source_id(
            segment.dataset, item.title, item.text,
        )
        if item.source_id != expected_source_id:
            raise ArtifactIntegrityError(
                f"paragraph stable content ID mismatch: {item.source_id}"
            )
    qids = [row.qid for row in segment.evaluation_rows]
    if not qids or len(qids) != len(set(qids)):
        raise ArtifactIntegrityError("segment qids must be non-empty and unique")
    available = set(source_ids)
    for row in segment.evaluation_rows:
        if row.dataset != segment.dataset or row.split != segment.split:
            raise ArtifactIntegrityError("evaluation row dataset/split mismatch")
        candidates = set(row.paragraph_source_ids)
        gold = set(row.gold_source_ids)
        if (not row.question.strip() or row.hop < 2 or not gold or
                len(candidates) != len(row.paragraph_source_ids) or
                len(gold) != len(row.gold_source_ids) or
                not candidates <= available or not gold <= candidates):
            raise ArtifactIntegrityError(f"malformed evaluation row {row.qid}")
    return segment


def _expected_embedding_preimages(
    segments: Sequence[prep.PreparedSegmentV1],
) -> dict[str, tuple[str, str]]:
    expected: dict[str, tuple[str, str]] = {}
    for record in prep.embedding_records(segments):
        identity = record["id"]
        value = (record["kind"], sha256(record["text"].encode("utf-8")).hexdigest())
        old = expected.setdefault(identity, value)
        if old != value:
            raise ArtifactIntegrityError(f"embedding preimage collision: {identity}")
    return expected


def _preimage_receipt(
    segments: Sequence[prep.PreparedSegmentV1],
) -> dict[str, int | str]:
    extraction = prep.extraction_records(segments)
    embeddings = prep.embedding_records(segments)

    def jsonl_sha256(records: Sequence[Mapping[str, Any]]) -> str:
        body = "".join(canonical_json(record) + "\n" for record in records)
        return sha256(body.encode("utf-8")).hexdigest()

    return {
        "extraction_records": len(extraction),
        "extraction_jsonl_sha256": jsonl_sha256(extraction),
        "embedding_records": len(embeddings),
        "embedding_jsonl_sha256": jsonl_sha256(embeddings),
    }


def _verify_preimage_receipt(
    declared: Mapping[str, Any],
    segments: Sequence[prep.PreparedSegmentV1],
) -> dict[str, int | str]:
    _validate_preimage_receipt_schema(declared, label="stage preimages")
    observed = _preimage_receipt(segments)
    if dict(declared) != observed:
        raise ArtifactIntegrityError("run manifest preimage count/hash mismatch")
    return observed


def load_embedding_artifact(
    path: str | Path,
    segments: Sequence[prep.PreparedSegmentV1],
    *,
    receipt_path: str | Path | None = None,
    expected_model_revision: str | None = None,
    expected_execution: Mapping[str, Any] | None = None,
) -> EmbeddingArtifactV1:
    source = Path(path)
    try:
        archive = np.load(source, allow_pickle=False)
    except (OSError, ValueError) as exc:
        raise ArtifactIntegrityError(f"invalid embedding NPZ: {exc}") from exc
    if set(archive.files) != {"ids", "kinds", "text_sha256", "vectors"}:
        raise ArtifactIntegrityError("embedding NPZ members mismatch")
    ids = tuple(str(value) for value in archive["ids"].tolist())
    kinds = tuple(str(value) for value in archive["kinds"].tolist())
    text_hashes = tuple(str(value) for value in archive["text_sha256"].tolist())
    vectors = np.asarray(archive["vectors"], dtype=np.float64)
    if (vectors.ndim != 2 or vectors.shape[0] != len(ids) or
            len(kinds) != len(ids) or len(text_hashes) != len(ids)):
        raise ArtifactIntegrityError("embedding arrays are not aligned")
    if len(ids) != len(set(ids)):
        raise ArtifactIntegrityError("embedding IDs are not unique")
    if not np.isfinite(vectors).all():
        raise ArtifactIntegrityError("embedding vectors contain non-finite values")
    norm_error = np.max(np.abs(np.linalg.norm(vectors, axis=1) - 1.0))
    if norm_error > 1e-5:
        raise ArtifactIntegrityError("embedding vectors are not L2 normalized")
    expected = _expected_embedding_preimages(segments)
    expected_records = tuple(
        bge.EmbeddingInputV1(
            id=record["id"], kind=record["kind"], text=record["text"],
        )
        for record in prep.embedding_records(segments)
    )
    if set(ids) != set(expected):
        missing = sorted(set(expected) - set(ids))[:3]
        extra = sorted(set(ids) - set(expected))[:3]
        raise ArtifactIntegrityError(
            f"embedding stable-ID set mismatch; missing={missing}, extra={extra}"
        )
    for identity, kind, text_hash in zip(ids, kinds, text_hashes, strict=True):
        if expected[identity] != (kind, text_hash):
            raise ArtifactIntegrityError(f"embedding preimage mismatch: {identity}")
    receipt: Mapping[str, Any] | None = None
    file_digest = _file_sha256(source)
    if receipt_path is not None:
        try:
            loaded = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ArtifactIntegrityError(f"invalid embedding receipt: {exc}") from exc
        try:
            loaded = bge.validate_embedding_receipt(
                loaded, artifact_path=source, expected_records=expected_records,
                expected_producer_code_sha256=_file_sha256(Path(bge.__file__)),
            )
        except (TypeError, ValueError) as exc:
            raise ArtifactIntegrityError(
                f"embedding receipt failed validation: {exc}"
            ) from exc
        receipt = loaded
        if int(loaded["dimension"]) != vectors.shape[1]:
            raise ArtifactIntegrityError("embedding receipt dimension mismatch")
        if (expected_model_revision is not None and
                loaded.get("model_revision") != expected_model_revision):
            raise ArtifactIntegrityError("embedding model revision mismatch")
        if expected_execution is not None:
            _strict_root(
                expected_execution, EMBEDDING_MANIFEST_KEYS,
                label="expected embedding execution",
            )
            expected_fields = {
                "model": loaded["model"],
                "snapshot": loaded["model_revision"],
                "dimension": loaded["dimension"],
                "pooling": loaded["pooling"],
                "max_length": loaded["max_length"],
                "dtype": loaded["dtype"],
                "batch_size": loaded["batch_size"],
                "producer_code_sha256": loaded["producer_code_sha256"],
                "model_attestation": loaded["model_attestation"],
                "model_attestation_receipt": expected_execution[
                    "model_attestation_receipt"
                ],
                "config_sha256": expected_execution["config_sha256"],
            }
            if canonical_json(expected_fields) != canonical_json(dict(expected_execution)):
                raise ArtifactIntegrityError(
                    "embedding receipt differs from frozen execution commitment"
                )
    by_id = {identity: vectors[index] for index, identity in enumerate(ids)}
    return EmbeddingArtifactV1(
        path=str(source), file_sha256=file_digest, ids=ids, kinds=kinds,
        text_sha256=text_hashes, vectors=vectors, vector_by_id=by_id,
        receipt=receipt,
    )


def _usage_totals(records: Sequence[rex.RecordedExtractionV1]) -> dict[str, Any]:
    by_attempt: dict[str, rex.RecordedExtractionV1] = {}
    for record in records:
        by_attempt.setdefault(record.attempt_id, record)
    prompt = completion = total = 0
    latencies: list[int] = []
    for record in by_attempt.values():
        try:
            usage = json.loads(record.usage_json)
        except json.JSONDecodeError as exc:
            raise ArtifactIntegrityError("invalid recorded usage JSON") from exc
        if not isinstance(usage, Mapping):
            raise ArtifactIntegrityError("recorded usage must be an object")
        prompt += int(usage.get("prompt_tokens", 0) or 0)
        completion += int(usage.get("completion_tokens", 0) or 0)
        total += int(usage.get("total_tokens", 0) or 0)
        latencies.append(record.latency_ms)
    return {
        "finalized_endpoint_calls": len(by_attempt),
        "unique_batch_request_ids": len({
            record.batch_request_id for record in by_attempt.values()
        }),
        "recorded_paragraph_attempt_rows": len(records),
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "summed_call_latency_ms": sum(latencies),
        "mean_call_latency_ms": round(float(np.mean(latencies)), 3) if latencies else 0.0,
        "max_call_latency_ms": max(latencies, default=0),
    }


def load_extraction_artifact(
    path: str | Path,
    segments: Sequence[prep.PreparedSegmentV1],
    *,
    expected_model_revision: str | None = None,
    expected_prompt_sha256: str | None = None,
    expected_config_sha256: str | None = None,
) -> ExtractionArtifactV1:
    source = Path(path)
    try:
        journal = rex.load_attempt_journal_strict(source)
    except (OSError, rex.CacheCorruptionError) as exc:
        raise ArtifactIntegrityError(f"invalid extraction journal: {exc}") from exc
    if journal.unmatched_starts:
        raise ArtifactIntegrityError(
            "extraction journal has "
            f"{len(journal.unmatched_starts)} unmatched durable START events"
        )
    raw_records = list(journal.records)
    expected_source_order = [
        paragraph.source_id for segment in segments for paragraph in segment.paragraphs
    ]
    expected_sources = set(expected_source_order)
    if len(expected_source_order) != len(expected_sources):
        raise ArtifactIntegrityError(
            "prepared segments contain duplicate extraction source IDs"
        )
    dataset_by_source = {
        paragraph.source_id: segment.dataset
        for segment in segments
        for paragraph in segment.paragraphs
    }
    source_count_by_dataset = Counter(dataset_by_source.values())
    paragraph_by_source = {
        item.source_id: item for segment in segments for item in segment.paragraphs
    }
    starts_by_source: dict[str, list[rex.AttemptStartV1]] = defaultdict(list)
    for start in journal.starts:
        if start.batch_size != 1 or len(start.source_ids) != 1:
            raise ArtifactIntegrityError(
                "confirmatory extraction START is not batch_size=1"
            )
        source_id = start.source_ids[0]
        if source_id not in expected_sources:
            raise ArtifactIntegrityError(
                f"extraction START for unknown source {source_id}"
            )
        if (expected_prompt_sha256 is not None
                and start.prompt_sha256 != expected_prompt_sha256):
            raise ArtifactIntegrityError("extraction START prompt hash mismatch")
        if (expected_config_sha256 is not None
                and start.config_sha256 != expected_config_sha256):
            raise ArtifactIntegrityError("extraction START config hash mismatch")
        starts_by_source[source_id].append(start)
    attempts_by_source: dict[str, list[rex.RecordedExtractionV1]] = defaultdict(list)
    for record in raw_records:
        if record.batch_size != 1:
            raise ArtifactIntegrityError(
                "confirmatory extraction record is not batch_size=1"
            )
        if record.source_id not in expected_sources:
            raise ArtifactIntegrityError(f"extraction for unknown source {record.source_id}")
        paragraph = paragraph_by_source[record.source_id]
        expected_text_sha = sha256(paragraph.text.encode("utf-8")).hexdigest()
        expected_input_sha = sha256(canonical_json({
            "source_id": paragraph.source_id, "title": paragraph.title,
            "text": paragraph.text,
        }).encode("utf-8")).hexdigest()
        if (record.source_text_sha256 != expected_text_sha
                or record.source_input_sha256 != expected_input_sha):
            raise ArtifactIntegrityError(
                f"recorded extraction source preimage mismatch: {record.source_id}"
            )
        if (expected_model_revision is not None
                and record.model_revision != expected_model_revision):
            raise ArtifactIntegrityError("recorded extraction model revision mismatch")
        if (expected_prompt_sha256 is not None
                and record.prompt_sha256 != expected_prompt_sha256):
            raise ArtifactIntegrityError("recorded extraction prompt hash mismatch")
        if (expected_config_sha256 is not None
                and record.config_sha256 != expected_config_sha256):
            raise ArtifactIntegrityError("recorded extraction config hash mismatch")
        attempts_by_source[record.source_id].append(record)
    missing = sorted(
        expected_sources - set(attempts_by_source),
    )
    if missing:
        raise ArtifactIntegrityError(
            f"recorded extraction artifact incomplete: {len(missing)} missing; first={missing[:3]}"
        )
    frozen: dict[str, cb.FrozenExtractionV1] = {}
    attempt_status_counts: Counter[str] = Counter(
        record.status.value for record in raw_records
    )
    attempt_quarantine_reasons: Counter[str] = Counter(
        quarantine.reason.value
        for record in raw_records
        for quarantine in record.quarantines
    )
    terminal_status_counts: Counter[str] = Counter()
    terminal_quarantine_reasons: Counter[str] = Counter()
    retry_sources = 0
    attempt_cap_terminal_sources = 0
    attempt_cap_terminal_by_dataset: Counter[str] = Counter()
    for source_id, attempts in attempts_by_source.items():
        starts = starts_by_source.get(source_id, [])
        if not starts:
            raise ArtifactIntegrityError(
                f"source {source_id} has records without durable START"
            )
        retry_sources += len(starts) > 1
        if len({record.batch_request_id for record in attempts}) != 1:
            raise ArtifactIntegrityError(
                f"source {source_id} spans multiple extraction request IDs"
            )
        terminal = [record for record in attempts if record.frozen_extraction is not None]
        if len(terminal) != 1:
            raise ArtifactIntegrityError(
                f"source {source_id} has {len(terminal)} compiler-admissible terminal records"
            )
        record = terminal[0]
        if (len({start.batch_request_id for start in starts}) != 1
                or starts[0].batch_request_id != record.batch_request_id):
            raise ArtifactIntegrityError(
                f"source {source_id} spans multiple START request IDs"
            )
        if record.attempt_ordinal != max(item.attempt_ordinal for item in starts):
            raise ArtifactIntegrityError(
                f"source {source_id} terminal record is not the final START"
            )
        terminal_status_counts[record.status.value] += 1
        terminal_quarantine_reasons.update(
            item.reason.value for item in record.quarantines
        )
        capped = any(
            item.reason
            == rex.QuoteRejectCode.TRUNCATED_RESPONSE_AT_ATTEMPT_CAP
            for item in record.quarantines
        )
        attempt_cap_terminal_sources += capped
        if capped:
            attempt_cap_terminal_by_dataset[dataset_by_source[source_id]] += 1
        assert record.frozen_extraction is not None
        frozen[source_id] = record.frozen_extraction
    accounting = {
        "physical_journal_rows": len(journal.events),
        "attempt_start_rows": len(journal.starts),
        "attempt_finalize_rows": len(journal.finalizes),
        "paragraph_records": len(raw_records),
        "endpoint_calls": len(journal.starts),
        "endpoint_call_upper_bound": len(journal.starts),
        "unmatched_attempt_starts": len(journal.unmatched_starts),
        "status_counts": dict(sorted(attempt_status_counts.items())),
        "terminal_status_counts": dict(sorted(terminal_status_counts.items())),
        "retry_sources": retry_sources,
        "max_attempt_ordinal": max(
            (start.attempt_ordinal for start in journal.starts), default=0,
        ),
        "attempt_cap_terminal_sources": attempt_cap_terminal_sources,
        "attempt_cap_terminal_rate": round(
            attempt_cap_terminal_sources / max(len(expected_sources), 1), 8,
        ),
        "attempt_cap_terminal_by_dataset": {
            dataset: attempt_cap_terminal_by_dataset[dataset]
            for dataset in sorted(source_count_by_dataset)
        },
        "attempt_cap_terminal_rate_by_dataset": {
            dataset: round(
                attempt_cap_terminal_by_dataset[dataset]
                / source_count_by_dataset[dataset],
                8,
            )
            for dataset in sorted(source_count_by_dataset)
        },
        "quote_quarantine_reasons": dict(
            sorted(attempt_quarantine_reasons.items())
        ),
        "terminal_quote_quarantine_reasons": dict(
            sorted(terminal_quarantine_reasons.items())
        ),
        **_usage_totals(raw_records),
    }
    return ExtractionArtifactV1(
        path=str(source), file_sha256=_file_sha256(source),
        journal=journal, records=tuple(raw_records), frozen_by_source=frozen,
        accounting=accounting,
    )


def _paragraph_inputs(segment: prep.PreparedSegmentV1) -> tuple[tab.ParagraphInputV1, ...]:
    clean: list[tab.ParagraphInputV1] = []
    for item in segment.paragraphs:
        payload = {"source_id": item.source_id, "title": item.title, "text": item.text}
        reval.assert_compiler_payload_clean(payload)
        clean.append(tab.ParagraphInputV1(**payload))
    return tuple(clean)


def _b1_graph(build: tab.TitleAnchorBuildV1) -> b1comp.CompositionGraphV1:
    ordinal = {
        source_id: index for index, source_id in enumerate(
            build.paragraph_graph.target_source_ids
        )
    }
    receipts = {item.receipt_id: item for item in build.evidence_spans}
    arcs: list[b1comp.EvidenceArcV1] = []
    for link in build.directed_links:
        for receipt_id in link.evidence_receipt_ids:
            receipt = receipts[receipt_id]
            arcs.append(b1comp.EvidenceArcV1(
                source_target=ordinal[link.subject_source_id],
                target_target=ordinal[link.object_source_id],
                source_id=receipt.source_id,
                selector_start=receipt.body_start, selector_end=receipt.body_end,
                selector_exact=receipt.exact_quote,
                anchor_label=receipt.normalized_alias,
            ))
    return b1comp.make_graph(build.paragraph_graph.target_source_ids, arcs)


def _tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text.casefold())


def _bm25_matrix(
    documents: Sequence[str], questions: Sequence[str],
    *, k1: float = 1.5, b: float = 0.75,
) -> np.ndarray:
    tokenized = [_tokens(document) for document in documents]
    lengths = np.asarray([len(row) for row in tokenized], dtype=np.float64)
    average = max(float(lengths.mean()), 1.0)
    postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for document_id, row in enumerate(tokenized):
        for token, frequency in Counter(row).items():
            postings[token].append((document_id, frequency))
    out = np.zeros((len(questions), len(documents)), dtype=np.float64)
    for query_id, question in enumerate(questions):
        for token in set(_tokens(question)):
            posting = postings.get(token, ())
            if not posting:
                continue
            df = len(posting)
            idf = math.log(1.0 + (len(documents) - df + 0.5) / (df + 0.5))
            for document_id, frequency in posting:
                denominator = frequency + k1 * (
                    1.0 - b + b * lengths[document_id] / average
                )
                out[query_id, document_id] += (
                    idf * frequency * (k1 + 1.0) / denominator
                )
    return out


def _ranks(scores: np.ndarray) -> np.ndarray:
    order = np.argsort(-scores, axis=1, kind="stable")
    ranks = np.empty_like(order)
    ranks[np.arange(scores.shape[0])[:, None], order] = np.arange(
        1, scores.shape[1] + 1
    )
    return ranks


def _rrf(cosine: np.ndarray, bm25: np.ndarray, k: float = 60.0) -> np.ndarray:
    return 1.0 / (k + _ranks(cosine)) + 1.0 / (k + _ranks(bm25))


def compile_segment(
    segment: prep.PreparedSegmentV1,
    extractions: ExtractionArtifactV1,
    embeddings: EmbeddingArtifactV1,
) -> CompiledSegmentV1:
    paragraphs = _paragraph_inputs(segment)
    frozen = tuple(extractions.frozen_by_source[item.source_id] for item in paragraphs)
    b1_build = tab.build_title_anchor_graph(paragraphs)
    b1_issues = tab.verify_title_anchor_build(b1_build)
    if b1_issues:
        raise HarnessInvariantError(f"B1 verification failed: {b1_issues}")
    b3_build = cb.compile_claim_graph(paragraphs, frozen)
    b3_issues = cb.verify_claim_graph(b3_build)
    if b3_issues:
        raise HarnessInvariantError(f"B3 verification failed: {b3_issues[:5]}")
    b1_graph = _b1_graph(b1_build)
    b3_graph = typed.graph_from_claim_build(b3_build)
    target_ids = b1_build.paragraph_graph.target_source_ids
    if (b3_graph.target_ids != target_ids or
            b3_build.paragraph_graph.target_source_ids != target_ids):
        raise HarnessInvariantError("B1/B3 changed candidate identity or order")
    b1_pairs = {(arc.source_target, arc.target_target) for arc in b1_graph.arcs}
    shared_pairs = {
        (arc.source_target, arc.target_target)
        for arc in b3_graph.arcs
        if arc.origin == "verified_shared_entity"
    }
    added_shared_pairs = shared_pairs - b1_pairs
    if not added_shared_pairs:
        raise HarnessInvariantError(
            "PRECOMPUTE_NOOP: verified shared-entity evidence adds no adjacency"
        )

    paragraph_vectors = np.stack([
        embeddings.vector_by_id[f"paragraph:{source_id}"] for source_id in target_ids
    ])
    query_vectors = np.stack([
        embeddings.vector_by_id[f"query:{segment.dataset}:{row.qid}"]
        for row in segment.evaluation_rows
    ])
    cosine = query_vectors @ paragraph_vectors.T
    documents = b1_build.paragraph_graph.unit_texts
    questions = tuple(row.question for row in segment.evaluation_rows)
    bm25 = _bm25_matrix(documents, questions)
    rrf = _rrf(cosine, bm25)
    ordinal = {source_id: index for index, source_id in enumerate(target_ids)}
    gold: list[np.ndarray] = []
    for row in segment.evaluation_rows:
        try:
            gold.append(np.asarray(
                sorted({ordinal[item] for item in row.gold_source_ids}),
                dtype=np.int64,
            ))
        except KeyError as exc:
            raise HarnessInvariantError(f"gold stable ID missing: {exc.args[0]}") from exc
    return CompiledSegmentV1(
        segment=segment, target_ids=target_ids, ordinal_by_source=ordinal,
        b1_build=b1_build, b1_graph=b1_graph, b3_build=b3_build,
        b3_graph=b3_graph, cosine=cosine, bm25=bm25, rrf=rrf,
        gold_ordinals=tuple(gold),
    )


def _query_metrics(scores: np.ndarray, gold: np.ndarray, *, seed: int) -> dict[str, float]:
    order = np.argsort(-scores, kind="stable")
    top = set(int(item) for item in order[:K_METRIC])
    gold_set = set(int(item) for item in gold)
    return {
        "ndcg10": float(metrics.ndcg_at_k(
            scores, gold, np.arange(scores.size), k=K_METRIC, seed=seed,
        )),
        "asr10": float(gold_set.issubset(top)),
        "support_recall10": len(gold_set & top) / max(len(gold_set), 1),
    }


def _metric_arrays(
    matrix: np.ndarray,
    compiled: CompiledSegmentV1,
    indices: Sequence[int],
) -> dict[str, np.ndarray]:
    rows = [
        _query_metrics(matrix[index], compiled.gold_ordinals[index], seed=index + 1)
        for index in indices
    ]
    return {
        name: np.asarray([row[name] for row in rows], dtype=np.float64)
        for name in ("ndcg10", "asr10", "support_recall10")
    }


def _means(values: Mapping[str, np.ndarray]) -> dict[str, float]:
    return {name: round(float(row.mean()), 6) for name, row in values.items()}


def _b1_matrix(
    compiled: CompiledSegmentV1,
    policy: typed.TypedCompositionPolicyV1,
    *, hops: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    b1_policy = b1comp.CompositionPolicyV1(
        seed_k=policy.seed_k, hops=hops, mu=policy.mu, direction="forward",
        fanout_exponent=policy.fanout_exponent, max_fanout=policy.max_fanout,
    )
    rows: list[np.ndarray] = []
    trips: Counter[str] = Counter()
    applied = 0
    for static in compiled.cosine:
        final, _residual, receipt = b1comp.compose_scores(
            static, compiled.b1_graph, b1_policy,
        )
        rows.append(final)
        applied += receipt.reached_targets > 0
        if receipt.trip_reason:
            trips[receipt.trip_reason] += 1
    return np.stack(rows), {
        "apply_coverage": round(applied / len(rows), 6),
        "trip_reasons": dict(sorted(trips.items())),
    }


def _typed_matrix(
    compiled: CompiledSegmentV1,
    policy: typed.TypedCompositionPolicyV1,
    *, graph: typed.TypedCompositionGraphV1 | None = None,
) -> tuple[np.ndarray, tuple[typed.TypedCompositionReceiptV1, ...], dict[str, Any]]:
    treatment_graph = graph or compiled.b3_graph
    rows: list[np.ndarray] = []
    receipts: list[typed.TypedCompositionReceiptV1] = []
    trips: Counter[str] = Counter()
    applied = 0
    for index, row in enumerate(compiled.segment.evaluation_rows):
        static = compiled.cosine[index]
        final, _contribution, receipt = typed.compose_typed_scores(
            row.question, static, treatment_graph, policy,
        )
        if (receipt.fanout_gate_trips or receipt.join_hub_gate_trips) and (
                final.dtype != static.dtype or final.shape != static.shape
                or final.tobytes(order="C") != static.tobytes(order="C")):
            raise HarnessInvariantError(
                "typed safety trip did not return the bit-identical static floor"
            )
        rows.append(final)
        receipts.append(receipt)
        applied += receipt.reached_targets > 0
        if receipt.trip_reason:
            trips[receipt.trip_reason] += 1
    return np.stack(rows), tuple(receipts), {
        "apply_coverage": round(applied / len(rows), 6),
        "fallback_rate": round(1.0 - applied / len(rows), 6),
        "trip_reasons": dict(sorted(trips.items())),
        "fanout_gate_trips": sum(item.fanout_gate_trips for item in receipts),
        "join_hub_gate_trips": sum(item.join_hub_gate_trips for item in receipts),
        "h3_local_pass_queries": sum(
            item.h3_composition_status == "PASS" for item in receipts
        ),
    }


def _raw_evaluation_row(
    dataset: str,
    split: str,
    raw: Mapping[str, Any],
) -> prep.EvaluationRowV1:
    """Recompute the complete evaluator binding from raw benchmark evidence."""
    try:
        _compiler_row, _paragraphs, binding = (
            prep.fresh.derive_row_label_provenance(dataset, raw)
        )
    except prep.fresh.FreshManifestError as exc:
        raise ArtifactIntegrityError(
            f"raw evaluator provenance is invalid: {exc}"
        ) from exc
    return prep.EvaluationRowV1(
        dataset=dataset,
        split=split,
        qid=binding.example.qid,
        question=binding.example.question,
        paragraph_source_ids=binding.paragraph_source_ids,
        gold_source_ids=binding.gold_source_ids,
        hop=binding.benchmark_hop,
    )


def fresh_manifest_components(
    compiled: CompiledSegmentV1,
    path: str | Path,
    *,
    expected_file_sha256: str,
    expected_manifest_id: str,
) -> tuple[tuple[str, ...], dict[str, Any]]:
    """Recover fresh relation/evidence clusters from the evaluator sidecar.

    The fresh ``PreparedSegment`` intentionally omits relation labels.  This
    function joins the separately frozen holdout manifest by qid, verifies its
    file/selection identities and disjointness receipt, then unions examples
    that share either a relation template or exact evidence-content ID.
    """

    source = Path(path)
    if _file_sha256(source) != expected_file_sha256:
        raise ArtifactIntegrityError("fresh holdout manifest file hash mismatch")
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactIntegrityError(f"invalid fresh holdout manifest: {exc}") from exc
    if (not isinstance(value, Mapping)
            or value.get("schema_version") != prep.fresh.SCHEMA_VERSION
            or value.get("dataset") != compiled.segment.dataset
            or value.get("selected_manifest_sha256") != expected_manifest_id):
        raise ArtifactIntegrityError("fresh holdout manifest identity mismatch")
    audit = value.get("audit")
    if not isinstance(audit, Mapping) or not audit.get("all_disjoint"):
        raise ArtifactIntegrityError("fresh holdout disjointness audit failed")
    qids = tuple(row.qid for row in compiled.segment.evaluation_rows)
    if tuple(str(item) for item in value.get("selected_qids", ())) != qids:
        raise ArtifactIntegrityError("fresh manifest/segment qid order mismatch")
    compiler_paragraphs = tuple(sorted(
        (
            str(item.get("source_id", "")), str(item.get("title", "")),
            str(item.get("text", "")),
        )
        for item in value.get("compiler_paragraphs", ())
    ))
    segment_paragraphs = tuple(sorted(
        (item.source_id, item.title, item.text) for item in compiled.segment.paragraphs
    ))
    if compiler_paragraphs != segment_paragraphs:
        raise ArtifactIntegrityError("fresh manifest/segment paragraph mismatch")
    raw_compiler_rows = value.get("compiler_rows")
    if not isinstance(raw_compiler_rows, list):
        raise ArtifactIntegrityError("fresh manifest lacks compiler rows")
    compiler_rows: dict[str, tuple[str, ...]] = {}
    for index, item in enumerate(raw_compiler_rows):
        if (not isinstance(item, Mapping)
                or set(item) != {"row_id", "paragraph_source_ids"}):
            raise ArtifactIntegrityError(f"fresh compiler row {index} is malformed")
        row_id = str(item.get("row_id", ""))
        candidates = tuple(str(value) for value in item.get("paragraph_source_ids", ()))
        if (not row_id or not candidates or len(candidates) != len(set(candidates))
                or row_id in compiler_rows):
            raise ArtifactIntegrityError(f"fresh compiler row {index} is malformed")
        compiler_rows[row_id] = candidates
    sidecars = value.get("evaluator_sidecar")
    if not isinstance(sidecars, list):
        raise ArtifactIntegrityError("fresh manifest lacks evaluator sidecar")
    examples: dict[str, tuple[str, tuple[str, ...]]] = {}
    for index, binding in enumerate(sidecars):
        expected_binding_keys = {
            "binding_id", "row_id", "raw_row_sha256", "paragraph_source_ids",
            "gold_source_ids", "benchmark_hop", "example",
        }
        if (not isinstance(binding, Mapping) or set(binding) != expected_binding_keys
                or not isinstance(binding.get("example"), Mapping)):
            raise ArtifactIntegrityError(f"fresh evaluator binding {index} is malformed")
        example = binding["example"]
        qid = str(example.get("qid", ""))
        template = str(example.get("relation_template_id", ""))
        evidence = tuple(sorted(str(item) for item in example.get("evidence_content_ids", ())))
        if (not qid or not template or not evidence
                or example.get("dataset") != compiled.segment.dataset or qid in examples):
            raise ArtifactIntegrityError(f"fresh evaluator example {index} is malformed")
        segment_row = next(
            (row for row in compiled.segment.evaluation_rows if row.qid == qid), None
        )
        binding_id = str(binding.get("binding_id", ""))
        row_id = str(binding.get("row_id", ""))
        raw_row_sha256 = str(binding.get("raw_row_sha256", ""))
        candidates = tuple(
            str(item) for item in binding.get("paragraph_source_ids", ())
        )
        gold = tuple(str(item) for item in binding.get("gold_source_ids", ()))
        benchmark_hop = binding.get("benchmark_hop")
        occurrence_id = str(example.get("occurrence_id", ""))
        expected_row_id = prep.fresh._compiler_row_id(
            compiled.segment.dataset, qid, raw_row_sha256,
        )
        expected_binding_id = prep.fresh._evaluator_binding_id(
            dataset=compiled.segment.dataset, row_id=row_id,
            raw_row_sha256=raw_row_sha256,
            paragraph_source_ids=candidates, gold_source_ids=gold,
            benchmark_hop=benchmark_hop, occurrence_id=occurrence_id,
        ) if type(benchmark_hop) is int else ""
        if (segment_row is None or not binding_id or not row_id
                or re.fullmatch(r"[0-9a-f]{64}", raw_row_sha256) is None
                or example.get("raw_row_sha256") != raw_row_sha256
                or row_id != expected_row_id or binding_id != expected_binding_id
                or row_id not in compiler_rows
                or not candidates or len(candidates) != len(set(candidates))
                or not gold or len(gold) != len(set(gold))
                or not set(gold) <= set(candidates)
                or compiler_rows[row_id] != candidates
                or candidates != segment_row.paragraph_source_ids
                or gold != segment_row.gold_source_ids
                or type(benchmark_hop) is not int
                or benchmark_hop != segment_row.hop
                or str(example.get("question", "")) != segment_row.question):
            raise ArtifactIntegrityError(
                "fresh evaluator provenance binding mismatch"
            )
        examples[qid] = (template, evidence)
    if set(examples) != set(qids):
        raise ArtifactIntegrityError("fresh evaluator sidecar qid set mismatch")
    if len(compiler_rows) != len(examples):
        raise ArtifactIntegrityError("fresh compiler/evaluator row count mismatch")

    parent = list(range(len(qids)))

    def find(item: int) -> int:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: int, right: int) -> None:
        left, right = find(left), find(right)
        if left != right:
            parent[max(left, right)] = min(left, right)

    first_template: dict[str, int] = {}
    first_evidence: dict[str, int] = {}
    for index, qid in enumerate(qids):
        template, evidence = examples[qid]
        union(index, first_template.setdefault(template, index))
        for evidence_id in evidence:
            union(index, first_evidence.setdefault(evidence_id, index))
    members: dict[int, list[str]] = defaultdict(list)
    for index, qid in enumerate(qids):
        members[find(index)].append(qid)
    component_id = {
        root: sha256(canonical_json(tuple(sorted(items))).encode("utf-8")).hexdigest()
        for root, items in members.items()
    }
    components = tuple(component_id[find(index)] for index in range(len(qids)))
    return components, {
        "manifest_file_sha256": expected_file_sha256,
        "selected_manifest_sha256": expected_manifest_id,
        "method": "union(relation_template_id, exact_evidence_content_id)",
        "n_queries": len(qids), "n_components": len(set(components)),
        "disjoint_audit": dict(audit),
    }


def development_assignments(
    compiled: CompiledSegmentV1,
    raw_sidecar_path: str | Path,
    *, split_seed: int, expected_file_sha256: str | None = None,
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[str, ...], dict[str, Any]]:
    if compiled.segment.split != "development":
        raise ValueError("relation-disjoint assignments apply only to development")
    if (expected_file_sha256 is not None
            and _file_sha256(raw_sidecar_path) != expected_file_sha256):
        raise ArtifactIntegrityError("development relation sidecar file hash mismatch")
    try:
        payload = json.loads(Path(raw_sidecar_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactIntegrityError(f"invalid raw relation sidecar: {exc}") from exc
    if (not isinstance(payload, Mapping) or payload.get("dataset") != compiled.segment.dataset
            or not isinstance(payload.get("rows"), list)):
        raise ArtifactIntegrityError("raw relation sidecar schema mismatch")
    actual = sha256(
        reval.canonical_json(tuple(payload["rows"])).encode("utf-8")
    ).hexdigest()
    if actual != payload.get("rows_sha256"):
        raise ArtifactIntegrityError("raw relation sidecar hash mismatch")
    by_qid = {str(row.get("id", row.get("_id", ""))): row for row in payload["rows"]}
    if len(by_qid) != len(payload["rows"]) or "" in by_qid:
        raise ArtifactIntegrityError("development sidecar qids are duplicate or empty")
    try:
        raw_rows = tuple(by_qid[row.qid] for row in compiled.segment.evaluation_rows)
    except KeyError as exc:
        raise ArtifactIntegrityError(f"relation sidecar missing qid {exc.args[0]}") from exc
    rebound_rows = tuple(
        _raw_evaluation_row(
            compiled.segment.dataset, "development", raw,
        )
        for raw in raw_rows
    )
    for declared, rebound in zip(
        compiled.segment.evaluation_rows, rebound_rows, strict=True,
    ):
        if declared != rebound:
            raise ArtifactIntegrityError(
                f"development prepared segment provenance mismatch: {declared.qid}"
            )
    suite = reval.build_relation_evaluation_suite(
        compiled.segment.dataset, raw_rows,
        split_spec=(("val", 0.5), ("test", 0.5)), seed=split_seed,
    )
    example_by_qid = {item.qid: item for item in suite.examples}
    for row in compiled.segment.evaluation_rows:
        if example_by_qid[row.qid].question != " ".join(row.question.split()):
            raise ArtifactIntegrityError("development evaluator question binding mismatch")
    assignment = {item.occurrence_id: item for item in suite.assignments}
    split: list[str] = []
    components: list[str] = []
    for row in compiled.segment.evaluation_rows:
        example = example_by_qid[row.qid]
        item = assignment[example.occurrence_id]
        split.append(item.split)
        components.append(item.component_id)
    val = tuple(index for index, name in enumerate(split) if name == "val")
    test = tuple(index for index, name in enumerate(split) if name == "test")
    if not val or not test:
        raise HarnessInvariantError("relation/evidence-disjoint split is empty")
    return val, test, tuple(components), {
        "suite_id": suite.suite_id,
        "raw_snapshot_sha256": suite.raw_snapshot_sha256,
        "sidecar_file_sha256": _file_sha256(raw_sidecar_path),
        "split_seed": split_seed,
        "n_val": len(val), "n_test": len(test),
        "n_components": len(set(components)),
        "grouping": "union(relation_template_id, exact_evidence_content_id)",
        "prepared_row_provenance_sha256": sha256(
            canonical_json(tuple(asdict(row) for row in rebound_rows)).encode("utf-8")
        ).hexdigest(),
    }


def cluster_inference(
    delta: np.ndarray,
    components: Sequence[str],
    *,
    n_bootstrap: int,
    n_signflips: int,
    seed: int,
) -> dict[str, Any]:
    values = np.asarray(delta, dtype=np.float64)
    if values.ndim != 1 or not values.size or values.size != len(components):
        raise ValueError("delta/components must be non-empty and aligned")
    grouped = {
        key: np.flatnonzero(np.asarray(components) == key)
        for key in sorted(set(components))
    }
    keys = tuple(grouped)
    rng = np.random.default_rng(seed)
    draws = np.empty(n_bootstrap, dtype=np.float64)
    for index in range(n_bootstrap):
        chosen = rng.integers(0, len(keys), len(keys))
        sample = np.concatenate([values[grouped[keys[item]]] for item in chosen])
        draws[index] = float(sample.mean())
    sums = np.asarray([float(values[grouped[key]].sum()) for key in keys])
    observed = float(values.mean())
    greater_equal = 0
    if len(keys) <= 20:
        total_signflips = 1 << len(keys)
        for start in range(0, total_signflips, 5000):
            stop = min(start + 5000, total_signflips)
            numbers = np.arange(start, stop, dtype=np.uint64)[:, None]
            shifts = np.arange(len(keys), dtype=np.uint64)[None, :]
            bits = ((numbers >> shifts) & 1).astype(np.float64)
            signs = bits * 2.0 - 1.0
            greater_equal += int(np.sum((signs @ sums) / values.size >= observed))
        p_signflip = greater_equal / total_signflips
        signflip_method = "exact"
    else:
        total_signflips = n_signflips
        remaining = n_signflips
        while remaining:
            batch = min(5000, remaining)
            signs = rng.choice(np.asarray((-1.0, 1.0)), size=(batch, len(keys)))
            greater_equal += int(np.sum((signs @ sums) / values.size >= observed))
            remaining -= batch
        p_signflip = (greater_equal + 1) / (n_signflips + 1)
        signflip_method = "monte_carlo"
    return {
        "n_queries": int(values.size), "n_components": len(keys),
        "mean_delta": round(observed, 6),
        "ci95": [round(float(np.percentile(draws, 2.5)), 6),
                 round(float(np.percentile(draws, 97.5)), 6)],
        "p_cluster_signflip_one_sided": round(p_signflip, 6),
        "n_bootstrap": n_bootstrap, "n_signflips": total_signflips,
        "signflip_method": signflip_method, "resampling_seed": seed,
    }


def select_policy(
    compiled: CompiledSegmentV1,
    val_indices: Sequence[int],
    components: Sequence[str],
) -> tuple[typed.TypedCompositionPolicyV1, str, dict[str, Any]]:
    """Select once on dev-val with the frozen query-weighted objective."""

    if len(components) != len(compiled.segment.evaluation_rows):
        raise ValueError("selection component assignments are not aligned")

    static = {
        "cosine": _metric_arrays(compiled.cosine, compiled, val_indices),
        "bm25": _metric_arrays(compiled.bm25, compiled, val_indices),
        "rrf": _metric_arrays(compiled.rrf, compiled, val_indices),
    }
    strongest = max(
        static,
        key=lambda name: (
            float(static[name]["ndcg10"].mean()),
            float(static[name]["asr10"].mean()), name,
        ),
    )
    surface: list[tuple[tuple[float, ...], typed.TypedCompositionPolicyV1, dict[str, Any]]] = []
    for policy in POLICY_GRID:
        k2, _receipts, _diag = _typed_matrix(compiled, policy)
        k1_policy = replace(policy, max_hops=1)
        k1, _k1_receipts, _k1_diag = _typed_matrix(compiled, k1_policy)
        m2 = _metric_arrays(k2, compiled, val_indices)
        m1 = _metric_arrays(k1, compiled, val_indices)
        # Frozen tuning objective: query-weighted K2 mean nDCG, then ASR,
        # then the smaller intervention and seed budget.  Components govern
        # inference/certification, not the point estimand or policy objective.
        key = (
            float(m2["ndcg10"].mean()), float(m2["asr10"].mean()),
            -policy.mu, -policy.seed_k,
        )
        surface.append((key, policy, {
            "policy": asdict(policy),
            "tune_mean_ndcg10": round(key[0], 6),
            "tune_mean_asr10": round(key[1], 6),
            "k2_metrics": _means(m2), "k1_metrics": _means(m1),
        }))
    _key, chosen, _row = max(surface, key=lambda item: item[0])
    return chosen, strongest, {
        "tune_objective": "query mean nDCG10, ASR10, smaller mu, smaller seed_k",
        "inference_grouped_by": "relation/evidence component",
        "strongest_static": strongest,
        "static_metrics": {name: _means(value) for name, value in static.items()},
        "chosen_policy": asdict(chosen),
        "surface": [item[2] for item in sorted(surface, key=lambda item: item[0], reverse=True)],
    }


def _comparison(
    treatment: Mapping[str, np.ndarray],
    comparator: Mapping[str, np.ndarray],
    components: Sequence[str],
    config: EvaluationConfigV1,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for metric_name in ("ndcg10", "asr10", "support_recall10"):
        delta = treatment[metric_name] - comparator[metric_name]
        inference = cluster_inference(
            delta, components, n_bootstrap=config.n_bootstrap,
            n_signflips=config.n_signflips, seed=config.resampling_seed,
        )
        threshold = PRIMARY_THRESHOLDS.get(metric_name)
        inference["threshold"] = threshold
        inference["passes_threshold_and_ci"] = bool(
            threshold is not None and inference["mean_delta"] >= threshold
            and inference["ci95"][0] > 0
        )
        out[metric_name] = inference
    return out


def _receipt_teeth(
    receipts: Sequence[typed.TypedCompositionReceiptV1],
    compiled: CompiledSegmentV1,
    indices: Sequence[int],
) -> dict[str, Any]:
    depth2_gold_queries: list[int] = []
    depth2_paths = wrong_paths = 0
    violations: list[str] = []
    for index in indices:
        receipt = receipts[index]
        gold = set(int(value) for value in compiled.gold_ordinals[index])
        hit = False
        for path in receipt.promoted_paths:
            if path.selected_depth >= 2:
                depth2_paths += 1
                wrong_paths += path.target not in gold
            if path.first_reached_depth == 2 and path.target in gold:
                hit = True
                if (len(path.steps) < 2 or not path.intermediate_target_ids or
                        any(not step.source_selector.exact or not step.target_selector.exact
                            for step in path.steps)):
                    violations.append(
                        f"query={compiled.segment.evaluation_rows[index].qid}:target={path.target_id}"
                    )
        if hit:
            depth2_gold_queries.append(index)
    if violations:
        raise HarnessInvariantError(
            "depth-2 GOLD receipt lacks two selectors/intermediate: " + violations[0]
        )
    return {
        "query_indices": tuple(depth2_gold_queries),
        "n_depth2_first_gold_queries": len(depth2_gold_queries),
        "required_queries": max(10, math.ceil(0.05 * len(indices))),
        "n_depth2_promoted_paths": depth2_paths,
        "n_wrong_depth2_paths": wrong_paths,
        "wrong_depth2_path_rate": round(wrong_paths / max(depth2_paths, 1), 6),
        "receipt_violations": 0,
    }


def _typed_endpoint_signature(arc: typed.TypedEvidenceArcV1) -> tuple[Any, ...]:
    """Identity of one directed, typed endpoint, excluding arc/origin labels."""

    return (
        arc.source_target, arc.target_target,
        arc.source_claim_id, arc.target_claim_id,
        arc.source_predicate.exact,
        arc.target_predicate.exact if arc.target_predicate else None,
        arc.source_argument_role, arc.target_argument_role,
        arc.join_entity_id,
    )


def _graph_duplicate_typed_endpoints(
    graph: typed.TypedCompositionGraphV1,
) -> int:
    signatures = [_typed_endpoint_signature(arc) for arc in graph.arcs]
    return len(signatures) - len(set(signatures))


def _rewired_duplicate_typed_endpoints(
    graph: typed.TypedCompositionGraphV1,
    rewired_arc_ids: set[str],
) -> int:
    rewired = [
        _typed_endpoint_signature(arc) for arc in graph.arcs
        if arc.arc_id in rewired_arc_ids
    ]
    unselected = {
        _typed_endpoint_signature(arc) for arc in graph.arcs
        if arc.arc_id not in rewired_arc_ids
    }
    return sum(signature in unselected for signature in rewired)


def _second_edge_query_diagnostic(
    compiled: CompiledSegmentV1,
    policy: typed.TypedCompositionPolicyV1,
    real_matrix: np.ndarray,
    receipts: Sequence[typed.TypedCompositionReceiptV1],
    indices: Sequence[int],
    components: Sequence[str],
    config: EvaluationConfigV1,
) -> dict[str, Any]:
    """Query-local second-edge null with an exact matched-K1 invariant.

    The primary estimand is query weighted over *all* requested indices.  A
    query without an observed second edge therefore contributes an exact zero,
    rather than disappearing from the denominator.  An observed second edge
    without a matched-K1 decoy remains fail-closed and cannot be imputed.
    """

    graph = compiled.b3_graph
    if _graph_duplicate_typed_endpoints(graph):
        raise HarnessInvariantError(
            "real graph contains duplicate directed/typed endpoint tuples"
        )
    all_arcs = tuple(graph.arcs)
    rows: list[dict[str, Any]] = []
    primary_deltas: dict[str, list[float]] = defaultdict(list)
    valid_components: list[str] = []
    observed = invalid = 0
    for index in indices:
        qid = compiled.segment.evaluation_rows[index].qid
        real_receipt = receipts[index]
        second_ids = tuple(sorted({
            path.steps[1].arc_id for path in real_receipt.promoted_paths
            if len(path.steps) >= 2
        }))
        if not second_ids:
            zero_delta = {
                metric: 0.0
                for metric in ("ndcg10", "asr10", "support_recall10")
            }
            for metric, value in zero_delta.items():
                primary_deltas[metric].append(value)
            valid_components.append(components[index])
            rows.append({
                "qid": qid, "status": "UNCHANGED_NO_SECOND_EDGE",
                "second_edge_arc_ids": (),
                "real_minus_null": zero_delta,
            })
            continue
        observed += 1
        second_set = set(second_ids)
        candidates = sorted(
            (arc for arc in all_arcs if arc.arc_id not in second_set),
            key=lambda arc: (
                sha256(f"second-edge|{qid}|{arc.arc_id}".encode()).hexdigest(),
                arc.arc_id,
            ),
        )
        null_graph: typed.TypedCompositionGraphV1 | None = None
        null_scores: np.ndarray | None = None
        matched_k1: typed.MatchedK1AblationV1 | None = None
        chosen_decoy: str | None = None
        detail = "no non-self derangement with a decoy edge"
        attempted_decoys = 0
        k1_rejected_decoys = 0
        duplicate_rejected_decoys = 0
        last_null_k1_sha256: str | None = None
        real_k1 = real_receipt.k1_ablation
        for decoy in candidates:
            attempted_decoys += 1
            try:
                candidate_graph = typed.target_shuffle_null_control(
                    graph, (*second_ids, decoy.arc_id), seed=0,
                )
            except ValueError as exc:
                detail = str(exc)
                continue
            selected_ids = {*second_ids, decoy.arc_id}
            if (_rewired_duplicate_typed_endpoints(candidate_graph, selected_ids)
                    or _graph_duplicate_typed_endpoints(candidate_graph)):
                detail = "rewired arc duplicates an existing directed/typed endpoint"
                duplicate_rejected_decoys += 1
                continue
            candidate_scores, _residual, candidate_receipt = (
                typed.compose_typed_scores(
                    compiled.segment.evaluation_rows[index].question,
                    compiled.cosine[index], candidate_graph, policy,
                )
            )
            candidate_k1 = candidate_receipt.k1_ablation
            last_null_k1_sha256 = (
                candidate_k1.score_sha256 if candidate_k1 else None
            )
            if (real_k1 is None or candidate_k1 is None
                    or real_k1.score_sha256 != candidate_k1.score_sha256):
                detail = (
                    "matched K1 ablation missing" if real_k1 is None
                    or candidate_k1 is None else "matched K1 score digest changed"
                )
                k1_rejected_decoys += 1
                continue
            null_graph = candidate_graph
            null_scores = candidate_scores
            matched_k1 = candidate_k1
            chosen_decoy = decoy.arc_id
            break
        if null_graph is None:
            invalid += 1
            rows.append({
                "qid": qid, "status": "NULL_INVALID", "reason": detail,
                "second_edge_arc_ids": second_ids,
                "attempted_decoys": attempted_decoys,
                "k1_rejected_decoys": k1_rejected_decoys,
                "duplicate_rejected_decoys": duplicate_rejected_decoys,
                "real_k1_sha256": real_k1.score_sha256 if real_k1 else None,
                "last_null_k1_sha256": last_null_k1_sha256,
            })
            continue
        assert null_scores is not None
        assert matched_k1 is not None and real_k1 is not None
        real_metrics = _query_metrics(
            real_matrix[index], compiled.gold_ordinals[index], seed=index + 1,
        )
        null_metrics = _query_metrics(
            null_scores, compiled.gold_ordinals[index], seed=index + 1,
        )
        delta = {
            metric: real_metrics[metric] - null_metrics[metric]
            for metric in ("ndcg10", "asr10", "support_recall10")
        }
        for metric, value in delta.items():
            primary_deltas[metric].append(value)
        valid_components.append(components[index])
        rows.append({
            "qid": qid, "status": "VALID",
            "second_edge_arc_ids": second_ids, "decoy_arc_id": chosen_decoy,
            "matched_k1_sha256": real_k1.score_sha256,
            "attempted_decoys": attempted_decoys,
            "k1_rejected_decoys": k1_rejected_decoys,
            "duplicate_rejected_decoys": duplicate_rejected_decoys,
            "real_minus_null": {key: round(value, 6) for key, value in delta.items()},
        })
    inference = {
        metric: cluster_inference(
            np.asarray(values, dtype=np.float64), valid_components,
            n_bootstrap=config.n_bootstrap, n_signflips=config.n_signflips,
            seed=config.resampling_seed,
        )
        for metric, values in primary_deltas.items() if values
    }
    mean_delta = {
        metric: result["mean_delta"] for metric, result in inference.items()
    }
    valid = len(valid_components)
    estimand_complete = valid == len(indices) and invalid == 0
    passed = bool(
        observed > 0 and estimand_complete
        and inference.get("ndcg10", {}).get("ci95", [0])[0] > 0
        and inference.get("asr10", {}).get("ci95", [0])[0] > 0
    )
    return {
        "status": "PASS" if passed else "NULL_INVALID" if invalid else "FAIL",
        "estimand": "query-weighted over all requested indices",
        "total_queries": len(indices),
        "observed_queries": observed,
        "unchanged_no_second_edge_queries": len(indices) - observed,
        "valid_queries": valid,
        "invalid_queries": invalid, "mean_real_minus_null": mean_delta,
        "cluster_inference": inference,
        "estimand_complete": estimand_complete,
        "matched_k1_digest_invariant": invalid == 0,
        "passes_both_primary": passed, "queries": rows,
    }


def _graph_diagnostics(
    compiled: CompiledSegmentV1,
    indices: Sequence[int],
) -> dict[str, Any]:
    outgoing: dict[int, set[int]] = defaultdict(set)
    join_sources: dict[str, set[str]] = defaultdict(set)
    for arc in compiled.b3_graph.arcs:
        outgoing[arc.source_target].add(arc.target_target)
        join_sources[arc.join_entity_id].update((arc.source_id, arc.target_id))
    false_links: list[float] = []
    for index in indices:
        gold = set(int(value) for value in compiled.gold_ordinals[index])
        linked = [(source, target) for source in gold for target in outgoing[source]]
        false_links.append(
            sum(target not in gold for _, target in linked) / max(len(linked), 1)
        )
    component_sizes: list[int] = []
    undirected: list[set[int]] = [set() for _ in compiled.target_ids]
    for arc in compiled.b3_graph.arcs:
        undirected[arc.source_target].add(arc.target_target)
        undirected[arc.target_target].add(arc.source_target)
    seen: set[int] = set()
    for start in range(len(undirected)):
        if start in seen:
            continue
        frontier = {start}
        component: set[int] = set()
        while frontier:
            node = frontier.pop()
            if node in component:
                continue
            component.add(node)
            frontier.update(undirected[node] - component)
        seen.update(component)
        component_sizes.append(len(component))
    return {
        "b1_arcs": len(compiled.b1_graph.arcs),
        "b3_typed_arcs": len(compiled.b3_graph.arcs),
        "b3_shared_entity_arcs": compiled.b3_build.stats["n_shared_entity_arcs"],
        "b3_title_claim_arcs": compiled.b3_build.stats["n_claim_arcs"],
        "b3_title_fallback_arcs_excluded_from_typed_kernel": compiled.b3_build.stats[
            "n_title_fallback_arcs"
        ],
        "mean_gold_outgoing_false_link_rate": round(float(np.mean(false_links)), 6),
        "max_join_document_frequency": max(
            (len(values) for values in join_sources.values()), default=0,
        ),
        "n_components": len(component_sizes),
        "largest_component": max(component_sizes, default=0),
        "largest_component_fraction": round(
            max(component_sizes, default=0) / max(len(compiled.target_ids), 1), 6
        ),
    }


def evaluate_fixed_policy(
    compiled: CompiledSegmentV1,
    policy: typed.TypedCompositionPolicyV1,
    strongest_static: str,
    indices: Sequence[int],
    components: Sequence[str],
    config: EvaluationConfigV1,
    *,
    seed: int,
    run_nulls: bool,
) -> dict[str, Any]:
    indices = tuple(indices)
    local_components = tuple(components[index] for index in indices)
    k2_matrix, k2_receipts, k2_diag = _typed_matrix(compiled, policy)
    k1_policy = replace(policy, max_hops=1)
    k1_matrix, _k1_receipts, k1_diag = _typed_matrix(compiled, k1_policy)
    b1_k2_matrix, b1_k2_diag = _b1_matrix(compiled, policy, hops=2)
    b1_k1_matrix, b1_k1_diag = _b1_matrix(compiled, policy, hops=1)
    static_matrix = {
        "cosine": compiled.cosine, "bm25": compiled.bm25, "rrf": compiled.rrf,
    }[strongest_static]
    matrices = {
        "cosine": compiled.cosine,
        "bm25": compiled.bm25,
        "rrf": compiled.rrf,
        "b1_k1": b1_k1_matrix,
        "b1_k2": b1_k2_matrix,
        "b3_k1": k1_matrix,
        "b3_k2": k2_matrix,
    }
    metric_rows = {
        name: _metric_arrays(matrix, compiled, indices)
        for name, matrix in matrices.items()
    }
    comparisons = {
        "vs_matched_b3_k1": _comparison(
            metric_rows["b3_k2"], metric_rows["b3_k1"], local_components,
            config,
        ),
        "vs_b1_k2": _comparison(
            metric_rows["b3_k2"], metric_rows["b1_k2"], local_components,
            config,
        ),
        "vs_strongest_static": _comparison(
            metric_rows["b3_k2"], metric_rows[strongest_static], local_components,
            config,
        ),
    }
    teeth = _receipt_teeth(k2_receipts, compiled, indices)
    cohort = tuple(teeth.pop("query_indices"))
    if cohort:
        cohort_k2 = _metric_arrays(k2_matrix, compiled, cohort)
        cohort_k1 = _metric_arrays(k1_matrix, compiled, cohort)
        teeth["cohort_k2_minus_k1"] = {
            metric: round(float((cohort_k2[metric] - cohort_k1[metric]).mean()), 6)
            for metric in ("ndcg10", "asr10", "support_recall10")
        }
    else:
        teeth["cohort_k2_minus_k1"] = None

    null_report: dict[str, Any] = {
        "run": run_nulls, "controls": [],
        "multigraph_policy": (
            "duplicate directed/typed endpoint tuples forbidden"
        ),
    }
    if run_nulls:
        all_arc_ids = tuple(arc.arc_id for arc in compiled.b3_graph.arcs)
        if len(all_arc_ids) < 2:
            raise HarnessInvariantError("null controls need at least two typed arcs")
        controls: list[tuple[str, int, typed.TypedCompositionGraphV1]] = []
        invalid_controls: list[dict[str, Any]] = []
        for null_seed in config.null_seeds:
            try:
                topology = typed.target_shuffle_null_control(
                    compiled.b3_graph, all_arc_ids, seed=null_seed,
                )
            except ValueError as exc:
                invalid_controls.append({
                    "kind": "topology_target_shuffle", "seed": null_seed,
                    "status": "NULL_INVALID", "reason": str(exc),
                })
            else:
                duplicate_count = _graph_duplicate_typed_endpoints(topology)
                if duplicate_count:
                    invalid_controls.append({
                        "kind": "topology_target_shuffle", "seed": null_seed,
                        "status": "NULL_INVALID",
                        "reason": "duplicate directed/typed endpoint tuple",
                        "duplicate_typed_endpoints": duplicate_count,
                    })
                else:
                    controls.append(("topology_target_shuffle", null_seed, topology))
            try:
                relation = typed.relation_shuffle_null_control(
                    compiled.b3_graph, all_arc_ids, seed=null_seed,
                )
            except ValueError as exc:
                invalid_controls.append({
                    "kind": "relation_role_shuffle", "seed": null_seed,
                    "status": "NULL_INVALID", "reason": str(exc),
                })
            else:
                duplicate_count = _graph_duplicate_typed_endpoints(relation)
                if duplicate_count:
                    invalid_controls.append({
                        "kind": "relation_role_shuffle", "seed": null_seed,
                        "status": "NULL_INVALID",
                        "reason": "duplicate directed/typed endpoint tuple",
                        "duplicate_typed_endpoints": duplicate_count,
                    })
                else:
                    controls.append(("relation_role_shuffle", null_seed, relation))
        for kind, null_seed, graph in controls:
            null_matrix, _receipts, diag = _typed_matrix(compiled, policy, graph=graph)
            null_metrics = _metric_arrays(null_matrix, compiled, indices)
            null_inference = _comparison(
                metric_rows["b3_k2"], null_metrics, local_components, config,
            )
            delta = {
                metric: round(float(
                    (metric_rows["b3_k2"][metric] - null_metrics[metric]).mean()
                ), 6)
                for metric in ("ndcg10", "asr10", "support_recall10")
            }
            null_report["controls"].append({
                "kind": kind, "seed": null_seed,
                "status": "VALID",
                "topology_sha256": graph.topology_sha256,
                "duplicate_typed_endpoints": 0,
                "metrics": _means(null_metrics), "real_minus_null": delta,
                "cluster_inference": null_inference,
                "diagnostics": diag,
            })
        null_report["controls"].extend(invalid_controls)
        second_edge = _second_edge_query_diagnostic(
            compiled, policy, k2_matrix, k2_receipts, indices,
            components, config,
        )
        null_report["second_edge_query_diagnostic"] = second_edge
        null_report["real_beats_every_null_both_primary"] = bool(
            not invalid_controls and controls and second_edge["passes_both_primary"] and all(
            row["cluster_inference"]["ndcg10"]["ci95"][0] > 0
            and row["cluster_inference"]["asr10"]["ci95"][0] > 0
            for row in null_report["controls"] if row["status"] == "VALID"
            )
        )
    else:
        null_report["real_beats_every_null_both_primary"] = None

    pass_comparisons = all(
        comparison[metric]["passes_threshold_and_ci"]
        for comparison in comparisons.values()
        for metric in ("ndcg10", "asr10")
    )
    cohort_gain = teeth["cohort_k2_minus_k1"]
    pass_cohort = bool(
        teeth["n_depth2_first_gold_queries"] >= teeth["required_queries"]
        and cohort_gain is not None
        and cohort_gain["ndcg10"] > 0
        and cohort_gain["asr10"] > 0
    )
    graph_diagnostics = _graph_diagnostics(compiled, indices)
    graph_safety = bool(
        graph_diagnostics["largest_component_fraction"] <= 0.25
        and graph_diagnostics["max_join_document_frequency"] <= 8
    )
    query_safety = bool(
        k2_diag["fanout_gate_trips"] == 0 and k2_diag["join_hub_gate_trips"] == 0
    )
    passed = bool(
        pass_comparisons and pass_cohort and k2_diag["apply_coverage"] >= 0.50
        and graph_safety and query_safety
        and (not run_nulls or null_report["real_beats_every_null_both_primary"])
    )
    return {
        "n_queries": len(indices), "policy": asdict(policy),
        "strongest_static": strongest_static,
        "metrics": {name: _means(values) for name, values in metric_rows.items()},
        "score_digests": {name: _array_sha256(matrix[np.asarray(indices)])
                          for name, matrix in matrices.items()},
        "comparisons": comparisons,
        "depth2_gold_teeth": teeth,
        "composition_diagnostics": {"b3_k2": k2_diag, "b3_k1": k1_diag,
                                    "b1_k2": b1_k2_diag, "b1_k1": b1_k1_diag},
        "graph_diagnostics": graph_diagnostics,
        "safety_gate": {
            "largest_component_le_0_25": graph_diagnostics[
                "largest_component_fraction"
            ] <= 0.25,
            "max_join_df_le_8": graph_diagnostics[
                "max_join_document_frequency"
            ] <= 8,
            "no_query_fanout_or_hub_trip": query_safety,
            "pass": graph_safety and query_safety,
        },
        "null_gate": null_report,
        "pass": passed,
    }


def _segment_accounting(
    compiled: CompiledSegmentV1,
    extraction: ExtractionArtifactV1,
) -> dict[str, Any]:
    sources = {item.source_id for item in compiled.segment.paragraphs}
    records = [record for record in extraction.records if record.source_id in sources]
    return {
        "n_paragraphs": len(sources),
        "n_recorded_extractions": len(records),
        "n_verified_observations": compiled.b3_build.stats["n_verified_observations"],
        "n_nary_claims": compiled.b3_build.stats["n_nary_claims"],
        "compiler_quarantined_claims": compiled.b3_build.stats["n_quarantined_claims"],
        "compiler_quarantine_reasons": compiled.b3_build.stats["quarantine_reasons"],
        "shared_entity_quarantines": compiled.b3_build.stats[
            "n_quarantined_shared_entities"
        ],
        "shared_entity_quarantine_reasons": compiled.b3_build.stats[
            "shared_quarantine_reasons"
        ],
        "extractor_status_counts": dict(sorted(Counter(
            record.status.value for record in records
        ).items())),
    }


def _load_adjudication(path: str | Path | None) -> Mapping[str, Any] | None:
    if path is None:
        return None
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactIntegrityError(f"invalid arc adjudication: {exc}") from exc
    if not isinstance(value, Mapping):
        raise ArtifactIntegrityError("arc adjudication must be an object")
    return value


def _bh_qvalues(items: Sequence[tuple[str, float]]) -> dict[str, float]:
    ordered = sorted(items, key=lambda item: (item[1], item[0]))
    out: dict[str, float] = {}
    running = 1.0
    total = len(ordered)
    for rank in range(total, 0, -1):
        key, value = ordered[rank - 1]
        running = min(running, value * total / rank)
        out[key] = min(running, 1.0)
    return out


def _committed_path(manifest_path: Path, relative: str) -> Path:
    _validate_committed_path(relative, label="committed path")
    return (manifest_path.parent / relative).resolve()


def _stage_authorization(
    manifest_path: Path,
    manifest: Mapping[str, Any],
    stage: str,
    *,
    certificate_transition_sha256: str | None,
) -> dict[str, str]:
    parents = {
        "run_manifest_sha256": _file_sha256(manifest_path),
        "protocol_sha256": manifest["protocol"]["sha256"],
        "code_root_sha256": lifecycle.authorization_code_root(
            manifest["code_sha256"]
        ),
        "preflight_receipt_sha256": manifest["preflight"]["sha256"],
    }
    if stage == "fresh":
        parents["certificate_transition_sha256"] = _require_sha256(
            certificate_transition_sha256,
            label="certificate_transition_sha256",
        )
    elif certificate_transition_sha256 is not None:
        raise ArtifactIntegrityError(
            "development artifacts cannot cite a fresh transition"
        )
    return parents


def extraction_close_validation(
    artifact: ExtractionArtifactV1,
) -> dict[str, Any]:
    accounting_json = canonical_json(dict(artifact.accounting))
    accounting = json.loads(accounting_json)
    return {
        "schema_version": "hswm-h3-extraction-close-validation/v3",
        "file_sha256": artifact.file_sha256,
        "record_rows": len(artifact.records),
        "accounting": accounting,
        "accounting_sha256": sha256(accounting_json.encode("utf-8")).hexdigest(),
    }


def embedding_close_validation(
    artifact: EmbeddingArtifactV1,
    *,
    receipt_file_sha256: str,
) -> dict[str, Any]:
    if artifact.receipt is None:
        raise ArtifactIntegrityError("embedding CLOSE requires a receipt")
    return {
        "schema_version": "hswm-h3-embedding-close-validation/v1",
        "npz_sha256": artifact.file_sha256,
        "receipt_file_sha256": receipt_file_sha256,
        "receipt_sha256": artifact.receipt["receipt_sha256"],
        "n_records": len(artifact.ids),
        "dimension": int(artifact.vectors.shape[1]),
        "snapshot_root_sha256": artifact.receipt[
            "model_attestation"
        ]["snapshot_root_sha256"],
    }


def _load_stage_artifacts(
    stage: str,
    *,
    manifest_path: str | Path,
    manifest: Mapping[str, Any],
    certificate_transition_sha256: str | None = None,
) -> tuple[
    dict[str, prep.PreparedSegmentV1], ExtractionArtifactV1,
    EmbeddingArtifactV1, dict[str, Any],
]:
    """Load only manifest-committed outputs with valid OPEN/CLOSE lineage."""

    if stage not in STAGES:
        raise ValueError(f"unsupported artifact stage {stage!r}")
    manifest_file = Path(manifest_path).resolve()
    commitment = manifest["stage_artifacts"][stage]
    parents = _stage_authorization(
        manifest_file, manifest, stage,
        certificate_transition_sha256=certificate_transition_sha256,
    )
    segments: dict[str, prep.PreparedSegmentV1] = {}
    for dataset in DATASETS:
        key = f"{dataset}_{stage}"
        segment_binding = commitment["segments"][dataset]
        segment = load_prepared_segment(
            _committed_path(manifest_file, segment_binding["path"]),
            expected_sha256=segment_binding["sha256"],
        )
        if segment.dataset != dataset or segment.split != stage:
            raise ArtifactIntegrityError(f"segment key/content mismatch: {key}")
        segments[key] = segment
    ordered_segments = tuple(segments[f"{dataset}_{stage}"] for dataset in DATASETS)
    preimages = _verify_preimage_receipt(
        commitment["preimages"], ordered_segments,
    )
    paths = {
        key: _committed_path(manifest_file, value)
        for key, value in commitment["output_paths"].items()
    }
    try:
        extraction_open = lifecycle.load_open_receipt(
            paths["extraction_open_receipt"]
        )
        lifecycle.assert_authorization(
            extraction_open, stage=stage, expected=parents,
        )
        if (extraction_open["artifact_kind"] != "extraction_jsonl"
                or extraction_open["mode"] != "append_log"
                or extraction_open["reservation"]["output_path"]
                != str(paths["extraction_jsonl"])
                or extraction_open["input_sha256"]
                != preimages["extraction_jsonl_sha256"]
                or extraction_open["config_sha256"]
                != manifest["extractor"]["config_sha256"]
                or extraction_open["deployment_attestation_sha256"]
                != commitment["extraction_deployment_receipt"]["sha256"]
                or extraction_open["producer_code_sha256"]
                != manifest["code_sha256"]["recorded_llm_extractor.py"]):
            raise ArtifactIntegrityError("extraction OPEN commitment mismatch")
        extraction_close = lifecycle.load_close_receipt(
            paths["extraction_close_receipt"],
            open_receipt_path=paths["extraction_open_receipt"],
        )
    except lifecycle.ArtifactLifecycleError as exc:
        raise ArtifactIntegrityError(
            f"{stage} extraction lifecycle failed: {exc}"
        ) from exc
    expected_extractor = manifest["extractor"]
    extractions = load_extraction_artifact(
        paths["extraction_jsonl"], ordered_segments,
        expected_model_revision=expected_extractor["model_revision"],
        expected_prompt_sha256=expected_extractor["prompt_sha256"],
        expected_config_sha256=expected_extractor["config_sha256"],
    )
    if (
        extractions.accounting["attempt_cap_terminal_rate"]
        > MAX_ATTEMPT_CAP_TERMINAL_RATE
        or any(
            rate > MAX_ATTEMPT_CAP_TERMINAL_RATE_BY_DATASET
            for rate in extractions.accounting[
                "attempt_cap_terminal_rate_by_dataset"
            ].values()
        )
    ):
        raise ArtifactIntegrityError(
            "attempt-cap truncation trip rate exceeds frozen safety ceiling"
        )
    if (extraction_close["outputs"]["output_sha256"]
            != extractions.file_sha256
            or extraction_close["validation"]
            != extraction_close_validation(extractions)):
        raise ArtifactIntegrityError("extraction CLOSE domain validation mismatch")

    try:
        embedding_open = lifecycle.load_open_receipt(
            paths["embedding_open_receipt"]
        )
        lifecycle.assert_authorization(
            embedding_open, stage=stage, expected=parents,
        )
        expected_bundle_outputs = {
            "embedding_npz": str(paths["embedding_npz"]),
            "embedding_receipt": str(paths["embedding_receipt"]),
        }
        if (embedding_open["artifact_kind"] != "embedding_bundle"
                or embedding_open["mode"] != "exclusive_bundle"
                or embedding_open["reservation"]["run_directory"]
                != str(paths["embedding_run_directory"])
                or embedding_open["reservation"]["expected_outputs"]
                != expected_bundle_outputs
                or embedding_open["input_sha256"]
                != preimages["embedding_jsonl_sha256"]
                or embedding_open["config_sha256"]
                != manifest["embedding"]["config_sha256"]
                or embedding_open["deployment_attestation_sha256"]
                != manifest["embedding"]["model_attestation_receipt"]["sha256"]
                or embedding_open["producer_code_sha256"]
                != manifest["code_sha256"]["bge_m3_embed.py"]):
            raise ArtifactIntegrityError("embedding OPEN commitment mismatch")
        embedding_close = lifecycle.load_close_receipt(
            paths["embedding_close_receipt"],
            open_receipt_path=paths["embedding_open_receipt"],
        )
    except lifecycle.ArtifactLifecycleError as exc:
        raise ArtifactIntegrityError(
            f"{stage} embedding lifecycle failed: {exc}"
        ) from exc
    expected_embedding = manifest["embedding"]
    embeddings = load_embedding_artifact(
        paths["embedding_npz"], ordered_segments,
        receipt_path=paths["embedding_receipt"],
        expected_model_revision=expected_embedding["snapshot"],
        expected_execution=expected_embedding,
    )
    embedding_receipt_file_sha256 = _file_sha256(paths["embedding_receipt"])
    expected_close_outputs = {
        "embedding_npz": embeddings.file_sha256,
        "embedding_receipt": embedding_receipt_file_sha256,
    }
    observed_close_outputs = {
        key: value["sha256"] for key, value in embedding_close["outputs"].items()
    }
    if (observed_close_outputs != expected_close_outputs
            or embedding_close["validation"] != embedding_close_validation(
                embeddings,
                receipt_file_sha256=embedding_receipt_file_sha256,
            )):
        raise ArtifactIntegrityError("embedding CLOSE domain validation mismatch")
    runtime_receipt = {
        "status": "OPENED_CLOSED_AND_DOMAIN_VERIFIED",
        "segments": {
            dataset: dict(commitment["segments"][dataset]) for dataset in DATASETS
        },
        "preimages": preimages,
        "extraction_open_receipt_sha256": _file_sha256(
            paths["extraction_open_receipt"]
        ),
        "extraction_close_receipt_sha256": _file_sha256(
            paths["extraction_close_receipt"]
        ),
        "extraction_jsonl_sha256": extractions.file_sha256,
        "extraction_accounting": dict(extractions.accounting),
        "embedding_open_receipt_sha256": _file_sha256(
            paths["embedding_open_receipt"]
        ),
        "embedding_close_receipt_sha256": _file_sha256(
            paths["embedding_close_receipt"]
        ),
        "embedding_npz_sha256": embeddings.file_sha256,
        "embedding_receipt_file_sha256": embedding_receipt_file_sha256,
        "embedding_receipt_sha256": embeddings.receipt["receipt_sha256"],
        "embedding_snapshot_root_sha256": embeddings.receipt[
            "model_attestation"
        ]["snapshot_root_sha256"],
    }
    return segments, extractions, embeddings, runtime_receipt


def _write_json_once(path: Path, value: Mapping[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (canonical_json(dict(value)) + "\n").encode("utf-8")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ArtifactIntegrityError(
            f"phase artifact is first-write-wins: {path}"
        ) from exc
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    return sha256(encoded).hexdigest()


def _write_json_once_or_match(path: Path, value: Mapping[str, Any]) -> str:
    """Publish once, while allowing an exact idempotent crash resume."""

    encoded = (canonical_json(dict(value)) + "\n").encode("utf-8")
    if path.exists():
        try:
            existing = path.read_bytes()
        except OSError as exc:
            raise ArtifactIntegrityError(
                f"cannot read existing first-write artifact: {path}"
            ) from exc
        if existing != encoded:
            raise ArtifactIntegrityError(
                f"existing first-write artifact differs: {path}"
            )
        return sha256(existing).hexdigest()
    return _write_json_once(path, value)


def _phase_receipt_id(prefix: str, value: Mapping[str, Any], id_key: str) -> str:
    body = {key: child for key, child in value.items() if key != id_key}
    return prefix + sha256(canonical_json(body).encode("utf-8")).hexdigest()


def _phase_path(
    manifest_path: Path, manifest: Mapping[str, Any], key: str,
) -> Path:
    return _committed_path(manifest_path, manifest["phase_paths"][key])


def _create_certificate_transition(
    *,
    manifest_path: Path,
    manifest: Mapping[str, Any],
    development_report_path: Path,
    development_artifact_receipt: Mapping[str, Any],
    dataset_reports: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if (len(dataset_reports) != len(DATASETS)
            or any(item.get("certificate_admitted") is not True
                   for item in dataset_reports)):
        raise ArtifactIntegrityError(
            "certificate transition requires both development admissions"
        )
    certificates = {
        str(item["dataset"]): {
            "certificate_admitted": True,
            "selected_policy": dict(item["selection"]["chosen_policy"]),
            "strongest_static": str(item["selection"]["strongest_static"]),
            "selection_sha256": sha256(
                canonical_json(item["selection"]).encode("utf-8")
            ).hexdigest(),
            "certificate_sha256": sha256(
                canonical_json(item["certificate"]).encode("utf-8")
            ).hexdigest(),
        }
        for item in dataset_reports
    }
    value: dict[str, Any] = {
        "schema_version": CERTIFICATE_TRANSITION_SCHEMA_VERSION,
        "transition_id": "",
        "status": "BOTH_CERTIFICATES_PASS_FRESH_AUTHORIZED",
        "run_manifest_sha256": _file_sha256(manifest_path),
        "protocol_sha256": manifest["protocol"]["sha256"],
        "preflight_receipt_sha256": manifest["preflight"]["sha256"],
        "code_root_sha256": lifecycle.authorization_code_root(
            manifest["code_sha256"]
        ),
        "evaluation_config_sha256": sha256(
            canonical_json(manifest["evaluation_config"]).encode("utf-8")
        ).hexdigest(),
        "development_report_path": str(development_report_path),
        "development_report_sha256": _file_sha256(development_report_path),
        "development_artifact_receipt_sha256": sha256(
            canonical_json(dict(development_artifact_receipt)).encode("utf-8")
        ).hexdigest(),
        "certificates": certificates,
    }
    value["transition_id"] = _phase_receipt_id(
        "hswm:h3_b3_certificate_transition:v1:", value, "transition_id",
    )
    path = _phase_path(manifest_path, manifest, "certificate_transition")
    _write_json_once(path, value)
    return load_certificate_transition(path, manifest_path=manifest_path)


def load_certificate_transition(
    path: str | Path,
    *,
    manifest_path: str | Path,
) -> dict[str, Any]:
    source = Path(path).resolve()
    manifest_file = Path(manifest_path).resolve()
    manifest = load_run_manifest(manifest_file)
    if source != _phase_path(manifest_file, manifest, "certificate_transition"):
        raise ArtifactIntegrityError("certificate transition path is not committed")
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactIntegrityError(f"invalid certificate transition: {exc}") from exc
    _strict_root(value, {
        "schema_version", "transition_id", "status", "run_manifest_sha256",
        "protocol_sha256", "preflight_receipt_sha256", "code_root_sha256",
        "evaluation_config_sha256", "development_report_path",
        "development_report_sha256", "development_artifact_receipt_sha256",
        "certificates",
    }, label="certificate transition")
    report_path = _phase_path(manifest_file, manifest, "development_report")
    expected_id = _phase_receipt_id(
        "hswm:h3_b3_certificate_transition:v1:", value, "transition_id",
    )
    if (value["schema_version"] != CERTIFICATE_TRANSITION_SCHEMA_VERSION
            or value["transition_id"] != expected_id
            or value["status"] != "BOTH_CERTIFICATES_PASS_FRESH_AUTHORIZED"
            or value["run_manifest_sha256"] != _file_sha256(manifest_file)
            or value["protocol_sha256"] != manifest["protocol"]["sha256"]
            or value["preflight_receipt_sha256"] != manifest["preflight"]["sha256"]
            or value["code_root_sha256"]
            != lifecycle.authorization_code_root(manifest["code_sha256"])
            or value["evaluation_config_sha256"] != sha256(
                canonical_json(manifest["evaluation_config"]).encode("utf-8")
            ).hexdigest()
            or value["development_report_path"] != str(report_path)
            or value["development_report_sha256"] != _file_sha256(report_path)
            or not isinstance(value["certificates"], Mapping)
            or set(value["certificates"]) != set(DATASETS)
            or any(item.get("certificate_admitted") is not True
                   for item in value["certificates"].values())):
        raise ArtifactIntegrityError("certificate transition binding mismatch")
    try:
        development_report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactIntegrityError(f"invalid development report: {exc}") from exc
    try:
        report_datasets = development_report["datasets"]
        by_dataset = {
            str(item["dataset"]): item for item in report_datasets
        }
        expected_certificates = {
            dataset: {
                "certificate_admitted": True,
                "selected_policy": dict(
                    by_dataset[dataset]["selection"]["chosen_policy"]
                ),
                "strongest_static": str(
                    by_dataset[dataset]["selection"]["strongest_static"]
                ),
                "selection_sha256": sha256(canonical_json(
                    by_dataset[dataset]["selection"]
                ).encode("utf-8")).hexdigest(),
                "certificate_sha256": sha256(canonical_json(
                    by_dataset[dataset]["certificate"]
                ).encode("utf-8")).hexdigest(),
            }
            for dataset in DATASETS
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise ArtifactIntegrityError(
            "development report lacks exact certificate evidence"
        ) from exc
    if (development_report.get("schema_version")
            != DEVELOPMENT_REPORT_SCHEMA_VERSION
            or development_report.get("status") != "BOTH_CERTIFICATES_PASS"
            or development_report.get("run_manifest_sha256")
            != _file_sha256(manifest_file)
            or canonical_json(development_report.get("evaluation_config"))
            != canonical_json(manifest["evaluation_config"])
            or development_report.get("fresh_status") != "NOT_OPENED"
            or not isinstance(report_datasets, list)
            or len(report_datasets) != len(DATASETS)
            or set(by_dataset) != set(DATASETS)
            or any(item.get("certificate_admitted") is not True
                   for item in by_dataset.values())
            or value["certificates"] != expected_certificates
            or value["development_artifact_receipt_sha256"] != sha256(
                canonical_json(development_report["artifact_receipt"]).encode("utf-8")
            ).hexdigest()):
        raise ArtifactIntegrityError("transition development report mismatch")
    return value


def _create_fresh_artifact_seal(
    *,
    manifest_path: Path,
    manifest: Mapping[str, Any],
    transition_path: Path,
    transition: Mapping[str, Any],
    fresh_artifact_receipt: Mapping[str, Any],
    arc_deployment_receipt: Mapping[str, Any],
    arc_deployment_receipt_path: Path,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema_version": FRESH_ARTIFACT_SEAL_SCHEMA_VERSION,
        "seal_id": "",
        "status": "FRESH_ARTIFACTS_CLOSED_AND_VERIFIED",
        "run_manifest_sha256": _file_sha256(manifest_path),
        "certificate_transition_sha256": _file_sha256(transition_path),
        "certificate_transition_id": transition["transition_id"],
        "fresh_artifact_receipt": dict(fresh_artifact_receipt),
        "fresh_artifact_receipt_sha256": sha256(
            canonical_json(dict(fresh_artifact_receipt)).encode("utf-8")
        ).hexdigest(),
        "arc_deployment_receipt_path": str(arc_deployment_receipt_path),
        "arc_deployment_receipt_sha256": _file_sha256(
            arc_deployment_receipt_path
        ),
        "arc_deployment_id": arc_deployment_receipt["deployment_id"],
    }
    value["seal_id"] = _phase_receipt_id(
        "hswm:h3_b3_fresh_artifact_seal:v1:", value, "seal_id",
    )
    path = _phase_path(manifest_path, manifest, "fresh_artifact_seal")
    _write_json_once(path, value)
    return load_fresh_artifact_seal(
        path, manifest_path=manifest_path, transition_path=transition_path,
    )


def load_fresh_artifact_seal(
    path: str | Path,
    *,
    manifest_path: str | Path,
    transition_path: str | Path,
) -> dict[str, Any]:
    source = Path(path).resolve()
    manifest_file = Path(manifest_path).resolve()
    manifest = load_run_manifest(manifest_file)
    transition_file = Path(transition_path).resolve()
    transition = load_certificate_transition(
        transition_file, manifest_path=manifest_file,
    )
    if source != _phase_path(manifest_file, manifest, "fresh_artifact_seal"):
        raise ArtifactIntegrityError("fresh artifact seal path is not committed")
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactIntegrityError(f"invalid fresh artifact seal: {exc}") from exc
    _strict_root(value, {
        "schema_version", "seal_id", "status", "run_manifest_sha256",
        "certificate_transition_sha256", "certificate_transition_id",
        "fresh_artifact_receipt", "fresh_artifact_receipt_sha256",
        "arc_deployment_receipt_path", "arc_deployment_receipt_sha256",
        "arc_deployment_id",
    }, label="fresh artifact seal")
    expected_id = _phase_receipt_id(
        "hswm:h3_b3_fresh_artifact_seal:v1:", value, "seal_id",
    )
    arc_commitment = manifest["stage_artifacts"]["fresh"][
        "arc_deployment_receipt"
    ]
    arc_path = _committed_path(manifest_file, arc_commitment["path"])
    arc_receipt = _validate_deployment_attestation(
        arc_path, expected_model=arc_commitment["model"],
        expected_revision=arc_commitment["model_revision"],
        label="fresh arc deployment attestation",
    )
    if (value["schema_version"] != FRESH_ARTIFACT_SEAL_SCHEMA_VERSION
            or value["seal_id"] != expected_id
            or value["status"] != "FRESH_ARTIFACTS_CLOSED_AND_VERIFIED"
            or value["run_manifest_sha256"] != _file_sha256(manifest_file)
            or value["certificate_transition_sha256"] != _file_sha256(transition_file)
            or value["certificate_transition_id"] != transition["transition_id"]
            or value["arc_deployment_receipt_path"] != str(arc_path)
            or value["arc_deployment_receipt_sha256"] != _file_sha256(arc_path)
            or value["arc_deployment_id"] != arc_receipt["deployment_id"]
            or value["fresh_artifact_receipt_sha256"] != sha256(
                canonical_json(value["fresh_artifact_receipt"]).encode("utf-8")
            ).hexdigest()):
        raise ArtifactIntegrityError("fresh artifact seal binding mismatch")
    return value


def run_development_phase(
    *,
    manifest_path: str | Path,
    config: EvaluationConfigV1 = EvaluationConfigV1(),
) -> dict[str, Any]:
    """Evaluate development only, then authorize fresh with a write-once receipt."""

    manifest_file = Path(manifest_path).resolve()
    manifest = load_run_manifest(manifest_file)
    config_receipt = _evaluation_config_receipt(config)
    _require_frozen_evaluation_config(config_receipt)
    if canonical_json(manifest["evaluation_config"]) != canonical_json(config_receipt):
        raise ArtifactIntegrityError("runtime evaluation config differs from manifest")
    development_segments, extractions, embeddings, artifact_receipt = (
        _load_stage_artifacts(
            "development", manifest_path=manifest_file, manifest=manifest,
        )
    )
    compiled = {
        key: compile_segment(segment, extractions, embeddings)
        for key, segment in development_segments.items()
    }
    dataset_reports: list[dict[str, Any]] = []
    for dataset in DATASETS:
        world = compiled[f"{dataset}_development"]
        sidecar = manifest["development_sidecars"][dataset]
        sidecar_path = _committed_path(manifest_file, sidecar["path"])
        val, certificate_indices, components, split_receipt = development_assignments(
            world, sidecar_path, split_seed=config.split_seed,
            expected_file_sha256=sidecar["file_sha256"],
        )
        policy, strongest, selection = select_policy(world, val, components)
        certificate = evaluate_fixed_policy(
            world, policy, strongest, certificate_indices, components, config,
            seed=100 if dataset == "musique" else 200, run_nulls=False,
        )
        primary = certificate["comparisons"]["vs_matched_b3_k1"]
        admitted = bool(
            all(primary[metric]["passes_threshold_and_ci"]
                for metric in ("ndcg10", "asr10"))
            and certificate["safety_gate"]["pass"]
        )
        dataset_reports.append({
            "dataset": dataset,
            "verdict": "CERTIFICATE_PASS" if admitted else "CERTIFICATE_REFUSED",
            "certificate_admitted": admitted,
            "relation_evidence_split": split_receipt,
            "selection": selection,
            "certificate": certificate,
            "deployed_policy": (
                asdict(policy) if admitted else asdict(replace(policy, mu=0.0))
            ),
            "builder_accounting": _segment_accounting(world, extractions),
        })
    both_pass = all(item["certificate_admitted"] for item in dataset_reports)
    report = {
        "schema_version": DEVELOPMENT_REPORT_SCHEMA_VERSION,
        "status": "BOTH_CERTIFICATES_PASS" if both_pass else "CERTIFICATE_REFUSED",
        "run_manifest_sha256": _file_sha256(manifest_file),
        "evaluation_config": config_receipt,
        "artifact_receipt": artifact_receipt,
        "datasets": dataset_reports,
        "fresh_status": "NOT_OPENED",
    }
    report_path = _phase_path(manifest_file, manifest, "development_report")
    _write_json_once_or_match(report_path, report)
    if both_pass:
        transition_path = _phase_path(
            manifest_file, manifest, "certificate_transition",
        )
        if transition_path.exists():
            transition = load_certificate_transition(
                transition_path, manifest_path=manifest_file,
            )
        else:
            transition = _create_certificate_transition(
                manifest_path=manifest_file, manifest=manifest,
                development_report_path=report_path,
                development_artifact_receipt=artifact_receipt,
                dataset_reports=dataset_reports,
            )
        report = {**report, "certificate_transition": {
            "path": str(transition_path),
            "sha256": _file_sha256(transition_path),
            "transition_id": transition["transition_id"],
        }}
    else:
        report = {**report, "certificate_transition": None}
    return report


def run_fresh_phase(
    *,
    manifest_path: str | Path,
    config: EvaluationConfigV1 = EvaluationConfigV1(),
    arc_transport: arca.Transport | None = None,
) -> dict[str, Any]:
    """Run fresh confirmation only through the committed transition and seals.

    The separately frozen fresh grouping manifests are opened only after both
    arc packets have been sealed, adjudicated, and closed.  Prepared segments
    necessarily contain evaluator rows, so the narrower safety claim is that
    every packet is mechanically query-label-clean, not that the Python process
    has never loaded an evaluator row.  No caller-supplied artifact or
    adjudication path is accepted.
    """

    manifest_file = Path(manifest_path).resolve()
    manifest = load_run_manifest(manifest_file)
    config_receipt = _evaluation_config_receipt(config)
    _require_frozen_evaluation_config(config_receipt)
    if canonical_json(manifest["evaluation_config"]) != canonical_json(
        config_receipt
    ):
        raise ArtifactIntegrityError("runtime evaluation config differs from manifest")

    transition_path = _phase_path(
        manifest_file, manifest, "certificate_transition",
    )
    transition = load_certificate_transition(
        transition_path, manifest_path=manifest_file,
    )
    transition_sha256 = _file_sha256(transition_path)
    fresh_segments, fresh_extractions, fresh_embeddings, artifact_receipt = (
        _load_stage_artifacts(
            "fresh", manifest_path=manifest_file, manifest=manifest,
            certificate_transition_sha256=transition_sha256,
        )
    )

    arc_commitment = manifest["stage_artifacts"]["fresh"][
        "arc_deployment_receipt"
    ]
    arc_deployment_path = _committed_path(
        manifest_file, arc_commitment["path"],
    )
    arc_deployment = _validate_deployment_attestation(
        arc_deployment_path,
        expected_model=arc_commitment["model"],
        expected_revision=arc_commitment["model_revision"],
        label="fresh arc deployment attestation",
    )
    if arc_deployment["endpoint"] != arc_commitment["endpoint"]:
        raise ArtifactIntegrityError("fresh arc deployment endpoint mismatch")
    arc_config_spec = manifest["arc_adjudicator"]
    arc_config = arca.ArcAdjudicatorConfigV1(
        endpoint=arc_config_spec["endpoint"],
        deployment_attestation_sha256=_file_sha256(arc_deployment_path),
        model=arc_config_spec["model"],
        model_revision=arc_config_spec["model_revision"],
        max_concurrency=arc_config_spec["max_concurrency"],
        timeout_seconds=arc_config_spec["timeout_seconds"],
        max_tokens=arc_config_spec["max_tokens"],
    )

    fresh_seal_path = _phase_path(
        manifest_file, manifest, "fresh_artifact_seal",
    )
    if fresh_seal_path.exists():
        fresh_seal = load_fresh_artifact_seal(
            fresh_seal_path, manifest_path=manifest_file,
            transition_path=transition_path,
        )
        if fresh_seal["fresh_artifact_receipt"] != artifact_receipt:
            raise ArtifactIntegrityError(
                "existing fresh seal binds different stage artifacts"
            )
    else:
        fresh_seal = _create_fresh_artifact_seal(
            manifest_path=manifest_file, manifest=manifest,
            transition_path=transition_path, transition=transition,
            fresh_artifact_receipt=artifact_receipt,
            arc_deployment_receipt=arc_deployment,
            arc_deployment_receipt_path=arc_deployment_path,
        )
    fresh_seal_sha256 = _file_sha256(fresh_seal_path)

    # Leakage is checked from hash-bound prepared segments; development
    # extraction/embedding outputs need not be reopened during the fresh phase.
    development_segments = {
        dataset: load_prepared_segment(
            _committed_path(
                manifest_file,
                manifest["stage_artifacts"]["development"]["segments"][dataset][
                    "path"
                ],
            ),
            expected_sha256=manifest["stage_artifacts"]["development"][
                "segments"
            ][dataset]["sha256"],
        )
        for dataset in DATASETS
    }
    development_qids = {
        (segment.dataset, row.qid)
        for segment in development_segments.values()
        for row in segment.evaluation_rows
    }
    fresh_qids = {
        (segment.dataset, row.qid)
        for segment in fresh_segments.values()
        for row in segment.evaluation_rows
    }
    if development_qids & fresh_qids:
        raise ArtifactIntegrityError("development/fresh qid leakage")

    compiled_fresh = {
        key: compile_segment(segment, fresh_extractions, fresh_embeddings)
        for key, segment in fresh_segments.items()
    }
    arc_evidence: dict[str, dict[str, Any]] = {}
    for dataset in DATASETS:
        fresh = compiled_fresh[f"{dataset}_fresh"]
        packet = build_arc_precision_audit_packet(
            fresh.b3_build, dataset=dataset,
        )
        paths = {
            key: _committed_path(manifest_file, value)
            for key, value in manifest["stage_artifacts"]["fresh"][
                "arc_paths"
            ][dataset].items()
        }
        if paths["packet"].exists():
            existing_packet = arca.load_audit_packet(paths["packet"])
            if canonical_json(existing_packet) != canonical_json(packet):
                raise ArtifactIntegrityError(
                    f"existing {dataset} arc packet differs from compiler output"
                )
        else:
            _write_json_once(paths["packet"], packet)

        stage_run_id = f"{fresh_seal['seal_id']}:{dataset}"
        if paths["packet_seal"].exists():
            packet_seal = arca.load_packet_seal(paths["packet_seal"])
            expected_seal_bindings = {
                "stage_run_id": stage_run_id,
                "run_manifest_sha256": _file_sha256(manifest_file),
                "certificate_transition_sha256": transition_sha256,
                "fresh_artifact_seal_sha256": fresh_seal_sha256,
                "packet_path": str(paths["packet"]),
                "deployment_attestation_path": str(arc_deployment_path),
                "ledger_path": str(paths["ledger"]),
                "output_path": str(paths["adjudication"]),
                "close_path": str(paths["adjudication_close"]),
                "adjudication_config_sha256": arca.config_sha256(arc_config),
            }
            if any(
                packet_seal[key] != value
                for key, value in expected_seal_bindings.items()
            ):
                raise ArtifactIntegrityError(
                    f"existing {dataset} packet seal binding mismatch"
                )
        else:
            packet_seal = arca.create_packet_seal(
                seal_path=paths["packet_seal"],
                stage_run_id=stage_run_id,
                run_manifest_sha256=_file_sha256(manifest_file),
                certificate_transition_sha256=transition_sha256,
                fresh_artifact_seal_sha256=fresh_seal_sha256,
                packet_path=paths["packet"], config=arc_config,
                deployment_attestation_path=arc_deployment_path,
                ledger_path=paths["ledger"],
                output_path=paths["adjudication"],
                close_path=paths["adjudication_close"],
            )
        adjudication_run = arca.run_sealed_arc_adjudication(
            paths["packet_seal"], arc_config,
            deployment_attestation_path=arc_deployment_path,
            transport=arc_transport,
        )
        adjudication_close = arca.validate_adjudication_close(
            paths["packet_seal"],
        )
        arc_evidence[dataset] = {
            "packet": packet,
            "packet_seal": packet_seal,
            "adjudication": adjudication_run.adjudication,
            "adjudication_close": adjudication_close,
        }

    # Only now may the separately frozen fresh grouping manifests be opened.
    dataset_reports: list[dict[str, Any]] = []
    for dataset in DATASETS:
        fresh = compiled_fresh[f"{dataset}_fresh"]
        certificate = transition["certificates"][dataset]
        policy = typed.TypedCompositionPolicyV1(**certificate["selected_policy"])
        strongest = certificate["strongest_static"]
        holdout = manifest["fresh_holdout"][dataset]
        holdout_path = _committed_path(manifest_file, holdout["path"])
        components, grouping = fresh_manifest_components(
            fresh, holdout_path,
            expected_file_sha256=holdout["manifest_file_sha256"],
            expected_manifest_id=holdout["selected_manifest_id"],
        )
        fresh_report = evaluate_fixed_policy(
            fresh, policy, strongest,
            tuple(range(len(fresh.segment.evaluation_rows))), components, config,
            seed=300 if dataset == "musique" else 400, run_nulls=True,
        )
        audit_score = score_arc_precision_audit(
            arc_evidence[dataset]["packet"],
            arc_evidence[dataset]["adjudication"],
        )
        dataset_reports.append({
            "dataset": dataset,
            "verdict": "PENDING_MULTIPLICITY",
            "pass": False,
            "selected_policy": asdict(policy),
            "strongest_static": strongest,
            "fresh_confirmation": fresh_report,
            "fresh_grouping": grouping,
            "shared_join_identity_precision_audit": {
                **arc_evidence[dataset], "score": audit_score,
            },
            "builder_accounting": _segment_accounting(
                fresh, fresh_extractions,
            ),
        })

    hypotheses: list[tuple[str, float]] = []
    for report in dataset_reports:
        for comparison_name, comparison in report[
            "fresh_confirmation"
        ]["comparisons"].items():
            for metric in ("ndcg10", "asr10"):
                hypotheses.append((
                    f"{report['dataset']}:{comparison_name}:{metric}",
                    float(comparison[metric]["p_cluster_signflip_one_sided"]),
                ))
    if len(hypotheses) != 12:
        raise HarnessInvariantError(
            "primary BH family must contain exactly 12 hypotheses"
        )
    qvalues = _bh_qvalues(hypotheses)
    for report in dataset_reports:
        local_q: dict[str, float] = {}
        for comparison_name, comparison in report[
            "fresh_confirmation"
        ]["comparisons"].items():
            for metric in ("ndcg10", "asr10"):
                key = f"{report['dataset']}:{comparison_name}:{metric}"
                qvalue = round(qvalues[key], 6)
                comparison[metric]["bh_q_12"] = qvalue
                comparison[metric]["passes_bh_q_lt_0_05"] = qvalue < 0.05
                local_q[f"{comparison_name}:{metric}"] = qvalue
        multiplicity_pass = all(value < 0.05 for value in local_q.values())
        report["fresh_confirmation"]["multiplicity"] = {
            "method": "Benjamini-Hochberg",
            "family": "2 datasets x 2 primary metrics x 3 primary comparisons",
            "qvalues": local_q,
            "pass": multiplicity_pass,
        }
        audit_admitted = report[
            "shared_join_identity_precision_audit"
        ]["score"]["admitted"]
        report["pass"] = bool(
            report["fresh_confirmation"]["pass"]
            and audit_admitted and multiplicity_pass
        )
        report["verdict"] = "PASS" if report["pass"] else "REFUSED_OR_REFUTED"

    passed = sum(item["pass"] for item in dataset_reports)
    verdict = (
        "H3_B3_GENERAL_PASS" if passed == 2 else
        "H3_B3_DATASET_SPECIFIC_ONLY" if passed == 1 else
        "H3_B3_REFUTED_OR_INCONCLUSIVE"
    )
    report = {
        "schema_version": SCHEMA_VERSION,
        "experiment": "H3 B3 evidence-bound typed K2 composition falsifier",
        "verdict": verdict,
        "claim_allowed": (
            "evidence-bound relational composition retrieval intelligence"
            if verdict == "H3_B3_GENERAL_PASS" else
            "dataset-specific mechanism evidence only" if passed == 1 else "none"
        ),
        "claim_forbidden": [
            "general reasoner", "answer reasoning", "downstream answer uplift",
            "deployable certified composition kernel", "typed arc precision",
        ],
        "preregistered_thresholds": {
            **PRIMARY_THRESHOLDS, "cluster_ci_lower": ">0",
            "apply_coverage": 0.50,
            "depth2_first_gold": "max(10, ceil(5% of test queries))",
            "shared_join_identity_precision": 0.95,
            "shared_join_identity_wilson95_lower": 0.90,
            "largest_component_fraction": 0.25, "max_join_df": 8,
        },
        "artifact_receipts": {
            "run_manifest_path": str(manifest_file),
            "run_manifest_sha256": _file_sha256(manifest_file),
            "protocol_sha256": manifest["protocol"]["sha256"],
            "certificate_transition_path": str(transition_path),
            "certificate_transition_sha256": transition_sha256,
            "fresh_artifact_seal_path": str(fresh_seal_path),
            "fresh_artifact_seal_sha256": fresh_seal_sha256,
            "fresh_stage": artifact_receipt,
            "evaluation_config": config_receipt,
        },
        "datasets": dataset_reports,
    }
    final_path = _phase_path(manifest_file, manifest, "final_report")
    _write_json_once_or_match(final_path, report)
    return report


def run_falsifier(
    *,
    manifest_path: str | Path,
    phase: str,
    config: EvaluationConfigV1 = EvaluationConfigV1(),
    arc_transport: arca.Transport | None = None,
) -> dict[str, Any]:
    """Compatibility entry point with a deliberately path-free API."""

    if phase == "development":
        if arc_transport is not None:
            raise ValueError("development phase cannot accept an arc transport")
        return run_development_phase(manifest_path=manifest_path, config=config)
    if phase == "fresh":
        return run_fresh_phase(
            manifest_path=manifest_path, config=config,
            arc_transport=arc_transport,
        )
    raise ValueError("phase must be exactly 'development' or 'fresh'")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase", choices=("development", "fresh"), required=True,
        help="run one manifest-authorized phase",
    )
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args(argv)
    report = run_falsifier(
        manifest_path=args.manifest,
        phase=args.phase,
    )
    manifest_file = Path(args.manifest).resolve()
    manifest = load_run_manifest(manifest_file)
    output = _phase_path(
        manifest_file, manifest,
        "development_report" if args.phase == "development" else "final_report",
    )
    print(json.dumps({
        "phase": args.phase,
        "status": report.get("status", report.get("verdict")),
        "out": str(output),
        "datasets": [
            {"dataset": item["dataset"], "verdict": item.get("verdict")}
            for item in report.get("datasets", ())
        ],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
