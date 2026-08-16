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
| Raw checked-in result    | registered `*.json`    | `results/raw/`   |
| Narrative research doc   | dated research `*.md`   | `docs/research/` |
| Canon/identity document  | ratified direction or definition | `docs/canon/` |
| Historical run log       | `*.log`                 | `results/logs/` |
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

W10 removed the first 58 audited non-Python legacy files from the physical
root. Their old names, source commit, and SHA-256 values are recorded in
[`ROOT_ASSET_MIGRATIONS.W10.v1.json`](../../ontology/history/ROOT_ASSET_MIGRATIONS.W10.v1.json),
so `hswm-legacy-replay` can materialize the exact pre-move checkout. The
remaining root assets are not invitations for new output: each belongs to a
path/SHA dependency cluster that must move atomically in a later wave.

[`ROOT_ASSET_MIGRATIONS.W11.v1.json`](../../ontology/history/ROOT_ASSET_MIGRATIONS.W11.v1.json)
moves the complete 17-file checked-in raw-result set to `results/raw/`.
The allowlist is deliberately exact: generic `*_result.json` classification
would incorrectly capture evidence fixtures with a different lifecycle. The
artifact resolver checks `results/raw/` first and the historical root second.

Five source-SHA-bound historical writers still contain their original root
defaults: `ab_p5_full.py`, `traversal_cert.py`, `stale_poisoning.py`,
`qkv_routing_falsifier.py`, and `qkv_b1_development_falsifier.py`. They are
preserved for detached replay and are not examples for current writers. Do not
run their default-output modes in the active checkout; use an explicit
`--out results/raw/<name>` where supported, or reproduce the no-`--out`
programs in the detached legacy-replay checkout.

Byte-frozen or user-primary records keep five original root-relative links:
two in `CANON_DIRECTION_...md`, two in
`USER_PRIMARY_HSWM_TOKEN_LEARNING_...md`, and one in
`f0_premise_p/PREREG.md`. The moved `PREREG_P0_...md` keeps one reciprocal
historical link. These links resolve in the detached replay checkout; their
source records are intentionally not edited just to rewrite navigation.

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
`_research/bookscale/c1_prelude_bookscale.py`. The relocated
`_research/p1_closed_loop/p1_run_real.py` intentionally preserves its locked
root artifact names through explicit repository-root discovery.
