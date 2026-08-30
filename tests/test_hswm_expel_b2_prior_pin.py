"""Offline invariants for the source-pinned ExpeL B2 comparator boundary."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRIOR = ROOT / "_research/causal_composition/priors/expel_b2_text_lesson_v1"
MANIFEST = PRIOR / "source_pin.v1.json"
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_expel_b2_source_pin_is_offline_and_immutably_identified() -> None:
    value = _manifest()

    assert value["schema_version"] == "hswm-causal-composition-prior-source-pin/v1"
    assert value["prior_uid"] == "sym:Prior:expel-b2-text-lesson-v1"
    assert value["scientific_status"] == "PRIOR_MECHANISM_REFERENCE_ONLY_NOT_HSWM_EVIDENCE"

    sources = value["official_sources"]
    assert sources["paper"]["arxiv_id"] == "2308.10144"
    assert sources["paper"]["doi"] == "10.1609/aaai.v38i17.29936"
    assert sources["paper"]["arxiv_version"] == "v3"
    assert sources["paper"]["versioned_pdf_url"].endswith("2308.10144v3")
    assert sources["repository"]["official_url"] == "https://github.com/LeapLabTHU/ExpeL"
    assert sources["repository"]["commit"] == "e41ec9a24823e7b560c561ab191441b56d9bcefc"
    assert sources["repository"]["tree"] == "8ba77f84284693ebbe12ba9a93bd32fd101a6922"
    assert sources["repository"]["release_or_tag"] is None
    assert sources["license"]["spdx"] == "Apache-2.0"

    digests = [
        sources["paper"]["sha256"],
        sources["repository"]["tarball_sha256"],
        sources["license"]["sha256"],
        *[item["sha256"] for item in value["minimal_reproduction_boundary"]["upstream_minimal_files"]],
    ]
    assert all(SHA256.fullmatch(digest) for digest in digests)
    assert re.fullmatch(r"[0-9a-f]{40}", sources["repository"]["tree"])
    assert value["offline_verifier_contract"]["network_access"] == "FORBIDDEN"


def test_expel_b2_prior_requires_isolation_parity_and_no_claim_boundary() -> None:
    value = _manifest()
    boundary = value["minimal_reproduction_boundary"]
    contract = value["future_run_contract"]

    assert {item["path"] for item in boundary["upstream_minimal_files"]} == {
        "agent/expel.py",
        "agent/reflect.py",
        "insight_extraction.py",
        "configs/agent/expel.yaml",
    }
    assert any("not vendored" in item for item in boundary["excluded"])
    assert "arm-private" in contract["b2_only_state"]
    assert "parity check" in contract["direct_vs_wrapper_parity"]
    assert "wrapper" in contract["direct_vs_wrapper_parity"]
    assert "same task information" in contract["resource_parity"]
    assert {
        "reflection_prompt_bytes_sha256",
        "retrieval_embedding_model_and_revision",
        "completion_token_call_retry_time_and_human_minutes_budget",
    } <= set(contract["fixed_before_outcome_inspection"])

    no_claim = " ".join(value["no_claim"])
    assert "G1 efficacy" in no_claim
    assert "HSWM learning" in no_claim
    assert "FCL-1" in no_claim
