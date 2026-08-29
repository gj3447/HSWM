"""Portable rendering contract for the repository's public math surfaces."""

from __future__ import annotations

from pathlib import Path

import pytest

from hswm.markdown_math_compiler import compile_portable_markdown_math


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_MATH_DOCS = (
    ROOT / "README.md",
    ROOT / "INDEX.md",
    *sorted((ROOT / "ontology").rglob("*.md")),
)

COMPILABLE_MATH_DOCS = (
    *PUBLIC_MATH_DOCS,
    *sorted((ROOT / "docs" / "canon").rglob("*.md")),
    *sorted((ROOT / "docs" / "research").rglob("*.md")),
)

# These are pre-existing, sometimes hash-bound source records.  The portable
# compiler removes their renderer-incompatible forms in derived output.  This
# non-increasing budget prevents new uses without rewriting historical bytes.
LEGACY_OPERATORNAME_BUDGET = {
    "docs/canon/HSWM_CONSTITUTION_2026-08-20.md": 3,
    "docs/canon/HSWM_LLM_FUNCTION_NETWORK_ARCHITECTURE_AND_FEASIBILITY_2026-07-23.md": 1,
    "docs/canon/SPEC_OPEN_SELF_SIMILAR_HSWM_2026-07-22.md": 5,
    "docs/canon/USER_PRIMARY_HSWM_FRACTAL_COGNITIVE_COMPOSITION_2026-08-28.md": 1,
    "docs/canon/USER_PRIMARY_HSWM_SCHEMA_RELATIVE_SINGLE_OWNER_2026-08-26.md": 2,
    "docs/canon/USER_PRIMARY_HSWM_TOKEN_HYPERGRAPH_CORE_2026-08-20.md": 6,
    "docs/canon/USER_PRIMARY_HUMAN_UNIVERSAL_BODY_DISTINCTION_2026-08-20.md": 1,
    "docs/research/HSWM_OCCAM_CORE_2026-08-20.md": 5,
    "docs/research/HSWM_SCHEMA_RELATIVE_SINGLE_OWNER_SCIENTIFIC_PHILOSOPHY_2026-08-26.md": 2,
    "docs/research/HSWM_SWM0W_S2S_GATE_2026-08-20.md": 1,
    "docs/research/HSWM_UNIFIED_MEANING_MAP_2026-08-16.md": 1,
    "docs/research/PROM_12_HSWM_CAUSAL_LOAD_BEARING_RESOLUTION_2026-07-26.md": 1,
    "docs/research/PROM_16_HSWM_HOLISTIC_SCIENTIFIC_ARCHITECTURE_2026-07-26.md": 1,
    "docs/research/PROM_17_HSWM_WHY_GLUE_CODE_NEURAL_TOPOLOGY_LLM_ACTIVATION_2026-07-30.md": 2,
    "docs/research/PROM_HSWM_PLASTICITY_WEIGHT_TOPOLOGY_LEARNING_2026-07-23.md": 4,
}


@pytest.mark.parametrize("path", PUBLIC_MATH_DOCS, ids=lambda path: str(path.relative_to(ROOT)))
def test_public_math_uses_portable_github_fences(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    # Some downstream Markdown renderers reject the AMS convenience macro even
    # though GitHub's MathJax surface accepts it.  Canonical entry documents use
    # base macros and GitHub's documented fenced-math form; sealed historical
    # research records are intentionally outside this mutable public surface.
    assert r"\operatorname" not in text
    assert not any(line.strip() in {r"\[", r"\]"} for line in text.splitlines())


@pytest.mark.parametrize("path", COMPILABLE_MATH_DOCS, ids=lambda path: str(path.relative_to(ROOT)))
def test_math_documents_compile_to_portable_renderer_subset(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    compiled = compile_portable_markdown_math(source)

    assert r"\operatorname" not in compiled.text
    assert not any(
        line.strip() in {r"\[", r"\]"} for line in compiled.text.splitlines()
    )


@pytest.mark.parametrize("path", COMPILABLE_MATH_DOCS, ids=lambda path: str(path.relative_to(ROOT)))
def test_no_new_forbidden_operator_macros(path: Path) -> None:
    relative = str(path.relative_to(ROOT))
    observed = path.read_text(encoding="utf-8").count(r"\operatorname")

    assert observed <= LEGACY_OPERATORNAME_BUDGET.get(relative, 0)
