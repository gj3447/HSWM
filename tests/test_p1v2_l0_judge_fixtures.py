from __future__ import annotations

import json

from p1v2_l0_judge_fixtures import run_fixtures


def test_real_judge_fixture_runner_separates_positive_and_negative(tmp_path):
    manifest = run_fixtures(tmp_path)

    assert manifest["positive_expected"] == "PASS"
    assert manifest["injected_negative_expected"] == "KILL"
    assert len(manifest["fixture_manifest_sha256"]) == 64
    positive = json.loads(
        (tmp_path / "p1v2_l0_positive_judge_receipt_20260724.json").read_text()
    )
    negative = json.loads(
        (tmp_path / "p1v2_l0_injected_negative_judge_receipt_20260724.json").read_text()
    )
    assert positive["verdict"] == "PASS"
    assert negative["verdict"] == "KILL"
