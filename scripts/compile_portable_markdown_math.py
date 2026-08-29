#!/usr/bin/env python3
"""Compile Markdown files to HSWM's portable math-rendering subset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from hswm.markdown_math_compiler import (
    MarkdownMathCompilationError,
    compile_portable_markdown_math,
)


def _markdown_paths(inputs: list[Path]) -> list[Path]:
    paths: set[Path] = set()
    for input_path in inputs:
        path = input_path.resolve()
        if path.is_dir():
            paths.update(candidate for candidate in path.rglob("*.md") if candidate.is_file())
        elif path.is_file():
            paths.add(path)
        else:
            raise FileNotFoundError(input_path)
    return sorted(paths)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compile forbidden Markdown math constructs to the portable renderer "
            "subset without changing source files."
        )
    )
    parser.add_argument("inputs", nargs="+", type=Path)
    output = parser.add_mutually_exclusive_group()
    output.add_argument(
        "--output",
        type=Path,
        help="write one compiled input to this path",
    )
    output.add_argument(
        "--output-dir",
        type=Path,
        help="write compiled files below this directory, relative to the current directory",
    )
    args = parser.parse_args()

    try:
        paths = _markdown_paths(args.inputs)
        if args.output is not None and len(paths) != 1:
            parser.error("--output requires exactly one Markdown input")

        totals = {
            "documents": len(paths),
            "operatorname_rewrites": 0,
            "legacy_compatibility_rewrites": 0,
            "display_fence_rewrites": 0,
            "math_fences_seen": 0,
        }
        compiled: list[tuple[Path, str]] = []
        for path in paths:
            result = compile_portable_markdown_math(path.read_text(encoding="utf-8"))
            compiled.append((path, result.text))
            totals["operatorname_rewrites"] += result.operatorname_rewrites
            totals["legacy_compatibility_rewrites"] += (
                result.legacy_compatibility_rewrites
            )
            totals["display_fence_rewrites"] += result.display_fence_rewrites
            totals["math_fences_seen"] += result.math_fences_seen

        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(compiled[0][1], encoding="utf-8")
        elif args.output_dir is not None:
            root = Path.cwd().resolve()
            for source, text in compiled:
                try:
                    relative = source.relative_to(root)
                except ValueError as error:
                    raise ValueError(
                        f"--output-dir input is outside the current directory: {source}"
                    ) from error
                destination = args.output_dir / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(text, encoding="utf-8")

        print(json.dumps({**totals, "status": "PORTABLE_MATH_COMPILED"}, sort_keys=True))
        return 0
    except (FileNotFoundError, MarkdownMathCompilationError, ValueError) as error:
        print(f"markdown math compilation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
