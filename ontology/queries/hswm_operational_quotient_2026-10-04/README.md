# Operational quotient research queries

From the repository root, use the existing `hswm-workspace` commands:

```sh
src/hswm/effect-runtime/bin/hswm-workspace validate operational-quotient
src/hswm/effect-runtime/bin/hswm-workspace query operational-quotient proofs
src/hswm/effect-runtime/bin/hswm-workspace query operational-quotient gaps
```

`proofs` returns four source-bound formal results, including their exact Lean
names. `gaps` returns one explicit boundary. Expected UIDs and predicate roles
are in [`graph-contract.v1.json`](../../../_research/operational_quotient_2026-10-04/graph-contract.v1.json).
SHACL checks structure and claim boundaries. Source SHA matching is separate;
these checks do not establish runtime refinement, efficacy or ideal completeness.
The prior metahumotonic abstraction hypothesis is an external anchor, not a new
proof claim and not an assertion that the hypothesis has passed its evaluation.
