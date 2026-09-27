# Integrated bounded HSWM closed-loop proof audit

This profile extends the existing TypeScript/Effect Lean auditor without
rewriting its prior receipts or its default three-philosophies profile. It
audits a finite closed-loop model only: canonical relation serialization and
revision, a local semantic-program execution abstraction, and a declared
evaluation witness.

```sh
npm --prefix src/hswm/effect-runtime run build
node src/hswm/effect-runtime/dist/semantic-philosophy-proof-process.js \
  --profile integrated-hswm \
  --output .hswm-local/integrated-hswm-proof-$(date +%Y%m%dT%H%M%SZ)
```

The profile compiles the default thirteen dependency modules, then
`HSWMLLMSemanticGraph`, `HSWMIntegratedClosedLoop`, and
`HSWMClosedLoopEvaluation`. It runs `#print axioms` for the three earlier
philosophy modules and the two new closed-loop modules. Source bytes and the
auditor source itself are rebound before the private receipt is written.

The resulting `lean-verification.v1.json` has claim ceiling
`CONDITIONAL_FINITE_CANONICAL_CLOSED_LOOP_NOT_FULL_HSWM_OR_REAL_LLM`. A passing
receipt checks declared finite Lean statements under the pinned compiler. It
does not establish full HSWM, an actual LLM's fidelity or learning efficacy,
or a general closed-loop world model.
