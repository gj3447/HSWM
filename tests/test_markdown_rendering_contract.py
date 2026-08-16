"""Portable rendering contract for the repository's public math surfaces."""

from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_MATH_DOCS = (
    ROOT / "README.md",
    ROOT / "INDEX.md",
    *sorted((ROOT / "ontology").rglob("*.md")),
)


@pytest.mark.parametrize("path", PUBLIC_MATH_DOCS, ids=lambda path: str(path.relative_to(ROOT)))
def test_public_math_uses_portable_github_fences(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    # Some downstream Markdown renderers reject the AMS convenience macro even
    # though GitHub's MathJax surface accepts it.  Canonical entry documents use
    # base macros and GitHub's documented fenced-math form; sealed historical
    # research records are intentionally outside this mutable public surface.
    assert r"\operatorname" not in text
    assert not any(line.strip() in {r"\[", r"\]"} for line in text.splitlines())
