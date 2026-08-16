# Path-bound history

Early experiments sometimes bind a repository-root path, exact source digest,
or `__file__`-relative behavior into a manifest or receipt. Those bindings are
historical evidence, not the layout for new work.

## Current compatibility surface

[`ROOT_COMPATIBILITY_BASELINE.v1.json`](ROOT_COMPATIBILITY_BASELINE.v1.json) is
the single frozen source of truth for root paths that had a concrete
compatibility or evidence reason at its source commit. New implementation,
documents, and artifacts use their typed directories instead of joining this
baseline. Listed root files remain byte-frozen; relocate one with a source-pinned
manifest before changing its canonical copy.

## Archived migrations and replay

The existing `PYTHON_ROOT_MIGRATIONS*.json` and
`ROOT_ASSET_MIGRATIONS*.json` files preserve old path, source-commit, and digest
bindings for relocations that already promised exact detached replay.
[`root-tidy-move-map.v1.json`](root-tidy-move-map.v1.json) preserves the earlier
move record. These files are retained as read-only history.

An ordinary file absent from the baseline's `paths` array moves through standard
Git history and normal compatibility tests. Moving a listed compatibility path
requires one source-pinned manifest in the existing replay registry so the old
path, source commit, digest, and canonical destination remain reproducible.

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

`quarantine/` contains non-executable historical mutation payloads whose old
instructions conflict with the active bounded ontology policy. They are source
material only, never runbooks.
