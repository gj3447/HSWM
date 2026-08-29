from __future__ import annotations

import pytest

from hswm.markdown_math_compiler import (
    MarkdownMathCompilationError,
    compile_portable_markdown_math,
)


def test_compiles_forbidden_operator_and_legacy_display_fence() -> None:
    source = """Before $\\operatorname{Readout}(x)$.

\\[
z=\\operatorname*{argmax}_{i} x_i
\\]
"""

    result = compile_portable_markdown_math(source)

    assert result.text == """Before $\\mathrm{Readout}(x)$.

```math
z=\\mathrm{argmax}_{i} x_i
```
"""
    assert result.operatorname_rewrites == 2
    assert result.legacy_compatibility_rewrites == 0
    assert result.display_fence_rewrites == 1
    assert result.math_fences_seen == 1


def test_preserves_non_math_fenced_code_and_inline_code() -> None:
    source = """`\\operatorname{literal}`

```python
value = r"\\operatorname{literal}"
```

```math
x=\\operatorname{clip}(y)
```
"""

    result = compile_portable_markdown_math(source)

    assert result.text.count(r"\operatorname{literal}") == 2
    assert r"\mathrm{clip}" in result.text
    assert result.operatorname_rewrites == 1


def test_compiles_admitted_hash_bound_legacy_math_without_source_mutation() -> None:
    source = r"""\mathsf{Owner}_{\sigma}(a,p)
\centernot\Rightarrow
\mathsf{Permit}_{\sigma}(S,e).

\mathcal K={S:|A|\le B_A\}

p_j = 2^(-m_j) sum_{k=w_j}^{m_j} choose(m_j,k),
p_j_adjusted = min(1, 3 p_j).
"""

    result = compile_portable_markdown_math(source)

    assert r"\not\Rightarrow" in result.text
    assert r"\mathcal K=\{S:" in result.text
    assert r"2^{-m_j} \sum_{k=w_j}^{m_j} \binom{m_j}{k}" in result.text
    assert r"p_{j,\mathrm{adjusted}} = \min(1, 3p_j)" in result.text
    assert result.legacy_compatibility_rewrites == 4


@pytest.mark.parametrize(
    "source, message",
    [
        (r"$\operatorname{not closed$", "malformed"),
        ("\\[\nx=1\n", "unclosed"),
        ("\\]\n", "unmatched"),
        ("```math\nx=1\n", "unclosed"),
    ],
)
def test_fails_closed_on_ambiguous_math(source: str, message: str) -> None:
    with pytest.raises(MarkdownMathCompilationError, match=message):
        compile_portable_markdown_math(source)
