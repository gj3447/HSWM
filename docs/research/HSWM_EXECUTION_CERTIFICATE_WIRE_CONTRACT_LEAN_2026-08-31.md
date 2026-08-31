# HSWM structural execution-certificate wire contract

> **Status:** `SECONDARY_AI_FORMAL_BOUNDARY / RECORD_DIGEST_CYCLE_REMOVED / TYPESCRIPT_RAW_BYTE_STRUCTURAL_CHECKER_PRESENT / SOURCE_LEVEL_REFINEMENT_AND_RUNTIME_OCCURRENCE_UNPROVED / SCIENTIFIC_UNJUDGED`
>
> **Target authority:**
> [`HSWM Constitution`](../canon/HSWM_CONSTITUTION_2026-08-20.md)
> and the target-preserving
> [`adaptive research strategy`](../canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md)
>
> **Formal artifact:**
> [`HSWMExecutionCertificateWire.lean`](../../formal/HSWMExecutionCertificateWire.lean)
>
> **Predecessor boundaries:**
> [`end-to-end runtime refinement`](HSWM_END_TO_END_RUNTIME_REFINEMENT_LEAN_BOUNDARY_2026-08-31.md)
> and
> [`canonical Permit authentication envelope`](HSWM_CANONICAL_PERMIT_AUTHENTICATION_ENVELOPE_2026-08-31.md)

## 1. Canonical role and conceptual delta

The target role is one evidence-bearing transition of the same evolving HSWM,
not a new certificate subsystem that stands outside it. A certificate is a
bounded projection of what one transition claims happened: its pre-execution
intent, exact Permit/invariant bindings, declared commit, and recovered
successor. It is not cognition, routing, outcome judgment, causal credit or
learning by itself.

Before this boundary, `ClaimedConcreteExecutionEvidence` could be supplied as
an unconstrained Lean record whose fields already included exact issue,
commit, ordering and uniqueness proofs. The Permit-envelope checker separately
compared its claims with a free-standing expected-binding record. Nothing
forced those expected bindings to be derived from the same certificate body.

This boundary makes the following conceptual change:

1. one pre-execution intent manifest is the source of the execution, head,
   target, revision, policy and nonce context;
2. the expected Permit-envelope bindings are derived from that manifest, not
   accepted as a separate arbitrary record, and the checker then requires the
   certificate's Permit/invariant projections to equal those intent bindings;
3. one structural checker requires the Permit issue, invariant certificate,
   commit witness, successful-commit list and recovery order to agree with that
   same context; and
4. checker acceptance constructs `ClaimedConcreteExecutionEvidence`, while a
   separately named semantic supplement remains mandatory before constructing
   `ClaimedRuntimeAdmissionCertificate`.

The fourth separation is essential. Raw fields cannot manufacture a runtime
occurrence, a state abstraction, `Inv`, outcome truth, causal identification or
LLM behavior.

## 2. Cycle-free evidence graph

The normative dependency direction is:

```text
canonical execution-intent body bytes
  -> execution-intent digest
  -> canonical Permit signing document and detached signature
  -> Permit envelope descriptor

typed signature-independent commit-plan core bytes
  -> planned successor-head commitment

pre-state + Permit envelope + invariant certificate + commit/recovery evidence
  -> execution-certificate body bytes
  -> execution-certificate descriptor/digest
```

Four exclusions prevent digest cycles:

- the execution-intent body contains neither its own digest nor the final
  execution-certificate digest; and
- the execution-certificate body contains neither its own digest nor a field
  whose digest recursively includes the certificate; and
- the signature-independent commit plan contains only the successor lineage,
  sequence and state digest. It does not contain the successor record digest
  that is computed from the plan bytes; and
- the invariant-certificate `contentDigest` names external invariant
  input/content bytes, not bytes of the certificate that contains that digest.

This is a syntactic decoded-field guarantee. The TypeScript raw codec follows
the same ordering in its successful vector, but Lean still does not prove that
the external serializer or digest adapter has no hidden dependency on the
final descriptor for every program execution.

The post-execution `certificateDigest` in `RuntimeExecutionTrace` is supplied
by `WireDigestAdapters.certificateDigestOf`. An external certificate descriptor
stays outside the body, and structural acceptance requires its digest to equal
that adapter result. The current Lean model does not prove that either value
was computed from raw bytes. The future codec must compute both from the final
certificate-body bytes. The Permit signs the pre-execution intent digest,
never the post-execution certificate digest.

The Permit envelope carries an `expectedNextHead.recordDigest`.
`SignatureIndependentCommitPlanWire` is the typed record-independent core and
has no Permit envelope, signature, intent digest, final certificate digest or
successor record digest field.
It uses contract version `hswm-signature-independent-commit-plan/v1` and the
literal
`SIGNATURE_INDEPENDENT_COMMIT_PLAN_NOT_PERMIT_ENVELOPE_NOT_CERTIFICATE`.
The intent names its bytes before signing; the certificate later requires the
recovered typed core and descriptor to equal that plan. A future full journal
wrapper may refer to the Permit envelope out of line, but it is not modeled by
this Lean boundary and is not the head-bearing core. Before such a wrapper is
accepted, a later codec boundary must give it its own descriptor and binding.
Its digest is the value later placed in `expectedNextHead.recordDigest`. A core
that embeds either that successor record digest or the Permit signature would
be circular and must be rejected. Lean proves
`successorProjectionIgnoresRecordDigest`, making the exclusion explicit.

## 3. Normative wire artifacts

Every external byte artifact modeled by this boundary is referenced by an
exact descriptor:

```text
ArtifactRef := {
  mediaType,
  byteLength,
  sha256
}
```

`sha256` is the future serialized field; Lean represents it as
`digest : EvidenceDigest`. The descriptor binds bytes only after the future
raw adapter has been shown sound; a self-asserted descriptor does not establish
its own binding, provenance or truth.

The TypeScript codec now enforces an exact media type, non-negative safe byte
length and lowercase SHA-256 form. This is executable implementation evidence,
not a Lean proof of the TypeScript parser or Node SHA-256 implementation.

### 3.1 Execution-intent body

The canonical intent body is pre-execution and contains at least:

- contract version, canonicalization profile and the literal
  `PRE_EXECUTION_INTENT_NOT_PERMIT_NOT_ADMISSION_NOT_LEARNING`;
- execution identity;
- predecessor and planned-successor head commitments;
- target atom address and expected/candidate revisions;
- reserved Permit identity and digest of the unsigned Permit content;
- proposal and invariant-content digests;
- authorization reference, authorizer and scope;
- the Permit responsibility owner, invariant responsibility owner and
  invariant validator, all transitively signed through the intent digest;
- nonce digest, key-policy version and revocation epoch;
- declared Permit-issue index; and
- descriptors for the schema, pre-state, sealed trajectory, outcome package,
  proposal, authorization and invariant input whose semantics remain external;
  and
- the typed `SignatureIndependentCommitPlanWire` and its descriptor.

The formal model parameterizes the digest operation as
`WireDigestAdapters.intentDigestOf`. This states exactly which manifest the
adapter receives. The TypeScript checker implements the corresponding
canonical-JSON/SHA-256 path, but Lean still does not verify that implementation.

### 3.2 Permit envelope

The existing canonical Permit envelope remains the only signed syntax in this
slice. The execution-certificate model does not project its signature into the
older end-to-end `PermitSigningMessage`: the two currently have different
contract versions and message syntax. Treating one Ed25519 acceptance as an
acceptance of both messages would be unsound.

Instead, the structural checker invokes the existing abstract envelope checker
against `expectedEnvelopeBindings`, deterministically derived from the
execution intent. Separate structural equalities require the exact
`HeadBoundPermit`, invariant certificate, issue and commit to match that same
intent. Envelope acceptance remains caller-relative to a supplied verifier and
external trust/time booleans; this module does not add a verifier-soundness or
authoritative-key premise.

### 3.3 Execution-certificate body

The canonical certificate body contains:

- contract version and the literal
  `STRUCTURALLY_BOUND_EXECUTION_CERTIFICATE_NOT_RUNTIME_OCCURRENCE_NOT_AUTHORITATIVE_PERMIT_NOT_ATOMIC_ADMISSION_NOT_OUTCOME_TRUTH_NOT_CAUSAL_CREDIT_NOT_LEARNING`;
- the complete execution-intent manifest;
- the exact Permit envelope and exact head-bound Permit projection;
- the exact head-bound invariant-certificate projection;
- the exact declared commit witness;
- one designated Permit-issue occurrence and one designated commit occurrence;
- a decoded recovery projection containing execution identity, predecessor and
  successor heads, Permit-issue list, successful-commit list and recovery index;
- descriptors for the intent bytes, Permit-envelope bytes, invariant
  input/content, commit occurrence, pre-state, post-state, recovered
  signature-independent commit core, recovery observation and trajectory;
- an external final certificate descriptor passed beside, not inside, the
  body; and
- no embedded final certificate digest.

The artifact descriptors let the TypeScript checker receive raw bytes out of
line and hash every role before semantic checks. Canonical typed JSON roles are
then strictly decoded and compared with their certificate projections;
content-only roles such as state, trajectory, outcome and invariant input stay
opaque and are bound by exact descriptors. The invariant projection does not
self-hash: its owner and validator are bound in the signed intent, while its
head/target/revisions and external content digest are checked separately. The
current Lean file calls an abstract `ArtifactVerifier` on each exact
role/descriptor. `WireDigestAdapters` explicitly bind descriptor digests to
decoded objects or head commitments. Lean does not prove those abstractions
sound for bytes.

### 3.4 Semantic supplement

The following data and propositions are deliberately not fields whose mere
presence can satisfy structural acceptance:

- concrete runtime-step semantics and evidence that the step occurred;
- exact runtime-before/runtime-after abstraction to `CanonicalState`;
- the actual state-digest function;
- runtime-state, trajectory and outcome-package artifact bindings;
- the semantic transition invariant over `S`, proposal and `S'`;
- `AtomicAdmissionConditions`, including owner-bound outcome learning; and
- external truth, evaluator independence, causal support and LLM measurement.

Lean packages these obligations as `RuntimeSemanticSupplement`. The supplement
is not emitted by the structural checker.

## 4. Structural acceptance contract

For a certificate body `wire`, acceptance requires all of the following:

- exact contract/canonicalization/status literals and accepted role-specific
  external artifact checks;
- an external certificate descriptor whose digest equals the certificate
  digest-adapter result;
- Permit-envelope acceptance against the bindings derived from `wire`;
- one shared predecessor head across intent, Permit, invariant certificate and
  commit witness;
- one shared target and expected/candidate revision pair;
- the commit consumes the exact Permit and invariant-certificate digests;
- the Permit decision binds the proposal trace/authorization/scope, is declared
  allowed and active, and uses the intent authorizer;
- the Permit owner, invariant owner and invariant validator equal the identities
  committed inside the signed execution intent;
- the successor shares the predecessor lineage and is exactly the next
  sequence;
- the issue occurrence exactly matches the Permit and execution;
- the commit occurrence exactly matches the commit witness, execution and
  recovered successor;
- the accepted recovery projection's issue list and successful-commit list are
  exact singletons;
- every descriptor/digest mapping, including the intent, proposal, Permit
  envelope, invariant, commit, pre/post state, recovery observation and
  typed signature-independent commit-plan/recovered-core equality and exact
  descriptor equality; and
- issue index is before commit index, which is before recovery index.

These checks yield field equalities and a declared trace. They do not prove
that a filesystem, database or distributed system linearized the transition.

## 5. Lean results and proof ceiling

`HSWMExecutionCertificateWire.lean` proves three layers:

1. structural checker acceptance projects every required binding, external
   check result and chronology condition;
2. those projections construct the existing
   `ClaimedConcreteExecutionEvidence` without asking the caller to supply its
   issue/commit/order/uniqueness proofs independently; the singleton lists come
   from the accepted decoded recovery projection, not a list synthesized by
   `traceOf`; and
3. an accepted certificate plus a separate `RuntimeSemanticSupplement`
   constructs `ClaimedRuntimeAdmissionCertificate` and yields the existing
   conditional refinement proposition, including `AtomicLearnAdmission`, only
   from the supplement's explicit `AtomicAdmissionConditions`.

The third theorem is deliberately assumption-carrying. It reduces structural
freedom but does not remove the semantic premises. The module additionally
proves fail-closed obstruction lemmas for altered intent, proposal and external
certificate digests; altered consumed Permit/invariant digests; a changed
commit-plan/recovered-core binding; an altered recovered commit log; a
nonlinear successor; a rejected certificate artifact; and invalid
issue/commit/recovery order.

The formal result is a field-level checker model. It does not:

- parse TypeScript or JSON bytes;
- implement canonical JSON or SHA-256 in Lean;
- prove Ed25519 or Node/OpenSSL correct;
- prove that a TypeScript checker refines this Lean checker;
- authenticate authoritative trust, clock or key custody;
- prove nonce uniqueness or consumption;
- prove the supplied `ArtifactVerifier` or any `WireDigestAdapters` function
  sound for external bytes;
- establish an actual runtime/storage occurrence;
- prove external outcome truth or independent causal credit; or
- prove that any revision improves real LLM behavior.

## 6. Raw-byte implementation status and remaining obligations

`canonical-atom-v2-execution-certificate-wire.ts` now accepts a bundle of
certificate, intent, Permit envelope, trust context, pre/post state,
commit-plan/core and recovery raw bytes. It hash/length-checks every role,
strictly decodes canonical typed artifacts, derives Permit bindings from the
intent, checks the full decoded-field conditions and rejects structural
mutations. Its complete vector constructs the plan first, computes its digest,
and only then constructs the successor head, demonstrating that the corrected
layout is executable without a hash fixed point.

This does not finish source-level refinement. Lean has no semantics for the
TypeScript source, Effect evaluation, Node crypto, the canonical JSON parser or
the filesystem. A universal claim still requires verified extraction or a
sound formal semantics plus a proof about the compiled program. Differential
vectors and mutation tests are conformance evidence, not that theorem.

If the storage design adds an outer journal wrapper, that wrapper must first be
added to the typed contract and mutation matrix rather than silently accepted.

The adversarial matrix must independently reject:

- noncanonical, duplicate-key, invalid UTF-8, lone-surrogate, float, unsafe
  integer and excess-property encodings;
- any descriptor media-type, byte-length or SHA mismatch;
- a different execution, intent, Permit, proposal, invariant, nonce, head,
  target, revision, owner, validator, policy, epoch or issue index;
- a valid Permit envelope paired with a different intent;
- missing/duplicate issue or commit entries and invalid chronology;
- a commit consuming another Permit or invariant certificate;
- stale/discontinuous predecessor or successor heads;
- a post-state, commit core or recovery observation from another execution; and
- injected `truth`, `causalCredit`, `llmImproved` or learning claims.

A fixed cross-consumer vector must pin its known public key and every root
artifact digest outside the vector's self-asserted values. Its successful
terminal may say only that fixed structural bytes were replayed; it may not say
that a real execution occurred.

## 7. Evidence status and next step

This formal contract is routine proof/engineering work, not a material
scientific result. It creates no research receipt and leaves HSWM efficacy
`UNJUDGED`.

The next step is evidence closure, in this order:

1. add an independently implemented fixed-vector raw-byte replay;
2. give the concrete parser/checker a verified semantics or extraction path;
3. connect the complete certificate producer to the local fsync-backed,
   process-crash-tested issuer/commit occurrence rather than merely checking a
   constructed vector;
4. replace ephemeral private-key custody and caller-owned clocks with an
   audited authority and crash-recoverable key lifecycle if a production claim
   is sought; and only then
5. execute the independently owned outcome/causal/real-LLM protocol.

Until those steps produce real evidence, the checked-in positive
end-to-end-runtime profile remains false.
