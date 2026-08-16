"""Deterministic HippoRAG OpenIE versus HSWM V5 extraction audit.

This is a schema/coverage comparison, not a downstream efficacy benchmark.
Only documents whose normalized title and body are identical in both inputs
are compared.  The raw surface-chain counts intentionally do not claim to be
legal H3 chains; they omit the typed composition and query-admission gates.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Iterable
import unicodedata


SCHEMA_VERSION = "hswm-oss-extraction-comparison/v1"


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", " ", value).strip()


def _contains_exact_normalized(needle: str, haystack: str) -> bool:
    return _normalize(needle) in _normalize(haystack)


def _percent(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(100.0 * numerator / denominator, 4)


def _latest_v5_records(journal_path: Path) -> list[dict[str, Any]]:
    latest: dict[str, tuple[tuple[int, str], dict[str, Any]]] = {}
    with journal_path.open(encoding="utf-8") as stream:
        for line in stream:
            event = json.loads(line)
            if event.get("event_type") != "FINALIZE":
                continue
            for record in event.get("records", []):
                source_id = str(record["source_id"])
                order_key = (
                    int(record.get("attempt_ordinal") or 0),
                    str(record.get("record_id") or ""),
                )
                if source_id not in latest or order_key > latest[source_id][0]:
                    latest[source_id] = (order_key, record)
    return [latest[source_id][1] for source_id in sorted(latest)]


def _decode_v5_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    decoded = []
    for record in records:
        source_input = json.loads(record["source_input_json"])
        frozen = record.get("frozen_extraction")
        payload = (
            json.loads(frozen["payload_json"])
            if frozen is not None
            else {"claims": []}
        )
        decoded.append(
            {
                "input": source_input,
                "record": record,
                "claims": payload.get("claims", []),
            }
        )
    return decoded


def _aligned_pairs(
    hipporag_docs: list[dict[str, Any]],
    v5_docs: list[dict[str, Any]],
) -> list[tuple[int, int]]:
    hipporag_by_material: dict[tuple[str, str], list[int]] = defaultdict(list)
    v5_by_material: dict[tuple[str, str], list[int]] = defaultdict(list)
    for index, document in enumerate(hipporag_docs):
        hipporag_by_material[
            (_normalize(document["title"]), _normalize(document["text"]))
        ].append(index)
    for index, document in enumerate(v5_docs):
        source_input = document["input"]
        v5_by_material[
            (_normalize(source_input["title"]), _normalize(source_input["text"]))
        ].append(index)

    pairs: list[tuple[int, int]] = []
    for material_key in sorted(set(hipporag_by_material) & set(v5_by_material)):
        pairs.extend(
            zip(
                sorted(v5_by_material[material_key]),
                sorted(hipporag_by_material[material_key]),
            )
        )
    return pairs


def _surface_connectivity(edges: list[tuple[str, str]]) -> dict[str, int]:
    outgoing: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for index, (source, target) in enumerate(edges):
        outgoing[source].append((index, target))

    composable = 0
    nonself_nonbacktrack = 0
    for first_index, (source, join) in enumerate(edges):
        for second_index, target in outgoing.get(join, []):
            if first_index == second_index:
                continue
            composable += 1
            if source != join and target != source and target != join:
                nonself_nonbacktrack += 1
    return {
        "directed_edges": len(edges),
        "raw_composable_pairs": composable,
        "nonself_nonbacktrack_pairs": nonself_nonbacktrack,
    }


def compare(hipporag_json: Path, v5_journal: Path) -> dict[str, Any]:
    hipporag_payload = json.loads(hipporag_json.read_text(encoding="utf-8"))
    hipporag_docs = hipporag_payload["docs"]
    v5_docs = _decode_v5_records(_latest_v5_records(v5_journal))
    pairs = _aligned_pairs(hipporag_docs, v5_docs)

    counts: Counter[str] = Counter()
    hipporag_edges: list[tuple[str, str]] = []
    v5_edges: list[tuple[str, str]] = []

    for v5_index, hipporag_index in pairs:
        v5_doc = v5_docs[v5_index]
        hipporag_doc = hipporag_docs[hipporag_index]
        body = hipporag_doc["text"]
        passage = f"{hipporag_doc['title']}\n{body}"
        entities = hipporag_doc.get("extracted_entities") or []
        triples = hipporag_doc.get("extracted_triples") or []

        counts["hippo_docs_with_output"] += int(bool(entities or triples))
        counts["hippo_entities"] += len(entities)
        counts["hippo_entity_body_exact"] += sum(
            _contains_exact_normalized(entity, body) for entity in entities
        )
        counts["hippo_entity_passage_exact"] += sum(
            _contains_exact_normalized(entity, passage) for entity in entities
        )
        counts["hippo_triples"] += len(triples)

        for triple in triples:
            if not isinstance(triple, list) or len(triple) != 3:
                continue
            subject, predicate, object_ = triple
            hipporag_edges.append((_normalize(subject), _normalize(object_)))
            counts["hippo_endpoints"] += 2
            counts["hippo_endpoint_body_exact"] += int(
                _contains_exact_normalized(subject, body)
            ) + int(_contains_exact_normalized(object_, body))
            counts["hippo_endpoint_passage_exact"] += int(
                _contains_exact_normalized(subject, passage)
            ) + int(_contains_exact_normalized(object_, passage))
            counts["hippo_predicate_body_exact"] += int(
                _contains_exact_normalized(predicate, body)
            )

        claims = v5_doc["claims"]
        counts["v5_docs_with_claims"] += int(bool(claims))
        counts["v5_claims"] += len(claims)
        counts["v5_quarantines"] += len(v5_doc["record"].get("quarantines") or [])
        source_text = v5_doc["input"]["text"]
        for claim in claims:
            arguments = claim.get("arguments") or []
            counts["v5_nary_2plus_args"] += int(len(arguments) >= 2)
            roles = [claim["subject"], claim["predicate"], *arguments]
            for role in roles:
                counts["v5_role_spans"] += 1
                counts["v5_offset_exact"] += int(
                    source_text[int(role["start"]) : int(role["end"])]
                    == role["exact"]
                )
            for argument in arguments:
                v5_edges.append(
                    (
                        _normalize(claim["subject"]["exact"]),
                        _normalize(argument["exact"]),
                    )
                )

    statuses = Counter(doc["record"].get("status") for doc in v5_docs)
    return {
        "schema_version": SCHEMA_VERSION,
        "scope": (
            "exact NFKC-casefold-whitespace-normalized title+body "
            "multiset intersection only"
        ),
        "hipporag_json": str(hipporag_json),
        "hipporag_sha256": sha256(hipporag_json.read_bytes()).hexdigest(),
        "v5_journal": str(v5_journal),
        "v5_journal_sha256": sha256(v5_journal.read_bytes()).hexdigest(),
        "hipporag_total_docs": len(hipporag_docs),
        "v5_unique_sources": len(v5_docs),
        "aligned_docs": len(pairs),
        "v5_global_status": dict(sorted(statuses.items())),
        "aligned_counts": dict(sorted(counts.items())),
        "aligned_rates_pct": {
            "hippo_entity_body_exact": _percent(
                counts["hippo_entity_body_exact"], counts["hippo_entities"]
            ),
            "hippo_entity_title_plus_body_exact": _percent(
                counts["hippo_entity_passage_exact"], counts["hippo_entities"]
            ),
            "hippo_endpoint_body_exact": _percent(
                counts["hippo_endpoint_body_exact"], counts["hippo_endpoints"]
            ),
            "hippo_endpoint_title_plus_body_exact": _percent(
                counts["hippo_endpoint_passage_exact"], counts["hippo_endpoints"]
            ),
            "hippo_predicate_body_exact": _percent(
                counts["hippo_predicate_body_exact"], counts["hippo_triples"]
            ),
            "v5_offset_exact": _percent(
                counts["v5_offset_exact"], counts["v5_role_spans"]
            ),
            "v5_claims_with_2plus_arguments": _percent(
                counts["v5_nary_2plus_args"], counts["v5_claims"]
            ),
        },
        "raw_surface_connectivity_not_h3_legal_chain": {
            "hipporag": _surface_connectivity(hipporag_edges),
            "v5": _surface_connectivity(v5_edges),
        },
        "interpretation_limits": [
            "substring exactness is not factual correctness",
            (
                "raw surface pairs do not apply H3 claim-continuity, role, "
                "query, fanout, or cycle gates"
            ),
            (
                "public HippoRAG output and V5 use different extractors; this "
                "is a schema/coverage comparison, not downstream efficacy"
            ),
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hipporag-json", type=Path, required=True)
    parser.add_argument("--v5-journal", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.dumps(
        compare(args.hipporag_json, args.v5_journal),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    if args.output is None:
        print(payload, end="")
    else:
        args.output.write_text(payload, encoding="utf-8")


if __name__ == "__main__":
    main()
