"""Separate-process LE-0 adapter for the frozen DGX Q1 independent verifier.

The Q1 runner is intentionally left byte-stable.  This unfrozen bridge invokes
only its independent reader after the action process has completed, prints the
canonical protocol verdict for LE-0 content-addressing, and maps a malformed
or VOID verdict to a nonzero operational exit status.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Callable

from _research.dgx_q1.independent_live_verifier import TERMINALS, VOID, verify
from _research.dnrd5.canonical_json import canonical_bytes


def run_verifier(
    root: Path,
    external_registry_root: Path,
    *,
    verify_fn: Callable[..., dict[str, Any]] = verify,
) -> tuple[dict[str, Any], int]:
    """Return the original bounded protocol verdict and LE-0 exit disposition."""

    result = verify_fn(root, external_registry_root=external_registry_root)
    if (
        not isinstance(result, dict)
        or not isinstance(result.get("terminal"), str)
        or result["terminal"] not in TERMINALS
    ):
        return {"terminal": VOID}, 2
    return result, 2 if result["terminal"] == VOID else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--external-registry-root", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result, exit_code = run_verifier(args.root, args.external_registry_root)
        print(canonical_bytes(result).decode("utf-8"))
        return exit_code
    except Exception:
        print(canonical_bytes({"terminal": VOID}).decode("utf-8"))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
