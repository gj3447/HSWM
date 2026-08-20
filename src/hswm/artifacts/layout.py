"""HSWM artifact layout convention (root-tidy follow-up).

New research artifacts MUST be written into per-kind subdirectories instead of
the repository root:

    EVIDENCE_*.json          -> evidence/
    *_DIAGNOSTIC_*.json      -> evidence/
    PREREG_*.json | *.md     -> prereg/
    *_MANIFEST*.json         -> manifests/
    registered configs/splits -> manifests/
    RECEIPTS_*.json          -> receipts/
    *_RESULTS_*.md           -> results/
    checked-in raw results   -> results/raw/
    narrative research docs  -> docs/research/

Backward compatibility: root-era artifacts keep validating after their exact
sources move to ``_research/root_compat``.  Readers should resolve names through
:func:`resolve_artifact_path`, which checks the per-kind subdirectory first,
then the canonical root-compat directory, and finally an old root location.
Path+sha256 ledger entries name explicit repository-relative paths and are
unaffected.

Escape hatch: set ``HSWM_ARTIFACT_ROOT`` to redirect the artifact output root
(useful for tests and scratch runs).  Paths then become
``$HSWM_ARTIFACT_ROOT/<subdir>/<name>``.  The subdir convention still applies.

Rule: never write new artifacts to the repository root.  See
docs/research/ARTIFACT_LAYOUT.md.
"""

from __future__ import annotations

import os
from pathlib import Path


_REPOSITORY_MARKERS = (
    "pyproject.toml",
    "ontology/HSWM_REPOSITORY_ONTOLOGY.v1.json",
)


def _discover_repository_root(anchor: str | Path = __file__) -> Path | None:
    """Return the enclosing source checkout, or ``None`` in an installed wheel."""

    resolved = Path(anchor).resolve(strict=True)
    start = resolved.parent if resolved.is_file() else resolved
    for candidate in (start, *start.parents):
        if all((candidate / marker).is_file() for marker in _REPOSITORY_MARKERS):
            return candidate
    return None


REPO_ROOT: Path | None = _discover_repository_root()

ARTIFACT_DIRS = {
    "evidence": "evidence",
    "prereg": "prereg",
    "manifest": "manifests",
    "receipt": "receipts",
    "results": "results",
    "raw_result": "results/raw",
    "research_doc": "docs/research",
}

RAW_RESULT_NAMES = frozenset({
    "ab_p5_full_2wiki_s7.json",
    "ab_p5_full_musique_s13.json",
    "ab_p5_full_musique_s7.json",
    "ab_p5_full_results.json",
    "ab_p5_pilot_results.json",
    "cert_2wiki_result.json",
    "cert_musique_result.json",
    "certified_cut_comparison_result.json",
    "h3_title_anchor_result.json",
    "qkv_b1_development_result.json",
    "qkv_routing_result.json",
    "semantic_2wiki_oracle_result.json",
    "semantic_layer_result.json",
    "swm0w_scalar_gate_candidate_2026-08-20.json",
    "stale_poisoning_2wiki_result.json",
    "stale_poisoning_musique_result.json",
    "substrate_bench_results.json",
    "traversal_bench_results.json",
})

# These names predate the typed-directory convention and cannot be classified
# safely from a broad suffix alone.  Keep the exception sets exact, as with the
# checked-in raw-result allowlist above.
EVIDENCE_NAMES = frozenset({
    "P1_GATE_DIAGNOSTIC_R2_2026-07-23.json",
    "P1_RANK_INVARIANCE_DIAGNOSTIC_R2_2026-07-23.json",
})

MANIFEST_NAMES = frozenset({
    "P1_SPLIT_2026-07-23.json",
    "hswm_core_existence_harness.v1.json",
    "hswm_giant_llm_harness.v1.json",
})

ENV_ARTIFACT_ROOT = "HSWM_ARTIFACT_ROOT"
ROOT_COMPAT_DIR = "_research/root_compat"


def classify_artifact(name: str) -> str | None:
    """Return the artifact kind for a bare filename, or None if unclassified."""
    bare = name.rsplit("/", 1)[-1]
    if bare.startswith("EVIDENCE_") and bare.endswith(".json"):
        return "evidence"
    if bare in EVIDENCE_NAMES:
        return "evidence"
    if bare.startswith("PREREG_") and bare.endswith((".json", ".md")):
        return "prereg"
    if "_MANIFEST" in bare and bare.endswith(".json"):
        return "manifest"
    if bare in MANIFEST_NAMES:
        return "manifest"
    if bare.startswith("RECEIPTS_") and bare.endswith(".json"):
        return "receipt"
    if "_RESULTS_" in bare and bare.endswith(".md"):
        return "results"
    if bare in RAW_RESULT_NAMES:
        return "raw_result"
    return None


def artifact_root() -> Path:
    """Artifact output root: HSWM_ARTIFACT_ROOT override, else the repo root."""
    override = os.environ.get(ENV_ARTIFACT_ROOT)
    if override:
        return Path(override).expanduser()
    if REPO_ROOT is None:
        raise RuntimeError(
            "artifact operations require HSWM_ARTIFACT_ROOT when the package "
            "is installed outside an HSWM source checkout"
        )
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
    """Resolve a bare filename across typed, root-compat, and old-root paths.

    With ``must_exist=False``, return the preferred candidate even when nothing
    exists yet, so callers keep their own error handling.
    """
    base = Path(root) if root is not None else artifact_root()
    kind = kind or classify_artifact(name)
    candidates = []
    if kind is not None:
        candidates.append(base / ARTIFACT_DIRS[kind] / name)
    if Path(name).name == name:
        candidates.append(base / ROOT_COMPAT_DIR / name)
    candidates.append(base / name)  # root-era checkout or detached replay
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
    """Yield existing typed, root-compat, and old-root paths, de-duplicated."""
    seen = set()
    base = Path(root) if root is not None else artifact_root()
    kind = kind or classify_artifact(name)
    candidates = []
    if kind is not None:
        candidates.append(base / ARTIFACT_DIRS[kind] / name)
    if Path(name).name == name:
        candidates.append(base / ROOT_COMPAT_DIR / name)
    candidates.append(base / name)
    for candidate in candidates:
        key = candidate.resolve()
        if key in seen or not candidate.is_file():
            continue
        seen.add(key)
        yield candidate
