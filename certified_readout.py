"""S3 certified field/readout admission for immutable HSWM snapshots.

The certificate is deliberately an exact scope/admission receipt, not a claim
of statistical or cryptographic proof.  A read is admitted only when world,
snapshot, embedding contract, revision cut, field parameters, and readout
policy all match.  Integrity failures refuse before hydrating the numerical
kernel.  A traversal explicitly certified OFF may use the same snapshot's
static floor; it may not silently switch worlds or revisions.
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

import field_snapshot as fs
import readouts
import traversal
from world_ir import canonical_json, content_id


CERTIFICATE_SCHEMA_VERSION = "hswm-readout-certificate/v1"
READOUT_POLICY_SCHEMA_VERSION = "hswm-readout-policy/v1"
READOUT_KERNEL_ABI_VERSION = "hswm-certified-readout-kernel-abi/v1"
TRAVERSAL_KERNEL_ABI_VERSION = "hswm-traversal-kernel-abi/v1"
_KERNEL_INVOCATION_COUNT = 0


class CertificateStatus(StrEnum):
    CERTIFIED = "certified"
    OFF = "off"
    REVOKED = "revoked"
    BROKEN = "broken"


class ReadoutKind(StrEnum):
    RETRIEVE = "retrieve"
    SELECTION = "selection"
    DISPATCH = "dispatch"
    TRAVERSAL = "traversal"


class ReadoutAction(StrEnum):
    APPLY = "apply"
    FALLBACK_CURRENT_STATIC = "fallback_current_static"
    REFUSE = "refuse"


class RefusalCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    INVALID_CERTIFICATE = "invalid_certificate"
    CERTIFICATE_EXPIRED = "certificate_expired"
    SNAPSHOT_BROKEN = "snapshot_broken"
    WORLD_FIELD_MISMATCH = "world_field_mismatch"
    FIELD_SNAPSHOT_MISMATCH = "field_snapshot_mismatch"
    MODEL_PRODUCER_MISMATCH = "model_producer_mismatch"
    MODEL_REVISION_MISMATCH = "model_revision_mismatch"
    MODEL_CONFIG_MISMATCH = "model_config_mismatch"
    EMBEDDING_DIMENSION_MISMATCH = "embedding_dimension_mismatch"
    FIELD_POLICY_MISMATCH = "field_policy_mismatch"
    REVISION_CUT_MISMATCH = "revision_cut_mismatch"
    REVISION_FOLD_MISMATCH = "revision_fold_mismatch"
    READOUT_POLICY_MISMATCH = "readout_policy_mismatch"
    KERNEL_MISMATCH = "kernel_mismatch"


class ProbeDisposition(StrEnum):
    NOT_DEPLOYABLE = "not_deployable"


class KernelBindingError(ValueError):
    pass


@dataclass(frozen=True)
class TraversalPolicyV1:
    mu: float
    gamma: float = traversal.GAMMA
    hops: int = traversal.K_DEFAULT
    kappa: int = 1
    tau_seed: float = traversal.TAU_SEED
    seed_m: int = traversal.SEED_M
    prune_m: int = traversal.PRUNE_M
    entropy_blowup: float = traversal.ENTROPY_BLOWUP
    neff_min: float = traversal.NEFF_MIN
    neff_topk: int = traversal.NEFF_TOPK
    kept_mass_min: float = traversal.KEPT_MASS_ABSTAIN
    kernel_sha256: str = ""


@dataclass(frozen=True)
class ReadoutPolicyV1:
    policy_id: str
    schema_version: str
    kind: ReadoutKind
    top_k: int
    selection_temperature: float
    traversal: TraversalPolicyV1 | None
    kernel_sha256: str


@dataclass(frozen=True)
class CertificationScopeV1:
    world_build_id: str
    snapshot_id: str
    embedding_producer: str
    model_revision: str
    model_config_sha256: str
    embedding_dimension: int
    revision_cut_id: str
    kernel_sha256: str
    parameter_sha256: str
    field_policy_sha256: str
    candidate_set_sha256: str
    readout_policy_id: str


@dataclass(frozen=True)
class ReadoutCertificateV1:
    certificate_id: str
    schema_version: str
    status: CertificateStatus
    issuer_id: str
    scope: CertificationScopeV1
    evidence_sha256: str
    valid_from_generation: int
    valid_through_generation: int


@dataclass(frozen=True)
class QueryEmbeddingV1:
    query_id: str
    input_sha256: str
    producer: str
    model_revision: str
    config_sha256: str
    dimension: int
    vector: tuple[float, ...]
    output_sha256: str


@dataclass(frozen=True)
class ReadoutRequestV1:
    request_id: str
    certificate_id: str
    expected_world_build_id: str
    expected_snapshot_id: str
    expected_revision_cut_id: str
    query: QueryEmbeddingV1
    policy: ReadoutPolicyV1


@dataclass(frozen=True)
class AdmissionContextV1:
    trusted_certificate_ids: tuple[str, ...]
    current_generation: int


@dataclass(frozen=True)
class TraversalReceiptV1:
    abstained: bool
    abstain_reason: str | None
    mu: float
    gamma: float
    hops: int
    kappa: int
    n_eff: float | None
    kept_mass: tuple[float, ...]
    paths: tuple[tuple[int, int, int, int, float], ...]
    contraction_log: tuple[float, ...]


@dataclass(frozen=True)
class ReadoutPayloadV1:
    kind: ReadoutKind
    target_ordinals: tuple[int, ...]
    target_ids: tuple[str, ...]
    scores: tuple[float, ...]
    probabilities: tuple[float, ...]
    dispatch_target_ordinal: int | None
    dispatch_target_id: str | None
    traversal_receipt: TraversalReceiptV1 | None
    score_components: fs.ScoreComponentsV1
    payload_sha256: str


@dataclass(frozen=True)
class ReadoutReceiptV1:
    receipt_id: str
    request_id: str
    certificate_id: str
    snapshot_id: str
    action: ReadoutAction
    refusal_code: RefusalCode | None
    detail: str
    kernel_invoked: bool
    payload_sha256: str | None


@dataclass(frozen=True)
class CertifiedReadoutResultV1:
    payload: ReadoutPayloadV1 | None
    receipt: ReadoutReceiptV1


@dataclass(frozen=True)
class ProbeResultV1:
    probe_id: str
    disposition: ProbeDisposition
    warning: str
    observed_action: ReadoutAction
    payload: ReadoutPayloadV1


def _sha_json(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _callable_sha256(value: Any) -> str:
    code = getattr(value, "__code__", None)
    if code is None:
        raise KernelBindingError(f"kernel callable {value!r} has no Python code object")
    return sha256(marshal.dumps(code)).hexdigest()


def _module_file_sha256(module: Any) -> str:
    path = getattr(module, "__file__", None)
    if not path:
        raise KernelBindingError(f"kernel module {module!r} has no source path")
    return sha256(Path(path).read_bytes()).hexdigest()


def installed_traversal_kernel_sha256() -> str:
    return _sha_json({
        "abi_version": TRAVERSAL_KERNEL_ABI_VERSION,
        "module_file_sha256": _module_file_sha256(traversal),
        "traverse_sha256": _callable_sha256(traversal.traverse),
        "build_index_sha256": _callable_sha256(traversal.build_index),
        "softmax_sha256": _callable_sha256(traversal._softmax_topm),
        "prune_sha256": _callable_sha256(traversal._prune_topm),
        "numpy_version": np.__version__,
        "python_version": tuple(sys.version_info[:2]),
    })


def installed_readout_kernel_sha256(kind: ReadoutKind) -> str:
    callables = {
        ReadoutKind.RETRIEVE: (readouts.retrieve,),
        ReadoutKind.SELECTION: (readouts.selection_distribution,),
        ReadoutKind.DISPATCH: (readouts.dispatch, readouts.selection_distribution),
        ReadoutKind.TRAVERSAL: (readouts.traverse, traversal.traverse),
    }[kind]
    internal_names = (
        "_payload_digest",
        "_receipt",
        "_traversal_receipt",
        "_compute_read",
        "_admitted",
    )
    internal_callables = tuple(globals().get(name) for name in internal_names)
    if any(value is None for value in internal_callables):
        raise KernelBindingError("certified readout internals are not fully loaded")
    return _sha_json({
        "abi_version": READOUT_KERNEL_ABI_VERSION,
        "module_file_sha256": _module_file_sha256(sys.modules[__name__]),
        "readouts_file_sha256": _module_file_sha256(readouts),
        "kind": kind,
        "callable_sha256": tuple(_callable_sha256(value) for value in callables),
        "internal_callable_sha256": tuple(
            (name, _callable_sha256(value))
            for name, value in zip(internal_names, internal_callables, strict=True)
        ),
        "traversal_kernel_sha256": (
            installed_traversal_kernel_sha256()
            if kind == ReadoutKind.TRAVERSAL else None
        ),
        "numpy_version": np.__version__,
        "python_version": tuple(sys.version_info[:2]),
    })


def _policy_payload(policy: ReadoutPolicyV1) -> dict[str, Any]:
    return {
        "schema_version": policy.schema_version,
        "kind": policy.kind,
        "top_k": policy.top_k,
        "selection_temperature": policy.selection_temperature,
        "traversal": policy.traversal,
        "kernel_sha256": policy.kernel_sha256,
    }


def _policy_id(policy: ReadoutPolicyV1) -> str:
    return content_id("readout_policy", _policy_payload(policy))


def make_readout_policy(
    kind: ReadoutKind | str,
    *,
    top_k: int = 10,
    selection_temperature: float = 1.0,
    traversal_policy: TraversalPolicyV1 | None = None,
) -> ReadoutPolicyV1:
    kind = ReadoutKind(kind)
    if top_k <= 0:
        raise ValueError("top_k must be > 0")
    if not math.isfinite(selection_temperature) or selection_temperature <= 0:
        raise ValueError("selection_temperature must be finite and > 0")
    if kind == ReadoutKind.TRAVERSAL and traversal_policy is None:
        traversal_policy = TraversalPolicyV1(mu=0.0)
    if kind != ReadoutKind.TRAVERSAL and traversal_policy is not None:
        raise ValueError("only traversal readouts may carry a traversal policy")
    if traversal_policy is not None and not traversal_policy.kernel_sha256:
        traversal_policy = replace(
            traversal_policy,
            kernel_sha256=installed_traversal_kernel_sha256(),
        )
    provisional = ReadoutPolicyV1(
        policy_id="",
        schema_version=READOUT_POLICY_SCHEMA_VERSION,
        kind=kind,
        top_k=int(top_k),
        selection_temperature=float(selection_temperature),
        traversal=traversal_policy,
        kernel_sha256=installed_readout_kernel_sha256(kind),
    )
    _validate_policy(provisional, permit_blank_id=True)
    return replace(provisional, policy_id=_policy_id(provisional))


def _validate_policy(policy: ReadoutPolicyV1, *, permit_blank_id: bool = False) -> None:
    try:
        kind = ReadoutKind(policy.kind)
    except (TypeError, ValueError) as exc:
        raise ValueError("unsupported readout kind") from exc
    if policy.schema_version != READOUT_POLICY_SCHEMA_VERSION:
        raise ValueError("unsupported readout policy schema")
    if policy.top_k <= 0:
        raise ValueError("top_k must be > 0")
    if not math.isfinite(policy.selection_temperature) or policy.selection_temperature <= 0:
        raise ValueError("selection temperature must be finite and > 0")
    if not permit_blank_id and policy.policy_id != _policy_id(policy):
        raise ValueError("readout policy ID mismatch")
    if policy.kernel_sha256 != installed_readout_kernel_sha256(kind):
        raise KernelBindingError("readout implementation differs from the bound kernel")
    if kind == ReadoutKind.TRAVERSAL:
        value = policy.traversal
        if value is None:
            raise ValueError("traversal policy missing")
        numeric = (value.mu, value.gamma, value.tau_seed, value.entropy_blowup,
                   value.neff_min, value.kept_mass_min)
        if not all(math.isfinite(item) for item in numeric):
            raise ValueError("traversal policy must be finite")
        if value.mu < 0 or value.gamma < 0 or value.gamma > 0.5 or value.hops <= 0 or value.kappa < 0:
            raise ValueError("invalid traversal parameters")
        if value.seed_m <= 0 or value.prune_m <= 0 or value.neff_topk <= 0:
            raise ValueError("invalid traversal bounds")
        bound_globals = (
            (value.tau_seed, traversal.TAU_SEED),
            (value.seed_m, traversal.SEED_M),
            (value.prune_m, traversal.PRUNE_M),
            (value.entropy_blowup, traversal.ENTROPY_BLOWUP),
            (value.neff_min, traversal.NEFF_MIN),
            (value.neff_topk, traversal.NEFF_TOPK),
            (value.kept_mass_min, traversal.KEPT_MASS_ABSTAIN),
        )
        if any(actual != expected for actual, expected in bound_globals):
            raise ValueError("traversal policy does not match the installed kernel constants")
        if value.kernel_sha256 != installed_traversal_kernel_sha256():
            raise KernelBindingError("traversal implementation differs from the bound kernel")
    elif policy.traversal is not None:
        raise ValueError("non-traversal policy carries traversal parameters")


def _scope(bundle: fs.FieldSnapshotBundleV1, policy: ReadoutPolicyV1) -> CertificationScopeV1:
    snapshot = bundle.snapshot
    contract = snapshot.embedding_contract
    return CertificationScopeV1(
        world_build_id=snapshot.artifact.build_id,
        snapshot_id=snapshot.snapshot_id,
        embedding_producer=contract.producer,
        model_revision=contract.model_revision,
        model_config_sha256=contract.config_sha256,
        embedding_dimension=contract.dimension,
        revision_cut_id=snapshot.revision_cut.cut_id,
        kernel_sha256=snapshot.kernel_sha256,
        parameter_sha256=snapshot.parameter_sha256,
        field_policy_sha256=snapshot.policy_sha256,
        candidate_set_sha256=snapshot.candidate_set_sha256,
        readout_policy_id=policy.policy_id,
    )


def _certificate_payload(certificate: ReadoutCertificateV1) -> dict[str, Any]:
    return {
        "schema_version": certificate.schema_version,
        "status": certificate.status,
        "issuer_id": certificate.issuer_id,
        "scope": certificate.scope,
        "evidence_sha256": certificate.evidence_sha256,
        "valid_from_generation": certificate.valid_from_generation,
        "valid_through_generation": certificate.valid_through_generation,
    }


def _certificate_id(certificate: ReadoutCertificateV1) -> str:
    return content_id("readout_certificate", _certificate_payload(certificate))


def issue_certificate(
    bundle: fs.FieldSnapshotBundleV1,
    policy: ReadoutPolicyV1,
    *,
    status: CertificateStatus = CertificateStatus.CERTIFIED,
    issuer_id: str = "local-s3-certifier",
    evidence_sha256: str = fs.EMPTY_SHA256,
    valid_from_generation: int = 0,
    valid_through_generation: int = 0,
) -> ReadoutCertificateV1:
    issues = fs.verify_field_snapshot(bundle)
    if issues:
        raise fs.SnapshotHydrationError(fs.SnapshotRejectionV1(
            fs.FIELD_SNAPSHOT_SCHEMA_VERSION, issues,
        ))
    _validate_policy(policy)
    if (
        isinstance(valid_from_generation, bool)
        or isinstance(valid_through_generation, bool)
        or not isinstance(valid_from_generation, int)
        or not isinstance(valid_through_generation, int)
        or valid_from_generation < 0
        or valid_through_generation < valid_from_generation
    ):
        raise ValueError("invalid certificate generation interval")
    provisional = ReadoutCertificateV1(
        certificate_id="",
        schema_version=CERTIFICATE_SCHEMA_VERSION,
        status=CertificateStatus(status),
        issuer_id=issuer_id,
        scope=_scope(bundle, policy),
        evidence_sha256=evidence_sha256,
        valid_from_generation=valid_from_generation,
        valid_through_generation=valid_through_generation,
    )
    return replace(provisional, certificate_id=_certificate_id(provisional))


def make_query_embedding(
    query_id: str,
    input_text: str,
    vector: np.ndarray | tuple[float, ...],
    contract: fs.EmbeddingContractV1,
    *,
    producer: str | None = None,
    model_revision: str | None = None,
    config_sha256: str | None = None,
) -> QueryEmbeddingV1:
    array = np.asarray(vector, dtype=np.float64)
    if array.ndim != 1 or not np.isfinite(array).all():
        raise ValueError("query embedding must be a finite vector")
    frozen = fs.freeze_array(array, "<f8")
    return QueryEmbeddingV1(
        query_id=query_id,
        input_sha256=sha256(input_text.encode("utf-8")).hexdigest(),
        producer=contract.producer if producer is None else producer,
        model_revision=contract.model_revision if model_revision is None else model_revision,
        config_sha256=contract.config_sha256 if config_sha256 is None else config_sha256,
        dimension=int(array.size),
        vector=tuple(float(value) for value in array),
        output_sha256=frozen.sha256,
    )


def _request_payload(request: ReadoutRequestV1) -> dict[str, Any]:
    return {
        "certificate_id": request.certificate_id,
        "expected_world_build_id": request.expected_world_build_id,
        "expected_snapshot_id": request.expected_snapshot_id,
        "expected_revision_cut_id": request.expected_revision_cut_id,
        "query": request.query,
        "policy": request.policy,
    }


def _request_id(request: ReadoutRequestV1) -> str:
    return content_id("readout_request", _request_payload(request))


def make_request(
    bundle: fs.FieldSnapshotBundleV1,
    certificate: ReadoutCertificateV1,
    policy: ReadoutPolicyV1,
    query: QueryEmbeddingV1,
    *,
    expected_world_build_id: str | None = None,
    expected_snapshot_id: str | None = None,
    expected_revision_cut_id: str | None = None,
) -> ReadoutRequestV1:
    snapshot = bundle.snapshot
    provisional = ReadoutRequestV1(
        request_id="",
        certificate_id=certificate.certificate_id,
        expected_world_build_id=(snapshot.artifact.build_id if expected_world_build_id is None
                                 else expected_world_build_id),
        expected_snapshot_id=(snapshot.snapshot_id if expected_snapshot_id is None
                              else expected_snapshot_id),
        expected_revision_cut_id=(snapshot.revision_cut.cut_id
                                  if expected_revision_cut_id is None
                                  else expected_revision_cut_id),
        query=query,
        policy=policy,
    )
    return replace(provisional, request_id=_request_id(provisional))


def _payload_digest(payload: ReadoutPayloadV1) -> str:
    return _sha_json({
        "kind": payload.kind,
        "target_ordinals": payload.target_ordinals,
        "target_ids": payload.target_ids,
        "scores": payload.scores,
        "probabilities": payload.probabilities,
        "dispatch_target_ordinal": payload.dispatch_target_ordinal,
        "dispatch_target_id": payload.dispatch_target_id,
        "traversal_receipt": payload.traversal_receipt,
        "component_sha256": payload.score_components.component_sha256,
    })


def _receipt(
    request: ReadoutRequestV1,
    snapshot_id: str,
    action: ReadoutAction,
    *,
    refusal_code: RefusalCode | None = None,
    detail: str = "",
    kernel_invoked: bool,
    payload_sha256: str | None = None,
) -> ReadoutReceiptV1:
    payload = {
        "request_id": request.request_id,
        "certificate_id": request.certificate_id,
        "snapshot_id": snapshot_id,
        "action": action,
        "refusal_code": refusal_code,
        "detail": detail,
        "kernel_invoked": kernel_invoked,
        "payload_sha256": payload_sha256,
    }
    return ReadoutReceiptV1(
        receipt_id=content_id("readout_receipt", payload),
        request_id=request.request_id,
        certificate_id=request.certificate_id,
        snapshot_id=snapshot_id,
        action=action,
        refusal_code=refusal_code,
        detail=detail,
        kernel_invoked=kernel_invoked,
        payload_sha256=payload_sha256,
    )


def _traversal_receipt(receipt: traversal.TraversalReceipt) -> TraversalReceiptV1:
    return TraversalReceiptV1(
        abstained=bool(receipt.abstained),
        abstain_reason=receipt.abstain_reason,
        mu=float(receipt.mu),
        gamma=float(receipt.gamma),
        hops=int(receipt.K),
        kappa=int(receipt.kappa),
        n_eff=(float(receipt.n_eff) if math.isfinite(receipt.n_eff) else None),
        kept_mass=tuple(float(value) for value in receipt.kept_mass),
        paths=tuple((int(a), int(b), int(c), int(d), float(e))
                    for a, b, c, d, e in receipt.paths),
        contraction_log=tuple(float(value) for value in receipt.contraction_log),
    )


def _compute_read(
    bundle: fs.FieldSnapshotBundleV1,
    request: ReadoutRequestV1,
    *,
    force_static: bool = False,
) -> tuple[ReadoutPayloadV1, ReadoutAction]:
    """Internal numerical kernel; callers must perform admission first."""
    global _KERNEL_INVOCATION_COUNT
    _KERNEL_INVOCATION_COUNT += 1
    policy = request.policy
    query = np.asarray(request.query.vector, dtype=np.float64)
    field = fs.hydrate_weight_field(bundle, verify=False)
    components = fs.score_components(bundle, query, verify=False)
    target_ids = bundle.snapshot.target_ids_by_dense
    receipt: TraversalReceiptV1 | None = None
    probabilities: tuple[float, ...] = ()
    dispatch_ordinal: int | None = None
    dispatch_id: str | None = None
    action = ReadoutAction.APPLY

    if policy.kind == ReadoutKind.RETRIEVE:
        ordinals_array = readouts.retrieve(field, query, k=policy.top_k)
        scores_array = field.value(query, ordinals_array)
    elif policy.kind == ReadoutKind.SELECTION:
        edges, probs = readouts.selection_distribution(
            field, query, temp=policy.selection_temperature,
        )
        order = np.argsort(-probs, kind="stable")[:policy.top_k]
        ordinals_array = edges[order]
        scores_array = field.value(query, ordinals_array)
        probabilities = tuple(float(value) for value in probs[order])
    elif policy.kind == ReadoutKind.DISPATCH:
        dispatch_ordinal = readouts.dispatch(field, query)
        ordinals_array = np.asarray([dispatch_ordinal], dtype=np.int64)
        scores_array = field.value(query, ordinals_array)
        edges, probs = readouts.selection_distribution(
            field, query, temp=policy.selection_temperature,
        )
        probabilities = (float(probs[int(np.flatnonzero(edges == dispatch_ordinal)[0])]),)
        dispatch_id = target_ids[dispatch_ordinal]
    elif policy.kind == ReadoutKind.TRAVERSAL:
        traversal_policy = policy.traversal
        assert traversal_policy is not None
        mu = 0.0 if force_static else traversal_policy.mu
        full_ordinals, full_scores, raw_receipt = readouts.traverse(
            field,
            query,
            k=field.hg.M,
            mu=mu,
            gamma=traversal_policy.gamma,
            K=traversal_policy.hops,
            kappa=traversal_policy.kappa,
        )
        final_by_ordinal = np.empty(field.hg.M, dtype=np.float64)
        final_by_ordinal[full_ordinals] = full_scores
        components = fs.attach_traversal_scores(components, final_by_ordinal)
        ordinals_array = full_ordinals[:policy.top_k]
        scores_array = full_scores[:policy.top_k]
        receipt = _traversal_receipt(raw_receipt)
        if force_static or raw_receipt.abstained:
            action = ReadoutAction.FALLBACK_CURRENT_STATIC
    else:  # pragma: no cover - StrEnum construction prevents this
        raise ValueError(f"unsupported readout kind {policy.kind!r}")

    ordinals = tuple(int(value) for value in ordinals_array)
    selected_ids = tuple(target_ids[value] for value in ordinals)
    provisional = ReadoutPayloadV1(
        kind=policy.kind,
        target_ordinals=ordinals,
        target_ids=selected_ids,
        scores=tuple(float(value) for value in scores_array),
        probabilities=probabilities,
        dispatch_target_ordinal=dispatch_ordinal,
        dispatch_target_id=dispatch_id,
        traversal_receipt=receipt,
        score_components=components,
        payload_sha256="",
    )
    payload = replace(provisional, payload_sha256=_payload_digest(provisional))
    component_scores = np.asarray(payload.score_components.final_scores, dtype=np.float64)
    if not np.array_equal(
        np.asarray(payload.scores, dtype=np.float64),
        component_scores[np.asarray(payload.target_ordinals, dtype=np.int64)],
    ):
        raise RuntimeError("readout payload is not explained by its component receipt")
    return payload, action


def research_probe(
    bundle: fs.FieldSnapshotBundleV1,
    request: ReadoutRequestV1,
    *,
    force_static: bool = False,
) -> ProbeResultV1:
    """Explicitly non-deployable raw computation for experiments only."""
    payload, action = _compute_read(bundle, request, force_static=force_static)
    warning = "UNSAFE RESEARCH PROBE: certificate bindings were not checked"
    probe_id = content_id("readout_probe", {
        "disposition": ProbeDisposition.NOT_DEPLOYABLE,
        "warning": warning,
        "request_id": request.request_id,
        "snapshot_id": bundle.snapshot.snapshot_id,
        "observed_action": action,
        "payload_sha256": payload.payload_sha256,
    })
    return ProbeResultV1(
        probe_id=probe_id,
        disposition=ProbeDisposition.NOT_DEPLOYABLE,
        warning=warning,
        observed_action=action,
        payload=payload,
    )


def _admitted(
    bundle: fs.FieldSnapshotBundleV1,
    request: ReadoutRequestV1,
    *,
    force_static: bool,
) -> CertifiedReadoutResultV1:
    payload, action = _compute_read(bundle, request, force_static=force_static)
    expected_payload_sha256 = _payload_digest(payload)
    if payload.payload_sha256 != expected_payload_sha256:
        return CertifiedReadoutResultV1(
            payload=None,
            receipt=_receipt(
                request,
                bundle.snapshot.snapshot_id,
                ReadoutAction.REFUSE,
                refusal_code=RefusalCode.KERNEL_MISMATCH,
                detail="computed payload digest does not match its content",
                kernel_invoked=True,
            ),
        )
    return CertifiedReadoutResultV1(
        payload=payload,
        receipt=_receipt(
            request,
            bundle.snapshot.snapshot_id,
            action,
            kernel_invoked=True, payload_sha256=payload.payload_sha256,
        ),
    )


def _refuse(
    bundle: fs.FieldSnapshotBundleV1,
    request: ReadoutRequestV1,
    code: RefusalCode,
    detail: str,
) -> CertifiedReadoutResultV1:
    return CertifiedReadoutResultV1(
        payload=None,
        receipt=_receipt(
            request, bundle.snapshot.snapshot_id, ReadoutAction.REFUSE,
            refusal_code=code, detail=detail, kernel_invoked=False,
        ),
    )


def read_certified(
    bundle: fs.FieldSnapshotBundleV1,
    certificate: ReadoutCertificateV1,
    request: ReadoutRequestV1,
    context: AdmissionContextV1,
) -> CertifiedReadoutResultV1:
    """Validate the exact certified tuple, then and only then invoke a readout."""
    try:
        _validate_policy(request.policy)
        expected_request_id = _request_id(request)
    except KernelBindingError as exc:
        return _refuse(bundle, request, RefusalCode.KERNEL_MISMATCH, str(exc))
    except (TypeError, ValueError) as exc:
        return _refuse(bundle, request, RefusalCode.INVALID_REQUEST, str(exc))
    if request.request_id != expected_request_id:
        return _refuse(bundle, request, RefusalCode.INVALID_REQUEST, "request ID mismatch")
    try:
        status = CertificateStatus(certificate.status)
        expected_certificate_id = _certificate_id(certificate)
        trusted = set(context.trusted_certificate_ids)
    except (TypeError, ValueError) as exc:
        return _refuse(bundle, request, RefusalCode.INVALID_CERTIFICATE, str(exc))
    if (
        certificate.schema_version != CERTIFICATE_SCHEMA_VERSION
        or certificate.certificate_id != expected_certificate_id
        or request.certificate_id != certificate.certificate_id
        or certificate.certificate_id not in trusted
    ):
        return _refuse(
            bundle, request, RefusalCode.INVALID_CERTIFICATE,
            "certificate is malformed, untrusted, or not the requested certificate",
        )
    generations = (
        context.current_generation,
        certificate.valid_from_generation,
        certificate.valid_through_generation,
    )
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0
           for value in generations):
        return _refuse(
            bundle, request, RefusalCode.INVALID_REQUEST,
            "certificate generations must be non-negative integers",
        )
    if context.current_generation < certificate.valid_from_generation or (
        context.current_generation > certificate.valid_through_generation
    ):
        return _refuse(
            bundle, request, RefusalCode.CERTIFICATE_EXPIRED,
            "certificate is outside its monotonic generation interval",
        )
    if status in {CertificateStatus.REVOKED, CertificateStatus.BROKEN}:
        return _refuse(
            bundle, request, RefusalCode.INVALID_CERTIFICATE,
            f"certificate status is {status.value}",
        )
    if status == CertificateStatus.OFF and request.policy.kind != ReadoutKind.TRAVERSAL:
        return _refuse(
            bundle, request, RefusalCode.INVALID_CERTIFICATE,
            "OFF is only a certified static fallback for traversal",
        )

    snapshot_issues = fs.verify_field_snapshot(bundle)
    if snapshot_issues:
        if any(issue.code == fs.SnapshotRejectCode.REVISION_TARGET_MISMATCH
               for issue in snapshot_issues):
            code = RefusalCode.REVISION_FOLD_MISMATCH
        elif any(issue.code == fs.SnapshotRejectCode.REVISION_CUT_MISMATCH
                 for issue in snapshot_issues):
            code = RefusalCode.REVISION_CUT_MISMATCH
        elif any("kernel" in issue.path for issue in snapshot_issues):
            code = RefusalCode.KERNEL_MISMATCH
        else:
            code = RefusalCode.SNAPSHOT_BROKEN
        return _refuse(
            bundle, request, code,
            "; ".join(f"{issue.code.value}:{issue.path}" for issue in snapshot_issues),
        )

    snapshot = bundle.snapshot
    scope = certificate.scope
    contract = snapshot.embedding_contract
    if (
        request.expected_world_build_id != snapshot.artifact.build_id
        or scope.world_build_id != snapshot.artifact.build_id
    ):
        return _refuse(bundle, request, RefusalCode.WORLD_FIELD_MISMATCH,
                       "world build ID differs from the certified field")
    if request.query.producer != contract.producer or scope.embedding_producer != contract.producer:
        return _refuse(bundle, request, RefusalCode.MODEL_PRODUCER_MISMATCH,
                       "query embedding producer differs from the field")
    if request.query.model_revision != contract.model_revision or scope.model_revision != contract.model_revision:
        return _refuse(bundle, request, RefusalCode.MODEL_REVISION_MISMATCH,
                       "query model revision differs from the field")
    if request.query.config_sha256 != contract.config_sha256 or scope.model_config_sha256 != contract.config_sha256:
        return _refuse(bundle, request, RefusalCode.MODEL_CONFIG_MISMATCH,
                       "query model configuration differs from the field")
    try:
        query_array = np.asarray(request.query.vector, dtype=np.float64)
        query_output_sha256 = fs.freeze_array(query_array, "<f8").sha256
    except (TypeError, ValueError, OverflowError) as exc:
        return _refuse(bundle, request, RefusalCode.INVALID_REQUEST,
                       f"malformed query vector: {exc}")
    if (
        request.query.dimension != contract.dimension
        or scope.embedding_dimension != contract.dimension
        or query_array.shape != (contract.dimension,)
        or not np.isfinite(query_array).all()
        or request.query.output_sha256 != query_output_sha256
    ):
        return _refuse(bundle, request, RefusalCode.EMBEDDING_DIMENSION_MISMATCH,
                       "query vector shape, finiteness, or digest differs from the field")
    if scope.kernel_sha256 != snapshot.kernel_sha256:
        return _refuse(bundle, request, RefusalCode.KERNEL_MISMATCH,
                       "field kernel differs from certificate scope")
    if (
        scope.parameter_sha256 != snapshot.parameter_sha256
        or scope.field_policy_sha256 != snapshot.policy_sha256
    ):
        return _refuse(bundle, request, RefusalCode.FIELD_POLICY_MISMATCH,
                       "field parameters or policy differ from certificate scope")
    if (
        request.expected_snapshot_id != snapshot.snapshot_id
        or scope.snapshot_id != snapshot.snapshot_id
        or scope.candidate_set_sha256 != snapshot.candidate_set_sha256
    ):
        return _refuse(bundle, request, RefusalCode.FIELD_SNAPSHOT_MISMATCH,
                       "snapshot or candidate layout differs from certificate scope")
    if (
        request.expected_revision_cut_id != snapshot.revision_cut.cut_id
        or scope.revision_cut_id != snapshot.revision_cut.cut_id
    ):
        return _refuse(bundle, request, RefusalCode.REVISION_CUT_MISMATCH,
                       "revision cut differs from certificate scope")
    if scope.readout_policy_id != request.policy.policy_id:
        return _refuse(bundle, request, RefusalCode.READOUT_POLICY_MISMATCH,
                       "readout policy differs from certificate scope")

    force_static = status == CertificateStatus.OFF
    return _admitted(bundle, request, force_static=force_static)
