"""Evidence-bound exact-title-anchor graph builder (builder arm B1).

This is the cheapest honest step beyond the legacy capitalization heuristic:
it links a paragraph only when its body contains a title-derived alias of
another paragraph.  Extraction is deterministic, network/LLM-free, and sees
only ``(source_id, title, text)``.  Evaluation questions, answers, support
labels, and hop labels are outside the API by construction.

The output keeps paragraph targets and ``"title :: text"`` strings in caller
order, so an existing paragraph/query embedding cache can be reused without a
single new embedding call.  Topology is role-preserving and directed (whether
the roles affect inference is a separate, versioned kernel decision):

    paragraph title SUBJECT anchor --body evidence--> title OBJECT target

Ambiguous aliases are quarantined instead of fanned out into false bridges.
Matches use a declared Unicode/punctuation normalizer and leftmost-longest
exact token matching; every accepted object mention carries body-local Python
Unicode-code-point offsets and an exact quote receipt.

Longinus ReferenceSite:
``HSWM/PROM_16_WORLD_COMPILER_CERTIFIED_READOUT_ENVELOPE_2026-07-20.md``
sections 14-18 (S6 builder adapters and builder falsifiers).
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
import unicodedata
from typing import Any, Sequence

import numpy as np

from world_ir import canonical_json, content_id, sha256_text


SCHEMA_VERSION = "hswm-title-anchor-builder/v1"
NORMALIZATION_VERSION = "unicode-nfkc-casefold-punctuation-token-v1"
OFFSET_UNIT = "python-unicode-codepoint-v1"
SUBJECT_ROLE = "paragraph_title_subject"
OBJECT_ROLE = "body_title_alias_object"

_LEADING_ARTICLES = frozenset({"a", "an", "the"})
_PARENTHETICAL_SUFFIX_RE = re.compile(r"\s*\([^()]*\)\s*$")


@dataclass(frozen=True)
class ParagraphInputV1:
    """The complete and deliberately narrow B1 compiler input."""

    source_id: str
    title: str
    text: str


@dataclass(frozen=True)
class ParagraphTargetV1:
    ordinal: int
    source_id: str
    title: str
    text: str
    unit_text: str
    title_sha256: str
    text_sha256: str


@dataclass(frozen=True)
class TitleSubjectAnchorV1:
    anchor_id: str
    source_id: str
    role: str
    title_start: int
    title_end: int
    exact_title: str
    normalized_title: str


@dataclass(frozen=True)
class TitleAliasBindingV1:
    alias_id: str
    source_id: str
    normalized_alias: str
    normalized_tokens: tuple[str, ...]
    derivations: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceSpanReceiptV1:
    receipt_id: str
    source_id: str
    subject_anchor_id: str
    object_source_id: str
    object_alias_id: str
    subject_role: str
    object_role: str
    body_start: int
    body_end: int
    exact_quote: str
    prefix: str
    suffix: str
    normalized_alias: str
    offset_unit: str
    source_text_sha256: str
    disposition: str


@dataclass(frozen=True)
class QuarantinedSpanV1:
    quarantine_id: str
    source_id: str
    body_start: int
    body_end: int
    exact_quote: str
    prefix: str
    suffix: str
    normalized_alias: str
    candidate_source_ids: tuple[str, ...]
    candidate_alias_ids: tuple[str, ...]
    reason: str
    offset_unit: str
    source_text_sha256: str


@dataclass(frozen=True)
class DirectedRoleLinkV1:
    link_id: str
    subject_source_id: str
    subject_anchor_id: str
    subject_role: str
    object_source_id: str
    object_anchor_id: str
    object_role: str
    evidence_receipt_ids: tuple[str, ...]


@dataclass(frozen=True)
class ParagraphGraphProjectionV1:
    """Dense ordinal projection for retrieval/traversal comparators.

    Row ``i`` in ``outgoing_target_ordinals`` corresponds to paragraph target
    ``target_source_ids[i]``.  Each tuple contains unique target ordinals in
    ascending caller order.  Direction is subject paragraph -> mentioned title
    paragraph; no implicit reverse edge or self-loop is added.
    """

    target_source_ids: tuple[str, ...]
    unit_texts: tuple[str, ...]
    outgoing_target_ordinals: tuple[tuple[int, ...], ...]

    def edge_pairs(self) -> tuple[tuple[int, int], ...]:
        return tuple(
            (source, target)
            for source, targets in enumerate(self.outgoing_target_ordinals)
            for target in targets
        )

    def adjacency(self, *, dtype: Any = np.float64) -> np.ndarray:
        """Return A[source, target] without normalization or symmetrization."""

        n = len(self.target_source_ids)
        out = np.zeros((n, n), dtype=dtype)
        for source, target in self.edge_pairs():
            out[source, target] = 1
        return out


@dataclass(frozen=True)
class TitleAnchorBuildV1:
    schema_version: str
    normalization_version: str
    build_id: str
    paragraphs: tuple[ParagraphTargetV1, ...]
    anchors: tuple[TitleSubjectAnchorV1, ...]
    aliases: tuple[TitleAliasBindingV1, ...]
    evidence_spans: tuple[EvidenceSpanReceiptV1, ...]
    quarantined_spans: tuple[QuarantinedSpanV1, ...]
    directed_links: tuple[DirectedRoleLinkV1, ...]
    paragraph_graph: ParagraphGraphProjectionV1
    stats: dict[str, Any]


@dataclass(frozen=True)
class _BodyToken:
    normalized: str
    start: int
    end: int


@dataclass(frozen=True)
class _Match:
    token_start: int
    token_end: int
    body_start: int
    body_end: int
    alias_tokens: tuple[str, ...]


def normalized_alias_tokens(text: str) -> tuple[str, ...]:
    """Canonical title/body tokens under the declared B1 normalizer.

    NFKC and casefold remove presentation/case variation.  Unicode letters,
    numbers, and combining marks remain inside tokens; every punctuation,
    symbol, separator, and control character is a boundary.  Thus
    ``"New-York"`` and ``"Ｎｅｗ—YORK"`` normalize to ``("new", "york")``,
    while ``"Yorkshire"`` never fuzzy-matches ``"York"``.
    """

    if not isinstance(text, str):
        raise TypeError("normalizer input must be str")
    normalized = unicodedata.normalize("NFKC", text).casefold()
    tokens: list[str] = []
    current: list[str] = []
    for char in normalized:
        if unicodedata.category(char)[0] in {"L", "N", "M"}:
            current.append(char)
        elif current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tuple(tokens)


def normalize_title_alias(text: str) -> str:
    return " ".join(normalized_alias_tokens(text))


def _body_tokens_with_offsets(text: str) -> tuple[_BodyToken, ...]:
    """Tokenize original text while retaining exact original source offsets."""

    runs: list[tuple[int, int]] = []
    start: int | None = None
    for index, char in enumerate(text):
        if unicodedata.category(char)[0] in {"L", "N", "M"}:
            if start is None:
                start = index
        elif start is not None:
            runs.append((start, index))
            start = None
    if start is not None:
        runs.append((start, len(text)))

    out: list[_BodyToken] = []
    for begin, end in runs:
        # Compatibility/case normalization can expand one source run.  Each
        # resulting token still cites the exact enclosing original run.
        for token in normalized_alias_tokens(text[begin:end]):
            out.append(_BodyToken(token, begin, end))
    return tuple(out)


def _title_alias_variants(title: str) -> dict[tuple[str, ...], set[str]]:
    variants: dict[tuple[str, ...], set[str]] = {}

    def add(surface: str, derivation: str) -> None:
        tokens = normalized_alias_tokens(surface)
        if tokens:
            variants.setdefault(tokens, set()).add(derivation)

    add(title, "full_title")
    full_tokens = normalized_alias_tokens(title)
    if len(full_tokens) > 1 and full_tokens[0] in _LEADING_ARTICLES:
        variants.setdefault(full_tokens[1:], set()).add("leading_article_stripped")

    without_suffix = _PARENTHETICAL_SUFFIX_RE.sub("", title)
    if without_suffix != title:
        add(without_suffix, "parenthetical_qualifier_stripped")
        base_tokens = normalized_alias_tokens(without_suffix)
        if len(base_tokens) > 1 and base_tokens[0] in _LEADING_ARTICLES:
            variants.setdefault(base_tokens[1:], set()).add(
                "parenthetical_and_leading_article_stripped"
            )
    return variants


def _build_trie(alias_keys: Sequence[tuple[str, ...]]) -> dict:
    root: dict = {}
    for alias in sorted(alias_keys):
        node = root
        for token in alias:
            node = node.setdefault(token, {})
        node.setdefault(None, []).append(alias)
    return root


def _leftmost_longest_matches(tokens: tuple[_BodyToken, ...], trie: dict) -> tuple[_Match, ...]:
    candidates: dict[int, list[_Match]] = {}
    for start in range(len(tokens)):
        node = trie
        end = start
        while end < len(tokens) and tokens[end].normalized in node:
            node = node[tokens[end].normalized]
            end += 1
            for alias_tokens in node.get(None, ()):  # terminal aliases
                candidates.setdefault(start, []).append(_Match(
                    token_start=start,
                    token_end=end,
                    body_start=tokens[start].start,
                    body_end=tokens[end - 1].end,
                    alias_tokens=alias_tokens,
                ))

    selected: list[_Match] = []
    cursor = 0
    for start in sorted(candidates):
        if start < cursor:
            continue
        best = min(
            candidates[start],
            key=lambda match: (
                -(match.token_end - match.token_start),
                -(match.body_end - match.body_start),
                match.alias_tokens,
            ),
        )
        selected.append(best)
        cursor = best.token_end
    return tuple(selected)


def _validate_inputs(paragraphs: Sequence[ParagraphInputV1]) -> tuple[ParagraphInputV1, ...]:
    if isinstance(paragraphs, (str, bytes)) or not isinstance(paragraphs, Sequence):
        raise TypeError("paragraphs must be a sequence of ParagraphInputV1")
    checked = tuple(paragraphs)
    if not checked:
        raise ValueError("at least one paragraph is required")
    seen: set[str] = set()
    for ordinal, paragraph in enumerate(checked):
        if not isinstance(paragraph, ParagraphInputV1):
            raise TypeError(
                f"paragraphs[{ordinal}] must be ParagraphInputV1; raw QA rows are forbidden"
            )
        if not paragraph.source_id:
            raise ValueError(f"paragraphs[{ordinal}].source_id must be non-empty")
        if paragraph.source_id in seen:
            raise ValueError(f"duplicate stable source_id: {paragraph.source_id}")
        seen.add(paragraph.source_id)
        if not isinstance(paragraph.title, str) or not paragraph.title.strip():
            raise ValueError(f"paragraphs[{ordinal}].title must be non-empty str")
        if not isinstance(paragraph.text, str):
            raise TypeError(f"paragraphs[{ordinal}].text must be str")
        if not normalized_alias_tokens(paragraph.title):
            raise ValueError(f"paragraphs[{ordinal}].title has no indexable Unicode token")
    return checked


def _distribution(values: Sequence[int]) -> dict[str, int | float]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "mean": round(float(array.mean()), 4),
        "p50": int(np.percentile(array, 50)),
        "p90": int(np.percentile(array, 90)),
        "max": int(array.max()),
        "zero_count": int(np.sum(array == 0)),
    }


def _gini(values: Sequence[int]) -> float:
    array = np.sort(np.asarray(values, dtype=np.float64))
    total = float(array.sum())
    if total == 0.0:
        return 0.0
    n = array.size
    weighted = float(np.sum((np.arange(1, n + 1)) * array))
    return round((2.0 * weighted) / (n * total) - (n + 1.0) / n, 4)


def build_title_anchor_graph(paragraphs: Sequence[ParagraphInputV1]) -> TitleAnchorBuildV1:
    """Compile B1 topology from paragraph evidence only.

    The function intentionally has no embedder or evaluation-suite parameter.
    Its returned target order and unit text are therefore cache-compatible but
    cannot be changed by query/answer/gold metadata.
    """

    inputs = _validate_inputs(paragraphs)
    targets = tuple(
        ParagraphTargetV1(
            ordinal=ordinal,
            source_id=paragraph.source_id,
            title=paragraph.title,
            text=paragraph.text,
            unit_text=f"{paragraph.title} :: {paragraph.text}",
            title_sha256=sha256_text(paragraph.title),
            text_sha256=sha256_text(paragraph.text),
        )
        for ordinal, paragraph in enumerate(inputs)
    )
    ordinal_by_source = {target.source_id: target.ordinal for target in targets}

    anchors: list[TitleSubjectAnchorV1] = []
    anchor_by_source: dict[str, TitleSubjectAnchorV1] = {}
    alias_derivations: dict[tuple[tuple[str, ...], str], set[str]] = {}
    alias_targets: dict[tuple[str, ...], set[str]] = {}
    for paragraph in inputs:
        anchor_payload = {
            "source_id": paragraph.source_id,
            "role": SUBJECT_ROLE,
            "title_sha256": sha256_text(paragraph.title),
        }
        anchor = TitleSubjectAnchorV1(
            anchor_id=content_id("title_anchor", anchor_payload),
            source_id=paragraph.source_id,
            role=SUBJECT_ROLE,
            title_start=0,
            title_end=len(paragraph.title),
            exact_title=paragraph.title,
            normalized_title=normalize_title_alias(paragraph.title),
        )
        anchors.append(anchor)
        anchor_by_source[paragraph.source_id] = anchor
        for alias_tokens, derivations in _title_alias_variants(paragraph.title).items():
            alias_targets.setdefault(alias_tokens, set()).add(paragraph.source_id)
            alias_derivations.setdefault((alias_tokens, paragraph.source_id), set()).update(derivations)

    aliases: list[TitleAliasBindingV1] = []
    alias_id_by_key_source: dict[tuple[tuple[str, ...], str], str] = {}
    for alias_tokens, source_id in sorted(
        alias_derivations,
        key=lambda item: (ordinal_by_source[item[1]], item[0]),
    ):
        payload = {
            "source_id": source_id,
            "normalized_tokens": alias_tokens,
            "normalization_version": NORMALIZATION_VERSION,
        }
        alias_id = content_id("title_alias", payload)
        alias_id_by_key_source[(alias_tokens, source_id)] = alias_id
        aliases.append(TitleAliasBindingV1(
            alias_id=alias_id,
            source_id=source_id,
            normalized_alias=" ".join(alias_tokens),
            normalized_tokens=alias_tokens,
            derivations=tuple(sorted(alias_derivations[(alias_tokens, source_id)])),
        ))

    trie = _build_trie(tuple(alias_targets))
    evidence: list[EvidenceSpanReceiptV1] = []
    quarantined: list[QuarantinedSpanV1] = []
    receipt_ids_by_pair: dict[tuple[str, str], list[str]] = {}
    self_reference_spans = 0
    selected_spans = 0
    selected_characters = 0
    linked_characters = 0
    paragraphs_with_selected: set[str] = set()
    paragraphs_with_link: set[str] = set()

    for paragraph in inputs:
        matches = _leftmost_longest_matches(_body_tokens_with_offsets(paragraph.text), trie)
        for match in matches:
            selected_spans += 1
            selected_characters += match.body_end - match.body_start
            paragraphs_with_selected.add(paragraph.source_id)
            exact = paragraph.text[match.body_start:match.body_end]
            prefix = paragraph.text[max(0, match.body_start - 32):match.body_start]
            suffix = paragraph.text[match.body_end:match.body_end + 32]
            normalized = " ".join(match.alias_tokens)
            candidate_ids = tuple(sorted(
                alias_targets[match.alias_tokens], key=ordinal_by_source.__getitem__
            ))
            candidate_alias_ids = tuple(
                alias_id_by_key_source[(match.alias_tokens, candidate_id)]
                for candidate_id in candidate_ids
            )
            if len(candidate_ids) != 1:
                payload = {
                    "source_id": paragraph.source_id,
                    "body_start": match.body_start,
                    "body_end": match.body_end,
                    "normalized_alias": normalized,
                    "candidate_source_ids": candidate_ids,
                    "candidate_alias_ids": candidate_alias_ids,
                    "reason": "ambiguous_alias",
                    "source_text_sha256": sha256_text(paragraph.text),
                }
                quarantined.append(QuarantinedSpanV1(
                    quarantine_id=content_id("title_alias_quarantine", payload),
                    source_id=paragraph.source_id,
                    body_start=match.body_start,
                    body_end=match.body_end,
                    exact_quote=exact,
                    prefix=prefix,
                    suffix=suffix,
                    normalized_alias=normalized,
                    candidate_source_ids=candidate_ids,
                    candidate_alias_ids=candidate_alias_ids,
                    reason="ambiguous_alias",
                    offset_unit=OFFSET_UNIT,
                    source_text_sha256=sha256_text(paragraph.text),
                ))
                continue

            object_source_id = candidate_ids[0]
            disposition = (
                "self_reference" if object_source_id == paragraph.source_id else "linked"
            )
            payload = {
                "source_id": paragraph.source_id,
                "object_source_id": object_source_id,
                "object_alias_id": candidate_alias_ids[0],
                "body_start": match.body_start,
                "body_end": match.body_end,
                "normalized_alias": normalized,
                "source_text_sha256": sha256_text(paragraph.text),
                "disposition": disposition,
            }
            receipt = EvidenceSpanReceiptV1(
                receipt_id=content_id("title_alias_evidence", payload),
                source_id=paragraph.source_id,
                subject_anchor_id=anchor_by_source[paragraph.source_id].anchor_id,
                object_source_id=object_source_id,
                object_alias_id=candidate_alias_ids[0],
                subject_role=SUBJECT_ROLE,
                object_role=OBJECT_ROLE,
                body_start=match.body_start,
                body_end=match.body_end,
                exact_quote=exact,
                prefix=prefix,
                suffix=suffix,
                normalized_alias=normalized,
                offset_unit=OFFSET_UNIT,
                source_text_sha256=sha256_text(paragraph.text),
                disposition=disposition,
            )
            evidence.append(receipt)
            if disposition == "self_reference":
                self_reference_spans += 1
            else:
                receipt_ids_by_pair.setdefault(
                    (paragraph.source_id, object_source_id), []
                ).append(receipt.receipt_id)
                linked_characters += match.body_end - match.body_start
                paragraphs_with_link.add(paragraph.source_id)

    links: list[DirectedRoleLinkV1] = []
    for (subject, object_), receipt_ids in sorted(
        receipt_ids_by_pair.items(),
        key=lambda item: (
            ordinal_by_source[item[0][0]], ordinal_by_source[item[0][1]]
        ),
    ):
        payload = {
            "subject_source_id": subject,
            "object_source_id": object_,
            "subject_role": SUBJECT_ROLE,
            "object_role": OBJECT_ROLE,
            "evidence_receipt_ids": tuple(sorted(receipt_ids)),
        }
        links.append(DirectedRoleLinkV1(
            link_id=content_id("title_anchor_link", payload),
            subject_source_id=subject,
            subject_anchor_id=anchor_by_source[subject].anchor_id,
            subject_role=SUBJECT_ROLE,
            object_source_id=object_,
            object_anchor_id=anchor_by_source[object_].anchor_id,
            object_role=OBJECT_ROLE,
            evidence_receipt_ids=tuple(sorted(receipt_ids)),
        ))

    outgoing: list[list[int]] = [[] for _ in targets]
    indegree = [0] * len(targets)
    for link in links:
        source_ordinal = ordinal_by_source[link.subject_source_id]
        object_ordinal = ordinal_by_source[link.object_source_id]
        outgoing[source_ordinal].append(object_ordinal)
        indegree[object_ordinal] += 1
    outgoing_tuples = tuple(tuple(sorted(set(values))) for values in outgoing)
    outdegree = [len(values) for values in outgoing_tuples]
    graph = ParagraphGraphProjectionV1(
        target_source_ids=tuple(target.source_id for target in targets),
        unit_texts=tuple(target.unit_text for target in targets),
        outgoing_target_ordinals=outgoing_tuples,
    )

    body_characters = sum(len(paragraph.text) for paragraph in inputs)
    ambiguous_keys = tuple(
        key for key, candidate_ids in alias_targets.items() if len(candidate_ids) > 1
    )
    hub_order = sorted(
        range(len(targets)),
        key=lambda ordinal: (-indegree[ordinal], ordinal),
    )[:5]
    stats: dict[str, Any] = {
        "n_paragraphs": len(targets),
        "n_title_alias_bindings": len(aliases),
        "n_unique_alias_keys": len(alias_targets),
        "n_directed_links": len(links),
        "n_evidence_spans": len(evidence),
        "span_coverage": {
            "selected_spans": selected_spans,
            "linked_spans": sum(x.disposition == "linked" for x in evidence),
            "self_reference_spans": self_reference_spans,
            "selected_characters": selected_characters,
            "linked_characters": linked_characters,
            "body_characters": body_characters,
            "selected_char_fraction": round(
                selected_characters / max(body_characters, 1), 6
            ),
            "linked_char_fraction": round(
                linked_characters / max(body_characters, 1), 6
            ),
            "paragraphs_with_selected_span": len(paragraphs_with_selected),
            "paragraphs_with_link": len(paragraphs_with_link),
            "paragraph_link_fraction": round(
                len(paragraphs_with_link) / len(targets), 6
            ),
        },
        "outdegree": _distribution(outdegree),
        "hubs": {
            "indegree": _distribution(indegree),
            "gini": _gini(indegree),
            "top": tuple(
                {
                    "source_id": targets[ordinal].source_id,
                    "title": targets[ordinal].title,
                    "indegree": indegree[ordinal],
                }
                for ordinal in hub_order
            ),
        },
        "alias_ambiguity": {
            "ambiguous_alias_keys": len(ambiguous_keys),
            "ambiguous_alias_bindings": sum(
                len(alias_targets[key]) for key in ambiguous_keys
            ),
            "quarantined_spans": len(quarantined),
            "quarantined_characters": sum(
                span.body_end - span.body_start for span in quarantined
            ),
        },
        "normalization_version": NORMALIZATION_VERSION,
        "offset_unit": OFFSET_UNIT,
        "input_fields": ("source_id", "title", "text"),
    }

    build_payload = {
        "schema_version": SCHEMA_VERSION,
        "normalization_version": NORMALIZATION_VERSION,
        "paragraphs": tuple(
            {
                "ordinal": target.ordinal,
                "source_id": target.source_id,
                "title_sha256": target.title_sha256,
                "text_sha256": target.text_sha256,
            }
            for target in targets
        ),
        "aliases": tuple(alias.alias_id for alias in aliases),
        "evidence": tuple(receipt.receipt_id for receipt in evidence),
        "quarantines": tuple(span.quarantine_id for span in quarantined),
        "links": tuple(link.link_id for link in links),
    }
    # Assert serializability here so descriptive stats cannot quietly acquire a
    # non-deterministic/non-finite value later.
    canonical_json(stats)
    build_id = content_id("title_anchor_build", build_payload)
    return TitleAnchorBuildV1(
        schema_version=SCHEMA_VERSION,
        normalization_version=NORMALIZATION_VERSION,
        build_id=build_id,
        paragraphs=targets,
        anchors=tuple(anchors),
        aliases=tuple(aliases),
        evidence_spans=tuple(evidence),
        quarantined_spans=tuple(quarantined),
        directed_links=tuple(links),
        paragraph_graph=graph,
        stats=stats,
    )


def verify_title_anchor_build(build: TitleAnchorBuildV1) -> tuple[str, ...]:
    """Cheap evidence/topology integrity verifier for comparator admission."""

    issues: list[str] = []
    if build.schema_version != SCHEMA_VERSION:
        issues.append("schema_version_mismatch")
    if build.normalization_version != NORMALIZATION_VERSION:
        issues.append("normalization_version_mismatch")
    source_by_id = {paragraph.source_id: paragraph for paragraph in build.paragraphs}
    anchor_by_id = {anchor.anchor_id: anchor for anchor in build.anchors}
    alias_by_id = {alias.alias_id: alias for alias in build.aliases}
    receipt_by_id = {receipt.receipt_id: receipt for receipt in build.evidence_spans}
    if len(source_by_id) != len(build.paragraphs):
        issues.append("duplicate_source_id")
    if build.paragraph_graph.target_source_ids != tuple(
        paragraph.source_id for paragraph in build.paragraphs
    ):
        issues.append("target_order_mismatch")
    if build.paragraph_graph.unit_texts != tuple(
        paragraph.unit_text for paragraph in build.paragraphs
    ):
        issues.append("unit_text_order_mismatch")

    expected_pairs: set[tuple[str, str]] = set()
    for receipt in build.evidence_spans:
        paragraph = source_by_id.get(receipt.source_id)
        if paragraph is None:
            issues.append(f"dangling_receipt_source:{receipt.receipt_id}")
            continue
        if paragraph.text[receipt.body_start:receipt.body_end] != receipt.exact_quote:
            issues.append(f"receipt_quote_mismatch:{receipt.receipt_id}")
        if sha256_text(paragraph.text) != receipt.source_text_sha256:
            issues.append(f"receipt_source_hash_mismatch:{receipt.receipt_id}")
        if receipt.subject_anchor_id not in anchor_by_id:
            issues.append(f"dangling_subject_anchor:{receipt.receipt_id}")
        if receipt.object_source_id not in source_by_id:
            issues.append(f"dangling_object_source:{receipt.receipt_id}")
        alias = alias_by_id.get(receipt.object_alias_id)
        if alias is None:
            issues.append(f"dangling_object_alias:{receipt.receipt_id}")
        elif (
            alias.source_id != receipt.object_source_id
            or alias.normalized_alias != receipt.normalized_alias
        ):
            issues.append(f"object_alias_binding_mismatch:{receipt.receipt_id}")
        if receipt.disposition == "linked":
            expected_pairs.add((receipt.source_id, receipt.object_source_id))

    actual_pairs: set[tuple[str, str]] = set()
    for link in build.directed_links:
        pair = (link.subject_source_id, link.object_source_id)
        actual_pairs.add(pair)
        if link.subject_role != SUBJECT_ROLE or link.object_role != OBJECT_ROLE:
            issues.append(f"link_role_mismatch:{link.link_id}")
        if link.subject_anchor_id not in anchor_by_id or link.object_anchor_id not in anchor_by_id:
            issues.append(f"dangling_link_anchor:{link.link_id}")
        if not link.evidence_receipt_ids:
            issues.append(f"link_without_evidence:{link.link_id}")
        for receipt_id in link.evidence_receipt_ids:
            receipt = receipt_by_id.get(receipt_id)
            if receipt is None:
                issues.append(f"dangling_link_receipt:{link.link_id}")
            elif (receipt.source_id, receipt.object_source_id) != pair:
                issues.append(f"link_receipt_pair_mismatch:{link.link_id}")
    if actual_pairs != expected_pairs:
        issues.append("link_pair_projection_mismatch")

    for span in build.quarantined_spans:
        paragraph = source_by_id.get(span.source_id)
        if paragraph is None:
            issues.append(f"dangling_quarantine_source:{span.quarantine_id}")
            continue
        if paragraph.text[span.body_start:span.body_end] != span.exact_quote:
            issues.append(f"quarantine_quote_mismatch:{span.quarantine_id}")
        if sha256_text(paragraph.text) != span.source_text_sha256:
            issues.append(f"quarantine_source_hash_mismatch:{span.quarantine_id}")
        if len(span.candidate_source_ids) != len(span.candidate_alias_ids):
            issues.append(f"quarantine_candidate_length_mismatch:{span.quarantine_id}")
        for source_id, alias_id in zip(
            span.candidate_source_ids, span.candidate_alias_ids, strict=True
        ):
            alias = alias_by_id.get(alias_id)
            if alias is None or alias.source_id != source_id:
                issues.append(f"quarantine_alias_binding_mismatch:{span.quarantine_id}")

    graph_pairs = {
        (
            build.paragraph_graph.target_source_ids[source],
            build.paragraph_graph.target_source_ids[target],
        )
        for source, target in build.paragraph_graph.edge_pairs()
    }
    if graph_pairs != actual_pairs:
        issues.append("paragraph_graph_projection_mismatch")
    if not all(math.isfinite(float(value)) for block in (
        build.stats.get("outdegree", {}),
        build.stats.get("hubs", {}).get("indegree", {}),
    ) for value in block.values() if isinstance(value, (int, float))):
        issues.append("nonfinite_stats")
    return tuple(sorted(set(issues)))
