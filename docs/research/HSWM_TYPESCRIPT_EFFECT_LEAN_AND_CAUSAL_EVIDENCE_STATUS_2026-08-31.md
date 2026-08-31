# HSWM TypeScript/Effect–Lean and causal-evidence status

> **Date:** `2026-08-31`
>
> **Status:** `PARTIAL_ENGINEERING_CLOSURE / LIVE_LEAN_ADMISSION_GATE_LOCAL_ONLY / SOURCE_LEVEL_REFINEMENT_UNPROVED / OUTCOME_CAUSAL_AND_LLM_CONFIRMATION_ABSENT`
>
> **Scientific status:** `UNJUDGED`

## Answer first

The requested chain is not wholly solved. Two bounded layers are now
executable and one is formally modeled; the scientific layers still require a
new externally operated occurrence.

| Claim | Checked-in evidence | Current decision | Confidence |
|---|---|---|---|
| TypeScript raw certificate fields conform to the Lean wire contract | complete strict codec/checker, one satisfiable raw vector, adversarial mutations, Lean decoded-field theorems | `CONFORMANCE_EVIDENCE_PRESENT / UNIVERSAL_SOURCE_REFINEMENT_UNPROVED` | high for tested vectors, unavailable for all TS executions |
| a protected local journal write follows a live Lean admission decision | executable pure `VerifiedAdmissionKernel`, canonical projected request/decision wire, bounded native stdin/stdout CLI, real TS preflight and exact-response check, private one-use approval and protected namespace tests | `LIVE_LOCAL_GATE / PROCESS_LOCAL_API_BOUNDARY_ONLY / UNIVERSAL_SOURCE_REFINEMENT_UNPROVED` | high for the checked bounded path; unavailable for arbitrary processes or filesystem writers |
| key, time and nonce participate in real Permit issuance | Node generates an Ed25519 keypair, a caller-relative system/injected clock fixes validity, `randomBytes(32)` mints a collision-checked one-use nonce digest, canonical envelope is signed and verified | `REAL_LOCAL_CRYPTO_OCCURRENCE / NOT_AUTHORITATIVE_PRODUCTION_ISSUANCE_OR_TRUSTED_TIME` | high for the local test process |
| Permit consumption and successor publication use an atomic no-replace local publication | verified envelope, nonce, intent, pre/post state bytes and heads are bound in one prepared-and-`fsync`ed file, then hard-linked into one successor slot; independent-process `SIGKILL` recovery and concurrent-winner tests pass | `LOCAL_POSIX_PROCESS_CRASH_EVIDENCE / NOT_POWER_LOSS_OR_DISTRIBUTED_LINEARIZABILITY_PROOF` | moderate |
| outcome is externally true and causal credit independently identified | no new outcome corpus, private-answer opening, independent evaluator receipt or independent judge result exists | `NOT_ESTABLISHED` | high confidence in the negative audit |
| admitted revision improves real LLM behavior | earlier exploratory calls exist, but no passed G0/G1 confirmatory occurrence exists | `NOT_ESTABLISHED` | high confidence in the negative audit |

“High confidence” in an engineering row means the declared local checks are
well supported, not that the broader HSWM claim is true. Tests are evidence
instruments; they are not cognition or efficacy.

## Target identity and conceptual delta

The target remains one token-native HSWM transition:

```text
sealed trajectory -> independently attributable outcome -> causal credit
-> owner-valid revision -> current Permit and invariant
-> durable successor -> changed fresh LLM behavior
```

The implementation does not introduce a separate authorization or certificate
subsystem. Permit, commit and certificate records are bounded projections of
one prospective state transition. The present delta is narrower: TypeScript
now performs its real local Permit/state/recovery preflight before asking a
bounded Lean native CLI for a canonical admission decision; only an exact
accepted response mints the private one-use approval that reaches the separate
protected journal namespace. This proves neither the adapters nor TypeScript
as a whole. Truth, credit and efficacy remain outside the result until real
evidence exists.

## Formal and executable engineering result

[`HSWMExecutionCertificateWire.lean`](../../formal/HSWMExecutionCertificateWire.lean)
proves that accepted decoded fields project the exact intent, Permit,
invariant, issue, singleton commit log, linear successor and chronology
conditions. During raw-vector construction, an earlier contract defect became
visible: the commit plan contained the successor record digest while its own
SHA-256 was required to equal that digest. That was an unrealizable hash
fixed-point obligation. The corrected plan carries only successor lineage,
sequence and state digest; Lean proves that its successor projection ignores
the later record digest.

[`canonical-atom-v2-execution-certificate-wire.ts`](../../src/hswm/effect-runtime/src/canonical-atom-v2-execution-certificate-wire.ts)
implements the corresponding strict canonical-JSON/raw-artifact checker. It
derives Permit expected bindings only from the decoded intent and validates
the full certificate body. Permit/invariant responsibility owners and the
invariant validator are committed inside the signed intent. The invariant
certificate's content digest names external invariant content rather than its
own enclosing bytes, avoiding another self-digest cycle. The complete vector
computes the record-independent plan bytes first, places their SHA-256 in the
successor head, signs the intent, and builds the certificate outside its own
digest.

This is strong cross-boundary conformance evidence, but not a mathematical
proof about the TypeScript program. Lean does not parse or execute the TS
source and has no formal semantics here for Effect, Node crypto, canonical JSON
or POSIX I/O. A universal `TS execution refines Lean` theorem still requires a
verified source semantics or proof-producing extraction.

[`HSWMLocalPermitCommit.lean`](../../formal/HSWMLocalPermitCommit.lean)
models the local transition and proves that acceptance requires the envelope,
time and state-byte-binding gates, consumes the nonce, appends exactly one
record, publishes the exact linear successor, rejects replay and rejects stale,
cross-lineage or nonlinear commands. Its foreign crypto, clock and actual
SHA-256 state-byte checks remain explicit Boolean premises, by design.

[`HSWMVerifiedAdmissionKernel.lean`](../../formal/HSWMVerifiedAdmissionKernel.lean)
adds an executable, pure admission boundary over that model. It proves both
soundness and completeness: an accepted kernel decision is exactly a
`localPermitCommit` transition, and every such model transition is accepted.
It also proves that acceptance requires all three supplied adapter facts,
consumes the exact nonce, publishes the declared successor and refines the
bounded linear journal. The kernel's input is deliberately explicit about its
trusted adapters; the proofs do not turn their Boolean outputs into proofs of
Ed25519, time, state bytes or storage.

[`HSWMVerifiedAdmissionWire.lean`](../../formal/HSWMVerifiedAdmissionWire.lean)
fixes a compact canonical JSON request/decision boundary for the recovered
head and consumed-nonce view, record and adapter facts. Its canonical parser
rejects noncanonical input and bounds request bytes, response bytes, identifier
bytes and the recovered nonce list (at 128). Lean proves that an accepted wire
response carries an exact kernel successor and, for every full local state
with the same recovered head/nonce view, simulates that full model transition.
[`HSWMAdmissionKernelCli.lean`](../../formal/HSWMAdmissionKernelCli.lean) is a
bounded native stdin/stdout adapter for this wire; it owns no key, clock,
nonce issuer or storage capability.

[`canonical-atom-v2-verified-admission-gateway.ts`](../../src/hswm/effect-runtime/src/canonical-atom-v2-verified-admission-gateway.ts)
is the live local integration. It runs the real Permit/state/recovery
preflight, serializes the exact canonical request to the configured Lean CLI,
requires an exact canonical accepted successor response, and only then mints a
private `WeakMap`-authenticated one-use approval for no-replace publication.
The gateway requires an existing root, resolves symlink aliases to one physical
protected-root identity for process-local submission serialization, and uses a
distinct protected journal namespace. Chained-admission and different-lineage
tests, including two aliases of one physical root, demonstrate the intended
local boundary.

## Actual local key, time, nonce, commit and recovery

[`canonical-atom-v2-local-permit-commit.ts`](../../src/hswm/effect-runtime/src/canonical-atom-v2-local-permit-commit.ts)
now supplies one bounded real occurrence path:

- a real ephemeral Ed25519 keypair is generated inside the issuer;
- the issuer mints 32 random nonce bytes and releases only their SHA-256;
- a duplicate nonce digest is retried within a fixed bound rather than silently
  minting the same reservation twice;
- a minted nonce digest may be signed once and unknown or reissued digests are
  rejected;
- issuance time, validity window, trust policy and revocation epoch are signed;
- commit re-verifies the canonical envelope against the public trust snapshot
  and current local clock;
- nonce, execution-intent digest, predecessor and successor heads, exact pre-
  and post-state bytes, verification time and exact envelope bytes are stored
  in one successor record;
- that record is written to a private `0400` staging file, file-`fsync`ed,
  atomically hard-linked without replacement into the final slot, directory-
  `fsync`ed and read back exactly; and
- recovery rechecks canonical bytes, signature, time-at-original-verification,
  state digests and adjacent state bytes, lineage-directory identity, immediate
  successor order and nonce uniqueness.

The tests observe one concurrent winner, restart-loadable public verification
context, replay/stale-head rejection, expired/forged no-write behavior and
tamper refusal. Two Linux independent-process tests also deliver `SIGKILL`
immediately after prepared-file `fsync` and immediately after final-slot link:
fresh recovery observes respectively zero commits and exactly one fully valid
commit. This is process-crash evidence, not a simulated power cut or a theorem
about every filesystem. The verification clock is real process input but is
caller-relative; it is not a trusted or monotonic time authority. The private
key is ephemeral and cannot resume issuance after process death; only its
public trust snapshot can be retained for record verification. Therefore the
precise claim is bounded local POSIX evidence, not a production authority,
trusted time, durable key custody, distributed transaction or power-loss
proof. The new protected gateway does not persist the Lean decision in
recovery, cannot exceed the 128 recovered-nonce wire ceiling without a new
contract/checkpoint, and leaves the legacy raw namespace available for public
compatibility. Its CLI path is caller-configured and unpinned. The private
approval is an in-process API boundary, not cross-process or same-UID
`node:fs` unbypassability.

## Outcome and LLM evidence validation

The evidence inventory was rechecked using a causal-claim ceiling rather than
counting model calls as success:

- [`HSWM_G1_MICRO_EXPLORATORY_RESULTS_2026-08-30.md`](../../results/HSWM_G1_MICRO_EXPLORATORY_RESULTS_2026-08-30.md)
  is one real eight-completion traversal/revision/remove/restore run. Every arm
  was correct, so the task was baseline-saturated. Its evaluator was local and
  same-process; `G0` did not pass and `G1` was not evaluated.
- [`HSWM_G1_OPAQUE_IDENTIFIABILITY_V2_RESULTS_2026-08-30.md`](../../results/HSWM_G1_OPAQUE_IDENTIFIABILITY_V2_RESULTS_2026-08-30.md)
  is a real exploratory 8-episode run with 64 completion and 64 tokenizer
  requests. It observed a state-readout separation, but retained position bias,
  an outcome-dependent forced-opposite arm, a same-process evaluator and no
  reusable baseline. It is G0 identifiability evidence, not G1 efficacy.
- ALFWorld artifacts qualify parts of a runtime and selection boundary only;
  they contain no confirmatory actor outcome or revision-effect result.

No checked-in data presently support an unbiased estimate of revision effect,
a valid uncertainty interval, outcome-source independence or independently
identified credit. Causal language is therefore withheld.

## Prospective closure contract

[`confirmatory_revision_protocol.py`](../../_research/dnrd5/confirmatory_revision_protocol.py)
adds a fail-closed pre-outcome readiness validator for the existing 300-block,
2,700-call DNRD-5 design. It requires four fixed arms, no retry/replacement,
future-randomness assignment, pre-outcome seals, distinct operational roles, a
blind separately operated evaluator, an independent reimplementation by the
judge, and external append-only raw evidence.

Passing that validator deliberately returns `false` for execution, outcome
truth, causal credit and LLM improvement. Promotion requires the actual sealed
corpus, private-answer opening, independent replay and the frozen three-
contrast analysis. The current machine has no qualified DGX run context,
independent evaluator/judge or externally controlled immutable destination, so
launching a smaller convenient run here would not answer the requested claim.

## What remains before the whole chain is solved

1. Connect the complete certificate producer to this gated local commit
   occurrence, rather than validating only a constructed full vector.
2. Replace the caller-configured/unpinned CLI and process-local protected-root
   boundary with an independently deployable authority if cross-process or
   same-UID filesystem non-bypassability is required.
3. Add persistent audited private-key custody, a trustworthy clock source and
   qualified power-loss/filesystem validation if the claim is to exceed the
   local process-crash boundary.
4. Supply a verified TS/Effect semantics or extraction path for a universal
   Lean refinement theorem.
5. Freeze and execute the external 300-block occurrence with an independently
   operated evaluator and judge.
6. Promote only if the active revision beats all frozen controls, removal
   eliminates the gain, restoration returns it, shuffled/delayed credit does
   not, and independent replay reproduces the result.

Until those conditions are met, the correct conclusion is partial engineering
closure and no causal or real-LLM efficacy claim.
