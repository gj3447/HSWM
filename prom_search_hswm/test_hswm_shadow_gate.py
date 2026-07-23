#!/usr/bin/env python3
from __future__ import annotations

import unittest

from hswm_shadow_gate import (
    DEFAULT_THRESHOLDS,
    GateThresholds,
    HyperEdge,
    TopologyOp,
    active_edges,
    apply_ops,
    canary_preservation,
    edge_id_for,
    evaluate_gate,
    mean_delta,
)


def base_edge(edge_id: str, members, invalid_at=None) -> HyperEdge:
    return HyperEdge(
        edge_id=edge_id,
        members=tuple(sorted(members)),
        origin="base",
        valid_at_round=0,
        invalid_at_round=invalid_at,
    )


class CanaryPreservationTest(unittest.TestCase):
    def test_no_regression_is_100(self):
        self.assertEqual(canary_preservation([0.5, 0.7], [0.5, 0.71], 0.01), 100.0)

    def test_regression_threshold_is_strict(self):
        # post == pre - epsilon is NOT a regression; post < pre - epsilon is.
        self.assertEqual(canary_preservation([0.5], [0.49], 0.01), 100.0)
        self.assertEqual(canary_preservation([0.5], [0.489], 0.01), 0.0)

    def test_partial_regression_rate(self):
        pre = [0.5, 0.5, 0.5, 0.5]
        post = [0.5, 0.5, 0.5, 0.4]
        self.assertEqual(canary_preservation(pre, post, 0.01), 75.0)

    def test_length_mismatch_and_empty_fail_closed(self):
        with self.assertRaises(ValueError):
            canary_preservation([0.5], [0.5, 0.5], 0.01)
        with self.assertRaises(ValueError):
            canary_preservation([], [], 0.01)

    def test_mean_delta(self):
        self.assertAlmostEqual(mean_delta([0.5, 0.6], [0.55, 0.5]), -0.025)
        with self.assertRaises(ValueError):
            mean_delta([], [])


class GateVerdictTest(unittest.TestCase):
    def test_all_pass(self):
        verdict = evaluate_gate(
            canary_preservation_pct=100.0,
            fresh_delta=0.01,
            target_delta=0.05,
            canary_n=60,
            target_n=30,
        )
        self.assertTrue(verdict.passed)
        self.assertEqual(verdict.reasons, ())
        self.assertIsNone(verdict.primary_reason)

    def test_canary_harm_only(self):
        verdict = evaluate_gate(
            canary_preservation_pct=97.9,
            fresh_delta=0.01,
            target_delta=0.05,
            canary_n=60,
            target_n=30,
        )
        self.assertFalse(verdict.passed)
        self.assertEqual(verdict.primary_reason, "canary_harm")

    def test_fresh_harm_only(self):
        verdict = evaluate_gate(
            canary_preservation_pct=100.0,
            fresh_delta=-0.011,
            target_delta=0.05,
            canary_n=60,
            target_n=30,
        )
        self.assertFalse(verdict.passed)
        self.assertEqual(verdict.primary_reason, "fresh_harm")

    def test_no_target_gain_only(self):
        verdict = evaluate_gate(
            canary_preservation_pct=100.0,
            fresh_delta=0.0,
            target_delta=0.029,
            canary_n=60,
            target_n=30,
        )
        self.assertFalse(verdict.passed)
        self.assertEqual(verdict.primary_reason, "no_target_gain")

    def test_priority_canary_before_fresh_before_target(self):
        verdict = evaluate_gate(
            canary_preservation_pct=90.0,
            fresh_delta=-0.05,
            target_delta=0.0,
            canary_n=60,
            target_n=30,
        )
        self.assertEqual(
            verdict.reasons, ("canary_harm", "fresh_harm", "no_target_gain")
        )
        self.assertEqual(verdict.primary_reason, "canary_harm")

    def test_insufficient_slices_fail_closed_and_outrank(self):
        verdict = evaluate_gate(
            canary_preservation_pct=100.0,
            fresh_delta=0.1,
            target_delta=0.1,
            canary_n=19,
            target_n=9,
        )
        self.assertFalse(verdict.passed)
        self.assertEqual(
            verdict.reasons, ("insufficient_canary_slice", "insufficient_target_slice")
        )

    def test_custom_thresholds(self):
        thresholds = GateThresholds(target_gain_min=0.0)
        verdict = evaluate_gate(
            canary_preservation_pct=98.0,
            fresh_delta=-0.01,
            target_delta=0.0,
            canary_n=20,
            target_n=10,
            thresholds=thresholds,
        )
        self.assertTrue(verdict.passed)

    def test_boundary_values_are_inclusive(self):
        verdict = evaluate_gate(
            canary_preservation_pct=98.0,
            fresh_delta=-0.01,
            target_delta=0.03,
            canary_n=20,
            target_n=10,
        )
        self.assertTrue(verdict.passed)


class ApplyOpsTest(unittest.TestCase):
    def test_add_creates_edge_and_dedups(self):
        edges = (base_edge("b1", [1, 2, 3]),)
        ops = [TopologyOp("ADD", (), ((4, 5, 6),)), TopologyOp("ADD", (), ((6, 5, 4),))]
        new_edges, entries = apply_ops(edges, ops, 1)
        self.assertEqual(len(new_edges), 2)
        adds = [entry for entry in entries if entry["op"] == "ADD"]
        self.assertEqual(len(adds), 1)  # second identical ADD is a no-op
        self.assertEqual(active_edges(new_edges)[1].members, (4, 5, 6))

    def test_split_supersedes_parent_and_preserves_history(self):
        edges = (base_edge("b1", [1, 2, 3, 4]),)
        ops = [TopologyOp("SPLIT", ("b1",), ((1, 2), (3, 4)))]
        new_edges, entries = apply_ops(edges, ops, 2)
        self.assertEqual(len(new_edges), 3)  # parent preserved in ledger
        parent = next(edge for edge in new_edges if edge.edge_id == "b1")
        self.assertEqual(parent.invalid_at_round, 2)
        active = active_edges(new_edges)
        self.assertEqual(len(active), 2)
        self.assertTrue(all(edge.origin == "split" for edge in active))
        kinds = [entry["op"] for entry in entries]
        self.assertEqual(kinds, ["SUPERSEDE", "ADD", "ADD"])

    def test_split_must_partition_parent(self):
        edges = (base_edge("b1", [1, 2, 3]),)
        with self.assertRaises(ValueError):
            apply_ops(edges, [TopologyOp("SPLIT", ("b1",), ((1, 2), (2, 4)))], 1)

    def test_merge_supersedes_both_parents(self):
        edges = (base_edge("b1", [1, 2, 3]), base_edge("b2", [3, 4, 5]))
        ops = [TopologyOp("MERGE", ("b1", "b2"), ((1, 2, 3, 4, 5),))]
        new_edges, entries = apply_ops(edges, ops, 3)
        active = active_edges(new_edges)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].origin, "merge")
        self.assertEqual(active[0].members, (1, 2, 3, 4, 5))
        superseded = [edge for edge in new_edges if edge.invalid_at_round == 3]
        self.assertEqual(len(superseded), 2)

    def test_merge_rejects_wrong_union(self):
        edges = (base_edge("b1", [1, 2]), base_edge("b2", [3, 4]))
        with self.assertRaises(ValueError):
            apply_ops(edges, [TopologyOp("MERGE", ("b1", "b2"), ((1, 2, 3),))], 1)

    def test_supersede_of_inactive_parent_fails_closed(self):
        edges = (base_edge("b1", [1, 2], invalid_at=1),)
        with self.assertRaises(ValueError):
            apply_ops(edges, [TopologyOp("SUPERSEDE", ("b1",), ())], 2)
        with self.assertRaises(ValueError):
            apply_ops(edges, [TopologyOp("SPLIT", ("missing",), ((1,), (2,)))], 2)

    def test_input_ledger_is_not_mutated(self):
        edges = (base_edge("b1", [1, 2, 3, 4]),)
        before = tuple(edges)
        apply_ops(edges, [TopologyOp("SPLIT", ("b1",), ((1, 2), (3, 4)))], 1)
        self.assertEqual(edges, before)
        self.assertIsNone(edges[0].invalid_at_round)

    def test_edge_ids_are_deterministic(self):
        self.assertEqual(
            edge_id_for("add", (1, 2, 3), 1), edge_id_for("add", (3, 2, 1), 1)
        )
        self.assertNotEqual(
            edge_id_for("add", (1, 2, 3), 1), edge_id_for("add", (1, 2, 3), 2)
        )

    def test_active_edges_excludes_superseded(self):
        edges = (
            base_edge("b1", [1, 2]),
            base_edge("b2", [3, 4], invalid_at=2),
        )
        self.assertEqual([edge.edge_id for edge in active_edges(edges)], ["b1"])


if __name__ == "__main__":
    unittest.main()
