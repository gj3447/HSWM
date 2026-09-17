# Semantic revision admission and CI repair

2026-09-17 · T0 engineering. Source base:
`ac0ee0c495c58d395c985f86bfcadb4787cbce19`.

## Observed failures

The F3 cache commit exposed existing CI failures; the same failures were
present at `f3772f9c1e5b9982ff33b8882cc99c6042e698e4`. Compare
[baseline CI](https://github.com/gj3447/HSWM/actions/runs/35175157481) and
[F3 CI](https://github.com/gj3447/HSWM/actions/runs/35179780700).

The Effect failure was a real architectural violation:
`learnLlmSemanticRelation` directly submitted a canonical durable mutation.
The existing enforcement test requires production graph updates to pass
through the graph-loop controller. The test and its allowlist are preserved.

The Python failures had separate causes: graph tests running without their
locked RDF/SHACL environment, query-result/count reports being treated as
ontology node arrays, an omitted transitive DNRD source input, and source
distribution omissions or repository-only tests.

## Semantic API migration

`prepareLlmSemanticRelationRevision` performs the existing trace, outcome,
backend and stale-frame checks, stages content, and returns a content-bound
revision proposal. Staging content does not admit it into canonical state.

`learnLlmSemanticRelation` now requires a final explicit admission capability.
There is no default raw durable submit. Existing callers must supply an
admission owner; the repository had only fixtures and documentation using the
old signature. This is an intentional public API change even though the
package remains private and version `0.0.0`.

`makeLlmSemanticGraphLoopAdmission` connects that proposal to the existing
controller. Its caller supplies the run contract, action descriptor,
verification decision and outcome descriptor, and graph evidence descriptors.
These inputs are not generated from the semantic prediction or outcome.
`CALLER_DECLARED_NOT_INDEPENDENTLY_VERIFIED` and
`REFERENCE_AUTHORIZATION_NOT_CANONICAL_PERMIT` retain their exact meanings.
An engineering admission is not proof of independent observation, causal
credit, learning efficacy, or canonical ratification.

Only `ACCEPT` reaches `submitDelta`. `RETRY` schedules a new bounded attempt;
an exhausted attempt or action budget escalates the run. `REJECT` stops the
run without committing a revision. Factory inputs are copied and frozen before
the Effect executes. The adapter preserves a controller's actual `COMMITTED`,
`REJECTED` or `QUARANTINED` result; accepting verification alone is not reported
as a successful commit. Retry scheduling never replays the LLM request itself.

The older research implementation document is source-hash-bound and remains
an exact historical record. This dated migration note describes the changed
API; it does not rewrite that document's verification snapshot.

## CI and package contracts

- Graph-dependent frontier projection and research-tooling query tests run in
  the existing separately locked graph environment. Repository coverage is
  preserved instead of hiding dependency failures with skips.
- The adaptive ontology test scans node-array bundles and ignores query result
  arrays or reports whose `nodes` field is a numeric count. Duplicate identity
  and external-anchor assertions remain unchanged.
- DNRD's current source closure now includes `native-pinned-verifier-runtime.ts`,
  imported through `effect-posix-services.ts`. Historical frozen manifests and
  experiment evidence are not rewritten.
- The Python source distribution transports paired Cypher/SPARQL queries,
  projection artifact JSON in the two typed artifact directories, the exact
  occurrence worker lock, and two explicitly bound D4 source files. The
  independent Effect package remains otherwise pruned.
- SHACL payload verification checks all seven intended shape files. Tests that
  require fixed Git objects or the pruned Effect/workflow tree remain active
  repository tests and are excluded from the Python tarball.
- The frontier module's two historical Git tests moved unchanged into
  `test_frontier_learning_historical_snapshot.py`. Its self-contained
  validation/export tests remain in the tarball and run with graph dependencies.
- Source-distribution CI extracts under `runner.temp`, outside the checkout.
  A parent Git database can no longer hide a missing distribution input.

## Validation

On 2026-09-17 with Node 24.13.0, the semantic admission suite passed 10 tests,
including real file-backed CAS quarantine and authorization rejection. The
unchanged production boundary enforcement test passed separately. TypeScript,
temporal types, Effect/functional lint, and both build targets passed. The
Effect lint retained its 38 existing exceptions and reported zero violations.

`hswm-dev hswm plan/run/status/feedback` recorded episode
`20260917-semantic-admission-ci`, selecting `relation:runtime-focused` and
passing 55 shared runtime regressions. Feedback is explicitly `agent(codex)`:
useful shared regression coverage, with direct feature/package checks also
required. This profile does not select the semantic admission tests itself.

An extracted source distribution outside any Git checkout passed all 51 graph
tests. Its first full non-graph run returned **3493 passed, 49 skipped, 5 failed**
in 686 seconds. The failures identified four Effect repository-closure tests
and one Git-history ledger test; they are retained as repository tests, while
their self-contained companion tests remain in the distribution. The failed
run is not presented as an all-green full run. Final focused verification is
**39 repository tests passed**, including the five retained checks, and
**20 tests passed in a newly rebuilt/extracted tarball**, including actual
package-content assertions. AST comparison confirmed all 12 test function
bodies across the split Effect-boundary and ledger modules were preserved.
The DNRD source-closure checks also passed (61 tests); the adaptive ontology
scan passed all 12 checks after its shape guards were corrected. Hosted CI is
the subsequent full-run check; no later CI outcome is assumed in this snapshot.

No HSWM scientific result, identity statement, CR/FCL status or efficacy claim
is changed by this engineering repair.
