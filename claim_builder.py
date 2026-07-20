"""Evidence-bound n-ary claim compiler (builder arm B3).

The module deliberately separates an *extractor* from the trusted compiler.
An extractor may run elsewhere and freeze JSON, but this compiler performs no
network or model call.  It accepts only paragraph evidence and frozen output,
re-checks every subject/predicate/argument against an exact source span, and
quarantines anything it cannot prove from the supplied paragraph.

N-ary claims are the durable representation.  Directed paragraph arcs are a
lossy, role-preserving projection used by retrieval/traversal comparators; they
never replace the source claim.  Exact title anchors provide the declared B1
fallback when no verified claim role explains a title-derived link.

Accepted extraction JSON (offsets are Python Unicode code points)::

    {
      "schema_version": "hswm-claim-extraction/v1",
      "claims": [{
        "subject": {"start": 0, "end": 5, "exact": "Alice"},
        "predicate": {"start": 6, "end": 10, "exact": "gave"},
        "arguments": [
          {"role": "recipient", "start": 11, "end": 14, "exact": "Bob"},
          {"role": "object", "start": 15, "end": 21, "exact": "a book"}
        ]
      }]
    }

Longinus ReferenceSite:
``HSWM/PROM_16_WORLD_COMPILER_CERTIFIED_READOUT_ENVELOPE_2026-07-20.md``
sections 14-18 (S6 recorded LLM n-ary adapter and builder falsifiers).
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
import unicodedata
from typing import Any, Sequence

from title_anchor_builder import (
    NORMALIZATION_VERSION,
    OBJECT_ROLE as TITLE_OBJECT_ROLE,
    OFFSET_UNIT,
    ParagraphInputV1,
    ParagraphGraphProjectionV1,
    TitleAnchorBuildV1,
    build_title_anchor_graph,
    normalize_title_alias,
    verify_title_anchor_build,
)
from world_ir import canonical_json, content_id, sha256_text


SCHEMA_VERSION = "hswm-claim-builder/v1"
EXTRACTION_SCHEMA_VERSION = "hswm-claim-extraction/v1"
ROLE_SCHEMA_VERSION = "exact-source-role/v1"

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_ROLE_RE = re.compile(r"[a-z][a-z0-9_:-]{0,63}\Z")
_ROOT_KEYS = frozenset({"schema_version", "claims"})
_CLAIM_KEYS = frozenset({"subject", "predicate", "arguments"})
_SPAN_KEYS = frozenset({"start", "end", "exact"})
_ARGUMENT_KEYS = frozenset({"role", "start", "end", "exact"})
_RESERVED_ARGUMENT_ROLES = frozenset({"subject", "predicate"})
_EVALUATION_KEYS = frozenset({
    "answer", "answers", "evaluation", "gold", "gold_id", "gold_ids",
    "hop", "hops", "is_supporting", "label", "labels", "qid",
    "question", "questions", "support", "supporting", "supporting_fact",
    "supporting_facts", "target_answer",
})


@dataclass(frozen=True)
class SharedEntityProjectionPolicyV1:
    """Frozen anti-percolation policy for evidence-paired role joins."""

    policy_id: str = "shared-exact-claim-role/v1"
    min_document_frequency: int = 2
    max_document_frequency: int = 8
    min_token_count: int = 2
    min_normalized_characters: int = 4
    max_role_spans_per_document: int = 1
    generic_surfaces: tuple[str, ...] = (
        "a person", "an organization", "the band", "the city", "the company",
        "the country", "the group", "the location", "the organization",
        "the person", "this person", "unknown entity",
    )


SHARED_ENTITY_POLICY = SharedEntityProjectionPolicyV1()


@dataclass(frozen=True)
class FrozenExtractionV1:
    """Immutable receipt for an already-produced extractor response."""

    extraction_id: str
    source_id: str
    producer: str
    model_revision: str
    prompt_sha256: str
    config_sha256: str
    output_sha256: str
    payload_json: str


@dataclass(frozen=True)
class ArgumentRoleV1:
    """One exact, typed role span inside a source paragraph."""

    role_id: str
    source_id: str
    role_kind: str
    role: str
    start: int
    end: int
    exact: str
    prefix: str
    suffix: str
    source_text_sha256: str
    offset_unit: str = OFFSET_UNIT


@dataclass(frozen=True)
class ClaimObservationV1:
    """Verified extractor observation with complete frozen provenance."""

    observation_id: str
    extraction_id: str
    source_id: str
    subject: ArgumentRoleV1
    predicate: ArgumentRoleV1
    arguments: tuple[ArgumentRoleV1, ...]
    producer: str
    model_revision: str
    prompt_sha256: str
    config_sha256: str
    output_sha256: str


@dataclass(frozen=True)
class QuarantinedClaimV1:
    """Auditable rejected extraction or individual claim."""

    quarantine_id: str
    extraction_id: str
    source_id: str
    claim_index: int | None
    reason: str
    detail: str
    producer: str
    model_revision: str
    prompt_sha256: str
    config_sha256: str
    output_sha256: str
    raw_claim_sha256: str


@dataclass(frozen=True)
class ParsedExtractionV1:
    extraction_id: str
    observations: tuple[ClaimObservationV1, ...]
    quarantines: tuple[QuarantinedClaimV1, ...]


@dataclass(frozen=True)
class NaryClaimV1:
    """Canonical n-ary fact; projections must retain this record."""

    claim_id: str
    source_id: str
    subject: ArgumentRoleV1
    predicate: ArgumentRoleV1
    arguments: tuple[ArgumentRoleV1, ...]
    observation_ids: tuple[str, ...]


@dataclass(frozen=True)
class ArcEvidenceSpanV1:
    """One endpoint receipt carried directly by a projected arc."""

    receipt_id: str
    source_id: str
    role_id: str
    role: str
    text_scope: str
    start: int
    end: int
    exact: str
    normalized_surface: str
    source_text_sha256: str


@dataclass(frozen=True)
class QuarantinedSharedEntityV1:
    quarantine_id: str
    join_entity_id: str
    normalized_surface: str
    role_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    document_frequency: int
    candidate_pair_count: int
    rejected_pair_count: int
    reason: str
    detail: str


@dataclass(frozen=True)
class ParagraphRoleArcV1:
    """Binary paragraph projection carrying its originating n-ary role."""

    arc_id: str
    subject_source_id: str
    object_source_id: str
    object_role: str
    origin: str
    claim_id: str | None
    target_claim_id: str | None
    predicate_role_id: str | None
    target_predicate_role_id: str | None
    source_role_id: str
    target_role_id: str
    source_evidence_span: ArcEvidenceSpanV1
    target_evidence_span: ArcEvidenceSpanV1
    join_entity_id: str
    evidence_receipt_ids: tuple[str, ...]


@dataclass(frozen=True)
class ClaimGraphBuildV1:
    schema_version: str
    build_id: str
    paragraphs: tuple[ParagraphInputV1, ...]
    frozen_extractions: tuple[FrozenExtractionV1, ...]
    claim_observations: tuple[ClaimObservationV1, ...]
    quarantined_claims: tuple[QuarantinedClaimV1, ...]
    quarantined_shared_entities: tuple[QuarantinedSharedEntityV1, ...]
    nary_claims: tuple[NaryClaimV1, ...]
    directed_arcs: tuple[ParagraphRoleArcV1, ...]
    paragraph_graph: ParagraphGraphProjectionV1
    title_anchor_fallback: TitleAnchorBuildV1
    stats: dict[str, Any]


# Short aliases make the contract's vocabulary available without weakening the
# repository-wide version suffix convention.
ArgumentRole = ArgumentRoleV1
ClaimObservation = ClaimObservationV1


class _DuplicateJSONKey(ValueError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise _DuplicateJSONKey(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None


def _expected_extraction_id(extraction: FrozenExtractionV1) -> str:
    return content_id("claim_extraction", {
        "source_id": extraction.source_id,
        "producer": extraction.producer,
        "model_revision": extraction.model_revision,
        "prompt_sha256": extraction.prompt_sha256,
        "config_sha256": extraction.config_sha256,
        "output_sha256": extraction.output_sha256,
    })


def freeze_extraction(
    source_id: str,
    payload_json: str,
    *,
    producer: str,
    model_revision: str,
    prompt_sha256: str,
    config_sha256: str,
) -> FrozenExtractionV1:
    """Create a frozen output receipt; this helper does not parse or trust it."""

    if not isinstance(payload_json, str):
        raise TypeError("payload_json must be str")
    output_sha256 = sha256_text(payload_json)
    provisional = FrozenExtractionV1(
        extraction_id="",
        source_id=source_id,
        producer=producer,
        model_revision=model_revision,
        prompt_sha256=prompt_sha256,
        config_sha256=config_sha256,
        output_sha256=output_sha256,
        payload_json=payload_json,
    )
    return FrozenExtractionV1(
        extraction_id=_expected_extraction_id(provisional),
        source_id=source_id,
        producer=producer,
        model_revision=model_revision,
        prompt_sha256=prompt_sha256,
        config_sha256=config_sha256,
        output_sha256=output_sha256,
        payload_json=payload_json,
    )


def _raw_claim_sha256(value: Any) -> str:
    try:
        return sha256_text(canonical_json(value))
    except (TypeError, ValueError):
        return sha256_text(repr(value))


def _quarantine(
    extraction: FrozenExtractionV1,
    *,
    claim_index: int | None,
    reason: str,
    detail: str,
    raw_claim: Any,
) -> QuarantinedClaimV1:
    raw_digest = _raw_claim_sha256(raw_claim)
    payload = {
        "extraction_id": extraction.extraction_id,
        "source_id": extraction.source_id,
        "claim_index": claim_index,
        "reason": reason,
        "detail": detail,
        "raw_claim_sha256": raw_digest,
    }
    return QuarantinedClaimV1(
        quarantine_id=content_id("claim_quarantine", payload),
        extraction_id=extraction.extraction_id,
        source_id=extraction.source_id,
        claim_index=claim_index,
        reason=reason,
        detail=detail,
        producer=extraction.producer,
        model_revision=extraction.model_revision,
        prompt_sha256=extraction.prompt_sha256,
        config_sha256=extraction.config_sha256,
        output_sha256=extraction.output_sha256,
        raw_claim_sha256=raw_digest,
    )


def _normalized_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.casefold()).strip("_")


def _find_evaluation_key(value: Any, path: str = "$") -> tuple[str, str] | None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = _normalized_key(str(key))
            if normalized in _EVALUATION_KEYS:
                return f"{path}.{key}", normalized
            found = _find_evaluation_key(child, f"{path}.{key}")
            if found is not None:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _find_evaluation_key(child, f"{path}[{index}]")
            if found is not None:
                return found
    return None


def _metadata_issue(extraction: FrozenExtractionV1, paragraph: ParagraphInputV1) -> tuple[str, str] | None:
    if not extraction.source_id or extraction.source_id != paragraph.source_id:
        return "source_mismatch", "extraction source_id does not match paragraph source_id"
    if (
        not isinstance(extraction.producer, str)
        or not isinstance(extraction.model_revision, str)
        or not extraction.producer.strip()
        or not extraction.model_revision.strip()
    ):
        return "invalid_provenance", "producer and model_revision must be non-empty"
    for field_name in ("prompt_sha256", "config_sha256", "output_sha256"):
        if not _is_sha256(getattr(extraction, field_name)):
            return "invalid_provenance_hash", f"{field_name} must be lowercase SHA-256"
    try:
        actual_output_sha256 = sha256_text(extraction.payload_json)
    except (AttributeError, TypeError, UnicodeEncodeError):
        return "invalid_output_payload", "payload_json must be UTF-8 encodable str"
    if extraction.output_sha256 != actual_output_sha256:
        return "output_hash_mismatch", "output_sha256 does not match frozen JSON bytes"
    if extraction.extraction_id != _expected_extraction_id(extraction):
        return "extraction_id_mismatch", "extraction_id does not match frozen provenance"
    return None


def _role(
    paragraph: ParagraphInputV1,
    *,
    role_kind: str,
    role: str,
    value: Any,
    allowed_keys: frozenset[str],
) -> tuple[ArgumentRoleV1 | None, tuple[str, str] | None]:
    if not isinstance(value, dict):
        return None, ("invalid_role_schema", f"{role_kind} must be an object")
    keys = frozenset(value)
    if keys != allowed_keys:
        return None, (
            "invalid_role_schema",
            f"{role_kind} keys must be {sorted(allowed_keys)}; got {sorted(keys)}",
        )
    start, end, exact = value.get("start"), value.get("end"), value.get("exact")
    if (
        isinstance(start, bool) or isinstance(end, bool)
        or not isinstance(start, int) or not isinstance(end, int)
    ):
        return None, ("invalid_span_range", f"{role_kind} offsets must be integers")
    if not isinstance(exact, str) or not exact:
        return None, ("invalid_span_range", f"{role_kind} exact text must be non-empty str")
    if start < 0 or end <= start or end > len(paragraph.text):
        return None, (
            "invalid_span_range",
            f"{role_kind} [{start},{end}) outside source length {len(paragraph.text)}",
        )
    if paragraph.text[start:end] != exact:
        return None, (
            "exact_span_mismatch",
            f"{role_kind} exact text does not match source [{start},{end})",
        )
    if role_kind == "argument":
        raw_role = value.get("role")
        if not isinstance(raw_role, str):
            return None, ("invalid_argument_role", "argument role must be str")
        role = raw_role.casefold()
        if _ROLE_RE.fullmatch(role) is None or role in _RESERVED_ARGUMENT_ROLES:
            return None, (
                "invalid_argument_role",
                "argument role must be a non-reserved lower-case role token",
            )

    source_hash = sha256_text(paragraph.text)
    payload = {
        "source_id": paragraph.source_id,
        "role_kind": role_kind,
        "role": role,
        "start": start,
        "end": end,
        "exact": exact,
        "source_text_sha256": source_hash,
        "role_schema_version": ROLE_SCHEMA_VERSION,
    }
    return ArgumentRoleV1(
        role_id=content_id("claim_role", payload),
        source_id=paragraph.source_id,
        role_kind=role_kind,
        role=role,
        start=start,
        end=end,
        exact=exact,
        prefix=paragraph.text[max(0, start - 32):start],
        suffix=paragraph.text[end:end + 32],
        source_text_sha256=source_hash,
    ), None


def _observation_id(extraction: FrozenExtractionV1, subject: ArgumentRoleV1,
                    predicate: ArgumentRoleV1,
                    arguments: tuple[ArgumentRoleV1, ...]) -> str:
    return content_id("claim_observation", {
        "extraction_id": extraction.extraction_id,
        "source_id": extraction.source_id,
        "subject_role_id": subject.role_id,
        "predicate_role_id": predicate.role_id,
        "argument_role_ids": tuple(role.role_id for role in arguments),
    })


def _expected_role_id(role: ArgumentRoleV1) -> str:
    return content_id("claim_role", {
        "source_id": role.source_id,
        "role_kind": role.role_kind,
        "role": role.role,
        "start": role.start,
        "end": role.end,
        "exact": role.exact,
        "source_text_sha256": role.source_text_sha256,
        "role_schema_version": ROLE_SCHEMA_VERSION,
    })


def parse_extraction_payload(
    paragraph: ParagraphInputV1,
    extraction: FrozenExtractionV1,
) -> ParsedExtractionV1:
    """Strictly parse and evidence-check one frozen extraction.

    Invalid metadata or root structure quarantines the whole output.  Invalid
    individual claims are quarantined independently so one bad span cannot
    erase other evidenced claims from the same immutable response.
    """

    if not isinstance(paragraph, ParagraphInputV1):
        raise TypeError("paragraph must be ParagraphInputV1; raw QA rows are forbidden")
    if not isinstance(extraction, FrozenExtractionV1):
        raise TypeError("extraction must be FrozenExtractionV1")

    metadata_issue = _metadata_issue(extraction, paragraph)
    if metadata_issue is not None:
        reason, detail = metadata_issue
        quarantine = _quarantine(
            extraction, claim_index=None, reason=reason, detail=detail,
            raw_claim=extraction.payload_json,
        )
        return ParsedExtractionV1(extraction.extraction_id, (), (quarantine,))

    try:
        payload = json.loads(extraction.payload_json, object_pairs_hook=_strict_object)
    except _DuplicateJSONKey as exc:
        quarantine = _quarantine(
            extraction, claim_index=None, reason="duplicate_json_key",
            detail=str(exc), raw_claim=extraction.payload_json,
        )
        return ParsedExtractionV1(extraction.extraction_id, (), (quarantine,))
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        quarantine = _quarantine(
            extraction, claim_index=None, reason="invalid_json",
            detail=str(exc), raw_claim=extraction.payload_json,
        )
        return ParsedExtractionV1(extraction.extraction_id, (), (quarantine,))

    leaked = _find_evaluation_key(payload)
    if leaked is not None:
        path, key = leaked
        quarantine = _quarantine(
            extraction, claim_index=None, reason="evaluation_label_leakage",
            detail=f"forbidden evaluation field {key!r} at {path}", raw_claim=payload,
        )
        return ParsedExtractionV1(extraction.extraction_id, (), (quarantine,))
    if not isinstance(payload, dict) or frozenset(payload) != _ROOT_KEYS:
        quarantine = _quarantine(
            extraction, claim_index=None, reason="invalid_root_schema",
            detail=f"root keys must be {sorted(_ROOT_KEYS)}", raw_claim=payload,
        )
        return ParsedExtractionV1(extraction.extraction_id, (), (quarantine,))
    if payload.get("schema_version") != EXTRACTION_SCHEMA_VERSION:
        quarantine = _quarantine(
            extraction, claim_index=None, reason="schema_version_mismatch",
            detail=f"expected {EXTRACTION_SCHEMA_VERSION}", raw_claim=payload,
        )
        return ParsedExtractionV1(extraction.extraction_id, (), (quarantine,))
    claims = payload.get("claims")
    if not isinstance(claims, list):
        quarantine = _quarantine(
            extraction, claim_index=None, reason="invalid_root_schema",
            detail="claims must be a JSON array", raw_claim=payload,
        )
        return ParsedExtractionV1(extraction.extraction_id, (), (quarantine,))

    observations: list[ClaimObservationV1] = []
    quarantines: list[QuarantinedClaimV1] = []
    seen_observations: set[str] = set()
    for claim_index, raw_claim in enumerate(claims):
        if not isinstance(raw_claim, dict) or frozenset(raw_claim) != _CLAIM_KEYS:
            quarantines.append(_quarantine(
                extraction, claim_index=claim_index, reason="invalid_claim_schema",
                detail=f"claim keys must be {sorted(_CLAIM_KEYS)}", raw_claim=raw_claim,
            ))
            continue
        raw_arguments = raw_claim.get("arguments")
        if not isinstance(raw_arguments, list) or not raw_arguments:
            quarantines.append(_quarantine(
                extraction, claim_index=claim_index, reason="invalid_claim_schema",
                detail="arguments must be a non-empty array", raw_claim=raw_claim,
            ))
            continue

        subject, issue = _role(
            paragraph, role_kind="subject", role="subject",
            value=raw_claim.get("subject"), allowed_keys=_SPAN_KEYS,
        )
        if issue is None:
            predicate, issue = _role(
                paragraph, role_kind="predicate", role="predicate",
                value=raw_claim.get("predicate"), allowed_keys=_SPAN_KEYS,
            )
        else:
            predicate = None

        arguments: list[ArgumentRoleV1] = []
        if issue is None:
            for raw_argument in raw_arguments:
                argument, issue = _role(
                    paragraph, role_kind="argument", role="",
                    value=raw_argument, allowed_keys=_ARGUMENT_KEYS,
                )
                if issue is not None:
                    break
                assert argument is not None
                arguments.append(argument)
        if issue is not None:
            reason, detail = issue
            quarantines.append(_quarantine(
                extraction, claim_index=claim_index, reason=reason,
                detail=detail, raw_claim=raw_claim,
            ))
            continue
        assert subject is not None and predicate is not None
        ordered_arguments = tuple(sorted(
            arguments, key=lambda role: (role.start, role.end, role.role, role.role_id)
        ))
        observation_id = _observation_id(
            extraction, subject, predicate, ordered_arguments
        )
        if observation_id in seen_observations:
            quarantines.append(_quarantine(
                extraction, claim_index=claim_index, reason="duplicate_claim",
                detail="same evidenced claim occurs more than once in one output",
                raw_claim=raw_claim,
            ))
            continue
        seen_observations.add(observation_id)
        observations.append(ClaimObservationV1(
            observation_id=observation_id,
            extraction_id=extraction.extraction_id,
            source_id=paragraph.source_id,
            subject=subject,
            predicate=predicate,
            arguments=ordered_arguments,
            producer=extraction.producer,
            model_revision=extraction.model_revision,
            prompt_sha256=extraction.prompt_sha256,
            config_sha256=extraction.config_sha256,
            output_sha256=extraction.output_sha256,
        ))

    return ParsedExtractionV1(
        extraction_id=extraction.extraction_id,
        observations=tuple(sorted(observations, key=lambda item: item.observation_id)),
        quarantines=tuple(sorted(quarantines, key=lambda item: item.quarantine_id)),
    )


def _validate_compile_inputs(
    paragraphs: Sequence[ParagraphInputV1],
    frozen_extractions: Sequence[FrozenExtractionV1],
) -> tuple[tuple[ParagraphInputV1, ...], tuple[FrozenExtractionV1, ...]]:
    if isinstance(paragraphs, (str, bytes)) or not isinstance(paragraphs, Sequence):
        raise TypeError("paragraphs must be a sequence of ParagraphInputV1")
    if isinstance(frozen_extractions, (str, bytes)) or not isinstance(frozen_extractions, Sequence):
        raise TypeError("frozen_extractions must be a sequence of FrozenExtractionV1")
    checked_paragraphs = tuple(paragraphs)
    if not checked_paragraphs:
        raise ValueError("at least one paragraph is required")
    for index, paragraph in enumerate(checked_paragraphs):
        if not isinstance(paragraph, ParagraphInputV1):
            raise TypeError(
                f"paragraphs[{index}] must be ParagraphInputV1; raw QA rows are forbidden"
            )
    checked_extractions = tuple(frozen_extractions)
    for index, extraction in enumerate(checked_extractions):
        if not isinstance(extraction, FrozenExtractionV1):
            raise TypeError(f"frozen_extractions[{index}] must be FrozenExtractionV1")
    source_ids = [paragraph.source_id for paragraph in checked_paragraphs]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("paragraph source_id values must be unique")
    extraction_ids = [extraction.extraction_id for extraction in checked_extractions]
    if len(extraction_ids) != len(set(extraction_ids)):
        raise ValueError("frozen extraction_id values must be unique")
    return (
        tuple(sorted(checked_paragraphs, key=lambda item: item.source_id)),
        tuple(sorted(checked_extractions, key=lambda item: item.extraction_id)),
    )


def _claim_id(observation: ClaimObservationV1) -> str:
    return content_id("nary_claim", {
        "source_id": observation.source_id,
        "subject_role_id": observation.subject.role_id,
        "predicate_role_id": observation.predicate.role_id,
        "argument_role_ids": tuple(role.role_id for role in observation.arguments),
    })


def _expected_arc_id(arc: ParagraphRoleArcV1) -> str:
    return content_id("claim_paragraph_arc", {
        "subject_source_id": arc.subject_source_id,
        "object_source_id": arc.object_source_id,
        "object_role": arc.object_role,
        "origin": arc.origin,
        "claim_id": arc.claim_id,
        "target_claim_id": arc.target_claim_id,
        "predicate_role_id": arc.predicate_role_id,
        "target_predicate_role_id": arc.target_predicate_role_id,
        "source_role_id": arc.source_role_id,
        "target_role_id": arc.target_role_id,
        "source_evidence_receipt_id": arc.source_evidence_span.receipt_id,
        "target_evidence_receipt_id": arc.target_evidence_span.receipt_id,
        "join_entity_id": arc.join_entity_id,
        "evidence_receipt_ids": arc.evidence_receipt_ids,
    })


def _expected_span_receipt_id(span: ArcEvidenceSpanV1) -> str:
    return content_id("arc_evidence_span", {
        "source_id": span.source_id,
        "role_id": span.role_id,
        "role": span.role,
        "text_scope": span.text_scope,
        "start": span.start,
        "end": span.end,
        "exact": span.exact,
        "normalized_surface": span.normalized_surface,
        "source_text_sha256": span.source_text_sha256,
    })


def _arc_span(
    *, source_id: str, role_id: str, role: str, text_scope: str,
    start: int, end: int, exact: str, source_text_sha256: str,
) -> ArcEvidenceSpanV1:
    provisional = ArcEvidenceSpanV1(
        receipt_id="", source_id=source_id, role_id=role_id, role=role,
        text_scope=text_scope, start=start, end=end, exact=exact,
        normalized_surface=normalize_title_alias(exact),
        source_text_sha256=source_text_sha256,
    )
    return ArcEvidenceSpanV1(
        receipt_id=_expected_span_receipt_id(provisional),
        source_id=source_id, role_id=role_id, role=role,
        text_scope=text_scope, start=start, end=end, exact=exact,
        normalized_surface=provisional.normalized_surface,
        source_text_sha256=source_text_sha256,
    )


def _claim_role_span(role: ArgumentRoleV1) -> ArcEvidenceSpanV1:
    return _arc_span(
        source_id=role.source_id, role_id=role.role_id, role=role.role,
        text_scope="body", start=role.start, end=role.end, exact=role.exact,
        source_text_sha256=role.source_text_sha256,
    )


def _make_arc(
    *, subject_source_id: str, object_source_id: str, object_role: str,
    origin: str, claim_id: str | None, target_claim_id: str | None,
    predicate_role_id: str | None, target_predicate_role_id: str | None,
    source_span: ArcEvidenceSpanV1, target_span: ArcEvidenceSpanV1,
    join_entity_id: str, evidence_receipt_ids: tuple[str, ...],
) -> ParagraphRoleArcV1:
    provisional = ParagraphRoleArcV1(
        arc_id="", subject_source_id=subject_source_id,
        object_source_id=object_source_id, object_role=object_role,
        origin=origin, claim_id=claim_id, target_claim_id=target_claim_id,
        predicate_role_id=predicate_role_id,
        target_predicate_role_id=target_predicate_role_id,
        source_role_id=source_span.role_id, target_role_id=target_span.role_id,
        source_evidence_span=source_span, target_evidence_span=target_span,
        join_entity_id=join_entity_id,
        evidence_receipt_ids=evidence_receipt_ids,
    )
    return ParagraphRoleArcV1(
        arc_id=_expected_arc_id(provisional),
        subject_source_id=subject_source_id, object_source_id=object_source_id,
        object_role=object_role, origin=origin, claim_id=claim_id,
        target_claim_id=target_claim_id, predicate_role_id=predicate_role_id,
        target_predicate_role_id=target_predicate_role_id,
        source_role_id=source_span.role_id, target_role_id=target_span.role_id,
        source_evidence_span=source_span, target_evidence_span=target_span,
        join_entity_id=join_entity_id,
        evidence_receipt_ids=evidence_receipt_ids,
    )


def _shared_join_id(normalized_surface: str) -> str:
    return content_id("claim_join_entity", {
        "kind": "exact_shared_claim_role",
        "normalized_surface": normalized_surface,
        "normalization_version": NORMALIZATION_VERSION,
        "policy_id": SHARED_ENTITY_POLICY.policy_id,
    })


_LOWERCASE_NAME_CONNECTORS = frozenset({
    "al", "bin", "da", "de", "del", "der", "di", "du", "la", "le",
    "of", "the", "van", "von", "y",
})


def _conservative_named_surface(exact: str) -> bool:
    """Recognize a conservative name shape without assuming Latin script.

    Cased scripts require every lexical token to contain an uppercase/titlecase
    character, unless it is a conventional lowercase name connector (``van``,
    ``of``, etc.).  Scripts without case, including Hangul, Han, Kana, and
    Arabic, are admitted when the separate two-token/length gates pass.  This
    rejects lowercase common phrases while not imposing ASCII title casing on
    non-ASCII names.
    """

    token_chars: list[list[str]] = []
    current: list[str] = []
    for char in unicodedata.normalize("NFKC", exact):
        if unicodedata.category(char)[0] in {"L", "N", "M"}:
            current.append(char)
        elif current:
            token_chars.append(current)
            current = []
    if current:
        token_chars.append(current)
    if not token_chars:
        return False

    saw_letter = False
    for chars in token_chars:
        letters = [char for char in chars if unicodedata.category(char).startswith("L")]
        if not letters:
            continue
        saw_letter = True
        cased = [char for char in letters if char.lower() != char.upper()]
        if not cased:  # uncased script: casing is not a meaningful identity gate
            continue
        surface = "".join(chars).casefold()
        if surface in _LOWERCASE_NAME_CONNECTORS:
            continue
        if not any(char.isupper() or char.istitle() for char in cased):
            return False
    return saw_letter


def _surface_identity_gate(
    normalized_surface: str,
    roles: Sequence[tuple[NaryClaimV1, ArgumentRoleV1]],
) -> tuple[str, str] | None:
    """Return a typed refusal when an exact-surface identity is unsafe."""

    tokens = tuple(normalized_surface.split())
    compact_characters = len(normalized_surface.replace(" ", ""))
    has_uncased_script = any(
        any(
            unicodedata.category(char).startswith("L")
            and char.lower() == char.upper()
            for char in role.exact
        )
        for _, role in roles
    )
    if normalized_surface in SHARED_ENTITY_POLICY.generic_surfaces:
        return "generic_surface", "surface is in the frozen generic-name denylist"
    if len(tokens) < SHARED_ENTITY_POLICY.min_token_count:
        return "homonym_prone_surface", "single-token surfaces are not identity-safe joins"
    if (
        compact_characters < SHARED_ENTITY_POLICY.min_normalized_characters
        and not has_uncased_script
    ):
        return "generic_surface", "surface fails the frozen minimum-character gate"
    if any(
        normalize_title_alias(role.exact) != normalized_surface
        for _, role in roles
    ):
        return (
            "surface_identity_mismatch",
            "source and target exact surfaces do not normalize identically",
        )
    if any(not _conservative_named_surface(role.exact) for _, role in roles):
        return (
            "non_named_surface",
            "surface fails the Unicode-aware conservative name-shape gate",
        )
    return None


def _quarantine_shared_join(
    normalized_surface: str,
    roles: Sequence[tuple[NaryClaimV1, ArgumentRoleV1]],
    reason: str,
    detail: str,
    *,
    candidate_pair_count: int,
    rejected_pair_count: int,
) -> QuarantinedSharedEntityV1:
    role_ids = tuple(sorted({role.role_id for _, role in roles}))
    source_ids = tuple(sorted({claim.source_id for claim, _ in roles}))
    join_entity_id = _shared_join_id(normalized_surface)
    payload = {
        "join_entity_id": join_entity_id,
        "normalized_surface": normalized_surface,
        "role_ids": role_ids,
        "source_ids": source_ids,
        "document_frequency": len(source_ids),
        "candidate_pair_count": candidate_pair_count,
        "rejected_pair_count": rejected_pair_count,
        "reason": reason,
        "detail": detail,
    }
    return QuarantinedSharedEntityV1(
        quarantine_id=content_id("shared_entity_quarantine", payload),
        join_entity_id=join_entity_id,
        normalized_surface=normalized_surface,
        role_ids=role_ids,
        source_ids=source_ids,
        document_frequency=len(source_ids),
        candidate_pair_count=candidate_pair_count,
        rejected_pair_count=rejected_pair_count,
        reason=reason,
        detail=detail,
    )


def _build_payload(
    paragraphs: tuple[ParagraphInputV1, ...],
    extractions: tuple[FrozenExtractionV1, ...],
    observations: tuple[ClaimObservationV1, ...],
    quarantines: tuple[QuarantinedClaimV1, ...],
    shared_quarantines: tuple[QuarantinedSharedEntityV1, ...],
    claims: tuple[NaryClaimV1, ...],
    arcs: tuple[ParagraphRoleArcV1, ...],
    title_anchor_build_id: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "paragraphs": tuple({
            "source_id": item.source_id,
            "title_sha256": sha256_text(item.title),
            "text_sha256": sha256_text(item.text),
        } for item in paragraphs),
        "frozen_extraction_ids": tuple(item.extraction_id for item in extractions),
        "observation_ids": tuple(item.observation_id for item in observations),
        "quarantine_ids": tuple(item.quarantine_id for item in quarantines),
        "shared_quarantine_ids": tuple(item.quarantine_id for item in shared_quarantines),
        "claim_ids": tuple(item.claim_id for item in claims),
        "arc_ids": tuple(item.arc_id for item in arcs),
        "title_anchor_build_id": title_anchor_build_id,
        "shared_entity_policy": SHARED_ENTITY_POLICY,
    }


def compile_claim_graph(
    paragraphs: Sequence[ParagraphInputV1],
    frozen_extractions: Sequence[FrozenExtractionV1],
) -> ClaimGraphBuildV1:
    """Purely compile verified n-ary claims and paragraph-level projections."""

    canonical_paragraphs, canonical_extractions = _validate_compile_inputs(
        paragraphs, frozen_extractions
    )
    paragraph_by_id = {paragraph.source_id: paragraph for paragraph in canonical_paragraphs}
    title_build = build_title_anchor_graph(canonical_paragraphs)
    title_issues = verify_title_anchor_build(title_build)
    if title_issues:
        raise ValueError(f"title-anchor fallback failed verification: {title_issues}")

    observations: list[ClaimObservationV1] = []
    quarantines: list[QuarantinedClaimV1] = []
    for extraction in canonical_extractions:
        paragraph = paragraph_by_id.get(extraction.source_id)
        if paragraph is None:
            quarantines.append(_quarantine(
                extraction, claim_index=None, reason="unknown_source",
                detail="extraction source_id is not in paragraph inputs",
                raw_claim=extraction.payload_json,
            ))
            continue
        parsed = parse_extraction_payload(paragraph, extraction)
        observations.extend(parsed.observations)
        quarantines.extend(parsed.quarantines)
    observations.sort(key=lambda item: item.observation_id)
    quarantines.sort(key=lambda item: item.quarantine_id)

    observations_by_claim: dict[str, list[ClaimObservationV1]] = {}
    for observation in observations:
        observations_by_claim.setdefault(_claim_id(observation), []).append(observation)
    claims = tuple(
        NaryClaimV1(
            claim_id=claim_id,
            source_id=group[0].source_id,
            subject=group[0].subject,
            predicate=group[0].predicate,
            arguments=group[0].arguments,
            observation_ids=tuple(sorted(item.observation_id for item in group)),
        )
        for claim_id, group in sorted(observations_by_claim.items())
    )

    # Title evidence is one conservative linker from a role span to a target
    # paragraph.  B3 additionally joins exact claim-role surfaces across
    # paragraphs, so topology is not capped by the set of paragraph titles.
    receipt_by_span = {
        (receipt.source_id, receipt.body_start, receipt.body_end): receipt
        for receipt in title_build.evidence_spans
    }
    anchor_by_source = {anchor.source_id: anchor for anchor in title_build.anchors}
    title_span_by_source = {
        paragraph.source_id: _arc_span(
            source_id=paragraph.source_id,
            role_id=anchor_by_source[paragraph.source_id].anchor_id,
            role=anchor_by_source[paragraph.source_id].role,
            text_scope="title",
            start=0,
            end=len(paragraph.title),
            exact=paragraph.title,
            source_text_sha256=sha256_text(paragraph.title),
        )
        for paragraph in canonical_paragraphs
    }
    claimed_receipt_ids: set[str] = set()
    arcs: list[ParagraphRoleArcV1] = []
    for claim in claims:
        projected_roles = (claim.subject, *claim.arguments)
        for role in projected_roles:
            receipt = receipt_by_span.get((claim.source_id, role.start, role.end))
            if receipt is None or receipt.exact_quote != role.exact:
                continue
            if receipt.disposition != "linked":
                continue
            claimed_receipt_ids.add(receipt.receipt_id)
            join_entity_id = content_id("claim_join_entity", {
                "kind": "title_anchor",
                "normalized_surface": receipt.normalized_alias,
                "target_source_id": receipt.object_source_id,
                "normalization_version": NORMALIZATION_VERSION,
            })
            arcs.append(_make_arc(
                subject_source_id=claim.source_id,
                object_source_id=receipt.object_source_id,
                object_role=role.role,
                origin="verified_nary_title",
                claim_id=claim.claim_id,
                target_claim_id=None,
                predicate_role_id=claim.predicate.role_id,
                target_predicate_role_id=None,
                source_span=_claim_role_span(role),
                target_span=title_span_by_source[receipt.object_source_id],
                join_entity_id=join_entity_id,
                evidence_receipt_ids=(receipt.receipt_id,),
            ))

    # Evidence-paired relation continuation.  A shared surface licenses only
    # argument -> subject across different paragraphs.  Co-mention, two
    # subjects, two arguments, and the implicit reverse direction are not
    # composition evidence.
    roles_by_surface: dict[str, list[tuple[NaryClaimV1, ArgumentRoleV1]]] = {}
    for claim in claims:
        for role in (claim.subject, *claim.arguments):
            normalized = normalize_title_alias(role.exact)
            if normalized:
                roles_by_surface.setdefault(normalized, []).append((claim, role))
    title_sources_by_surface: dict[str, set[str]] = {}
    for alias in title_build.aliases:
        title_sources_by_surface.setdefault(alias.normalized_alias, set()).add(alias.source_id)

    shared_quarantines: list[QuarantinedSharedEntityV1] = []
    shared_join_surfaces = 0
    title_covered_surfaces = 0
    shared_candidate_pairs = 0
    shared_rejected_pairs = 0
    shared_licensed_pairs = 0
    for normalized_surface, raw_roles in sorted(roles_by_surface.items()):
        roles = sorted(
            {(claim.claim_id, role.role_id): (claim, role)
             for claim, role in raw_roles}.values(),
            key=lambda item: (item[0].source_id, item[0].claim_id, item[1].role_id),
        )
        source_ids = {claim.source_id for claim, _ in roles}
        title_sources = title_sources_by_surface.get(normalized_surface, set())
        unique_title_source = (
            next(iter(title_sources)) if len(title_sources) == 1 else None
        )
        source_arguments_for_title = tuple(
            (claim, role) for claim, role in roles
            if unique_title_source is not None
            and claim.source_id != unique_title_source
            and role.role_kind == "argument"
        )
        if (
            len(source_ids) < SHARED_ENTITY_POLICY.min_document_frequency
            and not source_arguments_for_title
        ):
            continue

        cross_document_pairs = tuple(
            (source_claim, source_role, target_claim, target_role)
            for source_claim, source_role in roles
            for target_claim, target_role in roles
            if source_claim.source_id != target_claim.source_id
        )
        candidate_pair_count = max(
            len(cross_document_pairs), len(source_arguments_for_title)
        )
        shared_candidate_pairs += candidate_pair_count

        if len(title_sources) > 1:
            shared_quarantines.append(_quarantine_shared_join(
                normalized_surface, roles, "ambiguous_title_alias",
                f"surface maps to {len(title_sources)} paragraph titles",
                candidate_pair_count=candidate_pair_count,
                rejected_pair_count=candidate_pair_count,
            ))
            shared_rejected_pairs += candidate_pair_count
            continue

        identity_issue = _surface_identity_gate(normalized_surface, roles)
        if identity_issue is not None:
            reason, detail = identity_issue
            shared_quarantines.append(_quarantine_shared_join(
                normalized_surface, roles, reason, detail,
                candidate_pair_count=candidate_pair_count,
                rejected_pair_count=candidate_pair_count,
            ))
            shared_rejected_pairs += candidate_pair_count
            continue

        effective_source_ids = source_ids | title_sources
        if len(effective_source_ids) > SHARED_ENTITY_POLICY.max_document_frequency:
            shared_quarantines.append(_quarantine_shared_join(
                normalized_surface, roles, "hub_document_frequency",
                f"df={len(effective_source_ids)} exceeds max_df="
                f"{SHARED_ENTITY_POLICY.max_document_frequency}",
                candidate_pair_count=candidate_pair_count,
                rejected_pair_count=candidate_pair_count,
            ))
            shared_rejected_pairs += candidate_pair_count
            continue

        if unique_title_source is not None:
            title_covered_surfaces += 1
            if not source_arguments_for_title:
                if candidate_pair_count:
                    shared_quarantines.append(_quarantine_shared_join(
                        normalized_surface, roles, "role_direction_mismatch",
                        "unique title continuation has no external argument role",
                        candidate_pair_count=candidate_pair_count,
                        rejected_pair_count=candidate_pair_count,
                    ))
                    shared_rejected_pairs += candidate_pair_count
                continue
            matching_target_claims = tuple(
                claim for claim in claims
                if claim.source_id == unique_title_source
                and normalize_title_alias(claim.subject.exact) == normalized_surface
            )
            if len(matching_target_claims) != 1:
                reason = (
                    "title_continuation_missing_subject"
                    if not matching_target_claims
                    else "title_continuation_ambiguous_subject"
                )
                shared_quarantines.append(_quarantine_shared_join(
                    normalized_surface, roles, reason,
                    f"title_source={unique_title_source}; "
                    f"matching_target_claims={len(matching_target_claims)}",
                    candidate_pair_count=candidate_pair_count,
                    rejected_pair_count=candidate_pair_count,
                ))
                shared_rejected_pairs += candidate_pair_count
                continue

            role_ids_by_source: dict[str, set[str]] = {}
            for claim, role in source_arguments_for_title:
                role_ids_by_source.setdefault(claim.source_id, set()).add(role.role_id)
            if any(
                len(role_ids) > SHARED_ENTITY_POLICY.max_role_spans_per_document
                for role_ids in role_ids_by_source.values()
            ):
                shared_quarantines.append(_quarantine_shared_join(
                    normalized_surface, roles, "within_document_ambiguity",
                    "one source paragraph has multiple argument spans for the title entity",
                    candidate_pair_count=candidate_pair_count,
                    rejected_pair_count=candidate_pair_count,
                ))
                shared_rejected_pairs += candidate_pair_count
                continue

            target_claim = matching_target_claims[0]
            target_role = target_claim.subject
            licensed_pairs = tuple(
                (source_claim, source_role, target_claim, target_role)
                for source_claim, source_role in source_arguments_for_title
            )
            rejected_direction_count = max(
                candidate_pair_count - len(licensed_pairs), 0
            )
            if rejected_direction_count:
                shared_quarantines.append(_quarantine_shared_join(
                    normalized_surface, roles, "role_direction_mismatch",
                    "unique title continuation licenses only argument->subject; "
                    f"candidate_pairs={candidate_pair_count}; "
                    f"licensed_pairs={len(licensed_pairs)}",
                    candidate_pair_count=candidate_pair_count,
                    rejected_pair_count=rejected_direction_count,
                ))
                shared_rejected_pairs += rejected_direction_count
        else:
            role_ids_by_source: dict[str, set[str]] = {}
            for claim, role in roles:
                role_ids_by_source.setdefault(claim.source_id, set()).add(role.role_id)
            if any(
                len(role_ids) > SHARED_ENTITY_POLICY.max_role_spans_per_document
                for role_ids in role_ids_by_source.values()
            ):
                shared_quarantines.append(_quarantine_shared_join(
                    normalized_surface, roles, "within_document_ambiguity",
                    "one paragraph binds the same surface to multiple claim-role spans",
                    candidate_pair_count=candidate_pair_count,
                    rejected_pair_count=candidate_pair_count,
                ))
                shared_rejected_pairs += candidate_pair_count
                continue
            licensed_pairs = tuple(
                pair for pair in cross_document_pairs
                if pair[1].role_kind == "argument"
                and pair[3].role_kind == "subject"
            )
            rejected_direction_count = candidate_pair_count - len(licensed_pairs)
            if rejected_direction_count:
                shared_quarantines.append(_quarantine_shared_join(
                    normalized_surface, roles, "role_direction_mismatch",
                    "only argument->subject is licensed; "
                    f"candidate_pairs={candidate_pair_count}; "
                    f"licensed_pairs={len(licensed_pairs)}",
                    candidate_pair_count=candidate_pair_count,
                    rejected_pair_count=rejected_direction_count,
                ))
                shared_rejected_pairs += rejected_direction_count

        if not licensed_pairs:
            continue
        shared_join_surfaces += 1
        shared_licensed_pairs += len(licensed_pairs)
        join_entity_id = _shared_join_id(normalized_surface)
        for source_claim, source_role, target_claim, target_role in licensed_pairs:
            arcs.append(_make_arc(
                subject_source_id=source_claim.source_id,
                object_source_id=target_claim.source_id,
                object_role=target_role.role,
                origin="verified_shared_entity",
                claim_id=source_claim.claim_id,
                target_claim_id=target_claim.claim_id,
                predicate_role_id=source_claim.predicate.role_id,
                target_predicate_role_id=target_claim.predicate.role_id,
                source_span=_claim_role_span(source_role),
                target_span=_claim_role_span(target_role),
                join_entity_id=join_entity_id,
                evidence_receipt_ids=(),
            ))

    receipt_by_id = {
        receipt.receipt_id: receipt for receipt in title_build.evidence_spans
    }
    # Keep every unexplained B1 edge as a per-receipt fallback.  Per-receipt
    # rather than pair-collapsed records preserve the exact evidence boundary.
    for link in title_build.directed_links:
        for receipt_id in link.evidence_receipt_ids:
            if receipt_id in claimed_receipt_ids:
                continue
            receipt = receipt_by_id[receipt_id]
            source_span = _arc_span(
                source_id=link.subject_source_id,
                role_id=receipt.receipt_id,
                role=TITLE_OBJECT_ROLE,
                text_scope="body",
                start=receipt.body_start,
                end=receipt.body_end,
                exact=receipt.exact_quote,
                source_text_sha256=receipt.source_text_sha256,
            )
            join_entity_id = content_id("claim_join_entity", {
                "kind": "title_anchor",
                "normalized_surface": receipt.normalized_alias,
                "target_source_id": link.object_source_id,
                "normalization_version": NORMALIZATION_VERSION,
            })
            arcs.append(_make_arc(
                subject_source_id=link.subject_source_id,
                object_source_id=link.object_source_id,
                object_role=TITLE_OBJECT_ROLE,
                origin="title_anchor_fallback",
                claim_id=None,
                target_claim_id=None,
                predicate_role_id=None,
                target_predicate_role_id=None,
                source_span=source_span,
                target_span=title_span_by_source[link.object_source_id],
                join_entity_id=join_entity_id,
                evidence_receipt_ids=(receipt.receipt_id,),
            ))
    shared_quarantines.sort(key=lambda item: item.quarantine_id)
    canonical_arcs = tuple(sorted(arcs, key=lambda item: item.arc_id))

    ordinal_by_source = {
        paragraph.source_id: ordinal
        for ordinal, paragraph in enumerate(canonical_paragraphs)
    }
    outgoing: list[set[int]] = [set() for _ in canonical_paragraphs]
    for arc in canonical_arcs:
        outgoing[ordinal_by_source[arc.subject_source_id]].add(
            ordinal_by_source[arc.object_source_id]
        )
    paragraph_graph = ParagraphGraphProjectionV1(
        target_source_ids=tuple(item.source_id for item in canonical_paragraphs),
        unit_texts=tuple(f"{item.title} :: {item.text}" for item in canonical_paragraphs),
        outgoing_target_ordinals=tuple(tuple(sorted(values)) for values in outgoing),
    )

    stats: dict[str, Any] = {
        "n_paragraphs": len(canonical_paragraphs),
        "n_frozen_extractions": len(canonical_extractions),
        "n_verified_observations": len(observations),
        "n_quarantined_claims": len(quarantines),
        "n_quarantined_shared_entities": len(shared_quarantines),
        "n_nary_claims": len(claims),
        "n_claim_arcs": sum(arc.origin == "verified_nary_title" for arc in canonical_arcs),
        "n_shared_entity_arcs": sum(
            arc.origin == "verified_shared_entity" for arc in canonical_arcs
        ),
        "n_shared_join_surfaces": shared_join_surfaces,
        "n_shared_candidate_pairs": shared_candidate_pairs,
        "n_shared_licensed_pairs": shared_licensed_pairs,
        "n_shared_rejected_pairs": shared_rejected_pairs,
        "n_title_covered_shared_surfaces": title_covered_surfaces,
        "n_title_fallback_arcs": sum(arc.origin == "title_anchor_fallback" for arc in canonical_arcs),
        "n_binary_arcs": len(canonical_arcs),
        "role_arity": tuple(sorted(
            len(claim.arguments) + 2 for claim in claims
        )),
        "quarantine_reasons": tuple(sorted(
            (reason, sum(item.reason == reason for item in quarantines))
            for reason in {item.reason for item in quarantines}
        )),
        "shared_quarantine_reasons": tuple(sorted(
            (reason, sum(item.reason == reason for item in shared_quarantines))
            for reason in {item.reason for item in shared_quarantines}
        )),
        "shared_entity_policy": SHARED_ENTITY_POLICY,
        "input_fields": ("source_id", "title", "text"),
        "offset_unit": OFFSET_UNIT,
    }
    canonical_json(stats)
    observation_tuple = tuple(observations)
    quarantine_tuple = tuple(quarantines)
    shared_quarantine_tuple = tuple(shared_quarantines)
    build_payload = _build_payload(
        canonical_paragraphs, canonical_extractions, observation_tuple,
        quarantine_tuple, shared_quarantine_tuple, claims, canonical_arcs,
        title_build.build_id,
    )
    return ClaimGraphBuildV1(
        schema_version=SCHEMA_VERSION,
        build_id=content_id("claim_graph_build", build_payload),
        paragraphs=canonical_paragraphs,
        frozen_extractions=canonical_extractions,
        claim_observations=observation_tuple,
        quarantined_claims=quarantine_tuple,
        quarantined_shared_entities=shared_quarantine_tuple,
        nary_claims=claims,
        directed_arcs=canonical_arcs,
        paragraph_graph=paragraph_graph,
        title_anchor_fallback=title_build,
        stats=stats,
    )


def verify_claim_graph(build: ClaimGraphBuildV1) -> tuple[str, ...]:
    """Verify evidence, provenance references, n-ary grouping, and projection."""

    issues: list[str] = []
    if build.schema_version != SCHEMA_VERSION:
        issues.append("schema_version_mismatch")
    paragraph_by_id = {item.source_id: item for item in build.paragraphs}
    if len(paragraph_by_id) != len(build.paragraphs):
        issues.append("duplicate_paragraph_source_id")
    extraction_by_id = {item.extraction_id: item for item in build.frozen_extractions}
    observation_by_id = {item.observation_id: item for item in build.claim_observations}
    claim_by_id = {item.claim_id: item for item in build.nary_claims}
    receipt_by_id = {
        item.receipt_id: item for item in build.title_anchor_fallback.evidence_spans
    }
    issues.extend(f"title_anchor:{issue}" for issue in verify_title_anchor_build(
        build.title_anchor_fallback
    ))
    if len(extraction_by_id) != len(build.frozen_extractions):
        issues.append("duplicate_extraction_id")
    if len(observation_by_id) != len(build.claim_observations):
        issues.append("duplicate_observation_id")
    if len(claim_by_id) != len(build.nary_claims):
        issues.append("duplicate_claim_id")

    for extraction in build.frozen_extractions:
        paragraph = paragraph_by_id.get(extraction.source_id)
        if paragraph is None:
            continue
        metadata_issue = _metadata_issue(extraction, paragraph)
        if metadata_issue is not None:
            issues.append(f"frozen_extraction_{metadata_issue[0]}:{extraction.extraction_id}")

    for observation in build.claim_observations:
        paragraph = paragraph_by_id.get(observation.source_id)
        extraction = extraction_by_id.get(observation.extraction_id)
        if paragraph is None:
            issues.append(f"dangling_observation_source:{observation.observation_id}")
            continue
        if extraction is None:
            issues.append(f"dangling_observation_extraction:{observation.observation_id}")
        elif (
            observation.producer != extraction.producer
            or observation.model_revision != extraction.model_revision
            or observation.prompt_sha256 != extraction.prompt_sha256
            or observation.config_sha256 != extraction.config_sha256
            or observation.output_sha256 != extraction.output_sha256
        ):
            issues.append(f"observation_provenance_mismatch:{observation.observation_id}")
        roles = (observation.subject, observation.predicate, *observation.arguments)
        for role in roles:
            if role.source_id != observation.source_id:
                issues.append(f"role_source_mismatch:{role.role_id}")
                continue
            if paragraph.text[role.start:role.end] != role.exact:
                issues.append(f"role_quote_mismatch:{role.role_id}")
            if sha256_text(paragraph.text) != role.source_text_sha256:
                issues.append(f"role_source_hash_mismatch:{role.role_id}")
            if paragraph.text[max(0, role.start - 32):role.start] != role.prefix:
                issues.append(f"role_prefix_mismatch:{role.role_id}")
            if paragraph.text[role.end:role.end + 32] != role.suffix:
                issues.append(f"role_suffix_mismatch:{role.role_id}")
            if role.role_id != _expected_role_id(role):
                issues.append(f"role_id_mismatch:{role.role_id}")
        expected_id = content_id("claim_observation", {
            "extraction_id": observation.extraction_id,
            "source_id": observation.source_id,
            "subject_role_id": _expected_role_id(observation.subject),
            "predicate_role_id": _expected_role_id(observation.predicate),
            "argument_role_ids": tuple(
                _expected_role_id(role) for role in observation.arguments
            ),
        }) if extraction is not None else None
        if expected_id is not None and observation.observation_id != expected_id:
            issues.append(f"observation_id_mismatch:{observation.observation_id}")

    for claim in build.nary_claims:
        if not claim.arguments:
            issues.append(f"claim_without_argument:{claim.claim_id}")
        group = [observation_by_id.get(oid) for oid in claim.observation_ids]
        if not group or any(item is None for item in group):
            issues.append(f"dangling_claim_observation:{claim.claim_id}")
            continue
        first = group[0]
        assert first is not None
        if (
            claim.claim_id != _claim_id(first)
            or claim.source_id != first.source_id
            or claim.subject != first.subject
            or claim.predicate != first.predicate
            or claim.arguments != first.arguments
            or any(_claim_id(item) != claim.claim_id for item in group if item is not None)
        ):
            issues.append(f"nary_claim_group_mismatch:{claim.claim_id}")
    claimed_observations = {
        observation_id
        for claim in build.nary_claims
        for observation_id in claim.observation_ids
    }
    if claimed_observations != set(observation_by_id):
        issues.append("claim_observation_coverage_mismatch")

    for quarantine in build.quarantined_claims:
        expected_quarantine_id = content_id("claim_quarantine", {
            "extraction_id": quarantine.extraction_id,
            "source_id": quarantine.source_id,
            "claim_index": quarantine.claim_index,
            "reason": quarantine.reason,
            "detail": quarantine.detail,
            "raw_claim_sha256": quarantine.raw_claim_sha256,
        })
        if quarantine.quarantine_id != expected_quarantine_id:
            issues.append(f"quarantine_id_mismatch:{quarantine.quarantine_id}")

    for quarantine in build.quarantined_shared_entities:
        expected_quarantine_id = content_id("shared_entity_quarantine", {
            "join_entity_id": quarantine.join_entity_id,
            "normalized_surface": quarantine.normalized_surface,
            "role_ids": quarantine.role_ids,
            "source_ids": quarantine.source_ids,
            "document_frequency": quarantine.document_frequency,
            "candidate_pair_count": quarantine.candidate_pair_count,
            "rejected_pair_count": quarantine.rejected_pair_count,
            "reason": quarantine.reason,
            "detail": quarantine.detail,
        })
        if quarantine.quarantine_id != expected_quarantine_id:
            issues.append(
                f"shared_quarantine_id_mismatch:{quarantine.quarantine_id}"
            )
        if quarantine.join_entity_id != _shared_join_id(
            quarantine.normalized_surface
        ):
            issues.append(
                f"shared_quarantine_join_id_mismatch:{quarantine.quarantine_id}"
            )
        if quarantine.document_frequency != len(set(quarantine.source_ids)):
            issues.append(
                f"shared_quarantine_df_mismatch:{quarantine.quarantine_id}"
            )
        if (
            quarantine.candidate_pair_count < 0
            or quarantine.rejected_pair_count < 0
            or quarantine.rejected_pair_count > quarantine.candidate_pair_count
        ):
            issues.append(
                f"shared_quarantine_pair_count_invalid:{quarantine.quarantine_id}"
            )

    def verify_endpoint(
        arc: ParagraphRoleArcV1,
        span: ArcEvidenceSpanV1,
        expected_source_id: str,
        side: str,
    ) -> None:
        if span.receipt_id != _expected_span_receipt_id(span):
            issues.append(f"arc_{side}_span_id_mismatch:{arc.arc_id}")
        if span.source_id != expected_source_id:
            issues.append(f"arc_{side}_span_source_mismatch:{arc.arc_id}")
        paragraph = paragraph_by_id.get(span.source_id)
        if paragraph is None:
            issues.append(f"arc_{side}_span_dangling_source:{arc.arc_id}")
            return
        if span.text_scope == "body":
            text = paragraph.text
        elif span.text_scope == "title":
            text = paragraph.title
        else:
            issues.append(f"arc_{side}_span_unknown_scope:{arc.arc_id}")
            return
        if text[span.start:span.end] != span.exact:
            issues.append(f"arc_{side}_span_quote_mismatch:{arc.arc_id}")
        if sha256_text(text) != span.source_text_sha256:
            issues.append(f"arc_{side}_span_source_hash_mismatch:{arc.arc_id}")
        if normalize_title_alias(span.exact) != span.normalized_surface:
            issues.append(f"arc_{side}_span_normalization_mismatch:{arc.arc_id}")

    def role_for(claim: NaryClaimV1 | None, role_id: str) -> ArgumentRoleV1 | None:
        if claim is None:
            return None
        return next(
            (role for role in (claim.subject, *claim.arguments)
             if role.role_id == role_id),
            None,
        )

    expected_pairs: set[tuple[str, str]] = set()
    for arc in build.directed_arcs:
        expected_pairs.add((arc.subject_source_id, arc.object_source_id))
        if arc.arc_id != _expected_arc_id(arc):
            issues.append(f"arc_id_mismatch:{arc.arc_id}")
        if arc.subject_source_id not in paragraph_by_id or arc.object_source_id not in paragraph_by_id:
            issues.append(f"dangling_arc_source:{arc.arc_id}")
        if arc.source_role_id != arc.source_evidence_span.role_id:
            issues.append(f"arc_source_role_receipt_mismatch:{arc.arc_id}")
        if arc.target_role_id != arc.target_evidence_span.role_id:
            issues.append(f"arc_target_role_receipt_mismatch:{arc.arc_id}")
        verify_endpoint(arc, arc.source_evidence_span, arc.subject_source_id, "source")
        verify_endpoint(arc, arc.target_evidence_span, arc.object_source_id, "target")
        for receipt_id in arc.evidence_receipt_ids:
            receipt = receipt_by_id.get(receipt_id)
            if receipt is None:
                issues.append(f"dangling_arc_receipt:{arc.arc_id}")
            elif (
                receipt.source_id != arc.subject_source_id
                or receipt.object_source_id != arc.object_source_id
                or receipt.disposition != "linked"
            ):
                issues.append(f"arc_receipt_binding_mismatch:{arc.arc_id}")
        if arc.origin == "verified_nary_title":
            claim = claim_by_id.get(arc.claim_id or "")
            if claim is None:
                issues.append(f"dangling_arc_claim:{arc.arc_id}")
            else:
                projected_role = role_for(claim, arc.source_role_id)
                if (
                    arc.predicate_role_id != claim.predicate.role_id
                    or projected_role is None
                    or projected_role.role != arc.object_role
                    or arc.source_evidence_span != _claim_role_span(projected_role)
                    or arc.target_claim_id is not None
                    or arc.target_predicate_role_id is not None
                ):
                    issues.append(f"arc_role_binding_mismatch:{arc.arc_id}")
            if not arc.evidence_receipt_ids:
                issues.append(f"title_arc_without_alias_evidence:{arc.arc_id}")
            anchor = next(
                (item for item in build.title_anchor_fallback.anchors
                 if item.source_id == arc.object_source_id),
                None,
            )
            if anchor is None or arc.target_role_id != anchor.anchor_id:
                issues.append(f"title_arc_target_anchor_mismatch:{arc.arc_id}")
            elif arc.target_evidence_span != _arc_span(
                source_id=arc.object_source_id,
                role_id=anchor.anchor_id,
                role=anchor.role,
                text_scope="title",
                start=anchor.title_start,
                end=anchor.title_end,
                exact=anchor.exact_title,
                source_text_sha256=sha256_text(anchor.exact_title),
            ):
                issues.append(f"title_arc_target_evidence_mismatch:{arc.arc_id}")
            for receipt_id in arc.evidence_receipt_ids:
                receipt = receipt_by_id.get(receipt_id)
                if receipt is not None and (
                    receipt.body_start != arc.source_evidence_span.start
                    or receipt.body_end != arc.source_evidence_span.end
                    or receipt.exact_quote != arc.source_evidence_span.exact
                ):
                    issues.append(f"title_arc_source_evidence_mismatch:{arc.arc_id}")
        elif arc.origin == "verified_shared_entity":
            source_claim = claim_by_id.get(arc.claim_id or "")
            target_claim = claim_by_id.get(arc.target_claim_id or "")
            source_role = role_for(source_claim, arc.source_role_id)
            target_role = role_for(target_claim, arc.target_role_id)
            if (
                source_claim is None
                or target_claim is None
                or source_role is None
                or target_role is None
                or arc.predicate_role_id != source_claim.predicate.role_id
                or arc.target_predicate_role_id != target_claim.predicate.role_id
                or arc.source_evidence_span != _claim_role_span(source_role)
                or arc.target_evidence_span != _claim_role_span(target_role)
                or source_claim.source_id == target_claim.source_id
                or source_role.role_kind != "argument"
                or target_role.role_kind != "subject"
                or target_role.role != arc.object_role
            ):
                issues.append(f"shared_arc_role_binding_mismatch:{arc.arc_id}")
            elif (
                arc.source_evidence_span.normalized_surface
                != arc.target_evidence_span.normalized_surface
                or arc.join_entity_id != _shared_join_id(
                    arc.source_evidence_span.normalized_surface
                )
                or not _conservative_named_surface(source_role.exact)
                or not _conservative_named_surface(target_role.exact)
            ):
                issues.append(f"shared_arc_join_mismatch:{arc.arc_id}")
            elif source_claim is not None and target_claim is not None:
                normalized_surface = arc.source_evidence_span.normalized_surface
                identity_issue = _surface_identity_gate(
                    normalized_surface,
                    ((source_claim, source_role), (target_claim, target_role)),
                )
                if identity_issue is not None:
                    issues.append(f"shared_arc_identity_gate_failed:{arc.arc_id}")
                title_sources = {
                    alias.source_id for alias in build.title_anchor_fallback.aliases
                    if alias.normalized_alias == normalized_surface
                }
                if len(title_sources) > 1:
                    issues.append(f"shared_arc_ambiguous_title:{arc.arc_id}")
                elif len(title_sources) == 1 and arc.object_source_id not in title_sources:
                    issues.append(f"shared_arc_wrong_title_target:{arc.arc_id}")
            if arc.evidence_receipt_ids:
                issues.append(f"shared_arc_has_title_receipt:{arc.arc_id}")
        elif arc.origin == "title_anchor_fallback":
            if any(value is not None for value in (
                arc.claim_id, arc.target_claim_id, arc.predicate_role_id,
                arc.target_predicate_role_id,
            )):
                issues.append(f"fallback_claim_binding_present:{arc.arc_id}")
            if not arc.evidence_receipt_ids:
                issues.append(f"fallback_without_alias_evidence:{arc.arc_id}")
            for receipt_id in arc.evidence_receipt_ids:
                receipt = receipt_by_id.get(receipt_id)
                if receipt is not None and (
                    arc.source_role_id != receipt.receipt_id
                    or receipt.body_start != arc.source_evidence_span.start
                    or receipt.body_end != arc.source_evidence_span.end
                    or receipt.exact_quote != arc.source_evidence_span.exact
                ):
                    issues.append(f"fallback_source_evidence_mismatch:{arc.arc_id}")
            anchor = next(
                (item for item in build.title_anchor_fallback.anchors
                 if item.source_id == arc.object_source_id),
                None,
            )
            if anchor is None or arc.target_role_id != anchor.anchor_id:
                issues.append(f"fallback_target_anchor_mismatch:{arc.arc_id}")
        else:
            issues.append(f"unknown_arc_origin:{arc.arc_id}")

    graph_pairs = {
        (
            build.paragraph_graph.target_source_ids[source],
            build.paragraph_graph.target_source_ids[target],
        )
        for source, target in build.paragraph_graph.edge_pairs()
    }
    if graph_pairs != expected_pairs:
        issues.append("paragraph_graph_projection_mismatch")
    if build.paragraph_graph.target_source_ids != tuple(
        item.source_id for item in build.paragraphs
    ):
        issues.append("paragraph_graph_order_mismatch")
    if build.paragraph_graph.unit_texts != tuple(
        f"{item.title} :: {item.text}" for item in build.paragraphs
    ):
        issues.append("paragraph_graph_text_mismatch")
    try:
        canonical_json(build.stats)
    except (TypeError, ValueError):
        issues.append("invalid_stats")
    expected_build_id = content_id("claim_graph_build", _build_payload(
        build.paragraphs,
        build.frozen_extractions,
        build.claim_observations,
        build.quarantined_claims,
        build.quarantined_shared_entities,
        build.nary_claims,
        build.directed_arcs,
        build.title_anchor_fallback.build_id,
    ))
    if build.build_id != expected_build_id:
        issues.append("build_id_mismatch")
    return tuple(sorted(set(issues)))
