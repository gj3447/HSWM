from __future__ import annotations

from pathlib import Path

import pytest

from _research.dgx_q1.live_experiment import (
    LiveExperimentRefusal,
    _runner_input_file_map,
    load_frozen_inputs,
)
from _research.dgx_q1.live_preregistration import freeze_live_preregistration
from tests.test_dgx_q1_live_preregistration import preregistration_inputs


def test_loads_all_frozen_runner_inputs_without_dispatch(tmp_path: Path) -> None:
    root = tmp_path / "freeze"
    freeze_live_preregistration(root, preregistration_inputs())
    loaded = load_frozen_inputs(root)
    assert len(loaded["materials"]) == 24
    assert len(loaded["identities"]) == 6
    assert len(loaded["provenance"]) == 3
    assert _runner_input_file_map(loaded) == {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_missing_frozen_material_refuses_before_lease(tmp_path: Path) -> None:
    root = tmp_path / "freeze"
    freeze_live_preregistration(root, preregistration_inputs())
    (root / "materials/QCASE-001/rng.bin").unlink()
    with pytest.raises(LiveExperimentRefusal):
        load_frozen_inputs(root)
