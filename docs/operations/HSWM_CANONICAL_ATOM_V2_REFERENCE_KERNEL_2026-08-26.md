# HSWM canonical-atom v2 reference kernel

> **Date:** 2026-08-26
>
> **Status:** `IMPLEMENTED_REFERENCE_KERNEL / NON_DURABLE / SCIENTIFIC_UNJUDGED`
>
> **Authority:** engineering realization of the 2026-08-26 USER_PRIMARY
> single-owner direction; it does not add a new philosophical or scientific
> claim.

## 1. Outcome

The first TypeScript + Effect realization of the schema-relative canonical-atom
contract now exists independently of the retired fixed `H/W/A/F/Pi` v1 slice.
It implements a bounded reference kernel for:

- an open, versioned schema registry of atom kinds and responsibility owners;
- fork-safe keys `(schemaVersion, lineageId, atomUid, revisionId)`;
- exactly one schema-valid `responsibilityOwner` field per admitted atom;
- content-addressed immutable atom envelopes;
- persistent relation atoms with typed, role-bearing references;
- append-only linear revision and exact `supersedes` validation;
- actor claim, responsibility owner, and an opaque reference-layer grant as
  separate fields;
- strict unknown-input decoding, deterministic pure evolution, atomic Effect
  commit, and immutable effect receipts.

The philosophical source remains the
[`single-owner canon`](../canon/USER_PRIMARY_HSWM_SCHEMA_RELATIVE_SINGLE_OWNER_2026-08-26.md)
and the adversarial research contract remains the
[`scientific-philosophy study`](../research/HSWM_SCHEMA_RELATIVE_SINGLE_OWNER_SCIENTIFIC_PHILOSOPHY_2026-08-26.md).

## 2. Runtime boundary

The implementation is split by correctness responsibility:

| file | bounded responsibility |
|---|---|
| [`canonical-atom-v2-schema.ts`](../../src/hswm/effect-runtime/src/canonical-atom-v2-schema.ts) | strict Effect Schema ingress, v2 types, key identity, deep snapshots |
| [`canonical-atom-v2-domain.ts`](../../src/hswm/effect-runtime/src/canonical-atom-v2-domain.ts) | pure schema validation and deterministic append-only state evolution |
| [`canonical-atom-v2-runtime.ts`](../../src/hswm/effect-runtime/src/canonical-atom-v2-runtime.ts) | separate authorization check, atomic `Ref.modify` commit, journal and narrow runtime service |

The state implemented by this kernel is the engineering projection

```text
CanonicalAtomV2State =
  (schemaVersion, revision, bootstrapClosed, admitted atom versions)
```

Raw inputs that fail Effect Schema decoding or domain invariants never enter the
state. The kernel currently returns typed rejection errors rather than making
rejected or quarantined input a canonical atom.

Atom content is bound here by media type, exact byte length, and SHA-256 while
the phase-1 reference Layer remains entirely in memory. The optional
[`content-bound runtime`](HSWM_CANONICAL_ATOM_V2_CONTENT_BOUND_RUNTIME_2026-08-26.md)
now supplies duplicate-aware schema bytes, atom-envelope digests and a local
durable content-addressed port without changing this pure reducer. Its state and
receipt journal are still explicitly non-durable.

## 3. Enforced invariants

1. Schema owner addresses, atom kinds, and per-kind reference contracts are
   unique and cross-validated.
2. Every admitted atom names one owner in the active schema registry and in its
   kind's allowed-owner set.
3. Owner is not a permission. A matching external reference-layer grant and
   exact scope are required even when actor and owner strings happen to match.
   Grant input itself is strictly decoded and duplicate grant/scope definitions
   are rejected.
   Its receipt value is
   `REFERENCE_GRANT_MATCHED_NOT_CANONICAL_PERMIT`; validity windows,
   revocation and canonical authorization evidence are not falsely claimed.
4. Canonical keys cannot be overwritten. A linear revision advances the latest
   revision by exactly one, retains the same kind and owner, and references that
   exact predecessor through `hswm:reference:supersedes`.
5. Changing an owner through an ordinary revision is rejected. Schema migration
   is deliberately not implemented on this commit path.
6. Typed references must satisfy declared role, target kind and per-role
   cardinality.
   Existing referenced atoms and provenance sources must appear in the declared
   read set.
7. A persistent relation is admitted as its own atom with its own owner and
   declared minimum arity; a partially valid multi-atom write is rejected as a
   whole.
8. One successful transaction advances the state revision once and appends one
   receipt whose write set is derived from the actual committed atoms.
9. Concurrent transactions against the same expected state revision are
   serialized; only one conflicting transition can commit.
10. State, atom, nested reference, content, schema, and receipt values returned
    by the runtime are defensive frozen snapshots.
11. The exported pure reducer revalidates the complete prior state; a forged
    owner, kind, relation, revision lineage or provenance cycle cannot become a
    valid successor merely by calling the reducer directly.
12. `traceRef` is fail-closed in this phase. It remains `null` until a later
    schema can prove a pre-existing sealed trajectory rather than allowing a
    transition to manufacture its own trace.
13. `BOOTSTRAP` provenance is available only in the genesis transaction.
    `bootstrapClosed` becomes permanently true after the first commit; later
    admission must use observation or derivation provenance.

The exported `evolveCanonicalAtomsV2` function computes and validates a pure
candidate successor. Its success is not permission or canonical commit. Only
`CanonicalAtomV2Runtime.submit` crosses the reference-grant boundary and emits
an accepted receipt.

## 4. Explicit nonclaims and deferred work

This reference kernel, including its optional content-bound facade, is not:

- a durable canonical-state database, distributed log, CRDT, or production
  authorization service; only the optional facade's content bytes have a local
  POSIX durability adapter;
- a schema-migration or branch/merge implementation;
- a projection compiler or a canonical commit-back path;
- a canonical permit verifier—the configured grant adapter has no expiry or
  revocation semantics;
- an LLM function-cell executor;
- an outcome-bound learning rule, semantic-weight learner, or causal efficacy
  result;
- evidence that single-owner outperforms multi-owner, fixed-role, or other
  accountability schemes.

The state remains `SCIENTIFIC_UNJUDGED`. Tests establish executable invariant
closure only.

## 5. Verification and next order

Focused tests cover strict ingress, open registries, schema/lineage/revision
identity, owner validity, relation endpoints, hidden reads, immutable revision,
owner-change rejection, migration rejection, permission separation, frozen
snapshots, all-or-nothing batch failure, and concurrent one-winner commit.

The content-bound continuation completed the former first step and bound schema
and atom-envelope bytes without claiming durable state. The next implementation
order is:

1. add a predecessor-bound durable state-and-receipt journal with exact replay
   against every referenced content blob;
2. represent authorization, trace, outcome, and provenance evidence as typed
   canonical atoms without creating a bootstrap regress;
3. add explicit quarantine and rejected-decision receipts;
4. specify schema migration, fork, merge, and rollback/compensating restore;
5. add loss-declared projection compilation and forbid direct view commit-back;
6. only then introduce sealed trajectories and outcome-bound learning
   proposals.

No research receipt or results-log entry is created for this change because it
is routine engineering closure, not a material scientific result.
