# Path-bound history

Early experiments sometimes bind a repository-root path, exact source digest,
or `__file__`-relative behavior into a manifest or receipt. Those bindings are
historical evidence, not the layout for new work.

## Current compatibility surface

[`ROOT_COMPATIBILITY_BASELINE.v1.json`](ROOT_COMPATIBILITY_BASELINE.v1.json) is
the single frozen source of truth for root paths that had a concrete
compatibility or evidence reason at its source commit. New implementation,
documents, and artifacts use their typed directories instead of extending this
baseline. All 93 files that remained in its final active set moved together to
[`_research/root_compat/`](../../_research/root_compat/). The active repository
root therefore has no compatibility files. The cluster preserves flat imports,
`__file__`-relative behavior, and sibling document references, but is closed to
new work.

## Archived migrations and replay

The `PYTHON_ROOT_MIGRATIONS*.json` and `ROOT_ASSET_MIGRATIONS*.json` files
preserve old path, source-commit, digest, and canonical-destination bindings for
relocations that promise exact detached replay. The final
[`Python`](PYTHON_ROOT_MIGRATIONS.FINAL.v2.json) and
[`asset`](ROOT_ASSET_MIGRATIONS.FINAL.v1.json) manifests enumerate the complete
93-file move into the compatibility cluster.
[`root-tidy-move-map.v1.json`](root-tidy-move-map.v1.json) preserves the earlier
move record. These files are retained as read-only history.

An ordinary file absent from the baseline's `paths` array moves through standard
Git history and normal compatibility tests. The migration registry is additive:
old path, source commit, digest, and canonical destination remain reproducible
even after the active layout changes.

Use the retained registry without restoring old paths into the active checkout:

```bash
uv run hswm-legacy-replay list
uv run hswm-legacy-replay verify OLD_ROOT_FILE
uv run hswm-legacy-replay materialize OLD_ROOT_FILE /tmp/hswm-replay
```

The materialized checkout is a clean detached clone with Git metadata for
historical harnesses that inspect commit ancestry. Its replay receipt records
the selected commit, tree, paths, and source hashes.

## Boundary

Do not edit hash-bound payload evidence merely to refresh a path or narrative.
Current readers and writers should use canonical typed locations; historical
programs that require the old layout run only in detached replay.

The three `formal/verify_hswm_*_longinus.py` programs, their Longinus binding
manifests, and associated receipts are such historical records. They retain
their published root-era paths and SHA bindings and are not validators for the
current checkout layout. Do not rewrite them to make an active-tree invocation
pass; reproduce their recorded source context through detached replay.

`quarantine/` contains non-executable historical mutation payloads whose old
instructions conflict with the active bounded ontology policy. They are source
material only, never runbooks.
