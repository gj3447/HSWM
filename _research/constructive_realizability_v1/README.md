# Constructive proof round 1

This program checks three standalone formal artifacts with the repository's
existing Lean 4.32.1 toolchain. It does not run a model efficacy experiment.

From the HSWM checkout:

```bash
cd formal
lake env lean --trust=0 HSWMFiniteSelection.lean
lake env lean --trust=0 HSWMFiniteRandomizedIdentification.lean
lake env lean --trust=0 HSWMCompositionInterference.lean
```

The sources import `Std` only. No new toolchain or package is required.
`--trust=0` asks this Lean implementation to type-check imported modules as well.
This is kernel rechecking by the pinned Lean implementation; it is not a
qualification using a separate checker implementation.

The files are standalone proof artifacts, intentionally checked by the three
explicit commands above. The historical `formal/lakefile.toml` remains unchanged;
its default `lake build` does not select these new modules. A successful default
build alone must not be reported as verification of this round.

For an axiom audit, compile each exact source again with appended `#check` and
`#print axioms` commands for its named theorems. Preserve the source SHA-256,
command, compiler identity, exit status and output. The current audit permits
Lean's foundational `propext`, `Classical.choice`, and `Quot.sound`; it does not
permit `sorryAx`, new goal axioms, or `Lean.ofReduceBool` from `native_decide`.
An axiom audit checks proof dependencies, not whether a theorem's mathematical
statement matches the intended scientific claim. That requires separate review.

See the [round report](../../docs/research/HSWM_CONSTRUCTIVE_PROOF_ROUND_1_2026-09-10.md)
for the exact statements, model assumptions, counterexamples and open HSWM
connections. The [original program](../../docs/research/HSWM_CONSTRUCTIVE_REALIZABILITY_PROGRAM_2026-09-10.md)
and [prospective research graph](../research_coordination/constructive_realizability.v1.json)
remain historical inputs. Actual task events, raw agent outputs and build logs
are retained locally rather than published as scientific outcome data.
