# HSWM head-bound Permit, invariant and atomic-admission boundary

> **Status:** `SECONDARY_AI_FORMAL_TYPED_CONTRACT / ATOMIC_ADMISSION_SPECIFIED_NOT_RUNTIME_REFINED / SCIENTIFIC_UNJUDGED`
>
> **Target authority:**
> [`HSWM Constitution`](../canon/HSWM_CONSTITUTION_2026-08-20.md),
> [`adaptive research strategy`](../canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md),
> and the transition law in the
> [`DNRD-5 causal macroplasticity design`](HSWM_DNRD_5_CAUSAL_MACROPLASTICITY_DESIGN_2026-08-28.md)
>
> **Formal artifacts:**
> [`HSWMAtomicAdmission.lean`](../../formal/HSWMAtomicAdmission.lean)
> and its
> [`finite consistency witness`](../../formal/HSWMAtomicAdmissionConsistency.lean)
>
> **TypeScript obstruction projection:**
> [`canonical-atom-v2-atomic-admission-refinement.ts`](../../src/hswm/effect-runtime/src/canonical-atom-v2-atomic-admission-refinement.ts)

## 1. Canonical role

HSWM remains one token-native LLM-function macro-neural process. A Permit
decision, an invariant certificate and an admission receipt are schema-approved
atoms in its one evolving hypergraph. They are not separate control, safety or
learning subsystems. Their owners carry distinct correction responsibilities;
ownership alone never grants authority.

The target transition law for an exact effect `e` is:

```math
\mathrm{Inv}_{\sigma}(S,e,S')
\;\land\;
\mathrm{Permit}_{\sigma}(S,e)
\;\land\;
\mathrm{SingleOwner}_{\sigma}(\mathrm{writeset}(e)).
```

All three clauses must refer to the same predecessor state and exact proposed
successor at the admission linearization point. A Permit checked at an older
head, an invariant certificate for another candidate, or a receipt declaring a
different predecessor cannot be combined into admission.

## 2. Target, current evidence and conceptual delta

The target is an outcome-bound canonical revision whose current Permit,
schema-relative transition invariant and atomic state change agree at one
trusted head. Current checked-in evidence stops at two different boundaries:

| Boundary | What it establishes | What it does not establish |
| --- | --- | --- |
| abstract Lean `Learn` | outcome, Permit fields, a pre-state invariant predicate, exact target revision and frame preservation are necessary | a recovered head, Permit freshness at linearization, an exact `S -> S'` invariant certificate or CAS occurrence |
| DNRD-5 v2 two-CAS instrument | a local durable S0/R1/R2 append and receipt chronology with recovered raw-record checks | provider occurrence, outcome support, learning, efficacy or refinement to generic `Learn` |

The conceptual delta is therefore not a renamed DNRD-5 success. It is a
stronger formal relation that places the already separated outcome judgment
under one head-bound admission witness:

```text
trusted predecessor head H
  + Permit decision owned and evaluated for H and exact proposal c
  + invariant certificate owned and evaluated for H, c and candidate S'
  + explicit outcome-support judgment for c
  + one commit witness consuming those exact certificate identities
  -> AtomicLearnAdmission(H, S, c, S', H')
```

The relation uses schema-relative atoms and typed bindings. It does not return
to the retired fixed `H/W/A/F/Pi` decomposition.

## 3. Head- and candidate-bound objects

A `HeadSnapshot` identifies one lineage position, abstract state digest and raw
record digest. A head-bound Permit carries exactly one responsibility owner,
the authorizer decision, the predecessor head, both revision identifiers and a
content digest. A head-bound invariant certificate separately carries one
responsibility owner, a validator, the same predecessor head, exact target and
both revision identifiers, and its own content digest.

For predecessor `H`, successor `H'`, state `S`, proposal `c` and candidate
state `S'`, admission requires:

```math
\begin{aligned}
&\mathrm{digest}(S)=H.\mathrm{stateDigest},\\
&p.\mathrm{head}=i.\mathrm{head}=a.\mathrm{predecessor}=H,\\
&p.\mathrm{target}=i.\mathrm{target}=a.\mathrm{target}=c.\mathrm{target},\\
&p.\mathrm{expected}=i.\mathrm{expected}=c.\mathrm{expected},\\
&p.\mathrm{candidate}=i.\mathrm{candidate}=a.\mathrm{candidate}=c.\mathrm{candidate},\\
&\mathrm{Inv}_{\sigma}(S,c,S'),\\
&H'.\mathrm{lineage}=H.\mathrm{lineage},\\
&H'.\mathrm{sequence}=H.\mathrm{sequence}+1,\\
&\mathrm{digest}(S')=H'.\mathrm{stateDigest}.
\end{aligned}
```

The commit witness must name the exact Permit and invariant-certificate
digests. The Permit decision must also match the proposal's authorization,
trace and scope and remain allowed and active through the underlying `Learn`
relation.

For this bounded single-target model, the actual authorizer is distinct from
the trajectory actor, proposal author, target atom's responsibility owner,
outcome-support adjudicator, outcome-judgment owner and Permit-record owner.
These are formal principal inequalities, not authentication or proof of real
organizational independence.

## 4. Machine-checked obligations

The boundary module's 37 theorems prove that every `AtomicLearnAdmission`
witness:

- contains the underlying owner-bound outcome-evidence learning witness;
- binds Permit, invariant certificate and commit to the same current head;
- binds both certificates and the commit to the exact proposal target and
  expected/candidate revision pair;
- satisfies the exact transition invariant over `S`, `c` and `S'`;
- binds predecessor and successor state digests and advances exactly one head
  position in the same lineage;
- consumes the exact Permit and invariant-certificate identities in the commit
  witness;
- preserves the target responsibility owner, all non-target current atoms and
  the superseded version history through the underlying `Learn`; and
- determines a unique canonical successor state and declared successor head
  for fixed predecessor, proposal, evidence and commit inputs; and
- cannot be inhabited under stale-head, mismatched-candidate, denied/inactive
  Permit, invariant failure, certificate-substitution, commit-substitution or
  declared authorizer-role-collapse hypotheses.

The relation has no default, bypass or error-recovery constructor. Failure to
provide any field leaves it uninhabited rather than producing a weakened
success.

## 5. Finite consistency witness

Necessary-condition proofs alone could describe an accidentally contradictory
relation. The separate consistency module therefore constructs a complete
finite symbolic instance with 11 distinct principal values, one current atom,
a sealed trajectory, separately owned observation and support judgment, an
allowed head-bound Permit, a separately owned invariant certificate, and an
H0-to-H1 commit witness.

Its invariant is not the constant proposition `True`. It requires that the
candidate state be exactly the result of revising the proposal's one current
target and retaining its predecessor:

```math
\mathrm{ExactSingleTargetInv}(S,c,S')
\;:=\;
\exists v,\;
S[c.\mathrm{target}]=v
\;\land\;
S'=\mathrm{revise}(S,v,c).
```

Thirteen checked theorems construct the abstract `Learn`, owner-bound
outcome-learning and final `AtomicLearnAdmission` witnesses, prove that the
relation is inhabited, distinguish the predecessor and successor state
digests, and confirm the exact candidate revision, preserved target owner,
archived predecessor and unchanged other target.

This is specification non-vacuity, not evidence that an HSWM runtime, authority
service, evaluator, validator or external world supplied any of those values.

## 6. Relation to the TypeScript/Effect runtime

The generic current-state Permit checker still reports local eligibility as
`NOT_CANONICAL_PERMIT` and exports no commit capability. It cannot refine this
new relation.

The DNRD-5 v2 dispatcher is stronger in a different, deliberately local sense:
it recovers S0 before CAS1, recovers and reconstructs R1 before CAS2, binds
phase-specific authority and one-shot consumption, and confirms exact R2. Its
success terminal remains:

```text
NOT_PROVIDER_CALL_NOT_OCCURRENCE_NOT_LEARNING_NOT_EFFICACY
```

That instrument has no owner-bound outcome-support package and does not expose
the generic transition-invariant witness defined here. The companion read-only
TypeScript profile therefore records two present structural boundaries and
five still-missing semantic/composition obligations. Its verdict is
`BLOCKED_NOT_REFINED_TO_LEAN_ATOMIC_ADMISSION`, and its canonical decoder
accepts only the exact checked-in obstruction bytes. Consequently this phase
does not change TypeScript runtime semantics or relabel DNRD-5 as learning. A
later refinement must prove an explicit mapping from exact runtime bytes and
durable events to every field of `AtomicLearnAdmission`; field-name similarity
is insufficient.

## 7. Exact claim ceiling

Lean checks consequences of the declared relation without `sorry` or added
axioms. It does not authenticate principals or heads, prove digest collision
resistance, execute a validator, establish that a CAS occurred, prove an
external outcome true, assign valid causal credit, or prove that changed state
causes changed behavior. It is not a distributed-linearizability proof and not
a TypeScript semantics proof. The finite witness establishes only that this
bounded relation is jointly satisfiable in Lean; it is not a consistency proof
for all HSWM philosophy, ontology or runtime code.

No scientific result, G0/G1 gate, FCL law, cognition, consciousness, efficacy
or complete HSWM realization follows. This is a protective specification that
prevents stale or cross-candidate evidence from being called canonical
learning.
