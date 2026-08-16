"""S3 immutable field snapshots for the HSWM readout boundary.

The legacy prototype keeps numpy arrays in mutable ``Hypergraph`` and
``WeightField`` objects.  A certified readout must not bind those live objects:
it binds this content-addressed snapshot instead, verifies the frozen preimage,
and only then hydrates a short-lived field for the existing numerical kernel.

This is a pure module, not a durable engine.  Revision event folding,
concurrent publication, as-of storage, and compensation remain S4 work.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from hashlib import sha256
import math
import marshal
from pathlib import Path
import sys
from typing import Any

import numpy as np

import hypergraph as _hypergraph
from hypergraph import Hypergraph
import weight_field as _weight_field
from weight_field import WeightField, attention_alpha
from world_compiler import verify_world_artifact
from world_ir import WorldArtifactV1, canonical_json, content_id


FIELD_SNAPSHOT_SCHEMA_VERSION = "hswm-field-snapshot/v1"
FIELD_KERNEL_VERSION = "hswm-weight-field-numpy-f64/v1"
FIELD_KERNEL_ABI_VERSION = "hswm-static-field-kernel-abi/v1"
EMPTY_SHA256 = sha256(b"").hexdigest()


class SnapshotRejectCode(StrEnum):
    ARTIFACT_INVALID = "artifact_invalid"
    PROJECTION_MISMATCH = "projection_mismatch"
    LAYOUT_NOT_BIJECTIVE = "layout_not_bijective"
    WORLD_FIELD_MISMATCH = "world_field_mismatch"
    EMBEDDING_MISSING = "embedding_missing"
    EMBEDDING_MODEL_MIXED = "embedding_model_mixed"
    EMBEDDING_DIMENSION_MISMATCH = "embedding_dimension_mismatch"
    NONFINITE_VECTOR = "nonfinite_vector"
    REVISION_TARGET_MISMATCH = "revision_target_mismatch"
    REVISION_CUT_MISMATCH = "revision_cut_mismatch"
    KERNEL_PARAMETER_INVALID = "kernel_parameter_invalid"
    ARRAY_DIGEST_MISMATCH = "array_digest_mismatch"
    MATERIAL_DIGEST_MISMATCH = "material_digest_mismatch"
    SNAPSHOT_ID_MISMATCH = "snapshot_id_mismatch"


@dataclass(frozen=True)
class SnapshotIssueV1:
    code: SnapshotRejectCode
    path: str
    detail: str


@dataclass(frozen=True)
class SnapshotRejectionV1:
    schema_version: str
    issues: tuple[SnapshotIssueV1, ...]


@dataclass(frozen=True)
class FrozenArrayV1:
    """Immutable little-endian array payload.

    ``bytes`` owns the storage, so arrays reconstructed with ``frombuffer`` are
    read-only.  The digest covers dtype, shape, and bytes rather than a JSON
    rendering of floats.
    """

    dtype: str
    shape: tuple[int, ...]
    data: bytes
    sha256: str


@dataclass(frozen=True)
class EmbeddingContractV1:
    producer: str
    model_revision: str
    config_sha256: str
    dimension: int


@dataclass(frozen=True)
class RevisionCutV1:
    cut_id: str
    ledger_id: str
    revision: int
    events_root_sha256: str
    base_salience_by_target: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class FieldKernelSpecV1:
    kernel_version: str = FIELD_KERNEL_VERSION
    semantic_mode: str = "cosine-v1"
    lambda_b: float = 0.15
    bilinear_matrix: FrozenArrayV1 | None = None


@dataclass(frozen=True)
class FieldPolicyV1:
    policy_id: str = "legacy-static-current-v1"
    tie_policy: str = "numpy-stable-dense-order-v1"
    target_projection: str = "paragraph-v1"
    score_dtype: str = "float64"


@dataclass(frozen=True)
class FieldMaterialV1:
    node_embeddings: FrozenArrayV1
    target_embeddings: FrozenArrayV1
    member_offsets: FrozenArrayV1
    member_indices: FrozenArrayV1
    edge_frequency: FrozenArrayV1
    edge_recency: FrozenArrayV1
    base_salience: FrozenArrayV1
    material_sha256: str


@dataclass(frozen=True)
class FieldSnapshotV1:
    snapshot_id: str
    schema_version: str
    artifact: WorldArtifactV1
    entity_ids_by_dense: tuple[str, ...]
    target_ids_by_dense: tuple[str, ...]
    embedding_contract: EmbeddingContractV1
    revision_cut: RevisionCutV1
    kernel: FieldKernelSpecV1
    field_policy: FieldPolicyV1
    topology_sha256: str
    embedding_manifest_sha256: str
    candidate_set_sha256: str
    kernel_sha256: str
    parameter_sha256: str
    policy_sha256: str
    material_sha256: str


@dataclass(frozen=True)
class FieldSnapshotBundleV1:
    snapshot: FieldSnapshotV1
    material: FieldMaterialV1


@dataclass(frozen=True)
class ScoreComponentsV1:
    snapshot_id: str
    query_sha256: str
    candidate_sha256: str
    target_ordinals: tuple[int, ...]
    target_ids: tuple[str, ...]
    cosine: tuple[float, ...]
    semantic_residual: tuple[float, ...]
    temporal_delta: tuple[float, ...]
    traversal_residual: tuple[float, ...]
    final_scores: tuple[float, ...]
    component_sha256: str


class SnapshotHydrationError(ValueError):
    def __init__(self, rejection: SnapshotRejectionV1):
        self.rejection = rejection
        summary = "; ".join(f"{issue.code.value}:{issue.path}" for issue in rejection.issues)
        super().__init__(summary)


def _sha_json(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _callable_sha256(value: Any) -> str:
    code = getattr(value, "__code__", None)
    if code is None:
        raise ValueError(f"kernel callable {value!r} has no Python code object")
    return sha256(marshal.dumps(code)).hexdigest()


def _module_file_sha256(module: Any) -> str:
    path = getattr(module, "__file__", None)
    if not path:
        raise ValueError(f"kernel module {module!r} has no source path")
    return sha256(Path(path).read_bytes()).hexdigest()


def installed_static_kernel_sha256() -> str:
    """Digest the installed numerical ABI, source, and live callables.

    Recomputed during snapshot verification so an in-place source edit or
    monkeypatch invalidates certificates issued for the prior implementation.
    """
    return _sha_json({
        "abi_version": FIELD_KERNEL_ABI_VERSION,
        "snapshot_runtime_file_sha256": _module_file_sha256(sys.modules[__name__]),
        "module_file_sha256": _module_file_sha256(_weight_field),
        "hypergraph_file_sha256": _module_file_sha256(_hypergraph),
        "attention_alpha_sha256": _callable_sha256(_weight_field.attention_alpha),
        "combine_sha256": _callable_sha256(_weight_field.combine),
        "weight_field_value_sha256": _callable_sha256(_weight_field.WeightField.value),
        "numpy_version": np.__version__,
        "python_version": tuple(sys.version_info[:2]),
    })


def _array_digest(dtype: str, shape: tuple[int, ...], data: bytes) -> str:
    header = canonical_json({"dtype": dtype, "shape": shape}).encode("utf-8")
    h = sha256()
    h.update(len(header).to_bytes(8, "little"))
    h.update(header)
    h.update(data)
    return h.hexdigest()


def freeze_array(value: Any, dtype: str) -> FrozenArrayV1:
    if dtype not in {"<f8", "<i8"}:
        raise ValueError(f"unsupported frozen dtype {dtype!r}")
    array = np.ascontiguousarray(np.asarray(value, dtype=np.dtype(dtype)))
    if dtype == "<f8" and not np.isfinite(array).all():
        raise ValueError("frozen float array must be finite")
    data = array.tobytes(order="C")
    shape = tuple(int(x) for x in array.shape)
    return FrozenArrayV1(
        dtype=dtype,
        shape=shape,
        data=data,
        sha256=_array_digest(dtype, shape, data),
    )


def thaw_array(value: FrozenArrayV1) -> np.ndarray:
    array = np.frombuffer(value.data, dtype=np.dtype(value.dtype))
    return array.reshape(value.shape)


def _array_issues(value: FrozenArrayV1, path: str) -> list[SnapshotIssueV1]:
    issues: list[SnapshotIssueV1] = []
    if value.dtype not in {"<f8", "<i8"}:
        return [SnapshotIssueV1(
            SnapshotRejectCode.ARRAY_DIGEST_MISMATCH, path,
            f"unsupported frozen dtype {value.dtype!r}",
        )]
    if any(not isinstance(size, int) or size < 0 for size in value.shape):
        return [SnapshotIssueV1(
            SnapshotRejectCode.ARRAY_DIGEST_MISMATCH, path,
            "array shape must contain non-negative integers",
        )]
    count = math.prod(value.shape)
    if count * np.dtype(value.dtype).itemsize != len(value.data):
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.ARRAY_DIGEST_MISMATCH, path,
            "shape and byte length disagree",
        ))
        return issues
    expected = _array_digest(value.dtype, value.shape, value.data)
    if value.sha256 != expected:
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.ARRAY_DIGEST_MISMATCH, path,
            f"array digest {value.sha256} != {expected}",
        ))
    if value.dtype == "<f8" and not np.isfinite(thaw_array(value)).all():
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.NONFINITE_VECTOR, path,
            "frozen array contains NaN or infinity",
        ))
    return issues


def _material_payload(material: FieldMaterialV1) -> dict[str, str]:
    return {
        "node_embeddings": material.node_embeddings.sha256,
        "target_embeddings": material.target_embeddings.sha256,
        "member_offsets": material.member_offsets.sha256,
        "member_indices": material.member_indices.sha256,
        "edge_frequency": material.edge_frequency.sha256,
        "edge_recency": material.edge_recency.sha256,
        "base_salience": material.base_salience.sha256,
    }


def field_material_sha256(material: FieldMaterialV1) -> str:
    return _sha_json(_material_payload(material))


def make_revision_cut(
    target_ids: tuple[str, ...],
    base_salience: np.ndarray | tuple[float, ...],
    *,
    ledger_id: str = "legacy-positional-ledger",
    revision: int = 0,
    events_root_sha256: str = EMPTY_SHA256,
) -> RevisionCutV1:
    values = np.asarray(base_salience, dtype=np.float64)
    if values.shape != (len(target_ids),):
        raise ValueError("revision cut must contain exactly one salience per target")
    if not np.isfinite(values).all() or (values <= 0).any() or (values > 1).any():
        raise ValueError("revision salience must be finite and in (0, 1]")
    if revision < 0:
        raise ValueError("revision must be >= 0")
    pairs = tuple((target_id, float(value)) for target_id, value in zip(target_ids, values))
    payload = {
        "ledger_id": ledger_id,
        "revision": revision,
        "events_root_sha256": events_root_sha256,
        "base_salience_by_target": pairs,
    }
    return RevisionCutV1(
        cut_id=content_id("revision_cut", payload),
        ledger_id=ledger_id,
        revision=revision,
        events_root_sha256=events_root_sha256,
        base_salience_by_target=pairs,
    )


def _revision_cut_id(cut: RevisionCutV1) -> str:
    return content_id("revision_cut", {
        "ledger_id": cut.ledger_id,
        "revision": cut.revision,
        "events_root_sha256": cut.events_root_sha256,
        "base_salience_by_target": cut.base_salience_by_target,
    })


def _kernel_payload(kernel: FieldKernelSpecV1) -> dict[str, Any]:
    return {
        "kernel_version": kernel.kernel_version,
        "semantic_mode": kernel.semantic_mode,
        "lambda_b": kernel.lambda_b,
        "bilinear_matrix_sha256": (
            None if kernel.bilinear_matrix is None else kernel.bilinear_matrix.sha256
        ),
    }


def _kernel_sha256(kernel: FieldKernelSpecV1) -> str:
    return _sha_json({
        "kernel_version": kernel.kernel_version,
        "installed_kernel_sha256": installed_static_kernel_sha256(),
        "operations": "attention_alpha-then-combine-v1",
        "score_dtype": "float64",
        "semantic_mode": kernel.semantic_mode,
    })


def _parameter_sha256(kernel: FieldKernelSpecV1) -> str:
    return _sha_json({
        "lambda_b": kernel.lambda_b,
        "bilinear_matrix_sha256": (
            None if kernel.bilinear_matrix is None else kernel.bilinear_matrix.sha256
        ),
    })


def _policy_sha256(policy: FieldPolicyV1, parameter_sha256: str) -> str:
    return _sha_json({"field_policy": policy, "parameter_sha256": parameter_sha256})


def _snapshot_payload(snapshot: FieldSnapshotV1) -> dict[str, Any]:
    return {
        "schema_version": snapshot.schema_version,
        "world_build_id": snapshot.artifact.build_id,
        "entity_ids_by_dense": snapshot.entity_ids_by_dense,
        "target_ids_by_dense": snapshot.target_ids_by_dense,
        "embedding_contract": snapshot.embedding_contract,
        "revision_cut": snapshot.revision_cut,
        "kernel": _kernel_payload(snapshot.kernel),
        "field_policy": snapshot.field_policy,
        "topology_sha256": snapshot.topology_sha256,
        "embedding_manifest_sha256": snapshot.embedding_manifest_sha256,
        "candidate_set_sha256": snapshot.candidate_set_sha256,
        "kernel_sha256": snapshot.kernel_sha256,
        "parameter_sha256": snapshot.parameter_sha256,
        "policy_sha256": snapshot.policy_sha256,
        "material_sha256": snapshot.material_sha256,
    }


def _snapshot_id(snapshot: FieldSnapshotV1) -> str:
    return content_id("field_snapshot", _snapshot_payload(snapshot))


def _embedding_contract(artifact: WorldArtifactV1) -> EmbeddingContractV1 | None:
    contracts = {
        (
            observation.producer,
            observation.model_revision,
            observation.config_sha256,
            len(observation.vector),
        )
        for observation in artifact.embedding_observations
    }
    if len(contracts) != 1:
        return None
    producer, model_revision, config_sha256, dimension = next(iter(contracts))
    return EmbeddingContractV1(producer, model_revision, config_sha256, dimension)


def _embedding_manifest_sha256(artifact: WorldArtifactV1) -> str:
    return _sha_json(tuple(
        (
            observation.observation_id,
            observation.target_kind,
            observation.target_id,
            observation.producer,
            observation.model_revision,
            observation.config_sha256,
            observation.input_sha256,
            observation.output_sha256,
        )
        for observation in sorted(
            artifact.embedding_observations, key=lambda value: value.observation_id
        )
    ))


def _members_from_material(material: FieldMaterialV1) -> tuple[np.ndarray, ...]:
    offsets = thaw_array(material.member_offsets)
    indices = thaw_array(material.member_indices)
    return tuple(indices[int(offsets[i]):int(offsets[i + 1])] for i in range(len(offsets) - 1))


def _topology_sha256(
    target_ids: tuple[str, ...],
    entity_ids: tuple[str, ...],
    members: tuple[np.ndarray, ...] | list[np.ndarray],
) -> str:
    topology = tuple(
        (
            target_id,
            tuple(entity_ids[int(index)] for index in member),
        )
        for target_id, member in zip(target_ids, members)
    )
    return _sha_json(topology)


def _material_from_world(world: Any) -> FieldMaterialV1:
    hg = world.hg
    target_embeddings = np.asarray(getattr(hg, "unit_emb"), dtype=np.float64)
    offsets = np.zeros(hg.M + 1, dtype=np.int64)
    if hg.M:
        offsets[1:] = np.cumsum([len(member) for member in hg.members])
    indices = np.concatenate(hg.members) if hg.M else np.empty(0, dtype=np.int64)
    arrays = {
        "node_embeddings": freeze_array(hg.node_emb, "<f8"),
        "target_embeddings": freeze_array(target_embeddings, "<f8"),
        "member_offsets": freeze_array(offsets, "<i8"),
        "member_indices": freeze_array(indices, "<i8"),
        "edge_frequency": freeze_array(hg.edge_freq, "<f8"),
        "edge_recency": freeze_array(hg.edge_recency, "<f8"),
        "base_salience": freeze_array(hg.base_salience, "<f8"),
    }
    provisional = FieldMaterialV1(**arrays, material_sha256="")
    return FieldMaterialV1(**arrays, material_sha256=field_material_sha256(provisional))


def _binding_issues(
    snapshot: FieldSnapshotV1,
    material: FieldMaterialV1,
) -> list[SnapshotIssueV1]:
    issues: list[SnapshotIssueV1] = []
    artifact = snapshot.artifact
    entity_ids = snapshot.entity_ids_by_dense
    target_ids = snapshot.target_ids_by_dense
    if len(entity_ids) != len(set(entity_ids)) or set(entity_ids) != {
        entity.entity_id for entity in artifact.entities
    }:
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.LAYOUT_NOT_BIJECTIVE, "entity_ids_by_dense",
            "dense entity IDs are not a bijection over artifact entities",
        ))
    if len(target_ids) != len(set(target_ids)) or set(target_ids) != {
        target.target_id for target in artifact.field_targets
    }:
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.LAYOUT_NOT_BIJECTIVE, "target_ids_by_dense",
            "dense target IDs are not a bijection over artifact field targets",
        ))
    if issues:
        return issues

    nodes = thaw_array(material.node_embeddings)
    targets = thaw_array(material.target_embeddings)
    if nodes.ndim != 2 or targets.ndim != 2 or nodes.shape[0] != len(entity_ids) or targets.shape[0] != len(target_ids):
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.EMBEDDING_DIMENSION_MISMATCH, "material.embeddings",
            "embedding rows do not match the dense stable-ID layouts",
        ))
        return issues
    if nodes.shape[1] != snapshot.embedding_contract.dimension or targets.shape[1] != snapshot.embedding_contract.dimension:
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.EMBEDDING_DIMENSION_MISMATCH, "embedding_contract.dimension",
            "material dimension does not match the embedding contract",
        ))

    observation_by_target = {
        observation.target_id: observation
        for observation in artifact.embedding_observations
    }
    for row, stable_id in enumerate(entity_ids):
        observation = observation_by_target.get(stable_id)
        if observation is None or not np.array_equal(nodes[row], np.asarray(observation.vector, dtype=np.float64)):
            issues.append(SnapshotIssueV1(
                SnapshotRejectCode.WORLD_FIELD_MISMATCH, "material.node_embeddings",
                f"entity row {row} is not the artifact embedding for {stable_id}",
            ))
            break
    for row, stable_id in enumerate(target_ids):
        observation = observation_by_target.get(stable_id)
        if observation is None or not np.array_equal(targets[row], np.asarray(observation.vector, dtype=np.float64)):
            issues.append(SnapshotIssueV1(
                SnapshotRejectCode.WORLD_FIELD_MISMATCH, "material.target_embeddings",
                f"target row {row} is not the artifact embedding for {stable_id}",
            ))
            break

    entity_dense = {stable_id: index for index, stable_id in enumerate(entity_ids)}
    target_by_id = {target.target_id: target for target in artifact.field_targets}
    members = _members_from_material(material)
    if len(members) != len(target_ids):
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.WORLD_FIELD_MISMATCH, "material.members",
            "incidence edge count does not match target layout",
        ))
    else:
        for row, (stable_id, member) in enumerate(zip(target_ids, members)):
            expected = tuple(sorted(
                entity_dense[entity_id]
                for entity_id in target_by_id[stable_id].member_entity_ids
            ))
            actual = tuple(int(index) for index in member)
            if actual != expected:
                issues.append(SnapshotIssueV1(
                    SnapshotRejectCode.WORLD_FIELD_MISMATCH, "material.members",
                    f"incidence row {row} does not match artifact target {stable_id}",
                ))
                break
    return issues


def freeze_legacy_field_snapshot(
    artifact: WorldArtifactV1,
    world: Any,
    stable_ids: Any,
    *,
    revision: int = 0,
    ledger_id: str = "legacy-positional-ledger",
    events_root_sha256: str = EMPTY_SHA256,
    M: np.ndarray | None = None,
    lam: float = 0.15,
    field_policy: FieldPolicyV1 | None = None,
) -> FieldSnapshotBundleV1 | SnapshotRejectionV1:
    """Freeze a verified S2 legacy projection into an immutable S3 snapshot."""
    issues: list[SnapshotIssueV1] = []
    artifact_issues = verify_world_artifact(artifact)
    if artifact_issues:
        issues.extend(SnapshotIssueV1(
            SnapshotRejectCode.ARTIFACT_INVALID,
            f"artifact.{issue.path}", issue.detail,
        ) for issue in artifact_issues)
    policy = field_policy or FieldPolicyV1(target_projection=artifact.manifest.projection)
    if policy.target_projection != artifact.manifest.projection:
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.PROJECTION_MISMATCH, "field_policy.target_projection",
            f"{policy.target_projection!r} != {artifact.manifest.projection!r}",
        ))
    entity_ids = tuple(stable_ids.entity_ids_by_dense)
    target_ids = tuple(stable_ids.target_ids_by_dense)
    contract = _embedding_contract(artifact)
    if contract is None:
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.EMBEDDING_MODEL_MIXED, "artifact.embedding_observations",
            "snapshot requires one producer/model/config/dimension contract",
        ))
    try:
        material = _material_from_world(world)
    except (AttributeError, TypeError, ValueError) as exc:
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.EMBEDDING_MISSING, "world.hg.unit_emb", str(exc),
        ))
        material = None

    matrix: FrozenArrayV1 | None = None
    if not math.isfinite(float(lam)) or float(lam) < 0:
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.KERNEL_PARAMETER_INVALID, "kernel.lambda_b",
            "lambda_b must be finite and >= 0",
        ))
    if M is not None:
        try:
            raw_matrix = np.asarray(M, dtype=np.float64)
            if contract is not None and raw_matrix.shape != (contract.dimension, contract.dimension):
                raise ValueError(
                    f"M shape {raw_matrix.shape} != ({contract.dimension}, {contract.dimension})"
                )
            matrix = freeze_array(raw_matrix, "<f8")
        except (TypeError, ValueError) as exc:
            issues.append(SnapshotIssueV1(
                SnapshotRejectCode.KERNEL_PARAMETER_INVALID, "kernel.bilinear_matrix", str(exc),
            ))
    if issues or material is None or contract is None:
        return _reject(issues)

    kernel = FieldKernelSpecV1(
        semantic_mode="cosine-v1" if matrix is None else "bilinear-v1",
        lambda_b=float(lam),
        bilinear_matrix=matrix,
    )
    try:
        revision_cut = make_revision_cut(
            target_ids, thaw_array(material.base_salience),
            ledger_id=ledger_id, revision=revision,
            events_root_sha256=events_root_sha256,
        )
    except ValueError as exc:
        return _reject([SnapshotIssueV1(
            SnapshotRejectCode.REVISION_CUT_MISMATCH, "revision_cut", str(exc),
        )])
    topology_sha = _topology_sha256(target_ids, entity_ids, _members_from_material(material))
    embedding_manifest_sha = _embedding_manifest_sha256(artifact)
    candidate_sha = _sha_json(target_ids)
    kernel_sha = _kernel_sha256(kernel)
    parameter_sha = _parameter_sha256(kernel)
    policy_sha = _policy_sha256(policy, parameter_sha)
    provisional = FieldSnapshotV1(
        snapshot_id="",
        schema_version=FIELD_SNAPSHOT_SCHEMA_VERSION,
        artifact=artifact,
        entity_ids_by_dense=entity_ids,
        target_ids_by_dense=target_ids,
        embedding_contract=contract,
        revision_cut=revision_cut,
        kernel=kernel,
        field_policy=policy,
        topology_sha256=topology_sha,
        embedding_manifest_sha256=embedding_manifest_sha,
        candidate_set_sha256=candidate_sha,
        kernel_sha256=kernel_sha,
        parameter_sha256=parameter_sha,
        policy_sha256=policy_sha,
        material_sha256=material.material_sha256,
    )
    snapshot = replace(provisional, snapshot_id=_snapshot_id(provisional))
    bundle = FieldSnapshotBundleV1(snapshot=snapshot, material=material)
    verified = verify_field_snapshot(bundle)
    if verified:
        return _reject(list(verified))
    return bundle


def _reject(issues: list[SnapshotIssueV1]) -> SnapshotRejectionV1:
    ordered = tuple(sorted(issues, key=lambda issue: (issue.code.value, issue.path, issue.detail)))
    return SnapshotRejectionV1(FIELD_SNAPSHOT_SCHEMA_VERSION, ordered)


def verify_field_snapshot(bundle: FieldSnapshotBundleV1) -> tuple[SnapshotIssueV1, ...]:
    snapshot, material = bundle.snapshot, bundle.material
    issues: list[SnapshotIssueV1] = []
    if snapshot.schema_version != FIELD_SNAPSHOT_SCHEMA_VERSION:
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.SNAPSHOT_ID_MISMATCH, "snapshot.schema_version",
            f"unsupported schema {snapshot.schema_version!r}",
        ))
    for name in (
        "node_embeddings", "target_embeddings", "member_offsets", "member_indices",
        "edge_frequency", "edge_recency", "base_salience",
    ):
        issues.extend(_array_issues(getattr(material, name), f"material.{name}"))
    if snapshot.kernel.bilinear_matrix is not None:
        issues.extend(_array_issues(snapshot.kernel.bilinear_matrix, "kernel.bilinear_matrix"))

    expected_array_contracts = {
        "node_embeddings": ("<f8", 2),
        "target_embeddings": ("<f8", 2),
        "member_offsets": ("<i8", 1),
        "member_indices": ("<i8", 1),
        "edge_frequency": ("<f8", 1),
        "edge_recency": ("<f8", 1),
        "base_salience": ("<f8", 1),
    }
    for name, (dtype, rank) in expected_array_contracts.items():
        value = getattr(material, name)
        if value.dtype != dtype or len(value.shape) != rank:
            issues.append(SnapshotIssueV1(
                SnapshotRejectCode.ARRAY_DIGEST_MISMATCH, f"material.{name}",
                f"expected dtype {dtype} and rank {rank}",
            ))

    expected_material_sha = field_material_sha256(material)
    if material.material_sha256 != expected_material_sha or snapshot.material_sha256 != expected_material_sha:
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.MATERIAL_DIGEST_MISMATCH, "material.material_sha256",
            "material wrapper or snapshot does not bind the frozen arrays",
        ))

    artifact_issues = verify_world_artifact(snapshot.artifact)
    issues.extend(SnapshotIssueV1(
        SnapshotRejectCode.ARTIFACT_INVALID, f"artifact.{issue.path}", issue.detail,
    ) for issue in artifact_issues)
    contract = _embedding_contract(snapshot.artifact)
    if contract is None or contract != snapshot.embedding_contract:
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.EMBEDDING_MODEL_MIXED, "embedding_contract",
            "snapshot embedding contract differs from artifact observations",
        ))
    arrays_valid = not any(
        issue.code in {
            SnapshotRejectCode.ARRAY_DIGEST_MISMATCH,
            SnapshotRejectCode.NONFINITE_VECTOR,
        }
        for issue in issues
    )
    if arrays_valid:
        try:
            issues.extend(_binding_issues(snapshot, material))
        except (IndexError, TypeError, ValueError) as exc:
            issues.append(SnapshotIssueV1(
                SnapshotRejectCode.WORLD_FIELD_MISMATCH, "material",
                f"malformed frozen field material: {exc}",
            ))

    target_ids = snapshot.target_ids_by_dense
    cut = snapshot.revision_cut
    if (
        isinstance(cut.revision, bool)
        or not isinstance(cut.revision, int)
        or cut.revision < 0
        or not isinstance(cut.ledger_id, str)
        or not cut.ledger_id
        or not _is_sha256(cut.events_root_sha256)
    ):
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.REVISION_CUT_MISMATCH, "revision_cut",
            "revision must be a non-negative integer with ledger ID and SHA-256 event root",
        ))
    try:
        expected_cut_id = _revision_cut_id(cut)
    except (TypeError, ValueError) as exc:
        expected_cut_id = ""
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.REVISION_CUT_MISMATCH, "revision_cut",
            f"revision cut is not canonical: {exc}",
        ))
    if cut.cut_id != expected_cut_id:
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.REVISION_CUT_MISMATCH, "revision_cut.cut_id",
            "revision cut ID does not match its frozen preimage",
        ))
    cut_ids = tuple(target_id for target_id, _ in cut.base_salience_by_target)
    cut_values = np.asarray([value for _, value in cut.base_salience_by_target], dtype=np.float64)
    material_values = thaw_array(material.base_salience) if arrays_valid else np.empty(0)
    if (
        cut_ids != target_ids
        or not np.isfinite(cut_values).all()
        or (cut_values <= 0).any()
        or (cut_values > 1).any()
        or not np.array_equal(cut_values, material_values)
    ):
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.REVISION_TARGET_MISMATCH, "revision_cut.base_salience_by_target",
            "revision cut and frozen salience vector are not bit-identical",
        ))

    if arrays_valid:
        try:
            members = _members_from_material(material)
            expected_topology = _topology_sha256(
                snapshot.target_ids_by_dense, snapshot.entity_ids_by_dense, members,
            )
        except (IndexError, TypeError, ValueError) as exc:
            issues.append(SnapshotIssueV1(
                SnapshotRejectCode.WORLD_FIELD_MISMATCH, "material.members",
                f"cannot reconstruct topology: {exc}",
            ))
        else:
            if snapshot.topology_sha256 != expected_topology:
                issues.append(SnapshotIssueV1(
                    SnapshotRejectCode.SNAPSHOT_ID_MISMATCH, "snapshot.topology_sha256",
                    "topology digest does not match frozen incidence",
                ))
    if snapshot.embedding_manifest_sha256 != _embedding_manifest_sha256(snapshot.artifact):
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.SNAPSHOT_ID_MISMATCH, "snapshot.embedding_manifest_sha256",
            "embedding manifest digest does not match the artifact",
        ))
    if snapshot.candidate_set_sha256 != _sha_json(snapshot.target_ids_by_dense):
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.SNAPSHOT_ID_MISMATCH, "snapshot.candidate_set_sha256",
            "candidate digest does not match dense target order",
        ))
    if snapshot.kernel.kernel_version != FIELD_KERNEL_VERSION or snapshot.kernel.semantic_mode not in {
        "cosine-v1", "bilinear-v1",
    }:
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.KERNEL_PARAMETER_INVALID, "snapshot.kernel",
            "unsupported kernel version or semantic mode",
        ))
    matrix = snapshot.kernel.bilinear_matrix
    if matrix is not None and (
        matrix.dtype != "<f8"
        or matrix.shape != (
            snapshot.embedding_contract.dimension,
            snapshot.embedding_contract.dimension,
        )
    ):
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.KERNEL_PARAMETER_INVALID, "snapshot.kernel.bilinear_matrix",
            "bilinear matrix must be little-endian float64 with shape (dimension, dimension)",
        ))
    expected_field_policy = FieldPolicyV1(
        target_projection=snapshot.artifact.manifest.projection,
    )
    if snapshot.field_policy != expected_field_policy:
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.KERNEL_PARAMETER_INVALID, "snapshot.field_policy",
            "field policy is unsupported by the installed S3 kernel",
        ))
    if (
        not math.isfinite(snapshot.kernel.lambda_b)
        or snapshot.kernel.lambda_b < 0
        or (snapshot.kernel.semantic_mode == "cosine-v1") != (snapshot.kernel.bilinear_matrix is None)
    ):
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.KERNEL_PARAMETER_INVALID, "snapshot.kernel",
            "kernel mode, matrix, or lambda_b is inconsistent",
        ))
    try:
        expected_kernel = _kernel_sha256(snapshot.kernel)
    except (OSError, TypeError, ValueError) as exc:
        expected_kernel = ""
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.KERNEL_PARAMETER_INVALID, "snapshot.kernel.implementation",
            f"installed kernel cannot be bound: {exc}",
        ))
    expected_parameter = _parameter_sha256(snapshot.kernel)
    expected_policy = _policy_sha256(snapshot.field_policy, expected_parameter)
    if snapshot.kernel_sha256 != expected_kernel:
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.SNAPSHOT_ID_MISMATCH, "snapshot.kernel_sha256",
            "kernel digest mismatch",
        ))
    if snapshot.parameter_sha256 != expected_parameter:
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.SNAPSHOT_ID_MISMATCH, "snapshot.parameter_sha256",
            "parameter digest mismatch",
        ))
    if snapshot.policy_sha256 != expected_policy:
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.SNAPSHOT_ID_MISMATCH, "snapshot.policy_sha256",
            "field policy digest mismatch",
        ))
    try:
        expected_snapshot_id = _snapshot_id(snapshot)
    except (TypeError, ValueError) as exc:
        expected_snapshot_id = ""
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.SNAPSHOT_ID_MISMATCH, "snapshot",
            f"snapshot is not canonical: {exc}",
        ))
    if snapshot.snapshot_id != expected_snapshot_id:
        issues.append(SnapshotIssueV1(
            SnapshotRejectCode.SNAPSHOT_ID_MISMATCH, "snapshot.snapshot_id",
            f"snapshot ID {snapshot.snapshot_id} != {expected_snapshot_id}",
        ))
    return tuple(sorted(issues, key=lambda issue: (issue.code.value, issue.path, issue.detail)))


def hydrate_weight_field(
    bundle: FieldSnapshotBundleV1,
    *,
    verify: bool = True,
) -> WeightField:
    """Hydrate a short-lived legacy field; no mutable object is stored in the snapshot."""
    if verify:
        issues = verify_field_snapshot(bundle)
        if issues:
            raise SnapshotHydrationError(_reject(list(issues)))
    material = bundle.material
    nodes = thaw_array(material.node_embeddings)
    targets = thaw_array(material.target_embeddings)
    members = list(_members_from_material(material))
    hg = Hypergraph(
        node_emb=nodes,
        members=members,
        edge_freq=thaw_array(material.edge_frequency),
        edge_recency=thaw_array(material.edge_recency),
        base_salience=thaw_array(material.base_salience),
    )
    hg.unit_emb = targets  # type: ignore[attr-defined]
    matrix = (
        None if bundle.snapshot.kernel.bilinear_matrix is None
        else thaw_array(bundle.snapshot.kernel.bilinear_matrix)
    )
    return WeightField(
        hg,
        M=matrix,
        lam=bundle.snapshot.kernel.lambda_b,
        target_emb=targets,
    )


def _query_sha256(query: np.ndarray) -> str:
    frozen = freeze_array(np.asarray(query, dtype=np.float64), "<f8")
    return frozen.sha256


def _component_sha256(
    snapshot_id: str,
    query_sha256: str,
    target_ids: tuple[str, ...],
    arrays: tuple[np.ndarray, ...],
) -> str:
    payload = {
        "snapshot_id": snapshot_id,
        "query_sha256": query_sha256,
        "target_ids": target_ids,
        "array_sha256": tuple(freeze_array(array, "<f8").sha256 for array in arrays),
    }
    return _sha_json(payload)


def score_components(
    bundle: FieldSnapshotBundleV1,
    query_embedding: np.ndarray | tuple[float, ...],
    *,
    target_ordinals: tuple[int, ...] | None = None,
    verify: bool = True,
) -> ScoreComponentsV1:
    """Return an auditable component vector in the existing kernel's exact order."""
    if verify:
        issues = verify_field_snapshot(bundle)
        if issues:
            raise SnapshotHydrationError(_reject(list(issues)))
    query = np.asarray(query_embedding, dtype=np.float64)
    dimension = bundle.snapshot.embedding_contract.dimension
    if query.shape != (dimension,) or not np.isfinite(query).all():
        raise ValueError(f"query embedding must be finite shape ({dimension},)")
    targets = thaw_array(bundle.material.target_embeddings)
    base = thaw_array(bundle.material.base_salience)
    ordinals = (
        tuple(range(len(bundle.snapshot.target_ids_by_dense)))
        if target_ordinals is None else tuple(int(value) for value in target_ordinals)
    )
    if len(set(ordinals)) != len(ordinals) or any(
        value < 0 or value >= len(bundle.snapshot.target_ids_by_dense) for value in ordinals
    ):
        raise ValueError("target ordinals must be a unique in-range sequence")
    edges = np.asarray(ordinals, dtype=np.int64)
    cosine = attention_alpha(targets[edges], query, M=None)
    matrix = (
        None if bundle.snapshot.kernel.bilinear_matrix is None
        else thaw_array(bundle.snapshot.kernel.bilinear_matrix)
    )
    semantic = attention_alpha(targets[edges], query, M=matrix)
    semantic_residual = semantic - cosine
    temporal_delta = bundle.snapshot.kernel.lambda_b * np.log(
        np.clip(base[edges], 1e-6, None)
    )
    traversal_residual = np.zeros_like(cosine)
    final = semantic + temporal_delta
    target_ids = tuple(bundle.snapshot.target_ids_by_dense[value] for value in ordinals)
    query_sha = _query_sha256(query)
    candidate_sha = _sha_json(target_ids)
    component_sha = _component_sha256(
        bundle.snapshot.snapshot_id,
        query_sha,
        target_ids,
        (cosine, semantic_residual, temporal_delta, traversal_residual, final),
    )
    return ScoreComponentsV1(
        snapshot_id=bundle.snapshot.snapshot_id,
        query_sha256=query_sha,
        candidate_sha256=candidate_sha,
        target_ordinals=ordinals,
        target_ids=target_ids,
        cosine=tuple(float(value) for value in cosine),
        semantic_residual=tuple(float(value) for value in semantic_residual),
        temporal_delta=tuple(float(value) for value in temporal_delta),
        traversal_residual=tuple(float(value) for value in traversal_residual),
        final_scores=tuple(float(value) for value in final),
        component_sha256=component_sha,
    )


def attach_traversal_scores(
    components: ScoreComponentsV1,
    final_scores_by_ordinal: np.ndarray | tuple[float, ...],
) -> ScoreComponentsV1:
    """Bind an executed traversal's full score vector into its components."""
    final = np.asarray(final_scores_by_ordinal, dtype=np.float64)
    if final.shape != (len(components.target_ordinals),) or not np.isfinite(final).all():
        raise ValueError("traversal final scores must be one finite value per component target")
    static = (
        np.asarray(components.cosine, dtype=np.float64)
        + np.asarray(components.semantic_residual, dtype=np.float64)
        + np.asarray(components.temporal_delta, dtype=np.float64)
    )
    residual = final - static
    arrays = (
        np.asarray(components.cosine, dtype=np.float64),
        np.asarray(components.semantic_residual, dtype=np.float64),
        np.asarray(components.temporal_delta, dtype=np.float64),
        residual,
        final,
    )
    return replace(
        components,
        traversal_residual=tuple(float(value) for value in residual),
        final_scores=tuple(float(value) for value in final),
        component_sha256=_component_sha256(
            components.snapshot_id,
            components.query_sha256,
            components.target_ids,
            arrays,
        ),
    )
