# HSWM canonical-atom v2 typed transition-evidence contract

> **Date:** 2026-08-27
>
> **Status:** `PURE_TYPED_EVIDENCE_CONTRACT / NOT_CANONICAL_PERMIT / NOT_EXTERNAL_EFFECT_OCCURRENCE / NOT_CAUSAL_CREDIT / NOT_LEARNING / SCIENTIFIC_UNJUDGED`
>
> **Authority:** bounded conceptual and engineering continuation for
> canonical-atom v2. It does not add a philosophical ratification or a
> scientific result.

## 1. Canonical role and conceptual delta

HSWM remains one token-native LLM-function macro-neural network whose evolving
hypergraph is the same object's living harness, world model and continuous
learner. The fixed `H/W/A/F/Π` decomposition remains retired. The contracts in
this phase are typed evidence payloads and bounded interfaces to that one state
model; they are not new cognitive subsystems, owner partitions or a second
policy engine.

The existing v2 reference kernel and durable journal establish a narrow local
state-transition boundary: schema-valid immutable writes, exactly one
schema-relative responsibility owner per admitted atom version, content-bound
bytes, an accepted reference-grant receipt and predecessor-bound replay. The
receipt still says `REFERENCE_GRANT_MATCHED_NOT_CANONICAL_PERMIT`, and a
non-null trace remains unsupported by the existing commit reducer.

The target loop requires more:

```text
pre-existing schema, authority and provenance evidence
  -> bounded transition proposal
  -> pre-outcome sealed trajectory
  -> separately observed outcome
  -> causal-credit and revision proposal
  -> invariant, current-Permit and owner-valid admission decision
  -> changed next traversal or transition disposition
```

This phase closes only the typed evidence vocabulary and its internal binding.
It makes authorization-decision evidence, role claims, provenance claims,
pre-outcome trajectories, later outcome observations and rejection/quarantine
dispositions separately representable. It does not implement the current
`Permit_σ` predicate, execution, external effect occurrence, outcome
independence, causal credit or `Learn_σ`.

Codec acceptance is also not canonical admission. A value becomes a canonical
atom only if an active schema declares its kind and owner obligation and a
separate owner-valid transition admits the exact content. Raw candidate and
quarantine bytes remain outside `C_(σ,t)`. A separately admitted audit or
decision atom may refer to their content descriptor without admitting the
candidate it describes.

## 2. Role predicates do not collapse

Every admitted evidence atom version still has exactly one schema-declared
responsibility owner. The following predicates remain distinct even when one
principal string occurs in several positions:

| Role | What the evidence claims | What it does not imply |
| --- | --- | --- |
| responsibility owner | accountability for one admitted atom version's correctness, lineage, validation and recovery | actor, subject, custodian, authorizer, evaluator, truth or permission |
| claimant / actor | who claims to propose or realize the bounded transition | ownership, authority, execution or external completion |
| subject | the declared canonical atom key to which this v1 claim or decision applies; a principal can be represented only through a declared subject-key claim, while actual/admitted membership requires the later resolver | claimant, owner or consent |
| custodian | who claims to store or carry the exact content descriptor named as the custody object, with a separate evidence descriptor | ownership, authority, authenticity, actual possession or truth |
| authorizer | who is named by an authorization-decision record | current validity, sufficient authority or canonical Permit |
| trajectory sealer | who binds an ordered trace before the claimed outcome time | truthful execution, delivery, causation or outcome |
| evaluator / observer | who attributes an outcome observation to a source and method | independence, accuracy, truth or causal credit |
| disposition decider | who records reject or quarantine evidence | authorization, admission of the candidate or learning exclusion outside the declared scope |

Principal equality is allowed because small deployments may assign several
roles to one party. Equality never acts as a permission rule. In particular:

```math
Owner_σ(a,p) \centernot\Rightarrow Permit_σ(S,e).
```

Any durable relation with independent permission, lifecycle, commit, rollback
or revision effects must itself be an admitted relation atom with its own
single responsibility owner. A field-level pointer cannot acquire those
effects by convention.

## 3. Evidence chronology and non-derivations

The pure contract binds a claimed order without turning timestamps into a
trusted clock:

```text
proposal + exact declared schema/pre-state/evidence references
  -> authorization-decision evidence and revocation-check claim
  -> finite trajectory sealed without an outcome event
  -> later outcome observation, possibly UNKNOWN
  -> optional REJECTED or QUARANTINED disposition
  -> no automatic admission or learning transition
```

Structural chronology means only that the represented instants and content
descriptors agree. It does not prove that a sealer acted before learning an
outcome; that requires a later independently witnessed publication protocol.

`decisionRef` and `traceRef` must be distinct keys in the proposal read set,
must not occur in its write set, and must belong to the declared schema
version. `traceId` is bound to the trace atom UID. This blocks a bundle from
declaring that the same proposal writes its own required authority or trace.
It proves only a **declared pre-existing read**, not actual membership in the
current canonical state. Likewise, `claimedPredecessor` and its state revision
are exactly cross-bound to the proposal's expected revision but do not prove
that the descriptor is the actual durable journal head. State membership,
admitted evidence bytes and head freshness remain work for a later resolver.

The following implications are invalid in this phase:

- owner, claimant, authorizer reference, custodian, journal writer or receipt
  holder `=>` current permission;
- a matching grant or authorization-decision record `=>` expiry-, revocation-
  and consent-aware canonical Permit;
- a sealed trace or hash `=>` execution, external delivery, causal order or
  truthful narration;
- a provenance reference, matching bytes, signature claim or multiple sources
  `=>` authenticity, semantic truth, unbiasedness or independence;
- an outcome observation `=>` independent attribution, causal credit or a
  learned revision;
- a rejection or quarantine record `=>` canonical admission of its candidate;
- an accepted local state receipt `=>` external effect dispatch, completion or
  exactly-once delivery;
- absence of a local receipt `=>` absence of an external effect;
- durable replay of evidence `=>` changed future behavior or continuous
  learning.

Missing, invalid, not-yet-decided, not-yet-valid, expired, revoked, unchecked,
denied and unknown evidence states represented by this contract must remain
distinguishable. None may be silently collapsed to granted, accepted, false or
no-effect. This v1 bundle carries at most one outcome observation and neither
detects nor resolves conflicts among multiple observations. A later evidence
store and resolver must retain those observations separately and must not
silently collapse their conflict.

## 4. Pure contract boundary

The TypeScript + Effect slice is required to provide only:

1. strict structural schemas with bounded fields and closed status literals;
2. exact duplicate-aware canonical-JSON bytes and content descriptors;
3. immutable snapshots of accepted evidence values;
4. proposal, schema, pre-state, trace, read/write, role, disposition-custody and
   descriptor cross-binding;
5. ordered pre-outcome trajectory events with no outcome event kind;
6. claimed authorization-window and revocation-state classification that is
   explicitly not `Permit_σ`;
7. declared outcome-independence evidence that remains a claim rather than a
   truth or causal judgment; and
8. `REJECTED` / `QUARANTINED` evidence that carries a candidate content
   descriptor, never an admitted candidate lifecycle or an `ACCEPTED` option.

A `QUARANTINED` disposition requires the same named custodian to declare a
`QUARANTINE` custody whose object is exactly the disposition's candidate
descriptor. A `REJECTED` disposition binds its custodian's custody object to
the disposition evidence descriptor. The separate custody-evidence descriptor
still preserves only a claim; neither binding proves actual possession.

The module provides two strict canonical-JSON ingress domains:

- individually content-addressable authorization, trajectory, reference-effect,
  outcome and disposition records; and
- one bundle that recomputes those record descriptors and binds them to the
  exact canonical transition-proposal bytes.

Authorization evidence keeps decision evidence separate from a typed
revocation claim containing check time, optional revocation time and evidence
descriptor. Classification first revalidates the record and distinguishes
invalid, not-yet-decided, denied, not-yet-valid, expired, revoked, unchecked,
future-check, stale-check and coherent-grant claims, but every literal ends in
`NOT_PERMIT`.
Outcome records distinguish `OBSERVED`, `FAILED` and `UNKNOWN`; role separation
can be `UNKNOWN` or `DECLARED_ROLE_SEPARATION_NOT_PROVEN`. Under the latter
mode, evaluator text cannot reuse the claimant, authorizer, trajectory sealer,
write owner or declared custodian; this remains a structural declaration, not
proof of social or statistical independence. Reference-effect evidence carries
an opaque content descriptor that claims to identify a reference receipt and
separately mirrors the proposal's minimum receipt
fields—read/write sets, trace, actor claim, authorization reference, scope,
decision time, decision and provenance. It does not decode or authenticate the
referenced receipt bytes and remains `REFERENCE_EFFECT_NOT_EXTERNAL_EFFECT`.

The package root exports read-safe schemas, strict byte decoders, descriptor
functions, pure validators and explicit non-Permit classification. It does not
export an issuer, current-Permit resolver, evidence store, quarantine mutation
port, journal bypass, snapshot constructor or learning runtime. Existing v2
domain, content and journal record formats stay unchanged, so old accepted
records remain replayable with their original non-Permit meaning. In
particular, the current domain still rejects non-null `traceRef`; the evidence
contract prepares a future composition but does not silently enable commits.

## 5. Adversarial acceptance matrix

| Attack | Required result |
| --- | --- |
| owner, claimant and authorizer use the same principal text | role binding may decode, but no permission is inferred |
| authorization is invalid, not yet decided, denied, outside its window, revoked, not checked, stale-checked or checked only in the future | exact non-Permit classification remains visible |
| authority or trace required by a proposal is manufactured as the same proposal's write | composition rejects the self-authenticating reference |
| provenance descriptor is claimed without an admitted source key or state proof | claim may be preserved as `CLAIMED_NOT_TRUTH`; membership and anti-self-write checks require a later content/state resolver |
| trace contains an outcome event or claims to seal after the outcome observation | composition rejects the chronology |
| trace, schema, proposal, read/write or content descriptor differs across records | composition fails closed with a typed mismatch |
| evaluator claims independence while reusing a forbidden role under its declared separation mode | the independence claim is rejected or classified as unproved, never promoted to truth |
| disposition custodian text matches but its custody object differs from the required candidate or rejection-evidence descriptor | composition rejects the dangling custody claim |
| disposition attempts `ACCEPTED` or embeds an admitted candidate key | strict ingress rejects it |
| duplicate-key, noncanonical or excess-property JSON is supplied | exact byte ingress rejects it |
| caller mutates an input after validation | returned snapshots and later validation remain unchanged |

These are executable evidence-instrument criteria, not a measure of HSWM
intelligence or a proof that schema-relative single-owner accountability is
scientifically superior.

## 6. Platform-fault boundary

The preceding journal phase ordered an actual platform fault harness before
strengthening durability claims. This host can create an unprivileged
user/mount namespace, but it has no `/dev/fuse`, `fuse3`/`fusermount`,
`libfiu`, or disposable privileged block-device facility. The existing
Layer-local native-like errors, logical interruptions and live-PID races test
adapter control flow and local POSIX competition; they do not test actual
kernel/filesystem/device faults or power loss. `SIGKILL` would add process-crash
evidence only and is not relabeled as filesystem-fault evidence.

This limitation blocks stronger durability claims, not this independent pure
evidence contract. A later privileged CI/VM harness must pin kernel,
filesystem/mount options, Node version, fault implementation and call schedule,
then inject real operation failures and recover through a fresh process. A
physical power-cut or block-device experiment remains a separate claim.

## 7. Verification boundary

The executable checks on 2026-08-27 are engineering evidence instruments, not
HSWM progress or scientific confirmation:

- TypeScript no-emit checking passed;
- the transition-evidence and package-root API suites passed 16/16 checks;
- the complete canonical-atom v2 plus package-root API selection passed 123/123
  checks, including independent-process journal races;
- the production build and `npm pack --dry-run` passed and included the new
  JavaScript and declaration artifacts; and
- the full Effect package passed 563/565 checks. The two remaining failures are
  the pre-existing `s2s-live-python` source-closure check: the current
  `pyproject.toml` SHA-256 is
  `e6e65f0cfc1337e7e6d8abb56aa14206f77428850bc7f4d64ec80167512f6b42`,
  while its historical pinned expectation remains
  `67deb563870b314d8da0cba25abdd8dc39f87559232edcf1c1d616de6536171f`.

The historical pin was not rewritten as part of this work. These checks do not
show actual authority, receipt authenticity, external effect occurrence,
outcome independence, causal learning or platform-fault durability.

## 8. Next order

1. Keep the pure evidence codec and adversarial composition matrix independent
   from the accepted journal and runtime while their contracts evolve.
2. Specify a current-state Permit resolver with exact schema/head binding,
   expiry, revocation and consent observation. A resolver result still needs a
   separately owned canonical decision relation before it can affect commits.
3. Specify external effect intent, dispatch attempt and occurrence observation
   independently of local accepted receipts.
4. Add an external monotonic-head witness before anti-rollback or completeness
   claims.
5. Only after independently attributable outcomes and intervention evidence
   exist, propose causal credit, admission and changed-next-behavior tests for
   `Learn_σ`.

No content-addressed research receipt or `F1_R8_RESULTS_LOG.md` entry accompanies
this work. It is conceptual and engineering scaffolding, not a material
scientific result.
