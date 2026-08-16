"""Canonical source-only F-series research harness package.

The modules in this package are live research code. Historical root-path
replay is handled separately by the source-pinned W3 materializer; callers of
current code must import ``_research.f_series.<module>``.
"""

from __future__ import annotations

from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]

MODULES = (
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
)


def source_path(filename: str) -> Path:
    """Return the current canonical source for a root-era module basename."""

    relative = Path(filename)
    if relative.name != filename or relative.suffix != ".py":
        raise ValueError(f"expected a Python module basename, got {filename!r}")
    packaged = SOURCE_ROOT / relative
    return packaged if packaged.is_file() else REPO_ROOT / relative


__all__ = ["MODULES", "REPO_ROOT", "SOURCE_ROOT", "source_path"]
