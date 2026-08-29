"""Compile repository Markdown math into the portable renderer subset.

The source documents include hash-bound historical and canonical records, so
renderer compatibility must not require rewriting their bytes.  This module
builds a derived Markdown projection instead.  It intentionally performs only
semantics-preserving compatibility rewrites that the repository has admitted.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


class MarkdownMathCompilationError(ValueError):
    """Raised when a source cannot be compiled without guessing its meaning."""


@dataclass(frozen=True)
class MarkdownMathCompilation:
    """Portable Markdown plus an auditable rewrite summary."""

    text: str
    operatorname_rewrites: int
    legacy_compatibility_rewrites: int
    display_fence_rewrites: int
    math_fences_seen: int


_OPERATORNAME = re.compile(
    r"\\operatorname(?:\*)?\s*\{(?P<name>[A-Za-z][A-Za-z0-9]*)\}"
)
_FENCE_OPEN = re.compile(r"^(?P<indent>[ \t]*)(?P<marker>`{3,}|~{3,})(?P<info>.*)$")
_LEGACY_LITERAL_REWRITES = (
    (r"\centernot\Rightarrow", r"\not\Rightarrow"),
    (r"\mathcal K={S:", r"\mathcal K=\{S:"),
    (
        "p_j = 2^(-m_j) sum_{k=w_j}^{m_j} choose(m_j,k),",
        r"p_j = 2^{-m_j} \sum_{k=w_j}^{m_j} \binom{m_j}{k},",
    ),
    (
        "p_j_adjusted = min(1, 3 p_j).",
        r"p_{j,\mathrm{adjusted}} = \min(1, 3p_j).",
    ),
)


def _line_ending(line: str) -> str:
    if line.endswith("\r\n"):
        return "\r\n"
    if line.endswith("\n"):
        return "\n"
    return ""


def _is_fence_close(line: str, marker: str) -> bool:
    stripped = line.strip()
    return (
        len(stripped) >= len(marker)
        and set(stripped) == {marker[0]}
        and stripped[0] == marker[0]
    )


def _rewrite_math_segment(
    segment: str, *, line_number: int
) -> tuple[str, int, int]:
    rewritten, count = _OPERATORNAME.subn(
        lambda match: rf"\mathrm{{{match.group('name')}}}", segment
    )
    compatibility_rewrites = 0
    for source, replacement in _LEGACY_LITERAL_REWRITES:
        occurrences = rewritten.count(source)
        if occurrences:
            rewritten = rewritten.replace(source, replacement)
            compatibility_rewrites += occurrences
    if r"\operatorname" in rewritten:
        raise MarkdownMathCompilationError(
            f"line {line_number}: unsupported or malformed \\operatorname expression"
        )
    return rewritten, count, compatibility_rewrites


def _rewrite_outside_inline_code(
    line: str, *, line_number: int
) -> tuple[str, int, int]:
    """Rewrite renderer-visible text while preserving Markdown code spans."""

    parts = re.split(r"(`+)", line)
    active_ticks: int | None = None
    rewrites = 0
    compatibility_rewrites = 0
    for index, part in enumerate(parts):
        if part and set(part) == {"`"}:
            run_length = len(part)
            if active_ticks is None:
                active_ticks = run_length
            elif active_ticks == run_length:
                active_ticks = None
            continue
        if active_ticks is None:
            parts[index], count, compatibility_count = _rewrite_math_segment(
                part, line_number=line_number
            )
            rewrites += count
            compatibility_rewrites += compatibility_count
    return "".join(parts), rewrites, compatibility_rewrites


def compile_portable_markdown_math(text: str) -> MarkdownMathCompilation:
    """Return a renderer-safe Markdown projection without mutating the source.

    Admitted rewrites:

    * ``\\operatorname{Name}`` becomes the base-macro form ``\\mathrm{Name}``.
    * line-delimited ``\\[`` / ``\\]`` display math becomes a ``math`` fence.

    Ordinary fenced code and inline code spans are byte-preserved.  Ambiguous or
    malformed operator expressions fail closed instead of being guessed.
    """

    output: list[str] = []
    fence_marker: str | None = None
    fence_is_math = False
    legacy_display_open = False
    operatorname_rewrites = 0
    legacy_compatibility_rewrites = 0
    display_fence_rewrites = 0
    math_fences_seen = 0

    for line_number, line in enumerate(text.splitlines(keepends=True), start=1):
        if fence_marker is not None:
            if _is_fence_close(line, fence_marker):
                output.append(line)
                fence_marker = None
                fence_is_math = False
            elif fence_is_math:
                rewritten, count, compatibility_count = _rewrite_math_segment(
                    line, line_number=line_number
                )
                output.append(rewritten)
                operatorname_rewrites += count
                legacy_compatibility_rewrites += compatibility_count
            else:
                output.append(line)
            continue

        fence = _FENCE_OPEN.match(line.rstrip("\r\n"))
        if fence:
            fence_marker = fence.group("marker")
            info = fence.group("info").strip().split(maxsplit=1)
            fence_is_math = bool(info and info[0].lower() in {"math", "latex", "tex"})
            if fence_is_math:
                math_fences_seen += 1
            output.append(line)
            continue

        stripped = line.strip()
        if stripped == r"\[":
            if legacy_display_open:
                raise MarkdownMathCompilationError(
                    f"line {line_number}: nested \\[ display delimiter"
                )
            indentation = line[: len(line) - len(line.lstrip(" \t"))]
            output.append(f"{indentation}```math{_line_ending(line)}")
            legacy_display_open = True
            display_fence_rewrites += 1
            math_fences_seen += 1
            continue
        if stripped == r"\]":
            if not legacy_display_open:
                raise MarkdownMathCompilationError(
                    f"line {line_number}: unmatched \\] display delimiter"
                )
            indentation = line[: len(line) - len(line.lstrip(" \t"))]
            output.append(f"{indentation}```{_line_ending(line)}")
            legacy_display_open = False
            continue

        if legacy_display_open:
            rewritten, count, compatibility_count = _rewrite_math_segment(
                line, line_number=line_number
            )
        else:
            rewritten, count, compatibility_count = _rewrite_outside_inline_code(
                line, line_number=line_number
            )
        output.append(rewritten)
        operatorname_rewrites += count
        legacy_compatibility_rewrites += compatibility_count

    if legacy_display_open:
        raise MarkdownMathCompilationError("unclosed \\[ display delimiter")
    if fence_marker is not None and fence_is_math:
        raise MarkdownMathCompilationError("unclosed fenced math block")

    return MarkdownMathCompilation(
        text="".join(output),
        operatorname_rewrites=operatorname_rewrites,
        legacy_compatibility_rewrites=legacy_compatibility_rewrites,
        display_fence_rewrites=display_fence_rewrites,
        math_fences_seen=math_fences_seen,
    )
