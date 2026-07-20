# EPWC implementation receipt — S0 through S2 (2026-07-20)

## Verdict

HSWM now has an implemented **Evidence-Preserving World Compiler** boundary and
a lossless seam into the existing field/readout prototype. This slice does not
claim that the Certified Readout Envelope exists yet.

- **S0 complete:** the stale-poisoning falsifier uses actual supersede writes,
  includes the separated-graded arm (e), publishes write/traversal receipts,
  and reports the preregistered hop-2/3 population separately from all hops.
- **S1 complete:** frozen sources and recorded observations compile through a
  pure deterministic function into immutable, content-addressed World IR or a
  typed fail-closed rejection.
- **S2 complete:** legacy QA labels are outside the World IR; positional dense
  IDs live only in an explicit compatibility layout, while valid legacy field
  and readout behavior remains bit-identical.
- **S3 pending:** immutable field snapshots, policy certificates, runtime
  admission/refusal, event-folded revision state, as-of replay, and
  compensation are not implemented in this receipt.

The falsifier also narrows the claim. Arm (e) is bit-exact with arm (a), so
kill (iii) fires on both real datasets: graded revision does **not** require its
state to live inside one field object. The defensible engineering center is now
evidence preservation, deterministic compilation, snapshot binding, replay,
audit, and certified refusal.

## S0 — claim and falsifier repair

`stale_poisoning.py` now provides:

- an immutable external separated-revision representation for arm (e);
- real `readouts.supersede()` mutations with deterministic write receipts;
- current/audit bit-equivalence receipts for arms (a) and (e);
- traversal trip counts, reasons, measured `n_eff`, and path receipt counts;
- tie-correct midrank Spearman rho;
- hop-2/3 preregistered primary metrics plus separately labeled all-hop metrics;
- wrong-write collateral through the same supersede path.

| corrected primary result | MuSiQue | 2Wiki |
|---|---:|---:|
| primary population | n=134 (67 hop-2, 67 hop-3) | n=100 (hop-2) |
| all-hop population | n=200 (+66 hop-4) | n=200 (+100 hop-4) |
| rho, arm a = arm e | -0.9853 | -0.9233 |
| current delta vs hard filter at b=.5 | -1.24 pt | -0.50 pt |
| same delta, all hops | -1.08 pt | -0.62 pt |
| wrong supersede at b=.1, primary | -12.69 pt | -31.0 pt |
| wrong supersede at b=.1, all hops | -8.5 pt | -16.0 pt |
| kill (i) | fired: 0.000 <= 2SE 0.000 | fired: 0.005 <= 2SE 0.010 |
| kill (iii) | fired; a/e bit-exact | fired; a/e bit-exact |

Result artifact SHA-256 values:

- `stale_poisoning_musique_result.json`:
  `f381d397594f2a6002f8f78b72ddbfc133acc0fa5fb7515a49dd073b2dd87381`
- `stale_poisoning_2wiki_result.json`:
  `ff7b218e7a893e60db187660512a23445e4353e96d73ac1c14f22f32138ecd12`
- `stale_poisoning_fixture_result.json`:
  `6cc8500add201bf332df165675ef4fa80d15e5e7d16e7282fc2fa90ee2540a8f`

## S1 — immutable World IR and pure compiler

`world_ir.py` defines versioned frozen records for sources, exact text
selectors, mention and embedding observations, evidence units, entities, field
targets, manifests, evaluation suites, and typed compile issues. Durable IDs
are content-addressed; dense numpy positions are not part of their identity.

`world_compiler.py` exposes:

```python
compile_world(
    SourceBundleV1,
    ObservationBundleV1,
    CompilePolicyV1,
) -> WorldArtifactV1 | CompileRejectionV1
```

The compiler performs no filesystem, network, model, clock, or random access.
It verifies source digests and IDs, exact selector quote/context, normalization
policy, observation IDs and output hashes, references, embedding dimensions and
finiteness, and deterministic duplicate-conflict quarantine. Unsupported
projections and zero-width selectors fail closed. `verify_world_artifact()`
recompiles the attached source/observation/policy preimages and detects artifact
tampering.

The canonicalization contract is a repository-versioned, sorted UTF-8 JSON
profile; it does not claim full RFC 8785/JCS conformance.

## S2 — lossless legacy seam

`legacy_adapter.py` separates three concerns:

1. `WorldArtifactV1`: stable, order-invariant world identity;
2. `EvaluationSuiteV1`: questions, answers, hop labels, and gold targets;
3. `LegacyProjectionLayoutV1`: first-seen dense ordering needed by old numpy
   code.

The adapter preserves the legacy builder's paragraph identity, title/body
normalization and document-frequency rules, sorted entity vocabulary,
first-seen unit order, float64 arrays, query order, gold order, hop parsing,
stats, and exact two-call embedding protocol. Invalid/ragged/non-finite
embeddings, unknown gold targets, and empty artifacts become typed
`LegacyCompileError`s rather than raw numpy/lookup exceptions.

Parity tests cover field construction, retrieval, selection distribution,
dispatch, and mu=0 traversal. `readouts.plan()` remains a bit-exact compatibility
alias for the honestly named `selection_distribution()`.

## Verification

All commands used Python 3.11.

- S0 focused tests: **13 passed**.
- World Compiler + legacy parity focused tests: **22 passed**.
- Combined changed-surface tests: **35 passed**.
- Full repository suite: **85 passed in 12.61s** on the final source state.
- JSON contract audit: passed for MuSiQue, 2Wiki, and fixture artifacts.
- `git diff --check`: passed.
- Wheel build: `hswm-0.1.0-py3-none-any.whl` built successfully.
- Wheel-only import: `world_ir`, `world_compiler`, `legacy_adapter`, and
  `stale_poisoning` imported from the wheel, not the source worktree.
- Temporary wheel/build products were removed after verification.

## Files in this slice

New implementation and tests:

- `world_ir.py`
- `world_compiler.py`
- `legacy_adapter.py`
- `tests/test_world_compiler.py`
- `tests/test_legacy_adapter.py`

Repaired implementation, claims, results, and packaging:

- `stale_poisoning.py`
- `tests/test_stale_poisoning.py`
- `readouts.py`
- `tests/test_readout_identity.py`
- `stale_poisoning_{musique,2wiki,fixture}_result.json`
- `STALE_POISONING_RESULTS_2026-07-19.md`
- `README.md`
- `pyproject.toml`

## Explicit limits and the S3 gate

- The compiler currently supports only the fail-closed `paragraph-v1`
  projection. Assertion/n-ary compilation is future work.
- Legacy locators are synthetic content-addressed `legacy://paragraph/...`
  locators, not original upstream dataset locators.
- Mention observations preserve producer/version/output digest, but not yet a
  complete model/prompt/config/input/raw-output provenance bundle.
- Existing supersession remains a positional, in-place compatibility write.
- No immutable `FieldSnapshotV1`, certified policy envelope, durable event
  ledger, as-of fold, or compensation protocol exists yet.

S3 should land only when the following acceptance test can pass: a readout must
bind one immutable world build, field snapshot, model/config digest, policy
certificate, and revision cut; an unbound or uncertified combination must
refuse execution; replay of the same event cut must be deterministic; and an
operator must be able to inspect both current and as-of evidence without
deleting the superseded record.

Repository state: changes are intentionally uncommitted on top of base
`8ee4694`; no push and no KG write were performed.
