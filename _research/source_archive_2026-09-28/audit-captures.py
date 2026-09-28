#!/usr/bin/env python3
"""Verify private HSWM source-archive captures without publishing bodies.

The script treats every ``manifest.receipt.v1.json`` below ``--root`` as one
collection.  It never writes below that root and writes only structural receipt
metadata to ``--output``.  A readable HTML page is deliberately not called a
full-text paper.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import html
import json
import re
import subprocess
from pathlib import Path
from typing import Any


TITLE = re.compile(r"<title\b[^>]*>(.*?)</title\s*>", re.IGNORECASE | re.DOTALL)
CHALLENGE_EXACT = {"client challenge"}
CHALLENGE_CONTAINS = (
    "verifying your browser",
    "checking your browser",
    "just a moment",
    "access denied",
    "verify you are human",
    "attention required! | cloudflare",
)
NOT_FOUND_TITLES = {
    "404",
    "404 not found",
    "404 error",
    "not found",
    "page not found",
    "404 - page not found",
    "404 page not found",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pdfinfo_version() -> str:
    result = subprocess.run(["pdfinfo", "-v"], text=True, capture_output=True, check=False, timeout=20)
    return (result.stderr or result.stdout).splitlines()[0].strip()


def title_from(data: bytes) -> str | None:
    match = TITLE.search(data.decode("utf-8", errors="replace"))
    if match is None:
        return None
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", match.group(1)))).strip()


def html_status(title: str | None) -> tuple[str, str]:
    lowered = (title or "").lower()
    if lowered in CHALLENGE_EXACT or any(token in lowered for token in CHALLENGE_CONTAINS):
        return "HTML_CHALLENGE_PAGE", "EXCLUDED_CHALLENGE_PAGE"
    compact = re.sub(r"\s+", " ", lowered).strip(" -|:")
    if compact in NOT_FOUND_TITLES:
        return "HTML_NOT_FOUND_PAGE", "EXCLUDED_NOT_FOUND_PAGE"
    return "HTML_CAPTURED_NOT_FULLTEXT_VALIDATED", "NOT_FULLTEXT_VALIDATED"


def safe_blob(collection: Path, relative: str) -> Path | None:
    candidate = (collection / relative).resolve()
    try:
        candidate.relative_to(collection.resolve())
    except ValueError:
        return None
    return candidate


def audit_body(
    item: tuple[str, list[dict[str, Any]]],
    root: Path,
    pdfinfo: str,
    pdf_timeout: int,
) -> dict[str, Any]:
    digest, refs = item
    representative = refs[0]
    blob = Path(representative["_blobResolved"])
    public_refs = [{key: value for key, value in ref.items() if not key.startswith("_")} for ref in refs]
    result: dict[str, Any] = {
        "sha256": digest,
        "declaredSize": representative["declaredSize"],
        "receiptRefs": public_refs,
        "rawSha256Matches": False,
        "rawByteLengthMatches": False,
        "title": None,
        "pages": None,
        "pdfinfoExit": None,
    }
    copies: list[dict[str, Any]] = []
    by_path = {ref["_blobResolved"]: ref for ref in refs}
    for resolved, reference in sorted(by_path.items()):
        copy = Path(resolved)
        check: dict[str, Any] = {"blobPath": reference["blobPath"], "exists": copy.is_file()}
        if copy.is_file():
            check["actualByteLength"] = copy.stat().st_size
            check["rawSha256Matches"] = sha256(copy) == digest
            check["rawByteLengthMatches"] = all(
                ref["declaredSize"] == copy.stat().st_size for ref in refs if ref["_blobResolved"] == resolved
            )
        else:
            check.update(rawSha256Matches=False, rawByteLengthMatches=False)
        copies.append(check)
    result["copyBindings"] = copies
    result["rawSha256Matches"] = all(copy["rawSha256Matches"] for copy in copies)
    result["rawByteLengthMatches"] = all(copy["rawByteLengthMatches"] for copy in copies)
    if not blob.is_file():
        result.update(status="BLOB_MISSING", sourceCompleteness="EXCLUDED_RAW_BINDING_FAILURE")
        return result
    data = blob.read_bytes()
    result["actualByteLength"] = len(data)
    if not result["rawSha256Matches"] or not result["rawByteLengthMatches"]:
        result.update(status="RAW_BINDING_MISMATCH", sourceCompleteness="EXCLUDED_RAW_BINDING_FAILURE")
        return result

    mime_values = {ref["responseMime"] for ref in refs}
    expected_pdf = any(ref["expectedKind"] == "pdf" for ref in refs)
    pdf_signature = data.startswith(b"%PDF-")
    html_mime = bool(mime_values & {"text/html", "application/xhtml+xml"})
    if expected_pdf or "application/pdf" in mime_values or pdf_signature:
        result["pdfSignature"] = pdf_signature
        result["pdfinfoVersion"] = pdfinfo
        if not pdf_signature:
            result.update(status="PDF_SIGNATURE_MISSING", sourceCompleteness="EXCLUDED_NON_PDF_PAYLOAD")
            return result
        try:
            checked = subprocess.run(["pdfinfo", str(blob)], text=True, capture_output=True, check=False, timeout=pdf_timeout)
        except subprocess.TimeoutExpired:
            result.update(status="PDFINFO_TIMEOUT", sourceCompleteness="EXCLUDED_UNREADABLE_PDF")
            return result
        result["pdfinfoExit"] = checked.returncode
        if checked.returncode != 0:
            result.update(status="PDFINFO_PARSE_FAILED", sourceCompleteness="EXCLUDED_UNREADABLE_PDF")
            return result
        pages = re.search(r"^Pages:\s*(\d+)\s*$", checked.stdout, re.MULTILINE)
        result["pages"] = int(pages.group(1)) if pages else None
        if result["pages"] is None:
            result.update(status="PDFINFO_PAGES_MISSING", sourceCompleteness="EXCLUDED_UNREADABLE_PDF")
            return result
        result.update(status="VALID_PDF", sourceCompleteness="STRUCTURALLY_READABLE_PDF_NOT_CLAIM_VALIDATED")
        return result
    if html_mime:
        title = title_from(data)
        status, completeness = html_status(title)
        result.update(status=status, sourceCompleteness=completeness, title=title)
        return result
    result.update(status="OTHER_CAPTURED_MEDIA", sourceCompleteness="NOT_FULLTEXT_VALIDATED")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path, help="Private archive root containing collection manifests")
    parser.add_argument("--output", required=True, type=Path, help="Metadata-only JSON result path outside the private archive")
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--pdf-timeout-seconds", type=int, default=20)
    args = parser.parse_args()
    if args.max_workers < 1 or args.max_workers > 4 or args.pdf_timeout_seconds < 1:
        parser.error("--max-workers must be 1..4 and --pdf-timeout-seconds must be positive")
    root = args.root.resolve()
    output_path = args.output.resolve()
    try:
        output_path.relative_to(root)
    except ValueError:
        pass
    else:
        parser.error("--output must be outside --root; private archive bodies and receipts are read-only")
    manifests = sorted(root.rglob("manifest.receipt.v1.json"))
    bodies: dict[str, list[dict[str, Any]]] = {}
    receipt_count = 0
    for manifest_path in manifests:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        collection = manifest_path.parent
        for receipt in manifest.get("receipts", []):
            receipt_count += 1
            if receipt.get("status") != "ARCHIVED" or not isinstance(receipt.get("sha256"), str):
                continue
            blob = safe_blob(collection, str(receipt.get("blobPath", "")))
            bodies.setdefault(receipt["sha256"], []).append({
                "collectionManifest": manifest_path.relative_to(root).as_posix(),
                "id": receipt.get("id"),
                "url": receipt.get("finalUrl"),
                "expectedKind": receipt.get("expectedKind"),
                "responseMime": str((receipt.get("responseHeaders") or {}).get("contentType") or "").lower().split(";", 1)[0].strip(),
                "declaredSize": receipt.get("size"),
                "blobPath": str(receipt.get("blobPath", "")),
                "_blobResolved": str(blob) if blob is not None else "",
            })
    pdfinfo = pdfinfo_version()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        rows = list(pool.map(lambda item: audit_body(item, root, pdfinfo, args.pdf_timeout_seconds), sorted(bodies.items())))
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
    challenge = [row["sha256"] for row in rows if row["status"] == "HTML_CHALLENGE_PAGE"]
    invalid_statuses = {
        "BLOB_MISSING",
        "RAW_BINDING_MISMATCH",
        "PDF_SIGNATURE_MISSING",
        "PDFINFO_TIMEOUT",
        "PDFINFO_PARSE_FAILED",
        "PDFINFO_PAGES_MISSING",
    }
    validation_failed = any(row["status"] in invalid_statuses for row in rows)
    output = {
        "schemaVersion": "hswm-external-source-captures-validation/v1",
        "createdOn": "2026-09-28",
        "scope": {
            "root": "PRIVATE_ARCHIVE_ROOT",
            "collectionDiscovery": "Recursive manifest.receipt.v1.json discovery.",
            "pdfinfoVersion": pdfinfo,
            "maximumConcurrency": args.max_workers,
            "pdfTimeoutSeconds": args.pdf_timeout_seconds,
            "htmlBoundary": "Complete locally bounded HTML bodies are decoded only to read the title; bodies and extracted text are not emitted.",
            "challengeTitles": {"exact": ["Client Challenge"], "contains": list(CHALLENGE_CONTAINS)},
        },
        "aggregate": {
            "collectionManifests": len(manifests),
            "receiptRowsScanned": receipt_count,
            "archivedReceiptRefs": sum(len(refs) for refs in bodies.values()),
            "uniqueBodies": len(rows),
            "statusCounts": status_counts,
            "excludedChallengeSha256": challenge,
            "validationFailed": validation_failed,
        },
        "bodies": rows,
        "boundary": "Digest/size and format checks do not establish full-text completeness, licence, source relevance, claim truth, or HSWM efficacy.",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 2 if validation_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
