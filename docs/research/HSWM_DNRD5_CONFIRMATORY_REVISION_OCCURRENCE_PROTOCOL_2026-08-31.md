# HSWM DNRD-5 confirmatory revision occurrence protocol

- Date: `2026-08-31`
- Status: `PRE_OUTCOME_PROTOCOL_AND_VALIDATOR_ONLY / NOT_PREREGISTERED / NOT_EXECUTED / NO_SCIENTIFIC_RESULT`
- Executable gate: [`confirmatory_revision_protocol.py`](../../_research/dnrd5/confirmatory_revision_protocol.py)

## Role and conceptual delta

The target remains the outcome-to-credit-to-revision-to-fresh-behavior loop.
The existing DNRD-5 design specifies its causal question, but no checked-in
asset previously made the exact pre-outcome requirements an executable,
fail-closed handoff gate.  This protocol adds that gate.  It does not change
the target, reduce the 300-block criterion, or turn an implementation check
into a result.

## Required real occurrence

Before any provider call, one canonical manifest must bind the exact source
commit/tree, task generator, private probe and placebo commitments, W0/fork
bytes, future-randomness allocation, model/runtime snapshot, decoding seeds,
Permit policy, evaluator program, independent judge program, analysis program,
and an external append-only raw-artifact destination.

The current validator checks the declaration and its artifact descriptors. It
does not fetch those artifacts, recompute their descriptors, authenticate the
named principals, or attest that the external destination enforces its declared
access controls.

The occurrence is exactly 300 independently generated blocks and 2,700
generation calls.  It has no retry, replacement, resume, cache substitution,
or uncounted generation.  Each block keeps the existing four interventions:

- `ACTIVE` receives genuine attributable feedback and a current scoped Permit.
- `OUTCOME_INDEPENDENT_SHAM` receives distribution-matched source-blind
  placebo feedback, not a donor outcome.
- `DELAYED_NO_CREDIT` cannot admit feedback before all probe-response seals.
- `EXACT_W0_ROLLBACK` restores the behavior root and compiled readset byte for
  byte before probing.

The manifest requires a distinct transition executor, revision proposer,
outcome evaluator, credit adjudicator, independent judge, and Permit
authorizer.  This is only a minimum non-collapse condition; distinct strings
do not authenticate people, organizations, or services.

The real occurrence must use an evaluator that holds the hidden answer under
separate private custody, sees sealed probe responses but not arm, clone, probe
order, canonical state, or feedback source, and has no write access after
sealing. A separately sourced post-seal judge must independently reimplement
the artifact and analysis verification. The validator structurally requires
declarations of those properties; it does not itself prove the custody or
access-control facts. The manifest therefore makes *how outcome truth and
causal credit would be tested* explicit without asserting that either has
happened.

## Promotion gate and claim ceiling

Passing `validate_confirmatory_readiness` establishes only structural
pre-outcome eligibility.  It establishes none of execution, actual immutable
storage, source independence, outcome truth, causal credit, or improvement in
fresh LLM behavior.

To promote beyond that ceiling, all of the following must be present and
independently checked after a fresh occurrence:

1. external pre-outcome seals and raw request/response/evaluator artifacts;
2. real Permit issuance/revocation/time/nonce and durable transition receipts;
3. blind outcome scoring with private-answer opening and independent replay;
4. all 300 complete four-arm block seals, with no integrity failure or missing
   evaluator receipt; and
5. the frozen three-contrast analysis and its independently reproduced result.

Only a complete integrity-valid occurrence whose three frozen contrasts meet
their predeclared pass criteria may support the bounded DNRD-5 causal claim. A
negative or incomplete result retires or reroutes this mechanism route; it does
not change HSWM's target.

## Current blocker

No such manifest has been bound to a real DGX/model snapshot, future randomness
source, externally controlled immutable store, independently operated evaluator
or judge, or 300-block raw corpus.  The current protocol therefore does not
justify an outcome-truth, independent-causal-credit, or LLM-improvement claim.
