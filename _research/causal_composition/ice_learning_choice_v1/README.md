# ICE co-eligible counterexample-choice pilot

Status: `LOCAL_SYNTHETIC_ENGINEERING_PILOT_NOT_EFFICACY`.

This manifest is an authored, closed engineering fixture. It does not contain an
ICE case, user data, a real counterexample result, an external source resolver,
or an HSWM efficacy result. Both routes execute deterministic local Node
commands under the same declared context, complete task text, executor kind,
allowed cells, `cost_hint`, and run budget. Both preserve the same
`evidence == available` guard; unavailable evidence withholds both. Their
actual order differs: `check-existing -> construct-new -> complete` versus
`construct-new -> check-existing -> complete`, while `complete` has the same
output and exit-code check for both. `--force-route` only establishes
that each already-eligible route can execute; it is never evidence that the
learner selected the better route.

`check-first` verifies an existing-counterexample premise first;
`construct-first` constructs a new counterexample first. Their common completion
exit-code observations are equally valid only for this synthetic command
contract. They do not answer which action would be better on an unobserved
investigation.

The command fixture tests the synthetic claim `n*n>=n+1 for nonnegative
integers`. `check-existing` verifies the declared `candidate_n: 0` witness;
`construct-new` searches the finite range `0..4`; `complete` independently
rechecks both resulting witness records before emitting one canonical JSON
artifact. This is a deterministic engineering predicate, not an ICE claim.

## Query scope

The fixture is the smallest semantic example for the current remediation design
[v2](../../../ontology/evidence/HSWM_ICE_LEARNING_REMEDIATION_2026-09-08.v2.json):

- **Q1** records the complete co-eligible choice set, selected relation and
  declared reads in the native runtime plan/trajectory.
- **Q2** is intentionally limited to native executor outcomes; it does not
  implement output-bound human review or causal credit.
- **Q3** has no learned child guard. Parent-condition preservation is a WP1
  prerequisite outside this fixture.
- **Q4** does not generate a next question or call a resolver.
- **Q5** holds declared route cost and execution budget equal; measured wall
  time is not a utility conclusion.
- **Q6** pins this example to the remediation v2 design link above. It does
  not publish, replace, or recommend a KG bundle.

The intended semantic mapping is explicit: `I2 -> M1` (co-eligible choices),
`I3 -> M2`, `I4 -> M3`, `F1 -> M1` through `F5 -> M5`, and `M4 -> E2`.
This fixture exercises only the I2/M1 viability surface. It does not establish
any of those other remedies, an E1 choice effect, an E2 total effect, or a
causal relation.

The companion Vitest keeps frozen and learning arms in distinct temporary
SQLite files. A frozen UID tie-break is a deterministic baseline, and a learned
route change merely demonstrates that the current local score can mediate a
choice when two routes are genuinely eligible.

## Reproduce

The test is the portable reproduction path:

```bash
cd src/hswm/effect-runtime
./node_modules/.bin/vitest run ../../../tests/effect-runtime/ice-learning-choice.test.ts --maxWorkers=1
```

To exercise a forced viability route through the native CLI after its local
build, use `--route` (not a nonexistent `--force-route` option):

```bash
cd src/hswm/effect-runtime
node dist/hswm-live-process.js --program ../../../_research/causal_composition/ice_learning_choice_v1/counterexample-choice.v1.json run --workspace ../../.. --state /tmp/ice-choice-check.sqlite --context '{"evidence":"available","goal":"counterexample","candidate_n":0}' --task 'synthetic counterexample investigation' --episode check-first --route check-first --frozen --budget 1
```
