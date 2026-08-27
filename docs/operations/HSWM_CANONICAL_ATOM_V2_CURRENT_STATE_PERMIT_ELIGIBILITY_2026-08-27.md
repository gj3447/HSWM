# HSWM canonical-atom v2 current-state Permit eligibility boundary

> **Date:** 2026-08-27
>
> **Status:** `EXACT_LOCAL_HEAD_RELATIVE_ELIGIBILITY / NOT_CANONICAL_PERMIT / NOT_COMMIT_CAPABILITY / NOT_EXTERNAL_EFFECT / NOT_ADMISSION / NOT_LEARNING / SCIENTIFIC_UNJUDGED`
>
> **Authority:** bounded conceptual and engineering continuation of the v2
> transition-evidence contract. It neither ratifies a new HSWM philosophy nor
> reports a scientific result.

## 1. Canonical role, present evidence and conceptual delta

HSWM remains one token-native LLM-function macro-neural network. Its evolving
schema-relative canonical hypergraph is the same object's living harness,
world model and continuous learner; those are not separate subsystems. The
fixed `H/W/A/F/Π` decomposition remains retired. The only canonical uniqueness
used here is exactly one schema-relative responsibility owner for every
admitted canonical atom version. An owner remains accountability, not
permission.

The target constitutional predicate is:

```math
Permit_σ(S,e)
```

It is state-relative: an authorization label is insufficient unless the exact
schema, state, authority policy, affected subjects, consent state, revocation
state, scope and evaluation time agree. It is also only a necessary transition
condition. It does not itself execute, admit, dispatch, observe an outcome,
assign causal credit or learn.

The checked-in evidence before this phase establishes less:

- the local journal can reconstruct an intact predecessor-bound prefix and an
  exact local head;
- the transition-evidence bundle can bind an exact proposal, represented
  authorization decision and pre-outcome trajectory; and
- the bundle still treats membership and head freshness as claims.

The conceptual delta in this phase is therefore:

```text
well-bound represented evidence
  -> exact active schema and validated canonical state
  -> exact local journal head and state commitment
  -> admitted, content-bound, latest policy/decision/consent/trace atoms
  -> scope, purpose, direct-authorizer, consent and revocation evaluation
  -> local-head-relative eligibility only
```

This is deliberately not the delta from evidence to a globally current
canonical Permit. The local journal has no independent monotonic-head witness,
so complete trailing-slot deletion or a separately valid fork cannot be ruled
out. Calling a positive local result a globally current Permit would exceed the
checked-in evidence.

There are two intentionally different entry points. The pure checker consumes
a **caller-supplied snapshot package** and is therefore an evidence instrument:
it can test whether that package is internally exact, but cannot establish that
the package is the runtime's present state. The positive public boundary first
obtains exactly one recovered `CanonicalAtomV2DurableRuntime.snapshot`, compares
the supplied package against that one snapshot, and only then evaluates it.
Neither path turns caller-supplied `evaluatedAt` into trusted “now”. It is an
explicit claimed evaluation instant, not a clock authority.

## 2. State-relative authority and consent

Permission effects must come from admitted canonical relations and policy, not
from role-string equality or an atom's responsibility owner. The bounded v1
policy therefore names:

- exact scope and purpose pairs;
- direct authorizer principals allowed to decide each pair; and
- an exact consent slot and controller set for every affected canonical subject
  relation.

The policy itself is an admitted, content-addressed canonical atom version and
must be the latest version of its logical lineage. An authorization decision is
eligible only when its exact record bytes are the content of its exact admitted
decision atom, that atom is the latest logical version, the proposal read it
before writing, and the decision's authorizer appears in the matching policy
rule.

Every affected subject requires one exact consent decision. Its record must be
the content of the policy-selected consent slot's latest admitted atom version;
its consenter must be a controller named by policy; and its subject, relation,
claimant, scope and purpose must match exactly. Prefix, wildcard and
case-folding scope rules do not exist in v1.

This direct-authorizer model is intentionally narrower than arbitrary authority
delegation. It does not prove that a principal controls a person, that consent
was informed, or that the policy is morally legitimate. Principal identity,
delegation chains, signature verification and socially independent consent
remain later contracts. What v1 establishes is that these exact permission
relations are represented in—and selected by—the exact canonical snapshot,
rather than inferred from owner, claimant or authorizer text alone.

## 3. Exact-head and time boundary

An evaluation input carries the full active schema, validated canonical state,
the exact journal-head record and descriptor, and a local head observation. The
resolver recomputes and cross-checks:

- exact schema canonical bytes and binding;
- canonical state validity and state SHA-256;
- journal record descriptor, lineage, schema binding, revision and resulting
  state SHA-256;
- transition claimed predecessor, expected revision and proposal descriptor;
- exact canonical membership and content descriptor for policy,
  authorization-decision, consent-decision and trajectory atoms; and
- exact proposal reads and disjoint writes for every permission-bearing input.

The evaluation instant is explicit; the resolver never calls an ambient clock.
The local head observation must name the same schema, lineage, head, revision
and state digest and must be observed at the evaluation instant. Authorization
and consent decisions must already exist, satisfy
`notBefore <= evaluatedAt < expiresAt`, and carry a non-revoked check made at
that same instant. Missing, denied, not-yet-valid, expired, revoked, unchecked,
future-checked or stale-checked states fail closed.

The equality requirement avoids silently inventing a freshness tolerance. It
does not authenticate the clock or prove global head freshness. Those require a
separately trusted time source and external monotonic-head witness.

Consequently, “current” in this v1 name means only *relative to the exact local
snapshot that was compared during this evaluation*. It is neither an
anti-rollback statement nor a global Permit. A caller who needs trusted present
time must supply a later, separately specified trusted-clock contract; this
checker must not infer it from a descriptor label.

## 3.1 Permission-bearing records and proposal limits

The admitted, stable records used at this boundary are exactly: Permit policy,
authorization decision, consent decision, and trajectory contract. Each is
content-addressed independently before any transition evidence names it, which
avoids a head/decision hash cycle. The evidence bundle binds those pre-existing
records; it does not create them.

The candidate proposal may write only schema-approved `allowedWriteKinds` for
this permit policy. In bounded v1, a policy cannot include a permission-bearing
kind (policy, authorization-decision, consent-decision, or trajectory-contract)
in that set, and a candidate cannot create one or revise any such admitted
logical lineage. Separate policy-governance semantics do not yet exist. This is
stronger than merely rejecting an identical full key: a candidate cannot mint
its own future authority by changing an atom UID, selecting another lineage, or
advancing a revision number. The current reducer does not consume this
eligibility result as a commit capability.

## 4. Output and forbidden derivations

There are two deliberately non-interchangeable positive statuses:

```text
pure evidence instrument:
  ELIGIBLE_AT_EXACT_SUPPLIED_SNAPSHOT_NOT_CANONICAL_PERMIT
  snapshotBasis = SUPPLIED_STATE_AND_HEAD_RECORD_NOT_JOURNAL_REPLAY

public durable-runtime wrapper:
  ELIGIBLE_AT_RECOVERED_LOCAL_HEAD_FOR_SUPPLIED_TIME_NOT_CANONICAL_PERMIT
  snapshotBasis = ONE_DURABLE_RUNTIME_RECOVERY_SNAPSHOT
```

Both bind the exact schema, described snapshot, state revision and digest,
proposal, policy, authorization, trajectory, consent records and supplied
evaluation instant. Only the second additionally proves equality with the one
recovered local runtime snapshot used by that invocation. Both explicitly mark
the time as caller-supplied and the head as non-anti-rollback. Each is an
immutable read-only evaluation record, is not reusable authority, and contains
no store, journal, dispatch or commit method.

The following implications remain forbidden:

- owner, authorizer, claimant, custodian or controller equality `=>` Permit;
- policy or decision content membership `=>` semantic truth or moral legitimacy;
- a locally observed journal head `=>` globally current or rollback-free head;
- a caller-supplied evaluation instant or clock descriptor `=>` trusted now;
- local eligibility `=>` canonical Permit, admission or commit success;
- local eligibility or a sealed trajectory `=>` external effect occurrence;
- consent representation `=>` informed, authentic or uncoerced consent;
- outcome observation `=>` independence, causal credit or learning; and
- codec/test success `=>` HSWM intelligence or scientific efficacy.

An eventual commit path must re-evaluate these conditions inside the same
recover/validate/CAS linearization boundary. Passing an old evaluation record
to a later submit call would reintroduce a head-change TOCTOU bug. This phase
therefore does not connect the result to the current reducer or durable submit
API.

## 5. Adversarial acceptance matrix

| Attack | Required result |
| --- | --- |
| same schema version but different schema bytes | reject exact binding |
| same revision but different head, lineage or state digest | reject exact head |
| stale or fabricated claimed predecessor | reject predecessor binding |
| absent, non-current or content-mismatched policy/decision/consent/trace atom | reject membership |
| required permission relation appears only in the proposal write set | reject self-authorization |
| candidate creates a permission-bearing kind or revises any admitted permission-bearing lineage | reject self-authorization/governance collapse |
| responsibility owner equals actor or authorizer | no permission inference |
| authorizer is absent from the exact scope/purpose rule | reject authority |
| scope or purpose differs only by prefix/case | reject exact match |
| a subject lacks its policy-selected consent slot | reject consent |
| consenter is not a policy-declared controller | reject consent |
| authorization or consent is denied, future, expired, revoked, unchecked, future-checked or stale-checked | reject time/currentness |
| transition id is already in the accepted history | reject replay |
| effect, outcome or disposition is included in a pre-effect Permit evaluation | reject phase collapse |
| duplicate, excess-property or noncanonical JSON bytes | reject exact ingress |
| caller mutates an accepted input or result | immutable snapshot remains unchanged |

## 6. What remains open

1. Add an authenticated external monotonic-head witness and explicit trusted
   clock contract before using the word **current** without the local qualifier.
2. Replace direct-authorizer roots with schema-declared principal identity and
   bounded delegation-chain semantics where required.
3. Integrate re-evaluation into one recover/Permit/invariant/CAS commit boundary;
   never treat a prior eligibility record as a capability.
4. Specify external effect intent, dispatch attempt and occurrence separately
   from a local commit receipt.
5. Only later connect independently attributable outcomes to causal credit,
   owner-valid revision admission and changed-next-behavior evidence.

No content-addressed research receipt or `F1_R8_RESULTS_LOG.md` entry accompanies
this phase. It is philosophical closure at an engineering boundary plus a
falsifiable implementation contract, not a material research result.
