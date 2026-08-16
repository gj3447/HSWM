# Python source layout

`hswm/` is the canonical implementation namespace. Its directories express
semantic responsibility rather than experiment chronology:

| package | responsibility |
|---|---|
| `hswm.artifacts` | artifact discovery and path compatibility |
| `hswm.cells` | typed cellular execution, durable storage, and model ports |
| `hswm.diagnostics` | bounded diagnostics |
| `hswm.evaluation` | falsifiers and evidence-bound evaluation helpers |
| `hswm.experiments` | packaged experiment components |
| `hswm.infrastructure` | provider and repository integration |
| `hswm.learning` | outcome/credit/update contracts and diagnostics |
| `hswm.prototypes` | early synthetic and judgment-loop prototypes |
| `hswm.substrate` | world adaptation, certified reads, and convergence |

The other top-level directories under `src/` are compatibility import packages.
They preserve selected historical imports without putting `.py` shims back in
the repository root. New code must import the canonical `hswm.*` path.

Source-only experiment programs belong under `_research/`; maintenance commands
belong under `scripts/`. Root paths that cannot yet move are classified and
explained by [`ontology/history/PYTHON_ROOT_CLASSIFICATION.v1.json`](../ontology/history/PYTHON_ROOT_CLASSIFICATION.v1.json).
