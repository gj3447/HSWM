"""Strict, IO-free validation of the source-pinned USL v2 observation projection.

USL uses insertion-order JSON.stringify hashes, distinct from HSWM digests.
This bounded wire subset contains strings, booleans, null and safe integers.
It never runs a resolver, a declared check, a compiler, or a learning update.
"""
from __future__ import annotations

from hashlib import sha256
import ipaddress
import json
import re
from urllib.parse import urlsplit, urlunsplit

from hswm.cells.conditional import Reject, digest
from hswm.infrastructure.usl_adapter import (
    _exact, _list, _locator, _participants, _resolution, _text, _unique,
)

_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_SAFE_INTEGER = 2**53 - 1


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise Reject(f"USL v2 {message}")


def _wire(value: object, depth: int = 0) -> None:
    _require(depth < 24, "JSON depth")
    if value is None or type(value) in (str, bool):
        return
    if type(value) is int:
        _require(abs(value) <= _SAFE_INTEGER, "unsafe JSON integer")
        return
    if isinstance(value, list):
        for item in value:
            _wire(item, depth + 1)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            # No schema-approved keys are JS integer-index properties.
            _require(isinstance(key, str) and not key.isdecimal(), "JSON object key")
            _wire(item, depth + 1)
        return
    raise Reject("USL v2 unsupported JSON value")


def usl_digest(value: object) -> str:
    """JSON.stringify digest for the supported USL wire types, without sorting."""
    _wire(value)
    try:
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (ValueError, UnicodeError):
        raise Reject("USL v2 invalid UTF-8 JSON") from None
    return "sha256:" + sha256(raw).hexdigest()


def _fingerprint(value: object, label: str) -> None:
    _require(isinstance(value, str) and _DIGEST.fullmatch(value) is not None, label)


def _key(value: object) -> str:
    """Format non-URL locators; normalize a conservative ASCII HTTP URL subset.

Reject URL spellings requiring WHATWG transformations beyond this subset,
instead of guessing equivalence when checking a reported read permission.
"""
    text = _text(value, "v2 locator")
    _require(text == text.strip() and not re.search(r"\s", text), "locator whitespace")
    if re.match(r"https?://", text, re.I):
        _require(text.isascii() and not re.search(r'[\\<>"`{}\x00-\x20\x7f]', text), "unsupported URL spelling")
        parsed = urlsplit(text)
        _require(parsed.username is None and parsed.password is None and bool(parsed.hostname), "unsupported URL authority")
        host = parsed.hostname.lower()
        if ":" in host:
            # WHATWG emits a compressed lowercase IPv6 host.
            host = "[" + ipaddress.IPv6Address(host).compressed + "]"
        else:
            _require(re.fullmatch(r"[a-z0-9.-]+", host) is not None, "unsupported URL host")
            # WHATWG interprets numeric/hex IPv4 spellings specially.
            if re.fullmatch(r"(?:[0-9]+|0x[0-9a-f]+)", host.rstrip(".").split(".")[-1]):
                _require(str(ipaddress.IPv4Address(host)) == host, "unsupported IPv4 spelling")
        port = parsed.port
        authority = host if port is None or (parsed.scheme, port) in {("http", 80), ("https", 443)} else f"{host}:{port}"
        path = parsed.path or "/"
        _require(not any(p.lower() in {".", "..", "%2e", ".%2e", "%2e.", "%2e%2e"} for p in path.split("/")), "normalize URL dot segments upstream")
        # WHATWG retains empty query/fragment delimiters; urlunsplit drops them.
        result = urlunsplit((parsed.scheme.lower(), authority, path, parsed.query, parsed.fragment))
        if "?" in text.split("#", 1)[0] and parsed.query == "":
            result = result.replace("#", "?#", 1) if "#" in result else result + "?"
        if text.endswith("#"):
            result += "#"
        _require("'" not in parsed.query, "normalize URL query upstream")
        return result
    if text.startswith("kg://"):
        _require(re.fullmatch(r"kg://[A-Za-z0-9._-]+/\S+", text) is not None, "KG locator")
    elif text.startswith("file://"):
        _require(re.fullmatch(r"file://[A-Za-z0-9._-]+/(?!/)[^#\s]*(?:#L[0-9]+-L[0-9]+)?", text) is not None, "filesystem locator")
    elif text.startswith("git://"):
        _require(re.fullmatch(r"git://[^@\s:]+(?:@[0-9a-fA-F]{7,64})?(?::[^:\s@]+(?:::[^@\s]+)?(?:@L[0-9]+-L[0-9]+)?)?", text) is not None, "Git locator")
    else:
        raise Reject("USL v2 locator scheme")
    lines = re.search(r"(?:#|@)L([0-9]+)-L([0-9]+)$", text)
    if lines and text.startswith(("file://", "git://")):
        _require(1 <= int(lines[1]) <= int(lines[2]) <= _SAFE_INTEGER, "locator text line range")
    return text


def _formatted(value: object) -> str:
    loc = _locator(value)
    kind = loc["kind"]
    if "lineStart" in loc or "lineEnd" in loc:
        _require("lineStart" in loc and "lineEnd" in loc and loc["lineStart"] <= loc["lineEnd"] <= _SAFE_INTEGER, "locator line range")
    if kind == "url":
        result = loc["href"]
    elif kind == "kg":
        result = f"kg://{loc['source']}/{loc['uid']}"
    elif kind == "filesystem":
        result = f"file://{loc['host']}{loc['path']}"
        if "lineStart" in loc:
            result += f"#L{loc['lineStart']}-L{loc['lineEnd']}"
    else:
        _require(not (set(loc) & {"path", "symbol", "lineStart", "lineEnd"}) or "commit" in loc and "path" in loc, "Git locator fields")
        if "path" in loc:
            _require(not loc["path"].startswith("/") and not any(p in {"", ".", ".."} for p in loc["path"].split("/")), "Git relative path")
        result = "git://" + loc["repo"] + ("@" + loc["commit"] if "commit" in loc else "")
        result += ":" + loc["path"] if "path" in loc else ""
        result += "::" + loc["symbol"] if "symbol" in loc else ""
        if "lineStart" in loc:
            result += f"@L{loc['lineStart']}-L{loc['lineEnd']}"
    _key(result)
    return result


def _contract(meaning: dict) -> None:
    _require(bool(meaning["description"].strip()), "empty meaning")
    if "contract" not in meaning:
        return
    contract = _exact(meaning["contract"], {"scope", "checks"}, "v2 contract shape")
    _require(bool(_text(contract["scope"], "v2 scope").strip()), "empty scope")
    checks = _list(contract["checks"], "v2 checks", 16)
    _require(bool(checks), "empty checks")
    _unique(checks, "name", "v2 check")
    roles = {r["name"] for r in meaning["roles"]}
    for check in checks:
        _exact(check, {"name", "description", "evidenceRoles"}, "v2 check shape")
        _require(bool(_text(check["description"], "v2 check description").strip()), "empty check description")
        evidence = _list(check["evidenceRoles"], "v2 evidence roles", 16)
        _require(bool(evidence) and all(isinstance(r, str) and r in roles for r in evidence), "check role")
        _require(len(set(evidence)) == len(evidence), "duplicate evidence role")


def _rows(value: object, expected: dict, *, grounding: bool = False) -> dict:
    rows = _unique(_list(value, "v2 observations"), "name", "v2 observation")
    _require(list(rows) == list(expected), "selected observation names/order")
    for name, row in rows.items():
        _exact(row, {"name", "locator", "fingerprintScope", "status", "resolution", "issue"}, "v2 observation shape")
        loc = expected[name]["grounded" if grounding else "locator"]
        _require(row["locator"] == _formatted(loc), "observation locator binding")
        scope = "KG_METADATA" if loc["kind"] == "kg" else "RESOLVER_REPRESENTATION"
        _require(row["fingerprintScope"] == scope, "fingerprint scope")
        status = row["status"]
        _require(isinstance(status, str) and status in {"RESOLVES", "ORPHAN", "AMBIGUOUS", "DENIED"}, "observation status")
        resolution = row["resolution"]
        if resolution is not None:
            _resolution(resolution, loc)
            _key(resolution["resolvedLocator"])
        if status == "RESOLVES":
            _require(resolution is not None and resolution["matchCount"] == 1 and row["issue"] is None, "unique successful resolution")
        else:
            issue = _exact(row["issue"], {"reason", "detail"}, "v2 issue shape")
            _text(issue["detail"], "v2 issue detail")
            reasons = {"AMBIGUOUS", "IO"} if status == "AMBIGUOUS" else {status}
            _require(isinstance(issue["reason"], str) and issue["reason"] in reasons, "issue reason/status")
            _require(resolution is None or status == "AMBIGUOUS" and resolution["matchCount"] != 1 and issue["reason"] == "AMBIGUOUS", "unresolved representation")
    return rows


def validate_report(report: object, plan: dict, policy: dict, bindings: list[dict]) -> tuple[dict, dict, dict]:
    report = _exact(report, {"schema", "namespace", "planDigest", "meaningsDigest", "sourceDigest", "digestFormat", "status", "readScope", "metrics", "resources", "groundings", "meanings", "links", "semanticTruth", "observationDigest"}, "v2 report shape")
    _require(report["schema"] == "usl-program-observation/v2" and report["namespace"] == plan["namespace"] and report["semanticTruth"] == "NOT_EVALUATED", "report identity")
    _require(report["digestFormat"] == "sha256:utf8:JSON.stringify/v1", "digest format")
    _require(plan["namespace"] == plan["namespace"].strip(), "namespace whitespace")
    _require(report["planDigest"] == policy["usl_plan_digest"] == usl_digest(plan), "plan digest binding")
    _require(report["meaningsDigest"] == usl_digest(plan["meanings"]), "meanings digest")
    if report["sourceDigest"] is not None:
        _fingerprint(report["sourceDigest"], "source digest")
    _require(report["sourceDigest"] == policy["source_digest"], "source digest pin")
    _require(report["observationDigest"] == usl_digest({k: v for k, v in report.items() if k != "observationDigest"}), "observation digest")
    for resource in plan["resources"]:
        _formatted(resource["locator"])
    for meaning in plan["meanings"]:
        _contract(meaning)
        if "grounded" in meaning:
            _formatted(meaning["grounded"])
    selected = {b["link"] for b in bindings}
    links = {l["name"]: l for l in plan["links"] if l["name"] in selected}
    resource_names = {p["resource"] for l in links.values() for p in l["participants"]}
    meaning_names = {l["meaning"] for l in links.values()}
    resources = {r["name"]: r for r in plan["resources"] if r["name"] in resource_names}
    meanings = {m["name"]: m for m in plan["meanings"] if m["name"] in meaning_names}
    groundings = {n: m for n, m in meanings.items() if "grounded" in m}
    observed = _rows(report["resources"], resources)
    grounded = _rows(report["groundings"], groundings, grounding=True)
    declared_meanings = _unique(_list(report["meanings"], "v2 meanings"), "name", "v2 meaning")
    _require(list(declared_meanings) == list(meanings), "selected meanings")
    for name, row in declared_meanings.items():
        _exact(row, {"name", "digest", "definition"}, "v2 meaning shape")
        _require(row["digest"] == usl_digest(row["definition"]) == usl_digest(meanings[name]), "meaning definition binding")
    reported_links = _unique(_list(report["links"], "v2 links"), "name", "v2 link")
    _require(list(reported_links) == list(links), "selected links")
    for name, row in reported_links.items():
        _exact(row, {"name", "meaning", "participants", "meaningDigest", "contractDigest", "resourcesResolve", "semanticTruth", "verification"}, "v2 link shape")
        link = links[name]
        meaning = meanings[link["meaning"]]
        _require(row["meaning"] == link["meaning"] and row["semanticTruth"] == "NOT_EVALUATED", "link meaning")
        _require(_participants(row["participants"], meaning["roles"]) == link["participants"], "link participants")
        _require(row["meaningDigest"] == usl_digest(meaning), "link meaning digest")
        contract_digest = usl_digest({"meaning": meaning["name"], "description": meaning["description"], "roles": meaning["roles"], "contract": meaning.get("contract")})
        _require(row["contractDigest"] == contract_digest, "link contract digest")
        resolves = all(observed[p["resource"]]["status"] == "RESOLVES" for p in link["participants"])
        _require(type(row["resourcesResolve"]) is bool and row["resourcesResolve"] == resolves, "link resource status")
        expected_checks = []
        for check in meaning.get("contract", {}).get("checks", []):
            participants = {p["role"]: p["resource"] for p in link["participants"]}
            evidence = [{"role": role, "resource": participants[role]} for role in check["evidenceRoles"]]
            expected_checks.append({**check, "scope": meaning["contract"]["scope"], "evidence": evidence,
                                    "evidenceAvailable": all(observed[p["resource"]]["status"] == "RESOLVES" for p in evidence), "status": "NOT_EXECUTED"})
        _require(digest(row["verification"]) == digest(expected_checks), "verification contract/status")
    all_rows = [*observed.values(), *grounded.values()]
    status = "RESOLVES" if all(r["status"] == "RESOLVES" for r in all_rows) else "UNRESOLVED"
    _require(report["status"] == status, "aggregate status")
    scope = _exact(report["readScope"], {"links", "allowedLocators", "requestedLocators", "resourceBudget"}, "v2 read scope shape")
    targets = list(dict.fromkeys(r["locator"] for r in all_rows))
    _require(scope["links"] == list(links) and scope["requestedLocators"] == targets, "read scope selection")
    budget = scope["resourceBudget"]
    _require(type(budget) is int and len(targets) <= budget <= _SAFE_INTEGER, "resource budget")
    allowed = _list(scope["allowedLocators"], "v2 allowed locators", 256)
    keys = [_key(loc) for loc in allowed]
    # JavaScript's default sort compares UTF-16 units, including for KG/file IDs.
    _require(keys == allowed and keys == sorted(set(keys), key=lambda key: key.encode("utf-16-be")), "normalized unique allowlist")
    admitted = {loc for loc in targets if _key(loc) in keys}
    aliases = {}
    for row in all_rows:
        if row["locator"] not in admitted:
            _require(row["status"] == "DENIED", "unpermitted resolution")
        payload_digest = digest({k: row[k] for k in ("status", "resolution", "issue")})
        _require(aliases.setdefault(row["locator"], payload_digest) == payload_digest, "alias observation conflict")
    expected_metrics = {"declaredResources": len(plan["resources"]), "selectedResources": len(observed),
                        "uniqueLocators": len(targets), "resolverCalls": len(admitted),
                        "deniedLocators": len({r["locator"] for r in all_rows if r["status"] == "DENIED"})}
    metrics = _exact(report["metrics"], set(expected_metrics), "v2 metrics shape")
    _require(all(type(v) is int for v in metrics.values()) and metrics == expected_metrics, "metrics consistency")
    return observed, grounded, reported_links
