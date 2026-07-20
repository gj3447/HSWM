"""Typed, evidence-receipted relation composition research kernel.

This module answers a deliberately narrow H3 mechanism question: can a target
be promoted *only after* following two or more evidence-bound, query-compatible
claim arcs?  It is not a deployable readout and it never consumes evaluator
labels.  The only query input is raw text.

The graph adapter is intentionally duck-typed against ``claim_builder.py`` so
the compiler and this research kernel stay separate.  It accepts the final
shared-entity arc shape (two endpoint selectors plus a join entity) and the
earlier verified-title projection while that extension is landing.  Title-only
fallback arcs are excluded because they have no evidenced predicate.

Path propagation uses the max-product semiring.  Receipts retain every
predicate, both endpoint selectors, every join entity, and all intermediate
paragraph IDs.  A matched K=1 ablation is always reported for K>=2 runs.  The
local H3 necessity gate refuses PASS unless a positive target is first reached
at depth two; this is a mechanism gate, not an end-task performance claim.

Longinus ReferenceSite:
``HSWM/PROM_16_WORLD_COMPILER_CERTIFIED_READOUT_ENVELOPE_2026-07-20.md``
sections 14-18 (builder factorial, traversal re-certification, kill conditions).
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json
import math
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Literal

import numpy as np


ControlMode = Literal["typed", "untyped"]
H3Status = Literal["PASS", "REFUSED"]

_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)
_ROLE_SPLIT_RE = re.compile(r"[_:\-/]+")
_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "did", "do",
    "does", "for", "from", "how", "in", "is", "it", "of", "on", "or",
    "that", "the", "this", "to", "was", "were", "what", "when", "where",
    "which", "who", "whom", "whose", "why", "with",
})


def _digest(payload: Any) -> str:
    raw = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return sha256(raw).hexdigest()


def _score_digest(scores: np.ndarray) -> str:
    values = np.ascontiguousarray(scores, dtype=np.float64)
    return sha256(values.tobytes(order="C")).hexdigest()


def _selector_payload(selector: "SelectorSpanV1 | None") -> Any:
    if selector is None:
        return None
    return {
        "source_id": selector.source_id,
        "role_id": selector.role_id,
        "role": selector.role,
        "text_scope": selector.text_scope,
        "start": selector.start,
        "end": selector.end,
        "exact": selector.exact,
        "source_text_sha256": selector.source_text_sha256,
    }


def _normalized_words(text: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    words = []
    for raw in _WORD_RE.findall(normalized):
        if raw in _STOPWORDS:
            continue
        word = raw
        # A deliberately small morphology normalizer.  Prefix matching below
        # handles pairs such as composed/composer without a language model.
        for suffix in ("ingly", "edly", "ation", "ions", "ment", "ers", "ing", "ed", "er", "es", "s"):
            if len(word) - len(suffix) >= 4 and word.endswith(suffix):
                word = word[:-len(suffix)]
                break
        if word:
            words.append(word)
    return tuple(sorted(set(words)))


def _term_matches(left: str, right: str) -> bool:
    if left == right:
        return True
    # Relation morphology is noisy but short prefixes are dangerously broad.
    return min(len(left), len(right)) >= 5 and (
        left.startswith(right) or right.startswith(left)
    )


def _coverage(needles: tuple[str, ...], query_terms: tuple[str, ...]) -> float:
    if not needles or not query_terms:
        return 0.0
    hits = sum(
        1 for needle in needles
        if any(_term_matches(needle, query) for query in query_terms)
    )
    return float(hits) / float(len(needles))


@dataclass(frozen=True)
class SelectorSpanV1:
    """One exact source selector copied into every path receipt."""

    source_id: str
    role_id: str
    role: str
    text_scope: str
    start: int
    end: int
    exact: str
    source_text_sha256: str

    def __post_init__(self) -> None:
        if not all((self.source_id, self.role_id, self.role, self.text_scope,
                    self.exact, self.source_text_sha256)):
            raise ValueError("selector evidence fields must be non-empty")
        if self.start < 0 or self.end <= self.start:
            raise ValueError("selector must be a non-empty range")
        if self.end - self.start != len(self.exact):
            raise ValueError("selector range and exact text length disagree")
        if self.text_scope not in {"body", "title"}:
            raise ValueError("selector text_scope must be body or title")


@dataclass(frozen=True)
class TypedEvidenceArcV1:
    """One directed claim projection with typed and source-bound evidence."""

    arc_id: str
    source_target: int
    target_target: int
    source_id: str
    target_id: str
    source_claim_id: str
    target_claim_id: str | None
    source_predicate: SelectorSpanV1
    target_predicate: SelectorSpanV1 | None
    source_argument_role: str
    target_argument_role: str
    join_entity_id: str
    source_selector: SelectorSpanV1
    target_selector: SelectorSpanV1
    origin: str = "verified_claim"

    def __post_init__(self) -> None:
        if not all((self.arc_id, self.source_id, self.target_id,
                    self.source_claim_id,
                    self.source_argument_role, self.target_argument_role,
                    self.join_entity_id, self.origin)):
            raise ValueError("typed arc identity and relation fields must be non-empty")
        if self.source_target < 0 or self.target_target < 0:
            raise ValueError("target ordinals must be non-negative")
        if self.source_target == self.target_target:
            raise ValueError("self arcs are not composition evidence")
        if self.source_selector.source_id != self.source_id:
            raise ValueError("source selector is bound to a different source")
        if self.target_selector.source_id != self.target_id:
            raise ValueError("target selector is bound to a different target")
        if self.source_predicate.source_id != self.source_id:
            raise ValueError("source predicate is bound to a different source")
        if (self.target_predicate is not None and
                self.target_predicate.source_id != self.target_id):
            raise ValueError("target predicate is bound to a different target")
        if (self.target_claim_id is None) != (self.target_predicate is None):
            raise ValueError(
                "target claim and predicate must both exist, except at a title terminal"
            )
        if (self.target_claim_id is None and
                self.origin not in {"verified_nary_title", "verified_nary_claim"} and
                not self.origin.startswith("NULL_")):
            raise ValueError("only a verified title projection may be claim-terminal")


@dataclass(frozen=True)
class TypedCompositionGraphV1:
    target_ids: tuple[str, ...]
    arcs: tuple[TypedEvidenceArcV1, ...]
    topology_sha256: str
    is_null_control: bool = False

    @property
    def n_targets(self) -> int:
        return len(self.target_ids)


@dataclass(frozen=True)
class TypedCompositionPolicyV1:
    seed_k: int = 1
    max_hops: int = 2
    mu: float = 0.1
    fanout_exponent: float = 0.5
    max_fanout: int = 16
    max_join_degree: int = 8
    min_typed_match: float = 0.20

    def __post_init__(self) -> None:
        if self.seed_k < 1 or self.max_hops < 1:
            raise ValueError("seed_k and max_hops must be positive")
        if not math.isfinite(self.mu) or self.mu < 0:
            raise ValueError("mu must be finite and non-negative")
        if not math.isfinite(self.fanout_exponent) or self.fanout_exponent < 0:
            raise ValueError("fanout_exponent must be finite and non-negative")
        if self.max_fanout < 1 or self.max_join_degree < 1:
            raise ValueError("fanout and join-degree gates must be positive")
        if (not math.isfinite(self.min_typed_match) or
                not 0 < self.min_typed_match <= 1):
            raise ValueError("min_typed_match must be in (0, 1]")


@dataclass(frozen=True)
class TypedPathStepV1:
    depth: int
    arc_id: str
    source_target: int
    target_target: int
    source_id: str
    target_id: str
    source_claim_id: str
    target_claim_id: str | None
    source_predicate: SelectorSpanV1
    target_predicate: SelectorSpanV1 | None
    source_argument_role: str
    target_argument_role: str
    join_entity_id: str
    source_selector: SelectorSpanV1
    target_selector: SelectorSpanV1
    predicate_match: float
    role_match: float
    transition_weight: float


@dataclass(frozen=True)
class PromotedTypedPathV1:
    target: int
    target_id: str
    first_reached_depth: int
    selected_depth: int
    raw_path_score: float
    score_delta: float
    intermediate_targets: tuple[int, ...]
    intermediate_target_ids: tuple[str, ...]
    steps: tuple[TypedPathStepV1, ...]


@dataclass(frozen=True)
class DepthContributionV1:
    depth: int
    reachable_targets: int
    first_reachable_targets: int
    promoted_targets: int
    raw_path_score_sum: float
    selected_score_contribution: float


@dataclass(frozen=True)
class MatchedK1AblationV1:
    score_sha256: str
    reached_targets: int
    promoted_targets: tuple[int, ...]
    full_over_k1_promoted_targets: tuple[int, ...]
    full_over_k1_score_gain: float


@dataclass(frozen=True)
class TypedCompositionReceiptV1:
    topology_sha256: str
    query_sha256: str
    mode: ControlMode
    policy: TypedCompositionPolicyV1
    seed_targets: tuple[int, ...]
    reached_targets: int
    first_reachable_at_depth_2: int
    depth_2_promotions: int
    depth_contributions: tuple[DepthContributionV1, ...]
    promoted_paths: tuple[PromotedTypedPathV1, ...]
    k1_ablation: MatchedK1AblationV1 | None
    fanout_gate_trips: int
    join_hub_gate_trips: int
    h3_composition_status: H3Status
    h3_refusal_reason: str | None
    trip_reason: str | None
    research_only: bool = True


@dataclass(frozen=True)
class TypedUntypedControlV1:
    """Matched controls; arrays are returned separately by the helper."""

    topology_sha256: str
    static_score_sha256: str
    typed_score_sha256: str
    untyped_score_sha256: str
    typed_h3_status: H3Status
    untyped_h3_status: H3Status


@dataclass(frozen=True)
class _State:
    score: float
    nodes: tuple[int, ...]
    joins: tuple[str, ...]
    steps: tuple[TypedPathStepV1, ...]
    active_claim_id: str | None


@dataclass(frozen=True)
class _Run:
    final: np.ndarray
    contribution: np.ndarray
    seeds: tuple[int, ...]
    first_depth: Mapping[int, int]
    exact_depth: tuple[Mapping[int, _State], ...]
    selected: Mapping[int, _State]
    selected_depth: Mapping[int, int]
    fanout_trips: int
    hub_trips: int


def make_typed_graph(
    target_ids: Iterable[str],
    arcs: Iterable[TypedEvidenceArcV1],
    *,
    is_null_control: bool = False,
) -> TypedCompositionGraphV1:
    """Canonicalize an immutable typed graph without dropping duplicates."""

    ids = tuple(target_ids)
    if not ids or len(set(ids)) != len(ids) or any(not item for item in ids):
        raise ValueError("target_ids must be non-empty and unique")
    ordered = tuple(sorted(tuple(arcs), key=lambda arc: (
        arc.source_target, arc.target_target, arc.arc_id,
    )))
    arc_ids = [arc.arc_id for arc in ordered]
    if len(arc_ids) != len(set(arc_ids)):
        raise ValueError("arc_id values must be unique")
    if any(
        arc.source_target >= len(ids) or arc.target_target >= len(ids)
        for arc in ordered
    ):
        raise ValueError("arc references a target outside the candidate universe")
    for arc in ordered:
        if ids[arc.source_target] != arc.source_id:
            raise ValueError("arc source ordinal and source_id disagree")
        if ids[arc.target_target] != arc.target_id:
            raise ValueError("arc target ordinal and target_id disagree")
    payload = {
        "schema": "hswm-typed-composition-graph/v1",
        "target_ids": ids,
        "is_null_control": is_null_control,
        "arcs": tuple({
            "arc_id": arc.arc_id,
            "source_target": arc.source_target,
            "target_target": arc.target_target,
            "source_claim_id": arc.source_claim_id,
            "target_claim_id": arc.target_claim_id,
            "source_predicate": arc.source_predicate.exact,
            "target_predicate": (
                arc.target_predicate.exact if arc.target_predicate else None
            ),
            "source_argument_role": arc.source_argument_role,
            "target_argument_role": arc.target_argument_role,
            "join_entity_id": arc.join_entity_id,
            "source_predicate_selector": _selector_payload(arc.source_predicate),
            "target_predicate_selector": _selector_payload(arc.target_predicate),
            "source_selector": _selector_payload(arc.source_selector),
            "target_selector": _selector_payload(arc.target_selector),
            "origin": arc.origin,
        } for arc in ordered),
    }
    return TypedCompositionGraphV1(
        target_ids=ids,
        arcs=ordered,
        topology_sha256=_digest(payload),
        is_null_control=is_null_control,
    )


def _selector_from_object(value: Any, *, default_role: str = "entity") -> SelectorSpanV1:
    exact = getattr(value, "exact", getattr(value, "exact_quote", None))
    start = getattr(value, "start", getattr(value, "body_start", None))
    end = getattr(value, "end", getattr(value, "body_end", None))
    source_id = getattr(value, "source_id", None)
    role_id = getattr(value, "role_id", getattr(value, "receipt_id", None))
    role = getattr(value, "role", default_role)
    text_scope = getattr(value, "text_scope", "body")
    source_sha = getattr(
        value, "source_text_sha256", getattr(value, "source_sha256", None),
    )
    if source_sha is None:
        source_sha = _digest({"source_id": source_id, "scope": text_scope,
                              "exact": exact})
    return SelectorSpanV1(
        source_id=str(source_id), role_id=str(role_id), role=str(role),
        text_scope=str(text_scope), start=int(start), end=int(end),
        exact=str(exact), source_text_sha256=str(source_sha),
    )


def _claim_roles(claim: Any) -> tuple[Any, ...]:
    return (claim.subject, claim.predicate, *tuple(claim.arguments))


def graph_from_claim_build(build: Any) -> TypedCompositionGraphV1:
    """Adapt a verified ``ClaimGraphBuildV1`` without importing its module.

    Final shared-entity arcs are consumed directly.  An earlier verified title
    projection can be adapted from its claim role and B1 receipt; the target
    title becomes the second exact selector.  Missing evidence fails closed.
    """

    paragraph_graph = getattr(build, "paragraph_graph", None)
    target_ids = tuple(getattr(paragraph_graph, "target_source_ids", ()))
    if not target_ids:
        target_ids = tuple(
            paragraph.source_id for paragraph in getattr(build, "paragraphs", ())
        )
    ordinal = {source_id: index for index, source_id in enumerate(target_ids)}
    paragraphs = {
        paragraph.source_id: paragraph for paragraph in getattr(build, "paragraphs", ())
    }
    claims = {claim.claim_id: claim for claim in getattr(build, "nary_claims", ())}
    roles = {
        role.role_id: role
        for claim in claims.values()
        for role in _claim_roles(claim)
    }
    title_build = getattr(build, "title_anchor_fallback", None)
    title_receipts = {
        receipt.receipt_id: receipt
        for receipt in getattr(title_build, "evidence_spans", ())
    }

    adapted: list[TypedEvidenceArcV1] = []
    for raw_arc in getattr(build, "directed_arcs", ()):
        origin = str(getattr(raw_arc, "origin", ""))
        if not origin.startswith("verified_"):
            continue
        source_id = str(getattr(raw_arc, "subject_source_id"))
        target_id = str(getattr(raw_arc, "object_source_id"))
        if source_id not in ordinal or target_id not in ordinal:
            raise ValueError("verified claim arc references an unknown paragraph")
        claim_id = getattr(raw_arc, "claim_id", None)
        source_claim = claims.get(claim_id)
        if source_claim is None:
            raise ValueError("verified claim arc has no resolvable source claim")
        source_predicate = _selector_from_object(
            source_claim.predicate, default_role="predicate",
        )
        target_claim = claims.get(getattr(raw_arc, "target_claim_id", None))
        target_predicate = (
            _selector_from_object(target_claim.predicate, default_role="predicate")
            if target_claim is not None else None
        )

        source_span_obj = getattr(raw_arc, "source_evidence_span", None)
        target_span_obj = getattr(raw_arc, "target_evidence_span", None)
        if source_span_obj is not None and target_span_obj is not None:
            source_span = _selector_from_object(source_span_obj)
            target_span = _selector_from_object(target_span_obj)
        else:
            # Compatibility with the first verified-title projection.  It has
            # one body receipt; the referenced paragraph title is the second
            # exact selector.  No fabricated selector is allowed.
            source_role_id = getattr(
                raw_arc, "source_role_id",
                getattr(raw_arc, "argument_role_id", None),
            )
            source_role = roles.get(source_role_id)
            receipt_ids = tuple(getattr(raw_arc, "evidence_receipt_ids", ()))
            receipt = title_receipts.get(receipt_ids[0]) if len(receipt_ids) == 1 else None
            target_paragraph = paragraphs.get(target_id)
            if source_role is None or receipt is None or target_paragraph is None:
                raise ValueError("verified arc lacks two reconstructable evidence selectors")
            source_span = _selector_from_object(source_role)
            title = str(target_paragraph.title)
            target_span = SelectorSpanV1(
                source_id=target_id,
                role_id=f"title:{target_id}", role="title", text_scope="title",
                start=0, end=len(title), exact=title,
                source_text_sha256=sha256(title.encode("utf-8")).hexdigest(),
            )

        source_role = str(getattr(source_span, "role", "argument"))
        target_role = str(getattr(
            raw_arc, "object_role", getattr(target_span, "role", source_role),
        ))
        join_entity_id = getattr(raw_arc, "join_entity_id", None)
        if not join_entity_id:
            join_entity_id = "legacy-title:" + _digest({
                "surface": unicodedata.normalize("NFKC", target_span.exact).casefold(),
            })
        adapted.append(TypedEvidenceArcV1(
            arc_id=str(raw_arc.arc_id),
            source_target=ordinal[source_id], target_target=ordinal[target_id],
            source_id=source_id, target_id=target_id,
            source_claim_id=str(claim_id),
            target_claim_id=(
                str(target_claim.claim_id) if target_claim is not None else None
            ),
            source_predicate=source_predicate,
            target_predicate=target_predicate,
            source_argument_role=source_role,
            target_argument_role=target_role,
            join_entity_id=str(join_entity_id),
            source_selector=source_span, target_selector=target_span,
            origin=origin,
        ))
    return make_typed_graph(target_ids, adapted)


def _relation_match(
    query_terms: tuple[str, ...], arc: TypedEvidenceArcV1,
) -> tuple[float, float, float]:
    # Only the relation actually departed on this hop may score this hop.
    # Target predicate/role are continuity evidence for the *next* hop and
    # remain in the receipt, but letting them match here would look ahead.
    predicate_terms = _normalized_words(arc.source_predicate.exact)
    role_text = _ROLE_SPLIT_RE.sub(" ", arc.source_argument_role)
    role_terms = _normalized_words(role_text)
    predicate_match = _coverage(predicate_terms, query_terms)
    role_match = _coverage(role_terms, query_terms)
    # Predicate is the stronger semantic signal; the role can rescue a terse
    # query, but never contributes more than one quarter by itself.
    quality = 0.75 * predicate_match + 0.25 * role_match
    return predicate_match, role_match, quality


def _path_key(state: _State) -> tuple[str, ...]:
    return tuple(step.arc_id for step in state.steps)


def _run(
    query_terms: tuple[str, ...],
    static: np.ndarray,
    graph: TypedCompositionGraphV1,
    policy: TypedCompositionPolicyV1,
    mode: ControlMode,
    max_hops: int,
) -> _Run:
    seed_k = min(policy.seed_k, graph.n_targets)
    seeds = tuple(int(item) for item in np.argsort(-static, kind="stable")[:seed_k])
    if policy.mu == 0:
        return _Run(
            final=static.copy(), contribution=np.zeros_like(static), seeds=seeds,
            first_depth={}, exact_depth=(), selected={}, selected_depth={},
            fanout_trips=0, hub_trips=0,
        )

    adjacency: list[list[TypedEvidenceArcV1]] = [[] for _ in range(graph.n_targets)]
    join_sources: dict[str, set[str]] = {}
    for arc in graph.arcs:
        adjacency[arc.source_target].append(arc)
        join_sources.setdefault(arc.join_entity_id, set()).update((
            arc.source_id, arc.target_id,
        ))
    for row in adjacency:
        row.sort(key=lambda arc: (arc.target_target, arc.arc_id))

    current: tuple[_State, ...] = tuple(
        _State(
            score=max(float(static[seed]), 0.0), nodes=(seed,), joins=(),
            steps=(), active_claim_id=None,
        )
        for seed in seeds
    )
    first_depth: dict[int, int] = {}
    exact_depth: list[Mapping[int, _State]] = []
    selected: dict[int, _State] = {}
    selected_depth: dict[int, int] = {}
    fanout_trips = 0
    hub_trips = 0
    gate_failed = False

    for depth in range(1, max_hops + 1):
        # Claim identity, not merely paragraph identity, is the continuation
        # state.  Multiple claims in one paragraph remain separate frontiers.
        nxt_states: dict[
            tuple[int, str | None, tuple[str, ...], tuple[int, ...]], _State
        ] = {}
        for parent in sorted(current, key=lambda state: (
            state.nodes[-1], state.active_claim_id or "", _path_key(state),
        )):
            source = parent.nodes[-1]
            if depth == 1:
                # A seed paragraph may begin from any of its source claims.
                row = adjacency[source]
            else:
                # A title terminal has no target claim and cannot continue.
                if parent.active_claim_id is None:
                    continue
                row = [
                    arc for arc in adjacency[source]
                    if arc.source_claim_id == parent.active_claim_id
                ]
            if len(row) > policy.max_fanout:
                fanout_trips += 1
                gate_failed = True
                break
            if not row or parent.score <= 0:
                continue
            fanout_weight = float(len(row)) ** (-policy.fanout_exponent)
            for arc in row:
                if len(join_sources[arc.join_entity_id]) > policy.max_join_degree:
                    hub_trips += 1
                    gate_failed = True
                    break
                if arc.join_entity_id in parent.joins or arc.target_target in parent.nodes:
                    continue
                predicate_match, role_match, quality = _relation_match(query_terms, arc)
                if mode == "typed" and (
                    predicate_match < policy.min_typed_match
                    or quality < policy.min_typed_match
                ):
                    # Roles disambiguate an evidenced relation; they never
                    # license a relation whose source predicate did not match.
                    continue
                relation_weight = quality if mode == "typed" else 1.0
                transition = fanout_weight * relation_weight
                candidate_score = parent.score * transition
                if candidate_score <= 0:
                    continue
                step = TypedPathStepV1(
                    depth=depth, arc_id=arc.arc_id,
                    source_target=arc.source_target, target_target=arc.target_target,
                    source_id=arc.source_id, target_id=arc.target_id,
                    source_claim_id=arc.source_claim_id,
                    target_claim_id=arc.target_claim_id,
                    source_predicate=arc.source_predicate,
                    target_predicate=arc.target_predicate,
                    source_argument_role=arc.source_argument_role,
                    target_argument_role=arc.target_argument_role,
                    join_entity_id=arc.join_entity_id,
                    source_selector=arc.source_selector,
                    target_selector=arc.target_selector,
                    predicate_match=predicate_match, role_match=role_match,
                    transition_weight=transition,
                )
                candidate = _State(
                    score=candidate_score,
                    nodes=parent.nodes + (arc.target_target,),
                    joins=parent.joins + (arc.join_entity_id,),
                    steps=parent.steps + (step,),
                    active_claim_id=arc.target_claim_id,
                )
                state_key = (
                    arc.target_target, arc.target_claim_id,
                    candidate.joins, candidate.nodes,
                )
                old = nxt_states.get(state_key)
                if (old is None or candidate.score > old.score or
                        (candidate.score == old.score and
                         _path_key(candidate) < _path_key(old))):
                    nxt_states[state_key] = candidate
            if gate_failed:
                break
        if gate_failed:
            break

        # Collapse only for scoring/reporting.  The next frontier above keeps
        # distinct target claim IDs and path histories.
        nxt: dict[int, _State] = {}
        for candidate in nxt_states.values():
            target = candidate.nodes[-1]
            old = nxt.get(target)
            if (old is None or candidate.score > old.score or
                    (candidate.score == old.score and
                     _path_key(candidate) < _path_key(old))):
                nxt[target] = candidate
        exact_depth.append(dict(sorted(nxt.items())))
        for target, candidate in sorted(nxt.items()):
            first_depth.setdefault(target, depth)
            old = selected.get(target)
            old_depth = selected_depth.get(target, math.inf)
            if (old is None or candidate.score > old.score or
                    (candidate.score == old.score and
                     (depth, _path_key(candidate)) < (old_depth, _path_key(old)))):
                selected[target] = candidate
                selected_depth[target] = depth
        current = tuple(nxt_states.values())

    # Safety is query-atomic: encountering a reached high-fanout claim or join
    # hub discards every partial promotion, including earlier-hop scores.
    if gate_failed:
        return _Run(
            final=static.copy(), contribution=np.zeros_like(static), seeds=seeds,
            first_depth={}, exact_depth=(), selected={}, selected_depth={},
            fanout_trips=fanout_trips, hub_trips=hub_trips,
        )

    contribution = np.zeros_like(static)
    for target, state in selected.items():
        if target not in seeds:
            contribution[target] = state.score
    final = static + policy.mu * contribution
    return _Run(
        final=final, contribution=contribution, seeds=seeds,
        first_depth=first_depth, exact_depth=tuple(exact_depth),
        selected=selected, selected_depth=selected_depth,
        fanout_trips=fanout_trips, hub_trips=hub_trips,
    )


def compose_typed_scores(
    query_text: str,
    static_scores: np.ndarray,
    graph: TypedCompositionGraphV1,
    policy: TypedCompositionPolicyV1,
    *,
    mode: ControlMode = "typed",
) -> tuple[np.ndarray, np.ndarray, TypedCompositionReceiptV1]:
    """Compose scores from raw query text and evidence-bound arcs only."""

    if not isinstance(query_text, str):
        raise TypeError("query_text must be raw text, never an evaluation record")
    if not query_text.strip():
        raise ValueError("query_text must be non-empty")
    if mode not in {"typed", "untyped"}:
        raise ValueError("mode must be typed or untyped")
    static = np.asarray(static_scores, dtype=np.float64)
    if static.shape != (graph.n_targets,) or not np.isfinite(static).all():
        raise ValueError("static_scores must be one finite score per target")
    query_terms = _normalized_words(query_text)
    query_sha = sha256(query_text.encode("utf-8")).hexdigest()

    run = _run(
        query_terms, static, graph, policy, mode=mode,
        max_hops=policy.max_hops,
    )
    k1 = None
    if policy.max_hops >= 2 and policy.mu > 0:
        one = _run(query_terms, static, graph, policy, mode=mode, max_hops=1)
        full_over = tuple(
            int(index) for index in np.flatnonzero(run.final > one.final)
        )
        k1 = MatchedK1AblationV1(
            score_sha256=_score_digest(one.final),
            reached_targets=len(one.first_depth),
            promoted_targets=tuple(int(i) for i in np.flatnonzero(one.contribution > 0)),
            full_over_k1_promoted_targets=full_over,
            full_over_k1_score_gain=float(np.sum(run.final - one.final)),
        )

    depth_rows: list[DepthContributionV1] = []
    for depth in range(1, policy.max_hops + 1):
        row = run.exact_depth[depth - 1] if depth <= len(run.exact_depth) else {}
        selected_sum = sum(
            state.score for target, state in row.items()
            if run.selected_depth.get(target) == depth and target not in run.seeds
        )
        depth_rows.append(DepthContributionV1(
            depth=depth,
            reachable_targets=len(row),
            first_reachable_targets=sum(
                1 for target in row if run.first_depth.get(target) == depth
            ),
            promoted_targets=sum(
                1 for target, state in row.items()
                if target not in run.seeds and state.score > 0
            ),
            raw_path_score_sum=float(sum(state.score for state in row.values())),
            selected_score_contribution=float(policy.mu * selected_sum),
        ))

    promoted: list[PromotedTypedPathV1] = []
    for target, state in sorted(run.selected.items()):
        if target in run.seeds or run.contribution[target] <= 0:
            continue
        nodes = state.nodes
        promoted.append(PromotedTypedPathV1(
            target=target, target_id=graph.target_ids[target],
            first_reached_depth=run.first_depth[target],
            selected_depth=run.selected_depth[target],
            raw_path_score=float(state.score),
            score_delta=float(policy.mu * run.contribution[target]),
            intermediate_targets=tuple(nodes[1:-1]),
            intermediate_target_ids=tuple(graph.target_ids[item] for item in nodes[1:-1]),
            steps=state.steps,
        ))

    first_depth_2 = sum(1 for depth in run.first_depth.values() if depth == 2)
    depth_2_promotions = 0
    if len(run.exact_depth) >= 2:
        depth_2_promotions = sum(
            1 for target, state in run.exact_depth[1].items()
            if target not in run.seeds and state.score > 0
        )

    refusal: str | None = None
    if run.fanout_trips or run.hub_trips:
        refusal = "safety gate trip forced static fallback"
    elif policy.mu == 0:
        refusal = "mu=0 certified floor cannot establish composition"
    elif policy.max_hops < 2:
        refusal = "matched K>=2 run is required"
    elif depth_2_promotions == 0:
        refusal = "no positive depth-2 promotion"
    elif first_depth_2 == 0:
        refusal = "no target is first reachable at depth 2 over matched K=1"
    status: H3Status = "PASS" if refusal is None else "REFUSED"

    trip_parts = []
    if run.fanout_trips:
        trip_parts.append(f"fanout_gate={run.fanout_trips}")
    if run.hub_trips:
        trip_parts.append(f"join_hub_gate={run.hub_trips}")
    if not run.first_depth and policy.mu > 0:
        trip_parts.append("no_query_compatible_evidence_path")
    trip_reason = "; ".join(trip_parts) or None
    receipt = TypedCompositionReceiptV1(
        topology_sha256=graph.topology_sha256, query_sha256=query_sha,
        mode=mode, policy=policy, seed_targets=run.seeds,
        reached_targets=len(run.first_depth),
        first_reachable_at_depth_2=first_depth_2,
        depth_2_promotions=depth_2_promotions,
        depth_contributions=tuple(depth_rows),
        promoted_paths=tuple(promoted), k1_ablation=k1,
        fanout_gate_trips=run.fanout_trips,
        join_hub_gate_trips=run.hub_trips,
        h3_composition_status=status, h3_refusal_reason=refusal,
        trip_reason=trip_reason,
    )
    return run.final, run.contribution, receipt


def compare_typed_untyped(
    query_text: str,
    static_scores: np.ndarray,
    graph: TypedCompositionGraphV1,
    policy: TypedCompositionPolicyV1,
) -> tuple[
    tuple[np.ndarray, np.ndarray, TypedCompositionReceiptV1],
    tuple[np.ndarray, np.ndarray, TypedCompositionReceiptV1],
    TypedUntypedControlV1,
]:
    """Run typed and untyped controls over the exact same arcs and budget."""

    typed = compose_typed_scores(
        query_text, static_scores, graph, policy, mode="typed",
    )
    untyped = compose_typed_scores(
        query_text, static_scores, graph, policy, mode="untyped",
    )
    control = TypedUntypedControlV1(
        topology_sha256=graph.topology_sha256,
        static_score_sha256=_score_digest(np.asarray(static_scores, dtype=np.float64)),
        typed_score_sha256=_score_digest(typed[0]),
        untyped_score_sha256=_score_digest(untyped[0]),
        typed_h3_status=typed[2].h3_composition_status,
        untyped_h3_status=untyped[2].h3_composition_status,
    )
    return typed, untyped, control


def target_shuffle_null_control(
    graph: TypedCompositionGraphV1,
    arc_ids: Sequence[str],
    *,
    seed: int,
) -> TypedCompositionGraphV1:
    """Deterministically rotate selected targets as a non-evidence control.

    In/out degree is preserved, but endpoint evidence no longer licenses the
    rewired topology.  The graph is therefore explicitly marked null-control.
    At least two selected arcs with distinct targets are required.
    """

    if seed < 0:
        raise ValueError("seed must be non-negative")
    selected_ids = tuple(sorted(set(arc_ids)))
    if len(selected_ids) < 2:
        raise ValueError("shuffle control needs at least two arc IDs")
    by_id = {arc.arc_id: arc for arc in graph.arcs}
    if any(arc_id not in by_id for arc_id in selected_ids):
        raise ValueError("shuffle control references an unknown arc")
    selected = [by_id[arc_id] for arc_id in selected_ids]
    if len({arc.target_target for arc in selected}) < 2:
        raise ValueError("shuffle control needs distinct target endpoints")
    shifts = list(range(1, len(selected)))
    offset = seed % len(shifts)
    shifts = shifts[offset:] + shifts[:offset]
    targets = None
    for shift in shifts:
        candidates = selected[shift:] + selected[:shift]
        if all(
            arc.target_target != donor.target_target
            and arc.source_target != donor.target_target
            for arc, donor in zip(selected, candidates)
        ):
            targets = candidates
            break
    if targets is None:
        raise ValueError("no non-self target derangement exists for selected arcs")
    rewired: dict[str, TypedEvidenceArcV1] = {}
    for arc, donor in zip(selected, targets):
        rewired[arc.arc_id] = replace(
            arc,
            target_target=donor.target_target,
            target_id=donor.target_id,
            target_claim_id=donor.target_claim_id,
            target_selector=replace(donor.target_selector),
            target_predicate=(
                replace(donor.target_predicate)
                if donor.target_predicate is not None else None
            ),
            target_argument_role=donor.target_argument_role,
            origin="NULL_TARGET_SHUFFLE_CONTROL",
        )
    arcs = tuple(rewired.get(arc.arc_id, arc) for arc in graph.arcs)
    return make_typed_graph(graph.target_ids, arcs, is_null_control=True)


def relation_shuffle_null_control(
    graph: TypedCompositionGraphV1,
    arc_ids: Sequence[str],
    *,
    seed: int,
) -> TypedCompositionGraphV1:
    """Rotate predicate/role semantics while preserving topology and joins.

    This is the matched relation-label falsifier.  Endpoint selectors and the
    candidate universe are unchanged, while predicates and argument roles are
    rotated across the selected arcs.  Rotated predicate selectors are marked
    ``NULL_RELATION_CONTROL`` because their quotes no longer bind to the local
    source; callers must never treat this graph as evidence or deployment data.
    """

    if seed < 0:
        raise ValueError("seed must be non-negative")
    selected_ids = tuple(sorted(set(arc_ids)))
    if len(selected_ids) < 2:
        raise ValueError("relation shuffle needs at least two arc IDs")
    by_id = {arc.arc_id: arc for arc in graph.arcs}
    if any(arc_id not in by_id for arc_id in selected_ids):
        raise ValueError("relation shuffle references an unknown arc")
    selected = [by_id[arc_id] for arc_id in selected_ids]
    shift = 1 + (seed % (len(selected) - 1))
    donors = selected[shift:] + selected[:shift]

    def null_predicate(
        local: SelectorSpanV1, donor: SelectorSpanV1 | None,
    ) -> SelectorSpanV1:
        exact = donor.exact if donor is not None else "NULL_RELATION_CONTROL"
        return SelectorSpanV1(
            source_id=local.source_id,
            role_id=f"NULL_RELATION_CONTROL:{local.role_id}",
            role="predicate", text_scope=local.text_scope,
            start=local.start, end=local.start + len(exact), exact=exact,
            source_text_sha256=sha256(
                f"NULL_RELATION_CONTROL:{exact}".encode("utf-8")
            ).hexdigest(),
        )

    shuffled: dict[str, TypedEvidenceArcV1] = {}
    for arc, donor in zip(selected, donors):
        target_predicate = None
        if arc.target_predicate is not None:
            target_predicate = null_predicate(
                arc.target_predicate, donor.target_predicate,
            )
        shuffled[arc.arc_id] = replace(
            arc,
            source_predicate=null_predicate(
                arc.source_predicate, donor.source_predicate,
            ),
            target_predicate=target_predicate,
            source_argument_role=donor.source_argument_role,
            target_argument_role=donor.target_argument_role,
            origin="NULL_RELATION_SHUFFLE_CONTROL",
        )
    arcs = tuple(shuffled.get(arc.arc_id, arc) for arc in graph.arcs)
    return make_typed_graph(graph.target_ids, arcs, is_null_control=True)
