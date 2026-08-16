from __future__ import annotations

import importlib
from pathlib import Path

from _research.f_series import MODULES, REPO_ROOT, SOURCE_ROOT, source_path


EXPECTED_MODULES = {
    "b1_identity_unlock",
    "f2_delta_w_credit",
    "f3_agent_ab_transfer",
    "f3_agent_ab_transfer_r2",
    "f3_agent_ab_transfer_r3",
    "f3v2_arms",
    "f3v2_canary_gate",
    "f3v2_dev_smoke",
    "f3v2_procedural_worlds",
    "f3v2_sealed_prep",
    "f4_topology_learning",
    "f4_topology_learning_r2",
    "f5_consolidation",
    "r1_t1_retry",
    "r2_ml_walk",
    "r3_dump_replay_artifacts",
    "r3_replay_judge",
    "r3_walk_regime",
    "t1_entrance_reach",
    "t3_score_null",
}


def test_f_series_has_one_canonical_source_only_surface() -> None:
    assert set(MODULES) == EXPECTED_MODULES
    assert REPO_ROOT == Path(__file__).resolve().parents[1]
    assert SOURCE_ROOT == REPO_ROOT / "_research" / "f_series"

    for module_name in sorted(EXPECTED_MODULES):
        filename = f"{module_name}.py"
        assert not (REPO_ROOT / filename).exists()
        assert source_path(filename) == SOURCE_ROOT / filename


def test_all_f_series_modules_import_by_canonical_name() -> None:
    imported = {
        name: importlib.import_module(f"_research.f_series.{name}")
        for name in sorted(EXPECTED_MODULES)
    }

    assert imported["f3_agent_ab_transfer"].f2 is imported["f2_delta_w_credit"]
    assert imported["f3_agent_ab_transfer_r2"].f3r1 is imported[
        "f3_agent_ab_transfer"
    ]
    assert imported["f3v2_arms"].fw is imported["f3v2_procedural_worlds"]
    assert imported["f4_topology_learning_r2"].f4r1 is imported[
        "f4_topology_learning"
    ]


def test_source_path_rejects_non_basename_inputs() -> None:
    for invalid in ("../f2_delta_w_credit.py", "f2_delta_w_credit", "/tmp/x.py"):
        try:
            source_path(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"source_path accepted {invalid!r}")
