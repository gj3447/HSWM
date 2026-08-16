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

W4 moves the isolated OSS extraction comparison program into the existing
`_research.material_extraction` namespace. Its historical root path and exact
bytes remain reproducible from the source-pinned
[`W4 manifest`](PYTHON_ROOT_MIGRATIONS.W4.v2.json).

W5 co-locates the C1 book-scale replay judge with its canonical producer under
`_research.bookscale`. Current code discovers the repository root through
`pyproject.toml`, while the historical root command and exact bytes remain
reproducible from the source-pinned
[`W5 manifest`](PYTHON_ROOT_MIGRATIONS.W5.v2.json).

W6 moves the complete cellular runtime cluster into `hswm.cells` and retains
the four installed flat imports as compatibility packages. Root-era bytes and
commands remain reproducible from the source-pinned
[`W6 manifest`](PYTHON_ROOT_MIGRATIONS.W6.v2.json); the older Longinus bindings
and receipts remain immutable historical evidence.

W7 moves the exact hypergraph topology implementation into `hswm.substrate`.
The installed flat import is a module alias, so legacy callers, `__file__`-based
kernel hashes, and canonical callers share one exact module object. The
source-pinned [`W7 manifest`](PYTHON_ROOT_MIGRATIONS.W7.v2.json) preserves the
old root layout, while the active shared-field verifier resolves the same locked
bytes through the migration registry without rewriting its scientific baseline.

W8 moves the exact immutable field-snapshot implementation beside the certified
readout substrate. Its flat import is a module alias, preserving the canonical
module object and source-file SHA used by installed static-kernel identities.
The [`W8 manifest`](PYTHON_ROOT_MIGRATIONS.W8.v2.json) retains the old root
layout and bytes for detached replay.

W9 moves the exact dependency-closed document and corpus world builders beside
the canonical hypergraph substrate. Their flat imports are module aliases, so
legacy and canonical callers share module, class, function, and monkeypatch
identity. The source-pinned
[`W9 manifest`](PYTHON_ROOT_MIGRATIONS.W9.v2.json) preserves both old root
paths and byte identities for detached replay.

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
disjoint; the validator rejects a new or unexplained root module. After W9 the
review class is empty: every remaining module has an explicit evidence or replay
reason.

`quarantine/` contains non-executable historical mutation payloads whose old
instructions conflict with the active bounded ontology policy. They are source
material only, never runbooks.
