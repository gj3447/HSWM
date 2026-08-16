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
| `hswm.substrate` | hypergraph topology, document/world construction, immutable field cuts, certified reads, and convergence |

The other top-level directories under `src/` are compatibility import packages.
They preserve selected historical imports without putting `.py` shims back in
the repository root. New code must import the canonical `hswm.*` path.

Source-only experiment programs belong under `_research/`; maintenance commands
belong under `scripts/`. Root compatibility reasons are frozen in
[`ROOT_COMPATIBILITY_BASELINE.v1.json`](../ontology/history/ROOT_COMPATIBILITY_BASELINE.v1.json);
their replay and migration policy is documented in
[`ontology/history/README.md`](../ontology/history/README.md).
