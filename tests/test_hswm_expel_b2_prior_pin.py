"""Offline invariants for the source-pinned ExpeL B2 comparator boundary."""

from __future__ import annotations

import json
from hashlib import sha256
import re
from pathlib import Path

from hswm.selfmod.contracts import canonical_sha256


ROOT = Path(__file__).resolve().parents[1]
PRIOR = ROOT / "_research/causal_composition/priors/expel_b2_text_lesson_v1"
MANIFEST = PRIOR / "source_pin.v1.json"
RUNTIME = PRIOR / "runtime"
QUALIFICATION = ROOT / "manifests/HSWM_EXPEL_B2_DIRECT_RUNTIME_PARITY_2026-08-31.json"
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_expel_b2_source_pin_is_offline_and_immutably_identified() -> None:
    value = _manifest()

    assert value["schema_version"] == "hswm-causal-composition-prior-source-pin/v1"
    assert value["prior_uid"] == "sym:Prior:expel-b2-text-lesson-v1"
    assert value["scientific_status"] == "PRIOR_MECHANISM_REFERENCE_ONLY_NOT_HSWM_EVIDENCE"
    assert value["selection"]["arm_id"] == "B2_EXPEL_INSPIRED_TEXT_LESSON"

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
        *[
            item["sha256"]
            for item in value["minimal_reproduction_boundary"][
                "upstream_algorithm_evidence_files_not_executable_closure"
            ]
        ],
    ]
    assert all(SHA256.fullmatch(digest) for digest in digests)
    assert re.fullmatch(r"[0-9a-f]{40}", sources["repository"]["tree"])
    assert value["offline_verifier_contract"]["network_access"] == "FORBIDDEN"


def test_expel_b2_prior_requires_isolation_parity_and_no_claim_boundary() -> None:
    value = _manifest()
    boundary = value["minimal_reproduction_boundary"]
    contract = value["future_run_contract"]

    assert {
        item["path"]
        for item in boundary["upstream_algorithm_evidence_files_not_executable_closure"]
    } == {
        "agent/expel.py",
        "agent/reflect.py",
        "agent/react.py",
        "insight_extraction.py",
        "configs/agent/expel.yaml",
        "configs/benchmark/alfworld.yaml",
        "memory/episode.py",
        "memory/__init__.py",
        "prompts/alfworld.py",
        "prompts/templates/system.py",
        "prompts/templates/human.py",
        "utils.py",
        "eval.py",
    }
    files = {
        item["path"]: item
        for item in boundary["upstream_algorithm_evidence_files_not_executable_closure"]
    }
    assert files["agent/react.py"]["sha256"] == (
        "a0b8f6c2652bedfaa1442cafd0f22f8f6e050b5daf3355041df532d9a8adb552"
    )
    assert files["memory/episode.py"]["sha256"] == (
        "fd669464df67ec848e6225eb0bcaa7f37ec7335c5e4ffbbc9a966b29d51d78e7"
    )
    assert files["prompts/alfworld.py"]["sha256"] == (
        "130356ae2f6e08b9c90447bbf552ea279b4895762e87fe83be4347aff3f0d043"
    )
    assert files["prompts/templates/system.py"]["sha256"] == (
        "90ff238965728e5f8922c2294be95bc030e1374f22e31bf805a97cb5171b70aa"
    )
    assert files["prompts/templates/human.py"]["sha256"] == (
        "fbfdeeb32ce1299b38a7a61b15ec732a53fce42a5e950be176dad367b05bf216"
    )
    assert files["configs/benchmark/alfworld.yaml"]["sha256"] == (
        "651f3b5551178bc3073985a403fd1d050be25e88412dc399d10d29b609482bde"
    )
    assert files["utils.py"]["sha256"] == (
        "5b7ee915b8f4aa53c6f4162a19834a663030b679178001c86129afb05211a82b"
    )
    assert "RULE_TEMPLATE" in files["prompts/templates/human.py"]["role"]
    assert "get_fewshot_max_tokens" in files["utils.py"]["role"]
    assert boundary["executable_closure_status"].startswith("NOT_PINNED")
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


def test_expel_inspired_lesson_arm_is_not_the_faithful_direct_two_channel_arm() -> None:
    value = _manifest()
    boundary = value["minimal_reproduction_boundary"]
    contract = value["future_run_contract"]

    assert value["selection"]["arm_id"] == "B2_EXPEL_INSPIRED_TEXT_LESSON"
    assert "not faithful-direct" in value["selection"]["why_this_prior"]
    assert "B2_EXPEL_DIRECT" in " ".join(boundary["algorithm"])
    observations = boundary["faithful_direct_source_observations"]
    assert "numbered" in observations["global_rule_channel"]
    assert "successful" in observations["successful_trajectory_fewshot_channel"]
    assert "10" in observations["rule_cap_ambiguity"]
    assert "20" in observations["rule_cap_ambiguity"]
    assert "FAISS" in observations["retrieval_ambiguity"]
    assert "B2_EXPEL_DIRECT" in contract["direct_vs_wrapper_parity"]
    assert "global numbered-rule bytes" in contract["direct_vs_wrapper_parity"]


def test_expel_direct_runtime_qualification_is_hash_bound_and_claim_bounded() -> None:
    runtime = json.loads((RUNTIME / "runtime_pin.v1.json").read_text(encoding="utf-8"))
    fixture = json.loads(
        (RUNTIME / "direct_capture_fixture.v1.json").read_text(encoding="utf-8")
    )
    qualification = json.loads(QUALIFICATION.read_text(encoding="utf-8"))

    runtime_unsigned = dict(runtime)
    runtime_digest = runtime_unsigned.pop("runtime_pin_sha256")
    fixture_unsigned = dict(fixture)
    fixture_digest = fixture_unsigned.pop("fixture_sha256")
    assert runtime_digest == canonical_sha256(runtime_unsigned)
    assert fixture_digest == canonical_sha256(fixture_unsigned)
    assert qualification["status"] == (
        "DIRECT_AND_INDEPENDENT_WRAPPER_VECTOR_EXECUTED_EXACT_PARITY"
    )
    assert qualification["runtime"]["runtime_pin_sha256"] == runtime_digest
    assert qualification["runtime"]["fixture_sha256"] == fixture_digest
    assert qualification["runtime"]["runtime_pin_file_sha256"] == sha256(
        (RUNTIME / "runtime_pin.v1.json").read_bytes()
    ).hexdigest()
    assert qualification["runtime"]["fixture_file_sha256"] == sha256(
        (RUNTIME / "direct_capture_fixture.v1.json").read_bytes()
    ).hexdigest()

    for field, path in {
        "adapter": ROOT / "src/hswm/experiments/expel_b2_adapter.py",
        "upstream_capture": ROOT / "scripts/capture_hswm_expel_b2_upstream.py",
        "independent_wrapper_vector_capture": (
            ROOT / "scripts/capture_hswm_expel_b2_wrapper_vector.py"
        ),
        "parity_checker": ROOT / "scripts/check_hswm_expel_b2_direct_parity.py",
    }.items():
        assert qualification["source_code_sha256"][field] == sha256(
            path.read_bytes()
        ).hexdigest()

    assert all(qualification["capture"]["comparisons"].values())
    assert qualification["capture"]["network_connect_attempts_per_side"] == 0
    assert qualification["capture"]["llm_calls_per_side"] == 0
    assert qualification["capture"]["simulator_steps_per_side"] == 0
    assert qualification["capture"]["independent_wrapper_imported_upstream_agent"] is False
    assert "NOT_EXPEL_EFFICACY" in qualification["claim_ceiling"]
    assert "NOT_HSWM_ADMISSION" in qualification["claim_ceiling"]
