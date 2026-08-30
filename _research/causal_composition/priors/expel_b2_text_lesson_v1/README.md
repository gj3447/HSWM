# ExpeL B2 text-lesson prior pin

This directory pins an official ExpeL source boundary for a possible future
`B2_EXPEL_TEXT_LESSON` baseline arm. It is not an implementation, vendored
dependency, experiment, G0 qualification, G1 comparison, or HSWM result.

## What is pinned

[`source_pin.v1.json`](source_pin.v1.json) records the official ExpeL paper
(`arXiv:2308.10144v3`), the official `LeapLabTHU/ExpeL` commit
`e41ec9a24823e7b560c561ab191441b56d9bcefc` and tree
`8ba77f84284693ebbe12ba9a93bd32fd101a6922`, its Apache-2.0 license, and
SHA-256 digests for the versioned paper PDF, observed commit tarball, license,
and four minimal algorithm files. It intentionally records an immutable commit
because the upstream has no release or tag to pin; the tarball is accepted only
when its observed bytes match the recorded digest.

The minimal reusable comparator is: sealed training trajectories and outcomes
produce bounded natural-language lessons; a frozen similarity rule retrieves
those lessons into a fresh B2 probe. This is an external text-lesson baseline,
not an HSWM canonical revision. Its state is arm-private and cannot authorize
HSWM outcome-credit-owner-`Permit` mutation.

## Required future binding

Before a scientific occurrence, a separate preregistration must bind every
field listed in `future_run_contract.fixed_before_outcome_inspection`, including
the exact prompt bytes, lesson/retrieval policy, split, model/tool surface,
and resource budget. It must also demonstrate direct-versus-wrapper parity and
B2-only state isolation. The pin deliberately does not choose those values or
select a comparator for an already consumed occurrence.

The focused offline test validates this record's local schema and digest
invariants. It never fetches upstream resources; re-downloading upstream bytes
is an explicit, separate source-audit action.
