# Three-philosophies Lean proof audit

This is a bounded TypeScript/Effect runner for source-pinned Lean compilation
and axiom inspection of the finite formal witnesses attached to the three HSWM
directions. It does not make a new canonical write path or research gate.

```sh
npm --prefix src/hswm/effect-runtime run build
node src/hswm/effect-runtime/dist/semantic-philosophy-proof-process.js \
  --output .hswm-local/three-philosophies-proof-$(date +%Y%m%dT%H%M%SZ)
```

`--output` must name a fresh private directory. The runner resolves the
existing pinned Lean with `lake env which lean` from `formal/`, checks its
exact v4.32.1 version, binary SHA-256, and `formal/lean-toolchain` SHA-256
against the pre-existing source-bound record
[`_research/llm_semantic_graph_v1/lean-verification.v1.json`](../llm_semantic_graph_v1/lean-verification.v1.json).
It installs nothing. `--lean /absolute/path/to/lean` is available only when
the caller needs to select an already-installed exact pinned binary.

The runner compiles the dependency order into a fresh private OLean directory
using the exact validated absolute Lean binary (including an explicit
`--lean` value), hashes every source before and after compilation, and rebinds
all sources and the runner itself immediately before the report. It scans
reviewed code for `sorry`, `admit`, axiom/opaque/unsafe/meta declarations,
`native_decide`, and kernel-bypassing settings. Lean runs with `--trust=0`.
The runner appends `#print axioms` for every public theorem in the three new
philosophy modules and requires one unambiguous result per expected full
theorem name. It accepts only `propext`, `Quot.sound`, and `Classical.choice`.
Any other reported axiom, failed command, source drift, timeout, truncation,
or report ambiguity fails without producing a success report.

The output `lean-verification.v1.json` records toolchain identity, source and
compiler-output hashes, full theorem names, and exact reported axioms per
theorem as well as per source. It is a private fresh receipt. Copying any
result into public research evidence is a separate review action.

Claim ceiling: a successful audit establishes only that the declared finite,
conditional Lean statements checked against this kernel/toolchain. It does not
establish an outermost universe simulator, universal hypergraph minimum cost,
the physical/computational reality of CHU, actual LLM fidelity, or HSWM
efficacy.
