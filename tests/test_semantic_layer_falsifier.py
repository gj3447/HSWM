"""End-to-end registered gates for the heterogeneous semantic stack."""
from __future__ import annotations

import semantic_layer_falsifier as falsifier


def test_small_exhaustive_semantic_layer_matrix_clears_every_gate():
    result = falsifier.run_experiment(n_worlds=2)

    assert result["n_cases"] == 8
    assert result["counts"]["typed_exact"] == 8
    assert result["counts"]["single_frontier_ambiguous_refused"] == 8
    assert result["counts"]["homogeneous_repeat_exact"] == 4
    assert result["counts"]["branch_erasure_atomic_refused"] == 8
    assert result["counts"][
        "homogeneous_paired_assignment_signature_collisions"
    ] == 4
    assert result["counts"]["value_null_original_exact"] == 0
    assert result["counts"]["reducer_null_original_exact"] == 0
    assert result["all_gates_pass"] is True
    assert result["verdict"] == (
        "SYNTHETIC_HETEROGENEOUS_TYPED_LAYER_MECHANISM_PASS"
    )


def test_non_positive_world_count_is_rejected():
    for value in (0, -1):
        try:
            falsifier.run_experiment(n_worlds=value)
        except ValueError as exc:
            assert "positive integer" in str(exc)
        else:
            raise AssertionError(f"invalid world count {value} was accepted")
