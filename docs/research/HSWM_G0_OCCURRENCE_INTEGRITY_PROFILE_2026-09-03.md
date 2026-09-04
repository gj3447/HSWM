# HSWM G0 external occurrence-integrity profile

> **Status:** `DRAFT_SUCCESSOR / ENGINEERING_COMPONENTS_IMPLEMENTED /`
> `NOT_PREREGISTERED / NOT_EXECUTED / G0_NOT_PASSED / G1_LOCKED`
>
> **Date:** 2026-09-03
>
> **Target authority:** [HSWM Constitution](../canon/HSWM_CONSTITUTION_2026-08-20.md)
>
> **Research order:** [Adaptive research strategy](../canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md)

## 1. Decision and conceptual delta

This profile defines a fail-closed, external occurrence-integrity boundary for
the prospective G0 future-outcome successor.  It makes a future occurrence
auditable only if its protocol registration, signed package, public timestamp,
singleton claim, one-shot orchestration, pre-pulse actor material, public
randomness, independent reveal, and two evaluator receipts are connected by
typed content descriptors.

It does **not** change Atom v2, canonical ownership, Permit, causal admission,
credit assignment, or learning.  It is not a new HSWM subsystem.  The modules
are bounded adapters and projections around a prospective research occurrence;
they cannot make external services run, prove role independence, establish
outcome truth, or promote a locally constructed value into a scientific result.

The target identity remains one token-native LLM-function macro-neural network
whose evolving hypergraph is its living harness, world model, and continuous
learner.  Current evidence has not changed.  In particular, this profile is
not CF-07, not G0, not G1, not canonical learning evidence, and does not alter
the fractal status `SCIENTIFICALLY_CONNECTED / INTEGRATED_CLAIM_UNJUDGED`.

## 2. Required occurrence sequence

One real occurrence has this exact order.  The external WORM conditional
create is only a singleton candidate until an independent audit confirms
versioning, Object Lock retention, conditional-write enforcement, and policies
that close overwrite, delete-version, and delete-marker paths.  Temporal is
only an orchestration adapter.

```text
OSF preregistration immutable readback
  -> in-toto Statement v1 in DSSE envelope
  -> Rekor inclusion and RFC 3161 token verification
  -> separate-account WORM occurrence-UID conditional claim
  -> Temporal workflow with reject-duplicate and maximum-attempts = 1
  -> actor request, response, and action material sealed before pulse
  -> exact drand Quicknet pulse BLS verification
  -> independent custodian post-pulse mapping/reveal
  -> evaluator A and independently controlled evaluator B
  -> identical fixed input, normalized binding, and score
  -> non-publishable PENDING_EXTERNAL_AUDIT candidate receipt
  -> Temporal SEALED transition bound to that receipt digest
  -> qualified external auditor exports the complete Temporal history, binds a
     typed terminal audit receipt to it, and signs the exact completion-audit
     manifest; pinned Cosign verifies it
  -> final SEALED receipt; any disagreement or invalid transition: VOID
  -> terminal receipt plus RO-Crate and OpenLineage projections
```

The signed registration package fixes the protocol, one exact future pulse,
task/action roster, analysis, holdout, and arm schedule before outcome
inspection.  It must be read back from the registration service byte-for-byte.
The OSF file metadata self URL and its exact API-provided `links.download`
WaterButler URL are distinct bindings; the latter must be an HTTPS
`files.osf.io` URL and supplies the bytes used for the digest comparison.
The DSSE statement binds that package descriptor; the Rekor and RFC 3161
receipts each bind the DSSE receipt descriptor.  A timestamp alone is not role
proof, outcome proof, or independence proof.

### 2.1 Descriptor-only external handoff

Before credentials, endpoints, private assets, or external receipts are
exchanged, the local operator emits a canonical descriptor-only handoff
candidate for the planned occurrence UID:

```bash
uv run --locked hswm-g0-occurrence \
  external-handoff-template <occurrence-uid>
```

The handoff candidate binds the exact toolchain-candidate record and exposes
null slots for the protocol package, nine role bindings, every required
external binding, the DGX execution surface, the private lineage-disjoint
holdout, and the full operator-return chain from OSF readback through the final
terminal receipt.
The underlying identities, endpoints, credentials, private data, and receipts
remain outside the repository; only their content descriptors may populate the
handoff.

An external operator may return populated canonical bytes for structural
checking:

```bash
uv run --locked hswm-g0-occurrence \
  external-handoff-validate <handoff.json>
```

Both the empty template and every structurally valid populated handoff remain
`BLOCKED_EXTERNAL`.  Validation checks canonical bytes, the exact candidate
record digest, frozen slot coverage, descriptor shape, and declared role-
descriptor distinctness only.  It always reports external independence, live
execution readiness, and G0 passage as false.  A handoff therefore cannot
replace the external qualification record, signed receipts, service readbacks,
or the later gate decision.  The authoritative integrity and completion gates,
not this inventory, must subsequently verify every returned descriptor's exact
occurrence, protocol, chronology, and predecessor bindings.

The WORM singleton candidate uses the exact object key
`occurrences/<occurrence_uid>/claim.json`, `If-None-Match: *`, Compliance
retention, an immutable bucket policy descriptor, and separate claimant and
administrator identities.  A duplicate UID, retry, replacement round,
out-of-order event, late pre-pulse material, malformed descriptor, role
collision, evaluator disagreement, or unverifiable external receipt is never
reinterpreted as success.  It ends the same occurrence as `VOID` or leaves it
`BLOCKED_EXTERNAL` / `INCONCLUSIVE_EXTERNAL_VERIFICATION_REQUIRED` until an
external audit can decide the evidence.

Temporal's local `SEALED` phase is only a workflow transition label.  It is
not publication eligibility and cannot be consumed as outcome success without
the typed completion boundary's integrity and dual-evaluator agreement checks.
The completion boundary first emits a non-publishable
`PENDING_EXTERNAL_AUDIT` receipt.  A subsequent Temporal `SEALED` transition
must end its evidence chain in that exact candidate-receipt digest.  The final
completion call then re-runs the repository-qualified, artifact-pinned Cosign
verifier over a canonical audit manifest that binds the candidate, the full
terminal workflow history, the complete Temporal history export, its typed
terminal audit receipt, and the completion timestamps.  The history must begin
with `WorkflowExecutionStarted`, end with `WorkflowExecutionCompleted`, have
strictly increasing event IDs, and agree with the occurrence UID, workflow ID,
run ID, candidate digest, workflow digest/evidence, one-shot options, server
identity digest, signal-authorization-policy digest, and chronology.  This is a
qualified-auditor assertion over an exported history, not a Temporal-native
signature.  The completion boundary does not accept a caller-declared
`verified` value or an in-process capability as authorization.

The implementation's trust boundary is explicit: the installed HSWM package,
the repository-fixed qualification record, the qualified Cosign executable and
trusted-root bytes, and the isolated completion process are trusted computing
base.  External JSON, filesystem paths, workflow signals, and API callers are
untrusted inputs.  Python constructors and private module names are invariant
guards, not an authentication boundary; code that can replace the installed
package, its qualification record, or the completion process already controls
the trusted computing base and is outside this adapter's threat boundary.
Production deployment must therefore make those inputs read-only and admit
Temporal signals only through its separately authenticated authorization
policy.  The worker cannot prove signal-sender identity from signal payloads.

The actor seal contains descriptors for each raw request, response, and chosen
action.  The drand pulse is verified under the existing pinned Quicknet
boundary; it is public entropy, not a custodian or evaluator.  The custodian
reveals only after the pulse, using a distinct control domain.  Evaluator A and
B must use distinct implementation descriptors, receive the same declared
input, independently produce the same score, and provide signed evidence.  A
matching pair is necessary, not sufficient, for a G0 pass.  The normalized
dual-evaluation binding covers each evaluator's role, task, scorer,
configuration, implementation, exact input and output descriptors, score,
signed envelope, and cryptographic verification receipt; the central
integrity check and independent dual-evaluator bridge must compute the same
binding digest.

Terminal RO-Crate 1.3 and OpenLineage RunEvent projections publish both
`SEALED` and `VOID` occurrences.  `BLOCKED` and `PENDING_EXTERNAL_AUDIT` are not
publishable.  The RO-Crate root includes its terminal publication date and an
explicit no-license-granted notice; every artifact descriptor includes its
SHA-256 digest.  Before either projection is emitted, the publication boundary
replays the complete completion inputs, repeats the qualified Cosign audit for
`SEALED`, compares the canonical receipt byte-for-byte, and requires exact
terminal-receipt and audit-verification artifact metadata.  A caller-created
self-hashed receipt is therefore not publication authority.  Those projections
are export views only; they do not create a canonical atom, evidence admission,
or promotion path.

## 3. Implemented bounded components

| Component | Local module | Exact responsibility | Explicit non-responsibility |
|---|---|---|---|
| Integrity contract | `src/hswm/infrastructure/occurrence_integrity.py` | Typed descriptors, chronology, role-separation, and dual-evaluator consistency checks | External verification, outcome judgment, canonical write, Permit, learning |
| One-shot state machine | `src/hswm/infrastructure/occurrence_workflow.py` | Ordered fail-closed phases, terminal-first immutable `VOID`/`SEALED` handling, and one-shot launch options | Running Temporal or preventing a remote duplicate by itself |
| TypeScript/Effect phase-kernel candidate | `src/hswm/effect-runtime/src/g0-occurrence-phase-kernel.ts` | Strict internal ingress, module-issued immutable phase projection, one-shot policy binding, 11-case Python transition-result parity, and blocked typed terminal-receipt ports | Python wire parity, deadline/queue execution, live Temporal, completion handshake, durability, G0, or learning |
| Temporal SDK adapter | `_research/g0_occurrence/occurrence_temporal_worker.py` | Official `temporalio==1.32.0` signal-driven worker, WORM-bound start, reject-duplicate ID, one-attempt policies, and mandatory content-addressed external signal-policy binding | Enforcing that external policy, claiming the UID, supplying evidence, or proving that a production workflow ran |
| Preregistration readback | `src/hswm/infrastructure/occurrence_registration.py` | Strict, read-only OSF API v2 readback parsing and registration/package binding | Creating an OSF registration or authenticating to OSF |
| DSSE and timestamp commands | `src/hswm/infrastructure/occurrence_attestation.py` | in-toto Statement v1, DSSE shape parsing, pinned-binary command construction | Signing, network submission, or treating parsed DSSE as cryptographically verified |
| WORM claim contract | `src/hswm/infrastructure/occurrence_worm.py` | Conditional S3 claim command construction and fail-closed response classification | Provisioning a bucket, validating a live policy, or guaranteeing remote retention |
| Presence-only preflight | `src/hswm/infrastructure/occurrence_preflight.py` | No-secret readiness report for required bindings and candidate binaries | Credentials, artifact integrity, authorization, or proof of independence |
| External handoff | `src/hswm/infrastructure/occurrence_handoff.py` | Canonical descriptor slots connecting one planned occurrence to the exact external inputs and return-artifact checklist | Moving secrets or private data, verifying external facts, proving independence, authorizing execution, or passing G0 |
| Dual evaluation | `src/hswm/evaluation/occurrence_dual_evaluator.py` | Bind Inspect A and a distinct blinded evaluator B to exact input and decision/score descriptors | Running either evaluator or trusting caller-declared signature status as final audit |
| Completion boundary | `src/hswm/infrastructure/occurrence_completion.py` | Recompute integrity and A/B bindings, bind the exact seven-step workflow history, issue a non-publishable candidate, validate the typed terminal receipt/complete Temporal history, and verify the signed terminal audit with the fixed qualified Cosign/root before final admission | Running Temporal, operating or qualifying the auditor, judging outcome truth, or promoting G0 |
| Publication projections | `src/hswm/infrastructure/occurrence_publication.py` | Replay completion and qualified audit verification, then deterministically project RO-Crate and OpenLineage terminal views | Running external services, scientific interpretation, or promotion |
| Local operator CLI | `src/hswm/infrastructure/occurrence_cli.py` | Deterministic descriptor, statement, DSSE shape, one-shot option, command-construction, and preflight commands | Any external write, signature, workflow, evaluation, terminal-receipt import, or publication action |

The profile reuses `src/hswm/experiments/g0_future_outcome.py` for the fixed
future-outcome commitment/action-seal contract and
`src/hswm/experiments/swm0w_beacon.py` for the exact Quicknet verifier.  It
does not replace their claim ceilings.  `inspect-ai==0.3.260` remains only the
Evaluator A framework preflight until a fixed task and scorer are supplied.

The Effect phase kernel is a migration candidate, not a second authoritative
execution contract. Python remains authoritative for a live occurrence until
strict raw-wire mapping, deadline and signal-queue behavior, completion-audit
equivalence, durable recovery, external qualification, and independent review
close the cutover gates recorded in
[`HSWM_G0_EFFECT_PHASE_KERNEL_BOUNDARY_2026-09-04.md`](../operations/HSWM_G0_EFFECT_PHASE_KERNEL_BOUNDARY_2026-09-04.md).

## 4. Standard and toolchain candidates

The source-pinned discovery record is
[`HSWM_G0_OCCURRENCE_TOOLCHAIN_CANDIDATES.v1.json`](../../_research/g0_occurrence/HSWM_G0_OCCURRENCE_TOOLCHAIN_CANDIDATES.v1.json).
It records authority class, source commit, version, license, and adoption
state.  Every listed executable has `artifact_integrity: null`: none has been
downloaded, artifact-digest pinned, isolated-qualified, or adopted here.

| Boundary | Published authority | Candidate selected for later qualification |
|---|---|---|
| Registration | [OSF API v2](https://developer.osf.io/) | Official service readback only; no local registration client or credential is selected |
| Attestation | [in-toto Statement v1](https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md), [DSSE v1](https://github.com/secure-systems-lab/dsse/blob/master/envelope.md) | Strict HSWM statement/envelope subset; Cosign `v3.1.3`, source `11926fa5bbbbde47e88fc006b625a17769b743b2`, explicit trusted-root verification, Apache-2.0 |
| Transparency and time | [RFC 3161](https://www.rfc-editor.org/rfc/rfc3161) | Rekor `v1.5.4`, source `a36bd716fd0d81c314092718f37b53dc26b2af38`; Sigstore timestamp authority `v2.1.3`, source `811e94a148b97b90c638f58224d70d59da0c8b55`; OpenSSL `3.5.6`, source `286ddeaac037533bbdce65b3c689e3f7ffebf0f6`; all Apache-2.0 |
| Singleton claim | [Amazon S3 Object Lock](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html) | AWS CLI `2.36.36`, source `7f6739b0c29553c6524059b9ab0eadaf35939030`, Apache-2.0 |
| One-shot orchestration | Temporal vendor interface | Temporal CLI `v1.8.3`, source `1ff10b1012b44ba8bc953fcaa8ce5d296bf169d0`; official Python SDK `1.32.0`, source `fc6f97a487ed61df9ca5802adb66d8adfcb6df0f`, isolated lock `9d0ec5d9cca2a5a99358bbc0b3349bd3f057d23a757bc5b9620353a47d6ab229`; MIT |
| Publication | [RO-Crate 1.3](https://w3id.org/ro/crate/1.3), [OpenLineage RunEvent 2.0.2](https://openlineage.io/spec/2-0-2/OpenLineage.json) | Format projections only; custom facet schemas are frozen at repository commit `6108410a90f5caf8b367bb1fce5282c96744d24e`; no runtime is selected |

These candidates are not standards authorities merely because an HSWM adapter
can invoke them.  Before a live occurrence, each downloaded binary, image, or
package must have its exact platform artifact digest, source revision,
license bytes, trust root, capability allowlist, and isolated smoke test
recorded.  A third-party implementation must be qualified against the official
format or conformance surface and labeled as independent implementation.
The checked-in completion-auditor gate is
[`HSWM_G0_EXTERNAL_AUDIT_QUALIFICATION.v1.json`](../../_research/g0_occurrence/HSWM_G0_EXTERNAL_AUDIT_QUALIFICATION.v1.json).
It is deliberately `BLOCKED`; only a separately produced qualification receipt
may populate its exact Cosign artifact/license digests, trusted-root bytes, and
auditor identity/issuer.  Rekor inclusion verification also remains an
external evidence boundary; the local attestation module does not claim to be
an independently qualified Rekor verifier.

## 5. External prerequisites and handoff

The current host has no live registration, Sigstore, TSA, WORM, production
Temporal, custodian, evaluator-B, DGX, or private lineage-disjoint holdout
binding.  It therefore must not perform a scientific occurrence.  The
presence-only preflight intentionally returns a block rather than accepting
local substitutes.

The designated external operator must supply and independently audit all of
the following before authorizing a live run:

1. an OSF account and immutable registration/package readback;
2. role-specific signing identities, pinned Cosign artifact, immutable
   Sigstore trusted-root bytes, Rekor inclusion verification, TSA trust root,
   nonce, and verified RFC 3161 token;
3. a separate-account, versioned S3 Object Lock Compliance bucket; a policy
   that requires conditional create and denies deletion/retention weakening;
   and verified claim, object-version, retention, and policy readbacks;
4. a production Temporal namespace/server with a one-shot worker deployment
   that preserves the generated reject-duplicate and one-attempt options, plus
   an independently enforced signal-authentication/authorization policy and a
   content-addressed complete history export and terminal audit receipt;
5. distinct actor, revision-proposer, occurrence-claimant, WORM-admin,
   custodian, drand-verifier, evaluator-A, evaluator-B, and completion-auditor
   subjects, accounts, admin domains, and key references as required by the
   integrity contract;
6. an independently operated custodian endpoint/key, a second evaluator
   implementation/control domain, and a completion-auditor qualification
   record binding the exact Cosign artifact and license digests, immutable
   Sigstore trusted root, auditor identity/issuer, and qualification receipt;
   the checked-in record remains `BLOCKED` until those facts exist; and
7. the DGX execution surface plus the fixed, sealed, lineage-disjoint holdout
   assets, evaluator task/scorer, and prospective protocol values.

No credential, endpoint value, private dataset, model artifact, or external
receipt is checked into this repository.  The future external adapter may use
the local command builders only after its immutable artifact pins and
capability allowlist are recorded.  It must write its receipts to the declared
external evidence store, then return descriptors for independent verification;
it must never be a generic canonical-write, Permit, causal-admission, or
learning route.

## 6. Local engineering verification

The following verifies only the deterministic local contracts.  It neither
contacts an external service nor executes a prospective scientific occurrence.

```bash
uv run --locked --extra dev pytest -q \
  tests/test_occurrence_cli.py \
  tests/test_occurrence_dual_evaluator.py \
  tests/test_occurrence_completion.py \
  tests/test_occurrence_integrity.py \
  tests/test_occurrence_workflow_parity_vectors.py \
  tests/test_occurrence_workflow.py \
  tests/test_occurrence_registration.py \
  tests/test_occurrence_attestation.py \
  tests/test_occurrence_worm.py \
  tests/test_occurrence_preflight.py \
  tests/test_occurrence_handoff.py \
  tests/test_occurrence_publication.py \
  tests/test_occurrence_temporal_worker.py \
  tests/test_occurrence_toolchain_candidates.py
uv run --script _research/g0_occurrence/occurrence_temporal_worker.py \
  --locked --help
uv run --locked hswm-g0-occurrence preflight
cd src/hswm/effect-runtime
npm run check
npx vitest run test/g0-occurrence-phase-kernel.test.ts
```

## 7. Claim ceiling and stop rule

The only current result is `ENGINEERING_COMPONENTS_IMPLEMENTED`.  The required
status remains exactly:

```text
NOT_PREREGISTERED
NOT_EXECUTED
G0_NOT_PASSED
G1_LOCKED
```

Even a locally passing test suite, a syntactically valid DSSE envelope, a
candidate binary version, a generated RO-Crate, or a matching evaluator pair
cannot change that status.  A valid negative result retires or reroutes its
exact mechanism family with evidence lineage intact; it does not shrink the
target, weaken a success criterion, rename failure, or allow downstream scale
to rescue an upstream integrity failure.
