# Open HSWM kernel v2 — counterexample-driven amendment

> **base theory**: `theory-open-self-similar-hswm-20260722`
> **supersedes implementation**: `ENG-open-composition-kernel-v1` (`partial`)
> **status**: SECONDARY_AI engineering repair; USER_PRIMARY direction unchanged
> **scope**: deterministic composition kernel only, not learned agent/readout performance

## 1. Why v2 exists

The v1 preregistered fixture passed, and LakatoTree correctly returned `partial`. Independent
counterexample review then found five blockers outside that frozen fixture.

1. bare local port names collide globally during composition;
2. raw `OpenHSWM(...)` construction bypasses connector admission;
3. mounted legacy `Field` objects remain mutable aliases behind a stale digest;
4. separation manufactures non-injective delimiter-concatenated boundary interface IDs;
5. legacy `_rebuild()` drops isolated vertices, making eager merge order-dependent under a later
   metadata conflict.

Two additional boundary defects are repaired at the same seam:

- overlapping mount-local edge IDs may not silently collapse during materialization;
- an edge with empty provenance is rejected when captured, even though the legacy constructor
  accepts the key.

The v1 files and receipts remain immutable historical evidence. v2 is a new kernel and a new
prediction node, not a post-hoc rewrite of v1.

## 2. v2 decisions

### D1 — injective mount-qualified default interfaces

An atomic port's default interface ID is a length-prefixed encoding of `(mount_id, port_id)`:

```text
q + len(mount_id) + ':' + mount_id + len(port_id) + ':' + port_id
```

The address remains the structured `PortAddress(mount_id, port_id)`. Independent HSWMs may both
use a natural local port ID such as `entry` without collision. Explicit aliases remain optional
and must themselves be globally unique within the resulting manifest.

### D2 — factory-sealed canonical construction

`OpenHSWM` has no public raw constructor. Canonical instances arise only through:

```text
empty / from_field / compose / specialize / separate.recompose
```

Only `compose` admits a new connector, and it checks each endpoint against the operand's currently
exposed interface addresses. Internal reconstruction is private and is used only with state already
admitted by a prior canonical instance or a sealed separation receipt.

### D3 — immutable field snapshots

A mount owns `FrozenFieldSnapshot`, not a live `Field` alias. Capture freezes:

```text
vertices, edges, provenance, ledger, seams, legacy field digest
```

Embeddings remain explicitly derived/non-canonical, matching the documented legacy `field_id`
boundary. `thaw()` creates a new defensive `Field` only at explicit materialization. Mutating the
caller-owned source field after wrapping cannot change the manifest or later materialization.
Legacy `SeamArc` inputs are rebuilt as string-only records at capture and again at each mutable
output boundary; caller-owned seam objects or nested mutable payloads are never retained. Edge
members and evaluation clusters are likewise string atoms; nested mutable cluster payloads are
rejected rather than shallow-tupled into the snapshot.

### D4 — structured separation receipts

Separation does not mint boundary interface strings. A factory-sealed `SeparationResult` retains
the immutable parts, exact cut connector records, original interface projection, and source digest.
Its trusted `recompose()` restores those records directly and verifies exact digest equality.

### D5 — safe explicit materializer

v2 does not call legacy `merge_all()`.

- all snapshot vertices are unioned, including isolated vertices;
- same vertex/edge ID with different payload fails closed before reconstruction;
- every edge must have at least one provenance source;
- connector lowering still supports only binary `canonical_identity`;
- a lowered `canonical_identity` must have exactly one `left` and one `right` endpoint role, and
  vertices are assigned to `SeamArc.left_vid/right_vid` by role rather than tuple order;
- if distinct endpoint addresses resolve to the same legacy vertex, lowering fails closed because
  `SeamArc` cannot retain the port-level role distinction;
- duplicate field mounts are rejected;
- overlapping edge IDs across mounts are rejected unless the caller explicitly lists them in
  `shared_edge_ids`; declared shared edges must have identical payload and identical weight.

Thus materialization is an explicit quotient with a named sharing capability, not a silent collapse.

## 3. v2 falsifiers

The v2 node fails if any of the following holds.

1. two operands with local port ID `entry` cannot compose;
2. direct `OpenHSWM(...)` construction succeeds;
3. a connector over a non-exposed operand port enters through public API;
4. mutating the source `Field` changes a mounted digest or materialized result;
5. operand order chooses a different live field alias;
6. delimiter-heavy IDs break separation/recomposition;
7. an isolated vertex disappears during materialization;
8. conflicting isolated-vertex metadata depends on grouping/order;
9. empty provenance is captured;
10. an overlapping edge silently collapses without `shared_edge_ids`;
11. a declared shared edge with unequal payload/weight is accepted;
12. `compose` calls or simulates materialization;
13. v1 and legacy regression suites break.

## 4. v2r2 independent counterexample wave

The first v2 fixture exposed one contradictory test oracle (`1 failed, 51 passed`): the test tried
to materialize two mounts of the same frozen field even though the preregistered multiplicity law
requires that quotient to fail closed. The r1 child node corrected only that oracle and passed
`52/52`; no implementation semantic was relaxed.

An independent read-only review then found three further boundaries not covered by r1.

1. a legacy `SeamArc` could contain a mutable nested payload and survive shallow snapshot capture;
2. postponed PEP 604 union annotations imported on Python 3.9 but broke `typing.get_type_hints`;
3. binary identity lowering discarded endpoint roles, so semantically distinct manifests could
   collapse to the same legacy field.

The v2r2 tests were hashed and registered before the repair run. They require:

- rejection of non-string seam state and defensive copies at snapshot and output boundaries;
- public API type-hint resolution on the repository's Python 3.9.6 runtime;
- rejection of unadapted identity roles and role-directed `left/right` lowering.

The frozen red run was `5 failed, 52 passed`; the repaired target run was `57 passed`, and the
expanded v1/B0/B2/hypergraph regression run was `76 passed`. These are engineering receipts, not a
scientific-progress verdict.

Two reviewed behaviors remain deliberate rather than silently implied security properties:

- underscore-prefixed constructors are cooperative Python internals, not an adversarial in-process
  security boundary;
- `HIDE` is an interface projection, not irreversible revocation, so a later explicit `EXPOSE` may
  re-export a public port. Same-call connector admission still uses only interfaces exposed by the
  operands before that composition.

A second independent re-audit of the green r2 code found two residual non-injective boundaries:

- `FrozenEdge.clusters` shallow-tupled a nested mutable value;
- two distinct role-bearing ports could resolve to one legacy vertex and collapse into the same
  self-seam.

These counterexamples were observed before the v2r3 repair prediction, so the child node is
explicitly **post-red engineering TDD**, not blind preregistered science. Its script hash was frozen
before implementation changed. The red expanded run was `2 failed, 76 passed`; after validating
cluster atoms and rejecting same-vertex identity lowering, the target run was `59 passed` and the
expanded run was `78 passed`.

## 5. What this still does not solve

- relation-specific type/role/polarity compatibility or adapters;
- bounded readout over cyclic connector graphs;
- learned CONNECT/SEPARATE/SPECIALIZE policies and event persistence;
- multi-agent transfer and B2.1 interference-control performance.

Those remain LakatoTree foundation/frontier gaps. Passing v2 is an engineering closure result only.
