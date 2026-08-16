# HSWM artifact layout convention

**Rule: never write new artifacts to the repository root.** New artifacts go
to per-kind subdirectories so the root stays tidy and hash-locked records stay
findable.

## Convention

| Artifact kind            | Filename pattern        | Directory        |
| ------------------------ | ----------------------- | ---------------- |
| Evidence receipt         | `EVIDENCE_*.json`       | `evidence/`      |
| Preregistration          | `PREREG_*.json`, `*.md` | `prereg/`        |
| Run manifest             | `*_MANIFEST*.json`      | `manifests/`     |
| Results narrative        | `*_RESULTS_*.md`        | `results/`       |
| Narrative research doc   | dated research `*.md`   | `docs/research/` |
| Machine-readable ontology | `*_ONTOLOGY*.json`      | `ontology/`      |

The repository-wide path/concept projection lives in `ontology/`. Ontology
files organize meaning and navigation; they are not HSWM cognitive rules or
evidence of learned behavior.

## Helper

Use the canonical `hswm.artifacts.layout` package instead of hardcoding paths:

```python
from hswm.artifacts.layout import default_artifact_path, resolve_artifact_path

out = default_artifact_path("EVIDENCE_EXAMPLE_2026-01-01.json")   # evidence/...
path = resolve_artifact_path("EVIDENCE_B1_IDENTITY_UNLOCK_2026-07-22.json")
```

- `default_artifact_path(name, kind=None)` — write path in the per-kind
  subdir (creates the directory). Kind is inferred from the filename via
  `classify_artifact()`; pass `kind=` for anything non-standard.
- `resolve_artifact_path(name, root=None)` — read resolution: per-kind subdir
  first, **legacy root second**. Old root files and new subdir files both
  resolve; path+sha256 ledger entries keep working unchanged.
- `iter_artifact_paths(name)` — both locations, for listing-style readers.

## Escape hatch

`HSWM_ARTIFACT_ROOT` redirects the artifact output root (tests, scratch runs):
paths become `$HSWM_ARTIFACT_ROOT/<subdir>/<name>`. The subdir convention
still applies.

## Hash-bound legacy writers

Many historical harness scripts are hash-locked: their sha256 is bound in
`receipts/`, `LOCAL_INTEGRITY_CHECK/`, or root `PREREG_*.json` records, so they **must not be
edited**. They keep their root-relative output constants as historical record.
Do not rerun them against the locked root artifacts — a rerun with new data
would break the receipt bindings. New experiments must write new scripts that
route through `hswm.artifacts.layout.default_artifact_path`.

Writers already routed through the helper:
`_research/efficacy/b2_routing_signal.py`,
`_research/efficacy/e1_conditional_traversal.py`, and
`c1_prelude_bookscale.py`. Untracked/WIP
scripts (e.g. `p1_run_real.py`) are out of scope — route them when they are
adopted as tracked.
