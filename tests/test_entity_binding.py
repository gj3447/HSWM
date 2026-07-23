from __future__ import annotations

from dataclasses import replace

import pytest

import entity_binding as eb
from world_ir import canonical_json, make_source_snapshot


H0 = "0" * 64
H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64
H4 = "4" * 64
_DANGLING_RECEIPT_ID = "hswm:entity_binding_receipt:v1:" + "f" * 64


def _anchor(
    role: str,
    *,
    surface: str = "Alice",
    locator: str | None = None,
) -> tuple[object, eb.LocalEntityAnchorV1]:
    source = make_source_snapshot(
        locator or f"fixture://{role}", f"{surface} appears in exact evidence."
    )
    anchor = eb.make_local_entity_anchor(
        source=source,
        mention_role_id=role,
        evidence_selector_id=f"selector:{role}",
        start=0,
        end=len(surface),
        exact=surface,
    )
    return source, anchor


def _candidate(
    target_id: str,
    *,
    rank: int = 1,
    score: float = 0.9,
    entity_type: str = "person",
    response_sha256: str = H2,
) -> eb.BindingCandidateV1:
    return eb.BindingCandidateV1(
        target_id=target_id,
        score=score,
        rank=rank,
        entity_type=entity_type,
        response_sha256=response_sha256,
    )


def _receipt(
    anchor: eb.LocalEntityAnchorV1,
    *,
    target: str | None = "Q42",
    decision: eb.BindingDecision | str = eb.BindingDecision.ACCEPTED,
    entity_type: str = "person",
    external_qid: str | None | object = Ellipsis,
    candidates: tuple[eb.BindingCandidateV1, ...] | None = None,
    output_sha256: str = H1,
    policy_id: str = "fixture-policy/v1",
    thresholds_digest: str = H2,
    previous: str | None = None,
    supersedes: tuple[str, ...] = (),
    compensates: str | None = None,
) -> eb.EntityBindingReceiptV1:
    canonical_decision = eb.BindingDecision(decision)
    qid = (
        target if external_qid is Ellipsis and target and target.startswith("Q")
        else None if external_qid is Ellipsis
        else external_qid
    )
    assert qid is None or isinstance(qid, str)
    if candidates is None:
        built: list[eb.BindingCandidateV1] = []
        if target is not None:
            built.append(_candidate(target, entity_type=entity_type))
        if qid is not None and qid != target:
            built.append(_candidate(
                qid,
                rank=len(built) + 1,
                score=0.8,
                entity_type=entity_type,
                response_sha256=H3,
            ))
        candidates = tuple(built)
    quarantine_ids = (
        (f"quarantine:{anchor.mention_role_id}",)
        if canonical_decision is eb.BindingDecision.QUARANTINED else ()
    )
    return eb.make_binding_receipt(
        mention_role_id=anchor.mention_role_id,
        evidence_selector_id=anchor.evidence_selector_id,
        local_entity_anchor_id=anchor.local_entity_anchor_id,
        candidates=candidates,
        selected_target_id=(
            target if canonical_decision is eb.BindingDecision.ACCEPTED else None
        ),
        external_qid=(
            qid if canonical_decision is eb.BindingDecision.ACCEPTED else None
        ),
        resolver="fixture-linker",
        model_revision="fixture-v1",
        resolver_revision_sha256=H3,
        model_revision_sha256=H3,
        config_sha256=H0,
        output_sha256=output_sha256,
        policy_id=policy_id,
        thresholds_digest=thresholds_digest,
        decision=canonical_decision,
        decision_reason=f"fixture_{canonical_decision.value}",
        decision_detail_sha256=H0,
        quarantine_evidence_ids=quarantine_ids,
        supersedes_receipt_ids=supersedes,
        previous_receipt_id=previous,
        compensates_receipt_id=compensates,
    )


def _view(
    receipts: tuple[eb.EntityBindingReceiptV1, ...],
    pairs: tuple[tuple[object, eb.LocalEntityAnchorV1], ...],
    *,
    policy_id: str = "reversible-canonical-view/v1",
) -> eb.CanonicalEntityViewV1:
    return eb.build_canonical_entity_view(
        receipts,
        local_entity_anchors=tuple(anchor for _source, anchor in pairs),
        source_snapshots=tuple(source for source, _anchor_value in pairs),
        policy_id=policy_id,
    )


def _member(
    view: eb.CanonicalEntityViewV1,
    anchor: eb.LocalEntityAnchorV1,
) -> eb.CanonicalEntityMemberV1:
    return eb.member_by_local_anchor(view, anchor.local_entity_anchor_id)


def test_golden_evidence_anchor_receipt_and_view_hashes_are_stable() -> None:
    source = make_source_snapshot("fixture://alice", "Alice wrote a book.")
    anchor = eb.make_local_entity_anchor(
        source=source,
        mention_role_id="role:alice",
        evidence_selector_id="selector:alice",
        start=0,
        end=5,
        exact="Alice",
    )
    receipt = eb.make_binding_receipt(
        mention_role_id=anchor.mention_role_id,
        evidence_selector_id=anchor.evidence_selector_id,
        local_entity_anchor_id=anchor.local_entity_anchor_id,
        candidates=(_candidate("Q42", score=0.875),),
        selected_target_id="Q42",
        external_qid="Q42",
        resolver="fixture-linker",
        model_revision="fixture-v1",
        resolver_revision_sha256=H3,
        model_revision_sha256=H3,
        config_sha256=H0,
        output_sha256=H1,
        policy_id="fixture-policy/v1",
        thresholds_digest=H2,
        decision="accepted",
        decision_reason="unique_high_confidence",
        decision_detail_sha256=H0,
    )
    assert anchor.local_entity_anchor_id == (
        "hswm:local_entity_anchor:v1:"
        "69302a96883526cb918d9b9d2f13a496fa1ea1046c4385ab38befa4f4f46160b"
    )
    assert receipt.receipt_id == (
        "hswm:entity_binding_receipt:v1:"
        "c2fd5239846a8b36ca1361cb5b75b5c95550e58b6a46a9731c58c5caafb42a72"
    )
    assert '"decision_reason":"unique_high_confidence"' in canonical_json(receipt)
    assert '"quarantine_evidence_ids":[]' in canonical_json(receipt)

    view = eb.build_canonical_entity_view(
        (receipt,),
        local_entity_anchors=(anchor,),
        source_snapshots=(source,),
        policy_id="fixture-view/v1",
    )
    assert view.source_root_sha256 == (
        "025da547c1baa7e04fb90dc9ce3610cc851c0e4734f32f469aa4c7e0e7ba15a3"
    )
    assert view.receipt_root_sha256 == (
        "eda09ae993985615167ccd069c5cd436a479a949ac1b2899f7e00bac2ae269ee"
    )
    assert view.snapshot_id == (
        "hswm:canonical_entity_view:v1:"
        "b9477209f70f464042e36d231e4e3655abd148c741778210ed7896fac1493ed9"
    )
    eb.verify_canonical_entity_view(view, source_snapshots=(source,))


def test_accepted_subset_operates_while_unresolved_material_is_preserved() -> None:
    accepted_pair = _anchor("role:accepted", surface="Alice")
    ambiguous_pair = _anchor("role:ambiguous", surface="A. Lee")
    quarantined_pair = _anchor("role:quarantined", surface="she")
    unobserved_pair = _anchor("role:unobserved", surface="unknown")
    accepted = _receipt(accepted_pair[1])
    ambiguous = _receipt(
        ambiguous_pair[1],
        target=None,
        decision="ambiguous",
        candidates=(
            _candidate("Q42", rank=1, score=0.51),
            _candidate("Q99", rank=2, score=0.49, response_sha256=H3),
        ),
    )
    quarantined = _receipt(
        quarantined_pair[1],
        target=None,
        decision="quarantined",
        candidates=(),
        output_sha256=H3,
    )
    pairs = (
        accepted_pair, ambiguous_pair, quarantined_pair, unobserved_pair,
    )
    view = _view((quarantined, accepted, ambiguous), pairs)

    assert _member(view, accepted_pair[1]).state == "accepted"
    assert _member(view, ambiguous_pair[1]).state == "ambiguous"
    assert _member(view, quarantined_pair[1]).state == "quarantined"
    assert _member(view, unobserved_pair[1]).state == "unobserved"
    assert ambiguous.receipt_id in view.ambiguous_receipt_ids
    assert quarantined.receipt_id in view.quarantined_receipt_ids
    assert {item.receipt_id for item in view.receipts} == {
        accepted.receipt_id, ambiguous.receipt_id, quarantined.receipt_id,
    }
    eb.verify_canonical_entity_view(
        view, source_snapshots=tuple(pair[0] for pair in pairs)
    )


def test_compatible_accepted_anchors_share_only_a_reversible_projection() -> None:
    alice_pair = _anchor("role:alice", surface="Alice")
    alias_pair = _anchor("role:alias", surface="A. Lee")
    alice = _receipt(alice_pair[1])
    alias = _receipt(alias_pair[1])
    pairs = (alice_pair, alias_pair)

    view = _view((alias, alice), pairs)
    assert _member(view, alice_pair[1]).canonical_entity_id == (
        _member(view, alias_pair[1]).canonical_entity_id
    )
    cluster = next(item for item in view.clusters if item.selected_target_id == "Q42")
    assert set(cluster.local_entity_anchor_ids) == {
        alice_pair[1].local_entity_anchor_id,
        alias_pair[1].local_entity_anchor_id,
    }
    assert _view((alice, alias), pairs) == view


@pytest.mark.parametrize("conflict", ["type", "qid", "policy"])
def test_cluster_conflicts_abstain_instead_of_destructive_union(conflict: str) -> None:
    left_pair = _anchor(f"role:{conflict}:left", surface="Alice")
    right_pair = _anchor(f"role:{conflict}:right", surface="A. Lee")
    left_kwargs: dict[str, object] = {}
    right_kwargs: dict[str, object] = {}
    target = "Q42"
    if conflict == "type":
        right_kwargs["entity_type"] = "organization"
    elif conflict == "qid":
        target = "local:shared-person"
        left_kwargs["external_qid"] = "Q42"
        right_kwargs["external_qid"] = "Q99"
    else:
        right_kwargs["policy_id"] = "different-policy/v1"

    left = _receipt(left_pair[1], target=target, **left_kwargs)
    right = _receipt(right_pair[1], target=target, **right_kwargs)
    view = _view((left, right), (left_pair, right_pair))

    assert _member(view, left_pair[1]).state == "ambiguous"
    assert _member(view, right_pair[1]).state == "ambiguous"
    assert _member(view, left_pair[1]).canonical_entity_id != (
        _member(view, right_pair[1]).canonical_entity_id
    )
    assert set(view.ambiguous_receipt_ids) == {left.receipt_id, right.receipt_id}


def test_compensation_unmerges_only_the_revised_anchor_and_keeps_history() -> None:
    alice_pair = _anchor("role:alice", surface="Alice")
    alias_pair = _anchor("role:alias", surface="A. Lee")
    alice = _receipt(alice_pair[1])
    alias = _receipt(alias_pair[1])
    pairs = (alice_pair, alias_pair)
    merged = _view((alice, alias), pairs)

    correction = _receipt(
        alias_pair[1],
        target=None,
        decision="rejected",
        candidates=(_candidate("Q42"),),
        output_sha256=H4,
        previous=alias.receipt_id,
        compensates=alias.receipt_id,
    )
    corrected = _view((correction, alice, alias), pairs)

    assert _member(corrected, alice_pair[1]).state == "accepted"
    assert _member(corrected, alias_pair[1]).state == "rejected"
    assert _member(corrected, alice_pair[1]).canonical_entity_id != (
        _member(corrected, alias_pair[1]).canonical_entity_id
    )
    assert alias.receipt_id in corrected.superseded_receipt_ids
    assert alias.receipt_id in corrected.compensated_receipt_ids
    assert alias.receipt_id in _member(
        corrected, alias_pair[1]
    ).history_receipt_ids
    assert _view((alias, alice), pairs) == merged


def test_concurrent_revision_heads_abstain_and_preserve_both() -> None:
    pair = _anchor("role:branch", surface="Alice")
    root = _receipt(pair[1], target="Q42")
    left = _receipt(
        pair[1], target="Q42", output_sha256=H2, previous=root.receipt_id
    )
    right = _receipt(
        pair[1], target="Q99", output_sha256=H3, previous=root.receipt_id
    )
    view = _view((right, root, left), (pair,))
    member = _member(view, pair[1])

    assert member.state == "ambiguous"
    assert member.selected_target_id is None
    assert set(member.active_receipt_ids) == {left.receipt_id, right.receipt_id}
    assert root.receipt_id in member.history_receipt_ids


def test_concurrent_heads_can_be_reconciled_without_deleting_either_branch() -> None:
    pair = _anchor("role:reconciled", surface="Alice")
    root = _receipt(pair[1], target="Q42")
    left = _receipt(
        pair[1], target="Q42", output_sha256=H2, previous=root.receipt_id
    )
    right = _receipt(
        pair[1], target="Q99", output_sha256=H3, previous=root.receipt_id
    )
    resolution = _receipt(
        pair[1],
        target="Q84",
        output_sha256=H4,
        previous=left.receipt_id,
        supersedes=(right.receipt_id,),
    )

    view = _view((right, resolution, root, left), (pair,))
    member = _member(view, pair[1])

    assert member.state == "accepted"
    assert member.selected_target_id == "Q84"
    assert member.active_receipt_ids == (resolution.receipt_id,)
    assert set(member.history_receipt_ids) == {
        root.receipt_id,
        left.receipt_id,
        right.receipt_id,
        resolution.receipt_id,
    }
    assert {left.receipt_id, right.receipt_id}.issubset(
        view.superseded_receipt_ids
    )


def test_qid_target_and_external_qid_cannot_contradict_each_other() -> None:
    _source, anchor = _anchor("role:qid-mismatch", surface="Alice")
    with pytest.raises(ValueError, match="QID selected_target_id"):
        _receipt(anchor, target="Q42", external_qid="Q99")


def test_frozen_anchor_catalog_rejects_missing_or_forged_evidence() -> None:
    source, anchor = _anchor("role:bound", surface="Alice")
    receipt = _receipt(anchor)
    with pytest.raises(eb.BindingLedgerError, match="no immutable local anchor"):
        eb.build_canonical_entity_view(
            (receipt,), local_entity_anchors=(), source_snapshots=(source,)
        )
    with pytest.raises(eb.BindingLedgerError, match="no frozen source"):
        eb.build_canonical_entity_view(
            (receipt,), local_entity_anchors=(anchor,), source_snapshots=()
        )
    with pytest.raises(ValueError, match="does not bind selector evidence"):
        forged = replace(anchor, exact="Alicf")
        eb.build_canonical_entity_view(
            (receipt,), local_entity_anchors=(forged,), source_snapshots=(source,)
        )

    other_source, other_anchor = _anchor(
        "role:bound", surface="Different", locator="fixture://other"
    )
    with pytest.raises(eb.BindingLedgerError, match="multiple local anchors"):
        eb.build_canonical_entity_view(
            (),
            local_entity_anchors=(anchor, other_anchor),
            source_snapshots=(source, other_source),
        )


def test_text_is_never_silently_treated_as_a_record_iterable() -> None:
    with pytest.raises(TypeError, match="not text"):
        eb.build_canonical_entity_view(
            (), local_entity_anchors="anchor", source_snapshots=()
        )
    with pytest.raises(TypeError, match="not text"):
        eb.build_canonical_entity_view(
            "receipt", local_entity_anchors=(), source_snapshots=()
        )
    with pytest.raises(TypeError, match="not text"):
        eb.build_canonical_entity_view(
            (), local_entity_anchors=(), source_snapshots="source"
        )


def test_receipt_shape_and_lineage_fail_closed() -> None:
    pair = _anchor("role:shape", surface="Alice")
    with pytest.raises(ValueError, match="finite"):
        _candidate("Q42", score=float("nan"))
    with pytest.raises(ValueError, match="contiguous"):
        _receipt(
            pair[1],
            target=None,
            decision="ambiguous",
            candidates=(_candidate("Q42", rank=2),),
        )
    with pytest.raises(ValueError, match="quarantine evidence"):
        eb.make_binding_receipt(
            mention_role_id=pair[1].mention_role_id,
            evidence_selector_id=pair[1].evidence_selector_id,
            local_entity_anchor_id=pair[1].local_entity_anchor_id,
            resolver="fixture",
            model_revision="v1",
            resolver_revision_sha256=H3,
            model_revision_sha256=H3,
            config_sha256=H0,
            output_sha256=H1,
            policy_id="p1",
            thresholds_digest=H2,
            decision="quarantined",
            decision_reason="resolver_failure",
            decision_detail_sha256=H4,
        )

    dangling = _receipt(
        pair[1],
        target=None,
        decision="rejected",
        previous=_DANGLING_RECEIPT_ID,
    )
    with pytest.raises(eb.BindingLedgerError, match="dangling previous"):
        _view((dangling,), (pair,))

    valid = _receipt(pair[1])
    with pytest.raises(ValueError, match="receipt_id does not bind"):
        replace(valid, output_sha256=H4)
