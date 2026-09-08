from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from hswm.cells.conditional import Reject, digest
from hswm.infrastructure.usl_adapter import adapt_usl


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "_research/usl_adapter/examples/preview.v2.json"
NOW = 1_788_868_860.0


def request() -> dict:
    return json.loads(EXAMPLE.read_text())


def js_digest(value: object) -> str:
    """USL v2's exact identity format: UTF-8 JSON.stringify, no key sorting."""
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def resign_report(report: dict) -> None:
    payload = {key: value for key, value in report.items() if key != "observationDigest"}
    report["observationDigest"] = js_digest(payload)


def allowed(value: dict) -> set[tuple[str, str]]:
    return {tuple(item) for item in value["preview"]["checks"]["allowed_reads"]}


def adapt(value: dict) -> dict:
    return adapt_usl(value["plan"], value["report"], value["policy"], allowed_reads=allowed(value), now=NOW, revision="r1")


def test_v2_preserves_selected_usl_provenance_without_promoting_semantic_truth() -> None:
    value = request()
    result = adapt(value)
    report = value["report"]
    assert result["schema_version"] == "hswm-usl-observation-projection/v2"
    assert result["usl"]["report_schema"] == "usl-program-observation/v2"
    assert result["usl"]["plan_digest"] == report["planDigest"]
    assert result["usl"]["meanings_digest"] == report["meaningsDigest"]
    assert result["usl"]["source_digest"] == report["sourceDigest"]
    assert result["usl"]["observation_digest"] == report["observationDigest"]
    assert result["usl"]["digest_format"] == report["digestFormat"]
    assert "source_binding" in result["usl"]
    assert result["meanings"] == report["meanings"]
    assert [row["name"] for row in result["links"]] == report["readScope"]["links"]
    selected = {row["name"]: row for row in result["links"]}
    assert selected["development"]["meaningDigest"] == report["links"][0]["meaningDigest"]
    assert selected["development"]["contractDigest"] == report["links"][0]["contractDigest"]
    assert selected["development"]["verification"] == report["links"][0]["verification"]
    assert selected["development"]["verification"][0]["status"] == "NOT_EXECUTED"
    assert result["observations"]
    assert all(row["value"] is True for row in result["observations"])
    assert "no semantic truth" in result["mapping_loss"]


@pytest.mark.parametrize("mutate", [
    lambda value: value["report"]["readScope"].update(links=[]),
    lambda value: value["report"].update(status="UNRESOLVED"),
    lambda value: value["report"]["links"][0].update(resourcesResolve=False),
    lambda value: value["report"]["links"][0]["verification"][0].update(status="EXECUTED_AND_PASSED"),
    lambda value: value["report"]["metrics"].update(resolverCalls="forged"),
])
def test_v2_rejects_resigned_inconsistent_observation_fields(mutate) -> None:
    value = request()
    mutate(value)
    resign_report(value["report"])
    with pytest.raises(Reject):
        adapt(value)


def test_v2_rejects_missing_selected_report_link_and_semantic_or_source_pin_drift() -> None:
    value = request()
    value["report"]["links"] = []
    resign_report(value["report"])
    with pytest.raises(Reject):
        adapt(value)

    value = request()
    value["report"]["meanings"][0]["definition"]["description"] = "forged opposite declaration"
    value["report"]["meanings"][0]["digest"] = js_digest(value["report"]["meanings"][0]["definition"])
    value["report"]["links"][0]["meaningDigest"] = value["report"]["meanings"][0]["digest"]
    resign_report(value["report"])
    with pytest.raises(Reject):
        adapt(value)

    value = request()
    value["report"]["sourceDigest"] = f"sha256:{'0' * 64}"
    resign_report(value["report"])
    with pytest.raises(Reject):
        adapt(value)


def test_v2_denied_grounding_is_unknown_and_never_a_false_readiness() -> None:
    value = request()
    grounding = value["report"]["groundings"][0]
    grounding.update({"status": "DENIED", "resolution": None,
                      "issue": {"reason": "DENIED", "detail": "narrower resolver policy"}})
    value["report"]["status"] = "UNRESOLVED"
    value["report"]["metrics"]["deniedLocators"] = 1
    resign_report(value["report"])
    result = adapt(value)
    assert result["status"] == "UNRESOLVED"
    assert result["observations"] == []
    assert result["links"][0]["status"] == "UNKNOWN"
    assert any("GROUNDING" in reason and "DENIED" in reason for reason in result["links"][0]["reasons"])


def test_v2_policy_uses_hswm_and_usl_digest_lanes_without_weakening_v1() -> None:
    value = request()
    assert value["policy"]["plan_digest"] == digest(value["plan"])
    assert value["policy"]["usl_plan_digest"] == js_digest(value["plan"])
    assert value["policy"]["source_digest"] == value["report"]["sourceDigest"]
    for key in ("plan_digest", "usl_plan_digest", "source_digest"):
        changed = request()
        changed["policy"][key] = ("0" * 64 if key == "plan_digest" else f"sha256:{'0' * 64}")
        with pytest.raises(Reject):
            adapt(changed)


@pytest.mark.parametrize("timestamp, reason", [
    ("2020-01-01T00:00:00.000Z", "STALE"),
    ("2030-01-01T00:00:00.000Z", "FUTURE_TIMESTAMP"),
])
def test_v2_stale_or_future_evidence_remains_unknown(timestamp: str, reason: str) -> None:
    value = request()
    value["report"]["resources"][0]["resolution"]["resolvedAt"] = timestamp
    resign_report(value["report"])
    result = adapt(value)
    assert result["status"] == "UNRESOLVED"
    assert result["observations"] == []
    assert any(reason in item for item in result["links"][0]["reasons"])


def test_v2_explicit_null_source_is_allowed_only_when_policy_pins_null() -> None:
    value = request()
    value["report"]["sourceDigest"] = None
    resign_report(value["report"])
    with pytest.raises(Reject):
        adapt(value)
    value["policy"]["source_digest"] = None
    result = adapt(value)
    assert result["usl"]["source_digest"] is None


def test_v2_rejects_unauthorized_mapping_and_noncanonical_url_policy_addresses() -> None:
    value = request()
    with pytest.raises(Reject):
        adapt_usl(value["plan"], value["report"], value["policy"], allowed_reads=set(), now=NOW, revision="r1")
    value = request()
    allowed_locators = value["report"]["readScope"]["allowedLocators"]
    index = next(i for i, item in enumerate(allowed_locators) if item.startswith("https://"))
    allowed_locators[index] = allowed_locators[index].replace("https://example.invalid", "https://EXAMPLE.INVALID")
    resign_report(value["report"])
    with pytest.raises(Reject):
        adapt(value)
