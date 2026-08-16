# HSWM artifact layout convention

**Rule: never write new artifacts to the repository root.** New artifacts go
to per-kind subdirectories so the root stays tidy and hash-locked records stay
findable.

## Convention

| Artifact kind            | Filename pattern        | Directory        |
| ------------------------ | ----------------------- | ---------------- |
| Evidence receipt         | `EVIDENCE_*.json`, registered diagnostics | `evidence/` |
| Preregistration          | `PREREG_*.json`, `*.md` | `prereg/`        |
| Run manifest/config      | `*_MANIFEST*.json`, registered configs/splits | `manifests/` |
| Receipt                  | `RECEIPTS_*.json`       | `receipts/`      |
| Results narrative        | `*_RESULTS_*.md`        | `results/`       |
| Raw checked-in result    | registered `*.json`    | `results/raw/`   |
| Narrative research doc   | dated research `*.md`   | `docs/research/` |
| Canon/identity document  | ratified direction or definition | `docs/canon/` |
| Preserved user source    | immutable canon preimage `*.txt` | `docs/canon/sources/` |
| Historical run log       | `*.log`                 | `results/logs/` |
| Machine-readable ontology | `*_ONTOLOGY*.json`      | `ontology/`      |

Repository-wide semantic navigation lives in `ontology/`. Ontology files
organize meaning; they are not a mandatory per-path ledger, an HSWM cognitive
rule, or evidence of learned behavior.

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

## Historical compatibility

The frozen root compatibility set is recorded once in
[`ROOT_COMPATIBILITY_BASELINE.v1.json`](../../ontology/history/ROOT_COMPATIBILITY_BASELINE.v1.json).
Existing source-pinned migration manifests remain available through the
[`history index`](../../ontology/history/README.md) when a published command or
receipt must be replayed at its original commit and path. They are archival
compatibility records, not a template for ordinary unbound file moves. Files
outside the baseline's `paths` array use standard Git moves; relocating a listed
compatibility path adds one source-pinned manifest to the existing replay registry.

Some source-locked programs retain root-era input or output constants. Do not
edit those programs merely to modernize a path or run their default-output mode
against active locked artifacts. Use an explicit typed output when supported;
otherwise reproduce the historical program with `hswm-legacy-replay` in its
detached checkout. Current general-purpose readers and writers should use the
typed resolver above.

## Escape hatch

`HSWM_ARTIFACT_ROOT` redirects the artifact output root (tests, scratch runs):
paths become `$HSWM_ARTIFACT_ROOT/<subdir>/<name>`. The subdir convention
still applies.

## Hash-bound legacy writers

Many historical harness scripts are hash-locked: their sha256 is bound in
`receipts/`, `LOCAL_INTEGRITY_CHECK/`, or source-pinned root-era `PREREG_*.json`
records, so they **must not be
edited**. They keep their root-relative output constants as historical record.
Do not rerun them against the locked root artifacts — a rerun with new data
would break the receipt bindings. New experiments must write new scripts that
route through `hswm.artifacts.layout.default_artifact_path`.

Writers already routed through the helper:
`_research/efficacy/b2_routing_signal.py`,
`_research/efficacy/e1_conditional_traversal.py`, and
`_research/bookscale/c1_prelude_bookscale.py`. The relocated
`_research/p1_closed_loop/p1_run_real.py` preserves the historical basenames
while resolving its inputs and new outputs through the typed layout.
