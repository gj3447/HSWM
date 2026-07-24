"""ooptdd v2.5 — mutation allowlist (R3): machine-recorded equivalent mutants.

A survivor is either an OPEN GAP (the test suite should catch it and doesn't)
or a documented EQUIVALENT (mutation does not change observable behavior).
Hand-waving equivalents in commit messages does not scale; this module makes
them data:

  receipts/mutation_allowlist.json
  {"traversal.py": [{"kind": "binop", "detail": "Sub->Add", "lineno": 89,
                     "col": 16, "reason": "softmax constant-shift invariance"}]}

Fail-closed rules:
  - an entry without a non-empty reason is refused (undocumented equivalence
    is indistinguishable from a gap being hidden),
  - entries are matched by kind+detail (+lineno/col when given), so line
    drift only loosens matching when the author chose to omit them.
"""
from __future__ import annotations

import json
import os

DEFAULT_ALLOWLIST = os.path.join("receipts", "mutation_allowlist.json")


def load_allowlist(path: str = DEFAULT_ALLOWLIST) -> dict[str, list[dict]]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for module, entries in data.items():
        if not isinstance(entries, list):
            raise ValueError(f"{path}: entries for {module} must be a list")
        for e in entries:
            if not e.get("reason", "").strip():
                raise ValueError(f"{path}: entry {e} in {module} has no reason — refused")
            if not e.get("kind") or not e.get("detail"):
                raise ValueError(f"{path}: entry {e} in {module} needs kind and detail")
    return data


def is_equivalent(site, module_entries: list[dict]) -> str | None:
    """Return the reason if the site matches a documented equivalent, else None."""
    for e in module_entries:
        if e["kind"] != site.kind or e["detail"] != site.detail:
            continue
        if "lineno" in e and e["lineno"] != site.lineno:
            continue
        if "col" in e and e["col"] != site.col:
            continue
        return e["reason"]
    return None
