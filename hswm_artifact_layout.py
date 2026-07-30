"""HSWM artifact layout convention (root-tidy follow-up).

New research artifacts MUST be written into per-kind subdirectories instead of
the repository root:

    EVIDENCE_*.json          -> evidence/
    PREREG_*.json | *.md     -> prereg/
    *_MANIFEST*.json         -> manifests/
    *_RESULTS_*.md           -> results/
    narrative research docs  -> docs/research/

Backward compatibility: legacy root artifacts keep validating.  Readers should
resolve names through :func:`resolve_artifact_path`, which checks the per-kind
subdirectory first and then falls back to the legacy root location, so old
root files and new subdir files both resolve.  Path+sha256 ledger entries name
explicit repository-relative paths and are unaffected.

Escape hatch: set ``HSWM_ARTIFACT_ROOT`` to redirect the artifact output root
(useful for tests and scratch runs).  Paths then become
``$HSWM_ARTIFACT_ROOT/<subdir>/<name>``.  The subdir convention still applies.

Rule: never write new artifacts to the repository root.  See
docs/research/ARTIFACT_LAYOUT.md.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

ARTIFACT_DIRS = {
    "evidence": "evidence",
    "prereg": "prereg",
    "manifest": "manifests",
    "results": "results",
    "research_doc": "docs/research",
}

ENV_ARTIFACT_ROOT = "HSWM_ARTIFACT_ROOT"


def classify_artifact(name: str) -> str | None:
    """Return the artifact kind for a bare filename, or None if unclassified."""
    bare = name.rsplit("/", 1)[-1]
    if bare.startswith("EVIDENCE_") and bare.endswith(".json"):
        return "evidence"
    if bare.startswith("PREREG_") and bare.endswith((".json", ".md")):
        return "prereg"
    if "_MANIFEST" in bare and bare.endswith(".json"):
        return "manifest"
    if "_RESULTS_" in bare and bare.endswith(".md"):
        return "results"
    return None


def artifact_root() -> Path:
    """Artifact output root: HSWM_ARTIFACT_ROOT override, else the repo root."""
    override = os.environ.get(ENV_ARTIFACT_ROOT)
    if override:
        return Path(override).expanduser()
    return REPO_ROOT


def artifact_dir(kind: str, *, create: bool = False) -> Path:
    """Directory for an artifact kind (optionally created)."""
    if kind not in ARTIFACT_DIRS:
        raise ValueError(f"unknown artifact kind: {kind!r}")
    directory = artifact_root() / ARTIFACT_DIRS[kind]
    if create:
        directory.mkdir(parents=True, exist_ok=True)
    return directory


def default_artifact_path(name: str, kind: str | None = None, *, create: bool = True) -> Path:
    """Default write path for a new artifact (per-kind subdirectory).

    Writers should call this instead of hardcoding root-relative paths.
    """
    kind = kind or classify_artifact(name)
    if kind is None:
        raise ValueError(
            f"cannot classify artifact {name!r}; pass kind= explicitly "
            f"(one of {sorted(ARTIFACT_DIRS)})"
        )
    return artifact_dir(kind, create=create) / name


def resolve_artifact_path(
    name: str,
    kind: str | None = None,
    *,
    root: str | Path | None = None,
    must_exist: bool = True,
) -> Path:
    """Resolve an artifact by bare filename: per-kind subdir first, legacy root
    second.  With must_exist=False, return the preferred (subdir) candidate even
    when nothing exists yet, so callers keep their own error handling."""
    base = Path(root) if root is not None else artifact_root()
    kind = kind or classify_artifact(name)
    candidates = []
    if kind is not None:
        candidates.append(base / ARTIFACT_DIRS[kind] / name)
    candidates.append(base / name)  # legacy root location
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    if must_exist:
        raise FileNotFoundError(
            f"artifact {name!r} not found in: "
            + ", ".join(str(c) for c in candidates)
        )
    return candidates[0]


def iter_artifact_paths(name: str, kind: str | None = None, *, root: str | Path | None = None):
    """Yield every existing location for an artifact name (subdir, then root),
    de-duplicated.  For readers that must see both legacy and new files."""
    seen = set()
    base = Path(root) if root is not None else artifact_root()
    kind = kind or classify_artifact(name)
    candidates = []
    if kind is not None:
        candidates.append(base / ARTIFACT_DIRS[kind] / name)
    candidates.append(base / name)
    for candidate in candidates:
        key = candidate.resolve()
        if key in seen or not candidate.is_file():
            continue
        seen.add(key)
        yield candidate
