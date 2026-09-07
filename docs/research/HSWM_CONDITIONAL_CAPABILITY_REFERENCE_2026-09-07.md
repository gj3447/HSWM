# Conditional capability reference implementation

Status: SECONDARY_AI_IMPLEMENTATION_PREVIEW_ONLY.

The original design contract and its historical KG projection remain unchanged.
The conceptual delta is executable, bounded three-valued relation evaluation and
priority-based next-proposal selection. Relation and disposition candidates are
separate version-bound inputs into one computation; neither is a canonical atom.
Future admission must bind each atom to one schema-relative owner, typed references,
provenance, independent outcome/credit and current Inv/Permit.

The implementation lives in `src/hswm/cells/conditional.py`. It uses a small typed
Python input projection, not a parser for every record in the JSON design contract.
It emits design previews only, cannot execute tools, and has no admission API.
No compiled execution view or upper-cell composition is implemented.

## Experience proposal boundary (specified before implementation)

The bounded synthesizer receives only a declared finite field domain and explicitly
supplied complete public observation/outcome examples with source references.
It receives no evaluator, task identifier, hidden rule, locator, future outcome,
answer table from the twelve authored cases, or filesystem access callback.
An external caller is responsible for authenticating and sealing those sources;
this in-process interface is not OS isolation or verification of external evidence.

The search proposes conjunctions of equality leaves (a subset of the allowed AST
language), at most eight consistent candidates, using at most three leaves and a
bounded enumeration budget. It may create or revise a candidate from this history.
Contradictory duplicate contexts cause reopening. No candidates means unresolved,
not proof of an absent cause. Proposals retain OTHER and UNIDENTIFIED_CREDIT.
This is finite grammar synthesis, not new-field discovery or canonical learning.

Synthetic software checks keep their authored examples outside the implementation.
They test relation replacement, removal/restoration, missing observations, revision
and permission changes, and history-driven candidate changes. They are not a
held-out efficacy experiment. The original twelve cases include admission, handoff,
resolver and probe concerns outside this preview; no blanket 12/12 claim is made.
S-6, G0, G1 and D-4 retain their existing unresolved statuses.

## Implemented boundary and verification

The typed preview currently supports exact relation guards, explicit priority,
parameterless action proposals, missing-field observation requests, and an explicit
withhold fallback. Inline AST disposition guards, parameter bindings, alias/action
constraints, full proposal-record serialization, authenticated seals, admitted view
compilation, and causal-credit adjudication remain future work. Its provenance
references are caller assertions. The preview UID binds its static input subset;
it is not the future execution cache key. No candidate is claimed semantically
novel merely because its AST differs.

Validation command:

```sh
uv run pytest -q tests/test_conditional_capability.py tests/test_hswm_cellular_runtime.py
```

Result: 31 tests passed, including 20 new preview/synthesis checks. In the authored
counterexample, replacing `ready` with `ready AND clean` increases reads from one
to two fields and changes ACTION_PROPOSAL to WITHHOLD; restoring the original
relation restores the original preview. Adding an observed negative example to
public history removes the single-field candidate and retains a conjunction.
These are software semantics checks, not a material research efficacy result;
no research receipt or results-log promotion is warranted.
