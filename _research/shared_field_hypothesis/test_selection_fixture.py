from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parent
TASK_CONTRACTS = HERE / "task_contracts.v1.json"
sys.path.insert(0, str(HERE))

import selection_fixture as selection  # noqa: E402


def _action(
    action_id: str,
    *,
    outcome_id: str,
    acceptable: bool,
    reward: int,
    cost: int,
    risk: int,
    relevance: int,
) -> dict:
    return {
        "action_id": action_id,
        "outcome": {
            "outcome_id": outcome_id,
            "acceptable": acceptable,
            "payload": {"description": f"frozen outcome for {action_id}"},
        },
        "reward": reward,
        "cost": cost,
        "risk": risk,
        "relevance": relevance,
        "evidence_ids": ["e-env", "e-tools"],
    }


def _source() -> dict:
    return {
        "schema": selection.SOURCE_SCHEMA,
        "fixture_id": "cost-risk-world-001",
        "evidence_state": [
            {
                "evidence_id": "e-env",
                "payload": {"red_door": "unstable", "goal": "exit safely"},
            },
            {
                "evidence_id": "e-tools",
                "payload": {"key": True, "lockpick": True, "time_budget": 12},
            },
        ],
        "actions": [
            _action(
                "act-break-lock",
                outcome_id="out-break",
                acceptable=True,
                reward=95,
                cost=10,
                risk=2,
                relevance=85,
            ),
            _action(
                "act-use-key",
                outcome_id="out-key",
                acceptable=True,
                reward=90,
                cost=3,
                risk=1,
                relevance=80,
            ),
            _action(
                "act-use-red-door",
                outcome_id="out-red",
                acceptable=False,
                reward=100,
                cost=1,
                risk=10,
                relevance=100,
            ),
            _action(
                "act-wait",
                outcome_id="out-wait",
                acceptable=True,
                reward=70,
                cost=1,
                risk=0,
                relevance=20,
            ),
        ],
        "constraints": {
            "max_cost": 12,
            "max_risk": 3,
            "min_reward": 60,
            "cost_weight": 2,
            "risk_weight": 3,
        },
        "commitment_sha256": selection.COMMITMENT_SENTINEL,
    }


def _compile(payload: dict | None = None) -> selection.CompiledSelectionFixture:
    return selection.compile_selection_fixture(
        selection.seal_selection_source(payload if payload is not None else _source())
    )


def test_fixture_is_byte_deterministic_and_hash_bound() -> None:
    source = selection.seal_selection_source(_source())
    first = selection.compile_selection_fixture(source)
    second = selection.compile_selection_fixture(source)

    assert first.canonical_bytes == second.canonical_bytes
    assert first.compiled_sha256 == second.compiled_sha256
    assert first.source_sha256 == second.source_sha256
    assert first.evidence_state_sha256 == second.evidence_state_sha256
    assert first.oracle_sha256 == second.oracle_sha256
    assert first.document["gold_oracle_basis"].endswith("relevance excluded")
    assert first.document["claim_boundary"] == {
        "model_arm_implemented": False,
        "result_claimed": False,
        "efficacy_claimed": False,
    }


def test_top_relevance_is_refused_and_cost_risk_oracle_selects_independently() -> None:
    compiled = _compile()
    assert compiled.gold_action_id == "act-use-key"
    assert compiled.document["top_relevance_action_id"] == "act-use-red-door"
    assert compiled.document["separation_kind"] == (
        "TOP_RELEVANCE_UNSAFE_OR_CONSTRAINT_INVALID"
    )

    unsafe = compiled.action("act-use-red-door")
    assert unsafe["decision"] == "REFUSED"
    assert unsafe["selected"] is False
    assert unsafe["regret"] is None
    assert unsafe["refusal_reasons"] == [
        "UNACCEPTABLE_OUTCOME",
        "RISK_CAP_EXCEEDED",
    ]

    gold = compiled.action("act-use-key")
    assert gold["decision"] == "ELIGIBLE"
    assert gold["utility"] == 81
    assert gold["regret"] == 0


def test_regret_is_exact_and_deterministic_for_feasible_actions() -> None:
    compiled = _compile()
    assert compiled.action("act-break-lock")["utility"] == 69
    assert compiled.action("act-break-lock")["regret"] == 12
    assert compiled.action("act-wait")["utility"] == 68
    assert compiled.action("act-wait")["regret"] == 13

    replay = _compile()
    assert replay.action("act-break-lock")["regret"] == 12
    assert replay.action("act-wait")["regret"] == 13


def test_relevance_mutation_does_not_change_gold_or_regret() -> None:
    baseline = _compile()
    payload = _source()
    payload["actions"][0]["relevance"] = 110
    payload["actions"][2]["relevance"] = 100
    reranked = _compile(payload)

    assert reranked.document["top_relevance_action_id"] == "act-break-lock"
    assert reranked.document["separation_kind"] == "TOP_RELEVANCE_COST_SUBOPTIMAL"
    assert reranked.gold_action_id == baseline.gold_action_id == "act-use-key"
    assert reranked.action("act-break-lock")["regret"] == 12
    assert reranked.action("act-wait")["regret"] == 13


def test_source_tamper_without_new_commitment_is_refused() -> None:
    source = selection.seal_selection_source(_source())
    payload = json.loads(source.decode("utf-8"))
    payload["actions"][2]["risk"] = 0
    tampered = selection.canonical_json_bytes(payload)

    with pytest.raises(selection.SelectionTamperError, match="commitment mismatch"):
        selection.compile_selection_fixture(tampered)


def test_compiled_fixture_tamper_is_refused_by_replay_verifier() -> None:
    source = selection.seal_selection_source(_source())
    compiled = selection.compile_selection_fixture(source)
    payload = compiled.document
    payload["gold_action_id"] = "act-use-red-door"

    with pytest.raises(selection.SelectionTamperError, match="tamper/drift"):
        selection.verify_compiled_selection_fixture(
            source, selection.canonical_json_bytes(payload)
        )


def test_duplicate_ids_with_different_payloads_and_unknown_evidence_are_refused() -> None:
    payload = _source()
    duplicate = copy.deepcopy(payload["actions"][0])
    duplicate["cost"] = 1
    payload["actions"].insert(1, duplicate)
    with pytest.raises(selection.SelectionDuplicateIDError, match="action_id"):
        _compile(payload)

    payload = _source()
    payload["actions"][0]["evidence_ids"] = ["e-missing"]
    with pytest.raises(selection.SelectionFixtureError, match="unknown evidence"):
        _compile(payload)


def test_ambiguous_or_missing_gold_and_missing_separation_are_refused() -> None:
    payload = _source()
    # break-lock utility becomes the same 81 as use-key.
    payload["actions"][0]["reward"] = 107
    with pytest.raises(selection.SelectionOracleError, match="ambiguous"):
        _compile(payload)

    payload = _source()
    for action in payload["actions"]:
        action["outcome"]["acceptable"] = False
    with pytest.raises(selection.SelectionOracleError, match="no action"):
        _compile(payload)

    payload = _source()
    payload["actions"][1]["relevance"] = 101
    with pytest.raises(selection.SelectionOracleError, match="lacks separation"):
        _compile(payload)


def test_noncanonical_json_and_noninteger_score_are_refused() -> None:
    sealed = json.loads(selection.seal_selection_source(_source()).decode("utf-8"))
    pretty = json.dumps(sealed, indent=2).encode("utf-8")
    with pytest.raises(selection.CanonicalSelectionError, match="not canonical"):
        selection.compile_selection_fixture(pretty)

    payload = _source()
    payload["actions"][0]["cost"] = 1.5
    with pytest.raises(selection.SelectionFixtureError, match="integer"):
        _compile(payload)


def test_task_contract_freezes_roles_gates_and_no_result_boundary() -> None:
    contract = json.loads(TASK_CONTRACTS.read_text(encoding="utf-8"))
    assert contract["task_schemas"]["independent_selection_action"][
        "source_schema"
    ] == selection.SOURCE_SCHEMA
    assert contract["task_schemas"]["independent_selection_action"][
        "compiled_schema"
    ] == selection.COMPILED_SCHEMA
    assert [arm["role"] for arm in contract["arm_interface_expectations"]] == [
        "A",
        "B",
        "C",
        "D",
    ]
    gates = contract["exact_g2_exit_gates"]
    assert gates["all_gates_required"] is True
    assert gates["overall_status"] == "NOT_EXITED"
    assert {gate["id"] for gate in gates["gates"]} == {
        "G2-01-INDEPENDENT-LABELS",
        "G2-02-SELECTION-SEPARATION",
        "G2-03-REVISION-STREAM",
        "G2-04-TEMPORAL-ORACLE",
        "G2-05-BRANCH-CONFLUENCE",
        "G2-06-FAIL-CLOSED",
        "G2-07-ARM-INTERFACES",
        "G2-08-FROZEN-CONTAMINATION-BOUNDARY",
        "G2-09-NO-PREMATURE-RESULT",
    }
    assert all(value is False for value in contract["claim_boundary"].values() if isinstance(value, bool))
