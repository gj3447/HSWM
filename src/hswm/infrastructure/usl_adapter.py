"""Pure, caller-policy-bound projection of USL reachability observations.

This adapter reads supplied JSON-shaped values only.  It neither resolves a
locator nor executes, stores, admits, credits, or learns from a USL program.
"""

from __future__ import annotations

from datetime import datetime, timezone
from copy import deepcopy
import re
from typing import Any

from hswm.cells.conditional import Reject, digest, finite_number, same


PLAN_SCHEMA = "usl-semantic-plan/v1"
REPORT_SCHEMA = "usl-program-observation/v1"
REPORT_SCHEMA_V2 = "usl-program-observation/v2"
POLICY_SCHEMA = "hswm-usl-observation-policy/v1"
POLICY_SCHEMA_V2 = "hswm-usl-observation-policy/v2"
PROJECTION_SCHEMA = "hswm-usl-observation-projection/v1"
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_MAX = 64
_MAX_ROLES = 16
_MAX_TEXT = 4096
_KINDS = {"kg", "url", "git_repo", "filesystem"}
_GUARANTEES = {"pure", "sandboxed", "trust_host"}
_LOSS = [
    "reference resolution only",
    "no semantic truth",
    "caller-bound report not attestation",
    "no content extraction/credit/admission",
]


def _reject(message: str) -> None:
    raise Reject(message)


def _text(value: object, label: str, *, name: bool = False) -> str:
    if not isinstance(value, str) or not value or len(value) > _MAX_TEXT:
        _reject(label)
    if name and _NAME.fullmatch(value) is None:
        _reject(label)
    return value


def _exact(value: object, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        _reject(label)
    return value


def _list(value: object, label: str, maximum: int = _MAX) -> list[Any]:
    if not isinstance(value, list) or len(value) > maximum:
        _reject(label)
    return value


def _unique(rows: list[Any], key: str, label: str) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            _reject(label)
        value = _text(row.get(key), label, name=True)
        if value in found:
            _reject(f"duplicate {label}")
        found[value] = row
    return found


def _locator(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or not isinstance(value.get("kind"), str) or value["kind"] not in _KINDS:
        _reject("locator")
    kind = value["kind"]
    allowed = {
        "kg": {"kind", "source", "uid"},
        "url": {"kind", "href"},
        "git_repo": {"kind", "repo", "commit", "path", "symbol", "lineStart", "lineEnd"},
        "filesystem": {"kind", "host", "path", "lineStart", "lineEnd"},
    }[kind]
    if not set(value) <= allowed or set(value) == {"kind"}:
        _reject("locator fields")
    required = {"kind", "source", "uid"} if kind == "kg" else {"kind", "href"} if kind == "url" else {"kind", "repo"} if kind == "git_repo" else {"kind", "host", "path"}
    if not required <= set(value):
        _reject("locator fields")
    for key, item in value.items():
        if key in {"lineStart", "lineEnd"}:
            if type(item) is not int or item < 1:
                _reject("locator line")
        elif key != "kind":
            _text(item, "locator text")
    return value


def _participants(value: object, roles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = _list(value, "participants", _MAX_ROLES)
    if len(rows) != len(roles):
        _reject("participant count")
    result: list[dict[str, Any]] = []
    for participant, role in zip(rows, roles):
        row = _exact(participant, {"role", "resource"}, "participant shape")
        if _text(row["role"], "participant role", name=True) != role["name"]:
            _reject("participant role order")
        result.append(row)
    for row in result:
        _text(row["resource"], "participant resource", name=True)
    return result


def _validate_plan(plan: object, *, v2: bool = False) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    root = _exact(plan, {"schema", "languageVersion", "namespace", "resources", "meanings", "links", "declarationStatus"}, "plan shape")
    if root["schema"] != PLAN_SCHEMA or root["languageVersion"] != "0.1" or root["declarationStatus"] != "DECLARED":
        _reject("plan version")
    _text(root["namespace"], "namespace")
    resources = _unique(_list(root["resources"], "resources"), "name", "resource")
    meanings = _unique(_list(root["meanings"], "meanings"), "name", "meaning")
    links = _unique(_list(root["links"], "links"), "name", "link")
    if len(set(resources) | set(meanings) | set(links)) != len(resources) + len(meanings) + len(links):
        _reject("duplicate declaration name")
    for name, row in resources.items():
        _exact(row, {"name", "locator"}, "resource shape")
        _locator(row["locator"])
    for name, row in meanings.items():
        shape = set(row) - ({"contract"} if v2 else set())
        if shape not in ({"name", "roles", "description"}, {"name", "roles", "description", "grounded"}):
            _reject("meaning shape")
        roles = _list(row["roles"], "meaning roles", _MAX_ROLES)
        if not 2 <= len(roles) <= _MAX_ROLES:
            _reject("meaning role count")
        seen: set[str] = set()
        for role in roles:
            item = _exact(role, {"name", "kind"}, "role shape")
            role_name = _text(item["name"], "role name", name=True)
            if role_name in seen or not isinstance(item["kind"], str) or item["kind"] not in _KINDS | {"any"}:
                _reject("role")
            seen.add(role_name)
        _text(row["description"], "meaning description")
        if "grounded" in row:
            grounding = _locator(row["grounded"])
            if grounding["kind"] != "kg":
                _reject("meaning grounding")
    for name, row in links.items():
        _exact(row, {"name", "meaning", "participants"}, "link shape")
        meaning_name = _text(row["meaning"], "link meaning", name=True)
        if meaning_name not in meanings:
            _reject("undeclared link meaning")
        participants = _participants(row["participants"], meanings[meaning_name]["roles"])
        for participant, role in zip(participants, meanings[meaning_name]["roles"]):
            resource = resources.get(participant["resource"])
            if resource is None:
                _reject("undeclared participant resource")
            if role["kind"] != "any" and resource["locator"]["kind"] != role["kind"]:
                _reject("participant type mismatch")
    return root, resources, meanings, links


def _timestamp(value: object) -> float:
    text = _text(value, "resolvedAt")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        _reject("resolvedAt")
    if parsed.tzinfo is None:
        _reject("resolvedAt timezone")
    result = parsed.astimezone(timezone.utc).timestamp()
    if not finite_number(result):
        _reject("resolvedAt")
    return result


def _resolution(value: object, locator: dict[str, Any]) -> dict[str, Any]:
    row = _exact(value, {"locator", "resolvedLocator", "contentHash", "resolvedAt", "guaranteeLevel", "matchCount"}, "resolution shape")
    if not same(_locator(row["locator"]), locator):
        _reject("resolution locator mismatch")
    _text(row["resolvedLocator"], "resolvedLocator")
    if not isinstance(row["contentHash"], str) or _HASH.fullmatch(row["contentHash"]) is None:
        _reject("contentHash")
    _timestamp(row["resolvedAt"])
    if row["guaranteeLevel"] not in _GUARANTEES or type(row["matchCount"]) is not int or row["matchCount"] < 0:
        _reject("resolution guarantee or matches")
    return row


def _observation_rows(value: object, expected: dict[str, dict[str, Any]], *, grounding: bool) -> dict[str, dict[str, Any]]:
    found = _unique(_list(value, "groundings" if grounding else "report resources"), "name", "report observation")
    if set(found) != set(expected):
        _reject("report observation names do not match plan")
    for name, row in found.items():
        _exact(row, {"name", "status", "resolution", "issue"}, "report observation shape")
        if not isinstance(row["status"], str) or row["status"] not in {"RESOLVES", "ORPHAN", "AMBIGUOUS"}:
            _reject("report observation status")
        locator = expected[name]["grounded"] if grounding else expected[name]["locator"]
        if row["status"] == "RESOLVES":
            if row["issue"] is not None:
                _reject("resolving observation issue")
            if _resolution(row["resolution"], locator)["matchCount"] != 1:
                _reject("resolving observation is not unique")
        else:
            issue = _exact(row["issue"], {"reason", "detail"}, "unresolved observation issue")
            _text(issue["reason"], "unresolved observation reason")
            _text(issue["detail"], "unresolved observation detail")
            if row["status"] == "ORPHAN" and row["resolution"] is not None:
                _reject("orphan observation resolution")
            if row["status"] == "AMBIGUOUS" and row["resolution"] is not None:
                _resolution(row["resolution"], locator)
    return found


def _validate_report(report: object, plan: dict[str, Any], resources: dict[str, Any], meanings: dict[str, Any], links: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    root = _exact(report, {"schema", "namespace", "status", "resources", "groundings", "links", "semanticTruth"}, "report shape")
    if root["schema"] != REPORT_SCHEMA or root["namespace"] != plan["namespace"] or root["semanticTruth"] != "NOT_EVALUATED" or not isinstance(root["status"], str) or root["status"] not in {"RESOLVES", "UNRESOLVED"}:
        _reject("report identity or semantic truth")
    grounded = {name: meaning for name, meaning in meanings.items() if "grounded" in meaning}
    observations = _observation_rows(root["resources"], resources, grounding=False)
    groundings = _observation_rows(root["groundings"], grounded, grounding=True)
    report_resolves = all(row["status"] == "RESOLVES" for row in observations.values()) and all(
        row["status"] == "RESOLVES" for row in groundings.values()
    )
    if (root["status"] == "RESOLVES") != report_resolves:
        _reject("report aggregate status")
    reported_links = _unique(_list(root["links"], "report links"), "name", "report link")
    if set(reported_links) != set(links):
        _reject("report link names do not match plan")
    for name, row in reported_links.items():
        _exact(row, {"name", "meaning", "participants", "resourcesResolve", "semanticTruth"}, "report link shape")
        if row["meaning"] != links[name]["meaning"] or row["semanticTruth"] != "NOT_EVALUATED" or type(row["resourcesResolve"]) is not bool:
            _reject("report link meaning or semantic truth")
        roles = meanings[row["meaning"]]["roles"]
        if _participants(row["participants"], roles) != links[name]["participants"]:
            _reject("report link participants")
        computed = all(observations[p["resource"]]["status"] == "RESOLVES" for p in row["participants"])
        if row["resourcesResolve"] != computed:
            _reject("report link resource status")
    return observations, groundings, reported_links


def _allowed(value: object) -> set[tuple[str, str]]:
    if not isinstance(value, (set, frozenset)) or any(not isinstance(item, tuple) or len(item) != 2 or not all(isinstance(part, str) and part for part in item) for item in value):
        _reject("allowed_reads")
    return set(value)


def _validate_policy(policy: object, plan: dict[str, Any], resources: dict[str, Any], meanings: dict[str, Any], links: dict[str, Any], allowed_reads: set[tuple[str, str]], *, v2: bool = False) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    extra = {"usl_plan_digest", "source_digest"} if v2 else set()
    root = _exact(policy, {"schema_version", "namespace", "plan_digest", "max_age_seconds", "bindings", "resources"} | extra, "policy shape")
    if root["schema_version"] != (POLICY_SCHEMA_V2 if v2 else POLICY_SCHEMA) or root["namespace"] != plan["namespace"] or root["plan_digest"] != digest(plan):
        _reject("policy identity or plan digest")
    age = root["max_age_seconds"]
    if not finite_number(age) or not 0 < age <= 86400:
        _reject("policy max_age_seconds")
    bindings = _list(root["bindings"], "policy bindings")
    if not bindings:
        _reject("policy bindings")
    selected: set[str] = set()
    mapped: set[tuple[str, str]] = set()
    parsed: list[dict[str, Any]] = []
    for binding in bindings:
        row = _exact(binding, {"link", "role", "field"}, "policy binding shape")
        link, role, field = (_text(row[key], f"policy {key}", name=True) for key in ("link", "role", "field"))
        if link not in links or link in selected:
            _reject("duplicate or unknown selected link")
        # ``role`` is the caller's HSWM observation target, deliberately
        # distinct from the USL incidence roles above.  It is authorized only
        # by the independent allowed_reads set below.
        target = (role, field)
        if target in mapped:
            _reject("duplicate policy role field")
        selected.add(link)
        mapped.add(target)
        parsed.append({"link": link, "role": role, "field": field})
    # This happens before examining the caller report.
    if not mapped <= allowed_reads:
        _reject("unauthorized mapped read")
    pins: dict[str, dict[str, Any]] = {}
    for pin in _list(root["resources"], "policy resources"):
        row = _exact(pin, {"name", "content_hash", "resolved_locator"}, "policy resource shape")
        name = _text(row["name"], "policy resource")
        if name in pins:
            _reject("duplicate policy resource")
        pins[name] = row
    required: set[str] = set()
    for binding in parsed:
        link = links[binding["link"]]
        required.update(participant["resource"] for participant in link["participants"])
        meaning = meanings[link["meaning"]]
        if "grounded" in meaning:
            required.add(f"meaning:{meaning['name']}")
    if set(pins) != required:
        _reject("policy resource pins do not exactly cover selected links")
    for name, pin in pins.items():
        if not isinstance(pin["content_hash"], str) or _HASH.fullmatch(pin["content_hash"]) is None:
            _reject("policy content hash")
        _text(pin["resolved_locator"], "policy resolved locator")
    return root, parsed, pins


def _fresh(row: dict[str, Any], now: float, age: float, label: str) -> tuple[bool, float | None, str | None]:
    if row["status"] != "RESOLVES":
        return False, None, f"{label}_{row['status']}"
    resolved_at = _timestamp(row["resolution"]["resolvedAt"])
    if resolved_at > now:
        return False, None, f"{label}_FUTURE_TIMESTAMP"
    expires = resolved_at + age
    if now >= expires:
        return False, None, f"{label}_STALE"
    return True, expires, None


def _adapt_usl(plan: dict, report: dict, policy: dict, *, allowed_reads: set[tuple[str, str]], now: float, revision: str) -> dict:
    """Return only fresh, policy-pinned boolean reachability observations."""

    if not finite_number(now) or not isinstance(revision, str) or not revision or len(revision) > _MAX_TEXT:
        _reject("observation context")
    permitted = _allowed(allowed_reads)
    v2 = isinstance(report, dict) and report.get("schema") == REPORT_SCHEMA_V2
    plan_root, resources, meanings, links = _validate_plan(plan, v2=v2)
    policy_root, bindings, pins = _validate_policy(policy, plan_root, resources, meanings, links, permitted, v2=v2)
    if v2:
        from hswm.infrastructure.usl_observation_v2 import validate_report
        observations, groundings, report_links = validate_report(report, plan_root, policy_root, bindings)
    else:
        observations, groundings, report_links = _validate_report(report, plan_root, resources, meanings, links)
    plan_digest, report_digest, policy_digest = digest(plan), digest(report), digest(policy)
    source = digest({"plan_digest": plan_digest, "report_digest": report_digest, "policy_digest": policy_digest})
    emitted: list[dict[str, Any]] = []
    link_rows: list[dict[str, Any]] = []
    by_link = {binding["link"]: binding for binding in bindings}
    for name, link in links.items():
        reasons: list[str] = []
        expires: list[float] = []
        binding = by_link.get(name)
        if v2 and binding is None:
            continue
        if binding is None:
            reasons.append("NOT_SELECTED_BY_POLICY")
        else:
            for participant in link["participants"]:
                resource_name = participant["resource"]
                row = observations[resource_name]
                if row["resolution"] is not None:
                    pin = pins[resource_name]
                    resolution = row["resolution"]
                    if resolution["contentHash"] != pin["content_hash"] or resolution["resolvedLocator"] != pin["resolved_locator"]:
                        _reject(f"resource pin mismatch: {resource_name}")
                fresh, expiry, reason = _fresh(row, now, policy_root["max_age_seconds"], f"RESOURCE:{resource_name}")
                if not fresh:
                    reasons.append(reason)
                    continue
                expires.append(expiry)
            meaning = meanings[link["meaning"]]
            if "grounded" in meaning:
                grounding_name = meaning["name"]
                row = groundings[grounding_name]
                if row["resolution"] is not None:
                    pin = pins[f"meaning:{grounding_name}"]
                    resolution = row["resolution"]
                    if resolution["contentHash"] != pin["content_hash"] or resolution["resolvedLocator"] != pin["resolved_locator"]:
                        _reject(f"grounding pin mismatch: {grounding_name}")
                fresh, expiry, reason = _fresh(row, now, policy_root["max_age_seconds"], f"GROUNDING:{grounding_name}")
                if not fresh:
                    reasons.append(reason)
                else:
                    expires.append(expiry)
            if not report_links[name]["resourcesResolve"] and not reasons:
                _reject("report link resolution contradiction")
        status = "READY" if binding is not None and not reasons else "UNKNOWN"
        link_rows.append({"name": name, "meaning": link["meaning"], "participants": [dict(p) for p in link["participants"]], "status": status, "reasons": reasons})
        if status == "READY":
            emitted.append({"role": binding["role"], "field": binding["field"], "value": True, "revision": revision, "expires_at": min(expires), "source": source})
    result = {
        "schema_version": "hswm-usl-observation-projection/v2" if v2 else PROJECTION_SCHEMA,
        "status": "READY" if len(emitted) == len(bindings) else "UNRESOLVED",
        "plan_digest": plan_digest,
        "report_digest": report_digest,
        "policy_digest": policy_digest,
        "namespace": plan_root["namespace"],
        "observations": emitted,
        "links": link_rows,
        "mapping_loss": list(_LOSS),
    }
    if v2:
        result["meanings"] = deepcopy(report["meanings"])
        result["usl"] = {
            "report_schema": report["schema"], "plan_digest": report["planDigest"],
            "meanings_digest": report["meaningsDigest"], "source_digest": report["sourceDigest"],
            "observation_digest": report["observationDigest"], "digest_format": report["digestFormat"],
            "source_binding": "ABSENT" if report["sourceDigest"] is None else "CALLER_PINNED_NOT_RECOMPILED",
        }
        result["read_scope"] = deepcopy(report["readScope"])
        result["metrics"] = deepcopy(report["metrics"])
        for link in result["links"]:
            if link["name"] in report_links:
                observed = report_links[link["name"]]
                for key in ("meaningDigest", "contractDigest", "verification"):
                    link[key] = deepcopy(observed[key])
        result["mapping_loss"].extend([
            "declared checks preserved but not executed", "source digest caller-pinned, source not recompiled",
            "KG_METADATA is not full graph semantics", "noncanonical HTTP URL forms outside the supported subset reject",
        ])
    return result


def adapt_usl(plan: dict, report: dict, policy: dict, *, allowed_reads: set[tuple[str, str]], now: float, revision: str) -> dict:
    """Return a bounded projection and normalize malformed caller JSON to Reject."""

    try:
        return _adapt_usl(plan, report, policy, allowed_reads=allowed_reads, now=now, revision=revision)
    except Reject:
        raise
    except (TypeError, KeyError, ValueError, OverflowError) as error:
        raise Reject("malformed USL input") from error
