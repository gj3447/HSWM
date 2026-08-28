# HSWM-DNRD-5 successor schema and transaction chronology

- Date: 2026-08-28
- Successor experiment schema identity:
  `hswm:dnrd5:causal-macroplasticity:v2`
- Canonical schema-content bytes: `31,298`
- Canonical schema-content SHA-256:
  `a921264c5d1b5d9186d291e6a17ddc0282ce4eaa8832b1a599b7237c23d4b357`
- Generic substrate: Canonical Atom V2, unchanged
- Status: `CHECKED STRUCTURAL IMPLEMENTATION / UNJUDGED / SOURCE-A BLOCKED`
- Decision: `ACTUAL-BYTE CORPUS AND SOURCE-A FREEZE REMAIN BLOCKED`
- Model/provider calls: `0`

## Target identity, current evidence, and conceptual delta

The target remains one token-native LLM-function macro-neural network whose
schema-admitted evolving hypergraph is simultaneously its living harness,
world model, and continuous learner.  Lifecycle records, repository ontology,
KG projections, and MCP interfaces are bounded observations or interfaces to
that state; they are not independent cognition or learning systems.

The current evidence establishes structural contracts only.  The preserved
DNRD-5 v1 experiment schema has 37 kinds and a durable generic transaction
kernel.  The distinct v2 successor schema now has 44 kinds, and checked
instruments validate its same-batch dependency topology, canonical
ADMIT/RESTORE journal records, postcommit revision/rollback receipt seals, and
delayed audit-release record.  A separate adapter closes the preserved
lifecycle's 15 events, 59 artifact rows, 27 artifact kinds, and nine planned
generation calls to the v2 structural vocabulary.  No production atom payload
corpus, provider call, occurrence, state-learning effect, or efficacy
observation exists.

The lifecycle/atom alignment audit exposed three conceptual gaps:

1. v1 has no owned `audit_release` kind even though delayed disclosure has an
   information and authorization effect;
2. v1 `block_seal` does not close all atom, event, call, provider, Permit, and
   content bytes; and
3. v1 uses `transition_receipt` inside the same atomic write grammar as the
   effect it purports to receipt.  Such a pre-commit atom cannot bind the
   recovered journal record that only exists after the CAS succeeds.

The successor delta is therefore semantic, not cosmetic: distinguish
pre-commit authorization decisions, atomic state effects, and post-commit
durability observations; represent same-batch dependencies explicitly; add an
owned delayed release; and close the complete block evidence set.

## Version and preservation boundary

The v1 experiment identity, schema bytes, validators, historical designs, and
checked-in evidence remain unchanged.  The successor is a new experiment
schema identity, not an in-place edit and not a migration of admitted v1 atoms.
The generic Canonical Atom V2 kernel already permits references among writes in
one command and rejects cyclic provenance.  It is also unchanged.

The v1 `validateDnrd5ChronologicalAtoms` function validates a flat sequence of
already-materialized atoms.  Its rejection of same-batch forward references is
correct for that input model.  The successor adds a transaction/batch
chronology instrument rather than weakening or relabeling the v1 checker.

## Implemented schema semantics and remaining semantic obligations

The successor schema must retain exactly one schema-relative responsibility
owner per kind and exact typed-reference cardinalities.  At minimum it changes
or adds these roles:

| Kind | Lifecycle and responsibility |
| --- | --- |
| `revision_admission_decision` | Pre-commit decision directly binding one block, assignment, fork, proposal, validation, credit decision, grant, and authority chain.  The assignment-to-arm match and intended effect payload remain semantic-validator obligations.  It is not a receipt and cannot claim that a CAS occurred. |
| `rollback_decision` | Pre-commit restore decision directly binding block/assignment/fork scope, the admitted rollback staging disposition and its revision receipt, W0, restore policy, grant, and authority chain.  Exact restore intent remains a payload/semantic-validator obligation. |
| `capability_consumption` | One-shot consumption for a state-changing admission or restore.  It binds the current grant/capability/revocation chain and exactly one decision branch. |
| `macro_disposition` | State-effect atom written in the admission CAS.  It references its proposal, pre-commit decision, restore policy, and same-batch effect consumption; it does not reference a future receipt. |
| `restore_transaction` | State-effect atom written in the restore CAS.  It references W0, the staging disposition, rollback decision, restore policy/grant, and same-batch effect consumption. |
| `revision_transition_receipt` | Post-commit observation of one recovered admission CAS.  It references the admission decision, resulting disposition, main effect consumption, and separately consumed evidence-seal authority. |
| `rollback_transition_receipt` | Post-commit observation of the recovered restore CAS.  It references the rollback decision, restore transaction, main effect consumption, and separately consumed evidence-seal authority. |
| `evidence_seal_consumption` | One-shot, non-state-effect authority consumed with a post-commit receipt or delayed audit release.  Its purpose is exactly one revision decision, rollback decision, or audit-release capability.  It cannot admit or restore state and does not recursively require its own transition receipt. |
| `audit_release_capability` | Distinct disclosure-purpose capability kind binding the block, evaluator commitment, Permit policy, authorization, capability, and revocation chain.  Production currentness still requires independently authenticated authority/time evidence. |
| `audit_release` | Purpose- and block-scoped delayed disclosure binding the hidden outcome, escrow, four probe trajectories, four probe outcomes, and the distinct audit-release capability plus its authority chain. |
| `block_evidence_manifest` | Schema anchor for later exact-set content closure.  The present schema fixes block/assignment, trajectory/probe/audit, three revision receipts, one rollback receipt, and one restore; calls, provider/Permit records, raw blobs, lifecycle adapters, and source/build descriptors still require a semantic actual-byte manifest validator. |
| `block_seal` | Terminal schema atom requiring the evidence manifest, audit release, block/assignment, and four probe outcomes.  The later semantic validator must classify a missing effect receipt or descriptor as incomplete and not sealable. |

The main-effect atom references the same-batch `capability_consumption`.  The
consumption atom does not point back to the effect atom; its canonical payload
must instead be checked by the semantic layer against the complete command
intent.  This direction records that the state effect used a consumed
authority without creating a reference cycle.
The same rule applies to evidence sealing: the receipt or release references
the same-batch `evidence_seal_consumption`.

Schema structure alone cannot prove branch semantics.  A separate semantic
validator must require exactly one admission-or-rollback decision reference on
each effect consumption and must reject mismatched decision/effect/receipt
tuples.  It must likewise require a receipt's decision or an audit release's
release capability to equal the purpose referenced by its evidence-seal
consumption; the generic typed-reference schema proves kinds and cardinalities,
not equality between two cross-atom paths.

## Four effect CASes and their post-commit observations

A complete block has four state-changing durable CASes:

1. ACTIVE admission;
2. OUTCOME_INDEPENDENT_SHAM admission;
3. EXACT_W0_ROLLBACK staging admission; and
4. EXACT_W0_ROLLBACK restoration.

DELAYED_NO_CREDIT has no state-changing CAS.  Its proposal is quarantined and
must not enter a behavioral projection.

Each effect follows the same three-layer shape:

```text
pre-state decision
  -> one atomic main CAS {effect capability consumption, effect atom}
  -> recovered durable journal record
  -> one atomic non-effect seal CAS {evidence-seal consumption, post-commit receipt}
```

The three admissions produce exactly three
`revision_transition_receipt` atoms.  The restore produces exactly one
`rollback_transition_receipt`.  The receipt payload binds the preceding main
CAS's exact schema hash, command/write descriptors, transition ID, journal
lineage and record descriptor, prior/next revisions, state hashes, and journal
head.  It never includes the journal descriptor of its own sealing command;
doing so would create an impossible self-hash.

The lifecycle remains the preserved 59-row R2 chronology.  Its three
`TRANSITION_RECEIPT` rows project the three revision receipts.  Its one
`RESTORE_TRANSACTION` row requires an explicit adapter binding the main-CAS
`restore_transaction`, its main consumption, and the fourth post-commit
rollback receipt.  No extra lifecycle row or responsibility owner is invented.

## Transaction/batch chronology

The successor transaction primitive receives the exact successor schema,
pre-state, and one generic commit command.  It must:

- require every external typed or provenance source to exist in the pre-state
  and in the command read set;
- permit typed and provenance sources within the same write batch;
- reject duplicate/logically duplicate writes, self edges, missing sources,
  cross-batch forward references, and dependency or provenance cycles;
- derive an array-order-independent topological order, breaking ties with the
  canonical atom-key order;
- emit the exact ordered key list and its canonical content hash; and
- require the unchanged generic evolution kernel to accept the same command.

That graph primitive is necessary but not sufficient.  A protocol validator
must additionally recognize these phases and exact write grammars:

```text
PRECOMMIT_DECISION
EFFECT_CAS_ADMIT       = capability_consumption + macro_disposition
EFFECT_CAS_RESTORE     = capability_consumption + restore_transaction
POSTCOMMIT_RECEIPT     = evidence_seal_consumption + matching receipt
DELAYED_AUDIT_RELEASE  = evidence_seal_consumption + audit_release
BLOCK_EVIDENCE_SEAL    = block_evidence_manifest + block_seal
```

It must bind every post-commit receipt to a recovered preceding effect record,
enforce exact block/arm scope, and prevent behavior projection or probe dispatch
until all receipts required for that arm are durably sealed.

## Crash, replay, and idempotency semantics

A crash after the main effect CAS but before receipt sealing does not authorize
rerunning the effect.  The block is `INCOMPLETE`, and probe dispatch and block
seal are forbidden.  Recovery may only:

1. recover and independently validate the already-committed main journal
   record;
2. derive the deterministic receipt UID from that record descriptor and
   transition identity; and
3. idempotently submit the one matching receipt-seal command.

A conflicting receipt, changed journal descriptor, reused nonce, second effect
submission, or a receipt for an uncommitted command fails closed.  Receipt-seal
commands are explicitly non-effectful evidence admissions and are exempt from
recursive receipt generation.

## Information-flow requirements

The typed schema is not a noninterference proof.  The successor semantic layer
must independently show that:

- SHAM proposal, credit, authorization, effect, and projection paths contain
  placebo/allowed public inputs and no hidden-outcome-derived path;
- DELAYED paths bind escrow/no-admission status and cannot reach the genuine
  hidden outcome before all probe responses are sealed;
- ACTIVE and rollback admission paths bind the genuine allowed outcome
  projection under the declared capability;
- receipt, decision, audit, proposal transcript, and staging-only atoms are not
  traversable through a fresh-probe behavior projection; and
- `audit_release` uses a purpose-scoped disclosure capability, not an unrelated
  generic capability record.

## Exact block evidence closure

For a complete block, the manifest must require exactly three revision receipts
and exactly one rollback receipt.  It must also content-bind and independently
rederive exact sets, not merely list selected typed refs:

- every admitted successor-schema atom envelope and payload descriptor;
- all four effect-CAS and all post-commit seal journal records;
- all 15 lifecycle seals and 59 row-to-atom/derived-slot adapters;
- the W0/four-fork and four-arm assignment closure;
- the complete nine-call plan and observed provider gateway ledger;
- all model-visible request and response bytes, evaluator/placebo/escrow bytes,
  Permit inputs/resolutions, authorization and revocation observations;
- schema, source tree, selected build, import/call graph, runtime, and content
  store roots; and
- explicit per-block versus study-global support-atom cardinalities.

The independent judge must reject any missing or extra descriptor, swapped arm
or fork, changed raw byte blob under a still-valid lifecycle seal chain, wrong
receipt cardinality, or valid atom graph paired with a different provider or
journal record.

## Current checked implementation evidence

The successor identity is implemented as
`hswm:dnrd5:causal-macroplasticity:v2` with 44 schema-approved kinds and
exactly one schema-relative responsibility owner per kind.  Its canonical
schema-content serialization is 31,298 bytes with SHA-256
`a921264c5d1b5d9186d291e6a17ddc0282ce4eaa8832b1a599b7237c23d4b357`.
The v1 identity, 37-kind universe, and schema-content SHA-256
`03c44dec6907d16955927a2ab2886c03db97f1dd5746bc5f343ce853864592a0`
remain unchanged.

The atomic-batch chronology instrument now independently:

- validates the exact v2 schema and delegates generic invariants to the
  unchanged Canonical Atom V2 evolution kernel;
- permits same-command typed and provenance dependencies while requiring each
  external dependency in both pre-state and read set;
- rejects duplicate writes, reads, and typed references, self/future/missing
  dependencies, and dependency cycles; and
- derives an array-order-independent topological order and a hash over its
  exact sorted typed/provenance edges.

A record-bound main-effect verifier now accepts actual canonical schema,
pre-state, command, journal commit, record bytes, record descriptor, and write
envelope bytes.  For both ADMIT and RESTORE grammar it recomputes the batch,
generic accepted receipt, immediate predecessor/state hashes, sorted write
bindings, exact envelopes, journal replay, resulting state, canonical record
bytes, and record descriptor.  Its success terminal is deliberately
`RECORD_BOUND_EFFECT_VALIDATED_NOT_PERMIT_OR_OCCURRENCE`.

The effect grammar additionally equates the consumption's grant, capability,
and revocation to the selected decision's authority chain.  ADMIT equates the
decision proposal and same-batch disposition/consumption, and closes its
block/assignment/four-fork/W0, trajectory contract, evaluator, committed probe,
and randomness scope.  RESTORE equates the rollback decision's W0, restore
policy, grant, staging successor, and same-batch restore/consumption.
Schema-valid alternate authority, proposal, W0, policy, staging, subject, and
decision cross-wires are rejected rather than merely failing a kind check.

Both this verifier and the declared trace instrument use the same
`hswm-dnrd5-v2-postcommit-receipt-identity/v1` derivation over the effect-record
descriptor SHA, journal lineage, transition, decision, effect consumption, and
effect atom keys.  The shared hash prevents two incompatible local receipt UID
formulas; it does not prove record custody or receipt admission.

A raw postcommit receipt-seal verifier now revalidates the exact preceding
main-effect input, immediate record descriptor, lineage and resulting state;
recomputes canonical receipt payload bytes and its content descriptor; equates
the receipt decision/effect tuple and evidence purpose; equates the evidence
authority triple to that decision; replays the two-write journal command; and
recomputes its record bytes and descriptor.  A single chronological fixture
covers both ADMIT-to-revision-receipt and RESTORE-to-rollback-receipt paths.
Schema-valid alternate decision, effect, and authority cross-wires fail closed.
Its terminal remains `RAW_RECEIPT_SEAL_VALIDATED_NOT_PERMIT_OR_OCCURRENCE`.

A raw delayed-audit-release verifier likewise replays exactly
`{evidence_seal_consumption, audit_release}`.  It equates release purpose,
block, assignment, hidden-outcome/escrow chain, evaluator and release authority
chains, sealed-trajectory contract/W0, block randomness, and the bijective four
trajectory/outcome/evaluator-release closure over four distinct probe
commitments.  It still cannot establish delayed timing, custody, arm semantics,
or an actual provider event.

The v1-to-v2 lifecycle adapter pins both immutable source hashes and the exact
v2 schema hash.  It reconstructs all 46 direct rows plus four assignment, four
arm-transition, four probe, and one audit derived adapter rows; equates every
directly resolvable fork/validation/credit/receipt/restore/projection/outcome
link; and derives the exact 16-kind v2 support closure.  Its remaining staging,
consumption, disposition, rollback-receipt, probe-trajectory, and audit-release
values are deliberately opaque unique handles, not atom keys or byte evidence.
Only the actual-byte corpus judge may resolve those handles to canonical atoms.

A separate four-effect trace instrument checks the declared three-admission
plus one-restore partial order and deterministic future receipt identity.  It
only compares caller-supplied trace fields and therefore terminates at
`DECLARED_TRACE_CONSISTENT_ONLY`; it is not independent raw-record evidence.

These instruments do **not** yet validate a durable replay registry, full
predecessor-chain custody, raw content payload closure, exact block/arm
semantics, the manifest/block-seal record, Permit, provider/model dispatch,
occurrence, learning, or efficacy.  Each effect, receipt, and audit invocation
must now supply its bounded used-record-descriptor scope explicitly, but that
scope remains a local consistency input rather than a globally one-shot
registry.

## Evidence boundary and next gate

Implementing and testing this successor schema and chronology establishes only
that the intended transaction semantics are represented and falsifiable.  It
does not establish production byte closure, custody, independence, occurrence,
causal learning, utility, or efficacy.  No research-result receipt or
`F1_R8_RESULTS_LOG.md` entry is warranted.

The schema, batch graph, main-effect, postcommit receipt, delayed-audit, and
lifecycle-adapter slices have passed focused structural and mutation checks.
The next gate is the manifest/block-seal record inside the one-block
production-shaped fixture-byte corpus and its independently implemented judge,
under the frozen contract in
[`HSWM_DNRD_5_ONE_BLOCK_ACTUAL_BYTE_CORPUS_2026-08-28.md`](HSWM_DNRD_5_ONE_BLOCK_ACTUAL_BYTE_CORPUS_2026-08-28.md).
Source A remains forbidden until that byte closure and later source/build and
sole-dispatch qualifications pass.
