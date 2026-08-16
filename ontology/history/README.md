# Path-bound history

Many early experiments bind a root-relative path and exact source SHA into a
manifest or receipt. Moving those files would preserve their bytes but break
the historical path identity and, in several harnesses, change `__file__`-based
runtime behavior.

They remain a frozen compatibility surface until their complete dependency
cluster is migrated. The `hswm-legacy-replay` command now restores an exact old
root layout as a clean detached standalone clone, verifies the manifest-bound
commit and SHA-256 values, and never mutates the active checkout. New source,
research documents, and artifacts must use their canonical directories instead
of the legacy root.

[`LEGACY_ROOT_PATHS.v1.json`](LEGACY_ROOT_PATHS.v1.json) freezes the current
exception set. [`root-tidy-move-map.v1.json`](root-tidy-move-map.v1.json)
preserves the earlier migration record.

The `PYTHON_ROOT_MIGRATIONS*.json` manifests record each Python source removed
from the legacy root, its canonical ontology path, the source commit, and the
digest of the preserved pre-migration bytes. Separate manifests let each wave
pin the exact commit from which its old paths were removed. They are also the
single path registry consumed by `hswm-legacy-replay`; no second alias map can
silently drift from the migration evidence.

```bash
uv run hswm-legacy-replay list
uv run hswm-legacy-replay verify OLD_ROOT_FILE.py
uv run hswm-legacy-replay materialize OLD_ROOT_FILE.py /tmp/hswm-replay
```

The resulting checkout includes Git metadata because several historical
harnesses query commit ancestry while running. Its `.git/hswm-legacy-replay.json`
receipt binds the selected source commit, tree, old paths, and source hashes.

[`PYTHON_ROOT_CLASSIFICATION.v1.json`](PYTHON_ROOT_CLASSIFICATION.v1.json)
partitions every remaining root Python file into `SHA_LOCKED`,
`REPLAY_HISTORY_LOCKED`, or `REVIEW_REQUIRED`. The partition is exhaustive and
disjoint; the validator rejects a new or unexplained root module. After W3 the
review class is empty: every remaining module has an explicit evidence or replay
reason.

`quarantine/` contains non-executable historical mutation payloads whose old
instructions conflict with the active bounded ontology policy. They are source
material only, never runbooks.
