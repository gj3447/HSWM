from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import pytest

from hswm.cells.conditional import Reject, digest
from hswm.infrastructure.usl_adapter import adapt_usl


NOW = 1_700_000_000.0


def locator(kind: str, name: str) -> dict:
    if kind == "kg":
        return {"kind": "kg", "source": "fixture", "uid": name}
    if kind == "url":
        return {"kind": "url", "href": f"https://example.invalid/{name}"}
    return {"kind": "filesystem", "host": "fixture", "path": f"/tmp/{name}"}


def resolved(locator_value: dict, name: str, timestamp: str = "2023-11-14T22:13:20Z") -> dict:
    return {
        "locator": locator_value,
        "resolvedLocator": f"resolved:{name}",
        "contentHash": sha256(name.encode()).hexdigest(),
        "resolvedAt": timestamp,
        "guaranteeLevel": "sandboxed",
        "matchCount": 1,
    }


def fixture() -> tuple[dict, dict, dict]:
    resources = [
        {"name": "code", "locator": locator("filesystem", "code")},
        {"name": "spec", "locator": locator("url", "spec")},
        {"name": "anchor", "locator": locator("kg", "anchor")},
    ]
    participants = [
        {"role": "implementation", "resource": "code"},
        {"role": "requirement", "resource": "spec"},
        {"role": "meaning_anchor", "resource": "anchor"},
    ]
    plan = {
        "schema": "usl-semantic-plan/v1",
        "languageVersion": "0.1",
        "namespace": "fixture",
        "resources": resources,
        "meanings": [{
            "name": "implements",
            "roles": [
                {"name": "implementation", "kind": "filesystem"},
                {"name": "requirement", "kind": "url"},
                {"name": "meaning_anchor", "kind": "kg"},
            ],
            "description": "implementation follows requirement under an anchor",
            "grounded": locator("kg", "meaning"),
        }],
        "links": [{"name": "edge", "meaning": "implements", "participants": participants}],
        "declarationStatus": "DECLARED",
    }
    resource_rows = [{"name": item["name"], "status": "RESOLVES", "resolution": resolved(item["locator"], item["name"]), "issue": None} for item in resources]
    grounding = {"name": "implements", "status": "RESOLVES", "resolution": resolved(plan["meanings"][0]["grounded"], "meaning"), "issue": None}
    report = {
        "schema": "usl-program-observation/v1", "namespace": "fixture", "status": "RESOLVES",
        "resources": resource_rows, "groundings": [grounding],
        "links": [{"name": "edge", "meaning": "implements", "participants": participants, "resourcesResolve": True, "semanticTruth": "NOT_EVALUATED"}],
        "semanticTruth": "NOT_EVALUATED",
    }
    pins = [{"name": row["name"], "content_hash": row["resolution"]["contentHash"], "resolved_locator": row["resolution"]["resolvedLocator"]} for row in resource_rows]
    pins.append({"name": "meaning:implements", "content_hash": grounding["resolution"]["contentHash"], "resolved_locator": grounding["resolution"]["resolvedLocator"]})
    policy = {
        "schema_version": "hswm-usl-observation-policy/v1", "namespace": "fixture", "plan_digest": digest(plan),
        "max_age_seconds": 60, "bindings": [{"link": "edge", "role": "implementation", "field": "resolves"}], "resources": pins,
    }
    return plan, report, policy


def test_nary_role_order_is_preserved_and_rename_or_type_drift_rejects() -> None:
    plan, report, policy = fixture()
    result = adapt_usl(plan, report, policy, allowed_reads={("implementation", "resolves")}, now=NOW, revision="r1")
    assert result["status"] == "READY"
    assert [p["role"] for p in result["links"][0]["participants"]] == ["implementation", "requirement", "meaning_anchor"]
    assert result["observations"] == [{"role": "implementation", "field": "resolves", "value": True, "revision": "r1", "expires_at": NOW + 60, "source": result["observations"][0]["source"]}]
    renamed = deepcopy(plan)
    renamed["links"][0]["participants"][1]["role"] = "renamed"
    with pytest.raises(Reject, match="role order"):
        adapt_usl(renamed, report, policy, allowed_reads={("implementation", "resolves")}, now=NOW, revision="r1")
    mismatch = deepcopy(plan)
    mismatch["resources"][1]["locator"] = locator("filesystem", "spec")
    with pytest.raises(Reject, match="type mismatch"):
        adapt_usl(mismatch, report, policy, allowed_reads={("implementation", "resolves")}, now=NOW, revision="r1")


def test_policy_and_report_identity_or_pin_tampering_rejects() -> None:
    plan, report, policy = fixture()
    for mutate, message in [
        (lambda p, r, q: q.update(plan_digest="0" * 64), "plan digest"),
        (lambda p, r, q: q.update(namespace="other"), "policy identity"),
        (lambda p, r, q: q["resources"][0].update(content_hash="0" * 64), "pin mismatch"),
    ]:
        p, r, q = deepcopy(plan), deepcopy(report), deepcopy(policy)
        mutate(p, r, q)
        with pytest.raises(Reject, match=message):
            adapt_usl(p, r, q, allowed_reads={("implementation", "resolves")}, now=NOW, revision="r1")


def test_stale_ambiguous_and_orphan_are_unknown_not_false_and_no_input_is_mutated() -> None:
    plan, report, policy = fixture()
    original = deepcopy((plan, report, policy))
    # USL's runtime can retain a non-unique resolver representation for an
    # AMBIGUOUS endpoint; that remains unknown and cannot become False/True.
    report["resources"][0].update({"status": "AMBIGUOUS", "issue": {"reason": "AMBIGUOUS", "detail": "many"}})
    report["resources"][0]["resolution"]["matchCount"] = 2
    report["status"] = "UNRESOLVED"
    report["links"][0]["resourcesResolve"] = False
    result = adapt_usl(plan, report, policy, allowed_reads={("implementation", "resolves")}, now=NOW, revision="r1")
    assert result["status"] == "UNRESOLVED"
    assert result["observations"] == []
    assert result["links"][0]["status"] == "UNKNOWN"
    assert all(item["value"] is not False for item in result["observations"])
    stale_plan, stale_report, stale_policy = original
    stale_report["resources"][0]["resolution"]["resolvedAt"] = "2020-01-01T00:00:00Z"
    stale_report["links"][0]["resourcesResolve"] = True
    stale = adapt_usl(stale_plan, stale_report, stale_policy, allowed_reads={("implementation", "resolves")}, now=NOW, revision="r1")
    assert stale["observations"] == []
    assert "STALE" in stale["links"][0]["reasons"][0]


def test_unauthorized_mapping_rejects_before_report_and_adapter_has_no_learning_write() -> None:
    plan, report, policy = fixture()
    before = deepcopy((plan, report, policy))
    with pytest.raises(Reject, match="unauthorized mapped read"):
        adapt_usl(plan, report, policy, allowed_reads=set(), now=NOW, revision="r1")
    assert (plan, report, policy) == before
    result = adapt_usl(plan, report, policy, allowed_reads={("implementation", "resolves")}, now=NOW, revision="r1")
    assert "learning" not in result and "action" not in result and "owner" not in result
    assert (plan, report, policy) == before


def test_missing_or_future_grounding_overrides_link_resource_success() -> None:
    plan, report, policy = fixture()
    # Actual USL keeps resourcesResolve true when only the meaning grounding
    # fails; an adapter must inspect that independent observation as well.
    report["groundings"][0].update(status="ORPHAN", resolution=None,
                                    issue={"reason": "ORPHAN", "detail": "no visible grounding"})
    report["status"] = "UNRESOLVED"
    assert report["links"][0]["resourcesResolve"] is True
    missing = adapt_usl(plan, report, policy, allowed_reads={("implementation", "resolves")}, now=NOW, revision="r1")
    assert missing["observations"] == []
    assert missing["links"][0]["reasons"] == ["GROUNDING:implements_ORPHAN"]
    plan, report, policy = fixture()
    report["groundings"][0]["resolution"]["resolvedAt"] = "2030-01-01T00:00:00Z"
    future = adapt_usl(plan, report, policy, allowed_reads={("implementation", "resolves")}, now=NOW, revision="r1")
    assert future["observations"] == []
    assert future["links"][0]["reasons"] == ["GROUNDING:implements_FUTURE_TIMESTAMP"]


def test_partial_selected_links_are_unresolved_and_malformed_discriminators_reject() -> None:
    plan, report, policy = fixture()
    # A second selected relation is fresh while the first is ambiguous: retain
    # the fresh observation but do not promote the whole projection to READY.
    other_participants = [
        {"role": "implementation", "resource": "code2"},
        {"role": "requirement", "resource": "spec2"},
        {"role": "meaning_anchor", "resource": "anchor2"},
    ]
    for name, kind in [("code2", "filesystem"), ("spec2", "url"), ("anchor2", "kg")]:
        item = {"name": name, "locator": locator(kind, name)}
        plan["resources"].append(item)
        row = {"name": name, "status": "RESOLVES", "resolution": resolved(item["locator"], name), "issue": None}
        report["resources"].append(row)
        policy["resources"].append({"name": name, "content_hash": row["resolution"]["contentHash"], "resolved_locator": row["resolution"]["resolvedLocator"]})
    plan["links"].append({"name": "other", "meaning": "implements", "participants": other_participants})
    report["links"].append({"name": "other", "meaning": "implements", "participants": deepcopy(other_participants), "resourcesResolve": True, "semanticTruth": "NOT_EVALUATED"})
    policy["bindings"].append({"link": "other", "role": "usl", "field": "other_resolves"})
    policy["plan_digest"] = digest(plan)
    # Pins cover the same resources for both selected links.
    report["resources"][0].update({"status": "AMBIGUOUS", "issue": {"reason": "AMBIGUOUS", "detail": "many"}})
    report["resources"][0]["resolution"]["matchCount"] = 2
    report["status"] = "UNRESOLVED"
    report["links"][0]["resourcesResolve"] = False
    result = adapt_usl(plan, report, policy, allowed_reads={("implementation", "resolves"), ("usl", "other_resolves")}, now=NOW, revision="r1")
    assert result["status"] == "UNRESOLVED"
    assert [(row["role"], row["field"]) for row in result["observations"]] == [("usl", "other_resolves")]
    malformed_plan, valid_report, valid_policy = fixture()
    malformed_plan["resources"][0]["locator"]["kind"] = []
    with pytest.raises(Reject, match="locator"):
        adapt_usl(malformed_plan, valid_report, valid_policy, allowed_reads={("implementation", "resolves")}, now=NOW, revision="r1")
