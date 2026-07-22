"""Deterministic identity/claim weave arms — H3-C0 successor builder factorial.

H3-C0 root cause #2: "Builder material: insufficient for composition.  Alias
fragmentation, absent canonical entity identity, ambiguous quote selectors,
and missing subject-to-next-argument continuity prevent three-node claim
chains."  This module adds exactly that material as NEW arcs layered on the
frozen compiled build — the compiler itself is untouched, every woven arc
carries both endpoint exact spans plus a reversible weave receipt, and no
model, network, clock, or randomness is consumed.

Arms (deterministic sub-lane of the H3-C0 recommendation; the ReFinED-QID /
fastcoref ML lane is explicitly NOT implemented here):

  C1  exact title-to-claim-subject weave.  A title-terminal arc may continue
      into a target-paragraph claim whose subject surface exactly equals the
      normalized title.  Both the title selector and the body-subject
      selector are preserved in the weave receipt.  (H3-C0 counterfactual
      already published: MuSiQue +0 chains, 2Wiki 15 structural chains.)
  C2  canonical entity identity.  A paragraph title is a canonical anchor;
      its parenthetical disambiguator is stripped deterministically
      ("Polish-Russian War (film)" -> "polish-russian war").  A claim
      argument that exactly matches a canonical anchor resolves to that
      canonical entity, and cross-paragraph argument->subject arcs are woven
      between claims resolving to the same canonical entity.
  C3  C2 plus sibling-subject handoff: two claims (different paragraphs)
      whose subjects resolve to the SAME canonical entity hand off to each
      other — the deterministic stand-in for a coreference receipt.  A
      literal same-paragraph handoff cannot exist as a standalone arc (the
      frozen dataclass forbids self-ordinal arcs), so the intra-paragraph
      lane of the H3-C0 recommendation remains NOT implemented here.

Reversibility: every woven arc id is content-addressed and listed in a
``WeaveReceiptV1`` with rule name, both spans, and canonical key; removing
all arcs whose ``origin`` starts with ``woven_`` restores the frozen graph
bit-exactly (tested).
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
import unicodedata

from claim_builder import ArgumentRoleV1, ClaimGraphBuildV1, NaryClaimV1
from typed_composition import (
    SelectorSpanV1,
    TypedCompositionGraphV1,
    TypedEvidenceArcV1,
    make_typed_graph,
)

_PARENTHETICAL_RE = re.compile(r"\s*\([^)]*\)\s*$")


def normalize_surface(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold().strip()


def canonical_title_key(title: str) -> str:
    """Strip one trailing parenthetical disambiguator, then normalize."""
    return normalize_surface(_PARENTHETICAL_RE.sub("", title))


@dataclass(frozen=True)
class WeaveReceiptV1:
    """Reversible audit evidence for one woven arc."""

    arc_id: str
    rule: str                    # "c1_title_subject" | "c2_canonical_entity" | "c3_sibling_subject_handoff"
    canonical_key: str
    left_source_id: str
    left_role_id: str
    left_exact: str
    right_source_id: str
    right_role_id: str
    right_exact: str

    def payload(self) -> dict:
        return {
            "arc_id": self.arc_id, "rule": self.rule,
            "canonical_key": self.canonical_key,
            "left_source_id": self.left_source_id,
            "left_role_id": self.left_role_id, "left_exact": self.left_exact,
            "right_source_id": self.right_source_id,
            "right_role_id": self.right_role_id, "right_exact": self.right_exact,
        }


@dataclass(frozen=True)
class WeaveResultV1:
    arcs: tuple[TypedEvidenceArcV1, ...]
    receipts: tuple[WeaveReceiptV1, ...]


def _selector(role: ArgumentRoleV1) -> SelectorSpanV1:
    return SelectorSpanV1(
        source_id=role.source_id,
        role_id=role.role_id,
        role=role.role,
        text_scope="body",
        start=role.start,
        end=role.end,
        exact=role.exact,
        source_text_sha256=role.source_text_sha256,
    )


def _arc_id(rule: str, left_role_id: str, right_role_id: str) -> str:
    raw = json.dumps({"rule": rule, "left": left_role_id, "right": right_role_id},
                     sort_keys=True, separators=(",", ":")).encode()
    return f"woven:{rule}:{sha256(raw).hexdigest()[:24]}"


def _woven_arc(
    rule: str,
    ordinals: dict[str, int],
    source_claim: NaryClaimV1,
    left_role: ArgumentRoleV1,
    target_claim: NaryClaimV1,
    join_key: str,
) -> tuple[TypedEvidenceArcV1, WeaveReceiptV1] | None:
    source_id = source_claim.source_id
    target_id = target_claim.source_id
    # The typed arc dataclass forbids source_target == target_target, so a
    # literal intra-paragraph handoff cannot exist as a standalone arc; the
    # handoff lane is therefore woven only across paragraphs (see weave_c3).
    if source_id == target_id:
        return None
    arc_id = _arc_id(rule, left_role.role_id, target_claim.subject.role_id)
    arc = TypedEvidenceArcV1(
        arc_id=arc_id,
        source_target=ordinals[source_id],
        target_target=ordinals[target_id],
        source_id=source_id,
        target_id=target_id,
        source_claim_id=source_claim.claim_id,
        target_claim_id=target_claim.claim_id,
        source_predicate=_selector(source_claim.predicate),
        target_predicate=_selector(target_claim.predicate),
        source_argument_role=left_role.role,
        target_argument_role=target_claim.subject.role,
        join_entity_id=f"canonical:{join_key}",
        source_selector=_selector(left_role),
        target_selector=_selector(target_claim.subject),
        origin=f"woven_{rule}",
    )
    receipt = WeaveReceiptV1(
        arc_id=arc_id, rule=rule, canonical_key=join_key,
        left_source_id=source_id, left_role_id=left_role.role_id,
        left_exact=left_role.exact,
        right_source_id=target_id, right_role_id=target_claim.subject.role_id,
        right_exact=target_claim.subject.exact,
    )
    return arc, receipt


def _claims_by_subject_key(
    claims: tuple[NaryClaimV1, ...], key_fn,
) -> dict[str, list[NaryClaimV1]]:
    by_key: dict[str, list[NaryClaimV1]] = {}
    for claim in claims:
        key = key_fn(claim.subject.exact)
        if key:
            by_key.setdefault(key, []).append(claim)
    for row in by_key.values():
        row.sort(key=lambda c: c.claim_id)
    return by_key


def weave_c1(
    build: ClaimGraphBuildV1,
    titles: dict[str, str],
    base_graph: TypedCompositionGraphV1,
) -> WeaveResultV1:
    """Title-terminal -> exact same-normalized-title claim subject."""
    ordinals = {sid: i for i, sid in enumerate(base_graph.target_ids)}
    claims_by_id = {c.claim_id: c for c in build.nary_claims}
    claims_by_source: dict[str, list[NaryClaimV1]] = {}
    for claim in build.nary_claims:
        claims_by_source.setdefault(claim.source_id, []).append(claim)
    for row in claims_by_source.values():
        row.sort(key=lambda c: c.claim_id)

    arcs: list[TypedEvidenceArcV1] = []
    receipts: list[WeaveReceiptV1] = []
    seen: set[str] = set()
    for terminal in sorted(
        (a for a in base_graph.arcs if a.target_claim_id is None),
        key=lambda a: a.arc_id,
    ):
        title_key = normalize_surface(titles.get(terminal.target_id, ""))
        if not title_key:
            continue
        source_claim = claims_by_id.get(terminal.source_claim_id)
        if source_claim is None:
            continue
        left_role = next(
            (r for r in (*source_claim.arguments, source_claim.subject)
             if r.role_id == terminal.source_selector.role_id),
            None,
        )
        if left_role is None:
            continue
        for target_claim in claims_by_source.get(terminal.target_id, ()):  # exact subject == title
            if normalize_surface(target_claim.subject.exact) != title_key:
                continue
            woven = _woven_arc("c1_title_subject", ordinals, source_claim,
                               left_role, target_claim, title_key)
            if woven and woven[0].arc_id not in seen:
                seen.add(woven[0].arc_id)
                arcs.append(woven[0])
                receipts.append(woven[1])
    return WeaveResultV1(arcs=tuple(arcs), receipts=tuple(receipts))


def _canonical_anchor_map(titles: dict[str, str]) -> dict[str, str]:
    """canonical key -> anchoring paragraph id; ambiguous anchors are dropped
    (homonym guard: one canonical key must anchor exactly one paragraph)."""
    anchors: dict[str, list[str]] = {}
    for source_id in sorted(titles):
        key = canonical_title_key(titles[source_id])
        if key:
            anchors.setdefault(key, []).append(source_id)
    return {k: v[0] for k, v in anchors.items() if len(v) == 1}


def weave_c2(
    build: ClaimGraphBuildV1,
    titles: dict[str, str],
    base_graph: TypedCompositionGraphV1,
) -> WeaveResultV1:
    """Cross-paragraph argument -> subject arcs through canonical entities."""
    ordinals = {sid: i for i, sid in enumerate(base_graph.target_ids)}
    anchors = _canonical_anchor_map(titles)
    subjects = _claims_by_subject_key(
        build.nary_claims,
        lambda text: (canonical_title_key(text)
                      if canonical_title_key(text) in anchors else ""),
    )
    arcs: list[TypedEvidenceArcV1] = []
    receipts: list[WeaveReceiptV1] = []
    seen: set[str] = set()
    for claim in sorted(build.nary_claims, key=lambda c: c.claim_id):
        for role in claim.arguments:
            if role.role_id == claim.subject.role_id:
                continue
            key = canonical_title_key(role.exact)
            if key not in anchors:
                continue
            for target_claim in subjects.get(key, ()):
                woven = _woven_arc("c2_canonical_entity", ordinals, claim,
                                   role, target_claim, key)
                if woven and woven[0].arc_id not in seen:
                    seen.add(woven[0].arc_id)
                    arcs.append(woven[0])
                    receipts.append(woven[1])
    return WeaveResultV1(arcs=tuple(arcs), receipts=tuple(receipts))


def weave_c3(
    build: ClaimGraphBuildV1,
    titles: dict[str, str],
    base_graph: TypedCompositionGraphV1,
) -> WeaveResultV1:
    """C2 material plus the landed-entity -> next-claim-subject handoff woven
    as canonical-entity continuity across paragraphs (see _woven_arc note on
    why a literal same-ordinal arc cannot exist under the frozen dataclass)."""
    ordinals = {sid: i for i, sid in enumerate(base_graph.target_ids)}
    anchors = _canonical_anchor_map(titles)
    # Handoff: any claim whose subject resolves canonically may hand off to
    # any other claim (different paragraph) whose subject resolves to the
    # SAME canonical entity — sibling-subject continuity, the deterministic
    # stand-in for a coreference receipt.
    subjects = _claims_by_subject_key(
        build.nary_claims,
        lambda text: (canonical_title_key(text)
                      if canonical_title_key(text) in anchors else ""),
    )
    arcs: list[TypedEvidenceArcV1] = []
    receipts: list[WeaveReceiptV1] = []
    seen: set[str] = set()
    for key in sorted(subjects):
        row = subjects[key]
        for source_claim in row:
            for target_claim in row:
                if source_claim.claim_id == target_claim.claim_id:
                    continue
                woven = _woven_arc("c3_sibling_subject_handoff", ordinals,
                                   source_claim, source_claim.subject,
                                   target_claim, key)
                if woven and woven[0].arc_id not in seen:
                    seen.add(woven[0].arc_id)
                    arcs.append(woven[0])
                    receipts.append(woven[1])
    return WeaveResultV1(arcs=tuple(arcs), receipts=tuple(receipts))


def apply_weave(
    base_graph: TypedCompositionGraphV1,
    weaves: list[WeaveResultV1],
) -> TypedCompositionGraphV1:
    """Layer woven arcs over the frozen graph.  Frozen arcs are never edited."""
    arcs: dict[str, TypedEvidenceArcV1] = {a.arc_id: a for a in base_graph.arcs}
    for weave in weaves:
        for arc in weave.arcs:
            if arc.arc_id in arcs and arcs[arc.arc_id] != arc:
                raise ValueError(f"woven arc id collision {arc.arc_id}")
            arcs[arc.arc_id] = arc
    return make_typed_graph(
        base_graph.target_ids,
        tuple(arcs[k] for k in sorted(arcs)),
    )


def strip_weave(graph: TypedCompositionGraphV1) -> TypedCompositionGraphV1:
    """Reversibility: drop every woven arc, restoring the frozen topology."""
    return make_typed_graph(
        graph.target_ids,
        tuple(a for a in sorted(graph.arcs, key=lambda x: x.arc_id)
              if not a.origin.startswith("woven_")),
    )
