# HSWM-DNRD-5 v2 durable recovery and authority instrument

- Date: 2026-08-28
- Scope: local, no-provider-call instrumentation
- Predecessor implementation: `d772b71a43e92269cb55e63884d6a74c20195b7b`
- Predecessor CI: passed
- Scientific status: `UNJUDGED / NOT AN OCCURRENCE / NOT EFFICACY`

## Canonical target role

HSWM remains one token-native LLM-function macro-neural network. Its evolving,
schema-admitted hypergraph is simultaneously the living harness, world model,
and continuous learner. Durable journal recovery and authority records are
provenance and transition instruments inside that one causal-learning loop;
they are not separate cognition, routing, or learning subsystems. Repository
ontology, KG views, and MCPs remain bounded projections and interfaces.

The relevant canonical atoms have exactly one schema-relative responsibility
owner, typed references, content descriptors bound to canonical bytes, and a
declared position in the outcome-bound transition chronology. Tests are
falsification instruments for those claims, not HSWM progress or learning by
themselves.

## Current checked evidence

The predecessor implementation exposes one package-internal, read-only DNRD-5
recovery witness. It observes the raw durable journal once and replays that
same prefix to obtain both raw record bytes/descriptors and semantic
state/history. The sole dispatcher importer rechecks revision, history, raw
bytes, descriptors, and tail agreement. The symbol is absent from the public
package API and has no mutation operation. Commit `d772b71` passed the hosted
CI suite.

This establishes a local recovery seam suitable for later exact binding. It
does not authenticate an external custodian, prove globally durable storage,
or establish that any scientific occurrence ran.

The next bounded implementation validates canonical byte payloads for one v2
authority chain at one structurally valid DNRD-5 state. It checks:

- exact policy, authorization, capability, revocation-status, and grant atom
  kinds, media types, content hashes, byte lengths, payload schemas, and typed
  reference closure;
- exact membership of those atoms and the phase-appropriate decision purpose
  in a state accepted by the full DNRD-5 v2 canonical-state validator;
- actor, authorizer, custodian, scope, phase, policy generation,
  authorization generation, capability generation, authorization reference,
  capability ID, nonce, and declared validity-interval equality;
- direct binding of a main authority chain to the authority references on its
  `revision_admission_decision` or `rollback_decision`; and
- disjoint main/evidence authorization records and one-revision append-only
  structural ordering for an S0/R1 pair.

Its return type explicitly says that this is a caller-state structural check,
not durable recovery, a Permit, or a CAS. A future dispatcher may use it only
after supplying a state obtained from the internal recovery witness and after
independently binding the exact command and journal record.

Exactly one schema-relative responsibility owner per atom does not by itself
require a different runtime principal for every custodian role. This bounded
verifier requires the declared authorizer to differ from the actor and each
listed state-change custodian; any stronger separation-of-duty matrix must be
declared and tested at the dispatcher policy boundary rather than inferred
from role names.

## Conceptual delta

The transition protocol must not collapse authority and evidence sealing into
one capability or one state write. For an admission it is:

```text
verified S0
  -> CAS1 {capability_consumption, macro_disposition}
  -> recover and verify exact R1/main-record bytes
  -> CAS2 {evidence_seal_consumption, revision_transition_receipt}
  -> recover and verify exact R2/receipt-record bytes
```

For a restore, CAS1 writes `{capability_consumption,
restore_transaction}` and CAS2 writes `{evidence_seal_consumption,
rollback_transition_receipt}`. Main and evidence authorization decisions,
capabilities, revocation-status records, grants, capability IDs, authorization
references, and nonces are distinct. They may share a policy only when that
policy explicitly authorizes both matching phases for the same actor, scope,
and decision purpose.

After a crash following CAS1, recovery must never resubmit the main command.
Only an exact R1 match may proceed to deterministic receipt construction and
CAS2. A missing, competing, or mismatched R1 is incomplete or conflicting,
never silently relabeled as success. Receipt identity derives from the actual
recovered CAS1 record descriptor and contains no self-hash of its own future
record.

## Explicit nonclaims and next gate

The present instruments do not prove external authorization, trusted time,
custody, nonce uniqueness beyond one recovered lineage, an exact CAS1 result,
provider execution, Source A, occurrence, macroplastic learning, causal
improvement, or efficacy. A caller-supplied state cannot by itself prove
durable recovery, and an immutable `CHECKED_NOT_REVOKED` payload is only a
snapshot-local record unless a later authenticated revocation/time source is
bound.

The next implementation gate is therefore narrow:

1. bind the validated main authority payload to an exact recovered S0 and
   exact ADMIT command;
2. execute CAS1 once and recover its exact raw record as R1;
3. revalidate distinct evidence authority at R1, derive the receipt solely
   from R1, and execute CAS2 once;
4. recover and verify R2;
5. reject crash, replay, stale-head, cross-wired purpose/authority, and
   concurrent-writer counterexamples; and
6. repeat the same contract for RESTORE before any provider call.

Because this work is instrumentation rather than a material research result,
it creates no content-addressed result receipt and no
`F1_R8_RESULTS_LOG.md` entry.
