"""NEGATIVE ORACLE (intentionally regressed) — ooptdd ouroboros red-run probe.

This module exists ONLY to prove the metric-v2 gate suite is non-vacuous.
It monkey-patches the v2 machinery back to v1-style coverage-only scoring
(correct = 1; wrong AND abstain = 0; no fabrication cost, no c-sweep
sensitivity), then delegates to the REAL ``run_metric_v2_probe``.

Discipline demonstrated by ooptdd/metric_v2_regressed_requirements.yaml:
under this regression the scoring-sensitive gates MUST go RED —
REQ-V2-TYPED-BEATS-ALL-CONTROLS-T2 (shuffle contrast collapses to exactly 0),
REQ-V2-ROBUST-ACROSS-C (min contrast 0 is not > 0), REQ-V2-GOLDEN-REPLAY
(coverage typed utility 0.407 != golden 0.296) and REQ-V2-OUROBOROS-SELF-MEASURE
(v2 can no longer out-rank v1 — the snake cannot tell its tail from its head).
Scoring-insensitive gates (abstain-only-zero, fabrication-refusal,
alpha regression direction) stay green, proving the REDs come from the
scoring regression and not from a broken harness.

Never point the canonical spec (metric_v2_requirements.yaml) at this module.
"""
from __future__ import annotations

from fractions import Fraction

from prom_search_hswm import prom9_f1_metric_v2 as m2


def _coverage_per_arm_utility(evidence: m2.DevelopmentEvidence, c: int = 2):
    n = len(evidence.item_ids)
    return {
        arm: sum(
            (
                Fraction(1) if evidence.outcomes[(item_id, arm)] == "correct" else Fraction(0)
                for item_id in evidence.item_ids
            ),
            Fraction(0),
        )
        / n
        for arm in m2.ALL_ARMS
    }


def _coverage_paired_contrasts(evidence: m2.DevelopmentEvidence, c: int = 2):
    return m2.coverage_v1_contrasts(evidence)


def _coverage_min_contrast(evidence: m2.DevelopmentEvidence, c: int = 2):
    return min(m2.coverage_v1_contrasts(evidence).values())


# Regress the machinery BEFORE the adapter binds to it.  The adapter calls
# through the module object (m2.<fn>), and m2.c_sweep resolves these names
# from module globals at call time, so every scoring path is covered.
m2.per_arm_utility = _coverage_per_arm_utility
m2.paired_contrasts = _coverage_paired_contrasts
m2.min_contrast = _coverage_min_contrast

from metric_v2_conformance_adapter import run_metric_v2_probe as _real_probe  # noqa: E402


def run_metric_v2_probe(backend, cid: str) -> dict:
    return _real_probe(backend, cid)
