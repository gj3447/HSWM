# HSWM canonical Permit authentication envelope

> **Status:** `SECONDARY_AI_FORMAL_AND_ENGINEERING_BOUNDARY / AUTHENTICATION_MECHANISM_IMPLEMENTED / ACTUAL_ATOMIC_PERMIT_OCCURRENCE_ABSENT / SCIENTIFIC_UNJUDGED`
>
> **Target authority:**
> [`HSWM Constitution`](../canon/HSWM_CONSTITUTION_2026-08-20.md)
> and the target-preserving
> [`adaptive research strategy`](../canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md)
>
> **Formal artifacts:**
> [`HSWMCanonicalPermitEnvelope.lean`](../../formal/HSWMCanonicalPermitEnvelope.lean)
> and
> [`HSWMEndToEndRuntimeRefinement.lean`](../../formal/HSWMEndToEndRuntimeRefinement.lean)
> with the independent byte/crypto replay
> [`verify_hswm_canonical_permit_vector.py`](../../formal/verify_hswm_canonical_permit_vector.py)
>
> **Runtime artifact:**
> [`canonical-atom-v2-permit-envelope.ts`](../../src/hswm/effect-runtime/src/canonical-atom-v2-permit-envelope.ts)

## 1. Canonical role and conceptual delta

The target is one current, authorizer-issued Permit for one exact candidate
transition in the same evolving HSWM. The signing key is evidence for an
authorizer action under a declared key policy; it is not the atom's
responsibility owner, the transition's invariant validator, the outcome
evaluator or the causal adjudicator.

The predecessor runtime could preserve authorization-shaped records, bounded
head checks and local durable histories, but it deliberately labeled those
records as non-canonical Permit evidence. It did not authenticate an issuer or
bind a signature to the whole transition context.

This slice adds a read-only authentication boundary:

```text
a detached signer (an external key custodian in production) signs exact canonical signing bytes
  -> TypeScript decodes the exact canonical envelope
  -> caller-supplied canonical trust bytes select one authorized active Ed25519 key
  -> caller-supplied verification time checks Permit and key validity
  -> caller-supplied expected execution/head/revision/policy/nonce bindings are compared
  -> Ed25519 verifies the exact signing bytes
  -> caller-relative receipt hashes the bindings, trust bytes and selected key
```

It does not yet install the issuer at the storage linearization point or mutate
canonical state.

## 2. Signed field set

The signature covers the signing-document tag, header, claims and nonclaim
status. The header fixes the domain, contract version, repository
canonicalization profile, algorithm, key ID and payload type. The claims bind:

- Permit and execution identities;
- a pre-execution intent digest;
- Permit, proposal and transition-invariant digests;
- the exact predecessor and expected successor heads;
- target atom address and expected/candidate revisions;
- authorization reference, authorizer and scope;
- nonce digest;
- key-policy version and revocation epoch;
- declared linearization index; and
- issue, not-before and expiry instants.

The successor must share the predecessor lineage and have exactly the next
sequence number. The candidate revision must differ from the expected
revision. All identifiers and digests pass strict Effect schemas before bytes
are signed or accepted.

The final execution receipt digest is intentionally not in the signing
message. A final receipt may contain the Permit signature, so signing the
digest of that same final receipt would create a digest cycle. The formal
runtime trace now separates a stable pre-execution `executionIntentDigest`
from the post-execution `certificateDigest`. At this slice the intent digest
is a schema-checked opaque digest field: neither TypeScript nor Lean yet
defines and independently checks a canonical pre-execution intent-byte
manifest whose hash it must equal. The split removes the direct cycle; it does
not by itself establish the semantic content of the intent digest.

## 3. Cryptographic and byte boundary

The implementation uses Node's Ed25519 operation and requires an injected
detached signer. Private-key custody is not implemented in this module and no
private key enters the returned receipt. The deterministic
[`cross-consumer vector`](../../src/hswm/effect-runtime/test/fixtures/canonical-permit-envelope-v1.vector.json)
uses the first published Ed25519 key pair from
[RFC 8032](https://www.rfc-editor.org/rfc/rfc8032.html) and pins the raw
base64url signing/envelope bytes and both SHA-256 values.
The independent replay reconstructs and canonicalizes this fixed vector with
Python and verifies its detached signature with OpenSSL rather than the
TypeScript producer or Node verifier. It is a fixed-vector byte/crypto check,
not a second implementation of the full TypeScript schema, trust policy or
admission semantics. The replay script pins the RFC test public key, both
artifact digests and the caller-relative nonclaim status independently of the
values asserted inside the vector file.

The envelope uses the repository's restricted
`hswm-canonical-json/v1` encoding: safe integers only, exact UTF-8, duplicate
key rejection, bounded depth/nodes/bytes and UTF-16 lexical key ordering. It is
not labeled RFC 8785 JCS. [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785.html)
is the relevant primary reference for why signing requires an invariant JSON
representation, but its ECMAScript number-serialization contract is broader
than this repository profile. The fixed vector can expose drift between two
consumers, but general interoperability with a second complete canonicalizer
remains unproved.

The trust snapshot is also intentionally labeled
`CALLER_SUPPLIED_TRUST_SNAPSHOT_NOT_TRANSPARENCY_LOG`. It checks an exact
policy version, revocation epoch, key identity, authorizer, validity interval
and active/revoked status. Every listed public key must decode as an Ed25519
SPKI key, including keys not selected by this envelope. It does not prove
workload attestation, key custody, clock trust, rotation publication,
certificate-chain validity or transparency.

## 4. Lean result and proof ceiling

`HSWMCanonicalPermitEnvelope.lean` is a **field-binding abstraction** of
selected TypeScript checks, not the same checker and not a TypeScript-to-Lean
refinement theorem. It models selected header/claim fields, supplied expected
bindings, next-sequence chronology, and supplied adapter outcomes. Lean
proves:

- checker acceptance projects every checked field and every accepted adapter
  result;
- the accepted execution ID, intent digest, predecessor/successor heads,
  proposal digest, invariant digest and nonce equal the expected context;
- changing the execution-intent digest or nonce is incompatible with checker
  acceptance; and
- signature meaning follows only when a separate verifier-soundness premise is
  supplied.

The abstraction also omits the TypeScript signing-document `_tag`, identifier
and SHA schemas, real UTC-instant chronology, trust-snapshot/key lookup and
the key-ID-to-public-key relation. Its `ExternalPermitChecks` booleans stand
for adapter acceptance; they do not reproduce those algorithms. The proof does
not parse TypeScript JSON, implement Ed25519 in Lean or prove Node's verifier
correct. Lean's kernel checks the theorem composition, while the
implementation-refinement bridge from raw bytes and Node crypto remains a
separate obligation. Lean proof validation can additionally be rerun with the
official independent environment checker described in the
[Lean proof-validation reference](https://lean-lang.org/doc/reference/latest/ValidatingProofs/).

The Lean envelope namespace is also not yet connected to the end-to-end
`PermitAuthenticationEvidence`, `HeadBoundPermit`, invariant certificate,
runtime execution trace or `AtomicLearnAdmission`. Therefore equality to the
supplied expected fields does not establish that they arose from one canonical
runtime transition.

## 5. Executable negative evidence

The Effect-runtime tests require the valid fixed vector to verify relative to
the supplied test trust/time inputs and then reject:

- noncanonical bytes;
- any signed-document mutation;
- mismatched execution, intent, predecessor/successor head, proposal,
  invariant, nonce, policy, epoch or linearization index;
- expired Permit time;
- unknown, revoked or unauthorized keys;
- malformed Ed25519 material anywhere in the supplied trust snapshot;
- stale/different key-policy epochs;
- invalid successor chronology; and
- malformed signer output.

The fixed vector currently pins:

- signing-document SHA-256:
  `985d0156c0687de5d3e2a908c93c9aa098932afda9673925e5478dde4ff59c80`;
- envelope SHA-256:
  `66af55c2437da2394450bc985f2979176cf44c6b6443a1886c8ed142bc83ed9a`.

These are engineering test vectors, not a material HSWM research result.

## 6. Claims not earned by this slice

The caller-relative verification result literal is
`CALLER_RELATIVE_BINDINGS_TRUST_AND_TIME_ENVELOPE_VERIFIED_NOT_AUTHORITATIVE_PERMIT_NOT_ATOMIC_ADMISSION_NOT_LEARNING`.
The signed document's own status is only a byte-bound nonclaim label; neither
literal is an authoritative Permit occurrence. In particular, this slice does
not establish:

- that a production workload with legitimate custody actually issued a Permit;
- that `executionIntentDigest` hashes a fixed canonical pre-execution intent
  manifest;
- that the supplied trust snapshot or verification time is authoritative;
- that the nonce was globally unique or atomically consumed;
- that the current head, Permit, invariant, successor write and audit append
  shared one durable linearization point;
- that a recovered success is crash-consistent or distributed-linearizable;
- that the accepted envelope instantiates end-to-end
  `PermitAuthenticationEvidence` or binds to `HeadBoundPermit` and its
  invariant/commit witness;
- that the outcome is true, causal credit is independent or the revision
  improves real LLM behavior; or
- that the TypeScript/Effect runtime refines Lean atomic admission.

Accordingly the checked-in end-to-end readiness flag for actual Permit
authentication remains false. A mechanism and a test vector are present; a
production occurrence is not.

## 7. Next evidence transaction

The next proof-first slice is to freeze canonical bytes for the complete
execution certificate, implement an independent raw-byte checker and define
the Lean projection from its accepted value to the existing claimed runtime
certificate. That projection must also derive the expected envelope bindings
from the exact intent/admission context instead of accepting a free-standing
expected record.

Only after that checker boundary is fixed should this verifier sit behind a
separately identified issuer/executor and one durable admission transaction.
That transaction must obtain authoritative trust and time, re-read the current
head, verify the exact envelope and transition invariant, consume `permitId`
and nonce once, write the successor and append the audit receipt before
returning success. Its raw invocation/response history, crash/recovery
artifacts and exact certificate bytes must then be independently replayed
before the current Lean refinement obstruction can be changed.
