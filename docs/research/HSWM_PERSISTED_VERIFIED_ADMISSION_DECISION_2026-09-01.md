# HSWM persisted verified-admission decision boundary

> **Status:** `SECONDARY_AI_FORMAL_MODEL / EXECUTABLE_LOCAL_V2_BINDING / SOURCE_LEVEL_REFINEMENT_UNPROVED / SCIENTIFIC_UNJUDGED`
>
> **Target authority:**
> [`HSWM Constitution`](../canon/HSWM_CONSTITUTION_2026-08-20.md)
>
> **Formal artifact:**
> [`HSWMPersistedVerifiedAdmission.lean`](../../formal/HSWMPersistedVerifiedAdmission.lean)
>
> **Runtime artifacts:**
> [`canonical-atom-v2-verified-admission-gateway.ts`](../../src/hswm/effect-runtime/src/canonical-atom-v2-verified-admission-gateway.ts)
> and
> [`canonical-atom-v2-local-permit-commit.ts`](../../src/hswm/effect-runtime/src/canonical-atom-v2-local-permit-commit.ts)

## 1. Answer first

This slice closes one previously explicit gap: the v2 local path stores the
exact canonical Lean request and exact accepted response in the same immutable
journal slot as the Permit-bound state transition. A fresh gateway instance
recovers those bytes and checks them against the predecessor view reconstructed
from the journal. The accepted decision is therefore no longer only a live
`WeakMap` correlation for this v2 path.

It does not close the end-to-end HSWM claim. In particular, it is not a proof
about all TypeScript/Effect executions, an authoritative Permit issuer, a
power-loss or distributed transaction proof, a complete execution certificate,
outcome truth, causal credit, or LLM improvement.

## 2. Canonical role and temporal direction

Permit, decision, commit and later certificate are typed moments of one
schema-relative HSWM transition. They are not independent cognition or
authority subsystems. Their dependency direction matters:

```text
Permit/state/recovery preflight
  -> exact Lean request and accepted successor
  -> one immutable slot containing state transition + exact decision bytes
  -> restart recovery and exact decision revalidation
  -> later complete execution-certificate construction and audit
```

A complete execution certificate already contains its commit and recovery
projection. Using that completed certificate as a pre-commit premise would be
circular. The pre-commit gate therefore persists its exact decision with the
commit; the full certificate remains a post-occurrence audit object.

## 3. Lean result

`HSWMPersistedVerifiedAdmission.lean` defines a decoded persisted-entry model
over the existing verified-admission wire and local Permit-commit model. Lean
proves that checker acceptance implies:

- the response reflects the exact stored request;
- the request carries the same retained local-record projection;
- the response successor is the recovered view of the same full local-model
  transition from the supplied recovery prefix;
- that full local-model transition succeeds;
- the exact nonce is consumed and the exact successor head is published; and
- a substituted response, recovered request view, or local record fails
  closed.

The Permit signing-document model now also checks the decoded mandatory
`CanonicalPermitSigningDocument` tag and proves that a wrong tag cannot be
accepted.

These are decoded-value theorems. Lean does not thereby prove canonical JSON,
SHA-256, Ed25519, Node, POSIX, fsync, hard links, process execution or the
TypeScript source correct.

## 4. Runtime v2 binding

The existing v1 gateway and namespace remain unchanged. The new v2 route uses
contract `hswm-verified-admission-commit/v2` and namespace
`verified-admission-commits-v2`. One exact record contains:

- the canonical Permit envelope and pre/post state bytes;
- intent, nonce, predecessor and successor bindings;
- exact canonical Lean request and response bytes;
- SHA-256 values recomputed from those two byte strings; and
- one truthful bounded-status literal.

Before publication and during every recovery, the v2 gateway reconstructs the
wire request from the actual journal prefix. It requires byte equality with the
stored request and an exact canonical accepted response carrying the computed
successor. Publication remains one file-fsync followed by no-replace hard-link
publication, directory fsync and exact readback. A separate decision sidecar is
not used, so a process crash cannot publish the state slot without the decision
artifact that is part of those same bytes.

Integration tests exercise a real built Lean CLI, restart recovery, namespace
separation, exact request/response and hash recovery, canonical record
tampering, semantic successor substitution and rejection before publication.
This is ordinary local Linux integration evidence. The underlying v1 mechanism
has separate process-crash tests, but v2-specific `SIGKILL` checkpoints have
not yet been run and no physical power-cut claim is made.

## 5. Remaining boundary

The strongest honest statement is:

```text
accepted decoded persisted-entry checker
  -> exact bounded local-model transition in Lean

tested v2 runtime occurrence
  -> one local immutable record containing exact CLI decision bytes
```

There is not yet a theorem joining those two lines for every compiled
TypeScript execution. The configured CLI executable is unpinned, adapter facts
remain runtime-supplied, the local issuer key is ephemeral, the clock is
caller-relative, and a same-UID filesystem writer is outside the process-local
API boundary. Nonce and head uniqueness are local to the v2 namespace; the
legacy and generic namespaces are deliberately separate and do not provide one
global consumption domain.

The next proof-first step is a post-commit full-certificate audit wire and Lean
CLI with cross-language known-answer vectors. After that, an actual producer
must derive the complete certificate from this v2 receipt and fresh recovery,
and an independent audit receipt must bind that certificate without pretending
it existed before its own commit/recovery evidence. External outcome, causal
and real-LLM protocols remain later empirical obligations.

This formal-engineering result creates no research receipt and leaves HSWM
causal efficacy `UNJUDGED`.
