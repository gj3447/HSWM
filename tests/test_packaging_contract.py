from __future__ import annotations

from pathlib import Path
import tomllib


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_h3_runtime_and_entry_modules_are_shipped_in_the_wheel() -> None:
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    shipped = set(project["tool"]["setuptools"]["py-modules"])

    assert {
        "h3_artifact_lifecycle",
        "h3_b3_falsifier",
        "h3_b3_manifest",
        "h3_b3_preflight",
        "h3_title_anchor_falsifier",
    } <= shipped
