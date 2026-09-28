# Fresh-evaluation statistical learning proof

The isolated package in `formal/statistical-learning` pins Lean 4.32.1 and
Mathlib through its Lake manifest. It proves a finite-candidate concentration
bound, bounded row-corruption correction, selection soundness and power, and a
connection to the existing canonical graph `Step` and trace-bound `Learn`.

In `formal/statistical-learning`, Lake uses the checked-in manifest for the
dependency revisions. With the pinned Lean toolchain installed, prepare the
required Mathlib cache and build the aggregate package:

```sh
lake exe cache get Mathlib.Probability.Moments.SubGaussian
lake build
```

Then, from the repository root:

```sh
npm --prefix src/hswm/effect-runtime run build
node src/hswm/effect-runtime/dist/statistical-learning-proof-process.js \
  --output .hswm-local/statistical-learning-proof-fresh
```

The output directory must be new. The auditor uses the existing exact Lean
Linux binary/version pin, checks package configuration, dependency revisions
and clean dependency worktrees before and after the run,
compiles the legacy graph source and the four new modules into a fresh private
OLean directory, and prints every new public theorem/lemma's axioms. Only
`propext`, `Quot.sound`, and `Classical.choice` are permitted. It rechecks source
hashes before writing a receipt. The auditor itself installs no dependencies.

The checked-in `lean-verification.v1.json` is the public projection of that
audit. Mathlib's compiled imports are an explicitly recorded dependency trust
boundary; the auditor does not authenticate every cached OLean byte by
rebuilding from source. This is not an independent rebuild/check of every imported library
proof or of the Lean kernel. Exact-real selection is mathematical and is not
an extracted TypeScript numeric certificate.

The theorem assumptions do not certify real-world sampling, outcome truth,
the corruption witness, actual LLM fidelity, cost measurement, distribution
shift, or full recursive HSWM. See the [research note](../../docs/research/HSWM_FRESH_EVALUATION_LEAN_PROOF_2026-09-28.md)
and [dependency pins](../../formal/statistical-learning/SOURCE_PINS.md).
