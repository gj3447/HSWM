# Native USL → bounded relation-program instrument

Status: `LOCAL_SYNTHETIC_INSTRUMENT_QUALIFICATION_ONLY`.
This is an authored, same-process study, not G0/G1, canonical admission, a new
primitive invention claim, an LLM training run or a real KG deployment.

Read the [results and limitations](../../../results/HSWM_USL_RELATION_INSTRUMENT_RESULTS_2026-09-08.md)
and [fixed protocol](protocol.v1.json) before interpreting numbers.

The existing local USL checkout supplies `connectUsl({ read, adapt, policy })`.
Owner data stay in the owner fixture. Every request reads it again; the current
request and its prepared HSWM handoff share one version. No `.usl` source, new
USL database, manual compilation command or live KG configuration is required.
The HSWM snapshot keeps the native source digest and identities outside the
inner USL/HSWM prepared bundle; an absent authored-source digest remains null.

The new HSWM research consumer is pure TypeScript:

```ts
const response = yield* connection.hswm(request, options, authority)
const snapshot = yield* captureUslNativeSnapshot(response, expected)
// expected comes from the caller, not from the returned report.
// snapshot.relations keeps native UIDs, USL plan role order and full meanings.
```

This snapshot validates transport integrity from a trusted adapter. It does not
authenticate unavailable native source bytes, validate the truth of a relation,
or grant authority. The finite DSL learner consumes selected declared relations
and separately supplied outcome labels. No LLM or Python is executed by this
study runner; metadata checks or legacy repository tests are separate workflows.

## Reproduce a new instrument attempt

The final source-pins.v4 manifest binds 12 HSWM files and 34 local USL
source/contract files, including both dependency locks. The external USL working tree was dirty at capture:
its Git base alone is insufficient. Obtain the exact authorized local bytes;
the runner refuses drift and this repository does not redistribute USL source.
Use the already installed, pinned launcher. Do not install a floating package.
Attempt 04 used an isolated, read-only local copy of those authorized USL source
bytes to prevent concurrent source edits. This was not a copy of owner data or
a USL database; the private, UNLICENSED source is not redistributed here.
In the command below, set USL_STUDY_ROOT to that exact source copy. A current
sibling checkout is usable only if every manifest hash still matches.

From the HSWM checkout:

```bash
src/hswm/effect-runtime/node_modules/.bin/tsc \
  -p _research/causal_composition/relation_synthesis_usl_v1/tsconfig.json

USL_STUDY_ROOT=/path/to/exact-pinned-usl-source
"$USL_STUDY_ROOT/node_modules/.bin/tsx" \
  _research/causal_composition/relation_synthesis_usl_v1/run.mts \
  --usl-root "$USL_STUDY_ROOT" \
  --source-pins _research/causal_composition/relation_synthesis_usl_v1/source-pins.v4.json \
  --output /tmp/hswm-usl-relation-reproduction-01.json
```

Use a fresh output filename. Existing results are never replaced, including
failed attempts. A repair requires new source pins and a separately identified
attempt; it does not rewrite the original protocol/result. Timestamps and wall
time will differ. Candidate persistence and restoration are exact bytes.

The current [adapter profile](adapter-profile.v3.json) parses structured native
type/direction/description. USL v2 sorts named roles; its response alone cannot
recover original participant array order. The host retains order metadata from
the same owner read, binds it to the raw digest, verifies every role/UID binding,
and restores that order in the research feature view. The original ordered
equality criterion is unchanged. The full snapshot retains direction and free
description; the finite DSL selects only type and role incidence. Equality of
these features is not universal graph semantic equivalence.

All attempts are retained: 01 completed with the legacy meaning profile; 02
failed on the updated mapping; 03 failed on ordered-role equivalence; 04 completed
with profile v3. Attempts 02/03 have no efficacy verdict. The attempt-01 source
receipt resolves historical HSWM files at commit 7450aa1; it must not be checked
against later changed bytes. Final attempt 04 uses commit dca9d64 and pins v4.
The two completed attempts are different instrument versions, not independent
replications. See the results document for the malformed-digest repair and the
incomplete transitive source coverage of failed attempt 02.

The program AST is intentionally restricted to declared hops and finite set
operations. Its selected 3-hop composition is absent from the one-hop seed
library, while the information-matched native induction yields the same AST.
That equality qualifies the adapter path; it does not demonstrate an additional
HSWM advantage. See protocol `unmet_confirmatory_requirements` for the remaining
independent outcome, LLM, strong comparator and canonical-revision obligations.
