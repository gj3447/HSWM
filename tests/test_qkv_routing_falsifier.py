from __future__ import annotations

import qkv_routing_falsifier as falsifier


def test_exhaustive_order_collision_teeth_pass() -> None:
    result = falsifier.run_experiment(4)

    assert result["status"] == "PASS"
    assert result["n_programs"] == 8
    assert result["counts"]["ordered_k2_exact"] == 8
    assert result["counts"]["matched_k1_reaches_k2_target"] == 0
    assert result["counts"]["key_null_exact"] == 0
    assert result["counts"]["value_null_exact"] == 0
    assert result["counts"]["unordered_bag_exact"] == 4
    assert all(result["gates"].values())


def test_result_and_receipt_roots_are_deterministic() -> None:
    first = falsifier.run_experiment(2)
    second = falsifier.run_experiment(2)

    assert first == second
    assert first["result_sha256"] == second["result_sha256"]
    assert first["receipt_root_sha256"] == second["receipt_root_sha256"]
