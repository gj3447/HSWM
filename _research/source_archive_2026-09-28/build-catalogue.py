#!/usr/bin/env python3
"""Build the public, metadata-only external-source archive catalogue.

This utility never opens a URL or a private blob.  It joins the checked-in v2
inventory with already-written private archive receipts and validation metadata.
The output is deliberately a read-only research/KG projection, not a statement
that a cited source is true, licensed for redistribution, or useful for HSWM.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


DATE = "2026-09-28"
ARCHIVE_SCHEMA = "hswm-external-source-archive-catalogue/v1"
KG_SCHEMA = "hswm-external-source-archive-kg/v1"
MAX_NATIVE_SOURCE_BYTES = 16 * 1024 * 1024
RESEARCH = Path("_research/source_archive_2026-09-28")
PRIVATE_ARCHIVE = Path(".hswm-local/research-source-archive-20260928")
ONTOLOGY = Path("ontology/development/HSWM_EXTERNAL_SOURCE_ARCHIVE_2026-09-28.v1.json")
PROVENANCE = RESEARCH / "retrieval-provenance.v1.jsonld"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def stable_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def safe_collection_name(private_root: Path, manifest_path: Path) -> str:
    parent = manifest_path.parent
    rel = parent.relative_to(private_root)
    return "base" if str(rel) == "." else "-".join(rel.parts)


def public_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    """Drop private blob locations while retaining byte identity and HTTP metadata."""
    allowed = (
        "status", "id", "originalUrl", "requestedUrl", "finalUrl", "retrievedAt",
        "responseHeaders", "sha256", "size", "expectedKind", "maximumBytes", "transport",
        "metadata", "failure", "detail",
    )
    return {key: receipt[key] for key in allowed if key in receipt}


def receipt_key(collection: str, receipt: dict[str, Any]) -> str:
    return sha256_bytes(f"{collection}\x00{receipt.get('id', '')}\x00{receipt.get('originalUrl', '')}".encode())


def node_uid(kind: str, stable_key: str) -> str:
    # All generated keys are SHA-256 hex, therefore already within native UID grammar.
    return f"sym:Concept:source-archive-{kind}-{stable_key}"


def node(
    uid: str,
    name: str,
    description: str,
    role: str,
    status: str,
    **extra: str | bool | int | list[str],
) -> dict[str, Any]:
    props: dict[str, Any] = {
        "name": name,
        "description": description,
        "standard_graph_role": role,
        "authority_class": "SECONDARY_AI",
        "ontology_authority_class_v1": "SECONDARY_AI",
        "ontology_record_lifecycle_v1": "ACTIVE",
        "ontology_sensitivity_v1": "NORMAL",
        "ontology_review_required_v1": True,
        "responsibility_owner": "hswm:research:external-source-archive",
        "status": status,
        "claim_boundary": "RETRIEVAL_METADATA_AND_BYTE_BINDING_ONLY_NOT_SOURCE_TRUTH_NOT_LICENSE_GRANT_NOT_HSWM_EFFICACY",
        "projection_nonclaim": "NOT_RUNTIME_STATE_NOT_CANONICAL_LEARNING_NOT_WORLD_TRUTH",
    }
    props.update(extra)
    return {"uid": uid, "labels": ["Concept"], "properties": props}


def relation(from_uid: str, to_uid: str, kind: str, scope: str) -> dict[str, str]:
    return {
        "from_uid": from_uid,
        "to_uid": to_uid,
        "type": kind,
        "authority_class": "SECONDARY_AI",
        "scope": scope,
        "status": "PROJECTION_ONLY",
    }


def validation_index(validation: dict[str, Any] | None, item_key: str) -> dict[str, dict[str, Any]]:
    if validation is None:
        return {}
    entries = validation.get(item_key, [])
    if not isinstance(entries, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("sha256"), str):
            result[entry["sha256"]] = entry
    return result


def capture_status(
    receipt: dict[str, Any],
    combined: dict[str, dict[str, Any]],
    html: dict[str, dict[str, Any]],
    pdf: dict[str, dict[str, Any]],
) -> tuple[str, str, bool, str]:
    """Return (projection status, representation, usable, exact validation status).

    The combined audit is authoritative when present.  It is intentionally
    fail-closed: only a structurally readable PDF or a non-challenge HTML
    capture counts towards useful retrieval completeness.  The latter remains
    a landing-page representation, never a full-text assertion.
    """
    if receipt.get("status") != "ARCHIVED":
        return ("RETRIEVAL_FAILED", "NONE", False, "NOT_ARCHIVED")
    digest = receipt.get("sha256")
    if not isinstance(digest, str):
        return ("INVALID_RECEIPT", "NONE", False, "MISSING_SHA256")
    combined_entry = combined.get(digest)
    if combined_entry is not None:
        exact = str(combined_entry.get("status", "INVALID_VALIDATION_RECORD"))
        if exact == "VALID_PDF":
            return (exact, "PDF_PARSED", True, exact)
        if exact == "HTML_CAPTURED_NOT_FULLTEXT_VALIDATED":
            return (exact, "LANDING_HTML", True, exact)
        if exact == "HTML_CHALLENGE_PAGE":
            return (exact, "LANDING_HTML", False, exact)
        if exact == "OTHER_CAPTURED_MEDIA":
            # The digest is a valid captured response and therefore counts as
            # retrieval coverage, while explicitly remaining outside full-text
            # coverage and PDF/HTML semantic interpretation.
            return (exact, "OTHER_CAPTURED_MEDIA", True, exact)
        # Preserve the audit's precise status for queries while never allowing
        # malformed bindings, invalid PDF payloads, or other errors to count.
        return (exact, "NONE", False, exact)
    html_entry = html.get(digest)
    if html_entry is not None:
        if html_entry.get("status") == "CHALLENGE_PAGE":
            return ("HTML_CHALLENGE_PAGE", "LANDING_HTML", False, "CHALLENGE_PAGE")
        if html_entry.get("status") == "CAPTURED_HTML_NOT_FULLTEXT_VALIDATED":
            return ("HTML_CAPTURED_NOT_FULLTEXT_VALIDATED", "LANDING_HTML", True, "CAPTURED_HTML_NOT_FULLTEXT_VALIDATED")
        exact = str(html_entry.get("status", "INVALID_HTML_VALIDATION"))
        return (exact, "NONE", False, exact)
    pdf_entry = pdf.get(digest)
    if pdf_entry is not None:
        if pdf_entry.get("status") == "VALID_PDF":
            return ("VALID_PDF", "PDF_PARSED", True, "VALID_PDF")
        exact = str(pdf_entry.get("status", "INVALID_PDF_VALIDATION"))
        return (exact, "NONE", False, exact)
    # A receipt without an audit record stays visible but cannot establish a
    # useful capture.  MIME is merely a transport declaration.
    return ("CAPTURE_UNVALIDATED", "NONE", False, "NO_VALIDATION_RECORD")


def checked_binding(root: Path, path: Path) -> dict[str, str]:
    data = path.read_bytes()
    return {"path": relative(root, path), "sha256": sha256_bytes(data)}


def locate_validation(root: Path) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None, list[Path]]:
    combined = root / RESEARCH / "captures-validation.v1.json"
    html_path = root / RESEARCH / "html-validation.v1.json"
    pdf_path = root / RESEARCH / "pdf-validation.v1.json"
    if combined.exists():
        value = load_json(combined)
        return value, None, None, [combined]
    return (None,
            load_json(html_path) if html_path.exists() else None,
            load_json(pdf_path) if pdf_path.exists() else None,
            [path for path in (html_path, pdf_path) if path.exists()])


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_bytes(stable_json(value))
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".", help="repository root")
    parser.add_argument("--output-root", required=True, help="root for generated public metadata")
    parser.add_argument("--check-only", action="store_true", help="validate and report, without writing")
    args = parser.parse_args()
    root = Path(args.repo).resolve()
    output_root = Path(args.output_root).resolve()
    inventory_path = root / RESEARCH / "inventory.v2.json"
    supplement_paths = sorted((root / RESEARCH).glob("supplement.v*.json"))
    recovery_path = root / RESEARCH / "recovery-candidates.v1.json"
    inventory = load_json(inventory_path)
    supplements = [load_json(path) for path in supplement_paths]
    if not supplement_paths:
        raise ValueError("at least one supplement manifest is required")
    combined_validation, html_validation, pdf_validation, validation_paths = locate_validation(root)
    combined = validation_index(combined_validation, "bodies")
    html = validation_index(html_validation, "html")
    pdf = validation_index(pdf_validation, "pdfs")
    sources = inventory.get("sources")
    if not isinstance(sources, list) or len(sources) != 852:
        raise ValueError("inventory.v2 must contain exactly 852 canonical sources")
    inventory_by_id = {entry.get("id"): entry for entry in sources if isinstance(entry, dict)}
    if len(inventory_by_id) != 852 or any(not isinstance(key, str) for key in inventory_by_id):
        raise ValueError("inventory source IDs must be unique strings")

    private_root = root / PRIVATE_ARCHIVE
    manifests = sorted(private_root.glob("**/manifest.receipt.v1.json"))
    if not manifests:
        raise ValueError("no private archive manifest receipts found")
    receipts_by_id: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    collection_receipts: dict[str, dict[str, Any]] = {}
    receipt_manifest_bindings: list[dict[str, str]] = []
    for manifest_path in manifests:
        manifest = load_json(manifest_path)
        collection = safe_collection_name(private_root, manifest_path)
        if collection in collection_receipts:
            raise ValueError(f"duplicate collection name: {collection}")
        raw = manifest.get("receipts")
        if not isinstance(raw, list):
            raise ValueError(f"{manifest_path}: receipts must be an array")
        copied: list[dict[str, Any]] = []
        for receipt in raw:
            if not isinstance(receipt, dict) or not isinstance(receipt.get("id"), str):
                raise ValueError(f"{manifest_path}: malformed receipt")
            copied.append(public_receipt(receipt))
            receipts_by_id[receipt["id"]].append((collection, receipt))
        collection_receipts[collection] = {
            "schemaVersion": "hswm-external-source-archive-public-receipts/v1",
            "collection": collection,
            "sourceInputManifestSha256": str(manifest.get("manifestSha256", "")),
            "sourcePrivateManifestSha256": sha256_bytes(manifest_path.read_bytes()),
            "sourcePrivateManifestCreatedAt": str(manifest.get("createdAt", "")),
            "receipts": sorted(copied, key=lambda item: (str(item.get("id")), str(item.get("originalUrl")))),
        }
        # The raw manifest remains private.  Its digest is metadata carried by
        # the public receipt projection, not a repository artifact binding.
        receipt_manifest_bindings.append({
            "collection": collection,
            "sha256": sha256_bytes(manifest_path.read_bytes()),
        })

    source_rows: list[dict[str, Any]] = list(sources)
    already_archived_links: list[dict[str, Any]] = []
    for supplement in supplements:
        supplement_sources = supplement.get("sources", [])
        if not isinstance(supplement_sources, list):
            raise ValueError("supplement sources must be an array")
        source_rows.extend(item for item in supplement_sources if isinstance(item, dict))
        links = supplement.get("alreadyArchivedFullTextLinks", [])
        if not isinstance(links, list):
            raise ValueError("supplement alreadyArchivedFullTextLinks must be an array")
        already_archived_links.extend(item for item in links if isinstance(item, dict))
    source_by_id: dict[str, dict[str, Any]] = {}
    for entry in source_rows:
        identifier = entry.get("id")
        url = entry.get("url")
        if not isinstance(identifier, str) or not isinstance(url, str):
            raise ValueError("every inventory/supplement source requires id and url")
        previous = source_by_id.get(identifier)
        if previous is not None and previous.get("url") != url:
            raise ValueError(f"source ID has conflicting URLs: {identifier}")
        # The canonical inventory owns citations.  Supplement metadata augments
        # rather than overwrites that original citation evidence.
        if previous is not None:
            merged = dict(previous)
            for key, value in entry.items():
                if key in {"citations", "derivedFrom"}:
                    merged[key] = list(previous.get(key, [])) + list(value if isinstance(value, list) else [])
                elif key not in merged:
                    merged[key] = value
            source_by_id[identifier] = merged
        else:
            source_by_id[identifier] = entry
    source_ids_by_url: dict[str, list[str]] = defaultdict(list)
    for source_id, entry in source_by_id.items():
        source_ids_by_url[str(entry["url"])].append(source_id)

    catalogue_sources: list[dict[str, Any]] = []
    source_nodes: dict[str, str] = {}
    for source_id, entry in sorted(source_by_id.items()):
        url = str(entry["url"])
        source_nodes[source_id] = node_uid("source", sha256_bytes(url.encode()))
        attempts = receipts_by_id.get(source_id, [])
        capture_details = [capture_status(receipt, combined, html, pdf) for _, receipt in attempts]
        captures = [detail[0] for detail in capture_details]
        validation_statuses = [detail[3] for detail in capture_details]
        usable_capture = any(detail[2] for detail in capture_details)
        catalogue_sources.append({
            "id": source_id,
            "url": url,
            "expectedKind": entry.get("expectedKind", "any"),
            "inventoryRole": "CANONICAL_852" if source_id in inventory_by_id else "SUPPLEMENTARY_DERIVED_FULLTEXT",
            "citations": entry.get("citations", []),
            "derivedFrom": entry.get("derivedFrom", []),
            "receiptRefs": [{"collection": collection, "receiptId": receipt.get("id"), "receiptKey": receipt_key(collection, receipt)} for collection, receipt in attempts],
            "captureStatuses": sorted(set(captures)),
            "validationStatuses": sorted(set(validation_statuses)),
            "inCanonicalInventory": source_id in inventory_by_id,
            "currentCaptureStatus": "CAPTURED" if usable_capture else "UNAVAILABLE",
        })

    canonical_rows = [row for row in catalogue_sources if row["inCanonicalInventory"]]
    received = sum(1 for row in canonical_rows if row["receiptRefs"])
    challenge_or_error = sum(1 for row in canonical_rows if any(status in {"HTML_CHALLENGE_PAGE", "HTML_NOT_FOUND_PAGE", "RETRIEVAL_FAILED", "INVALID_RECEIPT"} or status.startswith(("RAW_BINDING_", "BLOB_", "PDF")) for status in row["captureStatuses"]))
    usable = sum(1 for row in canonical_rows if row["currentCaptureStatus"] == "CAPTURED")
    catalogue = {
        "schemaVersion": ARCHIVE_SCHEMA,
        "createdOn": DATE,
        "authority": "SECONDARY_AI",
        "claimBoundary": "RETRIEVAL_METADATA_AND_BYTE_BINDING_ONLY_NOT_SOURCE_TRUTH_NOT_LICENSE_GRANT_NOT_HSWM_EFFICACY",
        "inventory": checked_binding(root, inventory_path),
        "privateArchiveManifestBindings": sorted(receipt_manifest_bindings, key=lambda item: item["collection"]),
        "validationBindings": [checked_binding(root, path) for path in validation_paths],
        "completeness": {
            "canonicalInventoryUrls": 852,
            "canonicalUrlsWithAtLeastOneReceipt": received,
            "canonicalUrlsWithUsableNonChallengeCapture": usable,
            "canonicalUrlsWithChallengeOrErrorCapture": challenge_or_error,
            "meaning": "VALID_PDF, HTML_CAPTURED_NOT_FULLTEXT_VALIDATED, and SHA/size-verified OTHER_CAPTURED_MEDIA count as completed byte retrievals. VALID_PDF establishes only that the captured bytes parsed as a PDF; no representation establishes full-text completeness, source truth, licence, or HSWM relevance. Challenge, raw-binding, malformed, PDF parse, and all other validation errors remain represented but excluded."
        },
        "representations": {
            "landingHtml": sum(1 for row in catalogue_sources for status in row["captureStatuses"] if status == "HTML_CAPTURED_NOT_FULLTEXT_VALIDATED"),
            "validatedPdf": sum(1 for row in catalogue_sources for status in row["captureStatuses"] if status == "VALID_PDF"),
            "challengePage": sum(1 for row in catalogue_sources for status in row["captureStatuses"] if status == "HTML_CHALLENGE_PAGE"),
            "otherCapturedMedia": sum(1 for row in catalogue_sources for status in row["captureStatuses"] if status == "OTHER_CAPTURED_MEDIA"),
        },
        "sources": catalogue_sources,
        "boundary": "Public catalogue and copied receipts omit private blob paths and all third-party body bytes. Supplement derivedFrom records discovery lineage only and does not assert byte equality or a version identity unless its own receipt says so."
    }

    nodes: list[dict[str, Any]] = []
    relations: list[dict[str, str]] = []
    bundle_uid = "sym:AbstractNode:hswm-external-source-archive-2026-09-28"
    nodes.append(node(bundle_uid, "HSWM external source archive", "Metadata-only projection of cited external source retrieval attempts and local citations.", "SOURCE_ARCHIVE_BUNDLE", "SOURCE_BOUND_ARCHIVE"))
    for source_id, entry in sorted(source_by_id.items()):
        source_uid = source_nodes[source_id]
        role = "CANONICAL_CITED_SOURCE" if source_id in inventory_by_id else "SUPPLEMENTARY_FULLTEXT_SOURCE"
        source_catalogue = next(row for row in catalogue_sources if row["id"] == source_id)
        nodes.append(node(source_uid, f"External source {source_id}", "A cited URL identity; capture records below describe observed representations, not source truth.", role, "CITED_URL_DECLARED", source_id=source_id, source_url=str(entry["url"]), original_url=str(entry["url"]), expected_kind=str(entry.get("expectedKind", "any")), in_canonical_inventory=source_catalogue["inCanonicalInventory"], current_capture_status=source_catalogue["currentCaptureStatus"], capture_statuses=source_catalogue["captureStatuses"], validation_statuses=source_catalogue["validationStatuses"]))
        relations.append(relation(bundle_uid, source_uid, "CONTAINS", "SOURCE_ARCHIVE_URL_INVENTORY"))
        for citation in entry.get("citations", []):
            if not isinstance(citation, dict):
                continue
            identity = sha256_bytes(stable_json({"source": source_id, "citation": citation}))
            citation_uid = node_uid("citation", identity)
            nodes.append(node(citation_uid, "Local citation binding", "A local document cites this URL. It is a reference, not a derivation or an endorsement of the cited claim.", "CITATION_OCCURRENCE", "SOURCE_BOUND_LOCAL_REFERENCE", source_path=str(citation.get("path", "")), source_sha256=str(citation.get("sha256", "")), citation_locator=str(citation.get("locator", "")), cited_url=str(citation.get("citedUrl", entry["url"]))))
            relations.append(relation(citation_uid, source_uid, "REFERS_TO", "LOCAL_DOCUMENT_CITATION"))
        for derived in entry.get("derivedFrom", []):
            if not isinstance(derived, dict):
                continue
            parent_id = derived.get("sourceId")
            if not isinstance(parent_id, str):
                parent_url = derived.get("url")
                candidates = source_ids_by_url.get(parent_url, []) if isinstance(parent_url, str) else []
                parent_id = candidates[0] if len(candidates) == 1 else None
            parent = source_nodes.get(parent_id) if isinstance(parent_id, str) else None
            if parent is not None:
                relations.append(relation(source_uid, parent, "DISCOVERED_FROM", "SUPPLEMENTARY_FULLTEXT_DISCOVERY_NO_BYTE_EQUALITY_OR_WORK_VERSION_CLAIM"))
        for collection, receipt in receipts_by_id.get(source_id, []):
            attempt_uid = node_uid("attempt", receipt_key(collection, receipt))
            validity, representation, _usable, validation_status = capture_status(receipt, combined, html, pdf)
            failure = receipt.get("failure", receipt.get("detail", ""))
            failure_reason = failure if isinstance(failure, str) else json.dumps(failure, ensure_ascii=False, sort_keys=True)
            response_mime = str((receipt.get("responseHeaders") or {}).get("contentType") or "application/octet-stream")
            final_url = receipt.get("finalUrl")
            nodes.append(node(attempt_uid, "Source retrieval attempt", "Recorded bounded HTTP retrieval attempt; status is transport/capture metadata only.", "SOURCE_RETRIEVAL", str(receipt.get("status", "INVALID")), collection=collection, receipt_id=str(receipt.get("id", "")), requested_url=str(receipt.get("requestedUrl", "")), final_url=final_url if isinstance(final_url, str) else "", final_url_known=isinstance(final_url, str), retrieved_at=str(receipt.get("retrievedAt", "")), retrieval_status=str(receipt.get("status", "INVALID")), failure_reason=failure_reason, source_validity=validity, capture_validation_status=validation_status, representation_kind=representation, response_media_type=response_mime, transport=str(receipt.get("transport", "fetch")), maximum_bytes=int(receipt.get("maximumBytes", 32 * 1024 * 1024))))
            relations.append(relation(source_uid, attempt_uid, "RETRIEVED", "URL_TO_RETRIEVAL_ATTEMPT"))
            if receipt.get("status") == "ARCHIVED" and isinstance(receipt.get("sha256"), str):
                digest = receipt["sha256"]
                content_uid = node_uid("content", digest)
                # Add the immutable content entity after all attempts are seen:
                # the same digest can have different transport MIME declarations.
                relations.append(relation(attempt_uid, content_uid, "GENERATED", "RETRIEVAL_ATTEMPT_TO_CONTENT_ENTITY"))

    # A SHA entity is shared by every retrieval that produced the same bytes.
    # Transport headers belong on attempts; choose one normalized media type for
    # the SHA entity and retain every observed declaration as an array.
    content_observations: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for collection, receipts in receipts_by_id.items():
        for _collection, receipt in receipts:
            if receipt.get("status") == "ARCHIVED" and isinstance(receipt.get("sha256"), str):
                content_observations[receipt["sha256"]].append(receipt)
    for digest, observations in sorted(content_observations.items()):
        sizes = {int(item.get("size", 0)) for item in observations}
        if len(sizes) != 1 or next(iter(sizes)) < 1:
            raise ValueError(f"content digest has inconsistent or empty size: {digest}")
        mime_values = sorted({str((item.get("responseHeaders") or {}).get("contentType") or "application/octet-stream").lower() for item in observations})
        statuses = sorted({capture_status(item, combined, html, pdf)[0] for item in observations})
        representations = sorted({capture_status(item, combined, html, pdf)[1] for item in observations})
        nodes.append(node(
            node_uid("content", digest),
            "Retrieved content representation",
            "Content-addressed private response body; public projection contains only its digest and structural metadata.",
            "ARCHIVED_EXTERNAL_CONTENT",
            statuses[0],
            content_sha256=digest,
            byte_length=next(iter(sizes)),
            media_type=mime_values[0],
            observed_media_types=mime_values,
            source_validity=statuses,
            public_blob_committed=False,
            representation_kinds=representations,
        ))

    # Some discovery records intentionally point to a representation already
    # captured by another request.  Link them only when both URL identities are
    # unambiguous, and never infer byte or work/version equivalence.
    for discovered in already_archived_links:
        fulltext_url = discovered.get("fullTextUrl", discovered.get("url"))
        derived_rows = discovered.get("derivedFrom", [])
        if not isinstance(fulltext_url, str) or not isinstance(derived_rows, list):
            continue
        child_ids = source_ids_by_url.get(fulltext_url, [])
        if len(child_ids) != 1:
            continue
        for derived in derived_rows:
            if not isinstance(derived, dict):
                continue
            parent_id = derived.get("sourceId")
            if not isinstance(parent_id, str):
                parent_url = derived.get("url", discovered.get("parentUrl"))
                candidates = source_ids_by_url.get(parent_url, []) if isinstance(parent_url, str) else []
                parent_id = candidates[0] if len(candidates) == 1 else None
            if isinstance(parent_id, str) and parent_id in source_nodes:
                relations.append(relation(source_nodes[child_ids[0]], source_nodes[parent_id], "DISCOVERED_FROM", "ALREADY_ARCHIVED_FULLTEXT_DISCOVERY_NO_BYTE_EQUALITY_OR_WORK_VERSION_CLAIM"))

    unique_nodes = {item["uid"]: item for item in nodes}
    if len(unique_nodes) != len(nodes):
        # Equivalent content/source nodes must have exactly the same semantic projection.
        for item in nodes:
            existing = unique_nodes[item["uid"]]
            if existing != item:
                raise ValueError(f"conflicting deterministic node identity: {item['uid']}")
    unique_relations = {(item["from_uid"], item["type"], item["to_uid"]): item for item in relations}
    receipt_outputs = {str(RESEARCH / "receipts" / f"{collection}.v1.json"): receipt_document for collection, receipt_document in sorted(collection_receipts.items())}
    provenance_graph: list[dict[str, Any]] = []
    for source_id, entry in sorted(source_by_id.items()):
        url_identity = sha256_bytes(str(entry["url"]).encode())
        url_entity = f"urn:hswm:source-archive:url:sha256:{url_identity}"
        provenance_graph.append({
            "@id": url_entity,
            "@type": "prov:Entity",
            "hswm:sourceId": source_id,
            "hswm:declaredUrl": str(entry["url"]),
            "hswm:inCanonicalInventory": source_id in inventory_by_id,
        })
        for collection, receipt in receipts_by_id.get(source_id, []):
            key = receipt_key(collection, receipt)
            attempt_entity = f"urn:hswm:source-archive:attempt:sha256:{key}"
            provenance_graph.append({
                "@id": attempt_entity,
                "@type": "prov:Activity",
                "prov:used": {"@id": url_entity},
                "prov:endedAtTime": str(receipt.get("retrievedAt", "")),
                "hswm:collection": collection,
                "hswm:receiptId": str(receipt.get("id", "")),
                "hswm:transportStatus": str(receipt.get("status", "INVALID")),
            })
            if receipt.get("status") == "ARCHIVED" and isinstance(receipt.get("sha256"), str):
                digest = receipt["sha256"]
                digest_entity = f"urn:hswm:source-archive:content:sha256:{digest}"
                copy_entity = f"urn:hswm:source-archive:copy:sha256:{key}"
                provenance_graph.append({
                    "@id": copy_entity,
                    "@type": "prov:Entity",
                    "prov:wasGeneratedBy": {"@id": attempt_entity},
                    "prov:specializationOf": {"@id": digest_entity},
                    "hswm:sha256": digest,
                    "hswm:byteLength": int(receipt.get("size", 0)),
                })
                provenance_graph.append({
                    "@id": digest_entity,
                    "@type": "prov:Entity",
                    "hswm:sha256": digest,
                    "hswm:byteLength": int(receipt.get("size", 0)),
                })
    provenance = {
        "@context": {
            "prov": "http://www.w3.org/ns/prov#",
            "hswm": "https://hswm.local/ontology/",
        },
        "@id": "urn:hswm:source-archive:bundle:2026-09-28",
        "@type": "prov:Bundle",
        "hswm:schemaVersion": "hswm-external-source-archive-retrieval-provenance/v1",
        "hswm:authorityClass": "SECONDARY_AI",
        "hswm:claimBoundary": "RETRIEVAL_METADATA_AND_BYTE_BINDING_ONLY_NOT_SOURCE_TRUTH_NOT_LICENSE_GRANT_NOT_HSWM_EFFICACY",
        "hswm:bodyBoundary": "NO_THIRD_PARTY_BODY_BYTES_OR_PRIVATE_BLOB_PATHS",
        "@graph": provenance_graph,
    }
    # The generated public projections are source-bound too.  They do not bind
    # the KG itself, preventing a hash cycle; private manifests are bound by
    # their public receipt documents and artifact bindings below.
    generated_bindings = [
        {"path": path, "sha256": sha256_bytes(stable_json(value))}
        for path, value in {
            str(RESEARCH / "catalogue.v1.json"): catalogue,
            str(PROVENANCE): provenance,
            **receipt_outputs,
        }.items()
    ]
    bindings = [
        checked_binding(root, path)
        for path in [inventory_path, *supplement_paths, recovery_path, root / RESEARCH / "toolchain.v1.json", *validation_paths, root / RESEARCH / "build-catalogue.py"]
        if path.exists()
    ] + generated_bindings
    kg = {
        "schema_version": KG_SCHEMA,
        "bundle_uid": bundle_uid,
        "status": "SOURCE_BOUND_RETRIEVAL_METADATA_PROJECTION",
        "authority_boundary": "All archive interpretations are SECONDARY_AI. External sources remain externally authored and their truth, licence and relevance are not established here.",
        "nonclaim": "RETRIEVAL_METADATA_AND_BYTE_BINDING_ONLY_NOT_SOURCE_TRUTH_NOT_LICENSE_GRANT_NOT_HSWM_EFFICACY",
        "artifact_bindings": sorted(bindings, key=lambda item: item["path"]),
        "expected_counts": {"nodes": len(unique_nodes), "anchors": 0, "relations": len(unique_relations)},
        "anchors": [],
        "nodes": [unique_nodes[key] for key in sorted(unique_nodes)],
        "relations": [unique_relations[key] for key in sorted(unique_relations)],
    }
    if len(stable_json(kg)) > MAX_NATIVE_SOURCE_BYTES:
        raise ValueError("generated KG exceeds native compiler 16MiB source maximum")
    outputs: dict[str, Any] = {
        str(RESEARCH / "catalogue.v1.json"): catalogue,
        str(PROVENANCE): provenance,
        str(ONTOLOGY): kg,
        **receipt_outputs,
    }
    if args.check_only:
        print(json.dumps({"status": "CHECK_ONLY_PASS", "canonicalSources": 852, "catalogueSources": len(catalogue_sources), "kgNodes": len(unique_nodes), "kgRelations": len(unique_relations), "kgBytes": len(stable_json(kg)), "collections": sorted(collection_receipts)}, sort_keys=True))
        return 0
    for name, value in sorted(outputs.items()):
        atomic_write(output_root / name, value)
    print(json.dumps({"status": "WRITTEN", "outputRoot": str(output_root), "files": sorted(outputs), "kgBytes": len(stable_json(kg))}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
