# HSWM Effect runtime

This private package is the TypeScript/Effect production-runtime seed for
HSWM. It currently implements one narrow, engineering-only transaction:
crediting an already eligible trajectory against an existing role-aware
hyperedge and registered function cell.

The boundary is intentionally small:

- `domain.ts` is a deterministic, side-effect-free `H/W/A/F` transition.
- `schema.ts` decodes unknown input and snapshots accepted values.
- `runtime.ts` supplies the Effect shell: a capability-service port, typed
  failures, Layers, and one atomic state-plus-journal transaction.
- the existing Python/NumPy SWM experiments remain research/reference oracles;
  they are not silently relabeled as this runtime.

The SWM-0W-S2S confirmatory control slice is also present, but remains
pre-dispatch engineering:

- `s2s-confirmatory.ts` freezes the pilot-adoption binding, integer resource
  policy, exact seed contract, closed monotone phases, five VOID reasons, and
  the permanently disabled DS-derived compact-competitive phrase.
- `s2s-orchestration.ts` defines typed Effect ports for the Python numeric-only
  oracle, verified pulse source, artifact readback, and durable run evidence.
  It contains no live adapters and performs no beacon, GitHub, or numeric run.
- Python-owned `numeric_candidate.json` and `numeric_adjudication.json` remain
  opaque canonical bytes. TypeScript hashes them raw and reads only a strict,
  hash-bound adjudication projection; it never co-authors their receipt tree.
  The candidate phase therefore binds only the raw candidate and confirm-request
  hashes. Its Python receipt is admitted later from adjudication output, after
  the Python replay has validated the candidate's canonical self-receipt.
- the `Ref` control-plane Layer is test-only, intra-process simulation. Three
  GitHub jobs must reconstruct state from immutable predecessor-linked bytes
  and fresh API/download readback; the Layer is not durable truth and does not
  imply exactly-once external effects.

This is a `Π` control/evidence boundary around the Python numeric oracle, not a
new learned `W`, an S2S efficacy result, or authorization to dispatch the
future-seeded gate. Raw transition, store, adapter, and generic-submit
capabilities are intentionally absent from the package root export until a
production orchestrator owns all provenance checks end to end.

Independent exact-byte review has cleared the repaired source-A/B, pulse,
resource-accounting, and artifact-size invariants. The slice remains
`BLOCKED_PRE_PREREG` because live Git/GitHub/drand/Python/artifact adapters and
the durable three-job chronology are still absent. Resume from the repository
[`next-session handoff`](../../../docs/operations/HSWM_SWM0W_S2S_EFFECT_NEXT_SESSION_2026-08-21.md)
before adding live adapters or selecting a future round.

The in-memory Layer's static capability-ID allowlist is configuration for tests
and local scaffolding, not identity authentication. This slice is not evidence
of learned set-to-set `W`, durable causal learning, or a complete HSWM. A
production store, capability verifier, and outcome/provenance verifier are still
required before durable use.

Run the exact local verification surface with:

```sh
npm ci --ignore-scripts --no-audit --no-fund
npm run verify
```
