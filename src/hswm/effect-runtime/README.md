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
