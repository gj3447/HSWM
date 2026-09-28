# Operational philosophy proof

New proof modules use the existing pinned Lean 4.32.1 and Std; this profile
adds no package dependency. It derives a local abstraction criterion, an
output-behavior quotient's universal property, and executable typed n-ary
storage equivalence. The declared mathematical scope is not physical-world
truth, universal storage-cost optimality, real-LLM fidelity, or full HSWM.

From the repository root:

```sh
npm --prefix src/hswm/effect-runtime run build
node src/hswm/effect-runtime/dist/semantic-philosophy-proof-process.js \
  --profile operational-philosophy \
  --output .hswm-local/operational-philosophy-proof-fresh
```

The output directory must be new. The auditor reuses the exact historical
Linux Lean binary/version pin, compiles the declared dependency chain into a
fresh private OLean directory, and checks each new named theorem/lemma's
axioms. Only `propext`, `Quot.sound`, and `Classical.choice` are permitted.
This is not an independent kernel implementation or a real-model experiment.
The public receipt removes host-specific paths from the private report.

The generic graph codec is new: the historical `encodeNary` API was tied to
its namespace's fixed Role/Vertex enums despite its overbroad description.
Those source bytes and old receipts remain available unchanged. See the
[research note](../../docs/research/HSWM_OPERATIONAL_PHILOSOPHY_PROOF_2026-09-28.md)
for the correction, exact assumptions and remaining HSWM obligations.

The selected durable-branch implementation has a separate file-backed fixture
test. It exercises actual canonical relation revisions and the next semantic
execution with injected HTTP responses, not a real LLM or a Lean-to-TypeScript
compiler proof:

```sh
npm --prefix src/hswm/effect-runtime run test -- \
  ../../../tests/effect-runtime/canonical-atom-v2-semantic-selected-state.test.ts
```

The selection rows, corruption allowance and cost remain caller-declared.
Both branch roots must remain quiescent through reopening and the next step;
this library adapter adds no cross-process transaction or canonical Permit.
