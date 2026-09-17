"""Effect-runtime functional-boundary projection: determinism, shape, and lint-report freshness.

The bundle is engineering status only.  These tests prove the checked-in
projection is the deterministic build of its bound sources, that its graph
shape obeys the shared invariants, and that the current tree still satisfies the
boundary invariants (zero violations outside the lanes, a shrinking-only
allowlist) without pinning live files to the snapshot's exact counts (SR-5).
They do not prove HSWM cognition, learning, a migration-gate pass, or any
scientific claim.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from scripts import build_hswm_effect_fp_boundary_ontology as builder
from scripts import upsert_hswm_effect_fp_boundary as publisher


ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / builder.ONTOLOGY_PATH
RUNTIME = ROOT / "src/hswm/effect-runtime"


def _load() -> dict:
    return json.loads(ONTOLOGY.read_text(encoding="utf-8"))


def test_projection_is_the_deterministic_build_and_validates() -> None:
    data = builder.build_data()
    builder.validate_data(data)
    assert builder.encoded_data(data) == ONTOLOGY.read_bytes()
    assert data == _load()
    publisher.validate_data(data)


def test_bindings_match_the_checked_in_sources() -> None:
    data = _load()
    paths = [row["path"] for row in data["artifact_bindings"]]
    assert paths == [path.as_posix() for path in builder.SOURCE_BINDING_PATHS]
    for row in data["artifact_bindings"]:
        assert row["sha256"] == sha256((ROOT / row["path"]).read_bytes()).hexdigest()


def test_bound_lint_report_is_internally_consistent() -> None:
    """The checked-in report is the snapshot the bundle binds; it must be self-consistent."""

    report = builder.load_lint_report()
    assert report["violations"] == 0
    assert report["stale_allowlist_entries"] == 0
    assert set(report["allowlist"]) == set(report["lanes"] and {f for files in report["lanes"].values() for f in files})
    for name, entry in report["allowlist"].items():
        assert entry["lane"] in report["lanes"]
        for rule in entry["rules"]:
            assert report["per_file"][name][rule] > 0, (name, rule)


def test_current_tree_still_satisfies_the_boundary_invariants() -> None:
    """Invariants only (SR-5): the live tree is not pinned to the snapshot's exact counts.

    The lint must report zero violations outside the lanes and no stale allowlist
    entries; the allowlist may only shrink relative to the bound snapshot.
    """

    snapshot = builder.load_lint_report()
    allowlist = builder.load_allowlist()
    assert set(allowlist["files"]) <= set(snapshot["allowlist"]), "the allowlist may only shrink"
    for name, entry in allowlist["files"].items():
        assert entry["lane"] in allowlist["lanes"]
        assert set(entry["rules"]) <= set(snapshot["allowlist"][name]["rules"]), name
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not available; the lint runs in npm run check in the TypeScript CI lane")
    fresh = json.loads(
        subprocess.run(
            [node, "scripts/lint-effect-boundary.mjs", "--json"],
            cwd=RUNTIME,
            capture_output=True,
            text=True,
            check=False,
        ).stdout
    )
    assert fresh["violations"] == 0, "Effect boundary violated outside the exemption lanes"
    assert fresh["stale_allowlist_entries"] == 0, "allowlist carries a stale entry; drop it"
