# Optimization reinforcement contract

This additive view records a user goal, six AI-attributed rule augmentations,
four evaluation contracts, six unmeasured bottleneck stages, two existing
conditional Lean references, and three non-promotion boundaries. It does not
claim runtime W learning, measured efficacy, a bottleneck-free execution, or
global optimality.

All queries are scoped to `sym:AbstractNode:hswm-optimization-contract-2026-10-07-v1`.
`rules`, `contracts`, `bottlenecks`, `boundaries`, and `proofs` answer the
corresponding competency questions with source-connected subjects. It records
three direct source roles: the user reinforcement utterance, the existing Lean
reference, and evaluation-contract guidance. The six `REFERENCES` edges preserve
the stable base-rule identities without copying their canon.

`HAS_CONCEPT` goes from this view to its goal, rule, contract, bottleneck,
formal-reference and boundary nodes; the root has exactly one USER_GOAL, one
AI_GOAL_RESTATEMENT, six rules, four contracts, six stages, two references and
three boundaries. `HAS_SOURCE` goes from a claim or contract to its source.
Each rule has exactly one `REFERENCES` edge to its base-rule anchor, exactly one
`CONSTRAINS` edge to its evaluation contract, and exactly one evaluation-source
edge. Contracts and boundaries `CONSTRAINS` the root; stages `CONSTRAINS` the
end-to-end contract. These directions preserve subject ownership and make
cardinality checkable without turning navigation into runtime authority.

This view does not compose the base bundle. Artifact bindings pin the research
document, rule sources, routing observation, queries, shapes and test by SHA-256.
The validation report is derived from this bundle and is not included in its
bindings, avoiding a circular hash dependency. A historical match and a current
worktree match are separate observations.
