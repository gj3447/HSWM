# HSWM-DNRD-5 v2 durable recovery and authority instrument

- Date: 2026-08-28
- Scope: local, no-provider-call instrumentation
- Recovery/authority/consumption predecessors: `d772b71`, `e98d491`, `61d81c3`
- Latest predecessor CI: passed (`61d81c3`)
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

The next local instrument now validates one cycle-free consumption candidate
for each of `MAIN_ADMIT`, `MAIN_RESTORE`, `RECEIPT_ADMIT`, and
`RECEIPT_RESTORE`. Each candidate binds canonical payload and intent bytes to:

- the full validated caller state and its exact revision and canonical hash;
- the recovered journal lineage and exact raw-head descriptor;
- one phase-specific authority chain, purpose atom, nonce, and evaluation
  timestamp;
- one deterministic consumption-atom UID and four exact typed references;
- one full companion write with the phase-appropriate kind and reciprocal
  consumption reference; and
- the exact external dependency read set and a reconstructed, schema-valid
  two-write atomic chronology.

The command projection deliberately omits the consumption write whose content
commits to that projection. Reconstructing the omitted write before chronology
validation avoids a self-hash cycle while preserving the exact command
commitment. The validator rejects noncanonical bytes, descriptor drift,
surplus or missing reads, cross-wired references, wrong state-member kinds,
reused local atom or transition identities, and invalid two-write topology.
Its result remains a deeply immutable structural binding summary with an
explicit terminal status of `NOT_DURABLE_RECOVERY`, `NOT_CONSUMED`,
`NOT_PERMIT`, `NOT_CAS`, `NOT_OCCURRENCE`, `NOT_LEARNING`, and
`NOT_SCIENTIFIC_RESULT`.

This candidate check detects replay only against the supplied state. It does
not establish global or cross-purpose nonce consumption; the durable
dispatcher must make that guarantee from recovered state and compare-and-swap
outcomes.

The current dispatcher implements the first narrow durable path: initial
`ADMIT` from an exact recovered S0 through two separately authorized
compare-and-swap records, plus a recovery-only continuation for the exact
S0/R1/R2 prefix. Before CAS1 the initial entrypoint strictly decodes and
defensively snapshots the caller input, reconstructs the two-write command
from the consumption projection, validates the exact DNRD effect grammar,
binds actor/capability/scope/time to the validated main authority, and scans
all recovered `capability_consumption` and `evidence_seal_consumption` atoms
for a duplicate nonce across phases. Payload and envelope bindings are
recomputed from the supplied bytes before submission.

CAS1 is followed unconditionally by one raw recovery observation, including
when the submit call reports failure. Confirmation requires the exact next
revision, canonical journal bytes and descriptor, immediate predecessor,
write envelopes reread in journal-binding order, raw record replay, and the
exact main consumption atom. Receipt bytes and UID are then derived only from
that recovered R1 identity. Before CAS2, the dispatcher validates a disjoint
`RECEIPT_ADMIT` authority chain at exact R1, the receipt consumption, and the
full receipt grammar. CAS2 is likewise followed unconditionally by raw
recovery and full receipt-seal replay before returning
`CAS2_EXACT_R2_CONFIRMED`.

The separate `resumeDnrd5V2AdmitTwoCas` entrypoint has no call path to CAS1.
It obtains one raw recovery witness and canonically replays genesis through the
caller-declared S0 and the following R1 using the actual content-store envelope
bytes. It then binds both supplied phase transitions, commands, write-payload
sets, content descriptors, and envelope descriptors without staging. An exact
R1 may cause at most one CAS2 attempt followed by a fresh raw recovery; an
already exact R2 is fully revalidated and confirmed without a journal write.
S0, an extra tail, a different R1/R2, or a malformed or surplus candidate fails
closed. A concurrent CAS2 loser may report confirmation only after its fresh
recovery independently reconstructs the same exact R2.

The exported module-level receipt candidate verifier no longer accepts an
unvalidated grant/capability/revocation ID tuple. It revalidates the full
evidence authority payload against the exact receipt prestate and binds its
receipt phase, decision purpose, three authority references, actor, capability
ID, scope, and evaluation time. This resolves a genuine protocol contradiction:
the old receipt check required the evidence triple to equal the main
decision's authority triple, while the two-phase protocol requires the main
and evidence chains to be distinct.

Focused falsification covers the exact S0→R1→R2 success path and immediate
initial-entrypoint retry rejection, malformed ingress without journal mutation,
a forged receipt that leaves exact R1 without CAS2, a main command
authority-header mismatch, main/evidence authority cross-wiring, and
cross-phase nonce reuse. Resume-specific cases cover exact-R1 continuation
without a second R1, exact-R2 no-write idempotence, S0-only refusal, two
concurrent resumes converging without R3, and a fresh file-runtime reopen.
They also reject a duplicate receipt payload mapping at R1, a schema-valid
mutated main transition at R2, and changed main write-payload bytes at R2
without changing the journal. Standalone
receipt verification additionally rejects authority/header/phase/purpose and
raw-record cross-wires. Dedicated cases also show that generic-schema-valid
but DNRD-grammar-invalid main and receipt commands are rejected before their
respective CAS, leaving S0 or exact receipt-pending R1 unchanged. These tests
establish behavior of the local instrument; they are not evidence that HSWM
learned or improved.

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

After a crash following CAS1, the resume entrypoint never resubmits the main
command. Only an exact R1 match may proceed to deterministic receipt
construction and CAS2. A missing, competing, or mismatched R1 is incomplete
or conflicting, never silently relabeled as success. Receipt identity derives
from the actual recovered CAS1 record descriptor and contains no self-hash of
its own future record. The initial entrypoint remains intentionally
initial-only; continuation is isolated in the recovery-only entrypoint so no
resume branch can accidentally issue CAS1.

## Explicit nonclaims and next gate

The present instruments do not prove external authorization, trusted time,
external custody, nonce uniqueness beyond one recovered lineage, OS/process
kill or power-loss durability, provider execution, Source A, occurrence,
macroplastic learning, causal improvement, or efficacy. They do establish
exact local R1/R2 recovery for the initial and recovery-only ADMIT paths,
including reconstruction through a newly opened file-runtime layer. A
caller-supplied state cannot by itself prove durable recovery, and an immutable
`CHECKED_NOT_REVOKED` payload is only a snapshot-local record unless a later
authenticated revocation/time source is bound.

The next implementation gate is therefore narrow and ordered:

1. inject lost-return and actual process-boundary failures after CAS1 and CAS2,
   and
   distinguish exact receipt-pending state from competing or malformed tails;
2. add stale-head and cross-process concurrent-writer schedules that prove one
   durable winner and deterministic loser classification;
3. implement and falsify the symmetric `MAIN_RESTORE` / `RECEIPT_RESTORE`
   two-CAS path; and
4. only then connect the provider-free randomized/placebo causal experiment
   runner that can test outcome→credit→revision→fresh-behavior effects.

Because this work is instrumentation rather than a material research result,
it creates no content-addressed result receipt and no
`F1_R8_RESULTS_LOG.md` entry.
