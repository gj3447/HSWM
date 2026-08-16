# Root compatibility sources

`_research/root_compat/` contains the final source-pinned snapshot of files that
once lived at the repository root.  Keeping the set together preserves flat
Python imports and same-directory references without exposing those historical
files as the repository's public root surface.

The files in this directory are compatibility sources, not the location for
new implementation, research, documents, or generated artifacts.  New work
belongs in the typed directories described by `AGENTS.md`.  Historical commands
that require the original root layout must use `hswm-legacy-replay`, which
materializes the source commit recorded by the final Python and asset migration
manifests outside the active checkout.

Do not copy these files back to the active root or edit hash-bound records just
to modernize an old path.  The installed flat-module surface is sourced from
this directory through the setuptools `package-dir` mapping.

## Frozen H3 execution support

The nested `pyproject.toml` and three files under `tests/` are exact copies from
the source commit used by the active checkout migration.  They let the
byte-frozen H3 preflight keep treating the directory containing its historical
modules as a self-contained execution root.  They are support snapshot inputs,
not migration rows, editable tests, or alternate current project configuration.

Do not update these four copies when their current root counterparts change.
Any newer H3 protocol must use new canonical code and a new evidence contract;
the frozen support snapshot exists only to preserve the already-bound execution.
