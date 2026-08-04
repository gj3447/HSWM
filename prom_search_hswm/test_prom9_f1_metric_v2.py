"""Unit tests for prom9_f1_metric_v2 — selective-utility metric + identity discipline.

Synthetic fixtures build a fully hash-consistent 48-component development cohort
(suite self-hash, manifest binding, source-derived component schedule) so the
loader/verifier path is exercised end to end.  The golden smoke test runs
against the REAL frozen t2/t3b suites when they exist on disk (Dell) and is
skipped elsewhere.
"""
from __future__ import annotations

import copy
import os
from fractions import Fraction
from pathlib import Path

import pytest

from prom_search_hswm.hswm_function_network import (
    FLAT_ARM,
    REMOVAL_ARM,
    SHUFFLE_ARM,
    TYPED_ARM,
    VECTOR_ARM,
)
from prom_search_hswm.hswm_typed_ports import canonical_sha256
from prom_search_hswm import prom9_f1_metric_v2 as m2
from prom_search_hswm.prom9_f1_metric_v2 import MetricV2Refusal

ARMS = (TYPED_ARM, FLAT_ARM, VECTOR_ARM, REMOVAL_ARM, SHUFFLE_ARM)
RUN_ID = "metric-v2-test-run"
N_ITEMS = 48

# Outcome pattern over item indices 0..47 (hand-verified expectations below):
#   typed   : correct i<24, wrong 24<=i<28, rest abstain -> U(c=2) = 16/48 = 1/3
#   flat    : correct i<16, wrong 16<=i<24, rest abstain -> U(c=2) = 0
#   vector  : correct i<20, wrong 20<=i<23, rest abstain -> U(c=2) = 14/48 = 7/24
#   removal : abstain everywhere                        -> U(c=2) = 0
#   shuffle : correct i<18, wrong 18<=i<21, rest abstain -> U(c=2) = 12/48 = 1/4
_PATTERN = {
    TYPED_ARM: (24, 28),
    FLAT_ARM: (16, 24),
    VECTOR_ARM: (20, 23),
    REMOVAL_ARM: (0, 0),
    SHUFFLE_ARM: (18, 21),
}


def _item_id(index: int) -> str:
    return f"item-{index:02d}"


def _entity_id(index: int) -> str:
    return f"entity-{index:02d}"


def _component_id(index: int) -> str:
    return canonical_sha256(
        {
            "schema_version": "hswm-source-entity-connected-component/v1",
            "source_entity_ids": [_entity_id(index)],
        }
    )


def _answer_for(arm: str, index: int) -> dict:
    correct_until, wrong_until = _PATTERN[arm]
    if index < correct_until:
        # case/whitespace noise must still normalize to the accepted answer
        return {"abstain": False, "answer": f"  ANSWER-{_item_id(index).split('-')[1]}\n"}
    if index < wrong_until:
        return {"abstain": False, "answer": f"fabricated-{index}"}
    return {"abstain": True, "answer": ""}


def _accepted_answer(index: int) -> str:
    return f"answer-{_item_id(index).split('-')[1]}"


def _build_fixture() -> dict:
    manifest = {
        "schema_version": "hswm-prom9-f1-manifest/v3",
        "mode": "development",
        "run_id": RUN_ID,
        "items": [
            {
                "item_id": _item_id(i),
                "component_id": _component_id(i),
                "candidates": [{"source_entity_id": _entity_id(i)}],
            }
            for i in range(N_ITEMS)
        ],
    }
    item_runs = [
        {
            "item_id": _item_id(i),
            "arm_id": arm,
            "answer": _answer_for(arm, i),
        }
        for i in range(N_ITEMS)
        for arm in ARMS
    ]
    suite = {
        "schema_version": "hswm-prom9-f1-suite/v4",
        "mode": "development",
        "run_id": RUN_ID,
        "manifest_sha256": canonical_sha256(manifest),
        "item_runs": item_runs,
    }
    suite["suite_receipt_sha256"] = canonical_sha256(suite)
    gold = {
        "schema_version": "hswm-prom9-f1-gold/v2",
        "run_id": RUN_ID,
        "items": [
            {"item_id": _item_id(i), "accepted_answers": [_accepted_answer(i)]}
            for i in range(N_ITEMS)
        ],
    }
    selection = {
        "schema_version": "hswm-prom9-f1-r8-cohort-selection/v4",
        "development": {
            "item_ids": [_item_id(i) for i in range(N_ITEMS)],
            "component_schedule": [
                {
                    "component_id": _component_id(i),
                    "item_ids": [_item_id(i)],
                    "source_entity_ids": [_entity_id(i)],
                    "cluster_size": 1,
                }
                for i in range(N_ITEMS)
            ],
        },
    }
    return {
        "suite": suite,
        "gold": gold,
        "manifest": manifest,
        "selection": selection,
    }


@pytest.fixture()
def evidence() -> m2.DevelopmentEvidence:
    fixture = _build_fixture()
    return m2.verify_development_identity(
        suite=fixture["suite"],
        gold=fixture["gold"],
        manifest=fixture["manifest"],
        selection=fixture["selection"],
    )


def test_per_arm_utility_exact(evidence):
    utility = m2.per_arm_utility(evidence, c=2)
    assert utility[TYPED_ARM] == Fraction(1, 3)
    assert utility[FLAT_ARM] == Fraction(0)
    assert utility[VECTOR_ARM] == Fraction(7, 24)
    assert utility[REMOVAL_ARM] == Fraction(0)  # abstain-only degenerate arm
    assert utility[SHUFFLE_ARM] == Fraction(1, 4)


def test_outcome_classification(evidence):
    assert evidence.outcomes[(_item_id(0), TYPED_ARM)] == "correct"
    assert evidence.outcomes[(_item_id(26), TYPED_ARM)] == "wrong"
    assert evidence.outcomes[(_item_id(40), TYPED_ARM)] == "abstain"
    assert all(
        evidence.outcomes[(_item_id(i), REMOVAL_ARM)] == "abstain"
        for i in range(N_ITEMS)
    )


def test_paired_contrasts_exact(evidence):
    contrasts = m2.paired_contrasts(evidence, c=2)
    assert contrasts[FLAT_ARM] == Fraction(1, 3)
    assert contrasts[VECTOR_ARM] == Fraction(1, 24)
    assert contrasts[REMOVAL_ARM] == Fraction(1, 3)
    assert contrasts[SHUFFLE_ARM] == Fraction(1, 12)
    assert m2.min_contrast(evidence, c=2) == Fraction(1, 24)


def test_c_sweep_exact(evidence):
    sweep = m2.c_sweep(evidence, (1, 2, 3))
    assert sweep[1]["min_contrast"] == Fraction(1, 16)
    assert sweep[2]["min_contrast"] == Fraction(1, 24)
    assert sweep[3]["min_contrast"] == Fraction(1, 48)


def test_coverage_v1_contrasts_exact(evidence):
    v1 = m2.coverage_v1_contrasts(evidence)
    assert v1[FLAT_ARM] == Fraction(1, 6)
    assert v1[VECTOR_ARM] == Fraction(1, 12)
    assert v1[REMOVAL_ARM] == Fraction(1, 2)
    assert v1[SHUFFLE_ARM] == Fraction(1, 8)
    assert min(v1.values()) == Fraction(1, 12)


def test_multi_item_component_pairing():
    # one 2-item component: contrast is the mean of the per-item paired diffs
    outcomes = {}
    for item in ("a", "b"):
        for arm in ARMS:
            outcomes[(item, arm)] = "abstain"
    outcomes[("a", TYPED_ARM)] = "correct"
    outcomes[("b", TYPED_ARM)] = "correct"
    outcomes[("a", FLAT_ARM)] = "wrong"  # diff +3 at c=2
    outcomes[("b", FLAT_ARM)] = "correct"  # diff 0
    component_id = "ab" * 32
    evidence = m2.DevelopmentEvidence(
        accepted={"a": frozenset({"x"}), "b": frozenset({"y"})},
        outcomes=outcomes,
        schedule=(
            {
                "component_id": component_id,
                "item_ids": ["a", "b"],
                "source_entity_ids": ["e"],
                "cluster_size": 2,
            },
        ),
        item_ids=frozenset({"a", "b"}),
        suite_sha256="",
        gold_sha256="",
        manifest_sha256="",
        run_id=RUN_ID,
    )
    per_component = m2.per_component_contrasts(evidence, c=2)
    assert per_component[component_id][FLAT_ARM] == Fraction(3, 2)
    assert m2.paired_contrasts(evidence, c=2)[FLAT_ARM] == Fraction(3, 2)
    # macro over components != global per-arm diff when components differ in size
    assert m2.per_arm_utility(evidence, c=2)[TYPED_ARM] == Fraction(1)


def _drifted(fixture: dict, mutate) -> dict:
    broken = copy.deepcopy(fixture)
    mutate(broken)
    return broken


def _assert_refusal(fixture: dict) -> None:
    with pytest.raises(MetricV2Refusal):
        m2.verify_development_identity(
            suite=fixture["suite"],
            gold=fixture["gold"],
            manifest=fixture["manifest"],
            selection=fixture["selection"],
        )


def test_refuses_tampered_item_run_bytes():
    def mutate(broken):
        broken["suite"]["item_runs"][0]["answer"]["answer"] = "fabricated"

    _assert_refusal(_drifted(_build_fixture(), mutate))


def test_refuses_five_arm_coverage_gap():
    def mutate(broken):
        run = broken["suite"]["item_runs"].pop(0)
        # re-seal the suite so ONLY the coverage check can fire
        broken["suite"]["suite_receipt_sha256"] = canonical_sha256(
            {k: v for k, v in broken["suite"].items() if k != "suite_receipt_sha256"}
        )
        assert run["arm_id"] in ARMS

    _assert_refusal(_drifted(_build_fixture(), mutate))


def test_refuses_gold_identity_drift():
    def mutate(broken):
        broken["gold"]["items"] = broken["gold"]["items"][1:]

    _assert_refusal(_drifted(_build_fixture(), mutate))


def test_refuses_run_identity_drift():
    def mutate(broken):
        broken["manifest"]["run_id"] = "some-other-run"
        broken["suite"]["manifest_sha256"] = canonical_sha256(broken["manifest"])
        broken["suite"]["suite_receipt_sha256"] = canonical_sha256(
            {k: v for k, v in broken["suite"].items() if k != "suite_receipt_sha256"}
        )

    _assert_refusal(_drifted(_build_fixture(), mutate))


def test_refuses_component_source_drift():
    def mutate(broken):
        row = broken["selection"]["development"]["component_schedule"][0]
        row["source_entity_ids"] = ["entity-ff"]

    _assert_refusal(_drifted(_build_fixture(), mutate))


def test_refuses_manifest_hash_drift():
    def mutate(broken):
        broken["manifest"]["items"][0]["candidates"] = [
            {"source_entity_id": "entity-ff"}
        ]
        # suite still points at the ORIGINAL manifest hash

    _assert_refusal(_drifted(_build_fixture(), mutate))


def test_load_development_evidence_roundtrip(tmp_path):
    import json

    fixture = _build_fixture()
    paths = {}
    for name in ("suite", "gold", "manifest", "selection"):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(fixture[name]), encoding="utf-8")
        paths[f"{name}_path"] = path
    evidence = m2.load_development_evidence(**paths)
    assert m2.per_arm_utility(evidence, c=2)[TYPED_ARM] == Fraction(1, 3)
    # one flipped answer in the on-disk suite -> refusal, never silent acceptance
    tampered = json.loads(Path(paths["suite_path"]).read_text(encoding="utf-8"))
    tampered["item_runs"][0]["answer"]["answer"] = "fabricated"
    Path(paths["suite_path"]).write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(MetricV2Refusal):
        m2.load_development_evidence(**paths)


def test_normalize_answer_parity_with_power_module():
    power = pytest.importorskip("prom_search_hswm.prom9_f1_r8_power")
    battery = [
        "James B. Harris",
        "  August 8, 1975  ",
        "RAÚL\tOSORIO\n",
        "Straße  ÜBER  groß",
        "",
        "multiple   spaces\tand\nnewlines",
    ]
    for value in battery:
        assert m2._normalize_answer(value) == power._normalize_answer(value)
    assert m2.NORMALIZE_SOURCE == "power"


_REAL_ROOT = Path("/data/kjra/PROJECT/PI/hswm_f1_r8_a3_20260803")
_REAL_SELECTION = _REAL_ROOT / "common" / "selection.v4.json"


def _real_evidence(tag: str) -> m2.DevelopmentEvidence:
    base = _REAL_ROOT / f"development-a3-{tag}"
    return m2.load_development_evidence(
        suite_path=base / "suite.v4.json",
        gold_path=base / "gold.v2.json",
        manifest_path=base / "manifest.v3.json",
        selection_path=_REAL_SELECTION,
    )


@pytest.mark.skipif(
    not os.path.exists(_REAL_SELECTION),
    reason="real frozen a3 suites are absent (non-Dell host)",
)
def test_golden_replay_real_suites():
    t2 = _real_evidence("t2")
    sweep2 = m2.c_sweep(t2, (1, 2, 3))
    utility = sweep2[2]["per_arm_utility"]
    assert abs(float(utility[TYPED_ARM]) - 0.296) < 1e-3
    assert abs(float(utility[SHUFFLE_ARM]) - 0.148) < 1e-3
    assert abs(float(utility[VECTOR_ARM]) - 0.130) < 1e-3
    assert abs(float(utility[FLAT_ARM]) - 0.093) < 1e-3
    assert utility[REMOVAL_ARM] == 0
    assert abs(float(sweep2[1]["min_contrast"]) - 0.083) < 1e-3
    assert abs(float(sweep2[2]["min_contrast"]) - 0.167) < 1e-3
    assert abs(float(sweep2[3]["min_contrast"]) - 0.229) < 1e-3
    # the v1 metric is blind on the same bytes: min contrast exactly 0
    assert min(m2.coverage_v1_contrasts(t2).values()) == 0

    t3b = _real_evidence("t3b")
    sweep3 = m2.c_sweep(t3b, (1, 2, 3))
    assert abs(float(sweep3[2]["per_arm_utility"][TYPED_ARM]) - 0.185) < 1e-3
    assert abs(float(sweep3[1]["min_contrast"]) - (-0.031)) < 1e-3
    assert abs(float(sweep3[2]["min_contrast"]) - 0.083) < 1e-3
    assert abs(float(sweep3[3]["min_contrast"]) - 0.083) < 1e-3
    assert sweep3[2]["per_arm_utility"][REMOVAL_ARM] == 0
