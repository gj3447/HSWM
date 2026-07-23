from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

import pytest

from hswm_weight_snapshot import canonical_sha256
from p1v2_prompt_parity import ARM_IDS
from p1v4_replay_judge import (
    P1V3_FROZEN_SCORER_SHA256,
    P1V4ReplayJudgeError,
    build_replay_bundle,
    replay_metric,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _sealed_fixture(*, typed_improvements: int = 1):
    plans = [{"case_id": "fixture:0"}]
    budget = {
        "schema_version": "hswm-p1v4-replay-fixture-budget/v1",
        "parity": {"case_plans": plans},
        "score_contract": {
            "primary_metric": "typed_improvement_count_vs_no_memory",
            "baseline": 0,
            "direction": "higher",
            "required_valid_case_count": 1,
            "minimum_typed_improvements_for_pass": 1,
        },
    }
    budget["budget_manifest_sha256"] = canonical_sha256(budget)
    answers = {
        arm: canonical_sha256(
            {
                "arm": arm,
                "answer": (
                    "typed"
                    if typed_improvements and arm == "T1_typed_lesson"
                    else "base"
                ),
            }
        )
        for arm in ARM_IDS
    }
    observation = {
        "schema_version": "hswm-p1v4-replay-fixture-observation/v1",
        "case_id": "fixture:0",
        "arms": {
            arm: {
                "answers_sha256": answers[arm],
                "set_match": int(
                    arm == "T1_typed_lesson" if typed_improvements else True
                ),
                "logical_call_count": 1,
                "user_prompt_tokens": 32,
            }
            for arm in ARM_IDS
        },
        "budget": {"logical_model_calls": 4, "token_parity": True},
        "gold_boundary": {
            "gold_sent_to_answer_port": False,
            "gold_opened_only_after_all_arm_answers": True,
            "gold_values_published": False,
        },
    }
    observation["observation_sha256"] = canonical_sha256(observation)
    evidence = {
        "schema_version": "hswm-p1v4-replay-fixture-evidence/v1",
        "budget_manifest_sha256": budget["budget_manifest_sha256"],
        "observations": [observation],
    }
    evidence["evidence_sha256"] = canonical_sha256(evidence)
    return evidence, budget


def test_bundle_recomputes_metric_without_a_reported_value():
    evidence, budget = _sealed_fixture()
    bundle = build_replay_bundle(evidence=evidence, budget=budget)

    assert "value" not in bundle
    assert "metric" not in bundle
    assert replay_metric(bundle) == 1.0


def test_bundle_contract_names_the_actual_frozen_historic_scorer():
    scorer_bytes = (REPO_ROOT / "p1v3_heldout_judge.py").read_bytes()

    assert sha256(scorer_bytes).hexdigest() == P1V3_FROZEN_SCORER_SHA256


def test_self_contained_scorer_matches_frozen_historic_metric():
    from p1v3_heldout_judge import judge_heldout

    for improvements in (0, 1):
        evidence, budget = _sealed_fixture(typed_improvements=improvements)
        historic = judge_heldout(
            evidence=evidence,
            budget=budget,
            judge_script_sha256=P1V3_FROZEN_SCORER_SHA256,
        )
        bundle = build_replay_bundle(evidence=evidence, budget=budget)

        assert replay_metric(bundle) == float(historic["value"])


def test_exact_lakatotree_positional_cli_prints_metric(tmp_path):
    evidence, budget = _sealed_fixture()
    result_path = tmp_path / "result.json"
    result_path.write_text(
        json.dumps(build_replay_bundle(evidence=evidence, budget=budget)),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            str(REPO_ROOT / "p1v4_replay_judge.py"),
            str(result_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "metric=1\n"
    assert completed.stderr == ""


def test_nested_evidence_tamper_fails_closed():
    evidence, budget = _sealed_fixture()
    bundle = deepcopy(build_replay_bundle(evidence=evidence, budget=budget))
    bundle["evidence"]["observations"][0]["arms"][ARM_IDS[0]]["set_match"] = 0

    with pytest.raises(P1V4ReplayJudgeError, match="self-hash drifted"):
        replay_metric(bundle)


def test_resealed_bundle_cannot_override_frozen_scorer_hash():
    evidence, budget = _sealed_fixture()
    bundle = deepcopy(build_replay_bundle(evidence=evidence, budget=budget))
    bundle["scorer_contract"]["scorer_sha256"] = "0" * 64
    unsigned = dict(bundle)
    unsigned.pop("bundle_sha256")
    bundle["bundle_sha256"] = canonical_sha256(unsigned)

    with pytest.raises(P1V4ReplayJudgeError, match="frozen scorer file drifted"):
        replay_metric(bundle)


def test_prefilled_metric_field_is_rejected_instead_of_trusted():
    evidence, budget = _sealed_fixture()
    bundle = deepcopy(build_replay_bundle(evidence=evidence, budget=budget))
    bundle["metric"] = 999
    unsigned = dict(bundle)
    unsigned.pop("bundle_sha256")
    bundle["bundle_sha256"] = canonical_sha256(unsigned)

    with pytest.raises(P1V4ReplayJudgeError, match="fields drifted"):
        replay_metric(bundle)
