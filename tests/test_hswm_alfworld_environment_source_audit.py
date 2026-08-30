"""Offline checks for the locally authorized ALFWorld candidate boundary."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "_research/causal_composition/priors/alfworld_text_g1_candidate_v1/source_audit.v1.json"
AUTHORIZATION = ROOT / "_research/causal_composition/priors/alfworld_text_g1_candidate_v1/local_use_authorization.v1.json"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


def _audit() -> dict[str, object]:
    return json.loads(AUDIT.read_text(encoding="utf-8"))


def test_alfworld_candidate_has_local_authorization_without_license_overclaim() -> None:
    value = _audit()

    assert value["schema_version"] == "hswm-causal-composition-environment-source-audit/v1"
    assert value["candidate_uid"] == "sym:EnvironmentCandidate:alfworld-text-g1-v1"
    assert value["status"] == (
        "CANDIDATE_SELECTED_LOCAL_RESEARCH_AUTHORIZED_"
        "UPSTREAM_LICENSE_SCOPE_UNRESOLVED_NO_REDISTRIBUTION"
    )
    assert value["selection"]["environment_mode"] == "ALFWORLD_TEXT_ONLY"
    assert value["selection"]["single_task_family"] == "pick_clean_then_place_in_recep"

    blocker = value["blocking_license_scope"]
    assert blocker["code_mit_is_not_data_permission"] is True
    assert blocker["local_execution_decision"] == (
        "AUTHORIZED_BY_USER_FOR_LOCAL_NONREDISTRIBUTIVE_RESEARCH"
    )
    assert blocker["redistribution_decision"] == "BLOCKED"
    assert "annotation" in blocker["unresolved_question"]
    binding = value["local_use_authorization"]
    assert binding["authorization_uid"] == (
        "sym:LocalAuthorization:alfworld-assets-2026-08-30-v1"
    )
    assert binding["sha256"] == hashlib.sha256(AUTHORIZATION.read_bytes()).hexdigest()
    assert ROOT / binding["path"] == AUTHORIZATION
    authorization = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    assert authorization["authorization_uid"] == binding["authorization_uid"]
    assert value["offline_verifier_contract"]["network_access"] == "FORBIDDEN"


def test_local_authorization_is_exactly_scoped_and_not_an_upstream_grant() -> None:
    value = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))

    assert value["schema_version"] == "hswm-external-asset-local-use-authorization/v1"
    assert value["exact_user_message_sha256"] == (
        "ba482edb9b8ba8e8beb4865f7a8df405beedd3eb3f85ae9b125abe33a1116df4"
    )
    assert value["exact_user_message_sha256"] == hashlib.sha256(
        value["exact_user_message_utf8"].encode("utf-8")
    ).hexdigest()
    assert value["status"] == (
        "LOCAL_RESEARCH_FETCH_AND_EXECUTION_AUTHORIZED_"
        "UPSTREAM_LICENSE_SCOPE_UNRESOLVED_NO_REDISTRIBUTION"
    )
    excluded = " ".join(value["scope"]["excluded"])
    assert "redistributing" in excluded
    assert "upstream rightsholder" in excluded
    assert "HSWM canonical Permit" in excluded


def test_alfworld_source_and_observed_asset_pins_have_exact_offline_invariants() -> None:
    value = _audit()
    official = value["official_code_and_paper"]

    assert official["paper"]["arxiv_id"] == "2010.03768v2"
    assert official["repository"]["commit"] == "aaba6870f86c5be6a08a491f32a50b906227bc3e"
    assert official["repository"]["tree"] == "339069f91317079df9e378efd4ab253417d79b82"
    assert official["repository"]["tarball_sha256"] == (
        "5592fbb36124b08d24167c5f7612a55a2cc610e0c39170f638a69b628835ee3b"
    )
    assert official["code_license"]["spdx"] == "MIT"
    assert official["code_license"]["sha256"] == (
        "0bdf8c0558499c192b6ab55818e99e91ef0eb02c6e2d19d907b3f2e14df40590"
    )
    assert official["paper"]["sha256"] == (
        "4be2e61e875ca34f19befa92e8a117347fc380a2076d6e829e22e2a4c03dc9e1"
    )
    assert {
        item["path"]: item["sha256"]
        for item in official["minimal_source_files"]
    } == {
        "README.md": "57285c6ec91cbd135148a992814c9a2f943d40e781cd9ed7c4169b5f9131224a",
        "alfworld/data/README.md": "b30aed4bee175cf0a945d74ab2e39e84429b2ed750788f079ee327b4726bed0c",
        "scripts/alfworld-download": "754c6418eba7234b1ea1c68abcd47ecdb4bfca016f6c918526c575a9e326b755",
        "configs/base_config.yaml": "2fb5f24f344eaaf14d517605a27c248b9bb1bce445ca22f5fc4eb8a6d3156863",
        "alfworld/agents/environment/alfred_tw_env.py": "4d9166363e32f0fa70c63530a900785ddb45c79387a02ebcb9a21252869a8924",
    }
    assert all(
        SHA256.fullmatch(digest)
        for digest in [
            official["paper"]["sha256"],
            official["repository"]["tarball_sha256"],
            official["code_license"]["sha256"],
            *[item["sha256"] for item in official["minimal_source_files"]],
        ]
    )

    assets = value["official_downloaded_assets"]["assets"]
    assert [asset["name"] for asset in assets] == [
        "json_2.1.1_json.zip",
        "json_2.1.1_pddl.zip",
        "json_2.1.3_tw-pddl.zip",
    ]
    assert {
        asset["name"]: (asset["release_tag"], asset["tag_commit"], asset["observed_bytes"], asset["observed_sha256"])
        for asset in assets
    } == {
        "json_2.1.1_json.zip": (
            "0.2.2", "7afaf0c97d453396b0144da915156583f47521d8", 72018818,
            "25171f16e20ad7b048c47275c45b0babf3aa1cbab29cec97387922350a9844bc",
        ),
        "json_2.1.1_pddl.zip": (
            "0.2.2", "7afaf0c97d453396b0144da915156583f47521d8", 34881784,
            "913942ebed06659ea0da2f8122512d98bc6add30d84961ca803132d8fbcad585",
        ),
        "json_2.1.3_tw-pddl.zip": (
            "0.4.2", "1558ba46d078279ecb4c5d33a6cdffc96714a2d2", 36507267,
            "5df77ea759f2211a4106082839ddbbb790f1ba4e7d097ed732cf453f72aa36cf",
        ),
    }
    assert all(GIT_SHA.fullmatch(asset["tag_commit"]) for asset in assets)
    assert all(asset["observed_bytes"] > 0 for asset in assets)
    assert all(SHA256.fullmatch(asset["observed_sha256"]) for asset in assets)
    assert all(asset["github_api_digest"] is None for asset in assets)


def test_alfworld_candidate_preserves_future_information_and_claim_boundaries() -> None:
    value = _audit()
    contract = value["future_g0_g1_fairness_contract"]

    assert {"admissible_commands", "expert plans or traces", "hidden PDDL or simulator state", "final-holdout retrieval"} <= set(contract["forbidden_actor_inputs"])
    assert "unseen validation" in contract["fresh_transfer"]
    assert "separately identified evaluator" in contract["independent_evaluator"]
    assert "same sealed training trajectories" in contract["information_fairness"]
    no_claim = " ".join(value["no_claim"])
    assert "G1 result" in no_claim
    assert "HSWM learning efficacy" in no_claim
    assert "FCL-1" in no_claim
