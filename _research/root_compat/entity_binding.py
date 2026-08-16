"""Reversible, evidence-bound entity identity receipts for HSWM S4.0.

This is the first graph-neutral World Compiler v2 vertical slice.  It keeps
every immutable local entity anchor and every resolver candidate, including
ambiguous, rejected, and quarantined outcomes.  A canonical view may operate
on the accepted subset without treating unresolved material as absent or
destructively unioning source mentions.

Corrections are append-only revisions.  Rebuilding the view from a different
ledger cut is therefore sufficient to undo a bad binding; no source record or
local identity is mutated.  The module is pure and deterministic: it performs
no filesystem, network, clock, model, or random operation and changes no HSWM
graph topology.

Longinus ReferenceSite:
``WORLD_COMPILER_V2_OSS_PROM_2026-07-21.md`` sections 4.1 and 5 S4.0.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import math
import re
from typing import Iterable

from world_ir import SourceSnapshotV1, canonical_json, content_id, sha256_text


SCHEMA_VERSION = "hswm-entity-binding/v1"
VIEW_SCHEMA_VERSION = "hswm-canonical-entity-view/v1"

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_QID_RE = re.compile(r"Q[1-9][0-9]*\Z")
_RECEIPT_PREFIX = "hswm:entity_binding_receipt:v1:"


class BindingDecision(StrEnum):
    ACCEPTED = "accepted"
    AMBIGUOUS = "ambiguous"
    REJECTED = "rejected"
    QUARANTINED = "quarantined"


class CanonicalMemberState(StrEnum):
    ACCEPTED = "accepted"
    AMBIGUOUS = "ambiguous"
    REJECTED = "rejected"
    QUARANTINED = "quarantined"
    UNOBSERVED = "unobserved"


class BindingLedgerError(ValueError):
    """The immutable receipt ledger cannot produce one deterministic view."""


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _require_sha256(name: str, value: str) -> None:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


def _reject_string_iterable(name: str, value: object) -> None:
    if isinstance(value, (str, bytes)):
        raise TypeError(f"{name} must be an iterable of records, not text")


@dataclass(frozen=True)
class BindingCandidateV1:
    """One frozen resolver proposal; a proposal is never itself a binding."""

    target_id: str
    score: float
    rank: int
    entity_type: str
    response_sha256: str

    def __post_init__(self) -> None:
        _require_text("candidate target_id", self.target_id)
        _require_text("candidate entity_type", self.entity_type)
        if isinstance(self.rank, bool) or not isinstance(self.rank, int) or self.rank < 1:
            raise ValueError("candidate rank must be a positive integer")
        if not isinstance(self.score, (int, float)) or isinstance(self.score, bool):
            raise ValueError("candidate score must be numeric")
        if not math.isfinite(float(self.score)):
            raise ValueError("candidate score must be finite")
        object.__setattr__(self, "score", float(self.score))
        _require_sha256("candidate response_sha256", self.response_sha256)


@dataclass(frozen=True)
class LocalEntityAnchorV1:
    """One immutable local identity derived from one exact source selector."""

    local_entity_anchor_id: str
    mention_role_id: str
    evidence_selector_id: str
    source_id: str
    source_text_sha256: str
    start: int
    end: int
    exact: str

    def __post_init__(self) -> None:
        validate_local_entity_anchor(self)


@dataclass(frozen=True)
class EntityBindingReceiptV1:
    """Content-addressed decision about one exact mention-role binding."""

    receipt_id: str
    mention_role_id: str
    evidence_selector_id: str
    local_entity_anchor_id: str
    candidate_set: tuple[BindingCandidateV1, ...]
    selected_target_id: str | None
    external_qid: str | None
    resolver: str
    model_revision: str
    resolver_revision_sha256: str
    model_revision_sha256: str
    config_sha256: str
    output_sha256: str
    policy_id: str
    thresholds_digest: str
    decision: BindingDecision
    decision_reason: str
    decision_detail_sha256: str
    quarantine_evidence_ids: tuple[str, ...] = ()
    supersedes_receipt_ids: tuple[str, ...] = ()
    previous_receipt_id: str | None = None
    compensates_receipt_id: str | None = None

    def __post_init__(self) -> None:
        validate_binding_receipt(self)


@dataclass(frozen=True)
class CanonicalEntityMemberV1:
    """Current view of one immutable local anchor; history remains attached."""

    local_entity_anchor_id: str
    canonical_entity_id: str
    state: CanonicalMemberState
    selected_target_id: str | None
    external_qid: str | None
    active_receipt_ids: tuple[str, ...]
    history_receipt_ids: tuple[str, ...]


@dataclass(frozen=True)
class CanonicalEntityClusterV1:
    """A reversible projection, never a destructive source-entity union."""

    canonical_entity_id: str
    selected_target_id: str | None
    local_entity_anchor_ids: tuple[str, ...]
    active_receipt_ids: tuple[str, ...]
    external_qids: tuple[str, ...]


@dataclass(frozen=True)
class CanonicalEntityViewV1:
    """Deterministic ledger-cut snapshot retaining accepted and dark material."""

    schema_version: str
    snapshot_id: str
    policy_id: str
    source_root_sha256: str
    receipt_root_sha256: str
    local_entity_anchors: tuple[LocalEntityAnchorV1, ...]
    receipts: tuple[EntityBindingReceiptV1, ...]
    members: tuple[CanonicalEntityMemberV1, ...]
    clusters: tuple[CanonicalEntityClusterV1, ...]
    superseded_receipt_ids: tuple[str, ...]
    compensated_receipt_ids: tuple[str, ...]
    ambiguous_receipt_ids: tuple[str, ...]
    rejected_receipt_ids: tuple[str, ...]
    quarantined_receipt_ids: tuple[str, ...]


def _validate_source_snapshot(source: SourceSnapshotV1) -> None:
    for name, value in (
        ("source_id", source.source_id),
        ("source locator", source.locator),
        ("source media_type", source.media_type),
    ):
        _require_text(name, value)
    _require_sha256("source content_sha256", source.content_sha256)
    if sha256_text(source.content) != source.content_sha256:
        raise ValueError("source content_sha256 does not bind source content")
    expected_id = content_id("src", {
        "locator": source.locator,
        "content_sha256": source.content_sha256,
    })
    if source.source_id != expected_id:
        raise ValueError("source_id does not bind locator and content digest")


def _anchor_payload(
    *,
    mention_role_id: str,
    evidence_selector_id: str,
    source_id: str,
    source_text_sha256: str,
    start: int,
    end: int,
    exact: str,
) -> dict[str, object]:
    return {
        "schema_version": "hswm-local-entity-anchor/v1",
        "mention_role_id": mention_role_id,
        "evidence_selector_id": evidence_selector_id,
        "source_id": source_id,
        "source_text_sha256": source_text_sha256,
        "start": start,
        "end": end,
        "exact": exact,
    }


def make_local_entity_anchor(
    *,
    source: SourceSnapshotV1,
    mention_role_id: str,
    evidence_selector_id: str,
    start: int,
    end: int,
    exact: str,
) -> LocalEntityAnchorV1:
    """Bind a local identity to an exact selector in a frozen source."""

    _validate_source_snapshot(source)
    if isinstance(start, bool) or isinstance(end, bool):
        raise ValueError("anchor offsets must be integers")
    if not isinstance(start, int) or not isinstance(end, int):
        raise ValueError("anchor offsets must be integers")
    if start < 0 or end <= start or end > len(source.content):
        raise ValueError("anchor selector range is invalid")
    if source.content[start:end] != exact:
        raise ValueError("anchor selector exact text does not match source")
    payload = _anchor_payload(
        mention_role_id=mention_role_id,
        evidence_selector_id=evidence_selector_id,
        source_id=source.source_id,
        source_text_sha256=source.content_sha256,
        start=start,
        end=end,
        exact=exact,
    )
    return LocalEntityAnchorV1(
        local_entity_anchor_id=content_id("local_entity_anchor", payload),
        mention_role_id=mention_role_id,
        evidence_selector_id=evidence_selector_id,
        source_id=source.source_id,
        source_text_sha256=source.content_sha256,
        start=start,
        end=end,
        exact=exact,
    )


def validate_local_entity_anchor(anchor: LocalEntityAnchorV1) -> None:
    for name, value in (
        ("local_entity_anchor_id", anchor.local_entity_anchor_id),
        ("anchor mention_role_id", anchor.mention_role_id),
        ("anchor evidence_selector_id", anchor.evidence_selector_id),
        ("anchor source_id", anchor.source_id),
        ("anchor exact", anchor.exact),
    ):
        _require_text(name, value)
    _require_sha256("anchor source_text_sha256", anchor.source_text_sha256)
    if isinstance(anchor.start, bool) or isinstance(anchor.end, bool):
        raise ValueError("anchor offsets must be integers")
    if not isinstance(anchor.start, int) or not isinstance(anchor.end, int):
        raise ValueError("anchor offsets must be integers")
    if anchor.start < 0 or anchor.end <= anchor.start:
        raise ValueError("anchor selector range is invalid")
    if anchor.end - anchor.start != len(anchor.exact):
        raise ValueError("anchor selector range and exact text length disagree")
    expected = content_id("local_entity_anchor", _anchor_payload(
        mention_role_id=anchor.mention_role_id,
        evidence_selector_id=anchor.evidence_selector_id,
        source_id=anchor.source_id,
        source_text_sha256=anchor.source_text_sha256,
        start=anchor.start,
        end=anchor.end,
        exact=anchor.exact,
    ))
    if anchor.local_entity_anchor_id != expected:
        raise ValueError("local_entity_anchor_id does not bind selector evidence")


def verify_local_entity_anchor(
    anchor: LocalEntityAnchorV1,
    source: SourceSnapshotV1,
) -> None:
    validate_local_entity_anchor(anchor)
    _validate_source_snapshot(source)
    if anchor.source_id != source.source_id:
        raise ValueError("local anchor is bound to a different source")
    if anchor.source_text_sha256 != source.content_sha256:
        raise ValueError("local anchor source digest mismatch")
    if anchor.end > len(source.content):
        raise ValueError("local anchor selector exceeds source length")
    if source.content[anchor.start:anchor.end] != anchor.exact:
        raise ValueError("local anchor selector no longer matches source")


def _receipt_payload(
    *,
    mention_role_id: str,
    evidence_selector_id: str,
    local_entity_anchor_id: str,
    candidate_set: tuple[BindingCandidateV1, ...],
    selected_target_id: str | None,
    external_qid: str | None,
    resolver: str,
    model_revision: str,
    resolver_revision_sha256: str,
    model_revision_sha256: str,
    config_sha256: str,
    output_sha256: str,
    policy_id: str,
    thresholds_digest: str,
    decision: BindingDecision,
    decision_reason: str,
    decision_detail_sha256: str,
    quarantine_evidence_ids: tuple[str, ...],
    supersedes_receipt_ids: tuple[str, ...],
    previous_receipt_id: str | None,
    compensates_receipt_id: str | None,
) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "mention_role_id": mention_role_id,
        "evidence_selector_id": evidence_selector_id,
        "local_entity_anchor_id": local_entity_anchor_id,
        "candidate_set": candidate_set,
        "selected_target_id": selected_target_id,
        "external_qid": external_qid,
        "resolver": resolver,
        "model_revision": model_revision,
        "resolver_revision_sha256": resolver_revision_sha256,
        "model_revision_sha256": model_revision_sha256,
        "config_sha256": config_sha256,
        "output_sha256": output_sha256,
        "policy_id": policy_id,
        "thresholds_digest": thresholds_digest,
        "decision": decision,
        "decision_reason": decision_reason,
        "decision_detail_sha256": decision_detail_sha256,
        "quarantine_evidence_ids": quarantine_evidence_ids,
        "supersedes_receipt_ids": supersedes_receipt_ids,
        "previous_receipt_id": previous_receipt_id,
        "compensates_receipt_id": compensates_receipt_id,
    }


def _canonical_candidates(
    candidates: Iterable[BindingCandidateV1],
) -> tuple[BindingCandidateV1, ...]:
    _reject_string_iterable("candidates", candidates)
    ordered = tuple(sorted(tuple(candidates), key=lambda item: (item.rank, item.target_id)))
    ranks = tuple(item.rank for item in ordered)
    if ranks != tuple(range(1, len(ordered) + 1)):
        raise ValueError("candidate ranks must be contiguous and start at one")
    targets = tuple(item.target_id for item in ordered)
    if len(targets) != len(set(targets)):
        raise ValueError("candidate target_id values must be unique")
    return ordered


def make_binding_receipt(
    *,
    mention_role_id: str,
    evidence_selector_id: str,
    local_entity_anchor_id: str,
    candidates: Iterable[BindingCandidateV1] = (),
    selected_target_id: str | None = None,
    external_qid: str | None = None,
    resolver: str,
    model_revision: str,
    resolver_revision_sha256: str,
    model_revision_sha256: str,
    config_sha256: str,
    output_sha256: str,
    policy_id: str,
    thresholds_digest: str,
    decision: BindingDecision | str,
    decision_reason: str,
    decision_detail_sha256: str,
    quarantine_evidence_ids: Iterable[str] = (),
    supersedes_receipt_ids: Iterable[str] = (),
    previous_receipt_id: str | None = None,
    compensates_receipt_id: str | None = None,
) -> EntityBindingReceiptV1:
    """Create one canonical receipt after freezing all resolver observations."""

    canonical_candidates = _canonical_candidates(candidates)
    canonical_decision = BindingDecision(decision)
    _reject_string_iterable("quarantine_evidence_ids", quarantine_evidence_ids)
    _reject_string_iterable("supersedes_receipt_ids", supersedes_receipt_ids)
    canonical_quarantine_ids = tuple(sorted(set(quarantine_evidence_ids)))
    canonical_supersedes = tuple(sorted(set(supersedes_receipt_ids)))
    payload = _receipt_payload(
        mention_role_id=mention_role_id,
        evidence_selector_id=evidence_selector_id,
        local_entity_anchor_id=local_entity_anchor_id,
        candidate_set=canonical_candidates,
        selected_target_id=selected_target_id,
        external_qid=external_qid,
        resolver=resolver,
        model_revision=model_revision,
        resolver_revision_sha256=resolver_revision_sha256,
        model_revision_sha256=model_revision_sha256,
        config_sha256=config_sha256,
        output_sha256=output_sha256,
        policy_id=policy_id,
        thresholds_digest=thresholds_digest,
        decision=canonical_decision,
        decision_reason=decision_reason,
        decision_detail_sha256=decision_detail_sha256,
        quarantine_evidence_ids=canonical_quarantine_ids,
        supersedes_receipt_ids=canonical_supersedes,
        previous_receipt_id=previous_receipt_id,
        compensates_receipt_id=compensates_receipt_id,
    )
    return EntityBindingReceiptV1(
        receipt_id=content_id("entity_binding_receipt", payload),
        mention_role_id=mention_role_id,
        evidence_selector_id=evidence_selector_id,
        local_entity_anchor_id=local_entity_anchor_id,
        candidate_set=canonical_candidates,
        selected_target_id=selected_target_id,
        external_qid=external_qid,
        resolver=resolver,
        model_revision=model_revision,
        resolver_revision_sha256=resolver_revision_sha256,
        model_revision_sha256=model_revision_sha256,
        config_sha256=config_sha256,
        output_sha256=output_sha256,
        policy_id=policy_id,
        thresholds_digest=thresholds_digest,
        decision=canonical_decision,
        decision_reason=decision_reason,
        decision_detail_sha256=decision_detail_sha256,
        quarantine_evidence_ids=canonical_quarantine_ids,
        supersedes_receipt_ids=canonical_supersedes,
        previous_receipt_id=previous_receipt_id,
        compensates_receipt_id=compensates_receipt_id,
    )


def validate_binding_receipt(receipt: EntityBindingReceiptV1) -> None:
    """Fail closed on malformed or self-inconsistent immutable decisions."""

    for name, value in (
        ("receipt_id", receipt.receipt_id),
        ("mention_role_id", receipt.mention_role_id),
        ("evidence_selector_id", receipt.evidence_selector_id),
        ("local_entity_anchor_id", receipt.local_entity_anchor_id),
        ("resolver", receipt.resolver),
        ("model_revision", receipt.model_revision),
        ("policy_id", receipt.policy_id),
        ("decision_reason", receipt.decision_reason),
    ):
        _require_text(name, value)
    for name, value in (
        ("resolver_revision_sha256", receipt.resolver_revision_sha256),
        ("model_revision_sha256", receipt.model_revision_sha256),
        ("config_sha256", receipt.config_sha256),
        ("output_sha256", receipt.output_sha256),
        ("thresholds_digest", receipt.thresholds_digest),
        ("decision_detail_sha256", receipt.decision_detail_sha256),
    ):
        _require_sha256(name, value)
    if not isinstance(receipt.decision, BindingDecision):
        raise ValueError("decision must be a BindingDecision")
    if receipt.quarantine_evidence_ids != tuple(sorted(
        set(receipt.quarantine_evidence_ids)
    )):
        raise ValueError("quarantine_evidence_ids must be sorted and unique")
    if any(not isinstance(item, str) or not item.strip()
           for item in receipt.quarantine_evidence_ids):
        raise ValueError("quarantine_evidence_ids must be non-empty strings")
    if receipt.decision is BindingDecision.QUARANTINED:
        if not receipt.quarantine_evidence_ids:
            raise ValueError("quarantined receipt requires quarantine evidence")
    elif receipt.quarantine_evidence_ids:
        raise ValueError("only a quarantined receipt may cite quarantine evidence")
    if receipt.supersedes_receipt_ids != tuple(sorted(
        set(receipt.supersedes_receipt_ids)
    )):
        raise ValueError("supersedes_receipt_ids must be sorted and unique")
    if any(not item.startswith(_RECEIPT_PREFIX)
           for item in receipt.supersedes_receipt_ids):
        raise ValueError("supersedes_receipt_ids contains a non-receipt ID")
    if receipt.candidate_set != _canonical_candidates(receipt.candidate_set):
        raise ValueError("candidate_set is not in canonical rank order")

    candidate_targets = {item.target_id for item in receipt.candidate_set}
    if receipt.decision is BindingDecision.ACCEPTED:
        if not receipt.selected_target_id:
            raise ValueError("accepted receipt requires selected_target_id")
        if receipt.selected_target_id not in candidate_targets:
            raise ValueError("selected_target_id is absent from candidate_set")
    elif receipt.selected_target_id is not None:
        raise ValueError("only an accepted receipt may select a target")

    if receipt.external_qid is not None:
        if receipt.decision is not BindingDecision.ACCEPTED:
            raise ValueError("only an accepted receipt may carry external_qid")
        if _QID_RE.fullmatch(receipt.external_qid) is None:
            raise ValueError("external_qid must be a Wikidata QID")
        if receipt.external_qid not in candidate_targets:
            raise ValueError("external_qid must survive in candidate_set")
    if (
        receipt.selected_target_id is not None
        and _QID_RE.fullmatch(receipt.selected_target_id) is not None
        and receipt.external_qid != receipt.selected_target_id
    ):
        raise ValueError("QID selected_target_id must equal external_qid")

    for name, value in (
        ("previous_receipt_id", receipt.previous_receipt_id),
        ("compensates_receipt_id", receipt.compensates_receipt_id),
    ):
        if value is not None and not value.startswith(_RECEIPT_PREFIX):
            raise ValueError(f"{name} is not an HSWM entity binding receipt ID")
        if value == receipt.receipt_id:
            raise ValueError(f"{name} cannot self-reference")
    if receipt.receipt_id in receipt.supersedes_receipt_ids:
        raise ValueError("supersedes_receipt_ids cannot self-reference")
    if receipt.previous_receipt_id in receipt.supersedes_receipt_ids:
        raise ValueError("previous_receipt_id cannot also be superseded")

    payload = _receipt_payload(
        mention_role_id=receipt.mention_role_id,
        evidence_selector_id=receipt.evidence_selector_id,
        local_entity_anchor_id=receipt.local_entity_anchor_id,
        candidate_set=receipt.candidate_set,
        selected_target_id=receipt.selected_target_id,
        external_qid=receipt.external_qid,
        resolver=receipt.resolver,
        model_revision=receipt.model_revision,
        resolver_revision_sha256=receipt.resolver_revision_sha256,
        model_revision_sha256=receipt.model_revision_sha256,
        config_sha256=receipt.config_sha256,
        output_sha256=receipt.output_sha256,
        policy_id=receipt.policy_id,
        thresholds_digest=receipt.thresholds_digest,
        decision=receipt.decision,
        decision_reason=receipt.decision_reason,
        decision_detail_sha256=receipt.decision_detail_sha256,
        quarantine_evidence_ids=receipt.quarantine_evidence_ids,
        supersedes_receipt_ids=receipt.supersedes_receipt_ids,
        previous_receipt_id=receipt.previous_receipt_id,
        compensates_receipt_id=receipt.compensates_receipt_id,
    )
    expected = content_id("entity_binding_receipt", payload)
    if receipt.receipt_id != expected:
        raise ValueError("receipt_id does not bind the canonical receipt payload")


def _identity_key(receipt: EntityBindingReceiptV1) -> tuple[str, str, str]:
    return (
        receipt.mention_role_id,
        receipt.evidence_selector_id,
        receipt.local_entity_anchor_id,
    )


def _validate_lineage(
    receipts: tuple[EntityBindingReceiptV1, ...],
) -> tuple[dict[str, tuple[EntityBindingReceiptV1, ...]], set[str], set[str], set[str]]:
    by_id = {item.receipt_id: item for item in receipts}
    by_role: dict[str, list[EntityBindingReceiptV1]] = {}
    retired_ids: set[str] = set()
    compensated_ids: set[str] = set()

    for receipt in receipts:
        by_role.setdefault(receipt.mention_role_id, []).append(receipt)
        for ref_name, ref_id in (
            ("previous", receipt.previous_receipt_id),
            ("compensates", receipt.compensates_receipt_id),
            *(("supersedes", item) for item in receipt.supersedes_receipt_ids),
        ):
            if ref_id is None:
                continue
            target = by_id.get(ref_id)
            if target is None:
                raise BindingLedgerError(f"dangling {ref_name} receipt: {ref_id}")
            if _identity_key(target) != _identity_key(receipt):
                raise BindingLedgerError(
                    f"{ref_name} receipt crosses mention/evidence/local identity"
                )
        if receipt.previous_receipt_id is not None:
            retired_ids.add(receipt.previous_receipt_id)
        retired_ids.update(receipt.supersedes_receipt_ids)
        if receipt.compensates_receipt_id is not None:
            compensated_ids.add(receipt.compensates_receipt_id)

    def dependency_ids(receipt: EntityBindingReceiptV1) -> tuple[str, ...]:
        previous = (
            (receipt.previous_receipt_id,)
            if receipt.previous_receipt_id is not None else ()
        )
        return previous + receipt.supersedes_receipt_ids

    branch_roles: set[str] = set()
    canonical_groups: dict[str, tuple[EntityBindingReceiptV1, ...]] = {}
    for role_id, group in by_role.items():
        ordered = tuple(sorted(group, key=lambda item: item.receipt_id))
        if len({_identity_key(item) for item in ordered}) != 1:
            raise BindingLedgerError("one mention_role_id has conflicting identity")

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(receipt_id: str) -> None:
            if receipt_id in visiting:
                raise BindingLedgerError("binding receipt revision cycle")
            if receipt_id in visited:
                return
            visiting.add(receipt_id)
            for dependency_id in dependency_ids(by_id[receipt_id]):
                visit(dependency_id)
            visiting.remove(receipt_id)
            visited.add(receipt_id)

        for start in ordered:
            visit(start.receipt_id)
            ancestors: set[str] = set()
            frontier = list(dependency_ids(start))
            while frontier:
                ancestor_id = frontier.pop()
                if ancestor_id in ancestors:
                    continue
                ancestors.add(ancestor_id)
                frontier.extend(dependency_ids(by_id[ancestor_id]))
            if start.compensates_receipt_id is not None:
                if start.compensates_receipt_id not in ancestors:
                    raise BindingLedgerError(
                        "compensation must target an ancestor in the revision chain"
                    )

        referenced = {
            ref_id
            for item in ordered
            for ref_id in dependency_ids(item)
        }
        heads = tuple(item for item in ordered if item.receipt_id not in referenced)
        if not heads:
            raise BindingLedgerError("binding receipt lineage has no head")
        if len(heads) > 1:
            branch_roles.add(role_id)
        canonical_groups[role_id] = heads

    return canonical_groups, retired_ids, compensated_ids, branch_roles


def _member_state(
    active: tuple[EntityBindingReceiptV1, ...],
    *,
    branch_conflict: bool,
) -> tuple[CanonicalMemberState, str | None, str | None]:
    if not active:
        return CanonicalMemberState.UNOBSERVED, None, None
    decisions = {item.decision for item in active}
    targets = {
        item.selected_target_id
        for item in active if item.decision is BindingDecision.ACCEPTED
    }
    qids = {
        item.external_qid for item in active if item.external_qid is not None
    }
    if (
        not branch_conflict
        and decisions == {BindingDecision.ACCEPTED}
        and len(targets) == 1
        and len(qids) <= 1
    ):
        return CanonicalMemberState.ACCEPTED, next(iter(targets)), (
            next(iter(qids)) if qids else None
        )
    if decisions == {BindingDecision.REJECTED} and not branch_conflict:
        return CanonicalMemberState.REJECTED, None, None
    if decisions == {BindingDecision.QUARANTINED} and not branch_conflict:
        return CanonicalMemberState.QUARANTINED, None, None
    return CanonicalMemberState.AMBIGUOUS, None, None


def _view_payload(
    *,
    policy_id: str,
    source_root_sha256: str,
    receipt_root_sha256: str,
    local_entity_anchors: tuple[LocalEntityAnchorV1, ...],
    receipts: tuple[EntityBindingReceiptV1, ...],
    members: tuple[CanonicalEntityMemberV1, ...],
    clusters: tuple[CanonicalEntityClusterV1, ...],
    superseded_receipt_ids: tuple[str, ...],
    compensated_receipt_ids: tuple[str, ...],
    ambiguous_receipt_ids: tuple[str, ...],
    rejected_receipt_ids: tuple[str, ...],
    quarantined_receipt_ids: tuple[str, ...],
) -> dict[str, object]:
    return {
        "schema_version": VIEW_SCHEMA_VERSION,
        "policy_id": policy_id,
        "source_root_sha256": source_root_sha256,
        "receipt_root_sha256": receipt_root_sha256,
        "local_entity_anchors": local_entity_anchors,
        "receipts": receipts,
        "members": members,
        "clusters": clusters,
        "superseded_receipt_ids": superseded_receipt_ids,
        "compensated_receipt_ids": compensated_receipt_ids,
        "ambiguous_receipt_ids": ambiguous_receipt_ids,
        "rejected_receipt_ids": rejected_receipt_ids,
        "quarantined_receipt_ids": quarantined_receipt_ids,
    }


def build_canonical_entity_view(
    receipts: Iterable[EntityBindingReceiptV1],
    *,
    local_entity_anchors: Iterable[LocalEntityAnchorV1],
    source_snapshots: Iterable[SourceSnapshotV1],
    policy_id: str = "reversible-canonical-view/v1",
) -> CanonicalEntityViewV1:
    """Fold one immutable ledger cut without deleting unresolved material.

    Independent anchors with accepted receipts may share a projected canonical
    entity.  Any branch, conflicting target, ambiguous outcome, or quarantine
    stays a local singleton while unrelated accepted anchors remain usable.
    """

    _require_text("view policy_id", policy_id)
    _reject_string_iterable("receipts", receipts)
    _reject_string_iterable("local_entity_anchors", local_entity_anchors)
    _reject_string_iterable("source_snapshots", source_snapshots)

    source_by_id: dict[str, SourceSnapshotV1] = {}
    for source in source_snapshots:
        _validate_source_snapshot(source)
        prior_source = source_by_id.get(source.source_id)
        if prior_source is not None and prior_source != source:
            raise BindingLedgerError("duplicate source ID has different payload")
        source_by_id[source.source_id] = source
    ordered_sources = tuple(sorted(
        source_by_id.values(), key=lambda item: item.source_id,
    ))

    anchor_by_id: dict[str, LocalEntityAnchorV1] = {}
    role_to_anchor: dict[str, str] = {}
    for anchor in local_entity_anchors:
        source = source_by_id.get(anchor.source_id)
        if source is None:
            raise BindingLedgerError(
                f"local anchor has no frozen source: {anchor.source_id}"
            )
        verify_local_entity_anchor(anchor, source)
        prior_anchor = anchor_by_id.get(anchor.local_entity_anchor_id)
        if prior_anchor is not None and prior_anchor != anchor:
            raise BindingLedgerError("duplicate local anchor ID has different payload")
        prior_role_anchor = role_to_anchor.get(anchor.mention_role_id)
        if prior_role_anchor is not None and prior_role_anchor != anchor.local_entity_anchor_id:
            raise BindingLedgerError("mention role is bound to multiple local anchors")
        anchor_by_id[anchor.local_entity_anchor_id] = anchor
        role_to_anchor[anchor.mention_role_id] = anchor.local_entity_anchor_id
    ordered_anchors = tuple(sorted(
        anchor_by_id.values(), key=lambda item: item.local_entity_anchor_id,
    ))

    by_id: dict[str, EntityBindingReceiptV1] = {}
    for receipt in receipts:
        validate_binding_receipt(receipt)
        anchor = anchor_by_id.get(receipt.local_entity_anchor_id)
        if anchor is None:
            raise BindingLedgerError(
                f"receipt has no immutable local anchor: {receipt.local_entity_anchor_id}"
            )
        if (
            receipt.mention_role_id != anchor.mention_role_id
            or receipt.evidence_selector_id != anchor.evidence_selector_id
        ):
            raise BindingLedgerError(
                "receipt role/selector does not match its immutable local anchor"
            )
        prior = by_id.get(receipt.receipt_id)
        if prior is not None and prior != receipt:
            raise BindingLedgerError("duplicate receipt ID has different payload")
        by_id[receipt.receipt_id] = receipt
    ordered = tuple(sorted(by_id.values(), key=lambda item: item.receipt_id))

    active_groups, previous_ids, compensated_ids, branch_roles = _validate_lineage(ordered)
    history_by_anchor: dict[str, list[EntityBindingReceiptV1]] = {}
    active_by_anchor: dict[str, list[EntityBindingReceiptV1]] = {}
    branch_anchors: set[str] = set()
    for receipt in ordered:
        history_by_anchor.setdefault(receipt.local_entity_anchor_id, []).append(receipt)
    for role_id, heads in active_groups.items():
        anchor_id = heads[0].local_entity_anchor_id
        active_by_anchor.setdefault(anchor_id, []).extend(heads)
        if role_id in branch_roles:
            branch_anchors.add(anchor_id)

    preliminary: dict[
        str,
        tuple[
            CanonicalMemberState,
            str | None,
            str | None,
            tuple[EntityBindingReceiptV1, ...],
            tuple[EntityBindingReceiptV1, ...],
        ],
    ] = {}
    for anchor_id in sorted(anchor_by_id):
        active = tuple(sorted(
            active_by_anchor.get(anchor_id, ()), key=lambda item: item.receipt_id,
        ))
        history = tuple(sorted(
            history_by_anchor.get(anchor_id, ()), key=lambda item: item.receipt_id,
        ))
        state, selected_target_id, external_qid = _member_state(
            active, branch_conflict=anchor_id in branch_anchors,
        )
        preliminary[anchor_id] = (
            state, selected_target_id, external_qid, active, history,
        )

    target_anchors: dict[str, list[str]] = {}
    for anchor_id, (state, target, _qid, _active, _history) in preliminary.items():
        if state is CanonicalMemberState.ACCEPTED and target is not None:
            target_anchors.setdefault(target, []).append(anchor_id)
    cluster_conflicts: set[str] = set()
    for anchor_ids in target_anchors.values():
        active = tuple(
            receipt
            for anchor_id in anchor_ids
            for receipt in preliminary[anchor_id][3]
        )
        entity_types = {
            candidate.entity_type
            for receipt in active
            for candidate in receipt.candidate_set
            if candidate.target_id == receipt.selected_target_id
        }
        policy_profiles = {
            (receipt.policy_id, receipt.thresholds_digest) for receipt in active
        }
        external_qids = {
            receipt.external_qid
            for receipt in active if receipt.external_qid is not None
        }
        if (
            len(entity_types) != 1
            or len(policy_profiles) != 1
            or len(external_qids) > 1
        ):
            cluster_conflicts.update(anchor_ids)

    members: list[CanonicalEntityMemberV1] = []
    for anchor_id in sorted(anchor_by_id):
        state, selected_target_id, external_qid, active, history = preliminary[anchor_id]
        if anchor_id in cluster_conflicts:
            state = CanonicalMemberState.AMBIGUOUS
            selected_target_id = None
            external_qid = None
        if state is CanonicalMemberState.ACCEPTED:
            canonical_entity_id = content_id("canonical_entity", {
                "policy_id": policy_id,
                "selected_target_id": selected_target_id,
            })
        else:
            canonical_entity_id = content_id("canonical_entity_local", {
                "policy_id": policy_id,
                "local_entity_anchor_id": anchor_id,
            })
        members.append(CanonicalEntityMemberV1(
            local_entity_anchor_id=anchor_id,
            canonical_entity_id=canonical_entity_id,
            state=state,
            selected_target_id=selected_target_id,
            external_qid=external_qid,
            active_receipt_ids=tuple(item.receipt_id for item in active),
            history_receipt_ids=tuple(item.receipt_id for item in history),
        ))

    cluster_members: dict[str, list[CanonicalEntityMemberV1]] = {}
    for member in members:
        cluster_members.setdefault(member.canonical_entity_id, []).append(member)
    clusters: list[CanonicalEntityClusterV1] = []
    for canonical_entity_id, group in sorted(cluster_members.items()):
        ordered_group = tuple(sorted(
            group, key=lambda item: item.local_entity_anchor_id,
        ))
        targets = {
            item.selected_target_id
            for item in ordered_group if item.selected_target_id is not None
        }
        clusters.append(CanonicalEntityClusterV1(
            canonical_entity_id=canonical_entity_id,
            selected_target_id=next(iter(targets)) if len(targets) == 1 else None,
            local_entity_anchor_ids=tuple(
                item.local_entity_anchor_id for item in ordered_group
            ),
            active_receipt_ids=tuple(sorted(
                receipt_id
                for item in ordered_group for receipt_id in item.active_receipt_ids
            )),
            external_qids=tuple(sorted({
                item.external_qid
                for item in ordered_group if item.external_qid is not None
            })),
        ))

    member_by_anchor = {item.local_entity_anchor_id: item for item in members}
    active_receipts = {
        receipt_id: by_id[receipt_id]
        for member in members for receipt_id in member.active_receipt_ids
    }

    def active_ids_for(state: CanonicalMemberState) -> tuple[str, ...]:
        return tuple(sorted(
            receipt_id
            for receipt_id, receipt in active_receipts.items()
            if member_by_anchor[receipt.local_entity_anchor_id].state is state
        ))

    receipt_root_sha256 = sha256_text(canonical_json(ordered))
    source_root_sha256 = sha256_text(canonical_json(ordered_sources))
    canonical_members = tuple(members)
    canonical_clusters = tuple(clusters)
    view_fields = {
        "policy_id": policy_id,
        "source_root_sha256": source_root_sha256,
        "receipt_root_sha256": receipt_root_sha256,
        "local_entity_anchors": ordered_anchors,
        "receipts": ordered,
        "members": canonical_members,
        "clusters": canonical_clusters,
        "superseded_receipt_ids": tuple(sorted(previous_ids)),
        "compensated_receipt_ids": tuple(sorted(compensated_ids)),
        "ambiguous_receipt_ids": active_ids_for(CanonicalMemberState.AMBIGUOUS),
        "rejected_receipt_ids": active_ids_for(CanonicalMemberState.REJECTED),
        "quarantined_receipt_ids": active_ids_for(CanonicalMemberState.QUARANTINED),
    }
    payload = _view_payload(**view_fields)
    return CanonicalEntityViewV1(
        schema_version=VIEW_SCHEMA_VERSION,
        snapshot_id=content_id("canonical_entity_view", payload),
        **view_fields,
    )


def verify_canonical_entity_view(
    view: CanonicalEntityViewV1,
    *,
    source_snapshots: Iterable[SourceSnapshotV1],
) -> None:
    """Recompute the complete view from its preserved receipt ledger."""

    rebuilt = build_canonical_entity_view(
        view.receipts,
        local_entity_anchors=view.local_entity_anchors,
        source_snapshots=source_snapshots,
        policy_id=view.policy_id,
    )
    if rebuilt != view:
        raise BindingLedgerError("canonical entity view does not replay exactly")


def member_by_local_anchor(
    view: CanonicalEntityViewV1,
    local_entity_anchor_id: str,
) -> CanonicalEntityMemberV1:
    """Resolve one local anchor without falling through to a guessed entity."""

    for member in view.members:
        if member.local_entity_anchor_id == local_entity_anchor_id:
            return member
    raise KeyError(local_entity_anchor_id)


def receipt_by_id(
    view: CanonicalEntityViewV1,
    receipt_id: str,
) -> EntityBindingReceiptV1:
    for receipt in view.receipts:
        if receipt.receipt_id == receipt_id:
            return receipt
    raise KeyError(receipt_id)
