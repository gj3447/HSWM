# HSWM USL adapter v2

Status: `EXPERIMENTAL_EXTERNAL_REFERENCE_OBSERVATION / NOT_HSWM_EFFICACY`.
The adapter consumes supplied USL v2 JSON; the example uses injected resolvers.
It does not call an endpoint, execute a declared check, create a KG
record, admit an atom, assign causal credit, or learn.

## Use the v2 adapter

```bash
uv run --locked hswm-usl preview --request _research/usl_adapter/examples/preview.v2.json
```

The fixture returns `hswm-usl-preview/v2`, adapter status `READY`, and an
`ACTION_PROPOSAL` to inspect development references. The proposal is not
executed. Advancing `preview.checks.now` by 120 seconds produces `OBSERVE`
because the fixed fixture observations have expired. Real work requires a
fresh observation and caller-selected policy pins.

Both `project` and `preview` dispatch by the report schema. Legacy v1 reports
and policies retain their old behavior. V2 requires
`hswm-usl-observation-policy/v2`: the existing namespace, plan_digest,
max_age_seconds, bindings and resource pins, plus `usl_plan_digest` and
`source_digest`. The caller must establish these pins independently of an
untrusted report. Copying unknown report hashes into the policy is not
independent verification.

The adapter validates the full supplied plan, selected meaning definitions,
contract digests, exact selected report scope, resolution status, check evidence
mapping, `NOT_EXECUTED` status, resource budget and derived metrics. Selected
meanings/checks, read scope, metrics and USL digests are retained in the v2
projection. It rejects inconsistent fields even after the outer observation
digest has been recomputed. Missing, DENIED, stale or future-dated evidence
cannot produce a readiness observation. Missing selected rows are malformed
and rejected; valid unresolved rows produce `UNKNOWN`.

USL `JSON.stringify` hashes preserve object key order; retain the original
plan/report objects when assembling requests rather than sorting their keys.
The adapter's bounded JSON wire subset supports safe integers, strings,
booleans and null, with no floating point report values. HTTP URL policy keys
support ASCII hosts, root slash/default port/host case normalization and
canonical IPv4/IPv6. Userinfo, Unicode URL text and dot-segment spellings must
be normalized upstream into the supported representation; unsupported forms
are rejected instead of inferring permission equivalence.

Normally pin a non-null source digest. USL also supports sourceText-omitted
API observations: these require an explicit null `policy.source_digest` and
emit `source_binding: ABSENT`. A non-null policy pin rejects a null or changed
report source digest. The adapter does not recompile USL source or attest
authorship; READY means reference readiness under the supplied policy.

## Recreate the fixture

From the HSWM checkout, with the current local USL checkout already installed:

```bash
/home/lagyeongjun/CD/USL/node_modules/.bin/tsx \
  _research/usl_adapter/regenerate_preview_v2_2026_09_08.ts \
  --usl-root /home/lagyeongjun/CD/USL \
  --out _research/usl_adapter/examples/preview.v2.json
```

The authored input is
[`development_reference.v2.usl`](../../_research/usl_adapter/examples/development_reference.v2.usl).
It declares `development` and an unrelated link. The generated report selects
only `development`: its three participants and the `documents` grounding are
the four allowed/requested locators. Its contract check is reported
`NOT_EXECUTED`, and its semantic truth remains `NOT_EVALUATED`.

The policy pins exactly those three participants and `meaning:documents`. It
uses three independent identity lanes: HSWM's sorted-JSON `plan_digest`, USL's
`usl_plan_digest`, and the USL source-text `source_digest`. The fixture embeds
the source digest; regenerating against another USL source may legitimately
change USL-derived values. The local USL directory has no source commit, so
this is a reproducible fixture rather than a release-qualified integration.

## Verification

The related v1/v2 adapter, CLI, conditional-preview and canon-honesty tests
pass: 75 tests. CLI output preserves USL definition key order so embedded
digests remain valid after JSON serialization. Actual local USL compile and
observe calls reproduce fresh ACTION_PROPOSAL and expired OBSERVE with
injected endpoint results. Source hashes and the results are recorded in
[`adapter_v2_verification_2026-09-08.json`](../../_research/usl_adapter/adapter_v2_verification_2026-09-08.json).
These are interface checks, not developer-time or learning-effect measurements.

## Findings to return to USL

The injected source review records two report-integrity bugs in
[`review_v2_digest_probe_2026-09-08.json`](../../_research/usl_adapter/review_v2_digest_probe_2026-09-08.json).

1. `sourceText` is read again after resolver I/O. A caller can mutate that
   option during I/O and obtain an original plan digest paired with a different
   source digest. Fix by snapshotting source text once before compilation and
   deriving both plan and source digest from that immutable snapshot. A test
   must demonstrate that mutation during an injected resolver call cannot
   change the reported source digest.
2. The v2 report validator accepts a self-consistent forged aggregate
   `status`, `readScope`, `metrics`, `resourcesResolve`, and
   verification status when its outer digest is recomputed. Fix by validating
   each field against the plan and observations, including selected links,
   requested and allowed locator shapes, counts, resource resolution, and the
   fixed `NOT_EXECUTED` contract status. A test must reject every altered field
   after recomputing the observation digest. Full plan/source digests require
   the original plan/source or independent caller pins; a digest alone is not
   an authorship check.

Until those are fixed and independently rechecked, HSWM treats a supplied USL
v2 report as caller-bound observation data. It never treats its digests as an
attestation, endpoint resolution as semantic truth, or the boolean readiness
projection as an execution authorization.
